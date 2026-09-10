"""人工事实修订持久任务：Job/Step/Checkpoint/Lease 与幂等提交。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.enums import JobEventType
from app.domain.contracts.facts import FactAuthority
from app.services.evidence_app_errors import app_error_boundary
from app.services.fact_correction_service import (
    PreparedFactCorrection,
    prepare_fact_correction,
    prepared_to_payload,
)
from app.storage.codecs import utc_now, verify_payload_sha256
from app.storage.idempotency import IdempotencyRepository, request_hash
from app.workflow.errors import InvalidJobDefinitionError
from app.workflow.jobstore import DEFAULT_LEASE_TTL, JobStore
from app.workflow.states import backoff_delay

FACT_CORRECTION_JOB_TYPE = "fact_correction"
FACT_CORRECTION_IDEMPOTENCY_SCOPE = "fact_correction"
FACT_CORRECTION_PLAN_STEP_ID = "plan"
FACT_CORRECTION_APPLY_STEP_ID = "apply"


@dataclass(frozen=True)
class CreateFactCorrectionJobResult:
    job_id: str
    correction_id: str
    idempotency_key: str
    created: bool
    status: str


def _now_utc() -> datetime:
    return datetime.now(UTC)


class FactCorrectionJobService:
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

    def _store(self, session: Session) -> JobStore:
        return JobStore(session, now=self.now, lease_ttl=self.lease_ttl, backoff=self.backoff)

    @app_error_boundary
    def create_or_reuse_job(
        self,
        *,
        authority: FactAuthority,
        target_kind: Literal["fact", "event", "exposure"],
        target_id: str,
        locator_ids: list[str],
        reason: str,
        operator_id: str,
        updates: dict[str, Any],
        created_by: str,
        created_at: datetime | None = None,
    ) -> CreateFactCorrectionJobResult:
        if not created_by or not created_by.strip():
            raise InvalidJobDefinitionError("创建者不能为空")
        created_at = created_at or _now_utc()
        request_material = {
            "contract": "fact_correction_job_request/v2",
            "authority": authority.model_dump(mode="json"),
            "target_kind": target_kind,
            "target_id": target_id,
            "locator_ids": sorted(
                {str(item).strip() for item in locator_ids if str(item).strip()}
            ),
            "reason": reason.strip(),
            "operator_id": operator_id.strip(),
            "updates": updates,
            "created_by": created_by.strip(),
        }
        request_idempotency_key = request_hash(request_material)
        submitted_hash = request_hash(
            {"request_idempotency_key": request_idempotency_key, **request_material}
        )
        with self.session_factory() as session, session.begin():
            job_id = uuid4().hex
            record, created = IdempotencyRepository(session).resolve(
                scope=FACT_CORRECTION_IDEMPOTENCY_SCOPE,
                idempotency_key=request_idempotency_key,
                submitted_hash=submitted_hash,
                result_type="fact_correction_job",
                result_id=job_id,
            )
            if not created:
                return self._reuse_job(session, record.result_id)
            prepared = prepare_fact_correction(
                session,
                authority=authority,
                target_kind=target_kind,
                target_id=target_id,
                locator_ids=locator_ids,
                reason=reason,
                operator_id=operator_id,
                updates=updates,
                created_at=created_at,
            )
            return self._persist_job(
                session,
                prepared,
                created_by=created_by,
                job_id=job_id,
                request_idempotency_key=request_idempotency_key,
            )

    def _reuse_job(self, session: Session, job_id: str) -> CreateFactCorrectionJobResult:
        job = self._store(session).get_job(job_id)
        payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
        prepared = payload.get("prepared") or {}
        correction_id = str(prepared.get("correction_id") or "")
        correction_idempotency_key = str(prepared.get("idempotency_key") or "")
        if not correction_id or not correction_idempotency_key:
            raise InvalidJobDefinitionError("既有修订任务缺少不可变修订身份")
        return CreateFactCorrectionJobResult(
            job_id=job_id,
            correction_id=correction_id,
            idempotency_key=correction_idempotency_key,
            created=False,
            status=job.state,
        )

    def _persist_job(
        self,
        session: Session,
        prepared: PreparedFactCorrection,
        *,
        created_by: str,
        job_id: str,
        request_idempotency_key: str,
    ) -> CreateFactCorrectionJobResult:
        job_request = {
            "idempotency_key": prepared.idempotency_key,
            "request_idempotency_key": request_idempotency_key,
            "job_type": FACT_CORRECTION_JOB_TYPE,
            "prepared": prepared_to_payload(prepared),
            "created_by": created_by,
        }
        store = self._store(session)
        store.create_job(
            job_id=job_id,
            job_type=FACT_CORRECTION_JOB_TYPE,
            payload=job_request,
            progress_total=2,
        )
        store.create_step(
            step_id=FACT_CORRECTION_PLAN_STEP_ID,
            job_id=job_id,
            name="核对受影响范围",
            max_attempts=3,
            retryable=True,
        )
        store.create_step(
            step_id=FACT_CORRECTION_APPLY_STEP_ID,
            job_id=job_id,
            name="重新整理受影响信息",
            max_attempts=3,
            retryable=True,
        )
        store.add_step_dependencies(
            job_id=job_id,
            step_id=FACT_CORRECTION_APPLY_STEP_ID,
            depends_on=(FACT_CORRECTION_PLAN_STEP_ID,),
        )
        store.append_event(
            store.make_event(
                job_id=job_id,
                event_type=JobEventType.CREATED,
                progress_total=2,
                payload={
                    "job_type": FACT_CORRECTION_JOB_TYPE,
                    "correction_id": prepared.correction_id,
                },
            )
        )
        return CreateFactCorrectionJobResult(
            job_id=job_id,
            correction_id=prepared.correction_id,
            idempotency_key=prepared.idempotency_key,
            created=True,
            status="queued",
        )

    def cancel(self, job_id: str):
        with self.session_factory() as session, session.begin():
            return self._store(session).request_cancel(job_id)

    def retry(self, job_id: str):
        with self.session_factory() as session, session.begin():
            return self._store(session).retry_failed(job_id)

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
