"""Typed region results remain proposals and preserve failure/replay boundaries."""
import json

import pytest

from app.domain.contracts.local_region_read import parse_local_region_read
from app.evidence.artifacts import ArtifactStore
from app.llm.independent_vlm import IndependentVlmChatResult
from app.services.evidence_app_errors import AppScopeMismatchError
from app.services.job_service import JobService
from app.services.local_visual_verification import (
    LOCAL_VISUAL_JOB_TYPE, LOCAL_VISUAL_STEP, LocalVisualRegionRequest,
    LocalVisualVerificationService, create_local_visual_executor,
)
from app.storage.selective_vision_observation_repository import SelectiveVisionObservationRepository
from app.workflow.jobstore import JobStore
from app.workflow.errors import StepFailure
from app.workflow.runner import JobRunner, StepContext
from tests.v2.services.test_local_visual_job import _seed


def _reading():
    return {"items": [{
        "label": "示例测量", "raw_value": "4.04", "raw_unit": "10⁹/L",
        "reference_text": "3.50—9.50", "time_label": None,
        "excerpt": "示例测量 4.04 3.50—9.50 10⁹/L", "position": "本区域第一行",
        "script": "printed", "legibility": "clear", "annotation_target": None,
    }], "unresolved": ["区域边缘有裁切，其他项目无法确认。"]}


@pytest.mark.parametrize("kind,code", [
    ("transport_timeout", "LOCAL_VISUAL_TIMEOUT"),
    ("transport_connection", "LOCAL_VISUAL_CONNECTION_FAILED"),
    ("remote_error", "LOCAL_VISUAL_PROVIDER_FAILED"),
    ("provider_response_invalid", "LOCAL_VISUAL_PROVIDER_RESPONSE_INVALID"),
    ("auth", "LOCAL_VISUAL_AUTH_FAILED"),
    ("quota", "LOCAL_VISUAL_QUOTA"),
])
def test_provider_failure_is_saved_and_displayed_as_technical_failure(
    session_factory, data_paths, monkeypatch, kind, code,
):
    from app.llm.independent_vlm import IndependentVlmRemoteError

    seeded = _seed(session_factory, data_paths)
    artifacts = ArtifactStore(data_paths)
    service = LocalVisualVerificationService(session_factory, artifacts)
    job = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"],
                          LocalVisualRegionRequest(x0=1, y0=1, x1=30, y1=40))
    calls = []

    async def chat(*args, **kwargs):
        calls.append(1)
        raise IndependentVlmRemoteError("private provider detail", failure_kind=kind,
                                        disabled=True, status_code=503 if kind == "remote_error" else None)

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", chat)
    runner = JobRunner(session_factory, {LOCAL_VISUAL_JOB_TYPE: create_local_visual_executor(session_factory, artifacts)})
    assert runner.run_job(job["job_id"])
    view = service.latest(seeded["revision_id"], seeded["page_artifact_id"], job_id=job["job_id"])
    assert view["state"] == "failed_final" and view["observation_text"] is None
    assert "本次" in view["failure_message"] or "尚未" in view["failure_message"]
    assert "private provider detail" not in view["failure_message"]
    with session_factory() as session:
        jobs = JobStore(session)
        checkpoint = jobs.get_last_checkpoint(job["job_id"], LOCAL_VISUAL_STEP)[1]
        assert jobs.get_job(job["job_id"]).error_code == code
        assert not SelectiveVisionObservationRepository(session).list_by_page_artifact(seeded["page_artifact_id"])
    receipt = json.loads(artifacts.read(checkpoint["receipt_ref"]))
    assert receipt["failure_kind"] == kind and receipt["model"] is None
    assert view["can_retry"] is (kind != "auth")
    assert receipt["usage"] == {} and "private provider detail" not in json.dumps(receipt)
    if kind == "remote_error":
        assert receipt["remote_status_code"] == 503
    assert not runner.run_job(job["job_id"]) and len(calls) == 1


