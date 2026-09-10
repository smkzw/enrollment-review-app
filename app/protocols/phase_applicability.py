"""Deterministic hydration and publication gate for semantic phase results."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from dataclasses import dataclass
import re

from app.domain.contracts.enums import PhaseScope, StudyPhase
from app.domain.contracts.phase_applicability import (
    PhaseApplicabilityCandidateEvaluation,
    PhaseApplicabilityDisposition,
    PhaseApplicabilityEvidence,
    PhaseApplicabilityFrozenPackage,
    PhaseApplicabilityManualOverrideRecord,
    PhaseApplicabilityResolutionBatchDraft,
    PhaseApplicabilityResolutionDraft,
    PhaseApplicabilityResolutionSet,
    PhaseApplicabilityUnitResolution,
    stable_phase_applicability_candidate_id,
    stable_phase_applicability_evidence_id,
    stable_phase_applicability_override_id,
    stable_phase_applicability_resolution_id,
)
from app.domain.contracts.protocol_controls import StructureUnitKind

PHASE_APPLICABILITY_GATE_VERSION = "phase5/phase-applicability-gate/v2"

_WHITESPACE_RE = re.compile(r"\s+")
_HEADING_NUMBER_PREFIX_RE = re.compile(
    r"^\s*(?:第\s*)?(?:[0-9]+(?:[.．][0-9]+)*|[一二三四五六七八九十百]+|[IVXLC]+)"
    r"\s*[、.．:：\-\s]*",
    re.IGNORECASE,
)
_PLACEHOLDER_HEADINGS = {"（无标题）", "(无标题)", "（上级标题未识别）", "(上级标题未识别)"}
_SOURCE_CROSS_REFERENCE_RE = re.compile(
    r"(?:参见|详见|见(?:表|图|附录)?|同前|同上|refer(?:\s+to)?|see)",
    re.IGNORECASE,
)
_TARGET_APPLICABILITY_CUE_RE = re.compile(
    r"(?:符合|满足|不符合|不满足|遵守|执行|完成|记录|审核|评估|"
    r"禁止|不得|(?<!对)应|需|须|包括|采用|使用|进行|一致|相同|共同)",
    re.IGNORECASE,
)
_PHASE_RANGE_CUE_RE = re.compile(
    r"(?:所有|任何|全部|均|共同|适用于|每(?:项|一|个)|须|必须|不得|不允许)",
    re.IGNORECASE,
)
_PHASE_SPECIFIC_HEADING_RE = re.compile(
    r"(?:Ⅱ|II|2|二)\s*期|(?:Ⅲ|III|3|三)\s*期",
    re.IGNORECASE,
)
_GENERIC_RULE_TITLE_LABELS = frozenset(
    {
        "研究设计",
        "试验设计",
        "方案设计",
        "研究阶段",
        "研究期别",
        "流程",
        "要求",
        "标准",
    }
)

__all__ = [
    "PHASE_APPLICABILITY_GATE_VERSION",
    "PhaseApplicabilityGateError",
    "PhaseApplicabilityGateIssue",
    "PhaseApplicabilityGateReport",
    "PhaseApplicabilityHydrationError",
    "check_phase_applicability_gate",
    "check_phase_applicability_resolution",
    "gate_phase_applicability_resolution",
    "hydrate_phase_applicability_resolution",
    "record_phase_applicability_manual_override",
    "validate_phase_applicability_resolution",
]


class PhaseApplicabilityHydrationError(ValueError):
    """A provider draft cannot be mapped to the frozen package."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class PhaseApplicabilityGateError(ValueError):
    """A deterministic phase applicability publication stop."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        structure_unit_id: str | None = None,
    ) -> None:
        self.code = code
        self.structure_unit_id = structure_unit_id
        suffix = f" [{structure_unit_id}]" if structure_unit_id else ""
        super().__init__(f"{code}{suffix}: {message}")


@dataclass(frozen=True)
class PhaseApplicabilityGateIssue:
    """Compact non-throwing diagnostic returned by the check helper."""

    code: str
    message: str
    structure_unit_id: str | None = None


@dataclass(frozen=True)
class PhaseApplicabilityGateReport:
    accepted: bool
    gate_version: str
    issues: tuple[PhaseApplicabilityGateIssue, ...] = ()

    def __init__(
        self,
        *,
        accepted: bool,
        issues: Iterable[PhaseApplicabilityGateIssue] = (),
    ) -> None:
        object.__setattr__(self, "accepted", accepted)
        object.__setattr__(self, "gate_version", PHASE_APPLICABILITY_GATE_VERSION)
        object.__setattr__(self, "issues", tuple(issues))


def _value(value: object) -> str:
    return str(getattr(value, "value", value))


def _normalize_source_excerpt(value: str) -> str:
    """Use the project's ordinary whitespace-folding source normalization."""

    return _WHITESPACE_RE.sub(" ", value.strip())


def _normalize_heading_label(value: object) -> str:
    label = _HEADING_NUMBER_PREFIX_RE.sub("", str(value).strip())
    return _WHITESPACE_RE.sub(" ", label).casefold()


