"""Exact source-position matching; no fuzzy or clinical inference."""

from collections import defaultdict
from collections.abc import Sequence
import hashlib
import unicodedata

from pydantic import Field, model_validator

from app.domain.contracts.common import ContractModel
from app.domain.contracts.page_review import PageFactObservation, PageReviewLane, PageReviewRecord
from app.domain.page_normalization import normalize_field_name, normalize_text, observation_context_key, source_arrow_marks


class PageAssociationSource(ContractModel):
    source_document_version_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    text: str
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def verify_text(self):
        if hashlib.sha256(self.text.encode()).hexdigest() != self.text_sha256:
            raise ValueError("来源关联文本与冻结哈希不一致")
        return self


def _positioned_text(text: str) -> tuple[str, list[int]]:
    chars, offsets = [], []
    for offset, character in enumerate(text):
        for normalized in unicodedata.normalize("NFKC", character):
            if not normalized.isspace():
                chars.append(normalized)
                offsets.append(offset)
    return "".join(chars), offsets


def source_aligned_fact_pairs(
    records: Sequence[PageReviewRecord], source: PageAssociationSource
) -> list[tuple[PageFactObservation, PageFactObservation]]:
    source = PageAssociationSource.model_validate(source.model_dump())
    source_text, offsets = _positioned_text(source.text)
    groups = defaultdict(list)
    main = [record for record in records if record.lane in {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}]
    main = [PageReviewRecord.model_validate(record.model_dump()) for record in main]
    if len(main) != 2 or len({record.lane for record in main}) != 2:
        raise ValueError("来源关联需要两个不同主读")
    if len({(record.page_artifact_id, record.page_image_sha256, record.clause_pack_sha256) for record in main}) != 1:
        raise ValueError("来源关联的原件或条款版本不一致")
    for record in main:
        if (record.source_document_version_id, record.page_number) != (source.source_document_version_id, source.page_number):
            raise ValueError("来源关联文本不属于当前文档页")
        for fact in record.facts:
            if (fact.context is None or not normalize_text(fact.context.target_text)
                    or fact.context.polarity == "not_stated"):
                continue
            excerpt, _ = _positioned_text(fact.region.excerpt)
            if not excerpt:
                continue
            start = source_text.find(excerpt)
            if start < 0 or source_text.find(excerpt, start + 1) >= 0:
                continue
            context = fact.context.model_dump(exclude={"location_text"})
            key = (offsets[start], offsets[start + len(excerpt) - 1] + 1, normalize_field_name(fact.field_name),
                   observation_context_key(context))
            groups[key].append((record.lane, fact))
    return [tuple(fact for _, fact in sorted(matches, key=lambda item: item[0].value))
            for matches in groups.values()
            if len(matches) == 2 and len({lane for lane, _ in matches}) == 2
            and len({(fact.normalized_value, fact.normalized_unit) for _, fact in matches}) == 1
            and len({source_arrow_marks(fact.raw_value) for _, fact in matches}) == 1]


def source_aligned_fact_keys(records: Sequence[PageReviewRecord], source: PageAssociationSource) -> set[str]:
    return {fact.normalization_key for pair in source_aligned_fact_pairs(records, source) for fact in pair}
