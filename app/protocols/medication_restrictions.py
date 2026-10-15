"""One selected source union; proposals never manufacture official IN/EX rules."""
import re
from pydantic import Field

from app.domain.contracts.common import ContractModel
from app.domain.contracts.rules import (MedicationRestriction, MedicationSourceDisposition,
    ProhibitedMedicationItem, ProtocolScopeQuote, ProtocolScopeSection, ProtocolScopeSupplement, TimeUnit)
from app.domain.publication import canonical_hash
from app.domain.variables.dictionary import load_drug_classes
from app.protocols.deconstruction_gate import _numeric_tokens, _numeric_value_in_tokens, _time_bound_matches_source

ANCHOR_WORDS = {"icf_date": ("知情同意", "ICF"), "screening_date": ("筛选",), "baseline_date": ("基线",),
    "randomization_date": ("随机",), "first_dose_date": ("首次给药", "首剂", "第一次给药"),
    "study_drug_administration_date": ("研究药物给药", "试验药物给药"), "last_dose_date": ("末次给药", "最后一次给药"),
    "study_completion_date": ("研究完成", "研究结束"), "event_date": ("事件发生",), "review_node_date": ("当前审核节点", "本审核节点")}


class MedicationRestrictionProposal(ContractModel):
    medications: list[MedicationRestriction] = Field(default_factory=list)
    source_dispositions: list[MedicationSourceDisposition] = Field(default_factory=list)


class MedicationProposalError(ValueError):
    def __init__(self, message: str, *, item_index: int):
        self.item_index = item_index
        super().__init__(message)


def scope_selection_hash(selection):
    return canonical_hash(selection.model_dump(mode="json", exclude={"saved_at", "saved_by"}))


def scope_supplement_pending(revision):
    selection = revision.review_scope_selection
    supplement = revision.content.scope_supplement
    return selection is not None and (supplement is None
        or supplement.selection_sha256 != scope_selection_hash(selection))


def selected_scope_material(view, selection):
    if selection is None or selection.scope_content_hash != view["scope_content_hash"]:
        raise ValueError("请先保存与当前原文一致的范围选择。")
    included = set(selection.included_candidate_keys)
    sections = [ProtocolScopeSection(scope_kind=row["scope_kind"], source_span_ids=row["source_span_ids"],
        official_codes=row["official_codes"]) for row in view["candidates"] if row["candidate_key"] in included]
    sections.extend(ProtocolScopeSection(scope_kind=row.scope_kind, source_span_ids=row.source_span_ids,
        official_codes=row.official_codes) for row in selection.additions)
    records = {row["source_span_id"]: row for row in [*view["source_records"], *view["additional_source_records"]]}
    selected_ids = list(dict.fromkeys(key for section in sections for key in section.source_span_ids))
    sources = []
    for key in selected_ids:
        row = records.get(key)
        if row is None or row["identity_status"] != "ok":
            raise ValueError("补充范围有尚未核清的原文位置。")
        sources.append(ProtocolScopeQuote(source_span_id=key, excerpt=row["raw_text"]))
    medication_ids = set(key for section in sections if section.scope_kind == "medication_section" for key in section.source_span_ids)
    # Empty native paragraphs remain in scope; only nonempty text needs semantic disposition.
    readable = [row for row in sources if row.source_span_id in medication_ids and row.excerpt.strip()]
    return sections, sources, readable


def medication_input_hash(phase, readable, drug_classes=None):
    return canonical_hash({"phase": str(phase), "sources": [row.model_dump(mode="json") for row in readable],
                           "drug_classes": load_drug_classes() if drug_classes is None else drug_classes})


