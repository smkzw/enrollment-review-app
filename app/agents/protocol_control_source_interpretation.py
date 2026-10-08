"""Source-bound statement inventory for the existing protocol-control Agent."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from difflib import SequenceMatcher
from typing import Literal

from pydantic import Field, model_validator

from app.domain.contracts.common import ContractModel
from app.domain.contracts.protocol_controls import (
    ControlObligationKind,
    KnownOfficialRuleTarget,
    ProtocolControlDispositionBatch,
    ReviewNodeRole,
    StructureUnitDispositionKind,
)
from app.protocols.protocol_control_gate import _visit_scope_keys
from app.protocols.control_scope_sources import immediate_cell_scope_label
from app.protocols.procedure_catalog import (
    _without_display_footnotes,
    schedule_column_scope,
    schedule_row_values,
)
from app.protocols.source_time_fragments import intraday_time_fragments


SOURCE_INTERPRETATION_VERSION = "phase5/control-source-interpretation/v11"
SOURCE_INTERPRETATION_PROMPT_VERSION = "phase5/control-source-prompt/v22"
SOURCE_QUOTE_RECOVERY_VERSION = "phase5/source-quote-local-recovery/v2"
SOURCE_COVERAGE_VALIDATION_VERSION = "source-owned-inventory-validation/v1"
SOURCE_TARGET_REVIEW_VALIDATION_VERSION = "source-native-procedure-row-validation/v2"
SOURCE_TARGET_REVIEW_VERSION = "phase5/control-source-target-review/v23"
SOURCE_TARGET_REVIEW_POLICY_VERSION = "phase5/control-source-target-policy/v9"


_DAY_WEEK_WINDOW_RE = re.compile(
    r"(?P<anchor>.+?[前后])(?P<number>[1-9]\d{0,3})(?P<unit>天|日|周)"
    r"(?P<boundary>内|以内|以上|以下|不满|超过)?"
)


def _same_explicit_day_week_window(source: str, target: str) -> bool:
    """Only convert exact relative day/week windows with unchanged anchors and bounds."""
    left = _DAY_WEEK_WINDOW_RE.fullmatch(source)
    right = _DAY_WEEK_WINDOW_RE.fullmatch(target)
    if left is None or right is None:
        return False
    if (left["anchor"], left["boundary"]) != (right["anchor"], right["boundary"]):
        return False
    left_days = int(left["number"]) * (7 if left["unit"] == "周" else 1)
    right_days = int(right["number"]) * (7 if right["unit"] == "周" else 1)
    return left_days == right_days

_EXTERNAL_ATTRIBUTION_RE = re.compile(
    r"(?:指南|指导原则|共识|文献|报告|教科书|研究论文)"
    r"[^。！？；;]{0,40}(?:建议|推荐|指出|认为|报道|提出|描述)"
)
_STUDY_ADOPTION_RE = re.compile(
    r"(?:本研究|本方案|本试验|本项目)[^。！？；;]{0,40}"
    r"(?:规定|要求|设定|排除|不得|禁止|必须|须|应)|"
    r"(?:入选|排除|入组)标准|不得随机|不得入组|不予入组"
)


def _object_in_action_clause(text: str, action: str, action_at: int, object_text: str) -> bool:
    # A verbatim clause may include its terminal punctuation, but not two clauses.
    clause_action = action.rstrip("。！？!?；;")
    if (action_at < 0 or not object_text or not clause_action
            or any(mark in clause_action for mark in "。！？!?；;")):
        return False
    start = max((text.rfind(mark, 0, action_at) for mark in "。！？!?；;"), default=-1) + 1
    ends = [text.find(mark, action_at + len(clause_action)) for mark in "。！？!?；;"]
    end = min((pos for pos in ends if pos >= 0), default=len(text))
    return object_text in text[start:end]


def _attribution_in_same_sentence(source: str, quote: str, attribution: str) -> bool:
    text = normalize_source_excerpt(source)
    action = normalize_source_excerpt(quote)
    basis = normalize_source_excerpt(attribution)
    if not action or not basis or not _EXTERNAL_ATTRIBUTION_RE.search(basis):
        return False
    action_at = text.find(action)
    basis_at = text.find(basis)
    if action_at < 0 or basis_at < 0 or text.find(action, action_at + 1) >= 0:
        return False
    if basis_at + len(basis) >= action_at + len(action):
        return False
    start = max((text.rfind(mark, 0, action_at) for mark in "。！？；;"), default=-1) + 1
    ends = [text.find(mark, action_at + len(action)) for mark in "。！？；;"]
    end = min((pos for pos in ends if pos >= 0), default=len(text))
    return basis_at >= start and not _STUDY_ADOPTION_RE.search(text[start:end])


def _has_external_attribution_before_action(source: str, quote: str) -> bool:
    text = normalize_source_excerpt(source)
    action = normalize_source_excerpt(quote)
    action_at = text.find(action) if action else -1
    if action_at < 0:
        return False
    start = max((text.rfind(mark, 0, action_at) for mark in "。！？；;"), default=-1) + 1
    ends = [text.find(mark, action_at + len(action)) for mark in "。！？；;"]
    end = min((pos for pos in ends if pos >= 0), default=len(text))
    return bool(_EXTERNAL_ATTRIBUTION_RE.search(text[start:action_at + len(action)])) and not bool(
        _STUDY_ADOPTION_RE.search(text[start:end])
    )


_ENROLLMENT_DISPOSITIONS = frozenset({
    StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY.value,
    StructureUnitDispositionKind.REQUIRED_PROCEDURE.value,
    StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value,
    StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT.value,
    StructureUnitDispositionKind.PENDING_CONFIRMATION.value,
})

_EXPLICIT_TIME_FRAGMENT_RE = re.compile(
    r"(?:筛选|导入|基线|治疗|研究|试验|随访)期(?:间|内)?|"
    r"(?:筛选|基线|随机(?:化|分组)?|首次给药)(?:前|后|时)|"
    r"(?:W|D)\s*-?\d+\s*[~～至-]\s*(?:W|D)?\s*-?\d+|"
    r"\d+\s*(?:天|日|周|月|年)(?!岁|龄)(?:内|前|后|以上|以下)?|"
    r"每(?:日|天|周|月)(?:\d+|[一二三四五六七八九十]+)次|"
    r"(?:其余|其他|剩余|后续)(?:的)?访视",
    re.IGNORECASE,
)


def _scope_carries_stage_fragment(statement: "SourceStatement", fragment: str) -> bool:
    """A sourced stage label may live in scope; clocks and windows may not."""
    return bool(
        re.fullmatch(r"(?:筛选|导入|基线|治疗|研究|试验|随访)期(?:间|内)?", fragment)
        and fragment in normalize_source_excerpt(statement.scope_quote or "")
        and fragment in normalize_source_excerpt(statement.affected_stage or "")
    )


def _time_words_cover_stage_label(stage: str, time_words: Sequence[str]) -> bool:
    """Keep legacy containing phrases; split lists require whole literal members."""
    words = [normalize_source_excerpt(word) for word in time_words]
    if any(stage in word for word in words if word):
        return True
    ranges = []
    for word in words:
        if not word:
            continue
        start = stage.find(word)
        if start < 0 or stage.find(word, start + 1) >= 0:
            continue
        end = start + len(word)
        if (start and stage[start - 1] not in "、，,") or (end < len(stage) and stage[end] not in "、，,"):
            continue
        ranges.append((start, end))
    if len(ranges) < 2:
        return False
    covered = set(position for start, end in ranges for position in range(start, end))
    return all(position in covered or character in "、，,"
               for position, character in enumerate(stage))


def _unreported_time_fragments(statement: "SourceStatement") -> list[str]:
    reported = [normalize_source_excerpt(word) for word in statement.time_words]
    fragments = {
        normalize_source_excerpt(match.group())
        for is_scope, source in ((False, statement.quoted_text), (True, statement.scope_quote or ""))
        for match in _EXPLICIT_TIME_FRAGMENT_RE.finditer(source)
        if not any(
            title.start() <= match.start() < title.end()
            for title in re.finditer(r"《[^》]*》", source)
        )
        if not (is_scope
                and _scope_carries_stage_fragment(statement, normalize_source_excerpt(match.group())))
    }
    fragments.update(fragment for source in (statement.quoted_text, statement.scope_quote or "")
                     for fragment in intraday_time_fragments(source))
    return sorted(fragment for fragment in fragments if fragment and not any(
        fragment in word for word in reported
    ))


class SourceStatement(ContractModel):
    structure_unit_id: str = Field(min_length=1)
    quoted_text: str = Field(min_length=1)
    scope_quote: str | None = None
    scope_context_unit_id: str | None = Field(default=None, exclude_if=lambda value: value is None)
    force: Literal["required", "prohibited", "recommended", "descriptive", "unclear"]
    decision_functions: list[Literal[
        "action", "definition", "calculation_input", "threshold",
        "time_validity", "exception", "background", "unclassified",
    ]] = Field(default_factory=lambda: ["unclassified"])
    affected_stage: str | None = None
    time_words: list[str] = Field(...)
    exception_words: str | None = None
    unresolved: list[str] = Field(default_factory=list)
    eligibility_sequence: Literal["current_or_unknown", "after_eligibility_decision"] = "current_or_unknown"
    eligibility_sequence_quote: str | None = None
    control_authority: Literal["study_or_unknown", "cited_external_rationale"] = "study_or_unknown"
    attribution_quote: str | None = None

    @model_validator(mode="after")
    def require_coherent_functions(self) -> "SourceStatement":
        if not self.decision_functions or len(self.decision_functions) != len(set(self.decision_functions)):
            raise ValueError("每条陈述须有不重复的决策功能；未知时保留未分类")
        if len(self.decision_functions) > 1 and set(self.decision_functions) & {"background", "unclassified"}:
            raise ValueError("纯背景或未分类不能与决策功能并列")
        return self


class SourceInterpretation(ContractModel):
    version: Literal[SOURCE_INTERPRETATION_VERSION]
    statements: list[SourceStatement]
    units_without_statement: list[str]

    @model_validator(mode="after")
    def require_unique_empty_units(self) -> "SourceInterpretation":
        if len(self.units_without_statement) != len(set(self.units_without_statement)):
            raise ValueError("无独立陈述的来源单元不得重复")
        return self


def normalize_schedule_randomization_anchors(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
) -> tuple[SourceInterpretation, list[str]]:
    """Keep a marker-only schedule row as a workflow anchor, not a new rule."""

    units = {unit.structure_unit_id: unit for unit in batch.owned_units}
    grouped: dict[str, list[SourceStatement]] = {}
    for statement in interpretation.statements:
        grouped.setdefault(statement.structure_unit_id, []).append(statement)
    anchor_ids = {
        unit_id for unit_id, statements in grouped.items()
        if _is_schedule_randomization_anchor(
            units.get(unit_id), statements[0], require_statement_match=False,
        ) and not any(statement.scope_context_unit_id is not None for statement in statements) and (len(statements) != 1 or any(
            statement.quoted_text != units[unit_id].excerpt
            or statement.force != "descriptive"
            or statement.scope_quote is not None
            or statement.affected_stage is not None
            or statement.time_words
            or statement.exception_words is not None
            or statement.unresolved
            for statement in statements
        ))
    }
    if not anchor_ids:
        return interpretation, []
    updated = interpretation.model_copy(deep=True)
    seen: set[str] = set()
    statements = []
    for statement in updated.statements:
        if statement.structure_unit_id not in anchor_ids:
            statements.append(statement)
        elif statement.structure_unit_id not in seen:
            unit = units[statement.structure_unit_id]
            statements.append(SourceStatement(
                structure_unit_id=statement.structure_unit_id,
                quoted_text=unit.excerpt,
                force="descriptive",
                time_words=[],
            ))
            seen.add(statement.structure_unit_id)
    updated.statements = statements
    return updated, sorted(anchor_ids)


def normalize_mixed_schedule_scopes(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
) -> tuple[SourceInterpretation, list[str]]:
    """Remove a column heading misapplied to an entire mixed-stage X row."""

    units = {unit.structure_unit_id: unit for unit in batch.owned_units}
    updated = interpretation.model_copy(deep=True)
    changed: list[str] = []
    for statement in updated.statements:
        unit = units[statement.structure_unit_id]
        scope = normalize_source_excerpt(statement.scope_quote or "")
        if (
            not scope or statement.scope_context_unit_id is not None or statement.time_words
            or statement.affected_stage is not None or statement.exception_words is not None
            or statement.unresolved or scope in normalize_source_excerpt(unit.excerpt)
            or any(scope in normalize_source_excerpt(part) for part in unit.heading_path)
            or not schedule_column_links(batch, unit.structure_unit_id, statement.quoted_text)
        ):
            continue
        columns = schedule_column_scope(unit, batch.context_units)
        if columns and any(scope in normalize_source_excerpt(column.header_text)
                           for column in columns) and not all(
            scope in normalize_source_excerpt(column.header_text) for column in columns
        ):
            statement.scope_quote = None
            changed.append(unit.structure_unit_id)
    return updated, changed


class SourceQuoteCorrection(ContractModel):
    version: Literal["phase5/control-source-quote-correction/v1"]
    structure_unit_id: str = Field(min_length=1)
    corrected_quote: str | None = None
    unresolved: str | None = None


class SourceScopeCorrection(ContractModel):
    version: Literal["phase5/control-source-scope-correction/v1"]
    structure_unit_id: str = Field(min_length=1)
    scope_quote: str | None = None
    scope_context_unit_id: str | None = Field(default=None, exclude_if=lambda value: value is None)
    affected_stage: str | None = None
    time_words: list[str] = Field(...)
    unresolved: str | None = None


def native_schedule_scope_requires_recheck(
    batch: ProtocolControlDispositionBatch, statement: SourceStatement,
) -> bool:
    """Select a missing source dependency from native structure, not reviewer wording."""
    if statement.scope_quote is not None or statement.affected_stage is not None or statement.time_words:
        return False
    unit = next((item for item in batch.owned_units
                 if item.structure_unit_id == statement.structure_unit_id), None)
    if unit is None:
        return False
    columns = schedule_column_scope(unit, batch.context_units)
    return bool(columns) and all(
        native_schedule_time_excerpt_is_grounded(batch, statement, column.header_text)
        for column in columns
    )


def native_schedule_time_excerpt_is_grounded(
    batch: ProtocolControlDispositionBatch, statement: SourceStatement, excerpt: str | None,
) -> bool:
    """Select an existing scope recheck, never authorize a reviewer-supplied time."""
    unit = next((unit for unit in batch.owned_units
                 if unit.structure_unit_id == statement.structure_unit_id), None)
    value = normalize_source_excerpt(excerpt or "")
    if (unit is None or not value or statement.scope_context_unit_id is not None
            or normalize_source_excerpt(statement.quoted_text) != normalize_source_excerpt(unit.excerpt)):
        return False
    columns = schedule_column_scope(unit, batch.context_units)
    source_texts = {
        ref: normalize_source_excerpt(text)
        for source_unit in [*batch.owned_units, *batch.context_units]
        if source_unit.member_texts is not None
        for ref, text in zip(source_unit.member_source_refs, source_unit.member_texts or [], strict=True)
    }
    return bool(columns) and all(
        column.header_source_refs and not column.visit_unresolved and not column.marker_footnotes
        and (value == normalize_source_excerpt(column.header_text)
             or value in {source_texts.get(ref) for ref in column.header_source_refs})
        for column in columns
    )


def build_source_scope_correction_prompt(
    batch: ProtocolControlDispositionBatch, statement: SourceStatement, issue: str,
) -> str:
    unit = next((item for item in batch.owned_units
                 if item.structure_unit_id == statement.structure_unit_id), None)
    if unit is None:
        raise ValueError("待校正陈述不属于冻结来源")
    columns = schedule_column_scope(unit, batch.context_units)
    column_sources = [{
        "cell_path": column.cell_path, "cell_source_ref": column.cell_source_ref,
        "header_text": column.header_text, "header_source_refs": column.header_source_refs,
        "boundary_side": column.boundary_side, "visit_unresolved": column.visit_unresolved,
        "marker_footnotes": column.marker_footnotes,
    } for column in columns]
    return (
        "你是内置方案 Agent 的单条来源范围核对步骤。只核原文动作的适用范围、阶段和时间；"
        "动作摘录、条件、例外及其他陈述已经冻结，不得改写。"
        "time_words 只保留真正约束本条动作且逐字位于本条、其前置共同范围或所属标题的短语；"
        "冻结单元若含多条陈述，不得借同单元另一条陈述的时点；"
        "相邻 context 单元不能任意借用。仅当只读单元是同一单元格内紧邻在前、以冒号结束的完整项目标签，"
        "而非动作、时间或例外句，且你核实它直接限定本条对象时，scope_quote 可逐字引用整个标签，"
        "scope_context_unit_id 填该冻结单元ID；否则该ID填 null。这种引用不能补 time_words 或 affected_stage。"
        "引用ID必须出现在本条可核只读标签列表；列表为空时必须填 null，不从其他 context 自选。"
        "日程表另有下方逐列来源：标记所在单元格与访视列标题具有原生行列关系，"
        "不是前述同格项目标签。可核只读标签为空不表示没有访视列标题。"
        "若原文范围逐字存在于本行全部标记列的有源标题中，可在 scope_quote 引用该共同短语，"
        "scope_context_unit_id 仍为 null；affected_stage/time_words 仅可引用该范围内的原词。"
        "不同标记列没有同一范围时不得压成一个阶段；保留具体疑问。缺标题来源、访视未清或脚注有疑问时不能猜。"
        "只有一个标记列且可确认时，scope_quote 保留该列完整 header_text，不只摘一个时期或日数；"
        "完整表头共同说明同一次访视，不把组成短语数量当访视次数。"
        "上轮错误字段不可照抄：若共享范围不在本条动作前的同一来源单元、所属标题或表格标题中，且无上述可核标签，"
        "scope_quote 填 null；本条没有对应时间原文则 time_words 填空数组。"
        "本条括号内的临床子条件若有独立回溯期限也要逐项列出，文献书名的版本年份不算；"
        "本条及所属标题直接写出的时间不得删除。无法确认时 unresolved 写原因，"
        "I/II/III/IV 期是研究期别，不是受试者访视阶段或动作时间：保留在原句或有据共享范围，"
        "不要放进 affected_stage、time_words。"
        "其余字段按原文填写；能够确认则 unresolved 为 null。"
        "只返回一个 JSON 对象，字段必须齐全，version 必须逐字填写"
        ' "phase5/control-source-scope-correction/v1"，不得写成 1.0 或其他缩写。'
        "字段为 version、structure_unit_id、scope_quote、scope_context_unit_id、affected_stage、time_words、unresolved；"
        "可空字段无依据时填 null，time_words 无依据时填空数组。\n"
        f"上轮错误：{issue[:1000]}\n"
        f"冻结单元：{json.dumps({'structure_unit_id': unit.structure_unit_id, 'heading_path': unit.heading_path, 'excerpt': unit.excerpt, 'table_context': unit.table_context.model_dump(mode='json') if unit.table_context else None}, ensure_ascii=False)}\n"
        f"可核只读标签：{json.dumps(_cell_scope_label_packet(batch, unit), ensure_ascii=False)}\n"
        f"标记列原生来源：{json.dumps(column_sources, ensure_ascii=False)}\n"
        f"原陈述：{statement.model_dump_json()}"
    )


SOURCE_SCOPE_QUESTION_RECHECK_VERSION = "phase5/source-scope-question-recheck/v1"


def can_recheck_source_scope_question(
    statement: SourceStatement, batch: ProtocolControlDispositionBatch | None = None,
) -> bool:
    """Select a source question, never infer the clinical relationship of its times."""
    literal_times = (len(set(statement.time_words)) >= 2
            and all(normalize_source_excerpt(word) in normalize_source_excerpt(statement.quoted_text)
                    for word in statement.time_words))
    columns = ()
    if batch is not None:
        unit = next((unit for unit in batch.owned_units
                     if unit.structure_unit_id == statement.structure_unit_id), None)
        if unit is not None:
            columns = schedule_column_scope(unit, batch.context_units)
    native_scope = bool(columns) and all(column.header_source_refs and column.header_text
                                        and not column.visit_unresolved for column in columns)
    return bool(statement.unresolved) and statement.affected_stage is None and (literal_times or native_scope)


def build_source_scope_question_prompt(
    batch: ProtocolControlDispositionBatch, interpretation: SourceInterpretation, index: int,
) -> str:
    statement = interpretation.statements[index]
    if not can_recheck_source_scope_question(statement, batch):
        raise ValueError("本条不属于多时间来源疑问核对范围")
    unit = next(unit for unit in batch.owned_units
                if unit.structure_unit_id == statement.structure_unit_id)
    return (
        "你是内置方案 Agent 的单条原文范围疑问核对步骤。只核 unresolved 中的疑问是否"
        "确实由原文引起，不生成规则、不判断受试者。不同子条件可以各有自己的时间限定，"
        "没有共同 affected_stage 本身不构成原文歧义；也不能因此把所有分支套到同一阶段。"
        "逐项核原句的并列/选择、否定、对象与各自时间关系；若确有两种影响临床含义的解释，"
        "保留具体 unresolved，不能为了通过检查删除。仅当原文明确、疑问仅来自要求统一阶段时"
        "才可提出 unresolved 为空数组。原文、逻辑、时间词、范围、用途及其余字段逐项原样保留。"
        "返回原 SourceInterpretation JSON：version 原样，statements 恰为指定一条，"
        "units_without_statement 为空。普通原句仅 unresolved 可改变；若下方有原生标记列来源，"
        "另可按单条来源范围核对规则补 scope_quote/affected_stage/time_words，scope_context_unit_id 不变，"
        "不得删除原句已有时间词，只能引用全部标记列共有的原文范围。无共同范围、脚注或真实关系未清时保留疑问。"
        "不存在既有流程项不能作为忽略原文访视列的理由，也不得借另一个动作的流程项。此提案还须完整来源与目标核对，"
        "不是采用证明。\n"
        + json.dumps({"recheck_version": SOURCE_SCOPE_QUESTION_RECHECK_VERSION,
                      "version": interpretation.version,
                      "frozen_statement": statement.model_dump(mode="json"),
                      "source_unit": unit.model_dump(mode="json"),
                      "native_scope_instruction": build_source_scope_correction_prompt(batch, statement, "原有来源范围疑问")
                          if schedule_column_scope(unit, batch.context_units) else None}, ensure_ascii=False)
    )


def apply_source_scope_question_recheck(
    batch: ProtocolControlDispositionBatch, interpretation: SourceInterpretation,
    index: int, proposal: SourceInterpretation,
) -> SourceInterpretation:
    original = interpretation.statements[index]
    if (not can_recheck_source_scope_question(original, batch) or proposal.version != interpretation.version
            or len(proposal.statements) != 1 or proposal.units_without_statement):
        raise ValueError("时间疑问核对必须只返回指定原陈述")
    revised = proposal.statements[0]
    unit = next(unit for unit in batch.owned_units if unit.structure_unit_id == original.structure_unit_id)
    native = bool(schedule_column_scope(unit, batch.context_units))
    allowed = {"unresolved", "scope_quote", "affected_stage", "time_words"} if native else {"unresolved"}
    if (original.model_dump(mode="json", exclude=allowed)
            != revised.model_dump(mode="json", exclude=allowed)):
        raise ValueError("时间疑问核对不得改变原文、逻辑、范围、时间或其他来源字段")
    if native:
        # Reuse the existing scope gate and preservation rules, not a new adoption policy.
        apply_source_scope_correction(batch, interpretation, index, SourceScopeCorrection(
            version="phase5/control-source-scope-correction/v1",
            structure_unit_id=revised.structure_unit_id, scope_quote=revised.scope_quote,
            scope_context_unit_id=revised.scope_context_unit_id,
            affected_stage=revised.affected_stage, time_words=revised.time_words,
        ))
    result = interpretation.model_copy(deep=True)
    result.statements[index] = revised.model_copy(deep=True)
    validate_source_interpretation(batch, result)
    return result


def source_scope_correction_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_source_scope_correction_v1",
            "strict": True,
            "schema": SourceScopeCorrection.model_json_schema(),
        },
    }


def apply_source_scope_correction(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    statement_index: int,
    correction: SourceScopeCorrection,
) -> SourceInterpretation:
    statement = interpretation.statements[statement_index]
    source_unit = next(unit for unit in batch.owned_units
                       if unit.structure_unit_id == statement.structure_unit_id)
    unit = next((item for item in batch.owned_units
                 if item.structure_unit_id == statement.structure_unit_id), None)
    if unit is None or correction.structure_unit_id != statement.structure_unit_id or correction.unresolved:
        raise ValueError("单条来源范围仍未核清")
    direct_locations = [statement.quoted_text, *unit.heading_path]
    for word in statement.time_words:
        if is_study_phase_label(word):
            continue
        normalized = normalize_source_excerpt(word)
        if any(normalized in normalize_source_excerpt(part) for part in direct_locations) and word not in correction.time_words:
            raise ValueError("陈述或标题中的明确时间不可在局部校正时删除")
    if statement.affected_stage and not is_study_phase_label(statement.affected_stage) and any(
        normalize_source_excerpt(statement.affected_stage) in normalize_source_excerpt(part)
        for part in direct_locations
    ) and correction.affected_stage != statement.affected_stage:
        raise ValueError("陈述或标题中的明确阶段不可在局部校正时删除")
    updated = interpretation.model_copy(deep=True)
    phase_supported = any(
        normalize_source_excerpt(part)
        and any(
            is_study_phase_label(word)
            and normalize_source_excerpt(word) in normalize_source_excerpt(part)
            for word in (statement.affected_stage, *statement.time_words)
            if word
        )
        for part in [statement.quoted_text, correction.scope_quote or "", *unit.heading_path]
    )
    updated.statements[statement_index].scope_quote = correction.scope_quote
    updated.statements[statement_index].scope_context_unit_id = correction.scope_context_unit_id
    updated.statements[statement_index].affected_stage = (
        None if phase_supported and correction.affected_stage
        and is_study_phase_label(correction.affected_stage)
        else correction.affected_stage
    )
    updated.statements[statement_index].time_words = [
        word for word in correction.time_words
        if not (phase_supported and is_study_phase_label(word))
    ]
    isolated = SourceInterpretation(
        version=SOURCE_INTERPRETATION_VERSION,
        statements=[updated.statements[statement_index]],
        units_without_statement=[
            item.structure_unit_id for item in batch.owned_units
            if item.structure_unit_id != statement.structure_unit_id
        ],
    )
    validate_source_interpretation(batch, isolated)
    return updated


def build_source_quote_correction_prompt(
    batch: ProtocolControlDispositionBatch,
    statement: SourceStatement,
    issue_code: str = "SOURCE_QUOTE_UNGROUNDED",
) -> str:
    unit = next(
        (item for item in batch.owned_units
         if item.structure_unit_id == statement.structure_unit_id), None
    )
    if unit is None:
        raise ValueError("待校正陈述不属于冻结来源")
    issue_guidance = (
        "前次把资格确认的先决语句并入了其后动作的 quoted_text。"
        "只截取先决语句之后的同一动作，eligibility_sequence_quote 保持原文不变；"
        "不能删掉实际属于该动作的时间、数值、否定或例外。"
        if issue_code == "POST_ELIGIBILITY_SEQUENCE_UNGROUNDED"
        else "前次摘录不属于冻结原文。"
    )
    return (
        "你是内置方案 Agent 的逐字来源校正步骤。" + issue_guidance
        + "只从同一单元标题或正文选取表达原陈述同一要求的连续原句；"
        "不要换另一条要求、增加临床解释或改写数值、否定、时间与例外。"
        "无法逐字定位同一要求时 corrected_quote 填 null，并在 unresolved 说明。"
        "可以找到时 unresolved 填 null。只返回一个 JSON 对象，version 必须逐字填写"
        ' "phase5/control-source-quote-correction/v1"，不得写成 1.0 或其他缩写。'
        "字段为 version、structure_unit_id、corrected_quote、unresolved；可空字段无依据时填 null。\n"
        f"冻结单元：{json.dumps({'structure_unit_id': unit.structure_unit_id, 'heading_path': unit.heading_path, 'excerpt': unit.excerpt}, ensure_ascii=False)}\n"
        f"待校正陈述：{statement.model_dump_json()}"
    )


def source_quote_correction_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_source_quote_correction_v1",
            "strict": True,
            "schema": SourceQuoteCorrection.model_json_schema(),
        },
    }


def apply_source_quote_correction(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    statement_index: int,
    correction: SourceQuoteCorrection,
) -> SourceInterpretation:
    statement = interpretation.statements[statement_index]
    unit = next(
        (item for item in batch.owned_units
         if item.structure_unit_id == statement.structure_unit_id), None
    )
    new_quote = normalize_source_excerpt(correction.corrected_quote or "")
    old_quote = normalize_source_excerpt(statement.quoted_text)
    protected_marks = re.compile(
        r"不得|不可|不能|不允许|禁止|必须|除外|除非|否则|仅当|只有|如果|可以|应当|建议|"
        r"至少|至多|不超过|不低于|不高于|超过|低于|高于|未|无|不|须|应|若|≤|≥|<|>|"
        r"\b(?:not|no|never|must|shall|may|unless|except)\b", re.IGNORECASE,
    )
    chinese_quantity = re.compile(
        r"[零〇一二两三四五六七八九十百千万]+(?:个)?"
        r"(?:小时|分钟|天|日|周期|周|月|年|次|例|岁|毫克|微克|毫升)(?:内|前|后|以上|以下)?"
    )
    # Text similarity locates a spelling repair; it is not semantic equivalence.
    if (
        protected_marks.findall(unicodedata.normalize("NFKC", statement.quoted_text).casefold())
        != protected_marks.findall(unicodedata.normalize("NFKC", correction.corrected_quote or "").casefold())
        or chinese_quantity.findall(old_quote) != chinese_quantity.findall(new_quote)
        or any(
            normalize_source_excerpt(part) in old_quote
            and normalize_source_excerpt(part) not in new_quote
            for part in [*statement.time_words, statement.exception_words or ""]
            if normalize_source_excerpt(part)
        )
    ):
        raise ValueError("局部摘录校正不得改变否定、强度、数量、已核时间或例外")
    if (
        unit is None
        or correction.structure_unit_id != statement.structure_unit_id
        or correction.unresolved is not None
        or not new_quote
        or not any(new_quote in normalize_source_excerpt(part)
                   for part in [*unit.heading_path, unit.excerpt])
        or re.findall(r"\d+(?:\.\d+)?", old_quote) != re.findall(r"\d+(?:\.\d+)?", new_quote)
        or SequenceMatcher(None, old_quote, new_quote).ratio() < 0.75
    ):
        raise ValueError("校正后的摘录不能证明是同一来源要求")
    updated = interpretation.model_copy(deep=True)
    updated.statements[statement_index].quoted_text = correction.corrected_quote
    isolated = SourceInterpretation(
        version=SOURCE_INTERPRETATION_VERSION,
        statements=[updated.statements[statement_index]],
        units_without_statement=[
            item.structure_unit_id for item in batch.owned_units
            if item.structure_unit_id != statement.structure_unit_id
        ],
    )
    validate_source_interpretation(batch, isolated)
    return updated


class ScheduleColumnLink(ContractModel):
    column_index: int = Field(ge=0)
    cell_source_ref: str = Field(min_length=1)
    header_source_refs: list[str]
    visit_instance: str
    boundary_side: Literal["at_or_before_baseline", "after_baseline"]
    procedure_target_id: str | None = None
    marker_footnotes: list[str] = Field(default_factory=list)


class SourceStatementCoverage(ContractModel):
    statement_index: int = Field(ge=0)
    structure_unit_id: str = Field(min_length=1)
    disposition: str = Field(min_length=1)
    status: Literal["expressed", "semantically_aligned", "candidate_linked", "linked_only", "not_located"]
    candidate_indexes: list[int] = Field(default_factory=list)
    linked_candidate_indexes: list[int] = Field(default_factory=list)
    action_candidate_indexes: list[int] = Field(default_factory=list)
    matched_roles: list[Literal["applicability", "trigger", "obligation", "continuing", "exception"]] = Field(default_factory=list)
    linked_official_code: str | None = None
    linked_procedure_target_ids: list[str] = Field(default_factory=list)
    exact_official_excerpt_matches: list[str] = Field(default_factory=list)
    exact_procedure_excerpt_matches: list[str] = Field(default_factory=list)
    schedule_columns: list[ScheduleColumnLink] = Field(default_factory=list)


def schedule_column_links(
    batch: ProtocolControlDispositionBatch,
    structure_unit_id: str,
    quoted_text: str,
) -> list[ScheduleColumnLink]:
    """Close only a literal X row whose every enrollment column has a frozen target."""

    unit = next((item for item in batch.owned_units
                 if item.structure_unit_id == structure_unit_id), None)
    if unit is None or normalize_source_excerpt(quoted_text) != normalize_source_excerpt(unit.excerpt):
        return []
    table_root = unit.source_ref.rpartition(".r")[0]
    sibling_rows = [item for item in batch.owned_units
                    if item.structure_unit_id != unit.structure_unit_id
                    and item.source_ref.rpartition(".r")[0] == table_root]
    columns = schedule_column_scope(unit, [*batch.context_units, *sibling_rows])
    if not columns or any(column.boundary_side == "unresolved" for column in columns):
        return []
    row_values = schedule_row_values(unit, [*batch.context_units, *sibling_rows])
    row_token = unit.source_ref.rpartition(".r")[2]
    if "." in row_token:
        header_columns = [
            path[-1] + (span or 1) - 1
            for header in [*batch.context_units, *sibling_rows]
            if (header.table_context is not None
                and header.source_ref.rpartition(".r")[0] == table_root
                and header.table_context.row_index < unit.table_context.row_index)
            for path, span in zip(
                header.table_context.member_cell_paths,
                header.table_context.member_cell_col_spans
                or [None] * len(header.table_context.member_cell_paths),
                strict=True,
            )
        ]
        if (not header_columns or not row_values
                or {column for column, _text, _refs in row_values}
                != set(range(max(header_columns) + 1))):
            return []
    parts = [text for _column, text, _refs in row_values]
    # A parenthesized mark can be conditional on a visit note; it is not an
    # unconditional X that the existing-procedure shortcut may close.
    if any(
        text.strip().startswith(("(", "（"))
        for column, text, _refs in row_values
        if any(scope.column_index == column and scope.boundary_side == "at_or_before_baseline"
               for scope in columns)
    ):
        return []
    if len(parts) != len(columns) + 1 or not parts[0].strip() or any(
        not re.fullmatch(r"[（(]?\s*[xX×]\s*[)）]?(?:\^\d+)*", part.strip())
        for part in parts[1:]
    ):
        return []
    label_sources = _schedule_label_sources(batch, unit, row_values, sibling_rows)
    if not label_sources:
        return []
    links: list[ScheduleColumnLink] = []
    for column in columns:
        target_id = None
        if column.boundary_side == "at_or_before_baseline":
            if column.marker_footnotes:
                return []
            matches = [target for target in batch.known_procedure_targets
                       if target.visit_instance == column.header_text
                       and target.review_stage == column.review_stage
                       and _target_contains_row_label(target, label_sources)]
            if len(matches) != 1:
                return []
            target_id = matches[0].catalog_item_id
        links.append(ScheduleColumnLink(
            column_index=column.column_index,
            cell_source_ref=column.cell_source_ref,
            header_source_refs=list(column.header_source_refs),
            visit_instance=column.header_text,
            boundary_side=column.boundary_side,
            procedure_target_id=target_id,
            marker_footnotes=list(column.marker_footnotes),
        ))
    return links if any(link.procedure_target_id for link in links) else []


def _schedule_label_sources(batch, unit, row_values, sibling_rows=()) -> list[tuple[str, str]]:
    if not row_values or row_values[0][0] != 0:
        return []
    label_refs = set(row_values[0][2])
    label_sources: list[tuple[str, str]] = []
    mapped_refs: set[str] = set()
    for row_unit in [unit, *batch.context_units, *sibling_rows]:
        if row_unit.member_source_span_ids is None:
            continue
        for ref, spans, text in zip(
            row_unit.member_source_refs, row_unit.member_source_span_ids,
            row_unit.member_texts or [], strict=True,
        ):
            if ref in label_refs:
                mapped_refs.add(ref)
                label_sources.extend((span, text) for span in spans)
    if mapped_refs and mapped_refs != label_refs:
        return []
    if not label_sources:
        # Old frozen units did not retain a per-member span mapping. A short
        # locator can still be proved; hashed locators remain unresolved.
        label_ref = row_values[0][2][0]
        label_span = next((span for span in unit.source_span_ids if span.endswith(f"::{label_ref}")), None)
        if label_span is not None:
            label_sources = [(label_span, row_values[0][1])]
    if not label_sources:
        return []
    return label_sources


def _target_contains_row_label(target, label_sources) -> bool:
    return bool(target.source_excerpts) and all(
        any(span == target_span and normalize_source_excerpt(text)
            in normalize_source_excerpt(excerpt or "")
            for target_span, excerpt in zip(target.source_span_ids, target.source_excerpts, strict=True))
        for span, text in label_sources
    )


def _statement_schedule_label_sources(batch, statement) -> list[tuple[str, str]]:
    unit = next((item for item in batch.owned_units
                 if item.structure_unit_id == statement.structure_unit_id), None)
    if unit is None or unit.table_context is None:
        return []
    table_root = unit.source_ref.rpartition(".r")[0]
    siblings = [item for item in batch.owned_units
                if item.structure_unit_id != unit.structure_unit_id
                and item.source_ref.rpartition(".r")[0] == table_root]
    values = schedule_row_values(unit, [*batch.context_units, *siblings])
    if (not values or not values[0][1].strip()
            or normalize_source_excerpt(values[0][1])
            not in normalize_source_excerpt(statement.quoted_text)):
        return []
    return _schedule_label_sources(batch, unit, values, siblings)


class SourceTargetReviewItem(ContractModel):
    statement_index: int = Field(ge=0)
    decision: Literal[
        "covered_by_official", "covered_by_procedure", "additional_requirement",
        "not_current_control", "unresolved", "potential_same_requirement",
        "cited_external_rationale", "background_context", "definition_dependency",
    ]
    target_id: str | None = None
    source_action_excerpt: str = Field(min_length=1)
    target_action_excerpt: str | None = None
    source_time_excerpt: str | None = None
    target_time_excerpt: str | None = None
    target_scope_excerpt: str | None = None
    source_object_excerpt: str | None = None
    target_object_excerpt: str | None = None
    unresolved_aspects: list[str] = Field(default_factory=list)
    non_control_basis_excerpt: str | None = None
    attribution_excerpt: str | None = None


class SourceTargetReview(ContractModel):
    version: Literal[SOURCE_TARGET_REVIEW_VERSION]
    items: list[SourceTargetReviewItem]


def is_post_eligibility_calculation(
    statement: SourceStatement, review: SourceTargetReviewItem | None,
) -> bool:
    """Exclude only a proven later-stage calculation from current eligibility."""
    return bool(
        review is not None
        and review.decision == "not_current_control"
        and set(statement.decision_functions) <= {"action", "calculation_input"}
        and getattr(statement, "eligibility_sequence", "current_or_unknown")
        == "after_eligibility_decision"
        and not statement.unresolved
        and not review.unresolved_aspects
    )


SOURCE_DEFINITION_CONSUMER_VERSION = "phase5/control-source-definition-consumer/v3"


class SourceDefinitionAtomConsumer(ContractModel):
    """One bounded declaration of a consumer that evaluates a source definition.

    Three consumer kinds are declared and never substituted for each other:

    * ``control_atom`` — a hydrated control candidate atom. Candidate indexes
      are batch-local and are resolved by the execution layer against the frozen
      hydrated candidates.
    * ``official_predicate`` — an ``AtomicPredicate`` of the frozen official
      rules. The official code is checked against the batch's frozen official
      targets, and the ``(rule_component_id, predicate_id)`` identity is proven
      later against the frozen RuleSet; a parent IN/EX code is never accepted as
      the consumer identity.
    * ``restricted_statement`` — an actual non-executable source statement.
      It records a dependency, never a clinical truth or a made-up atom.

    The declaration carries the consumer's own source excerpt as its anchor; the
    definition quote is already stored on the record, and the two anchors are
    validated against their own frozen sources instead of being required to
    overlap. The optional relation note may explain the proposed connection but
    never proves it.
    """

    consumer_kind: Literal["control_atom", "official_predicate", "restricted_statement"] = "control_atom"
    restricted_statement_id: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)
    candidate_index: int | None = Field(default=None, ge=0)
    layer: Literal["applicability", "trigger", "obligation", "exception", "repeat_trigger"] | None = None
    group_index: int | None = Field(default=None, ge=0)
    atom_index: int | None = Field(default=None, ge=0)
    condition_id: str | None = Field(default=None, min_length=1)
    official_code: str | None = Field(default=None, pattern=r"^(IN|EX)-\d{2}$")
    rule_component_id: str | None = Field(default=None, min_length=1)
    predicate_id: str | None = Field(default=None, min_length=1)
    consumer_excerpt: str = Field(min_length=1)
    relation_note: str | None = Field(default=None, min_length=1)

    @property
    def key(self) -> tuple:
        if self.consumer_kind == "restricted_statement":
            return (self.consumer_kind, self.restricted_statement_id)
        if self.consumer_kind == "official_predicate":
            return (self.consumer_kind, self.rule_component_id, self.predicate_id)
        return (
            self.consumer_kind, self.candidate_index, self.layer,
            self.group_index, self.atom_index, self.condition_id,
        )

    @model_validator(mode="after")
    def require_repeat_condition(self) -> "SourceDefinitionAtomConsumer":
        if self.consumer_kind == "restricted_statement":
            if (not (self.restricted_statement_id or "").startswith("restricted:")
                    or not self.restricted_statement_id[len("restricted:"):].strip()
                    or any(value is not None for value in (
                        self.candidate_index, self.layer, self.group_index, self.atom_index,
                        self.condition_id, self.official_code, self.rule_component_id, self.predicate_id,
                    ))):
                raise ValueError("受限来源消费声明必须且只能携带实际受限陈述身份")
        elif self.restricted_statement_id is not None:
            raise ValueError("受限陈述身份不得混入可执行消费者")
        elif self.consumer_kind == "official_predicate":
            if (self.official_code is None or self.rule_component_id is None
                    or self.predicate_id is None
                    or any(value is not None for value in (
                        self.candidate_index, self.layer, self.condition_id,
                        self.group_index, self.atom_index,
                    ))):
                raise ValueError("官方条件消费声明必须且只能携带官方编号、子规则与条件身份")
        elif (
            self.candidate_index is None or self.layer is None
            or self.group_index is None or self.atom_index is None
            or any(value is not None for value in (
                self.official_code, self.rule_component_id, self.predicate_id,
            ))
        ):
            raise ValueError("控制原子消费声明必须且只能携带候选索引与原子位置")
        if (self.layer == "repeat_trigger") != (self.condition_id is not None):
            raise ValueError("复查触发消费原子必须且只能携带所属条件编号")
        if self.condition_id is not None and not self.condition_id.strip():
            raise ValueError("复查条件编号不能为空")
        if not normalize_source_excerpt(self.consumer_excerpt):
            raise ValueError("消费原子来源摘录不得为空白")
        if self.relation_note is not None and not self.relation_note.strip():
            raise ValueError("定义消费说明不得为空白")
        return self


class SourceDefinitionConsumerItem(ContractModel):
    statement_index: int = Field(ge=0)
    consumers: list[SourceDefinitionAtomConsumer] = Field(min_length=1)
    unresolved_aspects: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_unique_consumers(self) -> "SourceDefinitionConsumerItem":
        keys = [consumer.key for consumer in self.consumers]
        if len(keys) != len(set(keys)):
            raise ValueError("同一来源定义的消费原子不得重复")
        if any(not aspect.strip() for aspect in self.unresolved_aspects):
            raise ValueError("定义消费关系的未决之处不得为空白")
        return self


class SourceDefinitionConsumers(ContractModel):
    version: Literal[SOURCE_DEFINITION_CONSUMER_VERSION, "phase5/control-source-definition-consumer/v2"]
    items: list[SourceDefinitionConsumerItem]

    @model_validator(mode="after")
    def require_unique_statements(self) -> "SourceDefinitionConsumers":
        if self.version.endswith("/v2") and any(
            consumer.consumer_kind == "restricted_statement"
            for item in self.items for consumer in item.consumers
        ):
            raise ValueError("旧定义登记合同不能携带新增受限消费者")
        indexes = [item.statement_index for item in self.items]
        if len(indexes) != len(set(indexes)):
            raise ValueError("同一来源陈述不得重复登记消费原子")
        return self


SOURCE_DEFINITION_CONSUMER_PROMPT_VERSION = (
    "phase5/control-source-definition-consumer-prompt/v4"
)


def is_non_action_definition(statement: SourceStatement) -> bool:
    """Permit dependency review; numerical definitions still need proven consumers."""
    functions = set(statement.decision_functions)
    return bool(
        "definition" in functions
        and functions <= {"definition", "time_validity", "calculation_input", "threshold"}
        and getattr(statement, "force", None) == "descriptive"
        and not statement.unresolved
        and getattr(statement, "control_authority", "study_or_unknown") == "study_or_unknown"
        # A contradictory imperative is a reason to withhold this shortcut,
        # not proof that every other descriptive sentence is a definition.
        and not re.search(
            r"必须|不得|禁止|应当|(?:受试者|患者|研究者)[^。；;]{0,32}(?:须|应|需)|"
            r"\b(?:must|shall|required\s+to|prohibited)\b",
            statement.quoted_text, re.IGNORECASE,
        )
    )


def source_definition_statement_indexes(
    interpretation: SourceInterpretation,
) -> list[int]:
    """Definition registration does not depend on eligibility for a shortcut."""

    return [
        index for index, statement in enumerate(interpretation.statements)
        if "calculation_input" in statement.decision_functions
        or "definition" in statement.decision_functions
    ]


def _definition_consumer_atom_excerpts(atom: object) -> list[str]:
    excerpts = [value for value in getattr(atom, "source_excerpts", ()) if value]
    continuation = getattr(atom, "continuing_obligation", None)
    if continuation is not None:
        excerpts.extend(value for value in continuation.source_excerpts if value)
    return excerpts


def definition_consumer_candidate_atoms(candidate: object) -> list[dict[str, object]]:
    """Frozen atom positions with their own excerpts, resolved like the closure.

    The positions are exactly the ones the execution layer resolves: an atom is
    addressed by its layer, group index and atom index, and a repeat-trigger
    atom additionally by its condition id. Each entry exposes the atom's own
    frozen excerpts so a declared consumer excerpt can be anchored to its own
    source instead of to wording similarity.
    """

    semantics = getattr(candidate, "semantics", None)
    if semantics is None:
        raise ValueError("定义消费提示缺少冻结候选语义")
    entries: list[dict[str, object]] = []
    layers = (
        ("applicability", getattr(semantics, "applicability_expression", None)),
        ("trigger", getattr(semantics, "trigger_expression", None)),
        ("obligation", getattr(semantics, "obligation_expression", None)),
        ("exception", getattr(semantics, "exception_expression", None)),
    )
    for layer, expression in layers:
        if expression is None:
            continue
        for group_index, group in enumerate(expression.groups):
            for atom_index, atom in enumerate(group.atoms):
                entries.append({
                    "layer": layer,
                    "group_index": group_index,
                    "atom_index": atom_index,
                    "condition_id": None,
                    "excerpts": _definition_consumer_atom_excerpts(atom),
                })
    for condition in getattr(semantics, "repeat_trigger_conditions", ()):
        for group_index, group in enumerate(condition.expression.groups):
            for atom_index, atom in enumerate(group.atoms):
                entries.append({
                    "layer": "repeat_trigger",
                    "group_index": group_index,
                    "atom_index": atom_index,
                    "condition_id": condition.condition_id,
                    "excerpts": _definition_consumer_atom_excerpts(atom),
                })
    return entries


def build_source_definition_consumers_prompt(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    output: object,
    *,
    official_predicate_identities: Mapping[str, Sequence[tuple[str, str]]] | None = None,
    official_predicate_sources: Mapping[str, Mapping[tuple[str, str], Sequence[str]]] | None = None,
) -> str:
    """Ask only which frozen consumers depend on a frozen definition.

    The prompt exposes exactly the frozen inputs the declaration may reference:
    the calculation definitions of this batch, the hydrated candidate atom
    positions with their own excerpts, and the batch's frozen official targets.
    A frozen official predicate identity is offered only when the caller passes
    one, because the deep batch itself carries no official rule identity; an
    absent identity makes a parent IN/EX code unusable instead of guessed.
    """

    units = {unit.structure_unit_id: unit for unit in batch.owned_units}
    definitions = []
    for index in source_definition_statement_indexes(interpretation):
        statement = interpretation.statements[index]
        unit = units.get(statement.structure_unit_id)
        definitions.append({
            "statement_index": index,
            "structure_unit_id": statement.structure_unit_id,
            "quoted_text": statement.quoted_text,
            "scope_quote": statement.scope_quote,
            "force": statement.force,
            "decision_functions": list(statement.decision_functions),
            "unresolved": list(statement.unresolved),
            "source_unit_excerpt": unit.excerpt if unit is not None else None,
            "heading_path": list(unit.heading_path) if unit is not None else [],
        })
    candidates = [
        {
            "candidate_index": index,
            "control_candidate_id": candidate.control_candidate_id,
            "title": candidate.semantics.title,
            "atoms": definition_consumer_candidate_atoms(candidate),
        }
        for index, candidate in enumerate(output.candidates)
    ]
    restricted = [
        {"restricted_statement_id": statement.restricted_statement_id,
         "source_quote": statement.source_quote,
         "source_structure_unit_id": statement.source_structure_unit_id,
         "source_statement_index": statement.source_statement_index,
         "decision_functions": list(statement.decision_functions)}
        for statement in getattr(output, "restricted_statements", ())
    ]
    official_targets = [
        {
            "official_code": target.official_code,
            "label": target.label,
            "source_excerpts": list(target.source_excerpts),
        }
        for target in batch.known_official_targets
    ]
    frozen_official = {
        code: [
            {
                "rule_component_id": component_id,
                "predicate_id": predicate_id,
                "source_excerpts": list(
                    (official_predicate_sources or {}).get(code, {}).get(
                        (component_id, predicate_id), ()
                    )
                ),
            }
            for component_id, predicate_id in identities
        ]
        for code, identities in (official_predicate_identities or {}).items()
    }
    output_shape = (
        f'{{"version":"{SOURCE_DEFINITION_CONSUMER_VERSION}","items":[]}}'
    )
    official_rule = (
        "官方条件消费必须同时给出冻结官方编号 official_code 与“冻结官方条件身份”中该编号下"
        "逐字列出的 rule_component_id、predicate_id；consumer_excerpt 还必须取自该条件"
        "自己的 source_excerpts；身份或自身原文未列出时不得登记官方条件消费，"
        "不得用父编号、相同措辞、算子或阈值替代身份。"
        if frozen_official else
        "本批未提供冻结官方条件身份，任何官方条件消费都不得登记；"
        "父编号、相同措辞、算子或阈值都不能代替冻结的 rule_component_id 与 predicate_id。"
    )
    return (
        "你是本系统方案 Agent 的来源定义消费登记步骤。只登记下面列出的冻结定义由哪些"
        "已冻结条件实际依赖；包括计算输入以及时期、范围的定义，不把定义变成患者义务。"
        "不生成规则、不修改候选、不判断受试者。"
        "受限来源也可以依赖定义，但只能用冻结受限陈述清单中的 restricted_statement_id，"
        "consumer_kind 写 restricted_statement，consumer_excerpt 逐字取自该陈述自己的 source_quote。"
        "它不是可执行原子，所有候选、条件和原子位置字段填 null；不得用定义自身登记自我依赖。"
        "控制原子消费必须用冻结候选索引 candidate_index 加原子位置 layer、group_index、atom_index"
        "（复查触发原子还须逐字填写该条件的 condition_id），consumer_excerpt 必须逐字取自"
        "该原子自己列出的 excerpts 中任一段连续原文，不得改写或拼接。"
        f"{official_rule}"
        "一个定义可以有多个消费者；无法证明的消费者不要登记，把待核之处写入该陈述的"
        " unresolved_aspects。没有任何可登记消费者的定义可以不出现；"
        "不得登记清单外的定义、候选、原子位置或官方编号。"
        "relation_note 只解释拟定关系，不构成覆盖证据；statement_index 必须是下面列出的定义编号。"
        "不得因词语相同、数值接近或常识相似就登记消费者。只返回 JSON 对象。\n"
        f"提示版本：{SOURCE_DEFINITION_CONSUMER_PROMPT_VERSION}\n"
        f"无可证消费者时的输出形状：{output_shape}。"
        "有消费者时 items 每项写 statement_index、非空 consumers、unresolved_aspects；"
        "官方条件消费填写冻结列表中的 official_code、rule_component_id、predicate_id，"
        "candidate_index、layer、group_index、atom_index、condition_id 填 null；"
        "控制原子消费则填写已给出的 candidate_index、"
        "layer、group_index、atom_index；非 repeat_trigger 的 condition_id 填 null，"
        "official_code、rule_component_id、predicate_id 填 null。三种身份不能混填；"
        "relation_note 可为 null，不确定就不要登记该消费者。\n"
        f"冻结来源定义：{json.dumps(definitions, ensure_ascii=False, sort_keys=True)}\n"
        f"冻结候选身份与原子：{json.dumps(candidates, ensure_ascii=False, sort_keys=True)}\n"
        f"冻结受限陈述：{json.dumps(restricted, ensure_ascii=False, sort_keys=True)}\n"
        f"冻结官方目标：{json.dumps(official_targets, ensure_ascii=False, sort_keys=True)}\n"
        f"冻结官方条件身份：{json.dumps(frozen_official, ensure_ascii=False, sort_keys=True)}"
    )


def source_definition_consumers_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": (
                "protocol_control_source_definition_consumers_"
                + SOURCE_DEFINITION_CONSUMER_VERSION.rsplit("/", 1)[-1]
            ),
            "strict": True,
            "schema": SourceDefinitionConsumers.model_json_schema(),
        },
    }


SOURCE_UNIT_COMPARISON_VERSION = "phase5/control-source-unit-comparison/v3"


class SourceUnitComparison(ContractModel):
    version: Literal[SOURCE_UNIT_COMPARISON_VERSION]
    statement_index: int = Field(ge=0)
    relation: Literal["same_requirement", "different_or_unclear"]
    target_structure_unit_id: str | None = None
    source_action_excerpt: str | None = None
    target_action_excerpt: str | None = None
    target_scope_excerpt: str | None = None
    source_object_excerpt: str | None = None
    target_object_excerpt: str | None = None
    differences: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def empty_differences_for_same_requirement(cls, value: object) -> object:
        if (isinstance(value, dict)
                and value.get("relation") == "same_requirement"
                and value.get("differences") is None):
            return {**value, "differences": []}
        return value

    @model_validator(mode="after")
    def require_difference_when_unclear(self) -> "SourceUnitComparison":
        if self.relation == "different_or_unclear" and not self.differences:
            raise ValueError("未能确认同一要求时必须说明差异或未明之处")
        return self


def build_source_unit_comparison_prompt(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    statement_index: int,
) -> str:
    statement = interpretation.statements[statement_index]
    source_unit = next(
        unit for unit in batch.owned_units
        if unit.structure_unit_id == statement.structure_unit_id
    )
    contexts = [{"structure_unit_id": unit.structure_unit_id,
                 "source_ref": unit.source_ref, "excerpt": unit.excerpt}
                for unit in batch.context_units]
    return (
        "仅核一条方案原文与另一章节的只读原文是否完整表达同一要求；不生成规则、不判断受试者。"
        "先比较动作、对象、数量/单位、否定、条件、例外和适用时期。"
        "表格行标题或章节名只是定位线索；若正文明确写出具体对象，应以正文为准，"
        "不得把行标题当作药物身份或凭行标题补时间。"
        "另一章节若只说相同频次、对象不同、条件更窄或含义不明，返回 different_or_unclear。"
        "只有两端同一对象逐字相同、核心动作逐字相同，另一单元同句明确写出适用时期，"
        "且没有未解释的条件或例外差异，"
        "才返回 same_requirement。此结果仍只是待发布时复核的来源关系，不能给摘要补时期。"
        "same_requirement 时填写只读单元 ID、两端各自连续的对象原文、两端逐字相同的核心动作原文"
        "和另一单元同句的最短连续时期原文。对象必须在各自动作的同句前方，不能只比数值或频次；"
        "同一要求且无差异时 differences 必须填 []，不能填 null；"
        "不同或不明时其余字段填 null，在 differences 逐项写明差异。"
        "不要引用未给出的章节，不能把已知访视流程当作另一原文单元。"
        "仅返回 JSON，字段必须是 version、statement_index、relation、target_structure_unit_id、"
        "source_action_excerpt、target_action_excerpt、source_object_excerpt、target_object_excerpt、"
        "target_scope_excerpt、differences；"
        "无对应时后四个可空字段填 null。\n"
        f"版本：{SOURCE_UNIT_COMPARISON_VERSION}\n"
        f"本条：{json.dumps({'statement_index': statement_index, 'quoted_text': statement.quoted_text, 'scope_quote': statement.scope_quote, 'time_words': statement.time_words, 'exception_words': statement.exception_words, 'force': statement.force, 'source_unit_excerpt': source_unit.excerpt, 'heading_path': source_unit.heading_path, 'row_headers': source_unit.table_context.row_headers if source_unit.table_context else []}, ensure_ascii=False)}\n"
        f"另一章节：{json.dumps(contexts, ensure_ascii=False)}"
    )


def source_unit_comparison_response_format() -> dict[str, object]:
    return {"type": "json_schema", "json_schema": {
        "name": "protocol_control_source_unit_comparison_v3", "strict": True,
        "schema": SourceUnitComparison.model_json_schema(),
    }}


def source_unit_comparison_as_review(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    coverage: SourceStatementCoverage,
    comparison: SourceUnitComparison,
) -> SourceTargetReview | None:
    if comparison.statement_index != coverage.statement_index:
        raise ValueError("跨章节核对的来源陈述序位不一致")
    if comparison.relation != "same_requirement":
        return None
    review = SourceTargetReview(version=SOURCE_TARGET_REVIEW_VERSION, items=[
        SourceTargetReviewItem(
            statement_index=comparison.statement_index,
            decision="potential_same_requirement",
            target_id=comparison.target_structure_unit_id,
            source_action_excerpt=comparison.source_action_excerpt or "",
            target_action_excerpt=comparison.target_action_excerpt,
            target_scope_excerpt=comparison.target_scope_excerpt,
            source_object_excerpt=comparison.source_object_excerpt,
            target_object_excerpt=comparison.target_object_excerpt,
        )
    ])
    validate_source_target_review(batch, interpretation, [coverage], review)
    return review


def target_review_indexes(
    interpretation: SourceInterpretation,
    coverage: list[SourceStatementCoverage],
    batch: ProtocolControlDispositionBatch | None = None,
) -> list[int]:
    for entry in coverage:
        if (entry.statement_index >= len(interpretation.statements)
                or entry.structure_unit_id != interpretation.statements[entry.statement_index].structure_unit_id):
            raise SourceTargetReviewValidationError(
                "来源覆盖账与陈述清单不一致",
                code="SOURCE_COVERAGE_IDENTITY_INVALID",
                statement_index=None,
                json_path="/source_statement_coverage",
            )
    units = {unit.structure_unit_id: unit for unit in batch.owned_units} if batch else {}
    return [
        entry.statement_index
        for entry in coverage
        if (interpretation.statements[entry.statement_index].control_authority
            == "cited_external_rationale"
            or (entry.status != "expressed"
                and entry.disposition in _ENROLLMENT_DISPOSITIONS
                and not (
                    entry.schedule_columns
                    and all(
                        link.procedure_target_id is not None
                        for link in entry.schedule_columns
                        if link.boundary_side == "at_or_before_baseline"
                    )
                )
                and not _is_schedule_randomization_anchor(
                    units.get(entry.structure_unit_id),
                    interpretation.statements[entry.statement_index],
                )))
    ]


def _is_schedule_randomization_anchor(
    unit: object, statement: SourceStatement, *, require_statement_match: bool = True,
) -> bool:
    if unit is None or getattr(unit, "unit_kind", None) != "table_row":
        return False
    table = getattr(unit, "table_context", None)
    if table is None or not any("随机" in header for header in table.row_headers):
        return False
    if not any("日程" in heading or "访视" in heading
               for heading in getattr(unit, "heading_path", ())):
        return False
    marker = re.compile(r"(?:随机(?:分组|化)?|randomi[sz]ation)[|｜][X×√✓]", re.IGNORECASE)
    return bool(
        marker.fullmatch(normalize_source_excerpt(getattr(unit, "excerpt", "")))
        and (not require_statement_match or marker.fullmatch(normalize_source_excerpt(statement.quoted_text)))
        and (not require_statement_match or (not statement.time_words and not statement.exception_words))
    )


def _native_table_source_packet(unit) -> dict[str, object]:
    if unit.table_context is None:
        return {}
    return {"native_table_source": {
        "source_ref": unit.source_ref,
        "source_span_ids": list(unit.source_span_ids),
        "member_source_refs": list(unit.member_source_refs),
        "member_source_span_ids": unit.member_source_span_ids,
        "member_texts": unit.member_texts,
        "table_context": unit.table_context.model_dump(mode="json"),
    }}


def _target_review_source_packet(batch, comparison_target_id):
    excerpts, by_source, positions = [], {}, {}
    targets = {"official": [], "procedure": []}
    for category, entries in (("official", batch.known_official_targets),
                              ("procedure", batch.known_procedure_targets)):
        for target in entries:
            target_id = target.official_code if category == "official" else target.catalog_item_id
            if comparison_target_id is not None and target_id != comparison_target_id:
                continue
            refs = []
            for span_id, excerpt in zip(target.source_span_ids,
                                       target.source_excerpts or [None] * len(target.source_span_ids), strict=True):
                key = (span_id, excerpt)
                if span_id not in positions:
                    positions[span_id] = f"p{len(positions)}"
                if key not in by_source:
                    by_source[key] = f"e{len(excerpts)}"
                    excerpts.append({"excerpt_id": by_source[key], "source_position": positions[span_id],
                                     "excerpt": excerpt})
                refs.append(by_source[key])
            item = {"target_id": target_id, "label": target.label, "source_refs": refs}
            if category == "procedure":
                item["visit_instance"] = target.visit_instance
                shared = [positions[span_id] for span_id in target.source_span_ids
                    if any(other.catalog_item_id != target.catalog_item_id
                           and other.visit_instance != target.visit_instance
                           and span_id in other.source_span_ids for other in entries)]
                if shared:
                    item["shared_visit_source_positions"] = shared
            targets[category].append(item)
    return targets, excerpts


def build_source_target_review_prompt(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    coverage: list[SourceStatementCoverage],
    *,
    comparison_target_id: str | None = None,
) -> str:
    indexes = target_review_indexes(interpretation, coverage, batch)
    coverage_by_index = {entry.statement_index: entry for entry in coverage}
    source = [
        {
            "statement_index": index,
            "structure_unit_id": interpretation.statements[index].structure_unit_id,
            "current_disposition": coverage_by_index[index].disposition,
            "linked_official_code": coverage_by_index[index].linked_official_code,
            "linked_procedure_target_ids": coverage_by_index[index].linked_procedure_target_ids,
            "quoted_text": interpretation.statements[index].quoted_text,
            "force": interpretation.statements[index].force,
            "scope_quote": interpretation.statements[index].scope_quote,
            **({"scope_context_source": _cell_scope_label_packet(batch, next(
                unit for unit in batch.owned_units
                if unit.structure_unit_id == interpretation.statements[index].structure_unit_id
            ))} if interpretation.statements[index].scope_context_unit_id is not None else {}),
            "affected_stage": interpretation.statements[index].affected_stage,
            "time_words": interpretation.statements[index].time_words,
            "decision_functions": interpretation.statements[index].decision_functions,
            "background_context_allowed": (
                interpretation.statements[index].decision_functions == ["background"]
                and not interpretation.statements[index].unresolved
            ),
            "definition_dependency_allowed": is_non_action_definition(interpretation.statements[index]),
            "definition_dependency_permission_version": "non-action-numeric-definition/v1",
            "exception_words": interpretation.statements[index].exception_words,
            "unresolved": interpretation.statements[index].unresolved,
            "eligibility_sequence": interpretation.statements[index].eligibility_sequence,
            "eligibility_sequence_quote": interpretation.statements[index].eligibility_sequence_quote,
            "control_authority": interpretation.statements[index].control_authority,
            "attribution_quote": interpretation.statements[index].attribution_quote,
        }
        for index in indexes
    ]
    owned_by_id = {unit.structure_unit_id: unit for unit in batch.owned_units}
    for packet in source:
        packet.update(_native_table_source_packet(owned_by_id[packet["structure_unit_id"]]))
    procedures = {target.catalog_item_id: target for target in batch.known_procedure_targets}
    for packet in source:
        statement = interpretation.statements[packet["statement_index"]]
        labels = _statement_schedule_label_sources(batch, statement)
        mismatches = [target_id for target_id in packet["linked_procedure_target_ids"]
                      if target_id in procedures and labels
                      and not _target_contains_row_label(procedures[target_id], labels)]
        if mismatches:
            packet["native_row_link_diagnostic"] = {
                "version": SOURCE_TARGET_REVIEW_VALIDATION_VERSION,
                "rejected_target_ids": mismatches,
                "label_sources": [{"source_span_id": span, "excerpt": text}
                                  for span, text in labels],
                "reason": "已有链接没有包含本行项目的原始来源；共用脚注不能证明是同一项目。"
                          "不得宣称这些目标已覆盖。本条动作和时期明确但没有对应目标时，"
                          "选 additional_requirement；只有本条原文自身无法核清时保留 unresolved。"
                          "同一链接覆盖的约束不要求坚持已被此来源核查拒绝的链接。",
            }
    targets, target_excerpts = _target_review_source_packet(batch, comparison_target_id)
    read_only_sources = [
        {
            "structure_unit_id": unit.structure_unit_id,
            "source_ref": unit.source_ref,
            "heading_path": unit.heading_path,
            "excerpt": unit.excerpt,
            **_native_table_source_packet(unit),
        }
        for unit in batch.context_units
    ]
    return (
        "你是本系统方案 Agent 的逐项来源核对步骤。仅核下面列出的陈述，不生成新规则或判断受试者。"
        "每条只可选：已有官方入排完整覆盖、已有访视流程完整覆盖、尚有增量要求、"
        "只读单元可能复述同一要求（仅待跨章核验）、"
        "明确属于入排判定后执行而非本节点控制、无法核清。"
        "只有同一原文单元明确写出先确定入排资格、随后才执行该动作，才能选 not_current_control；"
        "此时 non_control_basis_excerpt 必须逐字引用该动作之前的先后依据。"
        "现有候选若仍把该动作写成本节点控制，不能选此项，须先修订候选。"
        "仅有治疗期标题、相邻频次或推测将来才发生，不足以排除当前控制，应保留待核。"
        "若上一步已用同句逐字归因将本条标为 cited_external_rationale，且它只是外部资料对"
        "设计目的的转述、本批没有把该动作做成候选，选 cited_external_rationale；"
        "attribution_excerpt 必须与上一步归因摘录逐字一致。不能仅因为标题叫科学原理、"
        "出现指南二字或未找到已有目标就选此项。若同句明确写本研究采纳为要求，仍须按要求核对。"
        "force 只记原文语气，不决定是否要核对；描述性语句可能定义入排所用的取值、计算、时窗或例外。"
        "背景说明只有在逐字摘录确实不改变本节点任何选择、计算或判断，且没有被装成候选动作时，"
        "才选 background_context，并用 non_control_basis_excerpt 引用本条内证明其为背景的连续原文。"
        "本条 decision_functions 不是结论；只有标为纯 background 且核对原文后确为背景，"
        "才可选 background_context。"
        "background_context_allowed 为 false 时不能在此步骤改写用途或仍选背景；"
        "用途复核若维持原分类，应核对其实际目标或保留具体用途/依赖未决，"
        "不能为了让流程通过而添加无源要求。"
        "若只因未找到条款或不确定用途，选 unresolved，不得当作背景。"
        "流程节点原始表头只供核查时期定义与上下文；它不是操作已被完整覆盖或患者已完成操作的证明。"
        "native_table_source 保留冻结原文的单元格路径、逐格文字和来源；"
        "同一表中标记单元格与表头的列位置可用于核查本行动作适用的访视，"
        "不得仅因标记文字没有重复写出表头就说原文未给时期。"
        "位置关系本身不证明已有目标覆盖，不补造缺失表头、合并关系或临床例外。"
        "没有表头原文时不能以派生访视名称补造来源；表头未写出的时长、锚点、例外继续保留具体未决。"
        "此步骤仍不得把流程节点编号填作官方或必做项目 target_id，也不得把时期定义改成患者义务。"
        "仅当 definition_dependency_allowed 为 true，且本条是有源、含义明确的定义而非动作，"
        "可选 definition_dependency；它只把完整定义交给后续影响范围核对，不表示定义已经执行或覆盖。"
        "definition_dependency_allowed 仅说明宿主允许核对此路径，不证明分类正确；"
        "先从本条原文独立核查是否要求某人执行、达到或避免某事，再核用途标签。"
        "带动作的定义须保留动作，不得借定义标签省略。"
        "此项 source_action_excerpt 引用本条定义原文，其他摘录及 target_id 均填 null，"
        "unresolved_aspects 填 []。实际依赖哪些条件由后续冻结消费者登记及全范围核对决定；"
        "原文存在歧义或含未完成动作时仍选 unresolved，不得用此项绕过。"
        "同段已有候选并不等于所有动作已覆盖；目录名称相似也不等于时间、条件、例外都已覆盖。"
        "unresolved 是当前冻结来源解释尚未核清的具体维度，不是受试者缺件。"
        "此字段非空时，不得选择 covered_by_official 或 covered_by_procedure；"
        "目标文字相同也不能消除已保存的来源疑问。本步骤无权改写或清空来源解释，"
        "须保留相关疑问及有源对照线索，不声称完整覆盖。"
        "未核清的原文也不得作为 not_current_control、potential_same_requirement 或 cited_external_rationale 关闭；"
        "只能在现有未完整覆盖路径中保留具体 unresolved_aspects，不将原文疑问改写成受试者缺件。"
        "若 scope_context_source 提供表内项目标签，宿主只核了位置；你须从原文独立核它是否"
        "直接限定本条对象及适用分期，再核实际目标是否完整对应。标签是另一动作、存在冲突或"
        "关系不明时必须保留 unresolved，不能仅因结构相邻就报完整覆盖。"
        "只引用目录名称或名称的一部分，只能证明项目关联，不能证明具体操作已覆盖。"
        "除非宿主的 label_action_supported_target_ids 已提供该动作的来源依据，"
        "完整覆盖须引用目标来源中真正承载操作的原文，而不是只截取项目名称。"
        "官方条件的名称可能就是整条标准：若条件带明确时间，可以引用同一冻结来源中完整的"
        "条件原文，或把它开头的时间单独放入 target_time_excerpt，其余连续原文放入"
        " target_action_excerpt；不能省略脚注标记、尾部条件，或从另一摘录借时间。"
        "完整引用只是出处证明，仍须独立核对条件、对象、否定和例外是否相同，不表示患者符合。"
        "目录只有项目名称而无动作依据时，原文动作明确则选 additional_requirement；"
        "原文自身无法核清才选 unresolved；不得把系统无法证明对应关系说成受试者缺记录。"
        "目标原文按 source_refs 列出的摘录编号在目标来源摘录表中查找；相同位置相同原文只提供一次，"
        "不代表合并不同访视。同一位置不同原文仍分别保留，缺原文的 null 不能作引用。"
        "source_refs 列出摘录编号；source_position 是宿主按冻结来源位置分配的短标识，不是页码。"
        "shared_visit_source_positions 只表示多访视共用位置，不是时间已对应的证明。"
        "完整覆盖必须从本陈述截出连续的 source_action_excerpt，并从目标引用的实际原文截出连续的"
        " target_action_excerpt。"
        "source_action_excerpt 必须是本条 quoted_text 内的连续原文，不得为了补齐医学条件而拼接"
        "scope_quote 的时间前缀或 quoted_text 外的例外尾句；时间和例外仍须另行核对，不能省略。"
        "两端动作摘录各自必须有原文依据，但文字不必完全相同；全称、缩写或表述差异"
        "只有在给出的方案原文能证明条件、对象、否定、阈值及例外相同后才可报完整覆盖。"
        "如本陈述有明确时间，须再分别给出来源时间与目标摘录或访视中的同一最短连续时间短语，"
        "两个字段归一化后须相同；仅同一锚点、前后方向及边界完全一致时，整数天/周可按七天一周核对等价，"
        "月份、访视周编号及其他表达不能推算等价。来源时间可取本条已核实的"
        "scope_quote 或所属标题，不得借相邻陈述的范围；不要把整行访视名称当成目标时间片段。"
        "一条陈述若同时列出访视范围和治疗持续期等多项时间要求，目标原文或访视定位必须逐项支持全部时间措辞；"
        "只对齐其中一项不得宣称完整覆盖，应选 additional_requirement 或 unresolved 并列出未覆盖之处。"
        "仅有每日或每周给药次数相同，不证明审核时期或持续期相同；须保留时间范围待核。"
        "若来源只写相对时点而目标只写另一访视名称、两边没有共同时间原文，"
        "即使你认为语义可能相当，也只能选 additional_requirement 或 unresolved，不得报完整覆盖。"
        "若本条来源的动作、对象和相对时点本身均有逐字依据，只是已有目标缺少该时点，"
        "应选 additional_requirement，引用已有目标作为对照并写明时间差额；"
        "只有来源动作或适用时期自身无法从本条及其明确范围核清时才选 unresolved。"
        "若多个访视目录项共用同一段说明，不能仅因该段包含本条时期就说所选访视已覆盖；"
        "还须核对该目录项独有的访视名称或独有来源。其余访视等相对称谓若无法定位到"
        "所选访视，应保留待核，不得借共用说明报完整覆盖。"
        "不得为了选增量要求，借同单元另一动作的时期、频次或治疗持续期。"
        "未完整覆盖时可以附上已有目标的逐字动作和时间作为核对线索，同时在 unresolved_aspects"
        "写明未对齐之处；此类目标引用不代表已覆盖。"
        "引用已有目标作对照时，target_id 必须是该冻结目标的编号，target_action_excerpt "
        "必须逐字摘自该目标 source_refs 指向的原文，两者须同时填写；不引用目标时两者都填 null，"
        "target_time_excerpt 也填 null。不能把本条原文复制到目标摘录，"
        "也不能因选择 additional_requirement 就省略所引用目标的编号。"
        "不要把未来要求提前判作当前已完成，不推断原文未写的例外。"
        "只读来源单元仅供识别跨章节复述、补充或矛盾的待核线索；它们不是冻结已有目标。"
        "不得因两段文字相似就报完整覆盖，也不得把只读来源的时期、例外或完成强度写成本陈述自己的原文。"
        "如后文可能补充本句但当前无法证明完整关系，列出具体差异并选增量或未核，不能直接舍弃本句。"
        "potential_same_requirement 只可引用给出的另一只读原文单元；两端对象与核心动作均须逐字相同，"
        "此项 target_id 必须填写该只读单元的 structure_unit_id，不能填写 source_ref、"
        "原文位置、摘录编号或已有官方/流程目标编号；source_ref 仅供定位原文。"
        "对象可在同句动作之前、之后或包含在动作摘录内，不得从另一句借用。"
        "并给出该单元同句的明确适用时期 target_scope_excerpt。此判断仅登记待核关系，"
        "不等于已有控制覆盖；后文必须独立解构并在最终发布前再次核验。"
        "选择此项时 source_time_excerpt、target_time_excerpt、non_control_basis_excerpt 均填 null，"
        "unresolved_aspects 填 []；时期只记在 target_scope_excerpt。若仍有真实差异，应选 unresolved，"
        "不能同时登记同一要求。"
        "source_object_excerpt、target_object_excerpt、target_scope_excerpt 仅限"
        " potential_same_requirement；其他所有 decision 的这三个字段必须填 null，"
        "不能把对象从 source_action_excerpt 中拆走，也不能以额外字段表达普通目标覆盖。"
        "已有链接仅为核对线索，不能代替原文；若声称链接的条款或流程完整覆盖，"
        "须引用草稿实际链接的同一目标，否则保持待核。"
        "不得省略任何陈述，不能引用未列出的目标。只返回 JSON 对象。\n"
        f'输出结构：{{"version":"{SOURCE_TARGET_REVIEW_VERSION}","items":'
        '[{"statement_index":0,"decision":"covered_by_official|covered_by_procedure|'
        'additional_requirement|not_current_control|unresolved|potential_same_requirement|cited_external_rationale|background_context|definition_dependency","target_id":null,"source_action_excerpt":"逐字动作",'
        '"target_action_excerpt":null,"source_object_excerpt":null,"target_object_excerpt":null,'
        '"source_time_excerpt":null,"target_time_excerpt":null,"target_scope_excerpt":null,'
        '"unresolved_aspects":[],"non_control_basis_excerpt":null,"attribution_excerpt":null}]}。枚举值只选一个，未知目标填 null；'
        '非跨章节关系的对象与另一来源时期字段一律填 null。\n'
        f"本次必须且只能返回这些 statement_index：{json.dumps(indexes)}。"
        "不得返回同单元其他陈述或上一轮整批清单；items 数量必须与本次序号数量相同。\n"
        f"待核陈述：{json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}\n"
        f"冻结已有目标：{json.dumps(targets, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}\n"
        f"目标来源摘录表：{json.dumps(target_excerpts, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}\n"
        "流程节点原始表头（仅上下文，不是已有操作目标）：" + json.dumps([
            {"workflow_stage_id": stage.workflow_stage_id, "visit_instance": stage.visit_instance,
             "source_verified": bool(stage.source_span_ids),
             "source_span_ids": stage.source_span_ids, "source_excerpts": stage.source_excerpts}
            for stage in batch.known_workflow_stage_targets
        ], ensure_ascii=False, sort_keys=True, separators=(',', ':')) + "\n"
        "名称引用的动作依据：" + json.dumps([
            {"statement_index": index, "label_action_supported_target_ids": [
                target.official_code if hasattr(target, "official_code") else target.catalog_item_id
                for target in [*batch.known_official_targets, *batch.known_procedure_targets]
                if target_action_established(batch, interpretation.statements[index], target)
                and (comparison_target_id is None or comparison_target_id == (
                    target.official_code if hasattr(target, "official_code") else target.catalog_item_id))
            ]} for index in indexes
        ], ensure_ascii=False, sort_keys=True) + "\n"
        f"只读来源线索：{json.dumps(read_only_sources, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}"
    )


def source_target_review_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_source_target_review_" + SOURCE_TARGET_REVIEW_VERSION.rsplit("/", 1)[-1],
            "strict": True,
            "schema": SourceTargetReview.model_json_schema(),
        },
    }


class SourceTargetReviewValidationError(ValueError):
    def __init__(
        self, message: str, *, code: str, statement_index: int | None,
        json_path: str, source_refs: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.statement_index = statement_index
        self.json_path = json_path
        self.source_refs = source_refs
        self.retry_class = "single_statement" if statement_index is not None else "whole_review"
        self.affected_dependents = (statement_index,) if statement_index is not None else ()


class SourceTemporalScopeUnresolved(ValueError):
    """Carry the exact duration/cross-node failure range as structured data.

    The failure semantics do not change: the batch stays unpublished and every
    listed statement keeps its unresolved source scope. This typed object only
    replaces the earlier free-text carrier so the range survives without
    parsing a Chinese message. It is not evidence of missing clinical data and
    it does not authorize any consumer for the range.
    """

    code = "TEMPORAL_SCOPE_UNRESOLVED"

    def __init__(
        self, *, statement_ids: Sequence[int], json_path: str,
        source_refs: Sequence[str] = (),
        retry_class: str = "temporal_scope_review",
        affected_dependents: Sequence[int] | None = None,
    ) -> None:
        ids = tuple(statement_ids)
        super().__init__(
            "来源陈述含持续期或跨节点时间要求，不能按单次访视补入："
            + ",".join(map(str, ids))
        )
        self.statement_ids = ids
        self.statement_index = ids[0] if len(ids) == 1 else None
        self.json_path = json_path
        self.source_refs = tuple(source_refs)
        self.retry_class = retry_class
        self.affected_dependents = (
            tuple(affected_dependents) if affected_dependents is not None else ids
        )


def validate_source_target_review(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    coverage: list[SourceStatementCoverage],
    review: SourceTargetReview,
) -> None:
    expected = target_review_indexes(interpretation, coverage, batch)
    if sorted(item.statement_index for item in review.items) != sorted(expected):
        raise SourceTargetReviewValidationError(
            "逐项来源核对必须且只能覆盖本次待核陈述",
            code="REVIEW_SCOPE_INVALID", statement_index=None, json_path="/items",
        )
    coverage_by_index = {entry.statement_index: entry for entry in coverage}
    official = {item.official_code: item for item in batch.known_official_targets}
    procedures = {item.catalog_item_id: item for item in batch.known_procedure_targets}
    owned = {unit.structure_unit_id: unit for unit in batch.owned_units}
    positions = {item.statement_index: index for index, item in enumerate(review.items)}

    def reject(item: SourceTargetReviewItem, code: str, field: str, message: str) -> None:
        statement = interpretation.statements[item.statement_index]
        unit = owned.get(statement.structure_unit_id)
        raise SourceTargetReviewValidationError(
            message, code=code, statement_index=item.statement_index,
            json_path=f"/items/{positions[item.statement_index]}/{field}",
            source_refs=tuple(unit.source_span_ids) if unit is not None else (),
        )

    for item in review.items:
        statement = interpretation.statements[item.statement_index]
        action = normalize_source_excerpt(item.source_action_excerpt)
        quoted = normalize_source_excerpt(statement.quoted_text)
        source_unit_text = normalize_source_excerpt(
            owned[statement.structure_unit_id].excerpt
        )
        leading_subject = (
            action[:-len(quoted)] if quoted and action.endswith(quoted) else ""
        )
        same_sentence_subject_extension = bool(
            leading_subject and len(leading_subject) <= 32
            and action in source_unit_text
            and action == normalize_source_excerpt(item.target_action_excerpt or "")
            and not re.search(r"[。；;，,:：]|筛选|基线|导入|随机|给药|前|后|内|天|周|月|年|不得|不应|仅|若|如|如果|除外", leading_subject)
        )
        if not action or (action not in quoted and not same_sentence_subject_extension):
            reject(item, "SOURCE_ACTION_MISMATCH", "source_action_excerpt", f"第{item.statement_index}条动作摘录不属于冻结陈述")
        if statement.decision_functions == ["unclassified"] and item.decision != "unresolved":
            reject(item, "SOURCE_FUNCTION_UNRESOLVED", "decision",
                   "原文对本节点审核的用途仍未核清，不能仅凭文字对应宣称已覆盖或无需审核")
        covered = item.decision in {"covered_by_official", "covered_by_procedure"}
        if covered and statement.unresolved:
            reject(item, "SOURCE_UNRESOLVED_STILL_COVERED", "decision",
                   "来源陈述仍有未核清内容，不能宣称已有目标完整覆盖")
        if statement.unresolved and item.decision in {
            "not_current_control", "potential_same_requirement", "cited_external_rationale",
        }:
            reject(item, "SOURCE_UNRESOLVED_STILL_EXCLUDED", "decision",
                   "来源陈述仍有未核清内容，不能排除当前审核或关闭来源疑问")
        if (not covered and item.decision not in {"not_current_control", "potential_same_requirement",
                                                "cited_external_rationale", "background_context", "definition_dependency"}
                and not item.unresolved_aspects):
            reject(item, "UNRESOLVED_ASPECTS_MISSING", "unresolved_aspects", "未完整覆盖的陈述必须说明待核实之处")
        if item.decision == "cited_external_rationale":
            attribution = normalize_source_excerpt(item.attribution_excerpt or "")
            if (statement.control_authority != "cited_external_rationale"
                    or not attribution
                    or attribution != normalize_source_excerpt(statement.attribution_quote or "")
                    or not _attribution_in_same_sentence(
                        owned[statement.structure_unit_id].excerpt,
                        statement.quoted_text, item.attribution_excerpt or "",
                    )):
                reject(item, "SOURCE_ATTRIBUTION_UNCONFIRMED", "attribution_excerpt",
                       "外部资料归因必须与已核陈述和同句原文一致")
            if (entry := coverage_by_index[item.statement_index]).action_candidate_indexes:
                reject(item, "EXTERNAL_RATIONALE_STILL_CONTROL", "decision",
                       "同一外部资料说明仍被写成候选控制，不能同时声明无需新增要求")
            if any((item.target_id, item.target_action_excerpt, item.source_time_excerpt,
                    item.target_time_excerpt, item.target_scope_excerpt,
                    item.source_object_excerpt, item.target_object_excerpt,
                    item.non_control_basis_excerpt)) or item.unresolved_aspects:
                reject(item, "SOURCE_ATTRIBUTION_SCOPE_INVALID", "decision",
                       "外部资料说明不能携带已有目标、跨章关系、额外时间或未决项目")
            continue
        if item.decision == "background_context":
            entry = coverage_by_index[item.statement_index]
            basis = normalize_source_excerpt(item.non_control_basis_excerpt or "")
            if (statement.decision_functions != ["background"]
                    or statement.force not in {"descriptive", "unclear"}
                    or statement.unresolved
                    or not basis or basis not in quoted
                    or entry.action_candidate_indexes or entry.candidate_indexes
                    or entry.exact_official_excerpt_matches
                    or entry.exact_procedure_excerpt_matches
                    or item.target_id is not None or item.target_action_excerpt is not None
                    or item.source_time_excerpt is not None or item.target_time_excerpt is not None
                    or item.target_scope_excerpt is not None
                    or item.source_object_excerpt is not None
                    or item.target_object_excerpt is not None
                    or item.attribution_excerpt is not None or item.unresolved_aspects):
                reject(item, "BACKGROUND_CONTEXT_UNPROVEN", "decision",
                       "纯背景处置须由本条原文及功能分类支持，且不能同时形成候选控制")
            continue
        if item.decision == "definition_dependency":
            entry = coverage_by_index[item.statement_index]
            if (not is_non_action_definition(statement)
                    or entry.candidate_indexes or entry.action_candidate_indexes
                    or any((item.target_id, item.target_action_excerpt, item.source_time_excerpt,
                            item.target_time_excerpt, item.target_scope_excerpt,
                            item.source_object_excerpt, item.target_object_excerpt,
                            item.non_control_basis_excerpt, item.attribution_excerpt))
                    or item.unresolved_aspects):
                reject(item, "DEFINITION_DEPENDENCY_UNPROVEN", "decision",
                       "定义须有明确来源且不含候选动作；影响范围尚待独立核对，不能借此宣称覆盖")
            continue
        if item.attribution_excerpt is not None:
            reject(item, "SOURCE_ATTRIBUTION_UNEXPECTED", "attribution_excerpt",
                   "只有外部资料说明可填写逐字归因")
        if (statement.control_authority == "cited_external_rationale"
                and item.decision != "unresolved"):
            reject(item, "SOURCE_ATTRIBUTION_DECISION_INVALID", "decision",
                   "已核外部资料说明不得直接改写成方案要求或已有目标")
        if item.decision == "potential_same_requirement":
            context = next((unit for unit in batch.context_units
                            if unit.structure_unit_id == item.target_id), None)
            if context is None and any(
                unit.source_ref == item.target_id for unit in batch.context_units
            ):
                reject(item, "CONTEXT_TARGET_ID_INVALID", "target_id",
                       "target_id 填写了 source_ref 原文位置；须填写只读单元的 structure_unit_id，不能自动转换来源编号")
            source_unit = owned[statement.structure_unit_id]
            source_context = normalize_source_excerpt(source_unit.excerpt)
            target_action = normalize_source_excerpt(item.target_action_excerpt or "")
            source_text = normalize_source_excerpt(item.source_action_excerpt)
            scope = normalize_source_excerpt(item.target_scope_excerpt or "")
            source_object = normalize_source_excerpt(item.source_object_excerpt or "")
            target_object = normalize_source_excerpt(item.target_object_excerpt or "")
            context_text = normalize_source_excerpt(context.excerpt) if context else ""
            source_action_at = source_context.find(source_text) if source_text else -1
            action_at = context_text.find(target_action) if target_action else -1
            # A period may be embedded in the exact action quote, not only
            # precede it. Never borrow a period following another action.
            scope_at = (context_text.rfind(scope, 0, action_at + len(target_action))
                        if scope and action_at >= 0 else -1)
            if (context is None or len(source_text) < 8
                    or source_text not in normalize_source_excerpt(statement.quoted_text)
                    or source_text != target_action
                    or source_object != target_object or len(source_object) < 3
                    or not _object_in_action_clause(
                        source_context, source_text, source_action_at, source_object)
                    or not _object_in_action_clause(
                        context_text, target_action, action_at, target_object)
                    or source_action_at < 0 or action_at < 0 or scope_at < 0
                    or any(mark in context_text[scope_at:action_at] for mark in "。！？!?；;")):
                reject(item, "CONTEXT_RELATION_UNGROUNDED", "target_id",
                       "跨章对应必须有两端同句的相同对象、逐字动作及后文明确时期")
            if (item.unresolved_aspects or item.non_control_basis_excerpt is not None
                    or item.source_time_excerpt is not None
                    or item.target_time_excerpt is not None):
                reject(item, "CONTEXT_RELATION_UNRESOLVED", "decision",
                       "仍有差异或沿用已有目标时间的陈述不能登记为同一要求")
            dimensions = [*statement.time_words]
            if statement.exception_words:
                dimensions.append(statement.exception_words)
            if any(normalize_source_excerpt(word) not in context_text for word in dimensions):
                reject(item, "CONTEXT_RELATION_DIMENSION_MISSING", "target_action_excerpt",
                       "另一原文单元未保留本条的时间或例外要求")
            continue
        if (item.target_scope_excerpt is not None or item.source_object_excerpt is not None
                or item.target_object_excerpt is not None):
            reject(item, "CONTEXT_SCOPE_UNEXPECTED", "target_scope_excerpt",
                   "只有跨章节待核关系可填写对象与另一单元的适用时期")
        if bool(item.target_id) != bool(item.target_action_excerpt):
            reject(item, "TARGET_ACTION_INCOMPLETE", "target_id", "目标身份与目标动作摘录必须同时提供")
        if not item.target_id:
            if covered or item.target_time_excerpt:
                reject(item, "FROZEN_TARGET_MISSING", "target_id", "目标时间或完整覆盖必须有冻结目标")
            target = None
        elif item.decision == "covered_by_official":
            target = official.get(item.target_id)
        elif item.decision == "covered_by_procedure":
            target = procedures.get(item.target_id)
        else:
            matches = [entry for entry in (official.get(item.target_id), procedures.get(item.target_id)) if entry]
            target = matches[0] if len(matches) == 1 else None
        if item.target_id and target is None:
            reject(item, "FROZEN_TARGET_INVALID", "target_id", f"第{item.statement_index}条引用了非冻结或不唯一的目标")
        entry = coverage_by_index[item.statement_index]
        if item.decision == "not_current_control":
            unit = owned[statement.structure_unit_id]
            source = normalize_source_excerpt(unit.excerpt)
            basis = normalize_source_excerpt(item.non_control_basis_excerpt or "")
            action_start = source.find(normalize_source_excerpt(statement.quoted_text))
            if (not basis or action_start < 0 or basis not in source[:action_start]
                    or item.target_id or item.target_time_excerpt):
                reject(item, "POST_ELIGIBILITY_BASIS_INVALID", "non_control_basis_excerpt",
                       "入排判定后的动作须有同一原文单元内位于动作之前的逐字先后依据")
            if (statement.eligibility_sequence != "after_eligibility_decision"
                    or basis != normalize_source_excerpt(statement.eligibility_sequence_quote or "")):
                reject(item, "POST_ELIGIBILITY_SEQUENCE_UNCONFIRMED", "decision",
                       "入排判定后的执行范围须与已核来源陈述的先后依据一致")
            if entry.action_candidate_indexes:
                reject(item, "POST_ELIGIBILITY_ACTION_STILL_CONTROL", "decision",
                       "本节点候选仍包含这一动作，不能同时列为入排判定后执行")
            if item.unresolved_aspects:
                reject(item, "POST_ELIGIBILITY_SCOPE_UNRESOLVED", "unresolved_aspects",
                       "仍有未核实范围的动作不得排除在当前审核之外")
        elif item.non_control_basis_excerpt is not None:
            reject(item, "POST_ELIGIBILITY_BASIS_UNEXPECTED", "non_control_basis_excerpt",
                   "只有入排判定后执行事项可携带先后依据")
        if covered and entry.status == "linked_only":
            linked_ids = (
                {entry.linked_official_code} if item.decision == "covered_by_official"
                else set(entry.linked_procedure_target_ids)
            )
            if item.target_id not in linked_ids:
                reject(item, "TARGET_LINK_MISMATCH", "target_id", f"第{item.statement_index}条覆盖目标与草稿链接不一致")
        if item.decision == "covered_by_procedure" and target is not None:
            labels = _statement_schedule_label_sources(batch, statement)
            if labels and not _target_contains_row_label(target, labels):
                reject(item, "TARGET_PROCEDURE_ROW_UNPROVEN", "target_id",
                       "流程项目未包含本行项目的来源；共用说明、时点或脚注不能代替项目归属")
        if target is None:
            target_excerpts: list[str] = []
        else:
            target_excerpts = [value for value in target.source_excerpts if value]
            target_action = normalize_source_excerpt(item.target_action_excerpt or "")
            if not target_action or not any(
                target_action in normalize_source_excerpt(excerpt) for excerpt in target_excerpts
            ):
                reject(item, "TARGET_ACTION_UNGROUNDED", "target_action_excerpt", f"第{item.statement_index}条目标动作缺少原文摘录")
            if (covered and "action" in statement.decision_functions
                    and normalize_source_excerpt(_without_display_footnotes(item.target_action_excerpt or ""))
                    in normalize_source_excerpt(_without_display_footnotes(target.label))
                    and not target_action_established(batch, statement, target)
                    and not _full_timed_official_clause_cited(item, target)):
                reject(item, "TARGET_ACTION_LABEL_ONLY_UNPROVEN", "target_action_excerpt",
                       "目录名称只证明项目关联，尚未证明本条操作已被覆盖；须核对动作原文或保留增量要求")
        source_time = normalize_source_excerpt(item.source_time_excerpt or "")
        target_time = normalize_source_excerpt(item.target_time_excerpt or "")
        unit_text = normalize_source_excerpt(owned[statement.structure_unit_id].excerpt)
        quoted_text = normalize_source_excerpt(statement.quoted_text)
        quote_at = unit_text.find(quoted_text)
        colon_at = unit_text.find(":")
        inherited_leading_time = bool(
            source_time and quote_at >= 0 and 0 <= colon_at < quote_at
            and ":" not in unit_text[colon_at + 1:quote_at]
            and source_time in unit_text[:colon_at]
        )
        source_locations = [
            statement.quoted_text,
            statement.scope_quote or "",
            *owned[statement.structure_unit_id].heading_path,
        ]
        source_time_is_composite = bool(statement.time_words) and all(
            normalize_source_excerpt(word) in source_time
            for word in statement.time_words
        ) and any(
            source_time in normalize_source_excerpt(location)
            for location in source_locations
        )
        if covered:
            missing_time = _unreported_time_fragments(statement)
            if missing_time:
                reject(item, "SOURCE_TIME_INCOMPLETE", "source_time_excerpt",
                       f"第{item.statement_index}条原文时间未在陈述清单中逐项列明：{missing_time}")
            if (re.search(r"(?:其余|其他|剩余|后续)(?:的)?访视", quoted_text)
                    and not re.search(r"(?:其余|其他|剩余|后续)(?:的)?访视", source_time)):
                reject(item, "SOURCE_TIME_INCOMPLETE", "source_time_excerpt",
                       "来源时间摘录缺少原文中的相对访视范围")
        source_time_in_scope = bool(source_time) and any(
            source_time in normalize_source_excerpt(location)
            for location in [statement.scope_quote or "", *owned[statement.structure_unit_id].heading_path]
        )
        if source_time and not inherited_leading_time and not source_time_is_composite and not source_time_in_scope and not any(
            source_time in normalize_source_excerpt(value) for value in statement.time_words
        ):
            reject(item, "SOURCE_TIME_UNGROUNDED", "source_time_excerpt", f"第{item.statement_index}条时间措辞不属于该陈述")
        if target_time and target is not None:
            locations = [*target_excerpts]
            if item.target_id in procedures:
                locations.append(procedures[item.target_id].visit_instance)
            if not any(target_time in normalize_source_excerpt(value) for value in locations):
                reject(item, "TARGET_TIME_UNGROUNDED", "target_time_excerpt", f"第{item.statement_index}条目标时间缺少原文或访视定位")
        if covered and statement.time_words and all(
            re.fullmatch(r"每(?:日|天|周|月)(?:\d+|[一二三四五六七八九十]+)次", normalize_source_excerpt(word))
            for word in statement.time_words
        ):
            scope = normalize_source_excerpt(statement.scope_quote or "")
            target_scopes = [*target_excerpts]
            if item.target_id in procedures:
                target_scopes.append(procedures[item.target_id].visit_instance)
            if not scope or not any(scope in normalize_source_excerpt(value) for value in target_scopes):
                reject(item, "FREQUENCY_ONLY_COVERAGE", "target_time_excerpt", "给药频次相同仍须证明来源与目标属于同一访视范围")
        if not covered:
            continue
        if item.decision == "covered_by_procedure" and source_time and target is not None:
            shared_time_spans = {
                span_id
                for span_id, excerpt in zip(target.source_span_ids, target.source_excerpts)
                if excerpt and target_time in normalize_source_excerpt(excerpt)
                and any(
                    other.catalog_item_id != target.catalog_item_id
                    and other.visit_instance != target.visit_instance
                    and any(
                        other_span == span_id and other_excerpt
                        and target_time in normalize_source_excerpt(other_excerpt)
                        for other_span, other_excerpt in zip(
                            other.source_span_ids, other.source_excerpts
                        )
                    )
                    for other in procedures.values()
                )
            }
            if shared_time_spans:
                visit = normalize_source_excerpt(target.visit_instance)
                specific_quote = any(
                    excerpt and target_time in normalize_source_excerpt(excerpt)
                    and span_id not in shared_time_spans
                    for span_id, excerpt in zip(target.source_span_ids, target.source_excerpts)
                )
                source_visits = _visit_scope_keys(source_time)
                target_visits = _visit_scope_keys(visit)
                relative_or_excluded = bool(re.search(
                    r"(?:其余|其他|剩余|后续)(?:的)?访视|除[^。；;]{0,30}外",
                    source_time,
                ))
                if not specific_quote and (
                    relative_or_excluded or not source_visits or not source_visits <= target_visits
                ):
                    reject(item, "TARGET_VISIT_SCOPE_UNPROVEN", "target_id",
                           "多个访视共用原文，所选流程目标缺少本条时期的独立访视依据")
        if item.unresolved_aspects:
            reject(item, "COVERED_WITH_GAPS", "unresolved_aspects", "仍有未覆盖维度的陈述不能标为已有目标完整覆盖")
        if statement.exception_words and not any(
            _exception_in_target(statement.exception_words, excerpt)
            for excerpt in target_excerpts
        ):
            reject(item, "TARGET_EXCEPTION_UNGROUNDED", "target_action_excerpt", f"第{item.statement_index}条例外未在目标原文定位")
        if statement.time_words:
            equivalent_window = _same_explicit_day_week_window(source_time, target_time)
            if not source_time or not target_time or (source_time != target_time and not equivalent_window):
                reject(item, "TIME_SCOPE_MISMATCH", "target_time_excerpt", f"第{item.statement_index}条时间措辞未获两端一致支持")
            target_locations = [*target_excerpts]
            if item.target_id in procedures:
                target_locations.append(procedures[item.target_id].visit_instance)
            unmatched = [
                word for word in statement.time_words
                if not equivalent_window and not all(
                    any(
                        normalize_source_excerpt(part) in normalize_source_excerpt(location)
                        for location in target_locations
                    )
                    for part in re.split(r"[（）()\[\]]", word)
                    if normalize_source_excerpt(part)
                )
            ]
            if unmatched:
                reject(item, "TARGET_TIME_INCOMPLETE", "target_time_excerpt", f"第{item.statement_index}条时间要求未在目标原文逐项覆盖：{unmatched}")
        elif item.source_time_excerpt or item.target_time_excerpt:
            if not inherited_leading_time or source_time != target_time:
                reject(item, "TIME_INVENTED", "source_time_excerpt", "无明确时间措辞的陈述不得凭空补时间")


def validated_source_review_seed(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    coverage: list[SourceStatementCoverage],
    review: SourceTargetReview,
) -> SourceTargetReview | None:
    """Retain individually current decisions for recovery, never final adoption.

    Missing items are allowed in a recovery seed. Duplicate or foreign indexes
    invalidate its scope; a semantically invalid item cannot discard a valid
    sibling. The full-review validator remains mandatory at final consumption.
    """
    expected = set(target_review_indexes(interpretation, coverage, batch))
    indexes = [item.statement_index for item in review.items]
    coverage_indexes = [entry.statement_index for entry in coverage]
    if (len(coverage_indexes) != len(set(coverage_indexes))
            or len(indexes) != len(set(indexes))
            or not set(indexes).issubset(expected)):
        raise SourceTargetReviewValidationError(
            "恢复用来源核对含重复或本次范围外的陈述",
            code="REVIEW_SCOPE_INVALID", statement_index=None, json_path="/items",
        )
    coverage_by_index = {entry.statement_index: entry for entry in coverage}
    kept = []
    for item in review.items:
        single = SourceTargetReview(version=SOURCE_TARGET_REVIEW_VERSION, items=[item])
        try:
            validate_source_target_review(
                batch, interpretation, [coverage_by_index[item.statement_index]], single,
            )
        except SourceTargetReviewValidationError:
            continue
        kept.append(item)
    return (SourceTargetReview(version=SOURCE_TARGET_REVIEW_VERSION, items=kept)
            if kept else None)


def validate_source_definition_consumers(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    consumers: SourceDefinitionConsumers,
) -> None:
    """Verify the definition side of a bounded consumer declaration.

    This step proves the declaration belongs to a source-bound calculation
    definition in this batch and that the definition carries a usable quote.
    The consumer excerpt is validated independently against its own frozen
    source by the layer that holds it: the execution layer resolves a control
    atom inside the frozen hydrated candidate, while an official predicate is
    proven against the frozen RuleSet at publication. This step additionally
    proves the declared official code is one of this batch's frozen official
    targets, so a parent code can never be invented. The two anchors are
    deliberately not required to contain each other, because the definition may
    live in a calculation/method chapter while the consumer is excerpted in an
    eligibility or visit chapter.
    """

    units = {unit.structure_unit_id: unit for unit in batch.owned_units}
    official_codes = {target.official_code for target in batch.known_official_targets}
    for position, item in enumerate(consumers.items):
        path = f"/source_definition_consumers/items/{position}"

        def reject(code: str, message: str, field: str) -> None:
            statement_index = (
                item.statement_index if item.statement_index < len(interpretation.statements) else None
            )
            unit = (
                units.get(interpretation.statements[item.statement_index].structure_unit_id)
                if statement_index is not None else None
            )
            raise SourceTargetReviewValidationError(
                message, code=code, statement_index=statement_index,
                json_path=f"{path}/{field}",
                source_refs=tuple(unit.source_span_ids) if unit is not None else (),
            )

        if item.statement_index >= len(interpretation.statements):
            reject(
                "SOURCE_DEFINITION_CONSUMER_SCOPE_INVALID",
                "定义消费登记引用了不存在的来源陈述", "statement_index",
            )
        statement = interpretation.statements[item.statement_index]
        if item.statement_index not in source_definition_statement_indexes(interpretation):
            reject(
                "SOURCE_DEFINITION_CONSUMER_SCOPE_INVALID",
                "只有本次冻结来源定义可以登记消费原子", "statement_index",
            )
        if not units.get(statement.structure_unit_id):
            reject(
                "SOURCE_DEFINITION_CONSUMER_SCOPE_INVALID",
                "定义消费登记不属于本批冻结来源单元", "statement_index",
            )
        if not normalize_source_excerpt(statement.quoted_text):
            reject(
                "SOURCE_DEFINITION_CONSUMER_QUOTE_BLANK",
                "空来源摘录不能登记消费原子", "statement_index",
            )
        for consumer_position, consumer in enumerate(item.consumers):
            if (consumer.consumer_kind == "official_predicate"
                    and consumer.official_code not in official_codes):
                reject(
                    "SOURCE_DEFINITION_CONSUMER_SCOPE_INVALID",
                    "官方条件消费登记引用了本批冻结官方目标之外的编号",
                    f"consumers/{consumer_position}/official_code",
                )


def require_frozen_official_predicate_identities(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    consumers: SourceDefinitionConsumers,
    official_predicate_identities: Mapping[str, Sequence[tuple[str, str]]] | None,
) -> None:
    """A declared official predicate must exist in the frozen identity index.

    The deep batch exposes parent IN/EX codes only, so the finer
    ``(rule_component_id, predicate_id)`` identity is never derivable from the
    batch itself. A declaration is accepted only when the caller passes the
    frozen identity index that holds it; an absent or empty index rejects every
    official declaration instead of accepting a parent code or wording as
    identity. The publication layer proves the same identity again against the
    frozen RuleSet.
    """

    frozen = {
        code: {(component_id, predicate_id) for component_id, predicate_id in identities}
        for code, identities in (official_predicate_identities or {}).items()
    }
    units = {unit.structure_unit_id: unit for unit in batch.owned_units}
    for item in consumers.items:
        unit = (
            units.get(interpretation.statements[item.statement_index].structure_unit_id)
            if item.statement_index < len(interpretation.statements) else None
        )
        for consumer in item.consumers:
            if consumer.consumer_kind != "official_predicate":
                continue
            if (consumer.rule_component_id, consumer.predicate_id) not in frozen.get(
                consumer.official_code, set()
            ):
                raise SourceTargetReviewValidationError(
                    "官方条件消费身份不在冻结官方条件身份中，不能用父编号或相近文字替代",
                    code="SOURCE_DEFINITION_CONSUMER_IDENTITY_UNPROVEN",
                    statement_index=item.statement_index,
                    json_path="/source_definition_consumers/items",
                    source_refs=tuple(unit.source_span_ids) if unit is not None else (),
                )


def parse_product_source_definition_consumers(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    text: str,
    *,
    official_predicate_identities: Mapping[str, Sequence[tuple[str, str]]] | None = None,
    restricted_statements: Sequence[object] = (),
) -> SourceDefinitionConsumers:
    """Parse and source-bind one declaration; invalid input never becomes a record."""

    consumers = SourceDefinitionConsumers.model_validate_json(text)
    if consumers.version != SOURCE_DEFINITION_CONSUMER_VERSION:
        raise ValueError("当前定义登记回答必须使用本次冻结合同版本")
    validate_source_definition_consumers(batch, interpretation, consumers)
    require_frozen_official_predicate_identities(
        batch, interpretation, consumers, official_predicate_identities,
    )
    validate_restricted_definition_consumers(batch, interpretation, consumers, restricted_statements)
    return consumers


def validate_restricted_definition_consumers(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    consumers: SourceDefinitionConsumers,
    restricted_statements: Sequence[object],
) -> None:
    """Bind restricted references to actual source objects, not proposed IDs."""
    restricted = {item.restricted_statement_id: item for item in restricted_statements}
    units = {unit.structure_unit_id: unit for unit in batch.owned_units}
    for item in consumers.items:
        for consumer in item.consumers:
            if consumer.consumer_kind != "restricted_statement":
                continue
            target = restricted.get(consumer.restricted_statement_id)
            definition = interpretation.statements[item.statement_index]
            if (target is None or target.source_structure_unit_id not in batch.owned_structure_unit_ids
                    or target.source_statement_index >= len(interpretation.statements)
                    or interpretation.statements[target.source_statement_index].structure_unit_id
                    != target.source_structure_unit_id
                    or (target.source_structure_unit_id, target.source_statement_index)
                    == (definition.structure_unit_id, item.statement_index)
                    or interpretation.statements[target.source_statement_index].quoted_text != target.source_quote
                    or sorted(target.source_span_ids)
                    != sorted(units[target.source_structure_unit_id].source_span_ids)
                    or not normalize_source_excerpt(consumer.consumer_excerpt)
                    in normalize_source_excerpt(target.source_quote)):
                raise SourceTargetReviewValidationError(
                    "受限定义消费者未绑定本批实际陈述及其自身逐字原文",
                    code="SOURCE_DEFINITION_CONSUMER_IDENTITY_UNPROVEN",
                    statement_index=item.statement_index,
                    json_path="/source_definition_consumers/items",
                )


def normalize_source_excerpt(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).translate(
        str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
    ).split())


def _full_timed_official_clause_cited(item, target) -> bool:
    """Prove complete citation of a timed official clause, not semantic equivalence.

    A time quoted elsewhere cannot turn a catalog name into a condition. Keep
    footnote markers: removing them would conceal an uncited source dependency.
    Untimed/name-only links continue to require the existing action proof.
    """
    if item.decision != "covered_by_official" or not isinstance(target, KnownOfficialRuleTarget):
        return False
    time = normalize_source_excerpt(item.target_time_excerpt or "")
    action = normalize_source_excerpt(item.target_action_excerpt or "").rstrip("。；;.!！?？")
    if not time or not action:
        return False
    return any(
        time in (quote := normalize_source_excerpt(excerpt).rstrip("。；;.!！?？"))
        and quote in {action, time + action}
        for excerpt in target.source_excerpts if excerpt
    )


def target_action_established(batch, statement, target) -> bool:
    """Proof for a label-only link, not a general semantic equivalence test."""
    from app.protocols.protocol_control_planning import detect_required_action_kinds

    if hasattr(target, "catalog_item_id") and not hasattr(target, "official_code"):
        labels = _statement_schedule_label_sources(batch, statement)
        if labels and not _target_contains_row_label(target, labels):
            return False
    source = normalize_source_excerpt(statement.quoted_text).rstrip("。；;.!！?？")
    required = set(batch.owned_required_action_kinds_by_structure_unit_id.get(
        statement.structure_unit_id, []))
    # A whole paragraph's action kinds cannot prove a different point in it.
    required &= set(detect_required_action_kinds(statement.quoted_text))
    supported = set(getattr(target, "covered_action_kinds", []))
    return any(source and source in normalize_source_excerpt(excerpt or "")
               for excerpt in target.source_excerpts) or bool(required and required <= supported)


def source_requires_temporal_resolution(statement) -> bool:
    """A named visit is not a duration, frequency, or continuing obligation."""
    source = normalize_source_excerpt(" ".join(filter(None, (
        statement.quoted_text, statement.scope_quote, *statement.time_words,
    ))))
    return bool(
        intraday_time_fragments(source)
        or re.search(r"\d+(?:天|日|周|月|年)(?:内|以上|以下)?", source)
        or re.search(r"(?:W|D)\d+[~～至-](?:W|D)?\d+", source)
        or re.search(r"整个|全程|持续|连续|继续", source)
        or re.search(r"期(?:、|，|,|和|及|与).{0,30}期", source)
        or re.search(r"每(?:日|天|周|月)(?:\d+|[一二三四五六七八九十]+)次", source)
    )


def source_visit_scope_matches(scope: str, frozen_visit: str) -> bool:
    # A day at the edge of a visit window is not the entire window.
    visit_codes = re.compile(r"(?:W|D)-?\d+(?:[~～至-](?:W|D)?-?\d+)?", re.IGNORECASE)
    scope_codes = {match.group().upper() for match in visit_codes.finditer(normalize_source_excerpt(scope))}
    frozen_codes = {match.group().upper() for match in visit_codes.finditer(normalize_source_excerpt(frozen_visit))}
    if not scope_codes <= frozen_codes:
        return False
    parts = [normalize_source_excerpt(part) for part in re.split(r"[（）()，,；;：:]", scope)
             if normalize_source_excerpt(part)]
    return bool(parts) and all(
        part in frozen_visit or (
            re.fullmatch(r"[^、，和及与/]+期内", part) is not None
            and part[:-1] in frozen_visit
        ) for part in parts
    )


def source_has_single_visit_anchor(statement) -> bool:
    if len(statement.time_words) != 1 or source_requires_temporal_resolution(statement):
        return False
    word = normalize_source_excerpt(statement.time_words[0])
    return bool(word) and (
        normalize_source_excerpt(statement.quoted_text).startswith(word)
        or normalize_source_excerpt(statement.scope_quote or "") == word
        or (word in normalize_source_excerpt(statement.scope_quote or "")
            and bool(statement.affected_stage)
            and normalize_source_excerpt(statement.affected_stage) in normalize_source_excerpt(
                statement.scope_quote or "")
            and not _unreported_time_fragments(statement))
    )


def shared_prohibition_preserves_source(statement, atom) -> bool:
    """Reuse the gate's exact current/future split, not a semantic shortcut."""
    from app.protocols.protocol_control_gate import _split_prohibition_atom_covers_clause
    source = normalize_source_excerpt(statement.quoted_text)
    continuation = getattr(atom, "continuing_obligation", None)
    if continuation is None:
        return False
    current_verb = re.search(r"不允许|不得|禁止|严禁|不应", atom.statement)
    future_verb = re.search(r"不允许|不得|禁止|严禁|不应", continuation.statement)
    if current_verb is None or future_verb is None:
        return False
    current_prefix = normalize_source_excerpt(atom.statement[:current_verb.start()])
    future_prefix = normalize_source_excerpt(continuation.statement[:future_verb.start()])
    policy = getattr(getattr(atom, "evaluation", None), "observation_policy", None)
    scope = normalize_source_excerpt(getattr(policy, "scope", "") or "")
    period = getattr(getattr(continuation, "prospective_period", None), "period", None)
    period = getattr(period, "value", period)
    future_period_matches = (
        bool(re.search(r"治疗|给药|用药", future_prefix)) if period == "treatment_period" else
        bool(re.search(r"(?:随机|基线|给药|入组)后", future_prefix)) if period == "study_period" else False
    )
    return bool(
        statement.force == "prohibited"
        and not statement.exception_words and not statement.unresolved
        and set(statement.decision_functions) <= {"action", "time_validity"}
        and all(normalize_source_excerpt(word) in source for word in statement.time_words)
        and (not statement.scope_quote or normalize_source_excerpt(statement.scope_quote) in source)
        and current_prefix in scope and future_prefix not in scope and future_period_matches
        and _split_prohibition_atom_covers_clause(
            re.sub(r"[。；;]+$", "", re.sub(r"\s+", "", statement.quoted_text)), atom,
        )
    )


