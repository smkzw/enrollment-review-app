"""选择性视觉后处理持久执行器：只消费已冻结修订的页产物与质量元数据。

边界：
- 不进入 OCR 页处理事务，不续 OCR 页租约，不改写 OCR 原文；
- 远端 VLM 在 JobRunner 事务外执行；观察落库由观察服务短事务完成；
- 失败关闭写 ``closed`` 审计后任务保持失败态，允许只重试未成功页面。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.enums import PageArtifactStatus
from app.evidence.artifacts import ArtifactStore
from app.evidence.ocr_adapter import PAGE_IMAGE_MIME
from app.evidence.selective_vision_review import (
    SELECTIVE_VISION_PLAN_VERSION,
    SKIP_FAILED_PAGE,
    SKIP_MISSING_PAGE_IMAGE,
    infer_complex_layout_not_represented,
)
from app.services.selective_vision_observation_service import (
    SelectiveVisionObservationPageMaterial,
    SelectiveVisionObservationService,
    SelectiveVisionObservationServiceError,
)
from app.services.selective_vision_postprocess_job_service import (
    SELECTIVE_VISION_POSTPROCESS_JOB_TYPE,
    SELECTIVE_VISION_POSTPROCESS_STEP_ID,
)
from app.services.selective_vision_runtime import selective_vision_route_sha256
from app.storage.config import DataPaths
from app.storage.evidence_repositories import SourceDocumentRepository
from app.storage.ocr_models import OCRProfileRecord
from app.storage.ocr_repositories import (
    EvidenceProcessingRevisionRepository,
    OcrPageRepository,
    PageArtifactRepository,
)
from app.workflow.errors import StepFailure
from app.workflow.runner import StepContext, StepExecutor

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SelectiveVisionPostprocessExecutorConfig:
    session_factory: sessionmaker[Session]
    data_paths: DataPaths
    artifact_store: ArtifactStore | None = None
    observation_service: SelectiveVisionObservationService | None = None
    review_runner: Callable[..., Any] | None = None


def _media_kind(media_type: str, file_name: str) -> str:
    mt = (media_type or "").lower()
    if mt == "application/pdf":
        return "pdf"
    if "wordprocessingml" in mt:
        return "docx"
    if mt in {"application/msword", "application/vnd.ms-word"}:
        return "doc"
    if mt in {"text/plain", "text/plain; charset=utf-8"}:
        return "text"
    if mt == "image/tiff" or mt.startswith("image/"):
        return "image"
    suffix = Path(file_name or "").suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".docx":
        return "docx"
    if suffix == ".doc":
        return "doc"
    if suffix == ".txt":
        return "text"
    if suffix in {".tif", ".tiff", ".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
        return "image"
    return "unsupported"


def _profile_route(session: Session, ocr_profile_sha256: str | None) -> str | None:
    if not ocr_profile_sha256:
        return None
    row = session.execute(
        select(OCRProfileRecord).where(
            OCRProfileRecord.profile_sha256 == ocr_profile_sha256
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return str(row.extraction_route)


def load_selective_vision_page_materials_for_revision(
    session: Session,
    *,
    evidence_processing_revision_id: str,
    artifact_store: ArtifactStore,
) -> list[SelectiveVisionObservationPageMaterial]:
    """从已冻结修订清单装载页材料；图像字节来自不可变工件库。"""
    revision = EvidenceProcessingRevisionRepository(session).get(
        evidence_processing_revision_id
    )
    artifact_repo = PageArtifactRepository(session)
    ocr_repo = OcrPageRepository(session)
    version_repo = SourceDocumentRepository(session)
    materials: list[SelectiveVisionObservationPageMaterial] = []

    for entry in revision.manifest:
        artifact = artifact_repo.get(entry.page_artifact_id)
        version = version_repo.get(entry.source_document_version_id)
        media_kind = _media_kind(version.media_type, version.file_name)
        page_image_sha = artifact.page_image_sha256
        has_page_image = bool(page_image_sha)
        image_bytes: bytes | None = None
        if has_page_image and page_image_sha is not None:
            try:
                image_bytes = artifact_store.read_by_sha("page_image", page_image_sha)
            except Exception:
                # 缺图由观察服务显式关闭；此处保留身份继续规划。
                image_bytes = None

        extraction_route: str | None = None
        ocr_page_id = entry.ocr_page_id
        has_native_text = bool(artifact.native_text_sha256)
        native_text_char_count = 0
        has_ocr_text = False
        ocr_text_char_count = 0
        ocr_confidence: float | None = None
        ocr_risk_kinds: tuple[str, ...] = ()
        layout_block_count: int | None = None

        if artifact.native_text_sha256:
            try:
                native_bytes = artifact_store.read_by_sha(
                    "native_text", artifact.native_text_sha256
                )
                native_text_char_count = len(
                    native_bytes.decode("utf-8", errors="ignore")
                )
                has_native_text = native_text_char_count > 0
            except Exception:
                has_native_text = True
                native_text_char_count = 0

        if ocr_page_id:
            ocr_page = ocr_repo.get(ocr_page_id)
            extraction_route = _profile_route(session, ocr_page.ocr_profile_sha256)
            if ocr_page.raw_text:
                has_ocr_text = True
                ocr_text_char_count = len(ocr_page.raw_text)
            ocr_confidence = ocr_page.quality.confidence
            layout_block_count = ocr_page.quality.layout_block_count
            ocr_risk_kinds = tuple(
                sorted({item.kind.value for item in ocr_page.risk_items})
            )

        complex_layout = infer_complex_layout_not_represented(
            has_native_text=has_native_text,
            native_text_char_count=native_text_char_count,
            layout_block_count=layout_block_count,
        )
        native_anomaly = artifact.status == PageArtifactStatus.DEGRADED
        materials.append(
            SelectiveVisionObservationPageMaterial(
                page_artifact_id=artifact.page_artifact_id,
                source_ref=entry.source_document_version_id,
                page_ordinal=int(entry.page_number),
                page_image_sha256=page_image_sha or ("0" * 64),
                media_kind=media_kind,
                extraction_route=extraction_route,
                page_artifact_status=artifact.status.value,
                has_page_image=has_page_image,
                has_native_text=has_native_text,
                native_text_char_count=native_text_char_count,
                has_ocr_text=has_ocr_text,
                ocr_text_char_count=ocr_text_char_count,
                non_text_mark_count=None,
                complex_layout_not_represented_by_native_text=complex_layout,
                native_extraction_anomaly=native_anomaly,
                ocr_confidence=ocr_confidence,
                ocr_risk_kinds=ocr_risk_kinds,
                ocr_page_id=ocr_page_id,
                image_bytes=image_bytes,
                media_type=PAGE_IMAGE_MIME,
            )
        )
    return materials


def create_selective_vision_postprocess_executor(
    config: SelectiveVisionPostprocessExecutorConfig,
) -> StepExecutor:
    artifact_store = config.artifact_store or ArtifactStore(config.data_paths)
    observation_service = config.observation_service or SelectiveVisionObservationService(
        config.session_factory,
        review_runner=config.review_runner,
    )

    def execute(context: StepContext) -> dict[str, Any]:
        if context.step_id != SELECTIVE_VISION_POSTPROCESS_STEP_ID:
            raise StepFailure(
                retryable=False,
                error_code="SELECTIVE_VISION_STEP_UNKNOWN",
                detail="选择性视觉后处理步骤无法识别。",
            )
        if context.last_checkpoint is not None:
            return dict(context.last_checkpoint)

        payload = context.job_payload or {}
        revision_id = str(payload.get("evidence_processing_revision_id") or "").strip()
        if not revision_id:
            raise StepFailure(
                retryable=False,
                error_code="SELECTIVE_VISION_REVISION_MISSING",
                detail="选择性视觉后处理任务缺少证据处理修订标识。",
            )
        plan_version = str(
            payload.get("plan_version") or SELECTIVE_VISION_PLAN_VERSION
        ).strip()
        if plan_version != SELECTIVE_VISION_PLAN_VERSION:
            raise StepFailure(
                retryable=False,
                error_code="SELECTIVE_VISION_PLAN_VERSION_UNSUPPORTED",
                detail="该视觉核验任务使用的规划版本与当前系统不一致，请重新创建任务。",
            )
        if payload.get("route_sha256") != selective_vision_route_sha256():
            raise StepFailure(
                retryable=False,
                error_code="SELECTIVE_VISION_ROUTE_CHANGED",
                detail="本次视觉核验的模型配置已变化，请创建当前配置的新任务。",
            )

        try:
            with config.session_factory() as session:
                materials = load_selective_vision_page_materials_for_revision(
                    session,
                    evidence_processing_revision_id=revision_id,
                    artifact_store=artifact_store,
                )
        except Exception as exc:
            raise StepFailure(
                retryable=True,
                error_code="SELECTIVE_VISION_MATERIAL_LOAD_FAILED",
                detail="已冻结资料页清单暂无法读取，系统将稍后重试视觉后处理。",
            ) from exc

        try:
            result = asyncio.run(
                observation_service.run_postprocess(materials, enabled=None)
            )
        except SelectiveVisionObservationServiceError as exc:
            raise StepFailure(
                retryable=False,
                error_code="SELECTIVE_VISION_POSTPROCESS_REJECTED",
                detail="选择性视觉后处理因页产物或 OCR 来源不一致已停止。",
            ) from exc
        except Exception as exc:
            logger.exception(
                "selective vision postprocess failed revision=%s job=%s",
                revision_id,
                context.job_id,
            )
            raise StepFailure(
                retryable=True,
                error_code="SELECTIVE_VISION_POSTPROCESS_RETRYABLE",
                detail="选择性视觉后处理尚未完成，系统将从已保存进度继续。",
            ) from exc

        eligible_ids = [
            material.page_artifact_id for material in materials
            if (material.source_ref, material.page_ordinal) in {
                (item.source_ref, item.page_ordinal) for item in result.plan.eligible
            }
        ]
        observed_ids = [row.page_artifact_id for row in result.observations]
        unreadable = any(
            item.skip_reason in {SKIP_FAILED_PAGE, SKIP_MISSING_PAGE_IMAGE}
            for item in result.skipped
        )
        incomplete = (
            result.closed_error is not None
            or unreadable
            or len(set(eligible_ids)) != len(eligible_ids)
            or len(observed_ids) != len(eligible_ids)
            or set(observed_ids) != set(eligible_ids)
        )
        if incomplete:
            raise StepFailure(
                retryable=False,
                error_code="SELECTIVE_VISION_PAGES_UNVERIFIED",
                detail="部分原始资料页尚未核实或无法读取；已核实页面已保留，可重试未完成的页面。",
            )
        return {
            "job_type": SELECTIVE_VISION_POSTPROCESS_JOB_TYPE,
            "evidence_processing_revision_id": revision_id,
            "plan_version": plan_version or result.plan.plan_version,
            "eligible_count": len(result.plan.eligible),
            "skipped_count": len(result.skipped),
            "observation_count": len(result.observations),
            "closed_count": len(result.closed),
            "created_observation_ids": list(result.created_observation_ids),
            "reused_observation_ids": list(result.reused_observation_ids),
            "closed_failure_kind": (
                result.closed_error.failure_kind if result.closed_error else None
            ),
            "eligible_page_artifact_ids": eligible_ids,
            "observed_page_artifact_ids": observed_ids,
            "status": "completed",
        }

    return execute


__all__ = [
    "SelectiveVisionPostprocessExecutorConfig",
    "create_selective_vision_postprocess_executor",
    "load_selective_vision_page_materials_for_revision",
]
