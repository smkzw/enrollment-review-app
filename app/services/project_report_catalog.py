"""项目正式报告只读目录：已保存的冻结报告清单，不重算任何结论。

目录只列"正式已保存"的报告：``review/v2`` 冻结审核（``evidence_snapshot_v2_id``
非空）且 ``completed_at`` 非空的运行；SQL 先按 ``(completed_at, review_run_id)``
降序 keyset 取候选（固定 ``limit+1``），再逐条经
:func:`app.services.review_history_service.get_run` 核对项目、中心与完成态。

边界：

- 名称、中心与方案版本一律取自冻结 ``detail.context``（``project_name``、
  ``subject.center_code/center_name``、``protocol_document.official_version``），
  不读项目/受试者登记现值；
- 中心过滤按冻结 ``context.subject.center_code``（``payload_json`` canonical
  JSON 的 ``$.subject.center_code``），不按受试者当前登记中心；
- 不去掉同一受试者不同日期/审核节点的报告：目录原样呈现全部正式报告，导出
  勾选由调用方（UI）负责；
- 不给总完成率、总体入排结论或"每例最新结果"，不做任何临床再判断；
- 目录范围内任一可见记录与冻结源不一致则大声失败
  （:class:`ReviewHistoryIncompleteError`），绝不静默跳过当空。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.services.review_action_worklist import _workflow_stage_label
from app.services.evidence_app_errors import EvidenceAppError
from app.services.review_history_service import (
    ReviewHistoryIncompleteError,
    get_run,
)
from app.storage.codecs import to_utc_naive
from app.storage.models import (
    ReviewContextSnapshotRecord,
    ReviewEpisodeRecord,
    ReviewRunRecord,
)
from app.storage.repositories import ProjectRepository

__all__ = [
    "ProjectReportEntry",
    "ProjectReportPage",
    "list_project_reports",
]

#: 目录单页数量上限；调用方按游标翻页，不一次拉取全部历史。
CATALOG_PAGE_LIMIT_MAX = 50


class ProjectReportQueryError(EvidenceAppError):
    status_code = 422
    code = "PROJECT_REPORT_QUERY_INVALID"
    title = "报告查询条件不完整"
    recovery = "请重新打开报告目录后再试。"


@dataclass(frozen=True)
class ProjectReportEntry:
    """一条已核对的正式报告目录项；全部字段来自冻结记录原样。"""

    subject_id: str
    subject_code: str
    review_episode_id: str
    review_run_id: str
    workflow_stage_label: str
    center_code: str | None
    center_name: str | None
    completed_at: datetime
    official_protocol_version: str


@dataclass(frozen=True)
class ProjectReportPage:
    """项目报告目录只读页：不含总数或完成率等临床汇总推断。"""

    items: tuple[ProjectReportEntry, ...]
    next_cursor: tuple[datetime, str] | None


def list_project_reports(
    session: Session,
    *,
    project_id: str,
    center_code: str | None = None,
    before_completed_at: datetime | None = None,
    before_run_id: str | None = None,
    limit: int = 20,
) -> ProjectReportPage:
    """列出项目内正式已保存报告的只读目录页（不改状态、不发布、不重算）。"""
    if not 1 <= limit <= CATALOG_PAGE_LIMIT_MAX:
        raise ProjectReportQueryError(f"目录每页数量须在1至{CATALOG_PAGE_LIMIT_MAX}之间")
    if (before_completed_at is None) != (before_run_id is None):
        raise ProjectReportQueryError("报告分页信息不完整，请重新打开目录。")
    if before_run_id is not None and not before_run_id.strip():
        raise ProjectReportQueryError("报告分页信息不完整，请重新打开目录。")
    cursor_completed_at = None
    if before_completed_at is not None:
        offset = before_completed_at.utcoffset()
        if before_completed_at.tzinfo is None or offset is None or offset.total_seconds() != 0:
            raise ProjectReportQueryError("报告分页时间格式不正确，请重新打开目录。")
        # 时间列按 UTC naive 存储（app/storage/codecs.py 约定）；游标归一化后再绑定。
        cursor_completed_at = to_utc_naive(before_completed_at)

    # 项目必须真实存在；缺失经存储 NotFound 翻译为稳定中文 404。
    ProjectRepository(session).get(project_id)

    filters = [
        # 同节点项目关系：审核节点归属所选项目，与近期记录预览同一约束。
        ReviewEpisodeRecord.project_id == project_id,
        # V2 资料链（CHECK 保证 context_id 同非空）：排除 fixture/v1 / trial 投影。
        ReviewRunRecord.evidence_snapshot_v2_id.is_not(None),
        # 目录只列已完成保存的正式报告；未完成审核不属于已保存报告。
        ReviewRunRecord.completed_at.is_not(None),
    ]
    if cursor_completed_at is not None:
        filters.append(
            or_(
                ReviewRunRecord.completed_at < cursor_completed_at,
                and_(
                    ReviewRunRecord.completed_at == cursor_completed_at,
                    ReviewRunRecord.review_run_id < before_run_id,
                ),
            )
        )
    if center_code is not None:
        # 冻结上下文里的中心；payload_json 为 canonical JSON 文本列，沿既有
        # json_extract 用法（prepared_review_workflow 等），不做字符串拼 SQL。
        filters.append(
            or_(ReviewContextSnapshotRecord.context_id.is_(None), func.json_extract(
                ReviewContextSnapshotRecord.payload_json, "$.subject.center_code"
            )
            == center_code)
        )
    rows = (
        session.execute(
            select(
                ReviewRunRecord.review_run_id,
                ReviewRunRecord.review_episode_id,
                ReviewEpisodeRecord.subject_id,
            )
            .join(
                ReviewEpisodeRecord,
                ReviewEpisodeRecord.review_episode_id
                == ReviewRunRecord.review_episode_id,
            )
            .outerjoin(
                ReviewContextSnapshotRecord,
                ReviewContextSnapshotRecord.context_id == ReviewRunRecord.context_id,
            )
            .where(*filters)
            .order_by(
                ReviewRunRecord.completed_at.desc(),
                ReviewRunRecord.review_run_id.desc(),
            )
            .limit(limit + 1)
        )
        .all()
    )

    entries: list[ProjectReportEntry] = []
    for review_run_id, review_episode_id, subject_id in rows[:limit]:
        detail = get_run(session, subject_id, review_episode_id, review_run_id)
        if detail.context.authority.project_id != project_id:
            raise ReviewHistoryIncompleteError(
                "目录记录与所选研究项目不一致。", review_run_id=review_run_id
            )
        if center_code is not None and detail.context.subject.center_code != center_code:
            raise ReviewHistoryIncompleteError(
                "目录记录与所选中心不一致。", review_run_id=review_run_id
            )
        if detail.run.completed_at is None:
            raise ReviewHistoryIncompleteError(
                "目录记录不是已完成的正式报告。", review_run_id=review_run_id
            )
        entries.append(
            ProjectReportEntry(
                subject_id=detail.context.authority.subject_id,
                subject_code=detail.context.subject.subject_code,
                review_episode_id=detail.run.review_episode_id,
                review_run_id=detail.run.review_run_id,
                workflow_stage_label=_workflow_stage_label(
                    review_run_id=detail.run.review_run_id, context=detail.context
                ),
                center_code=detail.context.subject.center_code,
                center_name=detail.context.subject.center_name,
                completed_at=detail.run.completed_at,
                official_protocol_version=detail.context.protocol_document.official_version,
            )
        )
    next_cursor = None
    if len(rows) > limit:
        last = entries[-1]
        next_cursor = (last.completed_at, last.review_run_id)
    return ProjectReportPage(items=tuple(entries), next_cursor=next_cursor)
