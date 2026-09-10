"""Slice 4.4 定位、风险、校对、被提及资料、处理候选与活动版本追加仓储（WP-44A）。

仓储负责追加写、一致性校验，以及激活事件与审核节点成对指针的原子更新：

- ``EvidenceLocatorRepository``             occurrence-aware 定位旁路工件（幂等身份）；
- ``OCRRiskScanRepository``                 风险扫描（三元组幂等复用 + 冲突拒绝）；
- ``OCRRiskReviewRepository``               风险核对决议（追加写）；
- ``CorrectionRepository``                  校对覆盖层记录（supersede 链校验）；
- ``ReferencedDocumentRepository``          被提及资料登记修订 + 满足修订（追加写链）；
- ``EvidenceActivationEventRepository``     激活/回滚事件（每 episode 连续序号）；
- ``EvidenceProcessingCandidateRepository``  处理候选 + 追加事件状态机（终态不可跳转）；
- ``CompleteEvidenceProcessingRevisionRepository`` 完整处理修订 + 有序旁路关联闭包。

活动版本成对指针只能通过 ``EvidenceActivationEventRepository.append_and_switch``
与事件在同一事务写入；禁止单独追加事件，避免服务层以外的调用制造孤立事件。
"""
from __future__ import annotations

import json
from typing import cast

from sqlalchemy import func, or_, select

from app.domain.contracts.enums import (
    ActivationEventKind,
    CoordinateSpace,
    EvidenceProcessingCandidateStatus,
    LocatorPrecision,
    LocatorSourceLayer,
    OCRPageStatus,
    OcrRiskLevel,
    PageArtifactStatus,
    ProcessingCandidateEventKind,
    ReferencedDocumentResolutionStatus,
    ReferencedDocumentStatus,
    SnapshotStatus,
)
from app.domain.contracts.evidence_locator import (
    BLOCKING_CORRECTION_KINDS,
    CompleteEvidenceProcessingRevision,
    CorrectionRecord,
    EvidenceActivationEvent,
    EvidenceLocatorArtifact,
    EvidenceProcessingCandidate,
    EvidenceProcessingCandidateEvent,
    OCRRiskPageReview,
    OCRRiskReview,
    OCRRiskScan,
    SOURCE_LINE_TARGET_PREFIX,
    ReferencedDocumentResolutionRevision,
    ReferencedDocumentRevision,
    completion_manifest_hash,
    validate_correction_source_anchor,
)
from app.domain.contracts.evidence_processing import EvidenceProcessingRevisionPage
from app.domain.contracts.ocr import OCRPage, OcrRiskFlag
from app.domain.contracts.review import ReviewEpisode
from app.evidence.effective_text import (
    correction_anchors_conflict,
    project_effective_text,
)
from app.evidence.locator_proof import (
    NATIVE_COORDINATES_SCHEMA,
    LocatorProofError,
    LocatorProofReader,
)
from app.storage.codecs import (
    PersistedContractInvalid,
    check_column_mirrors,
    decode_contract,
    encode_contract,
    to_utc_naive,
)
from app.storage.concurrency import apply_revisioned_update
from app.storage.evidence_locator_models import (
    CorrectionRecordRecord,
    EvidenceActivationEventRecord,
    EvidenceLocatorArtifactRecord,
    EvidenceProcessingCandidateEventRecord,
    EvidenceProcessingCandidateRecord,
    OCRRiskFlagRecord,
    OCRRiskPageReviewRecord,
    OCRRiskReviewRecord,
    OCRRiskScanRecord,
    ProcessingRevisionCorrectionRecord,
    ProcessingRevisionLocatorRecord,
    ProcessingRevisionMetadataRevisionRecord,
    ProcessingRevisionReferencedDocumentRecord,
    ProcessingRevisionResolutionRecord,
    ProcessingRevisionRiskReviewRecord,
    ProcessingRevisionRiskScanRecord,
    ReferencedDocumentResolutionRevisionRecord,
    ReferencedDocumentRevisionRecord,
)
from app.storage.evidence_models import (
    EvidenceSnapshotMemberRecord,
    EvidenceSnapshotV2Record,
    SourceDocumentMetadataRevisionRecord,
    SourceDocumentVersionV2Record,
)
from app.storage.evidence_repositories import (
    EvidenceSnapshotRepository,
    SourceDocumentMetadataRevisionRepository,
)
from app.storage.models import ReviewEpisodeRecord
from app.storage.ocr_models import (
    EvidenceProcessingRevisionPageRecord,
    EvidenceProcessingRevisionRecord,
    OCRPageRecord,
    PageArtifactRecord,
)
from app.storage.ocr_repositories import (
    EvidenceProcessingRevisionRepository,
    OcrPageRepository,
)
from app.storage.repositories import (
    DuplicateRecordError,
    EpisodeRepository,
    InvalidReferenceError,
    NotFoundError,
    RepositoryError,
    _episode_columns,
    _flush_guarded,
    _get_required,
)

__all__ = [
    "ActivationSequenceError",
    "CandidateIdempotencyConflictError",
    "CandidateStateTransitionError",
    "CompleteEvidenceProcessingRevisionRepository",
    "CorrectionOverlapError",
    "CorrectionRepository",
    "EvidenceActivationEventRepository",
    "EvidenceLocatorRepository",
    "EvidenceProcessingCandidateRepository",
    "LocatorIdentityError",
    "OCRRiskPageReviewRepository",
    "OCRRiskReviewRepository",
    "OCRRiskScanRepository",
    "OcrRevisionKindError",
    "ReferencedDocumentRepository",
    "RevisionClosureError",
    "RiskPageReviewAtomicityError",
    "RiskScanConflictError",
    "Slice44RepositoryError",
]


class Slice44RepositoryError(RepositoryError):
    """Slice 4.4 仓储领域错误基类。"""


class LocatorIdentityError(Slice44RepositoryError):
    """定位旁路工件身份/真实性门禁不一致，拒绝写入或还原。"""


class RiskScanConflictError(Slice44RepositoryError):
    """同一 (页, 原文哈希, 规则版本) 三元组复用但 flag 集合哈希不一致。"""


class RiskPageReviewAtomicityError(Slice44RepositoryError):
    """页级原子核对与逐条不可变核对不一致：覆盖集合/物化 review 缺项、多换或错绑。"""


class CorrectionOverlapError(Slice44RepositoryError):
    """完整修订内两个有效校对范围重叠且无显式替代，拒绝构建。"""


class CandidateStateTransitionError(Slice44RepositoryError):
    """处理候选状态转换非法或终态被冻结。"""


class CandidateIdempotencyConflictError(Slice44RepositoryError):
    """同一幂等键但候选输入不一致，拒绝复用。"""


class ActivationSequenceError(Slice44RepositoryError):
    """激活事件序号不连续或与既有事件冲突。"""


class RevisionClosureError(Slice44RepositoryError):
    """完整处理修订闭包与 base/旁路工件不一致，拒绝写入或还原。"""


class OcrRevisionKindError(Slice44RepositoryError):
    """修订类别（base/complete）与读取仓储不匹配。"""


def _verify_base_revision_scope(
    session,
    base_revision_id: str,
    *,
    ocr_page_id: str | None = None,
    review_episode_id: str | None = None,
) -> None:
    """base_processing_revision_id 必须指向存在的 base 修订，且锚定页出现在该 base 页清单。

    只证明同一审核节点不足：校对/风险核对必须证明其 OCR 页被该 base 修订页清单
    真正冻结（同闭包），否则跨 base 选择可绕过清单闭包。
    """
    base = session.get(EvidenceProcessingRevisionRecord, base_revision_id)
    if base is None:
        raise InvalidReferenceError(f"base 处理修订 {base_revision_id} 不存在")
    if base.revision_kind != "base":
        raise Slice44RepositoryError(
            f"base_processing_revision_id {base_revision_id} 必须是 base 修订，"
            "完整修订/校对/风险核对不得锚定 complete 修订"
        )
    episode: str | None = review_episode_id
    if ocr_page_id is not None:
        ocr = session.get(OCRPageRecord, ocr_page_id)
        if ocr is None:
            raise InvalidReferenceError(f"OCRPage {ocr_page_id} 不存在")
        # OCR 页必须出现在 base 页清单（同闭包证明）。
        from app.storage.ocr_models import EvidenceProcessingRevisionPageRecord

        in_base_manifest = session.execute(
            select(EvidenceProcessingRevisionPageRecord)
            .where(
                EvidenceProcessingRevisionPageRecord.revision_id == base_revision_id
            )
            .where(EvidenceProcessingRevisionPageRecord.ocr_page_id == ocr_page_id)
        ).scalars().first()
        if in_base_manifest is None:
            raise Slice44RepositoryError(
                f"OCRPage {ocr_page_id} 不在 base 修订 {base_revision_id} 的页清单中，"
                "校对/风险核对必须锚定同一 base 闭包内的页"
            )
        artifact = session.get(PageArtifactRecord, ocr.page_artifact_id)
        if artifact is None:
            raise InvalidReferenceError(f"PageArtifact {ocr.page_artifact_id} 不存在")
        document = session.get(
            SourceDocumentVersionV2Record, artifact.source_document_version_id
        )
        if document is None:
            raise InvalidReferenceError(
                f"资料版本 {artifact.source_document_version_id} 不存在"
            )
        episode = document.review_episode_id
    if episode is not None and base.review_episode_id != episode:
        raise Slice44RepositoryError(
            f"base 修订 {base_revision_id} 属于审核节点 {base.review_episode_id}，"
            f"与锚定对象 {episode} 作用域不一致"
        )


# --------------------------------------------------------------------------- 定位


def _require_artifact(artifact: EvidenceLocatorArtifact) -> None:
    """定位旁路工件必须满足来源层/哈希绑定、范围完整与 bbox 同源 sidecar 真实性。"""
    if artifact.source_layer == LocatorSourceLayer.RAW_OCR and artifact.ocr_page_id is None:
        raise LocatorIdentityError("raw_ocr 定位必须绑定 ocr_page_id")
    if artifact.source_layer == LocatorSourceLayer.EFFECTIVE_TEXT and artifact.ocr_page_id is None:
        raise LocatorIdentityError("effective_text 定位必须绑定 ocr_page_id")
    if artifact.authenticity.value == "authenticated" and artifact.sidecar_sha256 is None:
        raise LocatorIdentityError("真实 bbox 定位必须携带同源坐标 sidecar 哈希")
    if artifact.precision in {
        LocatorPrecision.BBOX,
        LocatorPrecision.TEXT_RANGE,
    } and (artifact.text_start is None or artifact.text_end is None):
        raise LocatorIdentityError("bbox/text_range 定位必须绑定具体原始字符范围")
    if artifact.precision == LocatorPrecision.PAGE_EXCERPT and artifact.anchor_hash is None:
        raise LocatorIdentityError("page_excerpt 定位必须携带可回放摘录锚点哈希")
    if artifact.precision == LocatorPrecision.PAGE_ONLY and artifact.anchor_hash is None:
        raise LocatorIdentityError("page_only 定位必须携带稳定目标身份锚点哈希")


