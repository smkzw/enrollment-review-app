from __future__ import annotations

import pytest

from app.agents.protocol_deconstructor import (
    ProtocolAgentResponse,
    ProtocolDeconstructorRunner,
    _collect_initial_semantic_response,
    _parse_protocol_draft,
    _parse_semantic_candidate,
    _recover_exact_fragments,
    _regressing_rule_codes,
    _select_repair_rule_codes,
    protocol_prompt_template_sha256,
    revise_protocol_draft_from_feedback,
    semantic_candidate_from_draft,
)
from app.domain.contracts.agents import PromptVersion
from app.domain.contracts.agent_io import (
    ProtocolSemanticDeconstructionCandidate,
    ProtocolSemanticRuleRepair,
    SemanticEvidenceRequirement,
    SemanticRule,
    SemanticRuleComponent,
)
from app.domain.contracts.enums import AgentNode, LogicalOperator
from app.protocols.deconstruction_gate import ProtocolGateIssue
from tests.v2.protocols.test_deconstruction_gate_slice3 import _fixture


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.start_prompts = []
        self.repair_prompts = []

    def start(self, *, prompt):
        self.start_prompts.append(prompt)
        return self.responses.pop(0)

    def continue_session(self, *, session_id, prompt):
        self.repair_prompts.append((session_id, prompt))
        return self.responses.pop(0)


class FailingStartTransport:
    def start(self, *, prompt):
        raise RuntimeError("上游连续返回空正文")


class FailingRepairTransport(FakeTransport):
    def continue_session(self, *, session_id, prompt):
        self.repair_prompts.append((session_id, prompt))
        raise RuntimeError("修订请求未完成")


def _prompt_version(template):
    return PromptVersion(
        prompt_version_id="protocol-deconstructor/v1",
        node=AgentNode.PROTOCOL_DECONSTRUCTOR,
        template_sha256=protocol_prompt_template_sha256(template),
        schema_version_id="protocol-deconstruction-draft/fixture-v1",
    )


def _semantic_candidate(source_input, draft):
    source_text = {
        material.source_span_id: material.text
        for material in source_input.source_materials
    }
    return ProtocolSemanticDeconstructionCandidate(
        candidate_id="candidate-1",
        proposed_rules=[
            SemanticRule(
                official_code=rule.official_code,
                components=[
                    SemanticRuleComponent(
                        title=component.title,
                        expression=component.expression,
                        exception_expression=component.exception_expression,
                        evidence_requirements=[
                            SemanticEvidenceRequirement(
                                fact_type=requirement.fact_type,
                                required_source_types=requirement.required_source_types,
                                allows_screening_record_transcription=(
                                    requirement.allows_screening_record_transcription
                                ),
                                requires_contemporaneous_objective_source=(
                                    requirement.requires_contemporaneous_objective_source
                                ),
                                due_stage=requirement.due_stage,
                                description=requirement.description,
                            )
                            for requirement in component.evidence_requirements
                        ],
                        source_span_ids=next(
                            item.source_refs
                            for item in draft.component_drafts
                            if item.proposed_component.rule_component_id
                            == component.rule_component_id
                        ),
                        source_excerpts=[
                            source_text[
                                next(
                                    item.source_refs[0]
                                    for item in draft.component_drafts
                                    if item.proposed_component.rule_component_id
                                    == component.rule_component_id
                                )
                            ]
                        ],
                    )
                    for component in rule.components
                ],
            )
            for rule in draft.proposed_rules
        ],
        created_by_agent_call_id="agent-call-1",
    )


def test_hydrated_draft_can_recover_semantic_candidate_for_persisted_repair():
    source_input, draft, _spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    hydrated = _parse_protocol_draft(candidate.model_dump_json(), source_input)

    recovered = semantic_candidate_from_draft(hydrated)

    assert recovered.candidate_id == candidate.candidate_id
    assert recovered.proposed_rules == candidate.proposed_rules
    assert recovered.created_by_agent_call_id == candidate.created_by_agent_call_id


