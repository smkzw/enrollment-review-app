"""Metamorphic acceptance checks for the project-neutral control chain.

The two real protocol documents are read-only corpus inputs only.  Semantic
cases below use synthetic text whose identifiers, clinical labels, instruments,
operators, anchors, and values are deliberately changed between variants.
No model is called and no accepted artifact is written.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.agents.protocol_control_deconstructor import (
    CONTROL_AGENT_WIRE_VERSION,
    ProtocolControlAgentInput,
    ProtocolControlAgentWire,
    ProtocolControlAgentWireCandidate,
    ProtocolControlAgentWireConditionAtom,
    ProtocolControlAgentWireConditionDnf,
    ProtocolControlAgentWireConditionGroup,
    ProtocolControlAgentWireDisposition,
    ProtocolControlAgentWireEvidence,
    ProtocolControlAgentWireNode,
    ProtocolControlAgentWireObligationAtom,
    ProtocolControlAgentWireObligationDnf,
    ProtocolControlAgentWireObligationGroup,
    build_protocol_control_agent_prompt,
    hydrate_protocol_control_agent_output,
)
from app.domain.contracts.enums import (
    AnchorType,
    PhaseScope,
    ReviewStage,
    StudyPhase,
    TimeDirection,
)
from app.domain.contracts.protocol_controls import (
    ControlMinimumEvidence,
    ControlObligationAtom,
    ControlObligationDnf,
    ControlObligationGroup,
    ControlObligationKind,
    ControlObligationModality,
    KnownOfficialRuleTarget,
    ProtocolControlDiscoveryDecision,
    ProtocolControlDiscoveryDisposition,
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
)
from app.domain.contracts.rules import TimeConstraint, TimeQuantity, TimeUnit, WorkflowStage
from app.protocols.protocol_control_gate import (
    ProtocolControlGateError,
    _check_obligation_logic,
    _check_obligation_modality_and_event_anchor,
    _check_obligation_modality_fidelity,
    _check_professional_judgment_fidelity,
)
from app.protocols.protocol_control_planning import (
    plan_protocol_control_batches,
    plan_protocol_control_discovery,
)


ROOT = Path(__file__).resolve().parents[3]
READ_ONLY_PROTOCOLS = (
    ROOT
    / "artifacts/phase5-acceptance/20260823/isolated-inputs/d001/protocol/"
    / "test-D001项目/CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx",
    ROOT
    / "artifacts/phase5-acceptance/20260823/isolated-inputs/sar/protocol/"
    / "4. Protocol/MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx",
)
SHARED_PROTOCOL_MODULES = (
    ROOT / "app/agents/protocol_control_deconstructor.py",
    ROOT / "app/domain/contracts/protocol_controls.py",
    ROOT / "app/protocols/protocol_control_planning.py",
    ROOT / "app/protocols/protocol_control_gate.py",
)


def _file_snapshot(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns


def _unit(
    unit_id: str,
    span_id: str,
    order: int,
    excerpt: str,
    *,
    heading: str = "generic controls",
) -> ProtocolStructureUnit:
    return ProtocolStructureUnit(
        structure_unit_id=unit_id,
        source_ref=f"body.p{order}",
        member_source_refs=[f"body.p{order}"],
        source_span_ids=[span_id],
        unit_kind="paragraph",
        heading_path=[heading],
        source_order=order,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.SHARED],
        excerpt=excerpt,
    )


def _manifest(
    *,
    protocol_version_id: str = "protocol:opaque-alpha",
    manifest_id: str = "manifest:opaque-alpha",
    excerpts: tuple[str, ...] = (
        "必须记录对象α的状态。",
        "补充语境，不形成独立控制。",
    ),
) -> ProtocolSectionCoverageManifest:
    units = [
        _unit(f"unit-{index:02d}", f"span-{index:02d}", index, excerpt)
        for index, excerpt in enumerate(excerpts, start=1)
    ]
    return ProtocolSectionCoverageManifest(
        manifest_id=manifest_id,
        protocol_version_id=protocol_version_id,
        protocol_document_sha256="b" * 64,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id=f"{manifest_id}:snapshot",
        units=units,
        dispositions=[],
        claims_full_coverage=False,
    )


def _workflow() -> list[WorkflowStage]:
    return [
        WorkflowStage(
            workflow_stage_id="stage:opaque:screening",
            stage=ReviewStage.SCREENING,
            display_name="opaque screening",
            visit_instance="visit-opaque-1",
        )
    ]


def _batch(
    manifest: ProtocolSectionCoverageManifest,
    *,
    max_owned_units_per_batch: int = 1,
):
    plan = plan_protocol_control_batches(
        manifest,
        max_owned_units_per_batch=max_owned_units_per_batch,
        context_radius=1,
        workflow_stages=_workflow(),
    )
    return plan, plan.batches[0]


def _wire_condition(
    statement: str,
    source_span_id: str,
    source_excerpt: str,
) -> ProtocolControlAgentWireConditionAtom:
    return ProtocolControlAgentWireConditionAtom(
        statement=statement,
        source_span_ids=[source_span_id],
        source_excerpts=[source_excerpt],
        time_constraint=None,
        requires_professional_judgment=False,
    )


def _wire_obligation(
    statement: str,
    source_span_id: str,
    source_excerpt: str,
    *,
    kind: ControlObligationKind = ControlObligationKind.MUST_RECORD,
    modality: ControlObligationModality = ControlObligationModality.MANDATORY,
    time_constraint: TimeConstraint | None = None,
    requires_professional_judgment: bool = False,
) -> ProtocolControlAgentWireObligationAtom:
    return ProtocolControlAgentWireObligationAtom(
        kind=kind,
        statement=statement,
        time_constraint=time_constraint,
        prospective_period=None,
        modality=modality,
        temporal_scope=None,
        source_span_ids=[source_span_id],
        source_excerpts=[source_excerpt],
        requires_professional_judgment=requires_professional_judgment,
    )


def _wire_for_batch(
    batch,
    *,
    title: str,
    population: str,
    source_excerpt: str,
    obligation: ProtocolControlAgentWireObligationAtom | None = None,
    applicability_expression: ProtocolControlAgentWireConditionDnf | None = None,
    trigger_expression: ProtocolControlAgentWireConditionDnf | None = None,
) -> ProtocolControlAgentWire:
    unit = batch.owned_units[0]
    span_id = unit.source_span_ids[0]
    return ProtocolControlAgentWire(
        wire_version=CONTROL_AGENT_WIRE_VERSION,
        dispositions=[
            ProtocolControlAgentWireDisposition(
                structure_unit_id=unit.structure_unit_id,
                disposition="other_control_candidate",
                linked_official_code=None,
                linked_procedure_catalog_item_id=None,
                linked_procedure_catalog_item_ids=[],
                notes=None,
            )
        ],
        candidate_drafts=[
            ProtocolControlAgentWireCandidate(
                title=title,
                applicable_population=population,
                applicability_expression=applicability_expression,
                trigger_expression=trigger_expression,
                obligation_expression=ProtocolControlAgentWireObligationDnf(
                    groups=[
                        ProtocolControlAgentWireObligationGroup(
                            atoms=[
                                obligation
                                or _wire_obligation(
                                    source_excerpt,
                                    span_id,
                                    source_excerpt,
                                )
                            ]
                        )
                    ]
                ),
                exception_expression=None,
                review_node_bindings=[
                    ProtocolControlAgentWireNode(
                        workflow_stage_id="stage:opaque:screening",
                        review_stage=ReviewStage.SCREENING,
                        role="decide_at_node",
                        guidance=None,
                    )
                ],
                minimum_evidence=[
                    ProtocolControlAgentWireEvidence(
                        fact_type="opaque-fact",
                        description="核对来源记录",
                        due_stage=ReviewStage.SCREENING,
                        required_source_types=["原始记录"],
                    )
                ],
                source_structure_unit_ids=[unit.structure_unit_id],
                source_span_ids=[span_id],
                cross_source_relations=[],
            )
        ],
    )


def _domain_obligation(
    statement: str,
    source_excerpt: str,
    *,
    source_span_id: str = "span:generic",
    modality: ControlObligationModality = ControlObligationModality.MANDATORY,
    kind: ControlObligationKind = ControlObligationKind.MUST_RECORD,
    requires_professional_judgment: bool = False,
) -> ControlObligationAtom:
    return ControlObligationAtom(
        obligation_id="obl-" + hashlib.sha256(statement.encode()).hexdigest()[:12],
        kind=kind,
        statement=statement,
        modality=modality,
        source_span_ids=[source_span_id],
        source_excerpts=[source_excerpt],
        requires_professional_judgment=requires_professional_judgment,
    )


def _domain_expression(*atoms: ControlObligationAtom) -> ControlObligationDnf:
    return ControlObligationDnf(
        groups=[ControlObligationGroup(atoms=list(atoms))]
    )


def _evidence(*source_types: str) -> list[ControlMinimumEvidence]:
    return [
        ControlMinimumEvidence(
            evidence_key="evidence:opaque",
            fact_type="opaque-fact",
            description="核对来源记录",
            due_stage=ReviewStage.SCREENING,
            required_source_types=list(source_types),
        )
    ]


@pytest.mark.parametrize("path", READ_ONLY_PROTOCOLS)
def test_heterogeneous_acceptance_corpora_are_read_only_inputs(path: Path) -> None:
    """D001 and SAR are retained as immutable corpus inputs, never outputs."""
    if not path.is_file():
        pytest.skip(f"read-only protocol fixture is absent: {path}")
    before = _file_snapshot(path)
    assert path.suffix.lower() == ".docx"
    assert path.stat().st_size > 0
    assert _file_snapshot(path) == before


def test_shared_protocol_chain_has_no_corpus_specific_branching() -> None:
    forbidden = (
        "CMS-D001",
        "MG-K10-SAR",
        "银屑病",
        "PASI",
        "PGA",
        "BSA",
        "DLQI",
        "IN-04",
        "EX-21",
    )
    for path in SHARED_PROTOCOL_MODULES:
        source = path.read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden), path


def test_legacy_reviewer_boundary_is_explicit_and_one_way() -> None:
    from app.pipeline import reviewer

    assert reviewer.LEGACY_REVIEWER_BOUNDARY == "legacy_only"
    assert reviewer.LEGACY_REVIEWER_V2_IMPORTS_ALLOWED is False


def test_protocol_identity_and_domain_labels_are_opaque_to_planning_and_hydration() -> None:
    cases = (
        {
            "protocol": "protocol:amber-17",
            "manifest": "manifest:amber-17",
            "title": "compound-alpha review",
            "population": "condition-lattice participant",
            "source": "必须记录compound-alpha的condition-lattice状态。",
        },
        {
            "protocol": "protocol:teal-93",
            "manifest": "manifest:teal-93",
            "title": "compound-beta review",
            "population": "condition-orbit participant",
            "source": "必须记录compound-beta的condition-orbit状态。",
        },
    )
    projections = []
    for case in cases:
        manifest = _manifest(
            protocol_version_id=case["protocol"],
            manifest_id=case["manifest"],
            excerpts=(case["source"], "未命名的补充背景。"),
        )
        plan, batch = _batch(manifest)
        agent_input = ProtocolControlAgentInput.from_batch(batch)
        prompt = build_protocol_control_agent_prompt(agent_input)
        assert case["protocol"] in prompt
        assert "D001" not in prompt
        assert "MG-K10-SAR" not in prompt
        wire = _wire_for_batch(
            batch,
            title=case["title"],
            population=case["population"],
            source_excerpt=case["source"],
        )
        hydrated = hydrate_protocol_control_agent_output(wire, batch)
        semantic = hydrated.candidates[0].semantics
        assert semantic is not None
        projections.append(
            (
                plan.expected_structure_unit_ids,
                batch.owned_structure_unit_ids,
                tuple(unit.unit_kind for unit in agent_input.owned_units),
                semantic.title,
                semantic.applicable_population,
                semantic.obligation_expression.groups[0].atoms[0].statement,
            )
        )

    assert projections[0][:3] == projections[1][:3]
    assert projections[0][3:] != projections[1][3:]


@pytest.mark.parametrize("rule_code", ("IN-01", "EX-99"))
def test_rule_numbers_are_opaque_frozen_targets(rule_code: str) -> None:
    manifest = _manifest(excerpts=("规则关联语境。", "无关背景。"))
    _, original_batch = _batch(manifest)
    batch = original_batch.model_copy(
        update={
            "known_official_targets": [
                KnownOfficialRuleTarget(
                    catalog_item_id="official:opaque",
                    official_code=rule_code,
                    label="opaque frozen rule",
                    position=0,
                    source_span_ids=["span:rule"],
                    source_excerpts=["冻结规则原文"],
                )
            ]
        }
    )
    unit_id = batch.owned_units[0].structure_unit_id
    wire = ProtocolControlAgentWire(
        wire_version=CONTROL_AGENT_WIRE_VERSION,
        dispositions=[
            ProtocolControlAgentWireDisposition(
                structure_unit_id=unit_id,
                disposition="official_eligibility",
                linked_official_code=rule_code,
                linked_procedure_catalog_item_id=None,
                linked_procedure_catalog_item_ids=[],
                notes=None,
            )
        ],
        candidate_drafts=[],
    )

    agent_input = ProtocolControlAgentInput.from_batch(batch)
    hydrated = hydrate_protocol_control_agent_output(wire, batch)
    assert agent_input.known_official_targets[0].official_code == rule_code
    assert hydrated.dispositions[0].linked_official_code == rule_code


@pytest.mark.parametrize(
    "source",
    (
        "必须记录object-alpha的state。",
        "必须记录 object-beta 的 state！",
        "必须记录object-gamma的state（更新版）。",
    ),
)
def test_textual_perturbations_keep_wire_scope_closed(source: str) -> None:
    manifest = _manifest(excerpts=(source, "无关背景。"))
    _, batch = _batch(manifest)
    wire = _wire_for_batch(
        batch,
        title="perturbed opaque control",
        population="opaque population",
        source_excerpt=source,
    )

    hydrated = hydrate_protocol_control_agent_output(wire, batch)
    candidate = hydrated.candidates[0]
    assert candidate.frozen_structure_unit_ids == [batch.owned_units[0].structure_unit_id]
    assert candidate.source_span_ids == [batch.owned_units[0].source_span_ids[0]]
    assert candidate.semantics is not None
    assert (
        candidate.semantics.obligation_expression.groups[0].atoms[0].source_excerpts
        == [source]
    )


def test_full_manifest_discovery_shape_does_not_depend_on_priority_terms() -> None:
    first = _manifest(
        protocol_version_id="protocol:one",
        manifest_id="manifest:one",
        excerpts=("结构单元甲。", "结构单元乙。", "结构单元丙。"),
    )
    second = _manifest(
        protocol_version_id="protocol:two",
        manifest_id="manifest:two",
        excerpts=("完全不同的主题。", "另一种主题。", "第三种主题。"),
    )
    first_plan = plan_protocol_control_discovery(
        first,
        max_units_per_batch=1,
        context_radius=1,
    )
    second_plan = plan_protocol_control_discovery(
        second,
        max_units_per_batch=1,
        context_radius=1,
    )

    assert first_plan.expected_structure_unit_ids == ["unit-01", "unit-02", "unit-03"]
    assert second_plan.expected_structure_unit_ids == first_plan.expected_structure_unit_ids
    assert [
        batch.target_structure_unit_ids for batch in first_plan.batches
    ] == [batch.target_structure_unit_ids for batch in second_plan.batches]
    assert [
        batch.context_structure_unit_ids for batch in first_plan.batches
    ] == [batch.context_structure_unit_ids for batch in second_plan.batches]
    assert first_plan.manifest_structure_unit_count == 3
    assert second_plan.manifest_structure_unit_count == 3
    assert (
        first_plan.manifest_structure_unit_ids_sha256
        == second_plan.manifest_structure_unit_ids_sha256
    )
    assert all(
        "expected_structure_unit_ids"
        not in batch.model_dump(mode="json")
        for plan in (first_plan, second_plan)
        for batch in plan.batches
    )


def test_dnf_and_or_mutation_preserves_explicit_structure_for_renamed_terms() -> None:
    cases = (
        ("condition-alpha", "condition-beta", "condition-gamma"),
        ("state-north", "state-south", "state-west"),
    )
    for first, second, alternative in cases:
        source = f"{first}且{second}，或{alternative}时必须记录结果。"
        manifest = _manifest(excerpts=(source, "无关背景。"))
        _, batch = _batch(manifest)
        span_id = batch.owned_units[0].source_span_ids[0]
        trigger = ProtocolControlAgentWireConditionDnf(
            groups=[
                ProtocolControlAgentWireConditionGroup(
                    atoms=[
                        _wire_condition(first, span_id, source),
                        _wire_condition(second, span_id, source),
                    ]
                ),
                ProtocolControlAgentWireConditionGroup(
                    atoms=[_wire_condition(alternative, span_id, source)]
                ),
            ]
        )
        wire = _wire_for_batch(
            batch,
            title=f"{first} control",
            population="opaque population",
            source_excerpt=source,
            trigger_expression=trigger,
        )
        hydrated = hydrate_protocol_control_agent_output(wire, batch)
        groups = hydrated.candidates[0].semantics.trigger_expression.groups
        assert [[atom.statement for atom in group.atoms] for group in groups] == [
            [first, second],
            [alternative],
        ]


def test_and_or_mutation_is_rejected_without_domain_specific_terms() -> None:
    first_source = "state-alpha"
    second_source = "state-beta"
    source = f"{first_source}且{second_source}"
    first = _domain_obligation(first_source, source, source_span_id="span:and")
    second = _domain_obligation(second_source, source, source_span_id="span:and")
    preserved = _domain_expression(first, second)
    _check_obligation_logic(
        SimpleNamespace(obligation_combination="all"),
        entity_id="control:opaque",
        obligation_expression=preserved,
    )

    weakened = ControlObligationDnf(
        groups=[
            ControlObligationGroup(atoms=[first]),
            ControlObligationGroup(atoms=[second]),
        ]
    )
    with pytest.raises(ProtocolControlGateError, match="OBLIGATION_AND_WEAKENED"):
        _check_obligation_logic(
            SimpleNamespace(obligation_combination="any"),
            entity_id="control:opaque",
            obligation_expression=weakened,
        )


def test_time_anchor_and_threshold_mutations_round_trip_without_fixed_values() -> None:
    variants = (
        (AnchorType.SCREENING_DATE, 1, TimeUnit.DAY, "筛选日期"),
        (AnchorType.BASELINE_DATE, 17, TimeUnit.WEEK, "基线日期"),
        (AnchorType.EVENT_DATE, 4096, TimeUnit.MONTH, "事件日期"),
    )
    for anchor, value, unit, anchor_label in variants:
        source = f"在{anchor_label}前{value}{unit.value}完成记录。"
        manifest = _manifest(excerpts=(source, "无关背景。"))
        _, batch = _batch(manifest)
        constraint = TimeConstraint(
            anchor_type=anchor,
            direction=TimeDirection.BEFORE,
            upper_bound=TimeQuantity(value=value, unit=unit),
        )
        wire = _wire_for_batch(
            batch,
            title=f"{anchor_label} control",
            population="opaque population",
            source_excerpt=source,
            obligation=_wire_obligation(
                source,
                batch.owned_units[0].source_span_ids[0],
                source,
                kind=ControlObligationKind.COMPLETE_BEFORE_ANCHOR,
                time_constraint=constraint,
            ),
        )
        hydrated = hydrate_protocol_control_agent_output(wire, batch)
        actual = hydrated.candidates[0].semantics.obligation_expression.groups[0].atoms[0]
        assert actual.time_constraint == constraint
        assert actual.time_constraint.anchor_type == anchor
        assert actual.time_constraint.upper_bound.value == value


def test_professional_judgment_follows_role_not_instrument_or_condition_name() -> None:
    for instrument in ("instrument-alpha", "instrument-beta"):
        self_report_source = f"参与者自评{instrument}问卷"
        self_report = _domain_obligation(
            self_report_source,
            self_report_source,
            source_span_id=f"span:{instrument}:self",
        )
        _check_professional_judgment_fidelity(
            entity_id=f"candidate:{instrument}:self",
            obligation_expression=_domain_expression(self_report),
            evidence=_evidence("参与者填写记录"),
        )

        professional_source = f"研究者根据专业判断评估{instrument}"
        professional = _domain_obligation(
            professional_source,
            professional_source,
            source_span_id=f"span:{instrument}:professional",
            kind=ControlObligationKind.MUST_PROFESSIONAL_ASSESSMENT,
            requires_professional_judgment=True,
        )
        _check_professional_judgment_fidelity(
            entity_id=f"candidate:{instrument}:professional",
            obligation_expression=_domain_expression(professional),
            evidence=_evidence("研究者判断记录"),
        )

        wrongly_marked = self_report.model_copy(
            update={"requires_professional_judgment": True}
        )
        with pytest.raises(
            ProtocolControlGateError,
            match="SELF_REPORTED_TOOL_MARKED_PROFESSIONAL",
        ):
            _check_professional_judgment_fidelity(
                entity_id=f"candidate:{instrument}:wrong",
                obligation_expression=_domain_expression(wrongly_marked),
                evidence=_evidence("参与者填写记录"),
            )


def test_recommendation_and_optional_modality_mutations_are_value_agnostic() -> None:
    recommendation_variants = (
        ("建议记录compound-alpha的结果。", ControlObligationModality.RECOMMENDED),
        ("推荐记录compound-beta的结果。", ControlObligationModality.RECOMMENDED),
        ("尽可能记录compound-gamma的结果。", ControlObligationModality.BEST_EFFORT),
    )
    for source, modality in recommendation_variants:
        atom = _domain_obligation(
            source,
            source,
            source_span_id=f"span:{abs(hash(source))}",
            modality=modality,
        )
        expression = _domain_expression(atom)
        _check_obligation_modality_fidelity(
            entity_id="candidate:opaque",
            obligation_expression=expression,
        )
        hardened = atom.model_copy(
            update={"modality": ControlObligationModality.MANDATORY}
        )
        expected_code = (
            "RECOMMENDED_MODALITY_DROPPED"
            if modality == ControlObligationModality.RECOMMENDED
            else "BEST_EFFORT_MODALITY_DROPPED"
        )
        with pytest.raises(ProtocolControlGateError, match=expected_code):
            _check_obligation_modality_fidelity(
                entity_id="candidate:opaque:hardened",
                obligation_expression=_domain_expression(hardened),
            )

    optional_source = "可记录compound-delta的结果。"
    optional_atom = _domain_obligation(
        optional_source,
        optional_source,
        source_span_id="span:optional",
    )
    _check_obligation_modality_and_event_anchor(
        entity_id="candidate:optional",
        obligation_expression=_domain_expression(optional_atom),
    )
    hardened_optional = optional_atom.model_copy(
        update={"statement": "记录compound-delta的结果。"}
    )
    with pytest.raises(ProtocolControlGateError, match="OPTIONAL_ACTION_MODALITY_DROPPED"):
        _check_obligation_modality_and_event_anchor(
            entity_id="candidate:optional:hardened",
            obligation_expression=_domain_expression(hardened_optional),
        )


def test_wire_contract_rejects_duplicate_alternative_groups_after_renaming() -> None:
    atom_a = _wire_condition("opaque-a", "span:dup", "opaque-a opaque-b")
    atom_b = _wire_condition("opaque-b", "span:dup", "opaque-a opaque-b")
    group = ProtocolControlAgentWireConditionGroup(atoms=[atom_a, atom_b])
    with pytest.raises(ValidationError, match="重复替代组"):
        ProtocolControlAgentWireConditionDnf(groups=[group, group.model_copy(deep=True)])
