"""Generic Phase 5.8b contracts and deterministic batch-planning fixtures.

These tests deliberately use synthetic structure units only.  They do not call
an Agent and do not read a protocol or write a project artifact.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.contracts.enums import (
    CatalogItemKind,
    CatalogKind,
    PhaseScope,
    ReviewStage,
    StudyPhase,
)
from app.domain.contracts.protocol_controls import (
    ControlConditionAtomDraft,
    ControlConditionDnfDraft,
    ControlConditionGroupDraft,
    ControlCrossSourceRelationDraft,
    ControlRelationTargetKind,
    CrossSourceRelationKind,
    ControlMinimumEvidence,
    ControlMinimumEvidenceDraft,
    ControlObligationAtom,
    ControlObligationAtomDraft,
    ControlObligationDnfDraft,
    ControlObligationGroupDraft,
    ControlObligationKind,
    ProtocolControlBatchDisposition,
    ProtocolControlBatchDispositionHydrated,
    ProtocolControlUnitDispositionDraft,
    ProtocolControlCandidateSemanticDraft,
    ProtocolControlDispositionBatch,
    KnownWorkflowStageTarget,
    ProtocolReviewControl,
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    ReviewNodeBinding,
    ReviewNodeRole,
    StructureUnitDispositionKind,
    stable_protocol_control_atom_id,
    stable_protocol_control_batch_id,
    stable_protocol_control_candidate_id,
    hydrate_protocol_control_batch_disposition,
    hydrate_protocol_control_candidate_semantics,
)
from app.domain.contracts.protocol_ingestion import (
    FrozenCatalogItem,
    FrozenProtocolCatalog,
)
from app.domain.contracts.rules import WorkflowStage
from app.domain.publication import canonical_hash
from app.protocols.protocol_control_planning import (
    ProtocolControlPlanningError,
    detect_required_action_kinds,
    plan_protocol_control_batches,
)


_SHA = "b" * 64
_SNAPSHOT = "snapshot:generic-58b"
_PROTOCOL = "protocol:generic-58b"


def _unit(
    number: int,
    heading: str,
    *,
    priority: int = 0,
) -> ProtocolStructureUnit:
    return ProtocolStructureUnit(
        structure_unit_id=f"su-{number:02d}",
        source_ref=f"body.p{number}",
        member_source_refs=[f"body.p{number}"],
        source_span_ids=[f"span:{number:02d}"],
        unit_kind="paragraph",
        heading_path=[heading],
        source_order=number,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.SHARED],
        excerpt=f"第{number}项原文",
        priority_rank=priority,
        priority_keyword_hits=["关键词"] if priority else [],
    )


def _manifest(*units: ProtocolStructureUnit) -> ProtocolSectionCoverageManifest:
    return ProtocolSectionCoverageManifest(
        manifest_id="manifest:generic-58b",
        protocol_version_id=_PROTOCOL,
        protocol_document_sha256=_SHA,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id=_SNAPSHOT,
        units=list(units),
    )


def _catalog(
    kind: CatalogKind, items: list[FrozenCatalogItem]
) -> FrozenProtocolCatalog:
    base = dict(
        catalog_id=f"catalog:{kind.value}",
        snapshot_id=_SNAPSHOT,
        catalog_kind=kind,
        study_phase=StudyPhase.PHASE_II,
        items=tuple(items),
        frozen_at=datetime(2026, 8, 24, tzinfo=timezone.utc),
        frozen_by="generic-test",
    )
    shell = FrozenProtocolCatalog.model_construct(
        schema_version="fixture/v1",
        **base,
        catalog_sha256="",
    )
    return FrozenProtocolCatalog(
        **base,
        catalog_sha256=canonical_hash(
            shell.model_dump(mode="json", exclude={"catalog_sha256"})
        ),
    )


def _node() -> ReviewNodeBinding:
    return ReviewNodeBinding(
        workflow_stage_id="stage:screening",
        review_stage=ReviewStage.SCREENING,
        role=ReviewNodeRole.EARLY_ATTENTION,
    )


def _draft(
    *,
    title: str = "洗脱期控制",
    source_units: list[str] | None = None,
    source_spans: list[str] | None = None,
    cross_source_relations: list[ControlCrossSourceRelationDraft] | None = None,
) -> ProtocolControlCandidateSemanticDraft:
    return ProtocolControlCandidateSemanticDraft(
        title=title,
        applicable_population="拟入组受试者",
        applicability_expression=ControlConditionDnfDraft(
            groups=[
                ControlConditionGroupDraft(
                    atoms=[
                        ControlConditionAtomDraft(
                            statement="拟入组",
                            source_span_ids=["span:01"],
                            source_excerpts=["拟入组"],
                        )
                    ]
                ),
                ControlConditionGroupDraft(
                    atoms=[
                        ControlConditionAtomDraft(
                            statement="目标人群",
                            source_span_ids=["span:02"],
                            source_excerpts=["目标人群"],
                        )
                    ]
                ),
            ]
        ),
        trigger_expression=ControlConditionDnfDraft(
            groups=[
                ControlConditionGroupDraft(
                    atoms=[
                        ControlConditionAtomDraft(
                            statement="筛查时核对",
                            source_span_ids=["span:01"],
                            source_excerpts=["筛查时核对"],
                        )
                    ]
                )
            ]
        ),
        obligation_expression=ControlObligationDnfDraft(
            groups=[
                ControlObligationGroupDraft(
                    atoms=[
                        ControlObligationAtomDraft(
                            kind=ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE,
                            statement="不得暴露于禁用药物",
                            source_span_ids=["span:01"],
                            source_excerpts=["不得暴露于禁用药物"],
                        ),
                        ControlObligationAtomDraft(
                            kind=ControlObligationKind.MUST_RECORD,
                            statement="必须记录末次用药日期",
                            source_span_ids=["span:02"],
                            source_excerpts=["必须记录末次用药日期"],
                        ),
                    ]
                )
            ]
        ),
        exception_expression=ControlConditionDnfDraft(
            groups=[
                ControlConditionGroupDraft(
                    atoms=[
                        ControlConditionAtomDraft(
                            statement="洗脱例外",
                            source_span_ids=["span:03"],
                            source_excerpts=["洗脱例外"],
                        )
                    ],
                    waives_trigger_branch_indexes=[0],
                )
            ]
        ),
        review_node_bindings=[_node()],
        minimum_evidence=[
            ControlMinimumEvidenceDraft(
                fact_type="medication_exposure",
                description="核对用药记录",
                due_stage=ReviewStage.SCREENING,
            )
        ],
        source_structure_unit_ids=source_units or ["su-01", "su-02"],
        source_span_ids=source_spans or ["span:01", "span:02", "span:03"],
        cross_source_relations=cross_source_relations or [],
    )


def test_dnf_layers_are_explicit_and_obligation_kinds_are_not_collapsed() -> None:
    draft = _draft()
    assert len(draft.applicability_expression.groups) == 2
    assert len(draft.applicability_expression.groups[0].atoms) == 1
    assert len(draft.obligation_expression.groups[0].atoms) == 2
    assert {atom.kind for atom in draft.obligation_expression.groups[0].atoms} == {
        ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE,
        ControlObligationKind.MUST_RECORD,
    }
    assert draft.exception_expression is not None
    assert draft.exception_expression.groups[0].atoms[0].source_excerpts == ["洗脱例外"]


def test_dnf_rejects_empty_group_and_unpaired_exact_source_excerpt() -> None:
    with pytest.raises(ValidationError):
        ControlConditionDnfDraft(groups=[ControlConditionGroupDraft(atoms=[])])
    with pytest.raises(ValidationError, match="一一对应"):
        ControlConditionAtomDraft(
            statement="条件",
            source_span_ids=["span:1"],
            source_excerpts=["片段一", "片段二"],
        )


def test_one_atom_preserves_multiple_non_contiguous_excerpts_from_one_span() -> None:
    atom = ControlConditionAtomDraft(
        statement="同一来源片段中的两个非连续位置",
        source_span_ids=["span:shared", "span:shared"],
        source_excerpts=["前段摘录", "后段摘录"],
    )
    assert atom.source_span_ids == ["span:shared", "span:shared"]
    assert atom.source_excerpts == ["前段摘录", "后段摘录"]


def test_planner_assigns_every_unit_once_and_keeps_context_read_only() -> None:
    units = [
        _unit(1, "章节 A", priority=1),
        _unit(2, "章节 A"),
        _unit(3, "章节 A"),
        _unit(4, "章节 B"),
        _unit(5, "章节 B"),
    ]
    plan = plan_protocol_control_batches(
        _manifest(*units),
        max_owned_units_per_batch=2,
        context_radius=1,
    )

    owned = [
        unit_id for batch in plan.batches for unit_id in batch.owned_structure_unit_ids
    ]
    assert owned == ["su-01", "su-02", "su-03", "su-04", "su-05"]
    assert len(owned) == len(set(owned)) == len(units)
    # su-03 may appear as read-only context for the first B batch, but it is
    # still owned only by the A chunk.
    assert "su-03" in plan.batches[0].context_structure_unit_ids
    assert "su-03" not in plan.batches[0].owned_structure_unit_ids
    assert len(plan.batches[0].owned_units) <= 2
    assert any(unit.priority_rank == 0 for unit in plan.batches[0].owned_units)


def test_planner_is_deterministic_and_keyword_priority_never_filters_membership() -> (
    None
):
    units = [_unit(1, "章节 A", priority=0), _unit(2, "章节 A", priority=9)]
    manifest = _manifest(*units)
    canonical = plan_protocol_control_batches(
        manifest,
        max_owned_units_per_batch=1,
        prioritize_keyword_rank=False,
    )
    prioritized = plan_protocol_control_batches(
        manifest,
        max_owned_units_per_batch=1,
        prioritize_keyword_rank=True,
    )
    assert canonical.model_dump(mode="json") == prioritized.model_dump(mode="json")
    assert {
        unit_id
        for batch in prioritized.batches
        for unit_id in batch.owned_structure_unit_ids
    } == {"su-01", "su-02"}
    assert [batch.batch_id for batch in prioritized.batches] == [
        batch.batch_id for batch in canonical.batches
    ]
    assert prioritized.batches[0].owned_structure_unit_ids == ["su-01"]
    assert [batch.priority_rank for batch in prioritized.batches] == [0, 9]


def test_planner_exposes_only_frozen_official_and_procedure_targets() -> None:
    official = _catalog(
        CatalogKind.OFFICIAL_PARENT_RULES,
        [
            FrozenCatalogItem(
                item_id="official-item-1",
                kind=CatalogItemKind.PARENT_RULE,
                official_code="EX-01",
                label="既有排除标准",
                position=0,
                source_span_ids=("span:01",),
            )
        ],
    )
    procedure = _catalog(
        CatalogKind.REQUIRED_PROCEDURES,
        [
            FrozenCatalogItem(
                item_id="procedure-item-1",
                kind=CatalogItemKind.REQUIRED_PROCEDURE,
                label="筛选期检查",
                visit_instance="screening-1",
                review_stage=ReviewStage.SCREENING,
                position=0,
                source_span_ids=("span:02",),
            )
        ],
    )
    plan = plan_protocol_control_batches(
        _manifest(_unit(1, "章节 A")),
        official,
        procedure,
    )
    batch = plan.batches[0]
    assert [item.official_code for item in batch.known_official_targets] == ["EX-01"]
    assert [item.catalog_item_id for item in batch.known_procedure_targets] == [
        "procedure-item-1"
    ]
    assert batch.known_procedure_targets[0].review_stage == ReviewStage.SCREENING
    assert batch.known_target_source_span_ids == ["span:01", "span:02"]


def test_planner_freezes_explicit_specimen_and_procedure_actions_for_the_gate() -> None:
    action_unit = _unit(1, "实验室检查").model_copy(
        update={"excerpt": ("采集用于实验室检查的样品，并应根据标准实验室程序进行。")}
    )
    descriptive_unit = _unit(2, "实验室检查").model_copy(
        update={"excerpt": "研究记录提及既往按照标准程序完成检查。"}
    )

    batch = plan_protocol_control_batches(
        _manifest(action_unit, descriptive_unit)
    ).batches[0]

    assert batch.owned_required_action_kinds_by_structure_unit_id == {
        "su-01": ["collect_biospecimen", "follow_specified_procedure"]
    }


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "研究者在筛选前向参与者解释所有的研究程序等信息，"
            "获得参与者自愿签署的ICF。",
            ["explain_information", "obtain_signature"],
        ),
        (
            "在筛选期获取参与者的人口学资料。",
            ["collect_data"],
        ),
        (
            "12导联心电图检查前参与者至少静息10 min。"
            "记录12导联心电图诊断结果、心率、PR间期、RR间期、QRS、QT间期，"
            "并应用Fridericia’s公式计算心率校正计算QTcF。",
            [
                "calculate_qtcf",
                "perform_ecg",
                "prepare_participant",
                "record_ecg_measurements",
            ],
        ),
        (
            "要求参与者站在校准过的身高测量板上，双脚并拢。",
            ["position_participant", "use_calibrated_device"],
        ),
        (
            "轻轻将仪器的测量臂移动至参与者头顶上。"
            "记录参与者的身高，单位为厘米（cm），保留整数。",
            ["operate_measurement_device", "record_with_precision"],
        ),
        (
            "生命体征检查包括坐位血压、坐位脉搏、体温和呼吸频率。"
            "测量前，建议参与者至少休息5分钟。",
            ["prepare_participant", "verify_vital_sign_components"],
        ),
        (
            "如果检查与样本采集时间一致，尽量在样本采集之前完成检查。",
            ["sequence_before_related_procedure"],
        ),
        (
            "研究者应告知参与者筛选期间的用药限制。",
            ["communicate_with_participant"],
        ),
    ],
)
def test_planner_freezes_cross_protocol_explicit_actions(
    text: str,
    expected: list[str],
) -> None:
    assert list(detect_required_action_kinds(text)) == expected


def test_device_name_alone_does_not_claim_height_measurement_performed() -> None:
    assert "perform_height_measurement" not in detect_required_action_kinds(
        "要求参与者站在校准过的身高测量板上。"
    )


def test_sequence_context_without_positive_action_does_not_create_action() -> None:
    assert "sequence_before_related_procedure" not in detect_required_action_kinds(
        "两项操作的先后顺序未作要求。"
    )


def test_related_sampling_reference_does_not_create_collection_obligation() -> None:
    assert "collect_biospecimen" not in detect_required_action_kinds(
        "如果检查与样本采集时间一致，尽量在样本采集之前完成检查。"
    )


def test_generic_vital_sign_label_does_not_claim_component_list() -> None:
    assert "verify_vital_sign_components" not in detect_required_action_kinds(
        "本次访视需完成生命体征检查。"
    )


def test_planner_copies_deterministic_workflow_stage_catalog_and_keeps_visits() -> None:
    workflow_stages = [
        WorkflowStage(
            workflow_stage_id="stage:screening:one",
            stage=ReviewStage.SCREENING,
            display_name="筛选期审核一",
            visit_instance="screening-1",
            visit_window="D-28~D-1",
        ),
        WorkflowStage(
            workflow_stage_id="stage:screening:two",
            stage=ReviewStage.SCREENING,
            display_name="筛选期审核二",
            visit_instance="screening-2",
            visit_window="D-14~D-1",
        ),
    ]
    procedure = _catalog(
        CatalogKind.REQUIRED_PROCEDURES,
        [
            FrozenCatalogItem(
                item_id="procedure-item-1",
                kind=CatalogItemKind.REQUIRED_PROCEDURE,
                label="筛选期检查一",
                visit_instance="screening-1",
                review_stage=ReviewStage.SCREENING,
                position=0,
                source_span_ids=("span:01",),
            ),
            FrozenCatalogItem(
                item_id="procedure-item-2",
                kind=CatalogItemKind.REQUIRED_PROCEDURE,
                label="筛选期检查二",
                visit_instance="screening-2",
                review_stage=ReviewStage.SCREENING,
                position=1,
                source_span_ids=("span:02",),
            ),
        ],
    )
    first = plan_protocol_control_batches(
        _manifest(_unit(1, "章节 A")),
        required_procedure_catalog=procedure,
        workflow_stages=workflow_stages,
    )
    second = plan_protocol_control_batches(
        _manifest(_unit(1, "章节 A")),
        required_procedure_catalog=procedure,
        workflow_stages=workflow_stages,
    )
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    targets = first.batches[0].known_workflow_stage_targets
    assert [target.workflow_stage_id for target in targets] == [
        "stage:screening:one",
        "stage:screening:two",
    ]
    assert [target.visit_instance for target in targets] == [
        "screening-1",
        "screening-2",
    ]


def test_duplicate_workflow_stage_ids_fail() -> None:
    stage = WorkflowStage(
        workflow_stage_id="stage:screening",
        stage=ReviewStage.SCREENING,
        display_name="筛选期审核",
        visit_instance="screening-1",
    )
    with pytest.raises(ProtocolControlPlanningError, match="workflow_stage_id"):
        plan_protocol_control_batches(
            _manifest(_unit(1, "章节 A")),
            workflow_stages=[
                stage,
                stage.model_copy(update={"display_name": "重复节点"}),
            ],
        )

    batch = plan_protocol_control_batches(
        _manifest(_unit(1, "章节 A")),
        workflow_stages=[stage],
    ).batches[0]
    payload = batch.model_dump(mode="python")
    payload["known_workflow_stage_targets"] = [
        KnownWorkflowStageTarget(
            workflow_stage_id="stage:screening",
            review_stage=ReviewStage.SCREENING,
            display_name="筛选期审核",
            visit_instance="screening-1",
        ),
        KnownWorkflowStageTarget(
            workflow_stage_id="stage:screening",
            review_stage=ReviewStage.SCREENING,
            display_name="筛选期审核重复",
            visit_instance="screening-2",
        ),
    ]
    with pytest.raises(ValidationError, match="workflow_stage_id"):
        ProtocolControlDispositionBatch(**payload)


def test_procedure_target_requires_known_workflow_stage_when_catalog_supplied() -> None:
    procedure = _catalog(
        CatalogKind.REQUIRED_PROCEDURES,
        [
            FrozenCatalogItem(
                item_id="procedure-item-1",
                kind=CatalogItemKind.REQUIRED_PROCEDURE,
                label="基线检查",
                visit_instance="baseline-1",
                review_stage=ReviewStage.BASELINE,
                position=0,
                source_span_ids=("span:01",),
            )
        ],
    )
    with pytest.raises(ProtocolControlPlanningError, match="无法与本批次"):
        plan_protocol_control_batches(
            _manifest(_unit(1, "章节 A")),
            required_procedure_catalog=procedure,
            workflow_stages=[
                WorkflowStage(
                    workflow_stage_id="stage:screening",
                    stage=ReviewStage.SCREENING,
                    display_name="筛选期审核",
                    visit_instance="screening-1",
                )
            ],
        )


def test_batch_result_rejects_foreign_candidate_source_and_duplicate_disposition() -> (
    None
):
    batch = plan_protocol_control_batches(
        _manifest(_unit(1, "章节 A"), _unit(2, "章节 A")),
        max_owned_units_per_batch=2,
        context_radius=0,
    ).batches[0]
    dispositions = [
        ProtocolControlUnitDispositionDraft(
            structure_unit_id="su-01",
            disposition=StructureUnitDispositionKind.PENDING_CONFIRMATION,
        ),
        ProtocolControlUnitDispositionDraft(
            structure_unit_id="su-02",
            disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
        ),
    ]
    result = ProtocolControlBatchDisposition(
        batch_id=batch.batch_id,
        coverage_manifest_id=batch.coverage_manifest_id,
        owned_structure_unit_ids=batch.owned_structure_unit_ids,
        owned_source_span_ids=batch.owned_source_span_ids,
        dispositions=dispositions,
        candidate_drafts=[],
    )
    assert result.batch_id == batch.batch_id
    with pytest.raises(ValidationError, match="批次外"):
        ProtocolControlBatchDisposition(
            batch_id=batch.batch_id,
            coverage_manifest_id=batch.coverage_manifest_id,
            owned_structure_unit_ids=batch.owned_structure_unit_ids,
            owned_source_span_ids=batch.owned_source_span_ids,
            dispositions=dispositions,
            candidate_drafts=[
                _draft(
                    source_units=["su-99"],
                    source_spans=["span:01", "span:02", "span:03"],
                )
            ],
        )


def test_batch_result_allows_zero_or_many_candidates_without_changing_unit_ownership() -> (
    None
):
    batch = plan_protocol_control_batches(
        _manifest(_unit(1, "章节 A"), _unit(2, "章节 A"), _unit(3, "章节 A")),
        max_owned_units_per_batch=3,
        context_radius=0,
    ).batches[0]
    dispositions = [
        ProtocolControlUnitDispositionDraft(
            structure_unit_id=unit_id,
            disposition=(
                StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
                if index <= 2
                else StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT
            ),
            candidate_draft_indexes=[0, 1] if index <= 2 else [],
        )
        for index, unit_id in enumerate(batch.owned_structure_unit_ids, start=1)
    ]
    empty = ProtocolControlBatchDisposition(
        batch_id=batch.batch_id,
        coverage_manifest_id=batch.coverage_manifest_id,
        owned_structure_unit_ids=batch.owned_structure_unit_ids,
        owned_source_span_ids=batch.owned_source_span_ids,
        dispositions=[
            ProtocolControlUnitDispositionDraft(
                structure_unit_id=item.structure_unit_id,
                disposition=StructureUnitDispositionKind.PENDING_CONFIRMATION,
            )
            for item in dispositions
        ],
        candidate_drafts=[],
    )
    many = ProtocolControlBatchDisposition(
        batch_id=batch.batch_id,
        coverage_manifest_id=batch.coverage_manifest_id,
        owned_structure_unit_ids=batch.owned_structure_unit_ids,
        owned_source_span_ids=batch.owned_source_span_ids,
        dispositions=dispositions,
        candidate_drafts=[
            _draft(source_units=["su-01", "su-02"]),
            _draft(title="另一个控制", source_units=["su-01", "su-02"]),
        ],
    )
    assert empty.candidate_drafts == []
    assert len(many.candidate_drafts) == 2


def test_batch_result_rejects_orphan_and_contradictory_candidate_drafts() -> None:
    batch = plan_protocol_control_batches(
        _manifest(_unit(1, "章节 A"), _unit(2, "章节 A"), _unit(3, "章节 A")),
        max_owned_units_per_batch=3,
        context_radius=0,
    ).batches[0]
    pending = [
        ProtocolControlUnitDispositionDraft(
            structure_unit_id=unit_id,
            disposition=StructureUnitDispositionKind.PENDING_CONFIRMATION,
        )
        for unit_id in batch.owned_structure_unit_ids
    ]
    with pytest.raises(ValidationError, match="孤儿候选"):
        ProtocolControlBatchDisposition(
            batch_id=batch.batch_id,
            coverage_manifest_id=batch.coverage_manifest_id,
            owned_structure_unit_ids=batch.owned_structure_unit_ids,
            owned_source_span_ids=batch.owned_source_span_ids,
            dispositions=pending,
            candidate_drafts=[_draft(source_units=["su-01", "su-02"])],
        )

    with pytest.raises(ValidationError, match="双向精确闭包"):
        ProtocolControlBatchDisposition(
            batch_id=batch.batch_id,
            coverage_manifest_id=batch.coverage_manifest_id,
            owned_structure_unit_ids=batch.owned_structure_unit_ids,
            owned_source_span_ids=batch.owned_source_span_ids,
            dispositions=[
                ProtocolControlUnitDispositionDraft(
                    structure_unit_id="su-01",
                    disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                    candidate_draft_indexes=[0],
                ),
                ProtocolControlUnitDispositionDraft(
                    structure_unit_id="su-02",
                    disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
                ),
                ProtocolControlUnitDispositionDraft(
                    structure_unit_id="su-03",
                    disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
                ),
            ],
            candidate_drafts=[_draft(source_units=["su-01", "su-02"])],
        )

    with pytest.raises(ValidationError, match="双向精确闭包"):
        ProtocolControlBatchDisposition(
            batch_id=batch.batch_id,
            coverage_manifest_id=batch.coverage_manifest_id,
            owned_structure_unit_ids=batch.owned_structure_unit_ids,
            owned_source_span_ids=batch.owned_source_span_ids,
            dispositions=[
                ProtocolControlUnitDispositionDraft(
                    structure_unit_id=unit_id,
                    disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                    candidate_draft_indexes=[0],
                )
                for unit_id in batch.owned_structure_unit_ids
            ],
            candidate_drafts=[_draft(source_units=["su-01", "su-02"])],
        )


def test_stable_candidate_batch_and_atom_ids_are_system_derived() -> None:
    batch_id = stable_protocol_control_batch_id("manifest", 1, ["su-01"])
    candidate_id = stable_protocol_control_candidate_id(
        "manifest", batch_id, ["su-01"], "semantic-hash"
    )
    second_candidate_id = stable_protocol_control_candidate_id(
        "manifest", batch_id, ["su-01"], "semantic-hash", 1
    )
    atom_id = stable_protocol_control_atom_id(candidate_id, "obligation", 0, 1)
    assert batch_id == stable_protocol_control_batch_id("manifest", 1, ["su-01"])
    assert candidate_id.startswith("pcc-")
    assert second_candidate_id != candidate_id
    assert atom_id.startswith("pca-")
    assert all(code not in candidate_id for code in ("IN-", "EX-", "REQ-", "CTRL-"))


def test_batch_hydration_assigns_plural_ids_for_one_unit_with_multiple_candidates() -> (
    None
):
    batch = plan_protocol_control_batches(
        _manifest(
            _unit(1, "章节 A"),
            _unit(2, "章节 A"),
            _unit(3, "章节 A"),
        ),
        max_owned_units_per_batch=3,
        context_radius=0,
    ).batches[0]
    result = ProtocolControlBatchDisposition(
        batch_id=batch.batch_id,
        coverage_manifest_id=batch.coverage_manifest_id,
        owned_structure_unit_ids=batch.owned_structure_unit_ids,
        owned_source_span_ids=batch.owned_source_span_ids,
        dispositions=[
            ProtocolControlUnitDispositionDraft(
                structure_unit_id="su-01",
                disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                candidate_draft_indexes=[0, 1],
            ),
            ProtocolControlUnitDispositionDraft(
                structure_unit_id="su-02",
                disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                candidate_draft_indexes=[0],
            ),
            ProtocolControlUnitDispositionDraft(
                structure_unit_id="su-03",
                disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
            ),
        ],
        candidate_drafts=[
            _draft(source_units=["su-01", "su-02"]),
            _draft(title="第二个控制", source_units=["su-01"]),
        ],
    )
    hydrated = hydrate_protocol_control_batch_disposition(batch, result)
    assert len(hydrated.candidates) == 2
    by_unit = {item.structure_unit_id: item for item in hydrated.dispositions}
    assert len(by_unit["su-01"].linked_control_candidate_ids) == 2
    assert len(by_unit["su-02"].linked_control_candidate_ids) == 1
    assert by_unit["su-03"].linked_control_candidate_ids == []
    assert all(
        candidate.control_candidate_id.startswith("pcc-")
        for candidate in hydrated.candidates
    )
    assert all(candidate.semantics is not None for candidate in hydrated.candidates)

    broken = hydrated.model_dump(mode="json")
    broken["dispositions"][2]["disposition"] = "other_control_candidate"
    broken["dispositions"][2]["linked_control_candidate_ids"] = [
        hydrated.candidates[0].control_candidate_id
    ]
    with pytest.raises(ValidationError, match="双向精确闭包"):
        ProtocolControlBatchDispositionHydrated(**broken)


def test_system_hydration_injects_atom_ids_and_preserves_all_four_layers() -> None:
    candidate_id = stable_protocol_control_candidate_id(
        "manifest", "batch", ["su-01", "su-02"], "semantic-hash"
    )
    hydrated = hydrate_protocol_control_candidate_semantics(
        _draft(), control_candidate_id=candidate_id
    )
    assert hydrated.applicability_expression is not None
    assert hydrated.trigger_expression is not None
    assert hydrated.exception_expression is not None
    assert all(
        atom.condition_atom_id
        for group in hydrated.applicability_expression.groups
        for atom in group.atoms
    )
    assert all(
        atom.obligation_id
        for group in hydrated.obligation_expression.groups
        for atom in group.atoms
    )
    assert all(
        "__wire__" not in atom.obligation_id
        for group in hydrated.obligation_expression.groups
        for atom in group.atoms
    )
    assert all(
        group.trigger_branch_id and group.trigger_branch_id.startswith("pct-")
        for group in hydrated.trigger_expression.groups
    )
    assert hydrated.exception_expression.groups[0].waives_trigger_branch_ids == [
        hydrated.trigger_expression.groups[0].trigger_branch_id
    ]


def test_published_control_can_use_hydrated_dnf_layers_without_flattening() -> None:
    candidate_id = stable_protocol_control_candidate_id(
        "manifest", "batch", ["su-01", "su-02"], "semantic-hash"
    )
    hydrated = hydrate_protocol_control_candidate_semantics(
        _draft(), control_candidate_id=candidate_id
    )
    control = ProtocolReviewControl(
        protocol_control_id="pcc-published-01",
        display_ordinal=1,
        protocol_version_id=_PROTOCOL,
        study_phase=StudyPhase.PHASE_II,
        title=hydrated.title,
        applicable_population=hydrated.applicable_population,
        obligations=[],
        applicability_expression=hydrated.applicability_expression,
        trigger_expression=hydrated.trigger_expression,
        obligation_expression=hydrated.obligation_expression,
        exception_expression=hydrated.exception_expression,
        review_node_bindings=hydrated.review_node_bindings,
        minimum_evidence=hydrated.minimum_evidence,
        source_span_ids=hydrated.source_span_ids,
        source_structure_unit_ids=hydrated.source_structure_unit_ids,
    )
    assert len(control.obligation_expression.groups[0].atoms) == 2
    assert control.exception_expression is not None
    assert control.has_explicit_obligation_dnf is True
    assert control.is_legacy_flat_compatibility is False


def test_flat_obligation_compatibility_is_visible_to_future_publication_gate() -> None:
    flat = ProtocolReviewControl(
        protocol_control_id="pcc-legacy-flat",
        display_ordinal=1,
        protocol_version_id=_PROTOCOL,
        study_phase=StudyPhase.PHASE_II,
        title="旧兼容控制",
        applicable_population="拟入组受试者",
        obligations=[
            ControlObligationAtom(
                obligation_id="legacy-ob-1",
                kind=ControlObligationKind.MUST_RECORD,
                statement="必须记录",
            )
        ],
        review_node_bindings=[_node()],
        minimum_evidence=[
            ControlMinimumEvidence(
                evidence_key="legacy-evidence",
                fact_type="record",
                description="记录",
                due_stage=ReviewStage.SCREENING,
            )
        ],
        source_span_ids=["span:01"],
        source_structure_unit_ids=["su-01"],
    )
    assert flat.is_legacy_flat_compatibility is True
    assert flat.has_explicit_obligation_dnf is False


def test_provider_relations_are_limited_to_known_batch_targets() -> None:
    relation = ControlCrossSourceRelationDraft(
        kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
        external_target_kind=ControlRelationTargetKind.OFFICIAL_RULE,
        external_target_id="EX-01",
        candidate_side="left",
        notes="仅引用本批次冻结目标",
    )
    procedure_relation = ControlCrossSourceRelationDraft(
        kind=CrossSourceRelationKind.FURTHER_EXPLANATION,
        external_target_kind=ControlRelationTargetKind.REQUIRED_PROCEDURE,
        external_target_id="procedure-item-1",
        candidate_side="right",
        notes="反向端点保留候选方向",
    )
    official = _catalog(
        CatalogKind.OFFICIAL_PARENT_RULES,
        [
            FrozenCatalogItem(
                item_id="official-item-1",
                kind=CatalogItemKind.PARENT_RULE,
                official_code="EX-01",
                label="既有排除标准",
                position=0,
                source_span_ids=("span:01",),
            )
        ],
    )
    procedure = _catalog(
        CatalogKind.REQUIRED_PROCEDURES,
        [
            FrozenCatalogItem(
                item_id="procedure-item-1",
                kind=CatalogItemKind.REQUIRED_PROCEDURE,
                label="筛选期检查",
                visit_instance="screening-1",
                review_stage=ReviewStage.SCREENING,
                position=0,
                source_span_ids=("span:02",),
            )
        ],
    )
    batch = plan_protocol_control_batches(
        _manifest(_unit(1, "章节 A"), _unit(2, "章节 A"), _unit(3, "章节 A")),
        official,
        procedure,
        max_owned_units_per_batch=3,
        context_radius=0,
    ).batches[0]
    result = ProtocolControlBatchDisposition(
        batch_id=batch.batch_id,
        coverage_manifest_id=batch.coverage_manifest_id,
        owned_structure_unit_ids=batch.owned_structure_unit_ids,
        owned_source_span_ids=batch.owned_source_span_ids,
        dispositions=[
            ProtocolControlUnitDispositionDraft(
                structure_unit_id="su-01",
                disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                candidate_draft_indexes=[0],
            ),
            ProtocolControlUnitDispositionDraft(
                structure_unit_id="su-02",
                disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                candidate_draft_indexes=[0],
            ),
            ProtocolControlUnitDispositionDraft(
                structure_unit_id="su-03",
                disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
            ),
        ],
        candidate_drafts=[
            _draft(
                source_units=["su-01", "su-02"],
                cross_source_relations=[relation, procedure_relation],
            )
        ],
    )
    hydrated = hydrate_protocol_control_batch_disposition(batch, result)
    candidate = hydrated.candidates[0]
    assert candidate.semantics is not None
    relations = candidate.semantics.cross_source_relations
    assert len(relations) == 2
    assert relations[0].left_target_kind == ControlRelationTargetKind.CONTROL_CANDIDATE
    assert relations[0].left_target_id == candidate.control_candidate_id
    assert relations[0].right_target_kind == ControlRelationTargetKind.OFFICIAL_RULE
    assert relations[0].right_target_id == "EX-01"
    assert relations[1].left_target_kind == ControlRelationTargetKind.REQUIRED_PROCEDURE
    assert relations[1].left_target_id == "procedure-item-1"
    assert relations[1].right_target_kind == ControlRelationTargetKind.CONTROL_CANDIDATE
    assert relations[1].right_target_id == candidate.control_candidate_id

    unknown_relation = relation.model_copy(update={"external_target_id": "EX-99"})
    unknown_result = result.model_copy(
        update={
            "candidate_drafts": [
                _draft(
                    source_units=["su-01", "su-02"],
                    cross_source_relations=[unknown_relation],
                )
            ]
        }
    )
    with pytest.raises(ValueError, match="未知的官方规则身份"):
        hydrate_protocol_control_batch_disposition(batch, unknown_result)

    with pytest.raises(
        ValidationError,
        match="只能引用已知官方规则、流程必做项或冻结流程节点",
    ):
        ControlCrossSourceRelationDraft(
            kind=CrossSourceRelationKind.FURTHER_EXPLANATION,
            external_target_kind=ControlRelationTargetKind.CONTROL_CANDIDATE,
            external_target_id="pcc-existing",
            candidate_side="left",
        )


def test_planner_rejects_catalog_from_another_phase() -> None:
    official = _catalog(
        CatalogKind.OFFICIAL_PARENT_RULES,
        [
            FrozenCatalogItem(
                item_id="official-item-1",
                kind=CatalogItemKind.PARENT_RULE,
                official_code="IN-01",
                label="既有入选标准",
                position=0,
                source_span_ids=("span:01",),
            )
        ],
    ).model_copy(update={"study_phase": StudyPhase.PHASE_III})
    with pytest.raises(ProtocolControlPlanningError, match="期别不一致"):
        plan_protocol_control_batches(_manifest(_unit(1, "章节 A")), official)
