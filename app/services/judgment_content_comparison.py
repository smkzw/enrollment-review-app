"""Compare two source-bound content checks without issuing clinical permission."""
from app.domain.contracts.judgment_content import JUDGMENT_CONTENT_VERSION
from app.domain.publication import canonical_hash
from app.llm.judgment_content import (
    JudgmentContentRead, build_judgment_content_messages, validate_judgment_content_payload,
)


def compare_judgment_content(pairs, batch, reads: tuple[JudgmentContentRead, JudgmentContentRead]):
    if len(reads) != 2 or {read.lane for read in reads} != {"main-A", "main-B"}:
        raise ValueError("判断内容比较需要本次两个独立主读结果")
    identities = {(read.frozen_input_sha256, read.batch_sha256, read.messages_sha256)
                  for read in reads}
    expected = (batch.frozen_input_sha256, batch.batch_sha256,
                canonical_hash(build_judgment_content_messages(pairs, batch)))
    if identities != {expected}:
        raise ValueError("判断内容比较不能混用不同输入或不同提示的结果")
    if len({(read.requested_provider, read.requested_model) for read in reads}) != 2:
        raise ValueError("判断内容比较不能将同一模型重复调用当作两个独立模型")
    indexed = {}
    for read in reads:
        payload = validate_judgment_content_payload(pairs, read.payload.model_dump_json())
        indexed[read.lane] = {item.pair_id: item for item in payload.results}
    records = []
    for pair in sorted(pairs, key=lambda item: item.pair_id):
        left, right = (indexed[lane][pair.pair_id] for lane in ("main-A", "main-B"))
        if left.agreement_key() != right.agreement_key():
            status = "disagreement"
        elif all(value == "supported" for value in left.agreement_key()):
            status = "content_supported"
        elif "rejected" in left.agreement_key():
            status = "content_rejected"
        else:
            status = "unresolved"
        records.append({
            "pair_id": pair.pair_id,
            "status": status,
            "lanes": {lane: indexed[lane][pair.pair_id].model_dump(mode="json")
                      for lane in ("main-A", "main-B")},
        })
    first = reads[0]
    material = {
        "version": JUDGMENT_CONTENT_VERSION,
        "frozen_input_sha256": first.frozen_input_sha256,
        "batch_sha256": first.batch_sha256,
        "messages_sha256": first.messages_sha256,
        "records": records,
    }
    return {**material, "comparison_sha256": canonical_hash(material)}
