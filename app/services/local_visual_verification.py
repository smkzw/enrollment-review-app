"""Source-bound region reading on the existing Job/ArtifactStore infrastructure.

This task never publishes observations, reviews OCR risks or activates evidence.
"""
from __future__ import annotations

import asyncio
import io
import json
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from PIL import Image

from app.domain.contracts.evidence import BoundingBox
from app.domain.contracts.local_region_read import LocalReadFormat, local_region_read_model, parse_local_region_read, render_local_region_read
from app.domain.publication import canonical_hash
from app.evidence.artifacts import ArtifactStore, ArtifactStoreError
from app.services.evidence_app_errors import AppScopeMismatchError, app_error_boundary
from app.services.job_service import JobService, StepSpec
from app.services.selective_vision_observation_service import (
    SelectiveVisionObservationService, local_visual_focus_coordinates, local_visual_prompt_identity,
)
from app.services.selective_vision_postprocess_executor import load_selective_vision_page_materials_for_revision
from app.services.selective_vision_runtime import selective_vision_route_sha256
from app.storage.codecs import verify_payload_sha256
from app.storage.models import JobRecord
from app.storage.ocr_repositories import EvidenceProcessingRevisionRepository, PageArtifactRepository
from app.storage.evidence_locator_repositories import CompleteEvidenceProcessingRevisionRepository
from app.storage.ocr_models import EvidenceProcessingRevisionRecord
from app.workflow.errors import StepFailure
from app.workflow.jobstore import JobStore

LOCAL_VISUAL_JOB_TYPE = "local_visual_verification"
LOCAL_VISUAL_STEP = "read_region"
LOCAL_VISUAL_CONTRACT = "local-visual-verification-job/v1"


def _receipt_matches(payload: dict, receipt: dict) -> bool:
    if (not isinstance(payload, dict) or not isinstance(receipt, dict)
            or not {"evidence_processing_revision_id", "page_artifact_id", "source_image_sha256", "prompt_sha256", "region"} <= payload.keys()
            or not isinstance(payload["region"], dict)
            or not {"x0", "y0", "x1", "y1", "clockwise_degrees"} <= payload["region"].keys()):
        return False
    region = receipt.get("region", {})
    if not isinstance(region, dict) or not isinstance(region.get("reading_view", {}), dict):
        return False
    view = region.get("reading_view", {})
    return (
        receipt.get("status") == "read" and receipt.get("candidate_only") is True
        and receipt.get("coverage_scope") == "region_only"
        and receipt.get("base_processing_revision_id") == payload.get("base_processing_revision_id", payload["evidence_processing_revision_id"])
        and receipt.get("requested_processing_revision_id") == (
            payload["evidence_processing_revision_id"] if "base_processing_revision_id" in payload else None
        )
        and receipt.get("page_artifact_id") == payload["page_artifact_id"]
        and receipt.get("prompt_sha256") == payload["prompt_sha256"]
        and receipt.get("read_format", "transcript") == payload["region"].get("read_format", "transcript")
        and view.get("source_page_artifact_id") == payload["page_artifact_id"]
        and view.get("source_image_sha256") == payload["source_image_sha256"]
        and view.get("clockwise_degrees") == payload["region"]["clockwise_degrees"]
        and region.get("view_bbox") == {key: payload["region"][key] for key in ("x0", "y0", "x1", "y1")}
        and receipt.get("focus_bbox") == payload.get("focus_bbox")
        and _payload_scope_matches(payload)
        and _read_contents_match(receipt, payload["region"].get("read_format", "transcript"))
    )


