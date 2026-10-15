"""Phase 5 选择性视觉观察侧车 ORM（追加写旁路）。

表名/列/约束以本模块为准；迁移 ``0019_selective_vision_observations`` 必须据此建表。
本表只保存观察性视觉核验结果，外键锚定已落盘 ``page_artifacts``（及可选
``ocr_pages``），绝不改写 OCR 原文、缓存或租约。
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base
from app.storage.evidence_models import PAYLOAD_SHA_LEN, EvidenceAppendedRecordMixin

__all__ = ["SelectiveVisionObservationORM"]


class SelectiveVisionObservationORM(EvidenceAppendedRecordMixin, Base):
    """不可变视觉观察侧车行。

    成功行在 ``observation_identity_sha256`` 上部分唯一；失败关闭行可追加多条，
    且 ``observation_text`` 必须为空。
    """

    __tablename__ = "selective_vision_observations"

    observation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    page_artifact_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("page_artifacts.page_artifact_id"),
        nullable=False,
    )
    source_document_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("source_document_versions_v2.source_document_version_id"),
        nullable=False,
    )
    source_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    page_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    page_image_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )
    ocr_page_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("ocr_pages.ocr_page_id"),
        nullable=True,
    )
    ocr_raw_text_sha256: Mapped[str | None] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=True
    )
    plan_version: Mapped[str] = mapped_column(String(128), nullable=False)
    risk_reasons_json: Mapped[list] = mapped_column(JSON, nullable=False)
    risk_reasons_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    observation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    finish_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    usage_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    failure_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    observation_identity_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('succeeded', 'closed')",
            name="ck_svo_status",
        ),
        CheckConstraint(
            "page_ordinal >= 1",
            name="ck_svo_page_ordinal",
        ),
        CheckConstraint(
            "(status = 'succeeded' AND observation_text IS NOT NULL "
            "AND failure_kind IS NULL) OR "
            "(status = 'closed' AND observation_text IS NULL "
            "AND failure_kind IS NOT NULL)",
            name="ck_svo_status_payload",
        ),
        CheckConstraint(
            "(ocr_page_id IS NULL AND ocr_raw_text_sha256 IS NULL) OR "
            "(ocr_page_id IS NOT NULL AND ocr_raw_text_sha256 IS NOT NULL)",
            name="ck_svo_ocr_pair",
        ),
        # 同一成功身份最多一条；失败关闭可多条共存。
        Index(
            "uq_svo_identity_succeeded",
            "observation_identity_sha256",
            unique=True,
            sqlite_where=text("status = 'succeeded'"),
        ),
        Index("ix_svo_page_artifact_id", "page_artifact_id"),
        Index("ix_svo_ocr_page_id", "ocr_page_id"),
        Index("ix_svo_source_document_version_id", "source_document_version_id"),
        Index(
            "ix_svo_page_image_plan_model",
            "page_artifact_id",
            "page_image_sha256",
            "plan_version",
            "model_id",
        ),
    )
