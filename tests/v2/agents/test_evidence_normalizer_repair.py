"""Bounded source-object recovery uses synthetic sources, never clinical gold."""

from copy import deepcopy
import json

import pytest

from app.agents.evidence_normalizer_repair import EvidenceSourceObjectRepair


def _previous():
    return {
        "schema_version": "phase5/normalizer-draft/v5",
        "fact_candidates": [
            {"candidate_ref": "finding", "assertion_scope": "observed_state",
             "asserted_object": "部位甲检查", "polarity": "negated",
             "raw_value": True, "canonical_value": True, "unit": None,
             "locator_ids": ["loc-a", "loc-b"], "date_range": None,
             "assertion_basis": {"asserted_object": "部位甲检查",
                                 "assertion_text": "部位甲未检", "locator_id": "loc-a"}},
            {"candidate_ref": "reading", "asserted_object": "项目乙", "canonical_value": 7},
        ],
        "event_candidates": [{"candidate_ref": "event", "fact_candidate_refs": ["reading"]}],
        "exposure_candidates": [], "unresolved_items": [],
    }


def _literal(previous):
    proposed = deepcopy(previous)
    fact = proposed["fact_candidates"][0]
    fact.update(asserted_object="部位甲", polarity="affirmed",
                raw_value="部位甲未检", canonical_value="部位甲未检")
    fact["assertion_basis"]["asserted_object"] = "部位甲"
    return proposed


def _plan(previous):
    return EvidenceSourceObjectRepair(json.dumps(previous, ensure_ascii=False), ("finding",),
                                      set_fields={"locator_ids", "fact_candidate_refs"})


def test_literal_record_repair_preserves_source_and_siblings():
    previous = _previous()
    proposed = _literal(previous)
    proposed["fact_candidates"][0]["locator_ids"].reverse()
    plan = _plan(previous)
    plan.validate(json.dumps(proposed, ensure_ascii=False))
    assert len(plan.precondition_sha256) == 64
    assert "不重新提取整页" in plan.instruction()
    assert previous == _previous()


@pytest.mark.parametrize("polarity", ["affirmed", "negated"])
@pytest.mark.parametrize("object_level", ["both", "basis_only", "fact_only"])
def test_boolean_object_cannot_lose_its_property(polarity, object_level):
    previous = _previous()
    previous["fact_candidates"][0]["polarity"] = polarity
    proposed = deepcopy(previous)
    if object_level != "basis_only":
        proposed["fact_candidates"][0]["asserted_object"] = "部位甲"
    if object_level != "fact_only":
        proposed["fact_candidates"][0]["assertion_basis"]["asserted_object"] = "部位甲"
    with pytest.raises(ValueError, match="布尔命题"):
        _plan(previous).validate(json.dumps(proposed, ensure_ascii=False))


@pytest.mark.parametrize("mutation", [
    "delete", "append", "reorder", "sibling_value", "event", "unresolved",
    "source_text", "source_locator", "date", "unit", "renumber", "invent_text",
])
def test_scope_cannot_be_expanded_by_whole_response_repair(mutation):
    previous = _previous()
    proposed = _literal(previous)
    fact = proposed["fact_candidates"][0]
    if mutation == "delete":
        proposed["fact_candidates"].pop()
    elif mutation == "append":
        proposed["fact_candidates"].append({"candidate_ref": "extra"})
    elif mutation == "reorder":
        proposed["fact_candidates"].reverse()
    elif mutation == "sibling_value":
        proposed["fact_candidates"][1]["canonical_value"] = 8
    elif mutation == "event":
        proposed["event_candidates"][0]["fact_candidate_refs"] = ["finding"]
    elif mutation == "unresolved":
        proposed["unresolved_items"].append({"code": "source_missing"})
    elif mutation == "source_text":
        fact["assertion_basis"]["assertion_text"] = "部位甲正常"
    elif mutation == "source_locator":
        fact["assertion_basis"]["locator_id"] = "loc-b"
    elif mutation == "date":
        fact["date_range"] = {"source_text": "今日"}
    elif mutation == "unit":
        fact["unit"] = "unitless"
    elif mutation == "renumber":
        fact["candidate_ref"] = "new-finding"
    else:
        fact["raw_value"] = fact["canonical_value"] = "部位甲已检且正常"
    with pytest.raises(ValueError):
        _plan(previous).validate(json.dumps(proposed, ensure_ascii=False))


def test_text_object_repair_does_not_change_the_measured_value():
    previous = _previous()
    fact = previous["fact_candidates"][0]
    fact.update(raw_value=7, canonical_value=7, polarity="affirmed", unit="分")
    proposed = deepcopy(previous)
    proposed["fact_candidates"][0]["asserted_object"] = "项目"
    proposed["fact_candidates"][0]["assertion_basis"]["asserted_object"] = "项目"
    _plan(previous).validate(json.dumps(proposed))
    proposed["fact_candidates"][0]["canonical_value"] = 8
    with pytest.raises(ValueError, match="未授权"):
        _plan(previous).validate(json.dumps(proposed))


def test_original_frozen_scope_survives_a_bad_proposal():
    previous = _previous()
    plan = _plan(previous)
    bad = _literal(previous)
    bad["fact_candidates"][1]["canonical_value"] = 9
    with pytest.raises(ValueError):
        plan.validate(json.dumps(bad))
    plan.validate(json.dumps(_literal(previous)))


@pytest.mark.parametrize("raw", ['{"fact_candidates":[],"fact_candidates":[]}',
                                 '{"fact_candidates":NaN}', '[]'])
def test_unreliable_previous_json_cannot_authorize_a_repair(raw):
    with pytest.raises(ValueError):
        EvidenceSourceObjectRepair(raw, ("finding",), set_fields=set())
