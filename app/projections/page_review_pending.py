"""Source-bound unresolved observations, separate from accepted clinical facts."""

from collections.abc import Sequence
from collections import defaultdict
import hashlib

from app.domain.contracts.page_review import PageReconciliation, PageReviewRecord
from app.domain.page_normalization import normalize_field_name, observation_context_key, source_arrow_marks


def _fact_review_status(review, observation, reviews):
    """Describe unresolved reads without promoting them to clinical conflicts."""
    others = [item for item in reviews if item.lane.value in {"main-A", "main-B"}
              and item.lane != review.lane
              and (item.page_artifact_id, item.page_image_sha256, item.source_document_version_id,
                   item.page_number, item.clause_pack_sha256)
              == (review.page_artifact_id, review.page_image_sha256, review.source_document_version_id,
                  review.page_number, review.clause_pack_sha256)]
    if not others:
        return "association_pending", "另一处判读尚待核对"
    if all(not item.facts for item in others):
        return "single_source", "目前仅一处判读记录此项，尚未确认"
    if observation.context is not None:
        identity = (normalize_field_name(observation.field_name),
                    observation_context_key(observation.context.model_dump()))
        matches = [fact for item in others for fact in item.facts
                   if fact.context is not None and
                   (normalize_field_name(fact.field_name),
                    observation_context_key(fact.context.model_dump())) == identity]
        if len(matches) == 1 and (matches[0].normalized_value, matches[0].normalized_unit) != (
                observation.normalized_value, observation.normalized_unit):
            return "read_value_disagreement", "同一对象的原文读值不一致，请核对原件"
        if len(matches) == 1 and source_arrow_marks(matches[0].raw_value) != source_arrow_marks(observation.raw_value):
            return "read_annotation_disagreement", "同一对象的原件异常标记读法不一致，请核对原件；不代表临床意义判断"
    return "association_pending", "两处判读的对应关系尚待核对"


def _unique_text_anchor(text: str, excerpt: str):
    start = text.find(excerpt) if excerpt else -1
    if start < 0 or text.find(excerpt, start + 1) >= 0:
        return None
    return {"source_layer": "effective_text", "source_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "text_start": start, "text_end": start + len(excerpt), "excerpt": excerpt}


def pending_page_observations(reviews: Sequence[PageReviewRecord], reconciliation: PageReconciliation,
                              *, page_texts=None) -> list[dict]:
    accepted = {
        "facts": set(reconciliation.accepted_fact_keys),
        "handwriting": {item.normalization_key for item in reconciliation.accepted_handwriting},
    }
    pending = []
    for review in reviews:
        for kind, keys in accepted.items():
            for observation in getattr(review, kind):
                if observation.normalization_key in keys:
                    continue
                status, message = (_fact_review_status(review, observation, reviews)
                                   if kind == "facts" else
                                   ("association_pending", "手写内容及所指对象尚待核对"))
                text = (page_texts or {}).get((review.source_document_version_id, review.page_number), "")
                anchor = _unique_text_anchor(text, observation.region.excerpt)
                pending.append({
                    "page_review_id": review.page_review_id,
                    "lane": review.lane.value,
                    "page_artifact_id": review.page_artifact_id,
                    "source_document_version_id": review.source_document_version_id,
                    "page_number": review.page_number,
                    "kind": kind,
                    "observation": observation.model_dump(mode="json"),
                    "use": "unresolved_only",
                    "review_status": status,
                    "review_message": message,
                    "text_anchor": anchor,
                })
    passages = defaultdict(list)
    for item in pending:
        anchor = item["text_anchor"]
        if anchor is not None and item["lane"] in {"main-A", "main-B"}:
            key = (item["source_document_version_id"], item["page_number"], item["kind"],
                   anchor["source_text_sha256"], anchor["text_start"], anchor["text_end"])
            passages[key].append(item)
    for items in passages.values():
        if len(items) == 2 and {item["lane"] for item in items} == {"main-A", "main-B"}:
            for item, other in ((items[0], items[1]), (items[1], items[0])):
                item["same_source_passage"] = {
                    "page_review_id": other["page_review_id"],
                    "observation_id": other["observation"]["observation_id"],
                    "meaning": "仅表示同一原文范围，不表示事实一致",
                }
    return pending
