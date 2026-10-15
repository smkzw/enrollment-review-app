"""项目作用域的正式审核待办只读清单。

从已存储的 ``review/v2`` ``ActionRequest`` 读取候选，再按审核运行调用
:func:`app.services.review_history_service.get_run` 核对冻结运行、上下文、门禁与
待办闭包。不读 trial/fixture 投影，不新建状态机，不发布、不重算临床结论。

分页按稳定 ``action_id`` 升序 keyset（``after_action_id`` + ``limit``），候选查询
固定 ``limit+1``；同页按运行去重后每个运行只调用一次 ``get_run``。历史未办结
待办不会因“只取最新运行”而静默消失；任一可见记录与冻结源不一致则大声失败。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.enums import ActionState, ReviewStage
from app.services.review_history_service import (
    ReviewHistoryAction,
    ReviewHistoryIncompleteError,
    ReviewHistoryRunDetail,
    get_run,
)
from app.storage.models import ActionRequestRecord
from app.storage.repositories import ProjectRepository

__all__ = [
    "ReviewActionWorklistItem",
    "ReviewActionWorklistMode",
    "ReviewActionWorklistPage",
    "list_review_action_worklist",
]

ReviewActionWorklistMode = Literal["open", "all"]

_OPEN_STATES = frozenset({ActionState.OPEN, ActionState.REOPENED})
_OPEN_STATE_VALUES = frozenset(state.value for state in _OPEN_STATES)


@dataclass(frozen=True)
class ReviewActionWorklistItem:
    """一条已核对待办 + 链接原报告所需的冻结运行/上下文元数据。"""

    action: ReviewHistoryAction
    project_name: str
    subject_id: str
    subject_code: str
    review_episode_id: str
    review_run_id: str
    workflow_stage_label: str
    started_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True)
class ReviewActionWorklistPage:
    """项目待办只读页：不含全局总数或临床完成度推断。"""

    project_id: str
    mode: ReviewActionWorklistMode
    items: tuple[ReviewActionWorklistItem, ...]
    next_after_action_id: str | None


def _workflow_stage_label(*, review_run_id: str, context) -> str:
    workflow_stage_id = context.review_episode.workflow_stage_id
    try:
        return next(
            stage.display_name
            for stage in context.workflow_stages
            if stage.workflow_stage_id == workflow_stage_id
        )
    except StopIteration as exc:
        raise ReviewHistoryIncompleteError(
            "本次审核缺少可用的工作阶段名称，暂不能展示办理清单。",
            review_run_id=review_run_id,
        ) from exc


def list_review_action_worklist(
    session: Session,
    *,
    project_id: str,
    mode: ReviewActionWorklistMode = "open",
    limit: int = 50,
    after_action_id: str | None = None,
    due_stage: ReviewStage | None = None,
) -> ReviewActionWorklistPage:
    """列出项目内已冻结正式审核待办（只读；不改状态、不发布）。"""
    if mode not in ("open", "all"):
        raise ValueError("mode 仅支持 open 或 all")
    if not 1 <= limit <= 100:
        raise ValueError("limit 必须在 1–100 之间")
    if due_stage is not None:
        due_stage = ReviewStage(due_stage)

    # 项目必须真实存在；缺失经存储 NotFound 翻译为稳定中文 404。
    ProjectRepository(session).get(project_id)

    filters = [
        ActionRequestRecord.project_id == project_id,
        # V2 资料链：排除 fixture/v1 / trial 投影候选。
        ActionRequestRecord.evidence_snapshot_v2_id.is_not(None),
    ]
    if mode == "open":
        filters.append(ActionRequestRecord.state.in_(sorted(_OPEN_STATE_VALUES)))
    if due_stage is not None:
        filters.append(ActionRequestRecord.due_stage == due_stage.value)
    if after_action_id is not None:
        filters.append(ActionRequestRecord.action_id > after_action_id)

    records = (
        session.execute(
            select(ActionRequestRecord)
            .where(*filters)
            .order_by(ActionRequestRecord.action_id.asc())
            .limit(limit + 1)
        )
        .scalars()
        .all()
    )
    page_records = list(records[:limit])
    next_after_action_id = page_records[-1].action_id if len(records) > limit else None

    # 同页按运行去重；每个运行恰好调用一次 get_run，避免只取最新运行。
    details_by_run: dict[tuple[str, str, str], ReviewHistoryRunDetail] = {}
    for record in page_records:
        run_key = (record.subject_id, record.review_episode_id, record.review_run_id)
        if run_key in details_by_run:
            continue
        details_by_run[run_key] = get_run(
            session,
            record.subject_id,
            record.review_episode_id,
            record.review_run_id,
        )

    items: list[ReviewActionWorklistItem] = []
    for record in page_records:
        run_key = (record.subject_id, record.review_episode_id, record.review_run_id)
        detail = details_by_run[run_key]
        action_view = next(
            (
                item
                for item in detail.actions
                if item.action.action_id == record.action_id
            ),
            None,
        )
        if action_view is None:
            raise ReviewHistoryIncompleteError(
                "办理清单中的待办与冻结审核记录不一致，拒绝展示。",
                review_run_id=record.review_run_id,
            )
        if mode == "open" and action_view.action.state not in _OPEN_STATES:
            raise ReviewHistoryIncompleteError(
                "待办办理状态与冻结记录不一致，拒绝展示。",
                review_run_id=record.review_run_id,
            )
        if due_stage is not None and action_view.action.due_stage != due_stage:
            raise ReviewHistoryIncompleteError(
                "待办完成阶段与保存记录不一致，暂不能展示。",
                review_run_id=record.review_run_id,
            )
        if (
            action_view.action.project_id != project_id
            or detail.context.authority.project_id != project_id
            or detail.run.review_run_id != record.review_run_id
            or detail.context.authority.review_episode_id != record.review_episode_id
            or detail.context.authority.subject_id != record.subject_id
        ):
            raise ReviewHistoryIncompleteError(
                "待办与本次审核、审核节点或项目范围不一致，拒绝展示。",
                review_run_id=record.review_run_id,
            )
        items.append(
            ReviewActionWorklistItem(
                action=action_view,
                project_name=detail.context.project_name,
                subject_id=detail.context.authority.subject_id,
                subject_code=detail.context.subject.subject_code,
                review_episode_id=detail.context.authority.review_episode_id,
                review_run_id=detail.run.review_run_id,
                workflow_stage_label=_workflow_stage_label(
                    review_run_id=detail.run.review_run_id,
                    context=detail.context,
                ),
                started_at=detail.run.started_at,
                completed_at=detail.run.completed_at,
            )
        )

    return ReviewActionWorklistPage(
        project_id=project_id,
        mode=mode,
        items=tuple(items),
        next_after_action_id=next_after_action_id,
    )
