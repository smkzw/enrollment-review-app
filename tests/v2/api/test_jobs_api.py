"""V2 Job API 集成测试：创建/幂等/状态/取消/重试与中文错误信封。

路由只做协议转换；本组覆盖 HTTP 状态码、幂等语义与错误信封形状，
不泄露实现术语（错误信封不含 SQL/堆栈/枚举值）。
"""
from __future__ import annotations

import pytest

from tests.v2.api.conftest import create_job_body


@pytest.mark.parametrize("legacy_stale_error", [False, True])
def test_recovered_status_reports_success_and_keeps_the_failed_attempt(client, legacy_stale_error):
    from datetime import timedelta
    from app.storage.codecs import utc_now
    from app.storage.models import JobRecord
    from app.workflow.jobstore import JobStore

    response = client.post("/api/v2/jobs", json=create_job_body(key="recovered-status", steps=[
        {"step_id": "s1", "name": "解析", "retryable": True, "max_attempts": 2},
        {"step_id": "s2", "name": "审核", "depends_on": ["s1"]},
    ]))
    job_id = response.json()["job_id"]
    now = [utc_now()]
    sessions = client.app.state.session_factory
    with sessions() as session, session.begin():
        store = JobStore(session, now=lambda: now[0])
        lease = store.claim_job(job_id, "test-worker")
        store.start_step(lease, "s1")
        store.fail_step(lease, "s1", retryable=True, error_code="E_TRANSIENT")
    assert client.get(f"/api/v2/jobs/{job_id}").json()["error_code"] == "E_TRANSIENT"
    now[0] += timedelta(seconds=1)
    with sessions() as session, session.begin():
        store = JobStore(session, now=lambda: now[0])
        assert store.requeue_due_retries() == [job_id]
        lease = store.claim_job(job_id, "test-worker")
        for step in ("s1", "s2"):
            store.start_step(lease, step)
            store.complete_step(lease, step, checkpoint_payload={"step": step})
        store.finish_success(lease)
        saved = store.get_job(job_id)
        assert saved.error_code is None and saved.error_classification is None
        if legacy_stale_error:
            saved.error_code, saved.error_classification = "E_TRANSIENT", "retryable"
    body = client.get(f"/api/v2/jobs/{job_id}").json()
    assert body["state"] == "completed" and body["error_code"] is None and body["error_classification"] is None
    failed = [event for event in body["events"] if event["event_type"] == "step_failed"]
    assert len(failed) == 1 and failed[0]["payload"]["error_code"] == "E_TRANSIENT"
    assert body["retryable_scope"] == []
    with sessions() as session:
        saved = session.get(JobRecord, job_id)
        assert saved.error_code == ("E_TRANSIENT" if legacy_stale_error else None)


def test_create_job_returns_201_and_queued(client) -> None:
    resp = client.post("/api/v2/jobs", json=create_job_body())
    assert resp.status_code == 201
    body = resp.json()
    assert body["job_id"]
    assert body["state"] == "queued"
    assert body["state_label"] == "等待处理"
    assert body["created"] is True


def test_validation_error_identifies_field_in_natural_chinese(client) -> None:
    body = create_job_body()
    body["idempotency_key"] = "x" * 257
    response = client.post("/api/v2/jobs", json=body)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_REQUEST"
    assert error["context"] == {
        "fields": [{"field": "重复提交标识", "issue": "内容过长"}]
    }
    assert "idempotency_key" not in str(error)


def test_create_job_idempotent_same_key_same_content(client) -> None:
    first = client.post("/api/v2/jobs", json=create_job_body(key="dup-1"))
    assert first.status_code == 201
    second = client.post("/api/v2/jobs", json=create_job_body(key="dup-1"))
    assert second.status_code == 200
    assert second.json()["job_id"] == first.json()["job_id"]
    assert second.json()["created"] is False
    # 只产生一个任务
    status = client.get(f"/api/v2/jobs/{first.json()['job_id']}")
    assert status.status_code == 200


def test_different_jobs_may_reuse_the_same_step_ids(client) -> None:
    first = client.post("/api/v2/jobs", json=create_job_body(key="shared-steps-1"))
    second = client.post("/api/v2/jobs", json=create_job_body(key="shared-steps-2"))
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["job_id"] != second.json()["job_id"]
    for job_id in (first.json()["job_id"], second.json()["job_id"]):
        status = client.get(f"/api/v2/jobs/{job_id}").json()
        assert [step["step_id"] for step in status["steps"]] == ["s1", "s2"]


