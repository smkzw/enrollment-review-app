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
from tests.v2.services.test_local_visual_job import _seed, _seed_complete


def _put(store, data, kind="evaluation_manifest"):
    return store.put(kind, json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).storage_ref


@pytest.fixture
def frozen_trial(session_factory, data_paths, monkeypatch, request):
    option = getattr(request, "param", "structured_candidate")
    options = option if isinstance(option, dict) else {"read_format": option}
    seed = (_seed_complete if options.get("complete") else _seed)(
        session_factory, data_paths, raw_text=options.get("raw_text"),
    )
    store = ArtifactStore(data_paths)
    service = LocalVisualVerificationService(session_factory, store)
    read_format = options["read_format"]
    selected_id = seed["complete_revision_id"] if options.get("complete") else seed["revision_id"]
    job = service.enqueue(selected_id, seed["page_artifact_id"], LocalVisualRegionRequest(
        x0=1, y0=1, x1=30, y1=40, read_format=read_format, include_context=bool(options.get("focus")),
    ))
    if options.get("legacy_focus"):
        from app.services.local_visual_verification import _payload_prompt_identity
        from app.storage.codecs import encode_value

        with session_factory() as session, session.begin():
            row = JobStore(session).get_job(job["job_id"])
            payload = json.loads(row.payload_json)
            payload.pop("model_image_policy")
            payload["prompt_sha256"] = _payload_prompt_identity(payload)
            row.payload_json, row.payload_sha256 = encode_value(payload)
    candidate = {"items": [{
        "label": "年龄", "raw_value": "50岁", "raw_unit": "岁", "reference_text": None,
        "time_label": None, "excerpt": "年龄：50岁", "position": "本区域一行",
        "script": "printed", "legibility": "clear", "annotation_target": None,
    }], "unresolved": []}
    if options.get("plain_row"):
        row = "1 CODE ★示例项目 4.04 3.50--9.50 10^9/L"
        candidate["items"][0].update(label="示例项目", raw_value="4.04", raw_unit="10^9/L",
                                   reference_text="3.50--9.50", excerpt=row)
    if read_format == "localized_candidate":
        edge = 100 if not options.get("focus") or options.get("outside_focus") else 200
        candidate["items"][0]["proposed_bbox"] = {"x0": edge, "y0": edge, "x1": 1000 - edge, "y1": 1000 - edge}
        if options.get("whole_region"):
            candidate["items"][0]["proposed_bbox"] = {"x0": 0, "y0": 0, "x1": 1000, "y1": 1000}
    if options.get("two_items"):
        sibling = deepcopy(candidate["items"][0])
        sibling.update(label="体温", raw_value="37℃", raw_unit=None, excerpt="体温：37℃")
        candidate["items"].append(sibling)
        if not options.get("same_field_region"):
            candidate["items"][0]["proposed_bbox"]["x1"] = 450
            sibling["proposed_bbox"]["x0"] = 550
    parent_text = "\n".join(item["excerpt"] for item in candidate["items"])
    if options.get("plain_row"):
        parent_text = "No. 代号 名称 结果 参考范围 单位\n" + parent_text
        if options.get("grouped_row"):
            parent_text = ("No. 代号 名称 结果 参考范围 单位 No. 代号 名称 结果 参考范围\n"
                           + candidate["items"][0]["excerpt"] + " 2 B 另一项目 2 1--3 mg/L")
        if options.get("wrong_plain_value"):
            parent_text = parent_text.replace("4.04", "4.05")

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
    response = {"model": "fixture-ocr", "choices": [{"finish_reason": "stop", "message": {"content": parent_text}}]}
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
            if options.get("complete"):
                from app.storage.evidence_locator_repositories import CompleteEvidenceProcessingRevisionRepository

                complete = CompleteEvidenceProcessingRevisionRepository(session, store).get(selected_id)
                before["base_revision_sha256"] = before["revision_sha256"]
                before["revision_sha256"] = canonical_hash(complete.model_dump(mode="json"))
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
             "ocr": {"status": "read", "text": parent_text, "response_ref": _put(store, response, "raw_response")},
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


