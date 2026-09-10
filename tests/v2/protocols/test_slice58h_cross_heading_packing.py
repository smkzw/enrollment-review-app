from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import median

import pytest
from pydantic import ValidationError

from app.agents.phase_applicability import (
    build_phase_applicability_agent_input,
    build_phase_applicability_agent_prompt,
)
from app.domain.contracts.enums import PhaseScope, StudyPhase
from app.domain.contracts.protocol_controls import (
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    StructureUnitKind,
    TableCellContext,
)
from app.protocols.full_protocol_coverage import (
    build_resolved_full_protocol_coverage_view,
)
from app.protocols.phase_applicability_planning import (
    PHASE_APPLICABILITY_DEFAULT_BATCH_PACKING_POLICY,
    PHASE_APPLICABILITY_PLAN_V1_VERSION,
    PHASE_APPLICABILITY_PLAN_V2_VERSION,
    PHASE_APPLICABILITY_SAME_HEADING_BATCH_PACKING_POLICY,
    PhaseApplicabilityFrozenPlan,
    plan_phase_applicability_batches,
)
from app.services.phase_applicability_execution import (
    PhaseApplicabilityExecutionError,
    PhaseApplicabilityExecutionState,
    PhaseApplicabilityExecutionService,
    PhaseApplicabilityExecutionStore,
)


_SHA = "a" * 64
_WORKTREE = Path(__file__).resolve().parents[3]
_D001_MANIFEST = _WORKTREE / (
    ".trellis/tasks/08-22-phase5-clinical-facts-profile/research/"
    "d001-ii-phase-closure/coverage_manifest.json"
)
_D001_HISTORICAL_PLAN = _WORKTREE / (
    ".trellis/tasks/08-22-phase5-clinical-facts-profile/research/"
    "d001-ii-phase-closure/frozen_phase_plan.json"
)
_D001_HISTORICAL_EXECUTION = _WORKTREE / (
    ".trellis/tasks/08-22-phase5-clinical-facts-profile/research/"
    "d001-ii-phase-closure/execution/"
    "d001-ii-phase-closure-20260825-slice58e.json"
)
_D001_PROTOCOL_COPY = _WORKTREE / (
    "artifacts/phase5-acceptance/20260823/isolated-inputs/d001/protocol/"
    "test-D001项目/CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx"
)


def _unit(
    unit_id: str,
    order: int,
    heading_path: list[str],
    *,
    scope: PhaseScope = PhaseScope.UNKNOWN,
    table: bool = False,
    excerpt: str | None = None,
) -> ProtocolStructureUnit:
    source_ref = f"body.p{order}"
    span_id = f"span-{unit_id}"
    table_context = None
    if table:
        table_path = (1, order, 0, 0)
        table_context = TableCellContext(
            table_path=table_path,
            row_index=0,
            column_index=0,
            member_cell_paths=[table_path],
            row_headers=["访视项目"],
            column_headers=["筛选期", "基线"],
        )
    return ProtocolStructureUnit(
        structure_unit_id=unit_id,
        source_ref=source_ref,
        member_source_refs=[source_ref],
        source_span_ids=[span_id],
        unit_kind=StructureUnitKind.TABLE_ROW if table else StructureUnitKind.PARAGRAPH,
        heading_path=heading_path,
        table_context=table_context,
        source_order=order,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[scope],
        excerpt=excerpt or f"{unit_id} 原文内容用于本期别适用性核对。",
    )


def _manifest(units: list[ProtocolStructureUnit]) -> ProtocolSectionCoverageManifest:
    return ProtocolSectionCoverageManifest(
        manifest_id="manifest:slice58h-packing",
        protocol_version_id="protocol:slice58h-packing",
        protocol_document_sha256=_SHA,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:slice58h-packing",
        units=units,
    )


def _owned_ids(plan) -> list[str]:
    return [
        unit.structure_unit_id
        for package in plan.packages
        for unit in package.owned_units
    ]


