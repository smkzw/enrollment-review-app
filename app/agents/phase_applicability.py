"""Chinese-native Agent wire for semantic protocol phase applicability.

The adapter is intentionally independent from the official eligibility and
other-control Agents.  It accepts only a frozen, source-closed package and
returns positional semantic drafts.  New provider calls use a compact v2
grouped wire: identical target payloads are emitted once and deterministically
expanded back into one draft per target.  The prompt renders each target and
context unit exactly once; context packets carry only their role and frozen
unit/span indexes, so packet membership cannot duplicate source text.  The
model may echo the system-provided target ``structure_unit_id`` values so
batch drift is detectable, but it cannot create source references or any
result/candidate/evidence identity.

No provider is selected here and no live model is called.  A caller may attach
the provider-neutral ``PhaseApplicabilityAgentTransport`` to a separately
configured transport after the deterministic contract has passed.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Callable, Literal, Protocol

from pydantic import Field, ValidationError, model_validator

from app.domain.contracts.common import ContractModel
from app.domain.contracts.enums import PhaseScope, StableEnum, StudyPhase
from app.domain.contracts.phase_applicability import (
    PhaseApplicabilityCandidateDraft,
    PhaseApplicabilityDisposition,
    PhaseApplicabilityEvidenceDraft,
    PhaseApplicabilityEvidencePolarity,
    PhaseApplicabilityFrozenPackage,
    PhaseApplicabilityResolutionBatchDraft,
    PhaseApplicabilityResolutionDraft,
    PhaseApplicabilityResolutionSet,
)
from app.protocols.phase_applicability import (
    PhaseApplicabilityHydrationError,
    check_phase_applicability_resolution,
    hydrate_phase_applicability_resolution,
)

PHASE_APPLICABILITY_AGENT_WIRE_VERSION = (
    "phase5/phase-applicability-agent-wire/v1"
)
# v1 remains readable for historical checkpoints and captured provider
# responses.  New transport calls use the grouped v2 contract below.
PHASE_APPLICABILITY_AGENT_WIRE_V1_VERSION = PHASE_APPLICABILITY_AGENT_WIRE_VERSION
PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION = (
    "phase5/phase-applicability-agent-wire/v2"
)
PHASE_APPLICABILITY_AGENT_CURRENT_WIRE_VERSION = (
    PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION
)
PHASE_APPLICABILITY_AGENT_INPUT_VERSION = (
    "phase5/phase-applicability-agent-input/v1"
)
PHASE_APPLICABILITY_AGENT_PROMPT_VERSION = (
    "phase5/phase-applicability-agent-prompt/v13"
)


class PhaseApplicabilityContextKind(StableEnum):
    """Authoritative structural context roles exposed to the Agent."""

    HEADING_CHAIN = "heading_chain"
    TABLE_TITLE_AND_HEADERS = "table_title_and_headers"
    STUDY_DESIGN_PHASE = "study_design_phase"
    PHASE_PROTOCOL = "phase_protocol"
    VISIT_FLOW = "visit_flow"
    CROSS_REFERENCE = "cross_reference"


__all__ = [
    "PHASE_APPLICABILITY_AGENT_INPUT_VERSION",
    "PHASE_APPLICABILITY_AGENT_PROMPT_VERSION",
    "PHASE_APPLICABILITY_AGENT_WIRE_VERSION",
    "PHASE_APPLICABILITY_AGENT_WIRE_V1_VERSION",
    "PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION",
    "PHASE_APPLICABILITY_AGENT_CURRENT_WIRE_VERSION",
    "DEFAULT_PHASE_APPLICABILITY_AGENT_PROMPT_TEMPLATE",
    "PhaseApplicabilityAgentAttempt",
    "PhaseApplicabilityAgentAttemptCallback",
    "PhaseApplicabilityAgentInput",
    "PhaseApplicabilityAgentResponse",
    "PhaseApplicabilityAgentRunResult",
    "PhaseApplicabilityAgentRunner",
    "PhaseApplicabilityAgentTransport",
    "PhaseApplicabilityAgentWire",
    "PhaseApplicabilityAgentWireBatch",
    "PhaseApplicabilityAgentWireGroup",
    "PhaseApplicabilityAgentWireV2",
    "PhaseApplicabilityAgentWireV2Group",
    "PhaseApplicabilityAgentWireV2Batch",
    "PhaseApplicabilityAgentCompactGroup",
    "PhaseApplicabilityAgentCompactWire",
    "PhaseApplicabilityAgentWireCandidate",
    "PhaseApplicabilityAgentWireEvidence",
    "PhaseApplicabilityAgentWireResult",
    "PhaseApplicabilityAgentWireUnitResult",
    "PhaseApplicabilityAgentWireValidationError",
    "PhaseApplicabilityContextKind",
    "PhaseApplicabilityContextPacket",
    "build_phase_applicability_agent_input",
    "build_phase_applicability_agent_prompt",
    "build_phase_applicability_context_packets",
    "build_phase_applicability_repair_prompt",
    "hydrate_phase_applicability_agent_output",
    "parse_phase_applicability_agent_output",
    "parse_phase_applicability_agent_wire",
    "parse_phase_applicability_agent_wire_v1",
    "parse_phase_applicability_agent_wire_v2",
    "phase_applicability_agent_json_schema",
    "phase_applicability_agent_v1_json_schema",
    "phase_applicability_agent_v2_json_schema",
    "phase_applicability_agent_v1_response_format",
    "phase_applicability_agent_prompt_template_sha256",
    "phase_applicability_agent_response_format",
    "validate_phase_applicability_agent_wire",
    "validate_phase_applicability_agent_wire_v2",
    "expand_phase_applicability_agent_wire_v2",
    "wire_to_phase_applicability_resolution_draft",
]


class PhaseApplicabilityAgentWireValidationError(ValueError):
    """Provider-wire or frozen-input validation error with bounded repair scope."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        unit_indexes: Sequence[int] = (),
        structure_unit_ids: Sequence[str] = (),
    ) -> None:
        self.code = code
        self.unit_indexes = tuple(dict.fromkeys(unit_indexes))
        self.structure_unit_ids = tuple(dict.fromkeys(structure_unit_ids))
        super().__init__(f"{code}: {message}")


class PhaseApplicabilityAgentResponse(ContractModel):
    """Raw transport response retained only for adapter audit."""

    session_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class PhaseApplicabilityAgentTransport(Protocol):
    """Provider-neutral transport boundary; no provider is selected here."""

    def start(self, *, prompt: str) -> PhaseApplicabilityAgentResponse: ...

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
    ) -> PhaseApplicabilityAgentResponse: ...


def _require_indexes(values: Sequence[int], label: str) -> None:
    if any(not isinstance(value, int) or value < 0 for value in values):
        raise ValueError(f"{label} 必须为非负整数")
    if list(values) != sorted(set(values)):
        raise ValueError(f"{label} 必须按升序排列且不得重复")