def test_feedback_revision_replaces_only_selected_parent_rule():
    source_input, draft, _spans = _fixture()
    candidate = semantic_candidate_from_draft(draft)
    replacement = candidate.proposed_rules[1].model_copy(deep=True)
    replacement.components[0].title = "按方案原文修正后的排除条件"
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[replacement],
    )
    transport = FakeTransport(
        [ProtocolAgentResponse(session_id="feedback-session", text=repair.model_dump_json())]
    )

    revised = revise_protocol_draft_from_feedback(
        source_input,
        draft,
        target_rule_code="EX-01",
        feedback_note="EX-01 的原文条件被理解错了，请按原文重新拆分。",
        transport=transport,
    )

    original = semantic_candidate_from_draft(draft)
    actual = semantic_candidate_from_draft(revised)
    assert actual.proposed_rules[0] == original.proposed_rules[0]
    assert actual.proposed_rules[1].components[0].title == "按方案原文修正后的排除条件"
    assert revised.draft_id == draft.draft_id
    assert "replacement_rules 必须且只能包含 EX-01" in transport.start_prompts[0]


def test_feedback_namespaced_draft_id_round_trips_without_creating_new_chain():
    """正式版本反馈草稿的命名空间不得在语义水合后重复套 draft 前缀。"""

    source_input, draft, _spans = _fixture()
    draft = draft.model_copy(update={"draft_id": "draft:feedback:stable-id"})
    candidate = semantic_candidate_from_draft(draft)
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[candidate.proposed_rules[1]],
    )
    transport = FakeTransport(
        [ProtocolAgentResponse(session_id="feedback-session", text=repair.model_dump_json())]
    )

    revised = revise_protocol_draft_from_feedback(
        source_input,
        draft,
        target_rule_code="EX-01",
        feedback_note="核对反馈草稿身份。",
        transport=transport,
    )

    assert candidate.candidate_id == "feedback:stable-id"
    assert revised.draft_id == "draft:feedback:stable-id"


def test_feedback_revision_rejects_wrong_rule_then_repairs_in_same_session():
    source_input, draft, _spans = _fixture()
    candidate = semantic_candidate_from_draft(draft)
    wrong = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[candidate.proposed_rules[0]],
    )
    replacement = candidate.proposed_rules[1].model_copy(deep=True)
    replacement.components[0].title = "修正后的目标规则"
    correct = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[replacement],
    )
    transport = FakeTransport(
        [
            ProtocolAgentResponse(session_id="feedback-session", text=wrong.model_dump_json()),
            ProtocolAgentResponse(session_id="feedback-session", text=correct.model_dump_json()),
        ]
    )

    revised = revise_protocol_draft_from_feedback(
        source_input,
        draft,
        target_rule_code="EX-01",
        feedback_note="只核对 EX-01。",
        transport=transport,
    )

    assert semantic_candidate_from_draft(revised).proposed_rules[1].components[0].title == "修正后的目标规则"
    assert transport.repair_prompts[0][0] == "feedback-session"
    assert "指定父规则的局部修订" in transport.repair_prompts[0][1]


def test_valid_json_passes_without_repair():
    source_input, draft, spans = _fixture()
    template = "按正式方案原文进行结构化解构。"
    transport = FakeTransport(
        [ProtocolAgentResponse(session_id="session-1", text=draft.model_dump_json())]
    )
    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )
    assert result.status == "可以进入审阅"
    assert len(result.attempts) == 1
    assert transport.repair_prompts == []
    assert "不得增加、删除、合并或调换成员" in transport.start_prompts[0]
    assert "不能拆成任一条件单独触发" in transport.start_prompts[0]
    assert "exception_expression" in transport.start_prompts[0]
    assert "first_dose_date" in transport.start_prompts[0]
    assert "不得为表示审核阶段而复制原子条件" in transport.start_prompts[0]
    assert "同时引用父级引导段和当前子项" in transport.start_prompts[0]


def _gate_issue(code, refs, *, level="阻止发布"):
    return ProtocolGateIssue(
        issue_code=code,
        check_name="temporal_semantics",
        level=level,
        problem="需要修正",
        impact="当前不能发布",
        next_action="核对原文",
        affected_refs=refs,
        repair_scope=refs,
    )


def test_repair_selection_rotates_to_less_repaired_parent_rules():
    _source_input, draft, _spans = _fixture()
    issues = [
        _gate_issue("IN_ISSUE", ["predicate-age"]),
        _gate_issue("EX_ISSUE", ["predicate-alt"]),
    ]

    selected = _select_repair_rule_codes(
        draft,
        issues,
        {"IN-01": 2, "EX-01": 0},
        limit=1,
    )

    assert selected == ["EX-01"]


