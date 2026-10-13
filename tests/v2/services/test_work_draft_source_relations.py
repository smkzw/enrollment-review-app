"""Synthetic source relations: literal provenance and actual calculation consumers."""
from datetime import date
from hashlib import sha256
from types import SimpleNamespace

import pytest

from app.domain.contracts.enums import TruthValue
from app.domain.contracts.work_draft import WorkDraftSourcePage
from app.services.work_draft_semantics import SourceRelation, relation_inputs, validate_relations


def test_source_reason_display_keeps_clinical_values_but_not_wire_vocabulary():
    from app.services.work_draft_projection import display_source_reason
    reason = "P16明确否认，T01故relation=refutes；site记录CS，2025-08-08 ALT 57.8 U/L。"
    shown = display_source_reason(reason)
    assert "P16" not in shown and "T01" not in shown and "refutes" not in shown
    assert "原文明示不符合该条件" in shown and "研究中心" in shown
    assert "CS，2025-08-08 ALT 57.8 U/L" in shown


def test_source_reason_display_translates_scope_fields_not_clinical_excerpt_values():
    from app.services.work_draft_projection import display_source_reason
    reason = "本条件requires_professional_judgment=false；applicable_population未声明；observed_value/observed_unit未填；ALT 57.8 U/L。"
    shown = display_source_reason(reason)
    assert "本条件不额外要求研究者判断" in shown
    assert "条款限定的适用人群未声明" in shown and "原始读数/原始单位未填" in shown
    assert "ALT 57.8 U/L" in shown


def test_qualified_inapplicability_does_not_display_missing_applicable_patient_evidence():
    from app.services.work_draft_projection import display_source_reason
    prefix = "已找到相关原文，但尚不足以证明本条件，不能当作未见记录。"
    reason = prefix + "原件证明applicable=no；本条的人群要求不适用。"
    assert display_source_reason(reason, decision="not_applicable") == "原件证明有据不适用；本条的人群要求不适用。"
    assert display_source_reason(reason, decision="indeterminate").startswith(prefix)


def page(text="病历记载：否认近期感染。", *, complete=True, category="study_chart", key="page"):
    return WorkDraftSourcePage(source_document_version_id="document", page_artifact_id=key,
        page_number=1, effective_text=text, effective_text_sha256=sha256(text.encode()).hexdigest(),
        document_category=category, extraction_complete=complete)


def target(kind="exclusion"):
    return {"target_id": "component:infection", "kind": kind,
            "atom": {"predicate": {"comparator": "exists"}}}


def row(**values):
    return SourceRelation(target_id=values.get("target_id", "component:infection"), relation=values.get("relation", "refutes"),
        applicable=values.get("applicable", "yes"), object_matches=values.get("object_matches", True),
        time_matches=values.get("time_matches", True), quotes=values.get("quotes", [
            {"page_artifact_id": "page", "excerpt": "否认近期感染"}]), reason="对应病历明确否认。")


def test_verified_chart_relation_uses_original_page_not_fake_fact():
    result = validate_relations({"results": [row().model_dump()]}, [target()], [page()])
    inputs = relation_inputs(result[0], target(), [page()])
    assert inputs["truth"] == TruthValue.FALSE.value
    assert inputs["source_read_refs"][0]["excerpt"] == "否认近期感染"
    assert "fact_id" not in inputs["source_read_refs"][0]


def test_pending_targets_share_short_batch_without_dropping_reused_targets_or_changing_inputs():
    from app.services.work_draft_semantics import source_batches, BATCH_SIZE
    targets = [{"target_id": str(index), "payload": {"value": index}} for index in range(122)]
    pending = {"0", "18", "35", "50", "68", "78", "91", "104", "119"}
    reusable = {target["target_id"]: {} for target in targets if target["target_id"] not in pending}
    batches = source_batches(targets, reusable)
    assert len(batches) == 8 and all(len(batch) <= BATCH_SIZE for batch in batches)
    assert {target["target_id"] for target in batches[0] if target["target_id"] not in reusable} == pending
    assert all(target["target_id"] in reusable for batch in batches[1:] for target in batch)
    assert {id(target) for batch in batches for target in batch} == {id(target) for target in targets}
    assert [target["target_id"] for target in targets] == [str(index) for index in range(122)]
    assert source_batches([], {}) == [[]]


