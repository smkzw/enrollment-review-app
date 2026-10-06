"""Candidate-only parent/field comparison on the existing local reading Job.

Two bounded OCR steps retain their own receipts. Neither agreement nor the
completion of this job grants source-position or clinical adoption authority.
"""
from __future__ import annotations

import json
from contextlib import nullcontext

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from app.domain.contracts.evidence import BoundingBox
from app.domain.contracts.local_region_read import LocalRegionRelativeBox
from app.domain.publication import canonical_hash
from app.evidence.artifacts import ArtifactStoreError
from app.evidence.local_region_position_trial import POSITION_TRIAL_VERSION, proposed_field_bbox
from app.evidence.ocr_adapter import DEFAULT_PROMPT, DEFAULT_REQUEST_PARAMS, build_ocr_request_payload
from app.evidence.reading_view import make_reading_region, make_reading_view
from app.services.evidence_app_errors import AppScopeMismatchError, app_error_boundary
from app.services.job_service import JobService, StepSpec
from app.storage.codecs import verify_payload_sha256
from app.storage.models import JobRecord
from app.storage.ocr_repositories import EvidenceProcessingRevisionRepository, OCRProfileRepository, OcrPageRepository
from app.workflow.errors import StepFailure
from app.workflow.jobstore import JobStore

COMPARISON_CONTRACT = "local-visual-field-comparison-job/v1"
PARENT_STEP = "read_parent_text"
FIELD_STEP = "read_field_text"
COMPARE_STEP = "compare_field"


class LocalFieldComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    visual_job_id: str = Field(min_length=1)
    item_index: int = Field(ge=0)


def _put(artifacts, value, kind="evaluation_manifest"):
    return artifacts.put(kind, json.dumps(value, ensure_ascii=False, sort_keys=True,
                                         separators=(",", ":")).encode()).storage_ref


