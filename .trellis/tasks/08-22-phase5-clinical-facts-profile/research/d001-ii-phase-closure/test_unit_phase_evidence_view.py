from __future__ import annotations

import json
from pathlib import Path

import pytest

from build_d001_unit_phase_evidence_view import (
    UnitPhaseEvidenceError,
    build_view_and_report,
)


ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "coverage_manifest.json"
MATRIX_PATH = ROOT / "d001-ii-control-matrix-closed.json"
PLAN_PATH = ROOT / "slice58i-v2-plan" / "execution" / "d001-ii-phase-closure-20260826-slice58i-v2.json"
FREEZE_METADATA_PATH = ROOT / "freeze_metadata.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _real_view() -> tuple[dict, dict]:
    return build_view_and_report(
        _load(MANIFEST_PATH),
        _load(MATRIX_PATH),
        _load(PLAN_PATH),
        freeze_metadata_payload=_load(FREEZE_METADATA_PATH),
    )


def test_real_d001_view_binds_current_matrix_and_v2_plan() -> None:
    view, report = _real_view()

    assert report["claims_complete"] is False
    assert report["semantic_run_executed"] is False
    assert report["semantic_package_execution_count"] == 0
    assert report["full_semantic_run_requested"] is False
    assert report["identities"]["manifest"]["manifest_id"] == "d001-ii-phase-closure-20260825-slice58e-manifest"
    assert report["identities"]["matrix"]["matrix_id"] == "protocol-control-matrix-d001-ii-362443131f0d384c"
    assert report["identities"]["plan"]["plan_id"] == "papl-45fde1ba5b326315737bda77"
    assert report["identities"]["freeze_metadata"]["source_sha256"] == (
        "362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98"
    )
    assert report["counts"]["matrix_row_count"] == 82
    assert report["counts"]["source_anchor_count"] == 155
    assert report["counts"]["unique_referenced_unit_count"] == 152
    assert report["counts"]["referenced_semantic_target_count"] == 117
    assert report["plan"]["package_count"] == 137
    assert report["plan"]["semantic_target_count"] == 1298
    assert report["unit_status_counts"] == {
        "blocked_structural": 1,
        "structurally_supported_candidate": 29,
        "source_conflict": 6,
        "unresolved_semantic": 116,
    }
    assert report["row_closure_status_counts"] == {
        "blocked_structural": 1,
        "structurally_supported_candidate": 4,
        "source_conflict": 3,
        "unresolved_semantic": 74,
    }
    assert len({record["structure_unit_id"] for record in report["unit_records"]}) == 152
    assert {item["stratum_id"] for item in report["representative_package_selection"]["strata"]} == {
        "explicit_phase_ii_flow",
        "shared_unknown_leaf",
        "table_5",
        "tuberculosis_pregnancy",
        "validity_retest",
        "opposite_phase_reference",
        "post_dose_contamination",
    }
    assert all(
        item["selection_status"] == "selected"
        for item in report["representative_package_selection"]["strata"]
    )
    assert len(report["representative_package_selection"]["packages"]) == 6
    assert view["claims_complete"] is False
    assert view["semantic_package_execution_count"] == 0


