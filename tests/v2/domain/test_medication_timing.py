from datetime import date

import pytest
from pydantic import ValidationError

from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import TruthValue as T
from app.domain.contracts.rules import MedicationRestriction
from app.domain.medication_timing import medication_window_violation


def restriction(meaning="prohibited_interval", **window):
    return MedicationRestriction(drug_text="药物甲", applicable_stages=["screening"],
        window={"anchor_type": "screening_date", "direction": "before", **window},
        window_interpretation=meaning, source_quotes=[{"source_span_id": "source", "excerpt": "合成时间要求"}])


def evaluate(item, day):
    return medication_window_violation(item, use_date=DateValue(value=day, precision="day"),
        anchor_dates={"screening_date": DateValue(value="2026-03-31", precision="day")})


@pytest.mark.parametrize("day,expected", [("2026-03-04", T.TRUE), ("2026-03-03", T.TRUE),
    ("2026-03-02", T.FALSE), ("2026-04-01", T.FALSE)])
def test_forbidden_interval_uses_calendar_and_direction(day, expected):
    assert evaluate(restriction(upper_bound={"value": 4, "unit": "week"}), day).truth == expected


@pytest.mark.parametrize("day,expected", [("2026-03-04", T.TRUE), ("2026-03-03", T.FALSE),
    ("2026-03-02", T.FALSE), ("2026-04-01", T.FALSE)])
def test_minimum_washout_inverts_qualification_not_date_direction(day, expected):
    assert evaluate(restriction("minimum_washout", lower_bound={"value": 4, "unit": "week"}), day).truth == expected


def test_month_is_calendar_not_thirty_days_and_open_boundary_is_preserved():
    assert evaluate(restriction(upper_bound={"value": 1, "unit": "month"}), "2026-02-28").truth == T.TRUE
    item = restriction(upper_bound={"value": 1, "unit": "month"}, upper_bound_inclusive=False)
    assert evaluate(item, "2026-02-28").truth == T.FALSE


def test_no_anchor_no_interpretation_and_partial_overlap_remain_unknown():
    item = restriction(None, upper_bound_days=28)
    assert evaluate(item, "2026-03-04").truth == T.UNKNOWN
    item = restriction(upper_bound_days=28, allow_partial_date=True)
    assert medication_window_violation(item, use_date=DateValue(value=date(2026, 3, 1), precision="month"),
        anchor_dates={"screening_date": DateValue(value="2026-03-31", precision="day")}).truth == T.UNKNOWN
    assert medication_window_violation(item, use_date=DateValue(value="2026-03-04", precision="day"),
        anchor_dates={}).truth == T.UNKNOWN


def test_pure_half_life_never_treats_absent_calendar_bound_as_open_forbidden_interval():
    item = restriction(half_life_multiplier=5)
    assert evaluate(item, "2025-01-01").truth == T.UNKNOWN
    assert evaluate(item, "2026-03-30").truth == T.UNKNOWN


def test_longer_window_missing_pk_can_confirm_inside_calendar_but_not_outside():
    item = restriction(upper_bound_days=28, half_life_multiplier=5,
        combined_window_selection="longer_of_calendar_and_half_life")
    assert evaluate(item, "2026-03-04").truth == T.TRUE
    assert evaluate(item, "2025-01-01").truth == T.UNKNOWN


@pytest.mark.parametrize("day,expected", [("2026-03-04", T.TRUE), ("2025-01-01", T.UNKNOWN)])
def test_minimum_longer_washout_uses_shared_calendar_and_pk_evaluator(day, expected):
    item = restriction("minimum_washout", lower_bound_days=28, half_life_multiplier=5,
        combined_window_selection="longer_of_calendar_and_half_life")
    result = evaluate(item, day)
    assert result.truth == expected
    if expected == T.UNKNOWN:
        assert "half_life_missing" in result.reason_codes


@pytest.mark.parametrize("meaning,window", [
    ("minimum_washout", {"upper_bound_days": 28}),
    ("minimum_washout", {"direction": "after", "lower_bound_days": 28}),
    ("prohibited_interval", {"lower_bound_days": 28}),
    ("prohibited_interval", {"lower_bound_days": 2, "half_life_multiplier": 5}),
])
def test_opposite_or_unsupported_meanings_cannot_be_saved_as_executable(meaning, window):
    with pytest.raises(ValidationError):
        restriction(meaning, **window)
