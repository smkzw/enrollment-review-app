from __future__ import annotations

from dataclasses import dataclass

from app.domain.contracts.enums import (
    ActionTarget,
    BlockingLevel,
    ComponentDecision,
    ExpectationStatus,
    GapType,
    ReviewStage,
)
from app.domain.contracts.evidence import EvidenceExpectation
from app.domain.contracts.rules import RuleComponent


DEFINITIVE_DECISIONS = {
    ComponentDecision.INCLUSION_MET,
    ComponentDecision.INCLUSION_NOT_MET,
    ComponentDecision.EXCLUSION_NOT_TRIGGERED,
    ComponentDecision.EXCLUSION_TRIGGERED,
    ComponentDecision.NOT_APPLICABLE,
    ComponentDecision.REQUIREMENT_MET,
}

INDETERMINATE_GAPS = {
    GapType.RECORD_INCOMPLETE,
    GapType.DESCRIPTION_INSUFFICIENT,
    GapType.HISTORICAL_SOURCE_UNAVAILABLE,
    GapType.REFERENCED_FILE_MISSING,
    GapType.REQUIRED_PROCEDURE_NOT_DONE,
    GapType.RESULT_FIELDS_MISSING,
    GapType.DATE_OR_ANCHOR_MISSING,
    GapType.OCR_OR_PARSE_RISK,
}

# 明确障碍判断（I7 修复）：exclusion_triggered / inclusion_not_met /
# requirement_not_met 属于决定性障碍结论，即使没有任何缺口也绝不派生为
# blocking_level=none；derive_assessment_blocking_level 与
# FinalAssessment.validate_gate_owned_state 共同构成确定性拒绝不变量。
BARRIER_DECISIONS = {
    ComponentDecision.EXCLUSION_TRIGGERED,
    ComponentDecision.INCLUSION_NOT_MET,
    ComponentDecision.REQUIREMENT_NOT_MET,
}


STAGE_RANK = {
    ReviewStage.PRE_SCREENING: 0,
    ReviewStage.SCREENING: 1,
    ReviewStage.RUN_IN: 2,
    ReviewStage.BASELINE: 3,
}


@dataclass(frozen=True)
class ActionDirective:
    target_party: ActionTarget
    requested_action: str
    acceptable_evidence: str
    due_stage: ReviewStage
    recompute_scope: tuple[str, ...]
    trigger_evidence_span_id: str | None


ACTION_CONTENT = {
    GapType.RECORD_INCOMPLETE: (
        ActionTarget.INVESTIGATOR,
        "补充当前审核节点未记录的关键信息，并注明信息来源。",
        "可定位、具日期且能够回答本条要求的完整病历记录。",
    ),
    GapType.DESCRIPTION_INSUFFICIENT: (
        ActionTarget.INVESTIGATOR,
        "补充足以判断本条要求的病历描述。",
        "具名、具日期并直接对应本条要求的病历记录。",
    ),
    GapType.HISTORICAL_SOURCE_UNAVAILABLE: (
        ActionTarget.CRA,
        "核实既往资料能否取得；无法取得时记录核实范围和结果。",
        "原始既往资料，或具名、具日期的无法取得说明及核实记录。",
    ),
    GapType.REFERENCED_FILE_MISSING: (
        ActionTarget.CRC,
        "补充病历或现有资料中已经明确引用的原始文件。",
        "被引用文件及其日期、版本和来源。",
    ),
    GapType.REQUIRED_PROCEDURE_NOT_DONE: (
        ActionTarget.INVESTIGATOR,
        "完成当前审核节点要求的检查、检验或评分。",
        "执行记录及能够支持本条判断的完整结果。",
    ),
    GapType.RESULT_FIELDS_MISSING: (
        ActionTarget.CRC,
        "补充本条判断所需的完整结果字段。",
        "同一份报告中的结果、单位、参考范围及检查日期。",
    ),
    GapType.DATE_OR_ANCHOR_MISSING: (
        ActionTarget.CRC,
        "补充用于计算本条时间窗的事件日期或审核节点日期。",
        "可定位且日期精度足以完成时间窗计算的记录。",
    ),
    GapType.PROFESSIONAL_JUDGMENT: (
        ActionTarget.INVESTIGATOR,
        "研究者针对本条要求作出并记录明确的临床判断。",
        "具名、具日期并直接关联本条要求的研究者判断。",
    ),
    GapType.SOURCE_CONFLICT: (
        ActionTarget.INVESTIGATOR,
        "核实相互冲突的资料，并记录针对本条要求的结论。",
        "具名、具日期且能够回到冲突原始来源的核实记录。",
    ),
    GapType.OCR_OR_PARSE_RISK: (
        ActionTarget.CRC,
        "核对识别不清或结构不完整的原始资料，并补充清晰版本。",
        "清晰原件或经原始资料逐项核对的更正记录。",
    ),
    GapType.INTERPRETATION_CONFLICT: (
        ActionTarget.SPONSOR_MEDICAL_OR_PROJECT,
        "明确本条方案要求的适用口径，并记录解释依据。",
        "与现行方案及修订案一致、具日期且可追溯的医学解释。",
    ),
    GapType.FUTURE_STAGE_NOT_DUE: (
        ActionTarget.INVESTIGATOR,
        "在本条要求到期的后续审核节点完成评估。",
        "对应审核节点的日期锚点及完整评估记录。",
    ),
    GapType.PROVENANCE_FOLLOWUP: (
        ActionTarget.CRA,
        "核对当前病历转述所依据的原始来源。",
        "原始来源，或具名、具日期的溯源核对记录。",
    ),
}


