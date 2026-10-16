"""Quoted field interpretations, not a caller-supplied verification switch."""
from __future__ import annotations

import calendar
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import Field

from .common import ContractModel


class MedicationFieldSourceDraft(ContractModel):
    field: Literal["medication_name", "start_range", "end_range", "record_time", "duration_status",
                   "dose", "unit", "frequency", "route"]
    role: Literal["actual_use", "use_start", "use_end", "single_use", "recorded_at", "use_detail",
                  "status_ended", "status_ongoing", "status_single", "status_intermittent", "status_unknown"]
    locator_id: str = Field(min_length=1)
    locator_ids: list[str] = Field(default_factory=list, exclude_if=lambda value: not value)
    object_text: str = Field(min_length=1)
    value_text: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)


class MedicationFieldSource(MedicationFieldSourceDraft):
    source_text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def source_date_bounds(text: str):
    """Parse written calendar parts only; UK never becomes a guessed day."""
    normalized = unicodedata.normalize("NFKC", text).strip()
    for separator in ("年", "月", ".", "/"):
        normalized = normalized.replace(separator, "-")
    parts = normalized.removesuffix("日").strip("-").split("-")
    if not 1 <= len(parts) <= 3 or len(parts[0]) != 4 or not parts[0].isdigit():
        raise ValueError("用药日期原文不是明确的年、年月或日期")
    known = []
    unknown = False
    for part in parts:
        if part.casefold() == "uk":
            unknown = True
        elif unknown or not part.isdigit():
            raise ValueError("不能补全未知日期或从日期说明中猜日期")
        else:
            known.append(int(part))
    year = known[0]
    if len(known) == 1:
        return "year", date(year, 1, 1), date(year, 12, 31)
    month = known[1]
    if len(known) == 2:
        return "month", date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    day = date(year, month, known[2])
    return "day", day, day


def medication_field_source_errors(candidate) -> list[str]:
    """Check declared values/roles; literal source identity is checked by the gate.

    The role is a source-based semantic proposal, not independently established
    by matching a date. All such clinical calculations remain low confidence.
    """
    sources = candidate.field_sources
    required = {"medication_name"}
    if candidate.duration_status.value != "unknown":
        required.add("duration_status")
    required.update(field for field in ("start_range", "end_range", "record_time", "dose", "unit", "frequency", "route")
        if getattr(candidate, field) is not None)
    fields = [item.field for item in sources]
    errors = []
    allowed = required | {"duration_status"}
    if len(fields) != len(set(fields)) or not required <= set(fields) or not set(fields) <= allowed:
        errors.append("用药逐字段依据缺失、重复或包含未声明字段")
    for source in sources:
        value = getattr(candidate, source.field)
        if source.locator_id not in candidate.locator_ids:
            errors.append("用药字段引用了本条记录以外的定位")
        if source.locator_ids and (source.locator_ids != sorted(set(source.locator_ids))
                or source.locator_id not in source.locator_ids):
            errors.append("用药连续原文的定位须唯一有序且包含主定位")
        # Only an explicitly cited continuous span may join printed line wraps.
        # Its complete unchanged text is checked against the source by the gate.
        object_present = ("".join(source.object_text.split()) in "".join(source.excerpt.split())
            if source.locator_ids else source.object_text in source.excerpt)
        value_present = (object_present if source.locator_ids and source.field == "medication_name"
            and source.value_text == source.object_text else source.value_text in source.excerpt)
        if (source.object_text != candidate.medication_name or not object_present or not value_present):
            errors.append("用药字段须在同一连续摘录中明确对应药物对象和原值")
        role = {"medication_name": {"actual_use"}, "duration_status": {"status_" + candidate.duration_status.value},
                "record_time": {"recorded_at"}, "start_range": {"use_start"}, "end_range": {"use_end"}
                }.get(source.field, {"use_detail"})
        if source.field in {"start_range", "end_range"} and candidate.duration_status.value == "single":
            role = {*role, "single_use"}
        if source.role not in role:
            errors.append("用药字段的日期或使用角色与目标字段不一致")
        if source.field in {"start_range", "end_range"}:
            try:
                if value is None or source_date_bounds(source.value_text) != (
                        value.precision.value, value.lower_bound, value.upper_bound):
                    errors.append("用药日期范围或精度与本字段原文不一致")
                if value is not None and value.source_text is not None and (
                        value.source_text not in source.excerpt or source.value_text not in value.source_text):
                    errors.append("用药日期展示原文与字段依据不一致")
            except ValueError as exc:
                errors.append(str(exc))
        elif source.field == "record_time":
            try:
                precision, lower, _ = source_date_bounds(source.value_text)
                if value is None or precision != "day" or value.date() != lower or value.time().isoformat() != "00:00:00":
                    errors.append("用药记录时间超出原文日期精度或与原文不符")
            except ValueError:
                try:
                    written = datetime.fromisoformat(source.value_text)
                    if written.tzinfo is None or written != value:
                        errors.append("用药记录时刻与原文不符或缺少时区依据")
                except ValueError:
                    errors.append("用药记录日期没有明确原值依据")
        elif source.field == "dose" and value != source.value_text:
            # A dose and its separately quoted unit may be printed together.
            # Compare the written number only; do not convert units or ranges.
            try:
                if not candidate.unit or not source.value_text.endswith(candidate.unit):
                    raise ValueError
                written = Decimal(source.value_text[:-len(candidate.unit)].strip())
                declared = Decimal(value)
                if not written.is_finite() or not declared.is_finite() or written != declared:
                    raise ValueError
            except (InvalidOperation, ValueError, TypeError):
                errors.append("用药剂量与其原文数字及单位不一致")
        elif source.field != "duration_status" and value != source.value_text:
            errors.append("用药字段值与其逐字原值不一致")
    return list(dict.fromkeys(errors))
