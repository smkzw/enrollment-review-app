"""方案文档提取（Phase 3 切片 1）：来源、渲染、快照、来源片段与冻结目录表

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-14

本文件的 Table 定义由 ORM metadata 生成后冻结；表结构变更必须新增迁移，
不得修改本文件。约束命名遵循与 app.storage.db 相同的 naming convention。
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(referred_table_name)s_%(column_0_N_name)s",
        "pk": "pk_%(table_name)s",
    }
)

protocol_source_artifacts = Table(
    "protocol_source_artifacts",
    metadata,
    Column("source_artifact_id", String(128), primary_key=True),
    Column("sha256", String(64), nullable=False),
    Column("mime_type", String(128), nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("storage_ref", String(512), nullable=False),
    Column("uploaded_at", DateTime, nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("sha256"),
)

protocol_render_artifacts = Table(
    "protocol_render_artifacts",
    metadata,
    Column("render_artifact_id", String(128), primary_key=True),
    Column(
        "source_artifact_id",
        String(128),
        ForeignKey("protocol_source_artifacts.source_artifact_id"),
        nullable=False,
    ),
    Column("source_sha256", String(64), nullable=False),
    Column("renderer", String(64), nullable=False),
    Column("renderer_version", String(64), nullable=False),
    Column("pdf_sha256", String(64), nullable=True),
    Column("page_count", Integer, nullable=True),
    Column("status", String(32), nullable=False),
    Column("storage_ref", String(512), nullable=True),
    Column("render_error", Text, nullable=True),
    Column("payload_json", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
)

protocol_extraction_snapshots = Table(
    "protocol_extraction_snapshots",
    metadata,
    Column("snapshot_id", String(128), primary_key=True),
    Column(
        "source_artifact_id",
        String(128),
        ForeignKey("protocol_source_artifacts.source_artifact_id"),
        nullable=False,
    ),
    Column("source_sha256", String(64), nullable=False),
    Column("parser_name", String(64), nullable=False),
    Column("parser_version", String(64), nullable=False),
    Column("status", String(32), nullable=False),
    Column("content_sha256", String(64), nullable=False),
    Column("content_storage_ref", String(512), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
)

protocol_source_spans = Table(
    "protocol_source_spans",
    metadata,
    Column("source_span_id", String(128), primary_key=True),
    Column(
        "snapshot_id",
        String(128),
        ForeignKey("protocol_extraction_snapshots.snapshot_id"),
        nullable=False,
    ),
    Column("source_ref", String(256), nullable=False),
    Column("document_part", String(32), nullable=False),
    Column("precision", String(32), nullable=False),
    Column("alignment_status", String(32), nullable=False),
    Column(
        "render_artifact_id",
        String(128),
        ForeignKey("protocol_render_artifacts.render_artifact_id"),
        nullable=True,
    ),
    Column("render_page", Integer, nullable=True),
    Column("table_path", JSON, nullable=True),
    Column("payload_json", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("snapshot_id", "source_ref"),
)

frozen_protocol_catalogs = Table(
    "frozen_protocol_catalogs",
    metadata,
    Column("catalog_id", String(128), primary_key=True),
    Column(
        "snapshot_id",
        String(128),
        ForeignKey("protocol_extraction_snapshots.snapshot_id"),
        nullable=False,
    ),
    Column("catalog_kind", String(32), nullable=False),
    Column("study_phase", String(32), nullable=False),
    Column("frozen_at", DateTime, nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("snapshot_id", "catalog_kind", "study_phase"),
)

TABLES = [
    protocol_source_artifacts,
    protocol_render_artifacts,
    protocol_extraction_snapshots,
    protocol_source_spans,
    frozen_protocol_catalogs,
]

Index(
    "ix_protocol_render_artifacts_source_artifact_id",
    protocol_render_artifacts.c.source_artifact_id,
)
Index(
    "ix_protocol_extraction_snapshots_source_artifact_id",
    protocol_extraction_snapshots.c.source_artifact_id,
)
Index("ix_protocol_source_spans_source_ref", protocol_source_spans.c.source_ref)
Index("ix_frozen_protocol_catalogs_snapshot_id", frozen_protocol_catalogs.c.snapshot_id)


def upgrade() -> None:
    """创建方案提取层五张追加写表；索引附着在 Table 上随表创建。"""
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind)


def downgrade() -> None:
    """反向删除五张表；SQLite DROP TABLE 会连带删除其索引。"""
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind)
