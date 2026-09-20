"""跨章控制来源资料要求：新增 control_publication_id 与三选一来源约束（0025）。

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-14

``evidence_requirements`` 增加第三来源列 ``control_publication_id``：指向 0024 建立
的不可变跨章控制目录发布 ``protocol_control_catalog_publications.publication_id``。
列可空；历史组件来源行与流程必做项目来源行逐行原样保留，``payload_json`` /
``payload_sha256`` 不变。控制来源的 ``protocol_control_id`` / ``evidence_key`` /
``workflow_stage_id`` 继续只存在于 payload 正文，本迁移不新增镜像列或新表。

``one_origin`` CHECK 从「两个来源二选一」改为「三个来源三选一」，SQLite 无法原地
修改 CHECK，因此沿用 0006 的既有做法重建 ``evidence_requirements``：建临时表 ->
按显式列名拷贝（新列为 NULL）-> 删旧表 -> 改名，随后用 ``PRAGMA foreign_key_check``
验证 ``evidence_expectations`` 等子表行与外键完整保留。重建期间在 raw 连接上临时
关闭外键（env.py 已按迁移粒度关闭外层事务，见 ``transaction_per_migration=False``）。

降级只在没有任何控制来源行时允许：存在 ``control_publication_id`` 非空的历史行时
显式拒绝，绝不静默丢弃或改写这些行的来源。
"""

from __future__ import annotations

from collections.abc import Sequence

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
)

# revision identifiers, used by Alembic.
revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_NAME = "evidence_requirements"
_INDEX_NAME = "ix_evidence_requirements_fact_type"
_PAYLOAD_SHA_LEN = 64

#: 三选一来源：恰好一个非空（组件 / 流程必做项目 / 已发布控制）。
_THREE_ORIGIN_CHECK_SQL = (
    "(rule_component_id IS NOT NULL AND procedure_catalog_item_id IS NULL "
    "AND control_publication_id IS NULL) OR "
    "(rule_component_id IS NULL AND procedure_catalog_item_id IS NOT NULL "
    "AND control_publication_id IS NULL) OR "
    "(rule_component_id IS NULL AND procedure_catalog_item_id IS NULL "
    "AND control_publication_id IS NOT NULL)"
)

#: 0006 形状的二选一来源（仅降级重建使用）。
_TWO_ORIGIN_CHECK_SQL = (
    "(rule_component_id IS NULL) != (procedure_catalog_item_id IS NULL)"
)

_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(referred_table_name)s_%(column_0_N_name)s",
    "pk": "pk_%(table_name)s",
}

def _declare_parent_stubs(target: MetaData, *, with_control_catalog: bool) -> None:
    """父表 stub 只用于解析外键，不重建父表（同 0006）。"""
    Table(
        "rule_sets",
        target,
        Column("rule_set_id", String(128), primary_key=True),
        Column("revision", Integer, primary_key=True),
    )
    Table(
        "rule_components",
        target,
        Column("rule_set_id", String(128), primary_key=True),
        Column("rule_set_revision", Integer, primary_key=True),
        Column("rule_component_id", String(128), primary_key=True),
    )
    if with_control_catalog:
        Table(
            "protocol_control_catalog_publications",
            target,
            Column("publication_id", String(128), primary_key=True),
        )


def _three_origin_requirements_table(table_name: str, target: MetaData) -> Table:
    """0025 形状 evidence_requirements（三选一来源，表名可定制为临时名）。"""
    _declare_parent_stubs(target, with_control_catalog=True)
    table = Table(
        table_name,
        target,
        Column("rule_set_id", String(128), nullable=False, primary_key=True),
        Column("rule_set_revision", Integer, nullable=False, primary_key=True),
        Column("requirement_id", String(128), nullable=False, primary_key=True),
        Column("rule_component_id", String(128), nullable=True),
        Column("procedure_catalog_item_id", String(128), nullable=True),
        Column("control_publication_id", String(128), nullable=True),
        Column("fact_type", String(128), nullable=False),
        Column("due_stage", String(32), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(_PAYLOAD_SHA_LEN), nullable=False),
        Column("created_at", DateTime, nullable=False),
        CheckConstraint(_THREE_ORIGIN_CHECK_SQL, name="one_origin"),
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
        ForeignKeyConstraint(
            ["control_publication_id"],
            ["protocol_control_catalog_publications.publication_id"],
        ),
    )
    Index(_INDEX_NAME, table.c.fact_type)
    return table


