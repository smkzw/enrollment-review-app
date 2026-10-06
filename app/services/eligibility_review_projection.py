"""只读入排审核投影。

本模块把当前审核节点的活动资料、已发布 V2 事实和已发布规则确定性地装配成
工作台读取模型。它不是正式 ``ReviewRun``，不写库，不调用模型，也不把缺失资料
解释为阴性结论。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Literal, Mapping

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.contracts.clause_pack import ClausePackClause, ClausePackRestrictedClause
from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import (
    ComponentDecision,
    DatePrecision,
    ExpectationStatus,
    GapType,
    TruthValue,
)
from app.domain.contracts.evidence import ClinicalFact, ConflictGroup
from app.domain.contracts.evidence_expectations_v2 import EvidenceExpectationV2
from app.domain.contracts.facts import (
    ClinicalConflictGroupV2,
    ClinicalFactV2,
    FactAuthority,
    PartialDateRange,
)
from app.domain.contracts.judgment_search import (
    JudgmentSearchCoverageStatus,
    JudgmentSearchCoverageSummary,
)
from app.domain.contracts.rules import iter_atomic_predicates
from app.domain.publication import canonical_hash
from app.domain.expression import (
    ComponentEvaluation,
    EvaluationContext,
)
from app.domain.gates.assessment import (
    RequirementGapState,
)
from app.services.published_clause_pack import project_published_clause_pack
from app.services.fact_normalization_command_service import authority_from_active_episode
from app.services.component_review import calculate_component_review
from app.storage.evidence_expectation_repository import EvidenceExpectationV2Repository
from app.storage.evidence_locator_repositories import EvidenceLocatorRepository
from app.storage.fact_rule_link_repository import FactRuleLinkV2Repository
from app.storage.active_facts import current_fact_heads
from app.storage.judgment_search_repository import JudgmentSearchSummaryRepository
from app.storage.repositories import (
    EpisodeRepository,
    get_rule_set,
    list_expectation_templates,
)

__all__ = [
    "EligibilityClauseProjection",
    "EligibilityFactRef",
    "EligibilityReviewProjection",
    "EligibilityReviewProjectionError",
    "EligibilityReviewProjectionService",
    "adapt_clinical_fact_v2",
    "adapt_clinical_facts_v2",
    "fold_fact_chain_heads",
]

_STALE_WORK_DRAFT = object()
_STALE_METHOD_WORK_DRAFT = object()


# 按临床安全优先级选取单值 gap_type。完整缺口集合仍由 evaluator/仓储确定，
# wire 只保留一个主缺口用于列表筛选和详情摘要。
_GAP_PRIORITY: tuple[GapType, ...] = (
    GapType.SOURCE_CONFLICT,
    GapType.INTERPRETATION_CONFLICT,
    GapType.CALCULATION_CAPABILITY_UNAVAILABLE,
    GapType.PROFESSIONAL_JUDGMENT,
    GapType.APPLICABLE_POPULATION_UNVERIFIED,
    GapType.REFERENCED_FILE_MISSING,
    GapType.OBSERVATION_UNVERIFIED,
    GapType.RECORD_INCOMPLETE,
    GapType.REQUIRED_PROCEDURE_NOT_DONE,
    GapType.RESULT_FIELDS_MISSING,
    GapType.DATE_OR_ANCHOR_MISSING,
    GapType.OCR_OR_PARSE_RISK,
    GapType.DESCRIPTION_INSUFFICIENT,
    GapType.HISTORICAL_SOURCE_UNAVAILABLE,
    GapType.PROVENANCE_FOLLOWUP,
    GapType.FUTURE_STAGE_NOT_DUE,
)

_GAP_LABELS: dict[GapType, str] = {
    GapType.CALCULATION_CAPABILITY_UNAVAILABLE: "系统尚不能按方案完成计算",
    GapType.APPLICABLE_POPULATION_UNVERIFIED: "适用人群尚未核实",
    GapType.OBSERVATION_UNVERIFIED: "资料尚待核实",
    GapType.RECORD_INCOMPLETE: "本次资料未见相关记录",
    GapType.DESCRIPTION_INSUFFICIENT: "描述不充分",
    GapType.HISTORICAL_SOURCE_UNAVAILABLE: "历史来源不可用",
    GapType.REFERENCED_FILE_MISSING: "已引用文件未提供",
    GapType.REQUIRED_PROCEDURE_NOT_DONE: "必要检查未执行",
    GapType.RESULT_FIELDS_MISSING: "结果字段缺失",
    GapType.DATE_OR_ANCHOR_MISSING: "日期或锚点缺失",
    GapType.PROFESSIONAL_JUDGMENT: "研究者专业判断缺失",
    GapType.SOURCE_CONFLICT: "来源冲突",
    GapType.OCR_OR_PARSE_RISK: "识别或解析风险",
    GapType.INTERPRETATION_CONFLICT: "解释材料冲突",
    GapType.FUTURE_STAGE_NOT_DUE: "后续节点尚未到期",
    GapType.PROVENANCE_FOLLOWUP: "需溯源核对",
}

_DECISION_LABELS: dict[ComponentDecision, str] = {
    ComponentDecision.INCLUSION_MET: "符合入选标准",
    ComponentDecision.INCLUSION_NOT_MET: "不符合入选标准",
    ComponentDecision.REQUIREMENT_MET: "流程要求已完成",
    ComponentDecision.REQUIREMENT_NOT_MET: "流程要求未完成",
    ComponentDecision.EXCLUSION_TRIGGERED: "触发排除标准",
    ComponentDecision.EXCLUSION_NOT_TRIGGERED: "未触发排除标准",
    ComponentDecision.PROFESSIONAL_JUDGMENT: "无法判定",
    ComponentDecision.CONFLICT: "存在冲突",
    ComponentDecision.NOT_DUE: "尚未到期",
    ComponentDecision.NOT_APPLICABLE: "不适用",
    # 内部枚举不应出现在 wire，但保留标签避免异常路径泄露英文。
    ComponentDecision.INDETERMINATE: "无法判定",
}


@dataclass(frozen=True)
class EligibilityFactRef:
    fact_id: str
    locator_id: str
    page_number: int
    source_document_version_id: str
    page_artifact_id: str
    excerpt: str | None


@dataclass(frozen=True)
class EligibilitySourceReadRef:
    source_document_version_id: str
    page_artifact_id: str
    page_number: int
    excerpt: str | None
    disposition: str


@dataclass(frozen=True)
class EligibilityClauseProjection:
    rule_component_id: str
    rule_code: str
    rule_kind: str
    text_summary: str
    source_text: str
    parent_rule_code: str | None
    decision: str
    decision_label: str
    reason: str
    fact_refs: tuple[EligibilityFactRef, ...]
    gap_type: str | None
    determination_mode: str
    # 具体动作指令（WP06）：仅在有缺口时给出责任方/请求动作/可接受证据，
    # 与 domain.policies.ACTION_CONTENT 的注册临床合同一一对应。
    action_owner: str | None = None
    action_detail: str | None = None
    action_evidence: str | None = None
    limitation_kind: str | None = None
    source_read_refs: tuple[EligibilitySourceReadRef, ...] = ()


@dataclass(frozen=True)
class EligibilityUnassignedConflict:
    conflict_group_id: str
    member_kind: str
    member_ids: tuple[str, ...]


@dataclass(frozen=True)
class EligibilityControlObligationProjection:
    obligation_id: str
    obligation_group_id: str
    statement: str
    source_excerpts: tuple[str, ...]
    status: str
    status_label: str
    reason: str
    fact_refs: tuple[EligibilityFactRef, ...]
    continuing_note: str | None = None
    action_owner: str | None = None
    action_detail: str | None = None
    action_evidence: str | None = None
    limitation_kind: str | None = None
    source_read_refs: tuple[EligibilitySourceReadRef, ...] = ()


@dataclass(frozen=True)
class EligibilityControlProjection:
    protocol_control_id: str
    display_label: str
    title: str
    source_span_ids: tuple[str, ...]
    obligations: tuple[EligibilityControlObligationProjection, ...]


@dataclass(frozen=True)
class EligibilityReviewProjection:
    subject_id: str
    review_episode_id: str
    rule_set_id: str
    rule_set_revision: int
    evidence_snapshot_v2_id: str
    complete_processing_revision_id: str
    clauses: tuple[EligibilityClauseProjection, ...]
    controls: tuple[EligibilityControlProjection, ...] = ()
    unassigned_conflicts: tuple[EligibilityUnassignedConflict, ...] = ()
    work_draft_state: Literal["not_started", "current", "source_changed", "method_changed"] = "not_started"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EligibilityReviewProjectionError(RuntimeError):
    """投影输入缺少可安全装配的结构化闭包。"""


def _restricted_clause_projection(
    clause: ClausePackRestrictedClause,
) -> EligibilityClauseProjection:
    if clause.limitation_kind == "interpretation_unresolved":
        reason = (
            "方案原文中有这项要求，但其适用含义尚未核清："
            + "；".join(clause.unresolved_dimensions)
            + "。本项暂不能判为符合或不符合。"
        )
    else:
        reason = (
            "方案原文中有这项要求，但当前审核方式尚不能可靠判定："
            + "；".join(clause.unresolved_dimensions)
            + "。本项暂不能判为符合或不符合。"
        )
    return EligibilityClauseProjection(
        rule_component_id=clause.clause_id,
        rule_code=clause.official_code,
        rule_kind=clause.kind.value,
        text_summary=clause.title,
        source_text="\n".join(clause.source_excerpts),
        parent_rule_code=(
            None if clause.display_code == clause.official_code else clause.official_code
        ),
        decision=ComponentDecision.INDETERMINATE.value,
        decision_label=_DECISION_LABELS[ComponentDecision.INDETERMINATE],
        reason=reason,
        fact_refs=(),
        gap_type=None,
        determination_mode="restricted",
        limitation_kind=clause.limitation_kind,
        action_owner=(
            "sponsor_medical_or_project"
            if clause.limitation_kind == "interpretation_unresolved" else None
        ),
        action_detail=(
            "请澄清该要求的适用对象、时期或例外，并与本版方案原文对应。"
            if clause.limitation_kind == "interpretation_unresolved"
            else "请完善该项要求的核对方法，不要求研究者替软件补判。"
        ),
        action_evidence=(
            "方案书面澄清或正式修订"
            if clause.limitation_kind == "interpretation_unresolved"
            else "经核实的审核方法与原文对应关系"
        ),
    )


# --------------------------------------------------------------------------- V2 -> Phase 3 适配


def _phase3_date_value(value: PartialDateRange | None) -> DateValue | None:
    """保留部分日期精度；未知日期绝不借用记录/上传日期。"""
    if value is None:
        return None
    if value.precision == DatePrecision.UNKNOWN:
        return DateValue(
            value=None,
            precision=DatePrecision.UNKNOWN,
            source_text=value.source_text,
        )
    # PartialDateRange 已保证已知范围有确定边界。Phase 3 的单点日期只保留
    # 精度和下界；评估器会按该精度展开日/月/年边界。
    return DateValue(
        value=value.lower_bound,
        precision=value.precision,
        source_text=value.source_text,
    )


def adapt_clinical_fact_v2(
    fact: ClinicalFactV2, *, conflict_group_id: str | None = None
) -> ClinicalFact:
    """把一个已发布 V2 事实适配成 evaluator 使用的 Phase 3 ``ClinicalFact``。

    V2 的 locator 是当前证据导航的稳定定位身份；Phase 3 evaluator 只需携带一组
    不透明的 evidence span id，因此这里一一保留 locator id，不做猜测式转换。
    """
    return ClinicalFact(
        fact_id=fact.fact_id,
        project_id=fact.authority.project_id,
        subject_id=fact.authority.subject_id,
        review_episode_id=fact.authority.review_episode_id,
        evidence_snapshot_id=fact.authority.evidence_snapshot_v2_id,
        fact_type=fact.fact_type,
        value=fact.value,
        unit=fact.unit,
        polarity=fact.polarity,
        # V2 只有通过发布门禁的事实，没有 Phase 3 模型置信度字段；发布事实
        # 已经是 evaluator 的接受输入，确定性地表示为满确定度。
        certainty=1.0,
        effective_date=_phase3_date_value(fact.date_range),
        evidence_span_ids=list(fact.locator_ids),
        conflict_group_id=conflict_group_id,
    )


def adapt_clinical_facts_v2(
    facts: Iterable[ClinicalFactV2],
    *,
    conflict_group_by_fact: Mapping[str, str] | None = None,
) -> list[ClinicalFact]:
    """批量适配事实，并保留输入事实集合的一一对应关系。"""
    conflict_group_by_fact = conflict_group_by_fact or {}
    return [
        adapt_clinical_fact_v2(
            fact, conflict_group_id=conflict_group_by_fact.get(fact.fact_id)
        )
        for fact in facts
    ]


def fold_fact_chain_heads(facts: Iterable[ClinicalFactV2]) -> list[ClinicalFactV2]:
    """同 ``stable_identity`` 只保留最高 revision，输出稳定排序。"""
    heads: dict[str, ClinicalFactV2] = {}
    for fact in facts:
        current = heads.get(fact.stable_identity)
        if current is None or fact.revision > current.revision:
            heads[fact.stable_identity] = fact
    return sorted(heads.values(), key=lambda item: (item.revision, item.fact_id))


# --------------------------------------------------------------------------- 辅助装配


def _primary_gap(gaps: set[GapType]) -> GapType | None:
    for gap in _GAP_PRIORITY:
        if gap in gaps:
            return gap
    return None


def _decision_for_wire(decision: ComponentDecision) -> ComponentDecision:
    """保留资料缺口与研究者判断缺口的领域区别。"""
    return decision




def _expectation_views(
    expectations: Iterable[EvidenceExpectationV2],
    templates_by_id: Mapping[str, Any],
) -> list[RequirementGapState]:
    views: list[RequirementGapState] = []
    for expectation in expectations:
        template = templates_by_id.get(expectation.template_id)
        if template is None:
            raise EligibilityReviewProjectionError("资料要求的来源模板不存在，不能生成审核结果")
        # derive_gate_gap_types keys expectations by EvidenceRequirement ID. The V2
        # template's requirement_id is the canonical key, not expectation_id.
        views.append(
            RequirementGapState(
                requirement_id=template.requirement_id,
                status=expectation.status,
                gap_type=expectation.gap_type,
            )
        )
    return views


def _phase3_conflict_groups(
    session: Session | None,
    authority: FactAuthority,
    facts: list[ClinicalFactV2],
    *,
    clauses: Iterable[ClausePackClause],
    current_groups: list[ClinicalConflictGroupV2] | None = None,
    frozen_links_by_fact: Mapping[str, list[Any]] | None = None,
) -> tuple[list[ConflictGroup], dict[str, str]]:
    """反推 V2 冲突组影响的 RuleComponent，并建立事实冲突标记。"""
    from app.storage.active_conflicts import current_conflict_heads
    if session is None and (current_groups is None or frozen_links_by_fact is None):
        raise EligibilityReviewProjectionError("冻结审核缺少争议或事实索引")
    groups = current_conflict_heads(session, authority) if current_groups is None else current_groups
    if not groups:
        return [], {}

    groups = [group for group in groups if group.member_kind == "fact"]
    if not groups:
        return [], {}

    active_fact_ids = {fact.fact_id for fact in facts}
    live_groups = []
    resolved_members: list[tuple[str, list[str]]] = []
    for group in groups:
        member_set = set(group.fact_ids)
        if not member_set <= active_fact_ids:
            raise EligibilityReviewProjectionError(
                "争议资料与当前病史尚未完整衔接，不能生成审核结果"
            )
        live_groups.append(group)
        resolved_members.append((group.conflict_group_id, sorted(member_set)))
    if not live_groups:
        return [], {}
    member_ids = sorted(
        {fact_id for _, members in resolved_members for fact_id in members}
    )
    links_by_fact = frozen_links_by_fact if frozen_links_by_fact is not None else FactRuleLinkV2Repository(session).list_for_facts(
        member_ids, facts=facts
    )
    known_component_ids = {
        clause.rule_component_id for clause in clauses
    }
    phase3_groups: list[ConflictGroup] = []
    conflict_group_by_fact: dict[str, str] = {}
    members_by_group = dict(resolved_members)
    for group in live_groups:
        head_members = members_by_group.get(group.conflict_group_id, [])
        affected_component_ids = sorted(
            {
                link.target_id
                for fact_id in head_members
                for link in links_by_fact.get(fact_id, [])
                if link.target_kind == "rule_component"
                and link.target_id in known_component_ids
            }
        )
        for fact_id in head_members:
            # A missing clause index must not make a disputed fact undisputed.
            # Only predicates actually using that fact encounter this marker.
            conflict_group_by_fact.setdefault(fact_id, group.conflict_group_id)
        # 冲突可能属于不在当前 ClausePack 中的实体；这种冲突不应阻断无关条款。
        if not affected_component_ids:
            continue
        phase3_groups.append(
            ConflictGroup(
                conflict_group_id=group.conflict_group_id,
                fact_ids=head_members,
                affected_rule_component_ids=affected_component_ids,
                resolved=False,
                resolution_evidence_span_ids=[],
            )
        )
    return phase3_groups, conflict_group_by_fact


def _latest_expectations(
    session: Session, authority: FactAuthority
) -> list[EvidenceExpectationV2]:
    """按当前权威元组和模板取最新期望 revision。"""
    repository = EvidenceExpectationV2Repository(session)
    bound = repository.list_for_authority(authority)
    by_template: dict[str, EvidenceExpectationV2] = {}
    for expectation in bound:
        current = by_template.get(expectation.template_id)
        if current is None or expectation.revision > current.revision:
            by_template[expectation.template_id] = expectation
    return sorted(by_template.values(), key=lambda item: (item.revision, item.template_id))


def _requires_investigator_judgment(requirement: Any) -> bool:
    """专业诊断或评分不等于本条资料要求另需研究者书面判断。"""
    return "investigator_assessment" in {
        source.strip().casefold() for source in requirement.required_source_types
    }


def _summary_gap_requirements(
    component: ClausePackClause,
    **kwargs,
) -> dict[str, GapType]:
    return requirement_summary_gaps(component.evidence_requirements, **kwargs)


def requirement_summary_gaps(
    requirements,
    *,
    episode_stage: Any,
    summaries: Mapping[str, JudgmentSearchCoverageSummary],
    templates_by_requirement: Mapping[str, Any],
    expectations: Iterable[RequirementGapState] = (),
    workflow_stage_id: str | None = None,
) -> dict[str, GapType]:
    """Keep each search gap bound to the requirement actually searched."""
    from app.domain.policies import STAGE_RANK

    expectations = tuple(expectations)
    missing_file_requirements = {
        item.requirement_id for item in expectations
        if item.gap_type == GapType.REFERENCED_FILE_MISSING
    }
    observed_requirements = {
        item.requirement_id for item in expectations
        if item.status == ExpectationStatus.OBSERVED
    }
    gaps: dict[str, GapType] = {}
    for requirement in requirements:
        if STAGE_RANK[requirement.due_stage] > STAGE_RANK[episode_stage]:
            continue
        # Supplied-page absence cannot override an explicitly missing source.
        if requirement.requirement_id in missing_file_requirements:
            continue
        template = templates_by_requirement.get(requirement.requirement_id)
        if (
            template is not None
            and template.due_stage == episode_stage
            and template.workflow_stage_id != workflow_stage_id
        ):
            continue
        required_source_types = {
            item.strip().casefold() for item in (
                template.required_source_types
                if template is not None
                else requirement.required_source_types
            )
        }
        if not (
            _requires_investigator_judgment(requirement)
            or "investigator_assessment" in required_source_types
        ):
            continue
        summary = summaries.get(requirement.requirement_id)
        if summary is None:
            gaps[requirement.requirement_id] = GapType.OBSERVATION_UNVERIFIED
        elif summary.status == JudgmentSearchCoverageStatus.CANDIDATES_PRESENT:
            gaps[requirement.requirement_id] = GapType.OBSERVATION_UNVERIFIED
        elif summary.status in {
            JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE,
        }:
            gaps[requirement.requirement_id] = GapType.OBSERVATION_UNVERIFIED
        elif summary.status == (
            JudgmentSearchCoverageStatus.ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE
        ):
            # A contradictory coverage record is not proof of absence or applicability.
            gaps[requirement.requirement_id] = (
                GapType.OBSERVATION_UNVERIFIED
                if requirement.requirement_id in observed_requirements
                else GapType.PROFESSIONAL_JUDGMENT
            )
    return gaps


def _summary_gaps(component: ClausePackClause, **kwargs) -> set[GapType]:
    """Compatibility projection for consumers that need only the gap set."""
    return set(_summary_gap_requirements(component, **kwargs).values())


def _fact_refs(
    session: Session,
    used_fact_ids: Iterable[str],
    facts_by_id: Mapping[str, ClinicalFactV2],
    selected_locators_by_fact: Mapping[str, set[str]] | None = None,
) -> tuple[EligibilityFactRef, ...]:
    selected = [facts_by_id[fact_id] for fact_id in sorted(set(used_fact_ids))]
    locator_ids = [
        locator_id
        for fact in selected
        for locator_id in fact.locator_ids
    ]
    locators = EvidenceLocatorRepository(session).get_many(locator_ids)
    locator_by_id = {item.locator_id: item for item in locators}
    refs: list[EligibilityFactRef] = []
    for fact in selected:
        selected_locators = (selected_locators_by_fact or {}).get(fact.fact_id)
        if selected_locators is not None and (
            not selected_locators or not selected_locators <= set(fact.locator_ids)
        ):
            raise EligibilityReviewProjectionError("本次核对位置与事实原件范围不一致")
        for locator_id in fact.locator_ids:
            if selected_locators is not None and locator_id not in selected_locators:
                continue
            locator = locator_by_id.get(locator_id)
            if locator is None:
                raise EligibilityReviewProjectionError(
                    f"事实 {fact.fact_id} 的定位 {locator_id} 缺少页码，拒绝生成原件导航"
                )
            refs.append(
                EligibilityFactRef(
                    fact_id=fact.fact_id,
                    locator_id=locator_id,
                    page_number=locator.page_number,
                    source_document_version_id=locator.source_document_version_id,
                    page_artifact_id=locator.page_artifact_id,
                    excerpt=locator.excerpt,
                )
            )
    return tuple(refs)


def _selected_predicate_locators(
    selection: Any,
    component_id: str,
    evaluation: ComponentEvaluation,
    used_fact_ids: set[str],
) -> dict[str, set[str]]:
    """Narrow source navigation only for receipt-verified, non-repeat pairs."""
    source = selection.predicate_frozen_input
    if source is None or not selection.source_pair_locations:
        return {}
    identities = {
        item.predicate_id: item
        for component in source.components
        if component.rule_component_id == component_id
        for item in component.binding_predicates
    }
    outcomes = {item.identity_sha256: item for item in selection.identity_outcomes}
    pairs: dict[tuple[str, str], set[str]] = {}
    for identity, pair_id, fact_id, locator_id in selection.source_pair_locations:
        outcome = outcomes.get(identity)
        if outcome is None or pair_id not in outcome.usable_pair_ids:
            raise EligibilityReviewProjectionError("原件配对不属于本次核对的资料范围")
        pairs.setdefault((identity, fact_id), set()).add(locator_id)
    chosen: dict[str, set[str]] = {}
    unproven: set[str] = set()
    for predicate_id, result in evaluation.predicate_evaluations.items():
        fact_ids = set(result.used_fact_ids) & used_fact_ids
        if not fact_ids:
            continue
        item = identities.get(predicate_id)
        outcome = outcomes.get(item.predicate_identity_sha256) if item is not None else None
        if (item is None or outcome is None or outcome.status != "usable"
                or item.predicate.repeat_scheme is not None
                or item.predicate.occurrence_window is not None):
            unproven.update(fact_ids)
            continue
        for fact_id in fact_ids:
            locators = pairs.get((item.predicate_identity_sha256, fact_id))
            if locators:
                chosen.setdefault(fact_id, set()).update(locators)
            else:
                unproven.add(fact_id)
    return {fact_id: locators for fact_id, locators in chosen.items() if fact_id not in unproven}


def _selected_control_locators(
    selection: Any,
    identity: str,
    used_fact_ids: set[str],
) -> dict[str, set[str]]:
    """Keep an obligation's navigation within its verified source pairs."""
    if not used_fact_ids:
        return {}
    if selection is None:
        raise EligibilityReviewProjectionError("补充要求使用的事实缺少本次核对依据")
    outcome = next(
        (item for item in selection.identity_outcomes if item.identity_sha256 == identity),
        None,
    )
    if outcome is None or outcome.status != "usable":
        raise EligibilityReviewProjectionError("补充要求使用的事实缺少本次核对依据")
    chosen: dict[str, set[str]] = {}
    for pair_identity, pair_id, fact_id, locator_id in selection.source_pair_locations:
        if pair_identity != identity or fact_id not in used_fact_ids:
            continue
        if pair_id not in outcome.usable_pair_ids:
            raise EligibilityReviewProjectionError("原件配对不属于本次核对的资料范围")
        chosen.setdefault(fact_id, set()).add(locator_id)
    if set(chosen) != used_fact_ids:
        raise EligibilityReviewProjectionError("补充要求使用的事实缺少已核对的原件位置")
    return chosen


