"""Synthetic regression coverage for the two-stage control route."""

from __future__ import annotations

import json
from datetime import datetime, timezone

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
from app.domain.contracts.enums import CatalogItemKind, CatalogKind, PhaseScope, ReviewStage, StudyPhase
from app.domain.contracts.protocol_controls import (
    ProtocolControlDispositionBatch,
    ProtocolControlDiscoveryDecision,
    ProtocolControlDiscoveryDisposition,
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    StructureUnitKind,
)
from app.domain.contracts.protocol_ingestion import FrozenCatalogItem, FrozenProtocolCatalog
from app.domain.publication import canonical_hash
from app.protocols.protocol_control_planning import (
    DEFAULT_PROTOCOL_CONTROL_DISCOVERY_BATCH_UNITS,
    _cross_chapter_readonly_context,
    _deep_batch_chunks,
    plan_protocol_control_deep_batches_from_discovery,
    plan_protocol_control_discovery,
    validate_protocol_control_deep_selection,
    validate_protocol_control_discovery_results,
)
from app.services.protocol_control_execution import _build_publication_plan


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


def test_cross_chapter_similarity_is_readonly_and_scoped() -> None:
    summary = _unit(0, "摘要").model_copy(update={
        "excerpt": "所有参加者须在筛选时完成采样，随后每日按规定剂量给药，并记录每次用药；如有漏服须在当次访视记录原因及实际给药情况，相关记录应保留在受试者原始病历中供后续访视核对。",
        "phase_scopes": [PhaseScope.PHASE_II],
    })
    later = _unit(1, "研究用药").model_copy(update={
        "excerpt": summary.excerpt,
        "phase_scopes": [PhaseScope.SHARED],
    })
    other_phase = _unit(2, "另一阶段").model_copy(update={
        "excerpt": later.excerpt,
        "phase_scopes": [PhaseScope.PHASE_III],
    })
    unrelated = _unit(3, "统计").model_copy(update={
        "excerpt": "本研究的统计分析将根据预定计划实施，资料核对和数据锁定的责任另行规定。",
    })
    matches = _cross_chapter_readonly_context(
        [summary], [summary, later, other_phase, unrelated],
    )
    assert matches[summary.structure_unit_id] == (later.structure_unit_id,)


def test_cross_chapter_short_text_is_not_promoted_to_context() -> None:
    first = _unit(0, "摘要").model_copy(update={"excerpt": "每日给药"})
    second = _unit(1, "研究用药").model_copy(update={"excerpt": "每日给药"})
    assert _cross_chapter_readonly_context([first], [first, second]) == {}


