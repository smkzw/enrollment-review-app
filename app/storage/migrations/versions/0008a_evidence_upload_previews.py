"""Phase 4 上传预览/条目/确认（Slice 4.2）：证据上传预览表

Revision ID: 0008a
Revises: 0008
Create Date: 2026-08-19

本迁移只新增 Phase 4 上传预览三张表，不回改已验收的 ``0008_evidence_ingestion``，
也不占用后续 ``0009_ocr_artifacts`` 的编号与职责；``down_revision`` 指向
``0008_evidence_ingestion``，升级顺序保持 0007 -> 0008 -> 0008a。表名/列/约束以
``app/storage/evidence_upload_models.py`` 为权威，由 ``verify_schema_matches_metadata``
在迁移后逐表交叉核对。降级按依赖逆序删除。

新增表：

- ``evidence_upload_previews``  短期候选预览：作用域、上传方式、基准快照、
                                创建时修订号、状态与确定性摘要（预览不是临床快照）；
- ``evidence_upload_items``     逐文件指纹/格式/大小/分类/处理建议/冲突，
                                文件名不是内容身份；暂存引用指向预览自有目录；
- ``evidence_upload_commits``   确认动作：预览摘要哈希、幂等键、产生的候选快照
                                与重复集合 no-op 标志。

``evidence_upload_previews.base_snapshot_id`` 与
``evidence_upload_commits.evidence_snapshot_id`` 建立到既有证据快照的外键；
取消只清理预览自有暂存，本迁移不触碰共享 blob 或历史表。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008a"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PAYLOAD_SHA_LEN = 64


def upgrade() -> None:
    op.create_table(
        "evidence_upload_previews",
        sa.Column("preview_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("review_episode_id", sa.String(length=128), nullable=False),
        sa.Column("upload_mode", sa.String(length=16), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("base_snapshot_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("preview_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"],
            name="fk_evidence_upload_previews_projects_project_id",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.subject_id"],
            name="fk_evidence_upload_previews_subjects_subject_id",
        ),
        sa.ForeignKeyConstraint(
            ["review_episode_id"], ["review_episodes.review_episode_id"],
            name="fk_evidence_upload_previews_review_episodes_review_episode_id",
        ),
        sa.ForeignKeyConstraint(
            ["base_snapshot_id"], ["evidence_snapshots_v2.evidence_snapshot_id"],
            name="fk_evidence_upload_previews_evidence_snapshots_v2_base_snapshot_id",
        ),
        sa.PrimaryKeyConstraint("preview_id", name="pk_evidence_upload_previews"),
    )
    op.create_index(
        "ix_eup_review_episode_id", "evidence_upload_previews", ["review_episode_id"]
    )
    op.create_index(
        "ix_eup_subject_id", "evidence_upload_previews", ["subject_id"]
    )
    op.create_table(
        "evidence_upload_items",
        sa.Column("item_id", sa.String(length=128), nullable=False),
        sa.Column("preview_id", sa.String(length=128), nullable=False),
        sa.Column("file_name", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("storage_ref", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("processing_hint", sa.String(length=32), nullable=False),
        sa.Column("logical_document_id", sa.String(length=128), nullable=True),
        sa.Column("existing_version_id", sa.String(length=128), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["preview_id"], ["evidence_upload_previews.preview_id"],
            name="fk_evidence_upload_items_evidence_upload_previews_preview_id",
        ),
        sa.PrimaryKeyConstraint("item_id", name="pk_evidence_upload_items"),
    )
    op.create_index(
        "ix_eui_preview_id", "evidence_upload_items", ["preview_id"]
    )
    op.create_table(
        "evidence_upload_commits",
        sa.Column("commit_id", sa.String(length=128), nullable=False),
        sa.Column("preview_id", sa.String(length=128), nullable=False),
        sa.Column("evidence_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("review_episode_id", sa.String(length=128), nullable=False),
        sa.Column("upload_mode", sa.String(length=16), nullable=False),
        sa.Column("preview_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("idempotency_key", sa.String(length=512), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=True),
        sa.Column("duplicate", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["preview_id"], ["evidence_upload_previews.preview_id"],
            name="fk_evidence_upload_commits_evidence_upload_previews_preview_id",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_snapshot_id"], ["evidence_snapshots_v2.evidence_snapshot_id"],
            name="fk_evidence_upload_commits_evidence_snapshots_v2_evidence_snapshot_id",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"],
            name="fk_evidence_upload_commits_projects_project_id",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.subject_id"],
            name="fk_evidence_upload_commits_subjects_subject_id",
        ),
        sa.ForeignKeyConstraint(
            ["review_episode_id"], ["review_episodes.review_episode_id"],
            name="fk_evidence_upload_commits_review_episodes_review_episode_id",
        ),
        sa.PrimaryKeyConstraint("commit_id", name="pk_evidence_upload_commits"),
    )
    op.create_index(
        "ix_euc_preview_id", "evidence_upload_commits", ["preview_id"]
    )
    op.create_index(
        "ix_euc_evidence_snapshot_id", "evidence_upload_commits", ["evidence_snapshot_id"]
    )


def downgrade() -> None:
    # 0008a 的预览/确认历史不可通过降级静默丢失；空表绿地库才允许反向删除。
    bind = op.get_bind()
    upload_tables = (
        "evidence_upload_commits",
        "evidence_upload_items",
        "evidence_upload_previews",
    )
    populated = [
        table_name
        for table_name in upload_tables
        if bind.exec_driver_sql(f"SELECT 1 FROM {table_name} LIMIT 1").first() is not None
    ]
    if populated:
        raise RuntimeError(
            "0008a 含有上传预览或确认数据，拒绝降级以避免丢失不可变历史："
            + ", ".join(populated)
        )

    # 依赖逆序删除：先删子表（条目/确认），再删预览主表。
    op.drop_table("evidence_upload_commits")
    op.drop_table("evidence_upload_items")
    op.drop_table("evidence_upload_previews")
