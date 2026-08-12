from __future__ import annotations

from pydantic import Field, model_validator

from .agents import AgentCallContract, CriticRun, GateResult, ModelConfigContract, PromptVersion
from .common import VersionedModel
from .evidence import EvidenceExpectation, EvidenceSpan
from .normalization import (
    ClinicalEventCandidate,
    CoverageSummary,
    EvidenceNormalizationCandidate,
    MedicationExposureCandidate,
    ReferencedDocumentCandidate,
    UnresolvedItem,
)
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


class ProtocolDeconstructionInput(VersionedModel):
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    protocol_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_page_refs: list[str] = Field(min_length=1)
    interpretation_source_ids: list[str] = Field(default_factory=list)


class ProtocolDeconstructionDraft(VersionedModel):
    draft_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
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


class EligibilityAssessmentInput(VersionedModel):
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    review_episode_id: str = Field(min_length=1)
    review_run_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    rule_component_ids: list[str] = Field(min_length=1)
    fact_ids: list[str] = Field(default_factory=list)
    expectation_ids: list[str] = Field(default_factory=list)


class EligibilityAssessmentOutput(VersionedModel):
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    review_episode_id: str = Field(min_length=1)
    review_run_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    candidates: list[AssessmentCandidate]
    coverage: CoverageSummary
    unresolved_items: list[UnresolvedItem] = Field(default_factory=list)
    created_by_agent_call_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_candidate_scope(self) -> "EligibilityAssessmentOutput":
        expected = (
            self.project_id,
            self.protocol_version_id,
            self.subject_id,
            self.rule_set_id,
            self.rule_set_revision,
            self.review_episode_id,
            self.review_run_id,
            self.evidence_snapshot_id,
            self.created_by_agent_call_id,
        )
        for candidate in self.candidates:
            actual = (
                candidate.project_id,
                candidate.protocol_version_id,
                candidate.subject_id,
                candidate.rule_set_id,
                candidate.rule_set_revision,
                candidate.review_episode_id,
                candidate.review_run_id,
                candidate.evidence_snapshot_id,
                candidate.agent_call_id,
            )
            if actual != expected:
                raise ValueError("EligibilityAssessmentOutput 与候选 scope/call 不一致")
        return self


class SafetyProvenanceCriticInput(VersionedModel):
    assessment_candidate_ids: list[str] = Field(min_length=1)
    fact_ids: list[str] = Field(default_factory=list)
    evidence_span_ids: list[str] = Field(default_factory=list)
    expectation_ids: list[str] = Field(default_factory=list)
    trigger_codes: list[str] = Field(min_length=1)
    input_scope_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class SafetyProvenanceCriticOutput(VersionedModel):
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    review_episode_id: str = Field(min_length=1)
    review_run_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    created_by_agent_call_id: str = Field(min_length=1)
    critic_runs: list[CriticRun]

    @model_validator(mode="after")
    def validate_critic_call_binding(self) -> "SafetyProvenanceCriticOutput":
        if any(
            item.created_by_agent_call_id != self.created_by_agent_call_id
            for item in self.critic_runs
        ):
            raise ValueError("SafetyProvenanceCriticOutput 与 CriticRun call 不一致")
        return self


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
