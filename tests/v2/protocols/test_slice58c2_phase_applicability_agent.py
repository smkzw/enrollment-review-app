from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.agents.phase_applicability import (
    PHASE_APPLICABILITY_AGENT_WIRE_V1_VERSION,
    PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION,
    PHASE_APPLICABILITY_AGENT_WIRE_VERSION,
    PhaseApplicabilityAgentInput,
    PhaseApplicabilityAgentResponse,
    PhaseApplicabilityAgentRunner,
    PhaseApplicabilityAgentWire,
    PhaseApplicabilityAgentWireValidationError,
    PhaseApplicabilityContextKind,
    PhaseApplicabilityContextPacket,
    build_phase_applicability_agent_input,
    build_phase_applicability_agent_prompt,
    build_phase_applicability_repair_prompt,
    hydrate_phase_applicability_agent_output,
    parse_phase_applicability_agent_wire,
    parse_phase_applicability_agent_wire_v1,
    phase_applicability_agent_json_schema,
    phase_applicability_agent_response_format,
)
from app.domain.contracts.enums import PhaseScope, StudyPhase
from app.domain.contracts.phase_applicability import (
    PhaseApplicabilityDisposition,
    PhaseApplicabilityEvidencePolarity,
    PhaseApplicabilityFrozenPackage,
    stable_phase_applicability_package_id,
)
from app.domain.contracts.protocol_controls import (
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    StructureUnitKind,
    TableCellContext,
)
from app.protocols.phase_applicability_planning import plan_phase_applicability_batches
from app.protocols.phase_applicability_planning import (
    build_phase_applicability_context_catalog,
)


_SHA = "a" * 64


def _unit(
    unit_id: str,
    order: int,
    *,
    scope: PhaseScope = PhaseScope.UNKNOWN,
    table: bool = False,
    excerpt: str | None = None,
    heading_path: list[str] | None = None,
    source_ref: str | None = None,
    table_kind: StructureUnitKind = StructureUnitKind.TABLE_ROW,
    table_path: tuple[int, ...] | None = None,
) -> ProtocolStructureUnit:
    span_id = f"span-{unit_id}"
    resolved_source_ref = source_ref or f"body.p{order}"
    resolved_table_path = table_path or (1, order, 0, 0)
    return ProtocolStructureUnit(
        structure_unit_id=unit_id,
        source_ref=resolved_source_ref,
        member_source_refs=[resolved_source_ref],
        source_span_ids=[span_id],
        unit_kind=table_kind if table else StructureUnitKind.PARAGRAPH,
        heading_path=heading_path
        or ["5 研究设计", "5.1 访视流程" if table else "5.2 期别说明"],
        table_context=(
            TableCellContext(
                table_path=resolved_table_path,
                row_index=resolved_table_path[-2],
                column_index=resolved_table_path[-1],
                member_cell_paths=[resolved_table_path],
                row_headers=["访视项目"],
                column_headers=["筛选期", "基线"],
            )
            if table
            else None
        ),
        source_order=order,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[scope],
        excerpt=excerpt or f"来源 {unit_id}：参见研究设计和期别流程。",
    )


def _package(
    *,
    owned: list[ProtocolStructureUnit] | None = None,
    context: list[ProtocolStructureUnit] | None = None,
) -> PhaseApplicabilityFrozenPackage:
    owned = owned or [
        _unit("target-01", 0),
        _unit("target-02", 1, table=True),
    ]
    context = context or [_unit("context-01", 2, scope=PhaseScope.PHASE_II)]
    manifest_id = "manifest:phase-agent"
    spans = sorted(
        {
            span_id
            for unit in [*owned, *context]
            for span_id in unit.source_span_ids
        }
    )
    return PhaseApplicabilityFrozenPackage(
        package_id=stable_phase_applicability_package_id(
            manifest_id,
            1,
            [unit.structure_unit_id for unit in owned],
        ),
        coverage_manifest_id=manifest_id,
        protocol_version_id="protocol:phase-agent-v1",
        protocol_document_sha256=_SHA,
        snapshot_id="snapshot:phase-agent",
        package_ordinal=1,
        selected_phase=StudyPhase.PHASE_II,
        opposite_phase=StudyPhase.PHASE_III,
        owned_units=owned,
        context_units=context,
        frozen_source_span_ids=spans,
    )


def _packets(package: PhaseApplicabilityFrozenPackage) -> list[PhaseApplicabilityContextPacket]:
    def packet(kind: PhaseApplicabilityContextKind, unit_indexes: list[int]):
        span_ids = sorted(
            {
                span_id
                for index in unit_indexes
                for span_id in package.all_units[index].source_span_ids
            }
        )
        return PhaseApplicabilityContextPacket(
            kind=kind,
            source_unit_indexes=unit_indexes,
            source_span_indexes=[package.frozen_source_span_ids.index(span) for span in span_ids],
        )

    return [
        packet(PhaseApplicabilityContextKind.HEADING_CHAIN, [0, 1, 2]),
        packet(PhaseApplicabilityContextKind.TABLE_TITLE_AND_HEADERS, [1]),
        packet(PhaseApplicabilityContextKind.STUDY_DESIGN_PHASE, [0, 2]),
        packet(PhaseApplicabilityContextKind.PHASE_PROTOCOL, [2]),
        packet(PhaseApplicabilityContextKind.VISIT_FLOW, [1]),
        packet(PhaseApplicabilityContextKind.CROSS_REFERENCE, [0, 1]),
    ]


def _input() -> PhaseApplicabilityAgentInput:
    package = _package()
    return PhaseApplicabilityAgentInput.from_frozen_package(package, _packets(package))


def _equivalent_input(
    second_updates: dict[str, object] | None = None,
) -> PhaseApplicabilityAgentInput:
    """Build two targets with an explicit, controllable equivalence boundary."""

    common = {
        "scope": PhaseScope.UNKNOWN,
        "table": True,
        "excerpt": "共同冻结目标摘录：本研究期别适用范围待语义确认。",
        "heading_path": ["5 研究设计", "5.2 期别说明"],
        "table_path": (1, 0, 0, 0),
    }
    first = _unit("target-01", 0, **common)
    second = _unit("target-02", 1, **common)
    if second_updates:
        second = second.model_copy(update=second_updates)
    package = _package(owned=[first, second])
    return PhaseApplicabilityAgentInput.from_frozen_package(package, _packets(package))


