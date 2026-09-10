"""原生 PDF 字符/词坐标提取（pdfplumber）。

正式坐标路径使用 ``pdfplumber``（MIT 许可）读取字符/词对象，并统一到 PDF
points 坐标系（原点左下、y 向上）。本模块把 pdfplumber 原生对象转成稳定的
阅读顺序文本 + 字符级 box，字符 box 直接映射回页图坐标系（见 ``coordinates``）。

页面文本由字符对象确定性装配（按行内 x 序 + 行间垂直重叠分组的阅读顺序），
存在整列无墨栏空隙的页面按栏主序恢复跨栏阅读顺序；文本偏移与字符 box
一一对应，供定位器生成真实的 ``text_range``/``bbox``。
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
    # 字符排版字号（PDF points）；来源未提供时为 0。
    size: float = 0.0
    # 字体名是否带 bold/black/heavy 字重标记（通用字体命名约定，非文本推断）。
    bold: bool = False


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
    # 页内图像/矢量内容计数（位图 + 矩形/曲线/线段）；None 表示读取失败。
    # 供结构入口区分空白页与扫描/图形页。
    non_text_mark_count: int | None = None

    def chars_in_range(self, start: int, end: int) -> tuple[NativeChar, ...]:
        """返回文本区间 ``[start, end)`` 覆盖到的字符（含与该区间重叠的字符）。"""
        return tuple(
            c
            for c in self.chars
            if c.start < end and c.start + len(c.text) > start
        )
_BOLD_FONTNAME_TOKENS = ("bold", "black", "heavy")


def _fontname_is_bold(fontname: str) -> bool:
    """通用字体命名约定：字体名含 bold/black/heavy 字重标记即视为粗体证据。

    这是排版层面的字重信号（Adobe/OT 字重命名惯例），不依赖任何项目
    文本内容；``Heiti``、``SimSun`` 等无字重标记的字体名一律视为非粗体。
    """
    lowered = fontname.lower()
    return any(token in lowered for token in _BOLD_FONTNAME_TOKENS)


_LINE_CLUSTER_TOLERANCE = 4.0  # points；兼容同一表格行不同单元格的轻微基线偏移


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


def _canonical_chars(
    chars: list[NativeChar],
    *,
    page_width: float,
    page_height: float,
    rotation: int,
) -> list[_CanonicalChar]:
    """把可视页字符批量还原为逻辑阅读坐标。"""
    return [
        _to_canonical_char(
            char,
            page_width=page_width,
            page_height=page_height,
            rotation=rotation,
        )
        for char in chars
    ]


def _group_lines(canonical_chars: list[_CanonicalChar]) -> list[list[_CanonicalChar]]:
    """按行顶坐标聚类，避免紧行距字符框重叠时把相邻两行交织。"""
    lines: list[dict] = []
    for c in sorted(canonical_chars, key=lambda c: (-c.y1, c.x0, c.display.start)):
        candidates = [
            line
            for line in lines
            if abs(c.y1 - line["anchor_y1"]) <= _LINE_CLUSTER_TOLERANCE
        ]
        if candidates:
            line = min(candidates, key=lambda item: abs(c.y1 - item["anchor_y1"]))
            line["chars"].append(c)
            line["anchor_y1"] = sum(item.y1 for item in line["chars"]) / len(
                line["chars"]
            )
            line["y_top"] = max(line["y_top"], c.y1)
            line["y_bottom"] = min(line["y_bottom"], c.y0)
        else:
            lines.append(
                {
                    "chars": [c],
                    "anchor_y1": c.y1,
                    "y_top": c.y1,
                    "y_bottom": c.y0,
                }
            )
    lines.sort(key=lambda line: -line["y_top"])
    result = []
    for line in lines:
        line["chars"].sort(key=lambda c: (c.x0, c.display.start))
        result.append(line["chars"])
    return result


#: 栏阅读顺序恢复（纯几何判据，与任何文本内容无关）：
#: 页内文字宽度范围内，整页没有任何字符跨越的 x 空隙最小宽度（points）。
MIN_COLUMN_GAP_POINTS = 4.0
#: 单个栏带必须覆盖的页内文字总宽度下限比例；不足则按单栏处理。
MIN_COLUMN_BAND_WIDTH_FRACTION = 0.15
#: 单个栏带垂直跨度必须达到的页内文字总高度下限比例；不足则按单栏处理。
MIN_COLUMN_BAND_HEIGHT_FRACTION = 0.4
#: 接受的栏带数量上限；超过则不做栏重排（保守，避免表单/边栏误报）。
MAX_COLUMN_BANDS = 3


def _column_bands(canonical_chars: list[_CanonicalChar]) -> list[tuple[float, float]] | None:
    """检测栏间空隙（gutter），按阅读顺序返回 x 栏带；单栏时返回 None。

    判据：页内文字宽度范围 [min_x, max_x] 内存在宽度不小于
    ``MIN_COLUMN_GAP_POINTS`` 的 x 区间，整页所有字符的 x 跨度都不覆盖该
    区间；且每个栏带的宽度与垂直跨度都足够大。仅当版面确实存在整列
    无墨的空隙时才触发，常规单栏正文（词隙、缩进、表内空隙）不满足
    「整页高度无墨」条件，因此不会被误判。
    """
    if len(canonical_chars) < 20:
        return None
    extents = [(c.x0, c.x1) for c in canonical_chars if c.x1 > c.x0]
    if len(extents) < 2:
        return None
    min_x = min(x0 for x0, _ in extents)
    max_x = max(x1 for _, x1 in extents)
    span = max_x - min_x
    if span <= 0:
        return None
    merged: list[list[float]] = []
    for x0, x1 in sorted(extents):
        if merged and x0 <= merged[-1][1] + 1e-6:
            merged[-1][1] = max(merged[-1][1], x1)
        else:
            merged.append([x0, x1])
    gutters: list[tuple[float, float]] = []
    for (a0, a1), (b0, b1) in zip(merged, merged[1:]):
        if b0 - a1 >= MIN_COLUMN_GAP_POINTS:
            gutters.append((a1, b0))
    if not gutters:
        return None
    bands: list[tuple[float, float]] = []
    prev = min_x
    for g0, g1 in gutters:
        bands.append((prev, g0))
        prev = g1
    bands.append((prev, max_x))
    if len(bands) > MAX_COLUMN_BANDS:
        return None
    min_y0 = min(c.y0 for c in canonical_chars)
    max_y1 = max(c.y1 for c in canonical_chars)
    min_band_width = MIN_COLUMN_BAND_WIDTH_FRACTION * span
    min_band_height = MIN_COLUMN_BAND_HEIGHT_FRACTION * (max_y1 - min_y0)
    for band_start, band_end in bands:
        if band_end - band_start < min_band_width:
            return None
        members = [
            c
            for c in canonical_chars
            if band_start - 1.0 <= (c.x0 + c.x1) / 2 <= band_end + 1.0
        ]
        if not members:
            return None
        if max(c.y1 for c in members) - min(c.y0 for c in members) < min_band_height:
            return None
    return bands


def _split_line_at_gutters(
    line: list[_CanonicalChar], gutters: list[tuple[float, float]]
) -> list[list[_CanonicalChar]]:
    """把横跨栏间空隙的行按空隙拆分为逐栏片段。

    只在「相邻字符的水平间隙完整覆盖某个栏空隙」处拆分；空隙内还有
    字符的行（如整宽页眉）保持完整。拆分数值完全由几何决定。
    """
    segments: list[list[_CanonicalChar]] = [[line[0]]]
    for previous, current in zip(line, line[1:]):
        split = False
        for g0, g1 in gutters:
            if g0 >= previous.x1 - 1e-6 and g1 <= current.x0 + 1e-6:
                segments.append([current])
                split = True
                break
        if not split:
            segments[-1].append(current)
    return segments


def _band_index_for_x(x: float, bands: list[tuple[float, float]]) -> int:
    """返回 x 点落入（或最接近）的栏带序号；空隙内的点归属较早栏带。"""
    best = 0
    best_overlap = -1.0
    for index, (b0, b1) in enumerate(bands):
        overlap = min(x, b1) - max(x, b0)
        if overlap > best_overlap + 1e-9:
            best, best_overlap = index, overlap
    return best


def _reorder_lines_by_bands(
    lines: list[list[_CanonicalChar]], bands: list[tuple[float, float]]
) -> list[list[_CanonicalChar]]:
    """多栏阅读顺序：栏带自左向右，栏内自上而下（栏目主序）。

    全局分行会把同高度的左右栏行合并成一行；这里先按栏空隙拆回片段，
    再把每个片段按 x 中心归栏（整宽行不拆分，按中心归入单栏），最后
    按栏主序输出，得到稳定的跨栏阅读顺序。
    """
    gutters = [
        (bands[index][1], bands[index + 1][0]) for index in range(len(bands) - 1)
    ]
    per_band: list[list[list[_CanonicalChar]]] = [[] for _ in bands]
    for line in lines:
        for segment in _split_line_at_gutters(line, gutters):
            center = (min(c.x0 for c in segment) + max(c.x1 for c in segment)) / 2
            per_band[_band_index_for_x(center, bands)].append(segment)
    ordered: list[list[_CanonicalChar]] = []
    for band_lines in per_band:
        band_lines.sort(
            key=lambda segment: (
                -max(c.y1 for c in segment),
                min(c.x0 for c in segment),
            )
        )
        ordered.extend(band_lines)
    return ordered


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
            placed.append(
                NativeChar(
                    c.display.text,
                    c.display.x0,
                    c.display.y0,
                    c.display.x1,
                    c.display.y1,
                    offset,
                    size=c.display.size,
                    bold=c.display.bold,
                )
            )
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


def _extract_open_page(page, page_index: int) -> NativePage:
    """从已打开的 pdfplumber 页构建同源文本与坐标。"""
    native_chars = [
        NativeChar(
            text=c["text"],
            x0=float(c["x0"]),
            y0=float(c["y0"]),
            x1=float(c["x1"]),
            y1=float(c["y1"]),
            start=0,
            size=float(c.get("size", 0) or 0),
            bold=_fontname_is_bold(str(c.get("fontname", ""))),
        )
        for c in page.chars
    ]
    rotation = int(getattr(page, "rotation", 0) or 0) % 360
    if rotation not in {0, 90, 180, 270}:
        raise ValueError(f"PDF 页面旋转必须是 0/90/180/270 度，实际为 {rotation}")
    page_width = float(page.width)
    page_height = float(page.height)
    canonical_chars = _canonical_chars(
        native_chars,
        page_width=page_width,
        page_height=page_height,
        rotation=rotation,
    )
    ordered_lines = _group_lines(canonical_chars)
    # 有框线表格的窄列、项目符号列和复选框列会形成贯穿页面的空隙，
    # 但它们不是正文分栏。表格页保持逐行顺序，具体单元格结构由上层恢复。
    try:
        has_ruled_table = bool(page.find_tables())
    except Exception:
        has_ruled_table = False
    bands = None if has_ruled_table else _column_bands(canonical_chars)
    if bands is not None:
        ordered_lines = _reorder_lines_by_bands(ordered_lines, bands)
    text, placed = _build_text_with_offsets(ordered_lines)
    words = _build_words(ordered_lines)
    try:
        non_text_mark_count = (
            len(page.images) + len(page.rects) + len(page.curves) + len(page.lines)
        )
    except Exception:
        non_text_mark_count = None
    return NativePage(
        page_number=page_index + 1,
        text=text,
        chars=tuple(placed),
        words=tuple(words),
        page_width=page_width,
        page_height=page_height,
        rotation=rotation,
        non_text_mark_count=non_text_mark_count,
    )


def extract_native_pages(pdf_path: str | Path | bytes) -> tuple[NativePage, ...]:
    """单次打开 PDF 并提取全部页，用于真实长方案的批量入口。"""
    opener = (
        pdfplumber.open(io.BytesIO(pdf_path))
        if isinstance(pdf_path, bytes)
        else pdfplumber.open(str(pdf_path))
    )
    with opener as pdf:
        return tuple(
            _extract_open_page(page, page_index)
            for page_index, page in enumerate(pdf.pages)
        )


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
        return _extract_open_page(pdf.pages[page_index], page_index)
