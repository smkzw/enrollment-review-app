"""Source-local quarantine keeps siblings unchanged, never makes a clinical verdict."""
from copy import deepcopy
import hashlib
import json

import pytest

from app.agents.evidence_normalizer import EvidenceNormalizerRunner, DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE
from app.agents.evidence_candidate_partition import recover_source_local_candidates
from app.projections.normalizer_reference_aliases import NormalizerReferenceAliases
from tests.v2.agents.test_fact_context_sources import _payload, _source_input
from tests.v2.agents.test_evidence_normalizer_adapter import _FakeTransport


def _draft():
    original = _payload()
    broken = original["fact_candidates"][0]
    broken["assertion_basis"]["asserted_object"] = "不存在的对象"
    sibling = deepcopy(broken)
    sibling.update(candidate_ref="good", locator_ids=["loc-2"])
    sibling["assertion_basis"].update(asserted_object="项目乙", contextual_qualifiers=[])
    original["fact_candidates"].append(sibling)
    return original


@pytest.mark.parametrize("compact", [False, True])
@pytest.mark.parametrize("kind", ["object", "context", "prospective"])
def test_valid_sibling_retained_without_any_repair_or_semantic_rewrite(kind, compact):
    original = _draft()
    broken = original["fact_candidates"][0]
    if kind != "object":
        broken["assertion_basis"]["asserted_object"] = "项目乙"
    if kind == "context":
        broken["assertion_basis"]["contextual_qualifiers"][0]["label"] = "未记载的量表"
    if kind == "prospective":
        broken["assertion_scope"] = "prospective_or_conditional"
    aliases = NormalizerReferenceAliases.from_payload(_source_input().model_dump(mode="json"))
    raw = json.dumps(aliases.transform(original) if compact else original, ensure_ascii=False)
    transport = _FakeTransport([(raw, "single-read")])
    result = EvidenceNormalizerRunner(max_transport_retries=0, max_schema_repairs=0).run(
        _source_input(), transport, prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
        require_current_draft=True, compact_references=compact, allow_candidate_partition=True)
    assert result.status == "部分已解析"
    assert not transport.repair_prompts
    assert [item.candidate_id for item in result.final_output.fact_candidates] == ["good"]
    fact = result.final_output.fact_candidates[0]
    assert fact.canonical_value == 2 and fact.assertion_basis.assertion_text == "项目乙2"
    receipt = result.candidate_partition_receipt
    assert receipt["raw_output_sha256"] == hashlib.sha256(raw.encode()).hexdigest()
    assert receipt["original_response"] == raw
    assert receipt["retained_draft"]["fact_candidates"] == [original["fact_candidates"][1]]
    assert receipt["quarantined_candidate_refs"] == ["f1"]
    question = result.final_output.unresolved_items[-1]
    assert question.code == "candidate_source_validation_failed"
    assert question.gap_type is None and not question.affected_requirement_ids
    assert not result.final_output.exposure_candidates


def test_dependency_quarantine_never_shrinks_an_event_to_its_good_subset():
    original = _draft()
    original["event_candidates"] = [{"candidate_ref": "event", "event_type": "检查记录",
        "profile_lane": "test_exam_score", "duration_status": "single",
        "fact_candidate_refs": ["f1", "good"], "locator_ids": ["loc-2"],
        "candidate_source_semantics": "primary_source", "model_uncertainty": 0}]
    partition = recover_source_local_candidates(json.dumps(original, ensure_ascii=False), _source_input())
    assert not partition.output.event_candidates
    assert partition.receipt["quarantined_candidate_refs"] == ["event", "f1"]
    assert len(partition.output.unresolved_items) == 2
    assert partition.receipt["original_draft"] == original


@pytest.mark.parametrize("change", ["foreign", "duplicate", "unknown_top", "unknown_fact",
    "unknown_dependency", "unknown_classification", "all_bad", "bad_sibling", "damaged_json"])
