"""Phase 4 证据快照与资料版本（Slice 4.1）：证据摄入表

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-19

本迁移只新增 Phase 4 证据底座表，不回写 0001-0007 既有表；旧项目数据只读。
表名/列/约束以 ``app/storage/evidence_models.py``（worker_02）为权威，由
``verify_schema_matches_metadata`` 在迁移后逐表交叉核对。降级按依赖逆序删除。

新增表：

- ``source_blobs``                    不可变原始文件身份/存储引用（内容寻址，sha256 唯一）；
- ``source_document_versions_v2``     逻辑资料的一个不可变版本（作用域 + 显式替代链）；
- ``source_document_metadata_revisions``  资料类型/来源方的不可变元数据修订链；
- ``evidence_snapshots_v2``           不可变证据快照（活动成员集合 + 集合哈希，
                                      自引用前序快照）；
- ``evidence_snapshot_members``       快照活动成员（逻辑资料 -> 生效版本 + 来源）；
- ``evidence_snapshot_status_events`` 候选状态机的追加审计事件（最新事件即当前状态）。

注意：``source_document_versions_v2.supersedes_version_id`` 与
``evidence_snapshots_v2.comparison_snapshot_id`` 有意不建外键（替代/比较链由
仓储与领域合同校验，避免 SQLite 自引用排序问题）；其余外键均建，迁移后用
``PRAGMA foreign_key_check`` 验证。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PAYLOAD_SHA_LEN = 64


def upgrade() -> None:
    op.create_table(
        "source_blobs",
        sa.Column("source_blob_id", sa.String(length=128), nullable=False),
        sa.Column("sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("storage_ref", sa.String(length=512), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("source_blob_id", name="pk_source_blobs"),
        sa.UniqueConstraint("sha256", name="uq_source_blobs_sha256"),
    )
    op.create_table(
        "source_document_versions_v2",
        sa.Column("source_document_version_id", sa.String(length=128), nullable=False),
        sa.Column("logical_document_id", sa.String(length=128), nullable=False),
        sa.Column("source_blob_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("file_name", sa.String(length=512), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("review_episode_id", sa.String(length=128), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("supersedes_version_id", sa.String(length=128), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_blob_sha256"], ["source_blobs.sha256"],
            name="fk_source_document_versions_v2_source_blobs_source_blob_sha256",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"],
            name="fk_source_document_versions_v2_projects_project_id",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.subject_id"],
            name="fk_source_document_versions_v2_subjects_subject_id",
        ),
        sa.ForeignKeyConstraint(
            ["review_episode_id"], ["review_episodes.review_episode_id"],
            name="fk_source_document_versions_v2_review_episodes_review_episode_id",
        ),
        sa.PrimaryKeyConstraint(
            "source_document_version_id", name="pk_source_document_versions_v2"
        ),
        sa.UniqueConstraint(
            "review_episode_id", "logical_document_id", "version_number",
            name="uq_sdv2_episode_logical_version",
        ),
    )
    op.create_index(
        "ix_sdv2_review_episode_id", "source_document_versions_v2", ["review_episode_id"]
    )
    op.create_index(
        "ix_sdv2_logical_document_id", "source_document_versions_v2", ["logical_document_id"]
    )
    op.create_table(
        "source_document_metadata_revisions",
        sa.Column("metadata_revision_id", sa.String(length=128), nullable=False),
        sa.Column("source_document_version_id", sa.String(length=128), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(length=128), nullable=False),
        sa.Column("source_party", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("is_auto_suggestion", sa.Boolean(), nullable=False),
        sa.Column("supersedes_metadata_revision_id", sa.String(length=128), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_document_version_id"],
            ["source_document_versions_v2.source_document_version_id"],
            name="fk_source_document_metadata_revisions_source_document_versions_v2_source_document_version_id",
        ),
        sa.PrimaryKeyConstraint("metadata_revision_id", name="pk_source_document_metadata_revisions"),
        sa.UniqueConstraint(
            "source_document_version_id", "revision", name="uq_sdmr_doc_revision"
        ),
    )
    op.create_index(
        "ix_sdmr_source_document_version_id",
        "source_document_metadata_revisions",
        ["source_document_version_id"],
    )
    op.create_table(
        "evidence_snapshots_v2",
        sa.Column("evidence_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("review_episode_id", sa.String(length=128), nullable=False),
        sa.Column("upload_mode", sa.String(length=16), nullable=False),
        sa.Column("prior_snapshot_id", sa.String(length=128), nullable=True),
        sa.Column("comparison_snapshot_id", sa.String(length=128), nullable=True),
        sa.Column("collection_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"],
            name="fk_evidence_snapshots_v2_projects_project_id",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.subject_id"],
            name="fk_evidence_snapshots_v2_subjects_subject_id",
        ),
        sa.ForeignKeyConstraint(
            ["review_episode_id"], ["review_episodes.review_episode_id"],
            name="fk_evidence_snapshots_v2_review_episodes_review_episode_id",
        ),
        sa.ForeignKeyConstraint(
            ["prior_snapshot_id"], ["evidence_snapshots_v2.evidence_snapshot_id"],
            name="fk_evidence_snapshots_v2_evidence_snapshots_v2_prior_snapshot_id",
        ),
        sa.PrimaryKeyConstraint("evidence_snapshot_id", name="pk_evidence_snapshots_v2"),
    )
    op.create_index(
        "ix_esnapv2_review_episode_id", "evidence_snapshots_v2", ["review_episode_id"]
    )
    op.create_index(
        "ix_esnapv2_subject_id", "evidence_snapshots_v2", ["subject_id"]
    )
    op.create_table(
        "evidence_snapshot_members",
        sa.Column("member_id", sa.String(length=128), nullable=False),
        sa.Column("snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("logical_document_id", sa.String(length=128), nullable=False),
        sa.Column("source_document_version_id", sa.String(length=128), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["evidence_snapshots_v2.evidence_snapshot_id"],
            name="fk_evidence_snapshot_members_evidence_snapshots_v2_snapshot_id",
        ),
        sa.ForeignKeyConstraint(
            ["source_document_version_id"],
            ["source_document_versions_v2.source_document_version_id"],
            name="fk_evidence_snapshot_members_source_document_versions_v2_source_document_version_id",
        ),
        sa.PrimaryKeyConstraint("member_id", name="pk_evidence_snapshot_members"),
        sa.UniqueConstraint(
            "snapshot_id", "logical_document_id", name="uq_esm_snapshot_logical"
        ),
    )
    op.create_index("ix_esm_snapshot_id", "evidence_snapshot_members", ["snapshot_id"])
    op.create_table(
        "evidence_snapshot_status_events",
        sa.Column("snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=False),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["evidence_snapshots_v2.evidence_snapshot_id"],
            name="fk_evidence_snapshot_status_events_evidence_snapshots_v2_snapshot_id",
        ),
        sa.PrimaryKeyConstraint("snapshot_id", "seq", name="pk_evidence_snapshot_status_events"),
    )
    op.create_index(
        "ix_esse_snapshot_id", "evidence_snapshot_status_events", ["snapshot_id"]
    )


def downgrade() -> None:
    # 0008 的证据历史不可通过降级静默丢失；空表绿地库才允许反向删除。
    bind = op.get_bind()
    evidence_tables = (
        "evidence_snapshot_status_events",
        "evidence_snapshot_members",
        "evidence_snapshots_v2",
        "source_document_metadata_revisions",
        "source_document_versions_v2",
        "source_blobs",
    )
    populated = [
        table_name
        for table_name in evidence_tables
        if bind.exec_driver_sql(f"SELECT 1 FROM {table_name} LIMIT 1").first() is not None
    ]
    if populated:
        raise RuntimeError(
            "0008 含有证据正式数据，拒绝降级以避免丢失不可变历史："
            + ", ".join(populated)
        )

    # 依赖逆序删除：先删子表，再删父表。
    op.drop_table("evidence_snapshot_status_events")
    op.drop_table("evidence_snapshot_members")
    op.drop_table("evidence_snapshots_v2")
    op.drop_table("source_document_metadata_revisions")
    op.drop_table("source_document_versions_v2")
    op.drop_table("source_blobs")
