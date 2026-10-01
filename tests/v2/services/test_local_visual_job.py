"""Region read production, persistence, recovery and consumer boundary."""
import io
import json
from dataclasses import replace

import pytest
from PIL import Image
from pydantic import ValidationError

from app.evidence.artifacts import ArtifactStore
from app.llm.independent_vlm import IndependentVlmChatResult
from app.services.evidence_app_errors import AppScopeMismatchError
from app.services.local_visual_verification import (
    LOCAL_VISUAL_JOB_TYPE, LOCAL_VISUAL_STEP, LocalVisualRegionRequest,
    LocalVisualVerificationService, create_local_visual_executor,
)
from app.services.job_service import JobService
from app.services.selective_vision_postprocess_job_service import SelectiveVisionPostprocessJobService
from app.storage.selective_vision_observation_repository import SelectiveVisionObservationRepository
from app.workflow.errors import StepFailure
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner, StepContext
from tests.v2.services.test_selective_vision_postfreeze_orchestration import _seed_frozen_revision


def _seed(factory, paths):
    image = io.BytesIO()
    Image.new("RGB", (80, 60), "white").save(image, "PNG")
    return _seed_frozen_revision(factory, paths, revision_id="local-job-base", image_bytes=image.getvalue())


def test_local_job_real_runner_preserves_page_coverage_and_supports_replay(
    session_factory, data_paths, monkeypatch,
):
    seeded = _seed(session_factory, data_paths)
    store = ArtifactStore(data_paths)
    service = LocalVisualVerificationService(session_factory, store)
    region = LocalVisualRegionRequest(x0=3, y0=4, x1=30, y1=40, clockwise_degrees=90)
    job = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"], region)
    assert service.enqueue(seeded["revision_id"], seeded["page_artifact_id"], region)["job_id"] == job["job_id"]
    assert service.latest(seeded["revision_id"], seeded["page_artifact_id"])["state"] == "queued"
    calls = []

    async def chat(prompt, pages, **kwargs):
        calls.append(pages)
        return IndependentVlmChatResult(text=f"source_ref={pages[0].source_ref}\n批注可见，所指对象不明。",
                                       model="fixture-model", finish_reason="stop", usage={})

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", chat)
    executor = create_local_visual_executor(session_factory, store)
    assert JobRunner(session_factory, {LOCAL_VISUAL_JOB_TYPE: executor}).run_once()
    result = service.latest(seeded["revision_id"], seeded["page_artifact_id"])
    assert result["state"] == "completed" and result["observation_text"] == "批注可见，所指对象不明。"
    assert result["candidate_only"] and result["coverage_scope"] == "region_only"
    with session_factory() as session:
        persisted = JobStore(session).get_job(job["job_id"])
        payload = json.loads(persisted.payload_json)
        checkpoint = JobStore(session).get_last_checkpoint(job["job_id"], LOCAL_VISUAL_STEP)[1]
        assert not SelectiveVisionObservationRepository(session).list_by_page_artifact(seeded["page_artifact_id"])
    assert not SelectiveVisionPostprocessJobService(session_factory).get_revision_task(seeded["revision_id"]).found
    context = StepContext(job["job_id"], LOCAL_VISUAL_JOB_TYPE, payload, LOCAL_VISUAL_STEP, "核实原件局部", 1, "checkpoint", checkpoint)
    assert executor(context) == checkpoint
    assert len(calls) == 1
    changed = {**payload, "region": {**payload["region"], "x1": 31}}
    with pytest.raises(StepFailure) as caught:
        executor(replace(context, job_payload=changed))
    assert caught.value.error_code == "LOCAL_VISUAL_RECEIPT_INVALID"
    assert len(calls) == 1


