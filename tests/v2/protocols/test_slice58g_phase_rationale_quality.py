from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.agents.phase_applicability import (
    PHASE_APPLICABILITY_AGENT_WIRE_V1_VERSION,
    PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION,
    PhaseApplicabilityAgentInput,
    PhaseApplicabilityAgentResponse,
    PhaseApplicabilityAgentRunner,
    PhaseApplicabilityAgentWireValidationError,
    build_phase_applicability_agent_prompt,
    hydrate_phase_applicability_agent_output,
)
from app.domain.contracts.enums import PhaseScope, StudyPhase
from app.domain.contracts.phase_applicability import (
    PhaseApplicabilityDisposition,
    PhaseApplicabilityEvidencePolarity,
    PhaseApplicabilityFrozenPackage,
    stable_phase_applicability_package_id,
)
from app.domain.contracts.protocol_controls import (
    ProtocolStructureUnit,
    StructureUnitKind,
)


_SHA = "a" * 64
_BAD_SUMMARY_FRAGMENT = "该段为方案摘要中"
_REAL_PROBE_DIR = (
    Path(__file__).resolve().parents[3]
    / ".trellis"
    / "tasks"
    / "08-22-phase5-clinical-facts-profile"
    / "research"
    / "d001-ii-phase-closure"
    / "probe-package32-slice58f"
)
_REAL_REPAIR2_DIR = _REAL_PROBE_DIR.parent / "probe-package32-slice58g-repair2"


def _synthetic_input(
    *,
    source_scope: PhaseScope = PhaseScope.UNKNOWN,
) -> PhaseApplicabilityAgentInput:
    unit = ProtocolStructureUnit(
        structure_unit_id="synthetic-target",
        source_ref="body.p0",
        member_source_refs=["body.p0"],
        source_span_ids=["synthetic-span"],
        unit_kind=StructureUnitKind.PARAGRAPH,
        heading_path=["方案摘要", "期别说明"],
        source_order=0,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[source_scope],
        excerpt="本段描述目标期别适用范围。",
    )
    package = PhaseApplicabilityFrozenPackage(
        package_id=stable_phase_applicability_package_id(
            "manifest:phase-rationale-quality",
            1,
            [unit.structure_unit_id],
        ),
        coverage_manifest_id="manifest:phase-rationale-quality",
        protocol_version_id="protocol:phase-rationale-quality",
        protocol_document_sha256=_SHA,
        snapshot_id="snapshot:phase-rationale-quality",
        package_ordinal=1,
        selected_phase=StudyPhase.PHASE_II,
        opposite_phase=StudyPhase.PHASE_III,
        owned_units=[unit],
        context_units=[],
        frozen_source_span_ids=["synthetic-span"],
    )
    return PhaseApplicabilityAgentInput.from_frozen_package(package)