def test_rule_repair_that_adds_blocking_issues_is_detected_as_regression():
    _source_input, draft, _spans = _fixture()
    previous = [_gate_issue("OLD", ["predicate-alt"])]
    revised = [
        _gate_issue("OLD", ["predicate-alt"]),
        _gate_issue("NEW", ["predicate-ast"]),
    ]

    assert _regressing_rule_codes(
        draft,
        previous,
        draft,
        revised,
        ["EX-01"],
    ) == {"EX-01"}


def test_equal_count_issue_moved_to_another_predicate_is_regression():
    _source_input, draft, _spans = _fixture()
    previous = [_gate_issue("TIME_ANCHOR_MISSING", ["predicate-alt"])]
    revised = [_gate_issue("TIME_ANCHOR_MISSING", ["predicate-ast"])]

    assert _regressing_rule_codes(
        draft,
        previous,
        draft,
        revised,
        ["EX-01"],
    ) == {"EX-01"}


def test_lean_semantic_candidate_is_hydrated_from_frozen_catalogs():
    source_input, draft, spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    template = "按正式方案原文进行结构化解构。"
    transport = FakeTransport(
        [ProtocolAgentResponse(session_id="session-1", text=candidate.model_dump_json())]
    )

    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )

    assert result.status == "可以进入审阅"
    assert result.final_draft is not None
    assert len(result.final_draft.parent_catalog_mappings) == 2
    assert len(result.final_draft.procedure_catalog_mappings) == 2
    assert len(result.final_draft.component_drafts) == 2
    assert {
        item.proposed_requirement.procedure_catalog_item_id
        for item in result.final_draft.evidence_requirement_drafts
        if item.procedure_catalog_item_id is not None
    } == {"procedure:screening:lab", "procedure:baseline:lab"}


def test_large_official_catalog_is_collected_in_ordered_same_session_batches():
    source_input, draft, _spans = _fixture()
    base_candidate = _semantic_candidate(source_input, draft)
    codes = ["IN-01", "IN-02", "IN-03", "EX-01", "EX-02", "EX-03"]
    items = []
    for index, code in enumerate(codes):
        template = source_input.parent_rule_catalog.items[index % 2]
        items.append(
            template.model_copy(
                update={
                    "item_id": f"catalog:{code}",
                    "official_code": code,
                    "position": index + 1,
                }
            )
        )
    expanded_input = source_input.model_copy(
        update={
            "parent_rule_catalog": source_input.parent_rule_catalog.model_copy(
                update={"items": tuple(items)}
            )
        }
    )

    def batch(rule_codes):
        rules = []
        for index, code in enumerate(rule_codes):
            rule = base_candidate.proposed_rules[index % 2].model_copy(deep=True)
            rule.official_code = code
            rules.append(rule)
        return base_candidate.model_copy(update={"proposed_rules": rules}, deep=True)

    transport = FakeTransport(
        [
            ProtocolAgentResponse(
                session_id="session-1", text=batch(codes[:3]).model_dump_json()
            ),
            ProtocolAgentResponse(
                session_id="session-1", text=batch(codes[3:]).model_dump_json()
            ),
        ]
    )

    response, error = _collect_initial_semantic_response(
        expanded_input,
        prompt_template="按正式方案原文进行结构化解构。",
        transport=transport,
        batch_size=3,
    )
    merged = _parse_semantic_candidate(response.text)

    assert error is None
    assert [rule.official_code for rule in merged.proposed_rules] == codes
    assert "必须且只能返回这些官方父规则" in transport.start_prompts[0]
    assert transport.repair_prompts[0][0] == "session-1"
    assert "第 2/2 批" in transport.repair_prompts[0][1]


def test_invalid_output_is_repaired_in_same_session():
    source_input, draft, spans = _fixture()
    template = "按正式方案原文进行结构化解构。"
    transport = FakeTransport(
        [
            ProtocolAgentResponse(session_id="session-1", text="不是 JSON"),
            ProtocolAgentResponse(
                session_id="session-1", text=draft.model_dump_json()
            ),
        ]
    )
    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )
    assert result.status == "可以进入审阅"
    assert [item.outcome for item in result.attempts] == [
        "输出格式无效",
        "通过完整性检查",
    ]
    assert transport.repair_prompts[0][0] == "session-1"
    assert "前一响应从未成功解析为完整草稿" in transport.repair_prompts[0][1]
    assert "严禁输出空列表" in transport.repair_prompts[0][1]


