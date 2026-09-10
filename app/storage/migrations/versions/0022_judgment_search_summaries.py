"""研究者书面判断检索覆盖摘要追加写存储。

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SHA = 64


def upgrade() -> None:
    op.create_table(
        "judgment_search_summaries",
        sa.Column("summary_id", sa.String(length=128), primary_key=True),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("review_episode_id", sa.String(length=128), nullable=False),
        sa.Column("evidence_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("evidence_processing_revision_id", sa.String(length=128), nullable=False),
        sa.Column("rule_set_id", sa.String(length=128), nullable=False),
        sa.Column("rule_set_revision", sa.Integer(), nullable=False),
        sa.Column("scope_sha256", sa.String(length=_SHA), nullable=False),
        sa.Column("requirement_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("found_candidate_count", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_SHA), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('candidates_present','all_supplied_pages_searched_without_candidate',"
            "'coverage_incomplete')",
            name="ck_jss_status",
        ),
        sa.CheckConstraint("found_candidate_count >= 0", name="ck_jss_found_count"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        sa.ForeignKeyConstraint(["review_episode_id"], ["review_episodes.review_episode_id"]),
        sa.ForeignKeyConstraint(["evidence_snapshot_id"], ["evidence_snapshots_v2.evidence_snapshot_id"]),
        sa.ForeignKeyConstraint(
            ["evidence_processing_revision_id"],
            ["evidence_processing_revisions.evidence_processing_revision_id"],
        ),
    )
    op.create_index(
        "ix_jss_authority_requirement",
        "judgment_search_summaries",
        ["review_episode_id", "evidence_processing_revision_id", "rule_set_id",
         "rule_set_revision", "requirement_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.exec_driver_sql("SELECT COUNT(*) FROM judgment_search_summaries").scalar_one():
        raise RuntimeError("0022 判断检索摘要已有不可变历史，拒绝有损降级")
    op.drop_index("ix_jss_authority_requirement", table_name="judgment_search_summaries")
    op.drop_table("judgment_search_summaries")
