#!/usr/bin/env python3
"""Run a generic phase-applicability execution from frozen JSON inputs.

The script intentionally accepts a manifest/plan rather than naming a study.
It first persists the complete input snapshot, then optionally runs the real
configured OpenAI-compatible Agent through the bounded Runner and gate.

``--package-ordinals`` restricts execution to selected frozen packages.  The
source plan file is never modified: a new self-consistent frozen plan is
rebuilt (continuous ordinals, rebuilt package/plan identities and target set)
so the execution scope hash differs from any historical full-plan run and no
checkpoint can be silently reused.
Every package-limited run persists a deterministic provenance JSON in
``--state-dir`` bound to the run id, so the old-to-new package mapping is
durable even without ``--summary``.  A conflicting provenance for the same
run id fails before any semantic Provider call and is never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agents.phase_applicability import (
    DEFAULT_PHASE_APPLICABILITY_AGENT_PROMPT_TEMPLATE,
    PhaseApplicabilityAgentRunner,
)
from app.agents.phase_applicability_transport import (
    OpenAICompatiblePhaseApplicabilityAgentTransport,
)
from app.domain.contracts.phase_applicability import (
    stable_phase_applicability_package_id,
)
from app.domain.contracts.protocol_controls import ProtocolSectionCoverageManifest
from app.protocols.phase_applicability_planning import (
    PHASE_APPLICABILITY_PLAN_V1_VERSION,
    PhaseApplicabilityFrozenPlan,
    PhaseApplicabilityPlanningError,
    _stable_plan_id,
    _stable_plan_id_v1,
    plan_phase_applicability_batches,
)
from app.services.phase_applicability_execution import (
    PhaseApplicabilityExecutionError,
    PhaseApplicabilityExecutionService,
    PhaseApplicabilityExecutionStore,
)


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_manifest(path: Path) -> ProtocolSectionCoverageManifest:
    payload = _load_json(path)
    if isinstance(payload, dict) and "coverage_manifest" in payload:
        payload = payload["coverage_manifest"]
    return ProtocolSectionCoverageManifest.model_validate(payload)


def _load_plan(path: Path) -> PhaseApplicabilityFrozenPlan:
    payload = _load_json(path)
    if isinstance(payload, dict) and "plan" in payload:
        payload = payload["plan"]
    return PhaseApplicabilityFrozenPlan.model_validate(payload)


class PackageSelectionProvenanceError(ValueError):
    """A durable package-selection provenance identity error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


PACKAGE_SELECTION_PROVENANCE_VERSION = (
    "phase5/phase-applicability-package-selection-provenance/v1"
)


