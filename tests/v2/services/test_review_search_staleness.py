"""Search append -> current-input check and publisher ordering, no clinical adoption.

Uses the real summary repository and ephemeral SQLite. Search execution/receipts
are not fabricated: these tests prove identity invalidation, not search quality.
Publisher seams stop before method approval or any clinical-result writes.
"""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import update

from app.domain.contracts.judgment_search import JudgmentSearchCoverageStatus
from app.domain.contracts.qualified_binding_selection import QualificationAdoptionAuthorization
from app.domain.publication import canonical_hash
from app.services import frozen_review_publication as publisher
from app.services import prepared_review_intake, prepared_review_workflow
from app.services import review_context_assembly as assembly
from app.storage.codecs import PersistedContractInvalid
from app.storage.idempotency import IdempotencyConflict, IdempotencyRepository
from app.storage.judgment_search_models import JudgmentSearchSummaryORM
from app.storage.judgment_search_repository import JudgmentSearchSummaryRepository
from app.storage.repositories import InvalidReferenceError, ScopeViolationError, persist_fixture
from app.workflow.jobstore import JobStore
from tests.v2.storage.test_migration_0019 import _seed_page_stack
from tests.v2.storage.test_migration_0022 import _authority, _summary
from tests.v2.storage.test_repositories_roundtrip import FIXTURES

NOW = datetime(2026, 10, 3, tzinfo=UTC)


def _seed(session):
    fixture = FIXTURES[0]
    persist_fixture(session, fixture)
    _seed_page_stack(session, fixture)
    return _authority(fixture)


def _context(authority, entries=()):
    # Only the fields consumed by the freshness check, not a persisted snapshot.
    from app.services.frozen_review_calculation import EVALUATOR_VERSION
    return SimpleNamespace(
        authority=authority, facts=(), fact_rule_links=(), events=(),
        medication_exposures=(), expectations=(), conflict_groups=(),
        judgment_search_results=tuple(entries), context_id="synthetic-context",
        context_sha256="f" * 64, review_run_id="synthetic-history-run",
        evaluator_version=EVALUATOR_VERSION, requirements_scope_version="review-requirements-scope/v1",
    )


def _save_search(session, authority, *, job_id, at, status):
    repository = JudgmentSearchSummaryRepository(session)
    JobStore(session).create_job(job_id=job_id, job_type="judgment_search",
                                 payload={"authority": authority.model_dump(mode="json")})
    repository.save_summary(
        _summary("judgment-required", status, "b" * 64), authority=authority,
        job_id=job_id, created_at=at,
    )
    return repository.latest_entries_for_authority(authority)["judgment-required"]


@pytest.mark.parametrize("new_status", [
    JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE,
    JudgmentSearchCoverageStatus.ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE,
])
def test_new_search_invalidates_current_input_without_rewriting_history(session_factory, new_status):
    with session_factory() as session, session.begin():
        authority = _seed(session)
        empty = _context(authority)
        assembly.require_current_review_clinical_material(session, empty)
        first = _save_search(session, authority, job_id="search-first", at=NOW,
                             status=JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE)
        with pytest.raises(ScopeViolationError, match="书面判断核查已经更新"):
            assembly.require_current_review_clinical_material(session, empty)
        frozen = _context(authority, [first])
        before = assembly.frozen_review_clinical_material_sha256(frozen)
        assembly.require_current_review_clinical_material(session, frozen)
        second = _save_search(session, authority, job_id="search-second", at=NOW + timedelta(seconds=1),
                              status=new_status)
        assert second.summary_id != first.summary_id
        assert assembly.frozen_review_clinical_material_sha256(frozen) == before
        assert JudgmentSearchSummaryRepository(session).get_entry(
            first.summary_id, authority=authority,
        ) == first
        with pytest.raises(ScopeViolationError):
            assembly.require_current_review_clinical_material(session, frozen)
        assembly.require_current_review_clinical_material(session, _context(authority, [second]))
        # No facts were changed: same-content repeat searches still have new receipts.
        assert assembly.current_review_clinical_material_sha256(session, authority) != before


def test_corrupt_search_is_not_downgraded_to_an_ordinary_stale_result(session_factory):
    with session_factory() as session, session.begin():
        authority = _seed(session)
        entry = _save_search(session, authority, job_id="search-first", at=NOW,
                             status=JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE)
        session.execute(update(JudgmentSearchSummaryORM).where(
            JudgmentSearchSummaryORM.summary_id == entry.summary_id,
        ).values(payload_sha256="a" * 64))
        session.expire_all()
        with pytest.raises(PersistedContractInvalid):
            assembly.require_current_review_clinical_material(session, _context(authority, [entry]))