def _require_unique_nonempty_strings(values: Sequence[str], label: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{label} 不得包含空值")
    if len(values) != len(set(values)):
        raise ValueError(f"{label} 不得重复")


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _phase_applicability_target_equivalence_fingerprint(unit: object) -> str:
    """Return the deterministic semantic boundary for one owned target.

    A compact v2 group may share a semantic payload only when its owned
    targets have the same frozen structural meaning.  System identities and
    source locations are deliberately excluded: they are echoed or injected
    for audit, not semantic content.  The source excerpt, heading chain,
    table context and phase range remain exact so distinct paragraphs cannot
    be hidden behind one group's evidence and rationale.
    """

    table_context = getattr(unit, "table_context", None)
    table_payload = None
    if table_context is not None:
        table_payload = {
            "table_path": list(getattr(table_context, "table_path", ())),
            "row_index": getattr(table_context, "row_index", None),
            "column_index": getattr(table_context, "column_index", None),
            "member_cell_paths": [
                list(path)
                for path in getattr(table_context, "member_cell_paths", ())
            ],
            "row_headers": list(getattr(table_context, "row_headers", ())),
            "column_headers": list(getattr(table_context, "column_headers", ())),
        }
    return _stable_json(
        {
            "unit_kind": str(
                getattr(getattr(unit, "unit_kind", None), "value", getattr(unit, "unit_kind", ""))
            ),
            "is_footnote_or_note": bool(getattr(unit, "is_footnote_or_note", False)),
            "heading_path": list(getattr(unit, "heading_path", ())),
            "table_context": table_payload,
            "study_phase": str(
                getattr(getattr(unit, "study_phase", None), "value", getattr(unit, "study_phase", ""))
            ),
            "phase_scopes": sorted(
                str(getattr(scope, "value", scope))
                for scope in getattr(unit, "phase_scopes", ())
            ),
            "excerpt": str(getattr(unit, "excerpt", "")),
        }
    )


def _validation_error_summary(exc: ValidationError) -> str:
    pieces: list[str] = []
    for error in exc.errors(
        include_url=False,
        include_context=False,
        include_input=False,
    ):
        location = ".".join(str(part) for part in error["loc"])
        pieces.append(f"{location}: {error['msg']}")
    return "；".join(pieces)


_CHINESE_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_LOG_LIKE_RE = re.compile(
    r"(?:^|[\s\[({])(?:ERROR|WARN|WARNING|INFO|DEBUG|TRACE|Traceback|Exception)"
    r"(?:$|[\s:：\])}])|(?:session_id|batch_id|stack trace|model output)",
    re.IGNORECASE,
)

_SELECTED_PHASE_TERMS = (
    "本期",
    "本期别",
    "选定期",
    "选定期别",
    "当前期",
    "当前期别",
    "本研究期",
    "本研究期别",
    "目标期",
    "目标期别",
)

_OPPOSITE_PHASE_TERMS = (
    "对侧期",
    "对侧期别",
    "对侧阶段",
    "另一阶段",
    "另一期",
    "另一期别",
)

def _validate_chinese_rationale(value: str, label: str) -> None:
    if not _CHINESE_RE.search(value):
        raise ValueError(f"{label} 必须使用中文自然语言说明，不得只返回英文或日志")
    if any(unicodedata.category(character).startswith("C") for character in value):
        raise ValueError(f"{label} 不得包含不可见控制字符或格式字符")
    if "\x00" in value or _LOG_LIKE_RE.search(value):
        raise ValueError(f"{label} 不得包含日志、调试字段或机器输出痕迹")
    for marker in ("'", '"'):
        if value.count(marker) % 2:
            raise ValueError(f"{label} 的引号或括号必须成对，不得返回截断句")
    for opening, closing in (("“", "”"), ("‘", "’"), ("（", "）"), ("《", "》"), ("【", "】")):
        depth = 0
        for character in value:
            if character == opening:
                depth += 1
            elif character == closing:
                depth -= 1
                if depth < 0:
                    break
        if depth:
            raise ValueError(f"{label} 的引号或括号必须成对，不得返回截断句")


def _phase_label_terms(phase: StudyPhase | None) -> tuple[str, ...]:
    """Return generic Chinese/roman aliases without using project names."""

    if phase == StudyPhase.PHASE_II:
        return ("Ⅱ期", "II期", "ii期", "二期", "2期")
    if phase == StudyPhase.PHASE_III:
        return ("Ⅲ期", "III期", "iii期", "三期", "3期")
    if phase == StudyPhase.SEAMLESS_II_III:
        return (
            "无缝期",
            "无缝期别",
            "无缝Ⅱ/Ⅲ期",
            "无缝II/III期",
            "Ⅱ/Ⅲ期",
            "II/III期",
        )
    return ()


class PhaseApplicabilityContextPacket(ContractModel):
    """A read-only packet containing only role and indexes into frozen sources.

    Packet membership is metadata, not a second source rendering.  The prompt
    presents the referenced target/context units once in their respective
    collections and uses these indexes only to describe how the same frozen
    sources support the structural context role.
    """

    kind: PhaseApplicabilityContextKind
    source_unit_indexes: list[int] = Field(min_length=1)
    source_span_indexes: list[int] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_packet_indexes(self) -> "PhaseApplicabilityContextPacket":
        _require_indexes(self.source_unit_indexes, "context source_unit_indexes")
        _require_indexes(self.source_span_indexes, "context source_span_indexes")
        return self


def _unit_matches_any(unit: object, terms: Sequence[str]) -> bool:
    heading = " ".join(getattr(unit, "heading_path", ()))
    excerpt = str(getattr(unit, "excerpt", ""))
    haystack = f"{heading} {excerpt}".casefold()
    return any(term.casefold() in haystack for term in terms)


def _heading_matches_any(unit: object, terms: Sequence[str]) -> bool:
    heading = " ".join(getattr(unit, "heading_path", ())).casefold()
    return any(term.casefold() in heading for term in terms)


def _table_title_indexes(units: Sequence[object]) -> set[int]:
    """Return table rows/headers plus source units carrying their table title."""

    table_titles: set[str] = set()
    for unit in units:
        heading_path = getattr(unit, "heading_path", ())
        if getattr(unit, "table_context", None) is not None and heading_path:
            title = str(heading_path[-1]).strip()
            if title:
                table_titles.add(title)
    return {
        index
        for index, unit in enumerate(units)
        if getattr(unit, "table_context", None) is not None
        or str(getattr(unit, "excerpt", "")).strip() in table_titles
    }


def _packet(
    kind: PhaseApplicabilityContextKind,
    indexes: Sequence[int],
    package: PhaseApplicabilityFrozenPackage,
) -> PhaseApplicabilityContextPacket | None:
    if not indexes:
        return None
    unit_indexes = sorted(set(indexes))
    units = package.all_units
    span_ids = sorted(
        {
            span_id
            for index in unit_indexes
            for span_id in units[index].source_span_ids
        }
    )
    span_indexes = [package.frozen_source_span_ids.index(span_id) for span_id in span_ids]
    return PhaseApplicabilityContextPacket(
        kind=kind,
        source_unit_indexes=unit_indexes,
        source_span_indexes=span_indexes,
    )


def build_phase_applicability_context_packets(
    package: PhaseApplicabilityFrozenPackage,
) -> list[PhaseApplicabilityContextPacket]:
    """Build a conservative source-grounded context projection.

    This helper never invents context text.  Every packet points to source
    units and source spans already closed by ``package``.  Callers may supply a
    stricter, manually selected packet list to ``build_phase_applicability_agent_input``.
    """

    units = package.all_units
    all_indexes = list(range(len(units)))
    packets: list[PhaseApplicabilityContextPacket] = []

    candidates: tuple[tuple[PhaseApplicabilityContextKind, list[int]], ...] = (
        (PhaseApplicabilityContextKind.HEADING_CHAIN, all_indexes),
        (
            PhaseApplicabilityContextKind.TABLE_TITLE_AND_HEADERS,
            sorted(_table_title_indexes(units)),
        ),
        (
            PhaseApplicabilityContextKind.STUDY_DESIGN_PHASE,
            [
                index
                for index, unit in enumerate(units)
                if _heading_matches_any(
                    unit,
                    (
                        "研究设计",
                        "试验设计",
                        "方案设计",
                        "研究阶段",
                        "研究期别",
                        "study design",
                        "study phase",
                        "trial design",
                        "phase",
                    ),
                )
            ],
        ),
        (
            PhaseApplicabilityContextKind.PHASE_PROTOCOL,
            [
                index
                for index, unit in enumerate(units)
                if any(
                    scope
                    in {
                        PhaseScope.PHASE_II,
                        PhaseScope.PHASE_III,
                        PhaseScope.SHARED,
                        PhaseScope.SEAMLESS_CANDIDATE,
                    }
                    for scope in unit.phase_scopes
                )
            ],
        ),
        (
            PhaseApplicabilityContextKind.VISIT_FLOW,
            [
                index
                for index, unit in enumerate(units)
                if _heading_matches_any(
                    unit,
                    (
                        "访视",
                        "访视流程",
                        "访视安排",
                        "visit",
                        "schedule",
                        "flow",
                        "follow-up",
                    ),
                )
            ],
        ),
        (
            PhaseApplicabilityContextKind.CROSS_REFERENCE,
            [
                index
                for index, unit in enumerate(units)
                if _unit_matches_any(
                    unit,
                    (
                        "参见",
                        "见表",
                        "详见",
                        "交叉引用",
                        "见图",
                        "见附录",
                        "同前",
                        "refer",
                        "see",
                    ),
                )
            ],
        ),
    )
    for kind, indexes in candidates:
        packet = _packet(kind, indexes, package)
        if packet is not None:
            packets.append(packet)
    return packets


class PhaseApplicabilityAgentInput(ContractModel):
    """Frozen, read-only Agent input with indexed context packet roles.

    ``target_units`` and ``context_units`` are the sole source-text
    presentations.  ``context_packets`` contains no duplicated unit payload;
    it only indexes those frozen units and their source spans.
    """

    schema_version: Literal[PHASE_APPLICABILITY_AGENT_INPUT_VERSION] = Field(...)
    frozen_package: PhaseApplicabilityFrozenPackage
    context_is_read_only: Literal[True] = True
    context_packets: list[PhaseApplicabilityContextPacket] = Field(min_length=1)

    @property
    def target_units(self):
        return self.frozen_package.owned_units

    @property
    def all_units(self):
        return self.frozen_package.all_units

    @property
    def target_structure_unit_ids(self) -> tuple[str, ...]:
        return tuple(unit.structure_unit_id for unit in self.target_units)

    @property
    def context_structure_unit_ids(self) -> tuple[str, ...]:
        return tuple(unit.structure_unit_id for unit in self.frozen_package.context_units)

    @classmethod
    def from_frozen_package(
        cls,
        package: PhaseApplicabilityFrozenPackage,
        context_packets: Sequence[PhaseApplicabilityContextPacket] | None = None,
    ) -> "PhaseApplicabilityAgentInput":
        packets = (
            list(context_packets)
            if context_packets is not None
            else build_phase_applicability_context_packets(package)
        )
        return cls(
            schema_version=PHASE_APPLICABILITY_AGENT_INPUT_VERSION,
            frozen_package=package,
            context_packets=packets,
        )

    # Short alias used by callers that treat the package as an input snapshot.
    from_package = from_frozen_package

    @model_validator(mode="after")
    def validate_context_closure(self) -> "PhaseApplicabilityAgentInput":
        package = self.frozen_package
        units = package.all_units
        package_spans = set(package.frozen_source_span_ids)
        unit_indexes = set(range(len(units)))
        span_index_by_id = {
            span_id: index
            for index, span_id in enumerate(package.frozen_source_span_ids)
        }
        for packet in self.context_packets:
            if not set(packet.source_unit_indexes) <= unit_indexes:
                raise ValueError("context packet 引用了冻结包外结构单元索引")
            if not set(packet.source_span_indexes) <= set(range(len(package_spans))):
                raise ValueError("context packet 引用了冻结包外来源片段索引")
            cited_spans = {
                span_id
                for unit_index in packet.source_unit_indexes
                for span_id in units[unit_index].source_span_ids
            }
            packet_spans = {
                package.frozen_source_span_ids[index]
                for index in packet.source_span_indexes
            }
            if not packet_spans <= cited_spans:
                raise ValueError("context packet 来源片段必须属于其引用的结构单元")
            if not packet_spans <= package_spans:
                raise ValueError("context packet 来源片段必须属于冻结包闭包")
            if [span_index_by_id[span_id] for span_id in sorted(packet_spans)] != packet.source_span_indexes:
                raise ValueError("context packet 来源片段索引必须按冻结来源顺序排列")
            if packet.kind == PhaseApplicabilityContextKind.TABLE_TITLE_AND_HEADERS:
                if not any(units[index].table_context is not None for index in packet.source_unit_indexes):
                    raise ValueError("表题/表头上下文必须引用表格结构单元")
        return self


def build_phase_applicability_agent_input(
    package: PhaseApplicabilityFrozenPackage,
    context_packets: Sequence[PhaseApplicabilityContextPacket] | None = None,
) -> PhaseApplicabilityAgentInput:
    return PhaseApplicabilityAgentInput.from_frozen_package(package, context_packets)


class PhaseApplicabilityAgentWireEvidence(ContractModel):
    """Provider evidence links; all source identities are positional indexes."""

    polarity: PhaseApplicabilityEvidencePolarity
    source_unit_indexes: list[int] = Field(min_length=1)
    source_span_indexes: list[int] = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_wire_evidence(self) -> "PhaseApplicabilityAgentWireEvidence":
        _require_indexes(self.source_unit_indexes, "evidence source_unit_indexes")
        _require_indexes(self.source_span_indexes, "evidence source_span_indexes")
        _validate_chinese_rationale(self.rationale, "证据 rationale")
        return self


class PhaseApplicabilityAgentWireCandidate(ContractModel):
    """One candidate scope with support/oppose/unresolved evidence indexes."""

    scope: PhaseScope
    supporting_evidence_indexes: list[int] = Field(default_factory=list)
    opposing_evidence_indexes: list[int] = Field(default_factory=list)
    unresolved_evidence_indexes: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_wire_candidate(self) -> "PhaseApplicabilityAgentWireCandidate":
        _require_indexes(
            self.supporting_evidence_indexes,
            "candidate supporting_evidence_indexes",
        )
        _require_indexes(
            self.opposing_evidence_indexes,
            "candidate opposing_evidence_indexes",
        )
        _require_indexes(
            self.unresolved_evidence_indexes,
            "candidate unresolved_evidence_indexes",
        )
        if self.scope in {PhaseScope.UNKNOWN, PhaseScope.MIXED}:
            raise ValueError("Agent 候选期别不得返回 UNKNOWN 或 MIXED")
        groups = (
            set(self.supporting_evidence_indexes),
            set(self.opposing_evidence_indexes),
            set(self.unresolved_evidence_indexes),
        )
        if groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2]:
            raise ValueError("候选支持、反对和未解决来源不得重复归类")
        if not any(groups):
            raise ValueError("每个候选期别至少需要一条证据索引")
        return self


