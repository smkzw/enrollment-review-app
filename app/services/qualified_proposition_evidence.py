"""Intersect receipt-proven relations with qualified sources; never infer coverage."""
from app.services.proposition_evidence_receipts import verify_completed_proposition_evidence
from app.domain.contracts.proposition_evidence import ProspectiveEvidenceCheck
from app.llm.proposition_context import proposition_context, prospective_requirement
from app.services.review_method_evidence import read_method_evaluation
from app.storage.repositories import ScopeViolationError

PROPOSITION_CONSUMER_VERSION = "qualified-proposition-evidence/v9"


def _control_current_node_reason(pair):
    if pair.candidate_family != "control":
        return None
    current = pair.episode.get("workflow_stage_id")
    context = pair.parent_source_context
    mapping = context.get("workflow_stage_map")
    bindings = context.get("review_node_bindings")
    if (not isinstance(current, str) or not current
            or not isinstance(mapping, dict) or not isinstance(bindings, list)):
        return "proposition_current_node_unverified"
    decisions = [item for item in bindings if isinstance(item, dict)
                 and item.get("role") == "decide_at_node"]
    if not decisions or any(not isinstance(item.get("workflow_stage_id"), str)
                            for item in decisions):
        return "proposition_current_node_unverified"
    if current not in {mapping.get(item["workflow_stage_id"]) for item in decisions}:
        return "proposition_current_node_mismatch"
    return None


def require_proposition_method(manifest, binding_method, evidence):
    if manifest.evaluation_kind != "pair_local_proposition_relation":
        raise ScopeViolationError("原文含义核实尚无对应的方法评测")
    methods = [item for item in manifest.methods if item.candidate_family == binding_method.candidate_family]
    if len(methods) != 1:
        raise ScopeViolationError("原文含义评测未覆盖本类要求")
    method = methods[0]
    if (method.source_qualification_method != binding_method
            or method.content_contract != evidence["contract"]
            or method.content_prompt_version != evidence["prompt_version"]
            or method.content_summary_version != evidence["summary"]["version"]
            or {key: value.model_dump(mode="json") for key, value in method.content_routes.items()}
            != evidence["routes"]
            or method.content_consumer_version != PROPOSITION_CONSUMER_VERSION):
        raise ScopeViolationError("原文核实与已评测的方法版本或读取配置不同")


def verify_qualified_proposition_evidence(
    session, artifact_store, *, source, binding_method, adoption,
):
    evidence = verify_completed_proposition_evidence(session, artifact_store, adoption.job_id)
    payload = evidence["payload"]
    if (source["candidate_family"] not in {"predicate", "control"}
            or payload["candidate_job_id"] != source["payload"]["candidate_job_id"]
            or any(payload.get(key) is None or payload.get(key) != source["payload"].get(key)
                   for key in ("review_context_id", "review_context_sha256",
                               "frozen_input_sha256", "comparison_sha256"))
            or evidence["summary_sha256"] != adoption.summary_logical_sha256
            or evidence["summary_artifact_sha256"] != adoption.summary_artifact_sha256):
        raise ScopeViolationError("原文含义结果与本次来源核实或审核准备不一致")
    source_pairs = {pair.pair_id: pair for pair in source["pairs"]}
    if any(source_pairs.get(pair.pair_id) != pair
           or pair.candidate_family != source["candidate_family"] for pair in evidence["pairs"]):
        raise ScopeViolationError("原文含义配对不属于本次来源核实")
    require_proposition_method(
        read_method_evaluation(artifact_store, adoption.evaluation_sha256), binding_method, evidence,
    )
    return evidence


def select_qualified_relations(evidence, source_records, *, source_validity_specs=None,
                               written_content_verified_pair_ids=frozenset()):
    """Arithmetic qualification remains conservative; no rejected source is waived.

    Written-attribution and observation/time coverage are not established by
    agreement alone. Any corresponding unresolved source check remains visible.
    """
    from app.services.qualified_binding_selection import (
        pair_direct_selection_rejection_reasons, source_validity_operand_calculable,
    )

    sources = {record.pair_id: record for record in source_records}
    pairs = {pair.pair_id: pair for pair in evidence["pairs"]}
    validity_specs = source_validity_specs or {}
    selected, unresolved = [], []
    for comparison in evidence["summary"]["comparisons"]:
        for record in comparison["records"]:
            source = sources.get(record["pair_id"])
            reasons = (["source_qualification_missing"] if source is None
                       else pair_direct_selection_rejection_reasons(
                           source, source_validity_calculable=source_validity_operand_calculable(
                               source, validity_specs.get(source.identity_sha256)),
                           written_content_verified=source.pair_id in written_content_verified_pair_ids))
            if source is not None and source.identity_sha256 != record["identity_sha256"]:
                reasons = [*reasons, "source_identity_mismatch"]
            if record["status"] not in {"entails_agreed", "contradicts_agreed"}:
                reasons = [*reasons, f"proposition_{record['status']}"]
            pair = pairs[record["pair_id"]]
            node_reason = _control_current_node_reason(pair)
            if node_reason is not None:
                reasons.append(node_reason)
            spec, _ = proposition_context(pair)
            policy = spec.get("observation_policy")
            for lane in record["lanes"].values():
                if isinstance(policy, dict) and policy.get("mode") == "action_completion":
                    witness = lane.get("action_witness")
                    expected = (
                        "completed" if record["status"] == "entails_agreed" else
                        "explicit_not_completed" if record["status"] == "contradicts_agreed" else None
                    )
                    if (not isinstance(witness, dict) or witness.get("status") != expected
                            or not isinstance(witness.get("action_quote"), str)
                            or not witness["action_quote"].strip()):
                        reasons.append("action_completion_source_unverified")
                    if lane.get("scope_correspondence") != "supported" or not lane.get("scope_quote"):
                        reasons.append("observation_scope_completeness_unverified")
                if (lane.get("assertion_extent") == "universal_over_declared_scope"
                        and (not isinstance(policy, dict) or policy.get("mode") not in {"any", "all"})):
                    reasons.append("proposition_scope_policy_mismatch")
                if policy is None and (lane.get("scope_correspondence") != "unresolved"
                                       or lane.get("scope_quote") is not None):
                    reasons.append("proposition_scope_policy_mismatch")
            if prospective_requirement(pair):
                for lane in record["lanes"].values():
                    future = lane.get("prospective_evidence")
                    reasons = [*reasons, *(
                        ProspectiveEvidenceCheck.model_validate(future).unresolved_codes()
                        if future is not None else ["prospective_statement_period_unverified"]
                    )]
            if reasons:
                unresolved.append({"pair_id": record["pair_id"],
                                   "identity_sha256": record["identity_sha256"],
                                   "fact_id": pairs[record["pair_id"]].fact_id,
                                   "locator_id": pairs[record["pair_id"]].locator_id,
                                   "reasons": sorted(set(reasons))})
            else:
                selected.append({**record, "fact_id": source.fact_id})
    return selected, unresolved
