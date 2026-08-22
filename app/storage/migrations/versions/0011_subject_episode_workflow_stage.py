"""Phase 4 迁移 0011：审核节点流程节点身份与可空 legacy 快照（WP-44 subject entry）。

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-21

背景：新增受试者必须为正式已发布项目原子实例化「每个需要审核的流程节点」对应的
审核节点；多个访视实例可能共享同一 ``ReviewStage``，必须用命名空间化的
``workflow_stage_id`` 区分。新建的空审核节点没有 Phase 2/3 legacy 证据快照，
因此 ``evidence_snapshot_id`` 必须允许为空，且绝不伪造占位快照或哨兵 ID。

本迁移只做追加/修复，不回写既有行：

1. 重建 ``review_episodes``：
   - ``evidence_snapshot_id`` 由 NOT NULL 改为可空（legacy 行非空值原样保留，
     FK 仍指向 ``evidence_snapshots`` 且保持 deferrable）；
   - 新增可空 ``workflow_stage_id`` 列（FK 到 ``workflow_stages.workflow_stage_id``，
     legacy 行为 NULL）。重建采用「建新表 -> 拷贝 -> 删旧表 -> 改名」，
     子表引用外键与全部行原样保留，重建后用 ``PRAGMA foreign_key_check`` 验证。
   - 成对活动指针列、其 CHECK 约束与全部既有外键/索引保持逐字不变。

降级（回 0010）只允许「无自动节点」的情况：任一审核节点 ``workflow_stage_id``
非空（自动建立）或 ``evidence_snapshot_id`` 为空（新式空节点）时，降级会把不可变
身份或空快照语义丢弃/违反 NOT NULL，必须拒绝并由管理器从迁移前备份恢复。
"""
from collections.abc import Sequence

from alembic import op
from sqlalchemy import (
    JSON,
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

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _raw_dbapi(bind):
    """DBAPI 层连接：SQLAlchemy 的 autobegin 会让事务内 PRAGMA foreign_keys
    变成 no-op，因此 FK 开关与完整性检查必须在 raw 连接上执行。"""
    return bind.connection.driver_connection


def _disable_foreign_keys(bind) -> None:
    raw = _raw_dbapi(bind)
    try:
        raw.execute("COMMIT")
    except Exception:  # noqa: BLE001, S110 - 与 0006/0010 同款模式；无事务 COMMIT 失败无害
        pass
    raw.execute("PRAGMA foreign_keys = OFF")


def _restore_foreign_keys(bind) -> None:
    raw = _raw_dbapi(bind)
    try:
        raw.execute("COMMIT")
    except Exception:  # noqa: BLE001, S110 - 与 0006/0010 同款模式
        pass
    raw.execute("PRAGMA foreign_keys = ON")


def _foreign_key_check_ok(bind) -> bool:
    raw = _raw_dbapi(bind)
    try:
        rows = raw.execute("PRAGMA foreign_key_check").fetchall()
    except Exception:  # noqa: BLE001 - 检查失败按不通过处理，由迁移管理器兜底
        return False
    return not rows


#: 升级形状的父表 stub：只用于解析外键，不重建父表。
metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(referred_table_name)s_%(column_0_N_name)s",
        "pk": "pk_%(table_name)s",
    }
)

projects = Table("projects", metadata, Column("project_id", String(128), primary_key=True))
subjects = Table("subjects", metadata, Column("subject_id", String(128), primary_key=True))
rule_sets = Table(
    "rule_sets",
    metadata,
    Column("rule_set_id", String(128), primary_key=True),
    Column("revision", Integer, primary_key=True),
)
protocol_document_versions = Table(
    "protocol_document_versions",
    metadata,
    Column("protocol_version_id", String(128), primary_key=True),
)
evidence_snapshots = Table(
    "evidence_snapshots",
    metadata,
    Column("evidence_snapshot_id", String(128), primary_key=True),
)
evidence_snapshots_v2 = Table(
    "evidence_snapshots_v2",
    metadata,
    Column("evidence_snapshot_id", String(128), primary_key=True),
)
evidence_processing_revisions = Table(
    "evidence_processing_revisions",
    metadata,
    Column("evidence_processing_revision_id", String(128), primary_key=True),
)
workflow_stages = Table(
    "workflow_stages",
    metadata,
    Column("workflow_stage_id", String(128), primary_key=True),
)


