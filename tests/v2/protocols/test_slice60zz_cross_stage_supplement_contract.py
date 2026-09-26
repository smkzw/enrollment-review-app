"""Focused regressions for cross-stage subsequent-control supplementary relations."""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from app.agents.protocol_control_deconstructor import (
    ProtocolControlAgentWireCandidate,
    ProtocolControlAgentWireEvidence,
    ProtocolControlAgentWireNode,
    ProtocolControlAgentWireObligationAtom,
    ProtocolControlAgentWireObligationDnf,
    ProtocolControlAgentWireObligationGroup,
    ProtocolControlAgentWireRelation,
    build_protocol_control_repair_prompt,
    hydrate_protocol_control_agent_output,
)
from app.domain.contracts.enums import ReviewStage
from app.domain.contracts.protocol_controls import (
    ControlCrossSourceRelation,
    ControlObligationKind,
    ControlRelationTargetKind,
    CrossSourceRelationKind,
    KnownRequiredProcedureTarget,
    KnownWorkflowStageTarget,
    ProtocolControlDispositionBatch,
    ReviewNodeBinding,
    ReviewNodeRole,
)
from app.domain.contracts.rules import TimeConstraint
from app.protocols.protocol_control_gate import (
    ProtocolControlGateError,
    _check_supplementary_procedure_stage_alignment,
    _validate_candidate,
)
from app.protocols.supplementary_relation_contract import (
    is_cross_stage_subsequent_control_supplement,
)
from tests.v2.protocols.test_slice58c_control_deconstructor import (
    _batch as _deconstructor_batch,
    _candidate as _deconstructor_candidate,
    _evidence_policy,
    _evaluation,
    _timed_evaluation,
    _wire,
)
from tests.v2.protocols.test_slice58c_protocol_control_gate import (
    _evidence,
    _explicit_obligation_dnf,
    _obligation,
    _workflow_targets,
)


def _screening_procedure() -> KnownRequiredProcedureTarget:
    return KnownRequiredProcedureTarget(
        catalog_item_id="procedure-screening",
        label="筛选期病毒学检查",
        visit_instance="screening-1",
        review_stage=ReviewStage.SCREENING,
        position=0,
        source_span_ids=["span:procedure:screening"],
    )


def _validity_obligation(*, anchor: str = "first_dose_date") -> ControlObligationDnf:
    return _explicit_obligation_dnf(
        atoms=[
            _obligation(
                kind=ControlObligationKind.VERIFY_RESULT_VALIDITY,
                statement="首次给药前28天内结果有效",
                source_excerpts=["首次给药前28天内结果有效"],
                time_constraint=TimeConstraint(
                    anchor_type=anchor,
                    direction="before",
                    upper_bound_days=28,
                ),
            )
        ]
    )


def _supplement_relation(
    *,
    procedure_id: str = "procedure-screening",
    affected_id: str,
) -> ControlCrossSourceRelation:
    return ControlCrossSourceRelation(
        relation_id="relation-cross-stage",
        kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
        left_target_kind=ControlRelationTargetKind.PROTOCOL_CONTROL,
        left_target_id="pctrl-cross-stage",
        right_target_kind=ControlRelationTargetKind.REQUIRED_PROCEDURE,
        right_target_id=procedure_id,
        affected_workflow_stage_id=affected_id,
    )


def _baseline_bindings(*, include_screening_attention: bool = False) -> list[ReviewNodeBinding]:
    bindings = [
        ReviewNodeBinding(
            workflow_stage_id="stage:baseline:1",
            review_stage=ReviewStage.BASELINE,
            role=ReviewNodeRole.DECIDE_AT_NODE,
        )
    ]
    if include_screening_attention:
        bindings.insert(
            0,
            ReviewNodeBinding(
                workflow_stage_id="stage:screening:1",
                review_stage=ReviewStage.SCREENING,
                role=ReviewNodeRole.EARLY_ATTENTION,
            ),
        )
    return bindings


def test_helper_detects_cross_stage_subsequent_control_supplement() -> None:
    procedure = _screening_procedure()
    workflow = _workflow_targets(include_baseline=True)
    assert is_cross_stage_subsequent_control_supplement(
        obligation_expression=_validity_obligation(),
        procedure=procedure,
        affected_workflow_stage_id="stage:baseline:1",
        workflow_targets=workflow,
    )
    assert not is_cross_stage_subsequent_control_supplement(
        obligation_expression=_validity_obligation(),
        procedure=procedure,
        affected_workflow_stage_id="stage:screening:1",
        workflow_targets=workflow,
    )


