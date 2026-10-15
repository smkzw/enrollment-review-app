"""Region read production, persistence, recovery and consumer boundary."""
import io
import json
import re
from dataclasses import replace
from types import SimpleNamespace

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


def _seed(factory, paths, *, raw_text=None, image_bytes=None):
    image = io.BytesIO()
    Image.new("RGB", (80, 60), "white").save(image, "PNG")
    kwargs = {} if raw_text is None else {"raw_text": raw_text}
    return _seed_frozen_revision(factory, paths, revision_id="local-job-base", image_bytes=image.getvalue() if image_bytes is None else image_bytes, **kwargs)


def _seed_complete(factory, paths, *, raw_text=None):
    from app.domain.contracts.enums import OcrRiskLevel, OcrRiskReviewDecision
    from app.domain.contracts.evidence_ingestion import SourceDocumentMetadataRevision
    from app.domain.contracts.evidence_locator import OCRRiskReview
    from app.services.evidence_revision_workflow import EvidenceRevisionBuildRequest, EvidenceRevisionWorkflow
    from app.services.evidence_sidecar_preparation import EvidenceSidecarPreparationService
    from app.storage.evidence_locator_repositories import OCRRiskScanRepository, OCRRiskReviewRepository
    from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord
    from app.storage.evidence_repositories import SourceDocumentMetadataRevisionRepository
    from app.storage.ocr_repositories import EvidenceProcessingRevisionRepository
    from tests.v2.storage.test_ocr_repositories import FIXED_UTC

    seeded = _seed(factory, paths, raw_text=raw_text)
    artifacts = ArtifactStore(paths)
    with factory() as session, session.begin():
        base = EvidenceProcessingRevisionRepository(session).get(seeded["revision_id"])
        SourceDocumentMetadataRevisionRepository(session).append(SourceDocumentMetadataRevision(
            metadata_revision_id="local-complete-metadata", source_document_version_id="doc-svo-1",
            document_type="lab", source_party="hospital", reason="Synthetic source fixture",
            is_auto_suggestion=False, revision=1, created_at=FIXED_UTC, created_by="tester",
        ))
    EvidenceSidecarPreparationService(factory, artifacts).prepare(seeded["revision_id"])
    with factory() as session, session.begin():
        for scan in OCRRiskScanRepository(session).list_by_page(seeded["ocr_page_id"]):
            for flag in scan.flags:
                if flag.level == OcrRiskLevel.BLOCKING:
                    OCRRiskReviewRepository(session).create(OCRRiskReview(
                        review_id=f"local-complete-{flag.risk_id}", risk_flag_id=f"{scan.scan_id}:{flag.risk_id}",
                        decision=OcrRiskReviewDecision.CONFIRMED_AS_READ, reason="Synthetic source fixture",
                        actor="tester", base_processing_revision_id=seeded["revision_id"],
                        expected_revision=1, created_at=FIXED_UTC,
                    ))
        locator_ids = [row.locator_id for row in session.query(EvidenceLocatorArtifactRecord).filter_by(
            page_artifact_id=seeded["page_artifact_id"],
        ).all()]
    workflow = EvidenceRevisionWorkflow(factory, artifacts)
    candidate = workflow.start(EvidenceRevisionBuildRequest(
        evidence_snapshot_id=base.evidence_snapshot_id, base_processing_revision_id=seeded["revision_id"],
        project_id=base.project_id, subject_id=base.subject_id, review_episode_id=base.review_episode_id,
        expected_revision=1, idempotency_key="local-complete-fixture", created_by="tester",
        selected_locator_ids=locator_ids,
    ))
    built = workflow.run_build(candidate.candidate_id)
    return {**seeded, "complete_revision_id": built.complete_revision_id}


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
    receipt = json.loads(store.read(checkpoint["receipt_ref"]))
    assert receipt["model"] == "fixture-model"
    assert receipt["reported_model"] is None
    assert receipt["response_id"] is None and receipt["request_id"] is None
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