def native_schedule_visit_scope_is_preserved(batch, statement, candidate) -> bool:
    """Prove one marked column against its frozen, physically sourced visit node."""
    if (statement.force not in {"required", "descriptive"}
            or not set(statement.decision_functions) <= {"action", "time_validity"}
            or "action" not in statement.decision_functions
            or statement.exception_words or statement.unresolved
            or statement.scope_context_unit_id is not None or not statement.time_words
            or _unreported_time_fragments(statement)):
        return False
    unit = next((unit for unit in batch.owned_units
                 if unit.structure_unit_id == statement.structure_unit_id), None)
    if (unit is None or unit.table_context is None
            or unit.source_ref.rpartition(".r")[2] != str(unit.table_context.row_index)
            or unit.unit_kind.value != "table_row"
            or unit.structure_unit_id not in candidate.source_structure_unit_ids
            or normalize_source_excerpt(statement.quoted_text) != normalize_source_excerpt(unit.excerpt)):
        return False
    columns = schedule_column_scope(unit, batch.context_units)
    if len(columns) != 1:
        return False
    column = columns[0]
    scope = normalize_source_excerpt(statement.scope_quote or "")
    if (not column.header_source_refs or column.visit_unresolved or column.marker_footnotes
            or column.boundary_side != "at_or_before_baseline"
            or scope != normalize_source_excerpt(column.header_text)
            or any(normalize_source_excerpt(word) not in scope for word in statement.time_words)
            or (statement.affected_stage and normalize_source_excerpt(statement.affected_stage) not in scope)):
        return False
    header_sources = {}
    for header in batch.context_units:
        if not set(header.member_source_refs) & set(column.header_source_refs):
            continue
        if header.member_texts is None or len(header.member_source_refs) != len(header.member_texts):
            return False
        if (header.member_source_span_ids is not None
                and len(header.member_source_span_ids) != len(header.member_source_refs)):
            return False
        for index, (ref, text) in enumerate(zip(
            header.member_source_refs, header.member_texts or [], strict=True,
        )):
            if ref not in column.header_source_refs:
                continue
            spans = (header.member_source_span_ids[index] if header.member_source_span_ids is not None
                     else [span for span in header.source_span_ids if span.endswith(f"::{ref}")])
            if len(spans) != 1 or ref in header_sources or spans[0] not in header.source_span_ids:
                return False
            header_sources[ref] = (spans[0], normalize_source_excerpt(text))
    if set(header_sources) != set(column.header_source_refs):
        return False
    nodes = [node for node in candidate.review_node_bindings if node.role == ReviewNodeRole.DECIDE_AT_NODE]
    if len(nodes) != 1:
        return False
    stages = [stage for stage in batch.known_workflow_stage_targets
              if stage.workflow_stage_id == nodes[0].workflow_stage_id]
    if len(stages) != 1:
        return False
    stage = stages[0]
    if (stage.review_stage != column.review_stage
            or normalize_source_excerpt(stage.visit_instance or "") != scope
            or len(stage.source_span_ids) != len(stage.source_excerpts)):
        return False
    stage_sources = set(zip(stage.source_span_ids,
                            map(normalize_source_excerpt, stage.source_excerpts), strict=True))
    if stage_sources != set(header_sources.values()):
        return False
    row_sources = set()
    if unit.member_texts is None or len(unit.member_texts) != len(unit.member_source_refs):
        return False
    if unit.member_source_span_ids is not None and len(unit.member_source_span_ids) != len(unit.member_source_refs):
        return False
    for index, (ref, text) in enumerate(zip(unit.member_source_refs, unit.member_texts, strict=True)):
        if not text.strip():
            continue
        spans = (unit.member_source_span_ids[index] if unit.member_source_span_ids is not None
                 else [span for span in unit.source_span_ids if span.endswith(f"::{ref}")])
        if len(spans) != 1 or spans[0] not in unit.source_span_ids:
            return False
        row_sources.add((spans[0], normalize_source_excerpt(text)))
    return any(
        atom.kind == ControlObligationKind.COMPLETE_OR_VERIFY
        and normalize_source_excerpt(atom.statement) == normalize_source_excerpt(statement.quoted_text)
        and set(atom.source_span_ids) <= set(unit.source_span_ids)
        and set(atom.source_span_ids) & set(unit.source_span_ids)
        and len(atom.source_span_ids) == len(atom.source_excerpts)
        and row_sources == set(zip(atom.source_span_ids,
                                   map(normalize_source_excerpt, atom.source_excerpts), strict=True))
        for group in candidate.obligation_expression.groups for atom in group.atoms
    )


