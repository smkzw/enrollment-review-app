"""Deterministic normalization used before page-review reconciliation."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from datetime import date
from app.domain.publication import canonical_hash

_UNIT_RX = re.compile(
    r"(×?10\^?9/l|×?10\^?12/l|g/l|mmol/l|μmol/l|umol/l|u/l|iu/l|kua/l|"
    r"iu/ml|ng/ml|pg/ml|mg/dl|mg/l|fl|pg|%|mmhg|次/分|bpm|cm|kg|岁|周|年|"
    r"个月|天|ml|s)$",
    re.IGNORECASE,
)
_FULL_DATE_RX = re.compile(r"^(\d{4})[年/.-](\d{1,2})[月/.-](\d{1,2})日?$")
_MONTH_RX = re.compile(r"^(\d{4})[年/.-](\d{1,2})月?$")


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", "" if value is None else str(value)).strip().lower()
    return re.sub(r"\s+", "", text).replace("，", ",").replace("：", ":")


def source_arrow_marks(value: str) -> str:
    """Preserve source annotations separately from numeric normalization."""
    return "".join(character for character in value if character in "↑↓")


def normalize_field_name(
    value: object, aliases: Mapping[str, str] | None = None
) -> str:
    normalized = re.sub(r"[\s\-_：:/]+", "", normalize_text(value))
    normalized_aliases = {
        re.sub(r"[\s\-_：:/]+", "", normalize_text(key)): normalize_text(target)
        for key, target in (aliases or {}).items()
    }
    return normalized_aliases.get(normalized, normalized)


def normalize_scalar_v2(value: object) -> tuple[str, str | None]:
    """Frozen legacy decoder; never use for new observations."""
    text = normalize_text(value).replace("↑", "").replace("↓", "")
    unit_match = _UNIT_RX.search(text)
    unit = normalize_text(unit_match.group(1)) if unit_match else None
    value_text = text[: unit_match.start()] if unit_match else text

    full_date = _FULL_DATE_RX.fullmatch(value_text)
    if full_date:
        year, month, day = map(int, full_date.groups())
        return f"{year:04d}-{month:02d}-{day:02d}", unit
    month_date = _MONTH_RX.fullmatch(value_text)
    if month_date:
        year, month = map(int, month_date.groups())
        return f"{year:04d}-{month:02d}", unit
    try:
        number = Decimal(value_text)
        if not number.is_finite():
            return value_text, unit
        # Do not round source evidence to the float formatter's six significant digits.
        canonical = format(number, "f")
        if "." in canonical:
            canonical = canonical.rstrip("0").rstrip(".")
        return "0" if number.is_zero() else canonical, unit
    except InvalidOperation:
        return value_text, unit


_NUMBER_RX = re.compile(r"^(<=|>=|<|>|≤|≥)?([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)$")
_CURRENT_UNIT_RX = re.compile(_UNIT_RX.pattern.replace("×?10", "[x×]?10"), re.IGNORECASE)


def normalize_scalar_v3(value: object) -> tuple[str, str | None]:
    """Validate dates and peel units only from a complete numeric expression."""
    text = normalize_text(value)
    full_date = _FULL_DATE_RX.fullmatch(text)
    if full_date:
        return date(*map(int, full_date.groups())).isoformat(), None
    month_date = _MONTH_RX.fullmatch(text)
    if month_date:
        year, month = map(int, month_date.groups())
        date(year, month, 1)
        return f"{year:04d}-{month:02d}", None
    numeric_text = text.rstrip("↑↓")
    match = _CURRENT_UNIT_RX.search(numeric_text)
    number_text = numeric_text[:match.start()] if match else numeric_text
    number = _NUMBER_RX.fullmatch(number_text)
    if number is None:
        return text, None
    comparator, raw_number = number.groups()
    canonical, _ = normalize_scalar_v2(raw_number)
    unit = match.group(1) if match else None
    if unit and re.fullmatch(r"[x×]?10\^?(9|12)/l", unit):
        unit = "×10^" + re.search(r"(9|12)/l", unit).group(1) + "/l"
    return (comparator or "") + canonical, unit


def normalize_scalar_v4(value: object) -> tuple[str, str | None]:
    from app.domain.page_timestamp import normalize_timestamp
    timestamp = normalize_timestamp(value)
    return (timestamp, None) if timestamp is not None else normalize_scalar_v3(value)


def normalize_scalar_v5(value: object) -> tuple[str, str | None]:
    text = normalize_text(value)
    numeric_text = text.rstrip("↑↓")
    match = _CURRENT_UNIT_RX.search(numeric_text)
    if match:
        number_text = numeric_text[:match.start()]
        unmarked = number_text.rstrip("↑↓")
        if unmarked != number_text and _NUMBER_RX.fullmatch(unmarked):
            return normalize_scalar_v4(unmarked + match.group(1))
    return normalize_scalar_v4(value)


def normalize_scalar(value: object) -> tuple[str, str | None]:
    text = normalize_text(value).rstrip("↑↓")
    match = re.fullmatch(r"(.+?)[↑↓]*/(?:μ|u)l", text)
    if match and _NUMBER_RX.fullmatch(match.group(1)):
        number, _ = normalize_scalar_v4(match.group(1))
        return number, "/μl"
    return normalize_scalar_v5(value)


def fact_normalization_key(
    field_name: object,
    raw_value: object,
    *,
    aliases: Mapping[str, str] | None = None,
    legacy: bool = False,
    version3: bool = False,
    version4: bool = False,
    version5: bool = False,
    context: Mapping[str, object] | None = None,
) -> tuple[str, str, str | None]:
    field = normalize_field_name(field_name, aliases)
    scalar = normalize_scalar_v2 if legacy else normalize_scalar_v3 if version3 else normalize_scalar_v4 if version4 else normalize_scalar_v5 if version5 else normalize_scalar
    value, unit = scalar(raw_value)
    key = "|".join((field, value, unit or ""))
    if context is not None:
        key += "|context:" + observation_context_key(context, version3=version3)
    return key, value, unit


def observation_context_key(context: Mapping[str, object], *, version3: bool = False) -> str:
    normalized = {key: normalize_text(value) for key, value in context.items()}
    if context.get("time_text"):
        normalized["time_text"] = (normalize_scalar_v3 if version3 else normalize_scalar_v4)(context["time_text"])[0]
    return canonical_hash(normalized)


def handwriting_normalization_key(kind: object, raw_text: object, *, context: Mapping[str, object] | None = None, version3: bool = False) -> tuple[str, str]:
    normalized = normalize_text(raw_text)
    key = f"{normalize_text(kind)}|{normalized}"
    if context is not None:
        key += "|context:" + observation_context_key(context, version3=version3)
    return key, normalized


__all__ = [
    "fact_normalization_key",
    "handwriting_normalization_key",
    "normalize_field_name",
    "normalize_scalar",
    "normalize_text",
]
