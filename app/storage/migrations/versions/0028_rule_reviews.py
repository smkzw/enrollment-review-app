"""Append-only, per-entry rule review history; existing payloads stay unchanged."""
from alembic import op
import sqlalchemy as sa

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rule_review_records",
        sa.Column("sequence", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("record_id", sa.String(128), nullable=False, unique=True),
        sa.Column("draft_id", sa.String(128), nullable=False),
        sa.Column("protocol_version_id", sa.String(128), nullable=False),
        sa.Column("official_code", sa.String(256), nullable=False),
        sa.Column("rule_content_hash", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_rule_review_scope", "rule_review_records",
                    ["protocol_version_id", "draft_id", "official_code"])


def downgrade():
    if op.get_bind().exec_driver_sql("SELECT 1 FROM rule_review_records LIMIT 1").first():
        raise RuntimeError("已有审定历史，拒绝有损降级")
    op.drop_table("rule_review_records")
