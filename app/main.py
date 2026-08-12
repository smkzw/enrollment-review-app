"""Main FastAPI application — thin entry point.

Serves the SPA frontend, aggregates routers, and handles startup initialization.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi import Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import HOST, PORT, PROJECTS_DIR, STATIC_DIR
from app.shared import projects, project_dir
from app.router import (
    health_router,
    auth_router,
    projects_router,
    subjects_router,
    pipeline_router,
    reports_router,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="临床试验入排审核系统",
    description="Clinical trial enrollment review system with OCR + LLM pipeline",
    version="2.0.0",
)

# Include all routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(subjects_router)
app.include_router(pipeline_router)
app.include_router(reports_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
async def startup():
    """Initialize: create projects directory, load existing projects, reset stale processing."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Projects directory: %s", PROJECTS_DIR)

    loaded = 0
    reset_count = 0
    for d in sorted(PROJECTS_DIR.iterdir()):
        if not d.is_dir():
            continue
        from app.models import ProjectConfig
        config_path = d / "config.json"
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                cfg = ProjectConfig.from_dict(data)
                projects[cfg.project_code] = cfg
                loaded += 1
            except Exception as exc:
                logger.warning("Failed to load project %s: %s", d.name, exc)

        subjects_dir = d / "subjects"
        if subjects_dir.exists():
            for sd in subjects_dir.iterdir():
                if not sd.is_dir():
                    continue
                info_path = sd / "info.json"
                if info_path.exists():
                    try:
                        info = json.loads(info_path.read_text(encoding="utf-8"))
                        if info.get("status") == "processing":
                            info["status"] = "pending"
                            info_path.write_text(
                                json.dumps(info, ensure_ascii=False, indent=4),
                                encoding="utf-8",
                            )
                            reset_count += 1
                            logger.info("Reset stale processing subject: %s/%s", d.name, sd.name)
                    except Exception:
                        pass

    logger.info("Loaded %d existing projects, reset %d stale subjects", loaded, reset_count)


# ---------------------------------------------------------------------------
# Frontend serving
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def serve_index():
    """Serve the SPA frontend."""
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index, media_type="text/html")
    return HTMLResponse(
        "<h1>入排审核系统</h1><p>Frontend not found. Place index.html in static/</p>"
    )


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Avoid noisy browser 404s for the default favicon request."""
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
