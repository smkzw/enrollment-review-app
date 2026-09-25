"""Generic tests for the Phase 5.8c other-control Agent adapter.

These fixtures are synthetic.  They do not call a model, read a real protocol,
or write a project artifact.
"""

from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.agents.protocol_control_deconstructor import (
    CONTROL_AGENT_WIRE_VERSION,
    ProtocolControlAgentResponse,
    ProtocolControlAgentRunner,
    ProtocolControlAgentInput,
    ProtocolControlAgentWire,
    ProtocolControlAgentWireCandidate,
    ProtocolControlAgentWireConditionAtom,
    ProtocolControlAgentWireConditionDnf,
    ProtocolControlAgentWireConditionGroup,
    ProtocolControlAgentWireDisposition,
    ProtocolControlAgentWireEvidence,
    ProtocolControlAgentWireExceptionDnf,
    ProtocolControlAgentWireObligationAtom,
    ProtocolControlAgentWireContinuingObligation,
    ProtocolControlAgentWireObligationDnf,
    ProtocolControlAgentWireObligationGroup,
    ProtocolControlAgentWireRelation,
    ProtocolControlAgentWireValidationError,
    _candidate_ids_from_wire,
    _merge_candidate_repair,
    _merge_source_candidate_insert,
    _merge_post_treatment_scope_repair,
    _merge_future_prohibition_repair,
    _future_prohibition_repair_path,
    _future_observation_scope_repair_path,
    _early_anchor_atom_repair_path,
    _calendar_bound_repair_path,
    _merge_calendar_bound_repair,
    _merge_candidate_repairs,
    _merge_obligation_atom_repair,
    _merge_observation_policy_repair,
    _invalid_time_operand_paths,
    _merge_time_operand_repair,
    _invalid_observation_policy_paths,
    _build_observation_policy_repair_prompt,
    _invalid_evidence_source_policy_path,
    _build_evidence_source_policy_repair_prompt,
    _merge_evidence_source_policy_repair,
    _missing_evidence_source_type_paths,
    _merge_evidence_source_types_repair,
    _restore_bounded_wire_repair,
    _repair_problem_guidance,
    _invalid_candidate_payload,
    _single_invalid_candidate_payload,
    build_protocol_control_agent_prompt,
    build_protocol_control_repair_prompt,
    hydrate_protocol_control_agent_output,
    parse_protocol_control_agent_output,
    parse_protocol_control_agent_wire,
    protocol_control_agent_json_schema,
    protocol_control_agent_response_format,
    protocol_control_candidate_repair_response_format,
    protocol_control_post_treatment_repair_response_format,
    protocol_control_future_prohibition_repair_response_format,
    protocol_control_calendar_bound_repair_response_format,
    protocol_control_atom_repair_response_format,
    protocol_control_observation_repair_response_format,
    protocol_control_time_operand_repair_response_format,
    protocol_control_evidence_source_repair_response_format,
    source_statement_coverage,
    validate_protocol_control_agent_wire,
)
from app.agents.protocol_control_source_interpretation import (
    SOURCE_INTERPRETATION_VERSION,
    SOURCE_TARGET_REVIEW_VERSION,
    SourceInterpretation,
    SourceQuoteCorrection,
    SourceScopeCorrection,
    SourceStatementCoverage,
    SourceTargetReview,
    build_source_interpretation_prompt,
    apply_source_scope_correction,
    build_source_target_review_prompt,
    target_review_indexes,
    schedule_column_links,
    normalize_schedule_randomization_anchors,
    normalize_mixed_schedule_scopes,
    validate_source_interpretation,
    validate_source_target_review,
    _exception_in_target,
)
from app.agents.protocol_control_stage_compiler import (
    RELATIVE_STAGE_REQUIREMENT_VERSION,
    STAGE_BOUND_REQUIREMENT_VERSION,
    RelativeStageRequirement,
    StageBoundCompilationGap,
    StageBoundRequirement,
    can_compile_relative_stage_requirement,
    build_relative_stage_requirement_prompt,
    build_stage_bound_requirement_prompt,
    compile_stage_bound_requirement,
)
from app.domain.contracts.enums import PhaseScope, ReviewStage, StudyPhase
from app.domain.contracts.protocol_controls import (
    ControlContinuingObligation,
    ControlObligationKind,
    ControlRelationTargetKind,
    CrossSourceRelationKind,
    KnownOfficialRuleTarget,
    KnownRequiredProcedureTarget,
    KnownWorkflowStageTarget,
    ProtocolControlDispositionBatch,
    ProtocolStructureUnit,
    ReviewNodeRole,
    StructureUnitDispositionKind,
    TableCellContext,
)
from app.protocols.protocol_control_repair_errors import publication_repair_error


def test_continuing_obligation_wire_excludes_system_schema_version() -> None:
    wire = ProtocolControlAgentWireContinuingObligation(
        statement="治疗期间不得调整背景治疗",
        prospective_period={"period": "treatment_period"},
        source_span_ids=["span:control"],
        source_excerpts=["筛选期及治疗期间不得调整背景治疗"],
        status="not_due_at_review_node",
    )
    assert "schema_version" not in wire.model_dump()
    assert "schema_version" not in wire.model_json_schema().get("properties", {})
    saved = ControlContinuingObligation(**wire.model_dump())
    assert saved.status == "not_due_at_review_node"


def _unit(unit_id: str, order: int, span_id: str, excerpt: str) -> ProtocolStructureUnit:
    return ProtocolStructureUnit(
        structure_unit_id=unit_id,
        source_ref=f"generic.body.p{order}",
        member_source_refs=[f"generic.body.p{order}"],
        source_span_ids=[span_id],
        unit_kind="paragraph",
        heading_path=["其他方案控制"],
        source_order=order,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.SHARED],
        excerpt=excerpt,
    )


def _batch() -> ProtocolControlDispositionBatch:
    owned = [
        _unit("su-01", 1, "span:01", "其他控制：年龄至少18岁"),
        _unit("su-02", 2, "span:02", "其他控制：筛选时记录末次用药日期"),
    ]
    context = _unit("su-03", 3, "span:03", "只读上下文，不得处置")
    return ProtocolControlDispositionBatch(
        batch_id="pcb-generic-01",
        coverage_manifest_id="manifest:generic-01",
        protocol_version_id="protocol:generic-01",
        study_phase=StudyPhase.PHASE_II,
        batch_number=1,
        batch_total=1,
        owned_units=owned,
        context_units=[context],
        owned_structure_unit_ids=["su-01", "su-02"],
        context_structure_unit_ids=["su-03"],
        owned_source_span_ids=["span:01", "span:02"],
        context_source_span_ids=["span:03"],
        known_official_targets=[
            KnownOfficialRuleTarget(
                catalog_item_id="official-item-1",
                official_code="EX-01",
                label="既有官方排除标准",
                position=0,
                source_span_ids=["span:official"],
            )
        ],
        known_procedure_targets=[
            KnownRequiredProcedureTarget(
                catalog_item_id="procedure-screening-1",
                label="筛选期检查",
                visit_instance="screening-1",
                review_stage=ReviewStage.SCREENING,
                position=0,
                source_span_ids=["span:procedure"],
            )
        ],
        known_workflow_stage_targets=[
            KnownWorkflowStageTarget(
                workflow_stage_id="stage:screening:one",
                review_stage=ReviewStage.SCREENING,
                display_name="筛选期审核一",
                visit_instance="screening-1",
            ),
            KnownWorkflowStageTarget(
                workflow_stage_id="stage:screening:two",
                review_stage=ReviewStage.SCREENING,
                display_name="筛选期审核二",
                visit_instance="screening-2",
            ),
        ],
    )


def _condition(
    statement: str,
    span_id: str,
    excerpt: str,
) -> ProtocolControlAgentWireConditionAtom:
    return ProtocolControlAgentWireConditionAtom(
        statement=statement,
        evaluation=_evaluation(statement, span_id, excerpt),
        source_span_ids=[span_id],
        source_excerpts=[excerpt],
        time_constraint=None,
        requires_professional_judgment=False,
    )


def _evaluation(statement: str, span_id: str, excerpt: str) -> dict:
    # Adapter fixtures exercise wire/source integrity, not clinical acceptance.
    return {
        "determination_mode": "semantic",
        "proposition": statement,
        "time_purpose": "not_applicable",
        "repeat_scheme": None,
        "observation_policy": {
            "mode": "unresolved",
            "scope": "样例未说明采用哪次记录",
            "source_span_ids": [span_id],
            "source_excerpts": [excerpt],
        },
        "source_span_ids": [span_id],
        "source_excerpts": [excerpt],
    }


def _evidence_policy(span_id: str, excerpt: str) -> dict:
    return {
        "requires_contemporaneous_objective_source": None,
        "allows_screening_record_transcription": None,
        "result_validity_status": "not_specified",
        "result_validity_constraint": None,
        "source_span_ids": [span_id],
        "source_excerpts": [excerpt],
    }


def _timed_evaluation(statement: str, span_id: str, excerpt: str) -> dict:
    return {**_evaluation(statement, span_id, excerpt),
            "time_purpose": "unresolved", "time_operand_attribute": "date_range"}


def _replace_atom_source(atom: dict, span_id: str, excerpt: str) -> None:
    """Keep the wire internally valid so tests reach the external source check."""
    atom["source_span_ids"] = [span_id]
    atom["source_excerpts"] = [excerpt]
    atom["evaluation"] = _evaluation(atom["statement"], span_id, excerpt)


def _candidate() -> ProtocolControlAgentWireCandidate:
    return ProtocolControlAgentWireCandidate(
        title="年龄资料控制",
        repeat_trigger_conditions=[],
        applicable_population="拟入组受试者",
        applicability_expression=ProtocolControlAgentWireConditionDnf(
            groups=[
                ProtocolControlAgentWireConditionGroup(
                    atoms=[_condition("年龄条件", "span:01", "年龄至少18岁")]
                )
            ]
        ),
        trigger_expression=None,
        obligation_expression=ProtocolControlAgentWireObligationDnf(
            groups=[
                ProtocolControlAgentWireObligationGroup(
                    atoms=[
                        ProtocolControlAgentWireObligationAtom(
                            kind=ControlObligationKind.REACH_CONDITION,
                            statement="年龄达到18岁",
                            evaluation={
                                **_evaluation("年龄达到18岁", "span:01", "年龄至少18岁"),
                                "determination_mode": "deterministic",
                                "operation": "value_comparison",
                                "operand_attribute": "value",
                                "predicate": {
                                    "predicate_id": "age-threshold",
                                    "subject": "受试者",
                                    "attribute": "年龄",
                                    "comparator": "gte",
                                    "value": 18,
                                    "unit": "岁",
                                    "source_clause": "年龄至少18岁",
                                },
                            },
                            time_constraint=None,
                            prospective_period=None,
                            source_span_ids=["span:01"],
                            source_excerpts=["年龄至少18岁"],
                            requires_professional_judgment=False,
                        )
                    ]
                )
            ]
        ),
        exception_expression=ProtocolControlAgentWireExceptionDnf(
            groups=[
                ProtocolControlAgentWireConditionGroup(
                    atoms=[_condition("无例外", "span:01", "年龄至少18岁")]
                )
            ]
        ),
        review_node_bindings=[
            {
                "workflow_stage_id": "stage:screening:one",
                "review_stage": ReviewStage.SCREENING,
                "role": ReviewNodeRole.DECIDE_AT_NODE,
                "guidance": None,
            }
        ],
        minimum_evidence=[
            ProtocolControlAgentWireEvidence(
                fact_type="demographics",
                description="核对年龄资料",
                due_stage=ReviewStage.SCREENING,
                required_source_types=["原始资料"],
                workflow_stage_ids=["stage:screening:one"],
                source_policy={
                    "requires_contemporaneous_objective_source": None,
                    "allows_screening_record_transcription": None,
                    "result_validity_status": "not_specified",
                    "result_validity_constraint": None,
                    "source_span_ids": ["span:01"],
                    "source_excerpts": ["年龄至少18岁"],
                },
                atom_refs=[{"layer": "obligation", "group_index": 0, "atom_index": 0}],
            )
        ],
        source_structure_unit_ids=["su-01"],
        source_span_ids=["span:01"],
        cross_source_relations=[],
    )


def _wire(*, candidate: ProtocolControlAgentWireCandidate | None = None) -> ProtocolControlAgentWire:
    return ProtocolControlAgentWire(
        wire_version=CONTROL_AGENT_WIRE_VERSION,
        dispositions=[
            ProtocolControlAgentWireDisposition(
                structure_unit_id="su-01",
                disposition=(
                    StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
                    if candidate is not None
                    else StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT
                ),
                linked_official_code=None,
                linked_procedure_catalog_item_id=None,
                linked_procedure_catalog_item_ids=[],
                notes=None if candidate is not None else "仅作背景说明，不形成控制候选",
            ),
            ProtocolControlAgentWireDisposition(
                structure_unit_id="su-02",
                disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
                linked_official_code=None,
                linked_procedure_catalog_item_id=None,
                linked_procedure_catalog_item_ids=[],
                notes="仅作补充语境，不形成控制候选",
            ),
        ],
        candidate_drafts=[] if candidate is None else [candidate],
    )


def test_wire_is_provider_identity_free_and_schema_is_strict() -> None:
    wire = _wire(candidate=_candidate())
    payload = wire.model_dump(mode="json")
    assert "candidate_id" not in json.dumps(payload, ensure_ascii=False)
    assert protocol_control_agent_json_schema()["additionalProperties"] is False
    assert protocol_control_agent_response_format()["json_schema"]["strict"] is True
    with pytest.raises(ProtocolControlAgentWireValidationError, match="PROVIDER_ID_FORBIDDEN"):
        parse_protocol_control_agent_wire(
            json.dumps({**payload, "candidate_id": "provider-picked"}, ensure_ascii=False)
        )


