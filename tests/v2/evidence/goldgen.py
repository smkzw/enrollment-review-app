"""Slice 4.0 脱敏/合成页级金标准生成器（确定性，无 PHI）。

覆盖范围（对应 PRD Slice 4.0）：
- 原生 PDF：唯一句、跨行文本、表格内否定词/数值/单位/日期；
- 扫描 PDF / 照片：无文本层的渲染页，记录真实绘制区域（页图像素坐标）；
- TXT：UTF-8 与 GB18030 解码路线；
- 多页 TIFF：逐 frame 页序；
- 重复文本定位：同页重复句必须预期降级；
- 失败页：截断 PDF、无效 .doc、损坏图片。

生成是确定性的（固定 fitz/PIL/docx 输出，剥离时间戳与随机文档 ID），
同一输入多次生成得到相同字节哈希。
"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import fitz
from docx import Document as DocxDocument
from PIL import Image

from app.domain.contracts.enums import (
    ExtractionRoute,
    LocatorPrecision,
    OcrRiskKind,
)
from app.domain.contracts.evidence import BoundingBox
from app.evidence.goldset import GoldPage, GoldSet, GoldTarget

GOLD_NAME = "slice4.0-synthetic"
A4_WIDTH = 595.0
A4_HEIGHT = 842.0
RENDER_DPI = 150
_SCALE = RENDER_DPI / 72.0
_FONT = "china-s"
_FIXED_PDF_ID = "0" * 32
# PyMuPDF may emit the trailer ID as either two hex strings or a literal string
# containing escaped random bytes.  Match the complete PDF ID array so both
# serializations receive the same deterministic replacement.
_ID_PATTERN = re.compile(rb"/ID\[(?:\\.|[^\]])*\]")
_FIXED_ZIP_DATE = (1980, 1, 1, 0, 0, 0)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _finalize_pdf(doc: fitz.Document) -> bytes:
    """导出 PDF 字节并剥离随机文档 ID 与元数据，保证确定性。"""
    doc.set_metadata({})
    data = doc.tobytes(garbage=4, deflate=True)
    fixed_id = b"/ID[<" + _FIXED_PDF_ID.encode() + b"><" + _FIXED_PDF_ID.encode() + b">]"
    data = _ID_PATTERN.sub(fixed_id, data)
    return data


def _finalize_docx(path: Path) -> None:
    """Rewrite DOCX ZIP members with stable metadata and compression settings."""
    with zipfile.ZipFile(path, "r") as source:
        members = [(info.filename, source.read(info.filename)) for info in source.infolist()]
    output = io.BytesIO()
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as target:
        for filename, payload in members:
            info = zipfile.ZipInfo(filename, date_time=_FIXED_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0
            target.writestr(info, payload)
    path.write_bytes(output.getvalue())


@dataclass(frozen=True)
class _DrawnPage:
    """一页绘制内容：文本行 + 每行绘制矩形（PDF points）与像素矩形。"""

    text_lines: tuple[tuple[float, float, str], ...]
    pixel_bboxes: tuple[tuple[str, BoundingBox], ...]


def _draw_page(
    page: fitz.Page,
    lines: list[tuple[float, float, str]],
    *,
    fontsize: int = 14,
) -> _DrawnPage:
    """在 fitz 页面上按 ``(x, y_top, text)`` 绘制文本并记录真实区域。"""
    pixel_boxes: list[tuple[str, BoundingBox]] = []
    for x, y, text in lines:
        page.insert_text((x, y), text, fontname=_FONT, fontsize=fontsize)
        rects = page.search_for(text)
        for rect in rects:
            pixel_boxes.append((text, _point_to_pixel(rect, A4_HEIGHT)))
    return _DrawnPage(text_lines=tuple(lines), pixel_bboxes=tuple(pixel_boxes))


def _point_to_pixel(rect, page_height: float) -> BoundingBox:
    """把 fitz 搜索矩形（页面坐标原点在左上、y 向下，与页图像素同向）换算为页图像素。

    fitz 页面坐标已是 y-down（与渲染页图像素同向），无需翻转；pdfminer/pdfplumber
    的原生字符坐标才是 y-up，由 ``coordinates.pdf_points_to_image_pixels`` 负责翻转。
    """
    return BoundingBox(
        x0=round(rect.x0 * _SCALE, 3),
        y0=round(rect.y0 * _SCALE, 3),
        x1=round(rect.x1 * _SCALE, 3),
        y1=round(rect.y1 * _SCALE, 3),
    )


def _pixmap_for(page: fitz.Page) -> fitz.Pixmap:
    return page.get_pixmap(
        matrix=fitz.Matrix(_SCALE, 0, 0, _SCALE, 0, 0), alpha=False
    )


def _pixmap_rgb_bytes(pix: fitz.Pixmap) -> tuple[bytes, int, int]:
    if pix.n == 1:  # gray -> RGB
        samples = b"".join(bytes((v, v, v)) for v in pix.samples)
        return samples, pix.width, pix.height
    return pix.samples, pix.width, pix.height


def _native_targets(page: fitz.Page, targets: list[GoldTarget]) -> tuple[GoldTarget, ...]:
    """为原生 PDF 目标补充真实绘制区域（页图像素），供坐标 spike 校验。"""
    result: list[GoldTarget] = []
    for target in targets:
        rects = page.search_for(target.text)
        pixel_bbox: BoundingBox | None = None
        if len(rects) == 1:
            pixel_bbox = _point_to_pixel(rects[0], A4_HEIGHT)
        result.append(
            GoldTarget(
                text=target.text,
                expected_precision=target.expected_precision,
                allow_exact=target.allow_exact,
                expected_pixel_bbox=pixel_bbox,
            )
        )
    return tuple(result)


def _build_native_pdf(root: Path) -> list[GoldPage]:
    doc = fitz.open()
    pages: list[GoldPage] = []

    p1 = doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
    _draw_page(
        p1,
        [
            (72, 90, "受试者张三，男，56岁，于2026年3月14日签署知情同意书。"),
            (72, 120, "既往史：否认高血压病史，血肌酐 76.1 umol/L。"),
            (72, 140, "否认糖尿病病史，空腹血糖 5.6 mmol/L。"),
        ],
    )
    p1_text = "受试者张三，男，56岁，于2026年3月14日签署知情同意书。\n既往史：否认高血压病史，血肌酐 76.1 umol/L。\n否认糖尿病病史，空腹血糖 5.6 mmol/L。"
    pages.append(
        GoldPage(
            gold_page_id="native-01-p1",
            file_ref="native-01.pdf",
            page_number=1,
            expected_text=p1_text,
            route=ExtractionRoute.NATIVE_PDF_TEXT,
            targets=_native_targets(
                p1,
                [
                    GoldTarget("否认高血压病史"),
                    GoldTarget("76.1"),
                    GoldTarget("2026年3月14日"),
                ],
            ),
            expected_risk_kinds=(
                OcrRiskKind.NEGATION_POLARITY,
                OcrRiskKind.NUMERIC_VALUE,
                OcrRiskKind.DECIMAL_POINT,
                OcrRiskKind.UNIT,
                OcrRiskKind.DATE,
            ),
        )
    )

    p2 = doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
    _draw_page(
        p2,
        [
            (72, 90, "再次确认：受试者已签署知情同意书。"),
            (72, 120, "再次确认：受试者已签署知情同意书。"),
            (72, 160, "生命体征：体温 36.5 摄氏度。"),
        ],
    )
    p2_text = (
        "再次确认：受试者已签署知情同意书。\n再次确认：受试者已签署知情同意书。\n生命体征：体温 36.5 摄氏度。"
    )
    pages.append(
        GoldPage(
            gold_page_id="native-01-p2",
            file_ref="native-01.pdf",
            page_number=2,
            expected_text=p2_text,
            route=ExtractionRoute.NATIVE_PDF_TEXT,
            targets=_native_targets(
                p2,
                [
                    # 同页重复文本：必须降级，不得生成伪精确高亮。
                    GoldTarget(
                        "已签署知情同意书",
                        expected_precision=LocatorPrecision.PAGE_EXCERPT,
                        allow_exact=False,
                    ),
                    GoldTarget("36.5"),
                ],
            ),
            expected_risk_kinds=(
                OcrRiskKind.NEGATION_POLARITY,
                OcrRiskKind.NUMERIC_VALUE,
                OcrRiskKind.DECIMAL_POINT,
            ),
        )
    )

    p3 = doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
    _draw_page(
        p3,
        [
            (72, 90, "检查结果："),
            (72, 120, "ALT\t32.5\tU/L\t2026-03-14"),
            (72, 140, "AST\t28.0\tU/L\t2026-03-14"),
            (72, 160, "尿素氮\t5.2\tmmol/L\t2026-03-14"),
        ],
    )
    p3_text = (
        "检查结果：\nALT\t32.5\tU/L\t2026-03-14\nAST\t28.0\tU/L\t2026-03-14\n尿素氮\t5.2\tmmol/L\t2026-03-14"
    )
    pages.append(
        GoldPage(
            gold_page_id="native-01-p3",
            file_ref="native-01.pdf",
            page_number=3,
            expected_text=p3_text,
            route=ExtractionRoute.NATIVE_PDF_TEXT,
            targets=_native_targets(
                p3,
                [
                    GoldTarget("32.5"),
                    # 表格内同值日期重复 3 次：必须降级。
                    GoldTarget(
                        "2026-03-14",
                        expected_precision=LocatorPrecision.PAGE_EXCERPT,
                        allow_exact=False,
                    ),
                ],
            ),
            expected_risk_kinds=(
                OcrRiskKind.NUMERIC_VALUE,
                OcrRiskKind.DECIMAL_POINT,
                OcrRiskKind.UNIT,
                OcrRiskKind.DATE,
            ),
        )
    )

    (root / "native-01.pdf").write_bytes(_finalize_pdf(doc))
    return pages


def _build_scanned_and_photo(root: Path) -> list[GoldPage]:
    pages: list[GoldPage] = []

    # 扫描 PDF 与照片共用同一绘制内容。
    src = fitz.open()
    page = src.new_page(width=A4_WIDTH, height=A4_HEIGHT)
    drawn = _draw_page(
        page,
        [
            (72, 320, "胸部X线检查未见异常。"),
            (72, 350, "检查日期：2026-04-02"),
        ],
    )
    pix = _pixmap_for(page)
    samples, width, height = _pixmap_rgb_bytes(pix)
    src.close()

    # 扫描 PDF：把渲染图作为整页图片，无文本层。
    scanned = fitz.open()
    spage = scanned.new_page(width=A4_WIDTH, height=A4_HEIGHT)
    spage.insert_image(spage.rect, pixmap=pix)
    (root / "scanned-01.pdf").write_bytes(_finalize_pdf(scanned))

    scanned_text = "胸部X线检查未见异常。\n检查日期：2026-04-02"
    scanned_targets = _pixel_targets(drawn.pixel_bboxes)
    pages.append(
        GoldPage(
            gold_page_id="scanned-01-p1",
            file_ref="scanned-01.pdf",
            page_number=1,
            expected_text=scanned_text,
            expected_readback_exact=False,
            route=ExtractionRoute.VISION_OCR,
            targets=scanned_targets,
            expected_risk_kinds=(OcrRiskKind.NEGATION_POLARITY, OcrRiskKind.DATE),
            expected_pixel_size=(width, height),
        )
    )

    # 照片：JPG。
    Image.frombytes("RGB", (width, height), samples).save(
        root / "photo-01.jpg", format="JPEG", quality=90
    )
    pages.append(
        GoldPage(
            gold_page_id="photo-01-p1",
            file_ref="photo-01.jpg",
            page_number=1,
            expected_text=scanned_text,
            expected_readback_exact=False,
            route=ExtractionRoute.VISION_OCR,
            targets=scanned_targets,
            expected_risk_kinds=(OcrRiskKind.NEGATION_POLARITY, OcrRiskKind.DATE),
            expected_pixel_size=(width, height),
        )
    )
    return pages


def _pixel_targets(pixel_bboxes: tuple[tuple[str, BoundingBox], ...]) -> tuple[GoldTarget, ...]:
    """把绘制区域的像素 bbox 作为布局候选评估目标。"""
    return tuple(
        GoldTarget(text, expected_precision=LocatorPrecision.BBOX, expected_pixel_bbox=bbox)
        for text, bbox in pixel_bboxes
    )


def _build_tiff(root: Path) -> list[GoldPage]:
    frames: list[tuple[str, str]] = [
        ("multi-frame-1", "第一帧：尿常规 隐血 阴性。"),
        ("multi-frame-2", "第二帧：血常规 WBC 6.8×10^9/L。"),
    ]
    images: list[Image.Image] = []
    pages: list[GoldPage] = []
    for index, (frame_name, text) in enumerate(frames, start=1):
        src = fitz.open()
        page = src.new_page(width=A4_WIDTH, height=A4_HEIGHT)
        drawn = _draw_page(page, [(72, 320, text)])
        pix = _pixmap_for(page)
        samples, width, height = _pixmap_rgb_bytes(pix)
        src.close()
        image = Image.frombytes("RGB", (width, height), samples)
        images.append(image)
        pages.append(
            GoldPage(
                gold_page_id=f"multi-01-frame{index}",
                file_ref="multi-01.tiff",
                page_number=index,
                expected_text=text,
                expected_readback_exact=False,
                route=ExtractionRoute.VISION_OCR,
                targets=_pixel_targets(drawn.pixel_bboxes),
                expected_risk_kinds=(
                    (OcrRiskKind.NEGATION_POLARITY,)
                    if "阴性" in text
                    else (OcrRiskKind.NUMERIC_VALUE, OcrRiskKind.DECIMAL_POINT)
                ),
                expected_pixel_size=(width, height),
            )
        )
    images[0].save(
        root / "multi-01.tiff",
        format="TIFF",
        save_all=True,
        append_images=images[1:],
        compression="raw",
    )
    return pages


def _build_txt_files(root: Path) -> list[GoldPage]:
    pages: list[GoldPage] = []
    (root / "txt-01.txt").write_text(
        "受试者补充资料说明\n2026-05-01\n否认既往手术史\n", encoding="utf-8"
    )
    pages.append(
        GoldPage(
            gold_page_id="txt-01",
            file_ref="txt-01.txt",
            page_number=1,
            expected_text="受试者补充资料说明\n2026-05-01\n否认既往手术史\n",
            route=None,
            targets=(GoldTarget("否认既往手术史", expected_precision=LocatorPrecision.TEXT_RANGE),),
            expected_risk_kinds=(OcrRiskKind.NEGATION_POLARITY, OcrRiskKind.DATE),
        )
    )

    (root / "txt-gb18030.txt").write_bytes(
        "受试者甲：已接种疫苗，2026年6月30日。\n".encode("gb18030")
    )
    pages.append(
        GoldPage(
            gold_page_id="txt-gb18030",
            file_ref="txt-gb18030.txt",
            page_number=1,
            expected_text="受试者甲：已接种疫苗，2026年6月30日。\n",
            route=None,
            targets=(
                GoldTarget("已接种疫苗", expected_precision=LocatorPrecision.TEXT_RANGE),
                GoldTarget("2026年6月30日", expected_precision=LocatorPrecision.TEXT_RANGE),
            ),
            expected_risk_kinds=(OcrRiskKind.NEGATION_POLARITY, OcrRiskKind.DATE),
        )
    )

    clean_pages: list[tuple[str, str, str]] = [
        (
            "risk-clean-01",
            "risk-clean-01.txt",
            "受试者于筛选期完成知情同意流程，随后由研究护士采集病史。资料已归档于研究文件夹。\n",
        ),
        (
            "risk-clean-02",
            "risk-clean-02.txt",
            "本页记录研究者对方案理解的备注，未包含任何检查结果。后续访视安排另行通知。\n",
        ),
        (
            "risk-clean-03",
            "risk-clean-03.txt",
            "中心名称与研究编号见封面。此页留白说明见附录。\n",
        ),
        (
            "risk-clean-04",
            "risk-clean-04.txt",
            "本页记录文件接收和归档流程，不包含检查结果或治疗判断。\n",
        ),
        (
            "risk-clean-05",
            "risk-clean-05.txt",
            "研究团队已完成资料清点，原件按照内部流程归档。\n",
        ),
        (
            "risk-clean-06",
            "risk-clean-06.txt",
            "本页为研究者签阅说明，未记录受试者测量结果。\n",
        ),
        (
            "risk-clean-07",
            "risk-clean-07.txt",
            "文件传递记录已由授权人员复核，具体内容见对应原件。\n",
        ),
        (
            "risk-clean-08",
            "risk-clean-08.txt",
            "本页说明资料保存位置，不包含日期、数值或单位信息。\n",
        ),
        (
            "risk-clean-09",
            "risk-clean-09.txt",
            "研究护士完成资料接收登记，未对临床结果作出解释。\n",
        ),
        (
            "risk-clean-10",
            "risk-clean-10.txt",
            "此页仅用于记录文件交接状态，未包含极性或实验室结果。\n",
        ),
        (
            "risk-clean-11",
            "risk-clean-11.txt",
            "资料目录已由研究中心保存，后续查阅应回到原始文件。\n",
        ),
        (
            "risk-clean-12",
            "risk-clean-12.txt",
            "本页为空白说明页，不承载受试者事实或研究结论。\n",
        ),
        (
            "risk-clean-13",
            "risk-clean-13.txt",
            "归档人员完成交接登记，未改变任何原始资料内容。\n",
        ),
    ]
    for page_id, file_name, text in clean_pages:
        (root / file_name).write_text(text, encoding="utf-8")
        pages.append(
            GoldPage(
                gold_page_id=page_id,
                file_ref=file_name,
                page_number=1,
                expected_text=text,
                route=None,
            )
        )
    return pages


def _build_docx(root: Path) -> list[GoldPage]:
    doc = DocxDocument()
    # 固定核心属性，避免时间戳破坏确定性。
    fixed = __import__("datetime").datetime(2026, 1, 1, 0, 0, 0)
    doc.core_properties.created = fixed
    doc.core_properties.modified = fixed
    doc.core_properties.last_printed = fixed
    doc.add_paragraph("补充资料说明：受试者于2026年7月2日完成访视。")
    table = doc.add_table(rows=2, cols=3)
    cells = [
        ("指标", "结果", "单位"),
        ("血红蛋白", "128", "g/L"),
    ]
    for row_index, row in enumerate(cells):
        for col_index, value in enumerate(row):
            table.cell(row_index, col_index).text = value
    doc.save(str(root / "docx-01.docx"))
    _finalize_docx(root / "docx-01.docx")

    pages = [
        GoldPage(
            gold_page_id="docx-01-p1",
            file_ref="docx-01.docx",
            page_number=1,
            expected_text=(
                "补充资料说明：受试者于2026年7月2日完成访视。\n指标\t结果\t单位\n血红蛋白\t128\tg/L"
            ),
            expected_readback_exact=False,  # 需受控 LibreOffice 渲染后评估（Slice 4.3）
            route=ExtractionRoute.RENDERED_PDF_TEXT,
            targets=(
                GoldTarget("血红蛋白", expected_precision=LocatorPrecision.PAGE_EXCERPT, allow_exact=False),
                GoldTarget("128", expected_precision=LocatorPrecision.PAGE_EXCERPT, allow_exact=False),
            ),
            expected_risk_kinds=(OcrRiskKind.NUMERIC_VALUE, OcrRiskKind.UNIT, OcrRiskKind.DATE),
        )
    ]
    return pages


def _build_failure_files(root: Path) -> list[GoldPage]:
    native_pdf = (root / "native-01.pdf").read_bytes()
    (root / "corrupt-01.pdf").write_bytes(native_pdf[:600])
    (root / "unsupported-01.doc").write_bytes(b"This is not a valid OLE compound document.\n")
    (root / "bad-image-01.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"not really png data" * 8)
    return [
        GoldPage(
            gold_page_id="corrupt-01",
            file_ref="corrupt-01.pdf",
            page_number=1,
            expected_failure_reason="PDF 文件被截断，无法解析页面结构",
        ),
        GoldPage(
            gold_page_id="unsupported-01",
            file_ref="unsupported-01.doc",
            page_number=1,
            expected_failure_reason="无效 .doc（非 OLE 复合文档），解码失败",
        ),
        GoldPage(
            gold_page_id="bad-image-01",
            file_ref="bad-image-01.png",
            page_number=1,
            expected_failure_reason="图片文件损坏，无法解码",
        ),
    ]


def build_gold_set(root: Path) -> GoldSet:
    """在 ``root`` 下生成确定性金标准文件并返回 GoldSet。"""
    root.mkdir(parents=True, exist_ok=True)
    pages: list[GoldPage] = []
    pages.extend(_build_native_pdf(root))
    pages.extend(_build_scanned_and_photo(root))
    pages.extend(_build_tiff(root))
    pages.extend(_build_txt_files(root))
    pages.extend(_build_docx(root))
    pages.extend(_build_failure_files(root))

    sha_by_file: dict[str, str] = {}
    for file_ref in sorted({page.file_ref for page in pages}):
        path = root / file_ref
        if not path.is_file():
            raise FileNotFoundError(f"金标准页面引用的生成物不存在: {path}")
        sha_by_file[file_ref] = _sha256(path.read_bytes())
    return GoldSet(
        name=GOLD_NAME,
        pages=tuple(pages),
        source_sha256_by_file=sha_by_file,
    )
