"""Phase 5 Slice 5.7：人工临床事实修订不可变追加写（修订 lineage 独立）。

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-23

新增 ``fact_corrections`` 追加写表，保存有理由的事实/事件/暴露修订：

- 目标 ``(target_kind, target_id, target_stable_identity, target_revision)`` 与
  新实体 ``(new_entity_id, new_stable_identity, new_revision)`` 的独立谱系；
  同稳定身份时新 ``revision = target_revision + 1``，新旧稳定不同时新身份可从 1 新起；
  分支由 ``UNIQUE(target_id)`` 与 ``UNIQUE(new_entity_id)`` 阻止（单出边/单入边）。
- 旧/新语义快照为仅含用户可审阅字段的规范 JSON（经 ``app.domain.publication`` 规范化），
  不含 ID/run/gate/revision/时间戳；仓储层校验快照与实际持久化合约一致。
- 类型化外键 ``target_fact/event/exposure_id`` 与 ``new_fact/event/exposure_id``
  按 ``target_kind`` 精确绑定，防止悬挂指向。
- 影响范围沿显式 locator / 文档版本 / 实体引用 / 冲突组 / FactRuleLink / Profile revision
  反向索引传播，无法证明时 ``impact_scope_kind='node'`` 并给出回退原因；
  局部范围必须保留 ``affected_conflict_group_ids``，节点级回退允许受影响集合为空；
- ``idempotency_key`` 全局唯一。

本迁移只新增表，不回写 Phase 2/3 占位表与既有 v2 表；降级仅空表绿地库允许。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PAYLOAD_SHA_LEN = 64


def upgrade() -> None:
    op.create_table(
        "fact_corrections",
        sa.Column("correction_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("review_episode_id", sa.String(length=128), nullable=False),
        sa.Column("episode_revision", sa.Integer(), nullable=False),
        sa.Column("protocol_version_id", sa.String(length=128), nullable=False),
        sa.Column("rule_set_id", sa.String(length=128), nullable=False),
        sa.Column("rule_set_revision", sa.Integer(), nullable=False),
        sa.Column("evidence_snapshot_v2_id", sa.String(length=128), nullable=False),
        sa.Column("complete_processing_revision_id", sa.String(length=128), nullable=False),
        sa.Column("target_kind", sa.String(length=16), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("target_stable_identity", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("new_stable_identity", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("target_revision", sa.Integer(), nullable=False),
        sa.Column("new_entity_id", sa.String(length=128), nullable=False),
        sa.Column("new_revision", sa.Integer(), nullable=False),
        sa.Column("target_fact_id", sa.String(length=128), nullable=True),
        sa.Column("target_event_id", sa.String(length=128), nullable=True),
        sa.Column("target_exposure_id", sa.String(length=128), nullable=True),
        sa.Column("new_fact_id", sa.String(length=128), nullable=True),
        sa.Column("new_event_id", sa.String(length=128), nullable=True),
        sa.Column("new_exposure_id", sa.String(length=128), nullable=True),
        sa.Column("old_snapshot_json", sa.Text(), nullable=False),
        sa.Column("old_snapshot_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("new_snapshot_json", sa.Text(), nullable=False),
        sa.Column("new_snapshot_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("locator_ids_json", sa.JSON(), nullable=False),
        sa.Column("operator_id", sa.String(length=128), nullable=False),
        sa.Column("corrected_at", sa.DateTime(), nullable=False),
        sa.Column("impact_scope_kind", sa.String(length=16), nullable=False),
        sa.Column("impact_fallback_reason", sa.Text(), nullable=True),
        sa.Column("affected_locator_ids_json", sa.JSON(), nullable=False),
        sa.Column("affected_document_ids_json", sa.JSON(), nullable=False),
        sa.Column("affected_fact_ids_json", sa.JSON(), nullable=False),
        sa.Column("affected_event_ids_json", sa.JSON(), nullable=False),
        sa.Column("affected_exposure_ids_json", sa.JSON(), nullable=False),
        sa.Column("affected_conflict_group_ids_json", sa.JSON(), nullable=False),
        sa.Column("affected_rule_link_ids_json", sa.JSON(), nullable=False),
        sa.Column("affected_expectation_ids_json", sa.JSON(), nullable=False),
        sa.Column("affected_profile_revision_ids_json", sa.JSON(), nullable=False),
        sa.Column("impact_scope_json", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], name="fk_fcorr_project_id"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"], name="fk_fcorr_subject_id"),
        sa.ForeignKeyConstraint(["review_episode_id"], ["review_episodes.review_episode_id"], name="fk_fcorr_review_episode_id"),
        sa.ForeignKeyConstraint(["protocol_version_id"], ["protocol_document_versions.protocol_version_id"], name="fk_fcorr_protocol_version_id"),
        sa.ForeignKeyConstraint(["rule_set_id", "rule_set_revision"], ["rule_sets.rule_set_id", "rule_sets.revision"], name="fk_fcorr_rule_set"),
        sa.ForeignKeyConstraint(["evidence_snapshot_v2_id"], ["evidence_snapshots_v2.evidence_snapshot_id"], name="fk_fcorr_evidence_snapshot_v2_id"),
        sa.ForeignKeyConstraint(["complete_processing_revision_id"], ["evidence_processing_revisions.evidence_processing_revision_id"], name="fk_fcorr_complete_processing_revision_id"),
        sa.ForeignKeyConstraint(["target_fact_id"], ["clinical_facts_v2.fact_id"], name="fk_fcorr_target_fact_id"),
        sa.ForeignKeyConstraint(["target_event_id"], ["clinical_events_v2.event_id"], name="fk_fcorr_target_event_id"),
        sa.ForeignKeyConstraint(["target_exposure_id"], ["medication_exposures_v2.exposure_id"], name="fk_fcorr_target_exposure_id"),
        sa.ForeignKeyConstraint(["new_fact_id"], ["clinical_facts_v2.fact_id"], name="fk_fcorr_new_fact_id"),
        sa.ForeignKeyConstraint(["new_event_id"], ["clinical_events_v2.event_id"], name="fk_fcorr_new_event_id"),
        sa.ForeignKeyConstraint(["new_exposure_id"], ["medication_exposures_v2.exposure_id"], name="fk_fcorr_new_exposure_id"),
        sa.PrimaryKeyConstraint("correction_id", name="pk_fact_corrections"),
        sa.UniqueConstraint("idempotency_key", name="uq_fcorr_idempotency_key"),
        sa.UniqueConstraint("target_id", name="uq_fcorr_target_id"),
        sa.UniqueConstraint("new_entity_id", name="uq_fcorr_new_entity_id"),
        sa.CheckConstraint("target_kind IN ('fact', 'event', 'exposure')", name="ck_fcorr_target_kind"),
        sa.CheckConstraint("impact_scope_kind IN ('local', 'node')", name="ck_fcorr_scope_kind"),
        sa.CheckConstraint("target_revision >= 1 AND new_revision >= 1", name="ck_fcorr_revision_ge"),
        sa.CheckConstraint("target_id != new_entity_id", name="ck_fcorr_target_new_distinct"),
        sa.CheckConstraint("(target_kind = 'fact' AND target_fact_id = target_id AND target_event_id IS NULL AND target_exposure_id IS NULL) OR (target_kind = 'event' AND target_event_id = target_id AND target_fact_id IS NULL AND target_exposure_id IS NULL) OR (target_kind = 'exposure' AND target_exposure_id = target_id AND target_fact_id IS NULL AND target_event_id IS NULL)", name="ck_fcorr_target_typed"),
        sa.CheckConstraint("(target_kind = 'fact' AND new_fact_id = new_entity_id AND new_event_id IS NULL AND new_exposure_id IS NULL) OR (target_kind = 'event' AND new_event_id = new_entity_id AND new_fact_id IS NULL AND new_exposure_id IS NULL) OR (target_kind = 'exposure' AND new_exposure_id = new_entity_id AND new_fact_id IS NULL AND new_event_id IS NULL)", name="ck_fcorr_new_typed"),
    )
    op.create_index("ix_fcorr_review_episode_id", "fact_corrections", ["review_episode_id"], unique=False)
    op.create_index("ix_fcorr_target_stable_identity", "fact_corrections", ["target_stable_identity"], unique=False)
    op.create_index("ix_fcorr_new_stable_identity", "fact_corrections", ["new_stable_identity"], unique=False)
    op.create_index("ix_fcorr_target_id", "fact_corrections", ["target_id"], unique=False)
    op.create_index("ix_fcorr_new_entity_id", "fact_corrections", ["new_entity_id"], unique=False)
    op.create_index("ix_fcorr_idempotency_key", "fact_corrections", ["idempotency_key"], unique=False)
    op.create_index("ix_fcorr_corrected_at", "fact_corrections", ["corrected_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    count = bind.exec_driver_sql("SELECT COUNT(*) FROM fact_corrections").scalar_one()
    if count:
        raise RuntimeError("0017 fact_corrections 已有不可变历史，拒绝有损降级")
    op.drop_index("ix_fcorr_corrected_at", table_name="fact_corrections")
    op.drop_index("ix_fcorr_idempotency_key", table_name="fact_corrections")
    op.drop_index("ix_fcorr_new_entity_id", table_name="fact_corrections")
    op.drop_index("ix_fcorr_target_id", table_name="fact_corrections")
    op.drop_index("ix_fcorr_new_stable_identity", table_name="fact_corrections")
    op.drop_index("ix_fcorr_target_stable_identity", table_name="fact_corrections")
    op.drop_index("ix_fcorr_review_episode_id", table_name="fact_corrections")
    op.drop_table("fact_corrections")