def test_wire_fills_only_omitted_evaluation_sources_from_same_atom() -> None:
    payload = _wire(candidate=_candidate()).model_dump(mode="json")
    atom = payload["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]
    expected_spans = atom["source_span_ids"]
    expected_excerpts = atom["source_excerpts"]
    del atom["evaluation"]["source_span_ids"]
    del atom["evaluation"]["source_excerpts"]
    parsed = parse_protocol_control_agent_wire(json.dumps(payload, ensure_ascii=False))
    restored = parsed.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    assert restored.evaluation.source_span_ids == expected_spans
    assert restored.evaluation.source_excerpts == expected_excerpts

    payload["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]["evaluation"]["source_excerpts"] = ["不同的明确摘录"]
    with pytest.raises(ProtocolControlAgentWireValidationError, match="逐字原文"):
        parse_protocol_control_agent_wire(json.dumps(payload, ensure_ascii=False))


@pytest.mark.parametrize(
    ("days", "value", "unit", "canonicalized"),
    [(14, 14, "day", True), (14, 15, "day", False), (30, 1, "month", False)],
)
def test_only_identical_day_bounds_are_mechanically_collapsed(
    days: int, value: int, unit: str, canonicalized: bool,
) -> None:
    from app.agents.protocol_control_deconstructor import _collapse_exact_duplicate_day_bounds
    from app.domain.contracts.rules import TimeConstraint

    payload = {"time_constraint": {
        "anchor_type": "screening_date", "direction": "before",
        "upper_bound_days": days, "upper_bound": {"value": value, "unit": unit},
    }}
    _collapse_exact_duplicate_day_bounds(payload)
    assert ("upper_bound" not in payload["time_constraint"]) is canonicalized
    if canonicalized:
        assert TimeConstraint.model_validate(payload["time_constraint"]).upper_bound_days == days
    else:
        with pytest.raises(ValueError, match="时间窗上界不能同时使用"):
            TimeConstraint.model_validate(payload["time_constraint"])


def test_provider_schema_omits_unsupported_conditionals() -> None:
    schema = protocol_control_agent_json_schema()

    def keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value).union(*(keys(child) for child in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(child) for child in value))
        return set()

    assert {"if", "then", "else"}.isdisjoint(keys(schema))


def test_provider_schema_requires_time_bound_edge_semantics() -> None:
    schema_text = json.dumps(protocol_control_agent_json_schema(), ensure_ascii=False)

    assert '"lower_bound_inclusive"' in schema_text
    assert '"upper_bound_inclusive"' in schema_text


def test_required_procedure_disposition_preserves_all_visit_targets() -> None:
    batch = _batch().model_copy(
        update={
            "known_procedure_targets": [
                *_batch().known_procedure_targets,
                KnownRequiredProcedureTarget(
                    catalog_item_id="procedure-baseline-1",
                    label="基线检查",
                    visit_instance="baseline-1",
                    review_stage=ReviewStage.BASELINE,
                    position=1,
                    source_span_ids=["span:procedure-baseline"],
                ),
            ]
        }
    )
    payload = _wire().model_dump(mode="json")
    payload["dispositions"][0].update(
        disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE.value,
        linked_procedure_catalog_item_ids=[
            "procedure-baseline-1",
            "procedure-screening-1",
        ],
        notes="筛选与基线访视共同完整覆盖该结构单元",
    )
    wire = ProtocolControlAgentWire.model_validate(payload)

    hydrated = hydrate_protocol_control_agent_output(wire, batch)

    assert hydrated.dispositions[0].linked_procedure_catalog_item_id is None
    assert hydrated.dispositions[0].linked_procedure_catalog_item_ids == [
        "procedure-baseline-1",
        "procedure-screening-1",
    ]


@pytest.mark.parametrize(
    ("procedure_ids", "match"),
    [
        (["procedure-screening-1", "procedure-screening-1"], "排序且不得重复"),
        (["procedure-screening-1", "procedure-baseline-1"], "排序且不得重复"),
    ],
)
def test_required_procedure_disposition_rejects_duplicate_or_unsorted_targets(
    procedure_ids: list[str],
    match: str,
) -> None:
    payload = _wire().model_dump(mode="json")
    payload["dispositions"][0].update(
        disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE.value,
        linked_procedure_catalog_item_ids=procedure_ids,
    )

    with pytest.raises(ValidationError, match=match):
        ProtocolControlAgentWire.model_validate(payload)


def test_required_procedure_disposition_rejects_unknown_and_ambiguous_targets() -> None:
    payload = _wire().model_dump(mode="json")
    payload["dispositions"][0].update(
        disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE.value,
        linked_procedure_catalog_item_ids=["procedure-unknown"],
    )
    wire = ProtocolControlAgentWire.model_validate(payload)
    with pytest.raises(ProtocolControlAgentWireValidationError, match="UNKNOWN_PROCEDURE_TARGET"):
        hydrate_protocol_control_agent_output(wire, _batch())

    payload["dispositions"][0]["linked_procedure_catalog_item_id"] = (
        "procedure-screening-1"
    )
    with pytest.raises(ValidationError, match="不得同时使用"):
        ProtocolControlAgentWire.model_validate(payload)


def test_prompt_explains_parallel_sources_and_conditional_alternative_obligations() -> None:
    prompt = build_protocol_control_agent_prompt(_batch())

    assert "数量完全相等、位置一一对应" in prompt
    assert "重复填写该 source_span_id" in prompt
    assert "条件原子本身不得携带该后果的时间窗" in prompt
    assert "activates_obligation_group_indexes" in prompt
    assert "表示默认后果被替代的触发分支范围" in prompt
    assert "必须使用完全相同的分支序位" in prompt
    assert "prospective_period=study_period" in prompt
    assert "不得只把持续终点留在标题、说明或摘录中" in prompt
    assert "不得只给锚点和方向而把数值留空" in prompt
    assert "超过/>N" in prompt
    assert "lower_bound_inclusive=false" in prompt
    assert "不超过/≤N/N以内" in prompt
    assert "后者是前者的明确特例" in prompt
    assert "不得把通用窗口传播到这些特例项目" in prompt
    assert "不重复建立特例义务" in prompt
    assert "都必须在该原子自己的 source_excerpts 中" in prompt
    assert "替代义务仍必须保留原持续期间" in prompt
    assert "同时引用缩短后起始窗口" in prompt
    assert "必须指向替代义务组本身" in prompt
    assert "共享一个后果" in prompt
    assert "只列出一组条件及其后续操作" in prompt
    assert "最小连续原文" in prompt
    assert "applicability_expression 只表达适用人群" in prompt
    assert "一个候选只表达一个最终决定阶段" in prompt
    assert "必须按最终决定阶段拆成多个候选" in prompt
    assert "新候选只保留未被覆盖的" in prompt
    assert "due_stage 与该 review_stage 一致" in prompt
    assert "输出前按以下顺序自检" in prompt
    assert "最终判定节点和最低证据" in prompt
    assert "按最终决定阶段分成两个候选" in prompt
    assert "必须将 owned 原文与已知目标摘录逐项比对" in prompt
    assert "目标缺少的任何项必须留在增量候选中" in prompt
    assert "独立动作谓词" in prompt
    assert "前置动作已被覆盖" in prompt
    assert "候选义务只保留未覆盖的动作" in prompt
    assert "评估维度" in prompt
    assert "量表量程或理论取值范围" in prompt
    assert "不是普通背景说明" in prompt
    assert "适用的冻结访视集合不同" in prompt
    assert "必须分成独立候选" in prompt
    assert "使用 complete_before_anchor" in prompt
    assert "不得改写为 schedule_or_verify_visit" in prompt
    assert "12）逐个核对独立动作谓词" in prompt
    assert "不得因二者同属 baseline 而退化为普通基线" in prompt
    assert "只覆盖其 visit_instance 指明的访视" in prompt
    assert "所有具有 visit_instance 的冻结访视节点分别作本节点判定" in prompt
    assert "10）原文若要求在计划访视执行" in prompt
    assert "不得发明未冻结的治疗期访视" in prompt
    assert "未列入链接目标的访视宣称为已覆盖" in prompt
    assert "trigger_expression 必须为 null" in prompt
    assert "不得为了连接义务而虚构触发分支" in prompt
    assert "必须至少保留一个已知目标未覆盖的义务增量" in prompt
    assert "删除重复操作候选" in prompt
    assert "不得以‘维持完整控制链’" in prompt
    assert "‘可进行/允许进行’表示可选操作" in prompt
    assert "‘无需/不要求执行’表示免除该要求" in prompt
    assert "‘不得随机/不得给药’描述锚点事件本身" in prompt
    assert "原文明确仅属于其他期别的内容不得成为本期候选" in prompt
    assert "应处置为 post_treatment_execution" in prompt
    assert "表述粒度不同本身不构成控制增量" in prompt
    assert "只读上下文可以帮助解释术语、访视和重复关系，但它本身不是已发布目标" in prompt
    assert "只读上下文出现相似或重复表述" in prompt
    assert "即使其偏离本身不直接触发入排失败" in prompt
    assert "同一要求也适用于治疗期访视" in prompt
    assert "不得要求当前受试者证明未来没有发生变化" in prompt


@pytest.mark.parametrize(
    ("problem", "expected"),
    [
        (
            "CONDITIONAL_BRANCH_MAPPING_INVALID: 多组条件未分别映射",
            "用一个义务组绑定全部触发分支",
        ),
        (
            "MIXED_DECISION_STAGE_CONTROL: 当前操作与后续有效性混合",
            "不得因此重复建立已由已知目标覆盖的操作候选",
        ),
        (
            "ROUTINE_OBLIGATION_MISLABELED_AS_TRIGGER: 常规检查误作触发",
            "应删除候选并将单元处置为 post_treatment_execution",
        ),
        (
            "DNF_DUPLICATE_ATOM: 义务组内重复",
            "只保留一项",
        ),
        (
            "EXCEPTION_LAYER_MISSING: 例外未拆分",
            "移入 exception_expression",
        ),
        (
            "OPTIONAL_ACTION_MODALITY_DROPPED: 可选语气丢失",
            "不得把可选操作改写成必做操作",
        ),
        (
            "PROHIBITED_EVENT_ANCHOR_MISMATCH: 事件锚点错误",
            "direction=on",
        ),
        (
            "TIME_ANCHOR_GUESSED_FROM_SCREENING: 混合时点污染",
            "不能让一个分支摘录夹带另一个时点",
        ),
        (
            "TIME_ANCHOR_MISSING: 时间性原子缺少锚点",
            "相对较晚锚点的 before 时间约束",
        ),
        (
            "TIME_BOUND_COMPARATOR_MISMATCH: 时间边界被改写",
            "不得把开区间改成闭区间",
        ),
        (
            "PROSPECTIVE_PERIOD_MISSING: 持续期间缺失",
            "若只是首次给药后的检查或随访，则删除候选",
        ),
        (
            "FUTURE_PROHIBITION_DECIDED_EARLY: 后续遵守不能提前证明",
            "statement 和 evaluation.proposition 均只陈述截至决定节点可核的行为",
        ),
        (
            "RECOMMENDED_MODALITY_DROPPED: 建议动作被写成强制",
            "必做原子不能连带引用后续的建议措辞",
        ),
        (
            "WIRE_SCHEMA_INVALID: 比较条件必须保留求值规格内的逐字原文",
            "source_term 不能代替 predicate 的逐字来源",
        ),
        (
            "CONTROL_DELTA_DROPPED: 控制增量遗漏",
            "只为目标确实未覆盖的人群、条件、动作、时间、阈值或例外建立增量候选",
        ),
        (
            "CONTROL_DELTA_COMPONENT_DROPPED: 来源要素遗漏",
            "保留原文直接规定的全部记录或执行要素",
        ),
        (
            "MIXED_TRIGGER_DECISION_STAGES: 筛选与基线触发混合",
            "不得把筛选失败降为提前关注",
        ),
        (
            "EXEMPTION_MODALITY_OVERSTATED: 豁免被强化",
            "不得使用 prohibit_event",
        ),
        (
            "CONTROL_DUPLICATE_RETAINED: 重复候选",
            "该单元的入排相关内容已被已知目标完整覆盖",
        ),
        (
            "COVERED_BRANCH_DUPLICATED: 已覆盖分支重复",
            "只在增量候选中保留目标未覆盖的分支",
        ),
        (
            "CANDIDATE_MISSING: 其他控制候选处置没有对应候选草稿",
            "不得只在 notes 中描述候选",
        ),
        (
            "FABRICATED_EXCERPT: obligation 原子 0 的摘录不是来源 span:01 的连续原文",
            "原子摘录（source_excerpts）必须从授权结构单元的冻结原文（excerpt）中逐字复制连续文本片段",
        ),
        (
            "SOURCE_SCOPE_ESCAPE: obligation 原子引用了本批 owned 之外的来源：span:99",
            "所有原子引用的来源定位（source_span_ids）必须属于本批授权结构单元的来源闭包",
        ),
    ],
)
def test_repair_prompt_explains_incremental_candidate_shape(
    problem: str,
    expected: str,
) -> None:
    prompt = build_protocol_control_repair_prompt(_batch(), problem=problem)

    assert expected in prompt


def test_repair_prompt_reuses_prior_schema_and_keeps_time_corrections_bounded() -> None:
    batch = _batch()
    without_time = build_protocol_control_repair_prompt(
        batch,
        problem="未给出时间约束，不能声明已确定其计算用途",
    )
    future_anchor = build_protocol_control_repair_prompt(
        batch,
        problem="未来计划窗只允许研究药物给药日、末次给药日或研究完成日",
    )

    assert "not_applicable 或 unresolved" in without_time
    assert "不得为了让规格通过而补造" in without_time
    combined = build_protocol_control_repair_prompt(
        batch,
        problem=(
            "普通值比较不能冒充日期间隔或书面判断计算；"
            "未给出时间约束，不能声明已确定其计算用途"
        ),
    )
    assert "operand_attribute 必须为 value" in combined
    assert "not_applicable 或 unresolved" in combined
    assert "筛选、基线和随机日期不能放入" in future_anchor
    assert "严格遵守本请求随附的 JSON Schema" in future_anchor
    assert '"$defs"' not in without_time
    assert '"$defs"' not in future_anchor


def test_planned_visit_and_evidence_repairs_preserve_node_closure() -> None:
    planned_visit_prompt = build_protocol_control_repair_prompt(
        _batch(),
        problem="PLANNED_VISIT_SCOPE_DROPPED",
    )
    assert "分别作本节点判定" in planned_visit_prompt
    assert "不得发明目录外节点" in planned_visit_prompt

    evidence_prompt = build_protocol_control_repair_prompt(
        _batch(),
        problem="DECISION_STAGE_EVIDENCE_MISSING",
    )
    assert "同阶段到期的最低证据" in evidence_prompt
    assert "不得删除决定节点" in evidence_prompt


def test_repair_prompt_keeps_frozen_node_identity_and_evaluation_mode() -> None:
    batch = _batch().model_copy(
        update={
            "known_workflow_stage_targets": [
                KnownWorkflowStageTarget(
                    workflow_stage_id="workflow-stage-generic-baseline",
                    review_stage=ReviewStage.BASELINE,
                    display_name="基线访视",
                )
            ]
        }
    )
    visit_prompt = build_protocol_control_repair_prompt(
        batch,
        problem="VISIT_SCHEDULE_WORKFLOW_TARGET_MISSING",
    )
    evaluation_prompt = build_protocol_control_repair_prompt(
        batch,
        problem="确定性求值须声明计算方式，其他模式不得夹带计算方式",
    )

    assert "workflow-stage-generic-baseline" in visit_prompt
    assert "cross_source_relations 留空仍不合格" in visit_prompt
    assert "不得为通过格式校验虚构计算方式" in evaluation_prompt


def test_deep_prompt_keeps_table_column_positions_distinct_from_nonempty_count() -> None:
    prompt = build_protocol_control_agent_prompt(_batch())

    assert "member_source_refs 中的 .r行.c列" in prompt
    assert "不得把后面非空格的值左移" in prompt


def test_prompt_separates_rule_authority_from_subject_evidence() -> None:
    prompt = build_protocol_control_agent_prompt(_batch())

    assert "是控制规则的权威依据，不是某名受试者" in prompt
    assert "只能列受试者层面的实际记录" in prompt
    assert "患者自填/自评问卷" in prompt
    assert "不得为纯患者自填/自评工具额外要求研究者评估记录" in prompt
    assert "该义务自己的 source_excerpts 必须同时包含" in prompt

    authority_prompt = build_protocol_control_repair_prompt(
        _batch(),
        problem="MINIMUM_EVIDENCE_AUTHORITY_SOURCE_CONFLATED",
    )
    assert "不是受试者个例证据" in authority_prompt

    judgment_prompt = build_protocol_control_repair_prompt(
        _batch(),
        problem="SELF_REPORTED_TOOL_MARKED_PROFESSIONAL",
    )
    assert "患者自填或自评问卷不属于研究者专业判断" in judgment_prompt

    researcher_evidence_prompt = build_protocol_control_repair_prompt(
        _batch(),
        problem="SELF_REPORTED_TOOL_RESEARCHER_EVIDENCE",
    )
    assert "不得额外要求研究者评估记录" in researcher_evidence_prompt

    provenance_prompt = build_protocol_control_repair_prompt(
        _batch(),
        problem="AUTHORITY_REFERENCE_SOURCE_DROPPED",
    )
    assert "该义务自己的 source_excerpts" in provenance_prompt


def test_repair_prompt_attaches_only_authorized_structure_units_closure() -> None:
    batch = _batch()
    prompt_single = build_protocol_control_repair_prompt(
        batch,
        problem="FABRICATED_EXCERPT: obligation 原子 0 的摘录不是来源 span:01 的连续原文",
        structure_unit_ids=["su-01"],
    )
    assert "其他控制：年龄至少18岁" in prompt_single
    assert "span:01" in prompt_single
    assert "其他控制：筛选时记录末次用药日期" not in prompt_single
    assert "只读上下文" not in prompt_single
    assert "标点、引号和空格均保持原样" in prompt_single
    assert '"source_ref": "generic.body.p1"' in prompt_single

    prompt_all = build_protocol_control_repair_prompt(
        batch,
        problem="FABRICATED_EXCERPT: obligation 原子 0 的摘录不是来源 span:01 的连续原文",
    )
    assert "其他控制：年龄至少18岁" in prompt_all
    assert "其他控制：筛选时记录末次用药日期" in prompt_all
    assert "只读上下文" not in prompt_all


def test_repair_prompt_preserves_curved_quotes_and_strict_validation_rejects_altered_quotes() -> None:
    ecg_excerpt = (
        "12导联心电图检查前参与者至少静息10 min。记录12导联心电图诊断结果、心率、"
        "PR间期、RR间期、QRS、QT间期，并应用Fridericia’s公式计算心率校正计算QTcF。"
    )
    unit = _unit("su-ecg-01", 10, "span:ecg-01", ecg_excerpt)
    batch = ProtocolControlDispositionBatch(
        batch_id="pcb-ecg-01",
        coverage_manifest_id="manifest:ecg-01",
        protocol_version_id="protocol:ecg-01",
        study_phase=StudyPhase.PHASE_II,
        batch_number=1,
        batch_total=1,
        owned_units=[unit],
        context_units=[],
        owned_structure_unit_ids=["su-ecg-01"],
        context_structure_unit_ids=[],
        owned_source_span_ids=["span:ecg-01"],
        context_source_span_ids=[],
        known_workflow_stage_targets=[
            KnownWorkflowStageTarget(
                workflow_stage_id="flow-screening",
                display_name="筛选期",
                review_stage=ReviewStage.SCREENING,
            )
        ],
    )

    valid_candidate = ProtocolControlAgentWireCandidate(
        title="心电图计算控制",
        repeat_trigger_conditions=[],
        applicable_population="拟入组受试者",
        applicability_expression=None,
        trigger_expression=None,
        obligation_expression=ProtocolControlAgentWireObligationDnf(
            groups=[
                ProtocolControlAgentWireObligationGroup(
                    atoms=[
                        ProtocolControlAgentWireObligationAtom(
                            kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                            statement="应用Fridericia’s公式计算心率校正计算QTcF",
                            evaluation=_evaluation("核对计算方法", "span:ecg-01", "并应用Fridericia’s公式计算心率校正计算QTcF。"),
                            time_constraint=None,
                            prospective_period=None,
                            source_span_ids=["span:ecg-01"],
                            source_excerpts=["并应用Fridericia’s公式计算心率校正计算QTcF。"],
                            requires_professional_judgment=False,
                        )
                    ]
                )
            ]
        ),
        exception_expression=None,
        review_node_bindings=[
            {
                "workflow_stage_id": "flow-screening",
                "review_stage": ReviewStage.SCREENING,
                "role": ReviewNodeRole.DECIDE_AT_NODE,
                "guidance": None,
            }
        ],
        minimum_evidence=[
            ProtocolControlAgentWireEvidence(
                fact_type="ecg",
                description="心电图核对",
                due_stage=ReviewStage.SCREENING,
                required_source_types=["原始资料"],
                workflow_stage_ids=["flow-screening"],
                source_policy=_evidence_policy("span:ecg-01", "并应用Fridericia’s公式计算心率校正计算QTcF。"),
                atom_refs=[{"layer": "obligation", "group_index": 0, "atom_index": 0}],
            )
        ],
        source_structure_unit_ids=["su-ecg-01"],
        source_span_ids=["span:ecg-01"],
        cross_source_relations=[],
    )
    valid_wire = ProtocolControlAgentWire(
        wire_version=CONTROL_AGENT_WIRE_VERSION,
        dispositions=[
            ProtocolControlAgentWireDisposition(
                structure_unit_id="su-ecg-01",
                disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                linked_official_code=None,
                linked_procedure_catalog_item_id=None,
                linked_procedure_catalog_item_ids=[],
                notes="心电图计算增量",
            )
        ],
        candidate_drafts=[valid_candidate],
    )
    hydrated = hydrate_protocol_control_agent_output(valid_wire, batch)
    assert len(hydrated.candidates) == 1
    altered_candidate = ProtocolControlAgentWireCandidate(
        title="心电图计算控制",
        repeat_trigger_conditions=[],
        applicable_population="拟入组受试者",
        applicability_expression=None,
        trigger_expression=None,
        obligation_expression=ProtocolControlAgentWireObligationDnf(
            groups=[
                ProtocolControlAgentWireObligationGroup(
                    atoms=[
                        ProtocolControlAgentWireObligationAtom(
                            kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                            statement="应用Fridericia's公式计算心率校正计算QTcF",
                            evaluation=_evaluation("核对计算方法", "span:ecg-01", "并应用Fridericia's公式计算心率校正计算QTcF。"),
                            time_constraint=None,
                            prospective_period=None,
                            source_span_ids=["span:ecg-01"],
                            source_excerpts=["并应用Fridericia's公式计算心率校正计算QTcF。"],
                            requires_professional_judgment=False,
                        )
                    ]
                )
            ]
        ),
        exception_expression=None,
        review_node_bindings=[
            {
                "workflow_stage_id": "flow-screening",
                "review_stage": ReviewStage.SCREENING,
                "role": ReviewNodeRole.DECIDE_AT_NODE,
                "guidance": None,
            }
        ],
        minimum_evidence=[
            ProtocolControlAgentWireEvidence(
                fact_type="ecg",
                description="心电图核对",
                due_stage=ReviewStage.SCREENING,
                required_source_types=["原始资料"],
                workflow_stage_ids=["flow-screening"],
                source_policy=_evidence_policy("span:ecg-01", "并应用Fridericia's公式计算心率校正计算QTcF。"),
                atom_refs=[{"layer": "obligation", "group_index": 0, "atom_index": 0}],
            )
        ],
        source_structure_unit_ids=["su-ecg-01"],
        source_span_ids=["span:ecg-01"],
        cross_source_relations=[],
    )
    altered_wire = ProtocolControlAgentWire(
        wire_version=CONTROL_AGENT_WIRE_VERSION,
        dispositions=[
            ProtocolControlAgentWireDisposition(
                structure_unit_id="su-ecg-01",
                disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                linked_official_code=None,
                linked_procedure_catalog_item_id=None,
                linked_procedure_catalog_item_ids=[],
                notes="心电图计算增量",
            )
        ],
        candidate_drafts=[altered_candidate],
    )
    # Curved ↔ straight quote is the only allowed typographic restoration.
    # Straight apostrophe must be deterministically restored to the frozen curved
    # excerpt when the normalized match is unique and contiguous; raw output hash
    # remains the straight-quote text for audit, so strict hydration now succeeds.
    hydrated_altered = hydrate_protocol_control_agent_output(altered_wire, batch)
    assert len(hydrated_altered.candidates) == 1
    restored_excerpt = hydrated_altered.candidates[0].semantics.obligation_expression.groups[0].atoms[0].source_excerpts[0]
    assert restored_excerpt == "并应用Fridericia’s公式计算心率校正计算QTcF。"
    assert "Fridericia’s" in restored_excerpt
    # Non-quote differences remain strict and must still fail.
    non_quote_candidate = ProtocolControlAgentWireCandidate(
        title="心电图计算控制",
        repeat_trigger_conditions=[],
        applicable_population="拟入组受试者",
        applicability_expression=None,
        trigger_expression=None,
        obligation_expression=ProtocolControlAgentWireObligationDnf(
            groups=[
                ProtocolControlAgentWireObligationGroup(
                    atoms=[
                        ProtocolControlAgentWireObligationAtom(
                            kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                            statement="应用Fridericia公式计算心率校正计算QTcF",
                            evaluation=_evaluation("核对计算方法", "span:ecg-01", "并应用FridericiaX公式计算心率校正计算QTcF。"),
                            time_constraint=None,
                            prospective_period=None,
                            source_span_ids=["span:ecg-01"],
                            source_excerpts=["并应用FridericiaX公式计算心率校正计算QTcF。"],
                            requires_professional_judgment=False,
                        )
                    ]
                )
            ]
        ),
        exception_expression=None,
        review_node_bindings=[
            {
                "workflow_stage_id": "flow-screening",
                "review_stage": ReviewStage.SCREENING,
                "role": ReviewNodeRole.DECIDE_AT_NODE,
                "guidance": None,
            }
        ],
        minimum_evidence=[
            ProtocolControlAgentWireEvidence(
                fact_type="ecg",
                description="心电图核对",
                due_stage=ReviewStage.SCREENING,
                required_source_types=["原始资料"],
                workflow_stage_ids=["flow-screening"],
                source_policy=_evidence_policy("span:ecg-01", "并应用FridericiaX公式计算心率校正计算QTcF。"),
                atom_refs=[{"layer": "obligation", "group_index": 0, "atom_index": 0}],
            )
        ],
        source_structure_unit_ids=["su-ecg-01"],
        source_span_ids=["span:ecg-01"],
        cross_source_relations=[],
    )
    non_quote_wire = ProtocolControlAgentWire(
        wire_version=CONTROL_AGENT_WIRE_VERSION,
        dispositions=[
            ProtocolControlAgentWireDisposition(
                structure_unit_id="su-ecg-01",
                disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                linked_official_code=None,
                linked_procedure_catalog_item_id=None,
                linked_procedure_catalog_item_ids=[],
                notes="心电图计算增量",
            )
        ],
        candidate_drafts=[non_quote_candidate],
    )
    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="FABRICATED_EXCERPT",
    ):
        hydrate_protocol_control_agent_output(non_quote_wire, batch)
    repair_prompt = build_protocol_control_repair_prompt(
        batch,
        problem="FABRICATED_EXCERPT: obligation 原子 0 的摘录不是来源 span:ecg-01 的连续原文",
        structure_unit_ids=["su-ecg-01"],
    )
    assert "Fridericia’s" in repair_prompt
    assert "并为 FABRICATED_EXCERPT 提供逐字复制指引" not in repair_prompt
    assert "标点、引号和空格均保持原样" in repair_prompt


def test_hydration_injects_candidate_and_atom_ids_and_keeps_layers_separate() -> None:
    batch = _batch()
    wire = _wire(candidate=_candidate())
    hydrated = hydrate_protocol_control_agent_output(wire, batch)
    assert len(hydrated.candidates) == 1
    candidate = hydrated.candidates[0]
    assert candidate.control_candidate_id.startswith("pcc-")
    assert candidate.semantics is not None
    assert candidate.semantics.control_candidate_id == candidate.control_candidate_id
    assert candidate.semantics.applicability_expression is not None
    assert candidate.semantics.trigger_expression is None
    assert candidate.semantics.exception_expression is not None
    atom_id = candidate.semantics.obligation_expression.groups[0].atoms[0].obligation_id
    assert atom_id.startswith("pca-")
    assert _candidate_ids_from_wire(wire, batch) == [candidate.control_candidate_id]
    assert all(
        "candidate_id" not in key
        for key in _wire(candidate=_candidate()).model_dump(mode="json")
    )


def test_no_candidate_requires_explicit_non_control_reason() -> None:
    batch = _batch()
    payload = _wire().model_dump(mode="json")
    payload["dispositions"][1]["notes"] = None
    with pytest.raises(ProtocolControlAgentWireValidationError, match="NON_CONTROL_REASON_MISSING"):
        hydrate_protocol_control_agent_output(json.dumps(payload, ensure_ascii=False), batch)

    accepted = hydrate_protocol_control_agent_output(json.dumps(_wire().model_dump(mode="json"), ensure_ascii=False), batch)
    assert accepted.candidates == []

    official_only = _wire().model_dump(mode="json")
    for disposition in official_only["dispositions"]:
        disposition["disposition"] = StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY.value
        disposition["linked_official_code"] = "EX-01"
        disposition["notes"] = None
    official_result = hydrate_protocol_control_agent_output(
        json.dumps(official_only, ensure_ascii=False), batch
    )
    assert official_result.candidates == []


def test_partial_batch_context_overlap_and_candidate_source_escape_are_rejected() -> None:
    batch = _batch()
    partial = _wire(candidate=_candidate()).model_dump(mode="json")
    partial["dispositions"] = partial["dispositions"][:1]
    with pytest.raises(ProtocolControlAgentWireValidationError, match="PARTIAL_BATCH"):
        hydrate_protocol_control_agent_output(json.dumps(partial, ensure_ascii=False), batch)

    escaped = _candidate().model_dump(mode="json")
    escaped["source_structure_unit_ids"] = ["su-03"]
    escaped["source_span_ids"] = ["span:03"]
    escaped["applicability_expression"]["groups"][0]["atoms"][0]["source_span_ids"] = ["span:03"]
    escaped["applicability_expression"]["groups"][0]["atoms"][0]["source_excerpts"] = ["只读上下文"]
    escaped["obligation_expression"]["groups"][0]["atoms"][0]["source_span_ids"] = ["span:03"]
    escaped["obligation_expression"]["groups"][0]["atoms"][0]["source_excerpts"] = ["只读上下文"]
    escaped["exception_expression"]["groups"][0]["atoms"][0]["source_span_ids"] = ["span:03"]
    escaped["exception_expression"]["groups"][0]["atoms"][0]["source_excerpts"] = ["只读上下文"]
    for layer in ("applicability", "obligation", "exception"):
        _replace_atom_source(escaped[f"{layer}_expression"]["groups"][0]["atoms"][0], "span:03", "只读上下文")
    escaped_wire = {
        **_wire().model_dump(mode="json"),
        "dispositions": [
            {
                **_wire().model_dump(mode="json")["dispositions"][0],
                "disposition": StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value,
            },
            _wire().model_dump(mode="json")["dispositions"][1],
        ],
        "candidate_drafts": [escaped],
    }
    with pytest.raises(ProtocolControlAgentWireValidationError, match="CANDIDATE_UNIT_SCOPE_ESCAPE"):
        hydrate_protocol_control_agent_output(json.dumps(escaped_wire, ensure_ascii=False), batch)

    borrowed = _candidate().model_dump(mode="json")
    borrowed["source_span_ids"] = ["span:02"]
    borrowed["applicability_expression"]["groups"][0]["atoms"][0]["source_span_ids"] = ["span:02"]
    borrowed["applicability_expression"]["groups"][0]["atoms"][0]["source_excerpts"] = [
        "筛选时记录末次用药日期"
    ]
    borrowed["obligation_expression"]["groups"][0]["atoms"][0]["source_span_ids"] = ["span:02"]
    borrowed["obligation_expression"]["groups"][0]["atoms"][0]["source_excerpts"] = [
        "筛选时记录末次用药日期"
    ]
    borrowed["exception_expression"]["groups"][0]["atoms"][0]["source_span_ids"] = ["span:02"]
    borrowed["exception_expression"]["groups"][0]["atoms"][0]["source_excerpts"] = [
        "筛选时记录末次用药日期"
    ]
    for layer in ("applicability", "obligation", "exception"):
        _replace_atom_source(borrowed[f"{layer}_expression"]["groups"][0]["atoms"][0], "span:02", "筛选时记录末次用药日期")
    borrowed_candidate = ProtocolControlAgentWireCandidate.model_validate(borrowed)
    borrowed_wire = _wire(candidate=borrowed_candidate)
    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="CANDIDATE_SOURCE_UNIT_SCOPE_ESCAPE",
    ):
        hydrate_protocol_control_agent_output(borrowed_wire, batch)


def test_fabricated_excerpt_empty_group_and_unknown_target_are_rejected() -> None:
    batch = _batch()
    fabricated = _candidate().model_dump(mode="json")
    fabricated["obligation_expression"]["groups"][0]["atoms"][0]["source_excerpts"] = ["模型编造的年龄"]
    _replace_atom_source(fabricated["obligation_expression"]["groups"][0]["atoms"][0], "span:01", "模型编造的年龄")
    payload = {
        **_wire().model_dump(mode="json"),
        "dispositions": [
            {
                **_wire().model_dump(mode="json")["dispositions"][0],
                "disposition": StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value,
            },
            _wire().model_dump(mode="json")["dispositions"][1],
        ],
        "candidate_drafts": [fabricated],
    }
    with pytest.raises(ProtocolControlAgentWireValidationError, match="FABRICATED_EXCERPT"):
        hydrate_protocol_control_agent_output(json.dumps(payload, ensure_ascii=False), batch)

    empty = _candidate().model_dump(mode="json")
    empty["applicability_expression"]["groups"] = []
    with pytest.raises(ValidationError):
        ProtocolControlAgentWireCandidate.model_validate(empty)

    ambiguous_nodes = _candidate().model_dump(mode="json")
    ambiguous_nodes["review_node_bindings"].append(
        {
            "workflow_stage_id": "stage:screening:one",
            "review_stage": ReviewStage.SCREENING.value,
            "role": ReviewNodeRole.EARLY_ATTENTION.value,
            "guidance": None,
        }
    )
    with pytest.raises(ValidationError, match="多个不同作用"):
        ProtocolControlAgentWireCandidate.model_validate(ambiguous_nodes)

    relation = ProtocolControlAgentWireRelation(
        kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
        external_target_kind=ControlRelationTargetKind.OFFICIAL_RULE,
        external_target_id="EX-99",
        candidate_side="left",
        affected_workflow_stage_id=None,
        notes=None,
    )
    unknown_candidate = _candidate().model_copy(update={"cross_source_relations": [relation]})
    unknown_wire = _wire(candidate=unknown_candidate)
    with pytest.raises(ProtocolControlAgentWireValidationError, match="UNKNOWN_OFFICIAL_TARGET"):
        hydrate_protocol_control_agent_output(unknown_wire.model_dump_json(), batch)


