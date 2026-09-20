"""Slice 4.4 证据读取应用服务（WP-44C 薄 API 边界）。

所有只读投影都收口到本服务：页分层读取、处理修订读取（base/complete + 逐门禁）、
被提及资料链头、快照/审核节点/受试者读取与当前版本指针投影。路由只做协议转换，
不再直接访问 SQLAlchemy/存储仓储/幂等表；本服务接收真实 ``ArtifactStore``，定位与
完整修订读取/门禁校验必须在有工件库的情况下进行。

历史精确回放（§8.3/§8.4）：指定处理修订时，只返回该完整修订冻结的
risk scan / risk review / correction / locator（属于请求页），后加的旁路工件
绝不混入旧修订回放；未指定修订时返回当前旁路工件。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict

from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.enums import OcrRiskLevel
from app.domain.contracts.evidence_ingestion import (
    EvidenceSnapshot,
    SourceDocumentMetadataRevision,
    SourceDocumentVersion,
)
from app.domain.contracts.evidence_locator import (
    CompleteEvidenceProcessingRevision,
    CorrectionRecord,
    EvidenceLocatorArtifact,
    EvidenceProcessingCandidate,
    OCRRiskReview,
    OCRRiskScan,
    ReferencedDocumentResolutionRevision,
    ReferencedDocumentRevision,
)
from app.domain.contracts.evidence_processing import EvidenceProcessingRevision
from app.domain.contracts.evidence_upload import EvidenceUploadCommit
from app.domain.contracts.ocr import OCRPage
from app.domain.contracts.review import ReviewEpisode, Subject
from app.domain.contracts.rules import WorkflowStage
from app.evidence.artifacts import ArtifactStore
from app.evidence.effective_text import EffectiveTextProjection, project_effective_text
from app.evidence.risk import (
    OCR_RISK_RULE_VERSION,
    allows_risk_review,
    correction_covers_risk,
)
from app.services.evidence_app_errors import (
    AppInternalError,
    AppNotFoundError,
    app_error_boundary,
)
from app.services.evidence_referenced_document_service import (
    EvidenceReferencedDocumentService,
)
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository,
    CorrectionRepository,
    EvidenceLocatorRepository,
    EvidenceProcessingCandidateRepository,
    OcrRevisionKindError,
    OCRRiskReviewRepository,
    OCRRiskScanRepository,
)
from app.storage.evidence_repositories import (
    EvidenceSnapshotRepository,
    SourceDocumentMetadataRevisionRepository,
    SourceDocumentRepository,
)
from app.storage.evidence_upload_repositories import EvidenceUploadCommitRepository
from app.storage.ocr_repositories import (
    EvidenceProcessingRevisionRepository,
    OcrPageRepository,
    PageArtifactRepository,
)
from app.storage.repositories import (
    EpisodeRepository,
    NotFoundError,
    SubjectRepository,
    get_project_row,
)
from app.storage.read_retention import retain_read_records

__all__ = [
    "EvidenceApiReadService",
    "GateSummary",
    "OcrPageView",
    "PageImageView",
    "ReferencedHeadView",
    "RevisionView",
]


@dataclass(frozen=True)
class GateSummary:
    """激活门禁逐项结果（读路径已由仓储强校验，此处如实汇总）。"""

    gate: str
    status: str  # "passed" | "not_applicable"
    detail: str


@dataclass(frozen=True)
class SourceDocumentSummary:
    version: SourceDocumentVersion
    metadata: SourceDocumentMetadataRevision


@dataclass(frozen=True)
class RevisionView:
    """处理修订读取视图：base 或 complete + 逐门禁。"""

    revision_id: str
    kind: str  # "base" | "complete"
    is_current: bool
    base: EvidenceProcessingRevision | None = None
    complete: CompleteEvidenceProcessingRevision | None = None
    gates: list[GateSummary] = field(default_factory=list)
    page_dimensions: dict[str, tuple[float, float]] = field(default_factory=dict)
    risk_flag_count: int = 0
    pending_risk_flag_count: int = 0


class _RiskCounts(TypedDict):
    risk_flag_count: int
    pending_risk_flag_count: int


@dataclass(frozen=True)
class OcrPageView:
    """页分层读取视图：原文 / 有效文本投影 / 所选校对 / 风险核对 / 定位并列。"""

    ocr: OCRPage
    episode_id: str
    revision_id: str | None
    is_current_revision: bool
    active_snapshot_id: str | None
    active_revision_id: str | None
    source_document_version_id: str | None = None
    effective: EffectiveTextProjection | None = None
    selected_corrections: list[CorrectionRecord] = field(default_factory=list)
    risk_scans: list[OCRRiskScan] = field(default_factory=list)
    risk_reviews: list[OCRRiskReview] = field(default_factory=list)
    locators: list[EvidenceLocatorArtifact] = field(default_factory=list)


@dataclass(frozen=True)
class PageImageView:
    """处理修订中一页的不可变原始页图及固有尺寸。"""

    content: bytes
    page_width: float
    page_height: float
    content_sha256: str


@dataclass(frozen=True)
class ReferencedHeadView:
    """被提及资料当前登记修订 + 当前满足修订。"""

    revision: ReferencedDocumentRevision
    resolution: ReferencedDocumentResolutionRevision | None = None


@dataclass(frozen=True)
class ProcessingCandidateView:
    """后台资料版本候选的持久状态与恢复序号。"""

    candidate: EvidenceProcessingCandidate
    event_seq: int


class EvidenceApiReadService:
    """证据读取应用服务（只读；页/修订/被提及资料/快照/审核节点/受试者投影）。"""

    def __init__(
        self,
        session_factory: sessionmaker,
        artifact_store: ArtifactStore,
    ) -> None:
        self.session_factory = session_factory
        self.artifact_store = artifact_store

    @app_error_boundary
    def processing_candidate(self, candidate_id: str) -> ProcessingCandidateView:
        """读取候选当前投影；页面刷新后仍可据此恢复核对任务。"""
        with self.session_factory() as session:
            repository = EvidenceProcessingCandidateRepository(
                session, self.artifact_store
            )
            candidate = repository.get(candidate_id)
            return ProcessingCandidateView(
                candidate=candidate,
                event_seq=len(repository.get_events(candidate_id)),
            )

    @app_error_boundary
    def latest_processing_candidate_for_snapshot(
        self, evidence_snapshot_id: str
    ) -> ProcessingCandidateView | None:
        """Return the latest persisted candidate so page re-entry is server-led."""
        with self.session_factory() as session:
            repository = EvidenceProcessingCandidateRepository(
                session, self.artifact_store
            )
            candidate = repository.latest_by_snapshot(evidence_snapshot_id)
            if candidate is None:
                return None
            return ProcessingCandidateView(
                candidate=candidate,
                event_seq=len(repository.get_events(candidate.candidate_id)),
            )

    @app_error_boundary
    def base_processing_revision_id_for_snapshot(
        self, evidence_snapshot_id: str
    ) -> str | None:
        """返回快照当前唯一可继续核对的基础处理修订；尚未生成时返回空。"""
        with self.session_factory() as session:
            revisions = EvidenceProcessingRevisionRepository(
                session
            ).list_by_snapshot(evidence_snapshot_id)
            if not revisions:
                return None
            return revisions[-1].evidence_processing_revision_id

    # ------------------------------------------------------------------ 页读取

    @app_error_boundary
    def page_view(
        self,
        ocr_page_id: str,
        processing_revision_id: str | None = None,
    ) -> OcrPageView:
        """读取当前有效页或待启用基础页；可读边界不改变完整修订激活门禁。"""
        from app.services.evidence_correction_service import EvidenceCorrectionService

        with self.session_factory() as session:
            ocr = OcrPageRepository(session).get(ocr_page_id)  # 404 if missing
            episode_id = self._episode_for_ocr_page(session, ocr_page_id)
            active_snapshot, active_revision = self._episode_pointer(
                session, episode_id
            )
            revision_id = (
                processing_revision_id
                if processing_revision_id is not None
                else active_revision
            )

            corrections: list[CorrectionRecord] = []
            effective: EffectiveTextProjection | None = None
            scans: list[OCRRiskScan] = []
            reviews: list[OCRRiskReview] = []
            locators: list[EvidenceLocatorArtifact] = []

            if revision_id is not None:
                try:
                    complete = self._load_complete(session, revision_id)
                except OcrRevisionKindError:
                    complete = None
                    base = EvidenceProcessingRevisionRepository(session).get(
                        revision_id
                    )
                    revision_episode_id = base.review_episode_id
                    manifest = base.manifest
                else:
                    revision_episode_id = complete.review_episode_id
                    manifest = complete.manifest

                if revision_episode_id != episode_id:
                    from app.storage.repositories import ScopeViolationError

                    raise ScopeViolationError(
                        f"处理修订 {revision_id} 与 OCR 页所属审核节点不一致"
                    )
                if not any(
                    entry.ocr_page_id == ocr_page_id
                    for entry in manifest
                ):
                    from app.storage.repositories import ScopeViolationError

                    raise ScopeViolationError(
                        f"处理修订 {revision_id} 的页清单未包含 OCR 页 {ocr_page_id}"
                    )
                if complete is None:
                    all_corrections = [
                        item
                        for item in CorrectionRepository(session).list_by_page(
                            ocr_page_id
                        )
                        if item.base_processing_revision_id == revision_id
                    ]
                    superseded_ids = {
                        item.supersedes_correction_id
                        for item in all_corrections
                        if item.supersedes_correction_id is not None
                    }
                    corrections = sorted(
                        (
                            item
                            for item in all_corrections
                            if item.correction_id not in superseded_ids
                        ),
                        key=lambda c: (c.text_start, c.text_end, c.correction_id),
                    )
                    if corrections:
                        effective = project_effective_text(ocr.raw_text, corrections)
                    scans = self._current_risk_scans(session, ocr_page_id)
                    reviews = self._current_reviews(
                        session,
                        ocr_page_id,
                        base_processing_revision_id=revision_id,
                        scans=scans,
                    )
                    locator_repo = EvidenceLocatorRepository(
                        session, self.artifact_store
                    )
                    locators = [
                        locator_repo.get(row.locator_id)
                        for row in session.execute(
                            self._locator_rows_stmt(ocr_page_id)
                        ).scalars().all()
                        if row.processing_revision_id in (None, revision_id)
                    ]
                else:
                    correction_repo = CorrectionRepository(session)
                    corrections = sorted(
                        (
                            correction_repo.get(cid)
                            for cid in complete.correction_ids
                            if correction_repo.get(cid).ocr_page_id == ocr_page_id
                        ),
                        key=lambda c: (c.text_start, c.text_end, c.correction_id),
                    )
                    effective = EvidenceCorrectionService(
                        self.session_factory, artifact_store=self.artifact_store
                    ).effective_text_for_page(revision_id, ocr_page_id)
                    # 冻结旁路工件：只取该完整修订选中的、且属于本页的 sidecar。
                    scan_repo = OCRRiskScanRepository(session)
                    scans = [
                        scan_repo.get(sid)
                        for sid in complete.risk_scan_ids
                        if scan_repo.get(sid).ocr_page_id == ocr_page_id
                    ]
                    review_repo = OCRRiskReviewRepository(session)
                    reviews = [
                        review_repo.get(rid)
                        for rid in complete.risk_review_ids
                        if self._review_belongs_to_page(session, rid, ocr_page_id)
                    ]
                    locator_repo = EvidenceLocatorRepository(
                        session, self.artifact_store
                    )
                    locators = [
                        locator_repo.get(lid)
                        for lid in complete.locator_ids
                        if locator_repo.get(lid).ocr_page_id == ocr_page_id
                    ]
            else:
                scans = self._current_risk_scans(session, ocr_page_id)
                reviews = self._current_reviews(session, ocr_page_id)
                locator_repo = EvidenceLocatorRepository(
                    session, self.artifact_store
                )
                locators = [
                    locator_repo.get(row.locator_id)
                    for row in session.execute(
                        self._locator_rows_stmt(ocr_page_id)
                    ).scalars().all()
                ]

            return OcrPageView(
                ocr=ocr,
                episode_id=episode_id,
                revision_id=revision_id,
                is_current_revision=(
                    revision_id is not None and revision_id == active_revision
                ),
                active_snapshot_id=active_snapshot,
                active_revision_id=active_revision,
                source_document_version_id=(
                    PageArtifactRepository(session)
                    .get(ocr.page_artifact_id)
                    .source_document_version_id
                ),
                effective=effective,
                selected_corrections=corrections,
                risk_scans=scans,
                risk_reviews=reviews,
                locators=locators,
            )

    @staticmethod
    def _review_belongs_to_page(session, review_id: str, ocr_page_id: str) -> bool:
        """核对决议属于请求页：其 flag 所在 scan 绑定该 OCR 页。"""
        from app.storage.evidence_locator_models import (
            OCRRiskFlagRecord,
            OCRRiskReviewRecord,
        )

        review = session.get(OCRRiskReviewRecord, review_id)
        if review is None:
            return False
        flag = session.get(OCRRiskFlagRecord, review.risk_flag_id)
        return flag is not None and flag.ocr_page_id == ocr_page_id

    @staticmethod
    def _current_risk_scans(session, ocr_page_id: str) -> list[OCRRiskScan]:
        """优先返回现行扫描规则结果；尚未重扫时保留旧结果供追溯。"""
        scans = OCRRiskScanRepository(session).list_by_page(ocr_page_id)
        current = [
            scan
            for scan in scans
            if scan.scanner_rule_version == OCR_RISK_RULE_VERSION
        ]
        return current or scans

    def _current_reviews(
        self,
        session,
        ocr_page_id: str,
        *,
        base_processing_revision_id: str | None = None,
        scans: list[OCRRiskScan] | None = None,
    ) -> list[OCRRiskReview]:
        scans = scans if scans is not None else self._current_risk_scans(session, ocr_page_id)
        flag_ids = {
            f"{scan.scan_id}:{flag.risk_id}"
            for scan in scans
            for flag in scan.flags
        }
        if not flag_ids:
            return []
        from sqlalchemy import select

        from app.storage.evidence_locator_models import OCRRiskReviewRecord

        statement = select(OCRRiskReviewRecord).where(
            OCRRiskReviewRecord.risk_flag_id.in_(flag_ids)
        )
        if base_processing_revision_id is not None:
            statement = statement.where(
                OCRRiskReviewRecord.base_processing_revision_id
                == base_processing_revision_id
            )
        rows = session.execute(statement).scalars().all()
        review_repo = OCRRiskReviewRepository(session)
        return sorted(
            (review_repo.get(row.review_id) for row in rows),
            key=lambda r: (r.created_at, r.review_id),
        )

    @staticmethod
    def _locator_rows_stmt(ocr_page_id: str):
        from sqlalchemy import select

        from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord

        return (
            select(EvidenceLocatorArtifactRecord)
            .where(EvidenceLocatorArtifactRecord.ocr_page_id == ocr_page_id)
        )

    # ------------------------------------------------------------------ 修订读取

    @app_error_boundary
    def revision_view(self, revision_id: str) -> RevisionView:
        """处理修订读取：base 走基础仓储，complete 走完整仓储 + 逐门禁。"""
        with self.session_factory() as session:
            try:
                complete = self._load_complete(session, revision_id)
                episode_id = complete.review_episode_id
            except OcrRevisionKindError:
                complete = None
                base = EvidenceProcessingRevisionRepository(session).get(
                    revision_id
                )
                episode_id = base.review_episode_id
                _active_snapshot, active_revision = self._episode_pointer(
                    session, episode_id
                )
                return RevisionView(
                    revision_id=revision_id,
                    kind="base",
                    is_current=(active_revision == revision_id),
                    base=base,
                    gates=self._base_gates(base),
                    page_dimensions=self._page_dimensions(session, base.manifest),
                    **self._risk_counts(
                        session,
                        revision_id=revision_id,
                        manifest=base.manifest,
                        complete=None,
                    ),
                )
            _active_snapshot, active_revision = self._episode_pointer(
                session, episode_id
            )
            return RevisionView(
                revision_id=revision_id,
                kind="complete",
                is_current=(active_revision == revision_id),
                complete=complete,
                gates=self._complete_gates(session, complete),
                page_dimensions=self._page_dimensions(session, complete.manifest),
                **self._risk_counts(
                    session,
                    revision_id=revision_id,
                    manifest=complete.manifest,
                    complete=complete,
                ),
            )

    def _risk_counts(
        self, session, *, revision_id: str, manifest, complete
    ) -> _RiskCounts:
        """Aggregate the same frozen/current page risk state exposed by page reads."""
        scan_repo = OCRRiskScanRepository(session)
        review_repo = OCRRiskReviewRepository(session)
        correction_repo = CorrectionRepository(session)
        all_flags = []
        reviewed_flag_ids: set[str] = set()
        corrections = []

        if complete is not None:
            scans = scan_repo.get_many(complete.risk_scan_ids)
            reviews = review_repo.get_many(complete.risk_review_ids)
            corrections = correction_repo.get_many(complete.correction_ids)
            reviewed_flag_ids = {review.risk_flag_id for review in reviews}
        else:
            page_ids = [
                entry.ocr_page_id
                for entry in manifest
                if entry.ocr_page_id is not None
            ]
            all_scans = scan_repo.list_by_pages(page_ids)
            scans_by_page: dict[str, list[OCRRiskScan]] = {
                page_id: [] for page_id in page_ids
            }
            for scan in all_scans:
                scans_by_page[scan.ocr_page_id].append(scan)
            scans = []
            for page_id in page_ids:
                page_scans = scans_by_page[page_id]
                current = [
                    scan
                    for scan in page_scans
                    if scan.scanner_rule_version == OCR_RISK_RULE_VERSION
                ]
                scans.extend(current or page_scans)

            flag_ids = {
                f"{scan.scan_id}:{flag.risk_id}"
                for scan in scans
                for flag in scan.flags
            }
            reviews = review_repo.list_for_flags(
                flag_ids,
                base_processing_revision_id=revision_id,
            )
            reviewed_flag_ids = {review.risk_flag_id for review in reviews}
            page_corrections = correction_repo.list_by_pages(
                page_ids,
                base_processing_revision_id=revision_id,
            )
            superseded_ids = {
                correction.supersedes_correction_id
                for correction in page_corrections
                if correction.supersedes_correction_id is not None
            }
            corrections = [
                correction
                for correction in page_corrections
                if correction.correction_id not in superseded_ids
            ]

        page_ids = [
            entry.ocr_page_id for entry in manifest if entry.ocr_page_id is not None
        ]
        pages = OcrPageRepository(session).get_many(page_ids)
        page_lengths = {page.ocr_page_id: len(page.raw_text) for page in pages}
        pending = 0
        for scan in scans:
            for flag in scan.flags:
                flag_id = f"{scan.scan_id}:{flag.risk_id}"
                all_flags.append(flag_id)
                if flag_id in reviewed_flag_ids and allows_risk_review(flag):
                    continue
                if any(
                    correction.ocr_page_id == scan.ocr_page_id
                    and correction_covers_risk(
                        flag,
                        correction_text_start=correction.text_start,
                        correction_text_end=correction.text_end,
                        page_text_length=page_lengths[scan.ocr_page_id],
                    )
                    for correction in corrections
                ):
                    continue
                pending += 1
        return {
            "risk_flag_count": len(all_flags),
            "pending_risk_flag_count": pending,
        }

    @staticmethod
    def _page_dimensions(session, manifest) -> dict[str, tuple[float, float]]:
        dimensions: dict[str, tuple[float, float]] = {}
        repository = PageArtifactRepository(session)
        artifacts = repository.get_many(
            [entry.page_artifact_id for entry in manifest]
        )
        for entry, artifact in zip(manifest, artifacts, strict=True):
            if (
                artifact.page_image_sha256 is not None
                and artifact.page_width is not None
                and artifact.page_height is not None
            ):
                dimensions[entry.entry_id] = (
                    artifact.page_width,
                    artifact.page_height,
                )
        return dimensions

    @app_error_boundary
    def page_image(self, revision_id: str, entry_id: str) -> PageImageView:
        """按冻结修订页清单读取页图，拒绝跨修订猜测或追随后来产物。"""
        with self.session_factory() as session, retain_read_records(session):
            try:
                revision = self._load_complete(session, revision_id)
                manifest = revision.manifest
            except OcrRevisionKindError:
                manifest = EvidenceProcessingRevisionRepository(session).get(
                    revision_id
                ).manifest
            entry = next((item for item in manifest if item.entry_id == entry_id), None)
            if entry is None:
                raise AppNotFoundError("该处理版本中没有这一个原始资料页。")
            artifact = PageArtifactRepository(session).get(entry.page_artifact_id)
            if (
                artifact.page_image_sha256 is None
                or artifact.page_width is None
                or artifact.page_height is None
            ):
                raise AppNotFoundError("该页处理未完成，目前没有可显示的原始页图。")
            content = self.artifact_store.read_by_sha(
                "page_image", artifact.page_image_sha256
            )
            return PageImageView(
                content=content,
                page_width=artifact.page_width,
                page_height=artifact.page_height,
                content_sha256=artifact.page_image_sha256,
            )

    def _base_gates(self, base: EvidenceProcessingRevision) -> list[GateSummary]:
        return [
            GateSummary("scope", "passed", "基础处理修订只冻结页产物与识别结果"),
            GateSummary(
                "page_closure",
                "passed",
                f"页清单 {len(base.manifest)} 页与快照一致",
            ),
            GateSummary("risk", "not_applicable", "基础处理修订不参与识别风险核对门禁"),
            GateSummary("correction", "not_applicable", "基础处理修订不投影校对层"),
            GateSummary("metadata", "passed", "基础处理修订冻结当时资料元数据"),
            GateSummary(
                "referenced",
                "not_applicable",
                "基础处理修订不冻结被提及资料闭包",
            ),
            GateSummary("locator", "not_applicable", "基础处理修订不冻结证据定位"),
            GateSummary("manifest", "passed", "基础处理修订清单哈希校验一致"),
        ]

    def _complete_gates(
        self, session: Session, complete: CompleteEvidenceProcessingRevision
    ) -> list[GateSummary]:
        """逐门禁结果投影：读路径已由仓储强校验，此处对已冻结合同如实汇总。"""
        base = EvidenceProcessingRevisionRepository(session).get(
            complete.base_processing_revision_id
        )
        gates: list[GateSummary] = []

        scope_ok = (
            base.project_id == complete.project_id
            and base.subject_id == complete.subject_id
            and base.review_episode_id == complete.review_episode_id
            and base.evidence_snapshot_id == complete.evidence_snapshot_id
        )
        gates.append(
            GateSummary(
                "scope",
                "passed" if scope_ok else "not_applicable",
                "项目/受试者/审核节点/快照与基础修订一致",
            )
        )

        page_ok = len(complete.manifest) == len(base.manifest) and all(
            (
                a.source_document_version_id,
                a.page_number,
                a.page_artifact_id,
                a.ocr_page_id,
                a.status.value if hasattr(a.status, "value") else a.status,
            )
            == (
                b.source_document_version_id,
                b.page_number,
                b.page_artifact_id,
                b.ocr_page_id,
                b.status.value if hasattr(b.status, "value") else b.status,
            )
            for a, b in zip(complete.manifest, base.manifest)
        )
        gates.append(
            GateSummary(
                "page_closure",
                "passed" if page_ok else "not_applicable",
                f"页清单 {len(complete.manifest)} 页与基础修订逐项一致",
            )
        )

        scan_repo = OCRRiskScanRepository(session)
        scans = {scan_id: scan_repo.get(scan_id) for scan_id in complete.risk_scan_ids}
        review_repo = OCRRiskReviewRepository(session)
        reviews = [review_repo.get(rid) for rid in complete.risk_review_ids]
        correction_repo = CorrectionRepository(session)
        corrections = [
            correction_repo.get(cid) for cid in complete.correction_ids
        ]
        reviewed_flags = {review.risk_flag_id for review in reviews}
        ocr_page_ids = {
            entry.ocr_page_id
            for entry in complete.manifest
            if entry.ocr_page_id is not None
        }
        blocking_total = 0
        blocking_covered = 0
        page_lengths = {
            page_id: len(OcrPageRepository(session).get(page_id).raw_text)
            for page_id in ocr_page_ids
        }
        for scan in scans.values():
            for flag in scan.flags:
                level = (
                    flag.level.value if hasattr(flag.level, "value") else flag.level
                )
                if level != OcrRiskLevel.BLOCKING.value:
                    continue
                blocking_total += 1
                flag_id = f"{scan.scan_id}:{flag.risk_id}"
                if flag_id in reviewed_flags and allows_risk_review(flag):
                    blocking_covered += 1
                    continue
                if any(
                    c.ocr_page_id == scan.ocr_page_id
                    and correction_covers_risk(
                        flag,
                        correction_text_start=c.text_start,
                        correction_text_end=c.text_end,
                        page_text_length=page_lengths[scan.ocr_page_id],
                    )
                    for c in corrections
                ):
                    blocking_covered += 1
        risk_ok = len(scans) == len(ocr_page_ids) and blocking_total == blocking_covered
        gates.append(
            GateSummary(
                "risk",
                "passed" if risk_ok else "not_applicable",
                f"{len(scans)}/{len(ocr_page_ids)} 页有风险扫描，"
                f"{blocking_covered}/{blocking_total} 条阻断风险已核对",
            )
        )

        overlap = False
        for i in range(len(corrections)):
            for j in range(i + 1, len(corrections)):
                a, b = corrections[i], corrections[j]
                if a.ocr_page_id != b.ocr_page_id:
                    continue
                if (
                    a.correction_id == b.supersedes_correction_id
                    or b.correction_id == a.supersedes_correction_id
                ):
                    continue
                if a.text_start < b.text_end and b.text_start < a.text_end:
                    overlap = True
        confirmation_ok = all(
            (not c.requires_confirmation) or c.confirmation_actor is not None
            for c in corrections
        )
        gates.append(
            GateSummary(
                "correction",
                "passed" if (not overlap) and confirmation_ok else "not_applicable",
                f"{len(corrections)} 条校对，范围无重叠冲突且关键变化已完成二次确认",
            )
        )

        manifest_docs = {
            entry.source_document_version_id for entry in complete.manifest
        }
        metadata_ok = len(complete.metadata_revision_ids) == len(manifest_docs)
        gates.append(
            GateSummary(
                "metadata",
                "passed" if metadata_ok else "not_applicable",
                f"{len(complete.metadata_revision_ids)}/{len(manifest_docs)} "
                "份资料有链头元数据修订",
            )
        )

        referenced_ok = True
        for rid in complete.referenced_document_revision_ids:
            try:
                from app.storage.evidence_locator_repositories import (
                    ReferencedDocumentRepository,
                )

                ReferencedDocumentRepository(session).get_revision(rid)
            except NotFoundError:
                referenced_ok = False
        for rid in complete.resolution_revision_ids:
            try:
                from app.storage.evidence_locator_repositories import (
                    ReferencedDocumentRepository,
                )

                ReferencedDocumentRepository(session).get_resolution(rid)
            except NotFoundError:
                referenced_ok = False
        gates.append(
            GateSummary(
                "referenced",
                "passed" if referenced_ok else "not_applicable",
                f"{len(complete.referenced_document_revision_ids)} 条登记修订 / "
                f"{len(complete.resolution_revision_ids)} 条满足修订可回放",
            )
        )

        locator_repo = EvidenceLocatorRepository(session, self.artifact_store)
        manifest_artifacts = {entry.page_artifact_id for entry in complete.manifest}
        locator_ok = True
        for lid in complete.locator_ids:
            try:
                if locator_repo.get(lid).page_artifact_id not in manifest_artifacts:
                    locator_ok = False
            except NotFoundError:
                locator_ok = False
        gates.append(
            GateSummary(
                "locator",
                "passed" if locator_ok else "not_applicable",
                f"{len(complete.locator_ids)} 条定位均绑定本修订页产物",
            )
        )

        manifest_ok = (
            complete.completion_manifest_sha256
            == CompleteEvidenceProcessingRevisionRepository(
                session, self.artifact_store
            ).manifest_sha256_for(complete)
        )
        gates.append(
            GateSummary(
                "manifest",
                "passed" if manifest_ok else "not_applicable",
                "闭包清单哈希与 base/页/子工件 payload 重算一致",
            )
        )
        return gates

    # ------------------------------------------------------------------ 被提及资料

    @app_error_boundary
    def referenced_heads(
        self, review_episode_id: str
    ) -> list[ReferencedHeadView]:
        """某审核节点下被提及资料的当前登记链头 + 当前满足状态（只读投影）。"""
        from sqlalchemy import select

        from app.storage.evidence_locator_models import (
            ReferencedDocumentRevisionRecord,
        )
        from app.storage.evidence_locator_repositories import (
            ReferencedDocumentRepository,
        )

        with self.session_factory() as session:
            rows = session.execute(
                select(ReferencedDocumentRevisionRecord).where(
                    ReferencedDocumentRevisionRecord.review_episode_id
                    == review_episode_id
                )
            ).scalars().all()
            if not rows:
                return []
            repo = ReferencedDocumentRepository(session)
            superseded = {
                r.supersedes_revision_id
                for r in rows
                if r.supersedes_revision_id is not None
            }
            heads = sorted(
                (r for r in rows if r.revision_id not in superseded),
                key=lambda r: r.referenced_document_id,
            )
            return [
                ReferencedHeadView(
                    revision=repo.get_revision(head.revision_id),
                    resolution=self._resolution_head(
                        session, head.referenced_document_id
                    ),
                )
                for head in heads
            ]

    @app_error_boundary
    def referenced_head(
        self, referenced_document_id: str
    ) -> ReferencedHeadView | None:
        """单个被提及资料当前链头 + 满足状态。"""

        with self.session_factory() as session:
            revision = EvidenceReferencedDocumentService.revision_head(
                session, referenced_document_id
            )
            if revision is None:
                return None
            return ReferencedHeadView(
                revision=revision,
                resolution=self._resolution_head(session, referenced_document_id),
            )

    @staticmethod
    def _resolution_head(
        session, referenced_document_id: str
    ) -> ReferencedDocumentResolutionRevision | None:
        return EvidenceReferencedDocumentService.resolution_head(
            session, referenced_document_id
        )

    # ------------------------------------------------------------------ 快照/审核节点/受试者

    @app_error_boundary
    def snapshot(self, snapshot_id: str) -> EvidenceSnapshot:
        with self.session_factory() as session:
            return EvidenceSnapshotRepository(session).get(snapshot_id)

    @app_error_boundary
    def snapshot_list(self, review_episode_id: str) -> list[EvidenceSnapshot]:
        with self.session_factory() as session:
            return EvidenceSnapshotRepository(session).list_by_episode(
                review_episode_id
            )

    @app_error_boundary
    def upload_processing_job_id_for_snapshot(self, snapshot_id: str) -> str | None:
        """Return the upload job even before a processing candidate exists."""
        with self.session_factory() as session:
            return EvidenceUploadCommitRepository(
                session
            ).processing_job_id_for_snapshot(snapshot_id)

    @app_error_boundary
    def source_document_version(self, version_id: str):
        with self.session_factory() as session:
            return SourceDocumentRepository(session).get(version_id)

    @app_error_boundary
    def locators_by_ids(
        self,
        locator_ids: list[str],
        *,
        complete_processing_revision_id: str,
    ) -> dict[str, EvidenceLocatorArtifact]:
        """批量读取冻结完整修订内的定位，供档案原文深链使用。"""
        ordered_ids = list(dict.fromkeys(locator_ids))
        if not ordered_ids:
            return {}
        with self.session_factory() as session:
            complete = self._load_complete(session, complete_processing_revision_id)
            outside = sorted(set(ordered_ids) - set(complete.locator_ids))
            try:
                locators = EvidenceLocatorRepository(
                    session, self.artifact_store
                ).get_many(ordered_ids)
            except NotFoundError as exc:
                raise AppInternalError(
                    "病历档案的证据定位与冻结资料版本不一致，无法安全打开原文。"
                    if outside else "病历档案引用的原文定位已不完整，无法安全打开原文。"
                ) from exc
            by_id = {locator.locator_id: locator for locator in locators}
            if outside:
                from app.storage.page_review_visual_locator_validation import (
                    VisualLocatorBatchContext,
                    verify_visual_locator,
                )

                # 闭包外视觉定位（页判读发布后追加）也共享同一会话的批量核验
                # 上下文：核验语义不变，只去掉每个定位重复的完整修订闭包
                # 重验（实测每定位约 1.4-2.1s，100 个定位会把档案页拖到
                # 3 分钟以上直至前端超时）。
                batch = VisualLocatorBatchContext(session)
                for locator_id in outside:
                    locator = by_id[locator_id]
                    if locator.page_review_visual is None:
                        raise AppInternalError("病历档案的证据定位与资料版本不一致，暂时无法打开原文。")
                    coverage = verify_visual_locator(session, locator, batch=batch)
                    if (coverage.evidence_processing_revision_id, coverage.evidence_snapshot_id,
                        coverage.review_episode_id) != (
                        complete.evidence_processing_revision_id, complete.evidence_snapshot_id,
                        complete.review_episode_id
                    ):
                        raise AppInternalError("病历档案的证据定位与资料版本不一致，暂时无法打开原文。")
            return {locator.locator_id: locator for locator in locators}

    @app_error_boundary
    def source_document_metadata_heads(
        self, version_ids: list[str]
    ) -> dict[str, SourceDocumentMetadataRevision]:
        """快照成员所属资料的当前分类建议/人工修订投影。"""
        with self.session_factory() as session:
            heads = SourceDocumentMetadataRevisionRepository(
                session
            ).heads_by_document_ids(version_ids)
            missing = sorted(set(version_ids) - set(heads))
            if missing:
                raise AppNotFoundError("部分资料还没有可核对的分类信息。")
            return heads

    @app_error_boundary
    def source_document_summaries(
        self, version_ids: list[str]
    ) -> dict[str, SourceDocumentSummary]:
        """一次会话读取快照成员的版本与当前元数据链头。"""
        with self.session_factory() as session:
            versions = SourceDocumentRepository(session).get_many(version_ids)
            metadata = SourceDocumentMetadataRevisionRepository(
                session
            ).heads_by_document_ids(version_ids)
            missing = sorted(set(version_ids) - set(metadata))
            if missing:
                raise AppNotFoundError("部分资料还没有可核对的分类信息。")
            return {
                version_id: SourceDocumentSummary(
                    version=versions[version_id], metadata=metadata[version_id]
                )
                for version_id in version_ids
            }

    @app_error_boundary
    def commit(self, commit_id: str) -> EvidenceUploadCommit:
        with self.session_factory() as session:
            return EvidenceUploadCommitRepository(session).get(commit_id)

    @app_error_boundary
    def episode(self, review_episode_id: str) -> ReviewEpisode:
        with self.session_factory() as session:
            return EpisodeRepository(session).get(review_episode_id)

    @app_error_boundary
    def episode_pointer(
        self, review_episode_id: str
    ) -> tuple[str | None, str | None]:
        """当前版本唯一权威：审核节点成对活动指针（绝不按时间/状态/顺序回退）。"""
        with self.session_factory() as session:
            return self._episode_pointer(session, review_episode_id)

    @app_error_boundary
    def require_subject_episode(
        self, subject_id: str, review_episode_id: str
    ) -> ReviewEpisode:
        """派生并重验作用域：审核节点必须属于路径受试者（跨对象一律 404）。"""
        with self.session_factory() as session:
            return self._require_subject_episode(session, subject_id, review_episode_id)

    @app_error_boundary
    def subject(self, subject_id: str) -> Subject:
        with self.session_factory() as session:
            return SubjectRepository(session).get(subject_id)

    @app_error_boundary
    def subjects_by_project(self, project_id: str) -> list[Subject]:
        with self.session_factory() as session:
            return SubjectRepository(session).list_by_project(project_id)

    @app_error_boundary
    def episodes_by_subject(
        self, subject_id: str, project_id: str
    ) -> list[ReviewEpisode]:
        with self.session_factory() as session:
            return EpisodeRepository(session).list_by_subject(
                subject_id, project_id=project_id
            )

    @app_error_boundary
    def latest_snapshot_id(self, review_episode_id: str) -> str | None:
        """返回该审核节点最近建立的资料快照，不改变活动版本的定义。"""
        with self.session_factory() as session:
            snapshots = EvidenceSnapshotRepository(session).list_by_episode(
                review_episode_id
            )
            return snapshots[-1].evidence_snapshot_id if snapshots else None

    @app_error_boundary
    def project_row(self, project_id: str):
        """返回 (Project, 当前 rule_set_revision)；项目不存在时返回 None。"""
        with self.session_factory() as session:
            return get_project_row(session, project_id)

    @app_error_boundary
    def workflow_stages_by_ids(
        self, workflow_stage_ids: list[str]
    ) -> dict[str, WorkflowStage]:
        """按命名空间化流程节点 ID 批量读取发布节点（单条 SELECT，禁止 N+1）。"""
        from app.storage.repositories import get_workflow_stages_by_ids

        with self.session_factory() as session:
            return get_workflow_stages_by_ids(session, workflow_stage_ids)

    @app_error_boundary
    def progress(self, job_id: str, job_state_labels: dict[str, str]):
        """只读证据处理进度投影（按持久 OCR 运行/页状态给出中文业务进度）。"""
        from app.services.evidence_progress_service import build_progress

        with self.session_factory() as session:
            return build_progress(session, job_id, job_state_labels=job_state_labels)

    # ------------------------------------------------------------------ 工具

    def _load_complete(
        self, session, revision_id: str
    ) -> CompleteEvidenceProcessingRevision:
        return CompleteEvidenceProcessingRevisionRepository(
            session, self.artifact_store
        ).get(revision_id)

    @staticmethod
    def _episode_for_ocr_page(session, ocr_page_id: str) -> str:
        ocr = OcrPageRepository(session).get(ocr_page_id)  # 不存在 -> 404
        artifact = PageArtifactRepository(session).get(ocr.page_artifact_id)
        document = SourceDocumentRepository(session).get(
            artifact.source_document_version_id
        )
        return document.review_episode_id

    @staticmethod
    def _episode_pointer(
        session, review_episode_id: str
    ) -> tuple[str | None, str | None]:
        episode = EpisodeRepository(session).get(review_episode_id)
        return (
            episode.active_evidence_snapshot_id,
            episode.active_evidence_processing_revision_id,
        )

    @staticmethod
    def _require_subject_episode(session, subject_id: str, review_episode_id: str):
        episode = EpisodeRepository(session).get(review_episode_id)
        if episode.subject_id != subject_id:
            raise NotFoundError(
                f"审核节点 {review_episode_id} 不属于受试者 {subject_id}"
            )
        return episode