def _heading_labels(unit: object) -> tuple[str, ...]:
    return tuple(
        label
        for segment in getattr(unit, "heading_path", ())
        if str(segment).strip() not in _PLACEHOLDER_HEADINGS
        if (label := _normalize_heading_label(segment))
    )


def _rule_title_label(unit: object) -> str:
    labels = _heading_labels(unit)
    return labels[-1] if labels else ""


def _same_rule_family(left: object, right: object) -> bool:
    """Match repeated copies of one atomic obligation, not a whole section.

    The previous intersection test made ``5 研究设计`` sufficient to join
    every descendant rule under that chapter.  Matching only the final title
    remained too broad: different laboratory tests or flow-table notes often
    share one section title while expressing unrelated obligations.  A
    title-only or section-level source must explicitly reference the target;
    implicit same-family propagation is limited to verbatim repeated atomic
    obligations (including corresponding repeated table content).
    """

    left_title = _rule_title_label(left)
    right_title = _rule_title_label(right)
    left_excerpt = _normalize_source_excerpt(str(getattr(left, "excerpt", "")))
    right_excerpt = _normalize_source_excerpt(str(getattr(right, "excerpt", "")))
    return bool(
        left_title
        and left_title == right_title
        and left_title not in _GENERIC_RULE_TITLE_LABELS
        and left_excerpt
        and left_excerpt == right_excerpt
    )


def _has_shared_heading_ancestor(left: object, right: object) -> bool:
    """Return whether two units share a parent heading.

    This is deliberately *not* a rule-family match.  It is used only for the
    narrow, phase-specific cross-reference exception below.
    """

    left_parents = set(_heading_labels(left)[:-1])
    right_parents = set(_heading_labels(right)[:-1])
    return bool(left_parents.intersection(right_parents))


def _explicitly_references_target_family(target: object, source: object) -> bool:
    target_label = _rule_title_label(target)
    if len(target_label) < 2:
        return False
    excerpt = _normalize_source_excerpt(str(getattr(source, "excerpt", ""))).casefold()
    if not excerpt or target_label not in excerpt:
        return False

    # A source whose own excerpt is exactly the frozen title is a direct title
    # anchor (common for table-title and procedure-title units).
    if (
        excerpt == target_label
        or _normalize_heading_label(excerpt) == target_label
        or _rule_title_label(source) == target_label
    ):
        return True

    # A title substring in an unrelated narrative is only a mention.  Require
    # either a nearby explicit reference marker or a nearby rule/applicability
    # predicate before treating it as target evidence.
    for match in re.finditer(re.escape(target_label), excerpt):
        window = excerpt[max(0, match.start() - 32) : match.end() + 32]
        if _SOURCE_CROSS_REFERENCE_RE.search(window) or _TARGET_APPLICABILITY_CUE_RE.search(window):
            return True
    return False


def _phase_specific_cross_reference(target: object, source: object) -> bool:
    """Allow a resolved phase-branch cross-reference without global fan-out.

    A phase-specific sibling may point back to the target's rule location by
    number (so the target title need not be repeated), but only when the source
    is itself phase-specific, carries an explicit cross-reference marker, and
    shares a structural parent.  A common parent alone never qualifies.
    """

    if not _has_shared_heading_ancestor(target, source):
        return False
    excerpt = _normalize_source_excerpt(str(getattr(source, "excerpt", "")))
    heading = " ".join(str(item) for item in getattr(source, "heading_path", ()))
    return bool(
        _SOURCE_CROSS_REFERENCE_RE.search(excerpt)
        and _PHASE_SPECIFIC_HEADING_RE.search(heading)
    )


def _target_related_source(target: object, source: object) -> bool:
    """Return whether a source is specific enough to support this target."""

    target_id = getattr(target, "structure_unit_id", None)
    source_id = getattr(source, "structure_unit_id", None)
    return (
        (bool(target_id) and target_id == source_id)
        or _same_rule_family(target, source)
        or _explicitly_references_target_family(target, source)
        or _phase_specific_cross_reference(target, source)
    )


def _explicitly_scopes_target_family(target: object, source: object) -> bool:
    """Require an explicit range statement before propagating phase scope."""

    target_label = _rule_title_label(target)
    if len(target_label) < 2:
        return False
    excerpt = _normalize_source_excerpt(str(getattr(source, "excerpt", ""))).casefold()
    if target_label not in excerpt:
        return False
    if excerpt == target_label or _normalize_heading_label(excerpt) == target_label:
        return True
    for match in re.finditer(re.escape(target_label), excerpt):
        suffix = excerpt[match.end() : match.end() + 8]
        if re.match(r"(?:的)?(?:结果|结论|建议)", suffix):
            continue
        window = excerpt[max(0, match.start() - 32) : match.end() + 32]
        if _SOURCE_CROSS_REFERENCE_RE.search(window) or _PHASE_RANGE_CUE_RE.search(window):
            return True
    return False


