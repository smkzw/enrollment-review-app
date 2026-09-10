"""人工事实修订后资料期望重投影：同源缺口信号重建回归（合成数据）。

历史缺陷（本文件前身以 strict xfail 复现，现修复后转为常驻回归）：

- 缺陷 A（显式风险丢失 → 静默升级）：``_reproject_expectations`` 曾以硬编码
  ``gap_signals=[]`` 重投影，原运行经持久化未解决项记录的 ``ocr_or_parse_risk``
  被丢弃，``observed_weak`` 静默升级为 ``observed``。
- 缺陷 B（无覆盖无信号 → 整次修订回滚）：到期模板失去全部覆盖事实且无信号时
  ``project_expectation`` 按设计抛 ``ProjectionInputError``，整次合法修订以
  ``FACT_CORRECTION_APPLY_FAILED`` 回滚。

修复（app/services/fact_expectation_gaps.py，唯一共享推导）：

- 修订重投影与原始终结共用 ``expectation_gap_signals``；
- 源运行只从「当前权威下活动实体引用的运行 ∪ 本次修订目标沿不可变修订记录
  回溯可达的运行」中选取，逐运行校验权威元组，拒绝成环/汇聚/缺失谱系；
- 先前期望中无法按所选源记录复核的显式风险，以非默认 ``observation_unverified``
  保守保留（不重写历史期望行、不把旧缺口断言为事实）；fallback 兜底缺口不
  视为已证实的具体风险，避免无谓降级真正的完整覆盖。

测试全部走真实 ``FactCorrectionJobService`` + ``FactCorrectionExecutor``（确定性，
无模型调用、无网络、无真实数据）；初始期望用同一共享推导从持久化记录生成，
与原始终结同源。
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from app.domain.contracts.enums import (
    ExpectationStatus,
    FactCallStatus,
    FactGate,
    FactNormalizationRunStatus,
    FactPolarity,
    GapType,
    GateOutcome,
    ReviewStage,
    SourceStrength,
)
from app.domain.contracts.evidence_expectations_v2 import CoverageGapSignal
from app.domain.contracts.evidence_normalizer import (
    EvidenceNormalizerUnresolvedItem,
    PersistedEvidenceNormalizerUnresolvedItem,
)
from app.domain.contracts.facts import (
    AssertionBasis,
    ClinicalFactCandidateV2,
    FactGateResult,
    FactNormalizationCall,
    FactNormalizationRun,
    fact_run_idempotency_key,
)
from app.services.evidence_expectation_projection_service import (
    EvidenceExpectationProjectionService,
)
from app.services.fact_correction_executor import (
    FactCorrectionExecutorConfig,
    create_fact_correction_executor,
)
from app.services.fact_correction_job_service import (
    FACT_CORRECTION_JOB_TYPE,
    FactCorrectionJobService,
)
from app.services.fact_expectation_gaps import (
    ReprojectionLineageError,
    corrections_by_new_entity,
    expectation_gap_signals,
    trace_correction_lineage,
)
from app.services.patient_profile_service import PatientProfileService
from app.storage.codecs import utc_now
from app.storage.evidence_expectation_repository import EvidenceExpectationV2Repository
from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord
from app.storage.fact_correction_repository import FactCorrectionRepository
from app.storage.fact_repositories import (
    ClinicalFactV2Repository,
    FactNormalizationCallRepository,
    FactNormalizationCandidateRepository,
    FactNormalizationRunRepository,
    FactNormalizationUnresolvedItemRepository,
    FactGateResultRepository,
)
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner
from tests.v2.projections.test_evidence_expectations import _template
from tests.v2.storage.test_fact_correction_repository import (
    _correction_for_facts,
    _seed_valid_chain,
)
from tests.v2.storage.test_fact_repositories import _date_range, _fact
from tests.v2.storage.test_fact_rule_link_repository import (
    _publish_fact as _publish_typed_fact,
)

NOW = datetime(2026, 9, 10, 8, 0, 0, tzinfo=UTC)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _seed_chain_with_template(session, prefix: str, *, fact_type: str = "vital_sign"):
    """活动权威链 + 一条到期（screening）资料期望模板；返回 (chain, template)。"""
    chain = _seed_valid_chain(session, prefix)
    template = _template(
        session,
        chain,
        requirement_id=f"{prefix}-req",
        fact_type=fact_type,
        due_stage=ReviewStage.SCREENING,
    )
    return chain, template


def _publish_supporting_fact(session, chain, template, *, fact_id: str, value: str):
    """发布一条完整来源、显式支持模板资料要求的已发布事实。"""
    return _publish_typed_fact(
        session,
        chain,
        fact_id=fact_id,
        fact_type=template.fact_type,
        asserted_object="血压",
        value=value,
        supported_requirement_ids=[template.requirement_id],
    )


def _publish_supporting_fact_on_run(
    session,
    chain,
    template,
    *,
    fact_id: str,
    run_id: str,
    value: str,
    supported_requirement_ids: list[str] | None = None,
    authority=None,
    source_strength: SourceStrength = SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
    candidate_source_semantics: str = "objective_result",
):
    """在指定规范化运行上发布支持模板要求的事实（跨运行谱系测试用）。"""
    if supported_requirement_ids is None:
        supported_requirement_ids = [template.requirement_id]
    call_id = (
        chain["call_id"] if run_id == chain["run_id"] else f"{run_id}-call"
    )
    candidate_id = f"{fact_id}-cand"
    gate_id = f"{fact_id}-gate"
    locator = session.get(EvidenceLocatorArtifactRecord, chain["locator_id"])
    basis = AssertionBasis(
        asserted_object="血压",
        assertion_text=locator.excerpt or "血压",
        locator_id=chain["locator_id"],
        source_text_sha256=locator.source_text_sha256,
    )
    FactNormalizationCandidateRepository(session).create(
        call_id,
        ClinicalFactCandidateV2(
            candidate_id=candidate_id,
            run_id=run_id,
            call_id=call_id,
            fact_type=template.fact_type,
            supported_requirement_ids=supported_requirement_ids,
            polarity=FactPolarity.AFFIRMED,
            asserted_object="血压",
            raw_value=value,
            canonical_value=value,
            unit="unitless",
            date_range=_date_range(),
            record_time=NOW,
            locator_ids=[chain["locator_id"]],
            candidate_source_semantics=candidate_source_semantics,
            assertion_basis=basis,
            model_uncertainty=0.01,
            created_at=NOW,
        ),
    )
    FactGateResultRepository(session).create(
        FactGateResult(
            gate_result_id=gate_id,
            run_id=run_id,
            call_id=call_id,
            candidate_id=candidate_id,
            gate=FactGate.TRANSACTIONAL_PUBLISH,
            outcome=GateOutcome.ACCEPTED,
            reasons=[],
            created_at=NOW,
        )
    )
    fact_overrides = {
        "fact_id": fact_id,
        "run_id": run_id,
        "gate_id": gate_id,
        "value": value,
        "record_time": NOW,
        "supported_requirement_ids": supported_requirement_ids,
        "assertion_basis": basis,
        "source_strength": source_strength,
    }
    if authority is not None:
        fact_overrides["authority"] = authority
    fact = _fact({**chain, "run_id": run_id, "gate_id": gate_id}, **fact_overrides)
    return ClinicalFactV2Repository(session).create(fact)


def _make_chain_metadata_unverifiable(session, chain) -> None:
    """把链上唯一资料的元数据来源方改写为无法确认（正式合同编码 + 哈希重算）。

    ``document_type`` 保持检验报告，但来源方不在研究者集合内，
    ``derive_source_strength_from_metadata`` 兜底派生
    ``SourceStrength.UNVERIFIABLE``（app/domain/gates/fact_evidence_closure.py）。
    在任何事实发布/投影消费之前执行，等价于种子阶段选择了不同元数据；
    完整修订闭包清单哈希按仓储算法重算并回写。
    """
    from app.domain.contracts.evidence_ingestion import SourceDocumentMetadataRevision
    from app.domain.contracts.evidence_locator import (
        CompleteEvidenceProcessingRevision,
    )
    from app.storage.codecs import decode_contract, encode_contract
    from app.storage.evidence_locator_repositories import (
        CompleteEvidenceProcessingRevisionRepository,
    )
    from app.storage.evidence_models import SourceDocumentMetadataRevisionRecord
    from app.storage.ocr_models import EvidenceProcessingRevisionRecord

    record = (
        session.query(SourceDocumentMetadataRevisionRecord)
        .filter(
            SourceDocumentMetadataRevisionRecord.source_document_version_id
            == chain["doc_id"]
        )
        .one()
    )
    contract = decode_contract(
        SourceDocumentMetadataRevision,
        record.payload_json,
        record.payload_sha256,
    )
    updated_metadata = contract.model_copy(update={"source_party": "其他机构"})
    record.payload_json, record.payload_sha256 = encode_contract(updated_metadata)
    record.source_party = updated_metadata.source_party
    session.flush()

    complete_row = session.get(
        EvidenceProcessingRevisionRecord, chain["complete_revision_id"]
    )
    complete = decode_contract(
        CompleteEvidenceProcessingRevision,
        complete_row.payload_json,
        complete_row.payload_sha256,
    )
    repository = CompleteEvidenceProcessingRevisionRepository(session)
    completion_manifest_sha256 = repository.manifest_sha256_for(complete)
    complete_row.payload_json, complete_row.payload_sha256 = encode_contract(
        complete.model_copy(update={"completion_manifest_sha256": completion_manifest_sha256})
    )
    complete_row.completion_manifest_sha256 = completion_manifest_sha256
    session.flush()
    session.expire_all()
    reread = repository.get(chain["complete_revision_id"])
    assert reread.metadata_revision_ids == complete.metadata_revision_ids


def _run_concrete_signals(session, chain):
    """按终结同源口径载入指定运行的事实候选与事务门禁结果。"""
    candidates = [
        candidate
        for candidate in FactNormalizationCandidateRepository(
            session
        ).list_by_run(chain["run_id"])
        if isinstance(candidate, ClinicalFactCandidateV2)
    ]
    gates = [
        result
        for result in FactGateResultRepository(session).list_by_run(chain["run_id"])
        if result.gate == FactGate.TRANSACTIONAL_PUBLISH
    ]
    return candidates, gates


def _persist_unresolved_item(
    session,
    chain,
    *,
    run_id: str,
    call_id: str,
    requirement_id: str,
    gap_type: GapType,
    reason: str,
    position: int = 0,
) -> PersistedEvidenceNormalizerUnresolvedItem:
    """在指定规范化运行上持久化逐页未解决项（与原始终结相同的结构化记录）。"""
    item = PersistedEvidenceNormalizerUnresolvedItem(
        unresolved_item_id=f"unresolved-{run_id}-{position}",
        run_id=run_id,
        call_id=call_id,
        logical_document_id=chain["logical_document_id"],
        position=position,
        item=EvidenceNormalizerUnresolvedItem(
            code="ocr_parse_risk",
            message="页面 OCR/解析存在风险",
            affected_pages=[1],
            affected_locator_ids=[],
            affected_requirement_ids=[requirement_id],
            gap_type=gap_type,
            reason=reason,
        ),
        created_at=NOW,
    )
    FactNormalizationUnresolvedItemRepository(session).create(item)
    return item


def _create_run_with_call(session, chain, run_id: str) -> None:
    """按正式仓储在指定权威下创建规范化运行与单页调用（测试辅助）。"""
    FactNormalizationRunRepository(session).create_or_reuse(
        FactNormalizationRun(
            run_id=run_id,
            authority=chain["authority"],
            idempotency_key=fact_run_idempotency_key(
                authority=chain["authority"],
                prompt_version_id=chain["prompt_version_id"],
                model_config_id=chain["model_config_id"],
                input_scope_sha256=_sha(f"{run_id}-scope"),
            ),
            prompt_version_id=chain["prompt_version_id"],
            model_config_id=chain["model_config_id"],
            input_scope_sha256=_sha(f"{run_id}-scope"),
            status=FactNormalizationRunStatus.SUCCEEDED,
            created_at=NOW,
            created_by="tester",
        )
    )
    FactNormalizationCallRepository(session).create(
        FactNormalizationCall(
            call_id=f"{run_id}-call",
            run_id=run_id,
            logical_document_id=chain["logical_document_id"],
            page_numbers=[1],
            status=FactCallStatus.SUCCEEDED,
            input_sha256=_sha(f"{run_id}-input"),
            created_at=NOW,
        )
    )


def _project_initial_expectations(session, chain, *, gap_signals=None):
    """按原始终结同源推导生成初始期望（revision 1）。

    ``gap_signals=None`` 时从源运行的持久化未解决项推导；显式传入仅用于
    「先前期望的源记录已不可追溯」场景（见保守保留测试）。
    """
    if gap_signals is None:
        items = FactNormalizationUnresolvedItemRepository(session).list_by_run(
            chain["run_id"]
        )
        gap_signals = expectation_gap_signals(session, chain["authority"], items)
    return EvidenceExpectationProjectionService().project(
        session,
        authority=chain["authority"],
        gap_signals=gap_signals,
        created_at=NOW,
        run_id=chain["run_id"],
    )


def _submit_and_run(session_factory, chain, fact_id, *, updates: dict, reason: str):
    created = FactCorrectionJobService(session_factory, now=utc_now).create_or_reuse_job(
        authority=chain["authority"],
        target_kind="fact",
        target_id=fact_id,
        locator_ids=[chain["locator_id"]],
        reason=reason,
        operator_id="reviewer-1",
        updates=updates,
        created_by="reviewer-1",
        created_at=NOW,
    )
    runner = JobRunner(
        session_factory,
        {
            FACT_CORRECTION_JOB_TYPE: create_fact_correction_executor(
                FactCorrectionExecutorConfig(session_factory=session_factory)
            )
        },
        worker_id="w1",
        now=utc_now,
        poll_interval=0.01,
    )
    runner.run_once()
    return created


def _job_snapshot(session_factory, job_id):
    with session_factory() as session:
        return JobStore(session, now=utc_now).snapshot(job_id)


def _assert_completed(session_factory, job_id):
    snapshot = _job_snapshot(session_factory, job_id)
    assert snapshot.state == "completed", (
        snapshot.state,
        snapshot.error_code,
        [(step.step_id, step.state, step.error_code) for step in snapshot.steps],
    )
    return snapshot


def test_correction_keeps_source_risk_recorded_on_unresolved_item(session_factory):
    """缺陷 A 回归：源运行持久化未解决项记录的 OCR 风险不得因修订重投影丢失。"""
    with session_factory() as session, session.begin():
        chain, template = _seed_chain_with_template(session, "fcorr-gap-a")
        fact = _publish_supporting_fact(
            session,
            chain,
            template,
            fact_id=f"{chain['run_id']}-fact-ocr",
            value="120/80",
        )
        _persist_unresolved_item(
            session,
            chain,
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            requirement_id=template.requirement_id,
            gap_type=GapType.OCR_OR_PARSE_RISK,
            reason="原运行未解决项：第1页 OCR/解析存在风险，需人工校对",
        )
        initial = _project_initial_expectations(session, chain)
        assert len(initial) == 1
        assert initial[0].status == ExpectationStatus.OBSERVED_WEAK
        assert initial[0].gap_type == GapType.OCR_OR_PARSE_RISK
        PatientProfileService().generate(
            session, authority=chain["authority"], created_at=NOW, generated_at=NOW
        )
        fact_id = fact.fact_id
        template_id = template.template_id
        episode_id = chain["review_episode_id"]
        authority = chain["authority"]

    created = _submit_and_run(
        session_factory,
        chain,
        fact_id,
        updates={"value": "130/80"},
        reason="核对原文第1页，血压值录入错误",
    )
    _assert_completed(session_factory, created.job_id)

    with session_factory() as session:
        corrections = FactCorrectionRepository(session).list_by_authority(authority)
        assert len(corrections) == 1
        assert corrections[0].target_id == fact_id
        new_fact = ClinicalFactV2Repository(session).get(corrections[0].new_entity_id)
        assert new_fact.value == "130/80"
        expectation = EvidenceExpectationV2Repository(session).latest_by_template(
            episode_id, template_id
        )
        assert expectation.revision == 2
        assert expectation.status == ExpectationStatus.OBSERVED_WEAK, (
            f"源运行风险被重投影丢弃：status={expectation.status}, "
            f"gap_type={expectation.gap_type}"
        )
        assert expectation.gap_type == GapType.OCR_OR_PARSE_RISK
        # 先期具体输入被当前源记录精确复现：不得再产生保守填充。
        details = [signal.detail or "" for signal in expectation.input_gap_signals or []]
        assert not any("先前期望" in detail for detail in details), details
        reproduced = [
            signal
            for signal in expectation.input_gap_signals or []
            if signal.kind == GapType.OCR_OR_PARSE_RISK
            and "原运行未解决项" in (signal.detail or "")
        ]
        assert reproduced, details


def test_correction_uncovering_due_template_completes_with_concrete_gap(session_factory):
    """缺陷 B 回归：清空唯一覆盖事实的资料要求支持不得回滚整次修订。

    期望行为：修订成功提交；失去覆盖的到期模板得到与原始终结同源的
    fallback 兜底缺口（非研究者判断要求为 ``record_incomplete``），
    绝不以通用缺口回退，也绝不因缺信号而拒绝修订。
    """
    with session_factory() as session, session.begin():
        chain, template = _seed_chain_with_template(session, "fcorr-gap-b")
        fact = _publish_supporting_fact(
            session,
            chain,
            template,
            fact_id=f"{chain['run_id']}-fact-only",
            value="120/80",
        )
        initial = _project_initial_expectations(session, chain)
        assert len(initial) == 1
        assert initial[0].status == ExpectationStatus.OBSERVED
        old_profile = PatientProfileService().generate(
            session, authority=chain["authority"], created_at=NOW, generated_at=NOW
        )
        old_profile_id = old_profile.patient_profile_revision_id
        fact_id = fact.fact_id
        template_id = template.template_id
        episode_id = chain["review_episode_id"]
        authority = chain["authority"]

    created = _submit_and_run(
        session_factory,
        chain,
        fact_id,
        updates={"supported_requirement_ids": []},
        reason="核对原文后该数值不属于该资料要求，解除要求绑定",
    )
    _assert_completed(session_factory, created.job_id)

    with session_factory() as session:
        corrections = FactCorrectionRepository(session).list_by_authority(authority)
        assert len(corrections) == 1
        assert corrections[0].target_id == fact_id
        new_fact = ClinicalFactV2Repository(session).get(corrections[0].new_entity_id)
        assert new_fact.supported_requirement_ids == []
        expectation = EvidenceExpectationV2Repository(session).latest_by_template(
            episode_id, template_id
        )
        assert expectation.revision == 2
        assert expectation.status == ExpectationStatus.ABSENT
        assert expectation.gap_type in {
            GapType.RECORD_INCOMPLETE,
            GapType.OBSERVATION_UNVERIFIED,
        }
        latest_profile = PatientProfileService().latest(session, episode_id)
        assert latest_profile is not None
        assert latest_profile.patient_profile_revision_id != old_profile_id


def test_correction_lineage_reaches_original_run_across_two_corrections(session_factory):
    """多步修订谱系：第二次修订仍须追溯到首次修订之前的原始运行风险记录。"""
    with session_factory() as session, session.begin():
        chain, template = _seed_chain_with_template(session, "fcorr-lineage")
        fact = _publish_supporting_fact(
            session,
            chain,
            template,
            fact_id=f"{chain['run_id']}-fact-chain",
            value="120/80",
        )
        _persist_unresolved_item(
            session,
            chain,
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            requirement_id=template.requirement_id,
            gap_type=GapType.OCR_OR_PARSE_RISK,
            reason="原运行未解决项：第1页 OCR/解析存在风险，需人工校对",
        )
        initial = _project_initial_expectations(session, chain)
        assert initial[0].status == ExpectationStatus.OBSERVED_WEAK
        PatientProfileService().generate(
            session, authority=chain["authority"], created_at=NOW, generated_at=NOW
        )
        fact_id = fact.fact_id
        template_id = template.template_id
        episode_id = chain["review_episode_id"]
        authority = chain["authority"]

    first = _submit_and_run(
        session_factory,
        chain,
        fact_id,
        updates={"value": "130/80"},
        reason="第一次核对更正数值",
    )
    _assert_completed(session_factory, first.job_id)
    with session_factory() as session:
        second_target = FactCorrectionRepository(session).get(
            first.correction_id
        ).new_entity_id
    second = _submit_and_run(
        session_factory,
        chain,
        second_target,
        updates={"value": "140/90"},
        reason="第二次核对更正数值",
    )
    _assert_completed(session_factory, second.job_id)

    with session_factory() as session:
        assert len(FactCorrectionRepository(session).list_by_authority(authority)) == 2
        expectation = EvidenceExpectationV2Repository(session).latest_by_template(
            episode_id, template_id
        )
        assert expectation.revision == 3
        assert expectation.status == ExpectationStatus.OBSERVED_WEAK, (
            f"原始运行风险在多步修订后丢失：status={expectation.status}, "
            f"gap_type={expectation.gap_type}"
        )
        assert expectation.gap_type == GapType.OCR_OR_PARSE_RISK


def test_reprojection_ignores_unrelated_orphan_run(session_factory):
    """无任何活动实体或修订谱系引用的孤立历史运行不得参与重投影。

    说明：跨权威（审核节点 revision/活动指针不同）的运行与实体在写入时即被
    ``FactAuthorityValidator.validate`` 整体拒绝（app/storage/fact_authority.py
    校验快照作用域、活动指针与 episode_revision），因此「其他权威的运行」无法
    经正式仓储 API 构造；运行选择器仍保留逐实体/逐运行的权威相等防御
    （app/services/fact_expectation_gaps.select_reprojection_source_runs），
    属纵深防御，此处以可合法构造的孤立运行（同权威、无实体/谱系引用）验证
    「绝不收集全部历史运行」这一选择边界。
    """
    with session_factory() as session, session.begin():
        chain, template = _seed_chain_with_template(session, "fcorr-orphan")
        fact = _publish_supporting_fact(
            session,
            chain,
            template,
            fact_id=f"{chain['run_id']}-fact-clean",
            value="120/80",
        )
        initial = _project_initial_expectations(session, chain)
        assert initial[0].status == ExpectationStatus.OBSERVED
        orphan_run_id = f"{chain['run_id']}-orphan"
        _create_run_with_call(session, chain, orphan_run_id)
        _persist_unresolved_item(
            session,
            chain,
            run_id=orphan_run_id,
            call_id=f"{orphan_run_id}-call",
            requirement_id=template.requirement_id,
            gap_type=GapType.OCR_OR_PARSE_RISK,
            reason="孤立历史运行的未解决项，没有任何已发布实体引用",
        )
        PatientProfileService().generate(
            session, authority=chain["authority"], created_at=NOW, generated_at=NOW
        )
        fact_id = fact.fact_id
        template_id = template.template_id
        episode_id = chain["review_episode_id"]

    created = _submit_and_run(
        session_factory,
        chain,
        fact_id,
        updates={"value": "130/80"},
        reason="核对原文第1页，血压值录入错误",
    )
    _assert_completed(session_factory, created.job_id)

    with session_factory() as session:
        expectation = EvidenceExpectationV2Repository(session).latest_by_template(
            episode_id, template_id
        )
        assert expectation.revision == 2
        assert expectation.status == ExpectationStatus.OBSERVED, (
            f"孤立运行的未解决项泄漏进重投影：status={expectation.status}, "
            f"gap_type={expectation.gap_type}"
        )
        assert expectation.gap_type is None


def test_prior_risk_without_source_linkage_stays_weak_as_unreconfirmed(session_factory):
    """先期显式风险无法按源记录复核时：保守保留较弱覆盖，不升级也不重申旧缺口。"""
    with session_factory() as session, session.begin():
        chain, template = _seed_chain_with_template(session, "fcorr-pad")
        fact = _publish_supporting_fact(
            session,
            chain,
            template,
            fact_id=f"{chain['run_id']}-fact-pad",
            value="120/80",
        )
        # 初始期望带显式 OCR 风险，但源运行上没有任何可追溯的结构化记录：
        # 代表“先前期望的源运行关联已不可发现”的历史状态。
        initial = _project_initial_expectations(
            session,
            chain,
            gap_signals=[
                CoverageGapSignal(
                    kind=GapType.OCR_OR_PARSE_RISK,
                    detail="历史运行的风险记录，源关联已不可追溯",
                    applies_to_template_id=template.template_id,
                )
            ],
        )
        assert initial[0].status == ExpectationStatus.OBSERVED_WEAK
        assert initial[0].gap_type == GapType.OCR_OR_PARSE_RISK
        PatientProfileService().generate(
            session, authority=chain["authority"], created_at=NOW, generated_at=NOW
        )
        fact_id = fact.fact_id
        template_id = template.template_id
        episode_id = chain["review_episode_id"]

    created = _submit_and_run(
        session_factory,
        chain,
        fact_id,
        updates={"value": "130/80"},
        reason="核对原文第1页，血压值录入错误",
    )
    _assert_completed(session_factory, created.job_id)

    with session_factory() as session:
        expectation = EvidenceExpectationV2Repository(session).latest_by_template(
            episode_id, template_id
        )
        assert expectation.revision == 2
        assert expectation.status == ExpectationStatus.OBSERVED_WEAK, (
            f"无法复核的先期风险被静默清除：status={expectation.status}, "
            f"gap_type={expectation.gap_type}"
        )
        # 不重申旧缺口（仍是 ocr_or_parse_risk 才算把旧缺口当事实），
        # 也不升级为 observed（那等于无证据清除风险）。
        assert expectation.gap_type == GapType.OBSERVATION_UNVERIFIED
        assert expectation.source_coverage == "complete"
        assert expectation.provenance_reason
        # 保守信号作为具体（非 fallback）输入被冻结在新期望上，
        # 因而在下一次修订中继续按「无法复核的具体输入」保留。
        pad_inputs = [
            signal
            for signal in expectation.input_gap_signals or []
            if not signal.fallback_only
        ]
        assert pad_inputs, expectation.input_gap_signals
        assert all(
            signal.kind == GapType.OBSERVATION_UNVERIFIED for signal in pad_inputs
        )


def test_correction_of_unrelated_fact_keeps_other_chain_source_risk(session_factory):
    """跨修订链谱系：修正无关事实时，其他活动实体原始运行的风险不得蒸发。

    X 与 Y 各自来自独立规范化运行；X 的原始运行携带具体 OCR 未解决项。
    修正 X（风险保留），随后修正无关的 Y：重投影必须沿 X 新实体的修订
    谱系回溯到 X 的原始运行，使 T 的期望仍为具体 ``ocr_or_parse_risk``，
    而不是降级成通用 ``observation_unverified`` 兜底。
    """
    with session_factory() as session, session.begin():
        chain, template = _seed_chain_with_template(session, "fcorr-cross")
        fact_x = _publish_supporting_fact(
            session,
            chain,
            template,
            fact_id=f"{chain['run_id']}-fact-x",
            value="120/80",
        )
        y_run_id = f"{chain['run_id']}-y"
        _create_run_with_call(session, chain, y_run_id)
        fact_y = _publish_supporting_fact_on_run(
            session,
            chain,
            template,
            fact_id=f"{chain['run_id']}-fact-y",
            run_id=y_run_id,
            value="130/85",
        )
        _persist_unresolved_item(
            session,
            chain,
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            requirement_id=template.requirement_id,
            gap_type=GapType.OCR_OR_PARSE_RISK,
            reason="X 原始运行未解决项：第1页 OCR/解析存在风险",
        )
        initial = _project_initial_expectations(session, chain)
        assert initial[0].status == ExpectationStatus.OBSERVED_WEAK
        assert initial[0].gap_type == GapType.OCR_OR_PARSE_RISK
        PatientProfileService().generate(
            session, authority=chain["authority"], created_at=NOW, generated_at=NOW
        )
        x_id, y_id = fact_x.fact_id, fact_y.fact_id
        template_id = template.template_id
        episode_id = chain["review_episode_id"]

    first = _submit_and_run(
        session_factory,
        chain,
        x_id,
        updates={"value": "125/85"},
        reason="第一次核对：更正 X 数值",
    )
    _assert_completed(session_factory, first.job_id)
    second = _submit_and_run(
        session_factory,
        chain,
        y_id,
        updates={"value": "131/86"},
        reason="第二次核对：更正无关的 Y 数值",
    )
    _assert_completed(session_factory, second.job_id)

    with session_factory() as session:
        expectation = EvidenceExpectationV2Repository(session).latest_by_template(
            episode_id, template_id
        )
        assert expectation.revision == 3
        assert expectation.status == ExpectationStatus.OBSERVED_WEAK, (
            f"无关修订后 X 原始运行风险丢失：status={expectation.status}, "
            f"gap_type={expectation.gap_type}"
        )
        assert expectation.gap_type == GapType.OCR_OR_PARSE_RISK, (
            "风险退化为通用 observation_unverified 即说明跨链谱系未被追溯"
        )


def test_rejected_candidate_risk_survives_accepted_binding_removal(session_factory):
    """被拒候选的压制只看当前未被取代事实的要求绑定，不看历史接受记录。

    同一要求上一条候选被接受、另一条被拒绝：终结时接受记录压制被拒风险
    （observed）。人工修订解除接受事实的要求绑定后，被拒来源的具体
    ``ocr_or_parse_risk`` 必须重新出现（absent + 具体缺口），而不是退化为
    通用的「尚无已核实记录」兜底。
    """
    with session_factory() as session, session.begin():
        chain, template = _seed_chain_with_template(session, "fcorr-rej")
        accepted_fact = _publish_supporting_fact(
            session,
            chain,
            template,
            fact_id=f"{chain['run_id']}-fact-acc",
            value="120/80",
        )
        rejected_candidate_id = f"{chain['run_id']}-rej-cand"
        rejected_locator = session.get(
            EvidenceLocatorArtifactRecord, chain["locator_id"]
        )
        rejected_basis = AssertionBasis(
            asserted_object="血压",
            assertion_text=rejected_locator.excerpt or "血压",
            locator_id=chain["locator_id"],
            source_text_sha256=rejected_locator.source_text_sha256,
        )
        FactNormalizationCandidateRepository(session).create(
            chain["call_id"],
            ClinicalFactCandidateV2(
                candidate_id=rejected_candidate_id,
                run_id=chain["run_id"],
                call_id=chain["call_id"],
                fact_type=template.fact_type,
                supported_requirement_ids=[template.requirement_id],
                polarity=FactPolarity.AFFIRMED,
                asserted_object="血压",
                raw_value="999/70",
                canonical_value="999/70",
                unit="mmHg",
                date_range=_date_range(),
                record_time=NOW,
                locator_ids=[chain["locator_id"]],
                candidate_source_semantics="objective_result",
                assertion_basis=rejected_basis,
                model_uncertainty=0.5,
                created_at=NOW,
            ),
        )
        FactGateResultRepository(session).create(
            FactGateResult(
                gate_result_id=f"{chain['run_id']}-rej-gate",
                run_id=chain["run_id"],
                call_id=chain["call_id"],
                candidate_id=rejected_candidate_id,
                gate=FactGate.TRANSACTIONAL_PUBLISH,
                outcome=GateOutcome.REJECTED,
                reasons=["非数值事实不应携带单位"],
                created_at=NOW,
            )
        )
        candidates, gates = _run_concrete_signals(session, chain)
        signals = expectation_gap_signals(
            session, chain["authority"], [], fact_candidates=candidates, gate_results=gates
        )
        assert all(signal.fallback_only for signal in signals), (
            "终结语义下接受记录应压制被拒候选风险"
        )
        initial = EvidenceExpectationProjectionService().project(
            session,
            authority=chain["authority"],
            gap_signals=signals,
            created_at=NOW,
            run_id=chain["run_id"],
        )
        assert initial[0].status == ExpectationStatus.OBSERVED
        PatientProfileService().generate(
            session, authority=chain["authority"], created_at=NOW, generated_at=NOW
        )
        accepted_id = accepted_fact.fact_id
        template_id = template.template_id
        episode_id = chain["review_episode_id"]

    created = _submit_and_run(
        session_factory,
        chain,
        accepted_id,
        updates={"supported_requirement_ids": []},
        reason="核对原文后该数值不属于该资料要求，解除接受事实的要求绑定",
    )
    _assert_completed(session_factory, created.job_id)

    with session_factory() as session:
        expectation = EvidenceExpectationV2Repository(session).latest_by_template(
            episode_id, template_id
        )
        assert expectation.revision == 2
        assert expectation.status == ExpectationStatus.ABSENT
        assert expectation.gap_type == GapType.OCR_OR_PARSE_RISK, (
            f"被拒来源风险退化为通用兜底：gap_type={expectation.gap_type}, "
            f"detail={expectation.gap_detail}"
        )
        assert expectation.gap_detail is not None
        assert "尚未通过事实完整性核对" in expectation.gap_detail
        assert "非数值事实不应携带单位" in expectation.gap_detail


def test_concrete_absent_becoming_complete_stays_unverified(session_factory):
    """具体缺口缺席 → 覆盖补齐：无显式处置时保持未核实，不得升级为 observed。"""
    with session_factory() as session, session.begin():
        chain, template = _seed_chain_with_template(session, "fcorr-abs2wk")
        fact = _publish_typed_fact(
            session,
            chain,
            fact_id=f"{chain['run_id']}-fact-late",
            fact_type=template.fact_type,
            asserted_object="血压",
            value="120/80",
            supported_requirement_ids=[],
        )
        initial = _project_initial_expectations(
            session,
            chain,
            gap_signals=[
                CoverageGapSignal(
                    kind=GapType.REQUIRED_PROCEDURE_NOT_DONE,
                    detail="心电图检查未执行",
                    applies_to_template_id=template.template_id,
                )
            ],
        )
        assert initial[0].status == ExpectationStatus.ABSENT
        assert initial[0].gap_type == GapType.REQUIRED_PROCEDURE_NOT_DONE
        PatientProfileService().generate(
            session, authority=chain["authority"], created_at=NOW, generated_at=NOW
        )
        fact_id = fact.fact_id
        template_id = template.template_id
        episode_id = chain["review_episode_id"]

    created = _submit_and_run(
        session_factory,
        chain,
        fact_id,
        updates={"supported_requirement_ids": [template.requirement_id]},
        reason="人工核对后确认该事实支持该资料要求",
    )
    _assert_completed(session_factory, created.job_id)

    with session_factory() as session:
        expectation = EvidenceExpectationV2Repository(session).latest_by_template(
            episode_id, template_id
        )
        assert expectation.revision == 2
        assert expectation.status == ExpectationStatus.OBSERVED_WEAK, (
            f"具体历史缺口被无证据升级为完整覆盖：status={expectation.status}"
        )
        assert expectation.gap_type == GapType.OBSERVATION_UNVERIFIED


def test_fallback_only_absence_clears_when_complete_evidence_arrives(session_factory):
    """明确为兜底的缺席（输入含 fallback_only）在完整证据到达时允许解除。"""
    with session_factory() as session, session.begin():
        chain, template = _seed_chain_with_template(session, "fcorr-fbclear")
        fact = _publish_typed_fact(
            session,
            chain,
            fact_id=f"{chain['run_id']}-fact-late-fb",
            fact_type=template.fact_type,
            asserted_object="血压",
            value="120/80",
            supported_requirement_ids=[],
        )
        # 无任何具体信号时，终结同源推导只产生 fallback_only 兜底 → 缺席。
        initial = _project_initial_expectations(session, chain)
        assert initial[0].status == ExpectationStatus.ABSENT
        assert initial[0].gap_type == GapType.RECORD_INCOMPLETE
        prior_inputs = initial[0].input_gap_signals
        assert prior_inputs is not None
        assert all(signal.fallback_only for signal in prior_inputs)
        PatientProfileService().generate(
            session, authority=chain["authority"], created_at=NOW, generated_at=NOW
        )
        fact_id = fact.fact_id
        template_id = template.template_id
        episode_id = chain["review_episode_id"]

    created = _submit_and_run(
        session_factory,
        chain,
        fact_id,
        updates={"supported_requirement_ids": [template.requirement_id]},
        reason="人工核对后确认该事实支持该资料要求",
    )
    _assert_completed(session_factory, created.job_id)

    with session_factory() as session:
        expectation = EvidenceExpectationV2Repository(session).latest_by_template(
            episode_id, template_id
        )
        assert expectation.revision == 2
        assert expectation.status == ExpectationStatus.OBSERVED, (
            f"明确兜底缺口未被完整证据解除：status={expectation.status}, "
            f"gap_type={expectation.gap_type}"
        )
        assert expectation.gap_type is None


def test_prior_pad_survives_unrelated_new_concrete_signal(session_factory):
    """无关新具体信号（不同 kind）与完整覆盖并存时，先期未复核不确定性不得被抹除。"""
    with session_factory() as session, session.begin():
        chain, template = _seed_chain_with_template(session, "fcorr-padnew")
        fact = _publish_supporting_fact(
            session,
            chain,
            template,
            fact_id=f"{chain['run_id']}-fact-pn",
            value="120/80",
        )
        prior_signal = CoverageGapSignal(
            kind=GapType.OBSERVATION_UNVERIFIED,
            detail="此前人工核对尚未确认记录存在",
            applies_to_template_id=template.template_id,
        )
        initial = _project_initial_expectations(
            session, chain, gap_signals=[prior_signal]
        )
        assert initial[0].status == ExpectationStatus.OBSERVED_WEAK
        assert initial[0].gap_type == GapType.OBSERVATION_UNVERIFIED
        # 初始投影之后再出现一条无关的具体未解决项（不同 kind）。
        _persist_unresolved_item(
            session,
            chain,
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            requirement_id=template.requirement_id,
            gap_type=GapType.DESCRIPTION_INSUFFICIENT,
            reason="描述不完整：记录缺少关键上下文",
            position=1,
        )
        PatientProfileService().generate(
            session, authority=chain["authority"], created_at=NOW, generated_at=NOW
        )
        fact_id = fact.fact_id
        template_id = template.template_id
        episode_id = chain["review_episode_id"]

    created = _submit_and_run(
        session_factory,
        chain,
        fact_id,
        updates={"value": "130/80"},
        reason="核对原文第1页，血压值录入错误",
    )
    _assert_completed(session_factory, created.job_id)

    with session_factory() as session:
        expectation = EvidenceExpectationV2Repository(session).latest_by_template(
            episode_id, template_id
        )
        assert expectation.revision == 2
        assert expectation.status == ExpectationStatus.OBSERVED_WEAK, (
            f"先期未复核输入被无关新信号抹除：status={expectation.status}, "
            f"gap_type={expectation.gap_type}"
        )
        assert expectation.gap_type == GapType.OBSERVATION_UNVERIFIED
        pad_inputs = [
            signal
            for signal in expectation.input_gap_signals or []
            if "先前期望" in (signal.detail or "")
        ]
        assert pad_inputs, expectation.input_gap_signals


@pytest.mark.parametrize("legacy", [False, True])
def test_global_new_signal_does_not_clear_prior_uncertainty(session_factory, legacy):
    from app.services.fact_expectation_gaps import _prior_unreconfirmed_signals
    from app.storage.codecs import encode_value
    from app.storage.facts_models import EvidenceExpectationV2Record

    with session_factory() as session, session.begin():
        chain, template = _seed_chain_with_template(session, f"fcorr-global-{legacy}")
        _publish_supporting_fact(
            session, chain, template, fact_id=f"{chain['run_id']}-fact", value="120/80",
        )
        initial = _project_initial_expectations(session, chain, gap_signals=[
            CoverageGapSignal(
                kind=GapType.OBSERVATION_UNVERIFIED,
                detail="原记录尚待核实", applies_to_template_id=template.template_id,
            ),
        ])[0]
        if legacy:
            row = session.get(EvidenceExpectationV2Record, initial.expectation_id)
            payload = initial.model_dump(mode="json")
            payload.pop("input_gap_signals")
            row.payload_json, row.payload_sha256 = encode_value(payload)
            session.flush()
            session.expire_all()
        pads = _prior_unreconfirmed_signals(
            session, authority=chain["authority"], concrete_signals=[
                CoverageGapSignal(kind=GapType.DESCRIPTION_INSUFFICIENT,
                                  detail="另一项描述需补充"),
            ],
        )
        assert len(pads) == 1
        assert pads[0].kind == GapType.OBSERVATION_UNVERIFIED
        assert pads[0].applies_to_template_id == template.template_id
        assert not pads[0].fallback_only
        assert initial.expectation_id in pads[0].detail


def test_same_kind_different_detail_prior_input_not_erased(session_factory):
    """同 kind 不同 detail 是两条独立关注：一条新信号不得视为先期输入的复现。

    模型未解决项合同不允许 ``observation_unverified``（投影层兜底概念），
    故两侧均使用真实可持久化的 ``ocr_or_parse_risk``：先期注入 detail=A，
    源运行后补 item detail=B。当前信号只复现 B，先期 A 仍须以关联填充保留。
    """
    with session_factory() as session, session.begin():
        chain, template = _seed_chain_with_template(session, "fcorr-samekind")
        fact = _publish_supporting_fact(
            session,
            chain,
            template,
            fact_id=f"{chain['run_id']}-fact-sk",
            value="120/80",
        )
        _project_initial_expectations(
            session,
            chain,
            gap_signals=[
                CoverageGapSignal(
                    kind=GapType.OCR_OR_PARSE_RISK,
                    detail="页面解析风险（先期人工标注 A）",
                    applies_to_template_id=template.template_id,
                )
            ],
        )
        _persist_unresolved_item(
            session,
            chain,
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            requirement_id=template.requirement_id,
            gap_type=GapType.OCR_OR_PARSE_RISK,
            reason="页面解析风险（本轮模型标注 B）",
            position=1,
        )
        PatientProfileService().generate(
            session, authority=chain["authority"], created_at=NOW, generated_at=NOW
        )
        fact_id = fact.fact_id
        template_id = template.template_id
        episode_id = chain["review_episode_id"]
        prior_id = EvidenceExpectationV2Repository(session).latest_by_template(
            episode_id, template_id
        ).expectation_id

    created = _submit_and_run(
        session_factory,
        chain,
        fact_id,
        updates={"value": "130/80"},
        reason="核对原文第1页，血压值录入错误",
    )
    _assert_completed(session_factory, created.job_id)

    with session_factory() as session:
        expectation = EvidenceExpectationV2Repository(session).latest_by_template(
            episode_id, template_id
        )
        assert expectation.revision == 2
        assert expectation.status == ExpectationStatus.OBSERVED_WEAK
        assert expectation.gap_type == GapType.OCR_OR_PARSE_RISK
        details = [signal.detail or "" for signal in expectation.input_gap_signals or []]
        assert any("先前期望" in detail and prior_id in detail for detail in details), (
            f"先期输入未被精确覆盖却未保留关联填充：{details}"
        )
        assert any("本轮模型标注 B" in detail for detail in details)
        assert not any("先期人工标注 A" in detail for detail in details)


def test_unverifiable_current_fact_cannot_erase_rejected_source_risk(session_factory):
    """SourceStrength.UNVERIFIABLE 的当前事实不构成已接受覆盖。

    覆盖判定契约将 UNVERIFIABLE 事实判为 none（无覆盖）；其支持的资料要求
    因此不得进入「当前已接受资料要求」去压制被拒候选的具体风险信号。
    """
    with session_factory() as session, session.begin():
        chain, template = _seed_chain_with_template(session, "fcorr-unv")
        _make_chain_metadata_unverifiable(session, chain)
        unverified_fact = _publish_supporting_fact_on_run(
            session,
            chain,
            template,
            fact_id=f"{chain['run_id']}-fact-unv",
            run_id=chain["run_id"],
            value="77",
            source_strength=SourceStrength.UNVERIFIABLE,
            candidate_source_semantics="unverifiable_source",
        )
        assert unverified_fact.source_strength == SourceStrength.UNVERIFIABLE
        rejected_candidate_id = f"{chain['run_id']}-unv-rej-cand"
        rejected_locator = session.get(
            EvidenceLocatorArtifactRecord, chain["locator_id"]
        )
        rejected_basis = AssertionBasis(
            asserted_object="血压",
            assertion_text=rejected_locator.excerpt or "血压",
            locator_id=chain["locator_id"],
            source_text_sha256=rejected_locator.source_text_sha256,
        )
        FactNormalizationCandidateRepository(session).create(
            chain["call_id"],
            ClinicalFactCandidateV2(
                candidate_id=rejected_candidate_id,
                run_id=chain["run_id"],
                call_id=chain["call_id"],
                fact_type=template.fact_type,
                supported_requirement_ids=[template.requirement_id],
                polarity=FactPolarity.AFFIRMED,
                asserted_object="血压",
                raw_value="888/60",
                canonical_value="888/60",
                unit="mmHg",
                date_range=_date_range(),
                record_time=NOW,
                locator_ids=[chain["locator_id"]],
                candidate_source_semantics="objective_result",
                assertion_basis=rejected_basis,
                model_uncertainty=0.5,
                created_at=NOW,
            ),
        )
        FactGateResultRepository(session).create(
            FactGateResult(
                gate_result_id=f"{chain['run_id']}-unv-rej-gate",
                run_id=chain["run_id"],
                call_id=chain["call_id"],
                candidate_id=rejected_candidate_id,
                gate=FactGate.TRANSACTIONAL_PUBLISH,
                outcome=GateOutcome.REJECTED,
                reasons=["记录字段与原文不符"],
                created_at=NOW,
            )
        )
        # 终结语义（None 覆盖）下，接受门禁仍压制被拒风险：缺席且为兜底缺口。
        candidates, gates = _run_concrete_signals(session, chain)
        signals = expectation_gap_signals(
            session, chain["authority"], [], fact_candidates=candidates, gate_results=gates
        )
        assert all(signal.fallback_only for signal in signals)
        initial = EvidenceExpectationProjectionService().project(
            session,
            authority=chain["authority"],
            gap_signals=signals,
            created_at=NOW,
            run_id=chain["run_id"],
        )
        assert initial[0].status == ExpectationStatus.ABSENT
        assert initial[0].gap_type == GapType.RECORD_INCOMPLETE
        PatientProfileService().generate(
            session, authority=chain["authority"], created_at=NOW, generated_at=NOW
        )
        unverified_id = unverified_fact.fact_id
        template_id = template.template_id
        episode_id = chain["review_episode_id"]

    # 事实类型更正改变替换签名，确保局部范围确实重投影该模板；
    # 若实现错误地用 UNVERIFIABLE 事实的要求压制被拒信号，重投影结果与 r1
    # 完全相同而幂等复用 revision 1，测试即失败。
    created = _submit_and_run(
        session_factory,
        chain,
        unverified_id,
        updates={"fact_type": "unmapped_type"},
        reason="核对原文后更正无法确认来源记录的事实类型",
    )
    _assert_completed(session_factory, created.job_id)

    with session_factory() as session:
        expectation = EvidenceExpectationV2Repository(session).latest_by_template(
            episode_id, template_id
        )
        assert expectation.revision == 2
        assert expectation.status == ExpectationStatus.ABSENT
        assert expectation.gap_type == GapType.OCR_OR_PARSE_RISK, (
            f"UNVERIFIABLE 事实压制了被拒来源风险：gap_type={expectation.gap_type}, "
            f"detail={expectation.gap_detail}"
        )
        assert expectation.gap_detail is not None
        assert "尚未通过事实完整性核对" in expectation.gap_detail


def test_prior_pad_ignores_expectation_from_other_authority(session_factory):
    """先期填充判定只看同一权威元组下的最新期望；旧权威期望不参与。"""
    from app.storage.models import ReviewEpisodeRecord

    from tests.v2.storage.test_fact_repositories import _update_episode

    with session_factory() as session, session.begin():
        chain, template = _seed_chain_with_template(session, "fcorr-authpad")
        fact = _publish_supporting_fact(
            session,
            chain,
            template,
            fact_id=f"{chain['run_id']}-fact-old",
            value="120/80",
        )
        _project_initial_expectations(
            session,
            chain,
            gap_signals=[
                CoverageGapSignal(
                    kind=GapType.OBSERVATION_UNVERIFIED,
                    detail="旧权威下的未核实标注",
                    applies_to_template_id=template.template_id,
                )
            ],
        )
        prior = EvidenceExpectationV2Repository(session).latest_by_template(
            chain["review_episode_id"], template.template_id
        )
        assert prior.status == ExpectationStatus.OBSERVED_WEAK
        PatientProfileService().generate(
            session, authority=chain["authority"], created_at=NOW, generated_at=NOW
        )
        # 审核节点 revision 前进：活动证据指针不变，权威元组 episode_revision 变为 2。
        _update_episode(
            session,
            session.get(ReviewEpisodeRecord, chain["review_episode_id"]),
            revision=2,
        )
        authority2 = chain["authority"].model_copy(
            update={"episode_revision": chain["authority"].episode_revision + 1}
        )
        new_chain = {**chain, "authority": authority2}
        new_run = f"{chain['run_id']}-a2"
        _create_run_with_call(session, new_chain, new_run)
        _publish_supporting_fact_on_run(
            session,
            new_chain,
            template,
            fact_id=f"{chain['run_id']}-fact-new",
            run_id=new_run,
            value="130/85",
            authority=authority2,
        )
        template_id = template.template_id
        episode_id = chain["review_episode_id"]

    created = _submit_and_run(
        session_factory,
        new_chain,
        f"{chain['run_id']}-fact-new",
        updates={"value": "131/86"},
        reason="新权威下核对更正数值",
    )
    _assert_completed(session_factory, created.job_id)

    with session_factory() as session:
        expectation = EvidenceExpectationV2Repository(session).latest_by_template(
            episode_id, template_id
        )
        assert expectation.revision == 2
        assert expectation.authority.episode_revision == 2
        assert expectation.status == ExpectationStatus.OBSERVED, (
            f"旧权威期望驱动了新权威的保守填充：status={expectation.status}, "
            f"gap_type={expectation.gap_type}"
        )
        assert expectation.gap_type is None


def _lineage_fact(suffix: str, value: str):
    ids = {
        "run_id": f"r-{suffix}",
        "gate_id": f"g-{suffix}",
        "project_id": "p",
        "subject_id": "s",
        "review_episode_id": "e",
        "protocol_version_id": "pr",
        "rule_set_id": "rs",
        "evidence_snapshot_v2_id": "snap",
        "complete_processing_revision_id": "comp",
        "locator_id": "loc",
    }
    return _fact(ids, fact_id=f"f-{suffix}", value=value, revision=1)


def test_resolver_rejects_cyclic_lineage():
    """修订入边成环时，运行选择器必须拒绝而不是无界回溯。"""
    a = _lineage_fact("a", "1")
    b = _lineage_fact("b", "2")
    c_ab = _correction_for_facts(a, b, ["loc"], correction_id="c1")
    c_ba = _correction_for_facts(b, a, ["loc"], correction_id="c2")
    by_new = {item.new_entity_id: item for item in (c_ab, c_ba)}
    with pytest.raises(ReprojectionLineageError, match="成环"):
        trace_correction_lineage(by_new, target_kind="fact", target_id=a.fact_id)


def test_resolver_rejects_converging_lineage():
    """同一新实体被多条修订指向（汇聚分支）时，谱系无法唯一追溯，必须拒绝。"""
    a = _lineage_fact("a", "1")
    b = _lineage_fact("b", "2")
    c = _lineage_fact("c", "3")
    c1 = _correction_for_facts(a, b, ["loc"], correction_id="c1")
    c2 = _correction_for_facts(c, b, ["loc"], correction_id="c2")
    with pytest.raises(ReprojectionLineageError, match="同时指向"):
        corrections_by_new_entity([c1, c2])
