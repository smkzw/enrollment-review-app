"""Calendar bounds for source-qualified total periods, not fact occurrence dates."""
from datetime import date, timedelta
from itertools import product

from app.domain.calendar_dates import date_bounds, shift_date
from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import DatePrecision
from app.domain.occurrence_evidence_bounds import bound_stated_total
from app.domain.publication import canonical_hash

CURRENT_NODE_POLICY = "unnamed-lookback/current-screening-baseline/v1"


def _source_date_bounds(value):
    precision = DatePrecision.DAY if value.day is not None else DatePrecision.MONTH if value.month is not None else DatePrecision.YEAR
    return date_bounds(DateValue(value=date(value.year, value.month or 1, value.day or 1), precision=precision), allow_partial=True)


def _anchor_bounds(episode, anchor_type):
    raw = episode.get("anchor_dates", {}).get(anchor_type)
    return date_bounds(DateValue.model_validate(raw), allow_partial=True) if raw is not None else None


def _endpoint_possibilities(values, inclusive, *, start):
    offsets = (0, 1) if inclusive is None else (int(not inclusive),)
    return tuple(sorted({value + timedelta(days=offset if start else -offset)
                         for value in values for offset in offsets}))


def required_frequency_period(window, episode):
    """Return every boundary possibility, retaining source vs application policy."""
    trace = {"reason_codes": []}
    def unresolved(reason):
        return (), (), {**trace, "reason_codes": [reason]}
    scope = window.scope
    if scope is None or scope.kind == "unresolved" or scope.quantifier == "unresolved":
        return unresolved("frequency_required_period_unresolved")
    if scope.quantifier != "single" or scope.kind not in {"anchored_lookback", "anchored_period", "unanchored_lookback"}:
        return unresolved("frequency_period_kind_unsupported")
    required_anchor = scope.anchor_type
    if scope.kind == "unanchored_lookback":
        required_anchor = {"screening": "screening_date", "baseline": "baseline_date"}.get(episode.get("stage"))
        if required_anchor is None:
            return unresolved("frequency_application_node_unresolved")
        trace["anchor_provenance"] = {"source": "application_policy", "policy_identity": CURRENT_NODE_POLICY,
                                      "stage": episode.get("stage"), "workflow_stage_id": episode.get("workflow_stage_id"),
                                      "anchor_type": required_anchor}
    else:
        trace["anchor_provenance"] = {"source": "protocol", "anchor_type": required_anchor}
    anchors = _anchor_bounds(episode, required_anchor)
    if anchors is None:
        return unresolved("frequency_anchor_missing")
    if scope.kind in {"anchored_lookback", "unanchored_lookback"}:
        required_starts = tuple(shift_date(value, window.duration, sign=-1) for value in anchors)
        required_ends = anchors
    else:
        required_starts = anchors
        required_ends = tuple(shift_date(value, window.duration) for value in anchors)
    required_starts = _endpoint_possibilities(required_starts, scope.start_inclusive, start=True)
    required_ends = _endpoint_possibilities(required_ends, scope.end_inclusive, start=False)
    trace["required_boundaries"] = {"start_inclusive": scope.start_inclusive, "end_inclusive": scope.end_inclusive}
    return required_starts, required_ends, trace


def _qualify_total_period(statement, window, episode, *, required_period=None):
    """Caller owns source and method qualification; every endpoint possibility is retained."""
    required_starts, required_ends, required_trace = (
        required_frequency_period(window, episode) if required_period is None else required_period
    )
    trace = {
        "version": "frequency-period-calculation/v2", "window_sha256": canonical_hash(window.model_dump(mode="json")),
        "episode_sha256": canonical_hash(episode), "statement_period": statement.period.model_dump(mode="json") if statement.period else None,
        "bounds": None, "replacement_authorized": False, **required_trace,
    }
    def unresolved(reason):
        return {**trace, "reason_codes": [reason]}
    if required_trace["reason_codes"]:
        return trace
    period = statement.period
    if statement.kind != "stated_total" or period is None or period.basis == "unresolved":
        return unresolved("frequency_total_period_unverified")
    if statement.count_relation is None or statement.count_relation == "unresolved":
        return unresolved("frequency_stated_count_relation_unverified")
    if period.basis == "explicit_dates":
        starts, ends = _source_date_bounds(period.start), _source_date_bounds(period.end)
    else:
        stated_anchor = _anchor_bounds(episode, period.anchor_type)
        if stated_anchor is None:
            return unresolved("frequency_statement_anchor_missing")
        shifted = tuple(shift_date(value, period.duration, sign=-1 if period.direction == "before" else 1)
                        for value in stated_anchor)
        starts, ends = (shifted, stated_anchor) if period.direction == "before" else (stated_anchor, shifted)
    starts = _endpoint_possibilities(starts, period.start_inclusive, start=True)
    ends = _endpoint_possibilities(ends, period.end_inclusive, start=False)
    trace["stated_boundaries"] = {"start_inclusive": period.start_inclusive, "end_inclusive": period.end_inclusive}
    bounds = []
    for start, end, required_start, required_end in product(starts, ends, required_starts, required_ends):
        if start > end or required_start > required_end:
            return unresolved("frequency_period_order_unresolved")
        result = bound_stated_total(statement.count, stated_start=start, stated_end=end,
                                    required_start=required_start, required_end=required_end,
                                    count_relation=statement.count_relation)
        if result is None:
            return unresolved("frequency_period_overlap_unresolved")
        bounds.append(result)
    # Union possibilities caused by precision; intersect only independent evidence constraints.
    upper = None if any(item.upper is None for item in bounds) else max(item.upper for item in bounds)
    trace["bounds"] = {"lower": min(item.lower for item in bounds), "upper": upper}
    trace["required_start_bounds"] = [value.isoformat() for value in required_starts]
    trace["required_end_bounds"] = [value.isoformat() for value in required_ends]
    trace["stated_start_bounds"] = [value.isoformat() for value in starts]
    trace["stated_end_bounds"] = [value.isoformat() for value in ends]
    return trace


def qualify_total_period(statement, window, episode, *, required_period=None):
    try:
        return _qualify_total_period(statement, window, episode, required_period=required_period)
    except (OverflowError, ValueError):
        return {
            "version": "frequency-period-calculation/v2", "bounds": None,
            "window_sha256": canonical_hash(window.model_dump(mode="json")),
            "episode_sha256": canonical_hash(episode),
            "statement_period": statement.period.model_dump(mode="json") if statement.period else None,
            "reason_codes": ["frequency_calendar_bounds_invalid"], "replacement_authorized": False,
        }
