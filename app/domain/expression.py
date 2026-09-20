from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
from calendar import monthrange
from math import ceil
from typing import Any
from collections.abc import Mapping, Sequence

from pydantic import Field, model_validator

from app.domain.calendar_dates import date_bounds as _date_bounds, shift_date as _shift_date
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
from app.domain.contracts.evaluation_result import EvaluationResult, RepeatAtomEvaluation, FrequencyAtomEvaluation
from app.domain.contracts.rules import (
    AtomicExpression,
    AtomicPredicate,
    RuleComponent,
    RuleExpression,
    TimeQuantity,
    TimeConstraint,
    TimeUnit,
)
from app.domain.publication import canonical_hash


class EvaluationContext(ContractModel):
    project_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    accepted_fact_ids: list[str] = Field(default_factory=list)
    facts: list[ClinicalFact] = Field(default_factory=list)
    anchor_dates: dict[AnchorType, DateValue] = Field(default_factory=dict)
    half_life_days: dict[str, float] = Field(default_factory=dict)
    # Legacy component-local vocabulary, not verified predicate correspondence.
    # R01 remains open: a category match alone cannot prove a clinical proposition.
    predicate_fact_type_aliases: dict[str, list[str]] = Field(default_factory=dict)

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
    return compare_values(predicate.comparator, observed, predicate.value)


def compare_values(comparator: Comparator, observed: Any, expected: Any) -> TruthValue:
    try:
        if comparator == Comparator.EXISTS:
            return TruthValue.UNKNOWN if observed is None else TruthValue.TRUE
        if comparator == Comparator.EQ:
            return TruthValue.TRUE if observed == expected else TruthValue.FALSE
        if comparator == Comparator.NE:
            return TruthValue.TRUE if observed != expected else TruthValue.FALSE
        if comparator == Comparator.GT:
            return TruthValue.TRUE if observed > expected else TruthValue.FALSE
        if comparator == Comparator.GTE:
            return TruthValue.TRUE if observed >= expected else TruthValue.FALSE
        if comparator == Comparator.LT:
            return TruthValue.TRUE if observed < expected else TruthValue.FALSE
        if comparator == Comparator.LTE:
            return TruthValue.TRUE if observed <= expected else TruthValue.FALSE
        if comparator == Comparator.IN:
            return TruthValue.TRUE if observed in expected else TruthValue.FALSE
        if comparator == Comparator.NOT_IN:
            return TruthValue.TRUE if observed not in expected else TruthValue.FALSE
    except (TypeError, ValueError):
        return TruthValue.UNKNOWN
    raise ValueError(f"不支持的比较器: {comparator}")


def evaluate_calculated_numeric_value(predicate: AtomicPredicate, *, value: Fraction, unit: str | None):
    """Compare exact arithmetic without putting a synthetic value in a source field."""
    if not isinstance(value, Fraction):
        raise TypeError("计算结果须保留精确数值")
    if predicate.unit is not None and _canonical_unit(predicate.unit) != _canonical_unit(unit):
        return _result(TruthValue.UNKNOWN, "unit_mismatch")
    expected = predicate.value
    values = expected if isinstance(expected, list) else [expected]
    if predicate.comparator != Comparator.EXISTS:
        if any(isinstance(item, bool) or not isinstance(item, (int, float, Decimal))
               or not Decimal(str(item)).is_finite() for item in values):
            return _result(TruthValue.UNKNOWN, "repeat_numeric_threshold_unverified")
        exact = [Fraction(Decimal(str(item))) for item in values]
        expected = exact if isinstance(expected, list) else exact[0]
    return _result(compare_values(predicate.comparator, value, expected), observed_unit=unit)


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
    fact_type = f"{expression.predicate.subject}.{expression.predicate.attribute}"
    result = evaluate_time_constraint(
        constraint,
        event_value=fact.effective_date,
        anchor_value=context.anchor_dates.get(constraint.anchor_type),
        half_life_days=context.half_life_days.get(fact_type),
    )
    return result.model_copy(update={"used_fact_ids": [fact.fact_id]})


