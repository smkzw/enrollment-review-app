from __future__ import annotations

from datetime import date
from calendar import monthrange
from math import ceil
from typing import Any

from pydantic import Field

from app.domain.contracts.common import ContractModel, DateValue
from app.domain.contracts.enums import (
    AnchorType,
    Comparator,
    DatePrecision,
    FactPolarity,
    LogicalOperator,
    TruthValue,
)
from app.domain.contracts.evidence import ClinicalFact
from app.domain.contracts.rules import AtomicExpression, AtomicPredicate, RuleComponent, RuleExpression


class EvaluationContext(ContractModel):
    facts: list[ClinicalFact] = Field(default_factory=list)
    anchor_dates: dict[AnchorType, DateValue] = Field(default_factory=dict)
    half_life_days: dict[str, float] = Field(default_factory=dict)


class EvaluationResult(ContractModel):
    truth: TruthValue
    reason_codes: list[str] = Field(default_factory=list)
    used_fact_ids: list[str] = Field(default_factory=list)


class ComponentEvaluation(ContractModel):
    applicable: TruthValue = TruthValue.TRUE
    trigger: EvaluationResult
    exception: EvaluationResult | None = None


def _result(
    truth: TruthValue,
    *reason_codes: str,
    used_fact_ids: list[str] | None = None,
) -> EvaluationResult:
    return EvaluationResult(
        truth=truth,
        reason_codes=list(dict.fromkeys(reason_codes)),
        used_fact_ids=used_fact_ids or [],
    )


def _merge(results: list[EvaluationResult], truth: TruthValue) -> EvaluationResult:
    return EvaluationResult(
        truth=truth,
        reason_codes=list(dict.fromkeys(code for item in results for code in item.reason_codes)),
        used_fact_ids=list(dict.fromkeys(fact_id for item in results for fact_id in item.used_fact_ids)),
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
            return TruthValue.TRUE
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


def _date_bounds(
    value: DateValue | None,
    *,
    allow_partial: bool,
) -> tuple[date, date] | None:
    if value is None or value.value is None:
        return None
    if value.precision == DatePrecision.DAY:
        return value.value, value.value
    if not allow_partial or value.precision == DatePrecision.UNKNOWN:
        return None
    if value.precision == DatePrecision.MONTH:
        first = value.value.replace(day=1)
        last = value.value.replace(day=monthrange(value.value.year, value.value.month)[1])
        return first, last
    if value.precision == DatePrecision.YEAR:
        return date(value.value.year, 1, 1), date(value.value.year, 12, 31)
    return None


def _evaluate_time(
    expression: AtomicExpression,
    fact: ClinicalFact,
    context: EvaluationContext,
) -> EvaluationResult:
    constraint = expression.time_constraint
    if constraint is None:
        return _result(TruthValue.TRUE, used_fact_ids=[fact.fact_id])
    event_bounds = _date_bounds(fact.effective_date, allow_partial=constraint.allow_partial_date)
    anchor_bounds = _date_bounds(
        context.anchor_dates.get(constraint.anchor_type),
        allow_partial=constraint.allow_partial_date,
    )
    if event_bounds is None or anchor_bounds is None:
        return _result(
            TruthValue.UNKNOWN,
            "date_or_anchor_missing",
            used_fact_ids=[fact.fact_id],
        )
    event_min, event_max = event_bounds
    anchor_min, anchor_max = anchor_bounds
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
            return _result(TruthValue.FALSE, "outside_time_window", used_fact_ids=[fact.fact_id])
        return _result(TruthValue.UNKNOWN, "ambiguous_partial_date", used_fact_ids=[fact.fact_id])
    if distance_max < 0:
        return _result(TruthValue.FALSE, "wrong_time_direction", used_fact_ids=[fact.fact_id])
    if distance_min < 0 <= distance_max:
        return _result(TruthValue.UNKNOWN, "ambiguous_time_direction", used_fact_ids=[fact.fact_id])

    lower_bound = constraint.lower_bound_days
    if constraint.half_life_multiplier is not None:
        fact_type = f"{expression.predicate.subject}.{expression.predicate.attribute}"
        half_life = context.half_life_days.get(fact_type)
        if half_life is None:
            return _result(TruthValue.UNKNOWN, "half_life_missing", used_fact_ids=[fact.fact_id])
        half_life_bound = ceil(half_life * constraint.half_life_multiplier)
        lower_bound = max(lower_bound or 0, half_life_bound)
    if lower_bound is not None:
        if distance_max < lower_bound:
            return _result(TruthValue.FALSE, "below_time_window", used_fact_ids=[fact.fact_id])
        if distance_min < lower_bound <= distance_max:
            return _result(TruthValue.UNKNOWN, "ambiguous_time_window", used_fact_ids=[fact.fact_id])
    if constraint.upper_bound_days is not None:
        if distance_min > constraint.upper_bound_days:
            return _result(TruthValue.FALSE, "above_time_window", used_fact_ids=[fact.fact_id])
        if distance_min <= constraint.upper_bound_days < distance_max:
            return _result(TruthValue.UNKNOWN, "ambiguous_time_window", used_fact_ids=[fact.fact_id])
    return _result(TruthValue.TRUE, used_fact_ids=[fact.fact_id])


def _evaluate_atomic(expression: AtomicExpression, context: EvaluationContext) -> EvaluationResult:
    predicate = expression.predicate
    fact_type = f"{predicate.subject}.{predicate.attribute}"
    matching = [fact for fact in context.facts if fact.fact_type == fact_type]
    if not matching:
        return _result(TruthValue.UNKNOWN, "fact_not_observed")
    if any(fact.polarity == FactPolarity.UNKNOWN for fact in matching):
        return _result(
            TruthValue.UNKNOWN,
            "fact_polarity_unknown",
            used_fact_ids=[fact.fact_id for fact in matching],
        )
    observed_values = {(fact.value, _canonical_unit(fact.unit)) for fact in matching}
    if len(observed_values) != 1 or any(fact.conflict_group_id for fact in matching):
        return _result(
            TruthValue.UNKNOWN,
            "source_conflict",
            used_fact_ids=[fact.fact_id for fact in matching],
        )
    fact = matching[0]
    if predicate.unit is not None and _canonical_unit(predicate.unit) != _canonical_unit(fact.unit):
        return _result(TruthValue.UNKNOWN, "unit_mismatch", used_fact_ids=[fact.fact_id])
    comparison = _compare(predicate, fact.value)
    comparison_result = _result(comparison, used_fact_ids=[fact.fact_id])
    time_result = _evaluate_time(expression, fact, context)
    return _evaluate_logical(LogicalOperator.ALL, [comparison_result, time_result])


def evaluate_expression(expression: RuleExpression, context: EvaluationContext) -> EvaluationResult:
    if expression.kind == "predicate":
        return _evaluate_atomic(expression, context)
    children = [evaluate_expression(child, context) for child in expression.children]
    return _evaluate_logical(expression.operator, children)


def evaluate_component(component: RuleComponent, context: EvaluationContext) -> ComponentEvaluation:
    return ComponentEvaluation(
        applicable=TruthValue.TRUE,
        trigger=evaluate_expression(component.expression, context),
        exception=(
            evaluate_expression(component.exception_expression, context)
            if component.exception_expression is not None
            else None
        ),
    )
