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
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Callable, Iterator, Mapping, Sequence
import fnmatch
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from app.storage.codecs import utc_now, verify_payload_sha256
from app.storage.models import JobRecord
from app.workflow.errors import (
    LeaseLostError,
    ProcessDeath,
    StepAwaitingUser,
    StepFailure,
)
from app.workflow.jobstore import (
    DEFAULT_LEASE_TTL,
    JobLease,
    JobStore,
    StepFailureOutcome,
)
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
    max_attempts: int = 1


StepApply = Callable[[Session], None]


@dataclass(frozen=True)
class PreparedStepResult:
    """事务外已计算的步骤结果。

    ``apply`` 只接收 Runner 提供的 SQLAlchemy ``Session``，必须保持短小、
    幂等，并且只能 ``flush``，不得 ``commit``。Runner 会在获得原子租约
    写栅栏后，将其与 checkpoint、step、progress 和 event 放在同一事务提交。
    """

    checkpoint: dict[str, Any]
    apply: StepApply


StepExecutionResult = dict[str, Any] | PreparedStepResult
StepExecutor = Callable[[StepContext], StepExecutionResult]
"""执行器协议：返回 checkpoint dict 或 PreparedStepResult；失败抛 StepFailure。"""


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
        on_cancelled: Callable[[str], None] | None = None,
        on_failed: Callable[[str], None] | None = None,
        max_parallel_steps: int = 1,
        job_scope: ColumnElement[bool] | None = None,
        on_maintenance: Callable[["JobRunner"], None] | None = None,
    ) -> None:
        if isinstance(max_parallel_steps, bool) or max_parallel_steps < 1:
            raise ValueError("max_parallel_steps 必须是 >= 1 的整数")
        self.session_factory = session_factory
        self.executors = dict(executors)
        registered_scope = JobRecord.job_type.in_(tuple(self.executors))
        self.job_scope = registered_scope if job_scope is None else and_(registered_scope, job_scope)
        self.worker_id = worker_id
        self.poll_interval = poll_interval
        self.now = now
        self.sleep = sleep
        self.lease_ttl = lease_ttl
        self.backoff = backoff
        self.on_cancelled = on_cancelled
        self.on_failed = on_failed
        self.max_parallel_steps = max_parallel_steps
        self.on_maintenance = on_maintenance
        self._stop_event = threading.Event()

    def _store(self, session: Session) -> JobStore:
        return JobStore(
            session,
            now=self.now,
            lease_ttl=self.lease_ttl,
            backoff=self.backoff,
            job_scope=self.job_scope,
        )

    def request_stop(self) -> None:
        self._stop_event.set()

    # -------------------------------------------------------------- 后台循环

    def serve(self, stop_event: threading.Event | None = None) -> None:
        """后台循环：维护（恢复/退避入队）-> 认领一个任务执行 -> 按间隔休眠。"""
        event = stop_event if stop_event is not None else self._stop_event
        while not event.is_set():
            worked = False
            try:
                self._maintenance()
                worked = self.run_once()
            except ProcessDeath:
                raise
            except Exception:
                logger.exception("后台任务循环异常，继续运行")
            self.sleep(self.poll_interval if not worked else 0.0)

    def _maintenance(self) -> None:
        with self.session_factory() as session, session.begin():
            self._store(session).requeue_due_retries()
        report = recover_expired_jobs(self.session_factory, now=self.now, job_scope=self.job_scope)
        for job_id in report.cancelled_jobs:
            self._notify_cancelled(job_id)
        for job_id in report.failed_final_jobs:
            self._notify_failed(job_id)
        if self.on_maintenance is not None:
            try:
                self.on_maintenance(self)
            except Exception:
                logger.exception("任务衔接维护未完成，其他已排队任务仍可执行")

    def lease_heartbeat(self, lease: JobLease):
        """Share the existing lease guard with bounded maintenance continuations."""
        return self._lease_heartbeat(lease)

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
        with self.session_factory() as session, session.begin():
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


    @staticmethod
    def _parallel_policy(payload: Mapping[str, Any] | None) -> tuple[int | None, set[str] | None, str]:
        """从冻结 payload 读取并行上限、白名单与前缀作用域。"""
        if not isinstance(payload, Mapping):
            return None, None, "discovery_*"
        control = payload.get("execution_control")
        if isinstance(control, Mapping):
            raw_max = control.get("max_parallel_steps")
            allow = control.get("parallelizable_step_ids")
            allowlist = (
                {item for item in allow if isinstance(item, str)}
                if isinstance(allow, list)
                else None
            )
            max_parallel = raw_max if isinstance(raw_max, int) and raw_max >= 1 else None
            return max_parallel, allowlist, "discovery_*"
        parallel_execution = payload.get("parallel_execution")
        if isinstance(parallel_execution, Mapping):
            raw_max = parallel_execution.get("max_parallel")
            scope = parallel_execution.get("scope")
            if not isinstance(scope, str) or not scope.strip():
                scope = "discovery_*"
            max_parallel = raw_max if isinstance(raw_max, int) and raw_max >= 1 else None
            return max_parallel, None, scope
        return None, None, "discovery_*"

    def _effective_parallel_limit(
        self, payload: Mapping[str, Any] | None
    ) -> tuple[int, set[str] | None, str]:
        payload_max, allowlist, scope = self._parallel_policy(payload)
        if self.max_parallel_steps <= 1:
            # Runner 默认串行；仅当任务冻结了 execution_control 时允许 payload 提升并行。
            if (
                isinstance(payload, Mapping)
                and isinstance(payload.get("execution_control"), Mapping)
                and isinstance(payload_max, int)
                and payload_max > 1
            ):
                return payload_max, allowlist, scope
            return 1, allowlist, scope
        if isinstance(payload_max, int):
            return min(self.max_parallel_steps, payload_max), allowlist, scope
        return self.max_parallel_steps, allowlist, scope

    def _select_parallel_wave(
        self,
        store: JobStore,
        job_id: str,
        payload: Mapping[str, Any] | None,
    ) -> list[Any] | None:
        limit, allowlist, scope = self._effective_parallel_limit(payload)
        if limit <= 1:
            return None
        runnables = store.list_runnable_steps(job_id)
        if len(runnables) <= 1:
            return None

        def eligible(step: Any) -> bool:
            if step.waiting_user_kind is not None:
                return False
            if allowlist is not None:
                return step.step_id in allowlist
            return fnmatch.fnmatchcase(step.step_id, scope)

        if not eligible(runnables[0]):
            return None
        wave = [step for step in runnables if eligible(step)][:limit]
        if len(wave) <= 1:
            return None
        return wave

    def _run_claimed(self, lease: JobLease, job_type: str) -> None:
        while True:
            lease = self._renew_if_due(lease)
            cancelled_at_boundary = False
            failed_at_boundary = False
            terminal_at_boundary = False
            context: StepContext | None = None
            step_id: str | None = None
            parallel_contexts: list[StepContext] | None = None
            with self.session_factory() as session, session.begin():
                store = self._store(session)
                status = store.job_status(lease.job_id)
                if status.state not in ACTIVE_LEASE_STATES:
                    return
                if status.cancel_requested or status.state == "cancel_requested":
                    store.cancel_at_boundary(lease)
                    cancelled_at_boundary = True
                else:
                    step = store.next_runnable_step(lease.job_id)
                    if step is None:
                        if store.all_steps_terminal(lease.job_id):
                            if store.any_step_failed(lease.job_id):
                                store.finish_failure(lease)
                                failed_at_boundary = True
                            else:
                                store.finish_success(lease)
                            cancelled_at_boundary = (
                                store.get_job(lease.job_id).state == "cancelled"
                            )
                            terminal_at_boundary = True
                        else:
                            store.release_deferred(lease)
                            return
                    else:
                        if self._stop_event.is_set():
                            # The preceding step/wave has already committed.
                            # Return the remaining work without consuming an attempt.
                            store.release_deferred(lease)
                            return
                        if step.waiting_user_kind is not None:
                            store.enter_user_wait(
                                lease,
                                step.step_id,
                                awaiting_user=step.waiting_user_kind,
                            )
                            return
                        payload_preview = self._job_payload(store, lease.job_id)
                        wave = self._select_parallel_wave(
                            store, lease.job_id, payload_preview
                        )
                        parallel_contexts: list[StepContext] | None
                        if wave is not None:
                            parallel_contexts = []
                            for wave_step in wave:
                                started_wave = store.start_step(lease, wave_step.step_id)
                                last_checkpoint = store.get_last_checkpoint(
                                    lease.job_id, started_wave.step_id
                                )
                                parallel_contexts.append(
                                    StepContext(
                                        job_id=lease.job_id,
                                        job_type=job_type,
                                        job_payload=payload_preview,
                                        step_id=started_wave.step_id,
                                        name=started_wave.name,
                                        attempt=started_wave.attempt,
                                        last_checkpoint_id=(
                                            last_checkpoint[0]
                                            if last_checkpoint
                                            else None
                                        ),
                                        last_checkpoint=(
                                            last_checkpoint[1]
                                            if last_checkpoint
                                            else None
                                        ),
                                        max_attempts=started_wave.max_attempts,
                                    )
                                )
                            context = parallel_contexts[0]
                            step_id = parallel_contexts[0].step_id
                        else:
                            parallel_contexts = None
                            started = store.start_step(lease, step.step_id)
                            last_checkpoint = store.get_last_checkpoint(
                                lease.job_id, started.step_id
                            )
                            context = StepContext(
                                job_id=lease.job_id,
                                job_type=job_type,
                                job_payload=payload_preview,
                                step_id=started.step_id,
                                name=started.name,
                                attempt=started.attempt,
                                last_checkpoint_id=(
                                    last_checkpoint[0] if last_checkpoint else None
                                ),
                                last_checkpoint=(
                                    last_checkpoint[1] if last_checkpoint else None
                                ),
                                max_attempts=started.max_attempts,
                            )
                            step_id = started.step_id
            if cancelled_at_boundary:
                self._notify_cancelled(lease.job_id)
                return
            if terminal_at_boundary:
                if failed_at_boundary:
                    self._notify_failed(lease.job_id)
                return
            if context is None or step_id is None:
                return
            if parallel_contexts is not None and len(parallel_contexts) > 1:
                if self._run_parallel_wave(lease, job_type, parallel_contexts):
                    return
                continue
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
                        step_result = executor(context)
                    finally:
                        # 失败提交也必须使用心跳期间刷新的租约到期时间。
                        lease = lease_ref[0]
            except ProcessDeath:
                raise
            except LeaseLostError:
                # 执行权已转移时不得把当前 worker 的结果解释为步骤失败；
                # 外层只丢弃结果，后续由租约恢复流程接管。
                raise
            except StepAwaitingUser as waiting:
                lease = self._renew_if_due(lease)
                with self.session_factory() as session, session.begin():
                    self._store(session).pause_running_step_for_user(
                        lease,
                        step_id,
                        awaiting_user=waiting.awaiting_user,
                        checkpoint_payload=waiting.checkpoint,
                    )
                return
            except StepFailure as failure:
                outcome = self._commit_step_failure(lease, step_id, failure)
                if outcome.job_state == "cancelled":
                    self._notify_cancelled(lease.job_id)
                elif outcome.job_state in {"failed", "failed_final"}:
                    self._notify_failed(lease.job_id)
                return
            except Exception:  # 意外异常按 fatal 处理，避免无限重试
                logger.exception("任务 %s 步骤 %s 意外失败", lease.job_id, step_id)
                failure = StepFailure(
                    retryable=False,
                    error_code=EXECUTOR_ERROR_CODE,
                    detail="任务执行遇到系统异常，请稍后重试或联系维护人员。",
                )
                outcome = self._commit_step_failure(lease, step_id, failure)
                if outcome.job_state == "cancelled":
                    self._notify_cancelled(lease.job_id)
                elif outcome.job_state in {"failed", "failed_final"}:
                    self._notify_failed(lease.job_id)
                return
            try:
                self._commit_step_success(lease, step_id, step_result)
            except LeaseLostError:
                raise
            except StepFailure as failure:
                outcome = self._commit_step_failure(lease, step_id, failure)
                if outcome.job_state == "cancelled":
                    self._notify_cancelled(lease.job_id)
                elif outcome.job_state in {"failed", "failed_final"}:
                    self._notify_failed(lease.job_id)
                return
            except Exception:
                logger.exception(
                    "任务 %s 步骤 %s 提交结果失败", lease.job_id, step_id
                )
                failure = StepFailure(
                    retryable=False,
                    error_code=EXECUTOR_ERROR_CODE,
                    detail="任务结果写入失败，请重试或联系维护人员。",
                )
                outcome = self._commit_step_failure(lease, step_id, failure)
                if outcome.job_state == "cancelled":
                    self._notify_cancelled(lease.job_id)
                elif outcome.job_state in {"failed", "failed_final"}:
                    self._notify_failed(lease.job_id)
                return
    def _run_parallel_wave(
        self,
        lease: JobLease,
        job_type: str,
        contexts: Sequence[StepContext],
    ) -> bool:
        """在同一租约下并行执行独立步骤波次；返回 True 表示任务应停止。"""
        executor = self.executors.get(job_type)
        if executor is None:
            failure = StepFailure(
                retryable=False,
                error_code=EXECUTOR_MISSING_CODE,
                detail="当前任务暂时无法执行，请联系维护人员检查任务配置。",
            )
            outcome = self._commit_step_failure(
                lease, contexts[0].step_id, failure, settle_job=True
            )
            if outcome.job_state == "cancelled":
                self._notify_cancelled(lease.job_id)
            elif outcome.job_state in {"failed", "failed_final"}:
                self._notify_failed(lease.job_id)
            return True

        results: dict[str, tuple[str, Any]] = {}
        process_death: ProcessDeath | None = None
        try:
            with self._lease_heartbeat(lease) as lease_ref:
                try:
                    with ThreadPoolExecutor(max_workers=len(contexts)) as pool:
                        future_map = {
                            pool.submit(executor, ctx): ctx for ctx in contexts
                        }
                        for future in as_completed(future_map):
                            ctx = future_map[future]
                            try:
                                result = future.result()
                                # Persist completed reads before slower siblings finish.
                                self._commit_step_success(lease_ref[0], ctx.step_id, result)
                                results[ctx.step_id] = ("ok", None)
                            except ProcessDeath as death:
                                # 排空同波其余 future：成功结果独立提交，
                                # 死亡步骤保持 running，交由租约恢复器收敛。
                                process_death = death
                            except LeaseLostError:
                                raise
                            except StepFailure as failure:
                                results[ctx.step_id] = ("fail", failure)
                            except Exception:
                                logger.exception(
                                    "任务 %s 并行步骤 %s 意外失败",
                                    lease.job_id,
                                    ctx.step_id,
                                )
                                results[ctx.step_id] = (
                                    "fail",
                                    StepFailure(
                                        retryable=False,
                                        error_code=EXECUTOR_ERROR_CODE,
                                        detail="任务执行遇到系统异常，请稍后重试或联系维护人员。",
                                    ),
                                )
                finally:
                    lease = lease_ref[0]
        except LeaseLostError:
            raise

        with self.session_factory() as session, session.begin():
            status = self._store(session).job_status(lease.job_id)
            cancelled = status.cancel_requested or status.state == "cancel_requested"
            if cancelled:
                self._store(session).cancel_at_boundary(lease)
        if cancelled:
            self._notify_cancelled(lease.job_id)
            return True

        if process_death is not None:
            # 已提交成功步骤；未入结果的死亡步骤保持 running，由恢复器重置。
            raise process_death

        failures = [
            (ctx.step_id, results[ctx.step_id][1])
            for ctx in sorted(contexts, key=lambda item: item.step_id)
            if results.get(ctx.step_id, ("ok", None))[0] == "fail"
        ]
        if not failures:
            return False

        had_fatal = False
        had_retryable = False
        for index, (step_id, failure) in enumerate(failures):
            is_last = index == len(failures) - 1
            settle = is_last
            # 非最后一次失败先保留租约，避免其余 running 成为孤儿。
            outcome = self._commit_step_failure(
                lease,
                step_id,
                failure,
                settle_job=settle,
            )
            if outcome.job_state == "cancelled":
                self._notify_cancelled(lease.job_id)
                return True
            if outcome.step_state == "failed_final":
                had_fatal = True
            if outcome.step_state == "failed_retryable":
                had_retryable = True
            if settle and outcome.job_state in {"failed", "failed_final"}:
                self._notify_failed(lease.job_id)
                return True
            if settle and outcome.job_state == "failed_retryable":
                return True

        if had_fatal:
            lease = self._renew_if_due(lease)
            with self.session_factory() as session, session.begin():
                self._store(session).finish_failure(lease)
            self._notify_failed(lease.job_id)
            return True
        if had_retryable:
            # 理论上最后一次 settle 已转 failed_retryable；兜底停止。
            return True
        return False

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
                try:
                    with self.session_factory() as session, session.begin():
                        renewed = self._store(session).renew_lease(active)
                except Exception:
                    # SQLite 的瞬时忙碌不代表执行权已经转移；下一次心跳继续用
                    # owner/generation 校验。真正被恢复器接管时 renew_lease 会
                    # 确定性返回 False，执行器结果仍会被丢弃。
                    logger.warning(
                        "任务 %s 租约心跳暂时写入失败，将继续核对执行权",
                        active.job_id,
                        exc_info=True,
                    )
                    continue
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

    def _commit_step_success(
        self,
        lease: JobLease,
        step_id: str,
        result: StepExecutionResult,
    ) -> None:
        lease = self._renew_if_due(lease)
        with self.session_factory() as session, session.begin():
            store = self._store(session)
            store.acquire_step_commit(lease, step_id)
            if isinstance(result, PreparedStepResult):
                self._apply_without_commit(session, result.apply)
                # SQLite 在领域写事务期间排斥恢复器写入；提交前刷新租约，
                # 避免长 apply 完成后仍以事务开始时的过期时间校验自身。
                if not store.renew_lease(lease):
                    raise LeaseLostError(
                        f"任务 {lease.job_id} 提交前无法确认执行权"
                    )
                checkpoint = result.checkpoint
            else:
                checkpoint = result
            store.complete_step_after_commit_fence(
                lease,
                step_id,
                checkpoint_payload=checkpoint,
            )

    @staticmethod
    def _apply_without_commit(session: Session, apply: StepApply) -> None:
        """执行领域写入回调，并拒绝回调提前提交 Runner 事务。"""

        def reject_commit(_session: Session) -> None:
            raise RuntimeError("PreparedStepResult.apply 不得调用 Session.commit()")

        event.listen(session, "before_commit", reject_commit)
        try:
            apply(session)
        finally:
            event.remove(session, "before_commit", reject_commit)

    def _commit_step_failure(
        self,
        lease: JobLease,
        step_id: str,
        failure: StepFailure,
        *,
        settle_job: bool = True,
    ) -> StepFailureOutcome:
        lease = self._renew_if_due(lease)
        with self.session_factory() as session, session.begin():
            return self._store(session).fail_step(
                lease,
                step_id,
                error_code=failure.error_code,
                retryable=failure.retryable,
                detail=failure.detail,
                diagnostic_checkpoint=failure.diagnostic_checkpoint,
                settle_job=settle_job,
            )

    def _notify_cancelled(self, job_id: str) -> None:
        """在任务取消事务提交后投影证据等领域的终态。"""
        if self.on_cancelled is None:
            return
        try:
            self.on_cancelled(job_id)
        except Exception:
            # Job 状态已提交；启动扫描会再次收敛投影，不能让回调故障停掉通用 worker。
            logger.exception("任务 %s 取消后的领域状态投影失败", job_id)

    def _notify_failed(self, job_id: str) -> None:
        """在任务终败事务提交后投影领域运行终态。"""
        if self.on_failed is None:
            return
        try:
            self.on_failed(job_id)
        except Exception:
            logger.exception("任务 %s 失败后的领域状态投影失败", job_id)

    def _job_payload(self, store: JobStore, job_id: str) -> dict[str, Any]:
        job = store.get_job(job_id)
        return verify_payload_sha256(job.payload_json, job.payload_sha256)

    def _renew_if_due(self, lease: JobLease) -> JobLease:
        """租约剩余不足 1/3 时续租；失败不阻断，交由后续提交的租约校验裁决。"""
        if lease.expires_at - self.now() > self.lease_ttl / 3:
            return lease
        with self.session_factory() as session, session.begin():
            if self._store(session).renew_lease(lease):
                return replace(lease, expires_at=self.now() + self.lease_ttl)
        return lease
