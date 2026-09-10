"""Thin API route for starting durable protocol-control execution."""
from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi import status as http_status

from app.api.v2.protocol_control_schemas import (
    StartProtocolControlExecutionRequest,
    StartProtocolControlExecutionResponse,
)
from app.api.v2.vocabulary import JOB_STATE_LABELS
from app.services.protocol_control_job_service import ProtocolControlJobService


router = APIRouter(
    prefix="/api/v2/protocol/control-executions",
    tags=["v2-protocol-control"],
)


def _service(request: Request) -> ProtocolControlJobService:
    return request.app.state.protocol_control_job_service


@router.post(
    "",
    response_model=StartProtocolControlExecutionResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def start_protocol_control_execution(
    body: StartProtocolControlExecutionRequest,
    request: Request,
    response: Response,
) -> StartProtocolControlExecutionResponse:
    result = _service(request).create_from_deconstruction(
        source_job_id=body.source_job_id,
        idempotency_key=body.idempotency_key,
    )
    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    return StartProtocolControlExecutionResponse(
        job_id=result.job_id,
        state=result.state,
        state_label=JOB_STATE_LABELS.get(result.state, result.state),
        created=result.created,
        source_job_id=result.source_job_id,
        snapshot_id=result.snapshot_id,
        manifest_id=result.manifest_id,
    )
