"""Bounded reconsideration of an unconsumed source-function disagreement."""

from __future__ import annotations

import json
import re

from app.domain.contracts.protocol_controls import ProtocolControlDispositionBatch

from .protocol_control_source_interpretation import (
    SOURCE_TARGET_REVIEW_VERSION,
    SourceInterpretation,
    SourceInterpretationValidationError,
    SourceStatementCoverage,
    SourceTargetReview,
    SourceTargetReviewItem,
    build_source_interpretation_prompt,
    normalize_source_excerpt,
    parse_product_source_interpretation,
    source_requires_temporal_resolution,
    validate_source_interpretation,
    validate_source_target_review,
)


SOURCE_FUNCTION_RECHECK_VERSION = "phase5/source-function-recheck/v3"
SOURCE_FUNCTION_FIELD_REPAIR_VERSION = "phase5/source-function-field-repair/v1"


def _function_field_repair_source(batch, text, issue):
    if (not isinstance(issue, SourceInterpretationValidationError)
            or issue.code not in {"SOURCE_FUNCTION_UNSTATED", "SOURCE_FUNCTION_UNRESOLVED"}):
        raise ValueError("只可补正已定位的来源用途字段")
    payload = json.loads(text)
    # This object is only a repair input, never an accepted interpretation.
    interpretation = SourceInterpretation.model_validate(payload)
    validate_source_interpretation(batch, interpretation)
    index = issue.statement_id
    if type(index) is not int or not 0 <= index < len(interpretation.statements):
        raise ValueError("来源用途补正位置无效")
    statement = interpretation.statements[index]
    unit = next(unit for unit in batch.owned_units
                if unit.structure_unit_id == statement.structure_unit_id)
    raw = payload["statements"][index]
    missing = "decision_functions" not in raw
    unqualified = raw.get("decision_functions") == ["unclassified"] and not raw.get("unresolved")
    if (issue.structure_unit_id != unit.structure_unit_id
            or issue.source_refs != list(unit.source_span_ids)
            or issue.json_path != f"/statements/{index}/decision_functions"
            or issue.code != ("SOURCE_FUNCTION_UNSTATED" if missing else "SOURCE_FUNCTION_UNRESOLVED")
            or not (missing or unqualified)):
        raise ValueError("来源用途补正与原答或来源见证不一致")
    context = [other for other in [*batch.owned_units, *batch.context_units]
               if other.structure_unit_id != unit.structure_unit_id]
    local = batch.model_copy(update={
        "owned_units": [unit], "context_units": context,
        "owned_structure_unit_ids": [unit.structure_unit_id],
        "context_structure_unit_ids": [other.structure_unit_id for other in context],
        "owned_source_span_ids": list(unit.source_span_ids),
        "context_source_span_ids": list(dict.fromkeys(
            span for other in context for span in other.source_span_ids)),
    })
    return payload, statement, local


def build_source_function_field_repair_prompt(
    batch: ProtocolControlDispositionBatch, text: str,
    issue: SourceInterpretationValidationError,
) -> str:
    _, statement, local = _function_field_repair_source(batch, text, issue)
    return (
        build_source_interpretation_prompt(local)
        + "\n本次只补正指定原陈述的 decision_functions 和 unresolved。"
        "依据冻结原文和上下文说明实际用途，不重读或重写其他陈述。"
        "不能确认用途时可保留 unclassified，但必须写出具体原文疑问；"
        "原有 unresolved 每项疑问均须原样保留，本次不能删除或替换。"
        "不得将接口错误称为研究者医学判断，也不得为了通过而默认 action 或 background。"
        "只返回原 SourceInterpretation 格式：statements 恰一条、"
        "units_without_statement 为空。除这两个字段外所有原字段必须原样保留，"
        "不改摘录、时间、范围、例外、语气和先后关系。提案不是采用依据。\n"
        + json.dumps({"repair_version": SOURCE_FUNCTION_FIELD_REPAIR_VERSION,
                      "statement_index": issue.statement_id,
                      "frozen_statement": statement.model_dump(mode="json")},
                     ensure_ascii=False, sort_keys=True)
    )


