from __future__ import annotations

from app.domain.contracts.enums import (
    BlockingLevel,
    ComponentDecision,
    ExpectationStatus,
    GapType,
)


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
