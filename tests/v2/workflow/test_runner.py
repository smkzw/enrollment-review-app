"""JobRunner 执行循环与故障注入：依赖顺序、退避重试、取消边界、进程死亡、重复 worker。"""
from __future__ import annotations

import time
from datetime import timedelta

import pytest

from app.workflow.errors import ProcessDeath, StepFailure
from app.workflow.jobstore import DEFAULT_LEASE_TTL, JobStore
from app.workflow.runner import JobRunner, StepContext
from tests.v2.workflow.conftest import (
    create_job_with_steps,
    expire_lease,
    job_state,
)

TWO_STEPS = [
    {"step_id": "s1", "name": "解析"},
    {"step_id": "s2", "name": "审核", "depends_on": ("s1",)},
]


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


def _snapshot(session_factory, clock, job_id):
    with _store(session_factory, clock) as store:
        return store.snapshot(job_id)


def _requeue_due(session_factory, clock):
    with _store(session_factory, clock) as store:
        return store.requeue_due_retries()


def test_runner_completes_dependent_steps_in_order(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=TWO_STEPS)
    calls: list[str] = []

    def executor(ctx: StepContext) -> dict:
        calls.append(ctx.step_id)
        return {"step": ctx.step_id, "attempt": ctx.attempt}

    runner = JobRunner(session_factory, {"demo": executor}, worker_id="w1")
    assert runner.run_job("job-1") is True
    assert calls == ["s1", "s2"]  # 依赖顺序
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.state == "completed"
    assert snap.progress_completed == 2
    kinds = [row.event.event_type.value for row in snap.events]
    assert kinds == [
        "created", "step_started", "step_completed",
        "step_started", "step_completed", "completed",
    ]
    seqs = [row.seq for row in snap.events]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)


def test_retryable_failure_reruns_only_failed_step_after_backoff(session_factory, clock):
    steps = [
        {"step_id": "s1", "name": "解析", "retryable": True, "max_attempts": 3},
        {"step_id": "s2", "name": "审核", "depends_on": ("s1",)},
    ]
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=steps)
    calls: list[str] = []
    fail_once = {"armed": True}

    def executor(ctx: StepContext) -> dict:
        calls.append(ctx.step_id)
        if ctx.step_id == "s1" and fail_once["armed"]:
            fail_once["armed"] = False
            raise StepFailure(retryable=True, error_code="E_TRANSIENT")
        return {"step": ctx.step_id}

    runner = JobRunner(session_factory, {"demo": executor}, worker_id="w1", now=clock.now)
    assert runner.run_job("job-1") is True
    assert job_state(session_factory, "job-1") == "failed_retryable"
    assert calls == ["s1"]  # s2 未执行：依赖未满足，只失败范围等待重试

    # 退避未到期：不可认领（任务不在 queued）
    assert runner.run_job("job-1") is False
    assert _requeue_due(session_factory, clock) == []

    clock.advance(0.6)  # backoff(attempt=1) = 0.5s
    assert _requeue_due(session_factory, clock) == ["job-1"]
    assert runner.run_job("job-1") is True
    assert calls == ["s1", "s1", "s2"]  # 只重跑失败步骤，s2 在 s1 成功后执行
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.state == "completed"
    assert snap.steps[0].attempt == 2
    kinds = [row.event.event_type.value for row in snap.events]
    assert kinds.count("retry_scheduled") == 1
    assert kinds.count("step_failed") == 1


def test_runner_releases_abnormally_queued_deferred_step_without_running_it(
    session_factory, clock
):
    """即使任务状态被异常回填，未到期步骤也不会执行或泄漏租约。"""
    from sqlalchemy import update

    from app.storage.models import JobRecord

    steps = [{"step_id": "s1", "name": "解析", "retryable": True, "max_attempts": 2}]
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=steps)
    with _store(session_factory, clock) as store:
        lease = store.claim_job("job-1", "w1")
        assert lease is not None
        store.start_step(lease, "s1")
    with _store(session_factory, clock) as store:
        store.fail_step(lease, "s1", error_code="E_RETRY", retryable=True)
    with session_factory() as session, session.begin():
        session.execute(
            update(JobRecord).where(JobRecord.job_id == "job-1").values(state="queued")
        )

    calls: list[str] = []
    runner = JobRunner(
        session_factory,
        {"demo": lambda ctx: calls.append(ctx.step_id) or {}},
        worker_id="w2",
        now=clock.now,
    )
    assert runner.run_job("job-1") is True
    snap = _snapshot(session_factory, clock, "job-1")
    assert calls == []
    assert snap.state == "failed_retryable"
    with session_factory() as session:
        assert session.get(JobRecord, "job-1").lease_owner is None


