from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_serializer, model_validator

from .agents import AgentCallContract, GateResult, ModelConfigContract, PromptVersion
from .common import DateValue, RevisionedModel, ScalarValue, VersionedModel
from .control_action_origin import ControlActionOrigin
from .proposition_evidence import PropositionPairGap
from .evaluation_result import RepeatAtomEvaluation, FrequencyAtomEvaluation
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
from .observation_selection import OrderedObservationAudit
from .facts import FactAuthority
from .review_evidence_scope import ReviewEvidenceScope, ReviewLocatedEvidenceScope
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


class ReviewRun(ReviewEvidenceScope):
    review_run_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    started_at: datetime
    completed_at: datetime | None = None
    supersedes_review_run_id: str | None = None
    episode_revision: int | None = Field(default=None, ge=1)
    context_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_episode_revision(self) -> "ReviewRun":
        if (self.schema_version == "review/v2") != (self.episode_revision is not None):
            raise ValueError("新版审核必须冻结审核节点修订；旧版审核不得补造该修订")
        if (self.schema_version == "review/v2") != (self.context_id is not None):
            raise ValueError("新版审核必须绑定冻结上下文；旧版审核不得补造该引用")
        if self.schema_version == "review/v2":
            _require_utc(self.started_at, "started_at")
            if self.completed_at is not None:
                _require_utc(self.completed_at, "completed_at")
                if self.completed_at < self.started_at:
                    raise ValueError("审核完成时间不得早于开始时间")
        return self

    @model_serializer(mode="wrap")
    def serialize_run_evidence(self, handler):
        payload = super().serialize_evidence_lineage(handler)
        if self.schema_version == "fixture/v1":
            payload.pop("episode_revision", None)
            payload.pop("context_id", None)
        return payload


class PredicateObservation(VersionedModel):
    schema_version: Literal["fixture/v1", "review/v2"] = "fixture/v1"
    predicate_id: str = Field(min_length=1)
    truth: TruthValue
    observed_value: ScalarValue | None = None
    observed_unit: str | None = None
    fact_ids: list[str] = Field(default_factory=list)
    evidence_span_ids: list[str] = Field(default_factory=list)
    locator_ids: list[str] | None = None
    reason_codes: list[str] = Field(default_factory=list)
    observation_ordering: OrderedObservationAudit | None = None
    proposition_pair_gaps: list[PropositionPairGap] = Field(default_factory=list)
    repeat_evaluation: RepeatAtomEvaluation | None = None
    frequency_evaluation: FrequencyAtomEvaluation | None = None

    @model_validator(mode="after")
    def validate_reference_lineage(self) -> "PredicateObservation":
        if self.schema_version == "fixture/v1":
            if self.frequency_evaluation is not None:
                raise ValueError("旧版条件观察不得混入频次计算")
            if self.locator_ids is not None or self.observation_ordering is not None or self.proposition_pair_gaps or self.repeat_evaluation is not None:
                raise ValueError("旧版条件观察不得混入新版定位")
        elif self.locator_ids is None or self.evidence_span_ids:
            raise ValueError("新版条件观察必须明确使用新版定位集合")
        if self.locator_ids is not None and (
            len(set(self.locator_ids)) != len(self.locator_ids)
            or any(not item.strip() for item in self.locator_ids)
        ):
            raise ValueError("条件观察的定位重复或为空")
        if self.observation_ordering is not None and set(self.fact_ids).intersection(
            item.fact_id for item in self.observation_ordering.not_selected
        ):
            raise ValueError("未采用的记录不能同时作为本条件采用的事实")
        if len({item.pair_id for item in self.proposition_pair_gaps}) != len(self.proposition_pair_gaps):
            raise ValueError("原文核实疑问不得重复")
        if self.frequency_evaluation is not None and (
            self.repeat_evaluation is not None
            or self.frequency_evaluation.result.truth != self.truth
            or set(self.frequency_evaluation.result.used_fact_ids) != set(self.fact_ids)
        ):
            raise ValueError("冻结的频次计算与本条件判断不一致")
        if self.repeat_evaluation is not None and (
            self.repeat_evaluation.result.truth != self.truth
            or set(self.repeat_evaluation.result.used_fact_ids) != set(self.fact_ids)
        ):
            raise ValueError("冻结的复查结果与本条件判断不一致")
        if (self.observation_ordering is not None
                and "selected_fact_ids" in self.observation_ordering.model_fields_set
                and set(self.fact_ids) != set(self.observation_ordering.selected_fact_ids)):
            raise ValueError("本条件采用的事实与检查选择依据不一致")
        return self

    @model_serializer(mode="wrap")
    def preserve_legacy_payload(self, handler):
        payload = handler(self)
        if self.observation_ordering is None:
            payload.pop("observation_ordering", None)
        if not self.proposition_pair_gaps:
            payload.pop("proposition_pair_gaps", None)
        if self.repeat_evaluation is None:
            payload.pop("repeat_evaluation", None)
        if self.frequency_evaluation is None:
            payload.pop("frequency_evaluation", None)
        if self.schema_version == "fixture/v1":
            payload.pop("locator_ids", None)
        return payload


