from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from app.domain.contracts.review import FixtureV1
from app.domain.contracts.agent_io import AgentContractsV1
from app.domain.contracts.uat import UatWorkspaceFixture
from app.domain.contracts.enums import (
    GateOutcome,
    ReviewStage,
    RuntimeErrorCode,
    UploadMode,
)
from app.domain.gates import (
    assessment_publication_from_fixture,
    assert_protocol_integrity,
    build_protocol_authority_confirmation,
    build_protocol_integrity_manifest,
    build_protocol_source_record,
    build_service_command_event,
    require_protocol_integrity_acceptance,
    validate_action_publication,
    validate_fixture_scope,
)
from app.domain.gates.actions import ActionPublication
from app.domain.gates.integrity import _trusted_registry_from_fixture
from app.domain.registry import _issue_trusted_registry
from app.domain.rollup import publish_episode_rollup


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = ROOT / "contracts" / "v1"
SCHEMA_PATH = CONTRACT_ROOT / "schema" / "fixture-v1.schema.json"
OPENAPI_PATH = CONTRACT_ROOT / "schema" / "openapi-v1.draft.json"
AGENT_SCHEMA_PATH = CONTRACT_ROOT / "schema" / "agent-contracts-v1.schema.json"
FIXTURE_PATHS = sorted((CONTRACT_ROOT / "fixtures").glob("subject-*.json"))
UAT_SCHEMA_PATH = CONTRACT_ROOT / "schema" / "uat-phase1-workspace.schema.json"
UAT_FIXTURE_PATH = CONTRACT_ROOT / "fixtures" / "uat-phase1-workspace.json"


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
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for path in FIXTURE_PATHS:
        payload = load_json(path)
        validator.validate(payload)
        FixtureV1.model_validate(payload)


def test_fixture_references_are_internally_consistent() -> None:
    for path in FIXTURE_PATHS:
        fixture = FixtureV1.model_validate(load_json(path))
        gate_by_id = {item.gate_result_id: item for item in fixture.gate_results}
        assert_protocol_integrity(
            fixture.rule_set,
            workflow_stages=fixture.workflow_stages,
            protocol_version=fixture.project.protocol_version,
            manifest=fixture.protocol_integrity_manifest,
            authority_record=fixture.protocol_authority_record,
            authority_confirmation=fixture.protocol_authority_confirmation,
            authority_gate_result=gate_by_id[
                fixture.project.protocol_version.authority_gate_result_id
            ],
            registry=_trusted_registry_from_fixture(fixture),
        )
        validate_fixture_scope(fixture, _trusted_registry_from_fixture(fixture))
        span_ids = {item.evidence_span_id for item in fixture.evidence_spans}
        fact_ids = {item.fact_id for item in fixture.facts}
        component_ids = {
            component.rule_component_id
            for rule in fixture.rule_set.rules
            for component in rule.components
        }
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
        assert {
            item.fact_id
            for candidate in fixture.evidence_normalization_candidates
            for item in candidate.clinical_fact_candidates
        } == fact_ids
        assert {
            item.evidence_span_id
            for candidate in fixture.evidence_normalization_candidates
            for item in candidate.evidence_span_candidates
        } == span_ids
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
        for call in fixture.agent_calls:
            assert set(call.gate_result_ids) <= gate_ids
            assert call.prompt_version_id in prompt_by_id
            assert prompt_by_id[call.prompt_version_id].node == call.node
            assert call.model_config_id in model_ids
        for action in fixture.actions:
                validate_action_publication(
                ActionPublication(
                    action=action,
                    gate_result=gate_by_id[action.gate_result_id],
                    assessment_publication=assessment_publication_from_fixture(
                        fixture, action.assessment_id
                    ),
                    ),
                    _trusted_registry_from_fixture(fixture),
                )
        for run in fixture.review_runs:
            assert run.review_episode_id == fixture.review_episode.review_episode_id
            assert run.protocol_version_id == fixture.review_episode.protocol_version_id
            assert run.rule_set_revision == fixture.review_episode.rule_set_revision
            assert run.evidence_snapshot_id == fixture.evidence_snapshot.evidence_snapshot_id


