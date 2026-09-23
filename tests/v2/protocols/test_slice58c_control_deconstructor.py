"""Generic tests for the Phase 5.8c other-control Agent adapter.

These fixtures are synthetic.  They do not call a model, read a real protocol,
or write a project artifact.
"""

from __future__ import annotations

import json
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
    _merge_candidate_repairs,
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
    validate_protocol_control_agent_wire,
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
    ):
        hydrate_protocol_control_agent_output(_wire(candidate=candidate), batch)

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