def _plan_payload_sha256(plan: PhaseApplicabilityFrozenPlan) -> str:
    """Hash the canonical frozen-plan payload deterministically."""

    serialized = json.dumps(
        plan.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _package_selection_provenance_path(state_dir: Path, run_id: str) -> Path:
    """Run-id-bound provenance path next to the execution checkpoint."""

    if state_dir.suffix.lower() == ".json":
        return state_dir.with_name(
            f"{state_dir.stem}-{run_id}.package-selection-provenance.json"
        )
    return state_dir / f"{run_id}.package-selection-provenance.json"


def _persist_package_selection_provenance(
    path: Path,
    provenance: dict[str, object],
) -> None:
    """Atomically persist deterministic provenance for one run id.

    An existing identical file is a no-op so identical reruns stay stable.
    A conflicting payload is refused without overwriting the first file.
    """

    serialized = _serialize_package_selection_provenance(provenance)
    _verify_existing_package_selection_provenance(path, serialized)
    if path.exists():
        return
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
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def _serialize_package_selection_provenance(
    provenance: dict[str, object],
) -> str:
    return json.dumps(
        provenance,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _verify_existing_package_selection_provenance(
    path: Path,
    serialized: str,
) -> None:
    """Reject a run-id mapping conflict before a checkpoint can be created."""

    if path.exists():
        if path.read_text(encoding="utf-8") != serialized:
            raise PackageSelectionProvenanceError(
                "PACKAGE_SELECTION_PROVENANCE_CONFLICT",
                f"run id 已绑定不同的包选择 provenance，拒绝覆盖：{path}",
            )


def _parse_package_ordinal_values(raw_values: list[str]) -> list[int]:
    """Parse repeatable comma-separated package ordinals deterministically.

    Values are normalized to ascending order regardless of argument order so
    the derived plan identity never depends on how the selection was written.
    """

    ordinals: list[int] = []
    for raw_value in raw_values:
        for token in raw_value.split(","):
            token = token.strip()
            if not token:
                continue
            if not token.isdigit() or int(token) < 1:
                raise ValueError(f"--package-ordinals 需要正整数包序号：{token!r}")
            ordinal = int(token)
            if ordinal in ordinals:
                raise ValueError(f"--package-ordinals 包序号不得重复：{ordinal}")
            ordinals.append(ordinal)
    if not ordinals:
        raise ValueError("--package-ordinals 不能为空")
    return sorted(ordinals)


def _select_frozen_plan_packages(
    plan: PhaseApplicabilityFrozenPlan,
    requested_ordinals: list[int],
    run_id: str,
) -> tuple[PhaseApplicabilityFrozenPlan, dict[str, object]]:
    """Derive a self-consistent frozen plan limited to selected packages.

    The source plan is never mutated.  Selected packages keep their original
    source order but are renumbered to a continuous ordinal sequence; package
    identities, the target set and the plan identity are rebuilt through the
    contract's own stable identity rules so the derived plan validates as a
    fresh frozen plan.  The returned provenance payload is deterministic and
    records the full audit chain: source and derived plan identities, source
    and derived plan payload hashes, selected source ordinals, and one mapping
    per package with source and derived identities plus exact owned
    structure-unit IDs.
    """

    by_ordinal = {package.package_ordinal: package for package in plan.packages}
    missing = [
        ordinal
        for ordinal in sorted(set(requested_ordinals))
        if ordinal not in by_ordinal
    ]
    if missing:
        raise PhaseApplicabilityPlanningError(
            "package_ordinal_missing",
            "冻结计划中没有这些包序号："
            + ",".join(str(ordinal) for ordinal in missing),
        )
    selected = [by_ordinal[ordinal] for ordinal in sorted(set(requested_ordinals))]
    packages: list[dict[str, object]] = []
    package_mappings: list[dict[str, object]] = []
    expected_ids: list[str] = []
    for new_ordinal, package in enumerate(selected, start=1):
        payload = package.model_dump(mode="json")
        owned_ids = list(package.owned_structure_unit_ids)
        derived_package_id = stable_phase_applicability_package_id(
            plan.coverage_manifest_id, new_ordinal, owned_ids
        )
        payload["package_ordinal"] = new_ordinal
        payload["package_id"] = derived_package_id
        packages.append(payload)
        expected_ids.extend(owned_ids)
        package_mappings.append(
            {
                "source_ordinal": package.package_ordinal,
                "source_package_id": package.package_id,
                "derived_ordinal": new_ordinal,
                "derived_package_id": derived_package_id,
                "owned_structure_unit_ids": owned_ids,
            }
        )
    derived_package_ids = [
        str(mapping["derived_package_id"]) for mapping in package_mappings
    ]
    if plan.schema_version == PHASE_APPLICABILITY_PLAN_V1_VERSION:
        derived_plan_id = _stable_plan_id_v1(
            plan.coverage_manifest_id,
            plan.max_owned_units_per_batch,
            plan.context_radius,
            derived_package_ids,
        )
    else:
        derived_plan_id = _stable_plan_id(
            plan.coverage_manifest_id,
            plan.max_owned_units_per_batch,
            plan.context_radius,
            plan.batch_packing_policy,
            derived_package_ids,
        )
    derived = PhaseApplicabilityFrozenPlan(
        schema_version=plan.schema_version,
        plan_id=derived_plan_id,
        coverage_manifest_id=plan.coverage_manifest_id,
        protocol_version_id=plan.protocol_version_id,
        study_phase=plan.study_phase,
        max_owned_units_per_batch=plan.max_owned_units_per_batch,
        context_radius=plan.context_radius,
        batch_packing_policy=plan.batch_packing_policy,
        expected_structure_unit_ids=expected_ids,
        packages=packages,
    )
    provenance = {
        "schema_version": PACKAGE_SELECTION_PROVENANCE_VERSION,
        "run_id": run_id,
        "source_plan_id": plan.plan_id,
        "derived_plan_id": derived.plan_id,
        "selected_source_ordinals": [package.package_ordinal for package in selected],
        "source_plan_sha256": _plan_payload_sha256(plan),
        "derived_plan_sha256": _plan_payload_sha256(derived),
        "package_mappings": package_mappings,
    }
    return derived, provenance


def _summary(state) -> dict[str, object]:
    return {
        "run_id": state.run_id,
        "status": state.status,
        "input_scope_sha256": state.input_scope_sha256,
        "prompt_template_sha256": state.prompt_template_sha256,
        "transport_identity": state.transport_identity,
        "coverage_manifest_id": state.coverage_manifest.manifest_id,
        "protocol_version_id": state.coverage_manifest.protocol_version_id,
        "protocol_document_sha256": state.coverage_manifest.protocol_document_sha256,
        "snapshot_id": state.coverage_manifest.snapshot_id,
        "coverage_unit_count": len(state.coverage_manifest.units),
        "expected_agent_unit_count": len(state.plan.expected_structure_unit_ids),
        "batch_count": len(state.batches),
        "accepted_batch_count": len(state.accepted_package_ids),
        "accepted_unit_count": len(state.accepted_structure_unit_ids),
        "unresolved_unit_count": len(state.unresolved_structure_unit_ids),
        "batch_statuses": [record.status for record in state.batches],
        "raw_output_sha256_count": sum(
            len(record.raw_output_sha256) for record in state.batches
        ),
        "attempt_count": sum(record.attempt_count for record in state.batches),
        "issue_count": sum(record.issue_count for record in state.batches),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage-manifest", type=Path, required=True)
    parser.add_argument("--plan", type=Path)
    parser.add_argument(
        "--package-ordinals",
        action="append",
        default=None,
        metavar="ORDINALS",
        help=(
            "可重复的冻结包序号选择（正整数，逗号分隔）。仅重建选中包的自洽"
            "计划身份、目标全集与包身份；原计划文件不被修改，执行范围哈希"
            "与历史完整计划运行不同，不会静默复用旧 checkpoint。每个限包"
            "运行都会把确定性 provenance 持久化到 --state-dir 并绑定 run "
            "id；同一 run id 的冲突 provenance 会在任何语义模型调用前失败。"
        ),
    )
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--backend")
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort")
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--max-owned-units-per-batch", type=int, default=12)
    parser.add_argument("--context-radius", type=int, default=1)
    parser.add_argument("--max-transport-retries", type=int, default=1)
    parser.add_argument("--max-schema-repairs", type=int, default=2)
    parser.add_argument("--prompt-template", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    manifest = _load_manifest(args.coverage_manifest)
    plan = _load_plan(args.plan) if args.plan else plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=args.max_owned_units_per_batch,
        context_radius=args.context_radius,
    )
    package_selection: dict[str, object] | None = None
    if args.package_ordinals:
        try:
            requested_ordinals = _parse_package_ordinal_values(args.package_ordinals)
        except ValueError as exc:
            parser.error(str(exc))
        try:
            plan, package_selection = _select_frozen_plan_packages(
                plan, requested_ordinals, run_id=args.run_id
            )
        except PhaseApplicabilityPlanningError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    service = PhaseApplicabilityExecutionService(
        PhaseApplicabilityExecutionStore(args.state_dir),
        runner=PhaseApplicabilityAgentRunner(
            max_transport_retries=args.max_transport_retries,
            max_schema_repairs=args.max_schema_repairs,
        ),
    )
    provenance_path = _package_selection_provenance_path(args.state_dir, args.run_id)

    def persist_selection_provenance() -> None:
        if package_selection is not None:
            _persist_package_selection_provenance(provenance_path, package_selection)

    def preflight_selection_provenance() -> None:
        if package_selection is not None:
            _verify_existing_package_selection_provenance(
                provenance_path,
                _serialize_package_selection_provenance(package_selection),
            )

    try:
        # A conflicting mapping must fail before prepare() can recreate a
        # missing checkpoint for a different package selection.
        preflight_selection_provenance()
        if args.build_only:
            state = service.prepare(
                run_id=args.run_id,
                coverage_manifest=manifest,
                plan=plan,
                max_owned_units_per_batch=args.max_owned_units_per_batch,
                context_radius=args.context_radius,
            )
            persist_selection_provenance()
        else:
            # Persist the durable input checkpoint before any model call.
            service.prepare(
                run_id=args.run_id,
                coverage_manifest=manifest,
                plan=plan,
                max_owned_units_per_batch=args.max_owned_units_per_batch,
                context_radius=args.context_radius,
            )
            # Verify/persist the run-id-bound provenance before executing.
            persist_selection_provenance()
            transport = OpenAICompatiblePhaseApplicabilityAgentTransport(
                **{
                    key: value
                    for key, value in {
                        "backend": args.backend,
                        "base_url": args.base_url,
                        "model": args.model,
                        "reasoning_effort": args.reasoning_effort,
                        "max_tokens": args.max_tokens,
                        "temperature": args.temperature,
                    }.items()
                    if value is not None
                }
            )
            prompt_template = (
                args.prompt_template.read_text(encoding="utf-8")
                if args.prompt_template
                else None
            )
            state = service.execute(
                run_id=args.run_id,
                coverage_manifest=manifest,
                plan=plan,
                transport=transport,
                prompt_template=prompt_template
                or DEFAULT_PHASE_APPLICABILITY_AGENT_PROMPT_TEMPLATE,
                max_owned_units_per_batch=args.max_owned_units_per_batch,
                context_radius=args.context_radius,
            )
    except (
        PhaseApplicabilityExecutionError,
        PackageSelectionProvenanceError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    summary = _summary(state)
    summary["plan_id"] = state.plan.plan_id
    if package_selection is not None:
        summary["package_selection"] = package_selection
    output = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if state.status == "completed" else 2 if not args.build_only else 0


if __name__ == "__main__":
    raise SystemExit(main())
