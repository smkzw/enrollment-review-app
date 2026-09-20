"""Reference checks only; these synthetic candidates are not clinical gold."""
import json
import asyncio
from types import SimpleNamespace

import pytest

from app.llm.predicate_binding_candidates import (
    build_predicate_binding_messages, validate_predicate_candidates,
    read_predicate_candidates, PredicateCandidateReadError,
    predicate_binding_prompt_input,
    candidate_value_shape,
)
from app.llm.page_review_harness import PageReaderRoute, PageCompletion
from app.domain.contracts.page_review import PageReviewLane
from app.llm.page_review_transport_options import page_completion_options
from tests.v2.services.test_predicate_binding_input import (
    _component_contract, _fact_record, _frozen_input, _locator_record, _sha,
)


def _case(*, source="合成排除原文"):
    component = _component_contract(["first", "second"], "component-a", source_clause=source)
    frozen = _frozen_input([component], [_fact_record("fact-a", _sha("fact-a"), ["loc-a"])], [_locator_record("loc-a")])
    result = {
        "results": [{
            "predicate_identity_sha256": p.predicate_identity_sha256,
            "status": "candidates",
            "candidates": [{"fact_id": "fact-a", "fact_attribute": "value", "locator_id": "loc-a",
                            "object_correspondence": "uncertain", "attribute_correspondence": "uncertain",
                            "correspondence_explanation": "待独立语义核对"}],
        } for p in component.trigger_predicates]
    }
    return frozen, result


def test_one_fact_can_be_a_candidate_for_multiple_predicates():
    frozen, payload = _case()
    result = validate_predicate_candidates(frozen, json.dumps(payload))
    assert len(result.results) == 2
    assert all(item.candidates[0].fact_id == "fact-a" for item in result.results)
    assert "truth" not in result.model_dump()


@pytest.mark.parametrize("attribute,value,shape", [
    ("value", 25, "numeric_value"),
    ("value", "某诊断", "non_numeric_value"),
    ("value", "25年", "non_numeric_value"),
    ("value", True, "non_numeric_value"),
    ("value", float("inf"), "non_numeric_value"),
    ("date_range", 25, "time_operand_needs_derivation"),
    ("record_time", 25, "time_operand_needs_derivation"),
    ("assertion_basis", 25, "context_only"),
])
def test_shape_check_never_converts_context_or_dates_to_scalar(attribute, value, shape):
    predicate = SimpleNamespace(comparator=SimpleNamespace(value="gte"), value=2,
                                unit="年", requires_professional_judgment=True)
    fact = SimpleNamespace(value=value, unit="年",
                           source_strength=SimpleNamespace(value="unverifiable_source"))
    result = candidate_value_shape(predicate, fact, attribute)
    assert result["operand_shape"] == shape
    assert result["accepted"] is False
    assert "source_unverifiable" in result["pending_checks"]
    assert "semantic_correspondence_unverified" in result["pending_checks"]
    assert "professional_judgment_applicability_unverified" in result["pending_checks"]
    assert "truth" not in result


def test_numeric_shape_is_not_semantic_or_unit_acceptance():
    predicate = SimpleNamespace(comparator=SimpleNamespace(value="lte"), value=75,
                                unit="周岁", requires_professional_judgment=False)
    fact = SimpleNamespace(value=51, unit="岁",
                           source_strength=SimpleNamespace(value="contemporaneous_objective_result"))
    result = candidate_value_shape(predicate, fact, "value")
    assert result["operand_shape"] == "numeric_value"
    assert "unit_equivalence_unverified" in result["pending_checks"]
    assert result["accepted"] is False


@pytest.mark.parametrize("field,value", [
    ("fact_id", "other-fact"), ("locator_id", "other-page"),
    ("excerpt", "ALT 9"), ("excerpt", " "), ("fact_attribute", "date_range"),
    ("truth", True),
])
def test_invalid_references_and_conclusions_are_rejected(field, value):
    frozen, payload = _case()
    payload["results"][0]["candidates"][0][field] = value
    with pytest.raises(ValueError):
        validate_predicate_candidates(frozen, json.dumps(payload))


