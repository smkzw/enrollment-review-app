"""Start page review from a server-resolved active episode."""

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from app.api.v2.schemas import JobActionResponse
from app.api.v2.vocabulary import JOB_STATE_LABELS
from app.services.page_review_status import page_review_status
from app.services.targeted_page_review_status import targeted_review_status
from app.domain.contracts.targeted_review_outcome import TargetedReviewOutcome
from app.services.targeted_page_review_detail import TargetedReviewEvidence, targeted_review_evidence
from app.services.targeted_review_candidates import targeted_review_candidates

router = APIRouter(prefix="/api/v2", tags=["v2-page-review"])


class PageReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    predecessor_job_id: str | None = Field(default=None, min_length=1)
    single_length_recovery: bool = Field(default=False, strict=True)


class PageReviewSubmit(BaseModel):
    job_id: str
    state: str
    state_label: str
    created: bool


class TargetedReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    original_job_id: str = Field(min_length=1)
    page_index: int = Field(ge=0, strict=True)


class TargetedReviewStatus(BaseModel):
    job_id: str
    state: str
    round_budget: Literal[2]
    rounds_with_receipts: int
    original_reconciliation_id: str
    status_label: str
    outcome: TargetedReviewOutcome | None


@router.get("/subjects/{subject_id}/review-episodes/{review_episode_id}/targeted-review-jobs/{job_id}/evidence",
            response_model=TargetedReviewEvidence)
def get_targeted_review_evidence(subject_id: str, review_episode_id: str, job_id: str, request: Request):
    request.app.state.evidence_api_read_service.require_subject_episode(subject_id, review_episode_id)
    return targeted_review_evidence(request.app.state.session_factory, subject_id=subject_id,
                                    review_episode_id=review_episode_id, job_id=job_id)


@router.get("/subjects/{subject_id}/review-episodes/{review_episode_id}/targeted-review-jobs/{job_id}",
            response_model=TargetedReviewStatus)
def get_targeted_review(subject_id: str, review_episode_id: str, job_id: str, request: Request):
    request.app.state.evidence_api_read_service.require_subject_episode(subject_id, review_episode_id)
    return targeted_review_status(request.app.state.session_factory, subject_id=subject_id,
                                 review_episode_id=review_episode_id, job_id=job_id)


@router.post("/subjects/{subject_id}/review-episodes/{review_episode_id}/targeted-review-jobs",
             response_model=PageReviewSubmit, status_code=201)
def create_targeted_review(subject_id: str, review_episode_id: str, body: TargetedReviewRequest,
                           request: Request, response: Response):
    request.app.state.evidence_api_read_service.require_subject_episode(subject_id, review_episode_id)
    result = request.app.state.page_review_runtime.enqueue_targeted(
        subject_id=subject_id, review_episode_id=review_episode_id,
        original_job_id=body.original_job_id, page_index=body.page_index)
    if not result.created:
        response.status_code = 200
    return PageReviewSubmit(job_id=result.job_id, state=result.state, created=result.created,
                            state_label=JOB_STATE_LABELS.get(result.state, "状态待更新"))


class PageReviewStatus(BaseModel):
    job_id: str
    state: str
    review_status: Literal["processing", "stopped", "needs_reread", "ready"]
    status_label: str
    total_pages: int
    accepted_pages: int
    unrelated_pages: int
    failed_pages: int
    pending_pages: int
    can_reread: bool
    coverage_id: str | None
    predecessor_job_id: str | None


@router.get("/subjects/{subject_id}/review-episodes/{review_episode_id}/page-review-jobs/{job_id}/conflicts")
def get_review_candidates(subject_id: str, review_episode_id: str, job_id: str, request: Request):
    request.app.state.evidence_api_read_service.require_subject_episode(subject_id, review_episode_id)
    return targeted_review_candidates(request.app.state.session_factory, subject_id=subject_id,
                                      review_episode_id=review_episode_id, job_id=job_id)


@router.get("/subjects/{subject_id}/review-episodes/{review_episode_id}/page-review-jobs/{job_id}",
            response_model=PageReviewStatus)
def get_page_review(subject_id: str, review_episode_id: str, job_id: str, request: Request):
    request.app.state.evidence_api_read_service.require_subject_episode(subject_id, review_episode_id)
    return page_review_status(request.app.state.session_factory, subject_id=subject_id,
                              review_episode_id=review_episode_id, job_id=job_id)


@router.post("/subjects/{subject_id}/review-episodes/{review_episode_id}/page-review-jobs",
             response_model=PageReviewSubmit, status_code=201)
def create_page_review(subject_id: str, review_episode_id: str, body: PageReviewRequest,
                       request: Request, response: Response):
    request.app.state.evidence_api_read_service.require_subject_episode(subject_id, review_episode_id)
    result = request.app.state.page_review_runtime.enqueue(
        subject_id=subject_id, review_episode_id=review_episode_id,
        predecessor_job_id=body.predecessor_job_id, single_length_recovery=body.single_length_recovery)
    if not result.created:
        response.status_code = 200
    return PageReviewSubmit(job_id=result.job_id, state=result.state, created=result.created,
                            state_label=JOB_STATE_LABELS.get(result.state, "状态待更新"))


@router.post("/subjects/{subject_id}/review-episodes/{review_episode_id}/page-review-jobs/{job_id}/resume",
             response_model=JobActionResponse)
def resume_page_review(subject_id: str, review_episode_id: str, job_id: str, request: Request):
    """受控续跑已取消的页级判读；节点内显式操作，不新建任务。"""
    request.app.state.evidence_api_read_service.require_subject_episode(subject_id, review_episode_id)
    outcome = request.app.state.page_review_runtime.resume(
        subject_id=subject_id, review_episode_id=review_episode_id, job_id=job_id)
    return JobActionResponse(job_id=job_id, state=outcome.state, changed=outcome.changed,
                             state_label=JOB_STATE_LABELS.get(outcome.state, "状态待更新"))
