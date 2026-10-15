"""诚实定位器测试：精度阶梯、重复文本消歧与降级诚实性。"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.domain.contracts.enums import DisambiguationOutcome, LocatorPrecision
from app.evidence import (
    extract_native_page,
    find_all_whitespace_insensitive,
    locate_target,
)
from app.evidence.pdf_native import NativeChar, NativePage

NATIVE_PDF = Path(__file__).resolve().parent / "generated-gold" / "native-01.pdf"


def _locate(pdf_path, page_index, target: str):
    page = extract_native_page(pdf_path, page_index)
    sha = hashlib.sha256(page.text.encode("utf-8")).hexdigest()
    return page, locate_target(
        page,
        target,
        source_text_sha256=sha,
        page_artifact_id=f"artifact-page-{page.page_number}",
    )


def test_whitespace_insensitive_matching(gold_set) -> None:
    text = "否认 高血压 病史，血肌酐 76.1"
    hits = find_all_whitespace_insensitive(text, "否认高血压病史")
    assert hits == [(0, 9)]
    hits = find_all_whitespace_insensitive("A\nB\nA\nB", "AB")
    assert len(hits) == 2
    assert hits == [(0, 3), (4, 7)]


def test_unique_target_yields_bbox_on_native_page(gold_root, gold_set) -> None:
    page, result = _locate(gold_root / "native-01.pdf", 0, "否认高血压病史")
    assert result.precision == LocatorPrecision.BBOX
    assert result.disambiguation == DisambiguationOutcome.UNIQUE_MATCH
    assert result.bbox is not None
    assert result.coordinate_frame is not None
    assert result.coordinate_frame.page_width == page.page_width
    assert result.coordinate_frame.page_height == page.page_height
    # bbox 必须落在页面内。
    assert 0 <= result.bbox.x0 < result.bbox.x1 <= page.page_width
    assert 0 <= result.bbox.y0 < result.bbox.y1 <= page.page_height


def test_repeated_target_degrades_to_page_excerpt(gold_root, gold_set) -> None:
    _, result = _locate(gold_root / "native-01.pdf", 1, "已签署知情同意书")
    assert result.precision == LocatorPrecision.PAGE_EXCERPT
    assert result.disambiguation == DisambiguationOutcome.REPEATED_TEXT_DEGRADED
    assert result.bbox is None
    assert result.coordinate_frame is None
    assert result.degradation_reason
    assert "消歧" in result.degradation_reason


def test_overlapping_native_targets_never_fake_unique_bbox() -> None:
    """重叠出现也属于重复文本，不能因游标跳过第二处而误画唯一红框。"""
    chars = tuple(
        NativeChar(
            text=character,
            x0=float(index * 10),
            y0=10.0,
            x1=float(index * 10 + 8),
            y1=20.0,
            start=index,
        )
        for index, character in enumerate("AAA")
    )
    page = NativePage(
        page_number=1,
        text="AAA",
        chars=chars,
        words=(),
        page_width=100.0,
        page_height=100.0,
        rotation=0,
    )
    result = locate_target(
        page,
        "AA",
        source_text_sha256=hashlib.sha256(page.text.encode("utf-8")).hexdigest(),
        page_artifact_id="artifact-overlap",
    )

    assert result.precision == LocatorPrecision.PAGE_EXCERPT
    assert result.disambiguation == DisambiguationOutcome.REPEATED_TEXT_DEGRADED
    assert result.bbox is None


def test_missing_target_degrades_to_page_only(gold_root, gold_set) -> None:
    _, result = _locate(gold_root / "native-01.pdf", 0, "不存在的文本内容")
    assert result.precision == LocatorPrecision.PAGE_ONLY
    assert result.disambiguation == DisambiguationOutcome.NOT_FOUND
    assert result.bbox is None
    assert result.degradation_reason


def test_locator_rejects_mismatched_source_text_hash(gold_root) -> None:
    page = extract_native_page(gold_root / "native-01.pdf", 0)
    with pytest.raises(ValueError, match="来源文本哈希"):
        locate_target(
            page,
            "不存在的文本内容",
            source_text_sha256="a" * 64,
            page_artifact_id="artifact-page-1",
        )


def test_repeated_table_date_never_fakes_bbox(gold_root, gold_set) -> None:
    _, result = _locate(gold_root / "native-01.pdf", 2, "2026-03-14")
    assert result.precision != LocatorPrecision.BBOX
    assert result.disambiguation == DisambiguationOutcome.REPEATED_TEXT_DEGRADED


def test_bbox_maps_to_gold_drawn_region(gold_root, gold_set) -> None:
    """坐标 spike 核心断言：定位 bbox 换算到页图像素后与真实绘制区域重叠。"""
    from app.evidence import bbox_overlap_ratio, pdf_points_to_image_pixels

    _page, result = _locate(gold_root / "native-01.pdf", 0, "76.1")
    assert result.precision == LocatorPrecision.BBOX
    gold_target = next(
        t for t in gold_set.pages_for("native-01.pdf")[0].targets if t.text == "76.1"
    )
    assert gold_target.expected_pixel_bbox is not None
    mapped = pdf_points_to_image_pixels(
        result.bbox, result.coordinate_frame, pixels_per_point=150 / 72.0
    )
    iou = bbox_overlap_ratio(mapped, gold_target.expected_pixel_bbox)
    assert iou >= 0.5
