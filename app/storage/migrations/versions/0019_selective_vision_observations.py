"""Phase 5：选择性视觉观察侧车（追加写旁路）。

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-31

``selective_vision_observations`` 保存页产物之上的不可变视觉观察或显式失败关闭
记录。成功身份（``observation_identity_sha256``）部分唯一；失败关闭可追加多条且
不得含模型伪输出。含正式数据时拒绝有损降级。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PAYLOAD_SHA_LEN = 64


def upgrade() -> None:
    op.create_table(
        "selective_vision_observations",
        sa.Column("observation_id", sa.String(length=128), nullable=False),
        sa.Column("page_artifact_id", sa.String(length=128), nullable=False),
        sa.Column("source_document_version_id", sa.String(length=128), nullable=False),
        sa.Column("source_ref", sa.String(length=512), nullable=False),
        sa.Column("page_ordinal", sa.Integer(), nullable=False),
        sa.Column("page_image_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("ocr_page_id", sa.String(length=128), nullable=True),
        sa.Column("ocr_raw_text_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=True),
        sa.Column("plan_version", sa.String(length=128), nullable=False),
        sa.Column("risk_reasons_json", sa.JSON(), nullable=False),
        sa.Column("risk_reasons_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=128), nullable=False),
        sa.Column("prompt_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("observation_text", sa.Text(), nullable=True),
        sa.Column("finish_reason", sa.String(length=128), nullable=True),
        sa.Column("usage_json", sa.JSON(), nullable=False),
        sa.Column("failure_kind", sa.String(length=64), nullable=True),
        sa.Column(
            "observation_identity_sha256",
            sa.String(length=_PAYLOAD_SHA_LEN),
            nullable=False,
        ),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('succeeded', 'closed')",
            name="ck_svo_status",
        ),
        sa.CheckConstraint(
            "page_ordinal >= 1",
            name="ck_svo_page_ordinal",
        ),
        sa.CheckConstraint(
            "(status = 'succeeded' AND observation_text IS NOT NULL "
            "AND failure_kind IS NULL) OR "
            "(status = 'closed' AND observation_text IS NULL "
            "AND failure_kind IS NOT NULL)",
            name="ck_svo_status_payload",
        ),
        sa.CheckConstraint(
            "(ocr_page_id IS NULL AND ocr_raw_text_sha256 IS NULL) OR "
            "(ocr_page_id IS NOT NULL AND ocr_raw_text_sha256 IS NOT NULL)",
            name="ck_svo_ocr_pair",
        ),
        sa.ForeignKeyConstraint(
            ["page_artifact_id"],
            ["page_artifacts.page_artifact_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_document_version_id"],
            ["source_document_versions_v2.source_document_version_id"],
        ),
        sa.ForeignKeyConstraint(
            ["ocr_page_id"],
            ["ocr_pages.ocr_page_id"],
        ),
        sa.PrimaryKeyConstraint("observation_id", name="pk_selective_vision_observations"),
    )
    op.create_index(
        "uq_svo_identity_succeeded",
        "selective_vision_observations",
        ["observation_identity_sha256"],
        unique=True,
        sqlite_where=sa.text("status = 'succeeded'"),
    )
    op.create_index(
        "ix_svo_page_artifact_id",
        "selective_vision_observations",
        ["page_artifact_id"],
        unique=False,
    )
    op.create_index(
        "ix_svo_ocr_page_id",
        "selective_vision_observations",
        ["ocr_page_id"],
        unique=False,
    )
    op.create_index(
        "ix_svo_source_document_version_id",
        "selective_vision_observations",
        ["source_document_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_svo_page_image_plan_model",
        "selective_vision_observations",
        ["page_artifact_id", "page_image_sha256", "plan_version", "model_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    count = bind.exec_driver_sql(
        "SELECT COUNT(*) FROM selective_vision_observations"
    ).scalar_one()
    if count:
        raise RuntimeError(
            "0019 selective_vision_observations 已有不可变历史，拒绝有损降级"
        )
    op.drop_index(
        "ix_svo_page_image_plan_model",
        table_name="selective_vision_observations",
    )
    op.drop_index(
        "ix_svo_source_document_version_id",
        table_name="selective_vision_observations",
    )
    op.drop_index("ix_svo_ocr_page_id", table_name="selective_vision_observations")
    op.drop_index("ix_svo_page_artifact_id", table_name="selective_vision_observations")
    op.drop_index(
        "uq_svo_identity_succeeded",
        table_name="selective_vision_observations",
    )
    op.drop_table("selective_vision_observations")
