"""Actual Job/receipt/consumer seam, without granting fact adoption."""
import json
from types import SimpleNamespace

import pytest

from app.evidence.ocr_adapter import InferenceResult
from app.services.evidence_app_errors import AppScopeMismatchError
from app.services.job_service import JobService
from app.services.local_visual_comparison_job import (
    COMPARE_STEP, FIELD_STEP, PARENT_STEP, LocalFieldComparisonRequest,
    LocalVisualComparisonService, create_local_comparison_executor,
)
from app.services.local_visual_verification import LOCAL_VISUAL_JOB_TYPE, LocalVisualVerificationService, create_local_visual_executor
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner
from tests.v2.services.test_local_region_comparison import frozen_trial  # noqa: F401


class Gate:
    def __init__(self, model):
        self.model = model
        self.calls = []

    def config(self):
        return {"models": {"ocr": self.model}}

    def run_under_lease(self, inference, *, request_payload, image_bytes):
        self.calls.append(request_payload)
        return inference(request_payload, image_bytes), {"model": self.model}


@pytest.fixture
def comparison(session_factory, frozen_trial):
    artifacts, trial, visual, request, _ = frozen_trial
    revision = visual.get("requested_processing_revision_id", visual["base_processing_revision_id"])
    page = visual["page_artifact_id"]
    source_job = trial["visual_job"]["job_id"]
    service = LocalVisualComparisonService(session_factory, artifacts)
    body = LocalFieldComparisonRequest(visual_job_id=source_job, item_index=0)
    created = service.enqueue(revision, page, body)
    return SimpleNamespace(artifacts=artifacts, trial=trial, visual=visual, request=request,
                           revision=revision, page=page, body=body, service=service, job=created)


def _runner(factory, case, *, field_text=None, fail_field=False, stop_after_parent=False):
    gate = Gate(case.request["model_id"])
    calls = []

    def infer(request, image):
        calls.append(request)
        if fail_field and len(calls) == 2:
            raise ConnectionError("fixture transport failure")
        text = case.trial["ocr"]["text"] if len(calls) == 1 or field_text is None else field_text
        raw = json.dumps({"model": request["model_id"], "choices": [{
            "finish_reason": "stop", "message": {"content": text}}]}).encode()
        if stop_after_parent and len(calls) == 1:
            runner.request_stop()
        return InferenceResult(raw, text)

    executor = create_local_comparison_executor(factory, case.artifacts, gate=gate, inference=infer)
    runner = JobRunner(factory, {LOCAL_VISUAL_JOB_TYPE: create_local_visual_executor(
        factory, case.artifacts, comparison_executor=executor)})
    return runner, gate, calls


@pytest.mark.parametrize("frozen_trial", [
    "localized_candidate", {"read_format": "localized_candidate", "complete": True},
    {"read_format": "localized_candidate", "focus": True, "complete": True},
], indirect=True)
def test_real_successor_saves_exact_two_reads_and_api_projection_without_adoption(session_factory, comparison):
    case = comparison
    old = case.artifacts.read(case.trial["visual"]["receipt_ref"])
    assert case.service.enqueue(case.revision, case.page, case.body)["job_id"] == case.job["job_id"]
    assert LocalVisualVerificationService(session_factory, case.artifacts).latest(
        case.revision, case.page)["job_id"] == case.body.visual_job_id
    runner, gate, calls = _runner(session_factory, case)
    assert runner.run_job(case.job["job_id"])
    result = case.service.latest(case.revision, case.page, case.body.visual_job_id, 0)
    assert result["state"] == "completed"
    assert result["outcome"]["single_field_transcription_agreement"]
    assert not result["outcome"]["source_position_verified"]
    assert not result["formal_adoption_authorized"]
    assert len(calls) == len(gate.calls) == 2
    with session_factory() as session:
        store = JobStore(session)
        checkpoint = store.get_last_checkpoint(case.job["job_id"], COMPARE_STEP)[1]
        assert store.get_last_checkpoint(case.job["job_id"], PARENT_STEP)
        assert store.get_last_checkpoint(case.job["job_id"], FIELD_STEP)
        trial = json.loads(case.artifacts.read(checkpoint["trial_ref"]))
        assert trial["before"] == trial["after"]
        assert trial["visual_job"]["job_id"] == case.body.visual_job_id
    assert case.artifacts.read(case.trial["visual"]["receipt_ref"]) == old
    assert not runner.run_job(case.job["job_id"])
    assert len(calls) == 2


