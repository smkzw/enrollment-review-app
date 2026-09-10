from __future__ import annotations

from datetime import date, timedelta
from calendar import monthrange
from math import ceil
from typing import Any

from pydantic import Field, model_validator

from app.domain.contracts.common import ContractModel, DateValue, ScalarValue
from app.domain.contracts.enums import (
    AnchorType,
    Comparator,
    DatePrecision,
    FactPolarity,
    LogicalOperator,
    TruthValue,
)
from app.domain.contracts.evidence import ClinicalFact
from app.domain.contracts.rules import (
    AtomicExpression,
    AtomicPredicate,
    RuleComponent,
    RuleExpression,
    TimeQuantity,
    TimeUnit,
)


class EvaluationContext(ContractModel):
    project_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    accepted_fact_ids: list[str] = Field(default_factory=list)
    facts: list[ClinicalFact] = Field(default_factory=list)
    anchor_dates: dict[AnchorType, DateValue] = Field(default_factory=dict)
    half_life_days: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_fact_scope(self) -> "EvaluationContext":
        fact_ids = [fact.fact_id for fact in self.facts]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("EvaluationContext 不能包含重复 fact_id")
        if set(fact_ids) != set(self.accepted_fact_ids):
            raise ValueError("Evaluator 只能读取当前 Gate 已接受的事实集合")
        expected_scope = (
            self.project_id,
            self.subject_id,
            self.review_episode_id,
            self.evidence_snapshot_id,
        )
        for fact in self.facts:
            actual_scope = (
                fact.project_id,
                fact.subject_id,
                fact.review_episode_id,
                fact.evidence_snapshot_id,
            )
            if actual_scope != expected_scope:
                raise ValueError("ClinicalFact 超出当前项目、受试者、Episode 或快照范围")
        return self


class EvaluationResult(ContractModel):
    truth: TruthValue
    reason_codes: list[str] = Field(default_factory=list)
    used_fact_ids: list[str] = Field(default_factory=list)
    observed_value: ScalarValue | None = None
    observed_unit: str | None = None
    evidence_span_ids: list[str] = Field(default_factory=list)


class ComponentEvaluation(ContractModel):
    applicable: TruthValue = TruthValue.TRUE
    trigger: EvaluationResult
    exception: EvaluationResult | None = None
    predicate_evaluations: dict[str, EvaluationResult]


def _result(
    truth: TruthValue,
    *reason_codes: str,
    used_fact_ids: list[str] | None = None,
    observed_value: ScalarValue | None = None,
    observed_unit: str | None = None,
    evidence_span_ids: list[str] | None = None,
) -> EvaluationResult:
    return EvaluationResult(
        truth=truth,
        reason_codes=list(dict.fromkeys(reason_codes)),
        used_fact_ids=used_fact_ids or [],
        observed_value=observed_value,
        observed_unit=observed_unit,
        evidence_span_ids=evidence_span_ids or [],
    )


def _merge(results: list[EvaluationResult], truth: TruthValue) -> EvaluationResult:
    return EvaluationResult(
        truth=truth,
        reason_codes=list(dict.fromkeys(code for item in results for code in item.reason_codes)),
        used_fact_ids=list(dict.fromkeys(fact_id for item in results for fact_id in item.used_fact_ids)),
        evidence_span_ids=list(
            dict.fromkeys(span_id for item in results for span_id in item.evidence_span_ids)
        ),
    )


def _evaluate_logical(operator: LogicalOperator, results: list[EvaluationResult]) -> EvaluationResult:
    truths = [item.truth for item in results]
    if operator == LogicalOperator.ALL:
        if TruthValue.FALSE in truths:
            return _merge(results, TruthValue.FALSE)
        if TruthValue.UNKNOWN in truths:
            return _merge(results, TruthValue.UNKNOWN)
        return _merge(results, TruthValue.TRUE)
    if operator == LogicalOperator.ANY:
        if TruthValue.TRUE in truths:
            return _merge(results, TruthValue.TRUE)
        if TruthValue.UNKNOWN in truths:
            return _merge(results, TruthValue.UNKNOWN)
        return _merge(results, TruthValue.FALSE)
    if operator == LogicalOperator.NOT:
        inverse = {
            TruthValue.TRUE: TruthValue.FALSE,
            TruthValue.FALSE: TruthValue.TRUE,
            TruthValue.UNKNOWN: TruthValue.UNKNOWN,
        }[truths[0]]
        return _merge(results, inverse)
    raise ValueError(f"不支持的逻辑运算符: {operator}")


