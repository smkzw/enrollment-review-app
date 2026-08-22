from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_serializer, model_validator

from .agents import AgentCallContract, GateResult, ModelConfigContract, PromptVersion
from .common import DateValue, RevisionedModel, ScalarValue, VersionedModel
from .enums import (
    ActionState,
    ActionTarget,
    AnchorType,
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
from .normalization import EvidenceNormalizationCandidate
from .projections import EpisodeRollup
from .rules import (
    ProtocolAuthorityConfirmation,
    ProtocolAuthorityRecord,
    ProtocolIntegrityManifest,
    ProtocolSourceRecord,
    RuleSet,
    ServiceCommandEvent,
    WorkflowStage,
)


def _require_utc(value: datetime, field_name: str) -> None:
    """Reject naive or non-UTC timestamps at the Phase 3/4 contract boundary."""
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise ValueError(f"{field_name} 必须携带 UTC 时区")
    if offset.total_seconds() != 0:
        raise ValueError(f"{field_name} 必须使用 UTC 时区")


class ProtocolDocumentVersion(VersionedModel):
    protocol_version_id: str = Field(min_length=1)
    protocol_code: str = Field(min_length=1)
    official_version: str = Field(min_length=1)
    official_date: DateValue
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    integrity_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_confirmation_id: str = Field(min_length=1)
    authority_gate_result_id: str = Field(min_length=1)
    integrity_gate_result_id: str = Field(min_length=1)


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
    """审核节点：受试者在某研究期别/审核节点的资料与处理修订活动版本。

    运行期唯一审核节点合同（Slice 4.4 收敛后，``evidence_ingestion`` 不再维护
    第二套同名合同）。``evidence_snapshot_id`` 是 Phase 2/3 fixture/审核链语义的
    legacy 字段，本合同保留其原义但**不作为** Phase 4 当前资料版本的 fallback。

    成对活动指针 ``active_evidence_snapshot_id`` 与
    ``active_evidence_processing_revision_id`` 是 Phase 4 当前版本的唯一权威：
    只在候选快照通过全部发布门禁后，在同一事务中按预期修订号原子更新；回滚通过
    新的 ActivationEvent 完成，不静默改写指针。二者必须同时存在或同时为空：活动
    资料必须既固定文档集合，又固定一份不可变证据处理修订。迁移 0010 不按时间/ID/
    历史 ACTIVE 状态回填本对指针；升级时保持 NULL，由正式激活命令建立。
    """

    review_episode_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    study_phase: StudyPhase
    stage: ReviewStage
    protocol_version_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    #: 自动创建的空审核节点没有 Phase 2/3 legacy 证据快照；该字段可空，不伪造占位。
    #: legacy fixture/审核链行仍保留其非空原义。
    evidence_snapshot_id: str | None = None
    #: 发布方案中的流程节点身份（命名空间化 ``workflow_stage_id``）。同一审核
    #: 阶段下多个访视实例各自对应独立审核节点，此字段把它们区分开；legacy 行可空。
    workflow_stage_id: str | None = None
    active_evidence_snapshot_id: str | None = None
    active_evidence_processing_revision_id: str | None = None
    anchor_dates: dict[AnchorType, DateValue] = Field(default_factory=dict)
    due_at: datetime | None = None

    @model_serializer(mode="wrap")
    def _serialize_omit_null_pointers(self, handler):
        """序列化时省略为 None 的可空字段。

        这保证旧 payload（无指针键/无 workflow_stage_id，或 legacy
        evidence_snapshot_id 非空）与新建但仍为空的可空字段 payload 逐字一致，
        不因新增可空字段改写 legacy 校验/发布哈希（``encode_contract``/Gate 闭包
        用 ``model_dump(mode=\"json\")``）。指针非 None 时正常出现在 payload。
        """
        data = handler(self)
        if self.active_evidence_snapshot_id is None:
            data.pop("active_evidence_snapshot_id", None)
        if self.active_evidence_processing_revision_id is None:
            data.pop("active_evidence_processing_revision_id", None)
        if self.evidence_snapshot_id is None:
            data.pop("evidence_snapshot_id", None)
        if self.workflow_stage_id is None:
            data.pop("workflow_stage_id", None)
        return data

    @model_validator(mode="after")
    def validate_active_pointers(self) -> ReviewEpisode:
        if (self.active_evidence_snapshot_id is None) != (
            self.active_evidence_processing_revision_id is None
        ):
            raise ValueError("审核节点的活动证据快照与处理修订必须同时存在或同时为空")
        if self.due_at is not None:
            _require_utc(self.due_at, "ReviewEpisode.due_at")
        return self


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
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    review_run_id: str = Field(min_length=1)
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
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    review_episode_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    review_run_id: str = Field(min_length=1)
    rule_component_id: str = Field(min_length=1)
    decision: ComponentDecision
    gap_types: list[GapType] = Field(default_factory=list)
    blocking_level: BlockingLevel
    used_fact_ids: list[str] = Field(default_factory=list)
    evidence_span_ids: list[str] = Field(default_factory=list)
    gate_result_id: str = Field(min_length=1)
    publication_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_gate_owned_state(self) -> FinalAssessment:
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
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    review_episode_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    review_run_id: str = Field(min_length=1)
    assessment_id: str = Field(min_length=1)
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
    def validate_gate_owned_blocking(self) -> ActionRequest:
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
    protocol_authority_record: ProtocolAuthorityRecord
    protocol_authority_command: ServiceCommandEvent
    protocol_authority_confirmation: ProtocolAuthorityConfirmation
    protocol_source_records: list[ProtocolSourceRecord] = Field(min_length=1)
    protocol_integrity_manifest: ProtocolIntegrityManifest
    rule_set: RuleSet
    workflow_stages: list[WorkflowStage]
    subject: Subject
    review_episode: ReviewEpisode
    evidence_snapshot: EvidenceSnapshot
    review_runs: list[ReviewRun]
    source_documents: list[SourceDocumentVersion]
    evidence_spans: list[EvidenceSpan]
    evidence_normalization_candidates: list[EvidenceNormalizationCandidate] = Field(
        min_length=1
    )
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