def _wire_result(
    agent_input: PhaseApplicabilityAgentInput,
    index: int,
    *,
    disposition: PhaseApplicabilityDisposition = (
        PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE
    ),
    polarity: PhaseApplicabilityEvidencePolarity = (
        PhaseApplicabilityEvidencePolarity.SUPPORTS
    ),
):
    unit = agent_input.target_units[index]
    unit_position = index
    span_position = agent_input.frozen_package.frozen_source_span_ids.index(
        unit.source_span_ids[0]
    )
    rationale_by_disposition = {
        PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE: (
            "原文明确说明该要求适用于本期，直接支持选定期别判断"
        ),
        PhaseApplicabilityDisposition.OPPOSITE_PHASE_APPLICABLE: (
            "原文明确说明该要求实际适用于对侧期别，直接支持对侧期别判断"
        ),
        PhaseApplicabilityDisposition.CROSS_PHASE_SHARED: (
            "原文明确说明同一要求对两期均适用，直接支持两期共用判断"
        ),
        PhaseApplicabilityDisposition.UNRESOLVED: (
            "当前原文仅有局部内容，缺少可确认适用范围的期别依据，仍需核对上下文"
        ),
    }
    rationale = rationale_by_disposition[disposition]
    return {
        "unit_index": index,
        "structure_unit_id": unit.structure_unit_id,
        "evidence": [
            {
                "polarity": polarity.value,
                "source_unit_indexes": [unit_position],
                "source_span_indexes": [span_position],
                "excerpt": unit.excerpt,
                "rationale": rationale,
            }
        ],
        "candidates": [
            {
                "scope": (
                    PhaseScope.SHARED.value
                    if disposition == PhaseApplicabilityDisposition.CROSS_PHASE_SHARED
                    else PhaseScope.PHASE_III.value
                    if disposition == PhaseApplicabilityDisposition.OPPOSITE_PHASE_APPLICABLE
                    else PhaseScope.PHASE_II.value
                ),
                "supporting_evidence_indexes": [0]
                if polarity == PhaseApplicabilityEvidencePolarity.SUPPORTS
                else [],
                "opposing_evidence_indexes": [0]
                if polarity == PhaseApplicabilityEvidencePolarity.OPPOSES
                else [],
                "unresolved_evidence_indexes": [0]
                if polarity == PhaseApplicabilityEvidencePolarity.UNRESOLVED
                else [],
            }
        ],
        "final_disposition": disposition.value,
        "rationale": rationale,
        "unresolved_reason": (
            "当前原文缺少可确认适用范围的期别依据，仍需核对上下文"
            if disposition == PhaseApplicabilityDisposition.UNRESOLVED
            else None
        ),
    }


def _wire(agent_input: PhaseApplicabilityAgentInput) -> dict[str, object]:
    return {
        "wire_version": PHASE_APPLICABILITY_AGENT_WIRE_VERSION,
        "results": [_wire_result(agent_input, index) for index in range(2)],
    }


def _compact_group(
    agent_input: PhaseApplicabilityAgentInput,
    indexes: list[int] | tuple[int, ...] = (0, 1),
    *,
    disposition: PhaseApplicabilityDisposition = (
        PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE
    ),
    polarity: PhaseApplicabilityEvidencePolarity = (
        PhaseApplicabilityEvidencePolarity.SUPPORTS
    ),
    source_unit_index: int | None = None,
    source_span_index: int | None = None,
    structure_unit_ids: list[str] | None = None,
) -> dict[str, object]:
    source_unit_index = (
        len(agent_input.target_units)
        if source_unit_index is None
        else source_unit_index
    )
    source_unit = agent_input.all_units[source_unit_index]
    source_span_index = (
        agent_input.frozen_package.frozen_source_span_ids.index(
            source_unit.source_span_ids[0]
        )
        if source_span_index is None
        else source_span_index
    )
    rationale_by_disposition = {
        PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE: (
            "原文明确说明该要求适用于本期，直接支持选定期别判断"
        ),
        PhaseApplicabilityDisposition.OPPOSITE_PHASE_APPLICABLE: (
            "原文明确说明该要求实际适用于对侧期别，直接支持对侧期别判断"
        ),
        PhaseApplicabilityDisposition.CROSS_PHASE_SHARED: (
            "原文明确说明同一要求对两期均适用，直接支持两期共用判断"
        ),
        PhaseApplicabilityDisposition.UNRESOLVED: (
            "当前原文仅有局部内容，缺少可确认适用范围的期别依据，仍需核对上下文"
        ),
    }
    rationale = rationale_by_disposition[disposition]
    return {
        "unit_indexes": list(indexes),
        "structure_unit_ids": (
            structure_unit_ids
            if structure_unit_ids is not None
            else [agent_input.target_units[index].structure_unit_id for index in indexes]
        ),
        "evidence": [
            {
                "polarity": polarity.value,
                "source_unit_indexes": [source_unit_index],
                "source_span_indexes": [source_span_index],
                "excerpt": source_unit.excerpt,
                "rationale": rationale,
            }
        ],
        "candidates": [
            {
                "scope": (
                    PhaseScope.SHARED.value
                    if disposition == PhaseApplicabilityDisposition.CROSS_PHASE_SHARED
                    else PhaseScope.PHASE_III.value
                    if disposition == PhaseApplicabilityDisposition.OPPOSITE_PHASE_APPLICABLE
                    else PhaseScope.PHASE_II.value
                ),
                "supporting_evidence_indexes": [0]
                if polarity == PhaseApplicabilityEvidencePolarity.SUPPORTS
                else [],
                "opposing_evidence_indexes": [0]
                if polarity == PhaseApplicabilityEvidencePolarity.OPPOSES
                else [],
                "unresolved_evidence_indexes": [0]
                if polarity == PhaseApplicabilityEvidencePolarity.UNRESOLVED
                else [],
            }
        ],
        "final_disposition": disposition.value,
        "rationale": rationale,
        "unresolved_reason": (
            "当前原文缺少可确认适用范围的期别依据，仍需核对上下文"
            if disposition == PhaseApplicabilityDisposition.UNRESOLVED
            else None
        ),
    }


