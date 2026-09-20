"""Compare source-validated declarations; agreement is not verified evidence."""
from app.llm.candidate_fact_accounting import ACCOUNTING_VERSION
from app.llm.predicate_binding_candidates import PredicateFactCandidate

COMPARISON_VERSION = "binding-candidate-comparison/v2"

# Accounting dispositions are compared per fact so that a one-lane candidate
# against the other lane's exclusion or uncertainty stays explicitly visible
# and is never collapsed into an agreed exclusion.
_ACCOUNTING_STATUS = {
    ("has_candidates", "has_candidates"): "candidates_in_both_lanes",
    ("has_candidates", "noncorrespondence"): "candidate_vs_noncorrespondence",
    ("noncorrespondence", "has_candidates"): "candidate_vs_noncorrespondence",
    ("has_candidates", "uncertain"): "candidate_vs_uncertain",
    ("uncertain", "has_candidates"): "candidate_vs_uncertain",
    ("noncorrespondence", "noncorrespondence"): "agreed_noncorrespondence",
    ("uncertain", "uncertain"): "agreed_uncertain",
    ("noncorrespondence", "uncertain"): "noncorrespondence_vs_uncertain",
    ("uncertain", "noncorrespondence"): "noncorrespondence_vs_uncertain",
}


def _accounting_rows(entry_a, entry_b) -> list[dict]:
    a, b = entry_a.fact_accounting, entry_b.fact_accounting
    if a is None or b is None:
        raise ValueError("回答缺少版本化逐事实考虑记录，不能当作完整枚举合并")
    if a.accounting_version != ACCOUNTING_VERSION or b.accounting_version != ACCOUNTING_VERSION:
        raise ValueError("逐事实考虑记录版本不符，不能合并")
    index_a = {item.fact_id: item for item in a.considered_facts}
    index_b = {item.fact_id: item for item in b.considered_facts}
    if set(index_a) != set(index_b):
        raise ValueError("两路逐事实考虑范围不同，不能合并")
    rows = []
    for fact_id in sorted(index_a):
        item_a, item_b = index_a[fact_id], index_b[fact_id]
        rows.append({
            "fact_id": fact_id,
            "status": _ACCOUNTING_STATUS[(item_a.disposition, item_b.disposition)],
            "main-A": item_a.model_dump(mode="json"),
            "main-B": item_b.model_dump(mode="json"),
        })
    return rows


def compare_candidate_declarations(left, right, *, identity_field: str) -> list[dict]:
    """Preserve both explanations and compare only the same source/attribute.

    Callers validate each payload against its frozen input and supplied batch.
    Different locators are not fused, even if they belong to the same fact.
    Empty results mean no candidate in this input, not missing source records.
    Each identity also carries the two lanes' per-fact accounting comparison;
    it records consideration only, never semantic correctness or adoption.
    """
    lanes = [{getattr(item, identity_field): item for item in payload.results}
             for payload in (left, right)]
    if any(len(index) != len(payload.results) for index, payload in zip(lanes, (left, right))):
        raise ValueError("对应结果含重复条件，不能合并")
    if lanes[0].keys() != lanes[1].keys():
        raise ValueError("两路核对范围不同，不能合并")

    def key(candidate: PredicateFactCandidate):
        return candidate.fact_id, candidate.fact_attribute, candidate.locator_id

    results = []
    for identity in sorted(lanes[0]):
        entries = [lane[identity] for lane in lanes]
        indexed = [{key(candidate): candidate for candidate in entry.candidates} for entry in entries]
        if any(len(index) != len(entry.candidates) for index, entry in zip(indexed, entries)):
            raise ValueError("同一条件下的候选来源重复，不能合并")
        comparisons = []
        for source in sorted(indexed[0].keys() | indexed[1].keys()):
            a, b = (index.get(source) for index in indexed)
            if a is None or b is None:
                status = "single_lane"
            elif (a.object_correspondence, a.attribute_correspondence) != (
                b.object_correspondence, b.attribute_correspondence,
            ):
                status = "declaration_disagreement"
            else:
                status = "same_declaration"
            comparisons.append({
                "fact_id": source[0], "fact_attribute": source[1], "locator_id": source[2],
                "status": status, "accepted": False,
                "main-A": a.model_dump(mode="json") if a else None,
                "main-B": b.model_dump(mode="json") if b else None,
            })
        results.append({
            identity_field: identity, "accepted": False,
            "status": "candidates_compared" if comparisons else "no_candidates_in_supplied_input",
            "uncertainty": {"main-A": entries[0].uncertainty, "main-B": entries[1].uncertainty},
            "comparisons": comparisons,
            "fact_accounting": _accounting_rows(entries[0], entries[1]),
        })
    return results
