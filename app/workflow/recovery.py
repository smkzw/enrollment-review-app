"""启动/重启恢复：过期租约 -> recovering -> 从最后成功 Checkpoint 恢复 -> queued。

恢复器只根据持久状态工作（design.md §5）；进程内 task/thread 不是真相。
每个阶段使用独立短事务：第一阶段把过期租约任务标记为 recovering（租约清空、
generation 递增），并直接取消过期租约的取消请求任务；第二阶段逐任务从持久
Checkpoint 恢复：有 Checkpoint 的 running 步骤视为已完成（不重复执行），
其余按尝试预算重新排队或终败，最后 recovering -> queued/failed_final。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session, sessionmaker

from app.storage.codecs import utc_now
from app.workflow.jobstore import JobStore


@dataclass
class RecoveryReport:
    recovered_jobs: list[str] = field(default_factory=list)
    cancelled_jobs: list[str] = field(default_factory=list)
    requeued_jobs: list[str] = field(default_factory=list)
    failed_final_jobs: list[str] = field(default_factory=list)

    @property
    def touched(self) -> int:
        return len(self.recovered_jobs) + len(self.cancelled_jobs)


def recover_expired_jobs(
    session_factory: sessionmaker[Session],
    *,
    now: Callable[[], datetime] = utc_now,
) -> RecoveryReport:
    """扫描并恢复所有过期租约任务；无过期租约时为空操作。"""
    report = RecoveryReport()
    with session_factory() as session:
        with session.begin():
            store = JobStore(session, now=now)
            report.recovered_jobs = store.mark_expired_running()
            report.cancelled_jobs = store.cancel_expired_cancel_requests()
    for job_id in report.recovered_jobs:
        with session_factory() as session:
            with session.begin():
                store = JobStore(session, now=now)
                final_state = store.requeue_recovering(job_id)
                if final_state == "failed_final":
                    report.failed_final_jobs.append(job_id)
                else:
                    report.requeued_jobs.append(job_id)
    return report


def run_startup_recovery(
    session_factory: sessionmaker[Session],
    *,
    now: Callable[[], datetime] = utc_now,
) -> RecoveryReport:
    """V2 写服务启动入口调用：识别过期租约并恢复，保证不存在永久 processing。"""
    return recover_expired_jobs(session_factory, now=now)
