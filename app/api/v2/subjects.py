"""Phase 4 受试者与审核节点基础 API（design.md §5.1，薄路由）。

路由只做协议转换，不做领域判断：调用证据读取服务与领域合同，把领域合同映射为
带中文投影标签的 DTO。本模块不导入 SQLAlchemy 或 ``app.storage``（薄 API 边界
验收由 AST 测试强制）：

- ``POST /projects/{project_id}/subjects`` 的 ``project_id`` 以路径为准，
  新增受试者必须属于该正式项目；
- ``GET /subjects/{subject_id}/review-episodes`` 返回该受试者全部审核节点，
  跨项目/跨受试者串入由读取服务拒绝；
- 审核节点 DTO 暴露成对活动指针 ``active_evidence_snapshot_id`` 与
  ``active_evidence_processing_revision_id``（current 唯一权威）。

每个请求经读取服务/会话边界；错误统一经 ``errors.py`` 信封返回。
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi import status as http_status

from app.api.v2.schemas import (
    EpisodeDTO,
    EpisodeListDTO,
    SubjectCreateRequest,
    SubjectDTO,
    SubjectListDTO,
)
from app.api.v2.vocabulary import review_stage_label, study_phase_label
from app.domain.contracts.review import ReviewEpisode, Subject
from app.services.evidence_api_read_service import EvidenceApiReadService

router = APIRouter(prefix="/api/v2", tags=["v2-subjects"])


def _read(request: Request) -> EvidenceApiReadService:
    return request.app.state.evidence_api_read_service


def _as_utc(value: datetime | None) -> datetime | None:
    """恢复存储层的 UTC 约定（数据库存 UTC naive，API 边界补回时区）。"""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _subject_dto(subject: Subject) -> SubjectDTO:
    return SubjectDTO(
        subject_id=subject.subject_id,
        subject_code=subject.subject_code,
        project_id=subject.project_id,
        center_code=subject.center_code,
        center_name=subject.center_name,
        sex=subject.sex,
        age_years=subject.age_years,
        revision=subject.revision,
    )


def _episode_dto(
    episode: ReviewEpisode,
    *,
    latest_evidence_snapshot_id: str | None = None,
    workflow_stage_label: str | None = None,
    visit_window: str | None = None,
) -> EpisodeDTO:
    phase = episode.study_phase.value if hasattr(episode.study_phase, "value") else episode.study_phase
    stage = episode.stage.value if hasattr(episode.stage, "value") else episode.stage
    anchor_dates: dict[str, Any] = {}
    for key, value in episode.anchor_dates.items():
        key_name = key.value if hasattr(key, "value") else key
        if hasattr(value, "model_dump"):
            anchor_dates[key_name] = value.model_dump(mode="json")
        else:
            anchor_dates[key_name] = value
    return EpisodeDTO(
        review_episode_id=episode.review_episode_id,
        subject_id=episode.subject_id,
        project_id=episode.project_id,
        rule_set_id=episode.rule_set_id,
        study_phase=phase,
        study_phase_label=study_phase_label(str(phase)),
        stage=stage,
        stage_label=review_stage_label(str(stage)),
        protocol_version_id=episode.protocol_version_id,
        rule_set_revision=episode.rule_set_revision,
        evidence_snapshot_id=episode.evidence_snapshot_id,
        workflow_stage_id=episode.workflow_stage_id,
        workflow_stage_label=workflow_stage_label,
        visit_window=visit_window,
        latest_evidence_snapshot_id=latest_evidence_snapshot_id,
        active_evidence_snapshot_id=episode.active_evidence_snapshot_id,
        active_evidence_processing_revision_id=(
            episode.active_evidence_processing_revision_id
        ),
        anchor_dates=anchor_dates,
        due_at=_as_utc(episode.due_at),
        revision=episode.revision,
    )


@router.get(
    "/projects/{project_id}/subjects",
    response_model=SubjectListDTO,
)
def list_subjects(project_id: str, request: Request) -> SubjectListDTO:
    read = _read(request)
    # 项目不存在 -> 404，不返回空列表伪装成功。
    if read.project_row(project_id) is None:
        from app.services.evidence_app_errors import AppNotFoundError

        raise AppNotFoundError(f"Project {project_id} 不存在")
    subjects = read.subjects_by_project(project_id)
    return SubjectListDTO(
        project_id=project_id,
        items=[_subject_dto(subject) for subject in subjects],
    )


@router.post(
    "/projects/{project_id}/subjects",
    response_model=SubjectDTO,
    status_code=http_status.HTTP_201_CREATED,
)
def create_subject(
    project_id: str, body: SubjectCreateRequest, request: Request
) -> SubjectDTO:
    subject = Subject(
        subject_id=uuid4().hex,
        subject_code=body.subject_code,
        project_id=project_id,
        center_code=body.center_code,
        center_name=body.center_name,
        sex=body.sex,
        age_years=body.age_years,
    )
    saved = request.app.state.evidence_api_command_service.create_subject(subject)
    return _subject_dto(saved)


@router.delete(
    "/projects/{project_id}/subjects/{subject_id}",
    response_model=SubjectDTO,
)
def delete_subject(project_id: str, subject_id: str, request: Request) -> SubjectDTO:
    """删除受试者：只允许尚未承载资料或审核内容的受试者（P4-R04）。

    随受试者自动建立的空审核节点会一并删除；任一节点已承载资料或审核内容时
    返回 409 ``SUBJECT_IN_USE``。受试者不存在或不属于路径项目返回 404。
    """
    deleted = request.app.state.evidence_api_command_service.delete_subject(
        project_id, subject_id
    )
    return _subject_dto(deleted)


@router.get(
    "/subjects/{subject_id}/review-episodes",
    response_model=EpisodeListDTO,
)
def list_review_episodes(subject_id: str, request: Request) -> EpisodeListDTO:
    read = _read(request)
    subject = read.subject(subject_id)  # 不存在 -> 404，不返回空列表伪装成功
    episodes = read.episodes_by_subject(subject_id, project_id=subject.project_id)
    stage_ids = [
        episode.workflow_stage_id
        for episode in episodes
        if episode.workflow_stage_id is not None
    ]
    stages = read.workflow_stages_by_ids(stage_ids)
    return EpisodeListDTO(
        subject_id=subject_id,
        items=[
            _episode_dto(
                episode,
                latest_evidence_snapshot_id=read.latest_snapshot_id(
                    episode.review_episode_id
                ),
                workflow_stage_label=(
                    stages[episode.workflow_stage_id].display_name
                    if episode.workflow_stage_id in stages
                    else None
                ),
                visit_window=(
                    stages[episode.workflow_stage_id].visit_window
                    if episode.workflow_stage_id in stages
                    else None
                ),
            )
            for episode in episodes
        ],
    )