def _unassigned_conflict_projections(groups) -> tuple[EligibilityUnassignedConflict, ...]:
    return tuple(
        EligibilityUnassignedConflict(
            conflict_group_id=group.conflict_group_id,
            member_kind=group.member_kind,
            member_ids=tuple(group.event_ids or group.exposure_ids),
        )
        for group in groups if group.member_kind != "fact"
    )


def _used_fact_ids(evaluation: ComponentEvaluation) -> set[str]:
    used = set(evaluation.trigger.used_fact_ids)
    if (
        evaluation.exception is not None
        and evaluation.trigger.truth == TruthValue.TRUE
    ):
        used.update(evaluation.exception.used_fact_ids)
    return used


def _action_directive_fields(gap: GapType | None) -> dict[str, str | None]:
    """从注册动作合同生成责任方/动作/可接受证据的线上字段。"""
    if gap is None:
        return {
            "action_owner": None,
            "action_detail": None,
            "action_evidence": None,
        }
    from app.domain.policies import ACTION_CONTENT

    target, action, evidence = ACTION_CONTENT[gap]
    return {
        "action_owner": target.value,
        "action_detail": action,
        "action_evidence": evidence,
    }


def _reason(
    clause: ClausePackClause,
    *,
    decision: ComponentDecision,
    gap: GapType | None,
    summaries: Mapping[str, JudgmentSearchCoverageSummary],
    judgment_gaps: Mapping[str, GapType] | None = None,
) -> str:
    """生成一句话中文原因，未知结论必须说明具体缺口。"""
    if decision == ComponentDecision.NOT_DUE:
        return "该条款不在本次节点到期，需在方案规定的对应节点核对。"
    if decision == ComponentDecision.NOT_APPLICABLE:
        return "该条款当前不适用于本审核节点。"
    if decision == ComponentDecision.CONFLICT or gap in {
        GapType.SOURCE_CONFLICT,
        GapType.INTERPRETATION_CONFLICT,
    }:
        return "本次提交的资料中存在相互冲突的事实，尚未完成核对，因此无法判定。"
    if gap == GapType.APPLICABLE_POPULATION_UNVERIFIED:
        return "方案对该条件限定了适用人群，本例是否属于该范围尚未完成有源核对，因此不能据现有结果判定本条。"
    if gap == GapType.CALCULATION_CAPABILITY_UNAVAILABLE:
        return "方案的计算方法已有来源，但系统尚未完成所用记录的核实与计算，目前不能判定；这不表示患者缺少记录或研究者判断。"

    # 终局判定优先给结论文案；缺口转"附带提醒"，避免"未触发排除标准"却配
    # "无法判定"理由的决策-文案矛盾（C 桥接激活确定性判定后暴露）。
    if decision in {
        ComponentDecision.EXCLUSION_NOT_TRIGGERED,
        ComponentDecision.EXCLUSION_TRIGGERED,
        ComponentDecision.INCLUSION_MET,
        ComponentDecision.INCLUSION_NOT_MET,
        ComponentDecision.REQUIREMENT_MET,
        ComponentDecision.REQUIREMENT_NOT_MET,
    }:
        base = {
            ComponentDecision.EXCLUSION_NOT_TRIGGERED: "本次提交的资料中未见满足该排除条款的记录。",
            ComponentDecision.EXCLUSION_TRIGGERED: "本次提交的资料中存在满足该排除条款的记录。",
            ComponentDecision.INCLUSION_MET: "本次提交的资料支持满足该入选条款。",
            ComponentDecision.INCLUSION_NOT_MET: "本次提交的资料显示不满足该入选条款。",
            ComponentDecision.REQUIREMENT_MET: "本次提交的资料显示已完成该必做项目。",
            ComponentDecision.REQUIREMENT_NOT_MET: "本次提交的资料显示未完成该必做项目。",
        }[decision]
        if gap is not None:
            return f"{base}（另有待核对事项：{_GAP_LABELS.get(gap, "具体资料缺口")}）"
        return base

    if decision in {
        ComponentDecision.PROFESSIONAL_JUDGMENT,
        ComponentDecision.INDETERMINATE,
    } or gap in {
        GapType.PROFESSIONAL_JUDGMENT,
        GapType.OBSERVATION_UNVERIFIED,
        GapType.RECORD_INCOMPLETE,
        GapType.DATE_OR_ANCHOR_MISSING,
        GapType.OCR_OR_PARSE_RISK,
        GapType.DESCRIPTION_INSUFFICIENT,
        GapType.HISTORICAL_SOURCE_UNAVAILABLE,
        GapType.REFERENCED_FILE_MISSING,
        GapType.REQUIRED_PROCEDURE_NOT_DONE,
        GapType.RESULT_FIELDS_MISSING,
        GapType.PROVENANCE_FOLLOWUP,
    }:
        judgment_requirements = [
            item
            for item in clause.evidence_requirements
            if _requires_investigator_judgment(item)
        ]
        if gap == GapType.PROFESSIONAL_JUDGMENT:
            missing_ids = {
                key for key, value in (judgment_gaps or {}).items()
                if value == GapType.PROFESSIONAL_JUDGMENT
            }
            if not missing_ids:
                return (
                    "本次提交的资料尚未完成该条款所需研究者书面判断的核对，"
                    "目前无法判定；请先核对现有原件，不能据此认定缺少研究者判断。"
                )
            message = "本次已核对的资料中未见本条所需的研究者书面判断，因此无法判定；需补充对应记录。"
            if GapType.OBSERVATION_UNVERIFIED in (judgment_gaps or {}).values():
                message += "本条另有资料尚未核实，需分别核对。"
            return message
        if gap == GapType.OBSERVATION_UNVERIFIED:
            if any(item.requirement_id not in summaries for item in judgment_requirements):
                return (
                    "本次提交的资料尚未完成该条款所需研究者书面判断的核对，"
                    "目前无法判定；请先核对现有原件，不能据此认定缺少研究者判断。"
                )
            return "该条款所需资料尚未完成核实，目前无法判定；需先核对本次提交的原件。"
        if gap == GapType.DATE_OR_ANCHOR_MISSING:
            return "本次提交的资料中事实日期或审核节点锚点缺失，因此无法判定。"
        # 按缺口类型生成完整通顺的中文句子（第三方测试 B1/B2：名词填空
        # 拼接会产生"未见…识别或解析风险"等病句）。
        sentences: dict[GapType, str] = {
            GapType.RECORD_INCOMPLETE:
                "本次提交的资料中尚未见到足以判定该条款的病历记录，因此无法判定。",
            GapType.OCR_OR_PARSE_RISK:
                "相关原始资料的文字识别或内容解析存在不确定，需先核对原件，因此无法判定。",
            GapType.RESULT_FIELDS_MISSING:
                "相关记录缺少判定所需的具体结果数值，因此无法判定。",
            GapType.DESCRIPTION_INSUFFICIENT:
                "相关记录的描述不够充分，无法支持判定，因此无法判定。",
            GapType.HISTORICAL_SOURCE_UNAVAILABLE:
                "判定该条款需要的历史资料目前无法取得，因此无法判定。",
            GapType.REFERENCED_FILE_MISSING:
                "资料中提到了某份文件，但该文件未在本次提交中提供，因此无法判定。",
            GapType.REQUIRED_PROCEDURE_NOT_DONE:
                "该条款要求的检查或操作尚未执行，因此无法判定。",
            GapType.PROVENANCE_FOLLOWUP:
                "相关记录的来源尚需进一步核对，因此无法判定。",
            GapType.INTERPRETATION_CONFLICT:
                "对该条款的解释材料与方案原文存在不一致，因此无法判定。",
            GapType.FUTURE_STAGE_NOT_DUE:
                "该条款的资料要求属于后续审核节点，目前尚未到期。",
        }
        if gap is not None and gap in sentences:
            return sentences[gap]
        label = _GAP_LABELS.get(gap, "具体资料缺口") if gap else "可判定资料"
        return f"本次提交的资料中尚缺{label}，因此无法判定。"

    if decision == ComponentDecision.INCLUSION_MET:
        return "已找到满足该入选条件的已核实事实。"
    if decision == ComponentDecision.INCLUSION_NOT_MET:
        return "当前资料中的事实未满足该入选条件。"
    if decision == ComponentDecision.REQUIREMENT_MET:
        return "已找到满足该流程要求的已核实事实。"
    if decision == ComponentDecision.REQUIREMENT_NOT_MET:
        return "当前资料中的事实未满足该流程要求。"
    if decision == ComponentDecision.EXCLUSION_TRIGGERED:
        return "已发现满足该排除条件的事实。"
    if decision == ComponentDecision.EXCLUSION_NOT_TRIGGERED:
        return "当前资料未发现满足该排除条件的事实。"
    return "本次提交的资料不足以形成明确判定，因此无法判定。"