def _synthetic_payload(
    agent_input: PhaseApplicabilityAgentInput,
    *,
    wire_version: str,
    disposition: PhaseApplicabilityDisposition,
    scope: PhaseScope,
    polarity: PhaseApplicabilityEvidencePolarity,
    rationale: str,
    unresolved_reason: str | None = None,
) -> dict[str, object]:
    evidence = {
        "polarity": polarity.value,
        "source_unit_indexes": [0],
        "source_span_indexes": [0],
        "excerpt": agent_input.target_units[0].excerpt,
        "rationale": rationale,
    }
    candidate = {
        "scope": scope.value,
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
    result = {
        "unit_index": 0,
        "structure_unit_id": agent_input.target_units[0].structure_unit_id,
        "evidence": [evidence],
        "candidates": [candidate],
        "final_disposition": disposition.value,
        "rationale": rationale,
        "unresolved_reason": unresolved_reason,
    }
    if wire_version == PHASE_APPLICABILITY_AGENT_WIRE_V1_VERSION:
        return {
            "wire_version": PHASE_APPLICABILITY_AGENT_WIRE_V1_VERSION,
            "results": [result],
        }
    return {
        "wire_version": PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION,
        "groups": [
            {
                "unit_indexes": [0],
                "structure_unit_ids": [
                    agent_input.target_units[0].structure_unit_id
                ],
                "evidence": [evidence],
                "candidates": [candidate],
                "final_disposition": disposition.value,
                "rationale": rationale,
                "unresolved_reason": unresolved_reason,
            }
        ],
    }


def _replace_rationales(
    payload: dict[str, object],
    rationale: str,
) -> dict[str, object]:
    updated = copy.deepcopy(payload)
    records = (
        updated["results"]
        if "results" in updated
        else updated["groups"]
    )
    assert isinstance(records, list)
    for record in records:
        assert isinstance(record, dict)
        record["rationale"] = rationale
        evidence = record["evidence"]
        assert isinstance(evidence, list)
        for item in evidence:
            assert isinstance(item, dict)
            item["rationale"] = rationale
        if record.get("unresolved_reason") is not None:
            record["unresolved_reason"] = rationale
    return updated


def test_prompt_allows_paired_phase_rule_references_without_shared_source() -> None:
    prompt = build_phase_applicability_agent_prompt(_synthetic_input())

    assert "这种成对引用不要求另有 phase_scopes=shared 的第三份来源" in prompt
    assert "成对来源必须作为一个组合判断" in prompt
    assert "共享支持证据中必须至少有一个冻结来源的 phase_scopes 已标记为 shared" not in prompt
    assert "不得创建证据索引全为空的候选" in prompt


def test_prompt_keeps_global_control_in_selected_phase_without_claiming_shared() -> None:
    prompt = build_phase_applicability_agent_prompt(_synthetic_input())

    assert "该全局章节结构可正向支持 selected_phase_applicable" in prompt
    assert "这不等于已经证明 cross_phase_shared" in prompt
    assert "不得因为无法证明另一期间也适用" in prompt
    assert "把当前所选期别明确需要遵守的全局控制降为 unresolved" in prompt


@pytest.mark.parametrize(
    "rationale",
    [
        "该段使用'研究期间''整个研究过程",
        "该段位于“研究治疗章节，支持本期适用。",
        "该段位于研究治疗（合并用药章节，支持本期适用。",
    ],
)
def test_wire_rejects_truncated_chinese_rationale(rationale: str) -> None:
    agent_input = _synthetic_input()
    payload = _synthetic_payload(
        agent_input,
        wire_version=PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION,
        disposition=PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE,
        scope=PhaseScope.PHASE_II,
        polarity=PhaseApplicabilityEvidencePolarity.SUPPORTS,
        rationale=rationale,
    )

    with pytest.raises(PhaseApplicabilityAgentWireValidationError) as caught:
        hydrate_phase_applicability_agent_output(payload, agent_input)

    assert caught.value.code == "WIRE_SCHEMA_INVALID"
    assert "引号或括号必须成对" in str(caught.value)


@pytest.mark.parametrize(
    "field_path",
    [
        ("groups", 0, "rationale"),
        ("groups", 0, "evidence", 0, "rationale"),
    ],
)
def test_wire_rejects_invisible_control_characters_in_rationales(
    field_path: tuple[str | int, ...],
) -> None:
    agent_input = _synthetic_input()
    payload = _synthetic_payload(
        agent_input,
        wire_version=PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION,
        disposition=PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE,
        scope=PhaseScope.PHASE_II,
        polarity=PhaseApplicabilityEvidencePolarity.SUPPORTS,
        rationale="依据冻结方案原文明确支持本期适用。",
    )
    target = payload
    for part in field_path[:-1]:
        target = target[part]
    target[field_path[-1]] = "依据\u000b冻结方案原文明确支持本期适用。"

    with pytest.raises(PhaseApplicabilityAgentWireValidationError) as caught:
        hydrate_phase_applicability_agent_output(payload, agent_input)

    assert caught.value.code == "WIRE_SCHEMA_INVALID"
    assert "不得包含不可见控制字符或格式字符" in str(caught.value)


@pytest.mark.parametrize(
    "wire_version",
    [
        PHASE_APPLICABILITY_AGENT_WIRE_V1_VERSION,
        PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION,
    ],
)
@pytest.mark.parametrize(
    "disposition,scope,polarity,rationale,unresolved_reason",
    [
        (
            PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE,
            PhaseScope.PHASE_II,
            PhaseApplicabilityEvidencePolarity.SUPPORTS,
            "依据冻结方案原文明确说明本期适用，故判定选定期别适用。",
            None,
        ),
        (
            PhaseApplicabilityDisposition.OPPOSITE_PHASE_APPLICABLE,
            PhaseScope.PHASE_III,
            PhaseApplicabilityEvidencePolarity.SUPPORTS,
            "依据冻结方案原文明确说明实际适用于对侧期，故判定对侧期适用。",
            None,
        ),
        (
            PhaseApplicabilityDisposition.CROSS_PHASE_SHARED,
            PhaseScope.SHARED,
            PhaseApplicabilityEvidencePolarity.SUPPORTS,
            "依据冻结方案原文明确说明同一要求在Ⅱ期和Ⅲ期均适用，故判定两期共用。",
            None,
        ),
        (
            PhaseApplicabilityDisposition.UNRESOLVED,
            PhaseScope.PHASE_II,
            PhaseApplicabilityEvidencePolarity.UNRESOLVED,
            "依据冻结原文和上下文资料不足以确定本期或对侧期，当前待确认。",
            "依据冻结原文和上下文资料不足以确定本期或对侧期，当前待确认。",
        ),
    ],
)
def test_rationale_wording_is_not_used_as_a_deterministic_semantic_gate(
    wire_version: str,
    disposition: PhaseApplicabilityDisposition,
    scope: PhaseScope,
    polarity: PhaseApplicabilityEvidencePolarity,
    rationale: str,
    unresolved_reason: str | None,
) -> None:
    agent_input = _synthetic_input(
        source_scope=(
            PhaseScope.SHARED
            if disposition == PhaseApplicabilityDisposition.CROSS_PHASE_SHARED
            else PhaseScope.UNKNOWN
        )
    )
    valid = _synthetic_payload(
        agent_input,
        wire_version=wire_version,
        disposition=disposition,
        scope=scope,
        polarity=polarity,
        rationale=rationale,
        unresolved_reason=unresolved_reason,
    )
    output = hydrate_phase_applicability_agent_output(valid, agent_input)
    assert output.results[0].final_disposition == disposition
    assert output.results[0].rationale == rationale

    terse = _replace_rationales(valid, _BAD_SUMMARY_FRAGMENT)
    terse_output = hydrate_phase_applicability_agent_output(terse, agent_input)
    assert terse_output.results[0].final_disposition == disposition


class _QueueTransport:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.session_ids: list[str] = []
        self.prompts: list[str] = []

    def start(self, *, prompt: str) -> PhaseApplicabilityAgentResponse:
        self.prompts.append(prompt)
        self.session_ids.append("synthetic-phase-session")
        return PhaseApplicabilityAgentResponse(
            session_id="synthetic-phase-session",
            text=self.responses.pop(0),
        )

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
    ) -> PhaseApplicabilityAgentResponse:
        self.prompts.append(prompt)
        self.session_ids.append(session_id)
        return PhaseApplicabilityAgentResponse(
            session_id=session_id,
            text=self.responses.pop(0),
        )