def _compact_wire(
    groups: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "wire_version": PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION,
        "groups": groups,
    }


def test_frozen_planner_keeps_owned_identity_and_read_only_context_separate() -> None:
    units = [_unit(f"unit-{index}", index) for index in range(5)]
    manifest = ProtocolSectionCoverageManifest(
        manifest_id="manifest:planner",
        protocol_version_id="protocol:planner",
        protocol_document_sha256=_SHA,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:planner",
        units=units,
    )
    plan = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=2,
        context_radius=1,
    )
    assert [unit_id for package in plan.packages for unit_id in package.owned_structure_unit_ids] == [
        unit.structure_unit_id for unit in units
    ]
    for package in plan.packages:
        assert not set(package.owned_structure_unit_ids) & set(
            package.context_units[i].structure_unit_id
            for i in range(len(package.context_units))
        )
        assert package.package_id.startswith("pap-")


def test_planner_keeps_explicit_phase_units_read_only_and_targets_only_ambiguity() -> None:
    units = [
        _unit("explicit-selected", 0, scope=PhaseScope.PHASE_II),
        _unit("explicit-opposite", 1, scope=PhaseScope.PHASE_III),
        _unit("explicit-shared", 2, scope=PhaseScope.SHARED),
        _unit("ambiguous-unknown", 3, scope=PhaseScope.UNKNOWN),
        _unit("ambiguous-mixed", 4, scope=PhaseScope.MIXED),
    ]
    manifest = ProtocolSectionCoverageManifest(
        manifest_id="manifest:explicit-boundary",
        protocol_version_id="protocol:explicit-boundary",
        protocol_document_sha256=_SHA,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:explicit-boundary",
        units=units,
    )
    plan = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=1,
        context_radius=0,
    )

    assert plan.expected_structure_unit_ids == [
        "ambiguous-unknown",
        "ambiguous-mixed",
    ]
    assert [
        unit.structure_unit_id
        for package in plan.packages
        for unit in package.owned_units
    ] == plan.expected_structure_unit_ids
    first_package = plan.packages[0]
    assert first_package.owned_structure_unit_ids == ("ambiguous-unknown",)
    assert {
        unit.structure_unit_id for unit in first_package.context_units
    } >= {
        "explicit-selected",
        "explicit-opposite",
        "explicit-shared",
    }

    agent_input = PhaseApplicabilityAgentInput.from_frozen_package(first_package)
    assert agent_input.target_structure_unit_ids == ("ambiguous-unknown",)
    assert "explicit-selected" not in agent_input.target_structure_unit_ids
    forged = _wire_result(agent_input, 0)
    forged["structure_unit_id"] = "explicit-selected"
    with pytest.raises(PhaseApplicabilityAgentWireValidationError, match="BATCH_DRIFT"):
        hydrate_phase_applicability_agent_output(
            {"wire_version": PHASE_APPLICABILITY_AGENT_WIRE_VERSION, "results": [forged]},
            agent_input,
        )


def test_all_structurally_explicit_manifest_has_zero_agent_packages() -> None:
    units = [
        _unit("selected", 0, scope=PhaseScope.PHASE_II),
        _unit("opposite", 1, scope=PhaseScope.PHASE_III),
        _unit("shared", 2, scope=PhaseScope.SHARED),
    ]
    manifest = ProtocolSectionCoverageManifest(
        manifest_id="manifest:all-explicit",
        protocol_version_id="protocol:all-explicit",
        protocol_document_sha256=_SHA,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:all-explicit",
        units=units,
    )
    plan = plan_phase_applicability_batches(manifest)
    assert plan.packages == []
    assert plan.expected_structure_unit_ids == []
    catalog = build_phase_applicability_context_catalog(manifest)
    assert catalog.explicit_phase_structure_unit_ids == [
        "selected",
        "opposite",
        "shared",
    ]


def test_distant_full_manifest_context_reaches_target_packets_and_table_title() -> None:
    units = [
        _unit(
            "design-anchor",
            0,
            scope=PhaseScope.PHASE_II,
            heading_path=["1 研究设计"],
            excerpt="研究设计明确本研究阶段和期别安排。",
        ),
        _unit(
            "target-table-title",
            1,
            scope=PhaseScope.SHARED,
            heading_path=["8 合并用药"],
            excerpt="表 2 合并用药安排",
        ),
        _unit(
            "target-concomitant-row",
            2,
            scope=PhaseScope.UNKNOWN,
            table=True,
            heading_path=["8 合并用药", "表 2 合并用药安排"],
            source_ref="body.t2.r1",
            table_path=(1, 0),
            excerpt="目标用药项目：参见研究设计和访视流程。",
        ),
        _unit(
            "flow-header",
            3,
            scope=PhaseScope.SHARED,
            table=True,
            table_kind=StructureUnitKind.TABLE_HEADER,
            heading_path=["4 访视流程", "表 1 访视安排"],
            source_ref="body.t1.r0",
            table_path=(0, 0),
            excerpt="访视项目 | 筛选期 | 基线",
        ),
        _unit(
            "flow-row",
            4,
            scope=PhaseScope.UNKNOWN,
            table=True,
            heading_path=["4 访视流程", "表 1 访视安排"],
            source_ref="body.t1.r1",
            table_path=(1, 0),
            excerpt="首次给药访视：按访视流程执行。",
        ),
        _unit(
            "cross-reference",
            5,
            scope=PhaseScope.UNKNOWN,
            heading_path=["6 安全性"],
            excerpt="详见研究设计及表 1 访视安排。",
        ),
    ]
    manifest = ProtocolSectionCoverageManifest(
        manifest_id="manifest:distant-context",
        protocol_version_id="protocol:distant-context",
        protocol_document_sha256=_SHA,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:distant-context",
        units=units,
    )
    catalog = build_phase_applicability_context_catalog(manifest)
    assert "design-anchor" in catalog.study_design_phase_structure_unit_ids
    assert "flow-header" in catalog.visit_flow_structure_unit_ids
    assert "cross-reference" in catalog.cross_reference_structure_unit_ids
    assert "target-table-title" in catalog.table_anchor_structure_unit_ids

    plan = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=1,
        context_radius=0,
    )
    target_package = next(
        package
        for package in plan.packages
        if package.owned_structure_unit_ids == ("target-concomitant-row",)
    )
    context_ids = {unit.structure_unit_id for unit in target_package.context_units}
    assert {
        "design-anchor",
        "target-table-title",
        "flow-header",
        "flow-row",
    } <= context_ids
    assert "cross-reference" not in context_ids

    agent_input = PhaseApplicabilityAgentInput.from_frozen_package(target_package)
    packet_kinds = {packet.kind for packet in agent_input.context_packets}
    assert {
        PhaseApplicabilityContextKind.HEADING_CHAIN,
        PhaseApplicabilityContextKind.TABLE_TITLE_AND_HEADERS,
        PhaseApplicabilityContextKind.STUDY_DESIGN_PHASE,
        PhaseApplicabilityContextKind.PHASE_PROTOCOL,
        PhaseApplicabilityContextKind.VISIT_FLOW,
        PhaseApplicabilityContextKind.CROSS_REFERENCE,
    } <= packet_kinds
    table_packet = next(
        packet
        for packet in agent_input.context_packets
        if packet.kind == PhaseApplicabilityContextKind.TABLE_TITLE_AND_HEADERS
    )
    table_packet_ids = {
        agent_input.all_units[index].structure_unit_id
        for index in table_packet.source_unit_indexes
    }
    assert {"target-table-title", "target-concomitant-row"} <= table_packet_ids


