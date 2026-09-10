import pytest
from pydantic import ValidationError

from scripts.evaluate_observation_alignment import Pair, Proposal, check_pairs, score_pairs
from app.domain.contracts.page_review import PageReviewRecord
from app.domain.contracts.page_review import ObservationContext
from tests.v2.domain.test_page_review_contracts import _review_payload


def test_experiment_rejects_generated_facts():
    with pytest.raises(ValidationError):
        Proposal.model_validate({"pairs": [], "facts": [{"value": "invented"}]})


def test_experiment_never_accepts_even_compatible_pairs():
    a = PageReviewRecord(**_review_payload())
    b = PageReviewRecord(**{**_review_payload(), "lane": "main-B"})
    pair = Pair(a=a.facts[0].observation_id, b=b.facts[0].observation_id)
    results = check_pairs(Proposal(pairs=[pair, pair, Pair(a="unknown", b=pair.b)]), a, b)
    assert all(not r["accepted"] and r["source_qc_required"] for r in results)
    assert "duplicate_pair_member" in results[0]["rejections"]
    assert "duplicate_pair_member" in results[1]["rejections"]
    assert "unknown_observation" in results[2]["rejections"]


@pytest.mark.parametrize("change,reason", [
    ({"raw_value": "5 mg/L"}, "value_or_unit_disagreement"),
    ({"raw_value": "5↑ g/L"}, "source_annotation_disagreement"),
    ({"time_text": "2025-08-09"}, "different_time"),
    ({"polarity": "negated"}, "polarity_unresolved"),
    ({"target_text": "another-object"}, "object_identity_unverified"),
])
def test_pairing_does_not_hide_conflicts(change, reason):
    a = PageReviewRecord(**_review_payload())
    context = ObservationContext(target_text="test", time_text="2025-08-08", polarity="asserted")
    fact = a.facts[0].model_copy(update={"raw_value": "5 g/L", "context": context})
    a = a.model_copy(update={"facts": [fact]})
    other = fact.model_copy(update={"raw_value": change.get("raw_value", fact.raw_value),
                                   "context": context.model_copy(update={k:v for k,v in change.items() if k != "raw_value"})})
    b = a.model_copy(update={"lane": "main-B", "facts": [other]})
    rows = check_pairs(Proposal(pairs=[Pair(a=fact.observation_id, b=other.observation_id)]), a, b)
    assert reason in rows[0]["rejections"]


def test_pairing_rejects_cross_page():
    a = PageReviewRecord(**_review_payload())
    b = a.model_copy(update={"lane": "main-B", "page_number": a.page_number + 1})
    with pytest.raises(ValueError, match="same source"):
        check_pairs(Proposal(pairs=[]), a, b)


def test_two_missing_targets_do_not_establish_identity():
    a = PageReviewRecord(**_review_payload())
    context = ObservationContext(target_text=" ", time_text="2025-08-08", polarity="asserted")
    fact = a.facts[0].model_copy(update={"context": context})
    a = a.model_copy(update={"facts": [fact]})
    b = a.model_copy(update={"lane": "main-B"})
    row = check_pairs(Proposal(pairs=[Pair(a=fact.observation_id, b=fact.observation_id)]), a, b)[0]
    assert "object_identity_unverified" in row["rejections"]
    assert row["accepted"] is False


def test_same_value_with_different_field_is_not_silently_compatible():
    a = PageReviewRecord(**_review_payload())
    other = a.facts[0].model_copy(update={"field_name": "another-field"})
    b = a.model_copy(update={"lane": "main-B", "facts": [other]})
    rows = check_pairs(Proposal(pairs=[Pair(a=a.facts[0].observation_id, b=other.observation_id)]), a, b)
    assert "field_identity_unverified" in rows[0]["rejections"]
    assert rows[0]["source_qc_required"] and not rows[0]["accepted"]


def test_scoring_counts_wrong_identity_and_duplicates_separately():
    correct = Pair(a="a1", b="b1")
    score = score_pairs(
        Proposal(pairs=[correct, correct, Pair(a="a2", b="b3")]),
        Proposal(pairs=[correct, Pair(a="a2", b="b2")]),
    )
    assert score == {
        "score_version": "field-correspondence/v2",
        "correct_pairs": 1, "wrong_pairs": 1, "missed_pairs": 1,
        "duplicate_pairs": 1, "precision": 0.5, "recall": 0.5,
        "reused_main_a_ids": ["a1"], "reused_main_b_ids": ["b1"],
        "one_to_one_correct_pairs": 0,
        "product_acceptance": False,
    }


def test_empty_negative_sample_is_not_reported_as_perfect_recall():
    score = score_pairs(Proposal(pairs=[]), Proposal(pairs=[]))
    assert score["precision"] is None and score["recall"] is None
    assert score["wrong_pairs"] == 0


def test_duplicate_gold_is_rejected():
    pair = Pair(a="a", b="b")
    with pytest.raises(ValueError, match="unique"):
        score_pairs(Proposal(pairs=[]), Proposal(pairs=[pair, pair]))


def test_distinct_pairs_reusing_one_observation_are_not_one_to_one():
    score = score_pairs(
        Proposal(pairs=[Pair(a="a1", b="b1"), Pair(a="a2", b="b1")]),
        Proposal(pairs=[Pair(a="a1", b="b1")]),
    )
    assert score["duplicate_pairs"] == 0
    assert score["reused_main_b_ids"] == ["b1"]
    assert score["correct_pairs"] == 1
    assert score["one_to_one_correct_pairs"] == 0
    assert score["product_acceptance"] is False


@pytest.mark.parametrize("pairs", [
    [Pair(a="a1", b="b1"), Pair(a="a1", b="b2")],
    [Pair(a="a1", b="b1"), Pair(a="a2", b="b1")],
])
def test_gold_rejects_reused_observation_ids(pairs):
    with pytest.raises(ValueError, match="one-to-one"):
        score_pairs(Proposal(pairs=[]), Proposal(pairs=pairs))
