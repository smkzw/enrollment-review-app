"""Focused tests for the package-limited execution entry.

Covers ``scripts/run_phase_applicability_acceptance.py --package-ordinals``:
deterministic ordinal parsing, self-consistent frozen-plan identity rebuild,
source-plan immutability, execution-scope isolation so historical checkpoints
can never be silently reused, and the durable run-id-bound provenance JSON
that makes the old-to-new package mapping auditable even without
``--summary``.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.domain.contracts.enums import PhaseScope, StudyPhase
from app.domain.contracts.phase_applicability import (
    stable_phase_applicability_package_id,
)
from app.domain.contracts.protocol_controls import (
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    StructureUnitKind,
)
from app.protocols.phase_applicability_planning import (
    PhaseApplicabilityFrozenPlan,
    PhaseApplicabilityPlanningError,
    plan_phase_applicability_batches,
)
from app.services.phase_applicability_execution import (
    PhaseApplicabilityExecutionError,
    PhaseApplicabilityExecutionService,
    PhaseApplicabilityExecutionStore,
)


_SHA = "a" * 64
_SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "run_phase_applicability_acceptance.py"
)
_SLICE58Q_ARTIFACTS = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "phase5-slice58q-mixed-paragraph-strong-boundary-20260826"
)
_SELECTED_ORDINALS = (67, 78, 79, 80, 111)
_PROVENANCE_VERSION = (
    "phase5/phase-applicability-package-selection-provenance/v1"
)


def _load_script_module():
    spec = importlib.util.spec_from_file_location(
        "run_phase_applicability_acceptance", _SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script_module():
    return _load_script_module()


def _unit(unit_id: str, order: int, scope: PhaseScope) -> ProtocolStructureUnit:
    return ProtocolStructureUnit(
        structure_unit_id=unit_id,
        source_ref=f"body.p{order}",
        member_source_refs=[f"body.p{order}"],
        source_span_ids=[f"span-{unit_id}"],
        unit_kind=StructureUnitKind.PARAGRAPH,
        heading_path=["5 研究设计", "5.2 期别说明"],
        source_order=order,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[scope],
        excerpt=f"来源 {unit_id}：本条需要判断研究期别。",
    )


def _manifest() -> ProtocolSectionCoverageManifest:
    units = [_unit("explicit-0", 0, PhaseScope.PHASE_II)]
    units.extend(
        _unit(f"target-{index}", index, PhaseScope.UNKNOWN)
        for index in range(1, 6)
    )
    return ProtocolSectionCoverageManifest(
        manifest_id="manifest:package-selection",
        protocol_version_id="protocol:package-selection",
        protocol_document_sha256=_SHA,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:package-selection",
        units=units,
    )


def _synthetic_plan() -> PhaseApplicabilityFrozenPlan:
    return plan_phase_applicability_batches(
        _manifest(),
        max_owned_units_per_batch=2,
        context_radius=0,
    )


def test_selection_rebuilds_self_consistent_frozen_plan(script_module):
    original = _synthetic_plan()
    assert len(original.packages) == 3
    assert original.expected_structure_unit_ids == [
        f"target-{index}" for index in range(1, 6)
    ]

    derived, provenance = script_module._select_frozen_plan_packages(
        original, [3, 2], run_id="run-sel-2-3"
    )

    assert provenance["schema_version"] == _PROVENANCE_VERSION
    assert provenance["run_id"] == "run-sel-2-3"
    assert provenance["source_plan_id"] == original.plan_id
    assert provenance["derived_plan_id"] == derived.plan_id
    assert provenance["selected_source_ordinals"] == [2, 3]
    assert provenance["source_plan_sha256"] == script_module._plan_payload_sha256(
        original
    )
    assert provenance["derived_plan_sha256"] == script_module._plan_payload_sha256(
        derived
    )
    assert [package.package_ordinal for package in derived.packages] == [1, 2]
    source_second, source_third = original.packages[1], original.packages[2]
    assert derived.packages[0].owned_units == source_second.owned_units
    assert derived.packages[1].owned_units == source_third.owned_units
    assert derived.packages[0].package_id == stable_phase_applicability_package_id(
        original.coverage_manifest_id,
        1,
        list(source_second.owned_structure_unit_ids),
    )
    assert derived.packages[1].package_id == stable_phase_applicability_package_id(
        original.coverage_manifest_id,
        2,
        list(source_third.owned_structure_unit_ids),
    )
    assert provenance["package_mappings"] == [
        {
            "source_ordinal": 2,
            "source_package_id": source_second.package_id,
            "derived_ordinal": 1,
            "derived_package_id": derived.packages[0].package_id,
            "owned_structure_unit_ids": list(
                source_second.owned_structure_unit_ids
            ),
        },
        {
            "source_ordinal": 3,
            "source_package_id": source_third.package_id,
            "derived_ordinal": 2,
            "derived_package_id": derived.packages[1].package_id,
            "owned_structure_unit_ids": list(
                source_third.owned_structure_unit_ids
            ),
        },
    ]
    assert derived.expected_structure_unit_ids == [
        "target-3",
        "target-4",
        "target-5",
    ]
    assert derived.plan_id != original.plan_id

    # The source plan is never mutated in place.
    assert [package.package_ordinal for package in original.packages] == [1, 2, 3]
    assert original.plan_id == provenance["source_plan_id"]
    assert original.expected_structure_unit_ids == [
        f"target-{index}" for index in range(1, 6)
    ]

    # The derived plan round-trips cleanly through the frozen-plan contract.
    assert PhaseApplicabilityFrozenPlan.model_validate(derived.model_dump()) == derived


def test_selection_rejects_unknown_and_invalid_ordinals(script_module):
    original = _synthetic_plan()
    with pytest.raises(
        PhaseApplicabilityPlanningError, match="package_ordinal_missing"
    ):
        script_module._select_frozen_plan_packages(original, [2, 99], run_id="run-x")

    with pytest.raises(ValueError, match="正整数包序号"):
        script_module._parse_package_ordinal_values(["0"])
    with pytest.raises(ValueError, match="正整数包序号"):
        script_module._parse_package_ordinal_values(["-3"])
    with pytest.raises(ValueError, match="正整数包序号"):
        script_module._parse_package_ordinal_values(["abc"])
    with pytest.raises(ValueError, match="不得重复"):
        script_module._parse_package_ordinal_values(["2,3", "3"])
    with pytest.raises(ValueError, match="不能为空"):
        script_module._parse_package_ordinal_values([" , "])

    assert script_module._parse_package_ordinal_values(["3, 2", "1"]) == [1, 2, 3]


def test_selecting_all_ordinals_reproduces_source_plan(script_module):
    original = _synthetic_plan()
    derived, provenance = script_module._select_frozen_plan_packages(
        original, [1, 2, 3], run_id="run-all"
    )
    assert provenance["selected_source_ordinals"] == [1, 2, 3]
    assert provenance["derived_plan_id"] == original.plan_id
    assert derived.model_dump() == original.model_dump()


def test_provenance_path_is_run_id_bound(script_module, tmp_path: Path):
    state_dir = tmp_path / "execution"
    path = script_module._package_selection_provenance_path(state_dir, "run-a")
    assert path == state_dir / "run-a.package-selection-provenance.json"

    file_store = tmp_path / "runs" / "legacy.json"
    file_path = script_module._package_selection_provenance_path(
        file_store, "run-a"
    )
    assert file_path == file_store.with_name(
        "legacy-run-a.package-selection-provenance.json"
    )


def test_provenance_persistence_refuses_conflict_and_allows_identical(
    script_module, tmp_path: Path
):
    original = _synthetic_plan()
    _, provenance = script_module._select_frozen_plan_packages(
        original, [2, 3], run_id="run-prov"
    )
    path = tmp_path / "run-prov.package-selection-provenance.json"
    script_module._persist_package_selection_provenance(path, provenance)
    first_bytes = path.read_text(encoding="utf-8")
    assert json.loads(first_bytes) == provenance

    # Identical rerun is a no-op.
    script_module._persist_package_selection_provenance(path, provenance)
    assert path.read_text(encoding="utf-8") == first_bytes

    # A different selection for the same run id is refused, file untouched.
    _, other = script_module._select_frozen_plan_packages(
        original, [1, 2], run_id="run-prov"
    )
    with pytest.raises(
        script_module.PackageSelectionProvenanceError,
        match="PACKAGE_SELECTION_PROVENANCE_CONFLICT",
    ):
        script_module._persist_package_selection_provenance(path, other)
    assert path.read_text(encoding="utf-8") == first_bytes


def test_scoped_plan_blocks_silent_reuse_of_historical_checkpoint(tmp_path: Path):
    manifest = _manifest()
    original = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=2,
        context_radius=0,
    )
    script_module = _load_script_module()
    derived, _ = script_module._select_frozen_plan_packages(
        original, [2, 3], run_id="run-scoped-prep"
    )

    store = PhaseApplicabilityExecutionStore(tmp_path / "runs")
    service = PhaseApplicabilityExecutionService(store)
    full = service.prepare(
        run_id="run-full", coverage_manifest=manifest, plan=original
    )
    with pytest.raises(PhaseApplicabilityExecutionError, match="EXECUTION_INPUT_CONFLICT"):
        service.prepare(run_id="run-full", coverage_manifest=manifest, plan=derived)

    scoped = service.prepare(
        run_id="run-scoped", coverage_manifest=manifest, plan=derived
    )
    assert scoped.input_scope_sha256 != full.input_scope_sha256
    assert [record.package_id for record in scoped.batches] == [
        package.package_id for package in derived.packages
    ]
    assert all(record.status == "pending" for record in scoped.batches)
    assert (tmp_path / "runs" / "run-scoped.json").is_file()


def _slice58q_inputs() -> tuple[Path, Path] | None:
    manifest_path = _SLICE58Q_ARTIFACTS / "coverage_manifest.json"
    plan_path = _SLICE58Q_ARTIFACTS / "frozen_phase_plan.json"
    if not manifest_path.is_file() or not plan_path.is_file():
        return None
    return manifest_path, plan_path


def _run_script(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _package_ordinal_flags(values: list[str]) -> list[str]:
    flags: list[str] = []
    for value in values:
        flags.extend(["--package-ordinals", value])
    return flags


def _slice58q_base_args(
    manifest_path: Path, plan_path: Path, state_dir: Path, run_id: str
) -> list[str]:
    return [
        "--coverage-manifest",
        str(manifest_path),
        "--plan",
        str(plan_path),
        "--state-dir",
        str(state_dir),
        "--run-id",
        run_id,
        "--build-only",
    ]


def test_cli_package_selection_prepares_scoped_checkpoint(
    script_module, tmp_path: Path
):
    inputs = _slice58q_inputs()
    if inputs is None:
        pytest.skip("58q 冻结输入缺失")
    manifest_path, plan_path = inputs
    source_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    state_dir = tmp_path / "execution"
    summary_path = tmp_path / "summary.json"

    result = _run_script(
        [
            "--coverage-manifest",
            str(manifest_path),
            "--plan",
            str(plan_path),
            "--state-dir",
            str(state_dir),
            "--run-id",
            "scope-test-pkg67-78-79-80-111",
            "--build-only",
            "--package-ordinals",
            "67,78",
            "--package-ordinals",
            "79,80,111",
            "--summary",
            str(summary_path),
        ]
    )
    assert result.returncode == 0, result.stdout + result.stderr

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["batch_count"] == len(_SELECTED_ORDINALS)
    assert summary["batch_statuses"] == ["pending"] * len(_SELECTED_ORDINALS)
    assert summary["plan_id"] != source_plan["plan_id"]

    selection = summary["package_selection"]
    assert selection["schema_version"] == _PROVENANCE_VERSION
    assert selection["run_id"] == "scope-test-pkg67-78-79-80-111"
    assert selection["source_plan_id"] == source_plan["plan_id"]
    assert selection["derived_plan_id"] == summary["plan_id"]
    assert selection["selected_source_ordinals"] == list(_SELECTED_ORDINALS)
    source_packages = {
        str(package["package_ordinal"]): package
        for package in source_plan["packages"]
    }
    for mapping in selection["package_mappings"]:
        assert mapping["source_package_id"] == source_packages[
            str(mapping["source_ordinal"])
        ]["package_id"]
    source_plan_obj = script_module._load_plan(plan_path)
    assert selection["source_plan_sha256"] == script_module._plan_payload_sha256(
        source_plan_obj
    )

    expected_ids = [
        unit["structure_unit_id"]
        for package in source_plan["packages"]
        if package["package_ordinal"] in set(_SELECTED_ORDINALS)
        for unit in package["owned_units"]
    ]
    assert summary["expected_agent_unit_count"] == len(expected_ids)

    checkpoint_path = state_dir / "scope-test-pkg67-78-79-80-111.json"
    assert checkpoint_path.is_file()
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert [package["package_ordinal"] for package in checkpoint["plan"]["packages"]] == [
        index for index in range(1, len(_SELECTED_ORDINALS) + 1)
    ]
    assert checkpoint["plan"]["expected_structure_unit_ids"] == expected_ids
    assert all(
        record["status"] == "pending" for record in checkpoint["batches"]
    )

    legacy_state_path = (
        _SLICE58Q_ARTIFACTS
        / "execution"
        / "d001-ii-phase-closure-20260826-slice58q.json"
    )
    if legacy_state_path.is_file():
        legacy = json.loads(legacy_state_path.read_text(encoding="utf-8"))
        assert summary["input_scope_sha256"] != legacy["input_scope_sha256"]


def test_cli_build_only_without_summary_writes_reloadable_provenance(
    script_module, tmp_path: Path
):
    inputs = _slice58q_inputs()
    if inputs is None:
        pytest.skip("58q 冻结输入缺失")
    manifest_path, plan_path = inputs
    source_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    state_dir = tmp_path / "execution"
    run_id = "prov-test-pkg67-78-79-80-111"

    result = _run_script(
        [
            *_slice58q_base_args(manifest_path, plan_path, state_dir, run_id),
            *_package_ordinal_flags(["67,78,79,80,111"]),
        ]
    )
    assert result.returncode == 0, result.stdout + result.stderr

    provenance_path = state_dir / f"{run_id}.package-selection-provenance.json"
    assert provenance_path.is_file()
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    assert provenance["schema_version"] == _PROVENANCE_VERSION
    assert provenance["run_id"] == run_id
    assert provenance["source_plan_id"] == source_plan["plan_id"]
    assert provenance["selected_source_ordinals"] == list(_SELECTED_ORDINALS)

    checkpoint_path = state_dir / f"{run_id}.json"
    assert checkpoint_path.is_file()
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint["plan"]["plan_id"] == provenance["derived_plan_id"]

    # Payload hashes re-verify against the canonical frozen-plan payloads.
    source_plan_obj = script_module._load_plan(plan_path)
    derived_plan_obj = PhaseApplicabilityFrozenPlan.model_validate(
        checkpoint["plan"]
    )
    assert provenance["source_plan_sha256"] == script_module._plan_payload_sha256(
        source_plan_obj
    )
    assert provenance["derived_plan_sha256"] == script_module._plan_payload_sha256(
        derived_plan_obj
    )

    # The mapping exactly matches both the source plan and the checkpoint.
    source_packages = {
        package["package_ordinal"]: package for package in source_plan["packages"]
    }
    checkpoint_packages = {
        package["package_ordinal"]: package
        for package in checkpoint["plan"]["packages"]
    }
    assert [
        mapping["source_ordinal"] for mapping in provenance["package_mappings"]
    ] == list(_SELECTED_ORDINALS)
    assert [
        mapping["derived_ordinal"] for mapping in provenance["package_mappings"]
    ] == [index for index in range(1, len(_SELECTED_ORDINALS) + 1)]
    for mapping in provenance["package_mappings"]:
        source_package = source_packages[mapping["source_ordinal"]]
        derived_package = checkpoint_packages[mapping["derived_ordinal"]]
        assert mapping["source_package_id"] == source_package["package_id"]
        assert mapping["derived_package_id"] == derived_package["package_id"]
        assert mapping["owned_structure_unit_ids"] == [
            unit["structure_unit_id"] for unit in source_package["owned_units"]
        ]
        assert mapping["owned_structure_unit_ids"] == [
            unit["structure_unit_id"] for unit in derived_package["owned_units"]
        ]
    assert checkpoint["plan"]["expected_structure_unit_ids"] == [
        unit_id
        for mapping in provenance["package_mappings"]
        for unit_id in mapping["owned_structure_unit_ids"]
    ]


def test_cli_identical_rerun_is_stable(tmp_path: Path):
    inputs = _slice58q_inputs()
    if inputs is None:
        pytest.skip("58q 冻结输入缺失")
    manifest_path, plan_path = inputs
    state_dir = tmp_path / "execution"
    run_id = "prov-test-stable-rerun"
    args = [
        *_slice58q_base_args(manifest_path, plan_path, state_dir, run_id),
        *_package_ordinal_flags(["67,78,79,80,111"]),
    ]
    first = _run_script(args)
    assert first.returncode == 0, first.stdout + first.stderr
    provenance_path = state_dir / f"{run_id}.package-selection-provenance.json"
    checkpoint_path = state_dir / f"{run_id}.json"
    first_provenance = provenance_path.read_text(encoding="utf-8")
    first_checkpoint = checkpoint_path.read_text(encoding="utf-8")

    second = _run_script(args)
    assert second.returncode == 0, second.stdout + second.stderr
    assert provenance_path.read_text(encoding="utf-8") == first_provenance
    assert checkpoint_path.read_text(encoding="utf-8") == first_checkpoint


def test_cli_conflicting_selection_same_run_id_fails(tmp_path: Path):
    inputs = _slice58q_inputs()
    if inputs is None:
        pytest.skip("58q 冻结输入缺失")
    manifest_path, plan_path = inputs
    state_dir = tmp_path / "execution"
    run_id = "prov-test-conflict"
    base = _slice58q_base_args(manifest_path, plan_path, state_dir, run_id)

    first = _run_script([*base, *_package_ordinal_flags(["67,78,79,80,111"])])
    assert first.returncode == 0, first.stdout + first.stderr
    provenance_path = state_dir / f"{run_id}.package-selection-provenance.json"
    checkpoint_path = state_dir / f"{run_id}.json"
    first_provenance = provenance_path.read_text(encoding="utf-8")
    first_checkpoint = checkpoint_path.read_text(encoding="utf-8")

    second = _run_script([*base, *_package_ordinal_flags(["67,78,79,80"])])
    assert second.returncode != 0
    assert "PACKAGE_SELECTION_PROVENANCE_CONFLICT" in second.stdout + second.stderr
    # The first provenance and checkpoint are never modified.
    assert provenance_path.read_text(encoding="utf-8") == first_provenance
    assert checkpoint_path.read_text(encoding="utf-8") == first_checkpoint


def test_cli_conflicting_provenance_blocks_checkpoint_rebuild(tmp_path: Path):
    inputs = _slice58q_inputs()
    if inputs is None:
        pytest.skip("58q 冻结输入缺失")
    manifest_path, plan_path = inputs
    state_dir = tmp_path / "execution"
    run_id = "prov-test-conflict-lost-checkpoint"
    base = _slice58q_base_args(manifest_path, plan_path, state_dir, run_id)

    first = _run_script([*base, *_package_ordinal_flags(["67,78,79,80,111"])])
    assert first.returncode == 0, first.stdout + first.stderr
    provenance_path = state_dir / f"{run_id}.package-selection-provenance.json"
    first_provenance = provenance_path.read_text(encoding="utf-8")
    checkpoint_path = state_dir / f"{run_id}.json"
    checkpoint_path.unlink()

    # Even with the checkpoint gone, the provenance alone detects the
    # identity change and is never overwritten.
    second = _run_script([*base, *_package_ordinal_flags(["67,78,79,80"])])
    assert second.returncode != 0
    assert "PACKAGE_SELECTION_PROVENANCE_CONFLICT" in second.stdout + second.stderr
    assert provenance_path.read_text(encoding="utf-8") == first_provenance
    # The preflight conflict check runs before prepare(), so a missing
    # checkpoint is not recreated for the conflicting selection.
    assert not checkpoint_path.exists()


def test_cli_rejects_unknown_package_ordinal(tmp_path: Path):
    inputs = _slice58q_inputs()
    if inputs is None:
        pytest.skip("58q 冻结输入缺失")
    manifest_path, plan_path = inputs

    result = _run_script(
        [
            *_slice58q_base_args(
                manifest_path, plan_path, tmp_path / "execution", "scope-test-bad-ordinal"
            ),
            *_package_ordinal_flags(["67,999"]),
        ]
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "package_ordinal_missing" in combined
    assert "999" in combined
    assert not (tmp_path / "execution" / "scope-test-bad-ordinal.json").exists()
    assert not (
        tmp_path
        / "execution"
        / "scope-test-bad-ordinal.package-selection-provenance.json"
    ).exists()


def test_cli_rejects_duplicate_package_ordinal(tmp_path: Path):
    inputs = _slice58q_inputs()
    if inputs is None:
        pytest.skip("58q 冻结输入缺失")
    manifest_path, plan_path = inputs

    result = _run_script(
        [
            *_slice58q_base_args(
                manifest_path, plan_path, tmp_path / "execution", "scope-test-duplicate"
            ),
            *_package_ordinal_flags(["67,78", "78,79"]),
        ]
    )
    assert result.returncode != 0
    assert "不得重复" in result.stdout + result.stderr
    assert not (tmp_path / "execution" / "scope-test-duplicate.json").exists()
    assert not (
        tmp_path / "execution" / "scope-test-duplicate.package-selection-provenance.json"
    ).exists()
