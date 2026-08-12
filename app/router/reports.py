"""Report and evidence endpoints — JSON/Markdown reports, bundle, evidence chunks."""

from __future__ import annotations

import re as _re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from app.shared import (
    ensure_project, ensure_subject, load_subject_info, project_dir,
)
from app.phases import load_review_workflow, phase_bundle_path, phase_llm_dir
from app.authz import current_user, require_project_access

router = APIRouter(prefix="/api/projects/{code}/subjects/{sid}", tags=["reports"])


def _child_parent_rule_id(rule_id: str) -> str:
    match = _re.match(r"^((?:IN|EX)-\d+)[A-Za-z].*$", rule_id or "")
    return match.group(1) if match else ""


def _default_report_phase(code: str) -> str:
    pd = project_dir(code)
    rules_path = pd / "criteria_rules.md"
    rules_text = rules_path.read_text(encoding="utf-8") if rules_path.exists() else ""
    workflow = load_review_workflow(pd, rules_text)
    for phase in workflow.get("review_phases") or []:
        phase_id = phase.get("phase_id")
        if phase_id and phase_id != "full":
            return phase_id
    phases = workflow.get("review_phases") or []
    return phases[0].get("phase_id", "full") if phases else "full"


@router.get("/report")
async def get_report_json(code: str, sid: str, request: Request, phase: str = Query("full")):
    """Get review report as structured JSON."""
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    sd = ensure_subject(code, sid)

    report_dir = phase_llm_dir(sd, phase)
    report_path = report_dir / "review_report.md"
    raw_path = report_dir / "review_raw.md"
    if phase == "full" and not report_path.exists() and not raw_path.exists():
        phase = _default_report_phase(code)
        report_dir = phase_llm_dir(sd, phase)
        report_path = report_dir / "review_report.md"
        raw_path = report_dir / "review_raw.md"

    if not report_path.exists() and not raw_path.exists():
        raise HTTPException(status_code=404, detail="Report not found. Run review first.")

    result = {
        "subject_id": sid,
        "project_code": code,
        "review_phase": phase,
    }

    raw_text = ""
    report_text = ""
    if raw_path.exists():
        raw_text = raw_path.read_text(encoding="utf-8")
        result["raw_response"] = raw_text
    if report_path.exists():
        report_text = report_path.read_text(encoding="utf-8")
        result["report_markdown"] = report_text

    parse_text = report_text or raw_text
    if parse_text:
        from app.pipeline.reviewer import (
            is_future_phase_verify_reasoning,
            is_source_traceability_verify_reasoning,
            parse_review_response,
        )
        parsed = parse_review_response(parse_text)
        result["verdict"] = parsed["overall_verdict"]
        result["summary"] = parsed["summary"]
        result["rule_results"] = [
            {
                "rule_id": r.rule_id,
                "rule_name": r.rule_name,
                "rule_type": r.rule_type,
                "result": r.verdict,
                "verification_type": (
                    "future_phase" if r.verdict == "pass_verify" and is_future_phase_verify_reasoning(r.reasoning)
                    else "source_traceability" if r.verdict == "pass_verify" and is_source_traceability_verify_reasoning(r.reasoning)
                    else "other" if r.verdict == "pass_verify"
                    else ""
                ),
                "reasoning": r.reasoning,
                "parent_rule_id": _child_parent_rule_id(r.rule_id),
                "is_child_rule": bool(_child_parent_rule_id(r.rule_id)),
                "is_parent_rule": any(_child_parent_rule_id(child.rule_id) == r.rule_id for child in parsed["rule_results"]),
                "hierarchy_level": 1 if _child_parent_rule_id(r.rule_id) else 0,
            }
            for r in parsed["rule_results"]
        ]
        result["group_results"] = [
            {
                "group_id": g.group_id,
                "result": g.verdict,
                "satisfied_members": g.satisfied_members,
                "summary": g.explanation,
            }
            for g in parsed["group_results"]
        ]

    # Include evidence bundle chunks for evidence viewer
    bundle_path = phase_bundle_path(sd, phase)
    if bundle_path.exists():
        bundle_text = bundle_path.read_text(encoding="utf-8")
        if report_path.exists():
            result["report_markdown"] = report_path.read_text(encoding="utf-8")
        chunks = []
        for m in _re.finditer(r"### (【.+?】.+?)$", bundle_text, _re.MULTILINE):
            chunk_header = m.group(1).strip()
            cid_match = _re.search(r"(ck_\d+)", chunk_header)
            chunk_id = cid_match.group(1) if cid_match else ""
            source = chunk_header
            start = m.end()
            next_m = _re.search(r"\n### |^---$", bundle_text[start:], _re.MULTILINE)
            end = start + next_m.start() if next_m else len(bundle_text)
            content = bundle_text[start:end].strip()
            chunks.append({"chunk_id": chunk_id, "source": source, "text": content})
        result["chunks"] = chunks

    try:
        info = load_subject_info(sd)
        result["status"] = info.status
        if not result.get("verdict"):
            result["verdict"] = info.overall_verdict
    except Exception:
        pass

    return result


@router.get("/report/md")
async def get_report_markdown(code: str, sid: str, request: Request, phase: str = Query("full")):
    """Get review report as markdown."""
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    sd = ensure_subject(code, sid)

    report_path = phase_llm_dir(sd, phase) / "review_report.md"
    if phase == "full" and not report_path.exists():
        phase = _default_report_phase(code)
        report_path = phase_llm_dir(sd, phase) / "review_report.md"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not found. Run review first.")

    return HTMLResponse(
        content=report_path.read_text(encoding="utf-8"),
        media_type="text/plain; charset=utf-8",
    )


@router.get("/bundle")
async def get_bundle(code: str, sid: str, request: Request, phase: str = Query("full")):
    """Get evidence bundle as markdown."""
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    sd = ensure_subject(code, sid)

    bundle_path = phase_bundle_path(sd, phase)
    if phase == "full" and not bundle_path.exists():
        phase = _default_report_phase(code)
        bundle_path = phase_bundle_path(sd, phase)
    if not bundle_path.exists():
        raise HTTPException(status_code=404, detail="Evidence bundle not found. Run OCR first.")

    return HTMLResponse(
        content=bundle_path.read_text(encoding="utf-8"),
        media_type="text/plain; charset=utf-8",
    )


@router.get("/evidence/{chunk_id}")
async def get_evidence_chunk(code: str, sid: str, chunk_id: str, request: Request, phase: str = Query("full")):
    """Get a specific evidence chunk by chunk_id (e.g. ck_0001)."""
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    sd = ensure_subject(code, sid)

    bundle_path = phase_bundle_path(sd, phase)
    if not bundle_path.exists():
        raise HTTPException(status_code=404, detail="Evidence bundle not found")

    bundle_text = bundle_path.read_text(encoding="utf-8")
    pattern = rf"(### .*?片段{_re.escape(chunk_id)}\)(?:.*?))(?=### |\Z)"
    match = _re.search(pattern, bundle_text, _re.DOTALL)
    if not match:
        raise HTTPException(status_code=404, detail=f"Chunk '{chunk_id}' not found")

    return {
        "chunk_id": chunk_id,
        "content": match.group(1).strip(),
    }
