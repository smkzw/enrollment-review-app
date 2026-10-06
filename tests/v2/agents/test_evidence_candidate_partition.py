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
        "candidate_source_semantics": "同期客观结果", "model_uncertainty": 0}]
    partition = recover_source_local_candidates(json.dumps(original, ensure_ascii=False), _source_input())
    assert not partition.output.event_candidates
    assert partition.receipt["quarantined_candidate_refs"] == ["event", "f1"]
    assert len(partition.output.unresolved_items) == 2
    assert partition.receipt["original_draft"] == original


@pytest.mark.parametrize("compact", [False, True])
@pytest.mark.parametrize("dependent", [False, True])
def test_unexpressed_value_is_retained_without_guessing_or_repair(compact, dependent):
    original = _draft()
    bad = original["fact_candidates"][0]
    bad["assertion_basis"].update(asserted_object="项目乙", contextual_qualifiers=[])
    bad.update(raw_value=None, canonical_value=None)
    if dependent:
        original["event_candidates"] = [{"candidate_ref": "event", "event_type": "检查记录",
            "profile_lane": "test_exam_score", "duration_status": "single", "fact_candidate_refs": ["f1", "good"],
            "locator_ids": ["loc-2"], "candidate_source_semantics": "同期客观结果", "model_uncertainty": 0}]
    aliases = NormalizerReferenceAliases.from_payload(_source_input().model_dump(mode="json"))
    raw = json.dumps(aliases.transform(original) if compact else original, ensure_ascii=False)
    transport = _FakeTransport([(raw, "incomplete-value")])
    result = EvidenceNormalizerRunner(max_transport_retries=0, max_schema_repairs=1).run(
        _source_input(), transport, prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
        require_current_draft=True, compact_references=compact, allow_candidate_partition=True)
    assert result.status == "部分已解析" and not transport.repair_prompts
    assert [fact.candidate_id for fact in result.final_output.fact_candidates] == ["good"]
    assert result.final_output.fact_candidates[0].canonical_value == 2
    assert not result.final_output.event_candidates
    receipt = result.candidate_partition_receipt
    assert receipt["original_draft"] == original
    assert receipt["original_response"] == raw
    assert receipt["retained_draft"]["fact_candidates"] == [original["fact_candidates"][1]]
    assert receipt["quarantined_candidate_refs"] == (["event", "f1"] if dependent else ["f1"])
    question = next(item for item in result.final_output.unresolved_items if item.code == "normalized_value_missing")
    assert question.affected_locator_ids == bad["locator_ids"]
    assert question.affected_pages == [1, 2]
    assert question.gap_type is None and not question.affected_requirement_ids


@pytest.mark.parametrize("fault", ["foreign", "identifier", "duplicate", "shape", "unknown_scope"])
def test_unexpressed_value_does_not_hide_global_damage(fault):
    original = _draft()
    bad = original["fact_candidates"][0]
    bad["assertion_basis"].update(asserted_object="项目乙", contextual_qualifiers=[])
    bad.update(raw_value=None, canonical_value=None)
    if fault == "foreign":
        bad["locator_ids"] = ["other-subject"]
    elif fault == "identifier":
        bad["value_kind"] = "identifier"
    elif fault == "duplicate":
        original["fact_candidates"][1]["candidate_ref"] = "f1"
    elif fault == "shape":
        bad["invented_field"] = True
    else:
        bad["assertion_scope"] = None
    with pytest.raises(ValueError):
        recover_source_local_candidates(json.dumps(original, ensure_ascii=False), _source_input())


