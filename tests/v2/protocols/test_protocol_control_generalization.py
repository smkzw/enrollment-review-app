"""Synthetic regression coverage for the two-stage control route."""

from __future__ import annotations

import json

import pytest

from app.agents.protocol_control_deconstructor import (
    CONTROL_DISCOVERY_WIRE_VERSION,
    ProtocolControlAgentInput,
    ProtocolControlDiscoveryAgentInput,
    ProtocolControlDiscoveryWireValidationError,
    bind_protocol_control_discovery_wire,
    build_protocol_control_agent_prompt,
    build_protocol_control_discovery_prompt,
    parse_protocol_control_discovery_agent_wire,
    wire_to_protocol_control_discovery_decisions,
)
from app.domain.contracts.enums import PhaseScope, StudyPhase
from app.domain.contracts.protocol_controls import (
    ProtocolControlDiscoveryDecision,
    ProtocolControlDiscoveryDisposition,
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
)
from app.protocols.protocol_control_planning import (
    DEFAULT_PROTOCOL_CONTROL_DISCOVERY_BATCH_UNITS,
    plan_protocol_control_deep_batches_from_discovery,
    plan_protocol_control_discovery,
    validate_protocol_control_deep_selection,
    validate_protocol_control_discovery_results,
)


_PROTOCOL = "protocol:general"
_MANIFEST = "manifest:general"


def _unit(number: int, heading: str = "通用章节") -> ProtocolStructureUnit:
    return ProtocolStructureUnit(
        structure_unit_id=f"unit-{number:03d}",
        source_ref=f"body.p{number}",
        member_source_refs=[f"body.p{number}"],
        source_span_ids=[f"span:{number:03d}"],
        unit_kind="paragraph",
        heading_path=[heading],
        source_order=number,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.SHARED],
        excerpt=f"第{number}项通用原文",
    )


def _manifest(count: int = 100) -> ProtocolSectionCoverageManifest:
    return ProtocolSectionCoverageManifest(
        manifest_id=_MANIFEST,
        protocol_version_id=_PROTOCOL,
        protocol_document_sha256="a" * 64,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:general",
        units=[_unit(number) for number in range(count)],
    )


def _discovery_decisions(
    plan,
    *,
    context_target: str = "unit-001",
) -> list[list[ProtocolControlDiscoveryDecision]]:
    batches: list[list[ProtocolControlDiscoveryDecision]] = []
    for batch in plan.batches:
        decisions: list[ProtocolControlDiscoveryDecision] = []
        for unit_id in batch.target_structure_unit_ids:
            if unit_id == "unit-000":
                decisions.append(
                    ProtocolControlDiscoveryDecision(
                        structure_unit_id=unit_id,
                        disposition=ProtocolControlDiscoveryDisposition.CANDIDATE,
                        required_context_structure_unit_ids=[context_target],
                        rationale="可能形成给药前控制并需要相邻语境。",
                    )
                )
            elif unit_id == "unit-001":
                decisions.append(
                    ProtocolControlDiscoveryDecision(
                        structure_unit_id=unit_id,
                        disposition=ProtocolControlDiscoveryDisposition.CONTEXT_ONLY,
                        rationale="仅补充相邻候选的语境。",
                    )
                )
            elif unit_id == "unit-002":
                decisions.append(
                    ProtocolControlDiscoveryDecision(
                        structure_unit_id=unit_id,
                        disposition=ProtocolControlDiscoveryDisposition.UNCERTAIN,
                        rationale="当前可见原文不足以排除控制作用。",
                    )
                )
            else:
                decisions.append(
                    ProtocolControlDiscoveryDecision(
                        structure_unit_id=unit_id,
                        disposition=ProtocolControlDiscoveryDisposition.NON_CONTROL,
                        rationale="可明确证明为与入排节点无关的背景。",
                    )
                )
        batches.append(decisions)
    return batches