def test_workflow_stage_catalog_is_frozen_and_review_stage_must_match() -> None:
    batch = _batch()
    second_visit = _candidate().model_dump(mode="json")
    second_visit["review_node_bindings"][0]["workflow_stage_id"] = "stage:screening:two"
    second_visit_candidate = ProtocolControlAgentWireCandidate.model_validate(second_visit)
    hydrated_second_visit = hydrate_protocol_control_agent_output(
        _wire(candidate=second_visit_candidate), batch
    )
    assert (
        hydrated_second_visit.candidates[0].semantics.review_node_bindings[0].workflow_stage_id
        == "stage:screening:two"
    )

    wrong_stage = _candidate().model_dump(mode="json")
    wrong_stage["review_node_bindings"][0]["review_stage"] = ReviewStage.BASELINE.value
    wrong_candidate = ProtocolControlAgentWireCandidate.model_validate(wrong_stage)
    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="WORKFLOW_REVIEW_STAGE_MISMATCH",
    ):
        hydrate_protocol_control_agent_output(_wire(candidate=wrong_candidate), batch)

    unknown_stage = _candidate().model_dump(mode="json")
    unknown_stage["review_node_bindings"][0]["workflow_stage_id"] = "stage:invented"
    unknown_candidate = ProtocolControlAgentWireCandidate.model_validate(unknown_stage)
    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="UNKNOWN_WORKFLOW_STAGE_TARGET",
    ):
        hydrate_protocol_control_agent_output(_wire(candidate=unknown_candidate), batch)

    without_catalog = batch.model_copy(update={"known_workflow_stage_targets": []})
    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="WORKFLOW_TARGET_CATALOG_MISSING",
    ):
        hydrate_protocol_control_agent_output(_wire(candidate=_candidate()), without_catalog)


def test_candidate_excerpt_must_match_candidate_owned_unit_when_span_is_shared() -> None:
    shared_batch = ProtocolControlDispositionBatch(
        batch_id="pcb-generic-shared-span",
        coverage_manifest_id="manifest:generic-shared-span",
        protocol_version_id="protocol:generic-01",
        study_phase=StudyPhase.PHASE_II,
        batch_number=1,
        batch_total=1,
        owned_units=[
            _unit("su-01", 1, "span:shared", "候选所属原文"),
            _unit("su-02", 2, "span:shared", "另一 owned 单元原文"),
        ],
        context_units=[],
        owned_structure_unit_ids=["su-01", "su-02"],
        context_structure_unit_ids=[],
        owned_source_span_ids=["span:shared"],
        context_source_span_ids=[],
        known_workflow_stage_targets=_batch().known_workflow_stage_targets,
    )
    borrowed = _candidate().model_dump(mode="json")
    borrowed["source_span_ids"] = ["span:shared"]
    for expression_key in (
        "applicability_expression",
        "obligation_expression",
        "exception_expression",
    ):
        atom = borrowed[expression_key]["groups"][0]["atoms"][0]
        atom["source_span_ids"] = ["span:shared"]
        atom["source_excerpts"] = ["另一 owned 单元原文"]
        _replace_atom_source(atom, "span:shared", "另一 owned 单元原文")
    borrowed_candidate = ProtocolControlAgentWireCandidate.model_validate(borrowed)
    with pytest.raises(ProtocolControlAgentWireValidationError, match="FABRICATED_EXCERPT"):
        hydrate_protocol_control_agent_output(_wire(candidate=borrowed_candidate), shared_batch)


def test_relation_hydration_injects_current_candidate_and_preserves_direction() -> None:
    batch = _batch()
    relation = ProtocolControlAgentWireRelation(
        kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
        external_target_kind=ControlRelationTargetKind.OFFICIAL_RULE,
        external_target_id="EX-01",
        candidate_side="right",
        affected_workflow_stage_id=None,
        notes="官方规则只作已知关系目标",
    )
    candidate = _candidate().model_copy(update={"cross_source_relations": [relation]})
    hydrated = hydrate_protocol_control_agent_output(_wire(candidate=candidate), batch)
    hydrated_relation = hydrated.candidates[0].semantics.cross_source_relations[0]
    assert hydrated_relation.left_target_kind == ControlRelationTargetKind.OFFICIAL_RULE
    assert hydrated_relation.left_target_id == "EX-01"
    assert hydrated_relation.right_target_kind == ControlRelationTargetKind.CONTROL_CANDIDATE
    assert hydrated_relation.right_target_id == hydrated.candidates[0].control_candidate_id


def test_supplementary_procedure_relation_uses_exact_visit_node() -> None:
    batch = _batch()
    relation = ProtocolControlAgentWireRelation(
        kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
        external_target_kind=ControlRelationTargetKind.REQUIRED_PROCEDURE,
        external_target_id="procedure-screening-1",
        candidate_side="left",
        affected_workflow_stage_id="stage:screening:one",
        notes="补充筛选访视的既有检查后果",
    )
    candidate = _candidate().model_copy(update={"cross_source_relations": [relation]})
    hydrated = hydrate_protocol_control_agent_output(_wire(candidate=candidate), batch)
    hydrated_relation = hydrated.candidates[0].semantics.cross_source_relations[0]
    assert (
        hydrated_relation.affected_workflow_stage_id
        == "stage:screening:one"
    )

    wrong_visit = relation.model_copy(
        update={"affected_workflow_stage_id": "stage:screening:two"}
    )
    candidate = _candidate().model_copy(
        update={"cross_source_relations": [wrong_visit]}
    )
    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="PROCEDURE_AFFECTED_STAGE_MISMATCH",
    ) as rejected:
        hydrate_protocol_control_agent_output(_wire(candidate=candidate), batch)
    assert rejected.value.candidate_indexes == (0,)

    with pytest.raises(ValidationError, match="首次受影响"):
        ProtocolControlAgentWireRelation(
            kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
            external_target_kind=ControlRelationTargetKind.REQUIRED_PROCEDURE,
            external_target_id="procedure-screening-1",
            candidate_side="left",
            affected_workflow_stage_id=None,
            notes="缺少节点",
        )


def test_temporal_obligation_kinds_keep_visit_validity_and_baseline_scope_separate() -> None:
    batch = _batch()
    payload = _candidate().model_dump(mode="json")
    atom = payload["obligation_expression"]["groups"][0]["atoms"][0]
    atom.update(
        kind=ControlObligationKind.COMPLETE_OR_VERIFY.value,
        time_constraint={
            "anchor_type": "screening_date",
            "direction": "before",
            "upper_bound_days": 7,
        },
    )
    atom["evaluation"] = _timed_evaluation(atom["statement"], "span:01", "年龄至少18岁")
    with pytest.raises(ValidationError, match="具体操作持续期"):
        ProtocolControlAgentWireCandidate.model_validate(payload)

    atom.update(
        kind=ControlObligationKind.COMPLETE_BEFORE_ANCHOR.value,
        time_constraint={
            "anchor_type": "screening_date",
            "direction": "before",
        },
    )
    ProtocolControlAgentWireCandidate.model_validate(payload)

    atom["time_constraint"] = None
    atom["evaluation"]["time_operand_attribute"] = None
    with pytest.raises(ValidationError, match="节点前完成义务"):
        ProtocolControlAgentWireCandidate.model_validate(payload)

    atom["time_constraint"] = {
        "anchor_type": "screening_date",
        "direction": "after",
    }
    atom["evaluation"]["time_operand_attribute"] = "date_range"
    with pytest.raises(ValidationError, match="方向必须为 before"):
        ProtocolControlAgentWireCandidate.model_validate(payload)

    atom.update(
        kind=ControlObligationKind.SCHEDULE_OR_VERIFY_VISIT.value,
        time_constraint=None,
    )
    atom["evaluation"]["time_operand_attribute"] = None
    payload["cross_source_relations"] = [
        {
            "kind": CrossSourceRelationKind.FURTHER_EXPLANATION.value,
            "external_target_kind": ControlRelationTargetKind.WORKFLOW_STAGE.value,
            "external_target_id": "stage:screening:one",
            "candidate_side": "left",
            "affected_workflow_stage_id": None,
            "notes": "补充筛选访视安排",
        }
    ]
    visit_candidate = ProtocolControlAgentWireCandidate.model_validate(payload)
    hydrated = hydrate_protocol_control_agent_output(
        _wire(candidate=visit_candidate), batch
    )
    relation = hydrated.candidates[0].semantics.cross_source_relations[0]
    assert relation.right_target_kind == ControlRelationTargetKind.WORKFLOW_STAGE
    assert relation.right_target_id == "stage:screening:one"

    payload["cross_source_relations"] = [
        {
            "kind": CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT.value,
            "external_target_kind": ControlRelationTargetKind.REQUIRED_PROCEDURE.value,
            "external_target_id": "procedure-screening-1",
            "candidate_side": "left",
            "affected_workflow_stage_id": "stage:screening:one",
            "notes": "把通用访视窗错误挂到单个检查项",
        }
    ]
    too_narrow = ProtocolControlAgentWireCandidate.model_validate(payload)
    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="VISIT_SCHEDULE_TARGET_TOO_NARROW",
    ):
        hydrate_protocol_control_agent_output(_wire(candidate=too_narrow), batch)

    atom.update(
        kind=ControlObligationKind.SELECT_BASELINE_VALUE.value,
        time_constraint=None,
    )
    payload["cross_source_relations"].append(
        {
            "kind": CrossSourceRelationKind.FURTHER_EXPLANATION.value,
            "external_target_kind": ControlRelationTargetKind.WORKFLOW_STAGE.value,
            "external_target_id": "stage:screening:one",
            "candidate_side": "left",
            "affected_workflow_stage_id": None,
            "notes": "通用基线值原则",
        }
    )
    mixed_baseline_scope = ProtocolControlAgentWireCandidate.model_validate(payload)
    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="BASELINE_VALUE_SCOPE_MIXED",
    ):
        hydrate_protocol_control_agent_output(
            _wire(candidate=mixed_baseline_scope), batch
        )


def test_action_specific_duration_needs_semantic_interval_not_one_value_match() -> None:
    excerpt = "自筛选日起按规定治疗持续7天"
    evaluation = _evaluation(excerpt, "span:treatment", excerpt)
    evaluation.update(time_purpose="interval_condition", time_operand_attribute="date_range")
    atom = ProtocolControlAgentWireObligationAtom(
        kind=ControlObligationKind.COMPLETE_OR_VERIFY,
        statement=excerpt,
        evaluation=evaluation,
        time_constraint={"anchor_type": "screening_date", "direction": "after", "upper_bound_days": 7},
        prospective_period=None,
        source_span_ids=["span:treatment"],
        source_excerpts=[excerpt],
        requires_professional_judgment=False,
    )
    assert atom.evaluation.determination_mode == "semantic"
    with pytest.raises(ValidationError, match="不得以单次值比较证明全程完成"):
        ProtocolControlAgentWireObligationAtom.model_validate(
            {**atom.model_dump(mode="json"), "evaluation": {
                **atom.evaluation.model_dump(mode="json"),
                "determination_mode": "deterministic",
                "operation": "time_constraint",
                "operand_attribute": "date_range",
                "time_operand_attribute": None,
            }}
        )


def test_candidate_source_identity_lists_are_canonicalized_without_changing_excerpts() -> None:
    raw = _candidate().model_dump(mode="json")
    original_excerpt = raw["obligation_expression"]["groups"][0]["atoms"][0]["source_excerpts"]
    raw["source_structure_unit_ids"] = ["su-01", "su-01"]
    raw["source_span_ids"] = ["span:02", "span:01", "span:01"]
    parsed = ProtocolControlAgentWireCandidate.model_validate(raw)
    assert parsed.source_structure_unit_ids == ["su-01"]
    assert parsed.source_span_ids == ["span:01", "span:02"]
    assert parsed.obligation_expression.groups[0].atoms[0].source_excerpts == original_excerpt


def test_result_validity_requires_exact_procedure_target() -> None:
    payload = _candidate().model_dump(mode="json")
    atom = payload["obligation_expression"]["groups"][0]["atoms"][0]
    atom["evaluation"] = _timed_evaluation(atom["statement"], "span:01", "年龄至少18岁")
    atom.update(
        kind=ControlObligationKind.VERIFY_RESULT_VALIDITY.value,
        time_constraint={
            "anchor_type": "screening_date",
            "direction": "before",
            "upper_bound_days": 7,
        },
    )
    candidate = ProtocolControlAgentWireCandidate.model_validate(payload)
    with pytest.raises(
        ProtocolControlAgentWireValidationError,
        match="RESULT_VALIDITY_PROCEDURE_TARGET_MISSING",
    ):
        hydrate_protocol_control_agent_output(_wire(candidate=candidate), _batch())

    payload["cross_source_relations"] = [
        {
            "kind": CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT.value,
            "external_target_kind": ControlRelationTargetKind.REQUIRED_PROCEDURE.value,
            "external_target_id": "procedure-screening-1",
            "candidate_side": "left",
            "affected_workflow_stage_id": "stage:screening:one",
            "notes": "补充检查结果有效期",
        }
    ]
    candidate = ProtocolControlAgentWireCandidate.model_validate(payload)
    hydrated = hydrate_protocol_control_agent_output(
        _wire(candidate=candidate), _batch()
    )
    assert (
        hydrated.candidates[0]
        .semantics.obligation_expression.groups[0]
        .atoms[0]
        .kind
        == ControlObligationKind.VERIFY_RESULT_VALIDITY
    )


def test_prompt_explains_non_official_supplement_and_read_only_context() -> None:
    prompt = build_protocol_control_agent_prompt(_batch())
    assert "补充" in prompt and "重复表述" in prompt
    assert "不会因此成为新的 IN/EX" in prompt
    assert "非控制理由" in prompt
    assert "context_units仅作只读上下文，不能处置、不能转移所有权" in prompt
    assert "stage:screening:one" in prompt and "screening-2" in prompt
    assert "不得发明、改写或新建节点身份" in prompt
    assert "affected_workflow_stage_id" in prompt
    assert "不得用更晚访视目标承接较早筛选影响" in prompt
    assert "schedule_or_verify_visit" in prompt
    assert "verify_result_validity" in prompt
    assert "select_baseline_value" in prompt
    assert "通用访视安排必须关联" in prompt
    agent_input = ProtocolControlAgentInput.from_batch(_batch())
    assert [item.workflow_stage_id for item in agent_input.known_workflow_stage_targets] == [
        "stage:screening:one",
        "stage:screening:two",
    ]


def test_prompt_schema_only_omits_generated_titles() -> None:
    prompt = build_protocol_control_agent_prompt(_batch())
    schema_text = prompt.split("输出结构：", 1)[1].split("\n\n本次冻结输入：", 1)[0]
    supplied = json.loads(schema_text)

    def without_titles(value):
        if isinstance(value, dict):
            return {key: without_titles(item) for key, item in value.items() if key != "title"}
        if isinstance(value, list):
            return [without_titles(item) for item in value]
        return value

    assert supplied == without_titles(protocol_control_agent_json_schema())
    assert len(schema_text) < len(json.dumps(protocol_control_agent_json_schema(), ensure_ascii=False))


class _FakeTransport:
    def __init__(self, responses: list[ProtocolControlAgentResponse]) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    def start(self, *, prompt: str) -> ProtocolControlAgentResponse:
        self.prompts.append(prompt)
        return self.responses.pop(0)

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
    ) -> ProtocolControlAgentResponse:
        self.prompts.append(prompt)
        response = self.responses.pop(0)
        assert response.session_id == session_id
        return response


def test_source_interpretation_is_source_bound_and_not_a_rule() -> None:
    batch = _batch()
    payload = {
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
            {"structure_unit_id": "su-01", "quoted_text": "年龄至少18岁", "force": "required", "time_words": []},
            {"structure_unit_id": "su-02", "quoted_text": "筛选时记录末次用药日期", "force": "required", "time_words": ["筛选时"]},
        ],
        "units_without_statement": [],
    }
    inventory = SourceInterpretation.model_validate(payload)
    validate_source_interpretation(batch, inventory)
    assert '"time_words":[]' in build_source_interpretation_prompt(batch)
    prompt_input = json.loads(build_source_interpretation_prompt(batch).split("冻结来源：", 1)[1])
    assert [item["structure_unit_id"] for item in prompt_input["owned"]] == ["su-01", "su-02"]
    payload["statements"][1]["quoted_text"] = "筛选前六个月内停止治疗"
    with pytest.raises(ValueError, match="不属于冻结来源"):
        validate_source_interpretation(batch, SourceInterpretation.model_validate(payload))
    payload["statements"][1]["quoted_text"] = "筛选时记录末次用药日期"
    payload["statements"][1]["time_words"] = ["筛选时", "治疗后六周"]
    with pytest.raises(ValueError, match="时间措辞不属于本条陈述"):
        validate_source_interpretation(batch, SourceInterpretation.model_validate(payload))
    payload["statements"][1]["time_words"] = ["筛选时", "末次用药日期"]
    validate_source_interpretation(batch, SourceInterpretation.model_validate(payload))
    payload["statements"][1]["quoted_text"] = "末次用药日期"
    payload["statements"][1]["time_words"] = ["筛选时"]
    with pytest.raises(ValueError, match="时间措辞不属于本条陈述"):
        validate_source_interpretation(batch, SourceInterpretation.model_validate(payload))


def test_shared_scope_must_precede_the_action_and_survive_target_review() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[1].excerpt = (
        "筛选期（D-7~D-1）：记录末次用药日期；治疗后七天核对其他资料。"
    )
    payload = {
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-02",
            "quoted_text": "记录末次用药日期",
            "scope_quote": "筛选期（D-7~D-1）",
            "force": "required",
            "affected_stage": "筛选期",
            "time_words": ["筛选期（D-7~D-1）"],
        }],
        "units_without_statement": ["su-01"],
    }
    validate_source_interpretation(batch, SourceInterpretation.model_validate(payload))
    payload["statements"][0]["quoted_text"] = "筛选期（D-7~D-1）：记录末次用药日期"
    validate_source_interpretation(batch, SourceInterpretation.model_validate(payload))
    payload["statements"][0]["quoted_text"] = "记录末次用药日期"
    payload["statements"][0]["scope_quote"] = "治疗后七天"
    with pytest.raises(ValueError, match="共享范围须来自陈述之前"):
        validate_source_interpretation(batch, SourceInterpretation.model_validate(payload))
    payload["statements"][0]["scope_quote"] = "筛选期（D-7~D-1）"
    payload["statements"][0]["time_words"] = []
    with pytest.raises(ValueError, match="明确阶段范围不得从时间措辞中遗漏"):
        validate_source_interpretation(batch, SourceInterpretation.model_validate(payload))
    payload["statements"][0]["affected_stage"] = None
    payload["statements"][0]["quoted_text"] = "治疗后七天核对其他资料"
    payload["statements"][0]["time_words"] = ["治疗后七天"]
    validate_source_interpretation(batch, SourceInterpretation.model_validate(payload))


def test_shared_scope_can_quote_the_owned_table_row_header() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].table_context = TableCellContext(
        table_path=(1, 1), row_index=1, column_index=1,
        member_cell_paths=[(1, 1)], row_headers=["本行适用范围"],
    )
    payload = {
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-01", "quoted_text": "年龄至少18岁",
            "scope_quote": "本行适用范围", "force": "required", "time_words": [],
        }],
        "units_without_statement": ["su-02"],
    }
    validate_source_interpretation(batch, SourceInterpretation.model_validate(payload))
    payload["statements"][0]["scope_quote"] = "相邻行适用范围"
    with pytest.raises(ValueError, match="共享范围须来自"):
        validate_source_interpretation(batch, SourceInterpretation.model_validate(payload))


def test_repair_guidance_distinguishes_same_stage_and_cross_stage() -> None:
    same = _repair_problem_guidance(
        "PROCEDURE_AFFECTED_STAGE_MISMATCH: 补充关系的受影响审核节点与所引用流程必做访视不一致"
    )
    cross = _repair_problem_guidance(
        "PROCEDURE_AFFECTED_STAGE_MISMATCH: 跨阶段后续控制补充的受影响审核节点必须晚于流程必做执行访视"
    )
    assert "同阶段流程补充" in same
    assert "后续最终判定节点" in cross
    assert "同阶段流程补充" not in cross
    calendar = _repair_problem_guidance(
        "TIME_CALENDAR_BOUND_MISSING: 义务原文含明确日历时长，但结构化时间窗未保存该数值和单位"
    )
    assert "数值、单位" in calendar
    assert "末次给药" not in calendar


def test_real_transport_inventory_is_checked_before_full_wire() -> None:
    batch = _batch()
    source = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
            {"structure_unit_id": "su-01", "quoted_text": "年龄至少18岁", "force": "required", "time_words": []},
            {"structure_unit_id": "su-02", "quoted_text": "筛选时记录末次用药日期", "force": "required", "time_words": ["筛选时"]},
        ],
        "units_without_statement": [],
    })

    class InventoryTransport(_FakeTransport):
        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.prompts.append(prompt)
            return ProtocolControlAgentResponse(
                session_id="source-session", text=source.model_dump_json()
            )

    transport = InventoryTransport([
        ProtocolControlAgentResponse(session_id="full-session", text=_wire().model_dump_json())
    ])
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert result.status == "需要核对"
    assert result.source_interpretation == source
    assert [item.status for item in result.source_statement_coverage] == [
        "not_located", "not_located",
    ]
    assert "已逐字定位的来源陈述" in transport.prompts[1]
    assert result.attempts[-1].error_classes == ["SOURCE_TARGET_REVIEW_TRANSPORT_FAILED"]
    assert result.final_output is None


def test_invalid_source_inventory_keeps_response_session_identity() -> None:
    class InvalidInventoryTransport(_FakeTransport):
        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(
                session_id="source-receipt-1", text='{"statements":[]}'
            )

    result = ProtocolControlAgentRunner().run(_batch(), InvalidInventoryTransport([]))
    assert result.status == "需要核对"
    assert result.session_id == "source-receipt-1"
    assert result.attempts[0].outcome == "schema_invalid"


def test_source_inventory_rechecks_unlocated_scope_once_without_inventing_it() -> None:
    valid = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": "年龄至少18岁",
                        "force": "required", "time_words": []}],
        "units_without_statement": ["su-02"],
    })
    invalid = valid.model_copy(deep=True)
    invalid.statements[0].scope_quote = "不存在的适用范围"

    class SourceTransport(_FakeTransport):
        def __init__(self) -> None:
            super().__init__([ProtocolControlAgentResponse(
                session_id="wire-session", text=_wire(candidate=_candidate()).model_dump_json()
            )])
            self.source_prompts: list[str] = []

        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.source_prompts.append(prompt)
            result = invalid if len(self.source_prompts) == 1 else valid
            return ProtocolControlAgentResponse(
                session_id="source-session", text=result.model_dump_json()
            )

    transport = SourceTransport()
    result = ProtocolControlAgentRunner().run(_batch(), transport)
    assert result.status == "已解析"
    assert len(transport.source_prompts) == 2
    assert "上一轮有源陈述未通过" in transport.source_prompts[1]
    assert result.attempts[0].outcome == "schema_invalid"
    assert result.source_interpretation == valid


def test_source_inventory_corrects_one_nearby_quote_without_rewriting_batch() -> None:
    invalid = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": "年龄至少18周岁",
                        "force": "required", "time_words": []}],
        "units_without_statement": ["su-02"],
    })

    class SourceTransport(_FakeTransport):
        def __init__(self) -> None:
            super().__init__([ProtocolControlAgentResponse(
                session_id="wire-session", text=_wire(candidate=_candidate()).model_dump_json()
            )])
            self.source_calls = 0

        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.source_calls += 1
            return ProtocolControlAgentResponse(session_id="source-session", text=invalid.model_dump_json())

        def correct_source_quote(self, *, prompt: str) -> ProtocolControlAgentResponse:
            assert "年龄至少18周岁" in prompt
            return ProtocolControlAgentResponse(session_id="quote-session", text=SourceQuoteCorrection(
                version="phase5/control-source-quote-correction/v1",
                structure_unit_id="su-01", corrected_quote="年龄至少18岁", unresolved=None,
            ).model_dump_json())

    transport = SourceTransport()
    result = ProtocolControlAgentRunner().run(_batch(), transport)
    assert result.status == "已解析"
    assert transport.source_calls == 1
    assert result.source_interpretation.statements[0].quoted_text == "年龄至少18岁"
    assert [item.outcome for item in result.attempts[:2]] == ["schema_invalid", "parsed"]


def test_source_inventory_rejects_quote_correction_that_changes_number() -> None:
    invalid = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": "年龄至少16岁",
                        "force": "required", "time_words": []}],
        "units_without_statement": ["su-02"],
    })

    class SourceTransport(_FakeTransport):
        def __init__(self) -> None:
            super().__init__([])
            self.source_calls = 0

        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.source_calls += 1
            return ProtocolControlAgentResponse(session_id="source-session", text=invalid.model_dump_json())

        def correct_source_quote(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="quote-session", text=SourceQuoteCorrection(
                version="phase5/control-source-quote-correction/v1",
                structure_unit_id="su-01", corrected_quote="年龄至少18岁", unresolved=None,
            ).model_dump_json())

    transport = SourceTransport()
    result = ProtocolControlAgentRunner().run(_batch(), transport)
    assert result.status == "需要核对"
    assert transport.source_calls == 2
    assert any("不能证明是同一来源要求" in issue
               for attempt in result.attempts for issue in attempt.issues)


