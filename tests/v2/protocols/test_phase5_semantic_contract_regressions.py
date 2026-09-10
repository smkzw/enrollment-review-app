"""Regression tests for Phase 5.8 semantic phase-contract failures.

These tests deliberately exercise the provider wire, same-session repair loop,
and the current deterministic gate as separate boundaries.  The final test
replays the local five-package D001 checkpoint as evidence only; it never
rewrites the checkpoint or any protocol source.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.phase_applicability import (
    PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION,
    PhaseApplicabilityAgentResponse,
    PhaseApplicabilityAgentRunner,
    PhaseApplicabilityAgentWireValidationError,
    build_phase_applicability_agent_input,
    parse_phase_applicability_agent_wire_v2,
    wire_to_phase_applicability_resolution_draft,
)
from app.domain.contracts.enums import PhaseScope, StudyPhase
from app.domain.contracts.phase_applicability import (
    PhaseApplicabilityDisposition,
    PhaseApplicabilityFrozenPackage,
    stable_phase_applicability_package_id,
)
from app.domain.contracts.protocol_controls import (
    ProtocolStructureUnit,
    StructureUnitKind,
)
from app.protocols.phase_applicability import (
    check_phase_applicability_resolution,
    hydrate_phase_applicability_resolution,
)
from app.services.phase_applicability_execution import (
    PhaseApplicabilityExecutionState,
)


_SHA = "a" * 64
_OLD_FIVE_PACKAGE_CHECKPOINT = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "phase5-slice58r2-d001-five-package-semantic-validation-20260827"
    / "execution"
    / "d001-ii-phase-closure-20260827-slice58r2-5pkg.json"
)


def _unit(
    unit_id: str,
    order: int,
    *,
    scope: PhaseScope = PhaseScope.UNKNOWN,
    heading_path: list[str] | None = None,
    excerpt: str | None = None,
) -> ProtocolStructureUnit:
    source_ref = f"body.p{order}"
    return ProtocolStructureUnit(
        structure_unit_id=unit_id,
        source_ref=source_ref,
        member_source_refs=[source_ref],
        source_span_ids=[f"span-{unit_id}"],
        unit_kind=StructureUnitKind.PARAGRAPH,
        heading_path=heading_path or ["5 研究设计", "5.2 期别说明"],
        source_order=order,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[scope],
        excerpt=excerpt or f"来源 {unit_id}：本条需要判断研究期别。",
    )


def _package(
    owned_units: list[ProtocolStructureUnit] | None = None,
    context_units: list[ProtocolStructureUnit] | None = None,
) -> PhaseApplicabilityFrozenPackage:
    owned = owned_units or [
        _unit("target-0", 0, excerpt="选定期别的研究要求。"),
        _unit("target-1", 1, excerpt="另一条待判断的研究要求。"),
        _unit("target-2", 2, excerpt="第三条待判断的研究要求。"),
    ]
    context = context_units or []
    spans = sorted(
        {
            span_id
            for unit in [*owned, *context]
            for span_id in unit.source_span_ids
        }
    )
    manifest_id = "manifest:phase5-semantic-regressions"
    return PhaseApplicabilityFrozenPackage(
        package_id=stable_phase_applicability_package_id(
            manifest_id,
            1,
            [unit.structure_unit_id for unit in owned],
        ),
        coverage_manifest_id=manifest_id,
        protocol_version_id="protocol:phase5-semantic-regressions",
        protocol_document_sha256=_SHA,
        snapshot_id="snapshot:phase5-semantic-regressions",
        package_ordinal=1,
        selected_phase=StudyPhase.PHASE_II,
        opposite_phase=StudyPhase.PHASE_III,
        owned_units=owned,
        context_units=context,
        frozen_source_span_ids=spans,
    )


def _v2_payload(
    package: PhaseApplicabilityFrozenPackage,
    *,
    unit_indexes: list[int] | None = None,
    invalid_scope_index: int | None = None,
    invalid_scope: str = "unknown",
    unresolved: bool = False,
) -> str:
    """Build a small provider payload without bypassing wire validation."""

    indexes = (
        list(range(len(package.owned_units)))
        if unit_indexes is None
        else list(unit_indexes)
    )
    groups = []
    for unit_index in indexes:
        unit = package.owned_units[unit_index]
        span_index = package.frozen_source_span_ids.index(unit.source_span_ids[0])
        evidence_polarity = "unresolved" if unresolved else "supports"
        scope = (
            invalid_scope
            if invalid_scope_index == unit_index
            else "phase_ii"
        )
        candidate = {
            "scope": scope,
            "supporting_evidence_indexes": [] if unresolved else [0],
            "opposing_evidence_indexes": [],
            "unresolved_evidence_indexes": [0] if unresolved else [],
        }
        groups.append(
            {
                "unit_indexes": [unit_index],
                "structure_unit_ids": [unit.structure_unit_id],
                "evidence": [
                    {
                        "polarity": evidence_polarity,
                        "source_unit_indexes": [unit_index],
                        "source_span_indexes": [span_index],
                        "excerpt": unit.excerpt,
                        "rationale": "原文直接提供该目标的期别判断依据",
                    }
                ],
                "candidates": [candidate],
                "final_disposition": (
                    PhaseApplicabilityDisposition.UNRESOLVED.value
                    if unresolved
                    else PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE.value
                ),
                "rationale": (
                    "来源不足，当前结论仍待确认"
                    if unresolved
                    else "原文直接支持选定期别适用"
                ),
                "unresolved_reason": (
                    "缺少足够的期别来源，仍待确认" if unresolved else None
                ),
            }
        )
    return json.dumps(
        {
            "wire_version": PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION,
            "groups": groups,
        },
        ensure_ascii=False,
    )


class _QueueTransport:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.start_calls = 0
        self.continue_calls = 0
        self.prompts: list[tuple[str, str]] = []

    def start(self, *, prompt: str) -> PhaseApplicabilityAgentResponse:
        self.start_calls += 1
        session_id = f"phase-regression-session-{self.start_calls}"
        self.prompts.append(("start", prompt))
        return PhaseApplicabilityAgentResponse(
            session_id=session_id,
            text=self.responses.pop(0),
        )

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
    ) -> PhaseApplicabilityAgentResponse:
        self.continue_calls += 1
        self.prompts.append(("continue", prompt))
        return PhaseApplicabilityAgentResponse(
            session_id=session_id,
            text=self.responses.pop(0),
        )


@pytest.mark.parametrize("scope", ["unknown", "mixed"])
def test_input_unknown_or_mixed_is_never_an_agent_candidate_scope(scope: str) -> None:
    package = _package()
    payload = _v2_payload(
        package,
        invalid_scope_index=0,
        invalid_scope=scope,
        unresolved=True,
    )

    with pytest.raises(
        PhaseApplicabilityAgentWireValidationError,
        match="UNKNOWN 或 MIXED",
    ):
        parse_phase_applicability_agent_wire_v2(payload)


def test_same_session_repair_prompt_requires_complete_target_echo() -> None:
    package = _package()
    agent_input = build_phase_applicability_agent_input(package)
    invalid = _v2_payload(
        package,
        invalid_scope_index=0,
        invalid_scope="unknown",
        unresolved=True,
    )
    partial_repair = _v2_payload(package, unit_indexes=[0])
    transport = _QueueTransport([invalid, partial_repair])

    result = PhaseApplicabilityAgentRunner(max_schema_repairs=1).run(
        agent_input,
        transport,
    )

    assert result.status == "需要核对"
    assert result.final_output is None
    assert transport.start_calls == 1
    assert transport.continue_calls == 1
    assert [attempt.outcome for attempt in result.attempts] == [
        "schema_invalid",
        "schema_invalid",
    ]
    assert "PARTIAL_OR_DRIFTED_BATCH" in result.attempts[-1].issues[0]

    repair_prompt = transport.prompts[-1][1]
    assert "完整冻结目标清单" in repair_prompt
    assert "修复后必须逐项回显" in repair_prompt
    for unit_index, unit in enumerate(package.owned_units):
        assert f'"unit_index": {unit_index}' in repair_prompt
        assert unit.structure_unit_id in repair_prompt


def test_same_session_repair_accepts_only_a_complete_repaired_batch() -> None:
    package = _package()
    agent_input = build_phase_applicability_agent_input(package)
    invalid = _v2_payload(
        package,
        invalid_scope_index=1,
        invalid_scope="mixed",
        unresolved=True,
    )
    complete_repair = _v2_payload(package)
    transport = _QueueTransport([invalid, complete_repair])

    result = PhaseApplicabilityAgentRunner(max_schema_repairs=1).run(
        agent_input,
        transport,
    )

    assert result.status == "已解析"
    assert result.final_output is not None
    assert [item.structure_unit_id for item in result.final_output.results] == [
        unit.structure_unit_id for unit in package.owned_units
    ]
    assert [attempt.outcome for attempt in result.attempts] == [
        "schema_invalid",
        "parsed",
    ]
    assert transport.start_calls == 1
    assert transport.continue_calls == 1


def test_global_chapter_and_title_mention_cannot_broadcast_to_specific_controls() -> None:
    owned = [
        _unit(
            "target-inclusion",
            0,
            heading_path=["6 研究人群", "6.1 入选标准"],
            excerpt="目标入选标准中的具体研究要求。",
        ),
        _unit(
            "target-concomitant",
            1,
            heading_path=["7 研究评估和程序", "7.2 结核筛查"],
            excerpt="目标结核筛查要求。",
        ),
    ]
    context = [
        _unit(
            "global-chapter",
            2,
            scope=PhaseScope.PHASE_II,
            heading_path=["5 研究设计"],
            excerpt="Ⅱ/Ⅲ期评估和程序一致，详见研究流程。",
        ),
        _unit(
            "title-mention",
            3,
            scope=PhaseScope.PHASE_II,
            heading_path=["9 安全性", "9.1 一般原则"],
            excerpt="本段仅提及结核筛查，但没有对应的规则要求。",
        ),
    ]
    package = _package(owned_units=owned, context_units=context)
    agent_input = build_phase_applicability_agent_input(package)

    # Deliberately construct the evidence chain a model previously used: the
    # first target cites a global chapter, and the second cites a paragraph
    # that merely mentions the target title.
    payload = {
        "wire_version": PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION,
        "groups": [
            {
                "unit_indexes": [0],
                "structure_unit_ids": ["target-inclusion"],
                "evidence": [
                    {
                        "polarity": "supports",
                        "source_unit_indexes": [2],
                        "source_span_indexes": [
                            package.frozen_source_span_ids.index("span-global-chapter")
                        ],
                        "excerpt": context[0].excerpt,
                        "rationale": "共同章节可以支持该目标的选定期别",
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
                "rationale": "共同章节支持选定期别适用",
                "unresolved_reason": None,
            },
            {
                "unit_indexes": [1],
                "structure_unit_ids": ["target-concomitant"],
                "evidence": [
                    {
                        "polarity": "supports",
                        "source_unit_indexes": [3],
                        "source_span_indexes": [
                            package.frozen_source_span_ids.index("span-title-mention")
                        ],
                        "excerpt": context[1].excerpt,
                        "rationale": "提及目标标题即可支持选定期别适用",
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
                "rationale": "标题提及支持选定期别适用",
                "unresolved_reason": None,
            },
        ],
    }
    wire = parse_phase_applicability_agent_wire_v2(
        json.dumps(payload, ensure_ascii=False)
    )
    draft = wire_to_phase_applicability_resolution_draft(wire, agent_input)
    resolutions = hydrate_phase_applicability_resolution(package, draft)
    report = check_phase_applicability_resolution(package, resolutions)

    issues = {
        issue.structure_unit_id: issue.code
        for issue in report.issues
        if issue.structure_unit_id is not None
    }
    assert not report.accepted
    assert issues == {
        "target-inclusion": "TARGET_RELATED_SUPPORT_MISSING",
        "target-concomitant": "TARGET_RELATED_SUPPORT_MISSING",
    }


def test_mixed_causal_reference_can_resolve_by_operation_phase() -> None:
    unit = _unit(
        "target-interim-analysis",
        0,
        scope=PhaseScope.MIXED,
        heading_path=["统计学考虑", "统计分析", "期中分析"],
        excerpt=(
            "该分析的主要目的是基于累积的II期研究的有效性和安全性数据，"
            "由独立数据监查委员会向申办方提供正式建议：包括能否继续进行Ⅲ期临床研究。"
        ),
    )
    package = _package(owned_units=[unit])
    wire = parse_phase_applicability_agent_wire_v2(_v2_payload(package))
    draft = wire_to_phase_applicability_resolution_draft(
        wire,
        build_phase_applicability_agent_input(package),
    )
    report = check_phase_applicability_resolution(
        package,
        hydrate_phase_applicability_resolution(package, draft),
    )

    assert report.accepted


def test_mixed_parallel_phase_obligations_can_remain_unresolved() -> None:
    unit = _unit(
        "target-hba1c-visits",
        0,
        scope=PhaseScope.MIXED,
        heading_path=["研究评估和程序", "实验室检查"],
        excerpt=(
            "糖化血红蛋白Ⅱ期仅在筛选、12周访视时检测，"
            "Ⅲ期仅在筛选、16周、52周访视进行。"
        ),
    )
    package = _package(owned_units=[unit])
    wire = parse_phase_applicability_agent_wire_v2(
        _v2_payload(package, unresolved=True)
    )
    draft = wire_to_phase_applicability_resolution_draft(
        wire,
        build_phase_applicability_agent_input(package),
    )
    report = check_phase_applicability_resolution(
        package,
        hydrate_phase_applicability_resolution(package, draft),
    )

    assert report.accepted


def test_old_five_package_checkpoint_reveals_global_source_broadcast() -> None:
    if not _OLD_FIVE_PACKAGE_CHECKPOINT.is_file():
        pytest.skip(f"旧五包语义检查点缺失：{_OLD_FIVE_PACKAGE_CHECKPOINT}")

    state = PhaseApplicabilityExecutionState.model_validate(
        json.loads(_OLD_FIVE_PACKAGE_CHECKPOINT.read_text(encoding="utf-8"))
    )
    assert state.gate_version == "phase5/phase-applicability-gate/v1"
    accepted_ordinals = [
        package.package_ordinal
        for package, record in zip(state.plan.packages, state.batches)
        if record.status == "accepted"
    ]
    assert accepted_ordinals == [1, 3, 4]
    assert state.status == "needs_review"

    # The historical checkpoint remains readable, but gate v2 must not silently
    # preserve its old acceptance. Package 1 contains an unresolved result that
    # never explains whether the selected phase itself is uncertain.
    package_1, record_1 = state.plan.packages[0], state.batches[0]
    assert record_1.final_output is not None
    package_1_report = check_phase_applicability_resolution(
        package_1, record_1.final_output
    )
    assert not package_1_report.accepted
    assert {issue.code for issue in package_1_report.issues} == {
        "SELECTED_PHASE_UNRESOLVED_EVIDENCE_MISSING"
    }

    for ordinal in (3, 4):
        package = next(
            package
            for package in state.plan.packages
            if package.package_ordinal == ordinal
        )
        record = next(
            record
            for record in state.batches
            if record.package_ordinal == ordinal
        )
        assert record.status == "accepted"
        assert record.final_output is not None

        broad_source = next(
            unit for unit in package.all_units if unit.source_ref == "body.p765"
        )
        assert broad_source.phase_scopes == [PhaseScope.SHARED]
        cross_phase_results = [
            result
            for result in record.final_output.results
            if result.final_disposition
            == PhaseApplicabilityDisposition.CROSS_PHASE_SHARED
        ]
        assert cross_phase_results
        for result in cross_phase_results:
            cited_unit_ids = {
                unit_id
                for evidence in result.evidence
                for unit_id in evidence.source_structure_unit_ids
            }
            assert broad_source.structure_unit_id in cited_unit_ids
            target = next(
                unit
                for unit in package.owned_units
                if unit.structure_unit_id == result.structure_unit_id
            )
            assert target.heading_path[-1] != broad_source.heading_path[-1]
            assert not any(
                target.heading_path[-1] in evidence.excerpt
                for evidence in result.evidence
            )

        report = check_phase_applicability_resolution(
            package, record.final_output
        )
        assert not report.accepted
        assert "SHARED_POSITIVE_SOURCE_MISSING" in {
            issue.code for issue in report.issues
        }
        assert {
            issue.structure_unit_id
            for issue in report.issues
            if issue.code == "SHARED_POSITIVE_SOURCE_MISSING"
        } == {result.structure_unit_id for result in cross_phase_results}
