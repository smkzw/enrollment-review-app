"""Lossless wire compaction; the authoritative ClausePack stays unchanged."""

from app.domain.contracts.clause_pack import ClausePack


def page_review_prompt_pack(pack: ClausePack) -> dict:
    payload = pack.model_dump(mode="json", exclude_none=True)
    source_refs: dict[str, str] = {}
    source_texts: dict[str, str] = {}
    for clause in payload["clauses"]:
        source = clause.pop("source_text")
        if source not in source_refs:
            ref = f"source-{len(source_refs) + 1}"
            source_refs[source] = ref
            source_texts[ref] = source
        clause["source_text_ref"] = source_refs[source]
    payload["source_texts"] = source_texts
    return payload