def _phase_range_source(target: object, source: object) -> bool:
    """Return whether target-related evidence may propagate phase scope.

    Target relation and phase-range authority are separate contracts.  An
    exact title in an unscoped/unknown unit can address the target, but it must
    not establish a selected/opposite/shared phase range.  Mixed scopes are
    likewise never propagated.
    """

    scopes = tuple(getattr(source, "phase_scopes", ()))
    target_id = getattr(target, "structure_unit_id", None)
    source_id = getattr(source, "structure_unit_id", None)
    carries_range = (
        (bool(target_id) and target_id == source_id)
        or _same_rule_family(target, source)
        or _explicitly_scopes_target_family(target, source)
        or _phase_specific_cross_reference(target, source)
    )
    return (
        carries_range
        and len(scopes) == 1
        and _value(scopes[0])
        in {
            _value(PhaseScope.PHASE_II),
            _value(PhaseScope.PHASE_III),
            _value(PhaseScope.SHARED),
            _value(PhaseScope.SEAMLESS_CANDIDATE),
        }
    )


def _references_target_rule_family(target: object, source: object) -> bool:
    """Backward-compatible alias for the target-related source predicate."""

    return _target_related_source(target, source)


def _excerpt_recovered_from_units(
    excerpt: str,
    source_units: Iterable[object],
) -> bool:
    """Require an exact normalized substring in at least one cited unit."""

    normalized_excerpt = _normalize_source_excerpt(excerpt)
    if not normalized_excerpt:
        return False
    return any(
        normalized_excerpt in _normalize_source_excerpt(str(getattr(unit, "excerpt", "")))
        for unit in source_units
    )


def _selected_scope(selected_phase: StudyPhase) -> PhaseScope:
    return {
        StudyPhase.PHASE_II: PhaseScope.PHASE_II,
        StudyPhase.PHASE_III: PhaseScope.PHASE_III,
        StudyPhase.SEAMLESS_II_III: PhaseScope.SEAMLESS_CANDIDATE,
    }[selected_phase]


def _opposite_scope(package: PhaseApplicabilityFrozenPackage) -> PhaseScope | None:
    if package.opposite_phase is None:
        return None
    return _selected_scope(package.opposite_phase)


def _allowed_scopes(package: PhaseApplicabilityFrozenPackage) -> set[PhaseScope]:
    result = {_selected_scope(package.selected_phase), PhaseScope.SHARED}
    opposite = _opposite_scope(package)
    if opposite is not None:
        result.add(opposite)
    if package.selected_phase == StudyPhase.SEAMLESS_II_III:
        result.update({PhaseScope.PHASE_II, PhaseScope.PHASE_III})
    return result


def _structurally_explicit_disposition(
    package: PhaseApplicabilityFrozenPackage,
    unit,
) -> PhaseApplicabilityDisposition | None:
    scopes = set(unit.phase_scopes)
    if len(scopes) != 1 or scopes & {PhaseScope.UNKNOWN, PhaseScope.MIXED}:
        return None
    scope = next(iter(scopes))
    if scope == _selected_scope(package.selected_phase):
        return PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE
    if scope == PhaseScope.SHARED:
        return PhaseApplicabilityDisposition.CROSS_PHASE_SHARED
    if _opposite_scope(package) == scope:
        return PhaseApplicabilityDisposition.OPPOSITE_PHASE_APPLICABLE
    return None


def _raise_hydration(code: str, message: str) -> None:
    raise PhaseApplicabilityHydrationError(code, message)


def _unit_at(package: PhaseApplicabilityFrozenPackage, index: int):
    if index < 0 or index >= len(package.all_units):
        _raise_hydration("PACKAGE_UNIT_INDEX_OUT_OF_RANGE", f"结构单元索引越界：{index}")
    return package.all_units[index]


def _span_at(package: PhaseApplicabilityFrozenPackage, index: int) -> str:
    if index < 0 or index >= len(package.frozen_source_span_ids):
        _raise_hydration("PACKAGE_SPAN_INDEX_OUT_OF_RANGE", f"来源片段索引越界：{index}")
    return package.frozen_source_span_ids[index]


def _evidence_source_units(package, evidence_draft):
    """Recover a wrong positional unit echo only from one exact source closure."""

    source_units = [
        _unit_at(package, index) for index in evidence_draft.source_unit_indexes
    ]
    source_spans = [
        _span_at(package, index) for index in evidence_draft.source_span_indexes
    ]
    allowed_spans = {
        span_id for source in source_units for span_id in source.source_span_ids
    }
    if set(source_spans) <= allowed_spans and _excerpt_recovered_from_units(
        evidence_draft.excerpt,
        source_units,
    ):
        return source_units, source_spans

    candidates = [
        unit
        for unit in package.all_units
        if set(source_spans) <= set(unit.source_span_ids)
        and _excerpt_recovered_from_units(evidence_draft.excerpt, [unit])
    ]
    if len(candidates) == 1:
        return candidates, source_spans
    if not set(source_spans) <= allowed_spans:
        _raise_hydration(
            "EVIDENCE_SPAN_UNIT_MISMATCH",
            "证据来源片段必须属于其引用的冻结结构单元",
        )
    _raise_hydration(
        "EVIDENCE_EXCERPT_NOT_VERBATIM",
        "证据摘录经空白规范化后无法在任一引用结构单元中逐字恢复",
    )


