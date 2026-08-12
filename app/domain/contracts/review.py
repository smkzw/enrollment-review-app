from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from .agents import AgentCallContract, GateResult, ModelConfigContract, PromptVersion
from .common import DateValue, RevisionedModel, ScalarValue, VersionedModel
from .enums import (
    AnchorType,
    ActionState,
    ActionTarget,
    BlockingLevel,
    ComponentDecision,
    GapType,
    ReviewStage,
    StudyPhase,
    TruthValue,
)
from .evidence import (
    ClinicalFact,
    ConflictGroup,
    EvidenceExpectation,
    EvidenceSnapshot,
    EvidenceSpan,
    PatientProfile,
    SourceDocumentVersion,
)
from .jobs import JobEvent, ReviewRunDiff
from .rules import ProtocolIntegrityManifest, RuleSet, WorkflowStage
from .projections import EpisodeRollup


class ProtocolDocumentVersion(VersionedModel):
    protocol_version_id: str = Field(min_length=1)
    protocol_code: str = Field(min_length=1)
    official_version: str = Field(min_length=1)
    official_date: DateValue
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    integrity_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Project(RevisionedModel):
    project_id: str = Field(min_length=1)
    project_code: str = Field(min_length=1)
    project_name: str = Field(min_length=1)
    study_phase: StudyPhase
    protocol_version: ProtocolDocumentVersion
    rule_set_id: str = Field(min_length=1)


class Subject(RevisionedModel):
    subject_id: str = Field(min_length=1)
    subject_code: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    center_code: str | None = None
    center_name: str | None = None
    sex: str | None = None
    age_years: float | None = Field(default=None, ge=0)


class ReviewEpisode(RevisionedModel):
    review_episode_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    study_phase: StudyPhase
    stage: ReviewStage
    protocol_version_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    evidence_snapshot_id: str = Field(min_length=1)
    anchor_dates: dict[AnchorType, DateValue] = Field(default_factory=dict)
    due_at: datetime | None = None


class ReviewRun(VersionedModel):
    review_run_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    evidence_snapshot_id: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime | None = None
    supersedes_review_run_id: str | None = None


class PredicateObservation(VersionedModel):
    predicate_id: str = Field(min_length=1)
    truth: TruthValue
    observed_value: ScalarValue | None = None
    observed_unit: str | None = None
    fact_ids: list[str] = Field(default_factory=list)
    evidence_span_ids: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)


class AssessmentCandidate(VersionedModel):
    assessment_candidate_id: str = Field(min_length=1)
    agent_call_id: str = Field(min_length=1)
    rule_component_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    proposed_decision: ComponentDecision
    gap_types: list[GapType] = Field(default_factory=list)
    used_fact_ids: list[str] = Field(default_factory=list)
    evidence_span_ids: list[str] = Field(default_factory=list)
    candidate_rationale: str = Field(min_length=1)
    predicate_observations: list[PredicateObservation] = Field(default_factory=list)
    processed_predicate_ids: list[str] = Field(default_factory=list)
    missing_predicate_ids: list[str] = Field(default_factory=list)
    uncertainty_codes: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    candidate_confidence: float = Field(ge=0, le=1)
    unresolved_items: list[str] = Field(default_factory=list)


class FinalAssessment(VersionedModel):
    assessment_id: str = Field(min_length=1)
    review_run_id: str = Field(min_length=1)
    rule_component_id: str = Field(min_length=1)
    decision: ComponentDecision
    gap_types: list[GapType] = Field(default_factory=list)
    blocking_level: BlockingLevel
    used_fact_ids: list[str] = Field(default_factory=list)
    evidence_span_ids: list[str] = Field(default_factory=list)
    action_ids: list[str] = Field(default_factory=list)
    gate_result_id: str = Field(min_length=1)
    publication_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_gate_owned_state(self) -> "FinalAssessment":
        from app.domain.policies import derive_assessment_blocking_level

        expected = derive_assessment_blocking_level(self.decision, set(self.gap_types))
        if self.blocking_level != expected:
            raise ValueError(f"FinalAssessment blocking_level 必须由 Gate 推导为 {expected.value}")
        from app.domain.publication import publication_fingerprint

        payload = self.model_dump(
            mode="json",
            exclude={"publication_fingerprint"},
        )
        expected_fingerprint = publication_fingerprint(
            entity_type="final_assessment",
            gate_result_id=self.gate_result_id,
            payload=payload,
        )
        if self.publication_fingerprint != expected_fingerprint:
            raise ValueError("FinalAssessment 缺少有效的确定性 Gate 发布指纹")
        return self


class ActionTransition(VersionedModel):
    transition_id: str = Field(min_length=1)
    from_state: ActionState
    to_state: ActionState
    occurred_at: datetime
    reason: str = Field(min_length=1)
    evidence_span_ids: list[str] = Field(default_factory=list)


class ActionRequest(RevisionedModel):
    action_id: str = Field(min_length=1)
    rule_component_id: str = Field(min_length=1)
    gap_type: GapType
    target_party: ActionTarget
    requested_action: str = Field(min_length=1)
    acceptable_evidence: str = Field(min_length=1)
    due_stage: ReviewStage
    blocking_level: BlockingLevel
    trigger_evidence_span_id: str | None = None
    state: ActionState
    recompute_scope: list[str] = Field(min_length=1)
    transitions: list[ActionTransition] = Field(default_factory=list)
    gate_result_id: str = Field(min_length=1)
    publication_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_gate_owned_blocking(self) -> "ActionRequest":
        from app.domain.policies import derive_action_blocking_level

        expected = derive_action_blocking_level(self.gap_type)
        if self.blocking_level != expected:
            raise ValueError(f"ActionRequest blocking_level 必须由 Gate 推导为 {expected.value}")
        if self.state == ActionState.CLOSED_SYSTEM and not any(
            transition.to_state == ActionState.CLOSED_SYSTEM
            for transition in self.transitions
        ):
            raise ValueError("系统自动关闭 Action 必须保留状态转换记录")
        from app.domain.publication import publication_fingerprint

        payload = self.model_dump(
            mode="json",
            exclude={"publication_fingerprint"},
        )
        expected_fingerprint = publication_fingerprint(
            entity_type="action_request",
            gate_result_id=self.gate_result_id,
            payload=payload,
        )
        if self.publication_fingerprint != expected_fingerprint:
            raise ValueError("ActionRequest 缺少有效的确定性 Gate 发布指纹")
        return self


class FixtureV1(VersionedModel):
    fixture_id: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    project: Project
    protocol_integrity_manifest: ProtocolIntegrityManifest
    rule_set: RuleSet
    workflow_stages: list[WorkflowStage]
    subject: Subject
    review_episode: ReviewEpisode
    evidence_snapshot: EvidenceSnapshot
    review_runs: list[ReviewRun]
    source_documents: list[SourceDocumentVersion]
    evidence_spans: list[EvidenceSpan]
    evidence_expectations: list[EvidenceExpectation]
    facts: list[ClinicalFact]
    conflict_groups: list[ConflictGroup] = Field(default_factory=list)
    patient_profile: PatientProfile
    assessment_candidates: list[AssessmentCandidate]
    final_assessments: list[FinalAssessment]
    actions: list[ActionRequest]
    episode_rollup: EpisodeRollup
    prompt_versions: list[PromptVersion]
    model_configs: list[ModelConfigContract]
    agent_calls: list[AgentCallContract]
    gate_results: list[GateResult]
    job_events: list[JobEvent]
    review_run_diffs: list[ReviewRunDiff] = Field(default_factory=list)
