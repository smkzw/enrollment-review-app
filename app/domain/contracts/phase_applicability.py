"""Phase applicability semantic contracts for the Phase 5 protocol workbench.

The source structure unit is the authority for identity.  Agent-facing drafts
therefore address units, spans and evidence by indexes into a frozen package;
the system-only hydration step assigns every persistent identity.  This keeps
semantic ambiguity explicit without allowing a model to manufacture a source
reference or a stable result id.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Sequence

from pydantic import Field, model_validator

from .enums import PhaseScope, StableEnum, StudyPhase
from .protocol_controls import Phase5ControlModel, ProtocolStructureUnit

PHASE_APPLICABILITY_CONTRACT_VERSION = "phase5/phase-applicability/v1"

_SHA256 = r"^[0-9a-f]{64}$"

__all__ = [
    "PHASE_APPLICABILITY_CONTRACT_VERSION",
    "PhaseApplicabilityCandidateDraft",
    "PhaseApplicabilityCandidateEvaluation",
    "PhaseApplicabilityDisposition",
    "PhaseApplicabilityEvidence",
    "PhaseApplicabilityEvidenceDraft",
    "PhaseApplicabilityEvidencePolarity",
    "PhaseApplicabilityFrozenPackage",
    "PhaseApplicabilityManualOverrideRecord",
    "PhaseApplicabilityResolutionBatchDraft",
    "PhaseApplicabilityResolutionDraft",
    "PhaseApplicabilityResolutionSet",
    "PhaseApplicabilityUnitResolution",
    "stable_phase_applicability_candidate_id",
    "stable_phase_applicability_evidence_id",
    "stable_phase_applicability_override_id",
    "stable_phase_applicability_package_id",
    "stable_phase_applicability_resolution_id",
]


class PhaseApplicabilityEvidencePolarity(StableEnum):
    """How one frozen source supports a candidate interpretation."""

    SUPPORTS = "supports"
    OPPOSES = "opposes"
    UNRESOLVED = "unresolved"


class PhaseApplicabilityDisposition(StableEnum):
    """The only four publish-facing outcomes of semantic phase resolution."""

    SELECTED_PHASE_APPLICABLE = "selected_phase_applicable"
    OPPOSITE_PHASE_APPLICABLE = "opposite_phase_applicable"
    CROSS_PHASE_SHARED = "cross_phase_shared"
    UNRESOLVED = "unresolved"


def _value(value: object) -> str:
    return str(getattr(value, "value", value))


def _stable_digest(*parts: object) -> str:
    payload = json.dumps(
        [_value(part) if isinstance(part, StableEnum) else part for part in parts],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _require_unique_nonempty(values: Sequence[str], label: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{label} 不得包含空值")
    if len(values) != len(set(values)):
        raise ValueError(f"{label} 不得重复")


def _require_sorted_unique(values: Sequence[str], label: str) -> None:
    _require_unique_nonempty(values, label)
    if list(values) != sorted(values):
        raise ValueError(f"{label} 必须按 ID 排序")


def _require_indexes(values: Sequence[int], label: str) -> None:
    if any(not isinstance(value, int) or value < 0 for value in values):
        raise ValueError(f"{label} 必须为非负整数")
    if list(values) != sorted(set(values)):
        raise ValueError(f"{label} 必须按升序排列且不得重复")


def stable_phase_applicability_package_id(
    coverage_manifest_id: str,
    package_ordinal: int,
    owned_structure_unit_ids: Sequence[str],
) -> str:
    """Return the package identity from system-owned frozen inputs only."""

    if package_ordinal < 1:
        raise ValueError("期别语义包序号必须从 1 起")
    _require_unique_nonempty(owned_structure_unit_ids, "owned_structure_unit_ids")
    return "pap-" + _stable_digest(
        coverage_manifest_id,
        package_ordinal,
        tuple(sorted(owned_structure_unit_ids)),
    )


def stable_phase_applicability_resolution_id(
    coverage_manifest_id: str,
    protocol_version_id: str,
    selected_phase: StudyPhase,
    structure_unit_id: str,
) -> str:
    """Identity of a unit's semantic result; disposition changes do not alter it."""

    return "par-" + _stable_digest(
        coverage_manifest_id,
        protocol_version_id,
        _value(selected_phase),
        structure_unit_id,
    )


def stable_phase_applicability_candidate_id(
    resolution_id: str,
    scope: PhaseScope,
) -> str:
    return "pac-" + _stable_digest(resolution_id, _value(scope))


