"""Focused regressions for candidate obligation action coverage proof.

Synthetic fixtures only; no model calls and no project-specific identifiers.
"""

from __future__ import annotations

import pytest

from app.domain.contracts.enums import PhaseScope, ReviewStage, StudyPhase
from app.domain.contracts.protocol_controls import (
    ControlCrossSourceRelation,
    ControlMinimumEvidence,
    ControlObligationAtom,
    ControlObligationDnf,
    ControlObligationGroup,
    ControlObligationKind,
    ControlRelationTargetKind,
    CrossSourceRelationKind,
    KnownRequiredProcedureTarget,
    ProtocolControlBatchDispositionHydrated,
    ProtocolControlCandidate,
    ProtocolControlCandidateSemantics,
    ProtocolControlUnitDisposition,
    ProtocolStructureUnit,
    ReviewNodeBinding,
    ReviewNodeRole,
    StructureUnitDispositionKind,
)
from app.protocols.protocol_control_gate import (
    ProtocolControlGateError,
    _check_hydrated_result_links,
    _check_obligation_source_action_impersonation,
    _obligation_statement_action_kinds,
)


_LAB_EXCERPT = "采集用于实验室检查的样品，并应根据标准实验室程序进行。"
_LAB_ACTIONS = ["collect_biospecimen", "follow_specified_procedure"]


def _paragraph_unit(
    unit_id: str,
    span_id: str,
    excerpt: str,
) -> ProtocolStructureUnit:
    return ProtocolStructureUnit(
        structure_unit_id=unit_id,
        source_ref=f"body.{unit_id}",
        member_source_refs=[f"body.{unit_id}"],
        source_span_ids=[span_id],
        unit_kind="paragraph",
        heading_path=["实验室检查"],
        source_order=1,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.PHASE_II],
        excerpt=excerpt,
    )


def _obligation_atom(
    *,
    obligation_id: str,
    statement: str,
    source_span_id: str,
    source_excerpt: str,
) -> ControlObligationAtom:
    return ControlObligationAtom(
        obligation_id=obligation_id,
        kind=ControlObligationKind.COMPLETE_OR_VERIFY,
        statement=statement,
        source_span_ids=[source_span_id],
        source_excerpts=[source_excerpt],
    )


def _candidate_with_obligations(
    *,
    candidate_id: str,
    unit_id: str,
    span_id: str,
    atoms: list[ControlObligationAtom],
    relations: list[ControlCrossSourceRelation] | None = None,
) -> ProtocolControlCandidate:
    semantics = ProtocolControlCandidateSemantics(
        title="实验室执行控制",
        applicable_population="拟入组受试者",
        control_candidate_id=candidate_id,
        obligation_expression=ControlObligationDnf(
            groups=[ControlObligationGroup(atoms=atoms)]
        ),
        review_node_bindings=[
            ReviewNodeBinding(
                workflow_stage_id="stage:screening:1",
                review_stage=ReviewStage.SCREENING,
                role=ReviewNodeRole.DECIDE_AT_NODE,
            )
        ],
        minimum_evidence=[
            ControlMinimumEvidence(
                evidence_key="evidence-lab",
                fact_type="laboratory_result",
                description="核对实验室执行记录",
                due_stage=ReviewStage.SCREENING,
                required_source_types=["原始资料"],
            )
        ],
        source_structure_unit_ids=[unit_id],
        source_span_ids=[span_id],
        cross_source_relations=relations or [],
    )
    return ProtocolControlCandidate(
        control_candidate_id=candidate_id,
        protocol_version_id="protocol:generic",
        study_phase=StudyPhase.PHASE_II,
        frozen_structure_unit_ids=[unit_id],
        title="实验室执行控制",
        applicable_population="拟入组受试者",
        source_span_ids=[span_id],
        semantics=semantics,
    )


def _hydrated_batch(
    *,
    unit: ProtocolStructureUnit,
    candidate: ProtocolControlCandidate,
) -> ProtocolControlBatchDispositionHydrated:
    return ProtocolControlBatchDispositionHydrated(
        batch_id="batch:action-coverage",
        coverage_manifest_id="manifest:action-coverage",
        owned_structure_unit_ids=[unit.structure_unit_id],
        owned_source_span_ids=list(unit.source_span_ids),
        dispositions=[
            ProtocolControlUnitDisposition(
                structure_unit_id=unit.structure_unit_id,
                disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                linked_control_candidate_ids=[candidate.control_candidate_id],
            )
        ],
        candidates=[candidate],
    )


