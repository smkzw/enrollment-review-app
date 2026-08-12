from __future__ import annotations

from app.domain.contracts.enums import ComponentDecision, GapType, RuleKind, TruthValue
from app.domain.contracts.review import AssessmentCandidate, FinalAssessment
from app.domain.expression import ComponentEvaluation
from app.domain.policies import derive_assessment_blocking_level, validate_decision_gap_matrix


class AssessmentGateError(ValueError):
    pass


def _decision_for_unknown(gaps: set[GapType]) -> ComponentDecision:
    if gaps.intersection({GapType.SOURCE_CONFLICT, GapType.INTERPRETATION_CONFLICT}):
        return ComponentDecision.CONFLICT
    if GapType.PROFESSIONAL_JUDGMENT in gaps:
        return ComponentDecision.PROFESSIONAL_JUDGMENT
    if gaps == {GapType.FUTURE_STAGE_NOT_DUE}:
        return ComponentDecision.NOT_DUE
    return ComponentDecision.INDETERMINATE


def derive_component_decision(
    *,
    rule_kind: RuleKind,
    evaluation: ComponentEvaluation,
    gaps: set[GapType],
) -> ComponentDecision:
    if evaluation.applicable == TruthValue.FALSE:
        return ComponentDecision.NOT_APPLICABLE
    if evaluation.applicable == TruthValue.UNKNOWN:
        return _decision_for_unknown(gaps)
    trigger = evaluation.trigger.truth
    if trigger == TruthValue.UNKNOWN:
        return _decision_for_unknown(gaps)
    if rule_kind == RuleKind.INCLUSION:
        return (
            ComponentDecision.INCLUSION_MET
            if trigger == TruthValue.TRUE
            else ComponentDecision.INCLUSION_NOT_MET
        )
    if rule_kind == RuleKind.REQUIRED_PROCEDURE:
        return (
            ComponentDecision.REQUIREMENT_MET
            if trigger == TruthValue.TRUE
            else ComponentDecision.REQUIREMENT_NOT_MET
        )
    if trigger == TruthValue.FALSE:
        return ComponentDecision.EXCLUSION_NOT_TRIGGERED
    if evaluation.exception is None or evaluation.exception.truth == TruthValue.FALSE:
        return ComponentDecision.EXCLUSION_TRIGGERED
    if evaluation.exception.truth == TruthValue.TRUE:
        return ComponentDecision.EXCLUSION_NOT_TRIGGERED
    return _decision_for_unknown(gaps)


def validate_assessment_candidate(candidate: AssessmentCandidate) -> None:
    try:
        validate_decision_gap_matrix(candidate.proposed_decision, set(candidate.gap_types))
    except ValueError as exc:
        raise AssessmentGateError(str(exc)) from exc


def publish_assessment(
    candidate: AssessmentCandidate,
    *,
    rule_kind: RuleKind,
    evaluation: ComponentEvaluation,
    assessment_id: str,
    review_run_id: str,
    gate_result_id: str,
    action_ids: list[str] | None = None,
) -> FinalAssessment:
    decision = derive_component_decision(
        rule_kind=rule_kind,
        evaluation=evaluation,
        gaps=set(candidate.gap_types),
    )
    if candidate.proposed_decision != decision:
        raise AssessmentGateError(
            f"Agent 候选状态 {candidate.proposed_decision.value} 与确定性结果 {decision.value} 不一致"
        )
    validate_assessment_candidate(candidate)
    blocking_level = derive_assessment_blocking_level(
        decision,
        set(candidate.gap_types),
    )
    return FinalAssessment(
        assessment_id=assessment_id,
        review_run_id=review_run_id,
        rule_component_id=candidate.rule_component_id,
        decision=decision,
        gap_types=candidate.gap_types,
        blocking_level=blocking_level,
        used_fact_ids=candidate.used_fact_ids,
        evidence_span_ids=candidate.evidence_span_ids,
        action_ids=action_ids or [],
        gate_result_id=gate_result_id,
    )
