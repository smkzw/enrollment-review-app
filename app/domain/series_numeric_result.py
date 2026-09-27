"""Series numeric aggregates remain calculations, never fabricated source facts."""
from collections.abc import Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Literal

from app.domain.contracts.evidence import ClinicalFact
from app.domain.repeat_numeric_result import aggregate_numeric_acquisitions

_OPERATION_ALIASES = {
    "sum": "sum",
    "mean": "mean",
    "average": "mean",
    "minimum": "minimum",
    "min": "minimum",
    "maximum": "maximum",
    "max": "maximum",
}


@dataclass(frozen=True)
class SeriesNumericResult:
    """Deterministic series aggregate; caller retains source and eligibility duty."""

    operation: str | None = None
    declared_input_count: int = 0
    present_input_count: int = 0
    allowed_missing_count: int = 0
    missing_count: int = 0
    missing_policy: str = "not_specified"
    source_range_complete: bool = False
    fact_ids: tuple[str, ...] = ()
    value: Fraction | None = None
    unit: str | None = None
    reason_codes: tuple[str, ...] = ()
    replacement_authorized: bool = field(default=False, init=False)

    def as_material(self) -> dict:
        return {
            "version": "series-numeric-result/v1",
            "operation": self.operation,
            "declared_input_count": self.declared_input_count,
            "present_input_count": self.present_input_count,
            "allowed_missing_count": self.allowed_missing_count,
            "missing_count": self.missing_count,
            "missing_policy": self.missing_policy,
            "source_range_complete": self.source_range_complete,
            "fact_ids": list(self.fact_ids),
            "exact_value": (
                None
                if self.value is None
                else {
                    "numerator": str(self.value.numerator),
                    "denominator": str(self.value.denominator),
                }
            ),
            "unit": self.unit,
            "reason_codes": list(self.reason_codes),
            "replacement_authorized": False,
            "eligible_for_rule_evaluation": False,
        }


def calculate_series_numeric_result(
    groups: Sequence[Sequence[ClinicalFact]],
    *,
    operation: str | None,
    declared_input_count: int,
    allowed_missing_count: int = 0,
    missing_policy: Literal["exclude", "impute", "not_specified", "unresolved"] = "not_specified",
    source_range_complete: bool,
    unit_required: bool = True,
) -> SeriesNumericResult:
    """Aggregate verified independent acquisition groups for a numeric series.

    The caller proves source qualification, eligibility, declared cardinality,
    allowed absence, and whether the searched source range is complete. This
    kernel does not invent missing values, convert units, authorize replacement,
    or emit a ClinicalFact.
    """
    if type(declared_input_count) is not int or declared_input_count < 0:
        raise ValueError("序列计算须声明非负的输入个数")
    if type(allowed_missing_count) is not int or allowed_missing_count < 0:
        raise ValueError("序列计算的允许缺失数须为非负整数")
    if allowed_missing_count > declared_input_count:
        raise ValueError("允许缺失数不能超过声明输入数")
    if type(source_range_complete) is not bool:
        raise ValueError("来源范围完整性须由本次原件核对给出")
    if missing_policy not in {"exclude", "impute", "not_specified", "unresolved"}:
        raise ValueError("缺失值处理方式须来自已核方案")
    if not isinstance(groups, Sequence) or isinstance(groups, (str, bytes)):
        raise ValueError("序列计算须使用已核独立采集分组")
    if any(
        not isinstance(group, Sequence) or isinstance(group, (str, bytes))
        or any(not isinstance(fact, ClinicalFact) for fact in group)
        for group in groups
    ):
        raise ValueError("当前序列算术试验只接受旧版事实材料，不能直接用于正式审核事实")

    present_input_count = len(groups)
    missing_count = max(declared_input_count - present_input_count, 0)
    fact_ids = tuple(
        sorted({fact.fact_id for group in groups for fact in group})
    )
    resolved_operation = None if operation is None else _OPERATION_ALIASES.get(operation)

    def result(**kwargs) -> SeriesNumericResult:
        return SeriesNumericResult(
            operation=resolved_operation if operation is not None else None,
            declared_input_count=declared_input_count,
            present_input_count=present_input_count,
            allowed_missing_count=allowed_missing_count,
            missing_count=missing_count,
            missing_policy=missing_policy,
            source_range_complete=source_range_complete,
            fact_ids=fact_ids,
            **kwargs,
        )

    def unresolved(*reasons: str) -> SeriesNumericResult:
        return result(reason_codes=tuple(sorted(set(reasons))))

    if not source_range_complete:
        return unresolved("series_source_range_incomplete")
    if operation is not None and resolved_operation is None:
        return unresolved("series_operation_unverified")
    if present_input_count > declared_input_count:
        return unresolved("series_input_count_exceeded")
    if missing_count > allowed_missing_count:
        return unresolved("series_missing_exceeds_allowed")
    if present_input_count == 0:
        return unresolved("series_result_missing")
    if missing_count and missing_policy == "impute":
        return unresolved("series_imputation_unsupported")
    if missing_count and missing_policy != "exclude":
        return unresolved("series_missing_policy_unverified")
    if resolved_operation is None and present_input_count != 1:
        return unresolved("series_operation_unverified")

    value, unit, reasons = aggregate_numeric_acquisitions(
        groups,
        operation=resolved_operation,
        unit_required=unit_required,
    )
    if reasons:
        return unresolved(*reasons)
    # This kernel has no source-backed acquisition membership or policy-scope
    # qualification yet. A valid arithmetic result is not an eligibility input.
    return result(
        value=value,
        unit=unit,
        reason_codes=("series_source_qualification_unverified",),
    )