def test_context_image_is_not_same_scope_agreement(frozen_trial):
    store, trial, visual, _, _ = frozen_trial
    visual["focus_bbox"] = {"x0": 2, "y0": 2, "x1": 20, "y1": 30}
    trial["visual"]["receipt_ref"] = _put(store, visual)
    with pytest.raises(ValueError, match="目标和上下文"):
        evaluate_local_region_trial(store, _put(store, trial))


@pytest.mark.parametrize("value,expected", [("<p>50</p>", "consistent_transcription_candidate"),
                                           ("5<br>0", "unresolved")])
def test_actual_saved_ocr_response_preserves_table_blocks(frozen_trial, value, expected):
    store, trial, _, _, response = frozen_trial
    text = ("<table><tr><td>项目</td><td>结果</td><td>参考范围</td><td>单位</td></tr>"
            f"<tr><td>年龄</td><td>{value}</td><td></td><td>岁</td></tr></table>")
    response["choices"][0]["message"]["content"] = text
    trial["ocr"].update(text=text, response_ref=_put(store, response, "raw_response"))
    ref = _put(store, trial)
    original = store.read(ref)
    result = json.loads(store.read(evaluate_local_region_trial(store, ref).storage_ref))
    assert result["contract"] == "local-region-transcript-comparison/v7"
    assert result["items"][0]["status"] == expected
    assert bool(result["unresolved"]) == (expected == "unresolved")
    assert not result["formal_adoption_authorized"] and not result["source_position_verified"]
    assert store.read(ref) == original


@pytest.mark.parametrize("frozen_trial,expected", [
    ({"read_format": "structured_candidate", "plain_row": True}, "consistent_transcription_candidate"),
    ({"read_format": "structured_candidate", "plain_row": True, "wrong_plain_value": True}, "unresolved"),
    ({"read_format": "structured_candidate", "plain_row": True, "grouped_row": True}, "consistent_transcription_candidate"),
    ({"read_format": "structured_candidate", "plain_row": True, "grouped_row": True, "wrong_plain_value": True}, "unresolved"),
], indirect=["frozen_trial"])
def test_plain_columns_through_real_job_save_and_comparison_consumer(frozen_trial, expected):
    store, trial, _, _, _ = frozen_trial
    source_ref = _put(store, trial)
    original = store.read(source_ref)
    result = json.loads(store.read(evaluate_local_region_trial(store, source_ref).storage_ref))
    assert result["contract"] == "local-region-transcript-comparison/v7"
    assert result["items"][0]["status"] == expected
    assert result["source_trial_ref"] == source_ref and store.read(source_ref) == original
    assert result["candidate_only"] and not result["formal_adoption_authorized"]
    assert not result["source_position_verified"]
    if "另一项目" in trial["ocr"]["text"]:
        assert result["unresolved"] and "另一项目" in result["unresolved"][0]


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


