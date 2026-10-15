"""As-stated count periods; an event date is not implicitly a count period."""
from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel
from .enums import AnchorType
from .rules import TimeQuantity
from .frequency_source_date import FrequencySourceDate


class FrequencyStatementPeriod(ContractModel):
    basis: Literal["explicit_dates", "anchor_relative", "unresolved"]
    start: FrequencySourceDate | None = None
    end: FrequencySourceDate | None = None
    duration: TimeQuantity | None = None
    duration_excerpt: str | None = Field(default=None, min_length=1)
    anchor_type: AnchorType | None = None
    anchor_excerpt: str | None = Field(default=None, min_length=1)
    direction: Literal["before", "after"] | None = None
    start_inclusive: bool | None = None
    end_inclusive: bool | None = None
    unresolved_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_basis(self):
        relative = (self.duration, self.duration_excerpt, self.anchor_type, self.anchor_excerpt, self.direction)
        if self.basis == "explicit_dates":
            if self.start is None or self.end is None or any(item is not None for item in relative):
                raise ValueError("明确计数期间须保留起止日期，不混入相对期间")
        elif self.basis == "anchor_relative":
            if self.start is not None or self.end is not None or any(item is None for item in relative):
                raise ValueError("相对计数期间须保留时长、方向和明确锚点原文")
            if self.anchor_type in {AnchorType.REVIEW_NODE_DATE, AnchorType.EVENT_DATE}:
                raise ValueError("病例总数不能借用审核应用政策或未指定事件作为计数锚点")
        elif any(item is not None for item in (*relative, self.start, self.end, self.start_inclusive, self.end_inclusive)):
            raise ValueError("未决计数期间不能夹带推测的日期界限")
        if self.basis == "unresolved":
            if not self.unresolved_reason or not self.unresolved_reason.strip():
                raise ValueError("计数期间未核清须保留具体疑问")
        elif self.unresolved_reason is not None:
            raise ValueError("结构化计数期间不能同时标作未决")
        for text in (self.duration_excerpt, self.anchor_excerpt):
            if text is not None and not text.strip():
                raise ValueError("计数期间依据不得为空白")
        return self

    def source_quotes(self):
        return [value for value in (
            self.start.excerpt if self.start is not None else None,
            self.end.excerpt if self.end is not None else None,
            self.duration_excerpt, self.anchor_excerpt,
        ) if value is not None]
