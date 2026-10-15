"""正式审核链双谱系资料（legacy 快照 / V2 快照 + 完整处理修订）。

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-13

本迁移只做追加与形状重建，不产生、不删除、不改写任何正式审核行：

1. 重建五张正式审核链表（``review_runs`` / ``assessment_candidates`` /
   ``final_assessments`` / ``action_requests`` / ``agent_calls``）：
   - ``evidence_snapshot_id`` 由 NOT NULL 改为可空，外键仍指向 legacy
     ``evidence_snapshots``，不删列、不改语义；
   - 新增可空 ``evidence_snapshot_v2_id``（FK ``evidence_snapshots_v2``）与
     ``complete_processing_revision_id``（FK ``evidence_processing_revisions``）；
   - 新增 ``action_requests.trigger_locator_id``（FK
     ``evidence_locator_artifacts``），与 legacy ``trigger_evidence_span_id`` 并存；
   - 正式审核实体（前四张表）加 CHECK：legacy 快照 XOR（V2 快照 + 完整处理修订），
     恰好一条谱系；V2 行的 ``evidence_snapshot_id`` 必须为 NULL，绝不把 V2 id
     写入 legacy 列，也绝不插入假 legacy 证据行；
   - ``agent_calls`` 保留「协议-only 调用三条资料指针全空」的合法形状，仅在
     携带资料指针时要求恰好一条谱系（不套用正式审核实体的强制判别）。
   重建沿用 0010 的「建新表 -> 拷贝 -> 删旧表 -> 改名」约定：拷贝时新列写 NULL，
   子表引用与全部旧行（payload/hash/时间戳/revision）原样保留，重建后用
   ``PRAGMA foreign_key_check`` 验证。

2. 新建五张 V2 谱系有序关联表（与 legacy fact/span 关联表物理分离）：
   ``assessment_candidate_facts_v2`` / ``assessment_candidate_locators`` /
   ``final_assessment_facts_v2`` / ``final_assessment_locators`` /
   ``action_transition_locators``。事实外键指向 ``clinical_facts_v2.fact_id``，
   定位外键指向 ``evidence_locator_artifacts.locator_id``（真实父表键，不使用
   无外键的 kind+id）。

降级只在「尚无 V2 谱系数据」时允许：任一正式审核行携带 V2 指针、或其 legacy
``evidence_snapshot_id`` 为空（AgentCall 的协议-only 全空行除外），或任一 0023
关联表有行时，必须拒绝有损降级（由管理器从迁移前备份恢复），不得静默丢弃
不可变历史。空库降级会删除 0023 关联表并把五张链表重建回 0022 形状。
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PAYLOAD_SHA_LEN = 64

_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(referred_table_name)s_%(column_0_N_name)s",
    "pk": "pk_%(table_name)s",
}

#: ``nullable`` 字段的哨兵值：只在 0023 形状可空（0022 形状 NOT NULL）。
_LINEAGE = "lineage"

#: 0023 新增的谱系列（所有链表共有）。
_V2_LINEAGE_COLUMNS = (
    "evidence_snapshot_v2_id",
    "complete_processing_revision_id",
)

_REVIEW_LINEAGE_CHECK_SQL = (
    "(evidence_snapshot_id IS NOT NULL AND evidence_snapshot_v2_id IS NULL "
    "AND complete_processing_revision_id IS NULL) OR "
    "(evidence_snapshot_id IS NULL AND evidence_snapshot_v2_id IS NOT NULL "
    "AND complete_processing_revision_id IS NOT NULL)"
)

_AGENT_CALL_LINEAGE_CHECK_SQL = (
    "(evidence_snapshot_id IS NULL AND evidence_snapshot_v2_id IS NULL "
    "AND complete_processing_revision_id IS NULL AND node = 'protocol_deconstructor') OR "
    "(evidence_snapshot_id IS NOT NULL AND evidence_snapshot_v2_id IS NULL "
    "AND complete_processing_revision_id IS NULL) OR "
    "(evidence_snapshot_id IS NULL AND evidence_snapshot_v2_id IS NOT NULL "
    "AND complete_processing_revision_id IS NOT NULL)"
)

#: 五张正式审核链表。``columns`` 为 ``(列名, 类型, 可空, 外键目标)``；列顺序与
#: ORM metadata 一致。``v2_only`` 列只在 0023 形状存在；``composite_fks`` 为
#: 复合外键；``indexes`` 必须与 ORM 索引完全一致（启动验证逐项对比）。
_TABLE_SPECS: dict[str, dict] = {
    "review_runs": {
        "pk": "review_run_id",
        "columns": (
            ("review_run_id", String(128), False, None),
            ("review_episode_id", String(128), False, "review_episodes.review_episode_id"),
            (
                "protocol_version_id",
                String(128),
                False,
                "protocol_document_versions.protocol_version_id",
            ),
            ("rule_set_revision", Integer(), False, None),
            ("context_id", String(128), True, "review_context_snapshots.context_id"),
            ("evidence_snapshot_id", String(128), _LINEAGE, "evidence_snapshots.evidence_snapshot_id"),
            ("evidence_snapshot_v2_id", String(128), True, "evidence_snapshots_v2.evidence_snapshot_id"),
            (
                "complete_processing_revision_id",
                String(128),
                True,
                "evidence_processing_revisions.evidence_processing_revision_id",
            ),
            ("started_at", DateTime(), False, None),
            ("completed_at", DateTime(), True, None),
            ("supersedes_review_run_id", String(128), True, "review_runs.review_run_id"),
            ("payload_json", Text(), False, None),
            ("payload_sha256", String(_PAYLOAD_SHA_LEN), False, None),
            ("created_at", DateTime(), False, None),
        ),
        "v2_only": _V2_LINEAGE_COLUMNS + ("context_id",),
        "composite_fks": (),
        "check": ("ck_review_runs_evidence_lineage", _REVIEW_LINEAGE_CHECK_SQL),
        "indexes": (("ix_review_runs_review_episode_id", ("review_episode_id",)),),
    },
    "assessment_candidates": {
        "pk": "assessment_candidate_id",
        "columns": (
            ("assessment_candidate_id", String(128), False, None),
            ("agent_call_id", String(128), False, "agent_calls.agent_call_id"),
            ("project_id", String(128), False, "projects.project_id"),
            (
                "protocol_version_id",
                String(128),
                False,
                "protocol_document_versions.protocol_version_id",
            ),
            ("subject_id", String(128), False, "subjects.subject_id"),
            ("review_episode_id", String(128), False, "review_episodes.review_episode_id"),
            ("review_run_id", String(128), False, "review_runs.review_run_id"),
            ("evidence_snapshot_id", String(128), _LINEAGE, "evidence_snapshots.evidence_snapshot_id"),
            ("evidence_snapshot_v2_id", String(128), True, "evidence_snapshots_v2.evidence_snapshot_id"),
            (
                "complete_processing_revision_id",
                String(128),
                True,
                "evidence_processing_revisions.evidence_processing_revision_id",
            ),
            ("rule_set_id", String(128), False, None),
            ("rule_set_revision", Integer(), False, None),
            ("rule_component_id", String(128), False, None),
            ("payload_json", Text(), False, None),
            ("payload_sha256", String(_PAYLOAD_SHA_LEN), False, None),
            ("created_at", DateTime(), False, None),
        ),
        "v2_only": _V2_LINEAGE_COLUMNS,
        "composite_fks": (
            (
                ("rule_set_id", "rule_set_revision", "rule_component_id"),
                (
                    "rule_components.rule_set_id",
                    "rule_components.rule_set_revision",
                    "rule_components.rule_component_id",
                ),
            ),
        ),
        "check": ("ck_assessment_candidates_evidence_lineage", _REVIEW_LINEAGE_CHECK_SQL),
        "indexes": (
            ("ix_assessment_candidates_review_episode_id", ("review_episode_id",)),
        ),
    },
    "final_assessments": {
        "pk": "assessment_id",
        "columns": (
            ("assessment_id", String(128), False, None),
            ("project_id", String(128), False, "projects.project_id"),
            (
                "protocol_version_id",
                String(128),
                False,
                "protocol_document_versions.protocol_version_id",
            ),
            ("subject_id", String(128), False, "subjects.subject_id"),
            ("review_episode_id", String(128), False, "review_episodes.review_episode_id"),
            ("review_run_id", String(128), False, "review_runs.review_run_id"),
            ("evidence_snapshot_id", String(128), _LINEAGE, "evidence_snapshots.evidence_snapshot_id"),
            ("evidence_snapshot_v2_id", String(128), True, "evidence_snapshots_v2.evidence_snapshot_id"),
            (
                "complete_processing_revision_id",
                String(128),
                True,
                "evidence_processing_revisions.evidence_processing_revision_id",
            ),
            ("rule_set_id", String(128), False, None),
            ("rule_set_revision", Integer(), False, None),
            ("rule_component_id", String(128), False, None),
            ("decision", String(48), False, None),
            ("blocking_level", String(32), False, None),
            ("gate_result_id", String(128), False, "gate_results.gate_result_id"),
            ("publication_fingerprint", String(_PAYLOAD_SHA_LEN), False, None),
            ("payload_json", Text(), False, None),
            ("payload_sha256", String(_PAYLOAD_SHA_LEN), False, None),
            ("created_at", DateTime(), False, None),
        ),
        "v2_only": _V2_LINEAGE_COLUMNS,
        "composite_fks": (
            (
                ("rule_set_id", "rule_set_revision", "rule_component_id"),
                (
                    "rule_components.rule_set_id",
                    "rule_components.rule_set_revision",
                    "rule_components.rule_component_id",
                ),
            ),
        ),
        "check": ("ck_final_assessments_evidence_lineage", _REVIEW_LINEAGE_CHECK_SQL),
        "indexes": (("ix_final_assessments_review_episode_id", ("review_episode_id",)),),
    },
    "action_requests": {
        "pk": "action_id",
        "columns": (
            ("action_id", String(128), False, None),
            ("project_id", String(128), False, "projects.project_id"),
            (
                "protocol_version_id",
                String(128),
                False,
                "protocol_document_versions.protocol_version_id",
            ),
            ("subject_id", String(128), False, "subjects.subject_id"),
            ("rule_set_id", String(128), False, None),
            ("rule_set_revision", Integer(), False, None),
            ("rule_component_id", String(128), False, None),
            ("review_episode_id", String(128), False, "review_episodes.review_episode_id"),
            ("evidence_snapshot_id", String(128), _LINEAGE, "evidence_snapshots.evidence_snapshot_id"),
            ("evidence_snapshot_v2_id", String(128), True, "evidence_snapshots_v2.evidence_snapshot_id"),
            (
                "complete_processing_revision_id",
                String(128),
                True,
                "evidence_processing_revisions.evidence_processing_revision_id",
            ),
            ("review_run_id", String(128), False, "review_runs.review_run_id"),
            ("assessment_id", String(128), False, "final_assessments.assessment_id"),
            ("gap_type", String(64), False, None),
            ("target_party", String(64), False, None),
            ("requested_action", Text(), False, None),
            ("acceptable_evidence", Text(), False, None),
            ("due_stage", String(32), False, None),
            ("blocking_level", String(32), False, None),
            ("trigger_evidence_span_id", String(128), True, "evidence_spans.evidence_span_id"),
            ("trigger_locator_id", String(128), True, "evidence_locator_artifacts.locator_id"),
            ("state", String(32), False, None),
            ("recompute_scope_json", JSON(), False, None),
            ("gate_result_id", String(128), False, "gate_results.gate_result_id"),
            ("publication_fingerprint", String(_PAYLOAD_SHA_LEN), False, None),
            ("revision", Integer(), False, None),
            ("created_at", DateTime(), False, None),
            ("updated_at", DateTime(), False, None),
            ("payload_json", Text(), False, None),
            ("payload_sha256", String(_PAYLOAD_SHA_LEN), False, None),
        ),
        "v2_only": _V2_LINEAGE_COLUMNS + ("trigger_locator_id",),
        "composite_fks": (
            (
                ("rule_set_id", "rule_set_revision", "rule_component_id"),
                (
                    "rule_components.rule_set_id",
                    "rule_components.rule_set_revision",
                    "rule_components.rule_component_id",
                ),
            ),
        ),
        "check": ("ck_action_requests_evidence_lineage", _REVIEW_LINEAGE_CHECK_SQL),
        "indexes": (
            ("ix_action_requests_review_episode_id", ("review_episode_id",)),
            ("ix_action_requests_state", ("state",)),
        ),
    },
    "agent_calls": {
        "pk": "agent_call_id",
        "columns": (
            ("agent_call_id", String(128), False, None),
            ("node", String(48), False, None),
            ("output_kind", String(32), False, None),
            ("write_scope", String(32), False, None),
            ("prompt_version_id", String(128), False, "prompt_versions.prompt_version_id"),
            ("model_config_id", String(128), False, "model_configs.model_config_id"),
            ("idempotency_key", String(256), False, None),
            ("attempt", Integer(), False, None),
            ("outcome", String(32), False, None),
            ("started_at", DateTime(), False, None),
            ("finished_at", DateTime(), False, None),
            ("project_id", String(128), False, "projects.project_id"),
            (
                "protocol_version_id",
                String(128),
                False,
                "protocol_document_versions.protocol_version_id",
            ),
            ("rule_set_id", String(128), True, None),
            ("rule_set_revision", Integer(), True, None),
            ("subject_id", String(128), True, "subjects.subject_id"),
            ("review_episode_id", String(128), True, "review_episodes.review_episode_id"),
            ("review_run_id", String(128), True, "review_runs.review_run_id"),
            ("evidence_snapshot_id", String(128), True, "evidence_snapshots.evidence_snapshot_id"),
            ("evidence_snapshot_v2_id", String(128), True, "evidence_snapshots_v2.evidence_snapshot_id"),
            (
                "complete_processing_revision_id",
                String(128),
                True,
                "evidence_processing_revisions.evidence_processing_revision_id",
            ),
            ("input_tokens", Integer(), True, None),
            ("output_tokens", Integer(), True, None),
            ("estimated_cost", Float(), True, None),
            ("payload_json", Text(), False, None),
            ("payload_sha256", String(_PAYLOAD_SHA_LEN), False, None),
            ("created_at", DateTime(), False, None),
        ),
        "v2_only": _V2_LINEAGE_COLUMNS,
        "composite_fks": (),
        "check": ("ck_agent_calls_evidence_lineage", _AGENT_CALL_LINEAGE_CHECK_SQL),
        "indexes": (
            ("ix_agent_calls_project_id", ("project_id",)),
            ("ix_agent_calls_idempotency_key", ("idempotency_key",)),
        ),
    },
}

_CHAIN_TABLE_NAMES = tuple(_TABLE_SPECS)

#: 0023 新建的 V2 谱系关联表：``(owner 列, owner 外键, ref 列, ref 外键)``。
_LINK_TABLE_SPECS: dict[str, tuple[str, str, str, str]] = {
    "assessment_candidate_facts_v2": (
        "assessment_candidate_id",
        "assessment_candidates.assessment_candidate_id",
        "fact_id",
        "clinical_facts_v2.fact_id",
    ),
    "assessment_candidate_locators": (
        "assessment_candidate_id",
        "assessment_candidates.assessment_candidate_id",
        "locator_id",
        "evidence_locator_artifacts.locator_id",
    ),
    "final_assessment_facts_v2": (
        "assessment_id",
        "final_assessments.assessment_id",
        "fact_id",
        "clinical_facts_v2.fact_id",
    ),
    "final_assessment_locators": (
        "assessment_id",
        "final_assessments.assessment_id",
        "locator_id",
        "evidence_locator_artifacts.locator_id",
    ),
    "action_transition_locators": (
        "transition_id",
        "action_transitions.transition_id",
        "locator_id",
        "evidence_locator_artifacts.locator_id",
    ),
}

_LINK_TABLE_NAMES = tuple(_LINK_TABLE_SPECS)

#: 降级顺序：先删关联表，再从子表向父表重建链表。
_DOWNGRADE_CHAIN_ORDER = (
    "agent_calls",
    "action_requests",
    "final_assessments",
    "assessment_candidates",
    "review_runs",
)


def _raw_dbapi(bind):
    """DBAPI 层连接：SQLAlchemy 的 autobegin 会让事务内 PRAGMA foreign_keys
    变成 no-op，因此 FK 开关与完整性检查必须在 raw 连接上执行（同 0010）。"""
    return bind.connection.driver_connection


def _disable_foreign_keys(bind) -> None:
    raw = _raw_dbapi(bind)
    if raw.in_transaction:
        raw.commit()
    raw.execute("PRAGMA foreign_keys = OFF")
    if raw.execute("PRAGMA foreign_keys").fetchone()[0] != 0:
        raise RuntimeError("无法切换迁移所需的外键状态，禁止重建审核表")


def _restore_foreign_keys(bind) -> None:
    raw = _raw_dbapi(bind)
    if raw.in_transaction:
        raw.commit()
    raw.execute("PRAGMA foreign_keys = ON")
    if raw.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise RuntimeError("迁移后外键约束未恢复，禁止继续启动")


def _foreign_key_check_ok(bind) -> bool:
    raw = _raw_dbapi(bind)
    try:
        rows = raw.execute("PRAGMA foreign_key_check").fetchall()
    except Exception:  # noqa: BLE001 - 检查失败按不通过处理，由迁移管理器兜底
        return False
    return not rows


def _register_parent_stubs(target: MetaData) -> None:
    """注册外键解析所需的父表轻量 stub（不重建父表）。"""
    Table("projects", target, Column("project_id", String(128), primary_key=True))
    Table("review_context_snapshots", target, Column("context_id", String(128), primary_key=True))
    Table("subjects", target, Column("subject_id", String(128), primary_key=True))
    Table(
        "review_episodes",
        target,
        Column("review_episode_id", String(128), primary_key=True),
    )
    Table(
        "protocol_document_versions",
        target,
        Column("protocol_version_id", String(128), primary_key=True),
    )
    Table(
        "rule_components",
        target,
        Column("rule_set_id", String(128), primary_key=True),
        Column("rule_set_revision", Integer(), primary_key=True),
        Column("rule_component_id", String(128), primary_key=True),
    )
    Table("gate_results", target, Column("gate_result_id", String(128), primary_key=True))
    Table(
        "evidence_snapshots",
        target,
        Column("evidence_snapshot_id", String(128), primary_key=True),
    )
    Table(
        "evidence_snapshots_v2",
        target,
        Column("evidence_snapshot_id", String(128), primary_key=True),
    )
    Table(
        "evidence_processing_revisions",
        target,
        Column("evidence_processing_revision_id", String(128), primary_key=True),
    )
    Table(
        "evidence_spans", target, Column("evidence_span_id", String(128), primary_key=True)
    )
    Table(
        "evidence_locator_artifacts",
        target,
        Column("locator_id", String(128), primary_key=True),
    )
    Table("clinical_facts_v2", target, Column("fact_id", String(128), primary_key=True))
    Table("review_runs", target, Column("review_run_id", String(128), primary_key=True))
    Table(
        "assessment_candidates",
        target,
        Column("assessment_candidate_id", String(128), primary_key=True),
    )
    Table(
        "final_assessments", target, Column("assessment_id", String(128), primary_key=True)
    )
    Table("agent_calls", target, Column("agent_call_id", String(128), primary_key=True))
    Table(
        "action_transitions",
        target,
        Column("transition_id", String(128), primary_key=True),
    )
    Table(
        "prompt_versions", target, Column("prompt_version_id", String(128), primary_key=True)
    )
    Table(
        "model_configs", target, Column("model_config_id", String(128), primary_key=True)
    )


def _build_chain_table(
    name: str, target: MetaData, *, with_v2: bool, table_name: str | None = None
) -> Table:
    """构造一张链表临时表（``with_v2=True`` 为 0023 形状，False 为 0022 形状）。"""
    spec = _TABLE_SPECS[name]
    v2_only = spec["v2_only"]
    physical_name = table_name or name
    columns: list[Column] = []
    constraints: list = []
    for column_name, column_type, nullable, fk_target in spec["columns"]:
        if column_name in v2_only and not with_v2:
            continue
        is_nullable = with_v2 if nullable == _LINEAGE else bool(nullable)
        columns.append(
            Column(
                column_name,
                column_type,
                nullable=is_nullable,
                primary_key=column_name == spec["pk"],
            )
        )
        if fk_target is not None:
            constraints.append(ForeignKeyConstraint([column_name], [fk_target]))
    for fk_columns, fk_referred in spec["composite_fks"]:
        constraints.append(
            ForeignKeyConstraint(list(fk_columns), list(fk_referred))
        )
    if with_v2:
        check_name, check_sql = spec["check"]
        constraints.append(CheckConstraint(check_sql, name=check_name))
        if name == "review_runs":
            constraints.append(CheckConstraint(
                "(evidence_snapshot_v2_id IS NULL AND context_id IS NULL) OR "
                "(evidence_snapshot_v2_id IS NOT NULL AND context_id IS NOT NULL)",
                name="ck_review_runs_context_lineage",
            ))
        if name == "action_requests":
            constraints.append(CheckConstraint(
                "(evidence_snapshot_v2_id IS NULL AND trigger_locator_id IS NULL) OR "
                "(evidence_snapshot_v2_id IS NOT NULL AND trigger_evidence_span_id IS NULL)",
                name="ck_action_requests_trigger_lineage",
            ))
    table = Table(physical_name, target, *columns, *constraints)
    for index_name, index_columns in spec["indexes"]:
        Index(index_name, *[table.c[column] for column in index_columns])
    return table


def _build_link_table(name: str, target: MetaData) -> Table:
    """构造一张 V2 谱系有序关联表（形状与 ORM ``_assoc_table`` 一致）。"""
    owner_column, owner_ref, ref_column, ref_ref = _LINK_TABLE_SPECS[name]
    return Table(
        name,
        target,
        Column(owner_column, String(128), nullable=False),
        Column(ref_column, String(128), nullable=False),
        Column("position", Integer(), nullable=False),
        UniqueConstraint(owner_column, ref_column),
        UniqueConstraint(owner_column, "position"),
        ForeignKeyConstraint([owner_column], [owner_ref]),
        ForeignKeyConstraint([ref_column], [ref_ref]),
    )


def _rebuild_chain_table(name: str, *, with_v2: bool) -> None:
    """建新表 -> 拷贝（新增列写 NULL）-> 删旧表 -> 改名；子表行与旧 payload 不变。"""
    bind = op.get_bind()
    spec = _TABLE_SPECS[name]
    legacy_columns = {
        column_name
        for column_name, _type, _nullable, _fk in spec["columns"]
        if column_name not in spec["v2_only"]
    }
    _disable_foreign_keys(bind)
    try:
        for index_name, _columns in spec["indexes"]:
            op.execute(f"DROP INDEX IF EXISTS {index_name}")
        temp_name = f"{name}_0023_new" if with_v2 else f"{name}_0022_legacy"
        target = MetaData(naming_convention=_NAMING_CONVENTION)
        _register_parent_stubs(target)
        new_table = _build_chain_table(
            name, target, with_v2=with_v2, table_name=temp_name
        )
        new_table.create(bind=bind)
        destination_columns = [column.name for column in new_table.columns]
        source_expressions = [
            column_name if column_name in legacy_columns else "NULL"
            for column_name in destination_columns
        ]
        op.execute(
            f"INSERT INTO {temp_name} ({', '.join(destination_columns)}) "
            f"SELECT {', '.join(source_expressions)} FROM {name}"
        )
        op.execute(f"DROP TABLE {name}")
        op.execute(f"ALTER TABLE {temp_name} RENAME TO {name}")
    finally:
        _restore_foreign_keys(bind)
    if not _foreign_key_check_ok(bind):
        raise RuntimeError(
            f"迁移重建 {name} 后外键完整性检查失败；子表行与外键引用未完整保留，"
            "禁止继续迁移"
        )


def upgrade() -> None:
    # 1) 五张正式审核链表：legacy 列原义保留，新增 V2 谱系列与 CHECK。
    for table_name in _CHAIN_TABLE_NAMES:
        _rebuild_chain_table(table_name, with_v2=True)

    # 2) V2 谱系有序关联表（真实父表外键，不使用无外键的 kind+id）。
    bind = op.get_bind()
    target = MetaData(naming_convention=_NAMING_CONVENTION)
    _register_parent_stubs(target)
    for table_name in _LINK_TABLE_NAMES:
        _build_link_table(table_name, target).create(bind=bind)

    if not _foreign_key_check_ok(bind):
        raise RuntimeError(
            "0023 迁移后外键完整性检查失败，禁止继续迁移"
        )


def _downgrade_guard_sql(table_name: str) -> str:
    """0022 形状无法承载的列值条件：任一成立即有损，禁止降级。

    ``agent_calls`` 的协议-only 调用三列全空，是 0022 形状下本来就合法的行，
    不视为 V2 历史；其余表在 0022 形状要求 legacy ``evidence_snapshot_id`` 非空。
    """
    conditions = [
        f"{column_name} IS NOT NULL"
        for column_name in _TABLE_SPECS[table_name]["v2_only"]
    ]
    if table_name != "agent_calls":
        conditions.append("evidence_snapshot_id IS NULL")
    return " OR ".join(conditions)


def _has_v2_history(bind) -> bool:
    """是否存在任何 V2 谱系正式数据；有则禁止有损降级。

    除链表的 0023-only 列值外，任一 0023 关联表有行同样属于 V2 历史。
    """
    for table_name in _CHAIN_TABLE_NAMES:
        condition = _downgrade_guard_sql(table_name)
        if bind.exec_driver_sql(
            f"SELECT COUNT(*) FROM {table_name} WHERE {condition}"
        ).scalar_one():
            return True
    for table_name in _LINK_TABLE_NAMES:
        if bind.exec_driver_sql(f"SELECT COUNT(*) FROM {table_name}").scalar_one():
            return True
    return False


def downgrade() -> None:
    bind = op.get_bind()
    if _has_v2_history(bind):
        raise RuntimeError(
            "0023 已存在 V2 谱系正式审核数据（V2 快照/完整处理修订指针、"
            "缺少 legacy 快照或 V2 事实/定位关联），拒绝有损降级以避免丢失"
            "不可变历史"
        )

    for table_name in _LINK_TABLE_NAMES:
        op.drop_table(table_name)

    for table_name in _DOWNGRADE_CHAIN_ORDER:
        _rebuild_chain_table(table_name, with_v2=False)