def simple_visit_action_preserves_time(batch, statement, candidate) -> bool:
    """Only the complete frozen visit scope may be carried by the bound stage."""

    if native_schedule_visit_scope_is_preserved(batch, statement, candidate):
        return True
    if (statement.force not in {"required", "descriptive"}
            or "action" not in statement.decision_functions
            or statement.exception_words or statement.unresolved
            or not source_has_single_visit_anchor(statement)):
        return False
    word = normalize_source_excerpt(statement.scope_quote or statement.time_words[0])
    if normalize_source_excerpt(statement.time_words[0]) not in word:
        return False
    source = normalize_source_excerpt(statement.quoted_text)
    stages = {item.workflow_stage_id: item for item in batch.known_workflow_stage_targets}
    for node in candidate.review_node_bindings:
        stage = stages.get(node.workflow_stage_id)
        if stage is None or node.role != ReviewNodeRole.DECIDE_AT_NODE:
            continue
        frozen_visit = normalize_source_excerpt(" ".join(filter(None, (
            stage.display_name, stage.visit_instance, stage.visit_window,
        ))))
        if source_visit_scope_matches(word, frozen_visit):
            return any(
                atom.kind == ControlObligationKind.COMPLETE_OR_VERIFY
                and source in normalize_source_excerpt(atom.statement)
                for group in candidate.obligation_expression.groups
                for atom in group.atoms
            )
    return False


