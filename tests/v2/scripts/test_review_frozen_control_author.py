"""Saved-answer reuse must retain original receipts and request reservations."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from app.agents.protocol_control_deconstructor import (
    ProtocolControlAgentResponse, ProtocolControlAgentRunner, ProtocolControlAgentWireValidationError,
)
from app.llm.logical_call_budget import LogicalCallBudget
from scripts.review_frozen_control_author import load_frozen_author, _SavedAuthorTransport
from tests.v2.protocols.test_protocol_control_fixed_flow import _separate_heading_example, _Transport


def _frozen_record():
    batch, inventory, review, selection = _separate_heading_example()
    batch.owned_source_span_ids = sorted({span for unit in batch.owned_units for span in unit.source_span_ids})
    batch.known_procedure_targets[0].visit_instance = batch.known_workflow_stage_targets[0].visit_instance
    batch = type(batch).model_validate(batch.model_dump(mode="json"))

    def reject_old_assembly(output):
        raise ProtocolControlAgentWireValidationError("FABRICATED_EXCERPT", "旧装配引用错误")

    result = ProtocolControlAgentRunner().run(
        batch, _Transport(review, selection), resume_source_interpretation=inventory,
        workflow_variant="RV1001-FLOW", output_validator=reject_old_assembly,
    )
    # The original source interpretation was a real prior response in this
    # fixture's frozen record, not a new provider call during reassembly.
    texts = [inventory.model_dump_json(), result.attempts[0].raw_output_text,
             result.attempts[1].raw_output_text]
    sessions = ["source-read", result.attempts[0].session_id, result.attempts[1].session_id]
    attempts = [{
        "attempt": i + 1, "session_id": sessions[i], "raw_output_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "raw_output_chars": len(text), "outcome": "parsed", "error_classes": [], "issues": [],
    } for i, text in enumerate(texts)]
    failure = result.attempts[-1].model_dump(mode="json")
    failure["attempt"] = 4
    saved = result.model_dump(mode="json")
    saved["attempts"] = attempts + [failure]
    budget = LogicalCallBudget("original-task", max_requests=6, max_output_tokens=600,
                               contract_sha256="d" * 64)
    receipts = []
    for i in range(3):
        request_hash = str(i + 1) * 64
        budget.reserve(request_sha256=request_hash, max_tokens=100)
        receipts.append({"finish_reason": "stop", "budget_request_sha256": request_hash,
                         "requested_max_tokens": 100, "request_reserved": True})
    return {
        "receipt_format_version": "frozen-control-slice/v2", "workflow_executed": "RV1001-FLOW",
        "consumer_validated": False, "call_receipts": receipts, "result": saved,
        "logical_task_id": "original-task", "execution_contract_sha256": "d" * 64,
        "logical_call_budget": budget.snapshot(), "frozen_batch": batch.model_dump(mode="json"),
        "attempt_raw_outputs": [{
            "attempt": i + 1, "session_id": sessions[i], "sha256": attempts[i]["raw_output_sha256"],
            "characters": len(text), "text": text, "outcome": "parsed", "error_classes": [],
        } for i, text in enumerate(texts)] + [{"text": None}],
    }


def _load(tmp_path, record):
    path = tmp_path / "frozen.json"
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return load_frozen_author(path)


def test_valid_complete_author_and_original_budget_are_reused_without_calls(tmp_path):
    data, batch, interpretation, review, author = _load(tmp_path, _frozen_record())
    assert len(review.items) == len(interpretation.statements) == 1
    assert batch.owned_structure_unit_ids == [interpretation.statements[0].structure_unit_id]
    assert author.session_id == data["attempt_raw_outputs"][2]["session_id"]
    assert data["logical_call_budget"]["requests_used"] == 3


@pytest.mark.parametrize("defect", ["extra_answer", "missing_answer", "changed_text", "wrong_session",
    "wrong_length", "different_failure", "successful", "changed_budget", "wrong_receipt",
    "unreserved_request", "wrong_contract", "unknown_consumer_state"])
def test_incompatible_record_is_rejected_before_provider_access(tmp_path, defect):
    record = deepcopy(_frozen_record())
    if defect == "extra_answer":
        record["attempt_raw_outputs"].append({"text": None})
    elif defect == "missing_answer":
        del record["attempt_raw_outputs"][2]
    elif defect == "changed_text":
        record["attempt_raw_outputs"][2]["text"] += " "
    elif defect == "wrong_session":
        record["attempt_raw_outputs"][2]["session_id"] = "other-author"
    elif defect == "wrong_length":
        record["attempt_raw_outputs"][2]["characters"] += 1
    elif defect == "different_failure":
        record["result"]["attempts"][-1]["error_classes"] = ["MODEL_IDENTITY_MISMATCH"]
    elif defect == "successful":
        record["consumer_validated"] = True
    elif defect == "changed_budget":
        record["logical_call_budget"]["requests_used"] = 0
    elif defect == "wrong_receipt":
        record["call_receipts"][2]["budget_request_sha256"] = "e" * 64
    elif defect == "unreserved_request":
        record["call_receipts"][2]["request_reserved"] = False
    elif defect == "wrong_contract":
        record["execution_contract_sha256"] = "e" * 64
    else:
        record["consumer_validated"] = None
    with pytest.raises(ValueError):
        _load(tmp_path, record)


def test_saved_transport_only_allows_the_missing_review_call():
    class Live:
        def __init__(self):
            self.calls = []

        def start_source_candidate_alignment(self, *, prompt):
            self.calls.append(prompt)
            return ProtocolControlAgentResponse(session_id="fresh-review", text="{}")

    live = Live()
    author = ProtocolControlAgentResponse(session_id="original-author", text="{}")
    transport = _SavedAuthorTransport(live, [{}, {"session_id": "original-review", "text": "{}"}], author)
    assert transport.read_stage_bound_requirement(prompt="unused") is author
    assert transport.start_source_target_review(prompt="unused").session_id == "original-review"
    assert live.calls == []
    assert transport.start_source_candidate_alignment(prompt="missing review").session_id == "fresh-review"
    assert live.calls == ["missing review"]
    with pytest.raises(ValueError):
        transport.start(prompt="whole author")
    with pytest.raises(ValueError):
        transport.continue_session(session_id="original-author", prompt="change answer")