@pytest.mark.parametrize("frozen_trial", [
    "localized_candidate",
    {"read_format": "localized_candidate", "complete": True},
    {"read_format": "localized_candidate", "focus": True},
    {"read_format": "localized_candidate", "focus": True, "complete": True},
    {"read_format": "localized_candidate", "focus": True, "legacy_focus": True},
], indirect=True)
@pytest.mark.parametrize("mutation", [None, "pixels", "model", "params", "length", "duplicate", "missing", "failed", "parent_prompt", "payload_hash"])
def test_localized_actual_job_to_subcrop_receipts_remains_isolated(frozen_trial, mutation, session_factory):
    from app.domain.contracts.evidence import BoundingBox
    from app.domain.contracts.local_region_read import LocalRegionRelativeBox
    from app.evidence.local_region_position_trial import proposed_field_bbox
    from app.evidence.reading_view import make_reading_region, make_reading_view
    from app.services.local_region_comparison import evaluate_localized_region_trial, evaluate_focused_localized_region_trial

    store, trial, visual, parent_request, _ = frozen_trial
    evaluate = evaluate_focused_localized_region_trial if visual.get("focus_bbox") is not None else evaluate_localized_region_trial
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
    if mutation in {"pixels", "model", "params", "duplicate", "parent_prompt", "payload_hash"}:
        with pytest.raises(ValueError):
            evaluate(store, _put(store, trial), reads, session_factory=session_factory)
    else:
        saved = json.loads(store.read(evaluate(store, _put(store, trial), reads, session_factory=session_factory).storage_ref))
        assert saved["items"][0]["single_field_transcription_agreement"] == (mutation is None)
        assert not saved["source_position_verified"] and not saved["formal_adoption_authorized"]
        assert saved["candidate_only"]
        assert saved["read_failure_item_indexes"] == ([0] if mutation in {"length", "failed"} else [])
        if visual.get("focus_bbox") is not None:
            assert saved["coverage_scope"] == "focus_only" and saved["context_scope"] == "association_only"
            assert saved["focus_bbox"] == visual["focus_bbox"]
        if visual.get("requested_processing_revision_id") is not None:
            base = json.loads(store.read(saved["base_comparison_ref"]))
            assert base["evidence_processing_revision_id"] == visual["requested_processing_revision_id"]
            assert base["base_processing_revision_id"] == visual["base_processing_revision_id"]
            assert base["base_revision_sha256"] == trial["before"]["base_revision_sha256"]
            assert base["evidence_revision_sha256"] == trial["before"]["revision_sha256"]


@pytest.mark.parametrize("frozen_trial", [
    {"read_format": "localized_candidate", "focus": True},
], indirect=True)
@pytest.mark.parametrize("damage", ["missing", "changed"])
def test_marked_model_pixels_are_required_even_when_job_and_text_match(
    frozen_trial, session_factory, monkeypatch, damage,
):
    from app.evidence.artifacts import ArtifactStoreError
    from app.evidence.reading_view import FOCUS_READING_IMAGE_VERSION
    from app.services.local_region_comparison import evaluate_focused_localized_region_trial

    store, trial, visual, _, _ = frozen_trial
    assert visual["model_image_policy"] == FOCUS_READING_IMAGE_VERSION
    original_read = store.read

    def read(ref):
        if ref == visual["model_image_artifact_ref"]:
            if damage == "missing":
                raise ArtifactStoreError("missing model image")
            return original_read(visual["image_artifact_ref"])
        return original_read(ref)

    monkeypatch.setattr(store, "read", read)
    with pytest.raises(ValueError, match="完整局部读取"):
        evaluate_focused_localized_region_trial(
            store, _put(store, trial), [], session_factory=session_factory,
        )


@pytest.mark.parametrize("frozen_trial", [
    {"read_format": "localized_candidate", "focus": True},
], indirect=True)
def test_focused_trial_does_not_enter_old_whole_region_consumer(frozen_trial, session_factory):
    from app.services.local_region_comparison import evaluate_localized_region_trial

    store, trial, _, _, _ = frozen_trial
    ref = _put(store, trial)
    original = store.read(ref)
    with pytest.raises(ValueError, match="目标和上下文"):
        evaluate_localized_region_trial(store, ref, [], session_factory=session_factory)
    assert store.read(ref) == original


@pytest.mark.parametrize("frozen_trial", [
    {"read_format": "localized_candidate", "focus": True, "outside_focus": True},
], indirect=True)
def test_position_proposal_crossing_focus_boundary_stays_unresolved(frozen_trial, session_factory):
    from app.services.local_region_comparison import evaluate_focused_localized_region_trial

    store, trial, _, _, _ = frozen_trial
    saved = json.loads(store.read(evaluate_focused_localized_region_trial(
        store, _put(store, trial), [{"item_index": 0}], session_factory=session_factory,
    ).storage_ref))
    assert saved["items"][0]["status"] == "unresolved"
    assert not saved["items"][0]["single_field_transcription_agreement"]
    assert "圈选目标之外" in saved["items"][0]["reasons"][0]
    assert not saved["source_position_verified"] and not saved["formal_adoption_authorized"]


