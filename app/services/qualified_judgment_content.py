"""Bind written-content evidence to the existing source-qualified review path."""
from app.domain.contracts.judgment_search import JudgmentSearchCoverageStatus
from app.services.judgment_content_receipts import verify_completed_judgment_content
from app.services.review_method_evidence import read_method_evaluation
from app.storage.repositories import ScopeViolationError

CONTENT_CONSUMER_VERSION = "qualified-judgment-content/v2"


def require_content_method(manifest, binding_method, content):
    if manifest.evaluation_kind != "written_judgment_content_fidelity":
        raise ScopeViolationError("书面判断必须有对应的内容核实评测")
    methods = [item for item in manifest.methods if item.candidate_family == binding_method.candidate_family]
    if len(methods) != 1:
        raise ScopeViolationError("书面判断评测未覆盖本类审核要求")
    method = methods[0]
    if (method.source_qualification_method != binding_method
            or method.content_contract != content["contract"]
            or method.content_prompt_version != content["prompt_version"]
            or method.content_summary_version != content["summary"]["version"]
            or {key: value.model_dump(mode="json") for key, value in method.content_routes.items()} != content["routes"]
            or method.content_consumer_version != CONTENT_CONSUMER_VERSION):
        raise ScopeViolationError("书面判断核实方法与已评测的版本或模型不同")


def verify_qualified_content(session, artifact_store, *, source, binding_method, adoption):
    content = verify_completed_judgment_content(session, artifact_store, adoption.job_id)
    payload = content["payload"]
    expected_version = ("judgment-content-input/v1" if source["candidate_family"] == "predicate"
                        else "judgment-content-input/control-v1")
    if (payload.get("input_version") != expected_version
            or payload["candidate_job_id"] != source["payload"]["candidate_job_id"]
            or any(payload.get(key) is None or payload.get(key) != source["payload"].get(key)
                   for key in ("review_context_id", "review_context_sha256", "frozen_input_sha256", "comparison_sha256"))
            or content["summary_sha256"] != adoption.summary_logical_sha256
            or content["summary_artifact_sha256"] != adoption.summary_artifact_sha256):
        raise ScopeViolationError("书面判断与本次来源核实或审核准备不一致")
    source_pairs = {pair.pair_id: pair for pair in source["pairs"]}
    if any(source_pairs.get(pair.pair_id) != pair for pair in content["pairs"]):
        raise ScopeViolationError("书面判断配对不属于本次完整来源核实")
    manifest = read_method_evaluation(artifact_store, adoption.evaluation_sha256)
    require_content_method(manifest, binding_method, content)
    supported = frozenset(record["pair_id"] for comparison in content["summary"]["comparisons"]
                          for record in comparison["records"] if record["status"] == "content_supported")
    return content, supported


def verified_judgment_requirements(frozen, source, outcomes, content, supported):
    """Resolve only judgment uncertainty, not all evidence expected by a requirement."""
    usable_pairs = {pair_id for outcome in outcomes if outcome.status == "usable"
                    for pair_id in outcome.usable_pair_ids} & set(supported)
    pairs = {pair.pair_id: pair for pair in content["pairs"]}
    summaries = {item.summary.requirement_id: item.summary for item in frozen.judgment_search_results}
    result = []
    for component in source.components:
        professional = {item.predicate_id: item.predicate_identity_sha256
                        for item in component.binding_predicates
                        if item.predicate.requires_professional_judgment}
        for requirement in component.evidence_requirements:
            targets = set(requirement.predicate_ids) & set(professional)
            summary = summaries.get(requirement.requirement_id)
            if (not targets or summary is None or not summary.found_candidates
                    or summary.status != JudgmentSearchCoverageStatus.CANDIDATES_PRESENT):
                continue
            if (summary.missing_lanes or summary.pages_without_lane_result
                    or summary.unreadable_channels or summary.ambiguous_channels):
                continue
            coverage = [item for item in content["excerpt_coverage"]
                        if item["requirement_id"] == requirement.requirement_id]
            if not coverage or any(item["status"] != "unique_source_match"
                                   or not set(item["pair_ids"]) & usable_pairs for item in coverage):
                continue
            linked = {pair_id for item in coverage for pair_id in item["pair_ids"]} & usable_pairs
            if all(any(pairs[pair_id].identity_sha256 == professional[predicate_id]
                       for pair_id in linked) for predicate_id in targets):
                result.append(requirement.requirement_id)
    return sorted(set(result))