def relative_visit_action_preserves_time(batch, statement, candidate) -> bool:
    """A later procedure may retain an exact, source-bound earlier-stage condition."""
    from app.domain.contracts.enums import ReviewStage
    from app.protocols.control_scope_sources import resolve_ancestor_scope_citation
    from app.protocols.supplementary_relation_contract import procedure_execution_workflow_stage_id

    if (statement.force != "required" or statement.unresolved or statement.exception_words
            or not statement.scope_quote or "action" not in statement.decision_functions
            or not set(statement.decision_functions) <= {"action", "time_validity"}
            or source_requires_temporal_resolution(statement)):
        return False
    unit = next((item for item in batch.owned_units
                 if item.structure_unit_id == statement.structure_unit_id), None)
    if (unit is None or len(unit.source_span_ids) != 1
            or unit.structure_unit_id not in candidate.source_structure_unit_ids):
        return False
    try:
        citation = resolve_ancestor_scope_citation(
            unit, statement.scope_quote, [*batch.owned_units, *batch.context_units],
        )
    except ValueError:
        return False
    source = normalize_source_excerpt(statement.quoted_text)
    scope = normalize_source_excerpt(statement.scope_quote)
    relative_words = [normalize_source_excerpt(word) for word in statement.time_words
                      if normalize_source_excerpt(word) not in scope]
    if (not relative_words or any(word not in source for word in relative_words)
            or not any(word.endswith(("后", "之后")) for word in relative_words)):
        return False
    stages = {item.workflow_stage_id: item for item in batch.known_workflow_stage_targets}
    prior = [stage for stage in stages.values() if source_visit_scope_matches(
        statement.scope_quote, normalize_source_excerpt(" ".join(filter(None, (
            stage.display_name, stage.visit_instance, stage.visit_window,
        )))),
    )]
    if len(prior) != 1:
        return False
    order = list(ReviewStage)
    for node in candidate.review_node_bindings:
        stage = stages.get(node.workflow_stage_id)
        if (stage is None or node.role != ReviewNodeRole.DECIDE_AT_NODE
                or node.scope_citation != citation
                or order.index(prior[0].review_stage) >= order.index(stage.review_stage)):
            continue
        procedures = [item for item in batch.known_procedure_targets if any(
            relation.kind.value == "supplementary_requirement"
            and relation.external_target_kind.value == "required_procedure"
            and relation.external_target_id == item.catalog_item_id
            and relation.affected_workflow_stage_id == stage.workflow_stage_id
            for relation in candidate.cross_source_relations
        ) and procedure_execution_workflow_stage_id(
            item, batch.known_workflow_stage_targets,
        ) == stage.workflow_stage_id]
        if not procedures:
            continue
        if any(
            atom.kind == ControlObligationKind.COMPLETE_OR_VERIFY
            and normalize_source_excerpt(atom.statement).rstrip("。；;.!！?？") == source.rstrip("。；;.!！?？")
            and set(atom.source_span_ids) <= set(unit.source_span_ids)
            and any(normalize_source_excerpt(excerpt) == source for excerpt in atom.source_excerpts)
            for group in candidate.obligation_expression.groups for atom in group.atoms
        ):
            return True
    return False


