"""Resolve structural visit headings without granting them authorship."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Sequence

from app.domain.contracts.protocol_controls import ControlScopeCitation, ProtocolStructureUnit
from app.domain.contracts.enums import PhaseScope, StudyPhase


def immediate_cell_scope_label(
    unit: ProtocolStructureUnit, context_id: str, scope_quote: str,
    owned_units: Sequence[ProtocolStructureUnit], context_units: Sequence[ProtocolStructureUnit],
) -> ProtocolStructureUnit:
    """Prove a literal preceding cell label, not its semantic applicability."""
    all_units = [*owned_units, *context_units]
    matches = [item for item in context_units if item.structure_unit_id == context_id]
    if len(matches) != 1 or sum(item.structure_unit_id == context_id for item in all_units) != 1:
        raise ValueError("表内范围引用须指向唯一只读来源单元")
    label = matches[0]
    selected_scope = {StudyPhase.PHASE_II: PhaseScope.PHASE_II,
                      StudyPhase.PHASE_III: PhaseScope.PHASE_III}.get(unit.study_phase)
    concrete_scopes = set(label.phase_scopes) & {PhaseScope.PHASE_II, PhaseScope.PHASE_III}
    if (selected_scope is not None and concrete_scopes and selected_scope not in concrete_scopes
            and not set(label.phase_scopes) & {PhaseScope.SHARED, PhaseScope.MIXED}):
        raise ValueError("表内项目标签明确属于另一研究期别")
    span_documents = [{ref.split("::", 1)[0] for ref in item.source_span_ids if "::" in ref}
                      for item in (label, unit)]
    left = re.fullmatch(r"(.+)\.p(\d+)", label.source_ref)
    right = re.fullmatch(r"(.+)\.p(\d+)", unit.source_ref)
    if (left is None or right is None or left[1] != right[1]
            or int(left[2]) + 1 != int(right[2])
            or label.source_order >= unit.source_order
            or label.study_phase != unit.study_phase
            or label.heading_path != unit.heading_path
            or unit.table_context is None or label.table_context is None
            or unit.table_context.table_path != label.table_context.table_path
            or unit.table_context.member_cell_paths != [unit.table_context.table_path]
            or label.table_context.member_cell_paths != [label.table_context.table_path]
            or label.member_source_refs != [label.source_ref]
            or unit.member_source_refs != [unit.source_ref]
            or (any(span_documents) and (
                len(span_documents[0]) != 1 or span_documents[0] != span_documents[1]))
            or sum(item.source_ref == label.source_ref for item in all_units) != 1):
        raise ValueError("表内范围须来自同一冻结单元格中紧邻在前的单段标签")
    text = _text(label.excerpt)
    # Colon-ended labels are a deliberately narrow structural family. A body
    # sentence or obligation cannot gain authority merely by preceding a row.
    if (not text.endswith(":") or not text[:-1] or ":" in text[:-1]
            or any(mark in text[:-1] for mark in ".。!?！？;；\n")
            or re.search(r"必须|不得|禁止|应当|至少|至多|不超过|完成|执行|进行|需|须|shall|must", text, re.I)
            or _text(scope_quote) != text):
        raise ValueError("表内范围只能逐字引用完整项目标签，不能借用邻段动作或条件")
    return label


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