def _two_origin_requirements_table(table_name: str, target: MetaData) -> Table:
    """0006/0024 形状 evidence_requirements（二选一来源，降级用）。"""
    _declare_parent_stubs(target, with_control_catalog=False)
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
        Column("payload_sha256", String(_PAYLOAD_SHA_LEN), nullable=False),
        Column("created_at", DateTime, nullable=False),
        CheckConstraint(_TWO_ORIGIN_CHECK_SQL, name="one_origin"),
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
    Index(_INDEX_NAME, table.c.fact_type)
    return table


def _raw_dbapi(bind):
    """DBAPI 层连接：事务内 ``PRAGMA foreign_keys`` 是 no-op，必须在 raw 连接执行。"""
    return bind.connection.driver_connection


def _rebuild_requirements_table(*, with_control_origin: bool) -> None:
    """建新表 -> 拷贝 -> 删旧表 -> 改名，保住子表对 evidence_requirements 的外键目标。

    升级方向新增 ``control_publication_id``（历史行写 NULL）；降级方向去掉该列。
    两种形状都按显式列名拷贝，``payload_json`` / ``payload_sha256`` 原样保留，
    不重算哈希、不改写正文。
    """
    bind = op.get_bind()
    # Finish Alembic's prior bookkeeping before toggling SQLite enforcement.
    # All destructive rebuild steps below belong to one explicit transaction.
    bind.commit()
    raw = _raw_dbapi(bind)
    previous_foreign_keys = int(raw.execute("PRAGMA foreign_keys").fetchone()[0])
    raw.execute("PRAGMA foreign_keys = OFF")
    if raw.execute("PRAGMA foreign_keys").fetchone()[0] != 0:
        raise RuntimeError("无法进入资料要求结构迁移，未重建原表")
    try:
        raw.execute("BEGIN IMMEDIATE")
        if not with_control_origin:
            control_rows = raw.execute(
                f"SELECT COUNT(*) FROM {_TABLE_NAME} WHERE control_publication_id IS NOT NULL"
            ).fetchone()[0]
            if control_rows:
                raise RuntimeError(
                    f"检测到 {control_rows} 条控制来源资料要求，拒绝有损降级到 0024"
                )
        metadata = MetaData(naming_convention=_NAMING_CONVENTION)
        # SQLite 索引名是库级命名空间；旧索引先释放，新表才能创建同名索引。
        op.execute(f"DROP INDEX IF EXISTS {_INDEX_NAME}")
        if with_control_origin:
            temp_name = f"{_TABLE_NAME}_new"
            new_table = _three_origin_requirements_table(temp_name, metadata)
            columns = (
                "rule_set_id, rule_set_revision, requirement_id, rule_component_id, "
                "procedure_catalog_item_id, control_publication_id, fact_type, "
                "due_stage, payload_json, payload_sha256, created_at"
            )
            source_columns = (
                "rule_set_id, rule_set_revision, requirement_id, rule_component_id, "
                "procedure_catalog_item_id, NULL, fact_type, "
                "due_stage, payload_json, payload_sha256, created_at"
            )
        else:
            temp_name = f"{_TABLE_NAME}_legacy"
            new_table = _two_origin_requirements_table(temp_name, metadata)
            columns = (
                "rule_set_id, rule_set_revision, requirement_id, rule_component_id, "
                "procedure_catalog_item_id, fact_type, "
                "due_stage, payload_json, payload_sha256, created_at"
            )
            source_columns = columns
        new_table.create(bind=bind)
        op.execute(
            f"INSERT INTO {temp_name} ({columns}) "
            f"SELECT {source_columns} FROM {_TABLE_NAME}"
        )
        op.execute(f"DROP TABLE {_TABLE_NAME}")
        op.execute(f"ALTER TABLE {temp_name} RENAME TO {_TABLE_NAME}")
        if raw.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("资料要求迁移后引用不完整，回滚本次表重建")
        bind.commit()
    except BaseException:
        bind.rollback()
        raw.rollback()
        raise
    finally:
        raw.execute(f"PRAGMA foreign_keys = {previous_foreign_keys}")


def upgrade() -> None:
    _rebuild_requirements_table(with_control_origin=True)


def downgrade() -> None:
    # Refusal is checked under the same write lock as table reconstruction.
    _rebuild_requirements_table(with_control_origin=False)
