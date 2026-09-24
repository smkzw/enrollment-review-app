"""Source-bound statement inventory for the existing protocol-control Agent."""

from __future__ import annotations

import json
import unicodedata
from typing import Literal

from pydantic import Field, model_validator

from app.domain.contracts.common import ContractModel
from app.domain.contracts.protocol_controls import (
    ProtocolControlDispositionBatch,
    StructureUnitDispositionKind,
)


SOURCE_INTERPRETATION_VERSION = "phase5/control-source-interpretation/v6"
SOURCE_INTERPRETATION_PROMPT_VERSION = "phase5/control-source-prompt/v9"
SOURCE_TARGET_REVIEW_VERSION = "phase5/control-source-target-review/v5"


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
) -> list[int]:
    return [
        entry.statement_index
        for entry in coverage
        if entry.status != "expressed"
        and entry.disposition in _ENROLLMENT_DISPOSITIONS
        and interpretation.statements[entry.statement_index].force in {"required", "prohibited"}
    ]


def build_source_target_review_prompt(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    coverage: list[SourceStatementCoverage],
) -> str:
    indexes = target_review_indexes(interpretation, coverage)
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
        "同一最短连续时间短语，两个字段归一化后必须完全相同；不要把整行访视名称当成目标时间片段。"
        "若来源只写相对时点而目标只写另一访视名称、两边没有共同时间原文，"
        "即使你认为语义可能相当，也只能选 additional_requirement 或 unresolved，不得报完整覆盖。"
        "未完整覆盖时可以附上已有目标的逐字动作和时间作为核对线索，同时在 unresolved_aspects"
        "写明未对齐之处；此类目标引用不代表已覆盖。"
        "不要把未来要求提前判作当前已完成，不推断原文未写的例外。"
        "已有链接仅为核对线索，不能代替原文；若声称链接的条款或流程完整覆盖，"
        "须引用草稿实际链接的同一目标，否则保持待核。"
        "不得省略任何陈述，不能引用未列出的目标。只返回 JSON 对象。\n"
        '输出结构：{"version":"phase5/control-source-target-review/v5","items":'
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
            "name": "protocol_control_source_target_review_v5",
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
    expected = target_review_indexes(interpretation, coverage)
    if sorted(item.statement_index for item in review.items) != sorted(expected):
        raise ValueError("逐项来源核对必须且只能覆盖本次待核陈述")
    coverage_by_index = {entry.statement_index: entry for entry in coverage}
    official = {item.official_code: item for item in batch.known_official_targets}
    procedures = {item.catalog_item_id: item for item in batch.known_procedure_targets}
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
        if source_time and not any(
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
            normalize_source_excerpt(statement.exception_words) in normalize_source_excerpt(excerpt)
            for excerpt in target_excerpts
        ):
            raise ValueError(f"第{item.statement_index}条例外未在目标原文定位")
        if statement.time_words:
            if not source_time or not target_time or source_time != target_time:
                raise ValueError(f"第{item.statement_index}条时间措辞未获两端一致支持")
        elif item.source_time_excerpt or item.target_time_excerpt:
            raise ValueError("无明确时间措辞的陈述不得凭空补时间")


def normalize_source_excerpt(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).translate(
        str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
    ).split())


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
            scope_before_statement = (
                bool(scope)
                and scope in source_excerpt
                and normalized_quote in source_excerpt
                and source_excerpt.index(scope) < source_excerpt.index(normalized_quote)
            )
            if not (scope_in_heading or scope_in_table_header or scope_before_statement):
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
