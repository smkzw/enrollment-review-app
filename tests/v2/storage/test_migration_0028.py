import pytest
from sqlalchemy import inspect
from app.storage.migrate import MigrationManager, MigrationFailure
from app.storage.db import build_engine
from tests.v2.protocols.slice4_helpers import confirmed_fixture
from tests.v2.protocols.test_rule_reviews import approve_draft


def test_review_table_is_present_and_empty_downgrade_is_lossless(data_paths):
    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    engine = build_engine(data_paths.db_path)
    assert "rule_review_records" in inspect(engine).get_table_names()
    engine.dispose()
    manager.downgrade("0027")
    engine = build_engine(data_paths.db_path)
    assert "rule_review_records" not in inspect(engine).get_table_names()
    engine.dispose()


def test_review_history_prevents_destructive_downgrade(data_paths, session_factory, migrated_engine):
    source, draft, _ = confirmed_fixture()
    approve_draft(session_factory, source, draft)
    migrated_engine.dispose()
    with pytest.raises(MigrationFailure):
        MigrationManager(data_paths).downgrade("0027")