def test_current_and_frozen_search_collection_order_does_not_change_identity():
    entries = [SimpleNamespace(summary_id=f"summary-{i}", job_id=f"job-{i}", payload_sha256=str(i) * 64)
               for i in (1, 2)]
    context = _context(object(), entries)
    reversed_context = _context(context.authority, reversed(entries))
    assert assembly.frozen_review_clinical_material_sha256(context) == (
        assembly.frozen_review_clinical_material_sha256(reversed_context)
    )


@pytest.mark.parametrize("changed", [{"job_id": "missing-job"}, {"summary_id": "damaged-id"}])
def test_identity_damage_cannot_resurrect_old_search(session_factory, changed):
    with session_factory() as session, session.begin():
        authority = _seed(session)
        first = _save_search(session, authority, job_id="search-first", at=NOW,
                             status=JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE)
        second = _save_search(session, authority, job_id="search-second", at=NOW + timedelta(seconds=1),
                              status=JudgmentSearchCoverageStatus.ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE)
        session.execute(update(JudgmentSearchSummaryORM).where(
            JudgmentSearchSummaryORM.summary_id == second.summary_id,
        ).values(**changed))
        session.expire_all()
        with pytest.raises(InvalidReferenceError):
            assembly.require_current_review_clinical_material(session, _context(authority, [first]))
        assert JudgmentSearchSummaryRepository(session).get_entry(first.summary_id, authority=authority) == first


def test_other_revision_has_provenance_and_cannot_become_current_search(session_factory):
    with session_factory() as session, session.begin():
        authority = _seed(session)
        old = _save_search(session, authority, job_id="search-first", at=NOW,
                           status=JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE)
        current = authority.model_copy(update={"episode_revision": authority.episode_revision + 1})
        entry = _save_search(session, current, job_id="search-current", at=NOW + timedelta(seconds=1),
                             status=JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE)
        assert JudgmentSearchSummaryRepository(session).latest_entries_for_authority(authority) == {
            old.summary.requirement_id: old,
        }
        assert JudgmentSearchSummaryRepository(session).latest_entries_for_authority(current) == {
            entry.summary.requirement_id: entry,
        }


@pytest.mark.parametrize("consumer", ["intake", "continuation"])
def test_real_search_fingerprint_reaches_prepared_review_consumers(session_factory, monkeypatch, consumer):
    with session_factory() as session, session.begin():
        authority = _seed(session)
        context = _context(authority)
        _save_search(session, authority, job_id="search-new", at=NOW,
                     status=JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE)
        job_id = "prepared-review"
        JobStore(session).create_job(job_id=job_id, job_type=prepared_review_workflow.WORKFLOW_JOB_TYPE,
                                    payload={"contract": prepared_review_workflow.CONTRACT,
                                             "execution_owner": prepared_review_workflow.OWNER,
                                             "review_context_id": context.context_id,
                                             "review_context_sha256": context.context_sha256})
    module = prepared_review_intake if consumer == "intake" else prepared_review_workflow
    monkeypatch.setattr(module, "ReviewContextV2Repository", lambda _: SimpleNamespace(get=lambda _: context))
    monkeypatch.setattr(module, "FactAuthorityValidator", lambda _: SimpleNamespace(validate=lambda _: None))
    with pytest.raises(ScopeViolationError, match="书面判断核查已经更新"):
        if consumer == "intake":
            module.require_prepared_review_intent(
                session_factory, subject_id=authority.subject_id, review_episode_id=authority.review_episode_id,
                context_id=context.context_id, kind="predicate_candidates",
            )
        else:
            with session_factory() as session:
                module.PreparedReviewContinuation._material(session, job_id)


def _authorization():
    # A typed request only. No approval gate is issued or verification bypassed.
    route = {"provider": "synthetic", "base_url": "https://invalid.example",
             "model": "synthetic", "reasoning_effort": "high", "max_tokens": 65536}
    return QualificationAdoptionAuthorization(
        authorization_id="synthetic", authorizing_service="synthetic",
        qualification_job_id="synthetic", candidate_family="predicate",
        frozen_input_sha256="a" * 64, comparison_sha256="b" * 64,
        summary_logical_sha256="c" * 64, summary_artifact_sha256="d" * 64,
        approved_evaluation_evidence_sha256="e" * 64,
        route_identities={"main-A": route, "main-B": route},
    )


