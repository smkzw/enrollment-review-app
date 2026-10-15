"""Bounded project history preview from verified frozen reports, not live verdicts."""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from app.services.review_action_worklist import _workflow_stage_label
from app.services.review_history_service import get_run, ReviewHistoryIncompleteError
from app.storage.models import ReviewRunRecord, ReviewEpisodeRecord
from app.storage.repositories import ProjectRepository


@dataclass(frozen=True)
class RecentProjectReview:
    subject_id: str
    subject_code: str
    review_episode_id: str
    review_run_id: str
    workflow_stage_label: str
    started_at: datetime
    completed_at: datetime | None


def recent_project_reviews(session, *, project_id, limit=6):
    if not 1 <= limit <= 20:
        raise ValueError("近期记录展示数量须在1至20之间")
    ProjectRepository(session).get(project_id)
    rows = session.execute(select(ReviewRunRecord, ReviewEpisodeRecord.subject_id).join(
        ReviewEpisodeRecord, ReviewEpisodeRecord.review_episode_id == ReviewRunRecord.review_episode_id,
    ).where(ReviewEpisodeRecord.project_id == project_id,
            ReviewRunRecord.evidence_snapshot_v2_id.is_not(None)).order_by(
        ReviewRunRecord.started_at.desc(), ReviewRunRecord.review_run_id.desc(),
    ).limit(limit + 1)).all()
    result = []
    for record, subject_id in rows[:limit]:
        detail = get_run(session, subject_id, record.review_episode_id, record.review_run_id)
        if detail.context.authority.project_id != project_id:
            raise ReviewHistoryIncompleteError("近期记录与所选研究项目不一致。", review_run_id=record.review_run_id)
        result.append(RecentProjectReview(
            subject_id=detail.context.authority.subject_id,
            subject_code=detail.context.subject.subject_code,
            review_episode_id=detail.run.review_episode_id,
            review_run_id=detail.run.review_run_id,
            workflow_stage_label=_workflow_stage_label(review_run_id=detail.run.review_run_id, context=detail.context),
            started_at=detail.run.started_at, completed_at=detail.run.completed_at,
        ))
    return tuple(result), len(rows) > limit