def test_valid_candidate_repairs_only_affected_parent_rule():
    source_input, draft, spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    bad_candidate = candidate.model_copy(deep=True)
    bad_candidate.proposed_rules[1].components[0].expression.operator = (
        LogicalOperator.ALL
    )
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[candidate.proposed_rules[1]],
    )
    template = "按正式方案原文进行结构化解构。"
    transport = FakeTransport(
        [
            ProtocolAgentResponse(
                session_id="session-1", text=bad_candidate.model_dump_json()
            ),
            ProtocolAgentResponse(session_id="session-1", text=repair.model_dump_json()),
        ]
    )

    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )

    assert result.status == "可以进入审阅"
    assert [item.outcome for item in result.attempts] == [
        "需要定向修正",
        "通过完整性检查",
    ]
    assert "['EX-01']" in transport.repair_prompts[0][1]
    assert "不要返回整份草稿" in transport.repair_prompts[0][1]
    assert result.final_draft is not None
    assert (
        result.final_draft.proposed_rules[0].components[0].expression
        == candidate.proposed_rules[0].components[0].expression
    )


def test_empty_schema_defs_and_singleton_identity_logic_are_normalized():
    _source_input, draft, _spans = _fixture()
    payload = draft.model_dump(mode="json")
    payload["$defs"] = {}
    original = payload["proposed_rules"][0]["components"][0]["expression"]
    payload["proposed_rules"][0]["components"][0]["expression"] = {
        "kind": "logical",
        "operator": "all",
        "children": [original],
    }

    parsed = _parse_protocol_draft(__import__("json").dumps(payload))

    assert parsed.proposed_rules[0].components[0].expression.kind == "predicate"


def test_shared_time_prefix_is_split_only_into_unique_exact_fragments():
    source = (
        "随机前12周（大分子药物）/4周（小分子药物）或5个药物半衰期"
        "（以较长时间为准）内参加过其他药物临床试验且使用过研究药物"
    )
    assert _recover_exact_fragments(
        "随机前4周（小分子药物）", [source]
    ) == ["随机前", "4周（小分子药物）"]


def test_nonempty_schema_definition_is_not_silently_discarded():
    _source_input, draft, _spans = _fixture()
    payload = draft.model_dump(mode="json")
    payload["$defs"] = {"unexpected": {"type": "object"}}

    with pytest.raises(Exception, match="Extra inputs"):
        _parse_protocol_draft(__import__("json").dumps(payload))


def test_unambiguous_nested_exception_is_moved_to_component_level():
    _source_input, draft, _spans = _fixture()
    payload = draft.model_dump(mode="json")
    component = payload["proposed_rules"][0]["components"][0]
    component["expression"]["exception_expression"] = component["expression"].copy()

    parsed = _parse_protocol_draft(__import__("json").dumps(payload))

    assert parsed.proposed_rules[0].components[0].exception_expression is not None


def test_missing_numeric_unit_survives_as_gate_repair_marker():
    _source_input, draft, _spans = _fixture()
    payload = draft.model_dump(mode="json")
    predicate = payload["proposed_rules"][0]["components"][0]["expression"][
        "predicate"
    ]
    predicate.pop("unit")

    parsed = _parse_protocol_draft(__import__("json").dumps(payload))

    assert (
        parsed.proposed_rules[0].components[0].expression.predicate.unit
        == "__missing_from_agent__"
    )


def test_duplicate_single_source_clause_is_removed_when_list_contains_it():
    _source_input, draft, _spans = _fixture()
    payload = draft.model_dump(mode="json")
    predicate = payload["proposed_rules"][0]["components"][0]["expression"][
        "predicate"
    ]
    predicate["source_clause"] = "年龄≥18岁"
    predicate["source_clauses"] = ["年龄≥18岁", "包括边界值"]

    parsed = _parse_protocol_draft(__import__("json").dumps(payload))
    parsed_predicate = parsed.proposed_rules[0].components[0].expression.predicate

    assert parsed_predicate.source_clause is None
    assert parsed_predicate.source_clauses == ["年龄≥18岁", "包括边界值"]


