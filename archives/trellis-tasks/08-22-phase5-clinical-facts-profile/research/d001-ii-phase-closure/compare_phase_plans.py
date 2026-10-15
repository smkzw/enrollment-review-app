#!/usr/bin/env python3
"""Compare frozen phase plans by stable source locations, not derived IDs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package_index(plan: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(package["package_ordinal"]): package for package in plan["packages"]}


def _unit_by_source_ref(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    units: dict[str, dict[str, Any]] = {}
    for package in plan["packages"]:
        for unit in package["owned_units"]:
            source_ref = unit["source_ref"]
            if source_ref in units:
                raise ValueError(f"语义目标原文定位重复：{source_ref}")
            units[source_ref] = {
                "package_ordinal": package["package_ordinal"],
                "package_id": package["package_id"],
                "structure_unit_id": unit["structure_unit_id"],
                "study_phase": unit["study_phase"],
                "phase_scopes": unit["phase_scopes"],
                "excerpt": unit["excerpt"],
            }
    return units


def _package_summary(package: dict[str, Any]) -> dict[str, Any]:
    return {
        "package_ordinal": package["package_ordinal"],
        "package_id": package["package_id"],
        "owned_source_refs": [unit["source_ref"] for unit in package["owned_units"]],
    }


def _find_packages(plan: dict[str, Any], source_ref: str) -> list[dict[str, Any]]:
    return [
        _package_summary(package)
        for package in plan["packages"]
        if any(unit["source_ref"] == source_ref for unit in package["owned_units"])
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-plan", type=Path, required=True)
    parser.add_argument("--new-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-removed-ref", action="append", default=[])
    parser.add_argument("--key-ref", action="append", default=[])
    parser.add_argument("--reviewed-old-package", action="append", type=int, default=[])
    args = parser.parse_args()

    old_plan = _load(args.old_plan)
    new_plan = _load(args.new_plan)
    old_units = _unit_by_source_ref(old_plan)
    new_units = _unit_by_source_ref(new_plan)
    old_refs = set(old_units)
    new_refs = set(new_units)
    removed_refs = sorted(old_refs - new_refs)
    added_refs = sorted(new_refs - old_refs)
    common_refs = sorted(old_refs & new_refs)
    changed_common_refs = [
        source_ref
        for source_ref in common_refs
        if any(
            old_units[source_ref][field] != new_units[source_ref][field]
            for field in ("study_phase", "phase_scopes", "excerpt")
        )
    ]
    expected_removed_refs = sorted(set(args.expected_removed_ref))

    old_packages = _package_index(old_plan)
    remaps: list[dict[str, Any]] = []
    for ordinal in args.reviewed_old_package:
        old_package = old_packages[ordinal]
        old_owned_refs = [unit["source_ref"] for unit in old_package["owned_units"]]
        exact_matches = [
            _package_summary(package)
            for package in new_plan["packages"]
            if [unit["source_ref"] for unit in package["owned_units"]] == old_owned_refs
        ]
        remaps.append(
            {
                "old": _package_summary(old_package),
                "exact_owned_source_ref_matches": exact_matches,
                "eligible_for_automatic_acceptance": False,
                "reason": "冻结计划及派生身份已变化；历史结果只可作诊断证据，须在新计划下重新运行和复核。",
            }
        )

    report = {
        "schema_version": "phase5/stable-source-plan-diff/v1",
        "comparison_basis": "owned_units.source_ref plus stable semantic fields",
        "old_plan": {
            "path": str(args.old_plan),
            "sha256": _sha256(args.old_plan),
            "plan_id": old_plan["plan_id"],
            "semantic_target_count": len(old_units),
            "package_count": len(old_plan["packages"]),
        },
        "new_plan": {
            "path": str(args.new_plan),
            "sha256": _sha256(args.new_plan),
            "plan_id": new_plan["plan_id"],
            "semantic_target_count": len(new_units),
            "package_count": len(new_plan["packages"]),
        },
        "removed_source_refs": removed_refs,
        "added_source_refs": added_refs,
        "changed_common_source_refs": changed_common_refs,
        "derived_id_changes_with_stable_semantics": sum(
            old_units[source_ref]["structure_unit_id"]
            != new_units[source_ref]["structure_unit_id"]
            for source_ref in common_refs
            if source_ref not in changed_common_refs
        ),
        "expected_removed_source_refs": expected_removed_refs,
        "unexpected_removed_source_refs": sorted(set(removed_refs) - set(expected_removed_refs)),
        "missing_expected_removed_source_refs": sorted(set(expected_removed_refs) - set(removed_refs)),
        "key_ref_packages": {
            source_ref: {
                "old": _find_packages(old_plan, source_ref),
                "new": _find_packages(new_plan, source_ref),
            }
            for source_ref in args.key_ref
        },
        "previously_reviewed_package_remap": remaps,
        "automatic_acceptance_reset": True,
        "accepted": (
            removed_refs == expected_removed_refs
            and not added_refs
            and not changed_common_refs
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "accepted": report["accepted"],
                "old_targets": len(old_units),
                "new_targets": len(new_units),
                "removed": len(removed_refs),
                "added": len(added_refs),
                "changed_common": len(changed_common_refs),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