def test_source_coverage_requires_direct_atom_quote_not_candidate_unit_only() -> None:
    batch = _batch()
    inventory = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
            {"structure_unit_id": "su-01", "quoted_text": "年龄至少18岁", "force": "required", "time_words": []},
            {"structure_unit_id": "su-02", "quoted_text": "筛选时记录末次用药日期", "force": "required", "time_words": ["筛选时"]},
        ],
        "units_without_statement": [],
    })
    wire = _wire(candidate=_candidate())
    entries = source_statement_coverage(batch, inventory, wire)
    assert [(item.status, item.candidate_indexes) for item in entries] == [
        ("expressed", [0]),
        ("not_located", []),
    ]
    assert entries[0].linked_candidate_indexes == [0]
    assert "obligation" in entries[0].matched_roles
    assert entries[0].linked_official_code is None
    assert entries[0].linked_procedure_target_ids == []
    assert entries[0].exact_official_excerpt_matches == []

    quoted_target = batch.known_official_targets[0].model_copy(
        update={"source_excerpts": ["年龄至少18岁"]}
    )
    target_batch = batch.model_copy(update={"known_official_targets": [quoted_target]})
    target_entries = source_statement_coverage(target_batch, inventory, wire)
    assert target_entries[0].exact_official_excerpt_matches == ["EX-01"]
    assert target_entries[0].linked_official_code is None

    trigger_only = _candidate().model_copy(deep=True)
    trigger_only.obligation_expression.groups[0].atoms[0].source_excerpts = ["另一个要求"]
    trigger_entries = source_statement_coverage(batch, inventory, _wire(candidate=trigger_only))
    assert trigger_entries[0].status == "candidate_linked"
    assert "applicability" in trigger_entries[0].matched_roles
    assert "obligation" not in trigger_entries[0].matched_roles

    wider_inventory = inventory.model_copy(deep=True)
    wider_inventory.statements[0].quoted_text = "其他控制"
    wider_inventory.statements[0].force = "descriptive"
    validate_source_interpretation(batch, wider_inventory)
    unresolved = source_statement_coverage(batch, wider_inventory, wire)
    assert unresolved[0].status == "candidate_linked"
    assert unresolved[0].linked_candidate_indexes == [0]

    partial_inventory = inventory.model_copy(deep=True)
    partial_inventory.statements[0].quoted_text = "其他控制：年龄至少18岁"
    validate_source_interpretation(batch, partial_inventory)
    partial = source_statement_coverage(batch, partial_inventory, wire)
    assert partial[0].status == "candidate_linked"
    assert "obligation" not in partial[0].matched_roles

    blank_inventory = inventory.model_copy(deep=True)
    blank_inventory.statements[0].quoted_text = "  \n  "
    with pytest.raises(ValueError, match="不得只有空白"):
        validate_source_interpretation(batch, blank_inventory)


def test_source_declared_acronym_preserves_exception_without_specific_alias_table() -> None:
    source = "[白内障摘除术或者激光辅助原位角膜磨削术（Laser in Situ Keratomileusis，LASIK）除外]"
    target = "开放性眼部手术史（白内障摘除术或者LASIK除外）；"
    assert _exception_in_target(source, target)
    assert not _exception_in_target(source, "开放性眼部手术史（白内障摘除术或者其他手术除外）；")
    assert not _exception_in_target(source, "开放性眼部手术史（LASIK除外）；")
    assert not _exception_in_target("[白内障摘除术或者另一手术除外]", target)
    two_aliases = (
        "快速血浆反应素环状卡片试验（Rapid Plasma Reagin，RPR）或"
        "甲苯胺红不加热血清试验（Toluidine Red Unheated Serum Test，TRUST）阴性者除外"
    )
    assert _exception_in_target(two_aliases, "筛选时TP-Ab阳性者，RPR或TRUST阴性者除外；")
    assert not _exception_in_target(two_aliases, "筛选时TP-Ab阳性者，RPR或TRUST阳性者除外；")


def test_source_target_review_requires_real_target_excerpts_and_matching_time() -> None:
    batch = _batch().model_copy(deep=True)
    batch.known_official_targets[0].source_excerpts = ["年龄至少18岁"]
    batch.known_procedure_targets[0].source_excerpts = ["记录末次用药日期"]
    batch.known_procedure_targets[0].visit_instance = "筛选时"
    inventory = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
            {"structure_unit_id": "su-01", "quoted_text": "其他控制：年龄至少18岁", "force": "required", "time_words": []},
            {"structure_unit_id": "su-02", "quoted_text": "筛选时记录末次用药日期", "force": "required", "time_words": ["筛选时"]},
        ],
        "units_without_statement": [],
    })
    coverage = [
        SourceStatementCoverage(statement_index=index, structure_unit_id=f"su-0{index + 1}",
                                disposition="other_control_candidate", status="candidate_linked")
        for index in range(2)
    ]
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [
            {"statement_index": 0, "decision": "covered_by_official", "target_id": "EX-01",
             "source_action_excerpt": "年龄至少18岁", "target_action_excerpt": "年龄至少18岁",
             "source_time_excerpt": None, "target_time_excerpt": None, "unresolved_aspects": []},
            {"statement_index": 1, "decision": "covered_by_procedure", "target_id": "procedure-screening-1",
             "source_action_excerpt": "记录末次用药日期", "target_action_excerpt": "记录末次用药日期",
             "source_time_excerpt": "筛选时", "target_time_excerpt": "筛选时", "unresolved_aspects": []},
        ],
    })
    assert target_review_indexes(inventory, coverage) == [0, 1]
    validate_source_target_review(batch, inventory, coverage, review)

    longer_batch = batch.model_copy(deep=True)
    longer_batch.owned_units[1].excerpt = "筛选时连续7天记录末次用药日期"
    longer_inventory = inventory.model_copy(deep=True)
    longer_inventory.statements[1].quoted_text = longer_batch.owned_units[1].excerpt
    longer_inventory.statements[1].time_words = ["筛选时", "7天"]
    validate_source_interpretation(longer_batch, longer_inventory)
    with pytest.raises(ValueError, match="时间要求未在目标原文逐项覆盖"):
        validate_source_target_review(longer_batch, longer_inventory, coverage, review)

    matching_batch = longer_batch.model_copy(deep=True)
    matching_batch.known_procedure_targets[0].source_excerpts = [
        "筛选时连续7天记录末次用药日期"
    ]
    matching_review = review.model_copy(deep=True)
    matching_review.items[1].source_time_excerpt = "筛选时连续7天"
    matching_review.items[1].target_time_excerpt = "筛选时连续7天"
    matching_review.items[1].target_action_excerpt = "记录末次用药日期"
    validate_source_target_review(
        matching_batch, longer_inventory, coverage, matching_review
    )
    matching_review.items[1].source_time_excerpt = "筛选时连续8天"
    with pytest.raises(ValueError, match="时间措辞不属于该陈述"):
        validate_source_target_review(
            matching_batch, longer_inventory, coverage, matching_review
        )

    borrowed_time = review.model_copy(deep=True)
    borrowed_time.items[1].target_time_excerpt = "基线时"
    with pytest.raises(ValueError, match="目标时间缺少原文或访视定位"):
        validate_source_target_review(batch, inventory, coverage, borrowed_time)

    invented_target = review.model_copy(deep=True)
    invented_target.items[0].target_id = "EX-99"
    with pytest.raises(ValueError, match="非冻结或不唯一的目标"):
        validate_source_target_review(batch, inventory, coverage, invented_target)

    missing_statement = review.model_copy(deep=True)
    missing_statement.items.pop()
    with pytest.raises(ValueError, match="必须且只能覆盖"):
        validate_source_target_review(batch, inventory, coverage, missing_statement)

    partial = review.model_copy(deep=True)
    partial.items[1].decision = "additional_requirement"
    partial.items[1].target_time_excerpt = None
    partial.items[1].unresolved_aspects = ["已有动作，但未核实时间是否相同"]
    validate_source_target_review(batch, inventory, coverage, partial)

    partial_without_reason = partial.model_copy(deep=True)
    partial_without_reason.items[1].unresolved_aspects = []
    with pytest.raises(ValueError, match="必须说明待核实"):
        validate_source_target_review(batch, inventory, coverage, partial_without_reason)

    partial_wrong_target = partial.model_copy(deep=True)
    partial_wrong_target.items[1].target_id = "procedure-not-in-batch"
    with pytest.raises(ValueError, match="非冻结或不唯一的目标"):
        validate_source_target_review(batch, inventory, coverage, partial_wrong_target)

    partial_invented_time = partial.model_copy(deep=True)
    partial_invented_time.items[1].target_time_excerpt = "随机后"
    with pytest.raises(ValueError, match="目标时间缺少原文"):
        validate_source_target_review(batch, inventory, coverage, partial_invented_time)

    linked = [item.model_copy(deep=True) for item in coverage]
    linked[0].status = "linked_only"
    linked[0].disposition = "official_eligibility"
    linked[0].linked_official_code = "EX-other"
    with pytest.raises(ValueError, match="覆盖目标与草稿链接不一致"):
        validate_source_target_review(batch, inventory, linked, review)
    linked[0].linked_official_code = "EX-01"
    validate_source_target_review(batch, inventory, linked, review)
    assert '"linked_official_code": "EX-01"' in build_source_target_review_prompt(
        batch, inventory, linked
    )


def test_source_target_review_accepts_only_verified_shared_time_scope() -> None:
    batch = _batch().model_copy(deep=True)
    period = "整个研究期间（从签署知情同意到末次给药后6个月）"
    action = "受试者及其伴侣同意采取避孕措施"
    batch.owned_units[1].excerpt = f"{period}，{action}"
    batch.known_procedure_targets[0].source_excerpts = [f"{period}，{action}"]
    inventory = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-02", "quoted_text": action,
            "scope_quote": period, "force": "required",
            "time_words": ["整个研究期间", "从签署知情同意到末次给药后6个月"],
        }],
        "units_without_statement": ["su-01"],
    })
    validate_source_interpretation(batch, inventory)
    coverage = [SourceStatementCoverage(
        statement_index=0, structure_unit_id="su-02",
        disposition="other_control_candidate", status="candidate_linked",
    )]
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{
            "statement_index": 0, "decision": "covered_by_procedure",
            "target_id": "procedure-screening-1",
            "source_action_excerpt": action, "target_action_excerpt": action,
            "source_time_excerpt": period, "target_time_excerpt": period,
            "unresolved_aspects": [],
        }],
    })
    validate_source_target_review(batch, inventory, coverage, review)

    borrowed = inventory.model_copy(deep=True)
    borrowed.statements[0].scope_quote = "相邻条目的治疗期间"
    with pytest.raises(ValueError, match="共享范围"):
        validate_source_interpretation(batch, borrowed)

    absent_target_time = batch.model_copy(deep=True)
    absent_target_time.known_procedure_targets[0].source_excerpts = [action]
    with pytest.raises(ValueError, match="目标时间缺少原文或访视定位"):
        validate_source_target_review(absent_target_time, inventory, coverage, review)


def test_source_scope_correction_is_local_and_preserves_direct_time() -> None:
    batch = _batch().model_copy(deep=True)
    original = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-02",
            "quoted_text": "筛选时记录末次用药日期",
            "scope_quote": "相邻条目的治疗期",
            "force": "required", "time_words": ["筛选时", "治疗期"],
        }],
        "units_without_statement": ["su-01"],
    })
    corrected = SourceScopeCorrection.model_validate({
        "version": "phase5/control-source-scope-correction/v1",
        "structure_unit_id": "su-02", "scope_quote": None,
        "affected_stage": None, "time_words": ["筛选时"], "unresolved": None,
    })
    accepted = apply_source_scope_correction(batch, original, 0, corrected)
    assert accepted.statements[0].quoted_text == original.statements[0].quoted_text
    assert accepted.statements[0].time_words == ["筛选时"]
    validate_source_interpretation(batch, accepted)

    without_direct_time = corrected.model_copy(update={"time_words": []})
    with pytest.raises(ValueError, match="明确时间不可"):
        apply_source_scope_correction(batch, original, 0, without_direct_time)
    wrong_unit = corrected.model_copy(update={"structure_unit_id": "su-01"})
    with pytest.raises(ValueError, match="仍未核清"):
        apply_source_scope_correction(batch, original, 0, wrong_unit)


def test_runner_repairs_two_source_scopes_without_rereading_other_statements() -> None:
    batch = _batch().model_copy(deep=True)
    original = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
            {"structure_unit_id": "su-01", "quoted_text": "年龄至少18岁",
             "force": "required", "time_words": ["治疗期"]},
            {"structure_unit_id": "su-02", "quoted_text": "筛选时记录末次用药日期",
             "scope_quote": "相邻条目的治疗期", "force": "required", "time_words": ["筛选时"]},
        ],
        "units_without_statement": [],
    })

    class ScopeTransport(_FakeTransport):
        source_calls = 0
        correction_calls = 0

        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.source_calls += 1
            return ProtocolControlAgentResponse(session_id="source-1", text=original.model_dump_json())

        def correct_source_scope(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.correction_calls += 1
            unit_id = "su-01" if self.correction_calls == 1 else "su-02"
            assert unit_id in prompt
            return ProtocolControlAgentResponse(session_id=f"scope-{self.correction_calls}", text=json.dumps({
                "version": "phase5/control-source-scope-correction/v1",
                "structure_unit_id": unit_id, "scope_quote": None,
                "affected_stage": None,
                "time_words": [] if unit_id == "su-01" else ["筛选时"],
                "unresolved": None,
            }, ensure_ascii=False))

    transport = ScopeTransport([
        ProtocolControlAgentResponse(session_id="wire-1", text=_wire(candidate=_candidate()).model_dump_json())
    ])
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert transport.source_calls == 1
    assert transport.correction_calls == 2
    assert result.source_interpretation is not None
    assert result.source_interpretation.statements[0].time_words == []
    assert result.source_interpretation.statements[1].scope_quote is None


def test_source_target_review_selects_unexpressed_enrollment_requirements() -> None:
    inventory = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
            {"structure_unit_id": f"su-{index}", "quoted_text": "应核查原文",
             "force": "required", "time_words": []}
            for index in range(4)
        ],
        "units_without_statement": [],
    })
    coverage = [
        SourceStatementCoverage(
            statement_index=index,
            structure_unit_id=f"su-{index}",
            disposition=disposition,
            status=status,
        )
        for index, (disposition, status) in enumerate([
            ("official_eligibility", "linked_only"),
            ("supporting_or_supplement", "not_located"),
            ("phase_excluded", "not_located"),
            ("other_control_candidate", "expressed"),
        ])
    ]
    assert target_review_indexes(inventory, coverage) == [0, 1]


def test_source_target_review_preserves_uncovered_statement_as_failure() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].excerpt = "其他控制：年龄至少18岁；筛选前说明年龄记录来源"
    batch.known_official_targets[0].source_excerpts = ["年龄至少18岁"]
    inventory = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
            {"structure_unit_id": "su-01", "quoted_text": "筛选前说明年龄记录来源", "force": "required", "time_words": []},
        ],
        "units_without_statement": ["su-02"],
    })
    claim = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "additional_requirement", "target_id": None,
                   "source_action_excerpt": "说明年龄记录来源", "target_action_excerpt": None,
                   "source_time_excerpt": None, "target_time_excerpt": None,
                   "unresolved_aspects": ["未找到既有条款对应的完整要求"]}],
    })

    class ReviewingTransport(_FakeTransport):
        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            assert "说明年龄记录来源" in prompt
            return ProtocolControlAgentResponse(session_id="target-1", text=claim.model_dump_json())

    result = ProtocolControlAgentRunner().run(
        batch,
        ReviewingTransport([ProtocolControlAgentResponse(session_id="wire-1", text=_wire(candidate=_candidate()).model_dump_json())]),
    )
    assert result.status == "需要核对"
    assert result.final_output is None
    assert result.source_target_review == claim
    assert result.attempts[-1].error_classes == ["SOURCE_TARGET_REVIEW_UNRESOLVED"]
    assert result.attempts[-2].output is not None

    batch.known_official_targets[0].source_excerpts = ["说明年龄记录来源"]
    claim = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "covered_by_official", "target_id": "EX-01",
                   "source_action_excerpt": "说明年龄记录来源",
                   "target_action_excerpt": "说明年龄记录来源",
                   "source_time_excerpt": None, "target_time_excerpt": None,
                   "unresolved_aspects": []}],
    })
    accepted = ProtocolControlAgentRunner().run(
        batch,
        ReviewingTransport([ProtocolControlAgentResponse(
            session_id="wire-2", text=_wire(candidate=_candidate()).model_dump_json()
        )]),
    )
    assert accepted.status == "已解析"
    assert accepted.source_target_review == claim
    assert accepted.final_output is not None


def test_source_target_review_rechecks_only_overclaimed_statement_once() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].excerpt = "其他控制：年龄至少18岁；筛选期及治疗期完成记录"
    batch.known_official_targets[0].source_excerpts = ["筛选期完成记录"]
    inventory = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-01", "quoted_text": "筛选期及治疗期完成记录",
            "force": "required", "time_words": ["筛选期", "治疗期"],
        }],
        "units_without_statement": ["su-02"],
    })

    def item(decision: str, unresolved: list[str]) -> SourceTargetReview:
        return SourceTargetReview.model_validate({
            "version": SOURCE_TARGET_REVIEW_VERSION,
            "items": [{
                "statement_index": 0, "decision": decision, "target_id": "EX-01",
                "source_action_excerpt": "完成记录", "target_action_excerpt": "完成记录",
                "source_time_excerpt": "筛选期", "target_time_excerpt": "筛选期",
                "unresolved_aspects": unresolved,
            }],
        })

    class ReviewingTransport(_FakeTransport):
        calls = 0

        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.calls += 1
            if self.calls == 1:
                return ProtocolControlAgentResponse(
                    session_id="target-1", text=item("covered_by_official", []).model_dump_json()
                )
            assert "第0条时间要求未在目标原文逐项覆盖" in prompt
            return ProtocolControlAgentResponse(
                session_id="target-2", text=item("unresolved", ["治疗期未在目标原文找到"]).model_dump_json()
            )

    transport = ReviewingTransport([
        ProtocolControlAgentResponse(session_id="wire-1", text=_wire(candidate=_candidate()).model_dump_json())
    ])
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert transport.calls == 2
    assert result.status == "需要核对"
    assert result.source_target_review is not None
    assert result.source_target_review.items[0].decision == "unresolved"
    assert any("SOURCE_TARGET_REVIEW_INVALID" in attempt.error_classes for attempt in result.attempts)


def test_source_target_addition_enters_bounded_repair_without_accepting_unchanged_wire() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].excerpt = "其他控制：年龄至少18岁；筛选前说明年龄记录来源"
    inventory = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": "筛选前说明年龄记录来源",
                        "force": "required", "time_words": []}],
        "units_without_statement": ["su-02"],
    })
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "additional_requirement", "target_id": None,
                   "source_action_excerpt": "说明年龄记录来源", "target_action_excerpt": None,
                   "source_time_excerpt": None, "target_time_excerpt": None,
                   "unresolved_aspects": ["现有候选未表达记录来源"]}],
    })
    original = _wire(candidate=_candidate()).model_dump_json()

    class AdditionTransport(_FakeTransport):
        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="target-1", text=review.model_dump_json())

    transport = AdditionTransport([
        ProtocolControlAgentResponse(session_id="wire-1", text=original),
        ProtocolControlAgentResponse(session_id="wire-1", text=original),
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        batch, transport, output_validator=lambda _output: None,
    )
    assert result.status == "需要核对"
    assert result.final_output is None
    assert result.source_target_review == review
    assert any("SOURCE_TARGET_ADDITIONAL_REQUIREMENT" in attempt.error_classes
               for attempt in result.attempts)
    assert "来源限定补入" in transport.prompts[-1]
    assert any("REPAIR_SCOPE_ESCAPE" in attempt.error_classes
               for attempt in result.attempts)


def test_source_target_addition_can_publish_only_after_source_bound_insert() -> None:
    batch = _batch().model_copy(deep=True)
    quote = "须记录年龄资料来源"
    batch.owned_units[0].excerpt = f"其他控制：{quote}"
    inventory = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": quote,
                        "force": "required", "time_words": []}],
        "units_without_statement": ["su-02"],
    })
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "additional_requirement", "target_id": None,
                   "source_action_excerpt": quote, "target_action_excerpt": None,
                   "source_time_excerpt": None, "target_time_excerpt": None,
                   "unresolved_aspects": ["既有目标没有记录来源要求"]}],
    })
    candidate = _candidate().model_dump(mode="json")
    candidate["title"] = "年龄资料来源记录"
    candidate["applicability_expression"] = None
    candidate["exception_expression"] = None
    atom = candidate["obligation_expression"]["groups"][0]["atoms"][0]
    atom["kind"] = "must_record"
    atom["statement"] = quote
    atom["source_excerpts"] = [quote]
    atom["evaluation"] = _evaluation(quote, "span:01", quote)
    candidate["minimum_evidence"][0]["description"] = quote
    candidate["minimum_evidence"][0]["source_policy"]["source_excerpts"] = [quote]

    class InsertingTransport(_FakeTransport):
        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="target-1", text=review.model_dump_json())

        def continue_candidate(self, *, session_id: str, prompt: str) -> ProtocolControlAgentResponse:
            self.prompts.append(prompt)
            assert "研究日区间标注首先是冻结访视的范围" in prompt
            assert "指向官方入排条款的关系须填 null" in prompt
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"candidate_draft": candidate}, ensure_ascii=False),
            )

    transport = InsertingTransport([
        ProtocolControlAgentResponse(session_id="wire-1", text=_wire().model_dump_json()),
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        batch, transport, output_validator=lambda _output: None,
    )
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert result.final_output is not None
    assert len(result.final_output.candidates) == 1
    assert result.source_statement_coverage[0].status == "expressed"
    assert any("SOURCE_TARGET_ADDITIONAL_REQUIREMENT" in attempt.error_classes
               for attempt in result.attempts)


def test_source_insert_preserves_procedure_link_for_mixed_source() -> None:
    original = _wire()
    original.dispositions[0] = ProtocolControlAgentWireDisposition(
        structure_unit_id="su-01",
        disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
        linked_official_code=None,
        linked_procedure_catalog_item_id="procedure-screening-1",
        linked_procedure_catalog_item_ids=[],
        notes=None,
    )
    revised = original.model_copy(deep=True)
    revised.dispositions[0] = ProtocolControlAgentWireDisposition(
        structure_unit_id="su-01",
        disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
        linked_official_code=None,
        linked_procedure_catalog_item_id=None,
        linked_procedure_catalog_item_ids=[],
        notes=None,
    )
    candidate = _candidate().model_dump(mode="json")
    candidate["cross_source_relations"] = [{
        "kind": "supplementary_requirement",
        "external_target_kind": "required_procedure",
        "external_target_id": "procedure-screening-1",
        "candidate_side": "left",
        "affected_workflow_stage_id": "stage:screening:one",
        "notes": None,
    }]
    revised.candidate_drafts = [ProtocolControlAgentWireCandidate.model_validate(candidate)]
    restored, changed = _restore_bounded_wire_repair(
        original, revised,
        mutable_structure_unit_ids={"su-01"},
        mutable_obligation_source_span_ids={"span:01"},
        allow_source_insert=True,
    )
    assert not changed
    assert restored.dispositions[0].disposition == StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
    revised.candidate_drafts[0].cross_source_relations = []
    with pytest.raises(ProtocolControlAgentWireValidationError, match="REPAIR_SCOPE_ESCAPE"):
        _restore_bounded_wire_repair(
            original, revised,
            mutable_structure_unit_ids={"su-01"},
            mutable_obligation_source_span_ids={"span:01"},
            allow_source_insert=True,
        )


def test_multi_source_insert_keeps_prior_wire_and_rejects_missing_target() -> None:
    initial = _wire()
    initial.dispositions[0] = ProtocolControlAgentWireDisposition(
        structure_unit_id="su-01",
        disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
        linked_official_code=None,
        linked_procedure_catalog_item_id="procedure-screening-1",
        linked_procedure_catalog_item_ids=[],
        notes=None,
    )
    first = _candidate().model_dump(mode="json")
    first["cross_source_relations"] = [{
        "kind": "supplementary_requirement", "external_target_kind": "required_procedure",
        "external_target_id": "procedure-screening-1", "candidate_side": "left",
        "affected_workflow_stage_id": "stage:screening:one", "notes": None,
    }]
    second = deepcopy(first)
    second["title"] = "另一项有源要求"
    payload = json.dumps({"candidate_drafts": [first, second]}, ensure_ascii=False)
    merged = _merge_source_candidate_insert(payload, initial, authorized_unit_ids={"su-01"})
    assert len(merged.candidate_drafts) == 2
    assert merged.candidate_drafts[0].title == first["title"]
    assert merged.dispositions[1] == initial.dispositions[1]
    first["cross_source_relations"] = []
    second["cross_source_relations"] = []
    with pytest.raises(ProtocolControlAgentWireValidationError, match="SOURCE_INSERT_INVALID"):
        _merge_source_candidate_insert(
            json.dumps({"candidate_drafts": [first, second]}), initial,
            authorized_unit_ids={"su-01"},
        )


def test_source_insert_only_ignores_an_exact_duplicate_atom_excerpt() -> None:
    initial = _wire()
    candidate = _candidate().model_dump(mode="json")
    excerpt = candidate["obligation_expression"]["groups"][0]["atoms"][0]["source_excerpts"][0]
    candidate["source_excerpts"] = [excerpt]
    merged = _merge_source_candidate_insert(
        json.dumps({"candidate_draft": candidate}), initial,
        authorized_unit_ids={"su-01"},
    )
    assert merged.candidate_drafts[0].obligation_expression.groups[0].atoms[0].source_excerpts == [excerpt]
    candidate["source_excerpts"] = ["原子来源中没有的临床要求"]
    with pytest.raises(ProtocolControlAgentWireValidationError, match="未在义务原子中逐字保存"):
        _merge_source_candidate_insert(
            json.dumps({"candidate_draft": candidate}), initial,
            authorized_unit_ids={"su-01"},
        )


def test_source_insert_keeps_missing_observation_choice_unresolved() -> None:
    candidate = _candidate().model_dump(mode="json")
    atom = candidate["obligation_expression"]["groups"][0]["atoms"][0]
    atom["evaluation"]["observation_policy"] = None
    merged = _merge_source_candidate_insert(
        json.dumps({"candidate_draft": candidate}, ensure_ascii=False),
        _wire(), authorized_unit_ids={"su-01"},
    )
    policy = merged.candidate_drafts[0].obligation_expression.groups[0].atoms[0].evaluation.observation_policy
    assert policy.mode == "unresolved"
    assert policy.source_span_ids == atom["source_span_ids"]
    assert policy.source_excerpts == atom["source_excerpts"]


def test_source_insert_completes_only_atom_proven_evidence_source_pair() -> None:
    candidate = _candidate().model_dump(mode="json")
    policy = candidate["minimum_evidence"][0]["source_policy"]
    policy["source_excerpts"] = []
    merged = _merge_source_candidate_insert(
        json.dumps({"candidate_draft": candidate}, ensure_ascii=False),
        _wire(), authorized_unit_ids={"su-01"},
    )
    assert merged.candidate_drafts[0].minimum_evidence[0].source_policy.source_excerpts == ["年龄至少18岁"]

    policy["source_excerpts"] = ["并非该原子的逐字来源", "另一段摘录"]
    with pytest.raises(ProtocolControlAgentWireValidationError, match="SOURCE_INSERT_INVALID"):
        _merge_source_candidate_insert(
            json.dumps({"candidate_draft": candidate}, ensure_ascii=False),
            _wire(), authorized_unit_ids={"su-01"},
        )


def test_marker_only_randomization_row_is_not_new_eligibility_control() -> None:
    statement = {
        "structure_unit_id": "schedule-row", "quoted_text": "随机 | X",
        "force": "required", "time_words": [],
    }
    interpretation = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [statement], "units_without_statement": [],
    })
    coverage = [SourceStatementCoverage(
        statement_index=0, structure_unit_id="schedule-row",
        disposition="supporting_or_supplement", status="linked_only",
    )]
    unit = SimpleNamespace(
        structure_unit_id="schedule-row", unit_kind="table_row",
        excerpt="随机 | X", heading_path=["方案摘要", "研究日程表"],
        table_context=SimpleNamespace(row_headers=["随机"]),
    )
    batch = SimpleNamespace(owned_units=[unit])
    assert target_review_indexes(interpretation, coverage, batch) == []

    unit.excerpt = "随机前必须完成全部入排复核 | X"
    assert target_review_indexes(interpretation, coverage, batch) == [0]

    unit.heading_path = ["方案摘要", "研究日程表"]
    unit.excerpt = "随机 | X"
    interpretation.statements[0].scope_quote = "不存在的共同范围"
    interpretation.statements[0].time_words = ["不存在的时间"]
    normalized, ids = normalize_schedule_randomization_anchors(batch, interpretation)
    assert ids == ["schedule-row"]
    assert normalized.statements[0].force == "descriptive"
    assert normalized.statements[0].quoted_text == unit.excerpt
    assert normalized.statements[0].scope_quote is None
    assert normalized.statements[0].time_words == []
    assert normalize_schedule_randomization_anchors(batch, normalized) == (normalized, [])

    unit.excerpt = "随机前必须完成全部入排复核 | X"
    untouched, ids = normalize_schedule_randomization_anchors(batch, interpretation)
    assert ids == []
    assert untouched == interpretation
    unit.excerpt = "随机 | X"
    unit.heading_path = ["合并用药"]
    assert target_review_indexes(interpretation, coverage, batch) == [0]