def _canonical_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    return unit.strip().lower().replace("×", "x").replace(" ", "")


def _compare(predicate: AtomicPredicate, observed: Any) -> TruthValue:
    expected = predicate.value
    try:
        if predicate.comparator == Comparator.EXISTS:
            return TruthValue.UNKNOWN if observed is None else TruthValue.TRUE
        if predicate.comparator == Comparator.EQ:
            return TruthValue.TRUE if observed == expected else TruthValue.FALSE
        if predicate.comparator == Comparator.NE:
            return TruthValue.TRUE if observed != expected else TruthValue.FALSE
        if predicate.comparator == Comparator.GT:
            return TruthValue.TRUE if observed > expected else TruthValue.FALSE
        if predicate.comparator == Comparator.GTE:
            return TruthValue.TRUE if observed >= expected else TruthValue.FALSE
        if predicate.comparator == Comparator.LT:
            return TruthValue.TRUE if observed < expected else TruthValue.FALSE
        if predicate.comparator == Comparator.LTE:
            return TruthValue.TRUE if observed <= expected else TruthValue.FALSE
        if predicate.comparator == Comparator.IN:
            return TruthValue.TRUE if observed in expected else TruthValue.FALSE
        if predicate.comparator == Comparator.NOT_IN:
            return TruthValue.TRUE if observed not in expected else TruthValue.FALSE
    except (TypeError, ValueError):
        return TruthValue.UNKNOWN
    raise ValueError(f"不支持的比较器: {predicate.comparator}")


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_index = divmod(month_index, 12)
    month = month_index + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def _shift_date(value: date, quantity: TimeQuantity, *, sign: int = 1) -> date:
    """Shift a complete calendar date without flattening months or years to days."""

    amount = sign * quantity.value
    if quantity.unit == TimeUnit.DAY:
        return value + timedelta(days=amount)
    if quantity.unit == TimeUnit.WEEK:
        return value + timedelta(days=amount * 7)
    if quantity.unit == TimeUnit.MONTH:
        return _add_months(value, amount)
    if quantity.unit == TimeUnit.YEAR:
        target_year = value.year + amount
        day = min(value.day, monthrange(target_year, value.month)[1])
        return date(target_year, value.month, day)
    raise ValueError(f"不支持的时间单位: {quantity.unit}")


def _is_end_of_month(value: date) -> bool:
    return value.day == monthrange(value.year, value.month)[1]


def _calendar_shift_is_boundary(
    event_date: date,
    anchor_date: date,
    shifted_event_date: date,
    quantity: TimeQuantity,
) -> bool:
    """Treat matching month-end dates as the same calendar boundary.

    For example, 2023-02-28 to 2024-02-29 is one calendar year even though
    the direct year shift clamps the intermediate date to 2024-02-28.
    """

    if shifted_event_date == anchor_date:
        return True
    return (
        quantity.unit in {TimeUnit.MONTH, TimeUnit.YEAR}
        and _is_end_of_month(event_date)
        and _is_end_of_month(anchor_date)
        and (shifted_event_date.year, shifted_event_date.month)
        == (anchor_date.year, anchor_date.month)
    )


def _calendar_bound_satisfied(
    event_date: date,
    anchor_date: date,
    direction: str,
    quantity: TimeQuantity,
    *,
    is_lower_bound: bool,
    inclusive: bool,
) -> bool:
    """Evaluate a month/year boundary using calendar arithmetic.

    A lower ``before`` bound asks whether adding the duration to the event
    still lands on or before the anchor; an upper bound uses the opposite
    inequality.  The ``after`` case mirrors this by shifting the event back.
    """

    if direction == "before":
        shifted_event_date = _shift_date(event_date, quantity)
        if _calendar_shift_is_boundary(
            event_date, anchor_date, shifted_event_date, quantity
        ):
            return inclusive
        if is_lower_bound:
            return shifted_event_date < anchor_date if not inclusive else shifted_event_date <= anchor_date
        return shifted_event_date > anchor_date if not inclusive else shifted_event_date >= anchor_date
    shifted_event_date = _shift_date(event_date, quantity, sign=-1)
    if _calendar_shift_is_boundary(
        event_date, anchor_date, shifted_event_date, quantity
    ):
        return inclusive
    if is_lower_bound:
        return shifted_event_date > anchor_date if not inclusive else shifted_event_date >= anchor_date
    return shifted_event_date < anchor_date if not inclusive else shifted_event_date <= anchor_date


