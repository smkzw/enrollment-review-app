"""Slice 4.4 定位、风险、校对、被提及资料、处理候选与活动版本 ORM（WP-44A）。

迁移 ``0010_evidence_locator_corrections`` 必须以本模块的表名/列/约束为准创建
下列表；与 0008/0008a/0009 及 Phase 3 表共存并外键隔离，绝不回写 4.3 原 OCR、
基础修订 payload/hash 或页清单：

- ``evidence_locator_artifacts``            occurrence-aware 定位旁路工件；
- ``ocr_risk_scans`` / ``ocr_risk_flags``   OCR 风险扫描（旁路）与逐风险条目；
- ``ocr_risk_reviews``                      用户对单个风险的追加写核对决议；
- ``correction_records``                    校对覆盖层记录（supersede 链）；
- ``referenced_document_revisions`` / ``referenced_document_resolution_revisions``
                                            “资料中提及但未提供”的两层不可变修订；
- ``evidence_activation_events``            激活/回滚追加事件；
- ``evidence_processing_candidates`` / ``evidence_processing_candidate_events``
                                            处理候选状态机（事件投影当前状态）；
- ``processing_revision_{locators,risk_scans,risk_reviews,corrections,
  metadata_revisions,referenced_documents,resolutions}``
                                            完整处理修订的有序旁路工件关联。

约定与 ``evidence_models.py`` 一致：追加写记录保存 canonical JSON payload + SHA-256，
规范化列用于检索并在读取时与 payload 交叉核对；时间列统一 UTC naive。
活动版本指针（``review_episodes.active_evidence_*``）只在候选通过全部发布门禁后
原子更新，本模块不承担激活事务，只提供追加写事件与关联存储。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base
from app.storage.evidence_models import PAYLOAD_SHA_LEN, EvidenceAppendedRecordMixin


class EvidenceLocatorArtifactRecord(EvidenceAppendedRecordMixin, Base):
    """occurrence-aware 定位旁路工件（追加写，不可变）。

    定位身份至少包含页工件、来源层、来源文本哈希、目标范围/上下文锚点与算法版本；
    bbox 必须由同源坐标 sidecar 证明。``processing_revision_id`` 仅在
    ``source_layer='effective_text'`` 时非空。
    """

    __tablename__ = "evidence_locator_artifacts"

    locator_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    page_artifact_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("page_artifacts.page_artifact_id"), nullable=False
    )
    ocr_page_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("ocr_pages.ocr_page_id"), nullable=True
    )
    source_document_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("source_document_versions_v2.source_document_version_id"),
        nullable=False,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_layer: Mapped[str] = mapped_column(String(16), nullable=False)
    source_text_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    precision: Mapped[str] = mapped_column(String(16), nullable=False)
    bbox_x0: Mapped[float | None] = mapped_column(nullable=True)
    bbox_y0: Mapped[float | None] = mapped_column(nullable=True)
    bbox_x1: Mapped[float | None] = mapped_column(nullable=True)
    bbox_y1: Mapped[float | None] = mapped_column(nullable=True)
    coordinate_space: Mapped[str | None] = mapped_column(String(32), nullable=True)
    frame_page_width: Mapped[float | None] = mapped_column(nullable=True)
    frame_page_height: Mapped[float | None] = mapped_column(nullable=True)
    frame_rotation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transform_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sidecar_sha256: Mapped[str | None] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=True
    )
    text_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    anchor_hash: Mapped[str | None] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=True
    )
    disambiguation: Mapped[str] = mapped_column(String(32), nullable=False)
    locator_algorithm_version: Mapped[str] = mapped_column(String(128), nullable=False)
    coordinate_transform_version: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    authenticity: Mapped[str] = mapped_column(String(16), nullable=False)
    effective_text_sha256: Mapped[str | None] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=True
    )
    processing_revision_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"),
        nullable=True,
    )
    match_confidence: Mapped[float | None] = mapped_column(nullable=True)
    degradation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_locator_page_artifact_id", "page_artifact_id"),
        Index("ix_locator_target_id", "target_id"),
    )


class OCRRiskScanRecord(EvidenceAppendedRecordMixin, Base):
    """对某一原始 OCR 哈希 + 规则版本的完整风险集合（追加旁路）。

    同一三元组 (ocr_page_id, raw_text_sha256, scanner_rule_version) 幂等复用；
    规则版本变化新建扫描，不覆盖旧扫描。
    """

    __tablename__ = "ocr_risk_scans"

    scan_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    ocr_page_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("ocr_pages.ocr_page_id"), nullable=False
    )
    raw_text_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )
    scanner_rule_version: Mapped[str] = mapped_column(String(128), nullable=False)
    flags_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    coverage_status: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "ocr_page_id",
            "raw_text_sha256",
            "scanner_rule_version",
            name="uq_ocr_risk_scans_triple",
        ),
        Index("ix_ocr_risk_scans_ocr_page_id", "ocr_page_id"),
    )


class OCRRiskFlagRecord(EvidenceAppendedRecordMixin, Base):
    """风险扫描的一条结构化风险（追加写，不可变）。

    ``flag_id`` 是全局稳定引用（供 OCRRiskReview 指向）；``risk_id`` 是扫描内
    OcrRiskFlag 的稳定身份，同 scan 内唯一。
    """

    __tablename__ = "ocr_risk_flags"

    flag_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    scan_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("ocr_risk_scans.scan_id"), nullable=False
    )
    risk_id: Mapped[str] = mapped_column(String(128), nullable=False)
    ocr_page_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("ocr_pages.ocr_page_id"), nullable=False
    )
    raw_text_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_start: Mapped[int] = mapped_column(Integer, nullable=False)
    text_end: Mapped[int] = mapped_column(Integer, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_version: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        UniqueConstraint("scan_id", "risk_id", name="uq_ocr_risk_flags_scan_risk"),
        Index("ix_ocr_risk_flags_ocr_page_id", "ocr_page_id"),
    )


class OCRRiskReviewRecord(EvidenceAppendedRecordMixin, Base):
    """用户对单个 OCR 风险的追加写核对决议。"""

    __tablename__ = "ocr_risk_reviews"

    review_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    risk_flag_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("ocr_risk_flags.flag_id"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    base_processing_revision_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"),
        nullable=False,
    )
    expected_revision: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (Index("ix_ocr_risk_reviews_risk_flag_id", "risk_flag_id"),)


class OCRRiskPageReviewRecord(EvidenceAppendedRecordMixin, Base):
    """用户对某一 OCR 页全部待核对风险的一次性原子核对决议（追加写审计）。

    ``covered_flag_ids`` 是本次原子动作覆盖的 flag 身份集合；``created_review_ids``
    是同一事务内逐条物化的不可变 ``OCRRiskReview``（一一对应）。两者都以 JSON
    镜像列保存并回读时与 canonical payload 交叉核对；缺/多/换绑在回放被拒绝。
    """

    __tablename__ = "ocr_risk_page_reviews"

    page_review_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    ocr_page_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("ocr_pages.ocr_page_id"), nullable=False
    )
    scan_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("ocr_risk_scans.scan_id"), nullable=False
    )
    raw_text_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )
    scanner_rule_version: Mapped[str] = mapped_column(String(128), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    base_processing_revision_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"),
        nullable=False,
    )
    expected_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    covered_flag_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    created_review_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    covered_flag_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )

    __table_args__ = (
        Index("ix_ocr_risk_page_reviews_ocr_page_id", "ocr_page_id"),
        Index("ix_ocr_risk_page_reviews_scan_id", "scan_id"),
    )


class CorrectionRecordRecord(EvidenceAppendedRecordMixin, Base):
    """校对覆盖层记录（追加写，supersede 链）。

    所有校对锚定同一不可变 raw OCR；``supersedes_correction_id`` 显式替代前项。
    关键语义变化（极性/数值/小数点/单位/日期/语义连接词）必须二次确认后才能进入
    完整修订的有效校对集合。
    """

    __tablename__ = "correction_records"

    correction_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    ocr_page_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("ocr_pages.ocr_page_id"), nullable=False
    )
    raw_text_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )
    text_start: Mapped[int] = mapped_column(Integer, nullable=False)
    text_end: Mapped[int] = mapped_column(Integer, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_text: Mapped[str] = mapped_column(Text, nullable=False)
    change_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confirmation_actor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confirmation_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    base_processing_revision_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"),
        nullable=False,
    )
    supersedes_correction_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("correction_records.correction_id"), nullable=True
    )
    affected_scope_json: Mapped[list] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "supersedes_correction_id", name="uq_correction_single_successor"
        ),
        Index(
            "uq_correction_single_root",
            "base_processing_revision_id",
            "ocr_page_id",
            "raw_text_sha256",
            "text_start",
            "text_end",
            unique=True,
            sqlite_where=text("supersedes_correction_id IS NULL"),
        ),
        Index("ix_correction_ocr_page_id", "ocr_page_id"),
        Index("ix_correction_supersedes", "supersedes_correction_id"),
    )


class ReferencedDocumentRevisionRecord(EvidenceAppendedRecordMixin, Base):
    """被提及资料登记修订（追加写，stable logical id + revision 链）。"""

    __tablename__ = "referenced_document_revisions"

    revision_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    referenced_document_id: Mapped[str] = mapped_column(String(128), nullable=False)
    project_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("projects.project_id"), nullable=False
    )
    subject_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("subjects.subject_id"), nullable=False
    )
    review_episode_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_episodes.review_episode_id"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    document_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_party: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trigger_locator_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_locator_artifacts.locator_id"),
        nullable=True,
    )
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    pattern_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_revision_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("referenced_document_revisions.revision_id"),
        nullable=True,
    )
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "referenced_document_id",
            "revision",
            name="uq_refdoc_revision_chain",
        ),
        UniqueConstraint(
            "supersedes_revision_id", name="uq_refdoc_revision_single_successor"
        ),
        Index("ix_refdoc_review_episode_id", "review_episode_id"),
    )


class ReferencedDocumentResolutionRevisionRecord(EvidenceAppendedRecordMixin, Base):
    """被提及资料的不可变满足修订：unresolved 或 provided。"""

    __tablename__ = "referenced_document_resolution_revisions"

    resolution_revision_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    referenced_document_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    source_document_version_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("source_document_versions_v2.source_document_version_id"),
        nullable=True,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_resolution_revision_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey(
            "referenced_document_resolution_revisions.resolution_revision_id"
        ),
        nullable=True,
    )
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "referenced_document_id",
            "revision",
            name="uq_refdoc_resolution_chain",
        ),
        UniqueConstraint(
            "supersedes_resolution_revision_id",
            name="uq_refdoc_resolution_single_successor",
        ),
    )


class EvidenceActivationEventRecord(EvidenceAppendedRecordMixin, Base):
    """审核节点版本切换的追加写激活事件（激活与回滚都用本记录）。"""

    __tablename__ = "evidence_activation_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    review_episode_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_episodes.review_episode_id"), nullable=False
    )
    activation_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    from_snapshot_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_snapshots_v2.evidence_snapshot_id"),
        nullable=True,
    )
    from_revision_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"),
        nullable=True,
    )
    to_snapshot_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_snapshots_v2.evidence_snapshot_id"),
        nullable=False,
    )
    to_revision_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    job_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("jobs.job_id"), nullable=True
    )
    candidate_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_candidates.candidate_id"),
        nullable=True,
    )
    expected_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    resulting_episode_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_status_transitioned: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    command_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "review_episode_id",
            "activation_seq",
            name="uq_activation_event_seq",
        ),
        Index("ix_activation_event_episode", "review_episode_id"),
    )


class EvidenceProcessingCandidateRecord(EvidenceAppendedRecordMixin, Base):
    """证据处理候选：绑定快照、base 修订、预期修订号、Job 与幂等键。

    ``status`` 是最近一次候选事件的投影；``idempotency_key`` 唯一，同键同输入回放、
    同键异输入冲突。
    """

    __tablename__ = "evidence_processing_candidates"

    candidate_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    evidence_snapshot_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_snapshots_v2.evidence_snapshot_id"),
        nullable=False,
    )
    base_processing_revision_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"),
        nullable=False,
    )
    project_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("projects.project_id"), nullable=False
    )
    subject_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("subjects.subject_id"), nullable=False
    )
    review_episode_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_episodes.review_episode_id"), nullable=False
    )
    expected_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("jobs.job_id"), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    candidate_input_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )
    scanner_rule_version: Mapped[str] = mapped_column(String(128), nullable=False)
    selected_locator_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    complete_revision_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_candidate_idempotency_key"),
        UniqueConstraint(
            "complete_revision_id", name="uq_candidate_complete_revision_id"
        ),
        Index("ix_candidate_review_episode_id", "review_episode_id"),
    )


class EvidenceProcessingCandidateEventRecord(EvidenceAppendedRecordMixin, Base):
    """处理候选的一条追加状态事件；最新事件即当前状态。"""

    __tablename__ = "evidence_processing_candidate_events"

    candidate_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_candidates.candidate_id"),
        primary_key=True,
    )
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_status: Mapped[str] = mapped_column(String(32), nullable=False)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    event_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    complete_revision_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"),
        nullable=True,
    )


class _ProcessingRevisionAssocMixin:
    """完整处理修订旁路工件关联公共列：owner + position + ref。"""

    revision_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)


class ProcessingRevisionLocatorRecord(_ProcessingRevisionAssocMixin, Base):
    __tablename__ = "processing_revision_locators"
    locator_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("evidence_locator_artifacts.locator_id"), nullable=False
    )


class ProcessingRevisionRiskScanRecord(_ProcessingRevisionAssocMixin, Base):
    __tablename__ = "processing_revision_risk_scans"
    scan_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("ocr_risk_scans.scan_id"), nullable=False
    )


class ProcessingRevisionRiskReviewRecord(_ProcessingRevisionAssocMixin, Base):
    __tablename__ = "processing_revision_risk_reviews"
    review_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("ocr_risk_reviews.review_id"), nullable=False
    )


class ProcessingRevisionCorrectionRecord(_ProcessingRevisionAssocMixin, Base):
    __tablename__ = "processing_revision_corrections"
    correction_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("correction_records.correction_id"), nullable=False
    )


class ProcessingRevisionMetadataRevisionRecord(_ProcessingRevisionAssocMixin, Base):
    __tablename__ = "processing_revision_metadata_revisions"
    metadata_revision_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey(
            "source_document_metadata_revisions.metadata_revision_id"
        ),
        nullable=False,
    )


class ProcessingRevisionReferencedDocumentRecord(_ProcessingRevisionAssocMixin, Base):
    __tablename__ = "processing_revision_referenced_documents"
    referenced_document_revision_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("referenced_document_revisions.revision_id"),
        nullable=False,
    )


class ProcessingRevisionResolutionRecord(_ProcessingRevisionAssocMixin, Base):
    __tablename__ = "processing_revision_resolutions"
    resolution_revision_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey(
            "referenced_document_resolution_revisions.resolution_revision_id"
        ),
        nullable=False,
    )
