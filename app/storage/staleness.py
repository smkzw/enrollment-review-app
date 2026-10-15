"""实体 stale 状态仓储。

上游变化（文档、事实、规则或锚点变化）后，受影响且尚未完成新 ReviewRun 的
实体进入结构化 stale 记录；只有当覆盖范围内的新 ReviewRun 完成后，才关闭
被该运行覆盖的 stale 项。stale 是持久业务状态，不由前端自行推测。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sqlalchemy.orm import Session

from app.storage.codecs import utc_now
from app.storage.models import EntityStalenessRow


@dataclass(frozen=True)
class StalenessRecord:
    id: int
    target_type: str
    target_id: str
    reason: str
    source_entity_type: str
    source_entity_id: str
    source_revision: int
    opened_at: datetime
    cleared_by_review_run_id: str | None
    cleared_at: datetime | None

    @property
    def open(self) -> bool:
        return self.cleared_at is None


def _to_record(row: EntityStalenessRow) -> StalenessRecord:
    return StalenessRecord(
        id=row.id,
        target_type=row.target_type,
        target_id=row.target_id,
        reason=row.reason,
        source_entity_type=row.source_entity_type,
        source_entity_id=row.source_entity_id,
        source_revision=row.source_revision,
        opened_at=row.opened_at,
        cleared_by_review_run_id=row.cleared_by_review_run_id,
        cleared_at=row.cleared_at,
    )


class StalenessRepository:
    """打开/查询/按 ReviewRun 覆盖范围精确关闭 stale 记录。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def open(
        self,
        *,
        target_type: str,
        target_id: str,
        reason: str,
        source_entity_type: str,
        source_entity_id: str,
        source_revision: int,
    ) -> StalenessRecord:
        """打开一条 stale 记录；同一来源 revision+原因的重复打开幂等返回既有记录。"""
        row = (
            self.session.query(EntityStalenessRow)
            .filter(
                EntityStalenessRow.target_type == target_type,
                EntityStalenessRow.target_id == target_id,
                EntityStalenessRow.reason == reason,
                EntityStalenessRow.source_entity_type == source_entity_type,
                EntityStalenessRow.source_entity_id == source_entity_id,
                EntityStalenessRow.source_revision == source_revision,
            )
            .one_or_none()
        )
        if row is not None:
            return _to_record(row)
        row = EntityStalenessRow(
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            source_revision=source_revision,
            opened_at=utc_now(),
        )
        self.session.add(row)
        self.session.flush()
        return _to_record(row)

    def open_many(self, items: Iterable[dict]) -> list[StalenessRecord]:
        return [self.open(**item) for item in items]

    def list_open(
        self,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        source_entity_type: str | None = None,
        source_entity_id: str | None = None,
    ) -> list[StalenessRecord]:
        """查询未关闭的 stale 项（可按目标或来源过滤）。"""
        query = self.session.query(EntityStalenessRow).filter(
            EntityStalenessRow.cleared_at.is_(None)
        )
        if target_type is not None:
            query = query.filter(EntityStalenessRow.target_type == target_type)
        if target_id is not None:
            query = query.filter(EntityStalenessRow.target_id == target_id)
        if source_entity_type is not None:
            query = query.filter(EntityStalenessRow.source_entity_type == source_entity_type)
        if source_entity_id is not None:
            query = query.filter(EntityStalenessRow.source_entity_id == source_entity_id)
        return [_to_record(row) for row in query.order_by(EntityStalenessRow.id).all()]

    def close_covered(
        self,
        *,
        review_run_id: str,
        covered: Iterable[tuple[str, str]],
    ) -> int:
        """关闭被新 ReviewRun 覆盖范围内的未关闭 stale 项；范围外保持打开。

        ``covered`` 为 ``(target_type, target_id)`` 集合；只有目标精确落在
        集合内的记录被标记 ``cleared_by_review_run_id``。返回关闭数量。
        """
        pairs = {(target_type, target_id) for target_type, target_id in covered}
        if not pairs:
            return 0
        rows = (
            self.session.query(EntityStalenessRow)
            .filter(EntityStalenessRow.cleared_at.is_(None))
            .all()
        )
        closed = 0
        now = utc_now()
        for row in rows:
            if (row.target_type, row.target_id) in pairs:
                row.cleared_by_review_run_id = review_run_id
                row.cleared_at = now
                closed += 1
        if closed:
            self.session.flush()
        return closed
