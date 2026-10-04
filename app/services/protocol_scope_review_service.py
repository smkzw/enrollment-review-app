"""Two bounded reads of a shared heading, without rewriting clinical content."""
from __future__ import annotations

import json

from app.domain.contracts.protocol_scope_review import OfficialScopeReading
from app.domain.publication import canonical_hash
from app.protocols.deconstruction_gate import _source_review_stages, _substantive_obligation_segments
from app.protocols.official_source_scope import frozen_parent_scope_fragments
from app.protocols.source_time_fragments import frozen_review_stage_aliases
from app.protocols.official_scope_review import (
    SCOPE_REVIEW_VERSION, OfficialScopeReviewError, OfficialScopeUnresolvedError, OfficialScopeRejectedError,
    scope_review_basis, scope_review_prompt, reviewed_scope_stages,
    scope_item_rejections, read_scope_receipt,
)


def review_official_source_scope(source, draft, *, official_code: str, transport, store,
                                resume_source_receipt=None):
    """Caller owns original persistent scope/run budgets and authorization.

    First session reads sources without the executable proposal. A fresh second
    session checks the same sources and proposal. Neither session modifies it.
    Completed raw answers remain stored even when parsing or reconciliation fails.
    """
    rules = [rule for rule in draft.proposed_rules if rule.official_code == official_code]
    if len(rules) != 1:
        raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_TARGET_MISMATCH")
    rule = rules[0]
    headings = frozen_parent_scope_fragments(
        source, official_code,
        scope_has_stages=lambda text: bool(_source_review_stages([text])),
        is_substantive=lambda text: bool(_substantive_obligation_segments(text)),
    )
    if not headings:
        raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_HEADING_MISSING")
    heading_stages = [stage.value for stage in _source_review_stages(
        [item.excerpt for item in headings], stage_aliases=frozen_review_stage_aliases(source))]
    basis = scope_review_basis(source, draft, rule, headings, heading_stages=heading_stages)
    if transport.logical_call_budget is None:
        raise OfficialScopeReviewError("BUDGET_RECORD_MISSING")
    initial_prompt = scope_review_prompt(basis)
    initial_options = transport._completion_kwargs(
        [{"role": "user", "content": transport._wire_contract_prompt(initial_prompt, "official_source_scope_review")}],
        output_kind="official_source_scope_review",
    )
    readings, receipts, sessions = [], [], []
    if resume_source_receipt is not None:
        try:
            reading, session_id, options = read_scope_receipt(basis, "source", resume_source_receipt, store.read)
            metadata = json.loads(store.read(resume_source_receipt["response_ref"]))["call_metadata"]
            transport.verify_recovery_budgets(metadata)
            saved_budget = metadata["logical_call_budget"]
            current_budget = transport.logical_call_budget.snapshot()
            request_hash = metadata["attempts"][-1]["budget_request_sha256"]
            # The transport reserves the actual streaming wire, not just its
            # completion options. Older unbound receipts cannot gain an allowance.
            wire_hashes = {canonical_hash(options), canonical_hash({**options, "stream": True}),
                           canonical_hash({**options, "stream": True,
                                           "stream_options": {"include_usage": True}})}
            if ({key: value for key, value in options.items() if key != "messages"}
                    != {key: value for key, value in initial_options.items() if key != "messages"}
                    or saved_budget["logical_task_id"] != current_budget["logical_task_id"]
                    or request_hash not in wire_hashes
                    or not all(any(row["request_sha256"] == request_hash
                                   and row["requested_max_tokens"] == options["max_tokens"]
                                   for row in budget["requests"])
                               for budget in (saved_budget, current_budget))):
                raise ValueError("saved source request is outside this allowance or model")
            scope_item_rejections(reading, basis, proposal=False)
            readings.append(reading)
            receipts.append(dict(resume_source_receipt))
            sessions.append(session_id)
        except OfficialScopeReviewError:
            raise
        except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
            raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_INVALID") from exc
    remaining_reads = 1 if readings else 2
    for allowance in (transport.logical_call_budget, getattr(transport, "logical_run_budget", None)):
        if allowance is None:
            continue
        budget = allowance.snapshot()
        if (budget["max_requests"] - budget["requests_used"] < remaining_reads
                or budget["max_output_tokens"] - budget["reserved_output_tokens"] < remaining_reads * initial_options["max_tokens"]):
            raise OfficialScopeReviewError("LOGICAL_BUDGET_EXHAUSTED")
    for stage in (("proposal",) if readings else ("source", "proposal")):
        prompt = scope_review_prompt(basis, source_reading=readings[0] if readings else None)
        request = {"version": SCOPE_REVIEW_VERSION, "basis_sha256": canonical_hash(basis),
                   "stage": stage, "prompt": prompt}
        messages = [{"role": "user", "content": transport._wire_contract_prompt(prompt, "official_source_scope_review")}]
        request["request_options"] = transport._completion_kwargs(messages, output_kind="official_source_scope_review")
        request_ref = store.put("raw_request", json.dumps(request, ensure_ascii=False).encode()).storage_ref
        try:
            response = transport.start(prompt=prompt, output_kind="official_source_scope_review")
        except Exception as exc:
            store.put("raw_response", json.dumps({
                "request_ref": request_ref, "status": "failed", "error_type": type(exc).__name__,
                "error_code": getattr(exc, "error_code", None),
                "call_metadata": getattr(exc, "error_metadata", {}),
            }, ensure_ascii=False).encode())
            raise
        response_ref = store.put("raw_response", response.model_dump_json().encode()).storage_ref
        receipts.append({"request_ref": request_ref, "response_ref": response_ref})
        sessions.append(response.session_id)
        reading = OfficialScopeReading.model_validate_json(response.text)
        scope_item_rejections(reading, basis, proposal=stage == "proposal")
        readings.append(reading)
    if len(set(sessions)) != 2:
        raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_DISAGREEMENT")
    proof = {"version": SCOPE_REVIEW_VERSION, "basis_sha256": canonical_hash(basis), "receipts": receipts,
             "validation_policy": "component-local/v1"}
    review_ref = store.put("evaluation_manifest", json.dumps(proof, ensure_ascii=False).encode()).storage_ref
    result = draft.model_copy(deep=True)
    updated = next(item for item in result.proposed_rules if item.official_code == official_code)
    for component in updated.components:
        # Completed outcomes supersede old clearance, including new uncertainty.
        component.source_scope_review_ref = review_ref
        binding = next(item for item in result.component_drafts
                       if item.proposed_component.rule_component_id == component.rule_component_id)
        binding.proposed_component = component.model_copy(deep=True)
    for component in updated.components:
        try:
            reviewed_scope_stages(source, result, updated, component, headings, store.read, heading_stages=heading_stages)
        except (OfficialScopeUnresolvedError, OfficialScopeRejectedError):
            continue
    return result


def validate_completed_scope_review(source, draft, *, official_code: str, store) -> None:
    """Replay every completed disposition, including legitimate new uncertainty."""
    rule = next(rule for rule in draft.proposed_rules if rule.official_code == official_code)
    headings = frozen_parent_scope_fragments(source, official_code,
        scope_has_stages=lambda text: bool(_source_review_stages([text])),
        is_substantive=lambda text: bool(_substantive_obligation_segments(text)))
    refs = {component.source_scope_review_ref for component in rule.components}
    if len(refs) != 1 or None in refs:
        raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_INVALID")
    for component in rule.components:
        try:
            reviewed_scope_stages(source, draft, rule, component, headings, store.read,
                heading_stages=[stage.value for stage in _source_review_stages(
                    [item.excerpt for item in headings], stage_aliases=frozen_review_stage_aliases(source))])
        except (OfficialScopeUnresolvedError, OfficialScopeRejectedError):
            continue