def test_candidate_obligation_must_itemize_each_frozen_action() -> None:
    unit = _paragraph_unit("su-lab", "span:lab", _LAB_EXCERPT)
    candidate = _candidate_with_obligations(
        candidate_id="pcc-lab-actions",
        unit_id=unit.structure_unit_id,
        span_id="span:lab",
        atoms=[
            _obligation_atom(
                obligation_id="obl-collect",
                statement="采集用于实验室检查的样品",
                source_span_id="span:lab",
                source_excerpt=_LAB_EXCERPT,
            ),
            _obligation_atom(
                obligation_id="obl-procedure",
                statement="应根据标准实验室程序执行",
                source_span_id="span:lab",
                source_excerpt=_LAB_EXCERPT,
            ),
        ],
    )

    _check_hydrated_result_links(
        _hydrated_batch(unit=unit, candidate=candidate),
        known_procedure_targets=[],
        unit_by_id={unit.structure_unit_id: unit},
        study_phase=StudyPhase.PHASE_II,
        owned_required_action_kinds_by_structure_unit_id={
            unit.structure_unit_id: _LAB_ACTIONS,
        },
    )


def test_ecg_candidate_statements_cover_rest_and_qtcf_actions() -> None:
    assert _obligation_statement_action_kinds(
        ControlObligationDnf(
            groups=[
                ControlObligationGroup(
                    atoms=[
                        _obligation_atom(
                            obligation_id="obl-rest",
                            statement="12导联心电图检查前参与者至少静息10 min",
                            source_span_id="span:ecg",
                            source_excerpt="12导联心电图检查前参与者至少静息10 min",
                        ),
                        _obligation_atom(
                            obligation_id="obl-qtcf",
                            statement="应用Fridericia's公式计算心率校正计算QTcF",
                            source_span_id="span:ecg",
                            source_excerpt="应用Fridericia’s公式计算心率校正计算QTcF",
                        ),
                    ]
                )
            ]
        )
    ) == {"calculate_qtcf", "perform_ecg", "prepare_participant"}


def test_disposition_change_without_obligation_coverage_is_rejected() -> None:
    unit = _paragraph_unit("su-lab", "span:lab", _LAB_EXCERPT)
    generic_excerpt = "完成方案规定的检查项目。"
    candidate = _candidate_with_obligations(
        candidate_id="pcc-lab-checklist-only",
        unit_id=unit.structure_unit_id,
        span_id="span:lab",
        atoms=[
            _obligation_atom(
                obligation_id="obl-checklist",
                statement="完成方案规定的检查项目",
                source_span_id="span:lab",
                source_excerpt=generic_excerpt,
            )
        ],
    )

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_hydrated_result_links(
            _hydrated_batch(unit=unit, candidate=candidate),
            known_procedure_targets=[],
            unit_by_id={unit.structure_unit_id: unit},
            study_phase=StudyPhase.PHASE_II,
            owned_required_action_kinds_by_structure_unit_id={
                unit.structure_unit_id: _LAB_ACTIONS,
            },
        )

    assert exc_info.value.code == "CANDIDATE_OBLIGATION_ACTION_UNCOVERED"
    assert exc_info.value.structure_unit_ids == (unit.structure_unit_id,)
    assert exc_info.value.candidate_ids == (candidate.control_candidate_id,)
    assert "collect_biospecimen" in str(exc_info.value)
    assert "follow_specified_procedure" in str(exc_info.value)


def test_source_excerpt_cannot_impersonate_obligation_action() -> None:
    expression = ControlObligationDnf(
        groups=[
            ControlObligationGroup(
                atoms=[
                    _obligation_atom(
                        obligation_id="obl-generic",
                        statement="完成方案规定的检查项目",
                        source_span_id="span:lab",
                        source_excerpt=_LAB_EXCERPT,
                    )
                ]
            )
        ]
    )

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_obligation_source_action_impersonation(
            expression,
            entity_id="pcc-source-only",
            required_actions=set(_LAB_ACTIONS),
            statement_covered=_obligation_statement_action_kinds(expression),
            procedure_covered=set(),
        )

    assert exc_info.value.code == "OBLIGATION_ACTION_SOURCE_ONLY"
    assert "collect_biospecimen" in str(exc_info.value)


