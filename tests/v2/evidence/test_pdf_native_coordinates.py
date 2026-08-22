"""原生 PDF 提取与坐标系统测试（pdfplumber + 纯换算）。"""
from __future__ import annotations

import hashlib

import fitz
import pytest

from app.domain.contracts.enums import CoordinateSpace
from app.domain.contracts.evidence import BoundingBox
from app.domain.contracts.ocr import CoordinateFrame
from app.evidence import coordinates, pdf_native

SCALE = 150 / 72.0


def _frame() -> CoordinateFrame:
    return CoordinateFrame(
        space=CoordinateSpace.PDF_POINTS,
        page_width=595.0,
        page_height=842.0,
        rotation=0,
        transform_version="slice4.0/v1",
    )


def test_pdf_points_to_image_pixels_flips_y_axis() -> None:
    # PDF points 原点左下、y 向上；页图像素原点左上、y 向下。
    bbox = BoundingBox(x0=72.0, y0=749.2, x1=170.0, y1=763.2)
    mapped = coordinates.pdf_points_to_image_pixels(bbox, _frame(), pixels_per_point=SCALE)
    assert mapped.x0 == pytest.approx(72 * SCALE)
    assert mapped.y0 == pytest.approx((842 - 763.2) * SCALE)
    assert mapped.x1 == pytest.approx(170 * SCALE)
    assert mapped.y1 == pytest.approx((842 - 749.2) * SCALE)
    # 图像空间内 top 更小（靠近页顶）。
    assert mapped.y0 < mapped.y1


def test_image_pixels_roundtrip_to_pdf_points() -> None:
    pdf = BoundingBox(x0=72.0, y0=749.2, x1=226.0, y1=763.2)
    mapped = coordinates.pdf_points_to_image_pixels(pdf, _frame(), pixels_per_point=SCALE)
    image_frame = CoordinateFrame(
        space=CoordinateSpace.PAGE_IMAGE_PIXELS,
        page_width=595.0,
        page_height=842.0,
        rotation=0,
        transform_version="slice4.0/v1",
    )
    back = coordinates.image_pixels_to_pdf_points(mapped, image_frame, pixels_per_point=SCALE)
    assert back.x0 == pytest.approx(pdf.x0, abs=1e-6)
    assert back.y0 == pytest.approx(pdf.y0, abs=1e-6)
    assert back.x1 == pytest.approx(pdf.x1, abs=1e-6)
    assert back.y1 == pytest.approx(pdf.y1, abs=1e-6)


def test_coordinate_out_of_bounds_rejected() -> None:
    with pytest.raises(coordinates.CoordinateError):
        coordinates.pdf_points_to_image_pixels(
            BoundingBox(x0=0, y0=0, x1=1000, y1=100), _frame(), pixels_per_point=SCALE
        )


def test_extract_native_page_reading_order_and_bounds(gold_root, gold_set) -> None:
    pdf = gold_root / "native-01.pdf"
    page = pdf_native.extract_native_page(pdf, 0)
    assert page.page_number == 1
    assert page.page_width == 595.0
    assert page.page_height == 842.0
    # 第一行在文本最前（阅读顺序自顶向下）。
    assert page.text.startswith("受试者张三")
    assert "否认高血压病史" in page.text
    assert page.words[0].text.startswith("受试者张三")
    # 字符坐标全部在页面边界内。
    for char in page.chars:
        assert 0 <= char.x0 < char.x1 <= page.page_width
        assert 0 <= char.y0 < char.y1 <= page.page_height
    for word in page.words:
        assert 0 <= word.x0 < word.x1 <= page.page_width
        assert 0 <= word.y0 < word.y1 <= page.page_height
    # 字符偏移与文本切片一致。
    for char in page.chars[:5]:
        assert page.text[char.start : char.start + len(char.text)] == char.text


def test_extract_native_page_chars_in_range_maps_offsets(gold_root, gold_set) -> None:
    pdf = gold_root / "native-01.pdf"
    page = pdf_native.extract_native_page(pdf, 0)
    index = page.text.find("否认高血压病史")
    assert index >= 0
    chars = page.chars_in_range(index, index + len("否认高血压病史"))
    assert len(chars) >= len("否认高血压病史")
    combined = "".join(c.text for c in chars)
    assert "否认高血压病史" in combined
    # bbox 由字符并集计算，落在页面内且非退化。
    bbox = coordinates.BoundingBox(
        x0=min(c.x0 for c in chars),
        y0=min(c.y0 for c in chars),
        x1=max(c.x1 for c in chars),
        y1=max(c.y1 for c in chars),
    )
    assert bbox.x1 > bbox.x0
    assert bbox.y1 > bbox.y0


def test_scanned_pdf_has_no_native_text_layer(gold_root, gold_set) -> None:
    pdf = gold_root / "scanned-01.pdf"
    page = pdf_native.extract_native_page(pdf, 0)
    assert page.text == ""
    assert not page.chars


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_rotated_pdf_preserves_reading_order_and_pixel_mapping(tmp_path, rotation) -> None:
    """Rotation is part of the supported coordinate contract, not metadata only."""
    pdf_path = tmp_path / f"rotated-{rotation}.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    target = "ROTATED TARGET"
    expected_text = f"{target}\nSECOND LINE"
    page.insert_text((72, 100), target, fontsize=14)
    page.insert_text((72, 140), "SECOND LINE", fontsize=14)
    page.set_rotation(rotation)
    doc.save(pdf_path)
    doc.close()

    native = pdf_native.extract_native_page(pdf_path, 0)
    assert native.text == expected_text
    assert [word.text for word in native.words] == ["ROTATED", "TARGET", "SECOND", "LINE"]
    source_hash = hashlib.sha256(native.text.encode("utf-8")).hexdigest()
    from app.evidence import (
        bbox_overlap_ratio,
        locate_target,
        pdf_points_to_image_pixels,
    )

    result = locate_target(
        native,
        target,
        source_text_sha256=source_hash,
        page_artifact_id=f"artifact-rotation-{rotation}",
    )
    assert result.bbox is not None
    assert result.coordinate_frame is not None

    with fitz.open(pdf_path) as rendered_doc:
        rendered_page = rendered_doc[0]
        pix = rendered_page.get_pixmap(matrix=fitz.Matrix(SCALE, SCALE), alpha=False)
        expected = rendered_page.search_for(target)[0] * rendered_page.rotation_matrix
    expected_bbox = BoundingBox(
        x0=expected.x0 * SCALE,
        y0=expected.y0 * SCALE,
        x1=expected.x1 * SCALE,
        y1=expected.y1 * SCALE,
    )
    mapped = pdf_points_to_image_pixels(
        result.bbox,
        result.coordinate_frame,
        pixels_per_point=SCALE,
    )
    assert 0 <= mapped.x0 < mapped.x1 <= pix.width
    assert 0 <= mapped.y0 < mapped.y1 <= pix.height
    assert bbox_overlap_ratio(mapped, expected_bbox) >= 0.5
