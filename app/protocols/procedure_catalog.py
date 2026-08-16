"""Deterministic required-procedure catalog construction for Phase 3.

This module is deliberately a sidecar to the phase graph and the existing
ingestion contracts.  It does not infer study-phase ownership from procedure
text, table numbers, or the legacy deconstructor.  A procedure table is
considered only when its structure contains a table root, visit-like header
rows, operation rows, and explicit ``X``/``(X)`` marks.

The output is the existing :class:`FrozenProtocolCatalog` contract.  The
contract has one free-text ``visit_instance`` field rather than a separate
review-stage field.  We keep a display-safe header there and retain the exact
source wording through its source spans.  Superscript footnote markers are not
part of a visit or operation name, but scientific notation such as ``10^9``
must remain intact.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.domain.contracts.enums import (
    AlignmentStatus,
    CatalogItemKind,
    CatalogKind,
    SourceLocatorPrecision,
    StudyPhase,
    ReviewStage,
)
from app.domain.contracts.protocol_ingestion import (
    FrozenCatalogItem,
    FrozenProtocolCatalog,
    ProtocolSourceSpan,
)
from app.domain.contracts.protocol_metadata import (
    PhaseApplicabilityBlock,
    PhaseApplicabilityGraph,
    PhaseProjection,
)
from app.domain.publication import canonical_hash

from .docx_structure import BlockKind, StructureBlock
from .phase_detection import project_single_phase
from .section_index import formal_source_span_ids


CATALOG_BUILDER_VERSION = "required-procedures/v1"
"""Stable implementation marker used in IDs, not a project-specific rule."""

_DEFAULT_FROZEN_AT = datetime(1970, 1, 1, tzinfo=timezone.utc)
_DEFAULT_FROZEN_BY = CATALOG_BUILDER_VERSION

_MARK_RE = re.compile(r"^\s*[\(（]?\s*[xX×]\s*[\)）]?\s*$")
_CELL_REF_RE = re.compile(r"\.r(?P<row>\d+)\.c(?P<col>\d+)")
_TRAILING_FOOTNOTE_RE = re.compile(
    r"\^\d+(?=\s*(?:\^\d+|[\uff09)\]\u3011]|$))"
)

_PRE_SCREENING_RE = re.compile(r"(?:预筛|预筛选|pre[\s_-]*screen)", re.I)
_SCREENING_RE = re.compile(r"(?:筛选|screen(?:ing)?|screening)", re.I)
_RUN_IN_RE = re.compile(
    r"(?:导入|洗脱|run[\s_-]*in|runin|run-in|lead[\s_-]*in)", re.I
)
_BASELINE_RE = re.compile(r"(?:基线|随机(?:化)?|baseline|randomi[sz]ation)", re.I)
_EXPLICIT_POST_BASELINE_RE = re.compile(
    r"(?:提前(?:退出|终止)|早退|退出访视|末次给药后|安全性随访|随访期|"
    r"\bEOS\b|\bEOT\b|early[\s_-]*(?:exit|termination)|"
    r"end[\s_-]*of[\s_-]*(?:study|treatment)|safety[\s_-]*follow[\s_-]*up)",
    re.I,
)
_POST_BASELINE_RE = re.compile(
    r"(?:治疗期|给药期|用药期|维持期|随访|访视后|结束访视|"
    r"treatment[\s_-]*(?:period|phase)?|follow[\s_-]*up|followup|"
    r"post[\s_-]*baseline)",
    re.I,
)

_STAGE_GROUP_RE = re.compile(
    r"(?:预筛(?:选)?期|筛选期|导入期|洗脱期|基线期|治疗期|给药期|"
    r"维持期|随访期|安全性随访|提前(?:退出|终止)|"
    r"pre[\s_-]*screen(?:ing)?[\s_-]*(?:period|phase)|"
    r"screen(?:ing)?[\s_-]*(?:period|phase)|run[\s_-]*in[\s_-]*(?:period|phase)|"
    r"baseline[\s_-]*(?:period|phase)|treatment[\s_-]*(?:period|phase)|"
    r"follow[\s_-]*up[\s_-]*(?:period|phase))",
    re.I,
)
_VISIT_OR_DATE_RE = re.compile(
    r"(?:^|[\s/（(])(?:V\s*\d+|W\s*[+-]?\d+|D\s*[+-]?\d+)|"
    r"访视(?:点|时间)?|试验(?:周数|天数)|时间窗|time[\s_-]*window",
    re.I,
)

_RANDOMIZATION_ACTION_RE = re.compile(
    r"^(?:随机(?:化|分组|入组)?|randomi[sz](?:e|ed|ation))(?:\s*\d+)?$",
    re.I,
)
_CONCOMITANT_THERAPY_RE = re.compile(
    r"(?:合并(?:用药|治疗)|伴随(?:用药|治疗)|背景治疗|concomitant|"
    r"background therapy)",
    re.I,
)
_INVESTIGATIONAL_TREATMENT_RE = re.compile(
    r"(?:(?:试验|研究|盲法|investigational|study)\s*(?:用)?"
    r"(?:药物|药品|产品|drug|product).{0,80}"
    r"(?:给药|服用|分发|发放|回收|退还|清点|administ|dos(?:e|ing)|"
    r"dispens|return|accountab)|"
    r"(?:给药|服用|分发|发放|回收|退还|清点).{0,80}"
    r"(?:试验|研究|盲法|investigational|study)\s*(?:用)?"
    r"(?:药物|药品|产品|drug|product))",
    re.I,
)
_VISIT_LOGISTICS_RE = re.compile(
    r"(?:(?:日记卡|日志卡|设备|器材).{0,8}(?:发放|分发|回收|退还)|"
    r"(?:发放|分发|回收|退还).{0,8}(?:日记卡|日志卡|设备|器材)|"
    r"预约(?:下次)?访视|visit[\s_-]*(?:scheduling|logistics)|"
    r"diar(?:y|ies).{0,12}(?:dispens|distribut|return|collect))",
    re.I,
)
_POST_DOSE_SAFETY_RE = re.compile(
    r"(?:给药后.{0,12}(?:不良事件|AE|反应)|注射部位反应|post[\s_-]*dose.{0,12}"
    r"(?:adverse|AE|reaction)|injection[\s_-]*site[\s_-]*reaction|"
    r"^(?:不良事件|adverse events?)(?:\s*\d+)?$)",
    re.I,
)

_GENERIC_HEADER_RE = re.compile(
    r"^(?:项目|检查项目|操作|操作项目|研究项目|评估项目|检查/评估|"
    r"访视|访视时间|访视点|时间点|研究流程|流程|procedure|procedures|"
    r"assessment|assessments|visit|visits|timepoint|time point)$",
    re.I,
)
_PLACEHOLDER_RE = re.compile(
    r"^(?:[-—–_＿.。…]+|待定|待核对|待确认|占位|placeholder|tbd|todo|"
    r"unknown|未说明|未确定|暂无|无)$",
    re.I,
)

_STAGE_ORDER: dict[ReviewStage, int] = {
    ReviewStage.PRE_SCREENING: 0,
    ReviewStage.SCREENING: 1,
    ReviewStage.RUN_IN: 2,
    ReviewStage.BASELINE: 3,
}


class ProcedureCatalogError(ValueError):
    """Stable deterministic rejection raised before an Agent may run."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        table_root: str | None = None,
    ) -> None:
        self.code = code
        self.table_root = table_root
        prefix = f"{code}"
        if table_root:
            prefix += f" [{table_root}]"
        super().__init__(f"{prefix}: {message}")


