"""Source-bound preparation and evaluated-method formal-save adapters.

This route accepts identities only, never caller-supplied facts or approvals.
It does not perform model inference or grant method adoption.
Registration does not waive the command's evaluation and approval checks.
"""
from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.services.evidence_app_errors import translate_storage_error
from app.services.qualified_review_command import submit_qualified_review
from app.services.review_preparation_command import prepare_review
from app.domain.contracts.facts import FactAuthority
from app.services.prepared_review_intake import ReviewTaskKind
from app.services.prepared_review_progress import read_prepared_review_progress
from app.services.prepared_review_workflow_view import read_review_workflow
from app.services.prepared_review_workflow import change_review_workflow
from app.api.v2.vocabulary import JOB_STATE_LABELS

router = APIRouter(prefix="/api/v2", tags=["v2-qualified-review"])


class QualifiedReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_id: str = Field(min_length=1)
    qualification_job_ids: list[str] = Field(min_length=1, max_length=2)
    judgment_content_job_ids: dict[str, str] = Field(default_factory=dict, max_length=2)
    proposition_evidence_job_ids: dict[str, str] = Field(default_factory=dict, max_length=2)
    observation_relation_job_ids: dict[str, str] = Field(default_factory=dict, max_length=2)
    frequency_evidence_job_ids: dict[str, str] = Field(default_factory=dict, max_length=2)
    method_approval_gate_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class QualifiedReviewResponse(BaseModel):
    review_run_id: str


class ReviewPreparationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_authority: FactAuthority
    idempotency_key: str = Field(min_length=1)


class ReviewPreparationResponse(BaseModel):
    context_id: str
    context_sha256: str
    review_run_id: str


class PreparedReviewTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_id: str = Field(min_length=1)
    kind: ReviewTaskKind
    candidate_job_id: str | None = Field(default=None, min_length=1)


class PreparedReviewWorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context_id: str = Field(min_length=1)


class PreparedReviewTaskResponse(BaseModel):
    job_id: str
    state: str
    state_label: str
    created: bool


@router.post("/subjects/{subject_id}/review-episodes/{review_episode_id}/prepared-review-workflows/{workflow_id}/publish",
             response_model=QualifiedReviewResponse)
def publish_workflow_report(subject_id: str, review_episode_id: str, workflow_id: str, request: Request):
    from app.config import ENROLLMENT_REVIEW_METHOD_APPROVAL_GATE_ID
    from app.services.prepared_review_publication import publish_prepared_review
    try:
        with request.app.state.session_factory() as session, session.begin():
            run_id = publish_prepared_review(
                session, request.app.state.artifact_store, subject_id=subject_id,
                review_episode_id=review_episode_id, workflow_id=workflow_id,
                method_approval_gate_id=ENROLLMENT_REVIEW_METHOD_APPROVAL_GATE_ID,
            )
    except Exception as exc:
        translated = translate_storage_error(exc)
        if translated is not None:
            raise translated from exc
        raise
    return QualifiedReviewResponse(review_run_id=run_id)


@router.post("/subjects/{subject_id}/review-episodes/{review_episode_id}/prepared-review-workflows",
             response_model=PreparedReviewTaskResponse, status_code=201)
def create_prepared_review_workflow(subject_id: str, review_episode_id: str,
                                   body: PreparedReviewWorkflowRequest, request: Request, response: Response):
    result = request.app.state.page_review_runtime.enqueue_review_workflow(
        subject_id=subject_id, review_episode_id=review_episode_id, context_id=body.context_id,
    )
    if not result.created:
        response.status_code = 200
    return PreparedReviewTaskResponse(job_id=result.job_id, state=result.state, created=result.created,
                                     state_label=JOB_STATE_LABELS.get(result.state, "状态待更新"))


class PreparedReviewProgressItem(BaseModel):
    job_id: str
    kind: ReviewTaskKind
    candidate_job_id: str | None
    state: str
    state_label: str
    progress_completed: int
    progress_total: int


class PreparedReviewProgressResponse(BaseModel):
    context_id: str
    context_sha256: str
    items: list[PreparedReviewProgressItem]
    next_cursor: str | None


class PreparedReviewWorkflowResponse(BaseModel):
    report_saved: bool
    job_id: str
    context_id: str
    context_sha256: str
    review_run_id: str
    state: str
    state_label: str
    stage_label: str
    progress_completed: int
    progress_total: int
    items: list[PreparedReviewProgressItem]


class PreparedReviewWorkflowActionResponse(BaseModel):
    state: str
    state_label: str
    changed: bool


@router.get("/subjects/{subject_id}/review-episodes/{review_episode_id}/prepared-review-workflows/{workflow_id}",
            response_model=PreparedReviewWorkflowResponse)
