"""方案控制发现链：任务内受控并行验收。

覆盖目标（项目无关、不绑定 D001/具体方案）：
1. 并行峰值不超过冻结配置；
2. 结果顺序可乱序完成，但持久事件序号单调，闭包依赖全部发现完成；
3. 部分成功保留已提交检查点；
4. 可重试 / 致命失败只影响失败范围；
5. 取消、租约丢失、恢复语义保持；
6. 串行兼容（max_parallel=1 或能力关闭）；
7. 审计假并发（无真实时间重叠却声称并行）与项目过拟合。

本文件在并行 API 落地前会明确失败「能力门」用例，其余并行场景在能力缺失时
跳过；串行基线与语义回归始终执行。
"""
from __future__ import annotations

import inspect
import re
import threading
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable

import pytest

from app.workflow.errors import ProcessDeath, StepFailure
from app.workflow.jobstore import DEFAULT_LEASE_TTL, JobStore
from app.workflow.recovery import recover_expired_jobs
from app.workflow.runner import JobRunner, StepContext
from tests.v2.workflow.conftest import create_job_with_steps, expire_lease

REPO_ROOT = Path(__file__).resolve().parents[3]
_PARALLEL_PARAM_CANDIDATES = (
    "max_in_job_parallelism",
    "max_parallel_steps",
    "in_job_parallelism",
    "max_parallel_discovery_steps",
)
_PROJECT_OVERFIT_PATTERNS = (
    r"\bD001\b",
    r"\bCMS-D001\b",
    r"\bSAR443820\b",
    r"\bSAR\d{3,}\b",
)


@dataclass(frozen=True)
class ParallelCapability:
    """探测到的任务内并行能力。"""

    param_name: str
    constructor: Callable[..., JobRunner]

    def build(
        self,
        session_factory,
        executors,
        *,
        max_parallel: int,
        worker_id: str = "w-parallel",
        now=None,
        lease_ttl: timedelta = DEFAULT_LEASE_TTL,
        **extra: Any,
    ) -> JobRunner:
        kwargs: dict[str, Any] = {
            "worker_id": worker_id,
            "lease_ttl": lease_ttl,
            self.param_name: max_parallel,
        }
        if now is not None:
            kwargs["now"] = now
        kwargs.update(extra)
        return self.constructor(session_factory, executors, **kwargs)


def _detect_parallel_capability() -> ParallelCapability | None:
    signature = inspect.signature(JobRunner.__init__)
    for name in _PARALLEL_PARAM_CANDIDATES:
        if name in signature.parameters:
            return ParallelCapability(param_name=name, constructor=JobRunner)
    return None


PARALLEL = _detect_parallel_capability()
requires_parallel = pytest.mark.skipif(
    PARALLEL is None,
    reason=(
        "JobRunner 尚未暴露任务内并行参数"
        f"（候选: {', '.join(_PARALLEL_PARAM_CANDIDATES)}）；等待 worker_02 落地"
    ),
)


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


def _discovery_shaped_steps(count: int = 4) -> list[dict[str, Any]]:
    """模拟相互独立的发现批次 + 依赖全部发现的闭包步骤。"""

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


def _overlap_executor(
    *,
    hold_seconds: float = 0.25,
    barrier: threading.Barrier | None = None,
    active: set[str] | None = None,
    peak: list[int] | None = None,
    order: list[str] | None = None,
    fail_step: str | None = None,
    fail: StepFailure | None = None,
    cancel_after: str | None = None,
    cancel_callback: Callable[[], None] | None = None,
    lock: threading.Lock | None = None,
) -> Callable[[StepContext], dict[str, Any]]:
    """可观测真实时间重叠的执行器。"""

    gate = lock or threading.Lock()
    live = active if active is not None else set()
    peaks = peak if peak is not None else [0]
    seen = order if order is not None else []

    def executor(ctx: StepContext) -> dict[str, Any]:
        with gate:
            live.add(ctx.step_id)
            peaks[0] = max(peaks[0], len(live))
            seen.append(ctx.step_id)
        if barrier is not None and ctx.step_id.startswith("discovery_"):
            barrier.wait(timeout=5)
        if cancel_after is not None and ctx.step_id == cancel_after and cancel_callback:
            cancel_callback()
        if fail_step is not None and ctx.step_id == fail_step:
            with gate:
                live.discard(ctx.step_id)
            assert fail is not None
            raise fail
        time.sleep(hold_seconds)
        with gate:
            live.discard(ctx.step_id)
        return {"step": ctx.step_id, "attempt": ctx.attempt}

    return executor