def test_fixture_rollups_match_scenario_semantics() -> None:
    expected = {
        "barrier": "clear_barrier",
        "clear": "future_attention",
        "gap_conflict": "current_gap",
    }
    for path in FIXTURE_PATHS:
        fixture = FixtureV1.model_validate(load_json(path))
        publication = publish_episode_rollup(
            review_episode_id=fixture.review_episode.review_episode_id,
            assessment_publications=[
                assessment_publication_from_fixture(
                    fixture, item.assessment_id
                )
                for item in fixture.final_assessments
            ],
            expectations=fixture.evidence_expectations,
            action_publications=[
                    ActionPublication(
                        action=item,
                        gate_result=next(
                        gate
                        for gate in fixture.gate_results
                            if gate.gate_result_id == item.gate_result_id
                        ),
                        assessment_publication=assessment_publication_from_fixture(
                            fixture, item.assessment_id
                        ),
                    )
                for item in fixture.actions
            ],
            gate_result_id=fixture.episode_rollup.gate_result_id,
            input_revision_map={
                fixture.review_episode.review_episode_id: fixture.review_episode.revision
            },
            created_at=fixture.review_runs[0].started_at,
            registry=_trusted_registry_from_fixture(fixture),
        )
        assert publication.rollup.main_status.value == expected[fixture.scenario]
        assert publication.rollup.model_dump(mode="json") == fixture.episode_rollup.model_dump(mode="json")


def test_rollup_publication_rejects_incomplete_or_duplicate_inputs() -> None:
    fixture = FixtureV1.model_validate(
        load_json(next(path for path in FIXTURE_PATHS if "gap_conflict" in path.name))
    )
    assessment_publications = [
        assessment_publication_from_fixture(fixture, item.assessment_id)
        for item in fixture.final_assessments
    ]
    gate_by_id = {item.gate_result_id: item for item in fixture.gate_results}
    action_publications = [
        ActionPublication(
            action=item,
            gate_result=gate_by_id[item.gate_result_id],
            assessment_publication=assessment_publication_from_fixture(
                fixture, item.assessment_id
            ),
        )
        for item in fixture.actions
    ]
    common = {
        "review_episode_id": fixture.review_episode.review_episode_id,
        "gate_result_id": "gate-rollup-adversarial",
        "input_revision_map": {
            fixture.review_episode.review_episode_id: fixture.review_episode.revision
        },
        "created_at": fixture.review_runs[0].started_at,
        "registry": _trusted_registry_from_fixture(fixture),
    }
    invalid_inputs = [
        {
            "assessment_publications": [],
            "expectations": fixture.evidence_expectations,
            "action_publications": action_publications,
        },
        {
            "assessment_publications": [
                *assessment_publications,
                assessment_publications[0],
            ],
            "expectations": fixture.evidence_expectations,
            "action_publications": action_publications,
        },
        {
            "assessment_publications": assessment_publications,
            "expectations": fixture.evidence_expectations[:-1],
            "action_publications": action_publications,
        },
        {
            "assessment_publications": assessment_publications,
            "expectations": [
                *fixture.evidence_expectations,
                fixture.evidence_expectations[0],
            ],
            "action_publications": action_publications,
        },
        {
            "assessment_publications": assessment_publications,
            "expectations": fixture.evidence_expectations,
            "action_publications": action_publications[:-1],
        },
        {
            "assessment_publications": assessment_publications,
            "expectations": fixture.evidence_expectations,
            "action_publications": [*action_publications, action_publications[0]],
        },
    ]
    for invalid in invalid_inputs:
        with pytest.raises(ValueError):
            publish_episode_rollup(**common, **invalid)


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


def test_openapi_paths_declare_parameters_requests_and_success_schemas() -> None:
    openapi = load_json(OPENAPI_PATH)
    for path, path_item in openapi["paths"].items():
        parameter_names = {
            item[1:-1]
            for item in path.split("/")
            if item.startswith("{") and item.endswith("}")
        }
        for operation in path_item.values():
            declared = {
                parameter["name"]
                for parameter in operation.get("parameters", [])
                if parameter["in"] == "path" and parameter["required"] is True
            }
            assert declared == parameter_names
            success = operation["responses"]["200"]
            assert success["content"]["application/json"]["schema"]["$ref"].startswith(
                "#/components/schemas/"
            )
    override = openapi["paths"]["/api/v2/actions/{action_id}/override"]["post"]
    assert override["requestBody"]["required"] is True
    assert override["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ActionOverrideCommand"
    }


