"""PreparedStepResult 的租约写栅栏与事务原子性回归。"""
from __future__ import annotations

import pytest
from datetime import timedelta
from sqlalchemy import select, text, update

from app.storage.models import JobRecord
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner, PreparedStepResult, StepContext
from tests.v2.workflow.conftest import create_job_with_steps


def _create_side_effect_table(session_factory) -> None:
    with session_factory() as session, session.begin():
        session.execute(
            text(
                "CREATE TABLE prepared_step_side_effects ("
                "id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
            )
        )


def _side_effect_values(session_factory) -> list[str]:
    with session_factory() as session:
        return list(
            session.execute(
                text("SELECT value FROM prepared_step_side_effects ORDER BY id")
            ).scalars()
        )


def _workflow_result(session_factory, clock) -> tuple[str, int, int, list[str]]:
    with session_factory() as session:
        store = JobStore(session, now=clock.now)
        snapshot = store.snapshot("job-1")
        checkpoint_count = len(store.list_checkpoints("job-1", "s1"))
    return (
        snapshot.steps[0].state,
        snapshot.progress_completed,
        checkpoint_count,
        [row.event.event_type.value for row in snapshot.events],
    )


def test_lost_lease_fence_skips_apply_and_all_domain_side_effects(
    session_factory, clock
):
    create_job_with_steps(
        session_factory,
        clock,
        steps=[{"step_id": "s1", "name": "发布"}],
    )
    _create_side_effect_table(session_factory)
    apply_calls: list[str] = []

    def executor(_context: StepContext) -> PreparedStepResult:
        # 模拟计算完成后已被恢复器/新 worker 夺走 generation。
        with session_factory() as session, session.begin():
            session.execute(
                update(JobRecord)
                .where(JobRecord.job_id == "job-1")
                .values(
                    lease_owner="w2",
                    lease_generation=JobRecord.lease_generation + 1,
                )
            )

        def apply(session) -> None:
            apply_calls.append("called")
            session.execute(
                text("INSERT INTO prepared_step_side_effects(value) VALUES ('lost')")
            )

        return PreparedStepResult(checkpoint={"published": True}, apply=apply)

    runner = JobRunner(
        session_factory,
        {"demo": executor},
        worker_id="w1",
        now=clock.now,
    )
    assert runner.run_job("job-1") is True

    assert apply_calls == []
    assert _side_effect_values(session_factory) == []
    step_state, progress, checkpoint_count, events = _workflow_result(
        session_factory, clock
    )
    assert step_state == "running"
    assert progress == 0
    assert checkpoint_count == 0
    assert "step_completed" not in events


def test_apply_failure_rolls_back_domain_checkpoint_step_progress_and_event(
    session_factory, clock
):
    create_job_with_steps(
        session_factory,
        clock,
        steps=[{"step_id": "s1", "name": "发布"}],
    )
    _create_side_effect_table(session_factory)

    def executor(_context: StepContext) -> PreparedStepResult:
        def apply(session) -> None:
            session.execute(
                text("INSERT INTO prepared_step_side_effects(value) VALUES ('partial')")
            )
            session.flush()
            raise RuntimeError("领域写入中途失败")

        return PreparedStepResult(checkpoint={"published": True}, apply=apply)

    runner = JobRunner(
        session_factory,
        {"demo": executor},
        worker_id="w1",
        now=clock.now,
    )
    assert runner.run_job("job-1") is True

    assert _side_effect_values(session_factory) == []
    step_state, progress, checkpoint_count, events = _workflow_result(
        session_factory, clock
    )
    assert step_state == "failed_final"
    assert progress == 0
    assert checkpoint_count == 0
    assert "step_completed" not in events
    assert "step_failed" in events


def test_success_commits_domain_write_and_checkpoint_together(session_factory, clock):
    create_job_with_steps(
        session_factory,
        clock,
        steps=[{"step_id": "s1", "name": "发布"}],
    )
    _create_side_effect_table(session_factory)
    apply_transaction_states: list[bool] = []

    def executor(_context: StepContext) -> PreparedStepResult:
        def apply(session) -> None:
            apply_transaction_states.append(session.in_transaction())
            session.execute(
                text("INSERT INTO prepared_step_side_effects(value) VALUES ('published')")
            )
            session.flush()

        return PreparedStepResult(checkpoint={"published": True}, apply=apply)

    runner = JobRunner(
        session_factory,
        {"demo": executor},
        worker_id="w1",
        now=clock.now,
    )
    assert runner.run_job("job-1") is True

    assert apply_transaction_states == [True]
    assert _side_effect_values(session_factory) == ["published"]
    step_state, progress, checkpoint_count, events = _workflow_result(
        session_factory, clock
    )
    assert step_state == "completed"
    assert progress == 1
    assert checkpoint_count == 1
    assert events.count("step_completed") == 1

    with session_factory() as session:
        row = session.execute(
            select(JobRecord.state, JobRecord.progress_completed).where(
                JobRecord.job_id == "job-1"
            )
        ).one()
        assert row == ("completed", 1)


def test_long_apply_refreshes_expired_lease_before_atomic_completion(
    session_factory, clock
):
    create_job_with_steps(
        session_factory,
        clock,
        steps=[{"step_id": "s1", "name": "发布"}],
    )
    _create_side_effect_table(session_factory)

    def executor(_context: StepContext) -> PreparedStepResult:
        def apply(session) -> None:
            session.execute(
                text("INSERT INTO prepared_step_side_effects(value) VALUES ('slow')")
            )
            clock.advance(1.0)

        return PreparedStepResult(checkpoint={"published": True}, apply=apply)

    runner = JobRunner(
        session_factory,
        {"demo": executor},
        worker_id="w1",
        now=clock.now,
        lease_ttl=timedelta(seconds=0.3),
    )
    assert runner.run_job("job-1") is True

    assert _side_effect_values(session_factory) == ["slow"]
    step_state, progress, checkpoint_count, events = _workflow_result(
        session_factory, clock
    )
    assert step_state == "completed"
    assert progress == 1
    assert checkpoint_count == 1
    assert events.count("step_completed") == 1


def test_apply_cannot_commit_runner_owned_transaction(session_factory, clock):
    create_job_with_steps(
        session_factory,
        clock,
        steps=[{"step_id": "s1", "name": "发布"}],
    )
    _create_side_effect_table(session_factory)

    def executor(_context: StepContext) -> PreparedStepResult:
        def apply(session) -> None:
            session.execute(
                text("INSERT INTO prepared_step_side_effects(value) VALUES ('early')")
            )
            session.commit()

        return PreparedStepResult(checkpoint={"published": True}, apply=apply)

    runner = JobRunner(
        session_factory,
        {"demo": executor},
        worker_id="w1",
        now=clock.now,
    )
    assert runner.run_job("job-1") is True

    assert _side_effect_values(session_factory) == []
    step_state, progress, checkpoint_count, events = _workflow_result(
        session_factory, clock
    )
    assert step_state == "failed_final"
    assert progress == 0
    assert checkpoint_count == 0
    assert "step_completed" not in events
    assert "step_failed" in events