def _date_bounds(value: DateValue, *, allow_partial: bool) -> tuple[date, date] | None:
    """Return the complete range represented by a clinical date value."""

    if value.value is None:
        return None
    if value.precision == DatePrecision.DAY:
        return value.value, value.value
    if not allow_partial or value.precision == DatePrecision.UNKNOWN:
        return None
    if value.precision == DatePrecision.MONTH:
        first = value.value.replace(day=1)
        last = value.value.replace(
            day=monthrange(value.value.year, value.value.month)[1]
        )
        return first, last
    if value.precision == DatePrecision.YEAR:
        return date(value.value.year, 1, 1), date(value.value.year, 12, 31)
    return None


def _calendar_bound_truth(
    event_bounds: tuple[date, date],
    anchor_bounds: tuple[date, date],
    direction: str,
    quantity: TimeQuantity,
    *,
    is_lower_bound: bool,
    inclusive: bool,
) -> TruthValue:
    """Evaluate every endpoint combination represented by partial dates.

    The result is definitive only when the whole possible interval agrees. This
    preserves calendar-month/year semantics without inventing an exact day for
    a month-only or year-only source date.
    """

    outcomes = {
        _calendar_bound_satisfied(
            event_date,
            anchor_date,
            direction,
            quantity,
            is_lower_bound=is_lower_bound,
            inclusive=inclusive,
        )
        for event_date in event_bounds
        for anchor_date in anchor_bounds
    }
    if outcomes == {True}:
        return TruthValue.TRUE
    if outcomes == {False}:
        return TruthValue.FALSE
    return TruthValue.UNKNOWN


def _quantity_in_days(quantity: TimeQuantity | None) -> int | None:
    if quantity is None:
        return None
    if quantity.unit == TimeUnit.DAY:
        return quantity.value
    if quantity.unit == TimeUnit.WEEK:
        return quantity.value * 7
    return None


