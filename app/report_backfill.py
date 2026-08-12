"""Utilities for reparsing persisted review reports after verdict logic changes."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from app.models import ReviewReport, SubjectStatus
from app.phases import phase_llm_dir
from app.pipeline.reviewer import parse_review_response
from app.shared import load_subject_info, save_subject_info


def _load_report_text(report_dir: Path) -> tuple[str, Path | None, Path | None]:
    report_path = report_dir / "review_report.md"
    raw_path = report_dir / "review_raw.md"
    if raw_path.exists():
        return raw_path.read_text(encoding="utf-8"), report_path, raw_path
    if report_path.exists():
        return report_path.read_text(encoding="utf-8"), report_path, None
    return "", None, None


def backfill_subject_report(
    subject_dir: Path,
    *,
    project_code: str,
    phase: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Reparse one subject report and rewrite the normalized Markdown/info verdict."""
    report_dir = phase_llm_dir(subject_dir, phase)
    text, report_path, raw_path = _load_report_text(report_dir)
    subject_id = subject_dir.name
    if not text:
        return {
            "subject_id": subject_id,
            "status": "skipped",
            "reason": "missing_report",
            "old_overall": "",
            "new_overall": "",
        }

    parsed = parse_review_response(text)
    new_overall = parsed.get("overall_verdict", "")
    old_overall = ""
    try:
        info = load_subject_info(subject_dir)
        old_overall = info.overall_verdict
    except Exception:
        info = None

    report = ReviewReport(
        subject_id=subject_id,
        project_code=project_code,
        overall_verdict=new_overall,
        summary=parsed.get("summary", ""),
        rule_results=parsed.get("rule_results", []),
        group_results=parsed.get("group_results", []),
        model_used="backfill:parse_review_response",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    new_markdown = report.to_markdown()
    old_markdown = report_path.read_text(encoding="utf-8") if report_path and report_path.exists() else ""
    changed = old_overall != new_overall or old_markdown != new_markdown

    if not dry_run:
        report_dir.mkdir(parents=True, exist_ok=True)
        target_report = report_path or (report_dir / "review_report.md")
        target_report.write_text(new_markdown, encoding="utf-8")
        if info is not None:
            info.overall_verdict = new_overall
            if info.status != SubjectStatus.PROCESSING.value:
                info.status = SubjectStatus.REVIEWED.value
            info.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_subject_info(subject_dir, info)

    return {
        "subject_id": subject_id,
        "status": "updated" if changed else "unchanged",
        "old_overall": old_overall,
        "new_overall": new_overall,
        "report_path": str(report_path or (report_dir / "review_report.md")),
        "raw_path": str(raw_path) if raw_path else "",
    }


def backfill_project_reports(
    project_path: Path,
    *,
    project_code: str = "",
    phase: str = "full",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Reparse every subject report for a project and return a compact summary."""
    project_path = Path(project_path)
    project_code = project_code or project_path.name
    subjects_root = project_path / "subjects"
    results: list[Dict[str, Any]] = []
    if not subjects_root.exists():
        return {"project_code": project_code, "phase": phase, "updated": 0, "skipped": 0, "subjects": []}

    for subject_dir in sorted(p for p in subjects_root.iterdir() if p.is_dir()):
        result = backfill_subject_report(
            subject_dir,
            project_code=project_code,
            phase=phase,
            dry_run=dry_run,
        )
        results.append(result)

    return {
        "project_code": project_code,
        "phase": phase,
        "dry_run": dry_run,
        "updated": sum(1 for r in results if r.get("status") == "updated"),
        "unchanged": sum(1 for r in results if r.get("status") == "unchanged"),
        "skipped": sum(1 for r in results if r.get("status") == "skipped"),
        "subjects": results,
    }
