"""结构块到渲染页/文本范围的对齐。

双通道来源模型（结构通道 + 渲染通道）通过规范化文本片段在页文本中做确定性
子串定位；找不到时降级为块级定位并说明原因，不伪造页码或坐标。

- 正文段落：跨页且页内唯一匹配 -> ``text_range`` 精度（带回原始字符范围）；
  重复文本只在前后精确锚点或表级物理范围内唯一时定位；中文字符间距
  差异在去空白后全篇唯一且可回验物理范围时视为精确对齐；
- 页眉/页脚：天然可能逐页重复，仅作降级页面提示，不作为规则级精确来源；
- 表格：按信息量选择子段落锚，只有唯一命中才给 ``page_only``；
- 无文本或渲染未命中 -> ``block`` 兜底，``alignment_status=unaligned``。
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.contracts.enums import (
    AlignmentStatus,
    DocumentPart,
    SourceLocatorPrecision,
)
from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
from .docx_structure import BlockKind, StructureBlock


@dataclass(frozen=True)
class AlignmentResult:
    spans: tuple[ProtocolSourceSpan, ...]
    aligned: int
    degraded: int
    unaligned: int


_PAGE_HINT_MAX_BLOCK_DISTANCE = 12
_SECTION_RECOVERY_MAX_BLOCK_DISTANCE = 64
_SECTION_RECOVERY_MAX_PAGE_DISTANCE = 12
_MIN_EXACT_FRAGMENT_LENGTH = 16


def _is_script_marker(text: str, index: int) -> bool:
    if text[index] == "^":
        return True
    return (
        text[index] == "_"
        and index > 0
        and index + 1 < len(text)
        and text[index - 1].isalnum()
        and text[index + 1].isalnum()
    )


def _normalize(text: str) -> tuple[str, list[int]]:
    """空白折叠规范化，并返回每个规范化字符对应的原始索引。

    规范化后无前导空格；尾随空格被剥离。``orig_indices[i]`` 为规范化第 i 个
    字符在原文中的下标。
    """
    norm_chars: list[str] = []
    orig_indices: list[int] = []
    in_ws = False
    for index, ch in enumerate(text):
        if _is_script_marker(text, index):
            continue
        if ch.isspace():
            if norm_chars and not in_ws:
                norm_chars.append(" ")
                orig_indices.append(index)
                in_ws = True
            continue
        norm_chars.append(ch)
        orig_indices.append(index)
        in_ws = False
    norm = "".join(norm_chars)
    stripped = norm.rstrip()
    return stripped, orig_indices[: len(stripped)]


def _compact(text: str) -> tuple[str, list[int]]:
    """移除全部空白并保留原始索引，用于恢复中文字符间距造成的渲染差异。"""
    chars: list[str] = []
    indices: list[int] = []
    for index, ch in enumerate(text):
        if _is_script_marker(text, index):
            continue
        if ch.isspace():
            continue
        chars.append(ch)
        indices.append(index)
    return "".join(chars), indices


def _match_locations(
    needle: str, page_norms: list[tuple[str, list[int]]]
) -> list[tuple[int, int]]:
    """返回规范化片段的全部 ``(页序号, 页内起点)``，避免重复命中伪精确。"""
    locations: list[tuple[int, int]] = []
    for page_index, (page_norm, _idx) in enumerate(page_norms):
        start = 0
        while needle:
            found = page_norm.find(needle, start)
            if found == -1:
                break
            locations.append((page_index, found))
            start = found + max(1, len(needle))
    return locations


def _span_id(snapshot_id: str, source_ref: str) -> str:
    raw = f"{snapshot_id}::{source_ref}"
    if len(raw) <= 128:
        return raw
    import hashlib

    return f"span:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def _table_row_col(table_path: tuple[int, ...] | None) -> tuple[int | None, int | None]:
    if table_path is None or len(table_path) < 2:
        return None, None
    return table_path[-2], table_path[-1]


def _table_anchor_needles(
    blocks: list[StructureBlock] | tuple[StructureBlock, ...],
) -> dict[str, tuple[str, ...]]:
    """表格结构节点 -> 按信息量降序排列的非空子段落锚点。"""
    anchors: dict[str, tuple[str, ...]] = {}
    for block in blocks:
        if block.kind != BlockKind.TABLE:
            continue
        prefix = block.source_ref + "."
        candidates: list[str] = []
        for candidate in blocks:
            if (
                candidate.kind == BlockKind.PARAGRAPH
                and candidate.source_ref.startswith(prefix)
            ):
                needle, _ = _normalize(candidate.text)
                if needle and needle not in candidates:
                    candidates.append(needle)
        if candidates:
            anchors[block.source_ref] = tuple(
                sorted(candidates, key=lambda value: (-len(value), value))
            )
    return anchors


def _alignment_container(block: StructureBlock) -> tuple[object, ...]:
    """Return the narrow structural container allowed to share page hints."""
    if block.document_part != DocumentPart.BODY:
        return ("excluded", block.source_ref)
    if block.table_path is None:
        return ("body", block.section_index)
    top_table = block.source_ref.split(".", 2)[1]
    return ("table_cell", block.section_index, top_table, block.table_path)


def _top_table_root(block: StructureBlock) -> str | None:
    if block.table_path is None or ".r" not in block.source_ref:
        return None
    return block.source_ref.split(".r", 1)[0]


def _add_conservative_page_hints(
    blocks: list[StructureBlock] | tuple[StructureBlock, ...],
    spans: list[ProtocolSourceSpan],
) -> list[ProtocolSourceSpan]:
    """Recover same-page hints without upgrading source authority.

    A hint is allowed only when the nearest preceding and following exact body
    paragraph locations are in the same narrow structural container, both are
    close in block order, and both resolve to the same rendered page. Adjacent
    pages, order inversions, repeated text and cross-cell/section neighbours are
    never guessed. The result remains ``DEGRADED/PAGE_ONLY`` and therefore must
    not satisfy a rule's formal source-coverage gate.
    """
    authoritative: list[tuple[StructureBlock, ProtocolSourceSpan]] = [
        (block, span)
        for block, span in zip(blocks, spans, strict=True)
        if block.kind == BlockKind.PARAGRAPH
        and block.document_part == DocumentPart.BODY
        and span.alignment_status == AlignmentStatus.ALIGNED
        and span.precision == SourceLocatorPrecision.TEXT_RANGE
        and span.render_page is not None
        and span.render_artifact_id is not None
    ]
    revised: list[ProtocolSourceSpan] = []
    for block, span in zip(blocks, spans, strict=True):
        if not (
            block.kind == BlockKind.PARAGRAPH
            and block.document_part == DocumentPart.BODY
            and block.text.strip()
            and span.alignment_status == AlignmentStatus.UNALIGNED
        ):
            revised.append(span)
            continue

        container = _alignment_container(block)
        peers = [
            item for item in authoritative if _alignment_container(item[0]) == container
        ]
        previous = [item for item in peers if item[0].block_order < block.block_order]
        following = [item for item in peers if item[0].block_order > block.block_order]
        if not previous or not following:
            revised.append(span)
            continue
        left_block, left_span = max(previous, key=lambda item: item[0].block_order)
        right_block, right_span = min(following, key=lambda item: item[0].block_order)
        if (
            block.block_order - left_block.block_order > _PAGE_HINT_MAX_BLOCK_DISTANCE
            or right_block.block_order - block.block_order
            > _PAGE_HINT_MAX_BLOCK_DISTANCE
            or left_span.render_page != right_span.render_page
            or left_span.render_artifact_id != right_span.render_artifact_id
        ):
            revised.append(span)
            continue

        revised.append(
            span.model_copy(
                update={
                    "render_artifact_id": left_span.render_artifact_id,
                    "render_page": left_span.render_page,
                    # PAGE_ONLY is a navigation hint, not an assertion that
                    # the block text occurs on that page.  A repeated block
                    # may already carry a structure-channel excerpt; clear it
                    # before changing precision so persisted round-trips do
                    # not manufacture a page-level quotation.
                    "excerpt": None,
                    "precision": SourceLocatorPrecision.PAGE_ONLY,
                    "alignment_status": AlignmentStatus.DEGRADED,
                    "degradation_reason": (
                        "前后精确定位均在同一结构容器和同一渲染页，仅作页面定位提示；"
                        "该提示不能单独满足规则来源覆盖要求"
                    ),
                }
            )
        )
    return revised


def _recover_bounded_exact_ranges(
    blocks: list[StructureBlock] | tuple[StructureBlock, ...],
    spans: list[ProtocolSourceSpan],
    *,
    render_artifact_id: str,
    page_norms: list[tuple[str, list[int]]],
    page_compacts: list[tuple[str, list[int]]],
    max_block_distance: int = _PAGE_HINT_MAX_BLOCK_DISTANCE,
    max_page_distance: int = 2,
) -> list[ProtocolSourceSpan]:
    """Resolve one repeated physical instance between two exact anchors.

    A paragraph repeated elsewhere in a long protocol is not globally unique,
    but its physical instance can still be deterministic when the nearest
    preceding and following structure blocks already have exact ranges on the
    same page.  The repeated paragraph is promoted only when exactly one of
    its page matches lies strictly between those ranges.  This is an exact
    text-range claim, unlike the page-only hint added later.
    """

    authoritative: list[tuple[StructureBlock, ProtocolSourceSpan]] = [
        (block, span)
        for block, span in zip(blocks, spans, strict=True)
        if block.kind == BlockKind.PARAGRAPH
        and block.document_part == DocumentPart.BODY
        and span.alignment_status == AlignmentStatus.ALIGNED
        and span.precision == SourceLocatorPrecision.TEXT_RANGE
        and span.render_artifact_id == render_artifact_id
        and span.render_page is not None
        and span.text_start is not None
        and span.text_end is not None
    ]
    revised: list[ProtocolSourceSpan] = []
    for block, span in zip(blocks, spans, strict=True):
        if not (
            block.kind == BlockKind.PARAGRAPH
            and block.document_part == DocumentPart.BODY
            and block.text.strip()
            and span.alignment_status == AlignmentStatus.UNALIGNED
        ):
            revised.append(span)
            continue

        container = _alignment_container(block)
        peers = [
            item for item in authoritative if _alignment_container(item[0]) == container
        ]
        previous = [item for item in peers if item[0].block_order < block.block_order]
        following = [item for item in peers if item[0].block_order > block.block_order]
        if not previous or not following:
            revised.append(span)
            continue
        left_block, left_span = max(previous, key=lambda item: item[0].block_order)
        right_block, right_span = min(following, key=lambda item: item[0].block_order)
        if (
            block.block_order - left_block.block_order > max_block_distance
            or right_block.block_order - block.block_order > max_block_distance
            or left_span.render_artifact_id != right_span.render_artifact_id
            or left_span.text_end is None
            or right_span.text_start is None
            or left_span.render_page is None
            or right_span.render_page is None
            or right_span.render_page < left_span.render_page
            or right_span.render_page - left_span.render_page > max_page_distance
            or (
                left_span.render_page == right_span.render_page
                and left_span.text_end > right_span.text_start
            )
        ):
            revised.append(span)
            continue

        def bounded_candidates(
            needle: str,
            location_pages: list[tuple[str, list[int]]],
        ) -> list[tuple[int, int, int]]:
            bounded: list[tuple[int, int, int]] = []
            for candidate_page, start in _match_locations(needle, location_pages):
                render_page = candidate_page + 1
                if not left_span.render_page <= render_page <= right_span.render_page:
                    continue
                _page_text, original_indices = location_pages[candidate_page]
                end = start + len(needle)
                raw_start = original_indices[start]
                raw_end = original_indices[end - 1] + 1
                after_left = (
                    render_page > left_span.render_page
                    or left_span.text_end <= raw_start
                )
                before_right = (
                    render_page < right_span.render_page
                    or raw_end <= right_span.text_start
                )
                if after_left and before_right:
                    bounded.append((render_page, raw_start, raw_end))
            return bounded

        needle, _ = _normalize(block.text)
        bounded = bounded_candidates(needle, page_norms)
        if len(bounded) != 1:
            compact_needle, _ = _compact(block.text)
            if len(compact_needle) >= 8:
                compact_bounded = bounded_candidates(compact_needle, page_compacts)
                if len(compact_bounded) == 1:
                    bounded = compact_bounded
        if len(bounded) != 1:
            revised.append(span)
            continue

        render_page, raw_start, raw_end = bounded[0]
        revised.append(
            span.model_copy(
                update={
                    "render_artifact_id": render_artifact_id,
                    "render_page": render_page,
                    "text_start": raw_start,
                    "text_end": raw_end,
                    "excerpt": block.text,
                    "precision": SourceLocatorPrecision.TEXT_RANGE,
                    "alignment_status": AlignmentStatus.ALIGNED,
                    "degradation_reason": None,
                }
            )
        )
    return revised


def _recover_exact_body_fragments(
    blocks: list[StructureBlock] | tuple[StructureBlock, ...],
    spans: list[ProtocolSourceSpan],
    *,
    render_artifact_id: str,
    page_compacts: list[tuple[str, list[int]]],
) -> list[ProtocolSourceSpan]:
    """Anchor a cross-page body paragraph by one exact source fragment.

    A DOCX paragraph can straddle rendered pages, so the complete structure
    text cannot always occur on any single PDF page.  This recovery is limited
    to top-level body paragraphs bounded by exact neighbours in the same Word
    section.  It chooses the longest prefix or suffix (minimum 16 non-space
    characters) that occurs exactly once inside that physical interval.  The
    span excerpt is that fragment only; the complete paragraph remains in the
    immutable structure channel and is never claimed as a single-page range.
    """

    authoritative: list[tuple[StructureBlock, ProtocolSourceSpan]] = [
        (block, span)
        for block, span in zip(blocks, spans, strict=True)
        if block.kind == BlockKind.PARAGRAPH
        and block.document_part == DocumentPart.BODY
        and block.table_path is None
        and span.alignment_status == AlignmentStatus.ALIGNED
        and span.precision == SourceLocatorPrecision.TEXT_RANGE
        and span.render_artifact_id == render_artifact_id
        and span.render_page is not None
        and span.text_start is not None
        and span.text_end is not None
    ]
    revised: list[ProtocolSourceSpan] = []
    for block, span in zip(blocks, spans, strict=True):
        if not (
            block.kind == BlockKind.PARAGRAPH
            and block.document_part == DocumentPart.BODY
            and block.table_path is None
            and block.text.strip()
            and span.alignment_status == AlignmentStatus.UNALIGNED
        ):
            revised.append(span)
            continue

        peers = [
            item
            for item in authoritative
            if item[0].section_index == block.section_index
        ]
        previous = [item for item in peers if item[0].block_order < block.block_order]
        following = [item for item in peers if item[0].block_order > block.block_order]
        if not previous or not following:
            revised.append(span)
            continue
        left_block, left_span = max(previous, key=lambda item: item[0].block_order)
        right_block, right_span = min(following, key=lambda item: item[0].block_order)
        if (
            block.block_order - left_block.block_order
            > _SECTION_RECOVERY_MAX_BLOCK_DISTANCE
            or right_block.block_order - block.block_order
            > _SECTION_RECOVERY_MAX_BLOCK_DISTANCE
            or left_span.render_page is None
            or right_span.render_page is None
            or right_span.render_page < left_span.render_page
            or right_span.render_page - left_span.render_page
            > _SECTION_RECOVERY_MAX_PAGE_DISTANCE
        ):
            revised.append(span)
            continue

        compact_source, source_indices = _compact(block.text)
        if len(compact_source) < _MIN_EXACT_FRAGMENT_LENGTH:
            revised.append(span)
            continue

        best: tuple[int, int, int, int, int] | None = None
        # Prefer longer fragments; prefix wins a same-length tie so the source
        # opens at the beginning of the paragraph when both ends are unique.
        for length in range(len(compact_source) - 1, _MIN_EXACT_FRAGMENT_LENGTH - 1, -1):
            candidates_to_try = (
                (0, compact_source[:length]),
                (len(compact_source) - length, compact_source[-length:]),
            )
            for source_start, needle in candidates_to_try:
                bounded: list[tuple[int, int, int]] = []
                for page_index, start in _match_locations(needle, page_compacts):
                    render_page = page_index + 1
                    if not left_span.render_page <= render_page <= right_span.render_page:
                        continue
                    _page_text, original_indices = page_compacts[page_index]
                    end = start + len(needle)
                    bounded.append(
                        (
                            render_page,
                            original_indices[start],
                            original_indices[end - 1] + 1,
                        )
                    )
                if len(bounded) == 1:
                    render_page, raw_start, raw_end = bounded[0]
                    best = (length, source_start, render_page, raw_start, raw_end)
                    break
            if best is not None:
                break
        if best is None:
            revised.append(span)
            continue

        length, source_start, render_page, raw_start, raw_end = best
        source_end = source_start + length
        excerpt_start = source_indices[source_start]
        excerpt_end = source_indices[source_end - 1] + 1
        revised.append(
            span.model_copy(
                update={
                    "render_artifact_id": render_artifact_id,
                    "render_page": render_page,
                    "text_start": raw_start,
                    "text_end": raw_end,
                    "excerpt": block.text[excerpt_start:excerpt_end],
                    "precision": SourceLocatorPrecision.TEXT_RANGE,
                    "alignment_status": AlignmentStatus.ALIGNED,
                    "degradation_reason": None,
                }
            )
        )
    return revised


def _downgrade_colliding_ranges(spans: list[ProtocolSourceSpan]) -> list[ProtocolSourceSpan]:
    range_counts: dict[tuple[str, int, int, int], int] = {}
    for span in spans:
        if (
            span.render_artifact_id
            and span.render_page is not None
            and span.text_start is not None
            and span.text_end is not None
        ):
            key = (
                span.render_artifact_id,
                span.render_page,
                span.text_start,
                span.text_end,
            )
            range_counts[key] = range_counts.get(key, 0) + 1

    collision_keys = {key for key, count in range_counts.items() if count > 1}
    if not collision_keys:
        return spans
    revised: list[ProtocolSourceSpan] = []
    for span in spans:
        key = (
            span.render_artifact_id or "",
            span.render_page or 0,
            span.text_start or 0,
            span.text_end or 0,
        )
        if key in collision_keys:
            span = span.model_copy(
                update={
                    "render_artifact_id": None,
                    "render_page": None,
                    "text_start": None,
                    "text_end": None,
                    "precision": SourceLocatorPrecision.BLOCK,
                    "alignment_status": AlignmentStatus.UNALIGNED,
                    "degradation_reason": (
                        f"{range_counts[key]} 个结构块共享同一渲染范围，"
                        "无法判定各自物理实例"
                    ),
                }
            )
        revised.append(span)
    return revised


def _recover_table_bounded_exact_ranges(
    blocks: list[StructureBlock] | tuple[StructureBlock, ...],
    spans: list[ProtocolSourceSpan],
    *,
    render_artifact_id: str,
    page_norms: list[tuple[str, list[int]]],
) -> list[ProtocolSourceSpan]:
    """Disambiguate repeated cell text inside one table's physical pages.

    Separate phase flow tables often repeat the same operation labels.  Exact
    sibling cell locations establish each table's rendered page interval; a
    repeated cell may claim a range only when exactly one matching instance
    falls inside that interval.  No whole-table or page-only locator is used
    as a substitute for the operation's own text range.
    """

    pages_by_table: dict[str, set[int]] = {}
    occupied: set[tuple[int, int, int]] = set()
    for block, span in zip(blocks, spans, strict=True):
        if (
            span.alignment_status == AlignmentStatus.ALIGNED
            and span.precision == SourceLocatorPrecision.TEXT_RANGE
            and span.render_artifact_id == render_artifact_id
            and span.render_page is not None
            and span.text_start is not None
            and span.text_end is not None
        ):
            occupied.add((span.render_page, span.text_start, span.text_end))
            table = _top_table_root(block)
            if table is not None:
                pages_by_table.setdefault(table, set()).add(span.render_page)

    # A long table may start before its first unique cell and end after its
    # last one. Bound that interval with the nearest exact top-level body
    # paragraphs surrounding the table root; these are structural neighbours,
    # not guessed page interpolation.
    top_level = [
        (block, span)
        for block, span in zip(blocks, spans, strict=True)
        if block.document_part == DocumentPart.BODY and block.table_path is None
    ]
    for index, (root_block, _root_span) in enumerate(top_level):
        if root_block.kind != BlockKind.TABLE:
            continue
        table_pages = pages_by_table.setdefault(root_block.source_ref, set())
        for direction in (-1, 1):
            inspected = 0
            cursor = index + direction
            while 0 <= cursor < len(top_level) and inspected < _PAGE_HINT_MAX_BLOCK_DISTANCE:
                candidate, candidate_span = top_level[cursor]
                cursor += direction
                if candidate.section_index != root_block.section_index:
                    break
                if candidate.kind == BlockKind.TABLE:
                    break
                if not candidate.text.strip():
                    continue
                inspected += 1
                if (
                    candidate.kind == BlockKind.PARAGRAPH
                    and candidate_span.alignment_status == AlignmentStatus.ALIGNED
                    and candidate_span.precision == SourceLocatorPrecision.TEXT_RANGE
                    and candidate_span.render_artifact_id == render_artifact_id
                    and candidate_span.render_page is not None
                ):
                    table_pages.add(candidate_span.render_page)
                    break

    revised: list[ProtocolSourceSpan] = []
    for block, span in zip(blocks, spans, strict=True):
        table = _top_table_root(block)
        table_pages = pages_by_table.get(table or "", set())
        if not (
            table
            and table_pages
            and block.kind == BlockKind.PARAGRAPH
            and block.document_part == DocumentPart.BODY
            and block.text.strip()
            and span.alignment_status == AlignmentStatus.UNALIGNED
        ):
            revised.append(span)
            continue

        needle, _ = _normalize(block.text)
        lower_page = min(table_pages)
        upper_page = max(table_pages)
        candidates: list[tuple[int, int, int]] = []
        for page_index, start in _match_locations(needle, page_norms):
            render_page = page_index + 1
            if not lower_page <= render_page <= upper_page:
                continue
            _page_norm, original_indices = page_norms[page_index]
            end = start + len(needle)
            raw_start = original_indices[start]
            raw_end = original_indices[end - 1] + 1
            candidate = (render_page, raw_start, raw_end)
            if candidate not in occupied:
                candidates.append(candidate)
        if len(candidates) != 1:
            revised.append(span)
            continue

        render_page, raw_start, raw_end = candidates[0]
        occupied.add((render_page, raw_start, raw_end))
        revised.append(
            span.model_copy(
                update={
                    "render_artifact_id": render_artifact_id,
                    "render_page": render_page,
                    "text_start": raw_start,
                    "text_end": raw_end,
                    "excerpt": block.text,
                    "precision": SourceLocatorPrecision.TEXT_RANGE,
                    "alignment_status": AlignmentStatus.ALIGNED,
                    "degradation_reason": None,
                }
            )
        )
    return revised


def find_block_by_ref(
    blocks: list[StructureBlock] | tuple[StructureBlock, ...], source_ref: str
) -> StructureBlock | None:
    """按 ``source_ref`` 定位块。"""
    for block in blocks:
        if block.source_ref == source_ref:
            return block
    return None


def verify_excerpt_against_blocks(
    blocks: list[StructureBlock] | tuple[StructureBlock, ...],
    source_ref: str,
    excerpt: str,
) -> bool:
    """校验摘录是否能在该 ``source_ref`` 块的原文中逐字定位（精确连续子串）。"""
    block = find_block_by_ref(blocks, source_ref)
    if block is None or not excerpt:
        return False
    return excerpt in block.text


def align_blocks(
    blocks: list[StructureBlock] | tuple[StructureBlock, ...],
    *,
    snapshot_id: str,
    render_artifact_id: str,
    page_texts: list[str],
    recover_page_hints: bool = True,
) -> AlignmentResult:
    """把结构块对齐到渲染页，产出 :class:`ProtocolSourceSpan` 集合。

    ``page_texts`` 由 :func:`app.protocols.rendering.pdf_page_texts` 读取。
    """
    page_norms = [_normalize(text) for text in page_texts]
    page_compacts = [_compact(text) for text in page_texts]
    table_anchors = _table_anchor_needles(blocks)
    spans: list[ProtocolSourceSpan] = []
    aligned = degraded = unaligned = 0

    for block in blocks:
        span = _align_block(
            block,
            snapshot_id=snapshot_id,
            render_artifact_id=render_artifact_id,
            page_norms=page_norms,
            page_compacts=page_compacts,
            table_anchors=table_anchors,
        )
        spans.append(span)

    for _pass in range(_PAGE_HINT_MAX_BLOCK_DISTANCE):
        recovered = _recover_bounded_exact_ranges(
            blocks,
            spans,
            render_artifact_id=render_artifact_id,
            page_norms=page_norms,
            page_compacts=page_compacts,
        )
        if recovered == spans:
            break
        spans = recovered

    # Collision downgrades often expose two legitimate structure copies in
    # distant rendered sections (for example a synopsis table and the formal
    # eligibility chapter). Re-run the same exact matcher with a bounded
    # section-sized window; the structural section and physical neighbours
    # still have to isolate exactly one occurrence.
    for _pass in range(_PAGE_HINT_MAX_BLOCK_DISTANCE):
        recovered = _recover_bounded_exact_ranges(
            blocks,
            spans,
            render_artifact_id=render_artifact_id,
            page_norms=page_norms,
            page_compacts=page_compacts,
            max_block_distance=_SECTION_RECOVERY_MAX_BLOCK_DISTANCE,
            max_page_distance=_SECTION_RECOVERY_MAX_PAGE_DISTANCE,
        )
        if recovered == spans:
            break
        spans = recovered

    spans = _recover_exact_body_fragments(
        blocks,
        spans,
        render_artifact_id=render_artifact_id,
        page_compacts=page_compacts,
    )

    spans = _downgrade_colliding_ranges(spans)

    for _pass in range(_PAGE_HINT_MAX_BLOCK_DISTANCE):
        recovered = _recover_bounded_exact_ranges(
            blocks,
            spans,
            render_artifact_id=render_artifact_id,
            page_norms=page_norms,
            page_compacts=page_compacts,
        )
        if recovered == spans:
            break
        spans = recovered

    for _pass in range(_PAGE_HINT_MAX_BLOCK_DISTANCE):
        recovered = _recover_bounded_exact_ranges(
            blocks,
            spans,
            render_artifact_id=render_artifact_id,
            page_norms=page_norms,
            page_compacts=page_compacts,
            max_block_distance=_SECTION_RECOVERY_MAX_BLOCK_DISTANCE,
            max_page_distance=_SECTION_RECOVERY_MAX_PAGE_DISTANCE,
        )
        if recovered == spans:
            break
        spans = recovered

    spans = _recover_exact_body_fragments(
        blocks,
        spans,
        render_artifact_id=render_artifact_id,
        page_compacts=page_compacts,
    )

    spans = _recover_table_bounded_exact_ranges(
        blocks,
        spans,
        render_artifact_id=render_artifact_id,
        page_norms=page_norms,
    )
    spans = _downgrade_colliding_ranges(spans)

    if recover_page_hints:
        spans = _add_conservative_page_hints(blocks, spans)

    for span in spans:
        if span.alignment_status == AlignmentStatus.ALIGNED:
            aligned += 1
        elif span.alignment_status == AlignmentStatus.DEGRADED:
            degraded += 1
        else:
            unaligned += 1

    return AlignmentResult(
        spans=tuple(spans), aligned=aligned, degraded=degraded, unaligned=unaligned
    )


def _align_block(
    block: StructureBlock,
    *,
    snapshot_id: str,
    render_artifact_id: str,
    page_norms: list[tuple[str, list[int]]],
    page_compacts: list[tuple[str, list[int]]],
    table_anchors: dict[str, tuple[str, ...]],
) -> ProtocolSourceSpan:
    row, col = _table_row_col(block.table_path)
    base = dict(
        source_span_id=_span_id(snapshot_id, block.source_ref),
        snapshot_id=snapshot_id,
        source_ref=block.source_ref,
        document_part=block.document_part,
        section_index=block.section_index,
        block_order=block.block_order,
        table_path=block.table_path,
        table_row=row,
        table_col=col,
    )

    if block.kind == BlockKind.TABLE:
        needles = table_anchors.get(block.source_ref, ())
        if not needles:
            return ProtocolSourceSpan(
                **base,
                precision=SourceLocatorPrecision.BLOCK,
                alignment_status=AlignmentStatus.UNALIGNED,
                degradation_reason="表格无文本子段落，无法定位渲染页",
            )
        ambiguous_pages: set[int] = set()
        for needle in needles:
            locations = _match_locations(needle, page_norms)
            if len(locations) == 1:
                page_index, _start = locations[0]
                return ProtocolSourceSpan(
                    **base,
                    render_artifact_id=render_artifact_id,
                    render_page=page_index + 1,
                    precision=SourceLocatorPrecision.PAGE_ONLY,
                    alignment_status=AlignmentStatus.ALIGNED,
                )
            ambiguous_pages.update(page for page, _start in locations)
        if not ambiguous_pages:
            return ProtocolSourceSpan(
                **base,
                precision=SourceLocatorPrecision.BLOCK,
                alignment_status=AlignmentStatus.UNALIGNED,
                degradation_reason="表格文本未在渲染页中找到",
            )
        return ProtocolSourceSpan(
            **base,
            precision=SourceLocatorPrecision.BLOCK,
            alignment_status=AlignmentStatus.UNALIGNED,
            degradation_reason=(
                "表格候选文本在多个位置重复，不能可靠确定渲染页；候选页："
                + "、".join(str(page + 1) for page in sorted(ambiguous_pages))
            ),
        )

    needle, _ = _normalize(block.text)
    if not needle:
        return ProtocolSourceSpan(
            **base,
            precision=SourceLocatorPrecision.BLOCK,
            alignment_status=AlignmentStatus.UNALIGNED,
            degradation_reason="块文本为空，无法定位渲染页",
        )

    locations = _match_locations(needle, page_norms)
    if not locations:
        compact_needle, _ = _compact(block.text)
        compact_locations = (
            _match_locations(compact_needle, page_compacts)
            if len(compact_needle) >= 8
            else []
        )
        if len(compact_locations) == 1 and block.document_part == DocumentPart.BODY:
            page_index, start = compact_locations[0]
            _page_compact, original_indices = page_compacts[page_index]
            end = start + len(compact_needle)
            return ProtocolSourceSpan(
                **base,
                render_artifact_id=render_artifact_id,
                render_page=page_index + 1,
                text_start=original_indices[start],
                text_end=original_indices[end - 1] + 1,
                excerpt=block.text,
                precision=SourceLocatorPrecision.TEXT_RANGE,
                alignment_status=AlignmentStatus.ALIGNED,
            )
        reason = "结构文本未在渲染页中找到（自动编号、域或版式差异）"
        if len(compact_locations) > 1:
            reason = f"去空白后文本仍在 {len(compact_locations)} 个位置重复，不能可靠定位"
        return ProtocolSourceSpan(
            **base,
            precision=SourceLocatorPrecision.BLOCK,
            alignment_status=AlignmentStatus.UNALIGNED,
            degradation_reason=reason,
        )

    first_page, first_start = locations[0]
    repeated = len(locations) > 1
    is_chrome = block.document_part in (DocumentPart.HEADER, DocumentPart.FOOTER)

    if not repeated and not is_chrome:
        # 单页唯一匹配：给出原始字符范围（text_range）。
        page_norm, orig_idx = page_norms[first_page]
        start = first_start
        end = start + len(needle)
        text_start = orig_idx[start]
        text_end = orig_idx[end - 1] + 1
        return ProtocolSourceSpan(
            **base,
            render_artifact_id=render_artifact_id,
            render_page=first_page + 1,
            text_start=text_start,
            text_end=text_end,
            excerpt=block.text,
            precision=SourceLocatorPrecision.TEXT_RANGE,
            alignment_status=AlignmentStatus.ALIGNED,
        )

    if is_chrome:
        return ProtocolSourceSpan(
            **base,
            render_artifact_id=render_artifact_id,
            render_page=first_page + 1,
            excerpt=block.text,
            precision=SourceLocatorPrecision.PAGE_EXCERPT,
            alignment_status=AlignmentStatus.DEGRADED,
            degradation_reason="页眉或页脚仅作页面提示，不作为规则级精确来源",
        )
    return ProtocolSourceSpan(
        **base,
        excerpt=block.text,
        precision=SourceLocatorPrecision.BLOCK,
        alignment_status=AlignmentStatus.UNALIGNED,
        degradation_reason=f"文本在 {len(locations)} 个位置重复出现，不能可靠确定页面",
    )


def verify_excerpt_against_page(
    span: ProtocolSourceSpan, page_text: str
) -> bool:
    """核验 span 摘录确实对应其声称页内范围，而非只在结构块内自证。"""
    if not span.excerpt or span.text_start is None or span.text_end is None:
        return False
    if span.text_end > len(page_text):
        return False
    expected, _ = _normalize(span.excerpt)
    actual, _ = _normalize(page_text[span.text_start:span.text_end])
    if expected and actual == expected:
        return True
    compact_expected, _ = _compact(span.excerpt)
    compact_actual, _ = _compact(page_text[span.text_start:span.text_end])
    return bool(compact_expected) and compact_actual == compact_expected