def hydrate_phase_applicability_resolution(
    package: PhaseApplicabilityFrozenPackage,
    draft: PhaseApplicabilityResolutionDraft | PhaseApplicabilityResolutionBatchDraft,
) -> PhaseApplicabilityResolutionSet:
    """Hydrate positional Agent output into system-owned identities.

    The draft has no package, unit, evidence, candidate or override identity
    fields.  Every source reference is resolved against the supplied frozen
    package, and a draft cannot cite a span that is not owned by one of its
    cited units.
    """

    drafts = draft.results if isinstance(draft, PhaseApplicabilityResolutionBatchDraft) else [draft]
    seen_unit_indexes: set[int] = set()
    hydrated: list[PhaseApplicabilityUnitResolution] = []
    owned_count = len(package.owned_units)
    for item in drafts:
        if item.unit_index >= owned_count:
            _raise_hydration(
                "RESULT_UNIT_NOT_OWNED",
                f"结果 unit_index 必须指向 owned 单元：{item.unit_index}",
            )
        if item.unit_index in seen_unit_indexes:
            _raise_hydration(
                "RESULT_UNIT_DUPLICATE",
                f"结果重复引用 owned 单元：{item.unit_index}",
            )
        seen_unit_indexes.add(item.unit_index)
        unit = package.owned_units[item.unit_index]
        resolution_id = stable_phase_applicability_resolution_id(
            package.coverage_manifest_id,
            package.protocol_version_id,
            package.selected_phase,
            unit.structure_unit_id,
        )
        evidence: list[PhaseApplicabilityEvidence] = []
        for evidence_draft in item.evidence:
            source_units, source_spans = _evidence_source_units(
                package,
                evidence_draft,
            )
            source_unit_ids = sorted({source.structure_unit_id for source in source_units})
            source_span_ids = sorted(set(source_spans))
            evidence_id = stable_phase_applicability_evidence_id(
                resolution_id,
                evidence_draft.polarity,
                source_unit_ids,
                source_span_ids,
                evidence_draft.excerpt,
                evidence_draft.rationale,
            )
            evidence.append(
                PhaseApplicabilityEvidence(
                    evidence_id=evidence_id,
                    polarity=evidence_draft.polarity,
                    source_structure_unit_ids=source_unit_ids,
                    source_span_ids=source_span_ids,
                    excerpt=evidence_draft.excerpt,
                    rationale=evidence_draft.rationale,
                )
            )

        evidence_ids = [item.evidence_id for item in evidence]
        candidates: list[PhaseApplicabilityCandidateEvaluation] = []
        for candidate_draft in item.candidates:
            indexes = (
                *candidate_draft.supporting_evidence_indexes,
                *candidate_draft.opposing_evidence_indexes,
                *candidate_draft.unresolved_evidence_indexes,
            )
            if any(index >= len(evidence_ids) for index in indexes):
                _raise_hydration(
                    "CANDIDATE_EVIDENCE_OUT_OF_RANGE",
                    "候选证据索引超出当前结构单元结果",
                )
            candidate_id = stable_phase_applicability_candidate_id(
                resolution_id,
                candidate_draft.scope,
            )
            candidates.append(
                PhaseApplicabilityCandidateEvaluation(
                    candidate_id=candidate_id,
                    scope=candidate_draft.scope,
                    supporting_evidence_ids=sorted(
                        {evidence_ids[index] for index in candidate_draft.supporting_evidence_indexes}
                    ),
                    opposing_evidence_ids=sorted(
                        {evidence_ids[index] for index in candidate_draft.opposing_evidence_indexes}
                    ),
                    unresolved_evidence_ids=sorted(
                        {evidence_ids[index] for index in candidate_draft.unresolved_evidence_indexes}
                    ),
                )
            )

        hydrated.append(
            PhaseApplicabilityUnitResolution(
                package_id=package.package_id,
                coverage_manifest_id=package.coverage_manifest_id,
                protocol_version_id=package.protocol_version_id,
                selected_phase=package.selected_phase,
                opposite_phase=package.opposite_phase,
                resolution_id=resolution_id,
                structure_unit_id=unit.structure_unit_id,
                evidence=evidence,
                candidate_evaluations=sorted(candidates, key=lambda value: value.scope.value),
                semantic_disposition=item.final_disposition,
                final_disposition=item.final_disposition,
                rationale=item.rationale,
                unresolved_reason=item.unresolved_reason,
            )
        )

    hydrated.sort(key=lambda item: package.owned_structure_unit_ids.index(item.structure_unit_id))
    return PhaseApplicabilityResolutionSet(
        package_id=package.package_id,
        coverage_manifest_id=package.coverage_manifest_id,
        protocol_version_id=package.protocol_version_id,
        selected_phase=package.selected_phase,
        opposite_phase=package.opposite_phase,
        results=hydrated,
    )


