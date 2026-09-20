"""Add immutable control report parts; existing clinical rows are untouched."""
from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "review_control_snapshots",
        sa.Column("review_run_id", sa.String(128), primary_key=True),
        sa.Column("context_id", sa.String(128), nullable=False),
        sa.Column("gate_result_id", sa.String(128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["review_run_id"], ["review_runs.review_run_id"]),
        sa.ForeignKeyConstraint(["context_id"], ["review_context_snapshots.context_id"]),
        sa.ForeignKeyConstraint(["gate_result_id"], ["gate_results.gate_result_id"]),
    )


def downgrade():
    if op.get_bind().exec_driver_sql("SELECT COUNT(*) FROM review_control_snapshots").scalar_one():
        raise RuntimeError("已有补充要求审核历史，拒绝有损降级")
    op.drop_table("review_control_snapshots")