@pytest.mark.parametrize("frozen_trial", ["localized_candidate"], indirect=True)
def test_transport_failure_retains_parent_then_explicit_retry_only_rereads_field(session_factory, comparison):
    case = comparison
    runner, _, calls = _runner(session_factory, case, fail_field=True)
    assert runner.run_job(case.job["job_id"])
    failed = case.service.latest(case.revision, case.page, case.body.visual_job_id, 0)
    assert failed["state"] == "failed_final" and failed["can_retry"]
    assert failed["outcome"] is None
    with session_factory() as session:
        saved = JobStore(session).get_last_checkpoint(case.job["job_id"], PARENT_STEP)
    JobService(session_factory).retry(case.job["job_id"])
    assert runner.run_job(case.job["job_id"])
    assert case.service.latest(case.revision, case.page, case.body.visual_job_id, 0)["state"] == "completed"
    with session_factory() as session:
        assert JobStore(session).get_last_checkpoint(case.job["job_id"], PARENT_STEP) == saved
    assert len(calls) == 3


@pytest.mark.parametrize("frozen_trial", ["localized_candidate"], indirect=True)
def test_cancel_preserves_saved_parent_and_new_successor_does_not_rewrite_old_job(session_factory, comparison):
    case = comparison
    runner, _, calls = _runner(session_factory, case, stop_after_parent=True)
    assert runner.run_job(case.job["job_id"])
    with session_factory() as session:
        parent = JobStore(session).get_last_checkpoint(case.job["job_id"], PARENT_STEP)
    assert parent and len(calls) == 1
    JobService(session_factory).cancel(case.job["job_id"])
    JobRunner(session_factory, runner.executors).run_job(case.job["job_id"])
    assert case.service.latest(case.revision, case.page, case.body.visual_job_id, 0)["state"] == "cancelled"
    successor = case.service.enqueue(case.revision, case.page, case.body)
    assert successor["job_id"] != case.job["job_id"]
    with session_factory() as session:
        assert JobStore(session).get_job(case.job["job_id"]).state == "cancelled"
        assert JobStore(session).get_last_checkpoint(case.job["job_id"], PARENT_STEP) == parent


@pytest.mark.parametrize("frozen_trial", ["localized_candidate"], indirect=True)
def test_different_value_is_unresolved_not_patient_missing_or_automatic_fact(session_factory, comparison):
    runner, _, _ = _runner(session_factory, comparison, field_text="年龄：51岁")
    assert runner.run_job(comparison.job["job_id"])
    result = comparison.service.latest(comparison.revision, comparison.page, comparison.body.visual_job_id, 0)
    assert result["state"] == "completed" and not result["outcome"]["single_field_transcription_agreement"]
    assert result["outcome"]["status"] == "unresolved"


@pytest.mark.parametrize("frozen_trial", ["localized_candidate"], indirect=True)
def test_wrong_ocr_configuration_refuses_before_call(session_factory, comparison):
    runner, gate, calls = _runner(session_factory, comparison)
    gate.model = "other-provider"
    assert runner.run_job(comparison.job["job_id"])
    result = comparison.service.latest(comparison.revision, comparison.page, comparison.body.visual_job_id, 0)
    assert result["state"] == "failed_final" and not result["can_retry"]
    assert not calls


