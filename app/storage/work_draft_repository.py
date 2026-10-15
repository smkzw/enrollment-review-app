"""Working items use the existing append-only storage and its integrity codec."""
from sqlalchemy import select

from app.domain.contracts.work_draft import WorkDraftItem, WorkDraftAcknowledgement, acknowledgement_input_hash
from app.storage.models import WorkDraftItemRecord, WorkDraftAcknowledgementRecord
from app.storage.repositories import AppendRepository, REVIEW_RUN_CONFIG, ScopeViolationError, _config


_ITEM_CONFIG = _config(WorkDraftItemRecord, WorkDraftItem,
    {"item_id": "item_id", "review_run_id": "review_run_id", "official_code": "official_code",
     "rule_component_id": "rule_component_id", "input_hash": "input_hash"},
    mirrors={"review_run_id": "review_run_id", "official_code": "official_code",
             "rule_component_id": "rule_component_id", "input_hash": "input_hash"})

_ACK_CONFIG = _config(WorkDraftAcknowledgementRecord, WorkDraftAcknowledgement,
    {key: key for key in ("acknowledgement_id", "review_episode_id", "official_code", "input_hash")},
    mirrors={key: key for key in ("review_episode_id", "official_code", "input_hash")})


class WorkDraftRepository:
    def __init__(self, session):
        self.session = session
        self.items = AppendRepository(session, _ITEM_CONFIG)
        self.acknowledgements = AppendRepository(session, _ACK_CONFIG)

    def save(self, item):
        run = AppendRepository(self.session, REVIEW_RUN_CONFIG).get(item.review_run_id)
        if run.run_kind != "work_draft":
            raise ScopeViolationError("工作稿条目不能写入正式签发记录")
        if item.acknowledgement_id is not None:
            from app.storage.review_context_repository import ReviewContextV2Repository
            record = self.acknowledgements.get(item.acknowledgement_id)
            frozen = ReviewContextV2Repository(self.session).get(run.context_id)
            if (record.review_episode_id != run.review_episode_id or record.actor_kind != item.confirmation_kind
                    or record.official_code != item.official_code
                    or record.input_hash != acknowledgement_input_hash(item, frozen.evaluator_version)):
                raise ScopeViolationError("核实记录与本条当前依据不一致")
        existing = self.items.get_or_none(item.item_id)
        if existing is not None:
            if existing != item:
                raise ScopeViolationError("旧工作稿条目不可覆盖")
            return existing
        return self.items.save(item)

    def list_acknowledgements(self, review_episode_id):
        ids = self.session.scalars(select(WorkDraftAcknowledgementRecord.acknowledgement_id).where(
            WorkDraftAcknowledgementRecord.review_episode_id == review_episode_id)
            .order_by(WorkDraftAcknowledgementRecord.created_at)).all()
        return [self.acknowledgements.get(key) for key in ids]

    def list_for_run(self, review_run_id):
        ids = self.session.scalars(select(WorkDraftItemRecord.item_id).where(
            WorkDraftItemRecord.review_run_id == review_run_id).order_by(WorkDraftItemRecord.item_id)).all()
        return [self.items.get(key) for key in ids]
