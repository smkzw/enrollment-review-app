"""V2 方案解构 API 集成测试。"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.services.protocol_workbench_service import (
    PROTOCOL_DECONSTRUCTION_JOB_TYPE,
    PROTOCOL_DECONSTRUCTION_STEPS,
    ProtocolWorkbenchService,
)
from app.services.job_service import JobService
from tests.v2.protocols.slice4_helpers import confirmed_fixture


def _minimal_docx_bytes() -> bytes:
    path = Path("/tmp/protocol-api-test.docx")
    doc = Document()
    doc.add_paragraph("临床研究方案")
    doc.add_paragraph("方案编号：TEST-001")
    doc.save(str(path))
    return path.read_bytes()


def _create_protocol_job(client: TestClient, *, key: str = "proto-key-1") -> str:
    files = {
        "file": (
            "test-protocol.docx",
            io.BytesIO(_minimal_docx_bytes()),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    data = {"idempotency_key": key, "actor": "测试用户"}
    response = client.post("/api/v2/protocol/deconstructions", files=files, data=data)
    assert response.status_code == 201, response.text
    return response.json()["job_id"]


def _seed_review_job(app, job_id: str) -> tuple:
    source_input, draft, spans = confirmed_fixture()
    service: ProtocolWorkbenchService = app.state.protocol_workbench_service
    service.seed_review_session(job_id, source_input=source_input, draft=draft, source_spans=spans)
    return source_input, draft


def test_upload_registers_source_and_creates_protocol_job(client) -> None:
    job_id = _create_protocol_job(client, key="upload-1")
    session = client.get(f"/api/v2/protocol/deconstructions/{job_id}")
    assert session.status_code == 200
    body = session.json()
    assert body["job_type"] == PROTOCOL_DECONSTRUCTION_JOB_TYPE
    assert body["file_name"] == "test-protocol.docx"
    assert body["source_artifact_id"]
    assert body["progress_total"] == len(PROTOCOL_DECONSTRUCTION_STEPS)
    assert body["progress_completed"] >= 1


def test_upload_idempotent_same_key(client) -> None:
    files = {
        "file": (
            "test-protocol.docx",
            io.BytesIO(_minimal_docx_bytes()),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    data = {"idempotency_key": "upload-dup", "actor": "测试用户"}
    first = client.post("/api/v2/protocol/deconstructions", files=files, data=data)
    second = client.post("/api/v2/protocol/deconstructions", files=files, data=data)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["job_id"] == first.json()["job_id"]
    assert second.json()["created"] is False


def test_missing_job_returns_chinese_envelope(client) -> None:
    response = client.get("/api/v2/protocol/deconstructions/does-not-exist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["title"] == "任务不存在"
    assert "correlation_id" in error


def test_draft_integrity_and_sources_after_seed(client, build_app) -> None:
    app = build_app()
    with TestClient(app) as test_client:
        job_id = _create_protocol_job(test_client, key="seed-review-1")
        _seed_review_job(app, job_id)

        draft = test_client.get(f"/api/v2/protocol/deconstructions/{job_id}/draft")
        assert draft.status_code == 200
        draft_body = draft.json()
        assert draft_body["revision_number"] == 1
        assert draft_body["rule_count"] == 2
        assert draft_body["status_label"] == "已保存"
        assert "content" in draft_body

        integrity = test_client.get(f"/api/v2/protocol/deconstructions/{job_id}/integrity")
        assert integrity.status_code == 200
        integrity_body = integrity.json()
        assert integrity_body["publishable"] is True
        assert integrity_body["blocking_count"] == 0
        assert integrity_body["summary"]

        sources = test_client.get(f"/api/v2/protocol/deconstructions/{job_id}/sources")
        assert sources.status_code == 200
        sources_body = sources.json()
        assert sources_body["selected_phase_label"] == "II 期"
        assert sources_body["source_materials"]

        session = test_client.get(f"/api/v2/protocol/deconstructions/{job_id}")
        assert session.status_code == 200
        assert session.json()["draft_revision_number"] == 1
        assert session.json()["awaiting_user"] == "review"


def test_save_draft_is_idempotent(client, build_app) -> None:
    app = build_app()
    with TestClient(app) as test_client:
        job_id = _create_protocol_job(test_client, key="save-draft-1")
        _seed_review_job(app, job_id)
        draft = test_client.get(f"/api/v2/protocol/deconstructions/{job_id}/draft").json()
        response = test_client.post(
            f"/api/v2/protocol/deconstructions/{job_id}/draft/save",
            json={"expected_revision_id": draft["revision_id"]},
        )
        assert response.status_code == 200
        assert response.json()["status_label"] == "已保存"


def test_publish_first_project(client, build_app) -> None:
    app = build_app()
    with TestClient(app) as test_client:
        job_id = _create_protocol_job(test_client, key="publish-1")
        _seed_review_job(app, job_id)
        draft = test_client.get(f"/api/v2/protocol/deconstructions/{job_id}/draft").json()
        response = test_client.post(
            f"/api/v2/protocol/deconstructions/{job_id}/publish",
            json={"idempotency_key": "pub-key-1", "actor": "医学监查员"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["project_id"]
        assert body["rule_set_revision"] == 1
        assert body["replay"] is False

        replay = test_client.post(
            f"/api/v2/protocol/deconstructions/{job_id}/publish",
            json={"idempotency_key": "pub-key-1", "actor": "医学监查员"},
        )
        assert replay.status_code == 200
        assert replay.json()["replay"] is True


def test_identity_not_ready_before_pipeline(client) -> None:
    job_id = _create_protocol_job(client, key="identity-wait-1")
    response = client.get(f"/api/v2/protocol/deconstructions/{job_id}/identity")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "IDENTITY_NOT_READY"
    assert error["recovery_action"]


def test_draft_not_ready_before_review(client) -> None:
    job_id = _create_protocol_job(client, key="draft-wait-1")
    response = client.get(f"/api/v2/protocol/deconstructions/{job_id}/draft")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] in {"DRAFT_NOT_READY", "STATE_CONFLICT", "STEP_STATE_CONFLICT"}
    assert error["title"]
    assert error["recovery_action"]