def test_failed_local_read_stays_failed_and_only_explicit_retry_calls_model(
    session_factory, data_paths, monkeypatch,
):
    seeded = _seed(session_factory, data_paths)
    store = ArtifactStore(data_paths)
    service = LocalVisualVerificationService(session_factory, store)
    job = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"], LocalVisualRegionRequest(x0=3, y0=4, x1=30, y1=40))
    calls = []

    async def chat(prompt, pages, **kwargs):
        calls.append(1)
        return IndependentVlmChatResult(text=f"source_ref={pages[0].source_ref}\n所指对象不明。", model="fixture-model",
                                       finish_reason="length" if len(calls) == 1 else "stop", usage={})

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", chat)
    runner = JobRunner(session_factory, {LOCAL_VISUAL_JOB_TYPE: create_local_visual_executor(session_factory, store)})
    assert runner.run_once()
    failed = service.latest(seeded["revision_id"], seeded["page_artifact_id"])
    assert failed["state"] == "failed_final" and failed["observation_text"] is None
    with session_factory() as session:
        checkpoint = JobStore(session).get_last_checkpoint(job["job_id"], LOCAL_VISUAL_STEP)[1]
        assert json.loads(store.read(checkpoint["receipt_ref"]))["status"] == "failed"
    assert not runner.run_once()
    JobService(session_factory).retry(job["job_id"])
    assert runner.run_once()
    assert service.latest(seeded["revision_id"], seeded["page_artifact_id"])["state"] == "completed"
    assert len(calls) == 2


def test_region_scope_pixel_bounds_and_configuration_identity(session_factory, data_paths, monkeypatch):
    seeded = _seed(session_factory, data_paths)
    service = LocalVisualVerificationService(session_factory, ArtifactStore(data_paths))
    box = LocalVisualRegionRequest(x0=1, y0=1, x1=60, y1=80, clockwise_degrees=90)
    with pytest.raises(AppScopeMismatchError):
        service.enqueue(seeded["revision_id"], "other-page", box)
    with pytest.raises(AppScopeMismatchError):
        service.enqueue(seeded["revision_id"], seeded["page_artifact_id"], box.model_copy(update={"x1": 61}))
    first = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"], box)
    monkeypatch.setattr("app.services.local_visual_verification.local_visual_prompt_identity", lambda *args: "new-prompt")
    second = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"], box)
    assert first["job_id"] != second["job_id"]
    JobService(session_factory).cancel(second["job_id"])
    assert service.latest(seeded["revision_id"], seeded["page_artifact_id"])["state"] == "cancelled"
    successor = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"], box)
    assert successor["job_id"] != second["job_id"] and successor["state"] == "queued"
    assert service.enqueue(seeded["revision_id"], seeded["page_artifact_id"], box)["job_id"] == successor["job_id"]
    with session_factory() as session:
        old = JobStore(session).get_job(second["job_id"])
        new = JobStore(session).get_job(successor["job_id"])
        assert old.state == "cancelled"
        assert json.loads(new.payload_json)["previous_job_id"] == second["job_id"]
    with pytest.raises(ValidationError):
        LocalVisualRegionRequest(x0=True, y0=1, x1=5, y1=5)
    with pytest.raises(ValidationError):
        LocalVisualRegionRequest(x0=1, y0=1, x1=1, y1=5)


def test_completed_without_saved_read_is_visible_failure_and_new_explicit_read_preserves_history(
    session_factory, data_paths,
):
    seeded = _seed(session_factory, data_paths)
    service = LocalVisualVerificationService(session_factory, ArtifactStore(data_paths))
    box = LocalVisualRegionRequest(x0=1, y0=1, x1=30, y1=40)
    original = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"], box)
    # Simulate the durable store anomaly, not a clinical or model outcome.
    with session_factory() as session, session.begin():
        JobStore(session).get_job(original["job_id"]).state = "completed"
    with pytest.raises(AppScopeMismatchError, match="缺少保存记录"):
        service.latest(seeded["revision_id"], seeded["page_artifact_id"], job_id=original["job_id"])
    successor = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"], box)
    assert successor["job_id"] != original["job_id"] and successor["state"] == "queued"
    with session_factory() as session:
        store = JobStore(session)
        assert store.get_job(original["job_id"]).state == "completed"
        payload = json.loads(store.get_job(successor["job_id"]).payload_json)
        assert payload["previous_job_id"] == original["job_id"]
        assert payload["recovery_reason"] == "completed_read_record_missing"
    assert service.enqueue(seeded["revision_id"], seeded["page_artifact_id"], box)["job_id"] == successor["job_id"]
