"""页级判读、对账和覆盖记录的追加写及来源闭包。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.contracts.page_review import (
    ClauseEvidenceSignal,
    EvidenceSignal,
    PageCoverageEntry,
    PageDisposition,
    PageReconciliation,
    PageRegion,
    PageReviewLane,
    PageReviewRecord,
    SubjectPageCoverage,
)
from app.storage.page_review_models import SubjectPageCoverageEntryORM
from app.storage.page_review_repository import PageReviewRepository
from app.storage.codecs import PersistedContractInvalid
from app.storage.repositories import ScopeViolationError, persist_fixture
from app.services.fact_normalization_source_adapter import (
    FactPlanningSourceError,
    build_page_review_normalizer_input,
)
from tests.v2.storage.test_migration_0019 import _IMAGE_SHA, _seed_page_stack
from tests.v2.storage.test_repositories_roundtrip import FIXTURES

NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)
PACK_SHA = "c" * 64


def _review(lane: PageReviewLane | str) -> PageReviewRecord:
    lane = PageReviewLane(lane)
    return PageReviewRecord(
        page_review_id=f"review-{lane.value}",
        page_artifact_id="pa-1",
        source_document_version_id="doc-1",
        page_number=1,
        page_image_sha256=_IMAGE_SHA,
        clause_pack_id="clause-pack:" + "d" * 32,
        clause_pack_sha256=PACK_SHA,
        lane=lane,
        provider="zhipu-coding-plan" if lane == PageReviewLane.MAIN_A else "cms-smk",
        model="GLM-5.3-Flash" if lane == PageReviewLane.MAIN_A else "MiniMax-M3",
        reasoning_effort="high",
        endpoint_base_url="https://independent.example/v1",
        fallback_used=False,
        finish_reason="stop",
        prompt_version="page-review-r3/v1",
        response_sha256=("a" if lane == PageReviewLane.MAIN_A else "b") * 64,
        has_eligibility_value=True,
        facts=[],
        clause_signals=[
            ClauseEvidenceSignal(
                clause_id="clause-1",
                signal=EvidenceSignal.MENTIONS,
                region=PageRegion(excerpt="原始证据摘录"),
            )
        ],
        handwriting=[],
        created_at=NOW,
    )


def _reconciliation() -> PageReconciliation:
    return PageReconciliation(
        reconciliation_id="reconciliation-1",
        page_artifact_id="pa-1",
        clause_pack_sha256=PACK_SHA,
        page_review_ids=["review-main-A", "review-main-B"],
        accepted_clause_signals=[
            ClauseEvidenceSignal(
                clause_id="clause-1",
                signal=EvidenceSignal.MENTIONS,
                region=PageRegion(excerpt="原始证据摘录"),
            )
        ],
        created_at=NOW,
    )


def _coverage(fixture) -> SubjectPageCoverage:
    return SubjectPageCoverage(
        coverage_id="coverage-1",
        subject_id=fixture.subject.subject_id,
        review_episode_id=fixture.review_episode.review_episode_id,
        evidence_snapshot_id="snap-1",
        evidence_processing_revision_id="rev-1",
        clause_pack_sha256=PACK_SHA,
        expected_page_artifact_ids=["pa-1"],
        entries=[
            PageCoverageEntry(
                page_artifact_id="pa-1",
                source_document_version_id="doc-1",
                page_number=1,
                disposition=PageDisposition.ACCEPTED,
                reconciliation_id="reconciliation-1",
            )
        ],
        created_at=NOW,
    )


def test_roundtrip_and_association_tamper_detection(session_factory) -> None:
    fixture = FIXTURES[0]
    with session_factory() as session, session.begin():
        persist_fixture(session, fixture)
        _seed_page_stack(session, fixture)
        repo = PageReviewRepository(session)
        for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B):
            repo.save_review(_review(lane))
        repo.save_reconciliation(_reconciliation())
        coverage = repo.save_coverage(_coverage(fixture))
        assert repo.get_coverage(coverage.coverage_id) == coverage

        entry = session.get(SubjectPageCoverageEntryORM, ("coverage-1", "pa-1"))
        entry.page_number = 2
        session.flush()
        with pytest.raises(PersistedContractInvalid, match="关联表"):
            repo.get_coverage("coverage-1")


def test_review_rejects_page_source_drift(session_factory) -> None:
    fixture = FIXTURES[0]
    with session_factory() as session, session.begin():
        persist_fixture(session, fixture)
        _seed_page_stack(session, fixture)
        bad = _review(PageReviewLane.MAIN_A).model_copy(update={"page_number": 2})
        with pytest.raises(ScopeViolationError, match="页码"):
            PageReviewRepository(session).save_review(bad)


def test_identical_response_from_new_prompt_keeps_both_read_identities(session_factory):
    with session_factory() as session, session.begin():
        fixture = FIXTURES[0]
        persist_fixture(session, fixture)
        _seed_page_stack(session, fixture)
        repo = PageReviewRepository(session)
        original = _review("main-A")
        newer = original.model_copy(update={"page_review_id": "review-new-prompt", "prompt_version": "page-review-r3/v11"})
        repo.save_review(original)
        repo.save_review(newer)
        assert repo.get_review(original.page_review_id) == original
        assert repo.get_review(newer.page_review_id) == newer


def test_reread_predecessor_is_source_bound_and_legacy_serialization_unchanged(session_factory):
    fixture = FIXTURES[0]
    with session_factory() as session, session.begin():
        persist_fixture(session, fixture)
        _seed_page_stack(session, fixture)
        repo = PageReviewRepository(session)
        failed = PageCoverageEntry(
            page_artifact_id="pa-1", source_document_version_id="doc-1", page_number=1,
            disposition=PageDisposition.FAILED_PENDING_REREAD,
            lane_failures=[{"lane": "main-B", "failure_kind": "schema"}],
        )
        original = _coverage(fixture).model_copy(update={"entries": [failed]})
        assert "predecessor_coverage_id" not in original.model_dump(mode="json")
        repo.save_coverage(original)
        successor = original.model_copy(update={"coverage_id": "coverage-2", "predecessor_coverage_id": "coverage-1"})
        repo.save_coverage(successor)
        assert repo.get_coverage("coverage-2") == successor
        with pytest.raises(ScopeViolationError, match="自身"):
            repo.save_coverage(successor.model_copy(update={"coverage_id": "coverage-1"}))
        for changes in ({"clause_pack_sha256": "e" * 64}, {"execution_versions": {"contract": "changed"}}):
            with pytest.raises(ScopeViolationError, match="来源或处理版本"):
                repo.save_coverage(successor.model_copy(update={"coverage_id": "invalid", **changes}))
        discarded = PageCoverageEntry(
            page_artifact_id="pa-1", source_document_version_id="doc-1", page_number=1,
            disposition=PageDisposition.DISCARDED_NO_ELIGIBILITY_VALUE, discard_reason="未发现相关内容",
        )
        completed = successor.model_copy(update={"coverage_id": "coverage-3", "entries": [discarded]})
        repo.save_coverage(completed)
        with pytest.raises(ScopeViolationError, match="既无失败页面"):
            repo.save_coverage(completed.model_copy(update={"coverage_id": "coverage-4", "predecessor_coverage_id": "coverage-3"}))


def test_normalizer_input_rebuilds_only_accepted_page_records(session_factory) -> None:
    fixture = FIXTURES[0]
    with session_factory() as session, session.begin():
        persist_fixture(session, fixture)
        _seed_page_stack(session, fixture)
        repo = PageReviewRepository(session)
        for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B):
            repo.save_review(_review(lane))
        repo.save_reconciliation(_reconciliation())
        repo.save_coverage(_coverage(fixture))

        result = build_page_review_normalizer_input(
            session,
            coverage_id="coverage-1",
            logical_document_id="logical-1",
            page_numbers=[1],
            doc_version_to_logical={"doc-1": "logical-1"},
        )

        assert [item.page_review_id for item in result.reviews] == [
            "review-main-A",
            "review-main-B",
        ]
        assert [item.reconciliation_id for item in result.reconciliations] == [
            "reconciliation-1"
        ]


def test_normalizer_input_rejects_page_pending_reread(session_factory) -> None:
    fixture = FIXTURES[0]
    with session_factory() as session, session.begin():
        persist_fixture(session, fixture)
        _seed_page_stack(session, fixture)
        failed = _coverage(fixture).model_copy(
            update={
                "coverage_id": "coverage-failed",
                "entries": [
                    PageCoverageEntry(
                        page_artifact_id="pa-1",
                        source_document_version_id="doc-1",
                        page_number=1,
                        disposition=PageDisposition.FAILED_PENDING_REREAD,
                        lane_failures=[
                            {
                                "lane": "main-B",
                                "failure_kind": "endpoint_unavailable",
                            }
                        ],
                    )
                ],
            }
        )
        PageReviewRepository(session).save_coverage(failed)

        with pytest.raises(FactPlanningSourceError, match="失败待复读"):
            build_page_review_normalizer_input(
                session,
                coverage_id="coverage-failed",
                logical_document_id="logical-1",
                page_numbers=[1],
                doc_version_to_logical={"doc-1": "logical-1"},
            )