def test_procedure_covered_actions_reduce_candidate_obligation_requirement() -> None:
    unit = _paragraph_unit("su-lab", "span:lab", _LAB_EXCERPT)
    relation = ControlCrossSourceRelation(
        relation_id="relation-procedure",
        kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
        left_target_kind=ControlRelationTargetKind.CONTROL_CANDIDATE,
        left_target_id="pcc-lab-partial",
        right_target_kind=ControlRelationTargetKind.REQUIRED_PROCEDURE,
        right_target_id="procedure-lab-checklist",
        affected_workflow_stage_id="stage:screening:1",
    )
    candidate = _candidate_with_obligations(
        candidate_id="pcc-lab-partial",
        unit_id=unit.structure_unit_id,
        span_id="span:lab",
        atoms=[
            _obligation_atom(
                obligation_id="obl-procedure",
                statement="应根据标准实验室程序执行",
                source_span_id="span:lab",
                source_excerpt=_LAB_EXCERPT,
            )
        ],
        relations=[relation],
    )
    procedure = KnownRequiredProcedureTarget(
        catalog_item_id="procedure-lab-checklist",
        label="执行检查项目",
        visit_instance="screening-1",
        review_stage=ReviewStage.SCREENING,
        position=0,
        covered_action_kinds=["collect_biospecimen"],
        source_span_ids=["span:procedure"],
    )

    _check_hydrated_result_links(
        _hydrated_batch(unit=unit, candidate=candidate),
        known_procedure_targets=[procedure],
        unit_by_id={unit.structure_unit_id: unit},
        study_phase=StudyPhase.PHASE_II,
        owned_required_action_kinds_by_structure_unit_id={
            unit.structure_unit_id: _LAB_ACTIONS,
        },
    )


def test_action_increment_cannot_be_labeled_as_further_explanation() -> None:
    unit = _paragraph_unit("su-lab", "span:lab", _LAB_EXCERPT)
    candidate_id = "pcc-lab-understated"
    relation = ControlCrossSourceRelation(
        relation_id="relation-procedure-understated",
        kind=CrossSourceRelationKind.FURTHER_EXPLANATION,
        left_target_kind=ControlRelationTargetKind.CONTROL_CANDIDATE,
        left_target_id=candidate_id,
        right_target_kind=ControlRelationTargetKind.REQUIRED_PROCEDURE,
        right_target_id="procedure-lab-checklist",
        affected_workflow_stage_id=None,
    )
    candidate = _candidate_with_obligations(
        candidate_id=candidate_id,
        unit_id=unit.structure_unit_id,
        span_id="span:lab",
        atoms=[
            _obligation_atom(
                obligation_id="obl-procedure",
                statement="应根据标准实验室程序执行并采集样品",
                source_span_id="span:lab",
                source_excerpt=_LAB_EXCERPT,
            )
        ],
        relations=[relation],
    )
    procedure = KnownRequiredProcedureTarget(
        catalog_item_id="procedure-lab-checklist",
        label="执行检查项目",
        visit_instance="screening-1",
        review_stage=ReviewStage.SCREENING,
        position=0,
        covered_action_kinds=["collect_biospecimen"],
        source_span_ids=["span:procedure"],
    )

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_hydrated_result_links(
            _hydrated_batch(unit=unit, candidate=candidate),
            known_procedure_targets=[procedure],
            unit_by_id={unit.structure_unit_id: unit},
            study_phase=StudyPhase.PHASE_II,
            owned_required_action_kinds_by_structure_unit_id={
                unit.structure_unit_id: _LAB_ACTIONS,
            },
        )

    assert exc_info.value.code == "ACTION_INCREMENT_RELATION_UNDERSTATED"