def test_real_view_is_byte_deterministic() -> None:
    first_view, first_report = _real_view()
    second_view, second_report = _real_view()

    assert json.dumps(first_view, ensure_ascii=False, sort_keys=True, separators=(",", ":")) == json.dumps(
        second_view, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    assert json.dumps(first_report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) == json.dumps(
        second_report, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _anchor(unit: dict, anchor_id: str) -> dict:
    return {
        "source_anchor_id": anchor_id,
        "source_ref": unit["source_ref"],
        "source_span_ids": list(unit["source_span_ids"]),
        "heading_path_zh": list(unit["heading_path"]),
        "structure_unit_id": unit["structure_unit_id"],
        "verbatim_excerpt": unit["excerpt"],
        "source_ordinal": 0,
    }


def _synthetic_payloads() -> tuple[dict, dict, dict]:
    identity = {
        "coverage_manifest_id": "fixture-manifest",
        "snapshot_id": "fixture-snapshot",
        "protocol_version_id": "fixture-protocol:v1:phase-ii",
        "protocol_document_sha256": "a" * 64,
    }
    units = []
    for unit_id, scope, excerpt in (
        ("u-selected", ["phase_ii"], "selected source"),
        ("u-unknown", ["unknown"], "unknown source"),
        ("u-mixed", ["mixed"], "mixed source"),
        ("u-opposite", ["phase_iii"], "opposite source"),
        ("u-shared", ["shared"], "shared source"),
    ):
        units.append(
            {
                "structure_unit_id": unit_id,
                "source_ref": f"body.{unit_id}",
                "source_span_ids": [f"body.{unit_id}"],
                "heading_path": ["Synthetic", unit_id],
                "excerpt": excerpt,
                "phase_scopes": scope,
                "source_order": len(units),
                "unit_kind": "paragraph",
                "table_context": None,
            }
        )
    by_id = {unit["structure_unit_id"]: unit for unit in units}

    def row(row_id: str, title: str, disposition: str, unit_id: str) -> dict:
        unit = by_id[unit_id]
        return {
            "matrix_row_id": row_id,
            "display_ordinal": int(row_id.rsplit("-", 1)[-1]),
            "title_zh": title,
            "phase_disposition": disposition,
            "source_anchors": [_anchor(unit, f"a-{row_id}")],
        }

    manifest = {
        "schema_version": "fixture/v1",
        "manifest_id": identity["coverage_manifest_id"],
        "snapshot_id": identity["snapshot_id"],
        "protocol_version_id": identity["protocol_version_id"],
        "protocol_document_sha256": identity["protocol_document_sha256"],
        "study_phase": "phase_ii",
        "claims_full_coverage": False,
        "units": units,
        "dispositions": [],
    }
    matrix = {
        "schema_version": "fixture/matrix/v1",
        "matrix_id": "fixture-matrix",
        **identity,
        "selected_phase": "phase_ii",
        "claims_complete": False,
        "rows": [
            row("row-1", "selected", "selected_phase_applicable", "u-selected"),
            row("row-2", "unknown", "cross_phase_shared", "u-unknown"),
            row("row-3", "mixed", "cross_phase_shared", "u-mixed"),
            row("row-4", "opposite", "selected_phase_applicable", "u-opposite"),
            row("row-5", "selected but shared claim", "cross_phase_shared", "u-selected"),
            row("row-6", "shared candidate", "cross_phase_shared", "u-shared"),
        ],
    }
    plan = {
        "schema_version": "phase5/phase-applicability-plan/v2",
        "plan_id": "fixture-plan",
        "coverage_manifest_id": identity["coverage_manifest_id"],
        "protocol_version_id": identity["protocol_version_id"],
        "study_phase": "phase_ii",
        "expected_structure_unit_ids": ["u-unknown", "u-mixed", "u-shared"],
        "packages": [
            {
                "package_id": "fixture-package",
                "package_ordinal": 1,
                "owned_units": [by_id[unit_id] for unit_id in ("u-unknown", "u-mixed", "u-shared")],
                "context_units": [],
            }
        ],
    }
    return manifest, matrix, plan


def test_synthetic_rows_keep_structural_semantic_and_source_conflicts_separate() -> None:
    view, report = build_view_and_report(*_synthetic_payloads())
    by_row = {row["matrix_row_id"]: row for row in report["row_records"]}
    by_unit = {unit["structure_unit_id"]: unit for unit in report["unit_records"]}

    assert by_unit["u-mixed"]["status"] == "blocked_structural"
    assert "STRUCTURE_PHASE_BOUNDARY_MIXED" in by_unit["u-mixed"]["blocker_codes"]
    assert by_row["row-3"]["closure_status"] == "blocked_structural"
    assert by_row["row-4"]["closure_status"] == "blocked_structural"
    assert by_unit["u-opposite"]["status"] == "blocked_structural"
    assert "OPPOSITE_PHASE_SOURCE" in by_unit["u-opposite"]["blocker_codes"]

    assert by_unit["u-unknown"]["status"] == "unresolved_semantic"
    assert by_row["row-2"]["closure_status"] == "unresolved_semantic"
    assert by_unit["u-shared"]["status"] == "unresolved_semantic"
    assert by_unit["u-shared"]["shared_evidence"]["positive_obligation_family_evidence_verified"] is False

    assert by_unit["u-selected"]["status"] == "source_conflict"
    assert "MATRIX_SHARED_DISPOSITION_CONFLICT" in by_unit["u-selected"]["source_conflict_codes"]
    assert by_row["row-5"]["closure_status"] == "source_conflict"
    assert by_row["row-1"]["closure_status"] == "structurally_supported_candidate"
    assert report["claims_complete"] is False
    assert view["semantic_run_executed"] is False


def test_complete_claims_input_is_rejected() -> None:
    manifest, matrix, plan = _synthetic_payloads()
    matrix["claims_complete"] = True
    with pytest.raises(UnitPhaseEvidenceError) as caught:
        build_view_and_report(manifest, matrix, plan)
    assert caught.value.code == "CLAIMS_COMPLETE_UNSAFE"
