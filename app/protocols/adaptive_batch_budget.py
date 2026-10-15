"""Adaptive token/output-budget batching for protocol-control discovery.

This module is intentionally project-agnostic. It never reads protocol codes,
disease names, drug names, or fixed protocol/package identities. Callers supply
ordered structure units; packing preserves source order and never drops coverage.

Performance contract (Phase 5 control discovery):

- Prefer input-token + output-budget adaptive packs over fixed unit counts.
- Preserve exact source coverage without project-specific clinical rules.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.contracts.protocol_controls import ProtocolStructureUnit

__all__ = [
    "AdaptiveBatchBudget",
    "AdaptiveBatchPack",
    "AdaptiveBatchPlanningError",
    "default_discovery_batch_budget",
    "estimate_text_tokens",
    "estimate_unit_tokens",
    "pack_structure_units_by_budget",
]

# Conservative mixed CJK/Latin heuristic: lower divisor => higher token estimate
# => smaller packs. Tunable via AdaptiveBatchBudget.chars_per_token.
_DEFAULT_CHARS_PER_TOKEN = 1.2
_DEFAULT_PER_UNIT_JSON_OVERHEAD_CHARS = 180


class AdaptiveBatchPlanningError(ValueError):
    """Invalid adaptive batch budget or packing input."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class AdaptiveBatchBudget:
    """Input/output token budget used to size adaptive discovery/deep packs."""

    max_input_tokens: int = 16000
    max_output_tokens: int = 8192
    output_tokens_per_unit: int = 280
    template_overhead_tokens: int = 3500
    chars_per_token: float = _DEFAULT_CHARS_PER_TOKEN
    max_units_hard_cap: int = 24
    min_units: int = 1
    per_unit_json_overhead_chars: int = _DEFAULT_PER_UNIT_JSON_OVERHEAD_CHARS

    def validate(self) -> None:
        if self.max_input_tokens < 1:
            raise AdaptiveBatchPlanningError(
                "input_budget_invalid",
                "max_input_tokens 必须为正整数。",
            )
        if self.max_output_tokens < 1:
            raise AdaptiveBatchPlanningError(
                "output_budget_invalid",
                "max_output_tokens 必须为正整数。",
            )
        if self.output_tokens_per_unit < 1:
            raise AdaptiveBatchPlanningError(
                "output_per_unit_invalid",
                "output_tokens_per_unit 必须为正整数。",
            )
        if self.template_overhead_tokens < 0:
            raise AdaptiveBatchPlanningError(
                "template_overhead_invalid",
                "template_overhead_tokens 不能为负数。",
            )
        if self.chars_per_token <= 0:
            raise AdaptiveBatchPlanningError(
                "chars_per_token_invalid",
                "chars_per_token 必须为正数。",
            )
        if self.max_units_hard_cap < 1:
            raise AdaptiveBatchPlanningError(
                "unit_cap_invalid",
                "max_units_hard_cap 必须为正整数。",
            )
        if self.min_units < 1:
            raise AdaptiveBatchPlanningError(
                "min_units_invalid",
                "min_units 必须为正整数。",
            )
        if self.min_units > self.max_units_hard_cap:
            raise AdaptiveBatchPlanningError(
                "min_units_exceed_cap",
                "min_units 不得超过 max_units_hard_cap。",
            )
        if self.per_unit_json_overhead_chars < 0:
            raise AdaptiveBatchPlanningError(
                "unit_overhead_invalid",
                "per_unit_json_overhead_chars 不能为负数。",
            )
        if self.template_overhead_tokens >= self.max_input_tokens:
            raise AdaptiveBatchPlanningError(
                "template_overhead_too_large",
                "template_overhead_tokens 必须小于 max_input_tokens。",
            )


@dataclass(frozen=True)
class AdaptiveBatchPack:
    """One adaptive pack with token estimates; over_budget only for unavoidable singles."""

    owned_units: tuple[ProtocolStructureUnit, ...]
    context_units: tuple[ProtocolStructureUnit, ...]
    estimated_input_tokens: int
    estimated_output_tokens: int
    over_budget: bool = False


def default_discovery_batch_budget(
    *,
    max_input_tokens: int | None = None,
    max_output_tokens: int | None = None,
    output_tokens_per_unit: int | None = None,
    template_overhead_tokens: int | None = None,
    chars_per_token: float | None = None,
    max_units_hard_cap: int | None = None,
) -> AdaptiveBatchBudget:
    """Build the default discovery budget; all knobs remain caller-overridable."""

    budget = AdaptiveBatchBudget(
        max_input_tokens=(
            max_input_tokens
            if max_input_tokens is not None
            else AdaptiveBatchBudget.max_input_tokens
        ),
        max_output_tokens=(
            max_output_tokens
            if max_output_tokens is not None
            else AdaptiveBatchBudget.max_output_tokens
        ),
        output_tokens_per_unit=(
            output_tokens_per_unit
            if output_tokens_per_unit is not None
            else AdaptiveBatchBudget.output_tokens_per_unit
        ),
        template_overhead_tokens=(
            template_overhead_tokens
            if template_overhead_tokens is not None
            else AdaptiveBatchBudget.template_overhead_tokens
        ),
        chars_per_token=(
            chars_per_token
            if chars_per_token is not None
            else AdaptiveBatchBudget.chars_per_token
        ),
        max_units_hard_cap=(
            max_units_hard_cap
            if max_units_hard_cap is not None
            else AdaptiveBatchBudget.max_units_hard_cap
        ),
    )
    budget.validate()
    return budget


