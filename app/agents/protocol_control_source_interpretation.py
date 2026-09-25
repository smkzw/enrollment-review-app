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


SOURCE_INTERPRETATION_VERSION = "phase5/control-source-interpretation/v6"
SOURCE_INTERPRETATION_PROMPT_VERSION = "phase5/control-source-prompt/v9"
SOURCE_TARGET_REVIEW_VERSION = "phase5/control-source-target-review/v7"


_ENROLLMENT_DISPOSITIONS = frozenset({
    StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY.value,
    StructureUnitDispositionKind.REQUIRED_PROCEDURE.value,
    StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value,
    StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT.value,
    StructureUnitDispositionKind.PENDING_CONFIRMATION.value,
})


class SourceStatement(ContractModel):
    structure_unit_id: str = Field(min_length=1)
    quoted_text: str = Field(min_length=1)
    scope_quote: str | None = None
    force: Literal["required", "prohibited", "recommended", "descriptive", "unclear"]
    affected_stage: str | None = None
    time_words: list[str] = Field(...)
    exception_words: str | None = None
    unresolved: list[str] = Field(default_factory=list)


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
        "本条及所属标题直接写出的时间不得删除。无法确认时 unresolved 写原因，"
        "其余字段按原文填写；能够确认则 unresolved 为 null。"
        "只返回 version、structure_unit_id、scope_quote、affected_stage、time_words、unresolved。\n"
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
    unit = next((item for item in batch.owned_units
                 if item.structure_unit_id == statement.structure_unit_id), None)
    if unit is None or correction.structure_unit_id != statement.structure_unit_id or correction.unresolved:
        raise ValueError("单条来源范围仍未核清")
    direct_locations = [statement.quoted_text, *unit.heading_path]
    for word in statement.time_words:
        normalized = normalize_source_excerpt(word)
        if any(normalized in normalize_source_excerpt(part) for part in direct_locations) and word not in correction.time_words:
            raise ValueError("陈述或标题中的明确时间不可在局部校正时删除")
    if statement.affected_stage and any(
        normalize_source_excerpt(statement.affected_stage) in normalize_source_excerpt(part)
        for part in direct_locations
    ) and correction.affected_stage != statement.affected_stage:
        raise ValueError("陈述或标题中的明确阶段不可在局部校正时删除")
    updated = interpretation.model_copy(deep=True)
    updated.statements[statement_index].scope_quote = correction.scope_quote
    updated.statements[statement_index].affected_stage = correction.affected_stage
    updated.statements[statement_index].time_words = correction.time_words
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
) -> str:
    unit = next(
        (item for item in batch.owned_units
         if item.structure_unit_id == statement.structure_unit_id), None
    )
    if unit is None:
        raise ValueError("待校正陈述不属于冻结来源")
    return (
        "你是内置方案 Agent 的逐字来源校正步骤。前次摘录不属于冻结原文。"
        "只从同一单元标题或正文选取表达原陈述同一要求的连续原句；"
        "不要换另一条要求、增加临床解释或改写数值、否定、时间与例外。"
        "无法逐字定位同一要求时 corrected_quote 填 null，并在 unresolved 说明。"
        "可以找到时 unresolved 填 null。只返回结构化 JSON。\n"
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
        "covered_by_official", "covered_by_procedure", "additional_requirement", "unresolved"
    ]
    target_id: str | None = None
    source_action_excerpt: str = Field(min_length=1)
    target_action_excerpt: str | None = None
    source_time_excerpt: str | None = None
    target_time_excerpt: str | None = None
    unresolved_aspects: list[str] = Field(default_factory=list)


class SourceTargetReview(ContractModel):
    version: Literal[SOURCE_TARGET_REVIEW_VERSION]
    items: list[SourceTargetReviewItem]


