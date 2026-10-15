"""Four-block source-scope discovery from frozen catalogs and native structure.

Candidates are not approved rules or phase applicability decisions. Unknown
references remain explicit. Raw source, geometry and identity are preserved;
there is no database, model call, publication or clinical adoption here.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import Enum

from app.domain.contracts.agent_io import ProtocolDeconstructionInput
from app.domain.contracts.enums import DocumentPart, ReviewStage
from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
from app.protocols.docx_structure import BlockKind, StructureBlock, native_source_text


class ReviewScopeKind(str, Enum):
    """四类范围候选；与 DESIGN §5.2 的 S1–S4 一一对应。"""

    OFFICIAL_RULE_TEXT = "official_rule_text"          # S1
    REFERENCED_SOURCE = "referenced_source"            # S2
    REQUIRED_PROCEDURE = "required_procedure"          # S3
    MEDICATION_SECTION = "medication_section"          # S4


#: 角色（候选类别）在来源记录中的稳定排序。
_ROLE_ORDER: tuple[ReviewScopeKind, ...] = (
    ReviewScopeKind.OFFICIAL_RULE_TEXT,
    ReviewScopeKind.REFERENCED_SOURCE,
    ReviewScopeKind.REQUIRED_PROCEDURE,
    ReviewScopeKind.MEDICATION_SECTION,
)


class ScopeDiagnosticKind(str, Enum):
    """有界的诊断类型；未知项一律显式，不解释为"没有限制"。"""

    REFERENCE_UNRESOLVED = "reference_unresolved"
    REFERENCE_AMBIGUOUS = "reference_ambiguous"
    REFERENCE_EXTERNAL_ATTRIBUTION = "reference_external_attribution"
    REFERENCE_IDENTIFIER_UNSUPPORTED = "reference_identifier_unsupported"
    SOURCE_SPAN_UNKNOWN = "source_span_unknown"
    SOURCE_SPAN_CROSS_SNAPSHOT = "source_span_cross_snapshot"
    SOURCE_TEXT_UNAVAILABLE = "source_text_unavailable"
    EXCERPT_NOT_IN_SOURCE_TEXT = "excerpt_not_in_source_text"
    TABLE_GEOMETRY_INCONSISTENT = "table_geometry_inconsistent"
    SOURCE_GEOMETRY_INCONSISTENT = "source_geometry_inconsistent"


@dataclass(frozen=True)
class ReviewScopeCandidate:
    """一个范围候选（发现结果，不是已采用的临床覆盖）。"""

    scope_kind: ReviewScopeKind
    label: str
    discovery_reason: str
    source_span_ids: tuple[str, ...] = ()
    block_source_refs: tuple[str, ...] = ()
    identifiers: tuple[str, ...] = ()
    official_codes: tuple[str, ...] = ()
    catalog_item_id: str | None = None
    visit_instance: str | None = None
    review_stage: ReviewStage | None = None
    citing_source_span_ids: tuple[str, ...] = ()
    frozen_source_excerpts: tuple[str | None, ...] = ()
    clinically_confirmed: bool = False


@dataclass(frozen=True)
class ReviewScopeDiagnostic:
    """一个有界的诊断对象：既不是临床结论，也不是"无要求"的证明。"""

    kind: ScopeDiagnosticKind
    message: str
    identifiers: tuple[str, ...] = ()
    source_span_ids: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    related_official_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviewScopeSourceRecord:
    """一个被候选引用到的来源定位：原文、几何、顺序、角色与身份状态。"""

    source_span_id: str
    source_ref: str
    block_order: int | None
    raw_text: str | None
    excerpt: str | None
    table_path: tuple[int, ...] | None
    roles: tuple[ReviewScopeKind, ...]
    identity_status: str  # ok | unknown_span | cross_snapshot | source_mismatch | excerpt_mismatch


@dataclass(frozen=True)
class ReviewScopeDiscovery:
    """发现结果：候选 + 诊断 + 来源记录；不构成临床采用。"""

    candidates: tuple[ReviewScopeCandidate, ...]
    diagnostics: tuple[ReviewScopeDiagnostic, ...]
    source_records: tuple[ReviewScopeSourceRecord, ...]
    clinical_adoption_applied: bool = False


# ---------------------------------------------------------------------------
# 引用识别（S2）
# ---------------------------------------------------------------------------

_DOTTED_NUMBER = r"\d+(?:\s*[.．\-–—]\s*\d+)*"
_CHINESE_NUMBER = r"[一二三四五六七八九十百]+"
_NUMBER_TOKEN = rf"(?:{_DOTTED_NUMBER}|{_CHINESE_NUMBER})"

_SECTION_RE = re.compile(rf"第\s*(?P<id>{_NUMBER_TOKEN})\s*(?:章节|节|章)")
_CUE_SECTION_RE = re.compile(r"(?:参照|参见|详见|见)\s*(?P<id>\d+(?:[.．]\d+)+)(?![\d.．])")
_APPENDIX_RE = re.compile(
    rf"(?:附录|(?<![A-Za-z])Appendix)\s*(?P<id>[A-Za-z0-9]+|{_CHINESE_NUMBER})",
    re.IGNORECASE,
)
_TABLE_RE = re.compile(
    rf"(?:表|(?<![A-Za-z])Table)\s*(?P<id>{_NUMBER_TOKEN})",
    re.IGNORECASE,
)
_ENGLISH_SECTION_RE = re.compile(rf"(?:Section|§)\s*(?P<id>{_DOTTED_NUMBER})", re.IGNORECASE)

_EXTERNAL_LATIN_MARKERS = (
    "ich", "gcp", "fda", "ema", "nmpa", "cde", "who", "iso", "iec",
    "nci", "ctcae", "meddra", "nccn", "usp", "astm", "hl7",
)
_EXTERNAL_TEXT_MARKERS = (
    "药典", "指导原则", "指南", "共识", "法规", "通则", "行业标准", "国家标准",
)
_CLAUSE_SEPARATORS = ("。", "；", ";", "！", "？", "!", "?", "\n")

_CHINESE_DIGITS = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}


class _ReferenceKind(str, Enum):
    SECTION = "section"
    APPENDIX = "appendix"
    TABLE = "table"


@dataclass(frozen=True)
class _Reference:
    kind: _ReferenceKind
    raw: str
    identifier: str
    start: int
    end: int
    unsupported: bool


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("：", ":")).strip()


def _chinese_number(value: str) -> int | None:
    """一至九十九的中文数字；超出范围返回 None（不猜）。"""

    if not value or any(char not in "零一二三四五六七八九十" for char in value):
        return None
    if "十" in value:
        left, _, right = value.partition("十")
        tens = 1 if left == "" else _CHINESE_DIGITS.get(left)
        if tens is None or tens == 0:
            return None
        if right == "":
            return tens * 10
        ones = _CHINESE_DIGITS.get(right)
        if ones is None:
            return None
        return tens * 10 + ones
    return _CHINESE_DIGITS.get(value)


def _normalize_identifier(value: str) -> str | None:
    """归一化引用标识：逐分量去前导零、字母大写、保留分隔符种类。"""

    raw = value.replace("．", ".").replace("－", "-").replace("–", "-").replace("—", "-")
    raw = re.sub(r"\s+", "", raw)
    if not raw:
        return None
    if raw.isdigit():
        return str(int(raw))
    if re.fullmatch(_CHINESE_NUMBER, raw):
        number = _chinese_number(raw)
        return None if number is None else str(number)
    tokens = re.split(r"([.\-])", raw)
    parts: list[str] = []
    for token in tokens:
        if token in (".", "-"):
            parts.append(token)
        elif token.isdigit():
            parts.append(str(int(token)))
        elif re.fullmatch(r"[A-Za-z0-9]+", token):
            parts.append(token.upper())
        else:
            return None
    return "".join(parts).strip(".-") or None


def _iter_references(text: str) -> tuple[_Reference, ...]:
    matches: list[tuple[int, int, _ReferenceKind, re.Match[str]]] = []
    for kind, pattern in (
        (_ReferenceKind.SECTION, _SECTION_RE),
        (_ReferenceKind.SECTION, _CUE_SECTION_RE),
        (_ReferenceKind.SECTION, _ENGLISH_SECTION_RE),
        (_ReferenceKind.APPENDIX, _APPENDIX_RE),
        (_ReferenceKind.TABLE, _TABLE_RE),
    ):
        for match in pattern.finditer(text):
            matches.append((match.start(), match.end(), kind, match))
    matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))

    references: list[_Reference] = []
    last_end = -1
    for start, end, kind, match in matches:
        if start < last_end:
            continue
        last_end = end
        identifier = _normalize_identifier(match.group("id"))
        references.append(
            _Reference(
                kind=kind,
                raw=match.group(0),
                identifier=identifier or "",
                start=start,
                end=end,
                unsupported=identifier is None,
            )
        )
    return tuple(references)


def _external_attribution(text: str, start: int, end: int) -> tuple[bool, tuple[str, ...]]:
    """引用所在整句是否属于外部文件／指南语境（保守：宁可未解析，不误绑定）。"""

    left = 0
    for separator in _CLAUSE_SEPARATORS:
        index = text.rfind(separator, 0, start)
        if index + 1 > left:
            left = index + 1
    right = len(text)
    for separator in _CLAUSE_SEPARATORS:
        index = text.find(separator, end)
        if index != -1 and index < right:
            right = index
    clause = text[left:right]
    markers: list[str] = []
    if clause.rfind("《") > clause.rfind("》"):
        markers.append("书名号引用")
    lowered = clause.lower()
    for token in _EXTERNAL_LATIN_MARKERS:
        if re.search(rf"(?<![a-z0-9]){token}(?![a-z0-9])", lowered):
            markers.append(token.upper())
    for token in _EXTERNAL_TEXT_MARKERS:
        if token in clause:
            markers.append(token)
    return bool(markers), tuple(dict.fromkeys(markers))


def _is_literal_fragment(excerpt: str, text: str) -> bool:
    return excerpt in text


# ---------------------------------------------------------------------------
# 结构标题与表题（S2/S4）
# ---------------------------------------------------------------------------

_TOC_STYLE_RE = re.compile(r"(?:^|\b)toc(?:\b|\d)|目录", re.IGNORECASE)
_HEADING_STYLE_RE = re.compile(r"heading|title|标题", re.IGNORECASE)
_STYLE_LEVEL_RE = re.compile(r"(\d+)")

_HEADING_EXPLICIT_RE = re.compile(rf"^第\s*(?P<num>{_NUMBER_TOKEN})\s*(?:章节|节|章)")
_HEADING_DOTTED_RE = re.compile(r"^(?P<num>\d+(?:[.．]\d+)+)")
_HEADING_SINGLE_RE = re.compile(r"^(?P<num>\d+)\s*(?:[、.．:：]|\s|$)")
_CONCRETE_NUMBERING_RE = re.compile(r"^\d+(?:[.．]\d+)*[.．]?$")

_LABEL_PREFIX_RE = re.compile(
    rf"^(?:第\s*{_NUMBER_TOKEN}\s*(?:章节|节|章|部分)?"
    rf"|\d+(?:[.．]\d+)*\s*(?:章节|节|章|部分|[、.．:：]|\s))"
)

_S4_HEADING_RE = re.compile(
    r"禁用(?:的)?(?:药物|药品|用药|治疗)|"
    r"禁止(?:使用|服用|应用)(?:的)?(?:药物|药品|用药)|"
    r"不允许(?:使用|服用|应用)(?:的)?(?:药物|药品|用药)|"
    r"合并(?:用药|药物|治疗)|"
    r"伴随(?:用药|治疗|药物)|"
    r"合用(?:药物|用药)|"
    r"(?<![A-Za-z])prohibited\s+(?:medications?|drugs?|therap(?:y|ies))|"
    r"(?<![A-Za-z])concomitant\s+(?:medications?|therap(?:y|ies)|treatments?)|"
    r"(?<![A-Za-z])disallowed\s+(?:medications?|drugs?)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _BodyEntry:
    block: StructureBlock
    index: int
    level: int | None
    number: str | None
    appendix: str | None
    caption_id: str | None


@dataclass(frozen=True)
class _ResolvedTarget:
    label: str
    anchor_ref: str
    anchor_order: int
    block_indexes: tuple[int, ...]


def _heading_level(block: StructureBlock) -> int | None:
    """只把结构信号明确的段落当标题；表格单元格内段落与目录样式除外。"""

    if block.kind != BlockKind.PARAGRAPH or block.table_path is not None:
        return None
    text = _normalize_text(block.text)
    if not text:
        return None
    style = f"{block.style_name or ''} {block.style or ''}".strip()
    if _TOC_STYLE_RE.search(style):
        return None
    if block.outline_level is not None:
        return max(0, block.outline_level)
    if _HEADING_STYLE_RE.search(style) and len(text) <= 200:
        match = _STYLE_LEVEL_RE.search(style)
        return max(0, int(match.group(1)) - 1) if match else 0
    return None


def _heading_number(block: StructureBlock) -> str | None:
    text = _normalize_text(block.text)
    for pattern in (_HEADING_EXPLICIT_RE, _HEADING_DOTTED_RE, _HEADING_SINGLE_RE):
        match = pattern.match(text)
        if match:
            return _normalize_identifier(match.group("num"))
    numbering = block.numbering
    if numbering is not None and numbering.lvl_text:
        concrete = numbering.lvl_text.strip()
        if "%" not in concrete and _CONCRETE_NUMBERING_RE.match(concrete):
            return _normalize_identifier(concrete.rstrip(".．"))
    return None


def _heading_appendix(block: StructureBlock) -> str | None:
    match = _APPENDIX_RE.search(_normalize_text(block.text))
    if match is None:
        return None
    return _normalize_identifier(match.group("id"))


def _heading_label(block: StructureBlock) -> str:
    value = _normalize_text(block.text)
    value = _LABEL_PREFIX_RE.sub("", value)
    return value.strip(" :：。．、")


def _is_table_block(block: StructureBlock | None) -> bool:
    return block is not None and block.kind == BlockKind.TABLE


def _caption_identifier(entries: Sequence[_BodyEntry], index: int) -> str | None:
    """表题 = 以"表 N／Table N"开头且紧邻真实表格块的段落。"""

    entry = entries[index]
    block = entry.block
    if block.kind != BlockKind.PARAGRAPH or entry.level is not None:
        return None
    text = _normalize_text(block.text)
    if not text or len(text) > 200:
        return None
    match = _TABLE_RE.match(text)
    if match is None:
        return None
    if _adjacent_table_index(entries, index) is None:
        return None
    return _normalize_identifier(match.group("id"))


def _body_entries(blocks: Sequence[StructureBlock]) -> tuple[_BodyEntry, ...]:
    body = [block for block in blocks if block.document_part == DocumentPart.BODY]
    entries: list[_BodyEntry] = []
    for index, block in enumerate(body):
        level = _heading_level(block)
        entries.append(
            _BodyEntry(
                block=block,
                index=index,
                level=level,
                number=_heading_number(block) if level is not None else None,
                appendix=_heading_appendix(block) if level is not None else None,
                caption_id=None,
            )
        )
    for index in range(len(entries)):
        caption_id = _caption_identifier(entries, index)
        if caption_id is not None:
            entries[index] = replace(entries[index], caption_id=caption_id)
    return tuple(entries)


def _subtree_indexes(entries: Sequence[_BodyEntry], start: int) -> tuple[int, ...]:
    level = entries[start].level
    indexes = [start]
    for index in range(start + 1, len(entries)):
        entry = entries[index]
        if entry.level is not None and entry.level <= (level or 0):
            break
        indexes.append(index)
    return tuple(indexes)


def _table_extent_indexes(entries: Sequence[_BodyEntry], top_index: int) -> tuple[int, ...]:
    indexes = [top_index]
    cursor = top_index + 1
    prefix = entries[top_index].block.source_ref + "."
    while cursor < len(entries) and entries[cursor].block.source_ref.startswith(prefix):
        indexes.append(cursor)
        cursor += 1
    return tuple(indexes)


def _adjacent_table_index(entries: Sequence[_BodyEntry], index: int) -> int | None:
    container = entries[index].block.table_path
    if index + 1 < len(entries) and _is_table_block(entries[index + 1].block):
        return index + 1 if entries[index + 1].block.table_path == container else None
    # A following caption comes after the table's cell blocks, not its opener.
    for previous in range(index - 1, -1, -1):
        block = entries[previous].block
        if block.kind == BlockKind.TABLE and block.table_path == container:
            if _table_extent_indexes(entries, previous)[-1] == index - 1:
                return previous
        if block.table_path is None and block.kind != BlockKind.TABLE:
            break
    return None


def _heading_target(entries: Sequence[_BodyEntry], index: int) -> _ResolvedTarget:
    block = entries[index].block
    return _ResolvedTarget(
        label=_normalize_text(block.text),
        anchor_ref=block.source_ref,
        anchor_order=block.block_order,
        block_indexes=_subtree_indexes(entries, index),
    )


def _table_target(entries: Sequence[_BodyEntry], index: int) -> _ResolvedTarget | None:
    caption = entries[index].block
    top = _adjacent_table_index(entries, index)
    if top is None:
        return None
    indexes = sorted({index, *_table_extent_indexes(entries, top)})
    first = entries[indexes[0]].block
    return _ResolvedTarget(
        label=_normalize_text(caption.text),
        anchor_ref=caption.source_ref,
        anchor_order=first.block_order,
        block_indexes=tuple(indexes),
    )


def _resolve_reference(
    reference: _Reference, entries: Sequence[_BodyEntry]
) -> tuple[_ResolvedTarget, ...]:
    if reference.kind is _ReferenceKind.SECTION:
        targets = [
            _heading_target(entries, entry.index)
            for entry in entries
            if entry.level is not None and entry.number == reference.identifier
        ]
        return tuple(targets)
    if reference.kind is _ReferenceKind.APPENDIX:
        targets = [
            _heading_target(entries, entry.index)
            for entry in entries
            if entry.level is not None and entry.appendix == reference.identifier
        ]
        return tuple(targets)
    targets = []
    for entry in entries:
        if entry.caption_id != reference.identifier:
            continue
        target = _table_target(entries, entry.index)
        if target is not None:
            targets.append(target)
    return tuple(targets)


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------


def review_scope_source_options(*, blocks: Sequence[StructureBlock], source_spans: Sequence[ProtocolSourceSpan],
                              query: str, offset: int = 0, limit: int = 20) -> dict:
    """Search the frozen native source, returning whole sections or individual paragraphs."""
    if offset < 0 or not 1 <= limit <= 20:
        raise ValueError("原文查找范围不合法")
    entries = _body_entries(sorted(blocks, key=lambda block: (block.block_order, block.source_ref)))
    spans_by_ref = {span.source_ref: span for span in source_spans}
    matches = [entry for entry in entries if entry.block.text.strip()
        and not _TOC_STYLE_RE.search(f"{entry.block.style_name or ''} {entry.block.style or ''}")
        and (_normalize_text(query).casefold() in _normalize_text(entry.block.text).casefold()
             if query.strip() else entry.level is not None)]
    options = []
    for entry in matches[offset:offset + limit]:
        indexes = _subtree_indexes(entries, entry.index) if entry.level is not None else (entry.index,)
        span = spans_by_ref.get(entry.block.source_ref)
        options.append({
            "label": entry.block.text if entry.level is not None else "方案原文段落",
            "text": entry.block.text,
            "page": span.render_page if span else None,
            "source_span_ids": [spans_by_ref[entries[index].block.source_ref].source_span_id
                for index in indexes if entries[index].block.source_ref in spans_by_ref],
            "missing_positions": sum(entries[index].block.source_ref not in spans_by_ref for index in indexes),
        })
    next_offset = offset + len(options)
    return {"items": options, "total": len(matches),
            "next_offset": next_offset if next_offset < len(matches) else None}


def discover_review_scope(
    *,
    source_input: ProtocolDeconstructionInput,
    blocks: Sequence[StructureBlock],
    source_spans: Sequence[ProtocolSourceSpan],
) -> ReviewScopeDiscovery:
    """从冻结输入派生范围候选；不做持久化、审定、期别判定或临床采用。"""

    materials = {item.source_span_id: item for item in source_input.source_materials}
    spans_by_id: dict[str, ProtocolSourceSpan] = {}
    spans_by_ref: dict[str, list[ProtocolSourceSpan]] = {}
    for span in source_spans:
        if span.source_span_id in spans_by_id or span.source_ref in spans_by_ref:
            raise ValueError("范围定位的来源身份或结构位置重复")
        spans_by_id[span.source_span_id] = span
        spans_by_ref.setdefault(span.source_ref, []).append(span)

    ordered = sorted(blocks, key=lambda block: (block.block_order, block.source_ref))
    blocks_by_ref = {block.source_ref: block for block in ordered}
    if len(blocks_by_ref) != len(ordered):
        raise ValueError("范围结构块的来源位置重复")
    entries = _body_entries(ordered)

    roles: dict[str, list[ReviewScopeKind]] = {}
    diagnostics: list[ReviewScopeDiagnostic] = []
    candidates: list[ReviewScopeCandidate] = []

    def add_role(span_id: str, kind: ReviewScopeKind) -> None:
        kinds = roles.setdefault(span_id, [])
        if kind not in kinds:
            kinds.append(kind)

    def add_diagnostic(
        kind: ScopeDiagnosticKind,
        message: str,
        *,
        identifiers: Sequence[str] = (),
        source_span_ids: Sequence[str] = (),
        source_refs: Sequence[str] = (),
        codes: Sequence[str] = (),
    ) -> None:
        diagnostics.append(
            ReviewScopeDiagnostic(
                kind=kind,
                message=message,
                identifiers=tuple(identifiers),
                source_span_ids=tuple(source_span_ids),
                source_refs=tuple(source_refs),
                related_official_codes=tuple(codes),
            )
        )

    def evidence(indexes: Sequence[int]) -> tuple[list[StructureBlock], tuple[str, ...], tuple[str, ...]]:
        block_list = [entries[index].block for index in indexes]
        span_ids: list[str] = []
        for block in block_list:
            if block.source_ref not in spans_by_ref:
                add_diagnostic(ScopeDiagnosticKind.SOURCE_SPAN_UNKNOWN,
                    "已找到原文结构，但缺少对应的来源定位", source_refs=(block.source_ref,))
            for span in spans_by_ref.get(block.source_ref, ()):
                if span.source_span_id not in span_ids:
                    span_ids.append(span.source_span_id)
        return block_list, tuple(block.source_ref for block in block_list), tuple(span_ids)

    checked_table_refs: set[str] = set()

    def check_table_geometry(block_list: Sequence[StructureBlock]) -> None:
        for block in block_list:
            if block.table_path is None or block.source_ref in checked_table_refs:
                continue
            expected = block.table_path[:-2] or None
            found = any(
                other.kind == BlockKind.TABLE
                and other.table_path == expected
                and other.document_part == block.document_part
                and block.source_ref.startswith(other.source_ref + ".")
                for other in ordered
            )
            if not found:
                checked_table_refs.add(block.source_ref)
                add_diagnostic(
                    ScopeDiagnosticKind.TABLE_GEOMETRY_INCONSISTENT,
                    f"表格块 {block.source_ref} 的嵌套路径缺少对应的上层表格结构",
                    source_refs=(block.source_ref,),
                )

    # S1：官方条款原文只来自冻结官方父规则目录。
    for item in source_input.parent_rule_catalog.items:
        candidates.append(
            ReviewScopeCandidate(
                scope_kind=ReviewScopeKind.OFFICIAL_RULE_TEXT,
                label=item.label,
                discovery_reason=f"官方父规则目录：{item.official_code}",
                source_span_ids=tuple(item.source_span_ids),
                official_codes=(item.official_code,) if item.official_code else (),
                catalog_item_id=item.item_id,
                frozen_source_excerpts=tuple(item.source_excerpts),
            )
        )
        for span_id in item.source_span_ids:
            add_role(span_id, ReviewScopeKind.OFFICIAL_RULE_TEXT)

    # S2：只扫描官方父规则原文材料中明示的章节／附录／表格引用。
    codes_by_span: dict[str, list[str]] = {}
    for item in source_input.parent_rule_catalog.items:
        if not item.official_code:
            continue
        for span_id in item.source_span_ids:
            codes = codes_by_span.setdefault(span_id, [])
            if item.official_code not in codes:
                codes.append(item.official_code)

    pending: dict[tuple[str, str, str], dict] = {}
    for span_id, codes in codes_by_span.items():
        material = materials.get(span_id)
        if material is None or not material.text:
            continue
        for reference in _iter_references(material.text):
            if reference.unsupported:
                add_diagnostic(
                    ScopeDiagnosticKind.REFERENCE_IDENTIFIER_UNSUPPORTED,
                    f"{reference.raw} 的标识形式暂不支持自动归一化，未猜测匹配",
                    identifiers=(reference.raw,),
                    source_span_ids=(span_id,),
                    codes=codes,
                )
                continue
            external, markers = _external_attribution(
                material.text, reference.start, reference.end
            )
            if external:
                add_diagnostic(
                    ScopeDiagnosticKind.REFERENCE_EXTERNAL_ATTRIBUTION,
                    f"{reference.raw} 处于外部文件或指南语境（{'、'.join(markers)}），"
                    f"未绑定到同编号方案章节",
                    identifiers=(reference.raw,),
                    source_span_ids=(span_id,),
                    codes=codes,
                )
                continue
            targets = _resolve_reference(reference, entries)
            if not targets:
                add_diagnostic(
                    ScopeDiagnosticKind.REFERENCE_UNRESOLVED,
                    f"{reference.raw} 在方案结构标题／表题中未找到匹配",
                    identifiers=(reference.raw,),
                    source_span_ids=(span_id,),
                    codes=codes,
                )
                continue
            if len(targets) > 1:
                add_diagnostic(
                    ScopeDiagnosticKind.REFERENCE_AMBIGUOUS,
                    f"{reference.raw} 匹配到 {len(targets)} 处结构标题／表题，需人工确认："
                    f"{'、'.join(target.anchor_ref for target in targets)}",
                    identifiers=(reference.raw,),
                    source_span_ids=(span_id,),
                    source_refs=tuple(target.anchor_ref for target in targets),
                    codes=codes,
                )
                continue
            target = targets[0]
            key = (reference.kind.value, reference.identifier, target.anchor_ref)
            item = pending.setdefault(
                key,
                {
                    "kind": reference.kind,
                    "target": target,
                    "identifiers": [],
                    "codes": [],
                    "citing_span_ids": [],
                },
            )
            if reference.raw not in item["identifiers"]:
                item["identifiers"].append(reference.raw)
            for code in codes:
                if code not in item["codes"]:
                    item["codes"].append(code)
            if span_id not in item["citing_span_ids"]:
                item["citing_span_ids"].append(span_id)

    for item in sorted(
        pending.values(),
        key=lambda value: (
            value["target"].anchor_order,
            value["identifiers"][0] if value["identifiers"] else "",
        ),
    ):
        target: _ResolvedTarget = item["target"]
        block_list, block_refs, span_ids = evidence(target.block_indexes)
        check_table_geometry(block_list)
        for span_id in (*span_ids, *item["citing_span_ids"]):
            add_role(span_id, ReviewScopeKind.REFERENCED_SOURCE)
        kind_label = "表题" if item["kind"] is _ReferenceKind.TABLE else "结构标题"
        candidates.append(
            ReviewScopeCandidate(
                scope_kind=ReviewScopeKind.REFERENCED_SOURCE,
                label=target.label,
                discovery_reason=(
                    f"{'、'.join(item['codes'])}引用{item['identifiers'][0]}，"
                    f"匹配{kind_label}「{target.label}」"
                ),
                source_span_ids=span_ids,
                block_source_refs=block_refs,
                identifiers=tuple(item["identifiers"]),
                official_codes=tuple(item["codes"]),
                citing_source_span_ids=tuple(item["citing_span_ids"]),
            )
        )

    # S3：只来自冻结必做项目录，不扫描访视表中的其他列。
    for item in source_input.required_procedure_catalog.items:
        candidates.append(
            ReviewScopeCandidate(
                scope_kind=ReviewScopeKind.REQUIRED_PROCEDURE,
                label=item.label,
                discovery_reason=f"冻结必做项目录：{item.visit_instance}",
                source_span_ids=tuple(item.source_span_ids),
                catalog_item_id=item.item_id,
                visit_instance=item.visit_instance,
                review_stage=item.review_stage,
                frozen_source_excerpts=tuple(item.source_excerpts),
            )
        )
        for span_id in item.source_span_ids:
            add_role(span_id, ReviewScopeKind.REQUIRED_PROCEDURE)

    # S4：真正的用药／治疗章节标题及其有界子树（含嵌套表格）。
    for entry in entries:
        if entry.level is None:
            continue
        if not _S4_HEADING_RE.search(_heading_label(entry.block)):
            continue
        block_list, block_refs, span_ids = evidence(_subtree_indexes(entries, entry.index))
        check_table_geometry(block_list)
        for span_id in span_ids:
            add_role(span_id, ReviewScopeKind.MEDICATION_SECTION)
        label = _normalize_text(entry.block.text)
        candidates.append(
            ReviewScopeCandidate(
                scope_kind=ReviewScopeKind.MEDICATION_SECTION,
                label=label,
                discovery_reason=f"标题匹配：{label}",
                source_span_ids=span_ids,
                block_source_refs=block_refs,
            )
        )

    # 来源记录：保留原文、几何、顺序与多角色；缺失／跨快照身份不丢弃。
    records: list[ReviewScopeSourceRecord] = []
    for span_id, kinds in roles.items():
        span = spans_by_id.get(span_id)
        material = materials.get(span_id)
        block = blocks_by_ref.get(span.source_ref if span is not None else
                                  material.source_ref if material is not None else "")
        raw_text = native_source_text(block, blocks_by_ref) if block is not None else material.text if material is not None else None
        if span is None:
            identity_status = "unknown_span"
            add_diagnostic(
                ScopeDiagnosticKind.SOURCE_SPAN_UNKNOWN,
                f"来源定位 {span_id} 不在本次结构来源中，未丢弃但无法核对",
                source_span_ids=(span_id,),
            )
        elif span.snapshot_id != source_input.extraction_snapshot_id:
            identity_status = "cross_snapshot"
            add_diagnostic(
                ScopeDiagnosticKind.SOURCE_SPAN_CROSS_SNAPSHOT,
                f"来源定位 {span_id} 属于其他快照（{span.snapshot_id}），未丢弃但无法核对",
                source_span_ids=(span_id,),
            )
        else:
            identity_status = "ok"
        if span is not None and (
            block is not None and (span.block_order != block.block_order
                or span.document_part != block.document_part or span.section_index != block.section_index
                or span.table_path != block.table_path)
            or material is not None and (span.source_ref != material.source_ref
                or span.block_order != material.block_order)
            or block is not None and material is not None and raw_text != material.text
        ):
            if identity_status == "ok":
                identity_status = "source_mismatch"
            add_diagnostic(ScopeDiagnosticKind.SOURCE_GEOMETRY_INCONSISTENT,
                "来源定位或冻结文字与原文结构不一致", source_span_ids=(span_id,))
        if raw_text is None:
            add_diagnostic(
                ScopeDiagnosticKind.SOURCE_TEXT_UNAVAILABLE,
                f"来源定位 {span_id} 缺少冻结原文材料",
                source_span_ids=(span_id,),
            )
        elif span is not None and span.excerpt and not _is_literal_fragment(span.excerpt, raw_text):
            if identity_status == "ok":
                identity_status = "excerpt_mismatch"
            add_diagnostic(
                ScopeDiagnosticKind.EXCERPT_NOT_IN_SOURCE_TEXT,
                f"来源定位 {span_id} 的摘录不是原文材料的逐字片段，未丢弃但需核对",
                source_span_ids=(span_id,),
            )
        records.append(
            ReviewScopeSourceRecord(
                source_span_id=span_id,
                source_ref=span.source_ref if span is not None else (
                    material.source_ref if material is not None else ""
                ),
                block_order=span.block_order if span is not None else (
                    material.block_order if material is not None else None
                ),
                raw_text=raw_text,
                excerpt=span.excerpt if span is not None else None,
                table_path=span.table_path if span is not None else None,
                roles=tuple(kind for kind in _ROLE_ORDER if kind in kinds),
                identity_status=identity_status,
            )
        )
    records.sort(
        key=lambda record: (
            record.block_order if record.block_order is not None else 1 << 30,
            record.source_span_id,
        )
    )

    deduped: list[ReviewScopeDiagnostic] = []
    seen: set[ReviewScopeDiagnostic] = set()
    for diagnostic in diagnostics:
        if diagnostic in seen:
            continue
        seen.add(diagnostic)
        deduped.append(diagnostic)

    return ReviewScopeDiscovery(
        candidates=tuple(candidates),
        diagnostics=tuple(deduped),
        source_records=tuple(records),
    )