class PhaseApplicabilityAgentWireResult(ContractModel):
    """One target result; ``structure_unit_id`` is an echo-only system identity."""

    unit_index: int = Field(ge=0)
    structure_unit_id: str = Field(min_length=1)
    evidence: list[PhaseApplicabilityAgentWireEvidence] = Field(min_length=1)
    candidates: list[PhaseApplicabilityAgentWireCandidate] = Field(min_length=1)
    final_disposition: PhaseApplicabilityDisposition
    rationale: str = Field(min_length=1)
    unresolved_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_wire_result(self) -> "PhaseApplicabilityAgentWireResult":
        _validate_chinese_rationale(self.rationale, "结果 rationale")
        if self.unresolved_reason is not None:
            _validate_chinese_rationale(self.unresolved_reason, "unresolved_reason")
        scopes = [candidate.scope for candidate in self.candidates]
        if len(scopes) != len(set(scopes)):
            raise ValueError("同一目标不得重复返回候选期别")
        evidence_count = len(self.evidence)
        referenced: set[int] = set()
        for candidate in self.candidates:
            indexes = (
                *candidate.supporting_evidence_indexes,
                *candidate.opposing_evidence_indexes,
                *candidate.unresolved_evidence_indexes,
            )
            if any(index >= evidence_count for index in indexes):
                raise ValueError("候选引用了当前目标之外的证据索引")
            referenced.update(indexes)
        if referenced != set(range(evidence_count)):
            raise ValueError("每条证据都必须绑定至少一个候选期别")
        if (
            self.final_disposition == PhaseApplicabilityDisposition.UNRESOLVED
            and not self.unresolved_reason
        ):
            raise ValueError("仍待确认处置必须记录 unresolved_reason")
        return self


class PhaseApplicabilityAgentWire(ContractModel):
    """Strict, reference-free provider output for one frozen package."""

    wire_version: Literal[PHASE_APPLICABILITY_AGENT_WIRE_VERSION] = Field(...)
    results: list[PhaseApplicabilityAgentWireResult] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_wire_results(self) -> "PhaseApplicabilityAgentWire":
        indexes = [item.unit_index for item in self.results]
        if indexes != sorted(set(indexes)):
            raise ValueError("Agent 结果必须按目标 unit_index 升序且不得重复")
        fingerprints = {
            _stable_json(item.model_dump(mode="json")) for item in self.results
        }
        if len(fingerprints) != len(self.results):
            raise ValueError("Agent 目标结果不得重复")
        return self


class PhaseApplicabilityAgentCompactGroup(ContractModel):
    """One v2 provider group shared by an explicit set of owned targets.

    The semantic payload is deliberately identical to the v1 per-target
    payload.  Only target ownership is compressed: ``unit_indexes`` and
    ``structure_unit_ids`` are parallel, provider-echoed lists.  Expansion
    later copies this payload into one provider-neutral draft per target.
    """

    unit_indexes: list[int] = Field(min_length=1)
    structure_unit_ids: list[str] = Field(min_length=1)
    evidence: list[PhaseApplicabilityAgentWireEvidence] = Field(min_length=1)
    candidates: list[PhaseApplicabilityAgentWireCandidate] = Field(min_length=1)
    final_disposition: PhaseApplicabilityDisposition
    rationale: str = Field(min_length=1)
    unresolved_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_compact_group(self) -> "PhaseApplicabilityAgentCompactGroup":
        _require_indexes(self.unit_indexes, "group unit_indexes")
        if len(self.structure_unit_ids) != len(self.unit_indexes):
            raise ValueError(
                "group structure_unit_ids 必须与 unit_indexes 逐项对应"
            )
        _require_unique_nonempty_strings(
            self.structure_unit_ids,
            "group structure_unit_ids",
        )
        _validate_chinese_rationale(self.rationale, "组 rationale")
        if self.unresolved_reason is not None:
            _validate_chinese_rationale(self.unresolved_reason, "组 unresolved_reason")
        scopes = [candidate.scope for candidate in self.candidates]
        if len(scopes) != len(set(scopes)):
            raise ValueError("同一分组不得重复返回候选期别")
        evidence_count = len(self.evidence)
        referenced: set[int] = set()
        for candidate in self.candidates:
            indexes = (
                *candidate.supporting_evidence_indexes,
                *candidate.opposing_evidence_indexes,
                *candidate.unresolved_evidence_indexes,
            )
            if any(index >= evidence_count for index in indexes):
                raise ValueError("分组候选引用了当前分组之外的证据索引")
            referenced.update(indexes)
        if referenced != set(range(evidence_count)):
            raise ValueError("分组中的每条证据都必须绑定至少一个候选期别")
        if (
            self.final_disposition == PhaseApplicabilityDisposition.UNRESOLVED
            and not self.unresolved_reason
        ):
            raise ValueError("分组仍待确认处置必须记录 unresolved_reason")
        return self


class PhaseApplicabilityAgentWireV2(ContractModel):
    """Strict grouped v2 provider output for one frozen package."""

    wire_version: Literal[PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION] = Field(...)
    groups: list[PhaseApplicabilityAgentCompactGroup] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_wire_groups(self) -> "PhaseApplicabilityAgentWireV2":
        flattened = [
            unit_index
            for group in self.groups
            for unit_index in group.unit_indexes
        ]
        first_indexes = [group.unit_indexes[0] for group in self.groups]
        if first_indexes != sorted(first_indexes):
            raise ValueError(
                "Agent v2 分组必须按每组首个 unit_index 升序排列"
            )
        if len(flattened) != len(set(flattened)):
            raise ValueError(
                "Agent v2 分组的 unit_indexes 跨组不得重复"
            )
        structure_unit_ids = [
            structure_unit_id
            for group in self.groups
            for structure_unit_id in group.structure_unit_ids
        ]
        if len(structure_unit_ids) != len(set(structure_unit_ids)):
            raise ValueError(
                "Agent v2 分组的 structure_unit_ids 跨组不得重复"
            )
        return self


# Descriptive aliases keep discovery compatible with the batch-oriented
# protocol-control Agent without creating a second implementation.
PhaseApplicabilityAgentWireBatch = PhaseApplicabilityAgentWire
PhaseApplicabilityAgentWireUnitResult = PhaseApplicabilityAgentWireResult
PhaseApplicabilityAgentWireGroup = PhaseApplicabilityAgentCompactGroup
PhaseApplicabilityAgentWireV2Group = PhaseApplicabilityAgentCompactGroup
PhaseApplicabilityAgentWireV2Batch = PhaseApplicabilityAgentWireV2
PhaseApplicabilityAgentCompactWire = PhaseApplicabilityAgentWireV2