def record_phase_applicability_manual_override(
    result: PhaseApplicabilityUnitResolution,
    *,
    after_disposition: PhaseApplicabilityDisposition,
    reason: str,
    overridden_by: str,
    overridden_at: datetime,
) -> PhaseApplicabilityUnitResolution:
    """Return a new immutable result revision with the same stable identity."""

    if not reason.strip():
        raise ValueError("人工覆盖必须记录理由")
    if after_disposition == result.final_disposition:
        raise ValueError("人工覆盖前后处置不能相同")
    if after_disposition == PhaseApplicabilityDisposition.UNRESOLVED:
        unresolved_evidence_ids = {
            evidence_id
            for candidate in result.candidate_evaluations
            for evidence_id in candidate.unresolved_evidence_ids
        }
        evidence_by_id = {item.evidence_id: item for item in result.evidence}
        if not any(
            evidence_by_id.get(evidence_id) is not None
            and evidence_by_id[evidence_id].polarity.value == "unresolved"
            for evidence_id in unresolved_evidence_ids
        ):
            raise ValueError(
                "UNRESOLVED_OVERRIDE_EVIDENCE_MISSING: "
                "人工覆盖为仍待确认时必须已有候选级未解决来源"
            )
    ordinal = len(result.manual_overrides) + 1
    override = PhaseApplicabilityManualOverrideRecord(
        override_id=stable_phase_applicability_override_id(
            result.resolution_id,
            ordinal,
        ),
        override_ordinal=ordinal,
        before_resolution_id=result.resolution_id,
        after_resolution_id=result.resolution_id,
        before_disposition=result.final_disposition,
        after_disposition=after_disposition,
        reason=reason,
        overridden_by=overridden_by,
        overridden_at=overridden_at,
    )
    return result.model_copy(
        update={
            "final_disposition": after_disposition,
            "unresolved_reason": (
                reason
                if after_disposition == PhaseApplicabilityDisposition.UNRESOLVED
                else result.unresolved_reason
            ),
            "manual_overrides": [*result.manual_overrides, override],
        }
    )


def _issue(
    issues: list[PhaseApplicabilityGateIssue],
    code: str,
    message: str,
    unit_id: str | None = None,
) -> None:
    issues.append(
        PhaseApplicabilityGateIssue(
            code,
            message,
            structure_unit_id=unit_id,
        )
    )


def _mixed_unit_requires_atomization(unit: object) -> bool:
    """Keep structurally composite mixed units out of a one-result contract."""

    return (
        getattr(unit, "unit_kind", None)
        in {
            StructureUnitKind.TABLE_HEADER,
            StructureUnitKind.TABLE_ROW,
            StructureUnitKind.TABLE_NOTE,
        }
        and len(getattr(unit, "member_source_refs", ())) > 1
    )