def test_adjacent_small_heading_runs_pack_but_unrelated_and_table_runs_do_not() -> None:
    units = [
        _unit("a-1", 0, ["5 研究设计", "5.1 小章节甲"]),
        _unit("a-2", 1, ["5 研究设计", "5.1 小章节甲"]),
        _unit("b-1", 2, ["5 研究设计", "5.2 小章节乙"]),
        _unit("b-2", 3, ["5 研究设计", "5.2 小章节乙"]),
        _unit("explicit", 4, ["5 研究设计", "5.3 明确期别"], scope=PhaseScope.PHASE_II),
        _unit("unrelated-1", 5, ["6 安全性", "6.1 小章节丙"]),
        _unit("unrelated-2", 6, ["7 统计", "7.1 小章节丁"]),
        _unit("table-1", 7, ["5 研究设计", "5.4 表格章节"], table=True),
        _unit("table-2", 8, ["5 研究设计", "5.4 表格章节"], table=True),
        _unit("after-table", 9, ["5 研究设计", "5.5 表格后章节"]),
    ]
    manifest = _manifest(units)

    packed = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=12,
        context_radius=0,
        batch_packing_policy=PHASE_APPLICABILITY_DEFAULT_BATCH_PACKING_POLICY,
    )
    same_heading = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=12,
        context_radius=0,
        batch_packing_policy=PHASE_APPLICABILITY_SAME_HEADING_BATCH_PACKING_POLICY,
    )

    assert packed.expected_structure_unit_ids == [
        "a-1",
        "a-2",
        "b-1",
        "b-2",
        "unrelated-1",
        "unrelated-2",
        "table-1",
        "table-2",
        "after-table",
    ]
    assert _owned_ids(packed) == packed.expected_structure_unit_ids
    assert packed.packages[0].owned_structure_unit_ids == (
        "a-1",
        "a-2",
        "b-1",
        "b-2",
    )
    assert all(
        not {"unrelated-1", "unrelated-2"} <= set(package.owned_structure_unit_ids)
        for package in packed.packages
    )
    assert all(
        not {"table-1", "table-2", "after-table"}
        <= set(package.owned_structure_unit_ids)
        for package in packed.packages
    )
    assert all(len(package.owned_units) <= 12 for package in packed.packages)
    assert len(packed.packages) < len(same_heading.packages)
    assert _owned_ids(same_heading) == _owned_ids(packed)
    assert packed.plan_id != same_heading.plan_id


def test_default_packing_flushes_before_splitting_next_heading_run() -> None:
    first_heading = ["5 研究设计", "5.1 第一小节"]
    second_heading = ["5 研究设计", "5.2 第二小节"]
    units = [
        _unit("first-heading", 0, first_heading, scope=PhaseScope.PHASE_II),
        *[_unit(f"first-{index}", index, first_heading) for index in range(1, 11)],
        _unit("second-heading", 11, second_heading, scope=PhaseScope.PHASE_II),
        *[_unit(f"second-{index}", index, second_heading) for index in range(12, 16)],
    ]

    packed = plan_phase_applicability_batches(
        _manifest(units),
        max_owned_units_per_batch=12,
        context_radius=1,
        batch_packing_policy=PHASE_APPLICABILITY_DEFAULT_BATCH_PACKING_POLICY,
    )

    assert [len(package.owned_units) for package in packed.packages] == [10, 4]
    assert [package.owned_structure_unit_ids for package in packed.packages] == [
        tuple(f"first-{index}" for index in range(1, 11)),
        tuple(f"second-{index}" for index in range(12, 16)),
    ]
    first_context_ids = {
        unit.structure_unit_id for unit in packed.packages[0].context_units
    }
    second_context_ids = {
        unit.structure_unit_id for unit in packed.packages[1].context_units
    }
    assert "first-heading" in first_context_ids
    assert "second-heading" in second_context_ids