def evaluate_time_constraint(
    constraint: TimeConstraint,
    *,
    event_value: DateValue | None,
    anchor_value: DateValue | None,
    half_life_days: float | None = None,
) -> EvaluationResult:
    """Evaluate explicit dates without constructing a clinical fact or predicate."""
    if (
        event_value is None
        or event_value.value is None
        or anchor_value is None
        or anchor_value.value is None
    ):
        return _result(
            TruthValue.UNKNOWN,
            "date_or_anchor_missing",
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
            return _result(TruthValue.TRUE)
        if event_max < anchor_min or anchor_max < event_min:
            return _result(
                TruthValue.FALSE,
                "outside_time_window",
            )
        return _result(
            TruthValue.UNKNOWN,
            "ambiguous_partial_date",
        )
    if distance_max < 0:
        return _result(TruthValue.FALSE, "wrong_time_direction")
    if distance_min < 0 <= distance_max:
        return _result(TruthValue.UNKNOWN, "ambiguous_time_direction")

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
    pending_reasons: list[str] = []
    if constraint.half_life_multiplier is not None:
        if constraint.half_life_evidence is not None:
            duration = constraint.half_life_evidence.in_days(Decimal(str(constraint.half_life_multiplier)))
        elif half_life_days is not None:
            duration = Decimal(str(half_life_days)) * Decimal(str(constraint.half_life_multiplier))
        else:
            duration = None
        if duration is None or not duration.is_finite() or duration <= 0:
            pending_reasons.append("half_life_missing")
        elif constraint.half_life_evidence is not None:
            # Source PK durations measure elapsed time. Date-only endpoints bound
            # it by (earliest distance - 1, latest distance + 1), not midnight.
            if Decimal(distance_max + 1) <= duration:
                return _result(TruthValue.FALSE, "below_time_window")
            if Decimal(distance_min - 1) < duration:
                pending_reasons.append("half_life_time_precision_insufficient")
        else:
            lower_bound = max(lower_bound or 0, ceil(duration))
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
            return _result(TruthValue.FALSE, "below_time_window")
        if crosses_boundary:
            pending_reasons.append("ambiguous_time_window")
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
            return _result(TruthValue.FALSE, "above_time_window")
        if crosses_boundary:
            pending_reasons.append("ambiguous_time_window")
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
            )
        if lower_truth == TruthValue.UNKNOWN:
            pending_reasons.extend(partial_reason_codes)
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
            )
        if upper_truth == TruthValue.UNKNOWN:
            pending_reasons.extend(partial_reason_codes)
    if pending_reasons:
        return _result(TruthValue.UNKNOWN, *sorted(set(pending_reasons)))
    return _result(TruthValue.TRUE)


def evaluate_observed_value(
    predicate: AtomicPredicate, *, value: ScalarValue | None,
    unit: str | None, polarity: FactPolarity,
) -> EvaluationResult:
    """Value arithmetic only; callers own source, object and temporal selection."""
    if polarity == FactPolarity.UNKNOWN:
        return _result(TruthValue.UNKNOWN, "fact_polarity_unknown")
    if predicate.unit is not None and _canonical_unit(predicate.unit) != _canonical_unit(unit):
        return _result(TruthValue.UNKNOWN, "unit_mismatch", observed_value=value, observed_unit=unit)
    comparison = _compare(predicate, value)
    if polarity == FactPolarity.NEGATED:
        comparison = {
            TruthValue.TRUE: TruthValue.FALSE,
            TruthValue.FALSE: TruthValue.TRUE,
            TruthValue.UNKNOWN: TruthValue.UNKNOWN,
        }[comparison]
    return _result(comparison, observed_value=value, observed_unit=unit)


