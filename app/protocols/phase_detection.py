"""Deterministic phase applicability graph and single-phase projection.

The graph is built from paragraph, table-row and visit-column structure blocks.
It never treats the words "操作无缝", dose hand-off, or new Phase III
participants as evidence that the same subjects continue across phases.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from app.domain.contracts.enums import (
    ApplicabilityGranularity,
    DocumentPart,
    MetadataSourceKind,
    PhaseDesignType,
    PhaseScope,
    StudyPhase,
)
from app.domain.contracts.protocol_metadata import (
    PhaseApplicabilityBlock,
    PhaseApplicabilityGraph,
    PhaseProjection,
    SeamlessPhaseCandidate,
    StudyPhaseCandidate,
)

from .docx_structure import StructureBlock

_CELL_REF_RE = re.compile(
    r"^(?P<table>.+?\.t\d+)\.r(?P<row>\d+)\.c(?P<col>\d+)(?:\.p\d+)?$"
)

_PHASE_II_RE = re.compile(r"(?:Ⅱ|II|2|二)\s*(?:期|[/／])", re.I)
_PHASE_III_RE = re.compile(r"(?:Ⅲ|III|3|三)\s*(?:期|[/／])", re.I)
_SHARED_WITHOUT_PHASE_RE = re.compile(
    r"均适用|共同适用|适用于两期|两期(?:均|共同)|各期(?:均|共同)"
    r"|共同(?:入选|纳入|排除|入排|适用)标准|两期通用(?:标准|要求|程序)",
    re.I,
)
_PHASE_PAIR_RE = (
    r"(?:Ⅱ|II|2|二)\s*期+\s*(?:临床研究)?(?:阶段)?\s*"
    r"(?:和|及|与|、|/|／)\s*"
    r"(?:Ⅲ|III|3|三)\s*期+\s*(?:临床研究)?(?:阶段)?"
)
_SHARED_AFTER_PAIR_RE = re.compile(
    _PHASE_PAIR_RE
    + r".{0,60}(?:相同|一致|共同|均适用|均采用|均进行|均需|均应|使用|采用|选择|用)",
    re.I,
)
_SHARED_BEFORE_PAIR_RE = re.compile(
    r"(?:相同|一致|共同|均适用).{0,30}" + _PHASE_PAIR_RE,
    re.I,
)
_SHARED_CRITERIA_AFTER_PAIR_RE = re.compile(
    _PHASE_PAIR_RE
    + r"(?:中|内|的)?\s*(?:受试者|参与者)?\s*"
    + r"(?:均)?(?:符合|满足|遵守|执行|完成|需|应)"
    + r".{0,30}(?:以下|下列|所有|任一)?\s*(?:标准|条件|要求|检查|程序|操作)",
    re.I,
)
_PHASE_PAIR_FULL_RE = re.compile(_PHASE_PAIR_RE, re.I)
_SEAMLESS_DESIGN_RE = re.compile(
    r"无缝\s*(?:适应性)?\s*(?:设计|研究|试验)|seamless\s+(?:adaptive\s+)?(?:design|trial)",
    re.I,
)
_SAME_COHORT_RE = re.compile(
    r"同一(?:受试者|参与者)(?:队列|批)|同一队列"
    r"|same\s+cohort|same\s+(?:subjects|participants).*?(?:continue|across\s+phases)",
    re.I,
)
_DISQUALIFYING_RE = re.compile(
    r"操作无缝|剂量(?:选择|衔接|转换|调整)|继续纳入(?:新的?|新增加的?)?(?:受试者|参与者)"
    r"|新(?:的)?(?:受试者|参与者)|另行纳入|继续入组(?:新|其他)",
    re.I,
)
_VISIT_RE = re.compile(
    r"筛选|导入|基线|随机|(?:D|W|V)\s*[-]?\s*\d+|访视|visit",
    re.I,
)
_HEADING_RE = re.compile(r"阶段|研究目的|入选标准|排除标准|流程|给药|研究设计|主要终点|临床研究")
_TABLE_APPLICABILITY_HEADING_RE = re.compile(
    r"(?:研究)?(?:流程|日程|访视)(?:图|表)|临床研究阶段流程表",
    re.I,
)


@dataclass(frozen=True)
class PhaseDetectionResult:
    graph: PhaseApplicabilityGraph
    phase_candidates: tuple[StudyPhaseCandidate, ...]


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"phase-{digest}"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("：", ":")).strip()


def _scope_from_text(
    text: str,
    inherited: tuple[PhaseScope, ...] | None = None,
) -> tuple[tuple[PhaseScope, ...], bool]:
    """Classify one local source unit conservatively.

    A phase mention is not enough to call a unit shared.  When both phases
    occur without an explicit local shared marker, the unit is ``MIXED`` and
    cannot enter a normal single-phase projection.  Untagged table cells are
    ``UNKNOWN`` until a nearby row/column header provides a narrow inheritance
    signal; they are never silently promoted to shared.
    """

    text = _normalize(text)
    has_ii = bool(_PHASE_II_RE.search(text))
    has_iii = bool(_PHASE_III_RE.search(text))
    shared_evidence = _has_shared_evidence(text, has_ii=has_ii, has_iii=has_iii)
    if shared_evidence and not _has_unpaired_phase_reference(text):
        return (PhaseScope.SHARED,), True
    if has_ii and has_iii:
        return (PhaseScope.MIXED,), False
    if has_ii:
        return (PhaseScope.PHASE_II,), False
    if has_iii:
        return (PhaseScope.PHASE_III,), False
    if inherited:
        return inherited, False
    return (PhaseScope.UNKNOWN,), False


def _has_shared_evidence(text: str, *, has_ii: bool, has_iii: bool) -> bool:
    """Recognize only a local, explicit shared-applicability statement.

    A generic ``共同`` in an untagged procedure or table heading is not enough
    to classify a source unit as shared.  A sentence naming both phases and
    declaring the requirement/standard the same is explicit local evidence.
    """

    if _SHARED_WITHOUT_PHASE_RE.search(text) and not has_ii and not has_iii:
        return True
    return has_ii and has_iii and bool(
        _SHARED_AFTER_PAIR_RE.search(text)
        or _SHARED_BEFORE_PAIR_RE.search(text)
        or _SHARED_CRITERIA_AFTER_PAIR_RE.search(text)
    )


def _has_unpaired_phase_reference(text: str) -> bool:
    """Detect a phase mention outside the explicit shared pair.

    For example, ``II期阶段性分析、II期和III期研究结束时`` contains a shared
    pair plus a phase-II-only event.  It is mixed content and must not be
    projected as a shared aggregate merely because a later sentence says
    ``共同批准``.
    """

    spans = [match.span() for match in _PHASE_PAIR_FULL_RE.finditer(text)]
    if not spans:
        return False
    residual: list[str] = []
    cursor = 0
    for start, end in spans:
        residual.append(text[cursor:start])
        cursor = end
    residual.append(text[cursor:])
    return bool(_PHASE_II_RE.search(" ".join(residual)) or _PHASE_III_RE.search(" ".join(residual)))


def _looks_like_heading(block: StructureBlock) -> bool:
    text = _normalize(block.text)
    return bool(
        len(text) <= 90
        or (block.style and "heading" in block.style.lower())
        or _HEADING_RE.search(text)
    )


def _establishes_scope_context(
    block: StructureBlock,
    scopes: tuple[PhaseScope, ...],
) -> bool:
    """Return whether an explicit local statement governs following siblings.

    A phase name inside an ordinary sentence must not silently retag subsequent
    paragraphs.  Context starts only from a heading or an applicability lead-in
    such as "III期符合下列所有标准".
    """

    if not _scope_is_clear(scopes):
        return False
    text = _normalize(block.text)
    return bool(
        (block.style and "heading" in block.style.lower())
        or _HEADING_RE.search(text)
        or re.search(
            r"(?:符合|满足|遵守|执行|完成|适用于|需|应).{0,35}"
            r"(?:以下|下列|所有|任一|标准|条件|要求|程序|操作)",
            text,
        )
    )


def _body_contexts(blocks: Sequence[StructureBlock]) -> Mapping[str, tuple[PhaseScope, ...]]:
    """Infer only a narrow heading context; neutral content stays unknown."""

    context: tuple[PhaseScope, ...] | None = None
    result: dict[str, tuple[PhaseScope, ...]] = {}
    last_part: DocumentPart | None = None
    for block in sorted(blocks, key=lambda item: item.block_order):
        if block.document_part != DocumentPart.BODY or block.table_path is not None:
            continue
        if last_part is not None and block.document_part != last_part:
            context = None
        text = _normalize(block.text)
        explicit, _shared = _scope_from_text(text)
        has_explicit = bool(_PHASE_II_RE.search(text) or _PHASE_III_RE.search(text))
        if has_explicit or explicit == (PhaseScope.SHARED,):
            result[block.source_ref] = explicit
            if (
                len(explicit) == 1
                and explicit[0]
                in {PhaseScope.PHASE_II, PhaseScope.PHASE_III, PhaseScope.SHARED}
                and _establishes_scope_context(block, explicit)
            ):
                context = explicit
            else:
                context = None
        else:
            result[block.source_ref] = context or (PhaseScope.UNKNOWN,)
        last_part = block.document_part
    return result


def _table_groups(blocks: Sequence[StructureBlock]):
    groups: dict[tuple[str, int], list[StructureBlock]] = {}
    for block in blocks:
        match = _CELL_REF_RE.match(block.source_ref)
        if not match:
            continue
        key = (match.group("table"), int(match.group("row")))
        groups.setdefault(key, []).append(block)
    return groups


def _table_heading_scopes(
    blocks: Sequence[StructureBlock],
) -> Mapping[str, tuple[PhaseScope, ...]]:
    """Bind a top-level table to its nearest explicit applicability heading.

    Visit matrices commonly carry the phase only in the paragraph immediately
    before the table; their cells contain clinical operations and X marks, not
    the words II/III. A heading naming one phase applies that phase to the
    following table. A heading explicitly naming a shared flow/schedule table
    for both phases applies to both as shared content, not as mixed prose.
    """
    ordered = sorted(blocks, key=lambda item: item.block_order)
    top_level = [
        block
        for block in ordered
        if block.document_part == DocumentPart.BODY and block.table_path is None
    ]
    result: dict[str, tuple[PhaseScope, ...]] = {}
    for index, block in enumerate(top_level):
        if not re.fullmatch(r"body\.t\d+", block.source_ref):
            continue
        inspected = 0
        for candidate in reversed(top_level[:index]):
            if re.fullmatch(r"body\.t\d+", candidate.source_ref):
                break
            text = _normalize(candidate.text)
            if not text:
                continue
            inspected += 1
            if inspected > 12 or candidate.section_index != block.section_index:
                break
            has_ii = bool(_PHASE_II_RE.search(text))
            has_iii = bool(_PHASE_III_RE.search(text))
            if not (has_ii or has_iii):
                continue
            if not _TABLE_APPLICABILITY_HEADING_RE.search(text):
                # A nearby narrative phase mention is not table authority.
                continue
            if has_ii and has_iii:
                result[block.source_ref] = (PhaseScope.SHARED,)
            elif has_ii:
                result[block.source_ref] = (PhaseScope.PHASE_II,)
            else:
                result[block.source_ref] = (PhaseScope.PHASE_III,)
            break
    return result


def _table_is_visit_table(groups: Mapping[tuple[str, int], list[StructureBlock]], table: str) -> bool:
    rows = [
        cells
        for (name, _row), cells in sorted(groups.items(), key=lambda item: item[0][1])
        if name == table
    ]
    sample = " ".join(_normalize(cell.text) for cells in rows[:3] for cell in cells)
    return bool(_VISIT_RE.search(sample))


def _scope_is_clear(scopes: tuple[PhaseScope, ...]) -> bool:
    return bool(scopes) and not set(scopes) & {PhaseScope.MIXED, PhaseScope.UNKNOWN}


def _combine_child_scopes(
    child_scopes: Sequence[tuple[PhaseScope, ...]],
) -> tuple[PhaseScope, ...]:
    """Aggregate local scopes without letting one hit dominate a mixed node."""

    if not child_scopes:
        return (PhaseScope.UNKNOWN,)
    flattened = {scope for scopes in child_scopes for scope in scopes}
    if PhaseScope.MIXED in flattened:
        return (PhaseScope.MIXED,)
    if PhaseScope.PHASE_II in flattened and PhaseScope.PHASE_III in flattened:
        return (PhaseScope.MIXED,)
    if PhaseScope.UNKNOWN in flattened:
        return (PhaseScope.UNKNOWN,)
    # An aggregate may inherit a scope only when every local child agrees.  A
    # phase-specific child next to a shared child is still mixed; retaining a
    # union such as [II, shared] would make both single-phase projections
    # consume the same aggregate and lose source ownership.
    first = child_scopes[0]
    if all(scopes == first for scopes in child_scopes[1:]):
        return first
    return (PhaseScope.MIXED,)


def _clear_header_scope(cells: Sequence[StructureBlock]) -> tuple[PhaseScope, ...] | None:
    """Return only a clear first-cell header signal for local inheritance."""

    for cell in sorted(cells, key=lambda item: (item.block_order, item.source_ref)):
        if not _normalize(cell.text):
            continue
        scopes, _shared = _scope_from_text(cell.text)
        if _scope_is_clear(scopes):
            return scopes
        return None
    return None


def _table_root(source_ref: str) -> str | None:
    match = re.match(r"^(?P<table>.+?\.t\d+)(?:\.r\d+|\.c\d+)", source_ref)
    return match.group("table") if match else None


def _projection_text(text: str, selected_phase: StudyPhase) -> str:
    label = "Ⅱ期" if selected_phase == StudyPhase.PHASE_II else "Ⅲ期"
    cleaned = text
    cleaned = re.sub(
        _PHASE_PAIR_RE + r"\s*(?:相同|一致)",
        label,
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r"(?:Ⅱ|II|2|二)\s*期+\s*(?:临床研究)?(?:阶段)?\s*"
        r"(?:和|及|与|、|/|／)\s*"
        r"(?:Ⅲ|III|3|三)\s*期+\s*(?:临床研究)?(?:阶段)?",
        label,
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"与\s*(?:Ⅱ|II)\s*期\s*(?:相同|一致)", "", cleaned, flags=re.I)
    cleaned = re.sub(r"与\s*(?:Ⅲ|III)\s*期\s*(?:相同|一致)", "", cleaned, flags=re.I)
    cleaned = re.sub(r"(?:Ⅱ|II)\s*[/、和及与]\s*(?:Ⅲ|III)\s*期", label, cleaned, flags=re.I)
    cleaned = re.sub(r"(?:两期|共同适用)", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" ，,；;:") or label


def _make_block(
    *,
    snapshot_id: str,
    source_ref: str,
    source_span_ids: list[str],
    granularity: ApplicabilityGranularity,
    source_order: int,
    text: str,
    scopes: tuple[PhaseScope, ...],
    table_path: tuple[int, ...] | None = None,
    table_row: int | None = None,
    visit_column: int | None = None,
    cross_phase: bool = False,
    is_aggregate: bool = False,
    child_block_ids: list[str] | None = None,
) -> PhaseApplicabilityBlock:
    return PhaseApplicabilityBlock(
        block_id=_stable_id(snapshot_id, source_ref, granularity.value),
        snapshot_id=snapshot_id,
        source_ref=source_ref,
        source_span_ids=source_span_ids,
        granularity=granularity,
        source_order=source_order,
        # Keep the source payload intact.  Consumer-facing phase wording is
        # derived in ``projection_text`` and never replaces this field.
        text=text,
        phase_scopes=list(scopes),
        table_path=table_path,
        table_row=table_row,
        visit_column=visit_column,
        cross_phase_comparison=cross_phase,
        projection_text=None,
        is_aggregate=is_aggregate,
        child_block_ids=child_block_ids or [],
    )


def _seamless_candidate(
    blocks: Sequence[PhaseApplicabilityBlock],
    *,
    snapshot_id: str,
) -> SeamlessPhaseCandidate | None:
    # A row/column aggregate is a derived view and must not manufacture a
    # seamless candidate.  Candidate evidence must point to an atomic source
    # block so the same-subject-space decision remains reviewable.
    atomic = [item for item in blocks if not item.is_aggregate]
    design_blocks = [item for item in atomic if _SEAMLESS_DESIGN_RE.search(item.text)]
    cohort_blocks = [item for item in atomic if _SAME_COHORT_RE.search(item.text)]
    disqualifying = [item for item in atomic if _DISQUALIFYING_RE.search(item.text)]
    if not design_blocks or not cohort_blocks or disqualifying:
        return None
    design = design_blocks[0]
    cohort = cohort_blocks[0]
    source_refs = list(dict.fromkeys([design.source_ref, cohort.source_ref]))
    return SeamlessPhaseCandidate(
        candidate_id=_stable_id(snapshot_id, "seamless", *source_refs),
        snapshot_id=snapshot_id,
        source_refs=source_refs,
        explicit_design_excerpt=design.text,
        same_cohort_excerpt=cohort.text,
        supporting_source_refs=source_refs,
    )


def _add_phase_candidate(
    phase_candidates: list[StudyPhaseCandidate],
    *,
    snapshot_id: str,
    block: StructureBlock,
    scopes: tuple[PhaseScope, ...],
    source_span_id: str,
) -> None:
    """Append a traceable phase candidate for an explicit source unit."""

    text = block.text
    if not (_PHASE_II_RE.search(text) or _PHASE_III_RE.search(text)):
        return
    phase_candidates.append(
        StudyPhaseCandidate(
            candidate_id=_stable_id(snapshot_id, "phase-candidate", block.source_ref),
            snapshot_id=snapshot_id,
            phase_scopes=list(scopes),
            design_type=(
                PhaseDesignType.SHARED_CONTENT
                if scopes == (PhaseScope.SHARED,)
                else PhaseDesignType.INDEPENDENT
            ),
            source_ref=block.source_ref,
            source_span_id=source_span_id,
            source_kind=(
                MetadataSourceKind.BODY
                if block.document_part == DocumentPart.BODY
                else MetadataSourceKind.HEADER_FOOTER
            ),
            excerpt=_normalize(text),
            priority_rank=40,
            confidence_basis=["局部结构块明确期别标记"],
            requires_confirmation=(
                scopes not in {
                    (PhaseScope.PHASE_II,),
                    (PhaseScope.PHASE_III,),
                    (PhaseScope.SHARED,),
                }
            ),
        )
    )


def _effective_table_scopes(
    groups: Mapping[tuple[str, int], list[StructureBlock]],
    table_heading_scopes: Mapping[str, tuple[PhaseScope, ...]],
) -> dict[str, tuple[tuple[PhaseScope, ...], bool]]:
    """Classify each table cell from local text plus narrow headers.

    Row and column hints are intentionally one-cell signals.  They are applied
    only to an otherwise unknown cell; a local phase mention or a local mixed
    statement always wins.  Conflicting row/column hints become ``MIXED``.
    """

    all_cells = [cell for cells in groups.values() for cell in cells]
    columns: dict[tuple[str, int], list[StructureBlock]] = {}
    for cell in all_cells:
        match = _CELL_REF_RE.match(cell.source_ref)
        if match is None:
            continue
        key = (match.group("table"), int(match.group("col")))
        columns.setdefault(key, []).append(cell)
    row_hints = {key: _clear_header_scope(cells) for key, cells in groups.items()}
    column_hints = {key: _clear_header_scope(cells) for key, cells in columns.items()}
    result: dict[str, tuple[tuple[PhaseScope, ...], bool]] = {}
    cell_contexts: dict[tuple[str, int, int], tuple[PhaseScope, ...]] = {}
    for (table, row), cells in groups.items():
        row_hint = row_hints[(table, row)]
        for cell in sorted(cells, key=lambda item: (item.block_order, item.source_ref)):
            local, cross = _scope_from_text(cell.text)
            match = _CELL_REF_RE.match(cell.source_ref)
            cell_key = (
                table,
                row,
                int(match.group("col")) if match is not None else -1,
            )
            if local != (PhaseScope.UNKNOWN,):
                result[cell.source_ref] = (local, cross)
                if _establishes_scope_context(cell, local):
                    cell_contexts[cell_key] = local
                continue
            cell_context = cell_contexts.get(cell_key)
            if cell_context is not None:
                result[cell.source_ref] = (cell_context, False)
                continue
            col_hint = (
                column_hints.get((table, int(match.group("col"))))
                if match is not None
                else None
            )
            if row_hint and col_hint:
                inherited = row_hint if row_hint == col_hint else (PhaseScope.MIXED,)
            else:
                inherited = (
                    row_hint
                    or col_hint
                    or table_heading_scopes.get(table)
                    or (PhaseScope.UNKNOWN,)
                )
            result[cell.source_ref] = (inherited, False)
    return result


def build_phase_applicability_graph(
    blocks: Sequence[StructureBlock],
    *,
    snapshot_id: str,
    source_span_ids: Mapping[str, str] | None = None,
) -> PhaseDetectionResult:
    """Build paragraph/table-row/visit-column applicability nodes."""

    if not blocks:
        raise ValueError("没有结构块，不能建立期别适用图")
    contexts = _body_contexts(blocks)
    nodes: list[PhaseApplicabilityBlock] = []
    phase_candidates: list[StudyPhaseCandidate] = []

    # Body/header/footer top-level paragraphs are atomic source nodes.  Table
    # cells are also atomic paragraph nodes; rows/columns below are derived
    # aggregates with explicit child ownership.
    table_blocks = [block for block in blocks if block.table_path is not None]
    body_blocks = [block for block in blocks if block.table_path is None]
    for block in body_blocks:
        if not _normalize(block.text):
            continue
        scopes, cross = _scope_from_text(block.text, contexts.get(block.source_ref))
        span_ref = (source_span_ids or {}).get(block.source_ref, block.source_ref)
        nodes.append(
            _make_block(
                snapshot_id=snapshot_id,
                source_ref=block.source_ref,
                source_span_ids=[span_ref],
                granularity=ApplicabilityGranularity.PARAGRAPH,
                source_order=block.block_order,
                text=block.text,
                scopes=scopes,
                cross_phase=cross,
            )
        )
        _add_phase_candidate(
            phase_candidates,
            snapshot_id=snapshot_id,
            block=block,
            scopes=scopes,
            source_span_id=span_ref,
        )

    groups = _table_groups(table_blocks)
    effective = _effective_table_scopes(groups, _table_heading_scopes(blocks))
    atomic_by_ref: dict[str, PhaseApplicabilityBlock] = {}
    for cell in sorted(table_blocks, key=lambda item: (item.block_order, item.source_ref)):
        if not _normalize(cell.text):
            continue
        match = _CELL_REF_RE.match(cell.source_ref)
        if match is None:
            continue
        scopes, cross = effective.get(cell.source_ref, ((PhaseScope.UNKNOWN,), False))
        span_ref = (source_span_ids or {}).get(cell.source_ref, cell.source_ref)
        node = _make_block(
            snapshot_id=snapshot_id,
            source_ref=cell.source_ref,
            source_span_ids=[span_ref],
            granularity=ApplicabilityGranularity.PARAGRAPH,
            source_order=cell.block_order,
            text=cell.text,
            scopes=scopes,
            table_path=cell.table_path,
            cross_phase=cross,
        )
        nodes.append(node)
        atomic_by_ref[cell.source_ref] = node
        _add_phase_candidate(
            phase_candidates,
            snapshot_id=snapshot_id,
            block=cell,
            scopes=scopes,
            source_span_id=span_ref,
        )

    visit_tables = {
        table for (table, _row) in groups if _table_is_visit_table(groups, table)
    }
    row_aggregates: list[PhaseApplicabilityBlock] = []
    for (table, row), cells in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1])):
        ordered = sorted(
            (cell for cell in cells if cell.source_ref in atomic_by_ref),
            key=lambda item: (item.block_order, item.source_ref),
        )
        if not ordered:
            continue
        child_nodes = [atomic_by_ref[cell.source_ref] for cell in ordered]
        row_text = " | ".join(cell.text for cell in ordered)
        first = ordered[0]
        row_aggregates.append(
            _make_block(
                snapshot_id=snapshot_id,
                source_ref=f"{table}.r{row}",
                source_span_ids=[
                    (source_span_ids or {}).get(cell.source_ref, cell.source_ref)
                    for cell in ordered
                ],
                granularity=ApplicabilityGranularity.TABLE_ROW,
                source_order=min(cell.block_order for cell in ordered),
                text=row_text,
                scopes=_combine_child_scopes([tuple(node.phase_scopes) for node in child_nodes]),
                table_path=first.table_path,
                table_row=row,
                cross_phase=any(node.cross_phase_comparison for node in child_nodes),
                is_aggregate=True,
                child_block_ids=[node.block_id for node in child_nodes],
            )
        )
    nodes.extend(row_aggregates)

    for table in sorted(visit_tables):
        columns: dict[int, list[StructureBlock]] = {}
        for (table_name, _row), cells in groups.items():
            if table_name != table:
                continue
            for cell in cells:
                match = _CELL_REF_RE.match(cell.source_ref)
                if match is not None and cell.source_ref in atomic_by_ref:
                    columns.setdefault(int(match.group("col")), []).append(cell)
        for col, column_cells in sorted(columns.items()):
            ordered = sorted(column_cells, key=lambda item: (item.block_order, item.source_ref))
            child_nodes = [atomic_by_ref[cell.source_ref] for cell in ordered]
            first = ordered[0]
            nodes.append(
                _make_block(
                    snapshot_id=snapshot_id,
                    source_ref=f"{table}.c{col}",
                    source_span_ids=[
                        (source_span_ids or {}).get(cell.source_ref, cell.source_ref)
                        for cell in ordered
                    ],
                    granularity=ApplicabilityGranularity.VISIT_COLUMN,
                    source_order=min(cell.block_order for cell in ordered),
                    text=" | ".join(cell.text for cell in ordered),
                    scopes=_combine_child_scopes([tuple(node.phase_scopes) for node in child_nodes]),
                    table_path=first.table_path,
                    visit_column=col,
                    cross_phase=any(node.cross_phase_comparison for node in child_nodes),
                    is_aggregate=True,
                    child_block_ids=[node.block_id for node in child_nodes],
                )
            )

    nodes.sort(key=lambda item: (item.source_order, item.source_ref, item.granularity.value))
    # A real phase graph always includes neutral/shared content.  If the source
    # only contains phase-specific text, shared is not invented as a block.
    seamless = _seamless_candidate(nodes, snapshot_id=snapshot_id)
    if seamless:
        design_ref = seamless.source_refs[0]
        nodes = [
            node.model_copy(update={"phase_scopes": [PhaseScope.SEAMLESS_CANDIDATE]})
            if node.source_ref == design_ref
            else node
            for node in nodes
        ]
        phase_candidates = [
            candidate.model_copy(
                update={
                    "phase_scopes": [PhaseScope.PHASE_II, PhaseScope.PHASE_III],
                    "design_type": PhaseDesignType.SEAMLESS_CANDIDATE,
                    "explicit_design_evidence": True,
                    "same_cohort_evidence": True,
                    "requires_confirmation": True,
                }
            )
            if candidate.source_ref == design_ref
            else candidate
            for candidate in phase_candidates
        ]
    detected = sorted(
        {scope for node in nodes for scope in node.phase_scopes}, key=lambda item: item.value
    )
    if seamless and PhaseScope.SEAMLESS_CANDIDATE not in detected:
        detected.append(PhaseScope.SEAMLESS_CANDIDATE)
        first_ref = seamless.source_refs[0]
        source_block = next(item for item in blocks if item.source_ref == first_ref)
        phase_candidates.append(
            StudyPhaseCandidate(
                candidate_id=_stable_id(snapshot_id, "seamless-phase-candidate", *seamless.source_refs),
                snapshot_id=snapshot_id,
                phase_scopes=[PhaseScope.PHASE_II, PhaseScope.PHASE_III],
                design_type=PhaseDesignType.SEAMLESS_CANDIDATE,
                source_ref=first_ref,
                source_span_id=(source_span_ids or {}).get(first_ref, first_ref),
                source_kind=(
                    MetadataSourceKind.BODY
                    if source_block.document_part == DocumentPart.BODY
                    else MetadataSourceKind.HEADER_FOOTER
                ),
                excerpt=seamless.explicit_design_excerpt,
                priority_rank=40,
                confidence_basis=["明确无缝设计措辞", "同一受试者队列连续跨期"],
                explicit_design_evidence=True,
                same_cohort_evidence=True,
                requires_confirmation=True,
            )
        )
    graph = PhaseApplicabilityGraph(
        graph_id=_stable_id(snapshot_id, "graph"),
        snapshot_id=snapshot_id,
        blocks=nodes,
        seamless_candidates=[seamless] if seamless else [],
        detected_phase_scopes=detected or [PhaseScope.UNKNOWN],
        default_design_type=(PhaseDesignType.SEAMLESS_CANDIDATE if seamless else PhaseDesignType.INDEPENDENT),
    )
    return PhaseDetectionResult(graph=graph, phase_candidates=tuple(phase_candidates))


def project_single_phase(
    graph: PhaseApplicabilityGraph,
    selected_phase: StudyPhase,
    *,
    projection_id: str | None = None,
) -> PhaseProjection:
    """Return selected-phase + shared blocks, excluding other-phase-only blocks."""

    if selected_phase not in {
        StudyPhase.PHASE_II,
        StudyPhase.PHASE_III,
        StudyPhase.SEAMLESS_II_III,
    }:
        raise ValueError("必须先确认 II 期、III 期或真正无缝期别")
    if selected_phase == StudyPhase.SEAMLESS_II_III and not graph.seamless_candidates:
        raise ValueError("没有通过明确设计和同一受试者队列证据的无缝候选")
    selected_scope = {
        StudyPhase.PHASE_II: PhaseScope.PHASE_II,
        StudyPhase.PHASE_III: PhaseScope.PHASE_III,
    }.get(selected_phase)
    def safe(block: PhaseApplicabilityBlock) -> bool:
        scopes = tuple(block.phase_scopes)
        if set(scopes) & {PhaseScope.MIXED, PhaseScope.UNKNOWN}:
            return False
        if selected_phase == StudyPhase.SEAMLESS_II_III:
            return bool(
                set(scopes)
                <= {
                    PhaseScope.PHASE_II,
                    PhaseScope.PHASE_III,
                    PhaseScope.SHARED,
                    PhaseScope.SEAMLESS_CANDIDATE,
                }
            )
        return scopes in {(selected_scope,), (PhaseScope.SHARED,)}

    # Prefer one aggregate view per table.  Visit tables project columns;
    # ordinary tables project rows.  If the preferred aggregate is mixed, its
    # safe atomic children remain independently eligible, but the mixed row or
    # column itself can never enter the Agent payload.
    visit_roots = {
        _table_root(block.source_ref)
        for block in graph.blocks
        if block.is_aggregate and block.granularity == ApplicabilityGranularity.VISIT_COLUMN
    }
    preferred_aggregates = {
        block.block_id
        for block in graph.blocks
        if block.is_aggregate
        and (
            (
                block.granularity == ApplicabilityGranularity.VISIT_COLUMN
                and _table_root(block.source_ref) in visit_roots
            )
            or (
                block.granularity == ApplicabilityGranularity.TABLE_ROW
                and _table_root(block.source_ref) not in visit_roots
            )
        )
    }
    included: list[PhaseApplicabilityBlock] = []
    excluded: list[str] = []
    suppressed_children: set[str] = set()

    def projected(block: PhaseApplicabilityBlock) -> PhaseApplicabilityBlock:
        # Do not mutate source text.  ``projection_text`` is a derived
        # consumer display field with no authority over source ownership.
        if block.cross_phase_comparison:
            return block.model_copy(
                update={"projection_text": _projection_text(block.text, selected_phase)}
            )
        return block.model_copy(update={"projection_text": None})

    for block in sorted(graph.blocks, key=lambda item: (item.source_order, item.source_ref)):
        if not block.is_aggregate:
            continue
        if block.block_id not in preferred_aggregates or not safe(block):
            excluded.append(block.block_id)
            continue
        included.append(projected(block))
        suppressed_children.update(block.child_block_ids)

    for block in sorted(graph.blocks, key=lambda item: (item.source_order, item.source_ref)):
        if block.is_aggregate:
            continue
        if block.block_id in suppressed_children or not safe(block):
            excluded.append(block.block_id)
            continue
        included.append(projected(block))

    included.sort(key=lambda item: (item.source_order, item.source_ref, item.granularity.value))
    excluded = list(dict.fromkeys(excluded))
    return PhaseProjection(
        projection_id=projection_id or _stable_id(graph.graph_id, selected_phase.value),
        graph_id=graph.graph_id,
        selected_phase=selected_phase,
        blocks=included,
        excluded_block_ids=excluded,
    )


# Public aliases make the projection contract discoverable without duplicating
# logic under a second name.
detect_phase_applicability = build_phase_applicability_graph
project_phase_applicability = project_single_phase
