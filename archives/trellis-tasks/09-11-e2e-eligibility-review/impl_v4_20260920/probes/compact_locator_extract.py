# Behavioral excerpt of _compact_locator_inputs, fetched from commit
# 60f5bb8fe67ac14d44af9ceab0801a9b2a42120b.
# Type annotations and docstrings omitted; not a whole-module/runtime test.
def _compact_locator_inputs(locators):
    ordered = sorted(locators, key=lambda item: item.locator_id)
    grouped_texts = {}
    for locator in ordered:
        text = (locator.localized_text or "").strip()
        if text:
            grouped_texts.setdefault((locator.source_layer, locator.source_text_sha256), set()).add(text)
    kept = []
    seen = set()
    for locator in ordered:
        text = (locator.localized_text or "").strip()
        if not text:
            kept.append(locator)
            continue
        group = (locator.source_layer, locator.source_text_sha256)
        identity = (*group, text)
        if identity in seen:
            continue
        seen.add(identity)
        if any(text != other and text in other for other in grouped_texts[group]):
            continue
        kept.append(locator)
    return kept
