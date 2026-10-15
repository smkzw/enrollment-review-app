"""Append working results without changing existing clinical history."""
from alembic import op
import sqlalchemy as sa

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("review_runs", sa.Column("run_kind", sa.String(32), nullable=True))
    op.add_column("review_runs", sa.Column("system_issues", sa.JSON(), nullable=True))
    op.create_table("work_draft_items",
        sa.Column("item_id", sa.String(128), primary_key=True),
        sa.Column("review_run_id", sa.String(128), sa.ForeignKey("review_runs.review_run_id"), nullable=False),
        sa.Column("official_code", sa.String(32), nullable=False),
        sa.Column("rule_component_id", sa.String(128), nullable=True),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_work_draft_items_run", "work_draft_items", ["review_run_id"])
    op.create_table("work_draft_acknowledgements",
        sa.Column("acknowledgement_id", sa.String(128), primary_key=True),
        sa.Column("review_episode_id", sa.String(128), sa.ForeignKey("review_episodes.review_episode_id"), nullable=False),
        sa.Column("official_code", sa.String(32), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))


def downgrade():
    if op.get_bind().exec_driver_sql("SELECT 1 FROM review_runs WHERE run_kind = 'work_draft' LIMIT 1").first():
        raise RuntimeError("已有工作稿记录，拒绝有损降级")
    op.drop_table("work_draft_acknowledgements")
    op.drop_index("ix_work_draft_items_run", table_name="work_draft_items")
    op.drop_table("work_draft_items")
    op.drop_column("review_runs", "system_issues")
    op.drop_column("review_runs", "run_kind")
