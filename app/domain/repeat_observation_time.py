"""Repeat-window arithmetic over supplied, independently qualified dates.

This does not establish which observation is initial or authorize replacement.
"""
from decimal import Decimal

from app.domain.calendar_dates import date_bounds
from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import AnchorType, TruthValue
from app.domain.contracts.repeat_scheme import RepeatTimeLimit
from app.domain.contracts.rules import TimeConstraint, TimeQuantity
from app.domain.expression import EvaluationResult, evaluate_time_constraint


def _result(truth, *reasons):
    return EvaluationResult(truth=truth, reason_codes=list(reasons))


def evaluate_repeat_time_limit(
    limit: RepeatTimeLimit, *, observation_date: DateValue | None,
    reference_date: DateValue | None,
) -> EvaluationResult:
    """Use calendar bounds and conservative elapsed-time bounds separately.

    The caller resolves the declared reference from verified relationships or
    the frozen episode. No fallback from initial to preceding/node date occurs.
    """
    if observation_date is None or reference_date is None:
        return _result(TruthValue.UNKNOWN, "repeat_date_missing")
    observed = date_bounds(observation_date, allow_partial=True)
    reference = date_bounds(reference_date, allow_partial=True)
    if observed is None or reference is None:
        return _result(TruthValue.UNKNOWN, "repeat_date_missing")
    bounds = (limit.lower_bound, limit.upper_bound)
    calendar_fields = {}
    elapsed = []
    for name, duration, inclusive in zip(
        ("lower", "upper"), bounds, (limit.lower_inclusive, limit.upper_inclusive), strict=True,
    ):
        if duration is None:
            continue
        integral = duration.value == duration.value.to_integral_value()
        if duration.unit in {"month", "year", "day", "week"} and integral:
            if duration.value == 0:
                calendar_fields[f"{name}_bound_days"] = 0
            else:
                calendar_fields[f"{name}_bound"] = TimeQuantity(value=int(duration.value), unit=duration.unit)
            calendar_fields[f"{name}_bound_inclusive"] = inclusive
        else:
            minutes = duration.value * {"minute": 1, "hour": 60, "day": 1440,
                                        "week": 10080}[duration.unit]
            elapsed.append((name, minutes))
    # The anchor label here is not a date lookup: the caller supplies the exact
    # reference_date. Calendar arithmetic uses only that value and direction.
    calendar = evaluate_time_constraint(
        TimeConstraint(anchor_type=limit.episode_anchor or AnchorType.REVIEW_NODE_DATE,
                       direction=limit.direction, allow_partial_date=True, **calendar_fields),
        event_value=observation_date, anchor_value=reference_date,
    )
    if calendar.truth == TruthValue.FALSE or not elapsed:
        return calendar
    if limit.direction == "after":
        low, high = (observed[0] - reference[1]).days, (observed[1] - reference[0]).days
    else:
        low, high = (reference[0] - observed[1]).days, (reference[1] - observed[0]).days
    # Date-only endpoints span whole days, so elapsed bounds are open. Even two
    # same-day observations do not establish a within-day order.
    minimum, maximum = Decimal((low - 1) * 1440), Decimal((high + 1) * 1440)
    uncertain = calendar.truth != TruthValue.TRUE or minimum < 0
    for name, value in elapsed:
        if name == "lower":
            if maximum <= value:
                return _result(TruthValue.FALSE, "below_time_window")
            uncertain |= minimum < value
        else:
            if minimum >= value:
                return _result(TruthValue.FALSE, "above_time_window")
            uncertain |= maximum > value
    if uncertain:
        return _result(TruthValue.UNKNOWN, "repeat_time_precision_insufficient")
    return _result(TruthValue.TRUE)
