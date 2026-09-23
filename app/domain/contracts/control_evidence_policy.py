"""Explicit source restrictions, separate from clinical lookback/obligation logic."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel
from .rules import TimeConstraint


class ControlEvidenceSourcePolicy(ContractModel):
    # None means unresolved, never the legacy template's permissive default.
    requires_contemporaneous_objective_source: bool | None = Field(...)
    allows_screening_record_transcription: bool | None = Field(...)
    result_validity_status: Literal["specified", "not_specified", "unknown"]
    result_validity_constraint: TimeConstraint | None = Field(...)
    source_span_ids: list[str] = Field(min_length=1)
    source_excerpts: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_policy(self) -> "ControlEvidenceSourcePolicy":
        if (self.result_validity_status == "specified") != (self.result_validity_constraint is not None):
            raise ValueError("明确的结果有效期必须保留完整时间约束，未明确时不得补造期限")
        if len(self.source_span_ids) != len(self.source_excerpts):
            raise ValueError("资料来源要求须逐项保留原文位置与摘录")
        if any(not value.strip() for value in [*self.source_span_ids, *self.source_excerpts]):
            raise ValueError("资料来源要求的原文位置与摘录不得为空")
        if len(set(zip(self.source_span_ids, self.source_excerpts))) != len(self.source_span_ids):
            raise ValueError("资料来源要求的原文位置与摘录不得成对重复")
        return self
