"""0022 判断检索覆盖摘要持久化迁移与不可变历史保护。

沿用 0018/0019/0020 的既有约定：
- 新表必须登记进 ``PHASE5_V2_TABLES``，避免污染 0007-0012 历史 metadata 快照；
- 空 history 允许降级，非空 history 拒绝有损降级。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect

from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.judgment_search import (
    JudgmentSearchCoverageStatus,
    JudgmentSearchCoverageSummary,
)
from app.storage.db import build_engine
from app.storage.judgment_search_repository import JudgmentSearchSummaryRepository
from app.storage.migrate import MigrationFailure, MigrationManager, resolve_head_revision
from app.storage.repositories import persist_fixture
from tests.v2.storage.test_migration_0008 import PHASE5_V2_TABLES
from tests.v2.storage.test_migration_0019 import _seed_page_stack
from tests.v2.storage.test_repositories_roundtrip import FIXTURES

MIGRATION_0022_TABLES = {"judgment_search_summaries"}


def test_0022_tables_are_registered_for_historical_metadata_snapshots() -> None:
    """后续 Phase 5 表不得污染 0007-0012 的历史 metadata 校验。"""
    assert MIGRATION_0022_TABLES <= PHASE5_V2_TABLES


def test_0022_adds_summary_table_and_empty_downgrade(data_paths) -> None:
    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    assert manager.read_revision(data_paths.db_path) == resolve_head_revision()

    engine = build_engine(data_paths.db_path)
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert MIGRATION_0022_TABLES <= set(tables)
        cols = {c["name"] for c in inspector.get_columns("judgment_search_summaries")}
        assert {
            "summary_id",
            "subject_id",
            "review_episode_id",
            "evidence_snapshot_id",
            "evidence_processing_revision_id",
            "rule_set_id",
            "rule_set_revision",
            "scope_sha256",
            "requirement_id",
            "status",
            "found_candidate_count",
            "job_id",
            "payload_json",
            "payload_sha256",
            "created_at",
        } <= cols
        indexes = {
            idx["name"] for idx in inspector.get_indexes("judgment_search_summaries")
        }
        assert "ix_jss_authority_requirement" in indexes
    finally:
        engine.dispose()

    manager.downgrade("0021")
    engine = build_engine(data_paths.db_path)
    try:
        assert not (MIGRATION_0022_TABLES & set(inspect(engine).get_table_names()))
    finally:
        engine.dispose()


def _authority(fixture) -> FactAuthority:
    return FactAuthority(
        project_id=fixture.project.project_id,
        subject_id=fixture.subject.subject_id,
        review_episode_id=fixture.review_episode.review_episode_id,
        episode_revision=1,
        protocol_version_id=fixture.project.protocol_version.protocol_version_id
        if hasattr(fixture.project, "protocol_version") else "protocol-1",
        rule_set_id=fixture.rule_set.rule_set_id,
        rule_set_revision=fixture.rule_set.revision,
        evidence_snapshot_v2_id="snap-1",
        complete_processing_revision_id="rev-1",
    )


def _summary(requirement_id: str, status: JudgmentSearchCoverageStatus,
             scope_sha256: str) -> JudgmentSearchCoverageSummary:
    return JudgmentSearchCoverageSummary(
        scope_sha256=scope_sha256,
        requirement_id=requirement_id,
        status=status,
    )


def test_0022_refuses_downgrade_with_immutable_history(
    data_paths, session_factory, migrated_engine
) -> None:
    with session_factory() as session, session.begin():
        fixture = FIXTURES[0]
        persist_fixture(session, fixture)
        _seed_page_stack(session, fixture)
        JudgmentSearchSummaryRepository(session).save_summary(
            _summary(
                "requirement-judgment-1",
                JudgmentSearchCoverageStatus.ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE,
                "b" * 64,
            ),
            authority=_authority(fixture),
            job_id="job-0022",
            created_at=datetime(2026, 9, 11, 8, 0, 0, tzinfo=UTC),
        )

    migrated_engine.dispose()
    with pytest.raises(MigrationFailure, match="0022"):
        MigrationManager(data_paths).downgrade("0021")
