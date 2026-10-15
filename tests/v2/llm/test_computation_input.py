"""Source-local positive/counterfactual shapes; not clinical receipt evidence."""
import json

import pytest
from pydantic import ValidationError

from app.domain.contracts.binding_qualification import BindingQualificationPairContext, binding_qualification_pair_id
from app.domain.contracts.computation_input import VERSION, ComputationInputContext
from app.domain.publication import canonical_hash
from app.llm.computation_input import build_computation_input_messages, validate_computation_input_payload
from app.llm.observation_relation import relation_batch
from app.services.computation_input_sources import plan_computation_input_batches
from app.storage.repositories import ScopeViolationError


def group(*, excerpts=None):
    excerpts = excerpts or ["第一次采集 A；采集日期2026-08-20；静息心率70 bpm",
                            "第二次采集 B；采集日期2026-08-20；静息心率70 bpm"]
    computation = {"operator": "mean", "operator_ref": {"statement_index": 0, "quote": "均值"},
                   "input_refs": [{"statement_index": 0, "quote": "两次采集"}],
                   "missing_policy": "not_specified"}
    members = []
    for index, excerpt in enumerate(excerpts):
        fact_id, locator_id = f"f{index}", f"l{index}"
        identity = dict(candidate_job_id="synthetic", frozen_input_sha256="b" * 64,
            identity_field="predicate_identity_sha256", identity_sha256="c" * 64,
            fact_id=fact_id, fact_attribute="value", locator_id=locator_id, candidate_batch_sha256=None)
        member = BindingQualificationPairContext(**identity, pair_id=binding_qualification_pair_id(**identity),
            candidate_family="predicate", candidate_job_type="predicate_binding_candidates",
            candidate_contract="synthetic", comparison_sha256="d" * 64,
            condition={"predicate": {"source_computation": computation}},
            fact={"fact_id": fact_id, "value": 70, "unit": "bpm"},
            locator={"locator_id": locator_id, "excerpt": excerpt}, episode={"stage": "screening"},
            parent_source_context={}, source_policy_status="missing", lane_declarations={"main-A": {}, "main-B": {}},
            candidate_receipt_sha256s={"main-A": ["a" * 64], "main-B": ["e" * 64]})
        members.append(member)
    material = {"version": VERSION, "identity_sha256": "c" * 64,
                "candidate_job_id": "synthetic", "frozen_input_sha256": "b" * 64,
                "computation": computation, "members": [item.model_dump(mode="json") for item in
                                                         sorted(members, key=lambda item: item.pair_id)]}
    # Include defaults in the actual typed context, just as the production loader.
    from app.domain.contracts.source_computation import SourceComputation
    material["computation"] = SourceComputation(**computation).model_dump(mode="json")
    return ComputationInputContext(pair_id=canonical_hash(material), **material)


def answer(source):
    rows = []
    for member in source.members:
        excerpt = member.locator["excerpt"]
        token = "A" if " A；" in excerpt else "B"
        rows.append({"pair_id": member.pair_id, "collection_token": token,
            "token_kind": "collection_identifier", "collection_excerpt": excerpt.split("；")[0],
            "date_role": "collection_time", "date_text": "2026-08-20",
            "date_excerpt": "采集日期2026-08-20", "explanation": "仅对应原文标识与日期，不授权输入集。"})
    return {"results": [{"pair_id": source.pair_id, "descriptions": rows,
                         "relations": [], "unresolved_notes": []}]}


def test_same_day_same_value_source_descriptions_and_actual_batch_are_preserved():
    source = group()
    messages = build_computation_input_messages([source], relation_batch([source]))
    request = json.loads(messages[1]["content"][0]["text"])
    material = request["groups"][0]["sources"]
    assert material["required_pair_ids"] == sorted(item.pair_id for item in source.members)
    parsed = validate_computation_input_payload([source], json.dumps(answer(source)))
    assert len(parsed.results[0].descriptions) == 2
    assert parsed.results[0].relations == []  # Different descriptions are not independent-collection proof.
    assert plan_computation_input_batches([source], max_characters=100000) == [relation_batch([source])]


@pytest.mark.parametrize("mutation", ["missing", "other_pair", "other_source", "invented_token", "invented_date",
                                     "unknown_with_token", "clinical_verdict", "one_sided_relation",
                                     "wrong_input_source", "wrong_input_ref"])
def test_scope_and_source_counterfactuals_are_rejected(mutation):
    source, payload = group(), None
    payload = answer(source)
    result = payload["results"][0]
    if mutation == "missing":
        result["descriptions"].pop()
    elif mutation == "other_pair":
        result["pair_id"] = "e" * 64
    elif mutation == "other_source":
        result["descriptions"][0]["collection_excerpt"] = "另一受试者的采集编号"
    elif mutation == "invented_token":
        result["descriptions"][0]["collection_token"] = "C"
    elif mutation == "invented_date":
        result["descriptions"][0]["date_text"] = "2026-08-21"
    elif mutation == "unknown_with_token":
        result["descriptions"][0]["token_kind"] = "unresolved"
    elif mutation == "clinical_verdict":
        result["eligible"] = True
    elif mutation in {"wrong_input_source", "wrong_input_ref"}:
        result["descriptions"][0].update(input_role="raw_input",
            input_excerpt=source.members[0].locator["excerpt"],
            input_ref=source.computation.input_refs[0].model_dump(mode="json"))
        if mutation == "wrong_input_source":
            result["descriptions"][0]["input_excerpt"] = "另一受试者的输入原文"
        else:
            result["descriptions"][0]["input_ref"]["statement_index"] = 1
    else:
        result["relations"] = [{"left_pair_id": source.members[0].pair_id,
            "right_pair_id": source.members[1].pair_id, "relation": "distinct_acquisition",
            "left_excerpt": source.members[0].locator["excerpt"], "right_excerpt": "不存在的关系说明",
            "explanation": "不能用这项关系。"}]
    with pytest.raises(ValueError):
        validate_computation_input_payload([source], json.dumps(payload))


def test_whole_local_group_cannot_be_silently_truncated_and_scope_changes_identity():
    source = group()
    with pytest.raises(ScopeViolationError, match="不能截去"):
        plan_computation_input_batches([source], max_characters=1)
    changed = group(excerpts=["新的采集原文", "另一处原文"])
    assert changed.pair_id != source.pair_id
    material = source.model_dump(mode="json")
    material["members"][0]["episode"] = {"stage": "baseline"}
    material["pair_id"] = canonical_hash({key: value for key, value in material.items() if key != "pair_id"})
    with pytest.raises(ValidationError, match="不能混入"):
        ComputationInputContext.model_validate(material)
