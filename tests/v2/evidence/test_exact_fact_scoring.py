import pytest

from scripts.score_exact_fact_keys import ScoredFact, score


def fact():
    return ScoredFact.model_validate(dict(
        fact_id="g1", project_id="study", subject_id="subject", image_sha256="a" * 64,
        field_id="field", context_id="blood:collection:2026-01-01", polarity="affirmed",
        raw_value="0", unit="g/l",
    ))


@pytest.mark.parametrize("field,value", [
    ("project_id", "another-study"), ("subject_id", "other-subject"),
    ("image_sha256", "b" * 64), ("field_id", "unrelated-field"),
    ("context_id", "urine:collection:2026-01-01"),
    ("context_id", "blood:collection:2025-01-01"),
    ("context_id", "blood:report:2026-01-01"), ("polarity", "negated"),
    ("unit", "mg/l"), ("raw_value", "<0"), ("raw_value", "0↑"),
])
def test_same_number_does_not_match_other_fact(field, value):
    gold = fact()
    predicted = ScoredFact.model_validate({**gold.model_dump(), "fact_id": "p1", field: value})
    assert score([gold], [predicted])["recall"] == 0


def test_zero_normalization_and_duplicate_predictions():
    gold = fact()
    data = gold.model_dump()
    predicted = [ScoredFact.model_validate({**data, "fact_id": name, "raw_value": "０.００"})
                 for name in ("p1", "p2")]
    result = score([gold], predicted)
    assert result["recall"] == 1
    assert result["precision"] == 0.5
    assert result["duplicate_prediction_count"] == 1
    assert not result["clinical_acceptance"]
    assert score([], [])["recall"] is None


def test_invalid_units_and_ambiguous_gold_are_not_silently_scored():
    gold = fact()
    duplicate = ScoredFact.model_validate({**gold.model_dump(), "fact_id": "g2"})
    with pytest.raises(ValueError, match="Duplicate gold"):
        score([gold, duplicate], [])
    with pytest.raises(ValueError, match="Duplicate fact IDs"):
        score([gold, gold], [])
    bad = ScoredFact.model_validate({**gold.model_dump(), "raw_value": "0 mg/l"})
    with pytest.raises(ValueError, match="Conflicting"):
        score([bad], [])