def test_rule_package_recovers_paired_phase_design_references_without_unrelated_source() -> (
    None
):
    design_heading = ["5 研究设计"]
    manifest = _manifest(
        [
            _unit(
                "phase-ii-rule-reference",
                0,
                design_heading,
                scope=PhaseScope.PHASE_II,
                excerpt="Ⅱ期参与者须符合所有入选标准且不符合任何排除标准。",
            ),
            _unit(
                "phase-iii-rule-reference",
                1,
                design_heading,
                scope=PhaseScope.PHASE_III,
                excerpt="Ⅲ期参与者须符合所有入选标准且不符合任何排除标准。",
            ),
            _unit(
                "unrelated-phase-source",
                2,
                design_heading,
                scope=PhaseScope.PHASE_III,
                excerpt="Ⅲ期采用双盲安慰剂对照设计。",
            ),
            _unit(
                "target-exclusion",
                3,
                ["6 研究人群", "6.2 排除标准"],
            ),
        ]
    )

    plan = plan_phase_applicability_batches(manifest, context_radius=0)
    package = next(
        item
        for item in plan.packages
        if "target-exclusion" in item.owned_structure_unit_ids
    )
    context_ids = {unit.structure_unit_id for unit in package.context_units}

    assert {
        "phase-ii-rule-reference",
        "phase-iii-rule-reference",
    } <= context_ids
    assert "unrelated-phase-source" not in context_ids


def test_named_phase_heading_freezes_its_operational_body_for_comparison() -> None:
    phase_ii_path = [
        "研究评估和程序",
        "访视安排",
        "Ⅱ期临床研究阶段",
        "计划外访视/检查",
    ]
    phase_iii_path = [
        "研究评估和程序",
        "访视安排",
        "Ⅲ期临床研究阶段",
        "计划外访视/检查",
    ]
    unrelated_path = [
        "研究评估和程序",
        "访视安排",
        "Ⅱ期临床研究阶段",
        "筛选期",
    ]
    manifest = _manifest(
        [
            _unit(
                "target-note",
                0,
                ["方案摘要", "研究流程表"],
                excerpt="计划外访视可由研究者按临床需要安排。",
            ),
            _unit(
                "phase-ii-heading",
                1,
                phase_ii_path,
                scope=PhaseScope.PHASE_II,
                excerpt="计划外访视/检查",
            ),
            _unit(
                "phase-ii-body",
                2,
                phase_ii_path,
                scope=PhaseScope.PHASE_II,
                excerpt="研究者可安排计划外访视并记录原因。",
            ),
            _unit(
                "phase-iii-heading",
                3,
                phase_iii_path,
                scope=PhaseScope.PHASE_III,
                excerpt="计划外访视/检查",
            ),
            _unit(
                "phase-iii-body",
                4,
                phase_iii_path,
                scope=PhaseScope.PHASE_III,
                excerpt="与Ⅱ期一致，详见对应章节。",
            ),
            _unit(
                "unrelated-heading",
                5,
                unrelated_path,
                scope=PhaseScope.PHASE_II,
                excerpt="筛选期",
            ),
            _unit(
                "unrelated-body",
                6,
                unrelated_path,
                scope=PhaseScope.PHASE_II,
                excerpt="筛选期完成其他检查。",
            ),
        ]
    )

    package = plan_phase_applicability_batches(
        manifest,
        context_radius=0,
    ).packages[0]
    context_ids = {unit.structure_unit_id for unit in package.context_units}

    assert {
        "phase-ii-heading",
        "phase-ii-body",
        "phase-iii-heading",
        "phase-iii-body",
    } <= context_ids
    assert "unrelated-heading" in context_ids
    assert "unrelated-body" not in context_ids


def test_package_keeps_complete_exact_clinical_subsection_as_read_only_context() -> (
    None
):
    section = ["研究评估和程序", "研究期间的检查和评估", "实验室检查"]
    sibling = ["研究评估和程序", "研究期间的检查和评估", "病毒学检查"]
    units = [
        _unit("lab-heading", 0, section, excerpt="表 6 实验室检查"),
        _unit("lab-body", 1, section),
        _unit("lab-condition", 2, section),
        _unit("virus-heading", 3, sibling),
        _unit("virus-body", 4, sibling),
    ]
    package = plan_phase_applicability_batches(
        _manifest(units),
        max_owned_units_per_batch=2,
        context_radius=0,
        batch_packing_policy=PHASE_APPLICABILITY_SAME_HEADING_BATCH_PACKING_POLICY,
    ).packages[0]
    context_ids = {unit.structure_unit_id for unit in package.context_units}

    assert package.owned_structure_unit_ids == ("lab-heading", "lab-body")
    assert "lab-condition" in context_ids
    assert "virus-heading" not in context_ids
    assert "virus-body" not in context_ids


