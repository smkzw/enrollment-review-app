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
from app.domain.contracts.local_region_read import LocalReadFormat, local_region_read_model, render_local_region_read
from app.domain.publication import canonical_hash
from app.evidence.artifacts import ArtifactStore
from app.services.evidence_app_errors import AppScopeMismatchError, app_error_boundary
from app.services.job_service import JobService, StepSpec
from app.services.selective_vision_observation_service import (
    SelectiveVisionObservationService, local_visual_prompt_identity,
)
from app.services.selective_vision_postprocess_executor import load_selective_vision_page_materials_for_revision
from app.services.selective_vision_runtime import selective_vision_route_sha256
from app.storage.codecs import verify_payload_sha256
from app.storage.models import JobRecord
from app.storage.ocr_repositories import EvidenceProcessingRevisionRepository, PageArtifactRepository
from app.workflow.errors import StepFailure
from app.workflow.jobstore import JobStore

LOCAL_VISUAL_JOB_TYPE = "local_visual_verification"
LOCAL_VISUAL_STEP = "read_region"
LOCAL_VISUAL_CONTRACT = "local-visual-verification-job/v1"


def _receipt_matches(payload: dict, receipt: dict) -> bool:
    region = receipt.get("region", {})
    view = region.get("reading_view", {})
    return (
        receipt.get("status") == "read" and receipt.get("candidate_only") is True
        and receipt.get("coverage_scope") == "region_only"
        and receipt.get("base_processing_revision_id") == payload["evidence_processing_revision_id"]
        and receipt.get("page_artifact_id") == payload["page_artifact_id"]
        and receipt.get("prompt_sha256") == payload["prompt_sha256"]
        and receipt.get("read_format", "transcript") == payload["region"].get("read_format", "transcript")
        and view.get("source_page_artifact_id") == payload["page_artifact_id"]
        and view.get("source_image_sha256") == payload["source_image_sha256"]
        and view.get("clockwise_degrees") == payload["region"]["clockwise_degrees"]
        and region.get("view_bbox") == {key: payload["region"][key] for key in ("x0", "y0", "x1", "y1")}
    )


class LocalVisualRegionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    x0: int = Field(ge=0)
    y0: int = Field(ge=0)
    x1: int = Field(gt=0)
    y1: int = Field(gt=0)
    clockwise_degrees: Literal[0, 90, 180, 270] = 0
    read_format: LocalReadFormat = "transcript"

    @model_validator(mode="after")
    def require_area(self):
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("核实区域必须有明确面积")
        return self

    def bbox(self) -> BoundingBox:
        return BoundingBox(x0=self.x0, y0=self.y0, x1=self.x1, y1=self.y1)


class LocalVisualVerificationService:
    def __init__(self, session_factory, artifact_store: ArtifactStore):
        self.session_factory = session_factory
        self.artifact_store = artifact_store
        self.jobs = JobService(session_factory)

    def _page(self, session, revision_id: str, page_id: str):
        revision = EvidenceProcessingRevisionRepository(session).get(revision_id)
        if not any(entry.page_artifact_id == page_id for entry in revision.manifest):
            raise AppScopeMismatchError("所选页面不属于当前资料版本。")
        return PageArtifactRepository(session).get(page_id)

    @app_error_boundary
    def enqueue(self, revision_id: str, page_id: str, region: LocalVisualRegionRequest) -> dict:
        with self.session_factory() as session, session.begin():
            page = self._page(session, revision_id, page_id)
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
            payload = {
                "contract": LOCAL_VISUAL_CONTRACT,
                "evidence_processing_revision_id": revision_id,
                "page_artifact_id": page_id,
                "source_image_sha256": page.page_image_sha256,
                "region": region.model_dump(mode="json", exclude={"read_format"} if region.read_format == "transcript" else set()),
                "route_sha256": selective_vision_route_sha256(),
                "prompt_sha256": local_visual_prompt_identity(region.read_format),
            }
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
            page = self._page(session, revision_id, page_id)
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
                checkpoint = JobStore(session).get_last_checkpoint(job.job_id, LOCAL_VISUAL_STEP)
                configuration_current = (
                    payload.get("route_sha256") == selective_vision_route_sha256()
                    and payload.get("prompt_sha256") == local_visual_prompt_identity(payload["region"].get("read_format", "transcript"))
                )
                result = {
                    "found": True, "job_id": job.job_id, "state": job.state,
                    "region": payload["region"], "observation_text": None,
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
        if (payload.get("route_sha256") != selective_vision_route_sha256()
                or payload.get("prompt_sha256") != local_visual_prompt_identity(payload["region"].get("read_format", "transcript"))):
            raise StepFailure(retryable=False, error_code="LOCAL_VISUAL_ROUTE_CHANGED",
                              detail="模型配置已变化，请重新圈选区域发起核实。")
        checkpoint = context.last_checkpoint
        if checkpoint is not None and checkpoint.get("status") == "read":
            saved = json.loads(artifact_store.read(checkpoint["receipt_ref"]))
            if _receipt_matches(payload, saved):
                return dict(checkpoint)
            raise StepFailure(retryable=False, error_code="LOCAL_VISUAL_RECEIPT_INVALID",
                              detail="已保存的局部读取与本次来源范围不符。")
        try:
            region = LocalVisualRegionRequest.model_validate(payload["region"])
            with session_factory() as session:
                pages = load_selective_vision_page_materials_for_revision(
                    session, evidence_processing_revision_id=payload["evidence_processing_revision_id"],
                    artifact_store=artifact_store, page_artifact_ids={payload["page_artifact_id"]},
                )
            if len(pages) != 1 or pages[0].page_image_sha256 != payload["source_image_sha256"]:
                raise ValueError("原始页图身份不符")
        except Exception as exc:
            raise StepFailure(retryable=False, error_code="LOCAL_VISUAL_SOURCE_INVALID",
                              detail="所选区域与资料原件无法核对，未进行读取。") from exc
        # Only a committed successful checkpoint is replayable. A crash between
        # model return and checkpoint commit may retain an orphan receipt and
        # require another call; do not promise exactly-once remote execution.
        try:
            receipt = asyncio.run(reader.verify_local_region(
                pages[0], base_processing_revision_id=payload["evidence_processing_revision_id"],
                view_bbox=region.bbox(), clockwise_degrees=region.clockwise_degrees,
                artifact_store=artifact_store,
                **({"read_format": region.read_format} if region.read_format != "transcript" else {}),
            ))
            result = json.loads(artifact_store.read(receipt.storage_ref))
        except Exception as exc:
            raise StepFailure(retryable=True, error_code="LOCAL_VISUAL_READ_FAILED",
                              detail="本次局部核实未完成，原件和原有核对结果不变。") from exc
        checkpoint = {"receipt_ref": receipt.storage_ref, "candidate_only": True,
                      "coverage_scope": "region_only", "status": result["status"]}
        if result["status"] != "read":
            raise StepFailure(retryable=True, error_code="LOCAL_VISUAL_RESPONSE_UNVERIFIED",
                              detail="本次局部读取未通过完整性核对，请重试或直接核对原件。",
                              diagnostic_checkpoint=checkpoint)
        return checkpoint

    return execute
