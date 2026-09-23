"""选择性视觉后处理持久任务：冻结修订后幂等入队，不等待远端 VLM。

本服务只负责创建/复用独立 Job；OCR 核心事务与页租约不得因入队而延长。
远端调用由 ``selective_vision_postprocess`` 执行器在独立任务租约下完成。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.evidence.selective_vision_review import SELECTIVE_VISION_PLAN_VERSION
from app.services.evidence_app_errors import (
    AppInternalError,
    AppNotFoundError,
    AppSelectiveVisionPlanUnsupportedError,
    app_error_boundary,
)
from app.services.job_service import JOB_IDEMPOTENCY_SCOPE, JobService, StepSpec
from app.services.selective_vision_runtime import selective_vision_route_sha256
from app.storage.codecs import utc_now, verify_payload_sha256
from app.storage.idempotency import IdempotencyRepository
from app.storage.ocr_repositories import EvidenceProcessingRevisionRepository
from app.storage.models import JobRecord
from app.storage.ocr_models import EvidenceProcessingRevisionRecord
from app.workflow.errors import InvalidJobDefinitionError
from app.workflow.jobstore import DEFAULT_LEASE_TTL, JobStore
from app.workflow.states import FAILED_STEP_STATES, TERMINAL_JOB_STATES
from app.workflow.states import backoff_delay

SELECTIVE_VISION_POSTPROCESS_JOB_TYPE = "selective_vision_postprocess"
SELECTIVE_VISION_POSTPROCESS_STEP_ID = "run_selective_vision"
SELECTIVE_VISION_POSTPROCESS_IDEMPOTENCY_PREFIX = "selective_vision_postprocess"


@dataclass(frozen=True)
class EnqueueSelectiveVisionPostprocessResult:
    job_id: str
    evidence_processing_revision_id: str
    created: bool
    state: str


@dataclass(frozen=True)
class SelectiveVisionRevisionTaskView:
    """修订 -> 视觉核验任务的只读投影（用户安全字段，无模型/日志/内部错误信息）。"""

    evidence_processing_revision_id: str
    found: bool
    job_id: str | None = None
    state: str | None = None
    cancel_requested: bool = False
    plan_supported: bool = True
    progress_completed: int = 0
    progress_total: int = 0
    failed_step_names: tuple[str, ...] = ()
    eligible_page_count: int | None = None
    skipped_page_count: int | None = None
    observation_page_count: int | None = None
    closed_page_count: int | None = None
    closed_failure_kind: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class SelectiveVisionTaskActionResult:
    job_id: str
    state: str
    changed: bool


def selective_vision_postprocess_idempotency_key(
    evidence_processing_revision_id: str,
    *,
    plan_version: str = SELECTIVE_VISION_PLAN_VERSION,
    route_sha256: str | None = None,
) -> str:
    revision_id = str(evidence_processing_revision_id or "").strip()
    if not revision_id:
        raise InvalidJobDefinitionError("证据处理修订标识不能为空")
    return (
        f"{SELECTIVE_VISION_POSTPROCESS_IDEMPOTENCY_PREFIX}:"
        f"{revision_id}:{plan_version}:{route_sha256 or selective_vision_route_sha256()}"
    )


class SelectiveVisionPostprocessJobService:
    """冻结修订后的独立视觉后处理任务入队（幂等、短事务）。"""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        now=utc_now,
        lease_ttl: timedelta = DEFAULT_LEASE_TTL,
        backoff=backoff_delay,
    ) -> None:
        self.session_factory = session_factory
        self.now = now
        self.lease_ttl = lease_ttl
        self.backoff = backoff
        self._jobs = JobService(
            session_factory,
            now=now,
            lease_ttl=lease_ttl,
            backoff=backoff,
        )

    def _store(self, session: Session) -> JobStore:
        return JobStore(
            session,
            now=self.now,
            lease_ttl=self.lease_ttl,
            backoff=self.backoff,
        )

    @app_error_boundary
    def enqueue_for_revision(
        self,
        evidence_processing_revision_id: str,
        *,
        plan_version: str = SELECTIVE_VISION_PLAN_VERSION,
        trigger: str = "evidence_processing_freeze",
    ) -> EnqueueSelectiveVisionPostprocessResult:
        """幂等入队：同修订同计划版本复用原任务，不触发也不等待 VLM。"""
        with self.session_factory() as session, session.begin():
            return self.enqueue_for_revision_in_session(
                session,
                evidence_processing_revision_id,
                plan_version=plan_version,
                trigger=trigger,
            )

    def enqueue_for_revision_in_session(
        self,
        session: Session,
        evidence_processing_revision_id: str,
        *,
        plan_version: str = SELECTIVE_VISION_PLAN_VERSION,
        trigger: str = "evidence_processing_freeze",
    ) -> EnqueueSelectiveVisionPostprocessResult:
        revision_id = str(evidence_processing_revision_id or "").strip()
        if not revision_id:
            raise InvalidJobDefinitionError("证据处理修订标识不能为空")
        EvidenceProcessingRevisionRepository(session).get(revision_id)
        plan = str(plan_version or "").strip() or SELECTIVE_VISION_PLAN_VERSION
        route_sha256 = selective_vision_route_sha256()
        trigger_name = str(trigger or "").strip() or "evidence_processing_freeze"
        idempotency_key = selective_vision_postprocess_idempotency_key(
            revision_id, plan_version=plan, route_sha256=route_sha256,
        )
        payload = {
            "contract": "selective_vision_postprocess_job/v2",
            "evidence_processing_revision_id": revision_id,
            "plan_version": plan,
            "route_sha256": route_sha256,
            "trigger": trigger_name,
            "idempotency_key": idempotency_key,
        }
        steps = [
            StepSpec(
                step_id=SELECTIVE_VISION_POSTPROCESS_STEP_ID,
                name="选择性视觉后处理",
                max_attempts=3,
                retryable=True,
            )
        ]
        created = self._jobs.create_job_in_session(
            session,
            idempotency_key=idempotency_key,
            job_type=SELECTIVE_VISION_POSTPROCESS_JOB_TYPE,
            payload=payload,
            steps=steps,
        )
        return EnqueueSelectiveVisionPostprocessResult(
            job_id=created.job_id,
            evidence_processing_revision_id=revision_id,
            created=created.created,
            state=created.state,
        )

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self.session_factory() as session:
            store = self._store(session)
            job = store.get_job(job_id)
            payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
            return {
                "job_id": job.job_id,
                "job_type": job.job_type,
                "state": job.state,
                "payload": payload,
                "progress_total": job.progress_total,
                "progress_completed": job.progress_completed,
            }

    # ------------------------------------------------------- 修订 -> 任务投影

    def _base_revision_id(self, session: Session, revision_id: str) -> str:
        """完整修订是用户入口；视觉任务仍以其不可变 base 修订为身份。"""
        record = session.get(EvidenceProcessingRevisionRecord, revision_id)
        if record is None:
            raise AppNotFoundError("找不到对应的资料处理版本。")
        if record.revision_kind == "base":
            EvidenceProcessingRevisionRepository(session).get(revision_id)
            return revision_id
        if record.revision_kind != "complete":
            raise AppInternalError("资料处理版本类型无法识别。")

        payload = verify_payload_sha256(record.payload_json, record.payload_sha256)
        base_revision_id = str(payload.get("base_processing_revision_id") or "")
        if (
            payload.get("evidence_processing_revision_id") != revision_id
            or payload.get("revision_kind") != "complete"
            or base_revision_id != record.base_processing_revision_id
        ):
            raise AppInternalError("资料处理版本关联不完整，系统已停止继续操作。")
        base = EvidenceProcessingRevisionRepository(session).get(base_revision_id)
        if (
            base.evidence_snapshot_id != record.evidence_snapshot_id
            or base.project_id != record.project_id
            or base.subject_id != record.subject_id
            or base.review_episode_id != record.review_episode_id
        ):
            raise AppInternalError("资料处理版本关联范围不一致，系统已停止继续操作。")
        return base_revision_id

    def _find_job_record(
        self, session: Session, revision_id: str
    ) -> tuple[JobRecord, dict[str, Any]] | None:
        """稳定关联：幂等键定位当前规划版本任务；兜底按任务类型+负载定位旧任务。"""
        record = IdempotencyRepository(session).get(
            JOB_IDEMPOTENCY_SCOPE,
            selective_vision_postprocess_idempotency_key(revision_id),
        )
        store = self._store(session)
        candidates: list[str] = []
        if record is not None and record.result_type == "job":
            candidates.append(record.result_id)
        # 旧规划版本任务使用不同幂等键；按类型扫描并校验负载中的修订标识。
        # 修订标识中的 LIKE 通配符必须先转义，避免误匹配其他修订的任务。
        escaped = (
            revision_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        like_rows = session.execute(
            select(JobRecord.job_id)
            .where(
                JobRecord.job_type == SELECTIVE_VISION_POSTPROCESS_JOB_TYPE,
                JobRecord.payload_json.like(f"%{escaped}%", escape="\\"),
            )
            .order_by(JobRecord.created_at.desc(), JobRecord.job_id)
        ).scalars().all()
        for job_id in like_rows:
            if job_id not in candidates:
                candidates.append(job_id)
        for job_id in candidates:
            job = store.get_job(job_id)
            payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
            if payload.get("evidence_processing_revision_id") == revision_id:
                return job, payload
        return None

    def _require_job_record(
        self, session: Session, revision_id: str
    ) -> tuple[JobRecord, dict[str, Any]]:
        found = self._find_job_record(session, revision_id)
        if found is None:
            raise AppNotFoundError("该资料版本暂无页面视觉核验任务。")
        job, payload = found
        if job.job_type != SELECTIVE_VISION_POSTPROCESS_JOB_TYPE:
            raise AppInternalError("页面视觉核验任务与资料修订关联不一致。")
        return job, payload

    @app_error_boundary
    def get_revision_task(
        self, evidence_processing_revision_id: str
    ) -> SelectiveVisionRevisionTaskView:
        """查询投影：修订 -> 视觉核验任务的用户可读状态与失败范围。"""
        revision_id = str(evidence_processing_revision_id or "").strip()
        if not revision_id:
            raise AppNotFoundError("资料处理修订标识不能为空。")
        with self.session_factory() as session:
            base_revision_id = self._base_revision_id(session, revision_id)
            found = self._find_job_record(session, base_revision_id)
            if found is None:
                return SelectiveVisionRevisionTaskView(
                    evidence_processing_revision_id=revision_id,
                    found=False,
                )
            job, payload = found
            if job.job_type != SELECTIVE_VISION_POSTPROCESS_JOB_TYPE:
                raise AppInternalError("页面视觉核验任务与资料修订关联不一致。")
            store = self._store(session)
            steps = store.list_steps(job.job_id)
            failed_names = tuple(
                step.name for step in steps if step.state in FAILED_STEP_STATES
            )
            checkpoint = store.get_last_checkpoint(
                job.job_id, SELECTIVE_VISION_POSTPROCESS_STEP_ID
            )
            checkpoint_payload = checkpoint[1] if checkpoint is not None else {}

            def _count(key: str) -> int | None:
                value = checkpoint_payload.get(key)
                return int(value) if isinstance(value, int) and value >= 0 else None

            return SelectiveVisionRevisionTaskView(
                evidence_processing_revision_id=revision_id,
                found=True,
                job_id=job.job_id,
                state=job.state,
                cancel_requested=bool(job.cancel_requested),
                plan_supported=(
                    str(payload.get("plan_version") or SELECTIVE_VISION_PLAN_VERSION)
                    == SELECTIVE_VISION_PLAN_VERSION
                    and payload.get("route_sha256") == selective_vision_route_sha256()
                ),
                progress_completed=int(job.progress_completed),
                progress_total=int(job.progress_total),
                failed_step_names=failed_names,
                eligible_page_count=_count("eligible_count"),
                skipped_page_count=_count("skipped_count"),
                observation_page_count=_count("observation_count"),
                closed_page_count=_count("closed_count"),
                closed_failure_kind=(
                    str(checkpoint_payload["closed_failure_kind"])
                    if checkpoint_payload.get("closed_failure_kind")
                    else None
                ),
                created_at=job.created_at,
                updated_at=job.updated_at,
            )

    def coverage_page_ids_match(self, evidence_processing_revision_id: str) -> bool:
        """Internal source check; raw page identities never enter the UI task view."""
        with self.session_factory() as session:
            revision_id = self._base_revision_id(session, evidence_processing_revision_id)
            found = self._find_job_record(session, revision_id)
            return found is not None and self._verified_scope_in_session(
                session, revision_id, found[0], found[1]
            ) is not None

    def verified_observation_scope(
        self, evidence_processing_revision_id: str
    ) -> tuple[frozenset[str], frozenset[str]] | None:
        """Return exact pages and observation rows accepted by the current completed job.

        ``None`` means no selective task exists (legacy caller). A present but
        unsupported/incomplete task is an error, never a legacy fallback.
        """
        with self.session_factory() as session:
            revision_id = self._base_revision_id(session, evidence_processing_revision_id)
            found = self._find_job_record(session, revision_id)
            if found is None:
                return None
            scope = self._verified_scope_in_session(session, revision_id, found[0], found[1])
            if scope is None:
                raise AppInternalError("当前页面质量核对的来源尚未完整，不能整理病史。")
            return scope

    def _verified_scope_in_session(
        self, session: Session, revision_id: str, job: JobRecord, payload: dict[str, Any]
    ) -> tuple[frozenset[str], frozenset[str]] | None:
        if (
            job.state != "completed"
            or payload.get("plan_version") != SELECTIVE_VISION_PLAN_VERSION
            or payload.get("route_sha256") != selective_vision_route_sha256()
        ):
            return None
        checkpoint = self._store(session).get_last_checkpoint(
            job.job_id, SELECTIVE_VISION_POSTPROCESS_STEP_ID
        )
        if checkpoint is None:
            return None
        result = checkpoint[1]
        expected = result.get("eligible_page_artifact_ids")
        observed = result.get("observed_page_artifact_ids")
        created = result.get("created_observation_ids")
        reused = result.get("reused_observation_ids")
        if not all(isinstance(items, list) for items in (expected, observed, created, reused)):
            return None
        if not all(isinstance(item, str) and item for item in expected + observed + created + reused):
            return None
        manifest_ids = {
            item.page_artifact_id
            for item in EvidenceProcessingRevisionRepository(session).get(revision_id).manifest
        }
        if not (
            len(expected) == result.get("eligible_count")
            and len(observed) == result.get("observation_count")
            and len(created) + len(reused) == len(observed)
            and len(set(expected)) == len(expected)
            and len(set(created + reused)) == len(observed)
            and set(expected) <= manifest_ids
            and set(expected) == set(observed)
            and result.get("closed_count") == 0
        ):
            return None
        return frozenset(expected), frozenset(created + reused)

    @app_error_boundary
    def cancel_revision_task(
        self, evidence_processing_revision_id: str
    ) -> SelectiveVisionTaskActionResult:
        """取消：先校验任务类型与修订关联，再复用持久取消请求机制。"""
        revision_id = str(evidence_processing_revision_id or "").strip()
        if not revision_id:
            raise AppNotFoundError("资料处理修订标识不能为空。")
        with self.session_factory() as session, session.begin():
            base_revision_id = self._base_revision_id(session, revision_id)
            job, _payload = self._require_job_record(session, base_revision_id)
            outcome = self._store(session).request_cancel(job.job_id)
            return SelectiveVisionTaskActionResult(
                job_id=job.job_id,
                state=outcome.state,
                changed=outcome.changed,
            )

    @app_error_boundary
    def retry_revision_task(
        self, evidence_processing_revision_id: str
    ) -> SelectiveVisionTaskActionResult:
        """人工重试当前失败范围；旧核验方式另建当前版本任务，保留旧历史。"""
        revision_id = str(evidence_processing_revision_id or "").strip()
        if not revision_id:
            raise AppNotFoundError("资料处理修订标识不能为空。")
        with self.session_factory() as session, session.begin():
            base_revision_id = self._base_revision_id(session, revision_id)
            job, payload = self._require_job_record(session, base_revision_id)
            if (
                str(payload.get("plan_version") or SELECTIVE_VISION_PLAN_VERSION)
                != SELECTIVE_VISION_PLAN_VERSION
                or payload.get("route_sha256") != selective_vision_route_sha256()
            ):
                if job.state not in TERMINAL_JOB_STATES:
                    raise AppSelectiveVisionPlanUnsupportedError()
                upgraded = self.enqueue_for_revision_in_session(
                    session,
                    base_revision_id,
                    plan_version=SELECTIVE_VISION_PLAN_VERSION,
                    trigger="plan_upgrade",
                )
                return SelectiveVisionTaskActionResult(
                    job_id=upgraded.job_id,
                    state=upgraded.state,
                    changed=upgraded.created,
                )
            outcome = self._store(session).retry_failed(job.job_id)
            return SelectiveVisionTaskActionResult(
                job_id=job.job_id,
                state=outcome.state,
                changed=outcome.changed,
            )

    @staticmethod
    def task_is_active(state: str | None) -> bool:
        """前端轮询判断的服务端同源口径：非终态且未在停止中。"""
        return (
            state is not None
            and state not in TERMINAL_JOB_STATES
            and state != "cancel_requested"
        )

    def cancel(self, job_id: str):
        with self.session_factory() as session, session.begin():
            return self._store(session).request_cancel(job_id)

    def retry(self, job_id: str):
        with self.session_factory() as session, session.begin():
            return self._store(session).retry_failed(job_id)


def enqueue_selective_vision_postprocess_for_revision(
    session_factory: sessionmaker[Session],
    evidence_processing_revision_id: str,
    *,
    plan_version: str = SELECTIVE_VISION_PLAN_VERSION,
    trigger: str = "evidence_processing_freeze",
) -> EnqueueSelectiveVisionPostprocessResult:
    """模块级便捷入队，供证据处理冻结点调用。"""
    return SelectiveVisionPostprocessJobService(session_factory).enqueue_for_revision(
        evidence_processing_revision_id,
        plan_version=plan_version,
        trigger=trigger,
    )


__all__ = [
    "SELECTIVE_VISION_POSTPROCESS_IDEMPOTENCY_PREFIX",
    "SELECTIVE_VISION_POSTPROCESS_JOB_TYPE",
    "SELECTIVE_VISION_POSTPROCESS_STEP_ID",
    "EnqueueSelectiveVisionPostprocessResult",
    "SelectiveVisionRevisionTaskView",
    "SelectiveVisionTaskActionResult",
    "SelectiveVisionPostprocessJobService",
    "enqueue_selective_vision_postprocess_for_revision",
    "selective_vision_postprocess_idempotency_key",
]