def _read_contents_match(receipt: dict, read_format: LocalReadFormat) -> bool:
    """Validate saved reading contents, never clinical accuracy or adoption."""
    from app.llm.independent_vlm import IndependentVlmSourceFidelityError, assert_source_locator_fidelity

    text = receipt.get("observation_text")
    if receipt.get("finish_reason") != "stop" or not isinstance(text, str):
        return False
    region_ref = "region:" + canonical_hash(receipt["region"])
    lines = text.strip().splitlines()
    if (receipt.get("region_source_ref") != region_ref or not lines
            or lines[0].strip() != "source_ref=" + region_ref
            or not any(line.strip() for line in lines[1:])):
        return False
    try:
        assert_source_locator_fidelity(text, [region_ref], require_claim=True)
        coordinates = None
        if receipt.get("focus_bbox") is not None:
            from app.services.selective_vision_observation_service import local_visual_prompts

            coordinates = local_visual_focus_coordinates(
                BoundingBox.model_validate(receipt["region"]["view_bbox"]),
                BoundingBox.model_validate(receipt["focus_bbox"]),
            )
            system, prompt = local_visual_prompts(region_ref, read_format, focus_coordinates=coordinates)
            if receipt.get("prompt") != prompt or receipt.get("system_prompt") != system:
                return False
        if read_format in {"structured_candidate", "localized_candidate"}:
            candidate = parse_local_region_read(text, source_ref=region_ref, read_format=read_format)
            if coordinates is not None:
                from app.domain.contracts.local_region_read import LocalRegionRelativeBox, require_localized_focus_scope

                require_localized_focus_scope(candidate, LocalRegionRelativeBox.model_validate(coordinates))
            return candidate.model_dump(mode="json") == receipt.get("structured_read")
        return read_format == "transcript" and "structured_read" not in receipt
    except (ValueError, TypeError, KeyError, IndependentVlmSourceFidelityError):
        return False


class LocalVisualRegionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    x0: int = Field(ge=0)
    y0: int = Field(ge=0)
    x1: int = Field(gt=0)
    y1: int = Field(gt=0)
    clockwise_degrees: Literal[0, 90, 180, 270] = 0
    read_format: LocalReadFormat = "transcript"
    include_context: bool = False

    @model_validator(mode="after")
    def require_area(self):
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("核实区域必须有明确面积")
        return self

    def bbox(self) -> BoundingBox:
        return BoundingBox(x0=self.x0, y0=self.y0, x1=self.x1, y1=self.y1)


def _payload_scope_matches(payload: dict) -> bool:
    try:
        context = LocalVisualRegionRequest.model_validate(payload["region"])
        focus = payload.get("focus_bbox")
        requested = payload.get("requested_region")
        if focus is None:
            return requested is None and not context.include_context
        original = LocalVisualRegionRequest.model_validate(requested)
        return (
            original.include_context and not context.include_context
            and original.clockwise_degrees == context.clockwise_degrees
            and original.read_format == context.read_format
            and original.bbox() == BoundingBox.model_validate(focus)
            and bool(local_visual_focus_coordinates(context.bbox(), original.bbox()))
        )
    except (ValueError, TypeError, KeyError):
        return False


def _payload_prompt_identity(payload: dict) -> str:
    focus = payload.get("focus_bbox")
    coordinates = local_visual_focus_coordinates(
        LocalVisualRegionRequest.model_validate(payload["region"]).bbox(), BoundingBox.model_validate(focus),
    ) if focus is not None else None
    read_format = payload["region"].get("read_format", "transcript")
    return (local_visual_prompt_identity(read_format) if coordinates is None
            else local_visual_prompt_identity(read_format, focus_coordinates=coordinates))


