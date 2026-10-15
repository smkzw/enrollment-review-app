"""Source descriptions of calculation inputs, not calculation/adoption authority."""
from typing import Literal

from pydantic import Field, model_validator

from app.domain.publication import canonical_hash
from .binding_qualification import BindingQualificationPairContext
from .common import ContractModel
from .source_computation import SourceComputation, SourceQuote

VERSION = "computation-input/v2"


def computation_for_condition(condition: dict) -> SourceComputation | None:
    predicate = condition.get("predicate")
    if predicate is None:
        evaluation = (condition.get("atom") or {}).get("evaluation") or {}
        predicate = evaluation.get("predicate")
    raw = (predicate or {}).get("source_computation")
    return None if raw is None else SourceComputation.model_validate(raw)


class ComputationInputContext(ContractModel):
    version: Literal["computation-input/v2"] = VERSION
    pair_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_job_id: str = Field(min_length=1)
    frozen_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    computation: SourceComputation
    members: list[BindingQualificationPairContext] = Field(min_length=1)

    @property
    def source_members(self):
        return self.members

    @model_validator(mode="after")
    def same_frozen_scope(self):
        if [item.pair_id for item in self.members] != sorted({item.pair_id for item in self.members}):
            raise ValueError("计算输入原文配对须完整排序且不得重复")
        first = self.members[0]
        for member in self.members:
            if ((member.identity_sha256, member.candidate_job_id, member.frozen_input_sha256)
                    != (self.identity_sha256, self.candidate_job_id, self.frozen_input_sha256)
                    or any(getattr(member, key) != getattr(first, key) for key in (
                        "condition", "episode", "parent_source_context", "comparison_sha256",
                        "candidate_family", "identity_field"))
                    or computation_for_condition(member.condition) != self.computation):
                raise ValueError("计算输入不能混入其他要求、节点或方案声明")
        for identity, content in (("fact_id", "fact"), ("locator_id", "locator")):
            seen = {}
            for member in self.members:
                key, value = getattr(member, identity), getattr(member, content)
                if key in seen and seen[key] != value:
                    raise ValueError("同一来源身份存在不同内容，不能覆盖后继续核实")
                seen[key] = value
        if self.pair_id != canonical_hash(self.model_dump(mode="json", exclude={"pair_id"})):
            raise ValueError("计算输入身份与实际原文范围不一致")
        return self


class ComputationSourceDescription(ContractModel):
    pair_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_role: Literal["raw_input", "context_only", "unresolved"] = "unresolved"
    input_excerpt: str | None = Field(default=None, min_length=1)
    input_ref: SourceQuote | None = None
    collection_token: str | None = Field(default=None, min_length=1)
    token_kind: Literal["collection_identifier", "explicit_collection_ordinal", "unresolved"]
    collection_excerpt: str | None = Field(default=None, min_length=1)
    date_role: Literal["collection_time", "report_time", "record_time", "unresolved"]
    date_text: str | None = Field(default=None, min_length=1)
    date_excerpt: str | None = Field(default=None, min_length=1)
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def explicit_source_or_unknown(self):
        if self.input_role == "unresolved":
            if self.input_excerpt is not None or self.input_ref is not None:
                raise ValueError("输入归属未核清时不得补入已确定的对应依据")
        elif self.input_excerpt is None or self.input_ref is None:
            raise ValueError("输入或背景的对应关系须保留病例和方案两端依据")
        for role, fields in ((self.token_kind, (self.collection_token, self.collection_excerpt)),
                             (self.date_role, (self.date_text, self.date_excerpt))):
            if role == "unresolved":
                if any(value is not None for value in fields):
                    raise ValueError("未核清时不能补入已确定的采集标识或日期")
            elif any(value is None or not value.strip() for value in fields):
                raise ValueError("明确采集身份或日期角色须附本条原文依据")
        if not self.explanation.strip():
            raise ValueError("输入来源说明不得为空白")
        return self


class ComputationSourceRelation(ContractModel):
    left_pair_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    right_pair_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    relation: Literal["same_acquisition", "distinct_acquisition"]
    left_excerpt: str = Field(min_length=1)
    right_excerpt: str = Field(min_length=1)
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def different_sources(self):
        if self.left_pair_id == self.right_pair_id or any(not value.strip() for value in (
                self.left_excerpt, self.right_excerpt, self.explanation)):
            raise ValueError("采集关系须指向不同原文并保留两端说明")
        return self

    def agreement_key(self):
        return self.relation, *sorted((self.left_pair_id, self.right_pair_id))


class ComputationInputResult(ContractModel):
    pair_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    descriptions: list[ComputationSourceDescription]
    relations: list[ComputationSourceRelation]
    unresolved_notes: list[str]

    @model_validator(mode="after")
    def unique_records(self):
        if [item.pair_id for item in self.descriptions] != sorted({item.pair_id for item in self.descriptions}):
            raise ValueError("计算输入须逐处核对，不得合并后漏掉原文")
        keys = [item.agreement_key() for item in self.relations]
        if len(keys) != len(set(keys)):
            raise ValueError("同一采集关系不得重复声明")
        return self


class ComputationInputPayload(ContractModel):
    results: list[ComputationInputResult]

    @model_validator(mode="after")
    def unique_groups(self):
        if len({item.pair_id for item in self.results}) != len(self.results):
            raise ValueError("计算输入结果不得重复对应要求")
        return self
