"""Persist V2 input snapshots in the existing context table, not a new review chain."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.contracts.review_context_v2 import ReviewContextSnapshotV2
from app.domain.publication import canonical_hash
from app.storage.models import ReviewContextSnapshotRecord
from app.storage.repositories import AppendRepository, DuplicateRecordError, _config


_CONTEXT_V2_CONFIG = _config(
    ReviewContextSnapshotRecord,
    ReviewContextSnapshotV2,
    {"context_id": "context_id", "review_episode_id": "authority.review_episode_id"},
    mirrors={"review_episode_id": "authority.review_episode_id"},
    created_at_key="created_at",
)


class ReviewContextV2Repository:
    """Immutable input storage; the publication service must verify source receipts."""

    def __init__(self, session: Session) -> None:
        self._repository = AppendRepository(session, _CONTEXT_V2_CONFIG)

    def get(self, context_id: str) -> ReviewContextSnapshotV2:
        return self._repository.get(context_id)

    def save(self, context: ReviewContextSnapshotV2) -> ReviewContextSnapshotV2:
        validated = ReviewContextSnapshotV2.model_validate(context.model_dump(mode="json"))
        existing = self._repository.get_or_none(validated.context_id)
        if existing is not None:
            if canonical_hash(existing.model_dump(mode="json")) != canonical_hash(validated.model_dump(mode="json")):
                raise DuplicateRecordError("同一审核上下文身份不能替换为不同资料")
            return existing
        self._repository.save(validated)
        return validated