def _new_review_episodes_table(table_name: str, target: MetaData) -> Table:
    """0010 形状 + 可空 evidence_snapshot_id + 可空 workflow_stage_id（升级目标）。"""
    table = Table(
        table_name,
        target,
        Column("review_episode_id", String(128), nullable=False, primary_key=True),
        Column("subject_id", String(128), nullable=False),
        Column("project_id", String(128), nullable=False),
        Column("rule_set_id", String(128), nullable=False),
        Column("rule_set_revision", Integer, nullable=False),
        Column("study_phase", String(32), nullable=False),
        Column("stage", String(32), nullable=False),
        Column("protocol_version_id", String(128), nullable=False),
        Column("evidence_snapshot_id", String(128), nullable=True),
        Column("workflow_stage_id", String(128), nullable=True),
        Column("active_evidence_snapshot_id", String(128), nullable=True),
        Column("active_evidence_processing_revision_id", String(128), nullable=True),
        Column("anchor_dates_json", JSON, nullable=False),
        Column("due_at", DateTime, nullable=True),
        Column("revision", Integer, nullable=False),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        CheckConstraint(
            "(active_evidence_snapshot_id IS NULL AND "
            "active_evidence_processing_revision_id IS NULL) OR "
            "(active_evidence_snapshot_id IS NOT NULL AND "
            "active_evidence_processing_revision_id IS NOT NULL)",
            name="ck_review_episodes_active_pointers_paired",
        ),
        ForeignKeyConstraint(
            ["protocol_version_id"],
            ["protocol_document_versions.protocol_version_id"],
        ),
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision"],
            ["rule_sets.rule_set_id", "rule_sets.revision"],
        ),
        ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        ForeignKeyConstraint(
            ["evidence_snapshot_id"],
            ["evidence_snapshots.evidence_snapshot_id"],
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["workflow_stage_id"],
            ["workflow_stages.workflow_stage_id"],
        ),
        ForeignKeyConstraint(
            ["active_evidence_snapshot_id"],
            ["evidence_snapshots_v2.evidence_snapshot_id"],
        ),
        ForeignKeyConstraint(
            ["active_evidence_processing_revision_id"],
            ["evidence_processing_revisions.evidence_processing_revision_id"],
        ),
        ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
    )
    Index("ix_review_episodes_subject_id", table.c.subject_id)
    Index("ix_review_episodes_project_id", table.c.project_id)
    return table


def _legacy_review_episodes_table(table_name: str, target: MetaData) -> Table:
    """0010 形状（降级目标）：无 workflow_stage_id，evidence_snapshot_id NOT NULL。"""
    table = Table(
        table_name,
        target,
        Column("review_episode_id", String(128), nullable=False, primary_key=True),
        Column("subject_id", String(128), nullable=False),
        Column("project_id", String(128), nullable=False),
        Column("rule_set_id", String(128), nullable=False),
        Column("rule_set_revision", Integer, nullable=False),
        Column("study_phase", String(32), nullable=False),
        Column("stage", String(32), nullable=False),
        Column("protocol_version_id", String(128), nullable=False),
        Column("evidence_snapshot_id", String(128), nullable=False),
        Column("active_evidence_snapshot_id", String(128), nullable=True),
        Column("active_evidence_processing_revision_id", String(128), nullable=True),
        Column("anchor_dates_json", JSON, nullable=False),
        Column("due_at", DateTime, nullable=True),
        Column("revision", Integer, nullable=False),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        CheckConstraint(
            "(active_evidence_snapshot_id IS NULL AND "
            "active_evidence_processing_revision_id IS NULL) OR "
            "(active_evidence_snapshot_id IS NOT NULL AND "
            "active_evidence_processing_revision_id IS NOT NULL)",
            name="ck_review_episodes_active_pointers_paired",
        ),
        ForeignKeyConstraint(
            ["protocol_version_id"],
            ["protocol_document_versions.protocol_version_id"],
        ),
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision"],
            ["rule_sets.rule_set_id", "rule_sets.revision"],
        ),
        ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        ForeignKeyConstraint(
            ["evidence_snapshot_id"],
            ["evidence_snapshots.evidence_snapshot_id"],
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["active_evidence_snapshot_id"],
            ["evidence_snapshots_v2.evidence_snapshot_id"],
        ),
        ForeignKeyConstraint(
            ["active_evidence_processing_revision_id"],
            ["evidence_processing_revisions.evidence_processing_revision_id"],
        ),
        ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
    )
    Index("ix_review_episodes_subject_id", table.c.subject_id)
    Index("ix_review_episodes_project_id", table.c.project_id)
    return table


