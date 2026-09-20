"""跨章控制目录发布的不可变存储（0024）。

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-14

只新建 ``protocol_control_catalog_publications`` 一张表：每个正式 ``RuleSet`` 修订
至多一个已发布跨章控制目录。列、主键、唯一约束、外键与索引与 ORM
``ProtocolControlCatalogRecord`` 逐项一致（启动验证逐项对比）。

本迁移不写入任何行，也不读取或改写既有协议、规则、Job、检查点与门禁结果；
``(rule_set_id, rule_set_revision)`` 唯一约束保证目录变化必须发布新的正式规则修订。
降级只在表为空时允许：已存在不可变发布历史时拒绝有损降级。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PAYLOAD_SHA_LEN = 64

_TABLE_NAME = "protocol_control_catalog_publications"


def upgrade() -> None:
    op.create_table(
        _TABLE_NAME,
        sa.Column("publication_id", sa.String(length=128), primary_key=True),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("protocol_version_id", sa.String(length=128), nullable=False),
        sa.Column("rule_set_id", sa.String(length=128), nullable=False),
        sa.Column("rule_set_revision", sa.Integer(), nullable=False),
        sa.Column("catalog_id", sa.String(length=128), nullable=False),
        sa.Column("source_job_id", sa.String(length=128), nullable=False),
        sa.Column("source_checkpoint_id", sa.String(length=128), nullable=False),
        sa.Column("gate_result_id", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
        sa.ForeignKeyConstraint(
            ["protocol_version_id"],
            ["protocol_document_versions.protocol_version_id"],
        ),
        sa.ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision"],
            ["rule_sets.rule_set_id", "rule_sets.revision"],
        ),
        sa.ForeignKeyConstraint(["source_job_id"], ["jobs.job_id"]),
        sa.ForeignKeyConstraint(
            ["source_checkpoint_id"],
            ["job_checkpoints.checkpoint_id"],
        ),
        sa.ForeignKeyConstraint(["gate_result_id"], ["gate_results.gate_result_id"]),
        sa.UniqueConstraint(
            "rule_set_id", "rule_set_revision", name="uq_pccp_rule_set_revision"
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.exec_driver_sql(f"SELECT COUNT(*) FROM {_TABLE_NAME}").scalar_one():
        raise RuntimeError("0024 跨章控制目录发布已有不可变历史，拒绝有损降级")
    op.drop_table(_TABLE_NAME)