class AssessmentCandidate(ReviewLocatedEvidenceScope):
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

    @model_validator(mode="after")
    def validate_observation_versions(self) -> "AssessmentCandidate":
        if any(item.schema_version != self.schema_version for item in self.predicate_observations):
            raise ValueError("候选结论与逐项条件观察的资料版本不一致")
        if any(item.observation_ordering is not None for item in self.predicate_observations):
            raise ValueError("结果选择依据只能由已核实的正式资料核对流程保存，不能由模型候选提供")
        return self


class FinalAssessment(ReviewLocatedEvidenceScope):
    assessment_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    review_episode_id: str = Field(min_length=1)
    review_run_id: str = Field(min_length=1)
    rule_component_id: str = Field(min_length=1)
    decision: ComponentDecision
    gap_types: list[GapType] = Field(default_factory=list)
    blocking_level: BlockingLevel
    used_fact_ids: list[str] = Field(default_factory=list)
    evidence_span_ids: list[str] = Field(default_factory=list)
    gate_result_id: str = Field(min_length=1)
    publication_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    predicate_observations: list[PredicateObservation] | None = None

    @model_serializer(mode="wrap")
    def preserve_legacy_observations(self, handler):
        payload = super().serialize_located_evidence(handler)
        if self.schema_version == "fixture/v1":
            payload.pop("predicate_observations", None)
        return payload

    @model_validator(mode="after")
    def validate_gate_owned_state(self) -> FinalAssessment:
        from app.domain.policies import derive_assessment_blocking_level

        if self.schema_version == "fixture/v1":
            if self.predicate_observations is not None:
                raise ValueError("旧版结论不得混入新版条件核对记录")
        else:
            observations = self.predicate_observations
            if observations is None or not observations:
                raise ValueError("本次结论必须保存逐项条件核对记录")
            if len({item.predicate_id for item in observations}) != len(observations):
                raise ValueError("结论中的条件核对记录重复")
            if any(
                item.schema_version != self.schema_version
                or not set(item.fact_ids) <= set(self.used_fact_ids)
                or not set(item.locator_ids or ()) <= set(self.locator_ids or ())
                for item in observations
            ):
                raise ValueError("条件核对记录与本条结论的依据不一致")

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
    schema_version: Literal["fixture/v1", "review/v2"] = "fixture/v1"
    transition_id: str = Field(min_length=1)
    from_state: ActionState
    to_state: ActionState
    occurred_at: datetime
    reason: str = Field(min_length=1)
    evidence_span_ids: list[str] = Field(default_factory=list)
    locator_ids: list[str] | None = None
    response_authority: FactAuthority | None = None

    @model_validator(mode="after")
    def validate_reference_lineage(self) -> "ActionTransition":
        if self.schema_version == "fixture/v1":
            if self.locator_ids is not None or self.response_authority is not None:
                raise ValueError("旧版待办记录不得混入新版原件定位")
        elif self.locator_ids is None or self.evidence_span_ids:
            raise ValueError("新版待办记录必须明确原件定位集合，不得混入旧版证据片段")
        if self.schema_version == "review/v2":
            _require_utc(self.occurred_at, "occurred_at")
            if bool(self.locator_ids) != (self.response_authority is not None):
                raise ValueError("办理原件必须同时保存所属资料版本")
            if not self.reason.strip():
                raise ValueError("办理说明不得为空白")
            if self.to_state == ActionState.CLOSED_MANUAL and not self.locator_ids:
                raise ValueError("人工办结必须保留回应原件")
        if self.locator_ids is not None and (
            any(not value.strip() for value in self.locator_ids)
            or len(set(self.locator_ids)) != len(self.locator_ids)
        ):
            raise ValueError("待办原件定位不得为空或重复")
        return self

    @model_serializer(mode="wrap")
    def serialize_references(self, handler):
        payload = handler(self)
        if self.schema_version == "fixture/v1":
            payload.pop("locator_ids", None)
            payload.pop("response_authority", None)
        return payload


