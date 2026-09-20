"""正式 V2 审核历史的只读 HTTP 适配层（薄路由）。

路由只做会话边界与协议转换：冻结记录的读取、绑定核对与完整性判断全部由
:mod:`app.services.review_history_service` 完成。本模块不导入 SQLAlchemy 或
``app.storage``（架构边界测试强制），不计算判定、不补齐缺口、不发布任何内容。

- ``GET /api/v2/subjects/{subject_id}/review-episodes/{review_episode_id}/review-runs``
  该审核节点已存储的正式 V2 运行（legacy 记录不出现；尚无正式运行时返回空列表）；
- ``GET /api/v2/subjects/{subject_id}/review-episodes/{review_episode_id}/review-runs/{review_run_id}``
  冻结运行 + 冻结输入 + 已存储结论 + 待办；未完成运行带明确状态，legacy 身份返回
  明确的不支持错误，冻结记录不完整时大声失败。

作用域与错误：审核节点必须属于路径受试者，且运行必须属于该节点（跨对象一律 404）；
存储失败经 ``translate_storage_error`` 翻译为稳定中文信封，冻结记录不完整保持大声
内部错误，绝不静默降级为“完整空报告”。本模块不做应用注册（由 owner 接入
``create_app``）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.api.v2.evidence_processing_schemas import LocatorDTO, locator_dto

from app.domain.contracts.clause_pack import DeterminationMode
from app.domain.contracts.common import ScalarValue
from app.domain.contracts.rules import TimeConstraint, iter_atomic_predicates
from app.domain.contracts.enums import (
    ActionState,
    ActionTarget,
    BlockingLevel,
    ComponentDecision,
    GapType,
    ReviewStage,
    RuleKind,
    TruthValue,
)
from app.domain.contracts.review_context_v2 import ReviewContextSnapshotV2
from app.domain.contracts.review import ReviewRun
from app.services.evidence_app_errors import translate_storage_error
from app.services.review_history_service import (
    ReviewHistoryAction,
    ReviewHistoryAssessment,
    ReviewHistoryClauseIdentity,
    ReviewHistoryRunDetail,
    ReviewHistoryRunStatus,
    ReviewHistoryRunSummary,
    get_run,
    list_runs,
)

router = APIRouter(prefix="/api/v2", tags=["v2-review-history"])

_SHA256 = r"^[0-9a-f]{64}$"


class ReviewHistoryClauseDTO(BaseModel):
    """冻结条款包中的审核要点身份（官方编号与标题原样来自冻结修订）。"""

    model_config = ConfigDict(extra="forbid")

    rule_component_id: str = Field(min_length=1)
    rule_code: str = Field(min_length=1)
    rule_display_code: str = Field(min_length=1)
    rule_title: str = Field(min_length=1)
    rule_kind: RuleKind
    determination_mode: DeterminationMode


class ReviewHistoryRunSummaryDTO(BaseModel):
    """一次正式审核的身份、冻结资料版本与持久化时间（状态只由时间戳推导）。"""

    model_config = ConfigDict(extra="forbid")

    review_run_id: str = Field(min_length=1)
    status: ReviewHistoryRunStatus
    stage: ReviewStage
    workflow_stage_id: str | None
    episode_revision: int = Field(ge=1)
    protocol_version_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    evidence_snapshot_v2_id: str = Field(min_length=1)
    complete_processing_revision_id: str = Field(min_length=1)
    context_id: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime | None
    supersedes_review_run_id: str | None


class ReviewHistoryContextDTO(BaseModel):
    """冻结输入快照的身份、来源指纹与内容规模；不含重新解释或推导结论。"""

    model_config = ConfigDict(extra="forbid")

    context_id: str = Field(min_length=1)
    review_run_id: str = Field(min_length=1)
    created_at: datetime
    evaluator_version: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    episode_revision: int = Field(ge=1)
    protocol_version_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    evidence_snapshot_v2_id: str = Field(min_length=1)
    complete_processing_revision_id: str = Field(min_length=1)
    stage: ReviewStage
    workflow_stage_id: str | None
    rule_set_sha256: str = Field(pattern=_SHA256)
    clause_pack_sha256: str = Field(pattern=_SHA256)
    protocol_integrity_gate_result_id: str = Field(min_length=1)
    fact_count: int = Field(ge=0)
    expectation_count: int = Field(ge=0)
    conflict_group_count: int = Field(ge=0)
    judgment_search_count: int = Field(ge=0)
    subject_code: str = Field(min_length=1)
    project_name: str = Field(min_length=1)
    center_code: str | None
    center_name: str | None
    official_protocol_version: str = Field(min_length=1)
    workflow_stage_label: str = Field(min_length=1)


class ReviewHistoryUnselectedObservationDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fact_id: str
    locator_ids: list[str]
    reason: str


class ReviewHistoryUnverifiedEvidenceDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    locator_id: str = Field(min_length=1)
    reason_codes: list[str] = Field(min_length=1)


class ReviewHistoryConditionDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    predicate_id: str = Field(min_length=1)
    condition_text: str | None
    truth: TruthValue
    observed_value: ScalarValue | None
    observed_unit: str | None
    fact_ids: list[str]
    locator_ids: list[str]
    reason_codes: list[str]
    selection_note: str | None = None
    calculation_basis: list[str] = Field(default_factory=list)
    not_selected: list[ReviewHistoryUnselectedObservationDTO] = Field(default_factory=list)
    unverified_evidence: list[ReviewHistoryUnverifiedEvidenceDTO] = Field(default_factory=list)


class ReviewHistoryAssessmentDTO(BaseModel):
    """一条已存储的冻结结论：判定、缺口原因、阻断级别与出处身份原样返回。"""

    model_config = ConfigDict(extra="forbid")

    assessment_id: str = Field(min_length=1)
    clause: ReviewHistoryClauseDTO
    decision: ComponentDecision
    gap_types: list[GapType] = Field(default_factory=list)
    blocking_level: BlockingLevel
    used_fact_ids: list[str] = Field(default_factory=list)
    locator_ids: list[str] = Field(default_factory=list)
    gate_result_id: str = Field(min_length=1)
    publication_fingerprint: str = Field(pattern=_SHA256)
    conditions: list[ReviewHistoryConditionDTO]


class ReviewResponseEvidenceDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    subject_id: str
    review_episode_id: str
    evidence_snapshot_v2_id: str
    complete_processing_revision_id: str
    locators: list[LocatorDTO]


class ReviewHistoryActionTransitionDTO(BaseModel):
    """待办状态转换的冻结历史（关闭待办不等于规则通过）。"""

    model_config = ConfigDict(extra="forbid")

    transition_id: str = Field(min_length=1)
    from_state: ActionState
    to_state: ActionState
    occurred_at: datetime
    reason: str = Field(min_length=1)
    locator_ids: list[str] = Field(default_factory=list)
    response_evidence: ReviewResponseEvidenceDTO | None


class ReviewHistoryControlIdentityDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocol_control_id: str = Field(min_length=1)
    obligation_id: str | None = Field(default=None, min_length=1)
    obligation_group_id: str | None = Field(default=None, min_length=1)
    display_label: str = Field(min_length=1)
    title: str = Field(min_length=1)


class ReviewHistoryActionDTO(BaseModel):
    """一条已存储待办的当前修订与完整转换记录。"""

    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1)
    assessment_id: str | None = Field(default=None, min_length=1)
    clause: ReviewHistoryClauseDTO | None
    control: ReviewHistoryControlIdentityDTO | None
    gap_type: GapType
    target_party: ActionTarget
    requested_action: str = Field(min_length=1)
    acceptable_evidence: str = Field(min_length=1)
    due_stage: ReviewStage
    blocking_level: BlockingLevel
    state: ActionState
    recompute_scope: list[str] = Field(min_length=1)
    trigger_locator_id: str | None
    record_revision: int = Field(ge=1)
    gate_result_id: str = Field(min_length=1)
    publication_fingerprint: str = Field(pattern=_SHA256)
    transitions: list[ReviewHistoryActionTransitionDTO] = Field(default_factory=list)


class ReviewHistoryRunListResponse(BaseModel):
    """审核节点的正式 V2 历史列表；空列表是合法状态。"""

    model_config = ConfigDict(extra="forbid")

    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    items: list[ReviewHistoryRunSummaryDTO] = Field(default_factory=list)


class ReviewHistoryControlDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_control_id: str = Field(min_length=1)
    display_label: str = Field(min_length=1)
    title: str = Field(min_length=1)
    modality: Literal["mandatory", "recommended", "best_effort"]
    obligation_id: str = Field(min_length=1)
    obligation_group_id: str = Field(min_length=1)
    activation: TruthValue
    observation_truth: TruthValue
    statement: str = Field(min_length=1)
    status: Literal["fulfilled", "unfulfilled", "unverified", "not_applicable"]
    protocol_excerpts: list[str | None]
    locator_ids: list[str]
    reason_codes: list[str]
    calculation_basis: list[str] = Field(default_factory=list)
    unverified_evidence: list[ReviewHistoryUnverifiedEvidenceDTO] = Field(default_factory=list)


class ReviewHistoryControlSelectionDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity: str
    protocol_control_id: str
    display_label: str
    condition_role: str
    condition_text: str
    selection_note: str
    not_selected: list[ReviewHistoryUnselectedObservationDTO]


class ReviewHistoryRunResponse(BaseModel):
    """单次正式审核的冻结历史（运行 + 冻结输入 + 结论 + 待办）。"""

    model_config = ConfigDict(extra="forbid")

    run: ReviewHistoryRunSummaryDTO
    context: ReviewHistoryContextDTO
    assessments: list[ReviewHistoryAssessmentDTO] = Field(default_factory=list)
    actions: list[ReviewHistoryActionDTO] = Field(default_factory=list)
    missing_rule_component_ids: list[str] = Field(default_factory=list)
    evidence_locators: list[LocatorDTO]
    controls: list[ReviewHistoryControlDTO] = Field(default_factory=list)
    missing_protocol_control_ids: list[str] = Field(default_factory=list)
    control_selection_records: list[ReviewHistoryControlSelectionDTO] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_component_identity(self) -> "ReviewHistoryRunResponse":
        component_ids = [item.clause.rule_component_id for item in self.assessments]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("同一次审核出现重复的审核要点结论")
        control_keys = [(item.protocol_control_id, item.obligation_id) for item in self.controls]
        if (len(control_keys) != len(set(control_keys))
                or len(self.missing_protocol_control_ids) != len(set(self.missing_protocol_control_ids))
                or any(item.protocol_control_id in self.missing_protocol_control_ids for item in self.controls)
                or (self.run.status == "completed" and self.missing_protocol_control_ids)):
            raise ValueError("跨章节要求审核记录重复或不完整")
        assessment_ids = {item.assessment_id for item in self.assessments}
        for action in self.actions:
            if action.control is not None:
                if (action.assessment_id is not None or action.clause is not None
                        or (action.control.obligation_id is None) == (action.control.obligation_group_id is None)
                        or not any(item.protocol_control_id == action.control.protocol_control_id and (
                            item.obligation_id == action.control.obligation_id if action.control.obligation_id is not None
                            else item.obligation_group_id == action.control.obligation_group_id
                        ) for item in self.controls)):
                    raise ValueError("办理事项引用的补充要求不属于本次审核")
            elif action.clause is None or action.assessment_id not in assessment_ids:
                raise ValueError("待办引用的冻结结论不属于本次审核")
        return self


def _session(request: Request):
    """应用会话工厂：路由只调用工厂，不导入 SQLAlchemy/存储类型。"""
    return request.app.state.session_factory()


def _raise_translated(exc: Exception) -> None:
    """存储/服务层失败 -> 稳定应用错误信封；未知异常原样上抛（内部错误兜底）。"""
    translated = translate_storage_error(exc)
    if translated is not None:
        raise translated from exc
    raise exc


def _clause_dto(identity: ReviewHistoryClauseIdentity) -> ReviewHistoryClauseDTO:
    return ReviewHistoryClauseDTO(
        rule_component_id=identity.rule_component_id,
        rule_code=identity.rule_code,
        rule_display_code=identity.rule_display_code,
        rule_title=identity.rule_title,
        rule_kind=identity.rule_kind,
        determination_mode=identity.determination_mode,
    )


def _run_dto(
    run: ReviewRun, context: ReviewContextSnapshotV2, status: ReviewHistoryRunStatus
) -> ReviewHistoryRunSummaryDTO:
    """运行/冻结输入身份取自冻结上下文权威（服务已逐项核对与运行一致）。"""
    authority = context.authority
    return ReviewHistoryRunSummaryDTO(
        review_run_id=run.review_run_id,
        status=status,
        stage=context.review_episode.stage,
        workflow_stage_id=context.review_episode.workflow_stage_id,
        episode_revision=authority.episode_revision,
        protocol_version_id=authority.protocol_version_id,
        rule_set_id=authority.rule_set_id,
        rule_set_revision=authority.rule_set_revision,
        evidence_snapshot_v2_id=authority.evidence_snapshot_v2_id,
        complete_processing_revision_id=authority.complete_processing_revision_id,
        context_id=context.context_id,
        started_at=run.started_at,
        completed_at=run.completed_at,
        supersedes_review_run_id=run.supersedes_review_run_id,
    )


def _context_dto(context: ReviewContextSnapshotV2) -> ReviewHistoryContextDTO:
    authority = context.authority
    return ReviewHistoryContextDTO(
        context_id=context.context_id,
        review_run_id=context.review_run_id,
        created_at=context.created_at,
        evaluator_version=context.evaluator_version,
        project_id=authority.project_id,
        subject_id=authority.subject_id,
        review_episode_id=authority.review_episode_id,
        episode_revision=authority.episode_revision,
        protocol_version_id=authority.protocol_version_id,
        rule_set_id=authority.rule_set_id,
        rule_set_revision=authority.rule_set_revision,
        evidence_snapshot_v2_id=authority.evidence_snapshot_v2_id,
        complete_processing_revision_id=authority.complete_processing_revision_id,
        stage=context.review_episode.stage,
        workflow_stage_id=context.review_episode.workflow_stage_id,
        rule_set_sha256=context.rule_set_sha256,
        clause_pack_sha256=context.clause_pack_sha256,
        protocol_integrity_gate_result_id=context.protocol_integrity_gate_result_id,
        fact_count=len(context.facts),
        expectation_count=len(context.expectations),
        conflict_group_count=len(context.conflict_groups),
        judgment_search_count=len(context.judgment_search_results),
        subject_code=context.subject.subject_code,
        project_name=context.project_name,
        center_code=context.subject.center_code,
        center_name=context.subject.center_name,
        official_protocol_version=context.protocol_document.official_version,
        workflow_stage_label=next(
            stage.display_name for stage in context.workflow_stages
            if stage.workflow_stage_id == context.review_episode.workflow_stage_id
        ),
    )


def _observation_selection_note(ordering, has_selected: bool) -> str:
    which = "最近一次" if ordering.criterion == "latest" else "最早一次"
    if ordering.window_order == "within_window":
        requirement = f"方案要求在规定时间范围内核对{which}记录。"
    elif ordering.window_order == "before_window_check":
        requirement = f"方案要求先选取{which}记录，再核对其是否符合时间要求。"
    elif ordering.window_order == "not_applicable":
        requirement = f"方案要求核对{which}记录。"
    else:
        return "原记录未明确选取记录与限定时间范围的先后依据，不据此补推或重新选择。"
    return requirement + ("已按该要求选取记录；范围仅限本次已提供并核实的资料。"
                          if has_selected else "目前尚未确定可采用的记录。")


def _half_life_basis(constraint: TimeConstraint | None) -> list[str]:
    if constraint is None or constraint.half_life_evidence is None:
        return []
    evidence = constraint.half_life_evidence
    return [f"本项半衰期依据：{evidence.applies_to_quote}；{evidence.duration_quote}。方案要求倍数：{constraint.half_life_multiplier:g}。",
            f"所引方案原文：{evidence.source_excerpt}"]


def _condition_times(expression):
    if expression.kind == "predicate":
        yield expression.predicate.predicate_id, expression.time_constraint
    else:
        for child in expression.children:
            yield from _condition_times(child)


def _assessment_dto(
    view: ReviewHistoryAssessment, context: ReviewContextSnapshotV2,
) -> ReviewHistoryAssessmentDTO:
    assessment = view.assessment
    clause = next(item for item in context.clause_pack.clauses
                  if item.rule_component_id == assessment.rule_component_id)
    predicates = {
        item.predicate_id: item
        for expression in (clause.expression, clause.exception_expression)
        if expression is not None for item in iter_atomic_predicates(expression)
    }
    conditions = []
    time_constraints = dict(pair for expression in (clause.expression, clause.exception_expression)
                            if expression is not None for pair in _condition_times(expression))
    facts = {item.fact_id: item for item in context.facts}
    for observation in assessment.predicate_observations or ():
        predicate = predicates[observation.predicate_id]
        repeat_notes, repeat_unselected = [], []
        if observation.repeat_evaluation is not None:
            from app.projections.repeat_review_presentation import repeat_review_presentation
            repeat_notes, repeat_unselected = repeat_review_presentation(observation.repeat_evaluation, facts)
        elif observation.frequency_evaluation is not None:
            from app.projections.frequency_review_presentation import frequency_review_presentation
            repeat_notes, repeat_unselected = frequency_review_presentation(observation.frequency_evaluation, facts)
        pending_sources = {}
        for gap in observation.proposition_pair_gaps:
            pending_sources.setdefault(gap.locator_id, set()).update(gap.reasons)
        audit = observation.observation_ordering
        selection_note = None
        if audit is not None:
            ordering = predicate.observation_policy.selection
            selection_note = _observation_selection_note(ordering, bool(observation.fact_ids))
        conditions.append(ReviewHistoryConditionDTO(
            predicate_id=observation.predicate_id,
            condition_text=predicate.source_clause or "\n".join(predicate.source_clauses) or predicate.source_term,
            truth=observation.truth, observed_value=observation.observed_value,
            observed_unit=observation.observed_unit, fact_ids=observation.fact_ids,
            locator_ids=list(observation.locator_ids or ()), reason_codes=observation.reason_codes,
            selection_note=selection_note,
            calculation_basis=_half_life_basis(time_constraints.get(observation.predicate_id)) + repeat_notes,
            not_selected=([ReviewHistoryUnselectedObservationDTO(
                fact_id=item.fact_id, locator_ids=list(facts[item.fact_id].locator_ids),
                reason=("不在方案要求的时间范围内，未作为本条件的判断依据。"
                        if item.reason == "observation_out_of_window"
                        else "按方案规定的检查先后顺序，本次未采用这条记录。"),
            ) for item in audit.not_selected] if audit is not None and observation.repeat_evaluation is None else []) + [
                ReviewHistoryUnselectedObservationDTO(**item) for item in repeat_unselected
            ],
            unverified_evidence=[
                ReviewHistoryUnverifiedEvidenceDTO(locator_id=locator, reason_codes=sorted(reasons))
                for locator, reasons in sorted(pending_sources.items())
            ],
        ))
    return ReviewHistoryAssessmentDTO(
        assessment_id=assessment.assessment_id,
        clause=_clause_dto(view.clause),
        decision=assessment.decision,
        gap_types=list(assessment.gap_types),
        blocking_level=assessment.blocking_level,
        used_fact_ids=list(assessment.used_fact_ids),
        locator_ids=list(assessment.locator_ids or ()),
        gate_result_id=assessment.gate_result_id,
        publication_fingerprint=assessment.publication_fingerprint,
        conditions=conditions,
    )


def _action_dto(view: ReviewHistoryAction) -> ReviewHistoryActionDTO:
    action = view.action
    return ReviewHistoryActionDTO(
        action_id=action.action_id,
        assessment_id=action.assessment_id,
        clause=_clause_dto(view.clause) if view.clause is not None else None,
        control=ReviewHistoryControlIdentityDTO(
            protocol_control_id=view.control.protocol_control_id,
            obligation_id=view.control.obligation_id,
            obligation_group_id=view.control.obligation_group_id,
            display_label=view.control.display_label, title=view.control.title,
        ) if view.control is not None else None,
        gap_type=action.gap_type,
        target_party=action.target_party,
        requested_action=action.requested_action,
        acceptable_evidence=action.acceptable_evidence,
        due_stage=action.due_stage,
        blocking_level=action.blocking_level,
        state=action.state,
        recompute_scope=list(action.recompute_scope),
        trigger_locator_id=action.trigger_locator_id,
        record_revision=action.revision,
        gate_result_id=action.gate_result_id,
        publication_fingerprint=action.publication_fingerprint,
        transitions=[
            ReviewHistoryActionTransitionDTO(
                transition_id=transition.transition_id,
                from_state=transition.from_state,
                to_state=transition.to_state,
                occurred_at=transition.occurred_at,
                reason=transition.reason,
                locator_ids=list(transition.locator_ids or ()),
                response_evidence=ReviewResponseEvidenceDTO(
                    project_id=transition.response_authority.project_id,
                    subject_id=transition.response_authority.subject_id,
                    review_episode_id=transition.response_authority.review_episode_id,
                    evidence_snapshot_v2_id=transition.response_authority.evidence_snapshot_v2_id,
                    complete_processing_revision_id=transition.response_authority.complete_processing_revision_id,
                    locators=[locator_dto(item) for item in view.response_locators[transition.transition_id]],
                ) if transition.response_authority is not None else None,
            )
            for transition in action.transitions
        ],
    )


@router.get(
    "/subjects/{subject_id}/review-episodes/{review_episode_id}/review-runs",
    response_model=ReviewHistoryRunListResponse,
)
def list_review_runs(
    subject_id: str, review_episode_id: str, request: Request
) -> ReviewHistoryRunListResponse:
    """列出该审核节点已存储的正式 V2 运行；legacy 记录不属于正式历史。"""
    with _session(request) as session:
        try:
            summaries: tuple[ReviewHistoryRunSummary, ...] = list_runs(
                session, subject_id, review_episode_id
            )
        except Exception as exc:  # noqa: BLE001 - 读取边界统一翻译
            _raise_translated(exc)
            raise
    return ReviewHistoryRunListResponse(
        subject_id=subject_id,
        review_episode_id=review_episode_id,
        items=[
            _run_dto(item.run, item.context, item.status) for item in summaries
        ],
    )


@router.get(
    "/subjects/{subject_id}/review-episodes/{review_episode_id}/review-runs/{review_run_id}",
    response_model=ReviewHistoryRunResponse,
)
def get_review_run(
    subject_id: str, review_episode_id: str, review_run_id: str, request: Request
) -> ReviewHistoryRunResponse:
    """读取一条冻结正式审核；不重算、不发布、不查询当前资料指针。"""
    with _session(request) as session:
        try:
            detail: ReviewHistoryRunDetail = get_run(
                session, subject_id, review_episode_id, review_run_id
            )
        except Exception as exc:  # noqa: BLE001 - 读取边界统一翻译
            _raise_translated(exc)
            raise
    from app.projections.control_atom_binding_input import project_control_atom_identities
    publication = detail.context.clause_pack.control_publication
    identities = {item.identity_sha256: item for item in project_control_atom_identities(publication)} if publication else {}
    control_sources = {item.protocol_control_id: item for item in publication.catalog.controls} if publication else {}
    facts = {item.fact_id: item for item in detail.context.facts}
    selection_records = []
    for control in detail.controls:
        for identity_hash, evaluation in control.frequency_evaluations.items():
            from app.projections.frequency_review_presentation import frequency_review_presentation
            identity = identities[identity_hash]
            notes, not_selected = frequency_review_presentation(evaluation, facts)
            selection_records.append(ReviewHistoryControlSelectionDTO(
                identity=identity_hash, protocol_control_id=control.protocol_control_id,
                display_label=control_sources[control.protocol_control_id].display_label,
                condition_role={"applicability": "适用条件", "trigger": "触发条件",
                                "obligation": "审核要求", "exception": "例外条件"}[identity.layer],
                condition_text=identity.atom.statement, selection_note="\n".join(notes),
                not_selected=[ReviewHistoryUnselectedObservationDTO(**item) for item in not_selected],
            ))
        for identity_hash, evaluation in control.repeat_evaluations.items():
            from app.projections.repeat_review_presentation import repeat_review_presentation
            identity = identities[identity_hash]
            notes, not_selected = repeat_review_presentation(evaluation, facts)
            selection_records.append(ReviewHistoryControlSelectionDTO(
                identity=identity_hash, protocol_control_id=control.protocol_control_id,
                display_label=control_sources[control.protocol_control_id].display_label,
                condition_role={"applicability": "适用条件", "trigger": "触发条件",
                                "obligation": "审核要求", "exception": "例外条件"}[identity.layer],
                condition_text=identity.atom.statement, selection_note="\n".join(notes),
                not_selected=[ReviewHistoryUnselectedObservationDTO(**item) for item in not_selected],
            ))
        for identity_hash, audit in control.observation_ordering.items():
            if identity_hash in control.repeat_evaluations:
                continue
            identity = identities[identity_hash]
            selection_records.append(ReviewHistoryControlSelectionDTO(
                identity=identity_hash, protocol_control_id=control.protocol_control_id,
                display_label=control_sources[control.protocol_control_id].display_label,
                condition_role={"applicability": "适用条件", "trigger": "触发条件",
                                "obligation": "审核要求", "exception": "例外条件"}[identity.layer],
                condition_text=identity.atom.statement,
                selection_note=_observation_selection_note(
                    identity.atom.evaluation.observation_policy.selection, bool(audit.selected_fact_ids),
                ),
                not_selected=[ReviewHistoryUnselectedObservationDTO(
                    fact_id=item.fact_id, locator_ids=list(facts[item.fact_id].locator_ids),
                    reason=("不在方案要求的时间范围内，未作为本条件的判断依据。"
                            if item.reason == "observation_out_of_window"
                            else "按方案规定的检查先后顺序，本次未采用这条记录。"),
                ) for item in audit.not_selected],
            ))
    return ReviewHistoryRunResponse(
        run=_run_dto(detail.run, detail.context, detail.status),
        context=_context_dto(detail.context),
        assessments=[_assessment_dto(item, detail.context) for item in detail.assessments],
        actions=[_action_dto(item) for item in detail.actions],
        missing_rule_component_ids=list(detail.missing_rule_component_ids),
        evidence_locators=[locator_dto(item) for item in detail.evidence_locators],
        controls=[ReviewHistoryControlDTO(
            protocol_control_id=control.protocol_control_id,
            display_label=next(source.display_label for source in detail.context.clause_pack.control_publication.catalog.controls if source.protocol_control_id == control.protocol_control_id),
            title=next(source.title for source in detail.context.clause_pack.control_publication.catalog.controls if source.protocol_control_id == control.protocol_control_id),
            modality=item.modality.value,
            obligation_id=item.obligation_id, statement=item.statement, status=item.status,
            obligation_group_id=item.obligation_group_id, activation=item.activation, observation_truth=item.observation_truth,
            protocol_excerpts=item.protocol_excerpts, locator_ids=item.locator_ids,
            unverified_evidence=[ReviewHistoryUnverifiedEvidenceDTO(
                locator_id=gap.locator_id, reason_codes=sorted(set(gap.reasons)),
            ) for gap in item.unverified_evidence],
            reason_codes=sorted(set(item.reason_codes + item.observation_reason_codes)),
            calculation_basis=list(dict.fromkeys(
                note for identity in identities.values()
                if identity.protocol_control_id == control.protocol_control_id
                and (identity.layer != "obligation" or identity.atom_id == item.obligation_id)
                for note in _half_life_basis(identity.atom.time_constraint)
            )),
        ) for control in detail.controls for item in control.obligations],
        missing_protocol_control_ids=list(detail.missing_protocol_control_ids),
        control_selection_records=selection_records,
    )


__all__ = [
    "ReviewHistoryActionDTO",
    "ReviewHistoryActionTransitionDTO",
    "ReviewHistoryAssessmentDTO",
    "ReviewHistoryClauseDTO",
    "ReviewHistoryContextDTO",
    "ReviewHistoryRunListResponse",
    "ReviewHistoryRunResponse",
    "ReviewHistoryRunSummaryDTO",
    "get_review_run",
    "list_review_runs",
    "router",
]
