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


def _para(
    source_ref,
    text,
    table_path=None,
    document_part=DocumentPart.BODY,
    block_order=0,
):
    return StructureBlock(
        source_ref=source_ref,
        document_part=document_part,
        section_index=0,
        block_order=block_order,
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


def test_ooxml_script_markers_align_to_rendered_plain_text():
    blocks = [
        _para("body.p0", "ANC<1.2×10^9/L，H_2O"),
        _para("body.p1", "胸片（正侧位）^14", block_order=1),
    ]
    pages = ["实验室检查：ANC<1.2×109/L，H2O；胸片（正侧位）14"]

    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=pages,
    )
    span = result.spans[0]

    assert span.alignment_status == AlignmentStatus.ALIGNED
    assert span.precision == SourceLocatorPrecision.TEXT_RANGE
    assert span.excerpt == "ANC<1.2×10^9/L，H_2O"
    assert verify_excerpt_against_page(span, pages[0])
    assert result.spans[1].alignment_status == AlignmentStatus.ALIGNED
    assert verify_excerpt_against_page(result.spans[1], pages[0])


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


def test_repeated_text_is_precise_when_one_instance_is_bounded_by_exact_anchors():
    repeated = "年龄十八至七十五周岁"
    page = f"摘要中的{repeated}。前一条唯一正文。{repeated}。后一条唯一正文。"
    blocks = [
        _para("body.p0", "前一条唯一正文", block_order=0),
        _para("body.p1", repeated, block_order=1),
        _para("body.p2", "后一条唯一正文", block_order=2),
    ]

    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=[page],
    )

    span = result.spans[1]
    assert span.alignment_status == AlignmentStatus.ALIGNED
    assert span.precision == SourceLocatorPrecision.TEXT_RANGE
    assert span.render_page == 1
    assert page[span.text_start : span.text_end] == repeated
    assert span.text_start > page.index("前一条唯一正文")
    assert verify_excerpt_against_page(span, page)


def test_repeated_text_is_precise_between_exact_anchors_on_adjacent_pages():
    repeated = "年龄十八至七十五周岁"
    blocks = [
        _para("body.p0", "前一条唯一正文", block_order=0),
        _para("body.p1", repeated, block_order=1),
        _para("body.p2", "后一条唯一正文", block_order=2),
    ]
    pages = [
        f"摘要中的{repeated}。前一条唯一正文。",
        f"{repeated}。后一条唯一正文。",
    ]

    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=pages,
    )

    span = result.spans[1]
    assert span.alignment_status == AlignmentStatus.ALIGNED
    assert span.precision == SourceLocatorPrecision.TEXT_RANGE
    assert span.render_page == 2
    assert verify_excerpt_against_page(span, pages[1])


def test_repeated_compact_text_without_initial_excerpt_is_recovered_by_anchors():
    source_text = "筛选时必须完成血常规检查"
    rendered = "筛 选 时 必 须 完 成 血 常 规 检 查"
    blocks = [
        _para("body.p0", "前一条唯一正文", block_order=0),
        _para("body.p1", source_text, block_order=1),
        _para("body.p2", "后一条唯一正文", block_order=2),
    ]
    pages = [
        f"摘要中的{rendered}。前一条唯一正文。",
        f"{rendered}。后一条唯一正文。",
    ]

    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=pages,
    )

    span = result.spans[1]
    assert span.alignment_status == AlignmentStatus.ALIGNED
    assert span.precision == SourceLocatorPrecision.TEXT_RANGE
    assert span.render_page == 2
    assert span.excerpt == source_text
    assert verify_excerpt_against_page(span, pages[1])


def test_two_repeated_instances_between_exact_anchors_remain_non_authoritative():
    repeated = "重复的规则正文"
    page = f"前一条唯一正文。{repeated}。{repeated}。后一条唯一正文。"
    blocks = [
        _para("body.p0", "前一条唯一正文", block_order=0),
        _para("body.p1", repeated, block_order=1),
        _para("body.p2", "后一条唯一正文", block_order=2),
    ]

    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=[page],
    )

    span = result.spans[1]
    assert span.alignment_status == AlignmentStatus.DEGRADED
    assert span.precision == SourceLocatorPrecision.PAGE_ONLY
    assert span.text_start is None
    assert span.text_end is None