def test_package_context_excludes_unrelated_tables_and_phase_sections() -> None:
    units = [
        _unit(
            "same-ancestor-phase",
            0,
            scope=PhaseScope.PHASE_II,
            heading_path=["8 目标表", "8.1 目标安排", "期别说明"],
            excerpt="本节明确目标表适用的研究期别。",
        ),
        _unit(
            "unrelated-phase",
            1,
            scope=PhaseScope.PHASE_III,
            heading_path=["9 另一期别说明"],
            excerpt="本结构单元属于另一期别。",
        ),
        _unit(
            "design-authority",
            2,
            scope=PhaseScope.PHASE_II,
            heading_path=["1 研究设计"],
            excerpt="研究设计明确本研究阶段安排。",
        ),
        _unit(
            "unrelated-table-title",
            3,
            scope=PhaseScope.SHARED,
            heading_path=["7 其他表"],
            excerpt="表 3 其他数据安排",
        ),
        _unit(
            "unrelated-table-row",
            4,
            scope=PhaseScope.SHARED,
            table=True,
            heading_path=["7 其他表", "表 3 其他数据安排"],
            source_ref="body.t3.r1",
            table_path=(3, 1, 0, 0),
            excerpt="无关表格行",
        ),
        _unit(
            "target-table-title",
            5,
            scope=PhaseScope.SHARED,
            heading_path=["8 目标表", "8.1 目标安排"],
            excerpt="表 2 目标安排",
        ),
        _unit(
            "target-table-header",
            6,
            scope=PhaseScope.SHARED,
            table=True,
            table_kind=StructureUnitKind.TABLE_HEADER,
            heading_path=["8 目标表", "8.1 目标安排", "表 2 目标安排"],
            source_ref="body.t2.r0",
            table_path=(2, 0, 0, 0),
            excerpt="项目 | 期别",
        ),
        _unit(
            "target-row",
            7,
            scope=PhaseScope.UNKNOWN,
            table=True,
            heading_path=["8 目标表", "8.1 目标安排", "表 2 目标安排"],
            source_ref="body.t2.r1",
            table_path=(2, 1, 0, 0),
            excerpt="待判断目标项目",
        ),
    ]
    manifest = ProtocolSectionCoverageManifest(
        manifest_id="manifest:relevant-context",
        protocol_version_id="protocol:relevant-context",
        protocol_document_sha256=_SHA,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:relevant-context",
        units=units,
    )
    plan = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=1,
        context_radius=0,
    )
    package = plan.packages[0]
    context_ids = {unit.structure_unit_id for unit in package.context_units}
    assert {
        "same-ancestor-phase",
        "design-authority",
        "target-table-title",
        "target-table-header",
    } <= context_ids
    assert {"unrelated-phase", "unrelated-table-title", "unrelated-table-row"}.isdisjoint(
        context_ids
    )
    assert package.owned_structure_unit_ids == ("target-row",)


