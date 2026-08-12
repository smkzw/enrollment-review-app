"""Review phase helpers for staged enrollment review."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


FULL_PHASE_ID = "full"


DEFAULT_PHASES: List[Dict[str, Any]] = [
    {
        "phase_id": FULL_PHASE_ID,
        "name": "全量审核",
        "visit": "",
        "day_window": "",
        "description": "使用全部已提供资料进行完整入排审核。",
        "required_items": [],
        "included_document_phases": ["prior", "screening", "baseline", "postbaseline", "communication", "unknown"],
    },
    {
        "phase_id": "screening_run_in",
        "name": "筛选/导入期",
        "visit": "V1",
        "day_window": "D-7~D-1",
        "description": "仅审核筛选/导入期及此前应完成的入排相关要求。",
        "required_items": ["签署知情同意书", "审核入选/排除标准"],
        "included_document_phases": ["prior", "screening", "communication", "unknown"],
    },
    {
        "phase_id": "baseline_randomization",
        "name": "基线/随机前",
        "visit": "V2（基线）",
        "day_window": "D1",
        "description": "在筛选/导入期基础上，审核基线、随机前和给药前应完成的要求。",
        "required_items": ["审核入选/排除标准", "随机"],
        "included_document_phases": ["prior", "screening", "baseline", "communication", "unknown"],
    },
]


def _normalize_study_stage(value: str) -> str:
    text = re.sub(r"\s+", "", value or "")
    if text in {"2期", "二期", "II期", "Ⅱ期", "II", "Ⅱ"}:
        return "Ⅱ期"
    if text in {"3期", "三期", "III期", "Ⅲ期", "III", "Ⅲ"}:
        return "Ⅲ期"
    return (value or "").strip()


def _configured_project_stage(project_path: Path) -> str:
    cfg_path = project_path / "config.json"
    if not cfg_path.exists():
        return ""
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        return _normalize_study_stage(data.get("study_stage", ""))
    except Exception:
        return ""


def _scope_workflow_to_project_stage(workflow: Dict[str, Any], project_path: Path) -> Dict[str, Any]:
    stage = _configured_project_stage(project_path)
    if not stage:
        return workflow
    scoped = dict(workflow)
    protocol_stages = scoped.get("protocol_study_stages") or scoped.get("study_stages") or []
    scoped["protocol_study_stages"] = protocol_stages
    scoped["study_stage"] = stage
    scoped["study_stages"] = [stage]
    scoped["requires_study_stage_selection"] = False
    stage_phases = [
        phase for phase in scoped.get("review_phases", [])
        if not phase.get("study_stage") or _normalize_study_stage(str(phase.get("study_stage", ""))) == stage
    ]
    if stage_phases:
        normalized_phases = []
        for phase in stage_phases:
            item = dict(phase)
            item["study_stage"] = stage
            normalized_phases.append(item)
        scoped["review_phases"] = normalized_phases
    return scoped


def normalize_phase_id(review_phase: Optional[str]) -> str:
    value = (review_phase or FULL_PHASE_ID).strip()
    return value or FULL_PHASE_ID


def artifact_suffix(review_phase: Optional[str]) -> str:
    phase_id = normalize_phase_id(review_phase)
    if phase_id == FULL_PHASE_ID:
        return ""
    return f"_{re.sub(r'[^A-Za-z0-9_-]+', '_', phase_id)}"


def phase_bundle_path(subject_dir: Path, review_phase: Optional[str]) -> Path:
    suffix = artifact_suffix(review_phase)
    return subject_dir / f"evidence_bundle{suffix}.md"


def phase_llm_dir(subject_dir: Path, review_phase: Optional[str]) -> Path:
    phase_id = normalize_phase_id(review_phase)
    if phase_id == FULL_PHASE_ID:
        return subject_dir / "llm"
    return subject_dir / "llm" / phase_id


def load_review_workflow(project_path: Path, rules_text: str = "") -> Dict[str, Any]:
    """Load project review workflow, falling back to conservative defaults."""
    workflow_path = project_path / "review_phases.json"
    if workflow_path.exists():
        try:
            data = json.loads(workflow_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("review_phases"):
                return _scope_workflow_to_project_stage(data, project_path)
        except Exception:
            pass

    stages = []
    if "Ⅱ/Ⅲ" in rules_text or "II期/Ⅲ期" in rules_text or "Ⅱ期" in rules_text and "Ⅲ期" in rules_text:
        stages = ["Ⅱ期", "Ⅲ期"]

    phases = [dict(p) for p in DEFAULT_PHASES]
    if "筛选/导入期" not in rules_text and "基线" not in rules_text:
        phases = [dict(DEFAULT_PHASES[0])]

    return _scope_workflow_to_project_stage({
        "study_stages": stages,
        "requires_study_stage_selection": len(stages) > 1,
        "review_phases": phases,
    }, project_path)


def phase_by_id(workflow: Dict[str, Any], review_phase: Optional[str]) -> Dict[str, Any]:
    phase_id = normalize_phase_id(review_phase)
    for phase in workflow.get("review_phases", []):
        if phase.get("phase_id") == phase_id:
            return phase
    for phase in DEFAULT_PHASES:
        if phase["phase_id"] == phase_id:
            return dict(phase)
    return dict(DEFAULT_PHASES[0])


def infer_document_phase(doc_stem: str, category: str = "") -> str:
    """Infer where a document belongs in the staged review timeline."""
    text = f"{doc_stem} {category}".lower()
    original = f"{doc_stem} {category}"

    if any(kw in original for kw in ("邮件", "沟通", "审核", "Q&A", "监查")) or any(
        kw in text for kw in ("email", "qa")
    ):
        return "communication"
    if any(kw in original for kw in ("既往", "病史", "出院")):
        return "prior"
    if any(kw in original for kw in ("基线", "随机前", "随机", "D1", "给药前")) or any(
        kw in text for kw in ("baseline", "random")
    ):
        return "baseline"
    if any(kw in original for kw in ("筛选", "导入", "入组")) or any(
        kw in text for kw in ("screening", "run-in", "run in")
    ):
        return "screening"
    if any(kw in original for kw in ("V3", "V4", "V5", "V6", "V7", "W1", "W2", "W4", "W8", "W12")):
        return "postbaseline"
    return "unknown"


def document_allowed_for_phase(doc_phase: str, review_phase_info: Dict[str, Any]) -> bool:
    allowed = review_phase_info.get("included_document_phases")
    if not allowed:
        allowed = DEFAULT_PHASES[0]["included_document_phases"]
    return doc_phase in allowed


def render_phase_scope(review_phase_info: Dict[str, Any], study_stage: str = "") -> str:
    phase_name = review_phase_info.get("name") or "全量审核"
    visit = review_phase_info.get("visit") or ""
    day_window = review_phase_info.get("day_window") or ""
    required = review_phase_info.get("required_items") or []

    lines = [
        "## 当前审核范围",
        f"- 当前研究阶段：{study_stage or '未指定'}",
        f"- 当前审核阶段：{phase_name}",
    ]
    if visit:
        lines.append(f"- 对应访视：{visit}")
    if day_window:
        lines.append(f"- 时间窗：{day_window}")
    if required:
        lines.append("- 本阶段应重点核查：" + "、".join(required))
    lines.append(
        "- 阶段性审核原则：只对截至本阶段应完成、且实际应已能获得的资料下结论；"
        "尚未到达的基线/随机前要求不得因当前资料未提供而判为证据不足，除非该要求在本阶段已经应完成。"
    )
    return "\n".join(lines)
