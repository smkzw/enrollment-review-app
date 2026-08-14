"""JobStore：租约、步骤事务与状态机写入的唯一入口。

设计约束（design.md §5/§8、prd.md §Job 与恢复）：

- 每次操作都是短事务；一个步骤的可见变化（Checkpoint + 步骤状态 +
  任务进度 + 单调序号 JobEvent）在同一个事务内提交；
- 步骤结果提交必须先通过租约校验（owner + generation + 未过期），否则抛
  :class:`LeaseLostError` 且不写入任何步骤结果；
- 取消是持久请求：worker 在安全步骤边界把任务转为 cancelled，
  已提交检查点与历史事件保留；
- 事件序号 ``(job_id, event_seq)`` 唯一且单调，在写入事务内分配；
- 恢复只依据持久状态工作；进程内 task/thread 不是真相。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.domain.contracts.enums import JobEventType
from app.domain.contracts.jobs import JobEvent
from app.storage.codecs import utc_now, verify_payload_sha256
from app.storage.models import (
    JobCheckpointRecord,
    JobRecord,
    JobStepRecord,
    job_step_dependencies,
)
from app.storage.repositories import JobRepository
from app.workflow.errors import (
    JobNotFoundError,
    JobStateConflictError,
    LeaseLostError,
    StepDeferredError,
    StepMismatchError,
)
from app.workflow.states import (
    ACTIVE_LEASE_STATES,
    CLAIMABLE_JOB_STATES,
    DEPENDENCY_FAILED_CODE,
    DIRECT_CANCELABLE_JOB_STATES,
    FAILED_STEP_STATES,
    RECOVERY_RESET_CODE,
    RUNNABLE_STEP_STATES,
    TERMINAL_JOB_STATES,
    TERMINAL_STEP_STATES,
    backoff_delay,
    step_is_deferred,
)

DEFAULT_LEASE_TTL = timedelta(seconds=30)
Now = Callable[[], datetime]


@dataclass(frozen=True)
class JobLease:
    """数据库租约：owner + 到期时间 + generation；提交/续租必须三者匹配。"""

    job_id: str
    owner: str
    generation: int
    expires_at: datetime


@dataclass(frozen=True)
class JobStatusRow:
    state: str
    cancel_requested: bool
    progress_completed: int
    progress_total: int


@dataclass(frozen=True)
class StepView:
    step_id: str
    name: str
    state: str
    attempt: int
    max_attempts: int
    retryable: bool
    error_code: str | None
    error_classification: str | None
    retry_not_before: datetime | None
    depends_on: tuple[str, ...]


@dataclass(frozen=True)
class EventRow:
    seq: int
    event: JobEvent


@dataclass(frozen=True)
class JobSnapshot:
    job_id: str
    job_type: str
    state: str
    cancel_requested: bool
    progress_completed: int
    progress_total: int
    error_code: str | None
    error_classification: str | None
    lease_generation: int
    created_at: datetime
    updated_at: datetime
    last_event_seq: int
    steps: list[StepView]
    events: list[EventRow]


@dataclass(frozen=True)
class JobActionOutcome:
    state: str
    changed: bool


@dataclass(frozen=True)
class StepFailureOutcome:
    job_state: str
    step_state: str
    attempt: int
    exhausted: bool
    retry_not_before: datetime | None


class JobStore:
    """工作流写入入口：包装存储原语并实施租约/状态机规则。"""

    def __init__(
        self,
        session: Session,
        *,
        now: Now = utc_now,
        lease_ttl: timedelta = DEFAULT_LEASE_TTL,
        backoff: Callable[[int], timedelta] = backoff_delay,
    ) -> None:
        self.session = session
        self.repo = JobRepository(session)
        self.now = now
        self.lease_ttl = lease_ttl
        self.backoff = backoff

    # ------------------------------------------------------------------ 创建

    def create_job(
        self,
        *,
        job_id: str,
        job_type: str,
        payload: dict[str, Any] | None = None,
        progress_total: int = 0,
    ) -> JobRecord:
        return self.repo.create_job(
            job_id=job_id,
            job_type=job_type,
            state="queued",
            payload=payload,
            progress_total=progress_total,
        )

    def create_step(
        self,
        *,
        step_id: str,
        job_id: str,
        name: str,
        max_attempts: int = 1,
        retryable: bool = False,
        depends_on: tuple[str, ...] = (),
    ) -> JobStepRecord:
        return self.repo.create_step(
            step_id=step_id,
            job_id=job_id,
            name=name,
            state="queued",
            attempt=0,
            max_attempts=max_attempts,
            retryable=retryable,
            depends_on=depends_on,
        )

    def add_step_dependencies(
        self,
        *,
        job_id: str,
        step_id: str,
        depends_on: tuple[str, ...],
    ) -> None:
        self.repo.add_step_dependencies(
            job_id=job_id,
            step_id=step_id,
            depends_on=depends_on,
        )

    def make_event(
        self,
        *,
        job_id: str,
        event_type: JobEventType,
        step_id: str | None = None,
        attempt: int = 1,
        checkpoint_id: str | None = None,
        retryable: bool = False,
        progress_completed: int = 0,
        progress_total: int = 0,
        payload: dict[str, Any] | None = None,
    ) -> JobEvent:
        return JobEvent(
            job_event_id=uuid4().hex,
            job_id=job_id,
            event_type=event_type,
            step_id=step_id,
            occurred_at=self.now(),
            attempt=attempt,
            checkpoint_id=checkpoint_id,
            retryable=retryable,
            progress_completed=progress_completed,
            progress_total=progress_total,
            payload=payload or {},
        )

    def append_event(self, event: JobEvent) -> int:
        return self.repo.append_event(event)

    # ------------------------------------------------------------------ 查询

    def get_job(self, job_id: str) -> JobRecord:
        job = self.session.get(JobRecord, job_id)
        if job is None:
            raise JobNotFoundError(f"任务 {job_id!r} 不存在")
        return job

    def job_status(self, job_id: str) -> JobStatusRow:
        row = self.session.execute(
            select(
                JobRecord.state,
                JobRecord.cancel_requested,
                JobRecord.progress_completed,
                JobRecord.progress_total,
            ).where(JobRecord.job_id == job_id)
        ).one_or_none()
        if row is None:
            raise JobNotFoundError(f"任务 {job_id!r} 不存在")
        return JobStatusRow(state=row.state, cancel_requested=bool(row.cancel_requested),
                            progress_completed=row.progress_completed,
                            progress_total=row.progress_total)

    def list_steps(self, job_id: str) -> list[JobStepRecord]:
        return self.session.execute(
            select(JobStepRecord)
            .where(JobStepRecord.job_id == job_id)
            .order_by(JobStepRecord.created_at, JobStepRecord.step_id)
        ).scalars().all()

    def _deps_map(self, job_id: str) -> dict[str, tuple[str, ...]]:
        rows = self.session.execute(
            select(
                job_step_dependencies.c.step_id,
                job_step_dependencies.c.depends_on_step_id,
            )
            .where(job_step_dependencies.c.job_id == job_id)
            .order_by(job_step_dependencies.c.step_id, job_step_dependencies.c.position)
        ).all()
        result: dict[str, list[str]] = {}
        for step_id, depends_on in rows:
            result.setdefault(step_id, []).append(depends_on)
        return {step_id: tuple(deps) for step_id, deps in result.items()}

    def next_runnable_step(self, job_id: str) -> JobStepRecord | None:
        """依赖已满足且未终态的下一个步骤；失败步骤按重试范围参与。"""
        steps = self.list_steps(job_id)
        deps = self._deps_map(job_id)
        completed = {step.step_id for step in steps if step.state == "completed"}
        now = self.now()
        for step in steps:
            if step.state not in RUNNABLE_STEP_STATES:
                continue
            if step_is_deferred(step.state, step.retry_not_before, now):
                continue
            if all(dep in completed for dep in deps.get(step.step_id, ())):
                return step
        return None

    def all_steps_terminal(self, job_id: str) -> bool:
        return all(step.state in TERMINAL_STEP_STATES for step in self.list_steps(job_id))

    def any_step_failed(self, job_id: str) -> bool:
        return any(step.state == "failed_final" for step in self.list_steps(job_id))

    def get_last_checkpoint(
        self, job_id: str, step_id: str
    ) -> tuple[str, dict[str, Any]] | None:
        row = self.session.execute(
            select(JobCheckpointRecord)
            .where(
                JobCheckpointRecord.job_id == job_id,
                JobCheckpointRecord.step_id == step_id,
            )
            .order_by(JobCheckpointRecord.created_at.desc(),
                      JobCheckpointRecord.checkpoint_id.desc())
            .limit(1)
        ).scalars().first()
        if row is None:
            return None
        payload = verify_payload_sha256(row.payload_json, row.payload_sha256)
        return row.checkpoint_id, payload

    def list_event_rows(self, job_id: str, after_seq: int = 0) -> list[EventRow]:
        return [
            EventRow(seq=seq, event=event)
            for seq, event in self.repo.list_event_rows(job_id, after_seq=after_seq)
        ]

    def snapshot(self, job_id: str) -> JobSnapshot:
        job = self.get_job(job_id)
        deps = self._deps_map(job_id)
        steps = [
            StepView(
                step_id=step.step_id,
                name=step.name,
                state=step.state,
                attempt=step.attempt,
                max_attempts=step.max_attempts,
                retryable=step.retryable,
                error_code=step.error_code,
                error_classification=step.error_classification,
                retry_not_before=step.retry_not_before,
                depends_on=deps.get(step.step_id, ()),
            )
            for step in self.list_steps(job_id)
        ]
        return JobSnapshot(
            job_id=job.job_id,
            job_type=job.job_type,
            state=job.state,
            cancel_requested=bool(job.cancel_requested),
            progress_completed=job.progress_completed,
            progress_total=job.progress_total,
            error_code=job.error_code,
            error_classification=job.error_classification,
            lease_generation=job.lease_generation,
            created_at=job.created_at,
            updated_at=job.updated_at,
            last_event_seq=job.last_event_seq,
            steps=steps,
            events=self.list_event_rows(job_id),
        )

    # ------------------------------------------------------------------ 租约

    def claim_next(self, worker_id: str, *, job_type: str | None = None) -> JobLease | None:
        return self._claim(worker_id=worker_id, job_type=job_type)

    def claim_job(self, job_id: str, worker_id: str) -> JobLease | None:
        return self._claim(worker_id=worker_id, job_id=job_id)

    def _claim(
        self,
        *,
        worker_id: str,
        job_id: str | None = None,
        job_type: str | None = None,
    ) -> JobLease | None:
        """条件更新认领：仅 queued/recovering 且无有效租约可领取，同时递增 generation。"""
        now = self.now()
        for _ in range(3):
            conditions = [
                JobRecord.state.in_(CLAIMABLE_JOB_STATES),
                or_(
                    JobRecord.lease_expires_at.is_(None),
                    JobRecord.lease_expires_at < now,
                ),
            ]
            if job_id is not None:
                conditions.append(JobRecord.job_id == job_id)
            if job_type is not None:
                conditions.append(JobRecord.job_type == job_type)
            row = self.session.execute(
                select(JobRecord.job_id, JobRecord.lease_generation)
                .where(*conditions)
                .order_by(JobRecord.created_at, JobRecord.job_id)
                .limit(1)
            ).first()
            if row is None:
                return None
            candidate_id, generation = row
            result = self.session.execute(
                update(JobRecord)
                .where(
                    JobRecord.job_id == candidate_id,
                    JobRecord.state.in_(CLAIMABLE_JOB_STATES),
                    or_(
                        JobRecord.lease_expires_at.is_(None),
                        JobRecord.lease_expires_at < now,
                    ),
                    JobRecord.lease_generation == generation,
                )
                .values(
                    state="running",
                    lease_owner=worker_id,
                    lease_expires_at=now + self.lease_ttl,
                    lease_generation=generation + 1,
                    revision=JobRecord.revision + 1,
                    updated_at=now,
                )
            )
            self.session.flush()
            if result.rowcount == 1:
                return JobLease(
                    job_id=candidate_id,
                    owner=worker_id,
                    generation=generation + 1,
                    expires_at=now + self.lease_ttl,
                )
        return None

    def _lease_guard(self, lease: JobLease) -> JobRecord:
        """租约校验：state/owner/generation/未过期 全部匹配才允许写入。"""
        now = self.now()
        job = self.get_job(lease.job_id)
        if job.state not in ACTIVE_LEASE_STATES:
            raise LeaseLostError(
                f"任务 {lease.job_id} 当前状态 {job.state}，不再持有租约"
            )
        if job.lease_owner != lease.owner:
            raise LeaseLostError(
                f"任务 {lease.job_id} 租约持有者不匹配（期望 {lease.owner}）"
            )
        if job.lease_generation != lease.generation:
            raise LeaseLostError(
                f"任务 {lease.job_id} 租约代号不匹配"
                f"（期望 {lease.generation}，当前 {job.lease_generation}）"
            )
        if job.lease_expires_at is None or job.lease_expires_at < now:
            raise LeaseLostError(f"任务 {lease.job_id} 租约已过期")
        return job

    def renew_lease(self, lease: JobLease) -> bool:
        """续租：仅当前持有者且租约未过期时可续。"""
        now = self.now()
        result = self.session.execute(
            update(JobRecord)
            .where(
                JobRecord.job_id == lease.job_id,
                JobRecord.state.in_(ACTIVE_LEASE_STATES),
                JobRecord.lease_owner == lease.owner,
                JobRecord.lease_generation == lease.generation,
                JobRecord.lease_expires_at.is_not(None),
                JobRecord.lease_expires_at >= now,
            )
            .values(
                lease_expires_at=now + self.lease_ttl,
                revision=JobRecord.revision + 1,
                updated_at=now,
            )
        )
        self.session.flush()
        return result.rowcount == 1

    def release_deferred(self, lease: JobLease) -> None:
        """无当前可运行步骤（依赖未满足或退避未到期）：退还租约回到 queued。"""
        now = self.now()
        has_deferred_retry = any(
            step_is_deferred(step.state, step.retry_not_before, now)
            for step in self.list_steps(lease.job_id)
        )
        result = self.session.execute(
            update(JobRecord)
            .where(
                JobRecord.job_id == lease.job_id,
                JobRecord.state == "running",
                JobRecord.lease_owner == lease.owner,
                JobRecord.lease_generation == lease.generation,
            )
            .values(
                state="failed_retryable" if has_deferred_retry else "queued",
                lease_owner=None,
                lease_expires_at=None,
                revision=JobRecord.revision + 1,
                updated_at=now,
            )
        )
        self.session.flush()
        if result.rowcount != 1:
            raise LeaseLostError(f"任务 {lease.job_id} 租约失效，无法退还")

    # -------------------------------------------------------------- 步骤事务

    def start_step(self, lease: JobLease, step_id: str) -> JobStepRecord:
        job = self._lease_guard(lease)
        now = self.now()
        step = self.session.get(
            JobStepRecord, {"job_id": job.job_id, "step_id": step_id}
        )
        if step is None or step.job_id != job.job_id:
            raise StepMismatchError(f"步骤 {step_id!r} 不属于任务 {job.job_id}")
        if step.state not in RUNNABLE_STEP_STATES:
            raise StepMismatchError(
                f"步骤 {step_id} 当前状态 {step.state}，不能启动"
            )
        if step.retry_not_before is not None and step.retry_not_before > now:
            raise StepDeferredError(step_id, step.retry_not_before)
        step.state = "running"
        step.attempt += 1
        step.error_code = None
        step.error_classification = None
        step.retry_not_before = None
        step.updated_at = now
        self.append_event(
            self.make_event(
                job_id=job.job_id,
                event_type=JobEventType.STEP_STARTED,
                step_id=step_id,
                attempt=step.attempt,
                progress_completed=job.progress_completed,
                progress_total=job.progress_total,
            )
        )
        self.session.flush()
        return step

    def complete_step(
        self,
        lease: JobLease,
        step_id: str,
        *,
        checkpoint_payload: dict[str, Any],
    ) -> int:
        """一个事务：Checkpoint + 步骤完成 + 任务进度 + STEP_COMPLETED 事件。"""
        job = self._lease_guard(lease)
        now = self.now()
        step = self.session.get(
            JobStepRecord, {"job_id": job.job_id, "step_id": step_id}
        )
        if step is None or step.job_id != job.job_id:
            raise StepMismatchError(f"步骤 {step_id!r} 不属于任务 {job.job_id}")
        if step.state != "running":
            raise StepMismatchError(f"步骤 {step_id} 当前状态 {step.state}，不能提交完成")
        checkpoint_id = uuid4().hex
        self.repo.create_checkpoint(
            checkpoint_id=checkpoint_id,
            job_id=job.job_id,
            step_id=step_id,
            payload={"attempt": step.attempt, **checkpoint_payload},
        )
        step.state = "completed"
        step.error_code = None
        step.error_classification = None
        step.retry_not_before = None
        step.updated_at = now
        self.session.flush()
        completed = self.session.execute(
            select(func.count())
            .select_from(JobStepRecord)
            .where(JobStepRecord.job_id == job.job_id, JobStepRecord.state == "completed")
        ).scalar_one()
        job.progress_completed = completed
        job.updated_at = now
        seq = self.append_event(
            self.make_event(
                job_id=job.job_id,
                event_type=JobEventType.STEP_COMPLETED,
                step_id=step_id,
                attempt=step.attempt,
                checkpoint_id=checkpoint_id,
                progress_completed=completed,
                progress_total=job.progress_total,
                payload={"checkpoint_id": checkpoint_id},
            )
        )
        self.session.flush()
        return seq

    def fail_step(
        self,
        lease: JobLease,
        step_id: str,
        *,
        error_code: str,
        retryable: bool,
        detail: str | None = None,
    ) -> StepFailureOutcome:
        """一个事务提交步骤失败：错误分类、退避时间、任务状态与事件。"""
        job = self._lease_guard(lease)
        now = self.now()
        step = self.session.get(
            JobStepRecord, {"job_id": job.job_id, "step_id": step_id}
        )
        if step is None or step.job_id != job.job_id:
            raise StepMismatchError(f"步骤 {step_id!r} 不属于任务 {job.job_id}")
        if step.state != "running":
            raise StepMismatchError(f"步骤 {step_id} 当前状态 {step.state}，不能提交失败")
        classification = "retryable" if retryable else "fatal"
        exhausted = retryable and step.attempt >= step.max_attempts
        event_payload: dict[str, Any] = {
            "error_code": error_code,
            "error_classification": classification,
        }
        if detail:
            event_payload["detail"] = detail
        step.error_code = error_code
        step.error_classification = classification
        if not retryable or exhausted:
            step.state = "failed_final"
            step.retry_not_before = None
            if exhausted:
                event_payload["attempt_exhausted"] = True
        else:
            step.state = "failed_retryable"
            step.retry_not_before = now + self.backoff(step.attempt)
            event_payload["retry_not_before"] = step.retry_not_before.isoformat()
        step.updated_at = now
        self.append_event(
            self.make_event(
                job_id=job.job_id,
                event_type=JobEventType.STEP_FAILED,
                step_id=step_id,
                attempt=step.attempt,
                retryable=retryable and not exhausted,
                progress_completed=job.progress_completed,
                progress_total=job.progress_total,
                payload=event_payload,
            )
        )
        if job.cancel_requested:
            # 取消请求优先：失败边界也是安全边界，任务直接转 cancelled。
            self._cancel_steps(job.job_id, now)
            job.state = "cancelled"
            job.lease_owner = None
            job.lease_expires_at = None
            job.updated_at = now
            self.append_event(
                self.make_event(
                    job_id=job.job_id,
                    event_type=JobEventType.CANCELLED,
                    progress_completed=job.progress_completed,
                    progress_total=job.progress_total,
                )
            )
            final_state = "cancelled"
        elif step.state == "failed_retryable":
            job.state = "failed_retryable"
            job.lease_owner = None
            job.lease_expires_at = None
            job.updated_at = now
            self.append_event(
                self.make_event(
                    job_id=job.job_id,
                    event_type=JobEventType.RETRY_SCHEDULED,
                    step_id=step_id,
                    attempt=step.attempt,
                    progress_completed=job.progress_completed,
                    progress_total=job.progress_total,
                    payload={
                        "retry_not_before": step.retry_not_before.isoformat(),
                        "retry_scope": [step_id],
                    },
                )
            )
            final_state = "failed_retryable"
        else:
            self._cascade_final_failure(job.job_id, step_id, now)
            self._sync_progress(job.job_id, job)
            self._finalize_job_failure(
                job,
                error_code=error_code,
                error_classification=classification,
                now=now,
            )
            final_state = "failed_final"
        self.session.flush()
        return StepFailureOutcome(
            job_state=final_state,
            step_state=step.state,
            attempt=step.attempt,
            exhausted=exhausted,
            retry_not_before=step.retry_not_before,
        )

    def finish_success(self, lease: JobLease) -> int:
        job = self._lease_guard(lease)
        steps = self.list_steps(job.job_id)
        if not all(step.state in TERMINAL_STEP_STATES for step in steps):
            raise JobStateConflictError("仍有未完成步骤，不能标记完成", current_state=job.state)
        if any(step.state == "failed_final" for step in steps):
            raise JobStateConflictError("存在失败步骤，不能标记完成", current_state=job.state)
        now = self.now()
        job.state = "completed"
        job.lease_owner = None
        job.lease_expires_at = None
        job.updated_at = now
        seq = self.append_event(
            self.make_event(
                job_id=job.job_id,
                event_type=JobEventType.COMPLETED,
                progress_completed=job.progress_completed,
                progress_total=job.progress_total,
            )
        )
        self.session.flush()
        return seq

    def finish_failure(self, lease: JobLease) -> None:
        job = self._lease_guard(lease)
        now = self.now()
        failed = next(
            (step for step in self.list_steps(job.job_id) if step.state == "failed_final"),
            None,
        )
        self._sync_progress(job.job_id, job)
        self._finalize_job_failure(
            job,
            error_code=failed.error_code if failed is not None else RECOVERY_RESET_CODE,
            error_classification=(
                failed.error_classification if failed is not None else "fatal"
            ),
            now=now,
        )
        self.session.flush()

    # -------------------------------------------------------------- 取消/重试

    def request_cancel(self, job_id: str) -> JobActionOutcome:
        """持久取消请求：终态任务为无副作用 no-op，其余在安全边界转换。"""
        job = self.get_job(job_id)
        if job.state in TERMINAL_JOB_STATES or job.state == "cancel_requested":
            return JobActionOutcome(state=job.state, changed=False)
        now = self.now()
        if job.state in DIRECT_CANCELABLE_JOB_STATES:
            self._cancel_steps(job.job_id, now)
            job.state = "cancelled"
            job.cancel_requested = True
            job.lease_owner = None
            job.lease_expires_at = None
            job.updated_at = now
            self.append_event(
                self.make_event(
                    job_id=job_id,
                    event_type=JobEventType.CANCELLED,
                    progress_completed=job.progress_completed,
                    progress_total=job.progress_total,
                )
            )
            self.session.flush()
            return JobActionOutcome(state="cancelled", changed=True)
        # running：请求持久化，worker 在安全边界执行
        job.state = "cancel_requested"
        job.cancel_requested = True
        job.updated_at = now
        self.append_event(
            self.make_event(
                job_id=job_id,
                event_type=JobEventType.CANCEL_REQUESTED,
                progress_completed=job.progress_completed,
                progress_total=job.progress_total,
            )
        )
        self.session.flush()
        return JobActionOutcome(state="cancel_requested", changed=True)

    def cancel_at_boundary(self, lease: JobLease) -> int:
        """worker 在安全步骤边界执行取消：未启动步骤转 cancelled，历史保留。"""
        job = self._lease_guard(lease)
        now = self.now()
        self._cancel_steps(job.job_id, now)
        job.state = "cancelled"
        job.cancel_requested = True
        job.lease_owner = None
        job.lease_expires_at = None
        job.updated_at = now
        seq = self.append_event(
            self.make_event(
                job_id=job.job_id,
                event_type=JobEventType.CANCELLED,
                progress_completed=job.progress_completed,
                progress_total=job.progress_total,
            )
        )
        self.session.flush()
        return seq

    def retry_failed(self, job_id: str) -> JobActionOutcome:
        """人工重试：只把失败范围（failed_retryable/failed_final）重置回 queued。"""
        job = self.get_job(job_id)
        if job.state not in ("failed_final", "failed_retryable"):
            raise JobStateConflictError("只有失败的任务可以重试", current_state=job.state)
        if job.lease_owner is not None:
            raise JobStateConflictError("任务仍被占用，不能重试", current_state=job.state)
        now = self.now()
        failed = [step for step in self.list_steps(job_id) if step.state in FAILED_STEP_STATES]
        if not failed:
            raise JobStateConflictError("没有可重试的失败步骤", current_state=job.state)
        for step in failed:
            step.state = "queued"
            step.error_code = None
            step.error_classification = None
            step.retry_not_before = None
            step.updated_at = now
        job.state = "queued"
        job.error_code = None
        job.error_classification = None
        job.updated_at = now
        self.append_event(
            self.make_event(
                job_id=job_id,
                event_type=JobEventType.RETRY_SCHEDULED,
                progress_completed=job.progress_completed,
                progress_total=job.progress_total,
                payload={"retry_scope": [step.step_id for step in failed]},
            )
        )
        self.session.flush()
        return JobActionOutcome(state="queued", changed=True)

    def requeue_due_retries(self) -> list[str]:
        """退避到期且无未到期步骤的 failed_retryable 任务 -> queued。"""
        now = self.now()
        due = (
            select(JobStepRecord.job_id)
            .where(
                JobStepRecord.state == "failed_retryable",
                or_(
                    JobStepRecord.retry_not_before.is_(None),
                    JobStepRecord.retry_not_before <= now,
                ),
            )
        )
        blocked = (
            select(JobStepRecord.job_id).where(
                JobStepRecord.state == "failed_retryable",
                JobStepRecord.retry_not_before > now,
            )
        )
        result = self.session.execute(
            update(JobRecord)
            .where(
                JobRecord.state == "failed_retryable",
                JobRecord.lease_owner.is_(None),
                JobRecord.job_id.in_(due),
                JobRecord.job_id.not_in(blocked),
            )
            .values(
                state="queued",
                revision=JobRecord.revision + 1,
                updated_at=now,
            )
            .returning(JobRecord.job_id)
        )
        self.session.flush()
        return list(result.scalars())

    # ------------------------------------------------------------------ 恢复

    def mark_expired_running(self) -> list[str]:
        """恢复第一阶段：过期租约的 running 任务 -> recovering（租约清空、代号递增）。"""
        now = self.now()
        result = self.session.execute(
            update(JobRecord)
            .where(
                JobRecord.state == "running",
                JobRecord.lease_expires_at.is_not(None),
                JobRecord.lease_expires_at < now,
            )
            .values(
                state="recovering",
                lease_owner=None,
                lease_expires_at=None,
                lease_generation=JobRecord.lease_generation + 1,
                revision=JobRecord.revision + 1,
                updated_at=now,
            )
            .returning(JobRecord.job_id)
        )
        self.session.flush()
        return list(result.scalars())

    def cancel_expired_cancel_requests(self) -> list[str]:
        """取消请求已持久化但 worker 死亡：租约过期后直接在安全边界取消。"""
        now = self.now()
        ids = self.session.execute(
            update(JobRecord)
            .where(
                JobRecord.state == "cancel_requested",
                JobRecord.lease_expires_at.is_not(None),
                JobRecord.lease_expires_at < now,
            )
            .values(
                state="cancelled",
                lease_owner=None,
                lease_expires_at=None,
                lease_generation=JobRecord.lease_generation + 1,
                revision=JobRecord.revision + 1,
                updated_at=now,
            )
            .returning(JobRecord.job_id)
        ).scalars().all()
        for job_id in ids:
            self._cancel_steps(job_id, now)
            job = self.get_job(job_id)
            self.append_event(
                self.make_event(
                    job_id=job_id,
                    event_type=JobEventType.CANCELLED,
                    progress_completed=job.progress_completed,
                    progress_total=job.progress_total,
                    payload={"reason": "cancel_request_expired_lease"},
                )
            )
        self.session.flush()
        return list(ids)

    def requeue_recovering(self, job_id: str) -> str:
        """恢复第二阶段：recovering -> queued（或 failed_final），从最后 Checkpoint 恢复。"""
        job = self.get_job(job_id)
        if job.state != "recovering":
            return job.state  # 竞态下已被取消/认领，交由持有者处理
        now = self.now()
        failed_ids = self._reset_interrupted_steps(job_id, now)
        for failed_step_id in failed_ids:
            self._cascade_final_failure(job_id, failed_step_id, now)
        self._sync_progress(job_id, job)
        if failed_ids:
            self._finalize_job_failure(
                job,
                error_code=RECOVERY_RESET_CODE,
                error_classification="fatal",
                now=now,
                reason="recovery_attempts_exhausted",
            )
        else:
            job.state = "queued"
        job.updated_at = now
        self.session.flush()
        return job.state

    def prepare_claimed(self, lease: JobLease) -> str:
        """认领后执行前：把中断遗留的 running 步骤按恢复规则重置。

        与 :meth:`requeue_recovering` 共享同一逻辑 —— 即使没有启动期扫描，
        直接认领 recovering 任务也能正确恢复，不存在永久 processing。
        """
        job = self._lease_guard(lease)
        now = self.now()
        failed_ids = self._reset_interrupted_steps(job.job_id, now)
        for failed_step_id in failed_ids:
            self._cascade_final_failure(job.job_id, failed_step_id, now)
        self._sync_progress(job.job_id, job)
        if failed_ids:
            self._finalize_job_failure(
                job,
                error_code=RECOVERY_RESET_CODE,
                error_classification="fatal",
                now=now,
                reason="recovery_attempts_exhausted",
            )
        job.updated_at = now
        self.session.flush()
        return job.state

    def _reset_interrupted_steps(self, job_id: str, now: datetime) -> list[str]:
        """按持久状态重置中断步骤：有 Checkpoint -> completed；否则按预算排队或终败。"""
        job = self.get_job(job_id)
        failed_ids: list[str] = []
        for step in self.list_steps(job_id):
            if step.state != "running":
                continue
            last = self.get_last_checkpoint(job_id, step.step_id)
            if last is not None:
                checkpoint_id, _payload = last
                step.state = "completed"
                step.error_code = None
                step.error_classification = None
                step.retry_not_before = None
                step.updated_at = now
                self.session.flush()
                recovered_completed = self._completed_count(job_id)
                job.progress_completed = recovered_completed
                self.append_event(
                    self.make_event(
                        job_id=job_id,
                        event_type=JobEventType.STEP_COMPLETED,
                        step_id=step.step_id,
                        attempt=step.attempt,
                        checkpoint_id=checkpoint_id,
                        progress_completed=recovered_completed,
                        progress_total=job.progress_total,
                        payload={"recovered_from_checkpoint": True},
                    )
                )
            elif step.attempt >= step.max_attempts:
                step.state = "failed_final"
                step.error_code = RECOVERY_RESET_CODE
                step.error_classification = "fatal"
                step.retry_not_before = None
                step.updated_at = now
                failed_ids.append(step.step_id)
                self.append_event(
                    self.make_event(
                        job_id=job_id,
                        event_type=JobEventType.STEP_FAILED,
                        step_id=step.step_id,
                        attempt=step.attempt,
                        retryable=False,
                        progress_completed=job.progress_completed,
                        progress_total=job.progress_total,
                        payload={"reason": "attempt_budget_exhausted_during_recovery"},
                    )
                )
            else:
                step.state = "queued"
                step.error_code = None
                step.error_classification = None
                step.retry_not_before = None
                step.updated_at = now
                self.append_event(
                    self.make_event(
                        job_id=job_id,
                        event_type=JobEventType.RETRY_SCHEDULED,
                        step_id=step.step_id,
                        attempt=step.attempt,
                        progress_completed=job.progress_completed,
                        progress_total=job.progress_total,
                        payload={"reason": "lease_recovery"},
                    )
                )
        return failed_ids

    # ------------------------------------------------------------------ 内部

    def _cancel_steps(self, job_id: str, now: datetime) -> None:
        """未启动/未完成步骤转 cancelled；终态步骤保留历史。"""
        for step in self.list_steps(job_id):
            if step.state in TERMINAL_STEP_STATES:
                continue
            step.state = "cancelled"
            step.error_code = None
            step.error_classification = None
            step.retry_not_before = None
            step.updated_at = now

    def _cascade_final_failure(self, job_id: str, failed_step_id: str, now: datetime) -> None:
        """终败步骤的下游（传递依赖）一并终败，避免任务永久停留在 queued。"""
        job = self.get_job(job_id)
        deps = self._deps_map(job_id)
        affected: set[str] = set()
        queue = [failed_step_id]
        while queue:
            current = queue.pop()
            for step_id, depends_on in deps.items():
                if current in depends_on and step_id not in affected:
                    affected.add(step_id)
                    queue.append(step_id)
        steps = {step.step_id: step for step in self.list_steps(job_id)}
        for step_id in sorted(affected):
            step = steps[step_id]
            if step.state in TERMINAL_STEP_STATES:
                continue
            step.state = "failed_final"
            step.error_code = DEPENDENCY_FAILED_CODE
            step.error_classification = "fatal"
            step.retry_not_before = None
            step.updated_at = now
            self.append_event(
                self.make_event(
                    job_id=job_id,
                    event_type=JobEventType.STEP_FAILED,
                    step_id=step_id,
                    attempt=max(step.attempt, 1),
                    retryable=False,
                    progress_completed=job.progress_completed,
                    progress_total=job.progress_total,
                    payload={
                        "error_code": DEPENDENCY_FAILED_CODE,
                        "error_classification": "fatal",
                        "depends_on_step_id": failed_step_id,
                    },
                )
            )

    def _sync_progress(self, job_id: str, job: JobRecord) -> None:
        job.progress_completed = self._completed_count(job_id)

    def _completed_count(self, job_id: str) -> int:
        return self.session.execute(
            select(func.count())
            .select_from(JobStepRecord)
            .where(JobStepRecord.job_id == job_id, JobStepRecord.state == "completed")
        ).scalar_one()

    def _finalize_job_failure(
        self,
        job: JobRecord,
        *,
        error_code: str,
        error_classification: str,
        now: datetime,
        reason: str | None = None,
    ) -> None:
        """写入任务终败状态及独立终态事件，供断线订阅明确收束。"""
        job.state = "failed_final"
        job.error_code = error_code
        job.error_classification = error_classification
        job.lease_owner = None
        job.lease_expires_at = None
        job.updated_at = now
        payload: dict[str, Any] = {
            "error_code": error_code,
            "error_classification": error_classification,
        }
        if reason is not None:
            payload["reason"] = reason
        self.append_event(
            self.make_event(
                job_id=job.job_id,
                event_type=JobEventType.FAILED,
                progress_completed=job.progress_completed,
                progress_total=job.progress_total,
                payload=payload,
            )
        )
