"""用户等待边界：waiting_user 持久状态、无租约、无失败/重试、确认后重新入队。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.storage.models import JobRecord
from app.workflow.errors import JobStateConflictError, StepWaitForUser
from app.workflow.runner import JobRunner, StepContext
from app.workflow.recovery import recover_expired_jobs
from tests.v2.workflow.conftest import create_job_with_steps, store_transaction
from tests.v2.workflow.test_runner import _requeue_due, _snapshot


def _three_step_pipeline(*, wait_step: str = "confirm", awaiting: str = "identity") -> list[dict]:
    return [
        {"step_id": "prep", "name": "准备"},
        {"step_id": wait_step, "name": "确认", "depends_on": ("prep",)},
        {"step_id": "after", "name": "后续", "depends_on": (wait_step,)},
    ]


def _wait_executor(awaiting: str):
    def executor(ctx: StepContext) -> dict:
        if ctx.step_id in ("confirm", "review"):
            raise StepWaitForUser(awaiting_user=awaiting)
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
    assert snap.steps[1].attempt == 1
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
    assert snap.steps[1].attempt == 1
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
    assert snap.steps[1].attempt == 1


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
    assert snap.steps[1].attempt == 1
    assert snap.steps[2].state == "completed"
    kinds = [row.event.event_type.value for row in snap.events]
    assert kinds.count("step_failed") == 0
    assert kinds.count("retry_scheduled") == 0


def test_review_boundary_same_as_identity(session_factory, clock):
    steps = [
        {"step_id": "prep", "name": "准备"},
        {"step_id": "review", "name": "审阅", "depends_on": ("prep",)},
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
    with store_transaction(session_factory, clock) as store:
        with pytest.raises(JobStateConflictError):
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