def test_product_batch_execution_revalidates_whole_frozen_target_scope_then_filters(monkeypatch):
    from app.domain.contracts.agents import ModelConfigContract
    from app.domain.publication import canonical_hash
    from app.services import work_draft_review as service, work_draft_semantics as semantics
    targets = [{"target_id": str(index)} for index in range(122)]
    pending = {"0", "18", "35", "50", "68", "78", "91", "104", "119"}
    reused = {target["target_id"]: {"truth": "unknown"} for target in targets if target["target_id"] not in pending}
    proofs = {key: {"raw_response_ref": f"response:{key}"} for key in reused}
    batches = semantics.source_batches(targets, reused)
    model = ModelConfigContract(model_config_id="synthetic", provider="synthetic", model="fixture", reasoning_effort="high")
    rules = SimpleNamespace(model_dump=lambda **_: {"rules": "frozen"})
    authority = SimpleNamespace(review_episode_id="episode", rule_set_id="rules", rule_set_revision=1)
    frame = SimpleNamespace(work_draft=True, review_run_id="run", authority=authority,
        rule_set_sha256=canonical_hash(rules.model_dump()))
    closed = []
    class Session:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def close(self): closed.append(True)
    monkeypatch.setattr(service, "ReviewContextV2Repository", lambda _: SimpleNamespace(get=lambda _: frame))
    monkeypatch.setattr(service, "authority_from_active_episode", lambda *_: authority)
    monkeypatch.setattr(service, "get_rule_set", lambda *_: rules)
    monkeypatch.setattr(service, "JobStore", lambda _: SimpleNamespace(list_steps=lambda _: []))
    monkeypatch.setattr(semantics, "targets_for_review", lambda *_: targets)
    checked = []
    def reuse(session, store, frozen, current_targets, current_model, artifacts):
        assert current_targets is targets  # A subset would discard old full-group proof.
        checked.append(True)
        return reused, proofs
    def read(frozen, batch, current_model, artifacts, *, reused, reuse_proofs):
        assert closed and current_model == model
        assert batch is batches[0]
        expected = {t["target_id"] for t in batch} - pending
        assert set(reused) == expected == set(reuse_proofs)
        assert len(expected) == 7
        return {"results": reused, "reuse_proofs": reuse_proofs, "pending": 9}
    monkeypatch.setattr(service, "_reusable_source_reads", reuse)
    monkeypatch.setattr(semantics, "read_source_relations", read)
    context = SimpleNamespace(job_type=service.JOB_TYPE, job_id="job", step_id="semantic:0000",
        job_payload={"context_id": "context", "review_run_id": "run", "calculation_version": service.CALCULATION_VERSION,
            "semantic_model": model.model_dump(mode="json"), "semantic_batches": batches})
    result = service.WorkDraftReviewService(Session, object()).execute(context)
    assert checked and result["pending"] == 9


@pytest.mark.parametrize("change,expected", [(None, True), ("subject", False), ("file", False),
    ("visit", False), ("variable", False)])
