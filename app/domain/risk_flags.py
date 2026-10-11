"""Deterministic source/value warnings. Flags do not grant source qualification."""
from __future__ import annotations

import re
from decimal import Decimal
from enum import StrEnum

from app.domain.variables.dictionary import VariableDef


class RiskFlag(StrEnum):
    NEAR_THRESHOLD = "NEAR_THRESHOLD"
    HANDWRITTEN = "HANDWRITTEN"
    LOW_OCR_CONFIDENCE = "LOW_OCR_CONFIDENCE"
    DATE_ROLE_UNCLEAR = "DATE_ROLE_UNCLEAR"
    UNIT_INFERRED = "UNIT_INFERRED"
    PARTIAL_DATE = "PARTIAL_DATE"
    PRESCRIPTION_ONLY = "PRESCRIPTION_ONLY"
    SINGLE_WEAK_SOURCE = "SINGLE_WEAK_SOURCE"
    IMPLAUSIBLE_VALUE = "IMPLAUSIBLE_VALUE"
    ATTRIBUTION_UNCERTAIN = "ATTRIBUTION_UNCERTAIN"


_NUMBER = re.compile(r"(?<![\d.])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?![\d.])")
_REFERENCE_RANGE = re.compile(r"\d+(?:\.\d+)?\s*[-–~～]\s*\d+(?:\.\d+)?")


def number_in_excerpt(value, excerpt: str) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return True
    return any(Decimal(match.group()) == Decimal(str(value)) for match in _NUMBER.finditer(excerpt))


def fact_risk_flags(candidate, definition: VariableDef | None, *, text: str,
                    low_ocr: bool = False, handwritten: bool = False,
                    weak_source: bool = False, thresholds=(), date_sensitive=False) -> list[RiskFlag]:
    flags = set(candidate.risk_flags)
    if low_ocr:
        flags.add(RiskFlag.LOW_OCR_CONFIDENCE)
    if handwritten:
        flags.add(RiskFlag.HANDWRITTEN)
    if weak_source:
        flags.add(RiskFlag.SINGLE_WEAK_SOURCE)
    if candidate.date_range is not None:
        if candidate.date_range.precision.value != "day":
            flags.add(RiskFlag.PARTIAL_DATE)
        if date_sensitive and candidate.date_role in (None, "unknown"):
            flags.add(RiskFlag.DATE_ROLE_UNCLEAR)
    value = candidate.raw_value
    if definition is not None and definition.value_type == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            converted = definition.convert(value, candidate.unit or "")
        except ValueError:
            flags.add(RiskFlag.UNIT_INFERRED)
        else:
            if not Decimal(str(definition.plausible_range[0])) <= converted <= Decimal(str(definition.plausible_range[1])):
                flags.add(RiskFlag.IMPLAUSIBLE_VALUE)
            for threshold in thresholds:
                if isinstance(threshold, (int, float)) and not isinstance(threshold, bool) and threshold:
                    if abs(converted - Decimal(str(threshold))) / abs(Decimal(str(threshold))) <= Decimal("0.05"):
                        flags.add(RiskFlag.NEAR_THRESHOLD)
        aliases = [definition.label_zh, *definition.aliases_zh]
        matching_lines = [line for line in text.splitlines() if any(alias in line for alias in aliases)
                          and number_in_excerpt(value, line)]
        if not matching_lines or all(any(number_in_excerpt(value, match.group())
                                        for match in _REFERENCE_RANGE.finditer(line)) for line in matching_lines):
            flags.add(RiskFlag.ATTRIBUTION_UNCERTAIN)
        if candidate.unit and candidate.unit != "unitless" and candidate.unit not in text:
            flags.add(RiskFlag.UNIT_INFERRED)
    return sorted(flags, key=lambda value: value.value)
