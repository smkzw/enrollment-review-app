from app.domain.contracts.page_review import PageReviewRecord
from app.domain.page_reconciliation import reconcile_page_reviews
from app.projections.page_review_pending import pending_page_observations
from tests.v2.domain.test_page_review_contracts import _review_payload
import pytest


@pytest.mark.parametrize("second_mark", ["↓", ""])
def test_same_value_different_annotation_is_explicitly_unresolved(second_mark):
    from app.domain.page_normalization import fact_normalization_key
    from tests.v2.domain.test_page_observation_context import _fact
    reviews = []
    for lane, mark in (("main-A", "↑"), ("main-B", second_mark)):
        fact = _fact("2026-09-01")
        fact.raw_value = "4.3" + mark
        fact.normalization_key, fact.normalized_value, fact.normalized_unit = fact_normalization_key(
            fact.field_name, fact.raw_value, context=fact.context.model_dump())
        reviews.append(PageReviewRecord(**{**_review_payload(), "page_review_id": lane,
                                           "lane": lane, "facts": [fact]}))
    reconciliation = reconcile_page_reviews(reviews, determination_modes={})
    pending = pending_page_observations(reviews, reconciliation)
    assert len(pending) == 2
    assert {item["review_status"] for item in pending} == {"read_annotation_disagreement"}
    assert all(item["use"] == "unresolved_only" for item in pending)
    assert not reconciliation.accepted_fact_keys


