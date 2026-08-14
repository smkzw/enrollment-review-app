"""v2 基线 schema

Revision ID: 0001
Revises:
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """基线：仅标记 schema 起点，不建业务表。

    领域表由后续迁移（0002_domain_schema）引入；本迁移保持空，
    以便升级/降级/再升级的基线与 ORM metadata 一致。
    """
    connection = op.get_bind()
    actual = {
        "foreign_keys": connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one(),
        "journal_mode": connection.exec_driver_sql("PRAGMA journal_mode").scalar_one(),
        "synchronous": connection.exec_driver_sql("PRAGMA synchronous").scalar_one(),
        "busy_timeout": connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one(),
    }
    expected = {
        "foreign_keys": 1,
        "journal_mode": "wal",
        "synchronous": 2,
        "busy_timeout": 10_000,
    }
    if actual != expected:
        raise RuntimeError(f"V2 migration connection PRAGMA mismatch: {actual}")


def downgrade() -> None:
    """降级回空基线：删除 alembic 版本标记，不触碰业务数据目录。"""