def stable_phase_applicability_evidence_id(
    resolution_id: str,
    polarity: PhaseApplicabilityEvidencePolarity,
    source_structure_unit_ids: Sequence[str],
    source_span_ids: Sequence[str],
    excerpt: str,
    rationale: str,
) -> str:
    """Identity of a source-backed evidence assertion, independent of model IDs."""

    return "pae-" + _stable_digest(
        resolution_id,
        _value(polarity),
        tuple(sorted(source_structure_unit_ids)),
        tuple(sorted(source_span_ids)),
        excerpt,
        rationale,
    )


def stable_phase_applicability_override_id(
    resolution_id: str,
    override_ordinal: int,
) -> str:
    if override_ordinal < 1:
        raise ValueError("人工覆盖序号必须从 1 起")
    return "pao-" + _stable_digest(resolution_id, "override", override_ordinal)


class PhaseApplicabilityFrozenPackage(Phase5ControlModel):
    """Frozen owned/context source package presented to a semantic Agent."""

    package_id: str = Field(min_length=1)
    coverage_manifest_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    protocol_document_sha256: str = Field(pattern=_SHA256)
    snapshot_id: str = Field(min_length=1)
    package_ordinal: int = Field(ge=1)
    selected_phase: StudyPhase
    opposite_phase: StudyPhase | None = None
    owned_units: list[ProtocolStructureUnit] = Field(min_length=1)
    context_units: list[ProtocolStructureUnit] = Field(default_factory=list)
    frozen_source_span_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_package(self) -> "PhaseApplicabilityFrozenPackage":
        if self.selected_phase == StudyPhase.OTHER:
            raise ValueError("期别语义包必须绑定 II 期、III 期或无缝期别")
        expected_opposite = {
            StudyPhase.PHASE_II: StudyPhase.PHASE_III,
            StudyPhase.PHASE_III: StudyPhase.PHASE_II,
            StudyPhase.SEAMLESS_II_III: None,
        }[self.selected_phase]
        if self.opposite_phase != expected_opposite:
            raise ValueError("对侧期别必须由选定期别确定")

        owned_ids = [item.structure_unit_id for item in self.owned_units]
        context_ids = [item.structure_unit_id for item in self.context_units]
        _require_unique_nonempty(owned_ids, "owned_units.structure_unit_id")
        _require_unique_nonempty(context_ids, "context_units.structure_unit_id")
        if set(owned_ids) & set(context_ids):
            raise ValueError("owned/context 结构单元不得重叠")
        if self.owned_units != sorted(self.owned_units, key=lambda item: item.source_order):
            raise ValueError("owned_units 必须按原文顺序排列")
        if self.context_units != sorted(self.context_units, key=lambda item: item.source_order):
            raise ValueError("context_units 必须按原文顺序排列")
        if any(item.study_phase != self.selected_phase for item in (*self.owned_units, *self.context_units)):
            raise ValueError("冻结包结构单元期别必须与选定期别一致")

        expected_spans = sorted(
            {
                span_id
                for unit in (*self.owned_units, *self.context_units)
                for span_id in unit.source_span_ids
            }
        )
        _require_sorted_unique(self.frozen_source_span_ids, "frozen_source_span_ids")
        if self.frozen_source_span_ids != expected_spans:
            raise ValueError("冻结来源片段必须闭合到 owned/context 结构单元")
        expected_package_id = stable_phase_applicability_package_id(
            self.coverage_manifest_id,
            self.package_ordinal,
            owned_ids,
        )
        if self.package_id != expected_package_id:
            raise ValueError("package_id 必须由系统根据冻结 owned 身份生成")
        return self

    @property
    def all_units(self) -> tuple[ProtocolStructureUnit, ...]:
        return (*self.owned_units, *self.context_units)

    @property
    def owned_structure_unit_ids(self) -> tuple[str, ...]:
        return tuple(item.structure_unit_id for item in self.owned_units)

    @property
    def all_structure_unit_ids(self) -> tuple[str, ...]:
        return tuple(item.structure_unit_id for item in self.all_units)


class PhaseApplicabilityEvidenceDraft(Phase5ControlModel):
    """Agent evidence reference using only indexes into the frozen package."""

    polarity: PhaseApplicabilityEvidencePolarity
    source_unit_indexes: list[int] = Field(min_length=1)
    source_span_indexes: list[int] = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_evidence_draft(self) -> "PhaseApplicabilityEvidenceDraft":
        _require_indexes(self.source_unit_indexes, "source_unit_indexes")
        _require_indexes(self.source_span_indexes, "source_span_indexes")
        return self


