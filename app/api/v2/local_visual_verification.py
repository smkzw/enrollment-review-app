"""Thin endpoints for candidate-only local source reading."""
from fastapi import APIRouter, Query, Request
from app.services.local_visual_verification import LocalVisualRegionRequest
from app.services.local_visual_comparison_job import LocalFieldComparisonRequest, LocalVisualComparisonService

router = APIRouter(tags=["v2-evidence-processing"])
_PATH = "/api/v2/evidence-processing-revisions/{revision_id}/pages/{page_id}/local-verification"


@router.post(_PATH, status_code=202)
def start_local_verification(revision_id: str, page_id: str, body: LocalVisualRegionRequest, request: Request):
    return request.app.state.local_visual_verification_service.enqueue(revision_id, page_id, body)


@router.get(_PATH)
def get_local_verification(revision_id: str, page_id: str, request: Request, job_id: str | None = Query(None)):
    return request.app.state.local_visual_verification_service.latest(revision_id, page_id, job_id=job_id)


def _comparison_service(request):
    source = request.app.state.local_visual_verification_service
    return LocalVisualComparisonService(source.session_factory, source.artifact_store)


@router.post(_PATH + "/comparison", status_code=202)
def start_field_comparison(revision_id: str, page_id: str, body: LocalFieldComparisonRequest, request: Request):
    return _comparison_service(request).enqueue(revision_id, page_id, body)


@router.get(_PATH + "/comparison")
def get_field_comparison(revision_id: str, page_id: str, request: Request,
                         visual_job_id: str, item_index: int = Query(ge=0), job_id: str | None = None):
    return _comparison_service(request).latest(revision_id, page_id, visual_job_id, item_index, job_id=job_id)