def test_discovery_chunks_100_units_exactly_once_and_preserves_bounded_input() -> None:
    plan = plan_protocol_control_discovery(
        _manifest(),
        max_units_per_batch=10,
        context_radius=1,
    )
    target_ids = [
        unit_id
        for batch in plan.batches
        for unit_id in batch.target_structure_unit_ids
    ]

    assert len(plan.batches) == 10
    assert target_ids == [f"unit-{number:03d}" for number in range(100)]
    assert len(target_ids) == len(set(target_ids)) == 100
    assert plan.manifest_structure_unit_count == 100
    assert len(plan.manifest_structure_unit_ids_sha256) == 64
    assert all(len(batch.target_units) <= 10 for batch in plan.batches)

    first_input = ProtocolControlDiscoveryAgentInput.from_batch(plan.batches[0])
    assert len(first_input.target_units) == 10
    assert "expected_structure_unit_ids" not in first_input.model_dump(mode="json")
    discovery_prompt = build_protocol_control_discovery_prompt(first_input)
    assert "unit-099" not in discovery_prompt
    assert "高召回" in discovery_prompt


def test_discovery_packs_adjacent_headings_without_losing_local_context() -> None:
    manifest = ProtocolSectionCoverageManifest(
        manifest_id=_MANIFEST,
        protocol_version_id=_PROTOCOL,
        protocol_document_sha256="a" * 64,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:general",
        units=[
            _unit(0, "章节甲"),
            _unit(1, "章节甲"),
            _unit(2, "章节乙"),
            _unit(3, "章节乙"),
            _unit(4, "章节丙"),
        ],
    )

    first = plan_protocol_control_discovery(
        manifest,
        max_units_per_batch=3,
        context_radius=1,
    )
    second = plan_protocol_control_discovery(
        manifest,
        max_units_per_batch=3,
        context_radius=1,
    )

    assert [batch.target_structure_unit_ids for batch in first.batches] == [
        ["unit-000", "unit-001", "unit-002"],
        ["unit-003", "unit-004"],
    ]
    assert first.batches[0].context_structure_unit_ids == ["unit-003"]
    assert first.batches[1].context_structure_unit_ids == ["unit-002"]
    assert all(
        set(batch.target_structure_unit_ids).isdisjoint(
            batch.context_structure_unit_ids
        )
        for batch in first.batches
    )
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_discovery_default_is_large_enough_for_full_protocol_screening() -> None:
    plan = plan_protocol_control_discovery(_manifest())

    assert DEFAULT_PROTOCOL_CONTROL_DISCOVERY_BATCH_UNITS == 48
    assert len(plan.batches) == 3
    assert [len(batch.target_units) for batch in plan.batches] == [48, 48, 4]


def test_discovery_gate_closes_results_and_routes_only_candidate_uncertain_deep() -> None:
    manifest = _manifest()
    discovery_plan = plan_protocol_control_discovery(
        manifest,
        max_units_per_batch=10,
        context_radius=1,
    )
    raw_decisions = _discovery_decisions(discovery_plan)
    decisions = validate_protocol_control_discovery_results(
        discovery_plan,
        raw_decisions,
    )
    deep_plan = plan_protocol_control_deep_batches_from_discovery(
        manifest,
        discovery_plan,
        raw_decisions,
        max_owned_units_per_batch=8,
    )

    assert [decision.structure_unit_id for decision in decisions] == [
        f"unit-{number:03d}" for number in range(100)
    ]
    assert deep_plan.deep_structure_unit_ids == ("unit-000", "unit-002")
    assert deep_plan.non_deep_structure_unit_ids[0:2] == (
        "unit-001",
        "unit-003",
    )
    assert "unit-099" in deep_plan.non_deep_structure_unit_ids
    assert [
        unit_id
        for batch in deep_plan.batches
        for unit_id in batch.owned_structure_unit_ids
    ] == ["unit-000", "unit-002"]
    assert [
        unit_id
        for batch in deep_plan.batches
        for unit_id in batch.context_structure_unit_ids
    ] == ["unit-001"]
    assert all(
        unit_id not in deep_plan.deep_structure_unit_ids
        for unit_id in ("unit-001", "unit-099")
    )

    deep_input = ProtocolControlAgentInput.from_batch(deep_plan.batches[0])
    deep_prompt = build_protocol_control_agent_prompt(deep_input)
    assert "manifest_structure_unit_ids" not in deep_input.model_dump(mode="json")
    assert "unit-099" not in deep_prompt
    assert "unit-001" in deep_prompt
    assert len(deep_prompt) < 30_000


