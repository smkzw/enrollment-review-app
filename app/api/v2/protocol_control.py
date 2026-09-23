"""Thin API routes for durable protocol-control execution (start and read status)."""
from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi import status as http_status

from app.api.v2.protocol_control_schemas import (
    ProtocolControlExecutionStatusResponse,
    ProtocolControlRequirementsResponse,
    StartProtocolControlExecutionRequest,
    StartProtocolControlExecutionResponse,
)
from app.api.v2.vocabulary import JOB_STATE_LABELS
from app.services.protocol_control_job_service import ProtocolControlJobService
from app.services.protocol_control_status import protocol_control_execution_status, protocol_control_requirements


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
        discovery_source_job_id=body.discovery_source_job_id,
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


@router.get("/{job_id}", response_model=ProtocolControlExecutionStatusResponse)
def get_protocol_control_execution_status(
    job_id: str,
    request: Request,
) -> ProtocolControlExecutionStatusResponse:
    """Read-only publication checkpoint; never calls a model or writes state."""
    snapshot = protocol_control_execution_status(
        _service(request).session_factory, job_id=job_id
    )
    return ProtocolControlExecutionStatusResponse(
        job_id=snapshot.job_id,
        state=snapshot.state,
        state_label=JOB_STATE_LABELS.get(snapshot.state, snapshot.state),
        source_job_id=snapshot.source_job_id,
        status=snapshot.status,
        status_label=snapshot.status_label,
        publishable_checkpoint_id=snapshot.publishable_checkpoint_id,
        candidate_count=snapshot.candidate_count,
    )


@router.get("/{job_id}/requirements", response_model=ProtocolControlRequirementsResponse)
def get_protocol_control_requirements(job_id: str, request: Request) -> ProtocolControlRequirementsResponse:
    view = protocol_control_requirements(_service(request).session_factory, job_id=job_id)
    return ProtocolControlRequirementsResponse(
        job_id=view.job_id, source_job_id=view.source_job_id, checkpoint_id=view.checkpoint_id,
        candidates=list(view.candidates), workflow_stages=list(view.workflow_stages),
        relation_target_labels=dict(view.relation_target_labels),
    )