def _find_forbidden_provider_key(
    value: object,
    path: str = "",
) -> tuple[str, str] | None:
    forbidden = {
        "schema_version",
        "package_id",
        "batch_id",
        "coverage_manifest_id",
        "protocol_version_id",
        "snapshot_id",
        "resolution_id",
        "candidate_id",
        "evidence_id",
        "override_id",
        "source_structure_unit_ids",
        "source_span_ids",
        "source_unit_ids",
        "stable_id",
        "created_by_agent_call_id",
        "created_by_model",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in forbidden:
                return key, f"{path}.{key}" if path else key
            found = _find_forbidden_provider_key(
                child,
                f"{path}.{key}" if path else key,
            )
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_forbidden_provider_key(child, f"{path}[{index}]")
            if found is not None:
                return found
    return None


def _parse_phase_applicability_wire_text(
    text: str,
    model: type[ContractModel],
) -> ContractModel:
    """Parse one strict wire model; package closure is checked later."""

    if not text or not text.strip():
        raise PhaseApplicabilityAgentWireValidationError(
            "EMPTY_OUTPUT",
            "模型返回空输出",
        )
    stripped = text.strip()
    if stripped.startswith("```"):
        raise PhaseApplicabilityAgentWireValidationError(
            "MARKDOWN_OUTPUT",
            "模型输出不得包含 Markdown 代码块",
        )
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise PhaseApplicabilityAgentWireValidationError(
            "INVALID_JSON",
            f"模型输出不是合法 JSON：{exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise PhaseApplicabilityAgentWireValidationError(
            "TOP_LEVEL_NOT_OBJECT",
            "模型输出顶层必须是 JSON 对象",
        )
    forbidden = _find_forbidden_provider_key(payload)
    if forbidden is not None:
        key, path = forbidden
        raise PhaseApplicabilityAgentWireValidationError(
            "PROVIDER_ID_FORBIDDEN",
            f"provider 不得生成系统身份字段 {path}（{key}）",
        )
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise PhaseApplicabilityAgentWireValidationError(
            "WIRE_SCHEMA_INVALID",
            _validation_error_summary(exc),
        ) from exc


def parse_phase_applicability_agent_wire(
    text: str,
) -> PhaseApplicabilityAgentWire | PhaseApplicabilityAgentWireV2:
    """Parse either supported provider wire, dispatching by wire_version.

    Callers that need to force historical or compact parsing can use the
    explicit ``*_v2`` helper (or the v1 JSON schema) instead.
    """

    try:
        payload = json.loads(text.strip())
    except (TypeError, json.JSONDecodeError):
        payload = None
    if (
        isinstance(payload, dict)
        and payload.get("wire_version") == PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION
    ):
        return parse_phase_applicability_agent_wire_v2(text)
    parsed = _parse_phase_applicability_wire_text(text, PhaseApplicabilityAgentWire)
    assert isinstance(parsed, PhaseApplicabilityAgentWire)
    return parsed


def parse_phase_applicability_agent_wire_v2(
    text: str,
) -> PhaseApplicabilityAgentWireV2:
    """Parse the compact grouped v2 provider wire."""

    parsed = _parse_phase_applicability_wire_text(text, PhaseApplicabilityAgentWireV2)
    assert isinstance(parsed, PhaseApplicabilityAgentWireV2)
    return parsed


def parse_phase_applicability_agent_wire_v1(
    text: str,
) -> PhaseApplicabilityAgentWire:
    """Parse the historical v1 per-target provider wire explicitly."""

    parsed = _parse_phase_applicability_wire_text(text, PhaseApplicabilityAgentWire)
    assert isinstance(parsed, PhaseApplicabilityAgentWire)
    return parsed


def _strict_json_schema(model: type[ContractModel]) -> dict[str, object]:
    schema = deepcopy(model.model_json_schema())

    def require_declared_properties(value: object) -> None:
        if isinstance(value, list):
            for item in value:
                require_declared_properties(item)
            return
        if not isinstance(value, dict):
            return
        properties = value.get("properties")
        if isinstance(properties, dict) and properties:
            value["required"] = list(properties)
            value["additionalProperties"] = False
        for child in value.values():
            require_declared_properties(child)

    require_declared_properties(schema)
    return schema


def phase_applicability_agent_v1_json_schema() -> dict[str, object]:
    """Return the historical v1 schema for inspecting old artifacts."""

    return _strict_json_schema(PhaseApplicabilityAgentWire)


def phase_applicability_agent_v2_json_schema() -> dict[str, object]:
    """Return the compact grouped v2 schema used by new provider calls."""

    return _strict_json_schema(PhaseApplicabilityAgentWireV2)


def phase_applicability_agent_json_schema(
    version: Literal["v1", "v2"] = "v2",
) -> dict[str, object]:
    """Return a strict provider schema; new calls default to compact v2."""

    if version == "v1":
        return phase_applicability_agent_v1_json_schema()
    return phase_applicability_agent_v2_json_schema()


def phase_applicability_agent_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "phase_applicability_agent_wire_v2",
            "strict": True,
            "schema": phase_applicability_agent_json_schema(),
        },
    }


def phase_applicability_agent_v1_response_format() -> dict[str, object]:
    """Return the historical v1 format for replaying old provider calls."""

    return {
        "type": "json_schema",
        "json_schema": {
            "name": "phase_applicability_agent_wire_v1",
            "strict": True,
            "schema": phase_applicability_agent_v1_json_schema(),
        },
    }


DEFAULT_PHASE_APPLICABILITY_AGENT_PROMPT_TEMPLATE = (
    "请对本次冻结的方案结构单元逐项判断期别适用性，并严格返回指定 JSON。"
)

_PHASE_AGENT_SYSTEM_CONTRACT = (
    "你是中文原生方案期别适用性语义助手。你只能处理本次输入中的 owned target_units，"
    "每个 target 必须恰好属于一个 v2 groups 分组；当多个 target 的处置、候选证据、"
    "最终 rationale 和 unresolved_reason 完全相同时，只有在目标等价边界完全一致时才可合并；不同内容必须分开。"
    "目标等价边界由冻结目标的 unit_kind、heading_path、table_context、study_phase、phase_scopes 和 excerpt"
    "确定；其中任一字段不同都属于异质目标，必须拆为独立分组，不得共享同一 evidence 或 rationale。"
    "每个分组必须列出按升序排列且不重复的 unit_indexes，并逐项回显对应的 structure_unit_ids；"
    "不得用一个共享结果掩盖异质目标。target_units 和 context_units 各自只呈现一次冻结正文；"
    "context_packets 仅保留上下文类型及 source_unit_indexes/source_span_indexes，"
    "只是对同一冻结来源的只读索引，绝不重复注入结构单元正文。context_packets 和 context_units 仅是只读来源，"
    "绝不能取得目标所有权或成为新的目标。必须综合上位章节标题链、表题与表头、研究设计/期别"
    "章节、各期方案段落、访视流程表和明确交叉引用判断，不能只看目标段落、关键词邻近关系或"
    "方案总体印象。四种最终处置仅允许 selected_phase_applicable、opposite_phase_applicable、"
    "cross_phase_shared、unresolved；来源不足时必须返回 unresolved，绝不能把未知默认成共享。"
    "判断顺序固定为：先确认目标是否应纳入 selected_phase 所代表的独立研究，再判断是否有充分依据提升为两期共用。"
    "目标自己的正文位于非期别专属标题链，且直接形成研究要求、限制、操作或人群条件时，应优先用目标自身原文支持"
    " selected_phase_applicable；不得仅因缺少另一期间共用证明而返回 unresolved。只有目标自身语义仍不完整、"
    "存在对侧期专属限定、来源冲突或 mixed 原子边界未拆分时，才保留 unresolved。"
    "下文所述禁止全局广播，只限制用别的上层共同语句证明 cross_phase_shared 或扩散到兄弟义务；"
    "不限制把目标自身明确写出的全局控制纳入当前已选独立研究。"
    "原文未限定某一期、未区分两期或未出现期别名称，只表示未见排他性限定，不能单独证明两期共同适用。"
    "但本次任务首先服务于 selected_phase 所固定的独立研究：若目标位于方案全局章节，标题链不在任何期别专属"
    "分支下，正文明确形成研究要求、限制、操作或人群条件，且冻结上下文未显示其仅属于对侧期，"
    "该全局章节结构可正向支持 selected_phase_applicable；这不等于已经证明 cross_phase_shared。"
    "不得因为无法证明另一期间也适用，就把当前所选期别明确需要遵守的全局控制降为 unresolved。"
    "判为 cross_phase_shared 必须给出正向依据，例如方案明确说明两期共同适用，或可靠交叉引用把同一要求"
    "连接到两期；正向来源可以是与目标同一标题族的两期共用来源，也可以是Ⅱ期与Ⅲ期来源分别明确指向目标的同一规则标题；"
    "当两期设计段分别以‘所有’‘任何’‘每项’等全称范围明确指向同一个规则标题时，该引用覆盖该官方标题下的子条目，"
    "除非方案另有期别特异例外或改写；这种成对引用不要求另有 phase_scopes=shared 的第三份来源。"
    "成对来源必须作为一个组合判断，不得在同一标题下按目标轮流只取Ⅱ期或Ⅲ期来源而生成互相矛盾的单期处置；"
    "若仍判为单一期别，必须引用明确反证说明另一期间的全称引用为何不覆盖当前目标。"
    "共同章节结构只有在共同结构本身明确约束与目标相同的义务家族（同一义务、要求、操作或人群），"
    "且已核对不存在改变该义务的期别特异兄弟内容时，才可作为正向依据。共同章节标题、章节邻近、"
    "‘Ⅱ/Ⅲ期评估和程序一致’或盲法共用语句不能全局广播到所有入排、治疗、合并用药/治疗控制；"
    "单一共同章节证据不得广播到其他义务家族。若共同章节只部分闭合、只覆盖部分来源/表格成员，或兄弟内容"
    "仍未闭合，必须返回 unresolved；理由必须点明该原文或结构语境如何支持同一义务家族共用。"
    "期别处置必须根据该段的实际适用对象、操作或义务发生阶段判断，不得根据段落中出现了哪些期别名称判断。"
    "cross_phase_shared 仅用于同一要求、行动或人群明确对两期均适用；A期结果决定或触发B期安排，"
    "只说明两期存在因果或时序关联，不等于同一要求对两期均适用。仅描述对侧期入组、人群、给药或访视的段落，"
    "即使以选定期结果为前提，也应判为 opposite_phase_applicable。"
    "两期都出现同一检查、治疗或操作名称，也不等于该义务完全跨期共用；只要访视时间、时间窗、阈值、剂量、"
    "适用人群或执行条件存在期别差异，就应先按 selected_phase 的实际要求形成 selected_phase_applicable，"
    "不得用 cross_phase_shared 掩盖差异；若当前冻结单元无法独立回源所选期别的完整义务，才返回 unresolved。"
    "每条证据必须使用输入已经提供的 source_unit_indexes 和 source_span_indexes；被引用的 source unit"
    "及其 source_span_indexes 必须来自同一 target_units/context_units 冻结正文，且 source_span_index"
    "只能引用该 source unit 中与 source_span_ids 按位置一一对应、已经展示的全局来源片段索引；"
    "不得凭空猜测或跨 source unit 拼接索引。摘录必须是所引用"
    "结构单元 excerpt 中可逐字恢复的连续原文；来源充分时优先使用一条直接证据和简洁中文"
    "说明。每条证据优先只引用一个直接 source_unit_index 及该单元自身展示的 source_span_indexes；"
    "如确需引用多个来源单元，每个 source_span_index 都必须属于同条证据列出的某个来源单元，不能"
    "把标题链或其他单元的片段索引全部挂到一个 source_unit_index 下。"
    "说明，避免重复罗列封面、标题链、流程等同一事实；支持、反对、未解决来源必须按候选"
    "分别归类。"
    "候选数组只列有证据索引的实际候选，不得创建证据索引全为空的候选；最终处置已经明确时，"
    "通常只保留与最终处置对应的候选，存在反对或未解决证据时再增加相应候选。"
    "明确区分：target 的 phase_scopes 中 UNKNOWN/MIXED 只是冻结来源的输入状态；"
    "输入 UNKNOWN/MIXED 不是输出候选期别，绝不能复制为 candidate.scope；candidate.scope 只能使用 phase_ii、phase_iii、shared 或 seamless_candidate。"
    "上下文只能支持判断，不能创建新的来源、来源 ID、稳定结果 ID、候选 ID、证据 ID 或人工覆盖 ID。"
    "structure_unit_id 只能逐字回显与 unit_index 对应的系统目标身份，用于系统检查批次漂移，不能改写。"
    "最终 rationale、证据 rationale 和 unresolved_reason 必须使用简洁中文自然语言，不能返回英文、"
    "日志、调试字段、Markdown 或模型运行记录。理由还必须与最终处置逐项一致："
    "selected_phase_applicable 明确本期/选定期别及来源依据，opposite_phase_applicable 明确实际适用的"
    "对侧期别及来源依据，cross_phase_shared 明确同一要求、操作、义务或人群在两期均适用/跨期共用，"
    "unresolved 明确待确认状态及缺失的来源、证据或资料依据；不能只返回‘该段为方案摘要中’等中文残句。"
    "target 的 phase_scopes 为 mixed 只说明结构层在同一冻结单元中识别到多个期别名称，不等于已经证明存在"
    "多项不同期别义务。必须按实际主语、动作、适用对象和发生阶段继续判断：若同一不可再拆句只描述本期评估或"
    "操作，而对侧期仅是该操作的结果、建议、触发对象或后续安排，可按实际操作发生期形成单期处置；只有同一"
    "冻结单元确实包含两项或以上需要分别适用到不同期别的要求，且尚不能独立回源时，才返回 unresolved 并说明"
    "需要拆分的具体义务。"
)

