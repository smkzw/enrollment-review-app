"""Phase 4 OCR 持久化与基础证据处理修订 ORM（Slice 4.3）。

与 Phase 2/3 的 ``app/storage/models.py`` 及 Phase 4 证据表共存但物理隔离；
迁移 ``0009_ocr_artifacts``（追加在已验收的 ``0008a_evidence_upload_previews``
之后）必须以本模块的表名/列/约束为准创建下列表：

- ``ocr_profiles``                      识别配置稳定指纹（profile_sha256 唯一）；
- ``page_artifacts``                    不可变页产物（页图/原生文本/坐标/派生物哈希，
                                       页级内容去重 (资料版本, 页码, 页图输入哈希)）；
- ``raw_ocr_request_artifacts``         不可变原始 OCR 请求工件（内容寻址，sha256 唯一）；
- ``raw_ocr_response_artifacts``        不可变原始 OCR 响应工件（provider 原文不删改）；
- ``ocr_pages``                         页级识别结果（追加写不可变行；同一缓存键
                                       最多一条成功结果，部分唯一索引强制）；
- ``ocr_runs``                          文件级 OCR 运行：Profile、任务、状态与汇总；
- ``ocr_attempts``                      每次真实请求的追加写尝试（含被拒绝的晚到尝试，
                                       (cache_key, attempt_number) 唯一）；
- ``evidence_processing_revisions``     不可变基础证据处理修订（绑定快照、有序页清单
                                       哈希，明确不可激活，不触碰活动指针）；
- ``evidence_processing_revision_pages`` 修订页清单条目（逐页冻结 PageArtifact/OCRPage
                                       身份，(revision_id, position) 主键）；
- ``page_work_leases``                  页工作租约（owner/过期/单调递增代次，只防重复执行，
                                       不是并发额度）。

约定与 ``evidence_models.py`` 一致：追加写记录保存 canonical JSON payload +
SHA-256，规范化列用于检索并在读取时与 payload 交叉核对；时间列统一 UTC naive。
``page_work_leases`` 是可变的协调结构（同 JobRecord），不保存 payload。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
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


class OCRProfileRecord(EvidenceAppendedRecordMixin, Base):
    """识别配置稳定指纹；任一识别决定性输入变化必然产生新指纹。"""

    __tablename__ = "ocr_profiles"

    ocr_profile_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    profile_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False, unique=True
    )
    extraction_route: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    model_revision: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_sha256: Mapped[str | None] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=True)
    parser_version: Mapped[str] = mapped_column(String(128), nullable=False)
    render_params_sha256: Mapped[str | None] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=True
    )
    request_params_sha256: Mapped[str | None] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=True
    )
    layout_parser_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    coordinate_transform_version: Mapped[str] = mapped_column(String(128), nullable=False)


class PageArtifactRecord(EvidenceAppendedRecordMixin, Base):
    """不可变页产物：页图、原生文本/坐标与派生信息的身份与哈希。

    成功/降级页必须携带真实页输入哈希、页宽/页高、旋转与页图哈希；失败页（整
    文件无法分页或该页无法解码）没有这些真实值，列允许 NULL，不得用伪值填充。
    失败页身份由 worker_02 的确定性 ID 负责（SQLite 对 nullable 唯一键不阻止
    多个 NULL 记录），仓储仍拒绝同 ID 不同内容。``page_input_sha256`` 是渲染/
    解码输入的稳定身份；``OCRPage.page_input_sha256`` 是实际送入 OCR 的页图字节
    哈希，二者语义不同。
    """

    __tablename__ = "page_artifacts"

    page_artifact_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_document_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("source_document_versions_v2.source_document_version_id"),
        nullable=False,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_frame: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    page_input_sha256: Mapped[str | None] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=True
    )
    page_image_sha256: Mapped[str | None] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=True
    )
    native_text_sha256: Mapped[str | None] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=True
    )
    native_coordinates_sha256: Mapped[str | None] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=True
    )
    page_width: Mapped[float | None] = mapped_column(Float, nullable=True)
    page_height: Mapped[float | None] = mapped_column(Float, nullable=True)
    rotation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    renderer_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decoder_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    derivative_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    coordinate_transform_version: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "source_document_version_id",
            "page_number",
            "page_input_sha256",
            "renderer_version",
            "decoder_version",
            "coordinate_transform_version",
            name="uq_page_artifacts_doc_page_input_config",
        ),
        Index(
            "ix_page_artifacts_source_document",
            "source_document_version_id",
            "page_number",
        ),
    )


class RawOcrRequestArtifactRecord(EvidenceAppendedRecordMixin, Base):
    """不可变原始 OCR 请求工件引用（内容寻址，sha256 唯一）。"""

    __tablename__ = "raw_ocr_request_artifacts"

    raw_request_artifact_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False, unique=True
    )
    storage_ref: Mapped[str] = mapped_column(String(512), nullable=False)


class RawOcrResponseArtifactRecord(EvidenceAppendedRecordMixin, Base):
    """不可变原始 OCR 响应工件引用；provider 原文不删改，任何清洗都是派生步骤。"""

    __tablename__ = "raw_ocr_response_artifacts"

    raw_response_artifact_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False, unique=True
    )
    storage_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    model_revision: Mapped[str] = mapped_column(String(128), nullable=False)


class OCRPageRecord(EvidenceAppendedRecordMixin, Base):
    """页级识别结果（追加写不可变行，缓存键不唯一）。

    每次结果（待处理/处理中/失败/取消/成功）都是一条独立不可变行，永不原地
    改写历史尝试；不可变原始请求/响应、页图与原生文本分别由内容寻址工件表保存，
    尝试历史由 ``ocr_attempts`` 追加记录。同一缓存键最多允许一条 SUCCEEDED 行
    （部分唯一索引 ``uq_ocr_pages_cache_key_succeeded`` 在存储层强制），
    晚到/失败/取消结果可多条共存；成功缓存命中只返回那条不可变成功行。
    """

    __tablename__ = "ocr_pages"

    ocr_page_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    page_artifact_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("page_artifacts.page_artifact_id"), nullable=False
    )
    source_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    page_input_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    ocr_profile_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("ocr_profiles.ocr_profile_id"), nullable=False
    )
    ocr_profile_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    cache_key: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    layout_parser_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    coordinate_transform_version: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    layout_sidecar_sha256: Mapped[str | None] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=True
    )
    quality_json: Mapped[str] = mapped_column(Text, nullable=False)
    risk_items_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        # 同一缓存键最多一条成功结果；失败/取消/处理中可多条共存。
        Index(
            "uq_ocr_pages_cache_key_succeeded",
            "cache_key",
            unique=True,
            sqlite_where=text("status = 'succeeded'"),
        ),
        Index("ix_ocr_pages_cache_key", "cache_key"),
        Index("ix_ocr_pages_page_artifact_id", "page_artifact_id"),
        Index("ix_ocr_pages_ocr_profile_id", "ocr_profile_id"),
    )


class OCRRunRecord(EvidenceAppendedRecordMixin, Base):
    """文件级 OCR 运行：Profile、任务、状态与页级汇总。"""

    __tablename__ = "ocr_runs"

    ocr_run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_document_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("source_document_versions_v2.source_document_version_id"),
        nullable=False,
    )
    ocr_profile_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("ocr_profiles.ocr_profile_id"), nullable=False
    )
    ocr_profile_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    job_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("jobs.job_id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    page_total: Mapped[int] = mapped_column(Integer, nullable=False)
    page_succeeded: Mapped[int] = mapped_column(Integer, nullable=False)
    page_failed: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_ocr_runs_source_document_version_id", "source_document_version_id"),
        Index("ix_ocr_runs_job_id", "job_id"),
    )


class OCRAttemptRecord(EvidenceAppendedRecordMixin, Base):
    """每次真实 OCR 请求的追加写尝试（含被拒绝的晚到尝试）。

    ``cache_key`` 即页工作项身份（页级缓存唯一键）；``attempt_number`` 在同一
    cache_key 上 1 起递增，追加写永不覆盖历史尝试。晚到尝试以
    ``rejected_late`` 状态保留审计。
    """

    __tablename__ = "ocr_attempts"

    attempt_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    ocr_run_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("ocr_runs.ocr_run_id"), nullable=False
    )
    ocr_page_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("ocr_pages.ocr_page_id"), nullable=True
    )
    cache_key: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    failure_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw_request_artifact_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("raw_ocr_request_artifacts.raw_request_artifact_id"),
        nullable=True,
    )
    raw_response_artifact_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("raw_ocr_response_artifacts.raw_response_artifact_id"),
        nullable=True,
    )
    work_lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    work_lease_generation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    omlx_lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    retry_of_attempt_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("ocr_attempts.attempt_id"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "cache_key",
            "attempt_number",
            name="uq_ocr_attempts_cache_attempt",
        ),
        Index("ix_ocr_attempts_cache_key", "cache_key"),
        Index("ix_ocr_attempts_ocr_page_id", "ocr_page_id"),
    )


class EvidenceProcessingRevisionRecord(EvidenceAppendedRecordMixin, Base):
    """不可变基础证据处理修订：绑定快照、有序页清单哈希，明确不可激活。

    修订写入后不可原地改写；``is_activatable`` 恒为 False，仓储不提供任何激活
    或活动指针更新能力（Slice 4.3 只冻结非激活基础修订）。
    """

    __tablename__ = "evidence_processing_revisions"

    evidence_processing_revision_id: Mapped[str] = mapped_column(
        String(128), primary_key=True
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
    manifest_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    is_activatable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Slice 4.4 base/complete 辨别：0009 迁移前的 4.3 行投影为 'base'；
    # 完整修订是新 root row（revision_kind='complete'），通过 base_processing_revision_id
    # 冻结同一快照的 base 页清单，completion_manifest_sha256 冻结全部 4.4 关联闭包。
    revision_kind: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="base"
    )
    base_processing_revision_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey(
            "evidence_processing_revisions.evidence_processing_revision_id",
            name="fk_epr_base_processing_revision_self",
        ),
        nullable=True,
    )
    producer_candidate_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    candidate_input_sha256: Mapped[str | None] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=True
    )
    completion_manifest_sha256: Mapped[str | None] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        Index("ix_epr_evidence_snapshot_id", "evidence_snapshot_id"),
        Index("ix_epr_review_episode_id", "review_episode_id"),
        Index("ix_epr_revision_kind", "revision_kind"),
        CheckConstraint(
            "revision_kind IN ('base', 'complete')",
            name="ck_epr_revision_kind",
        ),
        CheckConstraint(
            "(revision_kind = 'base' AND is_activatable = 0 "
            "AND base_processing_revision_id IS NULL "
            "AND producer_candidate_id IS NULL "
            "AND candidate_input_sha256 IS NULL "
            "AND completion_manifest_sha256 IS NULL) OR "
            "(revision_kind = 'complete' AND is_activatable = 1 "
            "AND base_processing_revision_id IS NOT NULL "
            "AND producer_candidate_id IS NOT NULL "
            "AND candidate_input_sha256 IS NOT NULL "
            "AND completion_manifest_sha256 IS NOT NULL)",
            name="ck_epr_kind_shape",
        ),
        UniqueConstraint(
            "producer_candidate_id", name="uq_epr_producer_candidate"
        ),
    )


class EvidenceProcessingRevisionPageRecord(EvidenceAppendedRecordMixin, Base):
    """基础证据处理修订的有序页清单条目（追加写，不可变）。

    逐页冻结 PageArtifact/OCRPage 身份；``(revision_id, position)`` 为主键，
    同一修订内不允许重复 ``(revision_id, source_document_version_id, page_number)``。
    """

    __tablename__ = "evidence_processing_revision_pages"

    revision_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_document_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("source_document_versions_v2.source_document_version_id"),
        nullable=False,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_frame: Mapped[str | None] = mapped_column(String(128), nullable=True)
    page_artifact_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("page_artifacts.page_artifact_id"), nullable=False
    )
    ocr_page_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("ocr_pages.ocr_page_id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "revision_id",
            "source_document_version_id",
            "page_number",
            name="uq_eprp_revision_doc_page",
        ),
        Index("ix_eprp_page_artifact_id", "page_artifact_id"),
    )


class PageWorkLeaseRecord(Base):
    """页工作租约（持久协调结构，同 JobRecord 可变，不保存 payload）。

    ``work_item_id`` 即页级缓存唯一键（内容寻址）；``lease_generation`` 每次
    成功领取单调 +1；续租/释放/结果提交都核对 owner、代次与过期。该租约只防止
    同一页被重复 worker 执行，不参与全局真实推理并发额度。
    """

    __tablename__ = "page_work_leases"

    work_item_id: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), primary_key=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lease_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
