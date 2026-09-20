"""冻结正式审核历史的只读读取；不重算、不发布、不读当前资料指针。

本模块只从已存储的 ``review/v2`` 正式审核链读取：

- ``ReviewRun``（``REVIEW_RUN_CONFIG``：payload 哈希、列镜像与关联表核对）；
- ``ReviewContextSnapshotV2``（``ReviewContextV2Repository``：冻结输入快照）；
- ``FinalAssessment``（``FINAL_ASSESSMENT_CONFIG``）；
- ``ActionRequest``（``ActionRequestRepository``，含完整状态转换历史）。

它不调用模型、发布、装配、激活或实时投影服务，也不查询审核节点的当前活动指针，
因此后续上传/更正既不会改写、也不会阻断历史读取。规则判断、缺口原因、官方编号与
原件出处全部按冻结记录原样返回，不重新解释、不补造人判断、不给出置信度。

边界：

- 运行状态只由持久化的 ``started_at``/``completed_at`` 推导；``completed_at`` 为空
  即“未完成”，绝不当成完整报告，也不使用浏览器/当前时间补齐；
- 已完成审核必须对冻结条款包中的每个审核要点都有已存储结论，否则大声失败，而不是
  返回“完整但空”的报告；未完成审核允许部分结果，但必须带明确状态；
- 期望审核要点身份只来自本次运行自身冻结的 RuleSet 修订，并在与冻结上下文中的
  ``rule_set_sha256``/``clause_pack_sha256`` 复核一致后派生；不读项目当前指针、不重新
  求值表达式，也不把未决结论改写成通过；
- legacy ``fixture/v1`` 审核不得伪装成 V2 历史：列表只含 ``review/v2`` 记录，按身份
  读取 legacy 记录时给出明确的不支持错误；
- ``ActionRequest`` 是可修订根：历史视图返回其当前已存储修订与完整转换记录，不把
  “待办关闭”当作规则通过。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.clause_pack import DeterminationMode
from app.domain.contracts.control_review_outcome import ControlReviewOutcome
from app.domain.control_action_directives import control_action_targets
from app.domain.contracts.evidence_locator import EvidenceLocatorArtifact
from app.domain.contracts.enums import GapType, RuleKind
from app.domain.contracts.review import (
    ActionRequest,
    FinalAssessment,
    ReviewEpisode,
    ReviewRun,
)
from app.domain.contracts.review_context_v2 import ReviewContextSnapshotV2
from app.domain.contracts.rules import iter_atomic_predicates
from app.domain.publication import canonical_hash
from app.services.evidence_app_errors import EvidenceAppError
from app.storage.models import ActionRequestRecord, FinalAssessmentRecord, ReviewRunRecord
from app.storage.repositories import (
    FINAL_ASSESSMENT_CONFIG,
    GATE_RESULT_CONFIG,
    REVIEW_RUN_CONFIG,
    ActionRequestRepository,
    AppendRepository,
    EpisodeRepository,
    NotFoundError,
    ScopeViolationError,
    get_rule_set,
)
from app.storage.review_context_repository import ReviewContextV2Repository
from app.storage.review_control_repository import ReviewControlRepository
from app.storage.evidence_locator_repositories import EvidenceLocatorRepository
from app.storage.fact_authority import FactAuthorityValidator
from app.storage.review_reference_validation import validate_action_response

__all__ = [
    "ReviewHistoryAction",
    "ReviewHistoryAssessment",
    "ReviewHistoryClauseIdentity",
    "ReviewHistoryIncompleteError",
    "ReviewHistoryRunDetail",
    "ReviewHistoryRunStatus",
    "ReviewHistoryRunSummary",
    "ReviewHistoryUnsupportedError",
    "get_run",
    "list_runs",
]

#: 正式审核资料版本；legacy ``fixture/v1`` 绝不按本版本展示。
REVIEW_HISTORY_SCHEMA_VERSION = "review/v2"

#: 运行状态只由已持久化时间戳推导：有完成时间才是已完成报告。
ReviewHistoryRunStatus = Literal["completed", "in_progress"]

_STATUS_COMPLETED: ReviewHistoryRunStatus = "completed"
_STATUS_IN_PROGRESS: ReviewHistoryRunStatus = "in_progress"


class ReviewHistoryUnsupportedError(EvidenceAppError):
    """按身份请求的记录不是正式 V2 冻结审核：legacy 记录不得伪装成正式报告。"""

    status_code = 409
    code = "REVIEW_HISTORY_UNSUPPORTED"
    title = "该记录不是正式审核报告"
    recovery = "请返回审核记录列表查看可用报告；原有记录仍予保留，无需因此重新审核。"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            detail or "该记录来自旧版试运行，不能作为正式审核报告展示。"
        )


class ReviewHistoryIncompleteError(EvidenceAppError):
    """冻结记录闭包不完整：拒绝展示不完整或不可能的正式报告。"""

    status_code = 500
    code = "REVIEW_HISTORY_INCOMPLETE"
    title = "原审核记录不完整"
    recovery = "请联系维护人员核对该次审核保存的资料；系统不会展示不完整的正式报告。"

    def __init__(
        self,
        detail: str,
        *,
        review_run_id: str | None = None,
        missing_rule_component_ids: Sequence[str] = (),
    ) -> None:
        self.review_run_id = review_run_id
        self.missing_rule_component_ids = tuple(missing_rule_component_ids)
        super().__init__(detail)

    def context(self) -> dict[str, Any] | None:
        if self.review_run_id is None and not self.missing_rule_component_ids:
            return None
        return {
            "review_run_id": self.review_run_id,
            "missing_rule_component_ids": list(self.missing_rule_component_ids),
        }


@dataclass(frozen=True)
class ReviewHistoryClauseIdentity:
    """冻结条款包中的审核要点身份（官方编号与原文标题均来自冻结修订）。"""

    rule_component_id: str
    rule_code: str
    rule_display_code: str
    rule_title: str
    rule_kind: RuleKind
    determination_mode: DeterminationMode


@dataclass(frozen=True)
class ReviewHistoryRunSummary:
    """一条已存储的正式运行：合同原样返回，状态由时间戳推导。"""

    run: ReviewRun
    context: ReviewContextSnapshotV2
    status: ReviewHistoryRunStatus


@dataclass(frozen=True)
class ReviewHistoryAssessment:
    """已存储的冻结结论 + 冻结条款身份（不改写判定、不补置信度）。"""

    assessment: FinalAssessment
    clause: ReviewHistoryClauseIdentity


@dataclass(frozen=True)
class ReviewHistoryControlIdentity:
    protocol_control_id: str
    obligation_id: str | None
    obligation_group_id: str | None
    display_label: str
    title: str


@dataclass(frozen=True)
class ReviewHistoryAction:
    """已存储的待办当前修订 + 冻结条款身份；转换历史在 action 内原样保留。"""

    action: ActionRequest
    clause: ReviewHistoryClauseIdentity | None
    response_locators: dict[str, tuple[EvidenceLocatorArtifact, ...]]
    control: ReviewHistoryControlIdentity | None = None


@dataclass(frozen=True)
class ReviewHistoryRunDetail:
    """单次正式审核的冻结历史：运行、冻结输入、结论与待办。"""

    run: ReviewRun
    context: ReviewContextSnapshotV2
    status: ReviewHistoryRunStatus
    assessments: tuple[ReviewHistoryAssessment, ...]
    actions: tuple[ReviewHistoryAction, ...]
    missing_rule_component_ids: tuple[str, ...]
    evidence_locators: tuple[EvidenceLocatorArtifact, ...]
    controls: tuple[ControlReviewOutcome, ...] = ()
    missing_protocol_control_ids: tuple[str, ...] = ()


def _run_status(run: ReviewRun) -> ReviewHistoryRunStatus:
    return _STATUS_COMPLETED if run.completed_at is not None else _STATUS_IN_PROGRESS


def _evidence_lineage(
    value: ReviewRun | FinalAssessment | ActionRequest,
) -> tuple[str | None, str | None, str | None]:
    """与仓储 scope 校验相同的三指针元组；legacy 与 V2 混用必然不相等。"""
    return (
        value.evidence_snapshot_id,
        value.evidence_snapshot_v2_id,
        value.complete_processing_revision_id,
    )


def _require_subject_episode(
    session: Session, subject_id: str, review_episode_id: str
) -> ReviewEpisode:
    """审核节点必须存在且属于路径受试者；跨对象一律按记录不存在处理。"""
    episode = EpisodeRepository(session).get(review_episode_id)
    if episode.subject_id != subject_id:
        raise NotFoundError(
            f"ReviewEpisode {review_episode_id} 不属于 Subject {subject_id}"
        )
    return episode


def _require_v2_run(run: ReviewRun) -> None:
    """legacy 记录不得被静默重读为 V2 正式报告。"""
    if run.schema_version != REVIEW_HISTORY_SCHEMA_VERSION or run.context_id is None:
        raise ReviewHistoryUnsupportedError()


def _load_frozen_context(
    session: Session, run: ReviewRun, episode: ReviewEpisode
) -> ReviewContextSnapshotV2:
    """读取冻结输入并核对 run/context 身份、节点修订与资料版本绑定。"""
    context_id = run.context_id
    if context_id is None:
        # 合同保证 review/v2 必绑冻结上下文；缺失即拒绝，不按当前资料补造。
        raise ReviewHistoryIncompleteError(
            "本次审核没有绑定的冻结输入快照，系统不会展示不完整报告。",
            review_run_id=run.review_run_id,
        )
    try:
        context = ReviewContextV2Repository(session).get(context_id)
    except NotFoundError as exc:
        raise ReviewHistoryIncompleteError(
            "本次审核绑定的冻结输入快照已缺失，系统不会展示不完整报告。",
            review_run_id=run.review_run_id,
        ) from exc
    authority = context.authority
    if (
        context.review_run_id != run.review_run_id
        or authority.review_episode_id != run.review_episode_id
        or authority.episode_revision != run.episode_revision
        or authority.protocol_version_id != run.protocol_version_id
        or authority.rule_set_revision != run.rule_set_revision
        or authority.evidence_snapshot_v2_id != run.evidence_snapshot_v2_id
        or authority.complete_processing_revision_id
        != run.complete_processing_revision_id
        or context.review_episode.review_episode_id != run.review_episode_id
        or context.review_episode.revision != run.episode_revision
        or context.review_episode.project_id != episode.project_id
        or context.review_episode.subject_id != episode.subject_id
    ):
        raise ReviewHistoryIncompleteError(
            "冻结输入与本次审核、审核节点修订或资料版本不一致，拒绝展示。",
            review_run_id=run.review_run_id,
        )
    return context


def _pinned_clause_identities(
    session: Session, run: ReviewRun, context: ReviewContextSnapshotV2
) -> dict[str, ReviewHistoryClauseIdentity]:
    """读取当时保存的条款包；投影器升级不得改变历史记录的可读性。"""
    rule_set_id = context.authority.rule_set_id
    try:
        rule_set = get_rule_set(session, rule_set_id, run.rule_set_revision)
    except NotFoundError as exc:
        raise ReviewHistoryIncompleteError(
            "本次审核绑定的规则修订不存在，无法核对冻结结论。",
            review_run_id=run.review_run_id,
        ) from exc
    if (
        rule_set.rule_set_id != rule_set_id
        or rule_set.revision != run.rule_set_revision
        or rule_set.protocol_version_id != run.protocol_version_id
    ):
        raise ReviewHistoryIncompleteError(
            "冻结规则修订身份与本次审核不一致，拒绝展示。",
            review_run_id=run.review_run_id,
        )
    if canonical_hash(rule_set.model_dump(mode="json")) != context.rule_set_sha256:
        raise ReviewHistoryIncompleteError(
            "规则内容已变化，不能按当前规则解释或改写原审核记录。",
            review_run_id=run.review_run_id,
        )
    pack = context.clause_pack
    if (
        pack.clause_pack_sha256 != context.clause_pack_sha256
        or pack.rule_set_id != rule_set_id
        or pack.rule_set_revision != run.rule_set_revision
    ):
        raise ReviewHistoryIncompleteError(
            "冻结条款包与本次审核不一致，拒绝展示。",
            review_run_id=run.review_run_id,
        )
    return {
        clause.rule_component_id: ReviewHistoryClauseIdentity(
            rule_component_id=clause.rule_component_id,
            rule_code=clause.official_code,
            rule_display_code=clause.display_code,
            rule_title=clause.title,
            rule_kind=clause.kind,
            determination_mode=clause.determination_mode,
        )
        for clause in pack.clauses
    }


def _stored_assessments(
    session: Session,
    run: ReviewRun,
    episode: ReviewEpisode,
    context: ReviewContextSnapshotV2,
    clauses: dict[str, ReviewHistoryClauseIdentity],
) -> tuple[dict[str, FinalAssessment], tuple[ReviewHistoryAssessment, ...]]:
    """读取本次运行已存储的冻结结论，逐条核对归属与资料版本。

    返回 ``({审核要点身份: 冻结结论}, 按冻结条款包顺序的结论视图)``。
    """
    records = (
        session.execute(
            select(FinalAssessmentRecord).where(
                FinalAssessmentRecord.review_run_id == run.review_run_id
            )
        )
        .scalars()
        .all()
    )
    repository = AppendRepository(session, FINAL_ASSESSMENT_CONFIG)
    expected_predicates = {
        clause.rule_component_id: {
            item.predicate_id for expression in (clause.expression, clause.exception_expression)
            if expression is not None for item in iter_atomic_predicates(expression)
        } for clause in context.clause_pack.clauses
    }
    observation_policies = {
        (clause.rule_component_id, item.predicate_id): item.observation_policy
        for clause in context.clause_pack.clauses
        for expression in (clause.expression, clause.exception_expression)
        if expression is not None for item in iter_atomic_predicates(expression)
    }
    context_fact_ids = {item.fact_id for item in context.facts}
    from app.domain.contracts.predicate_binding import iter_binding_atoms, predicate_identity_sha256
    repeat_atoms = {
        (clause.rule_component_id, atom.predicate.predicate_id): atom
        for clause in context.clause_pack.clauses for expression in (clause.expression, clause.exception_expression)
        if expression is not None for atom in iter_binding_atoms(expression) if atom.predicate.repeat_scheme is not None
    }
    frequency_atoms = {
        (clause.rule_component_id, atom.predicate.predicate_id): atom
        for clause in context.clause_pack.clauses for expression in (clause.expression, clause.exception_expression)
        if expression is not None for atom in iter_binding_atoms(expression)
        if atom.predicate.occurrence_window is not None
    }
    semantic_identities = {
        (clause.rule_component_id, atom.predicate.predicate_id): predicate_identity_sha256(
            role=role, rule_component_id=clause.rule_component_id, parent_rule_id=clause.rule_id,
            official_code=clause.official_code, predicate=atom.predicate, time_constraint=atom.time_constraint,
        ) for clause in context.clause_pack.clauses
        for role, expression in (("trigger", clause.expression), ("exception", clause.exception_expression))
        if expression is not None for atom in iter_binding_atoms(expression)
        if atom.predicate.semantic_proposition is not None
    }
    context_facts = {item.fact_id: item for item in context.facts}
    stored: dict[str, FinalAssessment] = {}
    for record in sorted(records, key=lambda item: item.assessment_id):
        assessment = repository.get(record.assessment_id)
        if assessment.rule_component_id not in clauses:
            raise ReviewHistoryIncompleteError(
                "冻结结论包含条款包之外的审核要点，拒绝展示。",
                review_run_id=run.review_run_id,
            )
        if assessment.rule_component_id in stored:
            raise ReviewHistoryIncompleteError(
                "同一审核要点存在多条冻结结论，拒绝展示。",
                review_run_id=run.review_run_id,
            )
        if (
            assessment.review_run_id != run.review_run_id
            or assessment.review_episode_id != run.review_episode_id
            or assessment.subject_id != episode.subject_id
            or assessment.project_id != episode.project_id
            or assessment.protocol_version_id != run.protocol_version_id
            or assessment.rule_set_id != context.authority.rule_set_id
            or assessment.rule_set_revision != run.rule_set_revision
            or _evidence_lineage(assessment) != _evidence_lineage(run)
        ):
            raise ReviewHistoryIncompleteError(
                "冻结结论与本次审核、审核节点或资料版本不一致，拒绝展示。",
                review_run_id=run.review_run_id,
            )
        if {item.predicate_id for item in assessment.predicate_observations or ()} != expected_predicates[assessment.rule_component_id]:
            raise ReviewHistoryIncompleteError(
                "本项审核保存的条件记录不完整，暂不能展示报告。",
                review_run_id=run.review_run_id,
            )
        for observation in assessment.predicate_observations or ():
            if observation.frequency_evaluation is not None:
                frequency = observation.frequency_evaluation
                atom = frequency_atoms.get((assessment.rule_component_id, observation.predicate_id))
                if (atom is None or atom.predicate.repeat_scheme is not None
                        or atom.predicate.requires_professional_judgment
                        or frequency.atom_sha256 != canonical_hash(atom.model_dump(mode="json"))
                        or not frequency.evidence_fact_ids <= context_fact_ids
                        or any(source["fact_id"] not in context_facts
                               or source["locator_id"] not in context_facts[source["fact_id"]].locator_ids
                               for source in frequency.resolution.get("statement_sources", ()) )):
                    raise ReviewHistoryIncompleteError(
                        "频次依据与本次方案或原件范围不一致，暂不能展示报告。",
                        review_run_id=run.review_run_id,
                    )
            if observation.repeat_evaluation is not None:
                repeat = observation.repeat_evaluation
                atom = repeat_atoms.get((assessment.rule_component_id, observation.predicate_id))
                if (atom is None or repeat.atom_sha256 != canonical_hash(atom.model_dump(mode="json"))
                        or repeat.resolution.get("parent_id") != assessment.rule_component_id
                        or repeat.resolution.get("scheme_sha256") != canonical_hash(atom.predicate.repeat_scheme.model_dump(mode="json"))
                        or not repeat.evidence_fact_ids <= context_fact_ids):
                    raise ReviewHistoryIncompleteError(
                        "复查依据与本次方案或原件范围不一致，暂不能展示报告。",
                        review_run_id=run.review_run_id,
                    )
            for gap in observation.proposition_pair_gaps:
                fact = context_facts.get(gap.fact_id)
                if (gap.identity_sha256 != semantic_identities.get((assessment.rule_component_id, observation.predicate_id))
                        or fact is None or gap.locator_id not in fact.locator_ids):
                    raise ReviewHistoryIncompleteError(
                        "待核实原文与本条件或本次资料不一致，暂不能展示报告。",
                        review_run_id=run.review_run_id,
                    )
            audit = observation.observation_ordering
            if audit is None:
                continue
            policy = observation_policies[(assessment.rule_component_id, observation.predicate_id)]
            if (policy is None or policy.selection is None
                    or audit.policy_sha256 != canonical_hash(policy.model_dump(mode="json"))
                    or not set(audit.selected_fact_ids) <= context_fact_ids
                    or any(item.fact_id not in context_fact_ids for item in audit.not_selected)):
                raise ReviewHistoryIncompleteError(
                    "检查结果的选择依据与本次方案或原始资料不一致，暂不能展示报告。",
                    review_run_id=run.review_run_id,
                )
        stored[assessment.rule_component_id] = assessment
    ordered = tuple(
        ReviewHistoryAssessment(assessment=stored[rule_component_id], clause=clause)
        for rule_component_id, clause in clauses.items()
        if rule_component_id in stored
    )
    return stored, ordered


def _stored_actions(
    session: Session,
    run: ReviewRun,
    episode: ReviewEpisode,
    context: ReviewContextSnapshotV2,
    clauses: dict[str, ReviewHistoryClauseIdentity],
    assessments_by_component: dict[str, FinalAssessment],
    controls: tuple[ControlReviewOutcome, ...],
) -> tuple[ReviewHistoryAction, ...]:
    """读取本次运行已存储的待办，核对引用的冻结结论与资料版本。"""
    records = (
        session.execute(
            select(ActionRequestRecord).where(
                ActionRequestRecord.review_run_id == run.review_run_id
            )
        )
        .scalars()
        .all()
    )
    repository = ActionRequestRepository(session)
    assessments_by_id = {
        assessment.assessment_id: assessment
        for assessment in assessments_by_component.values()
    }
    ordered_records = sorted(
        records, key=lambda item: (item.rule_component_id or "", item.action_id)
    )
    views: list[ReviewHistoryAction] = []
    handled_gaps: set[tuple] = set()
    catalog = context.clause_pack.control_publication
    control_sources = {} if catalog is None else {item.protocol_control_id: item for item in catalog.catalog.controls}
    for record in ordered_records:
        action = repository.get(record.action_id)
        gate = AppendRepository(session, GATE_RESULT_CONFIG).get(action.gate_result_id)
        if (gate.result.value != "accepted" or action.action_id not in gate.accepted_entity_refs
                or gate.output_hash != canonical_hash(action.model_dump(mode="json"))):
            raise ReviewHistoryIncompleteError("办理记录与其保存依据不一致，暂不能展示。", review_run_id=run.review_run_id)
        clause = clauses.get(action.rule_component_id)
        referenced = assessments_by_id.get(action.assessment_id)
        control_identity = None
        if action.control_origin is not None:
            from app.storage.control_action_validation import validate_control_action_origin
            validate_control_action_origin(session, action)
            origin = action.control_origin
            source = control_sources.get(origin.protocol_control_id)
            if source is None:
                raise ReviewHistoryIncompleteError("办理事项不属于本次方案要求", review_run_id=run.review_run_id)
            control_identity = ReviewHistoryControlIdentity(origin.protocol_control_id, origin.obligation_id, origin.obligation_group_id, source.display_label, source.title)
            gap_key = (origin.protocol_control_id, origin.obligation_id, origin.obligation_group_id, action.gap_type)
            invalid_target = clause is not None or referenced is not None
        else:
            gap_key = (action.assessment_id, action.gap_type)
            invalid_target = (clause is None or referenced is None
                              or referenced.rule_component_id != action.rule_component_id
                              or action.gap_type not in referenced.gap_types)
        if (
            invalid_target
            or gap_key in handled_gaps
            or action.review_run_id != run.review_run_id
            or action.review_episode_id != run.review_episode_id
            or action.subject_id != episode.subject_id
            or action.project_id != episode.project_id
            or action.protocol_version_id != run.protocol_version_id
            or action.rule_set_id != context.authority.rule_set_id
            or action.rule_set_revision != run.rule_set_revision
            or _evidence_lineage(action) != _evidence_lineage(run)
        ):
            raise ReviewHistoryIncompleteError(
                "待办与本次审核、冻结结论或资料版本不一致，拒绝展示。",
                review_run_id=run.review_run_id,
            )
        handled_gaps.add(gap_key)
        response_locators = {}
        for transition in action.transitions:
            validate_action_response(session, action, transition)
            response_locators[transition.transition_id] = tuple(
                EvidenceLocatorRepository(session).get_many(list(transition.locator_ids or ()))
            )
        views.append(ReviewHistoryAction(action=action, clause=clause, control=control_identity, response_locators=response_locators))
    expected_gaps = {
        (assessment.assessment_id, gap)
        for assessment in assessments_by_id.values() for gap in assessment.gap_types
    } | {(control.protocol_control_id, item.obligation_id, item.obligation_group_id, item.gap_type)
         for control in controls for item in control_action_targets(control)}
    if run.completed_at is not None and handled_gaps != expected_gaps:
        raise ReviewHistoryIncompleteError(
            "本次审核缺少部分问题的办理要求，暂不能展示为完整报告。",
            review_run_id=run.review_run_id,
        )
    return tuple(views)


def list_runs(
    session: Session, subject_id: str, review_episode_id: str
) -> tuple[ReviewHistoryRunSummary, ...]:
    """列出该审核节点已存储的正式 V2 运行（按持久化开始时间升序）。

    legacy ``fixture/v1`` 运行不属于正式 V2 历史，因此不出现；按身份读取时另行给出
    明确的不支持错误。尚未有任何正式运行时返回空元组（空历史是合法状态）。每条记录
    在返回前都核对冻结输入与运行、节点修订、资料版本的绑定，宁可大声失败也不展示
    绑定已损坏的记录。
    """
    episode = _require_subject_episode(session, subject_id, review_episode_id)
    records = (
        session.execute(
            select(ReviewRunRecord).where(
                ReviewRunRecord.review_episode_id == review_episode_id
            )
        )
        .scalars()
        .all()
    )
    repository = AppendRepository(session, REVIEW_RUN_CONFIG)
    summaries: list[ReviewHistoryRunSummary] = []
    for record in records:
        run = repository.get(record.review_run_id)
        if run.schema_version != REVIEW_HISTORY_SCHEMA_VERSION:
            continue
        context = _load_frozen_context(session, run, episode)
        summaries.append(
            ReviewHistoryRunSummary(
                run=run, context=context, status=_run_status(run)
            )
        )
    summaries.sort(key=lambda item: (item.run.started_at, item.run.review_run_id))
    return tuple(summaries)


def get_run(
    session: Session, subject_id: str, review_episode_id: str, review_run_id: str
) -> ReviewHistoryRunDetail:
    """读取一条冻结正式审核：运行 + 冻结输入 + 已存储结论 + 待办。

    身份（运行/节点/受试者）与冻结绑定不一致时失败；legacy 运行给出明确的不支持
    错误。已完成运行缺少任一期望审核要点结论时大声失败，绝不返回“完整但空”的报告；
    未完成运行允许部分结果并显式列出未完成的审核要点身份。
    """
    episode = _require_subject_episode(session, subject_id, review_episode_id)
    run = AppendRepository(session, REVIEW_RUN_CONFIG).get(review_run_id)
    if run.review_episode_id != review_episode_id:
        raise NotFoundError(
            f"ReviewRun {review_run_id} 不属于 ReviewEpisode {review_episode_id}"
        )
    _require_v2_run(run)
    context = _load_frozen_context(session, run, episode)
    clauses = _pinned_clause_identities(session, run, context)
    assessments, ordered_assessments = _stored_assessments(
        session, run, episode, context, clauses
    )
    missing = tuple(
        rule_component_id
        for rule_component_id in clauses
        if rule_component_id not in assessments
    )
    if run.completed_at is not None and missing:
        raise ReviewHistoryIncompleteError(
            f"本次审核标记为已完成，但缺少 {len(missing)} 个审核要点的冻结结论，"
            "系统不会展示不完整报告。",
            review_run_id=run.review_run_id,
            missing_rule_component_ids=missing,
        )
    publication = context.clause_pack.control_publication
    expected_controls = () if publication is None else tuple(
        item.protocol_control_id for item in publication.catalog.controls
    )
    try:
        control_snapshot = ReviewControlRepository(session).get_or_none(review_run_id) if expected_controls else None
    except ScopeViolationError as exc:
        raise ReviewHistoryIncompleteError(
            "本次保存的补充要求与审核资料不一致，暂不能展示该报告。",
            review_run_id=review_run_id,
        ) from exc
    controls = tuple(control_snapshot.outcomes) if control_snapshot is not None else ()
    missing_controls = expected_controls if control_snapshot is None else ()
    if run.completed_at is not None and missing_controls:
        raise ReviewHistoryIncompleteError(
            "本次审核缺少跨章节要求的保存结果，暂不能展示为完整报告。",
            review_run_id=review_run_id,
        )
    actions = _stored_actions(session, run, episode, context, clauses, assessments, controls)
    unselected_fact_ids = {
        excluded.fact_id for item in ordered_assessments
        for observation in item.assessment.predicate_observations or ()
        if observation.observation_ordering is not None
        for excluded in observation.observation_ordering.not_selected
    }
    unselected_fact_ids.update(
        excluded.fact_id for control in controls for audit in control.observation_ordering.values()
        for excluded in audit.not_selected
    )
    unselected_fact_ids.update(
        fact_id for item in ordered_assessments for observation in item.assessment.predicate_observations or ()
        if observation.repeat_evaluation is not None for fact_id in observation.repeat_evaluation.evidence_fact_ids
    )
    unselected_fact_ids.update(
        fact_id for control in controls for repeat in control.repeat_evaluations.values()
        for fact_id in repeat.evidence_fact_ids
    )
    unselected_fact_ids.update(
        fact_id for item in ordered_assessments for observation in item.assessment.predicate_observations or ()
        if observation.frequency_evaluation is not None for fact_id in observation.frequency_evaluation.evidence_fact_ids
    )
    unselected_fact_ids.update(
        fact_id for control in controls for frequency in control.frequency_evaluations.values()
        for fact_id in frequency.evidence_fact_ids
    )
    locator_ids = sorted({
        locator_id
        for item in ordered_assessments
        for locator_id in (item.assessment.locator_ids or ())
    } | {locator_id for control in controls for item in control.obligations for locator_id in item.locator_ids}
      | {gap.locator_id for control in controls for item in control.obligations for gap in item.unverified_evidence}
      | {gap.locator_id for item in ordered_assessments
         for observation in item.assessment.predicate_observations or () for gap in observation.proposition_pair_gaps}
      | {locator for fact in context.facts if fact.fact_id in unselected_fact_ids for locator in fact.locator_ids})
    FactAuthorityValidator(session).validate_locators(context.authority, locator_ids)
    locators = EvidenceLocatorRepository(session).get_many(locator_ids)
    return ReviewHistoryRunDetail(
        run=run,
        context=context,
        status=_run_status(run),
        assessments=ordered_assessments,
        actions=actions,
        missing_rule_component_ids=missing,
        evidence_locators=tuple(locators),
        controls=controls,
        missing_protocol_control_ids=missing_controls,
    )
