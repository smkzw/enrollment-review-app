#!/usr/bin/env python3
"""Real MTPLX ProtocolControlAgent replay for frozen D001 II Table 5 rows.

Worker 03 / phase5-slice59m: invoke product ProtocolControlAgentRunner through
OpenAICompatibleProtocolControlAgentTransport (strict control Schema, MTPLX
medium). Deterministic fixture construction is not a substitute.

Writes only under artifacts/phase5-slice59m-*. Does not overwrite slice59l.
claims_complete remains false; Codex owns clinical QC.

Superseded for new representative-group work by
``slice59n_representative_group_control_replay.py`` +
``configs/representative_group_*.v1.json`` (keep this file as the accepted
slice59m artifact producer).
"""

from __future__ import annotations

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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
    KnownWorkflowStageTarget,
    ProtocolReviewControl,
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    PublishedProtocolControlCatalog,
    StructureUnitKind,
    TableCellContext,
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
from app.protocols.protocol_control_planning import (  # noqa: E402
    plan_protocol_control_batches,
)

EXPECTED_SHA = (
    "362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98"
)
FROZEN_PLAN = (
    ROOT
    / "artifacts"
    / "phase5-slice59i-d001-phase-table-caption-rebaseline-20260827"
    / "frozen_phase_plan.json"
)
PARENT_PHASE_QC = (
    ROOT
    / "artifacts"
    / "phase5-slice59j-d001-packages63-65-parent-qc-20260827"
    / "clinical-qc.json"
)
OUT_DIR = (
    ROOT
    / "artifacts"
    / "phase5-slice59m-d001-table5-mtplx-control-replay-bounded-repair-20260827"
)

REPRESENTATIVE_REFS = (
    "body.t10.r1",
    "body.t10.r3",
    "body.t10.r4",
    "body.t10.r7",
)

TASK_ID = "phase5-slice59m-20260827"
WORKER = "worker_03"


@dataclass(frozen=True)
class FrozenRow:
    source_ref: str
    structure_unit_id: str
    source_span_ids: tuple[str, ...]
    member_source_refs: tuple[str, ...]
    excerpt: str
    heading_path: tuple[str, ...]
    source_order: int
    unit_kind: str
    table_context: dict[str, Any]
    package_ordinal: int
    package_id: str
    protocol_document_sha256: str
    protocol_version_id: str
    snapshot_id: str
    coverage_manifest_id: str


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


def _load_rows() -> list[FrozenRow]:
    plan = json.loads(FROZEN_PLAN.read_text(encoding="utf-8"))
    by_ref: dict[str, FrozenRow] = {}
    for pkg in plan["packages"]:
        if pkg["package_ordinal"] not in {63, 64, 65}:
            continue
        for unit in pkg["owned_units"]:
            ref = unit["source_ref"]
            if ref not in REPRESENTATIVE_REFS:
                continue
            by_ref[ref] = FrozenRow(
                source_ref=ref,
                structure_unit_id=unit["structure_unit_id"],
                source_span_ids=tuple(unit["source_span_ids"]),
                member_source_refs=tuple(unit["member_source_refs"]),
                excerpt=unit["excerpt"],
                heading_path=tuple(unit["heading_path"]),
                source_order=int(unit["source_order"]),
                unit_kind=unit["unit_kind"],
                table_context=dict(unit["table_context"]),
                package_ordinal=int(pkg["package_ordinal"]),
                package_id=pkg["package_id"],
                protocol_document_sha256=pkg["protocol_document_sha256"],
                protocol_version_id=pkg["protocol_version_id"],
                snapshot_id=pkg["snapshot_id"],
                coverage_manifest_id=pkg["coverage_manifest_id"],
            )
    missing = [ref for ref in REPRESENTATIVE_REFS if ref not in by_ref]
    if missing:
        raise SystemExit(f"frozen rows missing: {missing}")
    return [by_ref[ref] for ref in REPRESENTATIVE_REFS]


def _unit(row: FrozenRow) -> ProtocolStructureUnit:
    ctx = row.table_context
    return ProtocolStructureUnit(
        structure_unit_id=row.structure_unit_id,
        source_ref=row.source_ref,
        member_source_refs=list(row.member_source_refs),
        source_span_ids=list(row.source_span_ids),
        unit_kind=StructureUnitKind(row.unit_kind),
        heading_path=list(row.heading_path),
        table_context=TableCellContext(
            table_path=tuple(ctx["table_path"]),
            row_index=int(ctx["row_index"]),
            column_index=int(ctx["column_index"]),
            member_cell_paths=[tuple(path) for path in ctx["member_cell_paths"]],
            row_headers=list(ctx.get("row_headers") or []),
            column_headers=list(ctx.get("column_headers") or []),
        ),
        source_order=row.source_order,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.UNKNOWN],
        excerpt=row.excerpt,
    )