def test_future_continuing_prohibition_does_not_authorize_cross_stage_supplement() -> None:
    prohibition = SimpleNamespace(
        kind=ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE,
        time_constraint=TimeConstraint(anchor_type="baseline_date", direction="before"),
        continuing_obligation=SimpleNamespace(status="not_due_at_review_node"),
    )
    expression = SimpleNamespace(groups=[SimpleNamespace(atoms=[prohibition])])
    assert not is_cross_stage_subsequent_control_supplement(
        obligation_expression=expression,
        procedure=_screening_procedure(),
        affected_workflow_stage_id="stage:baseline:1",
        workflow_targets=_workflow_targets(include_baseline=True),
    )


def test_syn_accept_01_cross_stage_validity_supplement_passes_gate() -> None:
    _check_supplementary_procedure_stage_alignment(
        [_supplement_relation(affected_id="stage:baseline:1")],
        entity_id="pctrl-cross-stage",
        bindings=_baseline_bindings(),
        evidence=_evidence(ReviewStage.BASELINE),
        obligation_expression=_validity_obligation(),
        procedure_targets=[_screening_procedure()],
        workflow_targets=_workflow_targets(include_baseline=True),
    )


def test_syn_accept_02_cross_stage_with_screening_early_attention_passes_gate() -> None:
    _check_supplementary_procedure_stage_alignment(
        [_supplement_relation(affected_id="stage:baseline:1")],
        entity_id="pctrl-cross-stage",
        bindings=_baseline_bindings(include_screening_attention=True),
        evidence=_evidence(ReviewStage.BASELINE),
        obligation_expression=_validity_obligation(),
        procedure_targets=[_screening_procedure()],
        workflow_targets=_workflow_targets(include_baseline=True),
    )


def test_syn_reject_02_same_stage_supplement_cannot_use_baseline_affected() -> None:
    with pytest.raises(
        ProtocolControlGateError,
        match="PROCEDURE_AFFECTED_STAGE_MISMATCH",
    ):
        _check_supplementary_procedure_stage_alignment(
            [_supplement_relation(affected_id="stage:baseline:1")],
            entity_id="pctrl-cross-stage",
            bindings=_baseline_bindings(),
            evidence=_evidence(ReviewStage.BASELINE),
            obligation_expression=_explicit_obligation_dnf(
                atoms=[
                    _obligation(
                        kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                        statement="筛选期额外问卷",
                        source_excerpts=["筛选期额外问卷"],
                    )
                ]
            ),
            procedure_targets=[_screening_procedure()],
            workflow_targets=_workflow_targets(include_baseline=True),
        )


def test_syn_reject_03_r3_shape_still_rejects_missing_decide_at_affected() -> None:
    with pytest.raises(
        ProtocolControlGateError,
        match="AFFECTED_STAGE_DECISION_MISSING",
    ):
        _check_supplementary_procedure_stage_alignment(
            [_supplement_relation(affected_id="stage:screening:1")],
            entity_id="pctrl-cross-stage",
            bindings=[
                ReviewNodeBinding(
                    workflow_stage_id="stage:baseline:1",
                    review_stage=ReviewStage.BASELINE,
                    role=ReviewNodeRole.DECIDE_AT_NODE,
                )
            ],
            evidence=_evidence(ReviewStage.BASELINE),
            obligation_expression=_validity_obligation(),
            procedure_targets=[_screening_procedure()],
            workflow_targets=_workflow_targets(include_baseline=True),
        )


def test_syn_reject_04_cross_stage_missing_baseline_evidence() -> None:
    with pytest.raises(
        ProtocolControlGateError,
        match="AFFECTED_STAGE_EVIDENCE_MISSING",
    ):
        _check_supplementary_procedure_stage_alignment(
            [_supplement_relation(affected_id="stage:baseline:1")],
            entity_id="pctrl-cross-stage",
            bindings=_baseline_bindings(),
            evidence=_evidence(ReviewStage.SCREENING),
            obligation_expression=_validity_obligation(),
            procedure_targets=[_screening_procedure()],
            workflow_targets=_workflow_targets(include_baseline=True),
        )


def _batch_with_baseline() -> ProtocolControlDispositionBatch:
    batch = _deconstructor_batch()
    return batch.model_copy(
        update={
            "known_workflow_stage_targets": [
                *batch.known_workflow_stage_targets,
                KnownWorkflowStageTarget(
                    workflow_stage_id="stage:baseline:1",
                    review_stage=ReviewStage.BASELINE,
                    display_name="基线期",
                    visit_instance="baseline-1",
                ),
            ]
        }
    )