def test_parallel_capability_gate_is_present():
    """验收门：任务内受控并行必须有可配置、可冻结的 runner 参数。"""

    assert PARALLEL is not None, (
        "未检测到 JobRunner 任务内并行配置参数。当前 signature="
        f"{inspect.signature(JobRunner.__init__)}；"
        "并行峰值/重叠验收无法成立，避免把串行误报成并行。"
    )


def test_serial_runner_independent_discovery_steps_have_peak_one(
    session_factory, clock
):
    """基线：现有串行 runner 对无依赖发现步骤峰值为 1（用于识别假并发）。"""

    steps = _discovery_shaped_steps(4)
    create_job_with_steps(
        session_factory,
        clock,
        job_id="job-serial-baseline",
        job_type="protocol_control_execution",
        steps=steps,
        payload={
            "execution_version": "acceptance",
            "adaptive_batching": {
                "notes": ["Current durable runner remains serial within one job."]
            },
        },
    )
    peak = [0]
    order: list[str] = []
    executor = _overlap_executor(hold_seconds=0.05, peak=peak, order=order)
    runner = JobRunner(
        session_factory,
        {"protocol_control_execution": executor},
        worker_id="w-serial",
        now=clock.now,
    )
    assert runner.run_job("job-serial-baseline") is True
    snap = _snapshot(session_factory, clock, "job-serial-baseline")
    assert snap.state == "completed"
    assert peak[0] == 1, f"串行基线峰值应为 1，实际 {peak[0]}（疑似假并发或竞态）"
    assert order[-1] == "closure"
    assert set(order[:-1]) == {f"discovery_{i:04d}" for i in range(1, 5)}