def _workflow() -> list[KnownWorkflowStageTarget]:
    return [
        KnownWorkflowStageTarget(
            workflow_stage_id="stage:baseline:1",
            review_stage=ReviewStage.BASELINE,
            display_name="基线期",
            visit_instance="baseline-1",
        )
    ]


def _phase_view(manifest: ProtocolSectionCoverageManifest) -> object:
    """Reuse accepted package-64 selected_phase_applicable without rewriting scopes."""

    plan = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=64,
        context_radius=1,
    )
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
                        rationale=(
                            "slice59j package-64 accepted selected_phase_applicable "
                            "for frozen Table 5 representative; scopes stay UNKNOWN"
                        ),
                    )
                ],
                candidates=[
                    PhaseApplicabilityCandidateDraft(
                        scope=PhaseScope.PHASE_II,
                        supporting_evidence_indexes=[0],
                        unresolved_evidence_indexes=[],
                    )
                ],
                final_disposition=PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE,
                rationale="accepted package-64 Table 5 phase applicability",
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


def _controls_from_candidates(
    *,
    rows: list[FrozenRow],
    candidates: list[Any],
) -> list[ProtocolReviewControl]:
    unit_to_ref = {row.structure_unit_id: row.source_ref for row in rows}
    controls: list[ProtocolReviewControl] = []
    ordinal = 1
    for candidate in candidates:
        semantics = candidate.semantics
        if semantics is None:
            continue
        source_units = list(candidate.frozen_structure_unit_ids)
        refs = [unit_to_ref.get(unit_id, unit_id) for unit_id in source_units]
        slug = "-".join(ref.replace(".", "-") for ref in refs)
        population = candidate.applicable_population or semantics.applicable_population
        if not population:
            continue
        flat_obligations = [
            atom
            for group in semantics.obligation_expression.groups
            for atom in group.atoms
        ]
        controls.append(
            ProtocolReviewControl(
                protocol_control_id=f"pctrl-slice59m-agent-{slug}",
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
                cross_source_relations=list(semantics.cross_source_relations),
                originating_candidate_id=candidate.control_candidate_id,
            )
        )
        ordinal += 1
    return controls


def _clinical_qc_scaffold(
    rows: list[FrozenRow],
    hydrated: Any | None,
) -> dict[str, Any]:
    by_unit = {row.structure_unit_id: row for row in rows}
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
                        "obligation_periods": [
                            {
                                "statement": atom.statement,
                                "period": (
                                    None
                                    if atom.prospective_period is None
                                    else atom.prospective_period.period.value
                                ),
                            }
                            for group in semantics.obligation_expression.groups
                            for atom in group.atoms
                        ],
                        "exception_group_count": (
                            0
                            if semantics is None or semantics.exception_expression is None
                            else len(semantics.exception_expression.groups)
                        ),
                    }
                )
        row_reviews.append(
            {
                "source_ref": row.source_ref,
                "structure_unit_id": row.structure_unit_id,
                "frozen_excerpt": row.excerpt,
                "agent_candidates": candidate_summaries,
                "codex_clinical_checks": {
                    "first_dose_anchor": None,
                    "study_period_through_completion": "pending_codex",
                    "longer_of_selection": None
                    if row.source_ref != "body.t10.r4"
                    else "pending_codex",
                    "clearance_24_to_6_substitute": None
                    if row.source_ref != "body.t10.r3"
                    else "pending_codex",
                    "herbal_local_exception": None
                    if row.source_ref != "body.t10.r7"
                    else "pending_codex",
                    "fixed_first_dose_window": None
                    if row.source_ref != "body.t10.r1"
                    else "pending_codex",
                },
                "codex_accepted": None,
            }
        )
        _ = by_unit
    return {
        "schema_version": "phase5/d001-table5-mtplx-control-replay-qc/v1",
        "task_id": TASK_ID,
        "worker": WORKER,
        "claims_complete": False,
        "structured_control_deconstruction_accepted": False,
        "parent_clinical_acceptance": "pending_codex",
        "protocol_document_sha256": EXPECTED_SHA,
        "representative_source_refs": list(REPRESENTATIVE_REFS),
        "rows": row_reviews,
        "notes": [
            "Agent wire/hydration/gate evidence only; Codex must QC against frozen Table 5 excerpts.",
            "Deterministic slice59l fixture is supporting contract evidence only and was not overwritten.",
        ],
    }


