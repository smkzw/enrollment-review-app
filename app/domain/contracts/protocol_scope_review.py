"""Source-bound review of an official heading's relationship to its children."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, StrictBool, model_validator

from .common import ContractModel
from .enums import ReviewStage


class ScopeCitation(ContractModel):
    source_span_id: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)


class PredicateScopeAssignment(ContractModel):
    predicate_id: str = Field(min_length=1)
    required_stages: list[ReviewStage]
    citations: list[ScopeCitation] = Field(min_length=1)


class HeadingScopeDisposition(ContractModel):
    source_span_id: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    disposition: Literal["shared_constraint", "node_overview", "context_only", "unresolved"]
    finding: str = Field(min_length=1)
    supporting_citations: list[ScopeCitation] = Field(min_length=1)


class OfficialScopeItem(ContractModel):
    component_id: str = Field(min_length=1)
    relation: Literal["governing", "separate_nodes", "context_only", "unresolved"]
    required_stages: list[ReviewStage]
    citations: list[ScopeCitation] = Field(min_length=1)
    predicate_assignments: list[PredicateScopeAssignment] = Field(min_length=1)
    heading_dispositions: list[HeadingScopeDisposition] = Field(min_length=1)
    unresolved_dimensions: list[str]
    proposal_agreement: StrictBool | None

    @model_validator(mode="after")
    def validate_result(self):
        if any(not value.strip() for value in self.unresolved_dimensions):
            raise ValueError("未核清的问题不能为空")
        if any(not item.finding.strip() for item in self.heading_dispositions):
            raise ValueError("总标题作用范围须有可核查的公开说明")
        if len(self.required_stages) != len(set(self.required_stages)):
            raise ValueError("审核节点不能重复")
        if self.relation == "unresolved" and not self.unresolved_dimensions:
            raise ValueError("未核清的关系必须说明具体问题")
        if self.relation != "unresolved" and self.unresolved_dimensions:
            raise ValueError("关系仍有疑问时不能标为已核清")
        if self.relation != "unresolved" and (
            not self.required_stages or any(not item.required_stages for item in self.predicate_assignments)
        ):
            raise ValueError("已核清的条件须逐项说明实际审核节点")
        return self


class OfficialScopeReading(ContractModel):
    items: list[OfficialScopeItem] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_targets(self):
        ids = [item.component_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("总标题核对不能重复子项")
        return self