def test_no_project_specific_parallel_rules_in_workflow_and_control_execution():
    """审计：并行/workflow/方案控制执行路径不得写入项目特异规则。"""

    targets = [
        REPO_ROOT / "app" / "workflow" / "runner.py",
        REPO_ROOT / "app" / "workflow" / "jobstore.py",
        REPO_ROOT / "app" / "workflow" / "recovery.py",
        REPO_ROOT / "app" / "services" / "protocol_control_execution.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in targets)
    offenders: list[str] = []
    for pattern in _PROJECT_OVERFIT_PATTERNS:
        for match in re.finditer(pattern, combined):
            offenders.append(match.group(0))
    assert offenders == [], f"发现项目特异标记：{sorted(set(offenders))}"


def test_discovery_job_graph_keeps_batches_independent_and_closure_joins(
    session_factory, clock
):
    """串行兼容合同：发现批次互不依赖，闭包汇合全部发现步骤。"""

    steps = _discovery_shaped_steps(3)
    create_job_with_steps(
        session_factory,
        clock,
        job_id="job-graph",
        steps=steps,
    )
    with _store(session_factory, clock) as store:
        deps = {
            step.step_id: tuple(step.depends_on)
            for step in store.snapshot("job-graph").steps
        }
    assert deps["discovery_0001"] == ()
    assert deps["discovery_0002"] == ()
    assert deps["discovery_0003"] == ()
    assert set(deps["closure"]) == {
        "discovery_0001",
        "discovery_0002",
        "discovery_0003",
    }


def test_serial_fatal_failure_keeps_prior_discovery_checkpoints(session_factory, clock):
    """串行部分成功：先完成的发现检查点保留，致命失败不回滚既有成功。"""

    steps = _discovery_shaped_steps(3)
    create_job_with_steps(
        session_factory, clock, job_id="job-serial-partial", job_type="demo", steps=steps
    )
    executor = _overlap_executor(
        hold_seconds=0.01,
        fail_step="discovery_0002",
        fail=StepFailure(
            retryable=False,
            error_code="DISCOVERY_FATAL",
            detail="串行致命失败注入",
        ),
    )
    runner = JobRunner(
        session_factory,
        {"demo": executor},
        worker_id="w-serial-partial",
        now=clock.now,
    )
    assert runner.run_job("job-serial-partial") is True
    snap = _snapshot(session_factory, clock, "job-serial-partial")
    assert snap.state in {"failed", "failed_final"}
    by_id = {step.step_id: step for step in snap.steps}
    assert by_id["discovery_0001"].state == "completed"
    assert by_id["discovery_0002"].state == "failed_final"
    with _store(session_factory, clock) as store:
        assert store.get_last_checkpoint("job-serial-partial", "discovery_0001") is not None
        assert store.get_last_checkpoint("job-serial-partial", "discovery_0002") is None


def test_serial_retryable_failure_reruns_only_failed_scope(session_factory, clock):
    steps = [
        {
            "step_id": "discovery_0001",
            "name": "发现 1",
            "retryable": True,
            "max_attempts": 3,
        },
        {
            "step_id": "discovery_0002",
            "name": "发现 2",
            "retryable": True,
            "max_attempts": 3,
        },
        {
            "step_id": "closure",
            "name": "闭包",
            "depends_on": ("discovery_0001", "discovery_0002"),
        },
    ]
    create_job_with_steps(
        session_factory, clock, job_id="job-serial-retry", job_type="demo", steps=steps
    )
    attempts = {"discovery_0001": 0, "discovery_0002": 0}

    def executor(ctx: StepContext) -> dict[str, Any]:
        if ctx.step_id.startswith("discovery_"):
            attempts[ctx.step_id] += 1
            if ctx.step_id == "discovery_0002" and attempts[ctx.step_id] == 1:
                raise StepFailure(
                    retryable=True,
                    error_code="DISCOVERY_RETRYABLE",
                    detail="串行可重试失败",
                )
        return {"step": ctx.step_id, "attempt": ctx.attempt}

    runner = JobRunner(
        session_factory,
        {"demo": executor},
        worker_id="w-serial-retry",
        now=clock.now,
        backoff=lambda _n: timedelta(seconds=0),
    )
    assert runner.run_job("job-serial-retry") is True
    with _store(session_factory, clock) as store:
        store.requeue_due_retries()
    assert runner.run_job("job-serial-retry") is True
    snap = _snapshot(session_factory, clock, "job-serial-retry")
    assert snap.state == "completed"
    assert attempts == {"discovery_0001": 1, "discovery_0002": 2}


def test_serial_cancel_between_independent_discovery_steps(session_factory, clock):
    steps = _discovery_shaped_steps(3)
    create_job_with_steps(
        session_factory, clock, job_id="job-serial-cancel", job_type="demo", steps=steps
    )
    started: list[str] = []

    def executor(ctx: StepContext) -> dict[str, Any]:
        started.append(ctx.step_id)
        if ctx.step_id == "discovery_0001":
            with _store(session_factory, clock) as store:
                store.request_cancel("job-serial-cancel")
        return {"step": ctx.step_id}

    runner = JobRunner(
        session_factory,
        {"demo": executor},
        worker_id="w-serial-cancel",
        now=clock.now,
    )
    assert runner.run_job("job-serial-cancel") is True
    snap = _snapshot(session_factory, clock, "job-serial-cancel")
    assert snap.state == "cancelled"
    assert started[0] == "discovery_0001"
    assert "closure" not in started


def test_serial_lease_loss_does_not_forge_step_failure(session_factory, clock, monkeypatch):
    steps = _discovery_shaped_steps(2)
    create_job_with_steps(
        session_factory, clock, job_id="job-serial-lease", job_type="demo", steps=steps
    )
    monkeypatch.setattr(JobStore, "renew_lease", lambda self, lease: False)

    def executor(_ctx: StepContext) -> dict[str, Any]:
        time.sleep(0.2)
        return {"step": "done"}

    runner = JobRunner(
        session_factory,
        {"demo": executor},
        worker_id="w-serial-lease",
        now=clock.now,
        lease_ttl=timedelta(seconds=0.15),
    )
    assert runner.run_job("job-serial-lease") is True
    snap = _snapshot(session_factory, clock, "job-serial-lease")
    assert snap.state == "running"
    assert all(
        row.event.event_type.value != "step_failed" for row in snap.events
    )


def test_serial_recovery_reruns_only_interrupted_discovery(session_factory, clock):
    steps = [
        {
            "step_id": f"discovery_{index:04d}",
            "name": f"发现批次 {index:04d}",
            "retryable": True,
            "max_attempts": 3,
        }
        for index in range(1, 4)
    ]
    steps.append(
        {
            "step_id": "closure",
            "name": "确定性闭包",
            "depends_on": tuple(step["step_id"] for step in steps),
        }
    )
    create_job_with_steps(
        session_factory, clock, job_id="job-serial-recover", job_type="demo", steps=steps
    )
    calls: list[str] = []

    def executor(ctx: StepContext) -> dict[str, Any]:
        calls.append(ctx.step_id)
        if ctx.step_id == "discovery_0002" and calls.count("discovery_0002") == 1:
            raise ProcessDeath("serial process death")
        return {"step": ctx.step_id}

    runner = JobRunner(
        session_factory,
        {"demo": executor},
        worker_id="w-serial-recover",
        now=clock.now,
    )
    with pytest.raises(ProcessDeath):
        runner.run_job("job-serial-recover")
    expire_lease(
        session_factory,
        "job-serial-recover",
        before=clock.now() - timedelta(seconds=1),
    )
    report = recover_expired_jobs(session_factory, now=clock.now)
    assert "job-serial-recover" in report.requeued_jobs
    assert runner.run_job("job-serial-recover") is True
    snap = _snapshot(session_factory, clock, "job-serial-recover")
    assert snap.state == "completed"
    assert calls.count("discovery_0001") == 1
    assert calls.count("discovery_0002") == 2
    assert calls.count("discovery_0003") == 1





@requires_parallel
def test_parallel_peak_respects_frozen_max_parallel(session_factory, clock):
    assert PARALLEL is not None
    steps = _discovery_shaped_steps(4)
    create_job_with_steps(
        session_factory,
        clock,
        job_id="job-peak",
        job_type="protocol_control_execution",
        steps=steps,
        payload={"parallel_execution": {"max_parallel": 2, "scope": "discovery_*"}},
    )
    barrier = threading.Barrier(2)
    peak = [0]
    order: list[str] = []
    executor = _overlap_executor(
        hold_seconds=0.05,
        barrier=barrier,
        peak=peak,
        order=order,
    )
    runner = PARALLEL.build(
        session_factory,
        {"protocol_control_execution": executor},
        max_parallel=2,
        worker_id="w-peak",
        now=clock.now,
    )
    assert runner.run_job("job-peak") is True
    snap = _snapshot(session_factory, clock, "job-peak")
    assert snap.state == "completed"
    assert peak[0] == 2, f"期望真实并行峰值 2，实际 {peak[0]}（假并发风险）"
    assert peak[0] <= 2
    assert order.count("closure") == 1
    assert order[-1] == "closure"


@requires_parallel
def test_parallel_completion_order_may_differ_but_events_are_monotonic(
    session_factory, clock
):
    assert PARALLEL is not None
    steps = _discovery_shaped_steps(3)
    create_job_with_steps(
        session_factory,
        clock,
        job_id="job-order",
        job_type="demo",
        steps=steps,
    )

    def executor(ctx: StepContext) -> dict[str, Any]:
        delay = 0.05 if ctx.step_id != "discovery_0001" else 0.2
        if ctx.step_id == "closure":
            delay = 0.01
        time.sleep(delay)
        return {"step": ctx.step_id}

    runner = PARALLEL.build(
        session_factory,
        {"demo": executor},
        max_parallel=3,
        worker_id="w-order",
        now=clock.now,
    )
    assert runner.run_job("job-order") is True
    snap = _snapshot(session_factory, clock, "job-order")
    completed_order = [
        row.event.step_id
        for row in snap.events
        if row.event.event_type.value == "step_completed"
    ]
    assert completed_order[-1] == "closure"
    assert set(completed_order[:-1]) == {
        "discovery_0001",
        "discovery_0002",
        "discovery_0003",
    }
    seqs = [row.seq for row in snap.events]
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))


