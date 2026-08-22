"""Phase 4 上传预览/条目/确认 ORM（Slice 4.2）。

与 Phase 2/3 的 ``app/storage/models.py`` 共存但物理隔离；迁移
``0008a_evidence_upload_previews``（追加在已验收的 ``0008_evidence_ingestion``
之后，保持后续 ``0009_ocr_artifacts`` 职责不变）必须以本模块的表名/列/约束为准
创建下列表：

- ``evidence_upload_previews``  短期候选预览：作用域、上传方式、基准快照、
                                创建时修订号、状态与确定性摘要；
- ``evidence_upload_items``     逐文件指纹/格式/大小/分类/处理建议/冲突，
                                文件名不是内容身份；暂存引用指向预览自有目录；
- ``evidence_upload_commits``   确认动作：预览摘要哈希、幂等键、产生的候选快照
                                与重复集合 no-op 标志。

约定与 ``evidence_models.py`` 一致：追加写记录保存 canonical JSON payload +
SHA-256，规范化列用于检索并在读取时与 payload 交叉核对；时间列统一 UTC naive。
预览不是临床快照：取消只清理预览自有暂存，不触碰共享 blob 或历史。
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base
from app.storage.evidence_models import PAYLOAD_SHA_LEN, EvidenceAppendedRecordMixin


class EvidenceUploadPreviewRecord(EvidenceAppendedRecordMixin, Base):
    """上传预览：绑定作用域、上传方式、基准快照、创建时修订号与状态。

    状态为 staged/committed/cancel_pending/cancelled（``UploadPreviewStatus``）；
    取消走 staged -> cancel_pending -> cancelled，``cancel_pending`` 表示取消意图
    已追加但暂存清理尚未验证完成（可重试）。预览不是临床快照，取消/确认都不改写
    既有快照或历史。
    """

    __tablename__ = "evidence_upload_previews"

    preview_id: Mapped[str] = mapped_column(String(128), primary_key=True)
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
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    base_snapshot_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_snapshots_v2.evidence_snapshot_id"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    preview_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        Index("ix_eup_review_episode_id", "review_episode_id"),
        Index("ix_eup_subject_id", "subject_id"),
    )


class EvidenceUploadItemRecord(EvidenceAppendedRecordMixin, Base):
    """逐文件指纹/格式/大小/分类/处理建议/重复关系/冲突（预览条目）。"""

    __tablename__ = "evidence_upload_items"

    item_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    preview_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_upload_previews.preview_id"),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    processing_hint: Mapped[str] = mapped_column(String(32), nullable=False)
    logical_document_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    existing_version_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_eui_preview_id", "preview_id"),
    )


class EvidenceUploadCommitRecord(EvidenceAppendedRecordMixin, Base):
    """确认动作：预览摘要哈希、幂等键、产生的候选快照与重复 no-op 标志。"""

    __tablename__ = "evidence_upload_commits"

    commit_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    preview_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_upload_previews.preview_id"),
        nullable=False,
    )
    evidence_snapshot_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_snapshots_v2.evidence_snapshot_id"),
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
    upload_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    preview_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(512), nullable=False)
    job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        Index("ix_euc_preview_id", "preview_id"),
        Index("ix_euc_evidence_snapshot_id", "evidence_snapshot_id"),
    )
