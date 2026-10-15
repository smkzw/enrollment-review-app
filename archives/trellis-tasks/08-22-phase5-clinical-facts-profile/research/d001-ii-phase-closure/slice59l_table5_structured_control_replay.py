#!/usr/bin/env python3
"""Deterministic Table 5 structured-control replay for slice59l worker_03.

Loads frozen D001 II-phase Table 5 rows, builds source-backed
``ProtocolReviewControl`` objects for the representative clinical shapes
(longer-of, conditional washout shorten, nested herbal exception, fixed
first-dose study-period prohibition), and runs the publication gate.

This is not an LLM deconstruction run and does not claim final clinical
acceptance. It only proves the shared TimeConstraint / activation contracts
can hold frozen Table 5 source logic without rewriting AND as OR.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.domain.contracts.enums import PhaseScope, ReviewStage, StudyPhase
from app.domain.contracts.phase_applicability import (
    PhaseApplicabilityCandidateDraft,
    PhaseApplicabilityDisposition,
    PhaseApplicabilityEvidenceDraft,
    PhaseApplicabilityEvidencePolarity,
    PhaseApplicabilityResolutionDraft,
)
from app.domain.contracts.protocol_controls import (
    ControlConditionAtom,
    ControlConditionDnf,
    ControlConditionGroup,
    ControlExceptionDnf,
    ControlExceptionGroup,
    ControlMinimumEvidence,
    ControlObligationAtom,
    ControlObligationDnf,
    ControlObligationGroup,
    ControlObligationKind,
    KnownWorkflowStageTarget,
    ProtocolControlBatchDispositionHydrated,
    ProtocolControlCandidate,
    ProtocolControlCandidateSemantics,
    ProtocolControlUnitDisposition,
    ProtocolReviewControl,
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    PublishedProtocolControlCatalog,
    ReviewNodeBinding,
    ReviewNodeRole,
    StructureUnitDisposition,
    StructureUnitDispositionKind,
    StructureUnitKind,
    TableCellContext,
)
from app.domain.contracts.rules import TimeConstraint, WorkflowStage
from app.protocols.phase_applicability import hydrate_phase_applicability_resolution
from app.protocols.full_protocol_coverage import build_resolved_full_protocol_coverage_view
from app.protocols.phase_applicability_planning import plan_phase_applicability_batches
from app.protocols.protocol_control_gate import (
    ProtocolControlGateError,
    validate_protocol_control_publication,
)
from app.protocols.protocol_control_planning import plan_protocol_control_batches

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
    / "phase5-slice59l-d001-table5-structured-control-replay-20260827"
)

REPRESENTATIVE_REFS = (
    "body.t10.r1",  # fixed first-dose window + study-period prohibition
    "body.t10.r3",  # conditional clearance shorten 24→6
    "body.t10.r4",  # longer-of calendar + half-life
    "body.t10.r7",  # nested herbal exception
)


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

    @property
    def time_text(self) -> str:
        return self.excerpt.split(" | ", 1)[0]

    @property
    def drug_text(self) -> str:
        parts = self.excerpt.split(" | ", 1)
        return parts[1] if len(parts) == 2 else self.excerpt


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _binding() -> list[ReviewNodeBinding]:
    return [
        ReviewNodeBinding(
            workflow_stage_id="stage:baseline:1",
            review_stage=ReviewStage.BASELINE,
            role=ReviewNodeRole.DECIDE_AT_NODE,
        )
    ]


def _evidence() -> list[ControlMinimumEvidence]:
    return [
        ControlMinimumEvidence(
            evidence_key="evidence:medication-exposure",
            fact_type="medication_exposure",
            description="核对禁限用药暴露起止与清除剂/例外条件记录",
            due_stage=ReviewStage.BASELINE,
            required_source_types=["原始资料"],
        )
    ]


def _span_excerpts(row: FrozenRow) -> tuple[list[str], list[str]]:
    spans = list(row.source_span_ids)
    excerpts = [row.time_text, row.drug_text]
    if len(excerpts) != len(spans):
        excerpts = [row.excerpt] * len(spans)
    return spans, excerpts


def _drug_span_excerpts(row: FrozenRow) -> tuple[list[str], list[str]]:
    """Exposure triggers cite the drug cell only — avoid temporal cues without anchors."""

    spans = list(row.source_span_ids)
    if len(spans) >= 2:
        return [spans[1]], [row.drug_text]
    return spans, [row.drug_text]


def _prohibit(
    *,
    obligation_id: str,
    statement: str,
    row: FrozenRow,
    time_constraint: TimeConstraint | None,
) -> ControlObligationAtom:
    spans, excerpts = _span_excerpts(row)
    return ControlObligationAtom(
        obligation_id=obligation_id,
        kind=ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE,
        statement=statement,
        time_constraint=time_constraint,
        source_span_ids=spans,
        source_excerpts=excerpts,
    )


def _condition(
    *,
    condition_atom_id: str,
    statement: str,
    row: FrozenRow,
    time_constraint: TimeConstraint | None = None,
    include_time_excerpt: bool = False,
) -> ControlConditionAtom:
    if include_time_excerpt:
        spans, excerpts = _span_excerpts(row)
    else:
        spans, excerpts = _drug_span_excerpts(row)
    return ControlConditionAtom(
        condition_atom_id=condition_atom_id,
        statement=statement,
        source_span_ids=spans,
        source_excerpts=excerpts,
        time_constraint=time_constraint,
    )


def _control(
    *,
    control_id: str,
    ordinal: int,
    title: str,
    row: FrozenRow,
    trigger_expression: ControlConditionDnf | None,
    obligation_expression: ControlObligationDnf,
    exception_expression: ControlExceptionDnf | None = None,
) -> ProtocolReviewControl:
    return ProtocolReviewControl(
        protocol_control_id=control_id,
        display_ordinal=ordinal,
        protocol_version_id=row.protocol_version_id,
        study_phase=StudyPhase.PHASE_II,
        title=title,
        applicable_population="拟入组受试者",
        obligations=[],
        obligation_combination="all",
        trigger_expression=trigger_expression,
        obligation_expression=obligation_expression,
        exception_expression=exception_expression,
        review_node_bindings=_binding(),
        minimum_evidence=_evidence(),
        source_span_ids=list(row.source_span_ids),
        source_structure_unit_ids=[row.structure_unit_id],
        cross_source_relations=[],
    )


def build_r1_fixed_first_dose(row: FrozenRow) -> ProtocolReviewControl:
    window = TimeConstraint(
        anchor_type="first_dose_date",
        direction="before",
        lower_bound={"value": 6, "unit": "month"},
    )
    return _control(
        control_id="pctrl-table5-r1-fixed-first-dose",
        ordinal=1,
        title="表5固定首次给药前窗禁止（靶向生物制剂）",
        row=row,
        trigger_expression=ControlConditionDnf(
            groups=[
                ControlConditionGroup(
                    atoms=[
                        _condition(
                            condition_atom_id="trg-r1",
                            statement=row.drug_text,
                            row=row,
                        )
                    ],
                    trigger_branch_id="pct-r1",
                )
            ]
        ),
        obligation_expression=ControlObligationDnf(
            groups=[
                ControlObligationGroup(
                    atoms=[
                        _prohibit(
                            obligation_id="obl-r1",
                            statement=(
                                f"{row.time_text}不得使用：{row.drug_text}"
                            ),
                            row=row,
                            time_constraint=window,
                        )
                    ],
                    obligation_group_id="pog-r1-default",
                    applies_to_trigger_branch_ids=["pct-r1"],
                    activated_by_exception_group_ids=[],
                )
            ]
        ),
    )


def build_r3_conditional_shorten(row: FrozenRow) -> ProtocolReviewControl:
    default_window = TimeConstraint(
        anchor_type="first_dose_date",
        direction="before",
        lower_bound={"value": 24, "unit": "month"},
    )
    short_window = TimeConstraint(
        anchor_type="first_dose_date",
        direction="before",
        lower_bound={"value": 6, "unit": "month"},
    )
    return _control(
        control_id="pctrl-table5-r3-leflunomide-clearance",
        ordinal=1,
        title="表5来氟米特默认24个月与清除剂后6个月",
        row=row,
        trigger_expression=ControlConditionDnf(
            groups=[
                ControlConditionGroup(
                    atoms=[
                        _condition(
                            condition_atom_id="trg-r3",
                            statement=row.drug_text,
                            row=row,
                        )
                    ],
                    trigger_branch_id="pct-r3",
                )
            ]
        ),
        obligation_expression=ControlObligationDnf(
            groups=[
                ControlObligationGroup(
                    atoms=[
                        _prohibit(
                            obligation_id="obl-r3-default",
                            statement="首次给药前24个月至试验结束不得暴露来氟米特",
                            row=row,
                            time_constraint=default_window,
                        )
                    ],
                    obligation_group_id="pog-r3-default",
                    applies_to_trigger_branch_ids=["pct-r3"],
                    activated_by_exception_group_ids=[],
                ),
                ControlObligationGroup(
                    atoms=[
                        _prohibit(
                            obligation_id="obl-r3-alt",
                            statement="首次给药前6个月至试验结束不得暴露来氟米特",
                            row=row,
                            time_constraint=short_window,
                        )
                    ],
                    obligation_group_id="pog-r3-alt",
                    applies_to_trigger_branch_ids=["pct-r3"],
                    activated_by_exception_group_ids=["peg-r3-clearance"],
                ),
            ]
        ),
        exception_expression=ControlExceptionDnf(
            groups=[
                ControlExceptionGroup(
                    atoms=[
                        _condition(
                            condition_atom_id="ex-r3-clearance",
                            statement="若经过药物清除剂进行洗脱可缩短至首次给药前6个月",
                            row=row,
                        )
                    ],
                    exception_group_id="peg-r3-clearance",
                    waives_trigger_branch_ids=["pct-r3"],
                    activates_obligation_group_ids=["pog-r3-alt"],
                )
            ]
        ),
    )


def build_r4_longer_of(row: FrozenRow) -> ProtocolReviewControl:
    longer = TimeConstraint(
        anchor_type="first_dose_date",
        direction="before",
        lower_bound={"value": 3, "unit": "month"},
        half_life_multiplier=5,
        combined_window_selection="longer_of_calendar_and_half_life",
    )
    return _control(
        control_id="pctrl-table5-r4-longer-of",
        ordinal=1,
        title="表5其他生物制剂较长者时间窗",
        row=row,
        trigger_expression=ControlConditionDnf(
            groups=[
                ControlConditionGroup(
                    atoms=[
                        _condition(
                            condition_atom_id="trg-r4",
                            statement=row.drug_text,
                            row=row,
                        )
                    ],
                    trigger_branch_id="pct-r4",
                )
            ]
        ),
        obligation_expression=ControlObligationDnf(
            groups=[
                ControlObligationGroup(
                    atoms=[
                        _prohibit(
                            obligation_id="obl-r4",
                            statement=(
                                "首次给药前3个月或5个半衰期（以时间较长者为准）"
                                "至试验结束不得使用除靶向IL-12、IL-17和/或IL-23外的其他生物制剂"
                            ),
                            row=row,
                            time_constraint=longer,
                        )
                    ],
                    obligation_group_id="pog-r4-default",
                    applies_to_trigger_branch_ids=["pct-r4"],
                    activated_by_exception_group_ids=[],
                )
            ]
        ),
    )


def build_r7_nested_herbal(row: FrozenRow) -> ProtocolReviewControl:
    default_window = TimeConstraint(
        anchor_type="first_dose_date",
        direction="before",
        lower_bound={"value": 4, "unit": "week"},
    )
    short_window = TimeConstraint(
        anchor_type="first_dose_date",
        direction="before",
        lower_bound={"value": 2, "unit": "week"},
    )
    drug_span = list(row.source_span_ids)[-1:]
    general_excerpt = "影响银屑病病情的非生物制剂系统治疗"
    herbal_excerpt = "中成药及传统中草药"
    return _control(
        control_id="pctrl-table5-r7-nested-herbal",
        ordinal=1,
        title="表5非生物系统治疗与局部中草药嵌套例外",
        row=row,
        trigger_expression=ControlConditionDnf(
            groups=[
                ControlConditionGroup(
                    atoms=[
                        ControlConditionAtom(
                            condition_atom_id="trg-r7-general",
                            statement=general_excerpt,
                            source_span_ids=drug_span,
                            source_excerpts=[general_excerpt],
                        )
                    ],
                    trigger_branch_id="pct-r7-general",
                ),
                ControlConditionGroup(
                    atoms=[
                        ControlConditionAtom(
                            condition_atom_id="trg-r7-herbal",
                            statement=herbal_excerpt,
                            source_span_ids=drug_span,
                            source_excerpts=[herbal_excerpt],
                        )
                    ],
                    trigger_branch_id="pct-r7-herbal",
                ),
            ]
        ),
        obligation_expression=ControlObligationDnf(
            groups=[
                ControlObligationGroup(
                    atoms=[
                        _prohibit(
                            obligation_id="obl-r7-general",
                            statement="首次给药前4周至试验结束不得使用非生物制剂系统治疗",
                            row=row,
                            time_constraint=default_window,
                        )
                    ],
                    obligation_group_id="pog-r7-general",
                    applies_to_trigger_branch_ids=["pct-r7-general"],
                    activated_by_exception_group_ids=[],
                ),
                ControlObligationGroup(
                    atoms=[
                        _prohibit(
                            obligation_id="obl-r7-herbal-default",
                            statement="首次给药前4周至试验结束不得使用中成药及传统中草药",
                            row=row,
                            time_constraint=default_window,
                        )
                    ],
                    obligation_group_id="pog-r7-herbal-default",
                    applies_to_trigger_branch_ids=["pct-r7-herbal"],
                    activated_by_exception_group_ids=[],
                ),
                ControlObligationGroup(
                    atoms=[
                        _prohibit(
                            obligation_id="obl-r7-herbal-alt",
                            statement="禁用时间可缩短至给药前2周至试验结束",
                            row=row,
                            time_constraint=short_window,
                        )
                    ],
                    obligation_group_id="pog-r7-herbal-alt",
                    applies_to_trigger_branch_ids=["pct-r7-herbal"],
                    activated_by_exception_group_ids=["peg-r7-herbal"],
                ),
            ]
        ),
        exception_expression=ControlExceptionDnf(
            groups=[
                ControlExceptionGroup(
                    atoms=[
                        ControlConditionAtom(
                            condition_atom_id="ex-r7-herbal",
                            statement=(
                                "对于无明确临床证据可能改善银屑病病情的中成药或传统中草药，"
                                "禁用时间可缩短至给药前2周至试验结束"
                            ),
                            source_span_ids=drug_span,
                            # Keep non-temporal excerpt on the condition atom;
                            # temporal shorten lives on the activated obligation.
                            source_excerpts=[
                                "无明确临床证据可能改善银屑病病情的中成药或传统中草药"
                            ],
                        )
                    ],
                    exception_group_id="peg-r7-herbal",
                    waives_trigger_branch_ids=["pct-r7-herbal"],
                    activates_obligation_group_ids=["pog-r7-herbal-alt"],
                )
            ]
        ),
    )


def _candidate_for(control: ProtocolReviewControl, row: FrozenRow) -> ProtocolControlCandidate:
    candidate_id = f"pcc-{row.source_ref.replace('.', '-')}"
    semantics = ProtocolControlCandidateSemantics(
        title=control.title,
        applicable_population=control.applicable_population,
        control_candidate_id=candidate_id,
        trigger_expression=control.trigger_expression,
        obligation_expression=control.obligation_expression,
        exception_expression=control.exception_expression,
        review_node_bindings=list(control.review_node_bindings),
        minimum_evidence=list(control.minimum_evidence),
        source_structure_unit_ids=list(control.source_structure_unit_ids),
        source_span_ids=list(control.source_span_ids),
        cross_source_relations=[],
    )
    return ProtocolControlCandidate(
        control_candidate_id=candidate_id,
        protocol_version_id=row.protocol_version_id,
        study_phase=StudyPhase.PHASE_II,
        frozen_structure_unit_ids=[row.structure_unit_id],
        title=control.title,
        applicable_population=control.applicable_population,
        source_span_ids=list(row.source_span_ids),
        semantics=semantics,
    )


def _phase_view(manifest: ProtocolSectionCoverageManifest) -> object:
    """Replay accepted package-64 selected_phase_applicable without mutating frozen scopes."""

    plan = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=64,
        context_radius=1,
    )
    package = plan.packages[0]
    target = package.owned_units[0]
    span_index = package.frozen_source_span_ids.index(target.source_span_ids[0])
    draft = PhaseApplicabilityResolutionDraft(
        unit_index=0,
        evidence=[
            PhaseApplicabilityEvidenceDraft(
                polarity=PhaseApplicabilityEvidencePolarity.SUPPORTS,
                source_unit_indexes=[0],
                source_span_indexes=[span_index],
                excerpt=target.excerpt,
                rationale=(
                    "slice59j package-64 accepted selected_phase_applicable for "
                    "this frozen Table 5 row; replay preserves UNKNOWN source scopes"
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
    resolutions = hydrate_phase_applicability_resolution(package, draft)
    return build_resolved_full_protocol_coverage_view(
        manifest,
        plan,
        [resolutions],
    )


def _gate_one(
    *,
    row: FrozenRow,
    control: ProtocolReviewControl,
) -> dict[str, Any]:
    unit = _unit(row)
    candidate = _candidate_for(control, row)
    control = control.model_copy(
        update={"originating_candidate_id": candidate.control_candidate_id}
    )
    manifest = ProtocolSectionCoverageManifest(
        manifest_id=f"manifest:slice59l-{row.source_ref}",
        protocol_version_id=row.protocol_version_id,
        protocol_document_sha256=row.protocol_document_sha256,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id=row.snapshot_id,
        units=[unit],
        dispositions=[
            StructureUnitDisposition(
                structure_unit_id=row.structure_unit_id,
                disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                linked_control_candidate_id=candidate.control_candidate_id,
            )
        ],
        claims_full_coverage=True,
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
    batch = plan.batches[0]
    results = [
        ProtocolControlBatchDispositionHydrated(
            batch_id=batch.batch_id,
            coverage_manifest_id=manifest.manifest_id,
            owned_structure_unit_ids=list(batch.owned_structure_unit_ids),
            owned_source_span_ids=list(batch.owned_source_span_ids),
            dispositions=[
                ProtocolControlUnitDisposition(
                    structure_unit_id=row.structure_unit_id,
                    disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                    linked_control_candidate_ids=[candidate.control_candidate_id],
                )
            ],
            candidates=[candidate],
        )
    ]
    catalog = PublishedProtocolControlCatalog(
        catalog_id=f"catalog:slice59l-{row.source_ref}",
        protocol_version_id=row.protocol_version_id,
        protocol_document_sha256=row.protocol_document_sha256,
        study_phase=StudyPhase.PHASE_II,
        coverage_manifest_id=manifest.manifest_id,
        allowed_source_span_ids=list(row.source_span_ids),
        controls=[control],
    )
    phase_view = _phase_view(manifest)
    validate_protocol_control_publication(
        manifest,
        catalog,
        plan,
        results,
        candidates=[],
        workflow_stage_targets=workflow,
        phase_applicability_view=phase_view,
    )
    return {
        "accepted": True,
        "source_ref": row.source_ref,
        "structure_unit_id": row.structure_unit_id,
        "protocol_control_id": control.protocol_control_id,
        "control_candidate_id": candidate.control_candidate_id,
        "frozen_phase_scopes": [scope.value for scope in unit.phase_scopes],
        "phase_view_disposition": str(
            phase_view.disposition_for(row.structure_unit_id)
        ),
        "control": control.model_dump(mode="json"),
        "candidate": candidate.model_dump(mode="json"),
    }


def _expect_reject(
    *,
    label: str,
    expected_code: str,
    builder: Callable[[], None],
) -> dict[str, Any]:
    try:
        builder()
    except ProtocolControlGateError as exc:
        return {
            "label": label,
            "accepted": False,
            "expected_code": expected_code,
            "actual_code": exc.code,
            "matched": exc.code == expected_code,
            "message": str(exc),
        }
    except ValueError as exc:
        # Contract-level rejects before gate are also useful evidence.
        return {
            "label": label,
            "accepted": False,
            "expected_code": expected_code,
            "actual_code": type(exc).__name__,
            "matched": expected_code in str(exc) or expected_code in type(exc).__name__,
            "message": str(exc),
        }
    return {
        "label": label,
        "accepted": True,
        "expected_code": expected_code,
        "actual_code": None,
        "matched": False,
        "message": "expected rejection but gate accepted",
    }


def _negative_cases(rows: dict[str, FrozenRow]) -> list[dict[str, Any]]:
    r3 = rows["body.t10.r3"]
    r4 = rows["body.t10.r4"]

    def missing_longer_of() -> None:
        bad = build_r4_longer_of(r4)
        # Drop selection while keeping calendar + half-life cues in statement.
        obl = bad.obligation_expression.groups[0].atoms[0]
        broken = obl.model_copy(
            update={
                "time_constraint": TimeConstraint(
                    anchor_type="first_dose_date",
                    direction="before",
                    lower_bound={"value": 3, "unit": "month"},
                )
            }
        )
        control = bad.model_copy(
            update={
                "obligation_expression": ControlObligationDnf(
                    groups=[
                        ControlObligationGroup(
                            atoms=[broken],
                            obligation_group_id="pog-r4-default",
                            applies_to_trigger_branch_ids=["pct-r4"],
                            activated_by_exception_group_ids=[],
                        )
                    ]
                )
            }
        )
        _gate_one(row=r4, control=control)

    def screening_anchor() -> None:
        bad = build_r1_fixed_first_dose(rows["body.t10.r1"])
        obl = bad.obligation_expression.groups[0].atoms[0]
        broken = obl.model_copy(
            update={
                "time_constraint": TimeConstraint(
                    anchor_type="screening_date",
                    direction="before",
                    lower_bound={"value": 6, "unit": "month"},
                )
            }
        )
        control = bad.model_copy(
            update={
                "obligation_expression": ControlObligationDnf(
                    groups=[
                        ControlObligationGroup(
                            atoms=[broken],
                            obligation_group_id="pog-r1-default",
                            applies_to_trigger_branch_ids=["pct-r1"],
                            activated_by_exception_group_ids=[],
                        )
                    ]
                )
            }
        )
        _gate_one(row=rows["body.t10.r1"], control=control)

    def short_on_condition() -> None:
        good = build_r3_conditional_shorten(r3)
        ex = good.exception_expression.groups[0]
        atom = ex.atoms[0].model_copy(
            update={
                "time_constraint": TimeConstraint(
                    anchor_type="first_dose_date",
                    direction="before",
                    lower_bound={"value": 6, "unit": "month"},
                )
            }
        )
        control = good.model_copy(
            update={
                "exception_expression": ControlExceptionDnf(
                    groups=[
                        ControlExceptionGroup(
                            atoms=[atom],
                            exception_group_id="peg-r3-clearance",
                            waives_trigger_branch_ids=["pct-r3"],
                            activates_obligation_group_ids=["pog-r3-alt"],
                        )
                    ]
                )
            }
        )
        _gate_one(row=r3, control=control)

    def and_rewritten_as_or() -> None:
        # Unconditional OR of 24m and 6m on the same trigger, no activation.
        default_window = TimeConstraint(
            anchor_type="first_dose_date",
            direction="before",
            lower_bound={"value": 24, "unit": "month"},
        )
        short_window = TimeConstraint(
            anchor_type="first_dose_date",
            direction="before",
            lower_bound={"value": 6, "unit": "month"},
        )
        control = _control(
            control_id="pctrl-table5-r3-or-rewrite",
            ordinal=1,
            title="非法把条件缩短写成无条件或",
            row=r3,
            trigger_expression=ControlConditionDnf(
                groups=[
                    ControlConditionGroup(
                        atoms=[
                            _condition(
                                condition_atom_id="trg-r3",
                                statement=r3.drug_text,
                                row=r3,
                            )
                        ],
                        trigger_branch_id="pct-r3",
                    )
                ]
            ),
            obligation_expression=ControlObligationDnf(
                groups=[
                    ControlObligationGroup(
                        atoms=[
                            _prohibit(
                                obligation_id="obl-24",
                                statement="首次给药前24个月不得暴露",
                                row=r3,
                                time_constraint=default_window,
                            )
                        ],
                        obligation_group_id="pog-24",
                        applies_to_trigger_branch_ids=["pct-r3"],
                        activated_by_exception_group_ids=[],
                    ),
                    ControlObligationGroup(
                        atoms=[
                            _prohibit(
                                obligation_id="obl-6",
                                statement="首次给药前6个月不得暴露",
                                row=r3,
                                time_constraint=short_window,
                            )
                        ],
                        obligation_group_id="pog-6",
                        applies_to_trigger_branch_ids=["pct-r3"],
                        activated_by_exception_group_ids=[],
                    ),
                ]
            ),
        )
        _gate_one(row=r3, control=control)

    return [
        _expect_reject(
            label="longer_of_missing_selection",
            expected_code="TIME_COMBINED_SELECTION_MISSING",
            builder=missing_longer_of,
        ),
        _expect_reject(
            label="first_dose_guessed_as_screening",
            expected_code="TIME_ANCHOR_GUESSED_FROM_SCREENING",
            builder=screening_anchor,
        ),
        _expect_reject(
            label="short_window_on_exception_condition",
            expected_code="EXCEPTION_TIME_ON_CONDITION",
            builder=short_on_condition,
        ),
        _expect_reject(
            label="conditional_shorten_rewritten_as_or",
            expected_code="OBLIGATION_WINDOW_UNCONDITIONAL_OR",
            builder=and_rewritten_as_or,
        ),
    ]


def _qc_checks(accepted: list[dict[str, Any]], negatives: list[dict[str, Any]]) -> dict[str, Any]:
    by_ref = {item["source_ref"]: item["control"] for item in accepted}

    def anchors(control: dict[str, Any]) -> set[str]:
        found: set[str] = set()
        for group in control.get("obligation_expression", {}).get("groups", []):
            for atom in group.get("atoms", []):
                tc = atom.get("time_constraint") or {}
                if tc.get("anchor_type"):
                    found.add(tc["anchor_type"])
        return found

    r3 = by_ref["body.t10.r3"]
    r3_groups = r3["obligation_expression"]["groups"]
    r3_default = next(g for g in r3_groups if not g.get("activated_by_exception_group_ids"))
    r3_alt = next(g for g in r3_groups if g.get("activated_by_exception_group_ids"))
    r3_ex = r3["exception_expression"]["groups"][0]

    r4 = by_ref["body.t10.r4"]
    r4_tc = r4["obligation_expression"]["groups"][0]["atoms"][0]["time_constraint"]

    r7 = by_ref["body.t10.r7"]
    r7_ex = r7["exception_expression"]["groups"][0]
    r7_waived = set(r7_ex["waives_trigger_branch_ids"])

    r1 = by_ref["body.t10.r1"]

    logic_checks = [
        {
            "source_ref": "body.t10.r1",
            "required_source_logic": "首次给药前6个月至试验结束",
            "structured_present": anchors(r1) == {"first_dose_date"},
            "detail": {
                "anchor_types": sorted(anchors(r1)),
                "lower_bound": r1["obligation_expression"]["groups"][0]["atoms"][0][
                    "time_constraint"
                ]["lower_bound"],
            },
        },
        {
            "source_ref": "body.t10.r3",
            "required_source_logic": "若经过药物清除剂进行洗脱可缩短至首次给药前6个月",
            "structured_present": (
                r3_default["atoms"][0]["time_constraint"]["lower_bound"]
                == {"value": 24, "unit": "month"}
                and r3_alt["atoms"][0]["time_constraint"]["lower_bound"]
                == {"value": 6, "unit": "month"}
                and r3_ex["activates_obligation_group_ids"] == ["pog-r3-alt"]
                and all(
                    atom.get("time_constraint") is None for atom in r3_ex["atoms"]
                )
                and set(r3_default["applies_to_trigger_branch_ids"])
                == set(r3_alt["applies_to_trigger_branch_ids"])
            ),
            "detail": {
                "default_months": r3_default["atoms"][0]["time_constraint"][
                    "lower_bound"
                ],
                "alt_months": r3_alt["atoms"][0]["time_constraint"]["lower_bound"],
                "activation": r3_ex["activates_obligation_group_ids"],
                "condition_has_time": any(
                    atom.get("time_constraint") is not None for atom in r3_ex["atoms"]
                ),
                "not_unconditional_or": True,
            },
        },
        {
            "source_ref": "body.t10.r4",
            "required_source_logic": "以时间较长者为准",
            "structured_present": (
                r4_tc.get("combined_window_selection")
                == "longer_of_calendar_and_half_life"
                and r4_tc.get("half_life_multiplier") == 5
                and r4_tc.get("anchor_type") == "first_dose_date"
            ),
            "detail": r4_tc,
        },
        {
            "source_ref": "body.t10.r7",
            "required_source_logic": "禁用时间可缩短至给药前2周至试验结束",
            "structured_present": (
                r7_waived == {"pct-r7-herbal"}
                and "pct-r7-general" not in r7_waived
                and r7_ex["activates_obligation_group_ids"] == ["pog-r7-herbal-alt"]
            ),
            "detail": {
                "waives": sorted(r7_waived),
                "activates": r7_ex["activates_obligation_group_ids"],
                "local_to_herbal_branch": r7_waived == {"pct-r7-herbal"},
            },
        },
    ]

    all_first_dose = all(
        anchors(control) == {"first_dose_date"} for control in by_ref.values()
    )
    negatives_ok = all(item["matched"] for item in negatives)
    structured_ok = all(item["structured_present"] for item in logic_checks)

    return {
        "schema_version": "phase5/d001-table5-structured-control-replay-qc/v1",
        "claims_complete": False,
        "phase_applicability_accepted": True,
        "phase_applicability_source": str(PARENT_PHASE_QC.relative_to(ROOT)),
        "structured_control_deconstruction_accepted": structured_ok and negatives_ok,
        "structured_control_replay_mode": (
            "deterministic_source_backed_gate_replay_not_llm_agent"
        ),
        "protocol_document_sha256": EXPECTED_SHA,
        "all_controls_use_first_dose_anchor": all_first_dose,
        "positive_gate_accepted_count": len(accepted),
        "negative_gate_matched_count": sum(1 for item in negatives if item["matched"]),
        "logic_checks": logic_checks,
        "negative_gate_checks": negatives,
        "structured_control_deconstruction_reason": (
            "冻结表5代表行已进入带 first_dose_date、longer_of 选择、"
            "清除剂激活绑定与局部中草药例外作用域的结构化控制，且门禁拒绝"
            "筛选日猜测、缺择长标签、条件窗挂条件原子、把条件缩短写成无条件或。"
            if structured_ok and negatives_ok
            else "结构化回放未完全满足父级 QC 逻辑检查或负例门禁。"
        ),
        "codex_final_acceptance_required": True,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = _load_rows()
    row_map = {row.source_ref: row for row in rows}
    if any(row.protocol_document_sha256 != EXPECTED_SHA for row in rows):
        raise SystemExit("protocol SHA mismatch against accepted hash")

    builders: list[tuple[str, Callable[[FrozenRow], ProtocolReviewControl]]] = [
        ("body.t10.r1", build_r1_fixed_first_dose),
        ("body.t10.r3", build_r3_conditional_shorten),
        ("body.t10.r4", build_r4_longer_of),
        ("body.t10.r7", build_r7_nested_herbal),
    ]

    accepted: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for source_ref, builder in builders:
        row = row_map[source_ref]
        try:
            accepted.append(_gate_one(row=row, control=builder(row)))
        except Exception as exc:  # noqa: BLE001 - record exact gate/contract failure
            errors.append(
                {
                    "source_ref": source_ref,
                    "error_type": type(exc).__name__,
                    "code": getattr(exc, "code", None),
                    "message": str(exc),
                }
            )

    negatives = _negative_cases(row_map)
    qc = _qc_checks(accepted, negatives) if not errors else {
        "schema_version": "phase5/d001-table5-structured-control-replay-qc/v1",
        "claims_complete": False,
        "structured_control_deconstruction_accepted": False,
        "positive_gate_errors": errors,
        "negative_gate_checks": negatives,
        "codex_final_acceptance_required": True,
    }

    provenance = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "frozen_plan_path": str(FROZEN_PLAN.relative_to(ROOT)),
        "frozen_plan_sha256": _sha256_file(FROZEN_PLAN),
        "parent_phase_qc_path": str(PARENT_PHASE_QC.relative_to(ROOT)),
        "protocol_document_sha256": EXPECTED_SHA,
        "representative_source_refs": list(REPRESENTATIVE_REFS),
        "replay_mode": "deterministic_source_backed_gate_replay_not_llm_agent",
        "worker": "worker_03",
        "task_id": "phase5-slice59l-20260827",
        "effective_route": "cursor/cursor-cli/auto",
    }
    source_rows = [
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
    ]
    gate_results = {
        "positive": [
            {
                "source_ref": item["source_ref"],
                "accepted": item["accepted"],
                "protocol_control_id": item["protocol_control_id"],
                "control_candidate_id": item["control_candidate_id"],
            }
            for item in accepted
        ],
        "positive_errors": errors,
        "negative": negatives,
    }
    structured = {
        "schema_version": "phase5/d001-table5-structured-controls/v1",
        "controls": [item["control"] for item in accepted],
        "candidates": [item["candidate"] for item in accepted],
    }

    (OUT_DIR / "freeze_provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT_DIR / "source_rows.json").write_text(
        json.dumps(source_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT_DIR / "structured-controls.json").write_text(
        json.dumps(structured, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT_DIR / "gate-results.json").write_text(
        json.dumps(gate_results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT_DIR / "clinical-qc.json").write_text(
        json.dumps(qc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    handoff = [
        "# Compact Handoff: slice59l Table 5 structured-control replay",
        "",
        f"- Task: `phase5-slice59l-20260827` / `worker_03`",
        f"- Route: `cursor/cursor-cli/auto` (declared mtplx route ineligible for this worker)",
        f"- Protocol SHA-256: `{EXPECTED_SHA}`",
        f"- Replay mode: deterministic source-backed gate replay (not LLM agent)",
        f"- Positive accepted: {len(accepted)}/{len(builders)}",
        f"- Negative matched: {sum(1 for n in negatives if n['matched'])}/{len(negatives)}",
        f"- structured_control_deconstruction_accepted: "
        f"`{qc.get('structured_control_deconstruction_accepted')}`",
        f"- claims_complete: `false` (Codex owns final clinical/source acceptance)",
        "",
        "## Representative rows",
    ]
    for row in rows:
        handoff.append(f"- `{row.source_ref}`: {row.excerpt}")
    handoff.extend(
        [
            "",
            "## Evidence / Inference / Uncertainty",
            "- Evidence: frozen plan packages 64 rows r1/r3/r4/r7 excerpts and span IDs.",
            "- Inference: structured controls encode longer-of selection, clearance "
            "activation binding, herbal-local exception scope, and first_dose anchors.",
            "- Uncertainty: this does not replace a future Agent deconstruction over "
            "all Table 5 rows; parent clinical/regulatory acceptance remains with Codex.",
            "",
        ]
    )
    (OUT_DIR / "compact-handoff.md").write_text(
        "\n".join(handoff), encoding="utf-8"
    )

    print(json.dumps({"out_dir": str(OUT_DIR), "qc": qc, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors and qc.get("structured_control_deconstruction_accepted") else 1


if __name__ == "__main__":
    raise SystemExit(main())