def target_review_indexes(
    interpretation: SourceInterpretation,
    coverage: list[SourceStatementCoverage],
    batch: ProtocolControlDispositionBatch | None = None,
) -> list[int]:
    units = {unit.structure_unit_id: unit for unit in batch.owned_units} if batch else {}
    return [
        entry.statement_index
        for entry in coverage
        if entry.status != "expressed"
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
        )
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
        ],
        "procedure": [
            {
                "target_id": target.catalog_item_id,
                "label": target.label,
                "visit_instance": target.visit_instance,
                "source_excerpts": target.source_excerpts,
            }
            for target in batch.known_procedure_targets
        ],
    }
    return (
        "你是本系统方案 Agent 的逐项来源核对步骤。仅核下面列出的陈述，不生成新规则或判断受试者。"
        "每条只可选：已有官方入排完整覆盖、已有访视流程完整覆盖、尚有增量要求、无法核清。"
        "同段已有候选并不等于所有动作已覆盖；目录名称相似也不等于时间、条件、例外都已覆盖。"
        "完整覆盖必须从本陈述截出连续的 source_action_excerpt，并从目标的 source_excerpts 截出连续的"
        " target_action_excerpt；如本陈述有明确时间，须再分别给出来源时间与目标摘录或访视中的"
        "同一最短连续时间短语，两个字段归一化后必须完全相同；来源时间可取本条已核实的"
        "scope_quote 或所属标题，不得借相邻陈述的范围；不要把整行访视名称当成目标时间片段。"
        "一条陈述若同时列出访视范围和治疗持续期等多项时间要求，目标原文或访视定位必须逐项支持全部时间措辞；"
        "只对齐其中一项不得宣称完整覆盖，应选 additional_requirement 或 unresolved 并列出未覆盖之处。"
        "若来源只写相对时点而目标只写另一访视名称、两边没有共同时间原文，"
        "即使你认为语义可能相当，也只能选 additional_requirement 或 unresolved，不得报完整覆盖。"
        "未完整覆盖时可以附上已有目标的逐字动作和时间作为核对线索，同时在 unresolved_aspects"
        "写明未对齐之处；此类目标引用不代表已覆盖。"
        "不要把未来要求提前判作当前已完成，不推断原文未写的例外。"
        "已有链接仅为核对线索，不能代替原文；若声称链接的条款或流程完整覆盖，"
        "须引用草稿实际链接的同一目标，否则保持待核。"
        "不得省略任何陈述，不能引用未列出的目标。只返回 JSON 对象。\n"
        '输出结构：{"version":"phase5/control-source-target-review/v7","items":'
        '[{"statement_index":0,"decision":"covered_by_official|covered_by_procedure|'
        'additional_requirement|unresolved","target_id":null,"source_action_excerpt":"逐字动作",'
        '"target_action_excerpt":null,"source_time_excerpt":null,"target_time_excerpt":null,'
        '"unresolved_aspects":[]}]}。枚举值只选一个，未知目标填 null。\n'
        f"待核陈述：{json.dumps(source, ensure_ascii=False, sort_keys=True)}\n"
        f"冻结已有目标：{json.dumps(targets, ensure_ascii=False, sort_keys=True)}"
    )


def source_target_review_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_source_target_review_v7",
            "strict": True,
            "schema": SourceTargetReview.model_json_schema(),
        },
    }


def validate_source_target_review(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    coverage: list[SourceStatementCoverage],
    review: SourceTargetReview,
) -> None:
    expected = target_review_indexes(interpretation, coverage, batch)
    if sorted(item.statement_index for item in review.items) != sorted(expected):
        raise ValueError("逐项来源核对必须且只能覆盖本次待核陈述")
    coverage_by_index = {entry.statement_index: entry for entry in coverage}
    official = {item.official_code: item for item in batch.known_official_targets}
    procedures = {item.catalog_item_id: item for item in batch.known_procedure_targets}
    owned = {unit.structure_unit_id: unit for unit in batch.owned_units}
    for item in review.items:
        statement = interpretation.statements[item.statement_index]
        action = normalize_source_excerpt(item.source_action_excerpt)
        if not action or action not in normalize_source_excerpt(statement.quoted_text):
            raise ValueError(f"第{item.statement_index}条动作摘录不属于冻结陈述")
        covered = item.decision in {"covered_by_official", "covered_by_procedure"}
        if not covered and not item.unresolved_aspects:
            raise ValueError("未完整覆盖的陈述必须说明待核实之处")
        if bool(item.target_id) != bool(item.target_action_excerpt):
            raise ValueError("目标身份与目标动作摘录必须同时提供")
        if not item.target_id:
            if covered or item.target_time_excerpt:
                raise ValueError("目标时间或完整覆盖必须有冻结目标")
            target = None
        elif item.decision == "covered_by_official":
            target = official.get(item.target_id)
        elif item.decision == "covered_by_procedure":
            target = procedures.get(item.target_id)
        else:
            matches = [entry for entry in (official.get(item.target_id), procedures.get(item.target_id)) if entry]
            target = matches[0] if len(matches) == 1 else None
        if item.target_id and target is None:
            raise ValueError(f"第{item.statement_index}条引用了非冻结或不唯一的目标")
        entry = coverage_by_index[item.statement_index]
        if covered and entry.status == "linked_only":
            linked_ids = (
                {entry.linked_official_code} if item.decision == "covered_by_official"
                else set(entry.linked_procedure_target_ids)
            )
            if item.target_id not in linked_ids:
                raise ValueError(f"第{item.statement_index}条覆盖目标与草稿链接不一致")
        if target is None:
            target_excerpts: list[str] = []
        else:
            target_excerpts = [value for value in target.source_excerpts if value]
            target_action = normalize_source_excerpt(item.target_action_excerpt or "")
            if not target_action or not any(
                target_action in normalize_source_excerpt(excerpt) for excerpt in target_excerpts
            ):
                raise ValueError(f"第{item.statement_index}条目标动作缺少原文摘录")
        source_time = normalize_source_excerpt(item.source_time_excerpt or "")
        target_time = normalize_source_excerpt(item.target_time_excerpt or "")
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
        if source_time and not source_time_is_composite and not any(
            source_time in normalize_source_excerpt(value) for value in statement.time_words
        ):
            raise ValueError(f"第{item.statement_index}条时间措辞不属于该陈述")
        if target_time and target is not None:
            locations = [*target_excerpts]
            if item.target_id in procedures:
                locations.append(procedures[item.target_id].visit_instance)
            if not any(target_time in normalize_source_excerpt(value) for value in locations):
                raise ValueError(f"第{item.statement_index}条目标时间缺少原文或访视定位")
        if not covered:
            continue
        if item.unresolved_aspects:
            raise ValueError("仍有未覆盖维度的陈述不能标为已有目标完整覆盖")
        if statement.exception_words and not any(
            _exception_in_target(statement.exception_words, excerpt)
            for excerpt in target_excerpts
        ):
            raise ValueError(f"第{item.statement_index}条例外未在目标原文定位")
        if statement.time_words:
            if not source_time or not target_time or source_time != target_time:
                raise ValueError(f"第{item.statement_index}条时间措辞未获两端一致支持")
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
                raise ValueError(
                    f"第{item.statement_index}条时间要求未在目标原文逐项覆盖：{unmatched}"
                )
        elif item.source_time_excerpt or item.target_time_excerpt:
            raise ValueError("无明确时间措辞的陈述不得凭空补时间")