def _rebuild_review_episodes(*, with_workflow_stage: bool) -> None:
    """建新表 -> 拷贝 -> 删旧表 -> 改名，保留子表外键目标与 legacy deferrable FK。"""
    bind = op.get_bind()
    _disable_foreign_keys(bind)
    try:
        op.execute("DROP INDEX IF EXISTS ix_review_episodes_subject_id")
        op.execute("DROP INDEX IF EXISTS ix_review_episodes_project_id")
        temp_name = "review_episodes_new" if with_workflow_stage else "review_episodes_legacy"
        if with_workflow_stage:
            new_table = _new_review_episodes_table(temp_name, metadata)
        else:
            new_table = _legacy_review_episodes_table(temp_name, metadata)
        new_table.create(bind=bind)
        if with_workflow_stage:
            # 升级：既有行无 workflow_stage_id（置 NULL），evidence_snapshot_id 原样保留。
            columns = (
                "review_episode_id, subject_id, project_id, rule_set_id, "
                "rule_set_revision, study_phase, stage, protocol_version_id, "
                "evidence_snapshot_id, workflow_stage_id, "
                "active_evidence_snapshot_id, active_evidence_processing_revision_id, "
                "anchor_dates_json, due_at, revision, created_at, updated_at, "
                "payload_json, payload_sha256"
            )
            source_columns = (
                "review_episode_id, subject_id, project_id, rule_set_id, "
                "rule_set_revision, study_phase, stage, protocol_version_id, "
                "evidence_snapshot_id, NULL, "
                "active_evidence_snapshot_id, active_evidence_processing_revision_id, "
                "anchor_dates_json, due_at, revision, created_at, updated_at, "
                "payload_json, payload_sha256"
            )
        else:
            # 降级：丢弃 workflow_stage_id 列；evidence_snapshot_id 恢复 NOT NULL。
            columns = (
                "review_episode_id, subject_id, project_id, rule_set_id, "
                "rule_set_revision, study_phase, stage, protocol_version_id, "
                "evidence_snapshot_id, active_evidence_snapshot_id, "
                "active_evidence_processing_revision_id, anchor_dates_json, due_at, "
                "revision, created_at, updated_at, payload_json, payload_sha256"
            )
            source_columns = columns
        op.execute(
            f"INSERT INTO {temp_name} ({columns}) "
            f"SELECT {source_columns} FROM review_episodes"
        )
        op.execute("DROP TABLE review_episodes")
        op.execute(f"ALTER TABLE {temp_name} RENAME TO review_episodes")
    finally:
        _restore_foreign_keys(bind)
    if not _foreign_key_check_ok(bind):
        raise RuntimeError(
            "迁移重建 review_episodes 后外键完整性检查失败；"
            "子表行与外键引用未完整保留，禁止继续迁移"
        )


def upgrade() -> None:
    _rebuild_review_episodes(with_workflow_stage=True)


def downgrade() -> None:
    bind = op.get_bind()
    raw = _raw_dbapi(bind)
    _disable_foreign_keys(bind)
    try:
        # 自动建立的空节点（workflow_stage_id 非空，或 evidence_snapshot_id 为空）
        # 在 0010 形状下无法表示：降级会丢弃节点身份或违反 NOT NULL，必须拒绝。
        has_new_episodes = raw.execute(
            "SELECT EXISTS("
            "SELECT 1 FROM review_episodes "
            "WHERE workflow_stage_id IS NOT NULL OR evidence_snapshot_id IS NULL)"
        ).fetchone()[0]
    finally:
        _restore_foreign_keys(bind)
    if has_new_episodes:
        raise RuntimeError(
            "存在自动建立的空审核节点（workflow_stage_id 非空或 evidence_snapshot_id 为空），"
            "降级会丢弃节点身份或违反旧 NOT NULL 约束，拒绝有损降级"
        )
    _rebuild_review_episodes(with_workflow_stage=False)