def test_equal_operation_labels_are_resolved_inside_separate_table_page_ranges():
    operation = "体格检查"
    blocks = [
        StructureBlock(
            source_ref="body.t0",
            document_part=DocumentPart.BODY,
            section_index=0,
            block_order=0,
            kind=BlockKind.TABLE,
            text="",
        ),
        _para("body.t0.r0.c0.p0", "Ⅱ期流程表唯一标题", (0, 0), block_order=1),
        _para("body.t0.r1.c0.p0", operation, (1, 0), block_order=2),
        _para("body.t0.r2.c0.p0", "Ⅱ期流程表唯一结尾", (2, 0), block_order=3),
        StructureBlock(
            source_ref="body.t1",
            document_part=DocumentPart.BODY,
            section_index=0,
            block_order=4,
            kind=BlockKind.TABLE,
            text="",
        ),
        _para("body.t1.r0.c0.p0", "Ⅲ期流程表唯一标题", (0, 0), block_order=5),
        _para("body.t1.r1.c0.p0", operation, (1, 0), block_order=6),
        _para("body.t1.r2.c0.p0", "Ⅲ期流程表唯一结尾", (2, 0), block_order=7),
    ]

    pages = [
        f"Ⅱ期流程表唯一标题 {operation} Ⅱ期流程表唯一结尾",
        f"Ⅲ期流程表唯一标题 {operation} Ⅲ期流程表唯一结尾",
    ]
    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=pages,
    )
    by_ref = {span.source_ref: span for span in result.spans}

    assert by_ref["body.t0.r1.c0.p0"].alignment_status == AlignmentStatus.ALIGNED
    assert by_ref["body.t0.r1.c0.p0"].render_page == 1
    assert by_ref["body.t1.r1.c0.p0"].alignment_status == AlignmentStatus.ALIGNED
    assert by_ref["body.t1.r1.c0.p0"].render_page == 2
    assert verify_excerpt_against_page(by_ref["body.t0.r1.c0.p0"], pages[0])
    assert verify_excerpt_against_page(by_ref["body.t1.r1.c0.p0"], pages[1])


def test_table_range_includes_exact_heading_before_first_unique_cell_page():
    operation = "签署知情同意书"
    blocks = [
        _para("body.p0", "Ⅱ期流程表唯一标题", block_order=0),
        StructureBlock(
            source_ref="body.t0",
            document_part=DocumentPart.BODY,
            section_index=0,
            block_order=1,
            kind=BlockKind.TABLE,
            text="",
        ),
        _para("body.t0.r5.c0.p0", operation, (5, 0), block_order=2),
        _para("body.t0.r26.c0.p0", "Ⅱ期表内唯一后项", (26, 0), block_order=3),
        _para("body.p1", "Ⅱ期流程表后唯一正文", block_order=4),
        _para("body.p2", "Ⅲ期流程表唯一标题", block_order=5),
        StructureBlock(
            source_ref="body.t1",
            document_part=DocumentPart.BODY,
            section_index=0,
            block_order=6,
            kind=BlockKind.TABLE,
            text="",
        ),
        _para("body.t1.r5.c0.p0", operation, (5, 0), block_order=7),
        _para("body.t1.r26.c0.p0", "Ⅲ期表内唯一后项", (26, 0), block_order=8),
        _para("body.p3", "Ⅲ期流程表后唯一正文", block_order=9),
    ]
    pages = [
        f"Ⅱ期流程表唯一标题 {operation}",
        "Ⅱ期表内唯一后项 Ⅱ期流程表后唯一正文",
        f"Ⅲ期流程表唯一标题 {operation}",
        "Ⅲ期表内唯一后项 Ⅲ期流程表后唯一正文",
    ]

    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=pages,
    )
    by_ref = {span.source_ref: span for span in result.spans}

    assert by_ref["body.t0.r5.c0.p0"].alignment_status == AlignmentStatus.ALIGNED
    assert by_ref["body.t0.r5.c0.p0"].render_page == 1
    assert by_ref["body.t1.r5.c0.p0"].alignment_status == AlignmentStatus.ALIGNED
    assert by_ref["body.t1.r5.c0.p0"].render_page == 3


