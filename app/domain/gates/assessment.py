from __future__ import annotations

from app.domain.contracts.enums import BlockingLevel, ComponentDecision, GapType
from app.domain.contracts.review import AssessmentCandidate, FinalAssessment


class AssessmentGateError(ValueError):
    pass


DEFINITIVE_DECISIONS = {
    ComponentDecision.INCLUSION_MET,
    ComponentDecision.INCLUSION_NOT_MET,
    ComponentDecision.EXCLUSION_NOT_TRIGGERED,
    ComponentDecision.EXCLUSION_TRIGGERED,
    ComponentDecision.NOT_APPLICABLE,
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


def _blocking_gaps(gaps: set[GapType]) -> set[GapType]:
    return gaps - {GapType.PROVENANCE_FOLLOWUP}


def derive_assessment_blocking_level(candidate: AssessmentCandidate) -> BlockingLevel:
    """Derive presentation blocking from the accepted state/gap matrix."""
    validate_assessment_candidate(candidate)
    gaps = set(candidate.gap_types)
    if not gaps:
        return BlockingLevel.NONE
    if gaps in (
        {GapType.PROVENANCE_FOLLOWUP},
        {GapType.FUTURE_STAGE_NOT_DUE},
    ):
        return BlockingLevel.ATTENTION
    return BlockingLevel.BLOCKING


def validate_assessment_candidate(candidate: AssessmentCandidate) -> None:
    gaps = set(candidate.gap_types)
    blocking_gaps = _blocking_gaps(gaps)
    decision = candidate.proposed_decision

    if decision in DEFINITIVE_DECISIONS and blocking_gaps:
        raise AssessmentGateError("明确判断不能携带阻断缺口")
    if decision == ComponentDecision.INDETERMINATE and not (blocking_gaps & INDETERMINATE_GAPS):
        raise AssessmentGateError("暂不能明确必须包含具体证据或资料缺口")
    if decision == ComponentDecision.PROFESSIONAL_JUDGMENT and GapType.PROFESSIONAL_JUDGMENT not in gaps:
        raise AssessmentGateError("需专业判断必须包含 professional_judgment")
    if decision == ComponentDecision.CONFLICT and not gaps.intersection(
        {GapType.SOURCE_CONFLICT, GapType.INTERPRETATION_CONFLICT}
    ):
        raise AssessmentGateError("存在冲突必须说明来源或解释冲突")
    if decision == ComponentDecision.NOT_DUE and GapType.FUTURE_STAGE_NOT_DUE not in gaps:
        raise AssessmentGateError("尚未到期必须包含 future_stage_not_due")


def publish_assessment(
    candidate: AssessmentCandidate,
    *,
    assessment_id: str,
    review_run_id: str,
    gate_result_id: str,
    action_ids: list[str] | None = None,
) -> FinalAssessment:
    validate_assessment_candidate(candidate)
    blocking_level = derive_assessment_blocking_level(candidate)
    return FinalAssessment(
        assessment_id=assessment_id,
        review_run_id=review_run_id,
        rule_component_id=candidate.rule_component_id,
        decision=candidate.proposed_decision,
        gap_types=candidate.gap_types,
        blocking_level=blocking_level,
        used_fact_ids=candidate.used_fact_ids,
        evidence_span_ids=candidate.evidence_span_ids,
        action_ids=action_ids or [],
        gate_result_id=gate_result_id,
    )
