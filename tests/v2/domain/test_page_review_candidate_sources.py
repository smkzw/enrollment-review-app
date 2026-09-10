from types import SimpleNamespace

import pytest

from app.domain.contracts.page_review import PageReviewRecord
from app.domain.page_reconciliation import reconcile_page_reviews
from app.domain.publication import canonical_hash
from app.projections.page_review_sources import accepted_observations, validate_accepted_candidate_sources
from tests.v2.domain.test_page_review_contracts import _review_payload


def test_literal_matching_only_normalizes_layout_not_clinical_tokens():
    from app.projections.page_review_sources import _literal_text
    assert _literal_text("Ａ １\n２") == "A12"
    assert _literal_text("未见异常") != _literal_text("见异常")
    assert _literal_text("< 5") != _literal_text("5")
    assert _literal_text("2026-09-01") != _literal_text("2026-09-02")


def test_visual_reference_binds_exact_reader_excerpt_and_coverage():
    from tests.v2.domain.test_page_review_evidence_sources import _pair, _materialize
    from app.projections.page_review_visual_locators import project_visual_locators
    from app.domain.contracts.evidence_normalizer import EvidenceNormalizerLocatorInput
    a, b = _pair()
    rec = reconcile_page_reviews([a, b], determination_modes={})
    group = _materialize(a, b, rec)
    locator = project_visual_locators(group)[0]
    item = next(item for item in accepted_observations([a], rec) if item["kind"] == "facts")
    attachment = SimpleNamespace(coverage_id=group.coverage_id, reviews=[a, b], reconciliations=[rec])
    source = EvidenceNormalizerLocatorInput(
        locator_id=locator.locator_id, page_number=locator.page_number,
        source_layer=locator.source_layer, precision=locator.precision,
        source_text_sha256=locator.source_text_sha256, localized_text=locator.excerpt,
        page_review_visual=locator.page_review_visual)
    output = SimpleNamespace(fact_candidates=[SimpleNamespace(
        source_observation_refs=[item["source_observation_ref"]], locator_ids=[source.locator_id])])
    validate_accepted_candidate_sources(output, attachment, locator_inputs=[source])
    for field, value in (("coverage_id", "other"), ("page_review_id", "other")):
        wrong = source.model_copy(update={"page_review_visual": source.page_review_visual.model_copy(update={field: value})})
        with pytest.raises(ValueError, match="视觉定位"):
            validate_accepted_candidate_sources(output, attachment, locator_inputs=[wrong])


def test_only_explicit_accepted_source_can_support_candidate():
    a = PageReviewRecord(**_review_payload())
    b = PageReviewRecord(**{**_review_payload(), "page_review_id": "b", "lane": "main-B"})
    reconciliation = reconcile_page_reviews([a, b], determination_modes={})
    attachment = SimpleNamespace(reviews=[a, b], reconciliations=[reconciliation])
    source = accepted_observations([a, b], reconciliation)[0]["source_observation_ref"]
    output = SimpleNamespace(fact_candidates=[SimpleNamespace(source_observation_refs=[source], locator_ids=["loc"])])
    excerpt = accepted_observations([a, b], reconciliation)[0]["observation"]["region"]["excerpt"]
    locators = [SimpleNamespace(locator_id="loc", page_number=a.page_number, localized_text=excerpt)]
    validate_accepted_candidate_sources(output, attachment, locator_inputs=locators)
    for wrong_page in (a.page_number + 1,):
        with pytest.raises(ValueError, match="来源页一致"):
            validate_accepted_candidate_sources(output, attachment, locator_inputs=[
                SimpleNamespace(locator_id="loc", page_number=wrong_page, localized_text=excerpt)])
    for wrong_text in (None, "同页另一项不相关内容"):
        with pytest.raises(ValueError, match="摘录无法"):
            validate_accepted_candidate_sources(output, attachment, locator_inputs=[
                SimpleNamespace(locator_id="loc", page_number=a.page_number, localized_text=wrong_text)])
    with pytest.raises(ValueError, match="来源页一致"):
        validate_accepted_candidate_sources(output, attachment)
    for refs in ([], ["pending-observation"], [source, "other-document"]):
        output.fact_candidates[0].source_observation_refs = refs
        with pytest.raises(ValueError):
            validate_accepted_candidate_sources(output, attachment)
    validate_accepted_candidate_sources(output, None)


def test_source_failure_identifies_candidate_reference_and_preserves_strict_match():
    a = PageReviewRecord(**_review_payload())
    b = PageReviewRecord(**{**_review_payload(), "page_review_id": "b", "lane": "main-B"})
    rec = reconcile_page_reviews([a, b], determination_modes={})
    item = accepted_observations([a, b], rec)[0]
    ref = item["source_observation_ref"]
    candidate = SimpleNamespace(candidate_id="fact-example", source_observation_refs=[ref], locator_ids=["loc"])
    with pytest.raises(ValueError) as error:
        validate_accepted_candidate_sources(
            SimpleNamespace(fact_candidates=[candidate]),
            SimpleNamespace(reviews=[a, b], reconciliations=[rec]),
            locator_inputs=[SimpleNamespace(locator_id="loc", page_number=a.page_number, localized_text="不同原文")],
        )
    assert "fact-example" in str(error.value)
    assert ref in str(error.value)
    assert "未解决项保留" in str(error.value)


def test_agreed_absence_of_page_evidence_cannot_support_a_fact():
    payload = {**_review_payload(), "facts": [], "handwriting": [],
               "clause_signals": [{"clause_id": "clause-1", "signal": "none"}]}
    a = PageReviewRecord(**payload)
    b = PageReviewRecord(**{**payload, "page_review_id": "b", "lane": "main-B"})
    reconciliation = reconcile_page_reviews([a, b], determination_modes={})
    assert reconciliation.accepted_clause_signals
    assert accepted_observations([a, b], reconciliation) == []
    historical_ref = "page-observation:" + canonical_hash({
        "review_id": a.page_review_id, "kind": "clause_signals", "index": 0,
    })
    output = SimpleNamespace(fact_candidates=[SimpleNamespace(source_observation_refs=[historical_ref])])
    attachment = SimpleNamespace(reviews=[a, b], reconciliations=[reconciliation])
    with pytest.raises(ValueError, match="已采信观察"):
        validate_accepted_candidate_sources(output, attachment)
