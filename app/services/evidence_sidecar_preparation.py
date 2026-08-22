"""基础资料页的风险提示、定位与增量沿用准备。

该服务只在不可变 OCR 页之上追加旁路记录，不修改原文，也不产生临床事实或入排判断。
处理任务完成基础修订时立即调用，使用户第一次打开工作台时就能看到
风险提示与真实定位；构建命令会幂等重复调用，用于兼容旧候选资料。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.enums import LocatorSourceLayer, UploadMode
from app.domain.contracts.evidence_locator import CorrectionRecord, OCRRiskReview
from app.domain.publication import canonical_hash
from app.evidence.artifacts import ArtifactStore
from app.evidence.risk import OCR_RISK_RULE_VERSION
from app.services.evidence_locator_service import EvidenceLocatorService, LocatorRequest
from app.services.evidence_risk_service import EvidenceRiskScanService
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository,
    CorrectionRepository,
    OCRRiskReviewRepository,
)
from app.storage.evidence_locator_models import (
    CorrectionRecordRecord,
    OCRRiskReviewRecord,
)
from app.storage.evidence_repositories import EvidenceSnapshotRepository
from app.storage.ocr_repositories import (
    EvidenceProcessingRevisionRepository,
    OcrPageRepository,
    PageArtifactRepository,
)
from app.storage.repositories import EpisodeRepository

__all__ = ["EvidenceSidecarPreparationService"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class EvidenceSidecarPreparationService:
    """幂等准备基础修订的风险提示、定位和可沿用人工记录。"""

    def __init__(
        self,
        session_factory: sessionmaker,
        artifact_store: ArtifactStore,
    ) -> None:
        self.session_factory = session_factory
        self.artifact_store = artifact_store

    def prepare(
        self,
        base_processing_revision_id: str,
        *,
        scanner_rule_version: str = OCR_RISK_RULE_VERSION,
    ) -> None:
        with self.session_factory() as session, session.begin():
            self.prepare_in_session(
                session,
                base_processing_revision_id,
                scanner_rule_version=scanner_rule_version,
            )

    def prepare_in_session(
        self,
        session: Session,
        base_processing_revision_id: str,
        *,
        scanner_rule_version: str = OCR_RISK_RULE_VERSION,
    ) -> None:
        base = EvidenceProcessingRevisionRepository(session).get(
            base_processing_revision_id
        )
        scans = []
        risk_service = EvidenceRiskScanService(self.session_factory)
        for entry in base.manifest:
            if entry.ocr_page_id is None:
                continue
            scan = risk_service.scan_page_in_session(
                session,
                entry.ocr_page_id,
                rule_version=scanner_rule_version,
            )
            scans.append((entry, scan))

        self._carry_forward_unchanged_sidecars(session, base, scans)
        self._create_risk_locators(session, scans)

    def _carry_forward_unchanged_sidecars(self, session, base, scans) -> None:
        snapshot = EvidenceSnapshotRepository(session).get(base.evidence_snapshot_id)
        if snapshot.upload_mode != UploadMode.INCREMENTAL or snapshot.prior_snapshot_id is None:
            return

        episode = EpisodeRepository(session).get(base.review_episode_id)
        prior_revision_id = episode.active_evidence_processing_revision_id
        if (
            episode.active_evidence_snapshot_id != snapshot.prior_snapshot_id
            or prior_revision_id is None
        ):
            return

        prior = CompleteEvidenceProcessingRevisionRepository(
            session, self.artifact_store
        ).get(prior_revision_id)
        current_ocr_pages = {
            entry.ocr_page_id for entry in base.manifest if entry.ocr_page_id is not None
        }
        current_flag_ids = {
            f"{scan.scan_id}:{flag.risk_id}"
            for _entry, scan in scans
            for flag in scan.flags
        }
        review_repo = OCRRiskReviewRepository(session)
        for previous_id in prior.risk_review_ids:
            previous = review_repo.get(previous_id)
            if previous.risk_flag_id not in current_flag_ids:
                continue
            carried_id = "rv-carry-" + canonical_hash(
                {
                    "base": base.evidence_processing_revision_id,
                    "previous": previous.review_id,
                }
            )[:32]
            if session.get(OCRRiskReviewRecord, carried_id) is not None:
                continue
            review_repo.create(
                OCRRiskReview(
                    review_id=carried_id,
                    risk_flag_id=previous.risk_flag_id,
                    decision=previous.decision,
                    reason=(
                        "原始识别页未变化，沿用上一有效资料版本的核对结果。"
                        f"原核对说明：{previous.reason}"
                    ),
                    actor="系统沿用",
                    base_processing_revision_id=base.evidence_processing_revision_id,
                    expected_revision=episode.revision,
                    created_at=_utcnow(),
                )
            )

        correction_repo = CorrectionRepository(session)
        for previous_id in prior.correction_ids:
            previous = correction_repo.get(previous_id)
            if previous.ocr_page_id not in current_ocr_pages:
                continue
            carried_id = "corr-carry-" + canonical_hash(
                {
                    "base": base.evidence_processing_revision_id,
                    "previous": previous.correction_id,
                }
            )[:32]
            if session.get(CorrectionRecordRecord, carried_id) is not None:
                continue
            correction_repo.create(
                CorrectionRecord(
                    correction_id=carried_id,
                    ocr_page_id=previous.ocr_page_id,
                    raw_text_sha256=previous.raw_text_sha256,
                    text_start=previous.text_start,
                    text_end=previous.text_end,
                    original_text=previous.original_text,
                    corrected_text=previous.corrected_text,
                    change_kind=previous.change_kind,
                    requires_confirmation=previous.requires_confirmation,
                    confirmation_actor=previous.confirmation_actor,
                    confirmation_at=previous.confirmation_at,
                    reason=(
                        "原始识别页未变化，沿用上一有效资料版本的校对结果。"
                        f"原校对说明：{previous.reason}"
                    ),
                    actor="系统沿用",
                    base_processing_revision_id=base.evidence_processing_revision_id,
                    supersedes_correction_id=None,
                    affected_scope=list(previous.affected_scope),
                    created_at=_utcnow(),
                )
            )

    def _create_risk_locators(self, session, scans) -> None:
        locator_service = EvidenceLocatorService(
            self.session_factory, self.artifact_store
        )
        ocr_repo = OcrPageRepository(session)
        artifact_repo = PageArtifactRepository(session)
        for entry, scan in scans:
            if entry.ocr_page_id is None:
                continue
            ocr_page = ocr_repo.get(entry.ocr_page_id)
            artifact = artifact_repo.get(entry.page_artifact_id)
            use_native = (
                artifact.native_text_sha256 == ocr_page.raw_text_sha256
                and artifact.native_coordinates_sha256 is not None
            )
            source_layer = (
                LocatorSourceLayer.NATIVE_TEXT
                if use_native
                else LocatorSourceLayer.RAW_OCR
            )
            for flag in scan.flags:
                locator_service.create_locator_in_session(
                    session,
                    LocatorRequest(
                        page_artifact_id=entry.page_artifact_id,
                        ocr_page_id=entry.ocr_page_id,
                        source_layer=source_layer,
                        source_text_sha256=ocr_page.raw_text_sha256,
                        target_id=f"{scan.scan_id}:{flag.risk_id}",
                        target_text_start=flag.text_start,
                        target_text_end=flag.text_end,
                        excerpt=flag.text,
                    ),
                )
