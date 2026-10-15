"""One-point revision of an isolated source-semantic reading."""

from __future__ import annotations

import json

from app.domain.contracts.protocol_controls import ProtocolControlDispositionBatch
from app.domain.publication import canonical_hash

from .protocol_control_semantic_point import SourceSemanticPacket, SourceSemanticPoint
from .protocol_control_source_interpretation import SourceInterpretation


def semantic_point_precondition(point: SourceSemanticPoint) -> str:
    return canonical_hash(point.model_dump(mode="json"))


def build_semantic_point_repair_prompt(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    packet: SourceSemanticPacket,
    *,
    statement_index: int,
    point_key: str,
    issue: str,
    visible_indexes: list[int],
) -> str:
    matches = [point for point in packet.items
               if (point.statement_index, point.point_key) == (statement_index, point_key)]
    if len(matches) != 1 or statement_index not in visible_indexes:
        raise ValueError("局部修订目标不属于本次来源语义包")
    if len(visible_indexes) != len(set(visible_indexes)) or any(
        index < 0 or index >= len(interpretation.statements) for index in visible_indexes
    ):
        raise ValueError("局部修订的可读原文范围无效")
    units = {unit.structure_unit_id: unit for unit in batch.owned_units}
    sources = []
    for index in visible_indexes:
        statement = interpretation.statements[index]
        unit = units.get(statement.structure_unit_id)
        if unit is None:
            raise ValueError("局部修订不能读取本批以外的来源单元")
        sources.append({
            "statement_index": index,
            "statement": statement.model_dump(mode="json"),
            "source_ref": unit.source_ref,
            "source_span_ids": unit.source_span_ids,
            "heading_path": unit.heading_path,
            "excerpt": unit.excerpt,
        })
    siblings = [
        {"statement_index": point.statement_index, "point_key": point.point_key,
         "proposition": point.proposition}
        for point in packet.items if point is not matches[0]
    ]
    material = {
        "target": matches[0].model_dump(mode="json"),
        "precondition_sha256": semantic_point_precondition(matches[0]),
        "issue": issue[:1200],
        "sources": sources,
        "other_points_read_only": siblings,
    }
    return (
        "你是内置方案 Agent 的单个语义点核对步骤，不判断受试者，不发布规则。"
        "只返回符合所附 JSON Schema 的 SourceSemanticPacket，items 恰为一个修订点；"
        "其 statement_index 和 point_key 与 target 完全相同，不输出或改写其他点。"
        "错误说明只是定位线索，须重读冻结原文判断；计算操作、输入选择、缺失政策"
        "可分别由不同语义点承担，不能因同句就复制成多个无输入的计算。"
        "每个计算输入、例外与依赖必须有相应逐字来源；不能确认时保留未核清维度，"
        "不要删除真实限制、补数值或补时点来使结构通过。其他点仅供理解依赖，"
        "本次修订不能改变它们。只返回 JSON。\n"
        + json.dumps(material, ensure_ascii=False, sort_keys=True)
    )


def apply_semantic_point_replacement(
    packet: SourceSemanticPacket,
    replacement: SourceSemanticPacket,
    *,
    statement_index: int,
    point_key: str,
    precondition_sha256: str,
) -> SourceSemanticPacket:
    matches = [point for point in packet.items
               if (point.statement_index, point.point_key) == (statement_index, point_key)]
    if len(matches) != 1 or semantic_point_precondition(matches[0]) != precondition_sha256:
        raise ValueError("语义点修订的原版本已变化，不能合并")
    if len(replacement.items) != 1 or (
        replacement.items[0].statement_index, replacement.items[0].point_key
    ) != (statement_index, point_key):
        raise ValueError("局部修订只能替换指定的一个语义点")
    return SourceSemanticPacket(
        version=packet.version,
        items=[replacement.items[0] if point is matches[0] else point
               for point in packet.items],
    )