def test_generated_schema_matches_current_contract_model() -> None:
    expected = FixtureV1.model_json_schema(ref_template="#/$defs/{model}")
    actual = load_json(SCHEMA_PATH)
    actual.pop("$id")
    actual.pop("$schema")
    assert actual == expected

    expected_agent = AgentContractsV1.model_json_schema(ref_template="#/$defs/{model}")
    actual_agent = load_json(AGENT_SCHEMA_PATH)
    Draft202012Validator.check_schema(actual_agent)
    actual_agent.pop("$id")
    actual_agent.pop("$schema")
    assert actual_agent == expected_agent

    expected_uat = UatWorkspaceFixture.model_json_schema(ref_template="#/$defs/{model}")
    actual_uat = load_json(UAT_SCHEMA_PATH)
    Draft202012Validator.check_schema(actual_uat)
    actual_uat.pop("$id")
    actual_uat.pop("$schema")
    assert actual_uat == expected_uat


def test_uat_workspace_has_executable_multistage_coverage() -> None:
    payload = load_json(UAT_FIXTURE_PATH)
    schema = load_json(UAT_SCHEMA_PATH)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
    workspace = UatWorkspaceFixture.model_validate(payload)
    assert len(workspace.episodes) == 14
    assert len(workspace.primary_subject_ids) == 6
    assert {item.review_episode.stage for item in workspace.episodes} == set(ReviewStage)
    for fixture in workspace.episodes:
        validate_fixture_scope(fixture, _trusted_registry_from_fixture(fixture))
        gate_by_id = {item.gate_result_id: item for item in fixture.gate_results}
        assert_protocol_integrity(
            fixture.rule_set,
            workflow_stages=fixture.workflow_stages,
            protocol_version=fixture.project.protocol_version,
            manifest=fixture.protocol_integrity_manifest,
            authority_record=fixture.protocol_authority_record,
            authority_confirmation=fixture.protocol_authority_confirmation,
            authority_gate_result=gate_by_id[
                fixture.project.protocol_version.authority_gate_result_id
            ],
            registry=_trusted_registry_from_fixture(fixture),
        )


def test_protocol_diff_requires_rule_scoped_source_locations() -> None:
    payload = load_json(UAT_FIXTURE_PATH)
    refs = payload["protocol_diff"]["source_refs_by_rule_code"]
    assert refs["EX-05"] == ["protocol-v2-draft:p12"]
    assert refs["REQ-02"] == ["protocol-v1:p10"]
    assert refs["EX-01"] == ["protocol-v1:p10", "protocol-v2-draft:p12"]

    del payload["protocol_diff"]["source_refs_by_rule_code"]["EX-05"]
    with pytest.raises(ValueError, match="每条新增、删除或变更规则"):
        UatWorkspaceFixture.model_validate(payload)


def test_uat_workspace_rejects_semantic_operator_coverage_regression() -> None:
    payload = load_json(UAT_FIXTURE_PATH)

    def remove_not(expression: dict) -> dict:
        if expression.get("kind") != "logical":
            return expression
        children = [remove_not(item) for item in expression["children"]]
        if expression.get("operator") == "not":
            return children[0]
        return {**expression, "children": children}

    for fixture in payload["episodes"]:
        for rule in fixture["rule_set"]["rules"]:
            for component in rule["components"]:
                component["expression"] = remove_not(component["expression"])
                if component.get("exception_expression") is not None:
                    component["exception_expression"] = remove_not(
                        component["exception_expression"]
                    )

    with pytest.raises(ValueError, match="ALL[/、]ANY[/、]NOT"):
        UatWorkspaceFixture.model_validate(payload)


def test_uat_workspace_rejects_semantic_change_with_same_operator_counts() -> None:
    payload = load_json(UAT_FIXTURE_PATH)
    for fixture in payload["episodes"]:
        component = next(
            component
            for rule in fixture["rule_set"]["rules"]
            for component in rule["components"]
            if component["rule_component_id"] == "component-ex-01"
        )
        component["expression"]["operator"] = "any"
        component["expression"]["children"][1]["operator"] = "all"
    with pytest.raises(ValueError, match="语义漂移"):
        UatWorkspaceFixture.model_validate(payload)


def test_uat_workspace_rejects_time_window_semantic_drift() -> None:
    payload = load_json(UAT_FIXTURE_PATH)
    for fixture in payload["episodes"]:
        component = next(
            component
            for rule in fixture["rule_set"]["rules"]
            for component in rule["components"]
            if component["rule_component_id"] == "component-ex-01"
        )
        component["expression"]["children"][1]["children"][1][
            "time_constraint"
        ]["upper_bound_days"] = 29
    with pytest.raises(ValueError, match="28 天时间窗"):
        UatWorkspaceFixture.model_validate(payload)


