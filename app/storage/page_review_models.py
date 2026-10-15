"""R3 页级判读、对账和受试者页覆盖的不可变持久化模型。"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base
from app.storage.evidence_models import PAYLOAD_SHA_LEN, EvidenceAppendedRecordMixin


class PageReviewRecordORM(EvidenceAppendedRecordMixin, Base):
    __tablename__ = "page_review_records"

    page_review_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    page_artifact_id: Mapped[str] = mapped_column(String(128), ForeignKey("page_artifacts.page_artifact_id"), nullable=False)
    source_document_version_id: Mapped[str] = mapped_column(String(128), ForeignKey("source_document_versions_v2.source_document_version_id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    page_image_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    clause_pack_id: Mapped[str] = mapped_column(String(128), nullable=False)
    clause_pack_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    lane: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str] = mapped_column(String(256), nullable=False)
    reasoning_effort: Mapped[str] = mapped_column(String(16), nullable=False)
    endpoint_base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False)
    finish_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    usage_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    response_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    has_eligibility_value: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (
        CheckConstraint("page_number >= 1", name="ck_prr_page_number"),
        CheckConstraint("lane IN ('main-A','main-B','handwriting-C')", name="ck_prr_lane"),
        Index("ix_prr_page_artifact_id", "page_artifact_id"),
    )


class PageReconciliationORM(EvidenceAppendedRecordMixin, Base):
    __tablename__ = "page_reconciliations"

    reconciliation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    page_artifact_id: Mapped[str] = mapped_column(String(128), ForeignKey("page_artifacts.page_artifact_id"), nullable=False)
    clause_pack_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    handwriting_reader_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (Index("ix_prec_page_artifact_id", "page_artifact_id"),)


class PageReconciliationReviewORM(Base):
    __tablename__ = "page_reconciliation_reviews"

    reconciliation_id: Mapped[str] = mapped_column(String(128), ForeignKey("page_reconciliations.reconciliation_id"), primary_key=True)
    page_review_id: Mapped[str] = mapped_column(String(128), ForeignKey("page_review_records.page_review_id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("position >= 1", name="ck_prr_link_position"),
        UniqueConstraint("reconciliation_id", "position", name="uq_prr_link_position"),
    )


class SubjectPageCoverageORM(EvidenceAppendedRecordMixin, Base):
    __tablename__ = "subject_page_coverages"

    coverage_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(128), ForeignKey("subjects.subject_id"), nullable=False)
    review_episode_id: Mapped[str] = mapped_column(String(128), ForeignKey("review_episodes.review_episode_id"), nullable=False)
    evidence_snapshot_id: Mapped[str] = mapped_column(String(128), ForeignKey("evidence_snapshots_v2.evidence_snapshot_id"), nullable=False)
    evidence_processing_revision_id: Mapped[str] = mapped_column(String(128), ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"), nullable=False)
    clause_pack_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    expected_page_count: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("expected_page_count >= 1", name="ck_spc_expected_page_count"),
        Index("ix_spc_episode_revision", "review_episode_id", "evidence_processing_revision_id"),
    )


class SubjectPageCoverageEntryORM(Base):
    __tablename__ = "subject_page_coverage_entries"

    coverage_id: Mapped[str] = mapped_column(String(128), ForeignKey("subject_page_coverages.coverage_id"), primary_key=True)
    page_artifact_id: Mapped[str] = mapped_column(String(128), ForeignKey("page_artifacts.page_artifact_id"), primary_key=True)
    source_document_version_id: Mapped[str] = mapped_column(String(128), ForeignKey("source_document_versions_v2.source_document_version_id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    disposition: Mapped[str] = mapped_column(String(48), nullable=False)
    reconciliation_id: Mapped[str | None] = mapped_column(String(128), ForeignKey("page_reconciliations.reconciliation_id"), nullable=True)
    discard_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    lane_failures_json: Mapped[list] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        CheckConstraint("page_number >= 1 AND position >= 1", name="ck_spce_position"),
        CheckConstraint("disposition IN ('accepted','discarded_no_eligibility_value','failed_pending_reread')", name="ck_spce_disposition"),
        UniqueConstraint("coverage_id", "position", name="uq_spce_position"),
    )


__all__ = [
    "PageReconciliationORM", "PageReconciliationReviewORM", "PageReviewRecordORM",
    "SubjectPageCoverageEntryORM", "SubjectPageCoverageORM",
]
