"""启动恢复与故障注入：提交前/后终止、租约过期、重复 worker、预算耗尽。"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.storage.models import JobCheckpointRecord
from app.workflow.jobstore import DEFAULT_LEASE_TTL, JobStore
from app.workflow.recovery import recover_expired_jobs
from app.workflow.runner import JobRunner, StepContext
from tests.v2.workflow.conftest import (
    create_job_with_steps,
    expire_lease,
    job_state,
)

STEPS = [{"step_id": "s1", "name": "解析", "retryable": True, "max_attempts": 3}]


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


def _claim_and_start(session_factory, clock, worker_id="w1"):
    """认领并启动 s1，模拟 worker 在步骤执行中被杀。"""
    with _store(session_factory, clock) as store:
        lease = store.claim_next(worker_id)
        store.start_step(lease, "s1")
    return lease


def _recover(session_factory, clock):
    return recover_expired_jobs(session_factory, now=clock.now)


def test_crash_before_commit_recovers_and_reruns_only_interrupted_step(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    lease = _claim_and_start(session_factory, clock)  # s1 running，未提交任何结果
    assert job_state(session_factory, "job-1") == "running"

    expire_lease(session_factory, "job-1", before=clock.now() - timedelta(seconds=1))
    report = _recover(session_factory, clock)
    assert report.recovered_jobs == ["job-1"]
    assert report.requeued_jobs == ["job-1"]

    with _store(session_factory, clock) as store:
        snap = store.snapshot("job-1")
    assert snap.state == "queued"
    assert snap.steps[0].state == "queued"
    assert snap.steps[0].attempt == 1  # 中断尝试已计入，恢复不重复计数
    kinds = [row.event.event_type.value for row in snap.events]
    assert "retry_scheduled" in kinds
    assert snap.events[-1].event.payload.get("reason") == "lease_recovery"

    # 恢复后可重新领取并完成；重复运行恢复器为空操作
    assert _recover(session_factory, clock).touched == 0
    lease2 = None
    with _store(session_factory, clock) as store:
        lease2 = store.claim_next("w1")
        assert lease2 is not None
        assert lease2.generation > lease.generation  # 代号递增，旧租约作废
        store.start_step(lease2, "s1")
        store.complete_step(lease2, "s1", checkpoint_payload={})
        store.finish_success(lease2)
    assert job_state(session_factory, "job-1") == "completed"


def test_crash_after_commit_does_not_reexecute_completed_step(session_factory, clock):
    steps = [
        {"step_id": "s1", "name": "解析"},
        # s2 需有剩余尝试预算，恢复器才会将其重新排队（design.md §5）。
        {"step_id": "s2", "name": "审核", "depends_on": ("s1",), "retryable": True, "max_attempts": 3},
    ]
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=steps)
    with _store(session_factory, clock) as store:
        lease = store.claim_next("w1")
        store.start_step(lease, "s1")
        store.complete_step(lease, "s1", checkpoint_payload={"v": 1})  # s1 已提交
        store.start_step(lease, "s2")  # 在 s2 执行中被杀

    expire_lease(session_factory, "job-1", before=clock.now() - timedelta(seconds=1))
    _recover(session_factory, clock)
    with _store(session_factory, clock) as store:
        snap = store.snapshot("job-1")
    states = {step.step_id: step.state for step in snap.steps}
    assert states == {"s1": "completed", "s2": "queued"}

    calls: list[str] = []
    def executor(ctx: StepContext) -> dict:
        calls.append(ctx.step_id)
        return {"step": ctx.step_id}

    runner = JobRunner(session_factory, {"demo": executor}, worker_id="w1", now=clock.now)
    assert runner.run_job("job-1") is True
    assert calls == ["s2"]  # 已完成步骤绝不重复执行
    assert job_state(session_factory, "job-1") == "completed"


def test_checkpoint_committed_before_crash_marks_step_completed(session_factory, clock):
    """执行器自行提交 Checkpoint 后进程被杀：恢复以 Checkpoint 为准，不重跑。"""
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    lease = _claim_and_start(session_factory, clock)
    # 模拟“checkpoint 已提交、步骤完成事务未提交”的窗口
    with _store(session_factory, clock) as store:
        store.repo.create_checkpoint(
            checkpoint_id="cp-1", job_id="job-1", step_id="s1", payload={"half": True}
        )
    expire_lease(session_factory, "job-1", before=clock.now() - timedelta(seconds=1))
    _recover(session_factory, clock)

    with _store(session_factory, clock) as store:
        snap = store.snapshot("job-1")
    assert snap.steps[0].state == "completed"
    completed_events = [
        row.event for row in snap.events if row.event.event_type.value == "step_completed"
    ]
    assert len(completed_events) == 1
    assert completed_events[0].checkpoint_id == "cp-1"
    assert completed_events[0].payload.get("recovered_from_checkpoint") is True
    assert completed_events[0].progress_completed == 1
    assert completed_events[0].progress_total == 1

    calls: list[str] = []
    def executor(ctx: StepContext) -> dict:
        calls.append(ctx.step_id)
        return {}
    runner = JobRunner(session_factory, {"demo": executor}, worker_id="w1")
    assert runner.run_job("job-1") is True
    assert calls == []  # Checkpoint 证明已完成，不重复执行
    assert job_state(session_factory, "job-1") == "completed"


def test_attempt_budget_exhausted_at_recovery_fails_final(session_factory, clock):
    steps = [{"step_id": "s1", "name": "解析", "retryable": True, "max_attempts": 1}]
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=steps)
    _claim_and_start(session_factory, clock)  # attempt 1 == max_attempts
    expire_lease(session_factory, "job-1", before=clock.now() - timedelta(seconds=1))
    report = _recover(session_factory, clock)
    assert report.recovered_jobs == ["job-1"]
    assert report.failed_final_jobs == ["job-1"]
    assert report.requeued_jobs == []
    with _store(session_factory, clock) as store:
        snap = store.snapshot("job-1")
    assert snap.state == "failed_final"
    assert snap.steps[0].state == "failed_final"
    assert snap.steps[0].error_code == "RECOVERY_RESET"
    assert snap.events[-1].event.event_type.value == "failed"
    # 不存在永久 processing
    assert job_state(session_factory, "job-1") != "running"


def test_unexpired_lease_is_untouched(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    _claim_and_start(session_factory, clock)
    report = _recover(session_factory, clock)
    assert report.touched == 0
    with _store(session_factory, clock) as store:
        snap = store.snapshot("job-1")
    assert snap.state == "running"
    assert snap.steps[0].state == "running"


def test_expired_cancel_request_cancels_directly(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    lease = _claim_and_start(session_factory, clock)
    with _store(session_factory, clock) as store:
        store.request_cancel("job-1")  # state=cancel_requested，但 worker 未处理即被杀
    expire_lease(session_factory, "job-1", before=clock.now() - timedelta(seconds=1))
    report = _recover(session_factory, clock)
    assert report.cancelled_jobs == ["job-1"]
    with _store(session_factory, clock) as store:
        snap = store.snapshot("job-1")
    assert snap.state == "cancelled"
    assert snap.steps[0].state == "cancelled"
    kinds = [row.event.event_type.value for row in snap.events]
    assert "cancel_requested" in kinds
    assert "cancelled" in kinds


def test_recovering_job_claimed_directly_is_prepared(session_factory, clock):
    """即使没有启动期扫描，直接认领 recovering 任务也会按恢复规则重置。"""
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    _claim_and_start(session_factory, clock)
    # 只执行恢复第一阶段：running -> recovering
    with _store(session_factory, clock) as store:
        assert store.mark_expired_running() == []
    expire_lease(session_factory, "job-1", before=clock.now() - timedelta(seconds=1))
    with _store(session_factory, clock) as store:
        assert store.mark_expired_running() == ["job-1"]
    assert job_state(session_factory, "job-1") == "recovering"

    calls: list[str] = []
    def executor(ctx: StepContext) -> dict:
        calls.append(ctx.step_id)
        return {}
    runner = JobRunner(session_factory, {"demo": executor}, worker_id="w1")
    assert runner.run_job("job-1") is True  # 认领 recovering -> prepare -> 执行
    assert calls == ["s1"]
    assert job_state(session_factory, "job-1") == "completed"


def test_recovery_preserves_checkpoint_rows_and_history(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    lease = _claim_and_start(session_factory, clock)
    expire_lease(session_factory, "job-1", before=clock.now() - timedelta(seconds=1))
    _recover(session_factory, clock)
    with _store(session_factory, clock) as store:
        snap = store.snapshot("job-1")
    # 历史事件（created/step_started）与恢复事件共存，序号单调
    seqs = [row.seq for row in snap.events]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)
    assert "created" in [row.event.event_type.value for row in snap.events]