def test_context_can_be_deep_owned_elsewhere_but_non_control_cannot_be_required() -> None:
    plan = plan_protocol_control_discovery(_manifest(), max_units_per_batch=10)
    decisions = _discovery_decisions(plan)

    cross_candidate = _discovery_decisions(plan, context_target="unit-002")
    cross_candidate_plan = plan_protocol_control_deep_batches_from_discovery(
        _manifest(),
        plan,
        cross_candidate,
        max_owned_units_per_batch=1,
    )
    assert [
        batch.owned_structure_unit_ids for batch in cross_candidate_plan.batches
    ] == [["unit-000"], ["unit-002"]]
    assert cross_candidate_plan.batches[0].context_structure_unit_ids == [
        "unit-002"
    ]

    cross_batch_context = _discovery_decisions(plan, context_target="unit-003")
    normalized = validate_protocol_control_discovery_results(
        plan, cross_batch_context
    )
    assert normalized[3].disposition == (
        ProtocolControlDiscoveryDisposition.CONTEXT_ONLY
    )
    normalized_plan = plan_protocol_control_deep_batches_from_discovery(
        _manifest(),
        plan,
        cross_batch_context,
        max_owned_units_per_batch=1,
    )
    assert normalized_plan.batches[0].context_structure_unit_ids == ["unit-003"]

    valid = validate_protocol_control_discovery_results(plan, decisions)
    with pytest.raises(ValueError, match="uncertain"):
        validate_protocol_control_deep_selection(valid, ["unit-000", "unit-001"])

    assert valid[1].disposition == ProtocolControlDiscoveryDisposition.CONTEXT_ONLY
    assert valid[-1].disposition == ProtocolControlDiscoveryDisposition.NON_CONTROL


@pytest.mark.parametrize(
    "disposition",
    [
        ProtocolControlDiscoveryDisposition.CONTEXT_ONLY,
        ProtocolControlDiscoveryDisposition.NON_CONTROL,
    ],
)
def test_non_owned_discovery_dispositions_cannot_reverse_context_edges(
    disposition,
) -> None:
    with pytest.raises(ValueError, match="反向声明"):
        ProtocolControlDiscoveryDecision(
            structure_unit_id="unit-001",
            disposition=disposition,
            required_context_structure_unit_ids=["unit-002"],
            rationale="该单元本身不进入深析。",
        )


def test_discovery_gate_rejects_missing_duplicate_and_out_of_scope_results() -> None:
    plan = plan_protocol_control_discovery(_manifest(), max_units_per_batch=10)
    valid = _discovery_decisions(plan)

    missing = [list(items) for items in valid]
    missing[-1] = missing[-1][:-1]
    with pytest.raises(ValueError, match="闭合"):
        validate_protocol_control_discovery_results(plan, missing)

    duplicate = [list(items) for items in valid]
    duplicate[0].append(duplicate[0][0])
    with pytest.raises(ValueError, match="重复"):
        validate_protocol_control_discovery_results(plan, duplicate)

    out_of_scope = [list(items) for items in valid]
    out_of_scope[0][0] = ProtocolControlDiscoveryDecision(
        structure_unit_id="unit-000",
        disposition=ProtocolControlDiscoveryDisposition.CANDIDATE,
        required_context_structure_unit_ids=["unit-999"],
        rationale="越界反例。",
    )
    with pytest.raises(ValueError, match="越出"):
        validate_protocol_control_discovery_results(plan, out_of_scope)


def test_uncertain_cannot_be_dropped_from_deep_selection() -> None:
    plan = plan_protocol_control_discovery(_manifest(), max_units_per_batch=10)
    decisions = validate_protocol_control_discovery_results(
        plan,
        _discovery_decisions(plan),
    )

    with pytest.raises(ValueError, match="uncertain"):
        validate_protocol_control_deep_selection(decisions, ["unit-000"])


def test_discovery_provider_cannot_create_stable_identity() -> None:
    with pytest.raises(ProtocolControlDiscoveryWireValidationError, match="身份"):
        parse_protocol_control_discovery_agent_wire(
            json.dumps(
                {
                    "discovery_batch_id": "provider-created",
                    "decisions": [],
                }
            )
        )


