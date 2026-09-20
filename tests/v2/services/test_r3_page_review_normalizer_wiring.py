"""R3 页级判读进入事实规范化任务的最小接线测试。"""

from __future__ import annotations

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
from app.services.fact_normalization_job_service import FactNormalizationJobService
from app.services.fact_normalization_source_adapter import build_evidence_normalizer_input
from app.storage.ocr_models import PageArtifactRecord
from app.storage.page_review_repository import PageReviewRepository
from app.llm.page_review_harness import PAGE_REVIEW_PROMPT_VERSION, require_page_reader_routes
from app.llm.page_review_transport_options import page_transport_contract
from app.domain.page_reconciliation import reconcile_page_reviews
from app.services.page_review_job_service import page_review_execution_versions, main_reader_identity
from tests.v2.services.test_fact_normalization_persistence import NOW, _seed_chain

PACK_SHA = "c" * 64


def _persist_page_review(session, chain: dict[str, object], *, pack=None, accepted=True,
                         routes=None, facts=None) -> str:
    pack_sha = pack.clause_pack_sha256 if pack else PACK_SHA
    page = session.get(PageArtifactRecord, chain["page_artifact_id"])
    records = []
    reader_routes = routes if routes is not None else require_page_reader_routes(require_credentials=False)
    for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B):
        transport = page_transport_contract(reader_routes[lane].provider)
        prompt_version = PAGE_REVIEW_PROMPT_VERSION + (f":{transport}" if transport else "")
        records.append(
            PageReviewRecord(
                page_review_id=f"{chain['subject_id']}-{lane.value}",
                page_artifact_id=page.page_artifact_id,
                source_document_version_id=chain["doc_id"],
                page_number=1,
                page_image_sha256=page.page_image_sha256,
                clause_pack_id=pack.clause_pack_id if pack else "clause-pack:" + "d" * 32,
                clause_pack_sha256=pack_sha,
                lane=lane,
                provider=reader_routes[lane].provider,
                model=reader_routes[lane].model,
                reasoning_effort=reader_routes[lane].reasoning_effort,
                endpoint_base_url=reader_routes[lane].base_url,
                fallback_used=False,
                prompt_version=prompt_version if pack else "page-review-r3/v1",
                response_sha256=("a" if lane == PageReviewLane.MAIN_A else "b")
                * 64,
                has_eligibility_value=True,
                facts=facts or [],
                clause_signals=[
                    ClauseEvidenceSignal(
                        clause_id=pack.clauses[0].clause_id if pack else "clause-1",
                        signal=EvidenceSignal.MENTIONS,
                        region=PageRegion(excerpt="ALT 5.6 U/L"),
                    )
                ],
                handwriting=[],
                created_at=NOW,
            )
        )
    reconciliation = PageReconciliation(
        reconciliation_id=f"{chain['subject_id']}-reconciliation",
        page_artifact_id=page.page_artifact_id,
        clause_pack_sha256=pack_sha,
        page_review_ids=[item.page_review_id for item in records],
        accepted_clause_signals=records[0].clause_signals if accepted else [],
        created_at=NOW,
    )
    if pack:
        from app.services.page_association_sources import page_association_sources
        from app.storage.evidence_locator_repositories import CompleteEvidenceProcessingRevisionRepository
        sources = page_association_sources(session, CompleteEvidenceProcessingRevisionRepository(session).get(
            chain["complete_revision_id"]))
        reconciliation = reconcile_page_reviews(records, determination_modes={
            clause.clause_id: clause.determination_mode for clause in pack.clauses},
            association_source=sources.get(page.page_artifact_id))
    coverage = SubjectPageCoverage(
        execution_versions=page_review_execution_versions() if pack else {},
        main_reader_identity_sha256=main_reader_identity(reader_routes) if pack else None,
        coverage_id=f"{chain['subject_id']}-coverage",
        subject_id=chain["subject_id"],
        review_episode_id=chain["episode_id"],
        evidence_snapshot_id=chain["snapshot_id"],
        evidence_processing_revision_id=chain["complete_revision_id"],
        clause_pack_sha256=pack_sha,
        expected_page_artifact_ids=[page.page_artifact_id],
        entries=[
            PageCoverageEntry(
                page_artifact_id=page.page_artifact_id,
                source_document_version_id=chain["doc_id"],
                page_number=1,
                disposition=PageDisposition.ACCEPTED,
                reconciliation_id=reconciliation.reconciliation_id,
            )
        ],
        created_at=NOW,
    )
    repo = PageReviewRepository(session)
    for record in records:
        repo.save_review(record)
    repo.save_reconciliation(reconciliation)
    repo.save_coverage(coverage)
    return coverage.coverage_id


