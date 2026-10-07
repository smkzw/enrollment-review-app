"""V2 方案解构 API 集成测试。"""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.api.v2.protocols import _metadata_candidate_dto, _phase_candidate_dtos
from app.domain.contracts.enums import (
    AnchorResolutionMode,
    InterpretationSourceType,
    ReviewStage,
    StudyPhase,
)
from app.services.protocol_deconstruction_executor import (
    ProtocolDeconstructionExecutorConfig,
    _handle_generate,
    create_protocol_deconstruction_executor,
)
from app.services.protocol_workbench_service import (
    PROTOCOL_DECONSTRUCTION_JOB_TYPE,
    PROTOCOL_DECONSTRUCTION_STEPS,
    STEP_FREEZE,
    STEP_GENERATE,
    STEP_RENDER,
    ProtocolWorkbenchService,
)
from app.workflow.runner import JobRunner, StepContext
from app.workflow.jobstore import JobStore
from tests.v2.api.protocol_e2e_helpers import (
    build_passing_draft_json,
    build_pipeline_e2e_docx,
    page_texts_from_blocks,
)
from tests.v2.protocols.slice4_helpers import confirmed_fixture
from tests.v2.protocols.joint_publication_helpers import seed_joint_control_publication


def _minimal_docx_bytes() -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as handle:
        path = Path(handle.name)
    doc = Document()
    doc.add_paragraph("临床研究方案")
    doc.add_paragraph("方案编号：TEST-001")
    doc.save(str(path))
    payload = path.read_bytes()
    path.unlink(missing_ok=True)
    return payload


def _pipeline_docx_bytes() -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as handle:
        path = Path(handle.name)
    build_pipeline_e2e_docx(path)
    payload = path.read_bytes()
    path.unlink(missing_ok=True)
    return payload