def _evaluate_atomic(expression: AtomicExpression, context: EvaluationContext,
                     fact_ids: Sequence[str] | None = None) -> EvaluationResult:
    predicate = expression.predicate
    if predicate.repeat_scheme is not None:
        return _result(TruthValue.UNKNOWN, "repeat_relation_unverified")
    if predicate.semantic_proposition is not None:
        return _result(TruthValue.UNKNOWN, "semantic_evidence_unverified")
    if predicate.occurrence_window is not None:
        return _result(TruthValue.UNKNOWN, "occurrence_scope_unverified")
    if predicate.prospective_window is not None or predicate.prospective_period is not None:
        return _result(TruthValue.UNKNOWN, "prospective_scope_unverified")
    policy = predicate.observation_policy
    if policy is not None and (policy.mode == "unresolved" or fact_ids is None):
        return _result(TruthValue.UNKNOWN, "observation_selection_unverified")
    fact_type = f"{predicate.subject}.{predicate.attribute}"
    # Legacy matching remains until the source-verified binding path is integrated.
    alias_types = context.predicate_fact_type_aliases.get(fact_type)
    if fact_ids is not None:
        matching = [fact for fact in context.facts if fact.fact_id in fact_ids]
    elif alias_types:
        matching = [fact for fact in context.facts if fact.fact_type in alias_types]
    else:
        matching = [fact for fact in context.facts if fact.fact_type == fact_type]
    if not matching:
        if fact_ids is not None and not predicate.requires_professional_judgment:
            # 双模型绑定的verified空选择：两道一致确认无对应事实。
            # 对排除条件返回FALSE=未触发；对入选条件返回FALSE=未满足。
            # 不是UNKNOWN——因为绑定已验证，不是"未核实"。
            return _result(
                TruthValue.FALSE,
                "verified_no_matching_fact",
                used_fact_ids=[],
                evidence_span_ids=[],
                observed_value=None,
                observed_unit=None,
            )
        reason = (
            "professional_judgment_unverified"
            if predicate.requires_professional_judgment
            else ("observation_unverified" if fact_ids is not None else "fact_not_observed")
        )
        return _result(TruthValue.UNKNOWN, reason)
    # Establish temporal membership before comparing values. Out-of-window
    # observations cannot create conflicts within this predicate's window.
    matching = sorted(matching, key=lambda fact: fact.fact_id)
    timed = [(fact, _evaluate_time(expression, fact, context)) for fact in matching]
    relevant = [(fact, result) for fact, result in timed if result.truth != TruthValue.FALSE]
    if not relevant:
        excluded_values = {(fact.value, _canonical_unit(fact.unit), fact.polarity) for fact, _ in timed}
        representative = timed[0][0] if len(excluded_values) == 1 else None
        return _result(
            TruthValue.UNKNOWN,
            "observation_out_of_window",
            *sorted({reason for _, result in timed for reason in result.reason_codes}),
            used_fact_ids=[fact.fact_id for fact, _ in timed],
            evidence_span_ids=sorted({span for fact, _ in timed for span in fact.evidence_span_ids}),
            observed_value=representative.value if representative else None,
            observed_unit=representative.unit if representative else None,
        )
    matching = [fact for fact, _ in relevant]
    unresolved_times = [result for _, result in relevant if result.truth == TruthValue.UNKNOWN]
    if unresolved_times:
        return _result(
            TruthValue.UNKNOWN,
            *sorted({reason for result in unresolved_times for reason in result.reason_codes}),
            used_fact_ids=[fact.fact_id for fact in matching],
            evidence_span_ids=sorted({span for fact in matching for span in fact.evidence_span_ids}),
        )
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
    if policy is not None and policy.mode in {"any", "all"} and not any(
        fact.conflict_group_id for fact in matching
    ):
        results = []
        for fact in matching:
            value_result = evaluate_observed_value(
                predicate, value=fact.value, unit=fact.unit, polarity=fact.polarity,
            )
            results.append(_result(
                value_result.truth, *value_result.reason_codes,
                used_fact_ids=[fact.fact_id], evidence_span_ids=fact.evidence_span_ids,
            ))
        return _evaluate_logical(
            LogicalOperator.ANY if policy.mode == "any" else LogicalOperator.ALL, results,
        )
    if len(observed_values) != 1 or any(fact.conflict_group_id for fact in matching):
        return _result(
            TruthValue.UNKNOWN,
            ("source_conflict" if any(fact.conflict_group_id for fact in matching)
             else "observation_selection_unverified"),
            used_fact_ids=[fact.fact_id for fact in matching],
            evidence_span_ids=[
                span_id for fact in matching for span_id in fact.evidence_span_ids
            ],
        )
    fact = matching[0]
    value_result = evaluate_observed_value(
        predicate, value=fact.value, unit=fact.unit, polarity=fact.polarity,
    )
    if "unit_mismatch" in value_result.reason_codes:
        return _result(
            TruthValue.UNKNOWN,
            "unit_mismatch",
            used_fact_ids=[fact.fact_id],
            observed_value=fact.value,
            observed_unit=fact.unit,
            evidence_span_ids=fact.evidence_span_ids,
        )
    return _result(
        value_result.truth,
        used_fact_ids=[fact.fact_id for fact in matching],
        observed_value=fact.value,
        observed_unit=fact.unit,
        evidence_span_ids=sorted({span for fact in matching for span in fact.evidence_span_ids}),
    )