def _validate_effective_disposition(
    package: PhaseApplicabilityFrozenPackage,
    result: PhaseApplicabilityUnitResolution,
    issues: list[PhaseApplicabilityGateIssue],
) -> None:
    unit_id = result.structure_unit_id
    evidence_by_id = {item.evidence_id: item for item in result.evidence}
    candidate_by_scope = {item.scope: item for item in result.candidate_evaluations}
    source_unit_by_id = {
        item.structure_unit_id: item for item in package.all_units
    }
    target_unit = source_unit_by_id.get(unit_id)

    for candidate in result.candidate_evaluations:
        if candidate.scope not in _allowed_scopes(package):
            _issue(issues, "CANDIDATE_SCOPE_UNSUPPORTED", "候选期别不属于选定期别及对侧范围", unit_id)
            continue
        expected_candidate_id = stable_phase_applicability_candidate_id(
            result.resolution_id,
            candidate.scope,
        )
        if candidate.candidate_id != expected_candidate_id:
            _issue(issues, "CANDIDATE_ID_MISMATCH", "候选身份不是系统根据期别范围生成的身份", unit_id)
        for field_name, polarity in (
            ("supporting_evidence_ids", "supports"),
            ("opposing_evidence_ids", "opposes"),
            ("unresolved_evidence_ids", "unresolved"),
        ):
            for evidence_id in getattr(candidate, field_name):
                evidence = evidence_by_id.get(evidence_id)
                if evidence is None:
                    _issue(issues, "CANDIDATE_EVIDENCE_UNKNOWN", "候选引用了当前结果之外的证据", unit_id)
                elif evidence.polarity.value != polarity:
                    _issue(issues, "CANDIDATE_EVIDENCE_POLARITY_CONFLICT", "候选证据极性与证据记录不一致", unit_id)

    effective = result.final_disposition
    selected_candidate = candidate_by_scope.get(_selected_scope(package.selected_phase))
    opposite_scope = _opposite_scope(package)
    opposite_candidate = candidate_by_scope.get(opposite_scope) if opposite_scope else None
    shared_candidate = candidate_by_scope.get(PhaseScope.SHARED)

    def supported(candidate) -> bool:
        return candidate is not None and bool(candidate.supporting_evidence_ids)

    def clean(candidate) -> bool:
        return candidate is not None and not (
            candidate.opposing_evidence_ids or candidate.unresolved_evidence_ids
        )

    def has_target_related_support(candidate) -> bool:
        if candidate is None or target_unit is None:
            return False
        return any(
            source.structure_unit_id == target_unit.structure_unit_id
            or _target_related_source(target_unit, source)
            for evidence_id in candidate.supporting_evidence_ids
            if evidence_id in evidence_by_id
            for source_unit_id in evidence_by_id[evidence_id].source_structure_unit_ids
            if (source := source_unit_by_id.get(source_unit_id)) is not None
        )

    def paired_rule_family_sources_present() -> bool:
        if target_unit is None:
            return False
        scopes = {
            scope
            for source in package.all_units
            if _phase_range_source(target_unit, source)
            for scope in source.phase_scopes
        }
        opposite = _opposite_scope(package)
        return (
            opposite is not None
            and _selected_scope(package.selected_phase) in scopes
            and opposite in scopes
        )

    def has_shared_rule_family_source(candidate) -> bool:
        if candidate is None or target_unit is None:
            return False
        supporting_units = [
            source_unit_by_id[source_unit_id]
            for evidence_id in candidate.supporting_evidence_ids
            if evidence_id in evidence_by_id
            for source_unit_id in evidence_by_id[evidence_id].source_structure_unit_ids
            if source_unit_id in source_unit_by_id
        ]
        if any(
            _phase_range_source(target_unit, source)
            and PhaseScope.SHARED in source.phase_scopes
            and (
                source.structure_unit_id == target_unit.structure_unit_id
                or _target_related_source(target_unit, source)
            )
            for source in supporting_units
        ):
            return True
        referenced_scopes = {
            scope
            for source in supporting_units
            if _phase_range_source(target_unit, source)
            for scope in source.phase_scopes
        }
        opposite_scope = _opposite_scope(package)
        return (
            opposite_scope is not None
            and _selected_scope(package.selected_phase) in referenced_scopes
            and opposite_scope in referenced_scopes
        )

    if effective == PhaseApplicabilityDisposition.UNRESOLVED:
        if not result.unresolved_reason:
            _issue(issues, "UNRESOLVED_REASON_MISSING", "仍待确认处置必须说明未决理由", unit_id)
        if not any(
            candidate.unresolved_evidence_ids
            for candidate in result.candidate_evaluations
        ):
            _issue(issues, "UNRESOLVED_EVIDENCE_MISSING", "仍待确认处置必须保留未解决来源", unit_id)
        if (
            not result.manual_overrides
            and (
                selected_candidate is None
                or not selected_candidate.unresolved_evidence_ids
            )
        ):
            _issue(
                issues,
                "SELECTED_PHASE_UNRESOLVED_EVIDENCE_MISSING",
                "仍待确认必须说明当前选定期别为何无法确定；仅未证明跨期共用不能阻断当前期别纳入",
                unit_id,
            )
        return

    if effective == PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE:
        if not supported(selected_candidate) or not clean(selected_candidate):
            _issue(issues, "FINAL_DISPOSITION_UNSUPPORTED", "选定期别处置缺少干净的支持依据", unit_id)
        elif not has_target_related_support(selected_candidate):
            _issue(
                issues,
                "TARGET_RELATED_SUPPORT_MISSING",
                "选定期别处置的支持来源未直接指向目标或其规则标题族",
                unit_id,
            )
        if supported(opposite_candidate) or supported(shared_candidate):
            _issue(issues, "CONTRADICTORY_FINAL_DISPOSITION", "选定期别处置与另一有支持依据的候选冲突", unit_id)
        if paired_rule_family_sources_present() and not (
            opposite_candidate and opposite_candidate.opposing_evidence_ids
        ):
            _issue(
                issues,
                "PAIRED_RULE_FAMILY_SOURCE_IGNORED",
                "冻结来源已分别显示两期均指向同一规则标题；单列本期必须提供对侧不适用的反证",
                unit_id,
            )
        return

    if effective == PhaseApplicabilityDisposition.OPPOSITE_PHASE_APPLICABLE:
        if opposite_candidate is None:
            _issue(issues, "FINAL_DISPOSITION_UNSUPPORTED", "对侧期别处置没有对侧候选", unit_id)
        elif not supported(opposite_candidate) or not clean(opposite_candidate):
            _issue(issues, "FINAL_DISPOSITION_UNSUPPORTED", "对侧期别处置缺少干净的支持依据", unit_id)
        elif not has_target_related_support(opposite_candidate):
            _issue(
                issues,
                "TARGET_RELATED_SUPPORT_MISSING",
                "对侧期别处置的支持来源未直接指向目标或其规则标题族",
                unit_id,
            )
        if supported(selected_candidate) or supported(shared_candidate):
            _issue(issues, "CONTRADICTORY_FINAL_DISPOSITION", "对侧期别处置与另一有支持依据的候选冲突", unit_id)
        if paired_rule_family_sources_present() and not (
            selected_candidate and selected_candidate.opposing_evidence_ids
        ):
            _issue(
                issues,
                "PAIRED_RULE_FAMILY_SOURCE_IGNORED",
                "冻结来源已分别显示两期均指向同一规则标题；单列对侧期必须提供本期不适用的反证",
                unit_id,
            )
        return

    if effective == PhaseApplicabilityDisposition.CROSS_PHASE_SHARED:
        if not supported(shared_candidate) or not clean(shared_candidate):
            _issue(issues, "SHARED_UNSUPPORTED", "跨期共享处置必须有明确共享支持依据", unit_id)
        elif not has_shared_rule_family_source(shared_candidate):
            _issue(
                issues,
                "SHARED_POSITIVE_SOURCE_MISSING",
                "跨期共享处置必须引用同一规则标题族的共用来源，或分别引用两期均明确指向该规则标题的正向来源",
                unit_id,
            )
        if supported(selected_candidate) or supported(opposite_candidate):
            _issue(issues, "CONTRADICTORY_FINAL_DISPOSITION", "共享处置与有支持依据的单期期别候选冲突", unit_id)