class EvidenceLocatorRepository:
    """occurrence-aware 定位旁路工件：追加写 + 身份幂等 + 来源/范围/工件真实性闭包。

    bbox 必须由与来源文本同源的内容寻址坐标工件（``native_coordinates/<sha>``）
    逐字符映射重算证明；``raw_ocr`` 当前是 text-only 路线，没有持久化机器坐标
    sidecar，因此原始 OCR 的 bbox 一律拒绝/诚实降级，绝不输出红框工件。
    ``effective_text`` 在 WP-44A 无法由投影引擎重建时一律拒绝持久化。
    """

    def __init__(self, session, artifact_store=None) -> None:
        self.session = session
        self.artifact_store = artifact_store
        self.proof = LocatorProofReader(artifact_store) if artifact_store is not None else None

    @staticmethod
    def _decode(record: EvidenceLocatorArtifactRecord) -> EvidenceLocatorArtifact:
        contract = decode_contract(
            EvidenceLocatorArtifact, record.payload_json, record.payload_sha256
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "EvidenceLocatorArtifact",
            record,
            payload,
            {
                "locator_id": "locator_id",
                "page_artifact_id": "page_artifact_id",
                "ocr_page_id": "ocr_page_id",
                "source_document_version_id": "source_document_version_id",
                "page_number": "page_number",
                "source_layer": "source_layer",
                "source_text_sha256": "source_text_sha256",
                "target_id": "target_id",
                "precision": "precision",
                "text_start": "text_start",
                "text_end": "text_end",
                "disambiguation": "disambiguation",
                "locator_algorithm_version": "locator_algorithm_version",
                "authenticity": "authenticity",
                "processing_revision_id": "processing_revision_id",
            },
        )
        return contract

    def _identity_conditions(self, artifact: EvidenceLocatorArtifact) -> list:
        """occurrence 身份：按精度冻结，绝不只靠 NULL range + 页/层/算法。

        - bbox/text_range：页工件 + 来源层/哈希 + 具体原始范围 + 算法版本
          （bbox 另加坐标 sidecar/proof 身份）；
        - page_excerpt：页工件 + 来源层/哈希 + 可回放摘录/上下文锚点哈希 +
          消歧结果 + 算法版本（不同摘录不碰撞，同一摘录精确别名碰撞）；
        - page_only/not-found：页工件 + 来源层/哈希 + 稳定目标身份 +
          降级/消歧证明 + 算法版本（不同目标不碰撞，同一目标精确别名碰撞）。
        """
        if artifact.source_layer == LocatorSourceLayer.PAGE_REVIEW_VISUAL:
            # The verified visual ID includes coverage and the individual reader.
            return [EvidenceLocatorArtifactRecord.locator_id == artifact.locator_id]
        base = [
            EvidenceLocatorArtifactRecord.page_artifact_id == artifact.page_artifact_id,
            EvidenceLocatorArtifactRecord.source_layer == artifact.source_layer.value,
            EvidenceLocatorArtifactRecord.source_text_sha256 == artifact.source_text_sha256,
            (
                EvidenceLocatorArtifactRecord.locator_algorithm_version
                == artifact.locator_algorithm_version
            ),
        ]
        if artifact.precision in (LocatorPrecision.BBOX, LocatorPrecision.TEXT_RANGE):
            base.extend(
                [
                    EvidenceLocatorArtifactRecord.text_start == artifact.text_start,
                    EvidenceLocatorArtifactRecord.text_end == artifact.text_end,
                ]
            )
            if artifact.precision == LocatorPrecision.BBOX:
                base.append(
                    EvidenceLocatorArtifactRecord.sidecar_sha256
                    == artifact.sidecar_sha256
                )
        elif artifact.precision == LocatorPrecision.PAGE_EXCERPT:
            base.extend(
                [
                    EvidenceLocatorArtifactRecord.anchor_hash == artifact.anchor_hash,
                    EvidenceLocatorArtifactRecord.disambiguation
                    == artifact.disambiguation.value,
                ]
            )
        elif artifact.precision == LocatorPrecision.PAGE_ONLY:
            base.extend(
                [
                    EvidenceLocatorArtifactRecord.target_id == artifact.target_id,
                    EvidenceLocatorArtifactRecord.disambiguation
                    == artifact.disambiguation.value,
                    EvidenceLocatorArtifactRecord.degradation_reason
                    == artifact.degradation_reason,
                ]
            )
        return base

    def _verify_frame(
        self, artifact: EvidenceLocatorArtifact, artifact_record: PageArtifactRecord
    ) -> None:
        """bbox 坐标系/页尺寸/旋转/变换版本必须与持久化 PageArtifact 一致。"""
        frame = artifact.coordinate_frame
        if frame is None:
            raise LocatorIdentityError("bbox 定位必须提供坐标系与页尺寸")
        dimensions_match = True
        if frame.space == CoordinateSpace.PAGE_IMAGE_PIXELS:
            dimensions_match = (
                frame.page_width == artifact_record.page_width
                and frame.page_height == artifact_record.page_height
            )
        if (
            not dimensions_match
            or frame.rotation != artifact_record.rotation
            or frame.transform_version != artifact_record.coordinate_transform_version
        ):
            raise LocatorIdentityError(
                f"定位 {artifact.locator_id} 的坐标系/页尺寸/旋转/变换版本与持久化"
                " PageArtifact 不一致，无法证明坐标同源"
            )

    def _verify_native(self, artifact: EvidenceLocatorArtifact, artifact_record: PageArtifactRecord) -> None:
        """原生文本/坐标工件真实性证明：读取内容寻址字节，重算/回验。"""
        if self.proof is None:
            raise LocatorIdentityError(
                "native_text 定位真实性证明需要内容寻址 ArtifactStore"
            )
        try:
            native_text = self.proof.native_text(artifact.source_text_sha256)
        except LocatorProofError as exc:
            raise LocatorIdentityError(str(exc)) from exc
        if (
            artifact_record.native_text_sha256 != artifact.source_text_sha256
            or artifact_record.native_text_sha256 is None
        ):
            raise LocatorIdentityError(
                f"定位 {artifact.locator_id} 的 native_text 哈希与页产物原生文本不一致"
            )
        if artifact.precision in (LocatorPrecision.BBOX, LocatorPrecision.TEXT_RANGE):
            self._verify_range_on_text(artifact, native_text, "native_text 工件")
        elif artifact.precision == LocatorPrecision.PAGE_EXCERPT:
            self._verify_excerpt_on_text(artifact, native_text, "native_text 工件")
        if artifact.precision == LocatorPrecision.BBOX:
            if artifact_record.native_coordinates_sha256 is None:
                raise LocatorIdentityError(
                    "text-only/无原生坐标 sidecar 的页产物不能输出 bbox"
                )
            if artifact.sidecar_sha256 != artifact_record.native_coordinates_sha256:
                raise LocatorIdentityError(
                    f"定位 {artifact.locator_id} 的坐标 sidecar 哈希与页产物原生"
                    "坐标 sidecar 不一致，无法证明坐标同源"
                )
            self._verify_frame(artifact, artifact_record)
            sidecar_sha = artifact.sidecar_sha256
            if sidecar_sha is None:
                raise LocatorIdentityError("bbox 定位必须携带同源坐标 sidecar 哈希")
            try:
                sidecar = self.proof.native_coordinates(sidecar_sha)
            except LocatorProofError as exc:
                raise LocatorIdentityError(str(exc)) from exc
            if sidecar.schema != NATIVE_COORDINATES_SCHEMA:
                raise LocatorIdentityError("原生坐标工件 schema 必须是 native_coordinates/v1")
            if sidecar.page_number != artifact.page_number:
                raise LocatorIdentityError("原生坐标工件页码与定位不一致")
            if sidecar.text != native_text:
                raise LocatorIdentityError("原生坐标工件文本与原生文本工件不一致")
            if sidecar.rotation != artifact_record.rotation:
                raise LocatorIdentityError("原生坐标工件旋转方向与 PageArtifact 不一致")
            frame = artifact.coordinate_frame
            if frame is None:
                raise LocatorIdentityError("bbox 定位必须提供坐标系与页尺寸")
            bbox = artifact.bbox
            if bbox is None:
                raise LocatorIdentityError("bbox 定位必须提供坐标")
            pixels_per_point = None
            if frame.space == CoordinateSpace.PAGE_IMAGE_PIXELS:
                if sidecar.page_width <= 0 or sidecar.page_height <= 0:
                    raise LocatorIdentityError("原生坐标工件页尺寸无效")
                scale_x = frame.page_width / sidecar.page_width
                scale_y = frame.page_height / sidecar.page_height
                if abs(scale_x - scale_y) > max(scale_x, scale_y) * 0.01:
                    raise LocatorIdentityError("原生坐标与页图的横纵缩放不一致")
                pixels_per_point = (scale_x + scale_y) / 2
            elif (
                frame.page_width != sidecar.page_width
                or frame.page_height != sidecar.page_height
            ):
                raise LocatorIdentityError("PDF 点坐标系页尺寸与原生坐标工件不一致")
            try:
                recomputed = self.proof.recompute_bbox(
                    sidecar,
                    text_start=artifact.text_start or 0,
                    text_end=artifact.text_end or 0,
                    frame=frame,
                    pixels_per_point=pixels_per_point,
                )
            except LocatorProofError as exc:
                raise LocatorIdentityError(str(exc)) from exc
            if not self.proof.bbox_matches(recomputed, bbox):
                raise LocatorIdentityError(
                    f"定位 {artifact.locator_id} 的 bbox 与原生坐标字符映射重算结果不一致"
                )

    def _verify_raw_ocr(self, artifact: EvidenceLocatorArtifact, artifact_record: PageArtifactRecord) -> None:
        """raw_ocr 定位：重读不可变 OCRPage.raw_text，校验哈希与范围/摘录。

        raw_ocr 当前是 text-only 路线，没有持久化机器坐标 sidecar → bbox 一律拒绝。
        """
        ocr_record = self.session.get(OCRPageRecord, artifact.ocr_page_id)
        if ocr_record is None:
            raise InvalidReferenceError(
                f"定位 {artifact.locator_id} 引用的 OCRPage {artifact.ocr_page_id} 不存在"
            )
        if (
            ocr_record.raw_text_sha256 != artifact.source_text_sha256
            or ocr_record.page_artifact_id != artifact.page_artifact_id
            or ocr_record.page_number != artifact.page_number
            or ocr_record.source_sha256 != artifact_record.source_sha256
        ):
            raise LocatorIdentityError(
                f"定位 {artifact.locator_id} 的 raw_ocr 哈希/页归属/源文件与 OCRPage 不一致"
            )
        if artifact.precision in (LocatorPrecision.BBOX, LocatorPrecision.TEXT_RANGE):
            self._verify_range_on_text(artifact, ocr_record.raw_text, "OCRPage.raw_text")
        elif artifact.precision == LocatorPrecision.PAGE_EXCERPT:
            self._verify_excerpt_on_text(
                artifact, ocr_record.raw_text, "OCRPage.raw_text"
            )
        if artifact.precision == LocatorPrecision.BBOX:
            raise LocatorIdentityError(
                "raw_ocr bbox 需要真实机器坐标 sidecar 工件；当前 text-only 识别路线"
                "没有持久化坐标，拒绝 bbox（诚实降级为 text_range/excerpt/page_only）"
            )

    def _verify_effective_text(self, artifact: EvidenceLocatorArtifact) -> None:
        """effective_text 定位：从绑定的完整处理修订读取该页所选校对，用投影引擎
        确定性重建有效文本并回验哈希/范围（WP-44B）。

        从不信任调用方自报的有效文本哈希：每次读取都从不可变 ``OCRPage.raw_text``
        + 完整修订所选校对集合重算投影，再核对 ``source_text_sha256`` /
        ``effective_text_sha256`` / 字符范围 / 摘录。投影文本没有持久化机器坐标
        sidecar，因此 effective_text 一律拒绝 bbox（诚实降级为 text_range/
        excerpt/page_only）。
        """
        if artifact.processing_revision_id is None:
            raise LocatorIdentityError("effective_text 定位必须绑定完整处理修订")
        if artifact.ocr_page_id is None:
            raise LocatorIdentityError("effective_text 定位必须绑定 OCR 页")
        revision = CompleteEvidenceProcessingRevisionRepository(
            self.session, self.artifact_store
        ).get(artifact.processing_revision_id)
        selected_ocr_page_id: str | None = None
        selected_page_artifact_id: str | None = None
        for entry in revision.manifest:
            if entry.ocr_page_id == artifact.ocr_page_id:
                selected_ocr_page_id = entry.ocr_page_id
                selected_page_artifact_id = entry.page_artifact_id
                break
        if selected_ocr_page_id is None:
            raise LocatorIdentityError(
                f"定位 {artifact.locator_id} 的 OCR 页不在完整修订 "
                f"{artifact.processing_revision_id} 的页清单中"
            )
        if selected_page_artifact_id != artifact.page_artifact_id:
            raise LocatorIdentityError(
                f"定位 {artifact.locator_id} 的页产物与完整修订页清单所选页不一致"
            )
        ocr_record = self.session.get(OCRPageRecord, artifact.ocr_page_id)
        if ocr_record is None:
            raise InvalidReferenceError(
                f"定位 {artifact.locator_id} 引用的 OCRPage {artifact.ocr_page_id} 不存在"
            )
        if ocr_record.page_artifact_id != artifact.page_artifact_id:
            raise LocatorIdentityError(
                f"定位 {artifact.locator_id} 的 OCRPage 与页产物归属不一致"
            )
        correction_repo = CorrectionRepository(self.session)
        selected_corrections = [
            correction_repo.get(correction_id)
            for correction_id in revision.correction_ids
        ]
        selected_corrections = [
            c for c in selected_corrections if c.ocr_page_id == artifact.ocr_page_id
        ]
        projection = project_effective_text(ocr_record.raw_text, selected_corrections)
        if artifact.source_text_sha256 != projection.effective_text_sha256:
            raise LocatorIdentityError(
                f"定位 {artifact.locator_id} 的源文本哈希与从完整修订重算的有效文本"
                "投影不一致"
            )
        if artifact.effective_text_sha256 != projection.effective_text_sha256:
            raise LocatorIdentityError(
                f"定位 {artifact.locator_id} 的投影哈希与重算结果不一致"
            )
        if artifact.precision in (LocatorPrecision.BBOX, LocatorPrecision.TEXT_RANGE):
            self._verify_range_on_text(
                artifact, projection.effective_text, "有效文本投影"
            )
        elif artifact.precision == LocatorPrecision.PAGE_EXCERPT:
            self._verify_excerpt_on_text(
                artifact, projection.effective_text, "有效文本投影"
            )
        if artifact.precision == LocatorPrecision.BBOX:
            raise LocatorIdentityError(
                "effective_text 投影没有持久化机器坐标 sidecar，拒绝 bbox"
                "（诚实降级为 text_range/excerpt/page_only）"
            )

    def _verify_source(self, artifact: EvidenceLocatorArtifact, batch=None) -> None:
        artifact_record = self.session.get(PageArtifactRecord, artifact.page_artifact_id)
        if artifact_record is None:
            raise InvalidReferenceError(
                f"定位 {artifact.locator_id} 引用的 PageArtifact "
                f"{artifact.page_artifact_id} 不存在"
            )
        if (
            artifact_record.source_document_version_id != artifact.source_document_version_id
            or artifact_record.page_number != artifact.page_number
        ):
            raise LocatorIdentityError(
                f"定位 {artifact.locator_id} 的资料版本/页码与页产物不一致"
            )

        if artifact.source_layer == LocatorSourceLayer.NATIVE_TEXT:
            self._verify_native(artifact, artifact_record)
        elif artifact.source_layer == LocatorSourceLayer.RAW_OCR:
            self._verify_raw_ocr(artifact, artifact_record)
        elif artifact.source_layer == LocatorSourceLayer.EFFECTIVE_TEXT:
            self._verify_effective_text(artifact)
        elif artifact.source_layer == LocatorSourceLayer.PAGE_REVIEW_VISUAL:
            from app.storage.page_review_visual_locator_validation import verify_visual_locator
            verify_visual_locator(self.session, artifact, batch=batch)
        else:
            raise LocatorIdentityError("该定位来源尚未接入原始记录核验，不能保存或采信")

    @staticmethod
    def _verify_range_on_text(
        artifact: EvidenceLocatorArtifact, source_text: str, label: str
    ) -> None:
        """范围必须在源文本内，且摘录（若有）必须逐字等于源文本对应切片。"""
        start, end = artifact.text_start, artifact.text_end
        if start is None or end is None:
            raise LocatorIdentityError("bbox/text_range 定位必须绑定具体原始字符范围")
        if not (0 <= start < end <= len(source_text)):
            raise LocatorIdentityError(
                f"定位 {artifact.locator_id} 的字符范围越出 {label}，无法证明目标范围"
            )
        if artifact.excerpt is not None and source_text[start:end] != artifact.excerpt:
            raise LocatorIdentityError(
                f"定位 {artifact.locator_id} 的摘录与 {label} 对应范围不一致"
            )

    @staticmethod
    def _verify_excerpt_on_text(
        artifact: EvidenceLocatorArtifact, source_text: str, label: str
    ) -> None:
        excerpt = artifact.excerpt
        if not excerpt or excerpt not in source_text:
            raise LocatorIdentityError(
                f"定位 {artifact.locator_id} 的页面摘录不能在 {label} 中回放证明"
            )

    def create(self, artifact: EvidenceLocatorArtifact, *, batch=None) -> EvidenceLocatorArtifact:
        created = self._prepare_create(artifact, batch=batch)
        self.session.add(created)
        _flush_guarded(self.session)
        return self.get(artifact.locator_id, batch=batch)

    def create_visual_many(self, artifacts: list[EvidenceLocatorArtifact]) -> list[EvidenceLocatorArtifact]:
        """Visual identity is its ID; source validation does not depend on this table."""
        from app.storage.page_review_visual_locator_validation import VisualLocatorBatchContext

        if any(item.source_layer != LocatorSourceLayer.PAGE_REVIEW_VISUAL for item in artifacts):
            raise InvalidReferenceError("批量保存仅用于原件判读定位")
        if len({item.locator_id for item in artifacts}) != len(artifacts):
            raise DuplicateRecordError("本批原件定位包含重复编号")
        batch = VisualLocatorBatchContext(self.session)
        # Validate every source before inserting anything; writes invalidate reuse.
        rows = [self._prepare_create(artifact, batch=batch) for artifact in artifacts]
        self.session.add_all(rows)
        _flush_guarded(self.session)
        return [self._decode(row) for row in rows]

    def _prepare_create(self, artifact: EvidenceLocatorArtifact, *, batch=None):
        existing = self.session.get(
            EvidenceLocatorArtifactRecord, artifact.locator_id
        )
        if existing is not None:
            raise DuplicateRecordError(
                f"定位旁路工件 {artifact.locator_id} 已存在，拒绝重复创建"
            )
        _require_artifact(artifact)
        self._verify_source(artifact, batch)
        row = self.session.execute(
            select(EvidenceLocatorArtifactRecord).where(
                *self._identity_conditions(artifact)
            )
        ).scalars().first()
        if row is not None:
            raise LocatorIdentityError(
                f"定位 {artifact.locator_id} 与既有定位 {row.locator_id} 属于同一 occurrence"
                "（页/来源层/原文哈希/原始范围/算法版本一致），身份碰撞，拒绝写入"
            )
        payload_json, payload_sha256 = encode_contract(artifact)
        created = EvidenceLocatorArtifactRecord(
            locator_id=artifact.locator_id,
            page_artifact_id=artifact.page_artifact_id,
            ocr_page_id=artifact.ocr_page_id,
            source_document_version_id=artifact.source_document_version_id,
            page_number=artifact.page_number,
            source_layer=artifact.source_layer.value,
            source_text_sha256=artifact.source_text_sha256,
            target_id=artifact.target_id,
            precision=artifact.precision.value,
            bbox_x0=artifact.bbox.x0 if artifact.bbox else None,
            bbox_y0=artifact.bbox.y0 if artifact.bbox else None,
            bbox_x1=artifact.bbox.x1 if artifact.bbox else None,
            bbox_y1=artifact.bbox.y1 if artifact.bbox else None,
            coordinate_space=(
                artifact.coordinate_frame.space.value
                if artifact.coordinate_frame
                else None
            ),
            frame_page_width=(
                artifact.coordinate_frame.page_width if artifact.coordinate_frame else None
            ),
            frame_page_height=(
                artifact.coordinate_frame.page_height if artifact.coordinate_frame else None
            ),
            frame_rotation=(
                artifact.coordinate_frame.rotation if artifact.coordinate_frame else None
            ),
            transform_version=(
                artifact.coordinate_frame.transform_version
                if artifact.coordinate_frame
                else None
            ),
            sidecar_sha256=artifact.sidecar_sha256,
            text_start=artifact.text_start,
            text_end=artifact.text_end,
            excerpt=artifact.excerpt,
            anchor_hash=artifact.anchor_hash,
            disambiguation=artifact.disambiguation.value,
            locator_algorithm_version=artifact.locator_algorithm_version,
            coordinate_transform_version=artifact.coordinate_transform_version,
            authenticity=artifact.authenticity.value,
            effective_text_sha256=artifact.effective_text_sha256,
            processing_revision_id=artifact.processing_revision_id,
            match_confidence=artifact.match_confidence,
            degradation_reason=artifact.degradation_reason,
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            created_at=to_utc_naive(artifact.created_at),
        )
        return created

    def get(self, locator_id: str, *, batch=None) -> EvidenceLocatorArtifact:
        record = _get_required(
            self.session, EvidenceLocatorArtifactRecord, locator_id, "EvidenceLocatorArtifact"
        )
        artifact = self._decode(record)
        self._verify_source(artifact, batch)
        return artifact

    def get_or_none(self, locator_id: str, *, batch=None) -> EvidenceLocatorArtifact | None:
        record = self.session.get(EvidenceLocatorArtifactRecord, locator_id)
        if record is None:
            return None
        artifact = self._decode(record)
        self._verify_source(artifact, batch)
        return artifact

    def get_many(self, locator_ids: list[str], *, batch=None) -> list[EvidenceLocatorArtifact]:
        """按调用方顺序一次取齐定位；缺失或损坏记录不得被静默省略。

        未显式传入 ``batch`` 时，本次调用内部共享一个批量核验上下文，
        同一事务内的重复修订核验只执行一次。
        """
        ordered_ids = list(dict.fromkeys(locator_ids))
        if not ordered_ids:
            return []
        if batch is None:
            from app.storage.page_review_visual_locator_validation import (
                VisualLocatorBatchContext,
            )
            batch = VisualLocatorBatchContext(self.session)
        rows = self.session.execute(
            select(EvidenceLocatorArtifactRecord).where(
                EvidenceLocatorArtifactRecord.locator_id.in_(ordered_ids)
            )
        ).scalars().all()
        by_id = {row.locator_id: row for row in rows}
        missing = [locator_id for locator_id in ordered_ids if locator_id not in by_id]
        if missing:
            raise NotFoundError(f"EvidenceLocatorArtifact 不存在: {missing}")
        artifacts = [self._decode(by_id[locator_id]) for locator_id in ordered_ids]
        for artifact in artifacts:
            self._verify_source(artifact, batch)
        return artifacts


# --------------------------------------------------------------------------- 风险