def estimate_text_tokens(text: str, *, chars_per_token: float = _DEFAULT_CHARS_PER_TOKEN) -> int:
    """Estimate tokens from character length; never uses project-specific tables."""

    if chars_per_token <= 0:
        raise AdaptiveBatchPlanningError(
            "chars_per_token_invalid",
            "chars_per_token 必须为正数。",
        )
    if not text:
        return 0
    return max(1, math.ceil(len(text) / chars_per_token))


def estimate_unit_tokens(
    unit: ProtocolStructureUnit,
    *,
    chars_per_token: float = _DEFAULT_CHARS_PER_TOKEN,
    per_unit_json_overhead_chars: int = _DEFAULT_PER_UNIT_JSON_OVERHEAD_CHARS,
) -> int:
    """Estimate one structure unit's contribution to the serialized discovery input."""

    # Stable, schema-like payload estimate without importing prompt templates.
    payload = {
        "structure_unit_id": unit.structure_unit_id,
        "source_ref": unit.source_ref,
        "member_source_refs": list(unit.member_source_refs),
        "source_span_ids": list(unit.source_span_ids),
        "unit_kind": unit.unit_kind,
        "heading_path": list(unit.heading_path),
        "source_order": unit.source_order,
        "excerpt": unit.excerpt,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return estimate_text_tokens(
        encoded + ("x" * max(0, per_unit_json_overhead_chars)),
        chars_per_token=chars_per_token,
    )


def _context_for_index(
    run: Sequence[ProtocolStructureUnit],
    *,
    start: int,
    end: int,
    context_radius: int,
) -> tuple[ProtocolStructureUnit, ...]:
    if context_radius <= 0:
        return ()
    before = list(run[max(0, start - context_radius) : start])
    after = list(run[end : min(len(run), end + context_radius)])
    return tuple(before + after)


def _estimate_pack_tokens(
    owned: Sequence[ProtocolStructureUnit],
    context: Sequence[ProtocolStructureUnit],
    budget: AdaptiveBatchBudget,
) -> tuple[int, int]:
    unit_tokens = sum(
        estimate_unit_tokens(
            unit,
            chars_per_token=budget.chars_per_token,
            per_unit_json_overhead_chars=budget.per_unit_json_overhead_chars,
        )
        for unit in (*owned, *context)
    )
    input_tokens = budget.template_overhead_tokens + unit_tokens
    output_tokens = budget.output_tokens_per_unit * len(owned)
    return input_tokens, output_tokens


def pack_structure_units_by_budget(
    units: Sequence[ProtocolStructureUnit],
    *,
    budget: AdaptiveBatchBudget,
    context_radius: int = 1,
    group_by_heading: bool = True,
) -> tuple[AdaptiveBatchPack, ...]:
    """Pack units under input/output budgets while preserving source order coverage.

    When a single unit alone exceeds the budget, it is still emitted as its own
    pack with ``over_budget=True`` so coverage is never dropped.
    """

    budget.validate()
    if context_radius < 0:
        raise AdaptiveBatchPlanningError(
            "context_radius_invalid",
            "context_radius 不能为负数。",
        )
    if not units:
        raise AdaptiveBatchPlanningError(
            "units_empty",
            "自适应分包不能在空结构单元清单上运行。",
        )

    ordered = tuple(sorted(units, key=lambda unit: (unit.source_order, unit.structure_unit_id)))
    if group_by_heading:
        runs: list[list[ProtocolStructureUnit]] = []
        for unit in ordered:
            heading = tuple(unit.heading_path)
            if not runs or tuple(runs[-1][0].heading_path) != heading:
                runs.append([])
            runs[-1].append(unit)
        groups: tuple[tuple[ProtocolStructureUnit, ...], ...] = tuple(
            tuple(run) for run in runs
        )
    else:
        groups = (ordered,)

    packs: list[AdaptiveBatchPack] = []
    for run in groups:
        index = 0
        while index < len(run):
            owned: list[ProtocolStructureUnit] = []
            accepted_input = 0
            accepted_output = 0
            while index + len(owned) < len(run) and len(owned) < budget.max_units_hard_cap:
                candidate = list(owned) + [run[index + len(owned)]]
                end = index + len(candidate)
                context = _context_for_index(
                    run,
                    start=index,
                    end=end,
                    context_radius=context_radius,
                )
                input_tokens, output_tokens = _estimate_pack_tokens(
                    candidate,
                    context,
                    budget,
                )
                exceeds_input = input_tokens > budget.max_input_tokens
                exceeds_output = output_tokens > budget.max_output_tokens
                if owned and (exceeds_input or exceeds_output):
                    break
                owned = candidate
                accepted_input = input_tokens
                accepted_output = output_tokens
                if exceeds_input or exceeds_output:
                    # First unit alone is over budget; emit and continue.
                    break
            if not owned:
                raise AdaptiveBatchPlanningError(
                    "packing_failed",
                    "自适应分包未能分配任何结构单元。",
                )
            end = index + len(owned)
            context = _context_for_index(
                run,
                start=index,
                end=end,
                context_radius=context_radius,
            )
            over_budget = (
                accepted_input > budget.max_input_tokens
                or accepted_output > budget.max_output_tokens
            )
            packs.append(
                AdaptiveBatchPack(
                    owned_units=tuple(owned),
                    context_units=context,
                    estimated_input_tokens=accepted_input,
                    estimated_output_tokens=accepted_output,
                    over_budget=over_budget,
                )
            )
            index = end

    covered = [unit.structure_unit_id for pack in packs for unit in pack.owned_units]
    expected = [unit.structure_unit_id for unit in ordered]
    if covered != expected:
        raise AdaptiveBatchPlanningError(
            "coverage_drift",
            "自适应分包必须按原文顺序恰好覆盖全部结构单元。",
        )
    return tuple(packs)

