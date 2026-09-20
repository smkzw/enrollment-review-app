"""Explicit batch intake and reconnectable progress, never clinical publication."""
from typing import Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.v2.review_action_worklist import _raise_translated
from app.services.batch_review_workflow import enqueue_batch_review, change_batch_review
from app.services.batch_review_view import batch_review_view, recent_review_batches
from app.services.batch_processing_estimates import estimate_processing_batch

router = APIRouter(prefix="/api/v2/projects/{project_id}/review-batches", tags=["v2-review-batches"])


class Member(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_id: str = Field(min_length=1, max_length=128)
    review_episode_id: str = Field(min_length=1, max_length=128)
    context_id: str = Field(min_length=1, max_length=128)


class BatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_key: str = Field(min_length=1, max_length=128)
    members: list[Member] = Field(min_length=1, max_length=50)


class EstimateMember(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_id: str = Field(min_length=1, max_length=128)
    review_episode_id: str = Field(min_length=1, max_length=128)
    snapshot_id: str = Field(min_length=1, max_length=128)
    complete_id: str = Field(min_length=1, max_length=128)


class EstimateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    members: list[EstimateMember] = Field(min_length=1, max_length=50)


@router.post("/estimate")
def estimate(project_id: str, body: EstimateRequest, request: Request):
    """Read-only historical reference; never prepares or starts a review."""
    try:
        routes = request.app.state.page_review_runtime.configured_review_routes()
        with request.app.state.session_factory() as session:
            return estimate_processing_batch(session, project_id=project_id, kind="review",
                members=[item.model_dump() for item in body.members], routes=routes)
    except Exception as exc:
        _raise_translated(exc)


@router.get("")
def recent(project_id: str, request: Request, offset: int = Query(default=0, ge=0, le=100000)):
    try:
        with request.app.state.session_factory() as session:
            return recent_review_batches(session, project_id=project_id, offset=offset)
    except Exception as exc:
        _raise_translated(exc)


@router.post("")
def create(project_id: str, body: BatchRequest, request: Request):
    try:
        result = enqueue_batch_review(request.app.state.session_factory,
            request.app.state.page_review_runtime.prepared_review_routes(),
            project_id=project_id, request_key=body.request_key,
            members=[item.model_dump() for item in body.members])
        return {"job_id": result.job_id, "state": result.state, "created": result.created}
    except Exception as exc:
        _raise_translated(exc)


@router.get("/{batch_id}")
def read(project_id: str, batch_id: str, request: Request):
    try:
        with request.app.state.session_factory() as session:
            return batch_review_view(session, project_id=project_id, batch_id=batch_id)
    except Exception as exc:
        _raise_translated(exc)


@router.post("/{batch_id}/{operation}")
def change(project_id: str, batch_id: str, operation: Literal["cancel", "retry"], request: Request):
    try:
        result = change_batch_review(request.app.state.session_factory,
            None if operation == "cancel" else request.app.state.page_review_runtime.prepared_review_routes(),
            project_id=project_id, batch_id=batch_id, operation=operation)
        return {"job_id": batch_id, "state": result.state, "changed": result.changed}
    except Exception as exc:
        _raise_translated(exc)
