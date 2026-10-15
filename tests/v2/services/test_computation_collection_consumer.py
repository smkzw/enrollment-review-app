"""Actual temporary jobs and sealed consumer; synthetic sources, not clinical gold."""
import json
from itertools import combinations

import pytest

from app.domain.contracts.enums import GapType, TruthValue
from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.facts import AssertionBasis, ClinicalFactV2, clinical_fact_stable_identity
from app.domain.contracts.predicate_binding import PredicateBindingFrozenInput, predicate_binding_frozen_input_sha256
from app.domain.contracts.rules import RuleSet
from app.domain.publication import canonical_hash
from app.evidence.artifacts import ArtifactStore
from app.llm.page_review_harness import PageCompletion
from app.llm.predicate_binding_batches import _batch, plan_binding_batches, project_binding_batch
from app.llm.predicate_binding_candidates import predicate_binding_prompt_input
from app.services.binding_qualification import BindingQualificationJobExecutor, enqueue_binding_qualification
from app.services.computation_input_job import ComputationInputJobExecutor, enqueue_computation_input
from app.services.frozen_review_calculation import calculate_frozen_review
from app.services.eligibility_review_projection import EligibilityReviewProjectionService
from app.services.predicate_binding_input import _frozen_component, _frozen_fact
from app.services.predicate_binding_job import PredicateBindingJobExecutor, enqueue_predicate_candidates
from app.services.qualified_binding_selection import build_receipt_verified_work_draft_selections
from app.workflow.runner import JobRunner
from app.workflow.jobstore import JobStore
from tests.v2.llm.test_predicate_binding_candidates import _route, _v2_accounting
from tests.v2.services.test_receipt_verified_work_draft_consumer import (
    _aligned_review_context, _qualification_payload_for_messages, _synthetic_material,
    POSITIVE_PREDICATE_ID,
)


def _collection_material(*, changed=False, duplicate=False, same_value=False, unit_variant=False,
                         unit_case_mismatch=False, shared_origin=False, duplicate_read_refs=False):
    authority, rule_set, frozen, seed, episode, _ = _synthetic_material(computation="single")
    data = rule_set.model_dump(mode="json")
    rule = data["rules"][0]
    predicate = rule["components"][0]["expression"]["children"][0]["predicate"]
    quote = "两次静息心率采集记录"
    clause = quote + "的均值等于72 bpm"
    predicate["source_clause"] = clause
    computation = predicate["source_computation"]
    computation["input_refs"][0]["quote"] = quote
    computation["input_selection"] = {"mode": "all", "source": {"statement_index": 0, "quote": quote}}
    computation["declared_input_count"] = {
        "value": 2, "number_text": "两", "source": {"statement_index": 0, "quote": quote}}
    rule["source_text"] = rule["source_text"].replace("一次静息心率记录的均值等于72 bpm", clause)
    rule_set = RuleSet.model_validate(data)
    facts, locators = [], []
    for key, value, unit, obj, text in (
        ("first", 72 if same_value else 70, "bpm", "静息心率",
         f"首次采集：静息心率 {72 if same_value else 70} bpm。"),
        ("second", 72 if same_value else 78 if changed else 74,
         "BPM" if unit_case_mismatch else " bpm " if unit_variant else "bpm", "静息心率",
         f"第二次采集：静息心率 {72 if same_value else 78 if changed else 74} bpm。"),
        ("other", 37, "℃", "体温", "体温 37℃，不是心率。"),
    ):
        names = [f"loc-{key}"] + ([f"loc-{key}-scan"] if duplicate and key == "first" else [])
        for name in names:
            locators.append(frozen.locators[0].model_copy(update={
                "locator_id": name, "target_id": name + "-target", "page_artifact_id": name + "-page",
                "source_document_version_id": name + "-doc", "excerpt": text,
                "source_text_sha256": canonical_hash(text), "text_end": len(text)}))
        kwargs = dict(authority=authority, fact_type=seed.fact_type, profile_lane=seed.profile_lane,
                      asserted_object=obj, polarity=seed.polarity, value=value, unit=unit, date_range=None)
        material = seed.model_dump(mode="json") | dict(
            fact_id=f"fact-{key}", value=value, unit=unit, asserted_object=obj, locator_ids=sorted(names),
            assertion_basis=AssertionBasis(asserted_object=obj, assertion_text=text, locator_id=names[0],
                                           source_text_sha256=canonical_hash(text)).model_dump(mode="json"),
            stable_identity=clinical_fact_stable_identity(**kwargs))
        facts.append(ClinicalFactV2.model_validate(material))
    if shared_origin:
        facts[:2] = [fact.model_copy(update={"source_observation_refs": ["same-observation"]})
                     for fact in facts[:2]]
    if duplicate_read_refs:
        facts[0] = facts[0].model_copy(update={"source_observation_refs": ["read-original", "read-scan"]})
    if same_value:
        first, second = facts[:2]
        assert first.stable_identity == second.stable_identity
        # Match actual publication: same semantic value is one fact with all source appearances.
        facts = [first.model_copy(update={
            "locator_ids": sorted(first.locator_ids + second.locator_ids),
            "source_observation_refs": ["observation-first", "observation-second"],
        }), facts[2]]
    material = frozen.model_dump(mode="json")
    material["components"] = [_frozen_component(rule_set.rules[0].components[0], rule_set.rules[0])]
    material["facts"] = [_frozen_fact(fact) for fact in facts]
    material["locators"] = sorted(locators, key=lambda item: item.locator_id)
    material.pop("frozen_input_sha256")
    identity_material = {key: material[key] for key in (
        "authority", "episode", "rule_set_id", "rule_set_revision", "protocol_version_id", "study_phase",
        "components", "facts", "locators", "documents")}
    identity_material.update(authority=authority, episode=episode, study_phase=frozen.study_phase)
    frozen = PredicateBindingFrozenInput(**material,
        frozen_input_sha256=predicate_binding_frozen_input_sha256(**identity_material))
    review = _aligned_review_context(authority=authority, rule_set=rule_set, clinical_fact=facts[0],
                                    clinical_facts=facts, episode=episode)
    return authority, rule_set, frozen, facts, review