def test_large_target_table_closure_repeats_across_batches_without_unrelated_table() -> None:
    target_title = _unit(
        "target-table-title",
        0,
        scope=PhaseScope.SHARED,
        heading_path=["7 目标表"],
        excerpt="表 9 目标安排",
    )
    target_header = _unit(
        "target-table-header",
        1,
        scope=PhaseScope.SHARED,
        table=True,
        table_kind=StructureUnitKind.TABLE_HEADER,
        heading_path=["7 目标表", "表 9 目标安排"],
        source_ref="body.t9.r0.c0.p0",
        table_path=(0, 0),
        excerpt="项目 | 期别",
    )
    target_note = _unit(
        "target-table-note",
        2,
        scope=PhaseScope.SHARED,
        table=True,
        table_kind=StructureUnitKind.TABLE_NOTE,
        heading_path=["7 目标表", "表 9 目标安排"],
        source_ref="body.t9.r6.c0.p0",
        table_path=(6, 0),
        excerpt="注：表内项目按方案要求执行。",
    )
    target_rows = [
        _unit(
            f"target-row-{index}",
            index + 3,
            scope=PhaseScope.UNKNOWN,
            table=True,
            heading_path=["7 目标表", "表 9 目标安排"],
            source_ref=f"body.t9.r{index + 1}.c0.p0",
            table_path=(index + 1, 0),
            excerpt=f"目标项目 {index + 1}：保留同表语境。",
        )
        for index in range(5)
    ]
    unrelated_title = _unit(
        "unrelated-table-title",
        8,
        scope=PhaseScope.SHARED,
        heading_path=["8 无关表"],
        excerpt="表 10 无关安排",
    )
    unrelated_row = _unit(
        "unrelated-table-row",
        9,
        scope=PhaseScope.SHARED,
        table=True,
        heading_path=["8 无关表", "表 10 无关安排"],
        source_ref="body.t10.r1.c0.p0",
        table_path=(1, 0),
        excerpt="无关表格行。",
    )
    units = [
        target_title,
        target_header,
        target_note,
        *target_rows,
        unrelated_title,
        unrelated_row,
    ]
    manifest = ProtocolSectionCoverageManifest(
        manifest_id="manifest:large-table-closure",
        protocol_version_id="protocol:large-table-closure",
        protocol_document_sha256=_SHA,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:large-table-closure",
        units=units,
    )
    plan = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=2,
        context_radius=0,
    )

    target_closure = {
        target_title.structure_unit_id,
        target_header.structure_unit_id,
        target_note.structure_unit_id,
        *(unit.structure_unit_id for unit in target_rows),
    }
    unrelated_ids = {
        unrelated_title.structure_unit_id,
        unrelated_row.structure_unit_id,
    }
    assert len(plan.packages) == 3
    assert [
        unit_id
        for package in plan.packages
        for unit_id in package.owned_structure_unit_ids
    ] == [unit.structure_unit_id for unit in target_rows]
    for package in plan.packages:
        all_ids = {unit.structure_unit_id for unit in package.all_units}
        owned_ids = set(package.owned_structure_unit_ids)
        context_ids = {unit.structure_unit_id for unit in package.context_units}
        assert target_closure <= all_ids
        assert target_closure - owned_ids <= context_ids
        assert unrelated_ids.isdisjoint(all_ids)

    target_input = build_phase_applicability_agent_input(plan.packages[0])
    assert PhaseApplicabilityContextKind.VISIT_FLOW not in {
        packet.kind for packet in target_input.context_packets
    }


def test_context_selection_has_relative_size_guardrail_without_truncation() -> None:
    units = [
        _unit(
            "design-authority",
            0,
            scope=PhaseScope.PHASE_II,
            heading_path=["1 研究设计"],
            excerpt="研究设计明确研究阶段安排。",
        )
    ]
    for index in range(1, 60):
        units.append(
            _unit(
                f"unrelated-{index}",
                index,
                scope=PhaseScope.SHARED,
                heading_path=[f"{index + 1} 无关章节"],
                excerpt=f"无关结构单元 {index}",
            )
        )
    units.append(
        _unit(
            "target",
            60,
            scope=PhaseScope.UNKNOWN,
            heading_path=["8 目标章节"],
            excerpt="待判断目标",
        )
    )
    manifest = ProtocolSectionCoverageManifest(
        manifest_id="manifest:context-size",
        protocol_version_id="protocol:context-size",
        protocol_document_sha256=_SHA,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:context-size",
        units=units,
    )
    plan = plan_phase_applicability_batches(manifest, max_owned_units_per_batch=1)
    package = plan.packages[0]
    assert len(package.context_units) * 2 < len(manifest.units)
    prompt = build_phase_applicability_agent_prompt(package)
    assert len(prompt) < len(manifest.units) * 500


def test_unresolved_local_cross_reference_remains_frozen_context() -> None:
    units = [
        _unit(
            "target-with-reference",
            0,
            scope=PhaseScope.UNKNOWN,
            heading_path=["2 目标章节", "2.1 目标内容"],
            excerpt="目标内容需要结合下列来源判断。",
        ),
        _unit(
            "unresolved-reference",
            1,
            scope=PhaseScope.UNKNOWN,
            heading_path=["2 目标章节", "2.1 目标内容"],
            excerpt="详见无法解析的附录标记。",
        ),
    ]
    manifest = ProtocolSectionCoverageManifest(
        manifest_id="manifest:unresolved-reference",
        protocol_version_id="protocol:unresolved-reference",
        protocol_document_sha256=_SHA,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:unresolved-reference",
        units=units,
    )
    plan = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=1,
        context_radius=1,
    )
    target_package = plan.packages[0]
    assert target_package.owned_structure_unit_ids == ("target-with-reference",)
    assert {
        unit.structure_unit_id for unit in target_package.context_units
    } == {"unresolved-reference"}


def test_input_contains_structural_context_packets_and_prompt_is_chinese_native() -> None:
    agent_input = _input()
    kinds = {packet.kind for packet in agent_input.context_packets}
    assert {
        PhaseApplicabilityContextKind.HEADING_CHAIN,
        PhaseApplicabilityContextKind.TABLE_TITLE_AND_HEADERS,
        PhaseApplicabilityContextKind.STUDY_DESIGN_PHASE,
        PhaseApplicabilityContextKind.PHASE_PROTOCOL,
        PhaseApplicabilityContextKind.VISIT_FLOW,
        PhaseApplicabilityContextKind.CROSS_REFERENCE,
    } <= kinds
    prompt = build_phase_applicability_agent_prompt(agent_input)
    assert "上位章节标题链" in prompt
    assert "表题与表头" in prompt
    assert "研究设计/期别章节" in prompt
    assert "访视流程表" in prompt
    assert "明确交叉引用" in prompt
    assert "未知默认成共享" in prompt
    assert "输入 UNKNOWN/MIXED 不是输出候选期别" in prompt
    assert "绝不能复制为 candidate.scope" in prompt
    assert "先确认目标是否应纳入 selected_phase 所代表的独立研究" in prompt
    assert "不限制把目标自身明确写出的全局控制纳入当前已选独立研究" in prompt
    assert "未限定某一期" in prompt
    assert "不能单独证明两期共同适用" in prompt
    assert "共同章节结构" in prompt
    assert "同一义务家族" in prompt
    assert "全局广播" in prompt
    assert "盲法共用" in prompt
    assert "部分闭合" in prompt
    assert "不得用 cross_phase_shared 掩盖差异" in prompt
    assert "访视时间、时间窗、阈值、剂量、适用人群或执行条件" in prompt
    assert "每条证据优先只引用一个直接 source_unit_index" in prompt
    assert "不能把标题链或其他单元的片段索引全部挂到一个" in prompt
    assert "不得生成系统身份字段" not in prompt
    assert phase_applicability_agent_json_schema()["additionalProperties"] is False
    assert phase_applicability_agent_response_format()["json_schema"]["strict"] is True


