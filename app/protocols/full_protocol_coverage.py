"""确定性全文结构单元覆盖清单骨架（Phase 5 Slice 5.8a）。

从现有 :class:`~app.protocols.docx_structure.StructureBlock` 与单期
:class:`~app.domain.contracts.protocol_metadata.PhaseProjection` 生成
:class:`~app.domain.contracts.protocol_controls.ProtocolSectionCoverageManifest`。

本模块只做确定性骨架：

- 保留标题路径、表格行列语境、来源定位与原文顺序；
- 关键词只影响 ``priority_rank`` / ``priority_keyword_hits``，不得过滤未命中单元；
- 不调用模型、不写存储、不生成处置或发布控制；
- ``claims_full_coverage`` 恒为 False，``dispositions`` 为空——处置由后续 Agent/门禁层完成。
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Mapping, Sequence

from app.domain.contracts.enums import (
    ApplicabilityGranularity,
    DocumentPart,
    PhaseScope,
    StudyPhase,
)
from app.domain.contracts.protocol_controls import (
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    StructureUnitKind,
    TableCellContext,
)
from app.domain.contracts.phase_applicability import (
    PhaseApplicabilityDisposition,
    PhaseApplicabilityResolutionSet,
)
from app.domain.contracts.protocol_metadata import (
    PhaseApplicabilityBlock,
    PhaseApplicabilityGraph,
    PhaseProjection,
)

from .docx_structure import BlockKind, StructureBlock
from .phase_applicability import check_phase_applicability_resolution
from .phase_applicability_planning import PhaseApplicabilityFrozenPlan
from .phase_detection import _scope_from_text as _phase_scope_from_text

__all__ = [
    "FullProtocolCoverageError",
    "FullProtocolCoverageResolutionIssue",
    "FullProtocolCoverageResolutionView",
    "build_full_protocol_coverage_manifest",
    "build_resolved_full_protocol_coverage_view",
    "expand_projection_structure_refs",
    "resolve_full_protocol_coverage",
]

# 与 procedure_catalog / phase_detection 一致：嵌套表取最后一个 r/c 匹配。
_CELL_REF_RE = re.compile(
    r"^(?P<table>.*\.t\d+)\.r(?P<row>\d+)\.c(?P<col>\d+)(?:\.p\d+)?$"
)
_NOTE_LEAD_RE = re.compile(
    r"^(?:注|註|备注|備註|脚注|腳注|注释|註釋|footnote|note)\s*[:：．.\d)]*",
    re.IGNORECASE,
)
# 表题通常是紧邻表格的普通段落，而不是一个 Heading 样式段落。只接受
# 通用的“表/Table + 编号”形态，避免把正文中偶然提到“表”的句子抬升为
# 章节标题或把具体方案编号写进结构规则。
_TABLE_TITLE_RE = re.compile(
    r"^(?:表格?|table)\s*"
    r"(?:[0-9０-９]+(?:\s*[-－—.．]\s*[0-9０-９]+)*|"
    r"[一二三四五六七八九十百千万]+)"
    r"(?:\s|$|[：:、.．)）\-－—])",
    re.IGNORECASE,
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

# Paragraph atomization is source-boundary-only. Colons, slashes, parentheses,
# ratios, dose lists, and visit lists are deliberately excluded. A comma is a
# boundary only when the text on both sides forms a different concrete phase
# clause.  The second clause may start with shared subject wording before its
# phase marker (for example, "筛选合格的Ⅲ期参与者").
_PARAGRAPH_STRONG_BOUNDARY_RE = re.compile(r"[。！？!?；;\n]+")
_PARAGRAPH_STRONG_SEPARATOR_ONLY_RE = re.compile(r"^[\s。！？!?；;]+$")
_PARAGRAPH_PHASE_HANDOFF_RE = re.compile(r"[，,]")
_PARAGRAPH_PHASE_MARKER_RE = re.compile(
    r"(?:Ⅱ|II|2|二|Ⅲ|III|3|三)\s*期", re.IGNORECASE
)


class FullProtocolCoverageError(ValueError):
    """全文覆盖清单构建失败。"""


@dataclass(frozen=True)
class FullProtocolCoverageResolutionIssue:
    """One deterministic problem in the non-mutating semantic view."""

    code: str
    message: str
    structure_unit_id: str | None = None
    package_id: str | None = None


@dataclass(frozen=True)
class FullProtocolCoverageResolutionView:
    """Resolved phase view over an immutable full-protocol manifest.

    ``coverage_manifest`` remains the original frozen source view.  The
    semantic result is carried separately as ``phase_dispositions``; no
    ``ProtocolStructureUnit.phase_scopes`` value is rewritten in place (or in
    a copied manifest).  The view may intentionally be incomplete so callers
    can inspect pending units before the publication gate rejects it.
    """

    coverage_manifest: ProtocolSectionCoverageManifest
    phase_plan: PhaseApplicabilityFrozenPlan
    resolution_sets: tuple[PhaseApplicabilityResolutionSet, ...]
    phase_dispositions: tuple[tuple[str, PhaseApplicabilityDisposition], ...]
    pending_structure_unit_ids: tuple[str, ...]
    phase_excluded_structure_unit_ids: tuple[str, ...]
    issues: tuple[FullProtocolCoverageResolutionIssue, ...] = ()

    @property
    def source_manifest(self) -> ProtocolSectionCoverageManifest:
        """Alias making the source/resolved boundary explicit to callers."""

        return self.coverage_manifest

    @property
    def resolution_by_unit(self) -> dict[str, PhaseApplicabilityDisposition]:
        return dict(self.phase_dispositions)

    @property
    def accepted(self) -> bool:
        unit_ids = {unit.structure_unit_id for unit in self.coverage_manifest.units}
        return (
            not self.issues
            and not self.pending_structure_unit_ids
            and set(self.resolution_by_unit) == unit_ids
        )

    @property
    def claims_full_coverage(self) -> bool:
        """Whether the semantic result view, rather than its source list, is complete."""

        return self.accepted

    def disposition_for(self, structure_unit_id: str) -> PhaseApplicabilityDisposition | None:
        return self.resolution_by_unit.get(structure_unit_id)

    def require_publishable(self) -> "FullProtocolCoverageResolutionView":
        """Raise the same hard stop the publication boundary must enforce."""

        if self.accepted:
            return self
        if self.issues:
            issue = self.issues[0]
            raise FullProtocolCoverageError(
                f"{issue.code}: {issue.message}"
                + (f" [{issue.structure_unit_id}]" if issue.structure_unit_id else "")
            )
        pending = ",".join(self.pending_structure_unit_ids)
        raise FullProtocolCoverageError(
            "PHASE_APPLICABILITY_UNRESOLVED: 仍有未完成期别语义结果：" + pending
        )


@dataclass(frozen=True)
class _ParagraphCoverageAtom:
    """One deterministic, source-ordered slice of a mixed paragraph.

    The raw paragraph remains the source of truth.  ``source_ref`` is a
    derived locator used only to give the atom a distinct coverage identity;
    ``parent_source_ref`` is retained for graph/span lookup and member
    ownership.  Character offsets are internal so normalization never causes
    two atoms to claim the same source text.
    """

    source_ref: str
    parent_source_ref: str
    text: str
    phase_scopes: tuple[PhaseScope, ...]
    ordinal: int
    start: int
    end: int


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"su-{digest}"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _phase_marker_scope(match: re.Match[str]) -> PhaseScope:
    marker = match.group(0).upper()
    return (
        PhaseScope.PHASE_III
        if "Ⅲ" in marker or "III" in marker or marker.startswith(("3", "三"))
        else PhaseScope.PHASE_II
    )


def _paragraph_clauses(text: str) -> list[tuple[int, int]]:
    """Return non-empty source ranges split by safe source boundaries."""

    ranges: list[tuple[int, int]] = []
    cursor = 0
    boundaries = sorted(
        (
            *((match.start(), match.end(), False) for match in _PARAGRAPH_STRONG_BOUNDARY_RE.finditer(text)),
            *((match.start(), match.end(), True) for match in _PARAGRAPH_PHASE_HANDOFF_RE.finditer(text)),
        ),
        key=lambda item: (item[0], item[1]),
    )
    for _start, end, is_phase_handoff in boundaries:
        if end <= cursor:
            continue
        segment = text[cursor:end]
        if is_phase_handoff:
            left_scopes, _ = _phase_scope_from_text(_normalize(segment))
            next_strong = _PARAGRAPH_STRONG_BOUNDARY_RE.search(text, end)
            right_end = next_strong.end() if next_strong is not None else len(text)
            right_segment = text[end:right_end]
            right_phase = _PARAGRAPH_PHASE_MARKER_RE.search(right_segment)
            left_phases = tuple(_PARAGRAPH_PHASE_MARKER_RE.finditer(segment))
            repeated_prefix = (
                right_phase is not None
                and bool(left_phases)
                and bool((prefix := _normalize(right_segment[: right_phase.start()])))
                and _normalize(segment[: left_phases[-1].start()]).endswith(prefix)
            )
            direct_phase = right_phase is not None and not _normalize(
                right_segment[: right_phase.start()]
            )
            concrete = {PhaseScope.PHASE_II, PhaseScope.PHASE_III}
            right_primary_scope = (
                _phase_marker_scope(right_phase) if right_phase is not None else None
            )
            if (
                len(left_scopes) != 1
                or left_scopes[0] not in concrete
                or right_primary_scope not in concrete
                or left_scopes[0] == right_primary_scope
                or not (direct_phase or repeated_prefix)
            ):
                continue
        if _normalize(segment) and not _PARAGRAPH_STRONG_SEPARATOR_ONLY_RE.fullmatch(
            segment
        ):
            ranges.append((cursor, end))
        elif ranges and _PARAGRAPH_STRONG_SEPARATOR_ONLY_RE.fullmatch(segment):
            # Preserve separator characters without manufacturing a clause
            # for whitespace/strong punctuation between two real clauses.
            previous_start, _previous_end = ranges[-1]
            ranges[-1] = (previous_start, end)
        else:
            # Keep leading separators attached to the first real source
            # clause instead of dropping them from the replay range.
            continue
        cursor = end
    if _normalize(text[cursor:]):
        ranges.append((cursor, len(text)))
    return ranges


def _paragraph_clause_groups(
    text: str,
) -> tuple[tuple[int, int, tuple[PhaseScope, ...]], ...]:
    """Classify and coalesce adjacent complete strong-boundary clauses."""

    groups: list[tuple[int, int, tuple[PhaseScope, ...]]] = []
    for start, end in _paragraph_clauses(text):
        segment = _normalize(text[start:end])
        scopes, _ = _phase_scope_from_text(segment)
        if start > 0 and text[start - 1] in "，," and scopes == (PhaseScope.MIXED,):
            first_phase = _PARAGRAPH_PHASE_MARKER_RE.search(segment)
            if first_phase is not None:
                scopes = (_phase_marker_scope(first_phase),)
        if groups and groups[-1][1] == start and groups[-1][2] == scopes:
            previous_start, _previous_end, previous_scopes = groups[-1]
            groups[-1] = (previous_start, end, previous_scopes)
        else:
            groups.append((start, end, scopes))
    return tuple(groups)


def _paragraph_atom_slices(
    block: StructureBlock,
    graph_block: PhaseApplicabilityBlock | None,
) -> tuple[_ParagraphCoverageAtom, ...]:
    """Split only separable mixed body prose into disjoint source slices.

    The phase graph remains authoritative for deciding whether atomization is
    needed.  Each complete strong-boundary clause is classified independently
    and adjacent equal signatures are coalesced.  No phase token can create a
    boundary inside one clause; if there are not at least two differing
    complete-clause signatures, the original paragraph remains one unit.
    """

    original = block.text
    normalized = _normalize(original)
    if not normalized:
        return ()

    graph_scopes = set(graph_block.phase_scopes) if graph_block is not None else set()
    if PhaseScope.MIXED not in graph_scopes:
        return (
            _ParagraphCoverageAtom(
                source_ref=block.source_ref,
                parent_source_ref=block.source_ref,
                text=normalized,
                phase_scopes=tuple(graph_block.phase_scopes)
                if graph_block is not None
                else (PhaseScope.UNKNOWN,),
                ordinal=0,
                start=0,
                end=len(original),
            ),
        )

    clause_groups = _paragraph_clause_groups(original)
    if len(clause_groups) < 2 or len({group[2] for group in clause_groups}) < 2:
        return (
            _ParagraphCoverageAtom(
                source_ref=block.source_ref,
                parent_source_ref=block.source_ref,
                text=normalized,
                phase_scopes=tuple(graph_block.phase_scopes)
                if graph_block is not None
                else (PhaseScope.UNKNOWN,),
                ordinal=0,
                start=0,
                end=len(original),
            ),
        )

    atoms: list[_ParagraphCoverageAtom] = []
    for ordinal, (start, end, scopes) in enumerate(clause_groups):
        segment = _normalize(original[start:end])
        if not segment:
            continue
        atoms.append(
            _ParagraphCoverageAtom(
                source_ref=f"{block.source_ref}#atom-{start}-{end}",
                parent_source_ref=block.source_ref,
                text=segment,
                phase_scopes=tuple(scopes),
                ordinal=ordinal,
                start=start,
                end=end,
            )
        )

    # An implementation edge case must never replace a valid source paragraph
    # with a partial inventory entry.
    if len(atoms) < 2:
        return (
            _ParagraphCoverageAtom(
                source_ref=block.source_ref,
                parent_source_ref=block.source_ref,
                text=normalized,
                phase_scopes=tuple(graph_block.phase_scopes)
                if graph_block is not None
                else (PhaseScope.UNKNOWN,),
                ordinal=0,
                start=0,
                end=len(original),
            ),
        )
    return tuple(atoms)


def _is_heading_block(block: StructureBlock) -> bool:
    """只按结构化 ``outline_level`` 识别标题。

    ``style``/``style_name`` 是来源元数据，不能作为标题判据：真实方案会
    使用数字样式 ID 和中文自定义样式名。编号列表也不能因为有编号或文本
    看起来像标题而进入标题路径；只有 DOCX 结构通道解析出的 outline level
    才能建立层级。
    """

    text = _normalize(block.text)
    if not text or len(text) > 120:
        return False
    if block.table_path is not None or block.document_part != DocumentPart.BODY:
        return False
    level = block.outline_level
    return isinstance(level, int) and 0 <= level <= 8


def _heading_level(block: StructureBlock) -> int:
    if not _is_heading_block(block):
        return 0
    # OOXML outlineLvl is zero-based: 0 is the first outline level.
    level = block.outline_level
    return (level + 1) if level is not None else 0


def _looks_like_list_item(block: StructureBlock) -> bool:
    return block.numbering is not None and not _is_heading_block(block)


def _looks_like_table_title(text: str) -> bool:
    """判断一个普通段落是否是结构上的表题候选。"""

    value = _normalize(text)
    return bool(value) and len(value) <= 200 and _TABLE_TITLE_RE.match(value) is not None


def _looks_like_note_text(text: str) -> bool:
    value = _normalize(text)
    if not value:
        return False
    if _NOTE_LEAD_RE.match(value):
        return True
    # DOCX 上标脚注在结构层常表现为尾部 ^N。
    return bool(re.search(r"\^\d+\s*$", value)) and len(value) <= 200


def _cell_location(block: StructureBlock) -> tuple[str, int, int] | None:
    """返回 (table_root, row, col)；嵌套表取最内层单元格。"""

    match = _CELL_REF_RE.fullmatch(block.source_ref)
    if match:
        return match.group("table"), int(match.group("row")), int(match.group("col"))
    if block.table_path is not None and len(block.table_path) >= 2:
        row, col = block.table_path[-2], block.table_path[-1]
        return block.source_ref.rsplit(".r", 1)[0], row, col
    return None


def _cell_path(block: StructureBlock) -> tuple[int, ...] | None:
    """返回完整单元格路径，并兼容旧块集缺失 ``table_path`` 的情况。"""

    if block.table_path is not None and len(block.table_path) >= 2:
        return tuple(block.table_path)
    coordinates = re.findall(r"\.r(\d+)\.c(\d+)(?=\.t\d+|\.p\d+$)", block.source_ref)
    if not coordinates:
        return None
    path: list[int] = []
    for row, col in coordinates:
        path.extend((int(row), int(col)))
    return tuple(path)


def _structure_ref_matches_aggregate(
    block: StructureBlock,
    aggregate: PhaseApplicabilityBlock,
) -> bool:
    location = _cell_location(block)
    if location is None:
        return False
    table, row, col = location
    if aggregate.granularity == ApplicabilityGranularity.TABLE_ROW:
        expected = f"{table}.r{row}"
        if aggregate.table_row is not None and aggregate.table_row != row:
            return False
        return aggregate.source_ref == expected
    if aggregate.granularity == ApplicabilityGranularity.VISIT_COLUMN:
        expected = f"{table}.c{col}"
        if aggregate.visit_column is not None and aggregate.visit_column != col:
            return False
        return aggregate.source_ref == expected
    return False


def expand_projection_structure_refs(
    projection: PhaseProjection,
    blocks: Sequence[StructureBlock],
) -> frozenset[str]:
    """将单期投影展开为应覆盖的原子 StructureBlock ``source_ref`` 集合。

    聚合行/访视列展开为其下属单元格段落；关键词不参与过滤。
    """

    included: set[str] = set()
    paragraph_blocks = [
        block
        for block in blocks
        if block.kind == BlockKind.PARAGRAPH and _normalize(block.text)
    ]
    for item in projection.blocks:
        if not item.is_aggregate:
            included.add(item.source_ref)
            continue
        for block in paragraph_blocks:
            if _structure_ref_matches_aggregate(block, item):
                included.add(block.source_ref)
    return frozenset(included)


def _heading_paths(blocks: Sequence[StructureBlock]) -> dict[str, list[str]]:
    """按原文顺序为每个段落块计算标题路径（含表格内段落）。"""

    ordered = sorted(blocks, key=lambda item: (item.block_order, item.source_ref))
    stack: list[str] = []
    result: dict[str, list[str]] = {}
    for block in ordered:
        if block.kind != BlockKind.PARAGRAPH:
            continue
        text = _normalize(block.text)
        if not text:
            continue
        if block.table_path is None and _is_heading_block(block):
            level = _heading_level(block)
            stack = stack[: max(level - 1, 0)]
            while len(stack) < level - 1:
                stack.append("（上级标题未识别）")
            stack.append(text)
            result[block.source_ref] = list(stack)
            continue
        result[block.source_ref] = list(stack) if stack else ["（无标题）"]
    return result


def _table_heading_paths(
    blocks: Sequence[StructureBlock],
    heading_paths: Mapping[str, list[str]],
) -> dict[str, list[str]]:
    """为每个表根建立章节 + 表题路径。

    表题在 DOCX 中经常是一个普通、居中的段落，不能依赖其样式名。对顶层
    表只取同一正文流中紧邻表根之前的非空段落；若该段落符合通用表题形态，
    就把它追加到当前章节路径。嵌套表继承最近外层表路径，并允许在所属
    单元格中识别一个紧邻的表题。这样表格行能保留真实上位章节和表题，且
    不会把表题扩散为后续普通正文的章节。
    """

    paragraph_blocks = sorted(
        (
            block
            for block in blocks
            if block.kind == BlockKind.PARAGRAPH
            and block.document_part == DocumentPart.BODY
            and _normalize(block.text)
        ),
        key=lambda item: (item.block_order, item.source_ref),
    )
    table_blocks = sorted(
        (block for block in blocks if block.kind == BlockKind.TABLE),
        key=lambda item: (
            len(item.table_path or ()),
            item.block_order,
            item.source_ref,
        ),
    )
    paths: dict[str, list[str]] = {}

    def _ancestor(table: StructureBlock) -> StructureBlock | None:
        table_path = tuple(table.table_path or ())
        candidates = [
            candidate
            for candidate in table_blocks
            if candidate.source_ref != table.source_ref
            and table.source_ref.startswith(candidate.source_ref + ".r")
            and len(table_path) == len(candidate.table_path or ()) + 2
        ]
        return max(candidates, key=lambda item: len(item.source_ref), default=None)

    for table in table_blocks:
        ancestor = _ancestor(table)
        ancestor_path = paths.get(ancestor.source_ref) if ancestor is not None else None
        scope_path = tuple(table.table_path or ())
        prior = [
            block
            for block in paragraph_blocks
            if block.block_order < table.block_order
            and (
                (block.table_path is None and not scope_path)
                or (
                    scope_path
                    and block.table_path is not None
                    and tuple(block.table_path) == scope_path
                )
            )
        ]
        previous = prior[-1] if prior else None
        base = (
            list(heading_paths.get(previous.source_ref, []))
            if previous is not None
            else list(ancestor_path or ["（无标题）"])
        )
        if not base:
            base = list(ancestor_path or ["（无标题）"])

        if (
            previous is not None
            and previous.numbering is None
            and _looks_like_table_title(previous.text)
        ):
            title = _normalize(previous.text)
            if title not in base:
                base.append(title)
        elif ancestor_path is not None:
            # Non-title prose in an outer cell is not a new chapter for an inner
            # table. Keep the outer table's proven context.
            base = list(ancestor_path)
        paths[table.source_ref] = base
    return paths


def _table_column_headers(
    cells_by_row: Mapping[int, list[StructureBlock]],
    column_index: int,
) -> list[str]:
    header_row = cells_by_row.get(0, [])
    headers: list[str] = []
    for cell in sorted(header_row, key=lambda item: item.table_path or ()):
        location = _cell_location(cell)
        if location is None or location[2] != column_index:
            continue
        value = _normalize(cell.text)
        if value:
            headers.append(value)
    return headers


def _table_row_headers(
    cells_by_row: Mapping[int, list[StructureBlock]],
    row_index: int,
) -> list[str]:
    """取该行首列非空文本作为行表头语境。"""

    row_cells = cells_by_row.get(row_index, [])
    for cell in sorted(row_cells, key=lambda item: item.table_path or ()):
        location = _cell_location(cell)
        if location is None or location[2] != 0:
            continue
        value = _normalize(cell.text)
        if value:
            return [value]
    return []


def _classify_table_row(
    row_index: int,
    cells: Sequence[StructureBlock],
) -> StructureUnitKind:
    joined = " | ".join(_normalize(cell.text) for cell in cells if _normalize(cell.text))
    if _looks_like_note_text(joined):
        return StructureUnitKind.TABLE_NOTE
    if row_index == 0:
        return StructureUnitKind.TABLE_HEADER
    return StructureUnitKind.TABLE_ROW


def _table_row_requires_atomization(
    cells: Sequence[StructureBlock],
    graph_blocks: Mapping[str, PhaseApplicabilityBlock],
) -> bool:
    """Return whether a row must be represented by one unit per cell paragraph.

    A table row remains a useful source unit when every member has the same
    single phase signature, including the unresolved ``(UNKNOWN,)`` signature.
    The full coverage manifest includes opposite-phase and unresolved source
    members by design, so a row aggregate must not hide a disagreement between
    members.  A member with multiple scopes, an explicit ``MIXED`` scope, a
    missing graph block, or an explicit cross-phase comparison is split even if
    its neighboring members otherwise agree.
    """

    signatures: list[tuple[PhaseScope, ...]] = []
    for cell in cells:
        block = graph_blocks.get(cell.source_ref)
        if block is None:
            # Body cells are normally required to exist in the graph.  Keep the
            # fallback conservative for non-body/nested inputs: an absent phase
            # signal cannot justify treating the whole row as shared.
            return True
        scopes = tuple(block.phase_scopes)
        if (
            not scopes
            or len(set(scopes)) != 1
            or PhaseScope.MIXED in scopes
            or block.cross_phase_comparison
        ):
            return True
        signatures.append(scopes)

    return bool(signatures) and any(
        signature != signatures[0] for signature in signatures[1:]
    )


def _classify_body_unit(block: StructureBlock) -> StructureUnitKind:
    if block.document_part in {DocumentPart.FOOTNOTE, DocumentPart.ENDNOTE}:
        return StructureUnitKind.FOOTNOTE_OR_ANNOTATION
    if _looks_like_note_text(block.text) and block.document_part != DocumentPart.BODY:
        return StructureUnitKind.FOOTNOTE_OR_ANNOTATION
    if _looks_like_list_item(block):
        return StructureUnitKind.LIST_ITEM
    if _looks_like_note_text(block.text):
        return StructureUnitKind.FOOTNOTE_OR_ANNOTATION
    return StructureUnitKind.PARAGRAPH


def _priority_hits(excerpt: str, keywords: Sequence[str]) -> list[str]:
    haystack = excerpt.casefold()
    hits: list[str] = []
    for keyword in keywords:
        token = keyword.strip()
        if not token:
            continue
        if token.casefold() in haystack and token not in hits:
            hits.append(token)
    return hits


def _span_ids_for(
    source_refs: Sequence[str],
    source_span_ids: Mapping[str, str | Sequence[str]] | None,
    graph_blocks: Mapping[str, PhaseApplicabilityBlock],
) -> list[str]:
    values: set[str] = set()
    for source_ref in source_refs:
        override = source_span_ids.get(source_ref) if source_span_ids else None
        if override is None:
            graph_block = graph_blocks.get(source_ref)
            if graph_block is None:
                raise FullProtocolCoverageError(
                    "期别适用图外结构单元必须显式提供来源片段：" + source_ref
                )
            values.update(graph_block.source_span_ids)
            continue
        candidates = [override] if isinstance(override, str) else override
        values.update(value.strip() for value in candidates if value.strip())
    return sorted(values)


def _atomic_phase_blocks(
    graph: PhaseApplicabilityGraph,
) -> dict[str, PhaseApplicabilityBlock]:
    return {
        item.source_ref: item
        for item in graph.blocks
        if not item.is_aggregate
    }


def _phase_scopes_for(
    source_refs: Sequence[str],
    graph_blocks: Mapping[str, PhaseApplicabilityBlock],
) -> list[PhaseScope]:
    missing = [source_ref for source_ref in source_refs if source_ref not in graph_blocks]
    scopes = {
        scope
        for source_ref in source_refs
        if source_ref in graph_blocks
        for scope in graph_blocks[source_ref].phase_scopes
    }
    if missing:
        # 脚注、尾注和文本框可能不属于既有正文期别图；必须保留并待确认，不能丢弃。
        scopes.add(PhaseScope.UNKNOWN)
    return sorted(scopes, key=lambda item: item.value)


def _selected_phase_scope(selected_phase: StudyPhase) -> PhaseScope:
    return {
        StudyPhase.PHASE_II: PhaseScope.PHASE_II,
        StudyPhase.PHASE_III: PhaseScope.PHASE_III,
        StudyPhase.SEAMLESS_II_III: PhaseScope.SEAMLESS_CANDIDATE,
    }[selected_phase]


def _opposite_phase_scope(selected_phase: StudyPhase) -> PhaseScope | None:
    return {
        StudyPhase.PHASE_II: PhaseScope.PHASE_III,
        StudyPhase.PHASE_III: PhaseScope.PHASE_II,
        StudyPhase.SEAMLESS_II_III: None,
    }[selected_phase]


def _structural_phase_disposition(
    selected_phase: StudyPhase,
    unit: ProtocolStructureUnit,
) -> PhaseApplicabilityDisposition | None:
    """Return a disposition only for one structurally explicit scope."""

    scopes = set(unit.phase_scopes)
    if len(scopes) != 1 or scopes & {PhaseScope.UNKNOWN, PhaseScope.MIXED}:
        return None
    scope = next(iter(scopes))
    if scope == _selected_phase_scope(selected_phase):
        return PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE
    if scope == PhaseScope.SHARED:
        return PhaseApplicabilityDisposition.CROSS_PHASE_SHARED
    if scope == _opposite_phase_scope(selected_phase):
        return PhaseApplicabilityDisposition.OPPOSITE_PHASE_APPLICABLE
    return None


def _same_frozen_structure_unit(
    package_unit: ProtocolStructureUnit,
    manifest_unit: ProtocolStructureUnit,
) -> bool:
    """Compare the complete source payload, not only the stable unit ID."""

    if not isinstance(package_unit, ProtocolStructureUnit):
        return False
    if not isinstance(manifest_unit, ProtocolStructureUnit):
        return False
    return package_unit.model_dump(mode="json") == manifest_unit.model_dump(mode="json")


def build_resolved_full_protocol_coverage_view(
    coverage_manifest: ProtocolSectionCoverageManifest,
    phase_plan: PhaseApplicabilityFrozenPlan,
    phase_applicability_resolutions: Sequence[PhaseApplicabilityResolutionSet] = (),
) -> FullProtocolCoverageResolutionView:
    """Aggregate semantic results without rewriting a frozen coverage manifest.

    The planner owns ambiguous-unit membership and package boundaries.  This
    function only joins each package's already-hydrated result set back to
    those system-owned units, validates the package gate, and exposes a
    read-only resolved view.  A missing or unresolved result is represented as
    pending so the caller can inspect the gap; publication must still reject
    the view through :meth:`FullProtocolCoverageResolutionView.require_publishable`.
    """

    if not isinstance(coverage_manifest, ProtocolSectionCoverageManifest):
        raise FullProtocolCoverageError("全文覆盖清单类型不正确")
    if not isinstance(phase_plan, PhaseApplicabilityFrozenPlan):
        raise FullProtocolCoverageError("期别语义计划类型不正确")

    resolution_sets = tuple(phase_applicability_resolutions or ())
    units = tuple(coverage_manifest.units)
    units_by_id = {unit.structure_unit_id: unit for unit in units}
    unit_ids = [unit.structure_unit_id for unit in units]
    expected_ambiguous_ids = [
        unit.structure_unit_id
        for unit in units
        if _structural_phase_disposition(coverage_manifest.study_phase, unit) is None
    ]
    issues: list[FullProtocolCoverageResolutionIssue] = []

    def add_issue(
        code: str,
        message: str,
        *,
        structure_unit_id: str | None = None,
        package_id: str | None = None,
    ) -> None:
        issues.append(
            FullProtocolCoverageResolutionIssue(
                code=code,
                message=message,
                structure_unit_id=structure_unit_id,
                package_id=package_id,
            )
        )

    if phase_plan.coverage_manifest_id != coverage_manifest.manifest_id:
        add_issue(
            "PHASE_PLAN_MANIFEST_MISMATCH",
            "期别语义计划未绑定当前全文覆盖清单",
        )
    if phase_plan.protocol_version_id != coverage_manifest.protocol_version_id:
        add_issue(
            "PHASE_PLAN_PROTOCOL_VERSION_MISMATCH",
            "期别语义计划未绑定当前方案版本",
        )
    if phase_plan.study_phase != coverage_manifest.study_phase:
        add_issue(
            "PHASE_PLAN_PHASE_MISMATCH",
            "期别语义计划未绑定当前选定期别",
        )
    if list(phase_plan.expected_structure_unit_ids) != expected_ambiguous_ids:
        add_issue(
            "PHASE_PLAN_SCOPE_MISMATCH",
            "期别语义计划必须逐项覆盖且仅覆盖全文清单中的模糊结构单元",
        )

    planned_owned_ids = [
        unit.structure_unit_id
        for package in phase_plan.packages
        for unit in package.owned_units
    ]
    if planned_owned_ids != list(phase_plan.expected_structure_unit_ids):
        add_issue(
            "PHASE_PLAN_OWNED_SCOPE_MISMATCH",
            "期别语义计划的本批待判断结构单元未完整覆盖全文清单",
        )

    packages_by_id = {package.package_id: package for package in phase_plan.packages}
    resolutions_by_package: dict[str, PhaseApplicabilityResolutionSet] = {}
    for resolution in resolution_sets:
        if not isinstance(resolution, PhaseApplicabilityResolutionSet):
            add_issue("PHASE_RESOLUTION_TYPE_INVALID", "期别语义结果集类型不正确")
            continue
        package_id = resolution.package_id
        if package_id not in packages_by_id:
            add_issue(
                "PHASE_RESOLUTION_PACKAGE_UNKNOWN",
                "期别语义结果集不属于当前冻结计划",
                package_id=package_id,
            )
            continue
        if package_id in resolutions_by_package:
            add_issue(
                "PHASE_RESOLUTION_PACKAGE_DUPLICATE",
                "同一冻结期别语义批次不得提供多个结果集",
                package_id=package_id,
            )
            continue
        resolutions_by_package[package_id] = resolution

    phase_dispositions: dict[str, PhaseApplicabilityDisposition] = {
        unit.structure_unit_id: disposition
        for unit in units
        if (
            disposition := _structural_phase_disposition(
                coverage_manifest.study_phase,
                unit,
            )
        )
        is not None
    }
    accepted_semantic_ids: set[str] = set()
    pending_ids: set[str] = set()

    for package in phase_plan.packages:
        owned_unit_ids = [unit.structure_unit_id for unit in package.owned_units]
        package_units = (*package.owned_units, *package.context_units)
        package_unit_ids = [unit.structure_unit_id for unit in package_units]
        package_integrity_ok = True

        package_identity_checks = (
            (
                "PHASE_PACKAGE_MANIFEST_MISMATCH",
                package.coverage_manifest_id != coverage_manifest.manifest_id,
                "冻结语义批次未绑定当前全文覆盖清单",
            ),
            (
                "PHASE_PACKAGE_PROTOCOL_VERSION_MISMATCH",
                package.protocol_version_id != coverage_manifest.protocol_version_id,
                "冻结语义批次未绑定当前方案版本",
            ),
            (
                "PHASE_PACKAGE_HASH_MISMATCH",
                package.protocol_document_sha256
                != coverage_manifest.protocol_document_sha256,
                "冻结语义批次未绑定当前方案原文哈希",
            ),
            (
                "PHASE_PACKAGE_SNAPSHOT_MISMATCH",
                package.snapshot_id != coverage_manifest.snapshot_id,
                "冻结语义批次未绑定当前证据快照",
            ),
            (
                "PHASE_PACKAGE_PHASE_MISMATCH",
                package.selected_phase != coverage_manifest.study_phase,
                "冻结语义批次未绑定当前选定期别",
            ),
        )
        for code, mismatch, message in package_identity_checks:
            if mismatch:
                add_issue(code, message, package_id=package.package_id)
                package_integrity_ok = False

        if len(package_unit_ids) != len(set(package_unit_ids)):
            add_issue(
                "PHASE_PACKAGE_SOURCE_UNIT_DUPLICATE",
                "冻结语义批次的结构单元身份重复",
                package_id=package.package_id,
            )
            package_integrity_ok = False

        for package_unit in package_units:
            unit_id = getattr(package_unit, "structure_unit_id", None)
            manifest_unit = units_by_id.get(unit_id)
            if manifest_unit is None:
                add_issue(
                    "PHASE_PACKAGE_UNIT_OUTSIDE_MANIFEST",
                    "冻结语义批次引用了当前全文覆盖清单之外的结构单元",
                    structure_unit_id=unit_id,
                    package_id=package.package_id,
                )
                package_integrity_ok = False
                continue
            if not _same_frozen_structure_unit(package_unit, manifest_unit):
                add_issue(
                    "PHASE_PACKAGE_SOURCE_UNIT_MISMATCH",
                    "冻结语义批次中的结构单元与当前全文覆盖清单的同名"
                    "结构单元不一致",
                    structure_unit_id=unit_id,
                    package_id=package.package_id,
                )
                package_integrity_ok = False

        if not package_integrity_ok:
            pending_ids.update(
                unit_id
                for unit_id in owned_unit_ids
                if unit_id in expected_ambiguous_ids
            )
            continue

        resolution = resolutions_by_package.get(package.package_id)
        if resolution is None:
            add_issue(
                "PHASE_APPLICABILITY_RESOLUTION_MISSING",
                "冻结语义批次尚未提供唯一水合结果",
                package_id=package.package_id,
            )
            pending_ids.update(owned_unit_ids)
            continue

        report = check_phase_applicability_resolution(package, resolution)
        if not report.accepted:
            for gate_issue in report.issues:
                add_issue(
                    gate_issue.code,
                    gate_issue.message,
                    structure_unit_id=gate_issue.structure_unit_id,
                    package_id=package.package_id,
                )
            pending_ids.update(owned_unit_ids)
            continue

        package_result_ids: set[str] = set()
        for result in resolution.results:
            unit_id = result.structure_unit_id
            if unit_id in package_result_ids or unit_id in accepted_semantic_ids:
                add_issue(
                    "PHASE_RESOLUTION_UNIT_DUPLICATE",
                    "同一模糊结构单元只能有一个接受的期别语义结果",
                    structure_unit_id=unit_id,
                    package_id=package.package_id,
                )
                pending_ids.add(unit_id)
                continue
            package_result_ids.add(unit_id)
            if unit_id not in units_by_id:
                add_issue(
                    "PHASE_RESOLUTION_UNIT_OUTSIDE_MANIFEST",
                    "期别语义结果引用了当前全文清单外的结构单元",
                    structure_unit_id=unit_id,
                    package_id=package.package_id,
                )
                pending_ids.add(unit_id)
                continue
            if unit_id not in expected_ambiguous_ids:
                add_issue(
                    "PHASE_RESOLUTION_UNIT_NOT_AMBIGUOUS",
                    "结构上已明确的单元不得通过语义结果覆盖原始期别范围",
                    structure_unit_id=unit_id,
                    package_id=package.package_id,
                )
                pending_ids.add(unit_id)
                continue

            if result.final_disposition == PhaseApplicabilityDisposition.UNRESOLVED:
                pending_ids.add(unit_id)
                phase_dispositions[unit_id] = result.final_disposition
                add_issue(
                    "PHASE_APPLICABILITY_UNRESOLVED",
                    result.unresolved_reason or "期别语义仍待确认",
                    structure_unit_id=unit_id,
                    package_id=package.package_id,
                )
                continue

            unit = units_by_id[unit_id]
            if (
                unit.unit_kind == StructureUnitKind.TABLE_ROW
                and len(unit.member_source_refs) > 1
                and PhaseScope.MIXED in set(unit.phase_scopes)
            ):
                # The current semantic contract resolves one structure unit at
                # a time and has no per-member result contract.  A mixed row
                # therefore cannot be flattened to one phase safely.
                pending_ids.add(unit_id)
                add_issue(
                    "MIXED_TABLE_ROW_MEMBER_RESOLUTION_REQUIRED",
                    "混合期别表格行必须逐成员证明同一处置，或通过明确的"
                    "来源成员合同拆分",
                    structure_unit_id=unit_id,
                    package_id=package.package_id,
                )
                continue

            phase_dispositions[unit_id] = result.final_disposition
            accepted_semantic_ids.add(unit_id)

        missing_result_ids = sorted(set(owned_unit_ids) - package_result_ids)
        for unit_id in missing_result_ids:
            if unit_id in units_by_id and unit_id in expected_ambiguous_ids:
                pending_ids.add(unit_id)

    pending_ids.update(set(expected_ambiguous_ids) - accepted_semantic_ids)
    pending_ids.intersection_update(set(unit_ids))
    ordered_pending = tuple(unit_id for unit_id in unit_ids if unit_id in pending_ids)
    ordered_dispositions = tuple(
        (unit_id, phase_dispositions[unit_id])
        for unit_id in unit_ids
        if unit_id in phase_dispositions
    )
    excluded = tuple(
        unit_id
        for unit_id, disposition in ordered_dispositions
        if disposition == PhaseApplicabilityDisposition.OPPOSITE_PHASE_APPLICABLE
    )
    return FullProtocolCoverageResolutionView(
        coverage_manifest=coverage_manifest,
        phase_plan=phase_plan,
        resolution_sets=resolution_sets,
        phase_dispositions=ordered_dispositions,
        pending_structure_unit_ids=ordered_pending,
        phase_excluded_structure_unit_ids=excluded,
        issues=tuple(issues),
    )


resolve_full_protocol_coverage = build_resolved_full_protocol_coverage_view


def build_full_protocol_coverage_manifest(
    blocks: Sequence[StructureBlock],
    projection: PhaseProjection,
    phase_graph: PhaseApplicabilityGraph,
    *,
    protocol_version_id: str,
    protocol_document_sha256: str,
    snapshot_id: str,
    manifest_id: str | None = None,
    source_span_ids: Mapping[str, str | Sequence[str]] | None = None,
    priority_keywords: Sequence[str] | None = None,
) -> ProtocolSectionCoverageManifest:
    """从结构块与单期投影生成全文结构单元覆盖清单骨架。

    Parameters
    ----------
    blocks:
        完整 StructureBlock 集。正文、脚注、尾注和文本框均进入覆盖清单；
        ``projection`` 只冻结本项目期别，不再充当内容过滤器。
    projection:
        ``project_single_phase`` 产出的选定期别投影。
    priority_keywords:
        仅用于优先级提示；不得缩小 ``units`` 成员资格。
    """

    if not protocol_version_id.strip():
        raise FullProtocolCoverageError("protocol_version_id 不得为空")
    if not _SHA256.fullmatch(protocol_document_sha256):
        raise FullProtocolCoverageError(
            "protocol_document_sha256 必须是 64 位小写十六进制"
        )
    if not snapshot_id.strip():
        raise FullProtocolCoverageError("snapshot_id 不得为空")
    if projection.selected_phase not in {
        StudyPhase.PHASE_II,
        StudyPhase.PHASE_III,
        StudyPhase.SEAMLESS_II_III,
    }:
        raise FullProtocolCoverageError(
            "覆盖清单必须绑定 II 期、III 期或已确认无缝期别"
        )
    if not blocks:
        raise FullProtocolCoverageError("没有结构块，不能建立覆盖清单")
    if not projection.blocks:
        raise FullProtocolCoverageError("单期投影为空，不能建立覆盖清单")
    if phase_graph.graph_id != projection.graph_id:
        raise FullProtocolCoverageError("期别适用图与单期投影身份不一致")
    if any(item.snapshot_id != snapshot_id for item in phase_graph.blocks):
        raise FullProtocolCoverageError("期别适用图与覆盖清单快照不一致")

    keywords = tuple(priority_keywords or ())
    eligible_parts = {
        DocumentPart.BODY,
        DocumentPart.FOOTNOTE,
        DocumentPart.ENDNOTE,
        DocumentPart.TEXTBOX,
    }
    included_refs = {
        block.source_ref
        for block in blocks
        if block.kind == BlockKind.PARAGRAPH
        and block.document_part in eligible_parts
        and _normalize(block.text)
    }
    if not included_refs:
        raise FullProtocolCoverageError("方案正文未产生任何可覆盖结构段落")

    blocks_by_ref = {block.source_ref: block for block in blocks}
    graph_blocks = _atomic_phase_blocks(phase_graph)
    missing_body_refs = sorted(
        source_ref
        for source_ref in included_refs
        if blocks_by_ref[source_ref].document_part == DocumentPart.BODY
        and source_ref not in graph_blocks
    )
    if missing_body_refs:
        raise FullProtocolCoverageError(
            "期别适用图外结构单元：" + ",".join(missing_body_refs)
        )
    heading_paths = _heading_paths(blocks)
    table_heading_paths = _table_heading_paths(blocks, heading_paths)

    table_rows: dict[tuple[str, int], list[StructureBlock]] = defaultdict(list)
    body_units: list[StructureBlock] = []
    for source_ref in sorted(
        included_refs,
        key=lambda ref: (
            blocks_by_ref[ref].block_order if ref in blocks_by_ref else 10**9,
            ref,
        ),
    ):
        block = blocks_by_ref.get(source_ref)
        if block is None:
            raise FullProtocolCoverageError(f"投影引用了缺失的结构块：{source_ref}")
        if block.kind != BlockKind.PARAGRAPH or not _normalize(block.text):
            continue
        location = _cell_location(block)
        if location is not None:
            table_root, row_index, _col = location
            table_rows[(table_root, row_index)].append(block)
        else:
            body_units.append(block)

    units: list[ProtocolStructureUnit] = []
    used_orders: set[int] = set()

    def _next_order(preferred: int) -> int:
        order = preferred
        while order in used_orders:
            order += 1
        used_orders.add(order)
        return order

    for block in sorted(body_units, key=lambda item: (item.block_order, item.source_ref)):
        kind = _classify_body_unit(block)
        heading = heading_paths.get(block.source_ref) or ["（无标题）"]
        is_note = kind == StructureUnitKind.FOOTNOTE_OR_ANNOTATION
        paragraph_atoms = _paragraph_atom_slices(
            block,
            graph_blocks.get(block.source_ref),
        )
        parent_spans = _span_ids_for(
            [block.source_ref], source_span_ids, graph_blocks
        )
        for atom in paragraph_atoms:
            excerpt = atom.text
            hits = _priority_hits(excerpt, keywords)
            is_atomized = atom.source_ref != block.source_ref
            structure_id_parts = (
                snapshot_id,
                projection.projection_id,
                block.source_ref,
                kind.value,
            )
            if is_atomized:
                structure_id_parts += (f"atom-{atom.start}-{atom.end}",)
            units.append(
                ProtocolStructureUnit(
                    structure_unit_id=_stable_id(*structure_id_parts),
                    source_ref=atom.source_ref,
                    member_source_refs=[atom.parent_source_ref],
                    source_span_ids=parent_spans,
                    unit_kind=kind,
                    heading_path=heading,
                    table_context=None,
                    is_footnote_or_note=is_note,
                    source_order=_next_order(block.block_order * 10 + atom.ordinal),
                    study_phase=projection.selected_phase,
                    phase_scopes=(
                        list(atom.phase_scopes)
                        if is_atomized
                        else _phase_scopes_for([block.source_ref], graph_blocks)
                    ),
                    excerpt=excerpt,
                    priority_rank=len(hits),
                    priority_keyword_hits=hits,
                )
            )

    for (table_root, row_index), cells in sorted(
        table_rows.items(),
        key=lambda item: (
            min(cell.block_order for cell in item[1]),
            item[0][0],
            item[0][1],
        ),
    ):
        ordered_cells = sorted(
            cells,
            key=lambda item: (
                item.table_path or (),
                item.block_order,
                item.source_ref,
            ),
        )
        kind = _classify_table_row(row_index, ordered_cells)
        first = ordered_cells[0]
        anchor_path = _cell_path(first)
        if anchor_path is None or len(anchor_path) < 2:
            raise FullProtocolCoverageError(
                f"表格结构单元缺少 table_path：{first.source_ref}"
            )
        if anchor_path[-2] != row_index:
            raise FullProtocolCoverageError(
                f"表格行索引与 table_path 不一致：{first.source_ref}"
            )

        all_table_cells: dict[int, list[StructureBlock]] = defaultdict(list)
        for (root, row), row_cells in table_rows.items():
            if root != table_root:
                continue
            all_table_cells[row].extend(row_cells)

        heading = table_heading_paths.get(table_root) or ["（无标题）"]
        atomize = _table_row_requires_atomization(ordered_cells, graph_blocks)
        member_groups: Sequence[Sequence[StructureBlock]] = (
            tuple((cell,) for cell in ordered_cells)
            if atomize
            else (tuple(ordered_cells),)
        )
        for member_cells in member_groups:
            excerpt = " | ".join(
                _normalize(cell.text) for cell in member_cells if _normalize(cell.text)
            )
            if not excerpt:
                continue
            hits = _priority_hits(excerpt, keywords)
            member_source_refs = sorted(cell.source_ref for cell in member_cells)
            member_cell_paths = sorted(
                {
                    path
                    for cell in member_cells
                    for path in [_cell_path(cell)]
                    if path is not None
                }
            )
            if not member_cell_paths:
                raise FullProtocolCoverageError(
                    f"表格结构单元缺少成员 table_path：{member_source_refs[0]}"
                )
            unit_source_ref = (
                member_cells[0].source_ref
                if atomize
                else f"{table_root}.r{row_index}"
            )
            unit_id = (
                _stable_id(
                    snapshot_id,
                    projection.projection_id,
                    member_cells[0].source_ref,
                    kind.value,
                )
                if atomize
                else _stable_id(
                    snapshot_id,
                    projection.projection_id,
                    table_root,
                    f"r{row_index}",
                    kind.value,
                )
            )
            unit_anchor_path = member_cell_paths[0]
            unit_column_index = unit_anchor_path[-1]
            units.append(
                ProtocolStructureUnit(
                    structure_unit_id=unit_id,
                    source_ref=unit_source_ref,
                    member_source_refs=member_source_refs,
                    source_span_ids=_span_ids_for(
                        member_source_refs, source_span_ids, graph_blocks
                    ),
                    unit_kind=kind,
                    heading_path=heading,
                    table_context=TableCellContext(
                        table_path=unit_anchor_path,
                        row_index=row_index,
                        column_index=unit_column_index,
                        member_cell_paths=member_cell_paths,
                        row_headers=_table_row_headers(all_table_cells, row_index),
                        column_headers=_table_column_headers(
                            all_table_cells, unit_column_index
                        ),
                    ),
                    is_footnote_or_note=kind == StructureUnitKind.TABLE_NOTE,
                    source_order=_next_order(
                        min(cell.block_order for cell in member_cells) * 10 + 1
                    ),
                    study_phase=projection.selected_phase,
                    phase_scopes=_phase_scopes_for(member_source_refs, graph_blocks),
                    excerpt=excerpt,
                    priority_rank=len(hits),
                    priority_keyword_hits=hits,
                )
            )

    if not units:
        raise FullProtocolCoverageError("选定期别未产生任何结构单元")

    units.sort(key=lambda item: item.source_order)
    resolved_manifest_id = manifest_id or _stable_id(
        "manifest",
        snapshot_id,
        projection.projection_id,
        projection.selected_phase.value,
    )
    return ProtocolSectionCoverageManifest(
        manifest_id=resolved_manifest_id,
        protocol_version_id=protocol_version_id.strip(),
        protocol_document_sha256=protocol_document_sha256,
        study_phase=projection.selected_phase,
        snapshot_id=snapshot_id.strip(),
        units=units,
        dispositions=[],
        claims_full_coverage=False,
    )