def test_product_reuse_across_rule_revision_requires_same_patient_source_visit_and_variables(monkeypatch, change, expected):
    import json
    from app.domain.contracts.facts import FactAuthority
    from app.services import work_draft_review as service, work_draft_semantics as semantics
    authority = FactAuthority(project_id="project", subject_id="subject", review_episode_id="episode", episode_revision=2,
        protocol_version_id="new", rule_set_id="rules", rule_set_revision=2, evidence_snapshot_v2_id="snapshot",
        complete_processing_revision_id="processing")
    old_authority = authority.model_copy(update={"episode_revision": 1, "protocol_version_id": "old", "rule_set_revision": 1,
        **({"subject_id": "other-patient"} if change == "subject" else {})})
    old = SimpleNamespace(authority=old_authority, source_pages=[page()], review_episode=SimpleNamespace(workflow_stage_id="old-stage"))
    current = SimpleNamespace(authority=authority, source_pages=[page()], review_episode=SimpleNamespace(workflow_stage_id="new-stage"))
    variable = SimpleNamespace(variable_id="observation", model_dump=lambda **_: {"unit": "different"})
    old_rules = SimpleNamespace(rule_set_id="rules", revision=1, study_phase="same", variable_definitions=[])
    new_rules = SimpleNamespace(rule_set_id="rules", revision=2, study_phase="same",
        variable_definitions=[variable] if change == "variable" else [])
    payload = json.dumps({"context_id": "previous"})
    job = SimpleNamespace(job_id="old-job", payload_json=payload, payload_sha256=sha256(payload.encode()).hexdigest())
    session = SimpleNamespace(scalars=lambda _: SimpleNamespace(all=lambda: [job]))
    monkeypatch.setattr(service, "ReviewContextV2Repository", lambda _: SimpleNamespace(get=lambda _: old))
    monkeypatch.setattr(service, "get_rule_set", lambda _, key, rev: old_rules if rev == 1 else new_rules)
    monkeypatch.setattr(service, "AppendRepository", lambda *_: SimpleNamespace(get=lambda key:
        SimpleNamespace(sha256="different" if change == "file" and key == "new" else "same-file")))
    import app.storage.repositories as repositories
    monkeypatch.setattr(repositories, "list_workflow_stages_for_rule_set", lambda _, key, rev: [SimpleNamespace(
        workflow_stage_id="old-stage" if rev == 1 else "new-stage",
        model_dump=lambda **_: {"visit": "other" if change == "visit" and rev == 2 else "same"})])
    previous_targets = [target()]
    monkeypatch.setattr(semantics, "targets_for_review", lambda frame, rules: previous_targets)
    seen = []
    def revalidate(checkpoint, frame, targets, model, store, *, previous_targets=None):
        assert frame is current and previous_targets == [target()]
        seen.append(True)
        return {"component:infection": {"truth": "false"}}, {"component:infection": {"raw_response_ref": "response"}}
    monkeypatch.setattr(semantics, "revalidate_saved_source_read", revalidate)
    store = SimpleNamespace(list_steps=lambda _: [SimpleNamespace(step_id="semantic:0000")],
        get_last_checkpoint=lambda *_: ("checkpoint", {"raw_refs": ["response"]}))
    accepted, proofs = service._reusable_source_reads(session, store, current, [target()], object(), object())
    assert bool(accepted) == bool(proofs) == bool(seen) == expected


def test_unique_line_wrap_restores_exact_original_quote_without_a_new_model_answer():
    from app.services.work_draft_semantics import split_valid_relations
    original = page("病历记载：否认近期\n感染。")
    accepted, failed = split_valid_relations({"results": [row().model_dump()]}, [target()], [original])
    assert not failed and accepted["component:infection"]["truth"] == "false"
    assert accepted["component:infection"]["source_format_restored"]
    assert accepted["component:infection"]["source_read_refs"][0]["excerpt"] == "否认近期\n感染"


@pytest.mark.parametrize("original,quote", [
    ("否认近期\n感染；否认近期\n感染", "否认近期感染"),
    ("读数1\n2mg", "读数12mg"),
    ("病历记录，否认感染", "病历记录,否认感染"),
    ("读数1 2mg", "读数12mg"),
    ("否认近期感染", "没有近期感染"),
])
def test_line_wrap_mapping_rejects_ambiguity_numeric_merging_and_changed_words(original, quote):
    from app.services.work_draft_semantics import source_excerpt
    assert source_excerpt(original, quote) is None


