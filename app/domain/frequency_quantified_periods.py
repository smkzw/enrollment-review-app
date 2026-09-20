"""Enumerate source-declared finite periods without inferring a history horizon."""
from datetime import timedelta

from app.domain.calendar_dates import shift_date
from app.domain.contracts.rules import TimeQuantity
from app.domain.frequency_period_qualification import _anchor_bounds, _source_date_bounds
from app.domain.publication import canonical_hash


def _exact(bounds):
    return bounds[0] if bounds is not None and bounds[0] == bounds[1] else None


def _relative_bounds(constraint, episode):
    anchor = _exact(_anchor_bounds(episode, constraint.anchor_type))
    if anchor is None:
        return None
    if constraint.lower_bound_inclusive is None or constraint.upper_bound_inclusive is None:
        return None
    def endpoint(quantity, sign, default):
        if quantity is not None:
            return shift_date(anchor, quantity, sign=sign)
        return default
    sign = -1 if constraint.direction == "before" else 1
    near = endpoint(constraint.lower_bound, sign, anchor)
    far = endpoint(constraint.upper_bound, sign, None)
    if far is None:
        return None
    near += timedelta(days=sign * int(not constraint.lower_bound_inclusive))
    far -= timedelta(days=sign * int(not constraint.upper_bound_inclusive))
    return (far, near) if sign == -1 else (near, far)


def enumerate_frequency_periods(window, episode, *, maximum_periods=10000):
    """A resource-limited prefix is never marked as a complete quantifier domain."""
    trace = {"version": "frequency-quantified-periods/v1", "periods": [], "domain_complete": False,
             "excluded_partial_periods": [],
             "window_sha256": canonical_hash(window.model_dump(mode="json")),
             "episode_sha256": canonical_hash(episode), "reason_codes": []}
    def unresolved(reason):
        return {**trace, "reason_codes": [reason]}
    if type(maximum_periods) is not int or maximum_periods <= 0:
        raise ValueError("计数期间处理额度必须为正整数")
    scope, horizon = window.scope, window.horizon
    if scope is None or scope.quantifier not in {"any", "every"}:
        return unresolved("frequency_quantifier_unresolved")
    if horizon is None or horizon.basis in {"unresolved", "unbounded"}:
        return unresolved("frequency_horizon_unresolved")
    if scope.boundary_periods not in {"full_only", "include_partial"}:
        return unresolved("frequency_boundary_periods_unresolved")
    if scope.start_inclusive is None or scope.end_inclusive is None:
        return unresolved("frequency_period_endpoints_unresolved")
    if scope.kind in {"any_consecutive", "anchored_period"}:
        if scope.duration_basis not in {"calendar_span", "boundary_offset"}:
            return unresolved("frequency_duration_basis_unresolved")
        if scope.duration_basis == "calendar_span" and not (scope.start_inclusive and scope.end_inclusive):
            return unresolved("frequency_calendar_span_endpoints_unresolved")
    try:
        if horizon.basis == "relative_window":
            bounds = _relative_bounds(horizon.relative_window, episode)
            if bounds is None:
                return unresolved("frequency_horizon_dates_unresolved")
            start, end = bounds
        else:
            if horizon.basis == "explicit_dates":
                start, end = _exact(_source_date_bounds(horizon.start)), _exact(_source_date_bounds(horizon.end))
            else:
                start, end = _exact(_anchor_bounds(episode, horizon.start_anchor)), _exact(_anchor_bounds(episode, horizon.end_anchor))
            if start is None or end is None or horizon.start_inclusive is None or horizon.end_inclusive is None:
                return unresolved("frequency_horizon_dates_unresolved")
            start += timedelta(days=int(not horizon.start_inclusive))
            end -= timedelta(days=int(not horizon.end_inclusive))
        if start > end:
            return unresolved("frequency_period_order_unresolved")
        trace["horizon_bounds"] = [start.isoformat(), end.isoformat()]
        trace["horizon_source"] = horizon.model_dump(mode="json")
        if scope.kind == "calendar_period":
            # Multi-unit calendar cycles require an explicitly declared epoch.
            if window.duration.value != 1:
                return unresolved("frequency_period_alignment_unresolved")
            if window.duration.unit == "month":
                current = start.replace(day=1)
            elif window.duration.unit == "year":
                current = start.replace(month=1, day=1)
            elif window.duration.unit == "week" and scope.calendar_week_start is not None:
                weekday = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday").index(scope.calendar_week_start)
                current = start - timedelta(days=(start.weekday() - weekday) % 7)
            elif window.duration.unit == "day":
                current = start
            else:
                return unresolved("frequency_period_alignment_unresolved")
        elif scope.kind == "any_consecutive":
            if scope.boundary_periods != "full_only":
                return unresolved("frequency_sliding_partial_period_unresolved")
            current = start
        elif scope.kind == "anchored_period":
            current = _exact(_anchor_bounds(episode, scope.anchor_type))
            if current is None:
                return unresolved("frequency_anchor_missing")
            if current > start:
                return unresolved("frequency_period_alignment_unresolved")
        else:
            return unresolved("frequency_period_kind_unsupported")
        examined, epoch = 0, current
        while current <= end:
            if examined >= maximum_periods:
                return unresolved("frequency_period_processing_limit")
            examined += 1
            following = (shift_date(epoch, TimeQuantity(value=window.duration.value * examined, unit=window.duration.unit))
                         if scope.kind == "anchored_period" else shift_date(current, window.duration))
            # Calendar periods end the day before the next period. Anchored
            # and sliding durations retain their declared endpoint semantics.
            raw_end = (following - timedelta(days=1)
                       if scope.kind == "calendar_period" or scope.duration_basis == "calendar_span" else following)
            period_start = current + timedelta(days=int(not scope.start_inclusive))
            period_end = raw_end - timedelta(days=int(not scope.end_inclusive))
            if period_start > period_end:
                return unresolved("frequency_period_order_unresolved")
            overlap = period_end >= start and period_start <= end
            full = period_start >= start and period_end <= end
            if overlap and (full or scope.boundary_periods == "include_partial"):
                left, right = max(start, period_start), min(end, period_end)
                trace["periods"].append({"start": left.isoformat(), "end": right.isoformat(),
                                         "partial": not full})
            elif overlap:
                trace["excluded_partial_periods"].append({"start": period_start.isoformat(),
                                                           "end": period_end.isoformat()})
            current = current + timedelta(days=1) if scope.kind == "any_consecutive" else following
        trace["domain_complete"] = True
        if not trace["periods"]:
            trace["reason_codes"] = ["frequency_no_eligible_period"]
        return trace
    except (OverflowError, ValueError):
        return unresolved("frequency_calendar_bounds_invalid")
