"""Working items use the existing append-only storage and its integrity codec."""
from sqlalchemy import select

from app.domain.contracts.work_draft import WorkDraftItem
from app.storage.models import WorkDraftItemRecord
from app.storage.repositories import AppendRepository, REVIEW_RUN_CONFIG, ScopeViolationError, _config


_ITEM_CONFIG = _config(WorkDraftItemRecord, WorkDraftItem,
    {"item_id": "item_id", "review_run_id": "review_run_id", "official_code": "official_code",
     "rule_component_id": "rule_component_id", "input_hash": "input_hash"},
    mirrors={"review_run_id": "review_run_id", "official_code": "official_code",
             "rule_component_id": "rule_component_id", "input_hash": "input_hash"})


class WorkDraftRepository:
    def __init__(self, session):
        self.session = session
        self.items = AppendRepository(session, _ITEM_CONFIG)

    def save(self, item):
        run = AppendRepository(self.session, REVIEW_RUN_CONFIG).get(item.review_run_id)
        if run.run_kind != "work_draft":
            raise ScopeViolationError("工作稿条目不能写入正式签发记录")
        existing = self.items.get_or_none(item.item_id)
        if existing is not None:
            if existing != item:
                raise ScopeViolationError("旧工作稿条目不可覆盖")
            return existing
        return self.items.save(item)

    def list_for_run(self, review_run_id):
        ids = self.session.scalars(select(WorkDraftItemRecord.item_id).where(
            WorkDraftItemRecord.review_run_id == review_run_id).order_by(WorkDraftItemRecord.item_id)).all()
        return [self.items.get(key) for key in ids]
