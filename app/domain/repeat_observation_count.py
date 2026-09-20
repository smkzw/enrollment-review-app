"""Count qualified acquisitions, not documents, pages, analytes or fact rows."""
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.domain.contracts.enums import TruthValue
from app.domain.contracts.repeat_scheme import RepeatScheme
from app.domain.expression import EvaluationResult


@dataclass(frozen=True)
class RepeatCountCalculation:
    observed_repeat_group_ids: tuple[str, ...]
    scope_complete: bool
    result: EvaluationResult


def evaluate_repeat_count(
    scheme: RepeatScheme, *, repeat_group_ids: Sequence[str],
    qualified_scope: Literal["per_initial_acquisition", "per_current_episode"],
    scope_complete: bool,
) -> RepeatCountCalculation:
    """Source qualification and scope membership are caller-owned prerequisites.

    A partial set can establish an exceeded maximum, never compliance with it.
    An undeclared count constraint says nothing about permission or result use.
    """
    if (not isinstance(repeat_group_ids, Sequence) or isinstance(repeat_group_ids, (str, bytes))
            or any(not isinstance(item, str) or not item.strip() for item in repeat_group_ids)
            or len(set(repeat_group_ids)) != len(repeat_group_ids)
            or type(scope_complete) is not bool
            or qualified_scope not in {"per_initial_acquisition", "per_current_episode"}):
        raise ValueError("复查次数须按已核实的独立检查及明确范围计算，不能按资料条数累加")
    if scheme.count_status == "not_specified":
        result = EvaluationResult(truth=TruthValue.TRUE, reason_codes=["repeat_count_not_specified"])
    elif (scheme.count_status == "unresolved" or scheme.count_scope != qualified_scope):
        result = EvaluationResult(truth=TruthValue.UNKNOWN, reason_codes=["repeat_count_scope_unverified"])
    elif len(repeat_group_ids) > scheme.maximum_repeats:
        result = EvaluationResult(truth=TruthValue.FALSE, reason_codes=["repeat_count_exceeded"])
    elif not scope_complete:
        result = EvaluationResult(truth=TruthValue.UNKNOWN, reason_codes=["repeat_count_coverage_incomplete"])
    else:
        result = EvaluationResult(truth=TruthValue.TRUE)
    return RepeatCountCalculation(tuple(sorted(repeat_group_ids)), scope_complete, result)