class PhaseApplicabilityCandidateDraft(Phase5ControlModel):
    """Agent candidate phase and positional evidence links, without IDs."""

    scope: PhaseScope
    supporting_evidence_indexes: list[int] = Field(default_factory=list)
    opposing_evidence_indexes: list[int] = Field(default_factory=list)
    unresolved_evidence_indexes: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_candidate_draft(self) -> "PhaseApplicabilityCandidateDraft":
        _require_indexes(self.supporting_evidence_indexes, "supporting_evidence_indexes")
        _require_indexes(self.opposing_evidence_indexes, "opposing_evidence_indexes")
        _require_indexes(self.unresolved_evidence_indexes, "unresolved_evidence_indexes")
        groups = (
            set(self.supporting_evidence_indexes),
            set(self.opposing_evidence_indexes),
            set(self.unresolved_evidence_indexes),
        )
        if groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2]:
            raise ValueError("同一候选的支持、反对和未解决来源不得重复归类")
        if not any(groups):
            raise ValueError("候选期别至少需要一条来源依据")
        return self


class PhaseApplicabilityResolutionDraft(Phase5ControlModel):
    """Provider-neutral result batch; all stable identities are deliberately absent."""

    unit_index: int = Field(ge=0)
    evidence: list[PhaseApplicabilityEvidenceDraft] = Field(min_length=1)
    candidates: list[PhaseApplicabilityCandidateDraft] = Field(min_length=1)
    final_disposition: PhaseApplicabilityDisposition
    rationale: str = Field(min_length=1)
    unresolved_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_resolution_draft(self) -> "PhaseApplicabilityResolutionDraft":
        scopes = [item.scope for item in self.candidates]
        if len(scopes) != len(set(scopes)):
            raise ValueError("同一结构单元候选期别不得重复")
        evidence_count = len(self.evidence)
        for candidate in self.candidates:
            indexes = (
                *candidate.supporting_evidence_indexes,
                *candidate.opposing_evidence_indexes,
                *candidate.unresolved_evidence_indexes,
            )
            if any(index >= evidence_count for index in indexes):
                raise ValueError("候选引用了当前结构单元结果之外的证据")
        referenced_indexes = {
            index
            for candidate in self.candidates
            for index in (
                *candidate.supporting_evidence_indexes,
                *candidate.opposing_evidence_indexes,
                *candidate.unresolved_evidence_indexes,
            )
        }
        if referenced_indexes != set(range(evidence_count)):
            raise ValueError("每条证据都必须绑定至少一个候选期别")
        if self.final_disposition == PhaseApplicabilityDisposition.UNRESOLVED and not self.unresolved_reason:
            raise ValueError("仍待确认处置必须记录 unresolved_reason")
        return self


class PhaseApplicabilityResolutionBatchDraft(Phase5ControlModel):
    """Optional batch envelope for multiple owned units in one model response."""

    results: list[PhaseApplicabilityResolutionDraft] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_batch(self) -> "PhaseApplicabilityResolutionBatchDraft":
        unit_indexes = [item.unit_index for item in self.results]
        if len(unit_indexes) != len(set(unit_indexes)):
            raise ValueError("同一语义批次每个 frozen owned 单元只能有一条结果")
        return self


class PhaseApplicabilityEvidence(Phase5ControlModel):
    """Hydrated source-backed evidence with system identity."""

    evidence_id: str = Field(min_length=1)
    polarity: PhaseApplicabilityEvidencePolarity
    source_structure_unit_ids: list[str] = Field(min_length=1)
    source_span_ids: list[str] = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_evidence(self) -> "PhaseApplicabilityEvidence":
        _require_sorted_unique(self.source_structure_unit_ids, "source_structure_unit_ids")
        _require_sorted_unique(self.source_span_ids, "source_span_ids")
        return self


class PhaseApplicabilityCandidateEvaluation(Phase5ControlModel):
    """Hydrated candidate phase with typed evidence polarity links."""

    candidate_id: str = Field(min_length=1)
    scope: PhaseScope
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    opposing_evidence_ids: list[str] = Field(default_factory=list)
    unresolved_evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_candidate(self) -> "PhaseApplicabilityCandidateEvaluation":
        for values, label in (
            (self.supporting_evidence_ids, "supporting_evidence_ids"),
            (self.opposing_evidence_ids, "opposing_evidence_ids"),
            (self.unresolved_evidence_ids, "unresolved_evidence_ids"),
        ):
            _require_sorted_unique(values, label)
        groups = (
            set(self.supporting_evidence_ids),
            set(self.opposing_evidence_ids),
            set(self.unresolved_evidence_ids),
        )
        if groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2]:
            raise ValueError("同一候选的证据身份不得跨极性重复")
        return self