class OCRRiskScanRepository:
    """风险扫描：同一三元组幂等复用，flag 集合哈希不一致则冲突拒绝。"""

    def __init__(self, session) -> None:
        self.session = session

    @staticmethod
    def _decode_scan(record: OCRRiskScanRecord) -> OCRRiskScan:
        contract = decode_contract(OCRRiskScan, record.payload_json, record.payload_sha256)
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "OCRRiskScan",
            record,
            payload,
            {
                "scan_id": "scan_id",
                "ocr_page_id": "ocr_page_id",
                "raw_text_sha256": "raw_text_sha256",
                "scanner_rule_version": "scanner_rule_version",
                "flags_sha256": "flags_sha256",
                "coverage_status": "coverage_status",
            },
        )
        return contract

    @staticmethod
    def _decode_flag(record: OCRRiskFlagRecord) -> OcrRiskFlag:
        contract = decode_contract(OcrRiskFlag, record.payload_json, record.payload_sha256)
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "OCRRiskFlag",
            record,
            payload,
            {
                "risk_id": "risk_id",
                "kind": "kind",
                "level": "level",
                "text": "text",
                "text_start": "text_start",
                "text_end": "text_end",
                "detail": "detail",
                "rule_version": "rule_version",
            },
        )
        return contract

    def _verify_flag_anchored_to_raw(
        self, scan: OCRRiskScan, ocr_record: OCRPageRecord | OCRPage
    ) -> None:
        """每个 flag 的范围必须在 OCRPage 原文内，且文本逐字等于原文切片。

        风险扫描是原 OCR 的旁路工件：任何越界、错文本、哈希/规则版本漂移都拒绝，
        保证扫描前后 OCRPage.raw_text/hash 逐字不变。
        """
        raw = ocr_record.raw_text
        for flag in scan.flags:
            if not (0 <= flag.text_start < flag.text_end <= len(raw)):
                raise RiskScanConflictError(
                    f"风险条目 {flag.risk_id} 的范围越出 OCRPage 原文，拒绝写入/还原"
                )
            if raw[flag.text_start:flag.text_end] != flag.text:
                raise RiskScanConflictError(
                    f"风险条目 {flag.risk_id} 的文本与 OCRPage 原文对应范围不一致"
                )

    def _verify_scan_flags_from_rows(
        self,
        scan: OCRRiskScan,
        record: OCRRiskScanRecord,
        rows: list[OCRRiskFlagRecord],
        ocr_page: OCRPage,
    ) -> None:
        actual = [
            (
                flag.risk_id,
                flag.kind.value,
                flag.level.value,
                flag.text,
                flag.text_start,
                flag.text_end,
                flag.detail,
                flag.rule_version,
            )
            for flag in (self._decode_flag(row) for row in rows)
        ]
        expected = [
            (
                flag.risk_id,
                flag.kind.value,
                flag.level.value,
                flag.text,
                flag.text_start,
                flag.text_end,
                flag.detail,
                flag.rule_version,
            )
            for flag in sorted(scan.flags, key=lambda f: f.risk_id)
        ]
        if actual != expected:
            raise PersistedContractInvalid(
                f"风险扫描 {scan.scan_id} 的 flag 子表与 payload 不一致，拒绝还原合同"
            )
        # 回读时逐 flag 回验：行 raw 哈希/规则版本镜像列与扫描一致，且锚定 OCRPage 原文。
        for row in rows:
            if row.raw_text_sha256 != scan.raw_text_sha256:
                raise PersistedContractInvalid(
                    f"风险条目 {row.flag_id} 的 raw_text_sha256 与扫描不一致"
                )
            if row.rule_version != record.scanner_rule_version:
                raise PersistedContractInvalid(
                    f"风险条目 {row.flag_id} 的 rule_version 与扫描规则版本不一致"
                )
        if ocr_page.raw_text_sha256 != scan.raw_text_sha256:
            raise PersistedContractInvalid(
                f"风险扫描 {scan.scan_id} 的 raw_text_sha256 与 OCRPage 不一致"
            )
        self._verify_flag_anchored_to_raw(scan, ocr_page)

    def _decode_records(
        self, records: list[OCRRiskScanRecord]
    ) -> dict[str, OCRRiskScan]:
        if not records:
            return {}
        scan_ids = {record.scan_id for record in records}
        flag_rows = self.session.execute(
            select(OCRRiskFlagRecord)
            .where(OCRRiskFlagRecord.scan_id.in_(scan_ids))
            .order_by(OCRRiskFlagRecord.scan_id, OCRRiskFlagRecord.risk_id)
        ).scalars().all()
        flags_by_scan: dict[str, list[OCRRiskFlagRecord]] = {
            scan_id: [] for scan_id in scan_ids
        }
        for row in flag_rows:
            flags_by_scan[row.scan_id].append(row)

        page_ids = list(dict.fromkeys(record.ocr_page_id for record in records))
        pages = OcrPageRepository(self.session).get_many(page_ids)
        pages_by_id = {page.ocr_page_id: page for page in pages}
        decoded: dict[str, OCRRiskScan] = {}
        for record in records:
            scan = self._decode_scan(record)
            self._verify_scan_flags_from_rows(
                scan,
                record,
                flags_by_scan[scan.scan_id],
                pages_by_id[scan.ocr_page_id],
            )
            decoded[scan.scan_id] = scan
        return decoded

    def _verify_scan_flags(self, scan: OCRRiskScan, record: OCRRiskScanRecord) -> None:
        rows = self.session.execute(
            select(OCRRiskFlagRecord)
            .where(OCRRiskFlagRecord.scan_id == scan.scan_id)
            .order_by(OCRRiskFlagRecord.risk_id)
        ).scalars().all()
        ocr_page = OcrPageRepository(self.session).get(scan.ocr_page_id)
        self._verify_scan_flags_from_rows(scan, record, rows, ocr_page)

    def get_or_create(self, scan: OCRRiskScan) -> tuple[OCRRiskScan, bool]:
        existing = self.session.execute(
            select(OCRRiskScanRecord)
            .where(OCRRiskScanRecord.ocr_page_id == scan.ocr_page_id)
            .where(OCRRiskScanRecord.raw_text_sha256 == scan.raw_text_sha256)
            .where(OCRRiskScanRecord.scanner_rule_version == scan.scanner_rule_version)
        ).scalars().first()
        if existing is not None:
            if existing.flags_sha256 != scan.flags_sha256:
                raise RiskScanConflictError(
                    f"同一风险扫描三元组已存在（scan {existing.scan_id}）但 flag 集合"
                    "哈希不一致，规则版本变化应新建扫描而非复用"
                )
            return self.get(existing.scan_id), False

        ocr_record = self.session.get(OCRPageRecord, scan.ocr_page_id)
        if ocr_record is None:
            raise InvalidReferenceError(f"风险扫描 {scan.scan_id} 引用的 OCRPage 不存在")
        if ocr_record.raw_text_sha256 != scan.raw_text_sha256:
            raise RiskScanConflictError(
                f"风险扫描 {scan.scan_id} 的 raw_text_sha256 与 OCRPage 不一致"
            )
        self._verify_flag_anchored_to_raw(scan, ocr_record)

        scan_json, scan_sha = encode_contract(scan)
        self.session.add(
            OCRRiskScanRecord(
                scan_id=scan.scan_id,
                ocr_page_id=scan.ocr_page_id,
                raw_text_sha256=scan.raw_text_sha256,
                scanner_rule_version=scan.scanner_rule_version,
                flags_sha256=scan.flags_sha256,
                coverage_status=scan.coverage_status,
                payload_json=scan_json,
                payload_sha256=scan_sha,
                created_at=to_utc_naive(scan.created_at),
            )
        )
        _flush_guarded(self.session)
        for flag in scan.flags:
            flag_json, flag_sha = encode_contract(flag)
            self.session.add(
                OCRRiskFlagRecord(
                    flag_id=f"{scan.scan_id}:{flag.risk_id}",
                    scan_id=scan.scan_id,
                    risk_id=flag.risk_id,
                    ocr_page_id=scan.ocr_page_id,
                    raw_text_sha256=scan.raw_text_sha256,
                    kind=flag.kind.value,
                    level=flag.level.value,
                    text=flag.text,
                    text_start=flag.text_start,
                    text_end=flag.text_end,
                    detail=flag.detail,
                    rule_version=flag.rule_version,
                    payload_json=flag_json,
                    payload_sha256=flag_sha,
                    created_at=to_utc_naive(scan.created_at),
                )
            )
        _flush_guarded(self.session)
        return self.get(scan.scan_id), True

    def get(self, scan_id: str) -> OCRRiskScan:
        record = _get_required(self.session, OCRRiskScanRecord, scan_id, "OCRRiskScan")
        scan = self._decode_scan(record)
        self._verify_scan_flags(scan, record)
        return scan

    def get_many(self, scan_ids: list[str]) -> list[OCRRiskScan]:
        """按冻结 ID 保序批量读取，逐扫描验证 payload、flag 子表与 OCR 闭包。"""
        if not scan_ids:
            return []
        rows = self.session.execute(
            select(OCRRiskScanRecord).where(
                OCRRiskScanRecord.scan_id.in_(set(scan_ids))
            )
        ).scalars().all()
        by_id = {row.scan_id: row for row in rows}
        missing = next((scan_id for scan_id in scan_ids if scan_id not in by_id), None)
        if missing is not None:
            _get_required(self.session, OCRRiskScanRecord, missing, "OCRRiskScan")
        decoded = self._decode_records(rows)
        return [decoded[scan_id] for scan_id in scan_ids]

    def list_by_pages(self, ocr_page_ids: list[str]) -> list[OCRRiskScan]:
        """一次读取多页全部扫描，仍对每个扫描执行完整来源闭包校验。"""
        if not ocr_page_ids:
            return []
        rows = self.session.execute(
            select(OCRRiskScanRecord)
            .where(OCRRiskScanRecord.ocr_page_id.in_(set(ocr_page_ids)))
            .order_by(
                OCRRiskScanRecord.ocr_page_id,
                OCRRiskScanRecord.created_at,
                OCRRiskScanRecord.scan_id,
            )
        ).scalars().all()
        decoded = self._decode_records(rows)
        return [decoded[row.scan_id] for row in rows]

    def list_by_page(self, ocr_page_id: str) -> list[OCRRiskScan]:
        rows = self.session.execute(
            select(OCRRiskScanRecord)
            .where(OCRRiskScanRecord.ocr_page_id == ocr_page_id)
            .order_by(OCRRiskScanRecord.created_at, OCRRiskScanRecord.scan_id)
        ).scalars().all()
        return [self.get(row.scan_id) for row in rows]


class OCRRiskReviewRepository:
    """风险核对决议：追加写；blocking 风险是否被完整修订选中由闭包门禁负责。"""

    def __init__(self, session) -> None:
        self.session = session

    @staticmethod
    def _decode(record: OCRRiskReviewRecord) -> OCRRiskReview:
        contract = decode_contract(OCRRiskReview, record.payload_json, record.payload_sha256)
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "OCRRiskReview",
            record,
            payload,
            {
                "review_id": "review_id",
                "risk_flag_id": "risk_flag_id",
                "decision": "decision",
                "reason": "reason",
                "actor": "actor",
                "base_processing_revision_id": "base_processing_revision_id",
                "expected_revision": "expected_revision",
            },
        )
        return contract

    def create(self, review: OCRRiskReview) -> OCRRiskReview:
        if self.session.get(OCRRiskReviewRecord, review.review_id) is not None:
            raise DuplicateRecordError(f"风险核对 {review.review_id} 已存在，拒绝重复创建")
        flag_record = self.session.get(OCRRiskFlagRecord, review.risk_flag_id)
        if flag_record is None:
            raise InvalidReferenceError(
                f"风险核对 {review.review_id} 引用的风险条目 {review.risk_flag_id} 不存在"
            )
        _verify_base_revision_scope(
            self.session,
            review.base_processing_revision_id,
            ocr_page_id=flag_record.ocr_page_id,
        )
        payload_json, payload_sha256 = encode_contract(review)
        self.session.add(
            OCRRiskReviewRecord(
                review_id=review.review_id,
                risk_flag_id=review.risk_flag_id,
                decision=review.decision.value,
                reason=review.reason,
                actor=review.actor,
                base_processing_revision_id=review.base_processing_revision_id,
                expected_revision=review.expected_revision,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                created_at=to_utc_naive(review.created_at),
            )
        )
        _flush_guarded(self.session)
        return self.get(review.review_id)

    def get(self, review_id: str) -> OCRRiskReview:
        record = _get_required(self.session, OCRRiskReviewRecord, review_id, "OCRRiskReview")
        return self._decode(record)

    def get_many(self, review_ids: list[str]) -> list[OCRRiskReview]:
        """按冻结 ID 保序批量还原核对决议并执行合同/镜像校验。"""
        if not review_ids:
            return []
        rows = self.session.execute(
            select(OCRRiskReviewRecord).where(
                OCRRiskReviewRecord.review_id.in_(set(review_ids))
            )
        ).scalars().all()
        by_id = {row.review_id: row for row in rows}
        missing = next(
            (review_id for review_id in review_ids if review_id not in by_id), None
        )
        if missing is not None:
            _get_required(self.session, OCRRiskReviewRecord, missing, "OCRRiskReview")
        return [self._decode(by_id[review_id]) for review_id in review_ids]

    def list_for_flags(
        self,
        flag_ids: set[str],
        *,
        base_processing_revision_id: str,
    ) -> list[OCRRiskReview]:
        """批量读取候选风险的核对，只返回指定 base 修订作用域。"""
        if not flag_ids:
            return []
        rows = self.session.execute(
            select(OCRRiskReviewRecord)
            .where(OCRRiskReviewRecord.risk_flag_id.in_(flag_ids))
            .order_by(OCRRiskReviewRecord.created_at, OCRRiskReviewRecord.review_id)
        ).scalars().all()
        reviews = [self._decode(row) for row in rows]
        return [
            review
            for review in reviews
            if review.base_processing_revision_id == base_processing_revision_id
        ]

    def reviewed_flag_ids(self, flag_ids: list[str]) -> set[str]:
        """返回候选 flag 集合中已存在至少一条核对决议的 flag_id（供页级原子核对求差）。"""
        if not flag_ids:
            return set()
        rows = self.session.execute(
            select(OCRRiskReviewRecord.risk_flag_id).where(
                OCRRiskReviewRecord.risk_flag_id.in_(flag_ids)
            )
        ).scalars()
        return set(rows)


class OCRRiskPageReviewRepository:
    """页级原子风险核对：追加写审计记录 + 覆盖集合/逐条物化一致性校验。

    页级核对把「对照原件后本页待核对项一次确认」收敛为单事务原子动作；本仓储负责
    校验该动作的来源快照（扫描/原文哈希/规则版本）与逐条不可变 ``OCRRiskReview``
    的物化一一对应，缺项/多换/错绑在写入与回放时都被拒绝。
    """

    def __init__(self, session) -> None:
        self.session = session

    @staticmethod
    def _decode(record: OCRRiskPageReviewRecord) -> OCRRiskPageReview:
        contract = decode_contract(
            OCRRiskPageReview, record.payload_json, record.payload_sha256
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "OCRRiskPageReview",
            record,
            payload,
            {
                "page_review_id": "page_review_id",
                "ocr_page_id": "ocr_page_id",
                "scan_id": "scan_id",
                "raw_text_sha256": "raw_text_sha256",
                "scanner_rule_version": "scanner_rule_version",
                "decision": "decision",
                "reason": "reason",
                "actor": "actor",
                "base_processing_revision_id": "base_processing_revision_id",
                "expected_revision": "expected_revision",
                "covered_flag_ids": "covered_flag_ids",
                "created_review_ids": "created_review_ids",
                "covered_flag_sha256": "covered_flag_sha256",
            },
        )
        return contract

    def _verify_atomic_closure(self, page_review: OCRRiskPageReview) -> None:
        scan = OCRRiskScanRepository(self.session).get(page_review.scan_id)
        if scan.ocr_page_id != page_review.ocr_page_id:
            raise RiskPageReviewAtomicityError(
                f"页级核对 {page_review.page_review_id} 的扫描不属于页 "
                f"{page_review.ocr_page_id}"
            )
        if scan.raw_text_sha256 != page_review.raw_text_sha256:
            raise RiskPageReviewAtomicityError(
                f"页级核对 {page_review.page_review_id} 的 raw_text_sha256 与扫描不一致"
            )
        if scan.scanner_rule_version != page_review.scanner_rule_version:
            raise RiskPageReviewAtomicityError(
                f"页级核对 {page_review.page_review_id} 的 scanner_rule_version 与扫描不一致"
            )
        from app.domain.publication import canonical_hash

        expected_sha = canonical_hash(sorted(page_review.covered_flag_ids))
        if page_review.covered_flag_sha256 != expected_sha:
            raise PersistedContractInvalid(
                f"页级核对 {page_review.page_review_id} 的 covered_flag_sha256 "
                "与覆盖集合不一致"
            )
        covered = set(page_review.covered_flag_ids)
        if len(covered) != len(page_review.covered_flag_ids):
            raise RiskPageReviewAtomicityError(
                f"页级核对 {page_review.page_review_id} 覆盖集合存在重复 flag_id"
            )
        review_repo = OCRRiskReviewRepository(self.session)
        mapped: dict[str, str] = {}
        for review_id in page_review.created_review_ids:
            review = review_repo.get(review_id)
            flag_id = review.risk_flag_id
            if flag_id not in covered:
                raise RiskPageReviewAtomicityError(
                    f"逐条核对 {review_id} 的 risk_flag_id {flag_id} 不在覆盖集合中"
                )
            if flag_id in mapped:
                raise RiskPageReviewAtomicityError(
                    f"覆盖 flag {flag_id} 存在多条物化逐条核对，破坏原子一一对应"
                )
            if review.base_processing_revision_id != page_review.base_processing_revision_id:
                raise RiskPageReviewAtomicityError(
                    f"逐条核对 {review_id} 的 base_processing_revision_id 与页级核对不一致"
                )
            mapped[flag_id] = review_id
        if set(mapped) != covered:
            missing = sorted(covered - set(mapped))
            raise RiskPageReviewAtomicityError(
                f"覆盖 flag 缺少物化逐条核对: {missing}"
            )

    def create(self, page_review: OCRRiskPageReview) -> OCRRiskPageReview:
        if self.session.get(OCRRiskPageReviewRecord, page_review.page_review_id) is not None:
            raise DuplicateRecordError(
                f"页级核对 {page_review.page_review_id} 已存在，拒绝重复创建"
            )
        if self.session.get(OCRPageRecord, page_review.ocr_page_id) is None:
            raise InvalidReferenceError(
                f"页级核对 {page_review.page_review_id} 引用的 OCRPage 不存在"
            )
        _verify_base_revision_scope(
            self.session,
            page_review.base_processing_revision_id,
            ocr_page_id=page_review.ocr_page_id,
        )
        self._verify_atomic_closure(page_review)
        payload_json, payload_sha256 = encode_contract(page_review)
        self.session.add(
            OCRRiskPageReviewRecord(
                page_review_id=page_review.page_review_id,
                ocr_page_id=page_review.ocr_page_id,
                scan_id=page_review.scan_id,
                raw_text_sha256=page_review.raw_text_sha256,
                scanner_rule_version=page_review.scanner_rule_version,
                decision=page_review.decision.value,
                reason=page_review.reason,
                actor=page_review.actor,
                base_processing_revision_id=page_review.base_processing_revision_id,
                expected_revision=page_review.expected_revision,
                covered_flag_ids=list(page_review.covered_flag_ids),
                created_review_ids=list(page_review.created_review_ids),
                covered_flag_sha256=page_review.covered_flag_sha256,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                created_at=to_utc_naive(page_review.created_at),
            )
        )
        _flush_guarded(self.session)
        return self.get(page_review.page_review_id)

    def get(self, page_review_id: str) -> OCRRiskPageReview:
        record = _get_required(
            self.session, OCRRiskPageReviewRecord, page_review_id, "OCRRiskPageReview"
        )
        page_review = self._decode(record)
        self._verify_atomic_closure(page_review)
        return page_review

    def list_by_page(self, ocr_page_id: str) -> list[OCRRiskPageReview]:
        rows = self.session.execute(
            select(OCRRiskPageReviewRecord)
            .where(OCRRiskPageReviewRecord.ocr_page_id == ocr_page_id)
            .order_by(OCRRiskPageReviewRecord.created_at, OCRRiskPageReviewRecord.page_review_id)
        ).scalars().all()
        return [self.get(row.page_review_id) for row in rows]