def test_deep_plan_preserves_source_action_and_exact_procedure_targets() -> None:
    action = "在筛选及基线访视完成症状评估；非到院日建议于给药前1 h内进行评估，每日均需评估。"
    owned = _unit(0).model_copy(update={"excerpt": action})
    manifest = _manifest(2).model_copy(update={"units": [owned, _unit(1)]})
    discovery = plan_protocol_control_discovery(manifest, max_units_per_batch=2)
    decisions = [[ProtocolControlDiscoveryDecision(
        structure_unit_id=unit_id,
        disposition=(ProtocolControlDiscoveryDisposition.CANDIDATE
                     if unit_id == owned.structure_unit_id else
                     ProtocolControlDiscoveryDisposition.NON_CONTROL),
        rationale="按原文核对",
    ) for unit_id in discovery.batches[0].target_structure_unit_ids]]
    items = [
        FrozenCatalogItem(
            item_id=f"procedure-{stage.value}",
            kind=CatalogItemKind.REQUIRED_PROCEDURE,
            label="症状评估",
            visit_instance=f"visit-{stage.value}",
            review_stage=stage,
            position=index,
            source_span_ids=("span:000",),
            source_excerpts=(action,),
        )
        for index, stage in enumerate((ReviewStage.SCREENING, ReviewStage.BASELINE))
    ] + [
        FrozenCatalogItem(
            item_id="procedure-other-excerpt",
            kind=CatalogItemKind.REQUIRED_PROCEDURE,
            label="其他评估",
            visit_instance="visit-other",
            review_stage=ReviewStage.BASELINE,
            position=2,
            source_span_ids=("span:000",),
            source_excerpts=("同页的另一项评估",),
        ),
    ]
    catalog_fields = dict(
        catalog_id="catalog:general-actions",
        snapshot_id=manifest.snapshot_id,
        catalog_kind=CatalogKind.REQUIRED_PROCEDURES,
        study_phase=manifest.study_phase,
        items=tuple(items),
        frozen_at=datetime(2026, 9, 26, tzinfo=timezone.utc),
        frozen_by="synthetic-test",
    )
    shell = FrozenProtocolCatalog.model_construct(
        schema_version="fixture/v1", **catalog_fields, catalog_sha256="",
    )
    procedures = FrozenProtocolCatalog(
        **catalog_fields,
        catalog_sha256=canonical_hash(
            shell.model_dump(mode="json", exclude={"catalog_sha256"})
        ),
    )

    plan = plan_protocol_control_deep_batches_from_discovery(
        manifest, discovery, decisions, required_procedure_catalog=procedures,
    )
    batch = plan.batches[0]
    assert batch.owned_required_action_kinds_by_structure_unit_id
    assert batch.owned_required_procedure_target_ids_by_structure_unit_id == {
        owned.structure_unit_id: ["procedure-baseline", "procedure-screening"]
    }


def test_cross_chapter_context_is_readonly_and_changes_plan_identity() -> None:
    source = "受试者在筛选开始后应持续按规定方案用药，每次访视核对实际剂量与给药次数，并记录任何中断原因和恢复日期。"
    source += "研究团队须核查已记录的给药情况，不得将未核对的用药记录视为完成。"
    manifest = _manifest(3).model_copy(update={"units": [
        _unit(0, "概要").model_copy(update={"excerpt": source}),
        _unit(1, "合并用药").model_copy(update={"excerpt": source}),
        _unit(2, "统计说明"),
    ]})
    discovery = plan_protocol_control_discovery(manifest, max_units_per_batch=3)
    decisions = [[ProtocolControlDiscoveryDecision(
        structure_unit_id=unit_id,
        disposition=(ProtocolControlDiscoveryDisposition.CANDIDATE
                     if unit_id == "unit-000" else
                     ProtocolControlDiscoveryDisposition.CONTEXT_ONLY
                     if unit_id == "unit-001" else
                     ProtocolControlDiscoveryDisposition.NON_CONTROL),
        rationale="只按来源处置",
    ) for unit_id in discovery.batches[0].target_structure_unit_ids]]
    linked = plan_protocol_control_deep_batches_from_discovery(manifest, discovery, decisions)
    assert linked.deep_structure_unit_ids == ("unit-000",)
    assert linked.batches[0].context_structure_unit_ids == ["unit-001"]
    assert linked.batches[0].owned_structure_unit_ids == ["unit-000"]
    changed = manifest.model_copy(update={"units": [
        manifest.units[0],
        manifest.units[1].model_copy(update={"excerpt": "这段只说明统计分析，不说明受试者用药。"}),
        manifest.units[2],
    ]})
    unlinked = plan_protocol_control_deep_batches_from_discovery(changed, discovery, decisions)
    assert unlinked.batches[0].context_structure_unit_ids == []
    assert unlinked.plan_id != linked.plan_id
    altered = linked.model_dump(mode="json")
    altered["related_context_ids_by_owned"] = {"unit-000": ["unit-002"]}
    with pytest.raises(ValueError, match="跨章节只读线索"):
        type(linked).model_validate(altered)


