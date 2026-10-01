"""Thin endpoints for candidate-only local source reading."""
from fastapi import APIRouter, Query, Request
from app.services.local_visual_verification import LocalVisualRegionRequest

router = APIRouter(tags=["v2-evidence-processing"])
_PATH = "/api/v2/evidence-processing-revisions/{revision_id}/pages/{page_id}/local-verification"


@router.post(_PATH, status_code=202)
def start_local_verification(revision_id: str, page_id: str, body: LocalVisualRegionRequest, request: Request):
    return request.app.state.local_visual_verification_service.enqueue(revision_id, page_id, body)


@router.get(_PATH)
def get_local_verification(revision_id: str, page_id: str, request: Request, job_id: str | None = Query(None)):
    return request.app.state.local_visual_verification_service.latest(revision_id, page_id, job_id=job_id)
