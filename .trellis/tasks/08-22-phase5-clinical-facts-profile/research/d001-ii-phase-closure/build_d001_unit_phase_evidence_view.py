#!/usr/bin/env python3
"""Build a deterministic, source-linked phase-evidence view for matrix units.

This is a research-artifact generator.  It does not resolve clinical phase
semantics and it does not treat a matrix ``phase_disposition`` as truth.  It
only joins the closed matrix to the current frozen coverage manifest and the
current semantic plan, then reports structural blockers, semantic uncertainty,
source conflicts, and row-level rollups.

The ``--plan`` input may be either a bare frozen plan or a phase-applicability
execution snapshot containing the plan under ``plan``.  The latter is the
current v2 D001 snapshot and is deliberately accepted without executing any
batch.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence


SELECTED_PHASE = "phase_ii"
OPPOSITE_PHASE = "phase_iii"
KNOWN_DISPOSITIONS = {"selected_phase_applicable", "cross_phase_shared"}


class UnitPhaseEvidenceError(ValueError):
    """A deterministic input or binding failure."""

    def __init__(self, code: str, message: str, *, context: str | None = None) -> None:
        self.code = code
        self.context = context
        suffix = f" ({context})" if context else ""
        super().__init__(f"{code}{suffix}: {message}")


def _nonempty_string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UnitPhaseEvidenceError("FIELD_INVALID", f"{field} must be a non-empty string")
    return value


def _list_of_strings(value: object, *, field: str, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise UnitPhaseEvidenceError("FIELD_INVALID", f"{field} must be an array")
    if not allow_empty and not value:
        raise UnitPhaseEvidenceError("FIELD_INVALID", f"{field} must not be empty")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise UnitPhaseEvidenceError("FIELD_INVALID", f"{field} must contain non-empty strings")
    return list(value)


def canonical_sha256(value: object) -> str:
    """Hash a JSON value independently of source key insertion order."""

    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _extract_plan(plan_payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    if not isinstance(plan_payload, Mapping):
        raise UnitPhaseEvidenceError("PLAN_INVALID", "plan must be an object")
    nested = plan_payload.get("plan")
    if nested is not None:
        if not isinstance(nested, Mapping):
            raise UnitPhaseEvidenceError("PLAN_INVALID", "execution snapshot plan must be an object")
        return nested, plan_payload
    return plan_payload, {}


def _identity_fields(payload: Mapping[str, Any], *, label: str) -> dict[str, str]:
    coverage_manifest_id = payload.get("coverage_manifest_id", payload.get("manifest_id"))
    return {
        "coverage_manifest_id": _nonempty_string(
            coverage_manifest_id, field=f"{label}.coverage_manifest_id"
        ),
        "snapshot_id": _nonempty_string(payload.get("snapshot_id"), field=f"{label}.snapshot_id"),
        "protocol_version_id": _nonempty_string(
            payload.get("protocol_version_id"), field=f"{label}.protocol_version_id"
        ),
        "protocol_document_sha256": _nonempty_string(
            payload.get("protocol_document_sha256"), field=f"{label}.protocol_document_sha256"
        ),
    }


def _validate_identity(
    manifest: Mapping[str, Any],
    matrix: Mapping[str, Any],
    plan: Mapping[str, Any],
    freeze_metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    manifest_identity = _identity_fields(manifest, label="manifest")
    matrix_identity = _identity_fields(matrix, label="matrix")
    plan_identity = {
        "coverage_manifest_id": _nonempty_string(
            plan.get("coverage_manifest_id"), field="plan.coverage_manifest_id"
        ),
        "protocol_version_id": _nonempty_string(
            plan.get("protocol_version_id"), field="plan.protocol_version_id"
        ),
    }
    selected_phase = _nonempty_string(matrix.get("selected_phase"), field="matrix.selected_phase")
    study_phase = _nonempty_string(manifest.get("study_phase"), field="manifest.study_phase")
    if selected_phase != study_phase or selected_phase != _nonempty_string(
        plan.get("study_phase"), field="plan.study_phase"
    ):
        raise UnitPhaseEvidenceError(
            "STUDY_PHASE_MISMATCH",
            "manifest, matrix, and plan selected study phase must be identical",
        )
    if manifest_identity["coverage_manifest_id"] != _nonempty_string(
        manifest.get("manifest_id"), field="manifest.manifest_id"
    ):
        raise UnitPhaseEvidenceError("MANIFEST_ID_INVALID", "manifest_id is invalid")
    if matrix_identity["coverage_manifest_id"] != manifest_identity["coverage_manifest_id"]:
        raise UnitPhaseEvidenceError("MANIFEST_ID_MISMATCH", "matrix is not bound to the current manifest")
    if plan_identity["coverage_manifest_id"] != manifest_identity["coverage_manifest_id"]:
        raise UnitPhaseEvidenceError("MANIFEST_ID_MISMATCH", "plan is not bound to the current manifest")
    for key in ("snapshot_id", "protocol_version_id", "protocol_document_sha256"):
        if matrix_identity[key] != manifest_identity[key]:
            raise UnitPhaseEvidenceError("PROTOCOL_IDENTITY_MISMATCH", f"matrix {key} differs from manifest")
    for key in ("protocol_version_id",):
        if plan_identity[key] != manifest_identity[key]:
            raise UnitPhaseEvidenceError("PROTOCOL_IDENTITY_MISMATCH", f"plan {key} differs from manifest")
    if bool(manifest.get("claims_full_coverage")) or bool(matrix.get("claims_complete")):
        raise UnitPhaseEvidenceError(
            "CLAIMS_COMPLETE_UNSAFE",
            "unit evidence view must not accept a complete-claims input",
        )

    freeze_identity: dict[str, Any] = {}
    if freeze_metadata is not None:
        if not isinstance(freeze_metadata, Mapping):
            raise UnitPhaseEvidenceError("FREEZE_METADATA_INVALID", "freeze metadata must be an object")
        for key in ("manifest_id", "snapshot_id", "protocol_version_id"):
            value = _nonempty_string(freeze_metadata.get(key), field=f"freeze_metadata.{key}")
            expected = {
                "manifest_id": manifest_identity["coverage_manifest_id"],
                "snapshot_id": manifest_identity["snapshot_id"],
                "protocol_version_id": manifest_identity["protocol_version_id"],
            }[key]
            if value != expected:
                raise UnitPhaseEvidenceError("FREEZE_IDENTITY_MISMATCH", f"freeze metadata {key} differs")
            freeze_identity[key] = value
        source = freeze_metadata.get("source")
        if isinstance(source, Mapping) and source.get("sha256"):
            source_sha = _nonempty_string(source.get("sha256"), field="freeze_metadata.source.sha256")
            if source_sha != manifest_identity["protocol_document_sha256"]:
                raise UnitPhaseEvidenceError("SOURCE_HASH_MISMATCH", "freeze source hash differs from manifest")
            freeze_identity["source_sha256"] = source_sha
        for key in ("run_id", "phase_graph_id", "projection_id", "manifest_payload_sha256", "plan_payload_sha256"):
            value = freeze_metadata.get(key)
            if value is not None:
                freeze_identity[key] = _nonempty_string(value, field=f"freeze_metadata.{key}")

    return {
        "selected_phase": selected_phase,
        "opposite_phase": OPPOSITE_PHASE if selected_phase == SELECTED_PHASE else SELECTED_PHASE,
        "manifest": {
            **manifest_identity,
            "manifest_id": manifest_identity["coverage_manifest_id"],
            "study_phase": study_phase,
        },
        "matrix": {
            "matrix_id": _nonempty_string(matrix.get("matrix_id"), field="matrix.matrix_id"),
            **matrix_identity,
            "selected_phase": selected_phase,
            "claims_complete": False,
        },
        "plan": {
            "plan_id": _nonempty_string(plan.get("plan_id"), field="plan.plan_id"),
            "schema_version": _nonempty_string(plan.get("schema_version"), field="plan.schema_version"),
            **plan_identity,
            "study_phase": study_phase,
        },
        "freeze_metadata": freeze_identity,
    }


def _validate_manifest(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    units = manifest.get("units")
    if not isinstance(units, list) or not units:
        raise UnitPhaseEvidenceError("MANIFEST_EMPTY", "manifest.units must be a non-empty array")
    by_id: dict[str, Mapping[str, Any]] = {}
    for unit in units:
        if not isinstance(unit, Mapping):
            raise UnitPhaseEvidenceError("UNIT_INVALID", "manifest unit must be an object")
        unit_id = _nonempty_string(unit.get("structure_unit_id"), field="unit.structure_unit_id")
        if unit_id in by_id:
            raise UnitPhaseEvidenceError("UNIT_DUPLICATE", f"duplicate structure unit: {unit_id}")
        _nonempty_string(unit.get("source_ref"), field=f"unit[{unit_id}].source_ref")
        _nonempty_string(unit.get("excerpt"), field=f"unit[{unit_id}].excerpt")
        _list_of_strings(unit.get("heading_path"), field=f"unit[{unit_id}].heading_path", allow_empty=False)
        _list_of_strings(unit.get("source_span_ids"), field=f"unit[{unit_id}].source_span_ids", allow_empty=False)
        scopes = _list_of_strings(unit.get("phase_scopes"), field=f"unit[{unit_id}].phase_scopes", allow_empty=False)
        if len(set(scopes)) != len(scopes):
            raise UnitPhaseEvidenceError("PHASE_SCOPE_DUPLICATE", f"duplicate phase scope: {unit_id}")
        by_id[unit_id] = unit
    return by_id


def _validate_plan(plan: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, Any]], dict[str, list[Mapping[str, Any]]], list[str]]:
    packages = plan.get("packages")
    expected = _list_of_strings(
        plan.get("expected_structure_unit_ids"), field="plan.expected_structure_unit_ids", allow_empty=False
    )
    if len(set(expected)) != len(expected):
        raise UnitPhaseEvidenceError("PLAN_TARGET_DUPLICATE", "plan expected structure unit ids must be unique")
    if not isinstance(packages, list) or not packages:
        raise UnitPhaseEvidenceError("PLAN_PACKAGES_EMPTY", "plan.packages must be a non-empty array")
    expected_set = set(expected)
    owned_by_id: dict[str, Mapping[str, Any]] = {}
    context_by_id: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    package_ids: set[str] = set()
    package_ordinals: set[int] = set()
    for package in packages:
        if not isinstance(package, Mapping):
            raise UnitPhaseEvidenceError("PLAN_PACKAGE_INVALID", "plan package must be an object")
        package_id = _nonempty_string(package.get("package_id"), field="package.package_id")
        ordinal = package.get("package_ordinal")
        if not isinstance(ordinal, int):
            raise UnitPhaseEvidenceError("PLAN_PACKAGE_INVALID", f"package ordinal invalid: {package_id}")
        if package_id in package_ids or ordinal in package_ordinals:
            raise UnitPhaseEvidenceError("PLAN_PACKAGE_DUPLICATE", f"duplicate package identity: {package_id}")
        package_ids.add(package_id)
        package_ordinals.add(ordinal)
        owned = package.get("owned_units")
        context = package.get("context_units")
        if not isinstance(owned, list) or not isinstance(context, list):
            raise UnitPhaseEvidenceError("PLAN_PACKAGE_INVALID", f"package units invalid: {package_id}")
        for role, units, destination in (("owned", owned, owned_by_id), ("context", context, context_by_id)):
            for unit in units:
                if not isinstance(unit, Mapping):
                    raise UnitPhaseEvidenceError("PLAN_UNIT_INVALID", f"{role} unit invalid: {package_id}")
                unit_id = _nonempty_string(unit.get("structure_unit_id"), field=f"{role}.structure_unit_id")
                if role == "owned":
                    if unit_id in destination:
                        raise UnitPhaseEvidenceError("PLAN_OWNERSHIP_DUPLICATE", f"owned unit repeated: {unit_id}")
                    destination[unit_id] = package
                else:
                    destination[unit_id].append(package)
    owned_set = set(owned_by_id)
    if owned_set != expected_set:
        missing = sorted(expected_set - owned_set)
        extra = sorted(owned_set - expected_set)
        raise UnitPhaseEvidenceError(
            "PLAN_OWNERSHIP_CLOSURE",
            f"plan owned units differ from expected targets; missing={missing[:5]} extra={extra[:5]}",
        )
    return owned_by_id, context_by_id, expected


def _anchor_assessment(
    anchor: Mapping[str, Any],
    unit: Mapping[str, Any] | None,
    *,
    row_id: str,
    row_disposition: str,
    selected_phase: str,
    opposite_phase: str,
) -> dict[str, Any]:
    anchor_id = str(anchor.get("source_anchor_id", ""))
    unit_id = str(anchor.get("structure_unit_id", ""))
    issues: list[str] = []
    if unit is None:
        return {
            "source_anchor_id": anchor_id,
            "structure_unit_id": unit_id,
            "structural_status": "blocked_structural",
            "semantic_status": "unresolved_semantic",
            "evidence_status": "blocked_structural",
            "relationship": "source_conflict",
            "blocker_codes": ["SOURCE_UNIT_UNKNOWN"],
            "source_conflict_codes": ["SOURCE_UNIT_UNKNOWN"],
            "phase_scopes": [],
            "matrix_phase_disposition": row_disposition,
            "matrix_disposition_claim_only": True,
        }
    scopes = _list_of_strings(unit.get("phase_scopes"), field=f"unit[{unit_id}].phase_scopes", allow_empty=False)
    scope_set = set(scopes)
    source_mismatches: list[str] = []
    if anchor.get("source_ref") != unit.get("source_ref"):
        source_mismatches.append("SOURCE_REF_MISMATCH")
    if anchor.get("heading_path_zh") != unit.get("heading_path"):
        source_mismatches.append("SOURCE_HEADING_PATH_MISMATCH")
    if set(anchor.get("source_span_ids", ())) != set(unit.get("source_span_ids", ())):
        source_mismatches.append("SOURCE_SPAN_CLOSURE_MISMATCH")
    excerpt = anchor.get("verbatim_excerpt")
    if not isinstance(excerpt, str) or excerpt not in str(unit.get("excerpt", "")):
        source_mismatches.append("VERBATIM_EXCERPT_NOT_FOUND")
    issues.extend(source_mismatches)

    if not scopes or "mixed" in scope_set or {selected_phase, opposite_phase}.issubset(scope_set):
        structural_status = "blocked_structural"
        semantic_status = "unresolved_semantic"
        evidence_status = "blocked_structural"
        issues.append("STRUCTURE_PHASE_BOUNDARY_MIXED")
    elif opposite_phase in scope_set:
        structural_status = "opposite_phase"
        semantic_status = "not_required"
        evidence_status = "blocked_structural"
        issues.append("OPPOSITE_PHASE_SOURCE")
    elif selected_phase in scope_set and scope_set == {selected_phase}:
        structural_status = "selected_phase"
        semantic_status = "not_required"
        evidence_status = "structurally_supported_candidate"
    elif "shared" in scope_set and scope_set == {"shared"}:
        structural_status = "shared_candidate"
        semantic_status = "unresolved_semantic"
        evidence_status = "unresolved_semantic"
        issues.append("SHARED_EVIDENCE_REQUIRES_OBLIGATION_FAMILY_PROOF")
    else:
        structural_status = "structurally_ambiguous"
        semantic_status = "unresolved_semantic"
        evidence_status = "unresolved_semantic"
        issues.append("PHASE_SCOPE_UNRESOLVED")

    relationship = "semantic_unresolved"
    relationship_codes: list[str] = []
    if source_mismatches:
        relationship = "source_conflict"
        relationship_codes.extend(source_mismatches)
    elif evidence_status == "blocked_structural":
        relationship = "structural_block"
        relationship_codes.extend(code for code in issues if code not in relationship_codes)
    elif evidence_status == "unresolved_semantic":
        relationship = "semantic_unresolved"
        relationship_codes.extend(issues)
    elif row_disposition == "selected_phase_applicable" and structural_status == "selected_phase":
        relationship = "compatible"
    elif row_disposition == "cross_phase_shared" and structural_status == "selected_phase":
        relationship = "source_conflict"
        relationship_codes.append("MATRIX_SHARED_DISPOSITION_CONFLICT")
    elif row_disposition not in KNOWN_DISPOSITIONS:
        relationship = "source_conflict"
        relationship_codes.append("MATRIX_DISPOSITION_UNKNOWN")
    elif structural_status == "selected_phase":
        relationship = "source_conflict"
        relationship_codes.append("MATRIX_DISPOSITION_NOT_SUPPORTED")

    return {
        "source_anchor_id": anchor_id,
        "structure_unit_id": unit_id,
        "structural_status": structural_status,
        "semantic_status": semantic_status,
        "evidence_status": evidence_status,
        "relationship": relationship,
        "blocker_codes": sorted(set(issues)),
        "source_conflict_codes": sorted(set(relationship_codes)) if relationship == "source_conflict" else [],
        "phase_scopes": sorted(scope_set),
        "matrix_phase_disposition": row_disposition,
        "matrix_disposition_claim_only": True,
    }


def _unit_status(assessments: Sequence[Mapping[str, Any]]) -> tuple[str, list[str], list[str]]:
    evidence = {str(item.get("evidence_status")) for item in assessments}
    blockers = sorted({code for item in assessments for code in item.get("blocker_codes", ())})
    conflicts = sorted({code for item in assessments for code in item.get("source_conflict_codes", ())})
    if "blocked_structural" in evidence:
        return "blocked_structural", blockers, conflicts
    if conflicts:
        return "source_conflict", blockers, conflicts
    if "unresolved_semantic" in evidence:
        return "unresolved_semantic", blockers, conflicts
    if "structurally_supported_candidate" in evidence:
        return "structurally_supported_candidate", blockers, conflicts
    return "blocked_structural", blockers or ["EVIDENCE_STATUS_MISSING"], conflicts


def _row_status(assessments: Sequence[Mapping[str, Any]]) -> tuple[str, list[str], list[str], list[str]]:
    structural = sorted(
        {
            code
            for item in assessments
            if item.get("evidence_status") == "blocked_structural"
            for code in item.get("blocker_codes", ())
        }
    )
    semantic = sorted(
        {
            code
            for item in assessments
            if item.get("evidence_status") == "unresolved_semantic"
            for code in item.get("blocker_codes", ())
        }
    )
    conflicts = sorted({code for item in assessments for code in item.get("source_conflict_codes", ())})
    if structural:
        return "blocked_structural", structural, semantic, conflicts
    if conflicts:
        return "source_conflict", structural, semantic, conflicts
    if semantic:
        return "unresolved_semantic", structural, semantic, conflicts
    return "structurally_supported_candidate", structural, semantic, conflicts


def _package_membership(
    unit_id: str,
    owned_by_id: Mapping[str, Mapping[str, Any]],
    context_by_id: Mapping[str, Sequence[Mapping[str, Any]]],
    expected_ids: set[str],
) -> dict[str, Any]:
    owner = owned_by_id.get(unit_id)
    contexts = sorted(
        (
            int(package.get("package_ordinal")),
            _nonempty_string(package.get("package_id"), field="package.package_id"),
        )
        for package in context_by_id.get(unit_id, ())
    )
    owned = None
    if owner is not None:
        owned = {
            "package_id": _nonempty_string(owner.get("package_id"), field="package.package_id"),
            "package_ordinal": int(owner["package_ordinal"]),
        }
    package_ids = sorted({package_id for _, package_id in contexts} | ({owned["package_id"]} if owned else set()))
    return {
        "semantic_target": unit_id in expected_ids,
        "owned_package": owned,
        "context_packages": [
            {"package_id": package_id, "package_ordinal": ordinal}
            for ordinal, package_id in contexts
        ],
        "package_ids": package_ids,
        "ownership_status": "owned" if owned is not None else "not_semantic_target",
    }


STRATA: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "explicit_phase_ii_flow",
        ("Ⅱ期临床研究阶段", "Ⅱ期", "筛选", "基线", "随机", "首次给药"),
        "覆盖明确Ⅱ期流程、筛选/基线/随机/首次给药边界；关键词只用于选择包，不作期别判定。",
    ),
    (
        "shared_unknown_leaf",
        ("合并用药/治疗", "合并用药", "合并治疗", "允许合并", "禁止的合并"),
        "覆盖共同章节未知叶节点；未限定期别不被当作跨期共享正向证据。",
    ),
    (
        "table_5",
        ("表5", "表 5"),
        "覆盖表5禁限用药/治疗的完整结构邻域代表包。",
    ),
    (
        "tuberculosis_pregnancy",
        ("结核", "妊娠", "避孕", "生育"),
        "覆盖结核、妊娠和避孕门控，保留混合成员边界。",
    ),
    (
        "validity_retest",
        ("有效期", "复测", "重复检查", "反射性", "重新筛选"),
        "覆盖结果有效期、复测与重新筛选风险。",
    ),
    (
        "opposite_phase_reference",
        ("Ⅲ期", "III", "phase_iii"),
        "覆盖对侧期引用；对侧来源不升级为选定期适用。",
    ),
    (
        "post_dose_contamination",
        ("治疗期", "给药后", "D1", "首次给药", "随机", "合并治疗"),
        "覆盖治疗后污染、首次给药前资格和合并治疗时序风险。",
    ),
)


def _select_representative_packages(
    unit_records: Sequence[Mapping[str, Any]],
    package_lookup: Mapping[str, Mapping[str, Any]],
    *,
    opposite_phase: str = OPPOSITE_PHASE,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected_ids: set[str] = set()
    strata: list[dict[str, Any]] = []
    for stratum_id, keywords, rationale in STRATA:
        candidates: list[Mapping[str, Any]] = []
        for record in unit_records:
            row_titles = " ".join(
                str(item.get("title_zh", "")) for item in record.get("matrix_references", ())
            )
            headings = " ".join(str(item) for item in record.get("heading_path", ()))
            excerpt = str(record.get("excerpt", ""))
            text = " ".join(
                [
                    excerpt,
                    headings,
                    row_titles,
                ]
            )
            scopes = set(record.get("phase_scopes", ()))
            if stratum_id == "shared_unknown_leaf":
                matches = (
                    record.get("status") == "unresolved_semantic"
                    and "unknown" in scopes
                    and any(keyword in row_titles or keyword in headings for keyword in keywords)
                )
            elif stratum_id == "opposite_phase_reference":
                matches = opposite_phase in scopes or any(keyword in text for keyword in keywords)
            else:
                matches = any(keyword in text for keyword in keywords)
            if matches and record.get("package_membership", {}).get("package_ids"):
                candidates.append(record)
        candidate_ids = sorted({package_id for record in candidates for package_id in record["package_membership"]["package_ids"]})
        selected_package_ids: list[str] = []
        if candidate_ids:
            def candidate_key(record: Mapping[str, Any], package_id: str) -> tuple[int, int, int, str]:
                row_titles = " ".join(
                    str(item.get("title_zh", "")) for item in record.get("matrix_references", ())
                )
                headings = " ".join(str(item) for item in record.get("heading_path", ()))
                excerpt = str(record.get("excerpt", ""))
                row_hits = sum(keyword in row_titles for keyword in keywords)
                heading_hits = sum(keyword in headings for keyword in keywords)
                excerpt_hits = sum(keyword in excerpt for keyword in keywords)
                structural_bonus = 100 if stratum_id == "tuberculosis_pregnancy" and record.get("status") == "blocked_structural" else 0
                owner_bonus = 10 if record.get("package_membership", {}).get("owned_package", {}) and record["package_membership"]["owned_package"].get("package_id") == package_id else 0
                score = structural_bonus + owner_bonus + row_hits * 100 + heading_hits * 20 + excerpt_hits
                return (-score, int(record.get("source_order", 0) or 0), int(package_lookup[package_id]["package_ordinal"]), package_id)

            best_record, best_package_id = min(
                ((record, package_id) for record in candidates for package_id in record["package_membership"]["package_ids"]),
                key=lambda pair: candidate_key(pair[0], pair[1]),
            )
            selected_package_ids = [best_package_id]
            selected_ids.update(selected_package_ids)
        strata.append(
            {
                "stratum_id": stratum_id,
                "rationale_zh": rationale,
                "candidate_unit_ids": sorted(str(record["structure_unit_id"]) for record in candidates),
                "candidate_package_ids": candidate_ids,
                "selected_package_ids": selected_package_ids,
                "selection_status": "selected" if selected_package_ids else "no_semantic_package_candidate",
            }
        )

    packages: list[dict[str, Any]] = []
    for package_id in sorted(
        selected_ids,
        key=lambda value: (int(package_lookup[value]["package_ordinal"]), value),
    ):
        package = package_lookup[package_id]
        owned = [
            str(record["structure_unit_id"])
            for record in unit_records
            if (record.get("package_membership", {}).get("owned_package") or {}).get("package_id") == package_id
        ]
        context = [
            str(record["structure_unit_id"])
            for record in unit_records
            if package_id in record.get("package_membership", {}).get("package_ids", ())
            and str(record["structure_unit_id"]) not in owned
        ]
        package_strata = [
            item["stratum_id"]
            for item in strata
            if package_id in item["selected_package_ids"]
        ]
        packages.append(
            {
                "package_id": package_id,
                "package_ordinal": int(package["package_ordinal"]),
                "strata": package_strata,
                "referenced_owned_unit_ids": sorted(owned),
                "referenced_context_unit_ids": sorted(context),
            }
        )
    return strata, packages


def build_unit_phase_evidence_view(
    manifest_payload: Mapping[str, Any],
    matrix_payload: Mapping[str, Any],
    plan_payload: Mapping[str, Any],
    *,
    freeze_metadata_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the source-linked unit and row view without semantic mutation."""

    plan, execution_snapshot = _extract_plan(plan_payload)
    identity = _validate_identity(manifest_payload, matrix_payload, plan, freeze_metadata_payload)
    units_by_id = _validate_manifest(manifest_payload)
    owned_by_id, context_by_id, expected_ids_list = _validate_plan(plan)
    expected_ids = set(expected_ids_list)

    rows = matrix_payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise UnitPhaseEvidenceError("MATRIX_EMPTY", "matrix.rows must be a non-empty array")
    row_by_id: dict[str, Mapping[str, Any]] = {}
    references_by_unit: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    row_assessments: dict[str, list[dict[str, Any]]] = {}
    source_anchor_count = 0
    for row in rows:
        if not isinstance(row, Mapping):
            raise UnitPhaseEvidenceError("MATRIX_ROW_INVALID", "matrix row must be an object")
        row_id = _nonempty_string(row.get("matrix_row_id"), field="row.matrix_row_id")
        if row_id in row_by_id:
            raise UnitPhaseEvidenceError("MATRIX_ROW_DUPLICATE", f"duplicate matrix row: {row_id}")
        disposition = _nonempty_string(row.get("phase_disposition"), field=f"row[{row_id}].phase_disposition")
        anchors = row.get("source_anchors")
        if not isinstance(anchors, list) or not anchors:
            raise UnitPhaseEvidenceError("MATRIX_ANCHORS_EMPTY", f"row has no source anchors: {row_id}")
        row_by_id[row_id] = row
        assessments: list[dict[str, Any]] = []
        for anchor in anchors:
            if not isinstance(anchor, Mapping):
                raise UnitPhaseEvidenceError("MATRIX_ANCHOR_INVALID", f"anchor invalid: {row_id}")
            source_anchor_count += 1
            unit_id = str(anchor.get("structure_unit_id", ""))
            assessment = _anchor_assessment(
                anchor,
                units_by_id.get(unit_id),
                row_id=row_id,
                row_disposition=disposition,
                selected_phase=identity["selected_phase"],
                opposite_phase=identity["opposite_phase"],
            )
            assessments.append(assessment)
            if unit_id in units_by_id:
                references_by_unit[unit_id].append(
                    {
                        "matrix_row_id": row_id,
                        "display_ordinal": row.get("display_ordinal"),
                        "title_zh": row.get("title_zh"),
                        "phase_disposition": disposition,
                        "source_anchor_id": anchor.get("source_anchor_id"),
                        "source_ordinal": anchor.get("source_ordinal"),
                        "verbatim_excerpt": anchor.get("verbatim_excerpt"),
                        "relationship": assessment["relationship"],
                    }
                )
        row_assessments[row_id] = assessments

    unit_records: list[dict[str, Any]] = []
    for unit_id in sorted(references_by_unit, key=lambda value: int(units_by_id[value].get("source_order", 0))):
        unit = units_by_id[unit_id]
        refs = references_by_unit[unit_id]
        status, blockers, conflicts = _unit_status(
            [
                _anchor_assessment(
                    {
                        "source_anchor_id": ref["source_anchor_id"],
                        "structure_unit_id": unit_id,
                        "source_ref": unit["source_ref"],
                        "heading_path_zh": unit["heading_path"],
                        "source_span_ids": unit["source_span_ids"],
                        "verbatim_excerpt": ref["verbatim_excerpt"],
                    },
                    unit,
                    row_id=str(ref["matrix_row_id"]),
                    row_disposition=str(ref["phase_disposition"]),
                    selected_phase=identity["selected_phase"],
                    opposite_phase=identity["opposite_phase"],
                )
                for ref in refs
            ]
        )
        package_membership = _package_membership(unit_id, owned_by_id, context_by_id, expected_ids)
        if status in {"unresolved_semantic", "blocked_structural"} and package_membership["semantic_target"] is False:
            blockers = sorted(set(blockers) | {"PLAN_SEMANTIC_TARGET_MISSING"})
        unit_records.append(
            {
                "structure_unit_id": unit_id,
                "source_ref": unit["source_ref"],
                "source_order": unit.get("source_order"),
                "source_span_ids": list(unit["source_span_ids"]),
                "heading_path": list(unit["heading_path"]),
                "unit_kind": unit.get("unit_kind"),
                "table_context": unit.get("table_context"),
                "excerpt": unit["excerpt"],
                "excerpt_sha256": hashlib.sha256(str(unit["excerpt"]).encode("utf-8")).hexdigest(),
                "phase_scopes": sorted(str(scope) for scope in unit["phase_scopes"]),
                "structural_status": _anchor_assessment(
                    {
                        "source_anchor_id": refs[0]["source_anchor_id"],
                        "structure_unit_id": unit_id,
                        "source_ref": unit["source_ref"],
                        "heading_path_zh": unit["heading_path"],
                        "source_span_ids": unit["source_span_ids"],
                        "verbatim_excerpt": refs[0]["verbatim_excerpt"],
                    },
                    unit,
                    row_id=str(refs[0]["matrix_row_id"]),
                    row_disposition=str(refs[0]["phase_disposition"]),
                    selected_phase=identity["selected_phase"],
                    opposite_phase=identity["opposite_phase"],
                )["structural_status"],
                "semantic_status": {
                    "structurally_supported_candidate": "not_required",
                    "unresolved_semantic": "unresolved_semantic",
                    "blocked_structural": "blocked_structural",
                    "source_conflict": "blocked_by_source_conflict",
                }[status],
                "status": status,
                "blocker_codes": blockers,
                "source_conflict_codes": conflicts,
                "matrix_references": sorted(
                    refs,
                    key=lambda ref: (
                        int(ref["display_ordinal"] or 0),
                        str(ref["matrix_row_id"]),
                        int(ref["source_ordinal"] or 0),
                        str(ref["source_anchor_id"]),
                    ),
                ),
                "matrix_phase_dispositions": sorted({str(ref["phase_disposition"]) for ref in refs}),
                "matrix_disposition_claim_only": True,
                "shared_evidence": {
                    "candidate": "shared" in set(unit["phase_scopes"]),
                    "positive_obligation_family_evidence_verified": False,
                    "requires_same_obligation_family_positive_evidence": True,
                },
                "package_membership": package_membership,
            }
        )

    row_records: list[dict[str, Any]] = []
    for row in rows:
        row_id = str(row["matrix_row_id"])
        assessments = row_assessments[row_id]
        status, structural, semantic, conflicts = _row_status(assessments)
        row_records.append(
            {
                "matrix_row_id": row_id,
                "display_ordinal": row.get("display_ordinal"),
                "title_zh": row.get("title_zh"),
                "phase_disposition": row.get("phase_disposition"),
                "matrix_disposition_claim_only": True,
                "source_anchor_count": len(assessments),
                "unique_structure_unit_count": len({str(item["structure_unit_id"]) for item in assessments}),
                "phase_scopes": sorted({scope for item in assessments for scope in item.get("phase_scopes", ())}),
                "closure_status": status,
                "blocked": status != "structurally_supported_candidate",
                "structural_blocker_codes": structural,
                "semantic_unresolved_codes": semantic,
                "source_conflict_codes": conflicts,
                "anchor_assessments": assessments,
            }
        )

    package_lookup = {
        _nonempty_string(package.get("package_id"), field="package.package_id"): package
        for package in plan["packages"]
    }
    strata, representative_packages = _select_representative_packages(
        unit_records,
        package_lookup,
        opposite_phase=identity["opposite_phase"],
    )
    status_counts = Counter(record["status"] for record in unit_records)
    row_status_counts = Counter(record["closure_status"] for record in row_records)
    phase_scope_counts = Counter(tuple(record["phase_scopes"]) for record in unit_records)
    referenced_target_count = sum(
        1 for record in unit_records if record["package_membership"]["semantic_target"]
    )
    report = {
        "schema_version": "phase5/d001-ii-unit-phase-evidence/v1",
        "identities": identity,
        "execution_snapshot": {
            "run_id": execution_snapshot.get("run_id"),
            "status": execution_snapshot.get("status"),
            "input_scope_sha256": execution_snapshot.get("input_scope_sha256"),
            "prompt_template_sha256": execution_snapshot.get("prompt_template_sha256"),
        },
        "claims_complete": False,
        "semantic_run_executed": False,
        "semantic_package_execution_count": 0,
        "full_semantic_run_requested": False,
        "semantic_run_scope": "matrix_referenced_units_only_for_future_review; no_batch_executed",
        "counts": {
            "matrix_row_count": len(row_records),
            "source_anchor_count": source_anchor_count,
            "unique_referenced_unit_count": len(unit_records),
            "referenced_semantic_target_count": referenced_target_count,
            "referenced_nonsemantic_target_count": len(unit_records) - referenced_target_count,
            "unit_status_counts": dict(sorted(status_counts.items())),
            "row_closure_status_counts": dict(sorted(row_status_counts.items())),
            "phase_scope_counts": {
                "+".join(scope) if scope else "empty": count
                for scope, count in sorted(phase_scope_counts.items())
            },
        },
        "plan": {
            "plan_id": identity["plan"]["plan_id"],
            "plan_schema_version": identity["plan"]["schema_version"],
            "package_count": len(plan["packages"]),
            "semantic_target_count": len(expected_ids_list),
            "semantic_target_ownership_closed": True,
            "plan_payload_sha256": canonical_sha256(plan),
        },
        "representative_package_selection": {
            "selection_policy": "declared_heterogeneous_strata_first_match_by_source_order_then_package_ordinal",
            "random_sampling": False,
            "strata": strata,
            "packages": representative_packages,
        },
        "row_blocking_contract": {
            "all_source_anchors_are_conjunctive": True,
            "blocks_on": [
                "unresolved_semantic",
                "blocked_structural",
                "opposite_phase",
                "source_conflict",
            ],
            "matrix_phase_disposition_is_authoritative": False,
        },
        "source_closure": {
            "all_referenced_units_resolved": len(unit_records) == len(
                {str(anchor.get("structure_unit_id")) for row in rows for anchor in row["source_anchors"]}
            ),
            "manifest_unit_count": len(units_by_id),
            "manifest_claims_full_coverage": bool(manifest_payload.get("claims_full_coverage")),
            "matrix_claims_complete": bool(matrix_payload.get("claims_complete")),
        },
        "unit_count": len(unit_records),
        "row_count": len(row_records),
        "source_anchor_count": source_anchor_count,
        "unit_status_counts": dict(sorted(status_counts.items())),
        "row_closure_status_counts": dict(sorted(row_status_counts.items())),
        "unit_records": unit_records,
        "row_records": row_records,
    }
    return report


