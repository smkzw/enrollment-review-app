from types import SimpleNamespace

import pytest

from app.services import fact_normalization_replay_sources as replay
from tests.v2.agents.test_evidence_normalizer_adapter import _r3_input


def test_legacy_replay_does_not_silently_attach_new_page_reviews(monkeypatch):
    monkeypatch.setattr(replay, "build_evidence_normalizer_input", lambda *a, **k: pytest.fail("unexpected read"))
    replay.validate_replayed_sources(None, payload={}, authority=None, run=None, call={}, candidate_ids=[])


@pytest.mark.parametrize("refs", [[], ["pending-observation"], ["fabricated-ref"], None])
def test_replay_checks_persisted_sources_against_frozen_coverage(monkeypatch, refs):
    from app.projections.page_review_sources import accepted_observations
    evidence = _r3_input()
    captured = []
    def build(*args, **kwargs):
        captured.append(kwargs)
        return evidence
    monkeypatch.setattr(replay, "build_evidence_normalizer_input", build)
    source = accepted_observations(evidence.page_review.reviews, evidence.page_review.reconciliations[0])[0]
    candidate = replay.ClinicalFactCandidateV2.model_construct(
        source_observation_refs=refs if refs is not None else [source["source_observation_ref"]], locator_ids=["loc-1"])
    monkeypatch.setattr(replay, "FactNormalizationCandidateRepository",
                        lambda session: SimpleNamespace(get=lambda identity: candidate))
    def run():
        replay.validate_replayed_sources(None, payload={"page_review_coverage_id": "coverage-frozen"},
            authority=evidence.authority, run=SimpleNamespace(run_id="run", created_at=evidence.created_at),
            call={"call_id": "call", "logical_document_id": "doc", "page_numbers": [1, 2], "input_sha256": "hash"},
            candidate_ids=["candidate"])
    if refs is None:
        run()
    else:
        with pytest.raises(ValueError, match="已采信观察"):
            run()
    assert captured[0]["page_review_coverage_id"] == "coverage-frozen"
