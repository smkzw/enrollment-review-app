"""Public start-contract checks for protocol-control execution."""
from __future__ import annotations

import hashlib
import pytest

from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunner
from app.domain.contracts.rules import WorkflowStage
from app.protocols.protocol_control_gate import validate_protocol_control_batch_candidates
from app.services.protocol_control_execution import _validate_saved_source_review
from app.services.protocol_control_status import ProtocolControlRequirementsView
from tests.v2.protocols.test_protocol_control_fixed_flow import _separate_heading_example, _Transport
from tests.v2.domain.test_control_catalog_restricted_contract import _unresolved_batch_review
from app.services.protocol_control_restricted_source import restricted_batch_from_review

from tests.v2.services.test_protocol_control_execution import _seed_frozen_source


_ENDPOINT = "/api/v2/protocol/control-executions"


@pytest.mark.parametrize("code, phrase", [
    ("SOURCE_TARGET_REVIEW_UNRESOLVED", "对应关系"),
    ("SOURCE_REQUIREMENT_CONSUMER_UNAVAILABLE", "由系统建设继续处理"),
    ("SOURCE_REQUIREMENT_INSERTION_LIMIT_REACHED", "已核清的部分仍保留"),
    ("SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED", "忠实表达"),
    ("DEFINITION_SCOPE_INVALID", "定义影响哪些要求"),
    ("DEFINITION_SCOPE_TRANSPORT_FAILED", "可按原范围重试"),
    ("DEFINITION_SCOPE_COMPLETION_UNCERTAIN", "不会立即重复发送"),
    ("LOGICAL_BUDGET_EXHAUSTED", "达到约定次数"),
    ("BUDGET_RECORD_INVALID", "原调用记录不完整"),
    ("BUDGET_INVALID", "尚未发送请求"),
    ("BUDGET_UNSUPPORTED", "无法遵守约定次数"),
    ("DEFINITION_SCOPE_UNAVAILABLE", "无法核对定义"),
    ("CHECKPOINT_MISSING", "前一步保存的内容缺失"),
    ("CHECKPOINT_INVALID", "未继续采用"),
    ("DEEP_OUTPUT_INVALID", "整理未完成"),
])
def test_saved_failure_reason_reaches_status_api_without_publication(client, code, phrase):
    from app.workflow.jobstore import JobStore

    seed = _seed_frozen_source(
        client.app.state.data_paths, client.app.state.session_factory, key="api-control-reason",
    )
    client.app.state.protocol_control_job_service.route_identity_factory = (
        lambda stage: hashlib.sha256(stage.encode("utf-8")).hexdigest()
    )
    created = client.post(_ENDPOINT, json={
        "source_job_id": seed.source_job_id, "idempotency_key": "control-reason",
    })
    assert created.status_code == 201
    job_id = created.json()["job_id"]
    with client.app.state.session_factory() as session:
        job = JobStore(session).get_job(job_id)
        job.state = "failed_final"
        job.error_code = "PROTOCOL_CONTROL_" + code
        session.commit()
    response = client.get(_ENDPOINT + "/" + job_id)
    assert response.status_code == 200
    payload = response.json()
    assert phrase in payload["status_label"]
    assert "SOURCE_" not in payload["status_label"]
    assert payload["status"] == "stopped"
    assert payload["publishable_checkpoint_id"] is None
    assert payload["candidate_count"] is None
    assert client.get(_ENDPOINT + "/" + job_id + "/requirements").status_code == 409


