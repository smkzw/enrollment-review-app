"""真实方案只读回归：MG-K10-SAR 与 CMS-D001 结构提取、字节身份与覆盖门槛。

源方案只读：每次测试前后哈希与 stat 断言字节身份不变、源目录无派生写入；
提取与渲染仅写入临时输出目录。文件缺失时跳过（本机验收时二者均在位）。
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from app.protocols.docx_structure import BlockKind, extract_docx_structure
from app.protocols.ingestion import register_source_artifact
from app.protocols.rendering import pdf_page_texts, render_to_pdf
from app.protocols.source_alignment import (
    align_blocks,
    verify_excerpt_against_blocks,
    verify_excerpt_against_page,
)

REAL_PROTOCOLS = [
    (
        "MG-K10-SAR",
        "/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/"
        "MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx",
    ),
    (
        "CMS-D001",
        "/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/"
        "CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx",
    ),
]

# 「低得不合理」的覆盖门槛：任一门槛不满足即视为提取失败（非空结果伪装成功）。
MIN_PARAGRAPHS = 1000
MIN_TABLES = 20
MIN_SECTIONS = 5


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_snapshot(path: Path):
    st = path.stat()
    return {
        "sha256": _sha256(path),
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "siblings": sorted(p.name for p in path.parent.iterdir()),
    }


@pytest.mark.parametrize("label,path", REAL_PROTOCOLS)
def test_real_protocol_extraction_coverage_and_numbering(label, path, tmp_path):
    source = Path(path)
    if not source.is_file():
        pytest.skip(f"真实方案文件缺失：{source}")

    before = _source_snapshot(source)
    artifact = register_source_artifact(
        source, source_artifact_id=label, storage_root=tmp_path
    )
    ext = extract_docx_structure(
        source, snapshot_id=f"{label}-snap", source_artifact=artifact, output_dir=tmp_path
    )
    after = _source_snapshot(source)

    # 1) 字节身份：源文件哈希/大小/mtime 与源目录列表完全不变
    assert after["sha256"] == before["sha256"]
    assert after["size"] == before["size"]
    assert after["mtime_ns"] == before["mtime_ns"]
    assert after["siblings"] == before["siblings"], "源目录出现了派生写入"

    # 2) 覆盖门槛：零/过低段落、表格、section 一律视为失败
    cov = ext.snapshot.coverage
    assert cov.paragraph_count >= MIN_PARAGRAPHS, cov
    assert cov.table_count >= MIN_TABLES, cov
    assert cov.section_count >= MIN_SECTIONS, cov

    # 3) 规范块集工件真实存在且哈希一致
    blob = Path(tmp_path) / ext.snapshot.content_storage_ref
    assert blob.is_file()
    assert _sha256(blob) == ext.snapshot.content_sha256

    # 4) 编号：无未解析编号异常；至少存在可还原官方编号文本的编号块
    unresolved = [a for a in ext.snapshot.anomalies if a.kind == "unresolved_numbering"]
    assert unresolved == []
    numbered = [
        b for b in ext.blocks
        if b.kind == BlockKind.PARAGRAPH and b.numbering is not None and b.numbering.lvl_text
    ]
    assert len(numbered) > 100, f"{label} 可解析编号块过少：{len(numbered)}"


@pytest.mark.parametrize("label,path", REAL_PROTOCOLS)
def test_real_protocol_artifact_sha256_stable(label, path, tmp_path):
    """同一源文件两次登记的 SHA-256 必须稳定一致（不可变登记基础）。"""
    source = Path(path)
    if not source.is_file():
        pytest.skip(f"真实方案文件缺失：{source}")
    a1 = register_source_artifact(
        source, source_artifact_id=f"{label}-a", storage_root=tmp_path
    )
    a2 = register_source_artifact(
        source, source_artifact_id=f"{label}-b", storage_root=tmp_path
    )
    assert a1.sha256 == a2.sha256
    assert a1.size_bytes == a2.size_bytes == source.stat().st_size


@pytest.mark.parametrize("label,path", REAL_PROTOCOLS)
def test_real_protocol_render_and_source_alignment(label, path, tmp_path):
    """真实长方案必须完成只读渲染、逐页读取和可核验的双通道来源对齐。"""
    source = Path(path)
    if not source.is_file():
        pytest.skip(f"真实方案文件缺失：{source}")

    before = _source_snapshot(source)
    artifact = register_source_artifact(
        source, source_artifact_id=f"{label}-render", storage_root=tmp_path
    )
    extraction = extract_docx_structure(
        source,
        snapshot_id=f"{label}-render-snap",
        source_artifact=artifact,
        output_dir=tmp_path,
    )
    rendered = render_to_pdf(
        source, tmp_path / "rendered", source_artifact=artifact
    )

    assert rendered.status.value == "succeeded", rendered.render_error
    assert rendered.pdf_path is not None and rendered.pdf_path.is_file()
    assert rendered.page_count is not None and rendered.page_count > 100
    pages = pdf_page_texts(rendered.pdf_path)
    assert len(pages) == rendered.page_count

    aligned = align_blocks(
        extraction.blocks,
        snapshot_id=extraction.snapshot.snapshot_id,
        render_artifact_id=f"{label}-render-artifact",
        page_texts=pages,
    )
    assert len(aligned.spans) == len(extraction.blocks)
    assert aligned.aligned > 0
    assert aligned.aligned + aligned.degraded > aligned.unaligned * 0.25

    material_spans = [span for span in aligned.spans if span.excerpt]
    assert material_spans
    assert all(
        verify_excerpt_against_blocks(
            extraction.blocks, span.source_ref, span.excerpt or ""
        )
        for span in material_spans
    )
    precise_spans = [
        span
        for span in aligned.spans
        if span.precision.value == "text_range"
    ]
    assert precise_spans
    assert all(
        span.render_page is not None
        and verify_excerpt_against_page(span, pages[span.render_page - 1])
        for span in precise_spans
    )
    claimed_ranges = [
        (span.render_page, span.text_start, span.text_end)
        for span in precise_spans
    ]
    assert len(claimed_ranges) == len(set(claimed_ranges)), (
        "不同结构块不得共享同一精确渲染范围"
    )

    after = _source_snapshot(source)
    assert after == before, "真实方案或其所在目录被渲染/对齐流程改写"
