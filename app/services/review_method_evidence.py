"""Read persisted method evidence; this module never creates user approval."""
from app.domain.contracts.enums import GateOutcome
from app.domain.contracts.review_method_adoption import BindingEvaluationManifest, ReviewMethodApproval
from app.domain.contracts.judgment_method_evaluation import JudgmentEvaluationManifest
from app.domain.contracts.proposition_method_evaluation import PropositionEvaluationManifest
from app.domain.contracts.observation_method_evaluation import ObservationEvaluationManifest
from app.domain.contracts.frequency_method_evaluation import FrequencyEvaluationManifest
from pydantic import TypeAdapter
from app.domain.publication import canonical_hash
from app.storage.repositories import AppendRepository, GATE_RESULT_CONFIG, ScopeViolationError


def require_evaluated_binding_method(manifest, verified, consumer_version: str):
    methods = [item for item in manifest.methods if item.candidate_family == verified["candidate_family"]]
    if len(methods) != 1:
        raise ScopeViolationError("评测记录未覆盖本类资料核对方法")
    method = methods[0]
    expected = {
        **verified["candidate_method"],
        "qualification_contract": verified["contract"],
        "qualification_prompt_version": verified["prompt_version"],
        "qualification_summary_version": verified["summary"].version,
        "qualification_routes": verified["routes"],
        "consumer_algorithm_version": consumer_version,
    }
    actual = method.model_dump(mode="json")
    if any(actual.get(key) != value for key, value in expected.items()):
        raise ScopeViolationError("本次核对方法或双模型配置与评测范围不一致")
    return method


def read_binding_evaluation(artifact_store, digest: str) -> BindingEvaluationManifest:
    manifest = BindingEvaluationManifest.model_validate_json(
        artifact_store.read_by_sha("evaluation_manifest", digest),
    )
    # The report is still evidence to inspect, not a score-triggered approval.
    artifact_store.read_by_sha("raw_response", manifest.scoring_report_sha256)
    return manifest


def read_method_evaluation(artifact_store, digest: str):
    manifest = TypeAdapter(BindingEvaluationManifest | JudgmentEvaluationManifest | PropositionEvaluationManifest
                          | ObservationEvaluationManifest | FrequencyEvaluationManifest).validate_json(
        artifact_store.read_by_sha("evaluation_manifest", digest),
    )
    artifact_store.read_by_sha("raw_response", manifest.scoring_report_sha256)
    return manifest


def read_review_method_approval(session, artifact_store, gate_id: str):
    gate = AppendRepository(session, GATE_RESULT_CONFIG).get(gate_id)
    refs = [ref for ref in gate.input_entity_refs if ref.startswith("method_approval:")]
    if gate.gate_name != "review-method-adoption" or gate.result != GateOutcome.ACCEPTED or len(refs) != 1:
        raise ScopeViolationError("尚无完整的审核方法采用确认")
    approval = ReviewMethodApproval.model_validate_json(
        artifact_store.read_by_sha("method_approval", refs[0].split(":", 1)[1]),
    )
    if gate.output_hash != canonical_hash(approval.model_dump(mode="json")) or gate_id not in gate.accepted_entity_refs:
        raise ScopeViolationError("采用确认与已保存记录不一致")
    artifact_store.read_by_sha("approval_source", approval.approval_source_sha256)
    manifests = {}
    families = set()
    for digest in approval.evaluation_manifest_sha256s:
        if f"evaluation_manifest:{digest}" not in gate.input_entity_refs:
            raise ScopeViolationError("采用确认缺少对应评测记录")
        manifest = read_method_evaluation(artifact_store, digest)
        if manifest.created_at > approval.approved_at:
            raise ScopeViolationError("采用确认早于所引用的评测记录")
        for method in manifest.methods:
            scope = (manifest.evaluation_kind, method.candidate_family)
            if scope in families:
                raise ScopeViolationError("同类审核方法存在多份不同采用范围")
            families.add(scope)
        manifests[digest] = manifest
    return approval, manifests
