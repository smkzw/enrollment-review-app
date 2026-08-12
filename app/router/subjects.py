"""Subject management endpoints — CRUD, upload, reset."""

from __future__ import annotations

import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.shared import (
    ensure_project, ensure_subject, subject_dir, project_dir,
    load_subject_info, save_subject_info, list_files_in_dir, clear_subject_outputs,
    validate_storage_id,
)
from app.models import SubjectInfo, SubjectStatus
from app.authz import current_user, require_project_access, require_subject_modify, can_modify_subject
from app.centers import normalize_center_code, normalize_center_name, upsert_center
from app.subject_dates import normalize_date_text
from app.audit import log_audit
from app.phases import load_review_workflow, phase_llm_dir
from app.pipeline.reviewer import parse_review_response

router = APIRouter(prefix="/api/projects/{code}/subjects", tags=["subjects"])
ALLOWED_SUBJECT_UPLOAD_EXTENSIONS = {
    ".pdf", ".docx", ".doc",
    ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp",
    ".txt",
}


class SubjectCreate(BaseModel):
    subject_id: str
    center_code: str = ""
    center_name: str = ""


class SubjectUpdate(BaseModel):
    center_code: Optional[str] = None
    center_name: Optional[str] = None
    screening_date: Optional[str] = None
    icf_date: Optional[str] = None
    phase_anchor_dates: Optional[Dict[str, str]] = None


def _display_review_phases(code: str) -> list[dict]:
    pd = project_dir(code)
    rules_path = pd / "criteria_rules.md"
    rules_text = rules_path.read_text(encoding="utf-8") if rules_path.exists() else ""
    workflow = load_review_workflow(pd, rules_text)
    phases = workflow.get("review_phases") or [{"phase_id": "full", "name": "全量审核"}]
    non_full = [phase for phase in phases if str(phase.get("phase_id") or "") != "full"]
    return non_full or phases