def test_text_anchor_is_unique_exact_and_version_bound():
    import hashlib
    from app.projections.page_review_pending import _unique_text_anchor
    text = "项目甲：未见异常。项目乙：需复查。"
    anchor = _unique_text_anchor(text, "未见异常")
    assert text[anchor["text_start"]:anchor["text_end"]] == "未见异常"
    assert anchor["source_layer"] == "effective_text"
    assert anchor["source_text_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    assert _unique_text_anchor(text + text, "未见异常") is None
    assert _unique_text_anchor(text, "未发现异常") is None
    assert _unique_text_anchor(text, "") is None


def test_pending_anchor_never_uses_another_page_or_document():
    a = PageReviewRecord(**_review_payload())
    b = PageReviewRecord(**{**_review_payload(), "page_review_id": "b", "lane": "main-B", "facts": []})
    result = reconcile_page_reviews([a, b], determination_modes={})
    excerpt = a.facts[0].region.excerpt
    for identity in (("other", a.page_number), (a.source_document_version_id, a.page_number + 1)):
        pending = pending_page_observations([a, b], result, page_texts={identity: excerpt})
        assert pending[0]["text_anchor"] is None
    pending = pending_page_observations([a, b], result, page_texts={
        (a.source_document_version_id, a.page_number): excerpt})
    assert pending[0]["text_anchor"]["excerpt"] == excerpt
    assert pending[0]["use"] == "unresolved_only"
    assert not result.accepted_fact_keys


def test_pending_observations_preserve_source_identity_and_raw_evidence():
    a = PageReviewRecord(**_review_payload())
    b = PageReviewRecord(**{**_review_payload(), "page_review_id": "b", "lane": "main-B", "facts": []})
    reconciliation = reconcile_page_reviews([a, b], determination_modes={})
    pending = pending_page_observations([a, b], reconciliation)
    assert len(pending) == 1
    assert pending[0]["observation"] == a.facts[0].model_dump(mode="json")
    assert pending[0]["page_review_id"] == a.page_review_id
    assert pending[0]["source_document_version_id"] == a.source_document_version_id
    assert pending[0]["use"] == "unresolved_only"
    assert pending[0]["review_status"] == "single_source"
    assert not reconciliation.accepted_fact_keys


def test_accepted_observations_are_not_relabelled_pending():
    a = PageReviewRecord(**_review_payload())
    b = PageReviewRecord(**{**_review_payload(), "page_review_id": "b", "lane": "main-B"})
    reconciliation = reconcile_page_reviews([a, b], determination_modes={})
    assert pending_page_observations([a, b], reconciliation) == []


def test_same_unique_passage_links_different_labels_without_accepting_facts():
    from app.domain.page_normalization import fact_normalization_key
    a = PageReviewRecord(**_review_payload())
    fact = a.facts[0].model_copy(deep=True)
    fact.field_name = "另一展示名称"
    fact.normalization_key, fact.normalized_value, fact.normalized_unit = fact_normalization_key(
        fact.field_name, fact.raw_value, context=fact.context.model_dump())
    b = PageReviewRecord(**{**_review_payload(), "page_review_id": "b", "lane": "main-B", "facts": [fact]})
    result = reconcile_page_reviews([a, b], determination_modes={})
    text = a.facts[0].region.excerpt
    texts = {(a.source_document_version_id, a.page_number): text}
    pending = pending_page_observations([a, b], result, page_texts=texts)
    assert len(pending) == 2
    assert all("same_source_passage" in item for item in pending)
    assert all(item["use"] == "unresolved_only" for item in pending)
    assert not result.accepted_fact_keys
    texts[(a.source_document_version_id, a.page_number)] = text + "\n" + text
    assert all("same_source_passage" not in item for item in
               pending_page_observations([a, b], result, page_texts=texts))


def test_different_dates_are_association_pending_not_value_disagreement():
    from tests.v2.domain.test_page_observation_context import _fact
    a = PageReviewRecord(**{**_review_payload(), "facts": [_fact("2026-09-01")]})
    b = PageReviewRecord(**{**_review_payload(), "page_review_id": "b", "lane": "main-B",
                           "facts": [_fact("2026-09-02")]})
    result = reconcile_page_reviews([a, b], determination_modes={})
    assert {item["review_status"] for item in pending_page_observations([a, b], result)} == {"association_pending"}
    assert not result.accepted_fact_keys


def test_same_association_different_values_remain_unresolved():
    from app.domain.page_normalization import fact_normalization_key
    from tests.v2.domain.test_page_observation_context import _fact
    first = _fact("2026-09-01")
    second = first.model_copy(deep=True)
    second.raw_value = "4.3"
    second.normalization_key, second.normalized_value, second.normalized_unit = fact_normalization_key(
        second.field_name, second.raw_value, context=second.context.model_dump())
    a = PageReviewRecord(**{**_review_payload(), "facts": [first]})
    b = PageReviewRecord(**{**_review_payload(), "page_review_id": "b", "lane": "main-B", "facts": [second]})
    result = reconcile_page_reviews([a, b], determination_modes={})
    pending = pending_page_observations([a, b], result)
    assert {item["review_status"] for item in pending} == {"read_value_disagreement"}
    assert not result.accepted_fact_keys


def test_handwriting_merge_winner_is_independent_of_record_order():
    """同内容键双读道一致时，胜者必须按读道优先级（main-A）确定。

    对账内容会以排序后的 page_review_ids 持久化；若胜者取决于传入顺序，
    校验器从存储重算将选到另一读道，破坏对账可复现性。
    """
    from app.domain.page_reconciliation import reconcile_page_reviews
    from app.domain.contracts.page_review import PageReviewRecord
    from tests.v2.domain.test_page_review_contracts import (
        _handwriting,
        _review_payload,
    )

    def _record(lane, page_review_id, observation_id):
        payload = {**_review_payload(),
                   "page_review_id": page_review_id,
                   "lane": lane,
                   "handwriting": [{**_handwriting().model_dump(),
                                    "observation_id": observation_id}]}
        return PageReviewRecord(**payload)

    a = _record("main-A", "page-review:aaa", "hw-A")
    b = _record("main-B", "page-review:zzz", "hw-B")
    by_lane_first = reconcile_page_reviews([a, b], determination_modes={})
    by_sorted_first = reconcile_page_reviews([b, a], determination_modes={})
    assert [h.observation_id for h in by_lane_first.accepted_handwriting] == ["hw-A"]
    assert by_lane_first.reconciliation_id == by_sorted_first.reconciliation_id