@pytest.mark.parametrize("change", [
    {"quotes": [{"page_artifact_id": "other-patient", "excerpt": "否认近期感染"}]},
    {"quotes": [{"page_artifact_id": "page", "excerpt": "未感染"}]},
    {"quotes": []},
])
def test_unverified_positive_or_negative_relation_is_rejected(change):
    with pytest.raises(ValueError):
        validate_relations({"results": [row(**change).model_dump()]}, [target()], [page()])


@pytest.mark.parametrize("change", [{"time_matches": False}, {"object_matches": False},
    {"relation": "not_found"}])
def test_valid_quote_with_uncertain_dimensions_is_retained_but_never_determinate(change):
    validated = validate_relations({"results": [row(**change).model_dump()]}, [target()], [page()])[0]
    result = relation_inputs(validated, target(), [page()])
    assert result["truth"] == "unknown" and not result["policy"]
    assert result["source_read_refs"][0]["excerpt"] == "否认近期感染"


@pytest.mark.parametrize("kind,complete,category,expected", [
    ("exclusion", True, "study_chart", TruthValue.FALSE),
    ("inclusion", True, "study_chart", TruthValue.UNKNOWN),
    ("exclusion", False, "study_chart", TruthValue.UNKNOWN),
    ("exclusion", True, "objective_report", TruthValue.UNKNOWN),
])
def test_missing_chart_judgment_is_scoped_policy_not_invented_denial(kind, complete, category, expected):
    inputs = relation_inputs(row(relation="not_found", quotes=[]), target(kind), [page(complete=complete, category=category)])
    assert inputs["truth"] == expected.value
    if expected == TruthValue.FALSE:
        assert inputs["policy"]
        assert inputs["source_read_refs"][0]["excerpt"] is None


def test_uncertain_record_does_not_become_not_seen_policy():
    inputs = relation_inputs(row(relation="unclear", object_matches=False), target(), [page()])
    assert inputs["truth"] == TruthValue.UNKNOWN.value and not inputs["policy"]


@pytest.mark.parametrize("change", [{"object_matches": False}, {"time_matches": False},
    {"relation": "conflict", "quotes": [{"page_artifact_id": "page", "excerpt": "否认近期感染"}] * 2}])
def test_inapplicability_cannot_hide_unverified_identity_time_or_conflict(change):
    scoped = target()
    scoped["atom"]["predicate"]["applicable_population"] = "指定人群"
    with pytest.raises(ValueError, match="不能同时确认"):
        validate_relations({"results": [row(applicable="no", **change).model_dump()]}, [scoped], [page()])


def test_inapplicability_requires_rule_scope_and_keeps_a_verified_quote_not_a_denial():
    read = row(applicable="no", relation="unclear")
    with pytest.raises(ValueError, match="未声明适用人群"):
        validate_relations({"results": [read.model_dump()]}, [target()], [page()])
    scoped = target()
    scoped["atom"]["predicate"]["applicable_population"] = "指定人群"
    valid = validate_relations({"results": [read.model_dump()]}, [scoped], [page()])[0]
    result = relation_inputs(valid, scoped, [page()])
    assert result["applicable"] == "no" and result["truth"] == "unknown" and not result["policy"]
    assert result["source_read_refs"][0]["excerpt"] == "否认近期感染"


def test_missing_duplicate_or_extra_targets_are_rejected():
    for rows in ([], [row(), row()], [row(target_id="unknown")]):
        with pytest.raises(ValueError):
            validate_relations({"results": [x.model_dump() for x in rows]}, [target()], [page()])


def test_conflict_requires_actual_opposing_quotes():
    with pytest.raises(ValueError):
        validate_relations({"results": [row(relation="conflict").model_dump()]}, [target()], [page()])


