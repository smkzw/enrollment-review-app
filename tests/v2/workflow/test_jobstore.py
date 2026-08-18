"""JobStore 租约与状态机写入：claim/续租/步骤事务/取消/重试/事件序号。"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import select

from app.domain.contracts.enums import JobEventType
from app.storage.models import JobCheckpointRecord
from app.workflow.errors import (
    JobNotFoundError,
    JobStateConflictError,
    LeaseLostError,
    StepDeferredError,
    StepMismatchError,
)
from app.workflow.jobstore import DEFAULT_LEASE_TTL, JobLease, JobStore
from tests.v2.workflow.conftest import create_job_with_steps

STEPS = [{"step_id": "s1", "name": "解析", "retryable": True, "max_attempts": 3}]


def _store(session_factory, clock):
    """每操作一个短事务的 JobStore 工厂。"""
    class _T:
        def __enter__(self):
            session = session_factory()
            self.session = session
            self.tx = session.begin()
            return JobStore(session, now=clock.now, lease_ttl=DEFAULT_LEASE_TTL)

        def __exit__(self, *exc):
            if exc[0] is None:
                self.tx.commit()
            else:
                self.tx.rollback()
            self.session.close()
            return False

    return _T()


def _claim(session_factory, clock, worker_id="w1", job_type=None):
    with _store(session_factory, clock) as store:
        return store.claim_next(worker_id, job_type=job_type)


def _snapshot(session_factory, clock, job_id):
    with _store(session_factory, clock) as store:
        return store.snapshot(job_id)


def test_create_job_emits_created_event_with_monotonic_seq(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.state == "queued"
    assert snap.progress_total == 1
    assert snap.progress_completed == 0
    assert snap.last_event_seq == 1
    assert len(snap.steps) == 1
    assert snap.steps[0].state == "queued"
    assert snap.steps[0].attempt == 0
    assert [row.seq for row in snap.events] == [1]
    assert snap.events[0].event.event_type.value == "created"


def test_claim_assigns_lease_and_blocks_second_claim(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    lease = _claim(session_factory, clock, "w1")
    assert lease is not None
    assert lease.owner == "w1"
    assert lease.generation == 1
    assert lease.expires_at == clock.now() + DEFAULT_LEASE_TTL
    assert _snapshot(session_factory, clock, "job-1").state == "running"

    # 有有效租约 -> 其他 worker 不可领取
    assert _claim(session_factory, clock, "w2") is None

    # 租约过期 -> 不可直接认领（必须先经恢复器 running->recovering->queued）
    from app.workflow.recovery import recover_expired_jobs

    clock.advance(DEFAULT_LEASE_TTL.total_seconds() + 1)
    assert _claim(session_factory, clock, "w2") is None
    report = recover_expired_jobs(session_factory, now=clock.now)
    assert report.recovered_jobs == ["job-1"]
    second = _claim(session_factory, clock, "w2")
    assert second is not None
    assert second.owner == "w2"
    assert second.generation == 3  # 首次认领 +1，恢复器标记 recovering +1，再认领 +1


def test_expired_lease_can_renew_until_recovery_changes_ownership(session_factory, clock):
    from app.workflow.recovery import recover_expired_jobs

    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    lease = _claim(session_factory, clock, "w1")
    with _store(session_factory, clock) as store:
        assert store.renew_lease(lease) is True
    renewed = replace(lease, expires_at=clock.now() + DEFAULT_LEASE_TTL)
    with _store(session_factory, clock) as store:
        assert store.renew_lease(renewed) is True

    clock.advance(DEFAULT_LEASE_TTL.total_seconds() + 1)
    with _store(session_factory, clock) as store:
        assert store.renew_lease(renewed) is True

    # 本机暂停后迟到心跳可恢复；只有再次过期并由恢复器接管，旧租约才失权。
    clock.advance(DEFAULT_LEASE_TTL.total_seconds() + 1)
    assert _claim(session_factory, clock, "w2") is None
    recover_expired_jobs(session_factory, now=clock.now)
    second = _claim(session_factory, clock, "w2")
    assert second is not None
    with _store(session_factory, clock) as store:
        assert store.renew_lease(renewed) is False

def test_complete_step_writes_checkpoint_progress_and_event(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    lease = _claim(session_factory, clock, "w1")
    with _store(session_factory, clock) as store:
        store.start_step(lease, "s1")
    with _store(session_factory, clock) as store:
        seq = store.complete_step(lease, "s1", checkpoint_payload={"ok": True})
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.steps[0].state == "completed"
    assert snap.steps[0].attempt == 1
    assert snap.progress_completed == 1
    assert snap.state == "running"  # 还有最后一步边界：任务仍在运行，等待 finish
    events = [row.event.event_type.value for row in snap.events]
    assert events == ["created", "step_started", "step_completed"]
    assert seq == 3
    # checkpoint 行与 payload 可读回
    with _store(session_factory, clock) as store:
        last = store.get_last_checkpoint("job-1", "s1")
    assert last is not None
    assert last[1]["ok"] is True
    assert last[1]["attempt"] == 1
    # 完成后再提交 -> 状态冲突
    with _store(session_factory, clock) as store:
        with pytest.raises(StepMismatchError):
            store.complete_step(lease, "s1", checkpoint_payload={"again": True})


def test_complete_step_rejects_wrong_owner(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    lease = _claim(session_factory, clock, "w1")
    with _store(session_factory, clock) as store:
        store.start_step(lease, "s1")
    impostor = replace(lease, owner="w2")
    with _store(session_factory, clock) as store:
        with pytest.raises(LeaseLostError):
            store.complete_step(impostor, "s1", checkpoint_payload={})
    # 结果被丢弃：无 checkpoint、步骤仍 running
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.steps[0].state == "running"
    assert snap.progress_completed == 0
    with _store(session_factory, clock) as store:
        assert store.get_last_checkpoint("job-1", "s1") is None


def test_complete_step_rejects_wrong_generation(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    lease = _claim(session_factory, clock, "w1")
    with _store(session_factory, clock) as store:
        store.start_step(lease, "s1")
    stale = replace(lease, generation=lease.generation + 5)
    with _store(session_factory, clock) as store:
        with pytest.raises(LeaseLostError):
            store.complete_step(stale, "s1", checkpoint_payload={})
    assert _snapshot(session_factory, clock, "job-1").steps[0].state == "running"


def test_complete_step_rejects_expired_lease(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    lease = _claim(session_factory, clock, "w1")
    with _store(session_factory, clock) as store:
        store.start_step(lease, "s1")
    clock.advance(DEFAULT_LEASE_TTL.total_seconds() + 1)
    with _store(session_factory, clock) as store:
        with pytest.raises(LeaseLostError):
            store.complete_step(lease, "s1", checkpoint_payload={})
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.steps[0].state == "running"
    with _store(session_factory, clock) as store:
        assert store.get_last_checkpoint("job-1", "s1") is None


def test_start_step_increments_attempt_and_step_deferred_rejected(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    lease = _claim(session_factory, clock, "w1")
    with _store(session_factory, clock) as store:
        store.start_step(lease, "s1")
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.steps[0].attempt == 1
    assert snap.steps[0].state == "running"
    assert snap.events[-1].event.event_type.value == "step_started"
    assert snap.events[-1].event.attempt == 1
    # 重复启动 -> 状态冲突
    with _store(session_factory, clock) as store:
        with pytest.raises(StepMismatchError):
            store.start_step(lease, "s1")
    # 退避未到期的 failed_retryable 步骤 -> StepDeferredError
    with _store(session_factory, clock) as store:
        store.fail_step(lease, "s1", error_code="E1", retryable=True)
    assert _snapshot(session_factory, clock, "job-1").state == "failed_retryable"
    clock.advance(0.6)
    with _store(session_factory, clock) as store:
        store.requeue_due_retries()
    lease2 = _claim(session_factory, clock, "w1")
    with _store(session_factory, clock) as store:
        store.start_step(lease2, "s1")
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.steps[0].attempt == 2
    assert snap.steps[0].retry_not_before is None  # 启动即清除退避标记


def test_fail_step_retryable_schedules_backoff_and_requeues_when_due(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    lease = _claim(session_factory, clock, "w1")
    with _store(session_factory, clock) as store:
        store.start_step(lease, "s1")
    with _store(session_factory, clock) as store:
        outcome = store.fail_step(lease, "s1", error_code="E_RETRY", retryable=True)
    assert outcome.job_state == "failed_retryable"
    assert outcome.step_state == "failed_retryable"
    assert outcome.exhausted is False
    assert outcome.retry_not_before == clock.now() + timedelta(seconds=0.5)

    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.state == "failed_retryable"
    assert snap.steps[0].state == "failed_retryable"
    assert snap.steps[0].error_code == "E_RETRY"
    assert snap.steps[0].error_classification == "retryable"
    assert snap.events[-2].event.event_type.value == "step_failed"
    assert snap.events[-2].event.retryable is True
    assert snap.events[-1].event.event_type.value == "retry_scheduled"

    # 退避未到期 -> 不重新入队；到期 -> 回到 queued
    with _store(session_factory, clock) as store:
        assert store.requeue_due_retries() == []
    clock.advance(0.6)
    with _store(session_factory, clock) as store:
        assert store.requeue_due_retries() == ["job-1"]
    assert _snapshot(session_factory, clock, "job-1").state == "queued"


def test_fail_step_non_retryable_fails_job_and_cascades_downstream(session_factory, clock):
    steps = [
        {"step_id": "s1", "name": "解析"},
        {"step_id": "s2", "name": "审核", "depends_on": ("s1",)},
        {"step_id": "s3", "name": "复核", "depends_on": ("s2",)},
    ]
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=steps)
    lease = _claim(session_factory, clock, "w1")
    with _store(session_factory, clock) as store:
        store.start_step(lease, "s1")
    with _store(session_factory, clock) as store:
        store.fail_step(lease, "s1", error_code="E_FATAL", retryable=False)
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.state == "failed_final"
    states = {step.step_id: step.state for step in snap.steps}
    assert states == {"s1": "failed_final", "s2": "failed_final", "s3": "failed_final"}
    codes = {step.step_id: step.error_code for step in snap.steps}
    assert codes["s1"] == "E_FATAL"
    assert codes["s2"] == "DEPENDENCY_FAILED"
    assert codes["s3"] == "DEPENDENCY_FAILED"
    # 下游失败有事件与溯源
    dependency_events = [
        row.event for row in snap.events
        if row.event.event_type.value == "step_failed" and row.event.step_id in ("s2", "s3")
    ]
    assert len(dependency_events) == 2
    assert all(e.payload.get("depends_on_step_id") == "s1" for e in dependency_events)
    assert all(e.progress_total == 3 for e in dependency_events)
    assert snap.events[-1].event.event_type.value == "failed"


def test_fail_step_budget_exhausted_goes_final(session_factory, clock):
    steps = [{"step_id": "s1", "name": "解析", "retryable": True, "max_attempts": 1}]
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=steps)
    lease = _claim(session_factory, clock, "w1")
    with _store(session_factory, clock) as store:
        store.start_step(lease, "s1")  # attempt 1 == max_attempts
    with _store(session_factory, clock) as store:
        outcome = store.fail_step(lease, "s1", error_code="E1", retryable=True)
    assert outcome.exhausted is True
    assert outcome.job_state == "failed_final"
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.state == "failed_final"
    assert snap.steps[0].state == "failed_final"
    failed_event = [
        row.event for row in snap.events if row.event.event_type.value == "step_failed"
    ][-1]
    assert failed_event.event_type.value == "step_failed"
    assert failed_event.retryable is False
    assert failed_event.payload.get("attempt_exhausted") is True
    assert snap.events[-1].event.event_type.value == "failed"


def test_request_cancel_on_running_job_persists_then_boundary_cancels(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    lease = _claim(session_factory, clock, "w1")
    with _store(session_factory, clock) as store:
        outcome = store.request_cancel("job-1")
    assert outcome.state == "cancel_requested"
    assert outcome.changed is True
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.cancel_requested is True
    assert snap.events[-1].event.event_type.value == "cancel_requested"
    # worker 在安全边界执行取消
    with _store(session_factory, clock) as store:
        store.cancel_at_boundary(lease)
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.state == "cancelled"
    assert snap.steps[0].state == "cancelled"
    assert snap.events[-1].event.event_type.value == "cancelled"


def test_request_cancel_on_queued_job_cancels_directly(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    with _store(session_factory, clock) as store:
        outcome = store.request_cancel("job-1")
    assert outcome.state == "cancelled"
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.steps[0].state == "cancelled"
    assert snap.events[-1].event.event_type.value == "cancelled"
    # 取消后的任务不可被领取
    assert _claim(session_factory, clock, "w1") is None


def test_request_cancel_on_terminal_job_is_noop(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    lease = _claim(session_factory, clock, "w1")
    with _store(session_factory, clock) as store:
        store.start_step(lease, "s1")
        store.complete_step(lease, "s1", checkpoint_payload={})
        store.finish_success(lease)
    with _store(session_factory, clock) as store:
        outcome = store.request_cancel("job-1")
    assert outcome.changed is False
    assert outcome.state == "completed"
    snap = _snapshot(session_factory, clock, "job-1")
    assert [e.event.event_type.value for e in snap.events].count("cancel_requested") == 0


def test_cancel_wins_at_failure_boundary(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    lease = _claim(session_factory, clock, "w1")
    with _store(session_factory, clock) as store:
        store.start_step(lease, "s1")
        store.request_cancel("job-1")
    with _store(session_factory, clock) as store:
        outcome = store.fail_step(lease, "s1", error_code="E1", retryable=True)
    assert outcome.job_state == "cancelled"
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.state == "cancelled"
    kinds = [e.event.event_type.value for e in snap.events]
    assert "step_failed" in kinds  # 失败历史保留
    assert "cancelled" in kinds
    assert "retry_scheduled" not in kinds  # 不再安排重试


def test_retry_resets_only_failed_scope(session_factory, clock):
    steps = [
        {"step_id": "s1", "name": "解析"},
        {"step_id": "s2", "name": "审核", "depends_on": ("s1",)},
    ]
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=steps)
    lease = _claim(session_factory, clock, "w1")
    with _store(session_factory, clock) as store:
        store.start_step(lease, "s1")
        store.complete_step(lease, "s1", checkpoint_payload={})
        store.start_step(lease, "s2")
        store.fail_step(lease, "s2", error_code="E_FATAL", retryable=False)
    assert _snapshot(session_factory, clock, "job-1").state == "failed_final"

    with _store(session_factory, clock) as store:
        outcome = store.retry_failed("job-1")
    assert outcome.state == "queued"
    assert outcome.changed is True
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.state == "queued"
    states = {step.step_id: step.state for step in snap.steps}
    assert states == {"s1": "completed", "s2": "queued"}  # 已完成步骤不重跑
    assert snap.steps[1].error_code is None
    assert snap.steps[1].retry_not_before is None
    retry_event = snap.events[-1].event
    assert retry_event.event_type.value == "retry_scheduled"
    assert retry_event.payload.get("retry_scope") == ["s2"]


def test_retry_rejects_non_failed_job(session_factory, clock):
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    with _store(session_factory, clock) as store:
        with pytest.raises(JobStateConflictError):
            store.retry_failed("job-1")


def test_snapshot_and_event_resume_without_duplicates(session_factory, clock):
    steps = [
        {"step_id": "s1", "name": "解析"},
        {"step_id": "s2", "name": "审核", "depends_on": ("s1",)},
    ]
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=steps)
    lease = _claim(session_factory, clock, "w1")
    with _store(session_factory, clock) as store:
        store.start_step(lease, "s1")
        store.complete_step(lease, "s1", checkpoint_payload={})
        store.start_step(lease, "s2")
        store.complete_step(lease, "s2", checkpoint_payload={})
        store.finish_success(lease)
    with _store(session_factory, clock) as store:
        rows = store.list_event_rows("job-1", after_seq=0)
    seqs = [row.seq for row in rows]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)
    assert seqs == [1, 2, 3, 4, 5, 6]
    with _store(session_factory, clock) as store:
        resumed = store.list_event_rows("job-1", after_seq=3)
    assert [row.seq for row in resumed] == [4, 5, 6]
    snap = _snapshot(session_factory, clock, "job-1")
    assert snap.last_event_seq == 6
    assert snap.events[-1].event.event_type.value == "completed"


def test_concurrent_sessions_allocate_event_sequences_atomically(session_factory, clock):
    """多个真实写会话同时追加事件，序号仍连续且无冲突。"""
    create_job_with_steps(session_factory, clock, job_id="job-1", steps=STEPS)
    workers = 8
    barrier = Barrier(workers)

    def append_one(index: int) -> int:
        with session_factory() as session:
            with session.begin():
                store = JobStore(session, now=clock.now)
                event = store.make_event(
                    job_id="job-1",
                    event_type=JobEventType.RETRY_SCHEDULED,
                    payload={"worker": index},
                )
                barrier.wait(timeout=5)
                return store.append_event(event)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        assigned = list(pool.map(append_one, range(workers)))

    assert sorted(assigned) == list(range(2, workers + 2))
    snapshot = _snapshot(session_factory, clock, "job-1")
    assert [row.seq for row in snapshot.events] == list(range(1, workers + 2))
    assert snapshot.last_event_seq == workers + 1


def test_unknown_job_raises_not_found(session_factory, clock):
    with _store(session_factory, clock) as store:
        with pytest.raises(JobNotFoundError):
            store.snapshot("missing")
        with pytest.raises(JobNotFoundError):
            store.job_status("missing")
