"""Phase 5：发布事实的断言对象改为必填。

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-23

0013 已经是既有迁移，不能通过回改它来收紧数据库约束，否则已升级到 0013
的数据库不会得到新约束。本迁移只收紧 ``clinical_facts_v2.assertion_object``：
发现历史空值时明确拒绝升级，不根据事实类型或正文猜测断言对象。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _raw_dbapi(bind):
    return bind.connection.driver_connection


def _disable_foreign_keys(bind) -> None:
    raw = _raw_dbapi(bind)
    try:
        raw.execute("COMMIT")
    except Exception:  # noqa: BLE001, S110 - 无活动事务时 COMMIT 失败无害
        pass
    raw.execute("PRAGMA foreign_keys = OFF")


def _restore_foreign_keys(bind) -> None:
    raw = _raw_dbapi(bind)
    try:
        raw.execute("COMMIT")
    except Exception:  # noqa: BLE001, S110 - 无活动事务时 COMMIT 失败无害
        pass
    raw.execute("PRAGMA foreign_keys = ON")


def _assert_foreign_keys_clean(bind) -> None:
    rows = _raw_dbapi(bind).execute("PRAGMA foreign_key_check").fetchall()
    if rows:
        raise RuntimeError("0014 迁移后外键完整性检查未通过")


def _alter_assertion_object(*, nullable: bool) -> None:
    bind = op.get_bind()
    _disable_foreign_keys(bind)
    try:
        with op.batch_alter_table("clinical_facts_v2") as batch_op:
            batch_op.alter_column(
                "assertion_object",
                existing_type=sa.String(length=256),
                existing_nullable=not nullable,
                nullable=nullable,
            )
    finally:
        _restore_foreign_keys(bind)
    _assert_foreign_keys_clean(bind)


def upgrade() -> None:
    bind = op.get_bind()
    null_count = bind.exec_driver_sql(
        "SELECT COUNT(*) FROM clinical_facts_v2 WHERE assertion_object IS NULL"
    ).scalar_one()
    if null_count:
        raise RuntimeError(
            "0014 检测到发布事实缺少断言对象，拒绝猜测或静默回填："
            f"{null_count} 条"
        )
    _alter_assertion_object(nullable=False)


def downgrade() -> None:
    _alter_assertion_object(nullable=True)
