"""Temporal membership precedes comparison of observations."""

from datetime import date

import pytest

from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import AnchorType, DatePrecision, FactPolarity, TruthValue
from app.domain.contracts.rules import AtomicExpression, AtomicPredicate, TimeConstraint
from app.domain.expression import evaluate_expression
from tests.v2.test_contract_logic import clinical_fact, evaluation_context


def _fact(identity, value, observed_on, *, polarity=FactPolarity.AFFIRMED):
    return clinical_fact(
        fact_id=identity, fact_type="laboratory.measurement", value=value,
        unit="mmol/L" if value is not None else None, polarity=polarity,
        certainty=1, evidence_span_ids=["span-" + identity],
        effective_date=DateValue(value=observed_on, precision=DatePrecision.DAY) if observed_on else None,
    )


def _evaluate(facts):
    expression = AtomicExpression(
        predicate=AtomicPredicate(predicate_id="measurement-threshold", subject="laboratory",
                                  attribute="measurement", comparator="lt", value=5, unit="mmol/L"),
        time_constraint=TimeConstraint(anchor_type=AnchorType.SCREENING_DATE,
                                       direction="before", upper_bound_days=7),
    )
    return evaluate_expression(expression, evaluation_context(
        facts=facts, anchor_dates={AnchorType.SCREENING_DATE: DateValue(
            value=date(2026, 9, 10), precision=DatePrecision.DAY)},
    ))


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("old_value,polarity", [(9, FactPolarity.AFFIRMED), (None, FactPolarity.UNKNOWN)])
def test_outside_window_observation_does_not_conflict_with_current_result(reverse, old_value, polarity):
    facts = [_fact("old", old_value, date(2026, 7, 1), polarity=polarity),
             _fact("current", 3, date(2026, 9, 9))]
    result = _evaluate(list(reversed(facts)) if reverse else facts)
    assert result.truth == TruthValue.TRUE
    assert result.used_fact_ids == ["current"]
    assert result.evidence_span_ids == ["span-current"]


@pytest.mark.parametrize("reverse", [False, True])
def test_unknown_date_does_not_become_certain_by_list_order(reverse):
    facts = [_fact("current", 3, date(2026, 9, 9)), _fact("undated", 3, None)]
    result = _evaluate(list(reversed(facts)) if reverse else facts)
    assert result.truth == TruthValue.UNKNOWN
    assert "date_or_anchor_missing" in result.reason_codes


def test_distinct_values_inside_window_still_require_resolution():
    result = _evaluate([_fact("one", 3, date(2026, 9, 9)),
                        _fact("two", 9, date(2026, 9, 8))])
    assert result.truth == TruthValue.UNKNOWN


@pytest.mark.parametrize("values", [(3,), (3, 3), (3, 9)])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.xfail(strict=True, reason="T1 F1: distinguish observation validity from an actual temporal requirement before changing definitive decisions")
def test_only_outdated_observations_cannot_prove_current_criterion_false(values, reverse):
    facts = [_fact(str(i), value, date(2026, 7, i + 1)) for i, value in enumerate(values)]
    result = _evaluate(list(reversed(facts)) if reverse else facts)
    assert result.truth == TruthValue.UNKNOWN
    assert "fact_not_observed_in_window" in result.reason_codes
    assert result.used_fact_ids == [str(i) for i in range(len(values))]
    assert result.observed_value == (values[0] if len(set(values)) == 1 else None)
