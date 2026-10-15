import pytest

from app.domain.contracts.enums import ComponentDecision, GapType, RuleKind, TruthValue
from app.domain.expression import ComponentEvaluation, EvaluationResult
from app.domain.gates.assessment import derive_component_decision
from app.domain.policies import validate_decision_gap_matrix


def test_wire_preserves_gap_decision_identity():
    from app.services.eligibility_review_projection import _decision_for_wire

    assert _decision_for_wire(ComponentDecision.INDETERMINATE) == ComponentDecision.INDETERMINATE


@pytest.mark.parametrize("kind", [RuleKind.INCLUSION, RuleKind.EXCLUSION, RuleKind.REQUIRED_PROCEDURE])
@pytest.mark.parametrize("truth", [TruthValue.TRUE, TruthValue.FALSE])
@pytest.mark.parametrize("gap,expected", [
    (GapType.PROFESSIONAL_JUDGMENT, ComponentDecision.PROFESSIONAL_JUDGMENT),
    (GapType.SOURCE_CONFLICT, ComponentDecision.CONFLICT),
    (GapType.OBSERVATION_UNVERIFIED, ComponentDecision.INDETERMINATE),
])
def test_relevant_blocking_gap_prevents_definitive_decision(kind, truth, gap, expected):
    evaluation = ComponentEvaluation(
        trigger=EvaluationResult(truth=truth), predicate_evaluations={},
    )
    decision = derive_component_decision(rule_kind=kind, evaluation=evaluation, gaps={gap})
    assert decision == expected
    validate_decision_gap_matrix(decision, {gap})


def test_documented_unperformed_procedure_retains_not_met():
    evaluation = ComponentEvaluation(
        trigger=EvaluationResult(truth=TruthValue.FALSE), predicate_evaluations={},
    )
    gaps = {GapType.REQUIRED_PROCEDURE_NOT_DONE}
    decision = derive_component_decision(
        rule_kind=RuleKind.REQUIRED_PROCEDURE, evaluation=evaluation, gaps=gaps,
    )
    assert decision == ComponentDecision.REQUIREMENT_NOT_MET
    validate_decision_gap_matrix(decision, gaps)


def test_nonblocking_provenance_reminder_preserves_decision():
    evaluation = ComponentEvaluation(
        trigger=EvaluationResult(truth=TruthValue.TRUE), predicate_evaluations={},
    )
    gaps = {GapType.PROVENANCE_FOLLOWUP}
    decision = derive_component_decision(
        rule_kind=RuleKind.INCLUSION, evaluation=evaluation, gaps=gaps,
    )
    assert decision == ComponentDecision.INCLUSION_MET
    validate_decision_gap_matrix(decision, gaps)


@pytest.mark.parametrize("extra_gap,expected", [
    (GapType.SOURCE_CONFLICT, ComponentDecision.CONFLICT),
    (GapType.OBSERVATION_UNVERIFIED, ComponentDecision.INDETERMINATE),
    (GapType.PROFESSIONAL_JUDGMENT, ComponentDecision.PROFESSIONAL_JUDGMENT),
])
def test_unperformed_procedure_with_unresolved_evidence_is_not_definite(extra_gap, expected):
    gaps = {GapType.REQUIRED_PROCEDURE_NOT_DONE, extra_gap}
    evaluation = ComponentEvaluation(
        trigger=EvaluationResult(truth=TruthValue.FALSE), predicate_evaluations={},
    )
    decision = derive_component_decision(
        rule_kind=RuleKind.REQUIRED_PROCEDURE, evaluation=evaluation, gaps=gaps,
    )
    assert decision == expected
    validate_decision_gap_matrix(decision, gaps)


def test_future_only_requirement_remains_not_due_despite_current_trigger():
    gaps = {GapType.FUTURE_STAGE_NOT_DUE}
    evaluation = ComponentEvaluation(
        trigger=EvaluationResult(truth=TruthValue.TRUE), predicate_evaluations={},
    )
    decision = derive_component_decision(
        rule_kind=RuleKind.EXCLUSION, evaluation=evaluation, gaps=gaps,
    )
    assert decision == ComponentDecision.NOT_DUE
    validate_decision_gap_matrix(decision, gaps)
