"""只读入排审核投影。

本模块把当前审核节点的活动资料、已发布 V2 事实和已发布规则确定性地装配成
工作台读取模型。它不是正式 ``ReviewRun``，不写库，不调用模型，也不把缺失资料
解释为阴性结论。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from sqlalchemy.orm import Session

from app.domain.contracts.clause_pack import ClausePackClause
from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import (
    ComponentDecision,
    DatePrecision,
    GapType,
    TruthValue,
)
from app.domain.contracts.evidence import ClinicalFact, ConflictGroup, EvidenceExpectation
from app.domain.contracts.evidence_expectations_v2 import EvidenceExpectationV2
from app.domain.contracts.facts import (
    ClinicalFactV2,
    FactAuthority,
    PartialDateRange,
)
from app.domain.contracts.judgment_search import (
    JudgmentSearchCoverageStatus,
    JudgmentSearchCoverageSummary,
)
from app.domain.expression import (
    ComponentEvaluation,
    EvaluationContext,
    evaluate_component,
)
from app.domain.gates.assessment import (
    derive_component_decision,
    derive_gate_gap_types,
)
from app.projections.clause_pack import project_clause_pack
from app.services.fact_normalization_command_service import authority_from_active_episode
from app.storage.evidence_expectation_repository import EvidenceExpectationV2Repository
from app.storage.evidence_locator_repositories import EvidenceLocatorRepository
from app.storage.fact_repositories import (
    ClinicalConflictGroupV2Repository,
    ClinicalFactV2Repository,
)
from app.storage.fact_rule_link_repository import FactRuleLinkV2Repository
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


# 按临床安全优先级选取单值 gap_type。完整缺口集合仍由 evaluator/仓储确定，
# wire 只保留一个主缺口用于列表筛选和详情摘要。
_GAP_PRIORITY: tuple[GapType, ...] = (
    GapType.SOURCE_CONFLICT,
    GapType.INTERPRETATION_CONFLICT,
    GapType.PROFESSIONAL_JUDGMENT,
    GapType.OBSERVATION_UNVERIFIED,
    GapType.RECORD_INCOMPLETE,
    GapType.REFERENCED_FILE_MISSING,
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
    GapType.OBSERVATION_UNVERIFIED: "资料尚待核实",
    GapType.RECORD_INCOMPLETE: "病历记录不完整",
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


@dataclass(frozen=True)
class EligibilityClauseProjection:
    rule_code: str
    rule_kind: str
    text_summary: str
    parent_rule_code: str | None
    decision: str
    decision_label: str
    reason: str
    fact_refs: tuple[EligibilityFactRef, ...]
    gap_type: str | None
    determination_mode: str


@dataclass(frozen=True)
class EligibilityReviewProjection:
    subject_id: str
    review_episode_id: str
    rule_set_id: str
    rule_set_revision: int
    evidence_snapshot_v2_id: str
    complete_processing_revision_id: str
    clauses: tuple[EligibilityClauseProjection, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EligibilityReviewProjectionError(RuntimeError):
    """投影输入缺少可安全装配的结构化闭包。"""


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
    """内部 indeterminate 不能越过 API 边界；统一表示为无法判定。"""
    if decision == ComponentDecision.INDETERMINATE:
        return ComponentDecision.PROFESSIONAL_JUDGMENT
    return decision




def _expectation_views(
    expectations: Iterable[EvidenceExpectationV2],
    templates_by_id: Mapping[str, Any],
) -> list[EvidenceExpectation]:
    views: list[EvidenceExpectation] = []
    for expectation in expectations:
        template = templates_by_id.get(expectation.template_id)
        if template is None:
            continue
        # derive_gate_gap_types keys expectations by EvidenceRequirement ID. The V2
        # template's requirement_id is the canonical key, not expectation_id.
        views.append(
            EvidenceExpectation.model_construct(
                schema_version="fixture/v1",
                expectation_id=expectation.expectation_id,
                requirement_id=template.requirement_id,
                review_episode_id=expectation.authority.review_episode_id,
                status=expectation.status,
                evidence_span_ids=list(expectation.locator_ids),
                gap_type=expectation.gap_type,
            )
        )
    return views


def _phase3_conflict_groups(
    session: Session,
    authority: FactAuthority,
    facts: list[ClinicalFactV2],
    *,
    clauses: Iterable[ClausePackClause],
) -> tuple[list[ConflictGroup], dict[str, str]]:
    """反推 V2 冲突组影响的 RuleComponent，并建立事实冲突标记。"""
    groups = ClinicalConflictGroupV2Repository(session).list_for_authority(authority)
    if not groups:
        return [], {}

    # 只读当前事实链头；已被事实修订替代的冲突组由 correction commit 过滤，
    # 同时避免旧事实 revision 重新把旧冲突带入本次求值。
    try:
        from app.storage.fact_correction_commit_repository import (
            FactCorrectionCommitRepository,
        )

        superseded_groups = FactCorrectionCommitRepository(session).superseded_conflict_ids(
            authority
        )
    except ImportError:  # pragma: no cover - 兼容旧数据库初始化顺序
        superseded_groups = set()
    groups = [
        group
        for group in groups
        if group.conflict_group_id not in superseded_groups
        and group.member_kind == "fact"
    ]
    if not groups:
        return [], {}

    active_fact_ids = {fact.fact_id for fact in facts}
    member_ids = sorted({fact_id for group in groups for fact_id in group.fact_ids})
    missing_members = sorted(set(member_ids) - active_fact_ids)
    if missing_members:
        raise EligibilityReviewProjectionError(
            "冲突组引用了已折叠链头之外的事实，拒绝静默并入历史事实："
            f"{missing_members}"
        )

    links_by_fact = FactRuleLinkV2Repository(session).list_for_facts(
        member_ids, facts=facts
    )
    known_component_ids = {
        clause.rule_component_id for clause in clauses
    }
    phase3_groups: list[ConflictGroup] = []
    conflict_group_by_fact: dict[str, str] = {}
    for group in groups:
        affected_component_ids = sorted(
            {
                link.target_id
                for fact_id in group.fact_ids
                for link in links_by_fact.get(fact_id, [])
                if link.target_kind == "rule_component"
                and link.target_id in known_component_ids
            }
        )
        # 冲突可能属于不在当前 ClausePack 中的实体；这种冲突不应阻断无关条款。
        if not affected_component_ids:
            continue
        phase3_groups.append(
            ConflictGroup(
                conflict_group_id=group.conflict_group_id,
                fact_ids=list(group.fact_ids),
                affected_rule_component_ids=affected_component_ids,
                resolved=False,
                resolution_evidence_span_ids=[],
            )
        )
        for fact_id in group.fact_ids:
            # 一个 Phase 3 fact 只能携带一个冲突组标记；按冲突组 ID 稳定取最先者。
            conflict_group_by_fact.setdefault(fact_id, group.conflict_group_id)
    return phase3_groups, conflict_group_by_fact


def _latest_expectations(
    session: Session, authority: FactAuthority
) -> list[EvidenceExpectationV2]:
    """按当前权威元组和模板取最新期望 revision。"""
    repository = EvidenceExpectationV2Repository(session)
    bound = [
        expectation
        for expectation in repository.list_by_episode(authority.review_episode_id)
        if expectation.authority == authority
    ]
    by_template: dict[str, EvidenceExpectationV2] = {}
    for expectation in bound:
        current = by_template.get(expectation.template_id)
        if current is None or expectation.revision > current.revision:
            by_template[expectation.template_id] = expectation

    # latest_by_template 是仓储提供的权威读取入口；在多权威历史并存时，
    # 仍以当前 authority 过滤后的 list_by_episode 结果为准，防止旧版本串入。
    for template_id in tuple(by_template):
        latest = repository.latest_by_template(
            authority.review_episode_id, template_id
        )
        if latest is not None and latest.authority == authority:
            by_template[template_id] = latest
    return sorted(by_template.values(), key=lambda item: (item.revision, item.template_id))


def _requires_investigator_judgment(
    component: ClausePackClause, requirement: Any
) -> bool:
    """判断摘要既可由资料类型声明，也可由条款结构声明。"""
    if component.determination_mode.value == "investigator_judgment":
        return True
    return "investigator_assessment" in {
        source.strip().casefold() for source in requirement.required_source_types
    }


def _summary_gaps(
    component: ClausePackClause,
    *,
    episode_stage: Any,
    summaries: Mapping[str, JudgmentSearchCoverageSummary],
    templates_by_requirement: Mapping[str, Any],
) -> set[GapType]:
    """把判断检索摘要的结构化状态转换成当前组件缺口。"""
    from app.domain.policies import STAGE_RANK

    gaps: set[GapType] = set()
    for requirement in component.evidence_requirements:
        if STAGE_RANK[requirement.due_stage] > STAGE_RANK[episode_stage]:
            continue
        template = templates_by_requirement.get(requirement.requirement_id)
        required_source_types = {
            item.strip().casefold() for item in (
                template.required_source_types
                if template is not None
                else requirement.required_source_types
            )
        }
        if not (
            _requires_investigator_judgment(component, requirement)
            or "investigator_assessment" in required_source_types
        ):
            continue
        summary = summaries.get(requirement.requirement_id)
        if summary is None:
            gaps.add(GapType.PROFESSIONAL_JUDGMENT)
        elif summary.status == JudgmentSearchCoverageStatus.CANDIDATES_PRESENT:
            gaps.add(GapType.OBSERVATION_UNVERIFIED)
        elif summary.status in {
            JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE,
        }:
            gaps.add(GapType.OBSERVATION_UNVERIFIED)
        elif summary.status == (
            JudgmentSearchCoverageStatus.ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE
        ):
            gaps.add(GapType.PROFESSIONAL_JUDGMENT)
    return gaps


def _fact_refs(
    session: Session,
    used_fact_ids: Iterable[str],
    facts_by_id: Mapping[str, ClinicalFactV2],
) -> tuple[EligibilityFactRef, ...]:
    selected = [facts_by_id[fact_id] for fact_id in sorted(set(used_fact_ids))]
    locator_ids = [
        locator_id
        for fact in selected
        for locator_id in fact.locator_ids
    ]
    locators = EvidenceLocatorRepository(session).get_many(locator_ids)
    page_by_locator = {item.locator_id: item.page_number for item in locators}
    refs: list[EligibilityFactRef] = []
    for fact in selected:
        for locator_id in fact.locator_ids:
            page_number = page_by_locator.get(locator_id)
            if page_number is None:
                raise EligibilityReviewProjectionError(
                    f"事实 {fact.fact_id} 的定位 {locator_id} 缺少页码，拒绝生成原件导航"
                )
            refs.append(
                EligibilityFactRef(
                    fact_id=fact.fact_id,
                    locator_id=locator_id,
                    page_number=page_number,
                )
            )
    return tuple(refs)


def _used_fact_ids(evaluation: ComponentEvaluation) -> set[str]:
    used = set(evaluation.trigger.used_fact_ids)
    if (
        evaluation.exception is not None
        and evaluation.trigger.truth == TruthValue.TRUE
    ):
        used.update(evaluation.exception.used_fact_ids)
    return used


def _reason(
    clause: ClausePackClause,
    *,
    decision: ComponentDecision,
    gap: GapType | None,
    summaries: Mapping[str, JudgmentSearchCoverageSummary],
) -> str:
    """生成一句话中文原因，未知结论必须说明具体缺口。"""
    if decision == ComponentDecision.NOT_DUE:
        return "该条款对应的资料要求属于后续审核节点，目前尚未到期。"
    if decision == ComponentDecision.NOT_APPLICABLE:
        return "该条款当前不适用于本审核节点。"
    if decision == ComponentDecision.CONFLICT or gap in {
        GapType.SOURCE_CONFLICT,
        GapType.INTERPRETATION_CONFLICT,
    }:
        return "本次提交的资料中存在相互冲突的事实，尚未完成核对，因此无法判定。"

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
            if _requires_investigator_judgment(clause, item)
        ]
        if gap == GapType.PROFESSIONAL_JUDGMENT:
            missing_summary = next(
                (
                    item
                    for item in judgment_requirements
                    if item.requirement_id not in summaries
                ),
                None,
            )
            if missing_summary is not None:
                return (
                    "本次提交的资料中未见该条款对应的研究者书面判断，且尚无完整的"
                    "判断检索摘要，因此无法判定。"
                )
            return "本次提交的资料中未见可用于确认该条款的研究者专业判断，因此无法判定。"
        if gap == GapType.OBSERVATION_UNVERIFIED:
            return "本次提交的资料中发现疑似相关记录，但尚未完成原件核实，因此无法判定。"
        if gap == GapType.DATE_OR_ANCHOR_MISSING:
            return "本次提交的资料中事实日期或审核节点锚点缺失，因此无法判定。"
        label = _GAP_LABELS.get(gap, "具体资料缺口") if gap else "可判定资料"
        return f"本次提交的资料中未见可用于判定该条款的{label}，因此无法判定。"

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


class EligibilityReviewProjectionService:
    """装配当前审核节点入排条款读取投影；本服务不持有写入状态。"""

    def project(
        self, session: Session, review_episode_id: str
    ) -> EligibilityReviewProjection:
        authority = authority_from_active_episode(session, review_episode_id)
        episode = EpisodeRepository(session).get(review_episode_id)
        rule_set = get_rule_set(session, authority.rule_set_id, authority.rule_set_revision)
        clause_pack = project_clause_pack(rule_set)

        fact_repository = ClinicalFactV2Repository(session)
        raw_facts = [
            fact
            for fact in fact_repository.list_for_authority(authority)
            if fact.authority == authority
        ]
        try:
            from app.storage.fact_correction_repository import FactCorrectionRepository

            superseded_fact_ids = FactCorrectionRepository(session).superseded_entity_ids(
                authority
            )
        except ImportError:  # pragma: no cover - compatibility with pre-correction DB
            superseded_fact_ids = set()
        raw_facts = [
            fact for fact in raw_facts if fact.fact_id not in superseded_fact_ids
        ]
        facts = fold_fact_chain_heads(raw_facts)
        clauses = tuple(clause_pack.clauses)
        phase3_conflicts, conflict_group_by_fact = _phase3_conflict_groups(
            session, authority, facts, clauses=clauses
        )
        phase3_facts = adapt_clinical_facts_v2(
            facts, conflict_group_by_fact=conflict_group_by_fact
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

        templates = list_expectation_templates(
            session, authority.rule_set_id, authority.rule_set_revision
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
            evaluation = evaluate_component(component, context)
            gaps = derive_gate_gap_types(
                component=component,
                evaluation=evaluation,
                episode_stage=episode.stage,
                expectations=expectation_views,
                conflict_groups=phase3_conflicts,
            )
            gaps.update(
                _summary_gaps(
                    clause,
                    episode_stage=episode.stage,
                    summaries=summaries,
                    templates_by_requirement=templates_by_requirement,
                )
            )
            if evaluation.trigger.truth == TruthValue.UNKNOWN and not gaps:
                gaps.add(GapType.RECORD_INCOMPLETE)
            decision = _decision_for_wire(
                derive_component_decision(
                    rule_kind=clause.kind,
                    evaluation=evaluation,
                    gaps=gaps,
                )
            )
            # derive_component_decision can return a definitive value even when a weak
            # source gap is present; preserve that determination while exposing the gap.
            gap = _primary_gap(gaps)
            used_fact_ids = _used_fact_ids(evaluation)
            output.append(
                EligibilityClauseProjection(
                    rule_code=clause.official_code,
                    rule_kind=clause.kind.value,
                    text_summary=clause.title,
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
                    ),
                    fact_refs=_fact_refs(session, used_fact_ids, facts_by_id),
                    gap_type=gap.value if gap is not None else None,
                    determination_mode=clause.determination_mode.value,
                )
            )

        return EligibilityReviewProjection(
            subject_id=authority.subject_id,
            review_episode_id=authority.review_episode_id,
            rule_set_id=authority.rule_set_id,
            rule_set_revision=authority.rule_set_revision,
            evidence_snapshot_v2_id=authority.evidence_snapshot_v2_id,
            complete_processing_revision_id=authority.complete_processing_revision_id,
            clauses=tuple(output),
        )


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
        evidence_requirements=clause.evidence_requirements,
    )
