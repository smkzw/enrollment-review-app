"""Phase 5 临床事实与 Patient Profile（Slice 5.1）：v2 写路径持久化基座

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-22

本迁移只新增 Phase 5 v2 新写表，不回写 0001-0012 既有表；Phase 2/3 占位事实表
（``clinical_facts`` / ``conflict_groups`` / ``evidence_normalization_candidates`` /
``evidence_expectations`` / ``patient_profiles``）保持只读回归锚点，Phase 5 仓储
不读取它们。表名/列/约束以 ``app/storage/facts_models.py``（worker_02）为权威，
由 ``verify_schema_matches_metadata`` 在迁移后逐表交叉核对。降级按依赖逆序删除，
且只在「空绿地库」允许：任一表有行即视为不可变历史已占用，必须拒绝有损降级
（由管理器从迁移前备份恢复）。

新增表（设计书 §2.2）：

- ``fact_normalization_runs``          规范化运行（冻结不可变权威元组 + 幂等键 +
                                       PromptVersion/ModelConfig + 输入范围哈希；
                                       不伪造 Phase 6 ReviewRun）；
- ``fact_normalization_calls``         一次规范化调用（显式页清单；超长文档按连续
                                       页组切片）；
- ``fact_normalization_candidates``    候选完整合同（与发布表物理分离）；
- ``fact_gate_results``                逐候选门禁结果（设计书 §4.2 九步顺序）；
- ``clinical_facts_v2`` / ``clinical_events_v2`` / ``medication_exposures_v2`` /
  ``clinical_conflict_groups_v2``      发布接受的临床事实/事件/用药暴露/冲突组；
- ``fact_evidence_locator_links``      发布实体/期望到 Phase 4
                                       ``EvidenceLocatorArtifact`` 的不可变引用
                                       （``entity_kind`` 判别 + locator 外键强约束）；
- ``event_fact_links`` / ``exposure_fact_links`` / ``clinical_conflict_members_v2``
                                       事件/暴露/冲突组到发布事实的有序引用；
- ``fact_rule_links_v2``               事实到已发布 RuleComponent/EvidenceRequirement
                                       的双向索引（精确身份匹配，可完全重建）；
- ``evidence_expectations_v2``         受试者级期望覆盖投影（五类状态 + 缺口类型）；
- ``patient_profile_revisions_v2``     不可变 Profile revision（绑定权威元组、状态与
                                       首屏突出集合）。

权威元组（project/subject/review_episode/episode_revision/protocol_version/
rule_set/rule_set_revision/evidence_snapshot_v2/complete_processing_revision）
在每个发布实体表与运行/期望/Profile 表上以规范化列冻结；``episode_revision`` 与
``complete_processing_revision_id`` 一起冻结运行时审核节点指针，指针变化时结果
记为陈旧并拒绝发布（仓储层校验，worker_03）。迁移后 ``PRAGMA foreign_key_check``
必须无违规。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PAYLOAD_SHA_LEN = 64

#: 降级时按依赖逆序检查是否被正式数据占用。
_V2_TABLES = (
    "patient_profile_revisions_v2",
    "fact_evidence_locator_links",
    "evidence_expectations_v2",
    "fact_rule_links_v2",
    "clinical_conflict_members_v2",
    "exposure_fact_links",
    "event_fact_links",
    "clinical_conflict_groups_v2",
    "medication_exposures_v2",
    "clinical_events_v2",
    "clinical_facts_v2",
    "fact_gate_results",
    "fact_normalization_candidates",
    "fact_normalization_calls",
    "fact_normalization_runs",
)


def _authority_columns() -> list[sa.Column]:
    """不可变权威元组规范化列（设计书 §2.1），供各发布表复用。"""
    return [
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("review_episode_id", sa.String(length=128), nullable=False),
        sa.Column("episode_revision", sa.Integer(), nullable=False),
        sa.Column("protocol_version_id", sa.String(length=128), nullable=False),
        sa.Column("rule_set_id", sa.String(length=128), nullable=False),
        sa.Column("rule_set_revision", sa.Integer(), nullable=False),
        sa.Column("evidence_snapshot_v2_id", sa.String(length=128), nullable=False),
        sa.Column(
            "complete_processing_revision_id", sa.String(length=128), nullable=False
        ),
    ]


def _authority_fks(table: str) -> list[sa.ForeignKeyConstraint]:
    """权威元组外键约束；与 ORM ``FactAuthorityColumns`` 完全一致。"""
    return [
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"],
            name=f"fk_{table}_projects_project_id",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.subject_id"],
            name=f"fk_{table}_subjects_subject_id",
        ),
        sa.ForeignKeyConstraint(
            ["review_episode_id"], ["review_episodes.review_episode_id"],
            name=f"fk_{table}_review_episodes_review_episode_id",
        ),
        sa.ForeignKeyConstraint(
            ["protocol_version_id"], ["protocol_document_versions.protocol_version_id"],
            name=f"fk_{table}_protocol_document_versions_protocol_version_id",
        ),
        sa.ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision"],
            ["rule_sets.rule_set_id", "rule_sets.revision"],
            name=f"fk_{table}_rule_sets_rule_set",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_snapshot_v2_id"], ["evidence_snapshots_v2.evidence_snapshot_id"],
            name=f"fk_{table}_evidence_snapshots_v2_evidence_snapshot_v2_id",
        ),
        sa.ForeignKeyConstraint(
            ["complete_processing_revision_id"],
            ["evidence_processing_revisions.evidence_processing_revision_id"],
            name=f"fk_{table}_evidence_processing_revisions_complete_processing_revision_id",
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "fact_normalization_runs",
        sa.Column("run_id", sa.String(length=128), nullable=False),
        *_authority_columns(),
        sa.Column("idempotency_key", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("prompt_version_id", sa.String(length=128), nullable=False),
        sa.Column("model_config_id", sa.String(length=128), nullable=False),
        sa.Column("input_scope_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        *_authority_fks("fact_normalization_runs"),
        sa.ForeignKeyConstraint(
            ["prompt_version_id"], ["prompt_versions.prompt_version_id"],
            name="fk_fact_normalization_runs_prompt_versions_prompt_version_id",
        ),
        sa.ForeignKeyConstraint(
            ["model_config_id"], ["model_configs.model_config_id"],
            name="fk_fact_normalization_runs_model_configs_model_config_id",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.job_id"],
            name="fk_fact_normalization_runs_jobs_job_id",
        ),
        sa.PrimaryKeyConstraint("run_id", name="pk_fact_normalization_runs"),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_fact_normalization_runs_idempotency_key"
        ),
    )
    op.create_index(
        "ix_fnr_review_episode_id", "fact_normalization_runs", ["review_episode_id"]
    )
    op.create_index(
        "ix_fnr_complete_processing_revision_id",
        "fact_normalization_runs",
        ["complete_processing_revision_id"],
    )
    op.create_index("ix_fnr_status", "fact_normalization_runs", ["status"])
    op.create_table(
        "fact_normalization_calls",
        sa.Column("call_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("logical_document_id", sa.String(length=128), nullable=False),
        sa.Column("page_numbers_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("input_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("raw_output_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["fact_normalization_runs.run_id"],
            name="fk_fact_normalization_calls_fact_normalization_runs_run_id",
        ),
        sa.PrimaryKeyConstraint("call_id", name="pk_fact_normalization_calls"),
        sa.UniqueConstraint("call_id", "run_id", name="uq_fnc_call_run"),
    )
    op.create_index("ix_fnc_run_id", "fact_normalization_calls", ["run_id"])
    op.create_index(
        "ix_fnc_logical_document_id", "fact_normalization_calls", ["logical_document_id"]
    )
    op.create_table(
        "fact_normalization_candidates",
        sa.Column("candidate_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("call_id", sa.String(length=128), nullable=False),
        sa.Column("candidate_kind", sa.String(length=16), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["fact_normalization_runs.run_id"],
            name="fk_fact_normalization_candidates_fact_normalization_runs_run_id",
        ),
        sa.ForeignKeyConstraint(
            ["call_id"], ["fact_normalization_calls.call_id"],
            name="fk_fact_normalization_candidates_fact_normalization_calls_call_id",
        ),
        sa.ForeignKeyConstraint(
            ["call_id", "run_id"],
            ["fact_normalization_calls.call_id", "fact_normalization_calls.run_id"],
            name="fk_fncandidate_call_run",
        ),
        sa.PrimaryKeyConstraint(
            "candidate_id", name="pk_fact_normalization_candidates"
        ),
        sa.UniqueConstraint(
            "candidate_id", "call_id", "run_id", name="uq_fncandidate_id_call_run"
        ),
        sa.CheckConstraint(
            "candidate_kind IN ('fact', 'event', 'exposure')",
            name="ck_fncandidate_kind",
        ),
    )
    op.create_index(
        "ix_fncandidate_run_id", "fact_normalization_candidates", ["run_id"]
    )
    op.create_index(
        "ix_fncandidate_call_id", "fact_normalization_candidates", ["call_id"]
    )
    op.create_table(
        "fact_gate_results",
        sa.Column("gate_result_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("call_id", sa.String(length=128), nullable=False),
        sa.Column("candidate_id", sa.String(length=128), nullable=False),
        sa.Column("gate", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["fact_normalization_runs.run_id"],
            name="fk_fact_gate_results_fact_normalization_runs_run_id",
        ),
        sa.ForeignKeyConstraint(
            ["call_id"], ["fact_normalization_calls.call_id"],
            name="fk_fact_gate_results_fact_normalization_calls_call_id",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["fact_normalization_candidates.candidate_id"],
            name="fk_fact_gate_results_fact_normalization_candidates_candidate_id",
        ),
        sa.ForeignKeyConstraint(
            ["call_id", "run_id"],
            ["fact_normalization_calls.call_id", "fact_normalization_calls.run_id"],
            name="fk_fgr_call_run",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id", "call_id", "run_id"],
            [
                "fact_normalization_candidates.candidate_id",
                "fact_normalization_candidates.call_id",
                "fact_normalization_candidates.run_id",
            ],
            name="fk_fgr_candidate_call_run",
        ),
        sa.PrimaryKeyConstraint("gate_result_id", name="pk_fact_gate_results"),
        sa.UniqueConstraint("candidate_id", "gate", name="uq_fgr_candidate_gate"),
    )
    op.create_index("ix_fgr_run_id", "fact_gate_results", ["run_id"])
    op.create_index("ix_fgr_call_id", "fact_gate_results", ["call_id"])
    op.create_index("ix_fgr_candidate_id", "fact_gate_results", ["candidate_id"])
    op.create_table(
        "clinical_facts_v2",
        sa.Column("fact_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("gate_id", sa.String(length=128), nullable=False),
        *_authority_columns(),
        sa.Column("fact_type", sa.String(length=128), nullable=False),
        sa.Column("polarity", sa.String(length=16), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("source_strength", sa.String(length=32), nullable=False),
        sa.Column("date_precision", sa.String(length=16), nullable=True),
        sa.Column("date_lower_bound", sa.Date(), nullable=True),
        sa.Column("date_upper_bound", sa.Date(), nullable=True),
        sa.Column("date_source_text", sa.Text(), nullable=True),
        sa.Column("record_time", sa.DateTime(), nullable=True),
        sa.Column("assertion_object", sa.String(length=256), nullable=True),
        sa.Column("assertion_text", sa.Text(), nullable=True),
        sa.Column("assertion_locator_id", sa.String(length=128), nullable=True),
        sa.Column("assertion_source_text_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=True),
        sa.Column("stable_identity", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["fact_normalization_runs.run_id"],
            name="fk_clinical_facts_v2_fact_normalization_runs_run_id",
        ),
        sa.ForeignKeyConstraint(
            ["gate_id"], ["fact_gate_results.gate_result_id"],
            name="fk_clinical_facts_v2_fact_gate_results_gate_id",
        ),
        *_authority_fks("clinical_facts_v2"),
        sa.ForeignKeyConstraint(
            ["assertion_locator_id"], ["evidence_locator_artifacts.locator_id"],
            name="fk_clinical_facts_v2_evidence_locator_artifacts_assertion_locator_id",
        ),
        sa.PrimaryKeyConstraint("fact_id", name="pk_clinical_facts_v2"),
        sa.UniqueConstraint(
            "stable_identity", "revision", name="uq_cfv2_stable_identity_revision"
        ),
    )
    op.create_index(
        "ix_cfv2_review_episode_id", "clinical_facts_v2", ["review_episode_id"]
    )
    op.create_index(
        "ix_cfv2_subject_fact_type", "clinical_facts_v2", ["subject_id", "fact_type"]
    )
    op.create_table(
        "clinical_events_v2",
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("gate_id", sa.String(length=128), nullable=False),
        *_authority_columns(),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("start_precision", sa.String(length=16), nullable=True),
        sa.Column("start_lower_bound", sa.Date(), nullable=True),
        sa.Column("start_upper_bound", sa.Date(), nullable=True),
        sa.Column("start_source_text", sa.Text(), nullable=True),
        sa.Column("end_precision", sa.String(length=16), nullable=True),
        sa.Column("end_lower_bound", sa.Date(), nullable=True),
        sa.Column("end_upper_bound", sa.Date(), nullable=True),
        sa.Column("end_source_text", sa.Text(), nullable=True),
        sa.Column("duration_status", sa.String(length=16), nullable=False),
        sa.Column("record_time", sa.DateTime(), nullable=True),
        sa.Column("source_strength", sa.String(length=32), nullable=False),
        sa.Column("stable_identity", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["fact_normalization_runs.run_id"],
            name="fk_clinical_events_v2_fact_normalization_runs_run_id",
        ),
        sa.ForeignKeyConstraint(
            ["gate_id"], ["fact_gate_results.gate_result_id"],
            name="fk_clinical_events_v2_fact_gate_results_gate_id",
        ),
        *_authority_fks("clinical_events_v2"),
        sa.PrimaryKeyConstraint("event_id", name="pk_clinical_events_v2"),
        sa.UniqueConstraint(
            "stable_identity", "revision", name="uq_cev2_stable_identity_revision"
        ),
    )
    op.create_index(
        "ix_cev2_review_episode_id", "clinical_events_v2", ["review_episode_id"]
    )
    op.create_index("ix_cev2_event_type", "clinical_events_v2", ["event_type"])
    op.create_table(
        "medication_exposures_v2",
        sa.Column("exposure_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("gate_id", sa.String(length=128), nullable=False),
        *_authority_columns(),
        sa.Column("medication_name", sa.String(length=256), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("indication", sa.Text(), nullable=True),
        sa.Column("dose", sa.String(length=128), nullable=True),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("frequency", sa.String(length=128), nullable=True),
        sa.Column("route", sa.String(length=128), nullable=True),
        sa.Column("start_precision", sa.String(length=16), nullable=True),
        sa.Column("start_lower_bound", sa.Date(), nullable=True),
        sa.Column("start_upper_bound", sa.Date(), nullable=True),
        sa.Column("start_source_text", sa.Text(), nullable=True),
        sa.Column("end_precision", sa.String(length=16), nullable=True),
        sa.Column("end_lower_bound", sa.Date(), nullable=True),
        sa.Column("end_upper_bound", sa.Date(), nullable=True),
        sa.Column("end_source_text", sa.Text(), nullable=True),
        sa.Column("duration_status", sa.String(length=16), nullable=False),
        sa.Column("record_time", sa.DateTime(), nullable=True),
        sa.Column("source_strength", sa.String(length=32), nullable=False),
        sa.Column("stable_identity", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["fact_normalization_runs.run_id"],
            name="fk_medication_exposures_v2_fact_normalization_runs_run_id",
        ),
        sa.ForeignKeyConstraint(
            ["gate_id"], ["fact_gate_results.gate_result_id"],
            name="fk_medication_exposures_v2_fact_gate_results_gate_id",
        ),
        *_authority_fks("medication_exposures_v2"),
        sa.PrimaryKeyConstraint("exposure_id", name="pk_medication_exposures_v2"),
        sa.UniqueConstraint(
            "stable_identity", "revision", name="uq_mev2_stable_identity_revision"
        ),
    )
    op.create_index(
        "ix_mev2_review_episode_id", "medication_exposures_v2", ["review_episode_id"]
    )
    op.create_index(
        "ix_mev2_medication_name", "medication_exposures_v2", ["medication_name"]
    )
    op.create_table(
        "clinical_conflict_groups_v2",
        sa.Column("conflict_group_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("gate_id", sa.String(length=128), nullable=False),
        *_authority_columns(),
        sa.Column("resolution_revision", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["fact_normalization_runs.run_id"],
            name="fk_clinical_conflict_groups_v2_fact_normalization_runs_run_id",
        ),
        sa.ForeignKeyConstraint(
            ["gate_id"], ["fact_gate_results.gate_result_id"],
            name="fk_clinical_conflict_groups_v2_fact_gate_results_gate_id",
        ),
        *_authority_fks("clinical_conflict_groups_v2"),
        sa.PrimaryKeyConstraint(
            "conflict_group_id", name="pk_clinical_conflict_groups_v2"
        ),
        sa.CheckConstraint(
            "resolution_revision = 0", name="ck_ccgv2_unresolved_slice51"
        ),
    )
    op.create_index(
        "ix_ccgv2_review_episode_id", "clinical_conflict_groups_v2", ["review_episode_id"]
    )
    op.create_index("ix_ccgv2_subject_id", "clinical_conflict_groups_v2", ["subject_id"])
    op.create_table(
        "fact_evidence_locator_links",
        sa.Column("entity_kind", sa.String(length=16), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("locator_id", sa.String(length=128), nullable=False),
        sa.Column("fact_id", sa.String(length=128), nullable=True),
        sa.Column("event_id", sa.String(length=128), nullable=True),
        sa.Column("exposure_id", sa.String(length=128), nullable=True),
        sa.Column("conflict_group_id", sa.String(length=128), nullable=True),
        sa.Column("expectation_id", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(
            ["locator_id"], ["evidence_locator_artifacts.locator_id"],
            name="fk_fact_evidence_locator_links_evidence_locator_artifacts_locator_id",
        ),
        sa.ForeignKeyConstraint(
            ["fact_id"], ["clinical_facts_v2.fact_id"],
            name="fk_fact_evidence_locator_links_clinical_facts_v2_fact_id",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["clinical_events_v2.event_id"],
            name="fk_fact_evidence_locator_links_clinical_events_v2_event_id",
        ),
        sa.ForeignKeyConstraint(
            ["exposure_id"], ["medication_exposures_v2.exposure_id"],
            name="fk_fact_evidence_locator_links_medication_exposures_v2_exposure_id",
        ),
        sa.ForeignKeyConstraint(
            ["conflict_group_id"], ["clinical_conflict_groups_v2.conflict_group_id"],
            name="fk_fact_evidence_locator_links_clinical_conflict_groups_v2_conflict_group_id",
        ),
        sa.ForeignKeyConstraint(
            ["expectation_id"], ["evidence_expectations_v2.expectation_id"],
            name="fk_fact_evidence_locator_links_evidence_expectations_v2_expectation_id",
        ),
        sa.PrimaryKeyConstraint(
            "entity_kind", "entity_id", "position", name="pk_fact_evidence_locator_links"
        ),
        sa.CheckConstraint(
            "entity_kind IN ('fact', 'event', 'exposure', 'conflict', 'expectation')",
            name="ck_fel_entity_kind",
        ),
        sa.CheckConstraint(
            "(entity_kind = 'fact' AND fact_id = entity_id AND event_id IS NULL "
            "AND exposure_id IS NULL AND conflict_group_id IS NULL AND expectation_id IS NULL) "
            "OR (entity_kind = 'event' AND event_id = entity_id AND fact_id IS NULL "
            "AND exposure_id IS NULL AND conflict_group_id IS NULL AND expectation_id IS NULL) "
            "OR (entity_kind = 'exposure' AND exposure_id = entity_id AND fact_id IS NULL "
            "AND event_id IS NULL AND conflict_group_id IS NULL AND expectation_id IS NULL) "
            "OR (entity_kind = 'conflict' AND conflict_group_id = entity_id AND fact_id IS NULL "
            "AND event_id IS NULL AND exposure_id IS NULL AND expectation_id IS NULL) "
            "OR (entity_kind = 'expectation' AND expectation_id = entity_id AND fact_id IS NULL "
            "AND event_id IS NULL AND exposure_id IS NULL AND conflict_group_id IS NULL)",
            name="ck_fel_entity_parent",
        ),
        sa.UniqueConstraint(
            "entity_kind", "entity_id", "locator_id", name="uq_fel_entity_locator"
        ),
    )
    op.create_index(
        "ix_fel_locator_id", "fact_evidence_locator_links", ["locator_id"]
    )
    op.create_table(
        "event_fact_links",
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("fact_id", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"], ["clinical_events_v2.event_id"],
            name="fk_event_fact_links_clinical_events_v2_event_id",
        ),
        sa.ForeignKeyConstraint(
            ["fact_id"], ["clinical_facts_v2.fact_id"],
            name="fk_event_fact_links_clinical_facts_v2_fact_id",
        ),
        sa.PrimaryKeyConstraint("event_id", "position", name="pk_event_fact_links"),
        sa.UniqueConstraint("event_id", "fact_id", name="uq_efl_event_fact"),
    )
    op.create_index("ix_efl_fact_id", "event_fact_links", ["fact_id"])
    op.create_table(
        "exposure_fact_links",
        sa.Column("exposure_id", sa.String(length=128), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("fact_id", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(
            ["exposure_id"], ["medication_exposures_v2.exposure_id"],
            name="fk_exposure_fact_links_medication_exposures_v2_exposure_id",
        ),
        sa.ForeignKeyConstraint(
            ["fact_id"], ["clinical_facts_v2.fact_id"],
            name="fk_exposure_fact_links_clinical_facts_v2_fact_id",
        ),
        sa.PrimaryKeyConstraint("exposure_id", "position", name="pk_exposure_fact_links"),
        sa.UniqueConstraint("exposure_id", "fact_id", name="uq_xfl_exposure_fact"),
    )
    op.create_index("ix_xfl_fact_id", "exposure_fact_links", ["fact_id"])
    op.create_table(
        "clinical_conflict_members_v2",
        sa.Column("conflict_group_id", sa.String(length=128), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("fact_id", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(
            ["conflict_group_id"], ["clinical_conflict_groups_v2.conflict_group_id"],
            name="fk_clinical_conflict_members_v2_clinical_conflict_groups_v2_conflict_group_id",
        ),
        sa.ForeignKeyConstraint(
            ["fact_id"], ["clinical_facts_v2.fact_id"],
            name="fk_clinical_conflict_members_v2_clinical_facts_v2_fact_id",
        ),
        sa.PrimaryKeyConstraint(
            "conflict_group_id", "position", name="pk_clinical_conflict_members_v2"
        ),
        sa.UniqueConstraint("conflict_group_id", "fact_id", name="uq_ccm_conflict_fact"),
    )
    op.create_index("ix_ccm_fact_id", "clinical_conflict_members_v2", ["fact_id"])
    op.create_table(
        "fact_rule_links_v2",
        sa.Column("link_id", sa.String(length=128), nullable=False),
        sa.Column("fact_id", sa.String(length=128), nullable=False),
        sa.Column("target_kind", sa.String(length=32), nullable=False),
        sa.Column("rule_set_id", sa.String(length=128), nullable=False),
        sa.Column("rule_set_revision", sa.Integer(), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("rule_component_id", sa.String(length=128), nullable=True),
        sa.Column("evidence_requirement_id", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(
            ["fact_id"], ["clinical_facts_v2.fact_id"],
            name="fk_fact_rule_links_v2_clinical_facts_v2_fact_id",
        ),
        sa.ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision"],
            ["rule_sets.rule_set_id", "rule_sets.revision"],
            name="fk_fact_rule_links_v2_rule_sets_rule_set",
        ),
        sa.ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision", "rule_component_id"],
            [
                "rule_components.rule_set_id",
                "rule_components.rule_set_revision",
                "rule_components.rule_component_id",
            ],
            name="fk_frl_rule_component",
        ),
        sa.ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision", "evidence_requirement_id"],
            [
                "evidence_requirements.rule_set_id",
                "evidence_requirements.rule_set_revision",
                "evidence_requirements.requirement_id",
            ],
            name="fk_frl_evidence_requirement",
        ),
        sa.PrimaryKeyConstraint("link_id", name="pk_fact_rule_links_v2"),
        sa.CheckConstraint(
            "target_kind IN ('rule_component', 'evidence_requirement')",
            name="ck_frl_target_kind",
        ),
        sa.CheckConstraint(
            "(target_kind = 'rule_component' AND rule_component_id = target_id "
            "AND evidence_requirement_id IS NULL) OR "
            "(target_kind = 'evidence_requirement' AND evidence_requirement_id = target_id "
            "AND rule_component_id IS NULL)",
            name="ck_frl_target_parent",
        ),
        sa.UniqueConstraint(
            "fact_id", "target_kind", "target_id", name="uq_frl_fact_target"
        ),
    )
    op.create_index(
        "ix_frl_target_kind_target", "fact_rule_links_v2", ["target_kind", "target_id"]
    )
    op.create_index(
        "ix_frl_rule_set", "fact_rule_links_v2", ["rule_set_id", "rule_set_revision"]
    )
    op.create_table(
        "evidence_expectations_v2",
        sa.Column("expectation_id", sa.String(length=128), nullable=False),
        *_authority_columns(),
        sa.Column("template_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("gap_type", sa.String(length=64), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        *_authority_fks("evidence_expectations_v2"),
        sa.ForeignKeyConstraint(
            ["template_id"], ["evidence_expectation_templates.template_id"],
            name="fk_evidence_expectations_v2_evidence_expectation_templates_template_id",
        ),
        sa.PrimaryKeyConstraint("expectation_id", name="pk_evidence_expectations_v2"),
        sa.UniqueConstraint(
            "review_episode_id", "template_id", "revision",
            name="uq_eev2_episode_template_revision",
        ),
    )
    op.create_index(
        "ix_eev2_review_episode_id", "evidence_expectations_v2", ["review_episode_id"]
    )
    op.create_index("ix_eev2_template_id", "evidence_expectations_v2", ["template_id"])
    op.create_index("ix_eev2_status", "evidence_expectations_v2", ["status"])
    op.create_table(
        "patient_profile_revisions_v2",
        sa.Column("patient_profile_revision_id", sa.String(length=128), nullable=False),
        *_authority_columns(),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column("highlights_json", sa.JSON(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        *_authority_fks("patient_profile_revisions_v2"),
        sa.PrimaryKeyConstraint(
            "patient_profile_revision_id", name="pk_patient_profile_revisions_v2"
        ),
        sa.CheckConstraint(
            "status IN ('succeeded', 'generating', 'failed', 'stale')",
            name="ck_pprv2_status",
        ),
        sa.UniqueConstraint(
            "review_episode_id", "revision", name="uq_pprv2_episode_revision"
        ),
    )
    op.create_index(
        "ix_pprv2_review_episode_id",
        "patient_profile_revisions_v2",
        ["review_episode_id"],
    )
    op.create_index("ix_pprv2_status", "patient_profile_revisions_v2", ["status"])


def downgrade() -> None:
    # 0013 的 v2 事实/事件/暴露/冲突/期望/Profile 是不可变历史；空表绿地库才允许
    # 反向删除，任一表有行即拒绝有损降级（由管理器从迁移前备份恢复）。
    bind = op.get_bind()
    populated = [
        table_name
        for table_name in _V2_TABLES
        if bind.exec_driver_sql(f"SELECT 1 FROM {table_name} LIMIT 1").first() is not None
    ]
    if populated:
        raise RuntimeError(
            "0013 含有 Phase 5 v2 正式数据，拒绝降级以避免丢失不可变历史："
            + ", ".join(populated)
        )

    # 依赖逆序删除：先删子表，再删父表。
    for table_name in _V2_TABLES:
        op.drop_table(table_name)