def normalize_source_excerpt(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).translate(
        str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
    ).split())


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


def validate_source_interpretation(
    batch: ProtocolControlDispositionBatch, interpretation: SourceInterpretation
) -> None:
    owned = {unit.structure_unit_id: unit for unit in batch.owned_units}
    statement_ids = {item.structure_unit_id for item in interpretation.statements}
    empty_ids = set(interpretation.units_without_statement)
    if statement_ids | empty_ids != set(owned) or statement_ids & empty_ids:
        raise ValueError("每个冻结来源单元必须由陈述或无独立陈述说明覆盖")
    for item in interpretation.statements:
        unit = owned[item.structure_unit_id]
        source_parts = [*unit.heading_path, unit.excerpt]
        normalized_quote = normalize_source_excerpt(item.quoted_text)
        if not normalized_quote:
            raise ValueError(f"陈述摘录不得只有空白：{item.structure_unit_id}")
        if not any(
            normalized_quote in normalize_source_excerpt(part)
            for part in source_parts
        ):
            raise ValueError(f"陈述摘录不属于冻结来源单元：{item.structure_unit_id}")
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
                and scope in source_excerpt
                and normalized_quote in source_excerpt
                and source_excerpt.index(scope) <= source_excerpt.index(normalized_quote)
            )
            if not (scope_in_heading or scope_in_table_header
                    or scope_in_visit_headers or scope_before_statement):
                raise ValueError(
                    f"共享范围须来自陈述之前的原文、所属标题或本单元表格标题：{item.structure_unit_id}"
                )
        if item.affected_stage is not None:
            affected = normalize_source_excerpt(item.affected_stage)
            if not affected or not any(
                affected in normalize_source_excerpt(part)
                for part in [item.quoted_text, item.scope_quote or "", *unit.heading_path]
            ):
                raise ValueError(f"阶段措辞须来自本条陈述或其共享范围：{item.structure_unit_id}")
            if not any(
                affected in normalize_source_excerpt(part)
                or normalize_source_excerpt(part) in affected
                for part in item.time_words if normalize_source_excerpt(part)
            ):
                raise ValueError(f"明确阶段范围不得从时间措辞中遗漏：{item.structure_unit_id}")
        for time_quote in item.time_words:
            normalized_time = normalize_source_excerpt(time_quote)
            if not normalized_time or not any(
                normalized_time in normalize_source_excerpt(part)
                for part in [item.quoted_text, item.scope_quote or "", *unit.heading_path]
            ):
                raise ValueError(f"时间措辞不属于本条陈述、共享范围或所属标题：{item.structure_unit_id}")


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
        "若段首范围或本单元 table_context 的行列标题同时约束本条动作，scope_quote 逐字摘录其共同范围，"
        "正文中的范围须在本条动作之前；"
        "不适用共同范围时填 null。quoted_text 尽量只取本条动作，不把其他动作混入。"
        "force 只表示原文语气，不表示受试者是否满足。"
        "不要在来源摘录阶段预测某句相对筛选、基线或给药节点的判定归属；"
        "time_words 是逐段连续原文组成的数组；无明确时间措辞填空数组，"
        "同一动作有多段时间措辞时分别摘录，不能用分号拼成非原文字串，也不可借用另一动作的时长；"
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
        '{"version":"phase5/control-source-interpretation/v6",'
        '"statements":[{"structure_unit_id":"来源单元ID","quoted_text":"逐字原文",'
        '"force":"required|prohibited|recommended|descriptive|unclear",'
        '"scope_quote":null,"affected_stage":null,"time_words":[], '
        '"exception_words":null,"unresolved":[]}],"units_without_statement":[]}。'
        "枚举字段只能取其中一个值；可空字段在原文未写时填 null，不得省略。\n"
        f"冻结来源：{json.dumps({'owned': source, 'context': context}, ensure_ascii=False, sort_keys=True)}"
    )


def source_interpretation_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_source_interpretation_v1",
            "strict": True,
            "schema": SourceInterpretation.model_json_schema(),
        },
    }
