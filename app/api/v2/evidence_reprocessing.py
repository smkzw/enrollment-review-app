"""Explicit reprocessing intake, keeping original material and reports untouched."""
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.v2.review_action_worklist import _raise_translated
from app.services.evidence_reprocessing import enqueue_reprocessing, reprocessing_view

router = APIRouter(prefix="/api/v2/projects/{project_id}/evidence-reprocessing", tags=["v2-evidence-reprocessing"])


class ReprocessingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_id: str = Field(min_length=1, max_length=128)
    review_episode_id: str = Field(min_length=1, max_length=128)
    snapshot_id: str = Field(min_length=1, max_length=128)
    complete_id: str = Field(min_length=1, max_length=128)
    request_key: str = Field(min_length=1, max_length=128)


@router.post("")
def create(project_id: str, body: ReprocessingRequest, request: Request):
    try:
        result = enqueue_reprocessing(request.app.state.session_factory,
            request.app.state.evidence_reprocess_adapter, project_id=project_id, **body.model_dump())
        return {"job_id": result.job_id, "state": result.state, "created": result.created}
    except Exception as exc:
        _raise_translated(exc)


@router.get("/{job_id}")
def read(project_id: str, job_id: str, request: Request):
    try:
        with request.app.state.session_factory() as session:
            return reprocessing_view(session, project_id=project_id, job_id=job_id)
    except Exception as exc:
        _raise_translated(exc)