@pytest.mark.parametrize("compact", [False, True])
def test_missing_numeric_unit_isolated_without_guessing_or_model_repair(compact):
    original = _draft()
    bad = original["fact_candidates"][0]
    bad["assertion_basis"].update(asserted_object="项目乙", contextual_qualifiers=[])
    bad["unit"] = None
    original["event_candidates"] = [{"candidate_ref": "event", "event_type": "检查记录",
        "profile_lane": "test_exam_score", "duration_status": "single",
        "fact_candidate_refs": ["f1", "good"], "locator_ids": ["loc-2"],
        "candidate_source_semantics": "同期客观结果", "model_uncertainty": 0}]
    aliases = NormalizerReferenceAliases.from_payload(_source_input().model_dump(mode="json"))
    raw = json.dumps(aliases.transform(original) if compact else original, ensure_ascii=False)
    transport = _FakeTransport([(raw, "unit-read")])
    result = EvidenceNormalizerRunner(max_transport_retries=0, max_schema_repairs=1).run(
        _source_input(), transport, prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
        require_current_draft=True, compact_references=compact, allow_candidate_partition=True)
    assert result.status == "部分已解析" and not transport.repair_prompts
    assert [fact.candidate_id for fact in result.final_output.fact_candidates] == ["good"]
    assert not result.final_output.event_candidates
    receipt = result.candidate_partition_receipt
    assert receipt["policy"] == "evidence-candidate-partition/v3"
    assert receipt["quarantined_candidate_refs"] == ["event", "f1"]
    assert receipt["original_draft"] == original
    assert receipt["retained_draft"]["fact_candidates"] == [original["fact_candidates"][1]]
    questions = result.final_output.unresolved_items
    assert {item.code for item in questions} == {"numeric_unit_missing", "candidate_source_validation_failed"}
    assert all(item.gap_type is None for item in questions)


@pytest.mark.parametrize("fault", ["foreign", "duplicate", "unknown_dependency", "identifier", "uncertainty",
    "foreign_requirement", "source_semantics", "object_mismatch"])
def test_missing_unit_cannot_hide_global_or_other_contract_damage(fault):
    original = _draft()
    bad = original["fact_candidates"][0]
    bad["assertion_basis"].update(asserted_object="项目乙", contextual_qualifiers=[])
    bad["unit"] = None
    if fault == "foreign":
        bad["locator_ids"].append("other-patient")
    elif fault == "duplicate":
        original["fact_candidates"][1]["candidate_ref"] = "f1"
    elif fault == "identifier":
        bad.update(value_kind="identifier", raw_value=2, canonical_value=2)
    elif fault == "uncertainty":
        bad["model_uncertainty"] = 2
    elif fault == "foreign_requirement":
        bad["supported_requirement_ids"] = ["other-requirement"]
    elif fault == "source_semantics":
        bad["candidate_source_semantics"] = "not-a-source"
    elif fault == "object_mismatch":
        bad["asserted_object"] = "另一个对象"
    else:
        original["actual_exposure_fact_refs"] = ["unknown"]
    with pytest.raises(ValueError):
        recover_source_local_candidates(json.dumps(original, ensure_ascii=False), _source_input())


@pytest.mark.parametrize("reference_case", ["reverse", "duplicate", "foreign"])
def test_observation_reference_order_does_not_rewrite_or_hide_source_membership(reference_case):
    from tests.v2.agents.test_evidence_normalizer_adapter import _r3_input_with_accepted_fact
    inp, refs = _r3_input_with_accepted_fact()
    original = _draft()
    for index, fact in enumerate(original["fact_candidates"]):
        fact.update(asserted_object="糖尿病病史", raw_value=2 if index == 0 else "患者无糖尿病病史。",
            canonical_value=2 if index == 0 else "患者无糖尿病病史。",
            unit=None, locator_ids=["loc-1"], source_observation_refs=sorted(refs))
        fact["assertion_basis"].update(asserted_object="糖尿病病史", assertion_text="患者无糖尿病病史。",
            locator_id="loc-1", contextual_qualifiers=[])
    reference_ids = sorted(refs, reverse=True)
    if reference_case == "duplicate":
        reference_ids.append(reference_ids[0])
    elif reference_case == "foreign":
        reference_ids.append("other-patient-observation")
    original["unresolved_items"] = [{"code": "reading_pending", "message": "原件观察尚待核对",
        "affected_pages": [1], "affected_locator_ids": ["loc-1"],
        "affected_observation_refs": reference_ids, "reason": "原件内容保留，不先整理为事实。"},
        {"code": "page_pending", "message": "第二页待核", "affected_pages": [2],
            "affected_locator_ids": ["loc-2"], "reason": "本例仅核观察引用。"}]
    raw = json.dumps(original, ensure_ascii=False)
    if reference_case != "reverse":
        with pytest.raises(ValueError):
            recover_source_local_candidates(raw, inp)
        return
    result = recover_source_local_candidates(raw, inp)
    assert result.receipt["original_draft"] == original
    assert result.output.unresolved_items[0].affected_observation_refs == sorted(refs)
    assert next(q for q in result.output.unresolved_items if q.code == "numeric_unit_missing").affected_observation_refs == sorted(refs)
    assert result.receipt["retained_draft"]["fact_candidates"] == [original["fact_candidates"][1]]


