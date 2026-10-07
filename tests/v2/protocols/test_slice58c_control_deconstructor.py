"""Generic tests for the Phase 5.8c other-control Agent adapter.

These fixtures are synthetic.  They do not call a model, read a real protocol,
or write a project artifact.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.agents.protocol_control_deconstructor import (
    CONTROL_AGENT_WIRE_VERSION,
    protocol_control_batch_response_format,
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
    _treatment_duration_atom_repair_path,
    _merge_calendar_bound_repair,
    _merge_candidate_repairs,
    _merge_obligation_atom_repair,
    _build_obligation_atom_repair_prompt,
    _merge_observation_policy_repair,
    _invalid_time_operand_paths,
    _merge_time_operand_repair,
    _build_time_operand_repair_prompt,
    _invalid_observation_policy_paths,
    _invalid_obligation_atom_path,
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
    SOURCE_UNIT_COMPARISON_VERSION,
    SourceInterpretation,
    SourceInterpretationValidationError,
    SourceQuoteCorrection,
    SourceScopeCorrection,
    SourceStatement,
    SourceStatementCoverage,
    SourceTargetReview,
    SourceTargetReviewItem,
    SourceUnitComparison,
    SourceTargetReviewValidationError,
    build_source_interpretation_prompt,
    parse_product_source_interpretation,
    source_interpretation_response_format,
    build_source_quote_correction_prompt,
    build_source_scope_correction_prompt,
    apply_source_scope_correction,
    apply_source_quote_correction,
    build_source_target_review_prompt,
    source_target_review_response_format,
    build_source_unit_comparison_prompt,
    target_review_indexes,
    schedule_column_links,
    normalize_schedule_randomization_anchors,
    normalize_mixed_schedule_scopes,
    validate_source_interpretation,
    validate_source_target_review,
    _exception_in_target,
    _unreported_time_fragments,
    is_study_phase_label,
)
from app.agents.protocol_control_source_function import (
    apply_source_function_recheck,
    build_source_function_recheck_prompt,
    can_recheck_source_function,
)
from app.agents.protocol_control_stage_compiler import (
    RELATIVE_STAGE_REQUIREMENT_VERSION,
    SHARED_PROHIBITION_REQUIREMENT_VERSION,
    STAGE_BOUND_REQUIREMENT_VERSION,
    RelativeStageRequirement,
    SharedProhibitionRequirement,
    assemble_source_requirement_inserts,
    StageBoundCompilationGap,
    StageBoundRequirement,
    can_compile_relative_stage_requirement,
    can_compile_shared_prohibition_requirement,
    can_compile_stage_bound_requirement,
    build_relative_stage_requirement_prompt,
    build_shared_prohibition_requirement_prompt,
    build_stage_bound_requirement_prompt,
    compile_stage_bound_requirement,
    compile_shared_prohibition_requirement,
    requires_temporal_resolution,
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


def _source_inventory(payload: dict) -> SourceInterpretation:
    # Legacy synthetic fixtures predate the required product-reader function field.
    material = deepcopy(payload)
    for statement in material.get("statements", []):
        statement.setdefault("decision_functions", ["action"])
    return SourceInterpretation.model_validate(material)


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
                required_source_types=[],  # This source imposes no record-type restriction.
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


def test_extra_readonly_disposition_is_excluded_without_losing_owned_units() -> None:
    batch = _batch()
    wire = _wire()
    extra = wire.dispositions[0].model_copy(deep=True)
    extra.structure_unit_id = "su-03"
    wire.dispositions.append(extra)

    accepted = validate_protocol_control_agent_wire(wire, batch)
    assert [item.structure_unit_id for item in accepted.dispositions] == ["su-01", "su-02"]
    assert len(wire.dispositions) == 3

    unknown = wire.model_copy(deep=True)
    unknown.dispositions[-1].structure_unit_id = "su-unknown"
    with pytest.raises(ProtocolControlAgentWireValidationError, match="PARTIAL_BATCH"):
        validate_protocol_control_agent_wire(unknown, batch)

    missing = wire.model_copy(deep=True)
    missing.dispositions = [item for item in missing.dispositions
                            if item.structure_unit_id != "su-02"]
    with pytest.raises(ProtocolControlAgentWireValidationError, match="PARTIAL_BATCH"):
        validate_protocol_control_agent_wire(missing, batch)

    referenced = _wire(candidate=_candidate())
    referenced.dispositions.append(extra)
    referenced.candidate_drafts[0].source_structure_unit_ids = ["su-03"]
    with pytest.raises(ProtocolControlAgentWireValidationError, match="PARTIAL_BATCH"):
        validate_protocol_control_agent_wire(referenced, batch)


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


def test_absent_time_bound_flag_is_irrelevant_but_real_bound_openness_survives() -> None:
    from app.agents.protocol_control_deconstructor import _normalize_absent_time_bound_flags
    from app.domain.contracts.rules import TimeConstraint

    payload = {"candidate_drafts": [{"time_constraint": {
        "anchor_type": "screening_date", "direction": "before",
        "lower_bound_days": 6, "lower_bound_inclusive": False,
        "upper_bound_days": None, "upper_bound_inclusive": False,
    }}]}
    _normalize_absent_time_bound_flags(payload)
    constraint = payload["candidate_drafts"][0]["time_constraint"]
    assert constraint["lower_bound_inclusive"] is False
    assert constraint["upper_bound_inclusive"] is True
    assert TimeConstraint.model_validate(constraint).lower_bound_inclusive is False
    wire_payload = _wire(candidate=_candidate()).model_dump(mode="json")
    atom = wire_payload["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]
    atom["time_constraint"] = {
        "anchor_type": "screening_date", "direction": "before",
        "upper_bound_days": None, "upper_bound_inclusive": False,
    }
    atom["evaluation"]["time_operand_attribute"] = "date_range"
    atom["evaluation"]["time_purpose"] = "interval_condition"
    parsed = parse_protocol_control_agent_wire(json.dumps(wire_payload, ensure_ascii=False))
    assert parsed.candidate_drafts[0].obligation_expression.groups[0].atoms[0].time_constraint.upper_bound_inclusive


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
    assert '"execution_workflow_stage_id":"stage:screening:one"' in prompt

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
            "EARLY_DECISION_FOR_FUTURE_ANCHOR: 末节点提前判定",
            "不能把末节点标为 later_node_review",
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
    assert '"execution_workflow_stage_id": "stage:screening:one"' in prompt


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


def test_same_source_candidates_keep_original_positions_and_reject_duplicates():
    batch = _batch()
    first = _candidate()
    wire = _wire(candidate=first)
    second = first.model_copy(update={"title": "同源的另一项要求"})
    wire.candidate_drafts.append(second)
    hydrated = hydrate_protocol_control_agent_output(wire, batch)
    ids = _candidate_ids_from_wire(wire, batch)
    assert len(set(ids)) == 2
    assert set(ids) == {c.control_candidate_id for c in hydrated.candidates}
    repaired = first.model_copy(update={"title": first.title + "（第一项已核）"})

    class IdentityTransport(_FakeTransport):
        def continue_candidate(self, *, session_id, prompt):
            self.prompts.append(prompt)
            assert "候选草稿位置（仅用于诊断，不得原样输出）：[0]" in prompt
            return ProtocolControlAgentResponse(session_id=session_id, text=json.dumps({
                "candidate_draft": repaired.model_dump(mode="json"),
            }))

    calls = 0

    def validate(output):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise publication_repair_error(
                issues=[SimpleNamespace(code="FIRST_FIELD_INVALID", message="只核第一项", entity_id=ids[0])],
                candidate_by_id={c.control_candidate_id: c for c in output.candidates},
                control_to_candidate={}, default_structure_unit_ids=batch.owned_structure_unit_ids,
            )

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(batch, IdentityTransport([
        ProtocolControlAgentResponse(session_id="duplicate-identity", text=wire.model_dump_json()),
    ]), output_validator=validate)
    assert result.status == "已解析", [a.issues for a in result.attempts]
    assert result.partial_wire.candidate_drafts == [repaired, second]
    assert wire.candidate_drafts == [first, second]
    duplicate = _wire(candidate=first)
    duplicate.candidate_drafts.append(first.model_copy(deep=True))
    with pytest.raises(ProtocolControlAgentWireValidationError, match="DUPLICATE_CANDIDATE"):
        hydrate_protocol_control_agent_output(duplicate, batch)
    assert _candidate_ids_from_wire(duplicate, batch) == []


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
        time_constraint={"anchor_type": "screening_date", "direction": "on"},
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


def test_prompt_schema_keeps_validation_and_freezes_write_scope() -> None:
    prompt = build_protocol_control_agent_prompt(_batch())
    schema_text = prompt.split("输出结构：", 1)[1].split("\n\n本次冻结输入：", 1)[0]
    supplied = json.loads(schema_text)

    def without_titles(value):
        if isinstance(value, dict):
            return {key: without_titles(item) for key, item in value.items() if key != "title"}
        if isinstance(value, list):
            return [without_titles(item) for item in value]
        return value

    assert supplied == without_titles(
        protocol_control_batch_response_format(_batch())["json_schema"]["schema"]
    )
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


def test_runner_passes_frozen_batch_to_scope_capable_transport() -> None:
    batch = _batch()

    class ScopedTransport(_FakeTransport):
        def start_batch(self, *, prompt, batch):
            self.received_batch = batch
            return self.start(prompt=prompt)

    transport = ScopedTransport([
        ProtocolControlAgentResponse(session_id="scope-session", text=_wire().model_dump_json()),
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=0).run(batch, transport)
    assert transport.received_batch is batch
    assert result.final_output is not None


def test_verified_source_only_resume_skips_source_reader_but_rebuilds_wire() -> None:
    batch = _batch()
    inventory = SourceInterpretation(
        version=SOURCE_INTERPRETATION_VERSION,
        statements=[],
        units_without_statement=list(batch.owned_structure_unit_ids),
    )

    class Transport(_FakeTransport):
        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            pytest.fail("已核来源不得在同身份恢复时重读")

    transport = Transport([ProtocolControlAgentResponse(
        session_id="wire-new", text=_wire().model_dump_json(),
    )])
    result = ProtocolControlAgentRunner().run(
        batch, transport, output_validator=lambda _output: None,
        resume_source_interpretation=inventory,
    )
    assert result.status == "已解析"
    assert result.source_interpretation == inventory
    assert len(transport.prompts) == 1

    invalid = inventory.model_copy(update={"units_without_statement": []})
    with pytest.raises(ValueError, match="每个冻结来源单元"):
        ProtocolControlAgentRunner().run(
            batch, Transport([]), output_validator=lambda _output: None,
            resume_source_interpretation=invalid,
        )


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
    inventory = _source_inventory(payload)
    validate_source_interpretation(batch, inventory)
    assert '"time_words":[]' in build_source_interpretation_prompt(batch)
    assert f'"version":"{SOURCE_INTERPRETATION_VERSION}"' in build_source_interpretation_prompt(batch)
    assert "该先决短语须在 quoted_text 之前" in build_source_interpretation_prompt(batch)
    assert "另一动作的日期、阶段或持续时长均不能借给本条" in build_source_interpretation_prompt(batch)
    from app.agents.protocol_control_source_interpretation import source_interpretation_response_format
    assert source_interpretation_response_format()["json_schema"]["name"].endswith(
        SOURCE_INTERPRETATION_VERSION.rsplit("/", 1)[-1]
    )
    prompt_input = json.loads(build_source_interpretation_prompt(batch).split("冻结来源：", 1)[1])
    assert [item["structure_unit_id"] for item in prompt_input["owned"]] == ["su-01", "su-02"]
    payload["statements"][1]["quoted_text"] = "筛选前六个月内停止治疗"
    with pytest.raises(ValueError, match="不属于冻结来源"):
        validate_source_interpretation(batch, _source_inventory(payload))
    payload["statements"][1]["quoted_text"] = "筛选时记录末次用药日期"
    payload["statements"][1]["time_words"] = ["筛选时", "治疗后六周"]
    with pytest.raises(SourceInterpretationValidationError, match="时间措辞不属于本条陈述") as error:
        validate_source_interpretation(batch, _source_inventory(payload))
    assert error.value.code == "SOURCE_TIME_UNGROUNDED"
    assert error.value.statement_id == 1
    assert error.value.structure_unit_id == "su-02"
    assert error.value.json_path == "statements[1].time_words"
    assert error.value.retry_class == "correct_source_scope"
    assert error.value.source_refs
    payload["statements"][1]["time_words"] = ["筛选时", "末次用药日期"]
    validate_source_interpretation(batch, _source_inventory(payload))
    payload["statements"][1]["quoted_text"] = "末次用药日期"
    payload["statements"][1]["time_words"] = ["筛选时"]
    with pytest.raises(ValueError, match="时间措辞不属于本条陈述"):
        validate_source_interpretation(batch, _source_inventory(payload))


@pytest.mark.parametrize("fragment", [
    "90分钟", "两小时", "半小时", "0.5小时", "９０ 分钟", "1.5 h", "two hours",
])
def test_intraday_source_time_cannot_disappear_from_inventory(fragment: str) -> None:
    batch = _batch().model_copy(deep=True)
    quote = f"在给药前{fragment}内采集样本"
    batch.owned_units[0].excerpt = quote
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": quote,
                        "force": "required", "time_words": ["给药前"]}],
        "units_without_statement": ["su-02"],
    })
    with pytest.raises(SourceInterpretationValidationError) as caught:
        validate_source_interpretation(batch, inventory)
    assert caught.value.code == "SOURCE_TIME_INCOMPLETE"
    assert caught.value.source_refs == ["span:01"]
    assert caught.value.statement_id == 0
    inventory.statements[0].time_words = [quote]
    validate_source_interpretation(batch, inventory)
    assert not _unreported_time_fragments(inventory.statements[0])


def test_intraday_scope_does_not_borrow_time_from_sibling_or_background_title() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].excerpt = "基线期给药前半小时：采集样本；两小时后复查。"
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": "采集样本",
                        "scope_quote": "基线期给药前半小时", "force": "required",
                        "time_words": ["基线期"]}],
        "units_without_statement": ["su-02"],
    })
    with pytest.raises(SourceInterpretationValidationError, match="半小时"):
        validate_source_interpretation(batch, inventory)
    inventory.statements[0].time_words = ["基线期给药前半小时"]
    validate_source_interpretation(batch, inventory)
    assert "两小时" not in " ".join(inventory.statements[0].time_words)
    batch.owned_units[0].excerpt = "参见《十分钟检测说明》了解背景。"
    inventory.statements[0] = SourceStatement(
        structure_unit_id="su-01", quoted_text=batch.owned_units[0].excerpt,
        force="descriptive", decision_functions=["background"], time_words=[],
    )
    validate_source_interpretation(batch, inventory)


@pytest.mark.parametrize("error_code", [
    "TIME_PRECISION_UNSUPPORTED", "NUMERIC_VALUE_NOT_IN_SOURCE", "COMPARATOR_CHANGED",
    "NUMERIC_UNIT_NOT_IN_SOURCE", "SOURCE_NUMERIC_SEMANTICS_UNVERIFIED",
])
def test_source_bound_failure_does_not_request_unscoped_candidate_repair(error_code: str) -> None:
    transport = _FakeTransport([ProtocolControlAgentResponse(
        session_id="clock-capability", text=_wire(candidate=_candidate()).model_dump_json(),
    )])

    def unavailable(output):
        raise ProtocolControlAgentWireValidationError(
            "PUBLICATION_GATE_REJECTED", "小时精度未支持，不能改为当天",
            error_class_codes=[error_code],
            structure_unit_ids=["su-01"],
            candidate_ids=[output.candidates[0].control_candidate_id],
        )

    result = ProtocolControlAgentRunner(max_schema_repairs=2).run(
        _batch(), transport, output_validator=unavailable,
    )
    assert result.status == "需要核对"
    assert result.final_output is None
    assert len(transport.prompts) == 1
    assert set(result.attempts[-1].error_classes) == {
        "PUBLICATION_GATE_REJECTED", error_code,
    }


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
    validate_source_interpretation(batch, _source_inventory(payload))
    payload["statements"][0]["quoted_text"] = "筛选期（D-7~D-1）：记录末次用药日期"
    validate_source_interpretation(batch, _source_inventory(payload))
    payload["statements"][0]["quoted_text"] = "记录末次用药日期"
    payload["statements"][0]["scope_quote"] = "治疗后七天"
    with pytest.raises(ValueError, match="共享范围须来自陈述之前"):
        validate_source_interpretation(batch, _source_inventory(payload))
    payload["statements"][0]["scope_quote"] = "筛选期（D-7~D-1）"
    payload["statements"][0]["time_words"] = []
    with pytest.raises(ValueError, match="明确阶段范围不得从时间措辞中遗漏"):
        validate_source_interpretation(batch, _source_inventory(payload))
    payload["statements"][0]["affected_stage"] = None
    payload["statements"][0]["quoted_text"] = "治疗后七天核对其他资料"
    payload["statements"][0]["time_words"] = ["治疗后七天"]
    validate_source_interpretation(batch, _source_inventory(payload))


def test_previous_action_time_is_not_a_shared_scope_across_clause_boundary() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[1].excerpt = "筛选时记录末次用药日期；治疗后七天核对其他资料。"
    payload = {
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-02", "quoted_text": "治疗后七天核对其他资料",
            "scope_quote": "筛选时", "force": "required", "time_words": ["治疗后七天"],
        }],
        "units_without_statement": ["su-01"],
    }
    with pytest.raises(SourceInterpretationValidationError) as error:
        validate_source_interpretation(batch, _source_inventory(payload))
    assert error.value.code == "SOURCE_SCOPE_UNGROUNDED"

    batch.owned_units[1].excerpt = "筛选期：记录末次用药日期；核对其他资料。"
    payload["statements"][0].update(
        quoted_text="核对其他资料", scope_quote="筛选期", time_words=["筛选期"],
    )
    validate_source_interpretation(batch, _source_inventory(payload))

    batch.owned_units[1].excerpt = "筛选期记录末次用药日期。治疗后核对其他资料。"
    payload["statements"][0].update(
        quoted_text="治疗后核对其他资料", scope_quote="筛选期", time_words=["治疗后"],
    )
    with pytest.raises(SourceInterpretationValidationError) as error:
        validate_source_interpretation(batch, _source_inventory(payload))
    assert error.value.code == "SOURCE_SCOPE_UNGROUNDED"


def test_leading_colon_scope_covers_later_sentence_but_not_next_scope() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[1].excerpt = (
        "筛选期：记录既往用药。受试者接受规定的背景治疗；随后核对资格。"
    )
    payload = {
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-02", "quoted_text": "受试者接受规定的背景治疗",
            "scope_quote": "筛选期：", "force": "required", "affected_stage": "筛选期",
            "time_words": ["筛选期"],
        }],
        "units_without_statement": ["su-01"],
    }
    validate_source_interpretation(batch, _source_inventory(payload))

    batch.owned_units[1].excerpt = (
        "筛选期：记录既往用药。基线期：受试者接受规定的背景治疗。"
    )
    with pytest.raises(SourceInterpretationValidationError) as error:
        validate_source_interpretation(batch, _source_inventory(payload))
    assert error.value.code == "SOURCE_SCOPE_UNGROUNDED"


def test_leading_visit_scope_covers_parallel_clauses_without_new_time() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[1].excerpt = "基线时完成甲检查；乙检查，丙检查；"
    payload = {
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-02", "quoted_text": "乙检查",
            "scope_quote": "基线时", "force": "required",
            "affected_stage": "基线时", "time_words": ["基线时"],
        }],
        "units_without_statement": ["su-01"],
    }
    validate_source_interpretation(batch, _source_inventory(payload))
    batch.owned_units[1].excerpt = "基线时完成甲检查；治疗后乙检查。"
    payload["statements"][0]["quoted_text"] = "治疗后乙检查"
    with pytest.raises(SourceInterpretationValidationError) as error:
        validate_source_interpretation(batch, _source_inventory(payload))
    assert error.value.code == "SOURCE_SCOPE_UNGROUNDED"


def test_age_in_weeks_is_not_a_treatment_duration() -> None:
    age = SourceStatement(
        structure_unit_id="su-age", quoted_text="年龄18~75周岁（包括边界值）",
        force="required", time_words=[],
    )
    assert _unreported_time_fragments(age) == []
    treatment = SourceStatement(
        structure_unit_id="su-treatment", quoted_text="持续治疗75周后复查",
        force="required", time_words=[],
    )
    assert _unreported_time_fragments(treatment) == ["75周后"]
    cited = SourceStatement(
        structure_unit_id="su-cited",
        quoted_text="参照《诊断和治疗指南（2022年修订版）》且既往病史至少2年",
        force="required", time_words=[],
    )
    assert _unreported_time_fragments(cited) == ["2年"]


def test_nested_clinical_lookback_is_detected_for_target_review() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[1].excerpt = "筛选时核对鼻部疾病，包括1年内鼻术后状态。"
    payload = {
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-02", "quoted_text": batch.owned_units[1].excerpt,
            "force": "required", "time_words": ["筛选时"],
        }],
        "units_without_statement": ["su-01"],
    }
    interpretation = _source_inventory(payload)
    validate_source_interpretation(batch, interpretation)
    assert _unreported_time_fragments(interpretation.statements[0]) == ["1年内"]
    payload["statements"][0]["time_words"].append("1年内")
    validate_source_interpretation(batch, _source_inventory(payload))


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
    validate_source_interpretation(batch, _source_inventory(payload))
    payload["statements"][0]["scope_quote"] = "相邻行适用范围"
    with pytest.raises(ValueError, match="共享范围须来自"):
        validate_source_interpretation(batch, _source_inventory(payload))


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
    source = _source_inventory({
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
    assert result.attempts[-1].error_classes == ["SOURCE_TARGET_REVIEW_UNAVAILABLE"]
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
    valid = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": "年龄至少18岁",
                        "force": "required", "time_words": []}],
        "units_without_statement": ["su-02"],
    })
    invalid = valid.model_copy(deep=True)
    invalid.statements[0].scope_quote = "不存在的适用范围"

    class SourceTransport(_FakeTransport):
        def __init__(self) -> None:
            literal = _candidate().model_copy(deep=True)
            literal.obligation_expression.groups[0].atoms[0].statement = "年龄至少18岁"
            super().__init__([ProtocolControlAgentResponse(
                session_id="wire-session", text=_wire(candidate=literal).model_dump_json()
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
    assert result.attempts[0].error_detail["json_path"] == "statements[0].scope_quote"
    assert result.source_interpretation == valid


def test_source_scope_repair_targets_statement_not_shared_unit_label() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[1].excerpt = "筛选时记录末次用药日期；治疗后七天核对其他资料。"
    invalid = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
            {"structure_unit_id": "su-02", "quoted_text": "筛选时记录末次用药日期",
             "force": "descriptive", "time_words": ["筛选时"]},
            {"structure_unit_id": "su-02", "quoted_text": "治疗后七天核对其他资料",
             "scope_quote": "其他资料", "force": "descriptive", "time_words": ["治疗后七天"]},
        ],
        "units_without_statement": ["su-01"],
    })

    class SourceTransport(_FakeTransport):
        def __init__(self) -> None:
            super().__init__([ProtocolControlAgentResponse(
                session_id="wire-session", text=_wire().model_dump_json(),
            )])
            self.corrected = False

        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="source-session", text=invalid.model_dump_json())

        def correct_source_scope(self, *, prompt: str) -> ProtocolControlAgentResponse:
            assert "治疗后七天核对其他资料" in prompt
            self.corrected = True
            return ProtocolControlAgentResponse(session_id="scope-session", text=SourceScopeCorrection(
                version="phase5/control-source-scope-correction/v1", structure_unit_id="su-02",
                scope_quote=None, affected_stage=None, time_words=["治疗后七天"], unresolved=None,
            ).model_dump_json())

    transport = SourceTransport()
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert transport.corrected
    assert result.source_interpretation.statements[0] == invalid.statements[0]
    assert result.source_interpretation.statements[1].scope_quote is None
    assert result.attempts[0].error_detail["statement_id"] == 1


def test_two_invalid_scopes_in_one_unit_are_corrected_separately() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[1].excerpt = "筛选时记录末次用药日期；治疗后七天核对其他资料。"
    invalid = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
            {"structure_unit_id": "su-02", "quoted_text": "筛选时记录末次用药日期",
             "scope_quote": "其他资料", "force": "required", "time_words": ["筛选时"]},
            {"structure_unit_id": "su-02", "quoted_text": "治疗后七天核对其他资料",
             "scope_quote": "筛选时", "force": "required", "time_words": ["治疗后七天"]},
        ],
        "units_without_statement": ["su-01"],
    })

    class SourceTransport(_FakeTransport):
        source_calls = 0
        correction_calls = 0

        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.source_calls += 1
            return ProtocolControlAgentResponse(session_id="source", text=invalid.model_dump_json())

        def correct_source_scope(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.correction_calls += 1
            assert ("记录末次用药日期" if self.correction_calls == 1 else "核对其他资料") in prompt
            return ProtocolControlAgentResponse(session_id="scope", text=SourceScopeCorrection(
                version="phase5/control-source-scope-correction/v1",
                structure_unit_id="su-02", scope_quote=None, affected_stage=None,
                time_words=["筛选时"] if self.correction_calls == 1 else ["治疗后七天"],
                unresolved=None,
            ).model_dump_json())

    transport = SourceTransport([
        ProtocolControlAgentResponse(session_id="wire", text=_wire().model_dump_json())
    ])
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert transport.source_calls == 1
    assert transport.correction_calls == 2
    assert result.source_interpretation is not None
    assert all(item.scope_quote is None for item in result.source_interpretation.statements)
    assert result.attempts[0].raw_output_text == invalid.model_dump_json()


def test_source_correction_prompts_name_the_exact_wire_versions() -> None:
    statement = SourceStatement(
        structure_unit_id="su-02", quoted_text="筛选时记录末次用药日期",
        force="required", time_words=["筛选时"],
    )
    scope = build_source_scope_correction_prompt(_batch(), statement, "来源范围待核对")
    quote = build_source_quote_correction_prompt(_batch(), statement)
    assert '"phase5/control-source-scope-correction/v1"' in scope
    assert '"phase5/control-source-quote-correction/v1"' in quote
    assert "不得写成 1.0" in scope
    assert "不得写成 1.0" in quote
    assert "同单元另一条陈述的时点" in scope
    assert "相邻 context 单元" in scope


def test_source_list_introduction_and_time_repair_have_explicit_contracts() -> None:
    source_prompt = build_source_interpretation_prompt(_batch())
    assert "列表引言" in source_prompt
    assert "units_without_statement" in source_prompt
    assert "相邻段落或 context 单元" in source_prompt
    repair_prompt = _build_time_operand_repair_prompt(
        _wire(candidate=_candidate()).model_dump(mode="json"), 0, ((0, 0),),
    )
    assert '"group_index":0' in repair_prompt
    assert '"atom_index":0' in repair_prompt
    assert '"attribute":"date_range|record_time|unresolved"' in repair_prompt
    assert "不得返回 date_attribute" in repair_prompt


def test_source_inventory_corrects_one_nearby_quote_without_rewriting_batch() -> None:
    invalid = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": "年龄至少18周岁",
                        "force": "required", "time_words": []}],
        "units_without_statement": ["su-02"],
    })

    class SourceTransport(_FakeTransport):
        def __init__(self) -> None:
            literal = _candidate().model_copy(deep=True)
            literal.obligation_expression.groups[0].atoms[0].statement = "年龄至少18岁"
            super().__init__([ProtocolControlAgentResponse(
                session_id="wire-session", text=_wire(candidate=literal).model_dump_json()
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


def test_source_inventory_corrects_embedded_eligibility_basis_locally() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[1].excerpt = "经入排标准判定符合后，筛选时记录末次用药日期并核对既往用药剂量与停药时间"
    invalid = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-02",
            "quoted_text": batch.owned_units[1].excerpt,
            "force": "required",
            "time_words": ["筛选时"],
            "eligibility_sequence": "after_eligibility_decision",
            "eligibility_sequence_quote": "经入排标准判定符合后",
        }],
        "units_without_statement": ["su-01"],
    })

    class SourceTransport(_FakeTransport):
        def __init__(self) -> None:
            super().__init__([])
            self.source_calls = 0

        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.source_calls += 1
            return ProtocolControlAgentResponse(session_id="source-session", text=invalid.model_dump_json())

        def correct_source_quote(self, *, prompt: str) -> ProtocolControlAgentResponse:
            assert "先决语句之后的同一动作" in prompt
            return ProtocolControlAgentResponse(session_id="quote-session", text=SourceQuoteCorrection(
                version="phase5/control-source-quote-correction/v1",
                structure_unit_id="su-02", corrected_quote="筛选时记录末次用药日期并核对既往用药剂量与停药时间", unresolved=None,
            ).model_dump_json())

    transport = SourceTransport()
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert transport.source_calls == 1, [item.issues for item in result.attempts]
    assert result.source_interpretation.statements[0].quoted_text == "筛选时记录末次用药日期并核对既往用药剂量与停药时间"
    assert [item.outcome for item in result.attempts[:2]] == ["schema_invalid", "parsed"]


def test_source_inventory_rejects_quote_correction_that_changes_number() -> None:
    invalid = _source_inventory({
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


@pytest.mark.parametrize("second_failure", [None, "unresolved", "wrong_source", "transport"])
def test_source_inventory_repairs_distinct_quotes_and_preserves_siblings(second_failure) -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[1].excerpt = "筛选时记录末次用药日期并核对既往用药剂量与停药时间"
    original = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
            {"structure_unit_id": "su-01", "quoted_text": "年龄至少18岁",
             "force": "required", "time_words": []},
            {"structure_unit_id": "su-02", "quoted_text": "筛选时记录末次用药时期",
             "force": "required", "time_words": ["筛选时"]},
            {"structure_unit_id": "su-02", "quoted_text": "核对既往用药剂量与停药时期",
             "force": "required", "time_words": []},
        ],
        "units_without_statement": [],
    })

    class SourceTransport(_FakeTransport):
        source_calls = 0
        correction_calls = 0

        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.source_calls += 1
            return ProtocolControlAgentResponse(session_id="source", text=original.model_dump_json())

        def correct_source_quote(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.correction_calls += 1
            second = self.correction_calls == 2
            assert ("停药时期" if second else "末次用药日") in prompt
            if second and second_failure == "transport":
                raise RuntimeError("provider disconnected")
            return ProtocolControlAgentResponse(session_id="quote", text=SourceQuoteCorrection(
                version="phase5/control-source-quote-correction/v1",
                structure_unit_id="su-01" if second and second_failure == "wrong_source" else "su-02",
                corrected_quote=(None if second and second_failure == "unresolved" else
                                 "核对既往用药剂量与停药时间" if second else "筛选时记录末次用药日期"),
                unresolved="无法核清" if second and second_failure == "unresolved" else None,
            ).model_dump_json())

    transport = SourceTransport([
        ProtocolControlAgentResponse(session_id="wire", text=_wire().model_dump_json())
    ])
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert transport.correction_calls == 2
    assert original.statements[1].quoted_text == "筛选时记录末次用药时期"
    assert result.attempts[1].outcome == "parsed"
    assert result.attempts[1].raw_output_text is not None
    if second_failure is None:
        assert transport.source_calls == 1
        inventory = result.source_interpretation
        assert inventory is not None
        assert inventory.statements[0] == original.statements[0]
        assert inventory.statements[1].quoted_text == "筛选时记录末次用药日期"
        assert inventory.statements[2].quoted_text == "核对既往用药剂量与停药时间"
        validate_source_interpretation(batch, inventory)
    else:
        assert result.status == "需要核对"
        assert result.source_interpretation is None
        assert transport.source_calls == (1 if second_failure == "transport" else 2)
        if second_failure == "transport":
            assert result.attempts[-1].error_classes == ["SOURCE_INTERPRETATION_CORRECTION_TRANSPORT_FAILED"]
            assert "筛选时记录末次用药日期" in result.attempts[1].raw_output_text
        assert result.attempts[2].outcome == (
            "transport_failed" if second_failure == "transport" else "schema_invalid"
        )


@pytest.mark.parametrize("old_quote,new_quote,time_words,exception", [
    ("筛选时不得记录末次用药日其", "筛选时可以记录末次用药日期", [], None),
    ("筛选后七天内记录末次用药日其", "筛选后记录末次用药日期", [], None),
    ("筛选时记录末次用药日其，必须核对既往用药", "筛选时记录末次用药日期", [], None),
    ("筛选后记录末次用药日其", "记录末次用药日期", ["筛选后"], None),
    ("筛选时记录末次用药日其，特殊情况另行处理", "筛选时记录末次用药日期", [], "特殊情况另行处理"),
    ("Record no medication change at baseline", "Record medication change at baseline", [], None),
    ("可以记录末次用药日其，不得调整剂量", "不得记录末次用药日期，可以调整剂量", [], None),
    ("三个周期内记录末次用药日其", "三个周内记录末次用药日期", [], None),
])
def test_source_quote_correction_rejects_semantic_marker_loss(
    old_quote, new_quote, time_words, exception,
) -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[1].excerpt = new_quote
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-02", "quoted_text": old_quote,
                        "force": "required", "time_words": time_words,
                        "exception_words": exception}],
        "units_without_statement": ["su-01"],
    })
    correction = SourceQuoteCorrection(
        version="phase5/control-source-quote-correction/v1",
        structure_unit_id="su-02", corrected_quote=new_quote, unresolved=None,
    )
    with pytest.raises(ValueError, match="不得改变否定、强度、数量"):
        apply_source_quote_correction(batch, inventory, 0, correction)
    assert inventory.statements[0].quoted_text == old_quote


def test_source_coverage_requires_direct_atom_quote_not_candidate_unit_only() -> None:
    batch = _batch()
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
            {"structure_unit_id": "su-01", "quoted_text": "年龄至少18岁", "force": "required", "time_words": []},
            {"structure_unit_id": "su-02", "quoted_text": "筛选时记录末次用药日期", "force": "required", "time_words": ["筛选时"]},
        ],
        "units_without_statement": [],
    })
    literal = _candidate().model_copy(deep=True)
    literal.obligation_expression.groups[0].atoms[0].statement = "年龄至少18岁"
    wire = _wire(candidate=literal)
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
    wrong_target = quoted_target.model_copy(update={
        "official_code": "EX-02", "source_excerpts": ["另一条不同的入排要求"],
    })
    wrong_batch = target_batch.model_copy(update={
        "known_official_targets": [quoted_target, wrong_target],
    })
    wrong_wire = _wire().model_copy(deep=True)
    wrong_wire.dispositions[0] = wrong_wire.dispositions[0].model_copy(update={
        "disposition": StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY,
        "linked_official_code": "EX-02", "notes": "误将相邻编号当作对应要求",
    })
    with pytest.raises(ProtocolControlAgentWireValidationError) as mismatch:
        source_statement_coverage(wrong_batch, inventory, wrong_wire)
    assert mismatch.value.code == "OFFICIAL_SOURCE_LINK_MISMATCH"
    wrong_wire.dispositions[0] = wrong_wire.dispositions[0].model_copy(update={
        "linked_official_code": "EX-01", "notes": "逐字对应的官方要求",
    })
    assert source_statement_coverage(wrong_batch, inventory, wrong_wire)[0].linked_official_code == "EX-01"

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


def test_source_coverage_accepts_literal_split_but_not_missing_connector() -> None:
    batch = _batch()
    sentence = "复查者应重新签署同意书，重新分配编号"
    batch.owned_units[0].excerpt = sentence
    candidate = _candidate()
    group = candidate.obligation_expression.groups[0]
    first = group.atoms[0].model_copy(update={
        "statement": "复查者应重新签署同意书",
        "source_excerpts": ["复查者应重新签署同意书"],
    })
    second = group.atoms[0].model_copy(update={
        "statement": "重新分配编号",
        "source_excerpts": ["重新分配编号"],
    })
    group.atoms = [first, second]
    wire = _wire(candidate=candidate)
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": sentence,
                        "force": "required", "time_words": []}],
        "units_without_statement": ["su-02"],
    })
    assert source_statement_coverage(batch, inventory, wire)[0].status == "expressed"

    inventory.statements[0].quoted_text = "复查者应重新签署同意书或重新分配编号"
    assert source_statement_coverage(batch, inventory, wire)[0].status == "candidate_linked"


@pytest.mark.parametrize("rewritten", [
    "年龄达到18岁", "年龄不得低于16岁", "年龄低于18岁", "基线后年龄至少18岁",
])
def test_single_source_citation_does_not_prove_rewritten_obligation(rewritten: str) -> None:
    batch = _batch()
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": "年龄至少18岁",
                        "force": "required", "time_words": []}],
        "units_without_statement": ["su-02"],
    })
    candidate = _candidate().model_copy(deep=True)
    candidate.obligation_expression.groups[0].atoms[0].statement = rewritten
    coverage = source_statement_coverage(batch, inventory, _wire(candidate=candidate))[0]
    assert coverage.status == "candidate_linked"
    assert "obligation" not in coverage.matched_roles
    candidate.obligation_expression.groups[0].atoms[0].statement = "年龄至少18岁"
    assert source_statement_coverage(batch, inventory, _wire(candidate=candidate))[0].status == "expressed"


def test_source_coverage_does_not_treat_whole_sentence_citation_as_whole_action() -> None:
    batch = _batch().model_copy(deep=True)
    source = "筛选期和研究结束访视均须核查同一记录"
    batch.owned_units[0].excerpt = source
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": source,
                        "force": "required", "time_words": ["筛选期", "研究结束访视"]}],
        "units_without_statement": ["su-02"],
    })
    candidate = _candidate().model_copy(deep=True)
    atom = candidate.obligation_expression.groups[0].atoms[0]
    atom.statement = "筛选期须核查同一记录"
    atom.source_excerpts = [source]
    partial = source_statement_coverage(batch, inventory, _wire(candidate=candidate))[0]
    assert partial.status == "candidate_linked"
    assert partial.action_candidate_indexes == []
    assert "obligation" not in partial.matched_roles

    atom.statement = source
    complete = source_statement_coverage(batch, inventory, _wire(candidate=candidate))[0]
    assert complete.status == "expressed"
    assert complete.action_candidate_indexes == [0]


def test_descriptive_decision_input_is_reviewed_even_when_same_unit_has_candidate() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].excerpt = "审核值取最近两次检查的平均值；筛选时记录结果。"
    inventory = SourceInterpretation(
        version=SOURCE_INTERPRETATION_VERSION,
        statements=[SourceStatement(
            structure_unit_id="su-01",
            quoted_text="审核值取最近两次检查的平均值",
            force="descriptive", decision_functions=["definition", "calculation_input"],
            time_words=[],
        )], units_without_statement=["su-02"],
    )
    validate_source_interpretation(batch, inventory)
    coverage = [SourceStatementCoverage(
        statement_index=0, structure_unit_id="su-01",
        disposition="other_control_candidate", status="candidate_linked",
        linked_candidate_indexes=[0],
    )]
    assert target_review_indexes(inventory, coverage, batch) == [0]
    with pytest.raises(SourceTargetReviewValidationError, match="逐项来源核对"):
        validate_source_target_review(batch, inventory, coverage,
                                      SourceTargetReview(version=SOURCE_TARGET_REVIEW_VERSION, items=[]))

    candidate = _candidate().model_copy(deep=True)
    candidate.applicability_expression.groups[0].atoms[0].source_excerpts = [batch.owned_units[0].excerpt]
    candidate.obligation_expression.groups[0].atoms[0].source_excerpts = [batch.owned_units[0].excerpt]
    production_coverage = source_statement_coverage(batch, inventory, _wire(candidate=candidate))
    assert production_coverage[0].status == "candidate_linked"
    assert target_review_indexes(inventory, production_coverage, batch) == [0]
    candidate.obligation_expression.groups[0].atoms[0].statement = inventory.statements[0].quoted_text
    production_coverage = source_statement_coverage(batch, inventory, _wire(candidate=candidate))
    assert production_coverage[0].status == "candidate_linked"
    assert target_review_indexes(inventory, production_coverage, batch) == [0]

    inventory.statements[0].decision_functions = ["definition"]
    definition_coverage = source_statement_coverage(batch, inventory, _wire(candidate=candidate))
    assert definition_coverage[0].status == "expressed"


def test_sibling_statements_need_distinct_obligation_evidence() -> None:
    batch = _batch().model_copy(deep=True)
    first, second = "筛选时记录甲项", "筛选时记录乙项"
    batch.owned_units[0].excerpt = f"{first}；{second}。"
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
            {"structure_unit_id": "su-01", "quoted_text": quote,
             "force": "required", "time_words": ["筛选时"]}
            for quote in (first, second)
        ],
        "units_without_statement": ["su-02"],
    })
    validate_source_interpretation(batch, inventory)
    candidate = _candidate().model_copy(deep=True)
    atom = candidate.obligation_expression.groups[0].atoms[0]
    atom.statement = batch.owned_units[0].excerpt
    atom.source_excerpts = [batch.owned_units[0].excerpt]
    shared = source_statement_coverage(batch, inventory, _wire(candidate=candidate))
    assert [entry.status for entry in shared] == ["candidate_linked", "candidate_linked"]
    assert target_review_indexes(inventory, shared, batch) == [0, 1]

    candidate.obligation_expression.groups[0].atoms = [
        atom.model_copy(update={"statement": quote, "source_excerpts": [quote]})
        for quote in (first, second)
    ]
    independent = source_statement_coverage(batch, inventory, _wire(candidate=candidate))
    assert [entry.status for entry in independent] == ["expressed", "expressed"]
    assert target_review_indexes(inventory, independent, batch) == []


def test_background_exit_requires_source_and_cannot_hide_candidate() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].excerpt = "预计样本量约二百人；筛选时记录结果。"
    inventory = SourceInterpretation(
        version=SOURCE_INTERPRETATION_VERSION,
        statements=[SourceStatement(
            structure_unit_id="su-01", quoted_text="预计样本量约二百人",
            force="descriptive", decision_functions=["background"], time_words=[],
        )], units_without_statement=["su-02"],
    )
    coverage = [SourceStatementCoverage(
        statement_index=0, structure_unit_id="su-01",
        disposition="supporting_or_supplement", status="candidate_linked",
    )]
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "background_context",
                   "source_action_excerpt": "预计样本量约二百人",
                   "non_control_basis_excerpt": "预计样本量约二百人"}],
    })
    validate_source_interpretation(batch, inventory)
    validate_source_target_review(batch, inventory, coverage, review)
    with pytest.raises(SourceTargetReviewValidationError, match="不能同时形成候选控制"):
        validate_source_target_review(batch, inventory,
                                      [coverage[0].model_copy(update={"candidate_indexes": [0]})], review)
    with pytest.raises(SourceTargetReviewValidationError, match="原文及功能分类"):
        validate_source_target_review(batch, inventory, [coverage[0].model_copy(update={
            "exact_official_excerpt_matches": ["EX-01"],
        })], review)
    with pytest.raises(SourceTargetReviewValidationError, match="原文及功能分类"):
        wrong = review.model_copy(deep=True)
        wrong.items[0].non_control_basis_excerpt = "未见条款"
        validate_source_target_review(batch, inventory, coverage, wrong)
    with pytest.raises(ValueError, match="不能与决策功能并列"):
        SourceStatement(structure_unit_id="su-01", quoted_text="预计样本量约二百人",
                        force="descriptive", decision_functions=["background", "threshold"], time_words=[])
    inventory.statements[0].force = "required"
    with pytest.raises(SourceTargetReviewValidationError, match="原文及功能分类"):
        validate_source_target_review(batch, inventory, coverage, review)


def _function_disagreement():
    batch = _batch().model_copy(deep=True)
    quote = "预计研究总时长分为资料准备和后续随访两个部分"
    batch.owned_units[1].excerpt = quote
    inventory = SourceInterpretation(
        version=SOURCE_INTERPRETATION_VERSION,
        statements=[SourceStatement(
            structure_unit_id="su-02", quoted_text=quote,
            force="descriptive", decision_functions=["definition", "time_validity"],
            time_words=[],
        )], units_without_statement=["su-01"],
    )
    entry = SourceStatementCoverage(
        statement_index=0, structure_unit_id="su-02",
        disposition="supporting_or_supplement", status="not_located",
    )
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "background_context",
                   "source_action_excerpt": quote, "non_control_basis_excerpt": quote}],
    })
    proposal = SourceInterpretation(
        version=SOURCE_INTERPRETATION_VERSION,
        statements=[inventory.statements[0].model_copy(update={"decision_functions": ["background"]})],
        units_without_statement=[],
    )
    return batch, inventory, entry, review, proposal


def test_source_function_recheck_preserves_original_and_all_siblings() -> None:
    batch, original, entry, review, proposal = _function_disagreement()
    original.statements.append(SourceStatement(
        structure_unit_id="su-01", quoted_text="年龄至少18岁", force="required",
        decision_functions=["action"], time_words=[],
    ))
    original.units_without_statement = []
    before = original.model_dump_json()
    with pytest.raises(SourceTargetReviewValidationError) as error:
        validate_source_target_review(batch, original, [entry], review)
    assert error.value.code == "BACKGROUND_CONTEXT_UNPROVEN"
    assert can_recheck_source_function(batch, original, entry, review.items[0])
    revised = apply_source_function_recheck(batch, original, entry, review.items[0], proposal)
    assert original.model_dump_json() == before
    assert revised.statements[1] == original.statements[1]
    validate_source_target_review(batch, revised, [entry], review)
    assert '"frozen_statement"' in build_source_function_recheck_prompt(batch, original, 0)


def test_source_function_recheck_can_reaffirm_without_approving_background() -> None:
    batch, original, entry, review, proposal = _function_disagreement()
    proposal.statements[0] = original.statements[0].model_copy(deep=True)
    before = original.model_dump_json()
    reaffirmed = apply_source_function_recheck(batch, original, entry, review.items[0], proposal)
    assert reaffirmed == original
    assert original.model_dump_json() == before
    with pytest.raises(SourceTargetReviewValidationError) as error:
        validate_source_target_review(batch, reaffirmed, [entry], review)
    assert error.value.code == "BACKGROUND_CONTEXT_UNPROVEN"


@pytest.mark.parametrize("outcome", [
    "background", "retained", "uncertain", "bad_quote", "transport",
    "review_unresolved", "bad_review", "review_transport",
])
def test_honest_unresolved_function_reaches_bounded_recheck(outcome: str) -> None:
    batch, original, entry, background, proposal = _function_disagreement()
    honest = SourceTargetReview(
        version=SOURCE_TARGET_REVIEW_VERSION,
        items=[SourceTargetReviewItem(
            statement_index=0, decision="unresolved",
            source_action_excerpt=original.statements[0].quoted_text,
            unresolved_aspects=["本条是设计说明还是审核所用定义尚未核清"],
        )],
    )
    assert can_recheck_source_function(batch, original, entry, honest.items[0])
    validate_source_target_review(batch, original, [entry], honest)
    if outcome == "retained":
        proposal.statements[0] = original.statements[0].model_copy(deep=True)
    elif outcome == "uncertain":
        proposal.statements[0].unresolved = ["用途仍有歧义"]
    elif outcome == "bad_quote":
        proposal.statements[0].quoted_text = "模型擅自修改的原文"

    class Transport(_FakeTransport):
        function_calls = 0
        target_calls = 0

        def start_source_interpretation(self, *, prompt: str):
            self.function_calls += 1
            assert '"frozen_statement"' in prompt
            if outcome == "transport":
                raise ProtocolControlAgentCallError("function-failed", "synthetic failure")
            return ProtocolControlAgentResponse(session_id="purpose-only", text=proposal.model_dump_json())

        def start_source_target_review(self, *, prompt: str):
            self.target_calls += 1
            if self.target_calls == 2:
                assert '"background_context_allowed":true' in prompt
                if outcome == "review_transport":
                    raise ProtocolControlAgentCallError("review-failed", "synthetic failure")
                if outcome == "bad_review":
                    return ProtocolControlAgentResponse(session_id="bad-review", text="{")
            return ProtocolControlAgentResponse(
                session_id=f"honest-review-{self.target_calls}",
                text=(honest if self.target_calls == 1 or outcome == "review_unresolved"
                      else background).model_dump_json(),
            )

        def start(self, *, prompt: str):
            pytest.fail("用途复核不能重新生成已有候选")

        def continue_session(self, **kwargs):
            pytest.fail("局部复核失败不能回退整包重读")

    transport = Transport([])
    wire = _wire(candidate=_candidate())
    original_json = original.model_dump_json()
    wire_json = wire.model_dump_json()
    result = ProtocolControlAgentRunner(max_transport_retries=3).run(
        batch, transport, resume_wire=wire, resume_source_interpretation=original,
        resume_session_id="saved-wire", output_validator=lambda value: None,
    )
    assert transport.function_calls == 1
    assert transport.target_calls == (2 if outcome in {
        "background", "review_unresolved", "bad_review", "review_transport",
    } else 1)
    assert original.model_dump_json() == original_json
    assert wire.model_dump_json() == wire_json
    assert result.partial_wire == wire
    if outcome == "background":
        assert result.final_output is not None
        assert result.source_target_review == background
        assert result.source_interpretation.statements[0].decision_functions == ["background"]
        assert any(attempt.session_id == "honest-review-2" and attempt.raw_output_text == background.model_dump_json()
                   for attempt in result.attempts)
    else:
        assert result.final_output is None
        if outcome in {"review_unresolved", "bad_review", "review_transport"}:
            assert result.source_interpretation.statements[0].decision_functions == ["background"]
        else:
            assert result.source_interpretation == original
        assert result.source_target_review == honest


@pytest.mark.parametrize("quote, time_words, stage, scope", [
    ("筛选期为1周（D-7~D-1）", ["1周", "D-7~D-1"], "筛选期", None),
    ("筛选期为一周", [], None, None),
    ("资料须在D-7~D-1取得", [], None, None),
    ("每12周一次", [], None, None),
    ("整个治疗期保持不变", [], None, None),
    ("在本节点记录检查结果", [], "筛选期", None),
    ("在本节点记录检查结果", [], None, "给药前"),
])
@pytest.mark.parametrize("decision", ["background_context", "unresolved"])
def test_source_function_recheck_never_backgrounds_unconsumed_time(quote, time_words, stage, scope, decision):
    batch, original, entry, review, proposal = _function_disagreement()
    batch.owned_units[1].excerpt = quote
    original.statements[0] = original.statements[0].model_copy(update={
        "quoted_text": quote, "time_words": time_words, "affected_stage": stage, "scope_quote": scope,
    })
    item = review.items[0].model_copy(update={
        "decision": decision, "source_action_excerpt": quote,
        "non_control_basis_excerpt": quote if decision == "background_context" else None,
        "unresolved_aspects": [] if decision == "background_context" else ["已有目标缺少时窗定义"],
    })
    proposal.statements[0] = original.statements[0].model_copy(update={"decision_functions": ["background"]})
    assert not can_recheck_source_function(batch, original, entry, item)
    with pytest.raises(ValueError):
        apply_source_function_recheck(batch, original, entry, item, proposal)
    assert original.statements[0].decision_functions == ["definition", "time_validity"]


@pytest.mark.parametrize("heading", ["筛选期为一周", "D-7~D-1", "整个治疗期"])
@pytest.mark.parametrize("decision", ["background_context", "unresolved"])
def test_source_function_recheck_keeps_heading_only_period(heading: str, decision: str):
    batch, original, entry, review, proposal = _function_disagreement()
    batch.owned_units[1].heading_path = ["研究流程", heading]
    before = original.model_dump_json()
    item = review.items[0].model_copy(update={
        "decision": decision,
        "non_control_basis_excerpt": (original.statements[0].quoted_text
                                      if decision == "background_context" else None),
        "unresolved_aspects": [] if decision == "background_context" else ["标题期间的用途尚未核清"],
    })
    assert not can_recheck_source_function(batch, original, entry, item)
    with pytest.raises(ValueError):
        apply_source_function_recheck(batch, original, entry, item, proposal)
    assert original.model_dump_json() == before


@pytest.mark.parametrize("resolved", [True, False])
def test_runner_reaffirmed_function_requires_one_valid_target_review(resolved: bool) -> None:
    batch, original, entry, review, proposal = _function_disagreement()
    target_quote = "研究总时长包括资料准备和后续随访两部分"
    batch.known_official_targets[0].source_excerpts = [target_quote]
    proposal.statements[0] = original.statements[0].model_copy(deep=True)
    corrected = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{
            "statement_index": 0,
            "decision": "covered_by_official" if resolved else "unresolved",
            "target_id": "EX-01" if resolved else None,
            "source_action_excerpt": original.statements[0].quoted_text,
            "target_action_excerpt": target_quote if resolved else None,
            "unresolved_aspects": [] if resolved else ["本条定义的使用范围仍未核清"],
        }],
    })

    class Transport(_FakeTransport):
        function_calls = 0
        target_calls = 0
        definition_calls = 0

        def start_source_definition_consumers(self, *, prompt: str):
            self.definition_calls += 1
            return ProtocolControlAgentResponse(
                session_id="definition-consumers",
                text=json.dumps({
                    "version": "phase5/control-source-definition-consumer/v2", "items": [],
                }),
            )

        def start_source_interpretation(self, *, prompt: str):
            self.function_calls += 1
            return ProtocolControlAgentResponse(session_id="function-retained", text=proposal.model_dump_json())

        def start_source_target_review(self, *, prompt: str):
            self.target_calls += 1
            source_line = next(line for line in prompt.splitlines() if line.startswith("待核陈述："))
            assert json.loads(source_line.removeprefix("待核陈述："))[0]["background_context_allowed"] is False
            assert "本次必须且只能返回这些 statement_index：[0]" in prompt
            return ProtocolControlAgentResponse(
                session_id=f"target-{self.target_calls}",
                text=(review if self.target_calls == 1 else corrected).model_dump_json(),
            )

        def start(self, *, prompt: str):
            pytest.fail("单条用途分歧不得触发重新编写已有候选")

    transport = Transport([])
    wire = _wire(candidate=_candidate())
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_wire=wire, resume_source_interpretation=original,
        resume_session_id="saved-wire", output_validator=lambda value: None,
    )
    assert transport.function_calls == 1
    assert transport.target_calls == 2
    assert transport.definition_calls == int(resolved)
    assert result.source_interpretation == original
    assert result.source_target_review == corrected
    assert result.partial_wire == wire
    assert (result.final_output is not None) == resolved
    assert any("SOURCE_TARGET_REVIEW_INVALID" in attempt.error_classes
               for attempt in result.attempts)
    assert not any("SOURCE_FUNCTION_RECHECK_UNRESOLVED" in attempt.error_classes
                   for attempt in result.attempts)


@pytest.mark.parametrize("field, value", [
    ("candidate_indexes", [0]), ("linked_candidate_indexes", [0]),
    ("action_candidate_indexes", [0]), ("matched_roles", ["trigger"]),
    ("linked_official_code", "EX-01"),
    ("linked_procedure_target_ids", ["procedure-screening-1"]),
    ("exact_official_excerpt_matches", ["EX-01"]),
    ("exact_procedure_excerpt_matches", ["procedure-screening-1"]),
    ("schedule_columns", [{"column_index": 1, "cell_source_ref": "cell-1",
                            "header_source_refs": ["header-1"], "visit_instance": "筛选",
                            "boundary_side": "at_or_before_baseline"}]),
])
def test_source_function_recheck_cannot_discard_consumers(field, value) -> None:
    batch, original, entry, review, proposal = _function_disagreement()
    entry = entry.model_copy(update={field: value})
    assert not can_recheck_source_function(batch, original, entry, review.items[0])
    with pytest.raises(ValueError, match="消费依赖"):
        apply_source_function_recheck(batch, original, entry, review.items[0], proposal)


@pytest.mark.parametrize("change", [
    {"quoted_text": "另一句原文"}, {"time_words": ["筛选前"]},
    {"scope_quote": "另一阶段"}, {"force": "unclear"},
    {"exception_words": "有例外"}, {"eligibility_sequence": "after_eligibility_decision"},
    {"structure_unit_id": "su-01"}, {"attribution_quote": "外部说明"},
    {"decision_functions": ["action"]}, {"unresolved": ["实际用途未明"]},
])
def test_source_function_recheck_rejects_meaning_changes_and_uncertainty(change) -> None:
    batch, original, entry, review, proposal = _function_disagreement()
    proposal.statements[0] = proposal.statements[0].model_copy(update=change)
    with pytest.raises(ValueError):
        apply_source_function_recheck(batch, original, entry, review.items[0], proposal)
    assert original.statements[0].decision_functions == ["definition", "time_validity"]


@pytest.mark.parametrize("functions", [["calculation_input"], ["threshold"], ["exception"], ["action"]])
def test_source_function_recheck_keeps_decisive_definitions(functions) -> None:
    batch, original, entry, review, proposal = _function_disagreement()
    original.statements[0].decision_functions = functions
    assert not can_recheck_source_function(batch, original, entry, review.items[0])
    original.statements[0].decision_functions = ["definition", "time_validity"]
    batch.known_official_targets[0].source_span_ids = ["span:02"]
    assert not can_recheck_source_function(batch, original, entry, review.items[0])
    batch.known_official_targets[0].source_span_ids = ["span:official"]
    proposal.statements.append(original.statements[0].model_copy(deep=True))
    with pytest.raises(ValueError, match="只能返回"):
        apply_source_function_recheck(batch, original, entry, review.items[0], proposal)


@pytest.mark.parametrize("failed", [False, True])
def test_runner_rechecks_one_function_without_reauthoring_candidate(failed: bool) -> None:
    batch, original, entry, review, proposal = _function_disagreement()
    if failed:
        proposal.statements[0].unresolved = ["仍可能限定实际审核时间"]

    class Transport(_FakeTransport):
        calls = 0

        def start_source_interpretation(self, *, prompt: str):
            self.calls += 1
            assert '"frozen_statement"' in prompt
            return ProtocolControlAgentResponse(session_id="function-1", text=proposal.model_dump_json())

        def start_source_target_review(self, *, prompt: str):
            return ProtocolControlAgentResponse(session_id="target-1", text=review.model_dump_json())

        def start(self, *, prompt: str):
            pytest.fail("用途复核不得重读已有合格候选")

    transport = Transport([])
    wire = _wire(candidate=_candidate())
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_wire=wire, resume_source_interpretation=original,
        resume_session_id="saved-wire", output_validator=lambda value: None,
    )
    assert transport.calls == 1
    assert result.partial_wire == wire
    if failed:
        assert result.status == "需要核对"
        assert result.final_output is None
        assert result.source_interpretation == original
        assert any("SOURCE_FUNCTION_RECHECK_UNRESOLVED" in attempt.error_classes
                   for attempt in result.attempts)
    else:
        assert result.status == "已解析"
        assert result.source_target_review == review
        assert result.source_interpretation.statements[0].decision_functions == ["background"]
        assert result.final_output is not None


def _raise_wrapped_terminal_failure(kind):
    from app.agents.protocol_control_agent_transport import (
        ProtocolControlAgentCallError, ProtocolControlModelIdentityError,
    )
    from app.llm.logical_call_budget import LogicalCallBudgetExhausted

    cause = {
        "identity": ProtocolControlModelIdentityError(
            "synthetic wrong model", configured_model="expected", reason="mismatch",
        ),
        "budget": LogicalCallBudgetExhausted("synthetic shared budget exhausted"),
        "interrupted": ProtocolControlAgentCallError(
            "interrupted-reader", "synthetic stream failure", uncertain_completion=True,
        ),
    }[kind]
    raise ProtocolControlAgentCallError("wrapped-reader", "synthetic adapter failure") from cause


@pytest.mark.parametrize("phase", ["discovery_start", "discovery_repair", "source_inventory", "wire_repair"])
@pytest.mark.parametrize("kind, code", [
    ("identity", "MODEL_IDENTITY_INVALID"),
    ("budget", "LOGICAL_BUDGET_EXHAUSTED"),
    ("interrupted", "FLOW_COMPLETION_UNCERTAIN"),
])
def test_sibling_read_terminal_causes_survive_wrappers_without_replay(phase, kind, code):
    from app.agents.protocol_control_deconstructor import (
        CONTROL_DISCOVERY_INPUT_VERSION, ProtocolControlDiscoveryAgentInput,
        ProtocolControlDiscoveryAgentRunner,
    )

    class Transport(_FakeTransport):
        calls = 0

        def start(self, *, prompt):
            self.calls += 1
            if phase == "discovery_start":
                _raise_wrapped_terminal_failure(kind)
            return ProtocolControlAgentResponse(session_id="first", text="{")

        def continue_session(self, **kwargs):
            self.calls += 1
            _raise_wrapped_terminal_failure(kind)

        def start_source_interpretation(self, **kwargs):
            self.calls += 1
            _raise_wrapped_terminal_failure(kind)

    transport = Transport([])
    batch = _batch()
    if phase.startswith("discovery"):
        unit = batch.owned_units[0]
        source = ProtocolControlDiscoveryAgentInput(
            schema_version=CONTROL_DISCOVERY_INPUT_VERSION,
            discovery_batch_id="discovery-synthetic", coverage_manifest_id="manifest-synthetic",
            protocol_version_id=batch.protocol_version_id, study_phase=unit.study_phase,
            target_units=[unit], target_structure_unit_ids=[unit.structure_unit_id],
        )
        result = ProtocolControlDiscoveryAgentRunner(max_transport_retries=3).run(source, transport)
    else:
        if phase == "wire_repair":
            transport.start_source_interpretation = None
        result = ProtocolControlAgentRunner(max_transport_retries=3).run(batch, transport)
    assert result.final_output is None
    assert result.attempts[-1].error_classes == [code]
    assert result.attempts[-1].outcome == "transport_failed"
    assert transport.calls == (2 if phase.endswith("repair") else 1)


@pytest.mark.parametrize("correction_kind", ["scope", "quote"])
@pytest.mark.parametrize("kind, code", [
    ("transport", "SOURCE_INTERPRETATION_CORRECTION_TRANSPORT_FAILED"),
    ("identity", "MODEL_IDENTITY_INVALID"),
    ("budget", "LOGICAL_BUDGET_EXHAUSTED"),
    ("interrupted", "FLOW_COMPLETION_UNCERTAIN"),
])
def test_inventory_correction_transport_failure_does_not_reread_all_sources(correction_kind, kind, code):
    invalid = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01",
                        "quoted_text": "年龄至少18周岁" if correction_kind == "quote" else "年龄至少18岁",
                        "force": "required",
                        "time_words": [] if correction_kind == "quote" else ["给药后7天"]}],
        "units_without_statement": ["su-02"],
    })

    class Transport(_FakeTransport):
        source_calls = 0
        repair_calls = 0

        def start_source_interpretation(self, **kwargs):
            self.source_calls += 1
            assert self.source_calls == 1
            return ProtocolControlAgentResponse(session_id="source-1", text=invalid.model_dump_json())

        def correct_source_scope(self, **kwargs):
            assert correction_kind == "scope"
            self.repair_calls += 1
            if kind == "transport":
                raise OSError("synthetic unavailable")
            _raise_wrapped_terminal_failure(kind)

        def correct_source_quote(self, **kwargs):
            assert correction_kind == "quote"
            self.repair_calls += 1
            if kind == "transport":
                raise OSError("synthetic unavailable")
            _raise_wrapped_terminal_failure(kind)

        def start(self, **kwargs):
            pytest.fail("Unvalidated source must not enter authoring")

    transport = Transport([])
    result = ProtocolControlAgentRunner().run(_batch(), transport)
    assert result.final_output is None and result.source_interpretation is None
    assert transport.source_calls == transport.repair_calls == 1
    assert result.attempts[-1].error_classes == [code]
    assert result.attempts[-1].raw_output_text is None
    assert result.attempts[0].raw_output_text == invalid.model_dump_json()


@pytest.mark.parametrize("failure, code, outcome", [
    ("transport", "SOURCE_FUNCTION_RECHECK_TRANSPORT_FAILED", "transport_failed"),
    ("schema", "SOURCE_FUNCTION_RECHECK_SCHEMA_INVALID", "schema_invalid"),
    ("scope", "SOURCE_FUNCTION_RECHECK_INVALID", "publication_invalid"),
    ("identity", "MODEL_IDENTITY_INVALID", "transport_failed"),
    ("budget", "LOGICAL_BUDGET_EXHAUSTED", "transport_failed"),
    ("interrupted", "FLOW_COMPLETION_UNCERTAIN", "transport_failed"),
])
def test_runner_function_failure_keeps_actual_cause_and_verified_wire(failure, code, outcome) -> None:
    batch, original, entry, review, proposal = _function_disagreement()
    proposal.statements[0].quoted_text = "未经授权改变原文"

    class Transport(_FakeTransport):
        target_calls = 0

        def start_source_interpretation(self, *, prompt: str):
            if failure in {"identity", "budget", "interrupted"}:
                _raise_wrapped_terminal_failure(failure)
            if failure == "transport":
                raise RuntimeError("isolated provider unavailable")
            return ProtocolControlAgentResponse(
                session_id="function-failure",
                text="{" if failure == "schema" else proposal.model_dump_json(),
            )

        def start_source_target_review(self, *, prompt: str):
            self.target_calls += 1
            return ProtocolControlAgentResponse(session_id="rejected-background", text=review.model_dump_json())

        def start(self, *, prompt: str):
            pytest.fail("复核故障不应丢弃已核结构并重写整批")

    transport = Transport([])
    wire = _wire(candidate=_candidate())
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_wire=wire, resume_source_interpretation=original,
        resume_session_id="saved-wire", output_validator=lambda _: None,
    )
    assert result.final_output is None
    assert result.partial_wire == wire
    assert result.source_interpretation == original
    assert transport.target_calls == 1
    assert result.attempts[-1].error_classes == [code]
    assert result.attempts[-1].outcome == outcome
    assert result.attempts[-1].error_detail["statement_id"] == 0
    if failure not in {"transport", "identity", "budget", "interrupted"}:
        assert result.attempts[-1].raw_output_text != review.model_dump_json()


def test_unclassified_source_cannot_be_closed_by_matching_candidate_text() -> None:
    batch = _batch()
    inventory = SourceInterpretation(
        version=SOURCE_INTERPRETATION_VERSION,
        statements=[SourceStatement(
            structure_unit_id="su-01", quoted_text="年龄至少18岁", force="unclear",
            decision_functions=["unclassified"], time_words=[], unresolved=["用途未核清"],
        )], units_without_statement=["su-02"],
    )
    candidate = _candidate().model_copy(deep=True)
    candidate.obligation_expression.groups[0].atoms[0].statement = "年龄至少18岁"
    coverage = source_statement_coverage(batch, inventory, _wire(candidate=candidate))
    assert coverage[0].status != "expressed"
    assert target_review_indexes(inventory, coverage, batch) == [0]
    claimed_covered = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "covered_by_official",
                   "source_action_excerpt": "年龄至少18岁", "target_id": "EX-01",
                   "target_action_excerpt": "年龄至少18岁"}],
    })
    with pytest.raises(SourceTargetReviewValidationError) as error:
        validate_source_target_review(batch, inventory, coverage, claimed_covered)
    assert error.value.code == "SOURCE_FUNCTION_UNRESOLVED"
    unresolved = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "unresolved",
                   "source_action_excerpt": "年龄至少18岁",
                   "unresolved_aspects": ["原文对本节点审核的用途尚未核清"]}],
    })
    validate_source_target_review(batch, inventory, coverage, unresolved)


def test_shared_procedure_paragraph_does_not_prove_every_visit_scope() -> None:
    batch = _batch().model_copy(deep=True)
    paragraph = (
        "筛选期和EOS需完成甲检查，其余访视可完成乙检查。"
        "W0可接受给药前7天内乙检查结果。"
        "筛选期及首次给药前完成丙检查。"
        "除筛选期外其余访视完成丁检查。"
    )
    batch.owned_units[0].excerpt = paragraph
    batch.known_procedure_targets = [
        KnownRequiredProcedureTarget(
            catalog_item_id=f"procedure-{visit}", label="检查",
            visit_instance=visit, review_stage=stage, position=index,
            source_span_ids=["span:shared"], source_excerpts=[paragraph],
        )
        for index, (visit, stage) in enumerate((
            ("筛选访视", ReviewStage.SCREENING),
            ("基线访视 / W0", ReviewStage.BASELINE),
        ))
    ]

    def check(quote: str, time_words: list[str], target_id: str,
              decision: str = "covered_by_procedure") -> None:
        inventory = SourceInterpretation(
            version=SOURCE_INTERPRETATION_VERSION,
            statements=[SourceStatement(
                structure_unit_id="su-01", quoted_text=quote,
                force="required", decision_functions=["action"], time_words=time_words,
            )], units_without_statement=["su-02"],
        )
        coverage = [SourceStatementCoverage(
            statement_index=0, structure_unit_id="su-01",
            disposition="required_procedure", status="not_located",
        )]
        review = SourceTargetReview.model_validate({
            "version": SOURCE_TARGET_REVIEW_VERSION,
            "items": [{
                "statement_index": 0, "decision": decision,
                "target_id": target_id, "source_action_excerpt": quote,
                "target_action_excerpt": quote,
                "source_time_excerpt": quote if time_words else None,
                "target_time_excerpt": quote if time_words else None,
                "unresolved_aspects": [] if decision == "covered_by_procedure" else ["访视范围待核"],
            }],
        })
        validate_source_target_review(batch, inventory, coverage, review)

    with pytest.raises(SourceTargetReviewValidationError) as other_visit:
        check("其余访视可完成乙检查", ["其余访视"], "procedure-筛选访视")
    assert other_visit.value.code == "TARGET_VISIT_SCOPE_UNPROVEN"
    with pytest.raises(SourceTargetReviewValidationError) as omitted_time:
        check("其余访视可完成乙检查", [], "procedure-筛选访视")
    assert omitted_time.value.code == "SOURCE_TIME_INCOMPLETE"
    with pytest.raises(SourceTargetReviewValidationError) as mixed_visit:
        check("筛选期和EOS需完成甲检查", ["筛选期", "EOS"], "procedure-筛选访视")
    assert mixed_visit.value.code == "TARGET_VISIT_SCOPE_UNPROVEN"
    with pytest.raises(SourceTargetReviewValidationError) as parallel_visit:
        check("筛选期及首次给药前完成丙检查", ["筛选期", "首次给药前"],
              "procedure-筛选访视")
    assert parallel_visit.value.code == "TARGET_VISIT_SCOPE_UNPROVEN"
    with pytest.raises(SourceTargetReviewValidationError) as excluded_visit:
        check("除筛选期外其余访视完成丁检查", ["筛选期", "其余访视"],
              "procedure-筛选访视")
    assert excluded_visit.value.code == "TARGET_VISIT_SCOPE_UNPROVEN"
    batch.known_procedure_targets[1].source_excerpts[0] = paragraph.replace(
        "W0可接受给药前7天内乙检查结果。", "W0可接受给药前7天内乙检查结果；"
    )
    with pytest.raises(SourceTargetReviewValidationError) as formatting:
        check("其余访视可完成乙检查", ["其余访视"], "procedure-筛选访视")
    assert formatting.value.code == "TARGET_VISIT_SCOPE_UNPROVEN"
    check("W0可接受给药前7天内乙检查结果", ["W0", "给药前7天内"],
          "procedure-基线访视 / W0")
    check("其余访视可完成乙检查", ["其余访视"], "procedure-筛选访视",
          "additional_requirement")


def test_source_coverage_rejects_cross_statement_identity() -> None:
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": "年龄至少18岁",
                        "force": "required", "time_words": []}],
        "units_without_statement": ["su-02"],
    })
    wrong = SourceStatementCoverage(
        statement_index=0, structure_unit_id="su-02",
        disposition="other_control_candidate", status="candidate_linked",
    )
    with pytest.raises(SourceTargetReviewValidationError) as error:
        target_review_indexes(inventory, [wrong], _batch())
    assert error.value.code == "SOURCE_COVERAGE_IDENTITY_INVALID"


def test_post_eligibility_action_requires_source_order_and_no_current_candidate() -> None:
    batch = _batch()
    batch.owned_units[0].excerpt = (
        "先确认符合入排条件的受试者，再随机分组并给予研究治疗。"
    )
    inventory = SourceInterpretation(
        version=SOURCE_INTERPRETATION_VERSION,
        statements=[SourceStatement(
            structure_unit_id="su-01", quoted_text="随机分组并给予研究治疗",
            force="required", decision_functions=["action"], time_words=[],
            eligibility_sequence="after_eligibility_decision",
            eligibility_sequence_quote="先确认符合入排条件的受试者",
        )],
        units_without_statement=["su-02"],
    )
    validate_source_interpretation(batch, inventory)
    coverage = [SourceStatementCoverage(
        statement_index=0, structure_unit_id="su-01",
        disposition="other_control_candidate", status="candidate_linked",
    )]
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{
            "statement_index": 0, "decision": "not_current_control", "target_id": None,
            "source_action_excerpt": "随机分组并给予研究治疗",
            "non_control_basis_excerpt": "先确认符合入排条件的受试者",
        }],
    })
    validate_source_target_review(batch, inventory, coverage, review)

    wrong_order = inventory.model_copy(deep=True)
    wrong_order.statements[0].eligibility_sequence_quote = "给予研究治疗"
    with pytest.raises(SourceInterpretationValidationError, match="位于动作之前"):
        validate_source_interpretation(batch, wrong_order)
    unconfirmed = inventory.model_copy(deep=True)
    unconfirmed.statements[0].eligibility_sequence = "current_or_unknown"
    unconfirmed.statements[0].eligibility_sequence_quote = None
    with pytest.raises(SourceTargetReviewValidationError, match="先后依据一致"):
        validate_source_target_review(batch, unconfirmed, coverage, review)
    still_current = coverage[0].model_copy(update={"action_candidate_indexes": [0]})
    with pytest.raises(SourceTargetReviewValidationError, match="不能同时列为"):
        validate_source_target_review(batch, inventory, [still_current], review)


def test_runner_rejects_candidate_for_action_after_eligibility_decision() -> None:
    batch = _batch()
    batch.owned_units[0].excerpt = "先确认符合入排条件的受试者，再核对年龄至少18岁。"
    inventory = SourceInterpretation(
        version=SOURCE_INTERPRETATION_VERSION,
        statements=[SourceStatement(
            structure_unit_id="su-01", quoted_text="年龄至少18岁", force="required",
            time_words=[], eligibility_sequence="after_eligibility_decision",
            eligibility_sequence_quote="先确认符合入排条件的受试者",
        )],
        units_without_statement=["su-02"],
    )
    transport = _FakeTransport([ProtocolControlAgentResponse(
        session_id="post-eligibility", text=_wire(candidate=_candidate()).model_dump_json(),
    )])
    result = ProtocolControlAgentRunner(max_schema_repairs=0).run(
        batch, transport, resume_source_interpretation=inventory,
    )
    assert result.status == "需要核对"
    assert any("POST_ELIGIBILITY_ACTION_AS_CONTROL" in attempt.error_classes
               for attempt in result.attempts)
    assert result.final_output is None


def test_cited_external_rationale_closes_only_its_own_statement() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].excerpt = (
        "某共识建议在给药前设置观察期，其作用是识别对对照处理有反应者（予以排除）。"
        "本研究要求在筛选时记录既往治疗。"
    )
    inventory = SourceInterpretation(
        version=SOURCE_INTERPRETATION_VERSION,
        statements=[
            SourceStatement(
                    structure_unit_id="su-01", quoted_text="识别对对照处理有反应者（予以排除）",
                    force="prohibited", decision_functions=["background"], time_words=[],
                control_authority="cited_external_rationale", attribution_quote="某共识建议",
            ),
            SourceStatement(
                structure_unit_id="su-01", quoted_text="本研究要求在筛选时记录既往治疗",
                force="required", time_words=["筛选时"],
            ),
        ],
        units_without_statement=["su-02"],
    )
    validate_source_interpretation(batch, inventory)
    coverage = [
        SourceStatementCoverage(statement_index=0, structure_unit_id="su-01",
                                disposition="supporting_or_supplement", status="not_located"),
        SourceStatementCoverage(statement_index=1, structure_unit_id="su-01",
                                disposition="supporting_or_supplement", status="not_located"),
    ]
    assert target_review_indexes(inventory, coverage, batch) == [0, 1]
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [
            {"statement_index": 0, "decision": "cited_external_rationale", "target_id": None,
             "source_action_excerpt": "识别对对照处理有反应者（予以排除）",
             "attribution_excerpt": "某共识建议"},
            {"statement_index": 1, "decision": "unresolved", "target_id": None,
             "source_action_excerpt": "本研究要求在筛选时记录既往治疗",
             "unresolved_aspects": ["尚未核实本研究的筛选操作要求"]},
        ],
    })
    validate_source_target_review(batch, inventory, coverage, review)
    assert review.items[1].decision == "unresolved"
    with_candidate = coverage[0].model_copy(update={"action_candidate_indexes": [0]})
    with pytest.raises(SourceTargetReviewValidationError, match="仍被写成候选控制"):
        validate_source_target_review(batch, inventory, [with_candidate, coverage[1]], review)
    with_target = review.model_copy(deep=True)
    with_target.items[0].target_id = "EX-01"
    with pytest.raises(SourceTargetReviewValidationError, match="不能携带已有目标"):
        validate_source_target_review(batch, inventory, coverage, with_target)


def test_attributed_rationale_cannot_hide_adopted_or_unattributed_rule() -> None:
    batch = _batch().model_copy(deep=True)
    statement = SourceStatement(
        structure_unit_id="su-01", quoted_text="对照反应者不得随机",
        force="prohibited", time_words=[], control_authority="cited_external_rationale",
        attribution_quote="某指南建议",
    )
    inventory = SourceInterpretation(
        version=SOURCE_INTERPRETATION_VERSION, statements=[statement],
        units_without_statement=["su-02"],
    )
    batch.owned_units[0].excerpt = "某指南建议，本研究规定对照反应者不得随机。"
    with pytest.raises(SourceInterpretationValidationError, match="不得含本研究采纳要求"):
        validate_source_interpretation(batch, inventory)
    batch.owned_units[0].excerpt = "某指南建议设置观察期。对照反应者不得随机。"
    with pytest.raises(SourceInterpretationValidationError, match="同句在前"):
        validate_source_interpretation(batch, inventory)
    batch.owned_units[0].excerpt = "可参照某指南对照反应者不得随机。"
    with pytest.raises(SourceInterpretationValidationError, match="逐字归因"):
        validate_source_interpretation(batch, inventory)


def test_external_attribution_inside_full_sentence_quote_still_needs_review() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].excerpt = "某共识建议观察受试者反应（予以排除）。"
    statement = SourceStatement(
        structure_unit_id="su-01", quoted_text="某共识建议观察受试者反应（予以排除）",
        force="descriptive", time_words=[],
    )
    inventory = SourceInterpretation(
        version=SOURCE_INTERPRETATION_VERSION, statements=[statement],
        units_without_statement=["su-02"],
    )
    with pytest.raises(SourceInterpretationValidationError, match="逐字归因"):
        validate_source_interpretation(batch, inventory)
    statement.control_authority = "cited_external_rationale"
    statement.attribution_quote = "某共识建议"
    validate_source_interpretation(batch, inventory)
    for status, disposition in [("expressed", "supporting_or_supplement"),
                                ("not_located", "non_control")]:
        coverage = [SourceStatementCoverage(
            statement_index=0, structure_unit_id="su-01",
            disposition=disposition, status=status,
        )]
        assert target_review_indexes(inventory, coverage, batch) == [0]


def test_runner_keeps_external_rationale_out_of_new_control() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].excerpt = "某共识建议设置观察期以识别对照反应者（予以排除）。"
    inventory = SourceInterpretation(
        version=SOURCE_INTERPRETATION_VERSION,
        statements=[SourceStatement(
            structure_unit_id="su-01", quoted_text="识别对照反应者（予以排除）",
            force="prohibited", decision_functions=["background"], time_words=[],
            control_authority="cited_external_rationale", attribution_quote="某共识建议",
        )], units_without_statement=["su-02"],
    )
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "cited_external_rationale",
                   "target_id": None, "source_action_excerpt": "识别对照反应者（予以排除）",
                   "attribution_excerpt": "某共识建议"}],
    })

    class Transport(_FakeTransport):
        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.prompts.append(prompt)
            return ProtocolControlAgentResponse(session_id="external-rationale", text=review.model_dump_json())

    result = ProtocolControlAgentRunner(max_schema_repairs=0).run(
        batch, Transport([ProtocolControlAgentResponse(
            session_id="wire-new", text=_wire().model_dump_json(),
        )]), output_validator=lambda _output: None,
        resume_source_interpretation=inventory,
    )
    assert result.status == "已解析"
    assert result.final_output is not None and not result.final_output.candidates
    assert result.source_target_review == review


def test_atom_repair_explains_null_time_constraint_without_inventing_a_window() -> None:
    prompt = _build_obligation_atom_repair_prompt(
        _batch(), _wire(candidate=_candidate()).model_dump(mode="json"),
        (0, 0, 0), "未给出时间约束，不能声明已确定其计算用途",
    )
    assert "time_purpose 只能是 not_applicable 或 unresolved" in prompt
    assert "不得凭访视背景推造日期计算" in prompt
    assert "返回的是完整原子" in prompt
    assert "确为无量纲时写 unitless" in prompt
    assert "原文未说明如何选择记录时写 unresolved" in prompt
    assert "time_constraint 为 null" in prompt
    assert "evaluation.time_operand_attribute 也必须为 null" in prompt
    assert "独立 time_constraint 计算只用 operand_attribute" in prompt


def test_duration_atom_repair_limits_observation_modes_without_erasing_period() -> None:
    prompt = _build_obligation_atom_repair_prompt(
        _batch(), _wire(candidate=_candidate()).model_dump(mode="json"),
        (0, 0, 0),
        "WIRE_SCHEMA_INVALID: 操作完成核对只适用于无额外持续期或结果条件的必做操作",
    )
    assert "有时间约束或持续期的义务不可使用 action_completion" in prompt
    assert "不得删除持续期或把它改成单次记录" in prompt
    assert "single、any、all、action_completion、unresolved" in prompt


def test_treatment_duration_repair_uses_typed_anchor_not_visit_labels() -> None:
    prompt = _build_obligation_atom_repair_prompt(
        _batch(), _wire(candidate=_candidate()).model_dump(mode="json"),
        (0, 0, 0), "TREATMENT_DURATION_USED_AS_EVENT_WINDOW",
    )
    assert '"anchor_type":"screening_date"' in prompt
    assert "D-7、D-1、访视名称" in prompt
    assert "evaluation.time_purpose" in prompt


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
    inventory = _source_inventory({
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

    unresolved_inventory = inventory.model_copy(deep=True)
    unresolved_inventory.statements[1].unresolved = ["筛选时的适用范围未核清"]
    with pytest.raises(SourceTargetReviewValidationError) as unresolved_error:
        validate_source_target_review(batch, unresolved_inventory, coverage, review)
    assert unresolved_error.value.code == "SOURCE_UNRESOLVED_STILL_COVERED"

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
    with pytest.raises(SourceTargetReviewValidationError, match="目标时间缺少原文或访视定位") as mismatch:
        validate_source_target_review(batch, inventory, coverage, borrowed_time)
    assert mismatch.value.code == "TARGET_TIME_UNGROUNDED"
    assert mismatch.value.statement_index == 1
    assert mismatch.value.json_path == "/items/1/target_time_excerpt"


    assert mismatch.value.retry_class == "single_statement"
    assert mismatch.value.source_refs
    reversed_review = borrowed_time.model_copy(deep=True)
    reversed_review.items.reverse()
    with pytest.raises(SourceTargetReviewValidationError) as reversed_mismatch:
        validate_source_target_review(batch, inventory, coverage, reversed_review)
    assert reversed_mismatch.value.statement_index == 1
    assert reversed_mismatch.value.json_path == "/items/0/target_time_excerpt"

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

    partial_context_target = partial.model_copy(deep=True)
    partial_context_target.items[1].target_id = "su-03"
    partial_context_target.items[1].target_action_excerpt = "只读上下文"
    with pytest.raises(ValueError, match="非冻结或不唯一的目标"):
        validate_source_target_review(batch, inventory, coverage, partial_context_target)

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
    source_line = next(line for line in build_source_target_review_prompt(
        batch, inventory, linked).splitlines() if line.startswith("待核陈述："))
    assert json.loads(source_line.removeprefix("待核陈述："))[0]["linked_official_code"] == "EX-01"
    from app.agents.protocol_control_source_interpretation import source_target_review_response_format
    review_prompt = build_source_target_review_prompt(batch, inventory, linked)
    assert f'"version":"{SOURCE_TARGET_REVIEW_VERSION}"' in review_prompt
    assert "只读来源单元仅供识别跨章节复述" in review_prompt
    assert "quoted_text 内的连续原文" in review_prompt
    assert "时间和例外仍须另行核对" in review_prompt
    assert "只读来源线索：" in review_prompt
    assert "其他所有 decision 的这三个字段必须填 null" in review_prompt
    context_line = next(line for line in review_prompt.splitlines() if line.startswith("只读来源线索："))
    assert json.loads(context_line.removeprefix("只读来源线索："))[0]["structure_unit_id"] == "su-03"
    assert source_target_review_response_format()["json_schema"]["name"].endswith(
        SOURCE_TARGET_REVIEW_VERSION.rsplit("/", 1)[-1]
    )


def test_source_target_review_does_not_relabel_old_receipts_as_current() -> None:
    current = json.dumps({"version": SOURCE_TARGET_REVIEW_VERSION, "items": []})
    for prior_version in ("phase5/control-source-target-review/v17",
                          "phase5/control-source-target-review/v20"):
        with pytest.raises(ValidationError):
            SourceTargetReview.model_validate_json(json.dumps({
                "version": prior_version, "items": [],
            }))
    assert SourceTargetReview.model_validate_json(current).version == SOURCE_TARGET_REVIEW_VERSION
    assert (source_target_review_response_format()["json_schema"]["schema"]["properties"]["version"]["const"]
            == SOURCE_TARGET_REVIEW_VERSION)


def test_product_source_reader_must_name_function_or_explain_unknown() -> None:
    payload = {
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-01", "quoted_text": "完成筛选检查",
            "force": "required", "time_words": [],
        }],
        "units_without_statement": [],
    }
    statement_schema = source_interpretation_response_format()["json_schema"]["schema"]["$defs"]["SourceStatement"]
    required = statement_schema["required"]
    assert "decision_functions" in required
    assert "default" not in statement_schema["properties"]["decision_functions"]
    with pytest.raises(SourceInterpretationValidationError) as missing:
        parse_product_source_interpretation(_batch(), json.dumps(payload))
    assert missing.value.code == "SOURCE_FUNCTION_UNSTATED"
    payload["statements"][0]["decision_functions"] = ["unclassified"]
    with pytest.raises(SourceInterpretationValidationError) as unclear:
        parse_product_source_interpretation(_batch(), json.dumps(payload))
    assert unclear.value.code == "SOURCE_FUNCTION_UNRESOLVED"
    payload["statements"][0]["unresolved"] = ["尚不能判断是否用于本节点"]
    assert parse_product_source_interpretation(_batch(), json.dumps(payload)).statements[0].decision_functions == [
        "unclassified",
    ]
    payload["statements"][0]["decision_functions"] = ["action"]
    payload["statements"][0]["unresolved"] = []
    assert parse_product_source_interpretation(_batch(), json.dumps(payload)).statements[0].decision_functions == [
        "action",
    ]


def test_source_target_review_accepts_only_earlier_same_unit_time_prefix() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[1].excerpt = (
        "筛选/导入期（D-7~D-1）：记录末次用药日期；治疗后核对其他资料。"
    )
    batch.known_procedure_targets[0].source_excerpts = ["记录末次用药日期"]
    batch.known_procedure_targets[0].visit_instance = "筛选/导入期 D-7~D-1"
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-02",
            "quoted_text": "记录末次用药日期",
            "force": "required",
            "time_words": [],
        }],
        "units_without_statement": ["su-01"],
    })
    coverage = [SourceStatementCoverage(
        statement_index=0, structure_unit_id="su-02",
        disposition="other_control_candidate", status="candidate_linked",
    )]
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{
            "statement_index": 0,
            "decision": "covered_by_procedure",
            "target_id": "procedure-screening-1",
            "source_action_excerpt": "记录末次用药日期",
            "target_action_excerpt": "记录末次用药日期",
            "source_time_excerpt": "D-7~D-1",
            "target_time_excerpt": "D-7~D-1",
            "unresolved_aspects": [],
        }],
    })
    validate_source_target_review(batch, inventory, coverage, review)

    batch.owned_units[1].excerpt = (
        "筛选期：核对其他资料。基线期（D-7~D-1）：记录末次用药日期。"
    )
    with pytest.raises(SourceTargetReviewValidationError) as failure:
        validate_source_target_review(batch, inventory, coverage, review)
    assert failure.value.code == "SOURCE_TIME_UNGROUNDED"


def test_source_target_review_keeps_same_sentence_subject_without_importing_conditions() -> None:
    batch = _batch().model_copy(deep=True)
    full_action = "所有受试者均需要完成肺功能测定"
    batch.owned_units[1].excerpt = full_action + "。"
    batch.known_procedure_targets[0].source_excerpts = [full_action]
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-02", "quoted_text": "均需要完成肺功能测定",
            "force": "required", "time_words": [],
        }],
        "units_without_statement": ["su-01"],
    })
    coverage = [SourceStatementCoverage(
        statement_index=0, structure_unit_id="su-02",
        disposition="other_control_candidate", status="candidate_linked",
    )]
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{
            "statement_index": 0, "decision": "covered_by_procedure",
            "target_id": "procedure-screening-1",
            "source_action_excerpt": full_action,
            "target_action_excerpt": full_action,
            "source_time_excerpt": None, "target_time_excerpt": None,
            "unresolved_aspects": [],
        }],
    })
    validate_source_target_review(batch, inventory, coverage, review)

    batch.owned_units[1].excerpt = "筛选前：" + full_action + "。"
    review.items[0].source_action_excerpt = "筛选前：" + full_action
    review.items[0].target_action_excerpt = review.items[0].source_action_excerpt
    with pytest.raises(SourceTargetReviewValidationError) as failure:
        validate_source_target_review(batch, inventory, coverage, review)
    assert failure.value.code == "SOURCE_ACTION_MISMATCH"


def test_source_target_review_accepts_only_verified_shared_time_scope() -> None:
    batch = _batch().model_copy(deep=True)
    period = "整个研究期间（从签署知情同意到末次给药后6个月）"
    action = "受试者及其伴侣同意采取避孕措施"
    batch.owned_units[1].excerpt = f"{period}，{action}"
    batch.known_procedure_targets[0].source_excerpts = [f"{period}，{action}"]
    inventory = _source_inventory({
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


@pytest.mark.parametrize(
    ("source_time", "target_time", "expected_code"),
    [
        ("筛选前2周内", "筛选前14天内", None),
        ("筛选前2周内", "基线前14天内", "TIME_SCOPE_MISMATCH"),
        ("筛选前2周内", "筛选后14天内", "TIME_SCOPE_MISMATCH"),
        ("筛选前2周内", "筛选前14天以上", "TIME_SCOPE_MISMATCH"),
        ("筛选前2周内", "筛选前30天内", "TIME_SCOPE_MISMATCH"),
        ("筛选前2周内", "第14天访视", "TIME_SCOPE_MISMATCH"),
        ("筛选前1个月内", "筛选前30天内", "TIME_SCOPE_MISMATCH"),
    ],
)
def test_source_target_review_converts_only_same_bounded_day_week_window(
    source_time: str, target_time: str, expected_code: str | None,
) -> None:
    batch = _batch().model_copy(deep=True)
    action = "核对既往用药"
    batch.owned_units[1].excerpt = f"{source_time}，{action}"
    batch.known_procedure_targets[0].source_excerpts = [f"{target_time}，{action}"]
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-02", "quoted_text": action,
            "scope_quote": source_time, "force": "required",
            "time_words": [source_time],
        }],
        "units_without_statement": ["su-01"],
    })
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
            "source_time_excerpt": source_time, "target_time_excerpt": target_time,
            "unresolved_aspects": [],
        }],
    })
    if expected_code is None:
        validate_source_target_review(batch, inventory, coverage, review)
    else:
        with pytest.raises(SourceTargetReviewValidationError) as failure:
            validate_source_target_review(batch, inventory, coverage, review)
        assert failure.value.code == expected_code


def test_source_target_review_checks_scope_and_duration_separately() -> None:
    batch = _batch().model_copy(deep=True)
    period = "筛选期及治疗期"
    action = "计划离开观察区48小时及以上"
    batch.owned_units[1].excerpt = f"{period}，{action}"
    batch.known_procedure_targets[0].source_excerpts = [f"{period}，{action}"]
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-02", "quoted_text": action,
            "scope_quote": period, "force": "prohibited",
            "time_words": ["筛选期", "治疗期", "48小时及以上"],
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
            "source_action_excerpt": "计划离开观察区",
            "target_action_excerpt": "计划离开观察区",
            "source_time_excerpt": period, "target_time_excerpt": period,
            "unresolved_aspects": [],
        }],
    })
    validate_source_target_review(batch, inventory, coverage, review)

    missing_duration = batch.model_copy(deep=True)
    missing_duration.known_procedure_targets[0].source_excerpts = [f"{period}，计划离开观察区"]
    with pytest.raises(SourceTargetReviewValidationError) as failure:
        validate_source_target_review(missing_duration, inventory, coverage, review)
    assert failure.value.code == "TARGET_TIME_INCOMPLETE"


def test_matching_dosing_frequency_alone_does_not_close_visit_coverage() -> None:
    batch = _batch().model_copy(deep=True)
    quote = "每日1次记录用药情况"
    batch.owned_units[1].excerpt = quote
    batch.known_procedure_targets[0].source_excerpts = [quote]
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-02", "quoted_text": quote,
                        "force": "required", "time_words": ["每日1次"]}],
        "units_without_statement": ["su-01"],
    })
    coverage = [SourceStatementCoverage(
        statement_index=0, structure_unit_id="su-02",
        disposition="other_control_candidate", status="candidate_linked",
    )]
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "covered_by_procedure",
                   "target_id": "procedure-screening-1",
                   "source_action_excerpt": quote, "target_action_excerpt": quote,
                   "source_time_excerpt": "每日1次", "target_time_excerpt": "每日1次",
                   "unresolved_aspects": []}],
    })
    validate_source_interpretation(batch, inventory)
    with pytest.raises(SourceTargetReviewValidationError) as error:
        validate_source_target_review(batch, inventory, coverage, review)
    assert error.value.code == "FREQUENCY_ONLY_COVERAGE"

    scoped_batch = batch.model_copy(deep=True)
    scoped_batch.owned_units[1].excerpt = "筛选期：" + quote
    scoped_batch.known_procedure_targets[0].visit_instance = "筛选期"
    scoped_inventory = inventory.model_copy(deep=True)
    scoped_inventory.statements[0].scope_quote = "筛选期"
    scoped_inventory.statements[0].time_words = ["筛选期", "每日1次"]
    validate_source_interpretation(scoped_batch, scoped_inventory)
    validate_source_target_review(scoped_batch, scoped_inventory, coverage, review)


def test_context_correspondence_is_only_a_sourced_pending_relation() -> None:
    batch = _batch().model_copy(deep=True)
    action = "每次给药10 mg，每日1次"
    batch.owned_units[1].excerpt = "背景治疗：" + action
    batch.context_units[0].excerpt = "所有受试者自筛选期开始接受背景治疗：" + action
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-02", "quoted_text": action,
                        "force": "required", "time_words": ["每日1次"]}],
        "units_without_statement": ["su-01"],
    })
    coverage = [SourceStatementCoverage(
        statement_index=0, structure_unit_id="su-02",
        disposition="other_control_candidate", status="candidate_linked",
    )]
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "potential_same_requirement",
                   "target_id": "su-03", "source_action_excerpt": action,
                   "target_action_excerpt": action, "target_scope_excerpt": "自筛选期开始",
                   "source_object_excerpt": "背景治疗", "target_object_excerpt": "背景治疗"}],
    })
    validate_source_interpretation(batch, inventory)
    validate_source_target_review(batch, inventory, coverage, review)
    review_prompt = build_source_target_review_prompt(batch, inventory, coverage)
    assert "target_id 必须填写该只读单元的 structure_unit_id" in review_prompt
    assert "不能填写 source_ref" in review_prompt
    for duplicate_source_ref in (False, True):
        wrong_namespace_batch = batch.model_copy(deep=True)
        if duplicate_source_ref:
            sibling = wrong_namespace_batch.context_units[0].model_copy(deep=True)
            sibling.structure_unit_id = "su-another-context"
            wrong_namespace_batch.context_units.append(sibling)
        wrong_namespace = review.model_copy(deep=True)
        wrong_namespace.items[0].target_id = batch.context_units[0].source_ref
        original = wrong_namespace.model_dump(mode="json")
        with pytest.raises(SourceTargetReviewValidationError) as error:
            validate_source_target_review(wrong_namespace_batch, inventory, coverage, wrong_namespace)
        assert error.value.code == "CONTEXT_TARGET_ID_INVALID"
        assert error.value.json_path == "/items/0/target_id"
        assert wrong_namespace.model_dump(mode="json") == original

    canonical_overlap = batch.model_copy(deep=True)
    sibling = canonical_overlap.context_units[0].model_copy(deep=True)
    sibling.structure_unit_id = "su-another-context"
    sibling.source_ref = review.items[0].target_id
    sibling.excerpt = "本条并非同一要求"
    canonical_overlap.context_units.append(sibling)
    validate_source_target_review(canonical_overlap, inventory, coverage, review)
    with_alias = batch.model_copy(deep=True)
    with_alias.context_units[0].excerpt = "所有受试者自筛选期开始接受背景治疗[别名]：" + action
    validate_source_target_review(with_alias, inventory, coverage, review)
    prompt = build_source_unit_comparison_prompt(batch, inventory, 0)
    assert "背景治疗：" + action in prompt
    assert "自筛选期开始接受背景治疗：" + action in prompt
    assert '"row_headers"' in prompt
    changed_object = review.model_copy(deep=True)
    changed_object.items[0].target_object_excerpt = "另一治疗"
    with pytest.raises(SourceTargetReviewValidationError, match="相同对象"):
        validate_source_target_review(batch, inventory, coverage, changed_object)
    for target_id, target_action, scope in (
        ("su-missing", action, "自筛选期开始"),
        ("su-03", "每次给药20 mg，每日1次", "自筛选期开始"),
        ("su-03", action, "自基线期开始"),
    ):
        changed = review.model_copy(deep=True)
        changed.items[0].target_id = target_id
        changed.items[0].target_action_excerpt = target_action
        changed.items[0].target_scope_excerpt = scope
        with pytest.raises(SourceTargetReviewValidationError) as error:
            validate_source_target_review(batch, inventory, coverage, changed)
        assert error.value.code == "CONTEXT_RELATION_UNGROUNDED"


@pytest.mark.parametrize("scope_before_action", [True, False])
@pytest.mark.parametrize("terminal_mark", ["", "。", "；", "!", "?", ";"])
def test_context_relation_keeps_scope_before_or_inside_exact_action(
    scope_before_action: bool, terminal_mark: str,
) -> None:
    batch = _batch().model_copy(deep=True)
    action = "所有受试者自筛选期开始接受背景治疗，每次给药10 mg" + terminal_mark
    period = "自筛选期开始"
    batch.owned_units[1].excerpt = action
    batch.context_units[0].excerpt = (period + "：" if scope_before_action else "实施安排：") + action
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-02", "quoted_text": action,
                        "force": "required", "time_words": [period]}],
        "units_without_statement": ["su-01"],
    })
    coverage = [SourceStatementCoverage(
        statement_index=0, structure_unit_id="su-02",
        disposition="other_control_candidate", status="candidate_linked",
    )]
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "potential_same_requirement",
                   "target_id": "su-03", "source_action_excerpt": action,
                   "target_action_excerpt": action, "target_scope_excerpt": period,
                   "source_object_excerpt": "背景治疗", "target_object_excerpt": "背景治疗"}],
    })
    validate_source_interpretation(batch, inventory)
    validate_source_target_review(batch, inventory, coverage, review)
    assert coverage[0].status == "candidate_linked"

    wrong_period = review.model_copy(deep=True)
    wrong_period.items[0].target_scope_excerpt = "自基线期开始"
    with pytest.raises(SourceTargetReviewValidationError) as error:
        validate_source_target_review(batch, inventory, coverage, wrong_period)
    assert error.value.code == "CONTEXT_RELATION_UNGROUNDED"

    neighboring_period = batch.model_copy(deep=True)
    ordinary_action = action.replace(period, "")
    neighboring_period.owned_units[1].excerpt = f"{period}：{ordinary_action}"
    neighboring_period.context_units[0].excerpt = f"{ordinary_action}。{period}核对另一项记录"
    scoped_inventory = inventory.model_copy(deep=True)
    scoped_inventory.statements[0].quoted_text = ordinary_action
    scoped_inventory.statements[0].scope_quote = period
    scoped_review = review.model_copy(deep=True)
    scoped_review.items[0].source_action_excerpt = ordinary_action
    scoped_review.items[0].target_action_excerpt = ordinary_action
    validate_source_interpretation(neighboring_period, scoped_inventory)
    with pytest.raises(SourceTargetReviewValidationError) as error:
        validate_source_target_review(neighboring_period, scoped_inventory, coverage, scoped_review)
    assert error.value.code == "CONTEXT_RELATION_UNGROUNDED"


@pytest.mark.parametrize("boundary", ["。", "；", "!", "?", ";"])
def test_context_terminal_quote_cannot_borrow_object_or_period_from_next_clause(
    boundary: str,
) -> None:
    batch = _batch().model_copy(deep=True)
    action = "记录本次评估结果" + boundary
    batch.owned_units[1].excerpt = "筛选期：受试者" + action
    batch.context_units[0].excerpt = "筛选期：受试者" + action
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-02", "quoted_text": action,
                        "scope_quote": "筛选期", "force": "required", "time_words": ["筛选期"]}],
        "units_without_statement": ["su-01"],
    })
    coverage = [SourceStatementCoverage(
        statement_index=0, structure_unit_id="su-02",
        disposition="other_control_candidate", status="candidate_linked",
    )]
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "potential_same_requirement",
                   "target_id": "su-03", "source_action_excerpt": action,
                   "target_action_excerpt": action, "target_scope_excerpt": "筛选期",
                   "source_object_excerpt": "受试者", "target_object_excerpt": "受试者"}],
    })
    validate_source_interpretation(batch, inventory)
    validate_source_target_review(batch, inventory, coverage, review)
    for text in (
        "筛选期：" + action + "受试者接受另一项检查",
        "受试者" + action + "筛选期安排另一项检查",
        "筛选期：受试者" + action + "核查另一项结果" + boundary,
    ):
        changed_batch = batch.model_copy(deep=True)
        changed_review = review.model_copy(deep=True)
        changed_batch.context_units[0].excerpt = text
        if text.endswith("核查另一项结果" + boundary):
            changed_review.items[0].target_action_excerpt = action + "核查另一项结果" + boundary
        with pytest.raises(SourceTargetReviewValidationError) as error:
            validate_source_target_review(changed_batch, inventory, coverage, changed_review)
        assert error.value.code == "CONTEXT_RELATION_UNGROUNDED"


@pytest.mark.parametrize("action, object_text, text", [
    ("计划共招募80例", "目标人群", "筛选期：计划共招募80例目标人群"),
    ("计划招募80例目标人群", "目标人群", "筛选期：计划招募80例目标人群"),
    ("每次给药10 mg，每日1次", "背景治疗", "筛选期：背景治疗每次给药10 mg，每日1次"),
    ("计划共招募80例", "目标人群", "筛选期：计划共招募８０例 目标人群"),
])
def test_context_relation_keeps_object_in_either_position_without_claiming_coverage(
    action: str, object_text: str, text: str,
) -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[1].excerpt = text
    batch.context_units[0].excerpt = text
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-02", "quoted_text": action,
                        "force": "required", "time_words": []}],
        "units_without_statement": ["su-01"],
    })
    coverage = [SourceStatementCoverage(
        statement_index=0, structure_unit_id="su-02",
        disposition="other_control_candidate", status="candidate_linked",
    )]
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "potential_same_requirement",
                   "target_id": "su-03", "source_action_excerpt": action,
                   "target_action_excerpt": action, "target_scope_excerpt": "筛选期",
                   "source_object_excerpt": object_text, "target_object_excerpt": object_text}],
    })
    validate_source_interpretation(batch, inventory)
    validate_source_target_review(batch, inventory, coverage, review)
    assert coverage[0].status == "candidate_linked"
    for field, value in (("source_time_excerpt", "筛选期"),
                         ("target_time_excerpt", "筛选期"),
                         ("unresolved_aspects", ["对象范围尚未核实"])):
        changed = review.model_copy(deep=True)
        setattr(changed.items[0], field, value)
        with pytest.raises(SourceTargetReviewValidationError) as error:
            validate_source_target_review(batch, inventory, coverage, changed)
        assert error.value.code == "CONTEXT_RELATION_UNRESOLVED"
    for separator in "。！？；;":
        for side in ("owned_units", "context_units"):
            changed_batch = batch.model_copy(deep=True)
            unit = getattr(changed_batch, side)[1 if side == "owned_units" else 0]
            unit.excerpt = "筛选期：" + action + separator + object_text
            if object_text in action:
                unit.excerpt = "筛选期：" + object_text + separator + action.replace(object_text, "其他人群")
            with pytest.raises(SourceTargetReviewValidationError) as error:
                validate_source_target_review(changed_batch, inventory, coverage, review)
            assert error.value.code == "CONTEXT_RELATION_UNGROUNDED"


def test_source_unit_comparison_accepts_only_null_empty_differences_for_same() -> None:
    payload = {
        "version": SOURCE_UNIT_COMPARISON_VERSION,
        "statement_index": 0,
        "relation": "same_requirement",
        "target_structure_unit_id": "su-03",
        "source_action_excerpt": "每次给药10 mg，每日1次",
        "target_action_excerpt": "每次给药10 mg，每日1次",
        "source_object_excerpt": "背景治疗",
        "target_object_excerpt": "背景治疗",
        "target_scope_excerpt": "自筛选期开始",
        "differences": None,
    }
    assert SourceUnitComparison.model_validate(payload).differences == []
    payload["relation"] = "different_or_unclear"
    with pytest.raises(ValidationError):
        SourceUnitComparison.model_validate(payload)


@pytest.mark.parametrize("reported_time", [[], ["每日"]])
def test_target_review_rejects_unreported_period_even_when_model_claims_coverage(
    reported_time: list[str],
) -> None:
    batch = _batch().model_copy(deep=True)
    quote = "整个治疗期（W0~W4）每日记录用药"
    batch.owned_units[1].excerpt = quote
    batch.known_procedure_targets[0].source_excerpts = [quote]
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-02", "quoted_text": quote,
                        "force": "required", "time_words": reported_time}],
        "units_without_statement": ["su-01"],
    })
    coverage = [SourceStatementCoverage(
        statement_index=0, structure_unit_id="su-02",
        disposition="other_control_candidate", status="candidate_linked",
    )]
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "covered_by_procedure",
                   "target_id": "procedure-screening-1",
                   "source_action_excerpt": quote, "target_action_excerpt": quote,
                   "source_time_excerpt": "每日" if reported_time else None,
                   "target_time_excerpt": "每日" if reported_time else None,
                   "unresolved_aspects": []}],
    })
    validate_source_interpretation(batch, inventory)
    with pytest.raises(SourceTargetReviewValidationError) as error:
        validate_source_target_review(batch, inventory, coverage, review)
    assert error.value.code == "SOURCE_TIME_INCOMPLETE"
    assert "治疗期" in str(error.value)
    assert "W0~W4" in str(error.value)


def test_missing_history_duration_is_reported_before_target_time_mismatch() -> None:
    batch = _batch().model_copy(deep=True)
    quote = "既往情况至少2年"
    batch.owned_units[1].excerpt = quote
    batch.known_official_targets[0].source_excerpts = [quote]
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-02", "quoted_text": quote,
                        "force": "required", "time_words": []}],
        "units_without_statement": ["su-01"],
    })
    coverage = [SourceStatementCoverage(
        statement_index=0, structure_unit_id="su-02",
        disposition="other_control_candidate", status="candidate_linked",
    )]
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "covered_by_official",
                   "target_id": "EX-01", "source_action_excerpt": quote,
                   "target_action_excerpt": quote,
                   "source_time_excerpt": "2年", "target_time_excerpt": "2年",
                   "unresolved_aspects": []}],
    })
    validate_source_interpretation(batch, inventory)
    with pytest.raises(SourceTargetReviewValidationError) as error:
        validate_source_target_review(batch, inventory, coverage, review)
    assert error.value.code == "SOURCE_TIME_INCOMPLETE"
    assert "2年" in str(error.value)


@pytest.mark.parametrize("quote,target_excerpt", [
    ("每日1次记录用药", "每日1次记录用药"),
    ("治疗期每日1次记录用药", "某药：治疗期每日1次记录用药"),
])
def test_time_overclaim_rechecks_only_claimed_target_with_source_context(
    quote: str, target_excerpt: str,
) -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].excerpt += f"；某药：{quote}。筛选期及基线期不得调整剂量。"
    batch.known_procedure_targets[0].source_excerpts = [target_excerpt]
    batch.known_procedure_targets[0].visit_instance = "筛选期"
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": quote,
                        "scope_quote": "某药：", "force": "required", "time_words": ["每日1次"]}],
        "units_without_statement": ["su-02"],
    })

    def answer(decision: str) -> str:
        return SourceTargetReview.model_validate({
            "version": SOURCE_TARGET_REVIEW_VERSION,
            "items": [{"statement_index": 0, "decision": decision,
                       "target_id": "procedure-screening-1",
                       "source_action_excerpt": quote, "target_action_excerpt": quote,
                       "source_time_excerpt": "每日1次", "target_time_excerpt": "每日1次",
                       "unresolved_aspects": [] if decision == "covered_by_procedure"
                       else ["尚不能证明基线期由该筛选流程覆盖"]}],
        }).model_dump_json()

    class ReviewingTransport(_FakeTransport):
        target_prompts: list[str] = []
        scope_prompts: list[str] = []

        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.target_prompts.append(prompt)
            return ProtocolControlAgentResponse(
                session_id=f"target-{len(self.target_prompts)}",
                text=answer("covered_by_procedure" if len(self.target_prompts) == 1 else "additional_requirement"),
            )

        def correct_source_scope(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.scope_prompts.append(prompt)
            return ProtocolControlAgentResponse(session_id="scope-1", text=SourceScopeCorrection(
                version="phase5/control-source-scope-correction/v1",
                structure_unit_id="su-01", scope_quote="某药：", affected_stage=None,
                time_words=["治疗期", "每日1次"], unresolved=None,
            ).model_dump_json())

    transport = ReviewingTransport([
        ProtocolControlAgentResponse(session_id="wire-1", text=_wire(candidate=_candidate()).model_dump_json())
    ])
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert len(transport.target_prompts) == 2, [attempt.error_classes for attempt in result.attempts]
    assert len(transport.scope_prompts) == (1 if quote.startswith("治疗期") else 0)
    if transport.scope_prompts:
        assert "本次只补全 time_words" in transport.scope_prompts[0]
        assert result.source_interpretation is not None
        assert result.source_interpretation.statements[0].time_words == ["治疗期", "每日1次"]
    assert "某药：" in transport.target_prompts[1]
    assert "筛选期及基线期不得调整剂量" in transport.target_prompts[1]
    assert "本次只比较列出的目标" in transport.target_prompts[1]
    assert "procedure-screening-1" in transport.target_prompts[1]
    assert "EX-01" not in transport.target_prompts[1]
    assert result.source_target_review is not None
    assert result.source_target_review.items[0].decision == "additional_requirement"
    assert result.status == "需要核对"


def test_source_scope_correction_is_local_and_preserves_direct_time() -> None:
    batch = _batch().model_copy(deep=True)
    original = _source_inventory({
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
    original = _source_inventory({
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


def test_runner_repairs_missing_stage_time_on_one_source_statement() -> None:
    batch = _batch()
    original = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-02",
            "quoted_text": "筛选时记录末次用药日期",
            "affected_stage": "筛选时",
            "force": "required",
            "time_words": [],
        }],
        "units_without_statement": ["su-01"],
    })

    class ScopeTransport(_FakeTransport):
        source_calls = 0
        correction_calls = 0

        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.source_calls += 1
            return ProtocolControlAgentResponse(session_id="source-1", text=original.model_dump_json())

        def correct_source_scope(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.correction_calls += 1
            assert "明确阶段范围" in prompt
            return ProtocolControlAgentResponse(session_id="scope-1", text=SourceScopeCorrection(
                version="phase5/control-source-scope-correction/v1",
                structure_unit_id="su-02", scope_quote=None,
                affected_stage="筛选时", time_words=["筛选时"], unresolved=None,
            ).model_dump_json())

    transport = ScopeTransport([
        ProtocolControlAgentResponse(session_id="wire-1", text=_wire().model_dump_json())
    ])
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert transport.source_calls == 1
    assert transport.correction_calls == 1
    assert result.source_interpretation is not None
    assert result.source_interpretation.statements[0].time_words == ["筛选时"]


def test_runner_repairs_intraday_omission_locally_without_rewriting_sibling() -> None:
    batch = _batch().model_copy(deep=True)
    quote = "首次给药前30分钟内采样，给药后2小时复查"
    batch.owned_units[1].excerpt = quote
    original = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
            {"structure_unit_id": "su-01", "quoted_text": "年龄至少18岁",
             "force": "required", "time_words": []},
            {"structure_unit_id": "su-02", "quoted_text": quote,
             "force": "required", "time_words": ["给药前", "给药后"]},
        ],
        "units_without_statement": [],
    })

    class ScopeTransport(_FakeTransport):
        source_calls = 0
        correction_calls = 0

        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.source_calls += 1
            return ProtocolControlAgentResponse(session_id="source", text=original.model_dump_json())

        def correct_source_scope(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.correction_calls += 1
            assert quote in prompt
            return ProtocolControlAgentResponse(session_id="scope", text=SourceScopeCorrection(
                version="phase5/control-source-scope-correction/v1",
                structure_unit_id="su-02", scope_quote=None, affected_stage=None,
                time_words=["给药前", "30分钟", "给药后", "2小时"], unresolved=None,
            ).model_dump_json())

    transport = ScopeTransport([
        ProtocolControlAgentResponse(session_id="wire", text=_wire().model_dump_json())
    ])
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert transport.source_calls == 1
    assert transport.correction_calls == 1
    assert result.source_interpretation is not None
    assert result.source_interpretation.statements[0] == original.statements[0]
    assert result.source_interpretation.statements[1].quoted_text == quote
    assert result.source_interpretation.statements[1].time_words == [
        "给药前", "30分钟", "给药后", "2小时",
    ]


@pytest.mark.parametrize("drop_scope", [False, True])
def test_runner_preserves_scope_only_intraday_limit_during_time_correction(drop_scope) -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[1].excerpt = "给药前90分钟完成标本采集"
    original = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-02", "quoted_text": "完成标本采集",
                        "scope_quote": "给药前90分钟", "force": "required", "time_words": []}],
        "units_without_statement": ["su-01"],
    })

    class ScopeTransport(_FakeTransport):
        correction_calls = 0

        def start_source_interpretation(self, *, prompt):
            return ProtocolControlAgentResponse(session_id="source", text=original.model_dump_json())

        def correct_source_scope(self, *, prompt):
            self.correction_calls += 1
            assert "scope_quote 和 affected_stage" in prompt
            return ProtocolControlAgentResponse(session_id="correction", text=SourceScopeCorrection(
                version="phase5/control-source-scope-correction/v1",
                structure_unit_id="su-02", scope_quote=None if drop_scope else "给药前90分钟",
                affected_stage=None, time_words=[] if drop_scope else ["给药前90分钟"], unresolved=None,
            ).model_dump_json())

    transport = ScopeTransport([
        ProtocolControlAgentResponse(session_id="wire", text=_wire().model_dump_json())
    ])
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert transport.correction_calls == 1
    if drop_scope:
        assert result.status == "需要核对"
        assert result.final_output is None
        assert any("不得改变已核原文范围" in issue for attempt in result.attempts for issue in attempt.issues)
    else:
        assert result.source_interpretation is not None
        assert result.source_interpretation.statements[0].scope_quote == "给药前90分钟"
        assert result.source_interpretation.statements[0].time_words == ["给药前90分钟"]


def test_source_stage_requires_complete_original_time_word() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[1].excerpt = "筛选期记录末次用药日期"
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-02", "quoted_text": "筛选期记录末次用药日期",
            "affected_stage": "筛选期", "force": "required", "time_words": ["筛选"],
        }],
        "units_without_statement": ["su-01"],
    })
    with pytest.raises(SourceInterpretationValidationError) as error:
        validate_source_interpretation(batch, inventory)
    assert error.value.code == "SOURCE_STAGE_TIME_MISSING"
    inventory.statements[0].time_words = ["筛选期"]
    validate_source_interpretation(batch, inventory)


def test_runner_corrects_study_phase_stage_without_rereading_source() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].excerpt = "Ⅲ期计划纳入164例受试者"
    original = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-01", "quoted_text": "Ⅲ期计划纳入164例受试者",
            "affected_stage": "Ⅲ期", "force": "required", "time_words": ["Ⅲ期"],
        }],
        "units_without_statement": ["su-02"],
    })

    class StageTransport(_FakeTransport):
        source_calls = 0
        correction_calls = 0

        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.source_calls += 1
            return ProtocolControlAgentResponse(session_id="phase-source", text=original.model_dump_json())

        def correct_source_scope(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.correction_calls += 1
            assert "方案期别" in prompt
            return ProtocolControlAgentResponse(session_id="phase-correction", text=json.dumps({
                "version": "phase5/control-source-scope-correction/v1",
                "structure_unit_id": "su-01", "scope_quote": None,
                "affected_stage": "Ⅲ期", "time_words": [], "unresolved": None,
            }, ensure_ascii=False))

    transport = StageTransport([
        ProtocolControlAgentResponse(session_id="phase-wire", text=_wire().model_dump_json())
    ])
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert transport.source_calls == 1
    assert transport.correction_calls == 1
    assert result.source_interpretation is not None
    assert result.source_interpretation.statements[0].quoted_text == original.statements[0].quoted_text
    assert result.source_interpretation.statements[0].affected_stage is None
    assert result.source_interpretation.statements[0].time_words == []


def test_source_target_review_selects_unexpressed_enrollment_requirements() -> None:
    inventory = _source_inventory({
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


@pytest.mark.parametrize("capacity", ["unavailable", "exhausted"])
def test_source_target_review_preserves_uncovered_statement_as_failure(monkeypatch, capacity) -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].excerpt = "其他控制：年龄至少18岁；筛选前说明年龄记录来源"
    batch.known_official_targets[0].source_excerpts = ["年龄至少18岁"]
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
                {"structure_unit_id": "su-01", "quoted_text": "筛选前说明年龄记录来源", "force": "required", "time_words": ["筛选前"]},
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

    if capacity == "exhausted":
        monkeypatch.setattr("app.agents.protocol_control_deconstructor.MAX_SOURCE_INSERT_REPAIRS", 0)
    result = ProtocolControlAgentRunner().run(
        batch,
        ReviewingTransport([ProtocolControlAgentResponse(session_id="wire-1", text=_wire(candidate=_candidate()).model_dump_json())]),
        output_validator=(lambda _output: None) if capacity == "exhausted" else None,
    )
    assert result.status == "需要核对"
    assert result.final_output is None
    assert result.source_target_review == claim
    expected = ("SOURCE_REQUIREMENT_CONSUMER_UNAVAILABLE" if capacity == "unavailable"
                else "SOURCE_REQUIREMENT_INSERTION_LIMIT_REACHED")
    assert result.attempts[-1].error_classes == [expected]
    assert result.attempts[-1].outcome == "publication_invalid"
    detail = result.attempts[-1].error_detail
    assert detail["code"] == expected
    assert detail["statement_ids"] == [0]
    assert detail["source_refs"] == ["span:01"]
    assert detail["review_snapshot"] == claim.model_dump(mode="json")
    assert result.source_interpretation.statements[0].unresolved == []
    assert result.attempts[-2].output is not None
    assert result.partial_wire == _wire(candidate=_candidate())

    batch.known_official_targets[0].source_excerpts = ["筛选前说明年龄记录来源"]
    claim = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "covered_by_official", "target_id": "EX-01",
                   "source_action_excerpt": "说明年龄记录来源",
                   "target_action_excerpt": "说明年龄记录来源",
                   "source_time_excerpt": "筛选前", "target_time_excerpt": "筛选前",
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
    inventory = _source_inventory({
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
            assert '"code":"TARGET_TIME_INCOMPLETE"' in prompt
            assert '"json_path":"/items/0/target_time_excerpt"' in prompt
            assert '"rejected_item":' in prompt
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
    review_issue = next(
        attempt.error_detail for attempt in result.attempts
        if attempt.error_detail is not None
    )
    assert review_issue["code"] == "TARGET_TIME_INCOMPLETE"
    assert review_issue["statement_id"] == 0
    assert review_issue["json_path"] == "/items/0/target_time_excerpt"
    assert review_issue["source_refs"]
    assert any("SOURCE_TARGET_REVIEW_INVALID" in attempt.error_classes for attempt in result.attempts)


@pytest.mark.parametrize("provide_grounded_relation", [True, False])
def test_context_relation_repair_receives_rejection_and_preserves_failed_scope(
    provide_grounded_relation: bool,
) -> None:
    batch = _batch().model_copy(deep=True)
    action = "每次给药10 mg，每日1次"
    batch.owned_units[0].excerpt = f"其他控制：年龄至少18岁；背景治疗：{action}"
    batch.context_units[0].excerpt = f"筛选期：背景治疗：{action}"
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": action,
                        "force": "required", "time_words": ["每日1次"]}],
        "units_without_statement": ["su-02"],
    })
    rejected = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "potential_same_requirement",
                   "target_id": None, "source_action_excerpt": action,
                   "target_action_excerpt": None, "target_scope_excerpt": "筛选期",
                   "source_object_excerpt": "背景治疗", "target_object_excerpt": "背景治疗"}],
    })
    corrected = rejected.model_copy(deep=True)
    corrected.items[0].target_id = "su-03"
    corrected.items[0].target_action_excerpt = action

    class ReviewingTransport(_FakeTransport):
        calls = 0

        def start_source_interpretation(self, *, prompt: str):
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt: str):
            self.calls += 1
            if self.calls == 2:
                assert '"code":"CONTEXT_RELATION_UNGROUNDED"' in prompt
                assert '"json_path":"/items/0/target_id"' in prompt
                assert '"target_id":null' in prompt
                assert "结构化拒绝反馈" in prompt
                assert "不猜来源编号、不改来源功能分类" in prompt
            answer = corrected if self.calls == 2 and provide_grounded_relation else rejected
            return ProtocolControlAgentResponse(session_id=f"target-{self.calls}", text=answer.model_dump_json())

    original = _wire(candidate=_candidate())
    transport = ReviewingTransport([
        ProtocolControlAgentResponse(session_id="wire-1", text=original.model_dump_json())
    ])
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert transport.calls == 2
    assert result.partial_wire == original
    if provide_grounded_relation:
        assert result.status == "待跨章核验"
        assert result.final_output is not None
        assert result.source_target_review == corrected
    else:
        assert result.status == "需要核对"
        assert result.final_output is None
        assert result.attempts[-1].error_detail["code"] == "CONTEXT_RELATION_UNGROUNDED"
        assert result.attempts[-1].error_detail["statement_id"] == 0


@pytest.mark.parametrize("fault", [None, "unproved", "scope_escape", "transport"])
def test_target_review_repairs_distinct_items_without_rereading_valid_sibling(fault) -> None:
    batch = _batch().model_copy(deep=True)
    actions = ["每次给药10 mg，每日1次", "每次检查并记录治疗用法", "每次随访并记录治疗依从性"]
    batch.owned_units[0].excerpt = "其他控制：年龄至少18岁；" + "；".join(
        f"背景治疗：{action}" for action in actions
    )
    batch.context_units[0].excerpt = "；".join(
        f"筛选期：背景治疗：{action}" for action in actions
    )
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": action,
                        "force": "required", "time_words": ["每日1次"] if index == 0 else []}
                       for index, action in enumerate(actions)],
        "units_without_statement": ["su-02"],
    })
    expected = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": index, "decision": "potential_same_requirement",
                   "target_id": "su-03", "source_action_excerpt": action,
                   "target_action_excerpt": action, "target_scope_excerpt": "筛选期",
                   "source_object_excerpt": "背景治疗", "target_object_excerpt": "背景治疗"}
                  for index, action in enumerate(actions)],
    })
    initial = expected.model_copy(deep=True)
    for item in initial.items[1:]:
        item.target_id = None
        item.target_action_excerpt = None
    original = _wire(candidate=_candidate())

    class ReviewingTransport(_FakeTransport):
        calls = 0
        prompts = []

        def start_source_interpretation(self, *, prompt):
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt):
            self.calls += 1
            self.prompts.append(prompt)
            if self.calls == 1:
                answer = initial
            else:
                index = self.calls - 1
                assert index in {1, 2}
                assert f'"statement_index":{index}' in prompt
                answer = SourceTargetReview(version=SOURCE_TARGET_REVIEW_VERSION,
                                            items=[expected.items[index].model_copy(deep=True)])
                if index == 2:
                    if fault == "transport":
                        raise OSError("isolated transport fault")
                    if fault == "unproved":
                        answer.items[0].target_id = None
                        answer.items[0].target_action_excerpt = None
                    if fault == "scope_escape":
                        answer.items.append(expected.items[0])
            return ProtocolControlAgentResponse(session_id=f"target-{self.calls}",
                                                text=answer.model_dump_json())

    transport = ReviewingTransport([
        ProtocolControlAgentResponse(session_id="wire-1", text=original.model_dump_json()),
    ])
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert transport.calls == 3
    assert result.partial_wire == original
    assert result.source_interpretation == inventory
    invalid = [attempt for attempt in result.attempts
               if attempt.error_detail and attempt.error_detail.get("review_snapshot_kind")
               == "assembled_pending_review"]
    assert [attempt.error_detail["statement_id"] for attempt in invalid] == [1, 2]
    second_snapshot = invalid[1].error_detail["review_snapshot"]
    assert second_snapshot["items"][0] == expected.items[0].model_dump(mode="json")
    assert second_snapshot["items"][1] == expected.items[1].model_dump(mode="json")
    if fault is None:
        assert result.status == "待跨章核验"
        assert result.source_target_review == expected
        assert result.final_output is not None
    else:
        assert result.status == "需要核对"
        assert result.final_output is None
        assert result.source_target_review is not None
        assert result.source_target_review.items == expected.items[:2]
        from app.services.protocol_control_execution import _resumable_saved_source_review

        saved = json.loads(result.model_dump_json())
        resumed = _resumable_saved_source_review(batch, inventory, saved)
        assert resumed.state == "partially_reused"
        assert resumed.review == result.source_target_review
        assert [entry.statement_index for entry in resumed.coverage] == [0, 1]
        with pytest.raises(SourceTargetReviewValidationError):
            validate_source_target_review(
                batch, inventory, result.source_statement_coverage, resumed.review,
            )

        class ResumeTransport(_FakeTransport):
            review_calls = 0

            def start_source_target_review(self, *, prompt):
                self.review_calls += 1
                source_rows = json.loads(prompt.split("待核陈述：", 1)[1].split("\n", 1)[0])
                assert [row["statement_index"] for row in source_rows] == [2]
                return ProtocolControlAgentResponse(
                    session_id="resumed-target-2",
                    text=SourceTargetReview(version=SOURCE_TARGET_REVIEW_VERSION,
                                            items=[expected.items[2]]).model_dump_json(),
                )

        resume_transport = ResumeTransport([])
        recovered = ProtocolControlAgentRunner().run(
            batch, resume_transport, resume_wire=result.partial_wire,
            resume_source_interpretation=inventory, resume_session_id="wire-1",
            resume_source_target_review=resumed.review,
            resume_source_statement_coverage=resumed.coverage,
            output_validator=lambda _output: None,
        )
        assert resume_transport.review_calls == 1
        assert recovered.status == "待跨章核验", [a.issues for a in recovered.attempts]
        assert recovered.final_output is not None
        assert recovered.source_target_review == expected
        assert result.source_target_review.items == expected.items[:2]
        last = result.attempts[-1]
        if fault == "transport":
            assert last.error_classes == ["SOURCE_TARGET_REVIEW_TRANSPORT_FAILED"]
            assert last.outcome == "transport_failed"
            assert last.raw_output_text is None
        else:
            assert last.error_detail["code"] == (
                "REVIEW_SCOPE_INVALID" if fault == "scope_escape" else "CONTEXT_RELATION_UNGROUNDED"
            )
            assert last.error_detail["review_snapshot_kind"] == "rejected_local_correction"
            assert last.error_detail["review_snapshot"]["items"][0]["statement_index"] == 2


@pytest.mark.parametrize("mutation", ["stale_item", "partial", "duplicate", "foreign", "bad_coverage"])
def test_saved_review_recovery_checks_each_item_without_accepting_partial_scope(mutation) -> None:
    from app.services.protocol_control_execution import _resumable_saved_source_review

    batch, inventory, relations, _first, _second = _context_relation_example()
    original = _wire(candidate=_candidate())
    coverage = source_statement_coverage(batch, inventory, original)
    review = SourceTargetReview(version=SOURCE_TARGET_REVIEW_VERSION, items=relations).model_copy(deep=True)
    if mutation == "stale_item":
        review.items[1].target_action_excerpt = "目标原文不存在的要求"
    elif mutation == "partial":
        review.items = review.items[:1]
    elif mutation == "duplicate":
        review.items.append(review.items[0].model_copy(deep=True))
    elif mutation == "foreign":
        review.items[1].statement_index = 99
    elif mutation == "bad_coverage":
        coverage[1] = coverage[1].model_copy(update={"structure_unit_id": "foreign-source"})
    saved = {"source_target_review": review.model_dump(mode="json"),
             "source_statement_coverage": [entry.model_dump(mode="json") for entry in coverage]}
    before = json.dumps(saved, sort_keys=True)
    restored = _resumable_saved_source_review(batch, inventory, saved)
    if mutation in {"stale_item", "partial"}:
        assert restored.state == "partially_reused"
        assert restored.review.items == [relations[0]]
        with pytest.raises(SourceTargetReviewValidationError):
            validate_source_target_review(batch, inventory, coverage, restored.review)
    else:
        assert restored.state == "refresh_required"
        assert restored.review is None
    assert json.dumps(saved, sort_keys=True) == before


def test_saved_review_validator_bug_is_not_a_reason_to_reread_models(monkeypatch) -> None:
    import app.agents.protocol_control_source_interpretation as source_module
    from app.services.protocol_control_execution import _resumable_saved_source_review
    from app.workflow.errors import StepFailure

    batch, inventory, relations, _first, _second = _context_relation_example()
    coverage = source_statement_coverage(batch, inventory, _wire(candidate=_candidate()))
    saved = {"source_target_review": SourceTargetReview(
        version=SOURCE_TARGET_REVIEW_VERSION, items=relations,
    ).model_dump(mode="json"),
        "source_statement_coverage": [entry.model_dump(mode="json") for entry in coverage]}

    def broken_validator(*args, **kwargs):
        raise TypeError("injected validator implementation fault")

    monkeypatch.setattr(source_module, "validate_source_target_review", broken_validator)
    with pytest.raises(StepFailure) as failed:
        _resumable_saved_source_review(batch, inventory, saved)
    assert failed.value.error_code == "PROTOCOL_CONTROL_SOURCE_REVIEW_VALIDATION_FAILED"
    assert failed.value.retryable is False


@pytest.mark.parametrize("kind", ["time_scope", "frequency_comparison"])
@pytest.mark.parametrize("fault", ["transport", "identity", "budget", "interrupted"])
def test_adjacent_target_repair_transport_fault_does_not_borrow_previous_response(kind, fault) -> None:
    batch = _batch().model_copy(deep=True)
    quote = ("整个治疗期（W0~W4）每日记录用药" if kind == "time_scope"
             else "每日1次记录用药情况")
    batch.owned_units[0].excerpt = "其他控制：年龄至少18岁；" + quote
    batch.known_procedure_targets[0].source_excerpts = [quote]
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": quote,
                        "force": "required",
                        "time_words": [] if kind == "time_scope" else ["每日1次"]}],
        "units_without_statement": ["su-02"],
    })
    claim = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "covered_by_procedure",
                   "target_id": "procedure-screening-1", "source_action_excerpt": quote,
                   "target_action_excerpt": quote,
                   "source_time_excerpt": None if kind == "time_scope" else "每日1次",
                   "target_time_excerpt": None if kind == "time_scope" else "每日1次"}],
    })
    original = _wire(candidate=_candidate())

    class ReviewingTransport(_FakeTransport):
        target_calls = 0
        repair_calls = 0

        def start_source_interpretation(self, *, prompt):
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt):
            self.target_calls += 1
            assert self.target_calls == 1
            return ProtocolControlAgentResponse(session_id="target-1", text=claim.model_dump_json())

        def correct_source_scope(self, *, prompt):
            assert kind == "time_scope"
            self.repair_calls += 1
            if fault != "transport":
                _raise_wrapped_terminal_failure(fault)
            raise OSError("isolated scope service fault")

        def start_source_unit_comparison(self, *, prompt):
            assert kind == "frequency_comparison"
            self.repair_calls += 1
            if fault != "transport":
                _raise_wrapped_terminal_failure(fault)
            raise OSError("isolated comparison service fault")

    transport = ReviewingTransport([
        ProtocolControlAgentResponse(session_id="wire-1", text=original.model_dump_json()),
    ])
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert transport.target_calls == transport.repair_calls == 1
    assert result.status == "需要核对"
    assert result.final_output is None
    assert result.partial_wire == original
    assert result.source_interpretation == inventory
    expected = {"transport": "SOURCE_TARGET_REVIEW_TRANSPORT_FAILED",
                "identity": "MODEL_IDENTITY_INVALID", "budget": "LOGICAL_BUDGET_EXHAUSTED",
                "interrupted": "FLOW_COMPLETION_UNCERTAIN"}[fault]
    assert result.attempts[-1].error_classes == [expected]
    assert result.attempts[-1].outcome == "transport_failed"
    assert result.attempts[-1].raw_output_text is None


def test_missing_target_reviewer_is_capability_failure_not_retryable_transport() -> None:
    batch = _batch().model_copy(deep=True)
    quote = "完成并记录背景治疗核对"
    batch.owned_units[0].excerpt = "其他控制：年龄至少18岁；" + quote
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": quote,
                        "force": "required", "time_words": []}],
        "units_without_statement": ["su-02"],
    })

    class SourceOnlyTransport(_FakeTransport):
        def start_source_interpretation(self, *, prompt):
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

    original = _wire(candidate=_candidate())
    result = ProtocolControlAgentRunner().run(batch, SourceOnlyTransport([
        ProtocolControlAgentResponse(session_id="wire-1", text=original.model_dump_json()),
    ]))
    assert result.status == "需要核对" and result.final_output is None
    assert result.partial_wire == original
    assert result.attempts[-1].error_classes == ["SOURCE_TARGET_REVIEW_UNAVAILABLE"]
    assert result.attempts[-1].raw_output_text is None


@pytest.mark.parametrize("focused_decision, expected_status", [
    ("covered_by_official", "已解析"),
    ("unresolved", "需要核对"),
])
def test_candidate_linked_unresolved_target_gets_one_source_bound_read(
    focused_decision: str, expected_status: str,
) -> None:
    batch = _batch().model_copy(deep=True)
    quote = "筛选前说明年龄记录来源"
    batch.owned_units[0].excerpt = f"其他控制：年龄至少18岁；{quote}"
    batch.known_official_targets[0].source_excerpts = [quote]
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": quote,
                        "force": "required", "time_words": ["筛选前"]}],
        "units_without_statement": ["su-02"],
    })

    def answer(decision: str) -> str:
        covered = decision == "covered_by_official"
        return SourceTargetReview.model_validate({
            "version": SOURCE_TARGET_REVIEW_VERSION,
            "items": [{"statement_index": 0, "decision": decision,
                       "target_id": "EX-01" if covered else None,
                       "source_action_excerpt": "说明年龄记录来源",
                       "target_action_excerpt": "说明年龄记录来源" if covered else None,
                       "source_time_excerpt": "筛选前", "target_time_excerpt": "筛选前" if covered else None,
                       "unresolved_aspects": [] if covered else ["尚未确认对应目标"],
                       }],
        }).model_dump_json()

    class ReviewingTransport(_FakeTransport):
        calls = 0

        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.calls += 1
            if self.calls == 2:
                assert "linked_procedure_target_ids 为空也不代表" in prompt
            return ProtocolControlAgentResponse(
                session_id=f"target-{self.calls}",
                text=answer("unresolved" if self.calls == 1 else focused_decision),
            )

    transport = ReviewingTransport([
        ProtocolControlAgentResponse(
            session_id="wire-1", text=_wire(candidate=_candidate()).model_dump_json(),
        )
    ])
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert transport.calls == 2
    assert result.status == expected_status
    assert result.source_target_review is not None
    assert result.source_target_review.items[0].decision == focused_decision
    if focused_decision == "unresolved":
        assert result.attempts[-1].error_classes == ["SOURCE_TARGET_REVIEW_UNRESOLVED"]
        assert result.attempts[-1].error_detail["statement_ids"] == [0]
        assert result.attempts[-1].error_detail["source_refs"] == ["span:01"]
        assert result.attempts[-1].outcome == "publication_invalid"
        assert result.source_interpretation.statements[0].unresolved == []
        assert result.partial_wire == _wire(candidate=_candidate())


@pytest.mark.parametrize("kind", ["transport", "schema", "source", "identity", "budget", "interrupted"])
def test_focused_target_failure_preserves_actual_response_and_checked_baseline(kind: str) -> None:
    batch = _batch().model_copy(deep=True)
    quote = "筛选前说明年龄记录来源"
    batch.owned_units[0].excerpt = f"其他控制：年龄至少18岁；{quote}"
    batch.known_official_targets[0].source_excerpts = [quote]
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": quote,
                        "force": "required", "time_words": ["筛选前"]}],
        "units_without_statement": ["su-02"],
    })
    initial = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "unresolved",
                   "source_action_excerpt": "说明年龄记录来源",
                   "source_time_excerpt": "筛选前", "unresolved_aspects": ["尚未确认对应目标"]}],
    })
    invalid = initial.model_copy(deep=True)
    invalid.items[0].decision = "covered_by_official"
    invalid.items[0].target_id = "EX-01"
    invalid.items[0].target_action_excerpt = "原文没有的动作"
    invalid.items[0].target_time_excerpt = "筛选前"
    invalid.items[0].unresolved_aspects = []
    raw = "{invalid-json" if kind == "schema" else invalid.model_dump_json()

    class Transport(_FakeTransport):
        calls = 0

        def start_source_interpretation(self, *, prompt):
            return ProtocolControlAgentResponse(session_id="source", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt):
            self.calls += 1
            if self.calls == 1:
                return ProtocolControlAgentResponse(session_id="initial", text=initial.model_dump_json())
            assert self.calls == 2
            if kind in {"identity", "budget", "interrupted"}:
                _raise_wrapped_terminal_failure(kind)
            if kind == "transport":
                raise OSError("isolated focused service failure")
            return ProtocolControlAgentResponse(session_id="rejected-focused", text=raw)

    original = _wire(candidate=_candidate())
    transport = Transport([ProtocolControlAgentResponse(session_id="wire", text=original.model_dump_json())])
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert transport.calls == 2
    assert result.status == "需要核对" and result.final_output is None
    assert result.partial_wire == original and result.source_interpretation == inventory
    assert result.source_target_review == initial
    assert result.source_statement_coverage == source_statement_coverage(batch, inventory, original)
    failure = result.attempts[-1]
    transport_failed = kind in {"transport", "identity", "budget", "interrupted"}
    terminal_code = {"identity": "MODEL_IDENTITY_INVALID", "budget": "LOGICAL_BUDGET_EXHAUSTED",
                     "interrupted": "FLOW_COMPLETION_UNCERTAIN"}.get(kind)
    assert failure.error_classes == [terminal_code or "SOURCE_TARGET_FOCUSED_TRANSPORT_FAILED" if transport_failed
                                     else "SOURCE_TARGET_FOCUSED_SCHEMA_INVALID" if kind == "schema"
                                     else "SOURCE_TARGET_FOCUSED_INVALID"]
    assert failure.outcome == ("transport_failed" if transport_failed
                               else "schema_invalid" if kind == "schema" else "publication_invalid")
    assert failure.raw_output_text == (None if transport_failed else raw)
    assert failure.raw_output_chars == (None if transport_failed else len(raw))
    assert failure.session_id == ("wrapped-reader" if terminal_code else "wire" if transport_failed else "rejected-focused")
    if not transport_failed:
        assert failure.raw_output_sha256 == hashlib.sha256(raw.encode()).hexdigest()
    detail = failure.error_detail
    assert detail["statement_id"] == 0 and detail["code"]
    assert detail["failure_class"] == failure.error_classes[0]
    assert (detail["validation_code"] is not None) == (kind == "source")
    assert detail["review_snapshot_kind"] == "rejected_focused_review"
    assert detail["review_snapshot"] == (invalid.model_dump(mode="json") if kind == "source" else None)
    assert detail["linked_candidate_indexes"] == [0]
    assert "SOURCE_TARGET_REVIEW_UNRESOLVED" not in failure.error_classes


def test_source_target_addition_enters_bounded_repair_without_accepting_unchanged_wire() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].excerpt = "其他控制：年龄至少18岁；筛选前说明年龄记录来源"
    inventory = _source_inventory({
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
    assert result.partial_wire == _wire(candidate=_candidate())
    assert any("SOURCE_TARGET_ADDITIONAL_REQUIREMENT" in attempt.error_classes
               for attempt in result.attempts)
    assert "来源限定补入" in transport.prompts[-1]
    assert "较早执行访视的补充关系" in transport.prompts[-1]
    assert any("REPAIR_SCOPE_ESCAPE" in attempt.error_classes
               for attempt in result.attempts)


@pytest.mark.parametrize("restored", [False, True])
def test_cited_but_unexpressed_candidate_does_not_request_duplicate_insert(restored: bool) -> None:
    batch = _batch()
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": "年龄至少18岁",
                        "force": "required", "time_words": []}],
        "units_without_statement": ["su-02"],
    })
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "additional_requirement", "target_id": None,
                   "source_action_excerpt": "年龄至少18岁", "target_action_excerpt": None,
                   "source_time_excerpt": None, "target_time_excerpt": None,
                   "unresolved_aspects": ["已有候选改写了原文限定"]}],
    })

    class Transport(_FakeTransport):
        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="source", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            if restored:
                pytest.fail("经当前校验的保存核对不得重读")
            return ProtocolControlAgentResponse(session_id="target", text=review.model_dump_json())

    original = _wire(candidate=_candidate())
    transport = Transport([] if restored else [ProtocolControlAgentResponse(
        session_id="wire", text=original.model_dump_json(),
    )])
    result = ProtocolControlAgentRunner().run(
        batch, transport, output_validator=lambda _output: None,
        **({"resume_wire": original, "resume_source_interpretation": inventory,
            "resume_session_id": "wire", "resume_source_target_review": review,
            "resume_source_statement_coverage": source_statement_coverage(batch, inventory, original)}
           if restored else {}),
    )
    assert result.status == "需要核对"
    assert result.final_output is None
    assert result.partial_wire == original
    assert len(transport.prompts) == (0 if restored else 1)
    failure = next(attempt for attempt in result.attempts
                   if "SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED" in attempt.error_classes)
    assert failure.error_detail == {
        "review_proof_origin": "saved_source_target_review" if restored else "model_response",
        "review_proof_sha256": hashlib.sha256(review.model_dump_json().encode()).hexdigest(),
        "code": "SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED",
        "statement_ids": [0],
        "candidate_indexes": [0],
        "source_refs": batch.owned_units[0].source_span_ids,
        "retry_class": "source_semantic_review",
        "affected_dependents": [0],
    }
    if restored:
        assert failure.session_id == "wire"
        assert failure.raw_output_chars is None
        assert failure.raw_output_text is None


def test_source_candidate_alignment_closes_only_verified_existing_candidate() -> None:
    from app.agents.protocol_control_candidate_alignment import SOURCE_CANDIDATE_ALIGNMENT_VERSION
    from app.services.protocol_control_execution import _validate_saved_source_review

    batch = _batch()
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": "年龄至少18岁",
                        "force": "required", "time_words": []}],
        "units_without_statement": ["su-02"],
    })
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "additional_requirement", "target_id": None,
                   "source_action_excerpt": "年龄至少18岁", "target_action_excerpt": None,
                   "source_time_excerpt": None, "target_time_excerpt": None,
                   "unresolved_aspects": ["既有目录未覆盖"]}],
    })

    class Transport(_FakeTransport):
        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="source", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="target", text=review.model_dump_json())

        def start_source_candidate_alignment(self, *, prompt: str) -> ProtocolControlAgentResponse:
            assert "年龄至少18岁" in prompt
            return ProtocolControlAgentResponse(session_id="alignment", text=json.dumps({
                "version": SOURCE_CANDIDATE_ALIGNMENT_VERSION,
                "items": [{"statement_index": 0, "candidate_index": 0,
                           "decision": "fully_expressed", "source_excerpt": "年龄至少18岁",
                           "candidate_atom_quotes": ["年龄达到18岁"],
                           "unresolved_dimensions": []}],
            }, ensure_ascii=False))

    candidate = _candidate().model_copy(update={"exception_expression": None})
    wire = _wire(candidate=candidate)
    result = ProtocolControlAgentRunner().run(
        batch, Transport([ProtocolControlAgentResponse(
            session_id="wire", text=wire.model_dump_json(),
        )]), output_validator=lambda _output: None,
    )
    assert result.status == "已解析"
    assert result.final_output is not None
    assert result.source_candidate_alignment is not None
    _validate_saved_source_review(batch, result)


@pytest.mark.parametrize("invalid_insert,drop_target", [(False, False), (True, False), (True, True)])
def test_source_target_addition_can_publish_only_after_source_bound_insert(invalid_insert, drop_target) -> None:
    batch = _batch().model_copy(deep=True)
    quote = "须记录年龄资料来源"
    batch.owned_units[0].excerpt = f"其他控制：{quote}"
    inventory = _source_inventory({
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
    candidate["cross_source_relations"] = [{
        "kind": "supplementary_requirement", "external_target_kind": "required_procedure",
        "external_target_id": "procedure-screening-1", "candidate_side": "left",
        "affected_workflow_stage_id": "stage:screening:one", "notes": None,
    }]

    class InsertingTransport(_FakeTransport):
        insert_calls = 0

        def continue_candidates(self, *, session_id: str, prompt: str) -> ProtocolControlAgentResponse:
            response = self.continue_candidate(session_id=session_id, prompt=prompt)
            return response.model_copy(update={"text": json.dumps({
                "candidate_drafts": [json.loads(response.text)["candidate_draft"]],
            }, ensure_ascii=False)})

        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="target-1", text=review.model_dump_json())

        def continue_candidate(self, *, session_id: str, prompt: str) -> ProtocolControlAgentResponse:
            self.prompts.append(prompt)
            self.insert_calls += 1
            if self.insert_calls == 1:
                assert "研究日区间标注首先是冻结访视的范围" in prompt
                assert "指向官方入排条款的关系须填 null" in prompt
            else:
                assert "这是遗漏要求的来源限定补入" not in prompt
            proposed = deepcopy(candidate)
            if invalid_insert and self.insert_calls == 1:
                proposed["review_node_bindings"][0]["role"] = "early_attention"
            if drop_target and self.insert_calls > 1:
                proposed["cross_source_relations"] = []
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"candidate_draft": proposed}, ensure_ascii=False),
            )

    initial = _wire()
    initial.dispositions[0] = ProtocolControlAgentWireDisposition(
        structure_unit_id="su-01", disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
        linked_official_code=None, linked_procedure_catalog_item_id="procedure-screening-1",
        linked_procedure_catalog_item_ids=[], notes=None,
    )
    transport = InsertingTransport([
        ProtocolControlAgentResponse(session_id="wire-1", text=initial.model_dump_json()),
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        batch, transport, output_validator=lambda _output: None,
    )
    if drop_target:
        assert result.status == "需要核对"
        assert result.final_output is None
        assert result.partial_wire == initial
        assert "REPAIR_SCOPE_ESCAPE" in result.attempts[-1].error_classes
        return
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert result.final_output is not None
    assert len(result.final_output.candidates) == 1
    assert transport.insert_calls == (2 if invalid_insert else 1)
    assert result.partial_wire.candidate_drafts == [ProtocolControlAgentWireCandidate.model_validate(candidate)]
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
    interpretation = _source_inventory({
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


@pytest.mark.parametrize("force", ["required", "descriptive"])
def test_schedule_row_with_enrollment_columns_cannot_be_discarded_as_post_treatment(
    monkeypatch: pytest.MonkeyPatch,
    force: str,
) -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].excerpt = "检查评估 | X | X | X"
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{"structure_unit_id": "su-01", "quoted_text": batch.owned_units[0].excerpt,
                        "force": force, "time_words": []}],
        "units_without_statement": ["su-02"],
    })
    monkeypatch.setattr(
        "app.agents.protocol_control_deconstructor.schedule_column_links",
        lambda _batch, _unit_id, _quote: [{
            "column_index": 1, "cell_source_ref": "generic.body.p1",
            "header_source_refs": ["generic.body.p1"], "visit_instance": "screening-1",
            "boundary_side": "at_or_before_baseline",
            "procedure_target_id": "procedure-screening-1",
        }],
    )
    wire = _wire().model_copy(deep=True)
    wire.dispositions[0].disposition = StructureUnitDispositionKind.POST_TREATMENT_EXECUTION
    with pytest.raises(ProtocolControlAgentWireValidationError) as rejected:
        source_statement_coverage(batch, inventory, wire)
    assert rejected.value.code == "SCHEDULE_ENROLLMENT_COLUMN_DISCARDED"
    assert rejected.value.structure_unit_ids == ("su-01",)

    wire.dispositions[0].disposition = StructureUnitDispositionKind.REQUIRED_PROCEDURE
    wire.dispositions[0].linked_procedure_catalog_item_id = "procedure-screening-1"
    assert source_statement_coverage(batch, inventory, wire)[0].linked_procedure_target_ids == [
        "procedure-screening-1"
    ]


def test_single_source_id_copy_error_is_rebound_only_when_unambiguous() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units = batch.owned_units[:1]
    batch.owned_structure_unit_ids = ["su-01"]
    batch.owned_source_span_ids = ["span:01"]
    wire = ProtocolControlAgentWire(
        wire_version=CONTROL_AGENT_WIRE_VERSION,
        dispositions=[ProtocolControlAgentWireDisposition(
            structure_unit_id="su-0l", disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
            linked_official_code=None, linked_procedure_catalog_item_id="procedure-screening-1",
            linked_procedure_catalog_item_ids=[], notes="按冻结访视核对",
        )],
        candidate_drafts=[],
    )
    accepted = validate_protocol_control_agent_wire(wire, batch)
    assert accepted.dispositions[0].structure_unit_id == "su-01"
    assert wire.dispositions[0].structure_unit_id == "su-0l"

    unrelated = wire.model_copy(deep=True)
    unrelated.dispositions[0].structure_unit_id = "su-zz"
    with pytest.raises(ProtocolControlAgentWireValidationError, match="PARTIAL_BATCH"):
        validate_protocol_control_agent_wire(unrelated, batch)

    with_candidate = wire.model_copy(deep=True)
    with_candidate.candidate_drafts = [_candidate()]
    with pytest.raises(ProtocolControlAgentWireValidationError, match="PARTIAL_BATCH"):
        validate_protocol_control_agent_wire(with_candidate, batch)


def test_trial_phase_heading_remains_scope_not_subject_time() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].excerpt = "Ⅲ期：筛选/导入期开展检查评估"
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-01", "quoted_text": "筛选/导入期开展检查评估",
            "scope_quote": "Ⅲ期：", "affected_stage": "筛选/导入期",
            "force": "required", "time_words": ["Ⅲ期", "筛选/导入期"],
        }],
        "units_without_statement": ["su-02"],
    })
    assert is_study_phase_label("Ⅲ期")
    assert not is_study_phase_label("治疗期")
    with pytest.raises(SourceInterpretationValidationError) as rejected:
        validate_source_interpretation(batch, inventory)
    assert rejected.value.code == "STUDY_PHASE_NOT_VISIT_TIME"

    corrected = apply_source_scope_correction(batch, inventory, 0, SourceScopeCorrection(
        version="phase5/control-source-scope-correction/v1",
        structure_unit_id="su-01", scope_quote="Ⅲ期：", affected_stage="筛选/导入期",
        time_words=["筛选/导入期"], unresolved=None,
    ))
    assert corrected.statements[0].scope_quote == "Ⅲ期："
    assert corrected.statements[0].time_words == ["筛选/导入期"]


def test_trial_phase_in_quoted_population_is_not_a_visit_time_or_stage() -> None:
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].excerpt = "Ⅲ期计划纳入164例受试者"
    original = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-01", "quoted_text": "Ⅲ期计划纳入164例受试者",
            "scope_quote": None, "affected_stage": "Ⅲ期",
            "force": "required", "time_words": ["Ⅲ期"],
        }],
        "units_without_statement": ["su-02"],
    })
    with pytest.raises(SourceInterpretationValidationError) as rejected:
        validate_source_interpretation(batch, original)
    assert rejected.value.code == "STUDY_PHASE_NOT_VISIT_STAGE"

    corrected = apply_source_scope_correction(batch, original, 0, SourceScopeCorrection(
        version="phase5/control-source-scope-correction/v1",
        structure_unit_id="su-01", scope_quote=None, affected_stage="Ⅲ期",
        time_words=[], unresolved=None,
    ))
    assert corrected.statements[0].quoted_text == original.statements[0].quoted_text
    assert corrected.statements[0].affected_stage is None
    assert corrected.statements[0].time_words == []
    validate_source_interpretation(batch, corrected)

    with pytest.raises(SourceInterpretationValidationError, match="共享范围"):
        apply_source_scope_correction(batch, original, 0, SourceScopeCorrection(
            version="phase5/control-source-scope-correction/v1",
            structure_unit_id="su-01", scope_quote="另一段的Ⅲ期", affected_stage=None,
            time_words=[], unresolved=None,
        ))

def test_schedule_columns_close_only_existing_enrollment_visits() -> None:
    def row(row_index: int, values: list[tuple[int, str]]) -> ProtocolStructureUnit:
        refs = [f"body.t0.r{row_index}.c{col}.p0" for col, _ in values]
        return ProtocolStructureUnit(
            structure_unit_id=f"row-{row_index}", source_ref=f"body.t0.r{row_index}",
            member_source_refs=refs, member_texts=[value for _, value in values],
            source_span_ids=[f"snapshot::{ref}" for ref in refs],
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
    conditional_row = mixed.model_copy(deep=True)
    conditional_row.member_texts[2] = "（X）"
    conditional_row.excerpt = "心电检查^2 | X | （X） | X"
    conditional_batch = batch.model_copy(deep=True)
    conditional_batch.owned_units = [conditional_row]
    assert schedule_column_links(
        conditional_batch, conditional_row.structure_unit_id, conditional_row.excerpt,
    ) == []
    delimiter_row = mixed.model_copy(deep=True)
    delimiter_row.member_texts[0] = "心电 | 检查^2"
    delimiter_row.excerpt = "心电 | 检查^2 | X | X | X"
    delimiter_batch = batch.model_copy(deep=True)
    delimiter_batch.owned_units = [delimiter_row]
    for target in delimiter_batch.known_procedure_targets:
        target.source_excerpts = ["心电 | 检查^2"]
    assert len(schedule_column_links(
        delimiter_batch, delimiter_row.structure_unit_id, delimiter_row.excerpt,
    )) == 3
    stale_row = delimiter_row.model_copy(deep=True)
    stale_row.member_texts = None
    delimiter_batch.owned_units = [stale_row]
    with pytest.raises(ValueError, match="逐项对应的原文"):
        schedule_column_links(
            delimiter_batch, stale_row.structure_unit_id, stale_row.excerpt,
        )
    sibling_batch = batch.model_copy(deep=True)
    sibling_batch.context_units = [header]
    sibling_batch.owned_units.append(visits)
    assert schedule_column_links(sibling_batch, mixed.structure_unit_id, mixed.excerpt) == links
    sibling_batch.context_units = []
    assert schedule_column_links(sibling_batch, mixed.structure_unit_id, mixed.excerpt) == []
    inventory = _source_inventory({
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
    inventory.statements[0].force = "descriptive"
    assert target_review_indexes(inventory, coverage, batch) == []
    batch.known_procedure_targets.pop()
    assert schedule_column_links(batch, mixed.structure_unit_id, mixed.excerpt) == []
    coverage[0].schedule_columns = []
    assert target_review_indexes(inventory, coverage, batch) == [0]
    assert schedule_column_links(batch, mixed.structure_unit_id, "心电检查^2 | X") == []
    mixed.excerpt = "心电检查^2 | X | X | X | 研究者判断"
    with pytest.raises(ValueError, match="展示文字与逐项来源原文不一致"):
        schedule_column_links(batch, mixed.structure_unit_id, mixed.excerpt)

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
    mixed.member_texts[3] = "X^27"
    mixed.excerpt = "心电检查^2 | X | X | X^27"
    batch.owned_units = [mixed]
    links = schedule_column_links(batch, mixed.structure_unit_id, mixed.excerpt)
    assert [item.marker_footnotes for item in links] == [[], [], ["^27"]]
    mixed.member_texts[1] = "X^4"
    mixed.excerpt = "心电检查^2 | X^4 | X | X^27"
    assert schedule_column_links(batch, mixed.structure_unit_id, mixed.excerpt) == []


def test_split_schedule_row_uses_only_complete_source_cells() -> None:
    from app.protocols.procedure_catalog import schedule_column_scope, schedule_row_values

    def cell(row: int, column: int, text: str, paragraph: int = 0) -> ProtocolStructureUnit:
        ref = f"body.t0.r{row}.c{column}.p{paragraph}"
        return ProtocolStructureUnit(
            structure_unit_id=ref, source_ref=ref,
            member_source_refs=[ref], member_texts=[text],
            source_span_ids=[f"snapshot::{ref}"],
            unit_kind="table_row", heading_path=["访视表"], source_order=row * 10 + column,
            study_phase=StudyPhase.PHASE_II, phase_scopes=[PhaseScope.SHARED],
            excerpt=text, table_context=TableCellContext(
                table_path=(row, column), row_index=row, column_index=column,
                member_cell_paths=[(row, column)],
            ),
        )

    header = [cell(0, index, text) for index, text in enumerate(
        ["项目", "筛选期 V1", "基线期 V2", "治疗期 V3"]
    )]
    label = cell(2, 0, "心电检查")
    marks = [cell(2, index, "X") for index in (1, 2, 3)]
    batch = _batch().model_copy(deep=True)
    batch.owned_units = [label, *marks]
    batch.context_units = header
    scopes = schedule_column_scope(label, [*header, *marks])
    assert [scope.boundary_side for scope in scopes] == [
        "at_or_before_baseline", "at_or_before_baseline", "after_baseline",
    ]
    batch.known_procedure_targets = [
        KnownRequiredProcedureTarget(
            catalog_item_id=f"procedure-{index}", label="心电检查",
            visit_instance=scopes[index - 1].header_text,
            review_stage=scopes[index - 1].review_stage, position=index,
            source_span_ids=label.source_span_ids, source_excerpts=[label.excerpt],
        ) for index in (1, 2)
    ]
    links = schedule_column_links(batch, label.structure_unit_id, label.excerpt)
    assert [link.procedure_target_id for link in links] == [
        "procedure-1", "procedure-2", None,
    ]
    assert schedule_column_links(batch, marks[0].structure_unit_id, "X") == []
    readonly = batch.model_copy(deep=True)
    readonly.owned_units = [label]
    readonly.context_units = [*header, *marks]
    assert schedule_column_links(readonly, label.structure_unit_id, label.excerpt) == links

    missing = batch.model_copy(deep=True)
    missing.owned_units.pop()
    assert schedule_column_links(missing, label.structure_unit_id, label.excerpt) == []
    conditional = batch.model_copy(deep=True)
    conditional.owned_units[2].member_texts = ["（X）"]
    conditional.owned_units[2].excerpt = "（X）"
    assert schedule_column_links(conditional, label.structure_unit_id, label.excerpt) == []

    extra_label = cell(2, 0, "复查", paragraph=1)
    assert schedule_row_values(label, [extra_label])[0] == (
        0, "心电检查 复查", (label.source_ref, extra_label.source_ref),
    )
    duplicate = label.model_copy(deep=True)
    duplicate.structure_unit_id = "duplicate"
    with pytest.raises(ValueError, match="互相冲突的来源"):
        schedule_row_values(label, [duplicate])


def test_split_schedule_label_uses_each_frozen_paragraph_locator() -> None:
    from app.protocols.procedure_catalog import schedule_column_scope

    def cell(row: int, col: int, text: str, paragraph: int = 0) -> ProtocolStructureUnit:
        ref = f"body.t0.r{row}.c{col}.p{paragraph}"
        span = f"span:{'a' * 56}{row:02d}{col:02d}{paragraph:02d}"
        return ProtocolStructureUnit(
            structure_unit_id=ref, source_ref=ref,
            member_source_refs=[ref], member_texts=[text],
            member_source_span_ids=[[span]], source_span_ids=[span],
            unit_kind="table_row", heading_path=["访视表"], source_order=row * 20 + col * 2 + paragraph,
            study_phase=StudyPhase.PHASE_II, phase_scopes=[PhaseScope.SHARED], excerpt=text,
            table_context=TableCellContext(
                table_path=(row, col), row_index=row, column_index=col,
                member_cell_paths=[(row, col)],
            ),
        )

    header = [cell(0, col, text) for col, text in enumerate(["项目", "筛选期 V1", "基线期 V2", "治疗期 V3"])]
    label = cell(2, 0, "心电检查")
    label_tail = cell(2, 0, "（12导联）", paragraph=1)
    marks = [cell(2, col, "X") for col in (1, 2, 3)]
    batch = _batch().model_copy(deep=True)
    batch.owned_units = [label, label_tail, *marks]
    batch.context_units = header
    scopes = schedule_column_scope(label, [*header, label_tail, *marks])
    batch.known_procedure_targets = [
        KnownRequiredProcedureTarget(
            catalog_item_id=f"procedure-{col}", label="心电检查（12导联）",
            visit_instance=scopes[col - 1].header_text,
            review_stage=scopes[col - 1].review_stage, position=col,
            source_span_ids=sorted([label.source_span_ids[0], label_tail.source_span_ids[0]]),
            source_excerpts=[text for _span, text in sorted([
                (label.source_span_ids[0], label.excerpt),
                (label_tail.source_span_ids[0], label_tail.excerpt),
            ])],
        ) for col in (1, 2)
    ]
    links = schedule_column_links(batch, label.structure_unit_id, label.excerpt)
    assert [link.procedure_target_id for link in links] == ["procedure-1", "procedure-2", None]
    batch.known_procedure_targets[0].source_excerpts[1] = "无关原文"
    assert schedule_column_links(batch, label.structure_unit_id, label.excerpt) == []


def test_wide_schedule_row_keeps_numeric_cell_order_without_trusting_display_text() -> None:
    from app.protocols.procedure_catalog import schedule_row_values

    refs = sorted(f"body.t0.r3.c{col}.p0" for col in range(12))
    unit = ProtocolStructureUnit(
        structure_unit_id="wide-row", source_ref="body.t0.r3",
        member_source_refs=refs,
        member_texts=[f"C{int(ref.split('.c')[-1].split('.')[0])}" for ref in refs],
        source_span_ids=sorted(f"snapshot::{ref}" for ref in refs),
        unit_kind="table_row", heading_path=["访视表"], source_order=3,
        study_phase=StudyPhase.PHASE_II, phase_scopes=[PhaseScope.SHARED],
        excerpt=" | ".join(f"C{col}" for col in range(12)),
        table_context=TableCellContext(
            table_path=(3, 0), row_index=3, column_index=0,
            member_cell_paths=[(3, col) for col in range(12)],
        ),
    )
    assert [text for _col, text, _refs in schedule_row_values(unit)] == [f"C{col}" for col in range(12)]
    unit.excerpt = " | ".join(f"C{col}" for col in reversed(range(12)))
    with pytest.raises(ValueError, match="展示文字与逐项来源原文不一致"):
        schedule_row_values(unit)


def test_schedule_header_with_multiple_paragraphs_in_one_cell_keeps_columns() -> None:
    from app.protocols.procedure_catalog import schedule_column_scope

    def row(number: int, values: list[tuple[int, int, str]]) -> ProtocolStructureUnit:
        members = sorted(
            (f"body.t0.r{number}.c{column}.p{paragraph}", text)
            for column, paragraph, text in values
        )
        refs = [ref for ref, _text in members]
        paths = sorted({(number, column) for column, _, _ in values})
        return ProtocolStructureUnit(
            structure_unit_id=f"row-{number}", source_ref=f"body.t0.r{number}",
            member_source_refs=refs, member_texts=[text for _ref, text in members],
            source_span_ids=[f"snapshot::{ref}" for ref in refs],
            unit_kind="table_row", heading_path=["访视表"], source_order=number,
            study_phase=StudyPhase.PHASE_II, phase_scopes=[PhaseScope.SHARED],
            excerpt=" | ".join(text for _, _, text in values if text.strip()),
            table_context=TableCellContext(
                table_path=(number, 0), row_index=number, column_index=0,
                member_cell_paths=paths,
            ),
        )

    header = row(0, [(0, 0, "项目"), (1, 0, "筛选期"),
                     (2, 0, "基线期"), (2, 1, "首次给药前"), (3, 0, "治疗期")])
    visits = row(1, [(0, 0, "访视"), (1, 0, "V1"),
                     (2, 0, "V2"), (2, 1, "基线"), (3, 0, "V3")])
    procedure = row(2, [(0, 0, "完成检查"), (1, 0, "X"),
                        (2, 0, "X"), (3, 0, "X")])
    columns = schedule_column_scope(procedure, [header, visits])
    assert [column.boundary_side for column in columns] == [
        "at_or_before_baseline", "at_or_before_baseline", "after_baseline",
    ]
    assert "基线期" in columns[1].header_text
    assert "基线" in columns[1].header_text

    lexical_header = row(0, [(0, 0, "项目"), (1, 0, "筛选期"),
                             (1, 2, "访视二"), (1, 10, "补充说明"),
                             (2, 0, "基线期"), (3, 0, "治疗期")])
    assert "访视二 补充说明" in schedule_column_scope(
        procedure, [lexical_header, visits],
    )[0].header_text
    blank_header = row(0, [(0, 0, "项目"), (1, 0, "筛选期"),
                           (2, 0, "基线期"), (3, 0, "治疗期"), (4, 0, "")])
    from app.protocols.procedure_catalog import schedule_row_values

    assert schedule_row_values(blank_header)[-1][1] == ""
    assert len(schedule_column_scope(procedure, [blank_header, visits])) == 3

    wrong_header = header.model_copy(deep=True)
    wrong_header.member_source_refs[3] = "body.t0.r0.c5.p1"
    with pytest.raises(ValueError, match="冻结单元格位置"):
        schedule_column_scope(procedure, [wrong_header, visits])


def test_schedule_header_merge_width_survives_semantic_batch() -> None:
    from app.protocols.procedure_catalog import schedule_column_scope

    def row(number: int, values: list[tuple[int, str, int]]) -> ProtocolStructureUnit:
        paths = [(number, col) for col, _, _ in values]
        refs = [f"body.t0.r{number}.c{col}.p0" for col, _, _ in values]
        texts = [value for _, value, _ in values]
        return ProtocolStructureUnit(
            structure_unit_id=f"merged-{number}", source_ref=f"body.t0.r{number}",
            member_source_refs=refs, member_texts=texts,
            source_span_ids=[f"snapshot::{ref}" for ref in refs],
            unit_kind="table_row", heading_path=["访视表"], source_order=number,
            study_phase=StudyPhase.PHASE_II, phase_scopes=[PhaseScope.SHARED],
            excerpt=" | ".join(texts),
            table_context=TableCellContext(
                table_path=paths[0], row_index=number, column_index=paths[0][-1],
                member_cell_paths=paths,
                member_cell_col_spans=[span for _, _, span in values],
            ),
        )

    header = row(0, [(0, "项目", 1), (1, "筛选期", 2)])
    visits = row(1, [(0, "访视", 1), (1, "V1", 1), (2, "V2", 1), (3, "V3", 1)])
    randomization = row(2, [(0, "随机", 1), (2, "X", 1)])
    procedure = row(3, [(0, "实验室检查", 1), (1, "X", 1), (2, "X", 1), (3, "X", 1)])
    columns = schedule_column_scope(procedure, [header, visits, randomization])
    assert "筛选期" in columns[0].header_text
    assert "筛选期" in columns[1].header_text
    assert "筛选期" not in columns[2].header_text
    assert columns[2].boundary_side == "after_baseline"


@pytest.mark.parametrize("prior_schema_repair", [False, True])
def test_mixed_official_source_keeps_its_link_when_new_requirement_is_added(
    prior_schema_repair: bool,
) -> None:
    batch = _batch().model_copy(deep=True)
    quote = "须记录年龄资料来源"
    batch.owned_units[0].excerpt = f"其他控制：年龄至少18岁；{quote}"
    batch.known_official_targets[0].source_excerpts = ["年龄至少18岁"]
    inventory = _source_inventory({
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


@pytest.mark.parametrize("restored", [False, True])
@pytest.mark.parametrize("invalid_insert", [False, True])
def test_source_insert_reuses_unchanged_validated_target_matches(
    restored: bool, invalid_insert: bool,
) -> None:
    batch = _batch().model_copy(deep=True)
    added_quote = "须记录年龄资料来源"
    batch.owned_units[0].excerpt = f"其他控制：年龄至少18岁；签署知情同意；{added_quote}"
    batch.known_official_targets[0].source_excerpts = ["签署知情同意"]
    inventory = _source_inventory({
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
            if restored:
                assert '"statement_index": 1' not in prompt
                self.review_calls += 1
                return ProtocolControlAgentResponse(
                    session_id="target-new",
                    text=SourceTargetReview(
                        version=SOURCE_TARGET_REVIEW_VERSION, items=[review.items[0]],
                    ).model_dump_json(),
                )
            self.review_calls += 1
            return ProtocolControlAgentResponse(session_id="target-1", text=review.model_dump_json())

        def start_source_insert(self, *, prompt: str, multiple: bool) -> ProtocolControlAgentResponse:
            assert restored and not multiple
            assert "已核候选只供去重" in prompt
            self.prompts.append(prompt)
            self.responses.pop(0)
            return ProtocolControlAgentResponse(
                session_id="source-insert-1",
                text="{}" if invalid_insert else json.dumps({"candidate_draft": candidate}, ensure_ascii=False),
            )

    responses = [] if restored else [
        ProtocolControlAgentResponse(session_id="wire-1", text=json.dumps(initial, ensure_ascii=False)),
    ]
    responses.append(ProtocolControlAgentResponse(
        session_id="wire-1", text="{}" if invalid_insert else json.dumps(revised, ensure_ascii=False),
    ))
    transport = CountingTransport(responses)
    original = ProtocolControlAgentWire.model_validate(initial)
    result = ProtocolControlAgentRunner(max_schema_repairs=0).run(
        batch, transport, output_validator=lambda _output: None,
        **({"resume_wire": original, "resume_source_interpretation": inventory,
            "resume_session_id": "wire-1", "resume_source_target_review": review,
            "resume_source_statement_coverage": source_statement_coverage(batch, inventory, original)}
           if restored else {}),
    )
    assert transport.review_calls == (0 if restored and invalid_insert else 1)
    insert = next(attempt for attempt in result.attempts
                  if "SOURCE_TARGET_ADDITIONAL_REQUIREMENT" in attempt.error_classes)
    assert insert.error_detail["review_proof_origin"] == (
        "saved_source_target_review" if restored else "model_response"
    )
    if restored:
        assert insert.session_id == "wire-1"
        assert insert.raw_output_text is None
        assert insert.raw_output_chars is None
    if invalid_insert:
        assert result.status == "需要核对"
        assert result.final_output is None
        assert result.partial_wire == original
        assert result.source_target_review == review
        assert not any("NoneType" in issue for attempt in result.attempts for issue in attempt.issues)
        return
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert len(result.final_output.candidates) == 2
    assert [entry.status for entry in result.source_statement_coverage] == [
        "candidate_linked", "expressed",
    ]


def _context_relation_example() -> tuple[
    object, SourceInterpretation, list[SourceTargetReviewItem], str, str,
]:
    """Two owned actions in one unit, each with its own same-sentence context."""

    batch = _batch().model_copy(deep=True)
    first = "每次给药10 mg，每日1次"
    second = "每次给药20 mg，每日1次"
    batch.owned_units[0].excerpt = (
        f"其他控制：年龄至少18岁；背景治疗：{first}。背景治疗：{second}"
    )
    batch.context_units[0].excerpt = (
        f"筛选期：背景治疗：{first}。筛选期：背景治疗：{second}"
    )
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
            {"structure_unit_id": "su-01", "quoted_text": first, "force": "required",
             "time_words": ["每日1次"]},
            {"structure_unit_id": "su-01", "quoted_text": second, "force": "required",
             "time_words": ["每日1次"]},
        ],
        "units_without_statement": ["su-02"],
    })
    relations = [
        SourceTargetReviewItem.model_validate({
            "statement_index": index, "decision": "potential_same_requirement",
            "target_id": "su-03", "source_action_excerpt": action,
            "target_action_excerpt": action, "target_scope_excerpt": "筛选期",
            "source_object_excerpt": "背景治疗", "target_object_excerpt": "背景治疗",
        })
        for index, action in enumerate((first, second))
    ]
    return batch, inventory, relations, first, second


@pytest.mark.parametrize("field,value", [
    ("affected_stage", "筛选期"),
    ("eligibility_sequence_quote", "确定入排资格之后"),
])
def test_saved_source_review_identity_includes_stage_and_sequence_basis(
    field: str, value: str,
) -> None:
    from app.agents.protocol_control_deconstructor import _source_statement_reuse_identity

    _batch_value, inventory, _relations, _first, _second = _context_relation_example()
    original = inventory.statements[0]
    unchanged = original.model_copy(deep=True)
    changed = original.model_copy(update={field: value})
    assert _source_statement_reuse_identity(original) == _source_statement_reuse_identity(unchanged)
    assert _source_statement_reuse_identity(original) != _source_statement_reuse_identity(changed)


@pytest.mark.parametrize("include_terminal_mark", [False, True])
def test_restored_saved_review_skips_rereading_and_keeps_pending_relation(
    include_terminal_mark: bool,
) -> None:
    batch, inventory, relations, _first, second = _context_relation_example()
    if include_terminal_mark:
        for unit in (batch.owned_units[0], batch.context_units[0]):
            unit.excerpt = unit.excerpt.replace(second, second + "。")
        for statement, relation in zip(inventory.statements, relations, strict=True):
            statement.quoted_text += "。"
            relation.source_action_excerpt += "。"
            relation.target_action_excerpt += "。"
    pending = SourceTargetReview(
        version=SOURCE_TARGET_REVIEW_VERSION, items=relations,
    )
    original = _wire(candidate=_candidate())
    saved_coverage = source_statement_coverage(batch, inventory, original)
    validate_source_target_review(batch, inventory, saved_coverage, pending)

    class NoReviewerTransport(_FakeTransport):
        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            pytest.fail("已保存且经当前校验仍有效的逐项来源核对不得重读")

    result = ProtocolControlAgentRunner().run(
        batch, NoReviewerTransport([]),
        resume_wire=original,
        resume_source_interpretation=inventory,
        resume_session_id="wire-session",
        resume_source_target_review=pending,
        resume_source_statement_coverage=saved_coverage,
        output_validator=lambda _output: None,
    )
    assert result.status == "待跨章核验", [attempt.issues for attempt in result.attempts]
    assert result.final_output is not None
    assert result.source_target_review is not None
    assert [item.decision for item in result.source_target_review.items] == [
        "potential_same_requirement", "potential_same_requirement",
    ]
    assert result.source_target_review == pending


def test_restored_saved_review_keeps_additional_requirement_for_the_real_consumer() -> None:
    batch, inventory, review, selection = _stage_bound_example()
    batch.owned_units[0].excerpt = "年龄至少18岁；" + batch.owned_units[0].excerpt
    original = _wire(candidate=_candidate())
    saved_coverage = source_statement_coverage(batch, inventory, original)
    saved = SourceTargetReview(version=SOURCE_TARGET_REVIEW_VERSION, items=[review])
    validate_source_target_review(batch, inventory, saved_coverage, saved)

    class StageReaderTransport(_FakeTransport):
        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            pytest.fail("已保存且经当前校验仍有效的逐项来源核对不得重读")

        def read_stage_bound_requirement(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="stage-1", text=selection.model_dump_json())

        def start_source_candidate_alignment(self, *, prompt):
            return _consent_policy_alignment_response(selection.action_excerpt, prompt)

    result = ProtocolControlAgentRunner().run(
        batch, StageReaderTransport([]),
        resume_wire=original,
        resume_source_interpretation=inventory,
        resume_session_id="wire-session",
        resume_source_target_review=saved,
        resume_source_statement_coverage=saved_coverage,
        output_validator=lambda _output: None,
    )
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert result.final_output is not None
    assert len(result.final_output.candidates) == 2
    assert result.source_target_review is not None
    assert result.source_target_review.items == []
    assert any(item.session_id == "stage-1" for item in result.attempts)


def test_restored_saved_review_refreshes_only_the_changed_statement() -> None:
    batch, inventory, relations, first, _second = _context_relation_example()
    relation, second_relation = relations
    saved = SourceTargetReview(
        version=SOURCE_TARGET_REVIEW_VERSION, items=relations,
    )
    original = _wire(candidate=_candidate())
    coverage = source_statement_coverage(batch, inventory, original)
    validate_source_target_review(batch, inventory, coverage, saved)
    changed = [
        coverage[0],
        coverage[1].model_copy(update={"status": "semantically_aligned"}),
    ]
    validate_source_target_review(batch, inventory, changed, saved)

    class CountingTransport(_FakeTransport):
        review_calls = 0
        prompts: list[str] = []

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.review_calls += 1
            self.prompts.append(prompt)
            return ProtocolControlAgentResponse(
                session_id="target-1",
                text=SourceTargetReview(
                    version=SOURCE_TARGET_REVIEW_VERSION, items=[second_relation],
                ).model_dump_json(),
            )

    transport = CountingTransport([])
    result = ProtocolControlAgentRunner().run(
        batch, transport,
        resume_wire=original,
        resume_source_interpretation=inventory,
        resume_session_id="wire-session",
        resume_source_target_review=saved,
        resume_source_statement_coverage=changed,
        output_validator=lambda _output: None,
    )
    assert transport.review_calls == 1, [attempt.issues for attempt in result.attempts]
    assert '"statement_index": 1' in transport.prompts[0]
    assert '"statement_index": 0' not in transport.prompts[0]
    assert result.status == "待跨章核验", [attempt.issues for attempt in result.attempts]
    assert result.source_target_review is not None
    assert [item.statement_index for item in result.source_target_review.items] == [0, 1]
    assert result.source_target_review.items[0] == relation
    assert first in transport.prompts[0]


def test_restored_saved_review_is_refused_when_current_scope_no_longer_proves_it() -> None:
    batch, inventory, relations, first, second = _context_relation_example()
    foreign = SourceTargetReview(
        version=SOURCE_TARGET_REVIEW_VERSION,
        items=[relations[0].model_copy(update={"statement_index": 4})],
    )
    original = _wire(candidate=_candidate())
    coverage = source_statement_coverage(batch, inventory, original)
    expected = SourceTargetReview(
        version=SOURCE_TARGET_REVIEW_VERSION, items=relations,
    )
    reasked: list[str] = []

    class RefreshingTransport(_FakeTransport):
        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            reasked.append(prompt)
            return ProtocolControlAgentResponse(
                session_id="target-1", text=expected.model_dump_json(),
            )

    result = ProtocolControlAgentRunner().run(
        batch, RefreshingTransport([]),
        resume_wire=original,
        resume_source_interpretation=inventory,
        resume_session_id="wire-session",
        resume_source_target_review=foreign,
        resume_source_statement_coverage=coverage,
        output_validator=lambda _output: None,
    )
    assert len(reasked) == 1, [attempt.issues for attempt in result.attempts]
    assert first in reasked[0] and second in reasked[0]
    assert result.status == "待跨章核验", [attempt.issues for attempt in result.attempts]
    assert result.source_target_review == expected


def test_restored_saved_review_requires_its_exact_saved_coverage() -> None:
    batch, inventory, relations, _first, _second = _context_relation_example()
    pending = SourceTargetReview(
        version=SOURCE_TARGET_REVIEW_VERSION, items=relations,
    )
    with pytest.raises(ValueError, match="来源覆盖账"):
        ProtocolControlAgentRunner().run(
            batch, _FakeTransport([]),
            resume_wire=_wire(candidate=_candidate()),
            resume_source_interpretation=inventory,
            resume_session_id="wire-session",
            resume_source_target_review=pending,
            output_validator=lambda _output: None,
        )


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


def test_deep_prompt_keeps_all_target_excerpts_without_catalog_bookkeeping() -> None:
    batch = _batch()
    batch.known_official_targets[0].source_excerpts = ["筛选前须符合该条原文"]
    batch.known_procedure_targets[0].source_excerpts = ["筛选期完成对应检查"]
    prompt = build_protocol_control_agent_prompt(batch)
    payload = json.loads(prompt.split("本次冻结输入：", 1)[1].split("\n\n", 1)[0])

    official = payload["known_official_targets"][0]
    procedure = payload["known_procedure_targets"][0]
    assert official == {
        "official_code": "EX-01",
        "label": "既有官方排除标准",
        "source_excerpts": ["筛选前须符合该条原文"],
    }
    assert procedure["catalog_item_id"] == "procedure-screening-1"
    assert procedure["visit_instance"] == "screening-1"
    assert procedure["source_excerpts"] == ["筛选期完成对应检查"]
    assert "source_span_ids" not in procedure
    assert batch.known_procedure_targets[0].source_span_ids == ["span:procedure"]


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
    revised["title"] += "（已核对）"
    revised_atom["evaluation"]["time_operand_attribute"] = None
    merged = _merge_candidate_repair(json.dumps({"candidate_draft": revised}), baseline, 0)
    assert merged.candidate_drafts[0].obligation_expression.groups[0].atoms[0].evaluation.time_operand_attribute == "date_range"

    omitted_defaults = deepcopy(revised)
    normalized_atom = omitted_defaults["obligation_expression"]["groups"][0]["atoms"][0]
    for field in ("continuing_obligation", "modality", "temporal_scope"):
        del normalized_atom[field]
    normalized = _merge_candidate_repair(
        json.dumps({"candidate_draft": omitted_defaults}), baseline, 0
    )
    assert normalized.candidate_drafts[0].obligation_expression == merged.candidate_drafts[0].obligation_expression

    unknown_meaning = deepcopy(revised)
    unknown_meaning["obligation_expression"]["groups"][0]["atoms"][0]["evaluation"]["unknown_semantic_property"] = "不得忽略"
    with pytest.raises(ProtocolControlAgentWireValidationError, match="CANDIDATE_REPAIR_INVALID"):
        _merge_candidate_repair(json.dumps({"candidate_draft": unknown_meaning}), baseline, 0)

    changed_time = deepcopy(revised)
    changed_time["obligation_expression"]["groups"][0]["atoms"][0]["time_constraint"]["direction"] = "after"
    with pytest.raises(ProtocolControlAgentWireValidationError, match="CANDIDATE_REPAIR_INVALID"):
        _merge_candidate_repair(json.dumps({"candidate_draft": changed_time}), baseline, 0)

    changed_source = deepcopy(revised)
    changed_source["obligation_expression"]["groups"][0]["atoms"][0]["source_excerpts"] = ["另一条原文"]
    with pytest.raises(ProtocolControlAgentWireValidationError, match="CANDIDATE_REPAIR_INVALID"):
        _merge_candidate_repair(json.dumps({"candidate_draft": changed_source}), baseline, 0)

    for field in ("statement", "proposition"):
        changed_meaning = deepcopy(revised)
        changed_atom = changed_meaning["obligation_expression"]["groups"][0]["atoms"][0]
        target = changed_atom if field == "statement" else changed_atom["evaluation"]
        target[field] = "另一项要求使用的日期"
        with pytest.raises(ProtocolControlAgentWireValidationError, match="CANDIDATE_REPAIR_INVALID"):
            _merge_candidate_repair(json.dumps({"candidate_draft": changed_meaning}), baseline, 0)


@pytest.mark.parametrize("remove_unrelated_link", [False, True])
def test_wire_stage_error_repairs_only_its_candidate_without_rewriting_batch(remove_unrelated_link) -> None:
    batch = _batch()
    relation = ProtocolControlAgentWireRelation(
        kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
        external_target_kind=ControlRelationTargetKind.REQUIRED_PROCEDURE,
        external_target_id="procedure-screening-1",
        candidate_side="left",
        affected_workflow_stage_id="stage:screening:two",
        notes="需核对具体访视",
    )
    first = _candidate().model_copy(update={"exception_expression": None})
    invalid_first = first.model_copy(update={"cross_source_relations": [relation]})
    valid_relation = relation.model_copy(
        update={"affected_workflow_stage_id": "stage:screening:one"}
    )
    fixed_first = first.model_copy(update={
        "cross_source_relations": [] if remove_unrelated_link else [valid_relation],
    })
    second = _candidate_for_second_unit().model_copy(update={"exception_expression": None})
    second.applicability_expression = None
    second_atom = second.obligation_expression.groups[0].atoms[0]
    second_atom.kind = ControlObligationKind.MUST_RECORD
    second_atom.evaluation = type(second_atom.evaluation).model_validate(
        _evaluation("记录末次用药日期", "span:02", "筛选时记录末次用药日期")
    )
    initial = _wire_with_two_candidates(invalid_first, second)

    class CandidateTransport(_FakeTransport):
        supports_candidate_field_repair = True

        def continue_candidate(self, *, session_id: str, prompt: str, fields=()):
            self.prompts.append(prompt)
            assert "仅返回包含 candidate_draft" in prompt
            assert "本轮获授权候选原稿" in prompt
            assert invalid_first.title in prompt
            assert fields == ("cross_source_relations",)
            assert "系统原样保留疗程、时间、义务、判定节点和证据" in prompt
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"candidate_draft": {
                    "cross_source_relations": fixed_first.model_dump(mode="json")["cross_source_relations"],
                }}),
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
    from app.protocols.protocol_control_gate import validate_protocol_control_batch_candidates
    validate_protocol_control_batch_candidates(batch, result.final_output)


def test_repair_prompt_repeats_target_index_without_claiming_coverage() -> None:
    prompt = build_protocol_control_repair_prompt(
        _batch(), problem="BASELINE_VALUE_SCOPE_MISSING"
    )
    assert "冻结目标索引" in prompt
    assert "是否覆盖仍须核对首轮输入中的目标原文" in prompt
    assert _batch().known_official_targets[0].official_code in prompt
    assert _batch().known_procedure_targets[0].catalog_item_id in prompt
    assert "cross_source_relations" in prompt


def test_relation_field_repair_retains_clinical_meaning_and_other_targets() -> None:
    first = _candidate()
    relation = ProtocolControlAgentWireRelation(
        kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
        external_target_kind=ControlRelationTargetKind.REQUIRED_PROCEDURE,
        external_target_id="procedure-screening-1", candidate_side="left",
        affected_workflow_stage_id="stage:screening:two", notes="待核对的关联",
    )
    unrelated = relation.model_copy(update={"external_target_id": "other-target"})
    first = first.model_copy(update={"cross_source_relations": [relation, unrelated]})
    baseline = _wire_with_two_candidates(first, _candidate_for_second_unit())
    retained = unrelated.model_dump(mode="json")
    payload = {"candidate_draft": {"cross_source_relations": [retained]}}
    merged = _merge_candidate_repair(
        json.dumps(payload), baseline, 0, fields=("cross_source_relations",),
        relation_target_ids=("procedure-screening-1",), relation_indexes=(0,),
    )
    expected = baseline.model_dump(mode="json")
    expected["candidate_drafts"][0]["cross_source_relations"] = [retained]
    assert merged.model_dump(mode="json") == expected
    assert baseline.candidate_drafts[0] == first
    for changed in (
        {"cross_source_relations": [], "workflow_stage_nodes": []},
        {"cross_source_relations": []},
        {"cross_source_relations": [retained, retained]},
        {"cross_source_relations": [retained, {**relation.model_dump(mode="json"), "kind": "mentions"}]},
    ):
        with pytest.raises(ProtocolControlAgentWireValidationError, match="CANDIDATE_REPAIR_INVALID"):
            _merge_candidate_repair(
                json.dumps({"candidate_draft": changed}), baseline, 0,
                fields=("cross_source_relations",), relation_target_ids=("procedure-screening-1",),
                relation_indexes=(0,),
            )
    schema = protocol_control_candidate_repair_response_format(fields=("cross_source_relations",))
    patch_schema = schema["json_schema"]["schema"]["properties"]["candidate_draft"]
    assert list(patch_schema["properties"]) == ["cross_source_relations"]
    assert patch_schema["additionalProperties"] is False
    with pytest.raises(ValueError, match="未授权"):
        protocol_control_candidate_repair_response_format(fields=("workflow_stage_nodes",))
    same_target = unrelated.model_copy(update={
        "external_target_id": relation.external_target_id, "candidate_side": "right",
    })
    same_target_wire = baseline.model_copy(update={"candidate_drafts": [
        first.model_copy(update={"cross_source_relations": [relation, same_target]}),
        baseline.candidate_drafts[1],
    ]})
    with pytest.raises(ProtocolControlAgentWireValidationError, match="未授权关系"):
        _merge_candidate_repair(
            json.dumps({"candidate_draft": {"cross_source_relations": []}}),
            same_target_wire, 0, fields=("cross_source_relations",),
            relation_target_ids=(relation.external_target_id,), relation_indexes=(0,),
        )


def test_stage_field_repair_cannot_fall_back_to_full_candidate_transport() -> None:
    first = _candidate()
    relation = ProtocolControlAgentWireRelation(
        kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
        external_target_kind=ControlRelationTargetKind.REQUIRED_PROCEDURE,
        external_target_id="procedure-screening-1", candidate_side="left",
        affected_workflow_stage_id="stage:screening:two", notes="待核对",
    )
    baseline = _wire_with_two_candidates(
        first.model_copy(update={"cross_source_relations": [relation]}), _candidate_for_second_unit(),
    )

    class LegacyTransport(_FakeTransport):
        def continue_candidate(self, **kwargs):
            raise AssertionError("不支持字段修订时不可重写整候选")

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        _batch(), LegacyTransport([ProtocolControlAgentResponse(session_id="s", text=baseline.model_dump_json())]),
    )
    assert result.status == "需要核对"
    assert result.final_output is None
    assert result.attempts[-1].outcome == "transport_failed"
    assert "不能退回整候选改写" in result.attempts[-1].issues[0]


def test_missing_affected_stage_decision_repair_does_not_assume_cross_stage() -> None:
    prompt = build_protocol_control_repair_prompt(
        _batch(), problem="AFFECTED_STAGE_DECISION_MISSING", candidate_only=True,
    )
    assert "删除错误关系" in prompt
    assert "增加 decide_at_node" in prompt
    assert "同阶段补充的受影响节点须与其一致" in prompt
    assert "只有原文明确要求在后续入排节点判定增量时" in prompt


def test_procedure_stage_mismatch_repair_can_remove_an_unrelated_link() -> None:
    prompt = build_protocol_control_repair_prompt(
        _batch(), problem="PROCEDURE_AFFECTED_STAGE_MISMATCH", candidate_only=True,
    )
    assert "同一具体检查或操作" in prompt
    assert "若无直接补充关系，删除该错误关系" in prompt
    assert "保留有源独立候选及其真实判定节点" in prompt


def test_obligation_failure_consequence_is_not_a_trigger_in_repair() -> None:
    prompt = build_protocol_control_repair_prompt(
        _batch(), problem="ROUTINE_OBLIGATION_MISLABELED_AS_TRIGGER", candidate_only=True,
    )
    assert "后一句是前述要求不满足时的后果" in prompt
    assert "保留全部合取义务与真实决定节点" in prompt
    assert "仅原文另有独立的适用人群或事件前提" in prompt


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


def test_observation_source_mismatch_repairs_candidate_without_rewriting_time_or_sibling() -> None:
    batch = _batch()
    first = _candidate()
    second = _candidate_for_second_unit()
    initial = _wire_with_two_candidates(first, second).model_dump(mode="json")
    atom = initial["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]
    atom["evaluation"]["observation_policy"]["source_excerpts"] = [
        "相邻要求：" + atom["source_excerpts"][0]
    ]

    class CandidateTransport(_FakeTransport):
        def continue_candidate(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            assert "观察选择的每段原文必须完整包含" in prompt
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"candidate_draft": first.model_dump(mode="json")}, ensure_ascii=False),
            )

        def continue_atom(self, *, session_id: str, prompt: str):
            raise AssertionError("来源摘录问题不得重写整个义务原子")

    transport = CandidateTransport([
        ProtocolControlAgentResponse(
            session_id="source-repair", text=json.dumps(initial, ensure_ascii=False)
        )
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(batch, transport)
    assert result.status == "已解析"
    assert result.final_output is not None
    assert result.final_output.candidates[1].title == second.title
    assert len(result.attempts) == 2


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


def test_atom_level_evaluation_error_uses_focused_repair() -> None:
    first = _candidate()
    original = _wire_with_two_candidates(first, _candidate_for_second_unit()).model_dump(mode="json")
    atom = original["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]
    atom["evaluation"]["observation_policy"]["mode"] = "action_completion"

    class AtomTransport(_FakeTransport):
        def __init__(self):
            super().__init__([ProtocolControlAgentResponse(
                session_id="atom-level", text=json.dumps(original, ensure_ascii=False),
            )])
            self.atom_calls = 0

        def continue_atom(self, *, session_id: str, prompt: str) -> ProtocolControlAgentResponse:
            self.atom_calls += 1
            assert "候选0／义务组0／原子0" in prompt
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"atom": first.obligation_expression.groups[0].atoms[0].model_dump(mode="json")}, ensure_ascii=False),
            )

        def continue_candidate(self, *, session_id: str, prompt: str) -> ProtocolControlAgentResponse:
            pytest.fail("单原子求值错误不应重写整个候选")

    transport = AtomTransport()
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(_batch(), transport)
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert transport.atom_calls == 1
    assert result.final_output is not None
    assert len(result.final_output.candidates) == 2


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


@pytest.mark.parametrize("continuation_change", [
    {"source_span_ids": ["span:02"]},
    {"source_excerpts": ["治疗期禁止开始新的治疗"]},
    {"source_excerpts": ["原文未记载的后续要求"]},
    {"status": "completed"},
])
def test_continuation_source_error_cannot_select_frozen_atom_repair(continuation_change) -> None:
    baseline = _wire_with_two_candidates(
        _candidate(), _candidate_for_second_unit(),
    ).model_dump(mode="json")
    atom = baseline["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]
    atom["kind"] = ControlObligationKind.PROHIBIT_EVENT.value
    atom["continuing_obligation"] = {
        "statement": "治疗期禁止开始新的治疗",
        "prospective_period": {"period": "treatment_period"},
        "source_span_ids": atom["source_span_ids"],
        "source_excerpts": atom["source_excerpts"],
        "status": "not_due_at_review_node",
        **continuation_change,
    }
    with pytest.raises(ProtocolControlAgentWireValidationError) as exc:
        parse_protocol_control_agent_wire(json.dumps(baseline, ensure_ascii=False))
    assert _invalid_obligation_atom_path(exc.value, baseline, 0) is None


def test_valid_continuation_keeps_evaluation_only_atom_repair_available() -> None:
    baseline = _wire_with_two_candidates(
        _candidate(), _candidate_for_second_unit(),
    ).model_dump(mode="json")
    atom = baseline["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]
    atom["kind"] = ControlObligationKind.PROHIBIT_EVENT.value
    atom["continuing_obligation"] = {
        "statement": "治疗期禁止开始新的治疗",
        "prospective_period": {"period": "treatment_period"},
        "source_span_ids": atom["source_span_ids"],
        "source_excerpts": atom["source_excerpts"],
        "status": "not_due_at_review_node",
    }
    atom["evaluation"]["observation_policy"]["mode"] = "action_completion"
    with pytest.raises(ProtocolControlAgentWireValidationError) as exc:
        parse_protocol_control_agent_wire(json.dumps(baseline, ensure_ascii=False))
    assert _invalid_obligation_atom_path(exc.value, baseline, 0) == (0, 0, 0)


def test_atom_repair_completes_only_explicit_unresolved_policy_from_own_atom() -> None:
    baseline = _wire(candidate=_candidate()).model_dump(mode="json")
    atom = deepcopy(baseline["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0])
    atom["evaluation"]["observation_policy"] = {"mode": "unresolved"}
    merged = _merge_obligation_atom_repair(
        json.dumps({"atom": atom}, ensure_ascii=False), baseline, (0, 0, 0)
    )
    policy = merged.candidate_drafts[0].obligation_expression.groups[0].atoms[0].evaluation.observation_policy
    assert policy.scope == atom["statement"]
    assert policy.source_span_ids == atom["source_span_ids"]
    assert policy.source_excerpts == atom["source_excerpts"]

    atom["evaluation"]["observation_policy"] = {"mode": "single"}
    with pytest.raises(ProtocolControlAgentWireValidationError, match="ATOM_REPAIR_INVALID"):
        _merge_obligation_atom_repair(json.dumps({"atom": atom}), baseline, (0, 0, 0))

    atom["evaluation"]["observation_policy"] = {
        "mode": "unresolved", "scope": atom["statement"],
        "source_span_ids": atom["source_span_ids"], "source_excerpts": ["不属于该原子的摘录"],
    }
    with pytest.raises(ProtocolControlAgentWireValidationError, match="ATOM_REPAIR_INVALID"):
        _merge_obligation_atom_repair(json.dumps({"atom": atom}, ensure_ascii=False), baseline, (0, 0, 0))


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
    assert paths == (("obligation", 0, 0), ("obligation", 0, 1))
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
        {"layer": "obligation", "group_index": 0, "atom_index": index, "policy": policy}
        for index in (0, 1)
    ]}
    merged = _merge_observation_policy_repair(json.dumps(repair), baseline, 0, paths)
    assert merged.candidate_drafts[1] == valid.candidate_drafts[1]
    assert [atom.statement for atom in merged.candidate_drafts[0].obligation_expression.groups[0].atoms] == [
        "年龄达到18岁", "核对年龄资料",
    ]
    schema = protocol_control_observation_repair_response_format()["json_schema"]
    assert schema["name"] == "protocol_control_observation_repair_v2"
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
    assert path == (0, (("obligation", 0, 0),))
    assert _future_prohibition_repair_path(error, wire, {0}) is None
    policy = dict(atom["evaluation"]["observation_policy"])
    policy["scope"] = "截至当前审核节点的背景治疗调整记录"
    repair = {"items": [{"layer": "obligation", "group_index": 0, "atom_index": 0, "policy": policy}]}
    prompt = _build_observation_policy_repair_prompt(baseline, 0, (("obligation", 0, 0),), str(error))
    assert "仅修正现有观察采用说明" in prompt
    merged = _merge_observation_policy_repair(json.dumps(repair), baseline, 0, (("obligation", 0, 0),))
    changed = merged.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    assert changed.evaluation.observation_policy.scope == policy["scope"]
    assert merged.candidate_drafts[1] == wire.candidate_drafts[1]
    repair["items"][0]["policy"]["source_excerpts"] = ["另一份资料"]
    with pytest.raises(ProtocolControlAgentWireValidationError, match="只允许修正 scope"):
        _merge_observation_policy_repair(json.dumps(repair), baseline, 0, (("obligation", 0, 0),))


@pytest.mark.parametrize("both_candidates", [False, True])
@pytest.mark.parametrize("repair_succeeds", [False, True])
def test_located_future_scope_repairs_one_of_several_atoms_without_rewriting(
    both_candidates: bool, repair_succeeds: bool,
) -> None:
    baseline = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit()).model_dump(mode="json")
    atoms = baseline["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"]
    first = atoms[0]
    first["kind"] = ControlObligationKind.PROHIBIT_EVENT.value
    first["continuing_obligation"] = {
        "statement": "治疗期不得调整背景治疗",
        "prospective_period": {"period": "treatment_period"},
        "source_span_ids": first["source_span_ids"],
        "source_excerpts": first["source_excerpts"], "status": "not_due_at_review_node",
    }
    sibling = deepcopy(first)
    sibling["statement"] = "核对另一独立禁止行为"
    sibling["evaluation"]["proposition"] = sibling["statement"]
    sibling["evaluation"]["observation_policy"]["scope"] = "截至当前审核节点的记录"
    first["evaluation"]["observation_policy"]["scope"] = "筛选期及治疗期记录"
    atoms.append(sibling)
    if both_candidates:
        second = baseline["candidate_drafts"][1]["obligation_expression"]["groups"][0]["atoms"][0]
        second["kind"] = first["kind"]
        second["continuing_obligation"] = {
            **first["continuing_obligation"], "source_span_ids": second["source_span_ids"],
            "source_excerpts": second["source_excerpts"],
        }
        second["evaluation"]["observation_policy"]["scope"] = first["evaluation"]["observation_policy"]["scope"]
    initial = ProtocolControlAgentWire.model_validate(baseline)
    policy = deepcopy(first["evaluation"]["observation_policy"])
    policy["scope"] = "截至当前审核节点的记录"

    class FieldTransport(_FakeTransport):
        def continue_observation_policies(self, *, session_id, prompt):
            self.prompts.append(prompt)
            assert "另一独立禁止行为" not in prompt
            target = baseline["candidate_drafts"][len(self.prompts) - 2]["obligation_expression"]["groups"][0]["atoms"][0]
            fixed_policy = deepcopy(target["evaluation"]["observation_policy"])
            if repair_succeeds:
                fixed_policy["scope"] = policy["scope"]
            return ProtocolControlAgentResponse(session_id=session_id, text=json.dumps({
                "items": [{"layer": "obligation", "group_index": 0, "atom_index": 0, "policy": fixed_policy}],
            }))

        def continue_candidate(self, **kwargs):
            pytest.fail("已有字段定位，不得整条重写")

        def continue_session(self, **kwargs):
            pytest.fail("已有字段定位，不得整组重写")

    calls = 0

    def validate(output):
        nonlocal calls
        calls += 1
        issues = [SimpleNamespace(
            code="FUTURE_PROHIBITION_DECIDED_EARLY", message="显示文字可以改变",
            entity_id=candidate.control_candidate_id,
            json_path="obligation_expression.groups.0.atoms.0.evaluation.observation_policy.scope",
        ) for candidate in output.candidates[:2 if both_candidates else 1]
            if candidate.semantics.obligation_expression.groups[0].atoms[0].evaluation.observation_policy.scope != policy["scope"]]
        if issues:
            raise publication_repair_error(
                issues=issues, candidate_by_id={c.control_candidate_id: c for c in output.candidates},
                control_to_candidate={}, default_structure_unit_ids=["su-01", "su-02"],
            )

    transport = FieldTransport([ProtocolControlAgentResponse(session_id="field-scope", text=initial.model_dump_json())])
    result = ProtocolControlAgentRunner(max_schema_repairs=2).run(_batch(), transport, output_validator=validate)
    if not repair_succeeds:
        assert result.status == "需要核对"
        assert calls == 2 and len(transport.prompts) == 2
        return
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert calls == (3 if both_candidates else 2) and len(transport.prompts) == calls
    final = result.partial_wire
    if not both_candidates:
        assert final.candidate_drafts[1] == initial.candidate_drafts[1]
    assert final.candidate_drafts[0].obligation_expression.groups[0].atoms[1] == initial.candidate_drafts[0].obligation_expression.groups[0].atoms[1]
    expected = deepcopy(baseline)
    expected["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]["evaluation"]["observation_policy"] = policy
    if both_candidates:
        expected["candidate_drafts"][1]["obligation_expression"]["groups"][0]["atoms"][0]["evaluation"]["observation_policy"]["scope"] = policy["scope"]
    assert final == ProtocolControlAgentWire.model_validate(expected)
    finding = result.attempts[0].error_detail["findings"][0]
    assert finding["json_path"].endswith("observation_policy.scope")


@pytest.mark.parametrize("path", [
    "obligation_expression.groups.99.atoms.0.evaluation.observation_policy.scope",
    "obligation_expression.groups.-1.atoms.0.evaluation.observation_policy.scope",
    "candidate_drafts.1.obligation_expression.groups.0.atoms.0.evaluation.observation_policy.scope",
    "obligation_expression.groups.0.atoms.0.source_excerpts",
    0,
])
def test_present_invalid_future_field_location_never_falls_back_to_guessing(path) -> None:
    wire = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit())
    error = ProtocolControlAgentWireValidationError(
        "PUBLICATION_GATE_REJECTED", "当前节点的观察范围",
        candidate_indexes=[0], error_class_codes=["FUTURE_PROHIBITION_DECIDED_EARLY"],
        validation_findings=[{"code": "FUTURE_PROHIBITION_DECIDED_EARLY", "json_path": path}],
    )
    assert _future_observation_scope_repair_path(error, wire, {0}) is None
    assert _future_prohibition_repair_path(error, wire, {0}) is None


def test_located_future_statement_selects_exact_atom_despite_legacy_message() -> None:
    wire = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit())
    atoms = wire.candidate_drafts[0].obligation_expression.groups[0].atoms
    atoms[0].kind = ControlObligationKind.PROHIBIT_EVENT
    atoms.append(atoms[0].model_copy(deep=True))
    error = ProtocolControlAgentWireValidationError(
        "PUBLICATION_GATE_REJECTED", "当前节点的观察范围",
        candidate_indexes=[0], error_class_codes=["FUTURE_PROHIBITION_DECIDED_EARLY"],
        validation_findings=[{"code": "FUTURE_PROHIBITION_DECIDED_EARLY",
                              "json_path": "obligation_expression.groups.0.atoms.1.statement"}],
    )
    assert _future_prohibition_repair_path(error, wire, {0}) == (0, 0, 1)
    assert _future_observation_scope_repair_path(error, wire, {0}) is None


def test_mixed_future_scope_and_duration_use_separate_existing_repairs():
    baseline = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit()).model_dump(mode="json")
    first_atom = baseline["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]
    first_atom["kind"] = ControlObligationKind.PROHIBIT_EVENT.value
    first_atom["continuing_obligation"] = {
        "statement": "治疗期不得调整背景治疗",
        "prospective_period": {"period": "treatment_period"},
        "source_span_ids": first_atom["source_span_ids"],
        "source_excerpts": first_atom["source_excerpts"], "status": "not_due_at_review_node",
    }
    first_atom["evaluation"]["observation_policy"]["scope"] = "筛选期及治疗期记录"
    second_atom = baseline["candidate_drafts"][1]["obligation_expression"]["groups"][0]["atoms"][0]
    second_atom["time_constraint"] = {
        "anchor_type": "screening_date", "direction": "before", "upper_bound_days": 7,
    }
    second_atom["evaluation"] = _timed_evaluation(
        second_atom["statement"], "span:02", second_atom["source_excerpts"][0],
    )
    initial = ProtocolControlAgentWire.model_validate(baseline)
    policy = deepcopy(first_atom["evaluation"]["observation_policy"])
    policy["scope"] = "截至当前审核节点的记录"
    corrected_atom = deepcopy(second_atom)
    corrected_atom["time_constraint"] = None
    corrected_atom["evaluation"]["time_purpose"] = "unresolved"
    corrected_atom["evaluation"]["time_operand_attribute"] = None

    class MixedTransport(_FakeTransport):
        def continue_observation_policies(self, *, session_id, prompt):
            self.prompts.append(prompt)
            assert "持续治疗" not in prompt
            return ProtocolControlAgentResponse(session_id=session_id, text=json.dumps({
                "items": [{"layer": "obligation", "group_index": 0, "atom_index": 0, "policy": policy}],
            }))

        def continue_atom(self, *, session_id, prompt):
            self.prompts.append(prompt)
            return ProtocolControlAgentResponse(session_id=session_id, text=json.dumps({"atom": corrected_atom}))

        def continue_candidate(self, **kwargs):
            pytest.fail("能定位到既有字段，不得重写整个候选")

        def continue_session(self, **kwargs):
            pytest.fail("独立错误不得恢复为完整重写")

    calls = 0

    def validate(output):
        nonlocal calls
        calls += 1
        issues = []
        if calls == 1:
            issues.append(SimpleNamespace(
                code="FUTURE_PROHIBITION_DECIDED_EARLY",
                message="当前节点的观察范围不得要求覆盖后续期间",
                entity_id=output.candidates[0].control_candidate_id,
            ))
        else:
            assert output.candidates[0].semantics.obligation_expression.groups[0].atoms[0].evaluation.observation_policy.scope == policy["scope"]
        if calls <= 2:
            issues.append(SimpleNamespace(
                code="TREATMENT_DURATION_USED_AS_EVENT_WINDOW", message="持续治疗时长误作事件发生窗口",
                entity_id=output.candidates[1].control_candidate_id, obligation_source_span_ids=["span:02"],
            ))
        if issues:
            raise publication_repair_error(
                issues=issues, candidate_by_id={c.control_candidate_id: c for c in output.candidates},
                control_to_candidate={}, default_structure_unit_ids=["su-01", "su-02"],
            )

    transport = MixedTransport([
        ProtocolControlAgentResponse(session_id="mixed-scopes", text=initial.model_dump_json()),
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(_batch(), transport, output_validator=validate)
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert calls == 3 and len(transport.prompts) == 3
    assert len(result.attempts[0].error_detail["findings"]) == 2
    assert result.partial_wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0].continuing_obligation == initial.candidate_drafts[0].obligation_expression.groups[0].atoms[0].continuing_obligation
    assert result.partial_wire.candidate_drafts[1].obligation_expression.groups[0].atoms[0].time_constraint is None


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
                    {"layer": "obligation", "group_index": 0, "atom_index": index, "policy": policy}
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


def test_policy_repair_covers_trigger_and_obligation_without_rewriting_candidate() -> None:
    batch = _batch()
    first = _candidate().model_copy(deep=True)
    first.trigger_expression = ProtocolControlAgentWireConditionDnf(
        groups=[ProtocolControlAgentWireConditionGroup(
            atoms=[_condition("核对年龄资料", "span:01", "年龄至少18岁")]
        )]
    )
    first.exception_expression = None
    second = _candidate_for_second_unit()
    initial = _wire_with_two_candidates(first, second).model_dump(mode="json")
    trigger = initial["candidate_drafts"][0]["trigger_expression"]["groups"][0]["atoms"][0]
    obligation = initial["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]
    trigger["evaluation"]["observation_policy"] = None
    obligation["evaluation"]["observation_policy"] = None
    policy = {
        "mode": "unresolved", "scope": "方案未明确选择哪次年龄记录",
        "source_span_ids": ["span:01"], "source_excerpts": ["年龄至少18岁"],
    }

    class PolicyTransport(_FakeTransport):
        def continue_observation_policies(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            assert '"layer":"trigger"' in prompt
            assert '"layer":"obligation"' in prompt
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"items": [
                    {"layer": layer, "group_index": 0, "atom_index": 0, "policy": policy}
                    for layer in ("obligation", "trigger")
                ]}, ensure_ascii=False),
            )

        def continue_candidate(self, *, session_id: str, prompt: str):
            raise AssertionError("缺少观察规则不能重写整个候选")

    transport = PolicyTransport([
        ProtocolControlAgentResponse(session_id="cross-layer", text=json.dumps(initial, ensure_ascii=False))
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(batch, transport)
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert result.final_output is not None
    assert result.final_output.candidates[1].title == second.title
    assert len(result.attempts) == 2


def test_policy_patch_survives_a_separate_atom_error_without_claiming_acceptance() -> None:
    first = _candidate()
    second = _candidate_for_second_unit()
    baseline = _wire_with_two_candidates(first, second).model_dump(mode="json")
    atom = baseline["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]
    atom["evaluation"]["observation_policy"] = None
    atom["evaluation"]["time_purpose"] = "event_membership"
    policy = {
        "mode": "unresolved", "scope": "原文未说明采用哪次记录",
        "source_span_ids": ["span:01"], "source_excerpts": ["年龄至少18岁"],
    }
    policy_reply = json.dumps({"items": [
        {"layer": "obligation", "group_index": 0, "atom_index": 0, "policy": policy},
    ]})
    corrected = deepcopy(atom)
    corrected["evaluation"]["observation_policy"] = policy
    corrected["evaluation"]["time_purpose"] = "not_applicable"

    class PatchTransport(_FakeTransport):
        def continue_observation_policies(self, *, session_id: str, prompt: str):
            return ProtocolControlAgentResponse(session_id=session_id, text=policy_reply)

        def continue_atom(self, *, session_id: str, prompt: str):
            assert "原文未说明采用哪次记录" in prompt
            return ProtocolControlAgentResponse(
                session_id=session_id, text=json.dumps({"atom": corrected}, ensure_ascii=False),
            )

        def continue_candidate(self, *, session_id: str, prompt: str):
            pytest.fail("已限定到一个求值错误，不应丢掉局部补入并重写候选")

    def run(budget):
        return ProtocolControlAgentRunner(max_schema_repairs=budget).run(_batch(), PatchTransport([
            ProtocolControlAgentResponse(session_id="patch-session", text=json.dumps(baseline)),
        ]))

    pending = run(1)
    assert pending.status == "需要核对"
    assert pending.final_output is None
    assert pending.attempts[1].raw_output_text == policy_reply
    complete = run(2)
    assert complete.status == "已解析", [attempt.issues for attempt in complete.attempts]
    assert complete.final_output is not None
    assert complete.attempts[1].raw_output_text == policy_reply
    assert complete.final_output.candidates[1].title == second.title
    assert complete.partial_wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0].evaluation.observation_policy.scope == policy["scope"]


def test_policy_patch_rejects_other_atom_quote_before_staging() -> None:
    baseline = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit()).model_dump(mode="json")
    atom = baseline["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]
    atom["evaluation"]["observation_policy"] = None
    snapshot = deepcopy(baseline)
    with pytest.raises(ProtocolControlAgentWireValidationError, match="原文不属于所在控制原子"):
        _merge_observation_policy_repair(json.dumps({"items": [{
            "layer": "obligation", "group_index": 0, "atom_index": 0,
            "policy": {"mode": "unresolved", "scope": "未明确",
                       "source_span_ids": ["span:02"], "source_excerpts": ["另一项原文"]},
        }]}), baseline, 0, (("obligation", 0, 0),))
    assert baseline == snapshot


def test_runner_uses_policy_only_repair_for_one_missing_policy() -> None:
    batch = _batch()
    initial = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit()).model_dump(mode="json")
    atom = initial["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]
    atom["evaluation"]["observation_policy"] = None

    class PolicyTransport(_FakeTransport):
        def continue_atom(self, *, session_id: str, prompt: str):
            raise AssertionError("仅缺观察规则不得重写整个原子")

        def continue_observation_policies(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"items": [{
                    "group_index": 0, "atom_index": 0,
                    "policy": {
                        "mode": "unresolved", "scope": "原文未说明采用哪次记录",
                        "source_span_ids": ["span:01"],
                        "source_excerpts": ["年龄至少18岁"],
                    },
                }]}),
            )

    transport = PolicyTransport([
        ProtocolControlAgentResponse(session_id="single-policy", text=json.dumps(initial))
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(batch, transport)
    assert result.status == "已解析"
    assert result.final_output is not None
    assert len(result.attempts) == 2


@pytest.mark.parametrize("failure", [None, "field_only", "quote", "session", "budget", "missing_reader"])
def test_multiple_candidates_missing_policy_use_only_frozen_field_repairs(failure) -> None:
    original = _wire_with_two_candidates(
        _candidate().model_copy(update={"exception_expression": None}),
        _candidate_for_second_unit().model_copy(update={"exception_expression": None}),
    ).model_dump(mode="json")
    second_atom = original["candidate_drafts"][1]["obligation_expression"]["groups"][0]["atoms"][0]
    second_atom["evaluation"] = _evaluation(
        second_atom["statement"], second_atom["source_span_ids"][0], second_atom["source_excerpts"][0],
    )
    original = ProtocolControlAgentWire.model_validate(original).model_dump(mode="json")
    initial = deepcopy(original)
    for draft in initial["candidate_drafts"]:
        draft["obligation_expression"]["groups"][0]["atoms"][0]["evaluation"]["observation_policy"] = None
    snapshot = deepcopy(initial)
    expected = deepcopy(initial)

    class PolicyTransport(_FakeTransport):
        policy_calls = 0

        def continue_observation_policies(self, *, session_id, prompt):
            index = self.policy_calls
            self.policy_calls += 1
            atom = initial["candidate_drafts"][index]["obligation_expression"]["groups"][0]["atoms"][0]
            policy = {
                "mode": "unresolved", "scope": "原文未明确采用哪次记录",
                "source_span_ids": atom["source_span_ids"],
                "source_excerpts": atom["source_excerpts"],
            }
            expected["candidate_drafts"][index]["obligation_expression"]["groups"][0]["atoms"][0]["evaluation"]["observation_policy"] = policy
            if failure == "quote":
                other = initial["candidate_drafts"][1 - index]["obligation_expression"]["groups"][0]["atoms"][0]
                policy = {**policy, "source_span_ids": other["source_span_ids"],
                          "source_excerpts": other["source_excerpts"]}
            assert "仅为列出的条件或义务原子补充观察采用说明" in prompt
            return ProtocolControlAgentResponse(
                session_id="foreign-session" if failure == "session" else session_id,
                text=json.dumps({"items": [{
                    "layer": "obligation", "group_index": 0, "atom_index": 0, "policy": policy,
                }]}, ensure_ascii=False),
            )

        def continue_candidate(self, **kwargs):
            pytest.fail("缺少观察说明不能重写整条要求或退回整候选")

        def continue_session(self, **kwargs):
            pytest.fail("字段恢复失败不能扩大整批请求")

    transport = PolicyTransport([
        ProtocolControlAgentResponse(session_id="policies", text=json.dumps(initial)),
    ])
    if failure == "missing_reader":
        transport.continue_observation_policies = None
    elif failure == "field_only":
        transport.continue_candidate = None
    consumers = []
    from app.protocols.protocol_control_gate import validate_protocol_control_batch_candidates

    def consume(output):
        validate_protocol_control_batch_candidates(_batch(), output)
        consumers.append(output)

    result = ProtocolControlAgentRunner(max_schema_repairs=1 if failure == "budget" else 2).run(
        _batch(), transport, output_validator=consume,
    )
    assert initial == snapshot
    if failure in {None, "field_only"}:
        assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
        assert len(consumers) == 1
        assert result.partial_wire.model_dump(mode="json") == expected
        assert transport.policy_calls == 2
        assert len(transport.prompts) == 1
        assert len(result.attempts) == 4  # Final assembled validation is not another model call.
    else:
        assert result.status == "需要核对"
        assert result.final_output is None
        assert consumers == []
        assert transport.policy_calls == (0 if failure == "missing_reader" else 1)
        if failure == "budget":
            assert result.attempts[-1].error_classes == ["REPAIR_BUDGET_EXHAUSTED"]


def test_candidate_relative_policy_selector_rejects_other_errors() -> None:
    from pydantic import ValidationError
    from app.agents.protocol_control_deconstructor import _invalid_observation_policy_paths

    baseline = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit()).model_dump(mode="json")
    draft = baseline["candidate_drafts"][1]
    draft["obligation_expression"]["groups"][0]["atoms"][0]["evaluation"]["observation_policy"] = None
    with pytest.raises(ValidationError) as missing:
        ProtocolControlAgentWireCandidate.model_validate(draft)
    assert _invalid_observation_policy_paths(missing.value, baseline, 1) == (("obligation", 0, 0),)
    draft["title"] = ""
    with pytest.raises(ValidationError) as mixed:
        ProtocolControlAgentWireCandidate.model_validate(draft)
    assert _invalid_observation_policy_paths(mixed.value, baseline, 1) == ()


def test_multi_policy_probe_reuses_canonical_normalization_without_changing_raw() -> None:
    from pydantic import ValidationError
    from app.agents.protocol_control_deconstructor import _invalid_candidate_payload, _invalid_observation_policy_paths

    baseline = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit()).model_dump(mode="json")
    for draft in baseline["candidate_drafts"]:
        atom = draft["obligation_expression"]["groups"][0]["atoms"][0]
        atom["evaluation"]["observation_policy"] = None
        del atom["evaluation"]["source_span_ids"]
        del atom["evaluation"]["source_excerpts"]
        atom["time_constraint"] = {
            "anchor_type": "screening_date", "direction": "before",
            "upper_bound_days": None, "upper_bound_inclusive": False,
        }
        atom["evaluation"]["time_operand_attribute"] = "date_range"
        atom["evaluation"]["time_purpose"] = "interval_condition"
    raw = json.dumps(baseline)
    snapshot = deepcopy(baseline)
    salvaged, indexes = _invalid_candidate_payload(raw)
    assert indexes == (0, 1)
    assert baseline == snapshot
    assert raw == json.dumps(baseline)
    for index in indexes:
        with pytest.raises(ValidationError) as invalid:
            ProtocolControlAgentWireCandidate.model_validate(salvaged["candidate_drafts"][index])
        assert _invalid_observation_policy_paths(invalid.value, salvaged, index) == (("obligation", 0, 0),)
        atom = salvaged["candidate_drafts"][index]["obligation_expression"]["groups"][0]["atoms"][0]
        assert atom["evaluation"]["source_excerpts"] == atom["source_excerpts"]
        assert atom["time_constraint"]["upper_bound_inclusive"] is True
        assert atom["time_constraint"]["upper_bound_days"] is None


def test_time_operand_repair_is_exact_and_unresolved_stays_unverified() -> None:
    valid = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit())
    baseline = valid.model_dump(mode="json")
    atoms = baseline["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"]
    atoms.append(deepcopy(atoms[0]))
    for atom in atoms:
        atom["time_constraint"] = {
            "anchor_type": "screening_date", "direction": "before",
            "upper_bound_days": None, "upper_bound_inclusive": False,
        }
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


@pytest.mark.parametrize("changed_source", [False, True])
def test_candidate_repair_missing_dates_stays_local_and_checks_source(changed_source) -> None:
    initial = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit())
    draft = initial.candidate_drafts[0].model_dump(mode="json")
    atom = draft["obligation_expression"]["groups"][0]["atoms"][0]
    atom["time_constraint"] = {"anchor_type": "screening_date", "direction": "before"}
    atom["evaluation"]["time_purpose"] = "unresolved"
    atom["evaluation"]["time_operand_attribute"] = None
    if changed_source:
        draft["source_structure_unit_ids"] = ["su-02"]

    class DateTransport(_FakeTransport):
        date_calls = 0
        candidate_calls = 0

        def continue_candidate(self, *, session_id, prompt):
            self.candidate_calls += 1
            if self.candidate_calls > 1:
                raise RuntimeError("测试停止重复整候选回答")
            return ProtocolControlAgentResponse(
                session_id=session_id, text=json.dumps({"candidate_draft": draft}),
            )

        def continue_time_operands(self, *, session_id, prompt):
            self.date_calls += 1
            assert '"group_index":0' in prompt and '"atom_index":0' in prompt
            return ProtocolControlAgentResponse(session_id=session_id, text=json.dumps({
                "items": [{"group_index": 0, "atom_index": 0, "attribute": "record_time"}],
            }))

    seen = 0

    def validate(output):
        nonlocal seen
        seen += 1
        if seen == 1:
            raise ProtocolControlAgentWireValidationError(
                "PUBLICATION_GATE_REJECTED", "目标候选仍须局部核对",
                candidate_ids=[output.candidates[0].control_candidate_id],
                structure_unit_ids=["su-01"], obligation_source_span_ids=["span:01"],
            )

    transport = DateTransport([ProtocolControlAgentResponse(
        session_id="candidate-date", text=initial.model_dump_json(),
    )])
    result = ProtocolControlAgentRunner(max_schema_repairs=2, max_transport_retries=0).run(
        _batch(), transport, output_validator=validate,
    )
    if changed_source:
        assert transport.date_calls == 0
        assert result.final_output is None
    else:
        assert result.status == "已解析", [a.issues for a in result.attempts]
        assert transport.date_calls == 1 and transport.candidate_calls == 1
        assert seen == 2
        assert result.partial_wire is None or result.final_output is not None
        assert result.final_output.candidates[1].title == initial.candidate_drafts[1].title
        assert result.final_output.candidates[0].semantics.obligation_expression.groups[0].atoms[0].evaluation.time_operand_attribute == "record_time"


def test_single_missing_time_operand_repairs_only_that_field() -> None:
    initial = _wire(candidate=_candidate()).model_dump(mode="json")
    atom = initial["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]
    atom["time_constraint"] = {"anchor_type": "screening_date", "direction": "after"}
    atom["evaluation"]["time_purpose"] = "unresolved"
    atom["evaluation"]["time_operand_attribute"] = None

    class FocusedTransport(_FakeTransport):
        def continue_time_operands(self, *, session_id: str, prompt: str):
            assert "record_time" in prompt and "date_range" in prompt
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"items": [{
                    "group_index": 0, "atom_index": 0, "attribute": "record_time",
                }]}),
            )

        def continue_atom(self, *, session_id: str, prompt: str):
            pytest.fail("单字段缺失不应让模型重写完整义务原子")

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        _batch(), FocusedTransport([
            ProtocolControlAgentResponse(session_id="one-date", text=json.dumps(initial))
        ]),
    )
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert result.final_output is not None
    repaired = result.final_output.candidates[0].semantics.obligation_expression.groups[0].atoms[0]
    assert repaired.evaluation.time_operand_attribute == "record_time"
    assert repaired.time_constraint.anchor_type.value == "screening_date"


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


@pytest.mark.parametrize("failure", [None, "budget", "unresolved", "scope", "session", "transport", "consumer"])
def test_multiple_candidate_repair_uses_typed_dates_without_rewriting_siblings(failure) -> None:
    valid = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit())
    initial = valid.model_dump(mode="json")
    for draft in initial["candidate_drafts"]:
        del draft["obligation_expression"]["groups"][0]["atoms"][0]["evaluation"]
    proposal = valid.candidate_drafts[0].model_dump(mode="json")
    atom = proposal["obligation_expression"]["groups"][0]["atoms"][0]
    atom["time_constraint"] = {"anchor_type": "screening_date", "direction": "before"}
    atom["evaluation"]["time_purpose"] = "unresolved"
    atom["evaluation"]["time_operand_attribute"] = None
    if failure == "scope":
        proposal["source_structure_unit_ids"] = ["su-02"]

    class Transport(_FakeTransport):
        candidate_calls = 0
        date_calls = 0

        def continue_candidate(self, *, session_id, prompt):
            self.candidate_calls += 1
            assert self.candidate_calls <= 2
            draft = proposal if self.candidate_calls == 1 else valid.candidate_drafts[1].model_dump(mode="json")
            return ProtocolControlAgentResponse(session_id=session_id, text=json.dumps({"candidate_draft": draft}))

        def continue_time_operands(self, *, session_id, prompt):
            self.date_calls += 1
            assert self.date_calls == 1
            assert valid.candidate_drafts[1].title not in prompt
            if failure == "transport":
                raise RuntimeError("synthetic transport failure")
            return ProtocolControlAgentResponse(
                session_id="other-session" if failure == "session" else session_id,
                text=json.dumps({"items": [{"group_index": 0, "atom_index": 0,
                                           "attribute": "unresolved" if failure == "unresolved" else "record_time"}]}),
            )

        def continue_session(self, **kwargs):
            pytest.fail("不得退回整批重写")

    consumer_calls = 0

    def validate(output):
        nonlocal consumer_calls
        consumer_calls += 1
        expected_sibling = hydrate_protocol_control_agent_output(valid, _batch()).candidates[1]
        assert output.candidates[1] == expected_sibling
        if failure == "consumer":
            raise ProtocolControlAgentWireValidationError("PUBLICATION_GATE_REJECTED", "synthetic semantic rejection")

    transport = Transport([ProtocolControlAgentResponse(session_id="multi-dates", text=json.dumps(initial))])
    result = ProtocolControlAgentRunner(max_schema_repairs=1 if failure == "budget" else 3).run(
        _batch(), transport, output_validator=validate,
    )
    assert initial["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0].get("evaluation") is None
    assert atom["evaluation"]["time_operand_attribute"] is None
    if failure is None:
        assert result.status == "已解析", [a.issues for a in result.attempts]
        assert transport.candidate_calls == 2 and transport.date_calls == 1
        assert consumer_calls == 1
        assert result.final_output.candidates[0].semantics.obligation_expression.groups[0].atoms[0].evaluation.time_operand_attribute == "record_time"
        assert result.final_output.candidates[1] == hydrate_protocol_control_agent_output(valid, _batch()).candidates[1]
        assert any(a.error_classes == ["CANDIDATE_REPAIR_INVALID"] for a in result.attempts)
    else:
        assert result.final_output is None
        assert transport.date_calls == (0 if failure in {"budget", "scope"} else 1)
        if failure == "unresolved":
            assert result.attempts[-1].error_classes == ["TIME_OPERAND_UNRESOLVED"]


@pytest.mark.parametrize("failure", [None, "scope", "other_error", "unresolved", "budget"])
def test_plural_candidate_transport_missing_date_keeps_typed_followup(failure) -> None:
    valid = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit())
    initial = valid.model_dump(mode="json")
    for draft in initial["candidate_drafts"]:
        del draft["obligation_expression"]["groups"][0]["atoms"][0]["evaluation"]
    proposals = [draft.model_dump(mode="json") for draft in valid.candidate_drafts]
    atom = proposals[1]["obligation_expression"]["groups"][0]["atoms"][0]
    atom["time_constraint"] = {"anchor_type": "screening_date", "direction": "before"}
    atom["evaluation"]["time_purpose"] = "unresolved"
    atom["evaluation"]["time_operand_attribute"] = None
    if failure == "scope":
        proposals[1]["source_structure_unit_ids"] = ["su-01"]
    elif failure == "other_error":
        proposals[0]["title"] = ""

    class Transport(_FakeTransport):
        date_calls = 0
        plural_calls = 0

        def continue_candidates(self, *, session_id, prompt):
            self.plural_calls += 1
            assert self.plural_calls == 1
            return ProtocolControlAgentResponse(session_id=session_id, text=json.dumps({"candidate_drafts": proposals}))

        def continue_time_operands(self, *, session_id, prompt):
            self.date_calls += 1
            assert valid.candidate_drafts[0].title not in prompt
            return ProtocolControlAgentResponse(session_id=session_id, text=json.dumps({"items": [{
                "group_index": 0, "atom_index": 0,
                "attribute": "unresolved" if failure == "unresolved" else "record_time",
            }]}))

        def continue_session(self, **kwargs):
            raise RuntimeError("reject whole-wire fallback in synthetic fixture")

    transport = Transport([ProtocolControlAgentResponse(session_id="plural-dates", text=json.dumps(initial))])
    result = ProtocolControlAgentRunner(max_schema_repairs=1 if failure == "budget" else 2).run(_batch(), transport)
    if failure is None:
        assert result.status == "已解析", [a.issues for a in result.attempts]
        expected = hydrate_protocol_control_agent_output(valid, _batch()).candidates[0]
        assert result.final_output.candidates[0] == expected
        assert result.final_output.candidates[1].semantics.obligation_expression.groups[0].atoms[0].evaluation.time_operand_attribute == "record_time"
        assert transport.plural_calls == transport.date_calls == 1
    else:
        assert result.final_output is None
        assert transport.date_calls == (1 if failure == "unresolved" else 0)


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


def _candidate_findings(output, codes):
    return publication_repair_error(
        issues=[SimpleNamespace(
            code=code, message="该要求的独立字段需核对",
            entity_id=candidate.control_candidate_id,
            candidate_ids=[], structure_unit_ids=[], obligation_source_span_ids=[],
        ) for candidate, code in zip(output.candidates, codes)],
        candidate_by_id={c.control_candidate_id: c for c in output.candidates},
        control_to_candidate={}, default_structure_unit_ids=["su-01", "su-02"],
    )


@pytest.mark.parametrize("failure", [None, "budget", "transport", "escape", "numeric"])
def test_independent_publication_findings_repair_one_candidate_and_revalidate_all(failure):
    first, second = _candidate(), _candidate_for_second_unit()
    initial = _wire_with_two_candidates(first, second)
    repaired = [c.model_copy(update={"title": c.title + "（已核）"}) for c in (first, second)]

    class ScopedTransport(_FakeTransport):
        def continue_candidate(self, *, session_id, prompt):
            self.prompts.append(prompt)
            index = len(self.prompts) - 2
            if failure == "transport" and index == 1:
                raise RuntimeError("test transport unavailable")
            if failure == "escape":
                return ProtocolControlAgentResponse(session_id=session_id, text=json.dumps({
                    "candidate_draft": repaired[1].model_dump(mode="json"),
                }))
            return ProtocolControlAgentResponse(session_id=session_id, text=json.dumps({
                "candidate_draft": repaired[index].model_dump(mode="json"),
            }))

        def continue_session(self, **kwargs):
            pytest.fail("两个独立要求不能合并成整批改写")

    calls = 0

    def validate(output):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _candidate_findings(output, [
                "FIRST_FIELD_INVALID", "NUMERIC_VALUE_NOT_IN_SOURCE"
                if failure == "numeric" else "SECOND_FIELD_INVALID",
            ])
        assert output.candidates[0].title == repaired[0].title
        if calls == 2:
            assert output.candidates[1].title == second.title
            raise publication_repair_error(
                issues=[SimpleNamespace(
                    code="SECOND_FIELD_INVALID", message="另一条要求仍需核对",
                    entity_id=output.candidates[1].control_candidate_id,
                )],
                candidate_by_id={c.control_candidate_id: c for c in output.candidates},
                control_to_candidate={}, default_structure_unit_ids=["su-01", "su-02"],
            )
        assert output.candidates[1].title == repaired[1].title

    transport = ScopedTransport([
        ProtocolControlAgentResponse(session_id="scoped-findings", text=initial.model_dump_json()),
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=1 if failure == "budget" else 2).run(
        _batch(), transport, output_validator=validate,
    )
    assert result.status == ("已解析" if failure is None else "需要核对")
    assert initial.candidate_drafts == [first, second]
    receipt = result.attempts[0]
    assert len(receipt.error_detail["findings"]) == 2
    assert len(receipt.error_detail["repair_candidate_ids"]) == 1
    assert "FIRST_FIELD_INVALID" in receipt.error_classes
    if failure == "numeric":
        assert "NUMERIC_VALUE_NOT_IN_SOURCE" in receipt.error_classes
        assert len(transport.prompts) == 1
    if failure is None:
        assert calls == 3
        assert result.partial_wire.candidate_drafts == repaired
        assert result.final_output is not None
    else:
        assert result.final_output is None


@pytest.mark.parametrize("unscoped", ["unknown", "cross", "outside_units", "structural", "unknown_with_structure"])
def test_publication_scope_never_guesses_unknown_or_structural_ownership(unscoped):
    output = hydrate_protocol_control_agent_output(
        _wire_with_two_candidates(_candidate(), _candidate_for_second_unit()), _batch(),
    )
    error = _candidate_findings(output, ["FIRST_FIELD_INVALID", "SECOND_FIELD_INVALID"])
    assert len(error.repair_scopes) == 2
    issues = [SimpleNamespace(**finding, message="待核字段") for finding in error.validation_findings]
    if unscoped == "unknown":
        issues[1].entity_id = "unknown-candidate"
    elif unscoped == "cross":
        issues[1].candidate_ids = [c.control_candidate_id for c in output.candidates]
    elif unscoped == "outside_units":
        issues[1].structure_unit_ids = ["su-01"]
    elif unscoped == "unknown_with_structure":
        issues[0].entity_id = "unknown-candidate"
        issues[1].code = "ACTION_TARGET_SCOPE_MISMATCH"
    else:
        issues[1].code = "ACTION_TARGET_SCOPE_MISMATCH"
    error = publication_repair_error(
        issues=issues, candidate_by_id={c.control_candidate_id: c for c in output.candidates},
        control_to_candidate={}, default_structure_unit_ids=["su-01", "su-02"],
    )
    assert not error.repair_scopes
    assert len(error.validation_findings) == 2
    assert error.repair_scope_unknown == (unscoped != "structural")
    if unscoped != "structural":
        transport = _FakeTransport([ProtocolControlAgentResponse(
            session_id="unknown-owner", text=_wire_with_two_candidates(
                _candidate(), _candidate_for_second_unit(),
            ).model_dump_json(),
        )])

        def reject(output):
            raise error

        result = ProtocolControlAgentRunner(max_schema_repairs=2).run(
            _batch(), transport, output_validator=reject,
        )
        assert result.status == "需要核对"
        assert result.final_output is None and len(transport.prompts) == 1
        assert any("机器可读修订范围" in text for text in result.attempts[-1].issues)


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


def test_source_insert_prompt_names_only_frozen_missing_prohibition() -> None:
    from app.agents.protocol_control_deconstructor import build_protocol_control_repair_prompt

    batch = _batch()
    missing = "任一项未满足，不得进入下一审核节点。"
    batch.owned_units[0].excerpt = "先完成资料核对；" + missing
    prompt = build_protocol_control_repair_prompt(
        batch, problem="ENROLLMENT_PROHIBITION_UNCOVERED",
        structure_unit_ids=["su-01"], source_insert=True,
        missing_source_statements=[missing],
    )
    assert "尚未形成独立候选的原句" in prompt
    assert missing in prompt
    assert "su-02" not in prompt.split("已由本批来源清单识别、但尚未形成独立候选的原句")[1].split("候选草稿位置")[0]


def test_partial_same_source_prohibition_uses_bounded_regrouping() -> None:
    from app.agents.protocol_control_deconstructor import build_protocol_control_repair_prompt

    issue = SimpleNamespace(
        code="ENROLLMENT_PROHIBITION_UNCOVERED", message="禁止要求尚未完整表达",
        entity_id="su-01", candidate_ids=[], structure_unit_ids=["su-01"],
        obligation_source_span_ids=["span:01"],
    )
    candidate = SimpleNamespace(
        frozen_structure_unit_ids=["su-01"],
        semantics=SimpleNamespace(obligation_expression=SimpleNamespace(groups=[
            SimpleNamespace(atoms=[SimpleNamespace(kind="prohibit_event")])
        ])),
    )
    error = publication_repair_error(
        issues=[issue], candidate_by_id={"candidate-existing": candidate},
        control_to_candidate={}, default_structure_unit_ids=["su-01", "su-02"],
    )
    assert error.allow_source_closure_rewrite
    assert not error.allow_source_insert
    assert error.candidate_ids == ("candidate-existing",)
    assert error.structure_unit_ids == ("su-01",)
    prompt = build_protocol_control_repair_prompt(
        _batch(), problem=str(error), structure_unit_ids=error.structure_unit_ids,
        source_closure_rewrite=True,
        missing_source_statements=["任一项未满足，不得进入下一审核节点。"],
        source_statement_inventory=[
            ("required", "进入下一审核节点前完成资料处理。"),
            ("prohibited", "任一项未满足，不得进入下一审核节点。"),
        ],
    )
    assert "替换或拆分旧候选" in prompt
    assert "不要在旧候选后仅追加近似候选" in prompt
    assert "进入下一审核节点前完成资料处理" in prompt


@pytest.mark.parametrize("still_missing", [False, True])
def test_two_separately_scoped_source_insertions_preserve_prior_candidate(
    still_missing: bool,
) -> None:
    first = _candidate()
    second = _candidate_for_second_unit()
    transport = _FakeTransport([
        ProtocolControlAgentResponse(session_id="insert-progress", text=_wire().model_dump_json()),
        ProtocolControlAgentResponse(
            session_id="insert-progress", text=_wire(candidate=first).model_dump_json(),
        ),
        ProtocolControlAgentResponse(
            session_id="insert-progress",
            text=_wire_with_two_candidates(first, second).model_dump_json(),
        ),
    ])
    calls = 0

    def validate(output) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _missing_source_error()
        if calls == 2:
            assert [item.title for item in output.candidates] == [first.title]
            raise publication_repair_error(
                issues=[SimpleNamespace(
                    code="ENROLLMENT_PROHIBITION_UNCOVERED",
                    message="第二个来源要求尚未形成候选",
                    entity_id="su-02",
                    candidate_ids=[],
                    structure_unit_ids=["su-02"],
                    obligation_source_span_ids=["span:02"],
                )],
                candidate_by_id={},
                control_to_candidate={},
                default_structure_unit_ids=["su-01", "su-02"],
            )
        assert [item.title for item in output.candidates] == [first.title, second.title]
        if still_missing:
            raise _missing_source_error()

    result = ProtocolControlAgentRunner(max_schema_repairs=0).run(
        _batch(), transport, output_validator=validate,
    )
    assert result.status == ("需要核对" if still_missing else "已解析")
    assert calls == 3
    assert len(transport.prompts) == 3
    if not still_missing:
        assert result.final_output is not None
        assert len(result.final_output.candidates) == 2


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


@pytest.mark.parametrize("drop_target", [False, True])
@pytest.mark.parametrize("prior_candidate", [False, True])
def test_successful_source_insert_allows_one_bounded_candidate_correction(drop_target, prior_candidate) -> None:
    initial = _wire(candidate=_candidate_for_second_unit()) if prior_candidate else _wire()
    if prior_candidate:
        initial.dispositions[1].disposition = StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
    initial.dispositions[0] = ProtocolControlAgentWireDisposition(
        structure_unit_id="su-01",
        disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
        linked_official_code=None,
        linked_procedure_catalog_item_id="procedure-screening-1",
        linked_procedure_catalog_item_ids=[],
        notes=None,
    )
    inserted = initial.model_dump(mode="json")
    inserted["dispositions"][0]["disposition"] = "other_control_candidate"
    inserted["dispositions"][0]["linked_procedure_catalog_item_id"] = None
    inserted["candidate_drafts"].append(_candidate().model_dump(mode="json"))
    inserted["candidate_drafts"][-1]["cross_source_relations"] = [{
        "kind": "supplementary_requirement",
        "external_target_kind": "required_procedure",
        "external_target_id": "procedure-screening-1",
        "candidate_side": "left",
        "affected_workflow_stage_id": "stage:screening:one",
        "notes": None,
    }]
    corrected = _candidate().model_dump(mode="json")
    corrected["title"] = "已核对的年龄资料控制"
    corrected["cross_source_relations"] = inserted["candidate_drafts"][-1]["cross_source_relations"]
    if drop_target:
        corrected["cross_source_relations"] = []
    if prior_candidate and not drop_target:
        before = ProtocolControlAgentWire.model_validate(inserted)
        after = before.model_copy(deep=True)
        after.candidate_drafts[-1] = ProtocolControlAgentWireCandidate.model_validate(corrected)
        reordered, _ = _restore_bounded_wire_repair(
            before, after, mutable_structure_unit_ids={"su-01"},
            mutable_candidate_source_keys={("su-01",)},
        )
        with pytest.raises(ProtocolControlAgentWireValidationError, match="REPAIR_SCOPE_ESCAPE"):
            _restore_bounded_wire_repair(
                initial, reordered, mutable_structure_unit_ids={"su-01"},
                mutable_obligation_source_span_ids={"span:01"}, allow_source_insert=True,
            )
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
            candidate = next(item for item in output.candidates
                             if item.frozen_structure_unit_ids == ["su-01"])
            raise ProtocolControlAgentWireValidationError(
                "PUBLICATION_GATE_REJECTED", "审核指引缺少来源",
                candidate_ids=[candidate.control_candidate_id],
                structure_unit_ids=["su-01"],
            )
        candidate = next(item for item in output.candidates
                         if item.frozen_structure_unit_ids == ["su-01"])
        assert candidate.title == corrected["title"]

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        _batch(), transport, output_validator=validate,
    )
    if drop_target:
        assert result.status == "需要核对"
        assert result.final_output is None
        assert "REPAIR_SCOPE_ESCAPE" in result.attempts[-1].error_classes
        assert calls == 2
        return
    assert result.status == "已解析", [(item.outcome, item.issues) for item in result.attempts]
    assert calls == 3
    if prior_candidate:
        assert result.partial_wire.candidate_drafts[0] == initial.candidate_drafts[0]
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


@pytest.mark.parametrize("shared_source_sibling", [False, True])
def test_future_prohibition_patch_splits_only_current_text_and_continuation(shared_source_sibling) -> None:
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
    if shared_source_sibling:
        sibling = _candidate().model_dump(mode="json")["obligation_expression"]["groups"][0]["atoms"][0]
        sibling["kind"] = ControlObligationKind.MUST_RECORD.value
        draft["obligation_expression"]["groups"][0]["atoms"].append(sibling)
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
                obligation_source_span_ids=["span:01"],
                error_class_codes=["FUTURE_PROHIBITION_DECIDED_EARLY"],
            )

    result = ProtocolControlAgentRunner(max_schema_repairs=0).run(
        batch, transport, output_validator=reject_future_once
    )
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert len(result.attempts) == 2
    if shared_source_sibling:
        assert result.final_output.candidates[0].semantics.obligation_expression.groups[0].atoms[1].statement == sibling["statement"]
        assert result.final_output.candidates[0].semantics.obligation_expression.groups[0].atoms[1].evaluation == initial.candidate_drafts[0].obligation_expression.groups[0].atoms[1].evaluation

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
    treatment_duration_error = ProtocolControlAgentWireValidationError(
        "PUBLICATION_GATE_REJECTED", "持续治疗时长不是事件窗口",
        structure_unit_ids=["su-01"], candidate_indexes=[0],
        obligation_source_span_ids=["span:01"],
        error_class_codes=["TREATMENT_DURATION_USED_AS_EVENT_WINDOW"],
    )
    assert _calendar_bound_repair_path(treatment_duration_error, initial, {0}) is None
    assert _treatment_duration_atom_repair_path(treatment_duration_error, initial, {0}) == path
    assert _treatment_duration_atom_repair_path(treatment_duration_error, initial, {0, 1}) is None
    assert _calendar_bound_repair_path(treatment_duration_error, initial, {0, 1}) is None
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
    unwrapped = _merge_calendar_bound_repair(json.dumps(patch["time_constraint"]), initial, path)
    assert unwrapped == merged
    absent_bound_flags = {
        "time_constraint": {
            "anchor_type": "screening_date", "direction": "on",
            "lower_bound_days": None, "upper_bound_days": None,
            "lower_bound_inclusive": None, "upper_bound_inclusive": None,
        }, "time_purpose": None,
    }
    flexible_payload = initial.model_dump(mode="json")
    flexible_payload["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]["kind"] = (
        ControlObligationKind.MUST_RECORD.value
    )
    flexible = ProtocolControlAgentWire.model_validate(flexible_payload)
    no_bound = _merge_calendar_bound_repair(json.dumps(absent_bound_flags), flexible, path)
    assert no_bound.candidate_drafts[0].obligation_expression.groups[0].atoms[0].time_constraint.direction.value == "on"
    with pytest.raises(ProtocolControlAgentWireValidationError, match="CALENDAR_BOUND_REPAIR_INVALID"):
        _merge_calendar_bound_repair(json.dumps({
            "time_constraint": {**absent_bound_flags["time_constraint"],
                                "direction": "before", "upper_bound_days": 7},
        }), flexible, path)
    with pytest.raises(ProtocolControlAgentWireValidationError, match="CALENDAR_BOUND_REPAIR_INVALID"):
        _merge_calendar_bound_repair(
            json.dumps({**patch["time_constraint"], "unsupported_field": "not from source"}),
            initial, path,
        )
    prior = initial.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    assert changed.model_copy(update={"time_constraint": prior.time_constraint}) == prior
    assert protocol_control_calendar_bound_repair_response_format()["json_schema"]["name"] == "protocol_control_calendar_bound_repair_v2"
    from app.agents.protocol_control_deconstructor import _build_calendar_bound_repair_prompt
    repair_prompt = _build_calendar_bound_repair_prompt(initial, path)
    assert "time_constraint:null" in repair_prompt
    assert "upper_bound_days" in repair_prompt
    assert "顶层只能有 time_constraint 与 time_purpose" in repair_prompt
    assert "不是零天的数值窗口" in repair_prompt
    assert '"screening_date"' in repair_prompt
    assert '"on"' in repair_prompt
    assert "筛选期、导入期等时期名称不是 anchor_type" in repair_prompt
    assert "示例只说明格式" in repair_prompt
    scoped_prompt = _build_calendar_bound_repair_prompt(initial, path, batch=_batch())
    assert "冻结访视" in scoped_prompt
    assert "不能把名称中的相对日标记直接充当" in scoped_prompt
    with pytest.raises(ProtocolControlAgentWireValidationError, match="CALENDAR_BOUND_REPAIR_INVALID"):
        _merge_calendar_bound_repair(json.dumps({"time_constraint": None}), initial, path)
    optional_window_payload = initial.model_dump(mode="json")
    optional_window_payload["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]["kind"] = ControlObligationKind.MUST_RECORD.value
    optional_window = ProtocolControlAgentWire.model_validate(optional_window_payload)
    no_window = _merge_calendar_bound_repair(json.dumps({
        "time_constraint": None, "time_purpose": "not_applicable",
    }), optional_window, path)
    no_window_atom = no_window.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    assert no_window_atom.time_constraint is None
    assert no_window_atom.evaluation.time_purpose == "not_applicable"
    assert no_window_atom.evaluation.time_operand_attribute is None

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


def test_calendar_repair_selects_same_source_siblings_one_at_a_time() -> None:
    first = _candidate().model_dump(mode="json")
    atom = first["obligation_expression"]["groups"][0]["atoms"][0]
    atom["time_constraint"] = {
        "anchor_type": "screening_date", "direction": "after", "lower_bound_days": 0,
    }
    atom["kind"] = ControlObligationKind.COMPLETE_OR_VERIFY.value
    atom["evaluation"] = _timed_evaluation(atom["statement"], "span:01", "年龄至少18岁")
    atom["evaluation"]["time_purpose"] = "interval_condition"
    second = deepcopy(first)
    second["title"] = "另一访视独立核对"
    wire_payload = _wire(candidate=_candidate()).model_dump(mode="json")
    wire_payload["candidate_drafts"] = [first, second]
    initial = ProtocolControlAgentWire.model_validate(wire_payload)
    error = ProtocolControlAgentWireValidationError(
        "PUBLICATION_GATE_REJECTED", "两条候选的零天边界均无原文支持",
        candidate_indexes=[0, 1], obligation_source_span_ids=["span:01"],
        error_class_codes=["TIME_CALENDAR_BOUND_UNSUPPORTED"],
    )
    assert _calendar_bound_repair_path(error, initial, {0, 1}) == (0, 0, 0)
    patch = {"time_constraint": {"anchor_type": "screening_date", "direction": "after"}}
    once = _merge_calendar_bound_repair(json.dumps(patch), initial, (0, 0, 0))
    assert once.candidate_drafts[1] == initial.candidate_drafts[1]
    assert _calendar_bound_repair_path(error, once, {1}) == (1, 0, 0)
    twice = _merge_calendar_bound_repair(json.dumps(patch), once, (1, 0, 0))
    assert all(
        candidate.obligation_expression.groups[0].atoms[0].time_constraint.lower_bound_days is None
        for candidate in twice.candidate_drafts
    )
    ambiguous = initial.model_dump(mode="json")
    ambiguous["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"].append(
        deepcopy(atom)
    )
    assert _calendar_bound_repair_path(
        error, ProtocolControlAgentWire.model_validate(ambiguous), {0, 1}
    ) is None


def test_runner_repairs_same_source_calendar_candidates_without_rewriting_siblings() -> None:
    first = _candidate().model_dump(mode="json")
    first_atom = first["obligation_expression"]["groups"][0]["atoms"][0]
    first_atom["time_constraint"] = {
        "anchor_type": "screening_date", "direction": "after", "lower_bound_days": 0,
    }
    first_atom["kind"] = ControlObligationKind.COMPLETE_OR_VERIFY.value
    first_atom["evaluation"] = _timed_evaluation(first_atom["statement"], "span:01", "年龄至少18岁")
    first_atom["evaluation"]["time_purpose"] = "interval_condition"
    second = deepcopy(first)
    second["title"] = "另一项独立核对"
    second["obligation_expression"]["groups"][0]["atoms"][0]["statement"] = "另一项年龄核对"
    second["obligation_expression"]["groups"][0]["atoms"][0]["evaluation"]["proposition"] = "另一项年龄核对"
    payload = _wire(candidate=_candidate()).model_dump(mode="json")
    payload["candidate_drafts"] = [first, second]
    initial = ProtocolControlAgentWire.model_validate(payload)

    class CalendarTransport(_FakeTransport):
        repair_calls = 0

        def continue_calendar_bound_repair(self, *, session_id: str, prompt: str):
            self.repair_calls += 1
            assert session_id == "same-source-calendar"
            expected_statement = "另一项年龄核对" if self.repair_calls == 2 else "年龄达到18岁"
            assert expected_statement in prompt
            return ProtocolControlAgentResponse(session_id=session_id, text=json.dumps({
                "time_constraint": {"anchor_type": "screening_date", "direction": "after"},
            }))

        def continue_candidates(self, *, session_id: str, prompt: str):
            pytest.fail("同源候选的时间边界不得交由整组重写")

    transport = CalendarTransport([
        ProtocolControlAgentResponse(session_id="same-source-calendar", text=initial.model_dump_json())
    ])
    seen = []

    def reject_unsupported_bound(output) -> None:
        seen.append([(candidate.control_candidate_id, candidate.title) for candidate in output.candidates])
        invalid = [
            candidate.control_candidate_id for candidate in output.candidates
            if candidate.semantics.obligation_expression.groups[0].atoms[0].time_constraint.lower_bound_days is not None
        ]
        if invalid:
            raise ProtocolControlAgentWireValidationError(
                "PUBLICATION_GATE_REJECTED", "两个来源相同但独立的零天边界没有原文支持",
                structure_unit_ids=["su-01"], candidate_ids=invalid,
                obligation_source_span_ids=["span:01"],
                error_class_codes=["TIME_CALENDAR_BOUND_UNSUPPORTED"],
            )

    result = ProtocolControlAgentRunner(max_schema_repairs=0).run(
        _batch(), transport, output_validator=reject_unsupported_bound,
    )
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert transport.repair_calls == 2
    assert seen[0][1] == seen[1][1]
    assert result.final_output is not None
    assert all(
        candidate.semantics.obligation_expression.groups[0].atoms[0].time_constraint.lower_bound_days is None
        for candidate in result.final_output.candidates
    )


def test_runner_stops_ambiguous_same_source_calendar_repair() -> None:
    draft = _candidate().model_dump(mode="json")
    atom = draft["obligation_expression"]["groups"][0]["atoms"][0]
    atom["time_constraint"] = {
        "anchor_type": "screening_date", "direction": "after", "lower_bound_days": 0,
    }
    atom["evaluation"] = _timed_evaluation(atom["statement"], "span:01", "年龄至少18岁")
    second_atom = deepcopy(atom)
    second_atom["statement"] = "同段的另一时间要求"
    second_atom["evaluation"]["proposition"] = "同段的另一时间要求"
    draft["obligation_expression"]["groups"][0]["atoms"].append(second_atom)
    second = deepcopy(draft)
    second["title"] = "另一候选"
    payload = _wire(candidate=_candidate()).model_dump(mode="json")
    payload["candidate_drafts"] = [draft, second]
    initial = ProtocolControlAgentWire.model_validate(payload)

    class AmbiguousTransport(_FakeTransport):
        def continue_calendar_bound_repair(self, *, session_id: str, prompt: str):
            pytest.fail("一个候选有两个匹配时间原子时不得猜测修订对象")

        def continue_candidates(self, *, session_id: str, prompt: str):
            pytest.fail("歧义不能退回整组改写")

    def reject_ambiguous(output) -> None:
        raise ProtocolControlAgentWireValidationError(
            "PUBLICATION_GATE_REJECTED", "时间要求无法逐条定位",
            structure_unit_ids=["su-01"],
            candidate_ids=[candidate.control_candidate_id for candidate in output.candidates],
            obligation_source_span_ids=["span:01"],
            error_class_codes=["TIME_CALENDAR_BOUND_UNSUPPORTED"],
        )

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        _batch(), AmbiguousTransport([
            ProtocolControlAgentResponse(session_id="ambiguous-calendar", text=initial.model_dump_json())
        ]), output_validator=reject_ambiguous,
    )
    assert result.status == "需要核对"
    assert any("无法逐条定位" in issue for issue in result.attempts[-1].issues)


@pytest.mark.parametrize("shared_source_sibling", [False, True])
def test_treatment_duration_repair_uses_one_atom_not_calendar_or_candidate(shared_source_sibling) -> None:
    draft = _candidate().model_dump(mode="json")
    atom = draft["obligation_expression"]["groups"][0]["atoms"][0]
    atom["time_constraint"] = {
        "anchor_type": "screening_date", "direction": "before", "upper_bound_days": 7,
    }
    atom["evaluation"] = _timed_evaluation(atom["statement"], "span:01", "年龄至少18岁")
    if shared_source_sibling:
        sibling = _candidate().model_dump(mode="json")["obligation_expression"]["groups"][0]["atoms"][0]
        sibling["kind"] = ControlObligationKind.MUST_RECORD.value
        sibling["statement"] = "记录年龄资料"
        sibling["evaluation"] = _evaluation(sibling["statement"], "span:01", "年龄至少18岁")
        draft["obligation_expression"]["groups"][0]["atoms"].append(sibling)
    initial = _wire(candidate=ProtocolControlAgentWireCandidate.model_validate(draft))
    repaired_atom = deepcopy(atom)
    repaired_atom["time_constraint"] = None
    repaired_atom["evaluation"]["time_purpose"] = "unresolved"
    repaired_atom["evaluation"]["time_operand_attribute"] = None

    class AtomTransport(_FakeTransport):
        def continue_atom(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            assert "只能根据冻结原文修订求值和时间字段" in prompt
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"atom": repaired_atom}, ensure_ascii=False),
            )

        def continue_calendar_bound_repair(self, *, session_id: str, prompt: str):
            pytest.fail("持续期错误不能只修事件窗口")

        def continue_candidate(self, *, session_id: str, prompt: str):
            pytest.fail("唯一原子错误不应重写整个候选")

    transport = AtomTransport([
        ProtocolControlAgentResponse(session_id="duration-session", text=initial.model_dump_json())
    ])
    calls = 0

    def reject_duration_once(output) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ProtocolControlAgentWireValidationError(
                "PUBLICATION_GATE_REJECTED", "持续治疗时长误作事件发生窗口",
                structure_unit_ids=["su-01"],
                candidate_ids=[output.candidates[0].control_candidate_id],
                obligation_source_span_ids=["span:01"],
                error_class_codes=["TREATMENT_DURATION_USED_AS_EVENT_WINDOW"],
            )

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        _batch(), transport, output_validator=reject_duration_once
    )
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert len(transport.prompts) == 2
    assert result.final_output is not None
    assert result.final_output.candidates[0].semantics is not None
    assert result.final_output.candidates[0].semantics.obligation_expression.groups[0].atoms[0].time_constraint is None
    if shared_source_sibling:
        assert result.final_output.candidates[0].semantics.obligation_expression.groups[0].atoms[1].statement == sibling["statement"]
        assert result.final_output.candidates[0].semantics.obligation_expression.groups[0].atoms[1].evaluation == initial.candidate_drafts[0].obligation_expression.groups[0].atoms[1].evaluation


def test_atom_repair_defaults_only_inclusivity_without_a_bound() -> None:
    initial = _wire(candidate=_candidate())
    baseline = initial.model_dump(mode="json")
    atom = deepcopy(baseline["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0])
    atom["time_constraint"] = {
        "anchor_type": "screening_date", "direction": "on",
        "lower_bound_inclusive": None, "upper_bound_inclusive": None,
    }
    atom["evaluation"]["time_purpose"] = "event_membership"
    atom["evaluation"]["time_operand_attribute"] = "date_range"
    merged = _merge_obligation_atom_repair(
        json.dumps({"atom": atom}, ensure_ascii=False), baseline, (0, 0, 0)
    )
    corrected = merged.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    assert corrected.time_constraint.lower_bound_inclusive is True
    assert corrected.time_constraint.upper_bound_inclusive is True
    atom["time_constraint"]["lower_bound_days"] = 7
    with pytest.raises(ProtocolControlAgentWireValidationError, match="ATOM_REPAIR_INVALID"):
        _merge_obligation_atom_repair(json.dumps({"atom": atom}), baseline, (0, 0, 0))


def test_distinct_calendar_atoms_are_repaired_once_each() -> None:
    drafts = [_candidate().model_dump(mode="json"), _candidate_for_second_unit().model_dump(mode="json")]
    for draft, span, excerpt in zip(
        drafts, ["span:01", "span:02"], ["年龄至少18岁", "筛选时记录末次用药日期"], strict=True,
    ):
        atom = draft["obligation_expression"]["groups"][0]["atoms"][0]
        atom["kind"] = ControlObligationKind.COMPLETE_BEFORE_ANCHOR.value
        atom["time_constraint"] = {
            "anchor_type": "screening_date", "direction": "before", "upper_bound_days": 7,
        }
        atom["evaluation"] = _timed_evaluation(atom["statement"], span, excerpt)
    initial = _wire_with_two_candidates(
        ProtocolControlAgentWireCandidate.model_validate(drafts[0]),
        ProtocolControlAgentWireCandidate.model_validate(drafts[1]),
    )

    class FocusedTransport(_FakeTransport):
        def __init__(self):
            super().__init__([ProtocolControlAgentResponse(
                session_id="calendar-two", text=initial.model_dump_json(),
            )])
            self.calendar_calls = 0

        def continue_calendar_bound_repair(self, *, session_id: str, prompt: str):
            self.calendar_calls += 1
            assert session_id == "calendar-two"
            return ProtocolControlAgentResponse(session_id=session_id, text=json.dumps({
                "time_constraint": {"anchor_type": "screening_date", "direction": "before"},
            }))

    transport = FocusedTransport()

    def reject_one_at_a_time(output) -> None:
        for index, candidate in enumerate(output.candidates):
            atom = candidate.semantics.obligation_expression.groups[0].atoms[0]
            if atom.time_constraint.upper_bound_days is not None:
                raise ProtocolControlAgentWireValidationError(
                    "PUBLICATION_GATE_REJECTED", "数值缺少原文支持",
                    structure_unit_ids=[f"su-0{index + 1}"], candidate_indexes=[index],
                    candidate_ids=[candidate.control_candidate_id],
                    obligation_source_span_ids=[f"span:0{index + 1}"],
                    error_class_codes=["TIME_CALENDAR_BOUND_UNSUPPORTED"],
                )

    result = ProtocolControlAgentRunner(max_schema_repairs=0).run(
        _batch(), transport, output_validator=reject_one_at_a_time,
    )
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert transport.calendar_calls == 2
    assert result.final_output is not None
    assert all(
        candidate.semantics.obligation_expression.groups[0].atoms[0].time_constraint.upper_bound_days is None
        for candidate in result.final_output.candidates
    )


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
    inventory = _source_inventory({
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


def test_shared_prohibition_keeps_future_period_out_of_current_evidence() -> None:
    from app.domain.contracts.enums import ProtocolPeriod
    from app.protocols.protocol_control_gate import validate_protocol_control_batch_candidates

    batch, inventory, review, _ = _stage_bound_example()
    source = "筛选期、治疗期不得调整既定治疗。"
    batch.owned_units[0].excerpt = source
    batch.known_workflow_stage_targets[0].display_name = "筛选期 / V1"
    batch.known_workflow_stage_targets[0].visit_instance = "筛选期 / V1"
    inventory.statements[0].quoted_text = source
    inventory.statements[0].scope_quote = "筛选期、治疗期"
    inventory.statements[0].force = "prohibited"
    inventory.statements[0].time_words = ["筛选期", "治疗期"]
    review.source_action_excerpt = "不得调整既定治疗"
    selection = SharedProhibitionRequirement.model_validate({
        "version": SHARED_PROHIBITION_REQUIREMENT_VERSION,
        "statement_index": 0,
        "current_statement": "筛选期不得调整既定治疗",
        "future_statement": "治疗期不得调整既定治疗",
        "workflow_stage_id": "stage:screening:one",
        "prospective_period": ProtocolPeriod.TREATMENT_PERIOD,
        "kind": "prohibit_medication_or_treatment_exposure",
        "title": "既定治疗调整限制",
        "applicable_population": "拟参加者",
        "observation_scope": "筛选期既定治疗调整记录",
        "fact_type": "treatment_change",
        "evidence_description": "筛选期既定治疗记录",
        "required_source_types": ["病历记录"],
        "unresolved_aspects": [],
    })
    assert can_compile_shared_prohibition_requirement(batch, inventory, review)
    assert "须逐字保留本次时期名称" in build_shared_prohibition_requirement_prompt(
        batch, inventory, review,
    )
    candidate = compile_shared_prohibition_requirement(batch, inventory, review, selection)
    atom = candidate.obligation_expression.groups[0].atoms[0]
    assert atom.statement == selection.current_statement
    assert atom.continuing_obligation.statement == selection.future_statement
    assert atom.evaluation.observation_policy.scope == selection.observation_scope
    _, output, coverage = assemble_source_requirement_inserts(
        batch, inventory, [review], _wire(),
        [ProtocolControlAgentResponse(session_id="shared-1", text=selection.model_dump_json())],
        lambda _output: None,
    )
    assert len(output.candidates) == 1
    assert coverage[0].status == "expressed"
    validate_protocol_control_batch_candidates(batch, output)

    with pytest.raises(StageBoundCompilationGap):
        compile_shared_prohibition_requirement(batch, inventory, review,
            selection.model_copy(update={"future_statement": "治疗期不得更换既定治疗"}))
    with pytest.raises(StageBoundCompilationGap):
        compile_shared_prohibition_requirement(batch, inventory, review,
            selection.model_copy(update={"observation_scope": "筛选期及治疗期既定治疗调整记录"}))

    inventory.statements[0].quoted_text = "基线期、治疗期不得调整既定治疗。"
    batch.owned_units[0].excerpt = inventory.statements[0].quoted_text
    review.source_action_excerpt = "不得调整既定治疗"
    assert can_compile_shared_prohibition_requirement(batch, inventory, review)
    with pytest.raises(StageBoundCompilationGap, match="审核节点"):
        compile_shared_prohibition_requirement(batch, inventory, review,
            selection.model_copy(update={
                "current_statement": "基线期不得调整既定治疗",
                "observation_scope": "基线期既定治疗调整记录",
            }))


def test_shared_prohibition_preserves_raw_fullwidth_source_excerpt() -> None:
    from app.domain.contracts.enums import ProtocolPeriod
    from app.protocols.protocol_control_gate import validate_protocol_control_batch_candidates

    batch, inventory, review, _ = _stage_bound_example()
    source = "筛选期、治疗期（第1访视）不得调整既定治疗。"
    batch.owned_units[0].excerpt = source
    inventory.statements[0].quoted_text = source
    inventory.statements[0].scope_quote = "筛选期、治疗期（第1访视）"
    inventory.statements[0].force = "prohibited"
    inventory.statements[0].time_words = ["筛选期", "治疗期（第1访视）"]
    review.source_action_excerpt = "不得调整既定治疗"
    selection = SharedProhibitionRequirement.model_validate({
        "version": SHARED_PROHIBITION_REQUIREMENT_VERSION,
        "statement_index": 0,
        "current_statement": "筛选期不得调整既定治疗",
        "future_statement": "治疗期（第1访视）不得调整既定治疗",
        "workflow_stage_id": "stage:screening:one",
        "prospective_period": ProtocolPeriod.TREATMENT_PERIOD,
        "kind": "prohibit_medication_or_treatment_exposure",
        "title": "治疗调整限制",
        "applicable_population": "拟参加者",
        "observation_scope": "筛选期治疗调整记录",
        "fact_type": "treatment_change",
        "evidence_description": "筛选期治疗记录",
        "required_source_types": ["病历记录"],
        "unresolved_aspects": [],
    })
    candidate = compile_shared_prohibition_requirement(batch, inventory, review, selection)
    atom = candidate.obligation_expression.groups[0].atoms[0]
    assert atom.source_excerpts == [source]
    assert atom.continuing_obligation.source_excerpts == [source]
    _, output, coverage = assemble_source_requirement_inserts(
        batch, inventory, [review], _wire(),
        [ProtocolControlAgentResponse(session_id="fullwidth-1", text=selection.model_dump_json())],
        lambda _output: None,
    )
    assert coverage[0].status == "expressed"
    validate_protocol_control_batch_candidates(batch, output)


def test_stage_bound_requirement_compiles_only_frozen_visit_scope() -> None:
    batch, inventory, review, selection = _stage_bound_example()
    prompt = build_stage_bound_requirement_prompt(batch, inventory, review)
    assert "拟参加者须完成知情同意记录" in prompt
    candidate = compile_stage_bound_requirement(batch, inventory, review, selection)
    atom = candidate.obligation_expression.groups[0].atoms[0]
    assert atom.time_constraint is None
    assert atom.evaluation.observation_policy.mode == "unresolved"
    assert atom.statement == inventory.statements[0].quoted_text
    assert atom.evaluation.proposition == inventory.statements[0].quoted_text
    assert atom.source_excerpts == ["筛选期（D-7~D-1）", selection.action_excerpt]
    assert candidate.review_node_bindings[0].workflow_stage_id == "stage:screening:one"
    assert candidate.minimum_evidence[0].source_policy.requires_contemporaneous_objective_source is None

    changed = selection.model_copy(update={"workflow_stage_id": "stage:screening:two"})
    with pytest.raises(StageBoundCompilationGap, match="冻结访视"):
        compile_stage_bound_requirement(batch, inventory, review, changed)
    shortened = selection.model_copy(update={"action_excerpt": "完成知情同意记录"})
    with pytest.raises(StageBoundCompilationGap, match="不得省略"):
        compile_stage_bound_requirement(batch, inventory, review, shortened)
    invented = selection.model_copy(update={
        "obligation_statement": "该参加者完成核查后符合入排要求",
    })
    with pytest.raises(StageBoundCompilationGap, match="逐字来源"):
        compile_stage_bound_requirement(batch, inventory, review, invented)


def test_stage_bound_action_completion_requires_source_only_operation() -> None:
    from app.domain.contracts.control_evaluation_spec import validate_control_atom_evaluation

    batch, inventory, review, selection = _stage_bound_example()
    action_only = selection.model_copy(update={"result_requirement": "action_only"})
    candidate = compile_stage_bound_requirement(batch, inventory, review, action_only)
    atom = candidate.obligation_expression.groups[0].atoms[0]
    assert atom.evaluation.observation_policy.mode == "action_completion"
    assert atom.evaluation.proposition == inventory.statements[0].quoted_text
    validate_control_atom_evaluation(atom, require_explicit=True)

    for requirement in ("result_required", "unresolved"):
        changed = selection.model_copy(update={"result_requirement": requirement})
        candidate = compile_stage_bound_requirement(batch, inventory, review, changed)
        assert candidate.obligation_expression.groups[0].atoms[0].evaluation.observation_policy.mode == "unresolved"
    with pytest.raises(StageBoundCompilationGap, match="必做操作"):
        compile_stage_bound_requirement(
            batch, inventory, review,
            action_only.model_copy(update={"kind": "must_record"}),
        )


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


def test_simple_period_inside_maps_to_that_frozen_visit_only() -> None:
    batch, inventory, review, selection = _stage_bound_example()
    batch.owned_units[0].excerpt = "筛选期内：拟参加者须完成知情同意记录。"
    batch.known_workflow_stage_targets[0].display_name = "筛选期"
    batch.known_workflow_stage_targets[0].visit_instance = "筛选期"
    inventory.statements[0].scope_quote = "筛选期内"
    inventory.statements[0].time_words = ["筛选期内"]
    selection = selection.model_copy(update={"stage_scope_excerpt": "筛选期内"})
    assert can_compile_stage_bound_requirement(batch, inventory, review)
    assert compile_stage_bound_requirement(batch, inventory, review, selection)

    for stage in batch.known_workflow_stage_targets:
        stage.display_name = "基线期"
        stage.visit_instance = "基线期"
    assert not can_compile_stage_bound_requirement(batch, inventory, review)
    with pytest.raises(StageBoundCompilationGap, match="原文时间要求"):
        compile_stage_bound_requirement(batch, inventory, review, selection)


def test_inline_single_visit_time_can_be_compiled_without_a_separate_scope() -> None:
    batch, inventory, review, selection = _stage_bound_example()
    source = "筛选期内拟参加者须完成知情同意记录。"
    batch.owned_units[0].excerpt = source
    batch.known_workflow_stage_targets[0].display_name = "筛选期"
    batch.known_workflow_stage_targets[0].visit_instance = "筛选期"
    inventory.statements[0].quoted_text = source
    inventory.statements[0].scope_quote = None
    inventory.statements[0].time_words = ["筛选期内"]
    selection = selection.model_copy(update={
        "stage_scope_excerpt": "筛选期内", "obligation_statement": source,
    })
    assert can_compile_stage_bound_requirement(batch, inventory, review)
    candidate = compile_stage_bound_requirement(batch, inventory, review, selection)
    assert candidate.review_node_bindings[0].workflow_stage_id == "stage:screening:one"
    inventory.statements[0].time_words = ["筛选期内", "基线前"]
    assert not can_compile_stage_bound_requirement(batch, inventory, review)
    with pytest.raises(StageBoundCompilationGap):
        compile_stage_bound_requirement(batch, inventory, review, selection)


def test_visit_action_insert_preserves_sourced_procedure_relation_and_coverage() -> None:
    batch, inventory, review, selection = _stage_bound_example()
    source = "筛选期内拟参加者须完成知情同意记录。"
    batch.owned_units[0].excerpt = source
    batch.known_workflow_stage_targets[0].display_name = "筛选期"
    batch.known_workflow_stage_targets[0].visit_instance = "screening-1"
    batch.known_procedure_targets[0].source_excerpts = ["知情同意记录"]
    inventory.statements[0].quoted_text = source
    inventory.statements[0].scope_quote = None
    inventory.statements[0].time_words = ["筛选期内"]
    inventory.statements[0].decision_functions = ["action", "time_validity"]
    review.target_id = "procedure-screening-1"
    review.target_action_excerpt = "知情同意记录"
    selection = selection.model_copy(update={
        "stage_scope_excerpt": "筛选期内", "obligation_statement": source,
        "result_requirement": "action_only",
    })
    candidate = compile_stage_bound_requirement(batch, inventory, review, selection)
    assert [(relation.external_target_kind.value, relation.external_target_id)
            for relation in candidate.cross_source_relations] == [
        ("required_procedure", "procedure-screening-1"),
    ]
    baseline = _wire()
    baseline.dispositions[0].disposition = StructureUnitDispositionKind.REQUIRED_PROCEDURE
    baseline.dispositions[0].linked_procedure_catalog_item_id = "procedure-screening-1"
    assert source_statement_coverage(batch, inventory, _wire(candidate=candidate))[0].status == "expressed"
    _, output, coverage = assemble_source_requirement_inserts(
        batch, inventory, [review], baseline,
        [ProtocolControlAgentResponse(session_id="visit-1", text=selection.model_dump_json())],
        lambda _output: None,
    )
    assert len(output.candidates) == 1
    assert coverage[0].status == "expressed"

    review.target_action_excerpt = "另一项检查"
    unrelated = compile_stage_bound_requirement(batch, inventory, review, selection)
    assert unrelated.cross_source_relations == []
    inventory.statements[0].time_words = ["筛选期内", "基线前"]
    assert source_statement_coverage(batch, inventory, _wire(candidate=candidate))[0].status != "expressed"


@pytest.mark.parametrize("quote,time_words", [
    ("拟参加者须接受治疗7天", ["筛选期（D-7~D-1）"]),
    ("在整个治疗期继续接受治疗", ["治疗期"]),
    ("筛选期、后续治疗期均不得调整用药", ["筛选期、后续治疗期"]),
    ("拟参加者每日1次接受治疗", ["每日1次"]),
    ("拟参加者每日一次接受治疗", ["每日一次"]),
    ("给药前90分钟内采集样本", ["给药前90分钟内"]),
    ("给药后两小时复查", ["给药后两小时"]),
    ("静坐半小时后完成测量", ["半小时后"]),
    ("静坐0.5小时后完成测量", ["0.5小时后"]),
    ("Collect within 45 minutes before administration", ["45 minutes"]),
])
def test_stage_bound_path_does_not_erase_explicit_duration_or_multiple_periods(
    quote: str, time_words: list[str],
) -> None:
    batch, inventory, review, selection = _stage_bound_example()
    batch.owned_units[0].excerpt = f"筛选期（D-7~D-1）：{quote}。"
    inventory.statements[0].quoted_text = quote
    inventory.statements[0].time_words = time_words
    review.source_action_excerpt = quote
    assert requires_temporal_resolution(inventory, 0)
    assert not can_compile_stage_bound_requirement(batch, inventory, review)
    with pytest.raises(StageBoundCompilationGap, match="持续期或跨节点"):
        compile_stage_bound_requirement(
            batch, inventory, review,
            selection.model_copy(update={"action_excerpt": quote, "obligation_statement": quote}),
        )


def test_frequency_in_source_remains_temporal_when_model_omits_time_words() -> None:
    batch, inventory, review, _ = _stage_bound_example()
    quote = "拟参加者每日1次接受治疗"
    batch.owned_units[0].excerpt = f"筛选期：{quote}。"
    inventory.statements[0].quoted_text = quote
    inventory.statements[0].time_words = []
    review.source_action_excerpt = quote
    assert requires_temporal_resolution(inventory, 0)
    assert not can_compile_stage_bound_requirement(batch, inventory, review)
    assert not can_compile_relative_stage_requirement(batch, inventory, review)


def test_stage_bound_path_rejects_multi_visit_range_in_scope() -> None:
    batch, inventory, review, selection = _stage_bound_example()
    inventory.statements[0].scope_quote = "治疗期（W0~W4）"
    inventory.statements[0].time_words = ["治疗期（W0~W4）"]
    assert requires_temporal_resolution(inventory, 0)
    assert not can_compile_stage_bound_requirement(batch, inventory, review)
    with pytest.raises(StageBoundCompilationGap, match="持续期或跨节点"):
        compile_stage_bound_requirement(batch, inventory, review, selection)


def test_temporal_addition_cannot_fall_back_to_full_source_insert() -> None:
    batch, inventory, review, _selection = _stage_bound_example()
    quote = "拟参加者须连续治疗7天"
    batch.owned_units[0].excerpt = f"年龄至少18岁；筛选期（D-7~D-1）：{quote}。"
    inventory.statements[0].quoted_text = quote
    inventory.statements[0].time_words = ["筛选期（D-7~D-1）"]
    review.source_action_excerpt = quote

    class TemporalTransport(_FakeTransport):
        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="target-1", text=SourceTargetReview(
                version=SOURCE_TARGET_REVIEW_VERSION, items=[review],
            ).model_dump_json())

        def start_source_insert(self, *, prompt: str, multiple: bool) -> ProtocolControlAgentResponse:
            raise AssertionError("跨节点义务不得进入整候选补入")

    result = ProtocolControlAgentRunner().run(
        batch,
        TemporalTransport([ProtocolControlAgentResponse(
            session_id="wire-1", text=_wire(candidate=_candidate()).model_dump_json(),
        )]),
        output_validator=lambda _output: None,
    )
    assert result.status == "需要核对"
    assert result.partial_wire is not None
    assert any("TEMPORAL_SCOPE_UNRESOLVED" in attempt.error_classes for attempt in result.attempts), [
        (attempt.error_classes, attempt.issues) for attempt in result.attempts
    ]
    resumed = ProtocolControlAgentRunner().run(
        batch, TemporalTransport([]),
        resume_wire=result.partial_wire,
        resume_source_interpretation=inventory,
        resume_session_id=result.session_id,
        output_validator=lambda _output: None,
    )
    assert resumed.status == "需要核对"
    assert resumed.partial_wire == result.partial_wire


def test_temporal_scope_failure_reports_every_exact_statement_without_regex() -> None:
    batch, _inventory, review, _selection = _stage_bound_example()
    first = "拟参加者须连续治疗7天"
    second = "拟参加者须持续接受治疗7天"
    batch.owned_units[0].excerpt = f"年龄至少18岁；{first}。{second}。"
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
            {"structure_unit_id": "su-01", "quoted_text": first, "force": "required",
             "time_words": ["7天"]},
            {"structure_unit_id": "su-01", "quoted_text": second, "force": "required",
             "time_words": ["7天"]},
        ],
        "units_without_statement": ["su-02"],
    })
    items = [
        review.model_copy(update={
            "statement_index": index, "source_action_excerpt": quote,
        })
        for index, quote in enumerate((first, second))
    ]
    asked_review = SourceTargetReview(
        version=SOURCE_TARGET_REVIEW_VERSION, items=items,
    )

    class TemporalTransport(_FakeTransport):
        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(
                session_id="source-1", text=inventory.model_dump_json(),
            )

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(
                session_id="target-1", text=asked_review.model_dump_json(),
            )

        def start_source_insert(self, *, prompt: str, multiple: bool) -> ProtocolControlAgentResponse:
            raise AssertionError("持续期义务不得进入整候选补入")

    result = ProtocolControlAgentRunner().run(
        batch,
        TemporalTransport([ProtocolControlAgentResponse(
            session_id="wire-1", text=_wire(candidate=_candidate()).model_dump_json(),
        )]),
        output_validator=lambda _output: None,
    )
    assert result.status == "需要核对", [attempt.issues for attempt in result.attempts]
    assert result.partial_wire is not None
    details = [
        attempt.error_detail for attempt in result.attempts
        if "TEMPORAL_SCOPE_UNRESOLVED" in attempt.error_classes
    ]
    assert len(details) == 1, [
        (attempt.error_classes, attempt.error_detail) for attempt in result.attempts
    ]
    detail = details[0]
    assert detail["code"] == "TEMPORAL_SCOPE_UNRESOLVED"
    assert detail["statement_ids"] == [0, 1]
    assert detail["json_path"] == "/items"
    assert detail["retry_class"] == "temporal_scope_review"
    assert detail["affected_dependents"] == [0, 1]
    assert detail["source_refs"] == ["span:01"]
    # The range is carried as data, not parsed back out of the Chinese message.
    assert all(
        token not in json.dumps(detail, ensure_ascii=False)
        for token in ("第", "条", "持续期")
    )


def test_temporal_gap_keeps_independently_verified_stage_addition() -> None:
    batch, inventory, simple_review, selection = _stage_bound_example()
    continuing = "拟参加者须持续接受治疗7天"
    batch.owned_units[0].excerpt = (
        "年龄至少18岁；筛选期（D-7~D-1）：拟参加者须完成知情同意记录。"
        + continuing + "。"
    )
    inventory.statements.append(inventory.statements[0].model_copy(update={
        "quoted_text": continuing,
        "time_words": ["治疗7天"],
    }))
    temporal_review = simple_review.model_copy(update={
        "statement_index": 1,
        "source_action_excerpt": continuing,
    })

    class MixedTimeTransport(_FakeTransport):
        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="target-1", text=SourceTargetReview(
                version=SOURCE_TARGET_REVIEW_VERSION,
                items=[simple_review, temporal_review],
            ).model_dump_json())

        def read_stage_bound_requirement(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="stage-1", text=selection.model_dump_json())

        def start_source_insert(self, *, prompt: str, multiple: bool) -> ProtocolControlAgentResponse:
            raise AssertionError("持续期义务不得落回整候选补入")

    result = ProtocolControlAgentRunner().run(
        batch,
        MixedTimeTransport([ProtocolControlAgentResponse(
            session_id="wire-1", text=_wire(candidate=_candidate()).model_dump_json(),
        )]),
        output_validator=lambda _output: None,
    )
    assert result.status == "需要核对"
    assert result.partial_wire is not None
    assert len(result.partial_wire.candidate_drafts) == 2
    assert result.source_target_review is not None
    assert [item.statement_index for item in result.source_target_review.items] == [1]
    assert any("TEMPORAL_SCOPE_UNRESOLVED" in attempt.error_classes for attempt in result.attempts)


@pytest.mark.parametrize("same_unit", [False, True])
@pytest.mark.parametrize("invalid_selection", [False, True])
def test_unresolved_sibling_keeps_verified_insert_without_accepting_batch(same_unit, invalid_selection) -> None:
    batch, inventory, review, selection = _stage_bound_example()
    known = inventory.statements[0].quoted_text
    unknown = "建议择期复核既往病史记录"
    batch.owned_units[0].excerpt = "年龄至少18岁；筛选期（D-7~D-1）：" + known + "。"
    if same_unit:
        batch.owned_units[0].excerpt += unknown + "。"
    else:
        batch.owned_units[1].excerpt = unknown
        inventory.units_without_statement = []
    inventory.statements.append(inventory.statements[0].model_copy(update={
        "structure_unit_id": "su-01" if same_unit else "su-02",
        "quoted_text": unknown, "scope_quote": None, "time_words": [],
        "force": "recommended", "unresolved": ["适用时期未核清"],
    }))
    unknown_review = review.model_copy(update={
        "statement_index": 1, "decision": "unresolved",
        "source_action_excerpt": unknown, "unresolved_aspects": ["适用时期未核清"],
    })
    initial = _wire(candidate=_candidate())

    class MixedReviewTransport(_FakeTransport):
        stage_calls = 0
        review_calls = 0
        insert_calls = 0

        def start_source_interpretation(self, *, prompt):
            return ProtocolControlAgentResponse(session_id="source", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt):
            self.review_calls += 1
            return ProtocolControlAgentResponse(session_id="review", text=SourceTargetReview(
                version=SOURCE_TARGET_REVIEW_VERSION,
                items=[review, unknown_review] if self.review_calls == 1 else [unknown_review],
            ).model_dump_json())

        def read_stage_bound_requirement(self, *, prompt):
            self.stage_calls += 1
            proposal = selection.model_copy(update={
                "action_excerpt": "另一来源的操作" if invalid_selection else selection.action_excerpt,
            })
            return ProtocolControlAgentResponse(session_id="stage", text=proposal.model_dump_json())

        def start_source_insert(self, **kwargs):
            self.insert_calls += 1
            raise RuntimeError("本例不允许整批补入")

    transport = MixedReviewTransport([ProtocolControlAgentResponse(
        session_id="wire", text=initial.model_dump_json(),
    )])
    result = ProtocolControlAgentRunner(max_schema_repairs=0).run(
        batch, transport, output_validator=lambda _output: None,
    )
    assert transport.stage_calls == 1
    assert result.status == "需要核对"
    assert result.final_output is None
    assert result.partial_wire is not None
    assert result.partial_wire.candidate_drafts[0] == initial.candidate_drafts[0]
    assert len(result.partial_wire.candidate_drafts) == (1 if invalid_selection else 2)
    restored = type(result).model_validate_json(result.model_dump_json())
    assert restored.partial_wire == result.partial_wire
    assert restored.source_target_review is not None
    assert any(item.statement_index == 1 and item.decision == "unresolved"
               for item in restored.source_target_review.items)
    from app.services.protocol_control_restricted_source import restricted_batch_from_review
    # This fixture's shared scope was not proved independent. A diagnostic
    # checkpoint is not sufficient authority for the restricted consumer.
    assert restricted_batch_from_review(batch, restored) is None
    assert len(restored.source_statement_coverage) == len(inventory.statements)
    if same_unit:
        assert transport.insert_calls == 0
    if not invalid_selection:
        assert [item.statement_index for item in restored.source_target_review.items] == [1]
        assert result.attempts[-1].error_classes == ["SOURCE_TARGET_REVIEW_UNRESOLVED"]
        assert result.attempts[-1].error_detail["statement_ids"] == [1]
        assert result.source_statement_coverage[0].status == "expressed"


def test_temporal_candidate_is_reviewed_before_insert_guard_without_forging_acceptance() -> None:
    from app.agents.protocol_control_candidate_alignment import SOURCE_CANDIDATE_ALIGNMENT_VERSION

    batch, inventory, review, _ = _stage_bound_example()
    quote = "拟参加者须连续治疗7天"
    batch.owned_units[0].excerpt = quote
    inventory.statements[0].quoted_text = quote
    inventory.statements[0].scope_quote = None
    inventory.statements[0].time_words = ["7天"]
    inventory.statements[0].decision_functions = ["action", "time_validity"]
    review.source_action_excerpt = quote
    review.source_time_excerpt = "7天"
    candidate = _candidate().model_dump(mode="json")
    candidate["applicability_expression"] = None
    candidate["exception_expression"] = None
    atom = candidate["obligation_expression"]["groups"][0]["atoms"][0]
    atom["statement"] = quote
    atom["source_excerpts"] = [quote]
    atom["evaluation"] = _evaluation(quote, "span:01", quote)
    original = _wire(candidate=type(_candidate()).model_validate(candidate))

    class TemporalAlignmentTransport(_FakeTransport):
        alignment_calls = 0

        def start_source_interpretation(self, *, prompt):
            return ProtocolControlAgentResponse(session_id="source", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt):
            return ProtocolControlAgentResponse(session_id="target", text=SourceTargetReview(
                version=SOURCE_TARGET_REVIEW_VERSION, items=[review],
            ).model_dump_json())

        def start_source_candidate_alignment(self, *, prompt):
            self.alignment_calls += 1
            return ProtocolControlAgentResponse(session_id="alignment", text=json.dumps({
                "version": SOURCE_CANDIDATE_ALIGNMENT_VERSION,
                "items": [{"statement_index": 0, "candidate_index": 0,
                           "decision": "fully_expressed", "source_excerpt": quote,
                           "candidate_atom_quotes": [quote], "unresolved_dimensions": []}],
            }, ensure_ascii=False))

        def start_source_insert(self, *, prompt, multiple):
            raise AssertionError("持续治疗不得降为单次访视补入")

    transport = TemporalAlignmentTransport([])
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_wire=original, resume_source_interpretation=inventory,
        resume_session_id="existing-wire", output_validator=lambda _output: None,
    )
    assert transport.alignment_calls == 1, [
        (attempt.error_classes, attempt.issues) for attempt in result.attempts
    ]
    assert result.status == "需要核对"
    assert result.partial_wire == original
    assert result.source_candidate_alignment is None
    assert all(entry.status != "semantically_aligned" for entry in result.source_statement_coverage)
    assert any("SOURCE_CANDIDATE_ALIGNMENT_INVALID" in attempt.error_classes for attempt in result.attempts)
    assert any("TEMPORAL_SCOPE_UNRESOLVED" in attempt.error_classes for attempt in result.attempts)


def _synthetic_policy_checks_from_prompt(prompt, candidate_index=0):
    """Agreeing reader fixture only; not a clinical semantic baseline."""
    from app.domain.contracts.control_evidence_policy import has_explicit_evidence_policy
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentWireEvidence
    selected = json.loads(prompt.split("待核对应：", 1)[1])
    candidate = next(row["candidate"] for row in selected
                     if row["candidate_index"] == candidate_index)
    checks = []
    for index, evidence in enumerate(candidate["minimum_evidence"]):
        if not has_explicit_evidence_policy(ProtocolControlAgentWireEvidence.model_validate(evidence)):
            continue
        policy = evidence["source_policy"]
        source = dict(evidence_index=index, source_span_id=policy["source_span_ids"][0],
                      source_excerpt=policy["source_excerpts"][0])
        checks.extend([
            dict(source, dimension="contemporaneous_objective_source",
                 boolean_value=policy["requires_contemporaneous_objective_source"]),
            dict(source, dimension="screening_record_transcription",
                 boolean_value=policy["allows_screening_record_transcription"]),
            dict(source, dimension="result_validity",
                 validity_status=policy["result_validity_status"],
                 validity_constraint=policy["result_validity_constraint"]),
        ])
        if evidence["required_source_types"]:
            checks.append(dict(source, dimension="required_source_types",
                               source_types=evidence["required_source_types"]))
    return checks


def _consent_policy_alignment_response(quote, prompt):
    from app.agents.protocol_control_candidate_alignment import SOURCE_CANDIDATE_ALIGNMENT_VERSION
    return ProtocolControlAgentResponse(session_id="synthetic-policy-review", text=json.dumps({
        "version": SOURCE_CANDIDATE_ALIGNMENT_VERSION,
        "items": [{"statement_index": 0, "candidate_index": 1, "decision": "fully_expressed",
                   "source_excerpt": quote, "candidate_atom_quotes": [quote], "unresolved_dimensions": [],
                   "evidence_policy_checks": _synthetic_policy_checks_from_prompt(prompt, 1)}],
    }, ensure_ascii=False))


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

        def start_source_candidate_alignment(self, *, prompt):
            return _consent_policy_alignment_response(selection.action_excerpt, prompt)

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


@pytest.mark.parametrize("shared_time_word", [None, "筛选/导入期（D-7~D-1）", "D-7~D-1"])
def test_relative_stage_requirement_preserves_after_stage_without_new_calendar_window(shared_time_word) -> None:
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
    inventory.statements[0].scope_quote = "筛选/导入期（D-7~D-1）："
    inventory.statements[0].time_words = ["完成导入治疗后"]
    if shared_time_word:
        inventory.statements[0].time_words.insert(0, shared_time_word)
    review.source_action_excerpt = "完成导入治疗后再次核查资格"
    review.source_time_excerpt = "完成导入治疗后"
    review.target_id = "procedure-screening-1"
    review.target_action_excerpt = "再次核查资格"
    relative = RelativeStageRequirement.model_validate({
        **selection.model_dump(exclude={"version"}),
        "version": RELATIVE_STAGE_REQUIREMENT_VERSION,
        "action_excerpt": review.source_action_excerpt,
        "stage_scope_excerpt": "筛选/导入期（D-7~D-1）：",
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
    assert atom.evaluation.proposition == inventory.statements[0].quoted_text
    assert candidate.review_node_bindings[0].review_stage == ReviewStage.BASELINE
    assert candidate.cross_source_relations[0].affected_workflow_stage_id == "stage:screening:two"
    assert source_statement_coverage(batch, inventory, _wire(candidate=candidate))[0].status == "expressed"
    if shared_time_word:
        missing_scope = candidate.model_copy(deep=True)
        missing_scope.obligation_expression.groups[0].atoms[0].source_excerpts[0] = (
            batch.owned_units[0].excerpt
        )
        assert source_statement_coverage(batch, inventory, _wire(candidate=missing_scope))[0].status == "candidate_linked"
        wrong_scope_source = candidate.model_copy(deep=True)
        wrong_scope_source.obligation_expression.groups[0].atoms[0].source_span_ids[0] = "unowned-span"
        with pytest.raises(ValueError, match="source_span_ids"):
            _wire(candidate=wrong_scope_source)
        wrong_scope_source.source_span_ids.append("unowned-span")
        assert source_statement_coverage(batch, inventory, _wire(candidate=wrong_scope_source))[0].status == "candidate_linked"
        fragment_time = inventory.model_copy(deep=True)
        fragment_time.statements[0].time_words[0] = "D-1"
        assert not can_compile_relative_stage_requirement(batch, fragment_time, review)
        assert source_statement_coverage(batch, fragment_time, _wire(candidate=candidate))[0].status == "candidate_linked"

    wrong_order = relative.model_copy(update={"workflow_stage_id": "stage:screening:one"})
    with pytest.raises(StageBoundCompilationGap, match="先后"):
        compile_stage_bound_requirement(batch, inventory, review, wrong_order)
    wrong_scope = relative.model_copy(update={"stage_scope_excerpt": "治疗期"})
    with pytest.raises(StageBoundCompilationGap):
        compile_stage_bound_requirement(batch, inventory, review, wrong_scope)
    invented_time = inventory.model_copy(deep=True)
    invented_time.statements[0].time_words.append("给药前90分钟")
    assert not can_compile_relative_stage_requirement(batch, invented_time, review)
    with pytest.raises(StageBoundCompilationGap):
        compile_stage_bound_requirement(batch, invented_time, review, relative)


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
        "required_source_types": [],  # This second action does not inherit the consent record type.
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

        def start_source_candidate_alignment(self, *, prompt):
            return _consent_policy_alignment_response(first.action_excerpt, prompt)

    validated_sizes = []

    def validate_complete_batch(output) -> None:
        validated_sizes.append(len(output.candidates))
        if len(validated_sizes) > 1 and len(output.candidates) != 3:
            raise ValueError("同批增量要求尚未齐全")

    result = ProtocolControlAgentRunner().run(
        batch,
        TwoActionTransport([ProtocolControlAgentResponse(
            session_id="wire-1", text=json.dumps(original, ensure_ascii=False)
        )]),
        output_validator=validate_complete_batch,
    )
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert validated_sizes == [1, 3]
    assert result.final_output is not None
    assert len(result.final_output.candidates) == 3
    assert result.source_target_review is not None and result.source_target_review.items == []
    assert {item.session_id for item in result.attempts} >= {"stage-1", "relative-1"}


def test_two_invalid_candidate_drafts_are_repaired_separately() -> None:
    first = _candidate().model_dump(mode="json")
    second = _candidate_for_second_unit().model_dump(mode="json")
    original = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit()).model_dump(mode="json")
    invalid = deepcopy(original)
    for draft in invalid["candidate_drafts"]:
        draft["title"] = ""

    class FocusedTransport(_FakeTransport):
        def __init__(self):
            super().__init__([ProtocolControlAgentResponse(
                session_id="wire-1", text=json.dumps(invalid, ensure_ascii=False),
            )])
            self.focused_indexes = []

        def continue_candidate(self, *, session_id: str, prompt: str) -> ProtocolControlAgentResponse:
            index = len(self.focused_indexes)
            self.focused_indexes.append(index)
            assert session_id == "wire-1"
            assert "只修复指定的一个候选" in prompt
            assert f"[{index}]" in prompt
            return ProtocolControlAgentResponse(
                session_id=session_id,
                text=json.dumps({"candidate_draft": [first, second][index]}, ensure_ascii=False),
            )

    transport = FocusedTransport()
    result = ProtocolControlAgentRunner(max_schema_repairs=2).run(
        _batch(), transport, output_validator=lambda _output: None,
    )
    assert result.status == "已解析", [attempt.issues for attempt in result.attempts]
    assert transport.focused_indexes == [0, 1]
    assert result.final_output is not None
    assert len(result.final_output.candidates) == 2
    assert result.repair_used

    class ChangedSourceTransport(FocusedTransport):
        def continue_candidate(self, *, session_id: str, prompt: str) -> ProtocolControlAgentResponse:
            response = super().continue_candidate(session_id=session_id, prompt=prompt)
            payload = json.loads(response.text)
            payload["candidate_draft"]["source_structure_unit_ids"] = ["su-02"]
            return ProtocolControlAgentResponse(
                session_id=session_id, text=json.dumps(payload, ensure_ascii=False),
            )

    changed = ChangedSourceTransport()
    rejected = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        _batch(), changed, output_validator=lambda _output: None,
    )
    assert rejected.status == "需要核对"
    assert changed.focused_indexes == [0]
    assert any("CANDIDATE_REPAIR_INVALID" in attempt.error_classes for attempt in rejected.attempts)

    from app.agents.protocol_control_deconstructor import _merge_candidate_repair_payload
    with pytest.raises(ProtocolControlAgentWireValidationError, match="CANDIDATE_REPAIR_SHAPE_INVALID"):
        _merge_candidate_repair_payload(json.dumps({"candidate_draft": []}), invalid, 0)

    disabled = FocusedTransport()
    no_budget = ProtocolControlAgentRunner(max_schema_repairs=0).run(
        _batch(), disabled, output_validator=lambda _output: None,
    )
    assert no_budget.status == "需要核对"
    assert disabled.focused_indexes == []

    limited = FocusedTransport()
    exhausted = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        _batch(), limited, output_validator=lambda _output: None,
    )
    assert exhausted.status == "需要核对"
    assert limited.focused_indexes == [0]
    assert exhausted.final_output is None


def test_mixed_source_actions_keep_verified_partial_on_failure_and_resume() -> None:
    batch, inventory, first_review, first = _stage_bound_example()
    actions = [
        "拟参加者须完成知情同意记录",
        "拟参加者须完成用药记录，除非已有书面核实",
        "拟参加者须完成既往病史记录",
        "拟参加者须完成既往治疗记录",
        "拟参加者须完成生活习惯记录",
    ]
    batch.owned_units[0].excerpt = (
        "年龄至少18岁；筛选期（D-7~D-1）：" + "。".join(actions) + "。"
    )
    inventory.statements = [
        inventory.statements[0].model_copy(update={
            "quoted_text": action,
            "exception_words": "除非已有书面核实" if index == 1 else None,
        })
        for index, action in enumerate(actions)
    ]
    reviews = [first_review.model_copy(update={
        "statement_index": index,
        "source_action_excerpt": action,
    }) for index, action in enumerate(actions)]
    selections = {index: first.model_copy(update={
        "statement_index": index,
        "action_excerpt": action,
        "title": f"记录{index}",
        "obligation_statement": action,
    }) for index, action in enumerate(actions) if index != 1}
    initial = _wire(candidate=_candidate()).model_dump_json()
    full_review = SourceTargetReview(
        version=SOURCE_TARGET_REVIEW_VERSION, items=reviews,
    )

    class MixedTransport(_FakeTransport):
        def __init__(self, responses):
            super().__init__(responses)
            self.source_calls = 0
            self.wire_calls = 0
            self.read_actions = []
            self.insert_calls = 0

        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.source_calls += 1
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            review = full_review if self.source_calls else SourceTargetReview(
                version=SOURCE_TARGET_REVIEW_VERSION, items=[reviews[1], reviews[4]],
            )
            return ProtocolControlAgentResponse(session_id="target-1", text=review.model_dump_json())

        def start(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.wire_calls += 1
            return super().start(prompt=prompt)

        def read_stage_bound_requirement(self, *, prompt: str) -> ProtocolControlAgentResponse:
            index = json.loads(prompt.split("冻结来源：", 1)[1])["statement_index"]
            selection = selections[index]
            self.read_actions.append(index)
            return ProtocolControlAgentResponse(
                session_id=f"stage-{index}", text=selection.model_dump_json(),
            )

        def start_source_insert(self, *, prompt: str, multiple: bool) -> ProtocolControlAgentResponse:
            self.insert_calls += 1
            assert "已核候选只供去重" in prompt
            raise RuntimeError("未完成条目仍需来源解释")

    first_transport = MixedTransport([ProtocolControlAgentResponse(
        session_id="wire-1", text=initial,
    )])
    result = ProtocolControlAgentRunner(max_schema_repairs=0).run(
        batch, first_transport, output_validator=lambda _output: None,
    )
    assert result.status == "需要核对"
    assert result.partial_wire is not None
    assert len(result.partial_wire.candidate_drafts) == 4, [item.issues for item in result.attempts]
    assert first_transport.read_actions == [0, 2, 3]
    assert result.source_interpretation is not None

    retry_transport = MixedTransport([])
    retried = ProtocolControlAgentRunner(max_schema_repairs=0).run(
        batch, retry_transport, output_validator=lambda _output: None,
        resume_wire=result.partial_wire,
        resume_source_interpretation=result.source_interpretation,
        resume_session_id=result.session_id,
    )
    assert retried.status == "需要核对"
    assert retry_transport.source_calls == retry_transport.wire_calls == 0
    assert retry_transport.read_actions == [4]
    assert retry_transport.insert_calls == 1
    assert retried.partial_wire is not None
    assert len(retried.partial_wire.candidate_drafts) == 5
    invalid_source = result.source_interpretation.model_copy(update={
        "units_without_statement": [], "statements": [],
    })
    with pytest.raises(ValueError, match="每个冻结来源单元"):
        ProtocolControlAgentRunner().run(
            batch, MixedTransport([]), output_validator=lambda _output: None,
            resume_wire=result.partial_wire,
            resume_source_interpretation=invalid_source,
            resume_session_id=result.session_id,
        )


@pytest.mark.parametrize("failure_kind", ["transport", "interrupted", "identity", "budget"])
@pytest.mark.parametrize("failed_index", [0, 1])
@pytest.mark.parametrize("adapter_wrapped", [False, True])
def test_short_requirement_transport_failure_does_not_expand_and_keeps_success(failure_kind, failed_index, adapter_wrapped):
    from app.agents.protocol_control_agent_transport import (
        ProtocolControlAgentCallError, ProtocolControlModelIdentityError,
    )
    from app.llm.logical_call_budget import LogicalCallBudgetExhausted

    batch, inventory, review, selection = _stage_bound_example()
    actions = ["拟参加者须完成知情同意记录", "拟参加者须完成既往病史记录"]
    batch.owned_units[0].excerpt = "年龄至少18岁；筛选期（D-7~D-1）：" + "。".join(actions) + "。"
    inventory.statements = [inventory.statements[0].model_copy(update={"quoted_text": text})
                            for text in actions]
    reviews = [review.model_copy(update={"statement_index": index, "source_action_excerpt": text})
               for index, text in enumerate(actions)]
    failures = {
        "transport": RuntimeError("synthetic connection failure"),
        "interrupted": ProtocolControlAgentCallError("short-reader", "synthetic stream failure", uncertain_completion=True),
        "identity": ProtocolControlModelIdentityError("synthetic wrong model", configured_model="expected", reason="mismatch"),
        "budget": LogicalCallBudgetExhausted("synthetic shared budget exhausted"),
    }

    class ShortFailure(_FakeTransport):
        def __init__(self):
            super().__init__([ProtocolControlAgentResponse(session_id="wire-1", text=_wire(candidate=_candidate()).model_dump_json())])
            self.read_indexes = []

        def start_source_interpretation(self, *, prompt):
            return ProtocolControlAgentResponse(session_id="source-1", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt):
            return ProtocolControlAgentResponse(session_id="target-1", text=SourceTargetReview(
                version=SOURCE_TARGET_REVIEW_VERSION, items=reviews,
            ).model_dump_json())

        def read_stage_bound_requirement(self, *, prompt):
            index = json.loads(prompt.split("冻结来源：", 1)[1])["statement_index"]
            self.read_indexes.append(index)
            if index == failed_index:
                if adapter_wrapped:
                    raise ProtocolControlAgentCallError("wrapped-reader", "synthetic adapter failure") from failures[failure_kind]
                raise failures[failure_kind]
            return ProtocolControlAgentResponse(session_id=f"short-{index}", text=selection.model_copy(update={
                "statement_index": index, "action_excerpt": actions[index], "obligation_statement": actions[index],
            }).model_dump_json())

        def start_source_insert(self, **kwargs):
            pytest.fail("A failed short read must not trigger a larger source insert")

        def start_source_candidate_alignment(self, **kwargs):
            pytest.fail("A failed short read must not trigger another semantic call")

        def continue_session(self, **kwargs):
            pytest.fail("A failed short read must not trigger whole-wire repair")

    transport = ShortFailure()
    result = ProtocolControlAgentRunner(max_schema_repairs=2).run(
        batch, transport, output_validator=lambda _output: None,
    )
    expected = {"transport": "SOURCE_REQUIREMENT_TRANSPORT_FAILED", "interrupted": "FLOW_COMPLETION_UNCERTAIN",
                "identity": "MODEL_IDENTITY_INVALID", "budget": "LOGICAL_BUDGET_EXHAUSTED"}[failure_kind]
    assert result.final_output is None
    assert transport.read_indexes == list(range(failed_index + 1))
    assert result.attempts[-1].error_classes == [expected]
    assert result.attempts[-1].outcome == "transport_failed"
    assert result.attempts[-1].error_detail["statement_ids"] == [failed_index]
    assert result.partial_wire is not None
    assert len(result.partial_wire.candidate_drafts) == 1 + failed_index
    assert [item.statement_index for item in result.source_target_review.items] == list(range(failed_index, 2))
    restored = type(result).model_validate_json(result.model_dump_json())
    assert restored.partial_wire == result.partial_wire
    assert restored.attempts[-1].error_detail == result.attempts[-1].error_detail


def _two_independent_candidate_linked_alignment_material():
    from app.agents.protocol_control_candidate_alignment import SOURCE_CANDIDATE_ALIGNMENT_VERSION

    age = "年龄至少18岁"
    continuing = "拟参加者须持续接受治疗7天"
    batch = _batch().model_copy(deep=True)
    batch.owned_units[0].excerpt = age
    batch.owned_units[1].excerpt = continuing
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
            {"structure_unit_id": "su-01", "quoted_text": age, "force": "required",
             "time_words": [], "decision_functions": ["action"]},
            {"structure_unit_id": "su-02", "quoted_text": continuing, "force": "required",
             "time_words": ["7天"], "decision_functions": ["action", "time_validity"]},
        ],
        "units_without_statement": [],
    })
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [
            {"statement_index": 0, "decision": "additional_requirement", "target_id": None,
             "source_action_excerpt": age, "target_action_excerpt": None,
             "source_time_excerpt": None, "target_time_excerpt": None,
             "unresolved_aspects": ["既有目录未覆盖年龄条件"]},
            {"statement_index": 1, "decision": "additional_requirement", "target_id": None,
             "source_action_excerpt": continuing, "target_action_excerpt": None,
             "source_time_excerpt": "7天", "target_time_excerpt": None,
             "unresolved_aspects": ["持续治疗时间尚未由候选完整表达"]},
        ],
    })
    first = _candidate().model_copy(update={"exception_expression": None})
    second_payload = _candidate_for_second_unit().model_dump(mode="json")
    second_payload["applicability_expression"] = None
    second_payload["exception_expression"] = None
    # Keep action linkage via source_excerpts, but avoid exact obligation equality so
    # coverage stays candidate_linked rather than prematurely expressed.
    continuing_atom_statement = "记录持续治疗安排"
    atom = second_payload["obligation_expression"]["groups"][0]["atoms"][0]
    atom["statement"] = continuing_atom_statement
    atom["source_excerpts"] = [continuing]
    atom["evaluation"] = _evaluation(continuing_atom_statement, "span:02", continuing)
    second_payload["minimum_evidence"][0]["description"] = continuing_atom_statement
    second_payload["minimum_evidence"][0]["source_policy"]["source_excerpts"] = [continuing]
    second = ProtocolControlAgentWireCandidate.model_validate(second_payload)
    wire = _wire_with_two_candidates(first, second)
    alignment = {
        "version": SOURCE_CANDIDATE_ALIGNMENT_VERSION,
        "items": [
            {"statement_index": 0, "candidate_index": 0, "decision": "fully_expressed",
             "source_excerpt": age, "candidate_atom_quotes": ["年龄达到18岁"],
             "unresolved_dimensions": []},
            {"statement_index": 1, "candidate_index": 1, "decision": "incomplete",
             "source_excerpt": continuing,
             "candidate_atom_quotes": [continuing_atom_statement],
             "unresolved_dimensions": ["持续治疗时间窗口"]},
        ],
    }
    return batch, inventory, review, wire, alignment


@pytest.mark.parametrize("failure_kind", ["transport", "interrupted", "identity", "budget"])
def test_alignment_transport_failure_keeps_partial_and_does_not_expand(failure_kind):
    from app.agents.protocol_control_agent_transport import ProtocolControlAgentCallError, ProtocolControlModelIdentityError
    from app.llm.logical_call_budget import LogicalCallBudgetExhausted
    batch, inventory, review, wire, _ = _two_independent_candidate_linked_alignment_material()
    cause = {
        "transport": RuntimeError("synthetic connection failure"),
        "interrupted": ProtocolControlAgentCallError("alignment-failed", "synthetic disconnect", uncertain_completion=True),
        "identity": ProtocolControlModelIdentityError("synthetic wrong model", configured_model="expected", reason="mismatch"),
        "budget": LogicalCallBudgetExhausted("synthetic exhausted budget"),
    }[failure_kind]

    class Transport(_FakeTransport):
        alignment_calls = 0

        def start_source_target_review(self, *, prompt):
            return ProtocolControlAgentResponse(session_id="target", text=review.model_dump_json())

        def start_source_candidate_alignment(self, *, prompt):
            self.alignment_calls += 1
            raise ProtocolControlAgentCallError("wrapped-alignment", "synthetic adapter failure") from cause

        def start_source_insert(self, **kwargs):
            pytest.fail("Transport failure cannot authorize a larger source insert")

        def continue_session(self, **kwargs):
            pytest.fail("Transport failure cannot authorize whole-wire repair")

    transport = Transport([])
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_wire=wire, resume_source_interpretation=inventory,
        resume_session_id="existing-wire", output_validator=lambda _output: None,
    )
    expected = {"transport": "SOURCE_CANDIDATE_ALIGNMENT_TRANSPORT_FAILED", "interrupted": "FLOW_COMPLETION_UNCERTAIN",
                "identity": "MODEL_IDENTITY_INVALID", "budget": "LOGICAL_BUDGET_EXHAUSTED"}[failure_kind]
    assert transport.alignment_calls == 1
    assert result.final_output is None and result.partial_wire == wire
    assert result.source_candidate_alignment is None
    assert result.attempts[-1].error_classes == [expected]
    assert result.attempts[-1].error_detail["statement_ids"] == [0, 1]
    assert result.attempts[-1].error_detail["candidate_indexes"] == [0, 1]


def test_partial_candidate_alignment_keeps_verified_pair_when_sibling_temporal_fails() -> None:
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunResult

    batch, inventory, review, wire, alignment = (
        _two_independent_candidate_linked_alignment_material()
    )

    class Transport(_FakeTransport):
        alignment_prompts: list[str] = []

        def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="source", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="target", text=review.model_dump_json())

        def start_source_candidate_alignment(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.alignment_prompts.append(prompt)
            return ProtocolControlAgentResponse(
                session_id="alignment", text=json.dumps(alignment, ensure_ascii=False),
            )

        def start_source_insert(self, *, prompt: str, multiple: bool) -> ProtocolControlAgentResponse:
            raise AssertionError("兄弟时间缺口不得抹掉已核候选后改走整候选补入")

    transport = Transport([])
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_wire=wire, resume_source_interpretation=inventory,
        resume_session_id="existing-wire", output_validator=lambda _output: None,
    )
    assert transport.alignment_prompts and "年龄至少18岁" in transport.alignment_prompts[0]
    assert "拟参加者须持续接受治疗7天" in transport.alignment_prompts[0]
    assert result.status == "需要核对"
    assert result.final_output is None
    assert result.partial_wire == wire
    assert result.source_candidate_alignment is not None
    saved = ProtocolControlAgentRunResult.model_validate(result.model_dump(mode="json"))
    assert [
        (item.statement_index, item.decision) for item in saved.source_candidate_alignment.items
    ] == [(0, "fully_expressed"), (1, "incomplete")]
    by_index = {entry.statement_index: entry for entry in saved.source_statement_coverage}
    assert by_index[0].status == "semantically_aligned"
    assert by_index[0].candidate_indexes == [0]
    assert by_index[1].status == "candidate_linked"
    details = [
        attempt.error_detail for attempt in saved.attempts
        if "TEMPORAL_SCOPE_UNRESOLVED" in attempt.error_classes
    ]
    assert len(details) == 1
    assert details[0]["statement_ids"] == [1]
    assert details[0]["affected_dependents"] == [1]


def test_resume_skips_only_revalidated_proven_alignment_pair() -> None:
    from app.agents.protocol_control_candidate_alignment import (
        SOURCE_CANDIDATE_ALIGNMENT_VERSION,
        SourceCandidateAlignment,
        bind_candidate_alignment,
    )

    batch, inventory, review, wire, alignment = (
        _two_independent_candidate_linked_alignment_material()
    )
    proven = SourceCandidateAlignment.model_validate({
        "version": SOURCE_CANDIDATE_ALIGNMENT_VERSION,
        "items": [alignment["items"][0]],
    })
    proven = bind_candidate_alignment(
        batch, inventory, source_statement_coverage(batch, inventory, wire), wire,
        proven, proven.model_dump_json(exclude={"proofs"}),
    )

    class ResumeTransport(_FakeTransport):
        alignment_calls = 0
        asked_pairs: list[str] = []

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="target", text=review.model_dump_json())

        def start_source_candidate_alignment(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.alignment_calls += 1
            self.asked_pairs.append(prompt)
            assert "年龄至少18岁" not in prompt or '"statement_index": 0' not in prompt
            assert "拟参加者须持续接受治疗7天" in prompt
            return ProtocolControlAgentResponse(session_id="alignment-2", text=json.dumps({
                "version": SOURCE_CANDIDATE_ALIGNMENT_VERSION,
                "items": [alignment["items"][1]],
            }, ensure_ascii=False))

        def start_source_insert(self, *, prompt: str, multiple: bool) -> ProtocolControlAgentResponse:
            raise AssertionError("续跑不得因已核年龄对而改走补入")

    transport = ResumeTransport([])
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_wire=wire, resume_source_interpretation=inventory,
        resume_session_id="existing-wire",
        resume_source_target_review=review,
        resume_source_statement_coverage=source_statement_coverage(batch, inventory, wire),
        resume_source_candidate_alignment=proven,
        output_validator=lambda _output: None,
    )
    assert transport.alignment_calls == 1
    assert result.status == "需要核对"
    assert result.final_output is None
    assert result.source_candidate_alignment is not None
    assert [
        (item.statement_index, item.decision)
        for item in result.source_candidate_alignment.items
    ] == [(0, "fully_expressed"), (1, "incomplete")]

    stale = SourceCandidateAlignment.model_validate({
        "version": SOURCE_CANDIDATE_ALIGNMENT_VERSION,
        "items": [{
            **alignment["items"][0],
            "candidate_atom_quotes": ["服药至少18天"],
        }],
    })

    class StaleTransport(_FakeTransport):
        alignment_calls = 0

        def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
            return ProtocolControlAgentResponse(session_id="target", text=review.model_dump_json())

        def start_source_candidate_alignment(self, *, prompt: str) -> ProtocolControlAgentResponse:
            self.alignment_calls += 1
            assert '"statement_index": 0' in prompt
            assert '"statement_index": 1' in prompt
            return ProtocolControlAgentResponse(
                session_id="alignment-stale",
                text=json.dumps(alignment, ensure_ascii=False),
            )

        def start_source_insert(self, *, prompt: str, multiple: bool) -> ProtocolControlAgentResponse:
            raise AssertionError("失效对应关系不得改走补入")

    stale_transport = StaleTransport([])
    stale_result = ProtocolControlAgentRunner().run(
        batch, stale_transport, resume_wire=wire,
        resume_source_interpretation=inventory, resume_session_id="stale-wire",
        resume_source_candidate_alignment=stale,
        output_validator=lambda _output: None,
    )
    assert stale_transport.alignment_calls == 1
    assert stale_result.status == "需要核对"
    assert stale_result.source_candidate_alignment is not None
    assert [
        (item.statement_index, item.decision)
        for item in stale_result.source_candidate_alignment.items
    ] == [(0, "fully_expressed"), (1, "incomplete")]


@pytest.mark.parametrize("changed", [
    "observation_scope", "time_constraint", "population", "applicability", "minimum_evidence",
    "source_context", "statement_context", "response", "duplicates", "missing_proof", "legacy",
])
def test_alignment_reuse_requires_unchanged_full_input_and_actual_response(changed) -> None:
    from app.agents.protocol_control_candidate_alignment import (
        SourceCandidateAlignment, bind_candidate_alignment, reusable_proven_alignment_items,
    )
    batch, inventory, _, wire, payload = _two_independent_candidate_linked_alignment_material()
    coverage = source_statement_coverage(batch, inventory, wire)
    parsed = SourceCandidateAlignment.model_validate(payload)
    proven = bind_candidate_alignment(batch, inventory, coverage, wire, parsed,
                                      json.dumps(payload, ensure_ascii=False))
    assert len(reusable_proven_alignment_items(batch, inventory, coverage, wire, proven)) == 1
    candidate = wire.candidate_drafts[0]
    atom = candidate.obligation_expression.groups[0].atoms[0]
    if changed == "observation_scope":
        atom.evaluation = atom.evaluation.model_copy(update={
            "observation_policy": atom.evaluation.observation_policy.model_copy(update={
                "scope": "采用新的记录口径",
            }),
        })
    elif changed == "time_constraint":
        atom.time_constraint = _candidate_for_second_unit().obligation_expression.groups[0].atoms[0].time_constraint
        if atom.time_constraint is None:
            from app.domain.contracts.rules import TimeConstraint
            atom.time_constraint = TimeConstraint.model_validate({
                "anchor_type": "screening_date", "direction": "before",
                "upper_bound_days": 2,
            })
    elif changed == "population":
        candidate.applicable_population = "仅部分受试者"
    elif changed == "applicability":
        candidate.applicability_expression = _candidate().applicability_expression
        candidate.applicability_expression.groups[0].atoms[0].statement += "且满足额外条件"
    elif changed == "minimum_evidence":
        candidate.minimum_evidence[0].description += "另须补充一次记录"
    elif changed == "source_context":
        batch.owned_units[0].heading_path = ["另一适用范围"]
    elif changed == "statement_context":
        inventory.statements[0].scope_quote = "仅部分受试者"
    elif changed == "response":
        proven.proofs[0].response_text += "损坏"
    elif changed == "duplicates":
        proven.items.append(proven.items[0].model_copy(deep=True))
    elif changed == "missing_proof":
        proven.proofs = []
    elif changed == "legacy":
        proven.version = "phase5/control-source-candidate-alignment/v7"
    assert reusable_proven_alignment_items(batch, inventory, coverage, wire, proven) == []


def test_alignment_reader_schema_does_not_delegate_application_proofs() -> None:
    from app.agents.protocol_control_candidate_alignment import candidate_alignment_response_format
    schema = candidate_alignment_response_format()["json_schema"]["schema"]
    assert "proofs" not in schema["properties"]
    assert "SourceCandidateAlignmentProof" not in schema.get("$defs", {})


def test_definition_failure_keeps_alignment_and_exact_wire_then_rechecks_changed_policy(monkeypatch) -> None:
    from app.agents import protocol_control_deconstructor as module
    from tests.v2.agents.test_protocol_control_candidate_alignment import _material, _alignment

    batch, inventory, _, _, review = _material()
    wire = _wire(candidate=_candidate().model_copy(update={"exception_expression": None}))

    class Transport(_FakeTransport):
        calls = 0

        def start_source_target_review(self, *, prompt):
            return ProtocolControlAgentResponse(session_id="target", text=review.model_dump_json())

        def start_source_candidate_alignment(self, *, prompt):
            self.calls += 1
            return ProtocolControlAgentResponse(session_id="alignment", text=_alignment().model_dump_json(
                exclude={"proofs"},
            ))

    monkeypatch.setattr(module, "declare_source_definition_consumers", lambda *_, **__: (None, True))
    transport = Transport([])
    first = ProtocolControlAgentRunner().run(
        batch, transport, resume_wire=wire, resume_source_interpretation=inventory,
        resume_session_id="wire", output_validator=lambda _: None,
    )
    assert first.status == "需要核对" and first.final_output is None
    assert first.partial_wire == wire and first.source_candidate_alignment is not None
    changed = first.partial_wire.model_copy(deep=True)
    atom = changed.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    atom.evaluation = atom.evaluation.model_copy(update={
        "observation_policy": atom.evaluation.observation_policy.model_copy(update={
            "scope": "采用另外一次记录",
        }),
    })
    second = ProtocolControlAgentRunner().run(
        batch, transport, resume_wire=changed, resume_source_interpretation=inventory,
        resume_session_id="changed-wire", output_validator=lambda _: None,
        resume_source_candidate_alignment=first.source_candidate_alignment,
    )
    assert transport.calls == 2
    assert second.final_output is None and second.partial_wire == changed
    assert second.source_candidate_alignment is not None
    assert first.source_candidate_alignment.proofs[0].candidate_sha256 != (
        second.source_candidate_alignment.proofs[0].candidate_sha256
    )


@pytest.mark.parametrize("selected", [None, "visit-a"])
def test_target_review_packet_deduplicates_text_without_merging_visits(selected):
    from app.agents.protocol_control_source_interpretation import _target_review_source_packet
    batch = _batch().model_copy(deep=True)
    quote = "各访视均保留检查原件。" * 80
    batch.known_procedure_targets = [KnownRequiredProcedureTarget(
        catalog_item_id=key, label="检查", visit_instance=visit, review_stage=stage,
        position=index, source_span_ids=["shared-location"], source_excerpts=[quote],
    ) for index, (key, visit, stage) in enumerate((
        ("visit-a", "筛选期", ReviewStage.SCREENING),
        ("visit-b", "基线期", ReviewStage.BASELINE),
    ))]
    targets, excerpts = _target_review_source_packet(batch, selected)
    by_id = {value["excerpt_id"]: value for value in excerpts}
    actual = targets["procedure"]
    assert len(actual) == (2 if selected is None else 1)
    for target in actual:
        assert len(target["shared_visit_source_positions"]) == 1
        ref = target["source_refs"][0]
        assert by_id[ref] == {
            "excerpt_id": ref, "source_position": target["shared_visit_source_positions"][0], "excerpt": quote}
    assert sum(row["excerpt"] == quote for row in excerpts) == 1
    if selected is None:
        assert actual[0]["source_refs"] == actual[1]["source_refs"]
        assert actual[0]["visit_instance"] != actual[1]["visit_instance"]
        assert len(json.dumps((actual, excerpts), ensure_ascii=False)) < len(quote) * 2


@pytest.mark.parametrize("difference", ["text", "position", "missing"])
def test_target_review_packet_keeps_different_or_missing_source_layers(difference):
    from app.agents.protocol_control_source_interpretation import _target_review_source_packet
    batch = _batch().model_copy(deep=True)
    targets = [KnownRequiredProcedureTarget(
        catalog_item_id=f"target-{n}", label="检查", visit_instance="筛选期",
        review_stage=ReviewStage.SCREENING, position=n,
        source_span_ids=["span-a"], source_excerpts=["筛选期完成检查"],
    ) for n in (0, 1)]
    if difference == "text":
        targets[1].source_excerpts = ["筛选期未完成检查"]
    elif difference == "position":
        targets[1].source_span_ids = ["span-b"]
    else:
        targets[1].source_excerpts = []
    batch.known_procedure_targets = targets
    payload, excerpts = _target_review_source_packet(batch, None)
    refs = [target["source_refs"][0] for target in payload["procedure"]]
    assert refs[0] != refs[1]
    assert all("shared_visit_source_positions" not in t for t in payload["procedure"])
    by_id = {e["excerpt_id"]: e for e in excerpts}
    assert (by_id[refs[0]]["source_position"] == by_id[refs[1]]["source_position"]) == (difference != "position")
    assert by_id[refs[1]]["excerpt"] == (
        None if difference == "missing" else targets[1].source_excerpts[0])


def test_target_review_prompt_supplies_force_without_declaring_coverage():
    batch = _batch()
    inventory = SourceInterpretation(version=SOURCE_INTERPRETATION_VERSION,
        statements=[SourceStatement(structure_unit_id="su-01", quoted_text="年龄至少18岁",
            force="recommended", decision_functions=["action"], time_words=[])],
        units_without_statement=["su-02"])
    coverage = [SourceStatementCoverage(statement_index=0, structure_unit_id="su-01",
        disposition="other_control_candidate", status="not_located")]
    prompt = build_source_target_review_prompt(batch, inventory, coverage)
    line = next(line for line in prompt.splitlines() if line.startswith("待核陈述："))
    assert json.loads(line.removeprefix("待核陈述："))[0]["force"] == "recommended"
    assert "force 只记原文语气，不决定是否要核对" in prompt
    assert "不是时间已对应的证明" in prompt
    assert "shared_visit_source_positions" in prompt