# A descriptive alias makes the failure boundary discoverable to callers that
# use ``BuildError`` terminology while preserving one exception type.
ProcedureCatalogBuildError = ProcedureCatalogError
# Keep the validation-oriented name used by the sibling frozen-catalog
# builder.  Both names deliberately resolve to the same stable exception.
CatalogValidationError = ProcedureCatalogError
RequiredProcedureCatalogError = ProcedureCatalogError
RequiredProcedureCatalogBuildError = ProcedureCatalogError


class _PostBaseline(Enum):
    POST_BASELINE = "post_baseline"


@dataclass(frozen=True)
class _Cell:
    root: str
    row: int
    col: int
    blocks: tuple[StructureBlock, ...]

    @property
    def text(self) -> str:
        return " ".join(
            part.text.strip() for part in self.blocks if part.text.strip()
        ).strip()

    @property
    def source_refs(self) -> tuple[str, ...]:
        return tuple(block.source_ref for block in self.blocks)

    @property
    def block_order(self) -> int:
        return min(block.block_order for block in self.blocks)


@dataclass(frozen=True)
class _VisitColumn:
    column: int
    stage: ReviewStage
    original_text: str
    header_refs: tuple[str, ...]


@dataclass(frozen=True)
class _OperationInstance:
    root: str
    row: int
    operation: str
    operation_refs: tuple[str, ...]
    visit: _VisitColumn
    source_span_ids: tuple[str, ...]
    position_hint: tuple[int, int, int]


def _short_digest(*parts: object) -> str:
    payload = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _root_for_cell(
    block: StructureBlock,
    table_roots: Sequence[StructureBlock],
) -> StructureBlock | None:
    """Find the narrowest table root owning a cell.

    ``table_path`` is authoritative for nested tables.  The source-ref prefix
    check is retained for synthetic fixtures and for old extracted snapshots
    which did not preserve a table path on every cell.
    """

    candidates: list[StructureBlock] = []
    for root in table_roots:
        if not block.source_ref.startswith(root.source_ref + ".r"):
            continue
        root_path = root.table_path or ()
        if block.table_path is None:
            # Synthetic/older snapshots may omit the path while retaining the
            # canonical ``.rN.cN`` source-ref shape.
            candidates.append(root)
            continue
        if len(block.table_path) != len(root_path) + 2:
            continue
        if tuple(block.table_path[: len(root_path)]) != tuple(root_path):
            continue
        candidates.append(root)
    if not candidates:
        return None
    return max(candidates, key=lambda item: (len(item.source_ref), item.block_order))


def _cell_coordinates(block: StructureBlock) -> tuple[int, int] | None:
    if block.table_path is not None and len(block.table_path) >= 2:
        return block.table_path[-2], block.table_path[-1]
    matches = tuple(_CELL_REF_RE.finditer(block.source_ref))
    if not matches:
        return None
    match = matches[-1]
    return int(match.group("row")), int(match.group("col"))


def _make_cells(
    blocks: Sequence[StructureBlock],
    root: StructureBlock,
) -> dict[tuple[int, int], _Cell]:
    grouped: dict[tuple[int, int], list[StructureBlock]] = {}
    for block in blocks:
        if block.kind != BlockKind.PARAGRAPH:
            continue
        if _root_for_cell(block, [root]) != root:
            continue
        coordinates = _cell_coordinates(block)
        if coordinates is None:
            continue
        grouped.setdefault(coordinates, []).append(block)
    return {
        coordinates: _Cell(
            root=root.source_ref,
            row=coordinates[0],
            col=coordinates[1],
            blocks=tuple(
                sorted(items, key=lambda item: (item.block_order, item.source_ref))
            ),
        )
        for coordinates, items in sorted(grouped.items())
    }


def _is_mark(text: str) -> bool:
    return bool(_MARK_RE.fullmatch(text.strip()))


