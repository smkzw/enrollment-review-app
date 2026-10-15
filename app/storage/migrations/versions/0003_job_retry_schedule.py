"""job_steps 重试调度时间

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为可重试步骤持久化退避时间，使重试调度在服务重启后仍然成立。"""
    op.add_column(
        "job_steps",
        sa.Column("retry_not_before", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """SQLite 列删除走 batch mode（env.py 已启用 render_as_batch）。"""
    with op.batch_alter_table("job_steps") as batch_op:
        batch_op.drop_column("retry_not_before")
