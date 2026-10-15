"""Deterministic series numeric kernel over verified acquisition groups."""

from datetime import date
from fractions import Fraction

import pytest

from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import DatePrecision, FactPolarity, ProfileLane, SourceStrength
from app.domain.contracts.evidence import ClinicalFact
from app.domain.contracts.predicate_binding import FrozenFactRecord
from app.domain.series_numeric_result import (
    SeriesNumericResult,
    calculate_series_numeric_result,
)


def _fact(
    identifier: str,
    value: float,
    *,
    unit: str = "分",
    polarity=FactPolarity.AFFIRMED,
    conflict_group_id: str | None = None,
):
    return ClinicalFact(
        fact_id=identifier,
        project_id="p",
        subject_id="s",
        review_episode_id="e",
        evidence_snapshot_id="snap",
        fact_type="量表得分",
        value=value,
        unit=unit,
        polarity=polarity,
        certainty=1,
        effective_date=DateValue(value=date(2026, 9, 1), precision=DatePrecision.DAY),
        evidence_span_ids=[identifier],
        conflict_group_id=conflict_group_id,
    )


def test_positive_mean_sum_and_extrema_on_complete_series():
    groups = [[_fact("a", 2)], [_fact("b", 4)], [_fact("c", 6)]]
    mean = calculate_series_numeric_result(
        groups,
        operation="mean",
        declared_input_count=3,
        allowed_missing_count=0,
        source_range_complete=True,
    )
    total = calculate_series_numeric_result(
        groups,
        operation="sum",
        declared_input_count=3,
        allowed_missing_count=0,
        source_range_complete=True,
    )
    lowest = calculate_series_numeric_result(
        groups,
        operation="minimum",
        declared_input_count=3,
        allowed_missing_count=0,
        source_range_complete=True,
    )
    highest = calculate_series_numeric_result(
        groups,
        operation="maximum",
        declared_input_count=3,
        allowed_missing_count=0,
        source_range_complete=True,
    )
    assert mean.value == Fraction(4)
    assert total.value == Fraction(12)
    assert lowest.value == Fraction(2)
    assert highest.value == Fraction(6)
    assert mean.unit == total.unit == lowest.unit == highest.unit == "分"
    assert mean.reason_codes == ("series_source_qualification_unverified",)
    assert mean.replacement_authorized is False
    assert not isinstance(mean, ClinicalFact)
    assert "ClinicalFact" not in type(mean).__name__


def test_synonym_operations_and_equal_acquisition_copies_are_preserved():
    groups = [
        [_fact("a", 2), _fact("a-copy", 2)],
        [_fact("b", 4)],
        [_fact("c", 6)],
    ]
    via_mean = calculate_series_numeric_result(
        groups,
        operation="mean",
        declared_input_count=3,
        source_range_complete=True,
    )
    via_average = calculate_series_numeric_result(
        groups,
        operation="average",
        declared_input_count=3,
        source_range_complete=True,
    )
    via_min = calculate_series_numeric_result(
        groups,
        operation="min",
        declared_input_count=3,
        source_range_complete=True,
    )
    via_max = calculate_series_numeric_result(
        groups,
        operation="max",
        declared_input_count=3,
        source_range_complete=True,
    )
    assert via_mean.value == via_average.value == Fraction(4)
    assert via_mean.operation == via_average.operation == "mean"
    assert via_min.value == Fraction(2) and via_min.operation == "minimum"
    assert via_max.value == Fraction(6) and via_max.operation == "maximum"
    # Independent equal acquisitions remain separate inputs for the mean.
    equal_independents = calculate_series_numeric_result(
        [[_fact("x", 2)], [_fact("y", 2)], [_fact("z", 5)]],
        operation="mean",
        declared_input_count=3,
        source_range_complete=True,
    )
    assert equal_independents.value == Fraction(3)


def test_allowed_missing_within_budget_still_aggregates_present_inputs():
    result = calculate_series_numeric_result(
        [[_fact("a", 2)], [_fact("b", 6)]],
        operation="mean",
        declared_input_count=3,
        allowed_missing_count=1,
        missing_policy="exclude",
        source_range_complete=True,
    )
    assert result.value == Fraction(4)
    assert result.present_input_count == 2
    assert result.missing_count == 1
    assert result.reason_codes == ("series_source_qualification_unverified",)
    assert result.missing_policy == "exclude"

    without_policy = calculate_series_numeric_result(
        [[_fact("a", 2)], [_fact("b", 6)]],
        operation="mean",
        declared_input_count=3,
        allowed_missing_count=1,
        source_range_complete=True,
    )
    assert without_policy.value is None
    assert without_policy.reason_codes == ("series_missing_policy_unverified",)

    imputation = calculate_series_numeric_result(
        [[_fact("a", 2)], [_fact("b", 6)]],
        operation="mean",
        declared_input_count=3,
        allowed_missing_count=1,
        missing_policy="impute",
        source_range_complete=True,
    )
    assert imputation.value is None
    assert imputation.reason_codes == ("series_imputation_unsupported",)


