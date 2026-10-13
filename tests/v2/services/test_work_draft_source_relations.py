"""Synthetic source relations: literal provenance and actual calculation consumers."""
from datetime import date
from hashlib import sha256
from types import SimpleNamespace

import pytest

from app.domain.contracts.enums import TruthValue
from app.domain.contracts.work_draft import WorkDraftSourcePage
from app.services.work_draft_semantics import SourceRelation, relation_inputs, validate_relations


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


@pytest.mark.parametrize("mutation", [None, "source", "target", "policy", "model", "truncated"])
def test_reuse_revalidates_actual_request_not_a_reconstructed_old_version(mutation):
    import json
    from app.domain.contracts.agents import ModelConfigContract
    from app.domain.contracts.enums import ReviewStage
    from app.services.work_draft_semantics import revalidate_saved_source_read, SEMANTIC_INSTRUCTIONS, SourceRelations
    model = ModelConfigContract(model_config_id="synthetic", provider="synthetic", model="fixture",
        reasoning_effort="high", parameters={"max_tokens": 65536, "prompt_version": "new-format"})
    frame = SimpleNamespace(source_pages=[page()], review_episode=SimpleNamespace(stage=ReviewStage.SCREENING,
        anchor_dates={}, model_dump=lambda **_: {"anchor_dates": {}}))
    material = {"stage": "screening", "anchor_dates": {}, "targets": [target()], "pages": [{
        "page_artifact_id": "page", "page_number": 1, "category": "study_chart", "text": page().effective_text}],
        "output_schema": SourceRelations.model_json_schema()}
    if mutation == "source": material["pages"][0]["text"] = "另一份资料"
    if mutation == "target": material["targets"][0] = target("inclusion")
    request = {"messages": [{"role": "user", "content":
        ("不同语义要求" if mutation == "policy" else SEMANTIC_INSTRUCTIONS) + "每个target_id恰好返回一次。\n" + json.dumps(material,ensure_ascii=False)}]}
    old_model = model.model_copy(update={"parameters": {"max_tokens": 65536, "prompt_version": "old-format"}}).model_dump(mode="json")
    if mutation == "model": old_model["model"] = "different-model"
    saved = {"model": old_model, "text": json.dumps({"results": [row().model_dump()]},ensure_ascii=False),
        "calls": [{"finish_reason": "length" if mutation == "truncated" else "stop", "response_model": "fixture", "request_artifact_sha256": "request"}]}
    class Artifacts:
        def read(self, ref): return json.dumps(saved,ensure_ascii=False).encode()
        def read_by_sha(self, kind, digest): return json.dumps(request,ensure_ascii=False).encode()
    original_result = relation_inputs(row(), target(), [page()])
    values, proofs = revalidate_saved_source_read({"raw_refs": ["response"], "results": {
        "component:infection": original_result}}, frame, [target()], model, Artifacts())
    assert bool(values) == (mutation is None)
    if values:
        assert values["component:infection"]["truth"] == "false" and proofs["component:infection"]["request_sha256"] == "request"


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
