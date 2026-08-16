"""Deterministic eligibility-section indexing for Phase 3.

This module is deliberately independent of the legacy deconstructor.  It uses
only the immutable structure blocks, the phase applicability graph and the
source spans produced by the V2 extraction path.  The index is an intermediate
structure: :mod:`app.protocols.catalogs` is responsible for selecting one
phase and applying the publication-facing catalog checks.

Word stores the displayed list number in ``numbering.xml`` rather than in the
paragraph text.  ``NumberingRef`` therefore carries the list template and the
index derives the displayed parent sequence from the first decimal list in a
section.  A concrete number embedded in a synthetic block is accepted only as
an explicit corroborating signal; it never replaces the structural list
boundary or source span.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from app.domain.contracts.enums import (
    AlignmentStatus,
    DocumentPart,
    PhaseScope,
    SourceLocatorPrecision,
    StudyPhase,
)
from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
from app.domain.contracts.protocol_metadata import (
    PhaseApplicabilityBlock,
    PhaseApplicabilityGraph,
)

from .docx_structure import BlockKind, StructureBlock


class SectionIndexError(ValueError):
    """A deterministic structure/phase/source index cannot be trusted."""

    def __init__(self, message: str, *, code: str = "section_index_invalid") -> None:
        super().__init__(message)
        self.code = code


_INCLUSION_HEADING_RE = re.compile(r"(?:入选|纳入)(?:标准|条件)", re.IGNORECASE)
_EXCLUSION_HEADING_RE = re.compile(r"排除(?:标准|条件)", re.IGNORECASE)
_BOTH_HEADING_RE = re.compile(
    r"(?:入选|纳入).{0,8}[/／、和及与].{0,8}排除|"
    r"排除.{0,8}[/／、和及与].{0,8}(?:入选|纳入)",
    re.IGNORECASE,
)
_TOC_STYLE_RE = re.compile(r"(?:^|\b)toc(?:\b|\d)", re.IGNORECASE)
_CHAPTER_PREFIX_RE = re.compile(
    r"^\s*(?:第\s*)?\d+(?!\s*期)(?:\s*[.．]\s*\d+){0,4}\s*[.、)]?\s*"
)
_PAGE_SUFFIX_RE = re.compile(r"\s+\d{1,4}\s*$")
_INLINE_CODE_RE = re.compile(r"(?<![A-Za-z0-9])(?P<prefix>IN|EX)[-_ ]?(?P<number>\d{1,3})(?!\d)", re.IGNORECASE)
_INLINE_NUMBER_RE = re.compile(r"^\s*[（(]?\s*(?P<number>\d{1,3})\s*[)）.．、](?:\s|$)")
_CONCRETE_LIST_NUMBER_RE = re.compile(r"^\s*[（(]?\s*(?P<number>\d{1,3})\s*[)）.．、]?\s*$")
_PHASE_II_RE = re.compile(r"(?:Ⅱ|II|2|二)\s*期", re.IGNORECASE)
_PHASE_III_RE = re.compile(r"(?:Ⅲ|III|3|三)\s*期", re.IGNORECASE)
_SHARED_RE = re.compile(
    r"共同(?:入选|纳入|排除|入排|适用)?标准|两期(?:均|共同|通用)|"
    r"均适用|共同适用|适用于两期|两期通用",
    re.IGNORECASE,
)
_PHASE_PAIR_RE = re.compile(
    r"(?:Ⅱ|II|2|二)\s*期?\s*(?:和|及|与|、|/|／)\s*"
    r"(?:Ⅲ|III|3|三)\s*期|"
    r"(?:Ⅲ|III|3|三)\s*期?\s*(?:和|及|与|、|/|／)\s*"
    r"(?:Ⅱ|II|2|二)\s*期",
    re.IGNORECASE,
)
_PLACEHOLDER_RE = re.compile(
    r"^\s*(?:\[\s*)?(?:placeholder|todo|tbd|n/?a|待补充|待填写|待定|占位|"
    r"未解析|未提取|暂无内容|空白)(?:\s*\])?\s*[。．:：;；_-]*\s*$",
    re.IGNORECASE,
)
_DECIMAL_FORMAT_RE = re.compile(r"decimal", re.IGNORECASE)
_BULLET_OR_LETTER_RE = re.compile(
    r"bullet|letter|roman|ordinal|chineseCounting|enclosedCircleAlpha|symbol",
    re.IGNORECASE,
)
_SECONDARY_LIST_LEVEL_RE = re.compile(r"%[2-9][0-9]*")
_TABLE_ROOT_RE = re.compile(r"^(?P<root>.+?\.t\d+)(?:\.r\d+|\.c\d+)")


@dataclass(frozen=True)
class OfficialParentRuleRange:
    """One official parent rule and its complete contiguous source range."""

    category: str
    official_code: str
    number: int
    label: str
    source_ref: str
    source_refs: tuple[str, ...]
    source_span_ids: tuple[str, ...]
    start_block_order: int
    end_block_order: int
    phase_scopes: tuple[PhaseScope, ...]
    section_id: str
    missing_source_refs: tuple[str, ...] = ()
    explicit_number: bool = False

    @property
    def kind(self) -> str:
        """Compatibility alias used by catalog-facing callers."""

        return self.category

    @property
    def parent_source_ref(self) -> str:
        return self.source_ref

    @property
    def source_range_refs(self) -> tuple[str, ...]:
        return self.source_refs

    @property
    def source_range_span_ids(self) -> tuple[str, ...]:
        return self.source_span_ids

    @property
    def parent_source_span_ids(self) -> tuple[str, ...]:
        return self.source_span_ids


@dataclass(frozen=True)
class EligibilitySection:
    """A paired inclusion/exclusion section candidate."""

    section_id: str
    section_index: int | None
    inclusion_heading_ref: str
    exclusion_heading_ref: str
    start_block_order: int
    end_block_order: int
    inclusion_rules: tuple[OfficialParentRuleRange, ...]
    exclusion_rules: tuple[OfficialParentRuleRange, ...]

    @property
    def rules(self) -> tuple[OfficialParentRuleRange, ...]:
        return self.inclusion_rules + self.exclusion_rules


@dataclass(frozen=True)
class ProtocolSectionIndex:
    """Immutable deterministic index over all discovered section candidates."""

    snapshot_id: str
    sections: tuple[EligibilitySection, ...]
    source_spans: tuple[ProtocolSourceSpan, ...]

    @property
    def inclusion_rules(self) -> tuple[OfficialParentRuleRange, ...]:
        return tuple(rule for section in self.sections for rule in section.inclusion_rules)

    @property
    def exclusion_rules(self) -> tuple[OfficialParentRuleRange, ...]:
        return tuple(rule for section in self.sections for rule in section.exclusion_rules)

    @property
    def official_parent_rules(self) -> tuple[OfficialParentRuleRange, ...]:
        return self.inclusion_rules + self.exclusion_rules

    def for_phase(self, selected_phase: StudyPhase) -> tuple[EligibilitySection, ...]:
        """Return section candidates that contain at least one selected rule."""

        selected_scope = _selected_scope(selected_phase)
        result: list[EligibilitySection] = []
        for section in self.sections:
            if any(_scope_may_match(rule.phase_scopes, selected_scope) for rule in section.rules):
                result.append(section)
        return tuple(result)


# Public aliases make the index discoverable under both names used by the
# design notes and by downstream callers.
SectionIndex = ProtocolSectionIndex
SectionIndexResult = ProtocolSectionIndex
OfficialParentRule = OfficialParentRuleRange


@dataclass(frozen=True)
class _Heading:
    kind: str
    block: StructureBlock


@dataclass(frozen=True)
class _IndexedRange:
    parent: StructureBlock
    number: int
    official_code: str
    source_blocks: tuple[StructureBlock, ...]
    phase_scopes: tuple[PhaseScope, ...]
    source_span_ids: tuple[str, ...]
    missing_source_refs: tuple[str, ...]
    explicit_number: bool


def _stable_section_id(snapshot_id: str, inclusion_ref: str, exclusion_ref: str) -> str:
    raw = f"{snapshot_id}|{inclusion_ref}|{exclusion_ref}".encode("utf-8")
    return f"section-{hashlib.sha256(raw).hexdigest()[:24]}"


def _selected_scope(selected_phase: StudyPhase) -> PhaseScope | None:
    return {
        StudyPhase.PHASE_II: PhaseScope.PHASE_II,
        StudyPhase.PHASE_III: PhaseScope.PHASE_III,
        StudyPhase.SEAMLESS_II_III: PhaseScope.SEAMLESS_CANDIDATE,
    }.get(selected_phase)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("：", ":")).strip()


def _strip_heading_decorations(text: str) -> str:
    value = _normalize_text(text).strip(" \t:：;；。．")
    value = _CHAPTER_PREFIX_RE.sub("", value)
    value = _PAGE_SUFFIX_RE.sub("", value)
    return value.strip(" \t:：;；。．")


def _heading_kind(block: StructureBlock) -> str | None:
    """Classify only a short formal inclusion/exclusion heading.

    Long prose such as "优化 III 期入选/排除标准" and schedule rows such as
    "审核入选/排除标准" are intentionally excluded.  TOC blocks are excluded
    by style and by their chapter/page shape, while table and body headings are
    both supported because real protocols use both forms.
    """

    if block.document_part != DocumentPart.BODY or not _normalize_text(block.text):
        return None
    value = _strip_heading_decorations(block.text)
    if _BOTH_HEADING_RE.search(value):
        return None
    style = (block.style or "").strip()
    if _TOC_STYLE_RE.search(style):
        return None
    raw_text = block.text.strip()
    if (
        block.table_path is None
        and "\t" in raw_text
        and _PAGE_SUFFIX_RE.search(raw_text)
        and _CHAPTER_PREFIX_RE.match(raw_text)
    ):
        return None
    if block.table_path is None and re.match(
        r"^\s*\d+(?:\s*[.．]\s*\d+)+\s+.+\s+\d{1,4}\s*$", _normalize_text(block.text)
    ):
        return None
    # Keep a strict suffix so a prose sentence containing the words is not a
    # section boundary.  Optional phase prefixes are allowed.
    if _INCLUSION_HEADING_RE.fullmatch(value) or re.fullmatch(
        r"(?:Ⅱ|II|2|二|Ⅲ|III|3|三)\s*期\s*" + _INCLUSION_HEADING_RE.pattern, value, re.IGNORECASE
    ):
        return "inclusion"
    if _EXCLUSION_HEADING_RE.fullmatch(value) or re.fullmatch(
        r"(?:Ⅱ|II|2|二|Ⅲ|III|3|三)\s*期\s*" + _EXCLUSION_HEADING_RE.pattern,
        value,
        re.IGNORECASE,
    ):
        return "exclusion"
    return None


def _table_root(block: StructureBlock) -> str | None:
    if block.table_path is None:
        return None
    match = _TABLE_ROOT_RE.match(block.source_ref)
    return match.group("root") if match else None


def _same_container(left: StructureBlock, right: StructureBlock) -> bool:
    if left.document_part != right.document_part or left.section_index != right.section_index:
        return False
    return _table_root(left) == _table_root(right)


def _looks_like_generic_boundary(block: StructureBlock) -> bool:
    if block.document_part != DocumentPart.BODY or not _normalize_text(block.text):
        return False
    if _heading_kind(block) is not None:
        return True
    text = _normalize_text(block.text)
    style = (block.style or "").lower()
    if any(token in style for token in ("heading", "title", "标题")) and len(text) <= 120:
        return True
    numbering = block.numbering
    if numbering is None or len(text) > 120 or _numbering_is_parent_capable(numbering):
        return False
    template = numbering.lvl_text or ""
    return numbering.level <= 2 and _SECONDARY_LIST_LEVEL_RE.search(template) is not None


def _numbering_signature(block: StructureBlock) -> tuple[object, ...] | None:
    numbering = block.numbering
    if numbering is None:
        return None
    template = (numbering.lvl_text or "").strip().lower()
    fmt = (numbering.num_fmt or "").strip().lower()
    # abstract_num_id is stable across numId restarts.  When it is unavailable,
    # numId is the best remaining structural identity.
    family_id: object = (
        "abstract",
        numbering.abstract_num_id,
    ) if numbering.abstract_num_id is not None else ("num", numbering.num_id)
    return (family_id, numbering.level, fmt, template)


def _numbering_is_parent_capable(numbering) -> bool:
    fmt = (numbering.num_fmt or "").strip()
    template = (numbering.lvl_text or "").strip()
    if not fmt or not template or _BULLET_OR_LETTER_RE.search(fmt):
        return False
    if _DECIMAL_FORMAT_RE.search(fmt) is None:
        return False
    if "%1" not in template or _SECONDARY_LIST_LEVEL_RE.search(template):
        return False
    return True


def _explicit_number(block: StructureBlock) -> tuple[int, str | None] | None:
    code_match = _INLINE_CODE_RE.search(block.text)
    if code_match:
        return int(code_match.group("number")), code_match.group("prefix").upper()
    match = _INLINE_NUMBER_RE.match(block.text)
    if match:
        return int(match.group("number")), None
    numbering = block.numbering
    if numbering is not None:
        concrete = _CONCRETE_LIST_NUMBER_RE.fullmatch(numbering.lvl_text or "")
        if concrete:
            return int(concrete.group("number")), None
    return None


def _scope_from_graph(item: PhaseApplicabilityBlock | None) -> tuple[PhaseScope, ...] | None:
    if item is None:
        return None
    return tuple(item.phase_scopes)


def _scope_is_clear(scope: tuple[PhaseScope, ...] | None) -> bool:
    return bool(scope) and not set(scope) & {PhaseScope.UNKNOWN, PhaseScope.MIXED}


def _has_explicit_scope_text(text: str) -> bool:
    normalized = _normalize_text(text)
    return bool(_PHASE_II_RE.search(normalized) or _PHASE_III_RE.search(normalized) or _SHARED_RE.search(normalized))


def _explicit_scope_from_text(text: str) -> tuple[PhaseScope, ...] | None:
    """Return only a phase scope stated in the local source text.

    This deliberately does not consult inherited graph context.  In an
    eligibility category, a short lead-in naming both phases is an official
    shared-list marker; a prose paragraph mentioning both phases remains
    mixed unless it has that pair/applicability shape.
    """

    normalized = _normalize_text(text)
    has_ii = bool(_PHASE_II_RE.search(normalized))
    has_iii = bool(_PHASE_III_RE.search(normalized))
    if _SHARED_RE.search(normalized) or (has_ii and has_iii and _PHASE_PAIR_RE.search(normalized)):
        return (PhaseScope.SHARED,)
    if has_ii and has_iii:
        return (PhaseScope.MIXED,)
    if has_ii:
        return (PhaseScope.PHASE_II,)
    if has_iii:
        return (PhaseScope.PHASE_III,)
    return None


def _container_key(block: StructureBlock) -> tuple[object, ...]:
    return (block.document_part, block.section_index, _table_root(block), block.table_path)


def _effective_scopes(
    blocks: Sequence[StructureBlock],
    graph_by_ref: Mapping[str, PhaseApplicabilityBlock],
) -> dict[str, tuple[PhaseScope, ...] | None]:
    """Resolve only explicit local phase context; never infer from project text."""

    result: dict[str, tuple[PhaseScope, ...] | None] = {}
    context: tuple[PhaseScope, ...] | None = None
    previous_container: tuple[object, ...] | None = None
    for block in sorted(blocks, key=lambda item: (item.block_order, item.source_ref)):
        container = _container_key(block)
        if container != previous_container:
            context = None
            previous_container = container
        local = _scope_from_graph(graph_by_ref.get(block.source_ref))
        clear_local = _scope_is_clear(local)
        explicit = _has_explicit_scope_text(block.text)
        if clear_local:
            result[block.source_ref] = local
            if explicit:
                context = local
            elif context is not None and block.numbering is not None and local != context:
                # A locally different numbered rule ends the inherited run.
                # An UNKNOWN continuation must not silently fall back to the
                # older shared/phase context.
                context = None
            elif context is not None and block.numbering is None:
                # Existing phase_detection may already have assigned a clear
                # inherited scope.  Preserve it for unnumbered lead-in text,
                # but do not let an untagged numbered rule start a new context.
                result[block.source_ref] = local
        else:
            if local is not None and set(local) & {PhaseScope.UNKNOWN, PhaseScope.MIXED} and explicit:
                # An explicit mixed/unknown block clears inherited context;
                # otherwise an unannotated child keeps the surrounding scope.
                context = None
                result[block.source_ref] = local
            else:
                result[block.source_ref] = context if context is not None else local
    return result


def _scope_may_match(scopes: tuple[PhaseScope, ...], selected_scope: PhaseScope | None) -> bool:
    if selected_scope is None:
        return False
    if selected_scope == PhaseScope.SEAMLESS_CANDIDATE:
        return bool(
            set(scopes)
            & {
                PhaseScope.PHASE_II,
                PhaseScope.PHASE_III,
                PhaseScope.SHARED,
                PhaseScope.SEAMLESS_CANDIDATE,
            }
        )
    return selected_scope in scopes or PhaseScope.SHARED in scopes


def _phase_marker(block: StructureBlock, scopes: tuple[PhaseScope, ...] | None) -> bool:
    explicit = _explicit_scope_from_text(block.text)
    return block.numbering is None and (
        _scope_is_clear(explicit) or (_scope_is_clear(scopes) and _has_explicit_scope_text(block.text))
    )


def _placeholder(text: str) -> bool:
    return not _normalize_text(text) or _PLACEHOLDER_RE.fullmatch(_normalize_text(text)) is not None


def _span_lookup(
    source_spans: Mapping[str, ProtocolSourceSpan] | Iterable[ProtocolSourceSpan],
) -> tuple[dict[str, ProtocolSourceSpan], dict[str, ProtocolSourceSpan], tuple[ProtocolSourceSpan, ...]]:
    spans = tuple(source_spans.values()) if isinstance(source_spans, Mapping) else tuple(source_spans)
    by_id: dict[str, ProtocolSourceSpan] = {}
    by_ref: dict[str, ProtocolSourceSpan] = {}
    for span in spans:
        prior_id = by_id.get(span.source_span_id)
        if prior_id is not None and prior_id != span:
            raise SectionIndexError(
                f"来源片段 ID 重复且内容不同：{span.source_span_id}",
                code="source_span_duplicate",
            )
        prior_ref = by_ref.get(span.source_ref)
        if prior_ref is not None and prior_ref.source_span_id != span.source_span_id:
            raise SectionIndexError(
                f"同一 source_ref 对应多个来源片段：{span.source_ref}",
                code="source_ref_ambiguous",
            )
        by_id[span.source_span_id] = span
        by_ref[span.source_ref] = span
    return by_id, by_ref, spans


def _source_spans_for(
    block: StructureBlock,
    graph_item: PhaseApplicabilityBlock | None,
    by_id: Mapping[str, ProtocolSourceSpan],
    by_ref: Mapping[str, ProtocolSourceSpan],
) -> tuple[ProtocolSourceSpan, ...]:
    if graph_item is not None:
        resolved: list[ProtocolSourceSpan] = []
        resolved_ids: set[str] = set()
        for span_id in graph_item.source_span_ids:
            span = by_id.get(span_id) or by_ref.get(span_id)
            if span is not None:
                if span.source_span_id not in resolved_ids:
                    resolved.append(span)
                    resolved_ids.add(span.source_span_id)
        if resolved:
            return tuple(resolved)
    span = by_ref.get(block.source_ref)
    return (span,) if span is not None else ()


def _range_scopes(
    source_blocks: Sequence[StructureBlock],
    effective_scopes: Mapping[str, tuple[PhaseScope, ...] | None],
) -> tuple[PhaseScope, ...]:
    scopes: list[PhaseScope] = []
    for block in source_blocks:
        local = effective_scopes.get(block.source_ref)
        if not local:
            local = (PhaseScope.UNKNOWN,)
        for scope in local:
            if scope not in scopes:
                scopes.append(scope)
    return tuple(scopes) or (PhaseScope.UNKNOWN,)


def _index_category_ranges(
    blocks: Sequence[StructureBlock],
    *,
    category: str,
    start_order: int,
    end_order: int,
    section_id: str,
    effective_scopes: Mapping[str, tuple[PhaseScope, ...] | None],
    graph_by_ref: Mapping[str, PhaseApplicabilityBlock],
    by_id: Mapping[str, ProtocolSourceSpan],
    by_ref: Mapping[str, ProtocolSourceSpan],
) -> tuple[OfficialParentRuleRange, ...]:
    candidates: list[
        tuple[StructureBlock, int, str | None, int, bool, tuple[PhaseScope, ...]]
    ] = []
    parent_signature: tuple[object, ...] | None = None
    # An official eligibility list without a local phase qualifier applies to
    # both selected protocol phases.  Only an explicit lead-in starts a
    # phase-specific run.  This prevents unrelated phase prose before the
    # section from leaking through phase_detection's inherited context.
    run_scope: tuple[PhaseScope, ...] | None = (PhaseScope.SHARED,)
    last_parent: StructureBlock | None = None
    segment_start: int | None = None
    segment_number = 1
    ranges: list[_IndexedRange] = []

    scoped_blocks = [
        block
        for block in blocks
        if start_order <= block.block_order < end_order
        and block.document_part == DocumentPart.BODY
    ]
    scoped_blocks.sort(key=lambda item: (item.block_order, item.source_ref))

    def close_segment(end_index: int) -> None:
        nonlocal segment_start, last_parent
        if segment_start is None or last_parent is None:
            return
        parent_index = next(
            (index for index, block in enumerate(scoped_blocks) if block.source_ref == last_parent.source_ref),
            None,
        )
        if parent_index is None:
            segment_start = None
            last_parent = None
            return
        # The caller supplies the index just before a new parent/phase marker.
        source_blocks = tuple(scoped_blocks[segment_start : end_index + 1])
        # Empty source blocks do not create an official member but remain in the
        # range when a parent has already started.
        source_span_ids: list[str] = []
        missing_refs: list[str] = []
        for source_block in source_blocks:
            graph_item = graph_by_ref.get(source_block.source_ref)
            source_block_spans = _source_spans_for(source_block, graph_item, by_id, by_ref)
            if not source_block_spans:
                if source_block.text.strip():
                    missing_refs.append(source_block.source_ref)
                continue
            for span in source_block_spans:
                if span.source_span_id not in source_span_ids:
                    source_span_ids.append(span.source_span_id)
        parent_info = next(
            item for item in candidates if item[0].source_ref == last_parent.source_ref
        )
        ranges.append(
            _IndexedRange(
                parent=last_parent,
                number=parent_info[1],
                official_code=(
                    f"{category.upper()[:2]}-{parent_info[1]:02d}"
                    if parent_info[2] is None
                    else f"{parent_info[2].upper()}-{parent_info[1]:02d}"
                ),
                source_blocks=source_blocks,
                phase_scopes=parent_info[5],
                source_span_ids=tuple(source_span_ids),
                missing_source_refs=tuple(dict.fromkeys(missing_refs)),
                explicit_number=parent_info[4],
            )
        )
        segment_start = None
        last_parent = None

    for index, block in enumerate(scoped_blocks):
        local_scope = effective_scopes.get(block.source_ref)
        if _phase_marker(block, local_scope):
            close_segment(index - 1)
            parent_signature = None
            segment_number = 1
            explicit_marker_scope = _explicit_scope_from_text(block.text)
            run_scope = (
                explicit_marker_scope
                if _scope_is_clear(explicit_marker_scope)
                else local_scope
                if _scope_is_clear(local_scope)
                else None
            )
            continue

        numbering = block.numbering
        if numbering is None or not _numbering_is_parent_capable(numbering):
            continue
        signature = _numbering_signature(block)
        if signature is None:
            continue
        if parent_signature is None:
            parent_signature = signature
            segment_start = index
        elif signature != parent_signature:
            # Once a run's official Word family is established, every other
            # family is a nested subclause.  A new official family is accepted
            # only after an explicit phase marker reset above; otherwise a
            # decimal child list must not manufacture parent catalog members.
            continue
        else:
            if segment_start is not None and last_parent is not None:
                close_segment(index - 1)
            segment_start = index

        explicit = _explicit_number(block)
        if segment_start == index and segment_number == 1 and numbering.start and numbering.start > 0:
            segment_number = numbering.start
        number = explicit[0] if explicit is not None else segment_number
        explicit_prefix = explicit[1] if explicit is not None else None
        explicit_scope = _explicit_scope_from_text(block.text)
        if explicit_scope is not None:
            parent_scope = explicit_scope
            if run_scope is not None and explicit_scope != run_scope:
                # A local differing rule is not authority for an untagged
                # continuation.  The next UNKNOWN graph member must remain
                # unresolved and be blocked by catalog validation.
                run_scope = None
        elif run_scope is not None:
            parent_scope = run_scope
        else:
            # After a local differing rule, inspect the graph's atomic scope,
            # not this module's inherited effective context.  This is the
            # dependency boundary that keeps an explicitly UNKNOWN
            # continuation unresolved.
            parent_scope = (
                _scope_from_graph(graph_by_ref.get(block.source_ref))
                or (PhaseScope.UNKNOWN,)
            )
        segment_number = number + 1
        last_parent = block
        candidates.append(
            (block, number, explicit_prefix, index, explicit is not None, parent_scope)
        )

    close_segment(len(scoped_blocks) - 1)

    result: list[OfficialParentRuleRange] = []
    for item in ranges:
        parent = item.parent
        prefix = "IN" if category == "inclusion" else "EX"
        # An inline official code is accepted only when its prefix agrees with
        # the section; the numeric portion still comes from the structural
        # sequence and is checked by catalogs.py.
        inline = _explicit_number(parent)
        if inline is not None and inline[1] is not None and inline[1] != prefix:
            raise SectionIndexError(
                f"{category} 章节出现错误官方编号前缀：{parent.source_ref}",
                code="official_code_category_mismatch",
            )
        result.append(
            OfficialParentRuleRange(
                category=category,
                official_code=f"{prefix}-{item.number:02d}",
                number=item.number,
                label=_normalize_text(parent.text),
                source_ref=parent.source_ref,
                source_refs=tuple(block.source_ref for block in item.source_blocks),
                source_span_ids=item.source_span_ids,
                start_block_order=item.source_blocks[0].block_order,
                end_block_order=item.source_blocks[-1].block_order,
                phase_scopes=item.phase_scopes,
                section_id=section_id,
                missing_source_refs=item.missing_source_refs,
                explicit_number=item.explicit_number,
            )
        )
    return tuple(result)


def _headings(blocks: Sequence[StructureBlock]) -> tuple[_Heading, ...]:
    return tuple(
        _Heading(kind=kind, block=block)
        for block in sorted(blocks, key=lambda item: (item.block_order, item.source_ref))
        if (kind := _heading_kind(block)) is not None
    )


def _next_boundary(
    exclusion: StructureBlock,
    blocks: Sequence[StructureBlock],
    headings: Sequence[_Heading],
) -> int:
    candidates = [
        heading.block
        for heading in headings
        if heading.block.block_order > exclusion.block_order
        and _same_container(exclusion, heading.block)
    ]
    if candidates:
        return min(block.block_order for block in candidates)
    for block in sorted(blocks, key=lambda item: (item.block_order, item.source_ref)):
        if block.block_order <= exclusion.block_order or not _same_container(exclusion, block):
            continue
        if _looks_like_generic_boundary(block):
            return block.block_order
    return max((block.block_order for block in blocks), default=exclusion.block_order) + 1


def build_section_index(
    blocks: Sequence[StructureBlock],
    phase_graph: PhaseApplicabilityGraph,
    source_spans: Mapping[str, ProtocolSourceSpan] | Iterable[ProtocolSourceSpan],
    *,
    snapshot_id: str | None = None,
) -> ProtocolSectionIndex:
    """Build a deterministic index of official inclusion/exclusion ranges.

    The function does not select a study phase and does not use any legacy
    extracted rule text.  It keeps all phase candidates in the index so the
    catalog freezer can reject unresolved/mixed members and isolate one phase
    without silently deleting source ranges.
    """

    if not blocks:
        raise SectionIndexError("没有结构块，不能建立入排章节索引", code="empty_structure")
    if not phase_graph.blocks:
        raise SectionIndexError("期别适用图为空，不能建立入排章节索引", code="empty_phase_graph")
    if snapshot_id is not None and snapshot_id != phase_graph.snapshot_id:
        raise SectionIndexError("结构块、期别图和来源快照不是同一快照", code="snapshot_mismatch")
    snapshot_id = phase_graph.snapshot_id
    by_id, by_ref, spans = _span_lookup(source_spans)
    for span in spans:
        if span.snapshot_id != snapshot_id:
            raise SectionIndexError(
                f"来源片段属于另一提取快照：{span.source_span_id}",
                code="source_snapshot_mismatch",
            )

    ordered_blocks = sorted(blocks, key=lambda item: (item.block_order, item.source_ref))
    block_by_ref = {block.source_ref: block for block in ordered_blocks}
    if len(block_by_ref) != len(ordered_blocks):
        raise SectionIndexError("结构块 source_ref 必须唯一", code="source_ref_duplicate")
    graph_by_ref: dict[str, PhaseApplicabilityBlock] = {}
    for item in phase_graph.blocks:
        if item.is_aggregate:
            continue
        if item.source_ref in graph_by_ref:
            raise SectionIndexError(
                f"期别图原子 source_ref 重复：{item.source_ref}",
                code="phase_source_ref_duplicate",
            )
        if item.source_ref not in block_by_ref:
            raise SectionIndexError(
                f"期别图引用不存在的结构块：{item.source_ref}",
                code="phase_source_ref_missing",
            )
        if item.snapshot_id != snapshot_id:
            raise SectionIndexError(
                f"期别图原子块属于另一提取快照：{item.source_ref}",
                code="phase_snapshot_mismatch",
            )
        for span_id in item.source_span_ids:
            span = by_id.get(span_id) or by_ref.get(span_id)
            if span is None:
                raise SectionIndexError(
                    f"期别图引用不存在的来源片段：{span_id}",
                    code="phase_source_span_missing",
                )
            if span.source_ref != item.source_ref:
                raise SectionIndexError(
                    f"期别图来源片段不属于原子块：{span_id}",
                    code="phase_source_span_mismatch",
                )
        graph_by_ref[item.source_ref] = item

    scopes = _effective_scopes(ordered_blocks, graph_by_ref)
    headings = _headings(ordered_blocks)
    pairs: list[tuple[_Heading, _Heading]] = []
    used_exclusion_refs: set[str] = set()
    for heading in headings:
        if heading.kind != "inclusion":
            continue
        candidates = [
            other
            for other in headings
            if other.kind == "exclusion"
            and other.block.block_order > heading.block.block_order
            and other.block.source_ref not in used_exclusion_refs
            and _same_container(heading.block, other.block)
        ]
        if not candidates:
            continue
        exclusion = min(candidates, key=lambda item: (item.block.block_order, item.block.source_ref))
        used_exclusion_refs.add(exclusion.block.source_ref)
        pairs.append((heading, exclusion))

    # Some DOCX files contain a reproduced criteria table before the formal
    # body section (and some contain a table-shaped contents page).  When a
    # top-level BODY heading pair exists, prefer that authoritative body pair;
    # retain table pairs only when the protocol has no body representation.
    body_pairs = [
        pair
        for pair in pairs
        if pair[0].block.table_path is None and pair[1].block.table_path is None
    ]
    if body_pairs:
        pairs = body_pairs

    if not pairs:
        raise SectionIndexError(
            "未能在结构通道中定位成对的入选标准和排除标准章节",
            code="eligibility_sections_missing",
        )

    indexed_sections: list[EligibilitySection] = []
    for inclusion_heading, exclusion_heading in pairs:
        section_id = _stable_section_id(
            snapshot_id,
            inclusion_heading.block.source_ref,
            exclusion_heading.block.source_ref,
        )
        end_order = _next_boundary(exclusion_heading.block, ordered_blocks, headings)
        inclusion_rules = _index_category_ranges(
            ordered_blocks,
            category="inclusion",
            start_order=inclusion_heading.block.block_order + 1,
            end_order=exclusion_heading.block.block_order,
            section_id=section_id,
            effective_scopes=scopes,
            graph_by_ref=graph_by_ref,
            by_id=by_id,
            by_ref=by_ref,
        )
        exclusion_rules = _index_category_ranges(
            ordered_blocks,
            category="exclusion",
            start_order=exclusion_heading.block.block_order + 1,
            end_order=end_order,
            section_id=section_id,
            effective_scopes=scopes,
            graph_by_ref=graph_by_ref,
            by_id=by_id,
            by_ref=by_ref,
        )
        if not inclusion_rules or not exclusion_rules:
            # A contents/summary line may spell both headings but cannot be an
            # eligibility section without official Word parent-list runs in
            # both categories.
            continue
        indexed_sections.append(
            EligibilitySection(
                section_id=section_id,
                section_index=inclusion_heading.block.section_index,
                inclusion_heading_ref=inclusion_heading.block.source_ref,
                exclusion_heading_ref=exclusion_heading.block.source_ref,
                start_block_order=inclusion_heading.block.block_order,
                end_block_order=end_order,
                inclusion_rules=inclusion_rules,
                exclusion_rules=exclusion_rules,
            )
        )

    if not indexed_sections:
        raise SectionIndexError(
            "入排标题候选均缺少完整的官方父规则列表",
            code="eligibility_sections_missing",
        )
    indexed_sections.sort(key=lambda item: (item.start_block_order, item.section_id))
    return ProtocolSectionIndex(
        snapshot_id=snapshot_id,
        sections=tuple(indexed_sections),
        source_spans=spans,
    )


# Naming aliases used by callers that describe the operation as indexing.
index_protocol_sections = build_section_index
build_protocol_section_index = build_section_index


def is_placeholder_label(text: str) -> bool:
    """Public placeholder predicate shared by catalog validation/tests."""

    return _placeholder(text)


def formal_source_span_ids(source_spans: Iterable[ProtocolSourceSpan]) -> frozenset[str]:
    """Return spans that satisfy the formal, non-degraded source locator rule.

    ``TEXT_RANGE`` and ``PAGE_ONLY`` are physical claims.  A duplicate range or
    duplicate page-only locator is not unique and is therefore not authoritative.
    """

    spans = tuple(source_spans)
    range_counts: dict[tuple[str, int, int, int], int] = {}
    page_counts: dict[tuple[str, int], int] = {}
    for span in spans:
        if (
            span.alignment_status != AlignmentStatus.ALIGNED
            or span.render_artifact_id is None
            or span.render_page is None
        ):
            continue
        if (
            span.precision == SourceLocatorPrecision.TEXT_RANGE
            and span.text_start is not None
            and span.text_end is not None
        ):
            key = (span.render_artifact_id, span.render_page, span.text_start, span.text_end)
            range_counts[key] = range_counts.get(key, 0) + 1
        elif span.precision == SourceLocatorPrecision.PAGE_ONLY:
            key = (span.render_artifact_id, span.render_page)
            page_counts[key] = page_counts.get(key, 0) + 1

    formal: set[str] = set()
    for span in spans:
        if (
            span.alignment_status != AlignmentStatus.ALIGNED
            or span.render_artifact_id is None
            or span.render_page is None
        ):
            continue
        if (
            span.precision == SourceLocatorPrecision.TEXT_RANGE
            and span.text_start is not None
            and span.text_end is not None
        ):
            key = (span.render_artifact_id, span.render_page, span.text_start, span.text_end)
            if range_counts.get(key) == 1:
                formal.add(span.source_span_id)
        elif span.precision == SourceLocatorPrecision.PAGE_ONLY:
            key = (span.render_artifact_id, span.render_page)
            if page_counts.get(key) == 1:
                formal.add(span.source_span_id)
    return frozenset(formal)