def _create_protocol_job(
    client: TestClient,
    *,
    key: str = "proto-key-1",
    docx_bytes: bytes | None = None,
) -> str:
    payload = docx_bytes if docx_bytes is not None else _minimal_docx_bytes()
    files = {
        "file": (
            "test-protocol.docx",
            io.BytesIO(payload),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    data = {"idempotency_key": key, "actor": "测试用户"}
    response = client.post("/api/v2/protocol/deconstructions", files=files, data=data)
    assert response.status_code == 201, response.text
    return response.json()["job_id"]


def _test_executor(app) -> JobRunner:
    executor = create_protocol_deconstruction_executor(
        ProtocolDeconstructionExecutorConfig(
            data_paths=app.state.data_paths,
            session_factory=app.state.session_factory,
            page_texts_builder=page_texts_from_blocks,
            draft_response_builder=build_passing_draft_json,
        )
    )
    return JobRunner(
        app.state.session_factory,
        {PROTOCOL_DECONSTRUCTION_JOB_TYPE: executor},
        worker_id="test-runner",
        poll_interval=0.01,
    )


def _run_until(client: TestClient, app, job_id: str, *, awaiting_user: str, limit: int = 40) -> None:
    runner = _test_executor(app)
    for _ in range(limit):
        session = client.get(f"/api/v2/protocol/deconstructions/{job_id}").json()
        if session.get("awaiting_user") == awaiting_user:
            return
        runner.run_job(job_id)
    session = client.get(f"/api/v2/protocol/deconstructions/{job_id}").json()
    pytest.fail(
        f"任务未在 {limit} 次推进后到达 awaiting_user={awaiting_user!r}；"
        f"当前状态={session.get('state')!r} awaiting_user={session.get('awaiting_user')!r}"
    )


def _seed_review_job(app, job_id: str, *, wait_at: str | None = None) -> tuple:
    source_input, draft, spans = confirmed_fixture()
    service: ProtocolWorkbenchService = app.state.protocol_workbench_service
    kwargs: dict = {
        "source_input": source_input,
        "draft": draft,
        "source_spans": spans,
    }
    if wait_at is not None:
        kwargs["wait_at"] = wait_at
    service.seed_review_session(job_id, **kwargs)
    return source_input, draft


def _joint_publish_payload(app, job_id: str, *, key: str) -> dict:
    service = app.state.protocol_workbench_service
    view = service.get_draft_detail(job_id)
    merged = service._merged_payload(job_id)
    source = service._load_source_input(merged)
    spans = service._load_source_spans(merged)
    control_job, checkpoint = seed_joint_control_publication(
        app.state.session_factory, app.state.data_paths,
        source, view.revision.content, spans, view.revision.revision_id,
    )
    return {"idempotency_key": key, "actor": "医学监查员",
            "control_job_id": control_job, "control_checkpoint_id": checkpoint}


def test_upload_registers_source_and_creates_protocol_job(client) -> None:
    job_id = _create_protocol_job(client, key="upload-1")
    session = client.get(f"/api/v2/protocol/deconstructions/{job_id}")
    assert session.status_code == 200
    body = session.json()
    assert body["job_type"] == PROTOCOL_DECONSTRUCTION_JOB_TYPE
    assert body["file_name"] == "test-protocol.docx"
    assert body["source_artifact_id"]
    assert body["progress_total"] == len(PROTOCOL_DECONSTRUCTION_STEPS)
    assert body["progress_completed"] >= 1


def test_pdf_protocol_upload_rejected_after_entry_decommission(build_app) -> None:
    """方案 PDF 上传入口已下线：上传直接被拒绝并给出中文指引，不创建任务。"""
    app = build_app(run_runner=False)
    with TestClient(app) as client:
        files = {
            "file": (
                "test-protocol.pdf",
                io.BytesIO(b"%PDF-1.7 decommissioned entry check"),
                "application/pdf",
            )
        }
        response = client.post(
            "/api/v2/protocol/deconstructions",
            files=files,
            data={"idempotency_key": "pdf-decommissioned", "actor": "测试用户"},
        )

        assert response.status_code == 409
        error = response.json()["error"]
        assert error["code"] == "UNSUPPORTED_PROTOCOL_FILE"
        assert "方案 PDF 上传入口已下线" in error["detail"]
        assert error["recovery_action"] == "请以 DOCX 重新上传正式方案。"


def test_semantic_draft_step_keeps_one_bounded_automatic_retry() -> None:
    generate = next(
        step for step in PROTOCOL_DECONSTRUCTION_STEPS if step.step_id == STEP_GENERATE
    )

    assert generate.retryable is True
    assert generate.max_attempts == 2


def test_frozen_input_precedes_semantic_generation() -> None:
    step_ids = [step.step_id for step in PROTOCOL_DECONSTRUCTION_STEPS]
    assert step_ids.index(STEP_FREEZE) < step_ids.index(STEP_GENERATE)
    generate = next(step for step in PROTOCOL_DECONSTRUCTION_STEPS if step.step_id == STEP_GENERATE)
    assert generate.depends_on == (STEP_FREEZE,)


def test_sources_remain_available_when_semantic_service_is_unavailable(
    build_app,
    monkeypatch,
) -> None:
    app = build_app(run_runner=False)
    with TestClient(app) as client:
        job_id = _create_protocol_job(
            client,
            key="freeze-before-semantic-failure",
            docx_bytes=_pipeline_docx_bytes(),
        )
        _run_until(client, app, job_id, awaiting_user="identity")
        confirmed = client.post(
            f"/api/v2/protocol/deconstructions/{job_id}/identity/confirm",
            json={
                "protocol_code": "E2E-001",
                "project_name": "E2E 测试研究",
                "official_version": "V1.0",
                "official_date_value": "2026-08-17",
                "official_date_precision": "day",
                "study_phase": StudyPhase.PHASE_II.value,
                "actor": "测试用户",
            },
        )
        assert confirmed.status_code == 200, confirmed.text

        monkeypatch.setattr(
            "app.services.protocol_deconstruction_executor.DEEPSEEK_API_KEY",
            "",
        )
        monkeypatch.setattr(
            "app.services.protocol_deconstruction_executor.DECONSTRUCT_BACKEND",
            "deepseek",
        )
        monkeypatch.setattr(
            "app.services.protocol_deconstruction_executor.DECONSTRUCT_ROUTE_MODE",
            "pinned",
        )
        executor = create_protocol_deconstruction_executor(
            ProtocolDeconstructionExecutorConfig(
                data_paths=app.state.data_paths,
                session_factory=app.state.session_factory,
                page_texts_builder=page_texts_from_blocks,
            )
        )
        JobRunner(
            app.state.session_factory,
            {PROTOCOL_DECONSTRUCTION_JOB_TYPE: executor},
            worker_id="no-semantic-runner",
            poll_interval=0.01,
        ).run_job(job_id)

        job = client.get(f"/api/v2/jobs/{job_id}").json()
        freeze = next(step for step in job["steps"] if step["step_id"] == STEP_FREEZE)
        generate = next(step for step in job["steps"] if step["step_id"] == STEP_GENERATE)
        assert freeze["state"] == "completed"
        assert generate["error_code"] == "SEMANTIC_PROVIDER_UNAVAILABLE"
        assert generate["state"] == "failed_retryable"

        sources = client.get(f"/api/v2/protocol/deconstructions/{job_id}/sources")
        assert sources.status_code == 200, sources.text
        assert sources.json()["selected_phase_label"] == "II 期"
        assert sources.json()["source_materials"]


@pytest.mark.parametrize(
    ("error_code", "expected_state"),
    [("STREAM_INTERRUPTED", "failed_retryable"),
     ("MODEL_IDENTITY_MISMATCH", "failed_final")],
)
def test_retained_candidate_after_terminal_call_is_diagnostic_not_saved_draft(
    build_app, monkeypatch, error_code: str, expected_state: str,
) -> None:
    from types import SimpleNamespace

    from app.agents.protocol_deconstructor import (
        ProtocolDeconstructionAttempt,
        ProtocolDeconstructionRunResult,
        ProtocolDeconstructorRunner,
        _hydrate_semantic_candidate,
        _parse_semantic_candidate,
    )
    from app.protocols.deconstruction_gate import ProtocolDeconstructionGate
    from app.storage.repositories import ProtocolDraftRevisionRepository

    captured = {}

    def failed_run(self, source_input, **kwargs):
        captured["source_input"] = source_input
        draft = _hydrate_semantic_candidate(
            source_input,
            _parse_semantic_candidate(build_passing_draft_json(
                SimpleNamespace(source_input=source_input),
            )),
        )
        gate = ProtocolDeconstructionGate().evaluate(
            source_input, draft, source_spans=kwargs["source_spans"],
        )
        return ProtocolDeconstructionRunResult(
            status="需要核对", same_session_id="synthetic-interrupted-session",
            attempts=[ProtocolDeconstructionAttempt(
                attempt=1, session_id="synthetic-interrupted-session",
                raw_output_sha256="a" * 64, outcome="会话异常",
                call_metadata={"error_code": error_code,
                               "private_reasoning": "must-not-enter-checkpoint"},
            )],
            final_draft=draft, final_gate_result=gate,
        )

    app = build_app(run_runner=False)
    with TestClient(app) as client:
        job_id = _create_protocol_job(
            client, key=f"retained-terminal-{error_code}",
            docx_bytes=_pipeline_docx_bytes(),
        )
        _run_until(client, app, job_id, awaiting_user="identity")
        confirmed = client.post(
            f"/api/v2/protocol/deconstructions/{job_id}/identity/confirm",
            json={
                "protocol_code": "E2E-001", "project_name": "E2E 测试研究",
                "official_version": "V1.0", "official_date_value": "2026-08-17",
                "official_date_precision": "day", "study_phase": StudyPhase.PHASE_II.value,
                "actor": "测试用户",
            },
        )
        assert confirmed.status_code == 200, confirmed.text
        monkeypatch.setattr(ProtocolDeconstructorRunner, "run", failed_run)
        _test_executor(app).run_job(job_id)

        job = client.get(f"/api/v2/jobs/{job_id}").json()
        generate = next(step for step in job["steps"] if step["step_id"] == STEP_GENERATE)
        assert generate["state"] == expected_state
        assert generate["error_code"] == error_code
        assert job["state"] == expected_state
        with app.state.session_factory() as session:
            checkpoint = JobStore(session).get_last_checkpoint(job_id, STEP_GENERATE)
            assert checkpoint is not None
            payload = checkpoint[1]
            diagnostic = payload["semantic_generation_failure"]
            assert diagnostic["final_draft"]
            assert diagnostic["attempts"][0]["raw_output_sha256"] == "a" * 64
            assert "call_metadata" not in diagnostic["attempts"][0]
            assert "draft_revision_id" not in payload
            source = captured["source_input"]
            assert ProtocolDraftRevisionRepository(session).find_by_generation_scope(
                project_id=source.project_id, protocol_version_id=source.protocol_version_id,
            ) == []
        assert client.get(
            f"/api/v2/protocol/deconstructions/{job_id}/sources",
        ).status_code == 200
        retry = client.post(f"/api/v2/jobs/{job_id}/retry")
        assert retry.status_code == 200, retry.text
        _test_executor(app).run_job(job_id)
        rerun = client.get(f"/api/v2/jobs/{job_id}").json()
        generate_again = next(step for step in rerun["steps"] if step["step_id"] == STEP_GENERATE)
        assert generate_again["state"] == "failed_final"
        assert generate_again["error_code"] == error_code
        assert next(step for step in rerun["steps"] if step["step_id"] == "integrity_check")["state"] != "completed"


def test_upload_registration_survives_api_claim_race(client, monkeypatch) -> None:
    original_claim_job = JobStore.claim_job
    api_claims = 0

    def claim_job_once_for_runner_race(self, job_id: str, worker_id: str):
        nonlocal api_claims
        if worker_id == ProtocolWorkbenchService.WORKER_ID and api_claims == 0:
            api_claims += 1
            return None
        return original_claim_job(self, job_id, worker_id)

    monkeypatch.setattr(JobStore, "claim_job", claim_job_once_for_runner_race)

    job_id = _create_protocol_job(client, key="upload-claim-race")
    session = client.get(f"/api/v2/protocol/deconstructions/{job_id}")
    assert session.status_code == 200
    assert session.json()["source_artifact_id"]
    assert session.json()["progress_completed"] == 0

    runner = _test_executor(client.app)
    runner.run_job(job_id)
    status = client.get(f"/api/v2/jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["error_code"] != "REGISTER_INCOMPLETE"


def test_upload_idempotent_same_key(client) -> None:
    files = {
        "file": (
            "test-protocol.docx",
            io.BytesIO(_minimal_docx_bytes()),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    data = {"idempotency_key": "upload-dup", "actor": "测试用户"}
    first = client.post("/api/v2/protocol/deconstructions", files=files, data=data)
    second = client.post("/api/v2/protocol/deconstructions", files=files, data=data)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["job_id"] == first.json()["job_id"]
    assert second.json()["created"] is False


def test_missing_job_returns_chinese_envelope(client) -> None:
    response = client.get("/api/v2/protocol/deconstructions/does-not-exist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["title"] == "任务不存在"
    assert "correlation_id" in error


def test_draft_integrity_and_sources_after_seed(client, build_app) -> None:
    app = build_app()
    with TestClient(app) as test_client:
        job_id = _create_protocol_job(test_client, key="seed-review-1")
        _seed_review_job(app, job_id)

        draft = test_client.get(f"/api/v2/protocol/deconstructions/{job_id}/draft")
        assert draft.status_code == 200
        draft_body = draft.json()
        assert draft_body["revision_number"] == 1
        assert draft_body["rule_count"] == 2
        assert draft_body["status_label"] == "已保存"
        assert "content" in draft_body

        integrity = test_client.get(f"/api/v2/protocol/deconstructions/{job_id}/integrity")
        assert integrity.status_code == 200
        integrity_body = integrity.json()
        assert integrity_body["publishable"] is True
        assert integrity_body["blocking_count"] == 0
        assert integrity_body["summary"]

        sources = test_client.get(f"/api/v2/protocol/deconstructions/{job_id}/sources")
        assert sources.status_code == 200
        sources_body = sources.json()
        assert sources_body["selected_phase"] == "phase_ii"
        assert sources_body["selected_phase_label"] == "II 期"
        assert sources_body["source_materials"]

        session = test_client.get(f"/api/v2/protocol/deconstructions/{job_id}")
        assert session.status_code == 200
        assert session.json()["draft_revision_number"] == 1
        assert session.json()["awaiting_user"] == "review"


def test_feedback_without_original_read_ledger_preserves_draft_and_explains(build_app, monkeypatch) -> None:
    import app.agents.protocol_semantic_model_router as router
    monkeypatch.setattr(router, "build_transport_for_candidate",
                        lambda candidate: pytest.fail("missing ledger must stop before model connection"))
    app = build_app()
    with TestClient(app) as test_client:
        job_id = _create_protocol_job(test_client, key="feedback-ledger-missing")
        _source, seeded = _seed_review_job(app, job_id, wait_at="await_review")
        before = test_client.get(f"/api/v2/protocol/deconstructions/{job_id}/draft").json()
        target = seeded.proposed_rules[1].components[0].rule_component_id
        response = test_client.post(
            f"/api/v2/protocol/deconstructions/{job_id}/draft/feedback",
            json={"expected_revision_id": before["revision_id"], "feedback_kind": "source_error",
                  "feedback_note": "只核对当前子项。", "target_rule_code": "EX-01",
                  "target_component_id": target, "actor": "医学监查员"},
        )
        assert response.status_code == 409, response.text
        error = response.json()["error"]
        assert error["code"] == "BUDGET_RECORD_MISSING"
        assert "次数记录未保留" in error["detail"]
        assert "不要反复点击" in error["recovery_action"]
        assert error["context"]["unchanged_revision_id"] == before["revision_id"]
        after = test_client.get(f"/api/v2/protocol/deconstructions/{job_id}/draft").json()
        assert after["revision_id"] == before["revision_id"]
        assert after["content"] == before["content"]


def test_parent_scope_request_saves_proof_through_existing_feedback_api(build_app, monkeypatch):
    from app.services.protocol_scope_review_service import review_official_source_scope
    from tests.v2.protocols.test_official_scope_review import ScopeReader, UncertainScopeReader, scope_fixture
    reader = ScopeReader()

    def revise(source_input, current_draft, target_rule_code, feedback_note, target_component_id,
               *, joint_source_repair, budget_store, scope_review_store):
        assert scope_review_store is not None and target_component_id is None
        return review_official_source_scope(source_input, current_draft, official_code=target_rule_code,
                                           transport=reader, store=scope_review_store)

    monkeypatch.setattr(ProtocolWorkbenchService, "_revise_feedback_with_model", staticmethod(revise))
    app = build_app(run_runner=False)
    with TestClient(app) as client:
        job_id = _create_protocol_job(client, key="parent-scope-feedback")
        source, draft, spans = scope_fixture()
        app.state.protocol_workbench_service.seed_review_session(job_id, source_input=source, draft=draft,
                                                               source_spans=spans, wait_at="await_review")
        url = f"/api/v2/protocol/deconstructions/{job_id}/draft"
        before = client.get(url).json()
        response = client.post(url + "/feedback", json={
            "expected_revision_id": before["revision_id"], "feedback_kind": "source_error",
            "feedback_note": "只核对总标题与各节点的关系。", "target_rule_code": "IN-01", "review_parent_scope": True,
        })
        assert response.status_code == 200, response.text
        after = client.get(url).json()
        assert after["revision_id"] != before["revision_id"]
        component = after["content"]["proposed_rules"][0]["components"][0]
        assert component["source_scope_review_ref"].startswith("artifacts/evaluation_manifest/")
        assert component["expression"] == before["content"]["proposed_rules"][0]["components"][0]["expression"]
        assert len(reader.prompts) == 2
        cleared_revision, cleared_content = after["revision_id"], after["content"]
        reader = UncertainScopeReader()
        uncertain = client.post(url + "/feedback", json={
            "expected_revision_id": cleared_revision, "feedback_kind": "source_error",
            "feedback_note": "新核对无法确认适用节点，保留当前具体疑问。", "target_rule_code": "IN-01", "review_parent_scope": True,
        })
        assert uncertain.status_code == 200, uncertain.text
        latest = client.get(url).json()
        assert latest["revision_id"] != cleared_revision
        assert latest["content"]["proposed_rules"][0]["components"][0]["expression"] == component["expression"]
        assert latest["content"]["proposed_rules"][0]["components"][0]["source_scope_review_ref"] != component["source_scope_review_ref"]
        assert len(reader.prompts) == 2
        from app.storage.repositories import ProtocolDraftRevisionRepository
        with app.state.session_factory() as session:
            historical = ProtocolDraftRevisionRepository(session).get(cleared_revision)
            assert historical.content.model_dump(mode="json") == cleared_content


@pytest.mark.parametrize("regression", [None, "numeric", "sibling", "binding"])
def test_local_feedback_saves_expired_scope_as_pending_not_approval(build_app, data_paths, monkeypatch, regression):
    from app.evidence.artifacts import ArtifactStore
    from app.services.protocol_scope_review_service import review_official_source_scope
    from app.storage.repositories import ProtocolDraftRevisionRepository
    from tests.v2.protocols.test_official_scope_review import ScopeReader, scope_fixture

    app = build_app(run_runner=False)
    store = ArtifactStore(data_paths)
    source, draft, spans = scope_fixture()
    target = draft.proposed_rules[0].components[0]
    target.expression.predicate.source_term = "年龄评分"
    draft.component_drafts[0].proposed_component = target.model_copy(deep=True)
    draft = review_official_source_scope(source, draft, official_code="IN-01",
        transport=ScopeReader(), store=store)
    old_proof_ref = draft.proposed_rules[0].components[0].source_scope_review_ref
    old_proof = store.read(old_proof_ref)

    def revise(source_input, current_draft, target_rule_code, feedback_note, target_component_id,
               *, joint_source_repair, budget_store, scope_review_store=None):
        if scope_review_store is not None:
            return review_official_source_scope(source_input, current_draft, official_code=target_rule_code,
                transport=ScopeReader(), store=scope_review_store)
        result = current_draft.model_copy(deep=True)
        component = result.proposed_rules[0].components[0]
        component.expression.predicate.source_term = "年龄"
        component.source_scope_review_ref = None
        if regression == "numeric":
            component.expression.predicate.value = 19
        elif regression == "sibling":
            result.proposed_rules[0].components[1].expression.predicate.value = 19
            result.component_drafts[1].proposed_component = result.proposed_rules[0].components[1].model_copy(deep=True)
        result.component_drafts[0].proposed_component = component.model_copy(deep=True)
        if regression == "binding":
            result.component_drafts[0].source_refs = ["foreign-source"]
        return result

    monkeypatch.setattr(ProtocolWorkbenchService, "_revise_feedback_with_model", staticmethod(revise))
    with TestClient(app) as client:
        job_id = _create_protocol_job(client, key=f"scope-expiry-{regression}")
        app.state.protocol_workbench_service.seed_review_session(job_id, source_input=source,
            draft=draft, source_spans=spans, wait_at="await_review")
        url = f"/api/v2/protocol/deconstructions/{job_id}"
        before = client.get(url + "/draft").json()
        response = client.post(url + "/draft/feedback", json={
            "expected_revision_id": before["revision_id"], "feedback_kind": "source_error",
            "feedback_note": "仅纠正当前指标原名，其他含义及兄弟项保持。", "target_rule_code": "IN-01",
            "target_component_id": target.rule_component_id,
        })
        after = client.get(url + "/draft").json()
        if regression is not None:
            assert response.status_code == 409, response.text
            assert after["revision_id"] == before["revision_id"]
            assert after["content"] == before["content"]
        else:
            assert response.status_code == 200, response.text
            assert after["revision_number"] == 2
            components = after["content"]["proposed_rules"][0]["components"]
            assert components[0].get("source_scope_review_ref") is None
            assert components[1] == before["content"]["proposed_rules"][0]["components"][1]
            integrity = client.get(url + "/integrity").json()
            assert not integrity["publishable"] and integrity["blocking_count"] > 0
            pending = app.state.protocol_workbench_service.get_draft_detail(job_id).revision.content
            pending_gate = app.state.protocol_workbench_service.gate.evaluate(source, pending, source_spans=spans)
            codes = {issue.issue_code for check in pending_gate.checks for issue in check.issues}
            assert "SOURCE_SCOPE_REVIEW_INVALID" in codes
            assert "REVIEW_STAGE_SCOPE_UNVERIFIED" in codes
            assert "METRIC_NOT_IN_SOURCE" not in codes
            from app.services.protocol_publication_service import (
                ProtocolPublicationRequest, ProtocolPublicationService, PublicationGateError,
            )
            with pytest.raises(PublicationGateError):
                ProtocolPublicationService(app.state.session_factory).publish(ProtocolPublicationRequest(
                    idempotency_key="expired-scope-must-not-publish", draft_revision_id=after["revision_id"],
                    source_input=source, source_spans=spans, actor="测试医学监查员",
                ))
            checked = client.post(url + "/draft/feedback", json={
                "expected_revision_id": after["revision_id"], "feedback_kind": "source_error",
                "feedback_note": "重新核对当前版本的总标题关系。", "target_rule_code": "IN-01",
                "review_parent_scope": True,
            })
            assert checked.status_code == 200, checked.text
            assert client.get(url + "/integrity").json()["publishable"]
            assert client.get(url + "/draft").json()["revision_number"] == 3
        with app.state.session_factory() as session:
            historical = ProtocolDraftRevisionRepository(session).get(before["revision_id"])
            assert historical.content.model_dump(mode="json") == before["content"]
        assert store.read(old_proof_ref) == old_proof


def test_scope_request_cannot_be_disguised_as_clarification(build_app):
    app = build_app(run_runner=False)
    with TestClient(app) as client:
        job_id = _create_protocol_job(client, key="parent-scope-invalid-feedback")
        _seed_review_job(app, job_id, wait_at="await_review")
        url = f"/api/v2/protocol/deconstructions/{job_id}/draft"
        before = client.get(url).json()
        response = client.post(url + "/feedback", json={
            "expected_revision_id": before["revision_id"], "feedback_kind": "clarification",
            "feedback_note": "只核对标题。", "target_rule_code": "IN-01", "review_parent_scope": True,
        })
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "SCOPE_REVIEW_REQUEST_INVALID"
        assert client.get(url).json()["revision_id"] == before["revision_id"]


def test_save_draft_is_idempotent(client, build_app) -> None:
    app = build_app()
    with TestClient(app) as test_client:
        job_id = _create_protocol_job(test_client, key="save-draft-1")
        _seed_review_job(app, job_id)
        draft = test_client.get(f"/api/v2/protocol/deconstructions/{job_id}/draft").json()
        response = test_client.post(
            f"/api/v2/protocol/deconstructions/{job_id}/draft/save",
            json={"expected_revision_id": draft["revision_id"]},
        )
        assert response.status_code == 200
        assert response.json()["status_label"] == "已保存"


def test_publish_first_project(client, build_app) -> None:
    app = build_app()
    with TestClient(app) as test_client:
        job_id = _create_protocol_job(test_client, key="publish-1")
        _seed_review_job(app, job_id, wait_at="publish")
        draft = test_client.get(f"/api/v2/protocol/deconstructions/{job_id}/draft").json()
        payload = _joint_publish_payload(app, job_id, key="pub-key-1")
        response = test_client.post(
            f"/api/v2/protocol/deconstructions/{job_id}/publish",
            json=payload,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["project_id"]
        assert body["rule_set_revision"] == 1
        assert body["replay"] is False

        replay = test_client.post(
            f"/api/v2/protocol/deconstructions/{job_id}/publish",
            json=payload,
        )
        assert replay.status_code == 200
        assert replay.json()["replay"] is True


def test_identity_not_ready_before_pipeline(client) -> None:
    job_id = _create_protocol_job(client, key="identity-wait-1")
    response = client.get(f"/api/v2/protocol/deconstructions/{job_id}/identity")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "IDENTITY_NOT_READY"
    assert error["recovery_action"]


def test_draft_not_ready_before_review(client) -> None:
    job_id = _create_protocol_job(client, key="draft-wait-1")
    response = client.get(f"/api/v2/protocol/deconstructions/{job_id}/draft")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] in {"DRAFT_NOT_READY", "STATE_CONFLICT", "STEP_STATE_CONFLICT"}
    assert error["title"]
    assert error["recovery_action"]


@pytest.mark.parametrize(
    ("official_date_value", "official_date_precision"),
    [("2026", "year"), ("2026-08", "month"), ("2026-08-17", "day")],
)
def test_upload_pipeline_reaches_identity_and_review_without_seed(
    build_app,
    official_date_value: str,
    official_date_precision: str,
) -> None:
    app = build_app(run_runner=False)
    with TestClient(app) as client:
        job_id = _create_protocol_job(
            client,
            key=f"pipeline-e2e-{official_date_precision}",
            docx_bytes=_pipeline_docx_bytes(),
        )
        _run_until(client, app, job_id, awaiting_user="identity")

        identity_session = client.get(f"/api/v2/jobs/{job_id}").json()
        identity_wait = next(
            step
            for step in identity_session["steps"]
            if step["step_id"] == "await_identity_confirm"
        )
        assert identity_wait["state"] == "waiting_user"
        assert identity_wait["attempt"] == 0
        identity_events = [item["event_type"] for item in identity_session["events"]]
        assert "waiting_user" in identity_events
        assert "step_failed" not in identity_events
        assert "retry_scheduled" not in identity_events

        identity = client.get(f"/api/v2/protocol/deconstructions/{job_id}/identity")
        assert identity.status_code == 200, identity.text
        identity_body = identity.json()
        assert identity_body["snapshot_id"]
        assert identity_body["phase_candidates"]
        assert len(identity_body["phase_candidates"]) == 1
        phase_candidate = identity_body["phase_candidates"][0]
        assert phase_candidate["phase_label"] == "II 期"
        assert "方案原文" in phase_candidate["rationale"]
        assert phase_candidate["source_excerpt"]
        assert identity_body["identity"]["status_label"] == "需要确认"
        assert all(
            item["field_label"] and item["source_label"]
            for item in identity_body["metadata_candidates"]
        )

        confirm = client.post(
            f"/api/v2/protocol/deconstructions/{job_id}/identity/confirm",
            json={
                "protocol_code": "E2E-001",
                "project_name": "E2E 测试研究",
                "official_version": "V1.0",
                "official_date_value": official_date_value,
                "official_date_precision": official_date_precision,
                "study_phase": StudyPhase.PHASE_II.value,
                "actor": "测试用户",
            },
        )
        assert confirm.status_code == 200, confirm.text

        confirmed_identity = client.get(
            f"/api/v2/protocol/deconstructions/{job_id}/identity"
        )
        assert confirmed_identity.status_code == 200, confirmed_identity.text
        assert confirmed_identity.json()["identity"]["official_date_value"] == official_date_value
        assert (
            confirmed_identity.json()["identity"]["official_date_precision"]
            == official_date_precision
        )

        _run_until(client, app, job_id, awaiting_user="review", limit=60)

        session = client.get(f"/api/v2/protocol/deconstructions/{job_id}").json()
        assert session["awaiting_user"] == "review"
        assert session["draft_revision_number"] == 1
        review_job = client.get(f"/api/v2/jobs/{job_id}").json()
        review_wait = next(
            step for step in review_job["steps"] if step["step_id"] == "await_review"
        )
        assert review_wait["state"] == "waiting_user"
        assert review_wait["attempt"] == 0

        draft = client.get(f"/api/v2/protocol/deconstructions/{job_id}/draft")
        assert draft.status_code == 200, draft.text
        draft_body = draft.json()
        assert draft_body["revision_number"] == 1
        assert draft_body["rule_count"] >= 1
        assert "content" in draft_body

        sources = client.get(f"/api/v2/protocol/deconstructions/{job_id}/sources")
        assert sources.status_code == 200, sources.text
        assert sources.json()["selected_phase_label"] == "II 期"

        def unexpected_model_call(_package):
            raise AssertionError("恢复已保存首稿时不得再次调用语义模型")

        recovered = _handle_generate(
            StepContext(
                job_id=job_id,
                job_type=PROTOCOL_DECONSTRUCTION_JOB_TYPE,
                job_payload={
                    "actor": "测试用户",
                    "session_kind": "first_deconstruction",
                },
                step_id="generate_draft",
                name="生成方案解构草稿",
                attempt=2,
                last_checkpoint_id=None,
                last_checkpoint=None,
            ),
            ProtocolDeconstructionExecutorConfig(
                data_paths=app.state.data_paths,
                session_factory=app.state.session_factory,
                page_texts_builder=page_texts_from_blocks,
                draft_response_builder=unexpected_model_call,
            ),
        )
        assert recovered["draft_revision_id"] == draft_body["revision_id"]


def test_session_projects_persisted_publish_wait(build_app) -> None:
    app = build_app()
    with TestClient(app) as client:
        job_id = _create_protocol_job(client, key="publish-wait-projection")
        _seed_review_job(app, job_id, wait_at="publish")

        session = client.get(f"/api/v2/protocol/deconstructions/{job_id}")
        assert session.status_code == 200, session.text
        body = session.json()
        assert body["state"] == "waiting_user"
        assert body["awaiting_user"] == "publish"
        assert body["awaiting_user_label"] == "等待发布确认"
        assert "发布正式项目" in body["next_action"]


def test_identity_date_candidate_projection_is_form_ready() -> None:
    candidate = _metadata_candidate_dto(
        {
            "candidate_id": "date-candidate",
            "field_category": "protocol_date",
            "candidate_value": "2026年8月17日",
            "normalized_value": "2026-08-17",
            "source_kind": "first_page",
            "excerpt": "版本日期：2026年8月17日",
        }
    )
    assert candidate.value == "2026-08-17"
    assert candidate.source_excerpt == "版本日期：2026年8月17日"


def test_phase_candidate_evidence_prefers_current_trial_structure() -> None:
    candidates = [
        {
            "candidate_id": "historical",
            "phase": "phase_ii",
            "excerpt": "既往II期PD结果显示药效明确",
        },
        {
            "candidate_id": "purpose",
            "phase": "phase_ii",
            "excerpt": "探索试验阶段（II期）研究目的",
        },
        {
            "candidate_id": "design",
            "phase": "phase_ii",
            "excerpt": "II期研究设计与给药方案",
        },
        {
            "candidate_id": "eligibility",
            "phase": "phase_ii",
            "excerpt": "II期入选标准",
        },
        {
            "candidate_id": "extra",
            "phase": "phase_ii",
            "excerpt": "II期其他描述",
        },
    ]

    result = _phase_candidate_dtos(candidates)

    assert len(result) == 1
    assert "研究目的" in result[0].source_excerpt
    assert "研究设计" in result[0].source_excerpt
    assert "入选标准" in result[0].source_excerpt
    assert "PD结果" not in result[0].source_excerpt
    assert "5 处期别标记" in result[0].rationale


def test_phase_candidate_evidence_joins_excerpts_without_duplicate_punctuation() -> None:
    candidates = [
        {
            "candidate_id": "phase-iii-a",
            "phase": "phase_iii",
            "excerpt": "优化Ⅲ期入选/排除标准；",
        },
        {
            "candidate_id": "phase-iii-b",
            "phase": "phase_iii",
            "excerpt": "Ⅲ期研究设计",
        },
    ]

    result = _phase_candidate_dtos(candidates)

    assert result[0].source_excerpt == "Ⅲ期研究设计；优化Ⅲ期入选/排除标准"
    assert "；；" not in result[0].source_excerpt


def test_phase_candidate_evidence_removes_trailing_colon_before_joining() -> None:
    candidates = [
        {
            "candidate_id": "phase-ii-a",
            "phase": "phase_ii",
            "excerpt": "II期给药方案:",
        },
        {
            "candidate_id": "phase-ii-b",
            "phase": "phase_ii",
            "excerpt": "探索试验阶段（Ⅱ期）",
        },
    ]

    result = _phase_candidate_dtos(candidates)

    assert result[0].source_excerpt == "II期给药方案；探索试验阶段（Ⅱ期）"


def test_official_projects_list_and_version_read_after_publish(client, build_app) -> None:
    app = build_app()
    with TestClient(app) as test_client:
        first = _create_protocol_job(test_client, key="projects-read-publish")
        _seed_review_job(app, first, wait_at="publish")
        draft = test_client.get(f"/api/v2/protocol/deconstructions/{first}/draft").json()
        published = test_client.post(
            f"/api/v2/protocol/deconstructions/{first}/publish",
            json=_joint_publish_payload(app, first, key="projects-read-pub"),
        )
        assert published.status_code == 200, published.text
        project_id = published.json()["project_id"]

        listed = test_client.get("/api/v2/protocol/projects")
        assert listed.status_code == 200, listed.text
        body = listed.json()
        assert len(body["projects"]) == 1
        project = body["projects"][0]
        assert project["project_id"] == project_id
        assert project["protocol_code"] == "TEST-001"
        assert project["official_version"] == "V1.0"
        assert project["rule_set_revision"] == 1
        assert project["study_phase_label"] == "II 期"

        detail = test_client.get(f"/api/v2/protocol/projects/{project_id}")
        assert detail.status_code == 200, detail.text
        detail_body = detail.json()
        assert detail_body["publication_count"] == 1
        assert len(detail_body["versions"]) == 1
        assert detail_body["versions"][0]["rule_count"] == 2


def test_redeconstruction_start_with_project_id_persists_target(client, build_app) -> None:
    app = build_app()
    with TestClient(app) as test_client:
        first = _create_protocol_job(test_client, key="redo-persist-first")
        _seed_review_job(app, first, wait_at="publish")
        draft = test_client.get(f"/api/v2/protocol/deconstructions/{first}/draft").json()
        published = test_client.post(
            f"/api/v2/protocol/deconstructions/{first}/publish",
            json=_joint_publish_payload(app, first, key="redo-persist-pub"),
        )
        project_id = published.json()["project_id"]

        files = {
            "file": (
                "redo-protocol.docx",
                io.BytesIO(_minimal_docx_bytes()),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        data = {
            "idempotency_key": "redo-start",
            "actor": "医学监查员",
            "project_id": project_id,
        }
        started = test_client.post(
            "/api/v2/protocol/deconstructions", files=files, data=data
        )
        assert started.status_code == 201, started.text
        job_id = started.json()["job_id"]

        session = test_client.get(f"/api/v2/protocol/deconstructions/{job_id}")
        assert session.status_code == 200, session.text
        body = session.json()
        assert body["session_kind"] == "re_deconstruction"
        assert body["target_project_id"] == project_id
        assert body["target_protocol_code"] == "TEST-001"
        assert body["target_study_phase_label"] == "II 期"


def test_feedback_redeconstruction_api_starts_without_upload(build_app) -> None:
    app = build_app()
    with TestClient(app) as test_client:
        first = _create_protocol_job(test_client, key="feedback-formal-first")
        _seed_review_job(app, first, wait_at="publish")
        published = test_client.post(
            f"/api/v2/protocol/deconstructions/{first}/publish",
            json=_joint_publish_payload(app, first, key="feedback-formal-pub"),
        )
        assert published.status_code == 200, published.text
        project_id = published.json()["project_id"]

        started = test_client.post(
            "/api/v2/protocol/deconstructions/from-formal",
            json={
                "project_id": project_id,
                "idempotency_key": "feedback-formal-start",
                "actor": "医学监查员",
            },
        )
        assert started.status_code == 201, started.text
        job_id = started.json()["job_id"]
        session = test_client.get(f"/api/v2/protocol/deconstructions/{job_id}")
        assert session.status_code == 200, session.text
        assert session.json()["awaiting_user"] == "review"
        comparison = test_client.get(
            f"/api/v2/protocol/deconstructions/{job_id}/draft/comparison"
        )
        assert comparison.status_code == 200, comparison.text
        assert comparison.json()["diff"]["modified_rule_codes"] == []
        republished = test_client.post(
            f"/api/v2/protocol/deconstructions/{job_id}/publish",
            json=_joint_publish_payload(app, job_id, key="feedback-formal-republish"),
        )
        assert republished.status_code == 200, republished.text
        assert republished.json()["rule_set_revision"] == 2


def test_active_draft_interpretation_sources_api_is_idempotent(build_app) -> None:
    app = build_app()
    with TestClient(app) as test_client:
        job_id = _create_protocol_job(
            test_client,
            key="active-source-api",
        )
        _seed_review_job(app, job_id, wait_at="await_review")
        draft = test_client.get(
            f"/api/v2/protocol/deconstructions/{job_id}/draft"
        ).json()
        source_view = test_client.get(
            f"/api/v2/protocol/deconstructions/{job_id}/sources"
        ).json()
        source = {
            "interpretation_source_id": "source-active-api",
            "protocol_version_id": source_view["protocol_version_id"],
            "source_type": InterpretationSourceType.MEDICAL_INTERPRETATION.value,
            "file_sha256": "c" * 64,
            "source_ref": "medical-note:api",
            "excerpt": "既往时间窗未写明起算日期。",
            "explanation": "按当前审核节点日期逐节点独立核对。",
            "applies_to_rule_refs": ["IN-01"],
            "clarifies_ambiguity": True,
            "anchor_resolutions": [
                {
                    "resolution_id": "resolution-active-api",
                    "affected_rule_refs": ["IN-01"],
                    "ambiguous_source_refs": ["span-in"],
                    "target_review_stages": [
                        ReviewStage.SCREENING.value,
                        ReviewStage.BASELINE.value,
                    ],
                    "resolution_mode": AnchorResolutionMode.CURRENT_REVIEW_NODE_DATE.value,
                }
            ],
        }
        body = {
            "expected_revision_id": draft["revision_id"],
            "idempotency_key": "active-source-api-registration",
            "interpretation_sources": [source],
            "actor": "医学监查员",
        }
        registered = test_client.post(
            f"/api/v2/protocol/deconstructions/{job_id}/interpretation-sources",
            json=body,
        )
        assert registered.status_code == 200, registered.text
        registered_body = registered.json()
        assert registered_body["draft_revision_id"] == draft["revision_id"]
        assert registered_body["interpretation_sources"][0][
            "interpretation_source_id"
        ] == "source-active-api"
        assert "source-active-api" not in registered_body["source_materials"]

        replay_body = {**body}
        replay = test_client.post(
            f"/api/v2/protocol/deconstructions/{job_id}/interpretation-sources",
            json=replay_body,
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["interpretation_sources"] == (
            registered_body["interpretation_sources"]
        )


def test_redeconstruction_start_unknown_project_returns_chinese_envelope(
    client,
) -> None:
    files = {
        "file": (
            "redo-protocol.docx",
            io.BytesIO(_minimal_docx_bytes()),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    data = {
        "idempotency_key": "redo-unknown",
        "actor": "医学监查员",
        "project_id": "missing-project",
    }
    response = client.post("/api/v2/protocol/deconstructions", files=files, data=data)
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "PROJECT_NOT_FOUND"
    assert error["title"] == "找不到正式项目"
    assert error["recovery_action"]


def test_redeconstruction_confirm_identity_lineage_mismatch_rejected(
    build_app,
) -> None:
    """重新解构身份确认阶段即拦截与目标项目不同谱系/期别的确认。"""
    app = build_app()
    with TestClient(app) as test_client:
        first = _create_protocol_job(test_client, key="redo-lineage-first")
        _seed_review_job(app, first, wait_at="publish")
        draft = test_client.get(f"/api/v2/protocol/deconstructions/{first}/draft").json()
        published = test_client.post(
            f"/api/v2/protocol/deconstructions/{first}/publish",
            json=_joint_publish_payload(app, first, key="redo-lineage-pub"),
        )
        project_id = published.json()["project_id"]

        files = {
            "file": (
                "redo-protocol.docx",
                io.BytesIO(_minimal_docx_bytes()),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        data = {
            "idempotency_key": "redo-lineage-start",
            "actor": "医学监查员",
            "project_id": project_id,
        }
        started = test_client.post(
            "/api/v2/protocol/deconstructions", files=files, data=data
        )
        assert started.status_code == 201, started.text
        job_id = started.json()["job_id"]

        # 任务未走到身份确认检查点：确认请求应被拒绝为状态冲突（非 200）。
        confirm = test_client.post(
            f"/api/v2/protocol/deconstructions/{job_id}/identity/confirm",
            json={
                "protocol_code": "OTHER-001",
                "project_name": "测试研究",
                "official_version": "V2.0",
                "official_date_value": "2026-08-17",
                "official_date_precision": "day",
                "study_phase": StudyPhase.PHASE_II.value,
                "actor": "医学监查员",
            },
        )
        assert confirm.status_code in (409, 422), confirm.text

def test_draft_comparison_endpoint_returns_baseline_candidate_and_diff(
    build_app,
) -> None:
    """重新解构比较投影：一次返回当前正式草稿、新草稿与八类差异。"""
    from app.services.protocol_draft_service import ProtocolDraftService

    app = build_app()
    with TestClient(app) as test_client:
        first = _create_protocol_job(test_client, key="compare-api-first")
        _seed_review_job(app, first, wait_at="publish")
        draft = test_client.get(f"/api/v2/protocol/deconstructions/{first}/draft").json()
        published = test_client.post(
            f"/api/v2/protocol/deconstructions/{first}/publish",
            json=_joint_publish_payload(app, first, key="compare-api-pub"),
        )
        assert published.status_code == 200, published.text
        project_id = published.json()["project_id"]

        files = {
            "file": (
                "redo-protocol.docx",
                io.BytesIO(_minimal_docx_bytes()),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        data = {
            "idempotency_key": "compare-api-start",
            "actor": "医学监查员",
            "project_id": project_id,
        }
        started = test_client.post(
            "/api/v2/protocol/deconstructions", files=files, data=data
        )
        assert started.status_code == 201, started.text
        job_id = started.json()["job_id"]

        # 重新解构子工作台种子：新版本草案
        source_input, draft, spans = confirmed_fixture()
        revised = draft.model_copy(
            update={
                "draft_id": "draft-compare-api",
                "protocol_version_id": "protocol-version-2",
                "protocol_metadata": draft.protocol_metadata.model_copy(
                    update={"version_candidate": "V2.0"}
                ),
            }
        )
        revised_input = source_input.model_copy(
            update={
                "protocol_version_id": "protocol-version-2",
                "identity_decision": source_input.identity_decision.model_copy(
                    update={"official_version": "V2.0"}
                ),
            }
        )
        service = app.state.protocol_workbench_service
        service.seed_review_session(
            job_id,
            source_input=revised_input,
            draft=revised,
            source_spans={key: span for key, span in spans.items()},
            wait_at="publish",
        )

        comparison = test_client.get(
            f"/api/v2/protocol/deconstructions/{job_id}/draft/comparison"
        )
        assert comparison.status_code == 200, comparison.text
        body = comparison.json()
        assert body["baseline"]["is_formal_baseline"] is True
        assert body["candidate"]["is_formal_baseline"] is False
        assert body["baseline"]["protocol_version_id"] == "protocol-version-1"
        assert body["candidate"]["protocol_version_id"] == "protocol-version-2"
        assert body["baseline"]["rule_count"] == 2
        assert body["candidate"]["rule_count"] == 2
        assert body["source_bound"] is True
        assert "rule_diffs" in body["diff"]


def test_draft_comparison_rejected_for_first_deconstruction(client) -> None:
    """首次解构不是重新解构，不提供正式基线比较。"""
    job_id = _create_protocol_job(client, key="compare-first-only")
    response = client.get(f"/api/v2/protocol/deconstructions/{job_id}/draft/comparison")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "NOT_RE_DECONSTRUCTION_JOB"
    assert error["recovery_action"]


@pytest.mark.parametrize("problem", [None, "uncovered", "wrong_source", "true_uncertainty", "executable", "parent"])
def test_redundant_source_retirement_keeps_consumers_and_requires_current_review(
    build_app, data_paths, monkeypatch, problem,
):
    from app.domain.contracts.rules import RestrictedRuleComponent
    from app.evidence.artifacts import ArtifactStore
    from app.services.protocol_scope_review_service import review_official_source_scope
    from app.storage.repositories import ProtocolDraftRevisionRepository
    from tests.v2.protocols.test_official_scope_review import ScopeReader, scope_fixture

    app = build_app(run_runner=False)
    store = ArtifactStore(data_paths)
    source, draft, spans = scope_fixture()
    rule = draft.proposed_rules[0]
    duplicate = RestrictedRuleComponent(
        rule_component_id="duplicate-source-holder", display_code="IN-01待核",
        title="重复来源待核", source_span_ids=["span-in"],
        source_excerpts=[quote for binding in draft.component_drafts
                         if binding.parent_official_code == "IN-01"
                         for quote in binding.source_excerpts],
        limitation_kind="consumer_unavailable", unresolved_dimensions=["原系统未能装配"],
    )
    if problem == "uncovered":
        duplicate.source_excerpts.append("筛选时必须记录体重")
    elif problem == "wrong_source":
        duplicate.source_span_ids = ["span-ex"]
    elif problem == "true_uncertainty":
        duplicate.limitation_kind = "interpretation_unresolved"
    rule.restricted_components.append(duplicate)
    draft = review_official_source_scope(source, draft, official_code="IN-01",
        transport=ScopeReader(), store=store)
    old_ref = draft.proposed_rules[0].components[0].source_scope_review_ref
    old_proof = store.read(old_ref)

    def forbid_model(*args, **kwargs):
        pytest.fail("source ownership check must not call a model")
    monkeypatch.setattr(ProtocolWorkbenchService, "_revise_feedback_with_model", staticmethod(forbid_model))
    with TestClient(app) as client:
        job = _create_protocol_job(client, key=f"retire-source-{problem}")
        service = app.state.protocol_workbench_service
        service.seed_review_session(job, source_input=source, draft=draft, source_spans=spans, wait_at="await_review")
        url = f"/api/v2/protocol/deconstructions/{job}"
        before = client.get(url + "/draft").json()
        request = {"expected_revision_id": before["revision_id"], "feedback_kind": "source_error",
                   "feedback_note": "核对来源已由原有两个独立要求完整承担；不改变条件。",
                   "target_rule_code": "IN-01", "target_component_id": duplicate.rule_component_id,
                   "retire_redundant_source": True}
        if problem == "executable":
            request["target_component_id"] = rule.components[0].rule_component_id
        elif problem == "parent":
            request["target_component_id"] = None
            request["review_parent_scope"] = True
        response = client.post(url + "/draft/feedback", json=request)
        after = client.get(url + "/draft").json()
        if problem is not None:
            assert response.status_code == 409, response.text
            assert after == before
        else:
            assert response.status_code == 200, response.text
            assert after["revision_number"] == 2
            old_rule = before["content"]["proposed_rules"][0]
            new_rule = after["content"]["proposed_rules"][0]
            assert not new_rule.get("restricted_components", [])
            assert new_rule["components"] == old_rule["components"]
            for field in before["content"]:
                if field not in {"proposed_rules", "draft_revision", "previous_draft_id"}:
                    assert after["content"][field] == before["content"][field]
            integrity = client.get(url + "/integrity").json()
            assert not integrity["publishable"]
            from app.services.protocol_publication_service import (
                ProtocolPublicationService, ProtocolPublicationRequest, PublicationGateError,
            )
            with pytest.raises(PublicationGateError):
                ProtocolPublicationService(app.state.session_factory).publish(ProtocolPublicationRequest(
                    idempotency_key="retirement-is-not-approval", draft_revision_id=after["revision_id"],
                    source_input=source, source_spans=spans, actor="测试用户"))
            stale = client.post(url + "/draft/feedback", json=request)
            assert stale.status_code == 409
            assert client.get(url + "/draft").json() == after
            def only_review(source_input, current, target_rule_code, feedback_note, target_component_id,
                            *, joint_source_repair, budget_store, scope_review_store=None):
                assert scope_review_store is not None
                return review_official_source_scope(source_input, current, official_code=target_rule_code,
                    transport=ScopeReader(), store=scope_review_store)
            monkeypatch.setattr(ProtocolWorkbenchService, "_revise_feedback_with_model", staticmethod(only_review))
            reviewed = client.post(url + "/draft/feedback", json={
                "expected_revision_id": after["revision_id"], "feedback_kind": "source_error",
                "feedback_note": "只重新核对当前要求的来源关系。", "target_rule_code": "IN-01",
                "review_parent_scope": True})
            assert reviewed.status_code == 200, reviewed.text
            assert client.get(url + "/integrity").json()["publishable"]
        with app.state.session_factory() as session:
            historical = ProtocolDraftRevisionRepository(session).get(before["revision_id"])
            assert historical.content.model_dump(mode="json") == before["content"]
        assert store.read(old_ref) == old_proof


@pytest.mark.parametrize("changed", ["sibling_value", "binding", "other_restricted", "last_consumer"])
def test_redundant_source_retirement_never_authorizes_sibling_edits(changed):
    from app.domain.contracts.rules import RestrictedRuleComponent
    from tests.v2.protocols.test_official_scope_review import scope_fixture
    _, before, _ = scope_fixture()
    rule = before.proposed_rules[0]
    item = RestrictedRuleComponent(rule_component_id="duplicate-holder", display_code="IN-01待核",
        title="重复来源", source_span_ids=["span-in"],
        source_excerpts=[before.component_drafts[0].source_excerpts[0]],
        limitation_kind="consumer_unavailable", unresolved_dimensions=["未装配"])
    rule.restricted_components.append(item)
    after = before.model_copy(deep=True)
    after.proposed_rules[0].restricted_components = []
    assert ProtocolWorkbenchService._redundant_restricted_removal_proven(before, after, "IN-01", item.rule_component_id)
    if changed == "sibling_value":
        after.proposed_rules[0].components[0].expression.predicate.value = 99
    elif changed == "binding":
        after.component_drafts[0].source_excerpts = ["其他来源"]
    elif changed == "other_restricted":
        rule.restricted_components.append(item.model_copy(update={"rule_component_id": "another-holder"}))
    else:
        after.proposed_rules[0].components = []
    assert not ProtocolWorkbenchService._redundant_restricted_removal_proven(before, after, "IN-01", item.rule_component_id)


def test_ordinary_feedback_cannot_silently_retire_a_restricted_source():
    from app.domain.contracts.rules import RestrictedRuleComponent
    from tests.v2.protocols.test_official_scope_review import scope_fixture
    _, before, _ = scope_fixture()
    item = RestrictedRuleComponent(rule_component_id="duplicate-holder", display_code="IN-01待核",
        title="重复来源", source_span_ids=["span-in"], source_excerpts=before.component_drafts[0].source_excerpts,
        limitation_kind="consumer_unavailable", unresolved_dimensions=["未装配"])
    before.proposed_rules[0].restricted_components.append(item)
    after = before.model_copy(deep=True)
    after.proposed_rules[0].restricted_components = []
    with pytest.raises(ValueError, match="不得删除"):
        ProtocolWorkbenchService._validate_source_error_scope(before, after,
            target_rule_code="IN-01", target_component_id=item.rule_component_id)
    ProtocolWorkbenchService._validate_source_error_scope(before, after,
        target_rule_code="IN-01", target_component_id=item.rule_component_id, allow_redundant_retirement=True)


@pytest.mark.parametrize("clause,atomic_quote", [
    ("治疗期间，使用治疗甲", "使用治疗甲"),
    ("未使用治疗甲", "未使用治疗甲"),
    ("使用治疗甲（已稳定治疗的受试者除外）", "使用治疗甲"),
    ("使用治疗甲且完成检查乙", "使用治疗甲"),
])
def test_retirement_rejects_quoted_but_unrepresented_qualifiers(clause, atomic_quote):
    from app.domain.contracts.enums import Comparator
    from app.domain.contracts.rules import RestrictedRuleComponent
    from tests.v2.protocols.test_official_scope_review import scope_fixture
    _, before, _ = scope_fixture()
    rule = before.proposed_rules[0]
    component = rule.components[0]
    predicate = component.expression.predicate
    predicate.attribute = predicate.source_term = "使用治疗甲"
    predicate.comparator = Comparator.EXISTS
    predicate.value = predicate.unit = None
    predicate.source_clause = atomic_quote
    component.exception_expression = None
    before.component_drafts[0].source_excerpts = [clause]
    before.component_drafts[0].proposed_component = component.model_copy(deep=True)
    item = RestrictedRuleComponent(rule_component_id="duplicate-holder", display_code="IN-01待核",
        title="重复来源", source_span_ids=["span-in"], source_excerpts=[clause],
        limitation_kind="consumer_unavailable", unresolved_dimensions=["未装配"])
    rule.restricted_components.append(item)
    after = before.model_copy(deep=True)
    after.proposed_rules[0].restricted_components = []
    assert not ProtocolWorkbenchService._redundant_restricted_removal_proven(before, after, "IN-01", item.rule_component_id)


def test_retirement_cannot_borrow_exception_marker_from_another_source():
    from app.domain.contracts.enums import Comparator
    from app.domain.contracts.rules import RestrictedRuleComponent
    from tests.v2.protocols.test_official_scope_review import scope_fixture
    _, before, _ = scope_fixture()
    rule = before.proposed_rules[0]
    component = rule.components[0]
    predicate = component.expression.predicate
    predicate.attribute = predicate.source_term = predicate.source_clause = "使用治疗甲"
    predicate.comparator = Comparator.EXISTS
    predicate.value = predicate.unit = None
    component.exception_expression = component.expression.model_copy(deep=True)
    exception = component.exception_expression.predicate
    exception.predicate_id += "-exception"
    exception.attribute = exception.source_term = exception.source_clause = "完成检查乙"
    before.component_drafts[0].source_excerpts = ["使用治疗甲", "完成检查乙除外"]
    before.component_drafts[0].proposed_component = component.model_copy(deep=True)
    item = RestrictedRuleComponent(rule_component_id="duplicate-holder", display_code="IN-01待核",
        title="重复来源", source_span_ids=["span-in"], source_excerpts=["使用治疗甲除外"],
        limitation_kind="consumer_unavailable", unresolved_dimensions=["未装配"])
    rule.restricted_components.append(item)
    after = before.model_copy(deep=True)
    after.proposed_rules[0].restricted_components = []
    assert not ProtocolWorkbenchService._redundant_restricted_removal_proven(
        before, after, "IN-01", item.rule_component_id)