def _non_mark_text(cell: _Cell | None) -> str:
    if cell is None:
        return ""
    text = cell.text
    return "" if _is_mark(text) else text


def _without_display_footnotes(value: str) -> str:
    """Remove only trailing display footnotes from a semantic label.

    DOCX superscript runs are represented as ``^N`` by the structure layer.
    Footnotes may appear at the end of a label, in a closing parenthesis, or
    as a sequence such as ``^2^6``.  A caret inside a unit or formula is left
    untouched because it is followed by more semantic text.
    """

    cleaned = value
    while True:
        updated = _TRAILING_FOOTNOTE_RE.sub("", cleaned)
        if updated == cleaned:
            break
        cleaned = updated
    return re.sub(r"\s+", " ", cleaned).strip()


def _normalized_header_key(value: str) -> str:
    return _without_display_footnotes(value).casefold()


def _is_generic_header(value: str) -> bool:
    return bool(_GENERIC_HEADER_RE.fullmatch(value.strip()))


def _derive_visit_stage(value: str) -> ReviewStage | _PostBaseline | None:
    """Derive a review-stage label from the visit header, not study phase."""

    value = _without_display_footnotes(value)
    # An explicit end/exit/follow-up cue is terminal even if another header
    # fragment happens to mention baseline.  Otherwise a concrete baseline or
    # randomization cue wins over a broad parent such as ``treatment period``.
    if _EXPLICIT_POST_BASELINE_RE.search(value):
        return _PostBaseline.POST_BASELINE
    if _BASELINE_RE.search(value):
        return ReviewStage.BASELINE
    if _RUN_IN_RE.search(value):
        return ReviewStage.RUN_IN
    if _PRE_SCREENING_RE.search(value):
        return ReviewStage.PRE_SCREENING
    if _SCREENING_RE.search(value):
        return ReviewStage.SCREENING
    if _POST_BASELINE_RE.search(value):
        return _PostBaseline.POST_BASELINE
    return None


def derive_review_stage(value: str) -> ReviewStage | None:
    """Public helper for callers that need the canonical visit label."""

    stage = _derive_visit_stage(value)
    return stage if isinstance(stage, ReviewStage) else None


def _header_projection(
    cells: Mapping[tuple[int, int], _Cell],
    *,
    first_mark_row: int,
    max_columns: int,
) -> dict[int, tuple[str, tuple[str, ...]]]:
    """Project a conservative header hierarchy onto each visit column.

    DOCX extraction emits one cell for a horizontally merged stage/group
    heading, but sparse visit/date rows use the same blank-cell shape.  Only a
    row containing an explicit period/phase group cue is therefore propagated
    horizontally.  Visit, week, day, and time-window rows remain column-local.
    """

    # Keep both text and source refs while propagating a merged header.  A
    # propagated value still points to the original source cell; no synthetic
    # source span is manufactured for a merged blank cell.
    effective: dict[tuple[int, int], tuple[str, tuple[str, ...]]] = {}
    for row in range(first_mark_row):
        row_values = [
            _non_mark_text(cells.get((row, col)))
            for col in range(1, max_columns)
        ]
        propagate_group = any(
            value
            and _STAGE_GROUP_RE.search(value)
            and not _VISIT_OR_DATE_RE.search(value)
            for value in row_values
        )
        last: tuple[str, tuple[str, ...]] | None = None
        for col in range(max_columns):
            cell = cells.get((row, col))
            text = _non_mark_text(cell)
            if text:
                last = (text, cell.source_refs if cell else ())
            elif propagate_group and last is not None:
                effective[(row, col)] = last
                continue
            effective[(row, col)] = (text, cell.source_refs if cell else ())

    for col in range(max_columns):
        last: tuple[str, tuple[str, ...]] | None = None
        for row in range(first_mark_row):
            value = effective.get((row, col), ("", ()))
            if value[0]:
                last = value
            elif last is not None:
                effective[(row, col)] = last

    result: dict[int, tuple[str, tuple[str, ...]]] = {}
    for col in range(max_columns):
        values: list[str] = []
        refs: list[str] = []
        for row in range(first_mark_row):
            value, value_refs = effective.get((row, col), ("", ()))
            if not value:
                continue
            value = _without_display_footnotes(value)
            if value not in values:
                values.append(value)
            for ref in value_refs:
                if ref not in refs:
                    refs.append(ref)
        result[col] = (" / ".join(values), tuple(refs))
    return result


def _is_non_enrollment_operation(
    operation: str,
    *,
    visit_column: int,
    randomization_anchor: int | None,
) -> bool:
    """Reject workflow/treatment roles that are not enrollment checks."""

    value = operation.strip()
    if _RANDOMIZATION_ACTION_RE.fullmatch(value):
        return True
    if not _CONCOMITANT_THERAPY_RE.search(value) and (
        _INVESTIGATIONAL_TREATMENT_RE.search(value)
        or _VISIT_LOGISTICS_RE.search(value)
    ):
        return True
    # A D1/randomization column can mix pre-randomization checks with
    # post-dose safety collection.  The latter must not become an enrollment
    # requirement merely because both share a physical table column.
    return bool(
        randomization_anchor is not None
        and visit_column == randomization_anchor
        and _POST_DOSE_SAFETY_RE.search(value)
    )


def _operation_label(
    row_cells: Mapping[tuple[int, int], _Cell],
    *,
    row: int,
    mark_columns: Sequence[int],
) -> tuple[str, tuple[str, ...]] | None:
    """Select the last meaningful label before the first marked column."""

    first_mark = min(mark_columns)
    candidates = [
        cell
        for (cell_row, cell_col), cell in row_cells.items()
        if cell_row == row
        and cell_col < first_mark
        and _non_mark_text(cell)
        and not _is_generic_header(_non_mark_text(cell))
    ]
    if not candidates:
        candidates = [
            cell
            for (cell_row, _cell_col), cell in row_cells.items()
            if cell_row == row
            and _non_mark_text(cell)
            and not _is_generic_header(_non_mark_text(cell))
        ]
    if not candidates:
        return None
    selected = max(candidates, key=lambda item: (item.col, item.block_order))
    return _non_mark_text(selected), selected.source_refs