def test_action_statement_from_another_source_unit_cannot_cover_this_unit() -> None:
    collection_unit = _paragraph_unit(
        "su-collection",
        "span:collection",
        "采集用于实验室检查的样品。",
    )
    procedure_unit = _paragraph_unit(
        "su-procedure",
        "span:procedure",
        "应根据标准实验室程序进行。",
    )
    candidate_id = "pcc-cross-unit"
    semantics = ProtocolControlCandidateSemantics(
        title="实验室执行控制",
        applicable_population="拟入组受试者",
        control_candidate_id=candidate_id,
        obligation_expression=ControlObligationDnf(
            groups=[
                ControlObligationGroup(
                    atoms=[
                        _obligation_atom(
                            obligation_id="obl-procedure-only",
                            statement="应根据标准实验室程序执行并采集样品",
                            source_span_id="span:procedure",
                            source_excerpt=procedure_unit.excerpt,
                        )
                    ]
                )
            ]
        ),
        review_node_bindings=[
            ReviewNodeBinding(
                workflow_stage_id="stage:screening:1",
                review_stage=ReviewStage.SCREENING,
                role=ReviewNodeRole.DECIDE_AT_NODE,
            )
        ],
        minimum_evidence=[
            ControlMinimumEvidence(
                evidence_key="evidence-cross-unit",
                fact_type="laboratory_result",
                description="核对实验室执行记录",
                due_stage=ReviewStage.SCREENING,
                required_source_types=["原始资料"],
            )
        ],
        source_structure_unit_ids=[
            collection_unit.structure_unit_id,
            procedure_unit.structure_unit_id,
        ],
        source_span_ids=["span:collection", "span:procedure"],
    )
    candidate = ProtocolControlCandidate(
        control_candidate_id=candidate_id,
        protocol_version_id="protocol:generic",
        study_phase=StudyPhase.PHASE_II,
        frozen_structure_unit_ids=[
            collection_unit.structure_unit_id,
            procedure_unit.structure_unit_id,
        ],
        title="实验室执行控制",
        applicable_population="拟入组受试者",
        source_span_ids=["span:collection", "span:procedure"],
        semantics=semantics,
    )
    result = ProtocolControlBatchDispositionHydrated(
        batch_id="batch:cross-unit",
        coverage_manifest_id="manifest:cross-unit",
        owned_structure_unit_ids=[
            collection_unit.structure_unit_id,
            procedure_unit.structure_unit_id,
        ],
        owned_source_span_ids=["span:collection", "span:procedure"],
        dispositions=[
            ProtocolControlUnitDisposition(
                structure_unit_id=unit.structure_unit_id,
                disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                linked_control_candidate_ids=[candidate.control_candidate_id],
            )
            for unit in (collection_unit, procedure_unit)
        ],
        candidates=[candidate],
    )

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_hydrated_result_links(
            result,
            known_procedure_targets=[],
            unit_by_id={
                collection_unit.structure_unit_id: collection_unit,
                procedure_unit.structure_unit_id: procedure_unit,
            },
            study_phase=StudyPhase.PHASE_II,
            owned_required_action_kinds_by_structure_unit_id={
                collection_unit.structure_unit_id: ["collect_biospecimen"],
                procedure_unit.structure_unit_id: ["follow_specified_procedure"],
            },
        )

    assert exc_info.value.code == "CANDIDATE_OBLIGATION_ACTION_UNCOVERED"
    assert exc_info.value.structure_unit_ids == (
        collection_unit.structure_unit_id,
    )


def test_required_procedure_disposition_bypass_still_fails() -> None:
    unit = _paragraph_unit("su-lab", "span:lab", _LAB_EXCERPT)
    result = ProtocolControlBatchDispositionHydrated(
        batch_id="batch:procedure-bypass",
        coverage_manifest_id="manifest:procedure-bypass",
        owned_structure_unit_ids=[unit.structure_unit_id],
        owned_source_span_ids=list(unit.source_span_ids),
        dispositions=[
            ProtocolControlUnitDisposition(
                structure_unit_id=unit.structure_unit_id,
                disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
                linked_procedure_catalog_item_ids=["procedure-lab-checklist"],
            )
        ],
        candidates=[],
    )
    procedure = KnownRequiredProcedureTarget(
        catalog_item_id="procedure-lab-checklist",
        label="执行检查项目",
        visit_instance="screening-1",
        review_stage=ReviewStage.SCREENING,
        position=0,
        covered_action_kinds=[],
        source_span_ids=["span:procedure"],
    )

    with pytest.raises(ProtocolControlGateError) as exc_info:
        _check_hydrated_result_links(
            result,
            known_procedure_targets=[procedure],
            unit_by_id={unit.structure_unit_id: unit},
            study_phase=StudyPhase.PHASE_II,
            owned_required_action_kinds_by_structure_unit_id={
                unit.structure_unit_id: _LAB_ACTIONS,
            },
        )

    assert exc_info.value.code == "PROCEDURE_ACTION_UNCOVERED"
