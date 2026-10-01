"""Bounded reconsideration of an unconsumed source-function disagreement."""

from __future__ import annotations

import json

from app.domain.contracts.protocol_controls import ProtocolControlDispositionBatch

from .protocol_control_source_interpretation import (
    SOURCE_TARGET_REVIEW_VERSION,
    SourceInterpretation,
    SourceStatementCoverage,
    SourceTargetReview,
    SourceTargetReviewItem,
    build_source_interpretation_prompt,
    validate_source_interpretation,
    validate_source_target_review,
)


SOURCE_FUNCTION_RECHECK_VERSION = "phase5/source-function-recheck/v2"


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
            or statement.unresolved or item.decision != "background_context"
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
                items=[item],
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
        "第一次读取和后续核对对本条用途不一致；两次意见都不是正确答案。"
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