class LocalVisualVerificationService:
    def __init__(self, session_factory, artifact_store: ArtifactStore):
        self.session_factory = session_factory
        self.artifact_store = artifact_store
        self.jobs = JobService(session_factory)

    def _page(self, session, revision_id: str, page_id: str):
        record = session.get(EvidenceProcessingRevisionRecord, revision_id)
        if record is not None and record.revision_kind == "complete":
            revision = CompleteEvidenceProcessingRevisionRepository(session, self.artifact_store).get(revision_id)
            base_id = revision.base_processing_revision_id
        else:
            revision = EvidenceProcessingRevisionRepository(session).get(revision_id)
            base_id = revision_id
        if not any(entry.page_artifact_id == page_id for entry in revision.manifest):
            raise AppScopeMismatchError("所选页面不属于当前资料版本。")
        return PageArtifactRepository(session).get(page_id), base_id

    @app_error_boundary
    def enqueue(self, revision_id: str, page_id: str, region: LocalVisualRegionRequest) -> dict:
        with self.session_factory() as session, session.begin():
            page, base_id = self._page(session, revision_id, page_id)
            if not page.page_image_sha256:
                raise AppScopeMismatchError("这一页尚无可核实的原图。")
            image_bytes = self.artifact_store.read_by_sha("page_image", page.page_image_sha256)
            if sha256(image_bytes).hexdigest() != page.page_image_sha256:
                raise AppScopeMismatchError("原图与当前页面身份不一致。")
            with Image.open(io.BytesIO(image_bytes)) as image:
                width, height = image.size
            if region.clockwise_degrees in (90, 270):
                width, height = height, width
            if region.x1 > width or region.y1 > height:
                raise AppScopeMismatchError("所选核实区域超出原图。")
            excluded = {"include_context"}
            if region.read_format == "transcript":
                excluded.add("read_format")
            reading_region = region.model_dump(mode="json", exclude=excluded)
            focus = None
            if region.include_context:
                # A geometric margin supplies nearby labels; it is not extra
                # evidence coverage or a disease-specific reading heuristic.
                from math import ceil

                dx, dy = ceil(width * 0.05), ceil(height * 0.05)
                reading_region.update(x0=max(0, region.x0 - dx), y0=max(0, region.y0 - dy),
                                      x1=min(width, region.x1 + dx), y1=min(height, region.y1 + dy))
                focus = region.bbox().model_dump(mode="json")
            payload = {
                "contract": LOCAL_VISUAL_CONTRACT,
                "evidence_processing_revision_id": revision_id,
                "page_artifact_id": page_id,
                "source_image_sha256": page.page_image_sha256,
                "region": reading_region,
                "route_sha256": selective_vision_route_sha256(),
            }
            if base_id != revision_id:
                payload["base_processing_revision_id"] = base_id
            if focus is not None:
                payload["focus_bbox"] = focus
                payload["requested_region"] = region.model_dump(mode="json", exclude=excluded - {"include_context"})
            payload["prompt_sha256"] = _payload_prompt_identity(payload)
            # Explicit rereads after cancellation or a missing saved reading get
            # successors; old terminal jobs and source regions remain unchanged.
            seen_job_ids = set()
            while True:
                result = self.jobs.create_job_in_session(
                    session, idempotency_key=LOCAL_VISUAL_JOB_TYPE + ":" + canonical_hash(payload),
                    job_type=LOCAL_VISUAL_JOB_TYPE, payload=payload,
                    steps=[StepSpec(step_id=LOCAL_VISUAL_STEP, name="核实原件局部", max_attempts=1, retryable=True)],
                )
                if result.job_id in seen_job_ids:
                    raise AppScopeMismatchError("无法建立独立的重读任务，原读取记录未改动。")
                seen_job_ids.add(result.job_id)
                missing_record = result.state == "completed" and JobStore(session).get_last_checkpoint(result.job_id, LOCAL_VISUAL_STEP) is None
                if result.state != "cancelled" and not missing_record:
                    break
                payload = {**payload, "previous_job_id": result.job_id}
                if missing_record:
                    payload["recovery_reason"] = "completed_read_record_missing"
            return {"job_id": result.job_id, "state": result.state, "created": result.created}

    @app_error_boundary
    def latest(self, revision_id: str, page_id: str, *, job_id: str | None = None) -> dict:
        with self.session_factory() as session:
            page, base_id = self._page(session, revision_id, page_id)
            query = select(JobRecord).where(
                JobRecord.job_type == LOCAL_VISUAL_JOB_TYPE,
                func.json_extract(JobRecord.payload_json, "$.evidence_processing_revision_id") == revision_id,
                func.json_extract(JobRecord.payload_json, "$.page_artifact_id") == page_id,
            )
            if job_id is not None:
                query = query.where(JobRecord.job_id == job_id)
            jobs = session.execute(query.order_by(JobRecord.created_at.desc(), JobRecord.job_id.desc()).limit(1)).scalars()
            for job in jobs:
                payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
                if (payload.get("evidence_processing_revision_id") != revision_id
                        or payload.get("page_artifact_id") != page_id):
                    continue
                if not _payload_scope_matches(payload):
                    raise AppScopeMismatchError("局部核实的圈选范围与周边图片不一致。")
                if payload.get("base_processing_revision_id", revision_id) != base_id:
                    raise AppScopeMismatchError("局部核实记录与资料版本的原件来源不一致。")
                checkpoint = JobStore(session).get_last_checkpoint(job.job_id, LOCAL_VISUAL_STEP)
                configuration_current = (
                    payload.get("route_sha256") == selective_vision_route_sha256()
                    and payload.get("prompt_sha256") == _payload_prompt_identity(payload)
                )
                result = {
                    "found": True, "job_id": job.job_id, "state": job.state,
                    "region": payload.get("requested_region", payload["region"]), "observation_text": None,
                    "candidate_only": True, "coverage_scope": "region_only",
                    "configuration_current": configuration_current,
                    "can_retry": configuration_current and job.state in {"failed_final", "failed_retryable"}
                        and job.error_code not in {"LOCAL_VISUAL_SOURCE_INVALID", "LOCAL_VISUAL_RECEIPT_INVALID", "LOCAL_VISUAL_CONTRACT_INVALID", "LOCAL_VISUAL_ROUTE_CHANGED"},
                }
                if job.state == "completed" and checkpoint is None:
                    raise AppScopeMismatchError("这次读取缺少保存记录，不能展示为已完成核实，请重新圈选或核对原件。")
                # Failed and cancelled tasks retain their receipts, not an accepted reading.
                if job.state == "completed" and checkpoint is not None:
                    receipt = json.loads(self.artifact_store.read(checkpoint[1]["receipt_ref"]))
                    if (not _receipt_matches(payload, receipt)
                            or page.page_image_sha256 != payload["source_image_sha256"]):
                        raise AppScopeMismatchError("局部核实记录与原件不一致。")
                    lines = receipt["observation_text"].splitlines()
                    result["observation_text"] = "\n".join(
                        line for line in lines if not line.strip().startswith("source_ref=")
                    ).strip()
                    read_format = payload["region"].get("read_format", "transcript")
                    if read_format in {"structured_candidate", "localized_candidate"}:
                        candidate = local_region_read_model(read_format).model_validate(receipt["structured_read"])
                        result["structured_read"] = candidate.model_dump(mode="json")
                        # Relative proposals belong to the actual reading image,
                        # not the narrower requested focus or the whole page.
                        result["reading_region"] = payload["region"]
                        result["observation_text"] = render_local_region_read(candidate)
                return result
            if job_id is not None:
                raise AppScopeMismatchError("这次局部读取不属于当前资料页。")
        return {"found": False, "candidate_only": True, "coverage_scope": "region_only"}