# --------------------------------------------------------------------------- 校对


class CorrectionRepository:
    """校对覆盖层记录：追加写 + supersede 链 + 原文本范围回验。"""

    def __init__(self, session) -> None:
        self.session = session

    @staticmethod
    def _decode(record: CorrectionRecordRecord) -> CorrectionRecord:
        contract = decode_contract(
            CorrectionRecord, record.payload_json, record.payload_sha256
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "CorrectionRecord",
            record,
            payload,
            {
                "correction_id": "correction_id",
                "ocr_page_id": "ocr_page_id",
                "raw_text_sha256": "raw_text_sha256",
                "text_start": "text_start",
                "text_end": "text_end",
                "original_text": "original_text",
                "corrected_text": "corrected_text",
                "change_kind": "change_kind",
                "requires_confirmation": "requires_confirmation",
                "confirmation_actor": "confirmation_actor",
                "confirmation_at": "confirmation_at",
                "reason": "reason",
                "actor": "actor",
                "base_processing_revision_id": "base_processing_revision_id",
                "supersedes_correction_id": "supersedes_correction_id",
            },
        )
        return contract

    def create(self, correction: CorrectionRecord) -> CorrectionRecord:
        if self.session.get(CorrectionRecordRecord, correction.correction_id) is not None:
            raise DuplicateRecordError(f"校对记录 {correction.correction_id} 已存在")
        ocr_record = self.session.get(OCRPageRecord, correction.ocr_page_id)
        if ocr_record is None:
            raise InvalidReferenceError(
                f"校对 {correction.correction_id} 引用的 OCRPage 不存在"
            )
        if ocr_record.raw_text_sha256 != correction.raw_text_sha256:
            raise CorrectionOverlapError(
                f"校对 {correction.correction_id} 的 raw_text_sha256 与 OCRPage 不一致"
            )
        try:
            validate_correction_source_anchor(
                ocr_record.raw_text,
                text_start=correction.text_start,
                text_end=correction.text_end,
                original_text=correction.original_text,
            )
        except ValueError as error:
            raise CorrectionOverlapError(
                f"校对 {correction.correction_id} 的来源锚点无效：{error}"
            ) from error
        _verify_base_revision_scope(
            self.session,
            correction.base_processing_revision_id,
            ocr_page_id=correction.ocr_page_id,
        )
        occurrence_rows = self.session.execute(
            select(CorrectionRecordRecord).where(
                CorrectionRecordRecord.base_processing_revision_id
                == correction.base_processing_revision_id,
                CorrectionRecordRecord.ocr_page_id == correction.ocr_page_id,
                CorrectionRecordRecord.raw_text_sha256 == correction.raw_text_sha256,
                CorrectionRecordRecord.text_start == correction.text_start,
                CorrectionRecordRecord.text_end == correction.text_end,
                CorrectionRecordRecord.original_text == correction.original_text,
            )
        ).scalars().all()
        if correction.supersedes_correction_id is None and occurrence_rows:
            raise CorrectionOverlapError(
                f"校对 {correction.correction_id} 对应的原文范围已有校对链；"
                "后续校对必须明确替代该链当前版本，不能创建第二个起始版本"
            )
        if correction.supersedes_correction_id is not None:
            superseded = self.session.get(
                CorrectionRecordRecord, correction.supersedes_correction_id
            )
            if superseded is None:
                raise InvalidReferenceError(
                    f"校对 {correction.correction_id} 替代的校对 "
                    f"{correction.supersedes_correction_id} 不存在"
                )
            superseded_payload = json.loads(superseded.payload_json)
            # 替代关系必须绑定同一 OCR 页、同一 raw 哈希、同一原始范围（同 occurrence）。
            for key in (
                "ocr_page_id",
                "raw_text_sha256",
                "text_start",
                "text_end",
                "original_text",
            ):
                if superseded_payload[key] != getattr(correction, key):
                    raise CorrectionOverlapError(
                        f"校对 {correction.correction_id} 只能替代同页同 raw 哈希同"
                        f"原始范围的校对（{key} 不一致）"
                    )
            # 必须使用同一 base 修订，且只能替代当前链头（防止分支/跳链）。
            if superseded_payload["base_processing_revision_id"] != (
                correction.base_processing_revision_id
            ):
                raise CorrectionOverlapError(
                    f"校对 {correction.correction_id} 必须使用与被替代校对相同的 base 修订"
                )
            # 当前链头 = 没有任何后继校对替代它。
            has_successor = self.session.execute(
                select(func.count())
                .select_from(CorrectionRecordRecord)
                .where(
                    CorrectionRecordRecord.supersedes_correction_id
                    == correction.supersedes_correction_id
                )
            ).scalar_one()
            if has_successor:
                raise CorrectionOverlapError(
                    f"校对 {correction.correction_id} 只能替代当前链头 "
                    f"{correction.supersedes_correction_id}（已存在后继，拒绝分支/跳链）"
                )
        payload_json, payload_sha256 = encode_contract(correction)
        self.session.add(
            CorrectionRecordRecord(
                correction_id=correction.correction_id,
                ocr_page_id=correction.ocr_page_id,
                raw_text_sha256=correction.raw_text_sha256,
                text_start=correction.text_start,
                text_end=correction.text_end,
                original_text=correction.original_text,
                corrected_text=correction.corrected_text,
                change_kind=correction.change_kind.value,
                requires_confirmation=correction.requires_confirmation,
                confirmation_actor=correction.confirmation_actor,
                confirmation_at=(
                    to_utc_naive(correction.confirmation_at)
                    if correction.confirmation_at
                    else None
                ),
                reason=correction.reason,
                actor=correction.actor,
                base_processing_revision_id=correction.base_processing_revision_id,
                supersedes_correction_id=correction.supersedes_correction_id,
                affected_scope_json=correction.affected_scope,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                created_at=to_utc_naive(correction.created_at),
            )
        )
        _flush_guarded(self.session)
        return self.get(correction.correction_id)

    def get(self, correction_id: str) -> CorrectionRecord:
        record = _get_required(
            self.session, CorrectionRecordRecord, correction_id, "CorrectionRecord"
        )
        return self._decode(record)

    def get_many(self, correction_ids: list[str]) -> list[CorrectionRecord]:
        """按冻结 ID 保序批量还原校对并执行合同/镜像校验。"""
        if not correction_ids:
            return []
        rows = self.session.execute(
            select(CorrectionRecordRecord).where(
                CorrectionRecordRecord.correction_id.in_(set(correction_ids))
            )
        ).scalars().all()
        by_id = {row.correction_id: row for row in rows}
        missing = next(
            (
                correction_id
                for correction_id in correction_ids
                if correction_id not in by_id
            ),
            None,
        )
        if missing is not None:
            _get_required(
                self.session, CorrectionRecordRecord, missing, "CorrectionRecord"
            )
        return [self._decode(by_id[item_id]) for item_id in correction_ids]

    def list_by_pages(
        self,
        ocr_page_ids: list[str],
        *,
        base_processing_revision_id: str,
    ) -> list[CorrectionRecord]:
        """批量读取多页校对，只返回指定 base 修订作用域。"""
        if not ocr_page_ids:
            return []
        rows = self.session.execute(
            select(CorrectionRecordRecord)
            .where(CorrectionRecordRecord.ocr_page_id.in_(set(ocr_page_ids)))
            .order_by(
                CorrectionRecordRecord.ocr_page_id,
                CorrectionRecordRecord.text_start,
                CorrectionRecordRecord.correction_id,
            )
        ).scalars().all()
        corrections = [self._decode(row) for row in rows]
        return [
            correction
            for correction in corrections
            if correction.base_processing_revision_id == base_processing_revision_id
        ]

    def list_by_page(self, ocr_page_id: str) -> list[CorrectionRecord]:
        rows = self.session.execute(
            select(CorrectionRecordRecord)
            .where(CorrectionRecordRecord.ocr_page_id == ocr_page_id)
            .order_by(CorrectionRecordRecord.text_start, CorrectionRecordRecord.correction_id)
        ).scalars().all()
        return [self._decode(row) for row in rows]


# --------------------------------------------------------------------------- 被提及资料


class ReferencedDocumentRepository:
    """被提及资料登记修订 + 满足修订（两层追加写链）。"""

    def __init__(self, session) -> None:
        self.session = session

    @staticmethod
    def _decode_revision(record: ReferencedDocumentRevisionRecord) -> ReferencedDocumentRevision:
        contract = decode_contract(
            ReferencedDocumentRevision, record.payload_json, record.payload_sha256
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "ReferencedDocumentRevision",
            record,
            payload,
            {
                "revision_id": "revision_id",
                "referenced_document_id": "referenced_document_id",
                "project_id": "project_id",
                "subject_id": "subject_id",
                "review_episode_id": "review_episode_id",
                "description": "description",
                "document_type": "document_type",
                "source_party": "source_party",
                "trigger_locator_id": "trigger_locator_id",
                "origin": "origin",
                "pattern_version": "pattern_version",
                "status": "status",
                "revision": "revision",
                "supersedes_revision_id": "supersedes_revision_id",
                "created_by": "created_by",
            },
        )
        return contract

    @staticmethod
    def _decode_resolution(
        record: ReferencedDocumentResolutionRevisionRecord,
    ) -> ReferencedDocumentResolutionRevision:
        contract = decode_contract(
            ReferencedDocumentResolutionRevision,
            record.payload_json,
            record.payload_sha256,
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "ReferencedDocumentResolutionRevision",
            record,
            payload,
            {
                "resolution_revision_id": "resolution_revision_id",
                "referenced_document_id": "referenced_document_id",
                "status": "status",
                "source_document_version_id": "source_document_version_id",
                "revision": "revision",
                "supersedes_resolution_revision_id": "supersedes_resolution_revision_id",
                "created_by": "created_by",
            },
        )
        return contract

    def _next_revision(self, table, doc_column: str, referenced_document_id: str) -> int:
        current = self.session.execute(
            select(func.max(table.c.revision)).where(
                table.c[doc_column] == referenced_document_id
            )
        ).scalar_one()
        return (current or 0) + 1

    def _verify_trigger_scope(
        self, revision: ReferencedDocumentRevision, locator: EvidenceLocatorArtifactRecord
    ) -> None:
        """触发定位必须与被提及资料属于同一 project/subject/review episode。"""
        document = self.session.get(
            SourceDocumentVersionV2Record, locator.source_document_version_id
        )
        if document is None:
            raise InvalidReferenceError(
                f"触发定位 {locator.locator_id} 的资料版本不存在"
            )
        if (
            document.project_id != revision.project_id
            or document.subject_id != revision.subject_id
            or document.review_episode_id != revision.review_episode_id
        ):
            raise Slice44RepositoryError(
                f"触发定位 {locator.locator_id} 与被提及资料 {revision.revision_id} "
                "不属于同一 project/subject/review episode，拒绝跨作用域触发"
            )

    def create_revision(
        self, revision: ReferencedDocumentRevision
    ) -> ReferencedDocumentRevision:
        if self.session.get(ReferencedDocumentRevisionRecord, revision.revision_id) is not None:
            raise DuplicateRecordError(f"被提及资料修订 {revision.revision_id} 已存在")
        expected = self._next_revision(
            ReferencedDocumentRevisionRecord.__table__,
            "referenced_document_id",
            revision.referenced_document_id,
        )
        if revision.revision != expected:
            raise CandidateStateTransitionError(
                f"被提及资料 {revision.referenced_document_id} 的修订号应为 {expected}，"
                f"得到 {revision.revision}"
            )
        if revision.supersedes_revision_id is not None:
            superseded = self.session.get(
                ReferencedDocumentRevisionRecord, revision.supersedes_revision_id
            )
            if superseded is None:
                raise InvalidReferenceError(
                    f"被提及资料修订 {revision.revision_id} 替代的修订不存在"
                )
            if json.loads(superseded.payload_json)["referenced_document_id"] != (
                revision.referenced_document_id
            ):
                raise CandidateStateTransitionError("被提及资料修订只能替代同资料链修订")
            successor = self.session.execute(
                select(ReferencedDocumentRevisionRecord).where(
                    ReferencedDocumentRevisionRecord.supersedes_revision_id
                    == revision.supersedes_revision_id
                )
            ).scalars().first()
            if successor is not None:
                raise CandidateStateTransitionError(
                    "被提及资料修订只能替代当前链头（已存在后继，拒绝分支）"
                )
        if revision.trigger_locator_id is not None:
            locator = self.session.get(
                EvidenceLocatorArtifactRecord, revision.trigger_locator_id
            )
            if locator is None:
                raise InvalidReferenceError(
                    f"被提及资料 {revision.revision_id} 的触发定位不存在"
                )
            self._verify_trigger_scope(revision, locator)
        payload_json, payload_sha256 = encode_contract(revision)
        self.session.add(
            ReferencedDocumentRevisionRecord(
                revision_id=revision.revision_id,
                referenced_document_id=revision.referenced_document_id,
                project_id=revision.project_id,
                subject_id=revision.subject_id,
                review_episode_id=revision.review_episode_id,
                description=revision.description,
                document_type=revision.document_type,
                source_party=revision.source_party,
                trigger_locator_id=revision.trigger_locator_id,
                origin=revision.origin.value,
                pattern_version=revision.pattern_version,
                status=revision.status.value,
                revision=revision.revision,
                supersedes_revision_id=revision.supersedes_revision_id,
                created_by=revision.created_by,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                created_at=to_utc_naive(revision.created_at),
            )
        )
        _flush_guarded(self.session)
        return self.get_revision(revision.revision_id)

    def get_revision(self, revision_id: str) -> ReferencedDocumentRevision:
        record = _get_required(
            self.session, ReferencedDocumentRevisionRecord, revision_id, "ReferencedDocumentRevision"
        )
        return self._decode_revision(record)

    def create_resolution(
        self, resolution: ReferencedDocumentResolutionRevision
    ) -> ReferencedDocumentResolutionRevision:
        if self.session.get(
            ReferencedDocumentResolutionRevisionRecord, resolution.resolution_revision_id
        ) is not None:
            raise DuplicateRecordError(f"满足修订 {resolution.resolution_revision_id} 已存在")
        expected = self._next_revision(
            ReferencedDocumentResolutionRevisionRecord.__table__,
            "referenced_document_id",
            resolution.referenced_document_id,
        )
        if resolution.revision != expected:
            raise CandidateStateTransitionError(
                f"被提及资料 {resolution.referenced_document_id} 的满足修订号应为 "
                f"{expected}，得到 {resolution.revision}"
            )
        if resolution.supersedes_resolution_revision_id is not None:
            superseded = self.session.get(
                ReferencedDocumentResolutionRevisionRecord,
                resolution.supersedes_resolution_revision_id,
            )
            if superseded is None or json.loads(superseded.payload_json)[
                "referenced_document_id"
            ] != resolution.referenced_document_id:
                raise CandidateStateTransitionError(
                    "满足修订只能替代同资料的满足链修订"
                )
            successor = self.session.execute(
                select(ReferencedDocumentResolutionRevisionRecord).where(
                    ReferencedDocumentResolutionRevisionRecord.supersedes_resolution_revision_id
                    == resolution.supersedes_resolution_revision_id
                )
            ).scalars().first()
            if successor is not None:
                raise CandidateStateTransitionError(
                    "满足修订只能替代当前链头（已存在后继，拒绝分支）"
                )
        if resolution.status == ReferencedDocumentResolutionStatus.PROVIDED:
            self._validate_provided_resolution_scope(resolution)
        # 满足修订必须挂接既有的被提及资料修订链（不允许孤儿满足记录）。
        chain_exists = self.session.execute(
            select(func.count())
            .select_from(ReferencedDocumentRevisionRecord)
            .where(
                ReferencedDocumentRevisionRecord.referenced_document_id
                == resolution.referenced_document_id
            )
        ).scalar_one()
        if not chain_exists:
            raise InvalidReferenceError(
                f"满足修订 {resolution.resolution_revision_id} 引用的被提及资料 "
                f"{resolution.referenced_document_id} 没有任何登记修订链，拒绝孤儿满足记录"
            )
        payload_json, payload_sha256 = encode_contract(resolution)
        self.session.add(
            ReferencedDocumentResolutionRevisionRecord(
                resolution_revision_id=resolution.resolution_revision_id,
                referenced_document_id=resolution.referenced_document_id,
                status=resolution.status.value,
                source_document_version_id=resolution.source_document_version_id,
                revision=resolution.revision,
                supersedes_resolution_revision_id=resolution.supersedes_resolution_revision_id,
                created_by=resolution.created_by,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                created_at=to_utc_naive(resolution.created_at),
            )
        )
        _flush_guarded(self.session)
        return self.get_resolution(resolution.resolution_revision_id)

    def _validate_provided_resolution_scope(
        self, resolution: ReferencedDocumentResolutionRevision
    ) -> None:
        """仓储兜底：满足资料必须属于同 scope 的当前活动快照。"""
        source_document = self.session.get(
            SourceDocumentVersionV2Record, resolution.source_document_version_id
        )
        if source_document is None:
            raise InvalidReferenceError(
                f"满足修订 {resolution.resolution_revision_id} 引用的资料版本不存在"
            )
        rows = self.session.execute(
            select(ReferencedDocumentRevisionRecord).where(
                ReferencedDocumentRevisionRecord.referenced_document_id
                == resolution.referenced_document_id
            )
        ).scalars().all()
        superseded_ids = {
            row.supersedes_revision_id
            for row in rows
            if row.supersedes_revision_id is not None
        }
        heads = [row for row in rows if row.revision_id not in superseded_ids]
        if len(heads) != 1:
            raise Slice44RepositoryError(
                "被提及资料登记链缺少唯一当前修订，不能建立满足关系"
            )
        referenced_document = self._decode_revision(heads[0])
        expected_scope = (
            referenced_document.project_id,
            referenced_document.subject_id,
            referenced_document.review_episode_id,
        )
        actual_scope = (
            source_document.project_id,
            source_document.subject_id,
            source_document.review_episode_id,
        )
        if actual_scope != expected_scope:
            raise Slice44RepositoryError(
                "被提及资料满足关系不能绑定其他项目、受试者或审核节点的资料版本"
            )
        episode = EpisodeRepository(self.session).get(
            referenced_document.review_episode_id
        )
        if episode.active_evidence_snapshot_id is None:
            raise Slice44RepositoryError(
                "审核节点尚无当前活动资料快照，不能建立已提供满足关系"
            )
        member = self.session.execute(
            select(EvidenceSnapshotMemberRecord).where(
                EvidenceSnapshotMemberRecord.snapshot_id
                == episode.active_evidence_snapshot_id,
                EvidenceSnapshotMemberRecord.source_document_version_id
                == resolution.source_document_version_id,
            )
        ).scalars().first()
        if member is None:
            raise Slice44RepositoryError(
                "被提及资料满足关系只能绑定当前活动资料快照中的成员"
            )

    def get_resolution(
        self, resolution_revision_id: str
    ) -> ReferencedDocumentResolutionRevision:
        record = _get_required(
            self.session,
            ReferencedDocumentResolutionRevisionRecord,
            resolution_revision_id,
            "ReferencedDocumentResolutionRevision",
        )
        return self._decode_resolution(record)