def test_missing_provider_envelope_survives_receipt_and_explicit_job_recovery(
    session_factory, data_paths, monkeypatch,
):
    from app.llm import independent_vlm as vlm

    seeded = _seed(session_factory, data_paths)
    store = ArtifactStore(data_paths)
    service = LocalVisualVerificationService(session_factory, store)
    job = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"],
                          LocalVisualRegionRequest(x0=3, y0=4, x1=30, y1=40))
    calls = []

    async def create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return SimpleNamespace(choices=[], id="failed-envelope", _request_id="failed-request", model=None)
        texts = "\n".join(part.get("text", "") for message in kwargs["messages"]
                          if isinstance(message.get("content"), list) for part in message["content"])
        source = re.search(r"\[PAGE_ANCHOR source_ref=([^\s\]]+)", texts).group(1)
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=f"source_ref={source}\n批注所指对象尚不明确。", reasoning_content=None),
            finish_reason="stop",
        )], model="synthetic-model", usage=None)

    monkeypatch.setattr(vlm, "get_independent_vlm_client", lambda: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
    ))
    runner = JobRunner(session_factory, {LOCAL_VISUAL_JOB_TYPE: create_local_visual_executor(session_factory, store)})
    assert runner.run_job(job["job_id"])
    failed = service.latest(seeded["revision_id"], seeded["page_artifact_id"])
    assert failed["state"] == "failed_final" and failed["can_retry"] is True
    assert "未返回完整的回答" in failed["failure_message"]
    assert failed["observation_text"] is None
    with session_factory() as session:
        persisted = JobStore(session).get_job(job["job_id"])
        assert persisted.error_code == "LOCAL_VISUAL_PROVIDER_RESPONSE_INVALID"
        checkpoint = JobStore(session).get_last_checkpoint(job["job_id"], LOCAL_VISUAL_STEP)[1]
    old_bytes = store.read(checkpoint["receipt_ref"])
    receipt = json.loads(old_bytes)
    assert receipt["failure_kind"] == "provider_response_invalid"
    assert receipt["reported_model"] is None and receipt["usage"] == {}
    assert receipt["request_id"] == "failed-request" and receipt["response_id"] == "failed-envelope"
    assert not runner.run_once() and len(calls) == 1
    JobService(session_factory).retry(job["job_id"])
    assert runner.run_job(job["job_id"])
    result = service.latest(seeded["revision_id"], seeded["page_artifact_id"])
    assert result["state"] == "completed" and result["candidate_only"] is True
    assert len(calls) == 2 and store.read(checkpoint["receipt_ref"]) == old_bytes
    with session_factory() as session:
        assert not SelectiveVisionObservationRepository(session).list_by_page_artifact(seeded["page_artifact_id"])


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


@pytest.mark.parametrize("rotation,selection,expected", [
    (0, (20, 10, 40, 30), (16, 7, 44, 33)),
    (180, (20, 10, 40, 30), (16, 7, 44, 33)),
    (90, (0, 0, 30, 80), (0, 0, 33, 80)),
    (270, (55, 70, 60, 80), (52, 66, 60, 80)),
])
def test_context_read_keeps_requested_focus_separate_from_clipped_image(
    session_factory, data_paths, rotation, selection, expected,
):
    from app.services.selective_vision_observation_service import local_visual_prompt_identity

    seeded = _seed(session_factory, data_paths)
    service = LocalVisualVerificationService(session_factory, ArtifactStore(data_paths))
    coords = dict(zip(("x0", "y0", "x1", "y1"), selection, strict=True))
    original = LocalVisualRegionRequest(**coords, clockwise_degrees=rotation)
    ordinary = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"], original)
    requested = original.model_copy(update={"include_context": True})
    focused = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"], requested)
    assert ordinary["job_id"] != focused["job_id"]
    assert service.enqueue(seeded["revision_id"], seeded["page_artifact_id"], requested)["job_id"] == focused["job_id"]
    with session_factory() as session:
        first = json.loads(JobStore(session).get_job(ordinary["job_id"]).payload_json)
        payload = json.loads(JobStore(session).get_job(focused["job_id"]).payload_json)
    assert "focus_bbox" not in first and "include_context" not in first["region"]
    assert first["prompt_sha256"] == local_visual_prompt_identity()
    assert tuple(payload["region"][key] for key in ("x0", "y0", "x1", "y1")) == expected
    assert payload["focus_bbox"] == coords
    assert payload["requested_region"] == {**coords, "clockwise_degrees": rotation, "include_context": True}
    assert payload["prompt_sha256"] != first["prompt_sha256"]
    assert service.latest(seeded["revision_id"], seeded["page_artifact_id"], job_id=focused["job_id"])["region"] == payload["requested_region"]


def test_invalid_context_flag_rejected_without_a_job():
    for value in ("true", 1, None):
        with pytest.raises(ValidationError):
            LocalVisualRegionRequest(x0=1, y0=1, x1=10, y1=10, include_context=value)


@pytest.mark.parametrize("read_format,expected", [
    ("transcript", "80cb6a736d8caa4cd837536bbd8683d39ee4f665f941cc136eb46610d1bbd25f"),
    ("structured_candidate", "c17b4749e2a4332587b20705baca2b0ff0427ce4357e2ff197c772210387f8aa"),
    ("localized_candidate", "df47cdf189ef106ee971e02e3946d774eb25d02903e45b30f2695dac694fbc80"),
])
def test_default_prompt_identity_matches_frozen_60a849e6(read_format, expected):
    from app.services.selective_vision_observation_service import local_visual_prompt_identity

    assert local_visual_prompt_identity(read_format) == expected


@pytest.mark.parametrize("missing", ["prompt_sha256", "clockwise_degrees"])
def test_incomplete_saved_payload_cannot_pass_receipt_readback(missing):
    from app.services.local_visual_verification import _receipt_matches

    payload = {"evidence_processing_revision_id": "rev", "page_artifact_id": "page",
               "source_image_sha256": "a" * 64, "prompt_sha256": "b" * 64,
               "region": {"x0": 1, "y0": 1, "x1": 30, "y1": 40, "clockwise_degrees": 0}}
    del (payload["region"] if missing == "clockwise_degrees" else payload)[missing]
    assert not _receipt_matches(payload, {"status": "read", "candidate_only": True, "coverage_scope": "region_only",
                                         "base_processing_revision_id": "rev", "page_artifact_id": "page"})


