"""Explicit identifiers for observations accepted by a page reconciliation."""

from app.domain.contracts.page_review import EvidenceSignal
from app.domain.publication import canonical_hash
import unicodedata


def _literal_text(value):
    return "".join(unicodedata.normalize("NFKC", value or "").split())


def accepted_observations(reviews, reconciliation, *, include_clause_signals=True):
    result = []
    for review in reviews:
        for kind in ("facts", "handwriting", "clause_signals"):
            if kind == "clause_signals" and not include_clause_signals:
                continue
            for index, observation in enumerate(getattr(review, kind)):
                if kind == "clause_signals" and observation.signal == EvidenceSignal.NONE:
                    continue
                accepted = (
                    observation.normalization_key in reconciliation.accepted_fact_keys if kind == "facts"
                    else observation in reconciliation.accepted_handwriting if kind == "handwriting"
                    else observation in reconciliation.accepted_clause_signals
                )
                if accepted:
                    ref = "page-observation:" + canonical_hash({
                        "review_id": review.page_review_id, "kind": kind, "index": index,
                    })
                    result.append({"source_observation_ref": ref, "kind": kind,
                                   "observation": observation.model_dump(mode="json")})
    return result


def validate_accepted_candidate_sources(output, attachment, *, locator_inputs=()):
    if attachment is None:
        return
    reviews = {review.page_review_id: review for review in attachment.reviews}
    accepted = {}
    origins = {}
    for reconciliation in attachment.reconciliations:
        for key in reconciliation.page_review_ids:
            review = reviews[key]
            for item in accepted_observations([review], reconciliation,
                    include_clause_signals=getattr(attachment, "visual_source_policy", None) is None):
                accepted[item["source_observation_ref"]] = (
                    review.page_number, _literal_text(item["observation"]["region"]["excerpt"]))
                origins[item["source_observation_ref"]] = (
                    key, item["kind"], item["observation"]["region"]["excerpt"])
    locator_pages = {item.locator_id: item.page_number for item in locator_inputs}
    locator_texts = {item.locator_id: _literal_text(item.localized_text) for item in locator_inputs}
    locators = {item.locator_id: item for item in locator_inputs}
    for candidate in output.fact_candidates:
        if not candidate.source_observation_refs or not set(candidate.source_observation_refs) <= accepted.keys():
            raise ValueError("事实候选必须引用本次已采信观察，不得引用待核对或其他资料")
        source_pages = {accepted[ref][0] for ref in candidate.source_observation_refs}
        if (any(key not in locator_pages for key in candidate.locator_ids)
                or {locator_pages[key] for key in candidate.locator_ids} != source_pages):
            raise ValueError("事实候选的原件定位页必须与所引用观察的来源页一致")
        for key in candidate.locator_ids:
            binding = getattr(locators[key], "page_review_visual", None)
            if binding is not None and (
                binding.coverage_id != attachment.coverage_id
                or not any(
                    origins[ref][0] == binding.page_review_id
                    and origins[ref][1] in {"facts", "handwriting"}
                    and origins[ref][2] == locators[key].localized_text
                    for ref in candidate.source_observation_refs
                )
            ):
                raise ValueError("视觉定位必须对应本次所引用的已核实观察")
        for ref in candidate.source_observation_refs:
            page, excerpt = accepted[ref]
            review_id, kind, original_excerpt = origins[ref]
            visual_match = any(
                (binding := getattr(locators[key], "page_review_visual", None)) is not None
                and binding.coverage_id == attachment.coverage_id
                and binding.page_review_id == review_id
                and kind in {"facts", "handwriting"}
                and locators[key].localized_text == original_excerpt
                for key in candidate.locator_ids
            )
            if visual_match:
                continue
            if not excerpt or not any(
                getattr(locators[key], "page_review_visual", None) is None
                and locator_pages[key] == page and excerpt in locator_texts[key]
                for key in candidate.locator_ids
            ):
                raise ValueError(
                    "已采信观察的摘录无法在所选原件定位中核对："
                    f"候选={getattr(candidate, 'candidate_id', '未提供')}；"
                    f"观察={ref}；第{page}页；摘录={excerpt[:240]}。"
                    "请从输入中选择确有原文支持的观察及对应定位；"
                    "不要把带省略号的拼接摘录当作连续原句。"
                    "若没有其他独立、已采信且可定位的来源，须在未解决项保留该内容，"
                    "不得生成无来源的事实或省略问题。"
                )
