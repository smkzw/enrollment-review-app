"""V2 Job SSE 订阅：断线重连、事件补齐、无重复、不乱序、断开不改任务。

- 事件序号 ``(job_id, seq)`` 单调唯一，``after_seq`` 续订无损补齐；
- 关闭订阅只结束生成器，不修改任务、不持有取消权（design.md §6）。
"""
from __future__ import annotations

import pytest

from app.api.v2.jobs import _sse_stream
from tests.v2.api.conftest import (
    claim_and_complete_step,
    complete_step_and_finish,
    create_job_body,
    parse_sse_frames,
)


def _stream(service, job_id: str, after_seq: int = 0):
    return _sse_stream(
        service,
        job_id,
        after_seq=after_seq,
        poll_interval=0.005,
        heartbeat_seconds=0.05,
    )


def test_sse_reconnect_after_disconnect_replays_without_duplicates(build_app, client):
    """断线后用 after_seq 重连：补齐缺失事件、不重复、不乱序、断开不改变任务。"""
    created = client.post("/api/v2/jobs", json=create_job_body()).json()
    job_id = created["job_id"]
    app = client.app
    sf = app.state.session_factory
    service = app.state.job_service

    # 先驱动 s1 完成（seq 1..3：created/step_started(s1)/step_completed(s1)），
    # 任务仍在运行、s2 排队 —— 给断开留出「非终态」窗口。
    lease = claim_and_complete_step(sf, job_id, "s1")

    # 第一段订阅：从头读到 s1 完成事件后断开（停止消费生成器）。
    seen: list[tuple[int, str]] = []
    for chunk in _stream(service, job_id, after_seq=0):
        for seq, event, _data in parse_sse_frames([chunk]):
            if seq is not None:
                seen.append((seq, event))
        if len(seen) >= 3:
            break
    assert seen == [(1, "created"), (2, "step_started"), (3, "step_completed")]

    # 断开后任务继续存在且未被取消/未改状态（断开只结束订阅，不修改任务）。
    assert client.get(f"/api/v2/jobs/{job_id}").json()["state"] == "running"

    # 由同一租约完成剩余步骤并收尾（seq 4..6）。
    complete_step_and_finish(sf, job_id, "s2", lease)

    # 以最后看到的序号重连：只补齐 4..6，终态后发送 done 并结束。
    frames = parse_sse_frames(list(_stream(service, job_id, after_seq=3)))
    seqs = [seq for seq, _ev, _d in frames if seq is not None]
    event_names = [ev for seq, ev, _d in frames if seq is not None]
    assert seqs == [4, 5, 6]
    assert event_names == ["step_started", "step_completed", "completed"]
    done = [ev for _seq, ev, _d in frames if ev == "done"]
    assert len(done) == 1
    assert frames[-1][2]["state"] == "completed"
    assert frames[-1][2]["last_seq"] == 6


def test_sse_from_zero_streams_full_ordered_history(build_app, client):
    """已完成任务从头订阅：全部事件按序号有序、无重复，并以 done 结束。"""
    created = client.post("/api/v2/jobs", json=create_job_body()).json()
    job_id = created["job_id"]
    app = client.app
    sf = app.state.session_factory
    service = app.state.job_service

    lease = claim_and_complete_step(sf, job_id, "s1")
    complete_step_and_finish(sf, job_id, "s2", lease)

    chunks = list(_stream(service, job_id, after_seq=0))
    frames = parse_sse_frames(chunks)
    seqs = [seq for seq, _ev, _d in frames if seq is not None]
    assert seqs == [1, 2, 3, 4, 5, 6]
    assert len(seqs) == len(set(seqs))  # 无重复
    # 每帧的 id 与 data.seq 一致
    for seq, _ev, data in frames:
        if seq is not None:
            assert data["seq"] == seq
            assert data["occurred_at"].endswith(("Z", "+00:00"))
    assert frames[-1][1] == "done"


def test_sse_unknown_job_returns_404(client) -> None:
    resp = client.get("/api/v2/jobs/missing/events?after_seq=0")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_sse_done_reports_server_last_seq_when_client_cursor_is_too_large(build_app, client):
    """客户端游标异常偏大时，done 仍返回数据库中的真实末序号。"""
    created = client.post("/api/v2/jobs", json=create_job_body()).json()
    job_id = created["job_id"]
    sf = client.app.state.session_factory
    service = client.app.state.job_service
    lease = claim_and_complete_step(sf, job_id, "s1")
    complete_step_and_finish(sf, job_id, "s2", lease)

    frames = parse_sse_frames(list(_stream(service, job_id, after_seq=9999)))
    assert frames[-1][1] == "done"
    assert frames[-1][2]["last_seq"] == 6


def test_sse_http_streaming_delivers_terminal_done(client) -> None:
    """通过 HTTP 端点走一遍流式订阅，验证媒体类型与 after_seq 透传。"""
    created = client.post("/api/v2/jobs", json=create_job_body()).json()
    job_id = created["job_id"]
    app = client.app
    sf = app.state.session_factory
    lease = claim_and_complete_step(sf, job_id, "s1")
    complete_step_and_finish(sf, job_id, "s2", lease)

    with client.stream("GET", f"/api/v2/jobs/{job_id}/events?after_seq=3") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.read()
    frames = parse_sse_frames([body])
    seqs = [seq for seq, _ev, _d in frames if seq is not None]
    assert seqs == [4, 5, 6]
    assert frames[-1][1] == "done"


def test_sse_browser_last_event_id_header_resumes_without_duplicates(client) -> None:
    """浏览器 EventSource 自动重连使用 Last-Event-ID 请求头。"""
    created = client.post("/api/v2/jobs", json=create_job_body()).json()
    job_id = created["job_id"]
    sf = client.app.state.session_factory
    lease = claim_and_complete_step(sf, job_id, "s1")
    complete_step_and_finish(sf, job_id, "s2", lease)

    with client.stream(
        "GET",
        f"/api/v2/jobs/{job_id}/events?after_seq=1",
        headers={"Last-Event-ID": "3"},
    ) as response:
        frames = parse_sse_frames([response.read()])

    seqs = [seq for seq, _event, _data in frames if seq is not None]
    assert seqs == [4, 5, 6]
    assert frames[-1][1] == "done"
