"""0020 页级判读持久化迁移与不可变历史保护。"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect

from app.storage.db import build_engine
from app.storage.migrate import MigrationFailure, MigrationManager, resolve_head_revision
from app.storage.page_review_repository import PageReviewRepository
from app.storage.repositories import persist_fixture
from tests.v2.storage.test_migration_0008 import PHASE5_V2_TABLES
from tests.v2.storage.test_migration_0019 import _seed_page_stack
from tests.v2.storage.test_page_review_repository import _review
from tests.v2.storage.test_repositories_roundtrip import FIXTURES


TABLES = {
    "page_review_records",
    "page_reconciliations",
    "page_reconciliation_reviews",
    "subject_page_coverages",
    "subject_page_coverage_entries",
}


def test_0020_schema_and_empty_downgrade(data_paths) -> None:
    assert TABLES <= PHASE5_V2_TABLES
    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    assert manager.read_revision(data_paths.db_path) == resolve_head_revision()

    engine = build_engine(data_paths.db_path)
    try:
        inspector = inspect(engine)
        assert TABLES <= set(inspector.get_table_names())
        reviews = {fk["referred_table"] for fk in inspector.get_foreign_keys("page_reconciliation_reviews")}
        assert reviews == {"page_reconciliations", "page_review_records"}
        coverage = {fk["referred_table"] for fk in inspector.get_foreign_keys("subject_page_coverages")}
        assert {"subjects", "review_episodes", "evidence_snapshots_v2", "evidence_processing_revisions"} <= coverage
    finally:
        engine.dispose()

    manager.downgrade("0019")
    engine = build_engine(data_paths.db_path)
    try:
        assert not (TABLES & set(inspect(engine).get_table_names()))
    finally:
        engine.dispose()


def test_0020_refuses_downgrade_with_immutable_history(
    data_paths, session_factory, migrated_engine
) -> None:
    with session_factory() as session, session.begin():
        fixture = FIXTURES[0]
        persist_fixture(session, fixture)
        _seed_page_stack(session, fixture)
        PageReviewRepository(session).save_review(_review("main-A"))

    migrated_engine.dispose()
    with pytest.raises(MigrationFailure, match="0020"):
        MigrationManager(data_paths).downgrade("0019")
