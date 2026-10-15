"""WP03/A01 路线判定：页码文字层不冒充全文读取成功。

场景矩阵（impl_v4 03_WORK_PACKAGES WP03 / 05_ACCEPTANCE A01）：
- 正文是整页扫描图、文字层只有页码 -> VISION_OCR（不把非空native当全文）；
- 只有无图正文/短文本页 -> 维持原生路线（不凭字符数猜测）；
- 正文文字+小logo图 -> 维持原生路线；
- 可检索扫描PDF（隐藏文字层覆盖正文）-> 维持原生路线。
"""
from __future__ import annotations

import fitz
import pytest

from app.domain.contracts.enums import ExtractionRoute
from app.evidence.paging import page_source_document
from app.evidence.page_processor import decide_route_detailed

A4_W, A4_H = 595.0, 842.0


def _png_bytes(width: int = 100, height: int = 100) -> bytes:
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, width, height))
    pix.set_rect(pix.irect, (200, 200, 200))
    return pix.tobytes("png")


def _pdf_page_bytes(build) -> bytes:
    doc = fitz.open()
    build(doc.new_page(width=A4_W, height=A4_H))
    return doc.tobytes()


def _decide(pdf_bytes: bytes):
    plan = page_source_document(
        content=pdf_bytes, media_kind="pdf", source_sha256="a" * 64,
    )
    assert len(plan.pages) == 1
    page = plan.pages[0]
    assert not page.expects_failure
    return decide_route_detailed(page)


def _footer(page: fitz.Page) -> None:
    page.insert_text((A4_W / 2 - 20, A4_H - 30), "第 1 页", fontsize=9)


def test_footer_text_over_fullpage_bitmap_routes_to_vision() -> None:
    """A01 核心场景：正文整页扫描图 + 页码文字层 -> VISION_OCR。"""
    png = _png_bytes()

    def build(page: fitz.Page) -> None:
        page.insert_image(fitz.Rect(0, 0, A4_W, A4_H), stream=png)
        _footer(page)

    route, detail = _decide(_pdf_page_bytes(build))
    assert route is ExtractionRoute.VISION_OCR
    assert detail == "native_text_marginal_over_bitmap_body"


def test_footer_text_without_bitmap_keeps_native() -> None:
    """只有页脚文字、无大图：维持原生路线（缺大图信号不降级）。"""

    def build(page: fitz.Page) -> None:
        _footer(page)

    route, detail = _decide(_pdf_page_bytes(build))
    assert route is ExtractionRoute.NATIVE_PDF_TEXT
    assert detail is None


def test_body_text_with_small_logo_keeps_native() -> None:
    """正文文字 + 小面积logo图：小图不满足大图阈值，维持原生路线。"""
    png = _png_bytes()

    def build(page: fitz.Page) -> None:
        page.insert_image(fitz.Rect(40, 40, 100, 80), stream=png)
        for index in range(10):
            page.insert_text(
                (72, 120 + index * 20), f"既往史记录第{index}行内容。", fontsize=10,
            )

    route, detail = _decide(_pdf_page_bytes(build))
    assert route is ExtractionRoute.NATIVE_PDF_TEXT
    assert detail is None


def test_short_body_without_bitmap_keeps_native() -> None:
    """短正文页（类似gold夹具的3行文本）：无大图即不触发A01降级。"""

    def build(page: fitz.Page) -> None:
        for index in range(3):
            page.insert_text(
                (72, 90 + index * 30), f"受试者记录第{index}行。", fontsize=10,
            )
        _footer(page)

    route, detail = _decide(_pdf_page_bytes(build))
    assert route is ExtractionRoute.NATIVE_PDF_TEXT
    assert detail is None


def test_searchable_scan_with_body_text_layer_keeps_native() -> None:
    """可检索扫描PDF：隐藏文字层覆盖正文（行带覆盖高）-> 维持原生路线。"""
    png = _png_bytes()

    def build(page: fitz.Page) -> None:
        page.insert_image(fitz.Rect(0, 0, A4_W, A4_H), stream=png)
        for index in range(25):
            page.insert_text(
                (72, 90 + index * 24), f"检验记录第{index}行，数值与单位。", fontsize=10,
            )

    route, detail = _decide(_pdf_page_bytes(build))
    assert route is ExtractionRoute.NATIVE_PDF_TEXT
    assert detail is None


@pytest.mark.parametrize("width,height,expected", [
    (595, 842, 1.0),
])
def test_large_image_coverage_bounds(width, height, expected) -> None:
    """图像覆盖率钳制：整页图占比上限为1.0。"""
    from app.evidence.pdf_native import extract_native_page

    png = _png_bytes()

    def build(page: fitz.Page) -> None:
        page.insert_image(fitz.Rect(0, 0, width, height), stream=png)

    page = extract_native_page(_pdf_page_bytes(build), 0)
    assert page.large_image_coverage == pytest.approx(expected)