@pytest.mark.parametrize(
    "wire_version",
    [
        PHASE_APPLICABILITY_AGENT_WIRE_V1_VERSION,
        PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION,
    ],
)
def test_synthetic_chinese_reason_does_not_trigger_lexical_repair(
    wire_version: str,
) -> None:
    agent_input = _synthetic_input()
    valid = _synthetic_payload(
        agent_input,
        wire_version=wire_version,
        disposition=PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE,
        scope=PhaseScope.PHASE_II,
        polarity=PhaseApplicabilityEvidencePolarity.SUPPORTS,
        rationale="依据冻结方案原文明确说明本期适用，故判定选定期别适用。",
    )
    invalid = _replace_rationales(valid, _BAD_SUMMARY_FRAGMENT)
    transport = _QueueTransport([json.dumps(invalid, ensure_ascii=False)])

    result = PhaseApplicabilityAgentRunner(max_schema_repairs=1).run(
        agent_input,
        transport,
    )

    assert result.status == "已解析"
    assert result.final_output is not None
    assert [attempt.outcome for attempt in result.attempts] == ["parsed"]
    assert transport.session_ids == ["synthetic-phase-session"]


def test_evidence_reason_tracks_its_own_polarity_not_the_final_disposition() -> None:
    agent_input = _synthetic_input()
    payload = _synthetic_payload(
        agent_input,
        wire_version=PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION,
        disposition=PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE,
        scope=PhaseScope.PHASE_II,
        polarity=PhaseApplicabilityEvidencePolarity.SUPPORTS,
        rationale="依据冻结方案原文明确说明本期适用，故判定选定期别适用。",
    )
    group = payload["groups"][0]
    group["evidence"].append(
        {
            "polarity": PhaseApplicabilityEvidencePolarity.OPPOSES.value,
            "source_unit_indexes": [0],
            "source_span_indexes": [0],
            "excerpt": agent_input.target_units[0].excerpt,
            "rationale": "原文另一处描述不支持本期适用，构成反对证据。",
        }
    )
    group["candidates"].append(
        {
            "scope": PhaseScope.PHASE_III.value,
            "supporting_evidence_indexes": [],
            "opposing_evidence_indexes": [1],
            "unresolved_evidence_indexes": [],
        }
    )

    output = hydrate_phase_applicability_agent_output(payload, agent_input)

    assert output.results[0].final_disposition == (
        PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE
    )
    assert [item.polarity for item in output.results[0].evidence] == [
        PhaseApplicabilityEvidencePolarity.SUPPORTS,
        PhaseApplicabilityEvidencePolarity.OPPOSES,
    ]


