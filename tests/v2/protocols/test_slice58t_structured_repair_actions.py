"""Independent regressions for structured phase-repair prompt actions."""

from __future__ import annotations

import json

import pytest

from app.agents.phase_applicability import (
    PHASE_APPLICABILITY_AGENT_WIRE_VERSION,
    PhaseApplicabilityAgentWireValidationError,
    build_phase_applicability_agent_input,
    build_phase_applicability_repair_prompt,
    hydrate_phase_applicability_agent_output,
)
from app.domain.contracts.enums import PhaseScope, StudyPhase
from app.domain.contracts.phase_applicability import (
    PhaseApplicabilityFrozenPackage,
    stable_phase_applicability_package_id,
)
from app.domain.contracts.protocol_controls import (
    ProtocolStructureUnit,
    StructureUnitKind,
)


_SHA = "a" * 64


def _unit(unit_id: str, order: int) -> ProtocolStructureUnit:
    source_ref = f"body.p{order}"
    return ProtocolStructureUnit(
        structure_unit_id=unit_id,
        source_ref=source_ref,
        member_source_refs=[source_ref],
        source_span_ids=[f"span-{unit_id}"],
        unit_kind=StructureUnitKind.PARAGRAPH,
        heading_path=["5 研究设计", "5.2 期别说明"],
        source_order=order,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.UNKNOWN],
        excerpt=f"冻结目标 {unit_id} 的原文要求待判断。",
    )


def _input():
    owned_units = [_unit("target-0", 0), _unit("target-1", 1)]
    manifest_id = "manifest:phase5-slice58t-repair-actions"
    return build_phase_applicability_agent_input(
        PhaseApplicabilityFrozenPackage(
            package_id=stable_phase_applicability_package_id(
                manifest_id,
                1,
                [unit.structure_unit_id for unit in owned_units],
            ),
            coverage_manifest_id=manifest_id,
            protocol_version_id="protocol:phase5-slice58t-repair-actions",
            protocol_document_sha256=_SHA,
            snapshot_id="snapshot:phase5-slice58t-repair-actions",
            package_ordinal=1,
            selected_phase=StudyPhase.PHASE_II,
            opposite_phase=StudyPhase.PHASE_III,
            owned_units=owned_units,
            context_units=[],
            frozen_source_span_ids=[
                unit.source_span_ids[0] for unit in owned_units
            ],
        )
    )


@pytest.mark.parametrize(
    ("problem", "required_action"),
    [
        (
            "PAIRED_RULE_FAMILY_SOURCE_IGNORED: 成对规则来源被忽略",
            "选定期别和对侧期别中指向同一具体规则标题/义务族的来源"
            "作为一组比较",
        ),
        (
            "TARGET_RELATED_SUPPORT_MISSING: 目标相关支持缺失",
            "目标自身或同一具体规则标题/同一义务族直接相关的支持来源",
        ),
        (
            "EVIDENCE_EXCERPT_NOT_VERBATIM: 证据摘录非逐字",
            "source unit excerpt 中可连续恢复的原文",
        ),
        (
            "CONTRADICTORY_FINAL_DISPOSITION: 最终处置与候选冲突",
            "让候选数组与最终处置一致",
        ),
    ],
)
def test_structured_repair_prompt_preserves_full_batch_and_target_scope(
    problem: str,
    required_action: str,
) -> None:
    agent_input = _input()
    prompt = build_phase_applicability_repair_prompt(
        agent_input,
        problem=problem,
        unit_indexes=[1],
        structure_unit_ids=["target-1"],
    )

    checklist_line = next(
        line
        for line in prompt.splitlines()
        if line.startswith("完整冻结目标清单（修复后必须逐项回显")
    )
    checklist = json.loads(checklist_line.split("：", 1)[1])
    assert checklist == [
        {"unit_index": 0, "structure_unit_id": "target-0"},
        {"unit_index": 1, "structure_unit_id": "target-1"},
    ]
    assert "本冻结包全部 target_units 的完整 v2 分组结果" in prompt
    assert "每个 target unit_index 恰好出现一次" in prompt
    assert "按升序完整返回" in prompt
    assert "逐字回显其对应的 structure_unit_id" in prompt
    assert "修复目标 unit_index：[1]" in prompt
    assert "修复目标 structure_unit_id：[\"target-1\"]" in prompt
    assert required_action in prompt
    assert "D001" not in prompt