def test_global_or_unlocalizable_faults_are_not_laundered_as_partial_success(change):
    original = _draft()
    if change == "foreign":
        original["fact_candidates"][0]["locator_ids"].append("other-patient")
    elif change == "duplicate":
        original["fact_candidates"][1]["candidate_ref"] = "f1"
    elif change == "unknown_top":
        original["published_facts"] = []
    elif change == "unknown_fact":
        original["fact_candidates"][0]["verified"] = True
    elif change == "unknown_dependency":
        original["event_candidates"] = [{"candidate_ref": "event", "fact_candidate_refs": ["absent"], "locator_ids": ["loc-2"]}]
    elif change == "unknown_classification":
        original["actual_exposure_fact_refs"] = ["absent"]
    elif change == "all_bad":
        original["fact_candidates"].pop()
    elif change == "bad_sibling":
        original["fact_candidates"][1]["model_uncertainty"] = 2
    text = json.dumps(original, ensure_ascii=False)
    if change == "damaged_json":
        text = text[:-1]
    with pytest.raises((ValueError, TypeError)):
        recover_source_local_candidates(text, _source_input())


def test_old_default_stays_failed_and_good_response_does_not_need_partition():
    original = _draft()
    for enabled in (False, True):
        payload = deepcopy(original)
        if enabled:
            payload["fact_candidates"][0]["assertion_basis"]["asserted_object"] = "项目乙"
        result = EvidenceNormalizerRunner(max_transport_retries=0, max_schema_repairs=0).run(
            _source_input(), _FakeTransport([(json.dumps(payload, ensure_ascii=False), "read")]),
            prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE, require_current_draft=True,
            allow_candidate_partition=enabled)
        assert result.candidate_partition_receipt is None
        assert (result.final_output is not None) == enabled


@pytest.mark.parametrize("fault", ["scope", "uncertainty", "nested", "event", "identifier", "missing_scope"])
def test_quarantining_a_source_error_cannot_hide_another_contract_error(fault):
    original = _draft()
    bad = original["fact_candidates"][0]
    bad["assertion_basis"].pop("contextual_qualifiers")
    if fault == "scope":
        bad["assertion_scope"] = "invalid-scope"
    elif fault == "uncertainty":
        bad["model_uncertainty"] = 2
    elif fault == "nested":
        bad["date_range"] = {"precision": "impossible"}
    elif fault == "identifier":
        bad.update(value_kind="identifier", unit="mg")
    elif fault == "missing_scope":
        bad["assertion_scope"] = None
    else:
        original["event_candidates"] = [{"candidate_ref": "event", "profile_lane": "test_exam_score",
            "duration_status": "single", "fact_candidate_refs": ["f1"], "locator_ids": ["loc-2"],
            "candidate_source_semantics": "primary_source", "model_uncertainty": 0}]
    with pytest.raises(ValueError):
        recover_source_local_candidates(json.dumps(original, ensure_ascii=False), _source_input())


def test_existing_unknown_date_fallback_still_preserves_its_question():
    original = _draft()
    original["fact_candidates"][1]["date_range"] = {"precision": "day",
        "source_text": "日期范围未能明确", "lower_bound": "2026-10-01", "upper_bound": "2026-10-02"}
    result = recover_source_local_candidates(json.dumps(original, ensure_ascii=False), _source_input())
    assert result.output.fact_candidates[0].date_range.precision.value == "unknown"
    assert any(item.code == "date_range_unclear" for item in result.output.unresolved_items)
    assert result.receipt["original_draft"] == original


def test_medication_closure_is_quarantined_without_losing_an_independent_measurement():
    original = _draft()
    bad = original["fact_candidates"][0]
    medicine = deepcopy(original["fact_candidates"][1])
    medicine.update(candidate_ref="medicine", profile_lane="medication")
    bad["profile_lane"] = "medication"
    original["fact_candidates"].append(medicine)
    original["actual_exposure_fact_refs"] = ["f1", "medicine"]
    original["exposure_candidates"] = [{"candidate_ref": "exposure", "medication_name": "来源用药",
        "duration_status": "single", "fact_candidate_refs": ["f1", "medicine"],
        "locator_ids": ["loc-2"], "candidate_source_semantics": "primary_source", "model_uncertainty": 0}]
    result = recover_source_local_candidates(json.dumps(original, ensure_ascii=False), _source_input())
    assert [item.candidate_id for item in result.output.fact_candidates] == ["good"]
    assert result.receipt["quarantined_candidate_refs"] == ["exposure", "f1", "medicine"]
    assert not result.output.exposure_candidates
    assert len(result.output.unresolved_items) == 3
    assert all("原答候选" not in item.reason for item in result.output.unresolved_items)