def test_deep_table_rows_retain_read_only_leading_headers() -> None:
    def row(table: int, index: int) -> ProtocolStructureUnit:
        ref = f"body.t{table}.r{index}"
        return ProtocolStructureUnit(
            structure_unit_id=f"table-{table}-row-{index}",
            source_ref=ref,
            member_source_refs=[f"{ref}.c0"],
            source_span_ids=[f"span:t{table}:r{index}"],
            unit_kind="table_row",
            heading_path=["访视安排"],
            table_context={
                "table_path": [index, 0],
                "row_index": index,
                "column_index": 0,
                "row_headers": ["项目"],
                "column_headers": ["阶段"],
                "member_cell_paths": [[index, 0]],
            },
            source_order=table * 100 + index,
            study_phase=StudyPhase.PHASE_II,
            phase_scopes=[PhaseScope.SHARED],
            excerpt=f"第{index}行",
        )

    first_table = [row(1, index) for index in (0, 1, 2, 3, 4, 6)]
    other_table = [row(2, index) for index in (0, 1, 6)]
    chunks = _deep_batch_chunks(
        [first_table[-1]],
        {},
        max_owned_units_per_batch=1,
        all_units=[*first_table, *other_table],
    )
    owned, context = chunks[0]
    assert [unit.structure_unit_id for unit in owned] == ["table-1-row-6"]
    assert [unit.structure_unit_id for unit in context] == [
        f"table-1-row-{index}" for index in range(5)
    ]

    manifest = ProtocolSectionCoverageManifest(
        manifest_id=_MANIFEST,
        protocol_version_id=_PROTOCOL,
        protocol_document_sha256="a" * 64,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:table",
        units=[*first_table, *other_table],
    )
    discovery = plan_protocol_control_discovery(manifest, max_units_per_batch=20)
    decisions = [[
        ProtocolControlDiscoveryDecision(
            structure_unit_id=unit_id,
            disposition=(
                ProtocolControlDiscoveryDisposition.CANDIDATE
                if unit_id == first_table[-1].structure_unit_id
                else ProtocolControlDiscoveryDisposition.NON_CONTROL
            ),
            rationale="前五行只供同表结构理解" if unit_id != first_table[-1].structure_unit_id else "待核对访视要求",
        )
        for unit_id in batch.target_structure_unit_ids
    ] for batch in discovery.batches]
    deep = plan_protocol_control_deep_batches_from_discovery(
        manifest, discovery, decisions, max_owned_units_per_batch=1
    )
    assert deep.batches[0].context_structure_unit_ids == [
        f"table-1-row-{index}" for index in range(5)
    ]
    assert all(
        unit_id not in deep.deep_structure_unit_ids
        for unit_id in deep.batches[0].context_structure_unit_ids
    )


def test_short_source_list_is_owned_together_without_absorbing_next_paragraph() -> None:
    units = [
        _unit(0).model_copy(update={"excerpt": "满足以下条件后方可复核："}),
        *[
            _unit(number).model_copy(update={
                "unit_kind": StructureUnitKind.LIST_ITEM, "excerpt": f"条件{number}须有记录；",
            })
            for number in range(1, 5)
        ],
        _unit(5).model_copy(update={"excerpt": "下一项独立要求须单独核对。"}),
    ]
    manifest = _manifest(6).model_copy(update={"units": units})
    discovery = plan_protocol_control_discovery(manifest, max_units_per_batch=6)
    decisions = [[ProtocolControlDiscoveryDecision(
        structure_unit_id=unit_id,
        disposition=ProtocolControlDiscoveryDisposition.CANDIDATE,
        rationale="逐条核对",
    ) for unit_id in batch.target_structure_unit_ids] for batch in discovery.batches]

    plan = plan_protocol_control_deep_batches_from_discovery(
        manifest, discovery, decisions, max_owned_units_per_batch=1,
    )
    assert [batch.owned_structure_unit_ids for batch in plan.batches] == [
        [f"unit-{number:03d}" for number in range(5)], ["unit-005"],
    ]
    assert plan.max_owned_units_per_batch == 1
    assert plan.batches[0].batch_total == 2
    publication = _build_publication_plan(manifest, plan)
    assert publication.batches[0].owned_structure_unit_ids == [
        f"unit-{number:03d}" for number in range(5)
    ]
    batch_payload = plan.batches[0].model_dump(mode="json")
    batch_payload["owned_required_action_kinds_by_structure_unit_id"] = {
        "unit-004": ["obtain_signature"],
        "unit-001": ["obtain_signature"],
    }
    stored = json.loads(json.dumps(batch_payload, sort_keys=True))
    assert ProtocolControlDispositionBatch.model_validate(stored).owned_structure_unit_ids == [
        f"unit-{number:03d}" for number in range(5)
    ]
    stored["owned_required_action_kinds_by_structure_unit_id"] = {
        "unit-not-owned": ["obtain_signature"],
    }
    with pytest.raises(ValueError, match="只能引用本批"):
        ProtocolControlDispositionBatch.model_validate(stored)