def get_review_workflow(subject_id: str, review_episode_id: str, workflow_id: str, request: Request):
    try:
        with request.app.state.session_factory() as session:
            result = read_review_workflow(session, subject_id=subject_id,
                                          review_episode_id=review_episode_id, workflow_id=workflow_id)
    except Exception as exc:
        translated = translate_storage_error(exc)
        if translated is not None:
            raise translated from exc
        raise
    result["state_label"] = (
        "审核报告已保存" if result["report_saved"]
        else "核对完成，尚未保存审核报告" if result["state"] == "completed"
        else "正在核对" if result["state"] == "queued" and result["items"]
        else JOB_STATE_LABELS.get(result["state"], "状态待更新"))
    for item in result["items"]:
        item["state_label"] = JOB_STATE_LABELS.get(item["state"], "状态待更新")
    return PreparedReviewWorkflowResponse(**result)


@router.post("/subjects/{subject_id}/review-episodes/{review_episode_id}/prepared-review-workflows/{workflow_id}/cancel",
             response_model=PreparedReviewWorkflowActionResponse)
def cancel_review_workflow(subject_id: str, review_episode_id: str, workflow_id: str, request: Request):
    try:
        result = change_review_workflow(request.app.state.session_factory, subject_id=subject_id,
                                        review_episode_id=review_episode_id, workflow_id=workflow_id, operation="cancel")
    except Exception as exc:
        translated = translate_storage_error(exc)
        if translated is not None:
            raise translated from exc
        raise
    return PreparedReviewWorkflowActionResponse(state=result.state, changed=result.changed,
                                                state_label=JOB_STATE_LABELS.get(result.state, "状态待更新"))


@router.post("/subjects/{subject_id}/review-episodes/{review_episode_id}/prepared-review-workflows/{workflow_id}/retry",
             response_model=PreparedReviewWorkflowActionResponse)
def retry_review_workflow(subject_id: str, review_episode_id: str, workflow_id: str, request: Request):
    result = request.app.state.page_review_runtime.retry_review_workflow(
        subject_id=subject_id, review_episode_id=review_episode_id, workflow_id=workflow_id,
    )
    return PreparedReviewWorkflowActionResponse(state=result.state, changed=result.changed,
                                                state_label=JOB_STATE_LABELS.get(result.state, "状态待更新"))


@router.get("/subjects/{subject_id}/review-episodes/{review_episode_id}/prepared-review-jobs",
            response_model=PreparedReviewProgressResponse)
def get_prepared_review_progress(subject_id: str, review_episode_id: str, request: Request,
                                context_id: str = Query(min_length=1),
                                after_job_id: str | None = Query(default=None, min_length=1),
                                limit: int = Query(default=50, ge=1, le=100)):
    try:
        with request.app.state.session_factory() as session:
            result = read_prepared_review_progress(
                session, subject_id=subject_id, review_episode_id=review_episode_id,
                context_id=context_id, after_job_id=after_job_id, limit=limit,
            )
    except Exception as exc:
        translated = translate_storage_error(exc)
        if translated is not None:
            raise translated from exc
        raise
    for item in result["items"]:
        item["state_label"] = JOB_STATE_LABELS.get(item["state"], "状态待更新")
    return PreparedReviewProgressResponse(**result)


@router.post("/subjects/{subject_id}/review-episodes/{review_episode_id}/prepared-review-jobs",
             response_model=PreparedReviewTaskResponse, status_code=201)
def create_prepared_review_task(subject_id: str, review_episode_id: str,
                               body: PreparedReviewTaskRequest, request: Request,
                               response: Response):
    result = request.app.state.page_review_runtime.enqueue_prepared_review(
        subject_id=subject_id, review_episode_id=review_episode_id, **body.model_dump(),
    )
    if not result.created:
        response.status_code = 200
    return PreparedReviewTaskResponse(
        job_id=result.job_id, state=result.state, created=result.created,
        state_label=JOB_STATE_LABELS.get(result.state, "状态待更新"),
    )


@router.post("/subjects/{subject_id}/review-episodes/{review_episode_id}/review-preparations",
             response_model=ReviewPreparationResponse)
def prepare_qualified_review(subject_id: str, review_episode_id: str,
                             body: ReviewPreparationRequest, request: Request):
    try:
        with request.app.state.session_factory() as session, session.begin():
            context = prepare_review(
                session, request.app.state.artifact_store,
                subject_id=subject_id, review_episode_id=review_episode_id,
                expected_authority=body.expected_authority, idempotency_key=body.idempotency_key,
            )
    except Exception as exc:
        translated = translate_storage_error(exc)
        if translated is not None:
            raise translated from exc
        raise
    return ReviewPreparationResponse(
        context_id=context.context_id, context_sha256=context.context_sha256,
        review_run_id=context.review_run_id,
    )


@router.post("/subjects/{subject_id}/review-episodes/{review_episode_id}/qualified-reviews",
             response_model=QualifiedReviewResponse)
def save_qualified_review(subject_id: str, review_episode_id: str,
                          body: QualifiedReviewRequest, request: Request):
    try:
        with request.app.state.session_factory() as session, session.begin():
            run_id = submit_qualified_review(
                session, request.app.state.artifact_store,
                subject_id=subject_id, review_episode_id=review_episode_id, **body.model_dump(),
            )
    except Exception as exc:
        translated = translate_storage_error(exc)
        if translated is not None:
            raise translated from exc
        raise
    return QualifiedReviewResponse(review_run_id=run_id)
