"""The double-click entry must serve the current product, not the legacy app."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.v2.desktop import create_desktop_app


def test_browse_reads_saved_local_job_without_execution_or_writes(data_paths, session_factory, monkeypatch):
    from app.api.v2.browse import create_browse_app
    from app.evidence.artifacts import ArtifactStore
    from app.llm.independent_vlm import IndependentVlmChatResult
    from app.services.local_visual_verification import (
        LOCAL_VISUAL_JOB_TYPE, LocalVisualRegionRequest,
        LocalVisualVerificationService, create_local_visual_executor,
    )
    from app.workflow.runner import JobRunner
    from tests.v2.services.test_local_visual_job import _seed

    seeded = _seed(session_factory, data_paths)
    store = ArtifactStore(data_paths)
    service = LocalVisualVerificationService(session_factory, store)
    calls = []

    async def read(prompt, pages, **kwargs):
        calls.append(1)
        return IndependentVlmChatResult(text=f"source_ref={pages[0].source_ref}\n字迹清楚，尚未采用。",
                                       model="fixture-model", finish_reason="stop", usage={})

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", read)
    job = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"],
                          LocalVisualRegionRequest(x0=3, y0=4, x1=30, y1=40))
    assert JobRunner(session_factory, {
        LOCAL_VISUAL_JOB_TYPE: create_local_visual_executor(session_factory, store),
    }).run_job(job["job_id"])
    before = hashlib.sha256(data_paths.db_path.read_bytes()).hexdigest()

    def no_model(*args, **kwargs):
        raise AssertionError("Browsing must not call a model")

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", no_model)
    monkeypatch.setattr("app.llm.independent_vlm.get_independent_vlm_client", no_model)
    path = f"/api/v2/evidence-processing-revisions/{seeded['revision_id']}/pages/{seeded['page_artifact_id']}/local-verification"
    with TestClient(create_browse_app(data_paths=data_paths)) as client:
        result = client.get(path, params={"job_id": job["job_id"]})
        assert result.status_code == 200
        body = result.json()
        assert body["state"] == "completed" and body["candidate_only"] is True
        assert body["observation_text"] == "字迹清楚，尚未采用。"
        assert client.post(path, json={"x0": 3, "y0": 4, "x1": 30, "y1": 40}).status_code == 403
        assert client.post(f"/api/v2/jobs/{job['job_id']}/retry").status_code == 403
        assert client.post(f"/api/v2/jobs/{job['job_id']}/cancel").status_code == 403
        assert client.get(path, params={"job_id": "wrong-job"}).status_code == 409
    assert hashlib.sha256(data_paths.db_path.read_bytes()).hexdigest() == before
    assert calls == [1]


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