def _subject_phase_reviews(code: str, sd: Path) -> dict[str, dict]:
    summaries: dict[str, dict] = {}
    for phase in _display_review_phases(code):
        phase_id = str(phase.get("phase_id") or "full")
        report_dir = phase_llm_dir(sd, phase_id)
        report_path = report_dir / "review_report.md"
        raw_path = report_dir / "review_raw.md"
        item = {
            "phase_id": phase_id,
            "name": phase.get("name") or phase_id,
            "visit": phase.get("visit") or "",
            "day_window": phase.get("day_window") or "",
            "has_report": False,
            "status": "not_reviewed",
            "verdict": "",
            "summary": "",
            "updated_at": "",
        }
        parse_path = report_path if report_path.exists() else raw_path if raw_path.exists() else None
        if parse_path:
            try:
                parsed = parse_review_response(parse_path.read_text(encoding="utf-8"))
                item["has_report"] = True
                item["status"] = "reviewed"
                item["verdict"] = parsed.get("overall_verdict") or ""
                item["summary"] = parsed.get("summary") or ""
                item["updated_at"] = datetime.fromtimestamp(parse_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                item["has_report"] = True
                item["status"] = "parse_error"
        summaries[phase_id] = item
    return summaries


def _safe_upload_filename(filename: str | None) -> str:
    original = str(filename or "").strip()
    if not original:
        raise HTTPException(status_code=400, detail="上传文件名不能为空")
    if "/" in original or "\\" in original:
        raise HTTPException(status_code=400, detail="上传文件名不能包含路径分隔符")
    safe_name = Path(original).name.strip()
    if safe_name in {"", ".", ".."} or ".." in safe_name:
        raise HTTPException(status_code=400, detail="上传文件名不合法")
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_SUBJECT_UPLOAD_EXTENSIONS:
        allowed = "、".join(sorted(ALLOWED_SUBJECT_UPLOAD_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"不支持的文件类型：{suffix or '无扩展名'}；允许：{allowed}")
    return safe_name


def _safe_upload_destination(raw_dir: Path, filename: str | None) -> Path:
    safe_name = _safe_upload_filename(filename)
    candidate = raw_dir / safe_name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        candidate = raw_dir / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("")
async def list_subjects(code: str, request: Request):
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    subjects_dir = project_dir(code) / "subjects"
    result = []
    if subjects_dir.exists():
        for sd in sorted(subjects_dir.iterdir()):
            if not sd.is_dir():
                continue
            info_path = sd / "info.json"
            if info_path.exists():
                try:
                    import json
                    data = json.loads(info_path.read_text(encoding="utf-8"))
                    data["can_modify"] = can_modify_subject(user, cfg, data)
                    data["phase_reviews"] = _subject_phase_reviews(code, sd)
                    result.append(data)
                except Exception:
                    pass
    return result


@router.post("", status_code=201)
async def create_subject(code: str, body: SubjectCreate, request: Request):
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    sid = validate_storage_id(body.subject_id, "受试者ID")

    sd = subject_dir(code, sid)
    if sd.exists():
        raise HTTPException(
            status_code=409,
            detail=f"Subject '{sid}' already exists in project '{code}'",
        )

    sd.mkdir(parents=True, exist_ok=True)
    (sd / "raw").mkdir(exist_ok=True)
    (sd / "cache").mkdir(exist_ok=True)
    (sd / "llm").mkdir(exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    center_code = normalize_center_code(body.center_code)
    center_name = normalize_center_name(body.center_name)
    if center_code or center_name:
        upsert_center(None, center_code, center_name, user["username"])

    info = SubjectInfo(
        subject_id=sid,
        project_code=code,
        owner_username=user["username"],
        center_code=center_code,
        center_name=center_name,
        status=SubjectStatus.PENDING.value,
        doc_count=0,
        last_updated=now,
    )
    save_subject_info(sd, info)
    log_audit(code, "create_subject", user["username"], subject_id=sid, center_code=center_code, center_name=center_name)
    return asdict(info)


@router.get("/{sid}")
async def get_subject(code: str, sid: str, request: Request):
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    sd = ensure_subject(code, sid)
    info = load_subject_info(sd)
    d = asdict(info)
    d["can_modify"] = can_modify_subject(user, cfg, info)
    d["files"] = list_files_in_dir(sd / "raw")
    d["has_bundle"] = (sd / "evidence_bundle.md").exists()
    d["has_report"] = (sd / "llm" / "review_report.md").exists()
    d["phase_reviews"] = _subject_phase_reviews(code, sd)
    return d


@router.patch("/{sid}")
async def update_subject(code: str, sid: str, body: SubjectUpdate, request: Request):
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    sd = ensure_subject(code, sid)
    info = load_subject_info(sd)
    require_subject_modify(user, cfg, info)

    fields = getattr(body, "model_fields_set", None)
    if fields is None:
        fields = getattr(body, "__fields_set__", set())
    if "center_code" in fields:
        info.center_code = normalize_center_code(body.center_code or "")
    if "center_name" in fields:
        info.center_name = normalize_center_name(body.center_name or "")
    if ("center_code" in fields or "center_name" in fields) and (info.center_code or info.center_name):
        upsert_center(None, info.center_code, info.center_name, user["username"])
    if "screening_date" in fields:
        info.screening_date = normalize_date_text(body.screening_date or "")
    if "icf_date" in fields:
        info.icf_date = normalize_date_text(body.icf_date or "")
        info.icf_date_manual = bool(info.icf_date)
    if "phase_anchor_dates" in fields:
        current = dict(info.phase_anchor_dates or {})
        for raw_phase_id, raw_date in (body.phase_anchor_dates or {}).items():
            phase_id = validate_storage_id(str(raw_phase_id or ""), "审核阶段ID")
            date_text = normalize_date_text(str(raw_date or ""))
            if date_text:
                current[phase_id] = date_text
            else:
                current.pop(phase_id, None)
        info.phase_anchor_dates = current

    info.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_subject_info(sd, info)
    log_audit(code, "update_subject", user["username"], subject_id=sid)
    data = asdict(info)
    data["can_modify"] = can_modify_subject(user, cfg, info)
    data["phase_reviews"] = _subject_phase_reviews(code, sd)
    return data


@router.delete("/{sid}")
async def delete_subject(code: str, sid: str, request: Request):
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    sd = ensure_subject(code, sid)
    require_subject_modify(user, cfg, load_subject_info(sd))
    shutil.rmtree(sd)
    log_audit(code, "delete_subject", user["username"], subject_id=sid)
    return {"status": "deleted", "subject_id": sid}


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

@router.post("/{sid}/reset")
async def reset_subject(code: str, sid: str, request: Request):
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    sd = ensure_subject(code, sid)
    info = load_subject_info(sd)
    require_subject_modify(user, cfg, info)
    info.status = "pending"
    save_subject_info(sd, info)
    log_audit(code, "reset_subject_status", user["username"], subject_id=sid)
    return {"status": "reset", "subject_id": sid}


@router.post("/{sid}/reset-cache")
async def reset_cache(code: str, sid: str, request: Request):
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    sd = ensure_subject(code, sid)
    info = load_subject_info(sd)
    require_subject_modify(user, cfg, info)
    clear_subject_outputs(sd, info)
    log_audit(code, "reset_subject_ocr", user["username"], subject_id=sid)
    return {"status": "cache_cleared", "subject_id": sid}


@router.post("/{sid}/rerun")
async def rerun_subject(code: str, sid: str, request: Request):
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    sd = ensure_subject(code, sid)
    info = load_subject_info(sd)
    require_subject_modify(user, cfg, info)
    clear_subject_outputs(sd, info)
    log_audit(code, "rerun_subject_prepare", user["username"], subject_id=sid)
    return {"status": "ready_to_rerun", "subject_id": sid}


@router.post("/{sid}/upload")
async def upload_files(
    code: str,
    sid: str,
    request: Request,
    files: List[UploadFile] = File(...),
    categories: List[str] = Form([]),
    center_code: str = Form(""),
    center_name: str = Form(""),
):
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    sd = ensure_subject(code, sid)
    info = load_subject_info(sd)
    require_subject_modify(user, cfg, info)
    raw_dir = sd / "raw"
    raw_dir.mkdir(exist_ok=True)

    saved = []
    cat_path = sd / "file_categories.json"
    cat_map = {}
    if cat_path.exists():
        try:
            import json
            loaded = json.loads(cat_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cat_map = {str(k): str(v) for k, v in loaded.items()}
        except Exception:
            cat_map = {}
    for i, upload in enumerate(files):
        if not upload.filename:
            continue
        dest = _safe_upload_destination(raw_dir, upload.filename)
        content = await upload.read()
        from app.config import MAX_UPLOAD_SIZE
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail=f"文件 '{upload.filename}' 超过最大上传限制 ({MAX_UPLOAD_SIZE // 1024 // 1024}MB)")
        dest.write_bytes(content)
        cat = categories[i] if i < len(categories) else "unknown"
        saved.append({"name": dest.name, "original_name": upload.filename, "size": len(content), "category": cat})
        cat_map[dest.name] = cat

    current_files = {
        f.name for f in raw_dir.iterdir()
        if f.is_file() and not f.name.startswith(".")
    }
    cat_map = {name: cat for name, cat in cat_map.items() if name in current_files}

    # Save category mapping for bundler
    import json
    cat_path.write_text(json.dumps(cat_map, ensure_ascii=False, indent=2))

    normalized_center_code = normalize_center_code(center_code)
    normalized_center_name = normalize_center_name(center_name)
    if normalized_center_code or normalized_center_name:
        info.center_code = normalized_center_code
        info.center_name = normalized_center_name
        upsert_center(None, normalized_center_code, normalized_center_name, user["username"])
    if not info.owner_username:
        info.owner_username = user["username"]
    info.doc_count = len(current_files)
    if saved and info.status in {SubjectStatus.REVIEWED.value, SubjectStatus.ERROR.value}:
        info.status = SubjectStatus.PENDING.value
        info.overall_verdict = ""
    info.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_subject_info(sd, info)
    log_audit(
        code,
        "upload_files",
        user["username"],
        subject_id=sid,
        file_count=len(saved),
        filenames=[item["name"] for item in saved],
    )

    return {"status": "uploaded", "files": saved, "doc_count": info.doc_count}
