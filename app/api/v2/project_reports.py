"""已保存审核报告目录，不生成或合并临床结论。"""
from datetime import datetime

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict

from app.api.v2.review_action_worklist import _raise_translated, _session
from app.services.project_report_catalog import list_project_reports

router = APIRouter(prefix="/api/v2", tags=["v2-project-reports"])


class ProjectReportDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    subject_id: str
    subject_code: str
    review_episode_id: str
    review_run_id: str
    workflow_stage_label: str
    center_code: str | None
    center_name: str | None
    completed_at: datetime
    official_protocol_version: str


class ReportCursorDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    completed_at: datetime
    review_run_id: str


class ProjectReportsDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    items: list[ProjectReportDTO]
    next_cursor: ReportCursorDTO | None


@router.get("/projects/{project_id}/saved-reports", response_model=ProjectReportsDTO)
def saved_reports(
    project_id: str, request: Request,
    center_code: str | None = Query(default=None, min_length=1),
    before_completed_at: datetime | None = None,
    before_run_id: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=20, ge=1, le=50),
):
    with _session(request) as session:
        try:
            page = list_project_reports(
                session, project_id=project_id, center_code=center_code,
                before_completed_at=before_completed_at, before_run_id=before_run_id,
                limit=limit,
            )
            return ProjectReportsDTO(
                project_id=project_id,
                items=[ProjectReportDTO.model_validate(item) for item in page.items],
                next_cursor=ReportCursorDTO(
                    completed_at=page.next_cursor[0], review_run_id=page.next_cursor[1],
                ) if page.next_cursor else None,
            )
        except Exception as exc:
            _raise_translated(exc)
            raise