@pytest.mark.parametrize("damage", ["missing_ref", "missing_blob", "invalid_json", "json_array"])
def test_damaged_saved_receipt_is_nonretryable_and_does_not_reread(
    session_factory, data_paths, monkeypatch, damage,
):
    seeded = _seed(session_factory, data_paths)
    store = ArtifactStore(data_paths)
    service = LocalVisualVerificationService(session_factory, store)
    job = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"],
                          LocalVisualRegionRequest(x0=1, y0=1, x1=30, y1=40))
    calls = []

    async def chat(prompt, pages, **kwargs):
        calls.append(1)
        return IndependentVlmChatResult(text=f"source_ref={pages[0].source_ref}\n批注对象不明。",
                                       model="fixture-model", finish_reason="stop", usage={})

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", chat)
    executor = create_local_visual_executor(session_factory, store)
    assert JobRunner(session_factory, {LOCAL_VISUAL_JOB_TYPE: executor}).run_job(job["job_id"])
    with session_factory() as session:
        persisted = JobStore(session).get_job(job["job_id"])
        payload = json.loads(persisted.payload_json)
        checkpoint = JobStore(session).get_last_checkpoint(job["job_id"], LOCAL_VISUAL_STEP)[1]
    original = store.read(checkpoint["receipt_ref"])
    damaged = dict(checkpoint)
    if damage == "missing_ref":
        damaged.pop("receipt_ref")
    elif damage == "missing_blob":
        damaged["receipt_ref"] = "artifacts/evaluation_manifest/" + "0" * 64
    else:
        damaged["receipt_ref"] = store.put(
            "evaluation_manifest", b"{" if damage == "invalid_json" else b"[]",
        ).storage_ref
    context = StepContext(job["job_id"], LOCAL_VISUAL_JOB_TYPE, payload, LOCAL_VISUAL_STEP,
                          "Synthetic read", 1, "checkpoint", damaged)
    with pytest.raises(StepFailure) as caught:
        executor(context)
    assert caught.value.error_code == "LOCAL_VISUAL_RECEIPT_INVALID"
    assert caught.value.retryable is False
    assert len(calls) == 1 and store.read(checkpoint["receipt_ref"]) == original


@pytest.mark.parametrize("damage", ["foreign_page", "length_marked_read", "invalid_json", "json_array"])
def test_new_receipt_must_match_source_before_job_can_complete(
    session_factory, data_paths, monkeypatch, damage,
):
    from app.services.selective_vision_observation_service import SelectiveVisionObservationService

    seeded = _seed(session_factory, data_paths)
    store = ArtifactStore(data_paths)
    service = LocalVisualVerificationService(session_factory, store)
    job = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"],
                          LocalVisualRegionRequest(x0=1, y0=1, x1=30, y1=40))
    calls = []
    original_receipts = []
    reader = SelectiveVisionObservationService(session_factory)

    async def chat(prompt, pages, **kwargs):
        calls.append(1)
        return IndependentVlmChatResult(text=f"source_ref={pages[0].source_ref}\n批注对象不明。",
                                       model="fixture-model", finish_reason="stop", usage={})

    class DamagedReceiptReader:
        async def verify_local_region(self, *args, **kwargs):
            receipt = await reader.verify_local_region(*args, **kwargs)
            original = store.read(receipt.storage_ref)
            original_receipts.append((receipt.storage_ref, original))
            value = json.loads(original)
            if damage == "foreign_page":
                value["page_artifact_id"] = "another-page"
            elif damage == "length_marked_read":
                value["finish_reason"] = "length"
            raw = (b"{" if damage == "invalid_json" else b"[]" if damage == "json_array"
                   else json.dumps(value, ensure_ascii=False).encode())
            return store.put("evaluation_manifest", raw)

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", chat)
    executor = create_local_visual_executor(session_factory, store, service=DamagedReceiptReader())
    runner = JobRunner(session_factory, {LOCAL_VISUAL_JOB_TYPE: executor})
    assert runner.run_job(job["job_id"])
    with session_factory() as session:
        record = JobStore(session).get_job(job["job_id"])
        assert record.state == "failed_final" and record.error_code == "LOCAL_VISUAL_RECEIPT_INVALID"
    result = service.latest(seeded["revision_id"], seeded["page_artifact_id"])
    assert result["can_retry"] is False and result["observation_text"] is None
    assert not runner.run_job(job["job_id"])
    assert len(calls) == 1
    assert all(store.read(ref) == raw for ref, raw in original_receipts)
    with session_factory() as session:
        assert not SelectiveVisionObservationRepository(session).list_by_page_artifact(seeded["page_artifact_id"])
