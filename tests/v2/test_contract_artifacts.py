from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from app.domain.contracts.review import FixtureV1
from app.domain.gates import validate_action_request
from app.domain.rollup import rollup_episode


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = ROOT / "contracts" / "v1"
SCHEMA_PATH = CONTRACT_ROOT / "schema" / "fixture-v1.schema.json"
OPENAPI_PATH = CONTRACT_ROOT / "schema" / "openapi-v1.draft.json"
FIXTURE_PATHS = sorted((CONTRACT_ROOT / "fixtures").glob("subject-*.json"))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def all_refs(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref":
                yield item
            else:
                yield from all_refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from all_refs(item)


def test_three_fixture_scenarios_validate_with_pydantic_and_json_schema() -> None:
    assert [path.stem for path in FIXTURE_PATHS] == [
        "subject-barrier",
        "subject-clear",
        "subject-gap_conflict",
    ]
    schema = load_json(SCHEMA_PATH)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for path in FIXTURE_PATHS:
        payload = load_json(path)
        validator.validate(payload)
        FixtureV1.model_validate(payload)


def test_fixture_references_are_internally_consistent() -> None:
    for path in FIXTURE_PATHS:
        fixture = FixtureV1.model_validate(load_json(path))
        span_ids = {item.evidence_span_id for item in fixture.evidence_spans}
        fact_ids = {item.fact_id for item in fixture.facts}
        component_ids = {
            component.rule_component_id
            for rule in fixture.rule_set.rules
            for component in rule.components
        }
        action_ids = {item.action_id for item in fixture.actions}
        gate_ids = {item.gate_result_id for item in fixture.gate_results}
        call_ids = {item.agent_call_id for item in fixture.agent_calls}
        prompt_by_id = {item.prompt_version_id: item for item in fixture.prompt_versions}
        model_ids = {item.model_config_id for item in fixture.model_configs}
        requirement_ids = {
            requirement.requirement_id
            for rule in fixture.rule_set.rules
            for component in rule.components
            for requirement in component.evidence_requirements
        }

        assert fixture.project.rule_set_id == fixture.rule_set.rule_set_id
        assert fixture.project.protocol_version.protocol_version_id == fixture.rule_set.protocol_version_id
        assert fixture.project.study_phase == fixture.rule_set.study_phase
        assert fixture.subject.project_id == fixture.project.project_id
        assert fixture.review_episode.subject_id == fixture.subject.subject_id
        assert fixture.review_episode.protocol_version_id == fixture.project.protocol_version.protocol_version_id
        assert fixture.review_episode.rule_set_revision == fixture.rule_set.revision
        assert fixture.review_episode.evidence_snapshot_id == fixture.evidence_snapshot.evidence_snapshot_id
        assert fixture.evidence_snapshot.subject_id == fixture.subject.subject_id
        assert fixture.evidence_snapshot.review_episode_id == fixture.review_episode.review_episode_id
        assert set(fixture.evidence_snapshot.source_document_version_ids) == {
            item.source_document_version_id for item in fixture.source_documents
        }
        assert fixture.review_episode.stage in {item.stage for item in fixture.workflow_stages}
        assert fixture.patient_profile.subject_id == fixture.subject.subject_id
        assert fixture.patient_profile.review_episode_id == fixture.review_episode.review_episode_id

        for fact in fixture.facts:
            assert set(fact.evidence_span_ids) <= span_ids
        for expectation in fixture.evidence_expectations:
            assert expectation.review_episode_id == fixture.review_episode.review_episode_id
            assert expectation.requirement_id in requirement_ids
            assert set(expectation.evidence_span_ids) <= span_ids
        for candidate in fixture.assessment_candidates:
            assert candidate.agent_call_id in call_ids
            assert candidate.rule_component_id in component_ids
            assert set(candidate.used_fact_ids) <= fact_ids
            assert set(candidate.evidence_span_ids) <= span_ids
        for assessment in fixture.final_assessments:
            assert assessment.rule_component_id in component_ids
            assert assessment.gate_result_id in gate_ids
            assert set(assessment.action_ids) <= action_ids
        for call in fixture.agent_calls:
            assert call.gate_result_id in gate_ids
            assert call.prompt_version_id in prompt_by_id
            assert prompt_by_id[call.prompt_version_id].node == call.node
            assert call.model_config_id in model_ids
        for action in fixture.actions:
            validate_action_request(action)
        for run in fixture.review_runs:
            assert run.review_episode_id == fixture.review_episode.review_episode_id
            assert run.protocol_version_id == fixture.review_episode.protocol_version_id
            assert run.rule_set_revision == fixture.review_episode.rule_set_revision
            assert run.evidence_snapshot_id == fixture.evidence_snapshot.evidence_snapshot_id


def test_fixture_rollups_match_scenario_semantics() -> None:
    expected = {
        "barrier": "clear_barrier",
        "clear": "no_clear_barrier",
        "gap_conflict": "current_gap",
    }
    for path in FIXTURE_PATHS:
        fixture = FixtureV1.model_validate(load_json(path))
        rollup = rollup_episode(
            fixture.final_assessments,
            fixture.evidence_expectations,
            fixture.actions,
        )
        assert rollup.main_status.value == expected[fixture.scenario]


def test_openapi_refs_target_existing_components() -> None:
    openapi = load_json(OPENAPI_PATH)
    assert openapi["openapi"] == "3.1.0"
    components = openapi["components"]["schemas"]
    for reference in all_refs(openapi):
        if reference.startswith("#/components/schemas/"):
            assert reference.rsplit("/", 1)[-1] in components


def test_openapi_non_success_responses_use_versioned_error_envelope() -> None:
    openapi = load_json(OPENAPI_PATH)
    error_schema = openapi["components"]["schemas"]["ErrorEnvelope"]
    assert "schema_version" in error_schema["properties"]
    for path_item in openapi["paths"].values():
        for operation in path_item.values():
            for status, response in operation["responses"].items():
                if not status.startswith("2"):
                    schema = response["content"]["application/json"]["schema"]
                    assert schema == {"$ref": "#/components/schemas/ErrorEnvelope"}


def test_generated_schema_matches_current_contract_model() -> None:
    expected = FixtureV1.model_json_schema(ref_template="#/$defs/{model}")
    actual = load_json(SCHEMA_PATH)
    actual.pop("$id")
    actual.pop("$schema")
    assert actual == expected