def is_study_phase_label(value: str) -> bool:
    """A protocol phase label is population scope, not subject-relative time."""

    return bool(re.fullmatch(
        r"(?:第)?(?:I|II|III|IV|[一二三四])期[:：]?",
        normalize_source_excerpt(value), re.IGNORECASE,
    ))


def _scope_precedes_action_in_same_clause(source: str, scope: str, quote: str) -> bool:
    """A previous action's time is not automatically shared by later actions."""

    if not scope or source.count(quote) != 1:
        return False
    quote_start = source.index(quote)
    if (source.startswith(scope) and scope.endswith((":", "："))
            and quote_start >= len(scope)
            and not any(mark in source[len(scope):quote_start] for mark in (":", "："))):
        return True
    if source.startswith(scope) and quote_start >= len(scope):
        intervening = source[len(scope):quote_start]
        new_time = re.search(
            r"(?:筛选|导入|基线|治疗|研究|试验|随访|随机(?:化)?|首次给药|给药|入组)(?:前|后|时|期|当天)",
            intervening,
        )
        new_time_in_action = re.match(
            r"(?:筛选|导入|基线|治疗|研究|试验|随访|随机(?:化)?|首次给药|给药|入组)(?:前|后|时|期|当天)",
            quote,
        )
        if (not any(mark in intervening for mark in "。！？?!:：")
                and new_time is None and new_time_in_action is None):
            return True
    for found in re.finditer(re.escape(scope), source):
        if found.start() > quote_start:
            break
        between = source[found.end():quote_start]
        boundaries = [position for mark in "。！？?!;"
                      if (position := between.find(mark)) >= 0]
        if boundaries and ":" not in between[:min(boundaries)]:
            continue
        return True
    return False


