"""Numeric repeat aggregates remain calculations, never fabricated source facts."""
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from app.domain.contracts.enums import FactPolarity
from app.domain.contracts.repeat_scheme import RepeatScheme
from app.domain.expression import EvaluationContext
from app.domain.publication import canonical_hash
from app.domain.repeat_result_selection import RepeatResultSelection


@dataclass(frozen=True)
class RepeatNumericResult:
    graph_sha256: str
    scheme_sha256: str
    supplied_scope_sha256: str
    context_sha256: str
    group_ids: tuple[str, ...]
    fact_ids: tuple[str, ...]
    value: Fraction | None = None
    unit: str | None = None
    reason_codes: tuple[str, ...] = ()

    def as_material(self) -> dict:
        return {
            "version": "repeat-numeric-result/v1",
            "graph_sha256": self.graph_sha256,
            "scheme_sha256": self.scheme_sha256,
            "scope": "supplied_facts_only", "supplied_scope_sha256": self.supplied_scope_sha256,
            "context_sha256": self.context_sha256,
            "group_ids": list(self.group_ids), "fact_ids": list(self.fact_ids),
            "exact_value": (None if self.value is None else {
                "numerator": str(self.value.numerator), "denominator": str(self.value.denominator),
            }),
            "unit": self.unit, "reason_codes": list(self.reason_codes),
            "replacement_authorized": False,
        }


def calculate_repeat_numeric_result(
    selection: RepeatResultSelection, graph: dict, context: EvaluationContext, *,
    scheme: RepeatScheme, qualified_value_fact_ids: frozenset[str],
    unit_required: bool = True,
) -> RepeatNumericResult:
    """Use all qualified records of each acquisition and collapse equal values.

    The caller supplies source-qualified value identities for the exact rule.
    This does not authorize replacement, infer a missing value, convert units,
    or turn a computed aggregate into a ClinicalFact. Exact rational output
    avoids rounding a mean across a later clinical threshold. Semantic all/any belongs
    to the bound proposition evaluator, not numeric truthiness.
    """
    if graph.get("graph_sha256") != canonical_hash({
        key: value for key, value in graph.items() if key != "graph_sha256"
    }):
        raise ValueError("检查对应记录已变化，不能继续合并结果")
    if selection.graph_sha256 != graph["graph_sha256"]:
        raise ValueError("结果选择与检查对应记录不是同一版本")
    if selection.scheme_sha256 != canonical_hash(scheme.model_dump(mode="json")):
        raise ValueError("结果选择与本次方案规定不是同一版本")
    groups = {item["group_id"]: item["fact_ids"] for item in graph["acquisition_groups"]}
    selected = selection.selected_group_ids
    if len(set(selected)) != len(selected) or not set(selected) <= groups.keys():
        raise ValueError("合并结果须使用已核实且不重复的检查")
    fact_ids = tuple(sorted({key for group_id in selected for key in groups[group_id]}))

    def result(**kwargs):
        return RepeatNumericResult(
            graph_sha256=selection.graph_sha256, scheme_sha256=selection.scheme_sha256,
            supplied_scope_sha256=selection.supplied_scope_sha256,
            context_sha256=canonical_hash(context.model_dump(mode="json")),
            group_ids=selected, fact_ids=fact_ids, **kwargs,
        )

    def unresolved(*reasons):
        return result(reason_codes=tuple(sorted(set(reasons))))

    if selection.reason_codes or graph["structural_reasons"]:
        return unresolved(*selection.reason_codes, *graph["structural_reasons"])
    if not selected:
        return unresolved("repeat_result_missing")
    operation = selection.combination
    if operation not in {None, "sum", "mean", "minimum", "maximum"}:
        return unresolved("repeat_result_requires_proposition_calculation")
    if operation is None and len(selected) != 1:
        return unresolved("repeat_result_combination_unverified")
    facts = {item.fact_id: item for item in context.facts}
    if not set(fact_ids) <= qualified_value_fact_ids or not set(fact_ids) <= facts.keys():
        return unresolved("repeat_result_value_unverified")
    values, units = [], set()
    for group_id in selected:
        group_values = set()
        for fact_id in groups[group_id]:
            fact = facts[fact_id]
            if fact.conflict_group_id:
                return unresolved("source_conflict")
            if fact.polarity != FactPolarity.AFFIRMED:
                return unresolved("repeat_result_polarity_unverified")
            if isinstance(fact.value, bool) or not isinstance(fact.value, (int, float, Decimal)):
                return unresolved("repeat_result_numeric_value_missing")
            value = Decimal(str(fact.value))
            if not value.is_finite():
                return unresolved("repeat_result_numeric_value_missing")
            if unit_required and (not fact.unit or not fact.unit.strip()):
                return unresolved("repeat_result_unit_unverified")
            group_values.add((Fraction(value), fact.unit))
        if len(group_values) != 1:
            return unresolved("repeat_same_acquisition_value_conflict")
        value, unit = next(iter(group_values))
        values.append(value)
        units.add(unit)
    if len(units) != 1:
        return unresolved("repeat_result_unit_unverified")
    if operation in {"sum", "mean"}:
        value = sum(values, Fraction(0))
        if operation == "mean":
            value /= len(values)
    elif operation == "minimum":
        value = min(values)
    elif operation == "maximum":
        value = max(values)
    else:
        value = values[0]
    return result(value=value, unit=next(iter(units)))
