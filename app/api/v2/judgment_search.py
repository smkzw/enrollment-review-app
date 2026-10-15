"""判断检索任务正式入口：服务端派生权威与目标组，客户端只提交意图。"""

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.v2.schemas import JobActionResponse
from app.api.v2.vocabulary import JOB_STATE_LABELS
from app.services.judgment_search_status import (
    judgment_search_job_results,
    judgment_search_job_status,
)

router = APIRouter(prefix="/api/v2", tags=["v2-judgment-search"])


class JudgmentSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirement_ids: list[str] | None = Field(
        default=None,
        description="留空时由系统按当前审核节点自动确定需要检索书面判断的资料要求",
    )


class JudgmentSearchSubmit(BaseModel):
    job_id: str
    state: str
    state_label: str
    created: bool


@router.post("/subjects/{subject_id}/review-episodes/{review_episode_id}/judgment-search-jobs",
             response_model=JudgmentSearchSubmit, status_code=201)
def create_judgment_search(subject_id: str, review_episode_id: str,
                           body: JudgmentSearchRequest, request: Request,
                           response: Response):
    request.app.state.evidence_api_read_service.require_subject_episode(subject_id, review_episode_id)
    result = request.app.state.page_review_runtime.enqueue_judgment_search(
        subject_id=subject_id, review_episode_id=review_episode_id,
        requirement_ids=body.requirement_ids)
    if not result.created:
        response.status_code = 200
    return JudgmentSearchSubmit(job_id=result.job_id, state=result.state,
                                created=result.created,
                                state_label=JOB_STATE_LABELS.get(result.state, "状态待更新"))


@router.get("/subjects/{subject_id}/review-episodes/{review_episode_id}/judgment-search-jobs/{job_id}")
def get_judgment_search(subject_id: str, review_episode_id: str, job_id: str,
                        request: Request):
    request.app.state.evidence_api_read_service.require_subject_episode(subject_id, review_episode_id)
    return judgment_search_job_status(request.app.state.session_factory,
                                      subject_id=subject_id,
                                      review_episode_id=review_episode_id, job_id=job_id)


@router.get("/subjects/{subject_id}/review-episodes/{review_episode_id}/judgment-search-jobs/{job_id}/results")
def get_judgment_search_results(subject_id: str, review_episode_id: str, job_id: str,
                                request: Request):
    """每条要求的候选摘录与未完成页，供界面定位原件核对；只读。"""
    request.app.state.evidence_api_read_service.require_subject_episode(subject_id, review_episode_id)
    return judgment_search_job_results(request.app.state.session_factory,
                                       subject_id=subject_id,
                                       review_episode_id=review_episode_id, job_id=job_id)


@router.post("/subjects/{subject_id}/review-episodes/{review_episode_id}/judgment-search-jobs/{job_id}/resume",
             response_model=JobActionResponse)
def resume_judgment_search(subject_id: str, review_episode_id: str, job_id: str,
                           request: Request):
    """受控续跑已取消的书面判断检索；节点内显式操作，不新建任务。"""
    request.app.state.evidence_api_read_service.require_subject_episode(subject_id, review_episode_id)
    outcome = request.app.state.page_review_runtime.resume_judgment_search(
        subject_id=subject_id, review_episode_id=review_episode_id, job_id=job_id)
    return JobActionResponse(job_id=job_id, state=outcome.state,
                             changed=outcome.changed,
                             state_label=JOB_STATE_LABELS.get(outcome.state, "状态待更新"))
