"""Two-lane source agreement; no relationship is yet an authorized replacement."""
from app.domain.contracts.observation_relation import OBSERVATION_RELATION_VERSION
from app.domain.publication import canonical_hash
from app.domain.observation_relation_graph import analyze_observation_relationships
from app.llm.observation_relation import (
    ObservationRelationRead, build_observation_relation_messages, validate_observation_relation_payload,
)
from app.services.judgment_content_receipts import _reconstruct_judgment_content_lane_state
from app.services.observation_relation_input import load_observation_relation_input
from app.workflow.errors import InvalidJobDefinitionError

JOB_TYPE = "observation_relation"
CONTRACT = "observation-relation-job/v5"
PURPOSE = "supplied_observation_relation"
PROMPT_VERSION = OBSERVATION_RELATION_VERSION
INPUT_FIELDS = (
    "candidate_job_id", "review_context_id", "review_context_sha256", "frozen_input_sha256",
    "comparison_sha256", "candidate_receipt_sha256s", "pairs", "identity_coverage", "input_sha256",
)


def rebuild_observation_relation_input(session, artifact_store, payload):
    rebuilt = load_observation_relation_input(
        session, artifact_store, candidate_job_id=payload["candidate_job_id"],
        context_id=payload["review_context_id"],
    )
    if rebuilt != {"version": payload["input_version"], **{key: payload[key] for key in INPUT_FIELDS}}:
        raise InvalidJobDefinitionError("观察关系原文与当前审核准备不一致")
    return rebuilt


def reconstruct_observation_relation_lanes(**kwargs):
    return _reconstruct_judgment_content_lane_state(
        **kwargs, message_builder=build_observation_relation_messages,
        payload_validator=validate_observation_relation_payload, read_type=ObservationRelationRead,
    )


def compose_observation_relation_summary(*, payload, pairs, batches, lane_reads, lane_receipts):
    comparisons = []
    for batch in batches:
        groups = [item for item in pairs if item.pair_id in set(batch.pair_ids)]
        reads = lane_reads.get(batch.batch_sha256) or {}
        receipts = lane_receipts.get(batch.batch_sha256) or {}
        expected = (batch.frozen_input_sha256, batch.batch_sha256,
                    canonical_hash(build_observation_relation_messages(groups, batch)))
        if any(reads.get(lane) is None or not receipts.get(lane) for lane in ("main-A", "main-B")):
            raise InvalidJobDefinitionError("观察关系尚缺完整双路回答及调用记录")
        if len({(reads[lane].requested_provider, reads[lane].requested_model)
                for lane in ("main-A", "main-B")}) != 2:
            raise InvalidJobDefinitionError("同一模型不能冒充两次独立观察关系核实")
        indexed = {}
        for lane in ("main-A", "main-B"):
            read = reads[lane]
            if read.lane != lane or (read.frozen_input_sha256, read.batch_sha256, read.messages_sha256) != expected:
                raise InvalidJobDefinitionError("观察关系回答的资料、提示或读道不一致")
            checked = validate_observation_relation_payload(groups, read.payload.model_dump_json())
            indexed[lane] = {item.pair_id: item for item in checked.results}
        for group in groups:
            left, right = (indexed[lane][group.pair_id] for lane in ("main-A", "main-B"))
            keys = [{link.agreement_key() for link in item.links} for item in (left, right)]
            common = keys[0] & keys[1]
            auxiliary_keys = [{item.agreement_key() for item in answer.auxiliary_associations}
                              for answer in (left, right)]
            auxiliary_common = auxiliary_keys[0] & auxiliary_keys[1]
            origins = [{item.fact_id: item for item in answer.origins} for answer in (left, right)]
            agreed_origins = {fact_id: origins[0][fact_id].role for fact_id in left.reviewed_fact_ids
                             if origins[0][fact_id].role == origins[1][fact_id].role
                             and origins[0][fact_id].role != "unresolved"}
            memberships = [{item.fact_id: item.membership for item in answer.episode_memberships or ()}
                           for answer in (left, right)]
            agreed_memberships = {key: value for key, value in memberships[0].items()
                                  if value != "unresolved" and memberships[1].get(key) == value}
            comparisons.append({
                "group_id": group.pair_id, "identity_sha256": group.identity_sha256,
                "agreed_relationships": [list(key) for key in sorted(common)],
                "agreed_episode_memberships": [
                    {"fact_id": key, "membership": value} for key, value in sorted(agreed_memberships.items())
                ],
                "agreed_auxiliary_associations": [list(key) for key in sorted(auxiliary_common)],
                "disputed_auxiliary_associations": [list(key) for key in sorted(auxiliary_keys[0] ^ auxiliary_keys[1])],
                "auxiliary_pairs_without_agreed_association": sorted(
                    set(left.reviewed_auxiliary_pair_ids) - {key[0] for key in auxiliary_common}),
                "relationship_graph": analyze_observation_relationships(
                    left.reviewed_fact_ids, sorted(common), origins=agreed_origins),
                "disputed_relationships": [list(key) for key in sorted(keys[0] ^ keys[1])],
                "facts_without_agreed_relationship": sorted(
                    set(left.reviewed_fact_ids) - {fact_id for key in common for fact_id in key[1:3]}),
                "agreed_origins": [
                    {"fact_id": fact_id, "role": role} for fact_id, role in sorted(agreed_origins.items())
                ],
                "unresolved_origin_fact_ids": [fact_id for fact_id in left.reviewed_fact_ids
                    if origins[0][fact_id].role != origins[1][fact_id].role
                    or origins[0][fact_id].role == "unresolved"],
                "lanes": {lane: indexed[lane][group.pair_id].model_dump(mode="json")
                          for lane in ("main-A", "main-B")},
                "lane_receipt_sha256s": {lane: list(receipts[lane]) for lane in ("main-A", "main-B")},
                "clinical_scope_complete": False, "replacement_authorized": False,
            })
    material = {
        "version": "observation-relation-summary/v5", "prompt_version": PROMPT_VERSION,
        "purpose": PURPOSE, **{key: payload[key] for key in INPUT_FIELDS if key != "pairs"},
        "batches": [batch.model_dump(mode="json") for batch in batches], "comparisons": comparisons,
        "accepted": False, "authorized_clinical_adoption": False, "clinically_qualified": False,
        "clinical_scope_complete": False, "empty_selected_pairs": not pairs,
    }
    return {**material, "summary_sha256": canonical_hash(material)}
