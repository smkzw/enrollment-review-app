"""Serializable calculation evidence, independent of evaluator implementation."""
from typing import Any

from pydantic import Field, model_validator

from .common import ContractModel, ScalarValue
from .enums import TruthValue
from app.domain.publication import canonical_hash


class EvaluationResult(ContractModel):
    truth: TruthValue
    reason_codes: list[str] = Field(default_factory=list)
    used_fact_ids: list[str] = Field(default_factory=list)
    observed_value: ScalarValue | None = None
    observed_unit: str | None = None
    evidence_span_ids: list[str] = Field(default_factory=list)


class FrequencyAtomEvaluation(ContractModel):
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    atom_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    resolution_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_fact_ids: list[str]
    result: EvaluationResult
    resolution: dict[str, Any]

    @property
    def evidence_fact_ids(self) -> set[str]:
        return set(self.source_fact_ids)

    @model_validator(mode="after")
    def validate_material(self):
        calculations = [self.resolution, *(row["calculation"] for row in self.resolution.get("period_results", ()))]
        references = {item["fact_id"] for calculation in calculations for item in calculation.get("statement_sources", ())}
        references.update(key for calculation in calculations
                          for key in EvaluationResult.model_validate(calculation["result"]).used_fact_ids)
        if (self.resolution_sha256 != canonical_hash(self.resolution)
                or EvaluationResult.model_validate(self.resolution["result"]) != self.result
                or len(set(self.source_fact_ids)) != len(self.source_fact_ids)
                or not set(self.result.used_fact_ids) <= set(self.source_fact_ids)
                or not references <= set(self.source_fact_ids)):
            raise ValueError("频次结果与冻结来源或计算依据不一致")
        return self


class RepeatAtomEvaluation(ContractModel):
    """Source-bound arithmetic; publication rebuilds it from verified receipts."""
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    atom_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    resolution_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_fact_ids: list[str]
    result: EvaluationResult
    resolution: dict[str, Any]
    numeric_result: dict[str, Any] | None = None

    @property
    def evidence_fact_ids(self) -> set[str]:
        results = [value for row in self.resolution.get("repeat_checks", ())
                   for value in row.get("checks", {}).values()]
        if self.resolution.get("absence_trigger") is not None:
            results.append(self.resolution["absence_trigger"])
        results.extend(row["absence_trigger"] for row in
                       (self.resolution.get("multi_initial_selection") or {}).get("chains", ())
                       if row.get("absence_trigger") is not None)
        frequency_sources = {key for row in self.resolution.get("condition_frequency_evaluations", ())
                             for value in row["evaluations"].values()
                             for key in FrequencyAtomEvaluation.model_validate(value).evidence_fact_ids}
        return set(self.source_fact_ids) | frequency_sources | {
            key for raw in results for key in EvaluationResult.model_validate(raw).used_fact_ids
        }

    @model_validator(mode="after")
    def validate_material(self):
        if (self.resolution_sha256 != canonical_hash(self.resolution)
                or len(set(self.source_fact_ids)) != len(self.source_fact_ids)
                or not set(self.result.used_fact_ids) <= set(self.source_fact_ids)):
            raise ValueError("复查结果与其来源或计算依据不一致")
        return self
