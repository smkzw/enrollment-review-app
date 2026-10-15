#!/usr/bin/env python3
"""Freeze the D001 II full coverage manifest and semantic phase plan.

This is an acceptance artifact, not application code.  It reads the named
original DOCX and writes only under this directory.  The semantic Agent run is
performed separately by the generic execution CLI so the frozen input can be
inspected before any model call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import sys

SCRIPT_ROOT = Path(__file__).resolve().parent
REPO = SCRIPT_ROOT.parents[4]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.domain.contracts.enums import StudyPhase
from app.protocols.docx_structure import extract_docx_structure
from app.protocols.full_protocol_coverage import build_full_protocol_coverage_manifest
from app.protocols.ingestion import register_source_artifact
from app.protocols.phase_applicability_planning import plan_phase_applicability_batches
from app.protocols.phase_detection import build_phase_applicability_graph, project_single_phase
from app.services.phase_applicability_execution import (
    PhaseApplicabilityExecutionService,
    PhaseApplicabilityExecutionStore,
)


SOURCE = Path(
    "/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/"
    "CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx"
)
PROTOCOL_VERSION_ID = "D001-02-002:v1.0:phase-ii"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _source_state() -> dict[str, object]:
    stat = SOURCE.stat()
    return {
        "path": str(SOURCE),
        "sha256": _sha256(SOURCE),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _canonical_sha(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
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
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=SCRIPT_ROOT)
    parser.add_argument("--run-tag", default="20260825-slice58e")
    args = parser.parse_args()
    root = args.output_dir.resolve()
    if root != SCRIPT_ROOT:
        root.mkdir(parents=True, exist_ok=False)
    snapshot_id = f"d001-ii-phase-closure-{args.run_tag}-snapshot"
    manifest_id = f"d001-ii-phase-closure-{args.run_tag}-manifest"
    run_id = f"d001-ii-phase-closure-{args.run_tag}"

    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    before = _source_state()
    if before["sha256"] != "362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98":
        raise RuntimeError(f"D001 原始方案哈希不匹配：{before}")

    source_artifact = register_source_artifact(
        SOURCE,
        source_artifact_id="d001-ii-phase-closure-source",
        storage_root=root / "source-input",
    )
    extraction = extract_docx_structure(
        SOURCE,
        snapshot_id=snapshot_id,
        source_artifact=source_artifact,
        output_dir=root / "structure",
    )
    if extraction.snapshot.status.value != "completed":
        raise RuntimeError(f"结构提取未完成：{extraction.snapshot.status.value}")

    phase_detection = build_phase_applicability_graph(
        extraction.blocks,
        snapshot_id=snapshot_id,
    )
    projection = project_single_phase(phase_detection.graph, StudyPhase.PHASE_II)
    manifest = build_full_protocol_coverage_manifest(
        extraction.blocks,
        projection,
        phase_detection.graph,
        protocol_version_id=PROTOCOL_VERSION_ID,
        protocol_document_sha256=str(before["sha256"]),
        snapshot_id=snapshot_id,
        manifest_id=manifest_id,
        priority_keywords=(
            "入选",
            "排除",
            "筛选",
            "基线",
            "首次给药",
            "随机",
            "结核",
            "妊娠",
            "合并用药",
            "洗脱",
            "复测",
            "有效期",
        ),
    )
    plan = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=12,
        context_radius=1,
    )

    ambiguous = len(plan.expected_structure_unit_ids)
    counts = {
        "structure_block_count": len(extraction.blocks),
        "phase_graph_block_count": len(phase_detection.graph.blocks),
        "coverage_unit_count": len(manifest.units),
        "ambiguous_unit_count": ambiguous,
        "frozen_batch_count": len(plan.packages),
        "selected_phase": manifest.study_phase.value,
        "claims_full_coverage": manifest.claims_full_coverage,
    }
    expected = {
        "structure_block_count": 3581,
        "phase_graph_block_count": 3405,
        "coverage_unit_count": 1848,
        "ambiguous_unit_count": 1240,
        "frozen_batch_count": 131,
    }
    for key, value in expected.items():
        if counts[key] != value:
            raise RuntimeError(f"D001 计数与冻结预期不一致：{key}={counts[key]}，预期={value}")

    manifest_payload = manifest.model_dump(mode="json")
    plan_payload = plan.model_dump(mode="json")
    manifest_sha = _write_json(root / "coverage_manifest.json", manifest_payload)
    plan_sha = _write_json(root / "frozen_phase_plan.json", plan_payload)
    source_after = _source_state()
    if source_after != before:
        raise RuntimeError(f"D001 原始方案在构建期间发生变化：before={before} after={source_after}")

    metadata = {
        "schema_version": "phase5/d001-ii-phase-closure-build/v1",
        "run_id": run_id,
        "source": source_after,
        "source_artifact": source_artifact.model_dump(mode="json"),
        "snapshot_id": snapshot_id,
        "manifest_id": manifest.manifest_id,
        "protocol_version_id": manifest.protocol_version_id,
        "extraction_snapshot": extraction.snapshot.model_dump(mode="json"),
        "phase_graph_id": phase_detection.graph.graph_id,
        "projection_id": projection.projection_id,
        "counts": counts,
        "expected_counts": expected,
        "manifest_payload_sha256": _canonical_sha(manifest_payload),
        "manifest_file_sha256": manifest_sha,
        "plan_payload_sha256": _canonical_sha(plan_payload),
        "plan_file_sha256": plan_sha,
        "max_owned_units_per_batch": plan.max_owned_units_per_batch,
        "context_radius": plan.context_radius,
        "source_unchanged": True,
    }
    _write_json(root / "freeze_metadata.json", metadata)

    # Persist the complete input snapshot before the first real model call.
    service = PhaseApplicabilityExecutionService(
        PhaseApplicabilityExecutionStore(root / "execution")
    )
    state = service.prepare(
        run_id=run_id,
        coverage_manifest=manifest,
        plan=plan,
    )
    if state.status not in {"planned", "running", "needs_review", "completed"}:
        raise RuntimeError(f"execution 状态异常：{state.status}")
    _write_json(
        root / "prepare_summary.json",
        {
            "run_id": state.run_id,
            "status": state.status,
            "input_scope_sha256": state.input_scope_sha256,
            "prompt_template_sha256": state.prompt_template_sha256,
            "batch_count": len(state.batches),
            "coverage_unit_count": len(state.coverage_manifest.units),
            "expected_agent_unit_count": len(state.plan.expected_structure_unit_ids),
            "checkpoint": str((root / "execution" / f"{run_id}.json").relative_to(root)),
        },
    )
    print(json.dumps({**counts, "manifest_sha256": manifest_sha, "plan_sha256": plan_sha}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