_PHASE_AGENT_REPAIR_CONTRACT = (
    "这是同一会话内的定向修复。只修复列出的冻结包和目标 unit_index；不要替换已接受批次，"
    "不要删除未被指出且仍有效的证据，不要扩展到其他目标。仍须返回本冻结包全部 target_units 的"
    "完整 v2 分组结果，并继续只使用输入给出的目标身份和来源索引。修复轮必须逐项回显完整冻结目标清单："
    "每个 target unit_index 恰好出现一次，按升序完整返回，并逐字回显其对应的 structure_unit_id；"
    "不得只返回首个失败目标或只返回修复目标。若校验问题指出异质目标同组，"
    "异质目标必须按 unit_kind、heading_path、table_context、study_phase、phase_scopes 和 excerpt 的确定性边界拆为独立分组；"
    "不得把不同摘录、标题链、表格语境或期别范围的目标重新合并，也不得用一套共享证据理由掩盖差异。"
    "修复期别语义时必须区分实际适用对象、操作发生阶段和仅作为前提的对侧期引用；"
    "不得因一段话同时出现两个期别名称就判为跨期共用。修复理由时必须保留具体来源依据，"
    "修复时先判断目标是否纳入 selected_phase 所代表的独立研究，再判断是否有充分依据提升为两期共用。"
    "目标自身位于非期别专属标题链并直接形成研究要求、限制、操作或人群条件时，优先用目标自身原文修复为"
    " selected_phase_applicable；禁止全局广播只限制跨期共用和兄弟义务扩散，不得据此把该目标降为 unresolved。"
    "不得把‘未限定某一期’‘未区分两期’‘适用于所有期别’作为跨期共用的唯一依据；若没有"
    "共同章节结构、明确两期共用原文或可靠交叉引用等正向依据，应改为 unresolved 并说明缺少什么。共同章节结构"
    "若目标位于方案全局章节且不在任何期别专属分支下，正文已明确形成研究要求、限制、操作或人群条件，"
    "并且没有对侧期专属证据，则可修复为 selected_phase_applicable；这只确认纳入当前所选期别，"
    "不能据此改为 cross_phase_shared，也不能因缺少另一期间共用证明而继续机械保留 unresolved。"
    "或Ⅱ期与Ⅲ期设计段分别以全称范围指向同一规则标题时，应核对该标题下目标是否存在期别特异例外；"
    "若无例外，成对引用可直接支持该标题下子条目两期共用，不要求额外 shared 来源。"
    "只有在其本身明确约束同一义务家族，且不存在改变该义务的期别特异兄弟内容时，才能作为正向证据候选；"
    "不得把‘Ⅱ/Ⅲ期评估和程序一致’或盲法共用语句全局广播到所有入排、治疗、合并用药/治疗控制。"
    "共同来源只部分闭合、只覆盖部分表格成员或仍有兄弟内容未闭合时，必须改为 unresolved。"
    "证据理由必须同时说明引用了哪段原文、标题链或表格语境，以及该来源为何支持、反对或仍待确认。"
    "unresolved 是 final_disposition，不是候选期别；candidate.scope 只能返回 phase_ii、phase_iii、"
    "shared 或 seamless_candidate，绝不能返回 unknown 或 mixed。即使最终待确认，也必须列出实际"
    "候选期别，并把未解决证据索引放入对应候选的 unresolved_evidence_indexes。最终 unresolved 表示当前"
    "选定期别是否纳入仍无法确定，因此必须包含 selected_phase 对应候选及其未解决证据；仅有 shared 候选"
    "未解决，只能说明尚未证明两期共用，不能据此阻断目标纳入当前所选期别。"
    "phase_scopes=mixed 也必须按实际义务判断：A期评估产生B期建议、触发B期安排或决定B期是否继续，"
    "不等于同一单元含有两项分别适用于A期和B期的要求；只有确有多个不可独立回源的期别义务时才保留 unresolved。"
    "两期都出现同一检查、治疗或操作名称时，若访视时间、时间窗、阈值、剂量、适用人群或执行条件不同，"
    "不得用 cross_phase_shared 掩盖差异；应按 selected_phase 的实际要求修复为 selected_phase_applicable，"
    "无法从冻结来源独立闭合所选期别义务时才保留 unresolved。"
    "再次强调：target 的 phase_scopes 中 UNKNOWN/MIXED 只是冻结来源的输入状态；"
    "输入 UNKNOWN/MIXED 不是输出候选期别，绝不能复制为 candidate.scope；candidate.scope 只能使用 phase_ii、phase_iii、shared 或 seamless_candidate。"
    "每条证据优先只引用一个直接来源单元和该单元自己的来源片段；不得把其他结构单元的片段索引"
    "挂到同一个 source_unit_index 下。修复后仍须完整返回全部目标，不得只返回首个失败目标。"
    "并按处置补全本期/对侧期/两期共用/待确认依据；‘该段为方案摘要中’等含中文残句仍属于失败。"
)