# --------------------------------------------------------------------------- 激活


class EvidenceActivationEventRepository:
    """激活/回滚原子仓储：验证事件并同步切换审核节点成对指针。"""

    def __init__(self, session) -> None:
        self.session = session

    @staticmethod
    def _decode(record: EvidenceActivationEventRecord) -> EvidenceActivationEvent:
        contract = decode_contract(
            EvidenceActivationEvent, record.payload_json, record.payload_sha256
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "EvidenceActivationEvent",
            record,
            payload,
            {
                "event_id": "event_id",
                "review_episode_id": "review_episode_id",
                "activation_seq": "activation_seq",
                "event_kind": "event_kind",
                "from_snapshot_id": "from_snapshot_id",
                "from_revision_id": "from_revision_id",
                "to_snapshot_id": "to_snapshot_id",
                "to_revision_id": "to_revision_id",
                "reason": "reason",
                "actor": "actor",
                "job_id": "job_id",
                "candidate_id": "candidate_id",
                "expected_revision": "expected_revision",
                "resulting_episode_revision": "resulting_episode_revision",
                "snapshot_status_transitioned": "snapshot_status_transitioned",
                "command_sha256": "command_sha256",
            },
        )
        return contract

    def _next_seq(self, review_episode_id: str) -> int:
        current = self.session.execute(
            select(func.max(EvidenceActivationEventRecord.activation_seq)).where(
                EvidenceActivationEventRecord.review_episode_id == review_episode_id
            )
        ).scalar_one()
        return (current or 0) + 1

    def append(self, event: EvidenceActivationEvent) -> EvidenceActivationEvent:
        """禁止孤立追加；事件与成对指针必须由 ``append_and_switch`` 原子写入。"""
        raise Slice44RepositoryError(
            "激活事件不能单独追加，必须通过原子激活/回滚入口同时切换当前版本"
        )

    def append_and_switch(
        self, event: EvidenceActivationEvent
    ) -> tuple[
        EvidenceActivationEvent,
        ReviewEpisode,
        EvidenceProcessingCandidate | None,
    ]:
        """原子追加事件、切换成对指针，并在启用时同步转换生产候选。"""
        with self.session.begin_nested():
            return self._append_and_switch_locked(event)

    def _append_and_switch_locked(
        self, event: EvidenceActivationEvent
    ) -> tuple[
        EvidenceActivationEvent,
        ReviewEpisode,
        EvidenceProcessingCandidate | None,
    ]:
        episode = EpisodeRepository(self.session).get(event.review_episode_id)
        current_pair = (
            episode.active_evidence_snapshot_id,
            episode.active_evidence_processing_revision_id,
        )
        if current_pair != (event.from_snapshot_id, event.from_revision_id):
            raise Slice44RepositoryError(
                "激活事件的来源版本对与审核节点当前活动版本不一致"
            )
        snapshot = self.session.get(EvidenceSnapshotV2Record, event.to_snapshot_id)
        if snapshot is None:
            raise InvalidReferenceError(
                f"激活事件 {event.event_id} 的目标快照 {event.to_snapshot_id} 不存在"
            )
        if snapshot.review_episode_id != event.review_episode_id:
            raise Slice44RepositoryError("激活事件、目标快照与审核节点不属于同一作用域")

        target_revision = self._validate_target_revision(event)
        if (
            target_revision.review_episode_id != event.review_episode_id
            or target_revision.evidence_snapshot_id != event.to_snapshot_id
        ):
            raise Slice44RepositoryError(
                "激活事件的目标完整处理版本与目标快照或审核节点不一致"
            )
        candidate = None
        if event.event_kind == ActivationEventKind.ACTIVATE:
            candidate = self._validate_ready_candidate(event, target_revision)
        else:
            historical = self.session.execute(
                select(EvidenceActivationEventRecord.event_id).where(
                    EvidenceActivationEventRecord.review_episode_id
                    == event.review_episode_id,
                    EvidenceActivationEventRecord.to_snapshot_id
                    == event.to_snapshot_id,
                    EvidenceActivationEventRecord.to_revision_id
                    == event.to_revision_id,
                )
            ).first()
            if historical is None:
                raise Slice44RepositoryError("回滚目标版本对没有历史激活记录")

        if EvidenceSnapshotRepository(self.session).current_status(
            event.to_snapshot_id
        ) != SnapshotStatus.ACTIVE:
            raise Slice44RepositoryError("激活事件写入时目标快照尚未完成首次启用")

        saved = self._append_validated(event)
        updated, _record = apply_revisioned_update(
            self.session,
            ReviewEpisodeRecord,
            ReviewEpisode,
            event.review_episode_id,
            event.expected_revision,
            changes={
                "active_evidence_snapshot_id": event.to_snapshot_id,
                "active_evidence_processing_revision_id": event.to_revision_id,
            },
            column_builder=_episode_columns,
            mutable_fields={
                "active_evidence_snapshot_id",
                "active_evidence_processing_revision_id",
            },
            entity_type="ReviewEpisode",
        )
        if candidate is not None:
            candidate_repo = EvidenceProcessingCandidateRepository(self.session)
            candidate_repo.append_event(
                EvidenceProcessingCandidateEvent(
                    candidate_id=candidate.candidate_id,
                    seq=len(candidate_repo.get_events(candidate.candidate_id)) + 1,
                    from_status=EvidenceProcessingCandidateStatus.READY,
                    to_status=EvidenceProcessingCandidateStatus.ACTIVE,
                    event_kind=ProcessingCandidateEventKind.ACTIVATE,
                    actor=event.actor,
                    reason=event.reason,
                    complete_revision_id=event.to_revision_id,
                    created_at=event.created_at,
                )
            )
            candidate = candidate_repo.get(candidate.candidate_id)
        return saved, cast(ReviewEpisode, updated), candidate

    def _validate_target_revision(
        self, event: EvidenceActivationEvent
    ) -> EvidenceProcessingRevisionRecord:
        target_revision = self.session.get(
            EvidenceProcessingRevisionRecord, event.to_revision_id
        )
        if target_revision is None:
            raise InvalidReferenceError(
                f"激活事件 {event.event_id} 的目标处理修订 {event.to_revision_id} 不存在"
            )
        if (
            target_revision.revision_kind != "complete"
            or not target_revision.is_activatable
            or target_revision.producer_candidate_id is None
            or target_revision.candidate_input_sha256 is None
            or target_revision.completion_manifest_sha256 is None
        ):
            raise InvalidReferenceError(
                f"激活事件 {event.event_id} 的目标处理修订 {event.to_revision_id} "
                "不是可激活的完整处理版本"
            )
        return target_revision

    def _validate_ready_candidate(
        self,
        event: EvidenceActivationEvent,
        target_revision: EvidenceProcessingRevisionRecord,
    ) -> EvidenceProcessingCandidate:
        if event.candidate_id is None:
            raise InvalidReferenceError("启用事件必须绑定生产候选")
        candidate = self.session.get(
            EvidenceProcessingCandidateRecord, event.candidate_id
        )
        if candidate is None:
            raise InvalidReferenceError("启用事件绑定的处理候选不存在")
        projected_candidate = EvidenceProcessingCandidateRepository(self.session).get(
            event.candidate_id
        )
        if (
            projected_candidate.status != EvidenceProcessingCandidateStatus.READY
            or projected_candidate.complete_revision_id != event.to_revision_id
            or projected_candidate.review_episode_id != event.review_episode_id
            or projected_candidate.evidence_snapshot_id != event.to_snapshot_id
            or projected_candidate.expected_revision != event.expected_revision
        ):
            raise InvalidReferenceError(
                "启用事件绑定的处理候选尚未就绪、预期修订已失效或作用域不一致"
            )
        if (
            target_revision.producer_candidate_id != event.candidate_id
            or target_revision.candidate_input_sha256
            != projected_candidate.candidate_input_sha256
        ):
            raise InvalidReferenceError("启用事件的目标完整修订不是绑定候选的输出")
        return projected_candidate

    def _append_validated(
        self, event: EvidenceActivationEvent
    ) -> EvidenceActivationEvent:
        if self.session.get(EvidenceActivationEventRecord, event.event_id) is not None:
            raise DuplicateRecordError(f"激活事件 {event.event_id} 已存在")
        same_command = self.session.execute(
            select(EvidenceActivationEventRecord.event_id).where(
                EvidenceActivationEventRecord.command_sha256 == event.command_sha256
            )
        ).first()
        if same_command is not None:
            raise DuplicateRecordError("相同激活/回滚命令已存在，拒绝重复追加")
        expected_seq = self._next_seq(event.review_episode_id)
        if event.activation_seq != expected_seq:
            raise ActivationSequenceError(
                f"审核节点 {event.review_episode_id} 的激活序号应为 {expected_seq}，"
                f"得到 {event.activation_seq}"
            )
        payload_json, payload_sha256 = encode_contract(event)
        self.session.add(
            EvidenceActivationEventRecord(
                event_id=event.event_id,
                review_episode_id=event.review_episode_id,
                activation_seq=event.activation_seq,
                event_kind=event.event_kind.value,
                from_snapshot_id=event.from_snapshot_id,
                from_revision_id=event.from_revision_id,
                to_snapshot_id=event.to_snapshot_id,
                to_revision_id=event.to_revision_id,
                reason=event.reason,
                actor=event.actor,
                job_id=event.job_id,
                candidate_id=event.candidate_id,
                expected_revision=event.expected_revision,
                resulting_episode_revision=event.resulting_episode_revision,
                snapshot_status_transitioned=event.snapshot_status_transitioned,
                command_sha256=event.command_sha256,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                created_at=to_utc_naive(event.created_at),
            )
        )
        _flush_guarded(self.session)
        return self.get(event.event_id)

    def get(self, event_id: str) -> EvidenceActivationEvent:
        record = _get_required(
            self.session, EvidenceActivationEventRecord, event_id, "EvidenceActivationEvent"
        )
        return self._decode(record)

    def list_by_episode(self, review_episode_id: str) -> list[EvidenceActivationEvent]:
        rows = self.session.execute(
            select(EvidenceActivationEventRecord)
            .where(
                EvidenceActivationEventRecord.review_episode_id == review_episode_id
            )
            .order_by(EvidenceActivationEventRecord.activation_seq)
        ).scalars().all()
        return [self._decode(row) for row in rows]


# --------------------------------------------------------------------------- 处理候选


