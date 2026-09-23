"""Protocol-declared observation policy, never a claim of evidence completeness."""
from typing import Literal

from pydantic import ConfigDict, Field, model_serializer, model_validator

from .common import ContractModel


class OrderedObservationExclusion(ContractModel):
    fact_id: str = Field(min_length=1)
    reason: Literal["not_governing_observation", "observation_out_of_window"]


class OrderedObservationAudit(ContractModel):
    policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    accounting_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scope: Literal["supplied_facts_only"] = "supplied_facts_only"
    selected_fact_ids: list[str] = Field(default_factory=list)
    not_selected: list[OrderedObservationExclusion] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def preserve_missing_selection(self, handler):
        value = handler(self)
        if "selected_fact_ids" not in self.model_fields_set:
            value.pop("selected_fact_ids", None)
        return value

    @model_validator(mode="after")
    def validate_exclusions(self):
        ids = [item.fact_id for item in self.not_selected]
        if len(ids) != len(set(ids)):
            raise ValueError("未采用的观察记录不得重复")
        if (len(self.selected_fact_ids) != len(set(self.selected_fact_ids))
                or any(not item.strip() for item in self.selected_fact_ids)
                or set(ids).intersection(self.selected_fact_ids)):
            raise ValueError("已采用和未采用的观察记录必须明确区分且不得重复")
        return self


class ObservationOrdering(ContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    criterion: Literal["latest", "earliest"]
    ordering_attribute: Literal["date_range"]
    window_order: Literal["not_applicable", "within_window", "before_window_check", "unresolved"] | None = None

    @classmethod
    def provider_json_schema(cls):
        schema = cls.model_json_schema()
        schema["required"] = list(schema["properties"])
        schema["properties"]["window_order"] = {"type": "string", "enum": [
            "not_applicable", "within_window", "before_window_check", "unresolved",
        ]}
        return schema

    @model_serializer(mode="wrap")
    def serialize_window_order(self, handler):
        value = handler(self)
        if self.window_order is None:
            value.pop("window_order", None)
        return value


class ObservationPolicy(ContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    mode: Literal["single", "any", "all", "unresolved"]
    scope: str = Field(min_length=1)
    source_span_ids: list[str] = Field(min_length=1)
    source_excerpts: list[str] = Field(min_length=1)
    selection: ObservationOrdering | None = None

    @model_serializer(mode="wrap")
    def serialize_selection(self, handler):
        value = handler(self)
        if self.selection is None:
            value.pop("selection", None)
        return value

    @model_validator(mode="after")
    def validate_policy(self):
        if (len(self.source_span_ids) != len(self.source_excerpts)
                or len(set(zip(self.source_span_ids, self.source_excerpts))) != len(self.source_span_ids)):
            raise ValueError("观察选择的来源须逐项对应且不得重复")
        if any(not value.strip() for value in (self.scope, *self.source_span_ids, *self.source_excerpts)):
            raise ValueError("观察选择范围和原文不得为空白")
        if self.selection is not None and self.mode != "single":
            raise ValueError("最近或最早观察选择只适用于方案明确要求采用单项结果的条件")
        return self


def validate_observation_window_order(policy, *, has_time_constraint: bool, require_explicit: bool = False):
    if policy is None or policy.selection is None:
        return
    order = policy.selection.window_order
    if order is None:
        if require_explicit:
            raise ValueError("须明确选取记录与核对时间范围的先后顺序；原文不明时保留未核实")
        return
    if order != "unresolved" and has_time_constraint == (order == "not_applicable"):
        raise ValueError("检查选择的时间顺序与所声明的时间约束不一致")
