"""Bounded source-object recovery uses synthetic sources, never clinical gold."""

from copy import deepcopy
import json

import pytest

from app.agents.evidence_normalizer_repair import EvidenceSourceObjectRepair
from app.agents.evidence_normalizer import (
    EvidenceNormalizerRunner, _schema_repair_prompt, _compact_schema,
    evidence_normalizer_json_schema, evidence_normalizer_prompt_template_sha256,
    DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE, build_evidence_normalizer_prompt,
)
from app.domain.variables.dictionary import VariableDef
from tests.v2.agents.test_evidence_normalizer_adapter import _input, _FakeTransport, _valid_output_dict


@pytest.mark.parametrize("field_sources", [False, True])
@pytest.mark.parametrize("variables", [False, True])
@pytest.mark.parametrize("provider_schema", [False, True])
def test_opted_in_runner_keeps_the_same_output_schema_for_repair(field_sources, variables, provider_schema):
    evidence = _input()
    if variables:
        evidence = evidence.model_copy(update={"variable_definitions": [VariableDef(
            variable_id="synthetic_history", label_zh="病史", value_type="boolean", domain="history")]})
    transport = _FakeTransport([("{", "same-session"), (json.dumps(_valid_output_dict()), "same-session")])
    transport.preserve_repair_schema = True
    transport.include_medication_field_sources = field_sources
    transport.enforces_output_json_schema = provider_schema
    schemas = []
    transport.set_output_schema = schemas.append
    result = EvidenceNormalizerRunner(max_schema_repairs=1, max_transport_retries=0).run(
        evidence, transport, prompt_template="按原文读取")
    assert result.status == "已解析"
    assert len(transport.start_prompts) == len(transport.repair_prompts) == 1
    session, repair = transport.repair_prompts[0]
    assert session == "same-session"
    expected = evidence_normalizer_json_schema(["synthetic_history"] if variables else None,
        include_medication_field_sources=field_sources)
    if variables or field_sources:
        assert schemas == [expected]
    if provider_schema:
        assert "输出结构：" not in repair
    else:
        initial_schema, _ = json.JSONDecoder().raw_decode(transport.start_prompts[0].split("输出结构：", 1)[1])
        repair_schema = json.loads(repair.split("输出结构：", 1)[1])
        assert initial_schema == repair_schema == expected
    assert "不得改用旧输出结构" in repair


def test_legacy_repair_and_prompt_identity_remain_exact():
    assert _schema_repair_prompt("合成错误").endswith("输出结构：" + _compact_schema())
    assert "不得改用旧输出结构" not in _schema_repair_prompt("合成错误")
    template = DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE
    assert evidence_normalizer_prompt_template_sha256(template) == "dd2d86d2da5d1ee69ea98aa6f7bb8854c3fa915c077f4b78f2af5c2cc4d3dbe8"
    assert evidence_normalizer_prompt_template_sha256(template, preserve_repair_schema=True) != evidence_normalizer_prompt_template_sha256(template)


@pytest.mark.parametrize("flag", [None, "true", 1])
def test_repair_schema_option_is_not_coerced(flag):
    with pytest.raises(ValueError, match="补答结构"):
        evidence_normalizer_prompt_template_sha256("读取", preserve_repair_schema=flag)
    with pytest.raises(ValueError, match="补答结构"):
        build_evidence_normalizer_prompt(_input(), prompt_template="读取", preserve_repair_schema=flag)


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
