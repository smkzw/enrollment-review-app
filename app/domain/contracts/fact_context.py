"""Source-labelled semantic context, not acquisition or adoption authority."""
from __future__ import annotations

from typing import Literal, Sequence

from pydantic import Field, model_validator

from .common import ContractModel


class FactContextSourceDraft(ContractModel):
    """Separate continuous citation; it does not prove the proposed relationship."""

    locator_id: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)


class FactContextSource(FactContextSourceDraft):
    source_text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class FactContextQualifierDraft(ContractModel):
    kind: Literal["assessment", "specimen", "method", "body_site", "laterality", "other"]
    label: str = Field(min_length=1)
    source: FactContextSourceDraft | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def nonblank_label(self):
        if not self.label.strip():
            raise ValueError("事实背景须保留非空原文名称")
        return self


class FactContextQualifier(FactContextQualifierDraft):
    source: FactContextSource | None = Field(default=None, exclude_if=lambda value: value is None)


def semantic_context(qualifiers: Sequence[FactContextQualifier]) -> list[dict[str, str]]:
    """Canonical labels only: no quote/location/read count or guessed synonyms."""
    return [{"kind": kind, "label": label}
            for kind, label in sorted({(item.kind, " ".join(item.label.split())) for item in qualifiers})]


def validate_context_excerpt(qualifiers: Sequence[FactContextQualifierDraft], assertion_text: str) -> None:
    text = " ".join(assertion_text.split())
    identities = [(item.kind, " ".join(item.label.split())) for item in qualifiers]
    if len(identities) != len(set(identities)):
        raise ValueError("同一事实的背景限定不得重复")
    for item in qualifiers:
        if item.source is None:
            if " ".join(item.label.split()) not in text:
                raise ValueError("事实背景名称须逐字来自同一断言依据；不能借邻近来源补写")
        elif " ".join(item.label.split()) not in " ".join(item.source.excerpt.split()):
            raise ValueError("另处背景名称须逐字来自它自己的独立摘录")


def context_source_ids(qualifiers: Sequence[FactContextQualifierDraft]) -> set[str]:
    return {item.source.locator_id for item in qualifiers if item.source is not None}


def validate_context_source_excerpt(excerpt: str, localized_text: str | None) -> None:
    """Require one identifiable literal citation in the frozen localized source."""
    quote = " ".join(excerpt.split())
    source = " ".join((localized_text or "").split())
    if not quote or source.find(quote) < 0 or source.find(quote) != source.rfind(quote):
        raise ValueError("背景独立摘录须在当前冻结定位中连续且唯一；不能使用整页未知或拼接原文")