def _is_placeholder_operation(value: str) -> bool:
    return not value.strip() or bool(_PLACEHOLDER_RE.fullmatch(value.strip()))


def _span_input_map(
    source_spans: Sequence[ProtocolSourceSpan] | Mapping[str, ProtocolSourceSpan],
) -> tuple[dict[str, ProtocolSourceSpan], dict[str, ProtocolSourceSpan]]:
    if isinstance(source_spans, Mapping):
        spans = list(source_spans.values())
    else:
        spans = list(source_spans)
    by_ref: dict[str, ProtocolSourceSpan] = {}
    by_id: dict[str, ProtocolSourceSpan] = {}
    duplicate_refs: set[str] = set()
    duplicate_ids: set[str] = set()
    for span in spans:
        if not isinstance(span, ProtocolSourceSpan):
            raise TypeError("source_spans 必须包含 ProtocolSourceSpan")
        if span.source_ref in by_ref:
            duplicate_refs.add(span.source_ref)
        else:
            by_ref[span.source_ref] = span
        if span.source_span_id in by_id:
            duplicate_ids.add(span.source_span_id)
        else:
            by_id[span.source_span_id] = span
    if duplicate_refs:
        refs = "、".join(sorted(duplicate_refs))
        raise ProcedureCatalogError(
            "source_span_ambiguous", f"同一 source_ref 存在多个来源片段：{refs}"
        )
    if duplicate_ids:
        ids = "、".join(sorted(duplicate_ids))
        raise ProcedureCatalogError("source_span_ambiguous", f"来源片段 ID 重复：{ids}")
    return by_ref, by_id


def _resolve_context(
    context_args: Sequence[object],
    *,
    phase_projection: PhaseProjection | None,
    phase_graph: PhaseApplicabilityGraph | None,
    source_spans: Sequence[ProtocolSourceSpan] | Mapping[str, ProtocolSourceSpan] | None,
    selected_phase: StudyPhase | None,
) -> tuple[
    PhaseProjection | None,
    PhaseApplicabilityGraph | None,
    Sequence[ProtocolSourceSpan] | Mapping[str, ProtocolSourceSpan],
    StudyPhase | None,
]:
    """Accept the two natural positional forms used by protocol callers."""

    projection = phase_projection
    graph = phase_graph
    spans = source_spans
    phase = selected_phase
    for argument in context_args:
        if isinstance(argument, PhaseProjection):
            if projection is not None and projection != argument:
                raise TypeError("不能同时提供两个不同的 PhaseProjection")
            projection = argument
        elif isinstance(argument, PhaseApplicabilityGraph):
            if graph is not None and graph != argument:
                raise TypeError("不能同时提供两个不同的 PhaseApplicabilityGraph")
            graph = argument
        elif isinstance(argument, StudyPhase):
            if phase is not None and phase != argument:
                raise TypeError("不能同时提供两个不同的 selected_phase")
            phase = argument
        else:
            if spans is not None:
                raise TypeError("source_spans 只能提供一次")
            spans = argument  # validated below with a precise error
    if spans is None:
        raise ProcedureCatalogError(
            "source_coverage_missing", "未提供 ProtocolSourceSpan 来源集合"
        )
    if not isinstance(spans, Mapping):
        try:
            spans = list(spans)  # type: ignore[arg-type]
        except TypeError as exc:
            raise TypeError("source_spans 必须是 ProtocolSourceSpan 序列或映射") from exc
    return projection, graph, spans, phase


def _selected_refs(
    projection: PhaseProjection,
    *,
    spans_by_id: Mapping[str, ProtocolSourceSpan],
) -> set[str]:
    refs: set[str] = set()
    for block in projection.blocks:
        refs.add(block.source_ref)
        for span_id in block.source_span_ids:
            refs.add(span_id)
            span = spans_by_id.get(span_id)
            if span is not None:
                refs.add(span.source_ref)
    return refs


def _validate_phase_context(
    *,
    projection: PhaseProjection | None,
    graph: PhaseApplicabilityGraph | None,
    selected_phase: StudyPhase | None,
) -> tuple[PhaseProjection, StudyPhase]:
    if projection is None and graph is None:
        raise ProcedureCatalogError(
            "phase_context_missing",
            "必须提供已建立的 PhaseProjection 或 PhaseApplicabilityGraph",
        )
    if projection is not None and graph is not None and projection.graph_id != graph.graph_id:
        raise ProcedureCatalogError(
            "phase_scope_mismatch", "PhaseProjection 不属于给定的期别适用图"
        )
    phase = selected_phase or (projection.selected_phase if projection else None)
    if phase is None:
        raise ProcedureCatalogError("phase_unresolved", "未提供已选研究期别")
    if phase not in {
        StudyPhase.PHASE_II,
        StudyPhase.PHASE_III,
        StudyPhase.SEAMLESS_II_III,
    }:
        raise ProcedureCatalogError(
            "phase_unresolved", "研究期别必须是已确认的 II 期、III 期或无缝期别"
        )
    if projection is not None and projection.selected_phase != phase:
        raise ProcedureCatalogError(
            "phase_scope_mismatch", "投影期别与 selected_phase 不一致"
        )
    if projection is None:
        try:
            projection = project_single_phase(graph, phase)  # type: ignore[arg-type]
        except ValueError as exc:
            raise ProcedureCatalogError("phase_unresolved", str(exc)) from exc
    return projection, phase


