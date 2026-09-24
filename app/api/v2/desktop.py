"""Serve the prebuilt React application and V2 API from one local origin."""
from pathlib import Path

from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles

from app.services.desktop_frontend import require_product_frontend
from app.services.evidence_app_bootstrap import DataPaths


def create_desktop_app(*, frontend_dir: Path, data_paths: DataPaths, browse_only: bool = False):
    directory = require_product_frontend(frontend_dir)
    if browse_only:
        from app.api.v2.browse import create_browse_app
        app = create_browse_app(data_paths=data_paths)
    else:
        from app.api.v2.app import create_app
        app = create_app(data_paths=data_paths)
        app.state.desktop_root = str(Path(__file__).resolve().parents[3])

    # Unknown API paths must not be answered by an HTML/asset fallback.
    @app.api_route("/api/{path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    def unknown_api(path: str):
        raise HTTPException(status_code=404, detail="找不到该操作，请刷新后重试。")

    app.mount("/", StaticFiles(directory=directory, html=True), name="desktop")
    return app
