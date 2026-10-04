"""Resolve structural visit headings without granting them authorship."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Sequence

from app.domain.contracts.protocol_controls import ControlScopeCitation, ProtocolStructureUnit


def _text(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).translate(
        str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
    ).split())


def _unit_digest(unit: ProtocolStructureUnit) -> str:
    return hashlib.sha256(json.dumps(
        unit.model_dump(mode="json"), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def resolve_ancestor_scope_citation(
    unit: ProtocolStructureUnit, scope: str,
    available_units: Sequence[ProtocolStructureUnit],
) -> ControlScopeCitation | None:
    """Return a unique physical ancestor; never substitute a body span."""
    quoted = _text(scope)
    if not quoted:
        raise ValueError("审核时期没有原文摘录")
    if quoted in _text(unit.excerpt):
        return None
    path = [_text(part) for part in unit.heading_path]
    headings = {part for part in path if quoted in part}
    matches = [item for item in available_units if (
        item.structure_unit_id != unit.structure_unit_id
        and item.source_order < unit.source_order
        and _text(item.excerpt) in headings
        and item.heading_path
        and [_text(part) for part in item.heading_path] == path[:len(item.heading_path)]
        and _text(item.excerpt) == _text(item.heading_path[-1])
        and item.study_phase == unit.study_phase
    )]
    if len(matches) != 1:
        raise ValueError("审核时期的祖先标题缺少唯一可核的原文位置")
    heading = matches[0]
    return ControlScopeCitation(
        structure_unit_id=heading.structure_unit_id,
        source_span_ids=list(heading.source_span_ids), source_excerpt=heading.excerpt,
        source_unit_sha256=_unit_digest(heading),
    )


def validate_scope_citations(bindings, source_units, available_units) -> None:
    """A heading supplies scope only; owned source/atom closures stay unchanged."""
    owned_ids = {unit.structure_unit_id for unit in source_units}
    for binding in bindings:
        citation = binding.scope_citation
        if citation is None:
            continue
        if citation.structure_unit_id in owned_ids or not source_units:
            raise ValueError("时期标题引用不能代替本条要求的来源单元")
        for unit in source_units:
            expected = resolve_ancestor_scope_citation(unit, citation.source_excerpt, available_units)
            if expected is None or citation != expected:
                raise ValueError("时期标题引用与本条要求的冻结祖先来源不一致")
