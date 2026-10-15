"""Storage round-trip coverage for Phase 3 slice 2 append contracts."""
from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import update

from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import (
    ApplicabilityGranularity,
    DocumentPart,
    IdentityAuthority,
    InterpretationSourceType,
    MetadataResolutionStatus,
    MetadataSourceKind,
    PhaseDesignType,
    PhaseScope,
    ProtocolMetadataField,
    SourceLocatorPrecision,
    StudyPhase,
)
from app.domain.contracts.protocol_metadata import (
    InterpretationConflict,
    InterpretationSource,
    PhaseApplicabilityBlock,
    PhaseApplicabilityGraph,
    PhaseProjection,
    ProtocolIdentityDecision,
    ProtocolMetadataCandidate,
    ProtocolMetadataConflict,
    StudyPhaseCandidate,
    StudyPhaseSelection,
)
from app.storage.models import (
    ProtocolDocumentVersionRecord,
    ProtocolExtractionSnapshotRecord,
    ProtocolIdentityDecisionRecord,
    ProtocolSourceArtifactRecord,
    StudyPhaseSelectionRecord,
)
from app.storage.codecs import PersistedContractInvalid
from app.storage.repositories import (
    AppendRepository,
    INTERPRETATION_CONFLICT_CONFIG,
    INTERPRETATION_SOURCE_CONFIG,
    PROTOCOL_IDENTITY_DECISION_CONFIG,
    PROTOCOL_METADATA_CANDIDATE_CONFIG,
    PROTOCOL_METADATA_CONFLICT_CONFIG,
    PROTOCOL_PHASE_GRAPH_CONFIG,
    PROTOCOL_PHASE_PROJECTION_CONFIG,
    STUDY_PHASE_CANDIDATE_CONFIG,
    STUDY_PHASE_SELECTION_CONFIG,
)


_NOW = datetime(2026, 8, 14, 12, 0, 0)


def _seed_protocol_parents(session) -> None:
    session.add(
        ProtocolSourceArtifactRecord(
            source_artifact_id="source-1",
            sha256="a" * 64,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=1,
            storage_ref="blobs/source-1",
            uploaded_at=_NOW,
            payload_json="{}",
            payload_sha256="0" * 64,
            created_at=_NOW,
        )
    )
    session.flush()
    session.add(
        ProtocolExtractionSnapshotRecord(
            snapshot_id="snapshot-1",
            source_artifact_id="source-1",
            source_sha256="a" * 64,
            parser_name="test",
            parser_version="1",
            status="completed",
            content_sha256="b" * 64,
            content_storage_ref="blobs/snapshot-1",
            payload_json="{}",
            payload_sha256="0" * 64,
            created_at=_NOW,
        )
    )
    session.add(
        ProtocolDocumentVersionRecord(
            protocol_version_id="protocol-v1",
            protocol_code="P-001",
            official_version="V2.1",
            official_date_value=_NOW,
            official_date_precision="day",
            sha256="c" * 64,
            integrity_manifest_sha256="d" * 64,
            authority_record_sha256="e" * 64,
            authority_confirmation_id="authority-confirmed",
            authority_gate_result_id="authority-gate",
            integrity_gate_result_id="integrity-gate",
            payload_json="{}",
            payload_sha256="0" * 64,
            created_at=_NOW,
        )
    )
    session.flush()


def _block() -> PhaseApplicabilityBlock:
    return PhaseApplicabilityBlock(
        block_id="block-1",
        snapshot_id="snapshot-1",
        source_ref="body.p1",
        source_span_ids=["span-1"],
        granularity=ApplicabilityGranularity.PARAGRAPH,
        source_order=1,
        text="共享条款",
        phase_scopes=[PhaseScope.SHARED],
    )


def _aggregate_block() -> PhaseApplicabilityBlock:
    return PhaseApplicabilityBlock(
        block_id="row-1",
        snapshot_id="snapshot-1",
        source_ref="body.t0.r0",
        source_span_ids=["span-1"],
        granularity=ApplicabilityGranularity.TABLE_ROW,
        source_order=1,
        text="共享条款",
        phase_scopes=[PhaseScope.SHARED],
        table_path=(0, 0),
        table_row=0,
        is_aggregate=True,
        child_block_ids=["block-1"],
    )