def test_future_visit_page_not_borrowed_from_later_node():
    from app.domain.contracts.common import DateValue
    from app.domain.contracts.enums import AnchorType, DatePrecision, ReviewStage
    from app.services.work_draft_semantics import source_pages_for_review
    frame = SimpleNamespace(review_episode=SimpleNamespace(stage=ReviewStage.SCREENING,
        anchor_dates={AnchorType.SCREENING_DATE: DateValue(value=date(2026, 1, 1), precision=DatePrecision.DAY)}),
        source_pages=[page("就诊时间:2026-01-01\n当前病历。"),
                      page("就诊时间:2026-01-15\n后续病历。", key="future")])
    assert [p.page_artifact_id for p in source_pages_for_review(frame)] == ["page"]


def test_default_work_graph_compatible_and_multiple_batches_durable():
    from app.graph.subject_graph import work_draft_steps
    assert [x[0] for x in work_draft_steps()] == ["calculate", "semantic", "compose", "save"]
    steps = list(work_draft_steps(3))
    assert steps[-2] == ("compose", ("semantic:0002",))
    assert steps[2] == ("semantic:0001", ("semantic:0000",))


def test_one_bad_quote_does_not_erase_valid_siblings():
    from app.services.work_draft_semantics import split_valid_relations
    other = {**target(), "target_id": "component:other"}
    valid, failed = split_valid_relations({"results": [row().model_dump(),
        row(target_id="component:other", quotes=[{"page_artifact_id": "page", "excerpt": "不存在的摘录"}]).model_dump()]},
        [target(), other], [page()])
    assert set(valid) == {"component:infection"} and set(failed) == {"component:other"}
    assert valid["component:infection"]["truth"] == "false"


def test_monthly_quota_is_detected_through_transport_wrapper():
    from app.services.work_draft_semantics import provider_is_blocked
    class QuotaError(RuntimeError):
        status_code = 429
    quota = QuotaError("monthly limit")
    wrapper = RuntimeError("transport failed")
    wrapper.__cause__ = quota
    assert provider_is_blocked(wrapper)
    assert not provider_is_blocked(RuntimeError("invalid schema"))


def test_source_reader_retries_only_bad_target_and_preserves_first_answer():
    import json
    from app.domain.contracts.enums import ReviewStage
    from app.services.work_draft_semantics import read_source_relations
    other = {**target(), "target_id": "component:other"}
    model = SimpleNamespace(model_dump=lambda **_: {"provider": "synthetic", "model": "fixture"})
    frame = SimpleNamespace(source_pages=[page()], review_episode=SimpleNamespace(stage=ReviewStage.SCREENING,
        anchor_dates={}, model_dump=lambda **_: {"anchor_dates": {}}))
    prompts = []
    class Transport:
        def propose_question_classifications(self, *, prompt, output_schema):
            prompts.append(prompt)
            wire = json.loads(prompt.split("\n", 1)[1])
            values = [row(target_id=t["target_id"], quotes=[{"page_artifact_id": "P01",
                "excerpt": "伪造摘录" if len(prompts) == 1 and t["target_id"] == "T02" else "否认近期感染"}]).model_dump()
                for t in wire["targets"]]
            return SimpleNamespace(text=json.dumps({"results": values}, ensure_ascii=False))
    class Artifacts:
        def put(self, kind, body):
            return SimpleNamespace(sha256=sha256(body).hexdigest(), storage_ref=f"artifacts/{kind}/{sha256(body).hexdigest()}")
    result = read_source_relations(frame, [target(), other], model, Artifacts(), transport_factory=lambda _: Transport())
    assert len(prompts) == 2 and set(result["results"]) == {"component:infection", "component:other"}
    second = json.loads(prompts[1].split("\n", 1)[1])
    assert [t["target_id"] for t in second["targets"]] == ["T02"]
    assert "error" not in result and len(result["raw_refs"]) == 2


