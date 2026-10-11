"""0.2.0：逐条审定、局部失效、验证发布及历史边界。"""
from copy import deepcopy

import pytest
from sqlalchemy import func, select

from app.domain.contracts.rule_reviews import RuleReviewRecord
from app.protocols.deconstruction_gate import ProtocolDeconstructionGate, publication_issue_level
from app.services.protocol_publication_service import (
    ProtocolPublicationError, ProtocolPublicationRequest, ProtocolPublicationService,
)
from app.services.protocol_rule_review import REVIEW_CONFIG, current_reviews, review_entries
from app.storage.models import ProjectRecord, RuleReviewRecordRow
from app.storage.repositories import AppendRepository, get_rule_set
from tests.v2.protocols.slice4_helpers import NOW, confirmed_fixture
from tests.v2.protocols.test_publication_service import _save_revision


def approve_draft(factory, source, draft, *, kind="builder_verification"):
    with factory() as session, session.begin():
        repository = AppendRepository(session, REVIEW_CONFIG)
        for entry in review_entries(source, draft):
            record = RuleReviewRecord(
                record_id=f"review:{entry['official_code']}:{entry['rule_content_hash']}",
                draft_id=draft.draft_id, protocol_version_id=draft.protocol_version_id,
                official_code=entry["official_code"], rule_content_hash=entry["rule_content_hash"],
                reviewer_kind=kind, reviewed_by="测试审定人", reviewed_at=NOW, action="approved",
                note="excluded" if entry["kind"] == "procedure" else None,
                result_variables=["eos"] if entry["kind"] == "procedure" else [],
            )
            repository.save(record)


def test_unreviewed_draft_cannot_publish_and_writes_no_formal_chain(slice4_env):
    factory, _ = slice4_env
    source, draft, spans = confirmed_fixture()
    revision = _save_revision(factory, draft)
    with pytest.raises(ProtocolPublicationError, match="尚未审定") as error:
        ProtocolPublicationService(factory).publish(ProtocolPublicationRequest(
            idempotency_key="unreviewed", draft_revision_id=revision.revision_id,
            source_input=source, source_spans=spans, actor="测试", published_at=NOW,
        ))
    assert error.value.code == "rule_reviews_incomplete"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ProjectRecord)) == 0


@pytest.mark.parametrize("kind, verification_only", [("builder_verification", True), ("medical_manager", False)])
def test_review_records_survive_publication_and_idempotent_replay(slice4_env, kind, verification_only):
    factory, _ = slice4_env
    source, draft, spans = confirmed_fixture()
    if kind == "medical_manager":
        from tests.v2.protocols.test_variable_binding import fixture_bindings
        from app.services.protocol_variable_binding import apply_variable_bindings
        draft = apply_variable_bindings(draft, fixture_bindings(draft))
    revision = _save_revision(factory, draft)
    approve_draft(factory, source, draft, kind=kind)
    request = ProtocolPublicationRequest(idempotency_key="reviewed", draft_revision_id=revision.revision_id,
        source_input=source, source_spans=spans, actor="测试", published_at=NOW)
    service = ProtocolPublicationService(factory)
    result = service.publish(request)
    assert result.verification_only is verification_only
    replay = service.publish(request)
    assert replay.replay and replay.verification_only is verification_only
    with factory() as session:
        stored = get_rule_set(session, result.rule_set_id, result.rule_set_revision)
        assert stored.verification_only is verification_only
        assert len(stored.review_records) == len(review_entries(source, draft))
        procedure = next(record for record in stored.review_records if record.note == "excluded")
        assert procedure.result_variables == ["eos"]


def test_changed_entry_invalidates_only_it_and_changed_source_invalidates_it(slice4_env):
    factory, _ = slice4_env
    source, draft, _ = confirmed_fixture()
    approve_draft(factory, source, draft)
    changed = draft.model_copy(deep=True)
    changed.proposed_rules[0].source_text += "（补充说明）"
    with factory() as session:
        entries, history = current_reviews(session, source, changed)
        assert entries[0]["review"] is None
        assert all(entry["review"] is not None for entry in entries[1:])
        assert len(history) == len(entries)
        changed_source = source.model_copy(deep=True)
        target_ref = entries[0]["source_refs"][0]
        next(item for item in changed_source.source_materials if item.source_span_id == target_ref).text += "新原文"
        rechecked, _ = current_reviews(session, changed_source, draft)
        assert rechecked[0]["review"] is None
        assert rechecked[1]["review"] is not None


def test_revocation_wins_at_same_timestamp_without_rewriting_history(slice4_env):
    factory, _ = slice4_env
    source, draft, _ = confirmed_fixture()
    approve_draft(factory, source, draft)
    with factory() as session, session.begin():
        entries, history = current_reviews(session, source, draft)
        original = history[0]
        before = original.model_dump_json()
        AppendRepository(session, REVIEW_CONFIG).save(original.model_copy(update={
            "record_id": "revoke", "action": "revoked",
        }))
        entries, after = current_reviews(session, source, draft)
        assert entries[0]["review"] is None
        assert after[0].model_dump_json() == before
        assert len(after) == len(history) + 1


def test_procedure_denominator_is_frozen_catalog_not_mapping():
    source, draft, _ = confirmed_fixture()
    draft.procedure_catalog_mappings = []
    entries = review_entries(source, draft)
    assert {item["official_code"] for item in entries if item["kind"] == "procedure"} == {
        item.item_id for item in source.required_procedure_catalog.items
    }


def test_gate_reminders_do_not_block_but_structural_identity_still_does():
    source, draft, spans = confirmed_fixture()
    draft.procedure_catalog_mappings = []
    result = ProtocolDeconstructionGate().evaluate(source, draft, source_spans=spans)
    assert result.publishable
    issue = next(issue for check in result.checks for issue in check.issues
                 if issue.issue_code == "PROCEDURE_CATALOG_NOT_EXACTLY_COVERED")
    assert publication_issue_level(issue) == "提醒"
    draft.protocol_version_id = "wrong-version"
    result = ProtocolDeconstructionGate().evaluate(source, draft, source_spans=spans)
    assert not result.publishable


def test_old_rule_set_payload_hash_is_not_changed_by_new_optional_fields():
    from app.domain.publication import canonical_hash
    from tests.v2.storage.test_repositories_roundtrip import FIXTURES
    original = deepcopy(FIXTURES[0].rule_set.model_dump(mode="json"))
    assert "review_records" not in original and "verification_only" not in original
    loaded = FIXTURES[0].rule_set.model_validate(original)
    assert canonical_hash(loaded.model_dump(mode="json")) == canonical_hash(original)
