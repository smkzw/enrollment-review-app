"""Job 应用服务：用户动作的用例编排与事务边界。

- 用户动作先创建持久 Job（幂等：同键同内容返回同一任务，同键不同内容冲突），
  再由后台 runner 执行；
- 每次用例是短事务（``with session.begin()``）；SSE 订阅只读，不修改任务；
- API 层只做协议转换，本层输出结构化 DTO，中文词汇由 API 投影提供。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.enums import JobEventType
from app.storage.codecs import utc_now
from app.storage.idempotency import IdempotencyRepository, request_hash
from app.workflow.jobstore import (
    DEFAULT_LEASE_TTL,
    EventRow,
    JobActionOutcome,
    JobSnapshot,
    JobStore,
)
from app.workflow.errors import InvalidJobDefinitionError
from app.workflow.states import backoff_delay

JOB_IDEMPOTENCY_SCOPE = "jobs"

Now = Callable[[], datetime]


@dataclass(frozen=True)
class StepSpec:
    """任务创建时的步骤声明（依赖引用同任务内的 step_id）。"""

    step_id: str
    name: str
    max_attempts: int = 1
    retryable: bool = False
    waiting_user_kind: str | None = None
    depends_on: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "max_attempts": self.max_attempts,
            "retryable": self.retryable,
            "waiting_user_kind": self.waiting_user_kind,
            "depends_on": list(self.depends_on),
        }


@dataclass(frozen=True)
class CreateJobResult:
    job_id: str
    state: str
    created: bool


class JobService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        now: Now = utc_now,
        lease_ttl: timedelta = DEFAULT_LEASE_TTL,
        backoff: Callable[[int], timedelta] = backoff_delay,
    ) -> None:
        self.session_factory = session_factory
        self.now = now
        self.lease_ttl = lease_ttl
        self.backoff = backoff

    def _store(self, session: Session) -> JobStore:
        return JobStore(
            session,
            now=self.now,
            lease_ttl=self.lease_ttl,
            backoff=self.backoff,
        )

    # ------------------------------------------------------------------ 用例

    def create_job(
        self,
        *,
        idempotency_key: str,
        job_type: str,
        payload: dict[str, Any] | None = None,
        steps: list[StepSpec] | None = None,
    ) -> CreateJobResult:
        """幂等创建持久 Job：同键同内容复用原任务，同键不同内容冲突。"""
        steps = steps or []
        self._validate_steps(steps)
        job_id = uuid4().hex
        submitted = request_hash(
            {
                "job_type": job_type,
                "payload": payload or {},
                "steps": [step.as_dict() for step in steps],
            }
        )
        with self.session_factory() as session:
            with session.begin():
                idempotency = IdempotencyRepository(session)
                record, created = idempotency.resolve(
                    scope=JOB_IDEMPOTENCY_SCOPE,
                    idempotency_key=idempotency_key,
                    submitted_hash=submitted,
                    result_type="job",
                    result_id=job_id,
                )
                if not created:
                    return CreateJobResult(
                        job_id=record.result_id,
                        state=self.get_job_state(record.result_id),
                        created=False,
                    )
                store = self._store(session)
                store.create_job(
                    job_id=job_id,
                    job_type=job_type,
                    payload=payload,
                    progress_total=len(steps),
                )
                for step in steps:
                    store.create_step(
                        step_id=step.step_id,
                        job_id=job_id,
                        name=step.name,
                        max_attempts=step.max_attempts,
                        retryable=step.retryable,
                        waiting_user_kind=step.waiting_user_kind,
                    )
                # 依赖可以任意顺序声明；先落全部步骤，再建立同任务复合外键。
                for step in steps:
                    store.add_step_dependencies(
                        job_id=job_id,
                        step_id=step.step_id,
                        depends_on=step.depends_on,
                    )
                store.append_event(
                    store.make_event(
                        job_id=job_id,
                        event_type=JobEventType.CREATED,
                        progress_total=len(steps),
                        payload={"job_type": job_type},
                    )
                )
        return CreateJobResult(job_id=job_id, state="queued", created=True)

    @staticmethod
    def _validate_steps(steps: list[StepSpec]) -> None:
        """拒绝重复、缺失、自引用或成环依赖，避免任务永久等待。"""
        ids = [step.step_id for step in steps]
        if len(ids) != len(set(ids)):
            raise InvalidJobDefinitionError("任务中存在重复的步骤编号")
        known = set(ids)
        graph = {step.step_id: tuple(step.depends_on) for step in steps}
        for step in steps:
            if step.waiting_user_kind is not None:
                if not step.waiting_user_kind.strip():
                    raise InvalidJobDefinitionError(
                        f"步骤 {step.step_id} 的等待确认类型不能为空"
                    )
                if step.retryable or step.max_attempts != 1:
                    raise InvalidJobDefinitionError(
                        f"等待确认步骤 {step.step_id} 不能配置自动重试或多次尝试"
                    )
        for step_id, dependencies in graph.items():
            if len(dependencies) != len(set(dependencies)):
                raise InvalidJobDefinitionError(f"步骤 {step_id} 存在重复依赖")
            if step_id in dependencies:
                raise InvalidJobDefinitionError(f"步骤 {step_id} 不能依赖自身")
            missing = [item for item in dependencies if item not in known]
            if missing:
                raise InvalidJobDefinitionError(
                    f"步骤 {step_id} 引用了不存在的前置步骤"
                )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in visiting:
                raise InvalidJobDefinitionError("任务步骤之间存在循环依赖")
            if step_id in visited:
                return
            visiting.add(step_id)
            for dependency in graph[step_id]:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in ids:
            visit(step_id)

    def get_status(self, job_id: str) -> JobSnapshot:
        with self.session_factory() as session:
            return self._store(session).snapshot(job_id)

    def get_job_state(self, job_id: str) -> str:
        with self.session_factory() as session:
            return self._store(session).job_status(job_id).state

    def get_events(self, job_id: str, after_seq: int = 0) -> list[EventRow]:
        with self.session_factory() as session:
            store = self._store(session)
            store.get_job(job_id)  # 不存在 -> NOT_FOUND
            return store.list_event_rows(job_id, after_seq=after_seq)

    def cancel(self, job_id: str) -> JobActionOutcome:
        with self.session_factory() as session:
            with session.begin():
                return self._store(session).request_cancel(job_id)

    def retry(self, job_id: str) -> JobActionOutcome:
        with self.session_factory() as session:
            with session.begin():
                return self._store(session).retry_failed(job_id)