def _exception_in_target(source_exception: str, target_excerpt: str) -> bool:
    source = normalize_source_excerpt(source_exception)
    target = normalize_source_excerpt(target_excerpt)
    if source in target:
        return True
    source = re.sub(r"[()\[\]]", "", source)
    target = re.sub(r"[()\[\]]", "", target)
    if source in target:
        return True
    declared_alias = normalize_source_excerpt(source_exception)
    matches = list(re.finditer(r"\([A-Za-z][A-Za-z0-9-]+[,，]([A-Z][A-Z0-9-]{1,})\)", declared_alias))
    if not matches:
        return False
    for match in reversed(matches):
        prefix = declared_alias[:match.start()]
        boundaries = [(prefix.rfind(word), word) for word in ("或者", "或", "及", "和", "、", "，", "[", "(")]
        position, boundary = max(boundaries, key=lambda item: item[0])
        term_start = position + len(boundary) if position >= 0 else 0
        term = prefix[term_start:]
        if len(term) < 2 or not all("\u4e00" <= char <= "\u9fff" for char in term):
            return False
        declared_alias = declared_alias[:term_start] + match.group(1) + declared_alias[match.end():]
    return re.sub(r"[()\[\]]", "", declared_alias) in target


class SourceInterpretationValidationError(ValueError):
    """A located source error; display text is never used to route repairs."""

    def __init__(self, code: str, message: str, *, statement_id: int,
                 structure_unit_id: str, json_path: str, source_refs: list[str],
                 retry_class: str) -> None:
        super().__init__(f"{message}：{structure_unit_id}")
        self.code = code
        self.statement_id = statement_id
        self.structure_unit_id = structure_unit_id
        self.json_path = json_path
        self.source_refs = source_refs
        self.retry_class = retry_class
        self.affected_dependents = [structure_unit_id]


