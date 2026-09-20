"""A category match is not proof of an arbitrary clinical proposition."""

import pytest

from app.domain.contracts.enums import FactPolarity, TruthValue
from app.domain.contracts.rules import AtomicExpression, AtomicPredicate
from app.domain.expression import evaluate_expression, evaluate_bound_component_experiment
from app.domain.publication import canonical_hash
from app.domain.contracts.rules import LogicalExpression
from tests.v2.test_contract_logic import clinical_fact, evaluation_context, gate_component


def _expression(attribute):
    return AtomicExpression(predicate=AtomicPredicate(
        predicate_id=f"predicate-{attribute}", subject="history",
        attribute=attribute, comparator="exists",
    ))


def _fact(fact_type):
    return clinical_fact(
        fact_id="record-1", fact_type=fact_type, value="unrelated observation",
        polarity=FactPolarity.AFFIRMED, certainty=1,
        evidence_span_ids=["source-1"],
    )


@pytest.mark.parametrize("attribute", ["condition_present", "exception_documented"])
@pytest.mark.xfail(strict=True, reason="R01: category aliases lack verified predicate-specific semantic binding")
def test_category_alias_cannot_prove_trigger_or_exception(attribute):
    result = evaluate_expression(_expression(attribute), evaluation_context(
        facts=[_fact("clinical_history")],
        predicate_fact_type_aliases={f"history.{attribute}": ["clinical_history"]},
    ))
    assert result.truth == TruthValue.UNKNOWN


def test_unrelated_category_without_alias_is_unknown():
    result = evaluate_expression(_expression("condition_present"), evaluation_context(
        facts=[_fact("clinical_history")],
    ))
    assert result.truth == TruthValue.UNKNOWN


def test_existing_exact_typed_contract_still_supports_exists():
    result = evaluate_expression(_expression("condition_present"), evaluation_context(
        facts=[_fact("history.condition_present")],
    ))
    assert result.truth == TruthValue.TRUE
    assert result.used_fact_ids == ["record-1"]


def _selected(component, context, selections, **hashes):
    return evaluate_bound_component_experiment(component, context,
        component_sha256=hashes.get("component_sha256", canonical_hash(component.model_dump(mode="json"))),
        context_sha256=hashes.get("context_sha256", canonical_hash(context.model_dump(mode="json"))),
        predicate_fact_ids=selections)


@pytest.mark.parametrize("exception_present", [False, True])
def test_isolated_selection_keeps_real_trigger_and_separate_exception(exception_present):
    component = gate_component(with_exception=True)
    context = evaluation_context(facts=[clinical_fact(
        fact_id="true-record", fact_type="renamed-category", value=True,
        polarity=FactPolarity.AFFIRMED, certainty=1, evidence_span_ids=["original"],
    ), _fact("clinical_history")], predicate_fact_type_aliases={
        "history.condition_present": ["clinical_history"],
        "exception.documented": ["clinical_history"],
    })
    result = _selected(component, context, {
        component.expression.predicate.predicate_id: ["true-record"],
        component.exception_expression.predicate.predicate_id: ["true-record"] if exception_present else [],
    })
    assert result.trigger.truth == TruthValue.TRUE
    assert result.exception.truth == (TruthValue.TRUE if exception_present else TruthValue.UNKNOWN)
    assert "record-1" not in result.trigger.used_fact_ids


def test_isolated_selection_does_not_fallback_for_explicit_empty_selection():
    component = gate_component().model_copy(update={"expression": _expression("condition_present")})
    context = evaluation_context(facts=[_fact("history.condition_present")])
    assert _selected(component, context, {"predicate-condition_present": []}).trigger.truth == TruthValue.UNKNOWN


@pytest.mark.parametrize("selection", [{}, {"unknown": []}, {"predicate-history-condition_present-eq": ["missing"]},
                                      {"predicate-history-condition_present-eq": ["record-1", "record-1"]}])
def test_isolated_selection_rejects_missing_extra_or_foreign_references(selection):
    with pytest.raises(ValueError):
        _selected(gate_component(), evaluation_context(facts=[_fact("anything")]), selection)


@pytest.mark.parametrize("field", ["component_sha256", "context_sha256"])
def test_isolated_selection_rejects_changed_scope(field):
    component = gate_component()
    with pytest.raises(ValueError, match="已变化"):
        _selected(component, evaluation_context(), {component.expression.predicate.predicate_id: []}, **{field: "0" * 64})


def test_isolated_selection_keeps_one_fact_for_two_bounds_and_detects_conflict():
    lower = AtomicExpression(predicate=AtomicPredicate(predicate_id="lower", subject="measurement",
        attribute="amount", comparator="gte", value=10, unit="u"))
    upper = AtomicExpression(predicate=AtomicPredicate(predicate_id="upper", subject="measurement",
        attribute="amount", comparator="lte", value=30, unit="u"))
    component = gate_component().model_copy(update={"expression": LogicalExpression(operator="all", children=[lower, upper])})
    def fact(identity, value):
        return clinical_fact(fact_id=identity, fact_type="arbitrary", value=value, unit="u",
                             polarity=FactPolarity.AFFIRMED, certainty=1, evidence_span_ids=[identity])
    context = evaluation_context(facts=[fact("a", 20), fact("b", 21)])
    assert _selected(component, context, {"lower": ["a"], "upper": ["a"]}).trigger.truth == TruthValue.TRUE
    conflict = _selected(component, context, {"lower": ["a", "b"], "upper": ["a", "b"]})
    assert conflict.trigger.truth == TruthValue.UNKNOWN
    assert "source_conflict" in conflict.trigger.reason_codes
