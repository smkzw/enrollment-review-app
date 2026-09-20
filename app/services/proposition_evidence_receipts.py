"""Rebuild pair-local proposition results from original product call receipts."""
from __future__ import annotations

from app.domain.contracts.proposition_evidence import PROPOSITION_EVIDENCE_VERSION
from app.domain.publication import canonical_hash
from app.llm.proposition_evidence import (
    PropositionEvidenceRead, build_proposition_evidence_messages,
    validate_proposition_evidence_payload,
)
from app.services.judgment_content_receipts import _reconstruct_judgment_content_lane_state
from app.services.proposition_evidence_comparison import compare_proposition_evidence
from app.services.proposition_evidence_input import load_proposition_evidence_input
from app.workflow.errors import InvalidJobDefinitionError

JOB_TYPE = "proposition_evidence"
CONTRACT = "proposition-evidence-job/v3"
PURPOSE = "pair_local_proposition_evidence"
PROMPT_VERSION = PROPOSITION_EVIDENCE_VERSION
SUMMARY_VERSION = "proposition-evidence-summary/v3"
INPUT_FIELDS = (
    "candidate_job_id", "review_context_id", "review_context_sha256",
    "frozen_input_sha256", "comparison_sha256", "candidate_receipt_sha256s",
    "pairs", "skipped_pairs", "identity_coverage", "input_sha256",
)


def rebuild_proposition_evidence_input(session, artifact_store, payload):
    rebuilt = load_proposition_evidence_input(
        session, artifact_store, candidate_job_id=payload["candidate_job_id"],
        context_id=payload["review_context_id"],
    )
    expected = {"version": payload["input_version"],
                **{key: payload[key] for key in INPUT_FIELDS}}
    if rebuilt != expected:
        raise InvalidJobDefinitionError("原文核实材料与当前审核准备或原始回答不一致")
    return rebuilt


def reconstruct_proposition_evidence_lanes(**kwargs):
    return _reconstruct_judgment_content_lane_state(
        **kwargs, message_builder=build_proposition_evidence_messages,
        payload_validator=validate_proposition_evidence_payload,
        read_type=PropositionEvidenceRead,
    )


def compose_proposition_evidence_summary(*, payload, pairs, batches, lane_reads, lane_receipts):
    comparisons = []
    for batch in batches:
        reads = lane_reads.get(batch.batch_sha256) or {}
        if any(reads.get(lane) is None for lane in ("main-A", "main-B")):
            raise InvalidJobDefinitionError("原文核实尚缺一次完整的独立读取")
        batch_pairs = [pair for pair in pairs if pair.pair_id in set(batch.pair_ids)]
        comparison = compare_proposition_evidence(
            batch_pairs, batch, (reads["main-A"], reads["main-B"]),
        )
        receipts = lane_receipts.get(batch.batch_sha256) or {}
        if any(not receipts.get(lane) for lane in ("main-A", "main-B")):
            raise InvalidJobDefinitionError("原文核实缺少两次独立读取的原始记录")
        comparisons.append({**comparison, "lane_receipt_sha256s": {
            lane: list(receipts[lane]) for lane in ("main-A", "main-B")}})
    material = {
        "version": SUMMARY_VERSION, "prompt_version": PROMPT_VERSION, "purpose": PURPOSE,
        **{key: payload[key] for key in INPUT_FIELDS if key != "pairs"},
        "batches": [batch.model_dump(mode="json") for batch in batches],
        "selected_pair_ids": sorted(pair.pair_id for pair in pairs),
        "comparisons": comparisons, "empty_selected_pairs": not pairs,
        "accepted": False, "authorized_clinical_adoption": False,
        "clinically_qualified": False, "scope": "pair_local",
        "observation_scope_verified": False,
    }
    return {**material, "summary_sha256": canonical_hash(material)}


def verify_completed_proposition_evidence(session, artifact_store, job_id):
    from app.services.content_job_verification import verify_completed_content_job
    from app.services.proposition_evidence_job import PropositionEvidenceJobExecutor

    return verify_completed_content_job(session, artifact_store, job_id, definition=PropositionEvidenceJobExecutor)