def evaluate_expression(expression: RuleExpression, context: EvaluationContext) -> EvaluationResult:
    if expression.kind == "predicate":
        return _evaluate_atomic(expression, context)
    children = [evaluate_expression(child, context) for child in expression.children]
    return _evaluate_logical(expression.operator, children)


def _evaluate_bound_predicates(
    expressions: Sequence[RuleExpression], context: EvaluationContext, *,
    predicate_fact_ids: Mapping[str, Sequence[str]] | None = None,
    unverified_predicate_ids: frozenset[str] = frozenset(),
    missing_judgment_predicate_ids: frozenset[str] = frozenset(),
    proposition_evaluations: Mapping[str, EvaluationResult] | None = None,
    repeat_evaluations: Mapping[str, RepeatAtomEvaluation] | None = None,
    frequency_evaluations: Mapping[str, FrequencyAtomEvaluation] | None = None,
) -> dict[str, EvaluationResult]:
    """Calculate explicit selections when supplied; never fill their missing keys.

    Selections are not semantic proof. The calling publication boundary owns
    source qualification and correspondence verification. None retains the
    legacy category path; an empty selection for an atom does not use it.
    """
    atoms = [atom for expression in expressions for atom in _iter_atomic_expressions(expression)]
    selections = None
    if predicate_fact_ids is not None:
        expected = {atom.predicate.predicate_id for atom in atoms}
        if (not isinstance(predicate_fact_ids, Mapping)
                or len(expected) != len(atoms) or set(predicate_fact_ids) != expected):
            raise ValueError("对应清单须分别完整列出触发和例外条件")
        accepted = set(context.accepted_fact_ids)
        selections = {}
        for key, values in predicate_fact_ids.items():
            if (not isinstance(values, Sequence) or isinstance(values, (str, bytes))
                    or any(not isinstance(value, str) for value in values)
                    or len(values) != len(set(values))
                    or not set(values).issubset(accepted)):
                raise ValueError("对应清单含重复或不属于当前资料范围的事实")
            selections[key] = tuple(values)
    if unverified_predicate_ids and (
        selections is None
        or not unverified_predicate_ids <= set(selections)
        or any(selections[key] for key in unverified_predicate_ids)
    ):
        raise ValueError("尚未核实的条件只能对应明确的空资料选择")
    professional_ids = {atom.predicate.predicate_id for atom in atoms
                        if atom.predicate.requires_professional_judgment}
    if missing_judgment_predicate_ids and (
        selections is None or not missing_judgment_predicate_ids <= professional_ids
        or any(selections[key] for key in missing_judgment_predicate_ids)
    ):
        raise ValueError("未见书面判断只能用于已核实范围、明确空选择的对应判断条件")
    proposition_evaluations = dict(proposition_evaluations or {})
    semantic_ids = {atom.predicate.predicate_id for atom in atoms
                    if atom.predicate.semantic_proposition is not None}
    if proposition_evaluations:
        if selections is None or not set(proposition_evaluations) <= semantic_ids:
            raise ValueError("原文命题结果只能对应本次明确声明的正式条件")
        for key, value in proposition_evaluations.items():
            if (not isinstance(value, EvaluationResult)
                    or not set(value.used_fact_ids) <= set(selections[key])
                    or (key in unverified_predicate_ids and value.truth != TruthValue.UNKNOWN)):
                raise ValueError("原文命题结果不得绕过资料范围或未核实状态")
    repeat_evaluations = dict(repeat_evaluations or {})
    repeat_atoms = {atom.predicate.predicate_id: atom for atom in atoms if atom.predicate.repeat_scheme is not None}
    if repeat_evaluations:
        if (selections is None or not set(repeat_evaluations) <= set(repeat_atoms)
                or set(repeat_evaluations) & set(proposition_evaluations)):
            raise ValueError("复查求值必须单独对应方案明确规定的复查条件")
        context_hash = canonical_hash(context.model_dump(mode="json"))
        for key, item in repeat_evaluations.items():
            if (not isinstance(item, RepeatAtomEvaluation)
                    or item.context_sha256 != context_hash
                    or item.atom_sha256 != canonical_hash(repeat_atoms[key].model_dump(mode="json"))
                    or not set(item.source_fact_ids) <= set(context.accepted_fact_ids)
                    or set(item.result.used_fact_ids) != set(selections[key])
                    or (key in unverified_predicate_ids | missing_judgment_predicate_ids
                        and item.result.truth != TruthValue.UNKNOWN)):
                raise ValueError("复查求值不能跨越方案、来源或尚未核实的书面判断")
    frequency_evaluations = dict(frequency_evaluations or {})
    frequency_atoms = {atom.predicate.predicate_id: atom for atom in atoms
                       if atom.predicate.occurrence_window is not None
                       and atom.predicate.repeat_scheme is None
                       and not atom.predicate.requires_professional_judgment}
    if frequency_evaluations:
        if (selections is None or not set(frequency_evaluations) <= set(frequency_atoms)
                or set(frequency_evaluations) & (set(repeat_evaluations) | set(proposition_evaluations))):
            raise ValueError("频次求值须对应独立的发生次数条件，不能替代复查或书面判断")
        context_hash = canonical_hash(context.model_dump(mode="json"))
        for key, item in frequency_evaluations.items():
            if (not isinstance(item, FrequencyAtomEvaluation)
                    or item.context_sha256 != context_hash
                    or item.atom_sha256 != canonical_hash(frequency_atoms[key].model_dump(mode="json"))
                    or not set(item.source_fact_ids) <= set(context.accepted_fact_ids)
                    or set(item.result.used_fact_ids) != set(selections[key])
                    or (key in unverified_predicate_ids | missing_judgment_predicate_ids
                        and item.result.truth != TruthValue.UNKNOWN)):
                raise ValueError("频次计算不能跨越方案、原件或未核实状态")
    predicate_evaluations = {
        atom.predicate.predicate_id: (
            frequency_evaluations[atom.predicate.predicate_id].result
            if atom.predicate.predicate_id in frequency_evaluations else
            repeat_evaluations[atom.predicate.predicate_id].result
            if atom.predicate.predicate_id in repeat_evaluations else
            proposition_evaluations[atom.predicate.predicate_id]
            if atom.predicate.predicate_id in proposition_evaluations else
            _result(TruthValue.UNKNOWN, "professional_judgment_missing")
            if atom.predicate.predicate_id in missing_judgment_predicate_ids else
            _result(TruthValue.UNKNOWN, "professional_judgment_unverified"
                    if atom.predicate.requires_professional_judgment else "observation_unverified",
                    *(["repeat_relation_unverified"] if atom.predicate.repeat_scheme is not None else []))
            if atom.predicate.predicate_id in unverified_predicate_ids else _evaluate_atomic(
            atom, context,
            selections[atom.predicate.predicate_id] if selections is not None else None,
        )) for atom in atoms
    }

    return predicate_evaluations