@requires_parallel
def test_partial_success_keeps_completed_discovery_checkpoints(session_factory, clock):
    assert PARALLEL is not None
    steps = _discovery_shaped_steps(3)
    create_job_with_steps(
        session_factory,
        clock,
        job_id="job-partial",
        job_type="demo",
        steps=steps,
    )
    barrier = threading.Barrier(2)
    peak = [0]
    executor = _overlap_executor(
        hold_seconds=0.05,
        barrier=barrier,
        peak=peak,
        fail_step="discovery_0003",
        fail=StepFailure(
            retryable=False,
            error_code="DISCOVERY_FATAL",
            detail="致命失败注入",
        ),
    )
    runner = PARALLEL.build(
        session_factory,
        {"demo": executor},
        max_parallel=2,
        worker_id="w-partial",
        now=clock.now,
    )
    assert runner.run_job("job-partial") is True
    snap = _snapshot(session_factory, clock, "job-partial")
    assert snap.state in {"failed", "failed_final"}
    by_id = {step.step_id: step for step in snap.steps}
    assert by_id["discovery_0001"].state == "completed"
    assert by_id["discovery_0002"].state == "completed"
    assert by_id["discovery_0003"].state == "failed_final"
    assert by_id["closure"].state in {"cancelled", "failed_final", "pending", "queued"}
    with _store(session_factory, clock) as store:
        assert store.get_last_checkpoint("job-partial", "discovery_0001") is not None
        assert store.get_last_checkpoint("job-partial", "discovery_0002") is not None
        assert store.get_last_checkpoint("job-partial", "discovery_0003") is None
    assert peak[0] >= 2


