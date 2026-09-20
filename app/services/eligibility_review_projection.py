"""只读入排审核投影。

本模块把当前审核节点的活动资料、已发布 V2 事实和已发布规则确定性地装配成
工作台读取模型。它不是正式 ``ReviewRun``，不写库，不调用模型，也不把缺失资料
解释为阴性结论。
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.contracts.clause_pack import ClausePackClause
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
from app.domain.expression import (
    ComponentEvaluation,
    EvaluationContext,
)
from app.domain.gates.assessment import (
    RequirementGapState,
)
from app.projections.clause_pack import project_clause_pack
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


# 按临床安全优先级选取单值 gap_type。完整缺口集合仍由 evaluator/仓储确定，
# wire 只保留一个主缺口用于列表筛选和详情摘要。
_GAP_PRIORITY: tuple[GapType, ...] = (
    GapType.SOURCE_CONFLICT,
    GapType.INTERPRETATION_CONFLICT,
    GapType.PROFESSIONAL_JUDGMENT,
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
    source_document_version_id: str
    page_artifact_id: str
    excerpt: str | None


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


@dataclass(frozen=True)
class EligibilityUnassignedConflict:
    conflict_group_id: str
    member_kind: str
    member_ids: tuple[str, ...]


@dataclass(frozen=True)
class EligibilityReviewProjection:
    subject_id: str
    review_episode_id: str
    rule_set_id: str
    rule_set_revision: int
    evidence_snapshot_v2_id: str
    complete_processing_revision_id: str
    clauses: tuple[EligibilityClauseProjection, ...]
    unassigned_conflicts: tuple[EligibilityUnassignedConflict, ...] = ()

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
        for locator_id in fact.locator_ids:
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

    def project(
        self, session: Session, review_episode_id: str
    ) -> EligibilityReviewProjection:
        authority = authority_from_active_episode(session, review_episode_id)
        episode = EpisodeRepository(session).get(review_episode_id)
        rule_set = get_rule_set(session, authority.rule_set_id, authority.rule_set_revision)
        clause_pack = project_clause_pack(rule_set)

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

        predicate_fact_ids = _load_binding_predicate_fact_ids(session)
        # C chain binding data is available via _load_binding_predicate_fact_ids.
        # The expression evaluator needs predicate_fact_ids to produce definite
        # results. Without it, predicates with observation_policy return UNKNOWN.
        # WP05 will properly connect the qualified binding selections.
        output: list[EligibilityClauseProjection] = []
        for clause in clauses:
            component = clause_to_rule_component(clause)
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
            result = calculate_component_review(
                component=component,
                rule_kind=clause.kind,
                context=component_context,
                episode_stage=episode.stage,
                expectations=expectation_views,
                conflicts=phase3_conflicts,
                workflow_stage_id=episode.workflow_stage_id,
                requirement_workflow_stage_ids={
                    item.requirement_id: item.workflow_stage_id for item in templates
                } if episode.workflow_stage_id is not None else None,
                source_gaps=frozenset(judgment_gaps.values()),
                predicate_fact_ids=_filter_for_component(
                    predicate_fact_ids, component),
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
            unassigned_conflicts=tuple(
                EligibilityUnassignedConflict(
                    conflict_group_id=group.conflict_group_id,
                    member_kind=group.member_kind,
                    member_ids=tuple(group.event_ids or group.exposure_ids),
                )
                for group in unassigned_groups
            ),
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
        repeat_trigger_conditions=list(clause.repeat_trigger_conditions),
        evidence_requirements=clause.evidence_requirements,
    )


def _load_binding_predicate_fact_ids(session):
    """Load predicate fact selections from the latest completed binding job."""
    try:
        from app.workflow.jobstore import JobStore
        from app.domain.contracts.predicate_binding import PredicateBindingFrozenInput
        from app.llm.predicate_binding_candidates import PredicateCandidatePayload
        from app.evidence.artifacts import ArtifactStore
        from app.services.evidence_app_bootstrap import resolve_data_paths

        rows = session.execute(
            text("SELECT job_id FROM jobs "
                 "WHERE job_type = 'predicate_binding_candidates' "
                 "AND state = 'completed' ORDER BY created_at DESC LIMIT 1")
        ).fetchall()
        if not rows:
            return None
        binding_job_id = rows[0][0]
        job_row = session.execute(
            text("SELECT payload_json FROM jobs WHERE job_id = :jid"),
            {"jid": binding_job_id},
        ).fetchone()
        if job_row is None:
            return None
        binding_payload = json.loads(job_row[0])
        frozen_data = binding_payload.get("frozen_input")
        if not frozen_data:
            return None
        frozen = PredicateBindingFrozenInput.model_validate(frozen_data)

        art_store = ArtifactStore(resolve_data_paths())
        store = JobStore(session)
        lane_payloads = {}
        for lane in ("main-A", "main-B"):
            cp = store.get_last_checkpoint(binding_job_id, f"read:{lane}")
            if cp is None or cp[1].get("status") != "unverified":
                return None
            cand_sha = cp[1].get("candidate_sha256")
            if not cand_sha:
                return None
            raw = art_store.read_by_sha("raw_response", cand_sha)
            artifact = json.loads(raw)
            lane_payloads[lane] = PredicateCandidatePayload.model_validate(
                artifact.get("payload", {}))

        result = {}
        for component in frozen.components:
            for pred in component.binding_predicates:
                pid = pred.predicate_identity_sha256
                key = pred.predicate_id
                fact_sets = []
                for lane in ("main-A", "main-B"):
                    lp = lane_payloads.get(lane)
                    if lp is None:
                        continue
                    for r in lp.results:
                        if r.predicate_identity_sha256 == pid:
                            fact_sets.append({c.fact_id for c in r.candidates})
                if len(fact_sets) == 2:
                    result[key] = sorted(fact_sets[0] & fact_sets[1])
                else:
                    result[key] = []
        return result if result else None
    except Exception:
        return None


def _filter_for_component(global_mapping, component):
    """Filter global mapping to only this component's predicates, or None."""
    if global_mapping is None:
        return None
    from app.domain.expression import _iter_atomic_expressions
    expressions = [component.expression]
    if component.exception_expression is not None:
        expressions.append(component.exception_expression)
    expected = set()
    for expr in expressions:
        for atom in _iter_atomic_expressions(expr):
            expected.add(atom.predicate.predicate_id)
    if not expected:
        return None
    return {pid: global_mapping.get(pid, []) for pid in expected}