def test_shallow_appendix_container_is_not_treated_as_one_clinical_subsection() -> (
    None
):
    units = [
        _unit("appendix-intro", 0, ["附录"]),
        _unit("appendix-table", 1, ["附录"], table=True),
        _unit("other-appendix", 2, ["附录"]),
    ]
    package = next(
        package
        for package in plan_phase_applicability_batches(
            _manifest(units),
            max_owned_units_per_batch=1,
            context_radius=0,
            batch_packing_policy=PHASE_APPLICABILITY_SAME_HEADING_BATCH_PACKING_POLICY,
        ).packages
        if "appendix-table" in package.owned_structure_unit_ids
    )
    context_ids = {unit.structure_unit_id for unit in package.context_units}

    assert "appendix-intro" not in context_ids
    assert "other-appendix" not in context_ids


def test_visit_policy_is_not_broadcast_to_an_unrelated_package() -> None:
    units = [
        _unit(
            "visit-heading",
            0,
            ["方案摘要", "研究流程表"],
            excerpt="研究流程表",
        ),
        _unit(
            "visit-policy",
            1,
            ["方案摘要", "研究流程表"],
            excerpt=(
                "筛选访视和D1间隔不超过7天时可与基线合并，"
                "以给药前最近一次结果作为基线值。"
            ),
        ),
        _unit(
            "unrelated-flow-note",
            2,
            ["方案摘要", "研究流程表"],
            excerpt="采集人口学资料。",
        ),
        _unit("target", 3, ["研究评估", "实验室检查"]),
    ]
    package = next(
        package
        for package in plan_phase_applicability_batches(
            _manifest(units), context_radius=0
        ).packages
        if "target" in package.owned_structure_unit_ids
    )
    context_ids = {unit.structure_unit_id for unit in package.context_units}

    assert "visit-heading" in context_ids
    assert "visit-policy" not in context_ids
    assert "unrelated-flow-note" not in context_ids


def test_visit_flow_parent_is_not_broadcast_when_structured_tables_are_authority() -> (
    None
):
    units = [
        _unit(
            "visit-heading",
            0,
            ["方案摘要", "研究流程表"],
            excerpt="研究流程表",
        ),
        _unit(
            "phase-ii-table",
            1,
            ["方案摘要", "研究流程表", "表 1 II期临床研究阶段流程表"],
            table=True,
        ),
        _unit(
            "phase-iii-table",
            2,
            ["方案摘要", "研究流程表", "表 2 III期临床研究阶段流程表"],
            table=True,
        ),
        _unit("target", 3, ["研究评估", "实验室检查"]),
    ]
    package = next(
        package
        for package in plan_phase_applicability_batches(
            _manifest(units), context_radius=0
        ).packages
        if "target" in package.owned_structure_unit_ids
    )
    context_ids = {unit.structure_unit_id for unit in package.context_units}

    assert "visit-heading" not in context_ids


def test_closing_heading_after_explicit_phase_segment_is_read_only_context() -> None:
    hypothesis = ["统计学考虑", "统计假设"]
    correction = [*hypothesis, "多重性校正"]
    sample_size = ["统计学考虑", "样本量计算"]
    units = [
        _unit("hypothesis", 0, hypothesis, excerpt="统计假设"),
        _unit(
            "phase-ii-body",
            1,
            hypothesis,
            scope=PhaseScope.PHASE_II,
            excerpt="Ⅱ期不做正式检验假设。",
        ),
        _unit(
            "phase-iii-lead-in",
            2,
            hypothesis,
            scope=PhaseScope.PHASE_III,
            excerpt="Ⅲ期采用如下假设检验：",
        ),
        _unit(
            "phase-iii-child-heading",
            3,
            correction,
            scope=PhaseScope.PHASE_III,
            excerpt="多重性校正",
        ),
        _unit(
            "phase-iii-child-body",
            4,
            correction,
            scope=PhaseScope.PHASE_III,
            excerpt="整体 alpha 水平保持不变。",
        ),
        _unit("sample-size-heading", 5, sample_size, excerpt="样本量计算"),
        _unit("sample-size-body", 6, sample_size),
    ]

    first = plan_phase_applicability_batches(
        _manifest(units),
        context_radius=0,
    ).packages[0]
    context_ids = {unit.structure_unit_id for unit in first.context_units}

    assert first.owned_structure_unit_ids == ("hypothesis",)
    assert "sample-size-heading" in context_ids
    assert "sample-size-body" not in context_ids


