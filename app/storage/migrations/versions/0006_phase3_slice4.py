"""Phase 3 切片 4：资料要求来源修复、审核节点期别与草稿 revision 历史

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-17

本迁移只做追加/修复，不回写 0001-0005：

1. 重建 ``evidence_requirements``：``rule_component_id`` 改为可空并新增
   ``procedure_catalog_item_id``，用 CHECK 约束保证「且只能绑定一个来源」；
   既有组件来源行原样保留（rule_component_id 非空、流程来源列空）。
   重建采用「建新表 -> 拷贝 -> 删旧表 -> 改名」，避免 SQLite 的 RENAME
   改写 ``evidence_expectations`` 等引用表的外键目标。
2. ``workflow_stages`` 追加 ``study_phase`` 列：同一操作在筛选与基线分别
   执行时按 (阶段, 期别) 保持身份，不跨项目合并审核节点。
3. 新增 ``protocol_draft_revisions``（不可变草稿历史，取消/发布不物理删除）。
4. 新增 ``evidence_expectation_templates``（无受试者模板投影，可重建）。
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(referred_table_name)s_%(column_0_N_name)s",
        "pk": "pk_%(table_name)s",
    }
)

# 0002 拥有的父表；轻量 stub 只用于解析外键，不重建父表。
rule_sets = Table(
    "rule_sets",
    metadata,
    Column("rule_set_id", String(128), primary_key=True),
    Column("revision", Integer, primary_key=True),
)
rule_components = Table(
    "rule_components",
    metadata,
    Column("rule_set_id", String(128), primary_key=True),
    Column("rule_set_revision", Integer, primary_key=True),
    Column("rule_component_id", String(128), primary_key=True),
)


def _new_shape_requirements_table(table_name: str, target: MetaData) -> Table:
    """新形状 evidence_requirements（表名可定制为临时名）。"""
    table = Table(
        table_name,
        target,
        Column("rule_set_id", String(128), nullable=False, primary_key=True),
        Column("rule_set_revision", Integer, nullable=False, primary_key=True),
        Column("requirement_id", String(128), nullable=False, primary_key=True),
        Column("rule_component_id", String(128), nullable=True),
        Column("procedure_catalog_item_id", String(128), nullable=True),
        Column("fact_type", String(128), nullable=False),
        Column("due_stage", String(32), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        CheckConstraint(
            "(rule_component_id IS NULL) != (procedure_catalog_item_id IS NULL)",
            name="one_origin",
        ),
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision"],
            ["rule_sets.rule_set_id", "rule_sets.revision"],
        ),
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision", "rule_component_id"],
            [
                "rule_components.rule_set_id",
                "rule_components.rule_set_revision",
                "rule_components.rule_component_id",
            ],
        ),
    )
    Index("ix_evidence_requirements_fact_type", table.c.fact_type)
    return table


def _legacy_shape_requirements_table(table_name: str, target: MetaData) -> Table:
    """0002 形状 evidence_requirements（rule_component_id 非空）。"""
    legacy_rule_sets = Table(
        "rule_sets",
        target,
        Column("rule_set_id", String(128), primary_key=True),
        Column("revision", Integer, primary_key=True),
    )
    legacy_rule_components = Table(
        "rule_components",
        target,
        Column("rule_set_id", String(128), primary_key=True),
        Column("rule_set_revision", Integer, primary_key=True),
        Column("rule_component_id", String(128), primary_key=True),
    )
    table = Table(
        table_name,
        target,
        Column("rule_set_id", String(128), nullable=False, primary_key=True),
        Column("rule_set_revision", Integer, nullable=False, primary_key=True),
        Column("requirement_id", String(128), nullable=False, primary_key=True),
        Column("rule_component_id", String(128), nullable=False),
        Column("fact_type", String(128), nullable=False),
        Column("due_stage", String(32), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision", "rule_component_id"],
            [
                "rule_components.rule_set_id",
                "rule_components.rule_set_revision",
                "rule_components.rule_component_id",
            ],
        ),
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision"],
            ["rule_sets.rule_set_id", "rule_sets.revision"],
        ),
    )
    Index("ix_evidence_requirements_fact_type", table.c.fact_type)
    return table


# 降级用独立 MetaData：避免与升级形状的 stub 同名冲突。
downgrade_metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(referred_table_name)s_%(column_0_N_name)s",
        "pk": "pk_%(table_name)s",
    }
)


protocol_draft_revisions = Table(
    "protocol_draft_revisions",
    metadata,
    Column("revision_id", String(128), primary_key=True),
    Column("draft_id", String(128), nullable=False),
    Column("revision_number", Integer, nullable=False),
    Column("previous_revision_id", String(128), nullable=True),
    Column("project_id", String(128), nullable=False),
    Column("protocol_version_id", String(128), nullable=False),
    Column("study_phase", String(32), nullable=False),
    Column("status", String(32), nullable=False),
    Column("reason", String(32), nullable=False),
    Column("feedback_kind", String(32), nullable=True),
    Column("actor", String(128), nullable=False),
    Column("content_sha256", String(64), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("draft_id", "revision_number"),
)

evidence_expectation_templates = Table(
    "evidence_expectation_templates",
    metadata,
    Column("template_id", String(128), primary_key=True),
    Column("rule_set_id", String(128), nullable=False),
    Column("rule_set_revision", Integer, nullable=False),
    Column("requirement_id", String(128), nullable=False),
    Column("due_stage", String(32), nullable=False),
    Column("study_phase", String(32), nullable=False),
    Column("workflow_stage_id", String(128), nullable=True),
    Column("fact_type", String(128), nullable=False),
    Column("projection_sha256", String(64), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("rule_set_id", "rule_set_revision", "requirement_id"),
)

Index("ix_protocol_draft_revisions_draft_id", protocol_draft_revisions.c.draft_id)
Index(
    "ix_evidence_expectation_templates_rule_set",
    evidence_expectation_templates.c.rule_set_id,
    evidence_expectation_templates.c.rule_set_revision,
)


def _rebuild_requirements_table(
    *,
    new_shape: bool,
) -> None:
    """建新表 -> 拷贝 -> 删旧表 -> 改名，保住引用表外键目标。"""
    bind = op.get_bind()
    # SQLite 索引名是库级命名空间；旧索引先释放，新表才能创建同名索引。
    op.execute("DROP INDEX IF EXISTS ix_evidence_requirements_fact_type")
    temp_name = (
        "evidence_requirements_new" if new_shape else "evidence_requirements_legacy"
    )
    if new_shape:
        new_table = _new_shape_requirements_table(temp_name, metadata)
        columns = (
            "rule_set_id, rule_set_revision, requirement_id, rule_component_id, "
            "procedure_catalog_item_id, fact_type, due_stage, "
            "payload_json, payload_sha256, created_at"
        )
        source_columns = (
            "rule_set_id, rule_set_revision, requirement_id, rule_component_id, "
            "NULL, fact_type, due_stage, "
            "payload_json, payload_sha256, created_at"
        )
        where_clause = ""
    else:
        new_table = _legacy_shape_requirements_table(temp_name, downgrade_metadata)
        columns = (
            "rule_set_id, rule_set_revision, requirement_id, rule_component_id, "
            "fact_type, due_stage, payload_json, payload_sha256, created_at"
        )
        source_columns = (
            "rule_set_id, rule_set_revision, requirement_id, rule_component_id, "
            "fact_type, due_stage, payload_json, payload_sha256, created_at"
        )
        where_clause = "WHERE rule_component_id IS NOT NULL"
    new_table.create(bind=bind)
    op.execute(
        f"INSERT INTO {temp_name} ({columns}) "
        f"SELECT {source_columns} FROM evidence_requirements {where_clause}"
    )
    op.execute("DROP TABLE evidence_requirements")
    op.execute(f"ALTER TABLE {temp_name} RENAME TO evidence_requirements")


def upgrade() -> None:
    # 新形状含 procedure_catalog_item_id 且 rule_component_id 可空。
    _rebuild_requirements_table(new_shape=True)
    op.add_column("workflow_stages", Column("study_phase", String(32), nullable=True))
    bind = op.get_bind()
    protocol_draft_revisions.create(bind=bind)
    evidence_expectation_templates.create(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    evidence_expectation_templates.drop(bind=bind)
    protocol_draft_revisions.drop(bind=bind)
    op.drop_column("workflow_stages", "study_phase")
    # 还原 0002 形状：rule_component_id 非空；流程来源行不属于旧契约，丢弃。
    _rebuild_requirements_table(new_shape=False)