def test_slice2_contracts_append_and_round_trip(session) -> None:
    _seed_protocol_parents(session)
    candidate = ProtocolMetadataCandidate(
        candidate_id="metadata-1",
        snapshot_id="snapshot-1",
        field_category=ProtocolMetadataField.PROTOCOL_CODE,
        candidate_value="P-001",
        normalized_value="P-001",
        source_ref="header.default.p0",
        document_part=DocumentPart.HEADER,
        source_kind=MetadataSourceKind.HEADER_FOOTER,
        identity_authority=IdentityAuthority.HIGH,
        priority_rank=10,
        confidence_basis=["页眉明确标签"],
        excerpt="方案编号：P-001",
    )
    conflict = ProtocolMetadataConflict(
        conflict_id="metadata-conflict-1",
        snapshot_id="snapshot-1",
        field_category=ProtocolMetadataField.PROTOCOL_CODE,
        candidate_ids=["metadata-1", "metadata-2"],
        normalized_values=["P-001", "P-002"],
        reason="两个来源值不同",
    )
    identity = ProtocolIdentityDecision(
        identity_decision_id="identity-1",
        snapshot_id="snapshot-1",
        project_name="项目一",
        project_code="P",
        protocol_code="P-001",
        official_version="V2.1",
        official_date=DateValue(value=date(2025, 9, 19), precision="day"),
        study_phase=StudyPhase.PHASE_II,
        selected_candidate_ids=["metadata-1"],
        conflict_ids=["metadata-conflict-1"],
        status=MetadataResolutionStatus.NEEDS_CONFIRMATION,
    )
    phase_candidate = StudyPhaseCandidate(
        candidate_id="phase-candidate-1",
        snapshot_id="snapshot-1",
        phase_scopes=[PhaseScope.PHASE_II, PhaseScope.PHASE_III],
        design_type=PhaseDesignType.INDEPENDENT,
        source_ref="body.p2",
        source_kind=MetadataSourceKind.BODY,
        excerpt="Ⅱ期和Ⅲ期分别开展",
        priority_rank=40,
        confidence_basis=["正文明确期别"],
    )
    selection = StudyPhaseSelection(
        selection_id="phase-selection-1",
        snapshot_id="snapshot-1",
        selected_phase=StudyPhase.PHASE_II,
        candidate_ids=["phase-candidate-1"],
    )
    source_block = _block()
    aggregate_block = _aggregate_block()
    graph = PhaseApplicabilityGraph(
        graph_id="graph-1",
        snapshot_id="snapshot-1",
        blocks=[source_block, aggregate_block],
        detected_phase_scopes=[PhaseScope.SHARED],
    )
    projection = PhaseProjection(
        projection_id="projection-1",
        graph_id="graph-1",
        selected_phase=StudyPhase.PHASE_II,
        blocks=[aggregate_block],
    )
    interpretation = InterpretationSource(
        interpretation_source_id="interpretation-1",
        protocol_version_id="protocol-v1",
        source_type=InterpretationSourceType.QA,
        file_sha256="f" * 64,
        source_ref="qa.p1",
        excerpt="方案未明确该说明",
        explanation="仅澄清模糊处",
        clarifies_ambiguity=True,
    )
    interpretation_conflict = InterpretationConflict(
        conflict_id="interpretation-conflict-1",
        protocol_version_id="protocol-v1",
        interpretation_source_id="interpretation-1",
        affected_rule_refs=["IN-01"],
        protocol_source_refs=["body.p3"],
        reason="解释材料改变阈值",
        impact="阻止发布",
    )

    records = [
        (PROTOCOL_METADATA_CANDIDATE_CONFIG, candidate),
        (PROTOCOL_METADATA_CONFLICT_CONFIG, conflict),
        (PROTOCOL_IDENTITY_DECISION_CONFIG, identity),
        (STUDY_PHASE_CANDIDATE_CONFIG, phase_candidate),
        (STUDY_PHASE_SELECTION_CONFIG, selection),
        (PROTOCOL_PHASE_GRAPH_CONFIG, graph),
        (PROTOCOL_PHASE_PROJECTION_CONFIG, projection),
        (INTERPRETATION_SOURCE_CONFIG, interpretation),
        (INTERPRETATION_CONFLICT_CONFIG, interpretation_conflict),
    ]
    for config, contract in records:
        AppendRepository(session, config).save(contract)
    session.commit()

    for config, contract in records:
        assert AppendRepository(session, config).get(
            getattr(contract, config.specs.keys().__iter__().__next__())
        ) == contract

    session.execute(
        update(ProtocolIdentityDecisionRecord)
        .where(ProtocolIdentityDecisionRecord.identity_decision_id == identity.identity_decision_id)
        .values(official_date_value=datetime(2025, 9, 20))
    )
    session.flush()
    session.expire_all()
    with pytest.raises(PersistedContractInvalid, match="official_date_value"):
        AppendRepository(session, PROTOCOL_IDENTITY_DECISION_CONFIG).get(
            identity.identity_decision_id
        )

    session.execute(
        update(ProtocolIdentityDecisionRecord)
        .where(ProtocolIdentityDecisionRecord.identity_decision_id == identity.identity_decision_id)
        .values(official_date_value=datetime(2025, 9, 19))
    )
    session.execute(
        update(StudyPhaseSelectionRecord)
        .where(StudyPhaseSelectionRecord.selection_id == selection.selection_id)
        .values(confirmed_at=_NOW)
    )
    session.flush()
    session.expire_all()
    with pytest.raises(PersistedContractInvalid, match="confirmed_at"):
        AppendRepository(session, STUDY_PHASE_SELECTION_CONFIG).get(selection.selection_id)
