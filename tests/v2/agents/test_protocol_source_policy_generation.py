"""New generations must not rely on historical source-policy defaults."""

import json

import jsonschema
import pytest
from pydantic import ValidationError

from app.agents.protocol_deconstructor import (
    _batch_schema_repair_prompt,
    _batch_source_span_ids,
    _compact_repair_schema,
    _compact_schema,
    _repair_prompt,
    _wire_evidence_requirement_schema,
    protocol_output_response_format,
)
from app.domain.contracts.agent_io import SemanticEvidenceRequirement


@pytest.mark.parametrize("kind", ["semantic_candidate", "semantic_rule_repair"])
def test_generation_source_identifiers_are_scoped_without_changing_read_schema(kind):
    allowed = ["snapshot-a::paragraph-7", "snapshot-a::paragraph-8"]
    builder = _compact_schema if kind == "semantic_candidate" else _compact_repair_schema
    schemas = (
        json.loads(builder(allowed)),
        protocol_output_response_format(kind, allowed_source_span_ids=allowed)["json_schema"]["schema"],
    )
    for schema in schemas:
        field = schema["$defs"]["SemanticRuleComponent"]["properties"]["source_span_ids"]
        jsonschema.validate([allowed[0]], field)
        for invalid in (["paragraph-7"], ["snapshot-b::paragraph-7"]):
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate(invalid, field)
    unscoped = json.loads(builder())
    assert "enum" not in unscoped["$defs"]["SemanticRuleComponent"]["properties"]["source_span_ids"]["items"]


def test_structure_and_semantic_repairs_preserve_selected_source_scope():
    from tests.v2.protocols.test_deconstruction_gate_slice3 import _fixture

    source, _, _ = _fixture()
    code = source.parent_rule_catalog.items[0].official_code
    allowed = _batch_source_span_ids(source, [code])
    assert allowed
    assert set(allowed) < set(source.allowed_source_span_ids)
    structure = _batch_schema_repair_prompt(
        [code], candidate_id="candidate", agent_call_id="call", batch_id="batch",
        problem="Invalid source identity", allowed_source_span_ids=allowed,
    )
    semantic = _repair_prompt(
        [], attempt=1, parsed_draft_available=True,
        replacement_rule_codes=[code], source_input=source,
    )
    for prompt in (structure, semantic):
        schema = json.loads(prompt.split("输出结构：", 1)[1])
        actual = schema["$defs"]["SemanticRuleComponent"]["properties"]["source_span_ids"]["items"]["enum"]
        assert actual == list(allowed)


@pytest.mark.parametrize("kind", ["semantic_candidate", "semantic_rule_repair"])
def test_prompt_and_provider_require_explicit_source_policy(kind):
    prompt_schema = json.loads(
        _compact_schema() if kind == "semantic_candidate" else _compact_repair_schema()
    )
    provider_schema = protocol_output_response_format(kind)["json_schema"]["schema"]
    for schema in (prompt_schema, provider_schema):
        requirement = schema["$defs"]["SemanticEvidenceRequirement"]
        isolated = {**requirement, "$defs": schema["$defs"]}
        payload = {
            "fact_type": "clinical_observation",
            "due_stage": "screening",
            "description": "Review source evidence",
            "predicate_ids": ["condition-a"],
            "allows_screening_record_transcription": False,
            "requires_contemporaneous_objective_source": True,
        }
        jsonschema.validate(payload, isolated)
        SemanticEvidenceRequirement.model_validate(payload)
        for field in (
            "allows_screening_record_transcription",
            "requires_contemporaneous_objective_source",
        ):
            incomplete = {k: v for k, v in payload.items() if k != field}
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate(incomplete, isolated)
            assert "default" not in requirement["properties"][field]


def test_unlinked_historical_requirements_remain_readable():
    requirement = SemanticEvidenceRequirement.model_validate({
        "fact_type": "clinical_observation",
        "due_stage": "screening",
        "description": "Historical record",
    })
    assert requirement.predicate_ids == []
    assert requirement.allows_screening_record_transcription is True
    assert requirement.requires_contemporaneous_objective_source is False


def test_compact_wire_also_requires_explicit_source_policy():
    schema = _wire_evidence_requirement_schema()
    payload = {
        "fact_type": "clinical_observation",
        "due_stage": "screening",
        "description": "Review source evidence",
        "allows_screening_record_transcription": False,
        "requires_contemporaneous_objective_source": True,
    }
    jsonschema.validate(payload, schema)
    for field in (
        "allows_screening_record_transcription",
        "requires_contemporaneous_objective_source",
    ):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({k: v for k, v in payload.items() if k != field}, schema)


def test_linked_missing_policy_stays_rejected_with_actionable_field_names():
    with pytest.raises(ValidationError) as error:
        SemanticEvidenceRequirement.model_validate({
            "fact_type": "clinical_observation",
            "due_stage": "screening",
            "description": "Source types are not source policy",
            "predicate_ids": ["condition-a"],
            "required_source_types": ["medical_record"],
        })
    for field in (
        "allows_screening_record_transcription",
        "requires_contemporaneous_objective_source",
    ):
        assert field in str(error.value)
