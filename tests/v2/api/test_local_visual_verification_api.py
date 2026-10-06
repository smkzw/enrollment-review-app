"""Product API enqueue/result are scoped; no model is called by an endpoint."""
import json

import pytest
from app.evidence.artifacts import ArtifactStore
from app.llm.independent_vlm import IndependentVlmChatResult
from app.services.local_visual_verification import LOCAL_VISUAL_JOB_TYPE, LOCAL_VISUAL_STEP
from app.services.selective_vision_postprocess_job_service import SelectiveVisionPostprocessJobService
from app.storage.codecs import encode_value
from app.storage.models import JobCheckpointRecord
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner
from tests.v2.services.test_local_visual_job import _seed, _seed_complete
from tests.v2.services.test_local_region_structured_read import _reading


def test_field_comparison_api_uses_existing_job_and_does_not_replace_the_visual_result(client, monkeypatch):
    from app.evidence.ocr_adapter import InferenceResult
    from app.services.local_visual_comparison_job import create_local_comparison_executor
    from app.services.local_visual_verification import create_local_visual_executor
    from tests.v2.services.test_local_visual_comparison_job import Gate

    factory = client.app.state.session_factory
    artifacts = ArtifactStore(client.app.state.data_paths)
    seeded = _seed(factory, client.app.state.data_paths)
    endpoint = f"/api/v2/evidence-processing-revisions/{seeded['revision_id']}/pages/{seeded['page_artifact_id']}/local-verification"
    candidate = _reading()
    candidate["items"][0]["proposed_bbox"] = {"x0": 0, "y0": 0, "x1": 1000, "y1": 1000}

    async def chat(prompt, pages, **kwargs):
        return IndependentVlmChatResult(text="source_ref=" + pages[0].source_ref + "\n" + json.dumps(candidate, ensure_ascii=False),
                                       model="fixture-model", finish_reason="stop", usage={})

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", chat)
    source = client.post(endpoint, json={"x0": 2, "y0": 3, "x1": 30, "y1": 40, "read_format": "localized_candidate"}).json()["job_id"]
    JobRunner(factory, client.app.state.job_executors).run_job(source)
    body = {"visual_job_id": source, "item_index": 0}
    created = client.post(endpoint + "/comparison", json=body)
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    assert client.get(endpoint).json()["job_id"] == source
    assert client.get(endpoint + "/comparison", params=body).json()["state"] == "queued"
    assert client.post(endpoint + "/comparison", json=body | {"verified": True}).status_code == 422

    def infer(request, image):
        text = candidate["items"][0]["excerpt"]
        raw = json.dumps({"model": request["model_id"], "choices": [{"finish_reason": "stop", "message": {"content": text}}]}).encode()
        return InferenceResult(raw, text)

    compare = create_local_comparison_executor(factory, artifacts, gate=Gate("GLM-OCR-bf16"), inference=infer)
    runner = JobRunner(factory, {LOCAL_VISUAL_JOB_TYPE: create_local_visual_executor(factory, artifacts, comparison_executor=compare)})
    assert runner.run_job(job_id)
    result = client.get(endpoint + "/comparison", params=body | {"job_id": job_id})
    assert result.status_code == 200 and result.json()["state"] == "completed"
    assert result.json()["outcome"]["item_index"] == 0
    assert not result.json()["outcome"]["source_position_verified"]
    assert not result.json()["formal_adoption_authorized"]
    assert client.get(endpoint + "/comparison", params=body | {"job_id": job_id, "item_index": 1}).status_code == 409
    assert client.get(endpoint).json()["job_id"] == source


@pytest.mark.parametrize("read_format", ["transcript", "structured_candidate"])
def test_product_region_entry_is_persisted_without_approving_page(client, read_format):
    factory = client.app.state.session_factory
    seeded = _seed(factory, client.app.state.data_paths)
    base = f"/api/v2/evidence-processing-revisions/{seeded['revision_id']}/pages/{seeded['page_artifact_id']}/local-verification"
    assert client.get(base).json()["found"] is False
    body = {"x0": 2, "y0": 3, "x1": 30, "y1": 40, "clockwise_degrees": 90, "read_format": read_format}
    response = client.post(base, json=body)
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert client.post(base, json=body).json()["job_id"] == job_id
    task = client.get(base).json()
    assert task["state"] == "queued" and task["observation_text"] is None
    assert task["candidate_only"] is True and task["coverage_scope"] == "region_only"
    assert LOCAL_VISUAL_JOB_TYPE in client.app.state.job_executors
    assert not SelectiveVisionPostprocessJobService(factory).get_revision_task(seeded["revision_id"]).found
    assert client.post(f"/api/v2/jobs/{job_id}/cancel").status_code == 200
    assert client.get(base).json()["state"] == "cancelled"
    assert client.post(base, json={**body, "x0": True}).status_code == 422
    assert client.post(base, json={**body, "x1": 61}).status_code == 409
    other = base.replace(seeded["page_artifact_id"], "other-page")
    assert client.post(other, json=body).status_code == 409


