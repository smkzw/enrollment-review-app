"""
Evidence Bundle Builder v2.0
============================
Combines page-level OCR results into evidence_bundle.md for LLM review.
No auto anchor date extraction — dates are identified by the LLM from evidence.
Supports 5 document categories with hierarchical evidence weighting.
"""

from __future__ import annotations

import re
from pathlib import Path
from collections import defaultdict
from typing import Optional, Dict, List

from app.phases import (
    DEFAULT_PHASES,
    document_allowed_for_phase,
    infer_document_phase,
    phase_by_id,
)


# ---------------------------------------------------------------------------
# 5 document categories with hierarchy (lower number = higher authority)
# ---------------------------------------------------------------------------
CATEGORY_CONFIG = {
    "screening_record": {
        "label": "筛选-基线病历",
        "priority": 1,
        "desc": "筛选期研究病历、基线评估记录 — 最权威来源，ICF/入排判断以此为准",
    },
    "screening_lab": {
        "label": "筛选-基线检验报告单",
        "priority": 2,
        "desc": "筛选期实验室检查、影像、心电图等",
    },
    "prior_record": {
        "label": "既往病历",
        "priority": 3,
        "desc": "既往就诊病历、诊断记录 — 历史参考",
    },
    "prior_lab": {
        "label": "既往检验检查报告单",
        "priority": 4,
        "desc": "既往实验室检查、影像等 — 历史参考",
    },
    "enrollment_comm": {
        "label": "入组审核邮件/沟通记录/Q&A",
        "priority": 5,
        "desc": "中心监查员沟通、医学监查Q&A、审核过程邮件 — 辅助参考",
    },
    "unknown": {
        "label": "其他",
        "priority": 99,
        "desc": "未分类文档",
    },
}

CATEGORY_LABELS = {k: v["label"] for k, v in CATEGORY_CONFIG.items()}
CATEGORY_PRIORITY = {k: v["priority"] for k, v in CATEGORY_CONFIG.items()}
SUBJECT_ID_RE = re.compile(r"(?:SA)?\d{5}", re.I)


def classify_by_filename(filename: str) -> str:
    """Auto-detect document category from filename keywords."""
    fn = filename.lower()
    if any(kw in fn for kw in ["筛选", "基线", "入组", "screening", "baseline"]):
        if any(kw in fn for kw in ["检验", "检查", "化验", "报告", "lab", "影像", "心电", "ecg"]):
            return "screening_lab"
        return "screening_record"
    if any(kw in fn for kw in ["既往", "病史", "出院", "诊断", "prior", "history"]):
        if any(kw in fn for kw in ["检验", "检查", "化验", "报告", "lab"]):
            return "prior_lab"
        return "prior_record"
    if any(kw in fn for kw in ["检验", "检查", "化验", "报告单", "lab", "影像", "心电", "ecg", "超声", "ct", "x-ray", "xray"]):
        return "screening_lab"
    if any(kw in fn for kw in ["邮件", "沟通", "审核", "qa", "q&a", "监查", "email", "monitor"]):
        return "enrollment_comm"
    if any(kw in fn for kw in ["病历", "record", "chart"]):
        return "screening_record"
    return "unknown"


def _discover_documents(subject_dir: Path) -> dict:
    docs = {}
    cache_dir = subject_dir / "cache"
    if not cache_dir.exists():
        raise FileNotFoundError(f"Cache directory not found: {cache_dir}")
    for subdir in sorted(cache_dir.iterdir()):
        if subdir.is_dir():
            pages = sorted(subdir.glob("*.md"))
            if pages:
                docs[subdir.name] = pages
    if docs:
        return docs
    for md_file in sorted(cache_dir.glob("*.md")):
        stem = md_file.stem
        m = re.match(r"^(.+?)[-_]p(?:age)?(\d+)$", stem, re.IGNORECASE)
        doc_stem = m.group(1) if m else stem
        docs.setdefault(doc_stem, []).append(md_file)
    for key in docs:
        docs[key].sort(key=lambda p: int(re.search(r"(\d+)", p.stem).group(1)) if re.search(r"(\d+)", p.stem) else 0)
    return docs


def _page_number(path: Path) -> int:
    m = re.search(r"(\d+)", path.stem)
    return int(m.group(1)) if m else 0


def _source_filename_for_doc(doc_stem: str, user_cats: dict) -> str:
    candidates = [
        doc_stem,
        f"{doc_stem}.pdf",
        f"{doc_stem}.docx",
        f"{doc_stem}.doc",
        f"{doc_stem}.jpg",
        f"{doc_stem}.jpeg",
        f"{doc_stem}.png",
        f"{doc_stem}.bmp",
        f"{doc_stem}.tif",
        f"{doc_stem}.tiff",
        f"{doc_stem}.webp",
    ]
    for candidate in candidates:
        if candidate in user_cats:
            return candidate
    return doc_stem


