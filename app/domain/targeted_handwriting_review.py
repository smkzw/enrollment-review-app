"""Auxiliary whole-page handwriting scope; never publishes a clinical judgment."""

from collections import Counter

from app.domain.page_normalization import normalize_text, observation_context_key
from app.domain.targeted_page_review import validate_pair


def _index(record):
    return Counter(
        _key(item)
        for item in record.handwriting
    )


def _key(item):
    return (item.kind.value, item.normalized_text, normalize_text(item.region.excerpt),
            observation_context_key(item.context.model_dump()) if item.context else None)


def pending_handwriting_excerpts(records) -> tuple[str, ...]:
    validate_pair(records)
    indexes = [_index(record) for record in records]
    excerpts = []
    for index, record in enumerate(records):
        remaining = indexes[index] - indexes[1 - index]
        for item in record.handwriting:
            key = _key(item)
            unknown = item.context is None or not normalize_text(item.context.target_text)
            if unknown or remaining[key] > 0:
                excerpts.append(item.region.excerpt)
                if remaining[key] > 0:
                    remaining[key] -= 1
    return tuple(excerpts)


def handwriting_needs_review(records) -> bool:
    validate_pair(records)
    # A kind mismatch or an observation seen by only one reader must not disappear.
    return bool(records[0].handwriting or records[1].handwriting) and not compare_handwriting_reads(records)


def compare_handwriting_reads(records) -> bool:
    """Return candidate agreement only; empty/missing ownership remains unresolved."""
    validate_pair(records)
    if not all(record.handwriting for record in records):
        return False
    if any(item.context is None or not normalize_text(item.context.target_text)
           for record in records for item in record.handwriting):
        return False
    return _index(records[0]) == _index(records[1])