def _source(session, artifacts, revision_id, page_id, visual_job_id, index):
    from app.services.local_visual_verification import (
        LOCAL_VISUAL_CONTRACT, LOCAL_VISUAL_JOB_TYPE, LOCAL_VISUAL_STEP,
        LocalVisualVerificationService, _model_image_matches, _receipt_matches,
    )
    from app.storage.evidence_locator_repositories import CompleteEvidenceProcessingRevisionRepository

    page, base_id = LocalVisualVerificationService(None, artifacts)._page(session, revision_id, page_id)
    base = EvidenceProcessingRevisionRepository(session).get(base_id)
    revision = (base if base_id == revision_id else
                CompleteEvidenceProcessingRevisionRepository(session, artifacts).get(revision_id))
    job = JobStore(session).get_job(visual_job_id)
    payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
    checkpoint = JobStore(session).get_last_checkpoint(visual_job_id, LOCAL_VISUAL_STEP)
    if (job.job_type != LOCAL_VISUAL_JOB_TYPE or job.state != "completed"
            or payload.get("contract") != LOCAL_VISUAL_CONTRACT
            or payload.get("evidence_processing_revision_id") != revision_id
            or payload.get("base_processing_revision_id", revision_id) != base_id
            or payload.get("page_artifact_id") != page_id or checkpoint is None
            or checkpoint[1].get("status") != "read"):
        raise ValueError("须先完成当前页面的逐项位置读取")
    receipt_ref = checkpoint[1]["receipt_ref"]
    visual = json.loads(artifacts.read(receipt_ref))
    if (not _receipt_matches(payload, visual) or not _model_image_matches(visual, artifacts)
            or page.page_image_sha256 != payload["source_image_sha256"]
            or visual.get("read_format") != "localized_candidate"):
        raise ValueError("已保存的逐项读取与本页原件不能对应")
    items = visual["structured_read"]["items"]
    if type(index) is not int or not 0 <= index < len(items) or items[index]["proposed_bbox"] is None:
        raise ValueError("所选项目尚无明确位置")
    parent = BoundingBox.model_validate(visual["region"]["view_bbox"])
    field = proposed_field_bbox(parent, LocalRegionRelativeBox.model_validate(items[index]["proposed_bbox"]))
    focus = BoundingBox.model_validate(visual.get("focus_bbox", parent.model_dump(mode="json")))
    if not (focus.x0 <= field.x0 < field.x1 <= focus.x1 and focus.y0 <= field.y0 < field.y1 <= focus.y1):
        raise ValueError("项目位置超出本次核实范围")
    boxes = [proposed_field_bbox(parent, LocalRegionRelativeBox.model_validate(item["proposed_bbox"]))
             for item in items if item["proposed_bbox"] is not None]
    if boxes.count(field) != 1:
        raise ValueError("多个项目指向同一区域，须先核对项目归属")
    entries = [entry for entry in base.manifest if entry.page_artifact_id == page_id]
    if len(entries) != 1:
        raise ValueError("原始文字与页面不能唯一对应")
    ocr = OcrPageRepository(session).get(entries[0].ocr_page_id)
    if ocr.raw_text_sha256 != visual["ocr_raw_text_sha256"]:
        raise ValueError("原始文字已变化，须重新核实")
    profile = OCRProfileRepository(session).get_by_fingerprint(ocr.ocr_profile_sha256)
    binding = visual["region"]["reading_view"]
    view = make_reading_view(artifacts.read_by_sha("page_image", page.page_image_sha256),
                             source_page_artifact_id=page_id, source_image_sha256=page.page_image_sha256,
                             clockwise_degrees=binding["clockwise_degrees"])
    requests = {}
    regions = {}
    for name, box in ((PARENT_STEP, parent), (FIELD_STEP, field)):
        region = make_reading_region(view, box)
        regions[name] = region
        requests[name] = build_ocr_request_payload(
            profile=profile, source_sha256=ocr.source_sha256, page_number=ocr.page_number,
            page_input_sha256=region.identity()["region_image_sha256"], image_bytes=region.image_bytes,
            prompt=DEFAULT_PROMPT, request_params=DEFAULT_REQUEST_PARAMS,
        )
    before = {"revision_sha256": canonical_hash(revision.model_dump(mode="json")),
              "ocr_raw_text_sha256": ocr.raw_text_sha256, "source_image_sha256": page.page_image_sha256}
    if base_id != revision_id:
        before["base_revision_sha256"] = canonical_hash(base.model_dump(mode="json"))
    frozen = {"visual_payload_sha256": job.payload_sha256, "visual_receipt_ref": receipt_ref,
              "before": before, "request_hashes": {name: canonical_hash(value) for name, value in requests.items()}}
    from app.services.local_region_comparison import _require_localized_product_trial

    # Check the existing production prompt/profile contract before either new
    # read, not after spending two calls on an incompatible historical record.
    _require_localized_product_trial(
        lambda: nullcontext(session), artifacts,
        {"visual_job": {"job_id": visual_job_id}, "visual_payload_sha256": job.payload_sha256,
         "visual": {"receipt_ref": receipt_ref}, "before": before, "source_region": visual["region"],
         "image_ref": visual["image_artifact_ref"]}, visual, requests[PARENT_STEP],
    )
    return frozen, visual, requests, regions


def _route_identity():
    from app.config import OMLX_BASE_URL

    return canonical_hash({"endpoint": OMLX_BASE_URL, "comparison_version": POSITION_TRIAL_VERSION,
                           "equal_crop_reuse": "exact-request-and-pixels/v1"})


