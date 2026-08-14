"""自动编号继承与未解析编号异常：样式链编号、numId=0、悬空 numId。"""
from __future__ import annotations

from app.domain.contracts.enums import ExtractionStatus
from app.protocols.docx_structure import BlockKind, extract_docx_structure
from app.protocols.ingestion import register_source_artifact
from .helpers import (
    build_based_on_numbering_docx,
    build_direct_numbering_docx,
    build_style_numbering_docx,
)


def _extract(tmp_path, name, builder):
    path = tmp_path / f"{name}.docx"
    builder(path)
    artifact = register_source_artifact(
        path, source_artifact_id=name, storage_root=tmp_path
    )
    return extract_docx_structure(
        path, snapshot_id=f"{name}-snap", source_artifact=artifact, output_dir=tmp_path
    )


def test_numbering_inherited_through_paragraph_style(tmp_path):
    """段落自身无 numPr，编号来自其段落样式（List Number）。"""
    ext = _extract(tmp_path, "style-num", build_style_numbering_docx)
    paras = [b for b in ext.blocks if b.kind == BlockKind.PARAGRAPH]
    styled = [b for b in paras if b.text == "styled item"]
    assert styled, "样式编号段落未被捕获"
    assert styled[0].numbering is not None
    # 沿样式链解析出的编号定义必须有可还原官方编号文本的 lvl_text
    assert styled[0].numbering.lvl_text is not None
    assert styled[0].numbering.num_fmt is not None


def test_numbering_inherited_through_based_on_style_chain(tmp_path):
    ext = _extract(tmp_path, "based-on-num", build_based_on_numbering_docx)
    paras = [
        block
        for block in ext.blocks
        if block.kind == BlockKind.PARAGRAPH and block.text == "based-on item"
    ]
    assert paras and paras[0].numbering is not None
    assert paras[0].numbering.lvl_text is not None


def test_numid_zero_is_explicitly_unnumbered_not_anomaly(tmp_path):
    ext = _extract(tmp_path, "num0", lambda p: build_direct_numbering_docx(p, num_id=0))
    paras = [b for b in ext.blocks if b.kind == BlockKind.PARAGRAPH and b.text == "numbered item"]
    assert paras
    assert paras[0].numbering is None  # numId=0 -> 显式取消编号，非悬空引用
    unresolved = [a for a in ext.snapshot.anomalies if a.kind == "unresolved_numbering"]
    assert unresolved == []
    assert ext.snapshot.status == ExtractionStatus.COMPLETED


def test_unresolved_numbering_emits_anomaly_and_needs_review(tmp_path):
    """numId 非 0 却无对应编号定义：必须产出异常而非静默丢弃编号上下文。"""
    ext = _extract(tmp_path, "dangling", lambda p: build_direct_numbering_docx(p, num_id=999))
    unresolved = [a for a in ext.snapshot.anomalies if a.kind == "unresolved_numbering"]
    assert len(unresolved) == 1
    assert unresolved[0].scope_ref is not None
    # 异常段落仍保留编号引用（lvl_text 无法解析），块级上下文不丢失
    paras = [b for b in ext.blocks if b.kind == BlockKind.PARAGRAPH and b.text == "numbered item"]
    assert paras
    assert paras[0].numbering is not None
    assert paras[0].numbering.lvl_text is None
    assert ext.snapshot.status == ExtractionStatus.NEEDS_REVIEW