def _load_real_bad_response() -> tuple[PhaseApplicabilityAgentInput, str, dict[str, object]]:
    input_path = _REAL_PROBE_DIR / "agent-input.json"
    history_path = _REAL_PROBE_DIR / "conversation-history.json"
    assert input_path.is_file(), input_path
    assert history_path.is_file(), history_path
    agent_input = PhaseApplicabilityAgentInput.model_validate(
        json.loads(input_path.read_text(encoding="utf-8"))
    )
    history = json.loads(history_path.read_text(encoding="utf-8"))
    raw_response = next(
        item["content"] for item in history if item.get("role") == "assistant"
    )
    payload = json.loads(raw_response)
    return agent_input, raw_response, payload


def test_real_slice58f_broad_shared_claim_is_blocked_before_rationale_wording() -> None:
    agent_input, raw_response, payload = _load_real_bad_response()
    assert payload["wire_version"] == PHASE_APPLICABILITY_AGENT_WIRE_V2_VERSION
    assert len(agent_input.target_units) == len(payload["groups"])
    assert {
        group["rationale"]
        for group in payload["groups"]
    } == {_BAD_SUMMARY_FRAGMENT}
    assert {
        evidence["rationale"]
        for group in payload["groups"]
        for evidence in group["evidence"]
    } == {_BAD_SUMMARY_FRAGMENT}

    with pytest.raises(PhaseApplicabilityAgentWireValidationError) as caught:
        hydrate_phase_applicability_agent_output(raw_response, agent_input)
    assert caught.value.code == "SHARED_POSITIVE_SOURCE_MISSING"


def test_real_slice58g_repair_cannot_broadcast_a_shared_source() -> None:
    agent_input, _, _ = _load_real_bad_response()
    response_path = _REAL_REPAIR2_DIR / "raw-response.json"
    assert response_path.is_file(), response_path
    payload = json.loads(response_path.read_text(encoding="utf-8"))

    with pytest.raises(PhaseApplicabilityAgentWireValidationError) as caught:
        hydrate_phase_applicability_agent_output(payload, agent_input)
    assert caught.value.code == "SHARED_POSITIVE_SOURCE_MISSING"
