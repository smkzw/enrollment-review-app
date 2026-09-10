"""Phase 5 v2 临床事实仓储与权威校验确定性测试（Slice 5.1，worker_03）。

覆盖 worker_03 的权威/定位门禁反例与追加写回读：

- 权威元组拒绝：legacy/缺失快照 id；未激活/未配对活动指针；非活动快照/处理修订；
  陈旧审核节点修订；作用域不一致；base/未激活/未就绪处理修订；
- 定位引用拒绝：跨审核节点 locator；跨快照（非快照成员资料）locator；
  跨处理修订（effective_text locator 绑定其他修订）locator；断言依据定位不在
  事实定位集合；
- 跨实体拒绝：事件/暴露/冲突引用不同权威元组的事实；事件/暴露/冲突定位不属于其
  引用事实的定位闭包；门禁结果不属于运行；
- revision 链只允许追加链头 +1：同稳定身份 revision=2 允许、回退 revision=1 拒绝；
- 追加写回读：事实/事件/暴露/冲突经 canonical JSON + 镜像列交叉校验后还原，
  payload 与链接表定位一致；运行幂等键重复提交返回原运行。

所有门禁在仓储写入边界执行（``fact_authority.FactAuthorityValidator``），旧占位
``clinical_facts`` 等表不进入本读/写路径。
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.domain.contracts.enums import (
    DatePrecision,
    DisambiguationOutcome,
    DurationStatus,
    FactCallStatus,
    FactGate,
    FactNormalizationRunStatus,
    FactPolarity,
    GateOutcome,
    LocatorAuthenticity,
    LocatorPrecision,
    LocatorSourceLayer,
    ProfileLane,
    SnapshotMemberOrigin,
    SnapshotStatus,
    SourceStrength,
    UploadMode,
)
from app.domain.contracts.evidence_ingestion import (
    EvidenceSnapshot,
    EvidenceSnapshotMember,
    SourceDocumentVersion,
)
from app.domain.contracts.evidence_locator import (
    CompleteEvidenceProcessingRevision,
    EvidenceLocatorArtifact,
)
from app.domain.contracts.facts import (
    AssertionBasis,
    ClinicalConflictGroupV2,
    ClinicalEventCandidateV2,
    ClinicalEventV2,
    ClinicalFactCandidateV2,
    ClinicalFactV2,
    FactAuthority,
    FactGateResult,
    FactNormalizationCall,
    FactNormalizationRun,
    MedicationExposureCandidateV2,
    MedicationExposureV2,
    PartialDateRange,
    clinical_event_stable_identity,
    clinical_fact_stable_identity,
    fact_run_idempotency_key,
    medication_exposure_stable_identity,
)
from app.domain.contracts.review import ReviewEpisode
from app.domain.publication import (
    evidence_processing_manifest_hash,
    evidence_snapshot_collection_hash,
)
from app.storage.codecs import PersistedContractInvalid, decode_contract, encode_contract
from app.storage.evidence_locator_models import (
    EvidenceLocatorArtifactRecord,
    ProcessingRevisionLocatorRecord,
)
from app.storage.evidence_models import (
    EvidenceSnapshotMemberRecord,
    EvidenceSnapshotV2Record,
    SourceBlobRecord,
    SourceDocumentVersionV2Record,
)
from app.storage.fact_authority import (
    FactAuthorityError,
    FactLocatorReferenceError,
)
from app.storage.fact_repositories import (
    ClinicalConflictGroupV2Repository,
    ClinicalEventV2Repository,
    ClinicalFactV2Repository,
    FactCrossEntityError,
    FactGateResultRepository,
    FactNormalizationCandidateRepository,
    FactNormalizationCallRepository,
    FactNormalizationRunRepository,
    FactRevisionChainError,
    MedicationExposureV2Repository,
    Phase5RepositoryError,
)
from app.storage.facts_models import (
    ClinicalConflictGroupV2Record,
    ClinicalConflictMemberV2Record,
    ClinicalEventV2Record,
    ClinicalFactV2Record,
    EventFactLinkRecord,
    ExposureFactLinkRecord,
    FactEvidenceLocatorLinkRecord,
    FactGateResultRecord,
    FactNormalizationCandidateRecord,
    FactNormalizationCallRecord,
    FactNormalizationRunRecord,
    MedicationExposureV2Record,
)
from app.storage.models import (
    EvidenceExpectationTemplateRecord,
    EvidenceRequirementRecord,
    ModelConfigRecord,
    ProjectRecord,
    PromptVersionRecord,
    ReviewEpisodeRecord,
    RuleSetRecord,
    SubjectRecord,
    ProtocolDocumentVersionRecord,
    WorkflowStageRecord,
)
from app.storage.ocr_models import (
    EvidenceProcessingRevisionRecord,
    PageArtifactRecord,
)
from app.storage.repositories import DuplicateRecordError, RepositoryError

NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)
_PAYLOAD = '{"kind": "test"}'
_PAYLOAD_SHA = hashlib.sha256(_PAYLOAD.encode("utf-8")).hexdigest()
_SOURCE_HASH_BY_LOCATOR: dict[str, str] = {}
_EXCERPT_BY_LOCATOR: dict[str, str] = {}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _add(session, record):
    session.add(record)
    session.flush()
    return record


def _bind_payload(record, contract) -> None:
    record.payload_json, record.payload_sha256 = encode_contract(contract)


def _update_payload(record, contract_type, **changes) -> None:
    contract = decode_contract(
        contract_type, record.payload_json, record.payload_sha256
    )
    _bind_payload(record, contract.model_copy(update=changes))


def _update_episode(session, episode: ReviewEpisodeRecord, **changes) -> None:
    from sqlalchemy import update

    contract = decode_contract(
        ReviewEpisode, episode.payload_json, episode.payload_sha256
    ).model_copy(update=changes)
    payload_json, payload_sha256 = encode_contract(contract)
    session.execute(
        update(ReviewEpisodeRecord)
        .where(ReviewEpisodeRecord.review_episode_id == episode.review_episode_id)
        .values(payload_json=payload_json, payload_sha256=payload_sha256, **changes)
    )
    session.expire_all()


def _seed_chain_legacy(session, prefix: str) -> dict[str, str]:
    """播种一条完整活动证据链（protocol/rule_set/project/subject/episode(已激活)/
    snapshot_v2/source doc/page artifact/base+complete 修订/prompt/model_config/
    run/call/gate/locator）。返回全部 id 供权威元组与发布实体引用。"""
    protocol_version_id = f"{prefix}-protocol"
    rule_set_id = f"{prefix}-ruleset"
    project_id = f"{prefix}-project"
    subject_id = f"{prefix}-subject"
    episode_id = f"{prefix}-episode"
    snapshot_id = f"{prefix}-snapshot-v2"
    doc_id = f"{prefix}-doc"
    page_artifact_id = f"{prefix}-pa"
    base_revision_id = f"{prefix}-base"
    complete_revision_id = f"{prefix}-complete"
    locator_id = f"{prefix}-locator"
    locator_id_2 = f"{prefix}-locator2"
    prompt_version_id = f"{prefix}-prompt"
    model_config_id = f"{prefix}-modelcfg"
    run_id = f"{prefix}-run"
    call_id = f"{prefix}-call"
    gate_id = f"{prefix}-gate"
    event_gate_id = f"{prefix}-event-gate"
    exposure_gate_id = f"{prefix}-exposure-gate"

    _add(session, ProtocolDocumentVersionRecord(
        protocol_version_id=protocol_version_id,
        protocol_code="P",
        official_version="v1",
        official_date_value=None,
        official_date_precision="unknown",
        sha256=_sha("protocol"),
        integrity_manifest_sha256=_sha("integrity"),
        authority_record_sha256=_sha("authority"),
        authority_confirmation_id="confirm",
        authority_gate_result_id="agr",
        integrity_gate_result_id="igr",
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
    ))
    _add(session, RuleSetRecord(
        rule_set_id=rule_set_id, revision=1, protocol_version_id=protocol_version_id,
        study_phase="phase_iii", payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA,
        created_at=NOW,
    ))
    _add(session, EvidenceRequirementRecord(
        rule_set_id=rule_set_id, rule_set_revision=1, requirement_id="req",
        rule_component_id=None, procedure_catalog_item_id="catalog",
        fact_type="vital_sign", due_stage="screening",
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
    ))
    _add(session, ProjectRecord(
        project_id=project_id, project_code="P", project_name="p",
        study_phase="phase_iii", protocol_version_id=protocol_version_id,
        rule_set_id=rule_set_id, rule_set_revision=1,
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA,
        revision=1, created_at=NOW, updated_at=NOW,
    ))
    _add(session, SubjectRecord(
        subject_id=subject_id, subject_code="S", project_id=project_id,
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA,
        revision=1, created_at=NOW, updated_at=NOW,
    ))
    _add(session, WorkflowStageRecord(
        workflow_stage_id=f"{prefix}-stage", protocol_version_id=protocol_version_id,
        stage="screening", study_phase="phase_iii",
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
    ))
    _add(session, EvidenceExpectationTemplateRecord(
        template_id=f"{prefix}-template", rule_set_id=rule_set_id,
        rule_set_revision=1, requirement_id="req", due_stage="screening",
        study_phase="phase_iii", workflow_stage_id=f"{prefix}-stage",
        fact_type="vital_sign", required_source_types=None,
        projection_sha256=_sha("projection"),
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
    ))
    # 审核节点先建（快照/修订外键指向它）；活动指针对为空，后续原子更新配对。
    episode = _add(session, ReviewEpisodeRecord(
        review_episode_id=episode_id, subject_id=subject_id, project_id=project_id,
        rule_set_id=rule_set_id, rule_set_revision=1, study_phase="phase_iii",
        stage="screening", protocol_version_id=protocol_version_id,
        evidence_snapshot_id=None, active_evidence_snapshot_id=None,
        active_evidence_processing_revision_id=None,
        anchor_dates_json={}, due_at=None,
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA,
        revision=1, created_at=NOW, updated_at=NOW,
    ))
    _add(session, EvidenceSnapshotV2Record(
        evidence_snapshot_id=snapshot_id, project_id=project_id, subject_id=subject_id,
        review_episode_id=episode_id, upload_mode="full", prior_snapshot_id=None,
        comparison_snapshot_id=None, collection_sha256=_sha("collection"),
        created_by="tester", payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA,
        created_at=NOW,
    ))
    _add(session, SourceBlobRecord(
        source_blob_id=f"{prefix}-blob", sha256=_sha(f"{prefix}-blob"),
        byte_size=4, media_type="application/pdf", storage_ref="mem://x",
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
    ))
    _add(session, SourceDocumentVersionV2Record(
        source_document_version_id=doc_id, logical_document_id=f"{prefix}-log",
        source_blob_sha256=_sha(f"{prefix}-blob"), file_name="f.pdf",
        media_type="application/pdf", page_count=1, project_id=project_id,
        subject_id=subject_id, review_episode_id=episode_id, version_number=1,
        supersedes_version_id=None, created_by="tester",
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
    ))
    _add(session, EvidenceSnapshotMemberRecord(
        member_id=f"{prefix}-member", snapshot_id=snapshot_id,
        logical_document_id=f"{prefix}-log", source_document_version_id=doc_id,
        origin="added", payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA,
        created_at=NOW,
    ))
    _add(session, PageArtifactRecord(
        page_artifact_id=page_artifact_id, source_document_version_id=doc_id,
        page_number=1, source_sha256=_sha("page-source"),
        derivative_sha256=_sha("derivative"), coordinate_transform_version="t/v1",
        status="succeeded", payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA,
        created_at=NOW,
    ))
    _add(session, EvidenceProcessingRevisionRecord(
        evidence_processing_revision_id=base_revision_id,
        evidence_snapshot_id=snapshot_id, project_id=project_id, subject_id=subject_id,
        review_episode_id=episode_id, manifest_sha256=_sha("base-manifest"),
        status="ready", is_activatable=False, revision_kind="base",
        base_processing_revision_id=None, producer_candidate_id=None,
        candidate_input_sha256=None, completion_manifest_sha256=None,
        created_by="tester", payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA,
        created_at=NOW,
    ))
    _add(session, EvidenceProcessingRevisionRecord(
        evidence_processing_revision_id=complete_revision_id,
        evidence_snapshot_id=snapshot_id, project_id=project_id, subject_id=subject_id,
        review_episode_id=episode_id, manifest_sha256=_sha("complete-manifest"),
        status="ready", is_activatable=True, revision_kind="complete",
        base_processing_revision_id=base_revision_id,
        producer_candidate_id=f"{prefix}-candidate",
        candidate_input_sha256=_sha("candidate-input"),
        completion_manifest_sha256=_sha("completion-manifest"),
        created_by="tester", payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA,
        created_at=NOW,
    ))
    # 已激活审核节点：活动指针对成对（snapshot + complete 修订已就绪后配对）。
    # 用 core UPDATE 设置指针，避免 ORM version_id_col 把 episode revision 自增到 2；
    # 生产激活路径由 EvidenceActivationEventRepository.append_and_switch 原子切换。
    from sqlalchemy import update

    session.execute(
        update(ReviewEpisodeRecord)
        .where(ReviewEpisodeRecord.review_episode_id == episode_id)
        .values(
            active_evidence_snapshot_id=snapshot_id,
            active_evidence_processing_revision_id=complete_revision_id,
        )
    )
    session.expire_all()
    _add(session, EvidenceLocatorArtifactRecord(
        locator_id=locator_id, page_artifact_id=page_artifact_id,
        source_document_version_id=doc_id, page_number=1, source_layer="raw_ocr",
        source_text_sha256=_sha("alt"), target_id="target-1", precision="text_range",
        text_start=0, text_end=5, excerpt="ALT 5", disambiguation="unique_match",
        locator_algorithm_version="v1", authenticity="degraded",
        degradation_reason="text-only", processing_revision_id=complete_revision_id,
        created_at=NOW, payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA,
    ))
    _add(session, EvidenceLocatorArtifactRecord(
        locator_id=locator_id_2, page_artifact_id=page_artifact_id,
        source_document_version_id=doc_id, page_number=1, source_layer="raw_ocr",
        source_text_sha256=_sha("ast"), target_id="target-2", precision="text_range",
        text_start=6, text_end=11, excerpt="AST 3", disambiguation="unique_match",
        locator_algorithm_version="v1", authenticity="degraded",
        degradation_reason="text-only", processing_revision_id=complete_revision_id,
        created_at=NOW, payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA,
    ))
    _add(session, ProcessingRevisionLocatorRecord(
        revision_id=complete_revision_id, position=1, locator_id=locator_id,
    ))
    _add(session, ProcessingRevisionLocatorRecord(
        revision_id=complete_revision_id, position=2, locator_id=locator_id_2,
    ))

    member_contract = EvidenceSnapshotMember(
        member_id=f"{prefix}-member",
        snapshot_id=snapshot_id,
        logical_document_id=f"{prefix}-log",
        source_document_version_id=doc_id,
        origin=SnapshotMemberOrigin.ADDED,
    )
    collection_sha256 = evidence_snapshot_collection_hash(
        members=[(f"{prefix}-log", doc_id)]
    )
    snapshot_record = session.get(EvidenceSnapshotV2Record, snapshot_id)
    snapshot_record.collection_sha256 = collection_sha256
    _bind_payload(
        snapshot_record,
        EvidenceSnapshot(
            evidence_snapshot_id=snapshot_id,
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=episode_id,
            upload_mode=UploadMode.FULL,
            members=[member_contract],
            collection_sha256=collection_sha256,
            status=SnapshotStatus.STAGED,
            created_at=NOW,
            created_by="tester",
        ),
    )
    _bind_payload(
        session.get(EvidenceSnapshotMemberRecord, f"{prefix}-member"),
        member_contract,
    )
    _bind_payload(
        session.get(SourceDocumentVersionV2Record, doc_id),
        SourceDocumentVersion(
            source_document_version_id=doc_id,
            logical_document_id=f"{prefix}-log",
            source_blob_sha256=_sha(f"{prefix}-blob"),
            file_name="f.pdf",
            media_type="application/pdf",
            page_count=1,
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=episode_id,
            version_number=1,
            created_at=NOW,
            created_by="tester",
        ),
    )
    episode_payload_json, episode_payload_sha256 = encode_contract(
        ReviewEpisode(
            review_episode_id=episode_id,
            subject_id=subject_id,
            project_id=project_id,
            rule_set_id=rule_set_id,
            study_phase="phase_iii",
            stage="screening",
            protocol_version_id=protocol_version_id,
            rule_set_revision=1,
            active_evidence_snapshot_id=snapshot_id,
            active_evidence_processing_revision_id=complete_revision_id,
        )
    )
    session.execute(
        update(ReviewEpisodeRecord)
        .where(ReviewEpisodeRecord.review_episode_id == episode_id)
        .values(
            payload_json=episode_payload_json,
            payload_sha256=episode_payload_sha256,
        )
    )
    session.expire_all()
    complete_manifest_sha256 = evidence_processing_manifest_hash(entries=[])
    complete_record = session.get(
        EvidenceProcessingRevisionRecord, complete_revision_id
    )
    complete_record.manifest_sha256 = complete_manifest_sha256
    _bind_payload(
        complete_record,
        CompleteEvidenceProcessingRevision(
            evidence_processing_revision_id=complete_revision_id,
            evidence_snapshot_id=snapshot_id,
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=episode_id,
            base_processing_revision_id=base_revision_id,
            producer_candidate_id=f"{prefix}-candidate",
            candidate_input_sha256=_sha("candidate-input"),
            manifest=[],
            manifest_sha256=complete_manifest_sha256,
            locator_ids=[locator_id, locator_id_2],
            completion_manifest_sha256=_sha("completion-manifest"),
            created_at=NOW,
            created_by="tester",
        ),
    )
    for locator_id_value, source_hash, target_id, start, end, excerpt in (
        (locator_id, _sha("alt"), "target-1", 0, 5, "ALT 5"),
        (locator_id_2, _sha("ast"), "target-2", 6, 11, "AST 3"),
    ):
        locator_record = session.get(EvidenceLocatorArtifactRecord, locator_id_value)
        locator_record.processing_revision_id = None
        _bind_payload(
            locator_record,
            EvidenceLocatorArtifact(
                locator_id=locator_id_value,
                page_artifact_id=page_artifact_id,
                source_document_version_id=doc_id,
                page_number=1,
                source_layer=LocatorSourceLayer.RAW_OCR,
                source_text_sha256=source_hash,
                target_id=target_id,
                precision=LocatorPrecision.TEXT_RANGE,
                text_start=start,
                text_end=end,
                excerpt=excerpt,
                disambiguation=DisambiguationOutcome.UNIQUE_MATCH,
                locator_algorithm_version="v1",
                authenticity=LocatorAuthenticity.DEGRADED,
                degradation_reason="text-only",
                created_at=NOW,
            ),
        )
    _add(session, PromptVersionRecord(
        prompt_version_id=prompt_version_id, node="evidence_normalizer",
        template_sha256=_sha("prompt"), schema_version_id="phase5/facts/v1",
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
    ))
    _add(session, ModelConfigRecord(
        model_config_id=model_config_id, provider="p", model="m",
        reasoning_effort="medium", payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA,
        created_at=NOW,
    ))
    run_authority = _authority({
        "project_id": project_id,
        "subject_id": subject_id,
        "review_episode_id": episode_id,
        "protocol_version_id": protocol_version_id,
        "rule_set_id": rule_set_id,
        "evidence_snapshot_v2_id": snapshot_id,
        "complete_processing_revision_id": complete_revision_id,
    })
    run = FactNormalizationRun(
        run_id=run_id, authority=run_authority,
        idempotency_key=fact_run_idempotency_key(
            authority=run_authority, prompt_version_id=prompt_version_id,
            model_config_id=model_config_id, input_scope_sha256=_sha("input-scope"),
        ),
        prompt_version_id=prompt_version_id, model_config_id=model_config_id,
        input_scope_sha256=_sha("input-scope"),
        status=FactNormalizationRunStatus.SUCCEEDED, created_at=NOW,
        created_by="tester",
    )
    FactNormalizationRunRepository(session).create_or_reuse(run)
    FactNormalizationCallRepository(session).create(FactNormalizationCall(
        call_id=call_id, run_id=run_id, logical_document_id=f"{prefix}-log",
        page_numbers=[1], status=FactCallStatus.SUCCEEDED,
        input_sha256=_sha("call-input"), created_at=NOW,
    ))
    FactNormalizationCandidateRepository(session).create(
        call_id,
        ClinicalFactCandidateV2(
            candidate_id=f"{prefix}-cand",
            run_id=run_id,
            call_id=call_id,
            fact_type="vital_sign",
            polarity=FactPolarity.AFFIRMED,
            asserted_object="血压",
            raw_value="120/80",
            canonical_value="120/80",
            unit="unitless",
            date_range=_date_range(),
            record_time=NOW,
            locator_ids=[locator_id],
            candidate_source_semantics="objective_result",
            assertion_basis=_basis(locator_id),
            model_uncertainty=0.01,
            created_at=NOW,
        ),
    )
    FactNormalizationCandidateRepository(session).create(
        call_id,
        ClinicalEventCandidateV2(
            candidate_id=f"{prefix}-event-cand",
            run_id=run_id,
            call_id=call_id,
            event_type="diagnosis",
            start_range=_date_range(),
            end_range=None,
            duration_status=DurationStatus.ONGOING,
            record_time=NOW,
            fact_candidate_ids=[f"{prefix}-cand"],
            locator_ids=[locator_id],
            candidate_source_semantics="historical_primary",
            model_uncertainty=0.02,
            created_at=NOW,
        ),
    )
    FactNormalizationCandidateRepository(session).create(
        call_id,
        MedicationExposureCandidateV2(
            candidate_id=f"{prefix}-exposure-cand",
            run_id=run_id,
            call_id=call_id,
            medication_name="二甲双胍",
            category="降糖药",
            indication="2 型糖尿病",
            dose="500",
            unit="mg",
            frequency="bid",
            route="口服",
            start_range=_date_range(),
            end_range=None,
            duration_status=DurationStatus.ONGOING,
            record_time=NOW,
            fact_candidate_ids=[f"{prefix}-cand"],
            locator_ids=[locator_id],
            candidate_source_semantics="current_chart",
            model_uncertainty=0.03,
            created_at=NOW,
        ),
    )
    FactGateResultRepository(session).create(FactGateResult(
        gate_result_id=gate_id, run_id=run_id, call_id=call_id,
        candidate_id=f"{prefix}-cand", gate=FactGate.TRANSACTIONAL_PUBLISH,
        outcome=GateOutcome.ACCEPTED, reasons=[], created_at=NOW,
    ))
    FactGateResultRepository(session).create(FactGateResult(
        gate_result_id=event_gate_id, run_id=run_id, call_id=call_id,
        candidate_id=f"{prefix}-event-cand", gate=FactGate.TRANSACTIONAL_PUBLISH,
        outcome=GateOutcome.ACCEPTED, reasons=[], created_at=NOW,
    ))
    FactGateResultRepository(session).create(FactGateResult(
        gate_result_id=exposure_gate_id, run_id=run_id, call_id=call_id,
        candidate_id=f"{prefix}-exposure-cand", gate=FactGate.TRANSACTIONAL_PUBLISH,
        outcome=GateOutcome.ACCEPTED, reasons=[], created_at=NOW,
    ))
    return {
        "project_id": project_id,
        "subject_id": subject_id,
        "review_episode_id": episode_id,
        "protocol_version_id": protocol_version_id,
        "rule_set_id": rule_set_id,
        "evidence_snapshot_v2_id": snapshot_id,
        "complete_processing_revision_id": complete_revision_id,
        "base_processing_revision_id": base_revision_id,
        "locator_id": locator_id,
        "locator_id_2": locator_id_2,
        "run_id": run_id,
        "call_id": call_id,
        "gate_id": gate_id,
        "fact_candidate_id": f"{prefix}-cand",
        "event_gate_id": event_gate_id,
        "exposure_gate_id": exposure_gate_id,
    }


def _seed_chain(
    session, prefix: str, *, fixture_index: int = 0
) -> dict[str, str]:
    """以正式 Phase 4 仓储构造逐页闭合的权威链，再补齐本文件所需候选。"""
    from tests.v2.helpers.phase5_fact_chain import seed_valid_fact_chain

    chain = seed_valid_fact_chain(
        session,
        prefix,
        fixture_index=fixture_index,
        create_run=True,
    )
    fact_candidate_id = f"{prefix}-cand"
    event_candidate_id = f"{prefix}-event-cand"
    exposure_candidate_id = f"{prefix}-exposure-cand"
    gate_id = f"{prefix}-gate"
    event_gate_id = f"{prefix}-event-gate"
    exposure_gate_id = f"{prefix}-exposure-gate"
    locator = session.get(EvidenceLocatorArtifactRecord, chain["locator_id"])
    locator_2 = session.get(EvidenceLocatorArtifactRecord, chain["locator_id_2"])
    assert locator is not None and locator_2 is not None
    _SOURCE_HASH_BY_LOCATOR.update(
        {
            chain["locator_id"]: locator.source_text_sha256,
            chain["locator_id_2"]: locator_2.source_text_sha256,
        }
    )
    _EXCERPT_BY_LOCATOR.update(
        {
            chain["locator_id"]: locator.excerpt or "血压 120/80 mmHg",
            chain["locator_id_2"]: locator_2.excerpt or "血压 120/80 mmHg",
        }
    )
    basis = AssertionBasis(
        asserted_object="血压",
        assertion_text=locator.excerpt or "血压 120/80 mmHg",
        locator_id=chain["locator_id"],
        source_text_sha256=locator.source_text_sha256,
    )
    candidate_repository = FactNormalizationCandidateRepository(session)
    candidate_repository.create(
        chain["call_id"],
        ClinicalFactCandidateV2(
            candidate_id=fact_candidate_id,
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            fact_type="vital_sign",
            polarity=FactPolarity.AFFIRMED,
            asserted_object="血压",
            raw_value="120/80",
            canonical_value="120/80",
            unit="unitless",
            date_range=_date_range(),
            record_time=NOW,
            locator_ids=[chain["locator_id"]],
            candidate_source_semantics="objective_result",
            assertion_basis=basis,
            model_uncertainty=0.01,
            created_at=NOW,
        ),
    )
    candidate_repository.create(
        chain["call_id"],
        ClinicalEventCandidateV2(
            candidate_id=event_candidate_id,
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            event_type="diagnosis",
            start_range=_date_range(),
            end_range=None,
            duration_status=DurationStatus.ONGOING,
            record_time=NOW,
            fact_candidate_ids=[fact_candidate_id],
            locator_ids=[chain["locator_id"]],
            candidate_source_semantics="historical_primary",
            model_uncertainty=0.02,
            created_at=NOW,
        ),
    )
    candidate_repository.create(
        chain["call_id"],
        MedicationExposureCandidateV2(
            candidate_id=exposure_candidate_id,
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            medication_name="二甲双胍",
            category="降糖药",
            indication="2 型糖尿病",
            dose="500",
            unit="mg",
            frequency="bid",
            route="口服",
            start_range=_date_range(),
            end_range=None,
            duration_status=DurationStatus.ONGOING,
            record_time=NOW,
            fact_candidate_ids=[fact_candidate_id],
            locator_ids=[chain["locator_id"]],
            candidate_source_semantics="current_chart",
            model_uncertainty=0.03,
            created_at=NOW,
        ),
    )
    gate_repository = FactGateResultRepository(session)
    for candidate_id, candidate_gate_id in (
        (fact_candidate_id, gate_id),
        (event_candidate_id, event_gate_id),
        (exposure_candidate_id, exposure_gate_id),
    ):
        gate_repository.create(
            FactGateResult(
                gate_result_id=candidate_gate_id,
                run_id=chain["run_id"],
                call_id=chain["call_id"],
                candidate_id=candidate_id,
                gate=FactGate.TRANSACTIONAL_PUBLISH,
                outcome=GateOutcome.ACCEPTED,
                reasons=[],
                created_at=NOW,
            )
        )
    return {
        **chain,
        "gate_id": gate_id,
        "fact_candidate_id": fact_candidate_id,
        "event_candidate_id": event_candidate_id,
        "event_gate_id": event_gate_id,
        "exposure_gate_id": exposure_gate_id,
    }


def _authority(ids: dict[str, str], **overrides) -> FactAuthority:
    base = {
        "project_id": ids["project_id"],
        "subject_id": ids["subject_id"],
        "review_episode_id": ids["review_episode_id"],
        "episode_revision": 1,
        "protocol_version_id": ids["protocol_version_id"],
        "rule_set_id": ids["rule_set_id"],
        "rule_set_revision": 1,
        "evidence_snapshot_v2_id": ids["evidence_snapshot_v2_id"],
        "complete_processing_revision_id": ids["complete_processing_revision_id"],
    }
    base.update(overrides)
    return FactAuthority(**base)


def _date_range():
    return PartialDateRange(
        source_text="2026-03-01",
        precision=DatePrecision.DAY,
        lower_bound=date(2026, 3, 1),
        upper_bound=date(2026, 3, 1),
    )


def _same_date_range_in_chinese():
    return PartialDateRange(
        source_text="2026年3月1日",
        precision=DatePrecision.DAY,
        lower_bound=date(2026, 3, 1),
        upper_bound=date(2026, 3, 1),
    )


def _basis(locator_id: str) -> AssertionBasis:
    return AssertionBasis(
        asserted_object="血压",
        assertion_text=_EXCERPT_BY_LOCATOR.get(locator_id, "血压 120/80 mmHg"),
        locator_id=locator_id,
        source_text_sha256=_SOURCE_HASH_BY_LOCATOR.get(locator_id, _sha("alt")),
    )


def _fact(ids, **overrides) -> ClinicalFactV2:
    base = {
        "fact_id": f"{ids['run_id']}-fact",
        "run_id": ids["run_id"],
        "gate_id": ids["gate_id"],
        "authority": _authority(ids),
        "fact_type": "vital_sign",
        "polarity": FactPolarity.AFFIRMED,
        "asserted_object": "血压",
        "value": "120/80",
        "unit": "unitless",
        "source_strength": SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        "date_range": _date_range(),
        "record_time": NOW,
        "locator_ids": [ids["locator_id"]],
        "assertion_basis": _basis(ids["locator_id"]),
        "revision": 1,
        "created_at": NOW,
    }
    base.update(overrides)
    if "locator_ids" in overrides and "assertion_basis" not in overrides:
        base["assertion_basis"] = _basis(base["locator_ids"][0])
    if "stable_identity" not in overrides:
        base["stable_identity"] = clinical_fact_stable_identity(
            authority=base["authority"], fact_type=base["fact_type"],
            profile_lane=base.get("profile_lane", ProfileLane.EVIDENCE_QUALITY),
            asserted_object=base["asserted_object"],
            polarity=base["polarity"], value=base["value"], unit=base["unit"],
            date_range=base["date_range"],
        )
    return ClinicalFactV2(**base)


def _event(ids, **overrides) -> ClinicalEventV2:
    base = {
        "event_id": f"{ids['run_id']}-event",
        "run_id": ids["run_id"],
        "gate_id": ids["event_gate_id"],
        "authority": _authority(ids),
        "event_type": "diagnosis",
        "start_range": _date_range(),
        "end_range": None,
        "duration_status": DurationStatus.ONGOING,
        "record_time": NOW,
        "fact_ids": [f"{ids['run_id']}-fact"],
        "referenced_fact_objects": ["vital_sign:血压"],
        "locator_ids": [ids["locator_id"]],
        "source_strength": SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        "revision": 1,
        "created_at": NOW,
    }
    base.update(overrides)
    if "stable_identity" not in overrides:
        base["stable_identity"] = clinical_event_stable_identity(
            authority=base["authority"], event_type=base["event_type"],
            profile_lane=base.get("profile_lane", ProfileLane.EVIDENCE_QUALITY),
            referenced_fact_objects=base["referenced_fact_objects"],
            start_range=base["start_range"], end_range=base["end_range"],
            duration_status=base["duration_status"],
        )
    return ClinicalEventV2(**base)


def _exposure(ids, **overrides) -> MedicationExposureV2:
    base = {
        "exposure_id": f"{ids['run_id']}-exposure",
        "run_id": ids["run_id"],
        "gate_id": ids["exposure_gate_id"],
        "authority": _authority(ids),
        "medication_name": "二甲双胍",
        "category": "降糖药",
        "indication": "2 型糖尿病",
        "dose": "500", "unit": "mg", "frequency": "bid", "route": "口服",
        "start_range": _date_range(),
        "end_range": None,
        "duration_status": DurationStatus.ONGOING,
        "record_time": NOW,
        "fact_ids": [f"{ids['run_id']}-fact"],
        "locator_ids": [ids["locator_id"]],
        "source_strength": SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        "revision": 1,
        "created_at": NOW,
    }
    base.update(overrides)
    if "stable_identity" not in overrides:
        base["stable_identity"] = medication_exposure_stable_identity(
            authority=base["authority"], medication_name=base["medication_name"],
            category=base["category"], indication=base["indication"],
            dose=base["dose"], unit=base["unit"], frequency=base["frequency"],
            route=base["route"], start_range=base["start_range"],
            end_range=base["end_range"], duration_status=base["duration_status"],
        )
    return MedicationExposureV2(**base)


@pytest.fixture
def chain(session):
    """head 库会话 + 已激活权威链；测试回滚。"""
    return _seed_chain(session, "t1")


@pytest.fixture
def chain_other(session):
    """第二条独立审核节点链（跨节点定位引用测试用）。"""
    return _seed_chain(session, "t2", fixture_index=1)


# ------------------------------------------------------------- 权威元组拒绝


def test_rejects_legacy_snapshot_id(chain, session):
    with pytest.raises(FactAuthorityError, match="legacy"):
        ClinicalFactV2Repository(session).create(
            _fact(chain, authority=_authority(chain, evidence_snapshot_v2_id="legacy-snap"))
        )


def test_rejects_missing_snapshot_id(chain, session):
    with pytest.raises(FactAuthorityError, match="不存在于 evidence_snapshots_v2"):
        ClinicalFactV2Repository(session).create(
            _fact(chain, authority=_authority(chain, evidence_snapshot_v2_id="nope"))
        )


def test_rejects_inactive_unpaired_episode(chain, session):
    episode = session.get(ReviewEpisodeRecord, chain["review_episode_id"])
    _update_episode(
        session,
        episode,
        active_evidence_snapshot_id=None,
        active_evidence_processing_revision_id=None,
    )
    session.flush()
    with pytest.raises(FactAuthorityError, match="未激活|未配对"):
        ClinicalFactV2Repository(session).create(_fact(chain))


def test_rejects_non_active_snapshot_pointer(chain, session):
    # 审核节点活动快照指向另一现存快照（权威元组仍引用原快照）-> 非活动版本拒绝。
    from app.storage.evidence_models import EvidenceSnapshotV2Record as Snap

    _add(session, Snap(
        evidence_snapshot_id="other-active-snapshot",
        project_id=chain["project_id"], subject_id=chain["subject_id"],
        review_episode_id=chain["review_episode_id"], upload_mode="full",
        prior_snapshot_id=None, comparison_snapshot_id=None,
        collection_sha256=_sha("other-active"), created_by="tester",
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
    ))
    episode = session.get(ReviewEpisodeRecord, chain["review_episode_id"])
    _update_episode(
        session,
        episode,
        active_evidence_snapshot_id="other-active-snapshot",
    )
    session.flush()
    with pytest.raises(FactAuthorityError, match="不是审核节点当前活动快照"):
        ClinicalFactV2Repository(session).create(_fact(chain))


def test_rejects_non_active_processing_revision_pointer(chain, session):
    episode = session.get(ReviewEpisodeRecord, chain["review_episode_id"])
    _update_episode(
        session,
        episode,
        active_evidence_processing_revision_id=chain["base_processing_revision_id"],
    )
    session.flush()
    with pytest.raises(FactAuthorityError, match="不是审核节点当前活动处理修订"):
        ClinicalFactV2Repository(session).create(_fact(chain))


def test_rejects_stale_episode_revision(chain, session):
    episode = session.get(ReviewEpisodeRecord, chain["review_episode_id"])
    _update_episode(session, episode, revision=2)
    session.flush()
    with pytest.raises(FactAuthorityError, match="陈旧审核节点修订"):
        ClinicalFactV2Repository(session).create(_fact(chain))


def test_rejects_scope_mismatch(chain, session):
    with pytest.raises(FactAuthorityError, match="作用域"):
        ClinicalFactV2Repository(session).create(
            _fact(chain, authority=_authority(chain, project_id="foreign-project"))
        )


def test_rejects_non_complete_processing_revision(chain, session):
    # 审核节点活动指针与权威元组都指向 base 修订（本不应发生的指针状态）：
    # 指针相等校验通过后，base 修订必须被完整修订门禁拒绝。
    from sqlalchemy import update

    session.execute(
        update(ReviewEpisodeRecord)
        .where(ReviewEpisodeRecord.review_episode_id == chain["review_episode_id"])
        .values(active_evidence_processing_revision_id=chain["base_processing_revision_id"])
    )
    session.expire_all()
    episode = session.get(ReviewEpisodeRecord, chain["review_episode_id"])
    _update_episode(
        session,
        episode,
        active_evidence_processing_revision_id=chain["base_processing_revision_id"],
    )
    with pytest.raises(FactAuthorityError, match="闭包不完整"):
        ClinicalFactV2Repository(session).create(
            _fact(chain, authority=_authority(
                chain, complete_processing_revision_id=chain["base_processing_revision_id"]
            ))
        )


def test_rejects_complete_revision_wrong_snapshot(chain, session):
    # 完整处理修订绑定另一快照（同审核节点）-> 与权威快照不一致拒绝。
    from app.storage.evidence_models import EvidenceSnapshotV2Record as Snap

    _add(session, Snap(
        evidence_snapshot_id="other-snapshot",
        project_id=chain["project_id"], subject_id=chain["subject_id"],
        review_episode_id=chain["review_episode_id"], upload_mode="full",
        prior_snapshot_id=None, comparison_snapshot_id=None,
        collection_sha256=_sha("other-collection"), created_by="tester",
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
    ))
    complete = session.get(
        EvidenceProcessingRevisionRecord, chain["complete_processing_revision_id"]
    )
    complete.evidence_snapshot_id = "other-snapshot"
    _update_payload(
        complete,
        CompleteEvidenceProcessingRevision,
        evidence_snapshot_id="other-snapshot",
    )
    session.flush()
    with pytest.raises(FactAuthorityError, match="闭包不完整"):
        ClinicalFactV2Repository(session).create(_fact(chain))


# ------------------------------------------------------------- 定位引用拒绝


def test_rejects_cross_episode_locator(chain, chain_other, session):
    with pytest.raises(FactLocatorReferenceError, match="跨审核节点"):
        ClinicalFactV2Repository(session).create(
            _fact(chain, locator_ids=[chain_other["locator_id"]])
        )


def test_rejects_locator_outside_snapshot_members(chain, session):
    member = session.execute(
        select(EvidenceSnapshotMemberRecord).where(
            EvidenceSnapshotMemberRecord.snapshot_id
            == chain["evidence_snapshot_v2_id"]
        )
    ).scalars().first()
    session.delete(member)
    session.flush()
    with pytest.raises(FactAuthorityError, match="闭包不完整"):
        ClinicalFactV2Repository(session).create(_fact(chain))


def test_rejects_locator_processing_revision_mirror_drift(chain, session):
    locator = session.get(EvidenceLocatorArtifactRecord, chain["locator_id"])
    locator.processing_revision_id = chain["base_processing_revision_id"]
    session.flush()
    with pytest.raises(FactAuthorityError, match="闭包不完整"):
        ClinicalFactV2Repository(session).create(_fact(chain))


def test_rejects_locator_not_in_complete_revision_closure(chain, session):
    membership = session.execute(
        select(ProcessingRevisionLocatorRecord).where(
            ProcessingRevisionLocatorRecord.revision_id
            == chain["complete_processing_revision_id"],
            ProcessingRevisionLocatorRecord.locator_id == chain["locator_id"],
        )
    ).scalar_one()
    session.delete(membership)
    session.flush()
    with pytest.raises(FactAuthorityError, match="闭包不完整"):
        ClinicalFactV2Repository(session).create(_fact(chain))


def test_rejects_complete_revision_with_falsified_empty_page_manifest(
    chain, session
):
    """有快照成员的完整修订不能通过伪造空页清单绕过逐页闭包。"""
    complete = session.get(
        EvidenceProcessingRevisionRecord,
        chain["complete_processing_revision_id"],
    )
    empty_manifest_hash = evidence_processing_manifest_hash(entries=[])
    complete.manifest_sha256 = empty_manifest_hash
    _update_payload(
        complete,
        CompleteEvidenceProcessingRevision,
        manifest=[],
        manifest_sha256=empty_manifest_hash,
    )
    session.flush()

    with pytest.raises(FactAuthorityError, match="闭包不完整"):
        ClinicalFactV2Repository(session).create(_fact(chain))


def test_rejects_unknown_locator(chain, session):
    with pytest.raises(FactLocatorReferenceError, match="不存在"):
        ClinicalFactV2Repository(session).create(
            _fact(chain, locator_ids=["no-such-locator"])
        )


def test_rejects_assertion_locator_outside_fact_locators(chain, session):
    with pytest.raises(ValueError, match="断言依据定位"):
        _fact(chain, assertion_basis=_basis("other-locator"))


def test_rejects_locator_source_hash_mirror_drift(chain, session):
    locator = session.get(EvidenceLocatorArtifactRecord, chain["locator_id"])
    locator.source_text_sha256 = _sha("other-source-text")
    session.flush()
    with pytest.raises(FactAuthorityError, match="闭包不完整"):
        ClinicalFactV2Repository(session).create(_fact(chain))


# ------------------------------------------------------------- 跨实体拒绝


def test_rejects_event_fact_of_different_authority(chain, chain_other, session):
    ClinicalFactV2Repository(session).create(_fact(chain))
    ClinicalFactV2Repository(session).create(_fact(chain_other))
    # 事件权威元组为 t1，但引用 t2 的事实 -> 跨实体拒绝。
    with pytest.raises(FactCrossEntityError, match="同一不可变权威元组"):
        ClinicalEventV2Repository(session).create(
            _event(chain, fact_ids=[f"{chain_other['run_id']}-fact"])
        )


def test_rejects_event_locator_not_in_fact_closure(chain, session):
    ClinicalFactV2Repository(session).create(_fact(chain))
    candidate_id = "event-outside-fact-closure"
    gate_id = "event-outside-fact-closure-gate"
    FactNormalizationCandidateRepository(session).create(
        chain["call_id"],
        ClinicalEventCandidateV2(
            candidate_id=candidate_id,
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            event_type="diagnosis",
            start_range=_date_range(),
            end_range=None,
            duration_status=DurationStatus.ONGOING,
            record_time=NOW,
            fact_candidate_ids=[chain["fact_candidate_id"]],
            locator_ids=[chain["locator_id_2"]],
            candidate_source_semantics="historical_primary",
            model_uncertainty=0.02,
            created_at=NOW,
        ),
    )
    FactGateResultRepository(session).create(FactGateResult(
        gate_result_id=gate_id,
        run_id=chain["run_id"],
        call_id=chain["call_id"],
        candidate_id=candidate_id,
        gate=FactGate.TRANSACTIONAL_PUBLISH,
        outcome=GateOutcome.ACCEPTED,
        reasons=[],
        created_at=NOW,
    ))
    # 事件定位引用同链第二个 locator（通过权威校验，但不在其事实定位闭包）。
    with pytest.raises(FactLocatorReferenceError, match="不属于其引用事实的定位闭包"):
        ClinicalEventV2Repository(session).create(
            _event(
                chain,
                gate_id=gate_id,
                locator_ids=[chain["locator_id_2"]],
            )
        )


def test_rejects_gate_not_belonging_to_run(chain, chain_other, session):
    with pytest.raises(Phase5RepositoryError, match="不属于运行"):
        ClinicalFactV2Repository(session).create(
            _fact(chain_other, gate_id=chain["gate_id"])
        )


def test_gate_results_create_many_preserves_run_and_candidate_links(chain, session):
    results = [
        FactGateResult(
            gate_result_id=f"batch-gate-{index}",
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            candidate_id=candidate_id,
            gate=FactGate.CONTRACT_AND_ENUM,
            outcome=GateOutcome.ACCEPTED,
            reasons=[],
            created_at=NOW,
        )
        for index, candidate_id in enumerate(
            (chain["fact_candidate_id"], chain["event_candidate_id"]),
            start=1,
        )
    ]

    persisted = FactGateResultRepository(session).create_many(results)

    assert persisted == results
    assert [
        FactGateResultRepository(session).get(item.gate_result_id)
        for item in results
    ] == results


def test_rejects_publish_run_authority_mismatch(chain, chain_other, session):
    with pytest.raises(FactCrossEntityError, match="不可变权威元组"):
        ClinicalFactV2Repository(session).create(
            _fact(
                chain_other,
                run_id=chain["run_id"],
                gate_id=chain["gate_id"],
            )
        )


@pytest.mark.parametrize(
    ("gate", "outcome", "reasons"),
    [
        (FactGate.VALUE_UNIT_DATE_SOURCE, GateOutcome.ACCEPTED, []),
        (FactGate.TRANSACTIONAL_PUBLISH, GateOutcome.REJECTED, ["未通过"]),
    ],
)
def test_rejects_nonfinal_or_unaccepted_publish_gate(
    chain, session, gate, outcome, reasons
):
    gate_id = f"alternate-{gate.value}-{outcome.value}"
    original = FactNormalizationCandidateRepository(session).get(
        chain["fact_candidate_id"]
    )
    alternate = original.model_copy(
        update={"candidate_id": "alternate-candidate"}
    )
    FactNormalizationCandidateRepository(session).create(
        chain["call_id"], alternate
    )
    FactGateResultRepository(session).create(FactGateResult(
        gate_result_id=gate_id,
        run_id=chain["run_id"],
        call_id=chain["call_id"],
        candidate_id="alternate-candidate",
        gate=gate,
        outcome=outcome,
        reasons=reasons,
        created_at=NOW,
    ))
    with pytest.raises(Phase5RepositoryError, match="最终事务发布门禁"):
        ClinicalFactV2Repository(session).create(
            _fact(chain, gate_id=gate_id)
        )


def test_rejects_event_fact_with_partial_authority_drift(chain, session):
    ClinicalFactV2Repository(session).create(_fact(chain))
    row = session.get(ClinicalFactV2Record, f"{chain['run_id']}-fact")
    row.episode_revision = 2
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="episode_revision"):
        ClinicalEventV2Repository(session).create(_event(chain))


def test_rejects_event_declared_fact_objects_different_from_published_facts(chain, session):
    ClinicalFactV2Repository(session).create(_fact(chain))
    with pytest.raises(FactCrossEntityError, match="引用事实对象"):
        ClinicalEventV2Repository(session).create(
            _event(chain, referenced_fact_objects=["vital_sign:体温"])
        )


def test_rejects_publish_semantics_different_from_gated_candidate(chain, session):
    with pytest.raises(FactCrossEntityError, match="候选语义"):
        ClinicalFactV2Repository(session).create(_fact(chain, value="130/90"))


# ------------------------------------------------------------- revision 链


def test_fact_revision_chain_append_only(chain, session):
    repo = ClinicalFactV2Repository(session)
    repo.create(_fact(chain, revision=1))
    # 链头 1 -> 允许追加 revision 2。
    repo.create(_fact(chain, fact_id="fact-rev2", revision=2))
    # 回退/跳号拒绝（当前链头为 2）。
    with pytest.raises(FactRevisionChainError, match="链头 2 \\+ 1"):
        repo.create(_fact(chain, fact_id="fact-dup", revision=1))
    with pytest.raises(FactRevisionChainError, match="链头 2 \\+ 1"):
        repo.create(_fact(chain, fact_id="fact-skip", revision=4))


def test_fact_revision_chain_must_start_at_one(chain, session):
    with pytest.raises(FactRevisionChainError, match="首个 revision 必须为 1"):
        ClinicalFactV2Repository(session).create(_fact(chain, revision=2))


# ------------------------------------------------------------- 追加写回读


def test_run_idempotency_key_reuse_returns_original(chain, session):
    run = FactNormalizationRunRepository(session).get(chain["run_id"])
    # 重复提交相同幂等键（不同 run_id）应返回原运行。
    repo = FactNormalizationRunRepository(session)
    duplicate = FactNormalizationRun(
        run_id="run-dup",
        authority=run.authority,
        idempotency_key=fact_run_idempotency_key(
            authority=run.authority, prompt_version_id=run.prompt_version_id,
            model_config_id=run.model_config_id,
            input_scope_sha256=run.input_scope_sha256,
        ),
        prompt_version_id=run.prompt_version_id,
        model_config_id=run.model_config_id,
        input_scope_sha256=run.input_scope_sha256,
        status=FactNormalizationRunStatus.RUNNING,
        created_at=NOW,
        created_by="tester",
    )
    reused = repo.create_or_reuse(duplicate)
    assert reused.run_id == chain["run_id"]
    assert session.get(FactNormalizationRunRecord, "run-dup") is None


def test_candidate_roundtrip_preserves_complete_contract(chain, session):
    candidate = FactNormalizationCandidateRepository(session).get(
        chain["fact_candidate_id"]
    )
    assert isinstance(candidate, ClinicalFactCandidateV2)
    assert candidate.run_id == chain["run_id"]
    assert candidate.locator_ids == [chain["locator_id"]]
    assert candidate.assertion_basis == _basis(chain["locator_id"])


def test_candidate_roundtrip_preserves_profile_lane(chain, session):
    repository = FactNormalizationCandidateRepository(session)
    original = repository.get(chain["fact_candidate_id"])
    candidate = original.model_copy(
        update={
            "candidate_id": "profile-lane-candidate",
            "profile_lane": ProfileLane.MEDICAL_HISTORY,
        }
    )
    repository.create(chain["call_id"], candidate)

    assert repository.get(candidate.candidate_id).profile_lane == ProfileLane.MEDICAL_HISTORY


def test_candidate_payload_hash_drift_is_rejected(chain, session):
    row = session.get(
        FactNormalizationCandidateRecord, chain["fact_candidate_id"]
    )
    row.payload_json = '{"tampered": true}'
    session.flush()
    from app.storage.codecs import PersistedContractInvalid

    with pytest.raises(PersistedContractInvalid):
        FactNormalizationCandidateRepository(session).get(
            chain["fact_candidate_id"]
        )


def test_candidate_call_id_mirror_drift_is_rejected(chain, session):
    second_call = FactNormalizationCall(
        call_id="candidate-mirror-call",
        run_id=chain["run_id"],
        logical_document_id="candidate-mirror-document",
        page_numbers=[1],
        status=FactCallStatus.SUCCEEDED,
        input_sha256=_sha("candidate-mirror-input"),
        created_at=NOW,
    )
    FactNormalizationCallRepository(session).create(second_call)
    candidate = FactNormalizationCandidateRepository(session).get(
        chain["fact_candidate_id"]
    ).model_copy(
        update={
            "candidate_id": "candidate-call-mirror",
            "call_id": second_call.call_id,
        }
    )
    FactNormalizationCandidateRepository(session).create(
        second_call.call_id, candidate
    )
    row = session.get(FactNormalizationCandidateRecord, candidate.candidate_id)
    row.call_id = chain["call_id"]
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="call_id"):
        FactNormalizationCandidateRepository(session).get(candidate.candidate_id)


def test_run_and_run_scoped_lists_decode_before_filtering(
    chain, chain_other, session
):
    run_row = session.get(FactNormalizationRunRecord, chain["run_id"])
    run_row.review_episode_id = chain_other["review_episode_id"]
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="review_episode_id"):
        FactNormalizationRunRepository(session).list_by_episode(
            chain["review_episode_id"]
        )
    run_row.review_episode_id = chain["review_episode_id"]
    session.flush()

    extra_call = FactNormalizationCall(
        call_id="list-mirror-call",
        run_id=chain["run_id"],
        logical_document_id="list-mirror-document",
        page_numbers=[1],
        status=FactCallStatus.SUCCEEDED,
        input_sha256=_sha("list-mirror-input"),
        created_at=NOW,
    )
    FactNormalizationCallRepository(session).create(extra_call)
    call_row = session.get(FactNormalizationCallRecord, extra_call.call_id)
    call_row.run_id = chain_other["run_id"]
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="run_id"):
        FactNormalizationCallRepository(session).list_by_run(chain["run_id"])
    gate_row = session.get(FactGateResultRecord, chain["gate_id"])
    gate_row.reasons_json = ["漂移"]
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="reasons_json"):
        FactGateResultRepository(session).list_by_run(chain["run_id"])


def test_published_lists_decode_before_filtering(chain, chain_other, session):
    ClinicalFactV2Repository(session).create(_fact(chain))
    ClinicalEventV2Repository(session).create(_event(chain))
    MedicationExposureV2Repository(session).create(_exposure(chain))

    cases = (
        (
            session.get(ClinicalFactV2Record, f"{chain['run_id']}-fact"),
            ClinicalFactV2Repository(session).list_by_episode,
        ),
        (
            session.get(ClinicalEventV2Record, f"{chain['run_id']}-event"),
            ClinicalEventV2Repository(session).list_by_episode,
        ),
        (
            session.get(
                MedicationExposureV2Record, f"{chain['run_id']}-exposure"
            ),
            MedicationExposureV2Repository(session).list_by_episode,
        ),
    )
    for row, list_by_episode in cases:
        row.review_episode_id = chain_other["review_episode_id"]
        session.flush()
        with pytest.raises(PersistedContractInvalid, match="review_episode_id"):
            list_by_episode(chain["review_episode_id"])
        row.review_episode_id = chain["review_episode_id"]
        session.flush()


def test_revision_chain_scan_rejects_hidden_stable_identity_drift(chain, session):
    repository = ClinicalFactV2Repository(session)
    first = _fact(chain)
    repository.create(first)
    row = session.get(ClinicalFactV2Record, first.fact_id)
    row.stable_identity = "b" * 64
    session.flush()

    with pytest.raises(PersistedContractInvalid, match="stable_identity"):
        repository.create(
            _fact(chain, fact_id="fact-revision-2", revision=2)
        )


def test_candidate_call_must_belong_to_same_run(chain, chain_other, session):
    candidate = FactNormalizationCandidateRepository(session).get(
        chain_other["fact_candidate_id"]
    ).model_copy(update={"candidate_id": "wrong-call-candidate"})
    with pytest.raises(Phase5RepositoryError, match="call_id"):
        FactNormalizationCandidateRepository(session).create(
            chain["call_id"], candidate
        )


def test_candidate_call_and_run_provenance_is_physically_bound(
    chain, chain_other, session
):
    session.add(
        FactNormalizationCandidateRecord(
            candidate_id="cross-run-candidate-row",
            run_id=chain["run_id"],
            call_id=chain_other["call_id"],
            candidate_kind="fact",
            payload_json=_PAYLOAD,
            payload_sha256=_PAYLOAD_SHA,
            created_at=NOW,
        )
    )
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        session.flush()


def test_locator_link_requires_real_typed_parent(chain, session):
    session.add(
        FactEvidenceLocatorLinkRecord(
            entity_kind="fact",
            entity_id="missing-fact",
            fact_id="missing-fact",
            position=1,
            locator_id=chain["locator_id"],
        )
    )
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        session.flush()


def test_fact_roundtrip_preserves_authority_identity_and_locators(chain, session):
    repo = ClinicalFactV2Repository(session)
    repo.create(_fact(chain))
    got = repo.get(f"{chain['run_id']}-fact")
    assert got.authority == _authority(chain)
    assert got.stable_identity == _fact(chain).stable_identity
    assert got.asserted_object == "血压"
    assert got.locator_ids == [chain["locator_id"]]
    assert got.assertion_basis.locator_id == chain["locator_id"]
    assert got.value == "120/80"
    assert got.date_range.lower_bound == date(2026, 3, 1)


def test_published_fact_roundtrip_preserves_profile_lane(chain, session):
    repository = ClinicalFactV2Repository(session)
    fact = _fact(chain, profile_lane=ProfileLane.TEST_EXAM_SCORE)
    repository.create(fact)

    assert repository.get(fact.fact_id).profile_lane == ProfileLane.TEST_EXAM_SCORE


def test_fact_asserted_object_column_payload_mirror_drift_rejected(chain, session):
    repo = ClinicalFactV2Repository(session)
    repo.create(_fact(chain))
    row = session.get(ClinicalFactV2Record, f"{chain['run_id']}-fact")
    row.assertion_object = "体温"
    session.flush()

    with pytest.raises(PersistedContractInvalid, match="assertion_object"):
        repo.get(f"{chain['run_id']}-fact")


def test_fact_payload_locator_mirror_drift_rejected(chain, chain_other, session):
    """链接表与 payload 定位不一致 -> 读取拒绝（不静默返回漂移真相）。"""
    repo = ClinicalFactV2Repository(session)
    repo.create(_fact(chain))
    link = session.execute(
        select(FactEvidenceLocatorLinkRecord).where(
            FactEvidenceLocatorLinkRecord.entity_kind == "fact",
            FactEvidenceLocatorLinkRecord.entity_id == f"{chain['run_id']}-fact",
        )
    ).scalars().first()
    link.locator_id = chain_other["locator_id"]
    session.flush()
    from app.storage.codecs import PersistedContractInvalid

    with pytest.raises(PersistedContractInvalid):
        repo.get(f"{chain['run_id']}-fact")


def test_event_roundtrip(chain, session):
    ClinicalFactV2Repository(session).create(_fact(chain))
    repo = ClinicalEventV2Repository(session)
    repo.create(_event(chain))
    got = repo.get(f"{chain['run_id']}-event")
    assert got.fact_ids == [f"{chain['run_id']}-fact"]
    assert got.referenced_fact_objects == ["vital_sign:血压"]
    assert got.locator_ids == [chain["locator_id"]]
    assert got.authority == _authority(chain)


def test_fact_publication_accepts_equivalent_date_with_different_source_text(chain, session):
    got = ClinicalFactV2Repository(session).create(
        _fact(chain, date_range=_same_date_range_in_chinese())
    )

    assert got.date_range.source_text == "2026年3月1日"


def test_event_publication_accepts_equivalent_date_with_different_source_text(chain, session):
    ClinicalFactV2Repository(session).create(_fact(chain))
    got = ClinicalEventV2Repository(session).create(
        _event(chain, start_range=_same_date_range_in_chinese())
    )

    assert got.start_range.source_text == "2026年3月1日"


def test_event_payload_spoofed_fact_objects_rejected_on_read(chain, session):
    ClinicalFactV2Repository(session).create(_fact(chain))
    repo = ClinicalEventV2Repository(session)
    repo.create(_event(chain))
    spoofed = _event(chain, referenced_fact_objects=["vital_sign:体温"])
    payload_json, payload_sha256 = encode_contract(spoofed)
    row = session.get(ClinicalEventV2Record, f"{chain['run_id']}-event")
    row.payload_json = payload_json
    row.payload_sha256 = payload_sha256
    row.stable_identity = spoofed.stable_identity
    session.flush()

    with pytest.raises(PersistedContractInvalid, match="引用事实对象"):
        repo.get(f"{chain['run_id']}-event")


def test_exposure_roundtrip(chain, session):
    ClinicalFactV2Repository(session).create(_fact(chain))
    repo = MedicationExposureV2Repository(session)
    repo.create(_exposure(chain))
    got = repo.get(f"{chain['run_id']}-exposure")
    assert got.medication_name == "二甲双胍"
    assert got.duration_status == DurationStatus.ONGOING
    assert got.record_time == NOW
    assert got.locator_ids == [chain["locator_id"]]


def test_exposure_publication_accepts_equivalent_date_with_different_source_text(chain, session):
    ClinicalFactV2Repository(session).create(_fact(chain))
    got = MedicationExposureV2Repository(session).create(
        _exposure(chain, start_range=_same_date_range_in_chinese())
    )

    assert got.start_range.source_text == "2026年3月1日"


def _create_and_assert_fact_conflict_group(chain, session):
    repo = ClinicalFactV2Repository(session)
    repo.create(_fact(chain, fact_id="fact-a"))
    second_candidate = ClinicalFactCandidateV2(
        candidate_id="second-fact-candidate",
        run_id=chain["run_id"],
        call_id=chain["call_id"],
        fact_type="vital_sign",
        polarity=FactPolarity.AFFIRMED,
        asserted_object="血压",
        raw_value="90/60",
        canonical_value="90/60",
        unit="unitless",
        date_range=_date_range(),
        record_time=NOW,
        locator_ids=[chain["locator_id"]],
        candidate_source_semantics="objective_result",
        assertion_basis=_basis(chain["locator_id"]),
        model_uncertainty=0.01,
        created_at=NOW,
    )
    FactNormalizationCandidateRepository(session).create(
        chain["call_id"], second_candidate
    )
    FactGateResultRepository(session).create(FactGateResult(
        gate_result_id="second-fact-gate",
        run_id=chain["run_id"],
        call_id=chain["call_id"],
        candidate_id=second_candidate.candidate_id,
        gate=FactGate.TRANSACTIONAL_PUBLISH,
        outcome=GateOutcome.ACCEPTED,
        reasons=[],
        created_at=NOW,
    ))
    repo.create(
        _fact(
            chain,
            fact_id="fact-b",
            gate_id="second-fact-gate",
            value="90/60",
        )
    )
    group = ClinicalConflictGroupV2(
        conflict_group_id="conflict-1",
        run_id=chain["run_id"],
        gate_id=chain["gate_id"],
        authority=_authority(chain),
        fact_ids=["fact-a", "fact-b"],
        locator_ids=[chain["locator_id"]],
        created_at=NOW,
    )
    crepo = ClinicalConflictGroupV2Repository(session)
    crepo.create(group)
    got = crepo.get("conflict-1")
    assert got.fact_ids == ["fact-a", "fact-b"]
    assert got.locator_ids == [chain["locator_id"]]
    assert got.resolution_revision == 0


def test_conflict_group_roundtrip(chain, session):
    _create_and_assert_fact_conflict_group(chain, session)


def test_legacy_fact_conflict_payload_reads_after_member_kind_migration(chain, session):
    """0016 回填成员类型后，0013 旧事实冲突正文仍须可回放。"""
    _create_and_assert_fact_conflict_group(chain, session)
    row = session.get(ClinicalConflictGroupV2Record, "conflict-1")
    assert row is not None
    payload = json.loads(row.payload_json)
    payload.pop("member_kind")
    payload.pop("event_ids")
    payload.pop("exposure_ids")
    row.payload_json = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    row.payload_sha256 = hashlib.sha256(row.payload_json.encode()).hexdigest()
    session.flush()
    session.expire_all()

    got = ClinicalConflictGroupV2Repository(session).get("conflict-1")
    assert got.member_kind == "fact"
    assert got.fact_ids == ["fact-a", "fact-b"]