def test_uat_contains_real_historical_source_unavailable_episode() -> None:
    workspace = UatWorkspaceFixture.model_validate(load_json(UAT_FIXTURE_PATH))
    matching = [
            fixture
            for fixture in workspace.episodes
            if any(
                item.gap_type is not None
                and item.gap_type.value == "historical_source_unavailable"
                for item in fixture.evidence_expectations
            )
    ]
    assert matching
    assert any(
        item.status.value == "observed_weak" and item.evidence_span_ids
        for fixture in matching
        for item in fixture.evidence_expectations
        if item.gap_type and item.gap_type.value == "historical_source_unavailable"
    )


def test_generated_json_schema_enforces_model_level_conditionals() -> None:
    schema = load_json(SCHEMA_PATH)
    openapi = load_json(OPENAPI_PATH)
    clinical_fact_schemas = [
        {"$defs": schema["$defs"], "$ref": "#/$defs/ClinicalFact"},
        {
            "components": openapi["components"],
            "$ref": "#/components/schemas/ClinicalFact",
        },
    ]
    invalid_fact = load_json(FIXTURE_PATHS[0])["facts"][0]
    invalid_fact.update({"polarity": "unknown", "value": True, "unit": None})
    for clinical_fact_schema in clinical_fact_schemas:
        with pytest.raises(JsonSchemaValidationError):
            Draft202012Validator(clinical_fact_schema).validate(invalid_fact)

    time_constraint_schemas = [
        {"$defs": schema["$defs"], "$ref": "#/$defs/TimeConstraint"},
        {
            "components": openapi["components"],
            "$ref": "#/components/schemas/TimeConstraint",
        },
    ]
    invalid_window = {
        "schema_version": "fixture/v1",
        "anchor_type": "baseline_date",
        "direction": "on",
        "lower_bound_days": 1,
        "upper_bound_days": None,
        "half_life_multiplier": None,
        "allow_partial_date": False,
    }
    for time_constraint_schema in time_constraint_schemas:
        with pytest.raises(JsonSchemaValidationError):
            Draft202012Validator(time_constraint_schema).validate(invalid_window)


def test_protocol_integrity_gate_rejects_tampered_stored_closure() -> None:
    fixture = FixtureV1.model_validate(load_json(FIXTURE_PATHS[0]))
    gate_by_id = {item.gate_result_id: item for item in fixture.gate_results}
    authority_gate = gate_by_id[
        fixture.project.protocol_version.authority_gate_result_id
    ]
    stored_gate = gate_by_id[
        fixture.project.protocol_version.integrity_gate_result_id
    ]
    tampered = stored_gate.model_copy(update={"output_hash": "f" * 64})
    with pytest.raises(ValueError, match="闭包无效"):
        require_protocol_integrity_acceptance(
            tampered,
            rule_set=fixture.rule_set,
            workflow_stages=fixture.workflow_stages,
            protocol_version=fixture.project.protocol_version,
            manifest=fixture.protocol_integrity_manifest,
            authority_record=fixture.protocol_authority_record,
            authority_confirmation=fixture.protocol_authority_confirmation,
            authority_gate_result=authority_gate,
            registry=_trusted_registry_from_fixture(fixture),
        )


def test_protocol_integrity_binds_full_authority_gate_payload() -> None:
    fixture = FixtureV1.model_validate(load_json(FIXTURE_PATHS[0]))
    gate_by_id = {item.gate_result_id: item for item in fixture.gate_results}
    authority_gate = gate_by_id[
        fixture.project.protocol_version.authority_gate_result_id
    ]
    changed_authority_gate = authority_gate.model_copy(
        update={"created_at": authority_gate.created_at + timedelta(seconds=1)}
    )
    changed_gates = [
        changed_authority_gate
        if item.gate_result_id == changed_authority_gate.gate_result_id
        else item
        for item in fixture.gate_results
    ]
    changed_fixture = fixture.model_copy(update={"gate_results": changed_gates})
    stored_integrity_gate = gate_by_id[
        fixture.project.protocol_version.integrity_gate_result_id
    ]
    with pytest.raises(ValueError, match="闭包无效"):
        require_protocol_integrity_acceptance(
            stored_integrity_gate,
            rule_set=fixture.rule_set,
            workflow_stages=fixture.workflow_stages,
            protocol_version=fixture.project.protocol_version,
            manifest=fixture.protocol_integrity_manifest,
            authority_record=fixture.protocol_authority_record,
            authority_confirmation=fixture.protocol_authority_confirmation,
            authority_gate_result=changed_authority_gate,
            registry=_trusted_registry_from_fixture(changed_fixture),
        )


