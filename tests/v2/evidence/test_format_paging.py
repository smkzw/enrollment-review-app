"""逐格式确定性分页测试（worker_02）。

用 Slice 4.0 合成金标准验证：原生/扫描 PDF、普通图片、多帧 TIFF、TXT、
DOCX、legacy DOC 产出真实有序页清单；整文件解码失败/未知页数产出显式失败页，
绝不伪造单页成功占位；页身份只由内容字节与页码/帧身份决定。
"""
from __future__ import annotations

import hashlib
import re

import fitz

from app.domain.contracts.enums import PageArtifactStatus
from app.evidence.paging import (
    DocConversionError,
    PageInput,
    derived_doc_input_sha256,
    page_source_document,
)

_sha = lambda b: hashlib.sha256(b).hexdigest()
_ID_PATTERN = re.compile(rb"/ID\[(?:\\.|[^\]])*\]")
_FIXED_ID = b"/ID[<" + b"0" * 32 + b"><" + b"0" * 32 + b">]"


def _reason(page: PageInput) -> str:
    assert page.failure_reason is not None
    return page.failure_reason


def _make_pdf(text: str = "PAGE TEXT\n") -> bytes:
    doc = fitz.open()  # type: ignore[attr-defined] - fitz stub 未覆盖 open/new_page
    page = doc.new_page(width=595, height=842)  # type: ignore[attr-defined]
    page.insert_text((72, 100), text, fontname="china-s", fontsize=14)
    doc.set_metadata({})  # type: ignore[attr-defined]
    data = doc.tobytes(garbage=4, deflate=True)  # type: ignore[arg-type]
    doc.close()
    return _ID_PATTERN.sub(_FIXED_ID, data)


class FakeDocConverter:
    """确定性 fake 转换器：DOCX/DOC -> 固定内容 PDF 字节，暴露稳定版本身份。"""

    def __init__(self, text: str = "DOC CONTENT\n", *, version: str = "fake-converter/v1") -> None:
        self.text = text
        self.converter_version = version

    def convert_to_pdf(self, content: bytes, *, suffix: str) -> bytes:
        if suffix == ".doc" and not content.startswith(b"\xd0\xcf\x11\xe0"):
            raise DocConversionError("无效的 .doc 文档文件，无法解码")
        return _make_pdf(self.text)


def _plan(content: bytes, kind: str, converter=None, sha: str | None = None):
    return page_source_document(
        content=content,
        media_kind=kind,
        source_sha256=sha or _sha(content),
        doc_converter=converter,
    )


def test_native_pdf_three_ordered_pages(gold_root, gold_set):
    content = (gold_root / "native-01.pdf").read_bytes()
    plan = _plan(content, "pdf")
    assert plan.media_kind == "pdf"
    assert plan.page_total == 3
    pages = plan.pages
    assert [p.page_number for p in pages] == [1, 2, 3]
    for page in pages:
        assert page.status == PageArtifactStatus.SUCCEEDED
        assert page.media_kind == "pdf"
        assert page.input_sha256 == _sha(content)
        assert page.render_source == content
        assert page.original_frame is None


def test_scanned_pdf_single_page(gold_root, gold_set):
    content = (gold_root / "scanned-01.pdf").read_bytes()
    plan = _plan(content, "pdf")
    assert plan.page_total == 1
    assert plan.pages[0].page_number == 1


def test_photo_image_single_page(gold_root, gold_set):
    content = (gold_root / "photo-01.jpg").read_bytes()
    plan = _plan(content, "image")
    assert plan.page_total == 1
    assert plan.pages[0].media_kind == "image"


def test_multi_frame_tiff_two_pages_with_frame_identity(gold_root, gold_set):
    content = (gold_root / "multi-01.tiff").read_bytes()
    plan = _plan(content, "image")
    assert plan.page_total == 2
    assert [p.original_frame for p in plan.pages] == ["frame-1", "frame-2"]
    for page in plan.pages:
        assert page.media_kind == "tiff"
        assert page.input_sha256 == _sha(content)


