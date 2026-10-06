"""Locate text not quoted by facts; this is not a clinical completeness proof."""

from app.domain.contracts.evidence_normalizer import (
    EvidenceNormalizerInput,
    EvidenceNormalizerOutput,
    EvidenceNormalizerSourceTextRange,
    EvidenceNormalizerUnresolvedItem,
)
from app.domain.contracts.enums import LocatorPrecision, LocatorSourceLayer


TEXT_ACCOUNTING_POLICY = "normalizer-text-accounting/v1"
UNACCOUNTED_TEXT_CODE = "source_text_not_accounted"


def _unique_offset(text: str, excerpt: str) -> int | None:
    start = text.find(excerpt)
    if start < 0 or text.find(excerpt, start + 1) >= 0:
        return None
    return start


def unaccounted_source_text(
    evidence_input: EvidenceNormalizerInput, output: EvidenceNormalizerOutput,
) -> list[EvidenceNormalizerUnresolvedItem]:
    """Account only exact, uniquely positioned quotes, never whole locator spans.

    Lines retain their shared context. We neither classify headers/background nor
    infer missing procedures. A fully quoted line still needs semantic review;
    image/handwriting coverage cannot be proven by a text ledger.
    """
    if any(item.code == UNACCOUNTED_TEXT_CODE or item.source_text_range is not None
           for item in output.unresolved_items):
        raise ValueError("来源文字核对记录必须由系统按本次冻结原文生成")
    pages = {page.page_number: page for page in evidence_input.pages}
    locators = {item.locator_id: item for item in evidence_input.available_locators}
    covered: dict[int, set[int]] = {number: set() for number in pages}
    for fact in output.fact_candidates:
        basis = fact.assertion_basis
        if basis is None:
            continue
        locator = locators.get(basis.locator_id)
        if locator is None or locator.precision == LocatorPrecision.PAGE_ONLY:
            continue
        page = pages[locator.page_number]
        if (locator.source_layer not in {
                LocatorSourceLayer.EFFECTIVE_TEXT, LocatorSourceLayer.RAW_OCR,
            } or locator.source_text_sha256 != page.effective_text_sha256
                or not locator.localized_text):
            continue
        local_start = _unique_offset(page.effective_text, locator.localized_text)
        quote_start = _unique_offset(locator.localized_text, basis.assertion_text)
        if local_start is None or quote_start is None:
            continue
        start = local_start + quote_start
        covered[page.page_number].update(range(start, start + len(basis.assertion_text)))

    items = []
    for page in evidence_input.pages:
        offset = 0
        for line in page.effective_text.splitlines(keepends=True):
            line_end = offset + len(line)
            ranges = []
            start = None
            for index in range(offset, line_end):
                if index not in covered[page.page_number]:
                    if start is None:
                        start = index
                elif start is not None:
                    ranges.append((start, index))
                    start = None
            if start is not None:
                ranges.append((start, line_end))
            for start, end in ranges:
                if not page.effective_text[start:end].strip():
                    continue
                # Preserve the line context without turning its punctuation into
                # independent clinical assertions or borrowing a neighbouring quote.
                items.append(EvidenceNormalizerUnresolvedItem(
                    code=UNACCOUNTED_TEXT_CODE,
                    message=f"第{page.page_number}页有文字尚未逐项整理核对。",
                    affected_pages=[page.page_number],
                    reason="这段文字尚不能确认已完整整理；可能包含标题、背景或临床记录，"
                           "不代表患者缺少检查，也不代表入排不符合。原文：" + line.strip(),
                    source_text_range=EvidenceNormalizerSourceTextRange(
                        source_document_version_id=page.source_document_version_id,
                        page_artifact_id=page.page_artifact_id,
                        page_number=page.page_number,
                        effective_text_sha256=page.effective_text_sha256,
                        text_start=start, text_end=end,
                        excerpt=page.effective_text[start:end],
                        context_start=offset, context_end=line_end,
                    ),
                ))
            offset = line_end
    return items


def validate_text_accounting_items(
    evidence_input: EvidenceNormalizerInput, items: list[EvidenceNormalizerUnresolvedItem],
) -> None:
    pages = {page.page_number: page for page in evidence_input.pages}
    for item in items:
        source = item.source_text_range
        if source is None:
            continue
        page = pages.get(source.page_number)
        if (item.code != UNACCOUNTED_TEXT_CODE or page is None
                or item.gap_type is not None or item.affected_requirement_ids
                or item.affected_pages != [source.page_number]
                or source.source_document_version_id != page.source_document_version_id
                or source.page_artifact_id != page.page_artifact_id
                or source.effective_text_sha256 != page.effective_text_sha256
                or source.context_end > len(page.effective_text)
                or source.excerpt != page.effective_text[source.text_start:source.text_end]):
            raise ValueError("来源文字核对记录与本次冻结原文不一致")
