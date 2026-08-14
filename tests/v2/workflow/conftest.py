"""workflow 测试夹具：假时钟与任务/租约操作助手。"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from sqlalchemy import update

from app.domain.contracts.enums import JobEventType
from app.storage.codecs import utc_now
from app.storage.models import JobRecord
from app.workflow.jobstore import DEFAULT_LEASE_TTL, JobStore


class FakeClock:
    """可推进的假时钟：租约/退避测试的确定性来源。"""

    def __init__(self, start: datetime | None = None) -> None:
        self.value = start or datetime(2026, 8, 14, 0, 0, 0)

    def now(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> datetime:
        self.value += timedelta(seconds=seconds)
        return self.value


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@contextmanager
def store_transaction(session_factory, clock: FakeClock):
    """上下文管理器：一个短事务内的 JobStore（假时钟）。"""
    with session_factory() as session:
        with session.begin():
            yield JobStore(
                session,
                now=clock.now,
                lease_ttl=DEFAULT_LEASE_TTL,
            )


def create_job_with_steps(
    session_factory,
    clock: FakeClock,
    *,
    job_id: str = "job-1",
    job_type: str = "demo",
    steps: list[dict] | None = None,
    payload: dict | None = None,
) -> None:
    """在一个事务内创建任务与步骤。

    步骤字典键：step_id/name/max_attempts/retryable/depends_on。
    """
    with session_factory() as session:
        with session.begin():
            store = JobStore(session, now=clock.now)
            store.create_job(
                job_id=job_id,
                job_type=job_type,
                payload=payload,
                progress_total=len(steps or []),
            )
            for spec in steps or []:
                store.create_step(
                    step_id=spec["step_id"],
                    job_id=job_id,
                    name=spec.get("name", spec["step_id"]),
                    max_attempts=spec.get("max_attempts", 1),
                    retryable=spec.get("retryable", False),
                    depends_on=tuple(spec.get("depends_on", ())),
                )
            store.append_event(
                store.make_event(
                    job_id=job_id,
                    event_type=JobEventType.CREATED,
                    progress_total=len(steps or []),
                )
            )


def expire_lease(session_factory, job_id: str, *, before: datetime) -> None:
    """模拟进程死亡后租约自然过期（Core 直改到期时间到过去）。"""
    with session_factory() as session:
        with session.begin():
            session.execute(
                update(JobRecord)
                .where(JobRecord.job_id == job_id)
                .values(
                    lease_expires_at=before,
                    revision=JobRecord.revision + 1,
                    updated_at=before,
                )
            )


def job_state(session_factory, job_id: str) -> str:
    with session_factory() as session:
        store = JobStore(session, now=utc_now)
        return store.job_status(job_id).state