def _validate_manual_history(
    result: PhaseApplicabilityUnitResolution,
    issues: list[PhaseApplicabilityGateIssue],
) -> None:
    unit_id = result.structure_unit_id
    current = result.semantic_disposition
    for expected_ordinal, override in enumerate(result.manual_overrides, start=1):
        if override.override_ordinal != expected_ordinal:
            _issue(issues, "MANUAL_OVERRIDE_ORDER", "人工覆盖序号必须连续", unit_id)
        expected_id = stable_phase_applicability_override_id(
            result.resolution_id,
            expected_ordinal,
        )
        if override.override_id != expected_id:
            _issue(issues, "MANUAL_OVERRIDE_ID_MISMATCH", "人工覆盖身份不是系统派生身份", unit_id)
        if (
            override.before_resolution_id != result.resolution_id
            or override.after_resolution_id != result.resolution_id
        ):
            _issue(issues, "MANUAL_OVERRIDE_IDENTITY_MUTATED", "人工覆盖不得改变前后结果身份", unit_id)
        if override.before_disposition != current:
            _issue(issues, "MANUAL_OVERRIDE_CHAIN_BROKEN", "人工覆盖 before 处置与历史链不一致", unit_id)
        current = override.after_disposition
    if current != result.final_disposition:
        _issue(issues, "FINAL_DISPOSITION_HISTORY_MISMATCH", "最终处置未闭合到人工覆盖历史", unit_id)


