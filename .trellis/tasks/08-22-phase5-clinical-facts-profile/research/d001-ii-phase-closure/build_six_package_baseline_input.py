#!/usr/bin/env python3
"""Build the six-package, source-identity-preserving baseline input.

This is a research-artifact generator.  It reads the already prepared v2
D001 II snapshot and the accepted representative-package selection, validates
the package and source identities, and writes only six provider inputs.  It
does not call a model, change the frozen plan, or read the original DOCX.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[4]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.agents.phase_applicability import (  # noqa: E402
    DEFAULT_PHASE_APPLICABILITY_AGENT_PROMPT_TEMPLATE,
    PHASE_APPLICABILITY_AGENT_CURRENT_WIRE_VERSION,
    PHASE_APPLICABILITY_AGENT_INPUT_VERSION,
    PHASE_APPLICABILITY_AGENT_PROMPT_VERSION,
    PhaseApplicabilityAgentInput,
    build_phase_applicability_agent_input,
    build_phase_applicability_agent_prompt,
    phase_applicability_agent_prompt_template_sha256,
)
from app.domain.contracts.protocol_controls import (  # noqa: E402
    ProtocolSectionCoverageManifest,
)
from app.protocols.phase_applicability_planning import (  # noqa: E402
    PHASE_APPLICABILITY_DEFAULT_BATCH_PACKING_POLICY,
    PhaseApplicabilityFrozenPlan,
)
from app.services.phase_applicability_execution import (  # noqa: E402
    PHASE_APPLICABILITY_EXECUTION_VERSION,
)


SCHEMA_VERSION = "phase5/d001-ii-six-package-semantic-baseline-input/v1"
SELECTED_PACKAGE_ORDINALS = (59, 63, 69, 70, 73, 79)
DEFAULT_OUTPUT_DIR = (
    REPO / "artifacts" / "phase5-slice58l-d001-six-package-semantic-baseline-20260826"
)

DATA_ROOT = ROOT
MANIFEST_PATH = DATA_ROOT / "coverage_manifest.json"
STATE_PATH = (
    DATA_ROOT
    / "slice58i-v2-plan/execution/d001-ii-phase-closure-20260826-slice58i-v2.json"
)
VIEW_PATH = DATA_ROOT / "d001-ii-unit-phase-evidence-view.json"
MATRIX_PATH = DATA_ROOT / "d001-ii-control-matrix-closed.json"
FREEZE_METADATA_PATH = DATA_ROOT / "freeze_metadata.json"


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON 顶层必须为 object：{path}")
    return payload


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO.resolve()).as_posix()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
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


def _write_json(path: Path, payload: object) -> str:
    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _write_bytes(path, encoded)
    return hashlib.sha256(encoded).hexdigest()


def _identity_from_manifest(manifest: ProtocolSectionCoverageManifest) -> dict[str, Any]:
    return {
        "manifest_id": manifest.manifest_id,
        "protocol_version_id": manifest.protocol_version_id,
        "protocol_document_sha256": manifest.protocol_document_sha256,
        "snapshot_id": manifest.snapshot_id,
        "selected_phase": manifest.study_phase.value,
        "coverage_unit_count": len(manifest.units),
        "claims_full_coverage": bool(manifest.claims_full_coverage),
    }


def _build_payload(
    output_dir: Path,
    *,
    state_path: Path = STATE_PATH,
) -> tuple[dict[str, Any], list[tuple[Path, dict[str, Any]]]]:
    state_payload = _load_json(state_path)
    manifest_payload = _load_json(MANIFEST_PATH)
    view_payload = _load_json(VIEW_PATH)
    matrix_payload = _load_json(MATRIX_PATH)
    freeze_payload = _load_json(FREEZE_METADATA_PATH)

    manifest = ProtocolSectionCoverageManifest.model_validate(manifest_payload)
    state_manifest = ProtocolSectionCoverageManifest.model_validate(
        state_payload.get("coverage_manifest")
    )
    _require(
        manifest.model_dump(mode="json") == state_manifest.model_dump(mode="json"),
        "独立 coverage_manifest 与 v2 execution snapshot 的清单内容不一致",
    )
    plan = PhaseApplicabilityFrozenPlan.model_validate(state_payload.get("plan"))
    _require(
        plan.schema_version == "phase5/phase-applicability-plan/v2",
        f"当前计划不是 v2：{plan.schema_version}",
    )
    _require(
        plan.batch_packing_policy == PHASE_APPLICABILITY_DEFAULT_BATCH_PACKING_POLICY,
        "当前计划未使用已冻结的相邻小章节打包策略",
    )
    _require(state_payload.get("status") == "planned", "v2 执行快照不是初始 planned 状态")
    _require(state_payload.get("transport_identity") == {}, "v2 执行快照已有 transport 身份")
    _require(
        all(record.get("status") == "pending" for record in state_payload.get("batches", [])),
        "v2 执行快照已有非 pending 批次，不能建立未污染的基线输入",
    )

    manifest_identity = _identity_from_manifest(manifest)
    _require(manifest_identity["claims_full_coverage"] is False, "清单不得声明全文覆盖完成")
    _require(len(plan.packages) == 137, "当前 v2 计划包数不是 137")
    _require(len(plan.expected_structure_unit_ids) == 1298, "当前 v2 待处置单元数不是 1298")
    _require(len(state_payload.get("batches", [])) == len(plan.packages), "state 批次未覆盖完整 v2 计划")
    _require(bool(str(state_payload.get("run_id", "")).strip()), "v2 execution snapshot 缺少 run_id")

    view_identities = view_payload.get("identities")
    _require(isinstance(view_identities, Mapping), "证据视图缺少 identities")
    view_manifest = view_identities.get("manifest", {})
    view_plan = view_identities.get("plan", {})
    view_matrix = view_identities.get("matrix", {})
    _require(view_manifest.get("manifest_id") == manifest.manifest_id, "证据视图 manifest_id 不一致")
    _require(view_manifest.get("snapshot_id") == manifest.snapshot_id, "证据视图 snapshot_id 不一致")
    _require(view_manifest.get("protocol_version_id") == manifest.protocol_version_id, "证据视图 protocol_version_id 不一致")
    _require(view_manifest.get("protocol_document_sha256") == manifest.protocol_document_sha256, "证据视图源方案哈希不一致")
    _require(view_plan.get("plan_id") == plan.plan_id, "证据视图 plan_id 不一致")
    _require(view_plan.get("coverage_manifest_id") == manifest.manifest_id, "证据视图 plan manifest_id 不一致")
    _require(view_plan.get("protocol_version_id") == plan.protocol_version_id, "证据视图 plan protocol_version_id 不一致")
    _require(view_payload.get("claims_complete") is False, "证据视图不得声明 claims_complete")
    _require(view_payload.get("semantic_run_executed") is False, "证据视图不得声明已执行语义包")
    _require(view_payload.get("full_semantic_run_requested") is False, "证据视图不得请求全量语义包")

    _require(matrix_payload.get("claims_complete") is False, "闭包矩阵不得声明 claims_complete")
    _require(matrix_payload.get("protocol_version_id") == manifest.protocol_version_id, "矩阵 protocol_version_id 不一致")
    _require(matrix_payload.get("protocol_document_sha256") == manifest.protocol_document_sha256, "矩阵源方案哈希不一致")
    _require(matrix_payload.get("snapshot_id") == manifest.snapshot_id, "矩阵 snapshot_id 不一致")
    matrix_rows = matrix_payload.get("rows")
    _require(isinstance(matrix_rows, list) and len(matrix_rows) == 82, "闭包矩阵行数不是 82")
    matrix_anchor_count = sum(len(row.get("source_anchors", [])) for row in matrix_rows)
    _require(matrix_anchor_count == 155, "闭包矩阵 source anchor 数不是 155")

    freeze_source = freeze_payload.get("source", {})
    _require(freeze_payload.get("manifest_id") == manifest.manifest_id, "freeze metadata manifest_id 不一致")
    _require(freeze_payload.get("snapshot_id") == manifest.snapshot_id, "freeze metadata snapshot_id 不一致")
    _require(freeze_payload.get("protocol_version_id") == manifest.protocol_version_id, "freeze metadata protocol_version_id 不一致")
    _require(freeze_source.get("sha256") == manifest.protocol_document_sha256, "freeze metadata 源方案哈希不一致")

    selection = view_payload.get("representative_package_selection")
    _require(isinstance(selection, Mapping), "证据视图缺少 representative_package_selection")
    _require(selection.get("random_sampling") is False, "代表包选择不得使用随机抽样")
    selection_policy = selection.get("selection_policy")
    _require(
        selection_policy == "declared_heterogeneous_strata_first_match_by_source_order_then_package_ordinal",
        "代表包选择策略不是已声明的异质分层策略",
    )
    selected_view_packages = selection.get("packages")
    _require(isinstance(selected_view_packages, list), "代表包 selection.packages 不是数组")
    selected_view_by_id = {item.get("package_id"): item for item in selected_view_packages}
    _require(len(selected_view_by_id) == len(selected_view_packages), "代表包 selection 含重复 package_id")
    _require(
        sorted(item.get("package_ordinal") for item in selected_view_packages) == list(SELECTED_PACKAGE_ORDINALS),
        "代表包序号不是冻结的 59/63/69/70/73/79",
    )
    _require(len(selected_view_packages) == len(SELECTED_PACKAGE_ORDINALS), "代表包选择不是六个")

    selected_strata = []
    for stratum in selection.get("strata", []):
        chosen = stratum.get("selected_package_ids", [])
        if chosen:
            _require(len(chosen) == 1, f"分层 {stratum.get('stratum_id')} 不是单包选择")
            _require(chosen[0] in selected_view_by_id, f"分层选择了未进入六包集合的包：{chosen[0]}")
            selected_strata.append(
                {
                    "stratum_id": stratum.get("stratum_id"),
                    "rationale_zh": stratum.get("rationale_zh"),
                    "selected_package_ids": list(chosen),
                }
            )
    _require(len(selected_strata) == 7, "异质代表包分层数不是 7")

    plan_by_id = {package.package_id: package for package in plan.packages}
    selected_packages = []
    for ordinal in SELECTED_PACKAGE_ORDINALS:
        matches = [package for package in plan.packages if package.package_ordinal == ordinal]
        _require(len(matches) == 1, f"冻结 v2 计划缺少唯一原始序号 {ordinal}")
        package = matches[0]
        selected_view = selected_view_by_id.get(package.package_id)
        _require(selected_view is not None, f"证据视图缺少冻结包 {package.package_id}")
        _require(selected_view.get("package_ordinal") == package.package_ordinal, f"包序号漂移：{package.package_id}")
        _require(
            set(selected_view.get("referenced_owned_unit_ids", [])) <= set(package.owned_structure_unit_ids),
            f"证据视图引用了冻结包外 owned 结构单元：{package.package_id}",
        )
        _require(
            set(selected_view.get("referenced_context_unit_ids", [])) <= set(
                unit.structure_unit_id for unit in package.context_units
            ),
            f"证据视图引用了冻结包外 context 结构单元：{package.package_id}",
        )
        selected_packages.append(package)

    selected_ids = [package.package_id for package in selected_packages]
    _require(len(set(selected_ids)) == 6, "六个代表包 package_id 不唯一")
    owned_ids = [unit_id for package in selected_packages for unit_id in package.owned_structure_unit_ids]
    context_ids = [unit.structure_unit_id for package in selected_packages for unit in package.context_units]
    _require(len(owned_ids) == len(set(owned_ids)), "六个代表包 owned 结构单元重复")
    _require(len(owned_ids) == 61, "六个代表包 owned 结构单元数不是 61")
    _require(len(context_ids) == 382, "六个代表包 context 结构单元总数不是 382")
    _require(len(set(owned_ids) | set(context_ids)) == 237, "六个代表包唯一结构单元总数不是 237")
    _require(set(selected_ids) == set(plan_by_id).intersection(selected_ids), "代表包不在冻结 v2 计划中")

    snapshot_prompt_template_sha256 = str(state_payload.get("prompt_template_sha256", ""))
    runtime_prompt_template_sha256 = phase_applicability_agent_prompt_template_sha256(
        DEFAULT_PHASE_APPLICABILITY_AGENT_PROMPT_TEMPLATE
    )
    prompt_hash_matches_snapshot = (
        snapshot_prompt_template_sha256 == runtime_prompt_template_sha256
    )
    plan_payload = plan.model_dump(mode="json")
    manifest_dump = manifest.model_dump(mode="json")
    expected_input_scope_sha256 = _canonical_sha256(
        {
            "execution_version": PHASE_APPLICABILITY_EXECUTION_VERSION,
            "coverage_manifest": manifest_dump,
            "plan": plan_payload,
        }
    )
    _require(
        state_payload.get("input_scope_sha256") == expected_input_scope_sha256,
        "v2 execution snapshot input_scope_sha256 无法由当前清单/计划重算",
    )

    package_records: list[dict[str, Any]] = []
    package_files: list[tuple[Path, dict[str, Any]]] = []
    for package in selected_packages:
        agent_input = build_phase_applicability_agent_input(package)
        # Re-validate the serialized input so the output is consumable without
        # relying on the in-memory Pydantic object.
        serialized_agent_input = agent_input.model_dump(mode="json")
        PhaseApplicabilityAgentInput.model_validate(serialized_agent_input)
        prompt = build_phase_applicability_agent_prompt(agent_input)
        package_payload = package.model_dump(mode="json")
        package_record = {
            "package_id": package.package_id,
            "package_ordinal": package.package_ordinal,
            "selection_strata": [
                item["stratum_id"]
                for item in selected_strata
                if package.package_id in item["selected_package_ids"]
            ],
            # The evidence view is indexed by the 152 matrix-referenced units;
            # its package membership is therefore a subset, while the frozen
            # package below is the complete source-closed execution payload.
            "referenced_owned_unit_ids": list(
                selected_view_by_id[package.package_id].get("referenced_owned_unit_ids", [])
            ),
            "referenced_context_unit_ids": list(
                selected_view_by_id[package.package_id].get("referenced_context_unit_ids", [])
            ),
            "owned_structure_unit_ids": list(package.owned_structure_unit_ids),
            "context_structure_unit_ids": [
                unit.structure_unit_id for unit in package.context_units
            ],
            "frozen_package": package_payload,
            "agent_input": serialized_agent_input,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "prompt_hash_basis": "current_runtime_default_template",
            "prompt_char_count": len(prompt),
            "target_unit_count": len(agent_input.target_units),
            "context_unit_count": len(package.context_units),
            "context_packet_count": len(agent_input.context_packets),
        }
        package_records.append(package_record)
        package_files.append(
            (
                output_dir / f"package-{package.package_ordinal:04d}-agent-input.json",
                serialized_agent_input,
            )
        )

    source_identity = {
        **manifest_identity,
        "opposite_phase": "phase_iii",
        "freeze_run_id": freeze_payload.get("run_id"),
        "phase_graph_id": freeze_payload.get("phase_graph_id"),
        "projection_id": freeze_payload.get("projection_id"),
        "source_artifact_id": freeze_payload.get("source_artifact", {}).get("source_artifact_id"),
        "source_file_name": freeze_payload.get("source_artifact", {}).get("file_name"),
        "source_size_bytes": freeze_source.get("size_bytes"),
        "manifest_payload_sha256": freeze_payload.get("manifest_payload_sha256"),
    }
    matrix_identity = {
        "matrix_id": view_matrix.get("matrix_id"),
        "protocol_version_id": matrix_payload.get("protocol_version_id"),
        "protocol_document_sha256": matrix_payload.get("protocol_document_sha256"),
        "snapshot_id": matrix_payload.get("snapshot_id"),
        "claims_complete": False,
        "matrix_row_count": len(matrix_rows),
        "source_anchor_count": matrix_anchor_count,
        "referenced_unit_count": len(view_payload.get("unit_records", [])),
    }
    current_plan_identity = {
        "plan_id": plan.plan_id,
        "schema_version": plan.schema_version,
        "payload_sha256": _canonical_sha256(plan_payload),
        "package_count": len(plan.packages),
        "expected_agent_unit_count": len(plan.expected_structure_unit_ids),
        "max_owned_units_per_batch": plan.max_owned_units_per_batch,
        "context_radius": plan.context_radius,
        "batch_packing_policy": plan.batch_packing_policy,
        "execution_snapshot_input_scope_sha256": state_payload.get("input_scope_sha256"),
    }
    selected_package_payload_sha256 = _canonical_sha256(
        [record["frozen_package"] for record in package_records]
    )
    total_prompt_chars = sum(record["prompt_char_count"] for record in package_records)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generator": {
            "path": _relative(Path(__file__)),
            "reads_original_docx": False,
            "calls_model": False,
            "writes_clinical_source": False,
        },
        "source_files": {
            "coverage_manifest": {
                "path": _relative(MANIFEST_PATH),
                "file_sha256": _file_sha256(MANIFEST_PATH),
            },
            "prepared_v2_execution_snapshot": {
                "path": _relative(state_path),
                "file_sha256": _file_sha256(state_path),
            },
            "unit_phase_evidence_view": {
                "path": _relative(VIEW_PATH),
                "file_sha256": _file_sha256(VIEW_PATH),
            },
            "closed_matrix": {
                "path": _relative(MATRIX_PATH),
                "file_sha256": _file_sha256(MATRIX_PATH),
            },
            "freeze_metadata": {
                "path": _relative(FREEZE_METADATA_PATH),
                "file_sha256": _file_sha256(FREEZE_METADATA_PATH),
            },
        },
        "source_identity": source_identity,
        "matrix_identity": matrix_identity,
        "full_frozen_plan_identity": current_plan_identity,
        "selection": {
            "selection_policy": selection_policy,
            "random_sampling": False,
            "selected_package_count": len(package_records),
            "selected_package_ids": selected_ids,
            "selected_package_ordinals": list(SELECTED_PACKAGE_ORDINALS),
            "excluded_frozen_package_count": len(plan.packages) - len(package_records),
            "selected_strata": selected_strata,
            "selected_from_view_claims_complete": view_payload.get("claims_complete"),
        },
        "execution_contract": {
            "execution_version": PHASE_APPLICABILITY_EXECUTION_VERSION,
            "prepared_state_run_id": state_payload.get("run_id"),
            "prepared_state_status": state_payload.get("status"),
            "provider_call_scope": "exactly_six_listed_packages",
            "provider_payload_mode": "one_package_file_per_call",
            "aggregate_file_role": "control_index_and_audit_record_only",
            "aggregate_file_must_not_be_submitted_to_runner": True,
            "provider_input_files": [
                f"package-{package.package_ordinal:04d}-agent-input.json"
                for package in selected_packages
            ],
            "same_session_repair": True,
            "max_transport_retries": 1,
            "max_schema_repairs": 2,
            "checkpoint_after_each_attempt": True,
            "agent_input_version": PHASE_APPLICABILITY_AGENT_INPUT_VERSION,
            "agent_wire_version": PHASE_APPLICABILITY_AGENT_CURRENT_WIRE_VERSION,
            "agent_prompt_version": PHASE_APPLICABILITY_AGENT_PROMPT_VERSION,
            "prepared_state_prompt_template_sha256": snapshot_prompt_template_sha256,
            "runtime_prompt_template_sha256": runtime_prompt_template_sha256,
            "prompt_hash_matches_prepared_state": prompt_hash_matches_snapshot,
            "ready_for_model_execution": prompt_hash_matches_snapshot,
            "claims_complete": False,
            "semantic_run_executed": False,
            "full_semantic_run_requested": False,
            "subject_review": False,
            "visual_test": False,
        },
        "service_scope_note": {
            "service_module": "app.services.phase_applicability_execution",
            "service_contract_reused": True,
            "full_plan_batches_in_prepared_state": len(state_payload.get("batches", [])),
            "selected_batches_in_provider_input": len(package_records),
            "warning": "现有 generic execute 会按完整 state.plan 逐批迭代；本工件只授权 provider 输入中的六包。执行器必须使用六包 allowlist 或逐包 Runner，不得把完整 137 包 state 直接交给 execute。",
        },
        "scope_counts": {
            "selected_owned_unit_count": len(owned_ids),
            "selected_context_unit_total": len(context_ids),
            "selected_unique_structure_unit_count": len(set(owned_ids) | set(context_ids)),
            "aggregate_prompt_char_count": total_prompt_chars,
        },
        "packages": package_records,
        "selected_package_payload_sha256": selected_package_payload_sha256,
        "controlled_input_sha256": "",
    }
    payload["controlled_input_sha256"] = _canonical_sha256(payload)
    return payload, package_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--state-path", type=Path, default=STATE_PATH)
    args = parser.parse_args(argv)
    output_dir = args.output_dir.resolve()
    payload, package_files = _build_payload(
        output_dir,
        state_path=args.state_path.resolve(),
    )
    aggregate_path = output_dir / "controlled-input.json"
    aggregate_file_sha256 = _write_json(aggregate_path, payload)
    for path, package_payload in package_files:
        _write_json(path, package_payload)
    _write_bytes(
        output_dir / "controlled-input.sha256",
        f"{aggregate_file_sha256}  controlled-input.json\n".encode("utf-8"),
    )
    print(
        json.dumps(
            {
                "output": _relative(aggregate_path),
                "controlled_input_sha256": payload["controlled_input_sha256"],
                "aggregate_file_sha256": aggregate_file_sha256,
                "package_count": len(payload["packages"]),
                "package_ordinals": payload["selection"]["selected_package_ordinals"],
                "excluded_frozen_package_count": payload["selection"]["excluded_frozen_package_count"],
                "selected_owned_unit_count": payload["scope_counts"]["selected_owned_unit_count"],
                "selected_context_unit_total": payload["scope_counts"]["selected_context_unit_total"],
                "aggregate_prompt_char_count": payload["scope_counts"]["aggregate_prompt_char_count"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
