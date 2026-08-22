"""V2 Job API：创建/状态/事件订阅(SSE)/取消/重试。

路由只调用 service/workflow，不做领域判断；错误信封见 ``errors.py``。
SSE 只订阅持久 JobEvent（``after_seq`` 续订），断开只结束订阅，
不修改任务、不持有取消权（design.md §6）。
"""
from __future__ import annotations

import json
import time
from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi import status as http_status
from fastapi.responses import StreamingResponse

from app.api.v2.schemas import (
    CreateJobRequest,
    CreateJobResponse,
    JobActionResponse,
    JobEventDTO,
    JobStatusResponse,
    JobStepDTO,
)
from app.api.v2.vocabulary import (
    EVENT_TYPE_LABELS,
    JOB_STATE_LABELS,
    STEP_STATE_LABELS,
    job_recovery_action,
)
from app.services.job_service import JobService, StepSpec
from app.workflow.jobstore import EventRow
from app.workflow.states import FAILED_STEP_STATES, TERMINAL_JOB_STATES

router = APIRouter(prefix="/api/v2/jobs", tags=["v2-jobs"])

_UNKNOWN_STATE_LABEL = "状态待更新"
_UNKNOWN_EVENT_LABEL = "事件已记录"


def _as_utc(value: datetime | None) -> datetime | None:
    """Restore the storage UTC convention at the API boundary."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _required_utc(value: datetime | None) -> datetime:
    """Restore a required persisted timestamp or fail closed on corrupt state."""
    restored = _as_utc(value)
    if restored is None:
        raise ValueError("任务持久时间字段缺失")
    return restored


def _service(request: Request) -> JobService:
    return request.app.state.job_service


@router.post("", response_model=CreateJobResponse, status_code=http_status.HTTP_201_CREATED)
def create_job(body: CreateJobRequest, request: Request, response: Response) -> CreateJobResponse:
    result = _service(request).create_job(
        idempotency_key=body.idempotency_key,
        job_type=body.job_type,
        payload=body.payload,
        steps=[
            StepSpec(
                step_id=step.step_id,
                name=step.name,
                max_attempts=step.max_attempts,
                retryable=step.retryable,
                depends_on=tuple(step.depends_on),
            )
            for step in body.steps
        ],
    )
    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    return CreateJobResponse(
        job_id=result.job_id,
        state=result.state,
        state_label=JOB_STATE_LABELS.get(result.state, _UNKNOWN_STATE_LABEL),
        created=result.created,
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, request: Request) -> JobStatusResponse:
    snapshot = _service(request).get_status(job_id)
    return JobStatusResponse(
        job_id=snapshot.job_id,
        job_type=snapshot.job_type,
        state=snapshot.state,
        state_label=JOB_STATE_LABELS.get(snapshot.state, _UNKNOWN_STATE_LABEL),
        cancel_requested=snapshot.cancel_requested,
        progress_completed=snapshot.progress_completed,
        progress_total=snapshot.progress_total,
        error_code=snapshot.error_code,
        error_classification=snapshot.error_classification,
        retryable_scope=[
            step.step_id for step in snapshot.steps if step.state in FAILED_STEP_STATES
        ],
        recovery_action=job_recovery_action(snapshot.state),
        created_at=_required_utc(snapshot.created_at),
        updated_at=_required_utc(snapshot.updated_at),
        last_event_seq=snapshot.last_event_seq,
        steps=[
            JobStepDTO(
                step_id=step.step_id,
                name=step.name,
                state=step.state,
                state_label=STEP_STATE_LABELS.get(step.state, _UNKNOWN_STATE_LABEL),
                attempt=step.attempt,
                max_attempts=step.max_attempts,
                retryable=step.retryable,
                error_code=step.error_code,
                error_classification=step.error_classification,
                retry_not_before=_as_utc(step.retry_not_before),
                depends_on=list(step.depends_on),
            )
            for step in snapshot.steps
        ],
        events=[
            JobEventDTO(
                seq=row.seq,
                job_event_id=row.event.job_event_id,
                event_type=row.event.event_type.value,
                event_type_label=EVENT_TYPE_LABELS.get(
                    row.event.event_type.value, _UNKNOWN_EVENT_LABEL
                ),
                step_id=row.event.step_id,
                occurred_at=_required_utc(row.event.occurred_at),
                attempt=row.event.attempt,
                checkpoint_id=row.event.checkpoint_id,
                retryable=row.event.retryable,
                progress_completed=row.event.progress_completed,
                progress_total=row.event.progress_total,
                payload=row.event.payload,
            )
            for row in snapshot.events
        ],
    )


@router.post("/{job_id}/cancel", response_model=JobActionResponse)
def cancel_job(job_id: str, request: Request) -> JobActionResponse:
    outcome = _service(request).cancel(job_id)
    return JobActionResponse(
        job_id=job_id,
        state=outcome.state,
        state_label=JOB_STATE_LABELS.get(outcome.state, _UNKNOWN_STATE_LABEL),
        changed=outcome.changed,
    )


@router.post("/{job_id}/retry", response_model=JobActionResponse)
def retry_job(job_id: str, request: Request) -> JobActionResponse:
    outcome = _service(request).retry(job_id)
    return JobActionResponse(
        job_id=job_id,
        state=outcome.state,
        state_label=JOB_STATE_LABELS.get(outcome.state, _UNKNOWN_STATE_LABEL),
        changed=outcome.changed,
    )


@router.get("/{job_id}/events")
def subscribe_job_events(
    job_id: str,
    request: Request,
    after_seq: int = Query(default=0, ge=0),
    last_event_id: int | None = Header(default=None, alias="Last-Event-ID", ge=0),
) -> StreamingResponse:
    service = _service(request)
    service.get_status(job_id)  # 不存在 -> 404 信封
    poll_interval: float = request.app.state.sse_poll_interval
    heartbeat_seconds: float = request.app.state.sse_heartbeat_seconds
    resume_after = max(after_seq, last_event_id or 0)
    return StreamingResponse(
        _sse_stream(
            service,
            job_id,
            after_seq=resume_after,
            poll_interval=poll_interval,
            heartbeat_seconds=heartbeat_seconds,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _format_event(row: EventRow) -> str:
    event = row.event
    data = json.dumps(
        {
            "seq": row.seq,
            "job_event_id": event.job_event_id,
            "job_id": event.job_id,
            "event_type": event.event_type.value,
            "step_id": event.step_id,
            "occurred_at": _required_utc(event.occurred_at).isoformat(),
            "attempt": event.attempt,
            "checkpoint_id": event.checkpoint_id,
            "retryable": event.retryable,
            "progress_completed": event.progress_completed,
            "progress_total": event.progress_total,
            "payload": event.payload,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"id: {row.seq}\nevent: {event.event_type.value}\ndata: {data}\n\n"


def _sse_stream(
    service: JobService,
    job_id: str,
    *,
    after_seq: int,
    poll_interval: float,
    heartbeat_seconds: float,
) -> Iterator[str]:
    """只读订阅：按 ``(job_id, seq)`` 单调补齐；断开只结束生成器，不修改任务。"""
    last_seq = after_seq
    last_heartbeat = time.monotonic()
    yield ": connected\n\n"
    while True:
        rows = service.get_events(job_id, after_seq=last_seq)
        if rows:
            for row in rows:
                yield _format_event(row)
                last_seq = row.seq
            last_heartbeat = time.monotonic()
            continue
        snapshot = service.get_status(job_id)
        if snapshot.state in TERMINAL_JOB_STATES:
            # 终态与事件在同一事务提交：终态后立即补齐一次，避免漏掉同批事件
            final = service.get_events(job_id, after_seq=last_seq)
            for row in final:
                yield _format_event(row)
                last_seq = row.seq
            yield (
                "event: done\n"
                + "data: "
                + json.dumps(
                    {
                        "job_id": job_id,
                        "state": snapshot.state,
                        "last_seq": snapshot.last_event_seq,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n\n"
            )
            return
        if time.monotonic() - last_heartbeat >= heartbeat_seconds:
            yield ": keep-alive\n\n"
            last_heartbeat = time.monotonic()
        time.sleep(poll_interval)
