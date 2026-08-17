"""Phase 3 切片 4：资料要求来源修复、审核节点期别与草稿 revision 历史

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-17

本迁移只做追加/修复，不回写 0001-0005：

1. 重建 ``evidence_requirements``：``rule_component_id`` 改为可空并新增
   ``procedure_catalog_item_id``，用 CHECK 约束保证「且只能绑定一个来源」；
   既有组件来源行原样保留（rule_component_id 非空、流程来源列空）。
   重建采用「建新表 -> 拷贝 -> 删旧表 -> 改名」，避免 SQLite 的 RENAME
   改写 ``evidence_expectations`` 等引用表的外键目标；``evidence_expectations``
   等子表已有真实行时，重建在非事务连接上临时关闭外键，完成后用
   ``PRAGMA foreign_key_check`` 验证子行与外键完整保留，再恢复外键约束。
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
    JSON,
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
    Column("required_source_types", JSON, nullable=True),
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


def _foreign_key_check_ok(bind) -> bool:
    """PRAGMA foreign_key_check 必须无违规行；有违规即返回 False。"""
    raw = _raw_dbapi(bind)
    try:
        rows = raw.execute("PRAGMA foreign_key_check").fetchall()
    except Exception:
        return False
    return not rows


def _raw_dbapi(bind):
    """DBAPI 层连接：SQLAlchemy 的 autobegin 会让事务内 PRAGMA foreign_keys
    变成 no-op，因此 FK 开关与完整性检查必须在 raw 连接上执行。"""
    return bind.connection.driver_connection


def _disable_foreign_keys(bind) -> None:
    raw = _raw_dbapi(bind)
    # 关闭 SQLAlchemy 隐式开启的事务，让 PRAGMA foreign_keys 真正生效；
    # 无事务时 COMMIT 是空操作，幂等无害。
    try:
        raw.execute("COMMIT")
    except Exception:
        pass
    raw.execute("PRAGMA foreign_keys = OFF")


def _restore_foreign_keys(bind) -> None:
    raw = _raw_dbapi(bind)
    try:
        raw.execute("COMMIT")
    except Exception:
        pass
    raw.execute("PRAGMA foreign_keys = ON")


def _rebuild_requirements_table(
    *,
    new_shape: bool,
) -> None:
    """建新表 -> 拷贝 -> 删旧表 -> 改名，保住引用表外键目标。

    ``evidence_expectations`` 等子表可能已有真实行引用 ``evidence_requirements``；
    重建期间在 raw 连接上临时关闭外键（见 env.py
    ``transaction_per_migration=False`` 与 :func:`_disable_foreign_keys`），
    重建完成后用 ``PRAGMA foreign_key_check`` 验证子行与外键完整保留，
    再恢复外键约束。
    """
    bind = op.get_bind()
    _disable_foreign_keys(bind)
    try:
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
    finally:
        _restore_foreign_keys(bind)
    if not _foreign_key_check_ok(bind):
        raise RuntimeError(
            "迁移重建 evidence_requirements 后外键完整性检查失败；"
            "子表行与外键引用未完整保留，禁止继续迁移"
        )


def _has_slice4_data(bind) -> bool:
    """是否存在 Slice 4 正式数据；有则禁止有损降级。"""
    for table, where in (
        ("protocol_draft_revisions", "1=1"),
        ("evidence_expectation_templates", "1=1"),
        ("evidence_requirements", "procedure_catalog_item_id IS NOT NULL"),
        ("workflow_stages", "study_phase IS NOT NULL"),
    ):
        try:
            count = bind.exec_driver_sql(
                f"SELECT COUNT(*) FROM {table} WHERE {where}"
            ).scalar_one()
        except Exception:
            continue
        if count:
            return True
    return False


def upgrade() -> None:
    # 新形状含 procedure_catalog_item_id 且 rule_component_id 可空。
    _rebuild_requirements_table(new_shape=True)
    op.add_column("workflow_stages", Column("study_phase", String(32), nullable=True))
    bind = op.get_bind()
    protocol_draft_revisions.create(bind=bind)
    evidence_expectation_templates.create(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    # 有损降级只允许用于灾难恢复：含 Slice 4 正式数据时必须显式拒绝，
    # 不得静默丢弃流程来源行、草稿历史或模板投影。
    if _has_slice4_data(bind):
        raise RuntimeError(
            "数据库包含 Phase 3 切片 4 正式数据（流程来源资料要求、草稿 revision "
            "历史、期望模板或审核节点期别），拒绝有损降级到 0005；"
            "仅允许空库或无切片 4 数据时降级"
        )
    evidence_expectation_templates.drop(bind=bind)
    protocol_draft_revisions.drop(bind=bind)
    op.drop_column("workflow_stages", "study_phase")
    # 还原 0002 形状：rule_component_id 非空；流程来源行不属于旧契约，丢弃。
    _rebuild_requirements_table(new_shape=False)
