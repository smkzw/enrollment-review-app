"""Count only explicitly distinct occurrences with source-qualified event dates."""
from app.domain.contracts.frequency_period import FrequencySourceDate
from app.domain.frequency_period_qualification import _source_date_bounds, required_frequency_period
from app.domain.occurrence_evidence_bounds import bound_distinct_occurrences
from app.domain.publication import canonical_hash


def qualify_individual_occurrences(statements, relationships, window, episode, *, required_period=None):
    trace = {
        "version": "frequency-individual-calculation/v1", "bounds": None,
        "window_sha256": canonical_hash(window.model_dump(mode="json")),
        "episode_sha256": canonical_hash(episode), "groups": [], "reason_codes": [],
        "enumeration_complete": False,
    }
    rows = {key: value for key, value in statements.items() if value["kind"] == "individual_occurrence"}
    if not rows:
        return {**trace, "reason_codes": ["frequency_individual_not_available"]}
    if any(value["count_unit"] != "occurrences" for value in rows.values()):
        return {**trace, "reason_codes": ["frequency_individual_days_unresolved"]}
    same = [(left, right) for relation, left, right in relationships if relation == "same_occurrence"]
    distinct = [(left, right) for relation, left, right in relationships if relation == "distinct_occurrence"]
    graph = bound_distinct_occurrences(list(rows), same_pairs=same, distinct_pairs=distinct, enumeration_complete=False)
    if graph.bounds is None:
        return {**trace, "reason_codes": list(graph.reason_codes)}
    try:
        starts, ends, required = required_frequency_period(window, episode) if required_period is None else required_period
        trace.update(required)
        if required["reason_codes"]:
            return trace
        if max(starts) > min(ends):
            return {**trace, "reason_codes": ["frequency_period_order_unresolved"]}
        owners, definite = {}, []
        for group in graph.groups:
            group_id = group[0]
            owners.update({key: group_id for key in group})
            dates = [_source_date_bounds(FrequencySourceDate.model_validate(rows[key]["occurrence_date"]))
                     for key in group if rows[key].get("occurrence_date") is not None]
            lower = max(value[0] for value in dates) if dates else None
            upper = min(value[1] for value in dates) if dates else None
            if dates and lower > upper:
                return {**trace, "reason_codes": ["frequency_same_occurrence_date_conflict"]}
            membership = "unresolved"
            if dates and lower >= max(starts) and upper <= min(ends):
                membership = "inside"
                definite.append(group_id)
            elif dates and (upper < min(starts) or lower > max(ends)):
                membership = "outside"
            trace["groups"].append({
                "group_id": group_id, "statement_sha256s": list(group), "membership": membership,
                "date_bounds": [lower.isoformat(), upper.isoformat()] if dates else None,
            })
        definite_set = set(definite)
        edges = sorted({tuple(sorted((owners[left], owners[right]))) for left, right in distinct
                        if owners[left] in definite_set and owners[right] in definite_set})
        counted = bound_distinct_occurrences(definite, same_pairs=[], distinct_pairs=edges, enumeration_complete=False)
        trace["bounds"] = {"lower": counted.bounds.lower, "upper": None}
        trace["distinct_witness"] = list(counted.distinct_witness)
        trace["required_start_bounds"] = [value.isoformat() for value in starts]
        trace["required_end_bounds"] = [value.isoformat() for value in ends]
        trace["reason_codes"] = list(counted.reason_codes)
        return trace
    except (OverflowError, ValueError):
        return {**trace, "bounds": None, "reason_codes": ["frequency_calendar_bounds_invalid"]}


def qualify_individual_days(statements, window, episode, *, required_period=None):
    """Minimum distinct dates consistent with explicitly recorded single days.

    A partial date supplies one possible day, never all days in that range.
    Greedy interval stabbing gives the minimum number of calendar days needed
    to satisfy the qualified statements; it does not assign actual dates.
    """
    trace = {
        "version": "frequency-day-calculation/v1", "bounds": None,
        "window_sha256": canonical_hash(window.model_dump(mode="json")),
        "episode_sha256": canonical_hash(episode), "days": [], "reason_codes": [],
        "enumeration_complete": False,
    }
    rows = {key: value for key, value in statements.items() if value["kind"] == "individual_day"}
    if not rows:
        return {**trace, "reason_codes": ["frequency_individual_not_available"]}
    try:
        starts, ends, required = required_frequency_period(window, episode) if required_period is None else required_period
        trace.update(required)
        if required["reason_codes"]:
            return trace
        if max(starts) > min(ends):
            return {**trace, "reason_codes": ["frequency_period_order_unresolved"]}
        inside = []
        for key, row in rows.items():
            bounds = (_source_date_bounds(FrequencySourceDate.model_validate(row["occurrence_date"]))
                      if row.get("occurrence_date") is not None else None)
            membership = "unresolved"
            if bounds is not None:
                lower, upper = bounds
                if lower >= max(starts) and upper <= min(ends):
                    membership = "inside"
                    inside.append((lower, upper, key))
                elif upper < min(starts) or lower > max(ends):
                    membership = "outside"
            trace["days"].append({"statement_sha256": key, "membership": membership,
                                  "date_bounds": [value.isoformat() for value in bounds] if bounds else None})
        lower_count, last = 0, None
        for lower, upper, _ in sorted(inside, key=lambda item: (item[1], item[0], item[2])):
            if last is None or lower > last:
                lower_count += 1
                last = upper
        trace["bounds"] = {"lower": lower_count, "upper": None}
        trace["required_start_bounds"] = [value.isoformat() for value in starts]
        trace["required_end_bounds"] = [value.isoformat() for value in ends]
        return trace
    except (OverflowError, ValueError):
        return {**trace, "bounds": None, "reason_codes": ["frequency_calendar_bounds_invalid"]}