def derive_action_directive(
    *,
    gap_type: GapType,
    component: RuleComponent,
    expectations: list[EvidenceExpectation],
    episode_stage: ReviewStage,
    assessment_evidence_span_ids: list[str],
) -> ActionDirective:
    """Derive user-facing follow-up content from registered clinical contracts."""

    requirement_by_id = {
        item.requirement_id: item for item in component.evidence_requirements
    }
    relevant_expectations = [
        item
        for item in expectations
        if item.requirement_id in requirement_by_id and item.gap_type == gap_type
    ]
    matching_due_stages = [
        requirement_by_id[item.requirement_id].due_stage
        for item in relevant_expectations
    ]
    if gap_type == GapType.FUTURE_STAGE_NOT_DUE:
        future_stages = [
            item.due_stage
            for item in component.evidence_requirements
            if STAGE_RANK[item.due_stage] > STAGE_RANK[episode_stage]
        ]
        if not future_stages:
            raise ValueError("后续节点复核待办必须对应尚未到期的证据要求")
        due_stage = min(future_stages, key=STAGE_RANK.__getitem__)
    elif matching_due_stages:
        due_stage = max(
            [episode_stage, *matching_due_stages], key=STAGE_RANK.__getitem__
        )
    else:
        due_stage = episode_stage

    target_party, requested_action, acceptable_evidence = ACTION_CONTENT[gap_type]
    trigger_candidates = sorted(
        {
            *assessment_evidence_span_ids,
            *(
                span_id
                for expectation in relevant_expectations
                for span_id in expectation.evidence_span_ids
            ),
        }
    )
    return ActionDirective(
        target_party=target_party,
        requested_action=requested_action,
        acceptable_evidence=acceptable_evidence,
        due_stage=due_stage,
        recompute_scope=(component.rule_component_id,),
        trigger_evidence_span_id=(trigger_candidates[0] if trigger_candidates else None),
    )


def validate_decision_gap_matrix(
    decision: ComponentDecision,
    gaps: set[GapType],
) -> None:
    blocking_gaps = gaps - {GapType.PROVENANCE_FOLLOWUP}
    if decision in DEFINITIVE_DECISIONS and blocking_gaps:
        raise ValueError("明确判断不能携带阻断缺口")
    if decision == ComponentDecision.INDETERMINATE and not (blocking_gaps & INDETERMINATE_GAPS):
        raise ValueError("暂不能明确必须包含具体证据或资料缺口")
    if decision == ComponentDecision.PROFESSIONAL_JUDGMENT and GapType.PROFESSIONAL_JUDGMENT not in gaps:
        raise ValueError("需专业判断必须包含 professional_judgment")
    if decision == ComponentDecision.CONFLICT and not gaps.intersection(
        {GapType.SOURCE_CONFLICT, GapType.INTERPRETATION_CONFLICT}
    ):
        raise ValueError("存在冲突必须说明来源或解释冲突")
    if decision == ComponentDecision.NOT_DUE and gaps != {GapType.FUTURE_STAGE_NOT_DUE}:
        raise ValueError("尚未到期必须且只能包含 future_stage_not_due")
    if decision == ComponentDecision.REQUIREMENT_NOT_MET and not (
        gaps
        & {
            GapType.REQUIRED_PROCEDURE_NOT_DONE,
            GapType.RESULT_FIELDS_MISSING,
            GapType.RECORD_INCOMPLETE,
        }
    ):
        raise ValueError("必做要求未完成必须包含对应的当前缺口")


def derive_assessment_blocking_level(
    decision: ComponentDecision,
    gaps: set[GapType],
) -> BlockingLevel:
    validate_decision_gap_matrix(decision, gaps)
    if decision in BARRIER_DECISIONS and not gaps:
        # 明确障碍结论：无缺口也不得显示“不阻断”（I7 修复）
        return BlockingLevel.BLOCKING
    if not gaps:
        return BlockingLevel.NONE
    if gaps in (
        {GapType.PROVENANCE_FOLLOWUP},
        {GapType.FUTURE_STAGE_NOT_DUE},
    ):
        return BlockingLevel.ATTENTION
    return BlockingLevel.BLOCKING


def derive_action_blocking_level(gap_type: GapType) -> BlockingLevel:
    if gap_type == GapType.PROVENANCE_FOLLOWUP:
        return BlockingLevel.NONE
    if gap_type == GapType.FUTURE_STAGE_NOT_DUE:
        return BlockingLevel.ATTENTION
    return BlockingLevel.BLOCKING


def derive_expectation_blocking_level(
    status: ExpectationStatus,
    gap_type: GapType | None,
) -> BlockingLevel:
    if status == ExpectationStatus.OBSERVED:
        return BlockingLevel.NONE
    if status == ExpectationStatus.NOT_DUE:
        return BlockingLevel.ATTENTION
    if status == ExpectationStatus.OBSERVED_WEAK and gap_type == GapType.PROVENANCE_FOLLOWUP:
        return BlockingLevel.ATTENTION
    return BlockingLevel.BLOCKING
