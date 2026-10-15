import pytest
from sqlalchemy import inspect
from app.storage.db import build_engine
from app.storage.migrate import MigrationManager, MigrationFailure
from app.storage.models import RuleSetVariablesRecord
from tests.v2.protocols.slice4_helpers import confirmed_fixture
from tests.v2.protocols.test_publication_service import _save_revision
from tests.v2.protocols.test_variable_binding import fixture_bindings
from tests.v2.protocols.test_rule_reviews import approve_draft
from app.services.protocol_variable_binding import apply_variable_bindings
from app.services.protocol_publication_service import ProtocolPublicationService, ProtocolPublicationRequest


def test_empty_dictionary_projection_downgrade_is_lossless(data_paths):
    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    engine = build_engine(data_paths.db_path)
    assert "rule_set_variables" in inspect(engine).get_table_names()
    engine.dispose()
    manager.downgrade("0028")
    engine = build_engine(data_paths.db_path)
    assert "rule_set_variables" not in inspect(engine).get_table_names()
    engine.dispose()


def test_published_dictionary_prevents_destructive_downgrade(data_paths, migrated_engine, session_factory):
    source, draft, spans = confirmed_fixture()
    draft = apply_variable_bindings(draft, fixture_bindings(draft))
    revision = _save_revision(session_factory, draft)
    approve_draft(session_factory, source, draft)
    result = ProtocolPublicationService(session_factory).publish(ProtocolPublicationRequest(
        idempotency_key="dictionary", draft_revision_id=revision.revision_id,
        source_input=source, source_spans=spans, actor="测试"))
    with session_factory() as session:
        assert session.get(RuleSetVariablesRecord, (result.rule_set_id, result.rule_set_revision)) is not None
    migrated_engine.dispose()
    with pytest.raises(MigrationFailure):
        MigrationManager(data_paths).downgrade("0028")