def test_protocol_integrity_rejects_unregistered_protocol_or_manifest_payload() -> None:
    fixture = FixtureV1.model_validate(load_json(FIXTURE_PATHS[0]))
    registry = _trusted_registry_from_fixture(fixture)
    gate_by_id = {item.gate_result_id: item for item in fixture.gate_results}
    authority_gate = gate_by_id[
        fixture.project.protocol_version.authority_gate_result_id
    ]
    changed_protocol = fixture.project.protocol_version.model_copy(
        update={"official_version": "V9.9-caller"}
    )
    with pytest.raises(ValueError, match="protocol_document_version.*已登记版本"):
        assert_protocol_integrity(
            fixture.rule_set,
            workflow_stages=fixture.workflow_stages,
            protocol_version=changed_protocol,
            manifest=fixture.protocol_integrity_manifest,
            authority_record=fixture.protocol_authority_record,
            authority_confirmation=fixture.protocol_authority_confirmation,
            authority_gate_result=authority_gate,
            registry=registry,
        )

    new_manifest = build_protocol_integrity_manifest(
        manifest_id="manifest-caller-replacement",
        protocol_version_id=fixture.project.protocol_version.protocol_version_id,
        protocol_document_sha256=fixture.project.protocol_version.sha256,
        study_phase=fixture.project.study_phase,
        source_refs=fixture.protocol_integrity_manifest.source_refs,
        authority_record=fixture.protocol_authority_record,
        authority_confirmation=fixture.protocol_authority_confirmation,
        authority_gate_result=authority_gate,
        registry=registry,
    )
    with pytest.raises(ValueError, match="未找到服务端已登记.*manifest"):
        assert_protocol_integrity(
            fixture.rule_set,
            workflow_stages=fixture.workflow_stages,
            protocol_version=fixture.project.protocol_version,
            manifest=new_manifest,
            authority_record=fixture.protocol_authority_record,
            authority_confirmation=fixture.protocol_authority_confirmation,
            authority_gate_result=authority_gate,
            registry=registry,
        )


def test_fixture_scope_rejects_same_id_registered_entity_replacements() -> None:
    fixture = FixtureV1.model_validate(load_json(FIXTURE_PATHS[0]))
    registry = _trusted_registry_from_fixture(fixture)
    invalid_fixtures = [
        fixture.model_copy(
            update={
                "subject": fixture.subject.model_copy(
                    update={"subject_code": "被替换的受试者编号"}
                )
            }
        ),
        fixture.model_copy(
            update={
                "evidence_snapshot": fixture.evidence_snapshot.model_copy(
                    update={"upload_mode": UploadMode.INCREMENTAL}
                )
            }
        ),
        fixture.model_copy(
            update={
                "review_runs": [
                    fixture.review_runs[0].model_copy(
                        update={
                            "started_at": fixture.review_runs[0].started_at
                            + timedelta(seconds=1)
                        }
                    )
                ]
            }
        ),
        fixture.model_copy(
            update={
                "prompt_versions": [
                    fixture.prompt_versions[0].model_copy(
                        update={"template_sha256": "f" * 64}
                    ),
                    *fixture.prompt_versions[1:],
                ]
            }
        ),
        fixture.model_copy(
            update={
                "model_configs": [
                    fixture.model_configs[0].model_copy(
                        update={"model": "被替换的模型配置"}
                    ),
                    *fixture.model_configs[1:],
                ]
            }
        ),
        fixture.model_copy(
            update={
                "source_documents": [
                    fixture.source_documents[0].model_copy(
                        update={"sha256": "f" * 64}
                    )
                ]
            }
        ),
    ]
    for invalid_fixture in invalid_fixtures:
        with pytest.raises(ValueError, match="已登记版本不一致"):
            validate_fixture_scope(invalid_fixture, registry)


def test_fixture_scope_rejects_extra_unregistered_calls_and_gates() -> None:
    fixture = FixtureV1.model_validate(load_json(FIXTURE_PATHS[0]))
    registry = _trusted_registry_from_fixture(fixture)
    source_call = fixture.agent_calls[0]
    extra_call = source_call.model_copy(
        update={
            "agent_call_id": "call-extra-unregistered",
            "gate_result_ids": ["gate-extra-unregistered"],
        }
    )
    source_gate = fixture.gate_results[0]
    extra_gate = source_gate.model_copy(
        update={
            "gate_result_id": "gate-extra-unregistered",
            "input_entity_refs": ["call-extra-unregistered"],
            "accepted_entity_refs": ["call-extra-unregistered"],
        }
    )
    with pytest.raises(ValueError, match="未找到服务端已登记的 agent_call"):
        validate_fixture_scope(
            fixture.model_copy(
                update={"agent_calls": [*fixture.agent_calls, extra_call]}
            ),
            registry,
        )
    with pytest.raises(ValueError, match="未找到服务端已登记的 gate_result"):
        validate_fixture_scope(
            fixture.model_copy(
                update={"gate_results": [*fixture.gate_results, extra_gate]}
            ),
            registry,
        )


