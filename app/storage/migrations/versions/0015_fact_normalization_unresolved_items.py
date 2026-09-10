"""Phase 5：持久化证据规范化逐页未解决项。

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-23

未解决项此前只存在任务检查点中，无法作为后续资料期望和 Patient Profile 的稳定
输入。本迁移新增独立追加写表，不回写候选、事实或旧项目数据。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fact_normalization_unresolved_items",
        sa.Column("unresolved_item_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("call_id", sa.String(length=128), nullable=False),
        sa.Column("logical_document_id", sa.String(length=128), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("affected_pages_json", sa.JSON(), nullable=False),
        sa.Column("affected_locator_ids_json", sa.JSON(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["fact_normalization_runs.run_id"],
            name="fk_fact_normalization_unresolved_items_run_id",
        ),
        sa.ForeignKeyConstraint(
            ["call_id"],
            ["fact_normalization_calls.call_id"],
            name="fk_fact_normalization_unresolved_items_call_id",
        ),
        sa.ForeignKeyConstraint(
            ["call_id", "run_id"],
            ["fact_normalization_calls.call_id", "fact_normalization_calls.run_id"],
            name="fk_fnunresolved_call_run",
        ),
        sa.PrimaryKeyConstraint(
            "unresolved_item_id",
            name="pk_fact_normalization_unresolved_items",
        ),
        sa.UniqueConstraint(
            "call_id", "position", name="uq_fnunresolved_call_position"
        ),
    )
    op.create_index(
        "ix_fnunresolved_run_id",
        "fact_normalization_unresolved_items",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_fnunresolved_call_id",
        "fact_normalization_unresolved_items",
        ["call_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    count = bind.exec_driver_sql(
        "SELECT COUNT(*) FROM fact_normalization_unresolved_items"
    ).scalar_one()
    if count:
        raise RuntimeError("0015 未解决项表已有不可变历史，拒绝有损降级")
    op.drop_index(
        "ix_fnunresolved_call_id",
        table_name="fact_normalization_unresolved_items",
    )
    op.drop_index(
        "ix_fnunresolved_run_id",
        table_name="fact_normalization_unresolved_items",
    )
    op.drop_table("fact_normalization_unresolved_items")
