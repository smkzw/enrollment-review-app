"""Date calculation only; drug membership, use evidence and exceptions stay separate."""
from app.domain.calendar_dates import date_bounds
from app.domain.contracts.enums import TruthValue
from app.domain.contracts.evaluation_result import EvaluationResult
from app.domain.contracts.rules import MedicationRestriction, TimeConstraint
from app.domain.expression import evaluate_time_constraint


def medication_window_violation(
    restriction: MedicationRestriction, *, use_date, anchor_dates,
) -> EvaluationResult:
    """TRUE means this dated record falls in the prohibited time, not exclusion.

    No date, PK duration, drug classification or actual administration is inferred.
    A caller must qualify those inputs before using the calculation clinically.
    """
    window = restriction.window
    if window is None or restriction.window_interpretation is None:
        return EvaluationResult(truth=TruthValue.UNKNOWN, reason_codes=["medication_window_meaning_missing"])
    anchor = anchor_dates.get(window.anchor_type)
    use_bounds = date_bounds(use_date, allow_partial=window.allow_partial_date) if use_date else None
    anchor_bounds = date_bounds(anchor, allow_partial=window.allow_partial_date) if anchor else None
    if use_bounds is None or anchor_bounds is None:
        return EvaluationResult(truth=TruthValue.UNKNOWN, reason_codes=["date_or_anchor_missing"])
    # A later record is not a failed washout before an earlier named anchor.
    if (window.direction == "before" and use_bounds[0] > anchor_bounds[1]
            or window.direction == "after" and use_bounds[1] < anchor_bounds[0]):
        return EvaluationResult(truth=TruthValue.FALSE, reason_codes=["wrong_time_direction"])
    inverse = {TruthValue.TRUE: TruthValue.FALSE, TruthValue.FALSE: TruthValue.TRUE,
               TruthValue.UNKNOWN: TruthValue.UNKNOWN}
    if restriction.window_interpretation == "minimum_washout":
        safe = evaluate_time_constraint(window, event_value=use_date, anchor_value=anchor)
        return safe.model_copy(update={"truth": inverse[safe.truth]})
    if window.half_life_multiplier is None:
        return evaluate_time_constraint(window, event_value=use_date, anchor_value=anchor)
    # PK is a minimum elapsed-time constraint. Invert it once even when it is
    # the only duration; a missing calendar branch must not become an open window.
    pk = TimeConstraint(anchor_type=window.anchor_type, direction=window.direction,
        half_life_multiplier=window.half_life_multiplier, half_life_evidence=window.half_life_evidence,
        allow_partial_date=window.allow_partial_date)
    pk_safe = evaluate_time_constraint(pk, event_value=use_date, anchor_value=anchor)
    pk_result = pk_safe.model_copy(update={"truth": inverse[pk_safe.truth]})
    calendar_payload = window.model_dump(mode="json")
    calendar_payload.update(half_life_multiplier=None, half_life_evidence=None, combined_window_selection=None)
    if window.upper_bound is None and window.upper_bound_days is None:
        return pk_result
    calendar_result = evaluate_time_constraint(TimeConstraint.model_validate(calendar_payload),
        event_value=use_date, anchor_value=anchor)
    # The explicitly approved longer-of window is a union of forbidden periods.
    truth = (TruthValue.TRUE if TruthValue.TRUE in {calendar_result.truth, pk_result.truth}
        else TruthValue.FALSE if calendar_result.truth == pk_result.truth == TruthValue.FALSE
        else TruthValue.UNKNOWN)
    return EvaluationResult(truth=truth, reason_codes=list(dict.fromkeys(
        [*calendar_result.reason_codes, *pk_result.reason_codes])) if truth == TruthValue.UNKNOWN else [])


def medication_period_violation(*, use_date, period_start, cutoff_date):
    """Check an observed date in a known applicable interval, not the whole study."""
    use = date_bounds(use_date, allow_partial=True) if use_date else None
    start = date_bounds(period_start, allow_partial=False) if period_start else None
    if use is None or start is None or cutoff_date is None or cutoff_date < start[0]:
        return EvaluationResult(truth=TruthValue.UNKNOWN, reason_codes=["date_or_anchor_missing"])
    if use[1] < start[0] or use[0] > cutoff_date:
        return EvaluationResult(truth=TruthValue.FALSE, reason_codes=["outside_time_window"])
    if use[0] >= start[0] and use[1] <= cutoff_date:
        return EvaluationResult(truth=TruthValue.TRUE)
    return EvaluationResult(truth=TruthValue.UNKNOWN, reason_codes=["ambiguous_time_window"])
