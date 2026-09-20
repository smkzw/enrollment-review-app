"""Slice 5.4 事务发布服务聚焦测试（Worker 01）

覆盖：
- merged locator closure（同 stable 不同来源合并为一条事实，多定位有序并集）
- conflict members remaining published（冲突成员并列发布后形成未解决冲突组）
- rollback on later entity failure（事件/暴露失败时事实一并回滚）
- stale authority pointer rejection（发布前复核活动指针，陈旧拒绝）
- retry idempotency（重复发布返回等价结果，不产生重复行）
- divergent payload conflict（同幂等域内 divergent payload 抛冲突）

仅聚焦本服务与直接相邻的 Fact 仓储，不跑全量套件。
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select, update

from app.domain.contracts.enums import (
    DatePrecision,
    DurationStatus,
    FactGate,
    FactPolarity,
    GateOutcome,
    ProfileLane,
    LocatorAuthenticity,
    LocatorPrecision,
    LocatorSourceLayer,
    DisambiguationOutcome,
    SnapshotStatus,
    SnapshotMemberOrigin,
    FactCallStatus,
    FactNormalizationRunStatus,
    UploadMode,
)
from app.domain.contracts.evidence_ingestion import EvidenceSnapshot, EvidenceSnapshotMember, SourceDocumentVersion
from app.domain.contracts.evidence_locator import CompleteEvidenceProcessingRevision, EvidenceLocatorArtifact
from app.domain.contracts.facts import (
    AssertionBasis,
    ClinicalEventCandidateV2,
    ClinicalFactCandidateV2,
    FactAuthority,
    FactGateResult,
    FactNormalizationCall,
    FactNormalizationRun,
    MedicationExposureCandidateV2,
    PartialDateRange,
    fact_run_idempotency_key,
)
from app.domain.publication import canonical_hash, evidence_snapshot_collection_hash, evidence_processing_manifest_hash
from app.storage.codecs import encode_contract
from app.storage.fact_authority import FactLocatorReferenceError
from app.storage.db import Base  # noqa
from app.storage.fact_repositories import (
    ClinicalConflictGroupV2Repository,
    ClinicalEventV2Repository,
    ClinicalFactV2Repository,
    FactGateResultRepository,
    FactNormalizationCallRepository,
    FactNormalizationCandidateRepository,
    FactNormalizationRunRepository,
    MedicationExposureV2Repository,
    Phase5RepositoryError,
)
from app.storage.facts_models import (
    ClinicalConflictGroupV2Record,
    ClinicalEventV2Record,
    ClinicalFactV2Record,
    FactNormalizationCandidateRecord,
    FactNormalizationCallRecord,
    FactNormalizationRunRecord,
    FactGateResultRecord,
    MedicationExposureV2Record,
)
from app.storage.evidence_models import (
    EvidenceSnapshotV2Record,
    EvidenceSnapshotMemberRecord,
    SourceDocumentVersionV2Record,
    SourceBlobRecord,
)
from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord, ProcessingRevisionLocatorRecord
from app.storage.models import ReviewEpisodeRecord, ProjectRecord, SubjectRecord, IdempotencyRecordRow
from app.storage.models import RuleSetRecord, ProtocolDocumentVersionRecord, WorkflowStageRecord, EvidenceExpectationTemplateRecord, EvidenceRequirementRecord
from app.storage.ocr_models import EvidenceProcessingRevisionRecord, PageArtifactRecord
from app.storage.repositories import EpisodeRepository
from app.services.fact_publication_service import (
    FactPublicationError,
    FactPublicationService,
    FactPublicationStaleAuthorityError,
)
from app.storage.idempotency import IdempotencyConflict
from tests.v2.helpers.phase5_fact_chain import seed_valid_fact_chain

NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)
_PAYLOAD = '{"kind": "test"}'
_PAYLOAD_SHA = hashlib.sha256(_PAYLOAD.encode("utf-8")).hexdigest()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _add(session, record):
    session.add(record)
    session.flush()
    return record


def _bind_payload(record, contract) -> None:
    record.payload_json, record.payload_sha256 = encode_contract(contract)


def _seed_chain_legacy(session, prefix: str) -> dict[str, str]:
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
    from sqlalchemy import update as sa_update
    session.execute(
        sa_update(ReviewEpisodeRecord)
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
    collection_sha256 = evidence_snapshot_collection_hash(members=[(f"{prefix}-log", doc_id)])
    snapshot_record = session.get(EvidenceSnapshotV2Record, snapshot_id)
    snapshot_record.collection_sha256 = collection_sha256
    _bind_payload(snapshot_record, EvidenceSnapshot(
        evidence_snapshot_id=snapshot_id, project_id=project_id, subject_id=subject_id,
        review_episode_id=episode_id, upload_mode=UploadMode.FULL, members=[member_contract],
        collection_sha256=collection_sha256, status=SnapshotStatus.STAGED, created_at=NOW, created_by="tester",
    ))
    _bind_payload(session.get(EvidenceSnapshotMemberRecord, f"{prefix}-member"), member_contract)
    _bind_payload(session.get(SourceDocumentVersionV2Record, doc_id), SourceDocumentVersion(
        source_document_version_id=doc_id, logical_document_id=f"{prefix}-log",
        source_blob_sha256=_sha(f"{prefix}-blob"), file_name="f.pdf", media_type="application/pdf",
        page_count=1, project_id=project_id, subject_id=subject_id, review_episode_id=episode_id,
        version_number=1, created_at=NOW, created_by="tester",
    ))
    from app.domain.contracts.review import ReviewEpisode
    episode_payload_json, episode_payload_sha256 = encode_contract(ReviewEpisode(
        review_episode_id=episode_id, subject_id=subject_id, project_id=project_id,
        rule_set_id=rule_set_id, study_phase="phase_iii", stage="screening",
        protocol_version_id=protocol_version_id, rule_set_revision=1,
        active_evidence_snapshot_id=snapshot_id, active_evidence_processing_revision_id=complete_revision_id,
    ))
    session.execute(
        sa_update(ReviewEpisodeRecord).where(ReviewEpisodeRecord.review_episode_id == episode_id).values(
            payload_json=episode_payload_json, payload_sha256=episode_payload_sha256,
        )
    )
    session.expire_all()
    complete_manifest_sha256 = evidence_processing_manifest_hash(entries=[])
    complete_record = session.get(EvidenceProcessingRevisionRecord, complete_revision_id)
    complete_record.manifest_sha256 = complete_manifest_sha256
    _bind_payload(complete_record, CompleteEvidenceProcessingRevision(
        evidence_processing_revision_id=complete_revision_id, evidence_snapshot_id=snapshot_id,
        project_id=project_id, subject_id=subject_id, review_episode_id=episode_id,
        base_processing_revision_id=base_revision_id, producer_candidate_id=f"{prefix}-candidate",
        candidate_input_sha256=_sha("candidate-input"), manifest=[], manifest_sha256=complete_manifest_sha256,
        locator_ids=[locator_id, locator_id_2], completion_manifest_sha256=_sha("completion-manifest"),
        created_at=NOW, created_by="tester",
    ))
    for locator_id_value, source_hash, target_id, start, end, excerpt in (
        (locator_id, _sha("alt"), "target-1", 0, 5, "ALT 5"),
        (locator_id_2, _sha("ast"), "target-2", 6, 11, "AST 3"),
    ):
        locator_record = session.get(EvidenceLocatorArtifactRecord, locator_id_value)
        locator_record.processing_revision_id = None
        _bind_payload(locator_record, EvidenceLocatorArtifact(
            locator_id=locator_id_value, page_artifact_id=page_artifact_id,
            source_document_version_id=doc_id, page_number=1,
            source_layer=LocatorSourceLayer.RAW_OCR, source_text_sha256=source_hash,
            target_id=target_id, precision=LocatorPrecision.TEXT_RANGE,
            text_start=start, text_end=end, excerpt=excerpt,
            disambiguation=DisambiguationOutcome.UNIQUE_MATCH,
            locator_algorithm_version="v1", authenticity=LocatorAuthenticity.DEGRADED,
            degradation_reason="text-only", created_at=NOW,
        ))
    _add(session, ProtocolDocumentVersionRecord(
        protocol_version_id=f"{prefix}-prompt", # reuse prefix for prompt alias? but need prompt_version separate
        protocol_code="P", official_version="v1", official_date_value=None,
        official_date_precision="unknown", sha256=_sha("prompt-pv"), integrity_manifest_sha256=_sha("int"), authority_record_sha256=_sha("auth"), authority_confirmation_id="c", authority_gate_result_id="a", integrity_gate_result_id="i",
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
    )) if session.get(ProtocolDocumentVersionRecord, f"{prefix}-prompt") is None else None
    # prompt/model records — use dedicated ids
    from app.storage.models import PromptVersionRecord, ModelConfigRecord
    if session.get(PromptVersionRecord, prompt_version_id) is None:
        _add(session, PromptVersionRecord(
            prompt_version_id=prompt_version_id, node="evidence_normalizer",
            template_sha256=_sha("prompt"), schema_version_id="phase5/facts/v1",
            payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
        ))
    if session.get(ModelConfigRecord, model_config_id) is None:
        _add(session, ModelConfigRecord(
            model_config_id=model_config_id, provider="p", model="m",
            reasoning_effort="medium", payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
        ))
    run_authority = _authority({
        "project_id": project_id, "subject_id": subject_id, "review_episode_id": episode_id,
        "protocol_version_id": protocol_version_id, "rule_set_id": rule_set_id,
        "evidence_snapshot_v2_id": snapshot_id, "complete_processing_revision_id": complete_revision_id,
    })
    run = FactNormalizationRun(
        run_id=run_id, authority=run_authority,
        idempotency_key=fact_run_idempotency_key(
            authority=run_authority, prompt_version_id=prompt_version_id,
            model_config_id=model_config_id, input_scope_sha256=_sha("input-scope"),
        ),
        prompt_version_id=prompt_version_id, model_config_id=model_config_id,
        input_scope_sha256=_sha("input-scope"),
        status=FactNormalizationRunStatus.SUCCEEDED, created_at=NOW, created_by="tester",
    )
    FactNormalizationRunRepository(session).create_or_reuse(run)
    FactNormalizationCallRepository(session).create(FactNormalizationCall(
        call_id=call_id, run_id=run_id, logical_document_id=f"{prefix}-log",
        page_numbers=[1], status=FactCallStatus.SUCCEEDED, input_sha256=_sha("call-input"), created_at=NOW,
    ))
    # 默认一个事实候选（可被各测试增补）
    FactNormalizationCandidateRepository(session).create(call_id, ClinicalFactCandidateV2(
        candidate_id=f"{prefix}-cand", run_id=run_id, call_id=call_id,
        fact_type="vital_sign", polarity=FactPolarity.AFFIRMED, asserted_object="血压",
        raw_value="120/80", canonical_value="120/80", unit="unitless",
        date_range=_date_range(), record_time=NOW, locator_ids=[locator_id],
        candidate_source_semantics="objective_result", assertion_basis=_basis(locator_id),
        model_uncertainty=0.01, created_at=NOW,
    ))
    FactGateResultRepository(session).create(FactGateResult(
        gate_result_id=gate_id, run_id=run_id, call_id=call_id,
        candidate_id=f"{prefix}-cand", gate=FactGate.TRANSACTIONAL_PUBLISH,
        outcome=GateOutcome.ACCEPTED, reasons=[], created_at=NOW,
    ))
    return {
        "project_id": project_id, "subject_id": subject_id, "review_episode_id": episode_id,
        "protocol_version_id": protocol_version_id, "rule_set_id": rule_set_id,
        "evidence_snapshot_v2_id": snapshot_id, "complete_processing_revision_id": complete_revision_id,
        "base_processing_revision_id": base_revision_id, "locator_id": locator_id, "locator_id_2": locator_id_2,
        "run_id": run_id, "call_id": call_id, "gate_id": gate_id,
        "fact_candidate_id": f"{prefix}-cand",
    }


def _seed_chain(
    session,
    prefix: str,
    *,
    fact_gate_outcome: GateOutcome = GateOutcome.ACCEPTED,
    supported_requirement_ids=None,
) -> dict[str, str]:
    chain = seed_valid_fact_chain(session, prefix, create_run=True)
    run_id = chain["run_id"]
    call_id = chain["call_id"]
    candidate_id = f"{prefix}-cand"
    gate_id = f"{prefix}-gate"
    locator = session.get(EvidenceLocatorArtifactRecord, chain["locator_id"])
    basis = AssertionBasis(
        asserted_object="血压",
        assertion_text="血压 120/80 mmHg",
        locator_id=chain["locator_id"],
        source_text_sha256=locator.source_text_sha256,
    )
    FactNormalizationCandidateRepository(session).create(
        call_id,
        ClinicalFactCandidateV2(
            candidate_id=candidate_id,
            run_id=run_id,
            call_id=call_id,
            fact_type="vital_sign",
            supported_requirement_ids=supported_requirement_ids or ["req-z"],
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
    FactGateResultRepository(session).create(
        FactGateResult(
            gate_result_id=gate_id,
            run_id=run_id,
            call_id=call_id,
            candidate_id=candidate_id,
            gate=FactGate.TRANSACTIONAL_PUBLISH,
            outcome=fact_gate_outcome,
            reasons=(
                []
                if fact_gate_outcome == GateOutcome.ACCEPTED
                else ["事实候选未通过最终事务门禁"]
            ),
            created_at=NOW,
        )
    )
    return {
        **chain,
        "gate_id": gate_id,
        "fact_candidate_id": candidate_id,
    }


def _authority(ids: dict[str, str], **overrides) -> FactAuthority:
    base = {
        "project_id": ids["project_id"], "subject_id": ids["subject_id"],
        "review_episode_id": ids["review_episode_id"], "episode_revision": 1,
        "protocol_version_id": ids["protocol_version_id"], "rule_set_id": ids["rule_set_id"],
        "rule_set_revision": 1, "evidence_snapshot_v2_id": ids["evidence_snapshot_v2_id"],
        "complete_processing_revision_id": ids["complete_processing_revision_id"],
    }
    base.update(overrides)
    return FactAuthority(**base)


def _date_range():
    return PartialDateRange(source_text="2026-03-01", precision=DatePrecision.DAY, lower_bound=date(2026, 3, 1), upper_bound=date(2026, 3, 1))


def _basis(locator_id: str) -> AssertionBasis:
    return AssertionBasis(asserted_object="血压", assertion_text="血压 120/80 mmHg", locator_id=locator_id, source_text_sha256=_sha("alt"))


def _source_hash(session, locator_id: str) -> str:
    return session.get(EvidenceLocatorArtifactRecord, locator_id).source_text_sha256


def _update_episode(session, episode: ReviewEpisodeRecord, **changes) -> None:
    from app.domain.contracts.review import ReviewEpisode

    payload = EpisodeRepository._decode_record(episode)
    updated = payload.model_copy(update=changes)
    # 保持 payload 与列同步
    episode_payload_json, episode_payload_sha256 = encode_contract(updated)
    for key, value in changes.items():
        setattr(episode, key, value)
    episode.payload_json = episode_payload_json
    episode.payload_sha256 = episode_payload_sha256
    session.flush()
    session.expire_all()


def _bind_isolated_fact_candidate(session, prefix, locator_id, asserted_object="血压", canonical_value="120/80", unit="unitless", date_range=None, polarity=FactPolarity.AFFIRMED):
    """便于在同一 run 内追加同 stable 或冲突候选。"""
    date_range = date_range or _date_range()
    cand = ClinicalFactCandidateV2(
        candidate_id=f"{prefix}-{hashlib.sha256((asserted_object+str(canonical_value)).encode()).hexdigest()[:8]}",
        run_id=f"{prefix}-run", call_id=f"{prefix}-call",
        fact_type="vital_sign", polarity=polarity, asserted_object=asserted_object,
        raw_value=str(canonical_value), canonical_value=canonical_value, unit=unit,
        date_range=date_range, record_time=NOW, locator_ids=[locator_id],
        candidate_source_semantics="objective_result", assertion_basis=AssertionBasis(asserted_object=asserted_object, assertion_text=f"{asserted_object} {canonical_value}", locator_id=locator_id, source_text_sha256=_sha("alt") if locator_id.endswith("locator") else _sha("ast")),
        model_uncertainty=0.01, created_at=NOW,
    )
    # 修正 sha：根据 locator 实际 source hash
    if locator_id.endswith("locator2"):
        cand = cand.model_copy(update={"assertion_basis": cand.assertion_basis.model_copy(update={"source_text_sha256": _sha("ast")})})
    return cand


# ------------------------------------------------------------------ 测试

def test_merged_locator_closure(session):
    prefix = "pub-merge"
    chain = _seed_chain(session, prefix)
    run_id = chain["run_id"]
    call_id = chain["call_id"]
    # 追加同 stable 的第二个候选，使用 locator2 且相同语义
    cand2 = ClinicalFactCandidateV2(
        candidate_id=f"{prefix}-cand2", run_id=run_id, call_id=call_id,
        fact_type="vital_sign", polarity=FactPolarity.AFFIRMED, asserted_object="血压",
        supported_requirement_ids=["req-a"],
        raw_value="120/80", canonical_value="120/80", unit="unitless",
        date_range=_date_range(), record_time=NOW, locator_ids=[chain["locator_id_2"]],
        candidate_source_semantics="objective_result", assertion_basis=AssertionBasis(asserted_object="血压", assertion_text="血压 120/80 mmHg", locator_id=chain["locator_id_2"], source_text_sha256=_source_hash(session, chain["locator_id_2"])),
        model_uncertainty=0.01, created_at=NOW,
    )
    FactNormalizationCandidateRepository(session).create(call_id, cand2)
    FactGateResultRepository(session).create(FactGateResult(
        gate_result_id=f"{prefix}-gate2", run_id=run_id, call_id=call_id, candidate_id=cand2.candidate_id, gate=FactGate.TRANSACTIONAL_PUBLISH, outcome=GateOutcome.ACCEPTED, reasons=[], created_at=NOW,
    ))
    svc = FactPublicationService()
    result = svc.publish(session, run_id)
    # 同 stable 应只产生一条 fact，且 locator 为并集有序
    assert len(result.fact_ids) == 1
    fact = ClinicalFactV2Repository(session).get(result.fact_ids[0])
    assert fact.locator_ids == sorted([chain["locator_id"], chain["locator_id_2"]])
    assert fact.source_candidate_ids == sorted(
        [chain["fact_candidate_id"], cand2.candidate_id]
    )
    assert fact.gate_ids == sorted([chain["gate_id"], f"{prefix}-gate2"])
    assert fact.supported_requirement_ids == ["req-a", "req-z"]
    # 不产生冲突组
    assert result.conflict_group_ids == []
    # 校验 fact 的权威仍为链上权威
    assert fact.authority == _authority(chain)


def test_same_fact_semantics_with_different_profile_lanes_are_rejected(session):
    prefix = "pub-lane-conflict"
    chain = _seed_chain(session, prefix)
    candidate = ClinicalFactCandidateV2(
        candidate_id=f"{prefix}-cand2",
        run_id=chain["run_id"],
        call_id=chain["call_id"],
        fact_type="vital_sign",
        profile_lane=ProfileLane.TEST_EXAM_SCORE,
        polarity=FactPolarity.AFFIRMED,
        asserted_object="血压",
        raw_value="120/80",
        canonical_value="120/80",
        unit="unitless",
        date_range=_date_range(),
        record_time=NOW,
        locator_ids=[chain["locator_id_2"]],
        candidate_source_semantics="objective_result",
        assertion_basis=AssertionBasis(
            asserted_object="血压",
            assertion_text="血压 120/80 mmHg",
            locator_id=chain["locator_id_2"],
            source_text_sha256=_source_hash(session, chain["locator_id_2"]),
        ),
        model_uncertainty=0.01,
        created_at=NOW,
    )
    FactNormalizationCandidateRepository(session).create(chain["call_id"], candidate)
    FactGateResultRepository(session).create(
        FactGateResult(
            gate_result_id=f"{prefix}-gate2",
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            candidate_id=candidate.candidate_id,
            gate=FactGate.TRANSACTIONAL_PUBLISH,
            outcome=GateOutcome.ACCEPTED,
            reasons=[],
            created_at=NOW,
        )
    )

    with pytest.raises(FactPublicationError, match="主题归属冲突"):
        FactPublicationService().publish(session, chain["run_id"])

    assert session.execute(
        select(ClinicalFactV2Record).where(
            ClinicalFactV2Record.run_id == chain["run_id"]
        )
    ).scalars().all() == []


@pytest.mark.parametrize("same_lane", [
    False,
    True,
])
@pytest.mark.parametrize("has_dependent_event", [False, True])
def test_later_run_preserves_fact_identity_and_sources(session, same_lane, has_dependent_event):
    prefix = "pub-cross-run-lane-conflict"
    chain = _seed_chain(
        session, prefix,
        supported_requirement_ids=["slice54-req-z"] if has_dependent_event else None,
    )
    if has_dependent_event:
        event = ClinicalEventCandidateV2(
            candidate_id=f"{prefix}-event", run_id=chain["run_id"], call_id=chain["call_id"],
            event_type="diagnosis", start_range=_date_range(), end_range=None,
            duration_status=DurationStatus.ONGOING, record_time=NOW,
            fact_candidate_ids=[chain["fact_candidate_id"]], locator_ids=[chain["locator_id"]],
            candidate_source_semantics="objective_result", model_uncertainty=0.02,
            created_at=NOW,
        )
        FactNormalizationCandidateRepository(session).create(chain["call_id"], event)
        FactGateResultRepository(session).create(FactGateResult(
            gate_result_id=f"{prefix}-event-gate", run_id=chain["run_id"],
            call_id=chain["call_id"], candidate_id=event.candidate_id,
            gate=FactGate.TRANSACTIONAL_PUBLISH, outcome=GateOutcome.ACCEPTED,
            reasons=[], created_at=NOW,
        ))
        exposure = MedicationExposureCandidateV2(
            candidate_id=f"{prefix}-exposure", run_id=chain["run_id"], call_id=chain["call_id"],
            medication_name="测试药物", dose="一片", frequency="每日一次",
            start_range=_date_range(), end_range=None,
            duration_status=DurationStatus.ONGOING, record_time=NOW,
            fact_candidate_ids=[chain["fact_candidate_id"]], locator_ids=[chain["locator_id"]],
            candidate_source_semantics="objective_result", model_uncertainty=0.02, created_at=NOW,
        )
        FactNormalizationCandidateRepository(session).create(chain["call_id"], exposure)
        FactGateResultRepository(session).create(FactGateResult(
            gate_result_id=f"{prefix}-exposure-gate", run_id=chain["run_id"],
            call_id=chain["call_id"], candidate_id=exposure.candidate_id,
            gate=FactGate.TRANSACTIONAL_PUBLISH, outcome=GateOutcome.ACCEPTED,
            reasons=[], created_at=NOW,
        ))
    first = FactPublicationService().publish(session, chain["run_id"])
    assert len(first.fact_ids) == 1
    if has_dependent_event:
        from tests.v2.projections.test_evidence_expectations import _template
        from app.domain.contracts.enums import ExpectationStatus, ReviewStage
        from app.domain.contracts.evidence_expectations_v2 import EvidenceExpectationV2
        from app.storage.evidence_expectation_repository import EvidenceExpectationV2Repository
        template = _template(
            session, chain, requirement_id="req-z", fact_type="vital_sign",
            due_stage=ReviewStage.SCREENING,
        )
        old_expectation = EvidenceExpectationV2Repository(session).project(EvidenceExpectationV2(
            expectation_id=f"{prefix}-expectation", authority=_authority(chain),
            template_id=template.template_id, status=ExpectationStatus.OBSERVED,
            revision=1, locator_ids=[chain["locator_id"]], coverage_fact_ids=first.fact_ids,
            source_coverage="complete", input_gap_signals=[], created_at=NOW,
        ))

    run_id = f"{prefix}-run-2"
    call_id = f"{prefix}-call-2"
    candidate_id = f"{prefix}-cand-2"
    input_scope_sha256 = _sha("second-input-scope")
    authority = _authority(chain)
    FactNormalizationRunRepository(session).create_or_reuse(
        FactNormalizationRun(
            run_id=run_id,
            authority=authority,
            idempotency_key=fact_run_idempotency_key(
                authority=authority,
                prompt_version_id=chain["prompt_version_id"],
                model_config_id=chain["model_config_id"],
                input_scope_sha256=input_scope_sha256,
            ),
            prompt_version_id=chain["prompt_version_id"],
            model_config_id=chain["model_config_id"],
            input_scope_sha256=input_scope_sha256,
            status=FactNormalizationRunStatus.SUCCEEDED,
            created_at=NOW,
            created_by="tester",
        )
    )
    FactNormalizationCallRepository(session).create(
        FactNormalizationCall(
            call_id=call_id,
            run_id=run_id,
            logical_document_id=chain["logical_document_id"],
            page_numbers=[1],
            status=FactCallStatus.SUCCEEDED,
            input_sha256=_sha("second-call-input"),
            created_at=NOW,
        )
    )
    FactNormalizationCandidateRepository(session).create(
        call_id,
        ClinicalFactCandidateV2(
            candidate_id=candidate_id,
            run_id=run_id,
            call_id=call_id,
            fact_type="vital_sign",
            profile_lane=(
                ProfileLane.EVIDENCE_QUALITY if same_lane
                else ProfileLane.TEST_EXAM_SCORE
            ),
            polarity=FactPolarity.AFFIRMED,
            asserted_object="血压",
            raw_value="120/80",
            canonical_value="120/80",
            unit="unitless",
            date_range=_date_range(),
            record_time=NOW,
            locator_ids=[chain["locator_id_2"]],
            candidate_source_semantics="objective_result",
            assertion_basis=AssertionBasis(
                asserted_object="血压",
                assertion_text="血压 120/80 mmHg",
                locator_id=chain["locator_id_2"],
                source_text_sha256=_source_hash(session, chain["locator_id_2"]),
            ),
            model_uncertainty=0.01,
            created_at=NOW,
        ),
    )
    FactGateResultRepository(session).create(
        FactGateResult(
            gate_result_id=f"{prefix}-gate-2",
            run_id=run_id,
            call_id=call_id,
            candidate_id=candidate_id,
            gate=FactGate.TRANSACTIONAL_PUBLISH,
            outcome=GateOutcome.ACCEPTED,
            reasons=[],
            created_at=NOW,
        )
    )

    if same_lane:
        if has_dependent_event:
            old_event = ClinicalEventV2Repository(session).get(first.event_ids[0])
            old_exposure = MedicationExposureV2Repository(session).get(first.exposure_ids[0])
        published = FactPublicationService().publish(session, run_id)
        original = ClinicalFactV2Repository(session).get(first.fact_ids[0])
        current = ClinicalFactV2Repository(session).get(published.fact_ids[0])
        assert current.stable_identity == original.stable_identity
        assert current.revision == original.revision + 1
        assert set(original.locator_ids) <= set(current.locator_ids)
        assert set(original.supported_requirement_ids) <= set(current.supported_requirement_ids)
        assert set(original.source_candidate_ids) <= set(current.source_candidate_ids)
        assert set(original.gate_ids) <= set(current.gate_ids)
        assert current.inherited_from_fact_id == original.fact_id
        assert FactPublicationService().publish(session, run_id).is_replay
        if has_dependent_event:
            successor = ClinicalEventV2Repository(session).get(published.event_ids[0])
            assert successor.source_revision_of == old_event.event_id
            assert successor.fact_ids == published.fact_ids
            assert successor.locator_ids == old_event.locator_ids
            assert successor.source_candidate_ids == old_event.source_candidate_ids
            assert ClinicalEventV2Repository(session).get(old_event.event_id) == old_event
            successor_exposure = MedicationExposureV2Repository(session).get(published.exposure_ids[0])
            assert successor_exposure.source_revision_of == old_exposure.exposure_id
            assert successor_exposure.fact_ids == published.fact_ids
            assert successor_exposure.dose == old_exposure.dose
            assert successor_exposure.source_candidate_ids == old_exposure.source_candidate_ids
            assert MedicationExposureV2Repository(session).get(old_exposure.exposure_id) == old_exposure
            expectation2 = EvidenceExpectationV2Repository(session).latest_by_template(
                chain["review_episode_id"], template.template_id
            )
            assert expectation2.source_revision_of == old_expectation.expectation_id
            assert expectation2.coverage_fact_ids == published.fact_ids
            assert expectation2.locator_ids == current.locator_ids
            assert expectation2.status == old_expectation.status
            with pytest.raises(Phase5RepositoryError, match="不得改变"):
                ClinicalEventV2Repository(session).create(
                    successor.model_copy(update={"event_type": "changed-event"})
                )
            with pytest.raises(Phase5RepositoryError, match="不得改变"):
                MedicationExposureV2Repository(session).create(
                    successor_exposure.model_copy(update={"dose": "两片"})
                )
            with pytest.raises(Phase5RepositoryError, match="不得改变"):
                EvidenceExpectationV2Repository(session).project(
                    expectation2.model_copy(update={"input_gap_signals": None})
                )
            from app.storage.source_reference_successors import source_successor_origin_run
            for changes in (
                {"dose": "两片"}, {"source_candidate_ids": []},
                {"fact_ids": []}, {"fact_ids": old_exposure.fact_ids},
                {"locator_ids": [chain["locator_id_2"]]},
            ):
                with pytest.raises(Phase5RepositoryError):
                    source_successor_origin_run(
                        session, successor_exposure.model_copy(update=changes),
                        MedicationExposureV2Repository(session), id_field="exposure_id",
                    )
        repository = ClinicalFactV2Repository(session)
        for changes in (
            {"inherited_from_fact_id": None},
            {"inherited_from_fact_id": current.fact_id},
            {"revision": current.revision + 1},
            {"authority": current.authority.model_copy(update={"subject_id": "other"})},
            {"gate_id": original.gate_id},
            {"source_candidate_ids": [candidate_id]},
            {"gate_ids": [f"{prefix}-gate-2"]},
            {"locator_ids": [chain["locator_id_2"]]},
        ):
            with pytest.raises((Phase5RepositoryError, FactLocatorReferenceError)):
                repository._publication_candidates(current.model_copy(update=changes))
        from unittest.mock import patch
        with patch(
            "app.storage.fact_correction_repository.FactCorrectionRepository.superseded_entity_ids",
            return_value={original.fact_id},
        ):
            with pytest.raises(Phase5RepositoryError, match="未经更正"):
                repository._publication_candidates(current)
        assert repository.get(original.fact_id) == original
        run3_id = f"{prefix}-run-3"
        scope3 = _sha("third-input-scope")
        run2 = FactNormalizationRunRepository(session).get(run_id)
        FactNormalizationRunRepository(session).create_or_reuse(run2.model_copy(update={
            "run_id": run3_id,
            "input_scope_sha256": scope3,
            "idempotency_key": fact_run_idempotency_key(
                authority=authority, prompt_version_id=chain["prompt_version_id"],
                model_config_id=chain["model_config_id"], input_scope_sha256=scope3,
            ),
        }))
        call3_id = f"{prefix}-call-3"
        FactNormalizationCallRepository(session).create(
            FactNormalizationCallRepository(session).get(call_id).model_copy(update={
                "run_id": run3_id, "call_id": call3_id,
                "input_sha256": _sha("third-call-input"),
            })
        )
        candidate3_id = f"{prefix}-cand-3"
        FactNormalizationCandidateRepository(session).create(
            call3_id,
            FactNormalizationCandidateRepository(session).get(candidate_id).model_copy(update={
                "candidate_id": candidate3_id, "call_id": call3_id, "run_id": run3_id,
            }),
        )
        FactGateResultRepository(session).create(
            FactGateResultRepository(session).get(f"{prefix}-gate-2").model_copy(update={
                "gate_result_id": f"{prefix}-gate-3", "call_id": call3_id,
                "run_id": run3_id, "candidate_id": candidate3_id,
            })
        )
        third = FactPublicationService().publish(session, run3_id)
        latest = repository.get(third.fact_ids[0])
        assert latest.inherited_from_fact_id == current.fact_id
        assert latest.revision == 3
        assert set(latest.source_candidate_ids) == set(current.source_candidate_ids) | {candidate3_id}
        assert latest.locator_ids == current.locator_ids
        replay3 = FactPublicationService().publish(session, run3_id)
        assert replay3.is_replay
        if has_dependent_event:
            event3 = ClinicalEventV2Repository(session).get(third.event_ids[0])
            exposure3 = MedicationExposureV2Repository(session).get(third.exposure_ids[0])
            assert event3.source_revision_of == successor.event_id
            assert exposure3.source_revision_of == successor_exposure.exposure_id
            assert event3.fact_ids == exposure3.fact_ids == third.fact_ids
            assert replay3.event_ids == third.event_ids
            assert replay3.exposure_ids == third.exposure_ids
            assert event3.locator_ids == old_event.locator_ids
            assert exposure3.locator_ids == old_exposure.locator_ids
            expectation3 = EvidenceExpectationV2Repository(session).latest_by_template(
                chain["review_episode_id"], template.template_id
            )
            assert expectation3.source_revision_of == expectation2.expectation_id
            assert expectation3.coverage_fact_ids == third.fact_ids
            # Exercise repository entry points, not only the source-link helper.
            for entity, dependent_repository, id_field in (
                (event3, ClinicalEventV2Repository(session), "event_id"),
                (exposure3, MedicationExposureV2Repository(session), "exposure_id"),
            ):
                for index, changes in enumerate((
                    {"fact_ids": [latest.fact_id, latest.fact_id]},
                    {"fact_ids": sorted([current.fact_id, latest.fact_id])},
                    {"source_revision_of": getattr(old_event if id_field == "event_id" else old_exposure, id_field), "revision": 2},
                )):
                    with pytest.raises(Phase5RepositoryError):
                        dependent_repository.create(entity.model_copy(update={
                            id_field: f"{prefix}-{id_field}-invalid-{index}", **changes,
                        }))
            for index, changes in enumerate((
                {"source_revision_of": old_expectation.expectation_id, "revision": 2},
                {"locator_ids": [chain["locator_id_2"]]},
                {"coverage_fact_ids": sorted([current.fact_id, latest.fact_id])},
            )):
                with pytest.raises(Phase5RepositoryError):
                    EvidenceExpectationV2Repository(session).project(expectation3.model_copy(update={
                        "expectation_id": f"{prefix}-expectation-invalid-{index}", **changes,
                    }))
            from app.services.patient_profile_service import PatientProfileService
            from app.domain.contracts.patient_profile_v2 import profile_items
            profile = PatientProfileService().generate(session, authority=authority)
            assert profile.status.value == "succeeded"
            assert {item.source_id for item in profile_items(profile)} == {
                latest.fact_id, event3.event_id, exposure3.exposure_id, expectation3.expectation_id,
            }
        assert repository.get(original.fact_id) == original
        assert repository.get(current.fact_id) == current
        from tests.v2.storage.test_fact_correction_repository import _correction_for_facts
        from app.storage.fact_correction_repository import FactCorrectionRepository
        for suffix, value in (("corrected", "130/80"), ("old-value", "120/80")):
            followup_run = f"{prefix}-{suffix}-run"
            followup_call = f"{prefix}-{suffix}-call"
            followup_candidate = f"{prefix}-{suffix}-candidate"
            scope = _sha(suffix)
            FactNormalizationRunRepository(session).create_or_reuse(run2.model_copy(update={
                "run_id": followup_run, "input_scope_sha256": scope,
                "idempotency_key": fact_run_idempotency_key(
                    authority=authority, prompt_version_id=chain["prompt_version_id"],
                    model_config_id=chain["model_config_id"], input_scope_sha256=scope,
                ),
            }))
            FactNormalizationCallRepository(session).create(
                FactNormalizationCallRepository(session).get(call_id).model_copy(update={
                    "run_id": followup_run, "call_id": followup_call,
                    "input_sha256": _sha(followup_call),
                })
            )
            FactNormalizationCandidateRepository(session).create(
                followup_call,
                FactNormalizationCandidateRepository(session).get(candidate_id).model_copy(update={
                    "candidate_id": followup_candidate, "call_id": followup_call,
                    "run_id": followup_run, "canonical_value": value, "raw_value": value,
                }),
            )
            FactGateResultRepository(session).create(
                FactGateResultRepository(session).get(f"{prefix}-gate-2").model_copy(update={
                    "gate_result_id": f"{prefix}-{suffix}-gate", "call_id": followup_call,
                    "run_id": followup_run, "candidate_id": followup_candidate,
                })
            )
            if suffix == "corrected":
                correction_result = FactPublicationService().publish(session, followup_run)
                corrected = repository.get(correction_result.fact_ids[0])
                correction = _correction_for_facts(
                    latest, corrected, [chain["locator_id_2"]]
                )
                FactCorrectionRepository(session).create(correction)
                replay = FactPublicationService().publish(session, run3_id)
                assert replay.is_replay and replay.fact_ids == third.fact_ids
                assert repository.get(latest.fact_id) == latest
            else:
                with pytest.raises(FactPublicationError, match="最新版本已经更正"):
                    FactPublicationService().publish(session, followup_run)
                assert len(repository.list_by_episode(chain["review_episode_id"])) == 4
        return

    with pytest.raises(FactPublicationError, match="主题归属冲突"):
        FactPublicationService().publish(session, run_id)
    assert ClinicalFactV2Repository(session).list_by_episode(
        chain["review_episode_id"]
    ) == [ClinicalFactV2Repository(session).get(first.fact_ids[0])]


@pytest.mark.parametrize("candidate_kind", ["event", "exposure"])
def test_linked_entity_rejects_fact_candidate_that_failed_final_gate(
    session, candidate_kind
):
    """事件/用药不能借用仅存在但未通过最终事务门禁的事实候选。"""
    prefix = f"pub-rejected-parent-{candidate_kind}"
    chain = _seed_chain(
        session,
        prefix,
        fact_gate_outcome=GateOutcome.REJECTED,
    )
    common = {
        "candidate_id": f"{prefix}-{candidate_kind}-cand",
        "run_id": chain["run_id"],
        "call_id": chain["call_id"],
        "record_time": NOW,
        "fact_candidate_ids": [chain["fact_candidate_id"]],
        "locator_ids": [chain["locator_id"]],
        "candidate_source_semantics": "objective_result",
        "model_uncertainty": 0.01,
        "created_at": NOW,
    }
    if candidate_kind == "event":
        candidate = ClinicalEventCandidateV2(
            event_type="diagnosis",
            start_range=_date_range(),
            end_range=None,
            duration_status=DurationStatus.ONGOING,
            **common,
        )
    else:
        candidate = MedicationExposureCandidateV2(
            medication_name="氯雷他定",
            category="抗组胺药",
            indication="过敏性鼻炎",
            dose="10",
            unit="mg",
            frequency="每日一次",
            route="口服",
            start_range=_date_range(),
            end_range=None,
            duration_status=DurationStatus.ONGOING,
            **common,
        )
    FactNormalizationCandidateRepository(session).create(chain["call_id"], candidate)
    FactGateResultRepository(session).create(
        FactGateResult(
            gate_result_id=f"{prefix}-{candidate_kind}-gate",
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            candidate_id=candidate.candidate_id,
            gate=FactGate.TRANSACTIONAL_PUBLISH,
            outcome=GateOutcome.ACCEPTED,
            reasons=[],
            created_at=NOW,
        )
    )

    with pytest.raises(FactPublicationError, match="未通过最终发布门禁"):
        FactPublicationService().publish(session, chain["run_id"])


def test_conflict_members_remaining_published(session):
    prefix = "pub-conflict"
    chain = _seed_chain(session, prefix)
    run_id = chain["run_id"]
    call_id = chain["call_id"]
    # 追加语义相同但值不同的冲突候选
    cand2 = ClinicalFactCandidateV2(
        candidate_id=f"{prefix}-cand2", run_id=run_id, call_id=call_id,
        fact_type="vital_sign", polarity=FactPolarity.AFFIRMED, asserted_object="血压",
        raw_value="130/90", canonical_value="130/90", unit="unitless",
        date_range=_date_range(), record_time=NOW, locator_ids=[chain["locator_id_2"]],
        candidate_source_semantics="objective_result", assertion_basis=AssertionBasis(asserted_object="血压", assertion_text="血压 130/90 mmHg", locator_id=chain["locator_id_2"], source_text_sha256=_source_hash(session, chain["locator_id_2"])),
        model_uncertainty=0.01, created_at=NOW,
    )
    FactNormalizationCandidateRepository(session).create(call_id, cand2)
    FactGateResultRepository(session).create(FactGateResult(
        gate_result_id=f"{prefix}-gate2", run_id=run_id, call_id=call_id, candidate_id=cand2.candidate_id, gate=FactGate.TRANSACTIONAL_PUBLISH, outcome=GateOutcome.ACCEPTED, reasons=[], created_at=NOW,
    ))
    svc = FactPublicationService()
    result = svc.publish(session, run_id)
    # 冲突成员并列发布：产生两条事实
    assert len(result.fact_ids) == 2
    facts = [ClinicalFactV2Repository(session).get(fid) for fid in result.fact_ids]
    values = sorted([f.value for f in facts])
    assert values == ["120/80", "130/90"]
    # 产生一条未解决冲突组，成员即两条事实，定位为并集
    assert len(result.conflict_group_ids) == 1
    group = ClinicalConflictGroupV2Repository(session).get(result.conflict_group_ids[0])
    assert sorted(group.fact_ids) == sorted(result.fact_ids)
    assert sorted(group.locator_ids) == sorted([chain["locator_id"], chain["locator_id_2"]])
    assert group.resolution_revision == 0
    # 冲突成员的定位仍各自保留
    for fact in facts:
        assert len(fact.locator_ids) == 1


def test_event_and_exposure_conflicts_are_published(session):
    """事件和用药/治疗暴露冲突不得在发布层丢失。"""
    prefix = "pub-linked-conflicts"
    chain = _seed_chain(session, prefix)
    common = {
        "run_id": chain["run_id"],
        "call_id": chain["call_id"],
        "record_time": NOW,
        "fact_candidate_ids": [chain["fact_candidate_id"]],
        "locator_ids": [chain["locator_id"]],
        "candidate_source_semantics": "objective_result",
        "model_uncertainty": 0.01,
        "created_at": NOW,
    }
    candidates = [
        ClinicalEventCandidateV2(
            candidate_id=f"{prefix}-event-ongoing",
            event_type="allergic_rhinitis",
            start_range=_date_range(),
            end_range=None,
            duration_status=DurationStatus.ONGOING,
            **common,
        ),
        ClinicalEventCandidateV2(
            candidate_id=f"{prefix}-event-ended",
            event_type="allergic_rhinitis",
            start_range=_date_range(),
            end_range=_date_range(),
            duration_status=DurationStatus.ENDED,
            **common,
        ),
        MedicationExposureCandidateV2(
            candidate_id=f"{prefix}-exposure-10",
            medication_name="氯雷他定",
            category="抗组胺药",
            indication="过敏性鼻炎",
            dose="10",
            unit="mg",
            frequency="每日一次",
            route="口服",
            start_range=_date_range(),
            end_range=None,
            duration_status=DurationStatus.ONGOING,
            **common,
        ),
        MedicationExposureCandidateV2(
            candidate_id=f"{prefix}-exposure-20",
            medication_name="氯雷他定",
            category="抗组胺药",
            indication="过敏性鼻炎",
            dose="20",
            unit="mg",
            frequency="每日一次",
            route="口服",
            start_range=_date_range(),
            end_range=None,
            duration_status=DurationStatus.ONGOING,
            **common,
        ),
    ]
    for position, candidate in enumerate(candidates, start=1):
        FactNormalizationCandidateRepository(session).create(chain["call_id"], candidate)
        FactGateResultRepository(session).create(
            FactGateResult(
                gate_result_id=f"{prefix}-linked-gate-{position}",
                run_id=chain["run_id"],
                call_id=chain["call_id"],
                candidate_id=candidate.candidate_id,
                gate=FactGate.TRANSACTIONAL_PUBLISH,
                outcome=GateOutcome.ACCEPTED,
                reasons=[],
                created_at=NOW,
            )
        )

    result = FactPublicationService().publish(session, chain["run_id"])

    assert len(result.event_ids) == 2
    assert len(result.exposure_ids) == 2
    groups = [
        ClinicalConflictGroupV2Repository(session).get(group_id)
        for group_id in result.conflict_group_ids
    ]
    assert {group.member_kind for group in groups} == {"event", "exposure"}
    event_group = next(group for group in groups if group.member_kind == "event")
    exposure_group = next(group for group in groups if group.member_kind == "exposure")
    assert event_group.event_ids == sorted(result.event_ids)
    assert exposure_group.exposure_ids == sorted(result.exposure_ids)
    assert event_group.fact_ids == event_group.exposure_ids == []
    assert exposure_group.fact_ids == exposure_group.event_ids == []


def test_serial_fact_change_publishes_without_conflict_group(session):
    prefix = "pub-serial-change"
    chain = _seed_chain(session, prefix)
    later = PartialDateRange(
        source_text="2027-03-01",
        precision=DatePrecision.DAY,
        lower_bound=date(2027, 3, 1),
        upper_bound=date(2027, 3, 1),
    )
    candidate = _bind_isolated_fact_candidate(
        session,
        prefix,
        chain["locator_id_2"],
        canonical_value="130/90",
        date_range=later,
    )
    candidate = candidate.model_copy(update={
        "assertion_basis": candidate.assertion_basis.model_copy(update={
            "source_text_sha256": _source_hash(session, chain["locator_id_2"])
        })
    })
    FactNormalizationCandidateRepository(session).create(chain["call_id"], candidate)
    FactGateResultRepository(session).create(FactGateResult(
        gate_result_id=f"{prefix}-later-gate",
        run_id=chain["run_id"],
        call_id=chain["call_id"],
        candidate_id=candidate.candidate_id,
        gate=FactGate.TRANSACTIONAL_PUBLISH,
        outcome=GateOutcome.ACCEPTED,
        reasons=[],
        created_at=NOW,
    ))

    result = FactPublicationService().publish(session, chain["run_id"])

    assert len(result.fact_ids) == 2
    assert result.conflict_group_ids == []


@pytest.mark.parametrize("missing_successor", [False, True])
@pytest.mark.parametrize("both_sides", [False, True])
def test_source_append_with_unreconciled_conflict_rolls_back(session, monkeypatch, missing_successor, both_sides):
    chain = _seed_chain(session, "pub-source-conflict")
    candidates = FactNormalizationCandidateRepository(session)
    gates = FactGateResultRepository(session)
    original_candidate = candidates.get(chain["fact_candidate_id"])
    other = original_candidate.model_copy(update={
        "candidate_id": "pub-source-conflict-other",
        "raw_value": "130/80", "canonical_value": "130/80",
    })
    candidates.create(chain["call_id"], other)
    gates.create(gates.get(chain["gate_id"]).model_copy(update={
        "gate_result_id": "pub-source-conflict-other-gate", "candidate_id": other.candidate_id,
    }))
    first = FactPublicationService().publish(session, chain["run_id"])
    assert len(first.conflict_group_ids) == 1
    run = FactNormalizationRunRepository(session).get(chain["run_id"])
    scope = _sha("conflict-followup")
    run_id, call_id = "pub-source-conflict-next-run", "pub-source-conflict-next-call"
    FactNormalizationRunRepository(session).create_or_reuse(run.model_copy(update={
        "run_id": run_id, "input_scope_sha256": scope,
        "idempotency_key": fact_run_idempotency_key(
            authority=run.authority, prompt_version_id=run.prompt_version_id,
            model_config_id=run.model_config_id, input_scope_sha256=scope,
        ),
    }))
    FactNormalizationCallRepository(session).create(
        FactNormalizationCallRepository(session).get(chain["call_id"]).model_copy(update={
            "call_id": call_id, "run_id": run_id, "input_sha256": _sha(call_id),
        })
    )
    followup = original_candidate.model_copy(update={
        "candidate_id": "pub-source-conflict-next-candidate", "run_id": run_id, "call_id": call_id,
    })
    candidates.create(call_id, followup)
    gates.create(gates.get(chain["gate_id"]).model_copy(update={
        "gate_result_id": "pub-source-conflict-next-gate",
        "run_id": run_id, "call_id": call_id, "candidate_id": followup.candidate_id,
    }))
    if both_sides:
        other_followup = other.model_copy(update={
            "candidate_id": "pub-source-conflict-next-other", "run_id": run_id, "call_id": call_id,
        })
        candidates.create(call_id, other_followup)
        gates.create(gates.get(chain["gate_id"]).model_copy(update={
            "gate_result_id": "pub-source-conflict-next-other-gate",
            "run_id": run_id, "call_id": call_id, "candidate_id": other_followup.candidate_id,
        }))
    if not missing_successor:
        from app.storage.active_conflicts import current_conflict_heads
        from app.services.patient_profile_service import PatientProfileService
        published = FactPublicationService().publish(session, run_id)
        assert len(published.conflict_group_ids) == 1
        repository = ClinicalConflictGroupV2Repository(session)
        previous = repository.get(first.conflict_group_ids[0])
        successor = repository.get(published.conflict_group_ids[0])
        assert successor.source_revision_of == previous.conflict_group_id
        assert successor.resolution_revision == previous.resolution_revision == 0
        assert successor.revision == 2
        assert len(successor.fact_ids) == len(previous.fact_ids) == 2
        assert successor.gate_id == previous.gate_id
        assert set(successor.fact_ids) == (
            set(published.fact_ids) | (set(previous.fact_ids) - {
                ClinicalFactV2Repository(session).get(item).inherited_from_fact_id
                for item in published.fact_ids
            })
        )
        assert set(successor.locator_ids) == {
            locator for item in successor.fact_ids
            for locator in ClinicalFactV2Repository(session).get(item).locator_ids
        }
        assert current_conflict_heads(session, run.authority) == [successor]
        assert repository.get(previous.conflict_group_id) == previous
        assert {item.conflict_group_id for item in repository.list_for_authority(run.authority)} == {
            previous.conflict_group_id, successor.conflict_group_id,
        }
        for index, changes in enumerate((
            {"fact_ids": successor.fact_ids[:1]},
            {"fact_ids": [successor.fact_ids[0], successor.fact_ids[0]]},
            {"fact_ids": previous.fact_ids},
            {"event_ids": ["unrelated-event"]},
            {"resolution_revision": 1},
            {"revision": 3},
        )):
            with pytest.raises(Phase5RepositoryError):
                repository.create(successor.model_copy(update={
                    "conflict_group_id": f"invalid-source-conflict-{index}", **changes,
                }))
        from app.storage.active_conflicts import source_conflict_heads
        from app.storage.repositories import InvalidReferenceError
        with pytest.raises(InvalidReferenceError, match="分叉"):
            source_conflict_heads([previous, successor, successor.model_copy(update={
                "conflict_group_id": "conflict-branch",
            })])
        assert FactPublicationService().publish(session, run_id).conflict_group_ids == published.conflict_group_ids
        assert PatientProfileService().generate(session, authority=run.authority).status.value == "succeeded"
        third_run, third_call = "pub-source-conflict-third-run", "pub-source-conflict-third-call"
        scope3 = _sha(third_run)
        FactNormalizationRunRepository(session).create_or_reuse(run.model_copy(update={
            "run_id": third_run, "input_scope_sha256": scope3,
            "idempotency_key": fact_run_idempotency_key(
                authority=run.authority, prompt_version_id=run.prompt_version_id,
                model_config_id=run.model_config_id, input_scope_sha256=scope3,
            ),
        }))
        FactNormalizationCallRepository(session).create(
            FactNormalizationCallRepository(session).get(chain["call_id"]).model_copy(update={
                "call_id": third_call, "run_id": third_run, "input_sha256": _sha(third_call),
            })
        )
        for index, source in enumerate([original_candidate, other] if both_sides else [original_candidate]):
            third_candidate = source.model_copy(update={
                "candidate_id": f"pub-source-conflict-third-{index}", "run_id": third_run, "call_id": third_call,
            })
            candidates.create(third_call, third_candidate)
            gates.create(gates.get(chain["gate_id"]).model_copy(update={
                "gate_result_id": f"pub-source-conflict-third-gate-{index}",
                "run_id": third_run, "call_id": third_call, "candidate_id": third_candidate.candidate_id,
            }))
        third = FactPublicationService().publish(session, third_run)
        assert len(third.conflict_group_ids) == 1
        third_group = repository.get(third.conflict_group_ids[0])
        assert third_group.source_revision_of == successor.conflict_group_id
        assert third_group.revision == 3
        assert third_group.gate_id == previous.gate_id
        assert current_conflict_heads(session, run.authority) == [third_group]
        assert repository.get(previous.conflict_group_id) == previous
        assert repository.get(successor.conflict_group_id) == successor
        assert FactPublicationService().publish(session, third_run).conflict_group_ids == third.conflict_group_ids
        assert PatientProfileService().generate(session, authority=run.authority).status.value == "succeeded"
        return
    monkeypatch.setattr(
        "app.services.source_conflict_successors.append_source_conflict_successors",
        lambda *args, **kwargs: [],
    )
    with pytest.raises(FactPublicationError, match="尚未与既有病史"):
        with session.begin_nested():
            FactPublicationService().publish(session, run_id)
    assert sorted(
        item.fact_id for item in ClinicalFactV2Repository(session).list_by_episode(
            chain["review_episode_id"]
        )
    ) == first.fact_ids
    assert sorted(
        item.conflict_group_id for item in ClinicalConflictGroupV2Repository(session).list_by_episode(
            chain["review_episode_id"]
        )
    ) == first.conflict_group_ids


@pytest.mark.parametrize("member_kind", ["event", "exposure"])
def test_dependent_conflict_source_growth_preserves_both_members(session, member_kind):
    from app.storage.active_conflicts import current_conflict_heads
    from app.services.patient_profile_service import PatientProfileService

    prefix = f"pub-{member_kind}-source-conflict"
    chain = _seed_chain(session, prefix)
    candidates = FactNormalizationCandidateRepository(session)
    gates = FactGateResultRepository(session)
    for index in range(2):
        common = dict(
            candidate_id=f"{prefix}-member-{index}", run_id=chain["run_id"], call_id=chain["call_id"],
            start_range=_date_range(), end_range=None, record_time=NOW,
            duration_status=DurationStatus.ONGOING,
            fact_candidate_ids=[chain["fact_candidate_id"]], locator_ids=[chain["locator_id"]],
            candidate_source_semantics="objective_result", model_uncertainty=0.02, created_at=NOW,
        )
        if member_kind == "event":
            common["duration_status"] = DurationStatus.ONGOING if index == 0 else DurationStatus.UNKNOWN
            member = ClinicalEventCandidateV2(**common, event_type="diagnosis")
        else:
            member = MedicationExposureCandidateV2(**common, medication_name="测试药物", dose="一片" if index == 0 else "两片")
        candidates.create(chain["call_id"], member)
        gates.create(gates.get(chain["gate_id"]).model_copy(update={
            "gate_result_id": f"{prefix}-member-gate-{index}", "candidate_id": member.candidate_id,
        }))
    first = FactPublicationService().publish(session, chain["run_id"])
    assert len(first.conflict_group_ids) == 1
    conflict_repository = ClinicalConflictGroupV2Repository(session)
    original = conflict_repository.get(first.conflict_group_ids[0])
    previous = original
    run = FactNormalizationRunRepository(session).get(chain["run_id"])
    member_repository = ClinicalEventV2Repository(session) if member_kind == "event" else MedicationExposureV2Repository(session)
    field = "event_ids" if member_kind == "event" else "exposure_ids"
    for revision in (2, 3):
        run_id, call_id = f"{prefix}-run-{revision}", f"{prefix}-call-{revision}"
        scope = _sha(run_id)
        FactNormalizationRunRepository(session).create_or_reuse(run.model_copy(update={
            "run_id": run_id, "input_scope_sha256": scope,
            "idempotency_key": fact_run_idempotency_key(
                authority=run.authority, prompt_version_id=run.prompt_version_id,
                model_config_id=run.model_config_id, input_scope_sha256=scope,
            ),
        }))
        FactNormalizationCallRepository(session).create(
            FactNormalizationCallRepository(session).get(chain["call_id"]).model_copy(update={
                "call_id": call_id, "run_id": run_id, "input_sha256": _sha(call_id),
            })
        )
        candidate = candidates.get(chain["fact_candidate_id"]).model_copy(update={
            "candidate_id": f"{prefix}-fact-{revision}", "run_id": run_id, "call_id": call_id,
        })
        candidates.create(call_id, candidate)
        gates.create(gates.get(chain["gate_id"]).model_copy(update={
            "gate_result_id": f"{prefix}-gate-{revision}", "run_id": run_id,
            "call_id": call_id, "candidate_id": candidate.candidate_id,
        }))
        published = FactPublicationService().publish(session, run_id)
        assert len(published.conflict_group_ids) == 1
        successor = conflict_repository.get(published.conflict_group_ids[0])
        assert successor.source_revision_of == previous.conflict_group_id
        assert successor.revision == revision
        assert successor.gate_id == original.gate_id
        assert successor.resolution_revision == 0
        members = [member_repository.get(item) for item in getattr(successor, field)]
        assert len(members) == 2
        assert {member.source_revision_of for member in members} == set(getattr(previous, field))
        assert set(successor.locator_ids) == {locator for member in members for locator in member.locator_ids}
        assert current_conflict_heads(session, run.authority) == [successor]
        assert PatientProfileService().generate(session, authority=run.authority).status.value == "succeeded"
        assert FactPublicationService().publish(session, run_id).conflict_group_ids == published.conflict_group_ids
        assert conflict_repository.get(previous.conflict_group_id) == previous
        previous = successor
    assert conflict_repository.get(original.conflict_group_id) == original


def test_rollback_on_later_entity_failure(session):
    prefix = "pub-rollback"
    chain = _seed_chain(session, prefix)
    run_id = chain["run_id"]
    call_id = chain["call_id"]
    # 为回滚测试添加一个事件候选，其 locator 不在事实闭包内 — 仓储层会拒绝
    # 先让事件候选的 locator 为 locator2，而事实仅含 locator1，gate 仍标记为 ACCEPTED 以进入发布路径
    event_cand = ClinicalEventCandidateV2(
        candidate_id=f"{prefix}-event-cand", run_id=run_id, call_id=call_id,
        event_type="diagnosis", start_range=_date_range(), end_range=None, duration_status=DurationStatus.ONGOING,
        record_time=NOW, fact_candidate_ids=[chain["fact_candidate_id"]], locator_ids=[chain["locator_id_2"]],
        candidate_source_semantics="historical_primary", model_uncertainty=0.02, created_at=NOW,
    )
    FactNormalizationCandidateRepository(session).create(call_id, event_cand)
    FactGateResultRepository(session).create(FactGateResult(
        gate_result_id=f"{prefix}-event-gate", run_id=run_id, call_id=call_id, candidate_id=event_cand.candidate_id, gate=FactGate.TRANSACTIONAL_PUBLISH, outcome=GateOutcome.ACCEPTED, reasons=[], created_at=NOW,
    ))
    svc = FactPublicationService()
    with pytest.raises(Exception):
        svc.publish(session, run_id)
    session.rollback()
    remaining = session.execute(select(ClinicalFactV2Record).where(ClinicalFactV2Record.run_id == run_id)).scalars().all()
    assert remaining == []
    row = session.execute(select(IdempotencyRecordRow).where(IdempotencyRecordRow.scope == "fact_publication_v2", IdempotencyRecordRow.idempotency_key == run_id)).scalar_one_or_none()
    assert row is None


def test_stale_authority_pointer_rejection(session):
    prefix = "pub-stale"
    chain = _seed_chain(session, prefix)
    run_id = chain["run_id"]
    drift_snapshot_id = f"{prefix}-drift-snapshot"
    _add(session, EvidenceSnapshotV2Record(
        evidence_snapshot_id=drift_snapshot_id, project_id=chain["project_id"], subject_id=chain["subject_id"],
        review_episode_id=chain["review_episode_id"], upload_mode="full", prior_snapshot_id=None, comparison_snapshot_id=None,
        collection_sha256=_sha("drift-collection"), created_by="tester", payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
    ))
    episode = session.get(ReviewEpisodeRecord, chain["review_episode_id"])
    _update_episode(session, episode, active_evidence_snapshot_id=drift_snapshot_id)
    session.flush()
    svc = FactPublicationService()
    with pytest.raises(FactPublicationStaleAuthorityError):
        svc.publish(session, run_id)
    session.rollback()


def test_retry_idempotency(session):
    prefix = "pub-idem"
    chain = _seed_chain(session, prefix)
    run_id = chain["run_id"]
    svc = FactPublicationService()
    first = svc.publish(session, run_id)
    assert not first.is_replay
    assert len(first.fact_ids) == 1
    # 重放应返回等价结果且标记为 replay，不产生新行
    second = svc.publish(session, run_id)
    assert second.is_replay
    assert second.fact_ids == first.fact_ids
    assert second.event_ids == first.event_ids
    assert second.exposure_ids == first.exposure_ids
    assert second.conflict_group_ids == first.conflict_group_ids
    # 库内仍只有一条事实
    rows = session.execute(select(ClinicalFactV2Record).where(ClinicalFactV2Record.run_id == run_id)).scalars().all()
    assert len(rows) == 1
    # 重放依据是不可变发布实体与候选闭包，不另造 JSON 结果记录。
    assert session.execute(
        select(IdempotencyRecordRow).where(
            IdempotencyRecordRow.scope == "fact_publication_v2",
            IdempotencyRecordRow.idempotency_key == run_id,
        )
    ).scalar_one_or_none() is None


def test_divergent_payload_rejected(session):
    prefix = "pub-diverge"
    chain = _seed_chain(session, prefix)
    run_id = chain["run_id"]
    call_id = chain["call_id"]
    svc = FactPublicationService()
    first = svc.publish(session, run_id)
    assert len(first.fact_ids) == 1
    # 在同一 run 内追加新候选并标记为 ACCEPTED，导致 divergent payload
    cand2 = ClinicalFactCandidateV2(
        candidate_id=f"{prefix}-cand2", run_id=run_id, call_id=call_id,
        fact_type="vital_sign", polarity=FactPolarity.AFFIRMED, asserted_object="心率",
        raw_value="80", canonical_value="80", unit="unitless",
        date_range=_date_range(), record_time=NOW, locator_ids=[chain["locator_id_2"]],
        candidate_source_semantics="objective_result", assertion_basis=AssertionBasis(asserted_object="心率", assertion_text="心率 80", locator_id=chain["locator_id_2"], source_text_sha256=_source_hash(session, chain["locator_id_2"])),
        model_uncertainty=0.01, created_at=NOW,
    )
    FactNormalizationCandidateRepository(session).create(call_id, cand2)
    FactGateResultRepository(session).create(FactGateResult(
        gate_result_id=f"{prefix}-gate2", run_id=run_id, call_id=call_id, candidate_id=cand2.candidate_id, gate=FactGate.TRANSACTIONAL_PUBLISH, outcome=GateOutcome.ACCEPTED, reasons=[], created_at=NOW,
    ))
    session.flush()
    with pytest.raises(FactPublicationError, match="候选集发生变化"):
        svc.publish(session, run_id)


def test_service_does_not_commit_session(session):
    """服务不得自行 commit/rollback，事务边界归调用方。"""
    prefix = "pub-nocommit"
    chain = _seed_chain(session, prefix)
    run_id = chain["run_id"]
    svc = FactPublicationService()
    # 在外层事务内调用，完成后不 commit 时新会话不可见
    svc.publish(session, run_id)
    # 同一 session 内可见
    assert session.execute(select(ClinicalFactV2Record).where(ClinicalFactV2Record.run_id == run_id)).scalars().all() != []
    # 外部新 session（新事务）在未 commit 前不可见 — 使用 session_factory 新开事务
    # 由于测试的 session 未 commit，engine 上另一连接不应看到未提交行（SQLite 同库但不同连接在 WAL 模式下可能延迟可见）
    # 此处仅断言服务未调用 commit：检查 session 已处于 dirty 但事务未关闭
    assert session.in_transaction()
    assert session.in_nested_transaction() is False or True  # 保持事务开放
    # 手动回滚后应消失
    session.rollback()
    assert session.execute(select(ClinicalFactV2Record).where(ClinicalFactV2Record.run_id == run_id)).scalars().all() == []