def test_table_page_range_does_not_choose_between_two_local_instances():
    operation = "体格检查"
    blocks = [
        StructureBlock(
            source_ref="body.t0",
            document_part=DocumentPart.BODY,
            section_index=0,
            block_order=0,
            kind=BlockKind.TABLE,
            text="",
        ),
        _para("body.t0.r0.c0.p0", "流程表唯一标题", (0, 0), block_order=1),
        _para("body.t0.r1.c0.p0", operation, (1, 0), block_order=2),
        _para("body.t0.r2.c0.p0", "流程表唯一结尾", (2, 0), block_order=3),
    ]
    page = f"流程表唯一标题 {operation} {operation} 流程表唯一结尾"

    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=[page],
    )

    span = next(item for item in result.spans if item.source_ref == "body.t0.r1.c0.p0")
    assert span.alignment_status == AlignmentStatus.UNALIGNED
    assert span.precision == SourceLocatorPrecision.BLOCK
    assert span.render_page is None
    assert span.text_start is None
    assert span.text_end is None


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


def test_unique_body_text_with_rendered_character_spacing_is_formally_aligned():
    source_text = "筛选时必须完成血常规检查"
    rendered = "筛 选 时 必 须 完 成 血 常 规 检 查"

    result = align_blocks(
        [_para("body.p0", source_text)],
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=[rendered],
    )

    span = result.spans[0]
    assert span.alignment_status == AlignmentStatus.ALIGNED
    assert span.precision == SourceLocatorPrecision.TEXT_RANGE
    assert span.degradation_reason is None
    assert verify_excerpt_against_page(span, rendered)


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


def test_colliding_structure_copies_are_reassigned_by_separate_exact_contexts():
    repeated = "首次给药前四周不得使用禁用治疗"
    spaced = "首 次 给 药 前 四 周 不 得 使 用 禁 用 治 疗"
    blocks = [
        _para("body.p0", "摘要前唯一正文", block_order=0),
        _para("body.p1", repeated, block_order=1),
        _para("body.p2", "摘要后唯一正文", block_order=2),
        _para("body.p3", "正式条款前唯一正文", block_order=3),
        _para("body.p4", repeated, block_order=4),
        _para("body.p5", "正式条款后唯一正文", block_order=5),
    ]
    pages = [
        f"摘要前唯一正文 {repeated} 摘要后唯一正文",
        f"正式条款前唯一正文 {spaced} 正式条款后唯一正文",
    ]

    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=pages,
    )
    by_ref = {span.source_ref: span for span in result.spans}

    assert by_ref["body.p1"].alignment_status == AlignmentStatus.ALIGNED
    assert by_ref["body.p1"].render_page == 1
    assert by_ref["body.p4"].alignment_status == AlignmentStatus.ALIGNED
    assert by_ref["body.p4"].render_page == 2
    assert verify_excerpt_against_page(by_ref["body.p1"], pages[0])
    assert verify_excerpt_against_page(by_ref["body.p4"], pages[1])


def test_distant_colliding_body_copies_use_exact_section_context():
    repeated = "首次给药前四周不得使用禁用治疗"
    filler = [
        _para(f"body.p{i}", f"中间结构段落{i}", block_order=i)
        for i in range(2, 22)
    ]
    blocks = [
        _para("body.p0", "摘要前唯一正文", block_order=0),
        _para("body.p1", repeated, block_order=1),
        *filler,
        _para("body.p22", "摘要后唯一正文", block_order=22),
        _para("body.p23", "正式条款前唯一正文", block_order=23),
        _para("body.p24", repeated, block_order=24),
        _para("body.p25", "正式条款后唯一正文", block_order=25),
    ]
    pages = [
        f"摘要前唯一正文 {repeated} 摘要后唯一正文",
        f"正式条款前唯一正文 {repeated} 正式条款后唯一正文",
    ]

    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=pages,
    )
    by_ref = {span.source_ref: span for span in result.spans}

    assert by_ref["body.p1"].alignment_status == AlignmentStatus.ALIGNED
    assert by_ref["body.p1"].render_page == 1
    assert by_ref["body.p24"].alignment_status == AlignmentStatus.ALIGNED
    assert by_ref["body.p24"].render_page == 2


