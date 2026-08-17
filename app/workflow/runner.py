"""JobRunner：租约驱动的后台执行循环。

- 只根据持久状态工作；进程内 task/thread 不是真相（design.md §5）；
- 每个步骤的可见变化（开始/完成/失败/取消）在独立短事务内提交，
  执行器调用发生在事务外，不持有 SQLite 写锁；
- 取消是持久请求：runner 在每个步骤开始前的安全边界检查并提交 cancelled；
- 可重试失败只重跑失败范围（退避到期后由 :meth:`JobStore.requeue_due_retries`
  重新入队）；失败范围之外的步骤不会重复执行；
- 故障注入：执行器抛出 :class:`ProcessDeath`（BaseException）模拟进程被
  强制终止 —— runner 不捕获、不清理、不写状态，恢复由租约过期 + 恢复器完成。
"""
from __future__ import annotations

import logging
import threading
import time as time_module
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, Callable, Iterator, Mapping

from sqlalchemy.orm import Session, sessionmaker

from app.storage.codecs import utc_now, verify_payload_sha256
from app.workflow.errors import LeaseLostError, ProcessDeath, StepFailure, StepWaitForUser
from app.workflow.jobstore import DEFAULT_LEASE_TTL, JobLease, JobStore
from app.workflow.recovery import recover_expired_jobs
from app.workflow.states import (
    ACTIVE_LEASE_STATES,
    EXECUTOR_ERROR_CODE,
    EXECUTOR_MISSING_CODE,
    backoff_delay,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StepContext:
    """执行器输入：任务/步骤范围 + 尝试次数 + 上次成功检查点（幂等重放依据）。"""

    job_id: str
    job_type: str
    job_payload: dict[str, Any]
    step_id: str
    name: str
    attempt: int
    last_checkpoint_id: str | None
    last_checkpoint: dict[str, Any] | None


StepExecutor = Callable[[StepContext], dict[str, Any]]
"""执行器协议：返回 checkpoint payload dict；失败抛 :class:`StepFailure`；
用户边界抛 :class:`StepWaitForUser`。"""


class JobRunner:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        executors: Mapping[str, StepExecutor],
        *,
        worker_id: str = "v2-worker",
        poll_interval: float = 0.25,
        now: Callable[[], datetime] = utc_now,
        sleep: Callable[[float], None] = time_module.sleep,
        lease_ttl: timedelta = DEFAULT_LEASE_TTL,
        backoff: Callable[[int], timedelta] = backoff_delay,
    ) -> None:
        self.session_factory = session_factory
        self.executors = dict(executors)
        self.worker_id = worker_id
        self.poll_interval = poll_interval
        self.now = now
        self.sleep = sleep
        self.lease_ttl = lease_ttl
        self.backoff = backoff
        self._stop_event = threading.Event()

    def _store(self, session: Session) -> JobStore:
        return JobStore(
            session,
            now=self.now,
            lease_ttl=self.lease_ttl,
            backoff=self.backoff,
        )

    def request_stop(self) -> None:
        self._stop_event.set()

    # -------------------------------------------------------------- 后台循环

    def serve(self, stop_event: threading.Event | None = None) -> None:
        """后台循环：维护（恢复/退避入队）-> 认领一个任务执行 -> 按间隔休眠。"""
        event = stop_event if stop_event is not None else self._stop_event
        while not event.is_set():
            try:
                self._maintenance()
                worked = self.run_once()
            except ProcessDeath:
                raise
            except Exception:
                logger.exception("后台任务循环异常，继续运行")
            self.sleep(self.poll_interval if not worked else 0.0)

    def _maintenance(self) -> None:
        with self.session_factory() as session:
            with session.begin():
                self._store(session).requeue_due_retries()
        recover_expired_jobs(self.session_factory, now=self.now)

    # -------------------------------------------------------------- 单任务

    def run_once(self, *, job_type: str | None = None) -> bool:
        """认领一个可执行任务并推进到下一个持久边界；无任务返回 False。"""
        claim = self._claim(job_type)
        if claim is None:
            return False
        lease, job_type_claimed = claim
        try:
            self._run_claimed(lease, job_type_claimed)
        except LeaseLostError:
            logger.info("任务 %s 租约失效，结果丢弃，交由恢复器处理", lease.job_id)
        return True

    def run_job(self, job_id: str) -> bool:
        """认领并执行指定任务（测试/手动重放用）；无法认领返回 False。"""
        claim = self._claim(job_id=job_id)
        if claim is None:
            return False
        lease, job_type = claim
        try:
            self._run_claimed(lease, job_type)
        except LeaseLostError:
            logger.info("任务 %s 租约失效，结果丢弃，交由恢复器处理", lease.job_id)
        return True

    def _claim(
        self, job_type: str | None = None, *, job_id: str | None = None
    ) -> tuple[JobLease, str] | None:
        with self.session_factory() as session:
            with session.begin():
                store = self._store(session)
                lease = (
                    store.claim_job(job_id, self.worker_id)
                    if job_id is not None
                    else store.claim_next(self.worker_id, job_type=job_type)
                )
                if lease is None:
                    return None
                job = store.get_job(lease.job_id)
                claimed_type = job.job_type
                # 恢复延续：认领后立刻按恢复规则重置中断步骤（幂等，普通任务为空操作）
                store.prepare_claimed(lease)
        return lease, claimed_type

    def _run_claimed(self, lease: JobLease, job_type: str) -> None:
        while True:
            lease = self._renew_if_due(lease)
            with self.session_factory() as session:
                with session.begin():
                    store = self._store(session)
                    status = store.job_status(lease.job_id)
                    if status.state not in ACTIVE_LEASE_STATES:
                        return
                    if status.cancel_requested or status.state == "cancel_requested":
                        store.cancel_at_boundary(lease)
                        return
                    step = store.next_runnable_step(lease.job_id)
                    if step is None:
                        if store.all_steps_terminal(lease.job_id):
                            if store.any_step_failed(lease.job_id):
                                store.finish_failure(lease)
                            else:
                                store.finish_success(lease)
                            return
                        store.release_deferred(lease)
                        return
                    started = store.start_step(lease, step.step_id)
                    last_checkpoint = store.get_last_checkpoint(
                        lease.job_id, started.step_id
                    )
                    context = StepContext(
                        job_id=lease.job_id,
                        job_type=job_type,
                        job_payload=self._job_payload(store, lease.job_id),
                        step_id=started.step_id,
                        name=started.name,
                        attempt=started.attempt,
                        last_checkpoint_id=last_checkpoint[0] if last_checkpoint else None,
                        last_checkpoint=last_checkpoint[1] if last_checkpoint else None,
                    )
                    step_id = started.step_id
            # 执行器在事务外运行：不持有写锁（执行时间超出租约由恢复器兜底）
            try:
                executor = self.executors.get(job_type)
                if executor is None:
                    raise StepFailure(
                        retryable=False,
                        error_code=EXECUTOR_MISSING_CODE,
                        detail="当前任务暂时无法执行，请联系维护人员检查任务配置。",
                    )
                with self._lease_heartbeat(lease) as lease_ref:
                    try:
                        checkpoint_payload = executor(context)
                    finally:
                        # 失败提交也必须使用心跳期间刷新的租约到期时间。
                        lease = lease_ref[0]
            except ProcessDeath:
                raise
            except StepWaitForUser as wait:
                self._commit_step_wait(lease, step_id, wait)
                return
            except StepFailure as failure:
                self._commit_step_failure(lease, step_id, failure)
                return
            except Exception as exc:  # 意外异常按 fatal 处理，避免无限重试
                logger.exception("任务 %s 步骤 %s 意外失败", lease.job_id, step_id)
                failure = StepFailure(
                    retryable=False,
                    error_code=EXECUTOR_ERROR_CODE,
                    detail=str(exc)[:500],
                )
                self._commit_step_failure(lease, step_id, failure)
                return
            self._commit_step_success(lease, step_id, checkpoint_payload)

    @contextmanager
    def _lease_heartbeat(self, lease: JobLease) -> Iterator[list[JobLease]]:
        """执行器运行期间定期续租，防止长步骤被另一进程误判为中断。

        可变单元素列表只在本方法与调用方之间传递最新租约；数据库中的
        owner/generation/expiry 仍是唯一执行权真相。心跳丢失时，执行器输出
        会被丢弃并由持久恢复流程接管。
        """
        current = [lease]
        guard = threading.Lock()
        stop = threading.Event()
        lost = threading.Event()
        interval = max(min(self.lease_ttl.total_seconds() / 3, 5.0), 0.05)

        def heartbeat() -> None:
            while not stop.wait(interval):
                with guard:
                    active = current[0]
                renewed_at = self.now()
                with self.session_factory() as session:
                    with session.begin():
                        renewed = self._store(session).renew_lease(active)
                if not renewed:
                    lost.set()
                    return
                with guard:
                    current[0] = replace(
                        active,
                        expires_at=renewed_at + self.lease_ttl,
                    )

        thread = threading.Thread(
            target=heartbeat,
            name=f"v2-lease-heartbeat-{lease.job_id[:12]}",
            daemon=True,
        )
        thread.start()
        try:
            yield current
        finally:
            stop.set()
            thread.join(timeout=max(interval * 2, 1.0))
            if thread.is_alive():
                lost.set()
            if lost.is_set():
                raise LeaseLostError(
                    f"任务 {lease.job_id} 执行期间租约续期失败，结果已丢弃"
                )

    def _commit_step_success(self, lease: JobLease, step_id: str, checkpoint: dict) -> None:
        lease = self._renew_if_due(lease)
        with self.session_factory() as session:
            with session.begin():
                self._store(session).complete_step(
                    lease, step_id, checkpoint_payload=checkpoint
                )

    def _commit_step_failure(self, lease: JobLease, step_id: str, failure: StepFailure) -> None:
        lease = self._renew_if_due(lease)
        with self.session_factory() as session:
            with session.begin():
                self._store(session).fail_step(
                    lease,
                    step_id,
                    error_code=failure.error_code,
                    retryable=failure.retryable,
                    detail=failure.detail,
                )

    def _commit_step_wait(
        self, lease: JobLease, step_id: str, wait: StepWaitForUser
    ) -> None:
        lease = self._renew_if_due(lease)
        with self.session_factory() as session:
            with session.begin():
                self._store(session).wait_for_user(
                    lease,
                    step_id,
                    awaiting_user=wait.awaiting_user,
                    checkpoint_payload=wait.checkpoint_payload,
                )

    def _job_payload(self, store: JobStore, job_id: str) -> dict[str, Any]:
        job = store.get_job(job_id)
        return verify_payload_sha256(job.payload_json, job.payload_sha256)

    def _renew_if_due(self, lease: JobLease) -> JobLease:
        """租约剩余不足 1/3 时续租；失败不阻断，交由后续提交的租约校验裁决。"""
        if lease.expires_at - self.now() > self.lease_ttl / 3:
            return lease
        with self.session_factory() as session:
            with session.begin():
                if self._store(session).renew_lease(lease):
                    return replace(lease, expires_at=self.now() + self.lease_ttl)
        return lease
