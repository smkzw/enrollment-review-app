"""Shared path helpers and SSE utility for the enrollment review app."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from fastapi import HTTPException

from app.config import PROJECTS_DIR
from app.models import ProjectConfig, SubjectInfo, SubjectStatus


# Global project registry (loaded at startup)
projects: Dict[str, ProjectConfig] = {}


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_STORAGE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def validate_storage_id(value: str, name: str = "ID") -> str:
    """Validate a user-controlled identifier before using it as a path part."""
    text = str(value or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail=f"{name}不能为空")
    if text in {".", ".."} or ".." in text:
        raise HTTPException(status_code=400, detail=f"{name}不允许包含 '..'")
    if "/" in text or "\\" in text:
        raise HTTPException(status_code=400, detail=f"{name}不允许包含路径分隔符")
    if not _STORAGE_ID_RE.fullmatch(text):
        raise HTTPException(status_code=400, detail=f"{name}只允许字母、数字、下划线、连字符和点号")
    return text


def project_dir(code: str) -> Path:
    code = validate_storage_id(code, "项目编号")
    return PROJECTS_DIR / code


def subject_dir(project_code: str, subject_id: str) -> Path:
    project_code = validate_storage_id(project_code, "项目编号")
    subject_id = validate_storage_id(subject_id, "受试者ID")
    return project_dir(project_code) / "subjects" / subject_id


def ensure_project(code: str) -> ProjectConfig:
    """Return ProjectConfig or raise 404."""
    cfg = projects.get(code)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"Project '{code}' not found")
    return cfg


def ensure_subject(project_code: str, subject_id: str) -> Path:
    """Return subject directory path or raise 404."""
    sd = subject_dir(project_code, subject_id)
    if not sd.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Subject '{subject_id}' not found in project '{project_code}'",
        )
    return sd


def load_subject_info(sd: Path) -> SubjectInfo:
    """Load SubjectInfo from info.json."""
    info_path = sd / "info.json"
    if not info_path.exists():
        raise HTTPException(status_code=404, detail="Subject info not found")
    data = json.loads(info_path.read_text(encoding="utf-8"))
    return SubjectInfo(**{
        k: v for k, v in data.items() if k in SubjectInfo.__dataclass_fields__
    })


def save_subject_info(sd: Path, info: SubjectInfo):
    """Persist SubjectInfo to info.json."""
    from dataclasses import asdict
    info_path = sd / "info.json"
    info_path.write_text(
        json.dumps(asdict(info), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def list_files_in_dir(directory: Path) -> List[dict]:
    """Return a list of file info dicts for all files in a directory."""
    if not directory.exists():
        return []
    result = []
    for f in sorted(directory.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            result.append({
                "name": f.name,
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
    return result


def clear_subject_outputs(sd: Path, info: SubjectInfo) -> None:
    """Clear all derived outputs (cache, bundle, LLM reports) and reset status."""
    import shutil
    for subdir in ("cache", "llm"):
        d = sd / subdir
        if d.exists():
            shutil.rmtree(d)
    for bundle in sd.glob("evidence_bundle*.md"):
        if bundle.is_file():
            bundle.unlink()
    info.status = SubjectStatus.PENDING.value
    info.overall_verdict = ""
    save_subject_info(sd, info)


def sse_event(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