def test_schedule_columns_close_only_existing_enrollment_visits() -> None:
    def row(row_index: int, values: list[tuple[int, str]]) -> ProtocolStructureUnit:
        refs = [f"body.t0.r{row_index}.c{col}.p0" for col, _ in values]
        return ProtocolStructureUnit(
            structure_unit_id=f"row-{row_index}", source_ref=f"body.t0.r{row_index}",
            member_source_refs=refs, source_span_ids=[f"snapshot::{ref}" for ref in refs],
            unit_kind="table_row", heading_path=["访视表"], source_order=row_index,
            study_phase=StudyPhase.PHASE_II, phase_scopes=[PhaseScope.SHARED],
            excerpt=" | ".join(value for _, value in values),
            table_context=TableCellContext(
                table_path=(row_index, 0), row_index=row_index, column_index=0,
                member_cell_paths=[(row_index, col) for col, _ in values],
            ),
        )

    header = row(0, [(0, "试验阶段"), (1, "筛选期"), (2, "基线期"), (3, "治疗期")])
    visits = row(1, [(0, "访视"), (1, "V1"), (2, "V2"), (3, "V3")])
    mixed = row(4, [(0, "心电检查^2"), (1, "X"), (2, "X"), (3, "X")])
    from app.protocols.procedure_catalog import schedule_column_scope

    scopes = schedule_column_scope(mixed, [header, visits])
    assert [item.boundary_side for item in scopes] == [
        "at_or_before_baseline", "at_or_before_baseline", "after_baseline",
    ]
    batch = _batch().model_copy(deep=True)
    batch.owned_units = [mixed]
    batch.context_units = [header, visits]
    batch.known_procedure_targets = [
        KnownRequiredProcedureTarget(
            catalog_item_id=f"procedure-{column}", label="心电检查",
            visit_instance=scopes[column - 1].header_text,
            review_stage=scopes[column - 1].review_stage, position=column,
            source_span_ids=[mixed.source_span_ids[0]], source_excerpts=["心电检查^2"],
        ) for column in (1, 2)
    ]
    links = schedule_column_links(batch, mixed.structure_unit_id, mixed.excerpt)
    assert [item.procedure_target_id for item in links] == [
        "procedure-1", "procedure-2", None,
    ]
    assert [item.cell_source_ref for item in links] == mixed.member_source_refs[1:]
    inventory = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": mixed.structure_unit_id,
                        "quoted_text": mixed.excerpt, "force": "required", "time_words": []}],
        "units_without_statement": [],
    })
    coverage = [SourceStatementCoverage(
        statement_index=0, structure_unit_id=mixed.structure_unit_id,
        disposition="supporting_or_supplement", status="not_located",
        schedule_columns=links,
    )]
    assert target_review_indexes(inventory, coverage, batch) == []
    batch.known_procedure_targets.pop()
    assert schedule_column_links(batch, mixed.structure_unit_id, mixed.excerpt) == []
    coverage[0].schedule_columns = []
    assert target_review_indexes(inventory, coverage, batch) == [0]
    assert schedule_column_links(batch, mixed.structure_unit_id, "心电检查^2 | X") == []
    mixed.excerpt = "心电检查^2 | X | X | X | 研究者判断"
    assert schedule_column_links(batch, mixed.structure_unit_id, mixed.excerpt) == []

    mixed.excerpt = "心电检查^2 | X | X | X"
    batch.known_procedure_targets.append(batch.known_procedure_targets[0].model_copy(
        update={"catalog_item_id": "duplicate-target", "position": 9},
    ))
    assert schedule_column_links(batch, mixed.structure_unit_id, mixed.excerpt) == []

    inventory.statements[0].scope_quote = "筛选期"
    with pytest.raises(ValueError, match="共享范围"):
        validate_source_interpretation(batch, inventory)
    batch.known_procedure_targets.pop()
    batch.known_procedure_targets.append(batch.known_procedure_targets[0].model_copy(
        update={"catalog_item_id": "procedure-2", "position": 2,
                "visit_instance": scopes[1].header_text,
                "review_stage": scopes[1].review_stage},
    ))
    corrected, changed = normalize_mixed_schedule_scopes(batch, inventory)
    assert changed == [mixed.structure_unit_id]
    assert corrected.statements[0].scope_quote is None
    assert inventory.statements[0].scope_quote == "筛选期"
    validate_source_interpretation(batch, corrected)
    inventory.statements[0].time_words = ["筛选期"]
    assert normalize_mixed_schedule_scopes(batch, inventory) == (inventory, [])
    inventory.statements[0].time_words = []

    one_visit = row(5, [(0, "用药记录"), (2, "X")])
    batch.owned_units = [one_visit]
    inventory.statements[0].structure_unit_id = one_visit.structure_unit_id
    inventory.statements[0].quoted_text = one_visit.excerpt
    inventory.statements[0].scope_quote = "基线期"
    validate_source_interpretation(batch, inventory)

    mixed.unit_kind = "table_note"
    mixed.excerpt = "心电检查^2 | X | X | X^27"
    batch.owned_units = [mixed]
    links = schedule_column_links(batch, mixed.structure_unit_id, mixed.excerpt)
    assert [item.marker_footnotes for item in links] == [[], [], ["^27"]]
    mixed.excerpt = "心电检查^2 | X^4 | X | X^27"
    assert schedule_column_links(batch, mixed.structure_unit_id, mixed.excerpt) == []

@pytest.mark.parametrize("prior_schema_repair", [False, True])
def test_mixed_official_source_keeps_its_link_when_new_requirement_is_added(
    prior_schema_repair: bool,
) -> None:
    batch = _batch().model_copy(deep=True)
    quote = "须记录年龄资料来源"
    batch.owned_units[0].excerpt = f"其他控制：年龄至少18岁；{quote}"
    batch.known_official_targets[0].source_excerpts = ["年龄至少18岁"]
    inventory = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": quote,
                        "force": "required", "time_words": []}],
        "units_without_statement": ["su-02"],
    })
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "additional_requirement", "target_id": "EX-01",
                   "source_action_excerpt": quote, "target_action_excerpt": "年龄至少18岁",
                   "source_time_excerpt": None, "target_time_excerpt": None,
                   "unresolved_aspects": ["原条款未要求记录资料来源"]}],
    })
    initial = _wire().model_dump(mode="json")
    initial["dispositions"][0].update(disposition="official_eligibility", linked_official_code="EX-01")
    revised = json.loads(json.dumps(initial))
    revised["dispositions"][0].update(disposition="other_control_candidate", linked_official_code=None, notes=None)
    candidate = _candidate().model_dump(mode="json")
    candidate["title"] = "年龄资料来源记录"
    candidate["applicability_expression"] = None
    candidate["exception_expression"] = None
    atom = candidate["obligation_expression"]["groups"][0]["atoms"][0]
    atom.update(kind="must_record", statement=quote, source_excerpts=[quote],
                evaluation=_evaluation(quote, "span:01", quote))
    candidate["minimum_evidence"][0]["description"] = quote
    candidate["minimum_evidence"][0]["source_policy"]["source_excerpts"] = [quote]
    candidate["cross_source_relations"] = [{
        "kind": "supplementary_requirement", "external_target_kind": "official_rule",
        "external_target_id": "EX-01", "candidate_side": "left",
        "affected_workflow_stage_id": None, "notes": None,
    }]
    revised["candidate_drafts"] = [candidate]

    class MixedTransport(_FakeTransport):
        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="target-1", text=review.model_dump_json())

    responses = []
    if prior_schema_repair:
        responses.append(ProtocolControlAgentResponse(
            session_id="wire-1",
            text=json.dumps({"wire_version": CONTROL_AGENT_WIRE_VERSION, "dispositions": []}),
        ))
    responses.extend([
        ProtocolControlAgentResponse(session_id="wire-1", text=json.dumps(initial, ensure_ascii=False)),
        ProtocolControlAgentResponse(session_id="wire-1", text=json.dumps(revised, ensure_ascii=False)),
    ])
    transport = MixedTransport(responses)
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        batch, transport, output_validator=lambda _output: None,
    )
    assert result.status == "已解析"
    assert result.final_output is not None
    assert len(result.final_output.candidates) == 1
    assert result.source_statement_coverage[0].status == "expressed"
    assert result.final_output.candidates[0].semantics.cross_source_relations[0].right_target_id == "EX-01"
    assert any("SOURCE_TARGET_ADDITIONAL_REQUIREMENT" in attempt.error_classes
               for attempt in result.attempts)


def test_source_insert_reuses_unchanged_validated_target_matches() -> None:
    batch = _batch().model_copy(deep=True)
    added_quote = "须记录年龄资料来源"
    batch.owned_units[0].excerpt = f"其他控制：年龄至少18岁；签署知情同意；{added_quote}"
    batch.known_official_targets[0].source_excerpts = ["签署知情同意"]
    inventory = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
            {"structure_unit_id": "su-01", "quoted_text": "签署知情同意",
             "force": "required", "time_words": []},
            {"structure_unit_id": "su-01", "quoted_text": added_quote,
             "force": "required", "time_words": []},
        ],
        "units_without_statement": ["su-02"],
    })
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [
            {"statement_index": 0, "decision": "covered_by_official", "target_id": "EX-01",
             "source_action_excerpt": "签署知情同意", "target_action_excerpt": "签署知情同意",
             "source_time_excerpt": None, "target_time_excerpt": None, "unresolved_aspects": []},
            {"statement_index": 1, "decision": "additional_requirement", "target_id": None,
             "source_action_excerpt": added_quote, "target_action_excerpt": None,
             "source_time_excerpt": None, "target_time_excerpt": None,
             "unresolved_aspects": ["已有目标未要求记录资料来源"]},
        ],
    })
    initial = _wire(candidate=_candidate()).model_dump(mode="json")
    revised = deepcopy(initial)
    candidate = _candidate().model_dump(mode="json")
    candidate["title"] = "年龄资料来源记录"
    candidate["applicability_expression"] = None
    candidate["exception_expression"] = None
    atom = candidate["obligation_expression"]["groups"][0]["atoms"][0]
    atom.update(kind="must_record", statement=added_quote, source_excerpts=[added_quote],
                evaluation=_evaluation(added_quote, "span:01", added_quote))
    candidate["minimum_evidence"][0]["description"] = added_quote
    candidate["minimum_evidence"][0]["source_policy"]["source_excerpts"] = [added_quote]
    revised["candidate_drafts"].append(candidate)

    class CountingTransport(_FakeTransport):
        review_calls = 0

        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.review_calls += 1
            return ProtocolControlAgentResponse(session_id="target-1", text=review.model_dump_json())

    transport = CountingTransport([
        ProtocolControlAgentResponse(session_id="wire-1", text=json.dumps(initial, ensure_ascii=False)),
        ProtocolControlAgentResponse(session_id="wire-1", text=json.dumps(revised, ensure_ascii=False)),
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=0).run(
        batch, transport, output_validator=lambda _output: None,
    )
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert transport.review_calls == 1
    assert len(result.final_output.candidates) == 2
    assert [entry.status for entry in result.source_statement_coverage] == [
        "candidate_linked", "expressed",
    ]


def test_strict_response_format_does_not_duplicate_full_schema_in_prompt() -> None:
    batch = _batch()
    full_prompt = build_protocol_control_agent_prompt(batch)
    strict_prompt = build_protocol_control_agent_prompt(batch, include_schema=False)
    assert "输出结构：" in full_prompt
    assert "输出结构：" not in strict_prompt
    assert "本次冻结输入：" in strict_prompt
    assert "严格遵循本次请求随附的 JSON Schema" in strict_prompt
    assert len(full_prompt) - len(strict_prompt) > 10000

    transport = _FakeTransport(
        [ProtocolControlAgentResponse(session_id="session-schema", text=_wire().model_dump_json())]
    )
    transport.response_format_mode = "json_schema"
    assert ProtocolControlAgentRunner().run(batch, transport).status == "已解析"
    assert "输出结构：" not in transport.prompts[0]


def test_same_session_repair_is_bounded_to_batch_and_cannot_replace_accepted_batch() -> None:
    batch = _batch()
    invalid = json.dumps({"wire_version": CONTROL_AGENT_WIRE_VERSION, "dispositions": []})
    valid = _wire(candidate=_candidate()).model_dump_json()
    transport = _FakeTransport(
        [
            ProtocolControlAgentResponse(session_id="session-1", text=invalid),
            ProtocolControlAgentResponse(session_id="session-1", text=valid),
        ]
    )
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(batch, transport)
    assert result.status == "已解析"
    assert len(result.attempts) == 2
    assert "pcb-generic-01" in transport.prompts[1]
    assert "su-01" in transport.prompts[1]
    assert "不要替换已经接受的批次" in transport.prompts[1]

    with pytest.raises(ValueError, match="已接受批次"):
        ProtocolControlAgentRunner().run(
            batch,
            _FakeTransport([]),
            accepted_batch_ids=[batch.batch_id],
        )


def test_same_session_repair_can_use_post_hydration_publication_feedback() -> None:
    batch = _batch()
    valid = _wire(candidate=_candidate()).model_dump_json()
    transport = _FakeTransport(
        [
            ProtocolControlAgentResponse(session_id="session-1", text=valid),
            ProtocolControlAgentResponse(session_id="session-1", text=valid),
        ]
    )
    calls = 0

    def validate_after_hydration(output) -> None:
        nonlocal calls
        calls += 1
        assert output.candidates
        if calls == 1:
            raise ProtocolControlAgentWireValidationError(
                "PROSPECTIVE_PERIOD_UNSUPPORTED",
                "义务持续期间必须由该原子的直接来源原文支持",
                structure_unit_ids=["su-01"],
            )

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        batch,
        transport,
        output_validator=validate_after_hydration,
    )

    assert result.status == "已解析"
    assert calls == 2
    assert [attempt.outcome for attempt in result.attempts] == [
        "publication_invalid",
        "parsed",
    ]
    assert "PROSPECTIVE_PERIOD_UNSUPPORTED" in transport.prompts[1]
    assert "su-01" in transport.prompts[1]


def test_repair_scope_outside_owned_batch_stops_without_follow_up() -> None:
    batch = _batch()
    transport = _FakeTransport(
        [ProtocolControlAgentResponse(session_id="session-1", text=_wire().model_dump_json())]
    )

    def reject_with_unknown_source(_output) -> None:
        raise ProtocolControlAgentWireValidationError(
            "CANDIDATE_SOURCE_SCOPE_ESCAPE",
            "来源编号不属于当前批次",
            structure_unit_ids=["su-not-in-batch"],
        )

    result = ProtocolControlAgentRunner(max_schema_repairs=2).run(
        batch,
        transport,
        output_validator=reject_with_unknown_source,
    )

    assert result.status == "需要核对"
    assert len(result.attempts) == 1
    assert "机器可读修订范围" in result.attempts[0].issues[-1]
    assert len(transport.prompts) == 1


def test_repeated_identical_invalid_output_stops_without_consuming_all_repairs() -> None:
    batch = _batch()
    missing_candidate = _wire().model_dump(mode="json")
    missing_candidate["dispositions"][0]["disposition"] = "other_control_candidate"
    invalid = json.dumps(missing_candidate, ensure_ascii=False)
    transport = _FakeTransport(
        [
            ProtocolControlAgentResponse(session_id="session-1", text=invalid),
            ProtocolControlAgentResponse(session_id="session-1", text=invalid),
        ]
    )

    result = ProtocolControlAgentRunner(max_schema_repairs=10).run(batch, transport)

    assert result.status == "需要核对"
    assert len(result.attempts) == 2
    assert all("CANDIDATE_MISSING" in attempt.issues[0] for attempt in result.attempts)
    assert "停止自动修订" in result.attempts[-1].issues[-1]
    assert "不得只在 notes 中描述候选" in transport.prompts[1]


def test_post_hydration_repair_restores_changes_outside_original_scope() -> None:
    batch = _batch()
    valid_wire = _wire(candidate=_candidate())
    escaped_payload = valid_wire.model_dump(mode="json")
    escaped_payload["dispositions"][1]["notes"] = "未授权改写的补充说明"
    transport = _FakeTransport(
        [
            ProtocolControlAgentResponse(
                session_id="session-1",
                text=valid_wire.model_dump_json(),
            ),
            ProtocolControlAgentResponse(
                session_id="session-1",
                text=json.dumps(escaped_payload, ensure_ascii=False),
            ),
            ProtocolControlAgentResponse(
                session_id="session-1",
                text=valid_wire.model_dump_json(),
            ),
        ]
    )
    validator_calls = 0

    def validate_after_hydration(output) -> None:
        nonlocal validator_calls
        validator_calls += 1
        if validator_calls == 1:
            raise ProtocolControlAgentWireValidationError(
                "TARGET_REJECTED",
                "只允许修复第一个结构单元",
                structure_unit_ids=["su-01"],
            )

    result = ProtocolControlAgentRunner(max_schema_repairs=2).run(
        batch,
        transport,
        output_validator=validate_after_hydration,
    )

    assert result.status == "已解析"
    assert validator_calls == 2
    assert [attempt.outcome for attempt in result.attempts] == [
        "publication_invalid",
        "parsed",
    ]
    assert result.attempts[1].issues == [
        "已由系统原样保留定向修订范围外的上一轮内容"
    ]
    assert result.final_output is not None
    restored = {
        item.structure_unit_id: item.notes
        for item in result.final_output.dispositions
    }
    assert restored["su-02"] != "未授权改写的补充说明"


def _candidate_for_second_unit() -> ProtocolControlAgentWireCandidate:
    payload = json.loads(
        _candidate()
        .model_dump_json()
        .replace("年龄资料控制", "末次用药记录控制")
        .replace("年龄条件", "末次用药记录条件")
        .replace("年龄达到18岁", "记录末次用药日期")
        .replace("核对年龄资料", "核对末次用药记录")
        .replace("demographics", "medication_history")
        .replace("年龄至少18岁", "筛选时记录末次用药日期")
        .replace("span:01", "span:02")
        .replace("su-01", "su-02")
    )
    return ProtocolControlAgentWireCandidate.model_validate(payload)


def _wire_with_two_candidates(
    first: ProtocolControlAgentWireCandidate,
    second: ProtocolControlAgentWireCandidate,
) -> ProtocolControlAgentWire:
    wire = _wire(candidate=first).model_dump(mode="json")
    wire["dispositions"][1].update(
        disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value,
        notes=None,
    )
    wire["candidate_drafts"] = [
        first.model_dump(mode="json"),
        second.model_dump(mode="json"),
    ]
    return ProtocolControlAgentWire.model_validate(wire)


def test_post_hydration_repairs_roll_forward_without_cross_candidate_regression() -> None:
    batch = _batch()
    first = _candidate()
    second = _candidate_for_second_unit()
    initial = _wire_with_two_candidates(first, second)
    first_fixed = first.model_copy(update={"title": "年龄资料控制（已修订）"})
    second_regressed = second.model_copy(update={"title": "错误改写的用药控制"})
    repair_first = _wire_with_two_candidates(first_fixed, second_regressed)
    first_regressed = first.model_copy(update={"title": "错误回退的年龄控制"})
    second_fixed = second.model_copy(update={"title": "末次用药记录控制（已修订）"})
    repair_second = _wire_with_two_candidates(first_regressed, second_fixed)
    transport = _FakeTransport(
        [
            ProtocolControlAgentResponse(
                session_id="session-1", text=initial.model_dump_json()
            ),
            ProtocolControlAgentResponse(
                session_id="session-1", text=repair_first.model_dump_json()
            ),
            ProtocolControlAgentResponse(
                session_id="session-1", text=repair_second.model_dump_json()
            ),
        ]
    )
    validator_calls = 0

    def validate_after_hydration(output) -> None:
        nonlocal validator_calls
        validator_calls += 1
        by_source = {
            tuple(candidate.frozen_structure_unit_ids): candidate
            for candidate in output.candidates
        }
        if validator_calls == 1:
            candidate = by_source[("su-01",)]
            raise ProtocolControlAgentWireValidationError(
                "FIRST_CANDIDATE_REJECTED",
                "只允许修订第一个候选",
                candidate_ids=[candidate.control_candidate_id],
                structure_unit_ids=["su-01"],
            )
        if validator_calls == 2:
            assert by_source[("su-02",)].title == second.title
            candidate = by_source[("su-02",)]
            raise ProtocolControlAgentWireValidationError(
                "SECOND_CANDIDATE_REJECTED",
                "只允许修订第二个候选",
                candidate_ids=[candidate.control_candidate_id],
                structure_unit_ids=["su-02"],
            )

    result = ProtocolControlAgentRunner(max_schema_repairs=2).run(
        batch,
        transport,
        output_validator=validate_after_hydration,
    )

    assert result.status == "已解析"
    assert result.final_output is not None
    by_source = {
        tuple(candidate.frozen_structure_unit_ids): candidate
        for candidate in result.final_output.candidates
    }
    assert by_source[("su-01",)].title == "年龄资料控制（已修订）"
    assert by_source[("su-02",)].title == "末次用药记录控制（已修订）"
    assert result.attempts[-1].issues == [
        "已由系统原样保留定向修订范围外的上一轮内容"
    ]


