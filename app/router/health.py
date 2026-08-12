"""Health check and statistics endpoints."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter

from app.shared import projects, project_dir

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check():
    """Check oMLX and DeepSeek connectivity."""
    from app.llm.client import check_omlx, check_deepseek

    omlx_ok, deepseek_ok = await asyncio.gather(
        check_omlx(),
        check_deepseek(),
        return_exceptions=True,
    )

    return {
        "service": "enrollment-review-app",
        "version": "2.0.0",
        "status": "ok",
        "omlx": bool(omlx_ok) if not isinstance(omlx_ok, Exception) else False,
        "deepseek": bool(deepseek_ok) if not isinstance(deepseek_ok, Exception) else False,
    }


@router.get("/stats")
async def get_stats():
    """Return overall statistics."""
    total_projects = len(projects)
    total_subjects = 0
    status_counts = {}
    verdict_counts = {}

    for code in projects:
        subjects_dir = project_dir(code) / "subjects"
        if not subjects_dir.exists():
            continue
        for sd in sorted(subjects_dir.iterdir()):
            if not sd.is_dir():
                continue
            info_path = sd / "info.json"
            if info_path.exists():
                try:
                    data = json.loads(info_path.read_text(encoding="utf-8"))
                    total_subjects += 1
                    status = data.get("status", "pending")
                    status_counts[status] = status_counts.get(status, 0) + 1
                    verdict = data.get("overall_verdict", "")
                    if verdict:
                        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
                except Exception:
                    pass

    return {
        "total_projects": total_projects,
        "total_subjects": total_subjects,
        "status_counts": status_counts,
        "verdict_counts": verdict_counts,
    }
