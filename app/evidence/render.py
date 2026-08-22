"""确定性页图渲染：把页输入渲染为不可变 PNG 字节（Slice 4.3，worker_02）。

渲染与 OCR 完全独立：本地渲染不消耗共享 oMLX 门禁额度。输出对同一输入与
渲染器版本确定（同一字节输入 -> 同一 PNG 字节 -> 同一 ``page_image_sha256``），
支持内容寻址去重与可复现页产物。

- PDF 系（pdf / docx / doc 转出的 PDF）用 fitz 按固定 DPI 渲染指定页；
- 普通图片 / 多帧 TIFF 用 Pillow 解码（TIFF 按 ``original_frame`` 定位帧）；
- 文本页把解码文本确定性绘制到 A4@150dpi 画布（CJK 字体按候选解析，缺失时
  显式失败，绝不用空白/错字图冒充成功）。

本模块是纯确定性函数，不写存储；不可变落盘见 ``artifacts.ArtifactStore``。
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

from app.evidence.paging import PageInput
from app.evidence.text import decode_text_bytes

#: 渲染器身份版本：任一渲染行为（DPI/编码/字体）变化必须提升该版本，
#: 否则同一输入会产生不同页图却复用同一渲染器身份。
RENDERER_VERSION = "slice4.3/render/v1"

#: 固定渲染 DPI（PDF 与页图均按此换算）。
RENDER_DPI = 150
_PIXELS_PER_POINT = RENDER_DPI / 72.0

#: 文本页画布（A4 @ 150 DPI，像素）。
_TEXT_PAGE_WIDTH = 1240
_TEXT_PAGE_HEIGHT = 1754
_TEXT_MARGIN = 64
_TEXT_FONT_SIZE = 20
_TEXT_LINE_HEIGHT = 30

#: macOS 单机可用的 CJK 字体候选（按优先级）；缺失时文本页渲染显式失败。
_CJK_FONT_CANDIDATES = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
)


class RenderError(ValueError):
    """页图渲染确定性错误。"""


@dataclass(frozen=True)
class RenderedPage:
    """一页的不可变渲染产物：PNG 字节 + 像素尺寸 + 渲染器版本。"""

    image_bytes: bytes
    width: int
    height: int
    renderer_version: str


def _resolve_cjk_font() -> Path:
    for candidate in _CJK_FONT_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            return path
    raise RenderError(
        "文本页渲染不可用：未找到可用的 CJK 字体（系统字体缺失），"
        "无法确定性绘制文本页图"
    )


def _render_pdf_page(
    pdf_bytes: bytes, page_number: int, renderer_version: str
) -> RenderedPage:
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            page = doc[page_number - 1]
            pix = page.get_pixmap(  # type: ignore[attr-defined] - fitz stub 未覆盖 get_pixmap
                matrix=fitz.Matrix(_PIXELS_PER_POINT, _PIXELS_PER_POINT), alpha=False
            )
            image_bytes = pix.tobytes("png")
            return RenderedPage(
                image_bytes=image_bytes,
                width=pix.width,
                height=pix.height,
                renderer_version=renderer_version,
            )
    except Exception as exc:
        raise RenderError(
            f"PDF 第 {page_number} 页渲染失败：{type(exc).__name__}: {exc}"
        ) from exc


def _render_pillow_page(
    content: bytes,
    *,
    original_frame: str | None,
    renderer_version: str,
) -> RenderedPage:
    try:
        with Image.open(io.BytesIO(content)) as source:
            if original_frame is not None:
                if not original_frame.startswith("frame-"):
                    raise RenderError(f"未知 TIFF 帧标识：{original_frame!r}")
                frame_index = int(original_frame.split("-", 1)[1]) - 1
                source.seek(frame_index)
            rgb = source.convert("RGB")
            buffer = io.BytesIO()
            rgb.save(buffer, format="PNG")
            return RenderedPage(
                image_bytes=buffer.getvalue(),
                width=rgb.width,
                height=rgb.height,
                renderer_version=renderer_version,
            )
    except RenderError:
        raise
    except Exception as exc:
        raise RenderError(
            f"图片页渲染失败：{type(exc).__name__}: {exc}"
        ) from exc


def _wrap_lines(text: str, *, width: int, font: ImageFont.FreeTypeFont) -> list[str]:
    """按像素宽度换行（整行超宽则逐字符截断，避免丢字）。"""
    lines: list[str] = []
    for raw in text.split("\n"):
        line = raw
        while True:
            if font.getlength(line) <= width:
                lines.append(line)
                break
            # 二分找可容纳的最长前缀。
            low, high = 0, len(line)
            best = 0
            while low <= high:
                mid = (low + high) // 2
                if font.getlength(line[:mid]) <= width:
                    best = mid
                    low = mid + 1
                else:
                    high = mid - 1
            if best <= 0:
                best = 1
            lines.append(line[:best])
            line = line[best:]
    return lines


def _render_text_page(content: bytes, renderer_version: str) -> RenderedPage:
    decoded = decode_text_bytes(content)
    font_path = _resolve_cjk_font()
    image = Image.new("RGB", (_TEXT_PAGE_WIDTH, _TEXT_PAGE_HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype(str(font_path), _TEXT_FONT_SIZE)
    except Exception as exc:
        raise RenderError(
            f"文本页渲染失败：无法加载 CJK 字体 {font_path}: {exc}"
        ) from exc
    usable_width = _TEXT_PAGE_WIDTH - 2 * _TEXT_MARGIN
    y = _TEXT_MARGIN
    for line in _wrap_lines(decoded.text, width=usable_width, font=font):
        if y + _TEXT_FONT_SIZE > _TEXT_PAGE_HEIGHT - _TEXT_MARGIN:
            break
        draw.text((_TEXT_MARGIN, y), line, fill="black", font=font)
        y += _TEXT_LINE_HEIGHT
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return RenderedPage(
        image_bytes=buffer.getvalue(),
        width=_TEXT_PAGE_WIDTH,
        height=_TEXT_PAGE_HEIGHT,
        renderer_version=renderer_version,
    )


def render_page_image(page_input: PageInput, *, renderer_version: str = RENDERER_VERSION) -> RenderedPage:
    """渲染一个成功页输入为不可变 PNG 页图。

    失败页输入（``page_input.expects_failure``）无渲染源，直接抛出
    :class:`RenderError`；渲染失败同样抛出，由调用方决定是否降级为失败页。
    """
    if page_input.render_source is None:
        raise RenderError(
            f"失败页（页码 {page_input.page_number}）没有可渲染的输入字节"
        )
    media_kind = page_input.media_kind
    if media_kind in {"pdf", "docx", "doc"}:
        return _render_pdf_page(
            page_input.render_source, page_input.page_number, renderer_version
        )
    if media_kind in {"image", "tiff"}:
        return _render_pillow_page(
            page_input.render_source,
            original_frame=page_input.original_frame,
            renderer_version=renderer_version,
        )
    if media_kind == "text":
        return _render_text_page(page_input.render_source, renderer_version)
    raise RenderError(f"未知页类别 {media_kind!r}，无法渲染页图")
