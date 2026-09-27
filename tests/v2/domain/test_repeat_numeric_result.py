"""Shared exact arithmetic for verified acquisition groups."""

from datetime import date
from fractions import Fraction

from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import DatePrecision, FactPolarity
from app.domain.contracts.evidence import ClinicalFact
from app.domain.repeat_numeric_result import aggregate_numeric_acquisitions


def _fact(identifier: str, value: float, *, unit: str = "分", polarity=FactPolarity.AFFIRMED):
    return ClinicalFact(
        fact_id=identifier, project_id="p", subject_id="s", review_episode_id="e",
        evidence_snapshot_id="snap", fact_type="量表得分", value=value, unit=unit,
        polarity=polarity, certainty=1, effective_date=DateValue(
            value=date(2026, 9, 1), precision=DatePrecision.DAY,
        ), evidence_span_ids=[identifier],
    )


def test_independent_equal_acquisitions_are_not_deduplicated():
    value, unit, reasons = aggregate_numeric_acquisitions(
        [[_fact("a", 2), _fact("a-copy", 2)], [_fact("b", 2)], [_fact("c", 5)]],
        operation="mean", unit_required=True,
    )
    assert (value, unit, reasons) == (Fraction(3), "分", ())


def test_one_fact_cannot_be_counted_as_two_acquisitions():
    first = _fact("same-source", 2)
    assert aggregate_numeric_acquisitions(
        [[first], [first], [_fact("independent-source", 5)]],
        operation="mean", unit_required=True,
    ) == (None, None, ("repeat_result_acquisition_overlap",))


def test_conflicting_same_acquisition_and_mixed_units_stay_unresolved():
    assert aggregate_numeric_acquisitions(
        [[_fact("a", 2), _fact("a-copy", 3)]], operation="mean", unit_required=True,
    )[2] == ("repeat_same_acquisition_value_conflict",)
    assert aggregate_numeric_acquisitions(
        [[_fact("a", 2)], [_fact("b", 2, unit="mg")]], operation="mean", unit_required=True,
    )[2] == ("repeat_result_unit_unverified",)


def test_unsupported_operation_and_empty_scope_do_not_produce_value():
    assert aggregate_numeric_acquisitions([], operation="mean", unit_required=True) == (
        None, None, ("repeat_result_missing",),
    )
    assert aggregate_numeric_acquisitions(
        [[_fact("a", 2)]], operation="median", unit_required=True,
    )[2] == ("repeat_result_combination_unverified",)
