#!/usr/bin/env python3
"""Deterministic reject gates for slice59n representative-group replay.

Research-only validators. Do not invent clinical obligations: they enforce
worker_01 stop conditions as structural checks against prepare rows and
hydrated Agent output (source presence, phase identity, required time anchors,
and repair-scope protection via the product runner).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


# Cross-chapter refs that package-72 context cannot supply alone.
VIRAL_TB_REQUIRED_ATTACHED_REFS = frozenset(
    {
        "body.t5.r18",
        "body.p328",
        "body.t5.r19",
        "body.p329",
        "body.p649",
        "body.p650",
        "body.p651",
        "body.p652",
        "body.p653",
        "body.p655",
        "body.p685",
        "body.p686",
        "body.p687",
        "body.p688",
        "body.p689",
    }
)

VIRAL_TB_REQUIRED_OWNED_REFS = frozenset(
    {
        "body.p802",
        "body.p803",
        "body.p804",
        "body.p805",
        "body.p806",
        "body.p807",
        "body.p808",
        "body.p809",
        "body.p810",
        "body.p811",
        "body.p812",
        "body.p813",
    }
)

# Material assessment atoms that must keep distinct time anchors when promoted.
VIRAL_TB_REQUIRED_TIME_ANCHORS: Mapping[str, frozenset[str]] = {
    "body.p804": frozenset({"first_dose_date"}),
    "body.p805": frozenset({"first_dose_date"}),
    "body.p809": frozenset({"randomization_date"}),
    "body.p811": frozenset({"first_dose_date"}),
}

# Frozen-excerpt markers that must survive if the unit is a control candidate.
# Structural presence checks only; not shared-app clinical keyword patching.
VIRAL_TB_REQUIRED_MARKERS: Mapping[str, tuple[str, ...]] = {
    "body.p808": ("不得被随机", "活动性结核"),
    "body.p809": ("潜伏性结核", "至少4周"),
    "body.p811": ("首次给药前至少4周", "预防性治疗"),
    "body.p812": ("利福平", "利福喷丁"),
    "body.p813": ("不确定", "1次"),
    "body.p804": ("首次给药前28天",),
    "body.p805": ("首次给药前28天",),
    "body.p807": ("胸部CT",),
}


@dataclass(frozen=True)
class RejectIssue:
    code: str
    message: str
    source_refs: tuple[str, ...] = ()
    structure_unit_ids: tuple[str, ...] = ()

    def as_wire_message(self) -> str:
        refs = ",".join(self.source_refs) if self.source_refs else "-"
        return f"{self.code}: {self.message} (refs={refs})"


def _row_map(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(row["source_ref"]): row for row in rows}


def evaluate_prepare_source_closure(
    *,
    group_id: str,
    rows: Sequence[Mapping[str, Any]],
    owned_source_refs: Sequence[str],
    attached_source_refs: Sequence[str],
    study_phase: str,
) -> list[RejectIssue]:
    """Reject missing config refs or phase-blind packing before any Agent call."""

    issues: list[RejectIssue] = []
    by_ref = _row_map(rows)
    expected = list(owned_source_refs) + list(attached_source_refs)
    missing = [ref for ref in expected if ref not in by_ref]
    if missing:
        issues.append(
            RejectIssue(
                code="SOURCE_MISSING",
                message="configured source_ref unresolved in prepare rows",
                source_refs=tuple(missing),
            )
        )

    owned = {ref for ref, row in by_ref.items() if row.get("role") == "owned"}
    attached = {ref for ref, row in by_ref.items() if row.get("role") == "attached"}
    if set(owned_source_refs) - owned:
        issues.append(
            RejectIssue(
                code="SOURCE_MISSING",
                message="owned_source_refs missing owned role rows",
                source_refs=tuple(sorted(set(owned_source_refs) - owned)),
            )
        )
    if set(attached_source_refs) - attached:
        issues.append(
            RejectIssue(
                code="SOURCE_MISSING",
                message="attached_source_refs missing attached role rows",
                source_refs=tuple(sorted(set(attached_source_refs) - attached)),
            )
        )

    if group_id == "d001-ii-viral-tb-cross-chapter":
        if VIRAL_TB_REQUIRED_OWNED_REFS - owned:
            issues.append(
                RejectIssue(
                    code="SOURCE_MISSING",
                    message="viral/TB owned assessment set incomplete",
                    source_refs=tuple(sorted(VIRAL_TB_REQUIRED_OWNED_REFS - owned)),
                )
            )
        if VIRAL_TB_REQUIRED_ATTACHED_REFS - attached:
            issues.append(
                RejectIssue(
                    code="CONTEXT_BLIND_CROSS_CHAPTER",
                    message=(
                        "package-72 alone is insufficient; EX/flow attachments "
                        "must be packed for source closure"
                    ),
                    source_refs=tuple(
                        sorted(VIRAL_TB_REQUIRED_ATTACHED_REFS - attached)
                    ),
                )
            )
        # t5.r18/r19 only exist in coverage_manifest for this freeze.
        for ref in ("body.t5.r18", "body.t5.r19"):
            row = by_ref.get(ref)
            if row is not None and row.get("lookup") != "coverage_manifest":
                issues.append(
                    RejectIssue(
                        code="IDENTITY_DRIFT",
                        message=f"{ref} must resolve via coverage_manifest",
                        source_refs=(ref,),
                    )
                )

    for ref, row in by_ref.items():
        phase = str(row.get("study_phase") or study_phase)
        if phase and phase != study_phase and "study_phase" in row:
            issues.append(
                RejectIssue(
                    code="PHASE_MISMATCH",
                    message=(
                        f"prepare row study_phase={phase!r} != config "
                        f"study_phase={study_phase!r}"
                    ),
                    source_refs=(ref,),
                    structure_unit_ids=(str(row.get("structure_unit_id") or ""),),
                )
            )
    return issues


def _candidate_unit_ids(candidate: Mapping[str, Any]) -> set[str]:
    frozen = candidate.get("frozen_structure_unit_ids") or []
    if frozen:
        return {str(item) for item in frozen}
    return {str(item) for item in (candidate.get("source_structure_unit_ids") or [])}


def _iter_obligation_atoms(candidate: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    semantics = candidate.get("semantics") or {}
    expression = semantics.get("obligation_expression") or {}
    for group in expression.get("groups") or []:
        for atom in group.get("atoms") or []:
            yield atom


def _iter_exception_atoms(candidate: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    semantics = candidate.get("semantics") or {}
    expression = semantics.get("exception_expression") or {}
    for group in expression.get("groups") or []:
        for atom in group.get("atoms") or []:
            yield atom


def _text_blob(candidate: Mapping[str, Any]) -> str:
    parts: list[str] = [str(candidate.get("title") or "")]
    semantics = candidate.get("semantics") or {}
    for expression_name in ("applicability_expression", "trigger_expression"):
        expression = semantics.get(expression_name) or {}
        for group in expression.get("groups") or []:
            for atom in group.get("atoms") or []:
                parts.append(str(atom.get("statement") or ""))
                parts.extend(str(item) for item in (atom.get("source_excerpts") or []))
    for atom in _iter_obligation_atoms(candidate):
        parts.append(str(atom.get("statement") or ""))
        parts.extend(str(item) for item in (atom.get("source_excerpts") or []))
    for atom in _iter_exception_atoms(candidate):
        parts.append(str(atom.get("statement") or ""))
        parts.extend(str(item) for item in (atom.get("source_excerpts") or []))
    return "\n".join(parts)


def _assertion_text_blob(candidate: Mapping[str, Any]) -> str:
    """Collect model-authored assertions without letting source quotes mask omissions."""

    parts: list[str] = [str(candidate.get("title") or "")]
    semantics = candidate.get("semantics") or {}
    for expression_name in (
        "applicability_expression",
        "trigger_expression",
        "obligation_expression",
        "exception_expression",
    ):
        expression = semantics.get(expression_name) or {}
        for group in expression.get("groups") or []:
            for atom in group.get("atoms") or []:
                parts.append(str(atom.get("statement") or ""))
    return "\n".join(parts)


def _anchors_for_candidate(candidate: Mapping[str, Any]) -> set[str]:
    anchors: set[str] = set()
    for atom in list(_iter_obligation_atoms(candidate)) + list(
        _iter_exception_atoms(candidate)
    ):
        tc = atom.get("time_constraint") or {}
        anchor = tc.get("anchor_type")
        if anchor:
            anchors.add(str(anchor))
    return anchors


def evaluate_hydrated_agent_output(
    *,
    group_id: str,
    study_phase: str,
    rows: Sequence[Mapping[str, Any]],
    hydrated: Mapping[str, Any] | None,
    allowed_structure_unit_ids: Sequence[str],
    required_candidate_source_refs: Sequence[str] = (),
    forbidden_candidate_source_refs: Sequence[str] = (),
    expected_disposition_by_source_ref: Mapping[str, str] | None = None,
    expected_workflow_stage_ids_by_source_ref: Mapping[
        str, Sequence[str]
    ] | None = None,
    candidate_forbidden_markers_by_source_ref: Mapping[str, Sequence[str]] | None = None,
    candidate_required_markers_by_source_ref: Mapping[str, Sequence[str]] | None = None,
) -> list[RejectIssue]:
    """Reject source gaps, phase misfit, logic weakening, or scope creep."""

    issues: list[RejectIssue] = []
    if hydrated is None:
        return [
            RejectIssue(
                code="SOURCE_MISSING",
                message="hydrated Agent output missing; cannot close sources",
            )
        ]

    by_ref = _row_map(rows)
    ref_by_unit = {
        str(row["structure_unit_id"]): str(row["source_ref"]) for row in rows
    }
    allowed = set(allowed_structure_unit_ids)
    candidates = list(hydrated.get("candidates") or [])
    dispositions = list(hydrated.get("dispositions") or [])

    for candidate in candidates:
        unit_ids = _candidate_unit_ids(candidate)
        outside = sorted(unit_ids - allowed)
        if outside:
            issues.append(
                RejectIssue(
                    code="SCOPE_CREEP",
                    message="candidate cites structure units outside configured group",
                    structure_unit_ids=tuple(outside),
                    source_refs=tuple(
                        ref_by_unit[unit_id]
                        for unit_id in outside
                        if unit_id in ref_by_unit
                    ),
                )
            )
        phase = str(candidate.get("study_phase") or study_phase)
        if candidate.get("study_phase") and phase != study_phase:
            issues.append(
                RejectIssue(
                    code="PHASE_MISMATCH",
                    message=(
                        f"candidate study_phase={phase!r} != config "
                        f"study_phase={study_phase!r}"
                    ),
                    structure_unit_ids=tuple(sorted(unit_ids)),
                    source_refs=tuple(
                        ref_by_unit[unit_id]
                        for unit_id in sorted(unit_ids)
                        if unit_id in ref_by_unit
                    ),
                )
            )
        for atom in _iter_obligation_atoms(candidate):
            spans = [str(item) for item in (atom.get("source_span_ids") or [])]
            if not spans:
                issues.append(
                    RejectIssue(
                        code="SOURCE_MISSING",
                        message="obligation atom missing source_span_ids",
                        structure_unit_ids=tuple(sorted(unit_ids)),
                    )
                )

    disposed_control_units = {
        str(item.get("structure_unit_id"))
        for item in dispositions
        if str(item.get("disposition") or "").endswith("CONTROL_CANDIDATE")
        or str(item.get("disposition") or "") == "other_control_candidate"
        or str(item.get("disposition") or "") == "OTHER_CONTROL_CANDIDATE"
    }
    # Be tolerant of enum value shapes from model_dump.
    for item in dispositions:
        disp = str(item.get("disposition") or "")
        if "control_candidate" in disp.lower():
            disposed_control_units.add(str(item.get("structure_unit_id")))

    unit_to_candidates: dict[str, list[Mapping[str, Any]]] = {}
    for candidate in candidates:
        for unit_id in _candidate_unit_ids(candidate):
            unit_to_candidates.setdefault(unit_id, []).append(candidate)

    disposition_by_unit = {
        str(item.get("structure_unit_id")): str(item.get("disposition") or "")
        for item in dispositions
    }
    for ref, expected in sorted(
        (expected_disposition_by_source_ref or {}).items()
    ):
        row = by_ref.get(ref)
        if row is None:
            continue
        unit_id = str(row["structure_unit_id"])
        actual = disposition_by_unit.get(unit_id, "")
        if actual != expected:
            issues.append(
                RejectIssue(
                    code="DISPOSITION_MISMATCH",
                    message=(
                        f"{ref} disposition={actual!r} does not match "
                        f"expected disposition={expected!r}"
                    ),
                    source_refs=(ref,),
                    structure_unit_ids=(unit_id,),
                )
            )

    for ref in sorted(set(required_candidate_source_refs)):
        row = by_ref.get(ref)
        if row is None:
            continue
        unit_id = str(row["structure_unit_id"])
        if unit_id not in unit_to_candidates:
            issues.append(
                RejectIssue(
                    code="CONTROL_DELTA_DROPPED",
                    message=(
                        f"{ref} contains a clinical control delta absent "
                        "from the frozen official/procedure target"
                    ),
                    source_refs=(ref,),
                    structure_unit_ids=(unit_id,),
                )
            )

    for ref, expected_stage_ids in sorted(
        (expected_workflow_stage_ids_by_source_ref or {}).items()
    ):
        row = by_ref.get(ref)
        if row is None:
            continue
        unit_id = str(row["structure_unit_id"])
        actual_stage_ids = {
            str(binding.get("workflow_stage_id"))
            for candidate in unit_to_candidates.get(unit_id, [])
            for binding in (
                (candidate.get("semantics") or {}).get("review_node_bindings")
                or []
            )
            if binding.get("workflow_stage_id")
        }
        expected = set(expected_stage_ids)
        if actual_stage_ids != expected:
            issues.append(
                RejectIssue(
                    code="REVIEW_STAGE_SCOPE_MISMATCH",
                    message=(
                        f"{ref} workflow stages={sorted(actual_stage_ids)} do not "
                        f"match expected stages={sorted(expected)}"
                    ),
                    source_refs=(ref,),
                    structure_unit_ids=(unit_id,),
                )
            )

    for ref in sorted(set(forbidden_candidate_source_refs)):
        row = by_ref.get(ref)
        if row is None:
            continue
        unit_id = str(row["structure_unit_id"])
        if unit_to_candidates.get(unit_id):
            issues.append(
                RejectIssue(
                    code="CONTROL_DUPLICATE_RETAINED",
                    message=f"{ref} is fully covered for enrollment review and must not publish a duplicate candidate",
                    source_refs=(ref,),
                    structure_unit_ids=(unit_id,),
                )
            )

    for ref, markers in sorted(
        (candidate_forbidden_markers_by_source_ref or {}).items()
    ):
        row = by_ref.get(ref)
        if row is None:
            continue
        unit_id = str(row["structure_unit_id"])
        blob = "\n".join(
            _assertion_text_blob(candidate)
            for candidate in unit_to_candidates.get(unit_id, [])
        )
        duplicated = [marker for marker in markers if marker in blob]
        if duplicated:
            issues.append(
                RejectIssue(
                    code="COVERED_BRANCH_DUPLICATED",
                    message=(
                        f"{ref} candidate repeats branches already covered by the frozen target: "
                        f"{duplicated}"
                    ),
                    source_refs=(ref,),
                    structure_unit_ids=(unit_id,),
                )
            )

    for ref, markers in sorted(
        (candidate_required_markers_by_source_ref or {}).items()
    ):
        row = by_ref.get(ref)
        if row is None:
            continue
        unit_id = str(row["structure_unit_id"])
        blob = "\n".join(
            _assertion_text_blob(candidate)
            for candidate in unit_to_candidates.get(unit_id, [])
        )
        missing = [marker for marker in markers if marker not in blob]
        if missing:
            issues.append(
                RejectIssue(
                    code="CONTROL_DELTA_COMPONENT_DROPPED",
                    message=(
                        f"{ref} candidate drops directly sourced control "
                        f"components: {missing}"
                    ),
                    source_refs=(ref,),
                    structure_unit_ids=(unit_id,),
                )
            )

    if group_id in {
        "d001-ii-viral-tb-cross-chapter",
        "d001-ii-viral-cross-chapter",
        "d001-ii-tb-cross-chapter",
    }:
        # Owning only the assessment chapter without EX/flow attachments already
        # failed prepare. Candidate controls must preserve the known anchors and
        # clinical markers for this bounded real-protocol oracle.

        for ref, required_anchors in VIRAL_TB_REQUIRED_TIME_ANCHORS.items():
            row = by_ref.get(ref)
            if row is None:
                continue
            unit_id = str(row["structure_unit_id"])
            if unit_id not in disposed_control_units and unit_id not in unit_to_candidates:
                continue
            found: set[str] = set()
            for candidate in unit_to_candidates.get(unit_id, []):
                found |= _anchors_for_candidate(candidate)
            missing_anchors = set(required_anchors) - found
            if missing_anchors:
                issues.append(
                    RejectIssue(
                        code="LOGIC_WEAKENING",
                        message=(
                            "required time anchor missing or collapsed for "
                            f"{ref}: expected {sorted(required_anchors)}, "
                            f"found {sorted(found)}"
                        ),
                        source_refs=(ref,),
                        structure_unit_ids=(unit_id,),
                    )
                )

        for ref, markers in VIRAL_TB_REQUIRED_MARKERS.items():
            row = by_ref.get(ref)
            if row is None:
                continue
            unit_id = str(row["structure_unit_id"])
            if unit_id not in disposed_control_units and unit_id not in unit_to_candidates:
                continue
            blob = "\n".join(
                _text_blob(candidate)
                for candidate in unit_to_candidates.get(unit_id, [])
            )
            missing_markers = [marker for marker in markers if marker not in blob]
            if missing_markers:
                issues.append(
                    RejectIssue(
                        code="LOGIC_WEAKENING",
                        message=(
                            f"control candidate for {ref} dropped required "
                            f"markers {missing_markers}"
                        ),
                        source_refs=(ref,),
                        structure_unit_ids=(unit_id,),
                    )
                )

        # Dual latent anchors must remain distinct across the group when both
        # p809 and p811 are control candidates.
        p809 = by_ref.get("body.p809")
        p811 = by_ref.get("body.p811")
        if p809 is not None and p811 is not None:
            u809 = str(p809["structure_unit_id"])
            u811 = str(p811["structure_unit_id"])
            if u809 in unit_to_candidates and u811 in unit_to_candidates:
                a809 = set()
                a811 = set()
                for candidate in unit_to_candidates[u809]:
                    a809 |= _anchors_for_candidate(candidate)
                for candidate in unit_to_candidates[u811]:
                    a811 |= _anchors_for_candidate(candidate)
                if a809 == {"first_dose_date"} and a811 == {"first_dose_date"}:
                    issues.append(
                        RejectIssue(
                            code="LOGIC_WEAKENING",
                            message=(
                                "latent TB dual anchors collapsed: p809 "
                                "randomization gate lost distinct "
                                "randomization_date vs p811 first_dose_date"
                            ),
                            source_refs=("body.p809", "body.p811"),
                            structure_unit_ids=(u809, u811),
                        )
                    )

    return issues


def first_reject(issues: Sequence[RejectIssue]) -> RejectIssue | None:
    return issues[0] if issues else None


def assert_no_rejects(issues: Sequence[RejectIssue]) -> None:
    issue = first_reject(issues)
    if issue is not None:
        raise AssertionError(issue.as_wire_message())