@pytest.mark.parametrize("value,unit,relation,expected", [
    (25, "mg/L", "supports", "true"),
    (25, "mg/L", "refutes", "true"),
    (None, None, "supports", "unknown"),
    (250, "mg/L", "supports", "unknown"),
    (25, "g/L", "supports", "unknown"),
])
def test_numeric_source_relation_must_use_literal_operands_and_code_comparison(value, unit, relation, expected):
    numeric_target = {**target(), "atom": {"predicate": {"predicate_id": "marker", "subject": "受试者",
        "attribute": "检验指标", "comparator": "gte", "value": 20, "unit": "mg/L"}},
        "variable": {"variable_id": "marker", "label_zh": "检验指标", "value_type": "number",
            "canonical_unit": "mg/L", "unit_conversions": {}, "plausible_range": [0, 1000], "domain": "lab"}}
    source = page("检验指标：25 mg/L。")
    relation_row = row(relation=relation, quotes=[{"page_artifact_id": "page", "excerpt": source.effective_text}]).model_copy(
        update={"observed_value": value, "observed_unit": unit})
    assert relation_inputs(relation_row, numeric_target, [source])["truth"] == expected


def test_compact_input_preserves_clinical_dependencies_and_only_maps_declared_aliases():
    from app.services.work_draft_semantics import wire_target, decode_source_aliases
    original = {**target(), "component_id": "host-only", "atom": {"predicate": {
        "predicate_id": "host-predicate", "comparator": "gte", "value": 4, "unit": "day",
        "dependency": {"component_id": "source-relation-must-remain"}, "not_known": None}}}
    compact = wire_target(original)
    assert "component_id" not in compact and "predicate_id" not in compact["atom"]["predicate"]
    assert compact["atom"]["predicate"]["dependency"]["component_id"] == "source-relation-must-remain"
    assert compact["atom"]["predicate"]["value"] == 4 and original["component_id"] == "host-only"
    decoded = decode_source_aliases({"results": [row(target_id="T01", quotes=[{
        "page_artifact_id": "P01", "excerpt": "否认近期感染"}]).model_dump()]},
        {"targets": {"T01": "component:infection"}, "pages": {"P01": "page"}})
    assert decoded["results"][0]["target_id"] == "component:infection"
    assert decoded["results"][0]["quotes"][0]["page_artifact_id"] == "page"


def test_exact_scope_echo_is_not_a_missing_target_but_other_fields_still_rejected():
    from app.services.work_draft_semantics import source_result_envelope
    material = {"version": "scope", "stage": "screening", "anchor_dates": {"screening_date": "2026-01-01"}}
    payload = {**material, "results": []}
    assert source_result_envelope(payload, material) == {"results": []}
    for change in ({"stage": "baseline"}, {"version": "different"}, {"exclusion_triggered": False}):
        with pytest.raises(ValueError):
            source_result_envelope({**payload, **change}, material)


