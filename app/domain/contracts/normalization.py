from __future__ import annotations

from pydantic import Field, model_validator

from .common import VersionedModel
from .evidence import ClinicalFact, ConflictGroup, EvidenceSpan


class CoverageSummary(VersionedModel):
    processed_refs: list[str] = Field(default_factory=list)
    missing_refs: list[str] = Field(default_factory=list)
    duplicate_refs: list[str] = Field(default_factory=list)


class UnresolvedItem(VersionedModel):
    code: str = Field(min_length=1)
    affected_scope: list[str] = Field(min_length=1)
    source_refs: list[str] = Field(default_factory=list)


class ClinicalEventCandidate(VersionedModel):
    event_candidate_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    event_date_lower: str | None = None
    event_date_upper: str | None = None
    subject_role: str = Field(min_length=1)
    stage_candidate: str | None = None
    evidence_span_ids: list[str] = Field(min_length=1)


class MedicationExposureCandidate(VersionedModel):
    exposure_candidate_id: str = Field(min_length=1)
    medication_or_class: str = Field(min_length=1)
    dose: str | None = None
    frequency: str | None = None
    route: str | None = None
    start_date_lower: str | None = None
    end_date_upper: str | None = None
    indication: str | None = None
    evidence_span_ids: list[str] = Field(min_length=1)


class ReferencedDocumentCandidate(VersionedModel):
    referenced_document_candidate_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    referenced_by_evidence_span_id: str = Field(min_length=1)


class EvidenceNormalizationCandidate(VersionedModel):
    candidate_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    clinical_fact_candidates: list[ClinicalFact] = Field(default_factory=list)
    evidence_span_candidates: list[EvidenceSpan] = Field(default_factory=list)
    conflict_candidates: list[ConflictGroup] = Field(default_factory=list)
    clinical_event_candidates: list[ClinicalEventCandidate] = Field(default_factory=list)
    medication_exposure_candidates: list[MedicationExposureCandidate] = Field(
        default_factory=list
    )
    referenced_document_candidates: list[ReferencedDocumentCandidate] = Field(
        default_factory=list
    )
    uncertainty_codes: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(min_length=1)
    coverage: CoverageSummary
    unresolved_items: list[UnresolvedItem] = Field(default_factory=list)
    created_by_agent_call_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_evidence_scope(self) -> "EvidenceNormalizationCandidate":
        expected = (
            self.project_id,
            self.subject_id,
            self.review_episode_id,
            self.evidence_snapshot_id,
        )
        for fact in self.clinical_fact_candidates:
            if (
                fact.project_id,
                fact.subject_id,
                fact.review_episode_id,
                fact.evidence_snapshot_id,
            ) != expected:
                raise ValueError(
                    "EvidenceNormalizationCandidate 与事实 scope 不一致"
                )
        return self
