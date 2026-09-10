"""Read identity migration preserves immutable linked history."""

import sqlite3

import pytest
from sqlalchemy import MetaData, UniqueConstraint
from sqlalchemy.orm import Session

from app.storage.db import Base, build_engine
from app.storage.migrate import MigrationFailure, MigrationManager
from app.storage.page_review_repository import PageReviewRepository
from app.storage.repositories import persist_fixture
from tests.v2.storage.test_migration_0019 import _seed_page_stack
from tests.v2.storage.test_page_review_repository import _coverage, _reconciliation, _review
from tests.v2.storage.test_repositories_roundtrip import FIXTURES


def _history(path):
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        return {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            for table in (
                "page_review_records", "page_reconciliations",
                "page_reconciliation_reviews", "subject_page_coverages",
                "subject_page_coverage_entries",
            )
        }


def test_upgrade_preserves_linked_history_and_refuses_lossy_downgrade(data_paths):
    historical = MetaData()
    for table in Base.metadata.tables.values():
        table.to_metadata(historical)
    historical.tables["page_review_records"].append_constraint(UniqueConstraint(
        "page_artifact_id", "clause_pack_sha256", "lane", "response_sha256",
        name="uq_prr_page_pack_lane_response",
    ))
    MigrationManager(data_paths, metadata=historical).upgrade("0020")
    manager = MigrationManager(data_paths)
    engine = build_engine(data_paths.db_path)
    try:
        with Session(engine) as session, session.begin():
            fixture = FIXTURES[0]
            persist_fixture(session, fixture)
            _seed_page_stack(session, fixture)
            repo = PageReviewRepository(session)
            repo.save_review(_review("main-A"))
            repo.save_review(_review("main-B"))
            repo.save_reconciliation(_reconciliation())
            repo.save_coverage(_coverage(fixture))
    finally:
        engine.dispose()
    before = _history(data_paths.db_path)
    manager.upgrade("0021")
    assert _history(data_paths.db_path) == before
    engine = build_engine(data_paths.db_path)
    try:
        with Session(engine) as session, session.begin():
            PageReviewRepository(session).save_review(_review("main-A").model_copy(update={
                "page_review_id": "new-prompt-read", "prompt_version": "new-version",
            }))
    finally:
        engine.dispose()
    expanded = _history(data_paths.db_path)
    with pytest.raises(MigrationFailure, match="0021"):
        manager.downgrade("0020")
    assert manager.read_revision(data_paths.db_path) == "0021"
    assert _history(data_paths.db_path) == expanded
