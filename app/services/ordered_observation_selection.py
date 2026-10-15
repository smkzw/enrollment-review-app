"""Deterministic ordering over explicitly accounted, qualified frozen observations.

No clinical names or provider assumptions. The caller owns the version-bound
semantic adoption permission; this module cannot establish it from agreement.
"""
from dataclasses import dataclass

from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import TruthValue
from app.domain.expression import evaluate_time_constraint


@dataclass(frozen=True)
class OrderedObservationSelection:
    fact_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    excluded: tuple[tuple[str, str], ...] = ()


def observation_scope_reasons(*, facts, operand_fact_ids, accounting):
    """Check supplied facts, not completeness of clinical history.

    A date-only candidate remains unresolved when its value cannot be qualified;
    it must not disappear from scope simply because one attribute was rejected.
    """
    rows = {item["fact_id"]: item for item in accounting}
    if len(rows) != len(accounting) or set(rows) != set(facts):
        return ("candidate_enumeration_incomplete",)
    operands = set(operand_fact_ids)
    candidates = set()
    for fact_id, row in rows.items():
        if row["status"] == "agreed_noncorrespondence":
            if fact_id in operands:
                return ("observation_scope_disagreement",)
        elif row["status"] == "candidates_in_both_lanes":
            candidates.add(fact_id)
        else:
            return ("observation_scope_unverified",)
    if not candidates or candidates != operands:
        return ("observation_operand_set_unverified",)
    return ()


def select_ordered_observation(
    *, policy, facts, operand_fact_ids, date_fact_ids, accounting,
    time_constraint, anchor_dates, time_purpose="event_membership",
    conflicting_fact_ids=(),
):
    """Choose a unique date-dominant observation, never a favorable value.

    Accounting covers supplied facts only. Missing extraction, missing documents
    and unknown clinical history remain separate upstream evidence obligations.
    """
    if policy is None or policy.mode != "single" or policy.selection is None:
        return OrderedObservationSelection((), ("observation_selection_unverified",))
    window_order = policy.selection.window_order
    if (window_order in {None, "unresolved"}
            or (time_constraint is None) != (window_order == "not_applicable")):
        return OrderedObservationSelection((), ("observation_window_policy_unverified",))
    reasons = observation_scope_reasons(
        facts=facts, operand_fact_ids=operand_fact_ids, accounting=accounting,
    )
    if reasons:
        return OrderedObservationSelection((), reasons)
    return select_qualified_observation_dates(
        policy=policy, facts=facts, operand_fact_ids=operand_fact_ids,
        date_fact_ids=date_fact_ids, time_constraint=time_constraint,
        anchor_dates=anchor_dates, time_purpose=time_purpose,
        conflicting_fact_ids=conflicting_fact_ids,
    )


def select_qualified_observation_dates(
    *, policy, facts, operand_fact_ids, date_fact_ids, time_constraint,
    anchor_dates, time_purpose="event_membership", conflicting_fact_ids=(),
):
    """Date arithmetic after the caller proves candidate/source completeness.

    Repeated representations of one verified acquisition may be represented by
    an original fact for ordering only; this does not select its clinical value.
    """
    if policy is None or policy.mode != "single" or policy.selection is None:
        return OrderedObservationSelection((), ("observation_selection_unverified",))
    window_order = policy.selection.window_order
    if (window_order in {None, "unresolved"}
            or (time_constraint is None) != (window_order == "not_applicable")):
        return OrderedObservationSelection((), ("observation_window_policy_unverified",))
    candidates = set(operand_fact_ids)
    dates = set(date_fact_ids)
    if candidates.intersection(conflicting_fact_ids):
        return OrderedObservationSelection((), ("source_conflict",))
    if not candidates <= dates:
        return OrderedObservationSelection((), ("known_date_unqualified",))
    bounds = {}
    membership = {}
    excluded = []
    for fact_id in sorted(candidates):
        date_range = facts[fact_id].date_range
        if date_range is None or date_range.lower_bound is None or date_range.upper_bound is None:
            return OrderedObservationSelection((), ("ordering_date_missing",))
        membership[fact_id] = TruthValue.TRUE
        if time_constraint is not None:
            if time_purpose not in {"event_membership", "source_validity"}:
                return OrderedObservationSelection((), ("observation_window_policy_unverified",))
            result = evaluate_time_constraint(
                time_constraint,
                event_value=DateValue(value=date_range.lower_bound, precision=date_range.precision,
                                      source_text=date_range.source_text),
                anchor_value=anchor_dates.get(time_constraint.anchor_type),
            )
            membership[fact_id] = result.truth
            if result.truth == TruthValue.FALSE and window_order == "within_window":
                excluded.append((fact_id, "observation_out_of_window"))
                continue
        bounds[fact_id] = (date_range.lower_bound, date_range.upper_bound)
    if not bounds:
        return OrderedObservationSelection((), ("observation_out_of_window",), tuple(excluded))
    latest = policy.selection.criterion == "latest"
    governing = [
        fact_id for fact_id, (lower, upper) in bounds.items()
        if all(other == fact_id or (lower > other_upper if latest else upper < other_lower)
               for other, (other_lower, other_upper) in bounds.items())
    ]
    if len(governing) != 1:
        reason = ("observation_tie_unresolved" if all(lo == hi for lo, hi in bounds.values())
                  else "observation_order_ambiguous_partial_date")
        return OrderedObservationSelection((), (reason,), tuple(excluded))
    selected = governing[0]
    if membership[selected] != TruthValue.TRUE:
        if membership[selected] == TruthValue.FALSE:
            return OrderedObservationSelection((), ("observation_out_of_window",),
                                              ((selected, "observation_out_of_window"),))
        return OrderedObservationSelection((), ("observation_window_membership_unverified",), tuple(excluded))
    excluded.extend((fact_id, "not_governing_observation") for fact_id in sorted(bounds) if fact_id != selected)
    return OrderedObservationSelection((selected,), (), tuple(excluded))
