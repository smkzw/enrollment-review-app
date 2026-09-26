"""Publication repair scope for cross-stage candidate repartition (slice61ab)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agents.protocol_control_deconstructor import (
    CONTROL_AGENT_WIRE_VERSION,
    ProtocolControlAgentResponse,
    ProtocolControlAgentRunner,
    ProtocolControlAgentWire,
    ProtocolControlAgentWireCandidate,
    ProtocolControlAgentWireDisposition,
    ProtocolControlAgentWireEvidence,
    ProtocolControlAgentWireNode,
    ProtocolControlAgentWireObligationAtom,
    ProtocolControlAgentWireObligationDnf,
    ProtocolControlAgentWireObligationGroup,
    ProtocolControlAgentWireRelation,
    ProtocolControlAgentWireValidationError,
    _validate_known_targets,
    _repair_problem_guidance,
    _restore_bounded_wire_repair,
)
from app.domain.contracts.enums import ReviewStage
from app.domain.contracts.protocol_controls import (
    ControlObligationKind,
    ControlRelationTargetKind,
    CrossSourceRelationKind,
    KnownRequiredProcedureTarget,
    StructureUnitDispositionKind,
)
from app.protocols.protocol_control_gate import (
    ProtocolControlGateError,
    _check_conditional_exemption_binding,
    _check_conditional_exemption_scope_split,
    _check_exemption_evidence_modality,
    _check_mixed_decision_stage_control,
    _validate_candidate,
)
from app.protocols.protocol_control_planning import detect_required_action_kinds
from app.protocols.protocol_control_repair_errors import (
    CANDIDATE_EXPRESSION_REPAIR_GATE_CODES,
    CANDIDATE_REPARTITION_GATE_CODES,
    SOURCE_CLOSURE_REWRITE_GATE_CODES,
    combined_repair_error,
    publication_repair_error,
)
from tests.v2.protocols.test_slice58c_control_deconstructor import (
    _FakeTransport,
    _evidence_policy,
    _evaluation,
    _timed_evaluation,
    _wire,
)
from tests.v2.protocols.test_slice60zz_cross_stage_supplement_contract import (
    _batch_with_baseline,
    _cross_stage_wire_candidate,
)

def test_mixed_decision_stage_control_authorizes_candidate_repartition() -> None:
    candidate = SimpleNamespace(
        control_candidate_id="pcc-mixed",
        frozen_structure_unit_ids=["su-a", "su-b"],
    )
    error = publication_repair_error(
        issues=[
            SimpleNamespace(
                code="MIXED_DECISION_STAGE_CONTROL",
                message="筛选期应完成的无锚点操作与基线/随机/首次给药前有效性判定必须拆成不同候选",
                entity_id="pcc-mixed",
            )
        ],
        candidate_by_id={"pcc-mixed": candidate},
        control_to_candidate={},
        default_structure_unit_ids=["su-fallback"],
    )

    assert error.allow_candidate_repartition is True
    assert error.candidate_ids == ("pcc-mixed",)
    assert error.structure_unit_ids == ("su-a", "su-b")
    assert "MIXED_DECISION_STAGE_CONTROL" in str(error)


def test_two_execution_visits_allow_source_bounded_repartition() -> None:
    batch = _batch_with_baseline()
    baseline_procedure = KnownRequiredProcedureTarget(
        catalog_item_id="procedure-baseline-1",
        label="基线期检查",
        visit_instance="baseline-1",
        review_stage=ReviewStage.BASELINE,
        position=1,
        source_span_ids=["span:procedure:baseline"],
    )
    batch = batch.model_copy(update={
        "known_procedure_targets": [*batch.known_procedure_targets, baseline_procedure],
    })
    candidate = _cross_stage_wire_candidate(
        affected_id="stage:baseline:1", bindings=[], evidence=[],
    )
    original_relation = candidate.cross_source_relations[0]
    original_atom = candidate.obligation_expression.groups[0].atoms[0]
    candidate = candidate.model_copy(update={
        "cross_source_relations": [
            original_relation,
            original_relation.model_copy(update={
                "external_target_id": "procedure-baseline-1",
            }),
        ],
        "obligation_expression": ProtocolControlAgentWireObligationDnf(groups=[
            ProtocolControlAgentWireObligationGroup(atoms=[
                ProtocolControlAgentWireObligationAtom.model_validate({
                    **original_atom.model_dump(mode="json"),
                    "kind": ControlObligationKind.COMPLETE_OR_VERIFY,
                    "time_constraint": None,
                    "evaluation": _evaluation(
                        "完成检查", "span:01", "年龄至少18岁",
                    ),
                }),
            ]),
        ]),
    })
    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="PROCEDURE_AFFECTED_STAGE_MISMATCH",
    ) as failure:
        _validate_known_targets(candidate, batch=batch)
    assert failure.value.allow_candidate_repartition is True

    single_target = candidate.model_copy(update={
        "cross_source_relations": [original_relation],
    })
    with pytest.raises(ProtocolControlAgentWireValidationError) as single_failure:
        _validate_known_targets(single_target, batch=batch)
    assert single_failure.value.allow_candidate_repartition is False


def test_mixed_trigger_decision_stages_authorizes_candidate_repartition() -> None:
    error = publication_repair_error(
        issues=[
            SimpleNamespace(
                code="MIXED_TRIGGER_DECISION_STAGES",
                message="筛选时触发的结论与基线/随机/首次给药前触发的结论必须拆成不同候选",
                entity_id="pcc-trigger",
            )
        ],
        candidate_by_id={
            "pcc-trigger": SimpleNamespace(
                control_candidate_id="pcc-trigger",
                frozen_structure_unit_ids=["su-trigger"],
            )
        },
        control_to_candidate={},
        default_structure_unit_ids=[],
    )

    assert error.allow_candidate_repartition is True


@pytest.mark.parametrize(
    "code",
    ["BASELINE_VALUE_SCOPE_MIXED", "MIXED_OBLIGATION_KIND_SCOPE"],
)
def test_temporal_mixed_scope_authorizes_source_preserving_repartition(code: str) -> None:
    error = publication_repair_error(
        issues=[SimpleNamespace(code=code, message="须分别表达", entity_id="pcc-mixed")],
        candidate_by_id={
            "pcc-mixed": SimpleNamespace(
                control_candidate_id="pcc-mixed",
                frozen_structure_unit_ids=["su-a", "su-b"],
            )
        },
        control_to_candidate={},
        default_structure_unit_ids=[],
    )

    assert error.allow_candidate_repartition is True
    assert error.candidate_ids == ("pcc-mixed",)
    assert error.structure_unit_ids == ("su-a", "su-b")


def test_unrelated_gate_codes_do_not_authorize_candidate_repartition() -> None:
    error = publication_repair_error(
        issues=[
            SimpleNamespace(
                code="EARLY_DECISION_FOR_FUTURE_ANCHOR",
                message="不得提前判定未来锚点",
                entity_id="pcc-early",
            )
        ],
        candidate_by_id={
            "pcc-early": SimpleNamespace(
                control_candidate_id="pcc-early",
                frozen_structure_unit_ids=["su-early"],
            )
        },
        control_to_candidate={},
        default_structure_unit_ids=[],
    )

    assert error.allow_candidate_repartition is False


def test_candidate_repartition_gate_codes_are_gate_level_not_project_specific() -> None:
    assert "ACTION_TARGET_SCOPE_MISMATCH" in CANDIDATE_REPARTITION_GATE_CODES
    assert "MIXED_DECISION_STAGE_CONTROL" in CANDIDATE_REPARTITION_GATE_CODES
    assert "BASELINE_VALUE_SCOPE_MIXED" in CANDIDATE_REPARTITION_GATE_CODES
    assert "MIXED_OBLIGATION_KIND_SCOPE" in CANDIDATE_REPARTITION_GATE_CODES
    assert "CONDITIONAL_EXEMPTION_BINDING_MISSING" not in CANDIDATE_REPARTITION_GATE_CODES
    assert (
        "CONDITIONAL_EXEMPTION_BINDING_MISSING"
        in CANDIDATE_EXPRESSION_REPAIR_GATE_CODES
    )
    assert "CONDITIONAL_EXEMPTION_SCOPE_SPLIT" in SOURCE_CLOSURE_REWRITE_GATE_CODES
    assert "CONDITIONAL_EXEMPTION_SCOPE_SPLIT" not in CANDIDATE_REPARTITION_GATE_CODES
    assert all(
        not code.startswith("d001") and "viral" not in code.lower()
        for code in CANDIDATE_REPARTITION_GATE_CODES
    )


def test_conditional_exemption_binding_allows_bounded_obligation_regrouping() -> None:
    regrouped_wire = _mixed_decision_initial_wire()
    regrouped = regrouped_wire.candidate_drafts[0]
    atoms = regrouped.obligation_expression.groups[0].atoms
    split = regrouped.model_copy(
        update={
            "obligation_expression": regrouped.obligation_expression.model_copy(
                update={
                    "groups": [
                        ProtocolControlAgentWireObligationGroup(atoms=[atoms[0]]),
                        ProtocolControlAgentWireObligationGroup(atoms=[atoms[1]]),
                    ]
                }
            )
        }
    )
    previous = regrouped_wire.model_copy(update={"candidate_drafts": [split]})
    current = regrouped_wire

    restored, applied = _restore_bounded_wire_repair(
        previous,
        current,
        mutable_structure_unit_ids={"su-01", "su-02"},
        mutable_candidate_source_keys={("su-01", "su-02")},
        allow_candidate_repartition=False,
    )

    assert applied is False
    assert restored.candidate_drafts == [regrouped]
    assert len(restored.candidate_drafts[0].obligation_expression.groups) == 1


def test_conditional_exemption_binding_uses_fixed_candidate_expression_scope() -> None:
    candidate = SimpleNamespace(
        control_candidate_id="pcc-waiver",
        frozen_structure_unit_ids=["su-waiver"],
    )
    error = publication_repair_error(
        issues=[
            SimpleNamespace(
                code="CONDITIONAL_EXEMPTION_BINDING_MISSING",
                message="结果有效期与免予后果必须在同一义务组",
                entity_id="pcc-waiver",
                candidate_ids=(),
                structure_unit_ids=(),
                obligation_source_span_ids=("span:waiver",),
            )
        ],
        candidate_by_id={"pcc-waiver": candidate},
        control_to_candidate={},
        default_structure_unit_ids=[],
    )

    assert error.allow_candidate_repartition is False
    assert error.candidate_ids == ("pcc-waiver",)
    assert error.obligation_source_span_ids == ()


def test_planning_freezes_exemption_as_required_semantic_action() -> None:
    assert detect_required_action_kinds(
        "可接受在首次给药前28天内的结果，筛选期/基线期无需再次检查。"
    ) == ("preserve_exemption_condition",)


def _conditional_exemption_expression(*, keep_validity: bool):
    atoms = []
    if keep_validity:
        atoms.append(
            ProtocolControlAgentWireObligationAtom(
                kind=ControlObligationKind.VERIFY_RESULT_VALIDITY,
                evaluation=_timed_evaluation(
                    "病毒学检查结果在首次给药前28天内有效",
                    "span:02",
                    "可接受在首次给药前28天内的结果",
                ),
                statement="病毒学检查结果在首次给药前28天内有效",
                time_constraint={
                    "anchor_type": "first_dose_date",
                    "direction": "before",
                    "upper_bound_days": 28,
                },
                prospective_period=None,
                source_span_ids=["span:02"],
                source_excerpts=["可接受在首次给药前28天内的结果"],
                requires_professional_judgment=False,
            )
        )
    atoms.append(
        ProtocolControlAgentWireObligationAtom(
            kind=ControlObligationKind.COMPLETE_OR_VERIFY,
            evaluation=_evaluation(
                "筛选期/基线期无需再次检查",
                "span:02",
                "筛选期/基线期无需再次检查",
            ),
            statement="筛选期/基线期无需再次检查",
            time_constraint=None,
            prospective_period=None,
            source_span_ids=["span:02"],
            source_excerpts=["筛选期/基线期无需再次检查"],
            requires_professional_judgment=False,
        )
    )
    return ProtocolControlAgentWireObligationDnf(
        groups=[ProtocolControlAgentWireObligationGroup(atoms=atoms)]
    )


def test_conditional_exemption_cannot_lose_its_same_source_condition() -> None:
    batch = _repartition_regression_batch()
    units = [
        unit.model_copy(
            update={
                "excerpt": "可接受在首次给药前28天内的结果，筛选期/基线期无需再次检查。"
            }
        )
        for unit in batch.owned_units
        if unit.structure_unit_id == "su-02"
    ]

    with pytest.raises(
        ProtocolControlGateError,
        match="CONDITIONAL_EXEMPTION_BINDING_MISSING",
    ):
        _check_conditional_exemption_binding(
            entity_id="candidate:conditional-exemption",
            units=units,
            trigger_expression=None,
            obligation_expression=_conditional_exemption_expression(
                keep_validity=False
            ),
        )


def test_conditional_exemption_accepts_condition_in_same_obligation_group() -> None:
    batch = _repartition_regression_batch()
    units = [
        unit.model_copy(
            update={
                "excerpt": "可接受在首次给药前28天内的结果，筛选期/基线期无需再次检查。"
            }
        )
        for unit in batch.owned_units
        if unit.structure_unit_id == "su-02"
    ]

    _check_conditional_exemption_binding(
        entity_id="candidate:conditional-exemption",
        units=units,
        trigger_expression=None,
        obligation_expression=_conditional_exemption_expression(keep_validity=True),
    )


def test_conditional_exemption_is_not_mislabeled_as_current_stage_action() -> None:
    _check_mixed_decision_stage_control(
        entity_id="candidate:conditional-exemption",
        obligation_expression=_conditional_exemption_expression(keep_validity=True),
    )


def test_exemption_evidence_cannot_require_the_waived_action_not_to_occur() -> None:
    batch = _repartition_regression_batch()
    units = [
        unit.model_copy(
            update={
                "excerpt": "可接受在首次给药前28天内的结果，筛选期/基线期无需再次检查。"
            }
        )
        for unit in batch.owned_units
        if unit.structure_unit_id == "su-02"
    ]
    for description in (
        "筛选期/基线期访视记录，确认未重复执行病毒学检查",
        "报告日期须在首次给药前28天内，且筛选期/基线期未重复执行病毒学检查",
        "确认筛选期未重新执行病毒学检查",
        "确认基线期未再行病毒学检测",
        "确认筛选期未做病毒学检查",
        "无重复病毒学检查记录",
        "no repeat virology testing at screening",
    ):
        with pytest.raises(
            ProtocolControlGateError,
            match="EXEMPTION_EVIDENCE_OVERSTATED",
        ):
            _check_exemption_evidence_modality(
                entity_id="candidate:waiver-evidence",
                units=units,
                obligation_expression=_conditional_exemption_expression(
                    keep_validity=True
                ),
                evidence=[SimpleNamespace(description=description)],
            )


def test_exemption_evidence_may_verify_the_qualifying_condition() -> None:
    batch = _repartition_regression_batch()
    units = [
        unit.model_copy(
            update={
                "excerpt": "可接受在首次给药前28天内的结果，筛选期/基线期无需再次检查。"
            }
        )
        for unit in batch.owned_units
        if unit.structure_unit_id == "su-02"
    ]
    _check_exemption_evidence_modality(
        entity_id="candidate:waiver-evidence",
        units=units,
        obligation_expression=_conditional_exemption_expression(keep_validity=True),
        evidence=[
            SimpleNamespace(
                description="病毒学检查报告，确认检测日期在首次给药前28天内"
            )
        ],
    )


def test_exemption_evidence_guard_is_scoped_to_source_waiver() -> None:
    batch = _repartition_regression_batch()
    units = [
        unit
        for unit in batch.owned_units
        if unit.structure_unit_id == "su-02"
    ]
    _check_exemption_evidence_modality(
        entity_id="candidate:no-source-waiver",
        units=units,
        obligation_expression=_conditional_exemption_expression(keep_validity=True),
        evidence=[SimpleNamespace(description="确认筛选期未重新执行病毒学检查")],
    )


def _scope_split_entities():
    screening = SimpleNamespace(
        control_candidate_id="pcc-screening",
        frozen_structure_unit_ids=["su-02"],
        semantics=SimpleNamespace(
            obligation_expression=ProtocolControlAgentWireObligationDnf(
                groups=[
                    ProtocolControlAgentWireObligationGroup(
                        atoms=[
                            ProtocolControlAgentWireObligationAtom(
                                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                                evaluation=_evaluation(
                                    "按标准程序完成三项检查",
                                    "span:02",
                                    "将根据标准程序进行八项检查",
                                ),
                                statement="按标准程序完成三项检查",
                                time_constraint=None,
                                prospective_period=None,
                                source_span_ids=["span:02"],
                                source_excerpts=["将根据标准程序进行八项检查"],
                                requires_professional_judgment=False,
                            )
                        ]
                    )
                ]
            )
        ),
    )
    validity = SimpleNamespace(
        control_candidate_id="pcc-validity",
        frozen_structure_unit_ids=["su-02"],
        semantics=SimpleNamespace(
            obligation_expression=_conditional_exemption_expression(
                keep_validity=True
            )
        ),
    )
    return screening, validity


def test_conditional_exemption_scope_split_rejects_unconditional_sibling() -> None:
    batch = _repartition_regression_batch()
    unit = next(
        item for item in batch.owned_units if item.structure_unit_id == "su-02"
    ).model_copy(
        update={
            "excerpt": "将根据标准程序进行八项检查。可接受首次给药前28天内的结果，筛选期/基线期无需再次检查。"
        }
    )
    screening, validity = _scope_split_entities()

    with pytest.raises(
        ProtocolControlGateError,
        match="CONDITIONAL_EXEMPTION_SCOPE_SPLIT",
    ) as error:
        _check_conditional_exemption_scope_split(
            [screening, validity],
            unit_by_id={"su-02": unit},
            candidate_scope=True,
        )

    assert error.value.candidate_ids == ("pcc-screening", "pcc-validity")
    assert error.value.structure_unit_ids == ("su-02",)


def test_scope_split_authorizes_source_closure_rewrite_not_repartition() -> None:
    screening, validity = _scope_split_entities()
    error = publication_repair_error(
        issues=[
            SimpleNamespace(
                code="CONDITIONAL_EXEMPTION_SCOPE_SPLIT",
                message="同源条件豁免不得拆成兄弟候选中的无条件执行义务",
                entity_id="pcc-screening",
                candidate_ids=("pcc-screening", "pcc-validity"),
                structure_unit_ids=("su-02",),
                obligation_source_span_ids=("span:02",),
            )
        ],
        candidate_by_id={
            "pcc-screening": screening,
            "pcc-validity": validity,
        },
        control_to_candidate={},
        default_structure_unit_ids=[],
    )

    assert error.allow_source_closure_rewrite is True
    assert error.allow_candidate_repartition is False
    assert error.candidate_ids == ("pcc-screening", "pcc-validity")
    assert error.obligation_source_span_ids == ()


def test_scope_split_drops_atom_spans_from_other_publication_issues() -> None:
    screening, validity = _scope_split_entities()
    error = publication_repair_error(
        issues=[
            SimpleNamespace(
                code="CONDITIONAL_EXEMPTION_SCOPE_SPLIT",
                message="同源条件豁免不得拆成无条件执行义务",
                entity_id="pcc-screening",
                candidate_ids=("pcc-screening", "pcc-validity"),
                structure_unit_ids=("su-02",),
                obligation_source_span_ids=("span:waiver",),
            ),
            SimpleNamespace(
                code="RECORD_PRECISION_COMPRESSED",
                message="另一个原子级问题",
                entity_id="pcc-other",
                candidate_ids=("pcc-other",),
                structure_unit_ids=("su-01",),
                obligation_source_span_ids=("span:other",),
            ),
        ],
        candidate_by_id={
            "pcc-screening": screening,
            "pcc-validity": validity,
        },
        control_to_candidate={},
        default_structure_unit_ids=[],
    )

    assert error.allow_source_closure_rewrite is True
    assert error.obligation_source_span_ids == ()
    assert error.candidate_ids == ("pcc-screening", "pcc-validity")
    assert error.structure_unit_ids == ("su-02",)
    assert "RECORD_PRECISION_COMPRESSED" in str(error)


def test_combined_source_closure_repair_drops_other_atom_spans() -> None:
    error = combined_repair_error(
        ProtocolControlAgentWireValidationError(
            "PUBLICATION_GATE_REJECTED",
            "需要来源闭包重写",
            structure_unit_ids=["su-02"],
            candidate_ids=["pcc-screening"],
            allow_source_closure_rewrite=True,
        ),
        ProtocolControlAgentWireValidationError(
            "OTHER_REPAIR",
            "另一个原子级问题",
            structure_unit_ids=["su-01"],
            candidate_ids=["pcc-other"],
            obligation_source_span_ids=["span:other"],
        ),
    )

    assert error.allow_source_closure_rewrite is True
    assert error.obligation_source_span_ids == ()
    assert error.candidate_ids == ("pcc-screening",)
    assert error.structure_unit_ids == ("su-02",)
    assert "OTHER_REPAIR" in str(error)


def test_control_scope_split_resolves_candidate_for_source_closure() -> None:
    screening, _ = _scope_split_entities()
    error = publication_repair_error(
        issues=[
            SimpleNamespace(
                code="CONDITIONAL_EXEMPTION_SCOPE_SPLIT",
                message="控制级条件豁免范围拆分",
                entity_id="control-screening",
                candidate_ids=(),
                structure_unit_ids=("su-02",),
                obligation_source_span_ids=("span:02",),
            )
        ],
        candidate_by_id={"pcc-screening": screening},
        control_to_candidate={"control-screening": "pcc-screening"},
        default_structure_unit_ids=[],
    )

    assert error.allow_source_closure_rewrite is True
    assert error.candidate_ids == ("pcc-screening",)
    assert error.structure_unit_ids == ("su-02",)
    assert error.obligation_source_span_ids == ()


def test_control_scope_gate_issue_seeds_originating_candidate_closure() -> None:
    batch = _repartition_regression_batch()
    unit = next(
        item for item in batch.owned_units if item.structure_unit_id == "su-02"
    ).model_copy(
        update={
            "excerpt": "将根据标准程序进行八项检查。可接受首次给药前28天内的结果，筛选期/基线期无需再次检查。"
        }
    )
    screening, validity = _scope_split_entities()
    controls = [
        SimpleNamespace(
            protocol_control_id="control-screening",
            originating_candidate_id="pcc-screening",
            source_structure_unit_ids=["su-02"],
            semantics=screening.semantics,
        ),
        SimpleNamespace(
            protocol_control_id="control-validity",
            originating_candidate_id="pcc-validity",
            source_structure_unit_ids=["su-02"],
            semantics=validity.semantics,
        ),
    ]

    with pytest.raises(ProtocolControlGateError) as gate_error:
        _check_conditional_exemption_scope_split(
            controls,
            unit_by_id={"su-02": unit},
            candidate_scope=False,
        )

    assert gate_error.value.code == "CONDITIONAL_EXEMPTION_SCOPE_SPLIT"
    assert gate_error.value.entity_id == "control-screening"
    assert gate_error.value.candidate_ids == ()
    issue = SimpleNamespace(
        code=gate_error.value.code,
        message=str(gate_error.value),
        entity_id=gate_error.value.entity_id,
        candidate_ids=gate_error.value.candidate_ids,
        structure_unit_ids=gate_error.value.structure_unit_ids,
        obligation_source_span_ids=(
            gate_error.value.obligation_source_span_ids
        ),
    )
    error = publication_repair_error(
        issues=[issue],
        candidate_by_id={
            "pcc-screening": screening,
            "pcc-validity": validity,
        },
        control_to_candidate={
            control.protocol_control_id: control.originating_candidate_id
            for control in controls
        },
        default_structure_unit_ids=[],
    )

    assert error.allow_source_closure_rewrite is True
    assert error.candidate_ids == ("pcc-screening",)
    assert error.structure_unit_ids == ("su-02",)


def test_source_closure_rewrite_allows_merge_within_closure() -> None:
    previous = _two_same_source_candidates_wire()
    merged = previous.candidate_drafts[0].model_copy(
        update={
            "title": "合并后的同源候选",
            "obligation_expression": ProtocolControlAgentWireObligationDnf(
                groups=[
                    ProtocolControlAgentWireObligationGroup(
                        atoms=[
                            *previous.candidate_drafts[0]
                            .obligation_expression.groups[0]
                            .atoms,
                            *previous.candidate_drafts[1]
                            .obligation_expression.groups[0]
                            .atoms,
                        ]
                    )
                ]
            ),
        }
    )
    current = previous.model_copy(update={"candidate_drafts": [merged]})

    restored, applied = _restore_bounded_wire_repair(
        previous,
        current,
        mutable_structure_unit_ids={"su-02"},
        mutable_candidate_source_keys={("su-02",)},
        mutable_candidate_source_union={"su-02"},
        allow_source_closure_rewrite=True,
    )

    assert len(restored.candidate_drafts) == 1
    assert restored.candidate_drafts[0].title == "合并后的同源候选"


def test_scope_split_runner_uses_source_closure_not_atom_repair() -> None:
    full_batch = _repartition_regression_batch()
    screening_unit = next(
        unit
        for unit in full_batch.owned_units
        if unit.structure_unit_id == "su-02"
    )
    batch = full_batch.model_copy(
        update={
            "owned_units": [screening_unit],
            "owned_structure_unit_ids": ["su-02"],
            "owned_source_span_ids": ["span:02"],
        }
    )
    first = _screening_execution_split_candidate()
    first_atom = first.obligation_expression.groups[0].atoms[0]
    second_atom = first_atom.model_copy(
        update={
            "statement": "筛选时记录末次用药日期",
            "evaluation": first_atom.evaluation.__class__.model_validate(
                _evaluation(
                    "筛选时记录末次用药日期",
                    "span:02",
                    "筛选时记录末次用药日期",
                )
            ),
            "source_excerpts": ["筛选时记录末次用药日期"],
        }
    )
    second = first.model_copy(
        update={
            "title": "末次用药日期记录",
            "obligation_expression": first.obligation_expression.model_copy(
                update={
                    "groups": [
                        first.obligation_expression.groups[0].model_copy(
                            update={"atoms": [second_atom]}
                        )
                    ]
                }
            ),
        }
    )
    template = _mixed_decision_repartition_wire()
    screening_disposition = next(
        disposition
        for disposition in template.dispositions
        if disposition.structure_unit_id == "su-02"
    )
    previous = template.model_copy(
        update={
            "dispositions": [screening_disposition],
            "candidate_drafts": [first, second],
        }
    )
    current = previous.model_copy(
        update={
            "candidate_drafts": [
                previous.candidate_drafts[0].model_copy(
                    update={
                        "title": "合并后的同源候选",
                        "obligation_expression": ProtocolControlAgentWireObligationDnf(
                            groups=[
                                ProtocolControlAgentWireObligationGroup(
                                    atoms=[
                                        *previous.candidate_drafts[0]
                                        .obligation_expression.groups[0]
                                        .atoms,
                                        *previous.candidate_drafts[1]
                                        .obligation_expression.groups[0]
                                        .atoms,
                                    ]
                                )
                            ]
                        ),
                    }
                )
            ]
        }
    )
    transport = _FakeTransport(
        [
            ProtocolControlAgentResponse(
                session_id="session-source-closure",
                text=previous.model_dump_json(),
            ),
            ProtocolControlAgentResponse(
                session_id="session-source-closure",
                text=current.model_dump_json(),
            ),
        ]
    )
    validator_calls = 0

    def validate_after_hydration(output) -> None:
        nonlocal validator_calls
        validator_calls += 1
        if validator_calls != 1:
            return
        candidate_by_id = {
            candidate.control_candidate_id: candidate
            for candidate in output.candidates
        }
        candidate_ids = tuple(candidate_by_id)
        raise publication_repair_error(
            issues=[
                SimpleNamespace(
                    code="CONDITIONAL_EXEMPTION_SCOPE_SPLIT",
                    message="同源条件豁免不得拆成无条件执行义务",
                    entity_id=candidate_ids[0],
                    candidate_ids=candidate_ids,
                    structure_unit_ids=("su-02",),
                    obligation_source_span_ids=("span:02",),
                ),
                SimpleNamespace(
                    code="RECORD_PRECISION_COMPRESSED",
                    message="同一轮另一个原子级问题",
                    entity_id=candidate_ids[0],
                    candidate_ids=(candidate_ids[0],),
                    structure_unit_ids=("su-02",),
                    obligation_source_span_ids=("span:other",),
                ),
            ],
            candidate_by_id=candidate_by_id,
            control_to_candidate={},
            default_structure_unit_ids=[],
        )

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        batch,
        transport,
        output_validator=validate_after_hydration,
    )

    assert result.status == "已解析"
    assert result.final_output is not None
    assert len(result.final_output.candidates) == 1
    assert validator_calls == 2


def test_scope_split_runner_rejects_source_closure_beyond_issue_authority() -> None:
    batch = _repartition_regression_batch()
    initial = _mixed_decision_initial_wire()
    spanning_candidate = initial.candidate_drafts[0].model_copy(
        update={
            "source_structure_unit_ids": ["su-01", "su-02"],
            "source_span_ids": ["span:01", "span:02"],
        }
    )
    initial = initial.model_copy(update={"candidate_drafts": [spanning_candidate]})
    transport = _FakeTransport(
        [
            ProtocolControlAgentResponse(
                session_id="session-source-closure-authority",
                text=initial.model_dump_json(),
            )
        ]
    )

    def validate_after_hydration(output) -> None:
        candidate = output.candidates[0]
        raise publication_repair_error(
            issues=[
                SimpleNamespace(
                    code="CONDITIONAL_EXEMPTION_SCOPE_SPLIT",
                    message="仅授权修订第二个结构单元的条件豁免",
                    entity_id=candidate.control_candidate_id,
                    candidate_ids=(candidate.control_candidate_id,),
                    structure_unit_ids=("su-02",),
                    obligation_source_span_ids=("span:02",),
                )
            ],
            candidate_by_id={candidate.control_candidate_id: candidate},
            control_to_candidate={},
            default_structure_unit_ids=[],
        )

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        batch,
        transport,
        output_validator=validate_after_hydration,
    )

    assert result.status == "需要核对"
    assert len(result.attempts) == 1
    assert result.attempts[-1].outcome == "publication_invalid"
    assert any(
        "缺少完整的机器可读修订范围" in issue
        for issue in result.attempts[-1].issues
    )


def test_source_closure_rewrite_allows_both_siblings_rewrite() -> None:
    previous = _two_same_source_candidates_wire()
    revised_first = previous.candidate_drafts[0].model_copy(
        update={"title": "修订后的第一个同源候选"}
    )
    revised_second = previous.candidate_drafts[1].model_copy(
        update={"title": "修订后的第二个同源候选"}
    )
    current = previous.model_copy(
        update={"candidate_drafts": [revised_second, revised_first]}
    )

    restored, applied = _restore_bounded_wire_repair(
        previous,
        current,
        mutable_structure_unit_ids={"su-02"},
        mutable_candidate_source_keys={("su-02",)},
        mutable_candidate_source_union={"su-02"},
        allow_source_closure_rewrite=True,
    )

    assert applied is True
    assert {candidate.title for candidate in restored.candidate_drafts} == {
        "修订后的第一个同源候选",
        "修订后的第二个同源候选",
    }


def test_source_closure_rewrite_restores_different_source_candidates() -> None:
    previous = _two_same_source_candidates_wire()
    frozen = previous.candidate_drafts[0].model_copy(
        update={
            "title": "不同来源冻结候选",
            "source_structure_unit_ids": ["su-01"],
        }
    )
    previous = previous.model_copy(
        update={"candidate_drafts": [*previous.candidate_drafts, frozen]}
    )
    revised = previous.candidate_drafts[1].model_copy(
        update={"title": "闭包内修订"}
    )
    changed_frozen = frozen.model_copy(update={"title": "模型越界改写"})
    current = previous.model_copy(
        update={
            "candidate_drafts": [
                changed_frozen,
                revised,
                previous.candidate_drafts[0],
            ]
        }
    )

    restored, applied = _restore_bounded_wire_repair(
        previous,
        current,
        mutable_structure_unit_ids={"su-02"},
        mutable_candidate_source_keys={("su-02",)},
        mutable_candidate_source_union={"su-02"},
        allow_source_closure_rewrite=True,
    )

    assert applied is True
    assert frozen in restored.candidate_drafts
    assert revised in restored.candidate_drafts


def test_source_closure_rewrite_rejects_source_loss() -> None:
    previous = _mixed_decision_repartition_wire()
    partial = previous.candidate_drafts[0].model_copy(
        update={"title": "闭包内修订但丢失 su-01"}
    )
    current = previous.model_copy(update={"candidate_drafts": [partial]})

    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="REPAIR_SCOPE_ESCAPE",
    ):
        _restore_bounded_wire_repair(
            previous,
            current,
            mutable_structure_unit_ids={"su-01", "su-02"},
            mutable_candidate_source_keys={("su-01", "su-02"), ("su-02",)},
            mutable_candidate_source_union={"su-01", "su-02"},
            allow_source_closure_rewrite=True,
        )


_SCOPE_SPLIT_GOLD_STANDARD_LEAK_TERMS = (
    "p804",
    "p805",
    "body.p804",
    "HBsAb",
    "HBeAg",
    "HBeAb",
    "八项检查",
    "su-86389",
    "624367a4829552da",
    "pcc-624367",
)


def test_scope_split_repair_guidance_avoids_parent_gold_standard_leaks() -> None:
    guidance = _repair_problem_guidance("CONDITIONAL_EXEMPTION_SCOPE_SPLIT")
    gate_message = (
        "同源条件豁免不得拆成兄弟候选中的无条件执行义务；"
        "被豁免操作必须与有效期及豁免条件保持同一语义范围"
    )

    for text in (guidance, gate_message):
        for term in _SCOPE_SPLIT_GOLD_STANDARD_LEAK_TERMS:
            assert term not in text
    assert "同一来源" in guidance
    assert "无条件" in guidance
    assert "有效期" in guidance


def test_source_closure_rewrite_allows_split_within_closure() -> None:
    combined = _screening_execution_split_candidate().model_copy(
        update={
            "title": "待拆分的同源候选",
            "obligation_expression": ProtocolControlAgentWireObligationDnf(
                groups=[
                    ProtocolControlAgentWireObligationGroup(
                        atoms=[
                            ProtocolControlAgentWireObligationAtom(
                                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                                evaluation=_evaluation(
                                    "筛选期应完成病毒学检查",
                                    "span:02",
                                    "筛选期应完成病毒学检查",
                                ),
                                statement="筛选期应完成病毒学检查",
                                time_constraint=None,
                                prospective_period=None,
                                source_span_ids=["span:02"],
                                source_excerpts=["筛选期应完成病毒学检查"],
                                requires_professional_judgment=False,
                            ),
                            *_conditional_exemption_expression(
                                keep_validity=True
                            ).groups[0].atoms,
                        ]
                    )
                ]
            ),
        }
    )
    previous = _mixed_decision_repartition_wire().model_copy(
        update={"candidate_drafts": [combined]}
    )
    split_first = _screening_execution_split_candidate().model_copy(
        update={"title": "拆分后执行候选"}
    )
    split_second = _baseline_validity_split_candidate().model_copy(
        update={
            "title": "拆分后有效窗候选",
            "source_structure_unit_ids": ["su-02"],
            "source_span_ids": ["span:02"],
        }
    )
    current = previous.model_copy(
        update={"candidate_drafts": [split_second, split_first]}
    )

    restored, applied = _restore_bounded_wire_repair(
        previous,
        current,
        mutable_structure_unit_ids={"su-02"},
        mutable_candidate_source_keys={("su-02",)},
        mutable_candidate_source_union={"su-02"},
        allow_source_closure_rewrite=True,
    )

    assert applied is True
    assert len(restored.candidate_drafts) == 2
    assert all(
        candidate.source_structure_unit_ids == ["su-02"]
        for candidate in restored.candidate_drafts
    )
    assert {candidate.title for candidate in restored.candidate_drafts} == {
        "拆分后执行候选",
        "拆分后有效窗候选",
    }


def test_source_closure_rewrite_rejects_cross_source_absorption() -> None:
    previous = _two_same_source_candidates_wire()
    absorbed = previous.candidate_drafts[1].model_copy(
        update={
            "title": "跨来源吸收改写",
            "source_structure_unit_ids": ["su-01", "su-02"],
        }
    )
    current = previous.model_copy(
        update={"candidate_drafts": [previous.candidate_drafts[0], absorbed]}
    )

    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="REPAIR_SCOPE_ESCAPE",
    ):
        _restore_bounded_wire_repair(
            previous,
            current,
            mutable_structure_unit_ids={"su-02"},
            mutable_candidate_source_keys={("su-02",)},
            mutable_candidate_source_union={"su-02"},
            allow_source_closure_rewrite=True,
        )


def test_source_closure_rewrite_rejects_empty_closure_candidates() -> None:
    previous = _two_same_source_candidates_wire()
    frozen = previous.candidate_drafts[0].model_copy(
        update={
            "title": "闭包外保留",
            "source_structure_unit_ids": ["su-01"],
        }
    )
    previous = previous.model_copy(
        update={"candidate_drafts": [frozen, *previous.candidate_drafts[1:]]}
    )
    current = previous.model_copy(update={"candidate_drafts": [frozen]})

    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="REPAIR_SCOPE_ESCAPE",
    ):
        _restore_bounded_wire_repair(
            previous,
            current,
            mutable_structure_unit_ids={"su-02"},
            mutable_candidate_source_keys={("su-02",)},
            mutable_candidate_source_union={"su-02"},
            allow_source_closure_rewrite=True,
        )


def test_source_closure_rewrite_freezes_multiple_different_source_siblings() -> None:
    same_source = _two_same_source_candidates_wire()
    frozen_first = same_source.candidate_drafts[0].model_copy(
        update={
            "title": "冻结来源候选一",
            "source_structure_unit_ids": ["su-01"],
        }
    )
    frozen_second = frozen_first.model_copy(update={"title": "冻结来源候选二"})
    previous = same_source.model_copy(
        update={
            "candidate_drafts": [
                *same_source.candidate_drafts,
                frozen_first,
                frozen_second,
            ]
        }
    )
    revised_first = previous.candidate_drafts[0].model_copy(
        update={"title": "闭包内第一个修订"}
    )
    revised_second = previous.candidate_drafts[1].model_copy(
        update={"title": "闭包内第二个修订"}
    )
    current = previous.model_copy(
        update={
            "candidate_drafts": [
                frozen_second.model_copy(update={"title": "越界改写二"}),
                revised_second,
                revised_first,
                frozen_first.model_copy(update={"title": "越界改写一"}),
            ]
        }
    )

    restored, applied = _restore_bounded_wire_repair(
        previous,
        current,
        mutable_structure_unit_ids={"su-02"},
        mutable_candidate_source_keys={("su-02",)},
        mutable_candidate_source_union={"su-02"},
        allow_source_closure_rewrite=True,
    )

    assert applied is True
    assert {candidate.title for candidate in restored.candidate_drafts} == {
        "闭包内第一个修订",
        "闭包内第二个修订",
        "冻结来源候选一",
        "冻结来源候选二",
    }


def test_source_closure_rewrite_shuffled_wire_order_uses_source_closure_not_title_sort() -> None:
    previous = _two_same_source_candidates_wire()
    frozen = previous.candidate_drafts[0].model_copy(
        update={
            "title": "Z-闭包外冻结",
            "source_structure_unit_ids": ["su-01"],
        }
    )
    mutable = previous.candidate_drafts[1].model_copy(update={"title": "A-闭包内待修订"})
    previous = previous.model_copy(update={"candidate_drafts": [frozen, mutable]})
    current = previous.model_copy(
        update={
            "candidate_drafts": [
                mutable.model_copy(update={"title": "A-已修订"}),
                frozen,
            ]
        }
    )

    restored, applied = _restore_bounded_wire_repair(
        previous,
        current,
        mutable_structure_unit_ids={"su-02"},
        mutable_candidate_source_keys={("su-02",)},
        mutable_candidate_source_union={"su-02"},
        allow_source_closure_rewrite=True,
    )

    assert applied is True
    assert [candidate.title for candidate in restored.candidate_drafts] == [
        "Z-闭包外冻结",
        "A-已修订",
    ]


def test_source_closure_rewrite_restored_split_pattern_still_triggers_scope_split_gate() -> None:
    batch = _repartition_regression_batch()
    unit = next(
        item for item in batch.owned_units if item.structure_unit_id == "su-02"
    ).model_copy(
        update={
            "excerpt": "将根据标准程序进行八项检查。可接受首次给药前28天内的结果，筛选期/基线期无需再次检查。"
        }
    )
    previous = _two_same_source_candidates_wire()
    cosmetic_first = previous.candidate_drafts[0].model_copy(
        update={"title": "假合并后的第一个候选"}
    )
    cosmetic_second = previous.candidate_drafts[1].model_copy(
        update={"title": "假合并后的第二个候选"}
    )
    current = previous.model_copy(
        update={"candidate_drafts": [cosmetic_second, cosmetic_first]}
    )

    restored, applied = _restore_bounded_wire_repair(
        previous,
        current,
        mutable_structure_unit_ids={"su-02"},
        mutable_candidate_source_keys={("su-02",)},
        mutable_candidate_source_union={"su-02"},
        allow_source_closure_rewrite=True,
    )

    assert applied is True
    screening, validity = _scope_split_entities()
    with pytest.raises(
        ProtocolControlGateError,
        match="CONDITIONAL_EXEMPTION_SCOPE_SPLIT",
    ):
        _check_conditional_exemption_scope_split(
            [screening, validity],
            unit_by_id={"su-02": unit},
            candidate_scope=True,
        )


def test_conditional_exemption_scope_accepts_one_bound_validity_candidate() -> None:
    batch = _repartition_regression_batch()
    unit = next(
        item for item in batch.owned_units if item.structure_unit_id == "su-02"
    ).model_copy(
        update={
            "excerpt": "可接受首次给药前28天内的结果。筛选期/基线期无需再次检查。"
        }
    )
    _, validity = _scope_split_entities()

    _check_conditional_exemption_scope_split(
        [validity],
        unit_by_id={"su-02": unit},
        candidate_scope=True,
    )


def test_combined_routine_action_and_waiver_still_requires_stage_split() -> None:
    expression = ProtocolControlAgentWireObligationDnf(
        groups=[
            ProtocolControlAgentWireObligationGroup(
                atoms=[
                    ProtocolControlAgentWireObligationAtom(
                        kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                        evaluation=_evaluation(
                            "完成三项检查，满足28天有效期时无需再次检查",
                            "span:02",
                            "完成三项检查，满足28天有效期时无需再次检查",
                        ),
                        statement="完成三项检查，满足28天有效期时无需再次检查",
                        time_constraint=None,
                        prospective_period=None,
                        source_span_ids=["span:02"],
                        source_excerpts=["完成三项检查，满足28天有效期时无需再次检查"],
                        requires_professional_judgment=False,
                    ),
                    ProtocolControlAgentWireObligationAtom(
                        kind=ControlObligationKind.VERIFY_RESULT_VALIDITY,
                        evaluation=_timed_evaluation(
                            "核对结果在首次给药前28天内有效",
                            "span:02",
                            "可接受首次给药前28天内的结果",
                        ),
                        statement="核对结果在首次给药前28天内有效",
                        time_constraint={
                            "anchor_type": "first_dose_date",
                            "direction": "before",
                            "upper_bound_days": 28,
                        },
                        prospective_period=None,
                        source_span_ids=["span:02"],
                        source_excerpts=["可接受首次给药前28天内的结果"],
                        requires_professional_judgment=False,
                    ),
                ]
            )
        ]
    )
    with pytest.raises(ProtocolControlGateError, match="MIXED_DECISION_STAGE_CONTROL"):
        _check_mixed_decision_stage_control(
            entity_id="candidate:combined-action-waiver",
            obligation_expression=expression,
        )


def _repartition_regression_batch():
    batch = _batch_with_baseline()
    owned_units = list(batch.owned_units)
    owned_units[0] = owned_units[0].model_copy(
        update={"excerpt": "年龄至少18岁；首次给药前28天内的结果有效。"}
    )
    owned_units[1] = owned_units[1].model_copy(
        update={"excerpt": "筛选期应完成病毒学检查；筛选时记录末次用药日期"}
    )
    return batch.model_copy(update={"owned_units": owned_units})


def _mixed_decision_stage_candidate() -> ProtocolControlAgentWireCandidate:
    return _cross_stage_wire_candidate(
        affected_id="stage:baseline:1",
        bindings=[
            ProtocolControlAgentWireNode(
                workflow_stage_id="stage:screening:one",
                review_stage=ReviewStage.SCREENING,
                role="early_attention",
                guidance=None,
            ),
            ProtocolControlAgentWireNode(
                workflow_stage_id="stage:baseline:1",
                review_stage=ReviewStage.BASELINE,
                role="decide_at_node",
                guidance=None,
            ),
        ],
        evidence=[
            ProtocolControlAgentWireEvidence(
                fact_type="lab_report",
                description="核对首次给药前28天内结果",
                due_stage=ReviewStage.BASELINE,
                required_source_types=["实验室报告"],
                workflow_stage_ids=["stage:baseline:1"],
                source_policy=_evidence_policy(
                    "span:01", "首次给药前28天内的结果有效"
                ),
                atom_refs=[
                    {"layer": "obligation", "group_index": 0, "atom_index": 0}
                ],
            )
        ],
    ).model_copy(
        update={
            "title": "混合筛选执行与基线有效窗",
            "applicability_expression": None,
            "source_structure_unit_ids": ["su-01", "su-02"],
            "source_span_ids": ["span:01", "span:02"],
            "exception_expression": None,
            "obligation_expression": ProtocolControlAgentWireObligationDnf(
                groups=[
                    ProtocolControlAgentWireObligationGroup(
                        atoms=[
                            ProtocolControlAgentWireObligationAtom(
                                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                                evaluation=_evaluation(
                                    "筛选期应完成病毒学检查",
                                    "span:02",
                                    "筛选期应完成病毒学检查",
                                ),
                                statement="筛选期应完成病毒学检查",
                                time_constraint=None,
                                prospective_period=None,
                                source_span_ids=["span:02"],
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
            ),
        }
    )


def _screening_execution_split_candidate() -> ProtocolControlAgentWireCandidate:
    return _cross_stage_wire_candidate(
        affected_id="stage:screening:one",
        bindings=[
            ProtocolControlAgentWireNode(
                workflow_stage_id="stage:screening:one",
                review_stage=ReviewStage.SCREENING,
                role="decide_at_node",
                guidance=None,
            )
        ],
        evidence=[
            ProtocolControlAgentWireEvidence(
                fact_type="lab_report",
                description="核对筛选期检查完成",
                due_stage=ReviewStage.SCREENING,
                required_source_types=["实验室报告"],
                workflow_stage_ids=["stage:screening:one"],
                source_policy=_evidence_policy(
                    "span:02", "筛选期应完成病毒学检查"
                ),
                atom_refs=[
                    {"layer": "obligation", "group_index": 0, "atom_index": 0}
                ],
            )
        ],
    ).model_copy(
        update={
            "title": "筛选期检查执行",
            "applicability_expression": None,
            "source_structure_unit_ids": ["su-02"],
            "source_span_ids": ["span:02"],
            "exception_expression": None,
            "cross_source_relations": [
                ProtocolControlAgentWireRelation(
                    kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
                    external_target_kind=ControlRelationTargetKind.REQUIRED_PROCEDURE,
                    external_target_id="procedure-screening-1",
                    candidate_side="left",
                    affected_workflow_stage_id="stage:screening:one",
                    notes="筛选期额外检查项目",
                )
            ],
            "obligation_expression": ProtocolControlAgentWireObligationDnf(
                groups=[
                    ProtocolControlAgentWireObligationGroup(
                        atoms=[
                            ProtocolControlAgentWireObligationAtom(
                                kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                                evaluation=_evaluation(
                                    "筛选期应完成病毒学检查",
                                    "span:02",
                                    "筛选期应完成病毒学检查",
                                ),
                                statement="筛选期应完成病毒学检查",
                                time_constraint=None,
                                prospective_period=None,
                                source_span_ids=["span:02"],
                                source_excerpts=["筛选期应完成病毒学检查"],
                                requires_professional_judgment=False,
                            )
                        ]
                    )
                ]
            ),
        }
    )


def _baseline_validity_split_candidate() -> ProtocolControlAgentWireCandidate:
    return _cross_stage_wire_candidate(
        affected_id="stage:baseline:1",
        bindings=[
            ProtocolControlAgentWireNode(
                workflow_stage_id="stage:baseline:1",
                review_stage=ReviewStage.BASELINE,
                role="decide_at_node",
                guidance=None,
            )
        ],
        evidence=[
            ProtocolControlAgentWireEvidence(
                fact_type="lab_report",
                description="核对首次给药前28天内结果",
                due_stage=ReviewStage.BASELINE,
                required_source_types=["实验室报告"],
                workflow_stage_ids=["stage:baseline:1"],
                source_policy=_evidence_policy(
                    "span:01", "首次给药前28天内的结果有效"
                ),
                atom_refs=[
                    {"layer": "obligation", "group_index": 0, "atom_index": 0}
                ],
            )
        ],
    ).model_copy(
        update={
            "title": "首次给药前28天有效窗",
            "applicability_expression": None,
            "source_structure_unit_ids": ["su-01", "su-02"],
            "source_span_ids": ["span:01", "span:02"],
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


def _mixed_decision_initial_wire() -> ProtocolControlAgentWire:
    wire = _wire(candidate=_mixed_decision_stage_candidate()).model_dump(mode="json")
    wire["dispositions"][1].update(
        disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value,
        notes="第二个单元参与混合候选",
    )
    return ProtocolControlAgentWire.model_validate(wire)


def _mixed_decision_repartition_wire() -> ProtocolControlAgentWire:
    screening = _screening_execution_split_candidate()
    validity = _baseline_validity_split_candidate()
    return ProtocolControlAgentWire(
        wire_version=CONTROL_AGENT_WIRE_VERSION,
        dispositions=[
            ProtocolControlAgentWireDisposition(
                structure_unit_id="su-01",
                disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                linked_official_code=None,
                linked_procedure_catalog_item_id=None,
                linked_procedure_catalog_item_ids=[],
                notes="基线有效窗来源",
            ),
            ProtocolControlAgentWireDisposition(
                structure_unit_id="su-02",
                disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                linked_official_code=None,
                linked_procedure_catalog_item_id=None,
                linked_procedure_catalog_item_ids=[],
                notes="筛选执行来源",
            ),
        ],
        candidate_drafts=[screening, validity],
    )


def _assert_hydrated_candidates_pass_gate(output) -> None:
    batch = _repartition_regression_batch()
    unit_by_id = {item.structure_unit_id: item for item in batch.owned_units}
    for candidate in output.candidates:
        _validate_candidate(
            candidate,
            unit_by_id=unit_by_id,
            allowed_span_ids=set(batch.owned_source_span_ids),
            workflow_targets=batch.known_workflow_stage_targets,
            procedure_targets=batch.known_procedure_targets,
            official_codes={item.official_code for item in batch.known_official_targets},
            procedure_ids={
                item.catalog_item_id for item in batch.known_procedure_targets
            },
            candidate_ids={candidate.control_candidate_id},
        )


def _mixed_decision_repair_error(output, *, allow_repartition: bool):
    candidate_by_id = {
        candidate.control_candidate_id: candidate for candidate in output.candidates
    }
    error = publication_repair_error(
        issues=[
            SimpleNamespace(
                code="MIXED_DECISION_STAGE_CONTROL",
                message="筛选期应完成的无锚点操作与基线/随机/首次给药前有效性判定必须拆成不同候选",
                entity_id=output.candidates[0].control_candidate_id,
            )
        ],
        candidate_by_id=candidate_by_id,
        control_to_candidate={},
        default_structure_unit_ids=list(output.candidates[0].frozen_structure_unit_ids),
    )
    if not allow_repartition:
        error.allow_candidate_repartition = False
    return error


def test_synthetic_runner_mixed_decision_repartition_preserves_both_candidates() -> None:
    batch = _repartition_regression_batch()
    initial_wire = _mixed_decision_initial_wire()
    repartitioned_wire = _mixed_decision_repartition_wire()
    transport = _FakeTransport(
        [
            ProtocolControlAgentResponse(
                session_id="session-mixed-repartition",
                text=initial_wire.model_dump_json(),
            ),
            ProtocolControlAgentResponse(
                session_id="session-mixed-repartition",
                text=repartitioned_wire.model_dump_json(),
            ),
        ]
    )
    validator_calls = 0

    def validate_after_hydration(output) -> None:
        nonlocal validator_calls
        validator_calls += 1
        if validator_calls == 1:
            raise _mixed_decision_repair_error(output, allow_repartition=True)
        _assert_hydrated_candidates_pass_gate(output)

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        batch,
        transport,
        output_validator=validate_after_hydration,
    )

    assert result.status == "已解析"
    assert result.final_output is not None
    source_keys = {
        tuple(candidate.frozen_structure_unit_ids)
        for candidate in result.final_output.candidates
    }
    assert source_keys == {("su-02",), ("su-01", "su-02")}
    assert result.attempts[-1].issues == [
        "已由系统原样保留定向修订范围外的上一轮内容"
    ]


def test_synthetic_runner_without_repartition_authorization_rejects_split_candidate() -> None:
    batch = _repartition_regression_batch()
    initial_wire = _mixed_decision_initial_wire()
    repartitioned_wire = _mixed_decision_repartition_wire()
    transport = _FakeTransport(
        [
            ProtocolControlAgentResponse(
                session_id="session-mixed-drop",
                text=initial_wire.model_dump_json(),
            ),
            ProtocolControlAgentResponse(
                session_id="session-mixed-drop",
                text=repartitioned_wire.model_dump_json(),
            ),
        ]
    )
    validator_calls = 0

    def validate_after_hydration(output) -> None:
        nonlocal validator_calls
        validator_calls += 1
        if validator_calls == 1:
            raise _mixed_decision_repair_error(output, allow_repartition=False)

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        batch,
        transport,
        output_validator=validate_after_hydration,
    )

    assert result.status == "需要核对"
    assert result.final_output is None
    assert result.attempts[-1].outcome == "schema_invalid"
    assert "REPAIR_SCOPE_ESCAPE" in result.attempts[-1].issues[0]
    assert validator_calls == 1


def test_repartition_rejects_out_of_scope_candidate_partition() -> None:
    previous = _mixed_decision_initial_wire()
    current = _mixed_decision_repartition_wire()
    out_of_scope = current.candidate_drafts[0].model_copy(
        update={
            "title": "越界新增候选",
            "source_structure_unit_ids": ["su-02", "su-out-of-scope"],
        }
    )
    tampered = current.model_copy(
        update={"candidate_drafts": [out_of_scope, *current.candidate_drafts[1:]]}
    )

    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="REPAIR_SCOPE_ESCAPE",
    ):
        _restore_bounded_wire_repair(
            previous,
            tampered,
            mutable_structure_unit_ids={"su-01", "su-02"},
            mutable_candidate_source_keys={("su-01", "su-02")},
            mutable_candidate_source_union={"su-01", "su-02"},
            allow_candidate_repartition=True,
        )


def test_same_source_candidate_repair_uses_bounded_wire_position() -> None:
    previous = _two_same_source_candidates_wire()
    changed_second = previous.candidate_drafts[1].model_copy(
        update={"title": "获准修订的第二个同源候选"}
    )
    current = previous.model_copy(
        update={
            "candidate_drafts": [changed_second, previous.candidate_drafts[0]]
        }
    )

    restored, applied = _restore_bounded_wire_repair(
        previous,
        current,
        mutable_structure_unit_ids={"su-02"},
        mutable_candidate_source_keys={("su-02",)},
        mutable_candidate_indexes={1},
    )

    assert applied is True
    assert restored.candidate_drafts[0] == previous.candidate_drafts[0]
    assert restored.candidate_drafts[1] == changed_second


def test_same_source_candidate_repair_rejects_modified_sibling() -> None:
    previous = _two_same_source_candidates_wire()
    current = previous.model_copy(
        update={
            "candidate_drafts": [
                previous.candidate_drafts[0].model_copy(
                    update={"title": "未获授权的同源候选改写"}
                ),
                previous.candidate_drafts[1].model_copy(
                    update={"title": "获准修订的同源候选"}
                ),
            ]
        }
    )

    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="REPAIR_SCOPE_ESCAPE",
    ):
        _restore_bounded_wire_repair(
            previous,
            current,
            mutable_structure_unit_ids={"su-02"},
            mutable_candidate_source_keys={("su-02",)},
            mutable_candidate_indexes={1},
        )


def test_same_source_candidate_repair_restores_changed_different_source_candidate() -> None:
    same_source = _two_same_source_candidates_wire()
    unrelated = same_source.candidate_drafts[0].model_copy(
        update={
            "title": "不同来源冻结候选",
            "source_structure_unit_ids": ["su-01"],
        }
    )
    previous = same_source.model_copy(
        update={"candidate_drafts": [*same_source.candidate_drafts, unrelated]}
    )
    revised = previous.candidate_drafts[1].model_copy(
        update={"title": "获准修订的同源候选"}
    )
    changed_unrelated = unrelated.model_copy(
        update={"title": "模型越界改写但由系统恢复"}
    )
    current = previous.model_copy(
        update={
            "candidate_drafts": [
                changed_unrelated,
                revised,
                previous.candidate_drafts[0],
            ]
        }
    )

    restored, applied = _restore_bounded_wire_repair(
        previous,
        current,
        mutable_structure_unit_ids={"su-02"},
        mutable_candidate_source_keys={("su-02",)},
        mutable_candidate_indexes={1},
    )

    assert applied is True
    assert restored.candidate_drafts == [
        previous.candidate_drafts[0],
        revised,
        unrelated,
    ]


def test_same_source_candidate_repair_rejects_different_source_partition_change() -> None:
    same_source = _two_same_source_candidates_wire()
    unrelated = same_source.candidate_drafts[0].model_copy(
        update={
            "title": "不同来源冻结候选",
            "source_structure_unit_ids": ["su-01"],
        }
    )
    previous = same_source.model_copy(
        update={"candidate_drafts": [*same_source.candidate_drafts, unrelated]}
    )
    current = previous.model_copy(
        update={
            "candidate_drafts": [
                previous.candidate_drafts[0],
                previous.candidate_drafts[1].model_copy(
                    update={"title": "获准修订的同源候选"}
                ),
                unrelated.model_copy(
                    update={"source_structure_unit_ids": ["su-new"]}
                ),
            ]
        }
    )

    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="REPAIR_SCOPE_ESCAPE",
    ):
        _restore_bounded_wire_repair(
            previous,
            current,
            mutable_structure_unit_ids={"su-02"},
            mutable_candidate_source_keys={("su-02",)},
            mutable_candidate_indexes={1},
        )


def test_same_source_candidate_repair_restores_multiple_frozen_different_source_siblings() -> None:
    same_source = _two_same_source_candidates_wire()
    unrelated_first = same_source.candidate_drafts[0].model_copy(
        update={
            "title": "不同来源冻结候选一",
            "source_structure_unit_ids": ["su-01"],
        }
    )
    unrelated_second = unrelated_first.model_copy(
        update={"title": "不同来源冻结候选二"}
    )
    previous = same_source.model_copy(
        update={
            "candidate_drafts": [
                *same_source.candidate_drafts,
                unrelated_first,
                unrelated_second,
            ]
        }
    )
    revised = previous.candidate_drafts[1].model_copy(
        update={"title": "获准修订的同源候选"}
    )
    current = previous.model_copy(
        update={
            "candidate_drafts": [
                unrelated_second.model_copy(update={"title": "越界改写二"}),
                revised,
                unrelated_first.model_copy(update={"title": "越界改写一"}),
                previous.candidate_drafts[0],
            ]
        }
    )

    restored, applied = _restore_bounded_wire_repair(
        previous,
        current,
        mutable_structure_unit_ids={"su-02"},
        mutable_candidate_source_keys={("su-02",)},
        mutable_candidate_indexes={1},
    )

    assert applied is True
    assert restored.candidate_drafts == [
        previous.candidate_drafts[0],
        revised,
        unrelated_first,
        unrelated_second,
    ]


def test_position_bounded_repair_rejects_candidate_count_change() -> None:
    previous = _mixed_decision_repartition_wire()
    current = previous.model_copy(
        update={"candidate_drafts": previous.candidate_drafts[:1]}
    )

    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="REPAIR_SCOPE_ESCAPE",
    ):
        _restore_bounded_wire_repair(
            previous,
            current,
            mutable_structure_unit_ids={"su-02"},
            mutable_candidate_source_keys={("su-02",)},
            mutable_candidate_indexes={0},
        )


def _two_same_source_candidates_wire():
    """Two su-02 candidates at distinct wire positions (different titles)."""

    previous = _mixed_decision_repartition_wire()
    same_source_second = previous.candidate_drafts[1].model_copy(
        update={"source_structure_unit_ids": ["su-02"]}
    )
    return previous.model_copy(
        update={
            "candidate_drafts": [previous.candidate_drafts[0], same_source_second]
        }
    )


def test_same_source_position_repair_preserves_wire_order_when_titles_sort_differently() -> None:
    """Title sort must not swap same-source siblings after position-keyed repair."""

    previous = _two_same_source_candidates_wire()
    frozen = previous.candidate_drafts[0].model_copy(update={"title": "Z-冻结候选"})
    mutable = previous.candidate_drafts[1].model_copy(update={"title": "A-待修订候选"})
    previous = previous.model_copy(update={"candidate_drafts": [frozen, mutable]})
    revised = mutable.model_copy(update={"title": "A-已修订候选"})
    current = previous.model_copy(
        update={"candidate_drafts": [revised, frozen]}
    )

    restored, applied = _restore_bounded_wire_repair(
        previous,
        current,
        mutable_structure_unit_ids={"su-02"},
        mutable_candidate_source_keys={("su-02",)},
        mutable_candidate_indexes={1},
    )

    assert applied is True
    assert [candidate.title for candidate in restored.candidate_drafts] == [
        "Z-冻结候选",
        "A-已修订候选",
    ]


def test_same_source_position_repair_rejects_duplicate_frozen_candidate() -> None:
    previous = _two_same_source_candidates_wire()
    duplicate_frozen = previous.model_copy(
        update={
            "candidate_drafts": [
                previous.candidate_drafts[0],
                previous.candidate_drafts[0],
            ]
        }
    )

    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="REPAIR_SCOPE_ESCAPE",
    ):
        _restore_bounded_wire_repair(
            previous,
            duplicate_frozen,
            mutable_structure_unit_ids={"su-02"},
            mutable_candidate_source_keys={("su-02",)},
            mutable_candidate_indexes={1},
        )


def test_same_source_position_repair_rejects_out_of_order_count_change() -> None:
    previous = _two_same_source_candidates_wire()
    revised = previous.candidate_drafts[1].model_copy(
        update={"title": "获准修订的同源候选"}
    )
    current = previous.model_copy(
        update={"candidate_drafts": [revised, previous.candidate_drafts[0], revised]}
    )

    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="REPAIR_SCOPE_ESCAPE",
    ):
        _restore_bounded_wire_repair(
            previous,
            current,
            mutable_structure_unit_ids={"su-02"},
            mutable_candidate_source_keys={("su-02",)},
            mutable_candidate_indexes={1},
        )


def test_runner_targets_one_of_two_same_source_candidates_by_wire_position() -> None:
    batch = _repartition_regression_batch()
    initial = _mixed_decision_repartition_wire()
    initial = initial.model_copy(
        update={
            "dispositions": [
                initial.dispositions[0].model_copy(
                    update={
                        "disposition": StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
                        "notes": "仅作上下文",
                    }
                ),
                initial.dispositions[1],
            ],
            "candidate_drafts": [
                initial.candidate_drafts[0],
                initial.candidate_drafts[0].model_copy(
                    update={"title": "第二个同源候选"}
                ),
            ]
        }
    )
    repaired = initial.model_copy(
        update={
            "candidate_drafts": [
                initial.candidate_drafts[1].model_copy(
                    update={"title": "获准修订的同源候选"}
                ),
                initial.candidate_drafts[0],
            ]
        }
    )
    transport = _FakeTransport(
        [
            ProtocolControlAgentResponse(
                session_id="session-same-source-position",
                text=initial.model_dump_json(),
            ),
            ProtocolControlAgentResponse(
                session_id="session-same-source-position",
                text=repaired.model_dump_json(),
            ),
        ]
    )
    validator_calls = 0

    def validate_after_hydration(output) -> None:
        nonlocal validator_calls
        validator_calls += 1
        if validator_calls == 1:
            target = next(
                candidate
                for candidate in output.candidates
                if candidate.title == initial.candidate_drafts[1].title
            )
            raise ProtocolControlAgentWireValidationError(
                "TARGETED_CANDIDATE_REPAIR",
                "只修订第二个同源候选",
                structure_unit_ids=target.frozen_structure_unit_ids,
                candidate_ids=[target.control_candidate_id],
            )

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        batch,
        transport,
        output_validator=validate_after_hydration,
    )

    assert result.status == "已解析"
    assert result.final_output is not None
    assert {candidate.title for candidate in result.final_output.candidates} == {
        initial.candidate_drafts[0].title,
        "获准修订的同源候选",
    }