def _combine_bound_expression(expression, predicate_evaluations):
    if expression.kind == "predicate":
        return predicate_evaluations[expression.predicate.predicate_id]
    return _evaluate_logical(expression.operator, [
        _combine_bound_expression(child, predicate_evaluations) for child in expression.children
    ])


def evaluate_bound_expression(
    expression: RuleExpression, context: EvaluationContext, *,
    predicate_fact_ids: Mapping[str, Sequence[str]],
    unverified_predicate_ids: frozenset[str] = frozenset(),
    missing_judgment_predicate_ids: frozenset[str] = frozenset(),
    proposition_evaluations: Mapping[str, EvaluationResult] | None = None,
    frequency_evaluations: Mapping[str, FrequencyAtomEvaluation] | None = None,
) -> EvaluationResult:
    """Evaluate a source-bound auxiliary tree without creating an eligibility rule."""
    if not isinstance(predicate_fact_ids, Mapping):
        raise ValueError("独立条件求值须逐项明确资料对应，不能按类别补选")
    results = _evaluate_bound_predicates(
        [expression], context, predicate_fact_ids=predicate_fact_ids,
        unverified_predicate_ids=unverified_predicate_ids,
        missing_judgment_predicate_ids=missing_judgment_predicate_ids,
        proposition_evaluations=proposition_evaluations,
        frequency_evaluations=frequency_evaluations,
    )
    return _combine_bound_expression(expression, results)