@pytest.mark.parametrize("mutation", [None, "structured_value", "length"])
def test_formal_api_readback_checks_the_saved_body_not_only_completed_status(client, monkeypatch, mutation):
    factory = client.app.state.session_factory
    artifacts = ArtifactStore(client.app.state.data_paths)
    seeded = _seed(factory, client.app.state.data_paths)
    base = f"/api/v2/evidence-processing-revisions/{seeded['revision_id']}/pages/{seeded['page_artifact_id']}/local-verification"
    body = {"x0": 1, "y0": 1, "x1": 30, "y1": 40, "read_format": "structured_candidate"}
    job_id = client.post(base, json=body).json()["job_id"]
    calls = []

    async def chat(prompt, pages, **kwargs):
        calls.append(1)
        return IndependentVlmChatResult(
            text="source_ref=" + pages[0].source_ref + "\n" + json.dumps(_reading(), ensure_ascii=False),
            model="fixture-model", finish_reason="stop", usage={},
        )

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", chat)
    assert JobRunner(factory, client.app.state.job_executors).run_job(job_id)
    with factory() as session:
        checkpoint_id, checkpoint = JobStore(session).get_last_checkpoint(job_id, LOCAL_VISUAL_STEP)
    original_ref = checkpoint["receipt_ref"]
    original_bytes = artifacts.read(original_ref)
    if mutation:
        receipt = json.loads(original_bytes)
        if mutation == "structured_value":
            receipt["structured_read"]["items"][0]["raw_value"] = "5.04"
        else:
            receipt["finish_reason"] = "length"
        checkpoint["receipt_ref"] = artifacts.put(
            "evaluation_manifest", json.dumps(receipt, ensure_ascii=False).encode(),
        ).storage_ref
        with factory() as session, session.begin():
            row = session.get(JobCheckpointRecord, checkpoint_id)
            row.payload_json, row.payload_sha256 = encode_value(checkpoint)
    result = client.get(base, params={"job_id": job_id})
    assert result.status_code == (409 if mutation else 200)
    if not mutation:
        assert result.json()["structured_read"] == _reading()
        assert result.json()["reading_region"] == body | {"clockwise_degrees": 0}
        assert result.json()["candidate_only"] and "尚未采用" in result.json()["observation_text"]
    else:
        assert "局部核实记录与原件不一致" in result.text
    assert artifacts.read(original_ref) == original_bytes and len(calls) == 1


@pytest.mark.parametrize("structured", [False, True])
def test_context_option_api_returns_the_requested_box_not_the_larger_reading_image(client, monkeypatch, structured):
    factory = client.app.state.session_factory
    artifacts = ArtifactStore(client.app.state.data_paths)
    seeded = _seed(factory, client.app.state.data_paths)
    base = f"/api/v2/evidence-processing-revisions/{seeded['revision_id']}/pages/{seeded['page_artifact_id']}/local-verification"
    body = {"x0": 20, "y0": 10, "x1": 40, "y1": 30, "clockwise_degrees": 0, "include_context": True}
    if structured:
        body["read_format"] = "localized_candidate"
    response = client.post(base, json=body)
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert client.get(base, params={"job_id": job_id}).json()["region"] == body

    async def chat(prompt, pages, **kwargs):
        assert "框外内容只供理解" in prompt
        candidate = _reading()
        candidate["items"][0]["proposed_bbox"] = {"x0": 300, "y0": 300, "x1": 700, "y1": 700}
        content = json.dumps(candidate, ensure_ascii=False) if structured else "可见圈定文字。"
        return IndependentVlmChatResult(text="source_ref=" + pages[0].source_ref + "\n" + content,
                                       model="fixture-model", finish_reason="stop", usage={})

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", chat)
    assert JobRunner(factory, client.app.state.job_executors).run_job(job_id)
    result = client.get(base, params={"job_id": job_id})
    assert result.status_code == 200 and result.json()["region"] == body
    assert result.json()["candidate_only"] and result.json()["coverage_scope"] == "region_only"
    if structured:
        assert result.json()["reading_region"] == {"x0": 16, "y0": 7, "x1": 44, "y1": 33,
                                                    "clockwise_degrees": 0, "read_format": "localized_candidate"}
        assert result.json()["structured_read"]["items"][0]["proposed_bbox"] == {"x0": 300, "y0": 300, "x1": 700, "y1": 700}
    with factory() as session:
        checkpoint = JobStore(session).get_last_checkpoint(job_id, LOCAL_VISUAL_STEP)[1]
    receipt = json.loads(artifacts.read(checkpoint["receipt_ref"]))
    assert receipt["region"]["view_bbox"] == {"x0": 16, "y0": 7, "x1": 44, "y1": 33}
    assert receipt["focus_bbox"] == {key: body[key] for key in ("x0", "y0", "x1", "y1")}
    assert client.post(base, json={**body, "include_context": "true"}).status_code == 422