def parse_product_source_interpretation(
    batch: ProtocolControlDispositionBatch, text: str,
) -> SourceInterpretation:
    """Require the live reader to state each decision function explicitly."""
    payload = json.loads(text)
    if isinstance(payload, dict) and isinstance(payload.get("statements"), list):
        units = {unit.structure_unit_id: unit for unit in batch.owned_units}
        for index, raw in enumerate(payload["statements"]):
            if not isinstance(raw, dict):
                continue
            missing = "decision_functions" not in raw
            unqualified = raw.get("decision_functions") == ["unclassified"] and not raw.get("unresolved")
            if not missing and not unqualified:
                continue
            unit_id = raw.get("structure_unit_id")
            unit = units.get(unit_id) if isinstance(unit_id, str) else None
            raise SourceInterpretationValidationError(
                "SOURCE_FUNCTION_UNSTATED" if missing else "SOURCE_FUNCTION_UNRESOLVED",
                "来源陈述须说明对本次审核的用途；暂不能确定时写明具体待核之处",
                statement_id=index,
                structure_unit_id=unit_id if isinstance(unit_id, str) else "未知来源单元",
                json_path=f"/statements/{index}/decision_functions",
                source_refs=list(unit.source_span_ids) if unit is not None else [],
                retry_class="source_interpretation",
            )
    return SourceInterpretation.model_validate(payload)