def test_job_freezes_page_review_scope_and_executor_can_rebuild(session_factory) -> None:
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="r3-normalizer")
        coverage_id = _persist_page_review(session, chain)

    service = FactNormalizationJobService(session_factory)
    created = service.create_or_reuse_from_source(
        authority=chain["authority"],
        prompt_version_id=chain["prompt_version_id"],
        model_config_id=chain["model_config_id"],
        created_by="tester",
        page_review_coverage_id=coverage_id,
    )
    payload = service.get_job(created.job_id)["payload"]
    assert payload["page_review_coverage_id"] == coverage_id

    call = payload["calls"][0]
    with session_factory() as session:
        evidence_input = build_evidence_normalizer_input(
            session,
            authority=chain["authority"],
            run_id=created.run_id,
            call_id=call["call_id"],
            logical_document_id=call["logical_document_id"],
            page_numbers=call["page_numbers"],
            expected_input_sha256=call["input_sha256"],
            page_review_coverage_id=coverage_id,
            created_at=NOW,
        )
    assert evidence_input.page_review is not None
    assert evidence_input.page_review.coverage_id == coverage_id
    from app.agents.evidence_normalizer import build_evidence_normalizer_prompt
    long_template = "完整内容" * 30_000
    prompt = build_evidence_normalizer_prompt(evidence_input, prompt_template=long_template)
    assert prompt.startswith(long_template)
    assert len(prompt) > 100_000
    assert "ALT 5.6 U/L" in prompt


@pytest.mark.parametrize("accepted,legacy,expected_calls,with_pending", [
    (False, False, 0, False), (True, False, 1, False), (False, True, 1, False),
    (True, False, 1, True), (False, False, 0, True), (True, True, 1, True),
])
def test_pending_only_group_preserves_pages_without_model_call(
    session_factory, accepted, legacy, expected_calls, with_pending,
):
    from app.services.fact_normalization_executor import (
        FactNormalizationExecutorConfig, create_fact_normalization_executor,
    )
    from app.workflow.runner import StepContext
    from app.projections.page_review_pending_normalization import PENDING_NORMALIZATION_POLICY

    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="pending-only")
        from tests.v2.domain.test_page_review_contracts import _fact
        coverage_id = _persist_page_review(session, chain, accepted=accepted,
                                          facts=[_fact()] if with_pending else None)
    service = FactNormalizationJobService(session_factory)
    params = dict(authority=chain["authority"], prompt_version_id=chain["prompt_version_id"],
                  model_config_id=chain["model_config_id"], created_by="tester",
                  page_review_coverage_id=coverage_id)
    created = service.create_or_reuse_from_source(**params)
    assert service.create_or_reuse_from_source(**params).job_id == created.job_id
    payload = service.get_job(created.job_id)["payload"]
    assert payload["pending_normalization_policy"] == PENDING_NORMALIZATION_POLICY
    if legacy:
        payload = dict(payload)
        payload.pop("pending_normalization_policy")

    calls = []
    def transport(evidence_input):
        from app.domain.contracts.evidence_normalizer import (
            EvidenceNormalizerOutput, EvidenceNormalizerUnresolvedItem,
        )
        calls.append(evidence_input.call_id)
        assert expected_calls == 1
        return EvidenceNormalizerOutput(
            run_id=evidence_input.run_id, call_id=evidence_input.call_id,
            logical_document_id=evidence_input.logical_document_id,
            page_numbers=evidence_input.page_numbers,
            unresolved_items=[EvidenceNormalizerUnresolvedItem(
                code="test_unresolved", message="本页尚待核实", reason="测试返回原页待核实项",
                affected_pages=evidence_input.page_numbers,
            )],
        )

    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(
        session_factory=session_factory, transport_fn=transport,
    ))
    context = StepContext(job_id=created.job_id, job_type="fact_normalization", job_payload=payload,
        step_id="normalize_000_" + chain["logical_document_id"], name="test", attempt=1,
        last_checkpoint_id=None, last_checkpoint=None, max_attempts=3)
    prepared = executor(context)
    assert len(calls) == expected_calls
    if expected_calls == 0:
        assert prepared.checkpoint["model_called"] is False
        assert prepared.checkpoint["normalization_method"] == PENDING_NORMALIZATION_POLICY
    else:
        assert "normalization_method" not in prepared.checkpoint
    assert prepared.checkpoint["candidate_ids"] == []
    assert prepared.checkpoint["unresolved_items"][0]["affected_pages"] == [1]
    retained = [item for item in prepared.checkpoint["unresolved_items"]
                if item["code"] == "page_observation_unverified"]
    assert len(retained) == int(with_pending and not legacy)
    if retained:
        assert "2条" in retained[0]["message"]
        assert _fact().raw_value in retained[0]["reason"]
        assert retained[0]["gap_type"] is None
    with session_factory() as session, session.begin():
        prepared.apply(session)
    from dataclasses import replace
    from app.services.fact_normalization_job_service import FACT_NORMALIZATION_FINALIZE_STEP_ID
    finalized = executor(replace(context, step_id=FACT_NORMALIZATION_FINALIZE_STEP_ID))
    with session_factory() as session, session.begin():
        finalized.apply(session)
    assert finalized.checkpoint["status"] == "partial"
    assert finalized.checkpoint["unresolved_item_count"] == 1 + int(with_pending and not legacy)
    assert "patient_profile_revision_id" not in finalized.checkpoint
    assert len(calls) == expected_calls
