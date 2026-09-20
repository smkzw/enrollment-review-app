from typing import Literal

from pydantic import Field, model_serializer, model_validator

from .common import ContractModel
from .enums import AnchorType


class OccurrenceScope(ContractModel):
    """Source-declared counting period, separate from the numeric threshold."""

    version: Literal["occurrence-scope/v1", "occurrence-scope/v2", "occurrence-scope/v3", "occurrence-scope/v4"] = "occurrence-scope/v4"
    kind: Literal[
        "anchored_lookback", "calendar_period", "anchored_period",
        "any_consecutive", "unanchored_lookback", "unresolved",
    ]
    quantifier: Literal["single", "every", "any", "unresolved"]
    anchor_type: AnchorType | None = None
    source_excerpts: list[str] = Field(min_length=1)
    unresolved_reason: str | None = Field(default=None, min_length=1)
    start_inclusive: bool | None = None
    end_inclusive: bool | None = None
    boundary_periods: Literal["full_only", "include_partial", "unresolved"] | None = None
    calendar_week_start: Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] | None = None
    duration_basis: Literal["calendar_span", "boundary_offset", "unresolved"] | None = None

    @model_serializer(mode="wrap")
    def preserve_historical_boundaries(self, handler):
        value = handler(self)
        if self.version in {"occurrence-scope/v1", "occurrence-scope/v2"}:
            value.pop("start_inclusive", None)
            value.pop("end_inclusive", None)
        if self.version != "occurrence-scope/v4":
            value.pop("boundary_periods", None)
            value.pop("calendar_week_start", None)
            value.pop("duration_basis", None)
        return value

    @model_validator(mode="after")
    def validate_scope(self):
        if self.version in {"occurrence-scope/v1", "occurrence-scope/v2"} and (self.start_inclusive is not None or self.end_inclusive is not None):
            raise ValueError("旧频次声明不能补入未保存的起止边界")
        if self.version != "occurrence-scope/v4" and (
                self.boundary_periods is not None or self.calendar_week_start is not None or self.duration_basis is not None):
            raise ValueError("旧频次声明不能补入未保存的周期划分")
        if self.calendar_week_start is not None and self.kind != "calendar_period":
            raise ValueError("非日历期间不能套用日历周起点")
        if self.boundary_periods is not None and self.quantifier not in {"any", "every"}:
            raise ValueError("不完整周期规则仅用于多个期间的统计")
        if self.duration_basis is not None and self.kind not in {"any_consecutive", "anchored_period"}:
            raise ValueError("周期长度定义仅用于连续或锚定期间")
        if self.kind == "unanchored_lookback" and self.version == "occurrence-scope/v1":
            raise ValueError("旧频次声明不能补入未保存的应用政策范围")
        if any(not text.strip() for text in self.source_excerpts):
            raise ValueError("频次期间须保留非空的方案原文")
        if len(set(self.source_excerpts)) != len(self.source_excerpts):
            raise ValueError("频次期间的原文片段不得重复")
        unresolved = self.kind == "unresolved" or self.quantifier == "unresolved"
        if unresolved:
            if not self.unresolved_reason or not self.unresolved_reason.strip():
                raise ValueError("频次期间或量词不明时须说明具体疑问")
        elif self.unresolved_reason is not None:
            raise ValueError("已明确的频次期间不能附带未决原因")
        if self.kind in {"anchored_lookback", "anchored_period"}:
            if self.anchor_type is None:
                raise ValueError("锚定频次期间须声明方案指定的日期类型")
        elif self.anchor_type is not None:
            raise ValueError("非锚定频次期间不得擅加日期锚点")
        if self.kind == "anchored_lookback" and self.quantifier not in {"single", "unresolved"}:
            raise ValueError("单个回溯期间不能当作每个或任意期间")
        if self.kind == "unanchored_lookback" and self.quantifier != "single":
            raise ValueError("未命名回溯锚点仅用于明确的单个回溯期间")
        if self.kind == "any_consecutive" and self.quantifier not in {"any", "every", "unresolved"}:
            raise ValueError("连续期间须保留任一或每一期间的原文量词")
        return self