@pytest.mark.parametrize("frozen_trial", [
    {"read_format": "localized_candidate", "complete": True},
], indirect=True)
@pytest.mark.parametrize("mutation", ["selected_hash", "base_hash", "missing_base_hash", "damaged_complete"])
def test_complete_trial_requires_both_real_revision_identities(frozen_trial, session_factory, mutation):
    from app.services.local_region_comparison import evaluate_localized_region_trial
    from app.storage.codecs import PersistedContractInvalid
    from app.storage.ocr_models import EvidenceProcessingRevisionRecord

    store, trial, visual, _, _ = frozen_trial
    if mutation == "selected_hash":
        trial["before"]["revision_sha256"] = "b" * 64
    elif mutation == "base_hash":
        trial["before"]["base_revision_sha256"] = "b" * 64
    elif mutation == "missing_base_hash":
        trial["before"].pop("base_revision_sha256")
    else:
        with session_factory() as session, session.begin():
            row = session.get(EvidenceProcessingRevisionRecord, visual["requested_processing_revision_id"])
            row.base_processing_revision_id = visual["requested_processing_revision_id"]
    trial["after"] = deepcopy(trial["before"])
    expected_error = PersistedContractInvalid if mutation == "damaged_complete" else ValueError
    with pytest.raises(expected_error):
        evaluate_localized_region_trial(store, _put(store, trial), [], session_factory=session_factory)