@pytest.mark.parametrize("case", ["all", "batched", "duplicate_scan", "unknown_acquisition",
                                 "changed_value", "uncertain_background", "same_value",
                                 "same_value_unknown_token", "same_value_same_token",
                                 "different_value_same_token", "same_value_different_kind",
                                 "unit_variant", "unit_case_mismatch", "shared_origin", "lane_disagreement",
                                 "duplicate_read_refs", "duplicate_refs_unlinked"])
def test_collection_jobs_to_sealed_arithmetic_and_consumer(session_factory, data_paths, monkeypatch, case):
    authority, rules, frozen, facts, review = _collection_material(
        changed=case == "changed_value", duplicate=case in {
            "duplicate_scan", "duplicate_read_refs", "duplicate_refs_unlinked"},
        same_value=case.startswith("same_value"), unit_variant=case == "unit_variant",
        unit_case_mismatch=case == "unit_case_mismatch",
        shared_origin=case == "shared_origin",
        duplicate_read_refs=case in {"duplicate_read_refs", "duplicate_refs_unlinked"})
    if case == "same_value":
        assert frozen.facts[0].source_observation_refs == ["observation-first", "observation-second"]
    if case == "shared_origin":
        assert all(fact.source_observation_refs == ["same-observation"]
                   for fact in frozen.facts if fact.fact_id != "fact-other")
    monkeypatch.setattr("app.services.predicate_binding_job.build_predicate_binding_frozen_input",
                        lambda *_args, **_kwargs: frozen)
    monkeypatch.setattr("app.services.binding_qualification.build_predicate_binding_frozen_input",
                        lambda *_args, **_kwargs: frozen)
    monkeypatch.setattr("app.storage.review_context_repository.ReviewContextV2Repository.get",
                        lambda *_args: review)
    monkeypatch.setattr("app.services.review_candidate_scope.get_rule_set", lambda *_args: rules)
    routes = {lane: _route(lane=lane, model=f"synthetic-{lane.value}")
              for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)}
    artifacts = ArtifactStore(data_paths)
    candidate_reads = []

    async def candidate_completion(_route, messages, _budget):
        request = json.loads(messages[1]["content"][0]["text"])
        batch = request["frozen_input"].get("batch")
        if batch:
            planned = plan_binding_batches(frozen, predicate_binding_prompt_input(frozen),
                                           max_characters=batch_options["batch_max_characters"])
            universe = next(item.fact_ids for item in planned if item.batch_sha256 == batch["batch_sha256"])
        else:
            universe = [fact.fact_id for fact in facts]
        candidate_reads.append(tuple(universe))
        results = []
        for entry in frozen.components[0].trigger_predicates:
            positive = entry.predicate_id == POSITIVE_PREDICATE_ID
            selected = [fact for fact in facts if fact.fact_id in universe and positive and fact.asserted_object == "静息心率"]
            pairs = [{"fact_id": fact.fact_id, "fact_attribute": "value", "locator_id": key,
                      "object_correspondence": "supported", "attribute_correspondence": "derivation_operand",
                      "correspondence_explanation": "本次采集的原始读数，不是已计算的均值。"}
                     for fact in selected for key in fact.locator_ids]
            accounting = _v2_accounting(candidate_fact_ids=[fact.fact_id for fact in selected], universe=universe,
                disposition="uncertain" if not positive or case == "uncertain_background" else "noncorrespondence",
                reason_code="category_match_only" if not positive or case == "uncertain_background" else "different_object")
            for excluded in accounting["grouped_dispositions"]:
                if excluded["disposition"] == "noncorrespondence":
                    excluded["source_locator_ids"] = sorted(key for fact in facts
                        if fact.fact_id in excluded["fact_ids"] for key in fact.locator_ids)
            results.append({"predicate_identity_sha256": entry.predicate_identity_sha256,
                "status": "candidates" if pairs else "unresolved", "candidates": pairs,
                **({} if pairs else {"uncertainty": "本批没有对应读数"}), "fact_accounting": accounting})
        return PageCompletion(json.dumps({"results": results}, ensure_ascii=False), "stop", {})

    async def qualification_completion(_route, messages, _budget):
        payload = _qualification_payload_for_messages(messages)
        for item in payload["results"]:
            item.update(attribute_match="derivation_operand", direct_operand_usable="not_usable",
                        unresolved_reasons=["原始采集读数，均值尚未计算。"])
        return PageCompletion(json.dumps(payload, ensure_ascii=False), "stop", {})

    async def source_completion(_route, messages, _budget):
        request = json.loads(messages[1]["content"][0]["text"])
        results = []
        for group in request["groups"]:
            # Read exact source material from the request; no clinical gold supplied.
            excerpts = {row["locator_id"]: row["excerpt"] for row in group["sources"]["locators"]}
            pairs = group["sources"]["pairs"]
            descriptions, relations = [], []
            for pair in pairs:
                quote = excerpts[pair["locator_id"]]
                token = "首次采集" if pair["locator_id"].startswith("loc-first") else "第二次采集"
                if case in {"same_value_same_token", "different_value_same_token", "same_value_different_kind"}:
                    token = "采集"  # Both quotes contain it; distinctness is not established by different file IDs.
                unknown_token = case == "same_value_unknown_token" or (
                    case == "lane_disagreement" and _route.lane == PageReviewLane.MAIN_B)
                descriptions.append({"pair_id": pair["pair_id"], "input_role": "raw_input",
                    "input_excerpt": quote, "input_ref": group["computation"]["input_refs"][0],
                    "collection_token": None if unknown_token else token,
                    "token_kind": "unresolved" if unknown_token else "collection_identifier"
                        if case == "same_value_different_kind" and token == "采集"
                        and pair["locator_id"].startswith("loc-first") else "explicit_collection_ordinal",
                    "collection_excerpt": None if unknown_token else quote, "date_role": "unresolved", "date_text": None,
                    "date_excerpt": None, "explanation": "原文明确记录采集次序；不补采集日期。"})
            if case not in {"unknown_acquisition", "duplicate_refs_unlinked"}:
                for left, right in combinations(pairs, 2):
                    relations.append({"left_pair_id": left["pair_id"], "right_pair_id": right["pair_id"],
                        "relation": "same_acquisition" if left["locator_id"].startswith("loc-first")
                            and right["locator_id"].startswith("loc-first") else "distinct_acquisition",
                        "left_excerpt": excerpts[left["locator_id"]], "right_excerpt": excerpts[right["locator_id"]],
                        "explanation": "同次报告的复印件不另计；原文明示首次与第二次采集。"})
            results.append({"pair_id": group["group_id"], "descriptions": sorted(descriptions, key=lambda item: item["pair_id"]),
                            "relations": relations, "unresolved_notes": []})
        return PageCompletion(json.dumps({"results": results}, ensure_ascii=False), "stop", {})

    batch_options = {}
    if case == "batched":
        prompt = predicate_binding_prompt_input(frozen)
        sizes = [len(json.dumps(project_binding_batch(prompt, frozen,
                    _batch(frozen, [fact.fact_id], ["component-a"])), ensure_ascii=False, separators=(",", ":")))
                 for fact in facts]
        batch_options = {"batch_max_characters": max(sizes)}
    candidate = enqueue_predicate_candidates(session_factory, review_episode_id=authority.review_episode_id,
        component_ids=["component-a"], routes=routes, review_context_id=review.context_id, **batch_options)
    executor = PredicateBindingJobExecutor(session_factory, artifacts, routes, completion=candidate_completion)
    assert JobRunner(session_factory, {executor.job_type: executor}).run_job(candidate.job_id)
    with session_factory() as session:
        store = JobStore(session)
        assert store.get_job(candidate.job_id).state == "completed", [
            (step.step_id, step.state, step.error_code,
             (store.get_last_checkpoint(candidate.job_id, step.step_id) or (None, {}))[1].get("failure"))
            for step in store.list_steps(candidate.job_id) if step.state != "completed"] + [
            (step_id, checkpoint[1]["failure"]) for step_id in [step.step_id for step in store.list_steps(candidate.job_id)]
            if (checkpoint := store.get_last_checkpoint(candidate.job_id, step_id)) and "failure" in checkpoint[1]]
    qualification = enqueue_binding_qualification(session_factory, candidate_job_id=candidate.job_id,
                                                   routes=routes, artifact_store=artifacts)
    executor = BindingQualificationJobExecutor(session_factory, artifacts, routes, completion=qualification_completion)
    assert JobRunner(session_factory, {executor.job_type: executor}).run_job(qualification.job_id)
    source = enqueue_computation_input(session_factory, candidate_job_id=candidate.job_id,
        context_id=review.context_id, routes=routes, artifact_store=artifacts)
    executor = ComputationInputJobExecutor(session_factory, artifacts, routes, completion=source_completion)
    assert JobRunner(session_factory, {executor.job_type: executor}).run_job(source.job_id)
    with session_factory() as session:
        selections = build_receipt_verified_work_draft_selections(session, artifacts,
            qualification_job_id=qualification.job_id, computation_input_job_id=source.job_id)
    calculation = calculate_frozen_review(review, rules, work_draft_selections=selections)
    value, = calculation.computation_atom_evaluations["predicate"].values()
    proof = value.resolution["input_qualification"]
    assert proof["authorized_clinical_adoption"] is False
    assert len(proof["acquisition_fact_ids"]) == (3 if case == "duplicate_refs_unlinked" else 2)
    if case in {"unknown_acquisition", "uncertain_background", "same_value_unknown_token", "same_value_same_token",
                "different_value_same_token", "same_value_different_kind", "shared_origin", "lane_disagreement",
                "duplicate_refs_unlinked"}:
        assert value.result.truth == TruthValue.UNKNOWN
        assert not proof["input_set_qualified"]
        assert GapType.CALCULATION_CAPABILITY_UNAVAILABLE in calculation.components[0].result.gaps
        assert GapType.PROFESSIONAL_JUDGMENT not in calculation.components[0].result.gaps
    elif case == "unit_case_mismatch":
        assert proof["input_set_qualified"]
        assert value.result.truth == TruthValue.UNKNOWN
        assert "repeat_result_unit_unverified" in value.result.reason_codes
        assert value.resolution["exact_value"] is None
    else:
        assert proof["input_set_qualified"]
        assert value.result.truth == (TruthValue.FALSE if case == "changed_value" else TruthValue.TRUE)
        assert value.resolution["exact_value"] == {"numerator": "74" if case == "changed_value" else "72", "denominator": "1"}
        assert value.result.used_fact_ids == (["fact-first"] if case == "same_value" else ["fact-first", "fact-second"])
        assert "fact-other" not in proof["fact_ids"]
    if case == "batched":
        assert len(candidate_reads) == 6
        assert all(len(universe) == 1 for universe in candidate_reads)
    if case in {"duplicate_scan", "duplicate_read_refs"}:
        assert len(value.result.evidence_span_ids) == 3
        # All-input aggregation has no source-declared collection order.
        assert sorted(proof["acquisition_fact_ids"]) == [["fact-first"], ["fact-second"]]
    if case in {"duplicate_read_refs", "duplicate_refs_unlinked"}:
        assert next(item for item in frozen.facts if item.fact_id == "fact-first").source_observation_refs == [
            "read-original", "read-scan"]
    if case == "same_value":
        assert proof["acquisition_fact_ids"] == [["fact-first"], ["fact-first"]]
        assert len(proof["reused_fact_source_bindings"]) == 2
        assert value.result.evidence_span_ids == ["loc-first", "loc-second"]
    # Use the real frozen calculator and presentation consumer. Only the source
    # repository lookup is isolated to the same synthetic frozen locators.
    monkeypatch.setattr("app.services.eligibility_review_projection.EvidenceLocatorRepository.get_many",
                        lambda _self, ids: [item for item in frozen.locators if item.locator_id in ids])
    with session_factory() as session:
        projection = EligibilityReviewProjectionService()._project_frozen_work_draft(
            session, frozen=review, rule_set=rules, selections=(selections,))
    assert projection.work_draft_state == "current"
    rendered = next(item for item in projection.clauses if item.rule_component_id == "component-a")
    if value.result.truth != TruthValue.UNKNOWN:
        assert "2次采集" in rendered.reason
        assert "均值为" in rendered.reason
        assert {item.locator_id for item in rendered.fact_refs} == set(value.result.evidence_span_ids)
    else:
        assert "计算依据" in rendered.reason
        if not proof["input_set_qualified"]:
            assert rendered.gap_type == GapType.CALCULATION_CAPABILITY_UNAVAILABLE.value
    assert any(item.rule_component_id != "component-a" for item in projection.clauses)