def test_foreign_observation_on_missing_unit_candidate_is_rejected_before_deletion():
    from tests.v2.agents.test_evidence_normalizer_adapter import _r3_input_with_accepted_fact
    inp, refs = _r3_input_with_accepted_fact()
    original = _draft()
    bad = original["fact_candidates"][0]
    bad["assertion_basis"].update(asserted_object="项目乙", contextual_qualifiers=[])
    bad.update(unit=None, source_observation_refs=["other-patient-observation"])
    with pytest.raises(ValueError, match="本次已采信观察"):
        recover_source_local_candidates(json.dumps(original, ensure_ascii=False), inp)


def test_two_independent_observation_groups_keep_quarantined_group_as_a_question():
    from tests.v2.agents.test_evidence_normalizer_adapter import _r3_input_with_accepted_fact
    from app.domain.page_normalization import fact_normalization_key
    from app.domain.contracts.evidence_normalizer import page_review_input_scope_hash, evidence_normalizer_input_scope_hash
    from app.projections.page_review_sources import accepted_observations
    inp, group_a = _r3_input_with_accepted_fact()
    attachment = inp.page_review
    key, value, unit = fact_normalization_key("记录对象", "患者", context={"target_text": "患者"})
    reviews = []
    for review in attachment.reviews:
        extra = review.facts[0].model_copy(update={"observation_id": review.facts[0].observation_id + "-object",
            "field_name": "记录对象", "raw_text": "患者", "raw_value": "患者",
            "normalized_value": value, "normalized_unit": unit, "normalization_key": key})
        reviews.append(review.model_copy(update={"facts": [*review.facts, extra]}))
    reconciliation = attachment.reconciliations[0].model_copy(update={
        "accepted_fact_keys": sorted([*attachment.reconciliations[0].accepted_fact_keys, key])})
    attachment = attachment.model_copy(update={"reviews": reviews, "reconciliations": [reconciliation],
        "scope_sha256": page_review_input_scope_hash(coverage_id=attachment.coverage_id,
            clause_pack_sha256=attachment.clause_pack_sha256, entries=attachment.entries,
            reviews=reviews, reconciliations=[reconciliation])})
    inp = inp.model_copy(update={"page_review": attachment, "input_scope_sha256": evidence_normalizer_input_scope_hash(
        authority=inp.authority, logical_document_id=inp.logical_document_id, context=inp.context,
        related_requirements=inp.related_requirements, manifest_sha256=inp.manifest_sha256,
        completion_manifest_sha256=inp.completion_manifest_sha256, page_numbers=inp.page_numbers,
        pages=inp.pages, available_locator_ids=inp.available_locator_ids, available_locators=inp.available_locators,
        page_review=attachment)})
    group_b = sorted(item["source_observation_ref"] for item in accepted_observations(reviews, reconciliation,
        include_clause_signals=False) if item["observation"]["normalization_key"] == key)
    original = _draft()
    for index, fact in enumerate(original["fact_candidates"]):
        obj = "糖尿病病史" if index == 0 else "患者"
        fact.update(asserted_object=obj, raw_value=2 if index == 0 else "患者",
            canonical_value=2 if index == 0 else "患者", unit=None, locator_ids=["loc-1"],
            source_observation_refs=sorted(group_a) if index == 0 else group_b)
        fact["assertion_basis"].update(asserted_object=obj, assertion_text="患者无糖尿病病史。",
            locator_id="loc-1", contextual_qualifiers=[])
    original["unresolved_items"] = [{"code": "page_pending", "message": "第二页待核", "affected_pages": [2],
        "affected_locator_ids": ["loc-2"], "reason": "本例仅核观察引用闭合。"}]
    result = recover_source_local_candidates(json.dumps(original, ensure_ascii=False), inp)
    assert result.output.fact_candidates[0].source_observation_refs == group_b
    question = next(q for q in result.output.unresolved_items if q.code == "numeric_unit_missing")
    assert question.affected_observation_refs == sorted(group_a)
    assert result.receipt["quarantined_candidate_refs"] == ["f1"]


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
            "candidate_source_semantics": "同期客观结果", "model_uncertainty": 0}]
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
        "locator_ids": ["loc-2"], "candidate_source_semantics": "同期客观结果", "model_uncertainty": 0}]
    result = recover_source_local_candidates(json.dumps(original, ensure_ascii=False), _source_input())
    assert [item.candidate_id for item in result.output.fact_candidates] == ["good"]
    assert result.receipt["quarantined_candidate_refs"] == ["exposure", "f1", "medicine"]
    assert not result.output.exposure_candidates
    assert len(result.output.unresolved_items) == 3
    assert all("原答候选" not in item.reason for item in result.output.unresolved_items)