def validate_source_interpretation(
    batch: ProtocolControlDispositionBatch, interpretation: SourceInterpretation
) -> None:
    owned = {unit.structure_unit_id: unit for unit in batch.owned_units}
    statement_ids = {item.structure_unit_id for item in interpretation.statements}
    empty_ids = set(interpretation.units_without_statement)
    if statement_ids | empty_ids != set(owned) or statement_ids & empty_ids:
        affected = sorted((statement_ids | empty_ids) - set(owned)
                          or set(owned) - (statement_ids | empty_ids)
                          or statement_ids & empty_ids)
        unit_id = affected[0]
        index = next((index for index, item in enumerate(interpretation.statements)
                      if item.structure_unit_id == unit_id), 0)
        raise SourceInterpretationValidationError(
            "SOURCE_COVERAGE_INVALID",
            "每个冻结来源单元必须由陈述或无独立陈述说明覆盖，参考单元不得列入",
            statement_id=index, structure_unit_id=unit_id, json_path="/statements",
            source_refs=list(owned[unit_id].source_span_ids) if unit_id in owned else [],
            retry_class="source_inventory",
        )
    for statement_id, item in enumerate(interpretation.statements):
        unit = owned[item.structure_unit_id]
        def reject(code: str, message: str, field: str, retry_class: str) -> None:
            raise SourceInterpretationValidationError(
                code, message, statement_id=statement_id,
                structure_unit_id=item.structure_unit_id,
                json_path=f"statements[{statement_id}].{field}",
                source_refs=list(unit.source_span_ids), retry_class=retry_class,
            )
        source_parts = [*unit.heading_path, unit.excerpt]
        normalized_quote = normalize_source_excerpt(item.quoted_text)
        if not normalized_quote:
            reject("SOURCE_QUOTE_BLANK", "陈述摘录不得只有空白", "quoted_text", "correct_source_quote")
        if not any(
            normalized_quote in normalize_source_excerpt(part)
            for part in source_parts
        ):
            reject("SOURCE_QUOTE_UNGROUNDED", "陈述摘录不属于冻结来源单元", "quoted_text", "correct_source_quote")
        scope = normalize_source_excerpt(item.scope_quote or "")
        context_label = None
        if item.scope_context_unit_id is not None:
            try:
                context_label = immediate_cell_scope_label(
                    unit, item.scope_context_unit_id, item.scope_quote or "",
                    batch.owned_units, batch.context_units,
                )
            except ValueError as exc:
                reject("SOURCE_SCOPE_CONTEXT_INVALID", str(exc), "scope_context_unit_id", "correct_source_scope")
        if item.scope_quote is not None:
            source_excerpt = normalize_source_excerpt(unit.excerpt)
            scope_in_heading = bool(scope) and any(
                scope in normalize_source_excerpt(part) for part in unit.heading_path
            )
            table = unit.table_context
            scope_in_table_header = bool(scope) and table is not None and any(
                scope in normalize_source_excerpt(part)
                for part in [*table.row_headers, *table.column_headers]
            )
            scope_in_visit_headers = False
            if (context_label is None and table is not None
                    and unit.unit_kind in {"table_row", "table_note"} and bool(scope)):
                columns = schedule_column_scope(unit, batch.context_units)
                scope_in_visit_headers = bool(columns) and all(
                    column.header_source_refs
                    and scope in normalize_source_excerpt(column.header_text)
                    for column in columns
                )
            scope_before_statement = (
                bool(scope)
                and _scope_precedes_action_in_same_clause(
                    source_excerpt, scope, normalized_quote,
                )
            )
            if not (context_label is not None or scope_in_heading or scope_in_table_header
                    or scope_in_visit_headers or scope_before_statement):
                reject("SOURCE_SCOPE_UNGROUNDED", "共享范围须来自陈述之前的原文、所属标题或本单元表格标题",
                       "scope_quote", "correct_source_scope")
        if item.affected_stage is not None:
            if is_study_phase_label(item.affected_stage):
                reject("STUDY_PHASE_NOT_VISIT_STAGE", "方案期别不是受试者访视阶段",
                       "affected_stage", "correct_source_scope")
            affected = normalize_source_excerpt(item.affected_stage)
            if not affected or not any(
                affected in normalize_source_excerpt(part)
                for part in [item.quoted_text, (item.scope_quote or "") if context_label is None else "", *unit.heading_path]
            ):
                reject("SOURCE_STAGE_UNGROUNDED", "阶段措辞须来自本条陈述或其共享范围",
                       "affected_stage", "correct_source_scope")
            if not _time_words_cover_stage_label(affected, item.time_words) and not (
                scope and affected in scope and not _unreported_time_fragments(item)
            ):
                reject("SOURCE_STAGE_TIME_MISSING", "明确阶段范围不得从时间措辞中遗漏",
                       "time_words", "correct_source_scope")
        for time_quote in item.time_words:
            if is_study_phase_label(time_quote):
                reject(
                    "STUDY_PHASE_NOT_VISIT_TIME",
                    "方案期别是适用人群范围，不是受试者访视或回溯时间；保留原范围，仅校正时间措辞",
                    "time_words", "correct_source_scope",
                )
            normalized_time = normalize_source_excerpt(time_quote)
            if not normalized_time or not any(
                normalized_time in normalize_source_excerpt(part)
                for part in [item.quoted_text, (item.scope_quote or "") if context_label is None else "", *unit.heading_path]
            ):
                reject("SOURCE_TIME_UNGROUNDED", "时间措辞不属于本条陈述、共享范围或所属标题",
                       "time_words", "correct_source_scope")
        reported_time = [normalize_source_excerpt(word) for word in item.time_words]
        missing_clock = sorted({
            fragment for source in (item.quoted_text, item.scope_quote or "")
            for fragment in intraday_time_fragments(source)
            if not any(fragment in word for word in reported_time)
        })
        if missing_clock:
            reject("SOURCE_TIME_INCOMPLETE", "原文小时或分钟要求不得从时间措辞遗漏："
                   + "、".join(missing_clock), "time_words", "correct_source_scope")
        if item.eligibility_sequence == "after_eligibility_decision":
            source = normalize_source_excerpt(unit.excerpt)
            boundary = normalize_source_excerpt(item.eligibility_sequence_quote or "")
            action_start = source.find(normalized_quote)
            if not boundary or action_start < 0 or boundary not in source[:action_start]:
                reject("POST_ELIGIBILITY_SEQUENCE_UNGROUNDED",
                       "入排判定后的动作须有同一来源单元中位于动作之前的逐字先后依据",
                       "eligibility_sequence_quote", "correct_source_scope")
        elif item.eligibility_sequence_quote is not None:
            reject("POST_ELIGIBILITY_SEQUENCE_UNEXPECTED",
                   "未声明入排判定后执行时不得携带先后依据",
                   "eligibility_sequence_quote", "correct_source_scope")
        if item.control_authority == "cited_external_rationale":
            if (item.eligibility_sequence != "current_or_unknown"
                    or item.eligibility_sequence_quote is not None
                    or not _attribution_in_same_sentence(
                        unit.excerpt, item.quoted_text, item.attribution_quote or "",
                    )):
                reject("SOURCE_ATTRIBUTION_INVALID",
                       "外部资料说明须由同句在前的逐字归因支持，且不得含本研究采纳要求",
                       "attribution_quote", "correct_source_scope")
        elif item.attribution_quote is not None:
            reject("SOURCE_ATTRIBUTION_UNEXPECTED",
                   "未声明外部资料说明时不得填写归因摘录",
                   "attribution_quote", "correct_source_scope")
        elif _has_external_attribution_before_action(unit.excerpt, item.quoted_text):
            reject("SOURCE_ATTRIBUTION_MISSING",
                   "同句外部资料转述须注明逐字归因；不能用描述性语气跳过核对",
                   "attribution_quote", "correct_source_scope")


def _cell_scope_label_packet(batch: ProtocolControlDispositionBatch, unit) -> list[dict[str, str]]:
    result = []
    for candidate in batch.context_units:
        try:
            label = immediate_cell_scope_label(
                unit, candidate.structure_unit_id, candidate.excerpt,
                batch.owned_units, batch.context_units,
            )
        except ValueError:
            continue
        result.append({"structure_unit_id": label.structure_unit_id,
                       "source_ref": label.source_ref, "excerpt": label.excerpt})
    return result


def build_source_interpretation_prompt(batch: ProtocolControlDispositionBatch) -> str:
    source = [
        {
            "structure_unit_id": unit.structure_unit_id,
            "heading_path": unit.heading_path,
            "excerpt": unit.excerpt,
            "table_context": unit.table_context.model_dump(mode="json") if unit.table_context else None,
            "possible_cell_scope_labels": _cell_scope_label_packet(batch, unit),
            **({"referenced_table_notes": batch.table_footnote_context_links[unit.structure_unit_id]}
               if unit.structure_unit_id in batch.table_footnote_context_links else {}),
        }
        for unit in batch.owned_units
    ]
    context = [
        {
            "structure_unit_id": unit.structure_unit_id,
            "source_ref": unit.source_ref,
            "heading_path": unit.heading_path,
            "excerpt": unit.excerpt,
            "table_context": unit.table_context.model_dump(mode="json") if unit.table_context else None,
            **({"referenced_table_notes": batch.table_footnote_context_links[unit.structure_unit_id]}
               if unit.structure_unit_id in batch.table_footnote_context_links else {}),
        }
        for unit in batch.context_units
    ]
    return (
        "你是入排审核系统内置方案分析助手。只处理 owned 原文，context 仅供理解。"
        "逐条摘出可能影响入排阶段的独立陈述，包括当前禁令、未来义务、建议、例外和背景；"
        "一个段落可有多条。quoted_text 必须是该 owned 单元标题或正文的连续逐字摘录。"
        "仅引出随后列举条款、没有另加独立动作或条件的列表引言，"
        "放入 units_without_statement；它的全满足关系由正式入排条款保留，"
        "不可再虚构一条无法回源的独立控制。"
        "若段首范围或本单元 table_context 的行列标题同时约束本条动作，scope_quote 逐字摘录其共同范围，"
        "正文中的范围须在本条动作之前；"
        "相邻段落或 context 单元不能任意借用。possible_cell_scope_labels 只证明紧邻同格项目标签的位置，"
        "不证明它适用；你须另核对象及原文关系。确认直接限定本条时，scope_quote 逐字填写完整标签、"
        "scope_context_unit_id 填标签单元ID；不得拼接或删掉期别。不能确认则保留具体 unresolved。"
        "该ID只能来自本条 possible_cell_scope_labels；空列表必须填 null，其他 context ID 不可填写。"
        "其他情况 scope_context_unit_id 为 null，不借邻段动作、条件、时间或例外；"
        "这个标签引用不授权补 affected_stage、time_words，也不等于已有目标覆盖。"
        "同一 owned 单元有多条陈述时，时间措辞也不能借自另一条陈述，除非本条动作之前有明确共同范围。"
        "不适用共同范围时填 null。quoted_text 只取本条动作；若另填资格先决原文，"
        "该先决短语须在 quoted_text 之前，不能把它并入动作摘录。"
        "force 只表示原文语气，不表示受试者是否满足。"
        "decision_functions 独立记录本条对当前入排决策的功能，可多选 action、definition、"
        "calculation_input、threshold、time_validity、exception；仅明确与入排无关的说明选"
        " background；不能确认用途选 unclassified。描述性语气仍可能规定取值窗口、计算输入"
        "或判定定义，不能因 force 为 descriptive 就选 background。背景或未分类不得与其他功能并列。"
        "引用外部指南、共识、文献等说明研究设计目的时，即使引文内有‘排除’，"
        "也不能因此把转述写成本研究的独立排除要求；逐条保留 force 原语气，"
        "control_authority 填 cited_external_rationale，attribution_quote 填同一句动作之前"
        "直接归属外部资料的连续逐字短语，必须含‘建议/推荐/指出’等转述动词，"
        "不能只填‘指南’。后续逐项核对不能因 force 为 recommended/descriptive 而省略。"
        "归因格式错误时应修正逐字摘录，不能改成描述性语气或无独立陈述来绕过核对。"
        "只有明确的外部资料归因，且同句没有本研究/本方案"
        "采纳为规定或入排标准时才可如此填写；否则用 study_or_unknown、归因填 null，"
        "后续仍须逐条核对。一个段落同时有外部说明与本研究要求时必须拆成不同陈述，"
        "不能把整个段落降为背景。"
        "若同一原文单元明确说先确定符合入排或入组资格，随后才执行本条动作，"
        "eligibility_sequence 写 after_eligibility_decision，并在 eligibility_sequence_quote"
        " 逐字引用动作之前的资格先决原文；否则写 current_or_unknown、引用填 null。"
        "这只记录原文先后关系，不能把未知动作凭治疗期标题或相邻句推为判定之后。"
        "不要在来源摘录阶段预测某句相对筛选、基线或给药节点的判定归属；"
        "time_words 是逐段连续原文组成的数组；无明确时间措辞填空数组，"
        "同一动作有多段时间措辞时分别摘录，不能用分号拼成非原文字串；"
        "小时、分钟和小数时长也须逐字摘出；不得改成当天或若干天，"
        "同句给药前与给药后的时间要求均须保留，程序未支持不等于原文没有要求；"
        "另一动作的日期、阶段或持续时长均不能借给本条，除非有直接适用的共同范围原文；"
        "每项时间措辞须出现在本条 quoted_text、确实适用的 scope_quote 或所属标题中，"
        "段首范围若限定本条动作，应列入 time_words，不可借同段另一动作的时长；"
        "若本句另有明确的相对时点（例如某阶段结束后），而段首仅交代前一阶段的背景，"
        "保留 scope_quote 供理解，但 time_words 只列本句真正约束动作的时点；"
        "不要把同一动作同时标为前一阶段期间和该阶段结束后。"
        "affected_stage 只可逐字取自本条或共同范围；访视时期名称可以由已核 scope_quote 承载，"
        "不必在 time_words 中重复整段标题。日期窗口、时长、频次、前后锚点和小时分钟仍须逐项保留；"
        "没有原文依据则 affected_stage 填 null，不得猜测。"
        "时间、例外、阶段有歧义时保留 unresolved，"
        "表格项目行的 X 应按 member_cell_paths 列位置与同表前置访视行核对，"
        "不可按压缩后的 X 文本顺序推断访视；无法对应时明确写 unresolved。"
        "不得猜测。确实无独立陈述的单元放 units_without_statement。每个 owned 单元必须覆盖。"
        "只返回一个 JSON 对象，字段结构为："
        f'{{"version":"{SOURCE_INTERPRETATION_VERSION}",'
        '"statements":[{"structure_unit_id":"来源单元ID","quoted_text":"逐字原文",'
        '"force":"required|prohibited|recommended|descriptive|unclear",'
        '"decision_functions":["definition","calculation_input"],'
        '"scope_quote":null,"scope_context_unit_id":null,"affected_stage":null,"time_words":[], '
        '"exception_words":null,"unresolved":[],"eligibility_sequence":"current_or_unknown|after_eligibility_decision",'
        '"eligibility_sequence_quote":null,"control_authority":"study_or_unknown|cited_external_rationale",'
        '"attribution_quote":null}],"units_without_statement":[]}。'
        "枚举字段只能取其中一个值；可空字段在原文未写时填 null，不得省略。\n"
        + ("相邻表格原文仅为有界只读片段，不证明清单完整；预算截断或位置边界不是清单结尾。"
           "范围不能核清时保留具体 unresolved。实际读取范围与停止原因："
           f"{json.dumps({key: value.model_dump(mode='json') for key, value in batch.table_context_reading_bounds.items()}, ensure_ascii=False, sort_keys=True)}\n"
           if batch.table_context_reading_bounds else "")
        +
        f"冻结来源：{json.dumps({'owned': source, 'context': context}, ensure_ascii=False, sort_keys=True)}"
        + ("\nreferenced_table_notes 由原生表格标记及表后编号清单对应到只读原文单元，"
           "只证明引用位置，不证明其中全部内容都适用于本行、本期或本访视。"
           "先读所列 context 原文再核适用范围；不得借用另一行项目的动作或条件。"
           "摘录仍来自 owned，不能把脚注中的独立要求复制为本行的新要求；"
           "脚注独立内容的处置以完整清单中的发现记录为准，不在本行重复创建；"
           "引用未列出或内容不足时保留明确疑问。"
           if batch.table_footnote_context_links else "")
    )


def source_interpretation_response_format(
    batch: ProtocolControlDispositionBatch | None = None,
) -> dict[str, object]:
    schema = SourceInterpretation.model_json_schema()
    statement_schema = schema["$defs"]["SourceStatement"]
    statement_schema["properties"]["decision_functions"].pop("default", None)
    statement_schema["required"] = [
        *statement_schema.get("required", []), "decision_functions",
    ]
    if batch is not None:
        owned_ids = list(batch.owned_structure_unit_ids)
        statement_schema["properties"]["structure_unit_id"]["enum"] = owned_ids
        schema["properties"]["units_without_statement"]["items"]["enum"] = owned_ids
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_source_interpretation_" + SOURCE_INTERPRETATION_VERSION.rsplit("/", 1)[-1],
            "strict": True,
            "schema": schema,
        },
    }