def apply_source_function_field_repair(
    batch: ProtocolControlDispositionBatch, text: str,
    issue: SourceInterpretationValidationError, proposal_text: str,
) -> str:
    payload, original, local = _function_field_repair_source(batch, text, issue)
    proposal = parse_product_source_interpretation(local, proposal_text)
    if len(proposal.statements) != 1 or proposal.units_without_statement:
        raise ValueError("来源用途补正只能返回指定的一条原陈述")
    revised = proposal.statements[0]
    if original.model_dump(mode="json", exclude={"decision_functions", "unresolved"}) != revised.model_dump(
        mode="json", exclude={"decision_functions", "unresolved"},
    ):
        raise ValueError("来源用途补正不得改动摘录、范围、时点、例外或兄弟陈述")
    if not set(original.unresolved) <= set(revised.unresolved):
        raise ValueError("来源用途补正不得删除或替换原有疑问")
    validate_source_interpretation(local, proposal)
    # Preserve every raw sibling, including its explicit/omitted fields. The
    # caller must parse and validate the complete merged answer again.
    payload["statements"][issue.statement_id].update(
        decision_functions=revised.decision_functions, unresolved=revised.unresolved,
    )
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


class SourceFunctionRecheckUnresolved(ValueError):
    """An explicit source-function question, not a model-service failure."""


def can_recheck_source_function(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    entry: SourceStatementCoverage,
    item: SourceTargetReviewItem,
) -> bool:
    """Permit a model proposal only where no current consumer may be discarded."""
    index = item.statement_index
    if index != entry.statement_index or index >= len(interpretation.statements):
        return False
    statement = interpretation.statements[index]
    if (entry.structure_unit_id != statement.structure_unit_id
            or statement.force not in {"descriptive", "unclear"}
            or not set(statement.decision_functions) <= {"definition", "time_validity"}
            or statement.unresolved or item.decision not in {"background_context", "unresolved"}
            or entry.status != "not_located"
            or entry.candidate_indexes or entry.action_candidate_indexes
            or entry.linked_candidate_indexes or entry.matched_roles
            or entry.linked_official_code or entry.linked_procedure_target_ids
            or entry.exact_official_excerpt_matches or entry.exact_procedure_excerpt_matches
            or entry.schedule_columns):
        return False
    unit = next((unit for unit in batch.owned_units
                 if unit.structure_unit_id == statement.structure_unit_id), None)
    if unit is None:
        return False
    # Probe inherited headings without altering the verbatim source statement.
    temporal_probe = statement.model_copy(update={
        "quoted_text": " ".join([statement.quoted_text, *unit.heading_path]),
    })
    heading_text = normalize_source_excerpt(" ".join(unit.heading_path))
    if (statement.time_words or statement.affected_stage or statement.scope_quote
            or source_requires_temporal_resolution(temporal_probe)
            or re.search(r"[一二三四五六七八九十百两半]+(?:天|日|周|月|年)|(?:W|D)-?\d+",
                         normalize_source_excerpt(temporal_probe.quoted_text), re.IGNORECASE)
            or any(normalize_source_excerpt(stage.display_name)
                   and normalize_source_excerpt(stage.display_name) in heading_text
                   for stage in batch.known_workflow_stage_targets)):
        return False
    source_spans = set(unit.source_span_ids)
    if any(source_spans.intersection(target.source_span_ids)
           for target in [*batch.known_official_targets, *batch.known_procedure_targets]):
        return False
    # Check every existing background guard, not just the conflict's error code.
    probe = interpretation.model_copy(deep=True)
    probe.statements[index].decision_functions = ["background"]
    try:
        validate_source_target_review(
            batch, probe, [entry], SourceTargetReview(
                version=SOURCE_TARGET_REVIEW_VERSION,
                # Admission probe only; this is never saved as review evidence.
                items=[item.model_copy(update={
                    "decision": "background_context",
                    "non_control_basis_excerpt": statement.quoted_text,
                    "unresolved_aspects": [],
                }) if item.decision == "unresolved" else item],
            ),
        )
    except ValueError:
        return False
    return True