def evaluate_component(
    component: RuleComponent, context: EvaluationContext, *,
    predicate_fact_ids: Mapping[str, Sequence[str]] | None = None,
    unverified_predicate_ids: frozenset[str] = frozenset(),
    missing_judgment_predicate_ids: frozenset[str] = frozenset(),
    proposition_evaluations: Mapping[str, EvaluationResult] | None = None,
    repeat_evaluations: Mapping[str, RepeatAtomEvaluation] | None = None,
    frequency_evaluations: Mapping[str, FrequencyAtomEvaluation] | None = None,
) -> ComponentEvaluation:
    """Keep eligibility composition limited to the original trigger and exception."""
    expressions = [component.expression]
    if component.exception_expression is not None:
        expressions.append(component.exception_expression)
    predicate_evaluations = _evaluate_bound_predicates(
        expressions, context, predicate_fact_ids=predicate_fact_ids,
        unverified_predicate_ids=unverified_predicate_ids,
        missing_judgment_predicate_ids=missing_judgment_predicate_ids,
        proposition_evaluations=proposition_evaluations,
        repeat_evaluations=repeat_evaluations,
        frequency_evaluations=frequency_evaluations,
    )

    return ComponentEvaluation(
        applicable=TruthValue.TRUE,
        trigger=_combine_bound_expression(component.expression, predicate_evaluations),
        exception=(
            _combine_bound_expression(component.exception_expression, predicate_evaluations)
            if component.exception_expression is not None
            else None
        ),
        predicate_evaluations=predicate_evaluations,
    )


def evaluate_bound_component_experiment(
    component: RuleComponent, context: EvaluationContext, *,
    component_sha256: str, context_sha256: str,
    predicate_fact_ids: Mapping[str, Sequence[str]],
) -> ComponentEvaluation:
    """Isolated consumer experiment, not a binding verifier or production route.

    The caller must establish semantic/source validity before eventual adoption.
    This entry point only proves that explicit selections can use the existing
    numerical, temporal and boolean evaluator without category fallback.
    """
    if component_sha256 != canonical_hash(component.model_dump(mode="json")):
        raise ValueError("审核条件已变化，不能沿用对应清单")
    if context_sha256 != canonical_hash(context.model_dump(mode="json")):
        raise ValueError("审核节点或事实已变化，不能沿用对应清单")
    return evaluate_component(component, context, predicate_fact_ids=predicate_fact_ids)


def _iter_atomic_expressions(expression: RuleExpression):
    if expression.kind == "predicate":
        yield expression
        return
    for child in expression.children:
        yield from _iter_atomic_expressions(child)