class EvidenceProcessingCandidateRepository:
    """处理候选 + 追加事件状态机：事件投影当前状态，终态不可跳转。"""

    def __init__(self, session, artifact_store=None) -> None:
        self.session = session
        self.artifact_store = artifact_store

    @staticmethod
    def _decode_candidate(
        record: EvidenceProcessingCandidateRecord,
    ) -> EvidenceProcessingCandidate:
        contract = decode_contract(
            EvidenceProcessingCandidate,
            record.payload_json,
            record.payload_sha256,
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "EvidenceProcessingCandidate",
            record,
            payload,
            {
                "candidate_id": "candidate_id",
                "evidence_snapshot_id": "evidence_snapshot_id",
                "base_processing_revision_id": "base_processing_revision_id",
                "project_id": "project_id",
                "subject_id": "subject_id",
                "review_episode_id": "review_episode_id",
                "expected_revision": "expected_revision",
                "job_id": "job_id",
                "idempotency_key": "idempotency_key",
                "scanner_rule_version": "scanner_rule_version",
                "selected_locator_ids_json": "selected_locator_ids",
                "candidate_input_sha256": "candidate_input_sha256",
                "created_by": "created_by",
            },
        )
        return contract

    @staticmethod
    def _decode_event(record: EvidenceProcessingCandidateEventRecord) -> EvidenceProcessingCandidateEvent:
        contract = decode_contract(
            EvidenceProcessingCandidateEvent,
            record.payload_json,
            record.payload_sha256,
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "EvidenceProcessingCandidateEvent",
            record,
            payload,
            {
                "candidate_id": "candidate_id",
                "seq": "seq",
                "from_status": "from_status",
                "to_status": "to_status",
                "event_kind": "event_kind",
                "actor": "actor",
                "reason": "reason",
                "complete_revision_id": "complete_revision_id",
                "created_at": "created_at",
            },
        )
        return contract

    def _verify_status_projection(
        self, record: EvidenceProcessingCandidateRecord, contract: EvidenceProcessingCandidate
    ) -> EvidenceProcessingCandidate:
        """候选当前状态由追加事件投影；payload 内 status 是创建时状态（staged）。

        读取时把 payload 的 status 覆盖为最新事件目标，并校验规范化 status 列与
        最新事件一致（列存投影，payload 存创建状态，二者语义不同）。
        """
        rows = self.session.execute(
            select(EvidenceProcessingCandidateEventRecord)
            .where(
                EvidenceProcessingCandidateEventRecord.candidate_id == record.candidate_id
            )
            .order_by(EvidenceProcessingCandidateEventRecord.seq)
        ).scalars().all()
        projected = EvidenceProcessingCandidateStatus.STAGED
        complete_revision_id: str | None = None
        attempt_manifest = contract.attempt_manifest
        attempt_input_sha256 = contract.candidate_input_sha256
        for expected_seq, row in enumerate(rows, start=1):
            event = self._decode_event(row)
            if event.candidate_id != record.candidate_id or event.seq != expected_seq:
                raise PersistedContractInvalid(
                    f"候选 {record.candidate_id} 的事件归属或序号不连续"
                )
            if event.from_status != projected:
                raise PersistedContractInvalid(
                    f"候选 {record.candidate_id} 的事件状态链不连续"
                )
            projected = event.to_status
            if event.attempt_manifest is not None:
                attempt_manifest = event.attempt_manifest
                attempt_input_sha256 = event.attempt_input_sha256 or attempt_input_sha256
            if event.complete_revision_id is not None:
                if complete_revision_id not in (None, event.complete_revision_id):
                    raise PersistedContractInvalid(
                        f"候选 {record.candidate_id} 的事件绑定了不同完整处理修订"
                    )
                complete_revision_id = event.complete_revision_id
        if record.status != projected.value:
            raise PersistedContractInvalid(
                f"候选 {record.candidate_id} 状态列与最新事件目标不一致，拒绝还原合同"
            )
        if record.complete_revision_id != complete_revision_id:
            raise PersistedContractInvalid(
                f"候选 {record.candidate_id} 的完整处理修订投影与事件链不一致"
            )
        if projected in {
            EvidenceProcessingCandidateStatus.READY,
            EvidenceProcessingCandidateStatus.ACTIVE,
        } and complete_revision_id is None:
            raise PersistedContractInvalid(
                f"候选 {record.candidate_id} 已完成构建但未绑定完整处理修订"
            )
        return contract.model_copy(
            update={
                "status": projected,
                "complete_revision_id": complete_revision_id,
                "attempt_manifest": attempt_manifest,
                "candidate_input_sha256": attempt_input_sha256,
            }
        )

    def create(
        self,
        candidate: EvidenceProcessingCandidate,
        first_event: EvidenceProcessingCandidateEvent | None = None,
    ) -> EvidenceProcessingCandidate:
        existing = self.session.execute(
            select(EvidenceProcessingCandidateRecord).where(
                EvidenceProcessingCandidateRecord.idempotency_key
                == candidate.idempotency_key
            )
        ).scalars().first()
        if existing is not None:
            existing_contract = self._decode_candidate(existing)
            if existing_contract.candidate_input_sha256 != candidate.candidate_input_sha256:
                raise CandidateIdempotencyConflictError(
                    f"幂等键 {candidate.idempotency_key} 已被不同输入占用，拒绝复用"
                )
            return self.get(existing.candidate_id)
        if candidate.status != EvidenceProcessingCandidateStatus.STAGED:
            raise CandidateStateTransitionError("新建候选必须从 staged 开始")
        if first_event is not None:
            if first_event.candidate_id != candidate.candidate_id:
                raise CandidateStateTransitionError("首事件必须属于候选本身")
            if (
                first_event.seq != 1
                or first_event.from_status != EvidenceProcessingCandidateStatus.STAGED
            ):
                raise CandidateStateTransitionError("首事件必须是 staged 出发且序号为 1")
        self._check_candidate_references(candidate)
        # payload 内 status 是创建状态（staged）；当前状态由事件投影。
        payload_json, payload_sha256 = encode_contract(candidate)
        self.session.add(
            EvidenceProcessingCandidateRecord(
                candidate_id=candidate.candidate_id,
                evidence_snapshot_id=candidate.evidence_snapshot_id,
                base_processing_revision_id=candidate.base_processing_revision_id,
                project_id=candidate.project_id,
                subject_id=candidate.subject_id,
                review_episode_id=candidate.review_episode_id,
                expected_revision=candidate.expected_revision,
                job_id=candidate.job_id,
                idempotency_key=candidate.idempotency_key,
                candidate_input_sha256=candidate.candidate_input_sha256,
                scanner_rule_version=candidate.scanner_rule_version,
                selected_locator_ids_json=candidate.selected_locator_ids,
                complete_revision_id=None,
                status=candidate.status.value,
                created_by=candidate.created_by,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                created_at=to_utc_naive(candidate.created_at),
            )
        )
        _flush_guarded(self.session)
        if first_event is not None:
            self._write_event(first_event)
        return self.get(candidate.candidate_id)

    def _check_candidate_references(self, candidate: EvidenceProcessingCandidate) -> None:
        snapshot = self.session.get(EvidenceSnapshotV2Record, candidate.evidence_snapshot_id)
        if snapshot is None:
            raise InvalidReferenceError(
                f"候选 {candidate.candidate_id} 引用的快照不存在"
            )
        base = self.session.get(
            EvidenceProcessingRevisionRecord, candidate.base_processing_revision_id
        )
        if base is None:
            raise InvalidReferenceError(
                f"候选 {candidate.candidate_id} 引用的 base 处理修订不存在"
            )
        if base.review_episode_id != candidate.review_episode_id:
            raise InvalidReferenceError("候选的 base 修订与审核节点作用域不一致")
        if base.evidence_snapshot_id != candidate.evidence_snapshot_id:
            raise InvalidReferenceError("候选的 base 修订与目标快照不一致")
        if (
            snapshot.project_id,
            snapshot.subject_id,
            snapshot.review_episode_id,
        ) != (
            candidate.project_id,
            candidate.subject_id,
            candidate.review_episode_id,
        ):
            raise InvalidReferenceError("候选声明的项目、受试者或审核节点与目标快照不一致")
        if (base.project_id, base.subject_id) != (
            candidate.project_id,
            candidate.subject_id,
        ):
            raise InvalidReferenceError("候选声明的项目或受试者与 base 修订不一致")
        manifest = EvidenceProcessingRevisionRepository(self.session).get(
            candidate.base_processing_revision_id
        ).manifest
        selected_pages = {entry.page_artifact_id for entry in manifest}
        for locator_id in candidate.selected_locator_ids:
            locator = EvidenceLocatorRepository(
                self.session, self.artifact_store
            ).get(locator_id)
            if locator.page_artifact_id not in selected_pages:
                raise InvalidReferenceError("候选选中的定位不属于 base 修订页清单")

    def _write_event(self, event: EvidenceProcessingCandidateEvent) -> None:
        if self.session.get(
            EvidenceProcessingCandidateRecord, event.candidate_id
        ) is None:
            raise InvalidReferenceError(f"候选 {event.candidate_id} 不存在")
        latest = self.session.execute(
            select(EvidenceProcessingCandidateEventRecord)
            .where(EvidenceProcessingCandidateEventRecord.candidate_id == event.candidate_id)
            .order_by(EvidenceProcessingCandidateEventRecord.seq.desc())
            .limit(1)
        ).scalars().first()
        current_status = (
            EvidenceProcessingCandidateStatus(latest.to_status)
            if latest is not None
            else EvidenceProcessingCandidateStatus.STAGED
        )
        candidate_record = self.session.get(
            EvidenceProcessingCandidateRecord, event.candidate_id
        )
        current_candidate = self.get(event.candidate_id)
        carries_attempt = event.event_kind in {
            ProcessingCandidateEventKind.WORKER_START,
            ProcessingCandidateEventKind.RETRY,
            ProcessingCandidateEventKind.CORRECTION_OR_RESOLUTION,
        }
        if (
            candidate_record is not None
            and candidate_record.job_id is not None
            and carries_attempt
            and (
                event.attempt_manifest is None
                or event.attempt_input_sha256 is None
            )
        ):
            raise CandidateStateTransitionError(
                "持久任务候选开始、重试或核对后继续时必须冻结尝试清单"
            )
        if event.seq != (latest.seq + 1 if latest is not None else 1):
            raise CandidateStateTransitionError(
                f"候选 {event.candidate_id} 的事件序号应为 "
                f"{latest.seq + 1 if latest is not None else 1}，得到 {event.seq}"
            )
        if event.from_status != current_status:
            raise CandidateStateTransitionError(
                f"候选 {event.candidate_id} 当前状态为 {current_status.value}，"
                f"事件声称 {event.from_status.value}"
            )
        # 合同已校验转换表；此处再校验终态。
        if current_status in {
            EvidenceProcessingCandidateStatus.ACTIVE,
            EvidenceProcessingCandidateStatus.REVISION_CONFLICT,
            EvidenceProcessingCandidateStatus.CANCELLED,
            EvidenceProcessingCandidateStatus.TERMINAL_FAILURE,
        }:
            raise CandidateStateTransitionError(
                f"候选 {event.candidate_id} 已处于终态 {current_status.value}，不可再转换"
            )
        payload_json, payload_sha256 = encode_contract(event)
        self.session.add(
            EvidenceProcessingCandidateEventRecord(
                candidate_id=event.candidate_id,
                seq=event.seq,
                from_status=event.from_status.value,
                to_status=event.to_status.value,
                event_kind=event.event_kind.value,
                actor=event.actor,
                reason=event.reason,
                complete_revision_id=event.complete_revision_id,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                created_at=to_utc_naive(event.created_at),
            )
        )
        _flush_guarded(self.session)
        self.session.execute(
            select(EvidenceProcessingCandidateRecord)
            .where(EvidenceProcessingCandidateRecord.candidate_id == event.candidate_id)
        )
        record = self.session.get(EvidenceProcessingCandidateRecord, event.candidate_id)
        record.status = event.to_status.value
        if event.complete_revision_id is not None:
            complete = self.session.get(
                EvidenceProcessingRevisionRecord, event.complete_revision_id
            )
            if complete is None or complete.revision_kind != "complete":
                raise InvalidReferenceError("候选事件绑定的完整处理修订不存在或类型不正确")
            # 候选在“待核对 -> 重新排队”时会通过追加事件冻结新的尝试输入；
            # 完成绑定必须使用事件链投影后的输入，不能退回创建时 payload。
            candidate = current_candidate
            if (
                complete.evidence_snapshot_id != candidate.evidence_snapshot_id
                or complete.base_processing_revision_id
                != candidate.base_processing_revision_id
            ):
                raise InvalidReferenceError("候选事件绑定的完整处理修订与候选输入不一致")
            if (
                complete.producer_candidate_id != candidate.candidate_id
                or complete.candidate_input_sha256
                != candidate.candidate_input_sha256
            ):
                raise InvalidReferenceError("候选只能绑定由自身冻结输入生成的完整处理修订")
            if record.complete_revision_id not in (None, event.complete_revision_id):
                raise CandidateStateTransitionError("候选不能换绑另一份完整处理修订")
            record.complete_revision_id = event.complete_revision_id
        _flush_guarded(self.session)

    def append_event(self, event: EvidenceProcessingCandidateEvent) -> EvidenceProcessingCandidate:
        self._write_event(event)
        return self.get(event.candidate_id)

    def get(self, candidate_id: str) -> EvidenceProcessingCandidate:
        record = _get_required(
            self.session, EvidenceProcessingCandidateRecord, candidate_id, "EvidenceProcessingCandidate"
        )
        contract = self._decode_candidate(record)
        return self._verify_status_projection(record, contract)

    def latest_by_snapshot(
        self, evidence_snapshot_id: str
    ) -> EvidenceProcessingCandidate | None:
        """Return the latest persisted candidate for one immutable snapshot."""
        record = self.session.execute(
            select(EvidenceProcessingCandidateRecord)
            .where(
                EvidenceProcessingCandidateRecord.evidence_snapshot_id
                == evidence_snapshot_id
            )
            .order_by(
                EvidenceProcessingCandidateRecord.created_at.desc(),
                EvidenceProcessingCandidateRecord.candidate_id.desc(),
            )
            .limit(1)
        ).scalars().first()
        if record is None:
            return None
        return self.get(record.candidate_id)

    def get_events(self, candidate_id: str) -> list[EvidenceProcessingCandidateEvent]:
        rows = self.session.execute(
            select(EvidenceProcessingCandidateEventRecord)
            .where(EvidenceProcessingCandidateEventRecord.candidate_id == candidate_id)
            .order_by(EvidenceProcessingCandidateEventRecord.seq)
        ).scalars().all()
        return [self._decode_event(row) for row in rows]


# --------------------------------------------------------------------------- 完整处理修订