def test_discovery_wire_is_versioned_and_provider_neutral() -> None:
    wire = parse_protocol_control_discovery_agent_wire(
        json.dumps(
            {
                "wire_version": CONTROL_DISCOVERY_WIRE_VERSION,
                "decisions": [
                    {
                        "structure_unit_id": "unit-000",
                        "disposition": "candidate",
                        "required_context_structure_unit_ids": ["unit-001"],
                        "rationale": "需要相邻语境后进入深析。",
                    }
                ],
            }
        )
    )
    decisions = wire_to_protocol_control_discovery_decisions(wire)
    assert decisions[0].structure_unit_id == "unit-000"
    assert decisions[0].disposition == ProtocolControlDiscoveryDisposition.CANDIDATE
    assert decisions[0].required_context_structure_unit_ids == ["unit-001"]
    assert decisions[0].rationale == "需要相邻语境后进入深析。"


def test_discovery_wire_canonicalizes_set_like_context_order() -> None:
    wire = parse_protocol_control_discovery_agent_wire(
        json.dumps(
            {
                "wire_version": CONTROL_DISCOVERY_WIRE_VERSION,
                "decisions": [
                    {
                        "structure_unit_id": "unit-000",
                        "disposition": "candidate",
                        "required_context_structure_unit_ids": [
                            "unit-009",
                            "unit-001",
                        ],
                        "rationale": "两个上下文身份的顺序不承载语义。",
                    }
                ],
            }
        )
    )

    assert wire.decisions[0].required_context_structure_unit_ids == [
        "unit-001",
        "unit-009",
    ]


def test_discovery_batch_binding_rejects_required_context_marked_non_control() -> None:
    batch = plan_protocol_control_discovery(
        _manifest(2),
        max_units_per_batch=2,
    ).batches[0]
    wire = parse_protocol_control_discovery_agent_wire(
        json.dumps(
            {
                "wire_version": CONTROL_DISCOVERY_WIRE_VERSION,
                "decisions": [
                    {
                        "structure_unit_id": "unit-000",
                        "disposition": "candidate",
                        "required_context_structure_unit_ids": ["unit-001"],
                        "rationale": "需要第二个单元解释语境。",
                    },
                    {
                        "structure_unit_id": "unit-001",
                        "disposition": "non_control",
                        "required_context_structure_unit_ids": [],
                        "rationale": "反例中错误处置为非控制内容。",
                    },
                ],
            }
        )
    )

    with pytest.raises(
        ProtocolControlDiscoveryWireValidationError,
        match="CONTEXT_DISPOSITION_CONFLICT",
    ):
        bind_protocol_control_discovery_wire(wire, batch)


def test_deep_prompt_size_does_not_follow_full_manifest_size() -> None:
    def deep_prompt_length(count: int) -> int:
        manifest = _manifest(count)
        discovery_plan = plan_protocol_control_discovery(
            manifest,
            max_units_per_batch=10,
        )
        deep_plan = plan_protocol_control_deep_batches_from_discovery(
            manifest,
            discovery_plan,
            _discovery_decisions(discovery_plan),
            max_owned_units_per_batch=8,
        )
        return len(build_protocol_control_agent_prompt(deep_plan.batches[0]))

    prompt_100 = deep_prompt_length(100)
    prompt_1000 = deep_prompt_length(1000)
    assert prompt_1000 - prompt_100 < 300


def test_old_per_unit_deep_planner_remains_available_without_manifest_projection() -> None:
    from app.protocols.protocol_control_planning import plan_protocol_control_batches

    old_plan = plan_protocol_control_batches(_manifest(3), max_owned_units_per_batch=2)
    input_projection = ProtocolControlAgentInput.from_batch(old_plan.batches[0])

    assert old_plan.expected_structure_unit_ids == [
        "unit-000",
        "unit-001",
        "unit-002",
    ]
    assert "manifest_structure_unit_ids" not in ProtocolControlAgentInput.model_fields
    assert "manifest_structure_unit_ids" not in input_projection.model_dump(mode="json")