@pytest.mark.parametrize("mutation", [
    "missing_source", "truncated", "judgment", "missing_fields", "empty",
])
def test_invalid_structured_read_is_not_repaired_or_adopted(mutation):
    data = _reading()
    if mutation == "judgment":
        data["items"][0]["exclusion_triggered"] = False
    elif mutation == "missing_fields":
        del data["items"][0]["raw_unit"]
    elif mutation == "empty":
        data = {"items": [], "unresolved": []}
    text = "source_ref=region:fixture\n" + json.dumps(data, ensure_ascii=False)
    if mutation == "missing_source":
        text = text.replace("region:fixture", "region:other")
    elif mutation == "truncated":
        text = text[:-1]
    with pytest.raises(ValueError):
        parse_local_region_read(text, source_ref="region:fixture")


@pytest.mark.parametrize("failure,code,retry", [
    ("length", "LOCAL_VISUAL_RESPONSE_LENGTH", True),
    ("empty", "LOCAL_VISUAL_RESPONSE_INCOMPLETE", True),
    ("source", "LOCAL_VISUAL_SOURCE_FIDELITY", False),
])
def test_incomplete_and_wrong_source_responses_have_distinct_job_reasons(
    session_factory, data_paths, monkeypatch, failure, code, retry,
):
    from app.llm.independent_vlm import IndependentVlmSourceFidelityError

    seeded = _seed(session_factory, data_paths)
    artifacts = ArtifactStore(data_paths)
    service = LocalVisualVerificationService(session_factory, artifacts)
    job = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"],
                          LocalVisualRegionRequest(x0=1, y0=1, x1=30, y1=40))
    calls = []

    async def chat(prompt, pages, **kwargs):
        calls.append(1)
        answer = IndependentVlmChatResult(
            text="source_ref=" + pages[0].source_ref + ("" if failure == "empty" else "\n圈选文字。"),
            model="fixture", finish_reason="length" if failure == "length" else "stop", usage={},
        )
        if failure == "source":
            raise IndependentVlmSourceFidelityError("wrong source", rejected_response=answer)
        return answer

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", chat)
    runner = JobRunner(session_factory, {LOCAL_VISUAL_JOB_TYPE: create_local_visual_executor(session_factory, artifacts)})
    assert runner.run_job(job["job_id"])
    view = service.latest(seeded["revision_id"], seeded["page_artifact_id"], job_id=job["job_id"])
    with session_factory() as session:
        assert JobStore(session).get_job(job["job_id"]).error_code == code
    assert view["can_retry"] is retry and view["observation_text"] is None
    assert not runner.run_job(job["job_id"]) and calls == [1]


def test_whole_crop_cannot_claim_marked_policy():
    from app.evidence.reading_view import FOCUS_READING_IMAGE_VERSION
    from app.services.local_visual_verification import _payload_scope_matches

    box = {"x0": 0, "y0": 0, "x1": 80, "y1": 60, "clockwise_degrees": 0}
    payload = {"region": box, "focus_bbox": {key: box[key] for key in ("x0", "y0", "x1", "y1")},
               "requested_region": {**box, "include_context": True}, "model_image_policy": FOCUS_READING_IMAGE_VERSION}
    assert not _payload_scope_matches(payload)
    del payload["model_image_policy"]
    assert _payload_scope_matches(payload)