class CompleteEvidenceProcessingRevisionRepository:
    """完整处理修订 + 有序旁路关联闭包（追加写，闭包门禁在持久化边界执行）。

    冻结 §4.6 全部结构门禁后才写入：页清单与 base 逐项相等且覆盖每个快照成员
    资料版本的**实际页数**（对照 ``SourceDocumentVersionV2Record.page_count`` 与
    持久化 PageArtifact 行），无缺页/重复页/失败页/换页/非终态 OCR；project/
    subject/review episode/study-phase 作用域一致；逐资料恰好一条链头元数据修订；
    逐页恰好一个风险扫描；每选中的核对/校对必须绑定本完整修订的 base 修订且其
    OCR 页必须出现在该 base 页清单；blocking 风险必须被选中核对或覆盖校对解除；
    校对无重叠、关键变化已确认；被提及资料与满足修订必须各自恰为链头；闭包清单
    哈希必须由 base/页/全部子工件的 canonical payload hash 重算一致。

    ``completion_manifest_sha256`` 由本仓储从 DB 读取子记录 payload hash 计算并
    校验（合同只校验格式与唯一性，不访问 DB）。
    """

    def __init__(self, session, artifact_store=None) -> None:
        self.session = session
        self.artifact_store = artifact_store

    @staticmethod
    def _decode_record(
        record: EvidenceProcessingRevisionRecord,
    ) -> CompleteEvidenceProcessingRevision:
        if record.revision_kind != "complete":
            raise OcrRevisionKindError(
                f"证据处理修订 {record.evidence_processing_revision_id} 不是 complete 修订，"
                "请使用 EvidenceProcessingRevisionRepository"
            )
        contract = decode_contract(
            CompleteEvidenceProcessingRevision,
            record.payload_json,
            record.payload_sha256,
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "CompleteEvidenceProcessingRevision",
            record,
            payload,
            {
                "evidence_processing_revision_id": "evidence_processing_revision_id",
                "evidence_snapshot_id": "evidence_snapshot_id",
                "project_id": "project_id",
                "subject_id": "subject_id",
                "review_episode_id": "review_episode_id",
                "base_processing_revision_id": "base_processing_revision_id",
                "producer_candidate_id": "producer_candidate_id",
                "candidate_input_sha256": "candidate_input_sha256",
                "manifest_sha256": "manifest_sha256",
                "completion_manifest_sha256": "completion_manifest_sha256",
                "status": "status",
                "is_activatable": "is_activatable",
                "created_by": "created_by",
                "created_at": "created_at",
            },
        )
        return contract

    # ------------------------------------------------------------------ 工具

    def _base_revision(self, revision: CompleteEvidenceProcessingRevision) -> EvidenceProcessingRevisionRecord:
        record = self.session.get(
            EvidenceProcessingRevisionRecord, revision.base_processing_revision_id
        )
        if record is None:
            raise InvalidReferenceError(
                f"完整修订 {revision.evidence_processing_revision_id} 的 base 修订不存在"
            )
        if record.revision_kind != "base":
            raise RevisionClosureError("完整修订的 base 必须是 base 修订")
        if record.evidence_snapshot_id != revision.evidence_snapshot_id:
            raise RevisionClosureError("完整修订与 base 修订必须属于同一快照")
        if record.review_episode_id != revision.review_episode_id:
            raise RevisionClosureError("完整修订与 base 修订必须属于同一审核节点")
        return record

    def _snapshot_record(
        self, revision: CompleteEvidenceProcessingRevision
    ) -> EvidenceSnapshotV2Record:
        snapshot = self.session.get(
            EvidenceSnapshotV2Record, revision.evidence_snapshot_id
        )
        if snapshot is None:
            raise RevisionClosureError(
                f"完整修订 {revision.evidence_processing_revision_id} 引用的快照不存在"
            )
        return snapshot

    def _verify_scope(self, revision: CompleteEvidenceProcessingRevision) -> None:
        """project/subject/review episode/study-phase 必须一致（快照、base、完整修订）。"""
        snapshot = self._snapshot_record(revision)
        base = self.session.get(
            EvidenceProcessingRevisionRecord, revision.base_processing_revision_id
        )
        if (
            snapshot.project_id,
            snapshot.subject_id,
            snapshot.review_episode_id,
        ) != (
            revision.project_id,
            revision.subject_id,
            revision.review_episode_id,
        ):
            raise RevisionClosureError(
                f"完整修订 {revision.evidence_processing_revision_id} 的作用域与快照不一致"
            )
        if (
            base.project_id,
            base.subject_id,
            base.review_episode_id,
        ) != (
            revision.project_id,
            revision.subject_id,
            revision.review_episode_id,
        ):
            raise RevisionClosureError(
                f"完整修订 {revision.evidence_processing_revision_id} 的作用域与 base 修订不一致"
            )
        episode = self.session.get(ReviewEpisodeRecord, revision.review_episode_id)
        if episode is None:
            raise RevisionClosureError("完整修订引用的审核节点不存在")
        # 快照/资料版本作用域由 0008 仓储创建时保证与 episode 一致；此处校验
        # study-phase 与 episode 一致（ReviewEpisodeRecord 有 study_phase 列）。
        if episode.study_phase is None:
            raise RevisionClosureError("审核节点缺少 study_phase，无法证明作用域")
        for doc_id in {e.source_document_version_id for e in revision.manifest}:
            document = self.session.get(SourceDocumentVersionV2Record, doc_id)
            if document is None:
                raise RevisionClosureError(f"页清单引用的资料版本 {doc_id} 不存在")
            if (
                document.project_id,
                document.subject_id,
                document.review_episode_id,
            ) != (
                revision.project_id,
                revision.subject_id,
                revision.review_episode_id,
            ):
                raise RevisionClosureError(
                    f"页清单资料 {doc_id} 与完整修订作用域不一致"
                )

    def _base_manifest(self, revision: CompleteEvidenceProcessingRevision) -> list[EvidenceProcessingRevisionPage]:
        base_repo = EvidenceProcessingRevisionRepository(self.session)
        rows = base_repo._manifest_rows(revision.base_processing_revision_id)
        return [
            base_repo._decode_page_entry(
                row, expected_revision_id=revision.base_processing_revision_id
            )
            for row in rows
        ]

    def _expected_pages_for_document(self, doc_id: str) -> set[int]:
        """资料版本的期望页集合：以持久化 PageArtifact 行为准，并与 page_count 交叉核对。

        若 ``page_count`` 已知，期望页必须为 ``1..page_count`` 且与持久化
        PageArtifact 页集合完全一致；若 page_count 未知，以持久化 PageArtifact 页
        集合为准。任一失败页/降级页都不算完整页。
        """
        document = self.session.get(SourceDocumentVersionV2Record, doc_id)
        if document is None:
            raise RevisionClosureError(f"资料版本 {doc_id} 不存在，无法核对页数")
        artifact_rows = self.session.execute(
            select(PageArtifactRecord).where(
                PageArtifactRecord.source_document_version_id == doc_id
            )
        ).scalars().all()
        if not artifact_rows:
            raise RevisionClosureError(f"资料版本 {doc_id} 没有任何页产物，无法证明完整页")
        artifact_pages = {row.page_number for row in artifact_rows}
        if document.page_count is not None:
            expected = set(range(1, document.page_count + 1))
            if artifact_pages != expected:
                raise RevisionClosureError(
                    f"资料版本 {doc_id} 的持久化页产物集合 {sorted(artifact_pages)} "
                    f"与 page_count={document.page_count} 的期望 {sorted(expected)} 不一致"
                )
        else:
            expected = artifact_pages
        return expected

    def _verify_page_closure(self, revision: CompleteEvidenceProcessingRevision) -> None:
        """页清单必须精确等于每个快照成员的期望页集合（数量与页号）。"""
        members = self.session.execute(
            select(EvidenceSnapshotMemberRecord).where(
                EvidenceSnapshotMemberRecord.snapshot_id == revision.evidence_snapshot_id
            )
        ).scalars().all()
        if not members:
            raise RevisionClosureError("快照没有活动成员，无法构建完整修订")
        member_docs = {m.source_document_version_id for m in members}

        manifest_by_doc: dict[str, set[int]] = {}
        seen_pages: set[tuple[str, int]] = set()
        for entry in revision.manifest:
            if entry.source_document_version_id not in member_docs:
                raise RevisionClosureError(
                    f"页清单包含非快照成员资料 {entry.source_document_version_id}"
                )
            page = (entry.source_document_version_id, entry.page_number)
            if page in seen_pages:
                raise RevisionClosureError(f"页清单重复页 {page}")
            seen_pages.add(page)
            manifest_by_doc.setdefault(entry.source_document_version_id, set()).add(
                entry.page_number
            )
        if set(manifest_by_doc) != member_docs:
            raise RevisionClosureError(
                f"页清单资料集合 {sorted(manifest_by_doc)} 必须精确等于快照成员资料"
                f"集合 {sorted(member_docs)}"
            )
        for doc_id in member_docs:
            expected = self._expected_pages_for_document(doc_id)
            actual = manifest_by_doc[doc_id]
            if actual != expected:
                raise RevisionClosureError(
                    f"完整修订 {revision.evidence_processing_revision_id} 的资料 "
                    f"{doc_id} 页清单 {sorted(actual)} 必须精确等于期望页集合 "
                    f"{sorted(expected)}（缺页/多页/换页均拒绝）"
                )

    def _verify_terminal_successful_pages(
        self, revision: CompleteEvidenceProcessingRevision
    ) -> None:
        """每页必须是终态成功页产物 + 终态成功 OCR 页（无失败/降级/非终态）。"""
        for entry in revision.manifest:
            artifact = self.session.get(PageArtifactRecord, entry.page_artifact_id)
            if artifact is None:
                raise RevisionClosureError(
                    f"页清单条目 {entry.entry_id} 引用的 PageArtifact 不存在"
                )
            if artifact.status != PageArtifactStatus.SUCCEEDED.value:
                raise RevisionClosureError(
                    f"页清单条目 {entry.entry_id} 的页产物不是终态成功页"
                    f"（{artifact.status}），不可激活"
                )
            if (
                artifact.source_document_version_id != entry.source_document_version_id
                or artifact.page_number != entry.page_number
            ):
                raise RevisionClosureError(
                    f"页清单条目 {entry.entry_id} 与页产物归属/页码不一致"
                )
            if entry.ocr_page_id is None:
                raise RevisionClosureError(
                    f"页清单条目 {entry.entry_id} 缺少 OCR 页引用"
                )
            ocr = self.session.get(OCRPageRecord, entry.ocr_page_id)
            if ocr is None:
                raise RevisionClosureError(
                    f"页清单条目 {entry.entry_id} 引用的 OCRPage 不存在"
                )
            if ocr.status != OCRPageStatus.SUCCEEDED.value:
                raise RevisionClosureError(
                    f"页清单条目 {entry.entry_id} 引用的 OCRPage 不是终态成功页"
                    f"（{ocr.status}）"
                )
            if (
                ocr.page_artifact_id != entry.page_artifact_id
                or ocr.page_number != entry.page_number
            ):
                raise RevisionClosureError("页清单条目与 OCRPage 归属不一致")

    # ------------------------------------------------------------------ 闭包

    def _child_payload_hash(self, record_cls, ref_id: str) -> str:
        """读取子记录 canonical payload hash（DB-bound，不信任镜像列）。"""
        record = self.session.get(record_cls, ref_id)
        if record is None:
            raise RevisionClosureError(f"子引用 {ref_id} 不存在")
        return record.payload_sha256

    def manifest_sha256_for(
        self,
        revision: CompleteEvidenceProcessingRevision,
        *,
        persisted_page_rows: list[EvidenceProcessingRevisionPageRecord] | None = None,
    ) -> str:
        """按 DB 子记录 payload hash 计算闭包清单哈希（合同只校验格式）。"""
        base = self._base_revision(revision)
        if persisted_page_rows is None:
            page_entries = [
                (entry.entry_id, encode_contract(entry)[1])
                for entry in revision.manifest
            ]
        else:
            page_entries = [
                (row.entry_id, row.payload_sha256) for row in persisted_page_rows
            ]
        return completion_manifest_hash(
            base_processing_revision_id=base.evidence_processing_revision_id,
            base_processing_revision_sha256=base.payload_sha256,
            page_entries=page_entries,
            locators=[
                (rid, self._child_payload_hash(EvidenceLocatorArtifactRecord, rid))
                for rid in revision.locator_ids
            ],
            risk_scans=[
                (rid, self._child_payload_hash(OCRRiskScanRecord, rid))
                for rid in revision.risk_scan_ids
            ],
            risk_reviews=[
                (rid, self._child_payload_hash(OCRRiskReviewRecord, rid))
                for rid in revision.risk_review_ids
            ],
            corrections=[
                (rid, self._child_payload_hash(CorrectionRecordRecord, rid))
                for rid in revision.correction_ids
            ],
            metadata_revisions=[
                (rid, self._child_payload_hash(SourceDocumentMetadataRevisionRecord, rid))
                for rid in revision.metadata_revision_ids
            ],
            referenced_documents=[
                (rid, self._child_payload_hash(ReferencedDocumentRevisionRecord, rid))
                for rid in revision.referenced_document_revision_ids
            ],
            resolutions=[
                (
                    rid,
                    self._child_payload_hash(
                        ReferencedDocumentResolutionRevisionRecord, rid
                    ),
                )
                for rid in revision.resolution_revision_ids
            ],
        )

    def _verify_manifest_hash(
        self,
        revision: CompleteEvidenceProcessingRevision,
        *,
        persisted_page_rows: list[EvidenceProcessingRevisionPageRecord] | None = None,
    ) -> None:
        expected = self.manifest_sha256_for(
            revision, persisted_page_rows=persisted_page_rows
        )
        if revision.completion_manifest_sha256 != expected:
            raise RevisionClosureError(
                f"完整修订 {revision.evidence_processing_revision_id} 的闭包清单哈希"
                "与 base/页/子工件 canonical payload hash 重算结果不一致"
            )

    def _verify_metadata_closure(
        self, revision: CompleteEvidenceProcessingRevision, *, require_current_heads: bool
    ) -> None:
        """逐资料恰好一条元数据修订；新建时额外要求为当前链头。"""
        manifest_docs = {entry.source_document_version_id for entry in revision.manifest}
        selected = []
        for mid in revision.metadata_revision_ids:
            record = self.session.get(SourceDocumentMetadataRevisionRecord, mid)
            if record is None:
                raise RevisionClosureError(f"选中的元数据修订 {mid} 不存在")
            contract = SourceDocumentMetadataRevisionRepository(self.session).get(mid)
            if contract.source_document_version_id not in manifest_docs:
                raise RevisionClosureError(
                    f"元数据修订 {mid} 属于非页清单资料"
                    f" {contract.source_document_version_id}"
                )
            # 必须是链头：没有任何后继修订替代它。
            has_successor = self.session.execute(
                select(func.count())
                .select_from(SourceDocumentMetadataRevisionRecord)
                .where(
                    SourceDocumentMetadataRevisionRecord.supersedes_metadata_revision_id
                    == mid
                )
            ).scalar_one()
            if require_current_heads and has_successor:
                raise RevisionClosureError(
                    f"元数据修订 {mid} 不是链头（存在后继替代），拒绝陈旧选择"
                )
            selected.append((contract.source_document_version_id, mid))
        by_doc: dict[str, list[str]] = {}
        for doc_id, mid in selected:
            by_doc.setdefault(doc_id, []).append(mid)
        for doc_id in manifest_docs:
            if len(by_doc.get(doc_id, [])) != 1:
                raise RevisionClosureError(
                    f"资料 {doc_id} 必须恰好绑定一条链头元数据修订，"
                    f"得到 {len(by_doc.get(doc_id, []))} 条"
                )
            if require_current_heads:
                rows = self.session.execute(
                    select(SourceDocumentMetadataRevisionRecord).where(
                        SourceDocumentMetadataRevisionRecord.source_document_version_id
                        == doc_id
                    )
                ).scalars().all()
                superseded_ids = {
                    row.supersedes_metadata_revision_id
                    for row in rows
                    if row.supersedes_metadata_revision_id is not None
                }
                current_ids = {
                    row.metadata_revision_id
                    for row in rows
                    if row.metadata_revision_id not in superseded_ids
                }
                selected_ids = set(by_doc[doc_id])
                if len(current_ids) != 1 or selected_ids != current_ids:
                    raise RevisionClosureError(
                        f"资料 {doc_id} 的当前元数据链必须唯一且完整入选；"
                        f"当前 {sorted(current_ids)}，选中 {sorted(selected_ids)}"
                    )

    def _verify_risk_closure(
        self, revision: CompleteEvidenceProcessingRevision, *, require_current_heads: bool
    ) -> None:
        """逐页恰好一个扫描；每个 blocking flag 由选中的有效核对或覆盖校对解除。

        扫描/flag/核对/校对全部通过各自仓储解码（payload hash + 镜像 + raw OCR 锚定）。
        """
        pages_by_ocr = {entry.ocr_page_id for entry in revision.manifest if entry.ocr_page_id}
        base_repo = EvidenceProcessingRevisionRepository(self.session)
        base_rows = base_repo._manifest_rows(revision.base_processing_revision_id)
        base_ocr_pages = {row.ocr_page_id for row in base_rows if row.ocr_page_id}

        scan_repo = OCRRiskScanRepository(self.session)
        scan_by_page: dict[str, int] = {}
        selected_flag_ids: set[str] = set()
        for scan_id in revision.risk_scan_ids:
            scan = scan_repo.get(scan_id)  # 解码 + flag 子表 + raw OCR 锚定
            ocr_page_id = scan.ocr_page_id
            if ocr_page_id is None:
                raise RevisionClosureError("风险扫描缺少 OCR 页引用")
            if ocr_page_id not in pages_by_ocr:
                raise RevisionClosureError("完整修订的风险扫描页不在页清单中")
            if ocr_page_id not in base_ocr_pages:
                raise RevisionClosureError("完整修订的风险扫描页不在 base 页清单中")
            scan_by_page[ocr_page_id] = scan_by_page.get(ocr_page_id, 0) + 1
            for flag in scan.flags:
                selected_flag_ids.add(f"{scan_id}:{flag.risk_id}")
        for ocr_page_id in pages_by_ocr:
            if scan_by_page.get(ocr_page_id, 0) != 1:
                raise RevisionClosureError(
                    f"OCR 页 {ocr_page_id} 必须恰好绑定一个选中的风险扫描，"
                    f"得到 {scan_by_page.get(ocr_page_id, 0)} 个"
                )

        review_repo = OCRRiskReviewRepository(self.session)
        selected_reviews: dict[str, OCRRiskReview] = {}
        for review_id in revision.risk_review_ids:
            review = review_repo.get(review_id)  # 解码 + 镜像
            if review.base_processing_revision_id != revision.base_processing_revision_id:
                raise RevisionClosureError(
                    f"风险核对 {review_id} 的 base 修订必须等于本完整修订的 base"
                )
            if review.risk_flag_id not in selected_flag_ids:
                raise RevisionClosureError(
                    "完整修订选中的风险核对必须对应其选中的风险扫描条目"
                )
            if review.risk_flag_id in selected_reviews:
                raise RevisionClosureError(
                    f"同一风险 flag {review.risk_flag_id} 只能选中一个有效核对"
                )
            selected_reviews[review.risk_flag_id] = review
            self._verify_flag_ocr_page_in_base_manifest(
                review.risk_flag_id, base_ocr_pages
            )

        correction_repo = CorrectionRepository(self.session)
        selected_corrections: list[CorrectionRecord] = []
        for correction_id in revision.correction_ids:
            correction = correction_repo.get(correction_id)  # 解码 + raw OCR 范围回验
            if correction.base_processing_revision_id != revision.base_processing_revision_id:
                raise RevisionClosureError(
                    f"校对 {correction_id} 的 base 修订必须等于本完整修订的 base"
                )
            has_successor = self.session.execute(
                select(func.count())
                .select_from(CorrectionRecordRecord)
                .where(CorrectionRecordRecord.supersedes_correction_id == correction_id)
            ).scalar_one()
            if require_current_heads and has_successor:
                raise RevisionClosureError(
                    f"校对 {correction_id} 不是当前链头，完整修订不得选择已被替代校对"
                )
            if correction.ocr_page_id not in pages_by_ocr:
                raise RevisionClosureError("完整修订的校对页不在页清单中")
            if correction.ocr_page_id not in base_ocr_pages:
                raise RevisionClosureError("完整修订的校对页不在 base 页清单中")
            if (
                correction.change_kind in BLOCKING_CORRECTION_KINDS
                and correction.confirmation_actor is None
            ):
                raise RevisionClosureError(
                    f"选中的关键校对 {correction_id} 未完成二次确认"
                )
            selected_corrections.append(correction)

        if require_current_heads:
            correction_rows = self.session.execute(
                select(CorrectionRecordRecord).where(
                    CorrectionRecordRecord.base_processing_revision_id
                    == revision.base_processing_revision_id,
                    CorrectionRecordRecord.ocr_page_id.in_(pages_by_ocr),
                )
            ).scalars().all()
            superseded_ids = {
                row.supersedes_correction_id
                for row in correction_rows
                if row.supersedes_correction_id is not None
            }
            current_ids = {
                row.correction_id
                for row in correction_rows
                if row.correction_id not in superseded_ids
            }
            selected_ids = {item.correction_id for item in selected_corrections}
            if selected_ids != current_ids:
                raise RevisionClosureError(
                    "完整修订必须纳入本基础修订全部当前有效校对；"
                    f"当前 {sorted(current_ids)}，选中 {sorted(selected_ids)}"
                )

        # 校对在选中集合内必须两两不重叠（只选有效项）。
        for i in range(len(selected_corrections)):
            for j in range(i + 1, len(selected_corrections)):
                a, b = selected_corrections[i], selected_corrections[j]
                if correction_anchors_conflict(a, b):
                    raise CorrectionOverlapError(
                        f"完整修订 {revision.evidence_processing_revision_id} 的校对 "
                        f"{a.correction_id} 与 {b.correction_id} 范围重叠；只选有效校对"
                    )

        # 每个 blocking flag 必须被选中核对或覆盖校对解除。
        for scan_id in revision.risk_scan_ids:
            scan = scan_repo.get(scan_id)
            for flag in scan.flags:
                flag_id = f"{scan_id}:{flag.risk_id}"
                if flag.level != OcrRiskLevel.BLOCKING:
                    continue
                if flag_id in selected_reviews:
                    continue
                covered = any(
                    c.ocr_page_id == scan.ocr_page_id
                    and c.text_start <= flag.text_start
                    and c.text_end >= flag.text_end
                    for c in selected_corrections
                )
                if not covered:
                    raise RevisionClosureError(
                        f"blocking 风险 {flag_id} 未由选中的有效核对或覆盖校对解除"
                    )

    def _verify_flag_ocr_page_in_base_manifest(
        self, flag_id: str, base_ocr_pages: set[str]
    ) -> None:
        """被选中核对引用的 flag 的 OCR 页必须出现在 base 页清单（不仅是 episode 相同）。"""
        flag = self.session.get(OCRRiskFlagRecord, flag_id)
        if flag is None:
            raise RevisionClosureError(f"风险 flag {flag_id} 不存在")
        ocr_page_id = flag.ocr_page_id
        if ocr_page_id is None:
            raise RevisionClosureError(f"风险 flag {flag_id} 缺少 OCR 页引用")
        if ocr_page_id not in base_ocr_pages:
            raise RevisionClosureError(
                f"风险 flag {flag_id} 的 OCR 页不在 base 页清单中，无法证明同闭包"
            )

    def _verify_referenced_docs(
        self,
        revision: CompleteEvidenceProcessingRevision,
        *,
        require_current_heads: bool,
    ) -> None:
        """被提及资料：每逻辑资料恰一条链头登记修订 + 恰一条链头满足修订。

        confirmed 必须携带属于本闭包的触发定位；provided 必须引用快照成员资料。
        """
        manifest_docs = {entry.source_document_version_id for entry in revision.manifest}
        ref_repo = ReferencedDocumentRepository(self.session)
        selected_reg: dict[str, ReferencedDocumentRevision] = {}
        for rid in revision.referenced_document_revision_ids:
            revision_contract = ref_repo.get_revision(rid)  # 解码 + 镜像
            if revision_contract.review_episode_id != revision.review_episode_id:
                raise RevisionClosureError(
                    "被提及资料修订必须与被完整修订同审核节点作用域"
                )
            if selected_reg.get(revision_contract.referenced_document_id) is not None:
                raise RevisionClosureError(
                    "同一逻辑被提及资料只能选中一条登记修订（重复逻辑修订拒绝）"
                )
            selected_reg[revision_contract.referenced_document_id] = revision_contract
            # 必须是链头。
            has_successor = self.session.execute(
                select(func.count())
                .select_from(ReferencedDocumentRevisionRecord)
                .where(ReferencedDocumentRevisionRecord.supersedes_revision_id == rid)
            ).scalar_one()
            if require_current_heads and has_successor:
                raise RevisionClosureError(
                    f"被提及资料修订 {rid} 不是链头（陈旧/分支选择拒绝）"
                )
            trigger_id = revision_contract.trigger_locator_id
            if revision_contract.status == ReferencedDocumentStatus.CONFIRMED and (
                trigger_id is None or trigger_id not in revision.locator_ids
            ):
                raise RevisionClosureError(
                    "被确认的被提及资料必须携带属于本完整修订闭包的触发定位"
                )

        selected_res: dict[str, ReferencedDocumentResolutionRevision] = {}
        for rid in revision.resolution_revision_ids:
            resolution = ref_repo.get_resolution(rid)  # 解码 + 镜像
            if resolution.referenced_document_id not in selected_reg:
                raise RevisionClosureError(
                    "满足修订必须对应本完整修订选中的被提及资料（多余满足链拒绝）"
                )
            if selected_res.get(resolution.referenced_document_id) is not None:
                raise RevisionClosureError(
                    "同一逻辑被提及资料只能选中一条满足修订（重复满足修订拒绝）"
                )
            selected_res[resolution.referenced_document_id] = resolution
            has_successor = self.session.execute(
                select(func.count())
                .select_from(ReferencedDocumentResolutionRevisionRecord)
                .where(
                    ReferencedDocumentResolutionRevisionRecord.supersedes_resolution_revision_id
                    == rid
                )
            ).scalar_one()
            if require_current_heads and has_successor:
                raise RevisionClosureError(
                    f"满足修订 {rid} 不是链头（陈旧/分支选择拒绝）"
                )
            if resolution.status == ReferencedDocumentResolutionStatus.PROVIDED:
                if resolution.source_document_version_id not in manifest_docs:
                    raise RevisionClosureError(
                        "provided 满足关系的资料必须属于该完整修订快照/页清单成员"
                    )
            else:
                if resolution.source_document_version_id is not None:
                    raise RevisionClosureError("unresolved 满足关系不能携带资料版本")

        # 每个被确认/被选登记资料必须有满足修订（缺满足修订 = 闭包不完整）。
        for logical_id in selected_reg:
            if logical_id not in selected_res:
                raise RevisionClosureError(
                    f"被提及资料 {logical_id} 缺少选中的满足修订，闭包不完整"
                )

        if require_current_heads:
            registration_rows = self.session.execute(
                select(ReferencedDocumentRevisionRecord).where(
                    ReferencedDocumentRevisionRecord.review_episode_id
                    == revision.review_episode_id
                )
            ).scalars().all()
            superseded_registration_ids = {
                row.supersedes_revision_id
                for row in registration_rows
                if row.supersedes_revision_id is not None
            }
            current_registration_ids = {
                row.revision_id
                for row in registration_rows
                if row.revision_id not in superseded_registration_ids
            }
            selected_registration_ids = set(
                revision.referenced_document_revision_ids
            )
            if selected_registration_ids != current_registration_ids:
                raise RevisionClosureError(
                    "完整修订必须纳入本审核节点全部当前被提及资料；"
                    f"当前 {sorted(current_registration_ids)}，"
                    f"选中 {sorted(selected_registration_ids)}"
                )

            logical_ids = set(selected_reg)
            resolution_rows = self.session.execute(
                select(ReferencedDocumentResolutionRevisionRecord).where(
                    ReferencedDocumentResolutionRevisionRecord.referenced_document_id.in_(
                        logical_ids
                    )
                )
            ).scalars().all() if logical_ids else []
            superseded_resolution_ids = {
                row.supersedes_resolution_revision_id
                for row in resolution_rows
                if row.supersedes_resolution_revision_id is not None
            }
            current_resolution_ids = {
                row.resolution_revision_id
                for row in resolution_rows
                if row.resolution_revision_id not in superseded_resolution_ids
            }
            selected_resolution_ids = set(revision.resolution_revision_ids)
            if selected_resolution_ids != current_resolution_ids:
                raise RevisionClosureError(
                    "完整修订必须纳入所选被提及资料全部当前满足状态；"
                    f"当前 {sorted(current_resolution_ids)}，"
                    f"选中 {sorted(selected_resolution_ids)}"
                )

    def _verify_locator_closure(self, revision: CompleteEvidenceProcessingRevision) -> None:
        """定位必须通过证明路径并精确绑定完整修订所选页产物/OCR 页。"""
        manifest_pages = {
            entry.page_artifact_id: entry.ocr_page_id for entry in revision.manifest
        }
        locator_repo = EvidenceLocatorRepository(self.session, self.artifact_store)
        correction_repo = CorrectionRepository(self.session)
        for locator_id in revision.locator_ids:
            locator = locator_repo.get(locator_id)  # 重跑真实性证明（不信任镜像列）
            if locator.page_artifact_id not in manifest_pages:
                raise RevisionClosureError("完整修订的定位页产物不在页清单中")
            selected_ocr_page_id = manifest_pages[locator.page_artifact_id]
            if (
                locator.source_layer == LocatorSourceLayer.RAW_OCR
                and locator.ocr_page_id != selected_ocr_page_id
            ):
                raise RevisionClosureError("原始识别定位未绑定页清单所选 OCR 页")
            if locator.ocr_page_id is not None and locator.ocr_page_id != selected_ocr_page_id:
                raise RevisionClosureError("定位引用的 OCR 页与页清单所选 OCR 页不一致")
            if locator.source_layer == LocatorSourceLayer.EFFECTIVE_TEXT:
                if locator.processing_revision_id is None or locator.ocr_page_id is None:
                    raise RevisionClosureError("有效文本定位缺少来源完整修订或 OCR 页")
                source_revision = self.get(locator.processing_revision_id)
                if (
                    source_revision.evidence_snapshot_id != revision.evidence_snapshot_id
                    or source_revision.base_processing_revision_id
                    != revision.base_processing_revision_id
                ):
                    raise RevisionClosureError(
                        "有效文本定位的来源完整修订与当前完整修订快照/base 不一致"
                    )
                ocr = OcrPageRepository(self.session).get(locator.ocr_page_id)
                selected_corrections = []
                for correction_id in revision.correction_ids:
                    correction = correction_repo.get(correction_id)
                    if correction.ocr_page_id == locator.ocr_page_id:
                        selected_corrections.append(correction)
                projection = project_effective_text(ocr.raw_text, selected_corrections)
                if (
                    locator.source_text_sha256 != projection.effective_text_sha256
                    or locator.effective_text_sha256 != projection.effective_text_sha256
                ):
                    raise RevisionClosureError(
                        "有效文本定位与当前完整修订选中校对的投影不一致"
                    )
                if locator.precision == LocatorPrecision.TEXT_RANGE:
                    locator_repo._verify_range_on_text(
                        locator, projection.effective_text, "当前完整修订有效文本"
                    )
                elif locator.precision == LocatorPrecision.PAGE_EXCERPT:
                    locator_repo._verify_excerpt_on_text(
                        locator, projection.effective_text, "当前完整修订有效文本"
                    )
            self._verify_document_episode(
                locator.source_document_version_id,
                revision.review_episode_id,
                f"定位 {locator_id}",
            )

    def _verify_referenced(
        self,
        revision: CompleteEvidenceProcessingRevision,
        *,
        require_current_heads: bool,
        require_producer_processing: bool = False,
        persisted_page_rows: list[EvidenceProcessingRevisionPageRecord] | None = None,
    ) -> None:
        """冻结合同 §4.6 全部结构门禁。"""
        self._verify_scope(revision)
        self._verify_page_closure(revision)
        self._verify_terminal_successful_pages(revision)
        self._verify_metadata_closure(
            revision, require_current_heads=require_current_heads
        )
        self._verify_risk_closure(
            revision, require_current_heads=require_current_heads
        )
        self._verify_locator_closure(revision)
        self._verify_referenced_docs(
            revision, require_current_heads=require_current_heads
        )
        self._verify_manifest_hash(
            revision, persisted_page_rows=persisted_page_rows
        )
        self._verify_candidate_binding(
            revision,
            require_processing=require_producer_processing,
        )

    def _verify_candidate_binding(
        self,
        revision: CompleteEvidenceProcessingRevision,
        *,
        require_processing: bool,
    ) -> None:
        candidate = EvidenceProcessingCandidateRepository(self.session).get(
            revision.producer_candidate_id
        )
        if (
            require_processing
            and candidate.status != EvidenceProcessingCandidateStatus.PROCESSING
        ):
            raise RevisionClosureError("完整修订只能由正在构建的处理候选生成")
        if (
            candidate.candidate_input_sha256 != revision.candidate_input_sha256
            or candidate.evidence_snapshot_id != revision.evidence_snapshot_id
            or candidate.base_processing_revision_id
            != revision.base_processing_revision_id
            or candidate.project_id != revision.project_id
            or candidate.subject_id != revision.subject_id
            or candidate.review_episode_id != revision.review_episode_id
        ):
            raise RevisionClosureError("完整修订与生产候选冻结的输入或作用域不一致")
        for scan_id in revision.risk_scan_ids:
            scan = OCRRiskScanRepository(self.session).get(scan_id)
            if scan.scanner_rule_version != candidate.scanner_rule_version:
                raise RevisionClosureError("完整修订的风险扫描版本与生产候选不一致")
        expected_locator_ids = set(candidate.selected_locator_ids)
        # 风险扫描的自动定位由基础页准备阶段确定性生成，不是用户
        # 手选输入。生产候选门禁必须与构建器使用同一闭包定义，否则真实
        # 红框会被误判为“未选定定位”。
        base_page_artifact_ids = {
            entry.page_artifact_id for entry in revision.manifest
        }
        risk_flag_ids = {
            f"{scan_id}:{flag.risk_id}"
            for scan_id in revision.risk_scan_ids
            for flag in OCRRiskScanRepository(self.session).get(scan_id).flags
        }
        if base_page_artifact_ids:
            automatic_locator_ids = self.session.execute(
                select(EvidenceLocatorArtifactRecord.locator_id).where(
                    EvidenceLocatorArtifactRecord.page_artifact_id.in_(
                        base_page_artifact_ids
                    ),
                    or_(
                        EvidenceLocatorArtifactRecord.target_id.in_(risk_flag_ids),
                        EvidenceLocatorArtifactRecord.target_id.startswith(
                            SOURCE_LINE_TARGET_PREFIX
                        ),
                    ),
                )
            ).scalars().all()
            expected_locator_ids.update(automatic_locator_ids)
        referenced_repo = ReferencedDocumentRepository(self.session)
        for revision_id in revision.referenced_document_revision_ids:
            referenced = referenced_repo.get_revision(revision_id)
            if (
                referenced.status == ReferencedDocumentStatus.CONFIRMED
                and referenced.trigger_locator_id is not None
            ):
                expected_locator_ids.add(referenced.trigger_locator_id)
        if sorted(expected_locator_ids) != revision.locator_ids:
            raise RevisionClosureError("完整修订的定位集合与生产候选及被提及资料闭包不一致")

    def _verify_document_episode(
        self, source_document_version_id: str, review_episode_id: str, label: str
    ) -> None:
        document = self.session.get(
            SourceDocumentVersionV2Record, source_document_version_id
        )
        if document is None:
            raise RevisionClosureError(f"{label} 引用的资料版本不存在")
        if document.review_episode_id != review_episode_id:
            raise RevisionClosureError(
                f"{label} 的资料版本属于审核节点 {document.review_episode_id}，"
                f"与完整修订 {review_episode_id} 作用域不一致"
            )

    def _manifest_rows(self, revision_id: str) -> list[EvidenceProcessingRevisionPageRecord]:
        return self.session.execute(
            select(EvidenceProcessingRevisionPageRecord)
            .where(EvidenceProcessingRevisionPageRecord.revision_id == revision_id)
            .order_by(EvidenceProcessingRevisionPageRecord.position)
        ).scalars().all()

    # ------------------------------------------------------------------ 写读

    def create(
        self,
        revision: CompleteEvidenceProcessingRevision,
        *,
        require_current_heads: bool = True,
    ) -> CompleteEvidenceProcessingRevision:
        if self.session.get(
            EvidenceProcessingRevisionRecord, revision.evidence_processing_revision_id
        ) is not None:
            raise DuplicateRecordError(
                f"证据处理修订 {revision.evidence_processing_revision_id} 已存在"
            )
        # 先做全部闭包校验（失败时不产生任何 root/page/association 行）。
        self._base_revision(revision)
        base_manifest = self._base_manifest(revision)
        base_entries = [
            (
                entry.source_document_version_id,
                entry.page_number,
                entry.original_frame,
                entry.page_artifact_id,
                entry.ocr_page_id,
                entry.status.value,
            )
            for entry in base_manifest
        ]
        revision_entries = [
            (
                entry.source_document_version_id,
                entry.page_number,
                entry.original_frame,
                entry.page_artifact_id,
                entry.ocr_page_id,
                entry.status.value,
            )
            for entry in revision.manifest
        ]
        if base_entries != revision_entries:
            raise RevisionClosureError(
                f"完整修订 {revision.evidence_processing_revision_id} 的页清单必须"
                "逐项等于 base 修订页清单"
            )
        self._verify_referenced(
            revision,
            require_current_heads=require_current_heads,
            require_producer_processing=True,
        )

        # 根、页与全部关联在同一保存点中写入并读回验证。任一 flush/读回失败时，
        # 保存点整体回滚；即使调用方捕获异常后继续提交外层事务，也不会留下
        # is_activatable=True 的半闭包根记录。
        with self.session.begin_nested():
            self._insert_complete_revision(revision)
            self.session.flush()
            created = self.get(revision.evidence_processing_revision_id)
        return created

    def _insert_complete_revision(
        self, revision: CompleteEvidenceProcessingRevision
    ) -> None:
        """向当前事务加入完整修订的根、页和关联；调用方负责原子保存点。"""
        payload_json, payload_sha256 = encode_contract(revision)
        self.session.add(
            EvidenceProcessingRevisionRecord(
                evidence_processing_revision_id=revision.evidence_processing_revision_id,
                evidence_snapshot_id=revision.evidence_snapshot_id,
                project_id=revision.project_id,
                subject_id=revision.subject_id,
                review_episode_id=revision.review_episode_id,
                manifest_sha256=revision.manifest_sha256,
                status=revision.status.value,
                is_activatable=revision.is_activatable,
                revision_kind="complete",
                base_processing_revision_id=revision.base_processing_revision_id,
                producer_candidate_id=revision.producer_candidate_id,
                candidate_input_sha256=revision.candidate_input_sha256,
                completion_manifest_sha256=revision.completion_manifest_sha256,
                created_by=revision.created_by,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                created_at=to_utc_naive(revision.created_at),
            )
        )
        self.session.flush()
        for entry in revision.manifest:
            entry_json, entry_sha = encode_contract(entry)
            self.session.add(
                EvidenceProcessingRevisionPageRecord(
                    revision_id=revision.evidence_processing_revision_id,
                    position=entry.position,
                    entry_id=entry.entry_id,
                    source_document_version_id=entry.source_document_version_id,
                    page_number=entry.page_number,
                    original_frame=entry.original_frame,
                    page_artifact_id=entry.page_artifact_id,
                    ocr_page_id=entry.ocr_page_id,
                    status=entry.status.value,
                    failure_reason=entry.failure_reason,
                    payload_json=entry_json,
                    payload_sha256=entry_sha,
                    created_at=to_utc_naive(revision.created_at),
                )
            )
        self.session.flush()
        assoc = [
            (ProcessingRevisionLocatorRecord, "locator_id", revision.locator_ids),
            (ProcessingRevisionRiskScanRecord, "scan_id", revision.risk_scan_ids),
            (ProcessingRevisionRiskReviewRecord, "review_id", revision.risk_review_ids),
            (ProcessingRevisionCorrectionRecord, "correction_id", revision.correction_ids),
            (
                ProcessingRevisionMetadataRevisionRecord,
                "metadata_revision_id",
                revision.metadata_revision_ids,
            ),
            (
                ProcessingRevisionReferencedDocumentRecord,
                "referenced_document_revision_id",
                revision.referenced_document_revision_ids,
            ),
            (
                ProcessingRevisionResolutionRecord,
                "resolution_revision_id",
                revision.resolution_revision_ids,
            ),
        ]
        for record_cls, ref_column, refs in assoc:
            for position, ref in enumerate(refs):
                self.session.add(
                    record_cls(
                        revision_id=revision.evidence_processing_revision_id,
                        position=position + 1,
                        **{ref_column: ref},
                    )
                )
    def get(self, evidence_processing_revision_id: str) -> CompleteEvidenceProcessingRevision:
        record = _get_required(
            self.session,
            EvidenceProcessingRevisionRecord,
            evidence_processing_revision_id,
            "CompleteEvidenceProcessingRevision",
        )
        contract = self._decode_record(record)
        page_rows = self._verify_page_mirror(contract)
        # 关联子表必须与 payload 有序集合一致（读取时全量闭包 + 顺序校验）。
        self._verify_assoc_mirror(contract)
        # 历史读取验证冻结内容，但不要求所选修订仍是今天的全局链头；否则后续
        # 合法追加会破坏旧报告的精确回放。
        self._verify_referenced(
            contract,
            require_current_heads=False,
            persisted_page_rows=page_rows,
        )
        return contract

    def _verify_page_mirror(
        self, contract: CompleteEvidenceProcessingRevision
    ) -> list[EvidenceProcessingRevisionPageRecord]:
        """实际页子表必须逐项等于根 payload，并校验每条 canonical payload/hash。"""
        rows = self._manifest_rows(contract.evidence_processing_revision_id)
        base_repo = EvidenceProcessingRevisionRepository(self.session)
        actual = [
            base_repo._decode_page_entry(
                row,
                expected_revision_id=contract.evidence_processing_revision_id,
            )
            for row in rows
        ]
        if actual != contract.manifest:
            raise PersistedContractInvalid(
                f"完整修订 {contract.evidence_processing_revision_id} 的实际页子表"
                "与根 payload 页清单不一致"
            )
        return rows

    def _verify_assoc_mirror(self, contract: CompleteEvidenceProcessingRevision) -> None:
        table_specs = [
            (ProcessingRevisionLocatorRecord, "locator_id", contract.locator_ids),
            (ProcessingRevisionRiskScanRecord, "scan_id", contract.risk_scan_ids),
            (ProcessingRevisionRiskReviewRecord, "review_id", contract.risk_review_ids),
            (ProcessingRevisionCorrectionRecord, "correction_id", contract.correction_ids),
            (
                ProcessingRevisionMetadataRevisionRecord,
                "metadata_revision_id",
                contract.metadata_revision_ids,
            ),
            (
                ProcessingRevisionReferencedDocumentRecord,
                "referenced_document_revision_id",
                contract.referenced_document_revision_ids,
            ),
            (
                ProcessingRevisionResolutionRecord,
                "resolution_revision_id",
                contract.resolution_revision_ids,
            ),
        ]
        for record_cls, ref_column, expected in table_specs:
            rows = self.session.execute(
                select(record_cls)
                .where(record_cls.revision_id == contract.evidence_processing_revision_id)
                .order_by(record_cls.position)
            ).scalars().all()
            actual = [getattr(row, ref_column) for row in rows]
            if actual != list(expected):
                raise PersistedContractInvalid(
                    f"完整修订 {contract.evidence_processing_revision_id} 的 "
                    f"{record_cls.__tablename__} 子表与 payload 不一致"
                )

    def list_by_snapshot(self, evidence_snapshot_id: str) -> list[CompleteEvidenceProcessingRevision]:
        rows = self.session.execute(
            select(EvidenceProcessingRevisionRecord)
            .where(EvidenceProcessingRevisionRecord.evidence_snapshot_id == evidence_snapshot_id)
            .where(EvidenceProcessingRevisionRecord.revision_kind == "complete")
            .order_by(EvidenceProcessingRevisionRecord.created_at)
        ).scalars().all()
        return [self.get(row.evidence_processing_revision_id) for row in rows]
