"""Bounded, source-only inquiry for unresolved protocol semantic points."""

from __future__ import annotations

import json
import unicodedata
from hashlib import sha256
from typing import Literal

from pydantic import Field, model_validator

from app.domain.contracts.common import ContractModel
from app.domain.contracts.protocol_controls import ProtocolStructureUnit

from .protocol_control_semantic_point import BoundSemanticPoint


INQUIRY_PLAN_VERSION = "phase5/control-semantic-inquiry-plan/v2"
INQUIRY_RESULT_VERSION = "phase5/control-semantic-inquiry-result/v3"


class SourceInquiryPlan(ContractModel):
    version: Literal[INQUIRY_PLAN_VERSION]
    queries: list[str] = Field(default_factory=list, max_length=2)
    read_structure_unit_ids: list[str] = Field(default_factory=list, max_length=3)
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_bounded_lookup(self):
        if not self.queries and not self.read_structure_unit_ids:
            raise ValueError("原文核查须提出搜索或明确来源单元")
        if any(len(query.strip()) < 2 or len(query) > 80 for query in self.queries):
            raise ValueError("搜索线索须是简短的原文词组")
        if len(self.queries) != len(set(self.queries)) or len(self.read_structure_unit_ids) != len(set(self.read_structure_unit_ids)):
            raise ValueError("原文核查不得重复相同请求")
        return self


class InquirySource(ContractModel):
    structure_unit_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    heading_path: list[str]
    excerpt: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    truncated: bool


class InquiryCitation(ContractModel):
    structure_unit_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class InquiryPointResult(ContractModel):
    semantic_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["source_cited_proposal", "remains_unknown"]
    proposed_clarification: str = Field(min_length=1)
    citations: list[InquiryCitation] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_citation_for_claim(self):
        if self.status == "source_cited_proposal" and not self.citations:
            raise ValueError("提出核查意见须给出逐字原文")
        return self


class SourceInquiryResult(ContractModel):
    version: Literal[INQUIRY_RESULT_VERSION]
    point_results: list[InquiryPointResult] = Field(min_length=1)


def _compact(text: str) -> str:
    return "".join(unicodedata.normalize("NFKC", text).split()).casefold()


