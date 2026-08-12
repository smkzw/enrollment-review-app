"""File classifier for clinical trial enrollment review pipeline.

Classifies uploaded documents into categories based on file type and content,
and sorts them in a logical review order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import fitz  # PyMuPDF

# Logical sort order for document categories
_CATEGORY_ORDER: dict[str, int] = {
    "邮件": 0,
    "筛选期病历": 1,
    "检验检查单": 2,
    "既往病历": 3,
    "量表": 4,
    "照片": 5,
    "其他": 99,
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}
PDF_EXTENSION = ".pdf"
DOCX_EXTENSIONS = {".docx", ".doc"}


@dataclass
class ClassifiedFile:
    """Result of classifying a single file."""

    path: Path
    file_type: str  # 'pdf_native' | 'pdf_scan' | 'image' | 'unknown'
    category: str  # e.g. '邮件', '病历', '量表', '其他'
    pages: int = 0
    text_chars: int = 0
    producer: str = ""
    note: str = ""
    sort_key: int = field(default=99, repr=False)


def _classify_category(name: str) -> str:
    """Determine document category from filename keywords."""
    lower = name.lower()
    if "邮件" in name or "email" in lower:
        return "邮件"
    if any(kw in name for kw in ("筛选", "入组")):
        return "筛选期病历"
    if any(kw in name for kw in ("检验", "检查", "化验", "血", "尿", "实验室")):
        return "检验检查单"
    if any(kw in name for kw in ("既往", "病史", "诊断", "出院")):
        return "既往病历"
    if any(kw in name for kw in ("量表", "PASI", "pasi", "PGA", "pga", "BSA", "bsa", "评分")):
        return "量表"
    if any(kw in name for kw in ("照片", "photo", "image", "皮损")):
        return "照片"
    if "病历" in name:
        return "筛选期病历"
    return "其他"


def _classify_pdf(path: Path) -> tuple[str, int, int, str]:
    """Classify a PDF file.

    Returns (file_type, pages, text_chars, producer).
    """
    try:
        doc = fitz.open(path)
    except Exception:
        return "pdf_scan", 0, 0, ""

    pages = len(doc)
    text_chars = 0
    producer = ""
    try:
        metadata = doc.metadata or {}
        producer = (metadata.get("producer") or "").strip()
        for page in doc:
            text_chars += len(page.get_text())
    except Exception:
        pass
    finally:
        doc.close()

    # Heuristic: CamScanner or similar → likely scan
    is_camscanner = "camscanner" in producer.lower() if producer else False

    if text_chars > 100:
        file_type = "pdf_native"
        note = f"PDF native, {text_chars} chars extractable, {pages} pages"
    else:
        file_type = "pdf_scan"
        note = f"PDF scan ({text_chars} chars), {pages} pages"
        if is_camscanner:
            note += f" (producer: {producer})"

    return file_type, pages, text_chars, producer


def classify_file(path: Path) -> ClassifiedFile:
    """Classify a single file and return a ClassifiedFile."""
    suffix = path.suffix.lower()
    name = path.name
    category = _classify_category(name)
    sort_key = _CATEGORY_ORDER.get(category, 99)

    if suffix == PDF_EXTENSION:
        file_type, pages, text_chars, producer = _classify_pdf(path)
        if text_chars <= 100:
            note = f"扫描件PDF ({text_chars}字可提取), {pages}页"
        else:
            note = f"原生PDF ({text_chars}字可提取), {pages}页"
        if producer:
            note += f", 制作工具: {producer}"
        return ClassifiedFile(
            path=path,
            file_type=file_type,
            category=category,
            pages=pages,
            text_chars=text_chars,
            producer=producer,
            note=note,
            sort_key=sort_key,
        )

    if suffix in IMAGE_EXTENSIONS:
        return ClassifiedFile(
            path=path,
            file_type="image",
            category=category,
            pages=1,
            text_chars=0,
            producer="",
            note=f"图片文件 ({suffix})",
            sort_key=sort_key,
        )

    if suffix in DOCX_EXTENSIONS:
        # Check if docx has text content
        try:
            from docx import Document
            doc = Document(str(path))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            text_chars = len(text)
            if text_chars > 100:
                file_type = "docx_native"
                note = f"DOCX文档 ({text_chars}字可提取)"
            else:
                file_type = "docx_scan"
                note = f"DOCX文档 (可能含图片/扫描件, {text_chars}字)"
        except Exception:
            file_type = "docx_scan"
            text_chars = 0
            note = f"DOCX文档 (读取失败)"
        
        return ClassifiedFile(
            path=path,
            file_type=file_type,
            category=category,
            pages=1,
            text_chars=text_chars,
            producer="",
            note=note,
            sort_key=sort_key,
        )

    return ClassifiedFile(
        path=path,
        file_type="unknown",
        category=category,
        pages=0,
        text_chars=0,
        producer="",
        note=f"未知文件类型 ({suffix})",
        sort_key=sort_key,
    )


def classify_directory(directory: Path) -> List[ClassifiedFile]:
    """Classify all files in a directory, sorted by logical review order."""
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    results: list[ClassifiedFile] = []
    for f in sorted(directory.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            results.append(classify_file(f))

    # Stable sort by category order, then filename within category
    results.sort(key=lambda c: (c.sort_key, c.path.name))
    return results