def _component_candidate_types(clause: ClausePackClause) -> dict[str, list[str]]:
    """Scope legacy vocabulary to a component; this is not semantic verification."""
    fact_types = sorted({requirement.fact_type for requirement in clause.evidence_requirements})
    expressions = [clause.expression]
    if clause.exception_expression is not None:
        expressions.append(clause.exception_expression)
    result = {}
    for expression in expressions:
        for predicate in iter_atomic_predicates(expression):
            key = f"{predicate.subject}.{predicate.attribute}"
            # 别名包含需求fact_type和predicate.attribute本身，
            # 使归一化产出的fact_type（可能等于attribute）也能匹配。
            aliases = list(set(fact_types + [predicate.attribute]))
            result[key] = aliases
    return result if result else {}


class EligibilityReviewProjectionService:
    """装配当前审核节点入排条款读取投影；本服务不持有写入状态。"""

    def __init__(self, artifact_store=None) -> None:
        self.artifact_store = artifact_store

    def project(
        self, session: Session, review_episode_id: str
    ) -> EligibilityReviewProjection:
        authority = authority_from_active_episode(session, review_episode_id)
        episode = EpisodeRepository(session).get(review_episode_id)
        rule_set = get_rule_set(session, authority.rule_set_id, authority.rule_set_revision)
        clause_pack = project_published_clause_pack(session, rule_set)
        if not clause_pack.clauses and not clause_pack.restricted_clauses and (
            clause_pack.control_publication is None
            or not (
                clause_pack.control_publication.catalog.controls
                or clause_pack.control_publication.catalog.restricted_statements
            )
        ):
            raise EligibilityReviewProjectionError("当前方案没有可审核的官方条款或补充要求")

        frozen_work_draft = self._completed_work_draft(
            session, authority=authority, rule_set=rule_set,
        )
        if (frozen_work_draft is not None and frozen_work_draft is not _STALE_WORK_DRAFT
                and frozen_work_draft is not _STALE_METHOD_WORK_DRAFT):
            frozen, selections = frozen_work_draft
            return self._project_frozen_work_draft(
                session, frozen=frozen, rule_set=rule_set, selections=selections,
            )

        facts = current_fact_heads(session, authority)
        clauses = tuple(clause_pack.clauses)
        from app.storage.active_conflicts import current_conflict_heads
        from app.services.patient_profile_service import PatientProfileService, PatientProfileProjectionError

        conflict_heads = current_conflict_heads(session, authority)
        unassigned_groups = [group for group in conflict_heads if group.member_kind != "fact"]
        if unassigned_groups:
            profile = PatientProfileService()
            event_ids = {item for group in unassigned_groups for item in group.event_ids}
            exposure_ids = {item for group in unassigned_groups for item in group.exposure_ids}
            try:
                # Reuse Profile selection and closure, without generating or persisting it.
                profile._validate_referential_closure(
                    facts=facts,
                    events=[item for item in profile._published_events(session, authority) if item.event_id in event_ids],
                    exposures=[item for item in profile._published_exposures(session, authority) if item.exposure_id in exposure_ids],
                    conflicts=unassigned_groups,
                    expectations=[],
                )
            except PatientProfileProjectionError as exc:
                raise EligibilityReviewProjectionError(
                    "争议资料与当前病史尚未完整衔接，不能生成审核结果"
                ) from exc
        phase3_conflicts, conflict_group_by_fact = _phase3_conflict_groups(
            session, authority, facts, clauses=clauses, current_groups=conflict_heads
        )
        phase3_facts = adapt_clinical_facts_v2(
            facts, conflict_group_by_fact=conflict_group_by_fact
        )

        templates = list_expectation_templates(
            session, authority.rule_set_id, authority.rule_set_revision
        )
        context = EvaluationContext(
            project_id=authority.project_id,
            subject_id=authority.subject_id,
            review_episode_id=authority.review_episode_id,
            evidence_snapshot_id=authority.evidence_snapshot_v2_id,
            accepted_fact_ids=[fact.fact_id for fact in phase3_facts],
            facts=phase3_facts,
            anchor_dates=dict(episode.anchor_dates),
        )
        templates_by_id = {template.template_id: template for template in templates}
        templates_by_requirement = {
            template.requirement_id: template for template in templates
        }
        expectations_v2 = _latest_expectations(session, authority)
        expectation_views = _expectation_views(expectations_v2, templates_by_id)
        summaries = JudgmentSearchSummaryRepository(session).latest_for_authority(authority)
        facts_by_id = {fact.fact_id: fact for fact in facts}

        output: list[EligibilityClauseProjection] = []
        for clause in clauses:
            component = clause_to_rule_component(clause)
            component_predicate_ids = {
                predicate.predicate_id
                for expression in (component.expression, component.exception_expression)
                if expression is not None
                for predicate in iter_atomic_predicates(expression)
            }
            # Without a completed current prepared-review workflow, every
            # predicate remains explicitly unverified.  Supplying complete empty
            # maps prevents the evaluator's legacy fact-type fallback from
            # turning unqualified facts into a negative or positive conclusion.
            component_fact_ids = {key: [] for key in component_predicate_ids}
            judgment_gaps = _summary_gap_requirements(
                clause,
                episode_stage=episode.stage,
                summaries=summaries,
                templates_by_requirement=templates_by_requirement,
                expectations=expectation_views,
                workflow_stage_id=episode.workflow_stage_id,
            )
            component_context = context.model_copy(update={
                "predicate_fact_type_aliases": _component_candidate_types(clause)})
            requirement_stage_ids = {
                requirement.requirement_id: templates_by_requirement[
                    requirement.requirement_id
                ].workflow_stage_id
                for requirement in component.evidence_requirements
                if requirement.requirement_id in templates_by_requirement
            }
            complete_requirement_stage_ids = (
                requirement_stage_ids
                if episode.workflow_stage_id is not None
                and len(requirement_stage_ids)
                == len(component.evidence_requirements)
                else None
            )
            result = calculate_component_review(
                component=component,
                rule_kind=clause.kind,
                context=component_context,
                episode_stage=episode.stage,
                expectations=expectation_views,
                conflicts=phase3_conflicts,
                workflow_stage_id=episode.workflow_stage_id,
                requirement_workflow_stage_ids=complete_requirement_stage_ids,
                source_gaps=frozenset(judgment_gaps.values()),
                predicate_fact_ids=component_fact_ids,
                unverified_predicate_ids=frozenset(component_predicate_ids),
            )
            evaluation = result.evaluation
            gaps = set(result.gaps)
            decision = _decision_for_wire(result.decision)
            # Only nonblocking provenance reminders may accompany a definite result.
            gap = _primary_gap(gaps)
            used_fact_ids = _used_fact_ids(evaluation)
            output.append(
                EligibilityClauseProjection(
                    rule_component_id=clause.rule_component_id,
                    rule_code=clause.official_code,
                    rule_kind=clause.kind.value,
                    text_summary=clause.title,
                    source_text=clause.source_text,
                    parent_rule_code=(
                        None
                        if clause.display_code == clause.official_code
                        else clause.official_code
                    ),
                    decision=decision.value,
                    decision_label=_DECISION_LABELS[decision],
                    reason=_reason(
                        clause,
                        decision=decision,
                        gap=gap,
                        summaries=summaries,
                        judgment_gaps=judgment_gaps,
                    ),
                    fact_refs=_fact_refs(session, used_fact_ids, facts_by_id),
                    gap_type=gap.value if gap is not None else None,
                    determination_mode=clause.determination_mode.value,
                    **_action_directive_fields(gap),
                )
            )

        return EligibilityReviewProjection(
            subject_id=authority.subject_id,
            review_episode_id=authority.review_episode_id,
            rule_set_id=authority.rule_set_id,
            rule_set_revision=authority.rule_set_revision,
            evidence_snapshot_v2_id=authority.evidence_snapshot_v2_id,
            complete_processing_revision_id=authority.complete_processing_revision_id,
            clauses=tuple(output) + tuple(
                _restricted_clause_projection(item)
                for item in clause_pack.restricted_clauses
            ),
            controls=_unverified_control_projections(clause_pack),
            unassigned_conflicts=_unassigned_conflict_projections(unassigned_groups),
            work_draft_state=(
                "source_changed" if frozen_work_draft is _STALE_WORK_DRAFT
                else "method_changed" if frozen_work_draft is _STALE_METHOD_WORK_DRAFT
                else "not_started"
            ),
        )

    def _completed_work_draft(self, session, *, authority, rule_set):
        """Load only the newest completed product workflow for this exact scope."""
        if self.artifact_store is None:
            return None
        from app.services.prepared_review_workflow import (
            PreparedReviewContinuation,
            require_current_review_tasks,
        )
        from app.services.review_context_assembly import (
            current_review_clinical_material_sha256,
            frozen_review_clinical_material_sha256,
            review_method_is_current,
        )
        from app.services.qualified_binding_selection import (
            build_receipt_verified_work_draft_selections,
        )
        from app.services.review_runtime_ownership import WORKFLOW_JOB_TYPE
        from app.storage.codecs import verify_payload_sha256
        from app.storage.models import JobRecord, ReviewContextSnapshotRecord
        from app.storage.review_context_repository import ReviewContextV2Repository
        from app.workflow.jobstore import JobStore

        context_repository = ReviewContextV2Repository(session)
        context_ids = [
            row.context_id
            for row in session.scalars(select(ReviewContextSnapshotRecord).where(
                ReviewContextSnapshotRecord.review_episode_id == authority.review_episode_id,
            ))
            if context_repository.get(row.context_id).authority == authority
        ]
        if not context_ids:
            return None
        rows = list(session.scalars(select(JobRecord).where(
            JobRecord.job_type == WORKFLOW_JOB_TYPE,
            func.json_extract(JobRecord.payload_json, "$.review_context_id").in_(context_ids),
        ).order_by(JobRecord.created_at.desc(), JobRecord.job_id.desc())))
        for row in rows:
            payload = verify_payload_sha256(row.payload_json, row.payload_sha256)
            context_id = payload.get("review_context_id")
            if context_id not in context_ids:
                raise EligibilityReviewProjectionError("审核工作记录与当前资料范围不一致")
            frozen = context_repository.get(context_id)
            if (
                current_review_clinical_material_sha256(session, authority)
                != frozen_review_clinical_material_sha256(frozen)
            ):
                return _STALE_WORK_DRAFT if row.state == "completed" else None
            # Never borrow an older completed result while a newer exact-scope
            # workflow is still running, failed or cancelled.
            if row.state != "completed":
                return None
            from app.services.prepared_review_workflow import CONTRACT, READABLE_CONTRACTS
            if payload.get("contract") in READABLE_CONTRACTS - {CONTRACT}:
                # History remains readable; never borrow it as a current-method draft.
                return None
            if not review_method_is_current(frozen):
                return _STALE_METHOD_WORK_DRAFT
            require_current_review_tasks(payload)
            if frozen.rule_set_sha256 != canonical_hash(rule_set.model_dump(mode="json")):
                raise EligibilityReviewProjectionError("工作稿对应的方案规则版本与当前节点不一致")
            store = JobStore(session)
            verification = store.get_last_checkpoint(row.job_id, "verification")
            ready = store.get_last_checkpoint(row.job_id, "ready")
            if verification is None or ready is None:
                raise EligibilityReviewProjectionError("工作稿标记为完成，但核对步骤记录不完整")
            if (ready[1].get("checks_complete") is not True
                    or ready[1].get("clinical_adoption") is not False
                    or ready[1].get("review_context_sha256") != frozen.context_sha256
                    or ready[1].get("children") != verification[1].get("children")):
                raise EligibilityReviewProjectionError("工作稿完成记录与本次资料不一致")
            if not PreparedReviewContinuation._dependencies_complete(
                session, row.job_id, payload, verification[1], "ready",
            ):
                raise EligibilityReviewProjectionError("工作稿仍有未完成的资料核对步骤")
            children = ready[1]["children"]
            families = ["predicate"]
            if payload.get("includes_controls"):
                families.append("control")
            selections = tuple(
                build_receipt_verified_work_draft_selections(
                    session,
                    self.artifact_store,
                    qualification_job_id=children[f"{family}_qualification"],
                    judgment_content_job_id=children.get(
                        "judgment_content" if family == "predicate"
                        else "control_judgment_content"
                    ),
                    proposition_evidence_job_id=children.get(
                        f"{family}_proposition_evidence",
                    ),
                    observation_relation_job_id=children.get(
                        f"{family}_observation_relation",
                    ),
                    frequency_evidence_job_id=children.get(
                        f"{family}_frequency_evidence",
                    ),
                    computation_input_job_id=children.get(
                        f"{family}_computation_input",
                    ),
                    history_source_search_job_id=children.get(f"{family}_history_source_search"),
                )
                for family in families
            )
            return frozen, selections
        return None

    def _project_frozen_work_draft(self, session, *, frozen, rule_set, selections):
        """Render a receipt-verified work draft without granting publication."""
        from app.services.frozen_review_calculation import calculate_frozen_review

        calculation = calculate_frozen_review(
            frozen,
            rule_set,
            work_draft_selections=selections,
        )
        from app.services.computation_atom_calculation import computation_result_note
        predicate_computations = calculation.computation_atom_evaluations.get("predicate", {})
        predicate_input = next((item.predicate_frozen_input for item in selections
                                if item.candidate_family == "predicate"), None)
        computation_notes = {
            component.rule_component_id: " ".join(filter(None, (
                computation_result_note(predicate_computations.get(entry.predicate_identity_sha256))
                for entry in (*component.trigger_predicates, *component.exception_predicates))))
            for component in (() if predicate_input is None else predicate_input.components)
        }
        clauses = {item.rule_component_id: item for item in frozen.clause_pack.clauses}
        facts_by_id = {item.fact_id: item for item in frozen.facts}
        summaries = {
            item.summary.requirement_id: item.summary
            for item in frozen.judgment_search_results
        }
        output = []
        predicate_selection = next(
            (item for item in selections if item.candidate_family == "predicate"), None
        )
        for item in calculation.components:
            clause = clauses[item.rule_component_id]
            result = item.result
            gap = _primary_gap(set(result.gaps))
            decision = _decision_for_wire(result.decision)
            output.append(EligibilityClauseProjection(
                rule_component_id=clause.rule_component_id,
                rule_code=clause.official_code,
                rule_kind=clause.kind.value,
                text_summary=clause.title,
                source_text=clause.source_text,
                parent_rule_code=(None if clause.display_code == clause.official_code
                                  else clause.official_code),
                decision=decision.value,
                decision_label=_DECISION_LABELS[decision],
                reason=_reason(
                    clause,
                    decision=decision,
                    gap=gap,
                    summaries=summaries,
                    judgment_gaps=dict(result.judgment_gaps),
                ) + ((" " + computation_notes[clause.rule_component_id])
                     if computation_notes.get(clause.rule_component_id) else "")
                  + _history_search_notice([
                      row for row in (() if predicate_selection is None else predicate_selection.history_search_results)
                      if any(entry.predicate_identity_sha256 == row["identity_sha256"]
                             and entry.predicate_id in result.evaluation.predicate_evaluations
                             and "supplied_records_history_not_seen" in
                                 result.evaluation.predicate_evaluations[entry.predicate_id].reason_codes
                             for component in predicate_selection.predicate_frozen_input.components
                             if component.rule_component_id == clause.rule_component_id
                             for entry in (*component.trigger_predicates, *component.exception_predicates))
                  ]),
                fact_refs=_fact_refs(
                    session,
                    _used_fact_ids(result.evaluation),
                    facts_by_id,
                    _selected_predicate_locators(
                        predicate_selection, clause.rule_component_id,
                        result.evaluation, _used_fact_ids(result.evaluation),
                    ) if predicate_selection is not None else None,
                ),
                gap_type=gap.value if gap is not None else None,
                determination_mode=clause.determination_mode.value,
                source_read_refs=_history_source_refs([
                    row for row in (() if predicate_selection is None else predicate_selection.history_search_results)
                    if any(entry.predicate_identity_sha256 == row["identity_sha256"]
                           for component in predicate_selection.predicate_frozen_input.components
                           if component.rule_component_id == clause.rule_component_id
                           for entry in (*component.trigger_predicates, *component.exception_predicates))
                ]),
                **_action_directive_fields(gap),
            ))

        controls = []
        control_selection = next(
            (item for item in selections if item.candidate_family == "control"), None
        )
        publication = frozen.clause_pack.control_publication
        if publication is not None:
            sources = {item.protocol_control_id: item for item in publication.catalog.controls}
            status_labels = {
                "fulfilled": "已满足",
                "unfulfilled": "尚未满足",
                "unverified": "无法判定",
                "not_applicable": "本节点不适用",
            }
            for control in calculation.control_outcomes:
                source = sources[control.protocol_control_id]
                atom_values = (
                    [atom for group in source.obligation_expression.groups for atom in group.atoms]
                    if source.obligation_expression is not None
                    else source.obligations
                )
                source_atoms = {atom.obligation_id: atom for atom in atom_values}
                obligations = []
                for obligation in control.obligations:
                    continuation = source_atoms[obligation.obligation_id].continuing_obligation
                    reasons = list(obligation.observation_reason_codes)
                    if obligation.status == "unverified":
                        reason = (
                            "本次已核对资料中缺少研究者书面判断，因此暂时无法判定。"
                            if "professional_judgment_missing" in reasons
                            else "相关原始资料尚未形成可核实的完整依据，因此暂时无法判定。"
                        )
                    elif obligation.status == "not_applicable":
                        reason = "该补充要求在当前审核节点不适用。"
                    elif obligation.status == "fulfilled":
                        reason = "当前已核实资料支持该补充要求已满足。"
                    else:
                        reason = "当前已核实资料显示该补充要求尚未满足。"
                    computation_note = computation_result_note(
                        calculation.computation_atom_evaluations.get("control", {}).get(obligation.identity_sha256))
                    if computation_note:
                        reason += " " + computation_note
                    reason += _history_search_notice([
                        row for row in (() if calculation.controls is None else calculation.controls.history_search_results)
                        if row["identity_sha256"] == obligation.identity_sha256
                    ])
                    history_rows = [row for row in (() if control_selection is None
                        else control_selection.history_search_results)
                        if row["identity_sha256"] == obligation.identity_sha256]
                    if any(row["status"] == "mentioned" for row in history_rows) and obligation.status == "unverified":
                        reason += " 检索已找到相关原文，尚待核清其对象、时间及含义，不按未发生处理。"
                    obligations.append(EligibilityControlObligationProjection(
                        obligation_id=obligation.obligation_id,
                        obligation_group_id=obligation.obligation_group_id,
                        statement=obligation.statement,
                        source_excerpts=tuple(
                            text for text in source_atoms[obligation.obligation_id].source_excerpts
                            if isinstance(text, str) and text.strip()
                        ),
                        status=obligation.status,
                        status_label=status_labels[obligation.status],
                        reason=reason,
                        source_read_refs=_history_source_refs(history_rows),
                        fact_refs=_fact_refs(
                            session, set(obligation.used_fact_ids), facts_by_id,
                            _selected_control_locators(
                                control_selection, obligation.identity_sha256,
                                set(obligation.used_fact_ids),
                            ) if (
                                source_atoms[obligation.obligation_id].evaluation is not None
                                and source_atoms[obligation.obligation_id].evaluation.repeat_scheme is None
                                and (
                                    source_atoms[obligation.obligation_id].evaluation.predicate is None
                                    or source_atoms[obligation.obligation_id].evaluation.predicate.occurrence_window is None
                                )
                            ) else None,
                        ),
                        continuing_note=_continuing_obligation_note(continuation),
                    ))
                controls.append(EligibilityControlProjection(
                    protocol_control_id=source.protocol_control_id,
                    display_label=source.display_label,
                    title=source.title,
                    source_span_ids=tuple(source.source_span_ids),
                    obligations=tuple(obligations),
                ))

        return EligibilityReviewProjection(
            subject_id=frozen.authority.subject_id,
            review_episode_id=frozen.authority.review_episode_id,
            rule_set_id=frozen.authority.rule_set_id,
            rule_set_revision=frozen.authority.rule_set_revision,
            evidence_snapshot_v2_id=frozen.authority.evidence_snapshot_v2_id,
            complete_processing_revision_id=frozen.authority.complete_processing_revision_id,
            clauses=tuple(output) + tuple(
                _restricted_clause_projection(item)
                for item in frozen.clause_pack.restricted_clauses
            ),
            controls=tuple(controls) + (
                _restricted_control_projections(publication)
                if publication is not None else ()
            ),
            unassigned_conflicts=_unassigned_conflict_projections(frozen.conflict_groups),
            work_draft_state="current",
        )


