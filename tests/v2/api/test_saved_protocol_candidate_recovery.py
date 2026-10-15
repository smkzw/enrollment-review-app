"""A failed DOCX run can create a new review attempt without fake generation."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.agents.protocol_deconstructor import ProtocolAgentCallError, _hydrate_semantic_candidate
from app.domain.contracts.agent_io import ProtocolSemanticDeconstructionCandidate
from app.domain.publication import canonical_hash
from app.evidence.artifacts import ArtifactStore
from app.services.protocol_deconstruction_executor import ProtocolDeconstructionExecutorConfig, create_protocol_deconstruction_executor
from app.services.protocol_workbench_service import PROTOCOL_DECONSTRUCTION_JOB_TYPE, STEP_FREEZE
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner
from tests.v2.api.protocol_e2e_helpers import build_passing_draft_json, page_texts_from_blocks
from tests.v2.api.test_protocols_api import _create_protocol_job, _pipeline_docx_bytes, _run_until


def _failed_source(client, app):
    job_id = _create_protocol_job(client, key="source-for-proposal-recovery", docx_bytes=_pipeline_docx_bytes())
    _run_until(client, app, job_id, awaiting_user="identity")
    response = client.post(f"/api/v2/protocol/deconstructions/{job_id}/identity/confirm", json={
        "protocol_code": "E2E-001", "project_name": "E2E 测试研究", "official_version": "V1.0",
        "official_date_value": "2026-08-17", "official_date_precision": "day", "study_phase": "phase_ii",
        "actor": "测试用户",
    })
    assert response.status_code == 200, response.text
    captured = {}

    def retain_then_fail(package):
        candidate = ProtocolSemanticDeconstructionCandidate.model_validate_json(build_passing_draft_json(package))
        captured["draft"] = _hydrate_semantic_candidate(package.source_input, candidate)
        raise ProtocolAgentCallError("failed-call", "终止调用", error_code="MODEL_IDENTITY_MISMATCH")

    executor = create_protocol_deconstruction_executor(ProtocolDeconstructionExecutorConfig(
        data_paths=app.state.data_paths, session_factory=app.state.session_factory,
        page_texts_builder=page_texts_from_blocks, draft_response_builder=retain_then_fail,
    ))
    JobRunner(app.state.session_factory, {PROTOCOL_DECONSTRUCTION_JOB_TYPE: executor}, worker_id="source-test").run_job(job_id)
    with app.state.session_factory() as session:
        store = JobStore(session)
        assert store.get_job(job_id).state == "failed_final"
        _, frozen = store.get_last_checkpoint(job_id, STEP_FREEZE)
        before = [(c_id, payload) for step in store.list_steps(job_id) for c_id, payload in store.list_checkpoints(job_id, step.step_id)]
    ref = ArtifactStore(app.state.data_paths).put("evaluation_manifest", captured["draft"].model_dump_json().encode()).storage_ref
    return job_id, {"candidate_ref": ref, "candidate_origin": "operator_imported_unpublished",
        "expected_freeze_sha256": canonical_hash(frozen), "idempotency_key": "saved-proposal-1"}, before


def test_recovery_uses_new_job_current_gate_and_real_saved_revision(build_app, monkeypatch):
    app = build_app(run_runner=False)
    with TestClient(app) as client:
        source_job, body, before = _failed_source(client, app)
        response = client.post(f"/api/v2/protocol/deconstructions/{source_job}/recover-saved-candidate", json=body)
        assert response.status_code == 201, response.text
        job_id = response.json()["job_id"]
        assert job_id != source_job

        def no_model(*args, **kwargs):
            pytest.fail("Recovery must not pretend to run an author or reset its budget")

        executor = create_protocol_deconstruction_executor(ProtocolDeconstructionExecutorConfig(
            data_paths=app.state.data_paths, session_factory=app.state.session_factory,
            page_texts_builder=no_model, draft_response_builder=no_model,
        ))
        JobRunner(app.state.session_factory, {PROTOCOL_DECONSTRUCTION_JOB_TYPE: executor}, worker_id="recovery-test").run_job(job_id)
        view = client.get(f"/api/v2/protocol/deconstructions/{job_id}")
        assert view.status_code == 200, view.text
        assert view.json()["awaiting_user"] == "review", view.text
        draft = client.get(f"/api/v2/protocol/deconstructions/{job_id}/draft")
        assert draft.status_code == 200, draft.text
        assert draft.json()["revision_number"] == 1
        assert draft.json()["imported_unpublished_proposal"] is True
        assert client.get(f"/api/v2/protocol/deconstructions/{job_id}/sources").status_code == 200
        assert client.get(f"/api/v2/protocol/deconstructions/{job_id}/integrity").status_code == 200
        repeated = client.post(f"/api/v2/protocol/deconstructions/{source_job}/recover-saved-candidate", json=body)
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()["job_id"] == job_id
        with app.state.session_factory() as session:
            store = JobStore(session)
            assert store.get_job(source_job).state == "failed_final"
            after = [(c_id, payload) for step in store.list_steps(source_job) for c_id, payload in store.list_checkpoints(source_job, step.step_id)]
            assert before == after
            _, generated = store.get_last_checkpoint(job_id, "generate_draft")
            assert generated["saved_candidate_recovery"]["new_model_reading"] is False
            assert generated["saved_candidate_recovery"]["current_gate_checked"] is True
            assert generated["saved_candidate_recovery"]["candidate_origin"] == "operator_imported_unpublished"
            _, original = store.get_last_checkpoint(source_job, STEP_FREEZE)
            _, recovered = store.get_last_checkpoint(job_id, STEP_FREEZE)
            assert original["source_input"] == recovered["source_input"]
        merged = app.state.protocol_workbench_service._merged_payload(job_id)
        budget_owner, source, renewal = app.state.protocol_workbench_service._validated_saved_recovery_context(merged)
        assert budget_owner == source_job
        assert renewal is None
        assert source.model_dump(mode="json") == original["source_input"]
        from app.services.protocol_workbench_service import ProtocolWorkbenchService
        seen = []

        def bounded_failure(source_input, current_draft, target_rule_code, note, target_component_id,
                            *, joint_source_repair, budget_store):
            seen.append(budget_store._root)
            raise ProtocolAgentCallError("same-original-budget", "原核对次数已用完",
                error_code="LOGICAL_BUDGET_EXHAUSTED",
                error_metadata={"first_completion_failure": {"error_code": "SCHEMA_INVALID", "line": 1, "column": 1}})

        monkeypatch.setattr(ProtocolWorkbenchService, "_revise_feedback_with_model", staticmethod(bounded_failure))
        content = draft.json()["content"]
        parent = content["proposed_rules"][0]
        response = client.post(f"/api/v2/protocol/deconstructions/{job_id}/draft/feedback", json={
            "expected_revision_id": draft.json()["revision_id"], "feedback_kind": "source_error",
            "feedback_note": "只核所选子项", "target_rule_code": parent["official_code"],
            "target_component_id": parent["components"][0]["rule_component_id"],
        })
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "LOGICAL_BUDGET_EXHAUSTED"
        assert "格式无法读取" in response.json()["error"]["detail"]
        proof = json.loads(ArtifactStore(app.state.data_paths).read(response.json()["error"]["context"]["call_failure_ref"]))
        assert proof["accepted"] is False
        assert proof["call_metadata"]["first_completion_failure"]["error_code"] == "SCHEMA_INVALID"
        assert seen == [app.state.data_paths.blobs_dir / "protocol-semantic-batches" / source_job]
        assert client.get(f"/api/v2/protocol/deconstructions/{job_id}/draft").json()["revision_id"] == draft.json()["revision_id"]


def test_source_freeze_renewal_changes_only_timestamp_metadata_and_rejects_content_changes(build_app):
    from datetime import timedelta
    from app.domain.contracts.agent_io import ProtocolDeconstructionInput
    from app.domain.contracts.protocol_ingestion import FrozenProtocolCatalog, frozen_catalog_content_hash
    from app.services.protocol_saved_draft_recovery import SavedDraftRecoveryError, reconcile_saved_source_identity
    app = build_app(run_runner=False)
    with TestClient(app) as client:
        source_job, _body, before = _failed_source(client, app)
        with app.state.session_factory() as session:
            _, frozen = JobStore(session).get_last_checkpoint(source_job, STEP_FREEZE)
        original = ProtocolDeconstructionInput.model_validate(frozen["source_input"])
        catalogs = {}
        for key in ("parent_rule_catalog", "required_procedure_catalog"):
            catalog = getattr(original, key).model_copy(update={"frozen_at": getattr(original, key).frozen_at + timedelta(days=1)})
            catalog = catalog.model_copy(update={"catalog_sha256": frozen_catalog_content_hash(catalog)})
            catalogs[key] = FrozenProtocolCatalog.model_validate(catalog.model_dump(mode="json"))
        current = original.model_copy(update=catalogs)
        renewed, proof = reconcile_saved_source_identity(current, original)
        assert renewed == original and proof["new_model_reading"] is False
        assert proof["previous_source_sha256"] != proof["renewed_source_sha256"]
        assert reconcile_saved_source_identity(renewed, original) == (original, None)
        changed = current.model_copy(update={"protocol_file_sha256": "0" * 64})
        with pytest.raises(SavedDraftRecoveryError):
            reconcile_saved_source_identity(changed, original)
        catalog = current.parent_rule_catalog
        item = catalog.items[0].model_copy(update={"source_span_ids": ("foreign-source",)})
        changed = current.model_copy(update={"parent_rule_catalog": catalog.model_copy(update={"items": (item, *catalog.items[1:])})})
        with pytest.raises(SavedDraftRecoveryError):
            reconcile_saved_source_identity(changed, original)
        with app.state.session_factory() as session:
            store = JobStore(session)
            assert before == [(c_id, payload) for step in store.list_steps(source_job) for c_id, payload in store.list_checkpoints(source_job, step.step_id)]


@pytest.mark.parametrize("fault", ["freeze", "candidate_scope", "artifact", "original", "blocks"])
def test_recovery_rejects_broken_or_foreign_source_before_creating_job(build_app, fault):
    app = build_app(run_runner=False)
    with TestClient(app) as client:
        source_job, body, _ = _failed_source(client, app)
        if fault == "freeze":
            body["expected_freeze_sha256"] = "0" * 64
        elif fault == "candidate_scope":
            artifacts = ArtifactStore(app.state.data_paths)
            payload = json.loads(artifacts.read(body["candidate_ref"]))
            payload["project_id"] = "foreign-project"
            body["candidate_ref"] = artifacts.put("evaluation_manifest", json.dumps(payload).encode()).storage_ref
        elif fault == "artifact":
            app.state.data_paths.root.joinpath(body["candidate_ref"]).write_bytes(b"corrupt")
        elif fault == "original":
            with app.state.session_factory() as session:
                _, record = JobStore(session).get_last_checkpoint(source_job, "register_file")
            app.state.data_paths.blobs_dir.joinpath(record["storage_ref"]).write_bytes(b"changed-original")
        else:
            with app.state.session_factory() as session:
                _, record = JobStore(session).get_last_checkpoint(source_job, "extract_structure")
            app.state.data_paths.blobs_dir.joinpath(record["content_storage_ref"]).write_bytes(b"changed-blocks")
        response = client.post(f"/api/v2/protocol/deconstructions/{source_job}/recover-saved-candidate", json=body)
        assert response.status_code in {409, 422}, response.text
        assert "SAVED_DRAFT_RECOVERY_INVALID" in response.text
        with app.state.session_factory() as session:
            assert JobStore(session).get_job(source_job).state == "failed_final"
