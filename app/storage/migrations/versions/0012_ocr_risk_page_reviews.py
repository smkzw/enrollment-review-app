"""Phase 4 迁移 0012：页级原子风险核对审计表（WP-44B risk page review）。

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-22

背景：逐条风险核对在整页场景不可操作；本迁移新增 ``ocr_risk_page_reviews`` 追加
旁路表，把「对照原件后本页待核对项一次确认」收敛为一次原子动作的审计记录，同时
逐条不可变 ``ocr_risk_reviews`` 仍由该动作在同一事务内逐条物化。表只做追加写，
绝不回写 ``ocr_pages``、``ocr_risk_scans``、``ocr_risk_flags`` 或任何临床事实。

降级（回 0011）只允许「空绿地库」：该表有任一行即视为不可变历史已占用，必须拒绝
有损降级（由管理器从迁移前备份恢复），不得静默丢弃。
"""
from collections.abc import Sequence

from alembic import op
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(referred_table_name)s_%(column_0_N_name)s",
        "pk": "pk_%(table_name)s",
    }
)

# 父表轻量 stub 只用于解析外键，不重建父表。
ocr_pages = Table(
    "ocr_pages", metadata, Column("ocr_page_id", String(128), primary_key=True)
)
ocr_risk_scans = Table(
    "ocr_risk_scans", metadata, Column("scan_id", String(128), primary_key=True)
)
evidence_processing_revisions = Table(
    "evidence_processing_revisions",
    metadata,
    Column(
        "evidence_processing_revision_id", String(128), primary_key=True
    ),
)

ocr_risk_page_reviews = Table(
    "ocr_risk_page_reviews",
    metadata,
    Column("page_review_id", String(128), primary_key=True),
    Column("ocr_page_id", String(128), nullable=False),
    Column("scan_id", String(128), nullable=False),
    Column("raw_text_sha256", String(64), nullable=False),
    Column("scanner_rule_version", String(128), nullable=False),
    Column("decision", String(32), nullable=False),
    Column("reason", Text, nullable=False),
    Column("actor", String(128), nullable=False),
    Column("base_processing_revision_id", String(128), nullable=False),
    Column("expected_revision", Integer, nullable=False),
    Column("covered_flag_ids", JSON, nullable=False),
    Column("created_review_ids", JSON, nullable=False),
    Column("covered_flag_sha256", String(64), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
    ForeignKeyConstraint(["ocr_page_id"], ["ocr_pages.ocr_page_id"]),
    ForeignKeyConstraint(["scan_id"], ["ocr_risk_scans.scan_id"]),
    ForeignKeyConstraint(
        ["base_processing_revision_id"],
        ["evidence_processing_revisions.evidence_processing_revision_id"],
    ),
)
Index(
    "ix_ocr_risk_page_reviews_ocr_page_id",
    ocr_risk_page_reviews.c.ocr_page_id,
)
Index("ix_ocr_risk_page_reviews_scan_id", ocr_risk_page_reviews.c.scan_id)


def upgrade() -> None:
    ocr_risk_page_reviews.create(bind=op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    count = bind.exec_driver_sql(
        "SELECT COUNT(*) FROM ocr_risk_page_reviews"
    ).scalar_one()
    if count:
        raise RuntimeError(
            "ocr_risk_page_reviews 已存在不可变历史，拒绝有损降级"
        )
    op.drop_table("ocr_risk_page_reviews")
