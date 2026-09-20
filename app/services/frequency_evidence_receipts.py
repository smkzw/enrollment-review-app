"""Preserve both readings; agreement alone is not clinical adoption."""
from app.domain.contracts.frequency_evidence import FREQUENCY_EVIDENCE_VERSION
from app.domain.publication import canonical_hash
from app.llm.frequency_evidence import (
    FrequencyEvidenceRead, build_frequency_evidence_messages, validate_frequency_evidence_payload,
)
from app.services.frequency_evidence_input import load_frequency_evidence_input
from app.services.judgment_content_receipts import _reconstruct_judgment_content_lane_state
from app.workflow.errors import InvalidJobDefinitionError

JOB_TYPE = "frequency_evidence"
CONTRACT = "frequency-evidence-job/v4"
PURPOSE = "source_frequency_statements"
PROMPT_VERSION = FREQUENCY_EVIDENCE_VERSION
INPUT_FIELDS = (
    "candidate_job_id", "review_context_id", "review_context_sha256", "frozen_input_sha256",
    "comparison_sha256", "candidate_receipt_sha256s", "pairs", "identity_coverage", "input_sha256",
)


def rebuild_frequency_evidence_input(session, artifact_store, payload):
    rebuilt = load_frequency_evidence_input(
        session, artifact_store, candidate_job_id=payload["candidate_job_id"], context_id=payload["review_context_id"],
    )
    if rebuilt != {"version": payload["input_version"], **{key: payload[key] for key in INPUT_FIELDS}}:
        raise InvalidJobDefinitionError("频次资料与当前审核准备不一致")
    return rebuilt


def reconstruct_frequency_evidence_lanes(**kwargs):
    return _reconstruct_judgment_content_lane_state(
        **kwargs, message_builder=build_frequency_evidence_messages,
        payload_validator=validate_frequency_evidence_payload, read_type=FrequencyEvidenceRead,
    )


def _indexed_sources(answer):
    return {canonical_hash(item.source_key()): item for item in answer.statements}


def _relationship_keys(answer):
    # Local output indices are not shared identities between independent models.
    identities = {item.statement_index: canonical_hash(item.source_key()) for item in answer.statements}
    return {(link.relation, *sorted((identities[link.left_statement_index], identities[link.right_statement_index])))
            for link in answer.relationships}


def compose_frequency_evidence_summary(*, payload, pairs, batches, lane_reads, lane_receipts):
    comparisons = []
    for batch in batches:
        groups = [item for item in pairs if item.pair_id in set(batch.pair_ids)]
        reads = lane_reads.get(batch.batch_sha256) or {}
        receipts = lane_receipts.get(batch.batch_sha256) or {}
        expected = (batch.frozen_input_sha256, batch.batch_sha256,
                    canonical_hash(build_frequency_evidence_messages(groups, batch)))
        if any(reads.get(lane) is None or not receipts.get(lane) for lane in ("main-A", "main-B")):
            raise InvalidJobDefinitionError("频次核对尚缺完整双路回答及回执")
        if len({(reads[lane].requested_provider, reads[lane].requested_model)
                for lane in ("main-A", "main-B")}) != 2:
            raise InvalidJobDefinitionError("同一模型不能冒充两次独立频次核对")
        indexed = {}
        for lane in ("main-A", "main-B"):
            read = reads[lane]
            if read.lane != lane or (read.frozen_input_sha256, read.batch_sha256, read.messages_sha256) != expected:
                raise InvalidJobDefinitionError("频次回答的输入、提示或读道不一致")
            checked = validate_frequency_evidence_payload(groups, read.payload.model_dump_json())
            indexed[lane] = {item.pair_id: item for item in checked.results}
        for group in groups:
            left, right = (indexed[lane][group.pair_id] for lane in ("main-A", "main-B"))
            statements = [_indexed_sources(answer) for answer in (left, right)]
            common = set(statements[0]) & set(statements[1])
            relationships = [_relationship_keys(answer) for answer in (left, right)]
            agreed_links = {key for key in relationships[0] & relationships[1]
                            if set(key[1:]) <= common}
            comparisons.append({
                "group_id": group.pair_id, "identity_sha256": group.identity_sha256,
                "agreed_statement_sha256s": sorted(common),
                "disputed_statement_sha256s": sorted(set(statements[0]) ^ set(statements[1])),
                "agreed_relationships": [list(key) for key in sorted(agreed_links)],
                "disputed_relationships": [list(key) for key in sorted(
                    (relationships[0] | relationships[1]) - agreed_links)],
                "lanes": {lane: indexed[lane][group.pair_id].model_dump(mode="json")
                          for lane in ("main-A", "main-B")},
                "lane_receipt_sha256s": {lane: list(receipts[lane]) for lane in ("main-A", "main-B")},
                "clinical_scope_complete": False, "replacement_authorized": False,
            })
    material = {
        "version": "frequency-evidence-summary/v4", "prompt_version": PROMPT_VERSION, "purpose": PURPOSE,
        **{key: payload[key] for key in INPUT_FIELDS if key != "pairs"},
        "batches": [batch.model_dump(mode="json") for batch in batches], "comparisons": comparisons,
        "accepted": False, "authorized_clinical_adoption": False, "clinically_qualified": False,
        "clinical_scope_complete": False, "empty_selected_pairs": not pairs,
    }
    return {**material, "summary_sha256": canonical_hash(material)}