def test_packing_identity_round_trip_and_execution_resume_include_policy(
    tmp_path: Path,
) -> None:
    manifest = _manifest(
        [
            _unit("left", 0, ["1 总则", "1.1 左章节"]),
            _unit("right", 1, ["1 总则", "1.2 右章节"]),
        ]
    )
    packed = plan_phase_applicability_batches(
        manifest,
        context_radius=0,
        batch_packing_policy=PHASE_APPLICABILITY_DEFAULT_BATCH_PACKING_POLICY,
    )
    restored = type(packed).model_validate(packed.model_dump(mode="json"))
    repeated = plan_phase_applicability_batches(
        manifest,
        context_radius=0,
        batch_packing_policy=PHASE_APPLICABILITY_DEFAULT_BATCH_PACKING_POLICY,
    )
    assert restored == packed
    assert repeated.plan_id == packed.plan_id
    assert [item.package_id for item in repeated.packages] == [
        item.package_id for item in packed.packages
    ]

    service = PhaseApplicabilityExecutionService(
        PhaseApplicabilityExecutionStore(tmp_path / "runs")
    )
    prepared = service.prepare(
        run_id="packing-resume",
        coverage_manifest=manifest,
        plan=packed,
    )
    assert prepared.plan.batch_packing_policy == (
        PHASE_APPLICABILITY_DEFAULT_BATCH_PACKING_POLICY
    )
    assert prepared.plan.plan_id == packed.plan_id

    same_heading = plan_phase_applicability_batches(
        manifest,
        context_radius=0,
        batch_packing_policy=PHASE_APPLICABILITY_SAME_HEADING_BATCH_PACKING_POLICY,
    )
    with pytest.raises(
        PhaseApplicabilityExecutionError, match="EXECUTION_INPUT_CONFLICT"
    ):
        service.prepare(
            run_id="packing-resume",
            coverage_manifest=manifest,
            plan=same_heading,
        )


