"""Frozen-parent leading-scope inventory from source identity only.

This module inventories exact leading heading text that appears before the first
substantive child inside one official parent rule's frozen source spans. It does
not decide whether that heading governs each child, authorize review stages, or
union stages across parents.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.domain.contracts.agent_io import (
    ProtocolDeconstructionInput,
    ProtocolSourceMaterial,
)


@dataclass(frozen=True)
class FrozenParentScopeFragment:
    """One exact frozen-source excerpt that may supply leading parent scope."""

    source_span_id: str
    excerpt: str


class FrozenParentScopeError(ValueError):
    """Source integrity failure; callers consume code/refs, not display text."""

    def __init__(self, code: str, source_refs: Sequence[str]):
        self.code = code
        self.source_refs = tuple(source_refs)
        super().__init__(f"{code}: {', '.join(source_refs)}")


def _colon_prefix(text: str) -> tuple[str, str] | None:
    depth = 0
    for index, char in enumerate(text):
        if char in "（([【":
            depth += 1
        elif char in "）)]】" and depth:
            depth -= 1
        elif not depth and char in "：:\n":
            return text[:index + 1], text[index + 1:]
    return None


def _matching_parent_items(source_input: ProtocolDeconstructionInput, official_code: str):
    return [
        item
        for item in source_input.parent_rule_catalog.items
        if item.official_code == official_code
    ]


def _resolve_parent_materials(
    source_input: ProtocolDeconstructionInput,
    source_span_ids: Sequence[str],
) -> list[ProtocolSourceMaterial]:
    materials_by_id: dict[str, ProtocolSourceMaterial] = {}
    for material in source_input.source_materials:
        if material.source_span_id in materials_by_id:
            raise FrozenParentScopeError(
                "FROZEN_PARENT_SCOPE_MATERIAL_DUPLICATE", [material.source_span_id]
            )
        materials_by_id[material.source_span_id] = material

    resolved: list[ProtocolSourceMaterial] = []
    for span_id in source_span_ids:
        material = materials_by_id.get(span_id)
        if material is None:
            raise FrozenParentScopeError("FROZEN_PARENT_SCOPE_MATERIAL_MISSING", [span_id])
        resolved.append(material)
    # Stable sorting preserves the frozen catalog's span order within a block.
    # Source identifiers are opaque, not a text-position ordering.
    return sorted(resolved, key=lambda item: item.block_order)


def frozen_parent_scope_fragments(
    source_input: ProtocolDeconstructionInput,
    official_code: str,
    *,
    scope_has_stages: Callable[[str], bool],
    is_substantive: Callable[[str], bool],
) -> tuple[FrozenParentScopeFragment, ...]:
    """Return leading stage-bearing scope excerpts for one frozen parent.

    Selection is bound to the unique ``official_code`` catalog item and only that
    item's ``source_span_ids``. Callbacks must wrap the caller's existing stage /
    substantive classifiers; this function does not duplicate those regexes.

    Inventory rules:
    - continue through structural lead-ins, including colon/newline boundaries;
    - keep stage-bearing leading headings and colon-prefixed context verbatim;
      clinical wording in a colon prefix is not proof that its scope is known;
    - stop at the first substantive body; never transfer its stages to siblings;
    - never read another parent's spans, later siblings, or headings that only
      appear after substantive body text.
    """

    matches = _matching_parent_items(source_input, official_code)
    if not matches:
        raise FrozenParentScopeError("FROZEN_PARENT_SCOPE_IDENTITY_MISSING", [official_code])
    if len(matches) > 1:
        raise FrozenParentScopeError("FROZEN_PARENT_SCOPE_IDENTITY_DUPLICATE", [official_code])

    parent = matches[0]
    materials = _resolve_parent_materials(source_input, parent.source_span_ids)
    fragments: list[FrozenParentScopeFragment] = []

    for material in materials:
        remaining = material.text
        while remaining:
            split = _colon_prefix(remaining)
            prefix, remaining = split if split is not None else (remaining, "")
            heading = prefix.rstrip("：:\r\n").strip()
            if not heading:
                continue
            # This look is only structural classification, never a new excerpt.
            structural_look = heading.replace("，", "").replace(",", "")
            substantive = is_substantive(structural_look)
            stage_bearing = scope_has_stages(heading)
            colon_context = prefix.rstrip().endswith(("：", ":"))
            if stage_bearing and (not substantive or colon_context):
                fragments.append(FrozenParentScopeFragment(material.source_span_id, prefix))
            if substantive:
                return tuple(fragments)

    return tuple(fragments)
