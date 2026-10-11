#!/usr/bin/env python3
"""Build a non-mutating aggregate view over the frozen D001 II run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[4]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.domain.contracts.protocol_controls import ProtocolSectionCoverageManifest
from app.protocols.full_protocol_coverage import build_resolved_full_protocol_coverage_view
from app.protocols.phase_applicability_planning import PhaseApplicabilityFrozenPlan
from app.services.phase_applicability_execution import PhaseApplicabilityExecutionStore


RUN_ID = "d001-ii-phase-closure-20260825"
SOURCE = Path(
    "/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/"
    "CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    manifest_payload = json.loads((ROOT / "coverage_manifest.json").read_text(encoding="utf-8"))
    plan_payload = json.loads((ROOT / "frozen_phase_plan.json").read_text(encoding="utf-8"))
    manifest = ProtocolSectionCoverageManifest.model_validate(manifest_payload)
    plan = PhaseApplicabilityFrozenPlan.model_validate(plan_payload)
    state = PhaseApplicabilityExecutionStore(ROOT / "execution").load(RUN_ID)
    view = build_resolved_full_protocol_coverage_view(
        manifest,
        plan,
        state.final_outputs,
    )

    resolution_by_unit = view.resolution_by_unit
    pending_ids = set(view.pending_structure_unit_ids)
    units = []
    disposition_counts: dict[str, int] = {}
    for unit in manifest.units:
        disposition = resolution_by_unit.get(unit.structure_unit_id)
        status = disposition.value if disposition is not None else "unresolved"
        disposition_counts[status] = disposition_counts.get(status, 0) + 1
        units.append(
            {
                "structure_unit_id": unit.structure_unit_id,
                "source_ref": unit.source_ref,
                "source_order": unit.source_order,
                "source_span_ids": list(unit.source_span_ids),
                "source_excerpt_sha256": hashlib.sha256(unit.excerpt.encode("utf-8")).hexdigest(),
                "phase_scopes": [scope.value for scope in unit.phase_scopes],
                "disposition": status,
                "semantic_pending": unit.structure_unit_id in pending_ids,
            }
        )

    source_state = {
        "path": str(SOURCE),
        "sha256": _sha256(SOURCE),
        "size_bytes": SOURCE.stat().st_size,
        "mtime_ns": SOURCE.stat().st_mtime_ns,
    }
    if source_state["sha256"] != manifest.protocol_document_sha256:
        raise RuntimeError(f"聚合视图发现源哈希漂移：{source_state}")

    issues = [
        {
            "code": issue.code,
            "message": issue.message,
            "structure_unit_id": issue.structure_unit_id,
            "package_id": issue.package_id,
        }
        for issue in view.issues
    ]
    payload = {
        "schema_version": "phase5/d001-ii-phase-closure-aggregate/v1",
        "run_id": RUN_ID,
        "source": source_state,
        "coverage_manifest_id": manifest.manifest_id,
        "protocol_version_id": manifest.protocol_version_id,
        "protocol_document_sha256": manifest.protocol_document_sha256,
        "snapshot_id": manifest.snapshot_id,
        "study_phase": manifest.study_phase.value,
        "plan_id": plan.plan_id,
        "plan_batch_count": len(plan.packages),
        "execution_status": state.status,
        "accepted": view.accepted,
        "claims_full_coverage": view.claims_full_coverage,
        "coverage_unit_count": len(manifest.units),
        "semantic_target_count": len(plan.expected_structure_unit_ids),
        "resolution_set_count": len(state.final_outputs),
        "pending_structure_unit_count": len(view.pending_structure_unit_ids),
        "pending_structure_unit_ids": list(view.pending_structure_unit_ids),
        "phase_excluded_structure_unit_ids": list(view.phase_excluded_structure_unit_ids),
        "disposition_counts": disposition_counts,
        "issue_count": len(issues),
        "issues": issues,
        "units": units,
        "manifest_payload_sha256": _canonical_sha(manifest_payload),
        "plan_payload_sha256": _canonical_sha(plan_payload),
        "source_unchanged": True,
        "non_mutating_source_manifest": True,
    }
    output = ROOT / "aggregate_view.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "execution_status": state.status,
        "accepted": view.accepted,
        "claims_full_coverage": view.claims_full_coverage,
        "coverage_unit_count": len(manifest.units),
        "semantic_target_count": len(plan.expected_structure_unit_ids),
        "pending_structure_unit_count": len(view.pending_structure_unit_ids),
        "resolution_set_count": len(state.final_outputs),
        "issue_count": len(issues),
        "disposition_counts": disposition_counts,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