def test_final_failure_after_max_attempts(session_factory, clock):
    steps = [{"step_id": "s1", "name": "解析", "retryable": True, "max_attempts": 2}]
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=steps)
    calls: list[str] = []

    def executor(ctx: StepContext) -> dict:
        calls.append(ctx.step_id)
        raise StepFailure(retryable=True, error_code="E_ALWAYS")

    runner = JobRunner(session_factory, {"demo": executor}, worker_id="w1", now=clock.now)
    assert runner.run_job("job-1") is True
    assert job_state(session_factory, "job-1") == "failed_retryable"
    clock.advance(0.6)
    _requeue_due(session_factory, clock)
    assert runner.run_job("job-1") is True
    assert calls == ["s1", "s1"]  # 恰好 max_attempts 次，不无限重试
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.state == "failed_final"
    failed = [row.event for row in snap.events if row.event.event_type.value == "step_failed"]
    assert failed[-1].payload.get("attempt_exhausted") is True
    assert job_state(session_factory, "job-1") != "running"


def test_cancel_requested_between_steps_stops_before_next_step(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=TWO_STEPS)
    calls: list[str] = []
    cancelled: list[str] = []

    def executor(ctx: StepContext) -> dict:
        calls.append(ctx.step_id)
        if ctx.step_id == "s1":
            # 用户在执行期间发起取消：持久请求，与 worker 解耦
            with _store(session_factory, clock) as store:
                store.request_cancel("job-1")
        return {"step": ctx.step_id}

    runner = JobRunner(
        session_factory,
        {"demo": executor},
        worker_id="w1",
        on_cancelled=cancelled.append,
    )
    assert runner.run_job("job-1") is True
    assert calls == ["s1"]  # s2 未执行：取消在安全边界生效
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.state == "cancelled"
    states = {step.step_id: step.state for step in snap.steps}
    assert states["s1"] == "completed"  # 已完成步骤保留
    assert states["s2"] == "cancelled"
    assert cancelled == ["job-1"]
    kinds = [row.event.event_type.value for row in snap.events]
    assert "cancel_requested" in kinds
    assert "cancelled" in kinds
    assert "step_completed" in kinds  # 历史事件保留


def test_process_death_before_commit_leaves_job_for_recovery(session_factory, clock):
    # 中断步骤必须有剩余尝试预算，恢复器才会重新排队（design.md §5）。
    steps = [
        {"step_id": "s1", "name": "解析", "retryable": True, "max_attempts": 3},
        {"step_id": "s2", "name": "审核", "depends_on": ("s1",), "retryable": True, "max_attempts": 3},
    ]
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=steps)

    def dying_executor(ctx: StepContext) -> dict:
        raise ProcessDeath()  # 提交前被强制终止

    runner = JobRunner(session_factory, {"demo": dying_executor}, worker_id="w1", now=clock.now)
    with pytest.raises(ProcessDeath):
        runner.run_job("job-1")
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.state == "running"  # 没有清理：等价于真实死亡
    assert snap.steps[0].state == "running"
    assert snap.lease_generation == 1

    # 租约过期 -> 恢复 -> 由新 worker 完成
    expire_lease(session_factory, "job-1", before=clock.now() - timedelta(seconds=1))
    from app.workflow.recovery import recover_expired_jobs
    report = recover_expired_jobs(session_factory, now=clock.now)
    assert report.recovered_jobs == ["job-1"]

    calls: list[str] = []
    def executor(ctx: StepContext) -> dict:
        calls.append(ctx.step_id)
        return {}
    fresh_runner = JobRunner(session_factory, {"demo": executor}, worker_id="w2", now=clock.now)
    assert fresh_runner.run_job("job-1") is True
    assert calls == ["s1", "s2"]
    assert job_state(session_factory, "job-1") == "completed"


