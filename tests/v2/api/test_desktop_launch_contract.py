"""The double-click entry must serve the current product, not the legacy app."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.v2.desktop import create_desktop_app


def test_desktop_serves_product_and_identifies_its_worktree(data_paths, tmp_path):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    html = b"<!doctype html><title>\xe5\x85\xa5\xe6\x8e\x92\xe5\xae\xa1\xe6\xa0\xb8</title>"
    (frontend / "index.html").write_bytes(html)
    (frontend / "product-build.json").write_text(json.dumps({
        "version": "enrollment-product-build/v1",
        "interface_trial": False,
        "protocol_stub": False,
        "api_base": "",
        "asset_base": "/",
        "files": {"index.html": hashlib.sha256(html).hexdigest()},
    }), encoding="utf-8")

    app = create_desktop_app(frontend_dir=frontend, data_paths=data_paths)
    with TestClient(app) as client:
        status = client.get("/api/v2/application-status")
        assert status.status_code == 200
        assert status.json() == {
            "mode": "standard",
            "can_modify": True,
            "service": "enrollment-review-v2-desktop",
            "instance_root": str(Path(__file__).resolve().parents[3]),
        }
        assert client.get("/").content == html
        assert client.get("/api/not-a-route").status_code == 404