def test_txt_utf8_and_gb18030_single_page(gold_root, gold_set):
    for file_ref in ("txt-01.txt", "txt-gb18030.txt"):
        content = (gold_root / file_ref).read_bytes()
        plan = _plan(content, "text")
        assert plan.page_total == 1
        assert plan.pages[0].status == PageArtifactStatus.SUCCEEDED
        assert plan.pages[0].media_kind == "text"


def test_docx_via_converter_produces_ordered_page(gold_root, gold_set):
    content = (gold_root / "docx-01.docx").read_bytes()
    converter = FakeDocConverter("DOCX page\n", version="fake-converter/v1")
    plan = _plan(content, "docx", converter=converter)
    assert plan.page_total == 1
    page = plan.pages[0]
    assert page.status == PageArtifactStatus.SUCCEEDED
    assert page.media_kind == "docx"
    # 转换产物的渲染源是转换得到的 PDF 字节（与来源不同）。
    assert page.render_source != content
    # 页输入身份由 源哈希+类别+转换器版本 派生，不是转换字节哈希（P4-R03）。
    expected = derived_doc_input_sha256(
        source_sha256=_sha(content),
        media_kind="docx",
        converter_version="fake-converter/v1",
    )
    assert page.input_sha256 == expected
    assert page.input_sha256 != _sha(content)
    assert page.input_sha256 != _sha(page.render_source)


def test_docx_same_content_same_converter_identical_identity(gold_root, gold_set):
    """同内容同转换器版本 -> 同一页输入身份（即使转换产物 PDF 字节不同）。"""
    content = (gold_root / "docx-01.docx").read_bytes()

    class ByteDifferentConverter:
        """两次转换产出字节不同的 PDF（不同 trailer ID），可见内容一致。"""

        converter_version = "fake-converter/v1"

        def convert_to_pdf(self, content: bytes, *, suffix: str) -> bytes:
            if not hasattr(self, "_tick"):
                self._tick = 0
            self._tick += 1
            doc = fitz.open()  # type: ignore[attr-defined] - fitz stub
            page = doc.new_page(width=595, height=842)  # type: ignore[attr-defined]
            page.insert_text((72, 100), "DOCX page\n", fontname="china-s", fontsize=14)
            doc.set_metadata({})  # type: ignore[attr-defined]
            data = doc.tobytes(garbage=4, deflate=True)  # type: ignore[arg-type]
            doc.close()
            unique = format(self._tick, "032x")
            fixed_id = b"/ID[<" + unique.encode() + b"><" + unique.encode() + b">]"
            return _ID_PATTERN.sub(fixed_id, data)

    converter = ByteDifferentConverter()
    first = _plan(content, "docx", converter=converter)
    second = _plan(content, "docx", converter=converter)
    # 转换字节不同（LibreOffice 元数据噪声模拟），但页输入身份相同。
    assert first.pages[0].render_source != second.pages[0].render_source
    assert first.pages[0].input_sha256 == second.pages[0].input_sha256
    assert first.pages[0].input_sha256 == derived_doc_input_sha256(
        source_sha256=_sha(content), media_kind="docx", converter_version="fake-converter/v1"
    )


def test_docx_converter_version_change_changes_identity(gold_root, gold_set):
    """转换器版本变化 -> 页输入身份变化（P4-R03 决定性输入）。"""
    content = (gold_root / "docx-01.docx").read_bytes()
    v1 = _plan(content, "docx", converter=FakeDocConverter(version="fake-converter/v1"))
    v2 = _plan(content, "docx", converter=FakeDocConverter(version="fake-converter/v2"))
    assert v1.pages[0].input_sha256 != v2.pages[0].input_sha256
    # 同一版本 -> 同一身份（稳定复用）。
    again = _plan(content, "docx", converter=FakeDocConverter(version="fake-converter/v1"))
    assert again.pages[0].input_sha256 == v1.pages[0].input_sha256


def test_docx_without_converter_is_explicit_failed_page(gold_root, gold_set):
    content = (gold_root / "docx-01.docx").read_bytes()
    plan = _plan(content, "docx", converter=None)
    assert plan.page_total == 1
    page = plan.pages[0]
    assert page.status == PageArtifactStatus.FAILED
    # 用户可见失败文本：稳定中文工作措辞，无工程术语。
    assert _reason(page) == "DOCX 转换不可用，无法生成可处理页面"
    for term in ("转换器", "适配器", "OCR", "text-only", "LibreOffice"):
        assert term not in _reason(page)
    assert page.render_source is None