def build_source_function_recheck_prompt(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    statement_index: int,
) -> str:
    statement = interpretation.statements[statement_index]
    unit = next(unit for unit in batch.owned_units
                if unit.structure_unit_id == statement.structure_unit_id)
    seen = {unit.structure_unit_id}
    context = []
    for other in [*batch.owned_units, *batch.context_units]:
        if other.structure_unit_id not in seen:
            seen.add(other.structure_unit_id)
            context.append(other)
    local = batch.model_copy(update={
        "owned_units": [unit], "context_units": context,
        "owned_structure_unit_ids": [unit.structure_unit_id],
        "context_structure_unit_ids": [other.structure_unit_id for other in context],
        "owned_source_span_ids": list(unit.source_span_ids),
        "context_source_span_ids": list(dict.fromkeys(
            span for other in context for span in other.source_span_ids)),
    })
    return (
        build_source_interpretation_prompt(local)
        + "\n本次是单条来源用途分歧核对，不重新生成陈述清单。"
        "第一次读取与后续核对对本条用途有分歧或尚未核清；两次意见都不是正确答案。"
        "请依据原文及上下文判断它是否实际限定审核、定义、取值或时间。"
        "描述研究总时长不一定是背景，描述性语气也不能作为排除依据。"
        "仅在没有实际决策作用时提出 background；否则保留原 decision_functions，"
        "并保持 unresolved 为空，由系统再单条纠正目标核对。"
        "若原文本身确有未核清之处，可在 unresolved 说明具体疑问，"
        "系统将保留原陈述及本次疑问而不采纳分类提案；不得为通过检查而假装确定。"
        "只返回原 SourceInterpretation 格式，statements 恰一条、"
        "units_without_statement 为空。除 decision_functions/unresolved 外"
        "所有字段必须逐项原样保留，不拆句、不改时间、例外或来源。"
        "这只是提案，来源和全部依赖仍由原流程复核。\n"
        + json.dumps({"recheck_version": SOURCE_FUNCTION_RECHECK_VERSION,
                      "frozen_statement": statement.model_dump(mode="json")},
                     ensure_ascii=False, sort_keys=True)
    )


def apply_source_function_recheck(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    entry: SourceStatementCoverage,
    item: SourceTargetReviewItem,
    proposal: SourceInterpretation,
) -> SourceInterpretation:
    if not can_recheck_source_function(batch, interpretation, entry, item):
        raise ValueError("本条存在消费依赖或来源未决，不能局部排除其决策作用")
    if (proposal.version != interpretation.version
            or len(proposal.statements) != 1 or proposal.units_without_statement):
        raise ValueError("用途复核必须且只能返回指定的一条原陈述")
    original = interpretation.statements[item.statement_index]
    revised = proposal.statements[0]
    old = original.model_dump(mode="json", exclude={"decision_functions", "unresolved"})
    new = revised.model_dump(mode="json", exclude={"decision_functions", "unresolved"})
    if old != new:
        raise ValueError("用途复核不得改动原文、时点、例外、范围或其他来源字段")
    if revised.unresolved:
        raise SourceFunctionRecheckUnresolved("本条用途分歧尚未核清，不能按背景处置")
    retained = revised.decision_functions == original.decision_functions
    if not retained and revised.decision_functions != ["background"]:
        raise ValueError("用途复核只可保留原用途或有据提出纯背景")
    result = interpretation.model_copy(deep=True)
    result.statements[item.statement_index] = revised.model_copy(deep=True)
    validate_source_interpretation(batch, result)
    if not retained:
        validate_source_target_review(
            batch, result, [entry], SourceTargetReview(
                version=SOURCE_TARGET_REVIEW_VERSION,
                items=[item],
            ),
        )
    return result