def build_scope_supplement(*, proposal, view, selection, phase, official_codes, receipts=(), drug_classes=None):
    sections, sources, readable = selected_scope_material(view, selection)
    texts = {row.source_span_id: row.excerpt for row in readable}
    covered = set()
    items = []
    classes = load_drug_classes() if drug_classes is None else drug_classes
    for index, restriction in enumerate(proposal.medications):
        window = restriction.window
        if (window is not None and window.lower_bound_days == 0 and window.lower_bound_inclusive
                and (window.upper_bound is not None or window.upper_bound_days is not None)):
            # A closed zero distance adds no restriction to a bounded before/after window.
            restriction = restriction.model_copy(update={"window": window.model_copy(update={"lower_bound_days": None})})
        for quote in restriction.source_quotes:
            if quote.source_span_id not in texts or quote.excerpt not in texts[quote.source_span_id]:
                raise MedicationProposalError("用药限制的摘录不在所选原文位置内。", item_index=index)
            covered.add(quote.source_span_id)
        quoted = "\n".join(quote.excerpt for quote in restriction.source_quotes)
        if restriction.drug_text not in quoted:
            raise MedicationProposalError("药物或治疗名称必须保留原文写法。", item_index=index)
        if restriction.exception_excerpt and restriction.exception_excerpt not in quoted:
            raise MedicationProposalError("例外内容须逐字保留在本条原文中。", item_index=index)
        source_texts = [texts[quote.source_span_id] for quote in restriction.source_quotes]
        own_exception = any(
            re.search(re.escape(restriction.drug_text) + r"\s*[（(][^）)]*(?:除外|例外)[^）)]*[）)]", text)
            or (restriction.drug_text in text and not re.search(r"[、，,]|\b(?:or|and)\b|或", text)
                and re.search(r"除外|例外|除[^。；\n]{1,80}外", text))
            for text in source_texts)
        if (own_exception and not restriction.exception_excerpt and not restriction.unresolved_reason):
            raise MedicationProposalError("本条原文有例外，尚未保留其内容或明确未决。", item_index=index)
        if restriction.period is not None:
            markers = {"study_period": ("研究期间", "试验期间", "整个研究", "整个试验"),
                       "treatment_period": ("治疗期间", "治疗期内", "治疗期")}[restriction.period.value]
            if not any(marker in quoted for marker in markers):
                raise MedicationProposalError("整个适用期间不能对应本条原文，不得把局部时间窗扩大。", item_index=index)
        if restriction.drug_class_id is not None and restriction.drug_class_id not in classes:
            raise MedicationProposalError("药物类别不在现有类别表内，不能猜测类别身份。", item_index=index)
        if restriction.applies_to_rule and restriction.applies_to_rule not in official_codes:
            raise MedicationProposalError("关联的入排条款不属于当前方案。", item_index=index)
        window = restriction.window
        if window is not None:
            direction = {"before": "前", "after": "后", "on": "(?:时|当日|当天)"}[window.direction.value]
            if not any(re.search(re.escape(word) + r"(?:期|访视|日期|日|书|开始|的|之){0,3}" + direction, quoted, re.IGNORECASE)
                       for word in ANCHOR_WORDS[window.anchor_type.value]):
                raise MedicationProposalError("时间起点或前后方向不能对应本条原文，不能借用默认节点。", item_index=index)
            if window.half_life_evidence is not None:
                raise MedicationProposalError("本次只整理方案要求，不得从模型常识补入药物半衰期依据。", item_index=index)
            bounds = [(window.lower_bound_days, TimeUnit.DAY), (window.upper_bound_days, TimeUnit.DAY)]
            bounds += [(value.value, value.unit) for value in (window.lower_bound, window.upper_bound) if value]
            if any(value is not None and not _time_bound_matches_source(value, unit, quoted) for value, unit in bounds):
                raise MedicationProposalError("洗脱时间的数量或单位不能对应本条原文。", item_index=index)
            if window.half_life_multiplier and not _numeric_value_in_tokens(window.half_life_multiplier, _numeric_tokens(quoted)):
                raise MedicationProposalError("半衰期倍数不能对应本条原文。", item_index=index)
        payload = restriction.model_dump(mode="json")
        items.append(ProhibitedMedicationItem(**payload, item_id="med:" + canonical_hash(payload)[:24]))
    dispositions = proposal.source_dispositions
    ids = [row.source_span_id for row in dispositions]
    # A permission can also supply exception context. This does not make the
    # exception's clinical scope verified; it remains visible for rule review.
    invalid_overlap = any(row.source_span_id in covered and (row.disposition != "permission" or
        any(not (item.exception_excerpt or item.unresolved_reason) for item in items
            if any(quote.source_span_id == row.source_span_id for quote in item.source_quotes)))
        for row in dispositions)
    if len(ids) != len(set(ids)) or set(ids) - set(texts) or invalid_overlap:
        raise ValueError("用药原文处置重复、越界或与已有条目冲突。")
    if covered | set(ids) != set(texts):
        raise ValueError("所选用药原文尚有未处理位置，不能用部分成功冒充完成。")
    return ProtocolScopeSupplement(selection_sha256=scope_selection_hash(selection),
        input_sha256=medication_input_hash(phase, readable, classes), structure_sha256=view["structure_sha256"],
        sections=sections, sources=sources, drug_classes=classes, medications=items, source_dispositions=dispositions,
        request_refs=[row["request_ref"] for row in receipts],
        response_refs=[row["response_ref"] for row in receipts if row.get("response_ref")])


def validate_scope_supplement(supplement, *, view, selection, phase, official_codes):
    proposal = MedicationRestrictionProposal(medications=[MedicationRestriction.model_validate(
        item.model_dump(exclude={"item_id"})) for item in supplement.medications],
        source_dispositions=supplement.source_dispositions)
    expected = build_scope_supplement(proposal=proposal, view=view, selection=selection,
        phase=phase, official_codes=official_codes, drug_classes=supplement.drug_classes)
    if supplement.model_dump(exclude={"request_refs", "response_refs", "reader_identity"}) != expected.model_dump(exclude={"request_refs", "response_refs", "reader_identity"}):
        raise ValueError("补充要求与当前范围、原文或条目身份不一致。")
