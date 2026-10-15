"""逐格式确定性分页：把来源文件切成真实的有序页清单（Slice 4.3，worker_02）。

分页只回答「这份文件到底有几页、每一页是什么」：页面身份由内容字节与
``(page_number, original_frame)`` 决定，文件名与 mtime 永不参与。

- ``page_source_document`` 对 PDF / 普通图片 / 多帧 TIFF / TXT / DOCX / legacy DOC
  分别产出有序 ``PageInput`` 清单；整文件解码失败或页数未知时产出**显式失败页**
  （``status=FAILED`` + 真实原因），绝不伪造「单页成功占位」来掩盖未知页数；
- DOCX / legacy DOC 通过可注入的 ``DocConverter``（生产路径为 LibreOffice 无头
  转换）先转 PDF 再分页；转换不可用/失败同样是显式失败页；
- ``PageInput.input_sha256`` 是**稳定的渲染/解码输入身份**：真实 PDF / 图片 /
  历史 TXT 为来源内容哈希；新 TXT 绑定源哈希、分页版本、字符范围与页文字；
  DOCX/DOC 为 ``源内容哈希 + 媒体类别 + 转换器版本`` 的
  派生哈希（不是转换产物 PDF 的字节哈希，避免 LibreOffice 元数据噪声破坏
  同内容同配置的页身份与 OCR 缓存复用，见 P4-R03）。

本模块是纯确定性函数（fitz / PIL / 文本解码），不做 OCR、不写存储；
渲染与页产物生成见 ``render`` / ``page_processor``。
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

import fitz
from PIL import Image

from app.domain.contracts.enums import PageArtifactStatus
from app.domain.publication import canonical_hash
from app.evidence.text import TextDecodeError, decode_text_bytes
from app.evidence.render import RenderError, paginate_text_content

#: 分页/解码身份版本：任一决定页数或页身份的解码行为变化必须提升该版本。
PAGING_VERSION = "slice4.3/paging/v2"

_TIFF_MAGICS = (b"II*\x00", b"MM\x00*")
#: OLE 复合文档魔数（legacy .doc）；缺失即非有效 .doc。
_OLE_COMPOUND_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

#: 可识别的来源格式类别（与上传预览 ``detect_file_format`` 的 kind 对齐）。
SUPPORTED_MEDIA_KINDS = frozenset({"pdf", "image", "text", "docx", "doc"})


class PagingError(ValueError):
    """分页阶段确定性错误（未知格式类别等）。"""


class DocConversionError(ValueError):
    """DOCX / legacy DOC 无法转换为可渲染 PDF。

    ``message`` 必须是**已净化的稳定中文领域措辞**（可进入失败页原因）；
    退出码 / stderr / 内部异常细节放在 ``technical_detail``，归 worker_03
    尝试/任务技术记录，绝不进入领域失败文本。
    """

    def __init__(self, message: str, *, technical_detail: str | None = None) -> None:
        super().__init__(message)
        self.technical_detail = technical_detail


class DocConverter(Protocol):
    """DOCX / legacy DOC -> 可渲染 PDF 字节的转换器（生产路径 LibreOffice）。

    ``converter_version`` 是稳定转换器/版本身份：同内容同转换器版本必须得到
    同一派生页输入身份（参与 ``PageInput.input_sha256``），转换器版本变化必须
    改变页身份与 OCR 缓存键（P4-R03）。
    """

    converter_version: str

    def convert_to_pdf(self, content: bytes, *, suffix: str) -> bytes: ...


def content_sha256(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def is_tiff(content: bytes) -> bool:
    """按魔数判断 TIFF（II*\\x00 小端 / MM\\x00* 大端），不依赖扩展名。"""
    return content[:4] in _TIFF_MAGICS


def derived_doc_input_sha256(
    *, source_sha256: str, media_kind: str, converter_version: str
) -> str:
    """DOCX/DOC 页的稳定渲染/解码输入身份。

    由源内容哈希 + 媒体类别 + 转换器版本派生，**不**使用转换产物 PDF 的字节
    哈希：LibreOffice 会在 PDF 中写入可变文档 ID 等元数据，同内容同配置的
    两次转换字节可能不同，但页身份与 OCR 缓存必须一致（P4-R03）。
    """
    return canonical_hash(
        {
            "page_input": "doc_like_page_input/v1",
            "source_sha256": source_sha256,
            "media_kind": media_kind,
            "converter_version": converter_version,
        }
    )


@dataclass(frozen=True)
class PageInput:
    """一页的确定性输入身份。

    ``render_source`` 是渲染/解码该页的字节输入：PDF 页/图片为原文件字节，
    新 TXT 为该页原文的 UTF-8 字节，original_frame 保存解码后字符范围；
    DOCX/DOC 转换后的页为转换得到的 PDF 字节（与来源字节不同）。
    ``input_sha256`` 是**稳定渲染/解码输入身份**（真实格式为来源内容哈希，
    DOCX/DOC 为派生哈希），不是转换产物字节哈希。整文件失败页
    ``status=FAILED`` 且无 ``render_source``/``input_sha256``。

    ``technical_detail`` 是**非用户可见**的内部诊断：转换/解码异常细节供
    worker_03 写入尝试/任务技术记录，绝不进入 ``failure_reason`` 或用户可见中文。
    """

    page_number: int
    media_kind: str  # pdf | image | tiff | text | docx | doc
    original_frame: str | None
    render_source: bytes | None
    input_sha256: str | None
    status: PageArtifactStatus
    failure_reason: str | None
    technical_detail: str | None = None

    @property
    def expects_failure(self) -> bool:
        return self.status == PageArtifactStatus.FAILED


@dataclass(frozen=True)
class PagePlan:
    """一份来源文件的有序页计划；失败页与成功页可共存（兄弟页真相保留）。"""

    source_sha256: str
    media_kind: str
    pages: tuple[PageInput, ...]

    @property
    def page_total(self) -> int:
        return len(self.pages)


def _failed_page(
    page_number: int,
    media_kind: str,
    reason: str,
    *,
    technical_detail: str | None = None,
) -> PageInput:
    return PageInput(
        page_number=page_number,
        media_kind=media_kind,
        original_frame=None,
        render_source=None,
        input_sha256=None,
        status=PageArtifactStatus.FAILED,
        failure_reason=reason,
        technical_detail=technical_detail,
    )


def _success_pages(
    *,
    media_kind: str,
    count: int,
    render_source: bytes,
    input_sha256: str,
    frame_names: tuple[str | None, ...] | None = None,
) -> tuple[PageInput, ...]:
    """为 1..count 页生成成功页输入；``frame_names`` 用于 TIFF 逐帧身份。"""
    pages: list[PageInput] = []
    for page_number in range(1, count + 1):
        frame = frame_names[page_number - 1] if frame_names is not None else None
        pages.append(
            PageInput(
                page_number=page_number,
                media_kind=media_kind,
                original_frame=frame,
                render_source=render_source,
                input_sha256=input_sha256,
                status=PageArtifactStatus.SUCCEEDED,
                failure_reason=None,
            )
        )
    return tuple(pages)


def _page_pdf(
    pdf_bytes: bytes, *, media_kind: str, input_sha256: str
) -> tuple[PageInput, ...]:
    """打开 PDF 字节并产出真实页序；整文件损坏时产出显式失败页。

    ``input_sha256`` 由调用方给出稳定渲染/解码输入身份：真实 PDF 为来源内容
    哈希，DOCX/DOC 转换产物为派生身份（非转换字节哈希）。
    """
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            count = doc.page_count
    except Exception as exc:  # noqa: BLE001 - 任何解析失败都代表页数未知，必须显式失败
        # 页数未知：显式失败页，绝不伪造单页成功占位；异常细节只作内部诊断。
        return (
            _failed_page(
                1,
                media_kind,
                "PDF 文件被截断，无法解析页面结构",
                technical_detail=f"{type(exc).__name__}: {exc}",
            ),
        )
    return _success_pages(
        media_kind=media_kind,
        count=count,
        render_source=pdf_bytes,
        input_sha256=input_sha256,
    )


def _page_image(content: bytes, *, source_sha256: str) -> tuple[PageInput, ...]:
    """普通图片或 TIFF：单图一页，多帧 TIFF 逐帧一页。"""
    try:
        with Image.open(io.BytesIO(content)) as image:
            frame_count = int(getattr(image, "n_frames", 1))
    except Exception as exc:  # noqa: BLE001 - 图片解码失败一律显式失败页
        return (
            _failed_page(
                1,
                "image",
                "图片文件损坏，无法解码",
                technical_detail=f"{type(exc).__name__}: {exc}",
            ),
        )
    if frame_count > 1:
        frame_names = tuple(f"frame-{index}" for index in range(1, frame_count + 1))
        return _success_pages(
            media_kind="tiff",
            count=frame_count,
            render_source=content,
            input_sha256=source_sha256,
            frame_names=frame_names,
        )
    return _success_pages(
        media_kind="image",
        count=1,
        render_source=content,
        input_sha256=source_sha256,
    )


def _page_text(content: bytes, *, source_sha256: str, paging_version: str) -> tuple[PageInput, ...]:
    """TXT：按显示宽度分页，保存解码后原文的字符范围。"""
    try:
        decoded = decode_text_bytes(content)
    except TextDecodeError as exc:
        # 稳定中文领域措辞，不泄露内部解码错误细节；细节只作内部诊断。
        return (
            _failed_page(
                1,
                "text",
                "文件无法解码为文本，内容编码不受支持",
                technical_detail=f"{type(exc).__name__}: {exc}",
            ),
        )
    if paging_version == "slice4.3/paging/v1":
        return _success_pages(
            media_kind="text", count=1, render_source=content, input_sha256=source_sha256,
        )
    try:
        chunks = paginate_text_content(decoded.text)
    except (RenderError, OSError) as exc:
        return (_failed_page(
            1, "text", "文本排版暂不可用，尚未生成完整页面",
            technical_detail=f"{type(exc).__name__}: {exc}",
        ),)
    return tuple(
        PageInput(
            page_number=index, media_kind="text",
            original_frame=f"text-chars-{start}-{end}",
            render_source=chunk.encode("utf-8"),
            input_sha256=canonical_hash({
                "source_sha256": source_sha256, "paging_version": paging_version,
                "start": start, "end": end, "text": chunk,
            }),
            status=PageArtifactStatus.SUCCEEDED, failure_reason=None,
        )
        for index, (start, end, chunk) in enumerate(chunks, 1)
    )


def _page_doc_like(
    content: bytes,
    *,
    media_kind: str,
    source_sha256: str,
    doc_converter: DocConverter | None,
) -> tuple[PageInput, ...]:
    """DOCX / legacy DOC：先转 PDF 再按 PDF 页序分页；转换失败显式失败页。

    页输入身份由 ``derived_doc_input_sha256`` 决定（源哈希 + 类别 + 转换器版本），
    与转换产物字节无关，保证同内容同配置复用同一页身份与 OCR 缓存。
    """
    if media_kind == "doc" and not content.startswith(_OLE_COMPOUND_MAGIC):
        return (
            _failed_page(
                1,
                media_kind,
                "无效的 .doc 文档文件，无法解码",
            ),
        )
    if doc_converter is None:
        return (
            _failed_page(
                1,
                media_kind,
                f"{media_kind.upper()} 转换不可用，无法生成可处理页面",
            ),
        )
    try:
        pdf_bytes = doc_converter.convert_to_pdf(content, suffix=f".{media_kind}")
    except DocConversionError as exc:
        # 转换器异常消息本身已净化；技术细节归 worker_03，绝不进入用户可见文本。
        return (
            _failed_page(
                1,
                media_kind,
                f"{media_kind.upper()} 转换失败，无法生成可处理页面",
                technical_detail=exc.technical_detail,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - 转换器实现异常统一按转换失败上报
        return (
            _failed_page(
                1,
                media_kind,
                f"{media_kind.upper()} 转换失败，无法生成可处理页面",
                technical_detail=f"{type(exc).__name__}: {exc}",
            ),
        )
    converter_version = getattr(doc_converter, "converter_version", "unknown")
    input_sha256 = derived_doc_input_sha256(
        source_sha256=source_sha256,
        media_kind=media_kind,
        converter_version=converter_version,
    )
    return _page_pdf(pdf_bytes, media_kind=media_kind, input_sha256=input_sha256)


def page_source_document(
    *,
    content: bytes,
    media_kind: str,
    source_sha256: str | None = None,
    doc_converter: DocConverter | None = None,
    paging_version: str = PAGING_VERSION,
) -> PagePlan:
    """把来源文件切成真实有序页清单；未知类别或空内容产出显式失败页。

    ``media_kind`` 取值与上传预览格式探测一致：``pdf``/``image``/``text``/
    ``docx``/``doc``；``image`` 会按魔数进一步区分多帧 TIFF。整文件失败时返回
    单条显式失败页（页数未知不得伪装成功占位）。
    """
    if paging_version not in {"slice4.3/paging/v1", PAGING_VERSION}:
        raise PagingError("不支持的资料分页版本")
    digest = source_sha256 or content_sha256(content)
    if media_kind not in SUPPORTED_MEDIA_KINDS:
        return PagePlan(
            source_sha256=digest,
            media_kind=media_kind,
            pages=(
                _failed_page(
                    1,
                    media_kind,
                    f"不支持的来源格式类别 {media_kind!r}，无法建立页清单",
                ),
            ),
        )
    if not content:
        return PagePlan(
            source_sha256=digest,
            media_kind=media_kind,
            pages=(_failed_page(1, media_kind, "文件内容为空，无法建立页清单"),),
        )
    if media_kind == "pdf":
        pages = _page_pdf(content, media_kind="pdf", input_sha256=digest)
    elif media_kind == "image":
        pages = _page_image(content, source_sha256=digest)
    elif media_kind == "text":
        pages = _page_text(content, source_sha256=digest, paging_version=paging_version)
    else:  # docx | doc
        pages = _page_doc_like(
            content,
            media_kind=media_kind,
            source_sha256=digest,
            doc_converter=doc_converter,
        )
    return PagePlan(source_sha256=digest, media_kind=media_kind, pages=pages)