def phase_applicability_agent_prompt_template_sha256(prompt_template: str) -> str:
    payload = "\n\n".join(
        (
            PHASE_APPLICABILITY_AGENT_PROMPT_VERSION,
            prompt_template.strip(),
            _PHASE_AGENT_SYSTEM_CONTRACT,
            _PHASE_AGENT_REPAIR_CONTRACT,
            _stable_json(phase_applicability_agent_json_schema()),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _render_unit(
    unit: object,
    index: int,
    *,
    target: bool,
    frozen_source_span_index_by_id: Mapping[str, int],
) -> dict[str, object]:
    table_context = getattr(unit, "table_context", None)
    table = None
    if table_context is not None:
        table = {
            "table_path": list(table_context.table_path),
            "row_index": table_context.row_index,
            "column_index": table_context.column_index,
            "row_headers": list(table_context.row_headers),
            "column_headers": list(table_context.column_headers),
        }
    source_span_ids = list(unit.source_span_ids)
    try:
        source_span_indexes = [
            frozen_source_span_index_by_id[span_id]
            for span_id in source_span_ids
        ]
    except KeyError as exc:
        raise ValueError(
            "渲染结构单元引用了冻结包外 source_span_id"
        ) from exc
    return {
        "unit_index": index,
        "target": target,
        "structure_unit_id": unit.structure_unit_id,
        "source_ref": unit.source_ref,
        "source_span_ids": source_span_ids,
        "source_span_indexes": source_span_indexes,
        "unit_kind": unit.unit_kind.value,
        "heading_path": list(unit.heading_path),
        "table_context": table,
        "study_phase": unit.study_phase.value,
        "phase_scopes": [scope.value for scope in unit.phase_scopes],
        "excerpt": unit.excerpt,
    }


def build_phase_applicability_agent_prompt(
    value: PhaseApplicabilityAgentInput | PhaseApplicabilityFrozenPackage,
    *,
    prompt_template: str = DEFAULT_PHASE_APPLICABILITY_AGENT_PROMPT_TEMPLATE,
) -> str:
    """Build deterministic Chinese prompt from one frozen package."""

    agent_input = (
        value
        if isinstance(value, PhaseApplicabilityAgentInput)
        else build_phase_applicability_agent_input(value)
    )
    package = agent_input.frozen_package
    frozen_source_span_index_by_id = {
        span_id: index
        for index, span_id in enumerate(package.frozen_source_span_ids)
    }
    context_rendered = [
        {
            "kind": packet.kind.value,
            "source_unit_indexes": list(packet.source_unit_indexes),
            "source_span_indexes": list(packet.source_span_indexes),
        }
        for packet in agent_input.context_packets
    ]
    frozen_projection = {
        "schema_version": agent_input.schema_version,
        "package_id": package.package_id,
        "coverage_manifest_id": package.coverage_manifest_id,
        "protocol_version_id": package.protocol_version_id,
        "snapshot_id": package.snapshot_id,
        "selected_phase": package.selected_phase.value,
        "opposite_phase": package.opposite_phase.value if package.opposite_phase else None,
        "context_is_read_only": agent_input.context_is_read_only,
        "target_units": [
            _render_unit(
                unit,
                index,
                target=True,
                frozen_source_span_index_by_id=frozen_source_span_index_by_id,
            )
            for index, unit in enumerate(package.owned_units)
        ],
        "context_units": [
            _render_unit(
                unit,
                len(package.owned_units) + index,
                target=False,
                frozen_source_span_index_by_id=frozen_source_span_index_by_id,
            )
            for index, unit in enumerate(package.context_units)
        ],
        "context_packets": context_rendered,
    }
    return (
        f"{prompt_template.strip()}\n\n"
        f"{_PHASE_AGENT_SYSTEM_CONTRACT}\n\n"
        f"输出 JSON Schema：{_stable_json(phase_applicability_agent_json_schema())}\n\n"
        f"本次冻结输入：{_stable_json(frozen_projection)}\n\n"
        "请按 target_units 的 unit_index 升序完整返回 groups；每组 unit_indexes 必须升序且不重复，"
        "structure_unit_ids 必须与其逐项对应并逐字回显同一目标。仅当目标等价边界完全一致且处置/证据/理由相同的目标放在同一组，"
        "异质目标必须拆组。每组列出候选期别及其支持/反对/未解决证据索引；证据足够时只保留一条"
        "直接证据和简洁中文说明；不能省略任何目标。"
    )


def build_phase_applicability_repair_prompt(
    value: PhaseApplicabilityAgentInput | PhaseApplicabilityFrozenPackage,
    *,
    problem: str,
    unit_indexes: Sequence[int] | None = None,
    structure_unit_ids: Sequence[str] | None = None,
) -> str:
    agent_input = (
        value
        if isinstance(value, PhaseApplicabilityAgentInput)
        else build_phase_applicability_agent_input(value)
    )
    indexes = list(unit_indexes or range(len(agent_input.target_units)))
    if any(index < 0 or index >= len(agent_input.target_units) for index in indexes):
        raise ValueError("定向修复 unit_index 不属于当前冻结包")
    identity_line = ""
    if structure_unit_ids:
        identity_line = (
            "修复目标 structure_unit_id："
            f"{json.dumps(list(structure_unit_ids), ensure_ascii=False)}\n"
        )
    selected_labels = "、".join(
        (*_SELECTED_PHASE_TERMS, *_phase_label_terms(agent_input.frozen_package.selected_phase))
    )
    opposite_labels = "、".join(
        (*_OPPOSITE_PHASE_TERMS, *_phase_label_terms(agent_input.frozen_package.opposite_phase))
    ) or "无对侧期别"
    issue_directives: list[str] = []
    if "PAIRED_RULE_FAMILY_SOURCE_IGNORED" in problem:
        issue_directives.append(
            "本轮已发现成对规则来源被忽略：必须把选定期别和对侧期别中指向同一具体规则标题/义务族的来源作为一组比较，"
            "先分别核对两侧的原文、期别范围和是否存在期别特异例外，再决定单一期别、两期共用或仍待确认。"
            "不得只引用其中一侧后直接形成单期期别结论；若仍判为单一期别，必须在对侧候选中保留明确的不适用或不覆盖反证，"
            "若两侧均为该目标提供正向支持，应按共用门禁处理，不能删除或忽略另一侧来源；结论为两期共用时，"
            "把两侧正向来源均绑定到唯一有证据的 shared 候选，不再保留仅有支持证据的 phase_ii/phase_iii 候选。\n"
        )
    if "CONTRADICTORY_FINAL_DISPOSITION" in problem:
        issue_directives.append(
            "本轮已发现最终处置与候选证据互相冲突：必须让候选数组与最终处置一致。"
            "selected_phase_applicable 不能同时保留对侧或 shared 的支持候选；opposite_phase_applicable 不能同时保留本期或 shared 的支持候选；"
            "cross_phase_shared 只能把支持两期共用的正向来源绑定到 shared 候选，不得同时保留本期或对侧的支持候选。"
            "任何候选都必须至少引用一条支持、反对或未解决证据；不需要的候选应删除，绝不能返回空证据候选。\n"
        )
    if "TARGET_RELATED_SUPPORT_MISSING" in problem:
        issue_directives.append(
            "本轮已发现目标相关支持缺失：必须为每个受影响 target 重新绑定与目标自身或同一具体规则标题/同一义务族直接相关的支持来源，"
            "并说明该来源如何支持当前处置。不得用共同上级标题、章节邻近、普通提及、泛化研究背景或其他义务的来源冒充目标支持；"
            "source_unit_indexes 与 source_span_indexes 必须来自同一条证据列出的冻结来源单元，无法找到目标相关正向依据时应改为相应的反对或 unresolved 处置，"
            "不得凭空补造来源。\n"
        )
    if "EVIDENCE_EXCERPT_NOT_VERBATIM" in problem:
        issue_directives.append(
            "本轮已发现证据摘录非逐字：必须用所引用冻结 source unit excerpt 中可连续恢复的原文替换该 excerpt，"
            "只允许进行项目既有的空白规范化，不得改写、摘要、拼接不同单元文字、补标点或凭记忆重建。"
            "source_unit_indexes 与 source_span_indexes 必须逐项对应；每个 source_span_index 必须属于本证据列出的对应 source_unit_index；"
            "无法逐字核验的证据不得继续作为支持、反对或未解决依据，"
            "应从候选绑定中移除并依据剩余可核验来源重新判断，来源不足时返回 unresolved。\n"
        )
    if "SHARED_POSITIVE_SOURCE_MISSING" in problem:
        issue_directives.append(
            "本轮已明确指出跨期共用缺少正向来源：只能补充符合门禁的同一义务共用来源，"
            "或依据现有证据改为 selected_phase_applicable、opposite_phase_applicable 或 unresolved；"
            "禁止原样重复同一 cross_phase_shared 处置和同一不足来源。\n"
        )
    issue_directive = "".join(issue_directives)
    rationale_contract = (
        "理由修复要求：selected_phase_applicable 必须说明本期/选定期别和来源依据；"
        "opposite_phase_applicable 必须说明对侧期别和实际适用依据；cross_phase_shared 必须说明"
        "同一要求或操作在两期均适用/跨期共用；unresolved 必须说明待确认及缺失依据。"
        "仅写‘未限定某一期’‘未区分两期’或‘适用于所有期别’不能证明跨期共用；"
        "必须补充与目标同一标题族的共同章节、明确两期共用原文，或Ⅱ期与Ⅲ期来源分别明确指向目标同一规则标题等正向依据，否则改为 unresolved。"
        "若目标位于方案全局章节且标题链不在任何期别专属分支下，正文已经形成研究要求、限制、操作或人群条件，"
        "且没有对侧期专属证据，则该结构可支持 selected_phase_applicable；这不证明 cross_phase_shared，"
        "也不得仅因缺少另一期间共用证据而把当前所选期别控制保留为 unresolved。"
        "若两期来源分别以‘所有’‘任何’‘每项’等全称范围指向该规则标题，且没有期别特异例外，"
        "该成对来源覆盖标题下子条目，不要求另有 shared 来源。"
        "共同章节结构还必须明确约束同一义务家族（同一义务、要求、操作或人群），且不存在改变该义务的"
        "期别特异兄弟内容；不得把‘Ⅱ/Ⅲ期评估和程序一致’或盲法共用语句全局广播到所有入排、治疗、"
        "合并用药/治疗控制。共同来源只部分闭合、只覆盖部分表格成员或仍有兄弟内容未闭合时，必须改为 unresolved。"
        "每条证据理由必须点明原文、标题链或表格语境，并说明其与支持、反对或待确认结论的关系。"
        "unresolved 是最终处置而非候选期别；candidate.scope 只能是 phase_ii、phase_iii、shared"
        "或 seamless_candidate，不得返回 unknown 或 mixed。修复后必须返回本批全部目标。"
        "同一检查、治疗或操作名称若在两期具有不同访视时间、时间窗、阈值、剂量、适用人群或执行条件，"
        "不得判为 cross_phase_shared；必须先按所选期别实际义务判断，不能用动作名称相同掩盖期别差异。"
        f"本期可用通用表述或冻结期别别名（{selected_labels}），"
        f"对侧期可用通用表述或冻结期别别名（{opposite_labels}）。"
    )
    target_checklist = [
        {
            "unit_index": index,
            "structure_unit_id": unit.structure_unit_id,
        }
        for index, unit in enumerate(agent_input.target_units)
    ]
    return (
        f"{_PHASE_AGENT_REPAIR_CONTRACT}\n"
        f"{rationale_contract}\n"
        "本轮失败包重跑验收合同：只有在完整冻结目标清单逐项回显、每个受影响问题均按上述要求闭合、"
        "每条证据的来源单元/来源片段关系和摘录均可由冻结输入逐字复核、且未改变来源、目标身份、候选期别枚举或任何期别门禁时，"
        "该修复结果才可接受；否则继续返回需要核对的完整批次结果，不得用部分成功或放宽门禁代替修复。\n"
        f"冻结包身份（仅用于回显核对）：{agent_input.frozen_package.package_id}\n"
        "完整冻结目标清单（修复后必须逐项回显，成员和顺序不得改变）："
        f"{json.dumps(target_checklist, ensure_ascii=False)}\n"
        f"修复目标 unit_index：{json.dumps(indexes, ensure_ascii=False)}\n"
        f"{identity_line}"
        f"{issue_directive}"
        f"校验问题：{problem[:12000]}\n"
        f"输出 JSON Schema：{_stable_json(phase_applicability_agent_json_schema())}\n"
        "请在同一会话内只返回修复后的完整 wire JSON。"
    )


def _wire_to_domain_result(
    result: PhaseApplicabilityAgentWireResult,
) -> PhaseApplicabilityResolutionDraft:
    return PhaseApplicabilityResolutionDraft(
        unit_index=result.unit_index,
        evidence=[
            PhaseApplicabilityEvidenceDraft(
                polarity=evidence.polarity,
                source_unit_indexes=list(evidence.source_unit_indexes),
                source_span_indexes=list(evidence.source_span_indexes),
                excerpt=evidence.excerpt,
                rationale=evidence.rationale,
            )
            for evidence in result.evidence
        ],
        candidates=[
            PhaseApplicabilityCandidateDraft(
                scope=candidate.scope,
                supporting_evidence_indexes=list(candidate.supporting_evidence_indexes),
                opposing_evidence_indexes=list(candidate.opposing_evidence_indexes),
                unresolved_evidence_indexes=list(candidate.unresolved_evidence_indexes),
            )
            for candidate in result.candidates
        ],
        final_disposition=result.final_disposition,
        rationale=result.rationale,
        unresolved_reason=result.unresolved_reason,
    )


def _compact_group_to_domain_result(
    group: PhaseApplicabilityAgentCompactGroup,
    unit_index: int,
) -> PhaseApplicabilityResolutionDraft:
    return PhaseApplicabilityResolutionDraft(
        unit_index=unit_index,
        evidence=[
            PhaseApplicabilityEvidenceDraft(
                polarity=evidence.polarity,
                source_unit_indexes=list(evidence.source_unit_indexes),
                source_span_indexes=list(evidence.source_span_indexes),
                excerpt=evidence.excerpt,
                rationale=evidence.rationale,
            )
            for evidence in group.evidence
        ],
        candidates=[
            PhaseApplicabilityCandidateDraft(
                scope=candidate.scope,
                supporting_evidence_indexes=list(candidate.supporting_evidence_indexes),
                opposing_evidence_indexes=list(candidate.opposing_evidence_indexes),
                unresolved_evidence_indexes=list(candidate.unresolved_evidence_indexes),
            )
            for candidate in group.candidates
        ],
        final_disposition=group.final_disposition,
        rationale=group.rationale,
        unresolved_reason=group.unresolved_reason,
    )


def _compact_group_fingerprint(
    group: PhaseApplicabilityAgentCompactGroup,
) -> str:
    return _stable_json(
        {
            "evidence": [item.model_dump(mode="json") for item in group.evidence],
            "candidates": [
                item.model_dump(mode="json") for item in group.candidates
            ],
            "final_disposition": group.final_disposition.value,
            "rationale": group.rationale,
            "unresolved_reason": group.unresolved_reason,
        }
    )


def expand_phase_applicability_agent_wire_v2(
    wire: PhaseApplicabilityAgentWireV2 | Mapping[str, object],
    agent_input: PhaseApplicabilityAgentInput,
) -> PhaseApplicabilityResolutionBatchDraft:
    """Expand grouped v2 output into one provider-neutral draft per target.

    The expansion is deliberately the only place where the provider's
    parallel identity echo is interpreted.  It validates complete coverage,
    exact frozen identities, canonical group ordering, and duplicate group
    payloads before copying the shared semantic payload to each target.
    """

    if not isinstance(wire, PhaseApplicabilityAgentWireV2):
        try:
            wire = PhaseApplicabilityAgentWireV2.model_validate(wire)
        except ValidationError as exc:
            raise PhaseApplicabilityAgentWireValidationError(
                "WIRE_SCHEMA_INVALID",
                _validation_error_summary(exc),
            ) from exc

    expected_indexes = list(range(len(agent_input.target_units)))
    expected_ids = [unit.structure_unit_id for unit in agent_input.target_units]
    if not wire.groups:
        raise PhaseApplicabilityAgentWireValidationError(
            "EMPTY_GROUPS",
            "Agent v2 必须至少返回一个分组",
        )

    flattened: list[int] = []
    seen_ids: set[str] = set()
    fingerprints: dict[str, set[str]] = {}
    expanded: list[PhaseApplicabilityResolutionDraft] = []
    first_indexes = [group.unit_indexes[0] for group in wire.groups if group.unit_indexes]
    if first_indexes != sorted(first_indexes):
        raise PhaseApplicabilityAgentWireValidationError(
            "GROUP_ORDER",
            "v2 分组必须按每组首个 unit_index 升序排列",
            unit_indexes=first_indexes,
        )
    for group in wire.groups:
        if not group.unit_indexes:
            raise PhaseApplicabilityAgentWireValidationError(
                "EMPTY_GROUP",
                "Agent v2 分组不得为空",
            )
        if len(group.unit_indexes) != len(group.structure_unit_ids):
            raise PhaseApplicabilityAgentWireValidationError(
                "GROUP_ID_LENGTH_MISMATCH",
                "分组 structure_unit_ids 必须与 unit_indexes 逐项对应",
                unit_indexes=group.unit_indexes,
                structure_unit_ids=group.structure_unit_ids,
            )
        if list(group.unit_indexes) != sorted(set(group.unit_indexes)):
            raise PhaseApplicabilityAgentWireValidationError(
                "GROUP_UNIT_INDEX_ORDER",
                "分组 unit_indexes 必须按升序排列且不得重复",
                unit_indexes=group.unit_indexes,
                structure_unit_ids=group.structure_unit_ids,
            )
        for unit_index, structure_unit_id in zip(
            group.unit_indexes,
            group.structure_unit_ids,
        ):
            flattened.append(unit_index)
            if unit_index < 0 or unit_index >= len(expected_ids):
                raise PhaseApplicabilityAgentWireValidationError(
                    "TARGET_INDEX_OUT_OF_RANGE",
                    f"分组 unit_index 不属于当前冻结 owned 目标：{unit_index}",
                    unit_indexes=[unit_index],
                    structure_unit_ids=[structure_unit_id],
                )
            expected_id = expected_ids[unit_index]
            if structure_unit_id != expected_id:
                raise PhaseApplicabilityAgentWireValidationError(
                    "BATCH_DRIFT",
                    f"unit_index={unit_index} 未回显当前冻结目标结构单元身份",
                    unit_indexes=[unit_index],
                    structure_unit_ids=[structure_unit_id],
                )
            if structure_unit_id in seen_ids:
                raise PhaseApplicabilityAgentWireValidationError(
                    "GROUP_TARGET_DUPLICATE",
                    f"结构单元重复属于多个 v2 分组：{structure_unit_id}",
                    unit_indexes=[unit_index],
                    structure_unit_ids=[structure_unit_id],
                )
            seen_ids.add(structure_unit_id)
            expanded.append(_compact_group_to_domain_result(group, unit_index))

        target_fingerprints = {
            _phase_applicability_target_equivalence_fingerprint(
                agent_input.target_units[unit_index]
            )
            for unit_index in group.unit_indexes
        }
        if len(target_fingerprints) != 1:
            raise PhaseApplicabilityAgentWireValidationError(
                "TARGET_GROUP_HETEROGENEOUS",
                "异质目标不得属于同一 v2 分组；不同摘录、标题链、表格语境或期别范围必须拆组，"
                "请按目标等价边界分别返回对应证据和中文理由",
                unit_indexes=group.unit_indexes,
                structure_unit_ids=group.structure_unit_ids,
            )
        target_fingerprint = next(iter(target_fingerprints))
        payload_fingerprint = _compact_group_fingerprint(group)
        if target_fingerprint in fingerprints.get(payload_fingerprint, set()):
            raise PhaseApplicabilityAgentWireValidationError(
                "DUPLICATE_GROUP_PAYLOAD",
                "目标结构等价且处置、证据和理由相同时必须合并为同一分组",
                unit_indexes=group.unit_indexes,
                structure_unit_ids=group.structure_unit_ids,
            )
        fingerprints.setdefault(payload_fingerprint, set()).add(target_fingerprint)

    if sorted(flattened) != expected_indexes:
        missing = sorted(set(expected_indexes) - set(flattened))
        extra = sorted(set(flattened) - set(expected_indexes))
        raise PhaseApplicabilityAgentWireValidationError(
            "PARTIAL_OR_DRIFTED_BATCH",
            f"冻结包目标必须被分组完整覆盖且只覆盖当前批次；missing={missing}, extra={extra}",
            unit_indexes=flattened,
            structure_unit_ids=[
                structure_unit_id
                for group in wire.groups
                for structure_unit_id in group.structure_unit_ids
            ],
        )
    if len(seen_ids) != len(expected_ids):
        raise PhaseApplicabilityAgentWireValidationError(
            "GROUP_ID_COVERAGE_MISMATCH",
            "v2 分组结构身份未完整覆盖当前冻结 owned 目标",
            unit_indexes=flattened,
            structure_unit_ids=sorted(seen_ids),
        )
    expanded.sort(key=lambda item: item.unit_index)
    return PhaseApplicabilityResolutionBatchDraft(results=expanded)


def wire_to_phase_applicability_resolution_draft(
    wire: Mapping[str, object]
    | PhaseApplicabilityAgentWire
    | PhaseApplicabilityAgentWireV2,
    agent_input: PhaseApplicabilityAgentInput,
) -> PhaseApplicabilityResolutionBatchDraft:
    """Bind only the target echo and batch completeness; no stable IDs are read."""

    if isinstance(wire, Mapping):
        forbidden = _find_forbidden_provider_key(wire)
        if forbidden is not None:
            key, path = forbidden
            raise PhaseApplicabilityAgentWireValidationError(
                "PROVIDER_ID_FORBIDDEN",
                f"provider 不得生成系统身份字段 {path}（{key}）",
            )
        try:
            wire = (
                PhaseApplicabilityAgentWireV2.model_validate(wire)
                if wire.get("wire_version") == PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION
                else PhaseApplicabilityAgentWire.model_validate(wire)
            )
        except ValidationError as exc:
            raise PhaseApplicabilityAgentWireValidationError(
                "WIRE_SCHEMA_INVALID",
                _validation_error_summary(exc),
            ) from exc
    if isinstance(wire, PhaseApplicabilityAgentWireV2):
        return expand_phase_applicability_agent_wire_v2(wire, agent_input)

    expected_indexes = list(range(len(agent_input.target_units)))
    actual_indexes = [result.unit_index for result in wire.results]
    if actual_indexes != expected_indexes:
        missing = sorted(set(expected_indexes) - set(actual_indexes))
        extra = sorted(set(actual_indexes) - set(expected_indexes))
        raise PhaseApplicabilityAgentWireValidationError(
            "PARTIAL_OR_DRIFTED_BATCH",
            f"冻结包目标结果必须完整且只属于当前批次；missing={missing}, extra={extra}",
            unit_indexes=actual_indexes,
            structure_unit_ids=[result.structure_unit_id for result in wire.results],
        )
    expected_ids = [unit.structure_unit_id for unit in agent_input.target_units]
    for result in wire.results:
        if result.structure_unit_id != expected_ids[result.unit_index]:
            raise PhaseApplicabilityAgentWireValidationError(
                "BATCH_DRIFT",
                f"unit_index={result.unit_index} 未回显当前冻结目标结构单元身份",
                unit_indexes=[result.unit_index],
                structure_unit_ids=[result.structure_unit_id],
            )
    try:
        return PhaseApplicabilityResolutionBatchDraft(
            results=[_wire_to_domain_result(result) for result in wire.results]
        )
    except (ValidationError, ValueError) as exc:
        raise PhaseApplicabilityAgentWireValidationError(
            "DRAFT_SCHEMA_INVALID",
            str(exc),
            unit_indexes=actual_indexes,
            structure_unit_ids=expected_ids,
        ) from exc


def hydrate_phase_applicability_agent_output(
    value: str
    | Mapping[str, object]
    | PhaseApplicabilityAgentWire
    | PhaseApplicabilityAgentWireV2,
    agent_input: PhaseApplicabilityAgentInput,
) -> PhaseApplicabilityResolutionSet:
    """Parse, source-hydrate and gate one complete Agent batch."""

    def parse_any(text: str):
        try:
            payload = json.loads(text.strip())
        except (TypeError, json.JSONDecodeError):
            return parse_phase_applicability_agent_wire(text)
        if (
            isinstance(payload, dict)
            and payload.get("wire_version") == PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION
        ):
            return parse_phase_applicability_agent_wire_v2(text)
        return parse_phase_applicability_agent_wire(text)

    if isinstance(value, str):
        wire = parse_any(value)
    elif isinstance(value, (PhaseApplicabilityAgentWire, PhaseApplicabilityAgentWireV2)):
        wire = value
    else:
        forbidden = _find_forbidden_provider_key(value)
        if forbidden is not None:
            key, path = forbidden
            raise PhaseApplicabilityAgentWireValidationError(
                "PROVIDER_ID_FORBIDDEN",
                f"provider 不得生成系统身份字段 {path}（{key}）",
            )
        try:
            wire = (
                PhaseApplicabilityAgentWireV2.model_validate(value)
                if value.get("wire_version") == PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION
                else PhaseApplicabilityAgentWire.model_validate(value)
            )
        except ValidationError as exc:
            raise PhaseApplicabilityAgentWireValidationError(
                "WIRE_SCHEMA_INVALID",
                _validation_error_summary(exc),
            ) from exc
    draft = wire_to_phase_applicability_resolution_draft(wire, agent_input)
    package = agent_input.frozen_package
    try:
        resolutions = hydrate_phase_applicability_resolution(package, draft)
        report = check_phase_applicability_resolution(package, resolutions)
        if not report.accepted:
            affected_ids = tuple(
                dict.fromkeys(
                    issue.structure_unit_id
                    for issue in report.issues
                    if issue.structure_unit_id
                )
            )
            affected_indexes = tuple(
                index
                for index, unit in enumerate(agent_input.target_units)
                if unit.structure_unit_id in affected_ids
            )
            details = "; ".join(
                (
                    f"{issue.code} [{issue.structure_unit_id}]: {issue.message}"
                    if issue.structure_unit_id
                    else f"{issue.code}: {issue.message}"
                )
                for issue in report.issues
            )
            raise PhaseApplicabilityAgentWireValidationError(
                report.issues[0].code,
                details,
                unit_indexes=affected_indexes,
                structure_unit_ids=affected_ids,
            )
        return resolutions
    except PhaseApplicabilityHydrationError as exc:
        raise PhaseApplicabilityAgentWireValidationError(
            exc.code,
            str(exc),
            unit_indexes=(
                [item.unit_index for item in wire.results]
                if isinstance(wire, PhaseApplicabilityAgentWire)
                else [
                    unit_index
                    for group in wire.groups
                    for unit_index in group.unit_indexes
                ]
            ),
        ) from exc
    except PhaseApplicabilityAgentWireValidationError:
        raise
    except (ValidationError, ValueError) as exc:
        raise PhaseApplicabilityAgentWireValidationError(
            "HYDRATION_INVALID",
            str(exc),
            unit_indexes=(
                [item.unit_index for item in wire.results]
                if isinstance(wire, PhaseApplicabilityAgentWire)
                else [
                    unit_index
                    for group in wire.groups
                    for unit_index in group.unit_indexes
                ]
            ),
        ) from exc


def validate_phase_applicability_agent_wire(
    value: str
    | Mapping[str, object]
    | PhaseApplicabilityAgentWire
    | PhaseApplicabilityAgentWireV2,
    agent_input: PhaseApplicabilityAgentInput,
) -> PhaseApplicabilityResolutionSet:
    return hydrate_phase_applicability_agent_output(value, agent_input)


def validate_phase_applicability_agent_wire_v2(
    value: str | Mapping[str, object] | PhaseApplicabilityAgentWireV2,
    agent_input: PhaseApplicabilityAgentInput,
) -> PhaseApplicabilityResolutionSet:
    """Validate, expand, hydrate and gate a compact v2 provider response."""

    return hydrate_phase_applicability_agent_output(value, agent_input)


def parse_phase_applicability_agent_output(
    text: str,
    agent_input: PhaseApplicabilityAgentInput,
    *,
    hydrate: bool = True,
) -> PhaseApplicabilityResolutionSet | PhaseApplicabilityResolutionBatchDraft:
    try:
        payload = json.loads(text.strip())
    except (TypeError, json.JSONDecodeError):
        payload = None
    wire = (
        parse_phase_applicability_agent_wire_v2(text)
        if isinstance(payload, dict)
        and payload.get("wire_version") == PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION
        else parse_phase_applicability_agent_wire(text)
    )
    draft = wire_to_phase_applicability_resolution_draft(wire, agent_input)
    if not hydrate:
        return draft
    return hydrate_phase_applicability_agent_output(wire, agent_input)


class PhaseApplicabilityAgentAttempt(ContractModel):
    attempt: int = Field(ge=1)
    session_id: str = Field(min_length=1)
    raw_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome: Literal["parsed", "schema_invalid", "transport_failed"]
    output: PhaseApplicabilityResolutionSet | None = None
    issues: list[str] = Field(default_factory=list)
    rejected_unit_indexes: list[int] = Field(default_factory=list)
    rejected_structure_unit_ids: list[str] = Field(default_factory=list)


PhaseApplicabilityAgentAttemptCallback = Callable[
    [PhaseApplicabilityAgentAttempt], None
]


class PhaseApplicabilityAgentRunResult(ContractModel):
    status: Literal["已解析", "需要核对"]
    package_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    attempts: list[PhaseApplicabilityAgentAttempt] = Field(min_length=1)
    final_output: PhaseApplicabilityResolutionSet | None = None


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class PhaseApplicabilityAgentRunner:
    """Bounded same-session parse/repair loop for one frozen package."""

    def __init__(
        self,
        *,
        max_transport_retries: int = 1,
        max_schema_repairs: int = 2,
    ) -> None:
        if max_transport_retries < 0 or max_schema_repairs < 0:
            raise ValueError("重试上限必须为非负整数")
        self._max_transport_retries = max_transport_retries
        self._max_schema_repairs = max_schema_repairs

    def run(
        self,
        agent_input: PhaseApplicabilityAgentInput,
        transport: PhaseApplicabilityAgentTransport,
        *,
        prompt_template: str = DEFAULT_PHASE_APPLICABILITY_AGENT_PROMPT_TEMPLATE,
        accepted_package_ids: Sequence[str] = (),
        on_attempt: PhaseApplicabilityAgentAttemptCallback | None = None,
    ) -> PhaseApplicabilityAgentRunResult:
        package_id = agent_input.frozen_package.package_id
        if package_id in set(accepted_package_ids):
            raise ValueError(f"已接受冻结包不得被同会话修复替换：{package_id}")

        attempts: list[PhaseApplicabilityAgentAttempt] = []

        def record_attempt(attempt: PhaseApplicabilityAgentAttempt) -> None:
            attempts.append(attempt)
            if on_attempt is not None:
                on_attempt(attempt)

        session_id: str | None = None
        raw_text: str | None = None
        prompt = build_phase_applicability_agent_prompt(
            agent_input,
            prompt_template=prompt_template,
        )
        transport_failures = 0
        while True:
            try:
                response = (
                    transport.start(prompt=prompt)
                    if session_id is None
                    else transport.continue_session(session_id=session_id, prompt=prompt)
                )
                if session_id is not None and response.session_id != session_id:
                    raise RuntimeError("同会话修复不得更换 session_id")
                session_id = response.session_id
                raw_text = response.text
                break
            except Exception as exc:  # noqa: BLE001 - transport boundary
                attempt_id = len(attempts) + 1
                sid = session_id or f"transport-failed-{attempt_id}"
                record_attempt(
                    PhaseApplicabilityAgentAttempt(
                        attempt=attempt_id,
                        session_id=sid,
                        raw_output_sha256=_sha256(str(exc)),
                        outcome="transport_failed",
                        issues=[str(exc)[:2000]],
                    )
                )
                transport_failures += 1
                if transport_failures > self._max_transport_retries:
                    return PhaseApplicabilityAgentRunResult(
                        status="需要核对",
                        package_id=package_id,
                        session_id=sid,
                        attempts=attempts,
                    )

        assert session_id is not None and raw_text is not None
        repairs = 0
        while True:
            try:
                output = hydrate_phase_applicability_agent_output(raw_text, agent_input)
                record_attempt(
                    PhaseApplicabilityAgentAttempt(
                        attempt=len(attempts) + 1,
                        session_id=session_id,
                        raw_output_sha256=_sha256(raw_text),
                        outcome="parsed",
                        output=output,
                    )
                )
                return PhaseApplicabilityAgentRunResult(
                    status="已解析",
                    package_id=package_id,
                    session_id=session_id,
                    attempts=attempts,
                    final_output=output,
                )
            except Exception as exc:  # noqa: BLE001 - bounded validation boundary
                error = (
                    exc
                    if isinstance(exc, PhaseApplicabilityAgentWireValidationError)
                    else PhaseApplicabilityAgentWireValidationError(
                        "OUTPUT_INVALID",
                        str(exc),
                    )
                )
                record_attempt(
                    PhaseApplicabilityAgentAttempt(
                        attempt=len(attempts) + 1,
                        session_id=session_id,
                        raw_output_sha256=_sha256(raw_text),
                        outcome="schema_invalid",
                        issues=[str(error)[:2000]],
                        rejected_unit_indexes=list(error.unit_indexes),
                        rejected_structure_unit_ids=list(error.structure_unit_ids),
                    )
                )
                if repairs >= self._max_schema_repairs:
                    return PhaseApplicabilityAgentRunResult(
                        status="需要核对",
                        package_id=package_id,
                        session_id=session_id,
                        attempts=attempts,
                    )
                repairs += 1
                repair_prompt = build_phase_applicability_repair_prompt(
                    agent_input,
                    problem=str(error),
                    unit_indexes=error.unit_indexes or range(len(agent_input.target_units)),
                    structure_unit_ids=error.structure_unit_ids,
                )
                try:
                    response = transport.continue_session(
                        session_id=session_id,
                        prompt=repair_prompt,
                    )
                    if response.session_id != session_id:
                        raise RuntimeError("同会话修复不得更换 session_id")
                    raw_text = response.text
                except Exception as exc2:  # noqa: BLE001 - transport boundary
                    record_attempt(
                        PhaseApplicabilityAgentAttempt(
                            attempt=len(attempts) + 1,
                            session_id=session_id,
                            raw_output_sha256=_sha256(str(exc2)),
                            outcome="transport_failed",
                            issues=[str(exc2)[:2000]],
                            rejected_unit_indexes=list(error.unit_indexes),
                            rejected_structure_unit_ids=list(error.structure_unit_ids),
                        )
                    )
                    return PhaseApplicabilityAgentRunResult(
                        status="需要核对",
                        package_id=package_id,
                        session_id=session_id,
                        attempts=attempts,
                    )