@requires_parallel
def test_retryable_failure_reruns_only_failed_discovery_step(session_factory, clock):
    assert PARALLEL is not None
    steps = [
        {
            "step_id": "discovery_0001",
            "name": "发现 1",
            "retryable": True,
            "max_attempts": 3,
        },
        {
            "step_id": "discovery_0002",
            "name": "发现 2",
            "retryable": True,
            "max_attempts": 3,
        },
        {
            "step_id": "closure",
            "name": "闭包",
            "depends_on": ("discovery_0001", "discovery_0002"),
        },
    ]
    create_job_with_steps(
        session_factory, clock, job_id="job-retry", job_type="demo", steps=steps
    )
    attempts: dict[str, int] = {"discovery_0001": 0, "discovery_0002": 0}

    def executor(ctx: StepContext) -> dict[str, Any]:
        if ctx.step_id.startswith("discovery_"):
            attempts[ctx.step_id] = attempts.get(ctx.step_id, 0) + 1
            if ctx.step_id == "discovery_0002" and attempts[ctx.step_id] == 1:
                raise StepFailure(
                    retryable=True,
                    error_code="DISCOVERY_RETRYABLE",
                    detail="可重试失败注入",
                )
            time.sleep(0.05)
        return {"step": ctx.step_id, "attempt": ctx.attempt}

    runner = PARALLEL.build(
        session_factory,
        {"demo": executor},
        max_parallel=2,
        worker_id="w-retry",
        now=clock.now,
        backoff=lambda _n: timedelta(seconds=0),
    )
    assert runner.run_job("job-retry") is True
    with _store(session_factory, clock) as store:
        store.requeue_due_retries()
    assert runner.run_job("job-retry") is True
    snap = _snapshot(session_factory, clock, "job-retry")
    assert snap.state == "completed"
    assert attempts["discovery_0001"] == 1
    assert attempts["discovery_0002"] == 2


@requires_parallel
def test_cancel_requested_does_not_start_new_parallel_cohort(session_factory, clock):
    assert PARALLEL is not None
    steps = _discovery_shaped_steps(4)
    create_job_with_steps(
        session_factory, clock, job_id="job-cancel", job_type="demo", steps=steps
    )
    started: list[str] = []

    def request_cancel() -> None:
        with _store(session_factory, clock) as store:
            store.request_cancel("job-cancel")

    def executor(ctx: StepContext) -> dict[str, Any]:
        started.append(ctx.step_id)
        if ctx.step_id == "discovery_0001":
            request_cancel()
            time.sleep(0.1)
        else:
            time.sleep(0.05)
        return {"step": ctx.step_id}

    runner = PARALLEL.build(
        session_factory,
        {"demo": executor},
        max_parallel=2,
        worker_id="w-cancel",
        now=clock.now,
    )
    assert runner.run_job("job-cancel") is True
    snap = _snapshot(session_factory, clock, "job-cancel")
    assert snap.state == "cancelled"
    assert "closure" not in started
    assert all(step_id.startswith("discovery_") for step_id in started)


