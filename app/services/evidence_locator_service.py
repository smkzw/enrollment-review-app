"""Slice 4.4 occurrence-aware 定位服务（WP-44B）。

把定位请求确定性判定为四级诚实精度并持久化定位旁路工件：

- ``native_text``  读取与来源文本同源的内容寻址原生文本/坐标 sidecar 工件：
  有可信原始范围且范围可逐字符映射到同源坐标时输出 ``bbox``（authenticated）；
  无坐标 sidecar 或映射失败时诚实降级 ``text_range``；重复文本 ``page_excerpt``；
  未找到 ``page_only``（绝不生成伪精确红框）；
- ``raw_ocr``      text-only 识别路线没有持久化机器坐标 sidecar → 一律不输出
  bbox，只能 ``text_range`` / ``page_excerpt`` / ``page_only``（§8.1 反例 1）；
- ``effective_text`` 必须绑定完整处理修订 + 有效文本投影哈希；从该修订所选校对
  重算投影并回验哈希后定位（同样无坐标 sidecar，不输出 bbox）。

定位身份按「页工件 + 来源层 + 来源文本哈希 + 精度 + 原始范围/摘录锚点 + 算法
版本」确定性计算（``occurrence_locator_id``）：同页两处相同文本以不同可信范围
各自定位、互不碰撞；只给字符串或多处命中必须降级（§4.2 重复文本规则）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.enums import (
    CoordinateSpace,
    DisambiguationOutcome,
    LocatorAuthenticity,
    LocatorPrecision,
    LocatorSourceLayer,
)
from app.domain.contracts.evidence import BoundingBox
from app.domain.contracts.evidence_locator import (
    EvidenceLocatorArtifact,
    locator_anchor_hash,
)
from app.domain.contracts.ocr import CoordinateFrame
from app.evidence.effective_text import project_effective_text
from app.evidence.ocr_adapter import TEXT_ONLY_DEGRADATION_REASON
from app.evidence.locator import (
    OCCURRENCE_LOCATOR_ALGORITHM_VERSION,
    locate_in_text,
    occurrence_locator_id,
)
from app.evidence.locator_proof import LocatorProofError, LocatorProofReader
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository,
    CorrectionRepository,
    EvidenceLocatorRepository,
)
from app.storage.ocr_models import PageArtifactRecord
from app.storage.ocr_repositories import OcrPageRepository

__all__ = [
    "EvidenceLocatorService",
    "LocatorInputError",
    "LocatorRequest",
]


class LocatorInputError(ValueError):
    """定位请求与绑定来源层/哈希/范围不一致，拒绝构造。"""


def _utcnow():
    from datetime import UTC, datetime

    return datetime.now(UTC)


@dataclass(frozen=True)
class LocatorRequest:
    """一次定位请求（§4.2）：优先原始范围，其次才是摘录文本。"""

    page_artifact_id: str
    ocr_page_id: str | None = None
    source_layer: LocatorSourceLayer = LocatorSourceLayer.RAW_OCR
    source_text_sha256: str = ""
    target_id: str = ""
    target_text_start: int | None = None
    target_text_end: int | None = None
    excerpt: str | None = None
    locator_algorithm_version: str = OCCURRENCE_LOCATOR_ALGORITHM_VERSION
    coordinate_transform_version: str | None = None
    processing_revision_id: str | None = None
    effective_text_sha256: str | None = None


class EvidenceLocatorService:
    """occurrence-aware 定位服务：诚实精度判定 + 旁路工件持久化。"""

    def __init__(self, session_factory: sessionmaker, artifact_store: Any = None) -> None:
        self.session_factory = session_factory
        self.artifact_store = artifact_store

    def create_locator(self, request: LocatorRequest) -> EvidenceLocatorArtifact:
        with self.session_factory() as session, session.begin():
            return self.create_locator_in_session(session, request)

    def create_locator_in_session(
        self, session: Session, request: LocatorRequest
    ) -> EvidenceLocatorArtifact:
        source_layer = LocatorSourceLayer(request.source_layer)
        artifact_record = session.get(PageArtifactRecord, request.page_artifact_id)
        if artifact_record is None:
            raise LocatorInputError(f"定位引用的 PageArtifact {request.page_artifact_id} 不存在")

        if source_layer == LocatorSourceLayer.NATIVE_TEXT:
            decision, bbox, frame, sidecar_sha, coordinate_transform_version = (
                self._locate_native(session, request, artifact_record)
            )
        elif source_layer == LocatorSourceLayer.RAW_OCR:
            decision, bbox, frame, sidecar_sha, coordinate_transform_version = (
                self._locate_raw_ocr(session, request, artifact_record)
            )
        elif source_layer == LocatorSourceLayer.EFFECTIVE_TEXT:
            decision, bbox, frame, sidecar_sha, coordinate_transform_version = (
                self._locate_effective_text(session, request, artifact_record)
            )
        else:
            raise LocatorInputError(f"未知来源层 {source_layer.value}")

        precision = decision.precision
        authenticity = (
            LocatorAuthenticity.AUTHENTICATED
            if precision == LocatorPrecision.BBOX
            else LocatorAuthenticity.DEGRADED
        )
        degradation_reason = decision.degradation_reason
        if (
            precision in (LocatorPrecision.TEXT_RANGE, LocatorPrecision.PAGE_EXCERPT)
            and degradation_reason is None
        ):
            degradation_reason = (
                "当前原件只能定位到对应文字范围，未取得可验证的页面坐标，"
                "因此不显示区域标注"
            )
        anchor_hash = None
        if precision == LocatorPrecision.PAGE_EXCERPT or precision == LocatorPrecision.PAGE_ONLY:
            anchor_hash = locator_anchor_hash(
                page_artifact_id=request.page_artifact_id,
                source_layer=source_layer,
                source_text_sha256=request.source_text_sha256,
                precision=precision,
                target_id=request.target_id,
                excerpt=decision.excerpt,
                disambiguation=decision.disambiguation,
                degradation_reason=degradation_reason,
            )
        locator_id = occurrence_locator_id(
            page_artifact_id=request.page_artifact_id,
            source_layer=source_layer,
            source_text_sha256=request.source_text_sha256,
            precision=precision,
            target_id=request.target_id,
            text_start=decision.text_start,
            text_end=decision.text_end,
            sidecar_sha256=sidecar_sha,
            anchor_hash=anchor_hash,
            disambiguation=decision.disambiguation,
            degradation_reason=degradation_reason,
            locator_algorithm_version=request.locator_algorithm_version,
        )
        artifact = EvidenceLocatorArtifact(
            locator_id=locator_id,
            page_artifact_id=request.page_artifact_id,
            ocr_page_id=request.ocr_page_id,
            source_document_version_id=artifact_record.source_document_version_id,
            page_number=artifact_record.page_number,
            source_layer=source_layer,
            source_text_sha256=request.source_text_sha256,
            target_id=request.target_id,
            precision=precision,
            bbox=bbox,
            coordinate_frame=frame,
            sidecar_sha256=sidecar_sha,
            text_start=decision.text_start,
            text_end=decision.text_end,
            excerpt=decision.excerpt,
            anchor_hash=anchor_hash,
            disambiguation=decision.disambiguation,
            locator_algorithm_version=request.locator_algorithm_version,
            coordinate_transform_version=coordinate_transform_version,
            authenticity=authenticity,
            effective_text_sha256=request.effective_text_sha256,
            processing_revision_id=request.processing_revision_id,
            match_confidence=decision.match_confidence,
            degradation_reason=degradation_reason,
            created_at=_utcnow(),
        )
        repository = EvidenceLocatorRepository(session, self.artifact_store)
        existing = repository.get_or_none(locator_id)
        if existing is not None:
            if existing != artifact.model_copy(update={"created_at": existing.created_at}):
                raise LocatorInputError("同一定位身份已存在但内容不一致")
            return existing
        return repository.create(artifact)

    # ------------------------------------------------------------------ 层路由

    def _locate_native(self, session, request, artifact_record) -> tuple:
        if self.artifact_store is None:
            raise LocatorInputError("native_text 定位需要内容寻址 ArtifactStore 证明")
        if artifact_record.native_text_sha256 != request.source_text_sha256:
            raise LocatorInputError(
                "native_text 定位的来源文本哈希与页产物原生文本不一致"
            )
        proof = LocatorProofReader(self.artifact_store)
        try:
            native_text = proof.native_text(request.source_text_sha256)
        except LocatorProofError as exc:
            raise LocatorInputError(str(exc)) from exc
        decision = locate_in_text(
            native_text,
            excerpt=request.excerpt or "",
            text_start=request.target_text_start,
            text_end=request.target_text_end,
        )
        bbox: BoundingBox | None = None
        frame: CoordinateFrame | None = None
        sidecar_sha: str | None = None
        transform_version = artifact_record.coordinate_transform_version
        if (
            decision.precision in (LocatorPrecision.BBOX, LocatorPrecision.TEXT_RANGE)
            and decision.text_start is not None
            and decision.text_end is not None
            and artifact_record.native_coordinates_sha256 is not None
        ):
            sidecar_sha = artifact_record.native_coordinates_sha256
            try:
                sidecar = proof.native_coordinates(artifact_record.native_coordinates_sha256)
            except LocatorProofError as exc:
                raise LocatorInputError(str(exc)) from exc
            if sidecar.text != native_text:
                raise LocatorInputError("原生坐标 sidecar 文本与原生文本工件不一致")
            if sidecar.page_width <= 0 or sidecar.page_height <= 0:
                raise LocatorInputError("原生坐标页尺寸无效，无法映射到页图")
            scale_x = artifact_record.page_width / sidecar.page_width
            scale_y = artifact_record.page_height / sidecar.page_height
            if abs(scale_x - scale_y) > max(scale_x, scale_y) * 0.01:
                raise LocatorInputError("原生坐标与页图的横纵缩放不一致，拒绝绘制区域框")
            frame = CoordinateFrame(
                space=CoordinateSpace.PAGE_IMAGE_PIXELS,
                page_width=artifact_record.page_width,
                page_height=artifact_record.page_height,
                rotation=artifact_record.rotation,
                transform_version=transform_version,
            )
            try:
                bbox = proof.recompute_bbox(
                    sidecar,
                    text_start=decision.text_start,
                    text_end=decision.text_end,
                    frame=frame,
                    pixels_per_point=(scale_x + scale_y) / 2,
                )
            except LocatorProofError:
                # 字符映射失败：诚实降级为文本范围，不生成伪坐标。
                bbox = None
                frame = None
                sidecar_sha = None
                decision = _degraded_text_range(decision, "目标范围无同源坐标字符，诚实降级为文本范围")
        if decision.precision == LocatorPrecision.BBOX and bbox is None:
            decision = _degraded_text_range(decision, "无法从同源坐标证明 bbox，诚实降级为文本范围")
        if bbox is not None:
            decision = _promote_bbox(decision)
        return decision, bbox, frame, sidecar_sha, transform_version

    def _locate_raw_ocr(self, session, request, artifact_record) -> tuple:
        if request.ocr_page_id is None:
            raise LocatorInputError("raw_ocr 定位必须绑定 ocr_page_id")
        ocr = OcrPageRepository(session).get(request.ocr_page_id)
        if ocr.raw_text_sha256 != request.source_text_sha256:
            raise LocatorInputError("raw_ocr 定位的来源文本哈希与 OCRPage 不一致")
        if ocr.page_artifact_id != request.page_artifact_id:
            raise LocatorInputError("raw_ocr 定位的 OCR 页与页产物归属不一致")
        decision = locate_in_text(
            ocr.raw_text,
            excerpt=request.excerpt or "",
            text_start=request.target_text_start,
            text_end=request.target_text_end,
        )
        if decision.precision == LocatorPrecision.TEXT_RANGE:
            decision = _degraded_text_range(decision, TEXT_ONLY_DEGRADATION_REASON)
        return decision, None, None, None, artifact_record.coordinate_transform_version

    def _locate_effective_text(self, session, request, artifact_record) -> tuple:
        if request.processing_revision_id is None or request.effective_text_sha256 is None:
            raise LocatorInputError("effective_text 定位必须绑定完整处理修订与投影哈希")
        if request.ocr_page_id is None:
            raise LocatorInputError("effective_text 定位必须绑定 OCR 页")
        revision = CompleteEvidenceProcessingRevisionRepository(
            session, self.artifact_store
        ).get(request.processing_revision_id)
        ocr_page_id = request.ocr_page_id
        if not any(e.ocr_page_id == ocr_page_id for e in revision.manifest):
            raise LocatorInputError(
                "effective_text 定位的 OCR 页不在该完整修订页清单中"
            )
        ocr = OcrPageRepository(session).get(ocr_page_id)
        correction_repo = CorrectionRepository(session)
        corrections = [
            correction_repo.get(cid)
            for cid in revision.correction_ids
            if correction_repo.get(cid).ocr_page_id == ocr_page_id
        ]
        projection = project_effective_text(ocr.raw_text, corrections)
        if request.source_text_sha256 != projection.effective_text_sha256:
            raise LocatorInputError(
                "effective_text 定位的来源文本哈希与投影重算结果不一致"
            )
        if request.effective_text_sha256 != projection.effective_text_sha256:
            raise LocatorInputError(
                "effective_text 定位的投影哈希与重算结果不一致"
            )
        decision = locate_in_text(
            projection.effective_text,
            excerpt=request.excerpt or "",
            text_start=request.target_text_start,
            text_end=request.target_text_end,
        )
        if decision.precision == LocatorPrecision.TEXT_RANGE:
            decision = _degraded_text_range(
                decision,
                "校对后的文字可定位到对应文本范围，但无法可靠映射到原件区域，"
                "因此不显示区域标注",
            )
        return decision, None, None, None, artifact_record.coordinate_transform_version


def _degraded_text_range(decision, reason: str):
    from dataclasses import replace

    return replace(
        decision,
        precision=LocatorPrecision.TEXT_RANGE,
        degradation_reason=reason,
        disambiguation=DisambiguationOutcome.UNIQUE_MATCH,
    )


def _promote_bbox(decision):
    from dataclasses import replace

    return replace(
        decision,
        precision=LocatorPrecision.BBOX,
        degradation_reason=None,
        disambiguation=DisambiguationOutcome.UNIQUE_MATCH,
    )