def _publisher_seams(monkeypatch, context):
    monkeypatch.setattr(publisher, "ReviewContextV2Repository", lambda _: SimpleNamespace(get=lambda _: context))
    monkeypatch.setattr(publisher, "FactAuthorityValidator", lambda _: SimpleNamespace(validate=lambda _: None))
    def reject_approval(*args, **kwargs):
        raise RuntimeError("synthetic method approval boundary")
    monkeypatch.setattr(publisher, "read_review_method_approval", reject_approval)


def test_new_publication_checks_current_search_before_method_approval(session_factory, monkeypatch):
    with session_factory() as session, session.begin():
        authority = _seed(session)
        context = _context(authority)
        _publisher_seams(monkeypatch, context)
        # Unchanged inputs reach the existing method gate, not a new automatic adoption.
        with pytest.raises(RuntimeError, match="method approval boundary"):
            publisher.publish_frozen_review(
                session, object(), context_id=context.context_id, authorizations=[_authorization()],
                method_approval_gate_id="synthetic", idempotency_key="new",
            )
        _save_search(session, authority, job_id="search-new", at=NOW,
                     status=JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE)
        with pytest.raises(ScopeViolationError, match="书面判断核查已经更新"):
            publisher.publish_frozen_review(
                session, object(), context_id=context.context_id, authorizations=[_authorization()],
                method_approval_gate_id="synthetic", idempotency_key="new",
            )
        assert IdempotencyRepository(session).get(f"formal-review:{context.context_id}", "new") is None


def test_same_completed_receipt_returns_history_even_after_search_update(session_factory, monkeypatch):
    with session_factory() as session, session.begin():
        authority = _seed(session)
        context = _context(authority)
        _publisher_seams(monkeypatch, context)
        authorization = _authorization()
        request = canonical_hash({
            "version": publisher.PUBLICATION_VERSION, "context": context.context_sha256,
            "authorizations": [authorization.model_dump(mode="json")], "method": "synthetic",
        })
        repository = IdempotencyRepository(session)
        receipt, _ = repository.resolve(
            scope=f"formal-review:{context.context_id}", idempotency_key="saved",
            submitted_hash=request, result_type="review_run", result_id=context.review_run_id,
        )
        monkeypatch.setattr(publisher, "get_run", lambda *args: SimpleNamespace(status="completed"))
        _save_search(session, authority, job_id="search-new", at=NOW,
                     status=JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE)
        assert publisher.publish_frozen_review(
            session, object(), context_id=context.context_id, authorizations=[authorization],
            method_approval_gate_id="synthetic", idempotency_key="saved",
        ) == context.review_run_id
        assert repository.get(f"formal-review:{context.context_id}", "saved") == receipt


def test_old_publication_receipt_is_not_upgraded_or_overwritten(session_factory, monkeypatch):
    with session_factory() as session, session.begin():
        context = _context(_seed(session))
        _publisher_seams(monkeypatch, context)
        authorization = _authorization()
        old_request = canonical_hash({
            "version": "frozen-review-publication/v17", "context": context.context_sha256,
            "authorizations": [authorization.model_dump(mode="json")], "method": "synthetic",
        })
        repository = IdempotencyRepository(session)
        receipt, _ = repository.resolve(
            scope=f"formal-review:{context.context_id}", idempotency_key="saved-v17",
            submitted_hash=old_request, result_type="review_run", result_id=context.review_run_id,
        )
        with pytest.raises(IdempotencyConflict):
            publisher.publish_frozen_review(
                session, object(), context_id=context.context_id, authorizations=[authorization],
                method_approval_gate_id="synthetic", idempotency_key="saved-v17",
            )
        assert repository.get(f"formal-review:{context.context_id}", "saved-v17") == receipt


def test_old_method_approval_cannot_authorize_current_publication(session_factory, monkeypatch):
    with session_factory() as session, session.begin():
        context = _context(_seed(session))
        _publisher_seams(monkeypatch, context)
        authorization = _authorization()
        method = SimpleNamespace(candidate_family="predicate", publication_version="frozen-review-publication/v17",
                                 evaluator_version=publisher.EVALUATOR_VERSION,
                                 consumer_algorithm_version=authorization.consumer_algorithm_version)
        manifest = SimpleNamespace(evaluation_kind="binding_semantic_correspondence", methods=[method])
        monkeypatch.setattr(publisher, "read_review_method_approval", lambda *args: (
            object(), {authorization.approved_evaluation_evidence_sha256: manifest},
        ))
        with pytest.raises(ScopeViolationError, match="当前审核计算版本"):
            publisher.publish_frozen_review(
                session, object(), context_id=context.context_id, authorizations=[authorization],
                method_approval_gate_id="synthetic", idempotency_key="old-method",
            )
        assert IdempotencyRepository(session).get(f"formal-review:{context.context_id}", "old-method") is None
