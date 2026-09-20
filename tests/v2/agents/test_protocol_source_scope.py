import json

import pytest

from app.agents.protocol_deconstructor import (
    DNF_WIRE_VERSION,
    _parse_semantic_candidate,
    _validate_semantic_batch,
    _batch_prompt_payload,
    _semantic_batch_cache_key,
    ProtocolAgentCallError,
    ProtocolAgentResponse,
    revise_protocol_draft_from_feedback,
    semantic_candidate_from_draft,
    protocol_output_response_format,
)
from app.agents.protocol_source_scope import source_references
from app.domain.contracts.observation_selection import ObservationPolicy
from app.domain.contracts.agent_io import ProtocolSemanticRuleRepair
from app.domain.contracts.rules import iter_atomic_predicates
from tests.v2.protocols.test_deconstruction_gate_slice3 import _fixture
from tests.v2.protocols.test_protocol_deconstructor_adapter_slice3 import (
    _semantic_candidate,
    _wire_candidate,
    FakeTransport,
)


@pytest.mark.parametrize("compact", [False, True])
@pytest.mark.parametrize("kind", ["semantic_candidate", "semantic_rule_repair"])
def test_nested_source_fields_are_scoped_for_each_output_contract(compact, kind):
    allowed = ["snapshot-a::paragraph-8", "snapshot-a::paragraph-3"]
    schema = protocol_output_response_format(
        kind, compact=compact, allowed_source_span_ids=allowed
    )["json_schema"]["schema"]
    seen = set()

    def check(value, path=()):
        if isinstance(value, dict):
            for name, field in value.get("properties", {}).items():
                if name in {"source_span_ids", "source_refs"}:
                    assert field["items"]["enum"] == allowed
                    seen.add(name)
                elif name == "source_span_id":
                    assert field["enum"] == allowed
                    seen.add(name)
            for name, child in value.items():
                check(child, (*path, name))
        elif isinstance(value, list):
            for child in value:
                check(child, path)

    check(schema)
    assert seen == {"source_span_ids", "source_span_id", "source_refs"}


def test_location_labels_and_excerpts_are_not_interpreted_as_identifiers():
    assert list(source_references({
        "source_ref": "paragraph-8",
        "source_excerpts": ["snapshot-b::paragraph-8"],
        "expression": [{"source_span_id": "snapshot-a::paragraph-8"}],
    })) == ["snapshot-a::paragraph-8"]


def test_frozen_workflow_context_does_not_expand_rule_source_scope():
    source, _, _ = _fixture()
    rule = source.parent_rule_catalog.items[0]
    payload = _batch_prompt_payload(
        source, [rule.official_code], batch_number=1, batch_total=1,
        candidate_id="candidate",
    )
    expected = [item.model_dump(mode="json") for item in sorted(
        source.required_procedure_catalog.items, key=lambda item: item.position
    )]
    assert payload["required_procedure_catalog"] == expected
    assert payload["allowed_source_span_ids"] == list(rule.source_span_ids)
    assert {item["source_span_id"] for item in payload["source_materials"]} == set(rule.source_span_ids)


def test_cache_identity_binds_frozen_input_even_for_identical_prompt():
    class Transport:
        def semantic_cache_identity(self, **kwargs):
            return "same-transport"

    source, _, _ = _fixture()
    def key(value):
        return _semantic_batch_cache_key(
            Transport(), prompt="same prompt", batch_id="1/1", rule_codes=["IN-01"],
            source_input=value, prompt_template="template",
        )
    original = key(source)
    assert original != key(source.model_copy(update={"protocol_file_sha256": "f" * 64}))
    assert original != key(source.model_copy(update={"extraction_snapshot_id": "another"}))


def test_feedback_configures_scope_and_rejects_foreign_component_source():
    source, draft, _ = _fixture()
    candidate = semantic_candidate_from_draft(draft)
    replacement = candidate.proposed_rules[0].model_copy(deep=True)
    replacement.components[0].source_span_ids = ["foreign-source"]
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id, replacement_rules=[replacement]
    )

    class ScopedTransport(FakeTransport):
        def configure_output_scope(self, **scope):
            self.scope = scope

    response = ProtocolAgentResponse(session_id="same-session", text=repair.model_dump_json())
    transport = ScopedTransport([response, response])
    with pytest.raises(ProtocolAgentCallError, match="来源闭包"):
        revise_protocol_draft_from_feedback(
            source, draft, target_rule_code=replacement.official_code,
            feedback_note="Recheck against the unchanged source", transport=transport,
        )
    assert transport.scope["official_codes"] == (replacement.official_code,)
    assert "foreign-source" not in transport.scope["allowed_source_span_ids"]


@pytest.mark.parametrize("foreign", [False, True])
def test_nested_source_must_belong_to_its_component(foreign):
    source, draft, _ = _fixture()
    candidate = _semantic_candidate(source, draft)
    component = candidate.proposed_rules[0].components[0]
    span = (candidate.proposed_rules[1].components[0].source_span_ids[0]
            if foreign else component.source_span_ids[0])
    predicate = next(iter_atomic_predicates(component.expression))
    predicate.observation_policy = ObservationPolicy(
        mode="single", scope="Original observation", source_span_ids=[span],
        source_excerpts=[component.source_excerpts[0]],
    )
    kwargs = dict(
        expected_codes=[rule.official_code for rule in candidate.proposed_rules],
        expected_candidate_id=candidate.candidate_id,
        expected_agent_call_id=candidate.created_by_agent_call_id,
        source_input=source,
    )
    if foreign:
        with pytest.raises(ValueError, match="嵌套来源"):
            _validate_semantic_batch(candidate, **kwargs)
    else:
        _validate_semantic_batch(candidate, **kwargs)


@pytest.mark.parametrize("missing", [None, "allows_screening_record_transcription",
                                    "requires_contemporaneous_objective_source"])
def test_current_wire_never_fills_missing_source_policy(missing):
    source, draft, _ = _fixture()
    candidate = _semantic_candidate(source, draft)
    candidate.proposed_rules = candidate.proposed_rules[:1]
    component = candidate.proposed_rules[0].components[0]
    for predicate in iter_atomic_predicates(component.expression):
        predicate.observation_policy = ObservationPolicy(
            mode="single", scope="Original observation",
            source_span_ids=component.source_span_ids,
            source_excerpts=component.source_excerpts,
        )
    payload = _wire_candidate(candidate)
    payload["wire_version"] = DNF_WIRE_VERSION
    wire_component = payload["proposed_rules"][0]["components"][0]
    wire_component["repeat_trigger_conditions"] = []
    for group in wire_component["expression"]:
        for atoms in group.values():
            for atom in atoms:
                atom["semantic_proposition"] = None
                atom["repeat_scheme"] = None
    requirement = wire_component["evidence_requirements"][0]
    requirement.pop("predicate_ids", None)
    requirement.pop("predicate_refs", None)
    if missing is not None:
        del requirement[missing]
        with pytest.raises(ValueError, match="来源政策"):
            _parse_semantic_candidate(json.dumps(payload), compact=True)
    else:
        _parse_semantic_candidate(json.dumps(payload), compact=True)
