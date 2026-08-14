"""方案元信息、期别适用图与解释材料（Phase 3 切片 2）。

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-14

本文件的 Table 定义与 ``app.storage.models`` 中的追加写记录保持一致。
切片 1 的迁移已经冻结；后续结构变化必须继续新增迁移，不得回写 0001-0004。
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import (
    Boolean,
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

revision: str = "0005"
down_revision: Union[str, None] = "0004"
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


def _append_columns(*columns: Column) -> tuple[Column, ...]:
    """Add the canonical JSON/hash/timestamp columns to every append table."""

    return (
        *columns,
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
    )


# The prior migration owns these tables.  Lightweight metadata stubs let
# SQLAlchemy resolve the foreign keys while keeping 0004 frozen and avoiding
# any attempt to recreate the parent tables.
protocol_extraction_snapshots = Table(
    "protocol_extraction_snapshots",
    metadata,
    Column("snapshot_id", String(128), primary_key=True),
)
protocol_document_versions = Table(
    "protocol_document_versions",
    metadata,
    Column("protocol_version_id", String(128), primary_key=True),
)


protocol_metadata_candidates = Table(
    "protocol_metadata_candidates",
    metadata,
    *_append_columns(
        Column("candidate_id", String(128), primary_key=True),
        Column(
            "snapshot_id",
            String(128),
            ForeignKey("protocol_extraction_snapshots.snapshot_id"),
            nullable=False,
        ),
        Column("field_category", String(32), nullable=False),
        Column("normalized_value", String(512), nullable=False),
        Column("source_ref", String(256), nullable=False),
        Column("source_kind", String(32), nullable=False),
        Column("identity_authority", String(16), nullable=False),
        Column("priority_rank", Integer, nullable=False),
        Column("conflict_group_id", String(128), nullable=True),
    ),
)

protocol_metadata_conflicts = Table(
    "protocol_metadata_conflicts",
    metadata,
    *_append_columns(
        Column("conflict_id", String(128), primary_key=True),
        Column(
            "snapshot_id",
            String(128),
            ForeignKey("protocol_extraction_snapshots.snapshot_id"),
            nullable=False,
        ),
        Column("field_category", String(32), nullable=False),
        Column("status", String(32), nullable=False),
        Column("selected_candidate_id", String(128), nullable=True),
    ),
    UniqueConstraint("snapshot_id", "field_category", "status"),
)

protocol_identity_decisions = Table(
    "protocol_identity_decisions",
    metadata,
    *_append_columns(
        Column("identity_decision_id", String(128), primary_key=True),
        Column(
            "snapshot_id",
            String(128),
            ForeignKey("protocol_extraction_snapshots.snapshot_id"),
            nullable=False,
        ),
        Column("status", String(32), nullable=False),
        Column("project_name", String(256), nullable=True),
        Column("project_code", String(256), nullable=True),
        Column("protocol_code", String(256), nullable=True),
        Column("official_version", String(128), nullable=True),
        Column("official_date_value", DateTime, nullable=True),
        Column("official_date_precision", String(16), nullable=True),
        Column("study_phase", String(32), nullable=True),
        Column("confirmed_at", DateTime, nullable=True),
    ),
)

study_phase_candidates = Table(
    "study_phase_candidates",
    metadata,
    *_append_columns(
        Column("candidate_id", String(128), primary_key=True),
        Column(
            "snapshot_id",
            String(128),
            ForeignKey("protocol_extraction_snapshots.snapshot_id"),
            nullable=False,
        ),
        Column("design_type", String(32), nullable=False),
        Column("source_ref", String(256), nullable=False),
        Column("priority_rank", Integer, nullable=False),
    ),
)

study_phase_selections = Table(
    "study_phase_selections",
    metadata,
    *_append_columns(
        Column("selection_id", String(128), primary_key=True),
        Column(
            "snapshot_id",
            String(128),
            ForeignKey("protocol_extraction_snapshots.snapshot_id"),
            nullable=False,
        ),
        Column("selected_phase", String(32), nullable=False),
        Column("status", String(32), nullable=False),
        Column("confirmed_at", DateTime, nullable=True),
    ),
)

protocol_phase_applicability_graphs = Table(
    "protocol_phase_applicability_graphs",
    metadata,
    *_append_columns(
        Column("graph_id", String(128), primary_key=True),
        Column(
            "snapshot_id",
            String(128),
            ForeignKey("protocol_extraction_snapshots.snapshot_id"),
            nullable=False,
        ),
        Column("default_design_type", String(32), nullable=False),
    ),
    UniqueConstraint("snapshot_id"),
)

protocol_phase_projections = Table(
    "protocol_phase_projections",
    metadata,
    *_append_columns(
        Column("projection_id", String(128), primary_key=True),
        Column(
            "graph_id",
            String(128),
            ForeignKey("protocol_phase_applicability_graphs.graph_id"),
            nullable=False,
        ),
        Column("selected_phase", String(32), nullable=False),
    ),
    UniqueConstraint("graph_id", "selected_phase"),
)

interpretation_sources = Table(
    "interpretation_sources",
    metadata,
    *_append_columns(
        Column("interpretation_source_id", String(128), primary_key=True),
        Column(
            "protocol_version_id",
            String(128),
            ForeignKey("protocol_document_versions.protocol_version_id"),
            nullable=False,
        ),
        Column("source_type", String(32), nullable=False),
        Column("file_sha256", String(64), nullable=False),
        Column("authority", String(32), nullable=False),
        Column("source_ref", String(256), nullable=False),
        Column("is_current_amendment", Boolean, nullable=False),
    ),
)

interpretation_conflicts = Table(
    "interpretation_conflicts",
    metadata,
    *_append_columns(
        Column("conflict_id", String(128), primary_key=True),
        Column(
            "protocol_version_id",
            String(128),
            ForeignKey("protocol_document_versions.protocol_version_id"),
            nullable=False,
        ),
        Column(
            "interpretation_source_id",
            String(128),
            ForeignKey("interpretation_sources.interpretation_source_id"),
            nullable=False,
        ),
        Column("status", String(48), nullable=False),
        Column("blocks_publication", Boolean, nullable=False),
    ),
)

TABLES = [
    protocol_metadata_candidates,
    protocol_metadata_conflicts,
    protocol_identity_decisions,
    study_phase_candidates,
    study_phase_selections,
    protocol_phase_applicability_graphs,
    protocol_phase_projections,
    interpretation_sources,
    interpretation_conflicts,
]

Index(
    "ix_protocol_metadata_candidates_snapshot_id",
    protocol_metadata_candidates.c.snapshot_id,
)
Index(
    "ix_protocol_metadata_candidates_field_category",
    protocol_metadata_candidates.c.field_category,
)
Index(
    "ix_protocol_metadata_conflicts_snapshot_id",
    protocol_metadata_conflicts.c.snapshot_id,
)
Index(
    "ix_protocol_identity_decisions_snapshot_id",
    protocol_identity_decisions.c.snapshot_id,
)
Index("ix_study_phase_candidates_snapshot_id", study_phase_candidates.c.snapshot_id)
Index("ix_study_phase_selections_snapshot_id", study_phase_selections.c.snapshot_id)
Index("ix_protocol_phase_projections_graph_id", protocol_phase_projections.c.graph_id)
Index(
    "ix_interpretation_sources_protocol_version_id",
    interpretation_sources.c.protocol_version_id,
)
Index(
    "ix_interpretation_conflicts_protocol_version_id",
    interpretation_conflicts.c.protocol_version_id,
)
Index(
    "ix_interpretation_conflicts_source_id",
    interpretation_conflicts.c.interpretation_source_id,
)


def upgrade() -> None:
    """创建 slice 2 的九张追加写表。"""

    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind)


def downgrade() -> None:
    """按依赖相反顺序删除 slice 2 表。"""

    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind)
