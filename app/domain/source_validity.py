"""Check report freshness without deciding a clinical condition or inventing dates."""
from collections.abc import Mapping
from app.domain.calendar_dates import date_bounds, shift_date
from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import AnchorType, ReviewStage, TruthValue
from app.domain.contracts.facts import PartialDateRange
from app.domain.contracts.rules import TimeConstraint, TimeQuantity
from app.domain.expression import EvaluationResult, evaluate_time_constraint


def source_validity_anchor(
    *, due_stage: ReviewStage, current_stage: ReviewStage,
    anchors: Mapping[AnchorType, DateValue],
) -> DateValue | None:
    named_type = {
        ReviewStage.SCREENING: AnchorType.SCREENING_DATE,
        ReviewStage.BASELINE: AnchorType.BASELINE_DATE,
    }.get(due_stage)
    named = anchors.get(named_type) if named_type is not None else None
    current = anchors.get(AnchorType.REVIEW_NODE_DATE) if due_stage == current_stage else None
    if named is not None and current is not None:
        if date_bounds(named, allow_partial=True) != date_bounds(current, allow_partial=True):
            return None
    return named if named is not None else current


def source_validity(
    observed: PartialDateRange | None,
    window: TimeQuantity,
    anchor: DateValue | None,
) -> TruthValue:
    if observed is None or anchor is None:
        return TruthValue.UNKNOWN
    anchors = date_bounds(anchor, allow_partial=True)
    if anchors is None or observed.lower_bound is None or observed.upper_bound is None:
        return TruthValue.UNKNOWN
    try:
        earliest_start = shift_date(anchors[0], window, sign=-1)
        latest_start = shift_date(anchors[1], window, sign=-1)
    except (ValueError, OverflowError):
        return TruthValue.UNKNOWN
    if observed.lower_bound >= latest_start and observed.upper_bound <= anchors[0]:
        return TruthValue.TRUE
    if observed.upper_bound < earliest_start or observed.lower_bound > anchors[1]:
        return TruthValue.FALSE
    return TruthValue.UNKNOWN


def control_source_validity(
    observed: PartialDateRange | None,
    constraint: TimeConstraint,
    anchors: Mapping[AnchorType, DateValue],
    *,
    half_life_days: float | None = None,
) -> EvaluationResult:
    """Preserve month/year precision and use only the explicitly named anchor."""
    event = None
    if observed is not None:
        observed = PartialDateRange.model_validate(observed.model_dump(mode="json"))
        # DateValue with MONTH/YEAR precision still denotes the whole calendar
        # interval; its value is not an assertion that the event happened on day 1.
        event = DateValue(
            value=observed.lower_bound,
            precision=observed.precision,
            source_text=observed.source_text,
        )
    return evaluate_time_constraint(
        constraint,
        event_value=event,
        anchor_value=anchors.get(constraint.anchor_type),
        half_life_days=half_life_days,
    )
