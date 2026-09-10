"""Deterministic phase applicability graph and single-phase projection.

The graph is built from paragraph, table-row and visit-column structure blocks.
It never treats the words "操作无缝", dose hand-off, or new Phase III
participants as evidence that the same subjects continue across phases.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from app.domain.contracts.enums import (
    ApplicabilityGranularity,
    DocumentPart,
    MetadataSourceKind,
    PhaseDesignType,
    PhaseScope,
    StudyPhase,
)
from app.domain.contracts.protocol_metadata import (
    PhaseApplicabilityBlock,
    PhaseApplicabilityGraph,
    PhaseProjection,
    SeamlessPhaseCandidate,
    StudyPhaseCandidate,
)

from .docx_structure import StructureBlock

_CELL_REF_RE = re.compile(
    r"^(?P<table>.+?\.t\d+)\.r(?P<row>\d+)\.c(?P<col>\d+)(?:\.p\d+)?$"
)

_PHASE_II_TOKEN_RE = r"(?<![A-Za-z0-9])(?:Ⅱ|II|2|二)\s*期"
_PHASE_III_TOKEN_RE = r"(?<![A-Za-z0-9])(?:Ⅲ|III|3|三)\s*期"
# A slash is phase syntax only when it forms a complete II/III pair whose
# final member carries the phase marker.  Without this guard, ordinary values
# such as ``PGA 3/4`` and ``访视周数 2/3`` become false phase references.
_PHASE_PAIR_RE = (
    r"(?<![A-Za-z0-9])(?:Ⅱ|II|2|二)\s*(?:期\s*)?"
    r"(?:临床研究)?(?:阶段)?\s*"
    r"(?:和|及|与|、|/|／)\s*"
    r"(?:Ⅲ|III|3|三)\s*期\s*(?:临床研究)?(?:阶段)?"
)
_PHASE_II_RE = re.compile(
    rf"(?:{_PHASE_II_TOKEN_RE}|{_PHASE_PAIR_RE})", re.I
)
_PHASE_III_RE = re.compile(
    rf"(?:{_PHASE_III_TOKEN_RE}|{_PHASE_PAIR_RE})", re.I
)
_SHARED_WITHOUT_PHASE_RE = re.compile(
    r"均适用|共同适用|适用于两期|两期(?:均|共同)|各期(?:均|共同)"
    r"|共同(?:入选|纳入|排除|入排|适用)标准|两期通用(?:标准|要求|程序)",
    re.I,
)
_SHARED_AFTER_PAIR_RE = re.compile(
    _PHASE_PAIR_RE
    + r".{0,60}(?:相同|一致|共同|均适用|均采用|均进行|均需|均应|使用|采用|选择|用)",
    re.I,
)
_SHARED_BEFORE_PAIR_RE = re.compile(
    r"(?:相同|一致|共同|均适用).{0,30}" + _PHASE_PAIR_RE,
    re.I,
)
_SHARED_CRITERIA_AFTER_PAIR_RE = re.compile(
    _PHASE_PAIR_RE
    + r"(?:中|内|的)?\s*(?:受试者|参与者)?\s*"
    + r"(?:均)?(?:符合|满足|遵守|执行|完成|需|应)"
    + r".{0,30}(?:以下|下列|所有|任一)?\s*(?:标准|条件|要求|检查|程序|操作)",
    re.I,
)
_PHASE_PAIR_FULL_RE = re.compile(_PHASE_PAIR_RE, re.I)
_SEAMLESS_DESIGN_RE = re.compile(
    r"无缝\s*(?:适应性)?\s*(?:设计|研究|试验)|seamless\s+(?:adaptive\s+)?(?:design|trial)",
    re.I,
)
_SAME_COHORT_RE = re.compile(
    r"同一(?:受试者|参与者)(?:队列|批)|同一队列"
    r"|same\s+cohort|same\s+(?:subjects|participants).*?(?:continue|across\s+phases)",
    re.I,
)
_DISQUALIFYING_RE = re.compile(
    r"操作无缝|剂量(?:选择|衔接|转换|调整)|继续纳入(?:新的?|新增加的?)?(?:受试者|参与者)"
    r"|新(?:的)?(?:受试者|参与者)|另行纳入|继续入组(?:新|其他)",
    re.I,
)
_VISIT_RE = re.compile(
    r"筛选|导入|基线|随机|(?:D|W|V)\s*[-]?\s*\d+|访视|visit",
    re.I,
)
_TABLE_APPLICABILITY_HEADING_RE = re.compile(
    r"(?:研究)?(?:流程|日程|访视)(?:图|表)|临床研究阶段流程表",
    re.I,
)
# Table cells often carry plain ``Normal`` paragraphs rather than a Word
# outline style.  Keep the fallback deliberately narrow: only a phase marker
# at the start of the paragraph followed by a small vocabulary of heading
# nouns can establish context.  Narrative such as ``Ⅱ期计划在...`` therefore
# remains local evidence and cannot retag the rest of the cell.
_PLAIN_PHASE_HEADING_RE = re.compile(
    r"^(?:[（(]?\s*(?:\d+|[一二三四五六七八九十]+)\s*[）).、]\s*|[-–—•·]\s*)?"
    r"(?:Ⅱ|II|2|二|Ⅲ|III|3|三)\s*期"
    r"(?:临床)?(?:研究|试验)?"
    r"(?:阶段|部分|入选标准|排除标准|适用标准|共同标准|标准|要求|"
    r"设计|方案|流程|日程|主要终点|次要终点|研究目的|队列|治疗|给药)?"
    r"\s*[：:]?\s*$",
    re.I,
)
_PHASE_CONTENT_LEAD_IN_RE = re.compile(
    r"(?:"
    # ``如下的假设检验`` / ``以下的定义`` style lead-ins.
    r"(?:具体|内容)?(?:如下|以下|下列)(?:所示|列示|列出)?(?:的)?"
    r"(?:假设(?:检验)?|定义|公式|参数|列表|说明|内容|方法|步骤|状态)"
    # ``假设如下`` / ``公式如下所示`` style lead-ins.
    r"|(?:假设(?:检验)?|定义|公式|参数|列表|说明|内容|方法|步骤|状态)"
    r"(?:如下|如下所示|如下列出)"
    # ``内容如下`` is still typed; a bare ``如下`` is intentionally not.
    r")\s*[：:]",
    re.I,
)
_MAX_OUTLINE_LEVEL = 8


@dataclass(frozen=True)
class PhaseDetectionResult:
    graph: PhaseApplicabilityGraph
    phase_candidates: tuple[StudyPhaseCandidate, ...]


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"phase-{digest}"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("：", ":")).strip()


def _scope_from_text(
    text: str,
    inherited: tuple[PhaseScope, ...] | None = None,
) -> tuple[tuple[PhaseScope, ...], bool]:
    """Classify one local source unit conservatively.

    A phase mention is not enough to call a unit shared.  When both phases
    occur without an explicit local shared marker, the unit is ``MIXED`` and
    cannot enter a normal single-phase projection.  Untagged table cells are
    ``UNKNOWN`` until a nearby row/column header provides a narrow inheritance
    signal; they are never silently promoted to shared.
    """

    text = _normalize(text)
    has_ii = bool(_PHASE_II_RE.search(text))
    has_iii = bool(_PHASE_III_RE.search(text))
    shared_evidence = _has_shared_evidence(text, has_ii=has_ii, has_iii=has_iii)
    if shared_evidence and not _has_unpaired_phase_reference(text):
        return (PhaseScope.SHARED,), True
    if has_ii and has_iii:
        return (PhaseScope.MIXED,), False
    if has_ii:
        return (PhaseScope.PHASE_II,), False
    if has_iii:
        return (PhaseScope.PHASE_III,), False
    if inherited:
        return inherited, False
    return (PhaseScope.UNKNOWN,), False


def _has_shared_evidence(text: str, *, has_ii: bool, has_iii: bool) -> bool:
    """Recognize only a local, explicit shared-applicability statement.

    A generic ``共同`` in an untagged procedure or table heading is not enough
    to classify a source unit as shared.  A sentence naming both phases and
    declaring the requirement/standard the same is explicit local evidence.
    """

    if _SHARED_WITHOUT_PHASE_RE.search(text) and not has_ii and not has_iii:
        return True
    return has_ii and has_iii and bool(
        _SHARED_AFTER_PAIR_RE.search(text)
        or _SHARED_BEFORE_PAIR_RE.search(text)
        or _SHARED_CRITERIA_AFTER_PAIR_RE.search(text)
    )


def _has_unpaired_phase_reference(text: str) -> bool:
    """Detect a phase mention outside the explicit shared pair.

    For example, ``II期阶段性分析、II期和III期研究结束时`` contains a shared
    pair plus a phase-II-only event.  It is mixed content and must not be
    projected as a shared aggregate merely because a later sentence says
    ``共同批准``.
    """

    spans = [match.span() for match in _PHASE_PAIR_FULL_RE.finditer(text)]
    if not spans:
        return False
    residual: list[str] = []
    cursor = 0
    for start, end in spans:
        residual.append(text[cursor:start])
        cursor = end
    residual.append(text[cursor:])
    return bool(_PHASE_II_RE.search(" ".join(residual)) or _PHASE_III_RE.search(" ".join(residual)))

def _has_phase_content_lead_in(text: str) -> bool:
    """Return whether a typed forward lead-in follows a local phase marker."""

    lead_in = _PHASE_CONTENT_LEAD_IN_RE.search(text)
    if lead_in is None:
        return False
    phase_markers = (
        *tuple(_PHASE_II_RE.finditer(text)),
        *tuple(_PHASE_III_RE.finditer(text)),
    )
    return any(marker.start() <= lead_in.start() for marker in phase_markers)


def _looks_like_heading(block: StructureBlock) -> bool:
    """Return whether a block has an authoritative structural heading marker.

    Phase context is a source-structure fact, not a lexical guess.  In
    particular, a short paragraph or a paragraph whose raw style ID happens to
    contain ``heading`` is not enough: Word documents frequently use numeric
    custom style IDs, and ordinary numbered rules can look like headings.
    ``outline_level`` is populated by the DOCX extractor from the effective
    paragraph style/paragraph properties, so it is the only heading signal
    used here.  The text-length guard keeps empty/very large paragraphs from
    becoming context anchors while retaining the original block as an atomic
    source node.
    """

    text = _normalize(block.text)
    level = block.outline_level
    return bool(
        text
        and len(text) <= 120
        and block.document_part == DocumentPart.BODY
        and block.table_path is None
        and isinstance(level, int)
        and 0 <= level <= _MAX_OUTLINE_LEVEL
    )


def _establishes_scope_context(
    block: StructureBlock,
    scopes: tuple[PhaseScope, ...],
) -> bool:
    """Return whether an explicit local statement governs following siblings.

    A phase name inside an ordinary sentence must not silently retag subsequent
    paragraphs.  Context starts only from a heading or an applicability lead-in
    such as "III期符合下列所有标准", or a typed forward lead-in such as
    "III期的假设如下：".  The latter is deliberately vocabulary- and
    punctuation-bounded: a phase mention followed by ordinary narrative,
    comparison, or cross-reference text remains local evidence.
    """

    if not _scope_is_clear(scopes):
        return False
    text = _normalize(block.text)
    phase_table_caption = bool(
        len(text) <= 120
        and re.match(r"^(?:表|附表)\s*\d+\s*", text)
        and _TABLE_APPLICABILITY_HEADING_RE.search(text)
    )
    return bool(
        _looks_like_heading(block)
        or (
            block.document_part == DocumentPart.BODY
            and _PLAIN_PHASE_HEADING_RE.fullmatch(text) is not None
        )
        # A phase-specific visit-table caption also governs its trailing
        # notes and procedure explanations. DOCX protocols commonly render
        # these captions as ordinary paragraphs rather than outline headings.
        or (
            block.document_part == DocumentPart.BODY
            and block.table_path is None
            and phase_table_caption
        )
        # Typed forward lead-ins bind the immediately following source units
        # to the phase, subject to the structural boundary tracked by the
        # caller.  Do not broaden this to any ``如下``/``以下`` phrase.
        or _has_phase_content_lead_in(text)
        or re.search(
            r"(?:符合|满足|遵守|执行|完成|适用于|需|应).{0,35}"
            r"(?:以下|下列|所有|任一|标准|条件|要求|程序|操作)",
            text,
        )
    )


def _scope_with_context(
    text: str,
    inherited: tuple[PhaseScope, ...] | None,
    *,
    allow_local_context_switch: bool,
) -> tuple[tuple[PhaseScope, ...], bool]:
    """Apply a local signal without letting ordinary references switch scope.

    ``_scope_from_text`` describes the words in one source unit.  This helper
    adds the structural applicability context: an explicit shared statement
    always wins, a real heading/applicability lead-in may switch the context,
    and an ordinary phase mention remains local evidence only when there is no
    clear inherited scope.  A sentence comparing the opposite phase therefore
    cannot reclassify the surrounding section.
    """

    local, cross_phase = _scope_from_text(text)
    if inherited is None or not _scope_is_clear(inherited):
        return local, cross_phase
    if local == (PhaseScope.SHARED,) or allow_local_context_switch:
        return local, cross_phase
    return inherited, cross_phase


def _body_contexts(blocks: Sequence[StructureBlock]) -> Mapping[str, tuple[PhaseScope, ...]]:
    """Infer narrow heading/table-caption context; neutral content stays unknown."""

    context: tuple[PhaseScope, ...] | None = None
    context_heading_level: int | None = None
    # Retain the active structural heading path independently from the phase
    # context.  A plain lead-in can establish a phase while its enclosing
    # heading remains the boundary for later siblings.
    heading_levels: list[int] = []
    result: dict[str, tuple[PhaseScope, ...]] = {}
    for block in sorted(blocks, key=lambda item: item.block_order):
        if block.document_part != DocumentPart.BODY or block.table_path is not None:
            continue

        is_heading = _looks_like_heading(block)
        heading_level = block.outline_level if is_heading else None
        if is_heading and heading_level is not None:
            # Same-level and ancestor headings close a prior context; deeper
            # headings remain inside the current context's boundary.
            heading_levels = [
                level for level in heading_levels if level < heading_level
            ]
            heading_levels.append(heading_level)
        nearest_heading_level = heading_levels[-1] if heading_levels else None

        text = _normalize(block.text)
        explicit, _shared = _scope_from_text(text)
        has_explicit = bool(_PHASE_II_RE.search(text) or _PHASE_III_RE.search(text))
        if has_explicit or explicit == (PhaseScope.SHARED,):
            establishes_context = _establishes_scope_context(block, explicit)
            effective, _cross = _scope_with_context(
                text,
                context,
                allow_local_context_switch=establishes_context,
            )
            result[block.source_ref] = effective
            if establishes_context:
                # The local scope of this block and the context governing
                # later siblings are separate facts.  A heading or explicit
                # applicability lead-in may replace the structural context.
                context = explicit
                context_heading_level = (
                    heading_level if is_heading else nearest_heading_level
                )
            elif is_heading:
                # A structural heading with an unclear/mixed phase scope is a
                # real boundary, but it cannot safely establish inheritance.
                context = None
                context_heading_level = None
            # Keep ordinary phase references in the source text, but do not
            # let them erase a context established by an enclosing heading or
            # create one when no such heading exists.
        else:
            if is_heading:
                level = heading_level
                if (
                    context is not None
                    and context_heading_level is not None
                    and level is not None
                    and level > context_heading_level
                ):
                    # A heading nested below an explicit phase heading may
                    # inherit that phase.  A same-level or ancestor heading
                    # closes the previous phase context instead of leaking it
                    # into an unrelated section.  Keep the original phase
                    # heading as the boundary: updating this value to the
                    # first child would make the next sibling look like a
                    # boundary and drop the still-valid phase context.
                    result[block.source_ref] = context
                else:
                    result[block.source_ref] = (PhaseScope.UNKNOWN,)
                    context = None
                    context_heading_level = None
            else:
                result[block.source_ref] = context or (PhaseScope.UNKNOWN,)
    return result


def _table_groups(blocks: Sequence[StructureBlock]):
    groups: dict[tuple[str, int], list[StructureBlock]] = {}
    for block in blocks:
        match = _CELL_REF_RE.match(block.source_ref)
        if not match:
            continue
        key = (match.group("table"), int(match.group("row")))
        groups.setdefault(key, []).append(block)
    return groups


def _table_heading_scopes(
    blocks: Sequence[StructureBlock],
    body_contexts: Mapping[str, tuple[PhaseScope, ...]] | None = None,
) -> Mapping[str, tuple[PhaseScope, ...]]:
    """Bind a top-level table to its nearest explicit applicability heading.

    Visit matrices commonly carry the phase only in the paragraph immediately
    before the table; their cells contain clinical operations and X marks, not
    the words II/III. A heading naming one phase applies that phase to the
    following table. A heading explicitly naming a shared flow/schedule table
    for both phases applies to both as shared content, not as mixed prose.
    """
    ordered = sorted(blocks, key=lambda item: item.block_order)
    top_level = [
        block
        for block in ordered
        if block.document_part == DocumentPart.BODY and block.table_path is None
    ]
    result: dict[str, tuple[PhaseScope, ...]] = {}
    body_contexts = body_contexts or {}
    for index, block in enumerate(top_level):
        if not re.fullmatch(r"body\.t\d+", block.source_ref):
            continue

        # The table root occupies the same source-order position as the table
        # in the body stream.  If the structural walker has already proven a
        # clear phase context there, use that context directly; this covers
        # tables whose cells and ordinary table title do not repeat II/III.
        # UNKNOWN is deliberately not promoted and falls through to the
        # narrow explicit-title check below.
        structural_scope = body_contexts.get(block.source_ref)
        if structural_scope is not None and _scope_is_clear(structural_scope):
            result[block.source_ref] = structural_scope
            continue

        inspected = 0
        for candidate in reversed(top_level[:index]):
            if re.fullmatch(r"body\.t\d+", candidate.source_ref):
                break
            text = _normalize(candidate.text)
            if not text:
                continue
            inspected += 1
            if inspected > 12 or candidate.section_index != block.section_index:
                break
            has_ii = bool(_PHASE_II_RE.search(text))
            has_iii = bool(_PHASE_III_RE.search(text))
            if not (has_ii or has_iii):
                continue
            if not _TABLE_APPLICABILITY_HEADING_RE.search(text):
                # A nearby narrative phase mention is not table authority.
                continue
            if has_ii and has_iii:
                result[block.source_ref] = (PhaseScope.SHARED,)
            elif has_ii:
                result[block.source_ref] = (PhaseScope.PHASE_II,)
            else:
                result[block.source_ref] = (PhaseScope.PHASE_III,)
            break
    return result


def _table_is_visit_table(groups: Mapping[tuple[str, int], list[StructureBlock]], table: str) -> bool:
    rows = [
        cells
        for (name, _row), cells in sorted(groups.items(), key=lambda item: item[0][1])
        if name == table
    ]
    sample = " ".join(_normalize(cell.text) for cells in rows[:3] for cell in cells)
    return bool(_VISIT_RE.search(sample))


def _scope_is_clear(scopes: tuple[PhaseScope, ...]) -> bool:
    return bool(scopes) and not set(scopes) & {PhaseScope.MIXED, PhaseScope.UNKNOWN}


def _combine_child_scopes(
    child_scopes: Sequence[tuple[PhaseScope, ...]],
) -> tuple[PhaseScope, ...]:
    """Aggregate local scopes without letting one hit dominate a mixed node."""

    if not child_scopes:
        return (PhaseScope.UNKNOWN,)
    flattened = {scope for scopes in child_scopes for scope in scopes}
    if PhaseScope.MIXED in flattened:
        return (PhaseScope.MIXED,)
    if PhaseScope.PHASE_II in flattened and PhaseScope.PHASE_III in flattened:
        return (PhaseScope.MIXED,)
    if PhaseScope.UNKNOWN in flattened:
        return (PhaseScope.UNKNOWN,)
    # An aggregate may inherit a scope only when every local child agrees.  A
    # phase-specific child next to a shared child is still mixed; retaining a
    # union such as [II, shared] would make both single-phase projections
    # consume the same aggregate and lose source ownership.
    first = child_scopes[0]
    if all(scopes == first for scopes in child_scopes[1:]):
        return first
    return (PhaseScope.MIXED,)


def _clear_header_scope(cells: Sequence[StructureBlock]) -> tuple[PhaseScope, ...] | None:
    """Return only a clear first-cell header signal for local inheritance."""

    for cell in sorted(cells, key=lambda item: (item.block_order, item.source_ref)):
        if not _normalize(cell.text):
            continue
        scopes, _shared = _scope_from_text(cell.text)
        if _scope_is_clear(scopes) and (
            _establishes_scope_context(cell, scopes)
            or (
                scopes == (PhaseScope.SHARED,)
                and _has_shared_evidence(
                    _normalize(cell.text),
                    has_ii=False,
                    has_iii=False,
                )
            )
        ):
            return scopes
        return None
    return None


def _table_root(source_ref: str) -> str | None:
    match = re.match(r"^(?P<table>.+?\.t\d+)(?:\.r\d+|\.c\d+)", source_ref)
    return match.group("table") if match else None


def _projection_text(text: str, selected_phase: StudyPhase) -> str:
    label = "Ⅱ期" if selected_phase == StudyPhase.PHASE_II else "Ⅲ期"
    cleaned = text
    cleaned = re.sub(
        _PHASE_PAIR_RE + r"\s*(?:相同|一致)",
        label,
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(_PHASE_PAIR_RE, label, cleaned, flags=re.I)
    cleaned = re.sub(
        r"(?:Ⅱ|II|2|二)\s*期+\s*(?:临床研究)?(?:阶段)?\s*"
        r"(?:和|及|与|、|/|／)\s*"
        r"(?:Ⅲ|III|3|三)\s*期+\s*(?:临床研究)?(?:阶段)?",
        label,
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"与\s*(?:Ⅱ|II)\s*期\s*(?:相同|一致)", "", cleaned, flags=re.I)
    cleaned = re.sub(r"与\s*(?:Ⅲ|III)\s*期\s*(?:相同|一致)", "", cleaned, flags=re.I)
    cleaned = re.sub(r"(?:Ⅱ|II)\s*[/、和及与]\s*(?:Ⅲ|III)\s*期", label, cleaned, flags=re.I)
    cleaned = re.sub(r"(?:两期|共同适用)", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" ，,；;:") or label


def _make_block(
    *,
    snapshot_id: str,
    source_ref: str,
    source_span_ids: list[str],
    granularity: ApplicabilityGranularity,
    source_order: int,
    text: str,
    scopes: tuple[PhaseScope, ...],
    table_path: tuple[int, ...] | None = None,
    table_row: int | None = None,
    visit_column: int | None = None,
    cross_phase: bool = False,
    is_aggregate: bool = False,
    child_block_ids: list[str] | None = None,
) -> PhaseApplicabilityBlock:
    return PhaseApplicabilityBlock(
        block_id=_stable_id(snapshot_id, source_ref, granularity.value),
        snapshot_id=snapshot_id,
        source_ref=source_ref,
        source_span_ids=source_span_ids,
        granularity=granularity,
        source_order=source_order,
        # Keep the source payload intact.  Consumer-facing phase wording is
        # derived in ``projection_text`` and never replaces this field.
        text=text,
        phase_scopes=list(scopes),
        table_path=table_path,
        table_row=table_row,
        visit_column=visit_column,
        cross_phase_comparison=cross_phase,
        projection_text=None,
        is_aggregate=is_aggregate,
        child_block_ids=child_block_ids or [],
    )


def _seamless_candidate(
    blocks: Sequence[PhaseApplicabilityBlock],
    *,
    snapshot_id: str,
) -> SeamlessPhaseCandidate | None:
    # A row/column aggregate is a derived view and must not manufacture a
    # seamless candidate.  Candidate evidence must point to an atomic source
    # block so the same-subject-space decision remains reviewable.
    atomic = [item for item in blocks if not item.is_aggregate]
    design_blocks = [item for item in atomic if _SEAMLESS_DESIGN_RE.search(item.text)]
    cohort_blocks = [item for item in atomic if _SAME_COHORT_RE.search(item.text)]
    disqualifying = [item for item in atomic if _DISQUALIFYING_RE.search(item.text)]
    if not design_blocks or not cohort_blocks or disqualifying:
        return None
    design = design_blocks[0]
    cohort = cohort_blocks[0]
    source_refs = list(dict.fromkeys([design.source_ref, cohort.source_ref]))
    return SeamlessPhaseCandidate(
        candidate_id=_stable_id(snapshot_id, "seamless", *source_refs),
        snapshot_id=snapshot_id,
        source_refs=source_refs,
        explicit_design_excerpt=design.text,
        same_cohort_excerpt=cohort.text,
        supporting_source_refs=source_refs,
    )


def _add_phase_candidate(
    phase_candidates: list[StudyPhaseCandidate],
    *,
    snapshot_id: str,
    block: StructureBlock,
    scopes: tuple[PhaseScope, ...],
    source_span_id: str,
) -> None:
    """Append a traceable phase candidate for an explicit source unit."""

    text = block.text
    if not (_PHASE_II_RE.search(text) or _PHASE_III_RE.search(text)):
        return
    phase_candidates.append(
        StudyPhaseCandidate(
            candidate_id=_stable_id(snapshot_id, "phase-candidate", block.source_ref),
            snapshot_id=snapshot_id,
            phase_scopes=list(scopes),
            design_type=(
                PhaseDesignType.SHARED_CONTENT
                if scopes == (PhaseScope.SHARED,)
                else PhaseDesignType.INDEPENDENT
            ),
            source_ref=block.source_ref,
            source_span_id=source_span_id,
            source_kind=(
                MetadataSourceKind.BODY
                if block.document_part == DocumentPart.BODY
                else MetadataSourceKind.HEADER_FOOTER
            ),
            excerpt=_normalize(text),
            priority_rank=40,
            confidence_basis=["局部结构块明确期别标记"],
            requires_confirmation=(
                scopes not in {
                    (PhaseScope.PHASE_II,),
                    (PhaseScope.PHASE_III,),
                    (PhaseScope.SHARED,),
                }
            ),
        )
    )


def _effective_table_scopes(
    groups: Mapping[tuple[str, int], list[StructureBlock]],
    table_heading_scopes: Mapping[str, tuple[PhaseScope, ...]],
) -> dict[str, tuple[tuple[PhaseScope, ...], bool]]:
    """Classify each table cell from local text plus narrow headers.

    Row and column hints are intentionally one-cell signals.  A clear local
    heading/applicability lead-in may switch them, while an ordinary phase
    mention inherits the established context.  Conflicting row/column hints
    become ``MIXED``.
    """

    all_cells = [cell for cells in groups.values() for cell in cells]
    columns: dict[tuple[str, int], list[StructureBlock]] = {}
    for cell in all_cells:
        match = _CELL_REF_RE.match(cell.source_ref)
        if match is None:
            continue
        key = (match.group("table"), int(match.group("col")))
        columns.setdefault(key, []).append(cell)
    row_hints = {key: _clear_header_scope(cells) for key, cells in groups.items()}
    column_hints = {key: _clear_header_scope(cells) for key, cells in columns.items()}
    result: dict[str, tuple[tuple[PhaseScope, ...], bool]] = {}
    cell_contexts: dict[tuple[str, int, int], tuple[PhaseScope, ...]] = {}
    for (table, row), cells in groups.items():
        row_hint = row_hints[(table, row)]
        for cell in sorted(cells, key=lambda item: (item.block_order, item.source_ref)):
            local, _local_cross = _scope_from_text(cell.text)
            match = _CELL_REF_RE.match(cell.source_ref)
            cell_key = (
                table,
                row,
                int(match.group("col")) if match is not None else -1,
            )
            col_hint = (
                column_hints.get((table, int(match.group("col"))))
                if match is not None
                else None
            )
            if row_hint and col_hint:
                inherited = row_hint if row_hint == col_hint else (PhaseScope.MIXED,)
            else:
                inherited = (
                    row_hint
                    or col_hint
                    or table_heading_scopes.get(table)
                    or (PhaseScope.UNKNOWN,)
                )
            cell_context = cell_contexts.get(cell_key)
            inherited = cell_context or inherited
            effective, effective_cross = _scope_with_context(
                cell.text,
                inherited,
                allow_local_context_switch=_establishes_scope_context(cell, local),
            )
            result[cell.source_ref] = (
                effective,
                effective_cross if local != (PhaseScope.UNKNOWN,) else False,
            )
            if _establishes_scope_context(cell, local) and _scope_is_clear(local):
                cell_contexts[cell_key] = local
    return result


def build_phase_applicability_graph(
    blocks: Sequence[StructureBlock],
    *,
    snapshot_id: str,
    source_span_ids: Mapping[str, str] | None = None,
) -> PhaseDetectionResult:
    """Build paragraph/table-row/visit-column applicability nodes."""

    if not blocks:
        raise ValueError("没有结构块，不能建立期别适用图")
    contexts = _body_contexts(blocks)
    nodes: list[PhaseApplicabilityBlock] = []
    phase_candidates: list[StudyPhaseCandidate] = []

    # Body/header/footer top-level paragraphs are atomic source nodes.  Table
    # cells are also atomic paragraph nodes; rows/columns below are derived
    # aggregates with explicit child ownership.
    table_blocks = [block for block in blocks if block.table_path is not None]
    body_blocks = [block for block in blocks if block.table_path is None]
    for block in body_blocks:
        if not _normalize(block.text):
            continue
        local_scopes, cross = _scope_from_text(block.text)
        scopes = contexts.get(block.source_ref, local_scopes)
        span_ref = (source_span_ids or {}).get(block.source_ref, block.source_ref)
        nodes.append(
            _make_block(
                snapshot_id=snapshot_id,
                source_ref=block.source_ref,
                source_span_ids=[span_ref],
                granularity=ApplicabilityGranularity.PARAGRAPH,
                source_order=block.block_order,
                text=block.text,
                scopes=scopes,
                cross_phase=cross,
            )
        )
        _add_phase_candidate(
            phase_candidates,
            snapshot_id=snapshot_id,
            block=block,
            scopes=scopes,
            source_span_id=span_ref,
        )

    groups = _table_groups(table_blocks)
    effective = _effective_table_scopes(
        groups,
        _table_heading_scopes(blocks, contexts),
    )
    atomic_by_ref: dict[str, PhaseApplicabilityBlock] = {}
    for cell in sorted(table_blocks, key=lambda item: (item.block_order, item.source_ref)):
        if not _normalize(cell.text):
            continue
        match = _CELL_REF_RE.match(cell.source_ref)
        if match is None:
            continue
        scopes, cross = effective.get(cell.source_ref, ((PhaseScope.UNKNOWN,), False))
        span_ref = (source_span_ids or {}).get(cell.source_ref, cell.source_ref)
        node = _make_block(
            snapshot_id=snapshot_id,
            source_ref=cell.source_ref,
            source_span_ids=[span_ref],
            granularity=ApplicabilityGranularity.PARAGRAPH,
            source_order=cell.block_order,
            text=cell.text,
            scopes=scopes,
            table_path=cell.table_path,
            cross_phase=cross,
        )
        nodes.append(node)
        atomic_by_ref[cell.source_ref] = node
        _add_phase_candidate(
            phase_candidates,
            snapshot_id=snapshot_id,
            block=cell,
            scopes=scopes,
            source_span_id=span_ref,
        )

    visit_tables = {
        table for (table, _row) in groups if _table_is_visit_table(groups, table)
    }
    row_aggregates: list[PhaseApplicabilityBlock] = []
    for (table, row), cells in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1])):
        ordered = sorted(
            (cell for cell in cells if cell.source_ref in atomic_by_ref),
            key=lambda item: (item.block_order, item.source_ref),
        )
        if not ordered:
            continue
        child_nodes = [atomic_by_ref[cell.source_ref] for cell in ordered]
        row_text = " | ".join(cell.text for cell in ordered)
        first = ordered[0]
        row_aggregates.append(
            _make_block(
                snapshot_id=snapshot_id,
                source_ref=f"{table}.r{row}",
                source_span_ids=[
                    (source_span_ids or {}).get(cell.source_ref, cell.source_ref)
                    for cell in ordered
                ],
                granularity=ApplicabilityGranularity.TABLE_ROW,
                source_order=min(cell.block_order for cell in ordered),
                text=row_text,
                scopes=_combine_child_scopes([tuple(node.phase_scopes) for node in child_nodes]),
                table_path=first.table_path,
                table_row=row,
                cross_phase=any(node.cross_phase_comparison for node in child_nodes),
                is_aggregate=True,
                child_block_ids=[node.block_id for node in child_nodes],
            )
        )
    nodes.extend(row_aggregates)

    for table in sorted(visit_tables):
        columns: dict[int, list[StructureBlock]] = {}
        for (table_name, _row), cells in groups.items():
            if table_name != table:
                continue
            for cell in cells:
                match = _CELL_REF_RE.match(cell.source_ref)
                if match is not None and cell.source_ref in atomic_by_ref:
                    columns.setdefault(int(match.group("col")), []).append(cell)
        for col, column_cells in sorted(columns.items()):
            ordered = sorted(column_cells, key=lambda item: (item.block_order, item.source_ref))
            child_nodes = [atomic_by_ref[cell.source_ref] for cell in ordered]
            first = ordered[0]
            nodes.append(
                _make_block(
                    snapshot_id=snapshot_id,
                    source_ref=f"{table}.c{col}",
                    source_span_ids=[
                        (source_span_ids or {}).get(cell.source_ref, cell.source_ref)
                        for cell in ordered
                    ],
                    granularity=ApplicabilityGranularity.VISIT_COLUMN,
                    source_order=min(cell.block_order for cell in ordered),
                    text=" | ".join(cell.text for cell in ordered),
                    scopes=_combine_child_scopes([tuple(node.phase_scopes) for node in child_nodes]),
                    table_path=first.table_path,
                    visit_column=col,
                    cross_phase=any(node.cross_phase_comparison for node in child_nodes),
                    is_aggregate=True,
                    child_block_ids=[node.block_id for node in child_nodes],
                )
            )

    nodes.sort(key=lambda item: (item.source_order, item.source_ref, item.granularity.value))
    # A real phase graph always includes neutral/shared content.  If the source
    # only contains phase-specific text, shared is not invented as a block.
    seamless = _seamless_candidate(nodes, snapshot_id=snapshot_id)
    if seamless:
        design_ref = seamless.source_refs[0]
        nodes = [
            node.model_copy(update={"phase_scopes": [PhaseScope.SEAMLESS_CANDIDATE]})
            if node.source_ref == design_ref
            else node
            for node in nodes
        ]
        phase_candidates = [
            candidate.model_copy(
                update={
                    "phase_scopes": [PhaseScope.PHASE_II, PhaseScope.PHASE_III],
                    "design_type": PhaseDesignType.SEAMLESS_CANDIDATE,
                    "explicit_design_evidence": True,
                    "same_cohort_evidence": True,
                    "requires_confirmation": True,
                }
            )
            if candidate.source_ref == design_ref
            else candidate
            for candidate in phase_candidates
        ]
    detected = sorted(
        {scope for node in nodes for scope in node.phase_scopes}, key=lambda item: item.value
    )
    if seamless and PhaseScope.SEAMLESS_CANDIDATE not in detected:
        detected.append(PhaseScope.SEAMLESS_CANDIDATE)
        first_ref = seamless.source_refs[0]
        source_block = next(item for item in blocks if item.source_ref == first_ref)
        phase_candidates.append(
            StudyPhaseCandidate(
                candidate_id=_stable_id(snapshot_id, "seamless-phase-candidate", *seamless.source_refs),
                snapshot_id=snapshot_id,
                phase_scopes=[PhaseScope.PHASE_II, PhaseScope.PHASE_III],
                design_type=PhaseDesignType.SEAMLESS_CANDIDATE,
                source_ref=first_ref,
                source_span_id=(source_span_ids or {}).get(first_ref, first_ref),
                source_kind=(
                    MetadataSourceKind.BODY
                    if source_block.document_part == DocumentPart.BODY
                    else MetadataSourceKind.HEADER_FOOTER
                ),
                excerpt=seamless.explicit_design_excerpt,
                priority_rank=40,
                confidence_basis=["明确无缝设计措辞", "同一受试者队列连续跨期"],
                explicit_design_evidence=True,
                same_cohort_evidence=True,
                requires_confirmation=True,
            )
        )
    graph = PhaseApplicabilityGraph(
        graph_id=_stable_id(snapshot_id, "graph"),
        snapshot_id=snapshot_id,
        blocks=nodes,
        seamless_candidates=[seamless] if seamless else [],
        detected_phase_scopes=detected or [PhaseScope.UNKNOWN],
        default_design_type=(PhaseDesignType.SEAMLESS_CANDIDATE if seamless else PhaseDesignType.INDEPENDENT),
    )
    return PhaseDetectionResult(graph=graph, phase_candidates=tuple(phase_candidates))


def project_single_phase(
    graph: PhaseApplicabilityGraph,
    selected_phase: StudyPhase,
    *,
    projection_id: str | None = None,
) -> PhaseProjection:
    """Return selected-phase + shared blocks, excluding other-phase-only blocks."""

    if selected_phase not in {
        StudyPhase.PHASE_II,
        StudyPhase.PHASE_III,
        StudyPhase.SEAMLESS_II_III,
    }:
        raise ValueError("必须先确认 II 期、III 期或真正无缝期别")
    if selected_phase == StudyPhase.SEAMLESS_II_III and not graph.seamless_candidates:
        raise ValueError("没有通过明确设计和同一受试者队列证据的无缝候选")
    selected_scope = {
        StudyPhase.PHASE_II: PhaseScope.PHASE_II,
        StudyPhase.PHASE_III: PhaseScope.PHASE_III,
    }.get(selected_phase)
    def safe(block: PhaseApplicabilityBlock) -> bool:
        scopes = tuple(block.phase_scopes)
        if set(scopes) & {PhaseScope.MIXED, PhaseScope.UNKNOWN}:
            return False
        if selected_phase == StudyPhase.SEAMLESS_II_III:
            return bool(
                set(scopes)
                <= {
                    PhaseScope.PHASE_II,
                    PhaseScope.PHASE_III,
                    PhaseScope.SHARED,
                    PhaseScope.SEAMLESS_CANDIDATE,
                }
            )
        return scopes in {(selected_scope,), (PhaseScope.SHARED,)}

    # Prefer one aggregate view per table.  Visit tables project columns;
    # ordinary tables project rows.  If the preferred aggregate is mixed, its
    # safe atomic children remain independently eligible, but the mixed row or
    # column itself can never enter the Agent payload.
    visit_roots = {
        _table_root(block.source_ref)
        for block in graph.blocks
        if block.is_aggregate and block.granularity == ApplicabilityGranularity.VISIT_COLUMN
    }
    preferred_aggregates = {
        block.block_id
        for block in graph.blocks
        if block.is_aggregate
        and (
            (
                block.granularity == ApplicabilityGranularity.VISIT_COLUMN
                and _table_root(block.source_ref) in visit_roots
            )
            or (
                block.granularity == ApplicabilityGranularity.TABLE_ROW
                and _table_root(block.source_ref) not in visit_roots
            )
        )
    }
    included: list[PhaseApplicabilityBlock] = []
    excluded: list[str] = []
    suppressed_children: set[str] = set()

    def projected(block: PhaseApplicabilityBlock) -> PhaseApplicabilityBlock:
        # Do not mutate source text.  ``projection_text`` is a derived
        # consumer display field with no authority over source ownership.
        if block.cross_phase_comparison:
            return block.model_copy(
                update={"projection_text": _projection_text(block.text, selected_phase)}
            )
        return block.model_copy(update={"projection_text": None})

    for block in sorted(graph.blocks, key=lambda item: (item.source_order, item.source_ref)):
        if not block.is_aggregate:
            continue
        if block.block_id not in preferred_aggregates or not safe(block):
            excluded.append(block.block_id)
            continue
        included.append(projected(block))
        suppressed_children.update(block.child_block_ids)

    for block in sorted(graph.blocks, key=lambda item: (item.source_order, item.source_ref)):
        if block.is_aggregate:
            continue
        if block.block_id in suppressed_children or not safe(block):
            excluded.append(block.block_id)
            continue
        included.append(projected(block))

    included.sort(key=lambda item: (item.source_order, item.source_ref, item.granularity.value))
    excluded = list(dict.fromkeys(excluded))
    return PhaseProjection(
        projection_id=projection_id or _stable_id(graph.graph_id, selected_phase.value),
        graph_id=graph.graph_id,
        selected_phase=selected_phase,
        blocks=included,
        excluded_block_ids=excluded,
    )


# Public aliases make the projection contract discoverable without duplicating
# logic under a second name.
detect_phase_applicability = build_phase_applicability_graph
project_phase_applicability = project_single_phase
