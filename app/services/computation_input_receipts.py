"""Replayable calculation-source descriptions; agreement does not prove closure."""
from app.domain.contracts.computation_input import VERSION
from app.domain.publication import canonical_hash
from app.llm.computation_input import (
    ComputationInputRead, build_computation_input_messages, validate_computation_input_payload,
)
from app.services.computation_input_sources import load_computation_input_sources
from app.services.judgment_content_receipts import _reconstruct_judgment_content_lane_state
from app.storage.repositories import ScopeViolationError
from app.workflow.errors import InvalidJobDefinitionError

JOB_TYPE = "computation_input"
CONTRACT = "computation-input-job/v2"
PURPOSE = "supplied_computation_source_descriptions"
PROMPT_VERSION = VERSION
INPUT_FIELDS = ("candidate_job_id", "review_context_id", "review_context_sha256", "frozen_input_sha256",
                "comparison_sha256", "candidate_receipt_sha256s", "pairs", "identity_coverage", "input_sha256")


def rebuild_computation_input_sources(session, artifact_store, payload):
    if not {"input_version", *INPUT_FIELDS}.issubset(payload):
        raise InvalidJobDefinitionError("计算输入记录缺少原文或版本字段，不能复用旧结果")
    try:
        rebuilt = load_computation_input_sources(session, artifact_store,
            candidate_job_id=payload["candidate_job_id"], context_id=payload["review_context_id"])
    except ScopeViolationError as exc:
        raise InvalidJobDefinitionError(str(exc)) from exc
    if rebuilt != {"version": payload["input_version"], **{key: payload[key] for key in INPUT_FIELDS}}:
        raise InvalidJobDefinitionError("计算输入原文、方案声明或当前审核范围已变化")
    return rebuilt


def reconstruct_computation_input_lanes(**kwargs):
    return _reconstruct_judgment_content_lane_state(**kwargs,
        message_builder=build_computation_input_messages,
        payload_validator=validate_computation_input_payload, read_type=ComputationInputRead)


def _description_key(item):
    return (item.input_role, item.input_excerpt,
            None if item.input_ref is None else (item.input_ref.statement_index, item.input_ref.quote),
            item.collection_token, item.token_kind, item.collection_excerpt,
            item.date_role, item.date_text, item.date_excerpt)


def compose_computation_input_summary(*, payload, pairs, batches, lane_reads, lane_receipts):
    comparisons = []
    for batch in batches:
        groups = [item for item in pairs if item.pair_id in set(batch.pair_ids)]
        reads, receipts = lane_reads.get(batch.batch_sha256) or {}, lane_receipts.get(batch.batch_sha256) or {}
        expected = (batch.frozen_input_sha256, batch.batch_sha256,
                    canonical_hash(build_computation_input_messages(groups, batch)))
        if any(reads.get(lane) is None or not receipts.get(lane) for lane in ("main-A", "main-B")):
            raise InvalidJobDefinitionError("计算输入尚缺完整回答及调用记录")
        if len({(reads[lane].requested_provider, reads[lane].requested_model) for lane in ("main-A", "main-B")}) != 2:
            raise InvalidJobDefinitionError("同一模型不能冒充独立计算输入核实")
        answers = {}
        for lane in ("main-A", "main-B"):
            read = reads[lane]
            if read.lane != lane or (read.frozen_input_sha256, read.batch_sha256, read.messages_sha256) != expected:
                raise InvalidJobDefinitionError("计算输入回答的来源、提示或读道不一致")
            checked = validate_computation_input_payload(groups, read.payload.model_dump_json())
            answers[lane] = {item.pair_id: item for item in checked.results}
        for group in groups:
            left, right = (answers[lane][group.pair_id] for lane in ("main-A", "main-B"))
            descriptions = [{item.pair_id: item for item in answer.descriptions} for answer in (left, right)]
            agreed = [key for key in sorted(descriptions[0])
                      if _description_key(descriptions[0][key]) == _description_key(descriptions[1][key])]
            relationships = [{item.agreement_key() for item in answer.relations} for answer in (left, right)]
            comparisons.append({
                "group_id": group.pair_id, "identity_sha256": group.identity_sha256,
                "source_computation_sha256": canonical_hash(group.computation.model_dump(mode="json")),
                "agreed_source_descriptions": [descriptions[0][key].model_dump(mode="json") for key in agreed],
                "disputed_description_pair_ids": sorted(set(descriptions[0]) - set(agreed)),
                "agreed_relationships": [list(key) for key in sorted(relationships[0] & relationships[1])],
                "disputed_relationships": [list(key) for key in sorted(relationships[0] ^ relationships[1])],
                "lanes": {lane: answers[lane][group.pair_id].model_dump(mode="json") for lane in ("main-A", "main-B")},
                "lane_receipt_sha256s": {lane: list(receipts[lane]) for lane in ("main-A", "main-B")},
                "input_set_qualified": False, "clinical_scope_complete": False,
            })
    material = {"version": VERSION, "prompt_version": PROMPT_VERSION, "purpose": PURPOSE,
                **{key: payload[key] for key in INPUT_FIELDS if key != "pairs"},
                "batches": [batch.model_dump(mode="json") for batch in batches], "comparisons": comparisons,
                "accepted": False, "authorized_clinical_adoption": False, "clinically_qualified": False,
                "input_set_qualified": False, "clinical_scope_complete": False, "empty_selected_pairs": not pairs}
    return {**material, "summary_sha256": canonical_hash(material)}
