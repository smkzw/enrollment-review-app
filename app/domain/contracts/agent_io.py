from __future__ import annotations

from pydantic import Field

from .agents import AgentCallContract, CriticRun, GateResult, ModelConfigContract, PromptVersion
from .common import VersionedModel
from .evidence import ClinicalFact, ConflictGroup, EvidenceExpectation, EvidenceSpan
from .review import AssessmentCandidate
from .rules import Rule, WorkflowStage


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


class EvidenceNormalizationCandidate(VersionedModel):
    candidate_id: str = Field(min_length=1)
    clinical_fact_candidates: list[ClinicalFact] = Field(default_factory=list)
    evidence_span_candidates: list[EvidenceSpan] = Field(default_factory=list)
    conflict_candidates: list[ConflictGroup] = Field(default_factory=list)
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
