"""Count bounds from already-qualified evidence, not the number of source rows."""
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from app.domain.contracts.enums import TruthValue
from app.domain.expression import EvaluationResult


@dataclass(frozen=True)
class OccurrenceCountBounds:
    lower: int
    upper: int | None

    def __post_init__(self):
        if type(self.lower) is not int or self.lower < 0:
            raise ValueError("已证实的次数下界须为非负整数")
        if self.upper is not None and (
            type(self.upper) is not int or self.upper < self.lower
        ):
            raise ValueError("次数上界不得低于下界；相互矛盾的来源不能合成区间")


def intersect_count_bounds(bounds: list[OccurrenceCountBounds]) -> OccurrenceCountBounds | None:
    """Only caller-verified same-subject, same-event, same-period constraints may intersect.

    None means contradictory constraints, never an empty set of evidence.
    """
    if not bounds:
        raise ValueError("没有已核实依据时不能合成次数")
    lower = max(item.lower for item in bounds)
    finite = [item.upper for item in bounds if item.upper is not None]
    upper = min(finite) if finite else None
    if upper is not None and upper < lower:
        return None
    return OccurrenceCountBounds(lower, upper)


def evaluate_count_bounds(
    bounds: OccurrenceCountBounds,
    *,
    comparator: Literal["eq", "ne", "gt", "gte", "lt", "lte"],
    threshold: int | float,
) -> EvaluationResult:
    """Return a truth only when every count in the verified interval has that truth."""
    if type(threshold) not in {int, float}:
        raise ValueError("次数阈值须为方案明确给出的数值")
    try:
        target = Fraction(str(threshold))
    except (ValueError, OverflowError) as exc:
        raise ValueError("次数阈值须为有限数值") from exc
    lower, upper = bounds.lower, bounds.upper
    if comparator == "gte":
        positive, negative = lower >= target, upper is not None and upper < target
    elif comparator == "gt":
        positive, negative = lower > target, upper is not None and upper <= target
    elif comparator == "lte":
        positive, negative = upper is not None and upper <= target, lower > target
    elif comparator == "lt":
        positive, negative = upper is not None and upper < target, lower >= target
    elif comparator in {"eq", "ne"}:
        equal = upper is not None and lower == upper == target
        impossible = target.denominator != 1 or target < lower or (upper is not None and target > upper)
        positive, negative = (equal, impossible) if comparator == "eq" else (impossible, equal)
    else:
        raise ValueError("频次比较方式尚不支持，不能改用其他方向")
    truth = TruthValue.TRUE if positive else TruthValue.FALSE if negative else TruthValue.UNKNOWN
    return EvaluationResult(
        truth=truth,
        reason_codes=["occurrence_count_bounds_inconclusive"] if truth == TruthValue.UNKNOWN else [],
    )