def create_local_visual_executor(session_factory, artifact_store: ArtifactStore, *, service=None):
    reader = service or SelectiveVisionObservationService(session_factory)

    def execute(context):
        payload = context.job_payload
        if context.step_id != LOCAL_VISUAL_STEP or payload.get("contract") != LOCAL_VISUAL_CONTRACT:
            raise StepFailure(retryable=False, error_code="LOCAL_VISUAL_CONTRACT_INVALID",
                              detail="这次局部核实任务格式无法确认。")
        if not _payload_scope_matches(payload):
            raise StepFailure(retryable=False, error_code="LOCAL_VISUAL_CONTRACT_INVALID",
                              detail="圈选范围与周边图片不能对应，未进行读取。")
        if (payload.get("route_sha256") != selective_vision_route_sha256()
                or payload.get("prompt_sha256") != _payload_prompt_identity(payload)):
            raise StepFailure(retryable=False, error_code="LOCAL_VISUAL_ROUTE_CHANGED",
                              detail="模型配置已变化，请重新圈选区域发起核实。")
        try:
            region = LocalVisualRegionRequest.model_validate(payload["region"])
            with session_factory() as session:
                _, base_id = LocalVisualVerificationService(session_factory, artifact_store)._page(
                    session, payload["evidence_processing_revision_id"], payload["page_artifact_id"],
                )
                if base_id != payload.get("base_processing_revision_id", payload["evidence_processing_revision_id"]):
                    raise ValueError("所选资料版本与原件来源不一致")
                pages = load_selective_vision_page_materials_for_revision(
                    session, evidence_processing_revision_id=base_id,
                    artifact_store=artifact_store, page_artifact_ids={payload["page_artifact_id"]},
                )
            if len(pages) != 1 or pages[0].page_image_sha256 != payload["source_image_sha256"]:
                raise ValueError("原始页图身份不符")
        except Exception as exc:
            raise StepFailure(retryable=False, error_code="LOCAL_VISUAL_SOURCE_INVALID",
                              detail="所选区域与资料原件无法核对，未进行读取。") from exc
        checkpoint = context.last_checkpoint
        if checkpoint is not None and checkpoint.get("status") == "read":
            try:
                saved = json.loads(artifact_store.read(checkpoint["receipt_ref"]))
            except (ArtifactStoreError, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                raise StepFailure(retryable=False, error_code="LOCAL_VISUAL_RECEIPT_INVALID",
                                  detail="已保存的局部读取无法核对，未重新读取原件。") from exc
            if _receipt_matches(payload, saved):
                return dict(checkpoint)
            raise StepFailure(retryable=False, error_code="LOCAL_VISUAL_RECEIPT_INVALID",
                              detail="已保存的局部读取与本次来源范围不符。")
        # Only a committed successful checkpoint is replayable. A crash between
        # model return and checkpoint commit may retain an orphan receipt and
        # require another call; do not promise exactly-once remote execution.
        try:
            receipt = asyncio.run(reader.verify_local_region(
                pages[0], base_processing_revision_id=base_id,
                view_bbox=region.bbox(), clockwise_degrees=region.clockwise_degrees,
                artifact_store=artifact_store,
                **({"read_format": region.read_format} if region.read_format != "transcript" else {}),
                **({"focus_bbox": BoundingBox.model_validate(payload["focus_bbox"])} if "focus_bbox" in payload else {}),
                **({"requested_processing_revision_id": payload["evidence_processing_revision_id"]} if "base_processing_revision_id" in payload else {}),
            ))
        except Exception as exc:
            raise StepFailure(retryable=True, error_code="LOCAL_VISUAL_READ_FAILED",
                              detail="本次局部核实未完成，原件和原有核对结果不变。") from exc
        try:
            result = json.loads(artifact_store.read(receipt.storage_ref))
            if not isinstance(result, dict) or "status" not in result:
                raise ValueError("读取记录格式不完整")
        except (ArtifactStoreError, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            raise StepFailure(retryable=False, error_code="LOCAL_VISUAL_RECEIPT_INVALID",
                              detail="本次读取的保存记录无法核对，未采用或重复读取。") from exc
        checkpoint = {"receipt_ref": receipt.storage_ref, "candidate_only": True,
                      "coverage_scope": "region_only", "status": result["status"]}
        if result["status"] != "read":
            raise StepFailure(retryable=True, error_code="LOCAL_VISUAL_RESPONSE_UNVERIFIED",
                              detail="本次局部读取未通过完整性核对，请重试或直接核对原件。",
                              diagnostic_checkpoint=checkpoint)
        if not _receipt_matches(payload, result):
            raise StepFailure(retryable=False, error_code="LOCAL_VISUAL_RECEIPT_INVALID",
                              detail="本次局部读取与原件范围不能对应，未采用读取结果。",
                              diagnostic_checkpoint=checkpoint)
        return checkpoint

    return execute