def test_typed_result_production_save_readback_and_explicit_failure_retry(
    session_factory, data_paths, monkeypatch,
):
    seeded = _seed(session_factory, data_paths)
    artifacts = ArtifactStore(data_paths)
    service = LocalVisualVerificationService(session_factory, artifacts)
    box = LocalVisualRegionRequest(x0=1, y0=1, x1=30, y1=40)
    legacy = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"], box)
    box = box.model_copy(update={"read_format": "structured_candidate"})
    job = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"], box)
    assert legacy["job_id"] != job["job_id"]
    with session_factory() as session:
        payload = json.loads(JobStore(session).get_job(legacy["job_id"]).payload_json)
        assert "read_format" not in payload["region"]
        assert payload["region"]["clockwise_degrees"] == 0
    calls = []

    async def chat(prompt, pages, **kwargs):
        calls.append(prompt)
        assert '"raw_unit"' in prompt and "参考范围" in prompt
        assert "4.04" not in prompt
        body = json.dumps(_reading(), ensure_ascii=False) if len(calls) > 1 else "{"
        return IndependentVlmChatResult(
            text="source_ref=" + pages[0].source_ref + "\n" + body,
            model="fixture-model", finish_reason="stop", usage={"completion_tokens": 70},
        )

    monkeypatch.setenv("INDEPENDENT_VLM_MAX_TOKENS", "65536")
    monkeypatch.setenv("INDEPENDENT_VLM_REASONING_EFFORT", "high")
    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", chat)
    runner = JobRunner(session_factory, {LOCAL_VISUAL_JOB_TYPE: create_local_visual_executor(session_factory, artifacts)})
    assert runner.run_job(job["job_id"])
    failed = service.latest(seeded["revision_id"], seeded["page_artifact_id"], job_id=job["job_id"])
    assert failed["state"] == "failed_final" and failed["observation_text"] is None
    with session_factory() as session:
        checkpoint = JobStore(session).get_last_checkpoint(job["job_id"], LOCAL_VISUAL_STEP)[1]
    receipt = json.loads(artifacts.read(checkpoint["receipt_ref"]))
    assert receipt["failure_kind"] == "local_structure_invalid"
    assert receipt["requested_max_tokens"] == 65536 and receipt["requested_effort"] == "high"
    assert "structured_read" not in receipt
    JobService(session_factory).retry(job["job_id"])
    assert runner.run_job(job["job_id"])
    result = service.latest(seeded["revision_id"], seeded["page_artifact_id"], job_id=job["job_id"])
    assert result["state"] == "completed" and result["structured_read"] == _reading()
    assert result["candidate_only"] is True and result["coverage_scope"] == "region_only"
    assert "尚未采用" in result["observation_text"]
    assert not runner.run_job(job["job_id"])
    assert len(calls) == 2
    with session_factory() as session:
        assert not SelectiveVisionObservationRepository(session).list_by_page_artifact(seeded["page_artifact_id"])