def test_dependencies_can_be_declared_before_their_prerequisite(client) -> None:
    steps = [
        {"step_id": "s2", "name": "审核", "depends_on": ["s1"]},
        {"step_id": "s1", "name": "解析", "depends_on": []},
    ]
    response = client.post(
        "/api/v2/jobs", json=create_job_body(key="reverse-order", steps=steps)
    )
    assert response.status_code == 201
    status = client.get(f"/api/v2/jobs/{response.json()['job_id']}").json()
    by_id = {step["step_id"]: step for step in status["steps"]}
    assert by_id["s2"]["depends_on"] == ["s1"]


@pytest.mark.parametrize(
    "steps",
    [
        [
            {"step_id": "s1", "name": "解析", "depends_on": ["missing"]},
        ],
        [
            {"step_id": "s1", "name": "解析", "depends_on": ["s2"]},
            {"step_id": "s2", "name": "审核", "depends_on": ["s1"]},
        ],
        [
            {"step_id": "s1", "name": "解析", "depends_on": []},
            {"step_id": "s1", "name": "重复", "depends_on": []},
        ],
    ],
)
def test_invalid_dependency_graph_is_rejected_before_job_creation(client, steps) -> None:
    response = client.post(
        "/api/v2/jobs", json=create_job_body(key="invalid-graph", steps=steps)
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_JOB_DEFINITION"
    assert error["title"] == "任务步骤设置不完整"


def test_create_job_same_key_different_content_conflicts(client) -> None:
    client.post("/api/v2/jobs", json=create_job_body(key="conflict-1", payload={"a": 1}))
    resp = client.post("/api/v2/jobs", json=create_job_body(key="conflict-1", payload={"a": 2}))
    assert resp.status_code == 409
    error = resp.json()["error"]
    assert error["code"] == "IDEMPOTENCY_CONFLICT"
    assert "重复提交内容不一致" == error["title"]
    assert error["recovery_action"]


def test_get_status_returns_snapshot_with_steps_and_events(client) -> None:
    created = client.post("/api/v2/jobs", json=create_job_body()).json()
    resp = client.get(f"/api/v2/jobs/{created['job_id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == created["job_id"]
    assert body["job_type"] == "demo"
    assert body["progress_total"] == 2
    assert body["progress_completed"] == 0
    assert [s["step_id"] for s in body["steps"]] == ["s1", "s2"]
    assert body["steps"][1]["depends_on"] == ["s1"]
    assert [e["event_type"] for e in body["events"]] == ["created"]
    assert body["last_event_seq"] == 1
    assert body["recovery_action"]
    assert body["created_at"].endswith(("Z", "+00:00"))
    assert body["updated_at"].endswith(("Z", "+00:00"))
    assert body["events"][0]["occurred_at"].endswith(("Z", "+00:00"))


def test_cancel_queued_job(client) -> None:
    created = client.post("/api/v2/jobs", json=create_job_body()).json()
    resp = client.post(f"/api/v2/jobs/{created['job_id']}/cancel")
    assert resp.status_code == 200
    assert resp.json()["state"] == "cancelled"
    assert resp.json()["changed"] is True
    status = client.get(f"/api/v2/jobs/{created['job_id']}")
    assert status.json()["state"] == "cancelled"


def test_retry_non_failed_job_is_state_conflict(client) -> None:
    created = client.post("/api/v2/jobs", json=create_job_body()).json()
    resp = client.post(f"/api/v2/jobs/{created['job_id']}/retry")
    assert resp.status_code == 409
    error = resp.json()["error"]
    assert error["code"] == "JOB_STATE_CONFLICT"
    assert error["title"] == "任务状态不允许该操作"


def test_unknown_job_returns_404_not_found(client) -> None:
    for method, path in [
        ("get", "/api/v2/jobs/missing"),
        ("post", "/api/v2/jobs/missing/cancel"),
        ("post", "/api/v2/jobs/missing/retry"),
        ("get", "/api/v2/jobs/missing/events"),
    ]:
        resp = getattr(client, method)(path)
        assert resp.status_code == 404, (method, path)
        error = resp.json()["error"]
        assert error["code"] == "NOT_FOUND"
        assert error["title"] == "任务不存在"


def test_validation_error_has_chinese_envelope(client) -> None:
    resp = client.post("/api/v2/jobs", json={"job_type": "demo"})  # 缺少 idempotency_key
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "INVALID_REQUEST"
    assert error["title"] == "请求参数不合法"
    assert error["recovery_action"]


def test_step_extra_fields_rejected(client) -> None:
    body = create_job_body()
    body["steps"][0]["unknown_field"] = 1
    resp = client.post("/api/v2/jobs", json=body)
    assert resp.status_code == 422