def test_repair_prompt_rejects_absence_only_shared_reasoning() -> None:
    prompt = build_phase_applicability_repair_prompt(
        _input(),
        problem="RATIONALE_INCOMPLETE",
        unit_indexes=[0],
    )

    assert "未限定某一期" in prompt
    assert "不能证明跨期共用" in prompt
    assert "否则改为 unresolved" in prompt
    assert "标题链或表格语境" in prompt
    assert "unresolved 是最终处置而非候选期别" in prompt
    assert "不得返回 unknown 或 mixed" in prompt
    assert "输入 UNKNOWN/MIXED 不是输出候选期别" in prompt
    assert "先判断目标是否纳入 selected_phase 所代表的独立研究" in prompt
    assert "禁止全局广播只限制跨期共用和兄弟义务扩散" in prompt
    assert "不得用 cross_phase_shared 掩盖差异" in prompt
    assert "访视时间、时间窗、阈值、剂量、适用人群或执行条件" in prompt
    assert "必须返回本批全部目标" in prompt
    assert "修复轮必须逐项回显完整冻结目标清单" in prompt
    checklist_line = next(
        line
        for line in prompt.splitlines()
        if line.startswith("完整冻结目标清单（修复后必须逐项回显")
    )
    assert json.loads(checklist_line.split("：", 1)[1]) == [
        {"unit_index": 0, "structure_unit_id": "target-01"},
        {"unit_index": 1, "structure_unit_id": "target-02"},
    ]
    assert "同一义务家族" in prompt
    assert "全局广播" in prompt


def test_repair_prompt_for_missing_shared_source_forbids_repeating_same_result() -> None:
    prompt = build_phase_applicability_repair_prompt(
        _input(),
        problem="SHARED_POSITIVE_SOURCE_MISSING: 跨期共用缺少正向来源",
        unit_indexes=[0],
    )

    assert "只能补充符合门禁的同一义务共用来源" in prompt
    assert "禁止原样重复同一 cross_phase_shared 处置和同一不足来源" in prompt
    assert "selected_phase_applicable、opposite_phase_applicable 或 unresolved" in prompt
    assert "部分闭合" in prompt


def test_prompt_renders_global_span_indexes_paired_with_each_span_id() -> None:
    agent_input = _input()
    package = agent_input.frozen_package
    prompt = build_phase_applicability_agent_prompt(agent_input)
    projection = json.loads(
        prompt.split("本次冻结输入：", 1)[1].split("\n\n请按", 1)[0]
    )
    span_ids = package.frozen_source_span_ids

    rendered_units = [*projection["target_units"], *projection["context_units"]]
    assert rendered_units
    assert len(rendered_units) == len(package.all_units)
    assert [unit["unit_index"] for unit in rendered_units] == list(
        range(len(package.all_units))
    )
    assert [unit["structure_unit_id"] for unit in rendered_units] == [
        unit.structure_unit_id for unit in package.all_units
    ]
    assert all(
        set(packet) == {"kind", "source_unit_indexes", "source_span_indexes"}
        for packet in projection["context_packets"]
    )
    assert all(
        "excerpt" not in packet
        and "source_members" not in packet
        for packet in projection["context_packets"]
    )
    assert "source_members" not in prompt
    for rendered in rendered_units:
        assert len(rendered["source_span_ids"]) == len(
            rendered["source_span_indexes"]
        )
        assert [
            span_ids[index] for index in rendered["source_span_indexes"]
        ] == rendered["source_span_ids"]
    for packet in projection["context_packets"]:
        cited_spans = {
            span_id
            for unit_index in packet["source_unit_indexes"]
            for span_id in package.all_units[unit_index].source_span_ids
        }
        packet_spans = {
            span_ids[index] for index in packet["source_span_indexes"]
        }
        assert packet_spans <= cited_spans <= set(span_ids)
    assert "同一 target_units/context_units 冻结正文" in prompt
    assert "一条直接证据" in prompt
    assert len(prompt) < 240_000


def test_strict_hydration_echoes_only_target_identity_and_injects_system_ids() -> None:
    agent_input = _input()
    output = hydrate_phase_applicability_agent_output(_wire(agent_input), agent_input)
    assert [result.structure_unit_id for result in output.results] == [
        "target-01",
        "target-02",
    ]
    assert all(result.resolution_id.startswith("par-") for result in output.results)
    assert all(
        result.evidence[0].evidence_id.startswith("pae-")
        for result in output.results
    )
    dumped = json.dumps(_wire(agent_input), ensure_ascii=False)
    assert "resolution_id" not in dumped
    assert "evidence_id" not in dumped
    assert "source_span_ids" not in dumped


def test_v2_group_expands_to_sorted_unit_results_with_per_unit_identities() -> None:
    agent_input = _equivalent_input()
    output = hydrate_phase_applicability_agent_output(
        _compact_wire([_compact_group(agent_input)]),
        agent_input,
    )

    assert [result.structure_unit_id for result in output.results] == [
        "target-01",
        "target-02",
    ]
    assert len({result.resolution_id for result in output.results}) == 2
    assert [
        result.evidence[0].source_structure_unit_ids for result in output.results
    ] == [["context-01"], ["context-01"]]
    assert len({result.evidence[0].evidence_id for result in output.results}) == 2


@pytest.mark.parametrize(
    "updates",
    [
        pytest.param(
            {"excerpt": "另一条冻结目标摘录：本研究期别适用范围待语义确认。"},
            id="different-excerpt",
        ),
        pytest.param(
            {"heading_path": ["5 研究设计", "5.3 另一期别说明"]},
            id="different-heading-path",
        ),
        pytest.param(
            {
                "table_context": TableCellContext(
                    table_path=(1, 0, 0, 0),
                    row_index=0,
                    column_index=0,
                    member_cell_paths=[(1, 0, 0, 0)],
                    row_headers=["另一项目表头"],
                    column_headers=["筛选期", "基线"],
                )
            },
            id="different-table-context",
        ),
        pytest.param(
            {"phase_scopes": [PhaseScope.PHASE_III]},
            id="different-phase-scope",
        ),
    ],
)
def test_v2_rejects_one_group_for_each_heterogeneous_target_boundary(
    updates: dict[str, object],
) -> None:
    agent_input = _equivalent_input(updates)

    with pytest.raises(
        PhaseApplicabilityAgentWireValidationError,
        match="TARGET_GROUP_HETEROGENEOUS",
    ):
        hydrate_phase_applicability_agent_output(
            _compact_wire([_compact_group(agent_input)]),
            agent_input,
        )