@pytest.mark.parametrize("mutation", ["structured_value", "raw_value", "source", "length", "empty"])
def test_saved_reading_disagreement_rejected_by_display_and_replay(
    session_factory, data_paths, monkeypatch, mutation,
):
    from app.storage.codecs import encode_value
    from app.storage.models import JobCheckpointRecord

    seeded = _seed(session_factory, data_paths)
    artifacts = ArtifactStore(data_paths)
    service = LocalVisualVerificationService(session_factory, artifacts)
    box = LocalVisualRegionRequest(x0=1, y0=1, x1=30, y1=40, read_format="structured_candidate")
    job = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"], box)
    calls = []

    async def chat(prompt, pages, **kwargs):
        calls.append(1)
        return IndependentVlmChatResult(
            text="source_ref=" + pages[0].source_ref + "\n" + json.dumps(_reading(), ensure_ascii=False),
            model="fixture-model", finish_reason="stop", usage={},
        )

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", chat)
    executor = create_local_visual_executor(session_factory, artifacts)
    assert JobRunner(session_factory, {LOCAL_VISUAL_JOB_TYPE: executor}).run_job(job["job_id"])
    original_view = service.latest(seeded["revision_id"], seeded["page_artifact_id"], job_id=job["job_id"])
    assert original_view["structured_read"] == _reading()
    with session_factory() as session:
        jobs = JobStore(session)
        payload = json.loads(jobs.get_job(job["job_id"]).payload_json)
        checkpoint_id, checkpoint = jobs.get_last_checkpoint(job["job_id"], LOCAL_VISUAL_STEP)
    original_ref = checkpoint["receipt_ref"]
    original_bytes = artifacts.read(original_ref)
    receipt = json.loads(original_bytes)
    if mutation == "structured_value":
        receipt["structured_read"]["items"][0]["raw_value"] = "5.04"
    elif mutation == "raw_value":
        receipt["observation_text"] = receipt["observation_text"].replace("4.04", "5.04")
    elif mutation == "source":
        receipt["observation_text"] = receipt["observation_text"].replace(receipt["region_source_ref"], "region:other")
    elif mutation == "length":
        receipt["finish_reason"] = "length"
    else:
        receipt["observation_text"] = "source_ref=" + receipt["region_source_ref"]
    checkpoint = {**checkpoint, "receipt_ref": artifacts.put(
        "evaluation_manifest", json.dumps(receipt, ensure_ascii=False).encode(),
    ).storage_ref}
    # Simulate an erroneous producer binding a valid-hash but inconsistent
    # receipt; corrupt bytes alone are already rejected by ArtifactStore.
    with session_factory() as session, session.begin():
        row = session.get(JobCheckpointRecord, checkpoint_id)
        row.payload_json, row.payload_sha256 = encode_value(checkpoint)
    with pytest.raises(AppScopeMismatchError, match="局部核实记录与原件不一致"):
        service.latest(seeded["revision_id"], seeded["page_artifact_id"], job_id=job["job_id"])
    context = StepContext(job["job_id"], LOCAL_VISUAL_JOB_TYPE, payload, LOCAL_VISUAL_STEP,
                          "核实原件局部", 1, checkpoint_id, checkpoint)
    with pytest.raises(StepFailure) as caught:
        executor(context)
    assert caught.value.error_code == "LOCAL_VISUAL_RECEIPT_INVALID"
    assert len(calls) == 1 and artifacts.read(original_ref) == original_bytes
    assert not JobRunner(session_factory, {LOCAL_VISUAL_JOB_TYPE: executor}).run_job(job["job_id"])


@pytest.mark.parametrize("whole_page", [False, True])
def test_unmarked_legacy_or_whole_page_context_keeps_input_and_remains_replayable(
    session_factory, data_paths, monkeypatch, whole_page,
):
    from app.services.local_visual_verification import _payload_prompt_identity
    from app.storage.codecs import encode_value
    from app.storage.models import JobRecord

    seeded = _seed(session_factory, data_paths)
    artifacts = ArtifactStore(data_paths)
    service = LocalVisualVerificationService(session_factory, artifacts)
    job = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"],
                          LocalVisualRegionRequest(x0=0, y0=0, x1=80, y1=60, include_context=True) if whole_page
                          else LocalVisualRegionRequest(x0=20, y0=10, x1=40, y1=30, include_context=True))
    # Freeze the old payload shape before executing this synthetic historical job.
    with session_factory() as session, session.begin():
        record = session.get(JobRecord, job["job_id"])
        payload = json.loads(record.payload_json)
        if whole_page:
            assert "model_image_policy" not in payload
        else:
            del payload["model_image_policy"]
            payload["prompt_sha256"] = _payload_prompt_identity(payload)
        record.payload_json, record.payload_sha256 = encode_value(payload)
    calls = []

    async def chat(prompt, pages, **kwargs):
        calls.append(pages[0].image_bytes)
        assert "红框不是原件批注" not in kwargs["system_prompt"]
        return IndependentVlmChatResult(text="source_ref=" + pages[0].source_ref + "\n圈定文字无法辨认。",
                                       model="fixture-model", finish_reason="stop", usage={})

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", chat)
    executor = create_local_visual_executor(session_factory, artifacts)
    assert JobRunner(session_factory, {LOCAL_VISUAL_JOB_TYPE: executor}).run_job(job["job_id"])
    view = service.latest(seeded["revision_id"], seeded["page_artifact_id"], job_id=job["job_id"])
    assert view["state"] == "completed" and view["candidate_only"] is True
    with session_factory() as session:
        checkpoint_id, checkpoint = JobStore(session).get_last_checkpoint(job["job_id"], LOCAL_VISUAL_STEP)
    receipt = json.loads(artifacts.read(checkpoint["receipt_ref"]))
    assert "model_image_policy" not in receipt and "model_image_sha256" not in receipt
    assert calls == [artifacts.read(receipt["image_artifact_ref"])]
    context = StepContext(job["job_id"], LOCAL_VISUAL_JOB_TYPE, payload, LOCAL_VISUAL_STEP,
                          "核实原件局部", 1, checkpoint_id, checkpoint)
    assert executor(context) == checkpoint and len(calls) == 1


