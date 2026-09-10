"""Phase 5 EvidenceExpectation v2 覆盖投影测试（Slice 5.4，worker_03）。

覆盖 worker_03 的确定性投影语义与持久化边界：

- 完整状态优先级/矩阵：not_due / observed / observed_weak / referenced_missing /
  absent 五类状态与细分缺口类型；覆盖弱于引用缺失强于 absent；
- 较弱转述事实 + 定位 → observed_weak + 溯源提醒，绝不重复报无证据；
- 显式资料要求绑定 / 同权威元组隔离：未绑定或异权威事实不构成覆盖；
- revision 追加写：同内容幂等、变化只追加链头 +1、回退/跳号拒绝；
- 定位链接与 payload 双向镜像：删链接/改哈希即拒绝还原；
- 批量投影一个模板恰好一条期望（无双重报告）。

旧 ``evidence_expectations`` 占位表不进入本测试路径。
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select, update

from app.domain.contracts.enums import (
    DatePrecision,
    DisambiguationOutcome,
    FactCallStatus,
    FactGate,
    FactNormalizationRunStatus,
    FactPolarity,
    GateOutcome,
    LocatorAuthenticity,
    LocatorPrecision,
    LocatorSourceLayer,
    ReviewStage,
    SnapshotMemberOrigin,
    SnapshotStatus,
    SourceStrength,
    StudyPhase,
    UploadMode,
)
from app.domain.contracts.enums import ExpectationStatus, GapType
from app.domain.contracts.evidence import EvidenceExpectationTemplate
from app.domain.contracts.evidence_expectations_v2 import (
    CoverageGapSignal,
    CoverageObservation,
    EvidenceExpectationV2,
    canonical_input_gap_signals,
    expectation_identity,
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
    ClinicalFactCandidateV2,
    ClinicalFactV2,
    FactAuthority,
    FactGateResult,
    FactNormalizationCall,
    FactNormalizationRun,
    PartialDateRange,
    clinical_fact_stable_identity,
    fact_run_idempotency_key,
)
from app.domain.contracts.review import ReviewEpisode
from app.domain.contracts.rules import EvidenceRequirement
from app.domain.publication import (
    evidence_processing_manifest_hash,
    evidence_snapshot_collection_hash,
)
from app.projections.evidence_expectation_templates import (
    template_identity,
    template_projection_sha256,
)
from app.projections.evidence_expectations import (
    ProjectionInputError,
    project_expectation,
    project_expectations,
)
from app.services.evidence_expectation_projection_service import (
    EvidenceExpectationProjectionError,
    EvidenceExpectationProjectionService,
)
from app.storage.codecs import PersistedContractInvalid, encode_contract
from app.storage.evidence_expectation_repository import (
    EvidenceExpectationV2Repository,
)
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
from app.storage.fact_authority import FactAuthorityError
from app.storage.fact_repositories import (
    ClinicalFactV2Repository,
    FactGateResultRepository,
    FactNormalizationCandidateRepository,
    FactNormalizationCallRepository,
    FactNormalizationRunRepository,
    FactRevisionChainError,
    Phase5RepositoryError,
)
from app.storage.facts_models import (
    EvidenceExpectationV2Record,
    FactEvidenceLocatorLinkRecord,
)
from app.storage.models import (
    EvidenceExpectationTemplateRecord,
    EvidenceRequirementRecord,
    ModelConfigRecord,
    ProjectRecord,
    PromptVersionRecord,
    ProtocolDocumentVersionRecord,
    ReviewEpisodeRecord,
    RuleSetRecord,
    SubjectRecord,
    WorkflowStageRecord,
)
from app.storage.ocr_models import (
    EvidenceProcessingRevisionRecord,
    PageArtifactRecord,
)
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


def _date_range() -> PartialDateRange:
    return PartialDateRange(
        source_text="2026-03-01",
        precision=DatePrecision.DAY,
        lower_bound=date(2026, 3, 1),
        upper_bound=date(2026, 3, 1),
    )


def _seed_base(session, prefix: str) -> dict[str, str]:
    """播种一条完整活动证据链（protocol/rule_set/project/subject/已激活 episode/
    snapshot_v2/source doc/page artifact/base+complete 修订/locator/run/call）。
    返回全部 id 供权威元组、模板与发布事实引用。"""
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

    _add(session, ProtocolDocumentVersionRecord(
        protocol_version_id=protocol_version_id, protocol_code="P",
        official_version="v1", official_date_value=None,
        official_date_precision="unknown", sha256=_sha("protocol"),
        integrity_manifest_sha256=_sha("integrity"),
        authority_record_sha256=_sha("authority"),
        authority_confirmation_id="confirm", authority_gate_result_id="agr",
        integrity_gate_result_id="igr",
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
    ))
    _add(session, RuleSetRecord(
        rule_set_id=rule_set_id, revision=1, protocol_version_id=protocol_version_id,
        study_phase="phase_iii", payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA,
        created_at=NOW,
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
    _add(session, ReviewEpisodeRecord(
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
    # 已激活审核节点：活动指针对成对（用 core UPDATE 避免 ORM 自增 revision）。
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
        member_id=f"{prefix}-member", snapshot_id=snapshot_id,
        logical_document_id=f"{prefix}-log", source_document_version_id=doc_id,
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
            evidence_snapshot_id=snapshot_id, project_id=project_id,
            subject_id=subject_id, review_episode_id=episode_id,
            upload_mode=UploadMode.FULL, members=[member_contract],
            collection_sha256=collection_sha256, status=SnapshotStatus.STAGED,
            created_at=NOW, created_by="tester",
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
            file_name="f.pdf", media_type="application/pdf", page_count=1,
            project_id=project_id, subject_id=subject_id,
            review_episode_id=episode_id, version_number=1,
            created_at=NOW, created_by="tester",
        ),
    )
    episode_payload_json, episode_payload_sha256 = encode_contract(
        ReviewEpisode(
            review_episode_id=episode_id, subject_id=subject_id,
            project_id=project_id, rule_set_id=rule_set_id,
            study_phase="phase_iii", stage="screening",
            protocol_version_id=protocol_version_id, rule_set_revision=1,
            active_evidence_snapshot_id=snapshot_id,
            active_evidence_processing_revision_id=complete_revision_id,
        )
    )
    session.execute(
        update(ReviewEpisodeRecord)
        .where(ReviewEpisodeRecord.review_episode_id == episode_id)
        .values(payload_json=episode_payload_json, payload_sha256=episode_payload_sha256)
    )
    session.expire_all()
    complete_manifest_sha256 = evidence_processing_manifest_hash(entries=[])
    complete_record = session.get(EvidenceProcessingRevisionRecord, complete_revision_id)
    complete_record.manifest_sha256 = complete_manifest_sha256
    _bind_payload(
        complete_record,
        CompleteEvidenceProcessingRevision(
            evidence_processing_revision_id=complete_revision_id,
            evidence_snapshot_id=snapshot_id, project_id=project_id,
            subject_id=subject_id, review_episode_id=episode_id,
            base_processing_revision_id=base_revision_id,
            producer_candidate_id=f"{prefix}-candidate",
            candidate_input_sha256=_sha("candidate-input"),
            manifest=[], manifest_sha256=complete_manifest_sha256,
            locator_ids=[locator_id, locator_id_2],
            completion_manifest_sha256=_sha("completion-manifest"),
            created_at=NOW, created_by="tester",
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
                locator_id=locator_id_value, page_artifact_id=page_artifact_id,
                source_document_version_id=doc_id, page_number=1,
                source_layer=LocatorSourceLayer.RAW_OCR,
                source_text_sha256=source_hash, target_id=target_id,
                precision=LocatorPrecision.TEXT_RANGE, text_start=start,
                text_end=end, excerpt=excerpt,
                disambiguation=DisambiguationOutcome.UNIQUE_MATCH,
                locator_algorithm_version="v1",
                authenticity=LocatorAuthenticity.DEGRADED,
                degradation_reason="text-only", created_at=NOW,
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
        "workflow_stage_id": f"{prefix}-stage",
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


def _template(
    session,
    ids: dict[str, str],
    *,
    requirement_id: str,
    fact_type: str,
    due_stage: ReviewStage,
    requires_contemporaneous_objective_source: bool = False,
    allows_screening_record_transcription: bool = True,
    required_source_types: tuple[str, ...] = (),
    description: str = "资料核对要求",
) -> EvidenceExpectationTemplate:
    """种子模板记录（要求 FK 行 + 模板行）并返回合法合同。"""
    requirement_id = f"slice54-{requirement_id}"
    requirement = EvidenceRequirement(
        requirement_id=requirement_id,
        rule_component_id=None,
        procedure_catalog_item_id=f"{ids['run_id']}-catalog",
        fact_type=fact_type,
        required_source_types=list(required_source_types),
        allows_screening_record_transcription=allows_screening_record_transcription,
        requires_contemporaneous_objective_source=(
            requires_contemporaneous_objective_source
        ),
        due_stage=due_stage,
        description=description,
    )
    requirement_row = _add(session, EvidenceRequirementRecord(
        rule_set_id=ids["rule_set_id"], rule_set_revision=1,
        requirement_id=requirement_id, rule_component_id=None,
        procedure_catalog_item_id=f"{ids['run_id']}-catalog",
        fact_type=fact_type, due_stage=due_stage.value,
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
    ))
    _bind_payload(requirement_row, requirement)
    template_id = template_identity(ids["rule_set_id"], 1, requirement_id)
    projection_sha256 = template_projection_sha256(
        rule_set_id=ids["rule_set_id"], revision=1,
        requirement_id=requirement_id, due_stage=due_stage,
        study_phase=StudyPhase.PHASE_III,
        workflow_stage_id=ids["workflow_stage_id"], fact_type=fact_type,
        required_source_types=required_source_types,
        requires_contemporaneous_objective_source=(
            requires_contemporaneous_objective_source
        ),
        allows_screening_record_transcription=(
            allows_screening_record_transcription
        ),
        description=description,
    )
    template = EvidenceExpectationTemplate(
        template_id=template_id,
        rule_set_id=ids["rule_set_id"],
        rule_set_revision=1,
        requirement_id=requirement_id,
        due_stage=due_stage,
        study_phase=StudyPhase.PHASE_III,
        workflow_stage_id=ids["workflow_stage_id"],
        fact_type=fact_type,
        required_source_types=list(required_source_types),
        requires_contemporaneous_objective_source=(
            requires_contemporaneous_objective_source
        ),
        allows_screening_record_transcription=(
            allows_screening_record_transcription
        ),
        description=description,
        projection_sha256=projection_sha256,
        created_at=NOW,
    )
    template_row = _add(session, EvidenceExpectationTemplateRecord(
        template_id=template_id, rule_set_id=ids["rule_set_id"],
        rule_set_revision=1, requirement_id=requirement_id,
        due_stage=due_stage.value, study_phase="phase_iii",
        workflow_stage_id=ids["workflow_stage_id"], fact_type=fact_type,
        required_source_types=list(required_source_types),
        projection_sha256=projection_sha256,
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
    ))
    _bind_payload(template_row, template)
    return template


def _seed_unbound_ruleset(session) -> str:
    """种子一条独立规则集链（protocol/rule_set/workflow_stage + 模板），返回模板 ID。

    模板属于另一规则集修订，用于验证仓储拒绝「未绑定权威元组规则修订」的投影。
    """
    prefix = "u1"
    protocol_version_id = f"{prefix}-protocol"
    rule_set_id = f"{prefix}-ruleset"
    _add(session, ProtocolDocumentVersionRecord(
        protocol_version_id=protocol_version_id, protocol_code="U",
        official_version="v1", official_date_value=None,
        official_date_precision="unknown", sha256=_sha("u-protocol"),
        integrity_manifest_sha256=_sha("u-integrity"),
        authority_record_sha256=_sha("u-authority"),
        authority_confirmation_id="confirm", authority_gate_result_id="agr",
        integrity_gate_result_id="igr",
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
    ))
    _add(session, RuleSetRecord(
        rule_set_id=rule_set_id, revision=1,
        protocol_version_id=protocol_version_id, study_phase="phase_iii",
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
    ))
    _add(session, WorkflowStageRecord(
        workflow_stage_id=f"{prefix}-stage",
        protocol_version_id=protocol_version_id, stage="screening",
        study_phase="phase_iii",
        payload_json=_PAYLOAD, payload_sha256=_PAYLOAD_SHA, created_at=NOW,
    ))
    template = _template(
        session,
        {"rule_set_id": rule_set_id, "run_id": prefix,
         "workflow_stage_id": f"{prefix}-stage"},
        requirement_id="req-unbound", fact_type="vital_sign",
        due_stage=ReviewStage.SCREENING)
    return template.template_id


_HASH_BY_LOCATOR: dict[str, str] = {}


def _publish_fact(
    session,
    ids: dict[str, str],
    *,
    fact_id: str,
    gate_id: str,
    candidate_id: str,
    fact_type: str,
    source_strength: SourceStrength,
    asserted_object: str,
    value: str,
    unit: str,
    locator_ids: list[str],
    supported_requirement_ids: list[str] | None = None,
) -> ClinicalFactV2:
    """候选 → 事务发布门禁 → 已发布事实（同权威元组与来源强度）。"""
    basis_locator = locator_ids[0]
    basis = AssertionBasis(
        asserted_object=asserted_object,
        assertion_text=f"{asserted_object} {value}",
        locator_id=basis_locator,
        source_text_sha256=_HASH_BY_LOCATOR[basis_locator],
    )
    authority = _authority(ids)
    if supported_requirement_ids is None:
        supported_requirement_ids = sorted(
            row.requirement_id
            for row in session.execute(select(EvidenceRequirementRecord)).scalars()
            if row.rule_set_id == authority.rule_set_id
            and row.rule_set_revision == authority.rule_set_revision
            and row.fact_type == fact_type
        )
    FactNormalizationCandidateRepository(session).create(
        ids["call_id"],
        ClinicalFactCandidateV2(
            candidate_id=candidate_id, run_id=ids["run_id"], call_id=ids["call_id"],
            fact_type=fact_type, polarity=FactPolarity.AFFIRMED,
            supported_requirement_ids=supported_requirement_ids,
            asserted_object=asserted_object, raw_value=value, canonical_value=value,
            unit=unit, date_range=_date_range(), record_time=NOW,
            locator_ids=locator_ids, candidate_source_semantics="objective_result",
            assertion_basis=basis, model_uncertainty=0.0, created_at=NOW,
        ),
    )
    FactGateResultRepository(session).create(FactGateResult(
        gate_result_id=gate_id, run_id=ids["run_id"], call_id=ids["call_id"],
        candidate_id=candidate_id, gate=FactGate.TRANSACTIONAL_PUBLISH,
        outcome=GateOutcome.ACCEPTED, reasons=[], created_at=NOW,
    ))
    fact = ClinicalFactV2(
        fact_id=fact_id, run_id=ids["run_id"], gate_id=gate_id,
        authority=authority, fact_type=fact_type, polarity=FactPolarity.AFFIRMED,
        supported_requirement_ids=supported_requirement_ids,
        asserted_object=asserted_object, value=value, unit=unit,
        source_strength=source_strength, date_range=_date_range(), record_time=NOW,
        locator_ids=locator_ids, assertion_basis=basis, revision=1, created_at=NOW,
        stable_identity=clinical_fact_stable_identity(
            authority=authority, fact_type=fact_type, asserted_object=asserted_object,
            polarity=FactPolarity.AFFIRMED, value=value, unit=unit,
            date_range=_date_range(),
        ),
    )
    published = ClinicalFactV2Repository(session).create(
        fact.model_copy(
            update={"source_strength": SourceStrength.CONTEMPORANEOUS_OBJECTIVE}
        )
    )
    if source_strength == published.source_strength:
        return published
    return published.model_copy(update={"source_strength": source_strength})


def _seed_valid_base(session, prefix: str, *, fixture_index: int = 0):
    return seed_valid_fact_chain(
        session, prefix, fixture_index=fixture_index, create_run=True
    )


@pytest.fixture
def chain(session):
    """head 库会话 + 已激活权威链；测试回滚。"""
    ids = _seed_valid_base(session, "t1")
    _HASH_BY_LOCATOR.update({
        ids["locator_id"]: session.get(
            EvidenceLocatorArtifactRecord, ids["locator_id"]
        ).source_text_sha256,
        ids["locator_id_2"]: session.get(
            EvidenceLocatorArtifactRecord, ids["locator_id_2"]
        ).source_text_sha256,
    })
    return ids


@pytest.fixture
def chain_other(session):
    """第二条独立审核节点链（跨权威隔离测试用）。"""
    ids = _seed_valid_base(session, "t2", fixture_index=1)
    _HASH_BY_LOCATOR.update({
        ids["locator_id"]: session.get(
            EvidenceLocatorArtifactRecord, ids["locator_id"]
        ).source_text_sha256,
        ids["locator_id_2"]: session.get(
            EvidenceLocatorArtifactRecord, ids["locator_id_2"]
        ).source_text_sha256,
    })
    return ids


def _project(ids, template, *, observations=(), gap_signals=(), revision=1, **overrides):
    structured_observations = tuple(
        item
        if isinstance(item, CoverageObservation)
        else CoverageObservation(fact=item, source_types=["检验报告"])
        for item in observations
    )
    return project_expectation(
        template=template,
        authority=_authority(ids, **{k: v for k, v in overrides.items()}),
        current_stage=ReviewStage.SCREENING,
        observations=structured_observations,
        gap_signals=gap_signals,
        revision=revision,
        created_at=NOW,
    )


def test_projection_service_uses_authoritative_episode_stage(chain, session):
    template = _template(
        session,
        chain,
        requirement_id="baseline-only",
        fact_type="vital_sign",
        due_stage=ReviewStage.BASELINE,
    )

    projected = EvidenceExpectationProjectionService().project(
        session,
        authority=_authority(chain),
        gap_signals=[],
        created_at=NOW,
    )

    by_template = {item.template_id: item for item in projected}
    assert by_template[template.template_id].status == ExpectationStatus.NOT_DUE


def test_projection_service_rejects_ambiguous_same_stage_workflow_node(
    chain, session
):
    sibling_stage_id = "t1-screening-sibling"
    _add(
        session,
        WorkflowStageRecord(
            workflow_stage_id=sibling_stage_id,
            protocol_version_id=chain["protocol_version_id"],
            stage="screening",
            study_phase="phase_iii",
            payload_json=_PAYLOAD,
            payload_sha256=_PAYLOAD_SHA,
            created_at=NOW,
        ),
    )
    _template(
        session,
        {**chain, "workflow_stage_id": sibling_stage_id},
        requirement_id="sibling-screening",
        fact_type="vital_sign",
        due_stage=ReviewStage.SCREENING,
    )

    with pytest.raises(
        EvidenceExpectationProjectionError,
        match="同一阶段的另一流程节点",
    ):
        EvidenceExpectationProjectionService().project(
            session,
            authority=_authority(chain),
            gap_signals=[],
            created_at=NOW,
        )


# ---------------------------------------------------------------------------
# 1) 完整状态优先级 / 矩阵
# ---------------------------------------------------------------------------


def test_status_precedence_matrix(chain, session):
    """五类状态 × 代表性缺口：每个模板恰好得到预期状态与细分缺口。"""
    t_observed = _template(session, chain, requirement_id="req-obs",
                           fact_type="vital_sign", due_stage=ReviewStage.SCREENING)
    t_weak = _template(session, chain, requirement_id="req-weak",
                       fact_type="medical_history", due_stage=ReviewStage.SCREENING)
    t_contemp = _template(session, chain, requirement_id="req-contemp",
                          fact_type="heart_auscultation",
                          due_stage=ReviewStage.SCREENING,
                          requires_contemporaneous_objective_source=True)
    t_ref = _template(session, chain, requirement_id="req-ref",
                      fact_type="referenced_lab", due_stage=ReviewStage.SCREENING)
    t_absent = _template(session, chain, requirement_id="req-absent",
                         fact_type="procedure_done", due_stage=ReviewStage.SCREENING)
    t_future = _template(session, chain, requirement_id="req-future",
                         fact_type="baseline_vital", due_stage=ReviewStage.BASELINE)

    observed_fact = _publish_fact(
        session, chain, fact_id="f-obs", gate_id="g-obs", candidate_id="c-obs",
        fact_type="vital_sign", source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="血压", value="120/80", unit="unitless",
        locator_ids=[chain["locator_id"]],
    )
    weak_fact = _publish_fact(
        session, chain, fact_id="f-weak", gate_id="g-weak", candidate_id="c-weak",
        fact_type="medical_history",
        source_strength=SourceStrength.SCREENING_RECORD_TRANSCRIPTION,
        asserted_object="既往史", value="高血压病史", unit="unitless",
        locator_ids=[chain["locator_id"]],
    )
    weak_auscultation_fact = _publish_fact(
        session, chain, fact_id="f-weak-ausc", gate_id="g-weak-ausc",
        candidate_id="c-weak-ausc", fact_type="heart_auscultation",
        source_strength=SourceStrength.SCREENING_RECORD_TRANSCRIPTION,
        asserted_object="心音", value="闻及杂音", unit="unitless",
        locator_ids=[chain["locator_id_2"]],
    )

    cases = [
        (t_future, (), (), ExpectationStatus.NOT_DUE, GapType.FUTURE_STAGE_NOT_DUE),
        (t_observed, (observed_fact,), (),
         ExpectationStatus.OBSERVED, None),
        (t_weak, (weak_fact,), (),
         ExpectationStatus.OBSERVED_WEAK, GapType.PROVENANCE_FOLLOWUP),
        (t_contemp, (weak_auscultation_fact,), (),
         ExpectationStatus.OBSERVED_WEAK, GapType.PROVENANCE_FOLLOWUP),
        (t_ref, (), (CoverageGapSignal(
            kind=GapType.REFERENCED_FILE_MISSING,
            referenced_file_id="file-xyz", detail="外院化验单已引用未提供"),),
         ExpectationStatus.REFERENCED_MISSING, GapType.REFERENCED_FILE_MISSING),
        (t_absent, (), (CoverageGapSignal(
            kind=GapType.REQUIRED_PROCEDURE_NOT_DONE, detail="心电图检查未执行"),),
         ExpectationStatus.ABSENT, GapType.REQUIRED_PROCEDURE_NOT_DONE),
    ]
    for template, observations, signals, status, gap_type in cases:
        projected = _project(chain, template, observations=observations,
                             gap_signals=signals)
        assert projected.status == status, (template.requirement_id, projected)
        assert projected.gap_type == gap_type, (template.requirement_id, projected)

    not_due = _project(chain, t_future)
    assert not_due.coverage_fact_ids == [] and not_due.locator_ids == []
    observed = _project(chain, t_observed, observations=(observed_fact,))
    assert observed.source_coverage == "complete"
    assert observed.provenance_followup is False
    weak = _project(chain, t_weak, observations=(weak_fact,))
    assert weak.source_coverage == "weak"
    assert weak.provenance_followup is True
    assert weak.locator_ids == [chain["locator_id"]]
    assert weak.coverage_fact_ids == ["f-weak"]
    referenced = _project(chain, t_ref, gap_signals=(
        CoverageGapSignal(
            kind=GapType.REFERENCED_FILE_MISSING, referenced_file_id="file-xyz",
            detail="外院化验单已引用未提供"),))
    assert referenced.gap_detail == "外院化验单已引用未提供"


def test_absent_chooses_specific_supplied_gap_not_generic(chain, session):
    """到期无覆盖：选择供应方提供的具体当前缺口，绝不回退通用缺口。"""
    t = _template(session, chain, requirement_id="req-gaps",
                  fact_type="lab_result", due_stage=ReviewStage.SCREENING)
    # 多个具体缺口信号 → 按确定优先级选最高（流程未完成 > 结果字段缺失）。
    projected = _project(chain, t, gap_signals=[
        CoverageGapSignal(kind=GapType.RESULT_FIELDS_MISSING, detail="结果字段缺失"),
        CoverageGapSignal(kind=GapType.REQUIRED_PROCEDURE_NOT_DONE, detail="检查未执行"),
    ])
    assert projected.status == ExpectationStatus.ABSENT
    assert projected.gap_type == GapType.REQUIRED_PROCEDURE_NOT_DONE
    assert projected.gap_detail == "检查未执行"
    # 无任何结构化缺口信号 → 拒绝通用回退。
    with pytest.raises(ProjectionInputError, match="拒绝以通用缺口回退"):
        _project(chain, t)


def test_absent_accepts_explicit_professional_judgment_gap(chain, session):
    template = _template(
        session,
        chain,
        requirement_id="req-investigator-assessment",
        fact_type="investigator_assessment",
        due_stage=ReviewStage.SCREENING,
        required_source_types=("investigator_assessment",),
    )

    projected = _project(
        chain,
        template,
        gap_signals=[
            CoverageGapSignal(
                kind=GapType.PROFESSIONAL_JUDGMENT,
                detail="当前资料未见研究者书面判断",
            )
        ],
    )

    assert projected.status == ExpectationStatus.ABSENT
    assert projected.gap_type == GapType.PROFESSIONAL_JUDGMENT


@pytest.mark.parametrize("fallback_only", [False, True])
def test_verified_judgment_removes_only_default_unverified_notice(chain, session, fallback_only):
    template = _template(session, chain, requirement_id="req-confirmed-judgment",
        fact_type="investigator_assessment", due_stage=ReviewStage.SCREENING,
        required_source_types=("investigator_assessment",))
    fact = _publish_fact(session, chain, fact_id="judgment", gate_id="judgment-gate",
        candidate_id="judgment-candidate", fact_type="investigator_assessment",
        source_strength=SourceStrength.CURRENT_STUDY_CHART,
        asserted_object="检查项目", value="NCS", unit=None,
        locator_ids=[chain["locator_id"]], supported_requirement_ids=[template.requirement_id])
    result = _project(chain, template,
        observations=[CoverageObservation(fact=fact, source_types=["investigator_assessment"])],
        gap_signals=[CoverageGapSignal(kind=GapType.OBSERVATION_UNVERIFIED,
                                      fallback_only=fallback_only, detail="尚待核实")])
    assert result.status == (ExpectationStatus.OBSERVED if fallback_only else ExpectationStatus.OBSERVED_WEAK)


@pytest.mark.parametrize("parse_risk", [False, True])
@pytest.mark.parametrize("unverified", [False, True])
@pytest.mark.parametrize("source_types", [("investigator_assessment",),
                                          ("lab_report", "investigator_assessment")])
@pytest.mark.parametrize("document_type", ["检验报告", "病历资料"])
def test_lab_result_does_not_replace_required_written_judgment(chain, session, parse_risk, unverified, source_types, document_type):
    template = _template(session, chain, requirement_id="req-written-only",
        fact_type="investigator_assessment", due_stage=ReviewStage.SCREENING,
        required_source_types=source_types)
    fact = _publish_fact(session, chain, fact_id="lab-only", gate_id="lab-gate",
        candidate_id="lab-candidate", fact_type="lab_result",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="检查项目", value="10", unit="unitless",
        locator_ids=[chain["locator_id"]], supported_requirement_ids=[template.requirement_id])
    assert fact.authority == _authority(chain)
    assert template.requirement_id in fact.supported_requirement_ids
    signals = [CoverageGapSignal(
        kind=GapType.PROFESSIONAL_JUDGMENT, detail="未见研究者对该项结果的书面判断")]
    if parse_risk:
        signals.append(CoverageGapSignal(
            kind=GapType.OCR_OR_PARSE_RISK, detail="相关批注尚未完成判读"))
    if unverified:
        signals.append(CoverageGapSignal(
            kind=GapType.OBSERVATION_UNVERIFIED, detail="相关判断尚未核实"))
    result = _project(chain, template,
        observations=[CoverageObservation(fact=fact, source_types=[document_type])], gap_signals=signals)
    assert result.status != ExpectationStatus.OBSERVED
    if parse_risk:
        assert result.gap_type == GapType.OCR_OR_PARSE_RISK
        assert result.coverage_fact_ids == [fact.fact_id]
    elif unverified:
        assert result.gap_type == GapType.OBSERVATION_UNVERIFIED
        assert result.status == ExpectationStatus.OBSERVED_WEAK
        assert result.coverage_fact_ids == [fact.fact_id]
        assert not result.provenance_followup
    else:
        assert result.gap_type == GapType.PROFESSIONAL_JUDGMENT
        assert result.status == ExpectationStatus.ABSENT
        assert "书面判断" in result.gap_detail
    assert fact.locator_ids == [chain["locator_id"]]


def test_coverage_beats_referenced_missing(chain, session):
    """覆盖（含较弱覆盖）优先级高于引用缺失：弱事实 + 缺失文件信号 → 弱覆盖。"""
    t = _template(session, chain, requirement_id="req-prio",
                  fact_type="medical_history", due_stage=ReviewStage.SCREENING)
    weak_fact = _publish_fact(
        session, chain, fact_id="f-prio", gate_id="g-prio", candidate_id="c-prio",
        fact_type="medical_history",
        source_strength=SourceStrength.SCREENING_RECORD_TRANSCRIPTION,
        asserted_object="既往史", value="高血压病史", unit="unitless",
        locator_ids=[chain["locator_id"]],
    )
    projected = _project(chain, t, observations=(weak_fact,), gap_signals=[
        CoverageGapSignal(kind=GapType.REFERENCED_FILE_MISSING,
                          referenced_file_id="file-xyz"),
    ])
    assert projected.status == ExpectationStatus.OBSERVED_WEAK
    assert projected.gap_type == GapType.PROVENANCE_FOLLOWUP
    assert projected.provenance_followup is True


def test_complete_with_ocr_risk_is_weak_not_absent(chain, session):
    """完整覆盖 + 结构化 OCR/解析风险 → observed_weak(ocr_or_parse_risk)，非 absent。"""
    t = _template(session, chain, requirement_id="req-ocr",
                  fact_type="vital_sign", due_stage=ReviewStage.SCREENING)
    observed_fact = _publish_fact(
        session, chain, fact_id="f-ocr", gate_id="g-ocr", candidate_id="c-ocr",
        fact_type="vital_sign", source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="血压", value="120/80", unit="unitless",
        locator_ids=[chain["locator_id"]],
    )
    projected = _project(chain, t, observations=(observed_fact,), gap_signals=[
        CoverageGapSignal(kind=GapType.OCR_OR_PARSE_RISK, detail="页 1 OCR 风险"),
    ])
    assert projected.status == ExpectationStatus.OBSERVED_WEAK
    assert projected.gap_type == GapType.OCR_OR_PARSE_RISK
    assert projected.source_coverage == "complete"
    assert projected.coverage_fact_ids == ["f-ocr"]


def test_rejected_source_record_is_parse_risk_not_missing_record(chain, session):
    template = _template(
        session,
        chain,
        requirement_id="req-rejected-source",
        fact_type="vital_sign",
        due_stage=ReviewStage.SCREENING,
    )

    projected = _project(
        chain,
        template,
        gap_signals=[
            CoverageGapSignal(
                kind=GapType.OCR_OR_PARSE_RISK,
                detail="原始资料中发现相关记录，但尚未通过事实完整性核对",
            )
        ],
    )

    assert projected.status == ExpectationStatus.ABSENT
    assert projected.gap_type == GapType.OCR_OR_PARSE_RISK
    assert projected.gap_detail == "原始资料中发现相关记录，但尚未通过事实完整性核对"


def test_source_type_and_source_strength_are_independent(chain, session):
    """资料类型匹配不由来源强度代替；类型大小写和空格按合同规范化。"""
    template = _template(
        session,
        chain,
        requirement_id="req-source-type",
        fact_type="laboratory_result",
        due_stage=ReviewStage.SCREENING,
        required_source_types=("lab_report",),
    )
    fact = _publish_fact(
        session,
        chain,
        fact_id="f-source-type",
        gate_id="g-source-type",
        candidate_id="c-source-type",
        fact_type="laboratory_result",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="ALT",
        value="35",
        unit="U/L",
        locator_ids=[chain["locator_id"]],
    )

    matching = _project(
        chain,
        template,
        observations=(
            CoverageObservation(fact=fact, source_types=[" LAB_REPORT "]),
        ),
    )
    assert matching.status == ExpectationStatus.OBSERVED

    mismatching = _project(
        chain,
        template,
        observations=(
            CoverageObservation(fact=fact, source_types=["screening_record"]),
        ),
    )
    assert mismatching.status == ExpectationStatus.OBSERVED_WEAK
    assert mismatching.gap_type == GapType.PROVENANCE_FOLLOWUP
    assert mismatching.provenance_followup is True


def test_chinese_exam_report_satisfies_specific_ecg_report_source(chain, session):
    template = _template(
        session,
        chain,
        requirement_id="req-ecg-source-type",
        fact_type="ecg",
        due_stage=ReviewStage.SCREENING,
        required_source_types=("ecg_report",),
    )
    fact = _publish_fact(
        session,
        chain,
        fact_id="f-ecg-source-type",
        gate_id="g-ecg-source-type",
        candidate_id="c-ecg-source-type",
        fact_type="ecg",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="QTc",
        value="413",
        unit="ms",
        locator_ids=[chain["locator_id"]],
    )

    projected = _project(
        chain,
        template,
        observations=(CoverageObservation(fact=fact, source_types=["检查报告"]),),
    )

    assert projected.status == ExpectationStatus.OBSERVED
    assert projected.source_coverage == "complete"


def test_screening_transcription_respects_template_permission(chain, session):
    """同一转述事实仅在模板允许时形成较弱覆盖；禁止时保持真实缺口。"""
    allowed = _template(
        session,
        chain,
        requirement_id="req-transcription-allowed",
        fact_type="medical_history",
        due_stage=ReviewStage.SCREENING,
        allows_screening_record_transcription=True,
    )
    disallowed = _template(
        session,
        chain,
        requirement_id="req-transcription-disallowed",
        fact_type="medical_history",
        due_stage=ReviewStage.SCREENING,
        allows_screening_record_transcription=False,
    )
    fact = _publish_fact(
        session,
        chain,
        fact_id="f-transcription-permission",
        gate_id="g-transcription-permission",
        candidate_id="c-transcription-permission",
        fact_type="medical_history",
        source_strength=SourceStrength.SCREENING_RECORD_TRANSCRIPTION,
        asserted_object="既往过敏性鼻炎病程",
        value="超过3年",
        unit="unitless",
        locator_ids=[chain["locator_id"]],
    )
    observation = CoverageObservation(
        fact=fact,
        source_types=["screening_record"],
    )

    weak = _project(chain, allowed, observations=(observation,))
    assert weak.status == ExpectationStatus.OBSERVED_WEAK
    assert weak.gap_type == GapType.PROVENANCE_FOLLOWUP

    absent = _project(
        chain,
        disallowed,
        observations=(observation,),
        gap_signals=(
            CoverageGapSignal(
                kind=GapType.DESCRIPTION_INSUFFICIENT,
                detail="当前资料仅有筛选病历转述，未达到本项允许的来源要求",
            ),
        ),
    )
    assert absent.status == ExpectationStatus.ABSENT
    assert absent.gap_type == GapType.DESCRIPTION_INSUFFICIENT
    assert absent.coverage_fact_ids == []


# ---------------------------------------------------------------------------
# 2) 显式资料要求绑定 / 同权威元组隔离
# ---------------------------------------------------------------------------


def test_explicit_requirement_binding_allows_distinct_display_fact_type(chain, session):
    """展示分类不同但显式绑定同一资料要求时仍构成覆盖。"""
    t = _template(session, chain, requirement_id="req-iso-ft",
                  fact_type="vital_sign", due_stage=ReviewStage.SCREENING)
    other_type_fact = _publish_fact(
        session, chain, fact_id="f-other-type", gate_id="g-other-type",
        candidate_id="c-other-type", fact_type="medical_history",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="既往史", value="高血压病史", unit="unitless",
        locator_ids=[chain["locator_id"]],
        supported_requirement_ids=[t.requirement_id],
    )
    projected = _project(chain, t, observations=(other_type_fact,))
    assert projected.status == ExpectationStatus.OBSERVED
    assert projected.coverage_fact_ids == [other_type_fact.fact_id]


def test_authority_isolation(chain, chain_other, session):
    """同 fact_type 但不同权威元组的已发布事实绝不构成覆盖。"""
    t = _template(session, chain, requirement_id="req-iso-auth",
                  fact_type="vital_sign", due_stage=ReviewStage.SCREENING)
    other_authority_fact = _publish_fact(
        session, chain_other, fact_id="f-other-auth", gate_id="g-other-auth",
        candidate_id="c-other-auth", fact_type="vital_sign",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="血压", value="120/80", unit="unitless",
        locator_ids=[chain_other["locator_id"]],
    )
    projected = _project(chain, t, observations=(other_authority_fact,), gap_signals=[
        CoverageGapSignal(kind=GapType.DESCRIPTION_INSUFFICIENT, detail="描述不完整"),
    ])
    assert projected.status == ExpectationStatus.ABSENT
    assert projected.gap_type == GapType.DESCRIPTION_INSUFFICIENT


def test_repository_rejects_coverage_without_binding_or_with_wrong_authority(
    chain, chain_other, session
):
    """仓储边界：覆盖事实未绑定资料要求或权威元组不一致时拒绝投影。"""
    t = _template(session, chain, requirement_id="req-repo-iso",
                  fact_type="vital_sign", due_stage=ReviewStage.SCREENING)
    good = _publish_fact(
        session, chain, fact_id="f-good", gate_id="g-good", candidate_id="c-good",
        fact_type="vital_sign", source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="血压", value="120/80", unit="unitless",
        locator_ids=[chain["locator_id"]],
    )
    wrong_type = _publish_fact(
        session, chain, fact_id="f-wrong-type", gate_id="g-wrong-type",
        candidate_id="c-wrong-type", fact_type="medical_history",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="既往史", value="高血压病史", unit="unitless",
        locator_ids=[chain["locator_id"]],
    )
    other_authority = _publish_fact(
        session, chain_other, fact_id="f-other", gate_id="g-other",
        candidate_id="c-other", fact_type="vital_sign",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="血压", value="120/80", unit="unitless",
        locator_ids=[chain_other["locator_id"]],
    )
    repository = EvidenceExpectationV2Repository(session)
    good_expectation = _project(chain, t, observations=(good,))
    repository.project(good_expectation)

    with pytest.raises(Phase5RepositoryError, match="未显式绑定"):
        bad = good_expectation.model_copy(
            update={"coverage_fact_ids": ["f-wrong-type"]})
        repository.project(bad)
    with pytest.raises(Phase5RepositoryError, match="权威元组"):
        bad = good_expectation.model_copy(
            update={"coverage_fact_ids": ["f-other"]})
        repository.project(bad)


# ---------------------------------------------------------------------------
# 3) revision 追加写 + 幂等
# ---------------------------------------------------------------------------


def test_revision_append_only_and_idempotency(chain, session):
    """同内容幂等复用最新行；变化只允许链头 +1；回退/跳号拒绝；旧行保留。"""
    t = _template(session, chain, requirement_id="req-rev",
                  fact_type="vital_sign", due_stage=ReviewStage.SCREENING)
    fact = _publish_fact(
        session, chain, fact_id="f-rev", gate_id="g-rev", candidate_id="c-rev",
        fact_type="vital_sign", source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="血压", value="120/80", unit="unitless",
        locator_ids=[chain["locator_id"]],
    )
    repository = EvidenceExpectationV2Repository(session)
    first = _project(chain, t, observations=(fact,), revision=1)
    persisted = repository.project(first)
    assert persisted.revision == 1
    rows = session.execute(
        select(EvidenceExpectationV2Record)
    ).scalars().all()
    assert len(rows) == 1

    # 同内容重复投影 → 幂等返回最新行，不追加。
    repeated = repository.project(first)
    assert repeated.revision == 1
    rows = session.execute(
        select(EvidenceExpectationV2Record)
    ).scalars().all()
    assert len(rows) == 1

    # 内容变化（新事实发布 → 合并定位）→ 追加 revision 2，旧行保留。
    extra_fact = _publish_fact(
        session, chain, fact_id="f-rev2", gate_id="g-rev2", candidate_id="c-rev2",
        fact_type="vital_sign", source_strength=SourceStrength.HISTORICAL_PRIMARY,
        asserted_object="血压", value="118/78", unit="unitless",
        locator_ids=[chain["locator_id_2"]],
    )
    changed = _project(chain, t, observations=(fact, extra_fact), revision=2)
    second = repository.project(changed)
    assert second.revision == 2
    assert second.locator_ids == sorted([chain["locator_id"], chain["locator_id_2"]])
    rows = session.execute(
        select(EvidenceExpectationV2Record)
    ).scalars().all()
    assert {row.revision for row in rows} == {1, 2}
    old = repository.get(first.expectation_id)
    assert old.revision == 1  # 旧投影完整保留

    # 回退/跳号拒绝：latest=2 时不允许再写 revision 1/2/4 的不同内容。
    for bad_revision in (1, 2, 4):
        bad = _project(chain, t, observations=(fact,), revision=bad_revision,
                       gap_signals=[CoverageGapSignal(
                           kind=GapType.RECORD_INCOMPLETE, detail="不同内容")])
        with pytest.raises(FactRevisionChainError):
            repository.project(bad)

    # 新模板首个 revision 必须为 1。
    t2 = _template(session, chain, requirement_id="req-rev2",
                   fact_type="lab_result", due_stage=ReviewStage.SCREENING)
    with pytest.raises(FactRevisionChainError, match="首个 revision"):
        repository.project(_project(chain, t2, revision=2, gap_signals=[
            CoverageGapSignal(kind=GapType.RECORD_INCOMPLETE, detail="病历不完整")]))


def test_revision_chain_distinct_per_template(chain, session):
    """revision 链按 (review_episode, template) 隔离，互不干扰。"""
    t1 = _template(session, chain, requirement_id="req-chain-a",
                   fact_type="vital_sign", due_stage=ReviewStage.SCREENING)
    t2 = _template(session, chain, requirement_id="req-chain-b",
                   fact_type="medical_history", due_stage=ReviewStage.SCREENING)
    fact = _publish_fact(
        session, chain, fact_id="f-chain", gate_id="g-chain", candidate_id="c-chain",
        fact_type="vital_sign", source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="血压", value="120/80", unit="unitless",
        locator_ids=[chain["locator_id"]],
    )
    repository = EvidenceExpectationV2Repository(session)
    repository.project(_project(chain, t1, observations=(fact,), revision=1))
    repository.project(_project(chain, t2, revision=1, gap_signals=[
        CoverageGapSignal(kind=GapType.RECORD_INCOMPLETE, detail="病历不完整")]))
    # t2 链头仍为 1；t1 追加到 2 不影响 t2。
    second_fact = _publish_fact(
        session, chain, fact_id="f-chain2", gate_id="g-chain2",
        candidate_id="c-chain2", fact_type="vital_sign",
        source_strength=SourceStrength.HISTORICAL_PRIMARY,
        asserted_object="血压", value="118/78", unit="unitless",
        locator_ids=[chain["locator_id_2"]],
    )
    repository.project(_project(chain, t1, observations=(fact, second_fact),
                                revision=2))
    assert repository.latest_by_template(
        chain["review_episode_id"], t2.template_id).revision == 1
    assert repository.latest_by_template(
        chain["review_episode_id"], t1.template_id).revision == 2


# ---------------------------------------------------------------------------
# 4) 定位链接镜像 + 权威/模板绑定
# ---------------------------------------------------------------------------


def test_locator_link_mirror_and_payload_hash(chain, session):
    """定位链接与 payload 双向镜像；删链接/改哈希即拒绝还原合同。"""
    t = _template(session, chain, requirement_id="req-mirror",
                  fact_type="vital_sign", due_stage=ReviewStage.SCREENING)
    fact = _publish_fact(
        session, chain, fact_id="f-mirror", gate_id="g-mirror", candidate_id="c-mirror",
        fact_type="vital_sign", source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="血压", value="120/80", unit="unitless",
        locator_ids=[chain["locator_id"]],
    )
    repository = EvidenceExpectationV2Repository(session)
    expectation = _project(chain, t, observations=(fact,))
    repository.project(expectation)

    restored = repository.get(expectation.expectation_id)
    assert restored.locator_ids == [chain["locator_id"]]
    links = session.execute(
        select(FactEvidenceLocatorLinkRecord).where(
            FactEvidenceLocatorLinkRecord.entity_kind == "expectation",
            FactEvidenceLocatorLinkRecord.entity_id == expectation.expectation_id,
        )
    ).scalars().all()
    assert [link.locator_id for link in links] == [chain["locator_id"]]

    # 删除定位链接 → 镜像校验失败，拒绝还原。
    for link in links:
        session.delete(link)
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="定位链接"):
        repository.get(expectation.expectation_id)

    # 篡改 payload 哈希 → 拒绝还原（哈希校验先于镜像校验）。
    row = session.get(EvidenceExpectationV2Record, expectation.expectation_id)
    row.payload_sha256 = _sha("tampered")
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="哈希不一致"):
        repository.get(expectation.expectation_id)


def test_repository_rejects_unbound_template_and_stale_authority(
    chain, session
):
    """模板不属于权威元组规则修订 / 权威指针陈旧 → 拒绝投影。"""
    t = _template(session, chain, requirement_id="req-bound",
                  fact_type="vital_sign", due_stage=ReviewStage.SCREENING)
    repository = EvidenceExpectationV2Repository(session)
    expectation = _project(chain, t, gap_signals=[
        CoverageGapSignal(kind=GapType.RECORD_INCOMPLETE, detail="病历不完整")])
    repository.project(expectation)

    # 未绑定模板：模板记录属于另一规则集 → 拒绝。
    unbound_id = _seed_unbound_ruleset(session)
    unbound = EvidenceExpectationV2(
        expectation_id=expectation_identity(
            chain["review_episode_id"], unbound_id, 1),
        authority=_authority(chain),
        template_id=unbound_id,
        status=ExpectationStatus.ABSENT,
        gap_type=GapType.RECORD_INCOMPLETE,
        revision=1,
        created_at=NOW,
    )
    with pytest.raises(Phase5RepositoryError, match="不属于权威元组的规则集修订"):
        repository.project(unbound)

    # 权威指针陈旧：complete 修订引用非活动修订 → 拒绝。
    with pytest.raises(FactAuthorityError, match="活动处理修订"):
        repository.project(_project(
            chain, t,
            complete_processing_revision_id="stale-complete-revision",
            gap_signals=[CoverageGapSignal(
                kind=GapType.RECORD_INCOMPLETE, detail="病历不完整")]))


def test_repository_rejects_locators_outside_coverage_closure(chain, session):
    """期望定位必须正好等于覆盖事实定位闭包（多余定位拒绝）。"""
    t = _template(session, chain, requirement_id="req-closure",
                  fact_type="vital_sign", due_stage=ReviewStage.SCREENING)
    fact = _publish_fact(
        session, chain, fact_id="f-closure", gate_id="g-closure",
        candidate_id="c-closure", fact_type="vital_sign",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="血压", value="120/80", unit="unitless",
        locator_ids=[chain["locator_id"]],
    )
    repository = EvidenceExpectationV2Repository(session)
    # 合法投影（定位 = 覆盖闭包）。
    repository.project(_project(chain, t, observations=(fact,)))
    # 在闭包外加第二个合法定位 → 拒绝。
    extra = _project(chain, t, observations=(fact,)).model_copy(
        update={"locator_ids": sorted(
            [chain["locator_id"], chain["locator_id_2"]])})
    with pytest.raises(Phase5RepositoryError, match="定位闭包"):
        repository.project(extra)


# ---------------------------------------------------------------------------
# 5) 批量投影无双重报告 + 较弱转述回归
# ---------------------------------------------------------------------------


def test_weak_transcription_never_absent_no_double_report(chain, session):
    """较弱转述事实 + 定位 → observed_weak + 溯源提醒；绝不同时报 absent。"""
    t = _template(session, chain, requirement_id="req-weak-nodouble",
                  fact_type="medical_history", due_stage=ReviewStage.SCREENING)
    weak_fact = _publish_fact(
        session, chain, fact_id="f-weak-nd", gate_id="g-weak-nd",
        candidate_id="c-weak-nd", fact_type="medical_history",
        source_strength=SourceStrength.SCREENING_RECORD_TRANSCRIPTION,
        asserted_object="既往史", value="高血压病史", unit="unitless",
        locator_ids=[chain["locator_id"]],
    )
    projected = _project(chain, t, observations=(weak_fact,))
    assert projected.status == ExpectationStatus.OBSERVED_WEAK
    assert projected.status != ExpectationStatus.ABSENT
    assert projected.locator_ids == [chain["locator_id"]]
    assert projected.provenance_followup is True
    # 单一期望：无第二行重复报无证据。
    repository = EvidenceExpectationV2Repository(session)
    repository.project(projected)
    rows = session.execute(
        select(EvidenceExpectationV2Record)
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == ExpectationStatus.OBSERVED_WEAK.value


def test_batch_projects_every_template_exactly_once(chain, session):
    """批量投影覆盖当前规则修订全部模板，一个模板恰好一条期望。"""
    t1 = _template(session, chain, requirement_id="req-batch-a",
                   fact_type="vital_sign", due_stage=ReviewStage.SCREENING)
    t2 = _template(session, chain, requirement_id="req-batch-b",
                   fact_type="medical_history", due_stage=ReviewStage.SCREENING)
    t3 = _template(session, chain, requirement_id="req-batch-c",
                   fact_type="baseline_vital", due_stage=ReviewStage.BASELINE)
    t4 = _template(session, chain, requirement_id="req-batch-d",
                   fact_type="procedure_done", due_stage=ReviewStage.SCREENING)
    weak_fact = _publish_fact(
        session, chain, fact_id="f-batch", gate_id="g-batch", candidate_id="c-batch",
        fact_type="medical_history",
        source_strength=SourceStrength.SCREENING_RECORD_TRANSCRIPTION,
        asserted_object="既往史", value="高血压病史", unit="unitless",
        locator_ids=[chain["locator_id"]],
    )
    projected = project_expectations(
        templates=[t1, t2, t3, t4],
        authority=_authority(chain),
        current_stage=ReviewStage.SCREENING,
        observations=(
            CoverageObservation(fact=weak_fact, source_types=["检验报告"]),
        ),
        gap_signals=[
            CoverageGapSignal(
                kind=GapType.RECORD_INCOMPLETE, detail="病历不完整",
                applies_to_template_id=t1.template_id),
            CoverageGapSignal(
                kind=GapType.REQUIRED_PROCEDURE_NOT_DONE, detail="检查未执行",
                applies_to_template_id=t4.template_id),
        ],
        revision=1,
        created_at=NOW,
    )
    assert len(projected) == 4
    by_template = {item.template_id: item for item in projected}
    assert set(by_template) == {t.template_id for t in (t1, t2, t3, t4)}
    assert by_template[t1.template_id].status == ExpectationStatus.ABSENT
    assert by_template[t1.template_id].gap_type == GapType.RECORD_INCOMPLETE
    assert by_template[t2.template_id].status == ExpectationStatus.OBSERVED_WEAK
    assert by_template[t3.template_id].status == ExpectationStatus.NOT_DUE
    assert by_template[t4.template_id].status == ExpectationStatus.ABSENT
    assert by_template[t4.template_id].gap_type == (
        GapType.REQUIRED_PROCEDURE_NOT_DONE)
    assert len({item.expectation_id for item in projected}) == 4

    # 持久化后逐模板仍只有一条（无双重报告）。
    repository = EvidenceExpectationV2Repository(session)
    for item in projected:
        repository.project(item)
    rows = session.execute(
        select(EvidenceExpectationV2Record)
    ).scalars().all()
    assert len(rows) == 4
    assert len({row.template_id for row in rows}) == 4


def test_expectation_requires_exact_template_requirement_binding(chain, session):
    first = _template(
        session, chain, requirement_id="req-exact-a",
        fact_type="vital_sign", due_stage=ReviewStage.SCREENING,
    )
    sibling = _template(
        session, chain, requirement_id="req-exact-b",
        fact_type="vital_sign", due_stage=ReviewStage.SCREENING,
    )
    fact = _publish_fact(
        session, chain, fact_id="f-exact", gate_id="g-exact",
        candidate_id="c-exact", fact_type="vital_sign",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="血压", value="120/80", unit="unitless",
        locator_ids=[chain["locator_id"]],
        supported_requirement_ids=[first.requirement_id],
    )
    observed = _project(chain, first, observations=(fact,))
    absent = _project(
        chain,
        sibling,
        observations=(fact,),
        gap_signals=[
            CoverageGapSignal(
                kind=GapType.RECORD_INCOMPLETE,
                detail="同类型事实未绑定本资料要求",
            )
        ],
    )
    assert observed.status == ExpectationStatus.OBSERVED
    assert absent.status == ExpectationStatus.ABSENT


def test_legacy_unbound_fact_remains_fact_but_covers_nothing(chain, session):
    template = _template(
        session, chain, requirement_id="req-legacy-unbound",
        fact_type="vital_sign", due_stage=ReviewStage.SCREENING,
    )
    fact = _publish_fact(
        session, chain, fact_id="f-legacy-unbound", gate_id="g-legacy-unbound",
        candidate_id="c-legacy-unbound", fact_type="vital_sign",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="血压", value="120/80", unit="unitless",
        locator_ids=[chain["locator_id"]],
        supported_requirement_ids=[],
    )
    assert fact.fact_id == "f-legacy-unbound"
    projected = _project(
        chain,
        template,
        observations=(fact,),
        gap_signals=[
            CoverageGapSignal(
                kind=GapType.RECORD_INCOMPLETE,
                detail="旧事实未显式绑定资料要求",
            )
        ],
    )
    assert projected.status == ExpectationStatus.ABSENT
    assert projected.coverage_fact_ids == []


def test_expectation_identity_stable_and_template_bound(chain, session):
    """期望 ID 按 (节点, 模板, revision) 唯一；模板规则修订不匹配时拒绝投影。"""
    t = _template(session, chain, requirement_id="req-identity",
                  fact_type="vital_sign", due_stage=ReviewStage.SCREENING)
    signal = [CoverageGapSignal(kind=GapType.RECORD_INCOMPLETE, detail="病历不完整")]
    first = _project(chain, t, revision=1, gap_signals=signal)
    same = _project(chain, t, revision=1, gap_signals=signal)
    assert first.expectation_id == same.expectation_id
    assert first.expectation_id == expectation_identity(
        chain["review_episode_id"], t.template_id, 1)
    # 不同 revision → 不同行 ID（追加写绝不覆盖旧行）。
    second = _project(chain, t, revision=2, gap_signals=signal)
    assert second.expectation_id != first.expectation_id
    assert second.expectation_id == expectation_identity(
        chain["review_episode_id"], t.template_id, 2)
    # 模板绑定另一个规则集修订 → 拒绝（不产生未绑定投影）。
    with pytest.raises(ProjectionInputError, match="不属于权威元组的规则集修订"):
        project_expectation(
            template=t.model_copy(update={"rule_set_id": "other-ruleset"}),
            authority=_authority(chain),
            current_stage=ReviewStage.SCREENING,
            observations=(), created_at=NOW,
        )


# ---------------------------------------------------------------------------
# 6) 输入信号 provenance（input_gap_signals）冻结与幂等语义
# ---------------------------------------------------------------------------


def test_input_provenance_frozen_on_all_return_paths(chain, session):
    """每个投影返回路径（含 not_due）都冻结适用于本模板的输入信号。

    全局信号（applies_to_template_id=None）全部适用；重复输入被去重，冻结序
    由 canonical 键唯一决定（与传入顺序无关）；绑定其他模板的信号在投影器
    入口即被过滤，绝不进入 provenance。
    """
    t_future = _template(
        session, chain, requirement_id="prov-future",
        fact_type="baseline_vital", due_stage=ReviewStage.BASELINE,
    )
    t_observed = _template(
        session, chain, requirement_id="prov-observed",
        fact_type="vital_sign", due_stage=ReviewStage.SCREENING,
    )
    fact = _publish_fact(
        session, chain, fact_id="f-prov", gate_id="g-prov", candidate_id="c-prov",
        fact_type="vital_sign",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="血压", value="120/80", unit="unitless",
        locator_ids=[chain["locator_id"]],
    )
    concrete = CoverageGapSignal(kind=GapType.RECORD_INCOMPLETE, detail="病历不完整")
    fallback = CoverageGapSignal(
        kind=GapType.OBSERVATION_UNVERIFIED, detail="尚未核实", fallback_only=True
    )
    shuffled_duplicates = [
        fallback,
        concrete,
        CoverageGapSignal(kind=GapType.RECORD_INCOMPLETE, detail="病历不完整"),
        CoverageGapSignal(
            kind=GapType.OCR_OR_PARSE_RISK,
            detail="其他模板专属信号",
            applies_to_template_id="expectation-template-somewhere-else",
        ),
    ]
    expected = canonical_input_gap_signals(
        t_future.template_id,
        [fallback, concrete, CoverageGapSignal(kind=GapType.RECORD_INCOMPLETE, detail="病历不完整")],
    )
    assert len(expected) == 2

    not_due = _project(chain, t_future, gap_signals=shuffled_duplicates)
    assert not_due.status == ExpectationStatus.NOT_DUE
    assert not_due.input_gap_signals == expected

    observed = _project(chain, t_observed, observations=(fact,), gap_signals=shuffled_duplicates)
    assert observed.status == ExpectationStatus.OBSERVED
    assert observed.input_gap_signals == expected

    assert canonical_input_gap_signals(
        t_future.template_id, list(reversed([fallback, concrete]))
    ) == canonical_input_gap_signals(t_future.template_id, [fallback, concrete])


def test_contract_rejects_input_signal_bound_to_other_template(chain, session):
    """期望合同拒绝绑定其他模板的输入信号；None/[]/清单三态均可表达。"""
    t = _template(
        session, chain, requirement_id="prov-bind",
        fact_type="vital_sign", due_stage=ReviewStage.SCREENING,
    )
    from pydantic import ValidationError

    base = dict(
        expectation_id=expectation_identity(chain["review_episode_id"], t.template_id, 1),
        authority=_authority(chain),
        template_id=t.template_id,
        status=ExpectationStatus.NOT_DUE,
        gap_type=GapType.FUTURE_STAGE_NOT_DUE,
        revision=1,
        created_at=NOW,
    )
    assert EvidenceExpectationV2(**base).input_gap_signals is None
    assert EvidenceExpectationV2(
        **base, input_gap_signals=[]
    ).input_gap_signals == []
    with pytest.raises(ValidationError, match="其他模板"):
        EvidenceExpectationV2(
            **base,
            input_gap_signals=[
                CoverageGapSignal(
                    kind=GapType.RECORD_INCOMPLETE,
                    detail="跨模板信号",
                    applies_to_template_id="expectation-template-somewhere-else",
                )
            ],
        )


def test_legacy_payload_without_input_signals_decodes_unrewritten(chain, session):
    """历史 payload 缺少新字段时按 None（来源未知）解码，读取绝不改写旧行。"""
    t = _template(
        session, chain, requirement_id="prov-legacy",
        fact_type="vital_sign", due_stage=ReviewStage.SCREENING,
    )
    fact = _publish_fact(
        session, chain, fact_id="f-prov-legacy", gate_id="g-prov-legacy",
        candidate_id="c-prov-legacy", fact_type="vital_sign",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="血压", value="120/80", unit="unitless",
        locator_ids=[chain["locator_id"]],
    )
    repository = EvidenceExpectationV2Repository(session)
    persisted = repository.project(
        _project(chain, t, observations=(fact,), revision=1, gap_signals=[])
    )
    row = session.get(EvidenceExpectationV2Record, persisted.expectation_id)
    assert "input_gap_signals" in json.loads(row.payload_json)
    # 模拟升级前的历史行：剥离新字段并用正式编码回写哈希。
    from app.storage.codecs import encode_value

    legacy_payload = persisted.model_dump(mode="json")
    legacy_payload.pop("input_gap_signals")
    legacy_json, legacy_sha = encode_value(legacy_payload)
    assert "input_gap_signals" not in json.loads(legacy_json)
    row.payload_json = legacy_json
    row.payload_sha256 = legacy_sha
    session.flush()
    session.expire_all()

    decoded = repository.get(persisted.expectation_id)
    assert decoded.input_gap_signals is None
    assert decoded.status == persisted.status
    row_after = session.get(EvidenceExpectationV2Record, persisted.expectation_id)
    assert row_after.payload_sha256 == legacy_sha


def test_same_visible_status_different_input_provenance_appends_revision(chain, session):
    """可见状态相同、输入 provenance 变化时必须追加 revision；完全相同则幂等复用。"""
    t = _template(
        session, chain, requirement_id="prov-rev",
        fact_type="vital_sign", due_stage=ReviewStage.SCREENING,
    )
    fact = _publish_fact(
        session, chain, fact_id="f-prov-rev", gate_id="g-prov-rev",
        candidate_id="c-prov-rev", fact_type="vital_sign",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        asserted_object="血压", value="120/80", unit="unitless",
        locator_ids=[chain["locator_id"]],
    )
    repository = EvidenceExpectationV2Repository(session)
    first = repository.project(
        _project(
            chain, t, observations=(fact,), revision=1,
            gap_signals=[CoverageGapSignal(
                kind=GapType.RECORD_INCOMPLETE, detail="病历不完整", fallback_only=True,
            )],
        )
    )
    assert first.status == ExpectationStatus.OBSERVED
    assert first.input_gap_signals is not None
    assert all(signal.fallback_only for signal in first.input_gap_signals)

    changed = _project(chain, t, observations=(fact,), revision=2, gap_signals=[])
    assert changed.status == ExpectationStatus.OBSERVED
    assert changed.input_gap_signals == []
    second = repository.project(changed)
    assert second.revision == 2
    assert second.expectation_id != first.expectation_id

    repeated = repository.project(changed)
    assert repeated.expectation_id == second.expectation_id
    assert repeated.revision == 2
    rows = session.execute(select(EvidenceExpectationV2Record)).scalars().all()
    assert sorted(row.revision for row in rows) == [1, 2]
