"""Deterministic, traceable protocol identity candidate extraction.

The extractor consumes the immutable structure blocks produced by
``docx_structure``.  It intentionally returns candidates and conflicts rather
than silently choosing a project identity.  Priority is a deterministic hint
for review; a conflict or a fallback-only identity still requires confirmation.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import (
    AlignmentStatus,
    DocumentPart,
    IdentityAuthority,
    MetadataResolutionStatus,
    MetadataSourceKind,
    ProtocolMetadataField,
    SourceLocatorPrecision,
    StudyPhase,
)
from app.domain.contracts.protocol_metadata import (
    ProtocolIdentityDecision,
    ProtocolMetadataCandidate,
    ProtocolMetadataConflict,
)
from .docx_structure import StructureBlock

_DATE_RE = re.compile(
    r"(?P<year>20\d{2})\s*(?:年|[-/.])\s*(?P<month>\d{1,2})"
    r"(?:\s*(?:月|[-/.])\s*(?P<day>\d{1,2})\s*日?)?"
)
_COMPACT_DATE_RE = re.compile(r"(?<!\d)(?P<year>20\d{2})(?P<month>\d{2})(?P<day>\d{2})(?!\d)")
_VERSION_RE = re.compile(r"(?<![A-Za-z0-9])v?\s*(\d+(?:\.\d+){0,3})(?![A-Za-z0-9])", re.I)
_FILENAME_VERSION_RE = re.compile(
    r"(?<![A-Za-z0-9])v\s*(\d+(?:\.\d+){0,3})(?![A-Za-z0-9])", re.I
)
_CODE_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9]*(?:[-_/][A-Za-z0-9]+){1,})(?![A-Za-z0-9])")
_ROW_REF_RE = re.compile(r"^(?P<table>.+?\.t\d+)\.r(?P<row>\d+)\.c(?P<col>\d+)(?:\.p\d+)?$")

PRIORITY_RANK: dict[MetadataSourceKind, int] = {
    MetadataSourceKind.HEADER_FOOTER: 10,
    MetadataSourceKind.FIRST_PAGE: 20,
    MetadataSourceKind.SIGNATURE_PAGE: 30,
    MetadataSourceKind.BODY: 40,
    MetadataSourceKind.FILENAME: 50,
    MetadataSourceKind.USER_CONFIRMATION: 0,
}

IDENTITY_AUTHORITY: dict[MetadataSourceKind, IdentityAuthority] = {
    MetadataSourceKind.HEADER_FOOTER: IdentityAuthority.HIGH,
    MetadataSourceKind.FIRST_PAGE: IdentityAuthority.HIGH,
    MetadataSourceKind.SIGNATURE_PAGE: IdentityAuthority.MEDIUM,
    MetadataSourceKind.BODY: IdentityAuthority.MEDIUM,
    MetadataSourceKind.FILENAME: IdentityAuthority.LOW,
    MetadataSourceKind.USER_CONFIRMATION: IdentityAuthority.HIGH,
}

_IDENTITY_AUTHORITY_RANK = {
    IdentityAuthority.HIGH: 0,
    IdentityAuthority.MEDIUM: 1,
    IdentityAuthority.LOW: 2,
}

_GENERIC_TITLES = {
    "临床研究方案",
    "临床试验方案",
    "研究方案",
    "clinical study protocol",
    "clinical trial protocol",
    "protocol",
}


class MetadataExtractionError(ValueError):
    """元信息结构提取失败，不能用空候选伪装成功。"""


@dataclass(frozen=True)
class MetadataExtractionResult:
    snapshot_id: str
    candidates: tuple[ProtocolMetadataCandidate, ...]
    conflicts: tuple[ProtocolMetadataConflict, ...]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("：", ":").replace("／", "/")).strip(" \t:：;；")


def _normal_title(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" \t:：;；。，,.")


def _normal_code(value: str) -> str:
    value = _clean(value).strip("()（）[]【】,，。;；")
    return value.upper()


def _normal_version(value: str) -> str:
    match = _VERSION_RE.search(value)
    return match.group(1) if match else _clean(value).upper().lstrip("V")


def _parse_date(value: str) -> tuple[str, DateValue] | None:
    match = _DATE_RE.search(value)
    if match is None:
        match = _COMPACT_DATE_RE.search(value)
    if not match:
        return None
    year = int(match.group("year"))
    month = int(match.group("month"))
    day_text = match.group("day")
    if day_text is None:
        return (
            f"{year:04d}-{month:02d}",
            DateValue(
                value=datetime(year, month, 1).date(),
                precision="month",
                source_text=match.group(0),
            ),
        )
    day = int(day_text)
    parsed = datetime(year, month, day).date()
    return (
        parsed.isoformat(),
        DateValue(value=parsed, precision="day", source_text=match.group(0)),
    )


def _is_generic_title(value: str) -> bool:
    normalized = re.sub(r"[\s:：()（）【】\[\]、,，。./_-]+", "", value).lower()
    return normalized in {
        re.sub(r"[\s:：()（）【】\[\]、,，。./_-]+", "", title).lower()
        for title in _GENERIC_TITLES
    }


def _source_kind(block: StructureBlock, *, first_page_refs: set[str]) -> MetadataSourceKind:
    if block.document_part in {DocumentPart.HEADER, DocumentPart.FOOTER}:
        return MetadataSourceKind.HEADER_FOOTER
    if block.source_ref in first_page_refs:
        return MetadataSourceKind.FIRST_PAGE
    if re.search(r"签字页|签署页|签名页|signature\s+page", block.text, re.I):
        return MetadataSourceKind.SIGNATURE_PAGE
    return MetadataSourceKind.BODY


def _default_first_page_refs(blocks: Sequence[StructureBlock]) -> set[str]:
    """Conservative first-page approximation for structure-only extraction.

    When a render alignment map is available callers should pass explicit refs.
    In a DOCX structure snapshot, the first top-level table and the first body
    paragraphs are the only safe first-page approximation; later body blocks
    are never promoted merely because they contain a title-like phrase.
    """

    refs: set[str] = set()
    body_blocks = [item for item in blocks if item.document_part == DocumentPart.BODY]
    for block in body_blocks:
        if block.source_ref.startswith("body.t0"):
            refs.add(block.source_ref)
            continue
        if re.fullmatch(r"body\.p(?:[0-9]|1[0-3])", block.source_ref):
            refs.add(block.source_ref)
    return refs


def _source_fields(
    source_ref: str,
    source_spans: Mapping[str, object] | None,
) -> tuple[str | None, SourceLocatorPrecision, AlignmentStatus]:
    if not source_spans or source_ref not in source_spans:
        return None, SourceLocatorPrecision.BLOCK, AlignmentStatus.UNALIGNED
    span = source_spans[source_ref]
    return (
        getattr(span, "source_span_id", None),
        getattr(span, "precision", SourceLocatorPrecision.BLOCK),
        getattr(span, "alignment_status", AlignmentStatus.UNALIGNED),
    )


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"metadata-{digest}"


def _candidate_layer(candidate: ProtocolMetadataCandidate) -> tuple[int, int, int]:
    """Return the comparable authority layer for one field candidate.

    Formal/non-fallback evidence is compared before any filename fallback.
    Within that class, the deterministic source priority and identity
    authority decide whether two values are genuinely same-level conflicts.
    Rule locator precision is deliberately absent from this ordering.
    """

    return (
        int(candidate.is_fallback),
        candidate.priority_rank,
        _IDENTITY_AUTHORITY_RANK[candidate.identity_authority],
    )


def _candidate(
    *,
    snapshot_id: str,
    field_category: ProtocolMetadataField,
    value: str,
    source_ref: str,
    source_kind: MetadataSourceKind,
    excerpt: str,
    confidence_basis: list[str],
    document_part: DocumentPart,
    source_spans: Mapping[str, object] | None,
    is_fallback: bool = False,
) -> ProtocolMetadataCandidate | None:
    cleaned = _normal_title(value)
    if field_category in {
        ProtocolMetadataField.PROTOCOL_CODE,
        ProtocolMetadataField.PROJECT_CODE,
        ProtocolMetadataField.TEMPLATE_CODE,
    }:
        match = _CODE_RE.search(cleaned)
        if match is None:
            return None
        cleaned = match.group(1)
        normalized = _normal_code(cleaned)
    elif field_category == ProtocolMetadataField.PROTOCOL_VERSION or field_category == ProtocolMetadataField.TEMPLATE_VERSION:
        match = _VERSION_RE.search(cleaned)
        if match is None:
            return None
        token = match.group(0).replace(" ", "")
        cleaned = token.upper() if token.lower().startswith("v") else token
        normalized = match.group(1)
    elif field_category == ProtocolMetadataField.PROTOCOL_DATE:
        parsed = _parse_date(cleaned)
        if parsed is None:
            return None
        cleaned = parsed[1].source_text or cleaned
        normalized = parsed[0]
    else:
        normalized = _normal_title(cleaned).casefold()
    source_span_id, precision, alignment = _source_fields(source_ref, source_spans)
    generic = field_category in {
        ProtocolMetadataField.DOCUMENT_TITLE,
        ProtocolMetadataField.PROJECT_NAME,
    } and _is_generic_title(cleaned)
    return ProtocolMetadataCandidate(
        candidate_id=_stable_id(snapshot_id, field_category.value, normalized, source_ref),
        snapshot_id=snapshot_id,
        field_category=field_category,
        candidate_value=cleaned,
        normalized_value=normalized,
        source_ref=source_ref,
        source_span_id=source_span_id,
        document_part=document_part,
        source_kind=source_kind,
        identity_authority=IDENTITY_AUTHORITY[source_kind],
        priority_rank=PRIORITY_RANK[source_kind],
        confidence_basis=confidence_basis,
        excerpt=_clean(excerpt),
        locator_precision=precision,
        source_alignment_status=alignment,
        is_fallback=is_fallback,
        is_generic_title=generic,
    )


def _row_groups(blocks: Sequence[StructureBlock]) -> list[tuple[StructureBlock, str]]:
    """Return table-row excerpts using cell text without changing source refs."""

    groups: dict[tuple[str, int], list[StructureBlock]] = {}
    for block in blocks:
        match = _ROW_REF_RE.match(block.source_ref)
        if not match:
            continue
        key = (match.group("table"), int(match.group("row")))
        groups.setdefault(key, []).append(block)
    result: list[tuple[StructureBlock, str]] = []
    for cells in groups.values():
        ordered = sorted(cells, key=lambda item: item.source_ref)
        excerpt = " | ".join(_clean(item.text) for item in ordered if _clean(item.text))
        if excerpt:
            result.append((ordered[-1], excerpt))
    return result


def _label_value(label: str, value: str) -> list[tuple[ProtocolMetadataField, str, str]]:
    """Map one labelled row/line to distinct protocol/template fields."""

    label_norm = re.sub(r"\s+", "", label).lower()
    spaced_template_version = bool(re.search(r"版\s+本\s+号", label))
    value = _clean(value)
    output: list[tuple[ProtocolMetadataField, str, str]] = []
    if re.search(r"版本(?:号)?\s*/\s*(?:版本)?日期", label):
        output.append((ProtocolMetadataField.PROTOCOL_VERSION, value, "明确方案版本/日期标签"))
        output.append((ProtocolMetadataField.PROTOCOL_DATE, value, "明确方案版本/日期标签"))
        return output
    if re.search(r"模板编号|模板号|文件编号|文件编码|sop编号|sop号", label_norm):
        output.append((ProtocolMetadataField.TEMPLATE_CODE, value, "明确模板/文件编号标签"))
    elif re.search(r"项目代号|项目代码|项目编号", label_norm):
        output.append((ProtocolMetadataField.PROJECT_CODE, value, "明确项目代号标签"))
    elif re.search(r"方案编号|研究方案编号|protocol\s*(?:no|number)", label_norm, re.I):
        output.append((ProtocolMetadataField.PROTOCOL_CODE, value, "明确方案编号标签"))
    elif re.search(r"模板版本|模板版次|文件版本", label_norm) or spaced_template_version:
        output.append((ProtocolMetadataField.TEMPLATE_VERSION, value, "明确模板/文件版本标签"))
    elif re.search(r"版本日期|方案日期|研究方案日期|批准日期|日期|date", label_norm, re.I):
        output.append((ProtocolMetadataField.PROTOCOL_DATE, value, "明确版本日期标签"))
    elif re.search(r"方案版本(?!日期)|研究方案版本(?!日期)|方案版次", label_norm):
        output.append((ProtocolMetadataField.PROTOCOL_VERSION, value, "明确方案版本标签"))
    elif re.fullmatch(r"版本号|版本|version", label_norm, re.I):
        # Body first-page/signature rows are protocol fields. Header/footer
        # callers reclassify the standalone template label before this helper.
        output.append((ProtocolMetadataField.PROTOCOL_VERSION, value, "明确版本标签"))
    elif re.search(r"项目名称|项目名称|研究名称|试验名称|研究题目|方案标题|方案名称", label_norm):
        output.append((ProtocolMetadataField.PROJECT_NAME, value, "明确项目/方案名称标签"))
    elif re.search(r"标题|title", label_norm, re.I):
        output.append((ProtocolMetadataField.DOCUMENT_TITLE, value, "明确文档标题标签"))
    return output


def _parse_labeled_text(text: str) -> list[tuple[ProtocolMetadataField, str, str]]:
    text = text.replace("：", ":")
    # Match a label up to the first colon.  The value may contain additional
    # colons (e.g. an English title), so it is not split again.
    match = re.search(r"([^:：]{1,40}):\s*(.+)", text)
    if not match:
        return []
    label, value = match.groups()
    return _label_value(label, value)


def _parse_inline_protocol_identity(text: str) -> list[tuple[ProtocolMetadataField, str, str]]:
    """Parse header/footer lines containing several labelled fields."""

    text = text.replace("：", ":")
    output: list[tuple[ProtocolMetadataField, str, str]] = []
    if re.search(r"方案编号|protocol\s*(?:no|number)", text, re.I):
        match = re.search(r"(?:方案编号|protocol\s*(?:no|number))\s*[:：]?\s*([A-Za-z][A-Za-z0-9]*(?:[-_/][A-Za-z0-9]+)+)", text, re.I)
        if match:
            output.append((ProtocolMetadataField.PROTOCOL_CODE, match.group(1), "页眉/页脚明确方案编号标签"))
    if re.search(r"文件编号|模板编号|模板号", text, re.I):
        match = re.search(r"(?:文件编号|模板编号|模板号)\s*[:：]?\s*([A-Za-z][A-Za-z0-9]*(?:[-_/][A-Za-z0-9]+)+)", text, re.I)
        if match:
            output.append((ProtocolMetadataField.TEMPLATE_CODE, match.group(1), "页眉/页脚明确模板/文件编号标签"))
    if re.search(r"方案版本|版本号|版本日期|方案日期", text, re.I) and not re.search(r"文件编号|模板编号|模板号", text, re.I):
        version_match = re.search(r"(?:方案版本(?:/日期)?|版本号(?:/版本日期)?|版本)\s*[:：]?\s*(v?\s*\d+(?:\.\d+){0,3})", text, re.I)
        if version_match:
            output.append((ProtocolMetadataField.PROTOCOL_VERSION, version_match.group(1), "页眉/页脚明确方案版本标签"))
        date_match = _parse_date(text)
        if date_match:
            output.append((ProtocolMetadataField.PROTOCOL_DATE, date_match[1].source_text or date_match[0], "页眉/页脚明确方案日期标签"))
    if re.search(r"版\s*本\s*号", text) and not re.search(r"方案编号|方案版本|protocol", text, re.I):
        template_match = re.search(r"版\s*本\s*号\s*[:：]?\s*([A-Za-z0-9._-]+)", text, re.I)
        if template_match:
            output.append((ProtocolMetadataField.TEMPLATE_VERSION, template_match.group(1), "页眉/页脚明确模板版本标签"))
    return output


def _candidate_inputs(
    blocks: Sequence[StructureBlock],
    *,
    first_page_refs: set[str],
) -> Iterable[tuple[StructureBlock, str, list[tuple[ProtocolMetadataField, str, str]]]]:
    seen: set[tuple[str, str]] = set()
    for block in blocks:
        text = _clean(block.text)
        if not text:
            continue
        parsed = _parse_inline_protocol_identity(text) if block.document_part in {DocumentPart.HEADER, DocumentPart.FOOTER} else _parse_labeled_text(text)
        for field, value, basis in parsed:
            key = (block.source_ref, f"{field.value}:{_normal_title(value)}")
            if key not in seen:
                seen.add(key)
                yield block, text, [(field, value, basis)]
    for block, row_text in _row_groups(blocks):
        row_match = _ROW_REF_RE.match(block.source_ref)
        if not row_match:
            continue
        cells = [item for item in blocks if _ROW_REF_RE.match(item.source_ref) and _ROW_REF_RE.match(item.source_ref).group("table") == row_match.group("table") and int(_ROW_REF_RE.match(item.source_ref).group("row")) == int(row_match.group("row"))]
        ordered = sorted(cells, key=lambda item: item.source_ref)
        if len(ordered) < 2:
            continue
        label = _clean(ordered[0].text)
        value = _clean(" ".join(item.text for item in ordered[1:]))
        parsed = _label_value(label, value)
        # A standalone "版本号" in a header belongs to the template header;
        # body table rows are formal protocol identity fields.
        for field, field_value, basis in parsed:
            if field == ProtocolMetadataField.PROTOCOL_VERSION and block.document_part in {DocumentPart.HEADER, DocumentPart.FOOTER}:
                field = ProtocolMetadataField.TEMPLATE_VERSION
            key = (block.source_ref, f"{field.value}:{_normal_title(field_value)}")
            if key not in seen:
                seen.add(key)
                yield block, row_text, [(field, field_value, basis)]


def extract_protocol_metadata(
    blocks: Sequence[StructureBlock],
    *,
    snapshot_id: str,
    file_name: str | None = None,
    first_page_source_refs: Iterable[str] | None = None,
    source_spans: Mapping[str, object] | None = None,
) -> MetadataExtractionResult:
    """Extract traceable metadata candidates and deterministic conflict groups."""

    if not snapshot_id:
        raise MetadataExtractionError("元信息候选必须绑定提取快照")
    if not blocks:
        raise MetadataExtractionError("没有结构块，不能提取方案元信息")
    first_page_refs = set(first_page_source_refs or _default_first_page_refs(blocks))
    candidates: list[ProtocolMetadataCandidate] = []
    for block, excerpt, values in _candidate_inputs(blocks, first_page_refs=first_page_refs):
        kind = _source_kind(block, first_page_refs=first_page_refs)
        for field, value, basis in values:
            # The generic title is captured separately below; a protocol title
            # is a project name only when it has an explicit label.
            candidate = _candidate(
                    snapshot_id=snapshot_id,
                    field_category=field,
                    value=value,
                    source_ref=block.source_ref,
                    source_kind=kind,
                    excerpt=excerpt,
                    confidence_basis=[basis, f"source:{kind.value}"],
                    document_part=block.document_part,
                    source_spans=source_spans,
                )
            if candidate is not None:
                candidates.append(candidate)

    # The first meaningful body paragraph is a document title candidate.  It
    # is never silently promoted to project code/name when it is generic.
    body = [item for item in blocks if item.document_part == DocumentPart.BODY and _clean(item.text)]
    if body:
        title_block = body[0]
        title = _clean(title_block.text)
        if len(title) >= 3:
            kind = _source_kind(title_block, first_page_refs=first_page_refs)
            candidate = _candidate(
                    snapshot_id=snapshot_id,
                    field_category=ProtocolMetadataField.DOCUMENT_TITLE,
                    value=title,
                    source_ref=title_block.source_ref,
                    source_kind=kind,
                    excerpt=title,
                    confidence_basis=["首个正文标题候选", f"source:{kind.value}"],
                    document_part=title_block.document_part,
                    source_spans=source_spans,
                )
            if candidate is not None:
                candidates.append(candidate)

    if file_name:
        stem = Path(file_name).stem
        stem = re.sub(r"\s+", " ", stem).strip()
        if stem:
            candidate = _candidate(
                    snapshot_id=snapshot_id,
                    field_category=ProtocolMetadataField.DOCUMENT_TITLE,
                    value=stem,
                    source_ref=f"filename:{Path(file_name).name}",
                    source_kind=MetadataSourceKind.FILENAME,
                    excerpt=stem,
                    confidence_basis=["文件名兜底"],
                    document_part=DocumentPart.OTHER,
                    source_spans=source_spans,
                    is_fallback=True,
                )
            if candidate is not None:
                candidates.append(candidate)
            version_match = _FILENAME_VERSION_RE.search(stem)
            if version_match:
                candidate = _candidate(
                        snapshot_id=snapshot_id,
                        field_category=ProtocolMetadataField.PROTOCOL_VERSION,
                        value=version_match.group(0),
                        source_ref=f"filename:{Path(file_name).name}",
                        source_kind=MetadataSourceKind.FILENAME,
                        excerpt=stem,
                        confidence_basis=["文件名中的方案版本兜底"],
                        document_part=DocumentPart.OTHER,
                        source_spans=source_spans,
                        is_fallback=True,
                    )
                if candidate is not None:
                    candidates.append(candidate)
            parsed_filename_date = _parse_date(stem)
            if parsed_filename_date:
                candidate = _candidate(
                        snapshot_id=snapshot_id,
                        field_category=ProtocolMetadataField.PROTOCOL_DATE,
                        value=parsed_filename_date[1].source_text or parsed_filename_date[0],
                        source_ref=f"filename:{Path(file_name).name}",
                        source_kind=MetadataSourceKind.FILENAME,
                        excerpt=stem,
                        confidence_basis=["文件名中的方案日期兜底"],
                        document_part=DocumentPart.OTHER,
                        source_spans=source_spans,
                        is_fallback=True,
                    )
                if candidate is not None:
                    candidates.append(candidate)
            code_text = stem
            if version_match:
                code_text = code_text[: version_match.start()] + " " + code_text[version_match.end() :]
            date_match = _DATE_RE.search(code_text) or _COMPACT_DATE_RE.search(code_text)
            if date_match:
                code_text = code_text[: date_match.start()] + " " + code_text[date_match.end() :]
            code_match = _CODE_RE.search(code_text)
            if code_match:
                candidate = _candidate(
                        snapshot_id=snapshot_id,
                        field_category=ProtocolMetadataField.PROTOCOL_CODE,
                        value=code_match.group(1),
                        source_ref=f"filename:{Path(file_name).name}",
                        source_kind=MetadataSourceKind.FILENAME,
                        excerpt=stem,
                        confidence_basis=["文件名中的方案编号兜底"],
                        document_part=DocumentPart.OTHER,
                        source_spans=source_spans,
                        is_fallback=True,
                    )
                if candidate is not None:
                    candidates.append(candidate)

    # Re-attach deterministic conflict IDs.  Only different values at the
    # highest comparable layer are a conflict.  Lower-priority candidates are
    # retained as fallback evidence but cannot manufacture a formal conflict
    # against an agreed higher-priority value.
    grouped: dict[ProtocolMetadataField, list[ProtocolMetadataCandidate]] = {}
    for item in candidates:
        grouped.setdefault(item.field_category, []).append(item)
    conflicts: list[ProtocolMetadataConflict] = []
    for field, values in grouped.items():
        best_layer = min(_candidate_layer(item) for item in values)
        best_values = [item for item in values if _candidate_layer(item) == best_layer]
        normalized = sorted({item.normalized_value for item in best_values})
        if len(normalized) <= 1:
            continue
        conflict_id = _stable_id(snapshot_id, "metadata-conflict", field.value, *normalized)
        conflict = ProtocolMetadataConflict(
            conflict_id=conflict_id,
            snapshot_id=snapshot_id,
            field_category=field,
            candidate_ids=[item.candidate_id for item in best_values],
            normalized_values=normalized,
            reason=f"{field.value} 存在多个不同候选值，需用户确认",
        )
        conflicts.append(conflict)
        for index, item in enumerate(candidates):
            if item.candidate_id in conflict.candidate_ids:
                candidates[index] = item.model_copy(update={"conflict_group_id": conflict_id})
    return MetadataExtractionResult(snapshot_id, tuple(candidates), tuple(conflicts))


def _best_candidate(
    result: MetadataExtractionResult,
    field: ProtocolMetadataField,
) -> ProtocolMetadataCandidate | None:
    values = [item for item in result.candidates if item.field_category == field]
    if not values:
        return None
    return sorted(values, key=lambda item: (_candidate_layer(item), item.candidate_id))[0]


def _derive_project_code(protocol_code: str | None) -> str | None:
    if not protocol_code:
        return None
    pieces = re.split(r"[-_/]", protocol_code)
    if len(pieces) > 1 and re.fullmatch(r"\d+", pieces[-1]):
        return "-".join(pieces[:-1])
    return protocol_code


def _normal_date_value(value: DateValue) -> str:
    if value.value is None or value.precision.value == "unknown":
        raise MetadataExtractionError("方案日期确认必须提供年、月或日精度的规范值")
    if value.precision.value == "year":
        return f"{value.value.year:04d}"
    if value.precision.value == "month":
        return f"{value.value.year:04d}-{value.value.month:02d}"
    return value.value.isoformat()


def resolve_protocol_identity(
    result: MetadataExtractionResult,
    *,
    identity_decision_id: str,
    study_phase: StudyPhase | None = None,
    now: datetime | None = None,
) -> ProtocolIdentityDecision:
    """Select highest-priority candidates but leave ambiguity/fallback visible."""

    code = _best_candidate(result, ProtocolMetadataField.PROTOCOL_CODE)
    version = _best_candidate(result, ProtocolMetadataField.PROTOCOL_VERSION)
    date = _best_candidate(result, ProtocolMetadataField.PROTOCOL_DATE)
    project = _best_candidate(result, ProtocolMetadataField.PROJECT_NAME)
    title = _best_candidate(result, ProtocolMetadataField.DOCUMENT_TITLE)
    explicit_project_code = _best_candidate(result, ProtocolMetadataField.PROJECT_CODE)
    project_name = project.candidate_value if project else None
    if project_name and _is_generic_title(project_name):
        project_name = None
    if project_name is None and title and not title.is_generic_title:
        project_name = title.candidate_value
    protocol_code = code.candidate_value if code else None
    project_code = explicit_project_code.candidate_value if explicit_project_code else _derive_project_code(protocol_code)
    official_version = version.candidate_value if version else None
    official_date: DateValue | None = None
    if date:
        parsed = _parse_date(date.candidate_value)
        official_date = parsed[1] if parsed else None
    fields = [code, version, date]
    selected = [item.candidate_id for item in fields if item is not None]
    conflicts = [item for item in result.conflicts if item.field_category in {
        ProtocolMetadataField.PROJECT_NAME,
        ProtocolMetadataField.PROJECT_CODE,
        ProtocolMetadataField.PROTOCOL_CODE,
        ProtocolMetadataField.PROTOCOL_VERSION,
        ProtocolMetadataField.PROTOCOL_DATE,
    }]
    fallback = any(item is not None and item.is_fallback for item in fields)
    generic = (project is not None and project.is_generic_title) or (title is not None and title.is_generic_title and project is None)
    requires = bool(
        conflicts
        or fallback
        or generic
        or not all(fields)
        or official_date is None
        or project_name is None
        or study_phase is None
    )
    status = MetadataResolutionStatus.NEEDS_CONFIRMATION if requires else MetadataResolutionStatus.CONFIRMED
    confirmed_at = now or datetime.now(timezone.utc)
    return ProtocolIdentityDecision(
        identity_decision_id=identity_decision_id,
        snapshot_id=result.snapshot_id,
        project_name=project_name,
        project_code=project_code,
        protocol_code=protocol_code,
        official_version=official_version,
        official_date=official_date,
        study_phase=study_phase,
        selected_candidate_ids=selected,
        conflict_ids=[item.conflict_id for item in conflicts],
        status=status,
        confirmation_required=requires,
        confirmed_by=None if requires else "deterministic-resolver",
        confirmed_at=None if requires else confirmed_at,
    )


def confirm_protocol_identity(
    result: MetadataExtractionResult,
    pending: ProtocolIdentityDecision,
    *,
    protocol_code: str,
    project_name: str,
    project_code: str | None = None,
    official_version: str,
    official_date: DateValue,
    study_phase: StudyPhase,
    confirmed_by: str,
    confirmed_at: datetime,
    selected_candidate_ids: Sequence[str] | None = None,
) -> ProtocolIdentityDecision:
    """Apply explicit user confirmation; values remain bound to candidates or
    an explicitly confirmed generic/fallback value.
    """

    if not confirmed_by:
        raise MetadataExtractionError("身份确认必须记录确认人")
    available = {item.candidate_id for item in result.candidates}
    selected = list(selected_candidate_ids or pending.selected_candidate_ids)
    if any(item not in available for item in selected):
        raise MetadataExtractionError("身份确认引用了当前快照之外的候选")
    confirmed_values = {
        ProtocolMetadataField.PROJECT_NAME: _normal_title(project_name).casefold(),
        ProtocolMetadataField.PROJECT_CODE: _normal_code(
            project_code or pending.project_code or _derive_project_code(protocol_code) or ""
        ),
        ProtocolMetadataField.PROTOCOL_CODE: _normal_code(protocol_code),
        ProtocolMetadataField.PROTOCOL_VERSION: _normal_version(official_version),
        ProtocolMetadataField.PROTOCOL_DATE: _normal_date_value(official_date),
    }
    conflicts_by_id = {item.conflict_id: item for item in result.conflicts}
    for conflict_id in pending.conflict_ids:
        conflict = conflicts_by_id.get(conflict_id)
        if conflict is None:
            raise MetadataExtractionError("待确认身份引用了当前快照之外的冲突")
        desired = confirmed_values.get(conflict.field_category)
        matches = [
            item
            for item in result.candidates
            if item.candidate_id in conflict.candidate_ids
            and item.normalized_value == desired
        ]
        if len(matches) != 1:
            raise MetadataExtractionError(
                f"{conflict.field_category.value} 的确认值必须明确选中一个冲突候选"
            )
        selected = [item for item in selected if item not in conflict.candidate_ids]
        selected.append(matches[0].candidate_id)
    selected = list(dict.fromkeys(selected))
    confirmed_project_code = project_code or pending.project_code or _derive_project_code(protocol_code)
    return ProtocolIdentityDecision(
        identity_decision_id=pending.identity_decision_id,
        snapshot_id=pending.snapshot_id,
        project_name=_normal_title(project_name),
        project_code=_normal_code(confirmed_project_code) if confirmed_project_code else None,
        protocol_code=_normal_code(protocol_code),
        official_version=official_version,
        official_date=official_date,
        study_phase=study_phase,
        selected_candidate_ids=selected,
        conflict_ids=[],
        resolved_conflict_ids=list(
            dict.fromkeys([*pending.resolved_conflict_ids, *pending.conflict_ids])
        ),
        status=MetadataResolutionStatus.CONFIRMED,
        confirmation_required=False,
        confirmed_by=confirmed_by,
        confirmed_at=confirmed_at,
    )


# Short aliases used by callers that treat the structure extractor as a
# metadata provider rather than a protocol-specific module.
extract_metadata_candidates = extract_protocol_metadata
resolve_identity_candidates = resolve_protocol_identity
