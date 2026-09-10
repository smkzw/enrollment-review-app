"""Deterministic retention of unresolved page reads alongside normalizer output.

把冻结的 ``EvidenceNormalizerInput`` 页级判读附件中所有未解决观察投影为
确定性的 ``EvidenceNormalizerUnresolvedItem``：既覆盖部分采信/部分待核对
的混合页，也覆盖全部待核对页。原始摘录、读数/手写原文与原文关联按输入
原样保留；不做临床推断、不新增事实、不虚构定位，也不做缺口方向归类。

- 无页级判读附件（旧调用）或全部采信页不产生任何记录；
- 不同判读记录中的观察分别保留，文字一致不代表来源或事实已核实；
- 每页汇总为一条未解决项，``reason`` 以固定标签、固定顺序逐条列出原文
  内容，是确定性的结构化序列化，避免上百张界面卡片。工程主键（观察编号、
  归一化键、读道编号等）不出现在用户文本；派生值（归一化值/单位/键）不
  属于原文，仍保留在源页级判读记录中，不进入本报告。几何信息与完整观察
  载荷以源记录为唯一事实来源。
"""

import json

from app.domain.contracts.evidence_normalizer import (
    EvidenceNormalizerInput,
    EvidenceNormalizerUnresolvedItem,
)
from app.projections.page_review_pending import pending_page_observations

PENDING_RETENTION_CODE = "page_observation_unverified"

_POLARITY_LABELS = {
    "asserted": "肯定表述",
    "negated": "否定表述",
    "uncertain": "不确定表述",
    "not_stated": "未写明肯定或否定",
}

_HANDWRITING_LABELS = {
    "signature_initials_date": "签名、缩写或日期",
    "cs_ncs_judgment": "CS/NCS 判断",
    "note": "手写备注",
    "table_cell": "手写表格内容",
    "other": "其他手写内容",
}

_CONTEXT_LABELS = (
    ("target_text", "所指对象"),
    ("time_text", "时间原文"),
    ("location_text", "位置原文"),
)

# 只保留原文内容字段；normalized_value/normalization_key 等派生值不进入报告，
# 待核对的读不得充当规范化候选值。
_FACT_FIELDS = ("field_name", "raw_value", "raw_text")


def _retained_content(kind: str, observation: dict) -> dict:
    content = {"excerpt": observation["region"]["excerpt"],
               "raw_text": observation["raw_text"]}
    if kind == "facts":
        for field in _FACT_FIELDS:
            content[field] = observation[field]
    else:
        content["kind"] = observation["kind"]
    if observation.get("context") is not None:
        content["context"] = observation["context"]
    return content


def _identity(pending: dict, content: dict) -> str:
    return json.dumps({"page_review_id": pending["page_review_id"],
                      "observation_id": pending["observation"]["observation_id"],
                      "content": content, "kind": pending["kind"],
                      "message": pending["review_message"]},
                      ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _entry_text(kind: str, content: dict, message: str) -> str:
    if kind == "facts":
        head = (f"字段「{content['field_name']}」读数原文「{content['raw_value']}」"
                f"，记录原文「{content['raw_text']}」")
    else:
        label = _HANDWRITING_LABELS.get(content["kind"], content["kind"])
        head = f"手写类别「{label}」，手写原文「{content['raw_text']}」"
    parts = [head, f"原文摘录「{content['excerpt']}」"]
    context = content.get("context") or {}
    parts += [f"{label}「{context[key]}」" for key, label in _CONTEXT_LABELS if context.get(key)]
    if context.get("polarity"):
        parts.append(
            f"原文标注「{_POLARITY_LABELS.get(context['polarity'], context['polarity'])}」")
    parts.append(f"待核对原因「{message}」")
    return "，".join(parts)


def pending_retention_items(
    evidence_input: EvidenceNormalizerInput,
) -> list[EvidenceNormalizerUnresolvedItem]:
    """把输入中所有未解决页级观察保留为确定性未解决项；不改写输入。"""
    attachment = evidence_input.page_review
    if attachment is None:
        return []
    reviews = {item.page_review_id: item for item in attachment.reviews}
    records: dict[tuple[str, int, str], tuple[str, dict, str]] = {}
    for reconciliation in attachment.reconciliations:
        lane_reviews = [reviews[key] for key in reconciliation.page_review_ids]
        for pending in pending_page_observations(lane_reviews, reconciliation):
            kind = pending["kind"]
            content = _retained_content(kind, pending["observation"])
            message = pending["review_message"]
            key = (pending["source_document_version_id"], pending["page_number"],
                   _identity(pending, content))
            records.setdefault(key, (kind, content, message))
    by_page: dict[tuple[str, int], list[tuple[str, dict, str]]] = {}
    for key in sorted(records):
        by_page.setdefault((key[0], key[1]), []).append(records[key])
    items = []
    for (_source_document_version_id, page_number), entries in sorted(by_page.items()):
        listing = "；".join(
            f"{index}．{_entry_text(kind, content, message)}"
            for index, (kind, content, message) in enumerate(entries, 1)
        )
        items.append(EvidenceNormalizerUnresolvedItem(
            code=PENDING_RETENTION_CODE,
            message=f"第{page_number}页有{len(entries)}条内容尚待核对，原文已保留。",
            affected_pages=[page_number],
            reason=(
                f"第{page_number}页有尚未核实的内容，以下保留各条原文，供后续核对；"
                "这不代表已确认的病史，也不代表符合或不符合入排标准。"
                f"待核对原文：{listing}。"
            ),
        ))
    return items
