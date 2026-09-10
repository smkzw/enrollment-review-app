"""Revalidate R3 candidate provenance before reusing persisted step results."""

from types import SimpleNamespace

from app.domain.contracts.facts import ClinicalFactCandidateV2
from app.projections.page_review_sources import validate_accepted_candidate_sources
from app.services.fact_normalization_source_adapter import build_evidence_normalizer_input
from app.storage.fact_repositories import FactNormalizationCandidateRepository


def validate_replayed_sources(session, *, payload, authority, run, call, candidate_ids):
    coverage_id = payload.get("page_review_coverage_id")
    if not coverage_id:
        return
    from app.services.page_review_visual_sources import VISUAL_SOURCE_POLICY
    if payload.get("visual_source_policy") not in (None, VISUAL_SOURCE_POLICY):
        raise ValueError("视觉来源处理版本不受支持")
    evidence = build_evidence_normalizer_input(
        session, authority=authority, run_id=run.run_id, call_id=call["call_id"],
        logical_document_id=call["logical_document_id"], page_numbers=call["page_numbers"],
        expected_input_sha256=call["input_sha256"],
        max_pages_per_call=int(payload.get("max_pages_per_call", 20)),
        created_at=run.created_at, page_review_coverage_id=coverage_id,
        include_visual_sources=payload.get("visual_source_policy") == VISUAL_SOURCE_POLICY,
    )
    repository = FactNormalizationCandidateRepository(session)
    candidates = [repository.get(candidate_id) for candidate_id in candidate_ids]
    validate_accepted_candidate_sources(
        SimpleNamespace(fact_candidates=[item for item in candidates if isinstance(item, ClinicalFactCandidateV2)]),
        evidence.page_review, locator_inputs=evidence.available_locators,
    )
