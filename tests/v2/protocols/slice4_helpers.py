"""切片 4 共享夹具：已确认身份的 Gate 测试草稿。"""
from __future__ import annotations

from datetime import datetime, timezone

from app.domain.contracts.enums import MetadataResolutionStatus

from tests.v2.protocols.test_deconstruction_gate_slice3 import _fixture

NOW = datetime(2026, 8, 17, tzinfo=timezone.utc)
SHA = "a" * 64


def confirmed_fixture():
    """Gate 测试草稿 + 已确认身份/期别；返回 (source_input, draft, source_spans)。"""
    source_input, draft, source_spans = _fixture()
    source_input.identity_decision = source_input.identity_decision.model_copy(
        update={"status": MetadataResolutionStatus.CONFIRMED}
    )
    source_input.phase_selection = source_input.phase_selection.model_copy(
        update={"status": MetadataResolutionStatus.CONFIRMED}
    )
    return source_input, draft, source_spans


def approve_fixture_entries(factory, source, draft):
    """为合成发布夹具明确写入验证审定，不改变产品发布条件。"""
    from sqlalchemy import select
    from app.domain.contracts.rule_reviews import RuleReviewRecord
    from app.services.protocol_rule_review import REVIEW_CONFIG, review_entries
    from app.storage.models import RuleReviewRecordRow
    from app.storage.repositories import AppendRepository

    with factory() as session, session.begin():
        for entry in review_entries(source, draft):
            record_id = f"fixture-review:{draft.draft_id}:{entry['official_code']}:{entry['rule_content_hash']}"
            if session.scalar(select(RuleReviewRecordRow.sequence).where(RuleReviewRecordRow.record_id == record_id)):
                continue
            AppendRepository(session, REVIEW_CONFIG).save(RuleReviewRecord(
                record_id=record_id, draft_id=draft.draft_id, protocol_version_id=draft.protocol_version_id,
                official_code=entry["official_code"], rule_content_hash=entry["rule_content_hash"],
                reviewer_kind="builder_verification", reviewed_by="构建者（验证）", reviewed_at=NOW,
                action="approved",
            ))
