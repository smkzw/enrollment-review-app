"""Source-bound statement inventory for the existing protocol-control Agent."""

from __future__ import annotations

import json
import unicodedata
from typing import Literal

from pydantic import Field, model_validator

from app.domain.contracts.common import ContractModel
from app.domain.contracts.protocol_controls import ProtocolControlDispositionBatch


SOURCE_INTERPRETATION_VERSION = "phase5/control-source-interpretation/v5"
SOURCE_INTERPRETATION_PROMPT_VERSION = "phase5/control-source-prompt/v6"


class SourceStatement(ContractModel):
    structure_unit_id: str = Field(min_length=1)
    quoted_text: str = Field(min_length=1)
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
        for time_quote in item.time_words:
            normalized_time = normalize_source_excerpt(time_quote)
            if not normalized_time or not any(
                normalized_time in normalize_source_excerpt(part)
                for part in [item.quoted_text, *unit.heading_path]
            ):
                raise ValueError(f"时间措辞不属于本条陈述或所属标题：{item.structure_unit_id}")


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
        "force 只表示原文语气，不表示受试者是否满足。"
        "不要在来源摘录阶段预测某句相对筛选、基线或给药节点的判定归属；"
        "time_words 是逐段连续原文组成的数组；无明确时间措辞填空数组，"
        "同一动作有多段时间措辞时分别摘录，不能用分号拼成非原文字串，也不可借用另一动作的时长；"
        "每项时间措辞须出现在本条 quoted_text 或所属标题中，不可借同段另一句的时长；"
        "时间、例外、阶段有歧义时保留 unresolved，"
        "表格项目行的 X 应按 member_cell_paths 列位置与同表前置访视行核对，"
        "不可按压缩后的 X 文本顺序推断访视；无法对应时明确写 unresolved。"
        "不得猜测。确实无独立陈述的单元放 units_without_statement。每个 owned 单元必须覆盖。"
        "只返回一个 JSON 对象，字段结构为："
        '{"version":"phase5/control-source-interpretation/v5",'
        '"statements":[{"structure_unit_id":"来源单元ID","quoted_text":"逐字原文",'
        '"force":"required|prohibited|recommended|descriptive|unclear",'
        '"affected_stage":null,"time_words":[], '
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
