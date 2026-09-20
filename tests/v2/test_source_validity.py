from datetime import date

import pytest

from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import DatePrecision, TruthValue
from app.domain.contracts.facts import PartialDateRange
from app.domain.contracts.rules import TimeQuantity, TimeUnit
from app.domain.source_validity import source_validity


def _day(value):
    day = date.fromisoformat(value)
    return PartialDateRange(precision=DatePrecision.DAY, lower_bound=day, upper_bound=day)


@pytest.mark.parametrize("observed,expected", [
    ("2026-09-03", TruthValue.TRUE),
    ("2026-09-10", TruthValue.TRUE),
    ("2026-09-02", TruthValue.FALSE),
    ("2026-09-11", TruthValue.FALSE),
])
def test_source_validity_uses_closed_node_window(observed, expected):
    assert source_validity(
        _day(observed), TimeQuantity(value=7, unit=TimeUnit.DAY),
        DateValue(value=date(2026, 9, 10), precision=DatePrecision.DAY),
    ) == expected


def test_partial_date_must_fit_entire_window():
    observed = PartialDateRange(
        precision=DatePrecision.MONTH,
        lower_bound=date(2026, 8, 1), upper_bound=date(2026, 8, 31),
    )
    anchor = DateValue(value=date(2026, 9, 10), precision=DatePrecision.DAY)
    assert source_validity(observed, TimeQuantity(value=2, unit=TimeUnit.MONTH), anchor) == TruthValue.TRUE
    assert source_validity(observed, TimeQuantity(value=1, unit=TimeUnit.MONTH), anchor) == TruthValue.UNKNOWN


def test_months_are_not_thirty_days_and_future_evidence_is_not_current():
    anchor = DateValue(value=date(2024, 3, 31), precision=DatePrecision.DAY)
    window = TimeQuantity(value=1, unit=TimeUnit.MONTH)
    assert source_validity(_day("2024-02-29"), window, anchor) == TruthValue.TRUE
    assert source_validity(_day("2024-02-28"), window, anchor) == TruthValue.FALSE


@pytest.mark.parametrize("missing", ["observation", "anchor"])
def test_missing_date_is_not_filled_from_other_timestamps(missing):
    observed = None if missing == "observation" else _day("2026-09-05")
    anchor = None if missing == "anchor" else DateValue(value=date(2026, 9, 10), precision=DatePrecision.DAY)
    assert source_validity(observed, TimeQuantity(value=7, unit=TimeUnit.DAY), anchor) == TruthValue.UNKNOWN


def test_anchor_selection_preserves_stage_and_conflicting_dates():
    from app.domain.contracts.enums import AnchorType, ReviewStage
    from app.domain.source_validity import source_validity_anchor
    screen = DateValue(value=date(2026, 9, 1), precision=DatePrecision.DAY)
    baseline = DateValue(value=date(2026, 9, 10), precision=DatePrecision.DAY)
    anchors = {
        AnchorType.SCREENING_DATE: screen, AnchorType.BASELINE_DATE: baseline,
        AnchorType.REVIEW_NODE_DATE: baseline,
    }
    assert source_validity_anchor(due_stage=ReviewStage.SCREENING, current_stage=ReviewStage.BASELINE, anchors=anchors) == screen
    assert source_validity_anchor(due_stage=ReviewStage.BASELINE, current_stage=ReviewStage.BASELINE, anchors=anchors) == baseline
    del anchors[AnchorType.SCREENING_DATE]
    assert source_validity_anchor(due_stage=ReviewStage.SCREENING, current_stage=ReviewStage.BASELINE, anchors=anchors) is None
    anchors[AnchorType.REVIEW_NODE_DATE] = screen
    assert source_validity_anchor(due_stage=ReviewStage.BASELINE, current_stage=ReviewStage.BASELINE, anchors=anchors) is None