class PhaseApplicabilityManualOverrideRecord(Phase5ControlModel):
    """Immutable audit record; override never changes the result identity."""

    override_id: str = Field(min_length=1)
    override_ordinal: int = Field(ge=1)
    before_resolution_id: str = Field(min_length=1)
    after_resolution_id: str = Field(min_length=1)
    before_disposition: PhaseApplicabilityDisposition
    after_disposition: PhaseApplicabilityDisposition
    reason: str = Field(min_length=1)
    overridden_by: str = Field(min_length=1)
    overridden_at: datetime

    @model_validator(mode="after")
    def validate_override(self) -> "PhaseApplicabilityManualOverrideRecord":
        if self.before_resolution_id != self.after_resolution_id:
            raise ValueError("人工覆盖不得改变期别语义结果身份")
        if self.before_disposition == self.after_disposition:
            raise ValueError("人工覆盖前后处置不能相同")
        return self


class PhaseApplicabilityUnitResolution(Phase5ControlModel):
    """One system-identified unit result, including semantic and manual layers."""

    package_id: str = Field(min_length=1)
    coverage_manifest_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    selected_phase: StudyPhase
    opposite_phase: StudyPhase | None = None
    resolution_id: str = Field(min_length=1)
    structure_unit_id: str = Field(min_length=1)
    evidence: list[PhaseApplicabilityEvidence] = Field(min_length=1)
    candidate_evaluations: list[PhaseApplicabilityCandidateEvaluation] = Field(min_length=1)
    semantic_disposition: PhaseApplicabilityDisposition
    final_disposition: PhaseApplicabilityDisposition
    rationale: str = Field(min_length=1)
    unresolved_reason: str | None = Field(default=None, min_length=1)
    manual_overrides: list[PhaseApplicabilityManualOverrideRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_resolution(self) -> "PhaseApplicabilityUnitResolution":
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("期别语义证据身份不得重复")
        candidate_ids = [item.candidate_id for item in self.candidate_evaluations]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("期别语义候选身份不得重复")
        scopes = [item.scope for item in self.candidate_evaluations]
        if len(scopes) != len(set(scopes)):
            raise ValueError("期别语义候选期别不得重复")
        known_evidence = set(evidence_ids)
        for candidate in self.candidate_evaluations:
            linked = (
                *candidate.supporting_evidence_ids,
                *candidate.opposing_evidence_ids,
                *candidate.unresolved_evidence_ids,
            )
            if not set(linked) <= known_evidence:
                raise ValueError("候选不得引用当前结果之外的证据身份")
        referenced_evidence = {
            evidence_id
            for candidate in self.candidate_evaluations
            for evidence_id in (
                *candidate.supporting_evidence_ids,
                *candidate.opposing_evidence_ids,
                *candidate.unresolved_evidence_ids,
            )
        }
        if referenced_evidence != known_evidence:
            raise ValueError("每条证据都必须绑定至少一个候选期别")
        if self.semantic_disposition == PhaseApplicabilityDisposition.UNRESOLVED and not self.unresolved_reason:
            raise ValueError("仍待确认语义结果必须记录 unresolved_reason")
        override_ordinals = [item.override_ordinal for item in self.manual_overrides]
        if override_ordinals != list(range(1, len(override_ordinals) + 1)):
            raise ValueError("人工覆盖历史必须按连续序号排列")
        return self


class PhaseApplicabilityResolutionSet(Phase5ControlModel):
    """All semantic results for one frozen package."""

    package_id: str = Field(min_length=1)
    coverage_manifest_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    selected_phase: StudyPhase
    opposite_phase: StudyPhase | None = None
    # An all-structurally-explicit package may legitimately have no semantic
    # Agent results; the deterministic gate still checks every ambiguous unit.
    results: list[PhaseApplicabilityUnitResolution] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result_set(self) -> "PhaseApplicabilityResolutionSet":
        unit_ids = [item.structure_unit_id for item in self.results]
        if len(unit_ids) != len(set(unit_ids)):
            raise ValueError("一个冻结包内每个结构单元只能有一条期别语义结果")
        if any(
            item.package_id != self.package_id
            or item.coverage_manifest_id != self.coverage_manifest_id
            or item.protocol_version_id != self.protocol_version_id
            or item.selected_phase != self.selected_phase
            or item.opposite_phase != self.opposite_phase
            for item in self.results
        ):
            raise ValueError("期别语义结果必须绑定同一冻结包和选定期别")
        return self

    @property
    def result_by_unit(self) -> dict[str, PhaseApplicabilityUnitResolution]:
        return {item.structure_unit_id: item for item in self.results}