def _formal_span_ids(
    refs: Iterable[str],
    *,
    spans_by_ref: Mapping[str, ProtocolSourceSpan],
    blocks_by_ref: Mapping[str, StructureBlock],
    snapshot_id: str,
    table_root: str,
    role: str,
    required: bool = True,
) -> tuple[str, ...]:
    """Return formal source anchors for one operation or visit range.

    A range may be represented by several structural cells (for example a
    vertically merged visit header).  At least one formal anchor is required
    for a required range; degraded or missing sibling hints are not promoted
    into authority.  Mark cells are optional anchors because repeated ``X``
    glyphs commonly cannot be uniquely aligned in a rendered page.
    """

    ids: list[str] = []
    missing: list[str] = []
    formal_locator_ids = formal_source_span_ids(spans_by_ref.values())
    for source_ref in dict.fromkeys(refs):
        span = spans_by_ref.get(source_ref)
        block = blocks_by_ref.get(source_ref)
        if span is None or block is None:
            missing.append(source_ref)
            continue
        if span.snapshot_id != snapshot_id:
            raise ProcedureCatalogError(
                "source_scope_mismatch",
                f"{role} 来源不属于当前提取快照：{source_ref}",
                table_root=table_root,
            )
        if (
            span.alignment_status != AlignmentStatus.ALIGNED
            or span.source_span_id not in formal_locator_ids
        ):
            continue
        if span.precision == SourceLocatorPrecision.TEXT_RANGE:
            if not span.excerpt or span.excerpt not in block.text:
                continue
        elif span.precision == SourceLocatorPrecision.PAGE_ONLY:
            # The uniqueness check above prevents a shared page hint from
            # satisfying the item-level source gate.
            if span.render_artifact_id is None or span.render_page is None:
                continue
        else:
            continue
        ids.append(span.source_span_id)
    if required and not ids:
        details = (
            f"缺少原始来源片段：{'、'.join(missing)}"
            if missing
            else "没有唯一 ALIGNED TEXT_RANGE 或 PAGE_ONLY 定位"
        )
        raise ProcedureCatalogError(
            "source_coverage_missing",
            f"{role} {details}",
            table_root=table_root,
        )
    return tuple(ids)


def _table_looks_like_flow(
    root: StructureBlock,
    cells: Mapping[tuple[int, int], _Cell],
    *,
    max_rows: int,
    max_columns: int,
) -> tuple[bool, list[_Cell], int | None]:
    marks = sorted(
        (cell for cell in cells.values() if _is_mark(cell.text)),
        key=lambda item: (item.row, item.col, item.block_order, item.root),
    )
    if max_rows < 2 or max_columns < 2 or not marks:
        return False, marks, None
    first_mark_row = min(cell.row for cell in marks)
    header_cells = [
        cell
        for cell in cells.values()
        if cell.row < first_mark_row and _non_mark_text(cell)
    ]
    marked_columns = {cell.col for cell in marks}
    header_columns = {cell.col for cell in header_cells}
    marked_rows_with_labels = 0
    for row in {cell.row for cell in marks}:
        if any(
            item.row == row
            and item.col < min(cell.col for cell in marks if cell.row == row)
            and _non_mark_text(item)
            for item in cells.values()
        ):
            marked_rows_with_labels += 1
    # A single keyword is never sufficient.  The root dimensions, explicit
    # marks, header structure, and row labels are independent signals.
    structural = bool(
        (len(marked_columns) >= 2 or len(header_columns) >= 2)
        and len(header_cells) >= 2
        and marked_rows_with_labels >= 1
    )
    return structural, marks, first_mark_row


