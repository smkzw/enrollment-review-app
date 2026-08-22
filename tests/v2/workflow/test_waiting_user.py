"""用户等待边界：waiting_user 持久状态、无租约、无失败/重试、确认后重新入队。"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.storage.models import JobRecord
from app.workflow.errors import JobStateConflictError, StepAwaitingUser
from app.workflow.recovery import recover_expired_jobs
from app.workflow.runner import JobRunner, StepContext
from tests.v2.workflow.conftest import (
    create_job_with_steps,
    expire_lease,
    store_transaction,
)
from tests.v2.workflow.test_runner import _requeue_due, _snapshot


def _three_step_pipeline(*, wait_step: str = "confirm", awaiting: str = "identity") -> list[dict]:
    return [
        {"step_id": "prep", "name": "准备"},
        {
            "step_id": wait_step,
            "name": "确认",
            "waiting_user_kind": awaiting,
            "depends_on": ("prep",),
        },
        {"step_id": "after", "name": "后续", "depends_on": (wait_step,)},
    ]


def _wait_executor(awaiting: str):
    def executor(ctx: StepContext) -> dict:
        return {"step": ctx.step_id}

    return executor


def test_user_wait_transitions_to_waiting_without_failure_events(session_factory, clock):
    create_job_with_steps(
        session_factory,
        clock,
        job_id="job-wait",
        steps=_three_step_pipeline(),
    )
    runner = JobRunner(
        session_factory,
        {"demo": _wait_executor("identity")},
        worker_id="w1",
        now=clock.now,
    )
    assert runner.run_job("job-wait") is True
    snap = _snapshot(session_factory, clock, "job-wait")
    assert snap.state == "waiting_user"
    assert snap.steps[1].state == "waiting_user"
    assert snap.steps[1].attempt == 0
    job = snap
    assert job.steps[0].state == "completed"
    kinds = [row.event.event_type.value for row in snap.events]
    assert "waiting_user" in kinds
    assert "step_failed" not in kinds
    assert "retry_scheduled" not in kinds
    with session_factory() as session:
        row = session.execute(
            select(JobRecord.lease_owner, JobRecord.lease_expires_at).where(
                JobRecord.job_id == "job-wait"
            )
        ).one()
        assert row.lease_owner is None
        assert row.lease_expires_at is None


def test_waiting_job_cannot_be_claimed(session_factory, clock):
    create_job_with_steps(
        session_factory,
        clock,
        job_id="job-wait",
        steps=_three_step_pipeline(),
    )
    runner = JobRunner(
        session_factory,
        {"demo": _wait_executor("identity")},
        worker_id="w1",
        now=clock.now,
    )
    runner.run_job("job-wait")
    assert runner.run_job("job-wait") is False
    assert runner.run_once() is False


def test_maintenance_does_not_increase_attempt(session_factory, clock):
    create_job_with_steps(
        session_factory,
        clock,
        job_id="job-wait",
        steps=_three_step_pipeline(),
    )
    runner = JobRunner(
        session_factory,
        {"demo": _wait_executor("identity")},
        worker_id="w1",
        now=clock.now,
    )
    runner.run_job("job-wait")
    for _ in range(5):
        runner._maintenance()
        assert runner.run_once() is False
        assert _requeue_due(session_factory, clock) == []
    snap = _snapshot(session_factory, clock, "job-wait")
    assert snap.steps[1].attempt == 0
    assert snap.state == "waiting_user"


def test_startup_recovery_preserves_waiting_user(session_factory, clock):
    create_job_with_steps(
        session_factory,
        clock,
        job_id="job-wait",
        steps=_three_step_pipeline(),
    )
    runner = JobRunner(
        session_factory,
        {"demo": _wait_executor("identity")},
        worker_id="w1",
        now=clock.now,
    )
    runner.run_job("job-wait")
    report = recover_expired_jobs(session_factory, now=clock.now)
    assert "job-wait" not in report.recovered_jobs
    snap = _snapshot(session_factory, clock, "job-wait")
    assert snap.state == "waiting_user"
    assert snap.steps[1].attempt == 0


def test_crash_after_claim_before_wait_recovers_without_consuming_attempt(
    session_factory, clock
):
    """等待边界由步骤定义驱动，领取后进程退出也不能消耗确认步骤次数。"""
    runner = JobRunner(
        session_factory,
        {"demo": _wait_executor("identity")},
        worker_id="w1",
        now=clock.now,
    )
    create_job_with_steps(
        session_factory,
        clock,
        job_id="job-crash",
        steps=[
            {
                "step_id": "confirm",
                "name": "确认",
                "waiting_user_kind": "identity",
            }
        ],
    )
    with store_transaction(session_factory, clock) as store:
        lease = store.claim_job("job-crash", "w-crash")
        assert lease is not None
    expire_lease(
        session_factory,
        "job-crash",
        before=clock.now() - timedelta(seconds=1),
    )
    recover_expired_jobs(session_factory, now=clock.now)

    assert runner.run_job("job-crash") is True
    snap = _snapshot(session_factory, clock, "job-crash")
    assert snap.state == "waiting_user"
    assert snap.steps[0].state == "waiting_user"
    assert snap.steps[0].attempt == 0
    kinds = [row.event.event_type.value for row in snap.events]
    assert "step_started" not in kinds
    assert "step_failed" not in kinds
    assert "retry_scheduled" not in kinds


def test_complete_user_step_requeues_and_continues(session_factory, clock):
    create_job_with_steps(
        session_factory,
        clock,
        job_id="job-wait",
        steps=_three_step_pipeline(),
    )
    runner = JobRunner(
        session_factory,
        {"demo": _wait_executor("identity")},
        worker_id="w1",
        now=clock.now,
    )
    runner.run_job("job-wait")
    with store_transaction(session_factory, clock) as store:
        store.complete_user_step(
            "job-wait",
            "confirm",
            checkpoint_payload={"confirmed": True},
        )
    assert runner.run_job("job-wait") is True
    snap = _snapshot(session_factory, clock, "job-wait")
    assert snap.state == "completed"
    assert snap.steps[1].state == "completed"
    assert snap.steps[1].attempt == 0
    assert snap.steps[2].state == "completed"
    kinds = [row.event.event_type.value for row in snap.events]
    assert kinds.count("step_failed") == 0
    assert kinds.count("retry_scheduled") == 0


def test_review_boundary_same_as_identity(session_factory, clock):
    steps = [
        {"step_id": "prep", "name": "准备"},
        {
            "step_id": "review",
            "name": "审阅",
            "waiting_user_kind": "review",
            "depends_on": ("prep",),
        },
        {"step_id": "after", "name": "后续", "depends_on": ("review",)},
    ]
    create_job_with_steps(session_factory, clock, job_id="job-review", steps=steps)
    runner = JobRunner(
        session_factory,
        {"demo": _wait_executor("review")},
        worker_id="w1",
        now=clock.now,
    )
    runner.run_job("job-review")
    snap = _snapshot(session_factory, clock, "job-review")
    assert snap.state == "waiting_user"
    wait_events = [
        row for row in snap.events if row.event.event_type.value == "waiting_user"
    ]
    assert wait_events[-1].event.payload.get("awaiting_user") == "review"
    with store_transaction(session_factory, clock) as store:
        store.complete_user_step(
            "job-review",
            "review",
            checkpoint_payload={"reviewed": True},
        )
    assert runner.run_job("job-review") is True
    assert _snapshot(session_factory, clock, "job-review").state == "completed"


def test_cancel_waiting_job(session_factory, clock):
    create_job_with_steps(
        session_factory,
        clock,
        job_id="job-wait",
        steps=_three_step_pipeline(),
    )
    runner = JobRunner(
        session_factory,
        {"demo": _wait_executor("identity")},
        worker_id="w1",
        now=clock.now,
    )
    runner.run_job("job-wait")
    with store_transaction(session_factory, clock) as store:
        outcome = store.request_cancel("job-wait")
    assert outcome.state == "cancelled"
    snap = _snapshot(session_factory, clock, "job-wait")
    assert snap.state == "cancelled"
    assert snap.steps[1].state == "cancelled"


def test_complete_user_step_rejects_non_waiting_state(session_factory, clock):
    create_job_with_steps(
        session_factory,
        clock,
        job_id="job-wait",
        steps=_three_step_pipeline(),
    )
    with (
        store_transaction(session_factory, clock) as store,
        pytest.raises(JobStateConflictError),
    ):
        store.complete_user_step(
            "job-wait",
            "confirm",
            checkpoint_payload={"confirmed": True},
        )
    runner = JobRunner(
        session_factory,
        {"demo": _wait_executor("identity")},
        worker_id="w1",
        now=clock.now,
    )
    runner.run_job("job-wait")
    with store_transaction(session_factory, clock) as store:
        store.complete_user_step(
            "job-wait",
            "confirm",
            checkpoint_payload={"confirmed": True},
        )
        with pytest.raises(JobStateConflictError):
            store.complete_user_step(
                "job-wait",
                "confirm",
                checkpoint_payload={"confirmed": True},
            )


def test_running_step_can_pause_and_resume_same_step_without_failure(
    session_factory, clock
):
    """执行器发现业务核对项时，持久暂停同一步骤，核对后重新排队。"""
    create_job_with_steps(
        session_factory,
        clock,
        job_id="job-dynamic-review",
        steps=[{"step_id": "build", "name": "生成资料版本"}],
    )
    calls = 0

    def executor(ctx: StepContext) -> dict:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise StepAwaitingUser(
                awaiting_user="evidence_review",
                checkpoint={"candidate_id": "candidate-1"},
            )
        return {"candidate_id": "candidate-1", "status": "ready"}

    runner = JobRunner(
        session_factory,
        {"demo": executor},
        worker_id="w1",
        now=clock.now,
    )
    assert runner.run_job("job-dynamic-review") is True
    waiting = _snapshot(session_factory, clock, "job-dynamic-review")
    assert waiting.state == "waiting_user"
    assert waiting.steps[0].state == "waiting_user"
    assert waiting.steps[0].error_code is None
    assert not any(
        row.event.event_type.value in {"step_failed", "retry_scheduled"}
        for row in waiting.events
    )

    with store_transaction(session_factory, clock) as store:
        store.resume_waiting_step(
            "job-dynamic-review",
            "build",
            checkpoint_payload={"reviewed": True},
        )
    assert _snapshot(session_factory, clock, "job-dynamic-review").state == "queued"
    assert runner.run_job("job-dynamic-review") is True
    completed = _snapshot(session_factory, clock, "job-dynamic-review")
    assert completed.state == "completed"
    assert completed.steps[0].state == "completed"
    assert calls == 2
