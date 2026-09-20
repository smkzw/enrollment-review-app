"""Compare pair-local source relations, never whole-atom truth or adoption."""
from app.domain.publication import canonical_hash
from app.llm.proposition_evidence import (
    PropositionEvidenceRead, build_proposition_evidence_messages,
    validate_proposition_evidence_payload,
)


def compare_proposition_evidence(pairs, batch, reads: tuple[PropositionEvidenceRead, PropositionEvidenceRead]):
    if len(reads) != 2 or {read.lane for read in reads} != {"main-A", "main-B"}:
        raise ValueError("命题核实比较需要本次两个完整主读结果")
    expected = (batch.frozen_input_sha256, batch.batch_sha256,
                canonical_hash(build_proposition_evidence_messages(pairs, batch)))
    if {(read.frozen_input_sha256, read.batch_sha256, read.messages_sha256) for read in reads} != {expected}:
        raise ValueError("命题核实不能混用不同资料、要求或提示的回答")
    if len({(read.requested_provider, read.requested_model) for read in reads}) != 2:
        raise ValueError("同一模型重复调用不能作为两个独立判断")
    indexed = {}
    for read in reads:
        payload = validate_proposition_evidence_payload(pairs, read.payload.model_dump_json())
        indexed[read.lane] = {item.pair_id: item for item in payload.results}
    records = []
    for pair in sorted(pairs, key=lambda item: item.pair_id):
        left, right = (indexed[lane][pair.pair_id] for lane in ("main-A", "main-B"))
        if left.agreement_key() != right.agreement_key():
            status = "disagreement"
        elif left.relation == "undetermined":
            status = "unresolved"
        else:
            status = f"{left.relation}_agreed"
        records.append({
            "pair_id": pair.pair_id, "identity_sha256": pair.identity_sha256,
            "status": status, "scope": "pair_local",
            "lanes": {lane: indexed[lane][pair.pair_id].model_dump(mode="json")
                      for lane in ("main-A", "main-B")},
        })
    material = {
        "version": "proposition-evidence-comparison/v2", "clinical_adoption": False,
        "frozen_input_sha256": expected[0], "batch_sha256": expected[1], "messages_sha256": expected[2],
        "records": records,
    }
    return {**material, "comparison_sha256": canonical_hash(material)}
