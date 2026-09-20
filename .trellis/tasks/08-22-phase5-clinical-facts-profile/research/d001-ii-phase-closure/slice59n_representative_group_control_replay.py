#!/usr/bin/env python3
"""Configurable representative-group ProtocolControlAgent replay.

Converges the Table-5-only slice59m helper into a minimal config-driven harness.
Uses product ProtocolControlAgentRunner + check_protocol_control_publication.
Does not invent clinical obligations; Agent output remains the only semantic pass.

Modes:
  --dry-run   resolve units, build batch/prompt/gate scaffold, write prepare dir
  (default)   invoke real MTPLX transport through the product runner
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
PHASE_CLOSURE_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(PHASE_CLOSURE_DIR) not in sys.path:
    sys.path.insert(0, str(PHASE_CLOSURE_DIR))

from app.agents.protocol_control_agent_transport import (  # noqa: E402
    OpenAICompatibleProtocolControlAgentTransport,
)
from app.agents.protocol_control_deconstructor import (  # noqa: E402
    DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE,
    ProtocolControlAgentResponse,
    ProtocolControlAgentRunner,
    ProtocolControlAgentWireValidationError,
    build_protocol_control_agent_prompt,
    protocol_control_agent_prompt_template_sha256,
)
from app.domain.contracts.enums import PhaseScope, ReviewStage, StudyPhase  # noqa: E402
from app.domain.contracts.phase_applicability import (  # noqa: E402
    PhaseApplicabilityCandidateDraft,
    PhaseApplicabilityDisposition,
    PhaseApplicabilityEvidenceDraft,
    PhaseApplicabilityEvidencePolarity,
    PhaseApplicabilityResolutionBatchDraft,
    PhaseApplicabilityResolutionDraft,
)
from app.domain.contracts.protocol_controls import (  # noqa: E402
    ControlCrossSourceRelation,
    ControlRelationTargetKind,
    KnownOfficialRuleTarget,
    KnownRequiredProcedureTarget,
    KnownWorkflowStageTarget,
    ProtocolControlBatchPlan,
    ProtocolControlDispositionBatch,
    ProtocolReviewControl,
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    PublishedProtocolControlCatalog,
    StructureUnitKind,
    TableCellContext,
    stable_protocol_control_batch_id,
)
from app.domain.contracts.rules import WorkflowStage  # noqa: E402
from app.protocols.full_protocol_coverage import (  # noqa: E402
    build_resolved_full_protocol_coverage_view,
)
from app.protocols.phase_applicability import (  # noqa: E402
    hydrate_phase_applicability_resolution,
)
from app.protocols.phase_applicability_planning import (  # noqa: E402
    plan_phase_applicability_batches,
)
from app.protocols.protocol_control_gate import (  # noqa: E402
    check_protocol_control_publication,
)
from app.protocols.protocol_control_repair_errors import (  # noqa: E402
    clinical_repair_error as _clinical_repair_error,
    combined_repair_error as _combined_repair_error,
    publication_repair_error as _publication_repair_error,
    replay_validation_error as _replay_validation_error,
)
from app.protocols.protocol_control_planning import (  # noqa: E402
    detect_required_action_kinds,
    plan_protocol_control_batches,
)
from slice59n_representative_group_reject_gates import (  # noqa: E402
    evaluate_hydrated_agent_output,
    evaluate_prepare_source_closure,
    first_reject,
)

CONFIG_SCHEMA = "phase5/representative-group-control-replay-config/v1"


@dataclass(frozen=True)
class ResolvedUnit:
    source_ref: str
    role: str  # owned | attached
    lookup: str
    structure_unit_id: str
    source_span_ids: tuple[str, ...]
    member_source_refs: tuple[str, ...]
    excerpt: str
    heading_path: tuple[str, ...]
    source_order: int
    unit_kind: str
    table_context: dict[str, Any] | None
    study_phase: str
    phase_scopes: tuple[str, ...]
    is_footnote_or_note: bool
    package_ordinal: int | None
    package_id: str | None
    protocol_document_sha256: str
    protocol_version_id: str
    snapshot_id: str


def _technical_replay_accepted(
    *,
    hydrated: object | None,
    publication_gate_accepted: bool,
    clinical_issues: list[object],
) -> bool:
    """Return true only after hydration and both deterministic gates pass."""

    return (
        hydrated is not None
        and publication_gate_accepted
        and not clinical_issues
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
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
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def _repo_path(raw: str | None) -> Path | None:
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def _load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    extends = config.pop("extends", None)
    if extends:
        base_path = (path.parent / str(extends)).resolve()
        base = _load_config(base_path)
        for key, value in config.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key] = {**base[key], **value}
            else:
                base[key] = value
        config = base
    if config.get("schema_version") != CONFIG_SCHEMA:
        raise SystemExit(
            f"unsupported config schema_version={config.get('schema_version')!r};"
            f" expected {CONFIG_SCHEMA!r}"
        )
    for key in (
        "group_id",
        "task_id",
        "expected_protocol_sha256",
        "frozen_plan_path",
        "coverage_manifest_path",
        "owned_source_refs",
        "study_phase",
        "ids",
    ):
        if key not in config:
            raise SystemExit(f"config missing required key: {key}")
    if not config["owned_source_refs"]:
        raise SystemExit("owned_source_refs must be non-empty")
    return config


def _index_frozen_plan(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for pkg in plan["packages"]:
        meta = {
            "package_ordinal": int(pkg["package_ordinal"]),
            "package_id": pkg["package_id"],
            "protocol_document_sha256": pkg["protocol_document_sha256"],
            "protocol_version_id": pkg["protocol_version_id"],
            "snapshot_id": pkg["snapshot_id"],
            "coverage_manifest_id": pkg.get("coverage_manifest_id"),
        }
        for bucket in ("owned_units", "context_units"):
            for unit in pkg.get(bucket) or []:
                ref = unit["source_ref"]
                # Prefer first owned hit; do not let later context overwrite owned.
                if ref in index and index[ref]["_bucket"] == "owned_units":
                    continue
                if ref in index and bucket == "context_units":
                    continue
                index[ref] = {
                    **unit,
                    **meta,
                    "_bucket": bucket,
                    "_lookup": (
                        "frozen_plan_owned"
                        if bucket == "owned_units"
                        else "frozen_plan_context"
                    ),
                }
    return index


def _index_coverage(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for unit in manifest["units"]:
        index[unit["source_ref"]] = {
            **unit,
            "package_ordinal": None,
            "package_id": None,
            "protocol_document_sha256": manifest["protocol_document_sha256"],
            "protocol_version_id": manifest["protocol_version_id"],
            "snapshot_id": manifest["snapshot_id"],
            "_bucket": "coverage_manifest",
            "_lookup": "coverage_manifest",
        }
    return index


def _resolve_units(config: dict[str, Any]) -> list[ResolvedUnit]:
    plan_path = _repo_path(config["frozen_plan_path"])
    coverage_path = _repo_path(config["coverage_manifest_path"])
    assert plan_path is not None and coverage_path is not None
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    frozen_index = _index_frozen_plan(plan)
    coverage_index = _index_coverage(coverage)
    expected_package_identity = (
        config.get("expected_package_ordinal"),
        config.get("expected_package_id"),
    )
    lookup_order = list(
        config.get("unit_lookup")
        or ["frozen_plan_owned", "frozen_plan_context", "coverage_manifest"]
    )

    def pick(ref: str, role: str) -> dict[str, Any]:
        for source in lookup_order:
            if source in {"frozen_plan_owned", "frozen_plan_context"}:
                hit = frozen_index.get(ref)
                if hit is None:
                    continue
                if source == "frozen_plan_owned" and hit["_lookup"] != "frozen_plan_owned":
                    continue
                if source == "frozen_plan_context" and hit["_lookup"] != "frozen_plan_context":
                    continue
                return hit
            if source == "coverage_manifest":
                hit = coverage_index.get(ref)
                if hit is not None:
                    return hit
        raise SystemExit(f"{role} source_ref not found via {lookup_order}: {ref}")

    resolved: list[ResolvedUnit] = []
    seen: set[str] = set()
    owned_package_identity: tuple[int | None, str | None] | None = None
    for role, refs in (
        ("owned", list(config["owned_source_refs"])),
        ("attached", list(config.get("attached_source_refs") or [])),
    ):
        for ref in refs:
            if ref in seen:
                raise SystemExit(f"duplicate source_ref in config: {ref}")
            seen.add(ref)
            raw = pick(ref, role)
            if role == "owned":
                package_identity = (raw.get("package_ordinal"), raw.get("package_id"))
                if expected_package_identity != (None, None) and (
                    raw.get("_lookup") != "frozen_plan_owned"
                    or package_identity != expected_package_identity
                ):
                    raise SystemExit(
                        "owned source_ref package identity mismatch: "
                        f"{ref} resolved to {package_identity}, expected "
                        f"{expected_package_identity}"
                    )
                if owned_package_identity is None:
                    owned_package_identity = package_identity
                elif package_identity != owned_package_identity:
                    raise SystemExit(
                        "owned_source_refs span multiple frozen packages: "
                        f"{owned_package_identity} and {package_identity}"
                    )
            scopes = tuple(raw.get("phase_scopes") or ["unknown"])
            resolved.append(
                ResolvedUnit(
                    source_ref=ref,
                    role=role,
                    lookup=raw["_lookup"],
                    structure_unit_id=raw["structure_unit_id"],
                    source_span_ids=tuple(raw["source_span_ids"]),
                    member_source_refs=tuple(raw["member_source_refs"]),
                    excerpt=raw["excerpt"],
                    heading_path=tuple(raw["heading_path"]),
                    source_order=int(raw["source_order"]),
                    unit_kind=raw["unit_kind"],
                    table_context=(
                        dict(raw["table_context"])
                        if raw.get("table_context")
                        else None
                    ),
                    study_phase=str(raw.get("study_phase") or config["study_phase"]),
                    phase_scopes=scopes,
                    is_footnote_or_note=bool(raw.get("is_footnote_or_note") or False),
                    package_ordinal=raw.get("package_ordinal"),
                    package_id=raw.get("package_id"),
                    protocol_document_sha256=raw["protocol_document_sha256"],
                    protocol_version_id=raw["protocol_version_id"],
                    snapshot_id=raw["snapshot_id"],
                )
            )
    # Manifest contract requires original document order, not config listing order.
    return sorted(resolved, key=lambda row: (row.source_order, row.source_ref))


def _unit(row: ResolvedUnit) -> ProtocolStructureUnit:
    table_context = None
    if row.table_context is not None:
        ctx = row.table_context
        table_context = TableCellContext(
            table_path=tuple(ctx["table_path"]),
            row_index=int(ctx["row_index"]),
            column_index=int(ctx["column_index"]),
            member_cell_paths=[tuple(path) for path in ctx["member_cell_paths"]],
            row_headers=list(ctx.get("row_headers") or []),
            column_headers=list(ctx.get("column_headers") or []),
        )
    return ProtocolStructureUnit(
        structure_unit_id=row.structure_unit_id,
        source_ref=row.source_ref,
        member_source_refs=list(row.member_source_refs),
        source_span_ids=list(row.source_span_ids),
        unit_kind=StructureUnitKind(row.unit_kind),
        heading_path=list(row.heading_path),
        table_context=table_context,
        is_footnote_or_note=row.is_footnote_or_note,
        source_order=row.source_order,
        study_phase=StudyPhase(row.study_phase),
        phase_scopes=[PhaseScope(scope) for scope in row.phase_scopes],
        excerpt=row.excerpt,
    )


def _workflow(config: dict[str, Any]) -> list[KnownWorkflowStageTarget]:
    stages = config.get("workflow_stages") or [
        {
            "workflow_stage_id": "stage:baseline:1",
            "review_stage": "baseline",
            "display_name": "基线期",
            "visit_instance": "baseline-1",
        }
    ]
    return [
        KnownWorkflowStageTarget(
            workflow_stage_id=item["workflow_stage_id"],
            review_stage=ReviewStage(item["review_stage"]),
            display_name=item["display_name"],
            visit_instance=item.get("visit_instance"),
        )
        for item in stages
    ]


def _known_targets(
    config: dict[str, Any],
) -> tuple[list[KnownOfficialRuleTarget], list[KnownRequiredProcedureTarget]]:
    targets = config.get("known_targets") or {}
    excerpts_by_span: dict[str, str] = {}
    matrix_path = _repo_path(targets.get("source_path"))
    if matrix_path is not None:
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        for row in matrix.get("rows") or []:
            for anchor in row.get("source_anchors") or []:
                excerpt = str(anchor.get("verbatim_excerpt") or "")
                for span_id in anchor.get("source_span_ids") or []:
                    excerpts_by_span[str(span_id)] = excerpt

    def with_excerpts(item: dict[str, Any]) -> dict[str, Any]:
        if item.get("source_excerpts") or not excerpts_by_span:
            return item
        enriched = dict(item)
        try:
            enriched["source_excerpts"] = [
                excerpts_by_span[span_id]
                for span_id in enriched["source_span_ids"]
            ]
        except KeyError as exc:
            raise SystemExit(
                f"known target source span missing from source matrix: {exc.args[0]}"
            ) from exc
        return enriched

    official = [
        KnownOfficialRuleTarget.model_validate(with_excerpts(item))
        for item in targets.get("official_rules") or []
    ]
    procedures = [
        KnownRequiredProcedureTarget.model_validate(with_excerpts(item))
        for item in targets.get("required_procedures") or []
    ]
    return official, procedures


def _phase_view(
    manifest: ProtocolSectionCoverageManifest,
    config: dict[str, Any],
) -> object:
    phase_cfg = config.get("phase_applicability") or {}
    disposition = PhaseApplicabilityDisposition(
        phase_cfg.get("disposition") or "selected_phase_applicable"
    )
    scope = PhaseScope(phase_cfg.get("scope") or "phase_ii")
    rationale = str(
        phase_cfg.get("rationale")
        or "representative-group config scaffold selected_phase_applicable"
    )
    plan = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=max(64, len(manifest.units)),
        context_radius=1,
    )
    if not plan.packages:
        view = build_resolved_full_protocol_coverage_view(manifest, plan, [])
        return view.require_publishable()
    package = plan.packages[0]
    drafts: list[PhaseApplicabilityResolutionDraft] = []
    for index, target in enumerate(package.owned_units):
        span_index = package.frozen_source_span_ids.index(target.source_span_ids[0])
        drafts.append(
            PhaseApplicabilityResolutionDraft(
                unit_index=index,
                evidence=[
                    PhaseApplicabilityEvidenceDraft(
                        polarity=PhaseApplicabilityEvidencePolarity.SUPPORTS,
                        source_unit_indexes=[index],
                        source_span_indexes=[span_index],
                        excerpt=target.excerpt,
                        rationale=rationale,
                    )
                ],
                candidates=[
                    PhaseApplicabilityCandidateDraft(
                        scope=scope,
                        supporting_evidence_indexes=[0],
                        unresolved_evidence_indexes=[],
                    )
                ],
                final_disposition=disposition,
                rationale=rationale,
                unresolved_reason=None,
            )
        )
    resolutions = hydrate_phase_applicability_resolution(
        package,
        PhaseApplicabilityResolutionBatchDraft(results=drafts),
    )
    return build_resolved_full_protocol_coverage_view(
        manifest,
        plan,
        [resolutions],
    )


class TimedControlTransport:
    """Thin audit wrapper; product transport remains the only model caller."""

    def __init__(
        self,
        transport: OpenAICompatibleProtocolControlAgentTransport,
        progress_dir: Path,
    ) -> None:
        self.transport = transport
        self.progress_dir = progress_dir
        self.calls: list[dict[str, Any]] = []
        self.responses: list[dict[str, Any]] = []

    def _checkpoint(self) -> None:
        _write_json(self.progress_dir / "transport-calls.in-progress.json", self.calls)
        _write_json(
            self.progress_dir / "raw-responses.in-progress.json",
            [
                {
                    "kind": item["kind"],
                    "session_id": item["session_id"],
                    "text_sha256": _sha256_text(item["text"]),
                    "text_char_count": len(item["text"]),
                }
                for item in self.responses
            ],
        )

    def _call(
        self,
        kind: str,
        prompt: str,
        session_id: str | None = None,
    ) -> ProtocolControlAgentResponse:
        started = perf_counter()
        try:
            response = (
                self.transport.start(prompt=prompt)
                if session_id is None
                else self.transport.continue_session(
                    session_id=session_id,
                    prompt=prompt,
                )
            )
        except Exception as exc:
            self.calls.append(
                {
                    "kind": kind,
                    "status": "error",
                    "elapsed_seconds": round(perf_counter() - started, 6),
                    "prompt_char_count": len(prompt),
                    "prompt_sha256": _sha256_text(prompt),
                    "session_id": getattr(exc, "session_id", session_id),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            self._checkpoint()
            raise
        elapsed = round(perf_counter() - started, 6)
        self.calls.append(
            {
                "kind": kind,
                "status": "ok",
                "elapsed_seconds": elapsed,
                "prompt_char_count": len(prompt),
                "prompt_sha256": _sha256_text(prompt),
                "session_id": response.session_id,
                "output_char_count": len(response.text),
                "output_sha256": _sha256_text(response.text),
            }
        )
        self.responses.append(
            {
                "kind": kind,
                "session_id": response.session_id,
                "text": response.text,
            }
        )
        self._checkpoint()
        return response

    def start(self, *, prompt: str) -> ProtocolControlAgentResponse:
        return self._call("start", prompt)

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
    ) -> ProtocolControlAgentResponse:
        return self._call("repair", prompt, session_id)


def _promote_candidate_relations(
    relations: list[ControlCrossSourceRelation],
    *,
    candidate_id: str,
    control_id: str,
) -> list[ControlCrossSourceRelation]:
    """Replace only the current candidate endpoint with its published identity."""

    promoted: list[ControlCrossSourceRelation] = []
    for relation in relations:
        updates: dict[str, Any] = {}
        if (
            relation.left_target_kind
            == ControlRelationTargetKind.CONTROL_CANDIDATE
            and relation.left_target_id == candidate_id
        ):
            updates.update(
                left_target_kind=ControlRelationTargetKind.PROTOCOL_CONTROL,
                left_target_id=control_id,
            )
        if (
            relation.right_target_kind
            == ControlRelationTargetKind.CONTROL_CANDIDATE
            and relation.right_target_id == candidate_id
        ):
            updates.update(
                right_target_kind=ControlRelationTargetKind.PROTOCOL_CONTROL,
                right_target_id=control_id,
            )
        promoted.append(relation.model_copy(update=updates))
    return promoted


def _published_control_id(group_id: str, candidate_id: str) -> str:
    """Keep split candidates from one source independently publishable."""

    return f"pctrl-{group_id}-agent-{candidate_id}"


def _controls_from_candidates(
    *,
    rows: list[ResolvedUnit],
    candidates: list[Any],
    group_id: str,
) -> list[ProtocolReviewControl]:
    unit_to_ref = {row.structure_unit_id: row.source_ref for row in rows}
    controls: list[ProtocolReviewControl] = []
    ordinal = 1
    for candidate in candidates:
        semantics = candidate.semantics
        if semantics is None:
            continue
        source_units = list(candidate.frozen_structure_unit_ids)
        control_id = _published_control_id(
            group_id,
            candidate.control_candidate_id,
        )
        population = candidate.applicable_population or semantics.applicable_population
        if not population:
            continue
        flat_obligations = [
            atom
            for group in semantics.obligation_expression.groups
            for atom in group.atoms
        ]
        relations = _promote_candidate_relations(
            semantics.cross_source_relations,
            candidate_id=candidate.control_candidate_id,
            control_id=control_id,
        )
        controls.append(
            ProtocolReviewControl(
                protocol_control_id=control_id,
                display_ordinal=ordinal,
                protocol_version_id=candidate.protocol_version_id,
                study_phase=candidate.study_phase,
                title=candidate.title,
                applicable_population=population,
                applicability_expression=semantics.applicability_expression,
                trigger_expression=semantics.trigger_expression,
                obligation_expression=semantics.obligation_expression,
                exception_expression=semantics.exception_expression,
                obligations=flat_obligations,
                review_node_bindings=list(semantics.review_node_bindings),
                minimum_evidence=list(semantics.minimum_evidence),
                source_span_ids=list(candidate.source_span_ids),
                source_structure_unit_ids=source_units,
                cross_source_relations=relations,
                originating_candidate_id=candidate.control_candidate_id,
            )
        )
        ordinal += 1
    return controls


def _clinical_qc_scaffold(
    config: dict[str, Any],
    rows: list[ResolvedUnit],
    hydrated: Any | None,
) -> dict[str, Any]:
    checks_map: dict[str, list[str]] = dict(
        config.get("clinical_qc_checks_by_source_ref") or {}
    )
    row_reviews: list[dict[str, Any]] = []
    for row in rows:
        candidate_summaries: list[dict[str, Any]] = []
        if hydrated is not None:
            for candidate in hydrated.candidates:
                if row.structure_unit_id not in candidate.frozen_structure_unit_ids:
                    continue
                semantics = candidate.semantics
                time_atoms: list[dict[str, Any]] = []
                if semantics is not None:
                    for group in semantics.obligation_expression.groups:
                        for atom in group.atoms:
                            tc = atom.time_constraint
                            time_atoms.append(
                                {
                                    "kind": atom.kind.value
                                    if hasattr(atom.kind, "value")
                                    else str(atom.kind),
                                    "statement": atom.statement,
                                    "time_constraint": None
                                    if tc is None
                                    else tc.model_dump(mode="json"),
                                    "source_span_ids": list(atom.source_span_ids),
                                    "source_excerpts": list(atom.source_excerpts),
                                }
                            )
                candidate_summaries.append(
                    {
                        "control_candidate_id": candidate.control_candidate_id,
                        "title": candidate.title,
                        "obligation_time_atoms": time_atoms,
                        "exception_group_count": (
                            0
                            if semantics is None or semantics.exception_expression is None
                            else len(semantics.exception_expression.groups)
                        ),
                    }
                )
        pending_checks = {
            key: "pending_codex" for key in checks_map.get(row.source_ref, [])
        }
        row_reviews.append(
            {
                "source_ref": row.source_ref,
                "role": row.role,
                "lookup": row.lookup,
                "structure_unit_id": row.structure_unit_id,
                "frozen_excerpt": row.excerpt,
                "agent_candidates": candidate_summaries,
                "codex_clinical_checks": pending_checks,
                "codex_accepted": None,
            }
        )
    return {
        "schema_version": "phase5/representative-group-mtplx-control-replay-qc/v1",
        "task_id": config["task_id"],
        "worker": config.get("worker") or "worker_02",
        "group_id": config["group_id"],
        "claims_complete": False,
        "structured_control_deconstruction_accepted": False,
        "parent_clinical_acceptance": "pending_codex",
        "protocol_document_sha256": config["expected_protocol_sha256"],
        "owned_source_refs": list(config["owned_source_refs"]),
        "attached_source_refs": list(config.get("attached_source_refs") or []),
        "rows": row_reviews,
        "notes": list(config.get("notes") or [])
        + [
            "Agent wire/hydration/gate evidence only; Codex owns clinical QC.",
            "No clinical reasoning is copied into this harness.",
        ],
    }


def _out_dir(config: dict[str, Any], *, prepare: bool) -> Path:
    name = config.get("artifact_dir_name") or f"phase5-{config['group_id']}-replay"
    if prepare:
        return (
            ROOT
            / ".trellis"
            / "tasks"
            / "08-22-phase5-clinical-facts-profile"
            / "research"
            / "d001-ii-phase-closure"
            / "slice59n-prepare"
            / config["group_id"]
        )
    return ROOT / "artifacts" / name


def _build_single_batch_plan(
    *,
    manifest: ProtocolSectionCoverageManifest,
    owned_units: list[ProtocolStructureUnit],
    context_units: list[ProtocolStructureUnit],
    known_official_targets: list[KnownOfficialRuleTarget],
    known_procedure_targets: list[KnownRequiredProcedureTarget],
    workflow: list[KnownWorkflowStageTarget],
    pre_enrollment_structure_unit_ids: list[str],
    structural_only_structure_unit_ids: list[str],
    owned_visit_instance_by_structure_unit_id: dict[str, str],
    owned_procedure_semantic_families_by_structure_unit_id: dict[
        str, list[str]
    ],
    owned_required_action_kinds_by_structure_unit_id: dict[str, list[str]],
    owned_required_procedure_target_ids_by_structure_unit_id: dict[
        str, list[str]
    ],
    max_owned_units_per_batch: int,
) -> tuple[ProtocolControlBatchPlan, ProtocolControlDispositionBatch]:
    """Build one representative-group batch for the product runner/gate.

    Product ``plan_protocol_control_batches`` splits on exact heading-path runs.
    Cross-chapter groups therefore use this packing path. Attachments remain
    read-only prompt context and never enter the manifest ownership closure.
    """

    owned_ids = [unit.structure_unit_id for unit in owned_units]
    context_ids = [unit.structure_unit_id for unit in context_units]
    if set(owned_ids) & set(context_ids):
        raise SystemExit("owned and attached structure_unit_id sets must be disjoint")
    batch = ProtocolControlDispositionBatch(
        batch_id=stable_protocol_control_batch_id(
            manifest.manifest_id,
            1,
            owned_ids,
        ),
        coverage_manifest_id=manifest.manifest_id,
        protocol_version_id=manifest.protocol_version_id,
        study_phase=manifest.study_phase,
        batch_number=1,
        batch_total=1,
        priority_rank=max((unit.priority_rank for unit in owned_units), default=0),
        owned_units=list(owned_units),
        context_units=list(context_units),
        owned_structure_unit_ids=owned_ids,
        context_structure_unit_ids=context_ids,
        owned_source_span_ids=sorted(
            {span for unit in owned_units for span in unit.source_span_ids}
        ),
        context_source_span_ids=sorted(
            {span for unit in context_units for span in unit.source_span_ids}
        ),
        pre_enrollment_structure_unit_ids=list(
            pre_enrollment_structure_unit_ids
        ),
        structural_only_structure_unit_ids=list(structural_only_structure_unit_ids),
        owned_visit_instance_by_structure_unit_id=dict(
            owned_visit_instance_by_structure_unit_id
        ),
        owned_procedure_semantic_families_by_structure_unit_id={
            unit_id: list(families)
            for unit_id, families in (
                owned_procedure_semantic_families_by_structure_unit_id.items()
            )
        },
        owned_required_action_kinds_by_structure_unit_id={
            unit_id: list(action_kinds)
            for unit_id, action_kinds in (
                owned_required_action_kinds_by_structure_unit_id.items()
            )
        },
        owned_required_procedure_target_ids_by_structure_unit_id={
            unit_id: list(target_ids)
            for unit_id, target_ids in (
                owned_required_procedure_target_ids_by_structure_unit_id.items()
            )
        },
        known_official_targets=list(known_official_targets),
        known_procedure_targets=list(known_procedure_targets),
        known_workflow_stage_targets=list(workflow),
    )
    plan = ProtocolControlBatchPlan(
        plan_id="pcp-"
        + stable_protocol_control_batch_id(
            manifest.manifest_id,
            1,
            [batch.batch_id],
        ).removeprefix("pcb-"),
        coverage_manifest_id=manifest.manifest_id,
        protocol_version_id=manifest.protocol_version_id,
        study_phase=manifest.study_phase,
        max_owned_units_per_batch=max_owned_units_per_batch,
        context_radius=0,
        expected_structure_unit_ids=owned_ids,
        batches=[batch],
    )
    return plan, batch


def _build_pack(
    config: dict[str, Any],
    rows: list[ResolvedUnit],
) -> tuple[
    ProtocolSectionCoverageManifest,
    Any,
    Any,
    list[KnownWorkflowStageTarget],
    str,
    object,
    list[ResolvedUnit],
]:
    expected = config["expected_protocol_sha256"]
    if any(row.protocol_document_sha256 != expected for row in rows):
        bad = sorted(
            {
                row.source_ref
                for row in rows
                if row.protocol_document_sha256 != expected
            }
        )
        raise SystemExit(f"protocol SHA mismatch for refs: {bad}")

    owned_rows = [row for row in rows if row.role == "owned"]
    attached_rows = [row for row in rows if row.role == "attached"]
    if not owned_rows:
        raise SystemExit("owned_source_refs resolved empty")

    batching = config.get("batching") or {}
    mode = str(batching.get("mode") or "planner")
    ids = config["ids"]
    first = owned_rows[0]
    workflow = _workflow(config)
    known_official_targets, known_procedure_targets = _known_targets(config)
    pre_enrollment_refs = list(config.get("pre_enrollment_source_refs") or [])
    owned_by_ref = {row.source_ref: row for row in owned_rows}
    unknown_pre_enrollment = sorted(set(pre_enrollment_refs) - set(owned_by_ref))
    if unknown_pre_enrollment:
        raise SystemExit(
            "pre_enrollment_source_refs must be owned refs: "
            + ",".join(unknown_pre_enrollment)
        )
    pre_enrollment_structure_unit_ids = [
        owned_by_ref[row.source_ref].structure_unit_id
        for row in owned_rows
        if row.source_ref in set(pre_enrollment_refs)
    ]
    structural_only_refs = list(config.get("structural_only_source_refs") or [])
    unknown_structural_refs = sorted(set(structural_only_refs) - set(owned_by_ref))
    if unknown_structural_refs:
        raise SystemExit(
            "structural_only_source_refs must be owned refs: "
            + ",".join(unknown_structural_refs)
        )
    structural_only_structure_unit_ids = [
        owned_by_ref[row.source_ref].structure_unit_id
        for row in owned_rows
        if row.source_ref in set(structural_only_refs)
    ]
    owned_visit_instances_by_ref = {
        source_ref: visit_instance
        for source_ref, visit_instance in dict(
            config.get("owned_visit_instances_by_source_ref") or {}
        ).items()
        if visit_instance is not None
    }
    unknown_visit_refs = sorted(set(owned_visit_instances_by_ref) - set(owned_by_ref))
    if unknown_visit_refs:
        raise SystemExit(
            "owned_visit_instances_by_source_ref must be owned refs: "
            + ",".join(unknown_visit_refs)
        )
    owned_visit_instance_by_structure_unit_id = {
        owned_by_ref[source_ref].structure_unit_id: visit_instance
        for source_ref, visit_instance in owned_visit_instances_by_ref.items()
    }
    owned_procedure_families_by_ref = dict(
        config.get("owned_procedure_semantic_families_by_source_ref") or {}
    )
    unknown_family_refs = sorted(
        set(owned_procedure_families_by_ref) - set(owned_by_ref)
    )
    if unknown_family_refs:
        raise SystemExit(
            "owned_procedure_semantic_families_by_source_ref must be owned refs: "
            + ",".join(unknown_family_refs)
        )
    owned_procedure_semantic_families_by_structure_unit_id = {
        owned_by_ref[source_ref].structure_unit_id: list(families)
        for source_ref, families in owned_procedure_families_by_ref.items()
    }
    owned_action_kinds_by_ref = dict(
        config.get("owned_required_action_kinds_by_source_ref") or {}
    )
    non_control_refs = {
        source_ref
        for source_ref, disposition in dict(
            config.get("expected_disposition_by_source_ref") or {}
        ).items()
        if disposition in {"non_enrollment_execution", "supporting_or_supplement"}
    }
    unknown_action_refs = sorted(
        set(owned_action_kinds_by_ref) - set(owned_by_ref)
    )
    if unknown_action_refs:
        raise SystemExit(
            "owned_required_action_kinds_by_source_ref must be owned refs: "
            + ",".join(unknown_action_refs)
        )
    owned_required_action_kinds_by_structure_unit_id = {
        row.structure_unit_id: sorted(
            {
                *(
                    ()
                    if row.source_ref in non_control_refs
                    else detect_required_action_kinds(row.excerpt)
                ),
                *owned_action_kinds_by_ref.get(row.source_ref, ()),
            }
        )
        for row in owned_rows
        if (
            row.source_ref not in non_control_refs
            and detect_required_action_kinds(row.excerpt)
        )
        or owned_action_kinds_by_ref.get(row.source_ref)
    }
    owned_target_ids_by_ref = dict(
        config.get("owned_required_procedure_target_ids_by_source_ref") or {}
    )
    unknown_target_refs = sorted(set(owned_target_ids_by_ref) - set(owned_by_ref))
    if unknown_target_refs:
        raise SystemExit(
            "owned_required_procedure_target_ids_by_source_ref must be owned refs: "
            + ",".join(unknown_target_refs)
        )
    owned_required_procedure_target_ids_by_structure_unit_id = {
        owned_by_ref[source_ref].structure_unit_id: list(target_ids)
        for source_ref, target_ids in owned_target_ids_by_ref.items()
    }
    workflow_stages = [
        WorkflowStage(
            workflow_stage_id=item.workflow_stage_id,
            stage=item.review_stage,
            display_name=item.display_name,
            visit_instance=item.visit_instance,
        )
        for item in workflow
    ]

    if mode == "planner":
        if attached_rows:
            raise SystemExit(
                "batching.mode=planner cannot attach cross-chapter refs; "
                "use single_batch_with_attachments"
            )
        units = [_unit(row) for row in owned_rows]
        manifest = ProtocolSectionCoverageManifest(
            manifest_id=ids["manifest_id"],
            protocol_version_id=first.protocol_version_id,
            protocol_document_sha256=first.protocol_document_sha256,
            study_phase=StudyPhase(config["study_phase"]),
            snapshot_id=first.snapshot_id,
            units=units,
            dispositions=[],
            claims_full_coverage=False,
        )
        plan = plan_protocol_control_batches(
            manifest,
            max_owned_units_per_batch=max(64, len(units)),
            workflow_stages=workflow_stages,
        )
        if len(plan.batches) != 1:
            raise SystemExit(
                f"planner expected one control batch, got {len(plan.batches)}; "
                "use batching.mode=single_batch_with_attachments for multi-heading groups"
            )
        batch = plan.batches[0]
        if known_official_targets or known_procedure_targets:
            batch = batch.model_copy(
                update={
                    "known_official_targets": list(known_official_targets),
                    "known_procedure_targets": list(known_procedure_targets),
                }
            )
            batch = ProtocolControlDispositionBatch.model_validate(
                batch.model_dump(mode="json")
            )
            plan = plan.model_copy(update={"batches": [batch]})
            plan = ProtocolControlBatchPlan.model_validate(plan.model_dump(mode="json"))
        pack_rows = owned_rows
    elif mode == "single_batch_with_known_targets":
        units = [_unit(row) for row in owned_rows]
        context_units = [_unit(row) for row in attached_rows]
        manifest = ProtocolSectionCoverageManifest(
            manifest_id=ids["manifest_id"],
            protocol_version_id=first.protocol_version_id,
            protocol_document_sha256=first.protocol_document_sha256,
            study_phase=StudyPhase(config["study_phase"]),
            snapshot_id=first.snapshot_id,
            units=units,
            dispositions=[],
            claims_full_coverage=False,
        )
        plan, batch = _build_single_batch_plan(
            manifest=manifest,
            owned_units=units,
            context_units=context_units,
            known_official_targets=known_official_targets,
            known_procedure_targets=known_procedure_targets,
            workflow=workflow,
            pre_enrollment_structure_unit_ids=pre_enrollment_structure_unit_ids,
            structural_only_structure_unit_ids=structural_only_structure_unit_ids,
            owned_visit_instance_by_structure_unit_id=(
                owned_visit_instance_by_structure_unit_id
            ),
            owned_procedure_semantic_families_by_structure_unit_id=(
                owned_procedure_semantic_families_by_structure_unit_id
            ),
            owned_required_action_kinds_by_structure_unit_id=(
                owned_required_action_kinds_by_structure_unit_id
            ),
            owned_required_procedure_target_ids_by_structure_unit_id=(
                owned_required_procedure_target_ids_by_structure_unit_id
            ),
            max_owned_units_per_batch=max(64, len(units)),
        )
        pack_rows = sorted(
            owned_rows + attached_rows,
            key=lambda row: (row.source_order, row.source_ref),
        )
    elif mode == "single_batch_with_attachments":
        units = [_unit(row) for row in owned_rows]
        context_units = [_unit(row) for row in attached_rows]
        manifest = ProtocolSectionCoverageManifest(
            manifest_id=ids["manifest_id"],
            protocol_version_id=first.protocol_version_id,
            protocol_document_sha256=first.protocol_document_sha256,
            study_phase=StudyPhase(config["study_phase"]),
            snapshot_id=first.snapshot_id,
            units=units,
            dispositions=[],
            claims_full_coverage=False,
        )
        plan, batch = _build_single_batch_plan(
            manifest=manifest,
            owned_units=units,
            context_units=context_units,
            known_official_targets=known_official_targets,
            known_procedure_targets=known_procedure_targets,
            workflow=workflow,
            pre_enrollment_structure_unit_ids=pre_enrollment_structure_unit_ids,
            structural_only_structure_unit_ids=structural_only_structure_unit_ids,
            owned_visit_instance_by_structure_unit_id=(
                owned_visit_instance_by_structure_unit_id
            ),
            owned_procedure_semantic_families_by_structure_unit_id=(
                owned_procedure_semantic_families_by_structure_unit_id
            ),
            owned_required_action_kinds_by_structure_unit_id=(
                owned_required_action_kinds_by_structure_unit_id
            ),
            owned_required_procedure_target_ids_by_structure_unit_id=(
                owned_required_procedure_target_ids_by_structure_unit_id
            ),
            max_owned_units_per_batch=max(64, len(units)),
        )
        pack_rows = owned_rows + attached_rows
        pack_rows = sorted(pack_rows, key=lambda row: (row.source_order, row.source_ref))
    else:
        raise SystemExit(f"unsupported batching.mode: {mode!r}")

    phase_view = _phase_view(manifest, config)
    prompt = build_protocol_control_agent_prompt(batch)
    return manifest, plan, batch, workflow, prompt, phase_view, pack_rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Config-driven representative-group ProtocolControl replay"
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to representative_group_*.v1.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve/pack only; write prepare evidence under research/slice59n-prepare",
    )
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()
    config = _load_config(config_path)
    rows = _resolve_units(config)
    prepare_issues = evaluate_prepare_source_closure(
        group_id=str(config["group_id"]),
        rows=[
            {
                "source_ref": row.source_ref,
                "role": row.role,
                "lookup": row.lookup,
                "structure_unit_id": row.structure_unit_id,
                "source_span_ids": list(row.source_span_ids),
                "excerpt": row.excerpt,
                "study_phase": row.study_phase,
            }
            for row in rows
        ],
        owned_source_refs=list(config["owned_source_refs"]),
        attached_source_refs=list(config.get("attached_source_refs") or []),
        study_phase=str(config["study_phase"]),
    )
    blocked = first_reject(prepare_issues)
    if blocked is not None:
        raise SystemExit(blocked.as_wire_message())
    manifest, plan, batch, workflow, prompt, phase_view, pack_rows = _build_pack(
        config, rows
    )

    out_dir = _out_dir(config, prepare=args.dry_run)
    out_dir.mkdir(parents=True, exist_ok=True)
    execution_dir = out_dir / "execution"
    execution_dir.mkdir(parents=True, exist_ok=True)

    plan_path = _repo_path(config["frozen_plan_path"])
    coverage_path = _repo_path(config["coverage_manifest_path"])
    assert plan_path is not None and coverage_path is not None
    parent_qc_path = _repo_path(config.get("parent_phase_qc_path"))

    provenance = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task_id": config["task_id"],
        "worker": config.get("worker") or "worker_02",
        "group_id": config["group_id"],
        "mode": "dry_run_prepare" if args.dry_run else "live_mtplx_runner",
        "replay_mode": "product_protocol_control_agent_runner_mtplx",
        "config_path": str(config_path.relative_to(ROOT))
        if config_path.is_relative_to(ROOT)
        else str(config_path),
        "config_sha256": _sha256_file(config_path),
        "frozen_plan_path": str(plan_path.relative_to(ROOT)),
        "frozen_plan_sha256": _sha256_file(plan_path),
        "coverage_manifest_path": str(coverage_path.relative_to(ROOT)),
        "coverage_manifest_sha256": _sha256_file(coverage_path),
        "parent_phase_qc_path": None
        if parent_qc_path is None
        else str(parent_qc_path.relative_to(ROOT)),
        "parent_phase_qc_sha256": None
        if parent_qc_path is None
        else _sha256_file(parent_qc_path),
        "protocol_document_sha256": config["expected_protocol_sha256"],
        "owned_source_refs": list(config["owned_source_refs"]),
        "attached_source_refs": list(config.get("attached_source_refs") or []),
        "coverage_manifest_id": manifest.manifest_id,
        "control_batch_id": batch.batch_id,
        "control_plan_id": plan.plan_id,
        "prompt_char_count": len(prompt),
        "prompt_sha256": _sha256_text(prompt),
        "prompt_template_sha256": protocol_control_agent_prompt_template_sha256(
            DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE
        ),
        "claims_complete": False,
    }
    _write_json(out_dir / "freeze_provenance.json", provenance)
    _write_json(
        out_dir / "source_rows.json",
        [
            {
                "source_ref": row.source_ref,
                "role": row.role,
                "lookup": row.lookup,
                "structure_unit_id": row.structure_unit_id,
                "source_span_ids": list(row.source_span_ids),
                "excerpt": row.excerpt,
                "package_ordinal": row.package_ordinal,
                "package_id": row.package_id,
                "heading_path": list(row.heading_path),
                "unit_kind": row.unit_kind,
            }
            for row in pack_rows
        ],
    )
    _write_json(execution_dir / "batch.json", batch.model_dump(mode="json"))
    _write_json(
        execution_dir / "prompt-meta.json",
        {
            "prompt_char_count": len(prompt),
            "prompt_sha256": _sha256_text(prompt),
            "batching_mode": (config.get("batching") or {}).get("mode") or "planner",
            "owned_count": sum(1 for row in pack_rows if row.role == "owned"),
            "attached_count": sum(1 for row in pack_rows if row.role == "attached"),
            "context_structure_unit_ids": list(batch.context_structure_unit_ids),
        },
    )
    # Keep prompt text for prepare/debug; live runs also keep it for audit.
    (execution_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    if args.dry_run:
        clinical_qc = _clinical_qc_scaffold(config, pack_rows, None)
        clinical_qc["gate"] = {
            "accepted": False,
            "skipped": True,
            "reason": "dry-run prepare only; publication gate requires hydrated Agent output",
        }
        clinical_qc["runner_status"] = "dry_run"
        clinical_qc["reject_gates"] = {
            "prepare_accepted": True,
            "hydrated_skipped": True,
            "reason": "prepare source closure passed; hydrated reject gates require live Agent output",
        }
        _write_json(out_dir / "clinical-qc.json", clinical_qc)
        summary = {
            "task_id": config["task_id"],
            "worker": config.get("worker") or "worker_02",
            "group_id": config["group_id"],
            "mode": "dry_run_prepare",
            "batching_mode": (config.get("batching") or {}).get("mode") or "planner",
            "owned_count": sum(1 for row in pack_rows if row.role == "owned"),
            "attached_count": sum(1 for row in pack_rows if row.role == "attached"),
            "unit_count": len(pack_rows),
            "lookup_counts": {
                key: sum(1 for row in pack_rows if row.lookup == key)
                for key in sorted({row.lookup for row in pack_rows})
            },
            "control_batch_id": batch.batch_id,
            "prompt_char_count": len(prompt),
            "prompt_sha256": _sha256_text(prompt),
            "out_dir": str(out_dir.relative_to(ROOT)),
            "claims_complete": False,
        }
        _write_json(out_dir / "replay-summary.json", summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    runner_cfg = config.get("runner") or {}
    transport = OpenAICompatibleProtocolControlAgentTransport(
        timeout=float(runner_cfg.get("timeout_seconds") or 7200.0)
    )
    timed = TimedControlTransport(transport, execution_dir)
    transport_identity = {
        "backend": transport.backend,
        "provider": transport.provider,
        "base_url": transport.base_url,
        "model": transport.model,
        "reasoning_effort": transport.reasoning_effort,
        "max_tokens": transport.max_tokens,
        "temperature": transport.temperature,
        "timeout": transport.timeout,
        "max_retries": transport.max_retries,
        "response_format_sha256": transport.response_format_sha256,
        "uses_control_response_format": transport.uses_control_response_format,
        "transport_type": (
            "app.agents.protocol_control_agent_transport."
            "OpenAICompatibleProtocolControlAgentTransport"
        ),
    }
    provenance["transport_identity"] = transport_identity
    _write_json(out_dir / "freeze_provenance.json", provenance)

    allowed_spans = sorted(
        {
            *(span for unit in batch.owned_units for span in unit.source_span_ids),
        }
    )

    def validate_for_publication(hydrated_output: Any) -> None:
        candidate_by_id = {
            candidate.control_candidate_id: candidate
            for candidate in hydrated_output.candidates
        }
        candidate_controls = _controls_from_candidates(
            rows=pack_rows,
            candidates=hydrated_output.candidates,
            group_id=config["group_id"],
        )
        control_to_candidate = {
            control.protocol_control_id: control.originating_candidate_id
            for control in candidate_controls
        }
        catalog = PublishedProtocolControlCatalog(
            catalog_id=config["ids"]["catalog_id"],
            protocol_version_id=pack_rows[0].protocol_version_id,
            protocol_document_sha256=pack_rows[0].protocol_document_sha256,
            study_phase=StudyPhase(config["study_phase"]),
            coverage_manifest_id=manifest.manifest_id,
            allowed_source_span_ids=allowed_spans,
            controls=candidate_controls,
        )
        report = check_protocol_control_publication(
            manifest,
            catalog,
            plan,
            [hydrated_output],
            candidates=[],
            workflow_stage_targets=workflow,
            phase_applicability_view=phase_view,
        )
        # Publication-green is not enough: reject source/phase/logic defects.
        clinical_issues = evaluate_hydrated_agent_output(
                group_id=str(config["group_id"]),
                study_phase=str(config["study_phase"]),
                rows=[
                    {
                        "source_ref": row.source_ref,
                        "role": row.role,
                        "lookup": row.lookup,
                        "structure_unit_id": row.structure_unit_id,
                        "source_span_ids": list(row.source_span_ids),
                        "excerpt": row.excerpt,
                        "study_phase": row.study_phase,
                    }
                    for row in pack_rows
                ],
                hydrated=hydrated_output.model_dump(mode="json"),
                allowed_structure_unit_ids=list(batch.owned_structure_unit_ids),
                required_candidate_source_refs=list(
                    config.get("required_candidate_source_refs") or []
                ),
                forbidden_candidate_source_refs=list(
                    config.get("forbidden_candidate_source_refs") or []
                ),
                expected_disposition_by_source_ref=dict(
                    config.get("expected_disposition_by_source_ref") or {}
                ),
                expected_workflow_stage_ids_by_source_ref=dict(
                    config.get("expected_workflow_stage_ids_by_source_ref") or {}
                ),
                candidate_forbidden_markers_by_source_ref=dict(
                    config.get("candidate_forbidden_markers_by_source_ref") or {}
                ),
                candidate_required_markers_by_source_ref=dict(
                    config.get("candidate_required_markers_by_source_ref") or {}
                ),
            )
        validation_error = _replay_validation_error(
            publication_report=report,
            clinical_issues=clinical_issues,
            candidate_by_id=candidate_by_id,
            control_to_candidate=control_to_candidate,
            default_structure_unit_ids=list(batch.owned_structure_unit_ids),
        )
        if validation_error is not None:
            raise validation_error

    started = perf_counter()
    result = ProtocolControlAgentRunner(
        max_transport_retries=int(runner_cfg.get("max_transport_retries", 1)),
        max_schema_repairs=int(runner_cfg.get("max_schema_repairs", 2)),
    ).run(batch, timed, output_validator=validate_for_publication)
    elapsed = round(perf_counter() - started, 6)

    hydrated = result.final_output
    gate_report: dict[str, Any]
    controls: list[ProtocolReviewControl] = []
    if hydrated is None:
        gate_report = {
            "accepted": False,
            "skipped": True,
            "reason": "runner did not hydrate a final output",
            "runner_status": result.status,
        }
    else:
        controls = _controls_from_candidates(
            rows=pack_rows,
            candidates=hydrated.candidates,
            group_id=config["group_id"],
        )
        catalog = PublishedProtocolControlCatalog(
            catalog_id=config["ids"]["catalog_id"],
            protocol_version_id=pack_rows[0].protocol_version_id,
            protocol_document_sha256=pack_rows[0].protocol_document_sha256,
            study_phase=StudyPhase(config["study_phase"]),
            coverage_manifest_id=manifest.manifest_id,
            allowed_source_span_ids=allowed_spans,
            controls=controls,
        )
        report = check_protocol_control_publication(
            manifest,
            catalog,
            plan,
            [hydrated],
            candidates=[],
            workflow_stage_targets=workflow,
            phase_applicability_view=phase_view,
        )
        gate_report = {
            "accepted": report.accepted,
            "gate_version": report.gate_version,
            "control_count": len(controls),
            "candidate_count": len(hydrated.candidates),
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "entity_id": issue.entity_id,
                }
                for issue in report.issues
            ],
        }

    _write_json(execution_dir / "runner-result.json", result.model_dump(mode="json"))
    _write_json(execution_dir / "transport-calls.json", timed.calls)
    _write_json(
        execution_dir / "raw-responses.json",
        [
            {
                "kind": item["kind"],
                "session_id": item["session_id"],
                "text_sha256": _sha256_text(item["text"]),
                "text_char_count": len(item["text"]),
                "text": item["text"],
            }
            for item in timed.responses
        ],
    )
    if timed.responses:
        _write_json(
            execution_dir / "conversation-history.json",
            list(transport.history(result.session_id)),
        )
    (execution_dir / "transport-calls.in-progress.json").unlink(missing_ok=True)
    (execution_dir / "raw-responses.in-progress.json").unlink(missing_ok=True)

    if hydrated is not None:
        _write_json(out_dir / "hydrated-batch.json", hydrated.model_dump(mode="json"))
        _write_json(
            out_dir / "agent-controls.json",
            {
                "schema_version": "phase5/representative-group-mtplx-agent-controls/v1",
                "controls": [item.model_dump(mode="json") for item in controls],
            },
        )
    _write_json(out_dir / "gate-results.json", gate_report)
    clinical_qc = _clinical_qc_scaffold(config, pack_rows, hydrated)
    clinical_qc["gate"] = gate_report
    clinical_qc["runner_status"] = result.status
    clinical_qc["attempt_outcomes"] = [item.outcome for item in result.attempts]
    clinical_qc["raw_output_sha256"] = [
        item.raw_output_sha256 for item in result.attempts
    ]
    clinical_reject = evaluate_hydrated_agent_output(
        group_id=str(config["group_id"]),
        study_phase=str(config["study_phase"]),
        rows=[
            {
                "source_ref": row.source_ref,
                "role": row.role,
                "lookup": row.lookup,
                "structure_unit_id": row.structure_unit_id,
                "source_span_ids": list(row.source_span_ids),
                "excerpt": row.excerpt,
                "study_phase": row.study_phase,
            }
            for row in pack_rows
        ],
        hydrated=None if hydrated is None else hydrated.model_dump(mode="json"),
        allowed_structure_unit_ids=list(batch.owned_structure_unit_ids),
        required_candidate_source_refs=list(
            config.get("required_candidate_source_refs") or []
        ),
        forbidden_candidate_source_refs=list(
            config.get("forbidden_candidate_source_refs") or []
        ),
        expected_disposition_by_source_ref=dict(
            config.get("expected_disposition_by_source_ref") or {}
        ),
        expected_workflow_stage_ids_by_source_ref=dict(
            config.get("expected_workflow_stage_ids_by_source_ref") or {}
        ),
        candidate_forbidden_markers_by_source_ref=dict(
            config.get("candidate_forbidden_markers_by_source_ref") or {}
        ),
        candidate_required_markers_by_source_ref=dict(
            config.get("candidate_required_markers_by_source_ref") or {}
        ),
    )
    clinical_qc["reject_gates"] = {
        "accepted": not clinical_reject,
        "issues": [
            {
                "code": issue.code,
                "message": issue.message,
                "source_refs": list(issue.source_refs),
                "structure_unit_ids": list(issue.structure_unit_ids),
            }
            for issue in clinical_reject
        ],
    }
    _write_json(out_dir / "clinical-qc.json", clinical_qc)

    publication_gate_accepted = bool(gate_report.get("accepted"))
    deterministic_clinical_gate_accepted = not clinical_reject
    technical_replay_accepted = _technical_replay_accepted(
        hydrated=hydrated,
        publication_gate_accepted=publication_gate_accepted,
        clinical_issues=clinical_reject,
    )
    summary = {
        "task_id": config["task_id"],
        "worker": config.get("worker") or "worker_02",
        "group_id": config["group_id"],
        "mode": "live_mtplx_runner",
        "batching_mode": (config.get("batching") or {}).get("mode") or "planner",
        "elapsed_seconds": elapsed,
        "runner_status": result.status,
        "session_id": result.session_id,
        "attempt_count": len(result.attempts),
        "attempt_outcomes": [item.outcome for item in result.attempts],
        "transport_call_count": len(timed.calls),
        "raw_response_count": len(timed.responses),
        "hydrated": hydrated is not None,
        "candidate_count": 0 if hydrated is None else len(hydrated.candidates),
        "control_count": len(controls),
        "publication_gate_accepted": publication_gate_accepted,
        "deterministic_clinical_gate_accepted": deterministic_clinical_gate_accepted,
        "technical_replay_accepted": technical_replay_accepted,
        "parent_clinical_acceptance": "pending_codex",
        "gate_accepted": technical_replay_accepted,
        "owned_count": sum(1 for row in pack_rows if row.role == "owned"),
        "attached_count": sum(1 for row in pack_rows if row.role == "attached"),
        "claims_complete": False,
        "structured_control_deconstruction_accepted": False,
        "transport_identity": transport_identity,
        "protocol_document_sha256": config["expected_protocol_sha256"],
        "out_dir": str(out_dir.relative_to(ROOT)),
    }
    _write_json(out_dir / "replay-summary.json", summary)
    handoff = "\n".join(
        [
            f"# Compact Handoff: {config['group_id']} control Agent replay",
            "",
            f"- Task: `{config['task_id']}` / `{config.get('worker')}`",
            f"- Group: `{config['group_id']}`",
            "- Replay mode: product ProtocolControlAgentRunner + control Schema transport",
            f"- Runner status: `{result.status}`",
            f"- Publication gate accepted: `{publication_gate_accepted}`",
            f"- Deterministic clinical gate accepted: `{deterministic_clinical_gate_accepted}`",
            f"- Technical replay accepted: `{technical_replay_accepted}`",
            "- Parent clinical acceptance: `pending_codex`",
            "- claims_complete: `false`",
            "",
            "## Units",
            *[
                f"- `{row.role}` `{row.source_ref}` via `{row.lookup}`: {row.excerpt[:120]}"
                for row in pack_rows
            ],
            "",
        ]
    )
    (out_dir / "compact-handoff.md").write_text(handoff, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    deterministic_acceptance = (
        result.status == "已解析"
        and gate_report.get("accepted") is True
        and not clinical_reject
    )
    return 0 if deterministic_acceptance else 2


if __name__ == "__main__":
    raise SystemExit(main())