def _cross_stage_wire_candidate(
    *,
    affected_id: str,
    bindings: list[ProtocolControlAgentWireNode],
    evidence: list[ProtocolControlAgentWireEvidence],
) -> ProtocolControlAgentWireCandidate:
    candidate = _deconstructor_candidate()
    return candidate.model_copy(
        update={
            "cross_source_relations": [
                ProtocolControlAgentWireRelation(
                    kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
                    external_target_kind=ControlRelationTargetKind.REQUIRED_PROCEDURE,
                    external_target_id="procedure-screening-1",
                    candidate_side="left",
                    affected_workflow_stage_id=affected_id,
                    notes="筛选执行、基线判定有效窗",
                )
            ],
            "obligation_expression": ProtocolControlAgentWireObligationDnf(
                groups=[
                    ProtocolControlAgentWireObligationGroup(
                        atoms=[
                            ProtocolControlAgentWireObligationAtom(
                                kind=ControlObligationKind.VERIFY_RESULT_VALIDITY,
                                evaluation=_timed_evaluation(
                                    "年龄至少18岁", "span:01", "年龄至少18岁"
                                ),
                                statement="年龄至少18岁",
                                time_constraint={
                                    "anchor_type": "first_dose_date",
                                    "direction": "before",
                                    "upper_bound_days": 28,
                                },
                                prospective_period=None,
                                source_span_ids=["span:01"],
                                source_excerpts=["年龄至少18岁"],
                                requires_professional_judgment=False,
                            )
                        ]
                    )
                ]
            ),
            "review_node_bindings": bindings,
            "minimum_evidence": evidence,
        }
    )


def _validate_hydrated_candidate(
    candidate: ProtocolControlAgentWireCandidate,
    batch: ProtocolControlDispositionBatch,
) -> None:
    hydrated = hydrate_protocol_control_agent_output(_wire(candidate=candidate), batch)
    result = hydrated.candidates[0]
    _validate_candidate(
        result,
        unit_by_id={item.structure_unit_id: item for item in batch.owned_units},
        allowed_span_ids=set(batch.owned_source_span_ids),
        workflow_targets=batch.known_workflow_stage_targets,
        procedure_targets=batch.known_procedure_targets,
        official_codes={item.official_code for item in batch.known_official_targets},
        procedure_ids={
            item.catalog_item_id for item in batch.known_procedure_targets
        },
        candidate_ids={result.control_candidate_id},
    )


def test_wire_hydration_accepts_cross_stage_validity_supplement() -> None:
    batch = _batch_with_baseline()
    candidate = _cross_stage_wire_candidate(
        affected_id="stage:baseline:1",
        bindings=[
            ProtocolControlAgentWireNode(
                workflow_stage_id="stage:baseline:1",
                review_stage=ReviewStage.BASELINE,
                role=ReviewNodeRole.DECIDE_AT_NODE,
                guidance=None,
            )
        ],
        evidence=[
            ProtocolControlAgentWireEvidence(
                fact_type="lab_report",
                description="核对首次给药前28天内病毒学结果",
                due_stage=ReviewStage.BASELINE,
                required_source_types=["实验室报告"],
                workflow_stage_ids=["stage:baseline:1"],
                source_policy=_evidence_policy("span:01", "年龄至少18岁"),
                atom_refs=[
                    {"layer": "obligation", "group_index": 0, "atom_index": 0}
                ],
            )
        ],
    )
    candidate = candidate.model_copy(update={"exception_expression": None})
    hydrated = hydrate_protocol_control_agent_output(_wire(candidate=candidate), batch)
    relation = hydrated.candidates[0].semantics.cross_source_relations[0]
    assert relation.affected_workflow_stage_id == "stage:baseline:1"


def test_syn_reject_01_full_candidate_rejects_early_future_anchor_decision() -> None:
    batch = _batch_with_baseline()
    batch = batch.model_copy(
        update={
            "owned_units": [
                batch.owned_units[0].model_copy(
                    update={"excerpt": "年龄至少18岁；首次给药前28天内的结果有效。"}
                ),
                *batch.owned_units[1:],
            ]
        }
    )
    candidate = _cross_stage_wire_candidate(
        affected_id="stage:screening:one",
        bindings=[
            ProtocolControlAgentWireNode(
                workflow_stage_id="stage:screening:one",
                review_stage=ReviewStage.SCREENING,
                role=ReviewNodeRole.DECIDE_AT_NODE,
                guidance=None,
            )
        ],
        evidence=[
            ProtocolControlAgentWireEvidence(
                fact_type="lab_report",
                description="筛选期核对结果有效期",
                due_stage=ReviewStage.SCREENING,
                required_source_types=["实验室报告"],
                workflow_stage_ids=["stage:screening:one"],
                source_policy=_evidence_policy(
                    "span:01", "首次给药前28天内的结果有效"
                ),
                atom_refs=[
                    {"layer": "obligation", "group_index": 0, "atom_index": 0}
                ],
            )
        ],
    )
    candidate = candidate.model_copy(
        update={
            "exception_expression": None,
            "obligation_expression": ProtocolControlAgentWireObligationDnf(
                groups=[
                    ProtocolControlAgentWireObligationGroup(
                        atoms=[
                            ProtocolControlAgentWireObligationAtom(
                                kind=ControlObligationKind.VERIFY_RESULT_VALIDITY,
                                evaluation=_timed_evaluation(
                                    "首次给药前28天内的结果有效",
                                    "span:01",
                                    "首次给药前28天内的结果有效",
                                ),
                                statement="首次给药前28天内的结果有效",
                                time_constraint={
                                    "anchor_type": "first_dose_date",
                                    "direction": "before",
                                    "upper_bound_days": 28,
                                },
                                prospective_period=None,
                                source_span_ids=["span:01"],
                                source_excerpts=["首次给药前28天内的结果有效"],
                                requires_professional_judgment=False,
                            )
                        ]
                    )
                ]
            ),
        }
    )

    with pytest.raises(
        ProtocolControlGateError,
        match="EARLY_DECISION_FOR_FUTURE_ANCHOR",
    ):
        _validate_hydrated_candidate(candidate, batch)


