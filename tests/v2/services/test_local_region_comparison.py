"""The evaluation seam must compare actual same-region request/response bytes."""
import base64
from copy import deepcopy
import json

import pytest

from app.evidence.artifacts import ArtifactStore
from app.llm.independent_vlm import IndependentVlmChatResult
from app.services.local_region_comparison import evaluate_local_region_trial
from app.services.local_visual_verification import (
    LOCAL_VISUAL_JOB_TYPE, LOCAL_VISUAL_STEP, LocalVisualRegionRequest,
    LocalVisualVerificationService, create_local_visual_executor,
)
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner
from tests.v2.services.test_local_visual_job import _seed


def _put(store, data, kind="evaluation_manifest"):
    return store.put(kind, json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).storage_ref


@pytest.fixture
def frozen_trial(session_factory, data_paths, monkeypatch, request):
    seed = _seed(session_factory, data_paths)
    store = ArtifactStore(data_paths)
    service = LocalVisualVerificationService(session_factory, store)
    read_format = getattr(request, "param", "structured_candidate")
    job = service.enqueue(seed["revision_id"], seed["page_artifact_id"], LocalVisualRegionRequest(
        x0=1, y0=1, x1=30, y1=40, read_format=read_format,
    ))
    candidate = {"items": [{
        "label": "年龄", "raw_value": "50岁", "raw_unit": "岁", "reference_text": None,
        "time_label": None, "excerpt": "年龄：50岁", "position": "本区域一行",
        "script": "printed", "legibility": "clear", "annotation_target": None,
    }], "unresolved": []}
    if read_format == "localized_candidate":
        candidate["items"][0]["proposed_bbox"] = {"x0": 100, "y0": 100, "x1": 900, "y1": 900}

    async def chat(prompt, pages, **kwargs):
        return IndependentVlmChatResult(
            text="source_ref=" + pages[0].source_ref + "\n" + json.dumps(candidate, ensure_ascii=False),
            model="fixture-vision", finish_reason="stop", usage={},
        )

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", chat)
    runner = JobRunner(session_factory, {LOCAL_VISUAL_JOB_TYPE: create_local_visual_executor(session_factory, store)})
    assert runner.run_job(job["job_id"])
    with session_factory() as session:
        jobs = JobStore(session)
        checkpoint = jobs.get_last_checkpoint(job["job_id"], LOCAL_VISUAL_STEP)[1]
        payload_sha = jobs.get_job(job["job_id"]).payload_sha256
    visual = json.loads(store.read(checkpoint["receipt_ref"]))
    binding = visual["region"]
    image = store.read(visual["image_artifact_ref"])
    request = {"model_id": "fixture-ocr", "page": {"page_input_sha256": binding["region_image_sha256"]},
               "image": {"sha256": binding["region_image_sha256"], "data_base64": base64.b64encode(image).decode()}}
    response = {"model": "fixture-ocr", "choices": [{"finish_reason": "stop", "message": {"content": "年龄：50岁"}}]}
    before = {"revision_sha256": "a" * 64, "ocr_raw_text_sha256": visual["ocr_raw_text_sha256"],
              "source_image_sha256": binding["reading_view"]["source_image_sha256"]}
    if read_format == "localized_candidate":
        from app.domain.publication import canonical_hash
        from app.evidence.ocr_adapter import build_ocr_request_payload, DEFAULT_PROMPT, DEFAULT_REQUEST_PARAMS
        from app.storage.ocr_repositories import EvidenceProcessingRevisionRepository, OcrPageRepository, OCRProfileRepository

        with session_factory() as session:
            revision = EvidenceProcessingRevisionRepository(session).get(seed["revision_id"])
            ocr = OcrPageRepository(session).get(revision.manifest[0].ocr_page_id)
            profile = OCRProfileRepository(session).get_by_fingerprint(ocr.ocr_profile_sha256)
            before["revision_sha256"] = canonical_hash(revision.model_dump(mode="json"))
        request = build_ocr_request_payload(
            profile=profile, source_sha256=ocr.source_sha256, page_number=ocr.page_number,
            page_input_sha256=binding["region_image_sha256"], image_bytes=image,
            prompt=DEFAULT_PROMPT, request_params=DEFAULT_REQUEST_PARAMS,
        )
        response["model"] = profile.model_id
    trial = {"contract": "source-region-agreement-isolation/v1", "candidate_only": True,
             "formal_adoption_authorized": False, "source_and_clinical_state_unchanged": True,
             "before": before, "after": deepcopy(before), "source_region": binding,
             "image_ref": visual["image_artifact_ref"], "ocr_request_ref": _put(store, request, "raw_request"),
             "ocr": {"status": "read", "text": "年龄：50岁", "response_ref": _put(store, response, "raw_response")},
             "visual": {"state": "completed", "receipt_ref": checkpoint["receipt_ref"]},
             "visual_payload_sha256": payload_sha, "visual_job": {"job_id": job["job_id"]}}
    return store, trial, visual, request, response


def test_actual_job_receipt_and_ocr_bytes_enter_saved_comparison_not_fact_system(frozen_trial):
    store, trial, _, _, _ = frozen_trial
    ref = _put(store, trial)
    result = json.loads(store.read(evaluate_local_region_trial(store, ref).storage_ref))
    assert result["source_trial_ref"] == ref
    assert result["page_artifact_id"] == trial["source_region"]["reading_view"]["source_page_artifact_id"]
    assert result["items"][0]["status"] == "consistent_transcription_candidate"
    assert result["candidate_only"] and not result["formal_adoption_authorized"]
    assert not result["source_position_verified"]
    assert result["ocr_response_ref"] == trial["ocr"]["response_ref"]