def test_v2_rejects_unsorted_group_and_cross_group_target_indexes() -> None:
    agent_input = _input()
    unsorted_group = _compact_group(
        agent_input,
        [1, 0],
        structure_unit_ids=["target-02", "target-01"],
    )
    with pytest.raises(
        PhaseApplicabilityAgentWireValidationError,
        match="WIRE_SCHEMA_INVALID",
    ):
        hydrate_phase_applicability_agent_output(
            _compact_wire([unsorted_group]),
            agent_input,
        )

    unsorted_groups = [
        _compact_group(
            agent_input,
            [1],
            disposition=PhaseApplicabilityDisposition.UNRESOLVED,
            polarity=PhaseApplicabilityEvidencePolarity.UNRESOLVED,
        ),
        _compact_group(agent_input, [0]),
    ]
    with pytest.raises(
        PhaseApplicabilityAgentWireValidationError,
        match="WIRE_SCHEMA_INVALID",
    ):
        hydrate_phase_applicability_agent_output(
            _compact_wire(unsorted_groups),
            agent_input,
        )


def test_v2_rejects_duplicate_target_membership_and_duplicate_group_payload() -> None:
    agent_input = _input()
    duplicate_target_groups = [
        _compact_group(agent_input, [0]),
        _compact_group(agent_input, [0]),
    ]
    with pytest.raises(
        PhaseApplicabilityAgentWireValidationError,
        match="WIRE_SCHEMA_INVALID",
    ):
        hydrate_phase_applicability_agent_output(
            _compact_wire(duplicate_target_groups),
            agent_input,
        )

    equivalent_input = _equivalent_input()
    duplicate_payload_groups = [
        _compact_group(equivalent_input, [0]),
        _compact_group(equivalent_input, [1]),
    ]
    with pytest.raises(
        PhaseApplicabilityAgentWireValidationError,
        match="DUPLICATE_GROUP_PAYLOAD",
    ):
        hydrate_phase_applicability_agent_output(
            _compact_wire(duplicate_payload_groups),
            equivalent_input,
        )


def test_v2_rejects_identity_drift_and_missing_owned_target() -> None:
    agent_input = _input()
    drifted_group = _compact_group(agent_input)
    drifted_group["structure_unit_ids"] = [
        "target-01",
        "target-from-another-batch",
    ]
    with pytest.raises(
        PhaseApplicabilityAgentWireValidationError,
        match="BATCH_DRIFT",
    ):
        hydrate_phase_applicability_agent_output(
            _compact_wire([drifted_group]),
            agent_input,
        )

    with pytest.raises(
        PhaseApplicabilityAgentWireValidationError,
        match="PARTIAL_OR_DRIFTED_BATCH",
    ):
        hydrate_phase_applicability_agent_output(
            _compact_wire([_compact_group(agent_input, [0])]),
            agent_input,
        )


def test_v2_keeps_heterogeneous_target_semantics_in_separate_groups() -> None:
    agent_input = _input()
    output = hydrate_phase_applicability_agent_output(
        _compact_wire(
            [
                _compact_group(agent_input, [0]),
                _compact_group(
                    agent_input,
                    [1],
                    disposition=PhaseApplicabilityDisposition.UNRESOLVED,
                    polarity=PhaseApplicabilityEvidencePolarity.UNRESOLVED,
                ),
            ]
        ),
        agent_input,
    )

    assert [result.final_disposition for result in output.results] == [
        PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE,
        PhaseApplicabilityDisposition.UNRESOLVED,
    ]
    assert (
        output.results[1].unresolved_reason
        == "当前原文缺少可确认适用范围的期别依据，仍需核对上下文"
    )


def test_v2_allows_same_semantic_payload_for_separate_heterogeneous_targets() -> None:
    agent_input = _input()
    output = hydrate_phase_applicability_agent_output(
        _compact_wire(
            [
                _compact_group(agent_input, [0]),
                _compact_group(agent_input, [1]),
            ]
        ),
        agent_input,
    )

    assert [result.structure_unit_id for result in output.results] == [
        "target-01",
        "target-02",
    ]
    assert all(
        result.final_disposition
        == PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE
        for result in output.results
    )


def test_prompt_distinguishes_cross_phase_reference_from_shared_applicability() -> None:
    prompt = build_phase_applicability_agent_prompt(_input())

    assert "实际适用对象、操作或义务发生阶段" in prompt
    assert "因果或时序关联，不等于同一要求对两期均适用" in prompt
    assert "即使以选定期结果为前提" in prompt


def test_v2_evidence_span_must_belong_to_the_cited_source_unit() -> None:
    agent_input = _equivalent_input()
    mismatched_span_group = _compact_group(
        agent_input,
        source_unit_index=2,
        source_span_index=1,
    )
    with pytest.raises(
        PhaseApplicabilityAgentWireValidationError,
        match="EVIDENCE_SPAN_UNIT_MISMATCH",
    ):
        hydrate_phase_applicability_agent_output(
            _compact_wire([mismatched_span_group]),
            agent_input,
        )

    outside_unit_group = _compact_group(agent_input)
    outside_unit_group["evidence"][0]["source_unit_indexes"] = [99]
    with pytest.raises(
        PhaseApplicabilityAgentWireValidationError,
        match="PACKAGE_UNIT_INDEX_OUT_OF_RANGE",
    ):
        hydrate_phase_applicability_agent_output(
            _compact_wire([outside_unit_group]),
            agent_input,
        )