@pytest.mark.parametrize("mutation", ["omit", "duplicate", "unknown"])
def test_condition_coverage_must_be_exact(mutation):
    frozen, payload = _case()
    if mutation == "omit":
        payload["results"].pop()
    elif mutation == "duplicate":
        payload["results"].append(payload["results"][0])
    else:
        payload["results"][0]["predicate_identity_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="完整覆盖"):
        validate_predicate_candidates(frozen, json.dumps(payload))


def test_request_schema_enumerates_each_atomic_condition_without_merging():
    import jsonschema

    frozen, payload = _case()
    data = json.loads(build_predicate_binding_messages(frozen)[1]["content"][0]["text"])
    schema = data["output_schema"]
    expected = [p.predicate_identity_sha256 for c in frozen.components
                for p in (*c.trigger_predicates, *c.exception_predicates)]
    assert data["required_predicate_identities"] == expected
    assert schema["properties"]["results"]["minItems"] == len(expected)
    assert schema["properties"]["results"]["maxItems"] == len(expected)
    jsonschema.validate(payload, schema)
    omitted = {"results": payload["results"][:-1]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(omitted, schema)
    payload["results"][0]["predicate_identity_sha256"] = "0" * 64
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, schema)


def test_schema_count_does_not_replace_exact_identity_validation():
    import jsonschema

    frozen, payload = _case()
    data = json.loads(build_predicate_binding_messages(frozen)[1]["content"][0]["text"])
    payload["results"][1] = payload["results"][0].copy()
    jsonschema.validate(payload, data["output_schema"])
    with pytest.raises(ValueError, match="完整覆盖"):
        validate_predicate_candidates(frozen, json.dumps(payload))
    payload["results"] = [dict(predicate_identity_sha256=identity, status="unresolved",
                               candidates=[], uncertainty="本批尚未对应")
                          for identity in data["required_predicate_identities"]]
    assert all(item.status == "unresolved" for item in
               validate_predicate_candidates(frozen, json.dumps(payload)).results)


def test_exception_identity_is_required_separately_and_adapter_preserves_constraints():
    from app.domain.contracts.predicate_binding import (
        FrozenPredicateIdentity, FrozenRuleComponent, predicate_identity_sha256,
        predicate_component_identity_sha256,
    )
    from app.domain.expression import AtomicExpression

    frozen, _ = _case()
    component = frozen.components[0]
    original = component.trigger_predicates[1]
    fields = {key: getattr(original, key) for key in FrozenPredicateIdentity.model_fields
              if key != "predicate_identity_sha256"}
    fields["role"] = "exception"
    fields["predicate_id"] = "exception-condition"
    fields["predicate"] = original.predicate.model_copy(update={"predicate_id": fields["predicate_id"]})
    identity_fields = {key: value for key, value in fields.items()
                       if key not in {"predicate_id", "source_status"}}
    exception = FrozenPredicateIdentity(**fields,
        predicate_identity_sha256=predicate_identity_sha256(**identity_fields))
    component_fields = {key: getattr(component, key) for key in FrozenRuleComponent.model_fields
                        if key != "component_identity_sha256"}
    component_fields.update(exception_predicates=[exception],
                            exception_expression=AtomicExpression(predicate=exception.predicate))
    component = FrozenRuleComponent(**component_fields,
        component_identity_sha256=predicate_component_identity_sha256(**component_fields))
    frozen = _frozen_input([component], frozen.facts, frozen.locators)
    messages = build_predicate_binding_messages(frozen)
    data = json.loads(messages[1]["content"][0]["text"])
    assert len(data["required_predicate_identities"]) == 3
    assert exception.predicate_identity_sha256 in data["required_predicate_identities"]
    assert exception.predicate_identity_sha256 != component.trigger_predicates[1].predicate_identity_sha256
    schema = page_completion_options("mtplx", messages, 65536)["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["results"]["minItems"] == 3
    assert schema["properties"]["results"]["maxItems"] == 3
    assert schema["$defs"]["PredicateCandidateResult"]["properties"]["predicate_identity_sha256"]["enum"] == data["required_predicate_identities"]


def test_unverified_source_requires_unresolved_not_silent_acceptance():
    frozen, payload = _case(source=None)
    with pytest.raises(ValueError, match="原文未核实"):
        validate_predicate_candidates(frozen, json.dumps(payload))
    for item in payload["results"]:
        item.update(status="unresolved", candidates=[], uncertainty="条件原文尚未核实")
    assert all(item.status == "unresolved" for item in validate_predicate_candidates(frozen, json.dumps(payload)).results)


def test_prompt_uses_frozen_input_without_a_model_specific_branch():
    frozen, _ = _case()
    messages = build_predicate_binding_messages(frozen)
    data = json.loads(messages[1]["content"][0]["text"])
    assert data["frozen_input"] == predicate_binding_prompt_input(frozen)
    assert "glm" not in messages[0]["content"].lower()
    assert "qwen" not in messages[0]["content"].lower()


def test_duplicate_json_fields_are_rejected():
    frozen, _ = _case()
    with pytest.raises(ValueError, match="重复JSON"):
        validate_predicate_candidates(frozen, '{"results":[],"results":[]}')


def _route(**overrides):
    return PageReaderRoute(**{
        "lane": PageReviewLane.MAIN_A, "provider": "fixture-provider",
        "base_url": "http://unused.invalid", "api_key": "not-sent",
        "model": "fixture-model", "reasoning_effort": "high",
        "max_tokens": 65536, "max_concurrency": 1, **overrides,
    })


def test_text_request_uses_existing_local_schema_adapter():
    frozen, _ = _case()
    options = page_completion_options("mtplx", build_predicate_binding_messages(frozen), 65536)
    assert options["extra_body"]["generation_mode"] == "ar"
    assert options["response_format"]


def test_length_retries_once_with_larger_budget_and_preserves_responses():
    frozen, payload = _case()
    calls = []
    async def complete(route, messages, budget):
        calls.append((messages, budget))
        return PageCompletion("truncated" if len(calls) == 1 else json.dumps(payload),
                              "length" if len(calls) == 1 else "stop", {})
    result = asyncio.run(read_predicate_candidates(frozen, _route(), completion=complete))
    assert result.budgets == (65536, 131072)
    assert len(result.completions) == 2
    assert result.completions[0].text == "truncated"
    assert result.completions[-1].response_model is None
    assert calls[0][0] == calls[1][0]
    assert result.requested_provider == "fixture-provider"
    assert result.source_excerpts == {"loc-a": frozen.locators[0].excerpt}


def test_second_truncation_is_not_an_unresolved_success():
    frozen, _ = _case()
    async def complete(*args):
        return PageCompletion("partial", "length", {})
    with pytest.raises(PredicateCandidateReadError) as error:
        asyncio.run(read_predicate_candidates(frozen, _route(), completion=complete))
    assert error.value.budgets == (65536, 131072)
    assert len(error.value.completions) == 2


def test_invalid_output_retains_original_response_without_format_reread():
    frozen, _ = _case()
    async def complete(*args):
        return PageCompletion('{"truth":true}', "stop", {})
    with pytest.raises(PredicateCandidateReadError) as error:
        asyncio.run(read_predicate_candidates(frozen, _route(), completion=complete))
    assert len(error.value.completions) == 1
    assert error.value.completions[0].text == '{"truth":true}'


def test_small_budget_is_rejected_before_request():
    frozen, _ = _case()
    async def complete(*args):
        pytest.fail("must reject before sending")
    with pytest.raises(PredicateCandidateReadError, match="输出额度"):
        asyncio.run(read_predicate_candidates(frozen, _route(max_tokens=8192), completion=complete))


def test_rate_limit_wait_does_not_consume_output_retry(monkeypatch):
    frozen, payload = _case()
    waits, calls = [], []
    class RateLimited(Exception):
        status_code = 429
    async def sleep(seconds):
        waits.append(seconds)
    async def complete(route, messages, budget):
        calls.append(budget)
        if len(calls) == 1:
            raise RateLimited()
        return PageCompletion("partial" if len(calls) == 2 else json.dumps(payload),
                              "length" if len(calls) == 2 else "stop", {})
    monkeypatch.setattr("app.llm.predicate_binding_candidates.asyncio.sleep", sleep)
    result = asyncio.run(read_predicate_candidates(frozen, _route(), completion=complete))
    assert calls == [65536, 65536, 131072]
    assert waits == [60]
    assert result.budgets == (65536, 131072)


def test_rate_limit_wait_is_bounded_and_never_becomes_empty_success(monkeypatch):
    frozen, _ = _case()
    waits = []
    class RateLimited(Exception):
        status_code = 429
    async def sleep(seconds):
        waits.append(seconds)
    async def complete(*args):
        raise RateLimited()
    monkeypatch.setattr("app.llm.predicate_binding_candidates.asyncio.sleep", sleep)
    with pytest.raises(PredicateCandidateReadError) as error:
        asyncio.run(read_predicate_candidates(frozen, _route(), completion=complete))
    assert len(waits) == 12
    assert error.value.completions == ()


def test_compact_prompt_preserves_clinical_values_and_exact_excerpts():
    frozen, _ = _case()
    compact = predicate_binding_prompt_input(frozen)
    facts = {row["fact_id"]: row for row in (dict(zip(compact["facts"]["columns"], values)) for values in compact["facts"]["rows"])}
    sources = {row["locator_id"]: row for row in (dict(zip(compact["sources"]["columns"], values)) for values in compact["sources"]["rows"])}
    for fact in frozen.facts:
        item = facts[fact.fact_id]
        for field in ("asserted_object", "value", "unit", "polarity", "source_strength", "locator_ids"):
            assert item[field] == fact.model_dump(mode="json")[field]
    for locator in frozen.locators:
        assert sources[locator.locator_id]["excerpt"] == locator.excerpt
    assert compact["frozen_input_sha256"] == frozen.frozen_input_sha256