def build_evidence_bundle(
    subject_dir: Path,
    project_code: str,
    criteria_rules: str = "",
    anchor_dates: Optional[Dict[str, str]] = None,
    review_phase: str = "full",
    review_workflow: Optional[Dict] = None,
) -> str:
    """Build evidence bundle from cached OCR pages.

    No auto-extraction of anchor dates. User-provided anchor_dates are hints.
    Documents ordered by category priority.
    """
    subject_dir = Path(subject_dir)
    docs = _discover_documents(subject_dir)
    anchor_dates = anchor_dates or {}

    # Categorize documents — prefer user-provided mapping, fall back to filename detection
    doc_categories = {}
    cat_file = subject_dir / "file_categories.json"
    user_cats = {}
    if cat_file.exists():
        try:
            import json
            user_cats = json.loads(cat_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    workflow = review_workflow or {"review_phases": DEFAULT_PHASES}
    phase_info = phase_by_id(workflow, review_phase)

    for doc_stem in docs:
        if doc_stem in user_cats:
            doc_categories[doc_stem] = user_cats[doc_stem]
        elif f"{doc_stem}.pdf" in user_cats:
            doc_categories[doc_stem] = user_cats[f"{doc_stem}.pdf"]
        elif f"{doc_stem}.docx" in user_cats:
            doc_categories[doc_stem] = user_cats[f"{doc_stem}.docx"]
        elif f"{doc_stem}.doc" in user_cats:
            doc_categories[doc_stem] = user_cats[f"{doc_stem}.doc"]
        else:
            doc_categories[doc_stem] = classify_by_filename(doc_stem)

    doc_phases = {
        doc_stem: infer_document_phase(doc_stem, doc_categories.get(doc_stem, ""))
        for doc_stem in docs
    }
    filtered_docs = {
        doc_stem: pages
        for doc_stem, pages in docs.items()
        if document_allowed_for_phase(doc_phases.get(doc_stem, "unknown"), phase_info)
    }

    # Sort by category priority
    sorted_docs = sorted(
        filtered_docs.items(),
        key=lambda kv: (
            CATEGORY_PRIORITY.get(doc_categories[kv[0]], 99),
            doc_phases.get(kv[0], "unknown"),
            kv[0],
        ),
    )

    # Build chunks
    chunks = []
    subject_warnings = []
    chunk_id = 0
    expected_subject_digits = re.sub(r"\D", "", subject_dir.name)

    for doc_stem, page_paths in sorted_docs:
        cat = doc_categories[doc_stem]
        cat_label = CATEGORY_LABELS.get(cat, cat)
        cat_priority = CATEGORY_PRIORITY.get(cat, 99)

        for page_path in page_paths:
            chunk_id += 1
            cid = f"ck_{chunk_id:04d}"
            raw_text = page_path.read_text(encoding="utf-8", errors="replace")
            body = raw_text
            # Strip HTML comment prefix from cached OCR
            if body.startswith("<!--"):
                nl = body.find("\n")
                if nl > 0:
                    body = body[nl+1:].strip()
            detected_subjects = {re.sub(r"\D", "", m.group(0)) for m in SUBJECT_ID_RE.finditer(body)}
            detected_subjects = {item for item in detected_subjects if item}
            if expected_subject_digits and detected_subjects and expected_subject_digits not in detected_subjects:
                subject_warnings.append(
                    f"- {_source_filename_for_doc(doc_stem, user_cats)} p{_page_number(page_path)}：识别到受试者编号 "
                    f"{'、'.join(sorted(detected_subjects))}，与当前文件夹 {subject_dir.name} 不一致，请复核是否放错资料。"
                )

            page_num = _page_number(page_path)
            chunk_lines = [
                f"### 【{cat_label}】p{page_num} (片段{cid})",
                f"- 证据类别：{cat_label}（优先级{cat_priority}/5，1最高）",
                f"- 文档阶段：{doc_phases.get(doc_stem, 'unknown')}",
                f"- 来源文件：{_source_filename_for_doc(doc_stem, user_cats)}",
                "",
                body,
            ]
            chunks.append("\n".join(chunk_lines))

    total_chunks = len(chunks)

    # Build file mapping table
    file_map_lines = [
        "## 文件编号与类别对照表",
        "| 文件简称 | 证据类别 | 优先级 | 包含片段 |",
        "|----------|----------|--------|----------|",
    ]
    chunk_idx = 0
    for doc_stem, page_paths in sorted_docs:
        cat = doc_categories[doc_stem]
        cat_label = CATEGORY_LABELS.get(cat, cat)
        priority = CATEGORY_PRIORITY.get(cat, 99)
        npages = len(page_paths)
        start_cid = f"ck_{chunk_idx + 1:04d}"
        end_cid = f"ck_{chunk_idx + npages:04d}"
        cid_range = start_cid if npages == 1 else f"{start_cid}–{end_cid}"
        chunk_idx += npages
        short_name = re.sub(r'^[A-Za-z]{2}\d{4,6}', '', doc_stem) or doc_stem
        file_map_lines.append(
            f"| {short_name} | {cat_label} | {priority} | "
            f"{doc_phases.get(doc_stem, 'unknown')} | {cid_range} |"
        )

    file_map_table = "\n".join(file_map_lines)
    file_map_table = file_map_table.replace(
        "| 文件简称 | 证据类别 | 优先级 | 包含片段 |",
        "| 文件简称 | 证据类别 | 优先级 | 文档阶段 | 包含片段 |",
    ).replace(
        "|----------|----------|--------|----------|",
        "|----------|----------|--------|----------|----------|",
    )

    # Anchor dates (user hints only)
    anchor_rows = []
    label_map = {
        "screening_date": "筛选日期",
        "icf_date": "ICF签署日期",
        "first_dosing_date": "首次给药日期",
        "birth_date": "出生日期",
        "review_phase_anchor_date": "本次审核锚点日期（基线/随机前）",
    }
    for key, label in label_map.items():
        val = anchor_dates.get(key, "")
        if val:
            anchor_rows.append(f"| {label} | {val} | 用户提供 |")
        else:
            anchor_rows.append(f"| {label} | ... | 未提供结构化值；仅可从明确原文核实 |")

    anchor_table = "\n".join(anchor_rows)

    # Evidence hierarchy notice
    hierarchy_notice = (
        "## 证据层级说明\n\n"
        "证据优先级需按事实类型判断，当不同来源对同一信息有冲突时：\n"
        "- **当期事实**（ICF签署、筛选/基线生命体征、当期检验检查、当期评分）优先采信筛选-基线病历或报告单；如ICF签署日期，以筛选病历记录为准。\n"
        "- **既往事实/病程时长**（既往诊断、最早症状、病史超过X年/月、既往治疗/手术/用药/检查异常）优先采信既往病历、出院小结、诊断证明、既往检查报告或既往处方；筛选/基线病历中的病史描述属于转述，若无更早源文件支持，应提示“病史来源需溯源验证”。\n"
        "- **筛选-基线检验报告** > 既往检验报告\n"
        "- 病历记录 > 邮件/沟通记录（邮件中的建议不构成事实认定）\n\n"
        "审核时请优先采信对应事实类型的高层级证据。"
    )

    # Assemble
    joined_chunks = "\n\n---\n\n".join(chunks)
    phase_name = phase_info.get("name", "全量审核")
    phase_visit = phase_info.get("visit", "")
    phase_window = phase_info.get("day_window", "")
    phase_items = phase_info.get("required_items") or []
    phase_lines = [
        "## 审核阶段",
        f"审核阶段：**{phase_name}**",
    ]
    if phase_visit:
        phase_lines.append(f"- 对应访视：{phase_visit}")
    if phase_window:
        phase_lines.append(f"- 时间窗：{phase_window}")
    if phase_items:
        phase_lines.append(f"- 本阶段应核查项目：{'；'.join(phase_items)}")
    phase_lines.append(f"- 阶段过滤：本包纳入 {len(sorted_docs)} 个文档，排除明显属于后续阶段的文档。")
    phase_scope = "\n".join(phase_lines)
    subject_warning_block = ""
    if subject_warnings:
        subject_warning_block = (
            "## 资料一致性警告\n\n"
            + "\n".join(subject_warnings[:20])
            + ("\n- 其余不一致项已截断显示，请查看OCR缓存。" if len(subject_warnings) > 20 else "")
            + "\n\n"
        )

    bundle = (
        f"# 受试者证据材料\n"
        f"项目：**{project_code}**\n\n"
        f"{phase_scope}\n\n"
        f"{file_map_table}\n\n"
        f"{subject_warning_block}"
        f"## 锚点日期（仅供参考，不得用报告日期/打印日期/上传日期替代）\n"
        f"| 锚点 | 取值 | 来源 |\n"
        f"|------|------|------|\n"
        f"{anchor_table}\n\n"
        f"{hierarchy_notice}\n\n"
        f"## 证据材料\n"
        f"共 {total_chunks} 个片段\n\n"
        f"{joined_chunks}\n"
    )

    return bundle