def _history_search_notice(rows) -> str:
    if not rows:
        return ""
    pages = {key for row in rows for key in row["page_keys"]}
    return f" 本次已提供的{len(pages)}页资料已核对，未见相关事件记录；按本次资料范围判断，并非额外检查证明。"


def _history_source_refs(rows) -> tuple[EligibilitySourceReadRef, ...]:
    result = {}
    for row in rows:
        for source in row.get("source_refs", []):
            for excerpt in source["excerpts"] or [{"text": None}]:
                ref = EligibilitySourceReadRef(source["source_document_version_id"],
                    source["page_artifact_id"], source["page_number"], excerpt["text"], source["disposition"])
                result[(ref.source_document_version_id, ref.page_number, ref.excerpt, ref.disposition)] = ref
    return tuple(result.values())


def _continuing_obligation_note(continuation: object | None) -> str | None:
    if continuation is None:
        return None
    period = getattr(getattr(continuation, "prospective_period", None), "period", None)
    period_value = getattr(period, "value", period)
    period_label = {
        "treatment_period": "治疗期间",
        "study_period": "研究期间",
    }.get(period_value)
    if period_label is None:
        raise ValueError("后续持续要求的期间未获支持")
    return f"{period_label}：{continuation.statement}。本次入排审核不判定后续期间是否已遵守。"