def main() -> int:
    rows = _load_rows()
    if any(row.protocol_document_sha256 != EXPECTED_SHA for row in rows):
        raise SystemExit("protocol SHA mismatch against freeze contract")
    frozen_plan_sha = _sha256_file(FROZEN_PLAN)
    parent_qc = json.loads(PARENT_PHASE_QC.read_text(encoding="utf-8"))

    units = [_unit(row) for row in rows]
    first = rows[0]
    manifest = ProtocolSectionCoverageManifest(
        manifest_id=f"manifest:slice59m-table5-reps",
        protocol_version_id=first.protocol_version_id,
        protocol_document_sha256=first.protocol_document_sha256,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id=first.snapshot_id,
        units=units,
        dispositions=[],
        claims_full_coverage=False,
    )
    workflow = _workflow()
    plan = plan_protocol_control_batches(
        manifest,
        max_owned_units_per_batch=64,
        workflow_stages=[
            WorkflowStage(
                workflow_stage_id=item.workflow_stage_id,
                stage=item.review_stage,
                display_name=item.display_name,
                visit_instance=item.visit_instance,
            )
            for item in workflow
        ],
    )
    if len(plan.batches) != 1:
        raise SystemExit(f"expected one control batch, got {len(plan.batches)}")
    batch = plan.batches[0]
    phase_view = _phase_view(manifest)
    prompt = build_protocol_control_agent_prompt(batch)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    execution_dir = OUT_DIR / "execution"
    execution_dir.mkdir(parents=True, exist_ok=True)

    transport = OpenAICompatibleProtocolControlAgentTransport(timeout=7200.0)
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

    def validate_for_publication(hydrated_output: Any) -> None:
        candidate_by_id = {
            candidate.control_candidate_id: candidate
            for candidate in hydrated_output.candidates
        }
        candidate_controls = _controls_from_candidates(
            rows=rows,
            candidates=hydrated_output.candidates,
        )
        control_to_candidate = {
            control.protocol_control_id: control.originating_candidate_id
            for control in candidate_controls
        }
        catalog = PublishedProtocolControlCatalog(
            catalog_id="catalog:slice59m-table5-reps",
            protocol_version_id=first.protocol_version_id,
            protocol_document_sha256=first.protocol_document_sha256,
            study_phase=StudyPhase.PHASE_II,
            coverage_manifest_id=manifest.manifest_id,
            allowed_source_span_ids=sorted(
                {span for unit in units for span in unit.source_span_ids}
            ),
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
        if report.accepted:
            return
        issue = report.issues[0]
        candidate_id = (
            issue.entity_id
            if issue.entity_id in candidate_by_id
            else control_to_candidate.get(issue.entity_id or "")
        )
        candidate = candidate_by_id.get(candidate_id or "")
        raise ProtocolControlAgentWireValidationError(
            issue.code,
            issue.message,
            structure_unit_ids=(
                list(candidate.frozen_structure_unit_ids)
                if candidate is not None
                else batch.owned_structure_unit_ids
            ),
            candidate_ids=[candidate_id] if candidate_id else [],
        )

    started = perf_counter()
    result = ProtocolControlAgentRunner(
        max_transport_retries=1,
        max_schema_repairs=2,
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
        controls = _controls_from_candidates(rows=rows, candidates=hydrated.candidates)
        allowed_spans = sorted(
            {span for unit in units for span in unit.source_span_ids}
        )
        catalog = PublishedProtocolControlCatalog(
            catalog_id="catalog:slice59m-table5-reps",
            protocol_version_id=first.protocol_version_id,
            protocol_document_sha256=first.protocol_document_sha256,
            study_phase=StudyPhase.PHASE_II,
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

    provenance = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task_id": TASK_ID,
        "worker": WORKER,
        "replay_mode": "product_protocol_control_agent_runner_mtplx",
        "effective_route": "cursor/cursor-cli/auto",
        "declared_route_ineligible": "pi/mtplx/mtplx-qwen38-27b-optimized-quality",
        "product_mtplx_model": transport.model,
        "frozen_plan_path": str(FROZEN_PLAN.relative_to(ROOT)),
        "frozen_plan_sha256": frozen_plan_sha,
        "parent_phase_qc_path": str(PARENT_PHASE_QC.relative_to(ROOT)),
        "parent_phase_qc_sha256": _sha256_file(PARENT_PHASE_QC),
        "parent_phase_qc_all_selected_phase_applicable": parent_qc.get(
            "all_selected_phase_applicable"
        ),
        "protocol_document_sha256": EXPECTED_SHA,
        "representative_source_refs": list(REPRESENTATIVE_REFS),
        "coverage_manifest_id": manifest.manifest_id,
        "control_batch_id": batch.batch_id,
        "control_plan_id": plan.plan_id,
        "prompt_char_count": len(prompt),
        "prompt_sha256": _sha256_text(prompt),
        "prompt_template_sha256": protocol_control_agent_prompt_template_sha256(
            DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE
        ),
        "transport_identity": transport_identity,
        "claims_complete": False,
    }
    _write_json(OUT_DIR / "freeze_provenance.json", provenance)
    _write_json(
        OUT_DIR / "source_rows.json",
        [
            {
                "source_ref": row.source_ref,
                "structure_unit_id": row.structure_unit_id,
                "source_span_ids": list(row.source_span_ids),
                "excerpt": row.excerpt,
                "package_ordinal": row.package_ordinal,
                "package_id": row.package_id,
                "heading_path": list(row.heading_path),
            }
            for row in rows
        ],
    )
    _write_json(
        execution_dir / "batch.json",
        batch.model_dump(mode="json"),
    )
    _write_json(
        execution_dir / "runner-result.json",
        result.model_dump(mode="json"),
    )
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
        _write_json(
            OUT_DIR / "hydrated-batch.json",
            hydrated.model_dump(mode="json"),
        )
        _write_json(
            OUT_DIR / "agent-controls.json",
            {
                "schema_version": "phase5/d001-table5-mtplx-agent-controls/v1",
                "controls": [item.model_dump(mode="json") for item in controls],
            },
        )
    _write_json(OUT_DIR / "gate-results.json", gate_report)
    clinical_qc = _clinical_qc_scaffold(rows, hydrated)
    clinical_qc["gate"] = gate_report
    clinical_qc["runner_status"] = result.status
    clinical_qc["attempt_outcomes"] = [item.outcome for item in result.attempts]
    clinical_qc["raw_output_sha256"] = [
        item.raw_output_sha256 for item in result.attempts
    ]
    _write_json(OUT_DIR / "clinical-qc.json", clinical_qc)

    summary = {
        "task_id": TASK_ID,
        "worker": WORKER,
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
        "gate_accepted": gate_report.get("accepted"),
        "claims_complete": False,
        "structured_control_deconstruction_accepted": False,
        "transport_identity": transport_identity,
        "protocol_document_sha256": EXPECTED_SHA,
        "representative_source_refs": list(REPRESENTATIVE_REFS),
    }
    _write_json(OUT_DIR / "replay-summary.json", summary)

    handoff = "\n".join(
        [
            "# Compact Handoff: slice59m Table 5 MTPLX control Agent replay",
            "",
            f"- Task: `{TASK_ID}` / `{WORKER}`",
            "- Route: `cursor/cursor-cli/auto` (declared mtplx worker route ineligible;"
            " product MTPLX transport used for the clinical call)",
            f"- Product model: `{transport.model}` / `{transport.backend}` /"
            f" effort=`{transport.reasoning_effort}` / temp=`{transport.temperature}`",
            f"- Protocol SHA-256: `{EXPECTED_SHA}`",
            "- Replay mode: product ProtocolControlAgentRunner + control Schema transport",
            f"- Runner status: `{result.status}`",
            f"- Attempts: {len(result.attempts)}"
            f" outcomes={ [item.outcome for item in result.attempts]!r }",
            f"- Gate accepted: `{gate_report.get('accepted')}`"
            f" controls={len(controls)}"
            f" candidates={0 if hydrated is None else len(hydrated.candidates)}",
            "- structured_control_deconstruction_accepted: `false`",
            "- claims_complete: `false` (Codex owns parent clinical/source QC)",
            "",
            "## Representative rows",
            *[f"- `{row.source_ref}`: {row.excerpt}" for row in rows],
            "",
            "## Evidence / Inference / Uncertainty",
            "- Evidence: frozen plan hashes, transport identity, raw wire SHA,"
            " same-session repair attempts, hydration dump, publication-gate report.",
            "- Inference: Agent output is machine-parsed only; clinical correctness"
            " of first-dose / longer-of / clearance substitute / herbal exception"
            " is not asserted here.",
            "- Uncertainty: Codex must QC each representative against frozen excerpts;"
            " missing or incorrect structures must be repaired at shared prompt/"
            "contract/gate layer before acceptance.",
            "",
        ]
    )
    (OUT_DIR / "compact-handoff.md").write_text(handoff, encoding="utf-8")
    (OUT_DIR / "run.log").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.status == "已解析" else 2


if __name__ == "__main__":
    raise SystemExit(main())