@pytest.mark.skipif(
    not _D001_HISTORICAL_PLAN.is_file() or not _D001_HISTORICAL_EXECUTION.is_file(),
    reason="工作区内 D001 历史冻结计划或 execution state 缺失",
)
def test_historical_v1_plan_and_execution_state_remain_readable() -> None:
    plan_before = _file_snapshot(_D001_HISTORICAL_PLAN)
    execution_before = _file_snapshot(_D001_HISTORICAL_EXECUTION)
    plan_payload = json.loads(_D001_HISTORICAL_PLAN.read_text(encoding="utf-8"))
    historical_plan = PhaseApplicabilityFrozenPlan.model_validate(plan_payload)

    assert plan_payload["schema_version"] == PHASE_APPLICABILITY_PLAN_V1_VERSION
    assert "batch_packing_policy" not in plan_payload
    assert historical_plan.schema_version == PHASE_APPLICABILITY_PLAN_V1_VERSION
    assert historical_plan.batch_packing_policy == (
        PHASE_APPLICABILITY_SAME_HEADING_BATCH_PACKING_POLICY
    )
    assert len(historical_plan.packages) == 217
    assert historical_plan.plan_id == "papl-a8071fd5b33199e806bda00e"

    invalid_v1 = {
        **plan_payload,
        "batch_packing_policy": PHASE_APPLICABILITY_DEFAULT_BATCH_PACKING_POLICY,
    }
    with pytest.raises(ValidationError, match="v1 冻结计划不得使用"):
        PhaseApplicabilityFrozenPlan.model_validate(invalid_v1)

    state_payload = json.loads(_D001_HISTORICAL_EXECUTION.read_text(encoding="utf-8"))
    state = PhaseApplicabilityExecutionState.model_validate(state_payload)
    assert state.plan.schema_version == PHASE_APPLICABILITY_PLAN_V1_VERSION
    assert state.plan.plan_id == historical_plan.plan_id
    assert state.plan.batch_packing_policy == (
        PHASE_APPLICABILITY_SAME_HEADING_BATCH_PACKING_POLICY
    )
    assert len(state.batches) == 217

    current_plan = plan_phase_applicability_batches(
        state.coverage_manifest,
        max_owned_units_per_batch=12,
        context_radius=1,
        batch_packing_policy=PHASE_APPLICABILITY_DEFAULT_BATCH_PACKING_POLICY,
    )
    assert current_plan.schema_version == PHASE_APPLICABILITY_PLAN_V2_VERSION
    assert len(current_plan.packages) == 137
    assert current_plan.plan_id != state.plan.plan_id
    v2_without_policy = current_plan.model_dump(mode="json")
    v2_without_policy.pop("batch_packing_policy")
    with pytest.raises(ValidationError):
        PhaseApplicabilityFrozenPlan.model_validate(v2_without_policy)
    assert _file_snapshot(_D001_HISTORICAL_PLAN) == plan_before
    assert _file_snapshot(_D001_HISTORICAL_EXECUTION) == execution_before


