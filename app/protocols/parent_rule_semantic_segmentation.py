"""Conservative structural segmentation for oversized official parent rules."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Sequence

from app.domain.contracts.protocol_ingestion import FrozenCatalogItem


@dataclass(frozen=True)
class ParentRuleSegment:
    parent_official_code: str
    segment_id: str
    source_span_ids: tuple[str, ...]
    body_source_span_ids: tuple[str, ...]


@dataclass(frozen=True)
class ParentRuleSegmentPlan:
    parent_official_code: str
    segments: tuple[ParentRuleSegment, ...]


@dataclass(frozen=True)
class ParentSegmentationThresholds:
    enabled: bool = True
    soft_input_tokens: int = 8_000
    min_source_spans: int = 4
    min_obligations: int = 3
    max_concurrency: int = 2
    # Soft ceiling for packing adjacent closed sibling bodies that share the
    # same active qualifier stack. <=0 disables the token ceiling.
    segment_soft_tokens: int = 3_500
    # Hard cap on closed body units packed into one segment. <=0 disables the
    # unit ceiling. Enforced together with segment_soft_tokens.
    max_units_per_segment: int = 3


@dataclass(frozen=True)
class _ClosedUnit:
    qualifier_span_ids: tuple[str, ...]
    body_span_ids: tuple[str, ...]
    body_text: str


# Logical scopes that must stay fail-closed when open.
_LOGICAL_OPENING = "（("
_LOGICAL_CLOSING = "）)"
# Square/black brackets are treated as citation/layout punctuation only and do
# not participate in logical open-scope decisions.
_LEADING_BINDER = re.compile(r"^(?:且|并且|同时|以及|或|或者|除外|除非|但(?:不)?)")
_ENUMERATION = re.compile(r"^\s*(?:[（(]?\d+[）).、]|[一二三四五六七八九十]+[、.])")
_DEFAULT_CHARS_PER_TOKEN = 2.0


def clamp_parent_segment_concurrency(value: int, *, hard_cap: int = 3) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        return 2
    return max(1, min(value, hard_cap))


def _source_texts(item: FrozenCatalogItem, source_materials: Sequence[Any]) -> list[str]:
    material_text = {
        str(material.source_span_id): str(material.text).strip()
        for material in source_materials
    }
    return [
        (item.source_excerpts[index] or material_text.get(span_id, "")).strip()
        if index < len(item.source_excerpts)
        else material_text.get(span_id, "")
        for index, span_id in enumerate(item.source_span_ids)
    ]


def _logical_balanced(text: str) -> bool:
    """Round-parenthesis balance only; citation brackets are ignored."""

    for left, right in zip(_LOGICAL_OPENING, _LOGICAL_CLOSING, strict=True):
        depth = 0
        for char in text:
            if char == left:
                depth += 1
            elif char == right:
                if depth == 0:
                    return False
                depth -= 1
        if depth:
            return False
    return True


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / _DEFAULT_CHARS_PER_TOKEN))


def _is_qualifier(text: str) -> bool:
    stripped = text.strip()
    return (
        bool(stripped)
        and stripped.endswith(("：", ":"))
        and _logical_balanced(stripped)
    )


def _looks_continuation(text: str, *, previous: str) -> bool:
    """Project-neutral continuation shape; never glue a new sibling list item."""

    stripped = text.strip()
    if not stripped:
        return False
    first = stripped[0]
    if first in "）)":
        return True
    if first.isascii() and first.islower():
        return True
    if first in "，、；;,":
        return True
    previous_stripped = previous.strip()
    if not previous_stripped or _logical_balanced(previous_stripped):
        return False
    # Truncated mid-token English/Latin residue may continue on the next span.
    if previous_stripped[-1].isascii() and previous_stripped[-1].isalnum():
        return first.isascii() and (first.islower() or first.isalnum())
    return False


def _unit_closed(text: str, *, under_colon_list: bool) -> bool:
    stripped = text.strip()
    if (
        not stripped
        or not _logical_balanced(stripped)
        or _LEADING_BINDER.match(stripped)
        or _is_qualifier(stripped)
    ):
        return False
    if stripped.endswith(("。", ";", "；")) or bool(_ENUMERATION.match(stripped)):
        return True
    if not under_colon_list:
        return False
    # Colon-introduced sibling list item: logically balanced, non-qualifier,
    # not a continuation residue. Terminators are common but not required.
    return not _looks_continuation(stripped, previous="")


def _push_qualifier(
    stack: list[tuple[str, str]],
    *,
    span_id: str,
    text: str,
    bodies_seen_since_qualifier: bool,
) -> None:
    """Update the qualifier stack by frozen structural order."""

    if not stack:
        # First qualifier in the parent is the root.
        stack.append((span_id, text))
        return
    if not bodies_seen_since_qualifier:
        # Consecutive qualifier headers before a body extend the stack.
        stack.append((span_id, text))
        return
    # A qualifier after bodies begins/replaces a nested branch under the root.
    root = stack[0]
    stack[:] = [root, (span_id, text)]


def _collect_closed_units(
    span_ids: Sequence[str],
    texts: Sequence[str],
) -> list[_ClosedUnit] | None:
    stack: list[tuple[str, str]] = []
    units: list[_ClosedUnit] = []
    index = 0
    total = len(span_ids)
    bodies_seen_since_qualifier = False

    while index < total:
        span_id = span_ids[index]
        text = texts[index]
        if not text:
            return None
        if _is_qualifier(text):
            _push_qualifier(
                stack,
                span_id=span_id,
                text=text,
                bodies_seen_since_qualifier=bodies_seen_since_qualifier,
            )
            bodies_seen_since_qualifier = False
            index += 1
            continue

        under_colon_list = bool(stack)
        body_span_ids = [span_id]
        combined = text
        cursor = index + 1
        while not _logical_balanced(combined):
            if cursor >= total:
                return None
            next_span_id = span_ids[cursor]
            next_text = texts[cursor]
            if not next_text:
                return None
            if _is_qualifier(next_text):
                return None
            if _unit_closed(next_text, under_colon_list=under_colon_list) and not (
                _looks_continuation(next_text, previous=combined)
            ):
                # New closed sibling / list item cannot close an open logical scope.
                return None
            if not _looks_continuation(next_text, previous=combined):
                return None
            body_span_ids.append(next_span_id)
            combined = f"{combined}{next_text}"
            cursor += 1

        if _LEADING_BINDER.match(combined.strip()):
            return None
        if not _unit_closed(combined, under_colon_list=under_colon_list):
            return None

        units.append(
            _ClosedUnit(
                qualifier_span_ids=tuple(span for span, _ in stack),
                body_span_ids=tuple(body_span_ids),
                body_text=combined,
            )
        )
        bodies_seen_since_qualifier = True
        index = cursor

    return units


def _pack_units(
    units: Sequence[_ClosedUnit],
    *,
    segment_soft_tokens: int,
    max_units_per_segment: int,
) -> list[list[_ClosedUnit]]:
    if segment_soft_tokens <= 0 and max_units_per_segment <= 0:
        return [[unit] for unit in units]

    batches: list[list[_ClosedUnit]] = []
    current: list[_ClosedUnit] = []
    current_tokens = 0

    for unit in units:
        unit_tokens = _estimate_tokens(unit.body_text)
        same_stack = bool(current) and current[-1].qualifier_span_ids == unit.qualifier_span_ids
        over_units = (
            max_units_per_segment > 0 and len(current) >= max_units_per_segment
        )
        over_tokens = (
            segment_soft_tokens > 0
            and current_tokens + unit_tokens > segment_soft_tokens
        )
        if current and same_stack and not over_units and not over_tokens:
            current.append(unit)
            current_tokens += unit_tokens
            continue
        if current:
            batches.append(current)
        current = [unit]
        current_tokens = unit_tokens

    if current:
        batches.append(current)

    # Packing is optional and must preserve a multi-segment plan. If ceilings
    # collapse everything into one batch, keep 1:1 body units.
    if len(batches) < 2:
        return [[unit] for unit in units]
    return batches


def plan_parent_rule_segments(
    item: FrozenCatalogItem,
    *,
    source_materials: Sequence[Any],
    token_estimate: int,
    thresholds: ParentSegmentationThresholds,
) -> ParentRuleSegmentPlan | None:
    """Split frozen multi-block parents with hierarchical qualifier inheritance.

    Qualifier headers (colon-terminated, logically balanced spans) never become
    body segments. Open round parentheses, leading binders, and unlawful
    cross-span continuations fail closed to the whole-parent path. Unmatched
    square/black citation brackets are ignored for closedness. A single long
    paragraph is deliberately never split.
    """

    if (
        not thresholds.enabled
        or not item.official_code
        or token_estimate < thresholds.soft_input_tokens
        or len(item.source_span_ids) < thresholds.min_source_spans
    ):
        return None
    texts = _source_texts(item, source_materials)
    if not all(texts):
        return None

    units = _collect_closed_units(item.source_span_ids, texts)
    if units is None:
        return None

    min_units = max(2, thresholds.min_obligations)
    if len(units) < min_units:
        return None

    batches = _pack_units(
        units,
        segment_soft_tokens=thresholds.segment_soft_tokens,
        max_units_per_segment=thresholds.max_units_per_segment,
    )
    if len(batches) < 2:
        return None

    total = len(batches)
    segments = tuple(
        ParentRuleSegment(
            parent_official_code=item.official_code,
            segment_id=f"{item.official_code}#segment-{index:02d}-of-{total:02d}",
            source_span_ids=(
                *batch[0].qualifier_span_ids,
                *(span_id for unit in batch for span_id in unit.body_span_ids),
            ),
            body_source_span_ids=tuple(
                span_id for unit in batch for span_id in unit.body_span_ids
            ),
        )
        for index, batch in enumerate(batches, start=1)
    )
    return ParentRuleSegmentPlan(
        parent_official_code=item.official_code,
        segments=segments,
    )


def validate_segment_source_closure(candidate: Any, segment: ParentRuleSegment) -> None:
    allowed = set(segment.source_span_ids)
    referenced = {
        source_span_id
        for rule in candidate.proposed_rules
        for component in rule.components
        for source_span_id in component.source_span_ids
    }
    issue_refs = {
        source_ref
        for item in (*candidate.structural_warnings, *candidate.unresolved_items)
        for source_ref in item.source_refs
    }
    if not referenced <= allowed or not issue_refs <= allowed:
        raise ValueError(f"分段 {segment.segment_id} 引用了分段闭包之外的方案来源")
    if not set(segment.body_source_span_ids) <= referenced:
        raise ValueError(f"分段 {segment.segment_id} 未引用其正文来源")


def merge_parent_rule_segments(
    candidates: Sequence[Any],
    *,
    plan: ParentRuleSegmentPlan,
    candidate_id: str,
    agent_call_id: str,
) -> Any:
    if len(candidates) != len(plan.segments):
        raise ValueError("同父规则分段结果数量与冻结计划不一致")
    first = candidates[0]
    components = []
    warnings = []
    unresolved = []
    for segment, candidate in zip(plan.segments, candidates, strict=True):
        if len(candidate.proposed_rules) != 1:
            raise ValueError(f"分段 {segment.segment_id} 必须只返回一个官方父规则")
        rule = candidate.proposed_rules[0]
        if rule.official_code != plan.parent_official_code:
            raise ValueError(f"分段 {segment.segment_id} 返回了其他官方父规则")
        validate_segment_source_closure(candidate, segment)
        components.extend(rule.components)
        warnings.extend(candidate.structural_warnings)
        unresolved.extend(candidate.unresolved_items)
    merged_rule = first.proposed_rules[0].model_copy(update={"components": components})
    return first.model_copy(
        update={
            "candidate_id": candidate_id,
            "created_by_agent_call_id": agent_call_id,
            "proposed_rules": [merged_rule],
            "structural_warnings": warnings,
            "unresolved_items": unresolved,
        }
    )
