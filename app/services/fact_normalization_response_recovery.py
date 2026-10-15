"""Explicit, same-call revalidation of a complete failed model response."""
from dataclasses import dataclass
import hashlib
import json

from app.agents.evidence_normalizer import (
    parse_evidence_normalizer_output, validate_evidence_normalizer_output,
)
from app.agents.evidence_candidate_partition import recover_source_local_candidates
from app.domain.publication import canonical_hash


RESPONSE_RECOVERY_POLICY = "normalizer-saved-response-revalidation/v1"


@dataclass(frozen=True)
class SavedResponseRecovery:
    failure_manifest_sha256: str
    transport_receipt_sha256: str


@dataclass(frozen=True)
class RevalidatedResponse:
    output: object
    proof: dict
    partition: dict | None


def revalidate_saved_response(artifacts, selection, *, bindings, input_sha256,
                              evidence_input, expected_request, provider,
                              reference_aliases=None, allow_partition=False):
    """No answer search, model invocation, source alteration or persistence.

    Only the first logical answer of the explicitly selected failure may be
    reconsidered. Repair answers have changed context and are not interchangeable.
    """
    failure = json.loads(artifacts.read_by_sha("evaluation_manifest", selection.failure_manifest_sha256))
    receipt = json.loads(artifacts.read_by_sha("raw_response", selection.transport_receipt_sha256))
    for body in (failure, receipt):
        if any(body.get(key) != value for key, value in bindings.items()):
            raise ValueError("保存原答不属于当前作业及读取范围")
    attempts = failure.get("attempts")
    if (failure.get("input_sha256") != input_sha256 or not isinstance(attempts, list)
            or not attempts or not isinstance(attempts[0], dict)
            or attempts[0].get("error_code") != "PARTIAL_OUTPUT"
            or selection.transport_receipt_sha256 not in failure.get("transport_receipt_sha256", [])):
        raise ValueError("失败来源及首次完整回答无法核实")
    raw = receipt.get("raw_text")
    if not isinstance(raw, str) or not raw.strip() or receipt.get("finish_reason") != "stop":
        raise ValueError("保存原答未完整结束，不能作为恢复依据")
    raw_sha = hashlib.sha256(raw.encode()).hexdigest()
    if raw_sha != attempts[0].get("raw_output_sha256"):
        raise ValueError("保存原答不是失败记录中的首次回答")
    request_sha = receipt.get("request_artifact_sha256")
    if not isinstance(request_sha, str):
        raise ValueError("保存原答缺少实际请求依据")
    request = json.loads(artifacts.read_by_sha("raw_request", request_sha))
    if (any(request.get(key) != value for key, value in bindings.items())
            or request.get("request_receipt_version") != "normalizer-request/v1"
            or receipt.get("request_receipt_version") != "normalizer-request/v1"
            or request.get("provider") != provider or receipt.get("provider") != provider):
        raise ValueError("实际请求身份或供应商与当前范围不一致")
    actual_body = request.get("request_body")
    if not isinstance(actual_body, dict):
        raise ValueError("实际请求内容缺失")
    if canonical_hash(actual_body) != receipt.get("request_sha256") or actual_body != expected_request:
        raise ValueError("当前来源、提示、输出合同或模型参数与保存请求不同")
    # This bounded path does not invent alias evidence for an old gateway response.
    if (receipt.get("requested_model") != expected_request.get("model")
            or not isinstance(receipt.get("response_model"), str)
            or receipt["response_model"].casefold() != str(expected_request.get("model")).casefold()
            or not receipt.get("response_id")):
        raise ValueError("保存回答的实际模型身份无法对应本次请求")
    expected_aliases = reference_aliases.aliases if reference_aliases is not None else None
    if receipt.get("reference_aliases") != expected_aliases:
        raise ValueError("保存原答的来源简称与当前范围不同")
    partition = None
    try:
        output = parse_evidence_normalizer_output(raw,
            expected_run_id=evidence_input.run_id, expected_call_id=evidence_input.call_id,
            expected_logical_document_id=evidence_input.logical_document_id,
            expected_page_numbers=evidence_input.page_numbers,
            available_locator_ids=set(evidence_input.available_locator_ids),
            locator_source_hashes={item.locator_id: item.source_text_sha256 for item in evidence_input.available_locators},
            locator_source_texts={item.locator_id: item.localized_text for item in evidence_input.available_locators},
            created_at=evidence_input.created_at, reference_aliases=reference_aliases,
            require_current_draft=True)
        output = validate_evidence_normalizer_output(output, evidence_input)
    except (ValueError, TypeError):
        if not allow_partition:
            raise
        recovered = recover_source_local_candidates(raw, evidence_input, reference_aliases=reference_aliases)
        output, partition = recovered.output, recovered.receipt
    proof = {"policy": RESPONSE_RECOVERY_POLICY, **bindings,
        "input_sha256": input_sha256,
        "evidence_input_sha256": canonical_hash(evidence_input.model_dump(mode="json")),
        "failure_manifest_sha256": selection.failure_manifest_sha256,
        "transport_receipt_sha256": selection.transport_receipt_sha256,
        "request_artifact_sha256": request_sha, "request_sha256": receipt["request_sha256"],
        "response_model": receipt["response_model"], "response_id": receipt["response_id"],
        "raw_output_sha256": raw_sha, "output_sha256": canonical_hash(output.model_dump(mode="json")),
        "partitioned": partition is not None, "model_called": False}
    return RevalidatedResponse(output, proof, partition)