def test_marked_receipt_verifies_pixels_not_png_encoder_bytes(session_factory, data_paths, monkeypatch):
    import io
    from hashlib import sha256
    from PIL import Image, PngImagePlugin
    from app.services.local_visual_verification import _model_image_matches

    seeded = _seed(session_factory, data_paths)
    artifacts = ArtifactStore(data_paths)
    service = LocalVisualVerificationService(session_factory, artifacts)
    job = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"],
                          LocalVisualRegionRequest(x0=20, y0=10, x1=40, y1=30, include_context=True))

    async def chat(prompt, pages, **kwargs):
        return IndependentVlmChatResult(text="source_ref=" + pages[0].source_ref + "\n圈定文字无法辨认。",
                                       model="fixture-model", finish_reason="stop", usage={})

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", chat)
    assert JobRunner(session_factory, {LOCAL_VISUAL_JOB_TYPE: create_local_visual_executor(session_factory, artifacts)}).run_job(job["job_id"])
    with session_factory() as session:
        checkpoint = JobStore(session).get_last_checkpoint(job["job_id"], LOCAL_VISUAL_STEP)[1]
    receipt = json.loads(artifacts.read(checkpoint["receipt_ref"]))
    original = artifacts.read(receipt["model_image_artifact_ref"])
    output = io.BytesIO()
    info = PngImagePlugin.PngInfo()
    info.add_text("synthetic", "equivalent encoder variant")
    with Image.open(io.BytesIO(original)) as image:
        image.save(output, "PNG", pnginfo=info, optimize=True)
    encoded = output.getvalue()
    assert encoded != original
    receipt["model_image_artifact_ref"] = artifacts.put("reading_view_image", encoded).storage_ref
    receipt["model_image_sha256"] = sha256(encoded).hexdigest()
    assert _model_image_matches(receipt, artifacts)


