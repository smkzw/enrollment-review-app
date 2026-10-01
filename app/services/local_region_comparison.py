"""Evaluate frozen isolated reads without modifying evidence or clinical state."""
from __future__ import annotations

import base64
from copy import deepcopy
from hashlib import sha256
import json

from app.domain.contracts.evidence import BoundingBox
from app.domain.contracts.local_region_read import LocalizedRegionReadCandidate, parse_local_region_read
from app.domain.publication import canonical_hash
from app.evidence.artifacts import ArtifactStore, StoredArtifact
from app.evidence.local_region_comparison import compare_local_region_read
from app.evidence.local_region_position_trial import POSITION_TRIAL_VERSION, compare_single_field_subcrop, proposed_field_bbox
from app.evidence.reading_view import make_reading_region, make_reading_view


def evaluate_local_region_trial(artifacts: ArtifactStore, trial_ref: str) -> StoredArtifact:
    trial = json.loads(artifacts.read(trial_ref))
    if (trial.get("contract") != "source-region-agreement-isolation/v1"
            or trial.get("formal_adoption_authorized") is not False
            or trial.get("candidate_only") is not True
            or trial.get("source_and_clinical_state_unchanged") is not True
            or trial.get("before") != trial.get("after")
            or trial["ocr"].get("status") != "read"
            or trial["visual"].get("state") != "completed"):
        raise ValueError("本次隔离读取尚无完整且未改变原资料的回执")
    binding = trial["source_region"]
    view_binding = binding["reading_view"]
    view = make_reading_view(
        artifacts.read_by_sha("page_image", view_binding["source_image_sha256"]),
        source_page_artifact_id=view_binding["source_page_artifact_id"],
        source_image_sha256=view_binding["source_image_sha256"],
        clockwise_degrees=view_binding["clockwise_degrees"],
    )
    region = make_reading_region(view, BoundingBox.model_validate(binding["view_bbox"]))
    if (region.identity() != binding
            or artifacts.read(trial["image_ref"]) != region.image_bytes):
        raise ValueError("隔离读取的裁区与原图无法对应")
    request = json.loads(artifacts.read(trial["ocr_request_ref"]))
    raw_ocr = json.loads(artifacts.read(trial["ocr"]["response_ref"]))
    if (request["page"]["page_input_sha256"] != binding["region_image_sha256"]
            or request["image"]["sha256"] != binding["region_image_sha256"]
            or base64.b64decode(request["image"]["data_base64"], validate=True) != region.image_bytes
            or raw_ocr.get("model") != request["model_id"]):
        raise ValueError("文字主读的实际请求与本次裁区不一致")
    choice = raw_ocr["choices"][0]
    ocr_text = choice["message"]["content"]
    if (choice.get("finish_reason") != "stop" or not isinstance(ocr_text, str)
            or not ocr_text.strip() or ocr_text != trial["ocr"]["text"]):
        raise ValueError("文字主读不是本次完整返回的原文")
    visual_ref = trial["visual"]["receipt_ref"]
    visual = json.loads(artifacts.read(visual_ref))
    if (visual.get("status") != "read" or visual.get("finish_reason") != "stop"
            or visual.get("read_format") not in {"structured_candidate", "localized_candidate"}
            or visual.get("candidate_only") is not True
            or visual.get("coverage_scope") != "region_only"
            or visual.get("region") != binding
            or visual.get("page_artifact_id") != view_binding["source_page_artifact_id"]
            or artifacts.read(visual["image_artifact_ref"]) != region.image_bytes
            or visual.get("ocr_raw_text_sha256") != trial["before"]["ocr_raw_text_sha256"]
            or trial["before"]["source_image_sha256"] != view_binding["source_image_sha256"]
            or not visual.get("base_processing_revision_id")):
        raise ValueError("视觉读取回执与本次资料裁区不能对应")
    candidate = parse_local_region_read(
        visual["observation_text"], source_ref="region:" + canonical_hash(binding),
        read_format=visual["read_format"],
    )
    if candidate.model_dump(mode="json") != visual.get("structured_read"):
        raise ValueError("保存的逐项读取与模型实际正文不一致")
    result = compare_local_region_read(ocr_text, candidate)
    result.update({
        "source_trial_ref": trial_ref, "source_region": binding,
        "evidence_processing_revision_id": visual["base_processing_revision_id"],
        "page_artifact_id": visual["page_artifact_id"],
        "source_document_version_id": visual["source_document_version_id"],
        "base_revision_sha256": trial["before"]["revision_sha256"],
        "ocr_request_ref": trial["ocr_request_ref"],
        "ocr_response_ref": trial["ocr"]["response_ref"],
        "ocr_text_sha256": sha256(ocr_text.encode()).hexdigest(),
        "visual_receipt_ref": visual_ref,
        "visual_prompt_sha256": visual["prompt_sha256"],
        "visual_job_payload_sha256": trial["visual_payload_sha256"],
    })
    return artifacts.put("evaluation_manifest", json.dumps(
        result, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode())


def evaluate_localized_region_trial(artifacts: ArtifactStore, trial_ref: str, subreads: list[dict], *, session_factory) -> StoredArtifact:
    """Check actual pixels and raw OCR receipts, not caller-supplied approval flags."""
    base_ref = evaluate_local_region_trial(artifacts, trial_ref)
    base = json.loads(artifacts.read(base_ref.storage_ref))
    trial = json.loads(artifacts.read(trial_ref))
    visual = json.loads(artifacts.read(base["visual_receipt_ref"]))
    if visual["read_format"] != "localized_candidate":
        raise ValueError("此次读取没有逐项位置提案")
    candidate = LocalizedRegionReadCandidate.model_validate(visual["structured_read"])
    binding = base["source_region"]
    view_binding = binding["reading_view"]
    view = make_reading_view(
        artifacts.read_by_sha("page_image", view_binding["source_image_sha256"]),
        source_page_artifact_id=view_binding["source_page_artifact_id"],
        source_image_sha256=view_binding["source_image_sha256"],
        clockwise_degrees=view_binding["clockwise_degrees"],
    )
    parent = BoundingBox.model_validate(binding["view_bbox"])
    parent_request = json.loads(artifacts.read(base["ocr_request_ref"]))
    _require_localized_product_trial(session_factory, artifacts, trial, visual, parent_request)
    by_index = {}
    for read in subreads:
        index = read.get("item_index")
        if type(index) is not int or not 0 <= index < len(candidate.items) or index in by_index:
            raise ValueError("裁区读取的项目编号重复或超出本次提案")
        by_index[index] = read
    outcomes = []
    for index, item in enumerate(candidate.items):
        read = by_index.get(index)
        if item.proposed_bbox is None or read is None:
            outcomes.append({"item_index": index, "status": "unresolved", "candidate_only": True,
                             "source_position_verified": False, "single_field_transcription_agreement": False,
                             "reasons": ["位置未明确或尚无该位置的独立文字读取"]})
            continue
        region = make_reading_region(view, proposed_field_bbox(parent, item.proposed_bbox))
        request = json.loads(artifacts.read(read["ocr_request_ref"]))
        expected_request = deepcopy(parent_request)
        expected_request["page"]["page_input_sha256"] = region.identity()["region_image_sha256"]
        expected_request["image"]["sha256"] = region.identity()["region_image_sha256"]
        expected_request["image"]["data_base64"] = base64.b64encode(region.image_bytes).decode("ascii")
        if (region.identity() != read["source_region"]
                or artifacts.read(read["image_ref"]) != region.image_bytes
                or request != expected_request
                or request["page"]["page_input_sha256"] != region.identity()["region_image_sha256"]
                or request["image"]["sha256"] != region.identity()["region_image_sha256"]
                or base64.b64decode(request["image"]["data_base64"], validate=True) != region.image_bytes):
            raise ValueError("项目裁区的实际文字请求与原图位置不一致")
        if read["ocr"].get("status") != "read":
            outcomes.append({"item_index": index, "status": "unresolved", "candidate_only": True,
                             "source_position_verified": False, "single_field_transcription_agreement": False,
                             "reasons": ["此处文字读取未完成，不能以模型位置提案替代核实"]})
            continue
        raw = json.loads(artifacts.read(read["ocr"]["response_ref"]))
        choice = raw["choices"][0]
        text = choice["message"]["content"]
        if (raw.get("model") != request["model_id"] or choice.get("finish_reason") != "stop"
                or not isinstance(text, str) or not text.strip() or text != read["ocr"]["text"]):
            raise ValueError("项目裁区文字不是本次完整模型原答")
        outcome = compare_single_field_subcrop(text, candidate, index)
        original = base["items"][index]
        if original["status"] != "consistent_transcription_candidate":
            outcome.update({"status": "unresolved", "single_field_transcription_agreement": False})
            outcome["reasons"].append("原始两次读取仍有不一致或未清楚的内容")
        outcome.update({"reconstructed_subcrop_bytes_match_request": True,
                        "proposal_covers_entire_parent": region.view_bbox == parent,
                        "source_region": region.identity(),
                        "ocr_request_ref": read["ocr_request_ref"],
                        "ocr_response_ref": read["ocr"]["response_ref"]})
        outcomes.append(outcome)
    return artifacts.put("evaluation_manifest", json.dumps({
        "contract": POSITION_TRIAL_VERSION, "candidate_only": True,
        "formal_adoption_authorized": False, "source_position_verified": False,
        "source_trial_ref": trial_ref, "base_comparison_ref": base_ref.storage_ref,
        "items": outcomes, "unresolved": base["unresolved"], "unmatched_ocr": base["unmatched_ocr"],
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def _require_localized_product_trial(session_factory, artifacts, trial, visual, parent_request):
    from app.evidence.ocr_adapter import build_ocr_request_payload, DEFAULT_PROMPT, DEFAULT_REQUEST_PARAMS
    from app.services.local_visual_verification import LOCAL_VISUAL_JOB_TYPE, LOCAL_VISUAL_STEP, _receipt_matches
    from app.services.selective_vision_observation_service import local_visual_prompts, local_visual_prompt_identity
    from app.storage.codecs import verify_payload_sha256
    from app.storage.ocr_repositories import EvidenceProcessingRevisionRepository, OcrPageRepository, OCRProfileRepository
    from app.workflow.jobstore import JobStore

    with session_factory() as session:
        store = JobStore(session)
        job = store.get_job(trial["visual_job"]["job_id"])
        payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
        checkpoint = store.get_last_checkpoint(job.job_id, LOCAL_VISUAL_STEP)
        if (job.job_type != LOCAL_VISUAL_JOB_TYPE or job.state != "completed"
                or job.payload_sha256 != trial["visual_payload_sha256"] or checkpoint is None
                or checkpoint[1].get("status") != "read"
                or checkpoint[1].get("receipt_ref") != trial["visual"]["receipt_ref"]
                or not _receipt_matches(payload, visual)):
            raise ValueError("位置试验不是本系统已保存的完整局部读取")
        revision = EvidenceProcessingRevisionRepository(session).get(payload["evidence_processing_revision_id"])
        entries = [entry for entry in revision.manifest if entry.page_artifact_id == payload["page_artifact_id"]]
        if len(entries) != 1 or canonical_hash(revision.model_dump(mode="json")) != trial["before"]["revision_sha256"]:
            raise ValueError("位置试验的资料版本与本次任务不一致")
        ocr = OcrPageRepository(session).get(entries[0].ocr_page_id)
        profile = OCRProfileRepository(session).get_by_fingerprint(ocr.ocr_profile_sha256)
        if ocr.raw_text_sha256 != trial["before"]["ocr_raw_text_sha256"]:
            raise ValueError("原始文字已变化，本次位置试验须重新核对")
        expected_request = build_ocr_request_payload(
            profile=profile, source_sha256=ocr.source_sha256, page_number=ocr.page_number,
            page_input_sha256=trial["source_region"]["region_image_sha256"],
            image_bytes=artifacts.read(trial["image_ref"]), prompt=DEFAULT_PROMPT, request_params=DEFAULT_REQUEST_PARAMS,
        )
    system, prompt = local_visual_prompts(visual["region_source_ref"], "localized_candidate")
    if (parent_request != expected_request or visual.get("prompt") != prompt
            or visual.get("system_prompt") != system
            or visual.get("prompt_sha256") != local_visual_prompt_identity("localized_candidate")):
        raise ValueError("位置试验的实际提示或读取配置不属于当前产品入口")