def test_structured_repair_prompt_binds_sources_without_cross_unit_or_rewrite() -> None:
    agent_input = _input()

    paired_prompt = build_phase_applicability_repair_prompt(
        agent_input,
        problem="PAIRED_RULE_FAMILY_SOURCE_IGNORED",
        unit_indexes=[0],
    )
    assert (
        "先分别核对两侧的原文、期别范围和是否存在期别特异例外"
        in paired_prompt
    )
    assert (
        "若仍判为单一期别，必须在对侧候选中保留明确的"
        "不适用或不覆盖反证"
        in paired_prompt
    )
    assert "唯一有证据的 shared 候选" in paired_prompt

    contradictory_prompt = build_phase_applicability_repair_prompt(
        agent_input,
        problem="CONTRADICTORY_FINAL_DISPOSITION",
        unit_indexes=[0],
    )
    assert "cross_phase_shared 只能把支持两期共用的正向来源绑定到 shared 候选" in contradictory_prompt
    assert "绝不能返回空证据候选" in contradictory_prompt

    target_prompt = build_phase_applicability_repair_prompt(
        agent_input,
        problem="TARGET_RELATED_SUPPORT_MISSING",
        unit_indexes=[0],
    )
    assert (
        "不得用共同上级标题、章节邻近、普通提及、泛化研究背景或"
        "其他义务的来源"
        "冒充目标支持"
        in target_prompt
    )
    assert (
        "source_unit_indexes 与 source_span_indexes 必须来自同一条证据列出的"
        "冻结来源单元"
        in target_prompt
    )
    assert (
        "无法找到目标相关正向依据时应改为相应的反对或 unresolved 处置"
        in target_prompt
    )

    excerpt_prompt = build_phase_applicability_repair_prompt(
        agent_input,
        problem="EVIDENCE_EXCERPT_NOT_VERBATIM",
        unit_indexes=[0],
    )
    assert "只允许进行项目既有的空白规范化" in excerpt_prompt
    assert (
        "不得改写、摘要、拼接不同单元文字、补标点或凭记忆重建"
        in excerpt_prompt
    )
    assert (
        "每个 source_span_index 必须属于本证据列出的对应 source_unit_index"
        in excerpt_prompt
    )
    assert "来源不足时返回 unresolved" in excerpt_prompt


def test_gate_repair_reports_every_affected_target_in_one_round() -> None:
    def unit(
        unit_id: str,
        order: int,
        excerpt: str,
        *,
        scope: PhaseScope,
        heading_path: list[str],
    ) -> ProtocolStructureUnit:
        source_ref = f"body.p{order}"
        return ProtocolStructureUnit(
            structure_unit_id=unit_id,
            source_ref=source_ref,
            member_source_refs=[source_ref],
            source_span_ids=[f"span-{unit_id}"],
            unit_kind=StructureUnitKind.PARAGRAPH,
            heading_path=heading_path,
            source_order=order,
            study_phase=StudyPhase.PHASE_II,
            phase_scopes=[scope],
            excerpt=excerpt,
        )

    owned = [
        unit(
            "target-0",
            0,
            "签署知情同意书。",
            scope=PhaseScope.UNKNOWN,
            heading_path=["研究人群", "入选标准"],
        ),
        unit(
            "target-1",
            1,
            "年龄为18至75周岁。",
            scope=PhaseScope.UNKNOWN,
            heading_path=["研究人群", "入选标准"],
        ),
    ]
    context = [
        unit(
            "phase-ii",
            2,
            "Ⅱ期参与者必须符合所有入选标准。",
            scope=PhaseScope.PHASE_II,
            heading_path=["研究设计", "Ⅱ期总体设计"],
        ),
        unit(
            "phase-iii",
            3,
            "Ⅲ期参与者必须符合所有入选标准。",
            scope=PhaseScope.PHASE_III,
            heading_path=["研究设计", "Ⅲ期总体设计"],
        ),
    ]
    manifest_id = "manifest:phase5-slice58t-aggregate-gate"
    frozen_source_span_ids = sorted(
        item.source_span_ids[0] for item in [*owned, *context]
    )
    agent_input = build_phase_applicability_agent_input(
        PhaseApplicabilityFrozenPackage(
            package_id=stable_phase_applicability_package_id(
                manifest_id,
                1,
                [item.structure_unit_id for item in owned],
            ),
            coverage_manifest_id=manifest_id,
            protocol_version_id="protocol:phase5-slice58t-aggregate-gate",
            protocol_document_sha256=_SHA,
            snapshot_id="snapshot:phase5-slice58t-aggregate-gate",
            package_ordinal=1,
            selected_phase=StudyPhase.PHASE_II,
            opposite_phase=StudyPhase.PHASE_III,
            owned_units=owned,
            context_units=context,
            frozen_source_span_ids=frozen_source_span_ids,
        )
    )
    results = []
    for index, target in enumerate(owned):
        results.append(
            {
                "unit_index": index,
                "structure_unit_id": target.structure_unit_id,
                "evidence": [
                    {
                        "polarity": "supports",
                        "source_unit_indexes": [index],
                        "source_span_indexes": [
                            frozen_source_span_ids.index(target.source_span_ids[0])
                        ],
                        "excerpt": target.excerpt,
                        "rationale": "目标原文直接支持纳入所选期别。",
                    }
                ],
                "candidates": [
                    {
                        "scope": "phase_ii",
                        "supporting_evidence_indexes": [0],
                        "opposing_evidence_indexes": [],
                        "unresolved_evidence_indexes": [],
                    }
                ],
                "final_disposition": "selected_phase_applicable",
                "rationale": "目标原文直接支持纳入所选期别。",
            }
        )

    with pytest.raises(PhaseApplicabilityAgentWireValidationError) as captured:
        hydrate_phase_applicability_agent_output(
            json.dumps(
                {
                    "wire_version": PHASE_APPLICABILITY_AGENT_WIRE_VERSION,
                    "results": results,
                },
                ensure_ascii=False,
            ),
            agent_input,
        )

    assert captured.value.unit_indexes == (0, 1)
    assert captured.value.structure_unit_ids == ("target-0", "target-1")
    assert str(captured.value).count("PAIRED_RULE_FAMILY_SOURCE_IGNORED") >= 2