@pytest.mark.parametrize("mutation", [None, "wrap", "disagreement", "source", "target", "policy", "model", "truncated"])
def test_reuse_revalidates_actual_request_not_a_reconstructed_old_version(mutation):
    import json
    from app.domain.contracts.agents import ModelConfigContract
    from app.domain.contracts.enums import ReviewStage
    from app.services.work_draft_semantics import revalidate_saved_source_read, SEMANTIC_INSTRUCTIONS, SourceRelations
    model = ModelConfigContract(model_config_id="synthetic", provider="synthetic", model="fixture",
        reasoning_effort="high", parameters={"max_tokens": 65536, "prompt_version": "new-format"})
    source = page("病历记载：否认近期\n感染。") if mutation == "wrap" else page()
    if mutation == "disagreement": source = page("近期感染。否认近期感染。")
    frame = SimpleNamespace(source_pages=[source], review_episode=SimpleNamespace(stage=ReviewStage.SCREENING,
        anchor_dates={}, model_dump=lambda **_: {"anchor_dates": {}}))
    material = {"version": "input-v3", "stage": "screening", "anchor_dates": {}, "targets": [target()], "pages": [{
        "page_artifact_id": "page", "page_number": 1, "category": "study_chart", "text": source.effective_text}],
        "output_schema": SourceRelations.model_json_schema()}
    if mutation == "source": material["pages"][0]["text"] = "另一份资料"
    if mutation == "target": material["targets"][0] = target("inclusion")
    request = {"messages": [{"role": "user", "content":
        ("不同语义要求" if mutation == "policy" else SEMANTIC_INSTRUCTIONS) + "每个target_id恰好返回一次。\n" + json.dumps(material,ensure_ascii=False)}]}
    old_model = model.model_copy(update={"parameters": {"max_tokens": 65536, "prompt_version": "old-format"}}).model_dump(mode="json")
    if mutation == "model": old_model["model"] = "different-model"
    saved = {"model": old_model, "text": json.dumps({"results": [row().model_dump()]},ensure_ascii=False),
        "calls": [{"finish_reason": "length" if mutation == "truncated" else "stop", "response_model": "fixture", "request_artifact_sha256": "request"}]}
    if mutation == "disagreement":
        saved["text"] = json.dumps({"version": "input-v3", "results": [row().model_dump()]}, ensure_ascii=False)
    class Artifacts:
        def read(self, ref):
            value = saved
            if ref == "conflicting":
                value = {**saved, "text": json.dumps({"version": "input-v3", "results": [row(relation="supports",
                    quotes=[{"page_artifact_id": "page", "excerpt": "近期感染。"}]).model_dump()]}, ensure_ascii=False)}
            return json.dumps(value,ensure_ascii=False).encode()
        def read_by_sha(self, kind, digest): return json.dumps(request,ensure_ascii=False).encode()
    original_result = relation_inputs(row(), target(), [page()])
    refs = ["response", "conflicting"] if mutation == "disagreement" else ["response"]
    values, proofs = revalidate_saved_source_read({"raw_refs": refs, "results": {} if mutation in {"wrap", "disagreement"} else {
        "component:infection": original_result}}, frame, [target()], model, Artifacts())
    assert bool(values) == (mutation in {None, "wrap", "disagreement"})
    if values:
        assert values["component:infection"]["truth"] == ("unknown" if mutation == "disagreement" else "false")
        assert proofs["component:infection"]["request_sha256"] == "request"
        if mutation == "disagreement":
            assert values["component:infection"]["conflict"] and len(values["component:infection"]["source_read_refs"]) == 2


@pytest.mark.parametrize("change,expected", [(None, {"component:infection", "component:other"}),
    ("removed", {"component:infection"}), ("meaning", {"component:other"}), ("tampered", set()),
    ("context_missing", {"component:other"}), ("context_changed", {"component:other"})])
