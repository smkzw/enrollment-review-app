"""Phase 5 Slice 5.7：修订提交栅栏与冲突谱系（追加写）。

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-23

``fact_correction_commits`` 把一次成功修订绑定到其产生的 Patient Profile
revision，并保存提交时实际采用的影响范围。``fact_correction_conflict_outcomes``
以类型化外键记录被替代的旧冲突组与可选后继组：解决时后继为空，并列冲突时追加
新组。旧冲突组与旧 Profile 均不改写。含正式数据时拒绝有损降级。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PAYLOAD_SHA_LEN = 64


def upgrade() -> None:
    op.create_table(
        "fact_correction_commits",
        sa.Column("correction_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("review_episode_id", sa.String(length=128), nullable=False),
        sa.Column("episode_revision", sa.Integer(), nullable=False),
        sa.Column("protocol_version_id", sa.String(length=128), nullable=False),
        sa.Column("rule_set_id", sa.String(length=128), nullable=False),
        sa.Column("rule_set_revision", sa.Integer(), nullable=False),
        sa.Column("evidence_snapshot_v2_id", sa.String(length=128), nullable=False),
        sa.Column("complete_processing_revision_id", sa.String(length=128), nullable=False),
        sa.Column("patient_profile_revision_id", sa.String(length=128), nullable=False),
        sa.Column("impact_scope_kind", sa.String(length=16), nullable=False),
        sa.Column("impact_fallback_reason", sa.Text(), nullable=True),
        sa.Column("impact_scope_json", sa.JSON(), nullable=False),
        sa.Column("superseded_conflict_group_ids_json", sa.JSON(), nullable=False),
        sa.Column("successor_conflict_group_ids_json", sa.JSON(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "impact_scope_kind IN ('local', 'node')",
            name="ck_fcorr_commit_scope_kind",
        ),
        sa.ForeignKeyConstraint(["correction_id"], ["fact_corrections.correction_id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        sa.ForeignKeyConstraint(
            ["review_episode_id"], ["review_episodes.review_episode_id"]
        ),
        sa.ForeignKeyConstraint(
            ["protocol_version_id"],
            ["protocol_document_versions.protocol_version_id"],
        ),
        sa.ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision"],
            ["rule_sets.rule_set_id", "rule_sets.revision"],
        ),
        sa.ForeignKeyConstraint(
            ["evidence_snapshot_v2_id"], ["evidence_snapshots_v2.evidence_snapshot_id"]
        ),
        sa.ForeignKeyConstraint(
            ["complete_processing_revision_id"],
            ["evidence_processing_revisions.evidence_processing_revision_id"],
        ),
        sa.ForeignKeyConstraint(
            ["patient_profile_revision_id"],
            ["patient_profile_revisions_v2.patient_profile_revision_id"],
        ),
        sa.PrimaryKeyConstraint("correction_id", name="pk_fact_correction_commits"),
        sa.UniqueConstraint("correction_id", name="uq_fcorr_commit_correction_id"),
    )
    op.create_index(
        "ix_fcorr_commit_review_episode_id",
        "fact_correction_commits",
        ["review_episode_id"],
        unique=False,
    )
    op.create_index(
        "ix_fcorr_commit_profile_revision_id",
        "fact_correction_commits",
        ["patient_profile_revision_id"],
        unique=False,
    )
    op.create_table(
        "fact_correction_conflict_outcomes",
        sa.Column("outcome_id", sa.String(length=128), nullable=False),
        sa.Column("correction_id", sa.String(length=128), nullable=False),
        sa.Column("superseded_conflict_group_id", sa.String(length=128), nullable=False),
        sa.Column("successor_conflict_group_id", sa.String(length=128), nullable=True),
        sa.CheckConstraint(
            "successor_conflict_group_id IS NULL OR successor_conflict_group_id != superseded_conflict_group_id",
            name="ck_fcorr_conflict_outcome_distinct",
        ),
        sa.ForeignKeyConstraint(
            ["correction_id"], ["fact_correction_commits.correction_id"]
        ),
        sa.ForeignKeyConstraint(
            ["superseded_conflict_group_id"],
            ["clinical_conflict_groups_v2.conflict_group_id"],
        ),
        sa.ForeignKeyConstraint(
            ["successor_conflict_group_id"],
            ["clinical_conflict_groups_v2.conflict_group_id"],
        ),
        sa.PrimaryKeyConstraint("outcome_id", name="pk_fact_correction_conflict_outcomes"),
        sa.UniqueConstraint(
            "correction_id",
            "superseded_conflict_group_id",
            name="uq_fcorr_conflict_outcome_superseded",
        ),
    )
    op.create_index(
        "ix_fcorr_conflict_outcome_correction_id",
        "fact_correction_conflict_outcomes",
        ["correction_id"],
        unique=False,
    )
    op.create_index(
        "ix_fcorr_conflict_outcome_superseded",
        "fact_correction_conflict_outcomes",
        ["superseded_conflict_group_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    count = bind.exec_driver_sql(
        "SELECT COUNT(*) FROM fact_correction_commits"
    ).scalar_one()
    if count:
        raise RuntimeError("0018 fact_correction_commits 已有不可变历史，拒绝有损降级")
    op.drop_index(
        "ix_fcorr_conflict_outcome_superseded",
        table_name="fact_correction_conflict_outcomes",
    )
    op.drop_index(
        "ix_fcorr_conflict_outcome_correction_id",
        table_name="fact_correction_conflict_outcomes",
    )
    op.drop_table("fact_correction_conflict_outcomes")
    op.drop_index(
        "ix_fcorr_commit_profile_revision_id", table_name="fact_correction_commits"
    )
    op.drop_index(
        "ix_fcorr_commit_review_episode_id", table_name="fact_correction_commits"
    )
    op.drop_table("fact_correction_commits")
