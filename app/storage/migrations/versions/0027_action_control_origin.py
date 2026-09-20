"""Extend the existing action lifecycle with a frozen control origin.

No payload, revision or transition is rewritten. Final migration acceptance is
deferred to isolated whole-product verification, never the original clinical DB.
"""
from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

_CHECK = (
    "(assessment_id IS NOT NULL AND rule_component_id IS NOT NULL AND "
    "control_snapshot_run_id IS NULL AND protocol_control_id IS NULL AND control_obligation_id IS NULL AND control_obligation_group_id IS NULL) OR "
    "(assessment_id IS NULL AND rule_component_id IS NULL AND control_snapshot_run_id IS NOT NULL AND "
    "control_snapshot_run_id = review_run_id AND protocol_control_id IS NOT NULL AND "
    "((control_obligation_id IS NOT NULL AND control_obligation_group_id IS NULL) OR "
    "(control_obligation_id IS NULL AND control_obligation_group_id IS NOT NULL)) AND evidence_snapshot_v2_id IS NOT NULL)"
)


def _rebuild(upgrade: bool) -> None:
    bind = op.get_bind()
    raw = bind.connection.driver_connection
    if raw.in_transaction:
        raw.commit()
    raw.execute("PRAGMA foreign_keys=OFF")
    if raw.execute("PRAGMA foreign_keys").fetchone()[0] != 0:
        raise RuntimeError("无法准备办理记录迁移，未重建表")
    try:
        with op.batch_alter_table("action_requests", recreate="always") as batch:
            if upgrade:
                batch.alter_column("assessment_id", existing_type=sa.String(128), nullable=True)
                batch.alter_column("rule_component_id", existing_type=sa.String(128), nullable=True)
                batch.add_column(sa.Column("control_snapshot_run_id", sa.String(128), nullable=True))
                batch.add_column(sa.Column("protocol_control_id", sa.String(128), nullable=True))
                batch.add_column(sa.Column("control_obligation_id", sa.String(128), nullable=True))
                batch.add_column(sa.Column("control_obligation_group_id", sa.String(128), nullable=True))
                batch.create_foreign_key("fk_action_control_snapshot", "review_control_snapshots",
                                         ["control_snapshot_run_id"], ["review_run_id"])
                batch.create_check_constraint("ck_action_requests_requirement_origin", _CHECK)
            else:
                batch.drop_constraint("ck_action_requests_requirement_origin", type_="check")
                batch.drop_constraint("fk_action_control_snapshot", type_="foreignkey")
                for column in ("control_snapshot_run_id", "protocol_control_id", "control_obligation_id", "control_obligation_group_id"):
                    batch.drop_column(column)
                batch.alter_column("assessment_id", existing_type=sa.String(128), nullable=False)
                batch.alter_column("rule_component_id", existing_type=sa.String(128), nullable=False)
    finally:
        if raw.in_transaction:
            raw.commit()
        raw.execute("PRAGMA foreign_keys=ON")
        if raw.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("迁移后外键约束未恢复")
    if raw.execute("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("办理记录迁移后关联不完整，须恢复迁移前备份")


def upgrade() -> None:
    _rebuild(True)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.exec_driver_sql("SELECT 1 FROM action_requests WHERE control_snapshot_run_id IS NOT NULL LIMIT 1").first():
        raise RuntimeError("已有补充要求办理记录，拒绝有损降级")
    _rebuild(False)