def test_candidate_only_repair_preserves_other_candidates_and_dispositions() -> None:
    first = _candidate()
    second = _candidate_for_second_unit()
    initial = _wire_with_two_candidates(first, second)
    repaired = first.model_copy(update={"title": "年龄资料控制（已核对）"})
    payload = json.dumps({"candidate_draft": repaired.model_dump(mode="json")})
    merged = _merge_candidate_repair(payload, initial, 0)
    assert merged.candidate_drafts[0].title == repaired.title
    assert merged.candidate_drafts[1] == second
    assert merged.dispositions == initial.dispositions
    with pytest.raises(ProtocolControlAgentWireValidationError):
        _merge_candidate_repair(
            json.dumps({"candidate_draft": {**repaired.model_dump(mode="json"), "control_id": "invented"}}),
            initial,
            0,
        )
    response_format = protocol_control_candidate_repair_response_format()
    assert response_format["json_schema"]["name"] == "protocol_control_candidate_repair_v1"
    assert list(response_format["json_schema"]["schema"]["properties"]) == ["candidate_draft"]


def test_missing_evidence_types_are_assembled_without_rewriting_the_candidate() -> None:
    baseline = _wire(candidate=_candidate()).model_dump(mode="json")
    del baseline["candidate_drafts"][0]["minimum_evidence"][0]["required_source_types"]
    raw = json.dumps(baseline, ensure_ascii=False)
    with pytest.raises(ProtocolControlAgentWireValidationError) as caught:
        parse_protocol_control_agent_wire(raw)
    paths = _missing_evidence_source_type_paths(caught.value, baseline, 0)
    assert paths == ((0, 0),)
    response = json.dumps({"items": [{"candidate_index": 0, "evidence_index": 0,
                                     "required_source_types": ["原始资料"]}]}, ensure_ascii=False)
    merged = _merge_evidence_source_types_repair(response, baseline, paths)
    expected = deepcopy(baseline)
    expected["candidate_drafts"][0]["minimum_evidence"][0]["required_source_types"] = ["原始资料"]
    assert merged.model_dump(mode="json") == ProtocolControlAgentWire.model_validate(expected).model_dump(mode="json")
    with pytest.raises(ProtocolControlAgentWireValidationError, match="EVIDENCE_SOURCE_TYPES_REPAIR_INVALID"):
        _merge_evidence_source_types_repair(
            json.dumps({"items": [{"candidate_index": 0, "evidence_index": 1,
                                   "required_source_types": ["原始资料"]}]}), baseline, paths
        )

    class TypesTransport(_FakeTransport):
        def continue_evidence_source_types(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            assert "仅补齐" in prompt
            return ProtocolControlAgentResponse(session_id=session_id, text=response)

    transport = TypesTransport([ProtocolControlAgentResponse(session_id="types-session", text=raw)])
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(_batch(), transport)
    assert result.status == "已解析"
    assert result.final_output is not None
    assert len(transport.prompts) == 2


def test_missing_evidence_types_in_candidate_repair_uses_local_field_reply() -> None:
    original = _wire(candidate=_candidate())
    draft = original.candidate_drafts[0].model_dump(mode="json")
    del draft["minimum_evidence"][0]["required_source_types"]
    source_types = json.dumps({"items": [{"candidate_index": 0, "evidence_index": 0,
                                        "required_source_types": ["原始资料"]}]}, ensure_ascii=False)

    class TypesTransport(_FakeTransport):
        def continue_candidate(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            return ProtocolControlAgentResponse(
                session_id=session_id, text=json.dumps({"candidate_draft": draft}, ensure_ascii=False)
            )

        def continue_evidence_source_types(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            return ProtocolControlAgentResponse(session_id=session_id, text=source_types)

    seen = 0

    def validate(output) -> None:
        nonlocal seen
        seen += 1
        if seen == 1:
            raise ProtocolControlAgentWireValidationError(
                "PUBLICATION_GATE_REJECTED", "需修复候选中的一项字段",
                structure_unit_ids=["su-01"],
                candidate_ids=[output.candidates[0].control_candidate_id],
                obligation_source_span_ids=["span:01"],
            )

    transport = TypesTransport([ProtocolControlAgentResponse(
        session_id="types-candidate", text=original.model_dump_json()
    )])
    result = ProtocolControlAgentRunner(max_schema_repairs=2).run(
        _batch(), transport, output_validator=validate
    )
    assert result.status == "已解析"
    assert seen == 2
    assert len(transport.prompts) == 3
    assert result.final_output is not None


def test_candidate_repair_retains_only_unchanged_checked_time_attribute() -> None:
    original = _candidate().model_dump(mode="json")
    atom = original["obligation_expression"]["groups"][0]["atoms"][0]
    atom["evaluation"] = _timed_evaluation(atom["statement"], "span:01", "年龄至少18岁")
    atom["time_constraint"] = {"anchor_type": "screening_date", "direction": "before"}
    baseline = _wire(candidate=ProtocolControlAgentWireCandidate.model_validate(original))

    revised = deepcopy(original)
    revised_atom = revised["obligation_expression"]["groups"][0]["atoms"][0]
    revised_atom["statement"] += "（已核对）"
    revised_atom["evaluation"]["time_operand_attribute"] = None
    merged = _merge_candidate_repair(json.dumps({"candidate_draft": revised}), baseline, 0)
    assert merged.candidate_drafts[0].obligation_expression.groups[0].atoms[0].evaluation.time_operand_attribute == "date_range"

    changed_time = deepcopy(revised)
    changed_time["obligation_expression"]["groups"][0]["atoms"][0]["time_constraint"]["direction"] = "after"
    with pytest.raises(ProtocolControlAgentWireValidationError, match="CANDIDATE_REPAIR_INVALID"):
        _merge_candidate_repair(json.dumps({"candidate_draft": changed_time}), baseline, 0)

    changed_source = deepcopy(revised)
    changed_source["obligation_expression"]["groups"][0]["atoms"][0]["source_excerpts"] = ["另一条原文"]
    with pytest.raises(ProtocolControlAgentWireValidationError, match="CANDIDATE_REPAIR_INVALID"):
        _merge_candidate_repair(json.dumps({"candidate_draft": changed_source}), baseline, 0)


def test_wire_stage_error_repairs_only_its_candidate_without_rewriting_batch() -> None:
    batch = _batch()
    relation = ProtocolControlAgentWireRelation(
        kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
        external_target_kind=ControlRelationTargetKind.REQUIRED_PROCEDURE,
        external_target_id="procedure-screening-1",
        candidate_side="left",
        affected_workflow_stage_id="stage:screening:two",
        notes="需核对具体访视",
    )
    first = _candidate()
    invalid_first = first.model_copy(update={"cross_source_relations": [relation]})
    valid_relation = relation.model_copy(
        update={"affected_workflow_stage_id": "stage:screening:one"}
    )
    fixed_first = first.model_copy(update={"cross_source_relations": [valid_relation]})
    second = _candidate_for_second_unit()
    initial = _wire_with_two_candidates(invalid_first, second)

    class CandidateTransport(_FakeTransport):
        def continue_candidate(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            assert "仅返回包含 candidate_draft" in prompt
            assert "本轮获授权候选原稿" in prompt
            assert invalid_first.title in prompt
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"candidate_draft": fixed_first.model_dump(mode="json")}),
            )

    transport = CandidateTransport([
        ProtocolControlAgentResponse(
            session_id="candidate-session", text=initial.model_dump_json()
        )
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(batch, transport)
    assert result.status == "已解析"
    assert result.final_output is not None
    assert result.final_output.candidates[1].title == second.title
    assert result.final_output.dispositions[1].structure_unit_id == "su-02"
    assert len(result.attempts) == 2
    assert result.attempts[0].error_classes[0] == "PROCEDURE_AFFECTED_STAGE_MISMATCH"


def test_repair_prompt_repeats_target_index_without_claiming_coverage() -> None:
    prompt = build_protocol_control_repair_prompt(
        _batch(), problem="BASELINE_VALUE_SCOPE_MISSING"
    )
    assert "冻结目标索引" in prompt
    assert "是否覆盖仍须核对首轮输入中的目标原文" in prompt
    assert _batch().known_official_targets[0].official_code in prompt
    assert _batch().known_procedure_targets[0].catalog_item_id in prompt
    assert "cross_source_relations" in prompt


def test_repair_prompt_keeps_time_constraint_and_evaluation_consistent() -> None:
    prompt = build_protocol_control_repair_prompt(
        _batch(),
        problem="CANDIDATE_REPAIR_INVALID: 已有时间约束不能在求值规格中忽略",
        candidate_only=True,
    )
    assert "求值规格须说明该时间条件的用途" in prompt
    assert "不能仅改标记绕过校验" in prompt


def test_partial_repair_prompt_does_not_require_full_batch_output() -> None:
    batch = _batch()
    for partial in ({"candidate_only": True}, {"candidates_only": True}):
        prompt = build_protocol_control_repair_prompt(
            batch, problem="WIRE_SCHEMA_INVALID", candidate_indexes=[0], **partial
        )
        assert "系统保留" in prompt
        assert "仍须返回本批全部 owned_units" not in prompt
    full_prompt = build_protocol_control_repair_prompt(
        batch, problem="WIRE_SCHEMA_INVALID"
    )
    assert "仍须返回本批全部 owned_units" in full_prompt


def test_single_invalid_initial_candidate_is_repaired_without_rewriting_siblings() -> None:
    batch = _batch()
    first = _candidate()
    second = _candidate_for_second_unit()
    valid = _wire_with_two_candidates(first, second)
    initial = valid.model_dump(mode="json")
    del initial["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]["evaluation"]
    initial_text = json.dumps(initial, ensure_ascii=False)
    assert _single_invalid_candidate_payload(initial_text) is not None

    class CandidateTransport(_FakeTransport):
        def continue_candidate(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            assert session_id == "candidate-session"
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"candidate_draft": first.model_dump(mode="json")}),
            )

    transport = CandidateTransport([
        ProtocolControlAgentResponse(session_id="candidate-session", text=initial_text)
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(batch, transport)

    assert result.status == "已解析"
    assert result.final_output is not None
    assert len(result.attempts) == 2
    assert result.attempts[0].error_classes == ["WIRE_SCHEMA_INVALID"]
    assert result.final_output.candidates[1].title == second.title
    assert "仅返回包含 candidate_draft" in transport.prompts[1]


def test_single_invalid_atom_repairs_only_that_atom() -> None:
    batch = _batch()
    first = _candidate()
    second = _candidate_for_second_unit()
    valid = _wire_with_two_candidates(first, second)
    initial = valid.model_dump(mode="json")
    original_atom = initial["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]
    del original_atom["evaluation"]
    initial_text = json.dumps(initial, ensure_ascii=False)
    fixed_atom = first.obligation_expression.groups[0].atoms[0].model_dump(mode="json")

    class AtomTransport(_FakeTransport):
        def continue_atom(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            assert session_id == "atom-session"
            assert "候选0／义务组0／原子0" in prompt
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"atom": fixed_atom}, ensure_ascii=False),
            )

    transport = AtomTransport([
        ProtocolControlAgentResponse(session_id="atom-session", text=initial_text)
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(batch, transport)
    assert result.status == "已解析"
    assert result.final_output is not None
    assert result.final_output.candidates[1].title == second.title
    assert result.final_output.dispositions[1].structure_unit_id == "su-02"
    assert len(result.attempts) == 2
    assert result.attempts[0].error_classes == ["WIRE_SCHEMA_INVALID"]
    atom_schema = protocol_control_atom_repair_response_format()["json_schema"]
    assert atom_schema["name"] == "protocol_control_atom_repair_v1"
    assert list(atom_schema["schema"]["properties"]) == ["atom"]


def test_invalid_continuing_obligation_uses_candidate_repair_not_frozen_atom_repair() -> None:
    batch = _batch()
    first = _candidate()
    second = _candidate_for_second_unit()
    initial = _wire_with_two_candidates(first, second).model_dump(mode="json")
    atom = initial["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]
    atom["continuing_obligation"] = {
        "statement": "治疗期继续达到年龄条件",
        "prospective_period": {"period": "treatment_period"},
        "source_span_ids": ["span:01"],
        "source_excerpts": ["年龄至少18岁"],
        "status": "not_due_at_review_node",
    }

    class CandidateTransport(_FakeTransport):
        def continue_atom(self, *, session_id: str, prompt: str):
            pytest.fail("延续义务错误不能由冻结该字段的单原子修订处理")

        def continue_candidate(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            assert "后续持续义务不能挂在完成、给药或记录原子上" in prompt
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"candidate_draft": first.model_dump(mode="json")}, ensure_ascii=False),
            )

    transport = CandidateTransport([
        ProtocolControlAgentResponse(
            session_id="candidate-session",
            text=json.dumps(initial, ensure_ascii=False),
        )
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(batch, transport)
    assert result.status == "已解析"
    assert result.final_output is not None
    assert result.final_output.candidates[1].title == second.title
    assert [item.outcome for item in result.attempts] == ["schema_invalid", "parsed"]


def test_atom_repair_cannot_rewrite_source_or_siblings() -> None:
    valid = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit())
    baseline = valid.model_dump(mode="json")
    del baseline["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]["evaluation"]
    original = _candidate().obligation_expression.groups[0].atoms[0].model_dump(mode="json")
    merged = _merge_obligation_atom_repair(
        json.dumps({"atom": original}), baseline, (0, 0, 0)
    )
    assert merged.dispositions == valid.dispositions
    assert merged.candidate_drafts[1] == valid.candidate_drafts[1]
    changed = {**original, "statement": "新增无来源的医学义务"}
    with pytest.raises(ProtocolControlAgentWireValidationError, match="不得改变 statement"):
        _merge_obligation_atom_repair(
            json.dumps({"atom": changed}), baseline, (0, 0, 0)
        )


def test_multiple_missing_observation_policies_repair_only_requested_fields() -> None:
    valid = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit())
    baseline = valid.model_dump(mode="json")
    atoms = baseline["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"]
    second = deepcopy(atoms[0])
    second["statement"] = "核对年龄资料"
    second["evaluation"]["proposition"] = "核对年龄资料"
    atoms.append(second)
    for atom in atoms:
        atom["evaluation"]["observation_policy"] = None
    with pytest.raises(ProtocolControlAgentWireValidationError) as exc:
        parse_protocol_control_agent_wire(json.dumps(baseline))
    paths = _invalid_observation_policy_paths(exc.value, baseline, 0)
    assert paths == ((0, 0), (0, 1))
    repair_prompt = _build_observation_policy_repair_prompt(
        baseline, 0, paths, "观察采用说明缺失"
    )
    assert "年龄至少18岁" in repair_prompt
    assert "其他控制：年龄至少18岁" not in repair_prompt

    policy = {
        "mode": "unresolved", "scope": "原文未说明采用哪次记录",
        "source_span_ids": ["span:01"], "source_excerpts": ["年龄至少18岁"],
    }
    repair = {"items": [
        {"group_index": 0, "atom_index": index, "policy": policy}
        for index in (0, 1)
    ]}
    merged = _merge_observation_policy_repair(json.dumps(repair), baseline, 0, paths)
    assert merged.candidate_drafts[1] == valid.candidate_drafts[1]
    assert [atom.statement for atom in merged.candidate_drafts[0].obligation_expression.groups[0].atoms] == [
        "年龄达到18岁", "核对年龄资料",
    ]
    schema = protocol_control_observation_repair_response_format()["json_schema"]
    assert schema["name"] == "protocol_control_observation_repair_v1"
    repair["items"][1]["atom_index"] = 2
    with pytest.raises(ProtocolControlAgentWireValidationError, match="授权范围"):
        _merge_observation_policy_repair(json.dumps(repair), baseline, 0, paths)


def test_future_observation_scope_repair_preserves_policy_and_source() -> None:
    wire = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit())
    baseline = wire.model_dump(mode="json")
    atom = baseline["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]
    atom["kind"] = ControlObligationKind.PROHIBIT_EVENT.value
    atom["continuing_obligation"] = {
        "statement": "治疗期不得调整背景治疗",
        "prospective_period": {"period": "treatment_period"},
        "source_span_ids": atom["source_span_ids"],
        "source_excerpts": atom["source_excerpts"],
        "status": "not_due_at_review_node",
    }
    atom["evaluation"]["observation_policy"]["scope"] = "筛选期及双盲治疗期背景治疗调整记录"
    wire = ProtocolControlAgentWire.model_validate(baseline)
    error = ProtocolControlAgentWireValidationError(
        "PUBLICATION_GATE_REJECTED", "当前节点的观察范围不得要求覆盖后续期间",
        candidate_indexes=[0], error_class_codes=["FUTURE_PROHIBITION_DECIDED_EARLY"],
    )
    path = _future_observation_scope_repair_path(error, wire, {0})
    assert path == (0, ((0, 0),))
    assert _future_prohibition_repair_path(error, wire, {0}) is None
    policy = dict(atom["evaluation"]["observation_policy"])
    policy["scope"] = "截至当前审核节点的背景治疗调整记录"
    repair = {"items": [{"group_index": 0, "atom_index": 0, "policy": policy}]}
    prompt = _build_observation_policy_repair_prompt(baseline, 0, ((0, 0),), str(error))
    assert "仅修正现有观察采用说明" in prompt
    merged = _merge_observation_policy_repair(json.dumps(repair), baseline, 0, ((0, 0),))
    changed = merged.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    assert changed.evaluation.observation_policy.scope == policy["scope"]
    assert merged.candidate_drafts[1] == wire.candidate_drafts[1]
    repair["items"][0]["policy"]["source_excerpts"] = ["另一份资料"]
    with pytest.raises(ProtocolControlAgentWireValidationError, match="只允许修正 scope"):
        _merge_observation_policy_repair(json.dumps(repair), baseline, 0, ((0, 0),))


def test_runner_uses_policy_only_repair_for_multiple_atoms() -> None:
    batch = _batch()
    candidate = _candidate().model_copy(deep=True)
    atoms = candidate.obligation_expression.groups[0].atoms
    second = atoms[0].model_copy(deep=True)
    second.statement = "核对年龄资料"
    second.evaluation = second.evaluation.model_copy(update={"proposition": "核对年龄资料"})
    atoms.append(second)
    initial = _wire_with_two_candidates(candidate, _candidate_for_second_unit()).model_dump(mode="json")
    original_atoms = initial["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"]
    for atom in original_atoms:
        atom["evaluation"]["observation_policy"] = None
    policy = {
        "mode": "unresolved", "scope": "原文未说明采用哪次记录",
        "source_span_ids": ["span:01"], "source_excerpts": ["年龄至少18岁"],
    }

    class PolicyTransport(_FakeTransport):
        def continue_observation_policies(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            assert "核对年龄资料" in prompt
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"items": [
                    {"group_index": 0, "atom_index": index, "policy": policy}
                    for index in (0, 1)
                ]}),
            )

    transport = PolicyTransport([
        ProtocolControlAgentResponse(session_id="policy-session", text=json.dumps(initial))
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(batch, transport)
    assert result.status == "已解析"
    assert result.final_output is not None
    assert len(result.attempts) == 2


def test_time_operand_repair_is_exact_and_unresolved_stays_unverified() -> None:
    valid = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit())
    baseline = valid.model_dump(mode="json")
    atoms = baseline["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"]
    atoms.append(deepcopy(atoms[0]))
    for atom in atoms:
        atom["time_constraint"] = {"anchor_type": "screening_date", "direction": "before"}
        atom["evaluation"]["time_purpose"] = "unresolved"
        atom["evaluation"]["time_operand_attribute"] = None
    with pytest.raises(ProtocolControlAgentWireValidationError) as exc:
        parse_protocol_control_agent_wire(json.dumps(baseline))
    paths = _invalid_time_operand_paths(exc.value, baseline, 0)
    assert paths == ((0, 0), (0, 1))
    repair = {"items": [
        {"group_index": 0, "atom_index": index, "attribute": "record_time"}
        for index in (0, 1)
    ]}
    merged = _merge_time_operand_repair(json.dumps(repair), baseline, 0, paths)
    assert merged.candidate_drafts[1] == valid.candidate_drafts[1]
    assert all(atom.evaluation.time_operand_attribute == "record_time"
               for atom in merged.candidate_drafts[0].obligation_expression.groups[0].atoms)
    assert protocol_control_time_operand_repair_response_format()["json_schema"]["name"] == "protocol_control_time_operand_repair_v1"
    repair["items"][1]["attribute"] = "unresolved"
    with pytest.raises(ProtocolControlAgentWireValidationError, match="原文不足") as unresolved:
        _merge_time_operand_repair(json.dumps(repair), baseline, 0, paths)
    assert unresolved.value.code == "TIME_OPERAND_UNRESOLVED"


def test_runner_uses_bounded_time_operand_repair() -> None:
    batch = _batch()
    initial = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit()).model_dump(mode="json")
    atoms = initial["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"]
    atoms.append(deepcopy(atoms[0]))
    for atom in atoms:
        atom["time_constraint"] = {"anchor_type": "screening_date", "direction": "before"}
        atom["evaluation"]["time_purpose"] = "unresolved"
        atom["evaluation"]["time_operand_attribute"] = None

    class DateTransport(_FakeTransport):
        def continue_time_operands(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            assert session_id == "date-session"
            assert "time_operand_attribute" not in prompt or "null" in prompt
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"items": [
                    {"group_index": 0, "atom_index": index, "attribute": "record_time"}
                    for index in (0, 1)
                ]}),
            )

    transport = DateTransport([
        ProtocolControlAgentResponse(session_id="date-session", text=json.dumps(initial))
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(batch, transport)
    assert len(transport.prompts) == 2
    assert len(result.attempts) == 2
    assert result.attempts[0].error_classes == ["WIRE_SCHEMA_INVALID"]
    assert result.status == "已解析"


def test_evidence_source_repair_preserves_other_fields_and_rejects_invented_quote() -> None:
    batch = _batch()
    valid = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit())
    baseline = valid.model_dump(mode="json")
    policy = baseline["candidate_drafts"][0]["minimum_evidence"][0]["source_policy"]
    del policy["source_excerpts"]
    with pytest.raises(ProtocolControlAgentWireValidationError) as exc:
        parse_protocol_control_agent_wire(json.dumps(baseline))
    path = _invalid_evidence_source_policy_path(exc.value, baseline, 0)
    assert path == (0, 0)
    prompt = _build_evidence_source_policy_repair_prompt(batch, baseline, path, str(exc.value))
    assert "年龄至少18岁" in prompt
    assert "其他控制：年龄至少18岁" in prompt
    repaired_policy = valid.candidate_drafts[0].minimum_evidence[0].source_policy.model_dump(mode="json")
    merged = _merge_evidence_source_policy_repair(
        json.dumps({"policy": repaired_policy}), baseline, path, batch
    )
    assert merged == valid
    assert protocol_control_evidence_source_repair_response_format()["json_schema"]["name"] == "protocol_control_evidence_source_repair_v1"
    invented = {**repaired_policy, "source_excerpts": ["方案未写出的检查期限"]}
    with pytest.raises(ProtocolControlAgentWireValidationError, match="不属于授权原文"):
        _merge_evidence_source_policy_repair(
            json.dumps({"policy": invented}), baseline, path, batch
        )


def test_runner_repairs_only_one_evidence_source_policy() -> None:
    batch = _batch()
    valid = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit())
    initial = valid.model_dump(mode="json")
    del initial["candidate_drafts"][0]["minimum_evidence"][0]["source_policy"]["source_excerpts"]
    policy = valid.candidate_drafts[0].minimum_evidence[0].source_policy.model_dump(mode="json")

    class EvidenceTransport(_FakeTransport):
        def continue_evidence_source_policy(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"policy": policy}, ensure_ascii=False),
            )

    transport = EvidenceTransport([
        ProtocolControlAgentResponse(session_id="evidence-session", text=json.dumps(initial))
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(batch, transport)
    assert result.status == "已解析"
    assert result.final_output is not None
    assert result.final_output.candidates[1].title == valid.candidate_drafts[1].title
    assert len(result.attempts) == 2
    assert "仅修订这一项最低证据" in transport.prompts[1]


def test_multiple_invalid_initial_candidates_do_not_get_single_candidate_repair() -> None:
    valid = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit())
    initial = valid.model_dump(mode="json")
    for draft in initial["candidate_drafts"]:
        del draft["obligation_expression"]["groups"][0]["atoms"][0]["evaluation"]
    assert _single_invalid_candidate_payload(json.dumps(initial)) is None
    assert _invalid_candidate_payload(json.dumps(initial))[1] == (0, 1)

    class CandidateTransport(_FakeTransport):
        def continue_candidates(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({
                    "candidate_drafts": [
                        item.model_dump(mode="json") for item in valid.candidate_drafts
                    ]
                }),
            )

    transport = CandidateTransport([
        ProtocolControlAgentResponse(
            session_id="candidate-session", text=json.dumps(initial)
        )
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(_batch(), transport)
    assert result.status == "已解析"
    assert result.final_output is not None
    assert len(result.final_output.candidates) == 2
    assert "同样数量的 candidate_drafts" in transport.prompts[1]

    with pytest.raises(ProtocolControlAgentWireValidationError, match="数量"):
        _merge_candidate_repairs(
            json.dumps({"candidate_drafts": [valid.candidate_drafts[0].model_dump(mode="json")]}),
            initial, (0, 1),
        )
    with pytest.raises(ProtocolControlAgentWireValidationError, match="调换候选"):
        _merge_candidate_repairs(
            json.dumps({"candidate_drafts": [
                valid.candidate_drafts[1].model_dump(mode="json"),
                valid.candidate_drafts[0].model_dump(mode="json"),
            ]}),
            initial, (0, 1),
        )


def test_runner_repairs_only_the_rejected_candidate_when_transport_supports_it() -> None:
    batch = _batch()
    first = _candidate()
    second = _candidate_for_second_unit()
    initial = _wire_with_two_candidates(first, second)
    repaired = first.model_copy(update={"title": "年龄资料控制（已核对）"})

    class CandidateTransport(_FakeTransport):
        def continue_candidate(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            assert session_id == "candidate-session"
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"candidate_draft": repaired.model_dump(mode="json")}),
            )

    transport = CandidateTransport(
        [ProtocolControlAgentResponse(session_id="candidate-session", text=initial.model_dump_json())]
    )
    calls = 0

    def reject_first_once(output):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ProtocolControlAgentWireValidationError(
                "CANDIDATE_REJECTED",
                "第一个候选需要修订",
                candidate_ids=[output.candidates[0].control_candidate_id],
                structure_unit_ids=["su-01"],
            )

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        batch, transport, output_validator=reject_first_once
    )
    assert result.status == "已解析"
    assert result.final_output is not None
    assert [item.title for item in result.final_output.candidates] == [
        repaired.title,
        second.title,
    ]
    assert "仅返回包含 candidate_draft" in transport.prompts[1]


