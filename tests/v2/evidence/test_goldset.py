"""金标准生成测试：确定性、覆盖范围与失败页。"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pdfplumber
import pytest
from docx import Document as DocxDocument
from docx.opc.exceptions import PackageNotFoundError
from pdfminer.pdfdocument import PDFSyntaxError
from pdfplumber.utils.exceptions import PdfminerException
from PIL import Image, UnidentifiedImageError

from app.evidence import decode_text_bytes
from tests.v2.evidence.goldgen import build_gold_set

REQUIRED_CASES = {
    "native-01.pdf": "原生 PDF（唯一/跨行/表格/重复文本）",
    "scanned-01.pdf": "扫描 PDF（无文本层）",
    "photo-01.jpg": "照片",
    "docx-01.docx": "DOCX",
    "unsupported-01.doc": "无效 .doc 失败页",
    "txt-01.txt": "UTF-8 TXT",
    "txt-gb18030.txt": "GB18030 TXT",
    "multi-01.tiff": "多页 TIFF",
    "corrupt-01.pdf": "截断 PDF 失败页",
    "bad-image-01.png": "损坏图片失败页",
}


def test_gold_set_covers_all_required_cases(gold_set) -> None:
    for file_ref, description in REQUIRED_CASES.items():
        assert file_ref in gold_set.source_sha256_by_file, f"缺少 {description}: {file_ref}"
    file_refs = {p.file_ref for p in gold_set.pages}
    for file_ref in REQUIRED_CASES:
        assert file_ref in file_refs, f"金标准页面未覆盖 {file_ref}"
    # 失败文件必须记录期望失败原因，且不混入成功页语义。
    failure_pages = {p.file_ref: p for p in gold_set.pages if p.expects_failure}
    assert {"corrupt-01.pdf", "unsupported-01.doc", "bad-image-01.png"} <= set(failure_pages)
    for page in failure_pages.values():
        assert page.expected_text is None
        assert not page.targets
        assert not page.expected_risk_kinds


def test_gold_set_generation_is_deterministic(tmp_path) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    set_a = build_gold_set(root_a)
    set_b = build_gold_set(root_b)
    assert set_a.source_sha256_by_file == set_b.source_sha256_by_file
    assert set_a.pages == set_b.pages

    # PyMuPDF can choose the trailer-ID serialization once per interpreter.
    # Fresh processes are required here; two calls in one process can hide the
    # random literal-string ID that used to make scanned-01.pdf drift.
    script = (
        "from pathlib import Path; import sys; "
        "from tests.v2.evidence.goldgen import build_gold_set; "
        "build_gold_set(Path(sys.argv[1]))"
    )
    process_roots = [tmp_path / "process-a", tmp_path / "process-b"]
    for root in process_roots:
        subprocess.run(
            [sys.executable, "-c", script, str(root)],
            check=True,
            cwd=Path(__file__).resolve().parents[3],
        )
    for file_ref in set_a.source_sha256_by_file:
        bytes_a = (process_roots[0] / file_ref).read_bytes()
        bytes_b = (process_roots[1] / file_ref).read_bytes()
        assert hashlib.sha256(bytes_a).digest() == hashlib.sha256(bytes_b).digest(), file_ref


def test_generated_pdfs_use_canonical_trailer_id(gold_root) -> None:
    fixed_id = b"0" * 32
    for file_ref in ("native-01.pdf", "scanned-01.pdf"):
        payload = (gold_root / file_ref).read_bytes()
        assert b"/ID[<" + fixed_id + b"><" + fixed_id + b">]" in payload
        assert b"/ID[(" not in payload


def test_gold_pages_have_stable_risk_and_locator_contract(gold_set) -> None:
    for page in gold_set.pages:
        assert page.gold_page_id
        assert page.page_number >= 1
        # 重复文本目标必须声明不允许精确匹配。
        for target in page.targets:
            if not target.allow_exact:
                assert target.expected_precision.value in {"page_excerpt", "page_only"}


def test_multi_page_tiff_frame_order(gold_root, gold_set) -> None:
    frames = gold_set.pages_for("multi-01.tiff")
    assert [p.page_number for p in frames] == [1, 2]
    assert "阴性" in frames[0].expected_text
    assert "6.8" in frames[1].expected_text
    with Image.open(gold_root / "multi-01.tiff") as img:
        assert getattr(img, "n_frames", 1) == 2


def test_failure_files_fail_to_open(gold_root) -> None:
    with pytest.raises((PdfminerException, PDFSyntaxError)):
        pdfplumber.open(str(gold_root / "corrupt-01.pdf"))
    with pytest.raises(PackageNotFoundError):
        DocxDocument(str(gold_root / "unsupported-01.doc"))
    # PIL Image.open 对损坏 PNG 在识别阶段即抛 OSError。
    with pytest.raises((UnidentifiedImageError, OSError)):
        Image.open(gold_root / "bad-image-01.png")


def test_gb18030_txt_decodes_via_fixed_order(gold_root) -> None:
    payload = (gold_root / "txt-gb18030.txt").read_bytes()
    decoded = decode_text_bytes(payload)
    assert decoded.encoding == "gb18030"
    assert "已接种疫苗" in decoded.text
    # UTF-8 直接失败，不会误判编码。
    assert "受试者甲" in decoded.text
