"""Typed local transcriptions, never evidence qualification or OCR approval."""
from __future__ import annotations

import json
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from .common import ContractModel

LocalReadFormat = Literal["transcript", "structured_candidate", "localized_candidate"]


class LocalRegionReadItem(ContractModel):
    label: str | None
    raw_value: str | None
    raw_unit: str | None
    reference_text: str | None
    time_label: str | None
    excerpt: str = Field(min_length=1)
    position: str = Field(min_length=1)
    script: Literal["printed", "handwritten", "mixed"]
    legibility: Literal["clear", "partial", "unclear"]
    annotation_target: str | None


class LocalRegionReadCandidate(ContractModel):
    items: list[LocalRegionReadItem]
    unresolved: list[str]

    @model_validator(mode="after")
    def require_reading(self):
        if not self.items and not any(item.strip() for item in self.unresolved):
            raise ValueError("局部读取未提供可见内容或具体疑问")
        return self


class LocalRegionRelativeBox(ContractModel):
    """A proposed subregion, not a verified field location; units are 1/1000."""

    model_config = ConfigDict(extra="forbid", strict=True)

    x0: int = Field(ge=0, le=1000)
    y0: int = Field(ge=0, le=1000)
    x1: int = Field(ge=0, le=1000)
    y1: int = Field(ge=0, le=1000)

    @model_validator(mode="after")
    def require_area(self):
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("项目位置提案必须有明确面积")
        return self


class LocalizedRegionReadItem(LocalRegionReadItem):
    proposed_bbox: LocalRegionRelativeBox | None


class LocalizedRegionReadCandidate(LocalRegionReadCandidate):
    items: list[LocalizedRegionReadItem]


def local_region_read_model(read_format: LocalReadFormat):
    if read_format == "localized_candidate":
        return LocalizedRegionReadCandidate
    if read_format == "structured_candidate":
        return LocalRegionReadCandidate
    raise ValueError("此读取格式没有逐项结构")


def parse_local_region_read(
    text: str, *, source_ref: str, read_format: LocalReadFormat = "structured_candidate",
) -> LocalRegionReadCandidate:
    lines = text.strip().splitlines()
    if not lines or lines[0].strip() != "source_ref=" + source_ref:
        raise ValueError("局部读取缺少本次来源标识")
    body = "\n".join(lines[1:]).strip()
    if body.startswith("```json\n") and body.endswith("\n```"):
        body = body[len("```json\n"):-len("\n```")]
    # Do not drop unknown fields or repair incomplete output into a usable reading.
    return local_region_read_model(read_format).model_validate(json.loads(body))


def render_local_region_read(candidate: LocalRegionReadCandidate) -> str:
    lines = ["局部读取内容（尚未采用）"]
    for item in candidate.items:
        lines.append(item.excerpt + "；位置：" + item.position)
        if item.legibility != "clear":
            lines.append("此项有裁切或字迹不清，需结合原件核对。")
        if item.script != "printed" and item.annotation_target is None:
            lines.append("无法确认这处批注对应的项目。")
    lines.extend(candidate.unresolved)
    return "\n".join(lines)