@pytest.mark.parametrize("name", ["来源用药", "同义但无原文支持的药名"])
def test_derived_source_failure_retains_measurements_and_full_exposure_dependencies(name):
    original = _draft()
    bad = original["fact_candidates"][0]
    bad["assertion_basis"].update(asserted_object="项目乙", contextual_qualifiers=[])
    original["fact_candidates"].append(deepcopy(bad))
    original["fact_candidates"][-1]["candidate_ref"] = "other-medicine"
    for fact in (bad, original["fact_candidates"][-1]):
        fact["profile_lane"] = "medication"
    original["actual_exposure_fact_refs"] = ["f1", "other-medicine"]
    original["exposure_candidates"] = [{"candidate_ref": "derived", "medication_name": name,
        "duration_status": "single", "fact_candidate_refs": ["f1", "other-medicine"],
        "locator_ids": ["loc-2"], "candidate_source_semantics": "同期客观结果", "model_uncertainty": 0}]
    # Two distinct cited objects keep the existing unique-name repair unavailable.
    original["fact_candidates"][-1]["assertion_basis"].update(asserted_object="项目", assertion_text="项目乙2")
    original["fact_candidates"][-1]["asserted_object"] = "项目"
    raw = json.dumps(original, ensure_ascii=False)
    transport = _FakeTransport([(raw, "read-once")])
    result = EvidenceNormalizerRunner(max_transport_retries=0, max_schema_repairs=1).run(
        _source_input(), transport, prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
        require_current_draft=True, compact_references=False, allow_candidate_partition=True)
    assert result.status == "部分已解析" and not transport.repair_prompts
    assert [fact.candidate_id for fact in result.final_output.fact_candidates] == ["good"]
    assert not result.final_output.exposure_candidates
    receipt = result.candidate_partition_receipt
    assert receipt["quarantined_candidate_refs"] == ["derived", "f1", "other-medicine"]
    assert any(row["code"] == "EvidenceDerivedSourceError" for row in receipt["failures"])
    assert receipt["retained_draft"]["fact_candidates"] == [original["fact_candidates"][1]]
