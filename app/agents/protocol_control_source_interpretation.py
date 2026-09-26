"""Source-bound statement inventory for the existing protocol-control Agent."""

from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Literal

from pydantic import Field, model_validator

from app.domain.contracts.common import ContractModel
from app.domain.contracts.protocol_controls import (
    ProtocolControlDispositionBatch,
    StructureUnitDispositionKind,
)
from app.protocols.procedure_catalog import schedule_column_scope


SOURCE_INTERPRETATION_VERSION = "phase5/control-source-interpretation/v8"
SOURCE_INTERPRETATION_PROMPT_VERSION = "phase5/control-source-prompt/v16"
SOURCE_TARGET_REVIEW_VERSION = "phase5/control-source-target-review/v17"

_EXTERNAL_ATTRIBUTION_RE = re.compile(
    r"(?:指南|指导原则|共识|文献|报告|教科书|研究论文)"
    r"[^。！？；;]{0,40}(?:建议|推荐|指出|认为|报道|提出|描述)"
)
_STUDY_ADOPTION_RE = re.compile(
    r"(?:本研究|本方案|本试验|本项目)[^。！？；;]{0,40}"
    r"(?:规定|要求|设定|排除|不得|禁止|必须|须|应)|"
    r"(?:入选|排除|入组)标准|不得随机|不得入组|不予入组"
)


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
    r"每(?:日|天|周|月)(?:\d+|[一二三四五六七八九十]+)次",
    re.IGNORECASE,
)


def _unreported_time_fragments(statement: "SourceStatement") -> list[str]:
    reported = [normalize_source_excerpt(word) for word in statement.time_words]
    fragments = {
        normalize_source_excerpt(match.group())
        for source in (statement.quoted_text, statement.scope_quote or "")
        for match in _EXPLICIT_TIME_FRAGMENT_RE.finditer(source)
        if not any(
            title.start() <= match.start() < title.end()
            for title in re.finditer(r"《[^》]*》", source)
        )
    }
    return sorted(fragment for fragment in fragments if fragment and not any(
        fragment in word for word in reported
    ))