def build_view_and_report(
    manifest_payload: Mapping[str, Any],
    matrix_payload: Mapping[str, Any],
    plan_payload: Mapping[str, Any],
    *,
    freeze_metadata_payload: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    report = build_unit_phase_evidence_view(
        manifest_payload,
        matrix_payload,
        plan_payload,
        freeze_metadata_payload=freeze_metadata_payload,
    )
    view = {
        "schema_version": report["schema_version"],
        "identities": report["identities"],
        "claims_complete": False,
        "semantic_run_executed": False,
        "semantic_package_execution_count": 0,
        "full_semantic_run_requested": False,
        "semantic_run_scope": report["semantic_run_scope"],
        "unit_records": report["unit_records"],
        "row_records": report["row_records"],
        "representative_package_selection": report["representative_package_selection"],
    }
    return view, report


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = handle.name
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--freeze-metadata", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    freeze = (
        json.loads(args.freeze_metadata.read_text(encoding="utf-8"))
        if args.freeze_metadata is not None
        else None
    )
    view, report = build_view_and_report(
        manifest,
        matrix,
        plan,
        freeze_metadata_payload=freeze,
    )
    _write_json(args.output, view)
    _write_json(args.report, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "report": str(args.report),
                "claims_complete": False,
                "row_count": report["row_count"],
                "source_anchor_count": report["source_anchor_count"],
                "unit_count": report["unit_count"],
                "representative_package_count": len(report["representative_package_selection"]["packages"]),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
