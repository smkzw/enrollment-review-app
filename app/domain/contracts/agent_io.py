from __future__ import annotations

from pydantic import Field

from .agents import AgentCallContract, CriticRun, GateResult, ModelConfigContract, PromptVersion
from .common import VersionedModel
from .evidence import ClinicalFact, ConflictGroup, EvidenceExpectation, EvidenceSpan
from .review import AssessmentCandidate
from .rules import EvidenceRequirement, Rule, RuleComponent, WorkflowStage


class ProtocolMetadataDraft(VersionedModel):
    protocol_code_candidate: str = Field(min_length=1)
    title_candidate: str = Field(min_length=1)
    version_candidate: str = Field(min_length=1)
    date_candidate: str = Field(min_length=1)
    study_phase_candidates: list[str] = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)


class RuleComponentDraft(VersionedModel):
    draft_component_id: str = Field(min_length=1)
    parent_official_code: str = Field(min_length=1)
    proposed_component: RuleComponent
    source_refs: list[str] = Field(min_length=1)


class EvidenceRequirementDraft(VersionedModel):
    draft_requirement_id: str = Field(min_length=1)
    draft_component_id: str = Field(min_length=1)
    proposed_requirement: EvidenceRequirement
    source_refs: list[str] = Field(min_length=1)


class CoverageSummary(VersionedModel):
    processed_refs: list[str] = Field(default_factory=list)
    missing_refs: list[str] = Field(default_factory=list)
    duplicate_refs: list[str] = Field(default_factory=list)


class UnresolvedItem(VersionedModel):
    code: str = Field(min_length=1)
    affected_scope: list[str] = Field(min_length=1)
    source_refs: list[str] = Field(default_factory=list)


class ProtocolDeconstructionInput(VersionedModel):
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    protocol_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_page_refs: list[str] = Field(min_length=1)
    interpretation_source_ids: list[str] = Field(default_factory=list)


class ProtocolDeconstructionDraft(VersionedModel):
    draft_id: str = Field(min_length=1)
    proposed_rules: list[Rule]
    proposed_workflow_stages: list[WorkflowStage]
    protocol_metadata: ProtocolMetadataDraft
    component_drafts: list[RuleComponentDraft]
    evidence_requirement_drafts: list[EvidenceRequirementDraft]
    coverage: CoverageSummary
    unresolved_items: list[UnresolvedItem] = Field(default_factory=list)
    source_refs: list[str] = Field(min_length=1)
    created_by_agent_call_id: str = Field(min_length=1)


class EvidenceNormalizationInput(VersionedModel):
    project_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    source_document_version_ids: list[str] = Field(min_length=1)
    source_page_refs: list[str] = Field(min_length=1)


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
    clinical_fact_candidates: list[ClinicalFact] = Field(default_factory=list)
    evidence_span_candidates: list[EvidenceSpan] = Field(default_factory=list)
    conflict_candidates: list[ConflictGroup] = Field(default_factory=list)
    clinical_event_candidates: list[ClinicalEventCandidate] = Field(default_factory=list)
    medication_exposure_candidates: list[MedicationExposureCandidate] = Field(default_factory=list)
    referenced_document_candidates: list[ReferencedDocumentCandidate] = Field(default_factory=list)
    uncertainty_codes: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(min_length=1)
    coverage: CoverageSummary
    unresolved_items: list[UnresolvedItem] = Field(default_factory=list)
    created_by_agent_call_id: str = Field(min_length=1)


class EligibilityAssessmentInput(VersionedModel):
    project_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    review_episode_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    rule_component_ids: list[str] = Field(min_length=1)
    fact_ids: list[str] = Field(default_factory=list)
    expectation_ids: list[str] = Field(default_factory=list)


class EligibilityAssessmentOutput(VersionedModel):
    candidates: list[AssessmentCandidate]
    coverage: CoverageSummary
    unresolved_items: list[UnresolvedItem] = Field(default_factory=list)
    created_by_agent_call_id: str = Field(min_length=1)


class SafetyProvenanceCriticInput(VersionedModel):
    assessment_candidate_ids: list[str] = Field(min_length=1)
    fact_ids: list[str] = Field(default_factory=list)
    evidence_span_ids: list[str] = Field(default_factory=list)
    expectation_ids: list[str] = Field(default_factory=list)
    trigger_codes: list[str] = Field(min_length=1)
    input_scope_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class SafetyProvenanceCriticOutput(VersionedModel):
    critic_runs: list[CriticRun]


class AgentContractsV1(VersionedModel):
    prompt_version: PromptVersion
    model_configuration: ModelConfigContract
    agent_call: AgentCallContract
    gate_result: GateResult
    protocol_deconstruction_input: ProtocolDeconstructionInput
    protocol_deconstruction_output: ProtocolDeconstructionDraft
    evidence_normalization_input: EvidenceNormalizationInput
    evidence_normalization_output: EvidenceNormalizationCandidate
    eligibility_assessment_input: EligibilityAssessmentInput
    eligibility_assessment_output: EligibilityAssessmentOutput
    safety_provenance_critic_input: SafetyProvenanceCriticInput
    safety_provenance_critic_output: SafetyProvenanceCriticOutput