def test_only_two_targeted_repairs_are_allowed():
    source_input, _draft, spans = _fixture()
    template = "按正式方案原文进行结构化解构。"
    transport = FakeTransport(
        [
            ProtocolAgentResponse(session_id="session-1", text="无效一"),
            ProtocolAgentResponse(session_id="session-1", text="无效二"),
            ProtocolAgentResponse(session_id="session-1", text="无效三"),
        ]
    )
    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )
    assert result.status == "需要核对"
    assert len(result.attempts) == 3
    assert len(transport.repair_prompts) == 2


def test_semantic_repairs_have_separate_bounded_budget():
    source_input, draft, spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    bad_candidate = candidate.model_copy(deep=True)
    bad_candidate.proposed_rules[1].components[0].expression.operator = (
        LogicalOperator.ALL
    )
    bad_repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[bad_candidate.proposed_rules[1]],
    )
    template = "按正式方案原文进行结构化解构。"
    transport = FakeTransport(
        [
            ProtocolAgentResponse(
                session_id="session-1", text=bad_candidate.model_dump_json()
            ),
            *[
                ProtocolAgentResponse(
                    session_id="session-1", text=bad_repair.model_dump_json()
                )
                for _ in range(12)
            ],
        ]
    )

    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )

    assert result.status == "需要核对"
    assert len(result.attempts) == 13
    assert len(transport.repair_prompts) == 12
    assert all("['EX-01']" in prompt for _, prompt in transport.repair_prompts)


def test_invalid_local_repair_gets_one_schema_retry_without_empty_issue_list():
    source_input, draft, spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    bad_candidate = candidate.model_copy(deep=True)
    bad_candidate.proposed_rules[1].components[0].expression.operator = (
        LogicalOperator.ALL
    )
    good_repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[candidate.proposed_rules[1]],
    )
    template = "按正式方案原文进行结构化解构。"
    transport = FakeTransport(
        [
            ProtocolAgentResponse(
                session_id="session-1", text=bad_candidate.model_dump_json()
            ),
            ProtocolAgentResponse(
                session_id="session-1",
                text=(
                    '{"candidate_id":"candidate-1",'
                    '"final_output":"repair"}'
                ),
            ),
            ProtocolAgentResponse(
                session_id="session-1", text=good_repair.model_dump_json()
            ),
        ]
    )

    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )

    assert result.status == "可以进入审阅"
    assert [item.outcome for item in result.attempts] == [
        "需要定向修正",
        "输出格式无效",
        "通过完整性检查",
    ]
    assert "AGENT_OUTPUT_SCHEMA_INVALID" in transport.repair_prompts[1][1]
    assert "重新输出完整 JSON 对象，不要附加说明：[]" not in (
        transport.repair_prompts[1][1]
    )


def test_repair_cannot_silently_switch_session():
    source_input, draft, spans = _fixture()
    template = "按正式方案原文进行结构化解构。"
    transport = FakeTransport(
        [
            ProtocolAgentResponse(session_id="session-1", text="无效"),
            ProtocolAgentResponse(
                session_id="session-2", text=draft.model_dump_json()
            ),
        ]
    )
    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )
    assert result.status == "需要核对"
    assert result.attempts[-1].outcome == "会话异常"
    assert result.same_session_id == "session-1"


def test_initial_transport_failure_returns_auditable_review_result():
    source_input, _draft, spans = _fixture()
    template = "按正式方案原文进行结构化解构。"
    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=FailingStartTransport(),
        source_spans=spans,
    )
    assert result.status == "需要核对"
    assert result.attempts[0].outcome == "会话异常"
    assert "上游连续返回空正文" in result.attempts[0].issues[0].problem


def test_repair_transport_failure_preserves_prior_draft_and_stops_cleanly():
    source_input, draft, spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    bad_candidate = candidate.model_copy(deep=True)
    bad_candidate.proposed_rules[1].components[0].expression.operator = (
        LogicalOperator.ALL
    )
    template = "按正式方案原文进行结构化解构。"
    transport = FailingRepairTransport(
        [
            ProtocolAgentResponse(
                session_id="session-1", text=bad_candidate.model_dump_json()
            )
        ]
    )
    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )
    assert result.status == "需要核对"
    assert [attempt.outcome for attempt in result.attempts] == [
        "需要定向修正",
        "会话异常",
    ]
    assert result.same_session_id == "session-1"
    assert result.final_draft is not None
    assert result.final_gate_result is not None
    assert result.final_draft.draft_id == result.attempts[0].draft_id
    assert result.final_gate_result.publishable is False