def test_fixture_scope_rejects_exact_duplicate_top_level_entities() -> None:
    fixture = FixtureV1.model_validate(load_json(FIXTURE_PATHS[0]))
    registry = _trusted_registry_from_fixture(fixture)
    duplicate_cases = [
        ("facts", fixture.facts, "ClinicalFact"),
        ("evidence_spans", fixture.evidence_spans, "EvidenceSpan"),
        ("agent_calls", fixture.agent_calls, "AgentCall"),
        (
            "source_documents",
            fixture.source_documents,
            "SourceDocumentVersion",
        ),
        ("prompt_versions", fixture.prompt_versions, "PromptVersion"),
        ("model_configs", fixture.model_configs, "ModelConfig"),
        ("review_runs", fixture.review_runs, "ReviewRun"),
        ("assessment_candidates", fixture.assessment_candidates, "AssessmentCandidate"),
        ("final_assessments", fixture.final_assessments, "FinalAssessment"),
        ("actions", fixture.actions, "ActionRequest"),
    ]
    for field_name, values, label in duplicate_cases:
        with pytest.raises(ValueError, match=f"{label} ID 必须唯一"):
            validate_fixture_scope(
                fixture.model_copy(
                    update={field_name: [*values, values[0]]}
                ),
                registry,
            )

    duplicate_profile = fixture.patient_profile.model_copy(
        update={
            "events": [
                *fixture.patient_profile.events,
                fixture.patient_profile.events[0],
            ]
        }
    )
    with pytest.raises(ValueError, match="PatientProfileEvent ID 必须唯一"):
        validate_fixture_scope(
            fixture.model_copy(update={"patient_profile": duplicate_profile}),
            registry,
        )


def test_fixture_scope_rejects_duplicate_snapshot_and_agent_gate_references() -> None:
    fixture = FixtureV1.model_validate(load_json(FIXTURE_PATHS[0]))
    duplicate_snapshot = fixture.evidence_snapshot.model_copy(
        update={
            "source_document_version_ids": [
                fixture.source_documents[0].source_document_version_id,
                fixture.source_documents[0].source_document_version_id,
            ]
        }
    )
    snapshot_fixture = fixture.model_copy(
        update={"evidence_snapshot": duplicate_snapshot}
    )
    with pytest.raises(ValueError, match="证据快照"):
        validate_fixture_scope(
            snapshot_fixture, _trusted_registry_from_fixture(snapshot_fixture)
        )

    original_call = fixture.agent_calls[0]
    duplicate_gate_call = original_call.model_copy(
        update={
            "gate_result_ids": [
                original_call.gate_result_ids[0],
                original_call.gate_result_ids[0],
            ]
        }
    )
    calls = [
        duplicate_gate_call if item.agent_call_id == original_call.agent_call_id else item
        for item in fixture.agent_calls
    ]
    call_fixture = fixture.model_copy(update={"agent_calls": calls})
    with pytest.raises(ValueError, match="验收结果引用不得重复"):
        validate_fixture_scope(
            call_fixture, _trusted_registry_from_fixture(call_fixture)
        )


def test_fixture_scope_validates_gates_for_unused_registered_agent_call() -> None:
    fixture = FixtureV1.model_validate(load_json(FIXTURE_PATHS[0]))
    source_call = fixture.agent_calls[0]
    source_schema_gate = next(
        gate
        for gate in fixture.gate_results
        if gate.gate_result_id == source_call.gate_result_ids[0]
    )
    extra_call_id = "call-unused-extra"
    extra_schema_gate_id = "gate-unused-extra-schema"
    extra_other_gate_id = "gate-unused-extra-other"
    extra_call = source_call.model_copy(
        update={
            "agent_call_id": extra_call_id,
            "idempotency_key": "unused-extra-agent-call",
            "gate_result_ids": [extra_schema_gate_id, extra_other_gate_id],
        }
    )
    extra_schema_gate = source_schema_gate.model_copy(
        update={
            "gate_result_id": extra_schema_gate_id,
            "input_entity_refs": [extra_call_id],
            "accepted_entity_refs": [extra_call_id],
            "idempotency_key": "gate:unused-extra-schema",
        }
    )
    extra_other_gate = source_schema_gate.model_copy(
        update={
            "gate_result_id": extra_other_gate_id,
            "gate_name": "additional-output-gate",
            "input_scope_hash": "f" * 64,
            "input_revision_map": {"wrong-scope": 9},
            "input_entity_refs": [extra_call_id],
            "accepted_entity_refs": [extra_call_id],
            "idempotency_key": "gate:unused-extra-other",
        }
    )
    invalid_fixture = fixture.model_copy(
        update={
            "agent_calls": [*fixture.agent_calls, extra_call],
            "gate_results": [
                *fixture.gate_results,
                extra_schema_gate,
                extra_other_gate,
            ],
        }
    )
    with pytest.raises(ValueError, match="每项验收结果都必须完整接受"):
        validate_fixture_scope(
            invalid_fixture, _trusted_registry_from_fixture(invalid_fixture)
        )