def _unverified_control_projections(clause_pack) -> tuple[EligibilityControlProjection, ...]:
    """Keep published cross-chapter requirements visible before review completes."""
    publication = clause_pack.control_publication
    if publication is None:
        return ()
    result = []
    for control in publication.catalog.controls:
        obligations = []
        if control.obligation_expression is not None:
            groups = [
                (group.obligation_group_id, group.atoms)
                for group in control.obligation_expression.groups
            ]
        else:
            groups = [("legacy", control.obligations)]
        for group_id, atoms in groups:
            obligations.extend(
                EligibilityControlObligationProjection(
                    obligation_id=atom.obligation_id,
                    obligation_group_id=group_id,
                    statement=atom.statement,
                    source_excerpts=tuple(
                        text for text in atom.source_excerpts
                        if isinstance(text, str) and text.strip()
                    ),
                    status="unverified",
                    status_label="等待资料核对",
                    reason="本次资料核对尚未完成，目前不能判断该补充要求是否满足。",
                    fact_refs=(),
                    continuing_note=_continuing_obligation_note(atom.continuing_obligation),
                )
                for atom in atoms
            )
        result.append(EligibilityControlProjection(
            protocol_control_id=control.protocol_control_id,
            display_label=control.display_label,
            title=control.title,
            source_span_ids=tuple(control.source_span_ids),
            obligations=tuple(obligations),
        ))
    result.extend(_restricted_control_projections(publication))
    return tuple(result)


