"""R3 页级判读持久化：追加写、来源闭包和关联闭包校验。"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.page_review import (
    PageReconciliation,
    PageReviewLane,
    PageReviewRecord,
    SubjectPageCoverage,
)
from app.storage.codecs import (
    PersistedContractInvalid,
    check_column_mirrors,
    decode_contract,
    encode_contract,
    to_utc_naive,
)
from app.storage.evidence_models import EvidenceSnapshotV2Record, SourceDocumentVersionV2Record
from app.storage.models import ReviewEpisodeRecord, SubjectRecord
from app.storage.ocr_models import (
    EvidenceProcessingRevisionPageRecord,
    EvidenceProcessingRevisionRecord,
    PageArtifactRecord,
)
from app.storage.page_review_models import (
    PageReconciliationORM,
    PageReconciliationReviewORM,
    PageReviewRecordORM,
    SubjectPageCoverageEntryORM,
    SubjectPageCoverageORM,
)
from app.storage.repositories import (
    DuplicateRecordError,
    InvalidReferenceError,
    ScopeViolationError,
    _flush_guarded,
    _get_required,
)


def _same_or_conflict(row, payload_sha256: str, what: str):
    if row is None:
        return None
    if row.payload_sha256 != payload_sha256:
        raise DuplicateRecordError(f"{what}身份已存在但合同内容不同")
    return row


class PageReviewRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _verify_page(self, record: PageReviewRecord) -> None:
        page = _get_required(
            self.session, PageArtifactRecord, record.page_artifact_id, "页产物"
        )
        expected = (
            record.source_document_version_id,
            record.page_number,
            record.page_image_sha256,
        )
        actual = (
            page.source_document_version_id,
            page.page_number,
            page.page_image_sha256,
        )
        if actual != expected:
            raise ScopeViolationError("页级判读与页产物的资料版本、页码或图像哈希不一致")

    def save_review(self, record: PageReviewRecord) -> PageReviewRecord:
        self._verify_page(record)
        payload_json, payload_sha256 = encode_contract(record)
        existing = _same_or_conflict(
            self.session.get(PageReviewRecordORM, record.page_review_id),
            payload_sha256,
            "页级判读",
        )
        if existing is not None:
            return self.get_review(record.page_review_id)
        self.session.add(
            PageReviewRecordORM(
                page_review_id=record.page_review_id,
                page_artifact_id=record.page_artifact_id,
                source_document_version_id=record.source_document_version_id,
                page_number=record.page_number,
                page_image_sha256=record.page_image_sha256,
                clause_pack_id=record.clause_pack_id,
                clause_pack_sha256=record.clause_pack_sha256,
                lane=record.lane.value,
                provider=record.provider,
                model=record.model,
                reasoning_effort=record.reasoning_effort,
                endpoint_base_url=record.endpoint_base_url,
                fallback_used=record.fallback_used,
                finish_reason=record.finish_reason,
                usage_json=dict(record.usage),
                prompt_version=record.prompt_version,
                response_sha256=record.response_sha256,
                has_eligibility_value=record.has_eligibility_value,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                created_at=to_utc_naive(record.created_at),
            )
        )
        _flush_guarded(self.session)
        return record

    def get_review(self, page_review_id: str) -> PageReviewRecord:
        row = self.session.get(PageReviewRecordORM, page_review_id)
        if row is None:
            raise InvalidReferenceError(f"页级判读 {page_review_id!r} 不存在")
        record = decode_contract(PageReviewRecord, row.payload_json, row.payload_sha256)
        check_column_mirrors(
            "PageReviewRecord", row, json.loads(row.payload_json),
            {
                "page_review_id": "page_review_id", "page_artifact_id": "page_artifact_id",
                "source_document_version_id": "source_document_version_id", "page_number": "page_number",
                "page_image_sha256": "page_image_sha256", "clause_pack_id": "clause_pack_id",
                "clause_pack_sha256": "clause_pack_sha256", "lane": "lane",
                "provider": "provider", "model": "model", "reasoning_effort": "reasoning_effort",
                "endpoint_base_url": "endpoint_base_url", "fallback_used": "fallback_used",
                "finish_reason": "finish_reason", "prompt_version": "prompt_version",
                "response_sha256": "response_sha256", "has_eligibility_value": "has_eligibility_value",
                "created_at": "created_at",
            },
        )
        if dict(row.usage_json or {}) != record.usage:
            raise PersistedContractInvalid("页级判读 usage_json 与合同正文不一致")
        self._verify_page(record)
        return record

    def save_reconciliation(self, record: PageReconciliation) -> PageReconciliation:
        reviews = [self.get_review(item) for item in record.page_review_ids]
        if any(
            item.page_artifact_id != record.page_artifact_id
            or item.clause_pack_sha256 != record.clause_pack_sha256
            for item in reviews
        ):
            raise ScopeViolationError("页级对账引用了其他页面或其他条款包的判读")
        main_lanes = {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}
        if not main_lanes <= {item.lane for item in reviews}:
            raise ScopeViolationError("页级对账必须同时引用两个主读道")
        payload_json, payload_sha256 = encode_contract(record)
        existing = _same_or_conflict(
            self.session.get(PageReconciliationORM, record.reconciliation_id),
            payload_sha256,
            "页级对账",
        )
        if existing is not None:
            return self.get_reconciliation(record.reconciliation_id)
        self.session.add(
            PageReconciliationORM(
                reconciliation_id=record.reconciliation_id,
                page_artifact_id=record.page_artifact_id,
                clause_pack_sha256=record.clause_pack_sha256,
                handwriting_reader_triggered=record.handwriting_reader_triggered,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                created_at=to_utc_naive(record.created_at),
            )
        )
        _flush_guarded(self.session)
        for position, page_review_id in enumerate(record.page_review_ids, 1):
            self.session.add(
                PageReconciliationReviewORM(
                    reconciliation_id=record.reconciliation_id,
                    page_review_id=page_review_id,
                    position=position,
                )
            )
        _flush_guarded(self.session)
        return record

    def get_reconciliation(self, reconciliation_id: str) -> PageReconciliation:
        row = self.session.get(PageReconciliationORM, reconciliation_id)
        if row is None:
            raise InvalidReferenceError(f"页级对账 {reconciliation_id!r} 不存在")
        record = decode_contract(PageReconciliation, row.payload_json, row.payload_sha256)
        payload = json.loads(row.payload_json)
        mirrors = {
            "reconciliation_id": "reconciliation_id", "page_artifact_id": "page_artifact_id",
            "clause_pack_sha256": "clause_pack_sha256", "created_at": "created_at",
        }
        if "handwriting_reader_triggered" in payload:
            # Legacy receipts from the retired third read keep the mirrored column.
            mirrors["handwriting_reader_triggered"] = "handwriting_reader_triggered"
        check_column_mirrors("PageReconciliation", row, payload, mirrors)
        links = self.session.scalars(
            select(PageReconciliationReviewORM)
            .where(PageReconciliationReviewORM.reconciliation_id == reconciliation_id)
            .order_by(PageReconciliationReviewORM.position)
        ).all()
        if [item.page_review_id for item in links] != record.page_review_ids:
            raise PersistedContractInvalid("页级对账引用清单与合同正文不一致")
        reviews = [self.get_review(item) for item in record.page_review_ids]
        if any(item.page_artifact_id != record.page_artifact_id for item in reviews):
            raise PersistedContractInvalid("页级对账来源闭包不成立")
        return record

    def save_coverage(self, record: SubjectPageCoverage) -> SubjectPageCoverage:
        self._verify_coverage_scope(record)
        payload_json, payload_sha256 = encode_contract(record)
        existing = _same_or_conflict(
            self.session.get(SubjectPageCoverageORM, record.coverage_id),
            payload_sha256,
            "受试者页覆盖",
        )
        if existing is not None:
            return self.get_coverage(record.coverage_id)
        self.session.add(
            SubjectPageCoverageORM(
                coverage_id=record.coverage_id,
                subject_id=record.subject_id,
                review_episode_id=record.review_episode_id,
                evidence_snapshot_id=record.evidence_snapshot_id,
                evidence_processing_revision_id=record.evidence_processing_revision_id,
                clause_pack_sha256=record.clause_pack_sha256,
                expected_page_count=len(record.expected_page_artifact_ids),
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                created_at=to_utc_naive(record.created_at),
            )
        )
        _flush_guarded(self.session)
        for position, entry in enumerate(record.entries, 1):
            self.session.add(
                SubjectPageCoverageEntryORM(
                    coverage_id=record.coverage_id,
                    page_artifact_id=entry.page_artifact_id,
                    source_document_version_id=entry.source_document_version_id,
                    page_number=entry.page_number,
                    position=position,
                    disposition=entry.disposition.value,
                    reconciliation_id=entry.reconciliation_id,
                    discard_reason=entry.discard_reason,
                    lane_failures_json=[item.model_dump(mode="json") for item in entry.lane_failures],
                )
            )
        _flush_guarded(self.session)
        return record

    def get_coverage(self, coverage_id: str) -> SubjectPageCoverage:
        row = self.session.get(SubjectPageCoverageORM, coverage_id)
        if row is None:
            raise InvalidReferenceError(f"受试者页覆盖 {coverage_id!r} 不存在")
        record = decode_contract(SubjectPageCoverage, row.payload_json, row.payload_sha256)
        check_column_mirrors(
            "SubjectPageCoverage", row, json.loads(row.payload_json),
            {
                "coverage_id": "coverage_id", "subject_id": "subject_id",
                "review_episode_id": "review_episode_id", "evidence_snapshot_id": "evidence_snapshot_id",
                "evidence_processing_revision_id": "evidence_processing_revision_id",
                "clause_pack_sha256": "clause_pack_sha256", "created_at": "created_at",
            },
        )
        entries = self.session.scalars(
            select(SubjectPageCoverageEntryORM)
            .where(SubjectPageCoverageEntryORM.coverage_id == coverage_id)
            .order_by(SubjectPageCoverageEntryORM.position)
        ).all()
        if row.expected_page_count != len(record.expected_page_artifact_ids):
            raise PersistedContractInvalid("页覆盖计数与合同正文不一致")
        persisted = [
            {
                "page_artifact_id": item.page_artifact_id,
                "source_document_version_id": item.source_document_version_id,
                "page_number": item.page_number,
                "disposition": item.disposition,
                "reconciliation_id": item.reconciliation_id,
                "discard_reason": item.discard_reason,
                "lane_failures": list(item.lane_failures_json or []),
            }
            for item in entries
        ]
        if persisted != [item.model_dump(mode="json") for item in record.entries]:
            raise PersistedContractInvalid("页覆盖处置关联表与合同正文不一致")
        self._verify_coverage_scope(record)
        return record

    def _verify_coverage_scope(self, record: SubjectPageCoverage) -> None:
        if record.predecessor_coverage_id is not None:
            if record.predecessor_coverage_id == record.coverage_id:
                raise ScopeViolationError("资料重读不能引用自身作为前次结果")
            previous = _get_required(self.session, SubjectPageCoverageORM,
                                     record.predecessor_coverage_id, "前次页覆盖")
            predecessor = decode_contract(SubjectPageCoverage, previous.payload_json, previous.payload_sha256)
            fields = ("subject_id", "review_episode_id", "evidence_snapshot_id",
                      "evidence_processing_revision_id", "clause_pack_sha256",
                      "expected_page_artifact_ids", "execution_versions", "main_reader_identity_sha256")
            if any(getattr(predecessor, key) != getattr(record, key) for key in fields):
                raise ScopeViolationError("资料重读与前次结果的来源或处理版本不一致")
            if (not any(entry.lane_failures for entry in predecessor.entries)
                    and predecessor.reading_rotations == record.reading_rotations):
                raise ScopeViolationError("资料重读既无失败页面，也无阅读方向变更")
        subject = _get_required(self.session, SubjectRecord, record.subject_id, "受试者")
        episode = _get_required(self.session, ReviewEpisodeRecord, record.review_episode_id, "审核节点")
        snapshot = _get_required(self.session, EvidenceSnapshotV2Record, record.evidence_snapshot_id, "证据快照")
        revision = _get_required(self.session, EvidenceProcessingRevisionRecord, record.evidence_processing_revision_id, "证据处理修订")
        if episode.subject_id != subject.subject_id or snapshot.subject_id != subject.subject_id or revision.subject_id != subject.subject_id:
            raise ScopeViolationError("页覆盖的受试者作用域不一致")
        if snapshot.review_episode_id != episode.review_episode_id or revision.review_episode_id != episode.review_episode_id:
            raise ScopeViolationError("页覆盖的审核节点作用域不一致")
        if revision.evidence_snapshot_id != snapshot.evidence_snapshot_id:
            raise ScopeViolationError("页覆盖的处理修订不属于指定证据快照")
        revision_pages = self.session.scalars(
            select(EvidenceProcessingRevisionPageRecord)
            .where(EvidenceProcessingRevisionPageRecord.revision_id == revision.evidence_processing_revision_id)
            .order_by(EvidenceProcessingRevisionPageRecord.position)
        ).all()
        page_ids = [item.page_artifact_id for item in revision_pages]
        if page_ids != record.expected_page_artifact_ids:
            raise ScopeViolationError("页覆盖预期清单必须等于处理修订冻结的有序页清单")
        for entry in record.entries:
            page = _get_required(self.session, PageArtifactRecord, entry.page_artifact_id, "页产物")
            if (page.source_document_version_id, page.page_number) != (entry.source_document_version_id, entry.page_number):
                raise ScopeViolationError("页覆盖处置与页产物来源不一致")
            document = _get_required(self.session, SourceDocumentVersionV2Record, entry.source_document_version_id, "资料版本")
            if document.subject_id != record.subject_id or document.review_episode_id != record.review_episode_id:
                raise ScopeViolationError("页覆盖引用了其他受试者或审核节点的资料")
            if entry.reconciliation_id:
                reconciliation = self.get_reconciliation(entry.reconciliation_id)
                if reconciliation.page_artifact_id != entry.page_artifact_id or reconciliation.clause_pack_sha256 != record.clause_pack_sha256:
                    raise ScopeViolationError("页覆盖采信的对账记录不属于该页或该条款包")
                expected_rotation = record.reading_rotations.get(entry.page_artifact_id)
                for review_id in reconciliation.page_review_ids:
                    review = self.get_review(review_id)
                    actual_rotation = review.reading_view.clockwise_degrees if review.reading_view else None
                    if actual_rotation != expected_rotation:
                        raise ScopeViolationError("页覆盖记录与实际判读的阅读方向不一致")


__all__ = ["PageReviewRepository"]
