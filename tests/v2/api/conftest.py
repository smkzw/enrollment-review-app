"""tests/v2/api 夹具：临时数据根 + 可控 V2 应用（默认关闭后台 runner）。

SSE 测试需要确定性推进任务，因此默认 ``run_runner=False``；需要后台执行器时
由具体测试通过 ``build_app(executors=..., run_runner=True)`` 自行开启。
"""
from __future__ import annotations

import copy
import json

import pytest
from fastapi.testclient import TestClient

from app.api.v2.app import create_app
from app.storage.codecs import utc_now
from app.workflow.jobstore import JobLease, JobStore

DEMO_STEPS = [
    {"step_id": "s1", "name": "解析"},
    {"step_id": "s2", "name": "审核", "depends_on": ["s1"]},
]


@pytest.fixture(autouse=True)
def _stable_semantic_route_preflight_env(monkeypatch):
    """Keep API lifespan preflight off the network and non-strict by default."""

    monkeypatch.setenv("ENROLLMENT_SEMANTIC_ROUTE_PREFLIGHT_MODE", "degrade")
    monkeypatch.setenv("ENROLLMENT_SEMANTIC_ENDPOINT_PREFLIGHT", "0")


@pytest.fixture
def build_app(data_paths):
    """构造 V2 应用的工厂：可注入执行器、轮询与后台 runner 开关。"""
    from app.workflow.runner import StepExecutor

    def _build(*, executors: dict[str, StepExecutor] | None = None,
               run_runner: bool = False, **kwargs):
        defaults = dict(
            sse_poll_interval=0.005,
            sse_heartbeat_seconds=0.05,
        )
        defaults.update(kwargs)
        return create_app(
            data_paths=data_paths,
            executors=executors or {},
            run_runner=run_runner,
            **defaults,
        )

    return _build


@pytest.fixture
def client(build_app):
    app = build_app()
    with TestClient(app) as c:
        yield c


def create_job_body(key: str = "key-1", job_type: str = "demo",
                    steps: list[dict] | None = None,
                    payload: dict | None = None) -> dict:
    return {
        "idempotency_key": key,
        "job_type": job_type,
        "payload": payload or {},
        "steps": copy.deepcopy(steps if steps is not None else DEMO_STEPS),
    }


def claim_and_complete_step(session_factory, job_id: str, step_id: str,
                            worker: str = "w1",
                            checkpoint: dict | None = None) -> JobLease:
    """认领任务并完成单个步骤（保留租约，供后续步骤在同一租约内继续）。"""
    with session_factory() as session:
        with session.begin():
            store = JobStore(session, now=utc_now)
            lease = store.claim_job(job_id, worker)
            store.start_step(lease, step_id)
            store.complete_step(lease, step_id, checkpoint_payload=checkpoint or {})
            return lease


def complete_step_and_finish(session_factory, job_id: str, step_id: str,
                             lease: JobLease,
                             checkpoint: dict | None = None) -> None:
    """在同一租约内完成下一步并收尾（任务进入终态）。"""
    with session_factory() as session:
        with session.begin():
            store = JobStore(session, now=utc_now)
            store.start_step(lease, step_id)
            store.complete_step(lease, step_id, checkpoint_payload=checkpoint or {})
            store.finish_success(lease)


def parse_sse_frames(chunks) -> list[tuple[int | None, str | None, dict | None]]:
    """把 SSE 字节流解析为 ``(seq, event_type, data)`` 帧序列。

    忽略 ``: connected`` / ``: keep-alive`` 注释帧（seq/event 均为 None）。
    """
    frames: list[tuple[int | None, str | None, dict | None]] = []
    buf = ""
    for chunk in chunks:
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8")
        buf += chunk
        while "\n\n" in buf:
            frame, buf = buf.split("\n\n", 1)
            seq: int | None = None
            event: str | None = None
            data: dict | None = None
            for line in frame.split("\n"):
                if line.startswith("id: "):
                    seq = int(line[len("id: "):])
                elif line.startswith("event: "):
                    event = line[len("event: "):]
                elif line.startswith("data: "):
                    data = json.loads(line[len("data: "):])
            if seq is not None or event is not None or data is not None:
                frames.append((seq, event, data))
    return frames
