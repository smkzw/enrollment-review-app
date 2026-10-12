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


_NUMBER = re.compile(r"(?<![\d.])(?:(?<!\d)[-+])?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?![\d.])")
_REFERENCE_RANGE = re.compile(r"\d+(?:\.\d+)?\s*(?:--?|[–~～])\s*\d+(?:\.\d+)?")


def number_in_excerpt(value, excerpt: str) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return True
    return any(Decimal(match.group()) == Decimal(str(value)) for match in _NUMBER.finditer(excerpt))


def same_numeric_reading(raw, normalized) -> bool:
    """A literal number string and JSON number may agree; no unit/value inference."""
    import unicodedata
    if isinstance(raw, bool) or isinstance(normalized, bool) or not isinstance(normalized, (int, float)):
        return False
    literal = unicodedata.normalize("NFKC", str(raw)).strip()
    return bool(_NUMBER.fullmatch(literal)) and Decimal(literal) == Decimal(str(normalized))


def reference_upper_bound(fact) -> Decimal:
    """A range is usable only with its measurement in one literal source row."""
    import unicodedata
    basis = fact.assertion_basis
    if basis is None:
        raise ValueError("参考范围没有原文依据")
    ranges = [item for item in basis.contextual_qualifiers if item.kind == "reference_range"]
    if len(ranges) != 1 or ranges[0].source is not None:
        raise ValueError("本项须有同一原句内唯一的参考范围，不能借用另处记录")
    original = ranges[0].label
    rows = [line for line in basis.assertion_text.splitlines()
            if basis.asserted_object in line and original in line]
    if len(rows) != 1 or rows[0].count(original) != 1:
        raise ValueError("参考范围与项目读数没有唯一同排对应")
    row = rows[0]
    start = row.index(original)
    remainder = row[:start] + " " * len(original) + row[start + len(original):]
    reading = getattr(fact, "value", getattr(fact, "canonical_value", None))
    if not isinstance(reading, (int, float)) or isinstance(reading, bool) or not number_in_excerpt(reading, remainder):
        raise ValueError("项目读数不能取自参考范围内")
    normalize = lambda value: unicodedata.normalize("NFKC", value).replace(" ", "").replace("µ", "μ")
    field = row.split(basis.asserted_object, 1)[1].lstrip(" \t:：=↑↓")
    value_match = _NUMBER.match(field)
    if value_match is None or Decimal(value_match.group()) != Decimal(str(reading)):
        raise ValueError("原始结果必须紧随同一项目，不能取邻列数字")
    range_start = field.find(original)
    if range_start < value_match.end():
        raise ValueError("结果与参考范围的列顺序不明确")
    middle = normalize(field[value_match.end():range_start]).strip("↑↓")
    suffix = normalize(field[range_start + len(original):]).strip("↑↓")
    unit = normalize(getattr(fact, "unit", None) or "")
    text = normalize(original)
    range_has_unit = bool(unit and text.endswith(unit))
    if not unit or middle not in {"", unit} or suffix not in {"", unit} or not (range_has_unit or unit in {middle, suffix}):
        raise ValueError("同一行的结果、参考范围和单位关系不明确")
    if range_has_unit:
        text = text[:-len(unit)]
    number = r"\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
    match = re.fullmatch(rf"({number})(?:--?|[–~～])({number})|[<≤]({number})", text)
    if match is None:
        raise ValueError("参考范围未明确提供可计算的上限")
    upper = Decimal(match[2] or match[3])
    if not upper.is_finite() or upper <= 0 or match[1] and Decimal(match[1]) >= upper:
        raise ValueError("参考上限无效")
    return upper


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
    value = candidate.canonical_value
    if definition is not None and definition.value_type == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            converted = definition.convert(value, candidate.unit or "")
        except ValueError:
            flags.add(RiskFlag.UNIT_INFERRED)
        else:
            if not Decimal(str(definition.plausible_range[0])) <= converted <= Decimal(str(definition.plausible_range[1])):
                flags.add(RiskFlag.IMPLAUSIBLE_VALUE)
            for threshold in thresholds:
                if isinstance(threshold, (int, float, Decimal)) and not isinstance(threshold, bool) and threshold:
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