@pytest.mark.parametrize("outside", [False, True])
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_focused_read_runs_product_job_with_context_but_keeps_target_and_failure_boundaries(
    session_factory, data_paths, monkeypatch, outside, rotation,
):
    from app.domain.contracts.evidence import BoundingBox
    from app.services.selective_vision_observation_service import local_visual_focus_coordinates

    seeded = _seed(session_factory, data_paths)
    artifacts = ArtifactStore(data_paths)
    service = LocalVisualVerificationService(session_factory, artifacts)
    box = LocalVisualRegionRequest(x0=20, y0=10, x1=40, y1=30,
                                  read_format="localized_candidate", include_context=True, clockwise_degrees=rotation)
    job = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"], box)
    calls = []

    async def chat(prompt, pages, **kwargs):
        calls.append(1)
        assert "框外内容只供理解" in prompt and "不能另列框外项目" in prompt
        assert "红框不是原件批注" in kwargs["system_prompt"]
        calls[-1] = pages[0].image_bytes
        assert "不是相对于核实框" in prompt and "4.04" not in prompt
        data = _reading()
        data["items"][0]["proposed_bbox"] = (
            {"x0": 0, "y0": 0, "x1": 100, "y1": 100} if outside
            else {"x0": 100, "y0": 400, "x1": 700, "y1": 800}
        )
        return IndependentVlmChatResult(
            text="source_ref=" + pages[0].source_ref + "\n" + json.dumps(data, ensure_ascii=False),
            model="fixture-model", finish_reason="stop", usage={},
        )

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", chat)
    executor = create_local_visual_executor(session_factory, artifacts)
    runner = JobRunner(session_factory, {LOCAL_VISUAL_JOB_TYPE: executor})
    assert runner.run_job(job["job_id"])
    result = service.latest(seeded["revision_id"], seeded["page_artifact_id"], job_id=job["job_id"])
    assert result["region"]["include_context"] is True
    assert result["region"]["x0"] == box.x0 and result["region"]["y0"] == box.y0
    with session_factory() as session:
        payload = json.loads(JobStore(session).get_job(job["job_id"]).payload_json)
        checkpoint_id, checkpoint = JobStore(session).get_last_checkpoint(job["job_id"], LOCAL_VISUAL_STEP)
        assert not SelectiveVisionObservationRepository(session).list_by_page_artifact(seeded["page_artifact_id"])
    receipt = json.loads(artifacts.read(checkpoint["receipt_ref"]))
    from hashlib import sha256
    from app.evidence.reading_view import FOCUS_READING_IMAGE_VERSION

    assert payload["model_image_policy"] == receipt["model_image_policy"] == FOCUS_READING_IMAGE_VERSION
    assert calls[0] == artifacts.read(receipt["model_image_artifact_ref"])
    assert sha256(calls[0]).hexdigest() == receipt["model_image_sha256"]
    assert calls[0] != artifacts.read(receipt["image_artifact_ref"])
    assert receipt["focus_bbox"] == box.bbox().model_dump(mode="json")
    assert receipt["region"]["view_bbox"] == ({"x0": 17, "y0": 6, "x1": 43, "y1": 34} if rotation in (90, 270) else {"x0": 16, "y0": 7, "x1": 44, "y1": 33})
    assert receipt["candidate_only"] is True and result["coverage_scope"] == "region_only"
    if outside:
        assert result["state"] == "failed_final" and result["observation_text"] is None
        assert receipt["failure_kind"] == "local_focus_scope_mismatch" and "structured_read" not in receipt
        assert receipt["focus_rejected_item_indices"] == [0]
        assert "圈选范围外" in result["failure_message"]
    else:
        assert result["state"] == "completed" and len(result["structured_read"]["items"]) == 1
        context = StepContext(job["job_id"], LOCAL_VISUAL_JOB_TYPE, payload, LOCAL_VISUAL_STEP,
                              "核实原件局部", 1, checkpoint_id, checkpoint)
        assert executor(context) == checkpoint
    assert not runner.run_job(job["job_id"]) and len(calls) == 1
    with pytest.raises(ValueError, match="完整位于"):
        local_visual_focus_coordinates(BoundingBox(x0=16, y0=7, x1=44, y1=33),
                                       BoundingBox(x0=15, y0=10, x1=40, y1=30))


