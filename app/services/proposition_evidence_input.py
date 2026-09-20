"""Select source-relation work from a receipt-verified candidate job."""
from app.domain.contracts.binding_qualification import BindingQualificationPairContext
from app.domain.contracts.control_atom_binding import ControlBindingFrozenInput
from app.domain.contracts.predicate_binding import PredicateBindingFrozenInput
from app.domain.publication import canonical_hash
from app.projections.control_atom_binding_input import project_control_atom_identities
from app.services.binding_qualification_support import load_completed_candidate_qualification_input
from app.services.review_candidate_scope import require_prepared_candidate_scope


def plan_proposition_evidence_batches(pairs, *, max_characters):
    """Reuse exact-size packing with this reader's actual prompt, not an estimate."""
    from app.llm.proposition_evidence import build_proposition_evidence_messages
    from app.services.judgment_content_receipts import plan_judgment_content_batches
    return plan_judgment_content_batches(
        pairs, max_characters=max_characters, message_builder=build_proposition_evidence_messages,
    )


def load_proposition_evidence_input(session, artifact_store, *, candidate_job_id, context_id):
    material = load_completed_candidate_qualification_input(
        session, artifact_store, candidate_job_id, require_route_receipts=True,
    )
    family = material.get("family")
    if family not in {"control", "predicate"} or material.get("review_context_id") != context_id:
        raise ValueError("命题核实须使用本次审核对应的方案条件候选记录")
    if family == "control":
        frozen = ControlBindingFrozenInput.model_validate(material["frozen_input"])
        digest = require_prepared_candidate_scope(session, context_id, frozen.evidence_input, control_input=frozen)
        identities = {item.identity_sha256: item.atom.evaluation.operand_attribute
                      for item in project_control_atom_identities(frozen.publication, include_repeat_triggers=True)
                      if item.atom.evaluation is not None
                      and item.atom.evaluation.determination_mode in {"semantic", "investigator_judgment"}}
    else:
        frozen = PredicateBindingFrozenInput.model_validate(material["frozen_input"])
        digest = require_prepared_candidate_scope(session, context_id, frozen)
        identities = {item.predicate_identity_sha256: None for component in frozen.components
                      for item in component.binding_predicates
                      if item.predicate.semantic_proposition is not None}
    if digest != material["review_context_sha256"]:
        raise ValueError("命题核实候选与本次审核准备不一致")
    selected, skipped = [], []
    for raw in material["pairs"]:
        pair = BindingQualificationPairContext.model_validate(raw)
        if pair.identity_sha256 not in identities:
            continue
        if pair.candidate_family != family:
            raise ValueError("原文配对与方案条件来源不一致")
        if identities[pair.identity_sha256] not in {None, pair.fact_attribute}:
            skipped.append({"pair_id": pair.pair_id, "identity_sha256": pair.identity_sha256,
                            "reason": "declared_source_attribute_mismatch"})
            continue
        basis = pair.fact.get("assertion_basis")
        if (pair.fact_attribute not in {"value", "assertion_basis"}
                or not isinstance(basis, dict) or basis.get("locator_id") != pair.locator_id):
            skipped.append({"pair_id": pair.pair_id, "identity_sha256": pair.identity_sha256,
                            "reason": "bound_assertion_source_missing"})
            continue
        selected.append(pair.model_dump(mode="json"))
    selected.sort(key=lambda item: item["pair_id"])
    payload = {
        "version": "proposition-evidence-input/v2", "candidate_job_id": candidate_job_id,
        "review_context_id": context_id, "review_context_sha256": digest,
        "frozen_input_sha256": material["frozen_input_sha256"],
        "comparison_sha256": material["comparison_sha256"],
        "candidate_receipt_sha256s": material["candidate_receipt_sha256s"],
        "pairs": selected, "skipped_pairs": sorted(skipped, key=lambda item: item["pair_id"]),
        "identity_coverage": [{"identity_sha256": key,
            "pair_ids": [item["pair_id"] for item in selected if item["identity_sha256"] == key],
            "observation_scope_verified": False} for key in sorted(identities)],
    }
    return {**payload, "input_sha256": canonical_hash(payload)}
