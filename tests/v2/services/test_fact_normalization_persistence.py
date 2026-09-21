"""Phase 5 持久规范化任务的真实证据闭包、恢复与幂等测试。

覆盖：
- 同幂等键同内容复用 vs 同键异内容冲突
- 陈旧权威拒绝（活动指针变化后提交失败，保留上一状态）
- 空输出与部分输出拒绝（不生成空 Profile，保留上一活动版本）
- 迟到回包丢弃（租约 generation/过期校验，交由恢复器重放）
- 中断重启与租约回收（Checkpoint 幂等，已完成步骤不重复）
- 重复请求幂等（候选/调用已存在时不产生重复行）
- 检查点缺失恢复（成功调用已持久化时从持久记录重建检查点，零模型调用；
  身份不一致失效关闭）
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.agents.evidence_normalizer import (
    DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
    evidence_normalizer_prompt_template_sha256,
)
from app.domain.contracts.agents import ModelConfigContract, PromptVersion
from app.domain.contracts.evidence_normalizer import EvidenceNormalizerOutput, EvidenceNormalizerUnresolvedItem
from app.domain.contracts.facts import (
    AssertionBasis,
    ClinicalFactCandidateV2,
    FactAuthority,
    FactNormalizationCall,
    FactNormalizationRun,
    fact_run_idempotency_key,
)
from app.domain.contracts.enums import AgentNode, FactCallStatus, FactPolarity, LocatorSourceLayer, LocatorPrecision, LocatorAuthenticity, DisambiguationOutcome
from app.services.fact_normalization_executor import FactNormalizationExecutorConfig, create_fact_normalization_executor
from app.services.fact_normalization_job_service import (
    FactNormalizationCallSpec,
    FactNormalizationJobService,
    PARTIAL_OUTPUT_CODE,
    project_fact_normalization_run_status,
    recover_fact_normalization_runs,
)
from app.services.fact_normalization_source_adapter import (
    build_evidence_normalizer_input,
    build_fact_normalization_plan,
)
from app.domain.policies import STAGE_RANK
from app.storage.codecs import decode_contract, encode_contract
from app.storage.facts_models import (
    FactNormalizationCallRecord,
    FactNormalizationCandidateRecord,
    FactNormalizationRunRecord,
    FactNormalizationUnresolvedItemRecord,
)
from app.storage.fact_repositories import (
    FactNormalizationCallRepository,
    FactNormalizationRunRepository,
)
from app.storage.idempotency import IdempotencyConflict
from app.storage.models import JobRecord, JobStepRecord, ReviewEpisodeRecord
from app.storage.repositories import (
    MODEL_CONFIG_CONFIG,
    PROMPT_VERSION_CONFIG,
    AppendRepository,
)
from app.workflow.errors import StepFailure
from app.workflow.jobstore import JobStore
from app.workflow.recovery import recover_expired_jobs
from app.workflow.runner import JobRunner, StepContext

NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)
SOURCE_TEXT = "ALT 5.6 mmol/L 且 AST 3.5 mmol/L"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _bind_payload(record, contract):
    record.payload_json, record.payload_sha256 = encode_contract(contract)


def _update_episode(session, episode: ReviewEpisodeRecord, **changes):
    from app.domain.contracts.review import ReviewEpisode
    contract = decode_contract(ReviewEpisode, episode.payload_json, episode.payload_sha256).model_copy(update=changes)
    payload_json, payload_sha256 = encode_contract(contract)
    session.execute(update(ReviewEpisodeRecord).where(ReviewEpisodeRecord.review_episode_id == episode.review_episode_id).values(payload_json=payload_json, payload_sha256=payload_sha256, **changes))
    session.expire_all()


def _seed_chain(
    session,
    prefix: str,
    *,
    fixture_index: int = 0,
    include_metadata: bool = True,
    metadata_is_auto_suggestion: bool = False,
    mark_normalizer_model: bool = True,
) -> dict[str, str]:
    from app.domain.contracts.enums import (
        DisambiguationOutcome,
        EvidenceProcessingCandidateStatus,
        LocatorAuthenticity,
        LocatorPrecision,
        LocatorSourceLayer,
        PageArtifactStatus,
        SnapshotMemberOrigin,
        SnapshotStatus,
    )
    from app.domain.contracts.evidence_ingestion import (
        EvidenceSnapshot,
        EvidenceSnapshotMember,
        SourceDocumentMetadataRevision,
    )
    from app.domain.contracts.evidence_locator import (
        CompleteEvidenceProcessingRevision,
        EvidenceLocatorArtifact,
        EvidenceProcessingCandidate,
        EvidenceProcessingCandidateEvent,
        OCRRiskScan,
        ProcessingCandidateAttemptManifest,
        processing_candidate_input_hash,
    )
    from app.domain.contracts.evidence_processing import (
        EvidenceProcessingRevision,
        EvidenceProcessingRevisionPage,
    )
    from app.domain.publication import (
        canonical_hash,
        evidence_processing_manifest_hash,
        evidence_snapshot_collection_hash,
    )
    from app.storage.evidence_locator_repositories import (
        CompleteEvidenceProcessingRevisionRepository,
        EvidenceLocatorRepository,
        EvidenceProcessingCandidateRepository,
        OCRRiskScanRepository,
    )
    from app.storage.evidence_repositories import (
        BlobRepository,
        EvidenceSnapshotRepository,
        SourceDocumentMetadataRevisionRepository,
        SourceDocumentRepository,
    )
    from app.storage.ocr_repositories import (
        EvidenceProcessingRevisionRepository,
        OcrPageRepository,
        OCRProfileRepository,
        PageArtifactRepository,
    )
    from app.storage.repositories import (
        EpisodeRepository,
        SubjectRepository,
        persist_fixture,
    )
    from app.storage.models import ProjectRecord
    from tests.v2.storage.test_ocr_repositories import (
        make_artifact,
        make_blob,
        make_ocr_page,
        make_profile,
        make_version,
    )
    from tests.v2.storage.test_repositories_roundtrip import FIXTURES
    from tests.v2.storage.test_slice44_repositories import RAW_TEXT

    fixture = FIXTURES[fixture_index]
    raw_text = RAW_TEXT
    if session.get(ProjectRecord, fixture.project.project_id) is None:
        persist_fixture(session, fixture)
    else:
        SubjectRepository(session).save(fixture.subject)
        EpisodeRepository(session).save(fixture.review_episode)
    protocol_version_id = fixture.project.protocol_version.protocol_version_id
    rule_set_id = fixture.rule_set.rule_set_id
    rule_set_revision = fixture.rule_set.revision
    project_id = fixture.project.project_id
    subject_id = fixture.subject.subject_id
    episode_id = fixture.review_episode.review_episode_id
    snapshot_id = f"{prefix}-snapshot-v2"
    doc_id = f"{prefix}-doc"
    logical_document_id = f"{prefix}-log"
    page_artifact_id = f"{prefix}-pa"
    ocr_page_id = f"{prefix}-ocr-page"
    base_revision_id = f"{prefix}-base"
    complete_revision_id = f"{prefix}-complete"
    locator_id = f"{prefix}-locator"
    locator_id_2 = f"{prefix}-locator2"
    prompt_version_id = f"{prefix}-prompt"
    model_config_id = f"{prefix}-modelcfg"

    blob = make_blob(f"{prefix}-pdf".encode("utf-8"))
    BlobRepository(session).get_or_create_by_sha256(blob)
    SourceDocumentRepository(session).create_version(
        make_version(
            version_id=doc_id,
            logical_id=logical_document_id,
            blob_sha=blob.sha256,
            scope=(project_id, subject_id, episode_id),
            page_count=1,
        )
    )
    member = EvidenceSnapshotMember(
        member_id=f"{prefix}-member",
        snapshot_id=snapshot_id,
        logical_document_id=logical_document_id,
        source_document_version_id=doc_id,
        origin=SnapshotMemberOrigin.ADDED,
    )
    collection_sha256 = evidence_snapshot_collection_hash(
        members=[(logical_document_id, doc_id)]
    )
    EvidenceSnapshotRepository(session).create_full(
        EvidenceSnapshot(
            evidence_snapshot_id=snapshot_id,
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=episode_id,
            upload_mode="full",
            members=[member],
            collection_sha256=collection_sha256,
            status=SnapshotStatus.STAGED,
            created_at=NOW,
            created_by="tester",
        )
    )
    profile = OCRProfileRepository(session).get_or_create(
        make_profile(profile_id="facts-test-ocr-profile")
    )
    page_input_sha = _sha(f"{prefix}-page-input")
    page_source_sha = _sha(f"{prefix}-page-source")
    PageArtifactRepository(session).get_or_create(
        make_artifact(
            artifact_id=page_artifact_id,
            version_id=doc_id,
            page_input=page_input_sha,
            source_sha=page_source_sha,
        )
    )
    OcrPageRepository(session).create(
        make_ocr_page(
            page_id=ocr_page_id,
            artifact_id=page_artifact_id,
            profile_sha=profile.profile_sha256,
            page_input=page_input_sha,
            source_sha=page_source_sha,
            raw_text=raw_text,
        )
    )
    page_entry = EvidenceProcessingRevisionPage(
        entry_id=f"{prefix}-entry",
        position=1,
        source_document_version_id=doc_id,
        page_number=1,
        original_frame=None,
        page_artifact_id=page_artifact_id,
        ocr_page_id=ocr_page_id,
        status=PageArtifactStatus.SUCCEEDED,
    )
    manifest_sha = evidence_processing_manifest_hash(
        entries=[(doc_id, 1, None, page_artifact_id, ocr_page_id, "succeeded")]
    )
    EvidenceProcessingRevisionRepository(session).create(
        EvidenceProcessingRevision(
            evidence_processing_revision_id=base_revision_id,
            evidence_snapshot_id=snapshot_id,
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=episode_id,
            manifest=[page_entry],
            manifest_sha256=manifest_sha,
            created_at=NOW,
            created_by="tester",
        )
    )
    locator_repo = EvidenceLocatorRepository(session)
    source_hash = _sha(raw_text)
    for locator in (
        EvidenceLocatorArtifact(
            locator_id=locator_id,
            page_artifact_id=page_artifact_id,
            ocr_page_id=ocr_page_id,
            source_document_version_id=doc_id,
            page_number=1,
            source_layer=LocatorSourceLayer.RAW_OCR,
            source_text_sha256=source_hash,
            target_id=f"{prefix}-target-alt",
            precision=LocatorPrecision.TEXT_RANGE,
            text_start=0,
            text_end=5,
            excerpt="ALT 5",
            disambiguation=DisambiguationOutcome.UNIQUE_MATCH,
            locator_algorithm_version="v1",
            authenticity=LocatorAuthenticity.DEGRADED,
            degradation_reason="仅有文本范围",
            created_at=NOW,
        ),
        EvidenceLocatorArtifact(
            locator_id=locator_id_2,
            page_artifact_id=page_artifact_id,
            ocr_page_id=ocr_page_id,
            source_document_version_id=doc_id,
            page_number=1,
            source_layer=LocatorSourceLayer.RAW_OCR,
            source_text_sha256=source_hash,
            target_id=f"{prefix}-target-ast",
            precision=LocatorPrecision.TEXT_RANGE,
            text_start=17,
            text_end=22,
            excerpt="AST 3",
            disambiguation=DisambiguationOutcome.UNIQUE_MATCH,
            locator_algorithm_version="v1",
            authenticity=LocatorAuthenticity.DEGRADED,
            degradation_reason="仅有文本范围",
            created_at=NOW,
        ),
    ):
        locator_repo.create(locator)

    metadata_id = f"{prefix}-metadata"
    metadata_ids = [metadata_id] if include_metadata else []
    if include_metadata:
        SourceDocumentMetadataRevisionRepository(session).append(
            SourceDocumentMetadataRevision(
                metadata_revision_id=metadata_id,
                source_document_version_id=doc_id,
                document_type="检验报告",
                source_party="研究者所在机构",
                reason="测试资料类型已确认",
                is_auto_suggestion=metadata_is_auto_suggestion,
                revision=1,
                created_at=NOW,
                created_by="tester",
            )
        )
    scanner_rule_version = "facts-test/v1"
    scan_id = f"{prefix}-scan"
    OCRRiskScanRepository(session).get_or_create(
        OCRRiskScan(
            scan_id=scan_id,
            ocr_page_id=ocr_page_id,
            raw_text_sha256=source_hash,
            scanner_rule_version=scanner_rule_version,
            flags=[],
            flags_sha256=canonical_hash([]),
            coverage_status="complete",
            created_at=NOW,
        )
    )
    producer_id = f"{prefix}-processing-candidate"
    selected_locator_ids = sorted([locator_id, locator_id_2])
    attempt_manifest = ProcessingCandidateAttemptManifest(
        metadata_revision_ids=metadata_ids,
        risk_scan_ids=[scan_id],
        locator_ids=selected_locator_ids,
    )
    producer_input_sha = processing_candidate_input_hash(
        evidence_snapshot_id=snapshot_id,
        base_processing_revision_id=base_revision_id,
        expected_revision=fixture.review_episode.revision,
        scanner_rule_version=scanner_rule_version,
        selected_locator_ids=selected_locator_ids,
        attempt_manifest=attempt_manifest,
    )
    producer = EvidenceProcessingCandidate(
        candidate_id=producer_id,
        evidence_snapshot_id=snapshot_id,
        base_processing_revision_id=base_revision_id,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        expected_revision=fixture.review_episode.revision,
        idempotency_key=f"{prefix}-processing-key",
        scanner_rule_version=scanner_rule_version,
        selected_locator_ids=selected_locator_ids,
        attempt_manifest=attempt_manifest,
        candidate_input_sha256=producer_input_sha,
        status=EvidenceProcessingCandidateStatus.STAGED,
        created_by="tester",
        created_at=NOW,
    )
    EvidenceProcessingCandidateRepository(session).create(
        producer,
        EvidenceProcessingCandidateEvent(
            candidate_id=producer_id,
            seq=1,
            from_status="staged",
            to_status="processing",
            event_kind="worker_start",
            actor="tester",
            reason="构建测试完整处理修订",
            attempt_manifest=attempt_manifest,
            attempt_input_sha256=producer_input_sha,
            created_at=NOW,
        ),
    )
    complete_repo = CompleteEvidenceProcessingRevisionRepository(session)
    incomplete_hash = "0" * 64
    complete = CompleteEvidenceProcessingRevision(
        evidence_processing_revision_id=complete_revision_id,
        evidence_snapshot_id=snapshot_id,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        base_processing_revision_id=base_revision_id,
        producer_candidate_id=producer_id,
        candidate_input_sha256=producer_input_sha,
        manifest=[page_entry],
        manifest_sha256=manifest_sha,
        locator_ids=selected_locator_ids,
        risk_scan_ids=[scan_id],
        metadata_revision_ids=metadata_ids,
        completion_manifest_sha256=incomplete_hash,
        created_at=NOW,
        created_by="tester",
    )
    complete = complete.model_copy(
        update={"completion_manifest_sha256": complete_repo.manifest_sha256_for(complete)}
    )
    complete_repo.create(complete)

    episode = session.get(ReviewEpisodeRecord, episode_id)
    _update_episode(
        session,
        episode,
        active_evidence_snapshot_id=snapshot_id,
        active_evidence_processing_revision_id=complete_revision_id,
    )
    AppendRepository(session, PROMPT_VERSION_CONFIG).save(
        PromptVersion(
            prompt_version_id=prompt_version_id,
            node=AgentNode.EVIDENCE_NORMALIZER,
            template_sha256=evidence_normalizer_prompt_template_sha256(
                DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE
            ),
            schema_version_id="phase5/facts/v1",
        )
    )
    AppendRepository(session, MODEL_CONFIG_CONFIG).save(
        ModelConfigContract(
            model_config_id=model_config_id,
            provider="omlx",
            model="deterministic-test-transport",
            reasoning_effort="medium",
            parameters={
                "max_tokens": 4096,
                "temperature": 0.2,
                **(
                    {"agent_node": AgentNode.EVIDENCE_NORMALIZER.value}
                    if mark_normalizer_model
                    else {}
                ),
            },
        )
    )

    run_authority = FactAuthority(project_id=project_id, subject_id=subject_id, review_episode_id=episode_id, episode_revision=fixture.review_episode.revision, protocol_version_id=protocol_version_id, rule_set_id=rule_set_id, rule_set_revision=rule_set_revision, evidence_snapshot_v2_id=snapshot_id, complete_processing_revision_id=complete_revision_id)
    return {
        "project_id": project_id,
        "subject_id": subject_id,
        "episode_id": episode_id,
        "snapshot_id": snapshot_id,
        "doc_id": doc_id,
        "logical_document_id": logical_document_id,
        "page_artifact_id": page_artifact_id,
        "base_revision_id": base_revision_id,
        "complete_revision_id": complete_revision_id,
        "locator_id": locator_id,
        "locator_id_2": locator_id_2,
        "prompt_version_id": prompt_version_id,
        "model_config_id": model_config_id,
        "authority": run_authority,
        "protocol_version_id": protocol_version_id,
        "rule_set_id": rule_set_id,
    }


def _candidate_fact(run_id: str, call_id: str, locator_id: str, asserted_object="ALT") -> ClinicalFactCandidateV2:
    txt = "ALT 5" if asserted_object == "ALT" else "AST 3"
    return ClinicalFactCandidateV2(
        candidate_id=f"cand_{hashlib.sha256((run_id+call_id+locator_id).encode()).hexdigest()[:16]}",
        run_id=run_id,
        call_id=call_id,
        fact_type="lab_result",
        polarity=FactPolarity.AFFIRMED,
        asserted_object=asserted_object,
        canonical_value="异常",
        unit="unitless",
        locator_ids=[locator_id],
        candidate_source_semantics="同期客观结果",
        assertion_basis=AssertionBasis(locator_id=locator_id, asserted_object=asserted_object, assertion_text=txt, source_text_sha256=_sha(SOURCE_TEXT)),
        model_uncertainty=0.1,
        created_at=NOW,
    )


def _create_job_from_source(
    service: FactNormalizationJobService,
    chain: dict[str, object],
):
    return service.create_or_reuse_from_source(
        authority=chain["authority"],
        prompt_version_id=chain["prompt_version_id"],
        model_config_id=chain["model_config_id"],
        created_by="tester",
    )


# ---------------------------------------------------------------------------
# 测试：幂等与重复
# ---------------------------------------------------------------------------

def test_job_creation_rejects_document_without_confirmed_metadata(session_factory):
    from app.storage.evidence_locator_repositories import RevisionClosureError

    with session_factory() as session:
        with pytest.raises(RevisionClosureError, match="恰好绑定一条链头元数据修订"):
            _seed_chain(session, prefix="missing-meta", include_metadata=False)
        session.rollback()
    with session_factory() as session:
        assert session.execute(select(FactNormalizationRunRecord)).scalars().all() == []
        assert session.execute(select(FactNormalizationCallRecord)).scalars().all() == []

def test_create_or_reuse_job_idempotent_same_payload(session_factory):
    with session_factory() as session:
        chain = _seed_chain(session, prefix="idem1")
        session.commit()
    svc = FactNormalizationJobService(session_factory)
    first = _create_job_from_source(svc, chain)
    second = _create_job_from_source(svc, chain)
    assert first.job_id == second.job_id
    assert first.run_id == second.run_id
    assert first.created is True
    assert second.created is False
    # 检查未产生重复 Run
    with session_factory() as session:
        rows = session.execute(select(FactNormalizationRunRecord)).scalars().all()
        matching = [r for r in rows if r.idempotency_key == first.idempotency_key]
        assert len(matching) == 1


def test_source_plan_job_and_run_share_one_input_scope_hash(session_factory):
    with session_factory() as session:
        chain = _seed_chain(session, prefix="scope-identity")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    with session_factory() as session:
        plan, _ = build_fact_normalization_plan(
            session,
            authority=chain["authority"],
            revision_id=chain["complete_revision_id"],
        )

    created = _create_job_from_source(service, chain)
    job_payload = service.get_job(created.job_id)["payload"]
    with session_factory() as session:
        run = session.get(FactNormalizationRunRecord, created.run_id)
        assert run is not None
        assert run.input_scope_sha256 == plan.input_scope_sha256
    assert job_payload["input_scope_sha256"] == plan.input_scope_sha256


def test_non_default_page_group_size_is_frozen_and_forwarded(
    session_factory, monkeypatch
):
    import app.services.fact_normalization_executor as executor_module

    with session_factory() as session:
        chain = _seed_chain(session, prefix="page-group-size")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    created = service.create_or_reuse_from_source(
        authority=chain["authority"],
        prompt_version_id=chain["prompt_version_id"],
        model_config_id=chain["model_config_id"],
        created_by="tester",
        max_pages_per_call=1,
    )
    payload = service.get_job(created.job_id)["payload"]
    assert payload["max_pages_per_call"] == 1
    captured: list[int] = []
    original = executor_module.build_evidence_normalizer_input

    def capture(*args, **kwargs):
        captured.append(kwargs["max_pages_per_call"])
        return original(*args, **kwargs)

    monkeypatch.setattr(executor_module, "build_evidence_normalizer_input", capture)

    def transport(evidence_input):
        return EvidenceNormalizerOutput(
            run_id=evidence_input.run_id,
            call_id=evidence_input.call_id,
            logical_document_id=evidence_input.logical_document_id,
            page_numbers=evidence_input.page_numbers,
            fact_candidates=[
                _candidate_fact(
                    evidence_input.run_id,
                    evidence_input.call_id,
                    chain["locator_id"],
                )
            ],
        )

    executor = create_fact_normalization_executor(
        FactNormalizationExecutorConfig(
            session_factory=session_factory,
            transport_fn=transport,
        )
    )
    step_id = "normalize_000_" + chain["logical_document_id"]
    executor(
        StepContext(
            job_id=created.job_id,
            job_type="fact_normalization",
            job_payload=payload,
            step_id=step_id,
            name="证据规范化",
            attempt=1,
            last_checkpoint_id=None,
            last_checkpoint=None,
            max_attempts=3,
        )
    )
    assert captured == [1]


def test_executor_uses_persisted_job_step_as_transport_retry_boundary(
    session_factory,
):
    config = FactNormalizationExecutorConfig(session_factory=session_factory)

    assert config.max_transport_retries == 0


def test_auto_suggested_metadata_with_identifiable_type_is_accepted(session_factory):
    """R14修复：有据的自动建议（document_type可识别）不再构成隐藏人工门禁。"""
    with session_factory() as session:
        chain = _seed_chain(
            session,
            prefix="auto-meta",
            metadata_is_auto_suggestion=True,
        )
        session.commit()

    service = FactNormalizationJobService(session_factory)
    # document_type="检验报告"可识别，自动有据采用不阻断
    result = _create_job_from_source(service, chain)
    assert result.job_id  # job created successfully


def test_rebuilt_model_input_contains_frozen_document_stage_and_requirements(session_factory):
    with session_factory() as session:
        chain = _seed_chain(session, prefix="input-context")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)
    payload = service.get_job(created.job_id)["payload"]
    call = payload["calls"][0]
    with session_factory() as session:
        evidence_input = build_evidence_normalizer_input(
            session,
            authority=chain["authority"],
            run_id=created.run_id,
            call_id=call["call_id"],
            logical_document_id=call["logical_document_id"],
            page_numbers=call["page_numbers"],
            expected_input_sha256=call["input_sha256"],
            created_at=NOW,
        )
    assert evidence_input.context.document_type == "检验报告"
    assert evidence_input.context.source_party == "研究者所在机构"
    assert evidence_input.context.document_record_time is None
    assert all(
        STAGE_RANK[item.due_stage]
        <= STAGE_RANK[evidence_input.context.current_review_stage]
        for item in evidence_input.related_requirements
    )


def test_create_or_reuse_job_conflict_same_key_different_payload(session_factory):
    from app.services.fact_normalization_job_service import FactNormalizationCallSpec

    with session_factory() as session:
        chain = _seed_chain(session, prefix="idem2")
        session.commit()
    svc = FactNormalizationJobService(session_factory)
    first = _create_job_from_source(svc, chain)
    # 同一幂等键但不同 input_scope -> 预期冲突：计算输入范围哈希不同导致幂等键不同，实际不会冲突
    # 改为同幂等键不同调用内容：用同一 input_scope 但不同 page_numbers 仍导致相同幂等键？输入范围哈希由 calls 推导，若 page_numbers 不同则哈希不同，键不同
    # 因此构造显式 idempotency_key 冲突：传入相同 key 但不同 calls
    different_calls = [FactNormalizationCallSpec(logical_document_id=chain["logical_document_id"], page_numbers=[1], input_sha256=_sha("different"))]
    # 复用 first 的幂等键但提交不同内容
    with pytest.raises(Exception) as exc:
        svc.create_or_reuse_job(authority=chain["authority"], prompt_version_id=chain["prompt_version_id"], model_config_id=chain["model_config_id"], calls=different_calls, created_by="tester", idempotency_key=first.idempotency_key)
    assert "幂等键" in str(exc.value) or "idempotency" in str(exc.value).lower() or "不一致" in str(exc.value)


# ---------------------------------------------------------------------------
# 测试：陈旧权威拒绝
# ---------------------------------------------------------------------------

def test_executor_rejects_stale_authority_preserves_prior(session_factory):
    from app.services.fact_normalization_job_service import FactNormalizationCallSpec

    with session_factory() as session:
        chain = _seed_chain(session, prefix="stale1")
        session.commit()
    svc = FactNormalizationJobService(session_factory)
    result = _create_job_from_source(svc, chain)
    job_payload = svc.get_job(result.job_id)["payload"]
    call_id = job_payload["calls"][0]["call_id"]

    # 准备一个有效候选输出
    def transport_ok(evidence_input):
        # 构造一个有效候选
        cand = _candidate_fact(evidence_input.run_id, evidence_input.call_id, chain["locator_id"])
        return EvidenceNormalizerOutput(run_id=evidence_input.run_id, call_id=evidence_input.call_id, logical_document_id=evidence_input.logical_document_id, page_numbers=evidence_input.page_numbers, fact_candidates=[cand], event_candidates=[], exposure_candidates=[], unresolved_items=[])

    # 先让原始权威成功一次，检查候选数
    cfg_ok = FactNormalizationExecutorConfig(session_factory=session_factory, transport_fn=transport_ok)
    executor_ok = create_fact_normalization_executor(cfg_ok)
    # 使权威陈旧：递增审核节点 revision，模拟审核节点已推进而旧权威仍指向旧 revision
    with session_factory() as session:
        from app.storage.models import ReviewEpisodeRecord as _RER
        from app.domain.contracts.review import ReviewEpisode as _RE
        rec = session.get(_RER, chain["episode_id"])
        decoded = decode_contract(_RE, rec.payload_json, rec.payload_sha256)
        new_decoded = decoded.model_copy(update={"revision": decoded.revision + 1})
        pj, ps = encode_contract(new_decoded)
        session.execute(update(_RER).where(_RER.review_episode_id == chain["episode_id"]).values(payload_json=pj, payload_sha256=ps, revision=new_decoded.revision))
        session.commit()
    # 此时权威已陈旧，执行应失败
    cfg_stale = FactNormalizationExecutorConfig(session_factory=session_factory, transport_fn=transport_ok)
    executor_stale = create_fact_normalization_executor(cfg_stale)
    ctx = StepContext(job_id=result.job_id, job_type="fact_normalization", job_payload=job_payload, step_id="normalize_000_"+chain["logical_document_id"], name="test", attempt=1, last_checkpoint_id=None, last_checkpoint=None, max_attempts=3)
    with pytest.raises(StepFailure) as exc:
        executor_stale(ctx)
    assert exc.value.error_code == "STALE_AUTHORITY"
    # 检查未污染：调用表不应有新行（或至少不产生事实发布）
    with session_factory() as session:
        assert session.get(FactNormalizationCallRecord, call_id) is None
        # 无 ClinicalFactV2 产生
        from app.storage.facts_models import ClinicalFactV2Record
        facts = session.execute(select(ClinicalFactV2Record)).scalars().all()
        assert len(facts) == 0


# ---------------------------------------------------------------------------
# 测试：空输出与部分输出拒绝
# ---------------------------------------------------------------------------

def test_executor_rejects_empty_output(session_factory):
    with session_factory() as session:
        chain = _seed_chain(session, prefix="empty1")
        session.commit()
    svc = FactNormalizationJobService(session_factory)
    result = _create_job_from_source(svc, chain)
    job_payload = svc.get_job(result.job_id)["payload"]

    def transport_empty(evidence_input):
        return EvidenceNormalizerOutput(run_id=evidence_input.run_id, call_id=evidence_input.call_id, logical_document_id=evidence_input.logical_document_id, page_numbers=evidence_input.page_numbers, fact_candidates=[], event_candidates=[], exposure_candidates=[], unresolved_items=[])

    cfg = FactNormalizationExecutorConfig(session_factory=session_factory, transport_fn=transport_empty)
    executor = create_fact_normalization_executor(cfg)
    ctx = StepContext(job_id=result.job_id, job_type="fact_normalization", job_payload=job_payload, step_id="normalize_000_"+chain["logical_document_id"], name="test", attempt=1, last_checkpoint_id=None, last_checkpoint=None, max_attempts=3)
    with pytest.raises(StepFailure) as exc:
        executor(ctx)
    assert exc.value.error_code == "EMPTY_OUTPUT"


def test_job_creation_rejects_wrong_frozen_prompt_node_before_transport(session_factory):
    from app.storage.models import PromptVersionRecord

    with session_factory() as session:
        chain = _seed_chain(session, prefix="wrong-prompt-node")
        wrong_prompt = PromptVersion(
            prompt_version_id=chain["prompt_version_id"],
            node=AgentNode.PROTOCOL_DECONSTRUCTOR,
            template_sha256=evidence_normalizer_prompt_template_sha256(
                DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE
            ),
            schema_version_id="phase5/facts/v1",
        )
        payload_json, payload_sha256 = encode_contract(wrong_prompt)
        session.execute(
            update(PromptVersionRecord)
            .where(
                PromptVersionRecord.prompt_version_id
                == chain["prompt_version_id"]
            )
            .values(
                node=AgentNode.PROTOCOL_DECONSTRUCTOR.value,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
            )
        )
        session.commit()
    service = FactNormalizationJobService(session_factory)
    with pytest.raises(Exception, match="不属于证据规范化任务"):
        _create_job_from_source(service, chain)
    with session_factory() as session:
        assert session.execute(select(FactNormalizationRunRecord)).scalars().all() == []


def test_job_creation_rejects_tampered_model_config_before_transport(session_factory):
    from app.storage.models import ModelConfigRecord

    with session_factory() as session:
        chain = _seed_chain(session, prefix="tampered-model-config")
        session.execute(
            update(ModelConfigRecord)
            .where(ModelConfigRecord.model_config_id == chain["model_config_id"])
            .values(payload_json='{"tampered":true}')
        )
        session.commit()
    service = FactNormalizationJobService(session_factory)
    with pytest.raises(Exception, match="无法读取证据规范化配置"):
        _create_job_from_source(service, chain)
    with session_factory() as session:
        assert session.execute(select(FactNormalizationRunRecord)).scalars().all() == []


def test_executor_rechecks_frozen_model_role_before_transport(session_factory):
    from app.storage.models import ModelConfigRecord

    with session_factory() as session:
        chain = _seed_chain(session, prefix="wrong-model-role-after-create")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)
    payload = service.get_job(created.job_id)["payload"]

    wrong_model = ModelConfigContract(
        model_config_id=chain["model_config_id"],
        provider="omlx",
        model="deterministic-test-transport",
        reasoning_effort="medium",
        parameters={
            "max_tokens": 4096,
            "temperature": 0.2,
            "agent_node": AgentNode.PROTOCOL_DECONSTRUCTOR.value,
        },
    )
    payload_json, payload_sha256 = encode_contract(wrong_model)
    with session_factory() as session, session.begin():
        session.execute(
            update(ModelConfigRecord)
            .where(ModelConfigRecord.model_config_id == chain["model_config_id"])
            .values(payload_json=payload_json, payload_sha256=payload_sha256)
        )

    def must_not_call_transport(_evidence_input):
        raise AssertionError("职责错误的模型设置不得进入模型调用")

    executor = create_fact_normalization_executor(
        FactNormalizationExecutorConfig(
            session_factory=session_factory,
            transport_fn=must_not_call_transport,
        )
    )
    context = StepContext(
        job_id=created.job_id,
        job_type="fact_normalization",
        job_payload=payload,
        step_id=f"normalize_000_{chain['logical_document_id']}",
        name="test",
        attempt=1,
        last_checkpoint_id=None,
        last_checkpoint=None,
        max_attempts=3,
    )

    with pytest.raises(StepFailure) as exc:
        executor(context)

    assert exc.value.error_code == PARTIAL_OUTPUT_CODE
    assert "不属于个例档案整理任务" in exc.value.detail


def test_immediate_cancel_projects_run_terminal_status(session_factory):
    with session_factory() as session:
        chain = _seed_chain(session, prefix="cancel-run")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)

    outcome = service.cancel(created.job_id)

    assert outcome.state == "cancelled"
    with session_factory() as session:
        run = FactNormalizationRunRepository(session).get(created.run_id)
        assert run.status.value == "cancelled"


def test_cancelled_normalization_job_can_resume_without_repeating_completed_step(
    session_factory,
):
    from app.domain.contracts.enums import FactNormalizationRunStatus

    with session_factory() as session:
        chain = _seed_chain(session, prefix="cancelled-resume-run")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)

    with session_factory() as session, session.begin():
        store = JobStore(session)
        lease = store.claim_next("worker")
        assert lease is not None
        first_step = store.next_runnable_step(created.job_id)
        assert first_step is not None
        store.start_step(lease, first_step.step_id)
        store.complete_step(lease, first_step.step_id, checkpoint_payload={"facts": 1})
        checkpoint_before_cancel = store.get_last_checkpoint(
            created.job_id, first_step.step_id
        )
        assert checkpoint_before_cancel is not None
        store.request_cancel(created.job_id)
        store.cancel_at_boundary(lease)
    project_fact_normalization_run_status(
        session_factory,
        created.job_id,
        FactNormalizationRunStatus.CANCELLED,
    )

    assert service.retry(created.job_id).state == "queued"

    with session_factory() as session:
        snapshot = JobStore(session).snapshot(created.job_id)
        states = {step.step_id: step.state for step in snapshot.steps}
        assert states[first_step.step_id] == "completed"
        assert sum(state == "queued" for state in states.values()) == 1
        assert JobStore(session).get_last_checkpoint(
            created.job_id, first_step.step_id
        ) == checkpoint_before_cancel
        assert (
            FactNormalizationRunRepository(session).get(created.run_id).status.value
            == "running"
        )


def test_terminal_job_failure_projects_run_terminal_status(session_factory):
    from app.domain.contracts.enums import FactNormalizationRunStatus
    from app.workflow.runner import JobRunner

    with session_factory() as session:
        chain = _seed_chain(session, prefix="failed-run")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)

    def fatal(_evidence_input):
        raise ValueError("确定性失败")

    executor = create_fact_normalization_executor(
        FactNormalizationExecutorConfig(
            session_factory=session_factory,
            transport_fn=fatal,
        )
    )
    runner = JobRunner(
        session_factory,
        {"fact_normalization": executor},
        on_failed=lambda job_id: project_fact_normalization_run_status(
            session_factory,
            job_id,
            FactNormalizationRunStatus.FAILED,
        ),
    )

    assert runner.run_job(created.job_id) is True
    with session_factory() as session:
        run = FactNormalizationRunRepository(session).get(created.run_id)
        assert run.status.value == "failed"


def test_retryable_transport_failure_can_retry_open_run(session_factory):
    from app.workflow.runner import JobRunner

    with session_factory() as session:
        chain = _seed_chain(session, prefix="retryable-open-run")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)

    def timeout(_evidence_input):
        raise TimeoutError("transport timeout")

    runner = JobRunner(session_factory, {
        "fact_normalization": create_fact_normalization_executor(
            FactNormalizationExecutorConfig(
                session_factory=session_factory, transport_fn=timeout
            )
        )
    })
    assert runner.run_job(created.job_id) is True
    with session_factory() as session:
        assert FactNormalizationRunRepository(session).get(created.run_id).status.value == "running"
    assert service.retry(created.job_id).state == "queued"
    with session_factory() as session:
        assert FactNormalizationRunRepository(session).get(created.run_id).status.value == "running"


def test_terminal_failure_manual_retry_reopens_run_and_can_finish(session_factory):
    from app.domain.contracts.enums import FactNormalizationRunStatus
    from app.workflow.runner import JobRunner

    with session_factory() as session:
        chain = _seed_chain(session, prefix="failed-retry-run")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)

    def fatal(_evidence_input):
        raise ValueError("确定性失败")

    failed_runner = JobRunner(
        session_factory,
        {
            "fact_normalization": create_fact_normalization_executor(
                FactNormalizationExecutorConfig(
                    session_factory=session_factory, transport_fn=fatal
                )
            )
        },
        on_failed=lambda job_id: project_fact_normalization_run_status(
            session_factory, job_id, FactNormalizationRunStatus.FAILED
        ),
    )
    assert failed_runner.run_job(created.job_id) is True
    assert service.retry(created.job_id).state == "queued"
    with session_factory() as session:
        assert (
            FactNormalizationRunRepository(session).get(created.run_id).status.value
            == "running"
        )

    def succeeds(evidence_input):
        return EvidenceNormalizerOutput(
            run_id=evidence_input.run_id,
            call_id=evidence_input.call_id,
            logical_document_id=evidence_input.logical_document_id,
            page_numbers=evidence_input.page_numbers,
            fact_candidates=[
                _candidate_fact(
                    evidence_input.run_id,
                    evidence_input.call_id,
                    chain["locator_id"],
                )
            ],
        )

    retry_runner = JobRunner(
        session_factory,
        {
            "fact_normalization": create_fact_normalization_executor(
                FactNormalizationExecutorConfig(
                    session_factory=session_factory, transport_fn=succeeds
                )
            )
        },
    )
    assert retry_runner.run_job(created.job_id) is True
    with session_factory() as session:
        assert JobStore(session).job_status(created.job_id).state == "completed"
        assert (
            FactNormalizationRunRepository(session).get(created.run_id).status.value
            == "succeeded"
        )


def test_startup_recovery_closes_missed_failed_run_projection(session_factory):
    from app.workflow.runner import JobRunner

    with session_factory() as session:
        chain = _seed_chain(session, prefix="recover-failed-run")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)

    def fatal(_evidence_input):
        raise ValueError("确定性失败")

    runner = JobRunner(
        session_factory,
        {
            "fact_normalization": create_fact_normalization_executor(
                FactNormalizationExecutorConfig(
                    session_factory=session_factory,
                    transport_fn=fatal,
                )
            )
        },
    )
    assert runner.run_job(created.job_id) is True
    with session_factory() as session:
        assert (
            FactNormalizationRunRepository(session).get(created.run_id).status.value
            == "running"
        )

    recover_fact_normalization_runs(session_factory)

    with session_factory() as session:
        assert (
            FactNormalizationRunRepository(session).get(created.run_id).status.value
            == "failed"
        )


def test_executor_maps_text_transport_empty_json_to_empty_output(session_factory):
    with session_factory() as session:
        chain = _seed_chain(session, prefix="empty-text")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)
    job_payload = service.get_job(created.job_id)["payload"]

    class EmptyJsonTransport:
        def start(self, *, prompt):
            call = job_payload["calls"][0]
            body = {
                "schema_version": "phase5/v1",
                "run_id": created.run_id,
                "call_id": call["call_id"],
                "logical_document_id": call["logical_document_id"],
                "page_numbers": call["page_numbers"],
                "fact_candidates": [],
                "event_candidates": [],
                "exposure_candidates": [],
                "unresolved_items": [],
            }
            return type(
                "Response",
                (),
                {"session_id": "empty-session", "text": json.dumps(body, ensure_ascii=False)},
            )()

        def continue_session(self, *, session_id, prompt):
            raise AssertionError("空输出修复预算为零，不应继续会话")

    executor = create_fact_normalization_executor(
        FactNormalizationExecutorConfig(
            session_factory=session_factory,
            transport=EmptyJsonTransport(),
            max_schema_repairs=0,
        )
    )
    ctx = StepContext(
        job_id=created.job_id,
        job_type="fact_normalization",
        job_payload=job_payload,
        step_id="normalize_000_" + chain["logical_document_id"],
        name="test",
        attempt=1,
        last_checkpoint_id=None,
        last_checkpoint=None,
        max_attempts=3,
    )
    with pytest.raises(StepFailure) as exc:
        executor(ctx)
    assert exc.value.error_code == "EMPTY_OUTPUT"


def test_model_draft_is_hydrated_gated_and_persisted_by_real_executor(
    session_factory,
):
    from app.workflow.runner import JobRunner

    with session_factory() as session:
        chain = _seed_chain(session, prefix="draft-output")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)

    class DraftTransport:
        def start(self, *, prompt):
            body = {
                "schema_version": "phase5/normalizer-draft/v3",
                "fact_candidates": [
                    {
                        "candidate_ref": "f1",
                        "fact_type": "检验结果",
                        "profile_lane": "test_exam_score",
                        "polarity": "affirmed",
                        "asserted_object": "ALT",
                        "raw_value": "ALT 5",
                        "canonical_value": "ALT 5",
                        "unit": None,
                        "date_range": None,
                        "record_time": None,
                        "locator_ids": [chain["locator_id"]],
                        "candidate_source_semantics": "同期客观结果",
                        "assertion_basis": {
                            "asserted_object": "ALT",
                            "assertion_text": "ALT 5",
                            "locator_id": chain["locator_id"],
                        },
                        "model_uncertainty": 0.05,
                    }
                ],
                "event_candidates": [],
                "exposure_candidates": [],
                "actual_exposure_fact_refs": [],
                "non_exposure_medication_fact_refs": [],
                "unresolved_items": [],
            }
            return type(
                "Response",
                (),
                {
                    "session_id": "draft-session",
                    "text": json.dumps(body, ensure_ascii=False),
                },
            )()

        def continue_session(self, *, session_id, prompt):
            raise AssertionError("合法草稿不应进入结构修复")

    runner = JobRunner(
        session_factory,
        {
            "fact_normalization": create_fact_normalization_executor(
                FactNormalizationExecutorConfig(
                    session_factory=session_factory,
                    transport=DraftTransport(),
                )
            )
        },
    )

    assert runner.run_job(created.job_id) is True
    with session_factory() as session:
        run = FactNormalizationRunRepository(session).get(created.run_id)
        candidates = session.execute(
            select(FactNormalizationCandidateRecord).where(
                FactNormalizationCandidateRecord.run_id == created.run_id
            )
        ).scalars().all()
        assert run.status.value == "succeeded"
        assert len(candidates) == 1
        candidate = decode_contract(
            ClinicalFactCandidateV2,
            candidates[0].payload_json,
            candidates[0].payload_sha256,
        )
        assert candidate.candidate_id != "f1"
        assert candidate.assertion_basis is not None
        assert candidate.assertion_basis.source_text_sha256 == _sha(SOURCE_TEXT)


def test_finalize_atomically_publishes_rule_links_and_expectations(session_factory):
    from app.domain.contracts.enums import ExpectationStatus, ReviewStage
    from app.storage.evidence_expectation_repository import EvidenceExpectationV2Repository
    from app.storage.fact_repositories import ClinicalFactV2Repository
    from app.storage.fact_rule_link_repository import FactRuleLinkV2Repository
    from app.storage.models import ReviewEpisodeRecord, WorkflowStageRecord
    from app.storage.repositories import EpisodeRepository
    from tests.v2.projections.test_evidence_expectations import _template

    with session_factory() as session:
        chain = _seed_chain(session, prefix="finalize-derived")
        workflow_stage_id = session.execute(
            select(WorkflowStageRecord.workflow_stage_id).where(
                WorkflowStageRecord.protocol_version_id == chain["protocol_version_id"],
                WorkflowStageRecord.stage == "screening",
            )
        ).scalar_one()
        _update_episode(
            session,
            session.get(ReviewEpisodeRecord, chain["episode_id"]),
            workflow_stage_id=workflow_stage_id,
        )
        episode = EpisodeRepository(session).get(chain["episode_id"])
        template = _template(
            session,
            {
                **chain,
                "run_id": "finalize-derived",
                "workflow_stage_id": episode.workflow_stage_id,
            },
            requirement_id="alt-result",
            fact_type="lab_result",
            due_stage=ReviewStage.SCREENING,
            requires_contemporaneous_objective_source=True,
        )
        requirement_id = template.requirement_id
        session.commit()

    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)

    def transport(evidence_input):
        candidate = _candidate_fact(
            evidence_input.run_id, evidence_input.call_id, chain["locator_id"]
        ).model_copy(
            update={
                "raw_value": 5.0,
                "canonical_value": 5.0,
                "unit": "mmol/L",
                "supported_requirement_ids": [requirement_id],
            }
        )
        return EvidenceNormalizerOutput(
            run_id=evidence_input.run_id,
            call_id=evidence_input.call_id,
            logical_document_id=evidence_input.logical_document_id,
            page_numbers=evidence_input.page_numbers,
            fact_candidates=[candidate],
            event_candidates=[],
            exposure_candidates=[],
            unresolved_items=[],
        )

    executor = create_fact_normalization_executor(
        FactNormalizationExecutorConfig(
            session_factory=session_factory,
            transport_fn=transport,
        )
    )
    runner = JobRunner(
        session_factory,
        {"fact_normalization": executor},
    )
    assert runner.run_job(created.job_id) is True

    with session_factory() as session:
        job_status = JobStore(session).job_status(created.job_id)
        assert job_status.state == "completed"
        published_facts = ClinicalFactV2Repository(session).list_by_episode(
            chain["episode_id"]
        )
        assert len(published_facts) == 1
        assert published_facts[0].supported_requirement_ids == [requirement_id]
        links = FactRuleLinkV2Repository(session).list_facts_for_requirement(
            chain["rule_set_id"], 1, requirement_id
        )
        expectations = EvidenceExpectationV2Repository(session).list_by_episode(
            chain["episode_id"]
        )
        assert len(links) == 1
        assert len(expectations) == 1
        assert expectations[0].template_id == template.template_id
        assert expectations[0].status == ExpectationStatus.OBSERVED


def test_finalize_projects_record_gap_after_complete_snapshot_has_no_fact(
    session_factory,
):
    """完整页闭包后仍未见当前到期记录时，投影保守的记录不完整。"""
    from app.domain.contracts.enums import ExpectationStatus, GapType, ReviewStage
    from app.storage.evidence_expectation_repository import EvidenceExpectationV2Repository
    from app.storage.models import WorkflowStageRecord
    from tests.v2.projections.test_evidence_expectations import _template

    with session_factory() as session:
        chain = _seed_chain(session, prefix="finalize-missing-gap")
        workflow_stage_id = session.execute(
            select(WorkflowStageRecord.workflow_stage_id).where(
                WorkflowStageRecord.protocol_version_id == chain["protocol_version_id"],
                WorkflowStageRecord.stage == "screening",
            )
        ).scalar_one()
        _update_episode(
            session,
            session.get(ReviewEpisodeRecord, chain["episode_id"]),
            workflow_stage_id=workflow_stage_id,
        )
        template = _template(
            session,
            {
                **chain,
                "run_id": "finalize-missing-gap",
                "workflow_stage_id": workflow_stage_id,
            },
            requirement_id="missing-procedure",
            fact_type="procedure_done",
            due_stage=ReviewStage.SCREENING,
        )
        session.commit()

    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)

    def transport(evidence_input):
        candidate = _candidate_fact(
            evidence_input.run_id, evidence_input.call_id, chain["locator_id"]
        )
        return EvidenceNormalizerOutput(
            run_id=evidence_input.run_id,
            call_id=evidence_input.call_id,
            logical_document_id=evidence_input.logical_document_id,
            page_numbers=evidence_input.page_numbers,
            fact_candidates=[candidate],
            event_candidates=[],
            exposure_candidates=[],
            unresolved_items=[],
        )

    runner = JobRunner(
        session_factory,
        {
            "fact_normalization": create_fact_normalization_executor(
                FactNormalizationExecutorConfig(
                    session_factory=session_factory,
                    transport_fn=transport,
                )
            )
        },
    )
    assert runner.run_job(created.job_id) is True

    with session_factory() as session:
        job = session.get(JobRecord, created.job_id)
        assert job is not None
        assert job.state == "completed"
        expectations = EvidenceExpectationV2Repository(session).list_by_episode(
            chain["episode_id"]
        )
        by_template = {item.template_id: item for item in expectations}
        projected = by_template[template.template_id]
        assert projected.status == ExpectationStatus.ABSENT
        assert projected.gap_type == GapType.RECORD_INCOMPLETE
        assert projected.gap_detail == "当前尚无已核实的相关记录：资料核对要求"


@pytest.mark.parametrize("unverified_judgment", [False, True])
def test_gap_signals_cover_overdue_prior_stage_without_model_or_database(monkeypatch, unverified_judgment):
    from types import SimpleNamespace

    from app.domain.contracts.enums import GapType, ReviewStage
    from app.services import fact_normalization_executor as module

    template = SimpleNamespace(
        template_id="template-screening-overdue",
        requirement_id="requirement-screening-overdue",
        due_stage=ReviewStage.SCREENING,
        workflow_stage_id="workflow-screening",
        required_source_types=["investigator_assessment"] if unverified_judgment else [],
        description="筛选期资料核对要求",
    )
    authority = SimpleNamespace(
        rule_set_id="ruleset-1",
        rule_set_revision=1,
        review_episode_id="episode-baseline",
    )
    monkeypatch.setattr(module, "list_expectation_templates", lambda *_: [template])
    monkeypatch.setattr(
        module,
        "EpisodeRepository",
        lambda _session: SimpleNamespace(
            get=lambda _episode_id: SimpleNamespace(
                stage=ReviewStage.BASELINE,
                workflow_stage_id="workflow-baseline",
            )
        ),
    )

    unresolved = SimpleNamespace(
        item=SimpleNamespace(
            gap_type=GapType.OCR_OR_PARSE_RISK,
            affected_requirement_ids=[template.requirement_id],
            reason="页面需人工校对",
            referenced_file_id=None,
        )
    )
    signals = module._expectation_gap_signals(
        object(), authority, [] if unverified_judgment else [unresolved]
    )

    assert [signal.kind for signal in signals] == [
        GapType.OBSERVATION_UNVERIFIED if unverified_judgment else GapType.OCR_OR_PARSE_RISK
    ]
    if unverified_judgment:
        assert signals[0].detail == "现有资料尚未核实是否包含本条要求的记录，暂无法判定：筛选期资料核对要求"
    assert {signal.applies_to_template_id for signal in signals} == {
        template.template_id
    }


def test_gap_signals_distinguish_rejected_source_record_from_missing_record(monkeypatch):
    from types import SimpleNamespace

    from app.domain.contracts.enums import FactGate, GapType, GateOutcome, ReviewStage
    from app.services import fact_normalization_executor as module

    template = SimpleNamespace(
        template_id="template-blood-pressure",
        requirement_id="requirement-blood-pressure",
        due_stage=ReviewStage.SCREENING,
        workflow_stage_id="workflow-screening",
        required_source_types=[],
        description="血压记录",
    )
    authority = SimpleNamespace(
        rule_set_id="ruleset-1",
        rule_set_revision=1,
        review_episode_id="episode-screening",
    )
    monkeypatch.setattr(module, "list_expectation_templates", lambda *_: [template])
    monkeypatch.setattr(
        module,
        "EpisodeRepository",
        lambda _session: SimpleNamespace(
            get=lambda _episode_id: SimpleNamespace(
                stage=ReviewStage.SCREENING,
                workflow_stage_id="workflow-screening",
            )
        ),
    )
    candidate = SimpleNamespace(
        candidate_id="candidate-blood-pressure",
        supported_requirement_ids=[template.requirement_id],
    )
    rejected = SimpleNamespace(
        candidate_id=candidate.candidate_id,
        gate=FactGate.TRANSACTIONAL_PUBLISH,
        outcome=GateOutcome.REJECTED,
        reasons=["非数值事实不应携带单位"],
    )

    signals = module._expectation_gap_signals(
        object(),
        authority,
        [],
        fact_candidates=[candidate],
        gate_results=[rejected],
    )

    assert [signal.kind for signal in signals] == [GapType.OCR_OR_PARSE_RISK]
    assert signals[0].detail == (
        "原始资料中发现相关记录，但尚未通过事实完整性核对："
        "非数值事实不应携带单位"
    )


def test_finalize_projects_exact_structured_gap_as_absent(session_factory):
    """精确绑定资料要求的结构化缺口应形成可解释的缺失期望。"""
    from app.domain.contracts.enums import ExpectationStatus, GapType, ReviewStage
    from app.storage.evidence_expectation_repository import EvidenceExpectationV2Repository
    from app.storage.models import WorkflowStageRecord
    from tests.v2.projections.test_evidence_expectations import _template

    with session_factory() as session:
        chain = _seed_chain(session, prefix="finalize-exact-gap")
        workflow_stage_id = session.execute(
            select(WorkflowStageRecord.workflow_stage_id).where(
                WorkflowStageRecord.protocol_version_id == chain["protocol_version_id"],
                WorkflowStageRecord.stage == "screening",
            )
        ).scalar_one()
        _update_episode(
            session,
            session.get(ReviewEpisodeRecord, chain["episode_id"]),
            workflow_stage_id=workflow_stage_id,
        )
        template = _template(
            session,
            {
                **chain,
                "run_id": "finalize-exact-gap",
                "workflow_stage_id": workflow_stage_id,
            },
            requirement_id="history-record",
            fact_type="medical_history",
            due_stage=ReviewStage.SCREENING,
        )
        session.commit()

    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)

    def transport(evidence_input):
        unrelated = _candidate_fact(
            evidence_input.run_id, evidence_input.call_id, chain["locator_id"]
        ).model_copy(
            update={"raw_value": 5.0, "canonical_value": 5.0, "unit": "mmol/L"}
        )
        return EvidenceNormalizerOutput(
            run_id=evidence_input.run_id,
            call_id=evidence_input.call_id,
            logical_document_id=evidence_input.logical_document_id,
            page_numbers=evidence_input.page_numbers,
            fact_candidates=[unrelated],
            unresolved_items=[
                EvidenceNormalizerUnresolvedItem(
                    code="history_record_incomplete",
                    message="既往史记录不完整",
                    affected_pages=evidence_input.page_numbers,
                    affected_locator_ids=[],
                    affected_requirement_ids=[template.requirement_id],
                    gap_type=GapType.RECORD_INCOMPLETE,
                    reason="当前病历未完整记录方案要求核对的既往史",
                )
            ],
        )

    runner = JobRunner(
        session_factory,
        {
            "fact_normalization": create_fact_normalization_executor(
                FactNormalizationExecutorConfig(
                    session_factory=session_factory,
                    transport_fn=transport,
                )
            )
        },
    )
    assert runner.run_job(created.job_id) is True

    with session_factory() as session:
        job = session.get(JobRecord, created.job_id)
        assert job is not None and job.state == "completed"
        expectations = EvidenceExpectationV2Repository(session).list_by_episode(
            chain["episode_id"]
        )
        assert len(expectations) == 1
        assert expectations[0].status == ExpectationStatus.ABSENT
        assert expectations[0].gap_type == GapType.RECORD_INCOMPLETE
        assert expectations[0].gap_detail == "当前病历未完整记录方案要求核对的既往史"


def test_executor_rejects_partial_page_mismatch(session_factory):
    with session_factory() as session:
        chain = _seed_chain(session, prefix="partial1")
        session.commit()
    svc = FactNormalizationJobService(session_factory)
    result = _create_job_from_source(svc, chain)
    job_payload = svc.get_job(result.job_id)["payload"]

    def transport_partial(evidence_input):
        # 返回页清单与调用不一致（部分输出）
        cand = _candidate_fact(evidence_input.run_id, evidence_input.call_id, chain["locator_id"])
        # 故意返回错误的页清单
        return EvidenceNormalizerOutput(run_id=evidence_input.run_id, call_id=evidence_input.call_id, logical_document_id=evidence_input.logical_document_id, page_numbers=[999], fact_candidates=[cand], event_candidates=[], exposure_candidates=[], unresolved_items=[])

    cfg = FactNormalizationExecutorConfig(session_factory=session_factory, transport_fn=transport_partial)
    executor = create_fact_normalization_executor(cfg)
    ctx = StepContext(job_id=result.job_id, job_type="fact_normalization", job_payload=job_payload, step_id="normalize_000_"+chain["logical_document_id"], name="test", attempt=1, last_checkpoint_id=None, last_checkpoint=None, max_attempts=3)
    with pytest.raises(StepFailure) as exc:
        executor(ctx)
    assert exc.value.error_code == "PARTIAL_OUTPUT"


# ---------------------------------------------------------------------------
# 测试：迟到回包（租约丢失）与恢复
# ---------------------------------------------------------------------------

def test_late_reply_lease_lost_is_discarded_and_recoverable(session_factory):
    from tests.v2.workflow.conftest import FakeClock
    from app.workflow.jobstore import JobStore
    from app.workflow.runner import PreparedStepResult

    clock = FakeClock()
    with session_factory() as session:
        chain = _seed_chain(session, prefix="late1")
        session.commit()
    svc = FactNormalizationJobService(session_factory, now=clock.now)
    result = _create_job_from_source(svc, chain)
    job_payload = svc.get_job(result.job_id)["payload"]
    step_id = "normalize_000_" + chain["logical_document_id"]

    def transport_ok(evidence_input):
        candidate = _candidate_fact(
            evidence_input.run_id,
            evidence_input.call_id,
            chain["locator_id"],
        )
        return EvidenceNormalizerOutput(
            run_id=evidence_input.run_id,
            call_id=evidence_input.call_id,
            logical_document_id=evidence_input.logical_document_id,
            page_numbers=evidence_input.page_numbers,
            fact_candidates=[candidate],
        )

    executor = create_fact_normalization_executor(
        FactNormalizationExecutorConfig(
            session_factory=session_factory,
            transport_fn=transport_ok,
        )
    )
    # 认领任务并启动步骤
    with session_factory() as session:
        store = JobStore(session, now=clock.now)
        lease = store.claim_job(result.job_id, "worker-1")
        assert lease is not None
        store.start_step(lease, step_id)
        session.commit()
        original_generation = lease.generation
    prepared = executor(
        StepContext(
            job_id=result.job_id,
            job_type="fact_normalization",
            job_payload=job_payload,
            step_id=step_id,
            name="证据规范化",
            attempt=1,
            last_checkpoint_id=None,
            last_checkpoint=None,
            max_attempts=3,
        )
    )
    assert isinstance(prepared, PreparedStepResult)
    # 模拟另一 worker 接管：让租约过期并被恢复器递增 generation
    clock.advance(60)
    with session_factory() as session:
        # 手动让租约过期：过期时间设为过去
        session.execute(update(JobRecord).where(JobRecord.job_id == result.job_id).values(lease_expires_at=clock.now() - timedelta(seconds=1)))
        session.commit()
    # 恢复过期租约
    report = recover_expired_jobs(session_factory, now=clock.now)
    assert result.job_id in {*report.recovered_jobs, *report.requeued_jobs}
    # 原 worker 的领域写入和检查点必须由同一写栅栏共同拒绝。
    with session_factory() as session:
        store = JobStore(session, now=clock.now)
        from app.workflow.errors import LeaseLostError

        with pytest.raises(LeaseLostError):
            with session.begin():
                store.acquire_step_commit(lease, step_id)
                prepared.apply(session)
                store.complete_step_after_commit_fence(
                    lease,
                    step_id,
                    checkpoint_payload=prepared.checkpoint,
                )
    with session_factory() as session:
        assert session.get(
            FactNormalizationCallRecord,
            job_payload["calls"][0]["call_id"],
        ) is None
        assert session.execute(select(FactNormalizationCandidateRecord)).scalars().all() == []
    # 任务可被新 worker 重新认领
    with session_factory() as session:
        store = JobStore(session, now=clock.now)
        new_lease = store.claim_job(result.job_id, "worker-2")
        assert new_lease is not None
        assert new_lease.generation > original_generation


# ---------------------------------------------------------------------------
# 测试：Checkpoint 幂等与中断重启
# ---------------------------------------------------------------------------

def test_checkpoint_idempotent_and_restart_from_last_success(session_factory):
    from app.workflow.jobstore import JobStore
    from tests.v2.workflow.conftest import FakeClock
    from app.workflow.runner import JobRunner

    clock = FakeClock()
    with session_factory() as session:
        chain = _seed_chain(session, prefix="restart1")
        session.commit()
    svc = FactNormalizationJobService(session_factory, now=clock.now)
    result = _create_job_from_source(svc, chain)
    job_payload = svc.get_job(result.job_id)["payload"]
    transport_calls = {"count": 0}

    def transport_once(evidence_input):
        transport_calls["count"] += 1
        cand = _candidate_fact(evidence_input.run_id, evidence_input.call_id, chain["locator_id"])
        return EvidenceNormalizerOutput(run_id=evidence_input.run_id, call_id=evidence_input.call_id, logical_document_id=evidence_input.logical_document_id, page_numbers=evidence_input.page_numbers, fact_candidates=[cand], event_candidates=[], exposure_candidates=[], unresolved_items=[])

    cfg = FactNormalizationExecutorConfig(session_factory=session_factory, transport_fn=transport_once)
    executor = create_fact_normalization_executor(cfg)

    runner = JobRunner(
        session_factory,
        {"fact_normalization": executor},
        worker_id="worker-1",
        now=clock.now,
    )
    assert runner.run_job(result.job_id) is True

    # 验证候选已持久化
    with session_factory() as session:
        rows = session.execute(select(FactNormalizationCandidateRecord)).scalars().all()
        assert len(rows) == 1
        call_row = session.get(
            FactNormalizationCallRecord,
            job_payload["calls"][0]["call_id"],
        )
        assert call_row is not None
        store = JobStore(session, now=clock.now)
        assert len(
            store.list_checkpoints(
                result.job_id,
                "normalize_000_" + chain["logical_document_id"],
            )
        ) == 1
        assert store.job_status(result.job_id).state == "completed"

    reused = _create_job_from_source(svc, chain)
    assert reused.job_id == result.job_id
    assert reused.created is False
    assert runner.run_job(result.job_id) is False
    assert transport_calls["count"] == 1
    with session_factory() as session:
        rows = session.execute(select(FactNormalizationCandidateRecord)).scalars().all()
        assert len(rows) == 1


def test_checkpoint_replay_revalidates_active_authority(session_factory):
    from app.domain.contracts.review import ReviewEpisode
    from app.workflow.runner import JobRunner

    with session_factory() as session:
        chain = _seed_chain(session, prefix="checkpoint-authority")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)
    payload = service.get_job(created.job_id)["payload"]
    step_id = "normalize_000_" + chain["logical_document_id"]

    def transport(evidence_input):
        return EvidenceNormalizerOutput(
            run_id=evidence_input.run_id,
            call_id=evidence_input.call_id,
            logical_document_id=evidence_input.logical_document_id,
            page_numbers=evidence_input.page_numbers,
            fact_candidates=[
                _candidate_fact(
                    evidence_input.run_id,
                    evidence_input.call_id,
                    chain["locator_id"],
                )
            ],
        )

    executor = create_fact_normalization_executor(
        FactNormalizationExecutorConfig(
            session_factory=session_factory,
            transport_fn=transport,
        )
    )
    runner = JobRunner(
        session_factory,
        {"fact_normalization": executor},
        worker_id="worker-checkpoint-authority",
    )
    assert runner.run_job(created.job_id) is True
    with session_factory() as session:
        checkpoint_row = JobStore(session).get_last_checkpoint(created.job_id, step_id)
        assert checkpoint_row is not None
        checkpoint_id, checkpoint = checkpoint_row
        episode = session.get(ReviewEpisodeRecord, chain["episode_id"])
        decoded = decode_contract(
            ReviewEpisode, episode.payload_json, episode.payload_sha256
        )
        _update_episode(session, episode, revision=decoded.revision + 1)
        session.commit()

    replay_context = StepContext(
        job_id=created.job_id,
        job_type="fact_normalization",
        job_payload=payload,
        step_id=step_id,
        name="恢复检查",
        attempt=2,
        last_checkpoint_id=checkpoint_id,
        last_checkpoint=checkpoint,
        max_attempts=3,
    )
    with pytest.raises(StepFailure) as exc:
        executor(replay_context)
    assert exc.value.error_code == "STALE_AUTHORITY"


def test_unresolved_only_run_is_durable_and_marked_partial(session_factory):
    from app.workflow.runner import JobRunner

    with session_factory() as session:
        chain = _seed_chain(session, prefix="unresolved-only")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)

    def transport_unresolved(evidence_input):
        return EvidenceNormalizerOutput(
            run_id=evidence_input.run_id,
            call_id=evidence_input.call_id,
            logical_document_id=evidence_input.logical_document_id,
            page_numbers=evidence_input.page_numbers,
            unresolved_items=[
                EvidenceNormalizerUnresolvedItem(
                    code="ocr_text_uncertain",
                    message="本页关键数值无法可靠辨认",
                    affected_pages=evidence_input.page_numbers,
                    affected_locator_ids=[],
                    reason="有效文本存在无法确认的关键字符，需核对原件",
                )
            ],
        )

    runner = JobRunner(
        session_factory,
        {
            "fact_normalization": create_fact_normalization_executor(
                FactNormalizationExecutorConfig(
                    session_factory=session_factory,
                    transport_fn=transport_unresolved,
                )
            )
        },
        worker_id="worker-unresolved",
    )
    assert runner.run_job(created.job_id) is True
    with session_factory() as session:
        unresolved_rows = session.execute(
            select(FactNormalizationUnresolvedItemRecord)
        ).scalars().all()
        assert len(unresolved_rows) == 1
        assert unresolved_rows[0].affected_pages_json == [1]
        run = session.get(FactNormalizationRunRecord, created.run_id)
        assert run is not None
        assert run.status == "partial"

    reused = _create_job_from_source(service, chain)
    assert reused.job_id == created.job_id
    assert reused.created is False
    assert runner.run_job(created.job_id) is False
    with session_factory() as session:
        unresolved_rows = session.execute(
            select(FactNormalizationUnresolvedItemRecord)
        ).scalars().all()
        assert len(unresolved_rows) == 1


def test_gate_rejected_candidate_marks_run_partial(session_factory):
    from app.workflow.runner import JobRunner

    with session_factory() as session:
        chain = _seed_chain(session, prefix="gate-partial")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)

    def transport_mismatched_assertion(evidence_input):
        candidate = _candidate_fact(
            evidence_input.run_id,
            evidence_input.call_id,
            chain["locator_id"],
            asserted_object="AST",
        )
        return EvidenceNormalizerOutput(
            run_id=evidence_input.run_id,
            call_id=evidence_input.call_id,
            logical_document_id=evidence_input.logical_document_id,
            page_numbers=evidence_input.page_numbers,
            fact_candidates=[candidate],
        )

    runner = JobRunner(
        session_factory,
        {
            "fact_normalization": create_fact_normalization_executor(
                FactNormalizationExecutorConfig(
                    session_factory=session_factory,
                    transport_fn=transport_mismatched_assertion,
                )
            )
        },
        worker_id="worker-gate-partial",
    )
    assert runner.run_job(created.job_id) is True
    with session_factory() as session:
        run = session.get(FactNormalizationRunRecord, created.run_id)
        assert run is not None
        assert run.status == "partial"


@pytest.mark.parametrize("reject_sources", [False, True])
@pytest.mark.parametrize("with_checkpoint", [False, True])
def test_duplicate_candidate_not_duplicated_on_retry(session_factory, monkeypatch, reject_sources, with_checkpoint):
    with session_factory() as session:
        chain = _seed_chain(session, prefix="dup1")
        session.commit()
    svc = FactNormalizationJobService(session_factory)
    result = _create_job_from_source(svc, chain)
    job_payload = svc.get_job(result.job_id)["payload"]

    cand = _candidate_fact(job_payload["run_id"], job_payload["calls"][0]["call_id"], chain["locator_id"])

    transport_calls = {"count": 0}

    def transport_dup(evidence_input):
        transport_calls["count"] += 1
        return EvidenceNormalizerOutput(run_id=evidence_input.run_id, call_id=evidence_input.call_id, logical_document_id=evidence_input.logical_document_id, page_numbers=evidence_input.page_numbers, fact_candidates=[cand], event_candidates=[], exposure_candidates=[], unresolved_items=[])

    cfg = FactNormalizationExecutorConfig(session_factory=session_factory, transport_fn=transport_dup)
    executor = create_fact_normalization_executor(cfg)
    ctx = StepContext(job_id=result.job_id, job_type="fact_normalization", job_payload=job_payload, step_id="normalize_000_"+chain["logical_document_id"], name="test", attempt=1, last_checkpoint_id=None, last_checkpoint=None, max_attempts=3)
    first = executor(ctx)
    with session_factory() as session, session.begin():
        first.apply(session)
    # 检查点缺失但同身份成功调用已持久化：重试必须从持久记录恢复检查点，
    # 不得为同一调用再次消耗模型，也不得产生重复候选。
    ctx2 = StepContext(job_id=result.job_id, job_type="fact_normalization", job_payload=job_payload, step_id="normalize_000_"+chain["logical_document_id"], name="test", attempt=2, last_checkpoint_id=None, last_checkpoint=None, max_attempts=3)
    if with_checkpoint:
        from dataclasses import replace
        ctx2 = replace(ctx2, last_checkpoint_id="saved", last_checkpoint=first.checkpoint)
    if reject_sources:
        from app.services import fact_normalization_replay_sources
        def invalid_source(*args, **kwargs):
            assert kwargs["payload"] == job_payload
            raise ValueError("候选没有已采信观察")
        monkeypatch.setattr(fact_normalization_replay_sources, "validate_replayed_sources", invalid_source)
        with pytest.raises(StepFailure, match="来源未通过复验"):
            executor(ctx2)
    else:
        second = executor(ctx2)
        assert second == first.checkpoint
    assert transport_calls["count"] == 1
    with session_factory() as session:
        rows = session.execute(
            select(FactNormalizationCandidateRecord).where(
                FactNormalizationCandidateRecord.candidate_id
                == first.checkpoint["candidate_ids"][0]
            )
        ).scalars().all()
        assert len(rows) == 1


def test_lost_step_checkpoint_recovers_from_persisted_call_without_model_recall(session_factory):
    """中断现场回归：成功调用与候选已持久化但步骤检查点缺失时，
    重新认领的任务必须零模型调用完成同一调用并正常汇总发布。"""
    from app.workflow.runner import JobRunner

    with session_factory() as session:
        chain = _seed_chain(session, prefix="lostckpt")
        session.commit()
    svc = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(svc, chain)
    job_payload = svc.get_job(created.job_id)["payload"]
    step_id = "normalize_000_" + chain["logical_document_id"]

    def transport_once(evidence_input):
        return EvidenceNormalizerOutput(
            run_id=evidence_input.run_id,
            call_id=evidence_input.call_id,
            logical_document_id=evidence_input.logical_document_id,
            page_numbers=evidence_input.page_numbers,
            fact_candidates=[
                _candidate_fact(
                    evidence_input.run_id,
                    evidence_input.call_id,
                    chain["locator_id"],
                )
            ],
        )

    executor = create_fact_normalization_executor(
        FactNormalizationExecutorConfig(
            session_factory=session_factory,
            transport_fn=transport_once,
        )
    )
    # 模拟中断：模型结果已按 PreparedStepResult 提交领域副作用，
    # 但 runner 的检查点/步骤完成事务未及发生。
    prepared = executor(
        StepContext(
            job_id=created.job_id,
            job_type="fact_normalization",
            job_payload=job_payload,
            step_id=step_id,
            name="证据规范化",
            attempt=1,
            last_checkpoint_id=None,
            last_checkpoint=None,
            max_attempts=3,
        )
    )
    with session_factory() as session, session.begin():
        prepared.apply(session)

    def transport_must_not_run(evidence_input):
        raise AssertionError("检查点缺失恢复不得再次调用模型")

    recovery_runner = JobRunner(
        session_factory,
        {
            "fact_normalization": create_fact_normalization_executor(
                FactNormalizationExecutorConfig(
                    session_factory=session_factory,
                    transport_fn=transport_must_not_run,
                )
            )
        },
        worker_id="worker-lost-checkpoint",
    )
    assert recovery_runner.run_job(created.job_id) is True
    with session_factory() as session:
        candidate_rows = session.execute(
            select(FactNormalizationCandidateRecord)
        ).scalars().all()
        assert len(candidate_rows) == 1
        assert candidate_rows[0].candidate_id in prepared.checkpoint["candidate_ids"]
        checkpoint = JobStore(session).get_last_checkpoint(created.job_id, step_id)
        assert checkpoint is not None
        assert checkpoint[1]["candidate_ids"] == prepared.checkpoint["candidate_ids"]
        assert checkpoint[1]["raw_output_sha256"] == prepared.checkpoint["raw_output_sha256"]
        assert JobStore(session).job_status(created.job_id).state == "completed"
        run = session.get(FactNormalizationRunRecord, created.run_id)
        assert run is not None
        # 冻结文档元数据会在适配边界校准夹具候选的来源语义；此处证明恢复
        # 路径把同一持久领域状态收敛到同一成功终态，且不重放模型。
        assert run.status == "succeeded"


def test_persisted_call_identity_conflict_fails_closed(session_factory):
    """持久调用与任务步骤身份不一致时失效关闭，绝不复用也绝不重放模型。"""
    with session_factory() as session:
        chain = _seed_chain(session, prefix="idconf")
        session.commit()
    svc = FactNormalizationJobService(session_factory)
    result = _create_job_from_source(svc, chain)
    job_payload = svc.get_job(result.job_id)["payload"]
    call_payload = job_payload["calls"][0]

    def transport_never(evidence_input):
        raise AssertionError("身份冲突时不得调用模型")

    executor = create_fact_normalization_executor(
        FactNormalizationExecutorConfig(
            session_factory=session_factory,
            transport_fn=transport_never,
        )
    )
    with session_factory() as session, session.begin():
        FactNormalizationCallRepository(session).create(
            FactNormalizationCall(
                call_id=str(call_payload["call_id"]),
                run_id=str(job_payload["run_id"]),
                logical_document_id=str(call_payload["logical_document_id"]),
                page_numbers=list(call_payload["page_numbers"]),
                status=FactCallStatus.SUCCEEDED,
                input_sha256="f" * 64,
                raw_output_sha256="0" * 64,
                created_at=NOW,
            )
        )
    ctx = StepContext(job_id=result.job_id, job_type="fact_normalization", job_payload=job_payload, step_id="normalize_000_"+chain["logical_document_id"], name="test", attempt=2, last_checkpoint_id=None, last_checkpoint=None, max_attempts=3)
    with pytest.raises(StepFailure) as exc:
        executor(ctx)
    assert exc.value.error_code == "CALL_IDENTITY_CONFLICT"
