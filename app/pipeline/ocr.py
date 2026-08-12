"""
OCR engine for clinical trial document processing — v2 accelerated.

Three-layer optimization:
  Layer 1: Pre-processing — native text extraction before VLM, skip OCR for text-rich pages
  Layer 2: Concurrent — parallel file processing + parallel page OCR
  Layer 3: Multi-model — MiniMax for large files, oMLX for small files, both in parallel
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

import fitz  # PyMuPDF

from app.config import OCR_DPI, OCR_MAX_CONCURRENT, OCR_BACKEND, OCR_NATIVE_HIGH_PRECISION_REVIEW
from app.llm.client import call_vision_ocr

logger = logging.getLogger(__name__)
_GLOBAL_VLM_SEMAPHORES: dict[int, tuple[int, asyncio.Semaphore]] = {}

# ---------------------------------------------------------------------------
# OCR prompt specialised for Chinese clinical documents
# ---------------------------------------------------------------------------
OCR_PROMPT = """\
请提取图片中的所有文字内容，保持原始排版格式。\
如遇手写文字用 [手写:...] 标注，无法辨认的标注 [手写:不可辨]。\
如遇涂抹/遮盖用 [涂抹] 标注。\
签名处标注 [签名:xxx] 或 [签名:不可辨]。\
"""

OCR_POLARITY_REVIEW_PROMPT = OCR_PROMPT + """\
本页可能包含入排审核关键极性信息，请特别核对并逐字保留：否认/确认、有/无、未见/可见、阴性/阳性、正常/异常、未使用/已使用、未接受/已接受、未接种/已接种，以及任何“近X天/周/月/半衰期、随机前、基线前、给药前”的时间窗。\
不要把“否认”识别成“确认”，不要省略“不、无、未、否认”等否定词。\
"""

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx", ".doc"}
TEXT_EXTENSIONS = {".txt"}

# Threshold: if native text extraction yields this many chars per page, skip VLM OCR
NATIVE_TEXT_THRESHOLD = 80  # chars per page


def text_requires_high_precision_review(text: str) -> bool:
    """Return true when native text carries high-risk polarity/window facts."""
    value = str(text or "")
    if not value.strip():
        return False
    polarity = r"(否认|确认|未见|可见|有|无|阴性|阳性|正常|异常|未使用|已使用|未接受|已接受|未接种|已接种)"
    clinical_trigger = (
        r"(饮酒|吸烟|感染|急性疾病|合并用药|伴随用药|禁止用药|禁用|洗脱|"
        r"免疫抑制剂|免疫治疗|生物制剂|疫苗|梅毒|TPPA|TRUST|RPR|HIV|HBV|HCV|"
        r"ALT|AST|胆红素|GGT|尿糖|潜血|妊娠|避孕)"
    )
    window = r"(近\d+|随机前|基线前|给药前|半衰期|周|月|天)"
    if re.search(polarity + r".{0,40}" + clinical_trigger, value, re.IGNORECASE):
        return True
    if re.search(clinical_trigger + r".{0,40}" + polarity, value, re.IGNORECASE):
        return True
    if re.search(polarity + r".{0,48}" + window, value, re.IGNORECASE):
        return True
    if re.search(window + r".{0,48}" + polarity, value, re.IGNORECASE):
        return True
    return False


def global_vlm_semaphore() -> asyncio.Semaphore:
    """Return one OCR VLM semaphore per event loop.

    Subject-level batch parallelism can run multiple `/process` requests at the
    same time. A per-request semaphore would multiply the configured limit, so
    all concurrent OCR work in this server process must share one loop-local cap.
    """
    loop = asyncio.get_running_loop()
    key = id(loop)
    configured = OCR_MAX_CONCURRENT
    cached = _GLOBAL_VLM_SEMAPHORES.get(key)
    if cached is None or cached[0] != configured:
        cached = (configured, asyncio.Semaphore(configured))
        _GLOBAL_VLM_SEMAPHORES[key] = cached
    return cached[1]


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------
def _cache_dir(doc_name: Path, cache_root: Path) -> Path:
    return cache_root / doc_name.stem if isinstance(doc_name, Path) else cache_root / doc_name


def _cache_hit(md_cache: Path, source: Path) -> bool:
    if not md_cache.exists():
        return False
    return md_cache.stat().st_mtime >= source.stat().st_mtime


# ---------------------------------------------------------------------------
# PDF type detection
# ---------------------------------------------------------------------------
def _is_native_pdf(pdf_path: Path) -> bool:
    """Quick check: does the PDF have extractable text?"""
    try:
        doc = fitz.open(str(pdf_path))
        total_chars = sum(len(doc[i].get_text()) for i in range(min(3, len(doc))))
        doc.close()
        return total_chars > 100
    except Exception:
        return False


def _page_has_text_from_cache(page_texts: dict, page_idx: int) -> Tuple[bool, str, int]:
    """Check if a page has enough native text from pre-extracted cache.

    Returns (has_enough_text, extracted_text, char_count)
    """
    cached = page_texts.get(page_idx, "")
    char_count = len(cached.strip())
    return char_count >= NATIVE_TEXT_THRESHOLD, cached.strip(), char_count


def _dedupe_preserving_order(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        key = item.strip()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        result.append(item)
    return result


def detect_ocr_hallucination(text: str) -> tuple[bool, str, str]:
    """Detect and reduce repetitive OCR/VLM hallucination before caching."""
    raw = str(text or "")
    if not raw.strip():
        return False, raw, ""

    lines = raw.splitlines()
    non_empty = [line.strip() for line in lines if line.strip()]
    warnings: list[str] = []
    cleaned = raw

    if len(non_empty) >= 10:
        unique_lines = set(non_empty)
        repetition_ratio = 1 - (len(unique_lines) / len(non_empty))
        dominant_count = max((non_empty.count(line) for line in unique_lines), default=0)
        if repetition_ratio >= 0.5 or dominant_count >= 8:
            cleaned_lines = _dedupe_preserving_order(lines)
            cleaned = "\n".join(cleaned_lines)
            warnings.append(f"行重复率{repetition_ratio:.0%}")

    segments = [seg.strip() for seg in re.split(r"[。！？!?；;\n]+", cleaned) if len(seg.strip()) >= 4]
    if len(segments) >= 12:
        unique_segments = set(segments)
        segment_repetition = 1 - (len(unique_segments) / len(segments))
        dominant_segment_count = max((segments.count(seg) for seg in unique_segments), default=0)
        if segment_repetition >= 0.45 or dominant_segment_count >= 8:
            seen = set()
            deduped_segments = []
            for seg in segments:
                if seg in seen:
                    continue
                seen.add(seg)
                deduped_segments.append(seg)
            cleaned = "\n".join(deduped_segments)
            warnings.append(f"句段重复率{segment_repetition:.0%}")

    if warnings:
        warning = f"OCR质量警告：检测到疑似重复幻觉（{'，'.join(warnings)}），已去重；请必要时复核原始页图。"
        return True, f"<!-- ocr-quality-warning: hallucination-deduplicated -->\n[{warning}]\n\n{cleaned}", warning

    if len(cleaned) > 8000:
        warning = f"OCR质量警告：单页OCR结果{len(cleaned)}字符，超过常规阈值；请必要时复核原始页图。"
        return True, f"<!-- ocr-quality-warning: unusually-long-page -->\n[{warning}]\n\n{cleaned[:8000]}", warning

    return False, cleaned, ""


# ---------------------------------------------------------------------------
# Page rendering
# ---------------------------------------------------------------------------
def _render_page_to_jpeg(doc_path: Path, page_idx: int, dpi: int = OCR_DPI) -> bytes:
    """Render a single PDF page to JPEG bytes at the given DPI.
    
    Limits max dimension to 4000px and uses JPEG quality 80 for faster OCR.
    """
    doc = fitz.open(str(doc_path))
    page = doc[page_idx]
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    
    # Limit max dimension to 4000px to reduce file size
    max_dim = 4000
    if pix.width > max_dim or pix.height > max_dim:
        scale = max_dim / max(pix.width, pix.height)
        mat2 = fitz.Matrix(zoom * scale, zoom * scale)
        pix = page.get_pixmap(matrix=mat2, alpha=False)
    
    jpeg_bytes = pix.tobytes("jpeg", jpg_quality=92)
    doc.close()
    return jpeg_bytes


def _image_to_b64(image_bytes: bytes) -> str:
    """Return base64-encoded string for image bytes."""
    return base64.b64encode(image_bytes).decode("ascii")


# ---------------------------------------------------------------------------
# Core OCR per page — with Layer 1 pre-processing
# ---------------------------------------------------------------------------
async def _ocr_page_smart(
    file_path: Path,
    page_idx: int,
    doc_name: str,
    page_num: int,
    cache_root: Path,
    semaphore: asyncio.Semaphore,
    total_pages: int = 1,
    page_texts: dict = None,
) -> Tuple[int, str, str]:
    """Smart OCR for a single page: try native text first, fall back to VLM.
    
    Returns (page_num, markdown_text, method) where method is 'native' or 'vlm'.
    """
    cdir = _cache_dir(Path(doc_name), cache_root)
    cdir.mkdir(parents=True, exist_ok=True)  # Ensure cache dir exists
    md_cache = cdir / f"p{page_num}.md"
    jpg_cache = cdir / f"p{page_num}.jpg"

    # Cache hit? (skip empty files)
    if md_cache.exists() and md_cache.stat().st_size > 10:
        text = md_cache.read_text(encoding="utf-8")
        method = "native" if "<!-- native" in text else "vlm"
        return page_num, text, f"cache({method})"

    # Layer 1: Try native text extraction first (from pre-extracted cache)
    if page_texts is None:
        page_texts = {}
    has_text, native_text, char_count = _page_has_text_from_cache(page_texts, page_idx)
    
    if has_text:
        if OCR_NATIVE_HIGH_PRECISION_REVIEW and text_requires_high_precision_review(native_text):
            try:
                jpeg_bytes = await asyncio.to_thread(_render_page_to_jpeg, file_path, page_idx, OCR_DPI)
                jpg_cache.write_bytes(jpeg_bytes)
                img_b64 = _image_to_b64(jpeg_bytes)
                async with semaphore:
                    logger.info("VLM polarity review: %s p%d (pages=%d)", doc_name, page_num, total_pages)
                    vlm_text = await call_vision_ocr(img_b64, OCR_POLARITY_REVIEW_PROMPT, total_pages=total_pages)
                flagged, vlm_text, warning = detect_ocr_hallucination(vlm_text)
                if flagged:
                    logger.warning("OCR quality warning: %s p%d: %s", doc_name, page_num, warning)
                markdown = (
                    "<!-- native-pdf-extraction + vlm-polarity-review -->\n"
                    "[OCR质量提示：本页含入排关键极性词或时间窗，已执行图像OCR复核。若原生PDF文本与图像OCR在“否认/确认、有/无、阴性/阳性”等极性词不一致，请复核原始页图，不能仅凭单一路径判定。]\n\n"
                    "## 原生PDF文本\n"
                    f"{native_text}\n\n"
                    "## 图像OCR复核\n"
                    f"{vlm_text}"
                )
                md_cache.write_text(markdown, encoding="utf-8")
                logger.info("Native text polarity-reviewed: %s p%d (%d chars)", doc_name, page_num, char_count)
                return page_num, markdown, "native+vlm"
            except Exception as exc:
                logger.warning("VLM polarity review failed for %s p%d, using native text: %s", doc_name, page_num, exc)
                markdown = (
                    "<!-- native-pdf-extraction; vlm-polarity-review-failed -->\n"
                    "[OCR质量提示：本页含入排关键极性词或时间窗，但图像OCR复核失败；请必要时复核原始页图。]\n\n"
                    f"{native_text}"
                )
                md_cache.write_text(markdown, encoding="utf-8")
                return page_num, markdown, "native"
        # Page has enough native text — skip VLM OCR
        markdown = f"<!-- native-pdf-extraction -->\n\n{native_text}"
        md_cache.write_text(markdown, encoding="utf-8")
        logger.info("Native text OK: %s p%d (%d chars)", doc_name, page_num, char_count)
        return page_num, markdown, "native"

    # Layer 1 failed: need VLM OCR
    jpeg_bytes = await asyncio.to_thread(_render_page_to_jpeg, file_path, page_idx, OCR_DPI)
    jpg_cache.write_bytes(jpeg_bytes)
    img_b64 = _image_to_b64(jpeg_bytes)

    async with semaphore:
        logger.info("VLM OCR: %s p%d (pages=%d)", doc_name, page_num, total_pages)
        markdown = await call_vision_ocr(img_b64, OCR_POLARITY_REVIEW_PROMPT, total_pages=total_pages)
        
        # If VLM result is short or likely handwriting, try Baidu OCR as enhancement
        from app.llm.client import check_baidu_ocr, baidu_ocr_handwriting
        if await check_baidu_ocr() and len(markdown) < 200:
            try:
                baidu_text = await baidu_ocr_handwriting(img_b64)
                if baidu_text and len(baidu_text) > len(markdown):
                    markdown = f"<!-- baidu-ocr-enhanced -->\n\n{baidu_text}"
                    logger.info("Baidu OCR enhanced: %s p%d (%d chars)", doc_name, page_num, len(baidu_text))
            except Exception as e:
                logger.warning("Baidu OCR failed: %s", e)

    flagged, markdown, warning = detect_ocr_hallucination(markdown)
    if flagged:
        logger.warning("OCR quality warning: %s p%d: %s", doc_name, page_num, warning)
    md_cache.write_text(markdown, encoding="utf-8")
    return page_num, markdown, "vlm"


async def _ocr_image_bytes(
    image_bytes: bytes,
    doc_name: str,
    page_num: int,
    cache_root: Path,
    semaphore: asyncio.Semaphore,
    total_pages: int = 1,
) -> Tuple[int, str, str]:
    """OCR a pre-rendered image (page), with caching."""
    cdir = _cache_dir(Path(doc_name), cache_root)
    cdir.mkdir(parents=True, exist_ok=True)  # Ensure cache dir exists
    md_cache = cdir / f"p{page_num}.md"
    jpg_cache = cdir / f"p{page_num}.jpg"

    if md_cache.exists() and md_cache.stat().st_size > 10:
        return page_num, md_cache.read_text(encoding="utf-8"), "cache(vlm)"

    jpg_cache.write_bytes(image_bytes)
    img_b64 = _image_to_b64(image_bytes)

    async with semaphore:
        markdown = await call_vision_ocr(img_b64, OCR_POLARITY_REVIEW_PROMPT, total_pages=total_pages)

    flagged, markdown, warning = detect_ocr_hallucination(markdown)
    if flagged:
        logger.warning("OCR quality warning: %s p%d: %s", doc_name, page_num, warning)
    md_cache.write_text(markdown, encoding="utf-8")
    return page_num, markdown, "vlm"


async def _ocr_native_page(
    pdf_path: Path,
    page_idx: int,
    doc_name: str,
    page_num: int,
    cache_root: Path,
) -> Tuple[int, str, str]:
    """Extract text from a native PDF page (no LLM call)."""
    cdir = _cache_dir(Path(doc_name), cache_root)
    md_cache = cdir / f"p{page_num}.md"

    if _cache_hit(md_cache, pdf_path):
        return page_num, md_cache.read_text(encoding="utf-8"), "cache(native)"

    doc = fitz.open(str(pdf_path))
    text = doc[page_idx].get_text()
    doc.close()

    markdown = f"<!-- native-pdf-extraction -->\n\n{text}"
    md_cache.write_text(markdown, encoding="utf-8")
    return page_num, markdown, "native"


# ---------------------------------------------------------------------------
# Layer 3: Multi-model routing
# ---------------------------------------------------------------------------
def _choose_backend(file_path: Path) -> str | None:
    """Choose OCR backend based on file characteristics.
    
    DEPRECATED: Runtime backend selection now happens via call_vision_ocr()
    which uses configuredu OCR_BACKEND. This function is kept for future
    per-document routing logic.
    
    - Large PDFs (>=5 pages): use MiniMax (faster for batch)
    - Small files (<5 pages): use oMLX (local, no API cost)
    - If OCR_BACKEND is not 'auto', use the configured backend
    """
    if OCR_BACKEND != "auto":
        return OCR_BACKEND
    
    try:
        if file_path.suffix.lower() in PDF_EXTENSIONS:
            doc = fitz.open(str(file_path))
            num_pages = len(doc)
            doc.close()
            # Large files → MiniMax, small files → oMLX
            return "minimax" if num_pages >= 5 else "omlx"
    except Exception:
        pass
    return "auto"  # let call_vision_ocr decide


# ---------------------------------------------------------------------------
# Result wrapper for method tracking
# ---------------------------------------------------------------------------
class _OCRResult(list):
    """List subclass that carries raw results for method stats."""
    def __init__(self, items, raw=None):
        super().__init__(items)
        self.raw = raw or []


# ---------------------------------------------------------------------------
# Public API — Layer 2: Concurrent file processing
# ---------------------------------------------------------------------------
async def ocr_document(
    file_path: str | Path,
    cache_root: str | Path,
    doc_name: Optional[str] = None,
    vlm_semaphore: Optional[asyncio.Semaphore] = None,
) -> List[Tuple[int, str]]:
    """
    OCR an entire document (PDF or image) with smart pre-processing.
    
    Layer 1: Native text extraction before VLM
    Layer 3: Backend selection based on file size
    """
    file_path = Path(file_path)
    cache_root = Path(cache_root)
    if doc_name is None:
        doc_name = file_path.stem

    ext = file_path.suffix.lower()
    semaphore = vlm_semaphore or global_vlm_semaphore()
    backend = _choose_backend(file_path)

    # ------------------------------------------------------------------
    # Case 1: PDF
    # ------------------------------------------------------------------
    if ext in PDF_EXTENSIONS:
        doc = fitz.open(str(file_path))
        num_pages = len(doc)

        # Pre-extract all native text once (avoids per-page open/close, ~30x speedup)
        page_texts = {}
        try:
            for i in range(num_pages):
                page_texts[i] = doc[i].get_text()
        except Exception:
            pass
        doc.close()

        logger.info("OCR %s: %d pages", file_path.name, num_pages)

        # Process all pages concurrently with smart routing (pre-extracted native text)
        async def _process_page(idx: int):
            return await _ocr_page_smart(
                file_path, idx, doc_name, idx + 1, cache_root, semaphore,
                total_pages=num_pages, page_texts=page_texts
            )

        tasks = [_process_page(i) for i in range(num_pages)]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out failed pages, log errors
        valid_results = []
        for i, r in enumerate(raw_results):
            if isinstance(r, Exception):
                logger.error("OCR page %d of %s failed: %s", i + 1, file_path.name, r)
                continue
            valid_results.append(r)
        
        # Sort by page number
        raw_results = sorted(valid_results, key=lambda x: x[0])
        # Return (page_num, text) tuples, with raw_results attached via wrapper
        results = [(r[0], r[1]) for r in raw_results]
        return _OCRResult(results, raw_results)

    # ------------------------------------------------------------------
    # Case 2: Standalone image
    # ------------------------------------------------------------------
    if ext in IMAGE_EXTENSIONS:
        cdir = _cache_dir(Path(doc_name), cache_root)
        md_cache = cdir / "p1.md"

        if _cache_hit(md_cache, file_path):
            return [(1, md_cache.read_text(encoding="utf-8"))]

        image_bytes = file_path.read_bytes()
        page_num, md, method = await _ocr_image_bytes(
            image_bytes, doc_name, 1, cache_root, semaphore, total_pages=1
        )
        return [(page_num, md)]

    # ------------------------------------------------------------------
    # Case 3: DOCX/DOC
    # ------------------------------------------------------------------
    if ext in DOCX_EXTENSIONS:
        cdir = _cache_dir(Path(doc_name), cache_root)
        cdir.mkdir(parents=True, exist_ok=True)
        md_cache = cdir / "p1.md"

        if _cache_hit(md_cache, file_path):
            return [(1, md_cache.read_text(encoding="utf-8"))]

        # Extract text from docx
        try:
            from docx import Document
            doc = Document(str(file_path))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            markdown = f"<!-- docx-extraction -->\n\n{text}"
            md_cache.write_text(markdown, encoding="utf-8")
            logger.info("DOCX text extracted: %s (%d chars)", file_path.name, len(text))
            return [(1, markdown)]
        except ImportError:
            raise ValueError("python-docx not installed. Run: pip install python-docx")
        except Exception as e:
            raise ValueError(f"Failed to parse DOCX: {e}")

    # ------------------------------------------------------------------
    # Case 4: Plain text
    # ------------------------------------------------------------------
    if ext in TEXT_EXTENSIONS:
        cdir = _cache_dir(Path(doc_name), cache_root)
        cdir.mkdir(parents=True, exist_ok=True)
        md_cache = cdir / "p1.md"

        if _cache_hit(md_cache, file_path):
            return [(1, md_cache.read_text(encoding="utf-8"))]

        text = file_path.read_text(encoding="utf-8", errors="replace")
        markdown = f"<!-- text-file-extraction -->\n\n{text}"
        md_cache.write_text(markdown, encoding="utf-8")
        logger.info("TXT text extracted: %s (%d chars)", file_path.name, len(text))
        return [(1, markdown)]

    raise ValueError(f"Unsupported file type: {ext} ({file_path.name})")


async def ocr_documents_parallel(
    files: List[dict],
    cache_root: str | Path,
    max_concurrent_files: Optional[int] = None,
) -> dict:
    """OCR multiple files in parallel (Layer 2).
    
    Args:
        files: list of dicts with keys 'path', 'stem', 'pages'
        cache_root: cache directory
        max_concurrent_files: max files to process simultaneously
    
    Returns:
        dict with 'results' (list of file results), 'stats' (timing/counts)
    """
    import time
    cache_root = Path(cache_root)
    max_files = max_concurrent_files or OCR_MAX_CONCURRENT
    file_semaphore = asyncio.Semaphore(max_files)
    vlm_semaphore = global_vlm_semaphore()
    stats = {"total_files": len(files), "native_pages": 0, "vlm_pages": 0, "cached_pages": 0, "errors": []}

    async def _process_file(file_info: dict):
        async with file_semaphore:
            fpath = Path(file_info["path"])
            stem = file_info.get("stem", fpath.stem)
            logger.info("Starting OCR: %s", fpath.name)
            start = time.time()
            try:
                results = await ocr_document(
                    fpath,
                    cache_root,
                    doc_name=stem,
                    vlm_semaphore=vlm_semaphore,
                )
                elapsed = time.time() - start
                # Collect method stats from raw results
                pages_raw = getattr(results, 'raw', [])
                method_counts = {"native": 0, "vlm": 0, "cache": 0}
                for r in pages_raw:
                    method = r[2] if len(r) > 2 else "unknown"
                    if "native" in method:
                        method_counts["native"] += 1
                    if "vlm" in method:
                        method_counts["vlm"] += 1
                    if "cache" in method:
                        method_counts["cache"] += 1
                
                logger.info("Finished OCR: %s (%d pages, %.1fs, native=%d vlm=%d cache=%d)",
                    fpath.name, len(results), elapsed,
                    method_counts["native"], method_counts["vlm"], method_counts["cache"])
                return {
                    "file": fpath.name, "pages": results, "elapsed": elapsed,
                    "error": None, "pages_raw": pages_raw, "methods": method_counts,
                }
            except Exception as e:
                elapsed = time.time() - start
                logger.error("OCR failed: %s (%.1fs): %s", fpath.name, elapsed, e)
                stats["errors"].append({"file": fpath.name, "error": str(e)})
                return {"file": fpath.name, "pages": [], "elapsed": elapsed, "error": str(e), "pages_raw": [], "methods": {}}

    tasks = [_process_file(f) for f in files]
    results = await asyncio.gather(*tasks)

    # Aggregate method counts from each file into stats
    for r in results:
        methods = r.get("methods", {})
        stats["native_pages"] += methods.get("native", 0)
        stats["vlm_pages"] += methods.get("vlm", 0)
        stats["cached_pages"] += methods.get("cache", 0)

    return {"results": results, "stats": stats}


# ---------------------------------------------------------------------------
# Legacy API (for single-page batch re-processing)
# ---------------------------------------------------------------------------
async def ocr_pages_batch(
    file_path: str | Path,
    page_indices: List[int],
    cache_root: str | Path,
    doc_name: Optional[str] = None,
) -> List[Tuple[int, str]]:
    """OCR specific pages of a PDF."""
    file_path = Path(file_path)
    cache_root = Path(cache_root)
    if doc_name is None:
        doc_name = file_path.stem

    semaphore = global_vlm_semaphore()
    
    # Get total pages for model selection
    try:
        doc = fitz.open(str(file_path))
        num_pages = len(doc)
        doc.close()
    except Exception:
        num_pages = len(page_indices)

    async def _process(idx: int):
        page_num, text, _ = await _ocr_page_smart(
            file_path, idx, doc_name, idx + 1, cache_root, semaphore, total_pages=num_pages
        )
        return page_num, text

    tasks = [_process(i) for i in page_indices]
    raw = await asyncio.gather(*tasks, return_exceptions=True)
    results = []
    for i, r in enumerate(raw):
        if isinstance(r, Exception):
            logger.error("OCR page batch [%d] failed: %s", page_indices[i] if i < len(page_indices) else i, r)
            continue
        results.append(r)
    results.sort(key=lambda x: x[0])
    return results


def get_cached_text(doc_name: str, page_num: int, cache_root: str | Path) -> Optional[str]:
    """Read cached OCR text for a page, or None if not cached."""
    md_cache = Path(cache_root) / doc_name / f"p{page_num}.md"
    if md_cache.exists():
        return md_cache.read_text(encoding="utf-8")
    return None


def clear_cache(doc_name: str, cache_root: str | Path) -> int:
    """Delete all cached files for a document."""
    cdir = Path(cache_root) / doc_name
    if not cdir.exists():
        return 0
    count = 0
    for f in cdir.iterdir():
        f.unlink()
        count += 1
    cdir.rmdir()
    return count