@pytest.mark.parametrize("mutation", [
    "request_pixels", "request_hash", "ocr_model", "ocr_text", "ocr_length", "visual_pixels",
    "visual_region", "visual_ocr_parent", "visual_body", "visual_structured", "changed_state",
])
def test_same_words_do_not_bypass_source_or_receipt_mismatch(frozen_trial, mutation):
    store, trial, visual, request, response = frozen_trial
    if mutation == "request_pixels":
        request["image"]["data_base64"] = base64.b64encode(b"other pixels").decode()
    elif mutation == "request_hash":
        request["page"]["page_input_sha256"] = "b" * 64
    elif mutation == "ocr_model":
        response["model"] = "different-reader"
    elif mutation == "ocr_text":
        trial["ocr"]["text"] = "年龄：51岁"
    elif mutation == "ocr_length":
        response["choices"][0]["finish_reason"] = "length"
    elif mutation == "visual_pixels":
        visual["image_artifact_ref"] = store.put("reading_view_image", b"other pixels").storage_ref
    elif mutation == "visual_region":
        visual = deepcopy(visual)
        visual["region"]["view_bbox"]["x1"] += 1
    elif mutation == "visual_ocr_parent":
        visual["ocr_raw_text_sha256"] = "b" * 64
    elif mutation == "visual_body":
        visual["observation_text"] = visual["observation_text"].replace("50岁", "51岁")
    elif mutation == "visual_structured":
        visual["structured_read"]["items"][0]["raw_value"] = "51岁"
    elif mutation == "changed_state":
        trial["after"]["revision_sha256"] = "b" * 64
    trial["ocr_request_ref"] = _put(store, request, "raw_request")
    trial["ocr"]["response_ref"] = _put(store, response, "raw_response")
    trial["visual"]["receipt_ref"] = _put(store, visual)
    with pytest.raises(ValueError):
        evaluate_local_region_trial(store, _put(store, trial))


@pytest.mark.parametrize("frozen_trial", ["localized_candidate"], indirect=True)
@pytest.mark.parametrize("mutation", [None, "pixels", "model", "params", "length", "duplicate", "missing", "failed", "parent_prompt", "payload_hash"])
def test_localized_actual_job_to_subcrop_receipts_remains_isolated(frozen_trial, mutation, session_factory):
    from app.domain.contracts.evidence import BoundingBox
    from app.domain.contracts.local_region_read import LocalRegionRelativeBox
    from app.evidence.local_region_position_trial import proposed_field_bbox
    from app.evidence.reading_view import make_reading_region, make_reading_view
    from app.services.local_region_comparison import evaluate_localized_region_trial

    store, trial, visual, parent_request, _ = frozen_trial
    binding = trial["source_region"]
    source = binding["reading_view"]
    view = make_reading_view(store.read_by_sha("page_image", source["source_image_sha256"]),
                             source_page_artifact_id=source["source_page_artifact_id"],
                             source_image_sha256=source["source_image_sha256"], clockwise_degrees=0)
    box = LocalRegionRelativeBox.model_validate(visual["structured_read"]["items"][0]["proposed_bbox"])
    field = make_reading_region(view, proposed_field_bbox(BoundingBox.model_validate(binding["view_bbox"]), box))
    request = deepcopy(parent_request)
    request["page"]["page_input_sha256"] = field.identity()["region_image_sha256"]
    request["image"]["sha256"] = field.identity()["region_image_sha256"]
    request["image"]["data_base64"] = base64.b64encode(field.image_bytes).decode()
    response = {"model": request["model_id"], "choices": [{"finish_reason": "stop", "message": {"content": "年龄：50岁"}}]}
    if mutation == "pixels":
        request["image"]["data_base64"] = base64.b64encode(b"other pixels").decode()
    elif mutation == "model":
        response["model"] = "other-reader"
    elif mutation == "params":
        request["prompt"] = "supply the expected answer"
    elif mutation == "length":
        response["choices"][0]["finish_reason"] = "length"
    elif mutation == "parent_prompt":
        parent_request["prompt"] = request["prompt"] = "supply the expected answer"
        trial["ocr_request_ref"] = _put(store, parent_request, "raw_request")
    elif mutation == "payload_hash":
        trial["visual_payload_sha256"] = "b" * 64
    read = {"item_index": 0, "source_region": field.identity(),
            "image_ref": store.put("reading_view_image", field.image_bytes).storage_ref,
            "ocr_request_ref": _put(store, request, "raw_request"),
            "ocr": {"status": "failed" if mutation == "failed" else "read", "text": "年龄：50岁",
                    "response_ref": _put(store, response, "raw_response")}}
    reads = [] if mutation == "missing" else [read] * (2 if mutation == "duplicate" else 1)
    if mutation in {"pixels", "model", "params", "length", "duplicate", "parent_prompt", "payload_hash"}:
        with pytest.raises(ValueError):
            evaluate_localized_region_trial(store, _put(store, trial), reads, session_factory=session_factory)
    else:
        saved = json.loads(store.read(evaluate_localized_region_trial(store, _put(store, trial), reads, session_factory=session_factory).storage_ref))
        assert saved["items"][0]["single_field_transcription_agreement"] == (mutation is None)
        assert not saved["source_position_verified"] and not saved["formal_adoption_authorized"]
        assert saved["candidate_only"]
