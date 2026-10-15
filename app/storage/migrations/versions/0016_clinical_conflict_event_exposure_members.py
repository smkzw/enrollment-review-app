"""Phase 5：持久化事件与用药/治疗暴露冲突成员。

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-23

既有冲突组均为事实冲突，新增 ``member_kind`` 时以 ``fact`` 回填；事件与暴露分别
使用独立关联表，避免多态外键失去数据库约束。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("clinical_conflict_groups_v2") as batch_op:
        batch_op.add_column(
            sa.Column(
                "member_kind",
                sa.String(length=16),
                nullable=False,
                server_default="fact",
            )
        )
        batch_op.create_check_constraint(
            "ck_ccgv2_member_kind",
            "member_kind IN ('fact', 'event', 'exposure')",
        )

    op.create_table(
        "clinical_conflict_event_members_v2",
        sa.Column("conflict_group_id", sa.String(length=128), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(
            ["conflict_group_id"],
            ["clinical_conflict_groups_v2.conflict_group_id"],
            name="fk_ccem_conflict_group_id",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["clinical_events_v2.event_id"],
            name="fk_ccem_event_id",
        ),
        sa.PrimaryKeyConstraint(
            "conflict_group_id", "position", name="pk_ccem_conflict_position"
        ),
        sa.UniqueConstraint(
            "conflict_group_id", "event_id", name="uq_ccem_conflict_event"
        ),
    )
    op.create_index(
        "ix_ccem_event_id", "clinical_conflict_event_members_v2", ["event_id"]
    )

    op.create_table(
        "clinical_conflict_exposure_members_v2",
        sa.Column("conflict_group_id", sa.String(length=128), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("exposure_id", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(
            ["conflict_group_id"],
            ["clinical_conflict_groups_v2.conflict_group_id"],
            name="fk_ccxm_conflict_group_id",
        ),
        sa.ForeignKeyConstraint(
            ["exposure_id"],
            ["medication_exposures_v2.exposure_id"],
            name="fk_ccxm_exposure_id",
        ),
        sa.PrimaryKeyConstraint(
            "conflict_group_id", "position", name="pk_ccxm_conflict_position"
        ),
        sa.UniqueConstraint(
            "conflict_group_id", "exposure_id", name="uq_ccxm_conflict_exposure"
        ),
    )
    op.create_index(
        "ix_ccxm_exposure_id",
        "clinical_conflict_exposure_members_v2",
        ["exposure_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    event_count = bind.exec_driver_sql(
        "SELECT COUNT(*) FROM clinical_conflict_event_members_v2"
    ).scalar_one()
    exposure_count = bind.exec_driver_sql(
        "SELECT COUNT(*) FROM clinical_conflict_exposure_members_v2"
    ).scalar_one()
    if event_count or exposure_count:
        raise RuntimeError("0016 冲突成员表已有不可变历史，拒绝有损降级")

    op.drop_index("ix_ccxm_exposure_id", table_name="clinical_conflict_exposure_members_v2")
    op.drop_table("clinical_conflict_exposure_members_v2")
    op.drop_index("ix_ccem_event_id", table_name="clinical_conflict_event_members_v2")
    op.drop_table("clinical_conflict_event_members_v2")
    with op.batch_alter_table("clinical_conflict_groups_v2") as batch_op:
        batch_op.drop_constraint("ck_ccgv2_member_kind", type_="check")
        batch_op.drop_column("member_kind")
