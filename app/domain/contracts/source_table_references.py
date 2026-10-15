"""Physical table-reference closure; reading a table does not adopt its meaning."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from .protocol_controls import ProtocolStructureUnit

_TABLE_ROW_REF = re.compile(r"^(?P<table>.+?)\.r\d+(?:\.c\d+)?(?:\.p\d+)?$")
_PART = r"[0-9０-９一二三四五六七八九十百]+"
_NUMBER = rf"{_PART}(?:\s*[.．\-－—–]\s*{_PART})*"
_TABLE_TITLE_NUMBER_RE = re.compile(rf"(?:表格?|table)\s*(?P<number>{_NUMBER})", re.IGNORECASE)
_TABLE_REFERENCE_RE = re.compile(
    rf"(?:参见|详见|(?<![\w])见|(?<![a-z])refer(?:\s+to)?|(?<![a-z])see)\s*(?:第\s*)?"
    rf"(?:表格?|table)\s*(?P<number>{_NUMBER})"
    rf"(?![0-9０-９一二三四五六七八九十百]|\s*[.．\-－—–]\s*{_PART})",
    re.IGNORECASE,
)


def normalize_reference_number(value: str) -> str:
    value = value.strip()
    value = value.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    parts = re.split(r"([.．\-－—–])", value)
    if len(parts) > 1:
        return "".join(normalize_reference_number(part) if index % 2 == 0
                       else ("." if part in {".", "．"} else "-")
                       for index, part in enumerate(parts))
    if value.isdigit():
        return str(int(value))
    if value == "十":
        return "10"
    if value == "百":
        return "100"
    chinese = dict(zip("一二三四五六七八九", range(1, 10)))
    if value in chinese:
        return str(chinese[value])
    if len(value) == 2 and value[0] == "十" and value[1] in chinese:
        return str(10 + chinese[value[1]])
    if len(value) == 2 and value[1] == "十" and value[0] in chinese:
        return str(chinese[value[0]] * 10)
    return value.casefold()


def table_number(unit: ProtocolStructureUnit) -> str | None:
    for value in (*unit.heading_path, unit.excerpt):
        match = _TABLE_TITLE_NUMBER_RE.search(value)
        if match:
            return normalize_reference_number(match.group("number"))
    return None


def table_key(unit: ProtocolStructureUnit) -> tuple[str, str] | None:
    if unit.table_context is None:
        return None
    for source_ref in (unit.source_ref, *unit.member_source_refs):
        match = _TABLE_ROW_REF.match(source_ref)
        if match:
            return ("source", match.group("table"))
    outer_path = tuple(unit.table_context.table_path[:-2])
    if outer_path:
        return ("path", ",".join(str(value) for value in outer_path))
    return ("heading", "\x1f".join(unit.heading_path))


def explicit_table_reference_context(
    source: ProtocolStructureUnit,
    units: Sequence[ProtocolStructureUnit],
) -> tuple[str, ...]:
    """Select unique numbered physical tables, not similar prose or nearby phases."""
    referenced = {
        normalize_reference_number(match.group("number"))
        for match in _TABLE_REFERENCE_RE.finditer(source.excerpt)
    }
    if not referenced:
        return ()
    numbers_by_key: dict[tuple[str, str], set[str]] = defaultdict(set)
    for unit in units:
        key = table_key(unit)
        # Only physical source coordinates can authorize non-control context.
        if key is None or key[0] != "source" or not unit.heading_path:
            continue
        title = unit.heading_path[-1].strip()
        match = _TABLE_TITLE_NUMBER_RE.match(title)
        if match is not None and not re.match(rf"\s*[.．\-－—–]\s*{_PART}", title[match.end():]):
            numbers_by_key[key].add(normalize_reference_number(match.group("number")))
    selected_keys = set()
    for number in referenced:
        keys = [key for key, numbers in numbers_by_key.items() if number in numbers]
        if len(keys) == 1 and numbers_by_key[keys[0]] == {number}:
            selected_keys.add(keys[0])
    return tuple(
        unit.structure_unit_id
        for unit in sorted(units, key=lambda item: (item.source_order, item.structure_unit_id))
        if unit.structure_unit_id != source.structure_unit_id
        and table_key(unit) in selected_keys
    )


def has_explicit_table_reference(unit: ProtocolStructureUnit) -> bool:
    return _TABLE_REFERENCE_RE.search(unit.excerpt) is not None
