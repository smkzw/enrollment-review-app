"""Published variable vocabulary belongs to one immutable rule-set revision."""
from alembic import op
import sqlalchemy as sa

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("rule_set_variables",
        sa.Column("rule_set_id", sa.String(128), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["rule_set_id", "revision"], ["rule_sets.rule_set_id", "rule_sets.revision"]))


def downgrade():
    if op.get_bind().exec_driver_sql("SELECT 1 FROM rule_set_variables LIMIT 1").first():
        raise RuntimeError("已有发布数据项目，拒绝有损降级")
    op.drop_table("rule_set_variables")
