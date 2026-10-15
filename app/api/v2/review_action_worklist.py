"""项目正式审核待办只读清单的薄 HTTP 适配层。

路由只做会话边界与协议转换：候选筛选、冻结运行核对与完整性判断全部由
:mod:`app.services.review_action_worklist` 完成。本模块不导入 SQLAlchemy 或
``app.storage``，不计算判定、不补齐缺口、不发布任何内容，也不构成批准方法或
发布结果的权限。人工办理命令仍由 :mod:`app.api.v2.review_actions` 单独提供。

- ``GET /api/v2/projects/{project_id}/review-actions``
  项目作用域待办清单；``mode=open|all``，``limit`` 1–100（默认 50），
  ``after_action_id`` 可选 action-id keyset。响应含 ``project_id``、``mode``、
  ``items``、``next_after_action_id``，不发明全局总数或临床完成度。

本模块不做应用注册（由 owner 接入 ``create_app``）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.v2.review_history import ReviewHistoryActionDTO, _action_dto
from app.domain.contracts.enums import ReviewStage
from app.services.evidence_app_errors import translate_storage_error
from app.services.review_action_worklist import (
    ReviewActionWorklistItem,
    ReviewActionWorklistMode,
    ReviewActionWorklistPage,
    list_review_action_worklist,
)

router = APIRouter(prefix="/api/v2", tags=["v2-review-action-worklist"])


class ProjectEvidenceNodeDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_episode_id: str
    display_name: str
    active_evidence_snapshot_id: str | None
    active_evidence_processing_revision_id: str | None


class ProjectEvidenceSubjectDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_id: str
    subject_code: str
    center_code: str | None
    center_name: str | None
    nodes: list[ProjectEvidenceNodeDTO]


class ProjectEvidenceOverviewDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    items: list[ProjectEvidenceSubjectDTO]


@router.get("/projects/{project_id}/evidence-overview", response_model=ProjectEvidenceOverviewDTO)
def evidence_overview(project_id: str, request: Request):
    from app.services.project_evidence_overview import project_evidence_overview
    from app.api.v2.vocabulary import review_stage_label

    with _session(request) as session:
        try:
            rows = project_evidence_overview(session, project_id)
            return ProjectEvidenceOverviewDTO(project_id=project_id, items=[
                ProjectEvidenceSubjectDTO(
                    subject_id=row.subject.subject_id, subject_code=row.subject.subject_code,
                    center_code=row.subject.center_code, center_name=row.subject.center_name,
                    nodes=[ProjectEvidenceNodeDTO(
                        review_episode_id=node.episode.review_episode_id,
                        display_name=node.display_name or review_stage_label(node.episode.stage.value),
                        active_evidence_snapshot_id=node.episode.active_evidence_snapshot_id,
                        active_evidence_processing_revision_id=node.episode.active_evidence_processing_revision_id,
                    ) for node in row.nodes],
                ) for row in rows
            ])
        except Exception as exc:
            _raise_translated(exc)
            raise


class RecentReviewDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    subject_id: str
    subject_code: str
    review_episode_id: str
    review_run_id: str
    workflow_stage_label: str
    started_at: datetime
    completed_at: datetime | None


class RecentReviewsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    items: list[RecentReviewDTO]
    has_more: bool


@router.get("/projects/{project_id}/recent-reviews", response_model=RecentReviewsResponse)
def recent_reviews(project_id: str, request: Request,
                   limit: int = Query(default=6, ge=1, le=20)):
    from app.services.recent_project_reviews import recent_project_reviews

    with _session(request) as session:
        try:
            items, has_more = recent_project_reviews(session, project_id=project_id, limit=limit)
            return RecentReviewsResponse(project_id=project_id,
                items=[RecentReviewDTO.model_validate(item) for item in items], has_more=has_more)
        except Exception as exc:
            _raise_translated(exc)
            raise


class ReviewActionWorklistItemDTO(BaseModel):
    """已核对待办 + 链接原冻结报告所需的上下文身份。"""

    model_config = ConfigDict(extra="forbid")

    action: ReviewHistoryActionDTO
    project_name: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    subject_code: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    review_run_id: str = Field(min_length=1)
    workflow_stage_label: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime | None


class ReviewActionWorklistResponse(BaseModel):
    """项目待办只读页；空列表合法，不含全局总数。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    mode: ReviewActionWorklistMode
    items: list[ReviewActionWorklistItemDTO] = Field(default_factory=list)
    next_after_action_id: str | None = None


def _session(request: Request):
    """应用会话工厂：路由只调用工厂，不导入 SQLAlchemy/存储类型。"""
    return request.app.state.session_factory()


def _raise_translated(exc: Exception) -> None:
    """存储/服务层失败 -> 稳定应用错误信封；未知异常原样上抛。"""
    translated = translate_storage_error(exc)
    if translated is not None:
        raise translated from exc
    raise exc


def _item_dto(item: ReviewActionWorklistItem) -> ReviewActionWorklistItemDTO:
    return ReviewActionWorklistItemDTO(
        action=_action_dto(item.action),
        project_name=item.project_name,
        subject_id=item.subject_id,
        subject_code=item.subject_code,
        review_episode_id=item.review_episode_id,
        review_run_id=item.review_run_id,
        workflow_stage_label=item.workflow_stage_label,
        started_at=item.started_at,
        completed_at=item.completed_at,
    )


@router.get(
    "/projects/{project_id}/review-actions",
    response_model=ReviewActionWorklistResponse,
)
def list_project_review_actions(
    project_id: str,
    request: Request,
    mode: Literal["open", "all"] = Query(default="open"),
    limit: int = Query(default=50, ge=1, le=100),
    after_action_id: str | None = Query(default=None, min_length=1),
    due_stage: ReviewStage | None = Query(default=None),
) -> ReviewActionWorklistResponse:
    """读取项目内已冻结正式审核待办；不重算、不发布、不改办理状态。"""
    with _session(request) as session:
        try:
            page: ReviewActionWorklistPage = list_review_action_worklist(
                session,
                project_id=project_id,
                mode=mode,
                limit=limit,
                after_action_id=after_action_id,
                due_stage=due_stage,
            )
        except Exception as exc:  # noqa: BLE001 - 读取边界统一翻译
            _raise_translated(exc)
            raise
    return ReviewActionWorklistResponse(
        project_id=page.project_id,
        mode=page.mode,
        items=[_item_dto(item) for item in page.items],
        next_after_action_id=page.next_after_action_id,
    )


__all__ = [
    "ReviewActionWorklistItemDTO",
    "ReviewActionWorklistResponse",
    "list_project_review_actions",
    "router",
]