def _build_instances_for_table(
    root: StructureBlock,
    cells: Mapping[tuple[int, int], _Cell],
    *,
    all_marks: Sequence[_Cell],
    selected_refs: set[str],
    max_columns: int,
    spans_by_ref: Mapping[str, ProtocolSourceSpan],
    blocks_by_ref: Mapping[str, StructureBlock],
    snapshot_id: str,
) -> list[_OperationInstance]:
    first_mark_row = min(cell.row for cell in all_marks)
    header = _header_projection(
        cells,
        first_mark_row=first_mark_row,
        max_columns=max_columns,
    )
    selected_marks = sorted(
        (
            cell
            for cell in all_marks
            if any(ref in selected_refs for ref in cell.source_refs)
        ),
        key=lambda item: (item.row, item.col, item.block_order, item.root),
    )
    if not selected_marks:
        return []

    # The earliest marked randomization action is a structural timing anchor,
    # not a catalog item.  It allows a D1/W0 column under a broad treatment
    # group to be interpreted as baseline without reading clinical prose or a
    # project-specific table number.
    randomization_columns: list[int] = []
    for row in sorted({cell.row for cell in selected_marks}):
        row_marks = [cell for cell in selected_marks if cell.row == row]
        label_result = _operation_label(
            cells,
            row=row,
            mark_columns=sorted({cell.col for cell in row_marks}),
        )
        if label_result and _RANDOMIZATION_ACTION_RE.fullmatch(
            _without_display_footnotes(label_result[0])
        ):
            randomization_columns.extend(cell.col for cell in row_marks)
    randomization_anchor = min(randomization_columns) if randomization_columns else None

    selected_columns = sorted({cell.col for cell in selected_marks})
    explicit_baseline_columns = [
        col
        for col in selected_columns
        if _derive_visit_stage(header.get(col, ("", ()))[0]) == ReviewStage.BASELINE
    ]
    baseline_boundary = (
        randomization_anchor
        if randomization_anchor is not None
        else (max(explicit_baseline_columns) if explicit_baseline_columns else None)
    )

    visits: dict[int, _VisitColumn] = {}
    unresolved_columns: list[int] = []
    for col in selected_columns:
        if baseline_boundary is not None and col > baseline_boundary:
            # Everything physically after the randomization/latest baseline
            # anchor is outside the enrollment catalog.  It need not have a
            # resolvable visit label (for example a sparse early-exit column).
            continue
        source_header_text, header_refs = header.get(col, ("", ()))
        original_text = _without_display_footnotes(source_header_text)
        derived = (
            ReviewStage.BASELINE
            if randomization_anchor is not None and col == randomization_anchor
            else _derive_visit_stage(original_text)
        )
        if derived == _PostBaseline.POST_BASELINE:
            # Treatment/follow-up is intentionally outside this catalog.
            continue
        if not isinstance(derived, ReviewStage) or not original_text or not header_refs:
            unresolved_columns.append(col)
            continue
        visits[col] = _VisitColumn(
            column=col,
            stage=derived,
            original_text=original_text,
            header_refs=header_refs,
        )
    if unresolved_columns:
        raise ProcedureCatalogError(
            "visit_unresolved",
            "流程表中的选定访视列无法确定预筛选/筛选/导入或基线访视，"
            f"列：{','.join(str(item) for item in unresolved_columns)}",
            table_root=root.source_ref,
        )

    baseline_columns = [
        visit.column for visit in visits.values() if visit.stage == ReviewStage.BASELINE
    ]
    instances: list[_OperationInstance] = []
    selected_rows = sorted({cell.row for cell in selected_marks})
    for row in selected_rows:
        row_marks = [cell for cell in selected_marks if cell.row == row]
        all_label_result = _operation_label(
            cells,
            row=row,
            mark_columns=sorted({cell.col for cell in row_marks}),
        )
        if all_label_result is None:
            raise ProcedureCatalogError(
                "operation_missing",
                f"带有 X/(X) 标记的第 {row} 行没有可追溯操作名称",
                table_root=root.source_ref,
            )
        all_operation = _without_display_footnotes(all_label_result[0])
        if _is_placeholder_operation(all_operation):
            raise ProcedureCatalogError(
                "operation_placeholder",
                f"第 {row} 行的操作名称是占位内容：{all_operation!r}",
                table_root=root.source_ref,
            )
        row_visits = [visits[cell.col] for cell in row_marks if cell.col in visits]
        if not row_visits:
            continue
        label_result = _operation_label(
            cells,
            row=row,
            mark_columns=[visit.column for visit in row_visits],
        )
        if label_result is None:
            raise ProcedureCatalogError(
                "operation_missing",
                f"带有 X/(X) 标记的第 {row} 行没有可追溯操作名称",
                table_root=root.source_ref,
            )
        operation, operation_refs = label_result
        operation = _without_display_footnotes(operation)
        if _is_placeholder_operation(operation):
            raise ProcedureCatalogError(
                "operation_placeholder",
                f"第 {row} 行的操作名称是占位内容：{operation!r}",
                table_root=root.source_ref,
            )

        for visit in sorted(
            row_visits,
            key=lambda item: (
                _STAGE_ORDER[item.stage],
                item.column,
                _normalized_header_key(item.original_text),
            ),
        ):
            if _is_non_enrollment_operation(
                operation,
                visit_column=visit.column,
                randomization_anchor=randomization_anchor,
            ):
                continue
            if baseline_columns and visit.column > max(baseline_columns):
                # A recognized pre-baseline label after the baseline column is
                # a malformed matrix, not a reason to silently re-order it.
                raise ProcedureCatalogError(
                    "visit_order_invalid",
                    f"访视列 {visit.original_text!r} 出现在基线之后",
                    table_root=root.source_ref,
                )
            mark_cells = [cell for cell in row_marks if cell.col == visit.column]
            mark_refs = tuple(
                ref
                for cell in mark_cells
                for ref in cell.source_refs
            )
            # Formal coverage is checked separately for operation and visit
            # ranges.  A repeated mark glyph is retained when it has a formal
            # locator, but an unalignable/degraded mark cannot mask a missing
            # operation or visit anchor.
            operation_span_ids = _formal_span_ids(
                operation_refs,
                spans_by_ref=spans_by_ref,
                blocks_by_ref=blocks_by_ref,
                snapshot_id=snapshot_id,
                table_root=root.source_ref,
                role="操作",
            )
            visit_span_ids = _formal_span_ids(
                # Short visit/date cells are commonly repeated throughout a
                # protocol and therefore cannot claim a unique text range.
                # The original table root is an eligible fallback only when
                # alignment proved a unique ALIGNED PAGE_ONLY locator.  A
                # degraded/interpolated table hint still fails this gate.
                (*visit.header_refs, root.source_ref),
                spans_by_ref=spans_by_ref,
                blocks_by_ref=blocks_by_ref,
                snapshot_id=snapshot_id,
                table_root=root.source_ref,
                role="访视",
                required=False,
            )
            if not visit_span_ids:
                table_span = spans_by_ref.get(root.source_ref)
                # Some adjacent phase tables start on the same rendered page,
                # making their PAGE_ONLY roots non-authoritative in isolation.
                # In that narrow case, a table-specific, unique operation
                # TEXT_RANGE is the formal combined operation/visit-row range;
                # the aligned table root merely proves the structural context.
                # A DEGRADED/interpolated root can never enable this fallback.
                if not (
                    table_span is not None
                    and table_span.snapshot_id == snapshot_id
                    and table_span.alignment_status == AlignmentStatus.ALIGNED
                    and table_span.precision == SourceLocatorPrecision.PAGE_ONLY
                    and table_span.render_artifact_id is not None
                    and table_span.render_page is not None
                    and operation_span_ids
                ):
                    raise ProcedureCatalogError(
                        "source_coverage_missing",
                        "访视 没有唯一 ALIGNED TEXT_RANGE 或 PAGE_ONLY 定位",
                        table_root=root.source_ref,
                    )
                visit_span_ids = operation_span_ids
            mark_span_ids = _formal_span_ids(
                mark_refs,
                spans_by_ref=spans_by_ref,
                blocks_by_ref=blocks_by_ref,
                snapshot_id=snapshot_id,
                table_root=root.source_ref,
                role="标记",
                required=False,
            )
            refs = tuple(
                dict.fromkeys((*operation_span_ids, *visit_span_ids, *mark_span_ids))
            )
            instances.append(
                _OperationInstance(
                    root=root.source_ref,
                    row=row,
                    operation=operation,
                    operation_refs=operation_refs,
                    visit=visit,
                    source_span_ids=refs,
                    position_hint=(root.block_order, row, visit.column),
                )
            )
    if not instances:
        raise ProcedureCatalogError(
            "flow_table_empty",
            "结构上识别为研究流程表，但基线及以前没有必做操作",
            table_root=root.source_ref,
        )
    return instances


