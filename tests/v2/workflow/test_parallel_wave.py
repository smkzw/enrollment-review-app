"""租约安全的任务内并行波次：配置冻结与发现步骤独立执行。"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest

from app.workflow.errors import ProcessDeath, StepFailure
from app.workflow.jobstore import DEFAULT_LEASE_TTL, JobStore
from app.workflow.runner import JobRunner, StepContext
from tests.v2.workflow.conftest import create_job_with_steps


@pytest.mark.parametrize("ending", ["success", "crash", "cancel"])
def test_success_is_durable_while_other_lane_is_still_running(session_factory, clock, ending):
    create_job_with_steps(session_factory, clock, job_id="early-commit",
                          steps=_discovery_steps(2))
    release = threading.Event()

    def executor(ctx):
        if ctx.step_id == "discovery_0002":
            assert release.wait(timeout=10)
            if ending == "crash":
                raise ProcessDeath()
        return {"step": ctx.step_id}

    notifications = []

    def on_cancelled(job_id):
        notifications.append(_snapshot(session_factory, clock, job_id).state)

    runner = JobRunner(session_factory, {"demo": executor}, now=clock.now,
                       max_parallel_steps=2, on_cancelled=on_cancelled)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(runner.run_job, "early-commit")
        try:
            deadline = time.monotonic() + 5
            receipt = None
            while time.monotonic() < deadline:
                with _store(session_factory, clock) as store:
                    receipt = store.get_last_checkpoint("early-commit", "discovery_0001")
                if receipt is not None:
                    break
                time.sleep(0.02)
            assert receipt is not None
            assert not future.done()
            if ending == "cancel":
                with _store(session_factory, clock) as store:
                    store.request_cancel("early-commit")
        finally:
            release.set()
        if ending == "crash":
            with pytest.raises(ProcessDeath):
                future.result(timeout=10)
        else:
            assert future.result(timeout=10)
    with _store(session_factory, clock) as store:
        assert store.get_last_checkpoint("early-commit", "discovery_0001") == receipt
    if ending == "cancel":
        assert notifications == ["cancelled"]


def _store(session_factory, clock):
    class _T:
        def __enter__(self):
            self.session = session_factory()
            self.tx = self.session.begin()
            return JobStore(self.session, now=clock.now, lease_ttl=DEFAULT_LEASE_TTL)

        def __exit__(self, *exc):
            if exc[0] is None:
                self.tx.commit()
            else:
                self.tx.rollback()
            self.session.close()
            return False

    return _T()


def _snapshot(session_factory, clock, job_id: str):
    with _store(session_factory, clock) as store:
        return store.snapshot(job_id)


def _discovery_steps(count: int = 3):
    discovery = [
        {
            "step_id": f"discovery_{index:04d}",
            "name": f"发现批次 {index:04d}",
            "retryable": False,
            "max_attempts": 1,
        }
        for index in range(1, count + 1)
    ]
    discovery.append(
        {
            "step_id": "closure",
            "name": "确定性闭包",
            "depends_on": tuple(step["step_id"] for step in discovery),
        }
    )
    return discovery


def test_default_runner_remains_serial_without_parallel_capability(session_factory, clock):
    create_job_with_steps(
        session_factory,
        clock,
        job_id="job-serial",
        job_type="demo",
        steps=_discovery_steps(3),
    )
    peak = [0]
    live: set[str] = set()
    lock = threading.Lock()

    def executor(ctx: StepContext) -> dict:
        with lock:
            live.add(ctx.step_id)
            peak[0] = max(peak[0], len(live))
        time.sleep(0.05)
        with lock:
            live.discard(ctx.step_id)
        return {"step": ctx.step_id}

    runner = JobRunner(session_factory, {"demo": executor}, worker_id="w1", now=clock.now)
    assert runner.run_job("job-serial") is True
    assert peak[0] == 1
    assert _snapshot(session_factory, clock, "job-serial").state == "completed"


def test_parallel_wave_runs_independent_discovery_steps(session_factory, clock):
    create_job_with_steps(
        session_factory,
        clock,
        job_id="job-parallel",
        job_type="demo",
        steps=_discovery_steps(3),
        payload={
            "parallel_execution": {"max_parallel": 3, "scope": "discovery_*"},
        },
    )
    barrier = threading.Barrier(3)
    peak = [0]
    live: set[str] = set()
    lock = threading.Lock()

    def executor(ctx: StepContext) -> dict:
        with lock:
            live.add(ctx.step_id)
            peak[0] = max(peak[0], len(live))
        if ctx.step_id.startswith("discovery_"):
            barrier.wait(timeout=5)
        time.sleep(0.02)
        with lock:
            live.discard(ctx.step_id)
        return {"step": ctx.step_id}

    runner = JobRunner(
        session_factory,
        {"demo": executor},
        worker_id="w-par",
        now=clock.now,
        max_parallel_steps=3,
    )
    assert runner.run_job("job-parallel") is True
    assert peak[0] == 3
    snap = _snapshot(session_factory, clock, "job-parallel")
    assert snap.state == "completed"
    assert [step.step_id for step in snap.steps if step.state == "completed"][-1] == "closure"


def test_parallel_partial_success_commits_before_fatal(session_factory, clock):
    create_job_with_steps(
        session_factory,
        clock,
        job_id="job-partial",
        job_type="demo",
        steps=_discovery_steps(3),
    )
    barrier = threading.Barrier(2)
    peak = [0]
    live: set[str] = set()
    lock = threading.Lock()

    def executor(ctx: StepContext) -> dict:
        with lock:
            live.add(ctx.step_id)
            peak[0] = max(peak[0], len(live))
        if ctx.step_id.startswith("discovery_"):
            barrier.wait(timeout=5)
        with lock:
            live.discard(ctx.step_id)
        if ctx.step_id == "discovery_0003":
            raise StepFailure(retryable=False, error_code="DISCOVERY_FATAL", detail="x")
        return {"step": ctx.step_id}

    runner = JobRunner(
        session_factory,
        {"demo": executor},
        worker_id="w-partial",
        now=clock.now,
        max_parallel_steps=2,
    )
    assert runner.run_job("job-partial") is True
    snap = _snapshot(session_factory, clock, "job-partial")
    assert snap.state == "failed_final"
    by_id = {step.step_id: step for step in snap.steps}
    assert by_id["discovery_0001"].state == "completed"
    assert by_id["discovery_0002"].state == "completed"
    assert by_id["discovery_0003"].state == "failed_final"
    # No orphan running siblings after fatal settle.
    assert all(step.state != "running" for step in snap.steps)
    with _store(session_factory, clock) as store:
        assert store.get_last_checkpoint("job-partial", "discovery_0001") is not None
        assert store.get_last_checkpoint("job-partial", "discovery_0002") is not None


def test_execution_control_freeze_enables_parallel_when_runner_default_serial(
    session_factory, clock
):
    create_job_with_steps(
        session_factory,
        clock,
        job_id="job-frozen",
        job_type="protocol_control_execution",
        steps=_discovery_steps(2),
        payload={
            "execution_control": {
                "schema": "phase5/protocol-control-execution-control/v1",
                "max_parallel_steps": 2,
                "parallelizable_step_ids": ["discovery_0001", "discovery_0002"],
                "parallel_scope": "discovery_batches_only",
            }
        },
    )
    barrier = threading.Barrier(2)
    peak = [0]
    live: set[str] = set()
    lock = threading.Lock()

    def executor(ctx: StepContext) -> dict:
        with lock:
            live.add(ctx.step_id)
            peak[0] = max(peak[0], len(live))
        if ctx.step_id.startswith("discovery_"):
            barrier.wait(timeout=5)
        with lock:
            live.discard(ctx.step_id)
        return {"step": ctx.step_id}

    # Runner stays at default max_parallel_steps=1; frozen execution_control lifts it.
    runner = JobRunner(
        session_factory,
        {"protocol_control_execution": executor},
        worker_id="w-freeze",
        now=clock.now,
    )
    assert runner.run_job("job-frozen") is True
    assert peak[0] == 2
    assert _snapshot(session_factory, clock, "job-frozen").state == "completed"