def test_cross_page_paragraph_uses_unique_exact_fragment_inside_body_context():
    paragraph = "筛选时必须完成肺功能检查且第一秒用力呼气容积占预计值百分比不得低于百分之五十"
    prefix = "筛选时必须完成肺功能检查且第一秒用力呼气容积占预计值百分比"
    pages = [
        f"前一条唯一正文 {prefix}",
        "不得低于百分之五十 后一条唯一正文",
    ]
    blocks = [
        _para("body.p0", "前一条唯一正文", block_order=0),
        _para("body.p1", paragraph, block_order=1),
        _para("body.p2", "后一条唯一正文", block_order=2),
    ]

    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=pages,
    )
    span = result.spans[1]

    assert span.alignment_status == AlignmentStatus.ALIGNED
    assert span.precision == SourceLocatorPrecision.TEXT_RANGE
    assert span.render_page == 1
    assert span.excerpt == prefix
    assert span.excerpt != paragraph
    assert verify_excerpt_against_page(span, pages[0])


def test_unaligned_paragraph_gets_same_page_hint_only():
    blocks = [
        _para("body.p0", "前一条唯一正文", block_order=0),
        _para("body.p1", "无法直接对齐的自动编号正文", block_order=1),
        _para("body.p2", "后一条唯一正文", block_order=2),
    ]
    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=["前一条唯一正文\n渲染器改写的中间内容\n后一条唯一正文"],
    )
    hint = result.spans[1]
    assert hint.alignment_status == AlignmentStatus.DEGRADED
    assert hint.precision == SourceLocatorPrecision.PAGE_ONLY
    assert hint.render_page == 1
    assert hint.excerpt is None
    assert "不能单独满足规则来源覆盖要求" in (hint.degradation_reason or "")


def test_adjacent_pages_are_not_interpolated():
    blocks = [
        _para("body.p0", "前一页唯一正文", block_order=0),
        _para("body.p1", "无法直接对齐的正文", block_order=1),
        _para("body.p2", "后一页唯一正文", block_order=2),
    ]
    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=["前一页唯一正文", "后一页唯一正文"],
    )
    assert result.spans[1].alignment_status == AlignmentStatus.UNALIGNED
    assert result.spans[1].render_page is None


def test_page_hint_does_not_cross_table_cells():
    blocks = [
        _para(
            "body.t0.r0.c0.p0", "左侧唯一正文", table_path=(0, 0), block_order=0
        ),
        _para(
            "body.t0.r0.c1.p0", "无法直接对齐的正文", table_path=(0, 1), block_order=1
        ),
        _para(
            "body.t0.r0.c0.p1", "右侧唯一正文", table_path=(0, 0), block_order=2
        ),
    ]
    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=["左侧唯一正文\n右侧唯一正文"],
    )
    assert result.spans[1].alignment_status == AlignmentStatus.UNALIGNED
    assert result.spans[1].render_page is None


def test_page_order_inversion_is_not_interpolated():
    blocks = [
        _para("body.p0", "结构靠前但渲染在后页", block_order=0),
        _para("body.p1", "无法直接对齐的正文", block_order=1),
        _para("body.p2", "结构靠后但渲染在前页", block_order=2),
    ]
    result = align_blocks(
        blocks,
        snapshot_id="snap",
        render_artifact_id="render",
        page_texts=["结构靠后但渲染在前页", "结构靠前但渲染在后页"],
    )
    assert result.spans[1].alignment_status == AlignmentStatus.UNALIGNED
    assert result.spans[1].render_page is None