class LocalVisualComparisonService:
    def __init__(self, session_factory, artifacts):
        self.session_factory, self.artifacts = session_factory, artifacts

    @app_error_boundary
    def enqueue(self, revision_id, page_id, request: LocalFieldComparisonRequest):
        from app.services.local_visual_verification import LOCAL_VISUAL_JOB_TYPE

        with self.session_factory() as session, session.begin():
            try:
                frozen, _, _, _ = _source(session, self.artifacts, revision_id, page_id,
                                         request.visual_job_id, request.item_index)
            except (ValueError, KeyError, TypeError, ArtifactStoreError) as exc:
                raise AppScopeMismatchError("所选项目尚不能与本页完整读取对应，请重新核对原件。") from exc
            payload = {"contract": COMPARISON_CONTRACT, "evidence_processing_revision_id": revision_id,
                       "page_artifact_id": page_id, **request.model_dump(), **frozen,
                       "route_sha256": _route_identity()}
            # Cancelled attempts remain immutable; an explicit new request is a successor.
            seen = set()
            while True:
                result = JobService(self.session_factory).create_job_in_session(
                    session, idempotency_key=COMPARISON_CONTRACT + ":" + canonical_hash(payload),
                    job_type=LOCAL_VISUAL_JOB_TYPE, payload=payload,
                    steps=[StepSpec(PARENT_STEP, "核对周边项目文字", retryable=True),
                           StepSpec(FIELD_STEP, "核对所选项目文字", retryable=True, depends_on=(PARENT_STEP,)),
                           StepSpec(COMPARE_STEP, "保存项目核对依据", depends_on=(FIELD_STEP,))],
                )
                if result.job_id in seen:
                    raise AppScopeMismatchError("无法建立新的项目核对，原记录未改动。")
                seen.add(result.job_id)
                with_source_failure = (result.state == "failed_final"
                    and JobStore(session).get_job(result.job_id).error_code != "LOCAL_COMPARISON_READ_FAILED")
                if result.state != "cancelled" and not with_source_failure:
                    break
                payload = {**payload, "previous_job_id": result.job_id}
            return {"job_id": result.job_id, "state": result.state, "created": result.created}

    @app_error_boundary
    def latest(self, revision_id, page_id, visual_job_id, item_index, *, job_id=None):
        from app.services.local_visual_verification import LOCAL_VISUAL_JOB_TYPE

        with self.session_factory() as session:
            query = select(JobRecord).where(
                JobRecord.job_type == LOCAL_VISUAL_JOB_TYPE,
                func.json_extract(JobRecord.payload_json, "$.contract") == COMPARISON_CONTRACT,
                func.json_extract(JobRecord.payload_json, "$.evidence_processing_revision_id") == revision_id,
                func.json_extract(JobRecord.payload_json, "$.page_artifact_id") == page_id,
                func.json_extract(JobRecord.payload_json, "$.visual_job_id") == visual_job_id,
                func.json_extract(JobRecord.payload_json, "$.item_index") == item_index,
            )
            if job_id is not None:
                query = query.where(JobRecord.job_id == job_id)
            job = session.execute(query.order_by(JobRecord.created_at.desc(), JobRecord.job_id.desc()).limit(1)).scalar_one_or_none()
            if job is None:
                if job_id is not None:
                    raise AppScopeMismatchError("这次项目核对不属于当前页面。")
                return {"found": False, "candidate_only": True, "formal_adoption_authorized": False}
            payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
            try:
                frozen, _, requests, regions = _source(session, self.artifacts, revision_id, page_id, visual_job_id, item_index)
                if any(payload[key] != value for key, value in frozen.items()):
                    raise ValueError("来源已变化")
            except (ValueError, KeyError, TypeError, ArtifactStoreError) as exc:
                raise AppScopeMismatchError("项目核对的原件或资料版本已变化，不能作为当前核对结果。") from exc
            current = payload["route_sha256"] == _route_identity()
            response = {"found": True, "job_id": job.job_id, "state": job.state,
                        "candidate_only": True, "formal_adoption_authorized": False,
                        "configuration_current": current, "can_retry": current and job.state in {"failed_final", "failed_retryable"}
                        and job.error_code == "LOCAL_COMPARISON_READ_FAILED", "outcome": None}
            if job.state in {"failed_final", "failed_retryable"}:
                response["failure_message"] = "本次项目核对未完成，原件和原有结论未改动。"
            if job.state == "completed":
                checkpoint = JobStore(session).get_last_checkpoint(job.job_id, COMPARE_STEP)
                if checkpoint is None:
                    raise AppScopeMismatchError("项目核对缺少保存依据，不能显示为已完成。")
                saved = checkpoint[1]
                try:
                    trial = json.loads(self.artifacts.read(saved["trial_ref"]))
                    if (trial["visual_job"]["job_id"] != visual_job_id
                            or trial["visual_payload_sha256"] != frozen["visual_payload_sha256"]
                            or trial["visual"]["receipt_ref"] != frozen["visual_receipt_ref"]
                            or trial["before"] != frozen["before"] or len(saved["subreads"]) != 1
                            or saved["subreads"][0]["item_index"] != item_index):
                        raise ValueError("保存范围不符")
                    _validate_read(self.artifacts, {"ocr_request_ref": trial["ocr_request_ref"],
                                   "source_region": trial["source_region"], "image_ref": trial["image_ref"],
                                   "ocr": trial["ocr"]}, requests[PARENT_STEP], regions[PARENT_STEP])
                    _validate_read(self.artifacts, saved["subreads"][0], requests[FIELD_STEP], regions[FIELD_STEP])
                    expected = _evaluate(self.session_factory, self.artifacts, saved["trial_ref"], saved["subreads"])
                    if expected != saved["comparison_ref"]:
                        raise ValueError("保存对账不符")
                except (ValueError, KeyError, TypeError, ArtifactStoreError) as exc:
                    raise AppScopeMismatchError("项目核对结果与保存的实际回答不能对应。") from exc
                comparison = json.loads(self.artifacts.read(expected))
                response["outcome"] = comparison["items"][item_index]
            return response


