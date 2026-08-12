"""Project management + criteria rules + protocol deconstruction endpoints."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.config import MAX_UPLOAD_SIZE, PROJECTS_DIR
from app.shared import ensure_project, project_dir, projects
from app.models import ProjectConfig
from app.phases import load_review_workflow
from app.centers import (
    centers_to_markdown,
    load_centers,
    normalize_center_record,
    normalize_centers,
    parse_centers_from_excel_bytes,
    parse_centers_from_text,
    save_centers,
)
from app.markdown_export import generate_markdown_report
from app.audit import log_audit
from app.shared import validate_storage_id
from app.authz import (
    can_access_project,
    can_modify_subject,
    can_modify_project,
    current_user,
    is_admin,
    require_project_access,
    require_project_modify,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    project_code: str
    protocol_id: str
    name: str = ""


class ProjectUpdate(BaseModel):
    project_code: Optional[str] = None
    protocol_id: Optional[str] = None
    name: Optional[str] = None
    protocol_version: Optional[str] = None
    protocol_date: Optional[str] = None
    protocol_source_filename: Optional[str] = None
    study_stage: Optional[str] = None


class CentersSaveRequest(BaseModel):
    centers: list[dict] = []


def _rule_headings(text: str) -> list[str]:
    return [
        m.group(1).strip()
        for m in re.finditer(r"^#{3,5}\s+(.+)$", text or "", flags=re.MULTILINE)
        if re.search(r"\b(?:IN|EX|INC|EXC)[-_]?\d+", m.group(1), flags=re.I)
    ]


def _summarize_rule_changes(old_rules: str, new_rules: str) -> list[str]:
    old_headings = _rule_headings(old_rules)
    new_headings = _rule_headings(new_rules)
    old_set = set(old_headings)
    new_set = set(new_headings)
    changes = []
    added = [h for h in new_headings if h not in old_set]
    removed = [h for h in old_headings if h not in new_set]
    if added:
        changes.append("新增规则/条目：" + "；".join(added[:20]))
    if removed:
        changes.append("删除或未保留规则/条目：" + "；".join(removed[:20]))
    if len(old_headings) != len(new_headings):
        changes.append(f"规则标题数量变化：原 {len(old_headings)} 条，新 {len(new_headings)} 条。")
    if old_rules.strip() == new_rules.strip():
        changes.append("规则正文未检测到变化。")
    elif not added and not removed:
        changes.append("规则标题基本一致，但正文判断点、通过/不通过条件或流程核查说明存在修订，请逐条复核高风险条目。")
    return changes


def _safe_upload_filename(filename: str | None) -> str:
    original = str(filename or "protocol").strip()
    if "/" in original or "\\" in original:
        raise HTTPException(status_code=400, detail="方案文件名不能包含路径分隔符")
    name = Path(original).name.strip()
    if name in {"", ".", ".."} or ".." in name:
        raise HTTPException(status_code=400, detail="方案文件名不合法")
    suffix = Path(name).suffix.lower()
    if suffix and suffix not in {".docx", ".doc", ".pdf", ".txt"}:
        raise HTTPException(status_code=400, detail="方案文件仅支持 .docx、.doc、.pdf、.txt")
    return name or "protocol"


def _safe_project_code(value: str) -> str:
    code = re.sub(r"[^A-Za-z0-9_.-]+", "-", (value or "").strip()).strip("-_.")
    return code or "PROJECT"


def _unique_project_code(base_code: str) -> str:
    base = _safe_project_code(base_code)
    code = base
    idx = 2
    while code in projects or project_dir(code).exists():
        code = f"{base}_{idx}"
        idx += 1
    return code


def _study_stage_code_suffix(study_stage: str) -> str:
    stage = _normalize_study_stage_label(study_stage)
    if stage == "Ⅱ期":
        return "II"
    if stage == "Ⅲ期":
        return "III"
    return ""


def _project_code_base_for_stage(metadata: dict, workflow: dict | None = None) -> str:
    """Use study phase as part of project identity for multi-phase protocols."""
    base = _safe_project_code(metadata.get("project_code", "PROJECT"))
    stage = _normalize_study_stage_label(metadata.get("study_stage", ""))
    stages = (workflow or {}).get("protocol_study_stages") or (workflow or {}).get("study_stages") or []
    if not stage or len(stages) <= 1:
        return base
    suffix = _study_stage_code_suffix(stage)
    if not suffix:
        return base
    if re.search(rf"(?:^|[-_.]){re.escape(suffix)}$", base, flags=re.I):
        return base
    return f"{base}-{suffix}"


def _project_scoped_workflow(workflow: dict | None, selected_stage: str = "") -> dict:
    """Persist workflow as project-scoped after a phase has been selected."""
    if not workflow:
        return {}
    scoped = dict(workflow)
    stage = _normalize_study_stage_label(selected_stage)
    if stage:
        protocol_stages = workflow.get("protocol_study_stages") or workflow.get("study_stages") or []
        scoped["protocol_study_stages"] = protocol_stages
        scoped["study_stage"] = stage
        scoped["study_stages"] = [stage]
        scoped["requires_study_stage_selection"] = False
        stage_phases = [
            phase for phase in (workflow.get("review_phases") or [])
            if not phase.get("study_stage") or _normalize_study_stage_label(phase.get("study_stage", "")) == stage
        ]
        if stage_phases:
            normalized_phases = []
            for phase in stage_phases:
                item = dict(phase)
                item["study_stage"] = stage
                normalized_phases.append(item)
            scoped["review_phases"] = normalized_phases
    return scoped


def _sanitize_deconstructed_rules_header(rules: str, metadata: dict, selected_stage: str = "") -> str:
    """Replace LLM-generated protocol metadata with system-extracted metadata."""
    body = str(rules or "").strip()
    if body.startswith("---"):
        end = body.find("\n---", 3)
        if end != -1:
            body = body[end + len("\n---"):].lstrip()
    project_code = str(metadata.get("project_code") or "PROJECT").strip()
    protocol_id = str(metadata.get("protocol_id") or "").strip()
    version = str(metadata.get("protocol_version") or "").strip()
    protocol_date = str(metadata.get("protocol_date") or "").strip()
    stage = _normalize_study_stage_label(selected_stage)
    heading = f"# {project_code} 入排审核规则"
    body = re.sub(r"^#\s+.*?入排审核规则\s*$", heading, body, count=1, flags=re.MULTILINE)
    if not body.startswith("#"):
        body = heading + "\n\n" + body
    front_matter = [
        "---",
        f"项目代号: {project_code}",
        f"方案编号: {protocol_id}",
    ]
    if version or protocol_date:
        front_matter.append(f"方案版本/日期: {version}/{protocol_date}".rstrip("/"))
    if stage:
        front_matter.append(f"解构期别: {stage}")
    front_matter.append("---")
    return "\n".join(front_matter) + "\n\n" + body.rstrip() + "\n"


def _write_project_record(cfg: ProjectConfig) -> None:
    pd = project_dir(cfg.project_code)
    pd.mkdir(parents=True, exist_ok=True)
    (pd / "subjects").mkdir(exist_ok=True)

    (pd / "config.json").write_text(
        json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    rules_path = pd / "criteria_rules.md"
    if not rules_path.exists():
        rules_path.write_text(
            f"# {cfg.project_code} 入排标准\n\n## 入选标准\n\n## 排除标准\n",
            encoding="utf-8",
        )

    projects[cfg.project_code] = cfg


def _update_subject_project_codes(pd: Path, new_code: str) -> None:
    subjects_dir = pd / "subjects"
    if not subjects_dir.exists():
        return
    for info_path in subjects_dir.glob("*/info.json"):
        try:
            data = json.loads(info_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        data["project_code"] = new_code
        info_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _center_key(center: dict) -> str:
    rec = normalize_center_record(center) or {}
    return rec.get("center_code") or rec.get("center_name") or ""


def _center_can_modify(user: dict | None, center: dict) -> bool:
    if is_admin(user):
        return True
    owner = str(center.get("owner_username") or "")
    return bool(user and owner and owner == user.get("username"))


def _decorate_centers_for_user(centers: list[dict], user: dict | None) -> list[dict]:
    decorated = []
    for center in centers:
        item = dict(center)
        item["can_modify"] = _center_can_modify(user, item)
        decorated.append(item)
    return decorated


def _merge_center_save(existing: list[dict], incoming: list[dict], user: dict | None) -> list[dict]:
    incoming_norm = normalize_centers(incoming)
    existing_by_key = {_center_key(c): c for c in existing if _center_key(c)}
    incoming_by_key = {_center_key(c): c for c in incoming_norm if _center_key(c)}
    final: list[dict] = []

    for key, old in existing_by_key.items():
        new = incoming_by_key.pop(key, None)
        if new is None:
            if _center_can_modify(user, old):
                continue
            final.append(old)
            continue
        if not _center_can_modify(user, old):
            old_name = str(old.get("center_name") or "")
            new_name = str(new.get("center_name") or "")
            if old_name != new_name:
                raise HTTPException(status_code=403, detail=f"无权修改中心 {old.get('label') or key}")
            final.append(old)
            continue
        new["owner_username"] = old.get("owner_username") or user.get("username", "")
        final.append(new)

    for new in incoming_by_key.values():
        new["owner_username"] = user.get("username", "") if user else ""
        final.append(new)
    return normalize_centers(final)


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

@router.get("")
async def list_projects(request: Request):
    user = current_user(request)
    result = []
    for code, cfg in projects.items():
        if not can_access_project(user, cfg):
            continue
        d = cfg.to_dict()
        d["can_delete"] = can_modify_project(user, cfg)
        d["can_modify"] = can_modify_project(user, cfg)
        d["center_count"] = len(load_centers(project_dir(code)))
        subjects_dir = project_dir(code) / "subjects"
        stats = {
            "pass": 0,
            "pass_verify": 0,
            "fail": 0,
            "insufficient": 0,
            "investigator": 0,
            "pending": 0,
            "error": 0,
        }
        if subjects_dir.exists():
            subject_dirs = [x for x in subjects_dir.iterdir() if x.is_dir()]
            d["subject_count"] = len(subject_dirs)
            for sd in subject_dirs:
                info_path = sd / "info.json"
                try:
                    info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
                except Exception:
                    info = {}
                verdict = str(info.get("overall_verdict") or "")
                status = str(info.get("status") or "")
                if verdict in stats:
                    stats[verdict] += 1
                elif status == "error":
                    stats["error"] += 1
                else:
                    stats["pending"] += 1
        else:
            d["subject_count"] = 0
        stats["attention"] = stats["insufficient"] + stats["investigator"]
        stats["pending_total"] = stats["pending"] + stats["error"] + stats["attention"]
        d["stats"] = stats
        result.append(d)
    return result


@router.post("", status_code=201)
async def create_project(body: ProjectCreate, request: Request):
    user = current_user(request)
    code = validate_storage_id(body.project_code, "项目编号")
    if code in projects:
        raise HTTPException(status_code=409, detail=f"Project '{code}' already exists")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cfg = ProjectConfig(
        project_code=code,
        protocol_id=body.protocol_id.strip(),
        name=body.name.strip(),
        criteria_rules_path="criteria_rules.md",
        created_at=now,
        owner_username=user["username"],
    )

    _write_project_record(cfg)
    log_audit(code, "create_project", user["username"])
    return cfg.to_dict()


@router.get("/{code}")
async def get_project(code: str, request: Request):
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    d = cfg.to_dict()
    d["can_delete"] = can_modify_project(user, cfg)
    d["can_modify"] = can_modify_project(user, cfg)
    d["centers"] = _decorate_centers_for_user(load_centers(None), user)
    d["center_count"] = len(d["centers"])

    subjects_dir = project_dir(code) / "subjects"
    subject_list = []
    if subjects_dir.exists():
        for sd in sorted(subjects_dir.iterdir()):
            if not sd.is_dir():
                continue
            info_path = sd / "info.json"
            if info_path.exists():
                try:
                    data = json.loads(info_path.read_text(encoding="utf-8"))
                    data["can_modify"] = can_modify_subject(user, cfg, data)
                    subject_list.append(data)
                except Exception:
                    pass
    d["subjects"] = subject_list
    d["subject_count"] = len(subject_list)
    return d


@router.patch("/{code}")
async def update_project_info(code: str, body: ProjectUpdate, request: Request):
    """Update editable project metadata; owner/admin only."""
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    require_project_modify(user, cfg)

    old_code = cfg.project_code
    new_code = _safe_project_code(body.project_code if body.project_code is not None else old_code)
    if not new_code:
        raise HTTPException(status_code=400, detail="项目编号不能为空")
    old_pd = project_dir(old_code)
    target_pd = project_dir(new_code)
    if new_code != old_code and (new_code in projects or target_pd.exists()):
        raise HTTPException(status_code=409, detail=f"项目编号 {new_code} 已存在")

    if body.protocol_id is not None:
        cfg.protocol_id = body.protocol_id.strip()
    if body.name is not None:
        cfg.name = body.name.strip()
    if body.protocol_version is not None:
        cfg.protocol_version = body.protocol_version.strip()
    if body.protocol_date is not None:
        cfg.protocol_date = body.protocol_date.strip()
    if body.protocol_source_filename is not None:
        cfg.protocol_source_filename = body.protocol_source_filename.strip()
    if body.study_stage is not None:
        cfg.study_stage = body.study_stage.strip()

    if new_code != old_code:
        cfg.project_code = new_code
        if old_pd.exists():
            old_pd.rename(target_pd)
        projects.pop(old_code, None)
        _update_subject_project_codes(target_pd, new_code)
    _write_project_record(cfg)
    log_audit(cfg.project_code, "update_project", user["username"], old_project_code=old_code)

    data = cfg.to_dict()
    data["can_delete"] = can_modify_project(user, cfg)
    data["can_modify"] = can_modify_project(user, cfg)
    data["centers"] = _decorate_centers_for_user(load_centers(None), user)
    data["old_project_code"] = old_code
    return data


@router.get("/{code}/phases")
async def get_project_phases(code: str, request: Request):
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    pd = project_dir(code)
    rules_path = pd / "criteria_rules.md"
    rules_text = rules_path.read_text(encoding="utf-8") if rules_path.exists() else ""
    return load_review_workflow(pd, rules_text)


@router.delete("/{code}")
async def delete_project(code: str, request: Request):
    import shutil
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    require_project_modify(user, cfg)
    pd = project_dir(code)
    log_audit(code, "delete_project", user["username"])
    if pd.exists():
        shutil.rmtree(pd)
    del projects[code]
    return {"status": "deleted", "project_code": code}


# ---------------------------------------------------------------------------
# Center roster
# ---------------------------------------------------------------------------

@router.get("/{code}/centers")
async def get_centers(code: str, request: Request):
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    centers = _decorate_centers_for_user(load_centers(None), user)
    return {"project_code": code, "centers": centers, "count": len(centers)}


@router.put("/{code}/centers")
async def update_centers(code: str, body: CentersSaveRequest, request: Request):
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    existing = load_centers(None, include_subjects=False)
    merged = _merge_center_save(existing, body.centers, user)
    centers = save_centers(None, merged)
    log_audit(code, "update_centers", user["username"], center_count=len(centers))
    return {"status": "saved", "project_code": code, "centers": _decorate_centers_for_user(centers, user), "count": len(centers)}


@router.post("/{code}/centers/deconstruct")
async def deconstruct_centers(
    code: str,
    request: Request,
    file: Optional[UploadFile] = File(None),
    draft_text: str = Form(""),
    feedback: str = Form(""),
):
    """Parse an Excel/text center roster into an editable draft."""
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)

    centers: list[dict] = []
    warnings: list[str] = []
    if file is not None:
        content = await file.read()
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail=f"文件超过最大上传限制 ({MAX_UPLOAD_SIZE // 1024 // 1024}MB)")
        try:
            centers.extend(parse_centers_from_excel_bytes(content, file.filename or ""))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"中心名单解构失败: {exc}")
    if draft_text.strip():
        centers.extend(parse_centers_from_text(draft_text))
    if feedback.strip():
        parsed_feedback = parse_centers_from_text(feedback)
        centers.extend(parsed_feedback)
        if not parsed_feedback:
            warnings.append("反馈已记录，但未从反馈文字中识别到新的中心代号/名称行；请在草稿表格中直接修改后保存。")
    centers = normalize_centers([*load_centers(None, include_subjects=False), *centers]) if centers else load_centers(None, include_subjects=False)
    if file is not None or draft_text.strip() or feedback.strip():
        try:
            from app.llm.client import deconstruct_chat
            prompt = (
                "你是临床试验中心名单整理助手。请根据已有草稿和用户评论，输出规范Markdown表格，"
                "只保留两列：中心代号、中心名称。中心代号如为数字请保留两位，例如6写作06。"
                "不要输出解释。\n\n"
                f"## 已解析草稿\n{centers_to_markdown(centers)}\n\n"
                f"## 用户评论/补充\n{feedback or '无'}\n\n"
                f"## 用户粘贴原文\n{draft_text[:4000] if draft_text else '无'}"
            )
            llm_text = await deconstruct_chat(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2048,
            )
            llm_centers = parse_centers_from_text(llm_text)
            if llm_centers:
                centers = normalize_centers([*load_centers(None, include_subjects=False), *llm_centers])
        except Exception as exc:
            warnings.append(f"LLM修订未完成，已保留结构化解构草稿：{exc}")
    for center in centers:
        if not center.get("owner_username") and _center_key(center) not in {_center_key(c) for c in load_centers(None, include_subjects=False)}:
            center["owner_username"] = user.get("username", "")
    return {
        "status": "parsed",
        "project_code": code,
        "centers": _decorate_centers_for_user(centers, user),
        "draft_markdown": centers_to_markdown(centers),
        "count": len(centers),
        "warnings": warnings,
    }


@router.get("/{code}/reports/markdown")
async def export_project_markdown_report(
    code: str,
    request: Request,
    scope: str = Query("project"),
    phase: str = Query("full"),
    center_code: str = Query(""),
    subject_id: str = Query(""),
):
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    scope = (scope or "project").strip().lower()
    if scope not in {"project", "center", "subject"}:
        raise HTTPException(status_code=400, detail="scope 必须是 project、center 或 subject")
    if scope == "center" and not center_code.strip():
        raise HTTPException(status_code=400, detail="按中心导出时必须选择中心")
    if scope == "subject" and not subject_id.strip():
        raise HTTPException(status_code=400, detail="按个人导出时必须选择受试者")

    text = generate_markdown_report(
        project_path=project_dir(code),
        project=cfg.to_dict(),
        scope=scope,
        phase=phase,
        center_code=center_code.strip(),
        subject_id=subject_id.strip(),
    )
    filename_parts = [cfg.project_code, scope]
    if center_code.strip():
        filename_parts.append(center_code.strip())
    if subject_id.strip():
        filename_parts.append(subject_id.strip())
    filename_parts.append(datetime.now().strftime("%Y%m%d%H%M%S"))
    filename = "_".join(filename_parts) + ".md"
    return HTMLResponse(
        content=text,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Criteria rules
# ---------------------------------------------------------------------------

@router.get("/{code}/rules")
async def get_rules(code: str, request: Request):
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    rules_path = project_dir(code) / "criteria_rules.md"
    if not rules_path.exists():
        return {"rules": ""}
    return {"rules": rules_path.read_text(encoding="utf-8")}


@router.post("/{code}/rules")
async def update_rules(code: str, body: dict, request: Request):
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    require_project_modify(user, cfg)
    rules = body.get("rules", "")
    rules_path = project_dir(code) / "criteria_rules.md"
    rules_path.write_text(rules, encoding="utf-8")
    log_audit(code, "update_rules", user["username"], char_count=len(rules))
    return {"status": "updated"}


# ---------------------------------------------------------------------------
# Protocol deconstruction
# ---------------------------------------------------------------------------

from app.deconstructor import (  # noqa: E402
    DECONSTRUCT_PROMPT,
    extract_docx_criteria,
    extract_docx_protocol_workflow,
    extract_protocol_metadata,
    extract_protocol_text,
    _is_generic_protocol_title,
    _normalize_study_stage_label,
    render_protocol_workflow_markdown,
    sanitize_selected_stage_scope_language,
    strengthen_compound_condition_summaries,
    strip_outer_markdown_fence,
)


def _resolve_deconstruct_study_stage(workflow: dict, study_stage: str = "") -> str:
    """Validate and normalize the deconstruction study-stage selection."""
    selected = _normalize_study_stage_label(study_stage)
    stages = workflow.get("study_stages") or []
    if workflow.get("requires_study_stage_selection") and not selected:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "study_stage_required",
                "message": "方案同时包含Ⅱ期和Ⅲ期，请先选择本次解构Ⅱ期还是Ⅲ期。",
                "study_stages": stages,
            },
        )
    if selected and stages and selected not in stages:
        raise HTTPException(
            status_code=400,
            detail=f"所选研究阶段 {selected} 不在方案识别阶段中：{'、'.join(stages)}",
        )
    return selected


def _project_display_name(metadata: dict, code: str) -> str:
    name = str(metadata.get("name") or "").strip()
    if not name or _is_generic_protocol_title(name):
        return code
    return name


@router.post("/{code}/deconstruct")
async def deconstruct_protocol(
    code: str,
    request: Request,
    file: UploadFile = File(...),
    feedback: str = Form(""),
    study_stage: str = Form(""),
):
    """Upload a protocol document and deconstruct eligibility criteria using LLM."""
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    require_project_modify(user, cfg)

    pd = project_dir(code)
    filename = _safe_upload_filename(file.filename)
    temp_path = pd / f"_protocol_{filename}"
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail=f"文件超过最大上传限制 ({MAX_UPLOAD_SIZE // 1024 // 1024}MB)")
    temp_path.write_bytes(content)

    try:
        result = await _deconstruct_protocol_path(temp_path, feedback, output_dir=pd, study_stage=study_stage)
        log_audit(code, "deconstruct_protocol", user["username"], source_filename=filename, study_stage=result.get("study_stage", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Protocol deconstruction failed: %s", e)
        raise HTTPException(status_code=500, detail=f"方案解构失败: {str(e)}")


@router.post("/from-protocol", status_code=201)
async def create_project_from_protocol(
    request: Request,
    file: UploadFile = File(...),
    feedback: str = Form(""),
    study_stage: str = Form(""),
):
    """Create a project directly from an uploaded protocol document."""
    user = current_user(request)
    filename = _safe_upload_filename(file.filename)
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail=f"文件超过最大上传限制 ({MAX_UPLOAD_SIZE // 1024 // 1024}MB)")

    tmp_root = PROJECTS_DIR / ".tmp_protocol_uploads"
    tmp_dir = tmp_root / datetime.now().strftime("%Y%m%d%H%M%S%f")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / filename
    tmp_path.write_bytes(content)

    try:
        metadata = extract_protocol_metadata(str(tmp_path))
        metadata["protocol_source_filename"] = filename
        workflow = {}
        if tmp_path.suffix.lower() in (".docx", ".doc"):
            workflow = extract_docx_protocol_workflow(str(tmp_path))
        resolved_stage = _resolve_deconstruct_study_stage(workflow, study_stage)
        if resolved_stage:
            metadata["study_stage"] = resolved_stage
    except Exception as exc:
        logger.error("Protocol metadata extraction failed: %s", exc)
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(status_code=400, detail=f"方案元信息提取失败: {exc}")
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    code = _unique_project_code(_project_code_base_for_stage(metadata, workflow))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cfg = ProjectConfig(
        project_code=code,
        protocol_id=metadata.get("protocol_id", ""),
        name=_project_display_name(metadata, code),
        protocol_version=metadata.get("protocol_version", ""),
        protocol_date=metadata.get("protocol_date", ""),
        protocol_source_filename=filename,
        study_stage=metadata.get("study_stage", ""),
        criteria_rules_path="criteria_rules.md",
        created_at=now,
        owner_username=user["username"],
    )
    _write_project_record(cfg)
    log_audit(code, "create_project_from_protocol", user["username"], source_filename=filename, study_stage=cfg.study_stage)

    pd = project_dir(code)
    protocol_path = pd / f"_protocol_{filename}"
    protocol_path.write_bytes(content)

    response = {
        "status": "created",
        "project_code": code,
        "project": cfg.to_dict(),
        "metadata": metadata,
    }
    try:
        deconstruct_result = await _deconstruct_protocol_path(
            protocol_path,
            feedback,
            output_dir=pd,
            study_stage=study_stage,
        )
        resolved_stage = deconstruct_result.get("study_stage", "")
        if resolved_stage:
            cfg.study_stage = resolved_stage
            _write_project_record(cfg)
            response["project"] = cfg.to_dict()
        response.update({
            "status": "success",
            "deconstruction": deconstruct_result,
            "rules": deconstruct_result.get("rules", ""),
            "workflow": deconstruct_result.get("workflow"),
        })
    except Exception as exc:
        logger.exception("Project created but protocol deconstruction failed: %s", exc)
        response["deconstruct_error"] = str(exc)
    return response


@router.post("/deconstruct-draft")
async def deconstruct_protocol_draft(
    request: Request,
    file: UploadFile = File(...),
    feedback: str = Form(""),
    current_rules: str = Form(""),
    study_stage: str = Form(""),
):
    """Deconstruct a protocol into an editable draft without creating a project."""
    current_user(request)
    filename = _safe_upload_filename(file.filename)
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail=f"文件超过最大上传限制 ({MAX_UPLOAD_SIZE // 1024 // 1024}MB)")

    tmp_root = PROJECTS_DIR / ".tmp_protocol_uploads"
    tmp_dir = tmp_root / datetime.now().strftime("%Y%m%d%H%M%S%f")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / filename
    tmp_path.write_bytes(content)
    try:
        metadata = extract_protocol_metadata(str(tmp_path))
        metadata["protocol_source_filename"] = filename
        result = await _deconstruct_protocol_path(
            tmp_path,
            feedback,
            current_rules=current_rules,
            study_stage=study_stage,
        )
        result["metadata"] = metadata
        if result.get("study_stage"):
            result["metadata"]["study_stage"] = result["study_stage"]
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Protocol draft deconstruction failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"方案解构失败: {exc}")
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.post("/save-protocol-draft", status_code=201)
async def save_protocol_draft(
    request: Request,
    file: Optional[UploadFile] = File(None),
    rules: str = Form(...),
    metadata_json: str = Form("{}"),
    workflow_json: str = Form("{}"),
    target_project_code: str = Form(""),
):
    """Save an edited protocol deconstruction draft into a new or existing project."""
    user = current_user(request)
    try:
        metadata = json.loads(metadata_json or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"metadata_json 格式错误: {exc}")
    try:
        workflow = json.loads(workflow_json or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"workflow_json 格式错误: {exc}")

    if target_project_code:
        cfg = ensure_project(target_project_code)
        require_project_access(user, cfg)
        require_project_modify(user, cfg)
        code = cfg.project_code
        if metadata.get("protocol_id"):
            cfg.protocol_id = metadata.get("protocol_id", cfg.protocol_id)
        new_name = _project_display_name(metadata, code)
        if new_name:
            cfg.name = new_name
        cfg.protocol_version = metadata.get("protocol_version", cfg.protocol_version)
        cfg.protocol_date = metadata.get("protocol_date", cfg.protocol_date)
        cfg.protocol_source_filename = metadata.get("protocol_source_filename", cfg.protocol_source_filename)
        cfg.study_stage = metadata.get("study_stage", cfg.study_stage)
    else:
        code = _unique_project_code(_project_code_base_for_stage(metadata, workflow))
        cfg = ProjectConfig(
            project_code=code,
            protocol_id=metadata.get("protocol_id", ""),
            name=_project_display_name(metadata, code),
            protocol_version=metadata.get("protocol_version", ""),
            protocol_date=metadata.get("protocol_date", ""),
            protocol_source_filename=metadata.get("protocol_source_filename", ""),
            study_stage=metadata.get("study_stage", ""),
            criteria_rules_path="criteria_rules.md",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            owner_username=user["username"],
        )

    _write_project_record(cfg)
    pd = project_dir(code)
    (pd / "criteria_rules.md").write_text(rules, encoding="utf-8")
    if file is not None:
        filename = _safe_upload_filename(file.filename)
        content = await file.read()
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail=f"文件超过最大上传限制 ({MAX_UPLOAD_SIZE // 1024 // 1024}MB)")
        protocol_copy = pd / f"_protocol_{filename}"
        protocol_copy.write_bytes(content)
        cfg.protocol_source_filename = filename
        _write_project_record(cfg)
        if not workflow and protocol_copy.suffix.lower() in (".docx", ".doc"):
            try:
                workflow = extract_docx_protocol_workflow(str(protocol_copy))
            except Exception as exc:
                logger.warning("save-protocol-draft workflow extraction failed: %s", exc)

    if workflow:
        workflow = _project_scoped_workflow(workflow, cfg.study_stage)
        (pd / "review_phases.json").write_text(
            json.dumps(workflow, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    log_audit(code, "save_protocol_draft", user["username"], target_project_code=target_project_code, workflow_saved=bool(workflow), rules_char_count=len(rules))
    return {
        "status": "saved",
        "project_code": code,
        "project": cfg.to_dict(),
        "rules_char_count": len(rules),
        "workflow_saved": bool(workflow),
    }


@router.post("/{code}/deconstruct-revision")
async def deconstruct_project_revision(
    code: str,
    request: Request,
    file: Optional[UploadFile] = File(None),
    feedback: str = Form(""),
    current_rules: str = Form(""),
    use_current_protocol: str = Form("true"),
    study_stage: str = Form(""),
):
    """Draft a revised protocol deconstruction for an existing project."""
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    require_project_modify(user, cfg)
    pd = project_dir(code)
    old_rules_path = pd / "criteria_rules.md"
    old_rules = old_rules_path.read_text(encoding="utf-8") if old_rules_path.exists() else ""
    base_rules = current_rules or old_rules

    temp_path = None
    if file is not None:
        filename = _safe_upload_filename(file.filename)
        content = await file.read()
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail=f"文件超过最大上传限制 ({MAX_UPLOAD_SIZE // 1024 // 1024}MB)")
        tmp_root = PROJECTS_DIR / ".tmp_protocol_uploads"
        tmp_dir = tmp_root / datetime.now().strftime("%Y%m%d%H%M%S%f")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = tmp_dir / filename
        temp_path.write_bytes(content)
    else:
        candidates = sorted(pd.glob("_protocol_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates or use_current_protocol.lower() not in {"true", "1", "yes"}:
            raise HTTPException(status_code=400, detail="请上传新方案，或选择基于项目已保存方案修订")
        temp_path = candidates[0]
        tmp_dir = None

    try:
        metadata = extract_protocol_metadata(str(temp_path))
        result = await _deconstruct_protocol_path(
            temp_path,
            feedback,
            current_rules=base_rules,
            study_stage=study_stage or cfg.study_stage,
        )
        new_rules = result.get("rules", "")
        result.update({
            "metadata": metadata,
            "original_rules": old_rules,
            "changes": _summarize_rule_changes(old_rules, new_rules),
            "source": "uploaded_protocol" if file is not None else "current_project_protocol",
        })
        if result.get("study_stage"):
            result["metadata"]["study_stage"] = result["study_stage"]
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Project protocol revision failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"重新解构失败: {exc}")
    finally:
        if file is not None and temp_path is not None:
            import shutil
            shutil.rmtree(temp_path.parent, ignore_errors=True)


async def _deconstruct_protocol_path(
    protocol_path: Path,
    feedback: str = "",
    output_dir: Path | None = None,
    current_rules: str = "",
    study_stage: str = "",
) -> dict:
    suffix = protocol_path.suffix.lower()

    criteria_text = ""
    pre_info = ""
    workflow = {}

    if suffix in (".docx", ".doc"):
        try:
            workflow = extract_docx_protocol_workflow(str(protocol_path))
        except Exception as e:
            logger.warning("DOCX workflow extraction failed: %s", e)
            workflow = {}

        selected_stage = _resolve_deconstruct_study_stage(workflow, study_stage)
        try:
            extracted = extract_docx_criteria(str(protocol_path), selected_stage)
            pre_info = f"## 预提取结构信息\n\n入选标准：{extracted['inclusion_count']}条\n排除标准：{extracted['exclusion_count']}条\n\n"
            criteria_text = f"""## 入选标准（已从文档编号结构提取，共{extracted['inclusion_count']}条）
{extracted['inclusion_text']}