@pytest.mark.parametrize("mutation", ["focus_bbox", "prompt", "model_image", "model_hash", "model_policy", "crop_swap", "same_page_crop_swap", "source_bbox"])
def test_focused_saved_receipt_cannot_change_target_or_actual_prompt(
    session_factory, data_paths, monkeypatch, mutation,
):
    from app.storage.codecs import encode_value
    from app.storage.models import JobCheckpointRecord

    import io
    from hashlib import sha256
    from PIL import Image
    from app.domain.contracts.evidence import BoundingBox
    from app.domain.publication import canonical_hash
    from app.evidence.reading_view import make_focus_reading_image
    from app.services.local_visual_verification import _receipt_matches
    from app.services.selective_vision_observation_service import local_visual_focus_coordinates, local_visual_prompts

    original_image = Image.new("RGB", (80, 60), "white")
    original_image.paste("black", (0, 0, 28, 26))
    buffer = io.BytesIO()
    original_image.save(buffer, "PNG")
    seeded = _seed(session_factory, data_paths, image_bytes=buffer.getvalue())
    artifacts = ArtifactStore(data_paths)
    service = LocalVisualVerificationService(session_factory, artifacts)
    job = service.enqueue(seeded["revision_id"], seeded["page_artifact_id"],
                          LocalVisualRegionRequest(x0=20, y0=10, x1=40, y1=30, include_context=True))
    calls = []

    async def chat(prompt, pages, **kwargs):
        calls.append(1)
        return IndependentVlmChatResult(text="source_ref=" + pages[0].source_ref + "\n圈定文字无法辨认。",
                                       model="fixture-model", finish_reason="stop", usage={})

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", chat)
    executor = create_local_visual_executor(session_factory, artifacts)
    assert JobRunner(session_factory, {LOCAL_VISUAL_JOB_TYPE: executor}).run_job(job["job_id"])
    with session_factory() as session:
        payload = json.loads(JobStore(session).get_job(job["job_id"]).payload_json)
        checkpoint_id, checkpoint = JobStore(session).get_last_checkpoint(job["job_id"], LOCAL_VISUAL_STEP)
    original_ref = checkpoint["receipt_ref"]
    original_bytes = artifacts.read(original_ref)
    receipt = json.loads(original_bytes)
    if mutation == "focus_bbox":
        receipt["focus_bbox"]["x0"] += 1
    elif mutation == "prompt":
        receipt["prompt"] = receipt["prompt"].replace("不能另列框外项目", "可以列出框外项目")
    elif mutation == "model_image":
        receipt["model_image_artifact_ref"] = receipt["image_artifact_ref"]
    elif mutation == "model_hash":
        receipt["model_image_sha256"] = "0" * 64
    elif mutation == "model_policy":
        receipt["model_image_policy"] = "unknown/v1"
    else:
        if mutation == "source_bbox":
            raw = artifacts.read(receipt["image_artifact_ref"])
            receipt["region"]["source_bbox"]["x0"] += 1
        else:
            replacement = original_image.crop((0, 0, 28, 26)) if mutation == "same_page_crop_swap" else Image.new("RGB", (28, 26), "blue")
            buffer = io.BytesIO()
            replacement.save(buffer, "PNG")
            raw = buffer.getvalue()
            receipt["image_artifact_ref"] = artifacts.put("reading_view_image", raw).storage_ref
            receipt["region"]["region_image_sha256"] = sha256(raw).hexdigest()
        region_ref = "region:" + canonical_hash(receipt["region"])
        receipt["observation_text"] = receipt["observation_text"].replace(receipt["region_source_ref"], region_ref)
        receipt["region_source_ref"] = region_ref
        context = BoundingBox.model_validate(receipt["region"]["view_bbox"])
        focus = BoundingBox.model_validate(receipt["focus_bbox"])
        receipt["system_prompt"], receipt["prompt"] = local_visual_prompts(region_ref, "transcript", focus_coordinates=local_visual_focus_coordinates(context, focus), mark_focus=True)
        marked = make_focus_reading_image(raw, BoundingBox(x0=4, y0=3, x1=24, y1=23))
        receipt["model_image_artifact_ref"] = artifacts.put("reading_view_image", marked).storage_ref
        receipt["model_image_sha256"] = sha256(marked).hexdigest()
        assert _receipt_matches(payload, receipt)
    checkpoint = {**checkpoint, "receipt_ref": artifacts.put(
        "evaluation_manifest", json.dumps(receipt, ensure_ascii=False).encode(),
    ).storage_ref}
    with session_factory() as session, session.begin():
        row = session.get(JobCheckpointRecord, checkpoint_id)
        row.payload_json, row.payload_sha256 = encode_value(checkpoint)
    with pytest.raises(AppScopeMismatchError, match="局部核实记录与原件不一致"):
        service.latest(seeded["revision_id"], seeded["page_artifact_id"], job_id=job["job_id"])
    context = StepContext(job["job_id"], LOCAL_VISUAL_JOB_TYPE, payload, LOCAL_VISUAL_STEP,
                          "核实原件局部", 1, checkpoint_id, checkpoint)
    with pytest.raises(StepFailure) as caught:
        executor(context)
    assert caught.value.error_code == "LOCAL_VISUAL_RECEIPT_INVALID"
    assert len(calls) == 1 and artifacts.read(original_ref) == original_bytes