class SourceStatement(ContractModel):
    structure_unit_id: str = Field(min_length=1)
    quoted_text: str = Field(min_length=1)
    scope_quote: str | None = None
    force: Literal["required", "prohibited", "recommended", "descriptive", "unclear"]
    affected_stage: str | None = None
    time_words: list[str] = Field(...)
    exception_words: str | None = None
    unresolved: list[str] = Field(default_factory=list)
    eligibility_sequence: Literal["current_or_unknown", "after_eligibility_decision"] = "current_or_unknown"
    eligibility_sequence_quote: str | None = None
    control_authority: Literal["study_or_unknown", "cited_external_rationale"] = "study_or_unknown"
    attribution_quote: str | None = None


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
        ) and (len(statements) != 1 or any(
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
            statement.force != "required" or not scope or statement.time_words
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
    affected_stage: str | None = None
    time_words: list[str] = Field(...)
    unresolved: str | None = None


def build_source_scope_correction_prompt(
    batch: ProtocolControlDispositionBatch, statement: SourceStatement, issue: str,
) -> str:
    unit = next((item for item in batch.owned_units
                 if item.structure_unit_id == statement.structure_unit_id), None)
    if unit is None:
        raise ValueError("待校正陈述不属于冻结来源")
    return (
        "你是内置方案 Agent 的单条来源范围核对步骤。只核原文动作的适用范围、阶段和时间；"
        "动作摘录、条件、例外及其他陈述已经冻结，不得改写。"
        "time_words 只保留真正约束本条动作且逐字位于本条、其前置共同范围或所属标题的短语；"
        "本条括号内的临床子条件若有独立回溯期限也要逐项列出，文献书名的版本年份不算；"
        "本条及所属标题直接写出的时间不得删除。无法确认时 unresolved 写原因，"
        "I/II/III/IV 期是研究期别，不是受试者访视阶段或动作时间：保留在原句或有据共享范围，"
        "不要放进 affected_stage、time_words。"
        "其余字段按原文填写；能够确认则 unresolved 为 null。"
        "只返回一个 JSON 对象，字段必须齐全，version 必须逐字填写"
        ' "phase5/control-source-scope-correction/v1"，不得写成 1.0 或其他缩写。'
        "字段为 version、structure_unit_id、scope_quote、affected_stage、time_words、unresolved；"
        "可空字段无依据时填 null，time_words 无依据时填空数组。\n"
        f"上轮错误：{issue[:1000]}\n"
        f"冻结单元：{json.dumps({'structure_unit_id': unit.structure_unit_id, 'heading_path': unit.heading_path, 'excerpt': unit.excerpt, 'table_context': unit.table_context.model_dump(mode='json') if unit.table_context else None}, ensure_ascii=False)}\n"
        f"原陈述：{statement.model_dump_json()}"
    )


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
    validate_source_interpretation(batch, updated)
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
    status: Literal["expressed", "candidate_linked", "linked_only", "not_located"]
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
    try:
        columns = schedule_column_scope(unit, batch.context_units)
    except ValueError:
        return []
    if not columns or any(column.boundary_side == "unresolved" for column in columns):
        return []
    parts = unit.excerpt.split(" | ")
    if len(parts) != len(columns) + 1 or not parts[0].strip() or any(
        not re.fullmatch(r"[（(]?\s*[xX×]\s*[)）]?(?:\^\d+)*", part.strip())
        for part in parts[1:]
    ):
        return []
    label_ref = unit.member_source_refs[0]
    label_span = next((span for span in unit.source_span_ids if span.endswith(f"::{label_ref}")), None)
    if label_span is None:
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
                       and label_span in target.source_span_ids
                       and parts[0] in target.source_excerpts]
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


class SourceTargetReviewItem(ContractModel):
    statement_index: int = Field(ge=0)
    decision: Literal[
        "covered_by_official", "covered_by_procedure", "additional_requirement",
        "not_current_control", "unresolved", "potential_same_requirement",
        "cited_external_rationale",
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
    units = {unit.structure_unit_id: unit for unit in batch.owned_units} if batch else {}
    return [
        entry.statement_index
        for entry in coverage
        if (interpretation.statements[entry.statement_index].control_authority
            == "cited_external_rationale"
            or (entry.status != "expressed"
                and entry.disposition in _ENROLLMENT_DISPOSITIONS
                and interpretation.statements[entry.statement_index].force in {"required", "prohibited"}
                and not (
                    entry.schedule_columns
                    and interpretation.statements[entry.statement_index].force == "required"
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
            "scope_quote": interpretation.statements[index].scope_quote,
            "affected_stage": interpretation.statements[index].affected_stage,
            "time_words": interpretation.statements[index].time_words,
            "exception_words": interpretation.statements[index].exception_words,
            "eligibility_sequence": interpretation.statements[index].eligibility_sequence,
            "eligibility_sequence_quote": interpretation.statements[index].eligibility_sequence_quote,
            "control_authority": interpretation.statements[index].control_authority,
            "attribution_quote": interpretation.statements[index].attribution_quote,
        }
        for index in indexes
    ]
    targets = {
        "official": [
            {
                "target_id": target.official_code,
                "label": target.label,
                "source_excerpts": target.source_excerpts,
            }
            for target in batch.known_official_targets
            if comparison_target_id is None or target.official_code == comparison_target_id
        ],
        "procedure": [
            {
                "target_id": target.catalog_item_id,
                "label": target.label,
                "visit_instance": target.visit_instance,
                "source_excerpts": target.source_excerpts,
            }
            for target in batch.known_procedure_targets
            if comparison_target_id is None or target.catalog_item_id == comparison_target_id
        ],
    }
    read_only_sources = [
        {
            "structure_unit_id": unit.structure_unit_id,
            "source_ref": unit.source_ref,
            "heading_path": unit.heading_path,
            "excerpt": unit.excerpt,
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
        "同段已有候选并不等于所有动作已覆盖；目录名称相似也不等于时间、条件、例外都已覆盖。"
        "完整覆盖必须从本陈述截出连续的 source_action_excerpt，并从目标的 source_excerpts 截出连续的"
        " target_action_excerpt。"
        "source_action_excerpt 必须是本条 quoted_text 内的连续原文，不得为了补齐医学条件而拼接"
        "scope_quote 的时间前缀或 quoted_text 外的例外尾句；时间和例外仍须另行核对，不能省略。"
        "两端动作摘录各自必须有原文依据，但文字不必完全相同；全称、缩写或表述差异"
        "只有在给出的方案原文能证明条件、对象、否定、阈值及例外相同后才可报完整覆盖。"
        "如本陈述有明确时间，须再分别给出来源时间与目标摘录或访视中的同一最短连续时间短语，"
        "两个字段归一化后必须完全相同；来源时间可取本条已核实的"
        "scope_quote 或所属标题，不得借相邻陈述的范围；不要把整行访视名称当成目标时间片段。"
        "一条陈述若同时列出访视范围和治疗持续期等多项时间要求，目标原文或访视定位必须逐项支持全部时间措辞；"
        "只对齐其中一项不得宣称完整覆盖，应选 additional_requirement 或 unresolved 并列出未覆盖之处。"
        "仅有每日或每周给药次数相同，不证明审核时期或持续期相同；须保留时间范围待核。"
        "若来源只写相对时点而目标只写另一访视名称、两边没有共同时间原文，"
        "即使你认为语义可能相当，也只能选 additional_requirement 或 unresolved，不得报完整覆盖。"
        "若本条来源的动作、对象和相对时点本身均有逐字依据，只是已有目标缺少该时点，"
        "应选 additional_requirement，引用已有目标作为对照并写明时间差额；"
        "只有来源动作或适用时期自身无法从本条及其明确范围核清时才选 unresolved。"
        "不得为了选增量要求，借同单元另一动作的时期、频次或治疗持续期。"
        "未完整覆盖时可以附上已有目标的逐字动作和时间作为核对线索，同时在 unresolved_aspects"
        "写明未对齐之处；此类目标引用不代表已覆盖。"
        "不要把未来要求提前判作当前已完成，不推断原文未写的例外。"
        "只读来源单元仅供识别跨章节复述、补充或矛盾的待核线索；它们不是冻结已有目标。"
        "不得因两段文字相似就报完整覆盖，也不得把只读来源的时期、例外或完成强度写成本陈述自己的原文。"
        "如后文可能补充本句但当前无法证明完整关系，列出具体差异并选增量或未核，不能直接舍弃本句。"
        "potential_same_requirement 只可引用给出的另一只读原文单元；两端对象与核心动作均须逐字相同，"
        "并给出该单元同句的明确适用时期 target_scope_excerpt。此判断仅登记待核关系，"
        "不等于已有控制覆盖；后文必须独立解构并在最终发布前再次核验。"
        "source_object_excerpt、target_object_excerpt、target_scope_excerpt 仅限"
        " potential_same_requirement；其他所有 decision 的这三个字段必须填 null，"
        "不能把对象从 source_action_excerpt 中拆走，也不能以额外字段表达普通目标覆盖。"
        "已有链接仅为核对线索，不能代替原文；若声称链接的条款或流程完整覆盖，"
        "须引用草稿实际链接的同一目标，否则保持待核。"
        "不得省略任何陈述，不能引用未列出的目标。只返回 JSON 对象。\n"
        f'输出结构：{{"version":"{SOURCE_TARGET_REVIEW_VERSION}","items":'
        '[{"statement_index":0,"decision":"covered_by_official|covered_by_procedure|'
        'additional_requirement|not_current_control|unresolved|potential_same_requirement|cited_external_rationale","target_id":null,"source_action_excerpt":"逐字动作",'
        '"target_action_excerpt":null,"source_object_excerpt":null,"target_object_excerpt":null,'
        '"source_time_excerpt":null,"target_time_excerpt":null,"target_scope_excerpt":null,'
        '"unresolved_aspects":[],"non_control_basis_excerpt":null,"attribution_excerpt":null}]}。枚举值只选一个，未知目标填 null；'
        '非跨章节关系的对象与另一来源时期字段一律填 null。\n'
        f"待核陈述：{json.dumps(source, ensure_ascii=False, sort_keys=True)}\n"
        f"冻结已有目标：{json.dumps(targets, ensure_ascii=False, sort_keys=True)}\n"
        f"只读来源线索：{json.dumps(read_only_sources, ensure_ascii=False, sort_keys=True)}"
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
        covered = item.decision in {"covered_by_official", "covered_by_procedure"}
        if (not covered and item.decision not in {"not_current_control", "potential_same_requirement",
                                                "cited_external_rationale"}
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
            scope_at = context_text.rfind(scope, 0, action_at) if scope and action_at >= 0 else -1
            source_object_at = (source_context.rfind(source_object, 0, source_action_at)
                                if source_object and source_action_at >= 0 else -1)
            target_object_at = (context_text.rfind(target_object, 0, action_at)
                                if target_object and action_at >= 0 else -1)
            if (context is None or len(source_text) < 8
                    or source_text not in normalize_source_excerpt(statement.quoted_text)
                    or source_text != target_action
                    or source_object != target_object or len(source_object) < 3
                    or source_object_at < 0 or target_object_at < 0
                    or source_action_at < 0 or action_at < 0 or scope_at < 0
                    or any(mark in source_context[source_object_at:source_action_at] for mark in "。；;")
                    or any(mark in context_text[target_object_at:action_at] for mark in "。；;")
                    or any(mark in context_text[scope_at:action_at] for mark in "。；;")):
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
        if target is None:
            target_excerpts: list[str] = []
        else:
            target_excerpts = [value for value in target.source_excerpts if value]
            target_action = normalize_source_excerpt(item.target_action_excerpt or "")
            if not target_action or not any(
                target_action in normalize_source_excerpt(excerpt) for excerpt in target_excerpts
            ):
                reject(item, "TARGET_ACTION_UNGROUNDED", "target_action_excerpt", f"第{item.statement_index}条目标动作缺少原文摘录")
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
        if item.unresolved_aspects:
            reject(item, "COVERED_WITH_GAPS", "unresolved_aspects", "仍有未覆盖维度的陈述不能标为已有目标完整覆盖")
        if statement.exception_words and not any(
            _exception_in_target(statement.exception_words, excerpt)
            for excerpt in target_excerpts
        ):
            reject(item, "TARGET_EXCEPTION_UNGROUNDED", "target_action_excerpt", f"第{item.statement_index}条例外未在目标原文定位")
        if statement.time_words:
            if not source_time or not target_time or source_time != target_time:
                reject(item, "TIME_SCOPE_MISMATCH", "target_time_excerpt", f"第{item.statement_index}条时间措辞未获两端一致支持")
            target_locations = [*target_excerpts]
            if item.target_id in procedures:
                target_locations.append(procedures[item.target_id].visit_instance)
            unmatched = [
                word for word in statement.time_words
                if not all(
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


def normalize_source_excerpt(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).translate(
        str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
    ).split())


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


def validate_source_interpretation(
    batch: ProtocolControlDispositionBatch, interpretation: SourceInterpretation
) -> None:
    owned = {unit.structure_unit_id: unit for unit in batch.owned_units}
    statement_ids = {item.structure_unit_id for item in interpretation.statements}
    empty_ids = set(interpretation.units_without_statement)
    if statement_ids | empty_ids != set(owned) or statement_ids & empty_ids:
        raise ValueError("每个冻结来源单元必须由陈述或无独立陈述说明覆盖")
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
            if table is not None and unit.unit_kind in {"table_row", "table_note"} and bool(scope):
                try:
                    columns = schedule_column_scope(unit, batch.context_units)
                except ValueError:
                    columns = ()
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
            if not (scope_in_heading or scope_in_table_header
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
                for part in [item.quoted_text, item.scope_quote or "", *unit.heading_path]
            ):
                reject("SOURCE_STAGE_UNGROUNDED", "阶段措辞须来自本条陈述或其共享范围",
                       "affected_stage", "correct_source_scope")
            if not any(
                affected in normalize_source_excerpt(part)
                or normalize_source_excerpt(part) in affected
                for part in item.time_words if normalize_source_excerpt(part)
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
                for part in [item.quoted_text, item.scope_quote or "", *unit.heading_path]
            ):
                reject("SOURCE_TIME_UNGROUNDED", "时间措辞不属于本条陈述、共享范围或所属标题",
                       "time_words", "correct_source_scope")
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


def build_source_interpretation_prompt(batch: ProtocolControlDispositionBatch) -> str:
    source = [
        {
            "structure_unit_id": unit.structure_unit_id,
            "heading_path": unit.heading_path,
            "excerpt": unit.excerpt,
            "table_context": unit.table_context.model_dump(mode="json") if unit.table_context else None,
        }
        for unit in batch.owned_units
    ]
    context = [
        {
            "heading_path": unit.heading_path,
            "excerpt": unit.excerpt,
            "table_context": unit.table_context.model_dump(mode="json") if unit.table_context else None,
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
        "不适用共同范围时填 null。quoted_text 只取本条动作；若另填资格先决原文，"
        "该先决短语须在 quoted_text 之前，不能把它并入动作摘录。"
        "force 只表示原文语气，不表示受试者是否满足。"
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
        "另一动作的日期、阶段或持续时长均不能借给本条，除非有直接适用的共同范围原文；"
        "每项时间措辞须出现在本条 quoted_text、确实适用的 scope_quote 或所属标题中，"
        "段首范围若限定本条动作，应列入 time_words，不可借同段另一动作的时长；"
        "若本句另有明确的相对时点（例如某阶段结束后），而段首仅交代前一阶段的背景，"
        "保留 scope_quote 供理解，但 time_words 只列本句真正约束动作的时点；"
        "不要把同一动作同时标为前一阶段期间和该阶段结束后。"
        "affected_stage 只可逐字取自本条或共同范围，且须在 time_words 中有对应原文；否则填 null。"
        "时间、例外、阶段有歧义时保留 unresolved，"
        "表格项目行的 X 应按 member_cell_paths 列位置与同表前置访视行核对，"
        "不可按压缩后的 X 文本顺序推断访视；无法对应时明确写 unresolved。"
        "不得猜测。确实无独立陈述的单元放 units_without_statement。每个 owned 单元必须覆盖。"
        "只返回一个 JSON 对象，字段结构为："
        f'{{"version":"{SOURCE_INTERPRETATION_VERSION}",'
        '"statements":[{"structure_unit_id":"来源单元ID","quoted_text":"逐字原文",'
        '"force":"required|prohibited|recommended|descriptive|unclear",'
        '"scope_quote":null,"affected_stage":null,"time_words":[], '
        '"exception_words":null,"unresolved":[],"eligibility_sequence":"current_or_unknown|after_eligibility_decision",'
        '"eligibility_sequence_quote":null,"control_authority":"study_or_unknown|cited_external_rationale",'
        '"attribution_quote":null}],"units_without_statement":[]}。'
        "枚举字段只能取其中一个值；可空字段在原文未写时填 null，不得省略。\n"
        f"冻结来源：{json.dumps({'owned': source, 'context': context}, ensure_ascii=False, sort_keys=True)}"
    )


def source_interpretation_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_source_interpretation_" + SOURCE_INTERPRETATION_VERSION.rsplit("/", 1)[-1],
            "strict": True,
            "schema": SourceInterpretation.model_json_schema(),
        },
    }
