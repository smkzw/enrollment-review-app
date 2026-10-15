"""Resolve structural visit headings without granting them authorship."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Sequence

from app.domain.contracts.protocol_controls import ControlScopeCitation, ProtocolStructureUnit
from app.domain.contracts.enums import PhaseScope, StudyPhase


TABLE_SEQUENCE_SOURCE_VERSION = "table-sequence-source-location/v1"


def _same_source_scope(left: ProtocolStructureUnit, right: ProtocolStructureUnit) -> bool:
    documents = [{ref.split("::", 1)[0] for ref in item.source_span_ids if "::" in ref}
                 for item in (left, right)]
    selected = {StudyPhase.PHASE_II: PhaseScope.PHASE_II,
                StudyPhase.PHASE_III: PhaseScope.PHASE_III}.get(right.study_phase)
    concrete = set(left.phase_scopes) & {PhaseScope.PHASE_II, PhaseScope.PHASE_III}
    return (left.study_phase == right.study_phase
            and len(documents[0]) == 1 and documents[0] == documents[1]
            and not (selected is not None and concrete and selected not in concrete
                     and not set(left.phase_scopes) & {PhaseScope.SHARED, PhaseScope.MIXED}))


def _table_reference(unit: ProtocolStructureUnit) -> str | None:
    # This is a physical caption identifier, never a clinical keyword classifier.
    caption = _text(unit.heading_path[-1]) if unit.heading_path else ""
    match = re.match(r"(?:表|Table)(\d+(?:[.\-]\d+)*)(?![\d.\-])", caption, re.I)
    return match.group() if match else None


def table_sequence_source_packet(
    unit: ProtocolStructureUnit, quoted_text: str,
    owned_units: Sequence[ProtocolStructureUnit], context_units: Sequence[ProtocolStructureUnit],
) -> dict[str, object] | None:
    """Locate action cells and object headers; never infer treatment chronology."""
    from app.protocols.procedure_catalog import _schedule_cells_from_units

    root, marker, row = unit.source_ref.rpartition(".r")
    table = unit.table_context
    if (not marker or not row.isdigit() or table is None or int(row) != table.row_index
            or unit.unit_kind != "table_row" or not quoted_text.strip()):
        return None
    available = [*owned_units, *context_units]
    cells = _schedule_cells_from_units(available, root)
    quote = _text(quoted_text)
    matches = [cell for cell in cells.values() if cell.row == table.row_index
               and quote in _text(cell.text)]
    if len(matches) != 1 or matches[0].col_span is None:
        return None
    action = matches[0]
    action_refs = set(action.source_refs)
    if not action_refs <= set(unit.member_source_refs):
        return None
    action_columns = set(range(action.col, action.col + action.col_span))
    headers = []
    for header in context_units:
        if (header.unit_kind != "table_header" or header.table_context is None
                or header.member_source_span_ids is None
                or header.source_ref.rpartition(".r")[0] != root
                or not _same_source_scope(header, unit)
                or header.heading_path != unit.heading_path
                or header.source_order >= unit.source_order
                or header.table_context.row_index >= table.row_index):
            continue
        header_cells = _schedule_cells_from_units([header], root)
        covered = set()
        objects = []
        for cell in sorted(header_cells.values(), key=lambda item: item.col):
            if cell.col_span is None:
                continue
            columns = set(range(cell.col, cell.col + cell.col_span))
            if not columns & action_columns:
                continue
            # A merged header spanning another object cannot identify this cell.
            if not columns <= action_columns or columns & covered:
                objects = []
                break
            refs = sorted(span for source, spans in zip(
                header.member_source_refs, header.member_source_span_ids or [], strict=True,
            ) if source in cell.source_refs for span in spans)
            if not refs or not _text(cell.text):
                objects = []
                break
            objects.append(ControlScopeCitation(
                structure_unit_id=header.structure_unit_id, source_span_ids=refs,
                source_excerpt=cell.text, source_unit_sha256=_unit_digest(header),
            ))
            covered.update(columns)
        if objects and covered == action_columns:
            headers.append(objects)
    if len(headers) != 1:
        return None
    return {"version": TABLE_SEQUENCE_SOURCE_VERSION,
            "action_source_refs": sorted(action_refs),
            "action_columns": sorted(action_columns),
            "object_citations": [item.model_dump(mode="json") for item in headers[0]]}


def table_sequence_context_locations(
    unit: ProtocolStructureUnit, owned_units: Sequence[ProtocolStructureUnit],
    context_units: Sequence[ProtocolStructureUnit],
) -> dict[str, object] | None:
    """Offer frozen locations, not preselected eligibility or object relations."""
    objects = []
    for text in unit.member_texts or []:
        packet = table_sequence_source_packet(unit, text, owned_units, context_units)
        if packet is not None and packet not in objects:
            objects.append(packet)
    reference = _table_reference(unit)
    if not objects or reference is None:
        return None
    contexts = [ControlScopeCitation(
        structure_unit_id=item.structure_unit_id, source_span_ids=sorted(item.source_span_ids),
        source_excerpt=item.excerpt, source_unit_sha256=_unit_digest(item),
    ).model_dump(mode="json") for item in context_units
        if item.unit_kind in {"paragraph", "list_item"} and item.table_context is None
        and item.source_order < unit.source_order and _same_source_scope(item, unit)
        and reference in {_text(match.group()) for match in re.finditer(
            r"(?:表|Table)\s*\d+(?:[.\-]\d+)*(?![\d.\-])", item.excerpt, re.I)}
        and item.heading_path == unit.heading_path[:len(item.heading_path)]]
    return {"version": TABLE_SEQUENCE_SOURCE_VERSION, "context_locations": contexts,
            "table_reference": reference, "action_cells": objects} if contexts else None


def validate_table_sequence_context(
    unit, quoted_text, boundary_quote, context_citation, table_reference,
    object_citations, owned_units, context_units,
):
    """Check physical witnesses, leaving object/sequence meaning to fresh review."""
    matches = [item for item in context_units
               if item.structure_unit_id == context_citation.structure_unit_id]
    available = [*owned_units, *context_units]
    if (len(matches) != 1 or sum(item.structure_unit_id == context_citation.structure_unit_id
                                for item in available) != 1):
        raise ValueError("执行先后依据须来自唯一的冻结只读段落")
    context = matches[0]
    prefix = context.heading_path
    reference = _text(table_reference)
    boundary = _text(boundary_quote)
    if (context.unit_kind not in {"paragraph", "list_item"} or context.table_context is not None
            or context.source_order >= unit.source_order
            or not _same_source_scope(context, unit)
            or not prefix or prefix != unit.heading_path[:len(prefix)]
            or context_citation.source_unit_sha256 != _unit_digest(context)
            or context_citation.source_span_ids != sorted(context.source_span_ids)
            or context_citation.source_excerpt != context.excerpt
            or not boundary or boundary not in _text(context.excerpt)
            or reference != _table_reference(unit)
            or reference not in {_text(match.group()) for match in re.finditer(
                r"(?:表|Table)\s*\d+(?:[.\-]\d+)*(?![\d.\-])", context.excerpt, re.I)}):
        raise ValueError("执行先后依据、引用表格或冻结上下文身份不符")
    packet = table_sequence_source_packet(unit, quoted_text, owned_units, context_units)
    if packet is None or [item.model_dump(mode="json") for item in object_citations] != packet["object_citations"]:
        raise ValueError("动作所属表格列对象缺少完整、可回溯的表头依据")
    if any(_text(item.source_excerpt) not in boundary for item in object_citations):
        raise ValueError("先后依据未包含动作所属的每个列对象，不能借用另一种治疗的关系")
    return packet


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
