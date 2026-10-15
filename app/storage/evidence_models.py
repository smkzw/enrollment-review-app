"""Phase 4 证据快照与资料版本 ORM（Slice 4.1 冻结）。

与 Phase 2/3 的 ``app/storage/models.py`` 共存但物理隔离：Phase 3 的
``source_document_versions`` / ``evidence_snapshots`` 表保留为只读回归锚点，
Phase 4 的证据底座使用独立表名，绝不改写旧表。迁移 ``0008_evidence_ingestion``
（worker_03）必须以本模块的表名/列/约束为准创建下列表：

- ``source_blobs``                   不可变原始文件身份/存储引用（内容寻址，sha256 唯一）；
- ``source_document_versions_v2``    逻辑资料的一个不可变版本（绑定 blob 与
                                     项目/受试者/审核节点作用域，显式替代链）；
- ``source_document_metadata_revisions``  资料类型/来源方的不可变元数据修订链；
- ``evidence_snapshots_v2``          不可变证据快照（活动成员集合 + 集合哈希，
                                     状态只通过追加的状态事件迁移）；
- ``evidence_snapshot_members``      快照活动成员（逻辑资料 -> 生效版本 + 来源）；
- ``evidence_snapshot_status_events``  候选状态机的追加审计事件。

约定与 ``models.py`` 一致：追加写记录保存 canonical JSON payload + SHA-256，
规范化列用于检索并在读取时与 payload 交叉核对；时间列统一 UTC naive。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base

PAYLOAD_SHA_LEN = 64


class EvidenceAppendedRecordMixin:
    """Phase 4 追加写公共列：canonical JSON payload + 哈希 + 写入时间。"""

    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SourceBlobRecord(EvidenceAppendedRecordMixin, Base):
    """不可变原始文件身份/存储引用：``source_blob_id`` 即内容身份（SHA-256）。

    本 Slice 只冻结内容身份和存储引用，不负责上传或二进制落盘；跨受试者/节点/快照的
    临床 scope 由 ``source_document_versions_v2`` 表达，去重不合并临床作用域。
    """

    __tablename__ = "source_blobs"

    source_blob_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False, unique=True
    )
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_ref: Mapped[str] = mapped_column(String(512), nullable=False)


class SourceDocumentVersionV2Record(EvidenceAppendedRecordMixin, Base):
    """逻辑资料的一个不可变版本（Phase 4，独立于 Phase 3 同名表）。

    ``logical_document_id`` 在同审核节点作用域内稳定；显式替代记录
    ``supersedes_version_id`` 指向同一逻辑资料的前一版本。
    """

    __tablename__ = "source_document_versions_v2"

    source_document_version_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    logical_document_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_blob_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN),
        ForeignKey("source_blobs.sha256"),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    project_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("projects.project_id"), nullable=False
    )
    subject_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("subjects.subject_id"), nullable=False
    )
    review_episode_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_episodes.review_episode_id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_version_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "review_episode_id",
            "logical_document_id",
            "version_number",
            name="uq_sdv2_episode_logical_version",
        ),
        Index("ix_sdv2_review_episode_id", "review_episode_id"),
        Index("ix_sdv2_logical_document_id", "logical_document_id"),
    )


class SourceDocumentMetadataRevisionRecord(EvidenceAppendedRecordMixin, Base):
    """资料类型/来源方的不可变元数据修订链（追加写，永不原地改写）。

    每个修订有唯一 ``metadata_revision_id``；``revision`` 是同一
    ``source_document_version_id`` 链上的递增位置；非初始修订必须引用前序
    修订的唯一 ID。
    """

    __tablename__ = "source_document_metadata_revisions"

    metadata_revision_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_document_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("source_document_versions_v2.source_document_version_id"),
        nullable=False,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    document_type: Mapped[str] = mapped_column(String(128), nullable=False)
    source_party: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    is_auto_suggestion: Mapped[bool] = mapped_column(Boolean, nullable=False)
    supersedes_metadata_revision_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "source_document_version_id",
            "revision",
            name="uq_sdmr_doc_revision",
        ),
        Index("ix_sdmr_source_document_version_id", "source_document_version_id"),
    )


class EvidenceSnapshotV2Record(EvidenceAppendedRecordMixin, Base):
    """不可变证据快照：审核节点当时完整活动文档集合。

    活动成员集合（``evidence_snapshot_members``）与 ``collection_sha256``
    一经写入永不改变；候选生命周期状态通过追加的
    ``evidence_snapshot_status_events`` 迁移，读取时以最新事件为准。
    """

    __tablename__ = "evidence_snapshots_v2"

    evidence_snapshot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("projects.project_id"), nullable=False
    )
    subject_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("subjects.subject_id"), nullable=False
    )
    review_episode_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_episodes.review_episode_id"), nullable=False
    )
    upload_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    prior_snapshot_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_snapshots_v2.evidence_snapshot_id"),
        nullable=True,
    )
    comparison_snapshot_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    collection_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        Index("ix_esnapv2_review_episode_id", "review_episode_id"),
        Index("ix_esnapv2_subject_id", "subject_id"),
    )


class EvidenceSnapshotMemberRecord(EvidenceAppendedRecordMixin, Base):
    """证据快照中的一个活动资料成员（追加写，不可变）。

    同一快照内每个逻辑资料只能有一个活动版本（唯一约束兜底）。
    """

    __tablename__ = "evidence_snapshot_members"

    member_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_snapshots_v2.evidence_snapshot_id"),
        nullable=False,
    )
    logical_document_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_document_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("source_document_versions_v2.source_document_version_id"),
        nullable=False,
    )
    origin: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "logical_document_id",
            name="uq_esm_snapshot_logical",
        ),
        Index("ix_esm_snapshot_id", "snapshot_id"),
    )


class EvidenceSnapshotStatusEventRecord(EvidenceAppendedRecordMixin, Base):
    """候选快照状态机的追加审计事件；最新事件即当前状态。"""

    __tablename__ = "evidence_snapshot_status_events"

    snapshot_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_snapshots_v2.evidence_snapshot_id"),
        primary_key=True,
    )
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_status: Mapped[str] = mapped_column(String(32), nullable=False)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_esse_snapshot_id", "snapshot_id"),
    )