def _source_digest(unit: ProtocolStructureUnit) -> str:
    return sha256(json.dumps(
        unit.model_dump(mode="json"), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def inquiry_plan_response_format() -> dict[str, object]:
    return {"type": "json_schema", "json_schema": {
        "name": "protocol_control_semantic_inquiry_plan_v2", "strict": True,
        "schema": SourceInquiryPlan.model_json_schema(),
    }}


def inquiry_result_response_format() -> dict[str, object]:
    return {"type": "json_schema", "json_schema": {
        "name": "protocol_control_semantic_inquiry_result_v3", "strict": True,
        "schema": SourceInquiryResult.model_json_schema(),
    }}


def build_inquiry_plan_prompt(points: list[BoundSemanticPoint]) -> str:
    if not points or any(point.capability != "unresolved" for point in points):
        raise ValueError("仅能为尚未核清的来源点查原文")
    visible = [{
        "semantic_id": point.semantic_id,
        "structure_unit_id": point.structure_unit_id,
        "source_ref": point.source_ref,
        "quoted_text": point.exact_quote,
        "proposition": point.proposition,
        "unresolved_dimensions": point.unresolved_dimensions,
    } for point in points]
    return (
        "你是本系统内置方案Agent的有界原文查阅步骤，不决定入排、不改规则。"
        "根据未核清的具体问题，至多提出两个短搜索词组和三个已知来源单元ID；"
        "多个关键词用空格分隔，优先选能在方案不同章节查到定义或执行说明的词，"
        "不要把整句问题当作一个必须连续出现的检索词。"
        "可只读同一原文，也可搜索方案别处的定义、限制或例外。"
        "只能查本次上传方案的冻结来源，不能要求网络、外部指南、病例或数据库写入。"
        "搜索词用于找候选，不代表答案；找不到依据时仍须保留未决。"
        "只返回指定JSON。\n待核来源："
        + json.dumps(visible, ensure_ascii=False, sort_keys=True)
    )


def materialize_inquiry_sources(
    plan: SourceInquiryPlan,
    units: list[ProtocolStructureUnit],
    *,
    max_sources: int = 8,
    max_excerpt_chars: int = 4000,
) -> list[InquirySource]:
    """Search only the frozen protocol inventory, never an external corpus."""

    if max_sources < 1 or max_excerpt_chars < 1:
        raise ValueError("原文查阅预算无效")
    by_id = {unit.structure_unit_id: unit for unit in units}
    if len(by_id) != len(units) or not set(plan.read_structure_unit_ids) <= set(by_id):
        raise ValueError("要求读取的来源单元不属于当前冻结方案")
    if len(plan.read_structure_unit_ids) > max_sources:
        raise ValueError("明确指定的来源单元超过本次查阅上限，不能静默省略")
    chosen = [by_id[unit_id] for unit_id in plan.read_structure_unit_ids]
    seen = set(plan.read_structure_unit_ids)
    seen_headings = {tuple(unit.heading_path) for unit in chosen}
    ranked_queries = []
    for query in plan.queries:
        terms = [_compact(term) for term in query.split()]
        ranked = []
        for unit in units:
            content = _compact(" ".join([*unit.heading_path, unit.excerpt]))
            matched = sum(term in content for term in terms)
            if matched:
                ranked.append((matched, _compact(query) in content, unit))
        if ranked:
            best = max(item[0] for item in ranked)
            ranked_queries.append([
                unit for matched, exact, unit in sorted(
                    (item for item in ranked if item[0] >= max(1, best - 1)),
                    key=lambda item: (-item[1], -item[0], -min(len(item[2].excerpt), 256),
                                      item[2].source_order, item[2].structure_unit_id),
                )
            ])
    for distinct_heading in (True, False):
        while len(chosen) < max_sources:
            added = False
            for ranked in ranked_queries:
                unit = next((item for item in ranked if item.structure_unit_id not in seen
                             and (not distinct_heading or tuple(item.heading_path) not in seen_headings)), None)
                if unit is None:
                    continue
                chosen.append(unit)
                seen.add(unit.structure_unit_id)
                seen_headings.add(tuple(unit.heading_path))
                added = True
                if len(chosen) == max_sources:
                    break
            if not added:
                break
    return [InquirySource(
        structure_unit_id=unit.structure_unit_id,
        source_ref=unit.source_ref,
        heading_path=list(unit.heading_path),
        excerpt=unit.excerpt[:max_excerpt_chars],
        source_sha256=_source_digest(unit),
        truncated=len(unit.excerpt) > max_excerpt_chars,
    ) for unit in chosen[:max_sources]]


def build_inquiry_result_prompt(
    points: list[BoundSemanticPoint], sources: list[InquirySource],
) -> str:
    if not points:
        raise ValueError("没有待核来源点")
    return (
        "你是本系统内置方案Agent的局部关系核查步骤，不生成新规则或受试者结论。"
        "只回答每个已列语义点原先未核清的范围；逐字引用本次呈现的冻结原文。"
        "同一段中后置括号可能约束多条，也可能只约束最近一条；须看完整语法和章节，"
        "不能只因文字相邻就判定适用。访视日程的X也不自动证明入排作用。"
        "有依据的解释也只标 source_cited_proposal，不代表已经通过临床语义核对；"
        "找不到足以区分解释的原文，或任何关键原文被截断时，status 为 remains_unknown。"
        "不得把查到的其他来源冒充原条目的逐字原文；只能提出核对意见，原语义点不自动改写。"
        "只返回指定JSON。\n待核点："
        + json.dumps([point.model_dump(mode="json") for point in points], ensure_ascii=False, sort_keys=True)
        + "\n查得原文："
        + json.dumps([source.model_dump(mode="json") for source in sources], ensure_ascii=False, sort_keys=True)
    )


def verify_inquiry_result(
    result: SourceInquiryResult,
    points: list[BoundSemanticPoint],
    sources: list[InquirySource],
) -> SourceInquiryResult:
    """Verify provenance, not the model's clinical interpretation."""

    expected = {point.semantic_id for point in points}
    actual = [item.semantic_id for item in result.point_results]
    if set(actual) != expected or len(actual) != len(set(actual)):
        raise ValueError("核查回答未逐项对应原先未决语义点")
    by_id = {source.structure_unit_id: source for source in sources}
    for item in result.point_results:
        for citation in item.citations:
            source = by_id.get(citation.structure_unit_id)
            if source is None or citation.quote not in source.excerpt:
                raise ValueError("核查引文不属于本次查得原文")
            if item.status == "source_cited_proposal" and source.truncated:
                raise ValueError("来源正文未完整呈现，不能提出完整范围的核查意见")
    return result