def test_rule_only_revision_reuses_unchanged_targets_after_full_original_request_verification(change, expected):
    import json
    from app.domain.contracts.agents import ModelConfigContract
    from app.domain.contracts.enums import ReviewStage
    from app.services.work_draft_semantics import revalidate_saved_source_read, SEMANTIC_INSTRUCTIONS, SourceRelations
    previous = [target(), {**target(), "target_id": "component:other"}]
    if change == "context_changed":
        previous[0] = {**previous[0], "source_context": {"purpose": "旧限定"}}
    current = previous[:1] if change == "removed" else [target("inclusion"), previous[1]] if change == "meaning" else previous
    if change in {"context_missing", "context_changed"}:
        current = [{**previous[0], "source_context": {"purpose": "新增限定"}}, previous[1]]
    model = ModelConfigContract(model_config_id="synthetic", provider="synthetic", model="fixture", reasoning_effort="high")
    source = page()
    frame = SimpleNamespace(source_pages=[source], review_episode=SimpleNamespace(stage=ReviewStage.SCREENING,
        anchor_dates={}, model_dump=lambda **_: {"anchor_dates": {}}))
    material = {"version": "old", "stage": "screening", "anchor_dates": {}, "targets": previous,
        "pages": [{"page_artifact_id": "page", "page_number": 1, "category": "study_chart", "text": source.effective_text}],
        "output_schema": SourceRelations.model_json_schema()}
    if change == "tampered":
        material = {**material, "targets": [target("inclusion"), previous[1]]}
    request = {"messages": [{"role": "user", "content": SEMANTIC_INSTRUCTIONS + "每个target_id恰好一次。\n" + json.dumps(material)}]}
    rows = [row(target_id=t["target_id"]) for t in previous]
    saved = {"model": model.model_dump(mode="json"), "text": json.dumps({"results": [r.model_dump() for r in rows]}),
        "calls": [{"finish_reason": "stop", "response_model": "fixture", "request_artifact_sha256": "request"}]}
    class Artifacts:
        def read(self, _): return json.dumps(saved).encode()
        def read_by_sha(self, *_): return json.dumps(request).encode()
    checkpoint = {"raw_refs": ["response"], "results": {
        t["target_id"]: relation_inputs(r, t, [source]) for r, t in zip(rows, previous)}}
    accepted, proofs = revalidate_saved_source_read(checkpoint, frame, current, model, Artifacts(),
        previous_targets=current if change == "context_missing" else previous)
    assert set(accepted) == set(proofs) == expected
    assert all(value["truth"] == "false" for value in accepted.values())


def test_chart_role_override_does_not_change_normalizer_role(monkeypatch):
    from app import config
    from app.services.work_draft_semantics import runtime_model
    normalizer = (config.EVIDENCE_NORMALIZER_PROVIDER, config.EVIDENCE_NORMALIZER_MODEL)
    monkeypatch.setattr(config, "WORK_DRAFT_SEMANTIC_PROVIDER", "cms-router")
    monkeypatch.setattr(config, "WORK_DRAFT_SEMANTIC_MODEL", "glm-5.3-flash")
    monkeypatch.setattr(config, "WORK_DRAFT_SEMANTIC_REASONING_EFFORT", "high")
    monkeypatch.setattr(config, "WORK_DRAFT_SEMANTIC_MAX_TOKENS", 65536)
    model = runtime_model()
    assert (model.provider, model.model, model.reasoning_effort) == ("cms-router", "glm-5.3-flash", "high")
    assert model.parameters["max_tokens"] == 65536
    assert (config.EVIDENCE_NORMALIZER_PROVIDER, config.EVIDENCE_NORMALIZER_MODEL) == normalizer


@pytest.mark.parametrize("literal,value,unit,expected", [
    ("25.0 mg/L", 25, "mg/L", "true"),
    ("−25 mg/L", 25, "mg/L", "unknown"),
    ("25 mg/L", 25, "g/L", "unknown"),
    ("0.025 g/L", 0.025, "g/L", "true"),
])
def test_numeric_quote_preserves_sign_decimal_and_full_unit(literal, value, unit, expected):
    numeric_target = {**target(), "atom": {"predicate": {"predicate_id": "marker", "subject": "受试者",
        "attribute": "检验指标", "comparator": "gte", "value": 20, "unit": "mg/L"}},
        "variable": {"variable_id": "marker", "label_zh": "检验指标", "value_type": "number",
            "canonical_unit": "mg/L", "unit_conversions": {"g/L": 1000}, "plausible_range": [0, 1000], "domain": "lab"}}
    source = page("检验指标：" + literal)
    relation_row = row(relation="supports", quotes=[{"page_artifact_id": "page", "excerpt": source.effective_text}]).model_copy(
        update={"observed_value": value, "observed_unit": unit})
    assert relation_inputs(relation_row, numeric_target, [source])["truth"] == expected