def test_counterfactual_incomplete_range_or_excess_missing_stay_unresolved():
    incomplete = calculate_series_numeric_result(
        [[_fact("a", 2)], [_fact("b", 4)], [_fact("c", 6)]],
        operation="sum",
        declared_input_count=3,
        allowed_missing_count=0,
        source_range_complete=False,
    )
    assert incomplete.value is None
    assert incomplete.reason_codes == ("series_source_range_incomplete",)

    excess_missing = calculate_series_numeric_result(
        [[_fact("a", 2)]],
        operation="sum",
        declared_input_count=3,
        allowed_missing_count=1,
        source_range_complete=True,
    )
    assert excess_missing.value is None
    assert excess_missing.reason_codes == ("series_missing_exceeds_allowed",)

    exceeded = calculate_series_numeric_result(
        [[_fact("a", 1)], [_fact("b", 2)], [_fact("c", 3)], [_fact("d", 4)]],
        operation="sum",
        declared_input_count=3,
        source_range_complete=True,
    )
    assert exceeded.reason_codes == ("series_input_count_exceeded",)


def test_unverified_declared_count_cannot_be_replaced_by_supplied_record_count():
    result = calculate_series_numeric_result(
        [[_fact("a", 2)], [_fact("b", 4)]],
        operation="mean",
        declared_input_count=None,
        source_range_complete=True,
    )
    assert result.present_input_count == 2
    assert result.declared_input_count is None
    assert result.missing_count is None
    assert result.value is None
    assert result.reason_codes == ("series_declared_input_count_unverified",)
    assert result.as_material()["eligible_for_rule_evaluation"] is False


def test_fault_cases_reuse_acquisition_unit_conflict_and_do_not_emit_facts():
    overlap = calculate_series_numeric_result(
        [[_fact("same", 2)], [_fact("same", 2)], [_fact("other", 5)]],
        operation="mean",
        declared_input_count=3,
        source_range_complete=True,
    )
    assert overlap.value is None
    assert overlap.reason_codes == ("repeat_result_acquisition_overlap",)

    conflict = calculate_series_numeric_result(
        [[_fact("a", 2), _fact("a-copy", 3)]],
        operation="mean",
        declared_input_count=1,
        source_range_complete=True,
    )
    assert conflict.reason_codes == ("repeat_same_acquisition_value_conflict",)

    mixed_units = calculate_series_numeric_result(
        [[_fact("a", 2)], [_fact("b", 2, unit="mg")]],
        operation="sum",
        declared_input_count=2,
        source_range_complete=True,
    )
    assert mixed_units.reason_codes == ("repeat_result_unit_unverified",)

    disputed = calculate_series_numeric_result(
        [[_fact("a", 2, conflict_group_id="cg-1")]],
        operation="sum",
        declared_input_count=1,
        source_range_complete=True,
    )
    assert disputed.reason_codes == ("source_conflict",)

    empty = calculate_series_numeric_result(
        [],
        operation="mean",
        declared_input_count=2,
        allowed_missing_count=2,
        source_range_complete=True,
    )
    assert empty.value is None
    assert empty.reason_codes == ("series_result_missing",)
    assert isinstance(empty, SeriesNumericResult)
    material = empty.as_material()
    assert material["replacement_authorized"] is False
    assert material["eligible_for_rule_evaluation"] is False
    assert material["exact_value"] is None

    with pytest.raises(ValueError):
        calculate_series_numeric_result(
            [],
            operation="mean",
            declared_input_count=1,
            allowed_missing_count=2,
            source_range_complete=True,
        )


def test_complete_series_with_unknown_policy_is_only_an_arithmetic_diagnostic():
    result = calculate_series_numeric_result(
        [[_fact("a", 2)], [_fact("b", 4)]],
        operation="mean",
        declared_input_count=2,
        missing_policy="unresolved",
        source_range_complete=True,
    )
    assert result.value == Fraction(3)
    assert result.reason_codes == ("series_source_qualification_unverified",)
    assert result.as_material()["eligible_for_rule_evaluation"] is False


def test_formal_fact_shape_cannot_sneak_into_the_experimental_kernel():
    formal_fact = FrozenFactRecord(
        fact_id="new-fact",
        stable_identity="a" * 64,
        revision=1,
        fact_type="量表得分",
        profile_lane=ProfileLane.EVIDENCE_QUALITY,
        asserted_object="评分",
        polarity=FactPolarity.AFFIRMED,
        value=2,
        unit="分",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        locator_ids=["locator-1"],
    )
    with pytest.raises(ValueError, match="不能直接用于正式审核事实"):
        calculate_series_numeric_result(
            [[formal_fact]],
            operation="mean",
            declared_input_count=1,
            source_range_complete=True,
        )
