"""原生 PDF 字符/词坐标提取（pdfplumber）。

正式坐标路径使用 ``pdfplumber``（MIT 许可）读取字符/词对象，并统一到 PDF
points 坐标系（原点左下、y 向上）。本模块把 pdfplumber 原生对象转成稳定的
阅读顺序文本 + 字符级 box，字符 box 直接映射回页图坐标系（见 ``coordinates``）。

页面文本由字符对象确定性装配（按行内 x 序 + 行间垂直重叠分组的阅读顺序），
保证文本偏移与字符 box 一一对应，供定位器生成真实的 ``text_range``/``bbox``。
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import pdfplumber


@dataclass(frozen=True)
class NativeChar:
    """单个字符及其 PDF points 坐标（原点左下、y 向上）。"""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    # 该字符在页面装配文本 ``NativePage.text`` 中的起始偏移。
    start: int


@dataclass(frozen=True)
class NativeWord:
    """pdfplumber 原生词及其 PDF points 坐标。"""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class NativePage:
    """一页的原生文本、字符坐标、可视页尺寸与旋转。

    ``page_width/page_height`` 与字符坐标同属 pdfplumber 的可视页 y-up frame；旋转页
    只在阅读顺序排序时还原为逻辑坐标，返回的字符 bbox 不再做二次旋转。
    """

    page_number: int
    text: str
    chars: tuple[NativeChar, ...]
    words: tuple[NativeWord, ...]
    page_width: float
    page_height: float
    rotation: int

    def chars_in_range(self, start: int, end: int) -> tuple[NativeChar, ...]:
        """返回文本区间 ``[start, end)`` 覆盖到的字符（含与该区间重叠的字符）。"""
        return tuple(
            c
            for c in self.chars
            if c.start < end and c.start + len(c.text) > start
        )


_LINE_OVERLAP_TOLERANCE = 1.5  # points


@dataclass(frozen=True)
class _CanonicalChar:
    """字符在未旋转 PDF 阅读坐标中的 bbox，保留可显示的原始字符。"""

    display: NativeChar
    x0: float
    y0: float
    x1: float
    y1: float


def _to_canonical_char(
    char: NativeChar,
    *,
    page_width: float,
    page_height: float,
    rotation: int,
) -> _CanonicalChar:
    """将 pdfplumber 的可视旋转页坐标还原为逻辑阅读坐标。

    pdfplumber exposes a rotated page's visible width/height and y-up
    coordinates.  Keeping the returned ``NativeChar`` in that visible frame
    makes the later page-image mapping correct; only sorting uses this
    unrotated frame so 180/270 degree pages do not reverse the text.
    """
    if rotation == 0:
        x0, y0, x1, y1 = char.x0, char.y0, char.x1, char.y1
    elif rotation == 90:
        x0 = page_height - char.y1
        x1 = page_height - char.y0
        y0, y1 = char.x0, char.x1
    elif rotation == 180:
        x0 = page_width - char.x1
        x1 = page_width - char.x0
        y0 = page_height - char.y1
        y1 = page_height - char.y0
    elif rotation == 270:
        x0, x1 = char.y0, char.y1
        y0 = page_width - char.x1
        y1 = page_width - char.x0
    else:  # pragma: no cover - guarded by extract_native_page
        raise ValueError(f"不支持的页面旋转角度: {rotation}")
    return _CanonicalChar(display=char, x0=x0, y0=y0, x1=x1, y1=y1)


def _group_lines(
    chars: list[NativeChar],
    *,
    page_width: float,
    page_height: float,
    rotation: int,
) -> list[list[_CanonicalChar]]:
    """按逻辑阅读坐标分组，输出保持可映射到旋转页图的字符坐标。"""
    canonical_chars = [
        _to_canonical_char(
            char,
            page_width=page_width,
            page_height=page_height,
            rotation=rotation,
        )
        for char in chars
    ]
    lines: list[dict] = []
    for c in sorted(canonical_chars, key=lambda c: (-c.y1, c.x0, c.display.start)):
        placed = False
        for line in lines:
            if c.y1 >= line["y_bottom"] - _LINE_OVERLAP_TOLERANCE and c.y0 <= line["y_top"] + _LINE_OVERLAP_TOLERANCE:
                line["chars"].append(c)
                line["y_top"] = max(line["y_top"], c.y1)
                line["y_bottom"] = min(line["y_bottom"], c.y0)
                placed = True
                break
        if not placed:
            lines.append({"chars": [c], "y_top": c.y1, "y_bottom": c.y0})
    lines.sort(key=lambda line: -line["y_top"])
    result = []
    for line in lines:
        line["chars"].sort(key=lambda c: (c.x0, c.display.start))
        result.append(line["chars"])
    return result


def _space_threshold(chars: list[_CanonicalChar]) -> float:
    """同一行内插入空格的最小水平间隙（以行内字符宽度的中位数估计）。"""
    widths = [c.x1 - c.x0 for c in chars if c.x1 > c.x0]
    if not widths:
        return 0.0
    ordered = sorted(widths)
    median = ordered[len(ordered) // 2]
    return max(0.0, median * 0.5)


def _build_text_with_offsets(
    lines: list[list[_CanonicalChar]],
) -> tuple[str, list[NativeChar]]:
    """装配阅读顺序文本，并为每个字符返回其在文本中的起始偏移。"""
    text_parts: list[str] = []
    placed: list[NativeChar] = []
    offset = 0
    for line_index, line in enumerate(lines):
        if line_index > 0:
            text_parts.append("\n")
            offset += 1
        gap = _space_threshold(line)
        previous_x1: float | None = None
        for c in line:
            if previous_x1 is not None and c.x0 - previous_x1 > gap > 0:
                text_parts.append(" ")
                offset += 1
            placed.append(NativeChar(c.display.text, c.display.x0, c.display.y0, c.display.x1, c.display.y1, offset))
            text_parts.append(c.display.text)
            offset += len(c.display.text)
            previous_x1 = c.x1
    return "".join(text_parts), placed


def _build_words(lines: list[list[_CanonicalChar]]) -> list[NativeWord]:
    """从同一逻辑行序构造词，避免旋转页沿用 pdfplumber 的可视逆序词。"""
    words: list[NativeWord] = []

    def append_word(word_chars: list[NativeChar]) -> None:
        if not word_chars:
            return
        words.append(
            NativeWord(
                text="".join(char.text for char in word_chars),
                x0=min(char.x0 for char in word_chars),
                y0=min(char.y0 for char in word_chars),
                x1=max(char.x1 for char in word_chars),
                y1=max(char.y1 for char in word_chars),
            )
        )

    for line in lines:
        gap = _space_threshold(line)
        word_chars: list[NativeChar] = []
        previous_x1: float | None = None

        for canonical in line:
            char = canonical.display
            separated_by_gap = previous_x1 is not None and canonical.x0 - previous_x1 > gap > 0
            if char.text.isspace() or separated_by_gap:
                append_word(word_chars)
                word_chars.clear()
            if not char.text.isspace():
                word_chars.append(char)
            previous_x1 = canonical.x1
        append_word(word_chars)
    return words


_NATIVE_COORDINATES_SCHEMA = "native_coordinates/v1"


def serialize_native_coordinates(page: NativePage) -> bytes:
    """把原生页的字符/词坐标序列化为确定性 UTF-8 JSON（内容寻址工件）。

    JSON 用 ``sort_keys`` 与紧凑分隔符（与 ``canonical_hash`` 一致），同一
    ``NativePage`` 得到相同字节，供 ``native_coordinates_sha256`` 内容寻址。
    定位器用 ``chars`` 的 ``start`` 偏移把 ``text_range`` 还原为字符并集 bbox。
    """
    import json

    payload = {
        "schema": _NATIVE_COORDINATES_SCHEMA,
        "page_number": page.page_number,
        "page_width": page.page_width,
        "page_height": page.page_height,
        "rotation": page.rotation,
        "text": page.text,
        "words": [
            {
                "text": word.text,
                "x0": word.x0,
                "y0": word.y0,
                "x1": word.x1,
                "y1": word.y1,
            }
            for word in page.words
        ],
        "chars": [
            {
                "text": char.text,
                "start": char.start,
                "x0": char.x0,
                "y0": char.y0,
                "x1": char.x1,
                "y1": char.y1,
            }
            for char in page.chars
        ],
    }
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def extract_native_page(pdf_path: str | Path | bytes, page_index: int) -> NativePage:
    """用 pdfplumber 提取第 ``page_index``（0 基）页的原生文本与坐标。

    ``pdf_path`` 可以是文件路径或内存中的 PDF 字节（用于转换产物，如 DOCX
    经 LibreOffice 转出的 PDF，避免临时文件破坏确定性）。
    """
    opener = (
        pdfplumber.open(io.BytesIO(pdf_path))
        if isinstance(pdf_path, bytes)
        else pdfplumber.open(str(pdf_path))
    )
    with opener as pdf:
        page = pdf.pages[page_index]
        native_chars = [
            NativeChar(
                text=c["text"],
                x0=float(c["x0"]),
                y0=float(c["y0"]),
                x1=float(c["x1"]),
                y1=float(c["y1"]),
                start=0,
            )
            for c in page.chars
        ]
        rotation = int(getattr(page, "rotation", 0) or 0) % 360
        if rotation not in {0, 90, 180, 270}:
            raise ValueError(f"PDF 页面旋转必须是 0/90/180/270 度，实际为 {rotation}")
        page_width = float(page.width)
        page_height = float(page.height)
        ordered_lines = _group_lines(
            native_chars,
            page_width=page_width,
            page_height=page_height,
            rotation=rotation,
        )
        text, placed = _build_text_with_offsets(ordered_lines)
        words = _build_words(ordered_lines)
        return NativePage(
            page_number=page_index + 1,
            text=text,
            chars=tuple(placed),
            words=tuple(words),
            page_width=page_width,
            page_height=page_height,
            rotation=rotation,
        )