def test_fixture_scope_rejects_orphan_gate_and_orphan_gate_subgraph() -> None:
    fixture = FixtureV1.model_validate(load_json(FIXTURE_PATHS[0]))
    source_gate = fixture.gate_results[0]
    orphan_gate = source_gate.model_copy(
        update={
            "gate_result_id": "gate-orphan",
            "input_scope_hash": "f" * 64,
            "input_revision_map": {"orphan": 1},
            "input_entity_refs": ["orphan-input"],
            "accepted_entity_refs": ["orphan-output"],
            "idempotency_key": "gate:orphan",
            "output_hash": "e" * 64,
        }
    )
    orphan_fixture = fixture.model_copy(
        update={"gate_results": [*fixture.gate_results, orphan_gate]}
    )
    with pytest.raises(ValueError, match="孤立验收结果"):
        validate_fixture_scope(
            orphan_fixture, _trusted_registry_from_fixture(orphan_fixture)
        )

    schema_gate = next(
        item
        for item in fixture.gate_results
        if item.gate_name == "agent-output-schema-gate"
    )
    schema_gate_with_orphan_ref = schema_gate.model_copy(
        update={
            "input_entity_refs": [
                *schema_gate.input_entity_refs,
                orphan_gate.gate_result_id,
            ]
        }
    )
    smuggled_orphan_fixture = fixture.model_copy(
        update={
            "gate_results": [
                *[
                    schema_gate_with_orphan_ref
                    if item.gate_result_id == schema_gate.gate_result_id
                    else item
                    for item in fixture.gate_results
                ],
                orphan_gate,
            ]
        }
    )
    with pytest.raises(ValueError, match="孤立验收结果"):
        validate_fixture_scope(
            smuggled_orphan_fixture,
            _trusted_registry_from_fixture(smuggled_orphan_fixture),
        )

    orphan_a = orphan_gate.model_copy(
        update={
            "gate_result_id": "gate-orphan-a",
            "input_entity_refs": ["gate-orphan-b"],
            "idempotency_key": "gate:orphan-a",
        }
    )
    orphan_b = orphan_gate.model_copy(
        update={
            "gate_result_id": "gate-orphan-b",
            "input_entity_refs": ["gate-orphan-a"],
            "idempotency_key": "gate:orphan-b",
        }
    )
    orphan_subgraph_fixture = fixture.model_copy(
        update={
            "gate_results": [*fixture.gate_results, orphan_a, orphan_b]
        }
    )
    with pytest.raises(ValueError, match="孤立验收结果"):
        validate_fixture_scope(
            orphan_subgraph_fixture,
            _trusted_registry_from_fixture(orphan_subgraph_fixture),
        )


def test_fixture_scope_rejects_registered_unpublished_assessment_candidate() -> None:
    fixture = FixtureV1.model_validate(load_json(FIXTURE_PATHS[0]))
    source_candidate = fixture.assessment_candidates[0]
    unpublished_candidate = source_candidate.model_copy(
        update={"assessment_candidate_id": "candidate-registered-unpublished"}
    )
    invalid_fixture = fixture.model_copy(
        update={
            "assessment_candidates": [
                *fixture.assessment_candidates,
                unpublished_candidate,
            ]
        }
    )

    with pytest.raises(ValueError, match="必须完整进入 FinalAssessment 发布链"):
        validate_fixture_scope(
            invalid_fixture,
            _trusted_registry_from_fixture(invalid_fixture),
        )


def test_stage_isolation_gate_rejects_cross_project_episode() -> None:
    fixture = FixtureV1.model_validate(load_json(FIXTURE_PATHS[0]))
    registry = _trusted_registry_from_fixture(fixture)
    invalid_episode = fixture.review_episode.model_copy(update={"project_id": "project-other"})
    invalid_fixture = fixture.model_copy(update={"review_episode": invalid_episode})
    with pytest.raises(ValueError, match="review_episode 与服务端已登记版本不一致"):
        validate_fixture_scope(invalid_fixture, registry)


