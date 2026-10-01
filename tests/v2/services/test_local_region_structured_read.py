"""Typed region results remain proposals and preserve failure/replay boundaries."""
import json

import pytest

from app.domain.contracts.local_region_read import parse_local_region_read
from app.evidence.artifacts import ArtifactStore
from app.llm.independent_vlm import IndependentVlmChatResult
from app.services.job_service import JobService
from app.services.local_visual_verification import (
    LOCAL_VISUAL_JOB_TYPE, LOCAL_VISUAL_STEP, LocalVisualRegionRequest,
    LocalVisualVerificationService, create_local_visual_executor,
)
from app.storage.selective_vision_observation_repository import SelectiveVisionObservationRepository
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner
from tests.v2.services.test_local_visual_job import _seed


def _reading():
    return {"items": [{
        "label": "示例测量", "raw_value": "4.04", "raw_unit": "10⁹/L",
        "reference_text": "3.50—9.50", "time_label": None,
        "excerpt": "示例测量 4.04 3.50—9.50 10⁹/L", "position": "本区域第一行",
        "script": "printed", "legibility": "clear", "annotation_target": None,
    }], "unresolved": ["区域边缘有裁切，其他项目无法确认。"]}


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
