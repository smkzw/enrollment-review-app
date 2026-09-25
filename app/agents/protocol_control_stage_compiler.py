"""Bounded assembly of a single stage-bound source requirement.

The semantic reader chooses the action and its source.  This module supplies
only the mechanical fields of the existing control wire.  Unsupported timing,
conditions, and exceptions remain compilation gaps, not inferred rules.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Literal

from pydantic import Field

from app.domain.contracts.common import ContractModel
from app.domain.contracts.protocol_controls import (
    ControlObligationKind,
    ProtocolControlDispositionBatch,
    ReviewNodeRole,
)
from app.domain.contracts.enums import ReviewStage
from app.protocols.supplementary_relation_contract import procedure_execution_workflow_stage_id

from .protocol_control_deconstructor import (
    ProtocolControlAgentResponse,
    ProtocolControlAgentWire,
    ProtocolControlAgentWireCandidate,
    _merge_source_candidate_insert,
    hydrate_protocol_control_agent_output,
    source_statement_coverage,
)
from .protocol_control_source_interpretation import (
    SourceInterpretation,
    SourceTargetReviewItem,
    normalize_source_excerpt,
)


STAGE_BOUND_REQUIREMENT_VERSION = "phase5/control-stage-bound-requirement/v4"
RELATIVE_STAGE_REQUIREMENT_VERSION = "phase5/control-relative-stage-requirement/v3"


class _SourceRequirement(ContractModel):
    """Only semantic choices shared by the two bounded assembly paths."""

    statement_index: int = Field(ge=0)
    action_excerpt: str = Field(min_length=1)
    stage_scope_excerpt: str = Field(min_length=1)
    workflow_stage_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    applicable_population: str = Field(min_length=1)
    obligation_statement: str = Field(min_length=1)
    kind: Literal["complete_or_verify", "must_record", "must_professional_assessment"]
    determination_mode: Literal["semantic", "investigator_judgment"]
    observation_scope: str = Field(min_length=1)
    fact_type: str = Field(min_length=1)
    evidence_description: str = Field(min_length=1)
    required_source_types: list[str] = Field(min_length=1)
    unresolved_aspects: list[str] = Field(default_factory=list)


class StageBoundRequirement(_SourceRequirement):
    version: Literal[STAGE_BOUND_REQUIREMENT_VERSION]


class RelativeStageRequirement(_SourceRequirement):
    version: Literal[RELATIVE_STAGE_REQUIREMENT_VERSION]
    prior_workflow_stage_id: str = Field(min_length=1)
    target_procedure_id: str = Field(min_length=1)
    relative_time_excerpt: str = Field(min_length=1)


class StageBoundCompilationGap(ValueError):
    """A source dimension cannot be assembled without semantic invention."""


def _time_parts(text: str) -> list[str]:
    return [
        normalize_source_excerpt(part)
        for part in re.split(r"[（）()，,；;]", text)
        if normalize_source_excerpt(part)
    ]


def can_compile_stage_bound_requirement(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    review: SourceTargetReviewItem,
) -> bool:
    """Avoid a model call when the frozen visit cannot cover source timing."""

    if review.decision != "additional_requirement" or review.statement_index >= len(interpretation.statements):
        return False
    statement = interpretation.statements[review.statement_index]
    if (
        statement.force != "required"
        or not statement.scope_quote
        or not statement.time_words
        or statement.exception_words
        or statement.unresolved
    ):
        return False
    required = [part for word in statement.time_words for part in _time_parts(word)]
    scope_parts = _time_parts(statement.scope_quote)
    return bool(scope_parts) and all(part in normalize_source_excerpt(statement.scope_quote) for part in required) and any(
        all(part in normalize_source_excerpt(" ".join(filter(None, (
            stage.display_name, stage.visit_instance, stage.visit_window
        )))) for part in scope_parts)
        for stage in batch.known_workflow_stage_targets
    )


def can_compile_relative_stage_requirement(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    review: SourceTargetReviewItem,
) -> bool:
    if review.decision != "additional_requirement" or review.statement_index >= len(interpretation.statements):
        return False
    statement = interpretation.statements[review.statement_index]
    return bool(
        statement.force == "required"
        and statement.scope_quote
        and not statement.exception_words
        and not statement.unresolved
        and review.target_id
        and any(item.catalog_item_id == review.target_id for item in batch.known_procedure_targets)
        and review.source_time_excerpt
        and normalize_source_excerpt(review.source_time_excerpt)
        in normalize_source_excerpt(statement.quoted_text)
        and all(normalize_source_excerpt(word) in normalize_source_excerpt(statement.quoted_text)
                for word in statement.time_words)
    )


def build_stage_bound_requirement_prompt(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    review: SourceTargetReviewItem,
) -> str:
    """Ask the existing product reader for semantics, not final rule storage."""

    if review.statement_index >= len(interpretation.statements):
        raise StageBoundCompilationGap("增量陈述序位不存在")
    statement = interpretation.statements[review.statement_index]
    if review.decision != "additional_requirement":
        raise StageBoundCompilationGap("本路径只处理已核的增量要求")
    unit = next((item for item in batch.owned_units
                 if item.structure_unit_id == statement.structure_unit_id), None)
    if unit is None:
        raise StageBoundCompilationGap("增量要求不属于冻结来源单元")
    source = {
        "statement_index": review.statement_index,
        "quoted_text": statement.quoted_text,
        "scope_quote": statement.scope_quote,
        "time_words": statement.time_words,
        "force": statement.force,
        "exception_words": statement.exception_words,
        "source_action_excerpt": review.source_action_excerpt,
        "reason_for_insertion": review.unresolved_aspects,
        "owned_unit": {"structure_unit_id": unit.structure_unit_id,
                       "excerpt": unit.excerpt, "heading_path": unit.heading_path},
        "frozen_stages": [
            {"workflow_stage_id": item.workflow_stage_id,
             "review_stage": item.review_stage.value,
             "display_name": item.display_name,
             "visit_instance": item.visit_instance,
             "visit_window": item.visit_window}
            for item in batch.known_workflow_stage_targets
        ],
    }
    return (
        "你是本系统内置方案 Agent 的单项语义解释步骤，不审核受试者，也不输出完整规则。"
        "只处理一个已核实尚未覆盖的原文动作。选择原文逐字动作摘录、逐字访视范围和冻结节点；"
        "不要凭 D 日标记换算首次给药日期或补日历时限。"
        "仅当动作与全部时间措辞均能由同一冻结访视直接支持，且无未明条件、例外、持续期、"
        "复查频率或跨节点义务时才给出可装配的字段。其余情形在 unresolved_aspects 逐项说明，"
        "系统会保留为待核，不能靠你填写其他字段而通过。"
        "reason_for_insertion 只是前一步判定现有目录未完整覆盖的原因，不等于本条原文语义未明；"
        "请勿把它原样复制到 unresolved_aspects。若本条动作/访视本身可解释，该列表应为空。"
        "普通必做操作用 semantic，确需研究者书面判断才用 investigator_judgment；"
        "所需资料种类只能据原文提出，不额外要求未写明的签名或时间。"
        "本路径不向你询问选用哪次观察；原文未规定时系统固定保留为未核实，"
        "不得在其他字段暗示只取一份、最新一份或所有记录。"
        "不要把来源标题、背景信息或已有官方条款文字改写为新动作。"
        "只返回符合随附结构的 JSON 对象。\n"
        f"冻结来源：{json.dumps(source, ensure_ascii=False, sort_keys=True)}"
    )


def stage_bound_requirement_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_stage_bound_requirement_v4",
            "strict": True,
            "schema": StageBoundRequirement.model_json_schema(),
        },
    }


def build_relative_stage_requirement_prompt(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    review: SourceTargetReviewItem,
) -> str:
    if not can_compile_relative_stage_requirement(batch, interpretation, review):
        raise StageBoundCompilationGap("本陈述不具备有源相对节点核查条件")
    statement = interpretation.statements[review.statement_index]
    unit = next(item for item in batch.owned_units
                if item.structure_unit_id == statement.structure_unit_id)
    source = {
        "statement_index": review.statement_index,
        "quoted_text": statement.quoted_text,
        "scope_quote": statement.scope_quote,
        "time_words": statement.time_words,
        "source_action_excerpt": review.source_action_excerpt,
        "source_time_excerpt": review.source_time_excerpt,
        "reason_for_insertion": review.unresolved_aspects,
        "owned_unit": {"structure_unit_id": unit.structure_unit_id,
                       "excerpt": unit.excerpt, "heading_path": unit.heading_path},
        "frozen_stages": [
            {"workflow_stage_id": stage.workflow_stage_id,
             "review_stage": stage.review_stage.value,
             "display_name": stage.display_name,
             "visit_instance": stage.visit_instance,
             "visit_window": stage.visit_window}
            for stage in batch.known_workflow_stage_targets
        ],
        "frozen_procedure_target": [
            {"catalog_item_id": target.catalog_item_id,
             "review_stage": target.review_stage.value,
             "visit_instance": target.visit_instance,
             "source_excerpts": target.source_excerpts}
            for target in batch.known_procedure_targets
            if target.catalog_item_id == review.target_id
        ],
    }
    return (
        "你是本系统内置方案 Agent 的单项相对访视语义解释步骤，不审核受试者。"
        "只解释来源中该动作发生在先前阶段结束后的要求，以及哪个冻结节点承担复核；"
        "不要把相对先后关系换算成首次给药日回溯天数，不把既有目标声称为完全覆盖。"
        "仅当原文相对时间措辞逐字存在、先前与后续审核节点都在冻结目录、"
        "目标流程原文记录同类操作且后续节点确实晚于先前节点时，才给出字段。"
        "若条件、例外、持续期、频次、节点对应关系不清，在 unresolved_aspects 明示，"
        "系统将拒绝装配。reason_for_insertion 是旧目录没有完整表达的原因，"
        "不是本条原文语义未明，不能原样抄入 unresolved_aspects。"
        "按已有入排条款再次核查合格性是 complete_or_verify 加 semantic；"
        "只有原文要求研究者作独立书面临床判断时才用 must_professional_assessment"
        "加 investigator_judgment。两字段不能互相矛盾。"
        "workflow_stage_id 是执行此次核查的后续节点，不是先前导入节点；"
        "先后关系由 prior_workflow_stage_id 和 relative_time_excerpt 表达。"
        "本路径不询问选用哪次记录，原文未定则系统保留未核实。"
        "只返回随附结构的 JSON 对象。\n"
        f"冻结来源：{json.dumps(source, ensure_ascii=False, sort_keys=True)}"
    )


def relative_stage_requirement_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_relative_stage_requirement_v3",
            "strict": True,
            "schema": RelativeStageRequirement.model_json_schema(),
        },
    }


def compile_stage_bound_requirement(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    review: SourceTargetReviewItem,
    selection: StageBoundRequirement | RelativeStageRequirement,
) -> ProtocolControlAgentWireCandidate:
    """Compile only when each source time phrase has a supported stage path.

    This path does not invent calendar lookbacks, conditional branches,
    exceptions, or future continuing obligations.
    """

    if (
        selection.statement_index != review.statement_index
        or selection.statement_index >= len(interpretation.statements)
        or review.decision != "additional_requirement"
    ):
        raise StageBoundCompilationGap("本次解释不是已核的增量来源陈述")
    statement = interpretation.statements[selection.statement_index]
    if selection.unresolved_aspects or statement.unresolved or statement.exception_words:
        raise StageBoundCompilationGap("原文条件、例外或未核实之处不能由单阶段路径装配")
    if statement.force != "required":
        raise StageBoundCompilationGap("单阶段路径只处理已明确的必做要求")
    if selection.kind == ControlObligationKind.MUST_PROFESSIONAL_ASSESSMENT.value:
        if selection.determination_mode != "investigator_judgment":
            raise StageBoundCompilationGap("研究者判断要求须保留独立判断模式")
    elif selection.determination_mode != "semantic":
        raise StageBoundCompilationGap("普通操作不能伪装成研究者判断")

    units = [unit for unit in batch.owned_units if unit.structure_unit_id == statement.structure_unit_id]
    stages = [stage for stage in batch.known_workflow_stage_targets if stage.workflow_stage_id == selection.workflow_stage_id]
    if len(units) != 1 or len(stages) != 1:
        raise StageBoundCompilationGap("来源单元或审核节点不属于本次冻结批次")
    unit, stage = units[0], stages[0]
    source = normalize_source_excerpt(unit.excerpt)
    action = normalize_source_excerpt(selection.action_excerpt)
    scope = normalize_source_excerpt(selection.stage_scope_excerpt)
    if not action or not scope or action not in source:
        raise StageBoundCompilationGap("动作摘录不属于冻结原文")
    if scope not in source and not any(scope in normalize_source_excerpt(part) for part in unit.heading_path):
        raise StageBoundCompilationGap("访视范围摘录不属于冻结原文")
    if action not in normalize_source_excerpt(statement.quoted_text):
        raise StageBoundCompilationGap("动作不属于本条来源陈述")
    if scope != normalize_source_excerpt(statement.scope_quote or ""):
        raise StageBoundCompilationGap("访视范围必须采用已核陈述的原文范围")
    if normalize_source_excerpt(review.source_action_excerpt) not in action:
        raise StageBoundCompilationGap("动作不得省略已核增量摘录中的限定")

    declared_time = [part for word in statement.time_words for part in _time_parts(word)]
    scope_parts = _time_parts(selection.stage_scope_excerpt)
    frozen_visit = normalize_source_excerpt(" ".join(filter(None, (
        stage.display_name, stage.visit_instance, stage.visit_window
    ))))
    relations: list[dict[str, object]] = []
    if isinstance(selection, RelativeStageRequirement):
        previous = next((item for item in batch.known_workflow_stage_targets
                         if item.workflow_stage_id == selection.prior_workflow_stage_id), None)
        procedure = next((item for item in batch.known_procedure_targets
                          if item.catalog_item_id == selection.target_procedure_id), None)
        ordered = list(ReviewStage)
        if (
            previous is None or procedure is None
            or review.target_id != selection.target_procedure_id
            or ordered.index(previous.review_stage) >= ordered.index(stage.review_stage)
            or procedure_execution_workflow_stage_id(
                procedure, batch.known_workflow_stage_targets
            ) != stage.workflow_stage_id
        ):
            raise StageBoundCompilationGap("相对节点先后或流程目标不受冻结目录支持")
        previous_visit = normalize_source_excerpt(" ".join(filter(None, (
            previous.display_name, previous.visit_instance, previous.visit_window
        ))))
        relative = normalize_source_excerpt(selection.relative_time_excerpt)
        target_action = normalize_source_excerpt(review.target_action_excerpt or "")
        if (
            not scope_parts or any(part not in previous_visit for part in scope_parts)
            or not relative or relative != normalize_source_excerpt(review.source_time_excerpt or "")
            or relative not in normalize_source_excerpt(statement.quoted_text)
            or any(part not in relative for part in declared_time)
            or relative not in normalize_source_excerpt(selection.obligation_statement)
            or not target_action
            or not any(target_action in normalize_source_excerpt(value or "")
                       for value in procedure.source_excerpts)
        ):
            raise StageBoundCompilationGap("相对时间、原文动作或流程摘录不能逐项回源")
        relations.append({
            "kind": "supplementary_requirement",
            "external_target_kind": "required_procedure",
            "external_target_id": procedure.catalog_item_id,
            "candidate_side": "left",
            "affected_workflow_stage_id": stage.workflow_stage_id,
            "notes": "原文限定先前阶段结束后再次核查，现有流程仅记录核查动作与访视。",
        })
    elif not declared_time or not scope_parts or any(
        part not in scope for part in declared_time
    ) or any(part not in frozen_visit for part in scope_parts):
        raise StageBoundCompilationGap("原文时间要求未被所选冻结访视逐项覆盖")
    if not selection.observation_scope or not selection.required_source_types:
        raise StageBoundCompilationGap("资料范围或来源类型未说明")

    # The source quote remains exact.  Repeating a span with two distinct
    # excerpts is legal and keeps the action separate from its visit scope.
    if len(unit.source_span_ids) != 1:
        raise StageBoundCompilationGap("多处来源定位需要逐处语义解释")
    spans = [unit.source_span_ids[0], unit.source_span_ids[0]]
    excerpts = [selection.stage_scope_excerpt, statement.quoted_text]
    judgment = selection.determination_mode == "investigator_judgment"
    evaluation = {
        "version": "control-atom-evaluation/v4",
        "determination_mode": selection.determination_mode,
        "proposition": selection.obligation_statement,
        "time_purpose": "not_applicable",
        "repeat_scheme": None,
        "observation_policy": {
            "mode": "unresolved",
            "scope": selection.observation_scope,
            "source_span_ids": spans,
            "source_excerpts": excerpts,
        },
        "source_span_ids": spans,
        "source_excerpts": excerpts,
    }
    try:
        return ProtocolControlAgentWireCandidate.model_validate({
            "title": selection.title,
            "applicable_population": selection.applicable_population,
            "applicability_expression": None,
            "trigger_expression": None,
            "obligation_expression": {"groups": [{"atoms": [{
                "kind": selection.kind,
                "statement": selection.obligation_statement,
                "evaluation": evaluation,
                "time_constraint": None,
                "prospective_period": None,
                "continuing_obligation": None,
                "modality": "mandatory",
                "temporal_scope": None,
                "source_span_ids": spans,
                "source_excerpts": excerpts,
                "requires_professional_judgment": judgment,
            }], "applies_to_trigger_branch_indexes": []}]},
            "exception_expression": None,
            "repeat_trigger_conditions": [],
            "review_node_bindings": [{
                "workflow_stage_id": stage.workflow_stage_id,
                "review_stage": stage.review_stage,
                "role": ReviewNodeRole.DECIDE_AT_NODE,
                "guidance": None,
            }],
            "minimum_evidence": [{
                "fact_type": selection.fact_type,
                "description": selection.evidence_description,
                "due_stage": stage.review_stage,
                "required_source_types": selection.required_source_types,
                "workflow_stage_ids": [stage.workflow_stage_id],
                "source_policy": {
                    "requires_contemporaneous_objective_source": None,
                    "allows_screening_record_transcription": None,
                    "result_validity_status": "not_specified",
                    "result_validity_constraint": None,
                    "source_span_ids": spans,
                    "source_excerpts": excerpts,
                },
                "atom_refs": [{"layer": "obligation", "group_index": 0, "atom_index": 0}],
            }],
            "source_structure_unit_ids": [unit.structure_unit_id],
            "source_span_ids": [unit.source_span_ids[0]],
            "cross_source_relations": relations,
        })
    except ValueError as exc:
        raise StageBoundCompilationGap(str(exc)) from exc


def assemble_source_requirement_inserts(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    reviews: list[SourceTargetReviewItem],
    baseline: ProtocolControlAgentWire,
    responses: list[ProtocolControlAgentResponse],
    output_validator: Callable[..., None],
):
    """Insert all independently read actions as one source-closed batch."""

    if not reviews or len(reviews) != len(responses):
        raise StageBoundCompilationGap("逐项解释回执与待补来源数目不一致")
    candidates = []
    for review, response in zip(reviews, responses, strict=True):
        payload = json.loads(response.text)
        if payload.get("version") == STAGE_BOUND_REQUIREMENT_VERSION:
            selection = StageBoundRequirement.model_validate(payload)
        elif payload.get("version") == RELATIVE_STAGE_REQUIREMENT_VERSION:
            selection = RelativeStageRequirement.model_validate(payload)
        else:
            raise StageBoundCompilationGap("单项解释版本不属于本次装配合同")
        candidates.append(compile_stage_bound_requirement(batch, interpretation, review, selection))
    owned = {interpretation.statements[item.statement_index].structure_unit_id for item in reviews}
    merged = _merge_source_candidate_insert(
        json.dumps({"candidate_drafts": [item.model_dump(mode="json") for item in candidates]}, ensure_ascii=False),
        baseline,
        authorized_unit_ids=owned,
    )
    output = hydrate_protocol_control_agent_output(merged, batch)
    output_validator(output)
    coverage = source_statement_coverage(batch, interpretation, merged)
    if any(coverage[item.statement_index].status != "expressed" for item in reviews):
        raise StageBoundCompilationGap("新增义务没有逐字表达全部授权来源陈述")
    return merged, output, coverage