def test_atom_level_gate_error_keeps_owning_candidate_repair_scope() -> None:
    hydrated = hydrate_protocol_control_agent_output(_wire(candidate=_candidate()), _batch())
    candidate = hydrated.candidates[0]
    issue = SimpleNamespace(
        code="TIME_ANCHOR_MISSING",
        message="时间原子缺少命名锚点",
        entity_id=candidate.control_candidate_id + "/atom-1",
        candidate_ids=[],
        structure_unit_ids=[],
        obligation_source_span_ids=[],
    )
    error = publication_repair_error(
        issues=[issue],
        candidate_by_id={candidate.control_candidate_id: candidate},
        control_to_candidate={},
        default_structure_unit_ids=["su-01", "su-02"],
    )
    assert error.candidate_ids == (candidate.control_candidate_id,)
    assert error.structure_unit_ids == ("su-01",)


def _missing_source_error():
    return publication_repair_error(
        issues=[SimpleNamespace(
            code="ENROLLMENT_PROHIBITION_UNCOVERED",
            message="来源中的要求尚未形成候选",
            entity_id="su-01",
            candidate_ids=[],
            structure_unit_ids=["su-01"],
            obligation_source_span_ids=["span:01"],
        )],
        candidate_by_id={},
        control_to_candidate={},
        default_structure_unit_ids=["su-01", "su-02"],
    )


def test_missing_source_can_insert_candidate_without_existing_candidate_id() -> None:
    initial = _wire()
    repaired = _wire(candidate=_candidate())
    transport = _FakeTransport([
        ProtocolControlAgentResponse(session_id="insert-1", text=initial.model_dump_json()),
        ProtocolControlAgentResponse(session_id="insert-1", text=repaired.model_dump_json()),
    ])
    calls = 0

    def validate(output) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _missing_source_error()
        assert len(output.candidates) == 1

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        _batch(), transport, output_validator=validate
    )
    assert result.status == "已解析"
    assert calls == 2
    assert _missing_source_error().allow_source_insert is True
    assert "来源限定补入" in transport.prompts[1]
    assert "上一轮完整输出摘要" in transport.prompts[1]


def test_missing_source_uses_single_candidate_response_when_transport_supports_it() -> None:
    initial = _wire()

    class InsertTransport(_FakeTransport):
        def continue_candidate(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            assert session_id == "insert-single"
            assert "上一轮完整输出摘要" in prompt
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"candidate_draft": _candidate().model_dump(mode="json")}),
            )

    transport = InsertTransport([
        ProtocolControlAgentResponse(session_id="insert-single", text=initial.model_dump_json())
    ])
    calls = 0

    def validate(output) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _missing_source_error()
        assert len(output.candidates) == 1
        assert output.dispositions[1].disposition == StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        _batch(), transport, output_validator=validate
    )
    assert result.status == "已解析"
    assert calls == 2
    assert "仅返回包含 candidate_draft" in transport.prompts[1]


@pytest.mark.parametrize("violation", ["other_disposition", "wrong_source", "changed_candidate"])
def test_source_insert_rejects_changes_outside_authorized_scope(violation: str) -> None:
    initial = _wire()
    if violation == "changed_candidate":
        initial = _wire(candidate=_candidate())
        repaired = initial.model_dump(mode="json")
        repaired["candidate_drafts"][0]["title"] = "未经授权改写"
        repaired["candidate_drafts"].append(_candidate().model_dump(mode="json"))
    elif violation == "wrong_source":
        repaired = _wire(candidate=_candidate_for_second_unit()).model_dump(mode="json")
    else:
        repaired = _wire(candidate=_candidate()).model_dump(mode="json")
        repaired["dispositions"][1]["notes"] = "未经授权改写"
    transport = _FakeTransport([
        ProtocolControlAgentResponse(session_id="insert-2", text=initial.model_dump_json()),
        ProtocolControlAgentResponse(session_id="insert-2", text=json.dumps(repaired, ensure_ascii=False)),
    ])

    def validate(_output) -> None:
        raise _missing_source_error()

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        _batch(), transport, output_validator=validate
    )
    assert result.status == "需要核对"
    assert "REPAIR_SCOPE_ESCAPE" in result.attempts[-1].issues[0]


def test_successful_source_insert_allows_one_bounded_candidate_correction() -> None:
    initial = _wire()
    initial.dispositions[0] = ProtocolControlAgentWireDisposition(
        structure_unit_id="su-01",
        disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
        linked_official_code=None,
        linked_procedure_catalog_item_id="procedure-screening-1",
        linked_procedure_catalog_item_ids=[],
        notes=None,
    )
    inserted = _wire(candidate=_candidate()).model_dump(mode="json")
    inserted["candidate_drafts"][0]["cross_source_relations"] = [{
        "kind": "supplementary_requirement",
        "external_target_kind": "required_procedure",
        "external_target_id": "procedure-screening-1",
        "candidate_side": "left",
        "affected_workflow_stage_id": "stage:screening:one",
        "notes": None,
    }]
    corrected = _candidate().model_dump(mode="json")
    corrected["title"] = "已核对的年龄资料控制"
    corrected["cross_source_relations"] = inserted["candidate_drafts"][0]["cross_source_relations"]
    class CandidateTransport(_FakeTransport):
        def continue_candidate(self, *, session_id: str, prompt: str) -> ProtocolControlAgentResponse:
            return self.continue_session(session_id=session_id, prompt=prompt)

    transport = CandidateTransport([
        ProtocolControlAgentResponse(session_id="insert-correct", text=initial.model_dump_json()),
        ProtocolControlAgentResponse(session_id="insert-correct", text=json.dumps(inserted, ensure_ascii=False)),
        ProtocolControlAgentResponse(
            session_id="insert-correct",
            text=json.dumps({"candidate_draft": corrected}, ensure_ascii=False),
        ),
    ])
    calls = 0

    def validate(output) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _missing_source_error()
        if calls == 2:
            raise ProtocolControlAgentWireValidationError(
                "PUBLICATION_GATE_REJECTED", "审核指引缺少来源",
                candidate_ids=[output.candidates[0].control_candidate_id],
                structure_unit_ids=["su-01"],
            )
        assert output.candidates[0].title == corrected["title"]

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        _batch(), transport, output_validator=validate,
    )
    assert result.status == "已解析", [(item.outcome, item.issues) for item in result.attempts]
    assert calls == 3
    assert transport.prompts[-1].find("只修复指定的一个候选") >= 0


def test_explicit_candidate_repartition_preserves_authorized_source_union() -> None:
    first = _candidate()
    second = _candidate_for_second_unit()
    combined = first.model_copy(
        update={
            "title": "混合的年龄与用药候选",
            "source_structure_unit_ids": ["su-01", "su-02"],
            "source_span_ids": ["span:01", "span:02"],
        }
    )
    initial = _wire(candidate=combined).model_dump(mode="json")
    initial["dispositions"][1].update(
        disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value,
        notes=None,
    )
    initial_wire = ProtocolControlAgentWire.model_validate(initial)
    repartitioned_wire = _wire_with_two_candidates(first, second)
    transport = _FakeTransport(
        [
            ProtocolControlAgentResponse(
                session_id="session-1", text=initial_wire.model_dump_json()
            ),
            ProtocolControlAgentResponse(
                session_id="session-1", text=repartitioned_wire.model_dump_json()
            ),
        ]
    )
    calls = 0

    def validate_after_hydration(output) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ProtocolControlAgentWireValidationError(
                "ACTION_TARGET_SCOPE_MISMATCH",
                "候选必须按来源作用域拆分",
                structure_unit_ids=["su-01", "su-02"],
                candidate_ids=[output.candidates[0].control_candidate_id],
                allow_candidate_repartition=True,
            )

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        _batch(),
        transport,
        output_validator=validate_after_hydration,
    )

    assert result.status == "已解析"
    assert result.final_output is not None
    assert {
        tuple(candidate.frozen_structure_unit_ids)
        for candidate in result.final_output.candidates
    } == {("su-01",), ("su-02",)}


@pytest.mark.parametrize("removed_disposition", [
    StructureUnitDispositionKind.POST_TREATMENT_EXECUTION,
    StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
])
def test_post_treatment_reclassification_requires_explicit_disposition(
    removed_disposition: StructureUnitDispositionKind,
) -> None:
    combined = _candidate().model_copy(update={
        "source_structure_unit_ids": ["su-01", "su-02"],
        "source_span_ids": ["span:01", "span:02"],
    })
    initial_data = _wire(candidate=combined).model_dump(mode="json")
    initial_data["dispositions"][1].update(
        disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value,
        notes=None,
    )
    initial = ProtocolControlAgentWire.model_validate(initial_data)
    revised = initial.model_dump(mode="json")
    revised["candidate_drafts"][0] = _candidate().model_dump(mode="json")
    revised["dispositions"][1].update(
        disposition=removed_disposition.value,
        notes="该原文单元仅说明治疗期执行事项",
    )
    transport = _FakeTransport([
        ProtocolControlAgentResponse(session_id="stage-repair", text=initial.model_dump_json()),
        ProtocolControlAgentResponse(session_id="stage-repair", text=json.dumps(revised)),
    ])
    calls = 0

    def reject_first(output) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ProtocolControlAgentWireValidationError(
                "POST_ENROLLMENT_PROCEDURE_MISCLASSIFIED",
                "候选混入治疗期执行事项",
                structure_unit_ids=["su-01", "su-02"],
                candidate_ids=[output.candidates[0].control_candidate_id],
                allow_source_closure_rewrite=True,
                allow_post_enrollment_reclassification=True,
            )

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        _batch(), transport, output_validator=reject_first
    )
    if removed_disposition == StructureUnitDispositionKind.POST_TREATMENT_EXECUTION:
        assert result.status == "已解析"
        assert result.final_output is not None
        assert result.final_output.candidates[0].frozen_structure_unit_ids == ["su-01"]
    else:
        assert result.status == "需要核对"
        assert "REPAIR_SCOPE_ESCAPE" in result.attempts[-1].issues[0]


def test_post_treatment_repair_retains_checked_atoms_and_requires_explicit_source_move() -> None:
    batch = _batch().model_copy(update={
        "owned_units": [
            _batch().owned_units[0],
            _unit("su-02", 2, "span:02", "治疗期完成另一项研究操作"),
        ]
    })
    original = _candidate().model_dump(mode="json")
    first = original["obligation_expression"]["groups"][0]["atoms"][0]
    first["time_constraint"] = {"anchor_type": "screening_date", "direction": "before"}
    first["evaluation"] = _timed_evaluation(first["statement"], "span:01", "年龄至少18岁")
    later = deepcopy(first)
    later["statement"] = "后续治疗期完成另一项研究操作"
    _replace_atom_source(later, "span:02", "治疗期完成另一项研究操作")
    later["time_constraint"] = None
    original["obligation_expression"]["groups"][0]["atoms"].append(later)
    original["source_structure_unit_ids"] = ["su-01", "su-02"]
    original["source_span_ids"] = ["span:01", "span:02"]
    original_candidate = ProtocolControlAgentWireCandidate.model_validate(original)
    baseline = _wire(candidate=original_candidate).model_dump(mode="json")
    baseline["dispositions"][1].update(
        disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value, notes=None,
    )
    baseline_wire = ProtocolControlAgentWire.model_validate(baseline)
    repair = {
        "removed_atoms": [{"group_index": 0, "atom_index": 1}],
        "released_shared_units": [],
        "removed_unit_dispositions": [{
            **baseline["dispositions"][1],
            "disposition": StructureUnitDispositionKind.POST_TREATMENT_EXECUTION.value,
            "notes": "原文仅描述后续治疗期操作",
        }],
        "title": "年龄资料控制",
        "review_node_bindings": original["review_node_bindings"],
        "minimum_evidence": original["minimum_evidence"],
        "cross_source_relations": [],
    }
    merged = _merge_post_treatment_scope_repair(
        json.dumps(repair), baseline_wire, 0, batch
    )
    assert merged.candidate_drafts[0].obligation_expression.groups[0].atoms[0] == original_candidate.obligation_expression.groups[0].atoms[0]
    assert merged.candidate_drafts[0].source_structure_unit_ids == ["su-01"]
    assert merged.dispositions[1].disposition == StructureUnitDispositionKind.POST_TREATMENT_EXECUTION
    assert protocol_control_post_treatment_repair_response_format()["json_schema"]["name"] == "protocol_control_post_treatment_repair_v2"

    class NarrowTransport(_FakeTransport):
        def continue_post_treatment_repair(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            assert "原候选原子" in prompt
            return ProtocolControlAgentResponse(session_id=session_id, text=json.dumps(repair))

    transport = NarrowTransport([
        ProtocolControlAgentResponse(session_id="stage-repair", text=baseline_wire.model_dump_json())
    ])
    calls = 0

    def reject_mixed_candidate(output) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ProtocolControlAgentWireValidationError(
                "POST_ENROLLMENT_PROCEDURE_MISCLASSIFIED",
                "后续研究操作混入当前节点",
                structure_unit_ids=["su-01", "su-02"],
                candidate_ids=[output.candidates[0].control_candidate_id],
                allow_source_closure_rewrite=True,
                allow_post_enrollment_reclassification=True,
            )

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        batch, transport, output_validator=reject_mixed_candidate
    )
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert result.final_output is not None
    assert len(transport.prompts) == 2

    repair["removed_unit_dispositions"][0]["disposition"] = StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT.value
    with pytest.raises(ProtocolControlAgentWireValidationError, match="POST_TREATMENT_REPAIR_INVALID"):
        _merge_post_treatment_scope_repair(json.dumps(repair), baseline_wire, 0, batch)


def test_post_treatment_repair_releases_shared_unit_without_reclassifying_other_candidate() -> None:
    batch = _batch().model_copy(update={
        "owned_units": [
            _batch().owned_units[0],
            _unit("su-02", 2, "span:02", "筛选时记录末次用药日期；治疗期完成另一项研究操作"),
        ]
    })
    first = _candidate().model_dump(mode="json")
    later = deepcopy(first["obligation_expression"]["groups"][0]["atoms"][0])
    later["statement"] = "治疗期完成另一项研究操作"
    _replace_atom_source(later, "span:02", "治疗期完成另一项研究操作")
    first["obligation_expression"]["groups"][0]["atoms"].append(later)
    first["source_structure_unit_ids"] = ["su-01", "su-02"]
    first["source_span_ids"] = ["span:01", "span:02"]
    second = _candidate().model_dump(mode="json")
    second["title"] = "筛选时记录要求"
    second["source_structure_unit_ids"] = ["su-02"]
    second["source_span_ids"] = ["span:02"]
    for layer in ("applicability_expression", "obligation_expression", "exception_expression"):
        for group in second[layer]["groups"]:
            for atom in group["atoms"]:
                _replace_atom_source(atom, "span:02", "筛选时记录末次用药日期")
    second["minimum_evidence"][0]["source_policy"] = _evidence_policy(
        "span:02", "筛选时记录末次用药日期"
    )
    wire_data = _wire(candidate=ProtocolControlAgentWireCandidate.model_validate(first)).model_dump(mode="json")
    wire_data["dispositions"][1].update(
        disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value,
        notes=None,
    )
    wire_data["candidate_drafts"].append(second)
    baseline = ProtocolControlAgentWire.model_validate(wire_data)
    repair = {
        "removed_atoms": [{"group_index": 0, "atom_index": 1}],
        "released_shared_units": [{
            "structure_unit_id": "su-02",
            "source_excerpt": "治疗期完成另一项研究操作",
            "notes": "只移出首个候选的后续研究操作，不改变第二个候选的当前要求",
        }],
        "removed_unit_dispositions": [],
        "title": first["title"],
        "review_node_bindings": first["review_node_bindings"],
        "minimum_evidence": first["minimum_evidence"],
        "cross_source_relations": [],
    }
    merged = _merge_post_treatment_scope_repair(json.dumps(repair), baseline, 0, batch)
    assert merged.candidate_drafts[0].source_structure_unit_ids == ["su-01"]
    assert merged.candidate_drafts[1] == baseline.candidate_drafts[1]
    assert merged.dispositions == baseline.dispositions
    validate_protocol_control_agent_wire(merged, batch)

    repair["released_shared_units"][0]["source_excerpt"] = "原文中没有的事项"
    with pytest.raises(ProtocolControlAgentWireValidationError, match="POST_TREATMENT_REPAIR_INVALID"):
        _merge_post_treatment_scope_repair(json.dumps(repair), baseline, 0, batch)
    repair["released_shared_units"] = []
    repair["removed_unit_dispositions"] = [{
        **wire_data["dispositions"][1],
        "disposition": StructureUnitDispositionKind.POST_TREATMENT_EXECUTION.value,
        "notes": "治疗期完成另一项研究操作",
    }]
    with pytest.raises(ProtocolControlAgentWireValidationError, match="POST_TREATMENT_REPAIR_INVALID"):
        _merge_post_treatment_scope_repair(json.dumps(repair), baseline, 0, batch)