def test_corrupt_pdf_is_explicit_failed_page_not_fake_success(gold_root, gold_set):
    """页数未知时不得伪造单页成功占位；必须显式失败并说明原因。"""
    content = (gold_root / "corrupt-01.pdf").read_bytes()
    plan = _plan(content, "pdf")
    assert plan.page_total == 1
    page = plan.pages[0]
    assert page.status == PageArtifactStatus.FAILED
    assert _reason(page)
    assert page.render_source is None
    assert page.input_sha256 is None


def test_invalid_doc_is_explicit_failed_page(gold_root, gold_set):
    content = (gold_root / "unsupported-01.doc").read_bytes()
    plan = _plan(content, "doc", converter=FakeDocConverter())
    assert plan.page_total == 1
    page = plan.pages[0]
    assert page.status == PageArtifactStatus.FAILED
    assert "无效的 .doc" in _reason(page)


def test_invalid_doc_without_converter_still_fails_on_ole(gold_root, gold_set):
    content = (gold_root / "unsupported-01.doc").read_bytes()
    plan = _plan(content, "doc", converter=None)
    assert plan.pages[0].status == PageArtifactStatus.FAILED
    assert "无效的 .doc" in _reason(plan.pages[0])


def test_bad_image_is_explicit_failed_page(gold_root, gold_set):
    content = (gold_root / "bad-image-01.png").read_bytes()
    plan = _plan(content, "image")
    assert plan.page_total == 1
    page = plan.pages[0]
    assert page.status == PageArtifactStatus.FAILED
    assert "图片文件损坏" in _reason(page)


def test_empty_content_explicit_failed_page():
    plan = _plan(b"", "pdf")
    assert plan.pages[0].status == PageArtifactStatus.FAILED
    assert "内容为空" in _reason(plan.pages[0])


def test_unsupported_kind_explicit_failed_page():
    plan = _plan(b"PK\x03\x04 garbage", "archive")
    assert plan.pages[0].status == PageArtifactStatus.FAILED
    assert "不支持的来源格式" in _reason(plan.pages[0])


def test_conversion_failure_keeps_technical_detail_internal(
    gold_root, gold_set
):
    """转换失败：用户可见原因干净；内部技术诊断保留（供 worker_03，非用户可见）。"""
    content = (gold_root / "docx-01.docx").read_bytes()

    class SecretRaisingConverter:
        converter_version = "fake/v1"

        def convert_to_pdf(self, content: bytes, *, suffix: str) -> bytes:
            raise RuntimeError("Bearer secret-token-ABC")

    plan = _plan(content, "docx", converter=SecretRaisingConverter())
    page = plan.pages[0]
    assert page.status == PageArtifactStatus.FAILED
    assert _reason(page) == "DOCX 转换失败，无法生成可处理页面"
    for secret in ("RuntimeError", "secret-token-ABC", "Bearer"):
        assert secret not in _reason(page)
    # 内部诊断仍然可用（异常类名 + 消息），供 worker_03 技术记录。
    assert page.technical_detail is not None
    assert "RuntimeError" in page.technical_detail
    assert "secret-token-ABC" in page.technical_detail


def test_page_identity_never_uses_file_name_or_mtime():
    """同一内容字节 -> 同一页输入身份，文件名/mtime 不参与。"""
    a = _make_pdf("IDENTITY TEXT\n")
    b = _make_pdf("IDENTITY TEXT\n")
    assert a == b
    plan_a = _plan(a, "pdf")
    plan_b = _plan(b, "pdf", sha=_sha(a))
    assert plan_a.pages[0].input_sha256 == plan_b.pages[0].input_sha256
    assert plan_a.pages[0].page_number == plan_b.pages[0].page_number


def test_multi_page_pdf_preserves_all_sibling_pages(gold_root, gold_set):
    """原生 PDF 三页全部保留为成功页，兄弟页真相不丢失。"""
    content = (gold_root / "native-01.pdf").read_bytes()
    plan = _plan(content, "pdf")
    assert plan.page_total == 3
    assert all(p.status == PageArtifactStatus.SUCCEEDED for p in plan.pages)
