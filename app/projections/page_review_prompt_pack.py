"""Lossless wire compaction; the authoritative ClausePack stays unchanged."""

from app.domain.contracts.clause_pack import ClausePack
from app.projections.control_evidence_requirements import project_control_evidence_requirements


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
    publication = payload.pop("control_publication", None)
    if publication is not None:
        assert pack.control_publication is not None
        payload["control_evidence_requirements"] = [
            item.model_dump(mode="json", include={
                "requirement_id", "protocol_control_id", "evidence_key", "workflow_stage_id",
            })
            for item in project_control_evidence_requirements(pack.control_publication)
        ]
        # Execution receipts stay frozen internally, not repeated in model input.
        catalog = publication["catalog"]
        for field in ("catalog_id", "protocol_document_sha256", "coverage_manifest_id",
                      "allowed_source_span_ids"):
            catalog.pop(field, None)

        def compact_excerpts(value):
            if isinstance(value, list):
                return [compact_excerpts(item) for item in value]
            if not isinstance(value, dict):
                return value
            result = {}
            for key, item in value.items():
                if key == "source_excerpts":
                    refs = []
                    for excerpt in item:
                        if excerpt is None:
                            refs.append(None)
                            continue
                        if excerpt not in source_refs:
                            ref = f"source-{len(source_refs) + 1}"
                            source_refs[excerpt] = ref
                            source_texts[ref] = excerpt
                        refs.append(source_refs[excerpt])
                    result["source_excerpt_refs"] = refs
                else:
                    result[key] = compact_excerpts(item)
            return result

        # Keep branch/atom IDs and relation endpoints: they carry actual logic.
        payload["protocol_controls"] = compact_excerpts(catalog)
        payload["control_publication_id"] = publication["publication_id"]
        payload["control_workflow_stage_map"] = publication["workflow_stage_map"]
    return payload