def test_stage_isolation_gate_rejects_future_stage_source() -> None:
    fixture = FixtureV1.model_validate(load_json(FIXTURE_PATHS[0]))
    registry = _trusted_registry_from_fixture(fixture)
    future_document = fixture.source_documents[0].model_copy(
        update={"review_stage": ReviewStage.BASELINE}
    )
    invalid_fixture = fixture.model_copy(update={"source_documents": [future_document]})
    with pytest.raises(
        ValueError,
        match="source_document_version 与服务端已登记版本不一致",
    ):
        validate_fixture_scope(invalid_fixture, registry)


def test_stage_isolation_rejects_cross_subject_fact_and_rejected_publication_gate() -> None:
    fixture = FixtureV1.model_validate(load_json(FIXTURE_PATHS[0]))
    registry = _trusted_registry_from_fixture(fixture)
    cross_subject_fact = fixture.facts[0].model_copy(update={"subject_id": "subject-other"})
    with pytest.raises(ValueError, match="ClinicalFact 超出|accepted Evidence Candidate"):
        validate_fixture_scope(
            fixture.model_copy(
                update={"facts": [cross_subject_fact, *fixture.facts[1:]]}
            ),
            registry,
        )

    assessment = fixture.final_assessments[0]
    rejected = next(
        gate
        for gate in fixture.gate_results
        if gate.gate_result_id == assessment.gate_result_id
    ).model_copy(
        update={
            "result": GateOutcome.REJECTED,
            "accepted_entity_refs": [],
            "rejected_entity_refs": [assessment.assessment_id],
            "error_codes": [RuntimeErrorCode.SYNTHETIC_REJECTION],
        }
    )
    gates = [
        rejected if gate.gate_result_id == rejected.gate_result_id else gate
        for gate in fixture.gate_results
    ]
    with pytest.raises(ValueError, match="gate_result 与服务端已登记版本不一致"):
        validate_fixture_scope(
            fixture.model_copy(update={"gate_results": gates}), registry
        )


def test_protocol_diff_codes_are_derived_from_real_rule_sets() -> None:
    payload = load_json(UAT_FIXTURE_PATH)
    payload["protocol_diff"]["added_rule_codes"] = ["EX-99"]
    with pytest.raises(ValueError, match="实际差异"):
        UatWorkspaceFixture.model_validate(payload)


def test_fixture_rejects_synchronously_rehashed_service_command() -> None:
    fixture = FixtureV1.model_validate(load_json(FIXTURE_PATHS[0]))
    registry = _trusted_registry_from_fixture(fixture)
    forged_command = build_service_command_event(
        command_id=fixture.protocol_authority_command.command_id,
        record=fixture.protocol_authority_record,
        actor_id="other-reviewer",
        occurred_at=fixture.protocol_authority_command.occurred_at,
    )
    forged_registry = _issue_trusted_registry(
        protocol_authority_records=[fixture.protocol_authority_record],
        service_command_events=[forged_command],
    )
    forged_confirmation = build_protocol_authority_confirmation(
        confirmation_id=fixture.protocol_authority_confirmation.confirmation_id,
        command_event=forged_command,
        record=fixture.protocol_authority_record,
        registry=forged_registry,
    )
    forged_fixture = fixture.model_copy(
        update={
            "protocol_authority_command": forged_command,
            "protocol_authority_confirmation": forged_confirmation,
        }
    )
    with pytest.raises(ValueError, match="已登记版本"):
        validate_fixture_scope(forged_fixture, registry)


def test_fixture_rejects_synchronously_rehashed_protocol_source() -> None:
    fixture = FixtureV1.model_validate(load_json(FIXTURE_PATHS[0]))
    registry = _trusted_registry_from_fixture(fixture)
    original = fixture.protocol_source_records[0]
    forged_source = build_protocol_source_record(
        source_ref=original.source_ref,
        protocol_version_id=original.protocol_version_id,
        protocol_document_sha256=original.protocol_document_sha256,
        locator=f"{original.locator}-changed",
    )
    forged_fixture = fixture.model_copy(
        update={
            "protocol_source_records": [
                forged_source,
                *fixture.protocol_source_records[1:],
            ]
        }
    )
    with pytest.raises(ValueError, match="已登记版本"):
        validate_fixture_scope(forged_fixture, registry)
