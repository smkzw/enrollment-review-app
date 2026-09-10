"""Conservative isolated scoring after explicit source/field/context projection.

This does not infer aliases, clinical meaning or dates from free-text model output.
It is not a replacement for adjudicated gold or clinical acceptance.
"""

from collections import Counter

from pydantic import BaseModel, ConfigDict, Field

from app.domain.page_normalization import normalize_scalar, normalize_text, source_arrow_marks


class ScoredFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    fact_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    field_id: str = Field(min_length=1)
    context_id: str = Field(min_length=1)
    polarity: str = Field(min_length=1)
    raw_value: str = Field(min_length=1)
    unit: str

    def key(self):
        value, embedded_unit = normalize_scalar(self.raw_value)
        unit = normalize_text(self.unit)
        if embedded_unit and unit and normalize_text(embedded_unit) != unit:
            raise ValueError("Conflicting embedded and explicit units")
        return (self.project_id, self.subject_id, self.image_sha256, self.field_id,
                self.context_id, self.polarity, value, unit or embedded_unit or "",
                source_arrow_marks(self.raw_value))


def score(gold: list[ScoredFact], predicted: list[ScoredFact]):
    for records in (gold, predicted):
        if len({record.fact_id for record in records}) != len(records):
            raise ValueError("Duplicate fact IDs")
    expected = {record.key(): record.fact_id for record in gold}
    if len(expected) != len(gold):
        raise ValueError("Duplicate gold keys require adjudication")
    actual = Counter(record.key() for record in predicted)
    matched = set(expected).intersection(actual)
    return {
        "scope": "exact_projected_fact_keys_only",
        "matched_gold_ids": sorted(expected[key] for key in matched),
        "missed_gold_ids": sorted(expected[key] for key in set(expected) - matched),
        "unmatched_prediction_ids": sorted(record.fact_id for record in predicted
                                           if record.key() not in expected),
        "duplicate_prediction_count": sum(count - 1 for count in actual.values()),
        "gold_count": len(gold), "prediction_count": len(predicted),
        "recall": len(matched) / len(gold) if gold else None,
        "precision": len(matched) / len(predicted) if predicted else None,
        "clinical_acceptance": False,
    }