@requires_parallel
def test_lease_loss_discards_in_flight_parallel_results(session_factory, clock):
    assert PARALLEL is not None
    steps = _discovery_shaped_steps(2)
    create_job_with_steps(
        session_factory, clock, job_id="job-lease", job_type="demo", steps=steps
    )
    entered = threading.Event()

    def executor(ctx: StepContext) -> dict[str, Any]:
        if ctx.step_id.startswith("discovery_"):
            entered.set()
            time.sleep(0.3)
        return {"step": ctx.step_id}

    runner = PARALLEL.build(
        session_factory,
        {"demo": executor},
        max_parallel=2,
        worker_id="w-lease",
        now=clock.now,
        lease_ttl=timedelta(seconds=0.05),
    )

    def steal_lease() -> None:
        entered.wait(timeout=2)
        expire_lease(
            session_factory, "job-lease", before=clock.now() - timedelta(seconds=1)
        )
        with _store(session_factory, clock) as store:
            job = store.get_job("job-lease")
            job.lease_owner = "recovery-worker"
            job.lease_generation = job.lease_generation + 1
            job.lease_expires_at = clock.now() + DEFAULT_LEASE_TTL

    thief = threading.Thread(target=steal_lease, name="steal-lease", daemon=True)
    thief.start()
    assert runner.run_job("job-lease") is True
    thief.join(timeout=2)
    snap = _snapshot(session_factory, clock, "job-lease")
    assert all(
        step.state != "completed"
        for step in snap.steps
        if step.step_id.startswith("discovery_")
    ) or snap.lease_generation > 1


@requires_parallel
def test_recovery_after_process_death_reruns_only_incomplete_discovery(
    session_factory, clock
):
    assert PARALLEL is not None
    steps = [
        {
            "step_id": f"discovery_{index:04d}",
            "name": f"发现批次 {index:04d}",
            "retryable": True,
            "max_attempts": 3,
        }
        for index in range(1, 4)
    ]
    steps.append(
        {
            "step_id": "closure",
            "name": "确定性闭包",
            "depends_on": tuple(step["step_id"] for step in steps),
        }
    )
    create_job_with_steps(
        session_factory, clock, job_id="job-recover", job_type="demo", steps=steps
    )
    calls: list[str] = []

    def executor(ctx: StepContext) -> dict[str, Any]:
        calls.append(ctx.step_id)
        if ctx.step_id == "discovery_0002" and calls.count("discovery_0002") == 1:
            raise ProcessDeath("模拟进程死亡")
        time.sleep(0.02)
        return {"step": ctx.step_id}

    runner = PARALLEL.build(
        session_factory,
        {"demo": executor},
        max_parallel=2,
        worker_id="w-recover",
        now=clock.now,
        lease_ttl=timedelta(seconds=1),
    )
    with pytest.raises(ProcessDeath):
        runner.run_job("job-recover")
    expire_lease(
        session_factory, "job-recover", before=clock.now() - timedelta(seconds=1)
    )
    report = recover_expired_jobs(session_factory, now=clock.now)
    assert "job-recover" in report.requeued_jobs
    calls_before = list(calls)
    assert runner.run_job("job-recover") is True
    snap = _snapshot(session_factory, clock, "job-recover")
    assert snap.state == "completed"
    completed_before_death = [
        step_id
        for step_id in calls_before
        if step_id.startswith("discovery_") and step_id != "discovery_0002"
    ]
    for step_id in completed_before_death:
        assert calls.count(step_id) == 1


@requires_parallel
def test_serial_compatibility_max_parallel_one_matches_baseline(session_factory, clock):
    assert PARALLEL is not None
    steps = _discovery_shaped_steps(3)
    create_job_with_steps(
        session_factory, clock, job_id="job-serial-mode", job_type="demo", steps=steps
    )
    peak = [0]
    order: list[str] = []
    executor = _overlap_executor(hold_seconds=0.05, peak=peak, order=order)
    runner = PARALLEL.build(
        session_factory,
        {"demo": executor},
        max_parallel=1,
        worker_id="w-serial-mode",
        now=clock.now,
    )
    assert runner.run_job("job-serial-mode") is True
    assert peak[0] == 1
    assert order[-1] == "closure"
    snap = _snapshot(session_factory, clock, "job-serial-mode")
    assert snap.state == "completed"
