"""R3 页级判读、对账和页覆盖追加写存储。

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SHA = 64


def _payload_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_SHA), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "page_review_records",
        sa.Column("page_review_id", sa.String(length=128), primary_key=True),
        sa.Column("page_artifact_id", sa.String(length=128), nullable=False),
        sa.Column("source_document_version_id", sa.String(length=128), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("page_image_sha256", sa.String(length=_SHA), nullable=False),
        sa.Column("clause_pack_id", sa.String(length=128), nullable=False),
        sa.Column("clause_pack_sha256", sa.String(length=_SHA), nullable=False),
        sa.Column("lane", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("model", sa.String(length=256), nullable=False),
        sa.Column("reasoning_effort", sa.String(length=16), nullable=False),
        sa.Column("endpoint_base_url", sa.String(length=512), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("finish_reason", sa.String(length=128), nullable=True),
        sa.Column("usage_json", sa.JSON(), nullable=False),
        sa.Column("prompt_version", sa.String(length=128), nullable=False),
        sa.Column("response_sha256", sa.String(length=_SHA), nullable=False),
        sa.Column("has_eligibility_value", sa.Boolean(), nullable=False),
        *_payload_columns(),
        sa.CheckConstraint("page_number >= 1", name="ck_prr_page_number"),
        sa.CheckConstraint("lane IN ('main-A','main-B','handwriting-C')", name="ck_prr_lane"),
        sa.ForeignKeyConstraint(["page_artifact_id"], ["page_artifacts.page_artifact_id"]),
        sa.ForeignKeyConstraint(["source_document_version_id"], ["source_document_versions_v2.source_document_version_id"]),
        sa.UniqueConstraint("page_artifact_id", "clause_pack_sha256", "lane", "response_sha256", name="uq_prr_page_pack_lane_response"),
    )
    op.create_index("ix_prr_page_artifact_id", "page_review_records", ["page_artifact_id"])

    op.create_table(
        "page_reconciliations",
        sa.Column("reconciliation_id", sa.String(length=128), primary_key=True),
        sa.Column("page_artifact_id", sa.String(length=128), nullable=False),
        sa.Column("clause_pack_sha256", sa.String(length=_SHA), nullable=False),
        sa.Column("handwriting_reader_triggered", sa.Boolean(), nullable=False),
        *_payload_columns(),
        sa.ForeignKeyConstraint(["page_artifact_id"], ["page_artifacts.page_artifact_id"]),
    )
    op.create_index("ix_prec_page_artifact_id", "page_reconciliations", ["page_artifact_id"])
    op.create_table(
        "page_reconciliation_reviews",
        sa.Column("reconciliation_id", sa.String(length=128), nullable=False),
        sa.Column("page_review_id", sa.String(length=128), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position >= 1", name="ck_prr_link_position"),
        sa.ForeignKeyConstraint(["reconciliation_id"], ["page_reconciliations.reconciliation_id"]),
        sa.ForeignKeyConstraint(["page_review_id"], ["page_review_records.page_review_id"]),
        sa.PrimaryKeyConstraint("reconciliation_id", "page_review_id"),
        sa.UniqueConstraint("reconciliation_id", "position", name="uq_prr_link_position"),
    )

    op.create_table(
        "subject_page_coverages",
        sa.Column("coverage_id", sa.String(length=128), primary_key=True),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("review_episode_id", sa.String(length=128), nullable=False),
        sa.Column("evidence_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("evidence_processing_revision_id", sa.String(length=128), nullable=False),
        sa.Column("clause_pack_sha256", sa.String(length=_SHA), nullable=False),
        sa.Column("expected_page_count", sa.Integer(), nullable=False),
        *_payload_columns(),
        sa.CheckConstraint("expected_page_count >= 1", name="ck_spc_expected_page_count"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        sa.ForeignKeyConstraint(["review_episode_id"], ["review_episodes.review_episode_id"]),
        sa.ForeignKeyConstraint(["evidence_snapshot_id"], ["evidence_snapshots_v2.evidence_snapshot_id"]),
        sa.ForeignKeyConstraint(["evidence_processing_revision_id"], ["evidence_processing_revisions.evidence_processing_revision_id"]),
    )
    op.create_index("ix_spc_episode_revision", "subject_page_coverages", ["review_episode_id", "evidence_processing_revision_id"])
    op.create_table(
        "subject_page_coverage_entries",
        sa.Column("coverage_id", sa.String(length=128), nullable=False),
        sa.Column("page_artifact_id", sa.String(length=128), nullable=False),
        sa.Column("source_document_version_id", sa.String(length=128), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("disposition", sa.String(length=48), nullable=False),
        sa.Column("reconciliation_id", sa.String(length=128), nullable=True),
        sa.Column("discard_reason", sa.Text(), nullable=True),
        sa.Column("lane_failures_json", sa.JSON(), nullable=False),
        sa.CheckConstraint("page_number >= 1 AND position >= 1", name="ck_spce_position"),
        sa.CheckConstraint("disposition IN ('accepted','discarded_no_eligibility_value','failed_pending_reread')", name="ck_spce_disposition"),
        sa.ForeignKeyConstraint(["coverage_id"], ["subject_page_coverages.coverage_id"]),
        sa.ForeignKeyConstraint(["page_artifact_id"], ["page_artifacts.page_artifact_id"]),
        sa.ForeignKeyConstraint(["source_document_version_id"], ["source_document_versions_v2.source_document_version_id"]),
        sa.ForeignKeyConstraint(["reconciliation_id"], ["page_reconciliations.reconciliation_id"]),
        sa.PrimaryKeyConstraint("coverage_id", "page_artifact_id"),
        sa.UniqueConstraint("coverage_id", "position", name="uq_spce_position"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("subject_page_coverages", "page_reconciliations", "page_review_records"):
        if bind.exec_driver_sql(f"SELECT COUNT(*) FROM {table}").scalar_one():
            raise RuntimeError("0020 页级判读已有不可变历史，拒绝有损降级")
    op.drop_table("subject_page_coverage_entries")
    op.drop_index("ix_spc_episode_revision", table_name="subject_page_coverages")
    op.drop_table("subject_page_coverages")
    op.drop_table("page_reconciliation_reviews")
    op.drop_index("ix_prec_page_artifact_id", table_name="page_reconciliations")
    op.drop_table("page_reconciliations")
    op.drop_index("ix_prr_page_artifact_id", table_name="page_review_records")
    op.drop_table("page_review_records")