def test_source_list_does_not_jump_over_an_unowned_or_different_section_unit() -> None:
    parent = _unit(0).model_copy(update={"excerpt": "满足以下条件："})
    separator = _unit(1).model_copy(update={"excerpt": "只作结构说明。"})
    child = _unit(2).model_copy(update={"unit_kind": StructureUnitKind.LIST_ITEM, "excerpt": "须复核。"})
    groups = _deep_batch_chunks(
        [parent, child], {}, max_owned_units_per_batch=1,
        all_units=[parent, separator, child],
    )
    assert [owned[0].structure_unit_id for owned, _ in groups] == ["unit-000", "unit-002"]


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


def test_explicit_other_phase_is_covered_without_deep_review() -> None:
    manifest = _manifest(4)
    manifest = manifest.model_copy(
        update={
            "units": [
                unit.model_copy(
                    update={
                        "phase_scopes": (
                            [PhaseScope.PHASE_III]
                            if unit.structure_unit_id in {"unit-002", "unit-003"}
                            else [PhaseScope.UNKNOWN]
                        )
                    }
                )
                for unit in manifest.units
            ]
        }
    )
    discovery = plan_protocol_control_discovery(manifest, max_units_per_batch=4)
    decisions = _discovery_decisions(discovery)
    decisions[0] = [
        item.model_copy(
            update={
                "required_context_structure_unit_ids": ["unit-001", "unit-003"]
            }
        ) if item.structure_unit_id == "unit-000" else item.model_copy(
            update={"disposition": ProtocolControlDiscoveryDisposition.CANDIDATE}
        ) if item.structure_unit_id == "unit-003" else item
        for item in decisions[0]
    ]
    plan = plan_protocol_control_deep_batches_from_discovery(
        manifest, discovery, decisions
    )

    assert plan.deep_structure_unit_ids == ("unit-000",)
    assert "unit-002" in plan.non_deep_structure_unit_ids
    assert "unit-003" in plan.non_deep_structure_unit_ids
    assert next(
        item for item in plan.discovery_decisions
        if item.structure_unit_id == "unit-002"
    ).disposition == ProtocolControlDiscoveryDisposition.NON_CONTROL
    assert next(
        item for item in plan.discovery_decisions
        if item.structure_unit_id == "unit-003"
    ).disposition == ProtocolControlDiscoveryDisposition.CONTEXT_ONLY
    assert plan.batches[0].context_structure_unit_ids == ["unit-001", "unit-003"]
    assert next(
        item for item in plan.discovery_decisions
        if item.structure_unit_id == "unit-000"
    ).disposition == ProtocolControlDiscoveryDisposition.CANDIDATE
    assert [item.structure_unit_id for item in plan.discovery_decisions] == [
        item.structure_unit_id for item in manifest.units
    ]


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
    assert len(deep_prompt) < 60_000


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


def test_discovery_batch_binding_preserves_required_context_without_creating_control() -> None:
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

    decisions = bind_protocol_control_discovery_wire(wire, batch)

    assert decisions[0].disposition == ProtocolControlDiscoveryDisposition.CANDIDATE
    assert decisions[0].required_context_structure_unit_ids == ["unit-001"]
    assert decisions[1].disposition == ProtocolControlDiscoveryDisposition.CONTEXT_ONLY
    assert "原输出标为 non_control" in decisions[1].rationale


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