def test_syn_reject_05_full_candidate_cannot_mix_execution_and_later_validity() -> None:
    source_text = "年龄至少18岁；筛选期应完成病毒学检查；首次给药前28天内的结果有效。"
    batch = _batch_with_baseline()
    batch = batch.model_copy(
        update={
            "owned_units": [
                batch.owned_units[0].model_copy(update={"excerpt": source_text}),
                *batch.owned_units[1:],
            ]
        }
    )
    candidate = _cross_stage_wire_candidate(
        affected_id="stage:baseline:1",
        bindings=[
            ProtocolControlAgentWireNode(
                workflow_stage_id="stage:screening:one",
                review_stage=ReviewStage.SCREENING,
                role=ReviewNodeRole.EARLY_ATTENTION,
                guidance=None,
            ),
            ProtocolControlAgentWireNode(
                workflow_stage_id="stage:baseline:1",
                review_stage=ReviewStage.BASELINE,
                role=ReviewNodeRole.DECIDE_AT_NODE,
                guidance=None,
            ),
        ],
        evidence=[
            ProtocolControlAgentWireEvidence(
                fact_type="lab_report",
                description="核对首次给药前28天内病毒学结果",
                due_stage=ReviewStage.BASELINE,
                required_source_types=["实验室报告"],
                workflow_stage_ids=["stage:baseline:1"],
                source_policy=_evidence_policy(
                    "span:01", "筛选期应完成病毒学检查"
                ),
                atom_refs=[
                    {"layer": "obligation", "group_index": 0, "atom_index": 0}
                ],
            )
        ],
    )
    candidate = candidate.model_copy(
        update={
            "exception_expression": None,
            "obligation_expression": ProtocolControlAgentWireObligationDnf(
                groups=[
                    ProtocolControlAgentWireObligationGroup(
                        atoms=[
                            ProtocolControlAgentWireObligationAtom(
                                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                                evaluation=_evaluation(
                                    "筛选期应完成病毒学检查",
                                    "span:01",
                                    "筛选期应完成病毒学检查",
                                ),
                                statement="筛选期应完成病毒学检查",
                                time_constraint=None,
                                prospective_period=None,
                                source_span_ids=["span:01"],
                                source_excerpts=["筛选期应完成病毒学检查"],
                                requires_professional_judgment=False,
                            ),
                            ProtocolControlAgentWireObligationAtom(
                                kind=ControlObligationKind.VERIFY_RESULT_VALIDITY,
                                evaluation=_timed_evaluation(
                                    "首次给药前28天内的结果有效",
                                    "span:01",
                                    "首次给药前28天内的结果有效",
                                ),
                                statement="首次给药前28天内的结果有效",
                                time_constraint={
                                    "anchor_type": "first_dose_date",
                                    "direction": "before",
                                    "upper_bound_days": 28,
                                },
                                prospective_period=None,
                                source_span_ids=["span:01"],
                                source_excerpts=["首次给药前28天内的结果有效"],
                                requires_professional_judgment=False,
                            ),
                        ]
                    )
                ]
            )
        }
    )

    with pytest.raises(
        ProtocolControlGateError,
        match="MIXED_DECISION_STAGE_CONTROL",
    ):
        _validate_hydrated_candidate(candidate, batch)


def test_repair_prompt_includes_cross_stage_supplement_guidance() -> None:
    prompt = build_protocol_control_repair_prompt(
        batch=_batch_with_baseline(),
        problem="PUBLICATION_GATE_REJECTED: EARLY_DECISION_FOR_FUTURE_ANCHOR",
    )
    assert "affected_workflow_stage_id 必须选择" in prompt
    assert "early_attention" in prompt

    mixed_prompt = build_protocol_control_repair_prompt(
        batch=_batch_with_baseline(),
        problem="PUBLICATION_GATE_REJECTED: MIXED_DECISION_STAGE_CONTROL",
    )
    assert "拆成两个独立候选" in mixed_prompt
    assert "不得留在同一候选中" in mixed_prompt