def test_start_is_idempotent_and_hides_engineering_parameters(client):
    seed = _seed_frozen_source(
        client.app.state.data_paths,
        client.app.state.session_factory,
        key="api-control-start",
    )
    body = {
        "source_job_id": seed.source_job_id,
        "idempotency_key": "api-control-idempotency",
    }
    # This API test checks creation and idempotency, not live model availability.
    client.app.state.protocol_control_job_service.route_identity_factory = (
        lambda stage: hashlib.sha256(stage.encode("utf-8")).hexdigest()
    )

    first = client.post(_ENDPOINT, json=body)
    assert first.status_code == 201
    first_payload = first.json()
    assert first_payload["created"] is True
    assert first_payload["source_job_id"] == seed.source_job_id

    second = client.post(_ENDPOINT, json=body)
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["created"] is False
    assert second_payload["job_id"] == first_payload["job_id"]
    assert second_payload["snapshot_id"] == first_payload["snapshot_id"]
    assert second_payload["manifest_id"] == first_payload["manifest_id"]

    invalid = client.post(
        _ENDPOINT,
        json={
            **body,
            "max_deep_units_per_batch": 1,
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_REQUEST"


def test_start_checks_requested_deep_source_before_creating_job(client, monkeypatch):
    seed = _seed_frozen_source(client.app.state.data_paths, client.app.state.session_factory,
                               key="api-control-deep-reuse")
    service = client.app.state.protocol_control_job_service
    service.route_identity_factory = lambda stage: hashlib.sha256(stage.encode()).hexdigest()
    calls = []
    original = service.create_from_deconstruction

    def capture(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(service, "create_from_deconstruction", capture)
    with client.app.state.session_factory() as session:
        before = session.connection().exec_driver_sql("select count(*) from jobs").scalar_one()
    response = client.post(_ENDPOINT, json={
        "source_job_id": seed.source_job_id, "idempotency_key": "api-control-deep-reuse",
        "deep_source_job_id": "missing-deep-source",
        "recompute_missing_diagnostic_steps": ["deep_0001"],
    })
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PROTOCOL_CONTROL_DEEP_SOURCE_INVALID"
    assert calls[0]["deep_source_job_id"] == "missing-deep-source"
    assert calls[0]["recompute_missing_diagnostic_steps"] == ["deep_0001"]
    with client.app.state.session_factory() as session:
        assert session.connection().exec_driver_sql("select count(*) from jobs").scalar_one() == before


def test_requirement_response_keeps_saved_heading_separate_from_action_source(client, monkeypatch):
    """Real assembly/read-back plus API serialization; checkpoint lookup is stubbed."""
    batch, inventory, review, selection = _separate_heading_example()
    result = ProtocolControlAgentRunner().run(
        batch, _Transport(review, selection), resume_source_interpretation=inventory,
        workflow_variant="RV1001-FLOW",
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    restored = type(result).model_validate_json(result.model_dump_json())
    _validate_saved_source_review(batch, restored)
    view = ProtocolControlRequirementsView(
        job_id="control-scoped", source_job_id="source-scoped", checkpoint_id="checkpoint-scoped",
        candidates=tuple(restored.final_output.candidates),
        workflow_stages=tuple(WorkflowStage(
            workflow_stage_id=node.workflow_stage_id, stage=node.review_stage,
            display_name=node.display_name, visit_instance=node.visit_instance,
        ) for node in batch.known_workflow_stage_targets),
        relation_target_labels={}, calculation_gaps=(), restricted_statements=(),
    )
    monkeypatch.setattr("app.api.v2.protocol_control.protocol_control_requirements",
                        lambda *_args, **_kwargs: view)
    response = client.get(_ENDPOINT + "/control-scoped/requirements")
    assert response.status_code == 200
    semantics = response.json()["candidates"][0]["semantics"]
    citation = semantics["review_node_bindings"][0]["scope_citation"]
    assert citation["source_excerpt"] == inventory.statements[0].scope_quote
    assert citation["structure_unit_id"] == "scope-heading"
    assert citation["source_span_ids"] == ["span:heading"]
    assert len(citation["source_unit_sha256"]) == 64
    action = semantics["obligation_expression"]["groups"][0]["atoms"][0]
    assert action["source_excerpts"] == [inventory.statements[0].quoted_text]
    assert "span:heading" not in action["source_span_ids"]


def test_requirement_api_preserves_actual_restricted_producer_output(client, monkeypatch):
    batch, result = _unresolved_batch_review()
    saved = type(result).model_validate_json(result.model_dump_json())
    restricted = restricted_batch_from_review(batch, saved)
    assert restricted is not None
    statements = tuple(restricted.restricted_statements)
    view = ProtocolControlRequirementsView(
        job_id="restricted-job", source_job_id="source-job", checkpoint_id="checkpoint",
        candidates=(), workflow_stages=(), relation_target_labels={}, calculation_gaps=(),
        restricted_statements=statements,
    )
    monkeypatch.setattr("app.api.v2.protocol_control.protocol_control_requirements",
                        lambda *_args, **_kwargs: view)
    response = client.get(_ENDPOINT + "/restricted-job/requirements")
    assert response.status_code == 200
    payload = response.json()
    assert payload["candidates"] == []
    assert payload["restricted_statements"] == [item.model_dump(mode="json") for item in statements]
    assert all("obligation_expression" not in row for row in payload["restricted_statements"])