def test_v1_historical_wire_remains_readable_and_uses_the_same_hydration_gate() -> None:
    agent_input = _input()
    text = json.dumps(_wire(agent_input), ensure_ascii=False)
    parsed = parse_phase_applicability_agent_wire_v1(text)

    assert parsed.wire_version == PHASE_APPLICABILITY_AGENT_WIRE_V1_VERSION
    output = hydrate_phase_applicability_agent_output(parsed, agent_input)
    assert [result.structure_unit_id for result in output.results] == [
        "target-01",
        "target-02",
    ]


def test_parser_rejects_provider_ids_markdown_and_english_or_log_rationales() -> None:
    agent_input = _input()
    payload = _wire(agent_input)
    payload["package_id"] = agent_input.frozen_package.package_id
    with pytest.raises(PhaseApplicabilityAgentWireValidationError, match="PROVIDER_ID_FORBIDDEN"):
        parse_phase_applicability_agent_wire(json.dumps(payload, ensure_ascii=False))

    payload = _wire(agent_input)
    payload["results"][0]["rationale"] = "selected phase based on evidence"
    with pytest.raises(PhaseApplicabilityAgentWireValidationError, match="WIRE_SCHEMA_INVALID"):
        parse_phase_applicability_agent_wire(json.dumps(payload, ensure_ascii=False))

    with pytest.raises(PhaseApplicabilityAgentWireValidationError, match="MARKDOWN_OUTPUT"):
        parse_phase_applicability_agent_wire("```json\n{}\n```")

    payload = _wire(agent_input)
    payload["results"][0]["rationale"] = "ERROR: model output"
    with pytest.raises(PhaseApplicabilityAgentWireValidationError, match="WIRE_SCHEMA_INVALID"):
        parse_phase_applicability_agent_wire(json.dumps(payload, ensure_ascii=False))


def test_hydration_rejects_omission_batch_drift_and_source_escape() -> None:
    agent_input = _input()
    payload = _wire(agent_input)

    payload["results"] = payload["results"][:1]
    with pytest.raises(PhaseApplicabilityAgentWireValidationError, match="PARTIAL_OR_DRIFTED_BATCH"):
        hydrate_phase_applicability_agent_output(payload, agent_input)

    payload = _wire(agent_input)
    payload["results"][1]["structure_unit_id"] = "target-from-another-batch"
    with pytest.raises(PhaseApplicabilityAgentWireValidationError, match="BATCH_DRIFT"):
        hydrate_phase_applicability_agent_output(payload, agent_input)

    payload = _wire(agent_input)
    payload["results"][0]["evidence"][0]["source_span_indexes"] = [99]
    with pytest.raises(PhaseApplicabilityAgentWireValidationError, match="PACKAGE_SPAN_INDEX_OUT_OF_RANGE"):
        hydrate_phase_applicability_agent_output(payload, agent_input)


def test_shared_requires_supporting_source_and_unresolved_stays_explicit() -> None:
    agent_input = _input()
    payload = _wire(agent_input)
    payload["results"][0] = _wire_result(
        agent_input,
        0,
        disposition=PhaseApplicabilityDisposition.CROSS_PHASE_SHARED,
        polarity=PhaseApplicabilityEvidencePolarity.OPPOSES,
    )
    with pytest.raises(PhaseApplicabilityAgentWireValidationError, match="SHARED_UNSUPPORTED"):
        hydrate_phase_applicability_agent_output(payload, agent_input)

    unresolved = _wire_result(
        agent_input,
        0,
        disposition=PhaseApplicabilityDisposition.UNRESOLVED,
        polarity=PhaseApplicabilityEvidencePolarity.UNRESOLVED,
    )
    payload["results"][0] = unresolved
    output = hydrate_phase_applicability_agent_output(payload, agent_input)
    assert output.results[0].final_disposition == PhaseApplicabilityDisposition.UNRESOLVED


def test_shared_rationale_does_not_require_a_fixed_semantic_password() -> None:
    package = _package(
        owned=[
            _unit("target-01", 0, scope=PhaseScope.SHARED),
            _unit("target-02", 1, table=True),
        ]
    )
    agent_input = PhaseApplicabilityAgentInput.from_frozen_package(
        package,
        _packets(package),
    )
    payload = _wire(agent_input)
    shared = _wire_result(
        agent_input,
        0,
        disposition=PhaseApplicabilityDisposition.CROSS_PHASE_SHARED,
    )
    rationale = "方案原文逐字说明该检查在Ⅱ期与Ⅲ期均执行，直接支持两期共同适用"
    shared["rationale"] = rationale
    shared["evidence"][0]["rationale"] = rationale
    payload["results"][0] = shared

    output = hydrate_phase_applicability_agent_output(payload, agent_input)
    assert output.results[0].final_disposition == PhaseApplicabilityDisposition.CROSS_PHASE_SHARED


class _FakeTransport:
    def __init__(self, responses: list[PhaseApplicabilityAgentResponse]) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    def start(self, *, prompt: str) -> PhaseApplicabilityAgentResponse:
        self.prompts.append(prompt)
        return self.responses.pop(0)

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
    ) -> PhaseApplicabilityAgentResponse:
        self.prompts.append(prompt)
        response = self.responses.pop(0)
        assert response.session_id == session_id
        return response


def test_runner_repairs_in_same_session_without_live_model_call() -> None:
    agent_input = _input()
    invalid = json.dumps({"wire_version": PHASE_APPLICABILITY_AGENT_WIRE_VERSION, "results": []})
    valid = json.dumps(_wire(agent_input), ensure_ascii=False)
    transport = _FakeTransport(
        [
            PhaseApplicabilityAgentResponse(session_id="phase-session-1", text=invalid),
            PhaseApplicabilityAgentResponse(session_id="phase-session-1", text=valid),
        ]
    )
    result = PhaseApplicabilityAgentRunner(max_schema_repairs=1).run(
        agent_input,
        transport,
    )
    assert result.status == "已解析"
    assert result.final_output is not None
    assert len(result.attempts) == 2
    assert "定向修复" in transport.prompts[1]
    assert agent_input.frozen_package.package_id in transport.prompts[1]

    with pytest.raises(ValueError, match="已接受冻结包"):
        PhaseApplicabilityAgentRunner().run(
            agent_input,
            _FakeTransport([]),
            accepted_package_ids=[agent_input.frozen_package.package_id],
        )