def _restricted_control_projections(publication) -> tuple[EligibilityControlProjection, ...]:
    result = []
    for statement in publication.catalog.restricted_statements:
        interpretive = statement.limitation_kind == "interpretation_unresolved"
        reason = (
            "方案原文的适用含义尚未核清：" if interpretive
            else "方案原文有此要求，但当前审核尚不能可靠计算："
        ) + "；".join(statement.unresolved_dimensions) + "。本项暂不能判为符合或不符合。"
        result.append(EligibilityControlProjection(
            protocol_control_id=statement.restricted_statement_id,
            display_label="方案补充要求",
            title=statement.source_quote,
            source_span_ids=tuple(statement.source_span_ids),
            obligations=(EligibilityControlObligationProjection(
                obligation_id=statement.restricted_statement_id,
                obligation_group_id="restricted",
                statement=statement.source_quote,
                source_excerpts=(statement.source_quote,),
                status="restricted",
                limitation_kind=statement.limitation_kind,
                status_label="方案待澄清" if interpretive else "审核方法待完善",
                reason=reason,
                fact_refs=(),
                action_owner="sponsor_medical_or_project" if interpretive else None,
                action_detail=(
                    "请澄清该要求的适用对象、时期或例外，并与本版方案原文对应。"
                    if interpretive else "请完善该项要求的核对方法，不要求研究者替软件补判。"
                ),
                action_evidence="方案书面澄清或正式修订" if interpretive else "经核实的审核方法与原文对应关系",
            ),),
        ))
    return tuple(result)
def clause_to_rule_component(clause: ClausePackClause):
    """Rehydrate only evaluator inputs from a ClausePack clause."""
    from app.domain.contracts.rules import RuleComponent

    return RuleComponent(
        rule_component_id=clause.rule_component_id,
        parent_rule_id=clause.rule_id,
        display_code=clause.display_code,
        title=clause.title,
        expression=clause.expression,
        exception_expression=clause.exception_expression,
        repeat_trigger_conditions=list(clause.repeat_trigger_conditions),
        evidence_requirements=clause.evidence_requirements,
    )