def _evaluate_time(
    expression: AtomicExpression,
    fact: ClinicalFact,
    context: EvaluationContext,
) -> EvaluationResult:
    constraint = expression.time_constraint
    if constraint is None:
        return _result(TruthValue.TRUE, used_fact_ids=[fact.fact_id])
    event_value = fact.effective_date
    anchor_value = context.anchor_dates.get(constraint.anchor_type)
    if (
        event_value is None
        or event_value.value is None
        or anchor_value is None
        or anchor_value.value is None
    ):
        return _result(
            TruthValue.UNKNOWN,
            "date_or_anchor_missing",
            used_fact_ids=[fact.fact_id],
        )
    event_bounds = _date_bounds(
        event_value, allow_partial=constraint.allow_partial_date
    )
    anchor_bounds = _date_bounds(
        anchor_value, allow_partial=constraint.allow_partial_date
    )
    if event_bounds is None or anchor_bounds is None:
        return _result(
            TruthValue.UNKNOWN,
            "ambiguous_partial_date",
            "ambiguous_time_window",
            used_fact_ids=[fact.fact_id],
        )
    event_min, event_max = event_bounds
    anchor_min, anchor_max = anchor_bounds
    partial_reason_codes = (
        ("ambiguous_time_window", "ambiguous_partial_date")
        if (
            event_value.precision != DatePrecision.DAY
            or anchor_value.precision != DatePrecision.DAY
        )
        else ("ambiguous_time_window",)
    )
    if constraint.direction == "before":
        distance_min = (anchor_min - event_max).days
        distance_max = (anchor_max - event_min).days
    elif constraint.direction == "after":
        distance_min = (event_min - anchor_max).days
        distance_max = (event_max - anchor_min).days
    else:
        if event_min == event_max == anchor_min == anchor_max:
            return _result(TruthValue.TRUE, used_fact_ids=[fact.fact_id])
        if event_max < anchor_min or anchor_max < event_min:
            return _result(
                TruthValue.FALSE,
                "outside_time_window",
                used_fact_ids=[fact.fact_id],
            )
        return _result(
            TruthValue.UNKNOWN,
            "ambiguous_partial_date",
            used_fact_ids=[fact.fact_id],
        )
    if distance_max < 0:
        return _result(TruthValue.FALSE, "wrong_time_direction", used_fact_ids=[fact.fact_id])
    if distance_min < 0 <= distance_max:
        return _result(TruthValue.UNKNOWN, "ambiguous_time_direction", used_fact_ids=[fact.fact_id])

    lower_bound = constraint.lower_bound_days
    lower_quantity_days = _quantity_in_days(constraint.lower_bound)
    if lower_quantity_days is not None:
        lower_bound = max(lower_bound or 0, lower_quantity_days)
    upper_bound = constraint.upper_bound_days
    upper_quantity_days = _quantity_in_days(constraint.upper_bound)
    if upper_quantity_days is not None:
        upper_bound = (
            upper_quantity_days
            if upper_bound is None
            else min(upper_bound, upper_quantity_days)
        )
    if constraint.half_life_multiplier is not None:
        fact_type = f"{expression.predicate.subject}.{expression.predicate.attribute}"
        half_life = context.half_life_days.get(fact_type)
        if half_life is None:
            return _result(TruthValue.UNKNOWN, "half_life_missing", used_fact_ids=[fact.fact_id])
        half_life_bound = ceil(half_life * constraint.half_life_multiplier)
        lower_bound = max(lower_bound or 0, half_life_bound)
    if lower_bound is not None:
        below_window = (
            distance_max < lower_bound
            if constraint.lower_bound_inclusive
            else distance_max <= lower_bound
        )
        crosses_boundary = (
            distance_min < lower_bound <= distance_max
            if constraint.lower_bound_inclusive
            else distance_min <= lower_bound < distance_max
        )
        if below_window:
            return _result(TruthValue.FALSE, "below_time_window", used_fact_ids=[fact.fact_id])
        if crosses_boundary:
            return _result(TruthValue.UNKNOWN, "ambiguous_time_window", used_fact_ids=[fact.fact_id])
    if upper_bound is not None:
        above_window = (
            distance_min > upper_bound
            if constraint.upper_bound_inclusive
            else distance_min >= upper_bound
        )
        crosses_boundary = (
            distance_min <= upper_bound < distance_max
            if constraint.upper_bound_inclusive
            else distance_min < upper_bound <= distance_max
        )
        if above_window:
            return _result(TruthValue.FALSE, "above_time_window", used_fact_ids=[fact.fact_id])
        if crosses_boundary:
            return _result(TruthValue.UNKNOWN, "ambiguous_time_window", used_fact_ids=[fact.fact_id])
    if constraint.lower_bound is not None and constraint.lower_bound.unit in {
        TimeUnit.MONTH,
        TimeUnit.YEAR,
    }:
        lower_truth = _calendar_bound_truth(
            event_bounds,
            anchor_bounds,
            constraint.direction.value,
            constraint.lower_bound,
            is_lower_bound=True,
            inclusive=constraint.lower_bound_inclusive,
        )
        if lower_truth == TruthValue.FALSE:
            return _result(
                TruthValue.FALSE,
                "below_time_window",
                used_fact_ids=[fact.fact_id],
            )
        if lower_truth == TruthValue.UNKNOWN:
            return _result(
                TruthValue.UNKNOWN,
                *partial_reason_codes,
                used_fact_ids=[fact.fact_id],
            )
    if constraint.upper_bound is not None and constraint.upper_bound.unit in {
        TimeUnit.MONTH,
        TimeUnit.YEAR,
    }:
        upper_truth = _calendar_bound_truth(
            event_bounds,
            anchor_bounds,
            constraint.direction.value,
            constraint.upper_bound,
            is_lower_bound=False,
            inclusive=constraint.upper_bound_inclusive,
        )
        if upper_truth == TruthValue.FALSE:
            return _result(
                TruthValue.FALSE,
                "above_time_window",
                used_fact_ids=[fact.fact_id],
            )
        if upper_truth == TruthValue.UNKNOWN:
            return _result(
                TruthValue.UNKNOWN,
                *partial_reason_codes,
                used_fact_ids=[fact.fact_id],
            )
    return _result(TruthValue.TRUE, used_fact_ids=[fact.fact_id])


