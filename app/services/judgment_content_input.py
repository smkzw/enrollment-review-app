"""Receipt-bound written-judgment pair selection from one review preparation."""
from dataclasses import asdict

from app.domain.contracts.binding_qualification import BindingQualificationPairContext
from app.domain.contracts.control_evidence_dependency import control_atom_reference_key
from app.domain.publication import canonical_hash
from app.services.binding_qualification_support import load_completed_candidate_qualification_input
from app.services.judgment_fact_linkage import load_prepared_judgment_links
from app.services.control_judgment_fact_linkage import load_prepared_control_judgment_links


def load_judgment_content_input(session, artifact_store, *, candidate_job_id: str, context_id: str):
    """Retain unlinked excerpts; source matching never authorizes fact adoption."""
    material = load_completed_candidate_qualification_input(
        session, artifact_store, candidate_job_id, require_route_receipts=True,
    )
    if material.get("review_context_id") != context_id:
        raise ValueError("判断内容核实须来自同一次审核准备的候选任务")
    family = material.get("family")
    if family not in {"predicate", "control"}:
        raise ValueError("判断内容核实不支持当前要求类型")
    links = (load_prepared_judgment_links(session, artifact_store, context_id=context_id)
             if family == "predicate" else load_prepared_control_judgment_links(
                 session, artifact_store, context_id=context_id, source=material["frozen_input"]))
    pairs = [BindingQualificationPairContext.model_validate(item) for item in material["pairs"]]
    selected = {}
    coverage = []
    for link in links:
        linked_pairs = []
        if link.status == "unique_source_match":
            fact_id, locator_id = link.matches[0]
            for pair in pairs:
                if (pair.candidate_family != family or pair.fact_attribute != "value"
                        or pair.fact_id != fact_id or pair.locator_id != locator_id):
                    continue
                # Predicate identifiers are component-local; require the owning evidence row too.
                if family == "predicate":
                    if pair.condition.get("predicate_id") not in link.predicate_ids or not any(
                        policy.get("requirement_id") == link.requirement_id
                        and pair.condition["predicate_id"] in policy.get("predicate_ids", [])
                        for policy in pair.source_policies
                    ):
                        continue
                else:
                    atom_ref = control_atom_reference_key(*(pair.condition.get(key) for key in (
                        "layer", "group_index", "atom_index", "condition_id")))
                    if (pair.condition.get("protocol_control_id") != link.protocol_control_id
                            or atom_ref not in link.atom_refs) or not any(
                        policy.get("protocol_control_id") == link.protocol_control_id
                        and policy.get("evidence_key") == link.evidence_key
                        and any(control_atom_reference_key(*(ref.get(key) for key in (
                                    "layer", "group_index", "atom_index", "condition_id"))) == atom_ref
                                for ref in policy.get("atom_refs", []))
                        for policy in pair.source_policies
                    ):
                        continue
                selected[pair.pair_id] = pair.model_dump(mode="json")
                linked_pairs.append(pair.pair_id)
        coverage.append({
            **asdict(link),
            "predicate_ids": list(link.predicate_ids),
            "matches": [list(match) for match in link.matches],
            "pair_ids": sorted(linked_pairs),
            "content_check_ready": bool(linked_pairs),
            **({"atom_refs": [list(ref) for ref in link.atom_refs],
                "attribution_status": "explicit" if link.atom_refs else "unassigned"}
               if family == "control" else {}),
        })
    payload = {
        "version": "judgment-content-input/v1" if family == "predicate" else "judgment-content-input/control-v1",
        "candidate_job_id": candidate_job_id,
        "review_context_id": context_id,
        "review_context_sha256": material["review_context_sha256"],
        "frozen_input_sha256": material["frozen_input_sha256"],
        "comparison_sha256": material["comparison_sha256"],
        "candidate_receipt_sha256s": material["candidate_receipt_sha256s"],
        "pairs": [selected[key] for key in sorted(selected)],
        "excerpt_coverage": coverage,
    }
    return {**payload, "input_sha256": canonical_hash(payload)}
