"""Subject-level date extraction helpers."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from app.shared import load_subject_info, save_subject_info


DATE_RE = re.compile(r"(20\d{2})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})\s*日?")
ICF_CONTEXT_RE = re.compile(r"(知情同意|同意书|ICF|签署|签字|受试者同意)", re.I)
WEAK_DATE_CONTEXT_RE = re.compile(r"(筛选日期|筛选期|报告日期|采样日期|检测日期|就诊日期)")
VERSION_DATE_CONTEXT_RE = re.compile(r"(版本号|版本日期|方案版本|模板|生效日期|修订日期|Master\s*V)", re.I)
SIGNATURE_LOCAL_RE = re.compile(
    r"(受试者|患者|研究者|医生|医师)?[^。；;\n]{0,24}"
    r"(签署|签字)[^。；;\n]{0,16}(知情同意|同意书|ICF)|"
    r"(知情同意|同意书|ICF)[^。；;\n]{0,20}(签署|签字)",
    re.I,
)
SCREENING_RECORD_KEYWORDS = re.compile(r"(筛选|基线|病历|知情同意|screening|baseline|record|icf)", re.I)
SUBJECT_ID_RE = re.compile(r"(?:SA)?\d{5}", re.I)


def normalize_date_text(value: str) -> str:
    """Return YYYY-MM-DD when a date is recognizable, otherwise stripped text."""
    text = str(value or "").strip()
    if not text:
        return ""
    match = DATE_RE.search(text)
    if not match:
        return text
    year, month, day = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _candidate_score(path: Path, context: str, date_start: int | None = None, date_end: int | None = None) -> int:
    combined = f"{path.name}\n{context}"
    if date_start is not None and date_end is not None:
        local = context[max(0, date_start - 36): min(len(context), date_end + 36)]
    else:
        local = context
    score = 0
    if ICF_CONTEXT_RE.search(path.name):
        score += 12
    if ICF_CONTEXT_RE.search(context):
        score += 10
    if re.search(r"(签署|签字).{0,16}(知情同意|同意书|ICF)", context, re.I):
        score += 8
    if re.search(r"(知情同意|同意书|ICF).{0,16}(签署|签字|日期)", context, re.I):
        score += 8
    if SIGNATURE_LOCAL_RE.search(local):
        score += 24
    if re.search(r"(受试者|患者)[^。；;\n]{0,12}于\s*$", context[:date_start or 0], re.I):
        score += 18
    if VERSION_DATE_CONTEXT_RE.search(local):
        score -= 36
    if re.search(r"(版本日期|方案版本日期|模板日期)\s*[：:]*\s*$", context[:date_start or 0], re.I):
        score -= 36
    if WEAK_DATE_CONTEXT_RE.search(combined) and not ICF_CONTEXT_RE.search(combined):
        score -= 8
    return score


def _doc_category_for_cache_path(path: Path, categories: dict[str, str] | None = None) -> str:
    categories = categories or {}
    doc_stem = path.parent.name if re.match(r"^p\d+\.md$", path.name, re.I) else path.stem
    candidates = [
        doc_stem,
        f"{doc_stem}.pdf",
        f"{doc_stem}.docx",
        f"{doc_stem}.doc",
    ]
    for key in candidates:
        if key in categories:
            return str(categories[key] or "")
    return ""


def _is_valid_icf_source(path: Path, categories: dict[str, str] | None = None) -> bool:
    category = _doc_category_for_cache_path(path, categories)
    if category:
        return category == "screening_record"
    doc_label = f"{path.parent.name} {path.name}"
    if re.search(r"(邮件|沟通|讨论|审核|合格性|email|qa|q&a)", doc_label, re.I):
        return False
    return bool(SCREENING_RECORD_KEYWORDS.search(doc_label))


def _has_conflicting_subject_id(text: str, subject_id: str = "") -> bool:
    normalized = re.sub(r"\D", "", subject_id or "")
    if not normalized:
        return False
    ids = {re.sub(r"\D", "", m.group(0)) for m in SUBJECT_ID_RE.finditer(text or "")}
    ids = {item for item in ids if item}
    return bool(ids and normalized not in ids)


def _date_is_reasonable(date_str: str) -> bool:
    if not date_str:
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    return "2024-01-01" <= date_str <= today


def extract_icf_date_from_cache(
    cache_dir: Path,
    subject_id: str = "",
    categories: dict[str, str] | None = None,
) -> str:
    """Extract the best ICF/signature date from cached OCR markdown files."""
    if not cache_dir.exists():
        return ""

    candidates: list[tuple[int, int, str, str]] = []
    order = 0
    for path in sorted(cache_dir.rglob("*.md")):
        if not _is_valid_icf_source(path, categories):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if _has_conflicting_subject_id(text, subject_id):
            continue
        for match in DATE_RE.finditer(text):
            start = max(0, match.start() - 80)
            end = min(len(text), match.end() + 80)
            context = text[start:end]
            if _has_conflicting_subject_id(context, subject_id):
                continue
            score = _candidate_score(path, context, match.start() - start, match.end() - start)
            if score <= 0:
                continue
            date_text = normalize_date_text(match.group(0))
            if not _date_is_reasonable(date_text):
                continue
            candidates.append((score, order, date_text, path.name))
            order += 1

    if not candidates:
        return ""
    candidates.sort(key=lambda item: (-item[0], item[1], item[3]))
    return candidates[0][2]


def backfill_subject_icf_date(subject_path: Path) -> bool:
    """Fill SubjectInfo.icf_date from OCR cache unless manually overridden."""
    info = load_subject_info(subject_path)
    if info.icf_date_manual:
        return False
    categories = {}
    cat_path = subject_path / "file_categories.json"
    if cat_path.exists():
        try:
            import json
            loaded = json.loads(cat_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                categories = {str(k): str(v) for k, v in loaded.items()}
        except Exception:
            categories = {}
    date = extract_icf_date_from_cache(subject_path / "cache", subject_id=info.subject_id, categories=categories)
    if not date or date == info.icf_date:
        return False
    info.icf_date = date
    save_subject_info(subject_path, info)
    return True


def subject_anchor_dates(subject_path: Path, review_phase: str = "") -> dict[str, str]:
    """Return non-empty anchor dates for evidence bundling and LLM review."""
    info = load_subject_info(subject_path)
    anchors = {
        key: value
        for key, value in {
            "screening_date": info.screening_date,
            "icf_date": info.icf_date,
            "first_dosing_date": info.first_dosing_date,
            "birth_date": info.birth_date,
        }.items()
        if value
    }
    phase_id = str(review_phase or "").strip()
    if phase_id and isinstance(info.phase_anchor_dates, dict):
        phase_anchor = normalize_date_text(str(info.phase_anchor_dates.get(phase_id) or ""))
        if phase_anchor:
            anchors["review_phase_anchor_date"] = phase_anchor
    return anchors
