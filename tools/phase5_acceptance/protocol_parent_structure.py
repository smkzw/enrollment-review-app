"""Project-neutral structural fingerprints for protocol acceptance sampling.

This module selects read-only acceptance samples. It does not interpret a
clinical rule, generate a rule draft, or participate in product decisions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from app.domain.contracts.protocol_ingestion import (
    FrozenCatalogItem,
    ProtocolSourceSpan,
)


_ENUMERATION = re.compile(r"(?:^|[\n；;。])\s*(?:\d+[.、)]|[（(][一二三四五六七八九十]+[）)])")
_NUMERIC_THRESHOLD = re.compile(r"(?:≥|≤|>|<|=|不低于|不高于|至少|至多)\s*\d")
_TEMPORAL_WINDOW = re.compile(r"\d+(?:\.\d+)?\s*(?:天|日|周|星期|个月|月|年|半衰期)")
_DISJUNCTION = re.compile(r"(?:和/或|及/或|或者|任一|任何一项|至少一项|或)")
_CONJUNCTION = re.compile(r"(?:并且|同时|以及|均须|均应|且)")
_EXCEPTION = re.compile(r"(?:除外|除非|例外|但不包括)")
_JUDGMENT = re.compile(r"研究者[^，；。\n]{0,12}(?:评估|评定|判断|判定|认为|认定|确认|决定)")
_REVIEW_MILESTONE = re.compile(r"(?:预筛|筛选|导入|基线|随机|首次给药|首剂)")
_FUTURE_PLAN = re.compile(r"(?:计划|研究期间|治疗期间|研究完成后|研究结束后)")
_NEGATION = re.compile(r"(?:无|否认|未见|未发现|未发生|不得|不能|禁止)")
_PARENT_LEAD_IN = re.compile(r"[:：]\s*$", re.MULTILINE)

ACCEPTANCE_CHALLENGE_FEATURES = frozenset(
    {
        "logic:disjunction",
        "logic:conjunction",
        "logic:exception",
        "condition:numeric-threshold",
        "condition:temporal-window",
        "condition:professional-judgment",
        "condition:review-milestone",
        "condition:future-plan",
        "condition:negation",
    }
)


@dataclass(frozen=True)
class ParentStructureFingerprint:
    official_code: str
    features: frozenset[str]


@dataclass(frozen=True)
class ParentStructureSelection:
    selected: ParentStructureFingerprint
    minimum_distance: float
    distances: tuple[tuple[str, float], ...]


def fingerprint_parent_rule(
    item: FrozenCatalogItem,
    *,
    source_text_by_id: Mapping[str, str],
    source_spans: Mapping[str, ProtocolSourceSpan] | None = None,
) -> ParentStructureFingerprint:
    """Describe only generic shape signals visible in frozen source blocks."""

    texts = [source_text_by_id.get(span_id, "") for span_id in item.source_span_ids]
    text = "\n".join(part for part in texts if part)
    features = {
        "source:single" if len(item.source_span_ids) == 1 else "source:multiple",
        "body:enumerated" if _ENUMERATION.search(text) else "body:continuous",
    }
    if source_spans is not None:
        table_flags = [
            bool(source_spans.get(span_id) and source_spans[span_id].table_path)
            for span_id in item.source_span_ids
        ]
        if any(table_flags):
            features.add("source:table")
        if table_flags and not all(table_flags):
            features.add("source:mixed-layout")

    signals = (
        ("logic:disjunction", _DISJUNCTION),
        ("logic:conjunction", _CONJUNCTION),
        ("logic:exception", _EXCEPTION),
        ("condition:numeric-threshold", _NUMERIC_THRESHOLD),
        ("condition:temporal-window", _TEMPORAL_WINDOW),
        ("condition:professional-judgment", _JUDGMENT),
        ("condition:review-milestone", _REVIEW_MILESTONE),
        ("condition:future-plan", _FUTURE_PLAN),
        ("condition:negation", _NEGATION),
        ("body:parent-lead-in", _PARENT_LEAD_IN),
    )
    features.update(name for name, pattern in signals if pattern.search(text))
    if not any(name.startswith("condition:") for name in features):
        features.add("condition:qualitative")
    return ParentStructureFingerprint(
        official_code=item.official_code or item.item_id,
        features=frozenset(features),
    )


def structural_distance(
    left: ParentStructureFingerprint,
    right: ParentStructureFingerprint,
) -> float:
    """Return unweighted Jaccard distance over declared structural signals."""

    union = left.features | right.features
    if not union:
        return 0.0
    return len(left.features ^ right.features) / len(union)


def has_minimum_acceptance_challenge(
    fingerprint: ParentStructureFingerprint,
) -> bool:
    """Reject structurally trivial samples before distance-based selection."""

    return bool(fingerprint.features & ACCEPTANCE_CHALLENGE_FEATURES)


def select_most_structurally_distinct(
    candidates: Iterable[ParentStructureFingerprint],
    *,
    references: Sequence[ParentStructureFingerprint],
) -> ParentStructureSelection:
    """Choose the candidate farthest from its nearest previously tested rule."""

    if not references:
        raise ValueError("至少需要一个已测父规则结构作为参照")
    evaluated: list[ParentStructureSelection] = []
    for candidate in candidates:
        distances = tuple(
            (reference.official_code, structural_distance(candidate, reference))
            for reference in references
        )
        evaluated.append(
            ParentStructureSelection(
                selected=candidate,
                minimum_distance=min(distance for _code, distance in distances),
                distances=distances,
            )
        )
    if not evaluated:
        raise ValueError("没有可供选择的冻结父规则")
    return sorted(
        evaluated,
        key=lambda item: (-item.minimum_distance, item.selected.official_code),
    )[0]