def _file_snapshot(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns


def _prompt_metrics(plan) -> dict[str, float | int]:
    prompt_lengths: list[int] = []
    context_counts: list[int] = []
    rendered_counts: list[int] = []
    for package in plan.packages:
        agent_input = build_phase_applicability_agent_input(package)
        prompt = build_phase_applicability_agent_prompt(agent_input)
        prompt_lengths.append(len(prompt))
        context_counts.append(len(package.context_units))

        projection = json.loads(
            prompt.split("本次冻结输入：", 1)[1].split("\n\n请按", 1)[0]
        )
        rendered_units = [
            *projection["target_units"],
            *projection["context_units"],
        ]
        rendered_ids = [item["structure_unit_id"] for item in rendered_units]
        assert rendered_ids == list(package.all_structure_unit_ids)
        assert len(rendered_ids) == len(set(rendered_ids))
        assert len(rendered_units) == len(package.all_units)
        assert [item["unit_index"] for item in rendered_units] == list(
            range(len(package.all_units))
        )
        assert all(
            set(packet) == {"kind", "source_unit_indexes", "source_span_indexes"}
            for packet in projection["context_packets"]
        )
        assert all(
            set(packet["source_unit_indexes"]) <= set(range(len(package.all_units)))
            for packet in projection["context_packets"]
        )
        rendered_counts.append(len(rendered_units))

    return {
        "prompt_total": sum(prompt_lengths),
        "prompt_min": min(prompt_lengths),
        "prompt_median": median(prompt_lengths),
        "prompt_max": max(prompt_lengths),
        "context_total": sum(context_counts),
        "context_max": max(context_counts),
        "rendered_total": sum(rendered_counts),
    }


@pytest.mark.skipif(
    not _D001_MANIFEST.is_file(), reason="工作区内 D001 II 冻结清单缺失"
)
def test_real_d001_ii_packing_reduces_calls_without_prompt_or_source_regression(
    tmp_path: Path,
) -> None:
    manifest = ProtocolSectionCoverageManifest.model_validate(
        json.loads(_D001_MANIFEST.read_text(encoding="utf-8"))
    )
    assert manifest.manifest_id == "d001-ii-phase-closure-20260825-slice58e-manifest"
    assert manifest.protocol_version_id == "D001-02-002:v1.0:phase-ii"
    assert manifest.protocol_document_sha256 == (
        "362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98"
    )
    assert manifest.snapshot_id == "d001-ii-phase-closure-20260825-slice58e-snapshot"
    assert len(manifest.units) == 1840

    before = (
        _file_snapshot(_D001_PROTOCOL_COPY) if _D001_PROTOCOL_COPY.is_file() else None
    )
    if before is not None:
        assert before[0] == manifest.protocol_document_sha256

    baseline = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=12,
        context_radius=1,
        batch_packing_policy=PHASE_APPLICABILITY_SAME_HEADING_BATCH_PACKING_POLICY,
    )
    packed = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=12,
        context_radius=1,
        batch_packing_policy=PHASE_APPLICABILITY_DEFAULT_BATCH_PACKING_POLICY,
    )

    assert len(baseline.expected_structure_unit_ids) == 1298
    assert packed.expected_structure_unit_ids == baseline.expected_structure_unit_ids
    assert len(baseline.packages) == 217
    assert len(packed.packages) == 137
    assert len(packed.packages) < len(baseline.packages)
    assert all(len(package.owned_units) <= 12 for package in packed.packages)
    assert _owned_ids(packed) == packed.expected_structure_unit_ids
    assert len({package.package_id for package in packed.packages}) == len(
        packed.packages
    )

    manifest_ids = {unit.structure_unit_id for unit in manifest.units}
    for package in packed.packages:
        owned_ids = set(package.owned_structure_unit_ids)
        context_ids = {unit.structure_unit_id for unit in package.context_units}
        assert owned_ids <= manifest_ids
        assert context_ids <= manifest_ids
        assert not owned_ids & context_ids
        assert package.coverage_manifest_id == manifest.manifest_id
        assert package.protocol_version_id == manifest.protocol_version_id
        assert package.protocol_document_sha256 == manifest.protocol_document_sha256
        assert package.snapshot_id == manifest.snapshot_id
        assert package.frozen_source_span_ids == sorted(
            {span_id for unit in package.all_units for span_id in unit.source_span_ids}
        )

    baseline_metrics = _prompt_metrics(baseline)
    packed_metrics = _prompt_metrics(packed)
    assert packed_metrics == {
        "prompt_total": 4857259,
        "prompt_min": 23510,
        "prompt_median": 27986,
        "prompt_max": 122695,
        "context_total": 7607,
        "context_max": 197,
        "rendered_total": 8905,
    }
    schedule_note_package = packed.packages[35]
    assert schedule_note_package.package_ordinal == 36
    assert {"body.p932", "body.p979"} <= {
        unit.source_ref for unit in schedule_note_package.context_units
    }
    assert packed_metrics["context_total"] < baseline_metrics["context_total"]
    assert packed_metrics["context_max"] <= baseline_metrics["context_max"]
    assert packed_metrics["prompt_total"] < baseline_metrics["prompt_total"]
    assert packed_metrics["prompt_max"] <= baseline_metrics["prompt_max"]
    assert packed_metrics["rendered_total"] == sum(
        len(package.all_units) for package in packed.packages
    )

    service = PhaseApplicabilityExecutionService(
        PhaseApplicabilityExecutionStore(tmp_path / "runs")
    )
    prepared = service.prepare(
        run_id="d001-scale-packing",
        coverage_manifest=manifest,
        plan=packed,
    )
    reloaded = service.store.load("d001-scale-packing")
    assert prepared.status == "planned"
    assert reloaded.plan.plan_id == packed.plan_id
    assert reloaded.plan.batch_packing_policy == (
        PHASE_APPLICABILITY_DEFAULT_BATCH_PACKING_POLICY
    )
    assert len(reloaded.batches) == len(packed.packages)
    assert [item.package_id for item in reloaded.batches] == [
        item.package_id for item in packed.packages
    ]

    # No semantic outputs have been supplied in this scale-only regression;
    # publication must therefore remain closed rather than infer completeness.
    view = build_resolved_full_protocol_coverage_view(manifest, packed, ())
    assert view.accepted is False
    assert view.claims_full_coverage is False
    assert view.pending_structure_unit_ids == tuple(packed.expected_structure_unit_ids)

    if before is not None:
        assert _file_snapshot(_D001_PROTOCOL_COPY) == before
