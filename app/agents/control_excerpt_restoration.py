"""Restore quote glyphs in explicit source fields, never clinical content."""
from collections.abc import Mapping, Sequence


_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})


def control_quote_normalize(text: str) -> str:
    return text.translate(_QUOTES)


def recover_control_excerpt(excerpt: str, sources: Sequence[str]) -> str:
    """Require an exact match or one unique quote-equivalent source substring."""
    if not excerpt or any(excerpt in source for source in sources):
        return excerpt
    normalized = control_quote_normalize(excerpt)
    matches: list[str] = []
    for source in sources:
        text = control_quote_normalize(source)
        start = text.find(normalized)
        while start >= 0:
            matches.append(source[start:start + len(excerpt)])
            start = text.find(normalized, start + 1)
    return matches[0] if len(matches) == 1 else excerpt


def restore_source_fields(value: object, sources: Mapping[str, Sequence[str]]) -> object:
    """Descendants can only use their containing object's declared sources.

    Works on serialized data without modifying the provider response. Unmatched
    excerpts remain unchanged for the existing strict validators to reject.
    """
    if isinstance(value, list):
        return [restore_source_fields(item, sources) for item in value]
    if not isinstance(value, dict):
        return value
    result = dict(value)
    spans, excerpts = value.get("source_span_ids"), value.get("source_excerpts")
    scope = sources
    if isinstance(spans, list) and isinstance(excerpts, list) and len(spans) == len(excerpts):
        restored = [recover_control_excerpt(excerpt, sources.get(span, ()))
                    for span, excerpt in zip(spans, excerpts, strict=True)]
        result["source_excerpts"] = restored
        scope = {}
        for span, excerpt in zip(spans, restored, strict=True):
            scope.setdefault(span, []).append(excerpt)
    elif isinstance(value.get("source_span_id"), str) and isinstance(value.get("source_excerpt"), str):
        span = value["source_span_id"]
        excerpt = recover_control_excerpt(value["source_excerpt"], sources.get(span, ()))
        result["source_excerpt"] = excerpt
        scope = {span: (excerpt,)}
    texts = tuple(text for items in scope.values() for text in items)
    if isinstance(excerpts, list) and not isinstance(spans, list):
        result["source_excerpts"] = [recover_control_excerpt(item, texts) for item in excerpts]
    for key, child in result.items():
        if key in {"source_clause", "trigger_excerpt", "applies_to_quote", "duration_quote"} and isinstance(child, str):
            result[key] = recover_control_excerpt(child, texts)
        elif key == "source_clauses" and isinstance(child, list):
            result[key] = [recover_control_excerpt(item, texts) for item in child]
        elif key not in {"source_excerpts", "source_excerpt"}:
            result[key] = restore_source_fields(child, scope)
    return result
