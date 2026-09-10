"""Deterministic Phase 5.8c publication-gate regressions.

The synthetic cases do not call a model.  The final test reads the authorized
D001 protocol read-only and writes only extraction artifacts below pytest's
``tmp_path``; it proves source-input retention, not medical completeness.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.agents.protocol_control_deconstructor import ProtocolControlAgentInput
from app.domain.contracts.enums import (
    AnchorType,
    PhaseScope,
    ReviewStage,
    StudyPhase,
    TimeDirection,
)
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
    ControlCrossSourceRelation,
    ControlExceptionDnf,
    ControlExceptionGroup,
    ControlMinimumEvidence,
    ControlObligationAtom,
    ControlObligationDnf,
    ControlObligationGroup,
    ControlObligationKind,
    ControlObligationModality,
    ControlTemporalScopeKind,
    ControlRelationTargetKind,
    CrossSourceRelationKind,
    KnownOfficialRuleTarget,
    KnownRequiredProcedureTarget,
    KnownWorkflowStageTarget,
    ProtocolControlBatchDispositionHydrated,
    ProtocolControlBatchPlan,
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
    TableCellContext,
)
from app.domain.contracts.rules import (
    ProspectivePeriod,
    TimeConstraint,
    TimeQuantity,
    TimeUnit,
    WorkflowStage,
)
from app.protocols.docx_structure import extract_docx_structure
from app.protocols.full_protocol_coverage import build_full_protocol_coverage_manifest
from app.protocols.full_protocol_coverage import build_resolved_full_protocol_coverage_view
from app.protocols.ingestion import register_source_artifact
from app.protocols.phase_detection import build_phase_applicability_graph, project_single_phase
from app.protocols.phase_applicability import hydrate_phase_applicability_resolution
from app.protocols.phase_applicability_planning import plan_phase_applicability_batches
from app.protocols.protocol_control_gate import (
    ProtocolControlGateError,
    _check_conditional_branch_mapping,
    _check_minimum_evidence_modality_fidelity,
    _check_minimum_evidence_authority_boundary,
    _check_professional_judgment_fidelity,
    _check_authority_reference_provenance,
    _check_participant_preparation_realization_fidelity,
    _check_user_facing_item_count_fidelity,
    _check_collection_obligation_semantics,
    _check_dnf,
    _check_exception_layer,
    _check_anchor_decision_alignment,
    _check_mixed_decision_stage_control,
    _check_mixed_trigger_decision_stages,
    _check_obligation_modality_and_event_anchor,
    _check_recording_precision_fidelity,
    _check_post_enrollment_procedure_classification,
    _check_planned_visit_node_closure,
    _check_routine_action_not_trigger,
    _check_required_procedure_visit_scope,
    _check_review_guidance_action_fidelity,
    _check_hydrated_result_links,
    _check_supplementary_procedure_stage_alignment,
    _check_temporal_obligation_relation_scope,
    _check_time_constraints,
    _visit_scope_keys,
    check_protocol_control_publication,
    validate_protocol_control_publication,
)


def test_since_visit_reference_is_not_a_procedure_execution_visit() -> None:
    assert _visit_scope_keys("问询筛选访视以来的病史及诊治情况") == set()
    assert _visit_scope_keys("问询自上次访视以来的病史及诊治情况") == set()


def test_explicit_procedure_visits_remain_in_visit_scope() -> None:
    assert _visit_scope_keys("在筛选访视和基线访视分别收集病史") == {
        "screening",
        "baseline",
    }


def test_frozen_pre_enrollment_unit_cannot_be_downgraded_to_post_treatment() -> None:
    result = ProtocolControlBatchDispositionHydrated(
        batch_id="batch:pre-enrollment",
        coverage_manifest_id="manifest:pre-enrollment",
        owned_structure_unit_ids=["su-pre"],
        owned_source_span_ids=["span:pre"],
        dispositions=[
            ProtocolControlUnitDisposition(
                structure_unit_id="su-pre",
                disposition=StructureUnitDispositionKind.POST_TREATMENT_EXECUTION,
            )
        ],
        candidates=[],
    )
    unit = ProtocolStructureUnit(
        structure_unit_id="su-pre",
        source_ref="body.p1",
        member_source_refs=["body.p1"],
        source_span_ids=["span:pre"],
        unit_kind="list_item",
        heading_path=["访视安排", "治疗期"],
        source_order=10,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.PHASE_II],
        excerpt="问询上次访视以来的病史及诊治情况",
    )

    with pytest.raises(
        ProtocolControlGateError,
        match="PRE_ENROLLMENT_PROCEDURE_MISCLASSIFIED",
    ):
        _check_hydrated_result_links(
            result,
            known_procedure_targets=[],
            unit_by_id={"su-pre": unit},
            study_phase=StudyPhase.PHASE_II,
            pre_enrollment_structure_unit_ids=["su-pre"],
        )


def test_frozen_known_procedure_visit_cannot_be_downgraded_to_supplement() -> None:
    result = ProtocolControlBatchDispositionHydrated(
        batch_id="batch:known-procedure",
        coverage_manifest_id="manifest:known-procedure",
        owned_structure_unit_ids=["su-procedure"],
        owned_source_span_ids=["span:procedure"],
        dispositions=[
            ProtocolControlUnitDisposition(
                structure_unit_id="su-procedure",
                disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
            )
        ],
        candidates=[],
    )
    unit = ProtocolStructureUnit(
        structure_unit_id="su-procedure",
        source_ref="body.p1",
        member_source_refs=["body.p1"],
        source_span_ids=["span:procedure"],
        unit_kind="list_item",
        heading_path=["访视安排", "基线访视"],
        source_order=10,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.PHASE_II],
        excerpt="问询筛选访视以来的病史及诊治情况",
    )

    with pytest.raises(
        ProtocolControlGateError,
        match="KNOWN_PROCEDURE_DISPOSITION_MISMATCH",
    ):
        _check_hydrated_result_links(
            result,
            known_procedure_targets=[],
            unit_by_id={"su-procedure": unit},
            study_phase=StudyPhase.PHASE_II,
            owned_visit_instance_by_structure_unit_id={
                "su-procedure": "基线访视"
            },
        )


def test_frozen_required_action_cannot_be_discarded_as_supplement() -> None:
    result = ProtocolControlBatchDispositionHydrated(
        batch_id="batch:required-action",
        coverage_manifest_id="manifest:required-action",
        owned_structure_unit_ids=["su-method"],
        owned_source_span_ids=["span:method"],
        dispositions=[
            ProtocolControlUnitDisposition(
                structure_unit_id="su-method",
                disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
            )
        ],
        candidates=[],
    )
    unit = ProtocolStructureUnit(
        structure_unit_id="su-method",
        source_ref="body.p1",
        member_source_refs=["body.p1"],
        source_span_ids=["span:method"],
        unit_kind="list_item",
        heading_path=["研究评估和程序", "测量要求"],
        source_order=10,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.PHASE_II],
        excerpt="使用校准设备完成测量。",
    )

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_hydrated_result_links(
            result,
            known_procedure_targets=[],
            unit_by_id={"su-method": unit},
            study_phase=StudyPhase.PHASE_II,
            owned_required_action_kinds_by_structure_unit_id={
                "su-method": ["use_calibrated_device"]
            },
        )

    assert exc_info.value.code == "REQUIRED_ACTION_DISCARDED"


def test_out_of_scope_required_action_can_be_preserved_as_post_treatment() -> None:
    result = ProtocolControlBatchDispositionHydrated(
        batch_id="batch:post-treatment-action",
        coverage_manifest_id="manifest:post-treatment-action",
        owned_structure_unit_ids=["su-method"],
        owned_source_span_ids=["span:method"],
        dispositions=[
            ProtocolControlUnitDisposition(
                structure_unit_id="su-method",
                disposition=StructureUnitDispositionKind.POST_TREATMENT_EXECUTION,
            )
        ],
        candidates=[],
    )
    unit = ProtocolStructureUnit(
        structure_unit_id="su-method",
        source_ref="body.p1",
        member_source_refs=["body.p1"],
        source_span_ids=["span:method"],
        unit_kind="paragraph",
        heading_path=["研究评估和程序", "操作顺序"],
        source_order=10,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.PHASE_II],
        excerpt="给药后尽量先完成检查，再采集样本。",
    )

    _check_hydrated_result_links(
        result,
        known_procedure_targets=[],
        unit_by_id={"su-method": unit},
        study_phase=StudyPhase.PHASE_II,
        owned_required_action_kinds_by_structure_unit_id={
            "su-method": ["sequence_before_related_procedure"]
        },
    )


def test_pre_enrollment_required_action_cannot_be_sent_to_post_treatment() -> None:
    result = ProtocolControlBatchDispositionHydrated(
        batch_id="batch:misplaced-action",
        coverage_manifest_id="manifest:misplaced-action",
        owned_structure_unit_ids=["su-method"],
        owned_source_span_ids=["span:method"],
        dispositions=[
            ProtocolControlUnitDisposition(
                structure_unit_id="su-method",
                disposition=StructureUnitDispositionKind.POST_TREATMENT_EXECUTION,
            )
        ],
        candidates=[],
    )
    unit = ProtocolStructureUnit(
        structure_unit_id="su-method",
        source_ref="body.p1",
        member_source_refs=["body.p1"],
        source_span_ids=["span:method"],
        unit_kind="paragraph",
        heading_path=["筛选期", "测量要求"],
        source_order=10,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.PHASE_II],
        excerpt="筛选时建议先静息再测量。",
    )

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_hydrated_result_links(
            result,
            known_procedure_targets=[],
            unit_by_id={"su-method": unit},
            study_phase=StudyPhase.PHASE_II,
            pre_enrollment_structure_unit_ids=["su-method"],
            owned_required_action_kinds_by_structure_unit_id={
                "su-method": ["prepare_participant"]
            },
        )

    assert exc_info.value.code == "REQUIRED_ACTION_DISCARDED"


def test_candidate_action_cannot_expand_to_an_unowned_procedure_stage() -> None:
    candidate = _candidate(
        candidate_id="pcc-height-method",
        source_unit_ids=["su-height-method"],
        source_span_ids=["span:height-method"],
        source_excerpt="身高测量前脱鞋并摘除头饰。",
    )
    relations = [
        ControlCrossSourceRelation(
            relation_id=f"relation-{suffix}",
            kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
            left_target_kind=ControlRelationTargetKind.CONTROL_CANDIDATE,
            left_target_id=candidate.control_candidate_id,
            right_target_kind=ControlRelationTargetKind.REQUIRED_PROCEDURE,
            right_target_id=target_id,
            affected_workflow_stage_id=stage_id,
        )
        for suffix, target_id, stage_id in (
            ("screening", "procedure-screening", "stage:screening:1"),
            ("baseline", "procedure-baseline", "stage:baseline:1"),
        )
    ]
    candidate = candidate.model_copy(
        update={
            "semantics": candidate.semantics.model_copy(
                update={"cross_source_relations": relations}
            )
        }
    )
    result = ProtocolControlBatchDispositionHydrated(
        batch_id="batch:height-method",
        coverage_manifest_id="manifest:height-method",
        owned_structure_unit_ids=["su-height-method"],
        owned_source_span_ids=["span:height-method"],
        dispositions=[
            ProtocolControlUnitDisposition(
                structure_unit_id="su-height-method",
                disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                linked_control_candidate_ids=[candidate.control_candidate_id],
            )
        ],
        candidates=[candidate],
    )
    unit = ProtocolStructureUnit(
        structure_unit_id="su-height-method",
        source_ref="body.p1",
        member_source_refs=["body.p1"],
        source_span_ids=["span:height-method"],
        unit_kind="paragraph",
        heading_path=["身高及体重", "身高"],
        source_order=1,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.PHASE_II],
        excerpt="身高测量前脱鞋并摘除头饰。",
    )

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_hydrated_result_links(
            result,
            known_procedure_targets=[
                KnownRequiredProcedureTarget(
                    catalog_item_id="procedure-screening",
                    label="筛选期身高体重测量",
                    visit_instance="screening-1",
                    review_stage=ReviewStage.SCREENING,
                    position=0,
                    source_span_ids=["span:procedure:screening"],
                ),
                KnownRequiredProcedureTarget(
                    catalog_item_id="procedure-baseline",
                    label="基线期体重测量",
                    visit_instance="baseline-1",
                    review_stage=ReviewStage.BASELINE,
                    position=1,
                    source_span_ids=["span:procedure:baseline"],
                ),
            ],
            unit_by_id={"su-height-method": unit},
            study_phase=StudyPhase.PHASE_II,
            owned_required_procedure_target_ids_by_structure_unit_id={
                "su-height-method": ["procedure-screening"]
            },
        )

    assert exc_info.value.code == "ACTION_TARGET_SCOPE_MISMATCH"
    assert "procedure-baseline" in str(exc_info.value)
    assert exc_info.value.structure_unit_ids == ("su-height-method",)
    assert exc_info.value.candidate_ids == (candidate.control_candidate_id,)


def test_uncovered_procedure_actions_are_reported_for_the_whole_batch() -> None:
    units = {
        unit_id: ProtocolStructureUnit(
            structure_unit_id=unit_id,
            source_ref=f"body.{unit_id}",
            member_source_refs=[f"body.{unit_id}"],
            source_span_ids=[f"span:{unit_id}"],
            unit_kind="paragraph",
            heading_path=["测量要求"],
            source_order=index,
            study_phase=StudyPhase.PHASE_II,
            phase_scopes=[PhaseScope.PHASE_II],
            excerpt=excerpt,
        )
        for index, (unit_id, excerpt) in enumerate(
            (
                ("su-position", "按要求保持体位。"),
                ("su-precision", "按要求记录精度。"),
            ),
            1,
        )
    }
    result = ProtocolControlBatchDispositionHydrated(
        batch_id="batch:aggregate-actions",
        coverage_manifest_id="manifest:aggregate-actions",
        owned_structure_unit_ids=list(units),
        owned_source_span_ids=sorted(
            span for unit in units.values() for span in unit.source_span_ids
        ),
        dispositions=[
            ProtocolControlUnitDisposition(
                structure_unit_id=unit_id,
                disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
                linked_procedure_catalog_item_ids=["procedure-measurement"],
            )
            for unit_id in units
        ],
        candidates=[],
    )
    target = KnownRequiredProcedureTarget(
        catalog_item_id="procedure-measurement",
        label="执行测量",
        visit_instance="screening-1",
        review_stage=ReviewStage.SCREENING,
        position=0,
        covered_action_kinds=["perform_measurement"],
        source_span_ids=["span:procedure"],
    )

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_hydrated_result_links(
            result,
            known_procedure_targets=[target],
            unit_by_id=units,
            study_phase=StudyPhase.PHASE_II,
            owned_required_action_kinds_by_structure_unit_id={
                "su-position": ["position_participant"],
                "su-precision": ["record_with_precision"],
            },
        )

    assert exc_info.value.code == "PROCEDURE_ACTION_UNCOVERED"
    assert "su-position" in str(exc_info.value)
    assert "su-precision" in str(exc_info.value)


def test_frozen_procedure_targets_override_an_ambiguous_other_visits_phrase() -> None:
    unit = ProtocolStructureUnit(
        structure_unit_id="su-mixed-visits",
        source_ref="body.p1",
        member_source_refs=["body.p1"],
        source_span_ids=["span:mixed-visits"],
        unit_kind="paragraph",
        heading_path=["测量要求"],
        source_order=1,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.PHASE_II],
        excerpt="筛选访视进行身高和体重测量，其余访视点进行体重测量。",
    )
    targets = [
        KnownRequiredProcedureTarget(
            catalog_item_id="procedure-screening",
            label="筛选期身高体重测量",
            visit_instance="筛选访视",
            review_stage=ReviewStage.SCREENING,
            position=0,
            covered_action_kinds=[
                "perform_height_measurement",
                "perform_weight_measurement",
            ],
            source_span_ids=["span:screening"],
        ),
        KnownRequiredProcedureTarget(
            catalog_item_id="procedure-baseline",
            label="基线期体重测量",
            visit_instance="基线访视",
            review_stage=ReviewStage.BASELINE,
            position=1,
            covered_action_kinds=["perform_weight_measurement"],
            source_span_ids=["span:baseline"],
        ),
    ]
    disposition = ProtocolControlUnitDisposition(
        structure_unit_id=unit.structure_unit_id,
        disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
        linked_procedure_catalog_item_ids=[
            "procedure-baseline",
            "procedure-screening",
        ],
    )

    _check_required_procedure_visit_scope(
        disposition=disposition,
        unit=unit,
        procedure_targets=targets,
        study_phase=StudyPhase.PHASE_II,
        owned_required_action_kinds=[
            "perform_height_measurement",
            "perform_weight_measurement",
        ],
        owned_required_procedure_target_ids=[
            "procedure-baseline",
            "procedure-screening",
        ],
    )


def test_structural_labels_cannot_be_promoted_to_clinical_dispositions() -> None:
    unit = ProtocolStructureUnit(
        structure_unit_id="su-heading",
        source_ref="body.p1",
        member_source_refs=["body.p1"],
        source_span_ids=["span:heading"],
        unit_kind="paragraph",
        heading_path=["研究评估和程序", "身高及体重"],
        source_order=1,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.PHASE_II],
        excerpt="身高及体重",
    )
    result = ProtocolControlBatchDispositionHydrated(
        batch_id="batch:heading",
        coverage_manifest_id="manifest:heading",
        owned_structure_unit_ids=[unit.structure_unit_id],
        owned_source_span_ids=unit.source_span_ids,
        dispositions=[
            ProtocolControlUnitDisposition(
                structure_unit_id=unit.structure_unit_id,
                disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
                linked_procedure_catalog_item_ids=["procedure-measurement"],
            )
        ],
        candidates=[],
    )

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_hydrated_result_links(
            result,
            known_procedure_targets=[],
            unit_by_id={unit.structure_unit_id: unit},
            study_phase=StudyPhase.PHASE_II,
            structural_only_structure_unit_ids=[unit.structure_unit_id],
        )

    assert exc_info.value.code == "STRUCTURAL_LABEL_PROMOTED"


def test_planned_visit_scope_requires_every_frozen_visit_node() -> None:
    expression = _explicit_obligation_dnf(
        [
            _obligation(
            source_excerpts=["在研究流程中计划的访视点，研究者应完成告知并记录。"],
            )
        ]
    )
    screening = ReviewNodeBinding(
        workflow_stage_id="stage:screening:1",
        review_stage=ReviewStage.SCREENING,
        role=ReviewNodeRole.DECIDE_AT_NODE,
    )
    baseline = ReviewNodeBinding(
        workflow_stage_id="stage:baseline:1",
        review_stage=ReviewStage.BASELINE,
        role=ReviewNodeRole.DECIDE_AT_NODE,
    )
    targets = _workflow_targets(include_baseline=True)

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_planned_visit_node_closure(
            entity_id="candidate-planned-visits",
            expressions=(expression,),
            bindings=[screening],
            workflow_targets=targets,
        )
    assert exc_info.value.code == "PLANNED_VISIT_SCOPE_DROPPED"

    baseline_attention = baseline.model_copy(update={"role": ReviewNodeRole.EARLY_ATTENTION})
    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_planned_visit_node_closure(
            entity_id="candidate-planned-visits",
            expressions=(expression,),
            bindings=[screening, baseline_attention],
            workflow_targets=targets,
        )
    assert exc_info.value.code == "PLANNED_VISIT_SCOPE_DROPPED"

    _check_planned_visit_node_closure(
        entity_id="candidate-planned-visits",
        expressions=(expression,),
        bindings=[screening, baseline],
        workflow_targets=targets,
    )

    unscheduled_expression = _explicit_obligation_dnf(
        [_obligation(source_excerpts=["非计划访视时，可根据临床需要增加检查。"])],
    )
    _check_planned_visit_node_closure(
        entity_id="candidate-unscheduled-visit",
        expressions=(unscheduled_expression,),
        bindings=[screening],
        workflow_targets=targets,
    )
from app.protocols.protocol_control_planning import plan_protocol_control_batches


_SHA = "a" * 64
_PROTOCOL = "protocol:generic-58c"
_MANIFEST = "manifest:generic-58c"


def _paragraph_unit(
    unit_id: str,
    span_id: str,
    order: int,
    excerpt: str,
    *,
    phase_scopes: list[PhaseScope] | None = None,
) -> ProtocolStructureUnit:
    return ProtocolStructureUnit(
        structure_unit_id=unit_id,
        source_ref=f"body.p{order}",
        member_source_refs=[f"body.p{order}"],
        source_span_ids=[span_id],
        unit_kind="paragraph",
        heading_path=["其他方案控制"],
        source_order=order,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=phase_scopes or [PhaseScope.SHARED],
        excerpt=excerpt,
    )


def _table_row_unit() -> ProtocolStructureUnit:
    return ProtocolStructureUnit(
        structure_unit_id="su-table",
        source_ref="body.t0.r1",
        member_source_refs=["body.t0.r1.c0", "body.t0.r1.c1"],
        source_span_ids=["span:table:a", "span:table:b"],
        unit_kind="table_row",
        table_context=TableCellContext(
            table_path=(1, 0),
            row_index=1,
            column_index=0,
            member_cell_paths=[(1, 0), (1, 1)],
            row_headers=["控制"],
            column_headers=["时间", "要求"],
        ),
        heading_path=["其他方案控制"],
        source_order=2,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.SHARED],
        excerpt="控制 | 表格要求",
    )


def _units() -> list[ProtocolStructureUnit]:
    return [
        _paragraph_unit("su-control", "span:control", 1, "必须记录用药日期"),
        _table_row_unit(),
        _paragraph_unit("su-support", "span:support", 3, "补充背景说明"),
    ]


def _manifest(
    *,
    units: list[ProtocolStructureUnit] | None = None,
    dispositions: list[StructureUnitDisposition] | None = None,
    claims_full_coverage: bool = True,
) -> ProtocolSectionCoverageManifest:
    actual_units = units or _units()
    actual_dispositions = dispositions
    if actual_dispositions is None:
        actual_dispositions = [
            StructureUnitDisposition(
                structure_unit_id="su-control",
                disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                linked_control_candidate_id="pcc-control",
            ),
            StructureUnitDisposition(
                structure_unit_id="su-table",
                disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
            ),
            StructureUnitDisposition(
                structure_unit_id="su-support",
                disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
            ),
        ]
    return ProtocolSectionCoverageManifest(
        manifest_id=_MANIFEST,
        protocol_version_id=_PROTOCOL,
        protocol_document_sha256=_SHA,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:generic-58c",
        units=actual_units,
        dispositions=actual_dispositions,
        claims_full_coverage=claims_full_coverage,
    )


def _manifest_with_control_excerpt(excerpt: str) -> ProtocolSectionCoverageManifest:
    return _manifest(
        units=[
            _paragraph_unit("su-control", "span:control", 1, excerpt),
            _table_row_unit(),
            _paragraph_unit("su-support", "span:support", 3, "补充背景说明"),
        ]
    )


def _workflow_targets(*, include_baseline: bool = False) -> list[KnownWorkflowStageTarget]:
    targets = [
        KnownWorkflowStageTarget(
            workflow_stage_id="stage:screening:1",
            review_stage=ReviewStage.SCREENING,
            display_name="筛选期",
            visit_instance="screening-1",
        )
    ]
    if include_baseline:
        targets.append(
            KnownWorkflowStageTarget(
                workflow_stage_id="stage:baseline:1",
                review_stage=ReviewStage.BASELINE,
                display_name="基线期",
                visit_instance="baseline-1",
            )
        )
    return targets


def _obligation(
    *,
    obligation_id: str = "obl-1",
    kind: ControlObligationKind = ControlObligationKind.MUST_RECORD,
    statement: str = "必须记录用药日期",
    source_span_ids: list[str] | None = None,
    source_excerpts: list[str] | None = None,
    time_constraint: TimeConstraint | None = None,
    prospective_period: ProspectivePeriod | None = None,
    modality: ControlObligationModality = ControlObligationModality.MANDATORY,
    temporal_scope: ControlTemporalScopeKind | None = None,
    requires_professional_judgment: bool = False,
) -> ControlObligationAtom:
    return ControlObligationAtom(
        obligation_id=obligation_id,
        kind=kind,
        statement=statement,
        time_constraint=time_constraint,
        prospective_period=prospective_period,
        modality=modality,
        temporal_scope=temporal_scope,
        source_span_ids=source_span_ids or ["span:control"],
        source_excerpts=source_excerpts or ["必须记录用药日期"],
        requires_professional_judgment=requires_professional_judgment,
    )


def test_best_effort_history_collection_cannot_be_hardened() -> None:
    expression = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="收集银屑病相关治疗史",
                source_excerpts=["尽可能收集银屑病相关的治疗史"],
                temporal_scope=ControlTemporalScopeKind.FULL_HISTORY,
            )
        ]
    )

    with pytest.raises(ProtocolControlGateError, match="BEST_EFFORT_MODALITY_DROPPED"):
        _check_collection_obligation_semantics(
            entity_id="candidate-history",
            obligation_expression=expression,
            bindings=[],
        )


def test_best_effort_full_history_collection_is_preserved() -> None:
    expression = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="尽可能收集银屑病相关治疗史",
                source_excerpts=["尽可能收集银屑病相关的治疗史"],
                modality=ControlObligationModality.BEST_EFFORT,
                temporal_scope=ControlTemporalScopeKind.FULL_HISTORY,
            )
        ]
    )

    _check_collection_obligation_semantics(
        entity_id="candidate-history",
        obligation_expression=expression,
        bindings=[],
    )


def test_review_guidance_cannot_replace_actual_rest_with_communication() -> None:
    excerpt = "测量前，建议参与者至少休息5分钟。"
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                statement="测量前，建议参与者至少休息5分钟",
                source_excerpts=[excerpt],
                modality=ControlObligationModality.RECOMMENDED,
            )
        ]
    )
    bindings = [
        ReviewNodeBinding(
            workflow_stage_id="stage:screening:1",
            review_stage=ReviewStage.SCREENING,
            role=ReviewNodeRole.DECIDE_AT_NODE,
            guidance="确认测量前静息建议已告知参与者",
        )
    ]

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_review_guidance_action_fidelity(
            entity_id="candidate-rest",
            units=[_paragraph_unit("su-control", "span:control", 1, excerpt)],
            obligation_expression=obligation,
            bindings=bindings,
        )

    assert exc_info.value.code == "REVIEW_GUIDANCE_ACTION_INVENTED"


def test_review_guidance_may_directly_verify_source_backed_rest() -> None:
    excerpt = "测量前，建议参与者至少休息5分钟。"
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                statement="测量前，建议参与者至少休息5分钟",
                source_excerpts=[excerpt],
                modality=ControlObligationModality.RECOMMENDED,
            )
        ]
    )

    _check_review_guidance_action_fidelity(
        entity_id="candidate-rest",
        units=[_paragraph_unit("su-control", "span:control", 1, excerpt)],
        obligation_expression=obligation,
        bindings=[
            ReviewNodeBinding(
                workflow_stage_id="stage:screening:1",
                review_stage=ReviewStage.SCREENING,
                role=ReviewNodeRole.DECIDE_AT_NODE,
                guidance="核对生命体征测量前是否实际休息至少5分钟",
            )
        ],
    )


def test_minimum_evidence_cannot_harden_recommended_rest() -> None:
    excerpt = "测量前，建议参与者至少休息5分钟。"
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                statement="测量前，建议参与者至少休息5分钟",
                source_excerpts=[excerpt],
                modality=ControlObligationModality.RECOMMENDED,
            )
        ]
    )
    evidence = [
        ControlMinimumEvidence(
            evidence_key="evidence-rest",
            fact_type="vital_signs_examination_record",
            description="生命体征记录应证明测量前参与者已休息至少5分钟",
            due_stage=ReviewStage.SCREENING,
            required_source_types=[],
        )
    ]

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_minimum_evidence_modality_fidelity(
            entity_id="candidate-rest",
            obligation_expression=obligation,
            evidence=evidence,
        )

    assert exc_info.value.code == "MINIMUM_EVIDENCE_MODALITY_DROPPED"


def test_minimum_evidence_preserves_recommended_rest() -> None:
    excerpt = "测量前，建议参与者至少休息5分钟。"
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                statement="测量前，建议参与者至少休息5分钟",
                source_excerpts=[excerpt],
                modality=ControlObligationModality.RECOMMENDED,
            )
        ]
    )


def test_protocol_appendix_is_not_participant_minimum_evidence() -> None:
    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_minimum_evidence_authority_boundary(
            entity_id="candidate-pasi-method",
            evidence=[
                ControlMinimumEvidence(
                    evidence_key="evidence-pasi",
                    fact_type="pasi_assessment",
                    description="核对PASI评分记录",
                    due_stage=ReviewStage.SCREENING,
                    required_source_types=["PASI评分记录", "附录4评分细则"],
                )
            ],
        )

    assert exc_info.value.code == "MINIMUM_EVIDENCE_AUTHORITY_SOURCE_CONFLATED"


def test_patient_reported_questionnaire_is_not_professional_judgment() -> None:
    excerpt = "DLQI是一份包含10个问题的问卷，用于评估上1周内患者主观感受。"
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                statement="使用DLQI问卷评估患者主观感受",
                source_excerpts=[excerpt],
                requires_professional_judgment=True,
            )
        ]
    )

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_professional_judgment_fidelity(
            entity_id="candidate-dlqi-method",
            obligation_expression=obligation,
            evidence=[],
        )

    assert exc_info.value.code == "SELF_REPORTED_TOOL_MARKED_PROFESSIONAL"


def test_patient_reported_questionnaire_does_not_require_researcher_assessment() -> None:
    excerpt = "DLQI是一份包含10个问题的问卷，用于评估患者主观感受。"
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                statement="使用DLQI问卷评估患者主观感受",
                source_excerpts=[excerpt],
            )
        ]
    )

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_professional_judgment_fidelity(
            entity_id="candidate-dlqi-method",
            obligation_expression=obligation,
            evidence=[
                ControlMinimumEvidence(
                    evidence_key="evidence-dlqi",
                    fact_type="completed_questionnaire",
                    description="核对已完成的DLQI问卷",
                    due_stage=ReviewStage.BASELINE,
                    required_source_types=["已完成的DLQI问卷", "研究者评估记录"],
                )
            ],
        )

    assert exc_info.value.code == "SELF_REPORTED_TOOL_RESEARCHER_EVIDENCE"


def test_authority_reference_must_be_supported_by_same_atom_excerpt() -> None:
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                statement="PASI评分须综合评估皮损并按附录4执行",
                source_excerpts=["PASI评分须综合评估皮损"],
            )
        ]
    )

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_authority_reference_provenance(
            entity_id="candidate-pasi-method",
            obligation_expression=obligation,
        )

    assert exc_info.value.code == "AUTHORITY_REFERENCE_SOURCE_DROPPED"

    _check_minimum_evidence_modality_fidelity(
        entity_id="candidate-rest",
        obligation_expression=obligation,
        evidence=[
            ControlMinimumEvidence(
                evidence_key="evidence-rest",
                fact_type="vital_signs_examination_record",
                description="核对测量前是否休息至少5分钟，并注明该项为建议项",
                due_stage=ReviewStage.SCREENING,
                required_source_types=[],
            )
        ],
    )


def test_recommended_preparation_cannot_be_recast_as_advice_given() -> None:
    excerpt = "测量前，建议参与者至少休息5分钟。"
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                statement="测量前，建议参与者至少休息5分钟",
                source_excerpts=[excerpt],
                modality=ControlObligationModality.RECOMMENDED,
            )
        ]
    )

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_participant_preparation_realization_fidelity(
            entity_id="candidate-rest",
            obligation_expression=obligation,
            user_facing_texts=["核对测量前是否建议参与者至少休息5分钟（建议项）"],
        )

    assert exc_info.value.code == "PARTICIPANT_PREPARATION_RECAST_AS_ADVICE"


def test_recommended_preparation_may_verify_actual_rest() -> None:
    excerpt = "测量前，建议参与者至少休息5分钟。"
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                statement="测量前，建议参与者至少休息5分钟",
                source_excerpts=[excerpt],
                modality=ControlObligationModality.RECOMMENDED,
            )
        ]
    )

    _check_participant_preparation_realization_fidelity(
        entity_id="candidate-rest",
        obligation_expression=obligation,
        user_facing_texts=["核对测量前参与者是否实际休息至少5分钟（建议项，非强制）"],
    )


def test_user_facing_item_count_must_match_obligation() -> None:
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="核对生命体征检查包含血压、脉搏、体温、呼吸频率四项",
                source_excerpts=["生命体征检查包括血压、脉搏、体温、呼吸频率。"],
            )
        ]
    )

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_user_facing_item_count_fidelity(
            entity_id="candidate-vital-signs",
            obligation_expression=obligation,
            user_facing_texts=["核对收缩压、舒张压、脉搏、体温、呼吸频率五项"],
        )

    assert exc_info.value.code == "USER_FACING_ITEM_COUNT_MISMATCH"


def test_history_collection_cannot_mix_two_year_window_with_full_course() -> None:
    expression = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="尽可能收集近2年病史及完整病程",
                source_excerpts=["尽可能过去2年内的病史，并记录诊断时间和病程"],
                modality=ControlObligationModality.BEST_EFFORT,
                temporal_scope=ControlTemporalScopeKind.CALENDAR_LOOKBACK,
                time_constraint=TimeConstraint(
                    anchor_type=AnchorType.SCREENING_DATE,
                    direction=TimeDirection.BEFORE,
                    upper_bound=TimeQuantity(value=2, unit=TimeUnit.YEAR),
                ),
            )
        ]
    )

    with pytest.raises(ProtocolControlGateError, match="COLLECTION_TEMPORAL_SCOPES_MIXED"):
        _check_collection_obligation_semantics(
            entity_id="candidate-history",
            obligation_expression=expression,
            bindings=[],
        )


def test_official_rule_collection_window_needs_its_own_scope() -> None:
    expression = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="按排除标准规定时间收集病史",
                source_excerpts=["排除标准中要求审查的病史时间范围遵循排除标准的规定时间收集"],
            )
        ]
    )

    with pytest.raises(ProtocolControlGateError, match="COLLECTION_TEMPORAL_SCOPE_MISSING"):
        _check_collection_obligation_semantics(
            entity_id="candidate-history",
            obligation_expression=expression,
            bindings=[],
        )


def test_screening_and_baseline_collection_keeps_both_decision_nodes() -> None:
    expression = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="在筛选和基线收集病史",
                source_excerpts=["在筛选和/或基线收集既往和现病史"],
            )
        ]
    )
    screening = ReviewNodeBinding(
        workflow_stage_id="stage:screening:1",
        review_stage=ReviewStage.SCREENING,
        role=ReviewNodeRole.DECIDE_AT_NODE,
    )

    with pytest.raises(ProtocolControlGateError, match="COLLECTION_VISIT_CLOSURE_MISSING"):
        _check_collection_obligation_semantics(
            entity_id="candidate-history",
            obligation_expression=expression,
            bindings=[screening],
        )

    _check_collection_obligation_semantics(
        entity_id="candidate-history",
        obligation_expression=expression,
        bindings=[
            screening,
            ReviewNodeBinding(
                workflow_stage_id="stage:baseline:1",
                review_stage=ReviewStage.BASELINE,
                role=ReviewNodeRole.DECIDE_AT_NODE,
            ),
        ],
    )


def test_since_previous_visit_collection_needs_later_review_node() -> None:
    expression = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="问询筛选访视以来的病史及诊治情况",
                source_excerpts=["问询筛选访视以来的病史及诊治情况"],
                temporal_scope=ControlTemporalScopeKind.SINCE_PREVIOUS_VISIT,
            )
        ]
    )

    with pytest.raises(
        ProtocolControlGateError,
        match="COLLECTION_INTERVAL_REVIEW_NODE_MISSING",
    ):
        _check_collection_obligation_semantics(
            entity_id="candidate-history-update",
            obligation_expression=expression,
            bindings=[
                ReviewNodeBinding(
                    workflow_stage_id="stage:screening:1",
                    review_stage=ReviewStage.SCREENING,
                    role=ReviewNodeRole.DECIDE_AT_NODE,
                )
            ],
        )


def _explicit_obligation_dnf(
    atoms: list[ControlObligationAtom] | None = None,
    *,
    groups: list[list[ControlObligationAtom]] | None = None,
    applies_to_trigger_branch_ids: list[str] | None = None,
) -> ControlObligationDnf:
    actual_groups = groups or [atoms or [_obligation()]]
    return ControlObligationDnf(
        groups=[
            ControlObligationGroup(
                atoms=group,
                applies_to_trigger_branch_ids=list(
                    applies_to_trigger_branch_ids or []
                ),
            )
            for group in actual_groups
        ]
    )


def test_recording_precision_cannot_be_compressed_into_generic_measurement() -> None:
    expression = _explicit_obligation_dnf(
        [
            _obligation(
                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                statement="完成身高测量",
                source_span_ids=["span:height"],
                source_excerpts=["记录参与者的身高，单位为厘米（cm），保留整数。"],
            )
        ]
    )

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_recording_precision_fidelity(
            entity_id="candidate-height",
            obligation_expression=expression,
        )

    assert exc_info.value.code == "RECORD_PRECISION_COMPRESSED"
    assert exc_info.value.obligation_source_span_ids == ("span:height",)


def test_recording_precision_can_be_preserved_across_same_source_atoms() -> None:
    source = "单位为千克（kg），保留小数点后1位。"
    expression = _explicit_obligation_dnf(
        [
            _obligation(
                obligation_id="obl-unit",
                statement="体重以kg记录",
                source_span_ids=["span:weight"],
                source_excerpts=[source],
            ),
            _obligation(
                obligation_id="obl-precision",
                statement="体重保留1位小数",
                source_span_ids=["span:weight"],
                source_excerpts=[source],
            ),
        ]
    )

    _check_recording_precision_fidelity(
        entity_id="candidate-weight",
        obligation_expression=expression,
    )


def _conditional_trigger(*excerpts: str) -> ControlConditionDnf:
    return ControlConditionDnf(
        groups=[
            ControlConditionGroup(
                atoms=[
                    ControlConditionAtom(
                        condition_atom_id=f"condition-{index}",
                        statement=excerpt,
                        source_span_ids=["span:conditional"],
                        source_excerpts=[excerpt],
                    )
                ],
                trigger_branch_id=f"branch-{index}",
            )
            for index, excerpt in enumerate(excerpts)
        ]
    )


def test_multiple_condition_action_pairs_cannot_collapse_into_one_trigger() -> None:
    source = (
        "A阳性的参与者，需要进行A检测；"
        "B阳性的参与者，需要进行B检测。"
        "若C阳性，则进行C检测。结果统一记录。"
    )
    unit = _paragraph_unit("su-conditional", "span:conditional", 4, source)
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="记录相应检测结果",
                source_span_ids=["span:conditional"],
                source_excerpts=["结果统一记录"],
            )
        ],
        applies_to_trigger_branch_ids=["branch-0"],
    )

    with pytest.raises(
        ProtocolControlGateError,
        match="CONDITIONAL_BRANCH_MAPPING_INVALID",
    ):
        _check_conditional_branch_mapping(
            entity_id="candidate:conditional",
            units=[unit],
            trigger_expression=_conditional_trigger(source[:-7]),
            obligation_expression=obligation,
        )


def test_multiple_condition_action_pairs_can_share_one_explicitly_scoped_consequence() -> None:
    source = (
        "A阳性的参与者，需要进行A检测；"
        "B阳性的参与者，需要进行B检测。"
        "若C阳性，则进行C检测。结果统一记录。"
    )
    unit = _paragraph_unit("su-conditional", "span:conditional", 4, source)
    trigger = _conditional_trigger(
        "A阳性的参与者",
        "B阳性的参与者",
        "若C阳性",
    )
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="记录相应检测结果",
                source_span_ids=["span:conditional"],
                source_excerpts=["结果统一记录"],
            )
        ],
        applies_to_trigger_branch_ids=["branch-0", "branch-1", "branch-2"],
    )

    _check_conditional_branch_mapping(
        entity_id="candidate:conditional",
        units=[unit],
        trigger_expression=trigger,
        obligation_expression=obligation,
    )


def test_single_condition_action_pair_requires_an_explicit_trigger() -> None:
    source = "若A阳性，则进行A检测。"
    unit = _paragraph_unit("su-single-conditional", "span:conditional", 5, source)
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="进行A检测",
                source_span_ids=["span:conditional"],
                source_excerpts=["则进行A检测"],
            )
        ]
    )

    with pytest.raises(ProtocolControlGateError, match="CONDITIONAL_BRANCH_MAPPING_INVALID"):
        _check_conditional_branch_mapping(
            entity_id="candidate:single-conditional",
            units=[unit],
            trigger_expression=None,
            obligation_expression=obligation,
        )


def test_conditional_mapping_ignores_trailing_clause_punctuation() -> None:
    source = "若检查结果异常，则联系研究者。"
    unit = _paragraph_unit("su-punctuated-condition", "span:conditional", 5, source)
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                statement="联系研究者",
                source_span_ids=["span:conditional"],
                source_excerpts=[source],
            )
        ]
    )

    with pytest.raises(ProtocolControlGateError, match="CONDITIONAL_BRANCH_MAPPING_INVALID"):
        _check_conditional_branch_mapping(
            entity_id="candidate:punctuated-condition",
            units=[unit],
            trigger_expression=None,
            obligation_expression=obligation,
        )


def test_communicated_conditional_instruction_is_not_a_current_trigger() -> None:
    source = "研究者应告知参与者，如果停用所选方法，需立即联系研究者。"
    unit = _paragraph_unit("su-reported-condition", "span:conditional", 5, source)
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                statement=source,
                source_span_ids=["span:conditional"],
                source_excerpts=[source],
            )
        ]
    )

    _check_conditional_branch_mapping(
        entity_id="candidate:reported-condition",
        units=[unit],
        trigger_expression=None,
        obligation_expression=obligation,
    )


def test_alternative_conditions_in_one_clause_can_share_one_consequence() -> None:
    source = "初潮前、已绝经或永久性绝育的女性无需进行妊娠试验。"
    unit = _paragraph_unit("su-alternatives", "span:conditional", 6, source)
    trigger = _conditional_trigger("初潮前", "已绝经", "永久性绝育")
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="无需进行妊娠试验",
                source_span_ids=["span:conditional"],
                source_excerpts=["无需进行妊娠试验"],
            )
        ],
        applies_to_trigger_branch_ids=["branch-0", "branch-1", "branch-2"],
    )

    _check_conditional_branch_mapping(
        entity_id="candidate:alternative-populations",
        units=[unit],
        trigger_expression=trigger,
        obligation_expression=obligation,
    )


def test_sibling_conditional_clause_does_not_leak_into_split_candidate() -> None:
    source = "绝经女性需完成FSH检查。初潮前女性无需进行妊娠试验。"
    unit = _paragraph_unit("su-split-condition", "span:conditional", 7, source)
    trigger = _conditional_trigger("初潮前女性")
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="无需进行妊娠试验",
                source_span_ids=["span:conditional"],
                source_excerpts=["无需进行妊娠试验"],
            )
        ],
        applies_to_trigger_branch_ids=["branch-0"],
    )

    _check_conditional_branch_mapping(
        entity_id="candidate:split-condition",
        units=[unit],
        trigger_expression=trigger,
        obligation_expression=obligation,
    )


def test_explicit_exception_cannot_remain_only_in_obligation_text() -> None:
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="有风险者不得进入，除非已完成充分治疗",
                source_excerpts=["有风险者不得进入，除非已完成充分治疗"],
            )
        ]
    )

    with pytest.raises(ProtocolControlGateError, match="EXCEPTION_LAYER_MISSING"):
        _check_exception_layer(
            entity_id="candidate:exception-layer",
            semantic_expressions=(obligation,),
            exception_expression=None,
        )


def test_exception_in_sibling_source_clause_does_not_leak_into_this_candidate() -> None:
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="完成胸部影像学检查",
                source_excerpts=["完成胸部影像学检查"],
            )
        ]
    )

    _check_exception_layer(
        entity_id="candidate:without-local-exception",
        semantic_expressions=(obligation,),
        exception_expression=None,
    )


def test_optional_action_cannot_be_rewritten_as_mandatory() -> None:
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="进行1次复测",
                source_excerpts=["可进行1次复测"],
            )
        ]
    )

    with pytest.raises(ProtocolControlGateError, match="OPTIONAL_ACTION_MODALITY_DROPPED"):
        _check_obligation_modality_and_event_anchor(
            entity_id="candidate:optional-action",
            obligation_expression=obligation,
        )


def test_prohibited_randomization_is_anchored_on_randomization_event() -> None:
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="不得被随机分组",
                source_excerpts=["有活动性结核证据的参与者不得被随机分组"],
                time_constraint=TimeConstraint(
                    anchor_type="randomization_date",
                    direction="before",
                ),
            ).model_copy(update={"kind": ControlObligationKind.PROHIBIT_EVENT})
        ]
    )

    with pytest.raises(ProtocolControlGateError, match="PROHIBITED_EVENT_ANCHOR_MISMATCH"):
        _check_obligation_modality_and_event_anchor(
            entity_id="candidate:randomization-event",
            obligation_expression=obligation,
        )


def test_unconditional_required_procedure_cannot_be_both_trigger_and_obligation() -> None:
    excerpt = "将根据标准程序进行病毒学检查"
    trigger = _conditional_trigger(excerpt)
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="完成病毒学检查",
                source_span_ids=["span:conditional"],
                source_excerpts=[excerpt],
            )
        ],
        applies_to_trigger_branch_ids=["branch-0"],
    )

    with pytest.raises(
        ProtocolControlGateError,
        match="ROUTINE_OBLIGATION_MISLABELED_AS_TRIGGER",
    ):
        _check_routine_action_not_trigger(
            entity_id="candidate:routine-procedure",
            trigger_expression=trigger,
            obligation_expression=obligation,
        )


def test_conditional_follow_up_action_remains_a_valid_trigger() -> None:
    excerpt = "若病毒抗体阳性，则进行核酸检测"
    trigger = _conditional_trigger(excerpt)
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="完成核酸检测",
                source_span_ids=["span:conditional"],
                source_excerpts=[excerpt],
            )
        ],
        applies_to_trigger_branch_ids=["branch-0"],
    )

    _check_routine_action_not_trigger(
        entity_id="candidate:conditional-procedure",
        trigger_expression=trigger,
        obligation_expression=obligation,
    )


def test_current_procedure_and_future_validity_must_be_separate_candidates() -> None:
    action = "应完成乙肝表面抗体检查"
    validity = "首次给药前28天内的结果有效"
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(statement=action, source_excerpts=[action]),
            _obligation(
                obligation_id="obligation-validity",
                statement=validity,
                source_excerpts=[validity],
                time_constraint=TimeConstraint(
                    anchor_type="first_dose_date",
                    direction="before",
                    upper_bound_days=28,
                ),
            ),
        ]
    )

    with pytest.raises(ProtocolControlGateError, match="MIXED_DECISION_STAGE_CONTROL"):
        _check_mixed_decision_stage_control(
            entity_id="candidate:mixed-stage",
            obligation_expression=obligation,
        )


def test_direct_complete_action_and_future_validity_must_be_separate_candidates() -> None:
    action = "完成乙肝表面抗体检测"
    validity = "首次给药前28天内的结果有效"
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(statement=action, source_excerpts=["乙肝表面抗体"]),
            _obligation(
                obligation_id="obligation-validity-direct",
                statement=validity,
                source_excerpts=[validity],
                time_constraint=TimeConstraint(
                    anchor_type="first_dose_date",
                    direction="before",
                    upper_bound_days=28,
                ),
            ),
        ]
    )

    with pytest.raises(ProtocolControlGateError, match="MIXED_DECISION_STAGE_CONTROL"):
        _check_mixed_decision_stage_control(
            entity_id="candidate:mixed-stage-direct",
            obligation_expression=obligation,
        )


def test_duplicate_atoms_in_one_dnf_group_are_rejected() -> None:
    atom = _obligation(statement="完成检查", source_excerpts=["必须记录用药日期"])
    expression = _explicit_obligation_dnf(atoms=[atom, atom.model_copy(update={"obligation_id": "obl-copy"})])
    unit = _paragraph_unit("su-duplicate-atom", "span:conditional", 9, "必须记录用药日期")

    with pytest.raises(ProtocolControlGateError, match="DNF_DUPLICATE_ATOM"):
        _check_dnf(
            expression,
            label="义务",
            entity_id="candidate:duplicate-atom",
            source_unit_ids=[unit.structure_unit_id],
            source_span_ids={"span:conditional"},
            units=[unit],
        )


def test_future_anchored_action_remains_one_coherent_obligation() -> None:
    excerpt = "首次给药前28天内完成检查"
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                statement=excerpt,
                source_excerpts=[excerpt],
                time_constraint=TimeConstraint(
                    anchor_type="first_dose_date",
                    direction="before",
                    upper_bound_days=28,
                ),
            )
        ]
    )

    _check_mixed_decision_stage_control(
        entity_id="candidate:anchored-action",
        obligation_expression=obligation,
    )


def test_post_dose_scheduled_check_is_not_an_eligibility_control() -> None:
    excerpt = "首次给药后第52周进行血清检查"
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                statement=excerpt,
                source_excerpts=[excerpt],
                time_constraint=TimeConstraint(
                    anchor_type="first_dose_date",
                    direction="after",
                    lower_bound={"value": 52, "unit": "week"},
                    upper_bound={"value": 52, "unit": "week"},
                ),
            )
        ]
    )

    with pytest.raises(
        ProtocolControlGateError,
        match="POST_ENROLLMENT_PROCEDURE_MISCLASSIFIED",
    ):
        _check_post_enrollment_procedure_classification(
            entity_id="candidate:post-dose-check",
            obligation_expression=obligation,
        )


def test_treatment_period_check_is_not_an_eligibility_control() -> None:
    excerpt = "治疗期间可根据需要进行检查"
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                statement=excerpt,
                source_excerpts=[excerpt],
                prospective_period=ProspectivePeriod(period="treatment_period"),
            )
        ]
    )

    with pytest.raises(
        ProtocolControlGateError,
        match="POST_ENROLLMENT_PROCEDURE_MISCLASSIFIED",
    ):
        _check_post_enrollment_procedure_classification(
            entity_id="candidate:study-period-check",
            obligation_expression=obligation,
        )


def test_study_period_obligation_is_not_assumed_to_start_after_enrollment() -> None:
    excerpt = "从签署知情同意书之日起持续并正确使用避孕方法"
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                statement=excerpt,
                source_excerpts=[excerpt],
                prospective_period=ProspectivePeriod(period="study_period"),
            )
        ]
    )

    _check_post_enrollment_procedure_classification(
        entity_id="candidate:icf-started-study-period-obligation",
        obligation_expression=obligation,
    )


def test_pre_dose_validity_check_remains_an_eligibility_control() -> None:
    excerpt = "首次给药前28天内完成检查"
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement=excerpt,
                source_excerpts=[excerpt],
                time_constraint=TimeConstraint(
                    anchor_type="first_dose_date",
                    direction="before",
                    upper_bound_days=28,
                ),
            )
        ]
    )

    _check_post_enrollment_procedure_classification(
        entity_id="candidate:pre-dose-check",
        obligation_expression=obligation,
    )


def test_screening_and_first_dose_triggers_require_separate_controls() -> None:
    trigger = ControlConditionDnf(
        groups=[
            ControlConditionGroup(
                trigger_branch_id="branch-screening",
                atoms=[
                    ControlConditionAtom(
                        condition_atom_id="condition-screening",
                        statement="筛选时结果阳性",
                        source_span_ids=["span:control"],
                        source_excerpts=["筛选时"],
                        time_constraint=TimeConstraint(
                            anchor_type="screening_date", direction="on"
                        ),
                    )
                ],
            ),
            ControlConditionGroup(
                trigger_branch_id="branch-first-dose",
                atoms=[
                    ControlConditionAtom(
                        condition_atom_id="condition-first-dose",
                        statement="首次给药前结果阳性",
                        source_span_ids=["span:control"],
                        source_excerpts=["首次给药前"],
                        time_constraint=TimeConstraint(
                            anchor_type="first_dose_date", direction="before"
                        ),
                    )
                ],
            ),
        ]
    )

    with pytest.raises(ProtocolControlGateError, match="MIXED_TRIGGER_DECISION_STAGES"):
        _check_mixed_trigger_decision_stages(
            entity_id="candidate:mixed-trigger-stages",
            trigger_expression=trigger,
        )


def test_one_trigger_atom_cannot_hide_screening_inside_first_dose_anchor() -> None:
    excerpt = "筛选时或研究药物首次给药前妊娠试验结果为阳性"
    trigger = ControlConditionDnf(
        groups=[
            ControlConditionGroup(
                trigger_branch_id="branch-mixed",
                atoms=[
                    ControlConditionAtom(
                        condition_atom_id="condition-mixed",
                        statement=excerpt,
                        source_span_ids=["span:control"],
                        source_excerpts=[excerpt],
                        time_constraint=TimeConstraint(
                            anchor_type="first_dose_date", direction="before"
                        ),
                    )
                ],
            )
        ]
    )

    with pytest.raises(ProtocolControlGateError, match="MIXED_TRIGGER_DECISION_STAGES"):
        _check_mixed_trigger_decision_stages(
            entity_id="candidate:hidden-screening-trigger",
            trigger_expression=trigger,
        )


def test_separate_trigger_atoms_preserve_screening_and_first_dose_stages() -> None:
    screening = ControlConditionDnf(
        groups=[
            ControlConditionGroup(
                trigger_branch_id="branch-screening",
                atoms=[
                    ControlConditionAtom(
                        condition_atom_id="condition-screening",
                        statement="筛选时结果为阳性",
                        source_span_ids=["span:control"],
                        source_excerpts=["筛选时结果为阳性"],
                        time_constraint=TimeConstraint(
                            anchor_type="screening_date", direction="on"
                        ),
                    )
                ],
            )
        ]
    )
    first_dose = ControlConditionDnf(
        groups=[
            ControlConditionGroup(
                trigger_branch_id="branch-first-dose",
                atoms=[
                    ControlConditionAtom(
                        condition_atom_id="condition-first-dose",
                        statement="研究药物首次给药前结果为阳性",
                        source_span_ids=["span:control"],
                        source_excerpts=["研究药物首次给药前结果为阳性"],
                        time_constraint=TimeConstraint(
                            anchor_type="first_dose_date", direction="before"
                        ),
                    )
                ],
            )
        ]
    )

    _check_mixed_trigger_decision_stages(
        entity_id="candidate:screening-only",
        trigger_expression=screening,
    )
    _check_mixed_trigger_decision_stages(
        entity_id="candidate:first-dose-only",
        trigger_expression=first_dose,
    )


def test_screening_to_first_dose_interval_is_not_two_decision_stages() -> None:
    excerpt = "筛选后至研究药物首次给药前不得使用限制药物"
    trigger = ControlConditionDnf(
        groups=[
            ControlConditionGroup(
                trigger_branch_id="branch-window",
                atoms=[
                    ControlConditionAtom(
                        condition_atom_id="condition-window",
                        statement=excerpt,
                        source_span_ids=["span:control"],
                        source_excerpts=[excerpt],
                        time_constraint=TimeConstraint(
                            anchor_type="first_dose_date", direction="before"
                        ),
                    )
                ],
            )
        ]
    )

    _check_mixed_trigger_decision_stages(
        entity_id="candidate:screening-to-dose-window",
        trigger_expression=trigger,
    )


def test_exemption_cannot_be_strengthened_to_prohibition() -> None:
    excerpt = "初潮前女性无需进行妊娠试验"
    obligation = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                kind=ControlObligationKind.PROHIBIT_EVENT,
                statement="禁止进行妊娠试验",
                source_excerpts=[excerpt],
            )
        ]
    )

    with pytest.raises(ProtocolControlGateError, match="EXEMPTION_MODALITY_OVERSTATED"):
        _check_obligation_modality_and_event_anchor(
            entity_id="candidate:exemption",
            obligation_expression=obligation,
        )


def _evidence(stage: ReviewStage = ReviewStage.SCREENING) -> list[ControlMinimumEvidence]:
    return [
        ControlMinimumEvidence(
            evidence_key=f"evidence-{stage.value}",
            fact_type="medication_exposure",
            description="核对用药资料",
            due_stage=stage,
            required_source_types=["原始资料"],
        )
    ]


def _control(
    *,
    control_id: str = "pctrl-1",
    source_unit_ids: list[str] | None = None,
    source_span_ids: list[str] | None = None,
    obligation_expression: ControlObligationDnf | None = None,
    obligation_combination: str = "all",
    trigger_expression: ControlConditionDnf | None = None,
    exception_expression: ControlExceptionDnf | None = None,
    bindings: list[ReviewNodeBinding] | None = None,
    time_constraint: TimeConstraint | None = None,
    cross_source_relations: list[ControlCrossSourceRelation] | None = None,
    obligations: list[ControlObligationAtom] | None = None,
    minimum_evidence: list[ControlMinimumEvidence] | None = None,
) -> ProtocolReviewControl:
    actual_bindings = bindings or [
        ReviewNodeBinding(
            workflow_stage_id="stage:screening:1",
            review_stage=ReviewStage.SCREENING,
            role=ReviewNodeRole.DECIDE_AT_NODE,
        )
    ]
    actual_evidence = minimum_evidence
    if actual_evidence is None:
        decision_stages = {
            binding.review_stage
            for binding in actual_bindings
            if binding.role == ReviewNodeRole.DECIDE_AT_NODE
        }
        if not decision_stages:
            decision_stages = {ReviewStage.SCREENING}
        actual_evidence = [item for stage in sorted(decision_stages) for item in _evidence(stage)]
    return ProtocolReviewControl(
        protocol_control_id=control_id,
        display_ordinal=1,
        protocol_version_id=_PROTOCOL,
        study_phase=StudyPhase.PHASE_II,
        title="用药资料控制",
        applicable_population="拟入组受试者",
        trigger_condition=None,
        obligations=obligations or [],
        obligation_combination=obligation_combination,
        trigger_expression=trigger_expression,
        obligation_expression=obligation_expression
        if obligation_expression is not None
        else _explicit_obligation_dnf(),
        exception_expression=exception_expression,
        control_time_constraint=time_constraint,
        review_node_bindings=actual_bindings,
        minimum_evidence=actual_evidence,
        source_span_ids=source_span_ids or ["span:control"],
        source_structure_unit_ids=source_unit_ids or ["su-control"],
        cross_source_relations=cross_source_relations or [],
    )


def _candidate(
    *,
    candidate_id: str = "pcc-control",
    title: str = "用药资料控制",
    source_unit_ids: list[str] | None = None,
    source_span_ids: list[str] | None = None,
    source_excerpt: str = "必须记录用药日期",
) -> ProtocolControlCandidate:
    actual_unit_ids = source_unit_ids or ["su-control"]
    actual_span_ids = source_span_ids or ["span:control"]
    semantics = ProtocolControlCandidateSemantics(
        title=title,
        applicable_population="拟入组受试者",
        control_candidate_id=candidate_id,
        applicability_expression=None,
        trigger_expression=None,
        obligation_expression=_explicit_obligation_dnf(
            atoms=[
                _obligation(
                    source_span_ids=actual_span_ids,
                    source_excerpts=[source_excerpt] * len(actual_span_ids),
                    statement=source_excerpt,
                )
            ]
        ),
        exception_expression=None,
        review_node_bindings=[
            ReviewNodeBinding(
                workflow_stage_id="stage:screening:1",
                review_stage=ReviewStage.SCREENING,
                role=ReviewNodeRole.DECIDE_AT_NODE,
            )
        ],
        minimum_evidence=_evidence(),
        source_structure_unit_ids=actual_unit_ids,
        source_span_ids=actual_span_ids,
        cross_source_relations=[],
    )
    return ProtocolControlCandidate(
        control_candidate_id=candidate_id,
        protocol_version_id=_PROTOCOL,
        study_phase=StudyPhase.PHASE_II,
        frozen_structure_unit_ids=actual_unit_ids,
        title=title,
        applicable_population="拟入组受试者",
        source_span_ids=actual_span_ids,
        semantics=semantics,
    )


def _catalog(
    controls: list[ProtocolReviewControl],
    *,
    allowed_spans: list[str] | None = None,
) -> PublishedProtocolControlCatalog:
    return PublishedProtocolControlCatalog(
        catalog_id="catalog:generic-58c",
        protocol_version_id=_PROTOCOL,
        protocol_document_sha256=_SHA,
        study_phase=StudyPhase.PHASE_II,
        coverage_manifest_id=_MANIFEST,
        allowed_source_span_ids=allowed_spans
        or ["span:control", "span:support", "span:table:a", "span:table:b"],
        controls=controls,
    )


def _workflow_inputs(
    targets: list[KnownWorkflowStageTarget],
) -> list[WorkflowStage]:
    return [
        WorkflowStage(
            workflow_stage_id=target.workflow_stage_id,
            stage=target.review_stage,
            display_name=target.display_name,
            visit_instance=target.visit_instance,
            visit_window=target.visit_window,
        )
        for target in targets
    ]


def _plan(
    manifest: ProtocolSectionCoverageManifest,
    workflow_targets: list[KnownWorkflowStageTarget],
) -> ProtocolControlBatchPlan:
    return plan_protocol_control_batches(
        manifest,
        max_owned_units_per_batch=64,
        workflow_stages=_workflow_inputs(workflow_targets),
    )


def _result_candidates(
    manifest: ProtocolSectionCoverageManifest,
) -> list[ProtocolControlCandidate]:
    units = {unit.structure_unit_id: unit for unit in manifest.units}
    other_unit_ids = [
        item.structure_unit_id
        for item in manifest.dispositions
        if item.disposition == StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
    ]
    if not other_unit_ids and "su-control" in units:
        other_unit_ids = ["su-control"]

    candidates: list[ProtocolControlCandidate] = []
    for unit_id in other_unit_ids:
        unit = units[unit_id]
        source_span_ids = sorted(unit.source_span_ids)
        source_excerpt = unit.excerpt
        count = 2 if unit_id == "su-control" else 1
        for ordinal in range(count):
            candidate_id = (
                "pcc-control"
                if unit_id == "su-control" and ordinal == 0
                else (
                    "pcc-control-2"
                    if unit_id == "su-control"
                    else f"pcc-{unit_id}-{ordinal + 1}"
                )
            )
            candidates.append(
                _candidate(
                    candidate_id=candidate_id,
                    title=(
                        "用药资料控制"
                        if unit_id == "su-control"
                        else f"其他控制候选-{unit_id}"
                    ),
                    source_unit_ids=[unit_id],
                    source_span_ids=source_span_ids,
                    source_excerpt=source_excerpt,
                )
            )
    return candidates


def _hydrated_batch_results(
    manifest: ProtocolSectionCoverageManifest,
    plan: ProtocolControlBatchPlan,
) -> list[ProtocolControlBatchDispositionHydrated]:
    candidates = _result_candidates(manifest)
    candidate_unit_ids = {
        candidate.control_candidate_id: set(candidate.frozen_structure_unit_ids)
        for candidate in candidates
    }
    results: list[ProtocolControlBatchDispositionHydrated] = []
    for batch in plan.batches:
        owned_ids = set(batch.owned_structure_unit_ids)
        batch_candidates = [
            candidate
            for candidate in candidates
            if candidate_unit_ids[candidate.control_candidate_id] <= owned_ids
        ]
        candidate_ids_by_unit: dict[str, list[str]] = {}
        for candidate in batch_candidates:
            for unit_id in candidate.frozen_structure_unit_ids:
                candidate_ids_by_unit.setdefault(unit_id, []).append(
                    candidate.control_candidate_id
                )
        dispositions = []
        for unit_id in batch.owned_structure_unit_ids:
            linked_ids = sorted(candidate_ids_by_unit.get(unit_id, []))
            dispositions.append(
                ProtocolControlUnitDisposition(
                    structure_unit_id=unit_id,
                    disposition=(
                        StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
                        if linked_ids
                        else StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT
                    ),
                    linked_control_candidate_ids=linked_ids,
                )
            )
        results.append(
            ProtocolControlBatchDispositionHydrated(
                batch_id=batch.batch_id,
                coverage_manifest_id=manifest.manifest_id,
                owned_structure_unit_ids=list(batch.owned_structure_unit_ids),
                owned_source_span_ids=list(batch.owned_source_span_ids),
                dispositions=dispositions,
                candidates=batch_candidates,
            )
        )
    return results


def _gate(
    *,
    control: ProtocolReviewControl | None = None,
    controls: list[ProtocolReviewControl] | None = None,
    manifest: ProtocolSectionCoverageManifest | None = None,
    catalog: PublishedProtocolControlCatalog | None = None,
    candidates: list[ProtocolControlCandidate] | None = None,
    workflow_targets: list[KnownWorkflowStageTarget] | None = None,
    official_targets: list[KnownOfficialRuleTarget] | None = None,
    plan: ProtocolControlBatchPlan | None = None,
    batch_dispositions: list[ProtocolControlBatchDispositionHydrated] | None = None,
) -> PublishedProtocolControlCatalog:
    actual_manifest = manifest or _manifest()
    actual_catalog = catalog or _catalog(controls or [control or _control()])
    actual_workflow = workflow_targets if workflow_targets is not None else _workflow_targets()
    actual_plan = plan or _plan(actual_manifest, actual_workflow)
    actual_results = (
        batch_dispositions
        if batch_dispositions is not None
        else _hydrated_batch_results(actual_manifest, actual_plan)
    )
    return validate_protocol_control_publication(
        actual_manifest,
        actual_catalog,
        actual_plan,
        actual_results,
        candidates=candidates or [],
        workflow_stage_targets=actual_workflow,
        official_targets=official_targets or [],
    )


def _gate_control_with_manifest(
    control: ProtocolReviewControl,
    manifest: ProtocolSectionCoverageManifest,
    *,
    workflow_targets: list[KnownWorkflowStageTarget] | None = None,
) -> PublishedProtocolControlCatalog:
    actual_workflow = workflow_targets or _workflow_targets()
    plan = _plan(manifest, actual_workflow)
    batch_dispositions = []
    for result in _hydrated_batch_results(manifest, plan):
        candidates = []
        for candidate in result.candidates:
            semantics = candidate.semantics.model_copy(
                update={
                    "title": control.title,
                    "applicable_population": control.applicable_population,
                    "trigger_expression": control.trigger_expression,
                    "obligation_expression": control.obligation_expression,
                    "exception_expression": control.exception_expression,
                    "review_node_bindings": control.review_node_bindings,
                    "minimum_evidence": control.minimum_evidence,
                }
            )
            candidates.append(candidate.model_copy(update={"semantics": semantics}))
        batch_dispositions.append(result.model_copy(update={"candidates": candidates}))
    return _gate(
        control=control,
        candidates=[],
        manifest=manifest,
        workflow_targets=actual_workflow,
        plan=plan,
        batch_dispositions=batch_dispositions,
    )


def _semantic_plan_and_resolution(
    manifest: ProtocolSectionCoverageManifest,
    *,
    unresolved: bool = False,
) -> tuple[object, object]:
    plan = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=64,
        context_radius=1,
    )
    assert len(plan.packages) == 1
    package = plan.packages[0]
    target = package.owned_units[0]
    span_index = package.frozen_source_span_ids.index(target.source_span_ids[0])
    polarity = (
        PhaseApplicabilityEvidencePolarity.UNRESOLVED
        if unresolved
        else PhaseApplicabilityEvidencePolarity.SUPPORTS
    )
    candidate = PhaseApplicabilityCandidateDraft(
        scope=PhaseScope.PHASE_II,
        supporting_evidence_indexes=[] if unresolved else [0],
        unresolved_evidence_indexes=[0] if unresolved else [],
    )
    draft = PhaseApplicabilityResolutionDraft(
        unit_index=0,
        evidence=[
            PhaseApplicabilityEvidenceDraft(
                polarity=polarity,
                source_unit_indexes=[0],
                source_span_indexes=[span_index],
                excerpt=target.excerpt,
                rationale="冻结来源直接支持该期别语义处置",
            )
        ],
        candidates=[candidate],
        final_disposition=(
            PhaseApplicabilityDisposition.UNRESOLVED
            if unresolved
            else PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE
        ),
        rationale="依据冻结来源完成期别语义判断",
        unresolved_reason="缺少足够的跨章节期别证据" if unresolved else None,
    )
    resolutions = hydrate_phase_applicability_resolution(package, draft)
    return plan, resolutions


def _semantic_view(
    manifest: ProtocolSectionCoverageManifest,
    *,
    unresolved: bool = False,
) -> object:
    plan, resolutions = _semantic_plan_and_resolution(
        manifest,
        unresolved=unresolved,
    )
    return build_resolved_full_protocol_coverage_view(
        manifest,
        plan,
        [resolutions],
    )


def test_valid_explicit_dnf_candidate_and_control_publish() -> None:
    # The new publication path does not need the singular 5.8a manifest
    # dispositions; hydrated batch results are the authority.
    manifest = _manifest(dispositions=[], claims_full_coverage=False)
    workflow = _workflow_targets()
    plan = _plan(manifest, workflow)
    batch_results = _hydrated_batch_results(manifest, plan)
    control_unit = next(
        item
        for result in batch_results
        for item in result.dispositions
        if item.structure_unit_id == "su-control"
    )
    assert control_unit.linked_control_candidate_ids == [
        "pcc-control",
        "pcc-control-2",
    ]
    assert (
        validate_protocol_control_publication(
            manifest,
            _catalog([_control()]),
            plan,
            batch_results,
            workflow_stage_targets=workflow,
        )
        is not None
    )


def test_resolved_phase_view_enables_publish_without_mutating_frozen_scopes() -> None:
    unresolved_unit = _paragraph_unit(
        "su-control",
        "span:control",
        1,
        "必须记录用药日期",
        phase_scopes=[PhaseScope.UNKNOWN],
    )
    manifest = _manifest(
        units=[unresolved_unit, _units()[1], _units()[2]],
        dispositions=[],
        claims_full_coverage=False,
    )
    view = _semantic_view(manifest)

    assert manifest.units[0].phase_scopes == [PhaseScope.UNKNOWN]
    assert view.source_manifest is manifest
    assert view.accepted is True
    assert view.claims_full_coverage is True
    assert view.pending_structure_unit_ids == ()
    assert (
        view.disposition_for("su-control")
        == PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE
    )

    workflow = _workflow_targets()
    plan = _plan(manifest, workflow)
    batch_results = _hydrated_batch_results(manifest, plan)
    published = validate_protocol_control_publication(
        manifest,
        _catalog([_control()]),
        plan,
        batch_results,
        workflow_stage_targets=workflow,
        phase_applicability_view=view,
    )
    assert published.coverage_manifest_id == manifest.manifest_id


@pytest.mark.parametrize(
    ("forged_field", "forged_value"),
    [
        ("excerpt", "伪造的来源摘录"),
        ("source_span_ids", ["span:forged"]),
        ("member_source_refs", ["body.p1", "body.p1.c1"]),
        ("table_context", _table_row_unit().table_context),
    ],
)
def test_resolved_phase_view_rejects_same_id_forged_source_payload(
    forged_field: str,
    forged_value: object,
) -> None:
    unresolved_unit = _paragraph_unit(
        "su-control",
        "span:control",
        1,
        "必须记录用药日期",
        phase_scopes=[PhaseScope.UNKNOWN],
    )
    manifest = _manifest(
        units=[unresolved_unit, _units()[1], _units()[2]],
        dispositions=[],
        claims_full_coverage=False,
    )
    plan, resolutions = _semantic_plan_and_resolution(manifest)
    package = plan.packages[0]
    forged_unit = package.owned_units[0].model_copy(
        update={forged_field: forged_value}
    )
    forged_package = package.model_copy(update={"owned_units": [forged_unit]})
    forged_plan = plan.model_copy(update={"packages": [forged_package]})

    view = build_resolved_full_protocol_coverage_view(
        manifest,
        forged_plan,
        [resolutions],
    )
    assert view.accepted is False
    assert view.pending_structure_unit_ids == ("su-control",)
    assert "PHASE_PACKAGE_SOURCE_UNIT_MISMATCH" in {
        item.code for item in view.issues
    }


@pytest.mark.parametrize(
    ("forged_field", "forged_value", "expected_code"),
    [
        ("protocol_document_sha256", "b" * 64, "PHASE_PACKAGE_HASH_MISMATCH"),
        ("snapshot_id", "snapshot:stale", "PHASE_PACKAGE_SNAPSHOT_MISMATCH"),
    ],
)
def test_resolved_phase_view_rejects_stale_package_identity(
    forged_field: str,
    forged_value: object,
    expected_code: str,
) -> None:
    unresolved_unit = _paragraph_unit(
        "su-control",
        "span:control",
        1,
        "必须记录用药日期",
        phase_scopes=[PhaseScope.UNKNOWN],
    )
    manifest = _manifest(
        units=[unresolved_unit, _units()[1], _units()[2]],
        dispositions=[],
        claims_full_coverage=False,
    )
    plan, resolutions = _semantic_plan_and_resolution(manifest)
    forged_package = plan.packages[0].model_copy(
        update={forged_field: forged_value}
    )
    forged_plan = plan.model_copy(update={"packages": [forged_package]})

    view = build_resolved_full_protocol_coverage_view(
        manifest,
        forged_plan,
        [resolutions],
    )
    assert view.accepted is False
    assert view.pending_structure_unit_ids == ("su-control",)
    assert expected_code in {item.code for item in view.issues}


def test_resolved_phase_view_rejects_missing_or_extra_source_units() -> None:
    unresolved_unit = _paragraph_unit(
        "su-control",
        "span:control",
        1,
        "必须记录用药日期",
        phase_scopes=[PhaseScope.UNKNOWN],
    )
    manifest = _manifest(
        units=[unresolved_unit, _units()[1], _units()[2]],
        dispositions=[],
        claims_full_coverage=False,
    )
    plan, resolutions = _semantic_plan_and_resolution(manifest)
    package = plan.packages[0]

    extra_context = _paragraph_unit(
        "su-extra",
        "span:extra",
        4,
        "不属于当前全文覆盖清单的来源",
    )
    extra_plan = plan.model_copy(
        update={
            "packages": [
                package.model_copy(
                    update={"context_units": [*package.context_units, extra_context]}
                )
            ]
        }
    )
    extra_view = build_resolved_full_protocol_coverage_view(
        manifest,
        extra_plan,
        [resolutions],
    )
    assert extra_view.accepted is False
    assert "PHASE_PACKAGE_UNIT_OUTSIDE_MANIFEST" in {
        item.code for item in extra_view.issues
    }

    missing_plan = plan.model_copy(
        update={
            "packages": [
                package.model_copy(update={"owned_units": []})
            ]
        }
    )
    missing_view = build_resolved_full_protocol_coverage_view(
        manifest,
        missing_plan,
        [resolutions],
    )
    assert missing_view.accepted is False
    assert "PHASE_PLAN_OWNED_SCOPE_MISMATCH" in {
        item.code for item in missing_view.issues
    }


def test_unresolved_phase_view_remains_pending_and_blocks_publication() -> None:
    unresolved_unit = _paragraph_unit(
        "su-control",
        "span:control",
        1,
        "必须记录用药日期",
        phase_scopes=[PhaseScope.UNKNOWN],
    )
    manifest = _manifest(
        units=[unresolved_unit, _units()[1], _units()[2]],
        dispositions=[],
        claims_full_coverage=False,
    )
    view = _semantic_view(manifest, unresolved=True)
    assert view.accepted is False
    assert view.pending_structure_unit_ids == ("su-control",)
    assert "PHASE_APPLICABILITY_UNRESOLVED" in {item.code for item in view.issues}

    workflow = _workflow_targets()
    plan = _plan(manifest, workflow)
    batch_results = _hydrated_batch_results(manifest, plan)
    with pytest.raises(ProtocolControlGateError, match="PHASE_APPLICABILITY_UNRESOLVED"):
        validate_protocol_control_publication(
            manifest,
            _catalog([_control()]),
            plan,
            batch_results,
            workflow_stage_targets=workflow,
            phase_applicability_view=view,
        )


def test_opposite_phase_requires_explicit_phase_excluded_disposition() -> None:
    opposite_unit = _paragraph_unit(
        "su-control",
        "span:control",
        1,
        "仅限 III 期执行的控制",
        phase_scopes=[PhaseScope.PHASE_III],
    )
    manifest = _manifest(
        units=[opposite_unit, _units()[1], _units()[2]],
        dispositions=[],
        claims_full_coverage=False,
    )
    plan = plan_phase_applicability_batches(manifest, max_owned_units_per_batch=64)
    view = build_resolved_full_protocol_coverage_view(manifest, plan, [])
    assert view.accepted is True
    assert view.phase_excluded_structure_unit_ids == ("su-control",)

    workflow = _workflow_targets()
    control_plan = _plan(manifest, workflow)
    batch_results = _hydrated_batch_results(manifest, control_plan)
    with pytest.raises(ProtocolControlGateError, match="PHASE_EXCLUDED_DISPOSITION_REQUIRED"):
        validate_protocol_control_publication(
            manifest,
            _catalog([]),
            control_plan,
            batch_results,
            workflow_stage_targets=workflow,
            phase_applicability_view=view,
        )

    excluded_results = []
    for result in batch_results:
        dispositions = [
            item.model_copy(
                update={
                    "disposition": (
                        StructureUnitDispositionKind.PHASE_EXCLUDED
                        if item.structure_unit_id == "su-control"
                        else item.disposition
                    ),
                    "linked_control_candidate_ids": (
                        []
                        if item.structure_unit_id == "su-control"
                        else item.linked_control_candidate_ids
                    ),
                }
            )
            for item in result.dispositions
        ]
        candidates = [
            candidate
            for candidate in result.candidates
            if "su-control" not in candidate.frozen_structure_unit_ids
        ]
        excluded_results.append(
            result.model_copy(update={"dispositions": dispositions, "candidates": candidates})
        )
    assert (
        validate_protocol_control_publication(
            manifest,
            _catalog([]),
            control_plan,
            excluded_results,
            workflow_stage_targets=workflow,
            phase_applicability_view=view,
        ).coverage_manifest_id
        == manifest.manifest_id
    )


def test_mixed_table_row_cannot_be_flattened_without_member_contract() -> None:
    mixed_row = _table_row_unit().model_copy(
        update={
            "phase_scopes": [PhaseScope.MIXED],
            "excerpt": "II 期要求 | III 期要求",
        }
    )
    manifest = _manifest(
        units=[mixed_row, _paragraph_unit("su-support", "span:support", 3, "补充背景说明")],
        dispositions=[],
        claims_full_coverage=False,
    )
    view = _semantic_view(manifest)
    assert view.accepted is False
    assert view.pending_structure_unit_ids == ("su-table",)
    assert "MIXED_UNIT_REQUIRES_ATOMIZATION" in {
        item.code for item in view.issues
    }


def test_legacy_only_completion_cannot_publish() -> None:
    manifest = _manifest()
    report = check_protocol_control_publication(
        manifest,
        _catalog([]),
    )
    assert not report.accepted
    assert report.issues[0].code == "PLAN_REQUIRED_FOR_PUBLICATION"


def test_plan_without_batch_results_cannot_publish() -> None:
    manifest = _manifest()
    workflow = _workflow_targets()
    plan = _plan(manifest, workflow)
    with pytest.raises(ProtocolControlGateError, match="BATCH_DISPOSITIONS_REQUIRED"):
        validate_protocol_control_publication(
            manifest,
            _catalog([]),
            plan,
            (),
        )


def test_batch_results_without_plan_cannot_publish() -> None:
    manifest = _manifest()
    workflow = _workflow_targets()
    plan = _plan(manifest, workflow)
    batch_results = _hydrated_batch_results(manifest, plan)
    with pytest.raises(ProtocolControlGateError, match="PLAN_REQUIRED_FOR_BATCH_RESULTS"):
        validate_protocol_control_publication(
            manifest,
            _catalog([]),
            None,
            batch_results,
        )


def test_standalone_candidate_cannot_bypass_hydrated_results() -> None:
    manifest = _manifest()
    workflow = _workflow_targets()
    plan = _plan(manifest, workflow)
    batch_results = _hydrated_batch_results(manifest, plan)
    with pytest.raises(ProtocolControlGateError, match="STANDALONE_CANDIDATES_NOT_ALLOWED"):
        validate_protocol_control_publication(
            manifest,
            _catalog([]),
            plan,
            batch_results,
            candidates=[_candidate()],
        )


def test_unknown_control_unit_stops_after_complete_batch_disposition() -> None:
    """Phase resolution remains a separate route; this gate only stops."""

    unresolved = _paragraph_unit(
        "su-control",
        "span:control",
        1,
        "必须记录用药日期",
        phase_scopes=[PhaseScope.UNKNOWN],
    )
    manifest = _manifest(
        units=[unresolved, _units()[1], _units()[2]],
        dispositions=[],
        claims_full_coverage=False,
    )
    workflow = _workflow_targets()
    plan = _plan(manifest, workflow)
    batch_results = _hydrated_batch_results(manifest, plan)
    with pytest.raises(ProtocolControlGateError) as caught:
        validate_protocol_control_publication(
            manifest,
            _catalog([_control()]),
            plan,
            batch_results,
        )
    assert caught.value.code == "PHASE_APPLICABILITY_UNRESOLVED"


def test_legacy_singular_candidate_link_does_not_truncate_hydrated_plural_links() -> None:
    manifest = _manifest()
    workflow = _workflow_targets()
    plan = _plan(manifest, workflow)
    batch_results = _hydrated_batch_results(manifest, plan)
    legacy_dispositions = list(manifest.dispositions)
    legacy_dispositions[0] = legacy_dispositions[0].model_copy(
        update={"linked_control_candidate_id": "pcc-legacy-only"}
    )
    manifest = manifest.model_copy(update={"dispositions": legacy_dispositions})
    assert (
        validate_protocol_control_publication(
            manifest,
            _catalog([_control()]),
            plan,
            batch_results,
        ).coverage_manifest_id
        == _MANIFEST
    )
    control_unit = next(
        item
        for result in batch_results
        for item in result.dispositions
        if item.structure_unit_id == "su-control"
    )
    assert control_unit.linked_control_candidate_ids == [
        "pcc-control",
        "pcc-control-2",
    ]


def test_hydrated_plural_candidate_links_must_be_bidirectionally_closed() -> None:
    manifest = _manifest(dispositions=[], claims_full_coverage=False)
    workflow = _workflow_targets()
    plan = _plan(manifest, workflow)
    batch_results = _hydrated_batch_results(manifest, plan)
    result = batch_results[0]
    control_disposition = result.dispositions[0].model_copy(
        update={"linked_control_candidate_ids": ["pcc-control"]}
    )
    incomplete_result = result.model_copy(
        update={
            "dispositions": [control_disposition, *result.dispositions[1:]],
        }
    )
    with pytest.raises(ProtocolControlGateError, match="BATCH_CANDIDATE_LINK_INCOMPLETE"):
        validate_protocol_control_publication(
            manifest,
            _catalog([_control()]),
            plan,
            [incomplete_result],
        )


def test_phase_unknown_and_source_escape_are_stops() -> None:
    unresolved = _paragraph_unit(
        "su-control",
        "span:control",
        1,
        "必须记录用药日期",
        phase_scopes=[PhaseScope.UNKNOWN],
    )
    with pytest.raises(ProtocolControlGateError, match="PHASE_APPLICABILITY_UNRESOLVED"):
        _gate(manifest=_manifest(units=[unresolved, _units()[1], _units()[2]]))

    escaped = _control(source_unit_ids=["su-support"], source_span_ids=["span:control"])
    escaped_dispositions = [
        StructureUnitDisposition(
            structure_unit_id="su-control",
            disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
        ),
        StructureUnitDisposition(
            structure_unit_id="su-table",
            disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
        ),
        StructureUnitDisposition(
            structure_unit_id="su-support",
            disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
            linked_control_candidate_id="pcc-escaped",
        ),
    ]
    with pytest.raises(ProtocolControlGateError, match="SOURCE_UNIT_SCOPE_ESCAPE"):
        _gate(control=escaped, candidates=[], manifest=_manifest(dispositions=escaped_dispositions))


def test_frozen_workflow_target_and_review_stage_identity_are_required() -> None:
    with pytest.raises(ProtocolControlGateError, match="WORKFLOW_STAGE_TARGETS_MISSING"):
        _gate(workflow_targets=[])

    wrong_binding = ReviewNodeBinding(
        workflow_stage_id="stage:screening:1",
        review_stage=ReviewStage.BASELINE,
        role=ReviewNodeRole.DECIDE_AT_NODE,
    )
    with pytest.raises(ProtocolControlGateError, match="WORKFLOW_REVIEW_STAGE_MISMATCH"):
        _gate(control=_control(bindings=[wrong_binding]), candidates=[])


def test_first_dose_anchor_cannot_be_guessed_from_screening() -> None:
    excerpt = "首次给药前30天不得使用药物"
    time = TimeConstraint(
        anchor_type="screening_date",
        direction="before",
        upper_bound_days=30,
    )
    control = _control(
        time_constraint=time,
        obligation_expression=_explicit_obligation_dnf(
            atoms=[
                _obligation(
                    statement=excerpt,
                    source_excerpts=[excerpt],
                    time_constraint=time,
                )
            ]
        ),
    )
    with pytest.raises(ProtocolControlGateError, match="TIME_ANCHOR_GUESSED_FROM_SCREENING"):
        _gate_control_with_manifest(control, _manifest_with_control_excerpt(excerpt))


@pytest.mark.parametrize(
    ("excerpt", "constraint"),
    [
        (
            "筛选访视和D1访视间隔≤7天",
            TimeConstraint(
                anchor_type="first_dose_date",
                direction="before",
                upper_bound_days=7,
            ),
        ),
        (
            "筛选访视和D1访视间隔＞7天",
            TimeConstraint(
                anchor_type="first_dose_date",
                direction="before",
                lower_bound_days=7,
                lower_bound_inclusive=False,
            ),
        ),
        (
            "需在D1天前7天内进行基线访视",
            TimeConstraint(
                anchor_type="first_dose_date",
                direction="before",
                upper_bound_days=7,
            ),
        ),
    ],
)
def test_time_bound_comparator_preserves_source_edge(
    excerpt: str,
    constraint: TimeConstraint,
) -> None:
    atom = ControlConditionAtom(
        condition_atom_id="condition-time-edge",
        statement=excerpt,
        source_span_ids=["span:control"],
        source_excerpts=[excerpt],
        time_constraint=constraint,
    )

    _check_time_constraints(
        entity_id="control:time-edge",
        texts=[excerpt],
        expressions=[],
        flat_atoms=[atom],
        global_time_constraint=None,
    )


@pytest.mark.parametrize(
    ("excerpt", "constraint"),
    [
        (
            "筛选访视和D1访视间隔≤7天",
            TimeConstraint(
                anchor_type="first_dose_date",
                direction="before",
                upper_bound_days=7,
                upper_bound_inclusive=False,
            ),
        ),
        (
            "筛选访视和D1访视间隔＞7天",
            TimeConstraint(
                anchor_type="first_dose_date",
                direction="before",
                lower_bound_days=7,
            ),
        ),
    ],
)
def test_time_bound_comparator_rejects_changed_edge(
    excerpt: str,
    constraint: TimeConstraint,
) -> None:
    atom = ControlConditionAtom(
        condition_atom_id="condition-time-edge",
        statement=excerpt,
        source_span_ids=["span:control"],
        source_excerpts=[excerpt],
        time_constraint=constraint,
    )

    with pytest.raises(
        ProtocolControlGateError,
        match="TIME_BOUND_COMPARATOR_MISMATCH",
    ):
        _check_time_constraints(
            entity_id="control:time-edge",
            texts=[excerpt],
            expressions=[],
            flat_atoms=[atom],
            global_time_constraint=None,
        )


def test_missing_time_anchor_reports_exact_atom_and_statement() -> None:
    excerpt = "以给药前最近一次评估结果作为基线值"
    atom = ControlConditionAtom(
        condition_atom_id="condition-baseline-selection",
        statement=excerpt,
        source_span_ids=["span:control"],
        source_excerpts=[excerpt],
        time_constraint=None,
    )

    with pytest.raises(ProtocolControlGateError) as caught:
        _check_time_constraints(
            entity_id="control:baseline-selection",
            texts=[excerpt],
            expressions=[ControlConditionDnf(groups=[ControlConditionGroup(atoms=[atom])])],
            flat_atoms=[],
            global_time_constraint=None,
        )

    assert caught.value.entity_id == (
        "control:baseline-selection/condition-baseline-selection"
    )
    assert excerpt in str(caught.value)


def test_questionnaire_recall_period_is_not_a_study_visit_time_window() -> None:
    excerpt = "DLQI是一份包含10个问题的问卷，用于评估上1周内患者主观感受"
    atom = _obligation(
        statement="核对DLQI问卷是否回顾上1周内的主观感受",
        source_excerpts=[excerpt],
        time_constraint=None,
    )

    _check_time_constraints(
        entity_id="control:questionnaire-recall",
        texts=[excerpt],
        expressions=[_explicit_obligation_dnf(atoms=[atom])],
        flat_atoms=[],
        global_time_constraint=None,
    )


def test_mutation_and_weakened_to_or_is_rejected() -> None:
    atom_a = _obligation(obligation_id="obl-a", statement="A且B", source_excerpts=["必须记录用药日期"])
    atom_b = _obligation(obligation_id="obl-b", statement="A且B的第二义务", source_excerpts=["必须记录用药日期"])
    weakened = _control(
        obligation_expression=_explicit_obligation_dnf(groups=[[atom_a], [atom_b]]),
    )
    with pytest.raises(ProtocolControlGateError, match="OBLIGATION_AND_WEAKENED"):
        _gate(control=weakened, candidates=[])

    any_flag = _control(
        obligation_expression=_explicit_obligation_dnf(atoms=[atom_a, atom_b]),
        obligation_combination="any",
    )
    with pytest.raises(ProtocolControlGateError, match="OBLIGATION_AND_WEAKENED"):
        _gate(control=any_flag, candidates=[])


def test_exception_copied_to_sibling_branch_is_rejected() -> None:
    shared_units = [
        _paragraph_unit("su-control", "span:shared-ex", 1, "必须记录用药日期"),
        _paragraph_unit("su-sibling", "span:shared-ex", 2, "必须记录另一项资料"),
        _paragraph_unit("su-support", "span:support", 3, "补充背景说明"),
    ]
    trigger = ControlConditionDnf(
        groups=[
            ControlConditionGroup(
                atoms=[
                    ControlConditionAtom(
                        condition_atom_id="condition-trigger",
                        statement="既往用药暴露",
                        source_span_ids=["span:shared-ex"],
                        source_excerpts=["必须记录"],
                    )
                ],
                trigger_branch_id="pct-shared-trigger",
            )
        ]
    )
    exception = ControlExceptionDnf(
        groups=[
            ControlExceptionGroup(
                atoms=[
                    ControlConditionAtom(
                        condition_atom_id="condition-ex",
                        statement="例外条件",
                        source_span_ids=["span:shared-ex"],
                        source_excerpts=["必须记录"],
                    )
                ],
                waives_trigger_branch_ids=["pct-shared-trigger"],
            )
        ]
    )
    exception_second = ControlExceptionDnf(
        groups=[
            ControlExceptionGroup(
                atoms=[
                    ControlConditionAtom(
                        condition_atom_id="condition-ex-2",
                        statement="例外条件",
                        source_span_ids=["span:shared-ex"],
                        source_excerpts=["必须记录"],
                    )
                ],
                waives_trigger_branch_ids=["pct-shared-trigger"],
            )
        ]
    )
    first = _control(
        control_id="pctrl-1",
        source_unit_ids=["su-control"],
        source_span_ids=["span:shared-ex"],
        trigger_expression=trigger,
        obligation_expression=_explicit_obligation_dnf(
            atoms=[
                _obligation(
                    source_span_ids=["span:shared-ex"],
                    source_excerpts=["必须记录"],
                )
            ]
        ),
        exception_expression=exception,
    )
    second = _control(
        control_id="pctrl-2",
        source_unit_ids=["su-sibling"],
        source_span_ids=["span:shared-ex"],
        trigger_expression=trigger,
        obligation_expression=_explicit_obligation_dnf(
            atoms=[
                _obligation(
                    source_span_ids=["span:shared-ex"],
                    source_excerpts=["必须记录"],
                )
            ]
        ),
        exception_expression=exception_second,
    ).model_copy(update={"display_ordinal": 2})
    dispositions = [
        StructureUnitDisposition(
            structure_unit_id="su-control",
            disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
            linked_control_candidate_id="pcc-1",
        ),
        StructureUnitDisposition(
            structure_unit_id="su-sibling",
            disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
            linked_control_candidate_id="pcc-2",
        ),
        StructureUnitDisposition(
            structure_unit_id="su-support",
            disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
        ),
    ]
    with pytest.raises(ProtocolControlGateError, match="EXCEPTION_SIBLING_COPY"):
        _gate(
            manifest=_manifest(units=shared_units, dispositions=dispositions),
            catalog=_catalog(
                [],
                allowed_spans=["span:shared-ex", "span:support"],
            ).model_copy(update={"controls": [first, second]}),
            candidates=[],
        )


def test_unscoped_exception_with_trigger_is_rejected() -> None:
    trigger = ControlConditionDnf(
        groups=[
            ControlConditionGroup(
                atoms=[
                    ControlConditionAtom(
                        condition_atom_id="trg-a",
                        statement="药物A暴露",
                        source_span_ids=["span:control"],
                        source_excerpts=["必须记录用药日期"],
                    )
                ],
                trigger_branch_id="pct-a",
            )
        ]
    )
    exception = ControlExceptionDnf(
        groups=[
            ControlExceptionGroup(
                atoms=[
                    ControlConditionAtom(
                        condition_atom_id="ex-1",
                        statement="完成清除剂洗脱",
                        source_span_ids=["span:control"],
                        source_excerpts=["必须记录用药日期"],
                    )
                ],
                waives_trigger_branch_ids=[],
            )
        ]
    )
    with pytest.raises(ProtocolControlGateError, match="EXCEPTION_SCOPE_MISSING"):
        _gate(
            control=_control(
                trigger_expression=trigger,
                exception_expression=exception,
                obligation_expression=_explicit_obligation_dnf(
                    atoms=[
                        _obligation(
                            time_constraint=TimeConstraint(
                                anchor_type="first_dose_date",
                                direction="before",
                                lower_bound={"value": 24, "unit": "month"},
                            )
                        )
                    ]
                ),
            ),
            candidates=[],
        )


def _conditional_shorten_fixture(
    *,
    short_on_condition: bool = False,
    activate: bool = True,
    alt_applies: list[str] | None = None,
    default_applies: list[str] | None = None,
    waive: list[str] | None = None,
    include_default: bool = True,
    include_alternative: bool = True,
    orphan_alternative: bool = False,
    shorten_cue: bool = True,
) -> ProtocolReviewControl:
    """Build a generic 24→6 conditional-shorten control for gate regressions."""

    baseline_binding = ReviewNodeBinding(
        workflow_stage_id="stage:baseline:1",
        review_stage=ReviewStage.BASELINE,
        role=ReviewNodeRole.DECIDE_AT_NODE,
    )
    trigger = ControlConditionDnf(
        groups=[
            ControlConditionGroup(
                atoms=[
                    ControlConditionAtom(
                        condition_atom_id="trg-target",
                        statement="目标药物暴露",
                        source_span_ids=["span:control"],
                        source_excerpts=["目标药物暴露"],
                    )
                ],
                trigger_branch_id="pct-target",
            ),
            ControlConditionGroup(
                atoms=[
                    ControlConditionAtom(
                        condition_atom_id="trg-other",
                        statement="其他药物暴露",
                        source_span_ids=["span:control"],
                        source_excerpts=["其他药物暴露"],
                    )
                ],
                trigger_branch_id="pct-other",
            ),
        ]
    )
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
    waived = waive if waive is not None else ["pct-target"]
    default_scope = default_applies if default_applies is not None else ["pct-target"]
    alt_scope = alt_applies if alt_applies is not None else ["pct-target"]

    obligation_groups: list[ControlObligationGroup] = []
    if include_default:
        obligation_groups.append(
            ControlObligationGroup(
                atoms=[
                    _obligation(
                        obligation_id="obl-default",
                        statement="首次给药前24个月不得暴露",
                        source_excerpts=["首次给药前24个月不得暴露"],
                        time_constraint=default_window,
                    )
                ],
                obligation_group_id="pog-default",
                applies_to_trigger_branch_ids=default_scope,
                activated_by_exception_group_ids=[],
            )
        )
    if include_alternative:
        obligation_groups.append(
            ControlObligationGroup(
                atoms=[
                    _obligation(
                        obligation_id="obl-alt",
                        statement="首次给药前6个月不得暴露",
                        source_excerpts=["首次给药前6个月"],
                        time_constraint=short_window,
                    )
                ],
                obligation_group_id="pog-alt",
                applies_to_trigger_branch_ids=alt_scope,
                activated_by_exception_group_ids=(
                    ["peg-clearance"]
                    if activate or orphan_alternative
                    else []
                ),
            )
        )

    exception_atoms = [
        ControlConditionAtom(
            condition_atom_id="ex-clearance",
            statement=(
                "经药物清除剂进行洗脱可缩短"
                if shorten_cue
                else "经药物清除剂进行洗脱"
            ),
            source_span_ids=["span:control"],
            source_excerpts=[
                "经药物清除剂进行洗脱可缩短至首次给药前6个月"
                if shorten_cue
                else "经药物清除剂进行洗脱"
            ],
            time_constraint=short_window if short_on_condition else None,
        )
    ]
    return _control(
        bindings=[baseline_binding],
        trigger_expression=trigger,
        obligation_expression=ControlObligationDnf(groups=obligation_groups),
        exception_expression=ControlExceptionDnf(
            groups=[
                ControlExceptionGroup(
                    atoms=exception_atoms,
                    exception_group_id="peg-clearance",
                    waives_trigger_branch_ids=waived,
                    activates_obligation_group_ids=["pog-alt"] if activate else [],
                )
            ]
        ),
    )


def _conditional_shorten_manifest() -> ProtocolSectionCoverageManifest:
    return _manifest_with_control_excerpt(
        "目标药物暴露；其他药物暴露。"
        "首次给药前24个月不得暴露；"
        "经药物清除剂进行洗脱可缩短至首次给药前6个月。"
    )


def test_conditional_shorten_accepts_explicit_24_to_6_activation() -> None:
    assert _gate_control_with_manifest(
        _conditional_shorten_fixture(),
        _conditional_shorten_manifest(),
        workflow_targets=_workflow_targets(include_baseline=True),
    ) is not None


def test_conditional_shorten_rejects_short_window_on_condition_atom() -> None:
    with pytest.raises(ProtocolControlGateError, match="EXCEPTION_TIME_ON_CONDITION"):
        _gate_control_with_manifest(
            _conditional_shorten_fixture(short_on_condition=True),
            _conditional_shorten_manifest(),
            workflow_targets=_workflow_targets(include_baseline=True),
        )


def test_conditional_shorten_rejects_condition_without_alternative_obligation() -> None:
    with pytest.raises(ProtocolControlGateError, match="EXCEPTION_ACTIVATION_MISSING"):
        _gate_control_with_manifest(
            _conditional_shorten_fixture(
                activate=False,
                include_alternative=False,
            ),
            _conditional_shorten_manifest(),
            workflow_targets=_workflow_targets(include_baseline=True),
        )


def test_conditional_shorten_rejects_orphan_alternative_obligation() -> None:
    with pytest.raises(ProtocolControlGateError, match="OBLIGATION_ACTIVATION_ORPHAN"):
        _gate_control_with_manifest(
            _conditional_shorten_fixture(
                activate=False,
                orphan_alternative=True,
                shorten_cue=False,
            ),
            _conditional_shorten_manifest(),
            workflow_targets=_workflow_targets(include_baseline=True),
        )


def test_conditional_shorten_rejects_default_and_alt_on_different_triggers() -> None:
    with pytest.raises(ProtocolControlGateError, match="BRANCH_CONSEQUENCE_MISMATCH"):
        _gate_control_with_manifest(
            _conditional_shorten_fixture(
                default_applies=["pct-other"],
                alt_applies=["pct-target"],
                waive=["pct-target"],
            ),
            _conditional_shorten_manifest(),
            workflow_targets=_workflow_targets(include_baseline=True),
        )


def test_conditional_shorten_rejects_alternative_drifting_to_sibling_branch() -> None:
    with pytest.raises(ProtocolControlGateError, match="BRANCH_CONSEQUENCE_MISMATCH"):
        _gate_control_with_manifest(
            _conditional_shorten_fixture(
                alt_applies=["pct-other"],
                waive=["pct-target"],
            ),
            _conditional_shorten_manifest(),
            workflow_targets=_workflow_targets(include_baseline=True),
        )


def test_longer_of_selection_required_when_source_cues_exist() -> None:
    baseline_binding = ReviewNodeBinding(
        workflow_stage_id="stage:baseline:1",
        review_stage=ReviewStage.BASELINE,
        role=ReviewNodeRole.DECIDE_AT_NODE,
    )
    longer = TimeConstraint(
        anchor_type="first_dose_date",
        direction="before",
        lower_bound={"value": 3, "unit": "month"},
        half_life_multiplier=5,
        combined_window_selection="longer_of_calendar_and_half_life",
    )
    excerpt = "首次给药前3个月或5个半衰期，以时间较长者为准"
    manifest = _manifest_with_control_excerpt(excerpt)
    accepted = _control(
        bindings=[baseline_binding],
        obligation_expression=_explicit_obligation_dnf(
            atoms=[
                _obligation(
                    statement=excerpt,
                    source_excerpts=[excerpt],
                    time_constraint=longer,
                )
            ]
        ),
    )
    assert _gate_control_with_manifest(
        accepted,
        manifest,
        workflow_targets=_workflow_targets(include_baseline=True),
    ) is not None

    calendar_only = _control(
        bindings=[baseline_binding],
        obligation_expression=_explicit_obligation_dnf(
            atoms=[
                _obligation(
                    statement=excerpt,
                    source_excerpts=[excerpt],
                    time_constraint=TimeConstraint(
                        anchor_type="first_dose_date",
                        direction="before",
                        lower_bound={"value": 3, "unit": "month"},
                    ),
                )
            ]
        ),
    )
    with pytest.raises(ProtocolControlGateError, match="TIME_COMBINED_SELECTION_MISSING"):
        _gate_control_with_manifest(
            calendar_only,
            manifest,
            workflow_targets=_workflow_targets(include_baseline=True),
        )


def test_study_end_period_must_be_typed_on_the_obligation_atom() -> None:
    baseline_binding = ReviewNodeBinding(
        workflow_stage_id="stage:baseline:1",
        review_stage=ReviewStage.BASELINE,
        role=ReviewNodeRole.DECIDE_AT_NODE,
    )
    window = TimeConstraint(
        anchor_type="first_dose_date",
        direction="before",
        lower_bound={"value": 4, "unit": "week"},
    )
    excerpt = "首次给药前4周至试验结束禁止使用系统治疗"
    manifest = _manifest(
        units=[
            _paragraph_unit("su-control", "span:control", 1, excerpt),
            _table_row_unit(),
            _paragraph_unit("su-support", "span:support", 3, "补充背景说明"),
        ],
    )
    workflow_targets = _workflow_targets(include_baseline=True)
    plan = _plan(manifest, workflow_targets)
    batch_dispositions = []
    for result in _hydrated_batch_results(manifest, plan):
        candidates = []
        for candidate in result.candidates:
            semantics = candidate.semantics.model_copy(
                update={
                    "obligation_expression": _explicit_obligation_dnf(
                        atoms=[
                            _obligation(
                                statement="禁止使用系统治疗",
                                source_span_ids=list(candidate.source_span_ids),
                                source_excerpts=["禁止使用系统治疗"],
                            )
                        ]
                    )
                }
            )
            candidates.append(candidate.model_copy(update={"semantics": semantics}))
        batch_dispositions.append(result.model_copy(update={"candidates": candidates}))
    missing_period = _control(
        bindings=[baseline_binding],
        obligation_expression=_explicit_obligation_dnf(
            atoms=[
                _obligation(
                    statement="禁止使用系统治疗",
                    source_excerpts=[excerpt],
                    time_constraint=window,
                )
            ]
        ),
    )
    with pytest.raises(ProtocolControlGateError, match="PROSPECTIVE_PERIOD_MISSING"):
        _gate(
            control=missing_period,
            manifest=manifest,
            candidates=[],
            workflow_targets=workflow_targets,
            plan=plan,
            batch_dispositions=batch_dispositions,
        )

    complete_period = missing_period.model_copy(
        update={
            "obligation_expression": _explicit_obligation_dnf(
                atoms=[
                    _obligation(
                        statement="禁止使用系统治疗",
                        source_excerpts=[excerpt],
                        time_constraint=window,
                        prospective_period=ProspectivePeriod(period="study_period"),
                    )
                ]
            )
        }
    )
    missing_bound = complete_period.model_copy(
        update={
            "obligation_expression": _explicit_obligation_dnf(
                atoms=[
                    _obligation(
                        statement="禁止使用系统治疗",
                        source_excerpts=[excerpt],
                        time_constraint=TimeConstraint(
                            anchor_type="first_dose_date",
                            direction="before",
                        ),
                        prospective_period=ProspectivePeriod(period="study_period"),
                    )
                ]
            )
        }
    )
    with pytest.raises(ProtocolControlGateError, match="TIME_CALENDAR_BOUND_MISSING"):
        _gate(
            control=missing_bound,
            manifest=manifest,
            candidates=[],
            workflow_targets=workflow_targets,
            plan=plan,
            batch_dispositions=batch_dispositions,
        )

    unsupported_bound = complete_period.model_copy(
        update={
            "obligation_expression": _explicit_obligation_dnf(
                atoms=[
                    _obligation(
                        statement="禁止使用系统治疗",
                        source_excerpts=[excerpt],
                        time_constraint=TimeConstraint(
                            anchor_type="first_dose_date",
                            direction="before",
                            lower_bound={"value": 3, "unit": "week"},
                        ),
                        prospective_period=ProspectivePeriod(period="study_period"),
                    )
                ]
            )
        }
    )
    with pytest.raises(ProtocolControlGateError, match="TIME_CALENDAR_BOUND_UNSUPPORTED"):
        _gate(
            control=unsupported_bound,
            manifest=manifest,
            candidates=[],
            workflow_targets=workflow_targets,
            plan=plan,
            batch_dispositions=batch_dispositions,
        )

    assert _gate(
        control=complete_period,
        manifest=manifest,
        candidates=[],
        workflow_targets=workflow_targets,
        plan=plan,
        batch_dispositions=batch_dispositions,
    ) is not None


def test_obligation_period_without_direct_source_support_is_rejected() -> None:
    control = _control(
        obligation_expression=_explicit_obligation_dnf(
            atoms=[
                _obligation(
                    prospective_period=ProspectivePeriod(period="study_period"),
                )
            ]
        )
    )
    with pytest.raises(ProtocolControlGateError, match="PROSPECTIVE_PERIOD_UNSUPPORTED"):
        _gate(control=control, candidates=[])


def test_reported_future_period_does_not_make_the_discussion_action_ongoing() -> None:
    excerpt = (
        "研究者应与参与者讨论并确认参与者已知晓研究期间需持续正确使用该方法"
    )
    control = _control(
        obligation_expression=_explicit_obligation_dnf(
            atoms=[
                _obligation(
                    kind=ControlObligationKind.MUST_PROFESSIONAL_ASSESSMENT,
                    statement=excerpt,
                    source_excerpts=[excerpt],
                )
            ]
        )
    )

    assert _gate(
        control=control,
        manifest=_manifest_with_control_excerpt(excerpt),
        candidates=[],
    ) is not None


def test_reported_future_period_cannot_be_attached_to_the_discussion_action() -> None:
    excerpt = "研究者应告知参与者研究期间需持续正确使用该方法"
    control = _control(
        obligation_expression=_explicit_obligation_dnf(
            atoms=[
                _obligation(
                    kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                    statement=excerpt,
                    source_excerpts=[excerpt],
                    prospective_period=ProspectivePeriod(period="study_period"),
                )
            ]
        )
    )

    with pytest.raises(ProtocolControlGateError, match="PROSPECTIVE_PERIOD_UNSUPPORTED"):
        _gate(
            control=control,
            manifest=_manifest_with_control_excerpt(excerpt),
            candidates=[],
        )


def test_action_scoped_study_period_still_requires_structured_period() -> None:
    excerpt = "研究期间，研究者必须评估并记录避孕方法使用情况"
    control = _control(
        obligation_expression=_explicit_obligation_dnf(
            atoms=[
                _obligation(
                    kind=ControlObligationKind.MUST_PROFESSIONAL_ASSESSMENT,
                    statement=excerpt,
                    source_excerpts=[excerpt],
                )
            ]
        )
    )

    with pytest.raises(ProtocolControlGateError, match="PROSPECTIVE_PERIOD_MISSING"):
        _gate(
            control=control,
            manifest=_manifest_with_control_excerpt(excerpt),
            candidates=[],
        )


def test_icf_to_study_end_range_directly_supports_study_period() -> None:
    excerpt = "从签署知情同意书之日开始至研究药物末次给药后3个月为止禁止使用激素类避孕"
    expression = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                kind=ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE,
                statement="禁止使用激素类避孕",
                source_excerpts=[excerpt],
                time_constraint=TimeConstraint(
                    anchor_type="last_dose_date",
                    direction="after",
                    upper_bound={"value": 3, "unit": "month"},
                ),
                prospective_period=ProspectivePeriod(period="study_period"),
            )
        ]
    )

    _check_time_constraints(
        entity_id="control:icf-period",
        texts=[excerpt],
        expressions=(expression,),
        flat_atoms=(),
        global_time_constraint=None,
    )


def test_table_row_partial_source_closure_is_rejected() -> None:
    partial = _control(
        source_unit_ids=["su-table"],
        source_span_ids=["span:table:a"],
        obligation_expression=ControlObligationDnf(
            groups=[
                ControlObligationGroup(
                    atoms=[
                        _obligation(
                            source_span_ids=["span:table:a"],
                            source_excerpts=["表格要求"],
                        )
                    ]
                )
            ]
        ),
    )
    partial_dispositions = [
        StructureUnitDisposition(
            structure_unit_id="su-control",
            disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
        ),
        StructureUnitDisposition(
            structure_unit_id="su-table",
            disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
            linked_control_candidate_id="pcc-table",
        ),
        StructureUnitDisposition(
            structure_unit_id="su-support",
            disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
        ),
    ]
    with pytest.raises(ProtocolControlGateError, match="TABLE_ROW_SOURCE_CLOSURE_PARTIAL"):
        _gate(
            control=partial,
            candidates=[],
            manifest=_manifest(dispositions=partial_dispositions),
        )


def test_later_stage_review_requires_later_decisive_node() -> None:
    bindings = [
        ReviewNodeBinding(
            workflow_stage_id="stage:screening:1",
            review_stage=ReviewStage.SCREENING,
            role=ReviewNodeRole.EARLY_ATTENTION,
        ),
        ReviewNodeBinding(
            workflow_stage_id="stage:baseline:1",
            review_stage=ReviewStage.BASELINE,
            role=ReviewNodeRole.LATER_NODE_REVIEW,
        ),
    ]
    with pytest.raises(ProtocolControlGateError, match="LATER_NODE_DECISION_MISSING"):
        _gate(
            control=_control(bindings=bindings),
            candidates=[],
            workflow_targets=_workflow_targets(include_baseline=True),
        )


def test_future_first_dose_check_cannot_be_decided_as_screening_failure() -> None:
    excerpt = "首次给药前不得使用药物"
    first_dose = TimeConstraint(
        anchor_type="first_dose_date",
        direction="before",
    )
    control = _control(
        obligation_expression=_explicit_obligation_dnf(
            atoms=[
                _obligation(
                    statement=excerpt,
                    source_excerpts=[excerpt],
                    time_constraint=first_dose,
                )
            ]
        ),
        bindings=[
            ReviewNodeBinding(
                workflow_stage_id="stage:screening:1",
                review_stage=ReviewStage.SCREENING,
                role=ReviewNodeRole.DECIDE_AT_NODE,
            )
        ],
    )
    with pytest.raises(ProtocolControlGateError, match="EARLY_DECISION_FOR_FUTURE_ANCHOR"):
        _gate_control_with_manifest(
            control,
            _manifest_with_control_excerpt(excerpt),
            workflow_targets=_workflow_targets(include_baseline=True),
        )


def test_future_first_dose_check_cannot_also_decide_at_screening() -> None:
    excerpt = "首次给药前28天内完成检测"
    control = _control(
        obligation_expression=_explicit_obligation_dnf(
            atoms=[
                _obligation(
                    statement=excerpt,
                    source_excerpts=[excerpt],
                    time_constraint=TimeConstraint(
                        anchor_type="first_dose_date",
                        direction="before",
                        upper_bound_days=28,
                    ),
                )
            ]
        ),
        bindings=[
            ReviewNodeBinding(
                workflow_stage_id="stage:screening:1",
                review_stage=ReviewStage.SCREENING,
                role=ReviewNodeRole.DECIDE_AT_NODE,
            ),
            ReviewNodeBinding(
                workflow_stage_id="stage:baseline:1",
                review_stage=ReviewStage.BASELINE,
                role=ReviewNodeRole.DECIDE_AT_NODE,
            ),
        ],
        minimum_evidence=[
            *_evidence(),
            ControlMinimumEvidence(
                evidence_key="evidence-baseline",
                fact_type="laboratory_result",
                description="首次给药前核对检测有效期",
                due_stage=ReviewStage.BASELINE,
                required_source_types=["原始报告"],
            ),
        ],
    )

    with pytest.raises(ProtocolControlGateError, match="EARLY_DECISION_FOR_FUTURE_ANCHOR"):
        _gate_control_with_manifest(
            control,
            _manifest_with_control_excerpt(excerpt),
            workflow_targets=_workflow_targets(include_baseline=True),
        )


def test_future_first_dose_check_accepts_early_attention_and_baseline_decision() -> None:
    excerpt = "首次给药前28天内完成检测"
    control = _control(
        obligation_expression=_explicit_obligation_dnf(
            atoms=[
                _obligation(
                    statement=excerpt,
                    source_excerpts=[excerpt],
                    time_constraint=TimeConstraint(
                        anchor_type="first_dose_date",
                        direction="before",
                        upper_bound_days=28,
                    ),
                )
            ]
        ),
        bindings=[
            ReviewNodeBinding(
                workflow_stage_id="stage:screening:1",
                review_stage=ReviewStage.SCREENING,
                role=ReviewNodeRole.EARLY_ATTENTION,
            ),
            ReviewNodeBinding(
                workflow_stage_id="stage:baseline:1",
                review_stage=ReviewStage.BASELINE,
                role=ReviewNodeRole.DECIDE_AT_NODE,
            ),
        ],
        minimum_evidence=[
            ControlMinimumEvidence(
                evidence_key="evidence-baseline",
                fact_type="laboratory_result",
                description="首次给药前核对检测有效期",
                due_stage=ReviewStage.BASELINE,
                required_source_types=["原始报告"],
            )
        ],
    )

    _gate_control_with_manifest(
        control,
        _manifest_with_control_excerpt(excerpt),
        workflow_targets=_workflow_targets(include_baseline=True),
    )


def test_first_dose_anchor_uses_dedicated_frozen_node_when_available() -> None:
    expression = _explicit_obligation_dnf(
        atoms=[
            _obligation(
                statement="首次给药前完成检测",
                source_excerpts=["首次给药前完成检测"],
                time_constraint=TimeConstraint(
                    anchor_type="first_dose_date",
                    direction="before",
                ),
            )
        ]
    )
    workflow_targets = [
        *_workflow_targets(include_baseline=True),
        KnownWorkflowStageTarget(
            workflow_stage_id="stage:first-dose:1",
            review_stage=ReviewStage.BASELINE,
            display_name="首次给药前复核",
            visit_instance="治疗期 / W0 / D1",
        ),
    ]
    baseline_binding = [
        ReviewNodeBinding(
            workflow_stage_id="stage:baseline:1",
            review_stage=ReviewStage.BASELINE,
            role=ReviewNodeRole.DECIDE_AT_NODE,
        )
    ]

    with pytest.raises(ProtocolControlGateError, match="ANCHOR_WORKFLOW_STAGE_MISMATCH"):
        _check_anchor_decision_alignment(
            entity_id="control:first-dose",
            bindings=baseline_binding,
            workflow_targets=workflow_targets,
            expressions=(expression,),
            global_time_constraint=None,
        )

    _check_anchor_decision_alignment(
        entity_id="control:first-dose",
        bindings=[
            ReviewNodeBinding(
                workflow_stage_id="stage:first-dose:1",
                review_stage=ReviewStage.BASELINE,
                role=ReviewNodeRole.DECIDE_AT_NODE,
            )
        ],
        workflow_targets=workflow_targets,
        expressions=(expression,),
        global_time_constraint=None,
    )


def test_required_procedure_visit_scope_rejects_uncovered_selected_phase_visits() -> None:
    unit = _paragraph_unit(
        "su-pregnancy-schedule",
        "span:pregnancy-schedule",
        1,
        "必须在筛选、基线、第12周（Ⅱ期临床研究阶段）、"
        "第16、52周访视（Ⅲ期临床研究阶段）和提前退出访视进行检查。",
        phase_scopes=[PhaseScope.PHASE_II],
    )
    disposition = ProtocolControlUnitDisposition(
        structure_unit_id=unit.structure_unit_id,
        disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
        linked_procedure_catalog_item_ids=[
            "procedure:baseline",
            "procedure:d1",
            "procedure:screening",
        ],
    )
    targets = [
        KnownRequiredProcedureTarget(
            catalog_item_id="procedure:baseline",
            label="检查",
            visit_instance="筛选期 / 基线 / D≤-7",
            review_stage=ReviewStage.BASELINE,
            position=1,
            source_span_ids=["span:baseline"],
        ),
        KnownRequiredProcedureTarget(
            catalog_item_id="procedure:d1",
            label="检查",
            visit_instance="治疗期 / W0 / D1",
            review_stage=ReviewStage.BASELINE,
            position=2,
            source_span_ids=["span:d1"],
        ),
        KnownRequiredProcedureTarget(
            catalog_item_id="procedure:screening",
            label="检查",
            visit_instance="筛选期 / 筛选 / D-28~D-1",
            review_stage=ReviewStage.SCREENING,
            position=0,
            source_span_ids=["span:screening"],
        ),
    ]

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_required_procedure_visit_scope(
            disposition=disposition,
            unit=unit,
            procedure_targets=targets,
            study_phase=StudyPhase.PHASE_II,
        )

    assert exc_info.value.code == "PROCEDURE_VISIT_SCOPE_UNCOVERED"
    assert "第12周访视" in str(exc_info.value)
    assert "提前退出访视" in str(exc_info.value)
    assert "第16周访视" not in str(exc_info.value)
    assert "第52周访视" not in str(exc_info.value)


def test_required_procedure_visit_scope_rejects_extra_visit_target() -> None:
    unit = _paragraph_unit(
        "su-history",
        "span:history",
        1,
        "问询筛选访视以来的病史及诊治情况。",
        phase_scopes=[PhaseScope.PHASE_II],
    )
    disposition = ProtocolControlUnitDisposition(
        structure_unit_id=unit.structure_unit_id,
        disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
        linked_procedure_catalog_item_ids=[
            "procedure:baseline-history",
            "procedure:d1-history",
        ],
    )
    targets = [
        KnownRequiredProcedureTarget(
            catalog_item_id="procedure:baseline-history",
            label="基线病史复核",
            visit_instance="基线访视",
            review_stage=ReviewStage.BASELINE,
            position=0,
            source_span_ids=["span:baseline-history"],
        ),
        KnownRequiredProcedureTarget(
            catalog_item_id="procedure:d1-history",
            label="D1给药前病史复核",
            visit_instance="D1首次给药前",
            review_stage=ReviewStage.BASELINE,
            position=1,
            source_span_ids=["span:d1-history"],
        ),
    ]

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_required_procedure_visit_scope(
            disposition=disposition,
            unit=unit,
            procedure_targets=targets,
            study_phase=StudyPhase.PHASE_II,
            owned_visit_instance="基线访视",
            owned_procedure_semantic_families=[
                "medical_history",
                "treatment_history",
            ],
        )

    assert exc_info.value.code == "PROCEDURE_VISIT_SCOPE_OVERBOUND"
    assert "首次给药前访视" in str(exc_info.value)


def test_required_procedure_visit_scope_rejects_missing_semantic_family() -> None:
    unit = _paragraph_unit(
        "su-history-treatment",
        "span:history-treatment",
        1,
        "问询筛选访视以来的病史及诊治情况。",
        phase_scopes=[PhaseScope.PHASE_II],
    )
    disposition = ProtocolControlUnitDisposition(
        structure_unit_id=unit.structure_unit_id,
        disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
        linked_procedure_catalog_item_ids=["procedure:baseline-history"],
    )
    targets = [
        KnownRequiredProcedureTarget(
            catalog_item_id="procedure:baseline-history",
            label="基线访视既往和现病史复核",
            visit_instance="基线访视",
            review_stage=ReviewStage.BASELINE,
            position=0,
            semantic_family="medical_history",
            source_span_ids=["span:baseline-history"],
        ),
        KnownRequiredProcedureTarget(
            catalog_item_id="procedure:baseline-treatment",
            label="基线访视治疗史复核",
            visit_instance="基线访视",
            review_stage=ReviewStage.BASELINE,
            position=1,
            semantic_family="treatment_history",
            source_span_ids=["span:baseline-treatment"],
        ),
    ]

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_required_procedure_visit_scope(
            disposition=disposition,
            unit=unit,
            procedure_targets=targets,
            study_phase=StudyPhase.PHASE_II,
            owned_visit_instance="基线访视",
            owned_procedure_semantic_families=[
                "medical_history",
                "treatment_history",
            ],
        )

    assert exc_info.value.code == "PROCEDURE_SEMANTIC_FAMILY_UNCOVERED"
    assert "治疗史" in str(exc_info.value)

    disposition = disposition.model_copy(
        update={
            "linked_procedure_catalog_item_ids": [
                "procedure:baseline-history",
                "procedure:baseline-treatment",
            ]
        }
    )
    _check_required_procedure_visit_scope(
        disposition=disposition,
        unit=unit,
        procedure_targets=targets,
        study_phase=StudyPhase.PHASE_II,
        owned_visit_instance="基线访视",
        owned_procedure_semantic_families=[
            "medical_history",
            "treatment_history",
        ],
    )


def test_required_procedure_visit_scope_rejects_uncovered_action_predicate() -> None:
    unit = _paragraph_unit(
        "su-icf-explanation",
        "span:icf-explanation",
        1,
        "研究者解释研究程序并获得参与者签署知情同意书。",
        phase_scopes=[PhaseScope.PHASE_II],
    )
    disposition = ProtocolControlUnitDisposition(
        structure_unit_id=unit.structure_unit_id,
        disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
        linked_procedure_catalog_item_ids=["procedure:icf-signature"],
    )
    targets = [
        KnownRequiredProcedureTarget(
            catalog_item_id="procedure:icf-signature",
            label="签署知情同意书",
            visit_instance="筛选访视",
            review_stage=ReviewStage.SCREENING,
            position=0,
            semantic_family="informed_consent",
            covered_action_kinds=["obtain_signature"],
            source_span_ids=["span:icf-signature"],
        )
    ]

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_required_procedure_visit_scope(
            disposition=disposition,
            unit=unit,
            procedure_targets=targets,
            study_phase=StudyPhase.PHASE_II,
            owned_required_action_kinds=[
                "explain_information",
                "obtain_signature",
            ],
        )

    assert exc_info.value.code == "PROCEDURE_ACTION_UNCOVERED"
    assert "explain_information" in str(exc_info.value)


def test_decision_node_requires_evidence_due_at_that_stage() -> None:
    bindings = [
        ReviewNodeBinding(
            workflow_stage_id="stage:screening:1",
            review_stage=ReviewStage.SCREENING,
            role=ReviewNodeRole.EARLY_ATTENTION,
        ),
        ReviewNodeBinding(
            workflow_stage_id="stage:baseline:1",
            review_stage=ReviewStage.BASELINE,
            role=ReviewNodeRole.DECIDE_AT_NODE,
        ),
    ]

    with pytest.raises(ProtocolControlGateError, match="DECISION_STAGE_EVIDENCE_MISSING"):
        _gate(
            control=_control(bindings=bindings, minimum_evidence=_evidence()),
            candidates=[],
            workflow_targets=_workflow_targets(include_baseline=True),
        )


def test_unknown_relation_target_and_unresolved_conflict_stop_publication() -> None:
    unknown = ControlCrossSourceRelation(
        relation_id="relation-1",
        kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
        left_target_kind=ControlRelationTargetKind.PROTOCOL_CONTROL,
        left_target_id="pctrl-1",
        right_target_kind=ControlRelationTargetKind.OFFICIAL_RULE,
        right_target_id="EX-99",
        notes="待核对",
    )
    with pytest.raises(ProtocolControlGateError, match="UNKNOWN_RELATION_TARGET"):
        _gate(control=_control(cross_source_relations=[unknown]), candidates=[])

    conflict = ControlCrossSourceRelation(
        relation_id="relation-conflict",
        kind=CrossSourceRelationKind.SUBSTANTIVE_CONFLICT,
        left_target_kind=ControlRelationTargetKind.PROTOCOL_CONTROL,
        left_target_id="pctrl-1",
        right_target_kind=ControlRelationTargetKind.OFFICIAL_RULE,
        right_target_id="EX-01",
        notes="来源冲突未解决",
    )
    conflict_control = _control(cross_source_relations=[conflict])
    catalog = _catalog([]).model_copy(update={"controls": [conflict_control]})
    with pytest.raises(ProtocolControlGateError, match="UNRESOLVED_SUBSTANTIVE_CONFLICT"):
        _gate(catalog=catalog, candidates=[])


def test_supplementary_procedure_relation_aligns_exact_visit_decision_and_evidence() -> None:
    workflow = _workflow_targets(include_baseline=True)
    procedures = [
        KnownRequiredProcedureTarget(
            catalog_item_id="procedure-screening",
            label="筛选期检查",
            visit_instance="screening-1",
            review_stage=ReviewStage.SCREENING,
            position=0,
            source_span_ids=["span:procedure:screening"],
        ),
        KnownRequiredProcedureTarget(
            catalog_item_id="procedure-baseline",
            label="基线期检查",
            visit_instance="baseline-1",
            review_stage=ReviewStage.BASELINE,
            position=1,
            source_span_ids=["span:procedure:baseline"],
        ),
    ]

    def relation(procedure_id: str, affected_id: str | None) -> ControlCrossSourceRelation:
        return ControlCrossSourceRelation(
            relation_id=f"relation-{procedure_id}",
            kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
            left_target_kind=ControlRelationTargetKind.PROTOCOL_CONTROL,
            left_target_id="pctrl-1",
            right_target_kind=ControlRelationTargetKind.REQUIRED_PROCEDURE,
            right_target_id=procedure_id,
            affected_workflow_stage_id=affected_id,
        )

    _check_supplementary_procedure_stage_alignment(
        [relation("procedure-screening", "stage:screening:1")],
        entity_id="pctrl-1",
        bindings=[
            ReviewNodeBinding(
                workflow_stage_id="stage:screening:1",
                review_stage=ReviewStage.SCREENING,
                role=ReviewNodeRole.DECIDE_AT_NODE,
            )
        ],
        evidence=_evidence(ReviewStage.SCREENING),
        procedure_targets=procedures,
        workflow_targets=workflow,
    )

    with pytest.raises(
        ProtocolControlGateError,
        match="PROCEDURE_AFFECTED_STAGE_MISMATCH",
    ):
        _check_supplementary_procedure_stage_alignment(
            [relation("procedure-screening", "stage:baseline:1")],
            entity_id="pctrl-1",
            bindings=[
                ReviewNodeBinding(
                    workflow_stage_id="stage:baseline:1",
                    review_stage=ReviewStage.BASELINE,
                    role=ReviewNodeRole.DECIDE_AT_NODE,
                )
            ],
            evidence=_evidence(ReviewStage.BASELINE),
            procedure_targets=procedures,
            workflow_targets=workflow,
        )

    with pytest.raises(ProtocolControlGateError, match="AFFECTED_STAGE_MISSING"):
        _check_supplementary_procedure_stage_alignment(
            [relation("procedure-screening", None)],
            entity_id="pctrl-1",
            bindings=[],
            evidence=[],
            procedure_targets=procedures,
            workflow_targets=workflow,
        )

    _check_supplementary_procedure_stage_alignment(
        [relation("procedure-baseline", "stage:baseline:1")],
        entity_id="pctrl-1",
        bindings=[
            ReviewNodeBinding(
                workflow_stage_id="stage:baseline:1",
                review_stage=ReviewStage.BASELINE,
                role=ReviewNodeRole.DECIDE_AT_NODE,
            )
        ],
        evidence=_evidence(ReviewStage.BASELINE),
        procedure_targets=procedures,
        workflow_targets=workflow,
    )


def test_visit_schedule_cannot_propagate_a_general_window_to_one_procedure() -> None:
    relation = ControlCrossSourceRelation(
        relation_id="relation-visit-procedure",
        kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
        left_target_kind=ControlRelationTargetKind.PROTOCOL_CONTROL,
        left_target_id="pctrl-visit",
        right_target_kind=ControlRelationTargetKind.REQUIRED_PROCEDURE,
        right_target_id="procedure-baseline",
        affected_workflow_stage_id="stage:baseline:1",
    )

    with pytest.raises(
        ProtocolControlGateError,
        match="VISIT_SCHEDULE_TARGET_TOO_NARROW",
    ):
        _check_temporal_obligation_relation_scope(
            entity_id="pctrl-visit",
            obligation_expression=_explicit_obligation_dnf(
                atoms=[
                    _obligation(
                        kind=ControlObligationKind.SCHEDULE_OR_VERIFY_VISIT,
                        statement="需在首次给药前7天内进行基线访视",
                    )
                ]
            ),
            relations=[relation],
            bindings=[
                ReviewNodeBinding(
                    workflow_stage_id="stage:baseline:1",
                    review_stage=ReviewStage.BASELINE,
                    role=ReviewNodeRole.DECIDE_AT_NODE,
                )
            ],
        )


def test_visit_schedule_can_target_its_bound_workflow_stage() -> None:
    relation = ControlCrossSourceRelation(
        relation_id="relation-visit-stage",
        kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
        left_target_kind=ControlRelationTargetKind.PROTOCOL_CONTROL,
        left_target_id="pctrl-visit",
        right_target_kind=ControlRelationTargetKind.WORKFLOW_STAGE,
        right_target_id="stage:baseline:1",
    )

    _check_temporal_obligation_relation_scope(
        entity_id="pctrl-visit",
        obligation_expression=_explicit_obligation_dnf(
            atoms=[
                _obligation(
                    kind=ControlObligationKind.SCHEDULE_OR_VERIFY_VISIT,
                    statement="需在首次给药前7天内进行基线访视",
                )
            ]
        ),
        relations=[relation],
        bindings=[
            ReviewNodeBinding(
                workflow_stage_id="stage:baseline:1",
                review_stage=ReviewStage.BASELINE,
                role=ReviewNodeRole.DECIDE_AT_NODE,
            )
        ],
    )


def test_general_baseline_value_rule_and_procedure_exception_must_be_separate() -> None:
    relations = [
        ControlCrossSourceRelation(
            relation_id="relation-baseline-stage",
            kind=CrossSourceRelationKind.FURTHER_EXPLANATION,
            left_target_kind=ControlRelationTargetKind.PROTOCOL_CONTROL,
            left_target_id="pctrl-baseline-value",
            right_target_kind=ControlRelationTargetKind.WORKFLOW_STAGE,
            right_target_id="stage:baseline:1",
        ),
        ControlCrossSourceRelation(
            relation_id="relation-baseline-procedure",
            kind=CrossSourceRelationKind.FURTHER_EXPLANATION,
            left_target_kind=ControlRelationTargetKind.PROTOCOL_CONTROL,
            left_target_id="pctrl-baseline-value",
            right_target_kind=ControlRelationTargetKind.REQUIRED_PROCEDURE,
            right_target_id="procedure-baseline",
        ),
    ]

    with pytest.raises(
        ProtocolControlGateError,
        match="BASELINE_VALUE_SCOPE_MIXED",
    ):
        _check_temporal_obligation_relation_scope(
            entity_id="pctrl-baseline-value",
            obligation_expression=_explicit_obligation_dnf(
                atoms=[
                    _obligation(
                        kind=ControlObligationKind.SELECT_BASELINE_VALUE,
                        statement="以给药前最近一次评估结果作为基线值",
                    )
                ]
            ),
            relations=relations,
            bindings=[
                ReviewNodeBinding(
                    workflow_stage_id="stage:baseline:1",
                    review_stage=ReviewStage.BASELINE,
                    role=ReviewNodeRole.DECIDE_AT_NODE,
                )
            ],
        )


def test_legacy_flat_obligation_surface_is_not_publishable_in_58b() -> None:
    legacy = _control(
        obligation_expression=None,
        obligations=[_obligation()],
    ).model_copy(update={"obligation_expression": None})
    # model_copy deliberately simulates a legacy persisted 5.8a shape without
    # changing the domain contract; the publication gate is the migration stop.
    with pytest.raises(ProtocolControlGateError, match="LEGACY_FLAT_OBLIGATION_REJECTED"):
        _gate(control=legacy, candidates=[])


def _file_snapshot(path: Path) -> tuple[str, int, int, tuple[str, ...]]:
    stat = path.stat()
    return (
        hashlib.sha256(path.read_bytes()).hexdigest(),
        stat.st_size,
        stat.st_mtime_ns,
        tuple(sorted(item.name for item in path.parent.iterdir())),
    )


def test_real_d001_table5_rows_remain_in_review_input_and_ignore_keyword_filter(
    tmp_path: Path,
) -> None:
    source = Path(
        "/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/"
        "CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx"
    )
    if not source.is_file():
        pytest.skip(f"真实 D001 方案文件缺失：{source}")
    before = _file_snapshot(source)
    artifact = register_source_artifact(
        source,
        source_artifact_id="slice58c-d001-readonly",
        storage_root=tmp_path,
    )
    extraction = extract_docx_structure(
        source,
        snapshot_id="slice58c-d001-snapshot",
        source_artifact=artifact,
        output_dir=tmp_path,
    )
    phase = build_phase_applicability_graph(
        extraction.blocks,
        snapshot_id=extraction.snapshot.snapshot_id,
    )
    projection = project_single_phase(phase.graph, StudyPhase.PHASE_II)
    base = build_full_protocol_coverage_manifest(
        extraction.blocks,
        projection,
        phase.graph,
        protocol_version_id="D001-02-002:V1.0",
        protocol_document_sha256=artifact.sha256,
        snapshot_id=extraction.snapshot.snapshot_id,
        priority_keywords=[],
    )
    filtered = build_full_protocol_coverage_manifest(
        extraction.blocks,
        projection,
        phase.graph,
        protocol_version_id="D001-02-002:V1.0",
        protocol_document_sha256=artifact.sha256,
        snapshot_id=extraction.snapshot.snapshot_id,
        priority_keywords=["首次给药前7天"],
    )
    before_counts = (len(extraction.blocks), len(base.units))
    after_counts = (len(extraction.blocks), len(filtered.units))
    assert before_counts == after_counts
    assert before_counts == (3581, 1848)
    base_table5 = [unit for unit in base.units if unit.source_ref.startswith("body.t10.")]
    filtered_table5 = [
        unit for unit in filtered.units if unit.source_ref.startswith("body.t10.")
    ]
    base_rows = {unit.source_ref for unit in base_table5 if unit.unit_kind.value == "table_row"}
    filtered_rows = {
        unit.source_ref
        for unit in filtered_table5
        if unit.unit_kind.value == "table_row"
    }
    assert len(base_table5) == 13  # table header plus the 12 control rows
    assert len(base_rows) == 12
    assert filtered_rows == base_rows
    assert [unit.source_ref for unit in filtered_table5] == [
        unit.source_ref for unit in base_table5
    ]
    assert all(
        unit.member_source_refs
        and set(unit.source_span_ids)
        for unit in filtered_table5
    )
    assert any(not unit.priority_keyword_hits for unit in filtered_table5)

    plan = plan_protocol_control_batches(
        filtered,
        max_owned_units_per_batch=64,
        workflow_stages=[
            WorkflowStage(
                workflow_stage_id="stage:screening:1",
                stage=ReviewStage.SCREENING,
                display_name="筛选期",
                visit_instance="screening-1",
            )
        ],
    )
    review_inputs = [ProtocolControlAgentInput.from_batch(batch) for batch in plan.batches]
    review_input_ids = {
        unit.structure_unit_id
        for review_input in review_inputs
        for unit in review_input.owned_units
    }
    filtered_table5_ids = {
        unit.structure_unit_id for unit in filtered_table5
    }
    assert filtered_table5_ids <= review_input_ids

    after = _file_snapshot(source)
    assert after == before, "真实 D001 原文或其目录不得被读取流程改写"