class ActionRequest(ReviewEvidenceScope, RevisionedModel):
    action_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    review_episode_id: str = Field(min_length=1)
    review_run_id: str = Field(min_length=1)
    assessment_id: str | None = Field(default=None, min_length=1)
    rule_component_id: str | None = Field(default=None, min_length=1)
    control_origin: ControlActionOrigin | None = None
    gap_type: GapType
    target_party: ActionTarget
    requested_action: str = Field(min_length=1)
    acceptable_evidence: str = Field(min_length=1)
    due_stage: ReviewStage
    blocking_level: BlockingLevel
    trigger_evidence_span_id: str | None = None
    trigger_locator_id: str | None = Field(default=None, min_length=1)
    state: ActionState
    recompute_scope: list[str] = Field(min_length=1)
    transitions: list[ActionTransition] = Field(default_factory=list)
    gate_result_id: str = Field(min_length=1)
    publication_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_serializer(mode="wrap")
    def serialize_action_evidence(self, handler):
        payload = super().serialize_evidence_lineage(handler)
        if self.control_origin is None:
            payload.pop("control_origin", None)
        if self.schema_version == "fixture/v1":
            payload.pop("trigger_locator_id", None)
        return payload

    @model_validator(mode="after")
    def validate_gate_owned_blocking(self) -> ActionRequest:
        from app.domain.policies import derive_action_blocking_level

        if self.control_origin is None:
            if self.assessment_id is None or self.rule_component_id is None:
                raise ValueError("条款办理事项必须保留对应审核结论")
        elif (self.schema_version != "review/v2" or self.assessment_id is not None
                or self.rule_component_id is not None
                or self.control_origin.review_run_id != self.review_run_id):
            raise ValueError("其他章节的办理事项不得混用官方条款结论或不同审核记录")

        if (
            self.schema_version == "fixture/v1" and self.trigger_locator_id is not None
        ) or (
            self.schema_version == "review/v2" and self.trigger_evidence_span_id is not None
        ):
            raise ValueError("待办触发原件必须与审核资料版本一致")
        if any(item.schema_version != self.schema_version for item in self.transitions):
            raise ValueError("待办状态记录不得混用新旧资料版本")
        if self.schema_version == "review/v2":
            ids = [item.transition_id for item in self.transitions]
            if len(set(ids)) != len(ids):
                raise ValueError("待办办理记录重复")
            if (not self.transitions and self.state != ActionState.OPEN) or (
                self.transitions and self.transitions[0].from_state != ActionState.OPEN
            ):
                raise ValueError("待办须从待办理开始并保留完整办理历史")
            if self.transitions and self.transitions[-1].to_state != self.state:
                raise ValueError("待办当前情况与最后一次办理记录不一致")
            if any(
                previous.to_state != following.from_state
                or previous.occurred_at > following.occurred_at
                for previous, following in zip(self.transitions, self.transitions[1:])
            ):
                raise ValueError("待办办理记录前后不连续")

        expected = derive_action_blocking_level(self.gap_type)
        if self.control_origin is not None and self.control_origin.modality.value != "mandatory":
            expected = BlockingLevel.ATTENTION
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