def _evaluate_atomic(expression: AtomicExpression, context: EvaluationContext) -> EvaluationResult:
    predicate = expression.predicate
    fact_type = f"{predicate.subject}.{predicate.attribute}"
    matching = [fact for fact in context.facts if fact.fact_type == fact_type]
    if not matching:
        reason = (
            "professional_judgment_missing"
            if predicate.requires_professional_judgment
            else "fact_not_observed"
        )
        return _result(TruthValue.UNKNOWN, reason)
    if any(fact.polarity == FactPolarity.UNKNOWN for fact in matching):
        return _result(
            TruthValue.UNKNOWN,
            "fact_polarity_unknown",
            used_fact_ids=[fact.fact_id for fact in matching],
            evidence_span_ids=[
                span_id for fact in matching for span_id in fact.evidence_span_ids
            ],
        )
    observed_values = {
        (fact.value, _canonical_unit(fact.unit), fact.polarity)
        for fact in matching
    }
    if len(observed_values) != 1 or any(fact.conflict_group_id for fact in matching):
        return _result(
            TruthValue.UNKNOWN,
            "source_conflict",
            used_fact_ids=[fact.fact_id for fact in matching],
            evidence_span_ids=[
                span_id for fact in matching for span_id in fact.evidence_span_ids
            ],
        )
    fact = matching[0]
    if predicate.unit is not None and _canonical_unit(predicate.unit) != _canonical_unit(fact.unit):
        return _result(
            TruthValue.UNKNOWN,
            "unit_mismatch",
            used_fact_ids=[fact.fact_id],
            observed_value=fact.value,
            observed_unit=fact.unit,
            evidence_span_ids=fact.evidence_span_ids,
        )
    comparison = _compare(predicate, fact.value)
    if fact.polarity == FactPolarity.NEGATED:
        comparison = {
            TruthValue.TRUE: TruthValue.FALSE,
            TruthValue.FALSE: TruthValue.TRUE,
            TruthValue.UNKNOWN: TruthValue.UNKNOWN,
        }[comparison]
    comparison_result = _result(comparison, used_fact_ids=[fact.fact_id])
    time_result = _evaluate_time(expression, fact, context)
    combined = _evaluate_logical(LogicalOperator.ALL, [comparison_result, time_result])
    return _result(
        combined.truth,
        *combined.reason_codes,
        used_fact_ids=combined.used_fact_ids,
        observed_value=fact.value,
        observed_unit=fact.unit,
        evidence_span_ids=fact.evidence_span_ids,
    )


def evaluate_expression(expression: RuleExpression, context: EvaluationContext) -> EvaluationResult:
    if expression.kind == "predicate":
        return _evaluate_atomic(expression, context)
    children = [evaluate_expression(child, context) for child in expression.children]
    return _evaluate_logical(expression.operator, children)


def evaluate_component(component: RuleComponent, context: EvaluationContext) -> ComponentEvaluation:
    expressions = [component.expression]
    if component.exception_expression is not None:
        expressions.append(component.exception_expression)
    predicate_evaluations = {
        atomic.predicate.predicate_id: evaluate_expression(atomic, context)
        for expression in expressions
        for atomic in _iter_atomic_expressions(expression)
    }
    return ComponentEvaluation(
        applicable=TruthValue.TRUE,
        trigger=evaluate_expression(component.expression, context),
        exception=(
            evaluate_expression(component.exception_expression, context)
            if component.exception_expression is not None
            else None
        ),
        predicate_evaluations=predicate_evaluations,
    )


def _iter_atomic_expressions(expression: RuleExpression):
    if expression.kind == "predicate":
        yield expression
        return
    for child in expression.children:
        yield from _iter_atomic_expressions(child)