@pytest.mark.parametrize("frozen_trial", [{"read_format": "localized_candidate", "whole_region": True}], indirect=True)
def test_identical_crop_reuses_committed_read_without_second_call_or_adoption(session_factory, comparison):
    runner, _, calls = _runner(session_factory, comparison)
    assert runner.run_job(comparison.job["job_id"])
    result = comparison.service.latest(comparison.revision, comparison.page, comparison.body.visual_job_id, 0)
    assert result["state"] == "completed" and len(calls) == 1
    assert not result["outcome"]["source_position_verified"]
    assert not result["formal_adoption_authorized"]
    with session_factory() as session:
        store = JobStore(session)
        parent = store.get_last_checkpoint(comparison.job["job_id"], PARENT_STEP)[1]
        field = store.get_last_checkpoint(comparison.job["job_id"], FIELD_STEP)[1]
        assert field["read_ref"] == parent["read_ref"]
        assert field["reused_from_step"] == PARENT_STEP
        assert field["reuse_basis"] == "exact-request-and-pixels/v1"


@pytest.mark.parametrize("frozen_trial", ["localized_candidate"], indirect=True)
def test_configuration_failure_can_start_successor_without_rewriting_failed_history(session_factory, comparison):
    case = comparison
    runner, gate, calls = _runner(session_factory, case)
    gate.model = "other-provider"
    assert runner.run_job(case.job["job_id"]) and not calls
    with session_factory() as session:
        old = JobStore(session).get_job(case.job["job_id"])
        old_payload = old.payload_sha256
    successor = case.service.enqueue(case.revision, case.page, case.body)
    assert successor["created"] and successor["job_id"] != case.job["job_id"]
    gate.model = case.request["model_id"]
    assert runner.run_job(successor["job_id"])
    assert case.service.latest(case.revision, case.page, case.body.visual_job_id, 0)["state"] == "completed"
    with session_factory() as session:
        old = JobStore(session).get_job(case.job["job_id"])
        new = JobStore(session).get_job(successor["job_id"])
        assert old.state == "failed_final" and old.payload_sha256 == old_payload
        assert json.loads(new.payload_json)["previous_job_id"] == old.job_id


@pytest.mark.parametrize("frozen_trial", [
    {"read_format": "localized_candidate", "two_items": True, "same_field_region": True},
    {"read_format": "localized_candidate", "focus": True, "outside_focus": True},
], indirect=True)
def test_duplicate_or_outside_focus_position_is_rejected_before_new_job(session_factory, frozen_trial):
    artifacts, trial, visual, _, _ = frozen_trial
    service = LocalVisualComparisonService(session_factory, artifacts)
    with pytest.raises(AppScopeMismatchError):
        service.enqueue(visual.get("requested_processing_revision_id", visual["base_processing_revision_id"]),
                        visual["page_artifact_id"], LocalFieldComparisonRequest(
                            visual_job_id=trial["visual_job"]["job_id"], item_index=0))


@pytest.mark.parametrize("frozen_trial", ["localized_candidate"], indirect=True)
def test_foreign_page_and_forged_adoption_input_cannot_enqueue(comparison):
    from pydantic import ValidationError

    with pytest.raises(AppScopeMismatchError):
        comparison.service.enqueue(comparison.revision, "foreign", comparison.body)
    with pytest.raises(ValidationError):
        LocalFieldComparisonRequest(visual_job_id=comparison.body.visual_job_id, item_index=True)
    with pytest.raises(ValidationError):
        LocalFieldComparisonRequest(visual_job_id=comparison.body.visual_job_id, item_index=0, verified=True)


@pytest.mark.parametrize("frozen_trial", ["localized_candidate"], indirect=True)
def test_completed_checkpoint_cannot_replace_chosen_item_or_trial(session_factory, comparison):
    from app.storage.codecs import encode_value
    from app.storage.models import JobCheckpointRecord

    runner, _, _ = _runner(session_factory, comparison)
    runner.run_job(comparison.job["job_id"])
    with session_factory() as session, session.begin():
        key, saved = JobStore(session).get_last_checkpoint(comparison.job["job_id"], COMPARE_STEP)
        saved["subreads"][0]["item_index"] = 1
        row = session.get(JobCheckpointRecord, key)
        row.payload_json, row.payload_sha256 = encode_value(saved)
    with pytest.raises(AppScopeMismatchError):
        comparison.service.latest(comparison.revision, comparison.page, comparison.body.visual_job_id, 0)