def _evaluate(factory, artifacts, trial_ref, subreads):
    from app.services.local_region_comparison import evaluate_focused_localized_region_trial, evaluate_localized_region_trial

    trial = json.loads(artifacts.read(trial_ref))
    visual = json.loads(artifacts.read(trial["visual"]["receipt_ref"]))
    evaluator = evaluate_focused_localized_region_trial if visual.get("focus_bbox") else evaluate_localized_region_trial
    return evaluator(artifacts, trial_ref, subreads, session_factory=factory).storage_ref


def _validate_read(artifacts, read, request, region):
    from app.services.local_region_comparison import _subcrop_response_text

    if (json.loads(artifacts.read(read["ocr_request_ref"])) != request
            or read["source_region"] != region.identity()
            or artifacts.read(read["image_ref"]) != region.image_bytes
            or read["ocr"].get("status") != "read"):
        raise ValueError("已保存读取范围不符")
    _, failure = _subcrop_response_text(artifacts, read, request["model_id"])
    if failure is not None:
        raise ValueError("已保存读取不是完整返回")


def create_local_comparison_executor(factory, artifacts, *, gate=None, inference=None):
    from app.services.omlx_gate import OmlxGateClient, omlx_http_inference

    client = gate or OmlxGateClient()
    infer = inference or omlx_http_inference(gate=client)

    def execute(context):
        payload = context.job_payload
        try:
            if payload.get("contract") != COMPARISON_CONTRACT or context.step_id not in {PARENT_STEP, FIELD_STEP, COMPARE_STEP}:
                raise ValueError("核对格式不符")
            if payload.get("route_sha256") != _route_identity():
                raise ValueError("核对配置已变化")
            with factory() as session:
                frozen, visual, requests, regions = _source(
                    session, artifacts, payload["evidence_processing_revision_id"], payload["page_artifact_id"],
                    payload["visual_job_id"], payload["item_index"],
                )
                if any(payload[key] != value for key, value in frozen.items()):
                    raise ValueError("已冻结来源不符")
            if context.step_id == COMPARE_STEP:
                with factory() as session:
                    reads = [JobStore(session).get_last_checkpoint(context.job_id, step) for step in (PARENT_STEP, FIELD_STEP)]
                if any(read is None for read in reads):
                    raise ValueError("读取依据未完整保存")
                parent, field = [json.loads(artifacts.read(read[1]["read_ref"])) for read in reads]
                for name, read in ((PARENT_STEP, parent), (FIELD_STEP, field)):
                    _validate_read(artifacts, read, requests[name], regions[name])
                trial = {"contract": "source-region-agreement-isolation/v1", "candidate_only": True,
                         "formal_adoption_authorized": False, "source_and_clinical_state_unchanged": True,
                         "before": frozen["before"], "after": frozen["before"],
                         "source_region": parent["source_region"], "image_ref": parent["image_ref"],
                         "ocr_request_ref": parent["ocr_request_ref"], "ocr": parent["ocr"],
                         "visual": {"state": "completed", "receipt_ref": frozen["visual_receipt_ref"]},
                         "visual_payload_sha256": frozen["visual_payload_sha256"],
                         "visual_job": {"job_id": payload["visual_job_id"]}}
                trial_ref = _put(artifacts, trial)
                subreads = [{**field, "item_index": payload["item_index"]}]
                return {"trial_ref": trial_ref, "subreads": subreads,
                        "comparison_ref": _evaluate(factory, artifacts, trial_ref, subreads), "candidate_only": True}
        except (ValueError, KeyError, TypeError, ArtifactStoreError) as exc:
            raise StepFailure(retryable=False, error_code="LOCAL_COMPARISON_SOURCE_INVALID",
                              detail="本次项目核对与已保存来源不能对应，未采用读取结果。") from exc
        request, region = requests[context.step_id], regions[context.step_id]
        if context.last_checkpoint is not None and not context.last_checkpoint_is_diagnostic:
            try:
                _validate_read(artifacts, json.loads(artifacts.read(context.last_checkpoint["read_ref"])), request, region)
                return dict(context.last_checkpoint)
            except (ValueError, KeyError, TypeError, ArtifactStoreError) as exc:
                raise StepFailure(retryable=False, error_code="LOCAL_COMPARISON_RECEIPT_INVALID",
                                  detail="已保存读取无法核对，未重复读取或采用。") from exc
        if context.step_id == FIELD_STEP and requests[PARENT_STEP] == request:
            # The same crop/request is one reading, never an independent vote.
            with factory() as session:
                parent = JobStore(session).get_last_checkpoint(context.job_id, PARENT_STEP)
            try:
                if parent is None:
                    raise ValueError("周边读取尚无保存依据")
                _validate_read(artifacts, json.loads(artifacts.read(parent[1]["read_ref"])), request, region)
            except (ValueError, KeyError, TypeError, ArtifactStoreError) as exc:
                raise StepFailure(retryable=False, error_code="LOCAL_COMPARISON_RECEIPT_INVALID",
                                  detail="相同区域的保存读取无法核对，未重复读取或采用。") from exc
            return {"read_ref": parent[1]["read_ref"], "candidate_only": True,
                    "reused_from_step": PARENT_STEP, "reuse_basis": "exact-request-and-pixels/v1"}
        request_ref = _put(artifacts, request, "raw_request")
        image_ref = artifacts.put("reading_view_image", region.image_bytes).storage_ref
        try:
            if client.config().get("models", {}).get("ocr") != request["model_id"]:
                raise StepFailure(retryable=False, error_code="LOCAL_COMPARISON_CONFIG_INVALID",
                                  detail="文字核对配置与原始读取不一致，未另换模型。")
            # A crash before checkpoint commit can retain an orphan response;
            # only a committed successful read is replayable, not exactly-once IO.
            result, _ = client.run_under_lease(infer, request_payload=request, image_bytes=region.image_bytes)
            response_ref = artifacts.put("raw_response", result.raw_response).storage_ref
            parsed = json.loads(result.raw_response)
            choices = parsed.get("choices")
            if (parsed.get("model") != request["model_id"] or not isinstance(choices, list) or len(choices) != 1
                    or choices[0].get("finish_reason") != "stop"
                    or choices[0].get("message", {}).get("content") != result.recognized_text or not result.recognized_text.strip()):
                raise ValueError("文字核对未完整返回")
        except StepFailure:
            raise
        except Exception as exc:
            raw = getattr(exc, "raw_response", None)
            diagnostic = {"ocr_request_ref": request_ref, "image_ref": image_ref,
                          "source_region": region.identity(), "candidate_only": True}
            if raw is not None:
                diagnostic["response_ref"] = artifacts.put("raw_response", raw).storage_ref
            elif "response_ref" in locals():
                diagnostic["response_ref"] = response_ref
            raise StepFailure(retryable=True, error_code="LOCAL_COMPARISON_READ_FAILED",
                              detail="此区域文字核对未完成，原件和原有结论未改动。",
                              diagnostic_checkpoint=diagnostic) from exc
        read = {"source_region": region.identity(), "image_ref": image_ref, "ocr_request_ref": request_ref,
                "ocr": {"status": "read", "text": result.recognized_text, "response_ref": response_ref}}
        return {"read_ref": _put(artifacts, read), "candidate_only": True}

    return execute