def _source_ids_for_instance(
    instance: _OperationInstance,
    *,
    spans_by_ref: Mapping[str, ProtocolSourceSpan],
    blocks_by_ref: Mapping[str, StructureBlock],
    snapshot_id: str,
) -> tuple[str, ...]:
    operation_ids = _formal_span_ids(
        instance.operation_refs,
        spans_by_ref=spans_by_ref,
        blocks_by_ref=blocks_by_ref,
        snapshot_id=snapshot_id,
        table_root=instance.root,
        role="操作",
    )
    # The instance stores formal operation/visit anchors and any optional
    # formal mark anchors found during matrix construction.
    return tuple(dict.fromkeys((*operation_ids, *instance.source_span_ids)))


def build_required_procedure_catalog(
    blocks: Sequence[StructureBlock],
    *context_args: object,
    phase_projection: PhaseProjection | None = None,
    phase_graph: PhaseApplicabilityGraph | None = None,
    source_spans: Sequence[ProtocolSourceSpan]
    | Mapping[str, ProtocolSourceSpan]
    | None = None,
    selected_phase: StudyPhase | None = None,
    snapshot_id: str | None = None,
    frozen_at: datetime | None = None,
    frozen_by: str = _DEFAULT_FROZEN_BY,
) -> FrozenProtocolCatalog:
    """Freeze the selected phase's required pre-baseline procedure catalog.

    Accepted positional forms are intentionally small and explicit:

    ``(blocks, projection, spans)``
        Use an already-built single-phase projection.
    ``(blocks, graph, spans, selected_phase=...)``
        Project the graph deterministically inside this function.

    The keyword form may provide both ``phase_graph`` and
    ``phase_projection`` for consistency checks.  ``snapshot_id`` is normally
    derived from the graph or projection blocks; passing it explicitly is
    useful when the projection contains only an aggregate block.
    """

    projection, graph, spans_input, phase_arg = _resolve_context(
        context_args,
        phase_projection=phase_projection,
        phase_graph=phase_graph,
        source_spans=source_spans,
        selected_phase=selected_phase,
    )
    projection, phase = _validate_phase_context(
        projection=projection,
        graph=graph,
        selected_phase=phase_arg,
    )
    spans_by_ref, spans_by_id = _span_input_map(spans_input)
    if not blocks:
        raise ProcedureCatalogError(
            "flow_table_missing", "没有结构块，不能冻结必做项目录"
        )

    blocks_by_ref = {block.source_ref: block for block in blocks}
    if len(blocks_by_ref) != len(blocks):
        raise ProcedureCatalogError("source_ref_ambiguous", "结构块 source_ref 必须唯一")
    if snapshot_id is None:
        if graph is not None:
            snapshot_id = graph.snapshot_id
        else:
            snapshot_candidates = {
                block.snapshot_id
                for block in projection.blocks
                if isinstance(block, PhaseApplicabilityBlock)
            }
            # PhaseApplicabilityBlock guarantees a snapshot_id, and mixed
            # snapshots cannot safely form one catalog.
            if len(snapshot_candidates) == 1:
                snapshot_id = next(iter(snapshot_candidates))
    if not snapshot_id:
        raise ProcedureCatalogError("snapshot_missing", "无法确定当前提取快照")
    if graph is not None and graph.snapshot_id != snapshot_id:
        raise ProcedureCatalogError(
            "snapshot_scope_mismatch", "期别适用图与目录快照不一致"
        )
    if any(block.snapshot_id != snapshot_id for block in projection.blocks):
        raise ProcedureCatalogError(
            "snapshot_scope_mismatch", "期别投影与目录快照不一致"
        )
    for span in spans_by_ref.values():
        if span.snapshot_id != snapshot_id:
            raise ProcedureCatalogError(
                "snapshot_scope_mismatch", "来源片段与目录快照不一致"
            )

    selected_refs = _selected_refs(projection, spans_by_id=spans_by_id)
    roots = sorted(
        (block for block in blocks if block.kind == BlockKind.TABLE),
        key=lambda item: (item.block_order, item.source_ref),
    )
    all_instances: list[_OperationInstance] = []
    structural_roots = 0
    for root in roots:
        max_columns = root.table_cols or 0
        cells = _make_cells(blocks, root)
        if cells:
            max_columns = max(max_columns, max(col for _row, col in cells) + 1)
            max_rows = max(root.table_rows or 0, max(row for row, _col in cells) + 1)
        else:
            max_rows = root.table_rows or 0
        looks_like_flow, all_marks, _first_mark_row = _table_looks_like_flow(
            root,
            cells,
            max_rows=max_rows,
            max_columns=max_columns,
        )
        if not looks_like_flow:
            continue
        selected_marks = [
            cell
            for cell in all_marks
            if any(ref in selected_refs for ref in cell.source_refs)
        ]
        if not selected_marks:
            # The table may belong exclusively to the other study phase.  The
            # projection, not the table number or procedure wording, decides
            # whether it is in scope.
            continue
        structural_roots += 1
        all_instances.extend(
            _build_instances_for_table(
                root,
                cells,
                all_marks=all_marks,
                selected_refs=selected_refs,
                max_columns=max_columns,
                spans_by_ref=spans_by_ref,
                blocks_by_ref=blocks_by_ref,
                snapshot_id=snapshot_id,
            )
        )
    if structural_roots == 0 or not all_instances:
        raise ProcedureCatalogError(
            "flow_table_empty" if structural_roots else "flow_table_missing",
            "未找到当前选定期别中结构完整且含基线及以前必做"
            "操作的研究流程表",
        )

    # Deduplication is structural: phase + original visit instance + source
    # row (and table root to avoid merging equal rows from separate tables).
    # Similar labels never participate in the key.
    grouped: dict[tuple[str, str, str, str, int, int], _OperationInstance] = {}
    for instance in all_instances:
        key = (
            phase.value,
            instance.root,
            instance.visit.stage.value,
            _normalized_header_key(instance.visit.original_text),
            instance.row,
            instance.visit.column,
        )
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = instance
            continue
        # A duplicated physical mark under the same merged visit is one
        # instance, but both source ranges remain attached for auditability.
        grouped[key] = _OperationInstance(
            root=existing.root,
            row=existing.row,
            operation=existing.operation,
            operation_refs=tuple(
                dict.fromkeys((*existing.operation_refs, *instance.operation_refs))
            ),
            visit=existing.visit,
            source_span_ids=tuple(
                dict.fromkeys((*existing.source_span_ids, *instance.source_span_ids))
            ),
            position_hint=min(existing.position_hint, instance.position_hint),
        )

    ordered_instances = sorted(
        grouped.values(),
        key=lambda item: (
            item.position_hint,
            _STAGE_ORDER[item.visit.stage],
            _normalized_header_key(item.visit.original_text),
            item.operation,
        ),
    )
    items: list[FrozenCatalogItem] = []
    for position, instance in enumerate(ordered_instances):
        source_ids = _source_ids_for_instance(
            instance,
            spans_by_ref=spans_by_ref,
            blocks_by_ref=blocks_by_ref,
            snapshot_id=snapshot_id,
        )
        item_key = (
            CATALOG_BUILDER_VERSION,
            snapshot_id,
            phase.value,
            instance.root,
            instance.row,
            instance.visit.column,
            instance.visit.stage.value,
            _normalized_header_key(instance.visit.original_text),
            instance.operation,
            instance.operation_refs,
            source_ids,
        )
        item_id = f"procedure:{_short_digest(*item_key)}"
        items.append(
            FrozenCatalogItem(
                item_id=item_id,
                kind=CatalogItemKind.REQUIRED_PROCEDURE,
                label=instance.operation,
                visit_instance=instance.visit.original_text,
                review_stage=instance.visit.stage,
                position=position,
                source_span_ids=list(source_ids),
            )
        )

    catalog_signature = tuple(item.item_id for item in items)
    catalog_id = (
        f"catalog:{CatalogKind.REQUIRED_PROCEDURES.value}:"
        f"{_short_digest(CATALOG_BUILDER_VERSION, snapshot_id, phase.value, catalog_signature)}"
    )
    frozen_timestamp = frozen_at or _DEFAULT_FROZEN_AT
    if frozen_timestamp.tzinfo is None:
        raise ProcedureCatalogError("timestamp_invalid", "frozen_at 必须带时区")
    if not frozen_by.strip():
        raise ProcedureCatalogError("freezer_invalid", "frozen_by 不能为空")
    payload: dict[str, Any] = {
        "catalog_id": catalog_id,
        "snapshot_id": snapshot_id,
        "catalog_kind": CatalogKind.REQUIRED_PROCEDURES,
        "study_phase": phase,
        "items": tuple(items),
        "frozen_at": frozen_timestamp,
        "frozen_by": frozen_by,
        "schema_version": "fixture/v1",
    }
    # The contract hashes the serialized model excluding catalog_sha256.  Use
    # the same exact representation rather than hashing an ad-hoc item list.
    payload["catalog_sha256"] = canonical_hash(
        FrozenProtocolCatalog.model_construct(**payload)
        .model_dump(mode="json", exclude={"catalog_sha256"})
    )
    return FrozenProtocolCatalog.model_validate(payload)


freeze_required_procedure_catalog = build_required_procedure_catalog
build_procedure_catalog = build_required_procedure_catalog
build_required_procedures_catalog = build_required_procedure_catalog
freeze_required_procedures_catalog = build_required_procedure_catalog
freeze_procedure_catalog = build_required_procedure_catalog
freeze_required_procedures = build_required_procedure_catalog
CatalogBuildError = ProcedureCatalogError


__all__ = [
    "CATALOG_BUILDER_VERSION",
    "CatalogBuildError",
    "CatalogValidationError",
    "ProcedureCatalogBuildError",
    "ProcedureCatalogError",
    "RequiredProcedureCatalogBuildError",
    "RequiredProcedureCatalogError",
    "build_procedure_catalog",
    "build_required_procedure_catalog",
    "build_required_procedures_catalog",
    "derive_review_stage",
    "freeze_procedure_catalog",
    "freeze_required_procedure_catalog",
    "freeze_required_procedures",
    "freeze_required_procedures_catalog",
]
