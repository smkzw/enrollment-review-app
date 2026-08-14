"""结构块到渲染页/文本范围的对齐。

双通道来源模型（结构通道 + 渲染通道）通过规范化文本片段在页文本中做确定性
子串定位；找不到时降级为块级定位并说明原因，不伪造页码或坐标。

- 正文段落：跨页且页内唯一匹配 -> ``text_range`` 精度（带回原始字符范围）；
  重复文本不猜页；中文字符间距差异仅在去空白后唯一时降级对齐；
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


def _normalize(text: str) -> tuple[str, list[int]]:
    """空白折叠规范化，并返回每个规范化字符对应的原始索引。

    规范化后无前导空格；尾随空格被剥离。``orig_indices[i]`` 为规范化第 i 个
    字符在原文中的下标。
    """
    norm_chars: list[str] = []
    orig_indices: list[int] = []
    in_ws = False
    for index, ch in enumerate(text):
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
    if collision_keys:
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
        spans = revised

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
                alignment_status=AlignmentStatus.DEGRADED,
                degradation_reason="渲染文本含额外字距，按去空白文本唯一对齐",
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
