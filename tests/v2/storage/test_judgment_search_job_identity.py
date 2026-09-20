"""Repeated searches keep task-specific immutable results, even when text agrees."""
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import select, update

from app.domain.contracts.judgment_search import JudgmentSearchCoverageStatus, JudgmentSearchLane
from app.storage.judgment_search_models import JudgmentSearchSummaryORM
from app.storage.judgment_search_repository import JudgmentSearchSummaryRepository
from app.storage.repositories import persist_fixture
from app.domain.publication import canonical_hash
from tests.v2.storage.test_migration_0019 import _seed_page_stack
from tests.v2.storage.test_migration_0022 import _authority, _summary
from tests.v2.storage.test_repositories_roundtrip import FIXTURES


def test_invalid_copied_summary_is_rejected_before_persistence(session_factory):
    with session_factory() as session, session.begin():
        fixture = FIXTURES[0]
        persist_fixture(session, fixture)
        _seed_page_stack(session, fixture)
        summary = _summary(
            "judgment-required",
            JudgmentSearchCoverageStatus.ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE,
            "b" * 64,
        ).model_copy(update={"missing_lanes": (JudgmentSearchLane.MAIN_B,)})
        with pytest.raises(ValidationError, match="未见候选.*不一致"):
            JudgmentSearchSummaryRepository(session).save_summary(
                summary, authority=_authority(fixture), job_id="invalid-copy",
                created_at=datetime(2026, 9, 13, tzinfo=UTC),
            )
        assert session.scalars(select(JudgmentSearchSummaryORM)).all() == []


def test_identical_results_are_bound_to_each_search_job(session_factory):
    with session_factory() as session, session.begin():
        fixture = FIXTURES[0]
        persist_fixture(session, fixture)
        _seed_page_stack(session, fixture)
        authority = _authority(fixture)
        repository = JudgmentSearchSummaryRepository(session)
        summary = _summary(
            "judgment-required", JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE,
            "b" * 64,
        )
        for job_id in ("search-first", "search-second", "search-second"):
            repository.save_summary(
                summary, authority=authority, job_id=job_id,
                created_at=datetime(2026, 9, 13, tzinfo=UTC),
            )
        rows = session.scalars(select(JudgmentSearchSummaryORM)).all()
        assert {row.job_id for row in rows} == {"search-first", "search-second"}
        assert len(rows) == 2
        for job_id in ("search-first", "search-second"):
            assert repository.latest_for_authority(authority, job_id=job_id) == {
                summary.requirement_id: summary,
            }
        assert repository.latest_for_authority(authority, job_id="not-finished") == {}
        later = _summary(
            summary.requirement_id,
            JudgmentSearchCoverageStatus.ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE,
            "b" * 64,
        )
        repository.save_summary(
            later, authority=authority, job_id="search-third",
            created_at=datetime(2026, 9, 14, tzinfo=UTC),
        )
        assert repository.latest_for_authority(authority) == {
            summary.requirement_id: later,
        }
        assert repository.latest_for_authority(authority, job_id="search-first") == {
            summary.requirement_id: summary,
        }
        for changed in (
            {"episode_revision": authority.episode_revision + 1},
            {"protocol_version_id": "different-protocol-version"},
            {"project_id": "different-project"},
            {"subject_id": "different-subject"},
            {"evidence_snapshot_v2_id": "different-snapshot"},
        ):
            assert repository.latest_for_authority(
                authority.model_copy(update=changed)
            ) == {}, changed


def test_legacy_summary_identity_remains_readable_only_for_original_authority(session_factory):
    with session_factory() as session, session.begin():
        fixture = FIXTURES[0]
        persist_fixture(session, fixture)
        _seed_page_stack(session, fixture)
        authority = _authority(fixture)
        repository = JudgmentSearchSummaryRepository(session)
        summary = _summary(
            "legacy-judgment", JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE,
            "c" * 64,
        )
        repository.save_summary(
            summary, authority=authority, job_id="legacy-search",
            created_at=datetime(2026, 9, 12, tzinfo=UTC),
        )
        legacy_id = "judgment-search-summary:" + canonical_hash({
            "authority": authority.model_dump(mode="json"),
            "summary": summary.model_dump(mode="json"),
        })[:32]
        session.execute(update(JudgmentSearchSummaryORM).values(summary_id=legacy_id))
        session.expire_all()
        assert repository.latest_for_authority(authority, job_id="legacy-search") == {
            summary.requirement_id: summary,
        }
        assert repository.latest_for_authority(
            authority.model_copy(update={"episode_revision": 2})
        ) == {}