def test_duplicate_workers_only_one_claims(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=TWO_STEPS)
    calls: list[tuple[str, str]] = []

    def executor(ctx: StepContext) -> dict:
        calls.append((ctx.step_id, ctx.job_id))
        return {}

    runner_a = JobRunner(session_factory, {"demo": executor}, worker_id="wa")
    runner_b = JobRunner(session_factory, {"demo": executor}, worker_id="wb")
    assert runner_a.run_job("job-1") is True
    assert runner_b.run_job("job-1") is False  # 任务已被认领完成，无从领取
    assert job_state(session_factory, "job-1") == "completed"
    assert len(calls) == 2  # 每个步骤恰好执行一次，无重复 worker 重复执行


def test_long_running_step_renews_lease_during_executor(session_factory, clock):
    """执行时长超过初始租约，恢复扫描仍不得接管或重复执行。"""
    from app.workflow.recovery import recover_expired_jobs

    steps = [{"step_id": "s1", "name": "解析", "retryable": True, "max_attempts": 3}]
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=steps)
    reports = []

    def executor(ctx: StepContext) -> dict:
        time.sleep(0.45)
        reports.append(recover_expired_jobs(session_factory))
        time.sleep(0.2)
        return {"step": ctx.step_id}

    runner = JobRunner(
        session_factory,
        {"demo": executor},
        worker_id="w1",
        lease_ttl=timedelta(seconds=0.3),
    )
    assert runner.run_job("job-1") is True
    assert reports[0].touched == 0
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.state == "completed"
    assert snap.steps[0].attempt == 1


def test_heartbeat_recovers_after_local_clock_jumps_past_lease(session_factory, clock):
    """模拟 Mac 睡眠：没有恢复器接管时，唤醒后的原 worker 可继续提交。"""
    steps = [{"step_id": "s1", "name": "解析", "retryable": True, "max_attempts": 3}]
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=steps)

    def executor(ctx: StepContext) -> dict:
        clock.advance(1.0)
        time.sleep(0.15)
        return {"step": ctx.step_id}

    runner = JobRunner(
        session_factory,
        {"demo": executor},
        worker_id="w1",
        now=clock.now,
        lease_ttl=timedelta(seconds=0.3),
    )
    assert runner.run_job("job-1") is True
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.state == "completed"
    assert snap.steps[0].attempt == 1


def test_missing_executor_fails_final_with_typed_error(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=TWO_STEPS)
    runner = JobRunner(session_factory, {}, worker_id="w1")  # 未注册任何执行器
    assert runner.run_job("job-1") is True
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.state == "failed_final"
    assert snap.steps[0].error_code == "EXECUTOR_MISSING"
    failed = [row.event for row in snap.events if row.event.event_type.value == "step_failed"]
    assert failed[0].payload.get("error_code") == "EXECUTOR_MISSING"
    assert failed[0].retryable is False
    assert "demo" not in failed[0].payload.get("detail", "")
    assert snap.events[-1].event.event_type.value == "failed"


def test_unexpected_executor_exception_fails_fatal_without_retry(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=TWO_STEPS)

    def exploding_executor(ctx: StepContext) -> dict:
        raise ValueError("模拟执行器缺陷")

    runner = JobRunner(session_factory, {"demo": exploding_executor}, worker_id="w1")
    assert runner.run_job("job-1") is True
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.state == "failed_final"
    assert snap.steps[0].error_code == "EXECUTOR_ERROR"
    assert snap.steps[0].attempt == 1  # 缺陷不触发自动重试循环
    failed = [row.event for row in snap.events if row.event.event_type.value == "step_failed"]
    assert "模拟执行器缺陷" not in failed[-1].payload.get("detail", "")