def test_future_prohibition_patch_splits_only_current_text_and_continuation() -> None:
    source = "筛选期及治疗期不得调整背景治疗"
    batch = _batch().model_copy(update={
        "owned_units": [
            _unit("su-01", 1, "span:01", f"年龄至少18岁；{source}"),
            _batch().owned_units[1],
        ]
    })
    draft = _candidate().model_dump(mode="json")
    atom = draft["obligation_expression"]["groups"][0]["atoms"][0]
    atom.update(kind=ControlObligationKind.PROHIBIT_EVENT.value,
                statement=source,
                evaluation=_evaluation(source, "span:01", source),
                source_excerpts=[source])
    initial = _wire(candidate=ProtocolControlAgentWireCandidate.model_validate(draft))
    error = ProtocolControlAgentWireValidationError(
        "PUBLICATION_GATE_REJECTED", "当前节点不能证明后续期间",
        structure_unit_ids=["su-01"], candidate_indexes=[0],
        error_class_codes=["FUTURE_PROHIBITION_DECIDED_EARLY"],
    )
    path = _future_prohibition_repair_path(error, initial, {0})
    assert path == (0, 0, 0)
    repair = {"current_statement": "筛选期不得调整背景治疗",
              "current_proposition": "筛选期不得调整背景治疗",
              "continuing_obligation": {
        "statement": "治疗期不得调整背景治疗",
        "prospective_period": {"period": "treatment_period"},
        "source_span_ids": ["span:01"], "source_excerpts": [source],
        "status": "not_due_at_review_node",
    }}
    merged = _merge_future_prohibition_repair(json.dumps(repair), initial, path)
    changed = merged.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    assert changed.continuing_obligation is not None
    assert changed.statement == repair["current_statement"]
    assert changed.evaluation.proposition == repair["current_proposition"]
    assert changed.model_copy(update={
        "statement": source,
        "evaluation": initial.candidate_drafts[0].obligation_expression.groups[0].atoms[0].evaluation,
        "continuing_obligation": None,
    }) == initial.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    assert merged.dispositions == initial.dispositions
    validate_protocol_control_agent_wire(merged, batch)
    assert protocol_control_future_prohibition_repair_response_format()["json_schema"]["name"] == "protocol_control_future_prohibition_repair_v2"

    class FocusedTransport(_FakeTransport):
        def continue_candidate(self, *, session_id: str, prompt: str):
            pytest.fail("后续禁止修订不得重写整个候选")

        def continue_future_prohibition_repair(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            assert "当前 statement" in prompt
            return ProtocolControlAgentResponse(session_id=session_id, text=json.dumps(repair))

    transport = FocusedTransport([
        ProtocolControlAgentResponse(session_id="future-session", text=initial.model_dump_json())
    ])
    calls = 0

    def reject_future_once(output) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ProtocolControlAgentWireValidationError(
                "PUBLICATION_GATE_REJECTED", "当前节点不能证明后续期间",
                structure_unit_ids=["su-01"],
                candidate_ids=[output.candidates[0].control_candidate_id],
                error_class_codes=["FUTURE_PROHIBITION_DECIDED_EARLY"],
            )

    result = ProtocolControlAgentRunner(max_schema_repairs=0).run(
        batch, transport, output_validator=reject_future_once
    )
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert len(result.attempts) == 2

    mixed_again = merged.model_dump(mode="json")
    mixed_atom = mixed_again["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]
    mixed_atom["statement"] = source
    mixed_atom["evaluation"]["proposition"] = source
    with_existing_continuation = ProtocolControlAgentWire.model_validate(mixed_again)
    existing_repair = {**repair, "continuing_obligation": None}
    corrected = _merge_future_prohibition_repair(
        json.dumps(existing_repair), with_existing_continuation, path
    )
    corrected_atom = corrected.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    assert corrected_atom.continuing_obligation == changed.continuing_obligation
    assert corrected_atom.statement == "筛选期不得调整背景治疗"
    assert _future_prohibition_repair_path(error, with_existing_continuation, {0}) == path
    same_continuation = _merge_future_prohibition_repair(
        json.dumps(repair), with_existing_continuation, path
    )
    assert (
        same_continuation.candidate_drafts[0].obligation_expression.groups[0]
        .atoms[0].continuing_obligation == changed.continuing_obligation
    )
    altered_continuation = json.loads(json.dumps(repair))
    altered_continuation["continuing_obligation"]["statement"] = "治疗期可以调整背景治疗"
    with pytest.raises(ProtocolControlAgentWireValidationError, match="FUTURE_PROHIBITION_REPAIR_INVALID"):
        _merge_future_prohibition_repair(
            json.dumps(altered_continuation), with_existing_continuation, path
        )
    with pytest.raises(ProtocolControlAgentWireValidationError, match="FUTURE_PROHIBITION_REPAIR_INVALID"):
        _merge_future_prohibition_repair(initial.model_dump_json(), initial, path)

    repair["continuing_obligation"]["source_excerpts"] = ["原文不存在的后续要求"]
    with pytest.raises(ProtocolControlAgentWireValidationError, match="FUTURE_PROHIBITION_REPAIR_INVALID"):
        _merge_future_prohibition_repair(json.dumps(repair), initial, path)


def test_early_anchor_atom_repair_is_unique_and_cannot_target_siblings() -> None:
    error = ProtocolControlAgentWireValidationError(
        "PUBLICATION_GATE_REJECTED", "早期节点不能终判后续锚点",
        error_class_codes=["EARLY_DECISION_FOR_FUTURE_ANCHOR"],
    )
    atom = SimpleNamespace(time_constraint=SimpleNamespace(
        anchor_type=SimpleNamespace(value="baseline_date")
    ))
    wire = SimpleNamespace(candidate_drafts=[SimpleNamespace(
        obligation_expression=SimpleNamespace(groups=[SimpleNamespace(atoms=[atom])])
    )])
    assert _early_anchor_atom_repair_path(error, wire, {0}) == (0, 0, 0)
    wire.candidate_drafts[0].obligation_expression.groups[0].atoms.append(atom)
    assert _early_anchor_atom_repair_path(error, wire, {0}) is None
    assert _early_anchor_atom_repair_path(error, wire, {1}) is None


def test_calendar_bound_patch_changes_only_one_sourced_time_field() -> None:
    draft = _candidate().model_dump(mode="json")
    atom = draft["obligation_expression"]["groups"][0]["atoms"][0]
    atom["kind"] = ControlObligationKind.COMPLETE_BEFORE_ANCHOR.value
    atom["time_constraint"] = {
        "anchor_type": "screening_date", "direction": "before", "upper_bound_days": 7
    }
    atom["evaluation"] = _timed_evaluation(atom["statement"], "span:01", "年龄至少18岁")
    sibling = deepcopy(atom)
    sibling["kind"] = ControlObligationKind.MUST_RECORD.value
    sibling["statement"] = "记录筛选资料"
    sibling["evaluation"] = _evaluation("记录筛选资料", "span:01", "年龄至少18岁")
    sibling["time_constraint"] = None
    draft["obligation_expression"]["groups"][0]["atoms"].append(sibling)
    initial = _wire(candidate=ProtocolControlAgentWireCandidate.model_validate(draft))
    error = ProtocolControlAgentWireValidationError(
        "PUBLICATION_GATE_REJECTED", "数值缺少原文支持",
        structure_unit_ids=["su-01"], candidate_indexes=[0],
        obligation_source_span_ids=["span:01"],
        error_class_codes=["TIME_CALENDAR_BOUND_UNSUPPORTED"],
    )
    path = _calendar_bound_repair_path(error, initial, {0})
    assert path == (0, 0, 0)
    assert _calendar_bound_repair_path(error, initial, {0, 1}) is None
    assert _calendar_bound_repair_path(
        ProtocolControlAgentWireValidationError(
            "PUBLICATION_GATE_REJECTED", "多种错误", candidate_indexes=[0],
            obligation_source_span_ids=["span:01"],
            error_class_codes=["TIME_CALENDAR_BOUND_UNSUPPORTED", "FUTURE_PROHIBITION_DECIDED_EARLY"],
        ), initial, {0}
    ) is None
    patch = {"time_constraint": {"anchor_type": "screening_date", "direction": "before"}}
    merged = _merge_calendar_bound_repair(json.dumps(patch), initial, path)
    changed = merged.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    assert changed.time_constraint.upper_bound_days is None
    prior = initial.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    assert changed.model_copy(update={"time_constraint": prior.time_constraint}) == prior
    assert protocol_control_calendar_bound_repair_response_format()["json_schema"]["name"] == "protocol_control_calendar_bound_repair_v1"

    class FocusedTransport(_FakeTransport):
        def continue_candidate(self, *, session_id: str, prompt: str):
            pytest.fail("数值修订不得重写整个候选")

        def continue_calendar_bound_repair(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            assert "不得借用同一段落中另一动作的时长" in prompt
            return ProtocolControlAgentResponse(session_id=session_id, text=json.dumps(patch))

    transport = FocusedTransport([
        ProtocolControlAgentResponse(session_id="calendar-session", text=initial.model_dump_json())
    ])
    calls = 0

    def reject_bound_once(output) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ProtocolControlAgentWireValidationError(
                "PUBLICATION_GATE_REJECTED", "数值缺少原文支持",
                structure_unit_ids=["su-01"],
                candidate_ids=[output.candidates[0].control_candidate_id],
                obligation_source_span_ids=["span:01"],
                error_class_codes=["TIME_CALENDAR_BOUND_UNSUPPORTED"],
            )

    result = ProtocolControlAgentRunner(max_schema_repairs=0).run(
        _batch(), transport, output_validator=reject_bound_once
    )
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert len(result.attempts) == 2


def test_obligation_source_repair_preserves_sibling_atoms_and_candidate_fields() -> None:
    first = _candidate()
    first_atom = first.obligation_expression.groups[0].atoms[0]
    second_atom = first_atom.model_copy(
        update={
            "kind": ControlObligationKind.MUST_RECORD,
            "statement": "记录末次用药日期",
            "evaluation": first_atom.evaluation.__class__.model_validate(
                _evaluation("记录末次用药日期", "span:02", "筛选时记录末次用药日期")
            ),
            "source_span_ids": ["span:02"],
            "source_excerpts": ["筛选时记录末次用药日期"],
        }
    )
    initial_candidate = first.model_copy(
        update={
            "source_structure_unit_ids": ["su-01", "su-02"],
            "source_span_ids": ["span:01", "span:02"],
            "obligation_expression": first.obligation_expression.model_copy(
                update={
                    "groups": [
                        first.obligation_expression.groups[0].model_copy(
                            update={"atoms": [first_atom, second_atom]}
                        )
                    ]
                }
            ),
        }
    )
    initial = _wire(candidate=initial_candidate).model_dump(mode="json")
    initial["dispositions"][1].update(
        disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value,
        notes=None,
    )
    initial_wire = ProtocolControlAgentWire.model_validate(initial)

    repaired_first_atom = first_atom.model_copy(
        update={
            "kind": ControlObligationKind.MUST_RECORD,
            "statement": "按原文记录年龄",
        }
    )
    regressed_second_atom = second_atom.model_copy(
        update={"statement": "错误改写末次用药要求"}
    )
    repaired_candidate = initial_candidate.model_copy(
        update={
            "title": "未授权改写的候选标题",
            "obligation_expression": initial_candidate.obligation_expression.model_copy(
                update={
                    "groups": [
                        initial_candidate.obligation_expression.groups[0].model_copy(
                            update={
                                "atoms": [repaired_first_atom, regressed_second_atom]
                            }
                        )
                    ]
                }
            ),
        }
    )
    repaired = initial_wire.model_dump(mode="json")
    repaired["candidate_drafts"] = [repaired_candidate.model_dump(mode="json")]
    repaired_wire = ProtocolControlAgentWire.model_validate(repaired)
    transport = _FakeTransport(
        [
            ProtocolControlAgentResponse(
                session_id="session-1", text=initial_wire.model_dump_json()
            ),
            ProtocolControlAgentResponse(
                session_id="session-1", text=repaired_wire.model_dump_json()
            ),
        ]
    )
    calls = 0

    def validate_after_hydration(output) -> None:
        nonlocal calls
        calls += 1
        candidate = output.candidates[0]
        if calls == 1:
            raise ProtocolControlAgentWireValidationError(
                "RECORD_PRECISION_COMPRESSED",
                "只允许修订年龄义务原子",
                structure_unit_ids=["su-01"],
                candidate_ids=[candidate.control_candidate_id],
                obligation_source_span_ids=["span:01"],
            )
        atoms = candidate.semantics.obligation_expression.groups[0].atoms
        assert candidate.title == initial_candidate.title
        assert atoms[0].statement == "按原文记录年龄"
        assert atoms[1].statement == "记录末次用药日期"

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        _batch(),
        transport,
        output_validator=validate_after_hydration,
    )

    assert result.status == "已解析"
    assert calls == 2
    assert "span:01" in transport.prompts[1]
    assert result.attempts[-1].issues == [
        "已由系统原样保留定向修订范围外的上一轮内容"
    ]


def test_post_hydration_error_without_machine_readable_scope_stops_repair() -> None:
    valid = _wire(candidate=_candidate()).model_dump_json()
    transport = _FakeTransport(
        [ProtocolControlAgentResponse(session_id="session-1", text=valid)]
    )

    def reject_without_scope(_output) -> None:
        raise ProtocolControlAgentWireValidationError(
            "UNSCOPED_REJECTION",
            "没有可安全自动修订的机器可读范围",
        )

    result = ProtocolControlAgentRunner(max_schema_repairs=3).run(
        _batch(),
        transport,
        output_validator=reject_without_scope,
    )

    assert result.status == "需要核对"
    assert len(result.attempts) == 1
    assert "缺少完整的机器可读修订范围" in result.attempts[0].issues[-1]


def test_parse_output_can_return_unhydrated_domain_draft_for_gate_chain() -> None:
    draft = parse_protocol_control_agent_output(
        _wire(candidate=_candidate()).model_dump_json(),
        _batch(),
        hydrate=False,
    )
    assert draft.batch_id == "pcb-generic-01"
    assert draft.candidate_drafts[0].source_structure_unit_ids == ["su-01"]


def test_hydration_derives_trigger_branch_scope_for_conditional_shortening() -> None:
    from app.domain.contracts.rules import TimeConstraint

    candidate = ProtocolControlAgentWireCandidate(
        title="既往用药洗脱控制",
        repeat_trigger_conditions=[],
        applicable_population="拟入组受试者",
        applicability_expression=None,
        trigger_expression=ProtocolControlAgentWireConditionDnf(
            groups=[
                ProtocolControlAgentWireConditionGroup(
                    atoms=[_condition("目标药物暴露", "span:01", "年龄至少18岁")]
                ),
                ProtocolControlAgentWireConditionGroup(
                    atoms=[_condition("其他药物暴露", "span:01", "年龄至少18岁")]
                ),
            ]
        ),
        obligation_expression=ProtocolControlAgentWireObligationDnf(
            groups=[
                ProtocolControlAgentWireObligationGroup(
                    atoms=[
                        ProtocolControlAgentWireObligationAtom(
                            kind=ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE,
                            statement="首次给药前24个月不得暴露",
                            evaluation=_timed_evaluation("首次给药前24个月不得暴露", "span:01", "年龄至少18岁"),
                            time_constraint=TimeConstraint(
                                anchor_type="first_dose_date",
                                direction="before",
                                lower_bound={"value": 24, "unit": "month"},
                            ),
                            prospective_period=None,
                            source_span_ids=["span:01"],
                            source_excerpts=["年龄至少18岁"],
                            requires_professional_judgment=False,
                        )
                    ],
                    applies_to_trigger_branch_indexes=[0],
                ),
                ProtocolControlAgentWireObligationGroup(
                    atoms=[
                        ProtocolControlAgentWireObligationAtom(
                            kind=ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE,
                            statement="首次给药前6个月不得暴露",
                            evaluation=_timed_evaluation("首次给药前6个月不得暴露", "span:01", "年龄至少18岁"),
                            time_constraint=TimeConstraint(
                                anchor_type="first_dose_date",
                                direction="before",
                                lower_bound={"value": 6, "unit": "month"},
                            ),
                            prospective_period=None,
                            source_span_ids=["span:01"],
                            source_excerpts=["年龄至少18岁"],
                            requires_professional_judgment=False,
                        )
                    ],
                    applies_to_trigger_branch_indexes=[0],
                ),
            ]
        ),
        exception_expression=ProtocolControlAgentWireExceptionDnf(
            groups=[
                ProtocolControlAgentWireConditionGroup(
                    atoms=[
                        ProtocolControlAgentWireConditionAtom(
                            statement="经药物清除剂进行洗脱可缩短",
                            evaluation=_evaluation("经药物清除剂进行洗脱可缩短", "span:01", "年龄至少18岁"),
                            source_span_ids=["span:01"],
                            source_excerpts=["年龄至少18岁"],
                            time_constraint=None,
                            requires_professional_judgment=False,
                        )
                    ],
                    waives_trigger_branch_indexes=[0],
                    activates_obligation_group_indexes=[1],
                )
            ]
        ),
        review_node_bindings=[
            {
                "workflow_stage_id": "stage:screening:one",
                "review_stage": ReviewStage.SCREENING,
                "role": ReviewNodeRole.DECIDE_AT_NODE,
                "guidance": None,
            }
        ],
        minimum_evidence=[
            ProtocolControlAgentWireEvidence(
                fact_type="medication_exposure",
                description="核对用药资料",
                due_stage=ReviewStage.SCREENING,
                required_source_types=["原始资料"],
                workflow_stage_ids=["stage:screening:one"],
                source_policy=_evidence_policy("span:01", "年龄至少18岁"),
                atom_refs=[{"layer": "obligation", "group_index": 0, "atom_index": 0}],
            )
        ],
        source_structure_unit_ids=["su-01"],
        source_span_ids=["span:01"],
        cross_source_relations=[],
    )
    hydrated = hydrate_protocol_control_agent_output(
        _wire(candidate=candidate),
        _batch(),
    )
    semantics = hydrated.candidates[0].semantics
    assert semantics is not None
    assert semantics.trigger_expression is not None
    branch_ids = [
        group.trigger_branch_id for group in semantics.trigger_expression.groups
    ]
    assert all(branch_id and branch_id.startswith("pct-") for branch_id in branch_ids)
    default_group, alt_group = semantics.obligation_expression.groups
    assert default_group.applies_to_trigger_branch_ids == [branch_ids[0]]
    assert default_group.activated_by_exception_group_ids == []
    assert alt_group.applies_to_trigger_branch_ids == [branch_ids[0]]
    assert alt_group.obligation_group_id and alt_group.obligation_group_id.startswith(
        "pog-"
    )
    exception_group = semantics.exception_expression.groups[0]
    assert exception_group.waives_trigger_branch_ids == [branch_ids[0]]
    assert exception_group.activates_obligation_group_ids == [
        alt_group.obligation_group_id
    ]
    assert alt_group.activated_by_exception_group_ids == [
        exception_group.exception_group_id
    ]
    assert exception_group.atoms[0].time_constraint is None
    assert alt_group.atoms[0].time_constraint.lower_bound.value == 6

    timed_condition = candidate.model_dump(mode="json")
    timed_atom = timed_condition["exception_expression"]["groups"][0]["atoms"][0]
    timed_atom["evaluation"] = _timed_evaluation(timed_atom["statement"], "span:01", "年龄至少18岁")
    timed_condition["exception_expression"]["groups"][0]["atoms"][0][
        "time_constraint"
    ] = {
        "anchor_type": "first_dose_date",
        "direction": "before",
        "lower_bound": {"value": 6, "unit": "month"},
        "upper_bound": None,
        "lower_bound_days": None,
        "upper_bound_days": None,
        "half_life_multiplier": None,
        "combined_window_selection": None,
        "allow_partial_date": False,
    }
    with pytest.raises(
        (ProtocolControlAgentWireValidationError, ValidationError, ValueError),
        match="时间窗",
    ):
        hydrate_protocol_control_agent_output(
            json.dumps(
                {
                    **_wire(candidate=candidate).model_dump(mode="json"),
                    "candidate_drafts": [timed_condition],
                },
                ensure_ascii=False,
            ),
            _batch(),
        )


def _stage_bound_example():
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].excerpt = "筛选期（D-7~D-1）：拟参加者须完成知情同意记录。"
    batch.known_workflow_stage_targets[0].display_name = "筛选期 / V1 / D-7~D-1"
    batch.known_workflow_stage_targets[0].visit_instance = "筛选期 / V1 / D-7~D-1"
    inventory = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-01",
            "quoted_text": "拟参加者须完成知情同意记录",
            "scope_quote": "筛选期（D-7~D-1）",
            "force": "required",
            "time_words": ["筛选期（D-7~D-1）"],
        }],
        "units_without_statement": ["su-02"],
    })
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{
            "statement_index": 0,
            "decision": "additional_requirement",
            "target_id": None,
            "source_action_excerpt": "拟参加者须完成知情同意记录",
            "target_action_excerpt": None,
            "source_time_excerpt": None,
            "target_time_excerpt": None,
            "unresolved_aspects": ["现有条款未覆盖访视范围"],
        }],
    })
    selection = StageBoundRequirement.model_validate({
        "version": STAGE_BOUND_REQUIREMENT_VERSION,
        "statement_index": 0,
        "action_excerpt": "拟参加者须完成知情同意记录",
        "stage_scope_excerpt": "筛选期（D-7~D-1）",
        "workflow_stage_id": "stage:screening:one",
        "title": "知情同意记录",
        "applicable_population": "拟参加者",
        "obligation_statement": "拟参加者须完成知情同意记录",
        "kind": "complete_or_verify",
        "determination_mode": "semantic",
        "observation_scope": "筛选期拟参加者的知情同意记录",
        "fact_type": "informed_consent",
        "evidence_description": "知情同意记录",
        "required_source_types": ["知情同意记录"],
        "unresolved_aspects": [],
    })
    return batch, inventory, review.items[0], selection


def test_stage_bound_requirement_compiles_only_frozen_visit_scope() -> None:
    batch, inventory, review, selection = _stage_bound_example()
    prompt = build_stage_bound_requirement_prompt(batch, inventory, review)
    assert "拟参加者须完成知情同意记录" in prompt
    candidate = compile_stage_bound_requirement(batch, inventory, review, selection)
    atom = candidate.obligation_expression.groups[0].atoms[0]
    assert atom.time_constraint is None
    assert atom.evaluation.observation_policy.mode == "unresolved"
    assert atom.source_excerpts == ["筛选期（D-7~D-1）", selection.action_excerpt]
    assert candidate.review_node_bindings[0].workflow_stage_id == "stage:screening:one"
    assert candidate.minimum_evidence[0].source_policy.requires_contemporaneous_objective_source is None

    changed = selection.model_copy(update={"workflow_stage_id": "stage:screening:two"})
    with pytest.raises(StageBoundCompilationGap, match="冻结访视"):
        compile_stage_bound_requirement(batch, inventory, review, changed)
    shortened = selection.model_copy(update={"action_excerpt": "完成知情同意记录"})
    with pytest.raises(StageBoundCompilationGap, match="不得省略"):
        compile_stage_bound_requirement(batch, inventory, review, shortened)


def test_stage_bound_requirement_rejects_relative_time_and_unknown_semantics() -> None:
    batch, inventory, review, selection = _stage_bound_example()
    inventory.statements[0].time_words = ["完成导入治疗后"]
    with pytest.raises(StageBoundCompilationGap, match="时间要求"):
        compile_stage_bound_requirement(batch, inventory, review, selection)
    inventory.statements[0].time_words = ["筛选期（D-7~D-1）"]
    with pytest.raises(StageBoundCompilationGap, match="条件、例外"):
        compile_stage_bound_requirement(
            batch, inventory, review,
            selection.model_copy(update={"unresolved_aspects": ["有待确认的例外"]}),
        )


def test_stage_bound_insert_uses_product_reader_and_keeps_original_candidate() -> None:
    batch, inventory, review, selection = _stage_bound_example()
    batch.owned_units[0].excerpt = "年龄至少18岁；" + batch.owned_units[0].excerpt
    original = _wire(candidate=_candidate()).model_dump_json()

    class StageReaderTransport(_FakeTransport):
        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="target-1", text=SourceTargetReview(
                version=SOURCE_TARGET_REVIEW_VERSION, items=[review]
            ).model_dump_json())

        def read_stage_bound_requirement(self, *, prompt: str) -> ProtocolControlAgentResponse:
            assert "reason_for_insertion" in prompt
            return ProtocolControlAgentResponse(session_id="stage-1", text=selection.model_dump_json())

    validated = []
    result = ProtocolControlAgentRunner().run(
        batch,
        StageReaderTransport([ProtocolControlAgentResponse(session_id="wire-1", text=original)]),
        output_validator=lambda output: validated.append(output),
    )
    assert result.status == "已解析"
    assert result.final_output is not None
    assert len(result.final_output.candidates) == 2
    assert len(validated) == 2
    assert result.source_target_review is not None
    assert result.source_target_review.items == []
    assert any(item.session_id == "stage-1" for item in result.attempts)


def test_relative_stage_requirement_preserves_after_stage_without_new_calendar_window() -> None:
    batch, inventory, review, selection = _stage_bound_example()
    batch.owned_units[0].excerpt = (
        "筛选/导入期（D-7~D-1）：完成导入治疗后再次核查资格。"
    )
    batch.known_workflow_stage_targets[0].review_stage = ReviewStage.RUN_IN
    batch.known_workflow_stage_targets[0].display_name = "筛选/导入期 / V1 / D-7~D-1"
    batch.known_workflow_stage_targets[0].visit_instance = "筛选/导入期 / V1 / D-7~D-1"
    batch.known_workflow_stage_targets[1].review_stage = ReviewStage.BASELINE
    batch.known_workflow_stage_targets[1].display_name = "基线期 / V2 / D1"
    batch.known_workflow_stage_targets[1].visit_instance = "基线期 / V2 / D1"
    batch.known_procedure_targets[0].review_stage = ReviewStage.BASELINE
    batch.known_procedure_targets[0].visit_instance = "基线期 / V2 / D1"
    batch.known_procedure_targets[0].source_excerpts = ["再次核查资格"]
    inventory.statements[0].quoted_text = "完成导入治疗后再次核查资格"
    inventory.statements[0].scope_quote = "筛选/导入期（D-7~D-1）"
    inventory.statements[0].time_words = ["完成导入治疗后"]
    review.source_action_excerpt = "完成导入治疗后再次核查资格"
    review.source_time_excerpt = "完成导入治疗后"
    review.target_id = "procedure-screening-1"
    review.target_action_excerpt = "再次核查资格"
    relative = RelativeStageRequirement.model_validate({
        **selection.model_dump(exclude={"version"}),
        "version": RELATIVE_STAGE_REQUIREMENT_VERSION,
        "action_excerpt": review.source_action_excerpt,
        "stage_scope_excerpt": "筛选/导入期（D-7~D-1）",
        "workflow_stage_id": "stage:screening:two",
        "prior_workflow_stage_id": "stage:screening:one",
        "target_procedure_id": review.target_id,
        "relative_time_excerpt": review.source_time_excerpt,
        "obligation_statement": "完成导入治疗后再次核查资格",
    })
    assert can_compile_relative_stage_requirement(batch, inventory, review)
    assert "complete_or_verify 加 semantic" in build_relative_stage_requirement_prompt(
        batch, inventory, review
    )
    candidate = compile_stage_bound_requirement(batch, inventory, review, relative)
    atom = candidate.obligation_expression.groups[0].atoms[0]
    assert atom.time_constraint is None
    assert candidate.review_node_bindings[0].review_stage == ReviewStage.BASELINE
    assert candidate.cross_source_relations[0].affected_workflow_stage_id == "stage:screening:two"

    wrong_order = relative.model_copy(update={"workflow_stage_id": "stage:screening:one"})
    with pytest.raises(StageBoundCompilationGap, match="先后"):
        compile_stage_bound_requirement(batch, inventory, review, wrong_order)


def test_two_sourced_actions_insert_together_without_rewriting_existing_draft() -> None:
    batch, inventory, first_review, first = _stage_bound_example()
    batch.owned_units[0].excerpt = (
        "年龄至少18岁；筛选期（D-7~D-1）：拟参加者须完成知情同意记录。"
        "导入治疗结束后再次核查资格。"
    )
    batch.known_workflow_stage_targets[0].review_stage = ReviewStage.RUN_IN
    batch.known_workflow_stage_targets[1].review_stage = ReviewStage.BASELINE
    batch.known_workflow_stage_targets[1].display_name = "基线期 / V2 / D1"
    batch.known_workflow_stage_targets[1].visit_instance = "基线期 / V2 / D1"
    batch.known_procedure_targets[0].review_stage = ReviewStage.BASELINE
    batch.known_procedure_targets[0].visit_instance = "基线期 / V2 / D1"
    batch.known_procedure_targets[0].source_excerpts = ["再次核查资格"]
    inventory.statements.append(inventory.statements[0].model_copy(update={
        "quoted_text": "导入治疗结束后再次核查资格。",
        "time_words": ["导入治疗结束后"],
    }))
    second_review = first_review.model_copy(update={
        "statement_index": 1,
        "source_action_excerpt": "导入治疗结束后再次核查资格",
        "source_time_excerpt": "导入治疗结束后",
        "target_id": "procedure-screening-1",
        "target_action_excerpt": "再次核查资格",
    })
    relative = RelativeStageRequirement.model_validate({
        **first.model_dump(exclude={"version"}),
        "version": RELATIVE_STAGE_REQUIREMENT_VERSION,
        "statement_index": 1,
        "action_excerpt": second_review.source_action_excerpt,
        "workflow_stage_id": "stage:screening:two",
        "prior_workflow_stage_id": "stage:screening:one",
        "target_procedure_id": second_review.target_id,
        "relative_time_excerpt": second_review.source_time_excerpt,
        "obligation_statement": "导入治疗结束后再次核查资格",
    })
    target_review = SourceTargetReview(
        version=SOURCE_TARGET_REVIEW_VERSION, items=[first_review, second_review]
    )
    original = _wire(candidate=_candidate()).model_dump(mode="json")
    original["candidate_drafts"][0]["review_node_bindings"][0]["review_stage"] = "run_in"
    original["candidate_drafts"][0]["minimum_evidence"][0]["due_stage"] = "run_in"

    class TwoActionTransport(_FakeTransport):
        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="target-1", text=target_review.model_dump_json())

        def read_stage_bound_requirement(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="stage-1", text=first.model_dump_json())

        def read_relative_stage_requirement(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="relative-1", text=relative.model_dump_json())

    result = ProtocolControlAgentRunner().run(
        batch,
        TwoActionTransport([ProtocolControlAgentResponse(
            session_id="wire-1", text=json.dumps(original, ensure_ascii=False)
        )]),
        output_validator=lambda _output: None,
    )
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert result.final_output is not None
    assert len(result.final_output.candidates) == 3
    assert result.source_target_review is not None and result.source_target_review.items == []
    assert {item.session_id for item in result.attempts} >= {"stage-1", "relative-1"}