def test_complete_revision_reads_the_original_page_without_impersonating_the_base(client, monkeypatch):
    from dataclasses import replace
    from app.services.local_visual_verification import create_local_visual_executor
    from app.workflow.runner import StepContext
    from app.workflow.errors import StepFailure
    from app.storage.ocr_models import EvidenceProcessingRevisionRecord

    factory = client.app.state.session_factory
    artifacts = ArtifactStore(client.app.state.data_paths)
    seeded = _seed_complete(factory, client.app.state.data_paths)
    endpoint = f"/api/v2/evidence-processing-revisions/{seeded['complete_revision_id']}/pages/{seeded['page_artifact_id']}/local-verification"
    assert client.get(endpoint).status_code == 200
    assert client.get(endpoint).json()["found"] is False
    body = {"x0": 20, "y0": 10, "x1": 40, "y1": 30, "include_context": True}
    queued = client.post(endpoint, json=body)
    assert queued.status_code == 202
    job_id = queued.json()["job_id"]
    calls = []

    async def chat(prompt, pages, **kwargs):
        calls.append(1)
        return IndependentVlmChatResult(text="source_ref=" + pages[0].source_ref + "\nSynthetic source text.",
                                       model="fixture-model", finish_reason="stop", usage={})

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", chat)
    assert JobRunner(factory, client.app.state.job_executors).run_job(job_id)
    result = client.get(endpoint, params={"job_id": job_id})
    assert result.status_code == 200 and result.json()["state"] == "completed"
    assert result.json()["region"] == {**body, "clockwise_degrees": 0}
    with factory() as session:
        payload = json.loads(JobStore(session).get_job(job_id).payload_json)
        checkpoint = JobStore(session).get_last_checkpoint(job_id, LOCAL_VISUAL_STEP)[1]
    saved = artifacts.read(checkpoint["receipt_ref"])
    receipt = json.loads(saved)
    assert receipt["base_processing_revision_id"] == seeded["revision_id"]
    assert receipt["requested_processing_revision_id"] == seeded["complete_revision_id"]
    context = StepContext(job_id, LOCAL_VISUAL_JOB_TYPE, payload, LOCAL_VISUAL_STEP, "Synthetic read", 1, "checkpoint", checkpoint)
    executor = create_local_visual_executor(factory, artifacts)
    assert executor(context) == checkpoint and len(calls) == 1
    assert client.post(endpoint.replace(seeded["page_artifact_id"], "foreign-page"), json=body).status_code == 409
    base_endpoint = endpoint.replace(seeded["complete_revision_id"], seeded["revision_id"])
    assert client.get(base_endpoint, params={"job_id": job_id}).status_code == 409
    with pytest.raises(StepFailure) as wrong_base:
        executor(replace(context, job_payload={**payload, "base_processing_revision_id": seeded["complete_revision_id"]}))
    assert wrong_base.value.error_code == "LOCAL_VISUAL_SOURCE_INVALID"

    # A valid receipt does not bypass a damaged frozen revision's closure.
    with factory() as session, session.begin():
        row = session.get(EvidenceProcessingRevisionRecord, seeded["complete_revision_id"])
        row.base_processing_revision_id = seeded["complete_revision_id"]
    assert client.get(endpoint).status_code == 500
    assert client.post(endpoint, json=body).status_code == 500
    with pytest.raises(StepFailure) as caught:
        executor(context)
    assert caught.value.error_code == "LOCAL_VISUAL_SOURCE_INVALID"
    assert len(calls) == 1 and artifacts.read(checkpoint["receipt_ref"]) == saved
