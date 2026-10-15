"""持久任务声明式用户确认边界。

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "job_steps",
        sa.Column("waiting_user_kind", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table("job_steps") as batch_op:
        batch_op.drop_column("waiting_user_kind")