@pytest.mark.parametrize("frozen_trial", [{
    "read_format": "localized_candidate", "focus": True, "complete": True, "two_items": True,
}], indirect=True)
@pytest.mark.parametrize("failure,code", [
    ("length", "LOCAL_SUBCROP_RESPONSE_INCOMPLETE"),
    ("content_filter", "LOCAL_SUBCROP_RESPONSE_INCOMPLETE"),
    ("empty", "LOCAL_SUBCROP_RESPONSE_EMPTY"),
    ("message", "LOCAL_SUBCROP_RESPONSE_INVALID"),
    ("choices", "LOCAL_SUBCROP_RESPONSE_INVALID"),
    ("array", "LOCAL_SUBCROP_RESPONSE_INVALID"),
    ("invalid_json", "LOCAL_SUBCROP_RESPONSE_INVALID"),
    ("failed", "LOCAL_SUBCROP_READ_FAILED"),
])
def test_failed_subread_saves_successful_sibling_and_recovers_without_rereading_parent(
    frozen_trial, session_factory, monkeypatch, failure, code,
):
    from app.domain.contracts.evidence import BoundingBox
    from app.domain.contracts.local_region_read import LocalRegionRelativeBox
    from app.evidence.local_region_position_trial import proposed_field_bbox
    from app.evidence.reading_view import make_reading_region, make_reading_view
    from app.services.local_region_comparison import evaluate_focused_localized_region_trial

    store, trial, visual, parent_request, _ = frozen_trial
    source = trial["source_region"]["reading_view"]
    view = make_reading_view(
        store.read_by_sha("page_image", source["source_image_sha256"]),
        source_page_artifact_id=source["source_page_artifact_id"],
        source_image_sha256=source["source_image_sha256"], clockwise_degrees=0,
    )
    reads = []
    for index, item in enumerate(visual["structured_read"]["items"]):
        field = make_reading_region(view, proposed_field_bbox(
            BoundingBox.model_validate(trial["source_region"]["view_bbox"]),
            LocalRegionRelativeBox.model_validate(item["proposed_bbox"]),
        ))
        request = deepcopy(parent_request)
        request["page"]["page_input_sha256"] = field.identity()["region_image_sha256"]
        request["image"].update(sha256=field.identity()["region_image_sha256"],
                                data_base64=base64.b64encode(field.image_bytes).decode())
        response = {"model": request["model_id"], "choices": [{
            "finish_reason": "stop", "message": {"content": item["excerpt"]},
        }]}
        reads.append({
            "item_index": index, "source_region": field.identity(),
            "image_ref": store.put("reading_view_image", field.image_bytes).storage_ref,
            "ocr_request_ref": _put(store, request, "raw_request"),
            "ocr": {"status": "read", "text": item["excerpt"],
                    "response_ref": _put(store, response, "raw_response")},
        })
    complete_reads = deepcopy(reads)
    bad = json.loads(store.read(reads[0]["ocr"]["response_ref"]))
    if failure in {"length", "content_filter"}:
        bad["choices"][0]["finish_reason"] = failure
    elif failure == "empty":
        bad["choices"][0]["message"]["content"] = ""
    elif failure == "message":
        bad["choices"][0]["message"] = []
    elif failure == "choices":
        bad["choices"] = []
    elif failure == "array":
        bad = []
    elif failure == "failed":
        reads[0]["ocr"]["status"] = "failed"
    reads[0]["ocr"]["response_ref"] = (
        store.put("raw_response", b"{broken").storage_ref if failure == "invalid_json"
        else _put(store, bad, "raw_response")
    )
    def forbidden_call(*args, **kwargs):
        raise AssertionError("saved comparison must not invoke a model")
    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", forbidden_call)
    trial_ref = _put(store, trial)
    original_trial = store.read(trial_ref)
    result_ref = evaluate_focused_localized_region_trial(
        store, trial_ref, reads, session_factory=session_factory,
    ).storage_ref
    original_result = store.read(result_ref)
    result = json.loads(original_result)
    assert result["contract"] == "local-region-focused-position-trial/v3"
    assert result["read_failure_item_indexes"] == [0]
    assert result["items"][0]["status"] == "read_failure"
    assert result["items"][0]["failure_kind"] == code
    assert result["items"][0]["ocr_response_ref"] == reads[0]["ocr"]["response_ref"]
    assert not result["items"][0]["single_field_transcription_agreement"]
    assert result["items"][1]["single_field_transcription_agreement"]
    recovered = json.loads(store.read(evaluate_focused_localized_region_trial(
        store, trial_ref, complete_reads, session_factory=session_factory,
    ).storage_ref))
    assert recovered["read_failure_item_indexes"] == []
    assert recovered["items"][1] == result["items"][1]
    assert all(item["single_field_transcription_agreement"] for item in recovered["items"])
    assert not recovered["source_position_verified"] and not recovered["formal_adoption_authorized"]
    assert store.read(result_ref) == original_result
    assert store.read(trial_ref) == original_trial


@pytest.mark.parametrize("frozen_trial", [{
    "read_format": "localized_candidate", "focus": True, "complete": True,
    "two_items": True, "same_field_region": True,
}], indirect=True)
def test_same_actual_pixel_crop_cannot_prove_two_different_fields(frozen_trial, session_factory):
    from app.services.local_region_comparison import evaluate_focused_localized_region_trial

    store, trial, _, _, _ = frozen_trial
    saved = json.loads(store.read(evaluate_focused_localized_region_trial(
        store, _put(store, trial), [{"item_index": 0}, {"item_index": 1}],
        session_factory=session_factory,
    ).storage_ref))
    assert saved["read_failure_item_indexes"] == []
    assert len(saved["items"]) == 2
    for item in saved["items"]:
        assert item["status"] == "unresolved"
        assert not item["single_field_transcription_agreement"]
        assert "同一像素裁区" in item["reasons"][0]
    assert not saved["source_position_verified"] and not saved["formal_adoption_authorized"]
