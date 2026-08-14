"""来源对齐与摘录核验测试：table_path 传播、精确逐字摘录核验、span 契约校验。"""
from __future__ import annotations

import pytest

from app.domain.contracts.enums import AlignmentStatus, DocumentPart, SourceLocatorPrecision
from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
from app.protocols.docx_structure import BlockKind, StructureBlock
from app.protocols.source_alignment import (
    align_blocks,
    verify_excerpt_against_blocks,
    verify_excerpt_against_page,
)


def _para(source_ref, text, table_path=None, document_part=DocumentPart.BODY):
    return StructureBlock(
        source_ref=source_ref,
        document_part=document_part,
        section_index=0,
        block_order=0,
        kind=BlockKind.PARAGRAPH,
        text=text,
        table_path=table_path,
    )


def test_align_propagates_full_table_path():
    blocks = [
        _para(
            "body.t0.r1.c2.t0.r0.c0.p0",
            "唯一嵌套单元格文本",
            table_path=(1, 2, 0, 0),
        )
    ]
    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=["第 1 页 唯一嵌套单元格文本"],
    )
    span = result.spans[0]
    assert span.table_path == (1, 2, 0, 0)
    assert span.table_row == 0
    assert span.table_col == 0
    assert span.alignment_status == AlignmentStatus.ALIGNED


def test_exact_excerpt_verification_is_verbatim():
    blocks = [_para("body.p0", "入选标准：年龄 ≥ 18 岁")]
    # 逐字子串通过
    assert verify_excerpt_against_blocks(blocks, "body.p0", "年龄 ≥ 18 岁") is True
    # 篡改文本（哪怕空白等价）必须失败
    assert verify_excerpt_against_blocks(blocks, "body.p0", "年龄≥18岁") is False
    assert verify_excerpt_against_blocks(blocks, "body.p0", "年龄 ≥ 19 岁") is False
    # 不存在的 source_ref 失败
    assert verify_excerpt_against_blocks(blocks, "body.p9", "年龄") is False


def test_every_aligned_excerpt_verifies_against_block():
    blocks = [
        _para("body.p0", "入选标准甲"),
        _para("body.p1", "排除标准乙"),
        _para("body.p2", "随机前要求丙"),
    ]
    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=["入选标准甲 排除标准乙 随机前要求丙"],
    )
    for span in result.spans:
        if span.excerpt:
            assert verify_excerpt_against_blocks(
                blocks, span.source_ref, span.excerpt
            ), span.source_ref


def test_material_spans_have_nonempty_excerpt_table_containers_may_not():
    """目录级物料跨度（段落）必须携带非空摘录且逐字可核验；表格容器节点可无摘录。"""
    blocks = [
        _para("body.p0", "入选标准甲"),
        _para("body.p1", "排除标准乙"),
        StructureBlock(
            source_ref="body.t0",
            document_part=DocumentPart.BODY,
            section_index=0,
            block_order=2,
            kind=BlockKind.TABLE,
            text="",
        ),
        _para("body.t0.r0.c0.p0", "表格首格文本", table_path=(0, 0)),
    ]
    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=["入选标准甲 排除标准乙 表格首格文本"],
    )
    for span in result.spans:
        if span.precision == SourceLocatorPrecision.PAGE_ONLY:
            # 表格容器锚点：允许无摘录（非物料锚点）
            assert span.excerpt is None or span.excerpt == ""
            continue
        assert span.excerpt, f"{span.source_ref} 物料跨度缺摘录"
        assert verify_excerpt_against_blocks(
            blocks, span.source_ref, span.excerpt
        ), f"{span.source_ref} 摘录未能逐字回到块原文"


def test_span_table_path_contract_validates():
    common = dict(
        source_span_id="s1",
        snapshot_id="snap",
        source_ref="body.t0.r1.c2.p0",
        document_part=DocumentPart.BODY,
        block_order=0,
        precision=SourceLocatorPrecision.BLOCK,
        alignment_status=AlignmentStatus.UNALIGNED,
        degradation_reason="未对齐",
    )
    # 正确：table_row/col 等于最内层坐标
    ProtocolSourceSpan(**common, table_path=(1, 2), table_row=1, table_col=2)
    # 错误：table_row/col 与 table_path 不一致
    with pytest.raises(Exception):
        ProtocolSourceSpan(**common, table_path=(1, 2), table_row=0, table_col=0)
    # 错误：table_path 长度非偶数
    with pytest.raises(Exception):
        ProtocolSourceSpan(**common, table_path=(1,), table_row=None, table_col=None)
    # 错误：无 table_path 却携带 table_row/col
    with pytest.raises(Exception):
        ProtocolSourceSpan(**common, table_path=None, table_row=1, table_col=2)


def test_repeated_text_on_same_page_is_not_marked_precise():
    blocks = [_para("body.p0", "随机前四周不得使用研究禁用治疗")]
    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=["随机前四周不得使用研究禁用治疗。随机前四周不得使用研究禁用治疗。"],
    )
    span = result.spans[0]
    assert span.alignment_status == AlignmentStatus.UNALIGNED
    assert span.render_page is None
    assert "重复" in (span.degradation_reason or "")


def test_repeated_table_anchor_does_not_guess_first_page():
    blocks = [
        StructureBlock(
            source_ref="body.t0",
            document_part=DocumentPart.BODY,
            section_index=0,
            block_order=0,
            kind=BlockKind.TABLE,
            text="",
        ),
        _para("body.t0.r0.c0.p0", "访视", table_path=(0, 0)),
    ]
    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=["访视", "访视"],
    )
    table_span = result.spans[0]
    assert table_span.alignment_status == AlignmentStatus.UNALIGNED
    assert table_span.render_page is None


def test_precise_span_verifies_against_claimed_page_slice():
    text = "入选标准：年龄不低于十八周岁"
    result = align_blocks(
        [_para("body.p0", text)],
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=[f"方案正文 {text} 后续内容"],
    )
    span = result.spans[0]
    assert span.precision == SourceLocatorPrecision.TEXT_RANGE
    assert verify_excerpt_against_page(span, f"方案正文 {text} 后续内容")
    assert not verify_excerpt_against_page(span, "方案正文 另一段内容 后续内容")


def test_two_blocks_cannot_claim_the_same_physical_text_range():
    text = "研究者应在随机前确认全部入排标准"
    result = align_blocks(
        [_para("body.p0", text), _para("body.p1", text)],
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=[text],
    )
    assert all(
        span.alignment_status == AlignmentStatus.UNALIGNED
        and span.precision == SourceLocatorPrecision.BLOCK
        and span.render_page is None
        and "共享同一渲染范围" in (span.degradation_reason or "")
        for span in result.spans
    )