def check_phase_applicability_resolution(
    package: PhaseApplicabilityFrozenPackage,
    resolutions: PhaseApplicabilityResolutionSet,
) -> PhaseApplicabilityGateReport:
    """Return deterministic diagnostics without repairing the result set."""

    issues: list[PhaseApplicabilityGateIssue] = []
    if resolutions.package_id != package.package_id:
        _issue(issues, "PACKAGE_ID_MISMATCH", "结果集未绑定当前冻结包")
    if resolutions.coverage_manifest_id != package.coverage_manifest_id:
        _issue(issues, "MANIFEST_ID_MISMATCH", "结果集未绑定当前全文覆盖清单")
    if resolutions.protocol_version_id != package.protocol_version_id:
        _issue(issues, "PROTOCOL_VERSION_MISMATCH", "结果集未绑定当前方案版本")
    if resolutions.selected_phase != package.selected_phase or resolutions.opposite_phase != package.opposite_phase:
        _issue(issues, "PHASE_CONTEXT_MISMATCH", "结果集选定/对侧期别与冻结包不一致")

    owned_by_id = {item.structure_unit_id: item for item in package.owned_units}
    all_by_id = {item.structure_unit_id: item for item in package.all_units}

    for result in resolutions.results:
        owned_unit = owned_by_id.get(result.structure_unit_id)
        if (
            owned_unit is not None
            and PhaseScope.MIXED in owned_unit.phase_scopes
            and _mixed_unit_requires_atomization(owned_unit)
            and result.final_disposition
            != PhaseApplicabilityDisposition.UNRESOLVED
        ):
            _issue(
                issues,
                "MIXED_UNIT_REQUIRES_ATOMIZATION",
                "同一复合表格单元内含不同期别成员，在拆分为可独立溯源的单元前不得形成明确期别处置",
                result.structure_unit_id,
            )

    result_by_id: dict[str, PhaseApplicabilityUnitResolution] = {}
    for result in resolutions.results:
        unit_id = result.structure_unit_id
        if unit_id in result_by_id:
            _issue(issues, "UNIT_RESULT_DUPLICATE", "同一结构单元出现多个语义结果", unit_id)
            continue
        result_by_id[unit_id] = result
        if unit_id not in owned_by_id:
            _issue(issues, "UNIT_RESULT_OUTSIDE_FROZEN_PACKAGE", "语义结果不是 frozen owned 结构单元", unit_id)
            continue
        expected_resolution_id = stable_phase_applicability_resolution_id(
            package.coverage_manifest_id,
            package.protocol_version_id,
            package.selected_phase,
            unit_id,
        )
        if result.resolution_id != expected_resolution_id:
            _issue(issues, "RESOLUTION_ID_MISMATCH", "语义结果身份不是系统根据冻结单元生成的身份", unit_id)
        if (
            result.package_id != package.package_id
            or result.coverage_manifest_id != package.coverage_manifest_id
            or result.protocol_version_id != package.protocol_version_id
            or result.selected_phase != package.selected_phase
            or result.opposite_phase != package.opposite_phase
        ):
            _issue(issues, "RESULT_CONTEXT_MISMATCH", "单元语义结果未绑定当前冻结包上下文", unit_id)

        package_unit_ids = set(all_by_id)
        package_span_ids = set(package.frozen_source_span_ids)
        for evidence in result.evidence:
            if not set(evidence.source_structure_unit_ids) <= package_unit_ids:
                _issue(issues, "EVIDENCE_UNIT_OUTSIDE_FROZEN_PACKAGE", "证据引用了冻结包外结构单元", unit_id)
            if not set(evidence.source_span_ids) <= package_span_ids:
                _issue(issues, "EVIDENCE_SPAN_OUTSIDE_FROZEN_PACKAGE", "证据引用了冻结包外来源片段", unit_id)
            cited_spans = {
                span_id
                for cited_unit_id in evidence.source_structure_unit_ids
                if cited_unit_id in all_by_id
                for span_id in all_by_id[cited_unit_id].source_span_ids
            }
            if not set(evidence.source_span_ids) <= cited_spans:
                _issue(issues, "EVIDENCE_SPAN_UNIT_MISMATCH", "证据来源片段不属于其引用的结构单元", unit_id)
            cited_units = [
                all_by_id[cited_unit_id]
                for cited_unit_id in evidence.source_structure_unit_ids
                if cited_unit_id in all_by_id
            ]
            if not _excerpt_recovered_from_units(evidence.excerpt, cited_units):
                _issue(
                    issues,
                    "EVIDENCE_EXCERPT_NOT_VERBATIM",
                    "证据摘录经空白规范化后无法在任一引用结构单元中逐字恢复",
                    unit_id,
                )
            expected_evidence_id = stable_phase_applicability_evidence_id(
                result.resolution_id,
                evidence.polarity,
                evidence.source_structure_unit_ids,
                evidence.source_span_ids,
                evidence.excerpt,
                evidence.rationale,
            )
            if evidence.evidence_id != expected_evidence_id:
                _issue(issues, "EVIDENCE_ID_MISMATCH", "证据身份不是系统根据来源和内容生成的身份", unit_id)

        _validate_manual_history(result, issues)
        referenced_evidence = {
            evidence_id
            for candidate in result.candidate_evaluations
            for evidence_id in (
                *candidate.supporting_evidence_ids,
                *candidate.opposing_evidence_ids,
                *candidate.unresolved_evidence_ids,
            )
        }
        if referenced_evidence != {item.evidence_id for item in result.evidence}:
            _issue(issues, "EVIDENCE_ORPHANED", "每条证据都必须绑定至少一个候选期别", unit_id)
        _validate_effective_disposition(package, result, issues)
        structural_disposition = _structurally_explicit_disposition(
            package,
            owned_by_id[unit_id],
        )
        if (
            structural_disposition is not None
            and result.final_disposition != structural_disposition
        ):
            _issue(
                issues,
                "CONTRADICTORY_FINAL_DISPOSITION",
                "语义最终处置不得覆盖结构单元已明确的期别范围",
                unit_id,
            )

    for unit in package.owned_units:
        if unit.structure_unit_id in result_by_id:
            continue
        if _structurally_explicit_disposition(package, unit) is None:
            _issue(
                issues,
                "UNIT_RESULT_MISSING",
                "UNKNOWN/MIXED 或复合候选结构单元必须有语义期别结果",
                unit.structure_unit_id,
            )

    return PhaseApplicabilityGateReport(accepted=not issues, issues=issues)


def gate_phase_applicability_resolution(
    package: PhaseApplicabilityFrozenPackage,
    resolutions: PhaseApplicabilityResolutionSet,
) -> PhaseApplicabilityResolutionSet:
    report = check_phase_applicability_resolution(package, resolutions)
    if not report.accepted:
        first = report.issues[0]
        raise PhaseApplicabilityGateError(
            first.code,
            first.message,
            structure_unit_id=first.structure_unit_id,
        )
    return resolutions


def validate_phase_applicability_resolution(
    package: PhaseApplicabilityFrozenPackage,
    resolutions: PhaseApplicabilityResolutionSet,
) -> PhaseApplicabilityResolutionSet:
    return gate_phase_applicability_resolution(package, resolutions)


check_phase_applicability_gate = check_phase_applicability_resolution