## 排除标准（已从文档编号结构提取，共{extracted['exclusion_count']}条）
{extracted['exclusion_text']}
"""
        except Exception as e:
            logger.warning("DOCX structure extraction failed: %s, falling back to plain text", e)
    else:
        selected_stage = _normalize_study_stage_label(study_stage)

    workflow_for_project = _project_scoped_workflow(workflow, selected_stage)
    if output_dir and workflow_for_project.get("review_phases"):
        (output_dir / "review_phases.json").write_text(
            json.dumps(workflow_for_project, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if not criteria_text:
        try:
            criteria_text = extract_protocol_text(str(protocol_path))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    if len(criteria_text.strip()) < 100:
        raise HTTPException(status_code=400, detail="文档内容过少")

    current_rules_block = ""
    if current_rules:
        current_rules_block = f"\n\n## 当前解构草案（请在此基础上修订，不要丢失已有人工编辑）\n\n{current_rules}"
    feedback_block = ""
    if feedback:
        feedback_block = f"\n\n## 用户反馈（请根据以下反馈修正解构结果）\n{feedback}"
    stage_block = ""
    if selected_stage:
        stage_block = (
            f"\n\n## 本次解构范围\n"
            f"用户已选择本次只解构：{selected_stage}。\n"
            f"请把{selected_stage}视为一个独立项目的规则集，只使用{selected_stage}对应的父级编号、条款范围和审核节点。\n"
            f"另一期别不得进入正式IN/EX规则，不得用于比较，不得输出一致/差异说明，也不得写“仅{selected_stage}”“适用期别：{selected_stage}”等选择动作产生的标签。\n"
        )

    fixed_len = len(pre_info) + len(current_rules_block) + len(feedback_block) + len(stage_block) + 2000
    criteria_budget = max(20000, 80000 - fixed_len)
    if len(criteria_text) > criteria_budget:
        criteria_text = criteria_text[:criteria_budget] + "\n\n[方案正文过长，已截断；当前草稿与用户反馈已优先保留...]"

    user_msg = f"{pre_info}以下是研究方案的入选排除标准内容：\n\n{criteria_text}"
    user_msg += stage_block
    if current_rules:
        user_msg += current_rules_block
    if feedback:
        user_msg += feedback_block

    if len(user_msg) > 80000:
        user_msg = user_msg[:80000] + "\n\n[内容过长，已截断...]"

    from app.llm.client import deconstruct_chat

    messages = [
        {"role": "system", "content": DECONSTRUCT_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    result = await deconstruct_chat(messages)
    criteria_rules = result if isinstance(result, str) else ""
    criteria_rules = strip_outer_markdown_fence(criteria_rules)
    criteria_rules = sanitize_selected_stage_scope_language(criteria_rules, selected_stage, workflow)
    criteria_rules = strengthen_compound_condition_summaries(criteria_rules)
    workflow_md = render_protocol_workflow_markdown(workflow, selected_stage)
    if workflow_md and "基线及以前方案流程核查" not in criteria_rules:
        criteria_rules = criteria_rules.rstrip() + "\n\n---\n\n" + workflow_md + "\n"
    try:
        protocol_metadata = extract_protocol_metadata(str(protocol_path))
    except Exception:
        protocol_metadata = {}
    criteria_rules = _sanitize_deconstructed_rules_header(criteria_rules, protocol_metadata, selected_stage)

    if output_dir:
        rules_path = output_dir / "criteria_rules.md"
        rules_path.write_text(criteria_rules, encoding="utf-8")

    return {
        "status": "success",
        "rules": criteria_rules,
        "char_count": len(criteria_rules),
        "pre_extracted": pre_info if pre_info else None,
        "workflow": workflow_for_project if workflow_for_project else None,
        "study_stage": selected_stage,
    }
