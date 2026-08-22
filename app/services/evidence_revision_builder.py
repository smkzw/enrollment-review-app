"""Slice 4.4 完整处理修订构建器（WP-44B）。

从已接受的 WP-44A 仓储聚合当前 in-scope 闭包并冻结一份完整处理修订：

- 页清单与绑定 base 修订逐项相等；逐资料恰好一条链头元数据修订；
- 每页恰好一个所选规则版本的风险扫描；blocking 风险由所选核对或覆盖校对解除；
- 校对集合 = 该 base 修订当前全部有效链头（无重叠、关键变化已二次确认）；
- 被提及资料与满足修订各自恰为链头；
- 定位 = 显式所选 + 被确认被提及资料的触发定位；
- ``completion_manifest_sha256`` 由仓储按 DB 子记录 canonical payload hash 计算。

任何闭包要素缺失/漂移都抛类型化错误，仓储 ``create`` 的保存点保证失败不留下
可激活半闭包根（§8.4 反例 2）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.enums import (
    OcrRiskLevel,
    ProcessingRevisionStatus,
    ReferencedDocumentStatus,
)
from app.domain.contracts.evidence_locator import (
    CompleteEvidenceProcessingRevision,
    CorrectionRecord,
    OCRRiskScan,
)
from app.domain.contracts.evidence_processing import EvidenceProcessingRevision
from app.evidence.risk import (
    OCR_RISK_RULE_VERSION,
    allows_risk_review,
    correction_covers_risk,
)
from app.storage.evidence_locator_models import (
    EvidenceLocatorArtifactRecord,
    OCRRiskReviewRecord,
    ReferencedDocumentResolutionRevisionRecord,
    ReferencedDocumentRevisionRecord,
)
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository,
    CorrectionRepository,
    OCRRiskReviewRepository,
    OCRRiskScanRepository,
    ReferencedDocumentRepository,
)
from app.storage.evidence_repositories import (
    SourceDocumentMetadataRevisionRepository,
)
from app.storage.ocr_repositories import (
    EvidenceProcessingRevisionRepository,
    OcrPageRepository,
)

__all__ = [
    "EvidenceRevisionBuilder",
    "MissingMetadataRevisionError",
    "MissingRiskScanError",
    "RevisionBuildError",
    "RevisionClosure",
    "UnresolvedBlockingRiskError",
]




def _utcnow():
    from datetime import UTC, datetime

    return datetime.now(UTC)

class RevisionBuildError(RuntimeError):
    """完整处理修订闭包聚合错误基类。"""


class MissingRiskScanError(RevisionBuildError):
    """页在所选规则版本下没有任何风险扫描，无法冻结完整修订。"""


class MissingMetadataRevisionError(RevisionBuildError):
    """页清单资料缺少链头元数据修订，无法冻结完整修订。"""


class UnresolvedBlockingRiskError(RevisionBuildError):
    """存在未由核对/覆盖校对解除的 blocking 风险，完整修订不可冻结。"""


@dataclass
class RevisionClosure:
    """从当前 in-scope 旁路工件聚合出的完整修订闭包（确定性选择）。"""

    base_processing_revision_id: str
    metadata_revision_ids: list[str] = field(default_factory=list)
    risk_scan_ids: list[str] = field(default_factory=list)
    risk_review_ids: list[str] = field(default_factory=list)
    correction_ids: list[str] = field(default_factory=list)
    locator_ids: list[str] = field(default_factory=list)
    referenced_document_revision_ids: list[str] = field(default_factory=list)
    resolution_revision_ids: list[str] = field(default_factory=list)
    base_revision: EvidenceProcessingRevision | None = None


class EvidenceRevisionBuilder:
    """完整处理修订闭包聚合与构建（确定性；不写候选事件）。

    ``artifact_store`` 是完整修订闭包门禁所需的真实内容寻址工件库（原生文本/
    坐标证明）；API/工作流不得在无工件库的情况下实例化构建器（WP-44C 验收：
    定位/完整修订读取与构建必须接收真实 ArtifactStore）。
    """

    def __init__(self, artifact_store=None) -> None:
        self.artifact_store = artifact_store
        self._complete_repo_cls = CompleteEvidenceProcessingRevisionRepository

    def gather_closure(
        self,
        session: Session,
        *,
        evidence_snapshot_id: str,
        base_processing_revision_id: str,
        scanner_rule_version: str = OCR_RISK_RULE_VERSION,
        selected_locator_ids: list[str] | None = None,
        review_rule_version: str | None = None,
    ) -> RevisionClosure:
        """聚合当前 in-scope 闭包（确定性选择每页扫描/每个 blocking flag 的核对）。"""
        base_repo = EvidenceProcessingRevisionRepository(session)
        base = base_repo.get(base_processing_revision_id)
        manifest_docs = {entry.source_document_version_id for entry in base.manifest}
        ocr_pages = {
            entry.ocr_page_id for entry in base.manifest if entry.ocr_page_id is not None
        }

        # 逐资料链头元数据修订。
        metadata_ids: list[str] = []
        metadata_repo = SourceDocumentMetadataRevisionRepository(session)
        for doc_id in sorted(manifest_docs):
            head = metadata_repo.head(doc_id)
            if head is None:
                raise MissingMetadataRevisionError(
                    f"资料 {doc_id} 没有链头元数据修订，无法冻结完整处理修订"
                )
            metadata_ids.append(head.metadata_revision_id)

        # 每页恰好一个所选规则版本的风险扫描（同版本至多一个，取最新）。
        scan_repo = OCRRiskScanRepository(session)
        scan_ids: list[str] = []
        scans_by_page: dict[str, OCRRiskScan] = {}
        for ocr_page_id in sorted(ocr_pages):
            candidates = [
                scan
                for scan in scan_repo.list_by_page(ocr_page_id)
                if scan.scanner_rule_version == scanner_rule_version
            ]
            if not candidates:
                raise MissingRiskScanError(
                    f"OCR 页 {ocr_page_id} 在规则版本 {scanner_rule_version} 下没有"
                    "风险扫描，无法冻结完整处理修订"
                )
            chosen = max(candidates, key=lambda s: (s.created_at, s.scan_id))
            scan_ids.append(chosen.scan_id)
            scans_by_page[ocr_page_id] = chosen

        # blocking flag 的核对：逐 flag 取最新核对（无核对则依赖覆盖校对）。
        review_repo = OCRRiskReviewRepository(session)
        selected_flag_ids = {
            f"{scan.scan_id}:{flag.risk_id}"
            for scan in scans_by_page.values()
            for flag in scan.flags
        }
        review_ids: list[str] = []
        for flag_id in sorted(selected_flag_ids):
            rows = session.execute(
                select(OCRRiskReviewRecord).where(
                    OCRRiskReviewRecord.risk_flag_id == flag_id
                )
            ).scalars().all()
            if not rows:
                continue
            contracts = [review_repo.get(row.review_id) for row in rows]
            latest = max(contracts, key=lambda r: (r.created_at, r.review_id))
            review_ids.append(latest.review_id)

        # 当前全部有效校对链头（该 base 修订 + 页）。
        correction_repo = CorrectionRepository(session)
        correction_ids: list[str] = []
        for ocr_page_id in sorted(ocr_pages):
            page_corrections = [
                c
                for c in correction_repo.list_by_page(ocr_page_id)
                if c.base_processing_revision_id == base_processing_revision_id
            ]
            superseded_ids = {c.supersedes_correction_id for c in page_corrections if c.supersedes_correction_id}
            heads = sorted(
                (c for c in page_corrections if c.correction_id not in superseded_ids),
                key=lambda c: (c.text_start, c.text_end, c.correction_id),
            )
            for head in heads:
                correction_ids.append(head.correction_id)

        # 被提及资料与满足修订：审核节点当前链头。
        referenced_ids, resolution_ids = self._gather_referenced(session, base.review_episode_id)

        # 定位：风险扫描已生成的自动定位 + 显式所选 + 被确认登记
        # 资料的触发定位。自动定位必须同时命中本 base 的页工件和本次选中
        # 的风险 flag，不按时间或“最新”猜测。
        locator_ids = list(selected_locator_ids or [])
        page_artifact_ids = {entry.page_artifact_id for entry in base.manifest}
        if selected_flag_ids and page_artifact_ids:
            automatic_rows = session.execute(
                select(EvidenceLocatorArtifactRecord).where(
                    EvidenceLocatorArtifactRecord.target_id.in_(selected_flag_ids),
                    EvidenceLocatorArtifactRecord.page_artifact_id.in_(page_artifact_ids),
                )
            ).scalars().all()
            for row in automatic_rows:
                if row.locator_id not in locator_ids:
                    locator_ids.append(row.locator_id)
        referenced_repo = ReferencedDocumentRepository(session)
        for rid in referenced_ids:
            contract = referenced_repo.get_revision(rid)
            if (
                contract.status == ReferencedDocumentStatus.CONFIRMED
                and contract.trigger_locator_id is not None
            ) and contract.trigger_locator_id not in locator_ids:
                locator_ids.append(contract.trigger_locator_id)

        return RevisionClosure(
            base_processing_revision_id=base_processing_revision_id,
            metadata_revision_ids=sorted(metadata_ids),
            risk_scan_ids=sorted(scan_ids),
            risk_review_ids=sorted(review_ids),
            correction_ids=correction_ids,
            locator_ids=sorted(locator_ids),
            referenced_document_revision_ids=sorted(referenced_ids),
            resolution_revision_ids=sorted(resolution_ids),
            base_revision=base,
        )

    def closure_from_manifest(
        self,
        session: Session,
        *,
        base_processing_revision_id: str,
        metadata_revision_ids: list[str],
        risk_scan_ids: list[str],
        risk_review_ids: list[str],
        correction_ids: list[str],
        locator_ids: list[str],
        referenced_document_revision_ids: list[str],
        resolution_revision_ids: list[str],
    ) -> RevisionClosure:
        """按排队时冻结的精确 ID 清单重建闭包，不查询任何“最新”链头。"""
        base = EvidenceProcessingRevisionRepository(session).get(
            base_processing_revision_id
        )
        return RevisionClosure(
            base_processing_revision_id=base_processing_revision_id,
            metadata_revision_ids=list(metadata_revision_ids),
            risk_scan_ids=list(risk_scan_ids),
            risk_review_ids=list(risk_review_ids),
            correction_ids=list(correction_ids),
            locator_ids=list(locator_ids),
            referenced_document_revision_ids=list(
                referenced_document_revision_ids
            ),
            resolution_revision_ids=list(resolution_revision_ids),
            base_revision=base,
        )

    @staticmethod
    def _gather_referenced(
        session: Session, review_episode_id: str
    ) -> tuple[list[str], list[str]]:
        registration_rows = session.execute(
            select(ReferencedDocumentRevisionRecord).where(
                ReferencedDocumentRevisionRecord.review_episode_id == review_episode_id
            )
        ).scalars().all()
        referenced_ids: list[str] = []
        resolution_ids: list[str] = []
        if not registration_rows:
            return [], []
        superseded_registration_ids = {
            r.supersedes_revision_id for r in registration_rows if r.supersedes_revision_id
        }
        heads = [
            r
            for r in registration_rows
            if r.revision_id not in superseded_registration_ids
        ]
        for head in sorted(heads, key=lambda r: r.referenced_document_id):
            status = (
                head.status.value if hasattr(head.status, "value") else head.status
            )
            # “解除”表示这项候选不属于本次资料闭包。历史修订仍完整保留，
            # 但不能再把已解除的链头冻结进新的完整资料版本。
            if status == ReferencedDocumentStatus.DISMISSED.value:
                continue
            referenced_ids.append(head.revision_id)
            res_rows = session.execute(
                select(ReferencedDocumentResolutionRevisionRecord).where(
                    ReferencedDocumentResolutionRevisionRecord.referenced_document_id
                    == head.referenced_document_id
                )
            ).scalars().all()
            superseded_res = {
                r.supersedes_resolution_revision_id
                for r in res_rows
                if r.supersedes_resolution_revision_id
            }
            res_heads = [r for r in res_rows if r.resolution_revision_id not in superseded_res]
            if res_heads:
                res_head = max(res_heads, key=lambda r: r.revision)
                resolution_ids.append(res_head.resolution_revision_id)
        return referenced_ids, resolution_ids

    def build(
        self,
        session: Session,
        *,
        closure: RevisionClosure,
        evidence_snapshot_id: str,
        project_id: str,
        subject_id: str,
        review_episode_id: str,
        created_by: str,
        producer_candidate_id: str,
        candidate_input_sha256: str,
        revision_id: str | None = None,
        require_current_heads: bool = True,
    ) -> CompleteEvidenceProcessingRevision:
        """按闭包构建完整修订并交由仓储冻结（失败不留下可激活半闭包根）。"""
        base = closure.base_revision
        if base is None:
            raise RevisionBuildError("完整修订闭包缺少 base 修订")
        revision = CompleteEvidenceProcessingRevision(
            evidence_processing_revision_id=revision_id or f"complete-{uuid4().hex}",
            evidence_snapshot_id=evidence_snapshot_id,
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=review_episode_id,
            base_processing_revision_id=closure.base_processing_revision_id,
            producer_candidate_id=producer_candidate_id,
            candidate_input_sha256=candidate_input_sha256,
            manifest=base.manifest,
            manifest_sha256=base.manifest_sha256,
            locator_ids=closure.locator_ids,
            risk_scan_ids=closure.risk_scan_ids,
            risk_review_ids=closure.risk_review_ids,
            correction_ids=closure.correction_ids,
            metadata_revision_ids=closure.metadata_revision_ids,
            referenced_document_revision_ids=closure.referenced_document_revision_ids,
            resolution_revision_ids=closure.resolution_revision_ids,
            completion_manifest_sha256="0" * 64,
            status=ProcessingRevisionStatus.READY,
            is_activatable=True,
            created_at=_utcnow(),
            created_by=created_by,
        )
        repo = self._complete_repo_cls(session, self.artifact_store)
        return repo.create(
            revision.model_copy(
                update={"completion_manifest_sha256": repo.manifest_sha256_for(revision)}
            ),
            require_current_heads=require_current_heads,
        )

    def assert_blocking_resolved(
        self, session: Session, closure: RevisionClosure
    ) -> None:
        """门禁前置：每个 blocking flag 必须由所选核对或覆盖校对解除。"""
        scan_repo = OCRRiskScanRepository(session)
        correction_repo = CorrectionRepository(session)
        selected_scan_contracts = {
            scan_id: scan_repo.get(scan_id) for scan_id in closure.risk_scan_ids
        }
        review_contracts = [
            OCRRiskReviewRepository(session).get(rid)
            for rid in closure.risk_review_ids
        ]
        reviewed_flags = {r.risk_flag_id for r in review_contracts}
        correction_contracts: list[CorrectionRecord] = [
            correction_repo.get(cid) for cid in closure.correction_ids
        ]
        page_lengths = {
            scan.ocr_page_id: len(OcrPageRepository(session).get(scan.ocr_page_id).raw_text)
            for scan in selected_scan_contracts.values()
        }
        for scan_id, scan in selected_scan_contracts.items():
            for flag in scan.flags:
                if flag.level != OcrRiskLevel.BLOCKING:
                    continue
                flag_id = f"{scan_id}:{flag.risk_id}"
                if flag_id in reviewed_flags and allows_risk_review(flag):
                    continue
                covered = any(
                    c.ocr_page_id == scan.ocr_page_id
                    and correction_covers_risk(
                        flag,
                        correction_text_start=c.text_start,
                        correction_text_end=c.text_end,
                        page_text_length=page_lengths[scan.ocr_page_id],
                    )
                    for c in correction_contracts
                )
                if not covered:
                    raise UnresolvedBlockingRiskError(
                        f"blocking 风险 {flag_id} 未由选中核对或覆盖校对解除，"
                        "完整处理修订不可冻结"
                    )
