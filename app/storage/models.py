"""V2 SQLite 领域 ORM：规范化检索列 + canonical JSON/hash payload。

约定（与 ``.trellis/spec/backend/database-guidelines.md`` 及 Phase 2 设计一致）：

- 可变根（projects/subjects/review_episodes/evidence_expectations/action_requests/
  jobs/job_steps）含 ``revision``（SQLAlchemy version_id）与 created/updated 时间戳；
- 不可变记录（协议、规则、快照、跨度、事实、ReviewRun、评估、转换、Agent/Gate、
  Job 事件等）追加写，读取时校验 payload hash 后还原 Pydantic 合同；
- 复杂多值引用使用 association table；枚举存储稳定英文机器值；
- 时间列统一按 UTC naive 存储，payload 内保留合同原文精度。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.storage.db import Base

PAYLOAD_SHA_LEN = 64

#: 正式审核实体的资料谱系判别（ReviewRun/AssessmentCandidate/FinalAssessment/
#: ActionRequest）：恰好一条谱系。legacy 行只绑 legacy 快照；V2 行只绑 V2 快照 +
#: 完整处理修订，``evidence_snapshot_id`` 必须为 NULL（绝不把 V2 id 写入 legacy 列）。
REVIEW_EVIDENCE_LINEAGE_CHECK_SQL = (
    "(evidence_snapshot_id IS NOT NULL AND evidence_snapshot_v2_id IS NULL "
    "AND complete_processing_revision_id IS NULL) OR "
    "(evidence_snapshot_id IS NULL AND evidence_snapshot_v2_id IS NOT NULL "
    "AND complete_processing_revision_id IS NOT NULL)"
)

#: AgentCall 允许协议-only 调用三条资料指针全空（真实存在的无审核证据调用）；
#: 一旦携带资料指针，仍必须恰好一条谱系，不套用正式审核实体的强制判别。
AGENT_CALL_EVIDENCE_LINEAGE_CHECK_SQL = (
    "(evidence_snapshot_id IS NULL AND evidence_snapshot_v2_id IS NULL "
    "AND complete_processing_revision_id IS NULL AND node = 'protocol_deconstructor') OR "
    "(evidence_snapshot_id IS NOT NULL AND evidence_snapshot_v2_id IS NULL "
    "AND complete_processing_revision_id IS NULL) OR "
    "(evidence_snapshot_id IS NULL AND evidence_snapshot_v2_id IS NOT NULL "
    "AND complete_processing_revision_id IS NOT NULL)"
)


class AppendedRecordMixin:
    """不可变追加记录公共列：canonical JSON payload + 哈希 + 写入时间。"""

    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class RevisionedRecordMixin:
    """可变根公共列：revision 乐观并发 + 时间戳。

    通过 ``__mapper_args__`` directive 把真实 Column 交给 mapper versioning
    （字符串形式在 SQLAlchemy 2.0 的 RETURNING 路径上不兼容）。
    """

    revision: Mapped[int] = mapped_column(Integer, nullable=False)

    @declared_attr.directive
    def __mapper_args__(cls) -> dict:
        return {"version_id_col": cls.revision}
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)


# ---------------------------------------------------------------------------
# 可变根
# ---------------------------------------------------------------------------


class ProjectRecord(RevisionedRecordMixin, Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    project_code: Mapped[str] = mapped_column(String(128), nullable=False)
    project_name: Mapped[str] = mapped_column(String(256), nullable=False)
    study_phase: Mapped[str] = mapped_column(String(32), nullable=False)
    protocol_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_document_versions.protocol_version_id"),
        nullable=False,
    )
    rule_set_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_set_revision: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision"],
            ["rule_sets.rule_set_id", "rule_sets.revision"],
        ),
    )


class SubjectRecord(RevisionedRecordMixin, Base):
    __tablename__ = "subjects"

    subject_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject_code: Mapped[str] = mapped_column(String(128), nullable=False)
    project_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("projects.project_id"), nullable=False
    )
    center_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    center_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    sex: Mapped[str | None] = mapped_column(String(32), nullable=True)
    age_years: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (Index("ix_subjects_project_id", "project_id"),)
class ReviewEpisodeRecord(RevisionedRecordMixin, Base):
    __tablename__ = "review_episodes"

    review_episode_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("subjects.subject_id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("projects.project_id"), nullable=False
    )
    rule_set_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_set_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    study_phase: Mapped[str] = mapped_column(String(32), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    protocol_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_document_versions.protocol_version_id"),
        nullable=False,
    )
    # legacy evidence_snapshot_id 可空：自动创建的空审核节点没有 Phase 2/3 快照。
    evidence_snapshot_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey(
            "evidence_snapshots.evidence_snapshot_id",
            deferrable=True,
            initially="DEFERRED",
        ),
        nullable=True,
    )
    # 发布方案流程节点身份（命名空间化 workflow_stage_id）；legacy 行可空。
    workflow_stage_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("workflow_stages.workflow_stage_id"), nullable=True
    )
    # Phase 4 活动版本成对指针（Slice 4.4）：legacy evidence_snapshot_id 保留原义，
    # 本对指针是当前版本唯一权威，迁移 0010 不按时间/ID/历史状态回填。
    active_evidence_snapshot_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_snapshots_v2.evidence_snapshot_id"),
        nullable=True,
    )
    active_evidence_processing_revision_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"),
        nullable=True,
    )
    anchor_dates_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision"],
            ["rule_sets.rule_set_id", "rule_sets.revision"],
        ),
        CheckConstraint(
            "(active_evidence_snapshot_id IS NULL AND "
            "active_evidence_processing_revision_id IS NULL) OR "
            "(active_evidence_snapshot_id IS NOT NULL AND "
            "active_evidence_processing_revision_id IS NOT NULL)",
            name="ck_review_episodes_active_pointers_paired",
        ),
        Index("ix_review_episodes_subject_id", "subject_id"),
        Index("ix_review_episodes_project_id", "project_id"),
    )


class EvidenceExpectationRecord(RevisionedRecordMixin, Base):
    __tablename__ = "evidence_expectations"

    expectation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    requirement_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_set_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_set_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    review_episode_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_episodes.review_episode_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    gap_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision", "requirement_id"],
            [
                "evidence_requirements.rule_set_id",
                "evidence_requirements.rule_set_revision",
                "evidence_requirements.requirement_id",
            ],
        ),
        Index("ix_evidence_expectations_review_episode_id", "review_episode_id"),
    )


class ActionRequestRecord(RevisionedRecordMixin, Base):
    __tablename__ = "action_requests"

    action_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("projects.project_id"), nullable=False
    )
    protocol_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_document_versions.protocol_version_id"),
        nullable=False,
    )
    subject_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("subjects.subject_id"), nullable=False
    )
    rule_set_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_set_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_component_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    control_snapshot_run_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("review_control_snapshots.review_run_id"), nullable=True
    )
    protocol_control_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    control_obligation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    control_obligation_group_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_episode_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_episodes.review_episode_id"), nullable=False
    )
    # 双谱系指针：legacy 快照与（V2 快照 + 完整处理修订）恰好一条，见 CHECK。
    evidence_snapshot_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("evidence_snapshots.evidence_snapshot_id"), nullable=True
    )
    evidence_snapshot_v2_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_snapshots_v2.evidence_snapshot_id"),
        nullable=True,
    )
    complete_processing_revision_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"),
        nullable=True,
    )
    review_run_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_runs.review_run_id"), nullable=False
    )
    assessment_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("final_assessments.assessment_id"), nullable=True
    )
    gap_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_party: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_action: Mapped[str] = mapped_column(Text, nullable=False)
    acceptable_evidence: Mapped[str] = mapped_column(Text, nullable=False)
    due_stage: Mapped[str] = mapped_column(String(32), nullable=False)
    blocking_level: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_evidence_span_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("evidence_spans.evidence_span_id"), nullable=True
    )
    # V2 谱系的触发定位（Phase 4 locator）；legacy 行继续用 evidence_spans，绝不混用。
    trigger_locator_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_locator_artifacts.locator_id"),
        nullable=True,
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    recompute_scope_json: Mapped[list] = mapped_column(JSON, nullable=False)
    gate_result_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("gate_results.gate_result_id"), nullable=False
    )
    publication_fingerprint: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)

    __table_args__ = (
        CheckConstraint(
            REVIEW_EVIDENCE_LINEAGE_CHECK_SQL,
            name="ck_action_requests_evidence_lineage",
        ),
        CheckConstraint(
            "(assessment_id IS NOT NULL AND rule_component_id IS NOT NULL AND "
            "control_snapshot_run_id IS NULL AND protocol_control_id IS NULL AND control_obligation_id IS NULL AND control_obligation_group_id IS NULL) OR "
            "(assessment_id IS NULL AND rule_component_id IS NULL AND control_snapshot_run_id IS NOT NULL AND "
            "control_snapshot_run_id = review_run_id AND protocol_control_id IS NOT NULL AND "
            "((control_obligation_id IS NOT NULL AND control_obligation_group_id IS NULL) OR "
            "(control_obligation_id IS NULL AND control_obligation_group_id IS NOT NULL)) AND evidence_snapshot_v2_id IS NOT NULL)",
            name="ck_action_requests_requirement_origin",
        ),
        CheckConstraint(
            "(evidence_snapshot_v2_id IS NULL AND trigger_locator_id IS NULL) OR "
            "(evidence_snapshot_v2_id IS NOT NULL AND trigger_evidence_span_id IS NULL)",
            name="ck_action_requests_trigger_lineage",
        ),
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision", "rule_component_id"],
            [
                "rule_components.rule_set_id",
                "rule_components.rule_set_revision",
                "rule_components.rule_component_id",
            ],
        ),
        Index("ix_action_requests_review_episode_id", "review_episode_id"),
        Index("ix_action_requests_state", "state"),
    )


# ---------------------------------------------------------------------------
# 协议权威链（追加写）
# ---------------------------------------------------------------------------


class ProtocolDocumentVersionRecord(AppendedRecordMixin, Base):
    __tablename__ = "protocol_document_versions"

    protocol_version_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    protocol_code: Mapped[str] = mapped_column(String(128), nullable=False)
    official_version: Mapped[str] = mapped_column(String(64), nullable=False)
    official_date_value: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    official_date_precision: Mapped[str] = mapped_column(String(16), nullable=False)
    sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    integrity_manifest_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )
    authority_record_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    authority_confirmation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    authority_gate_result_id: Mapped[str] = mapped_column(String(128), nullable=False)
    integrity_gate_result_id: Mapped[str] = mapped_column(String(128), nullable=False)


class RuleSetRecord(AppendedRecordMixin, Base):
    __tablename__ = "rule_sets"

    rule_set_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    protocol_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_document_versions.protocol_version_id"),
        nullable=False,
    )
    study_phase: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (Index("ix_rule_sets_protocol_version_id", "protocol_version_id"),)


class RuleRecord(AppendedRecordMixin, Base):
    __tablename__ = "rules"

    rule_set_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    rule_set_revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    official_code: Mapped[str] = mapped_column(String(16), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    study_phase: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision"],
            ["rule_sets.rule_set_id", "rule_sets.revision"],
        ),
        Index("ix_rules_official_code", "official_code"),
    )


class RuleComponentRecord(AppendedRecordMixin, Base):
    __tablename__ = "rule_components"

    rule_set_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    rule_set_revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_component_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    parent_rule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    display_code: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    expression_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    expression_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    exception_expression_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    exception_expression_sha256: Mapped[str | None] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=True
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision"],
            ["rule_sets.rule_set_id", "rule_sets.revision"],
        ),
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision", "parent_rule_id"],
            ["rules.rule_set_id", "rules.rule_set_revision", "rules.rule_id"],
        ),
    )


class EvidenceRequirementRecord(AppendedRecordMixin, Base):
    __tablename__ = "evidence_requirements"

    rule_set_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    rule_set_revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    requirement_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    # One-and-only-one origin: a requirement is produced either by a rule
    # component, by a frozen procedure-catalog item (visit instance), or by a
    # published node-specific control of a frozen control catalog.  The CHECK
    # constraint mirrors the domain contract; procedure- and control-origin rows
    # keep rule_component_id NULL instead of fabricating a component binding.
    rule_component_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    procedure_catalog_item_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    # 镜像已发布目录的 publication_id（不可变 0024 表）；控制来源的
    # protocol_control_id / evidence_key / workflow_stage_id 只存在 payload 正文。
    control_publication_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("protocol_control_catalog_publications.publication_id"),
        nullable=True,
    )
    fact_type: Mapped[str] = mapped_column(String(128), nullable=False)
    due_stage: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "(rule_component_id IS NOT NULL AND procedure_catalog_item_id IS NULL "
            "AND control_publication_id IS NULL) OR "
            "(rule_component_id IS NULL AND procedure_catalog_item_id IS NOT NULL "
            "AND control_publication_id IS NULL) OR "
            "(rule_component_id IS NULL AND procedure_catalog_item_id IS NULL "
            "AND control_publication_id IS NOT NULL)",
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
        Index("ix_evidence_requirements_fact_type", "fact_type"),
    )


class WorkflowStageRecord(AppendedRecordMixin, Base):
    __tablename__ = "workflow_stages"

    workflow_stage_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    protocol_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_document_versions.protocol_version_id"),
        nullable=False,
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    # 审核节点按研究期别隔离：同一筛选/基线名称在不同期别项目中的节点
    # 不能互相合并；期别由发布服务写入，查询与投影按 (阶段, 期别) 去重。
    study_phase: Mapped[str | None] = mapped_column(String(32), nullable=True)


class ProtocolDraftRevisionRecord(AppendedRecordMixin, Base):
    """已保存草稿 revision（追加写，永不物理删除）。

    首稿 revision_number=1；后继 revision 通过 previous_revision_id 形成
    链，链头即当前草稿版本。乐观并发由服务层校验「后继必须指向链头」，
    过期编辑抛 StaleRevisionError，绝不覆盖新 revision。
    """

    __tablename__ = "protocol_draft_revisions"

    revision_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    draft_id: Mapped[str] = mapped_column(String(128), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_revision_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    project_id: Mapped[str] = mapped_column(String(128), nullable=False)
    protocol_version_id: Mapped[str] = mapped_column(String(128), nullable=False)
    study_phase: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    feedback_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)

    __table_args__ = (
        UniqueConstraint("draft_id", "revision_number"),
        Index("ix_protocol_draft_revisions_draft_id", "draft_id"),
    )


class EvidenceExpectationTemplateRecord(AppendedRecordMixin, Base):
    """无受试者资料核对期望模板投影（追加写，可重建）。

    ``(rule_set_id, rule_set_revision, requirement_id)`` 唯一；模板 ID 与
    投影哈希由稳定身份字段确定性计算，同一 revision 重建结果一致。
    """

    __tablename__ = "evidence_expectation_templates"

    template_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    rule_set_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_set_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    requirement_id: Mapped[str] = mapped_column(String(128), nullable=False)
    due_stage: Mapped[str] = mapped_column(String(32), nullable=False)
    study_phase: Mapped[str] = mapped_column(String(32), nullable=False)
    workflow_stage_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("workflow_stages.workflow_stage_id"), nullable=False
    )
    fact_type: Mapped[str] = mapped_column(String(128), nullable=False)
    required_source_types: Mapped[list | None] = mapped_column(JSON, nullable=True)
    projection_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("rule_set_id", "rule_set_revision", "requirement_id"),
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision"],
            ["rule_sets.rule_set_id", "rule_sets.revision"],
        ),
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision", "requirement_id"],
            [
                "evidence_requirements.rule_set_id",
                "evidence_requirements.rule_set_revision",
                "evidence_requirements.requirement_id",
            ],
        ),
        Index(
            "ix_evidence_expectation_templates_rule_set",
            "rule_set_id",
            "rule_set_revision",
        ),
    )


class ProtocolAuthorityRecordRow(AppendedRecordMixin, Base):
    __tablename__ = "protocol_authority_records"

    authority_record_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    protocol_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_document_versions.protocol_version_id"),
        nullable=False,
    )
    study_phase: Mapped[str] = mapped_column(String(32), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ProtocolSourceRecordRow(AppendedRecordMixin, Base):
    __tablename__ = "protocol_source_records"

    source_ref: Mapped[str] = mapped_column(String(256), primary_key=True)
    protocol_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_document_versions.protocol_version_id"),
        nullable=False,
    )
    protocol_document_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)


class ServiceCommandEventRecord(AppendedRecordMixin, Base):
    __tablename__ = "service_command_events"

    command_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    protocol_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_document_versions.protocol_version_id"),
        nullable=False,
    )
    authority_record_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_authority_records.authority_record_id"),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ProtocolAuthorityConfirmationRecord(AppendedRecordMixin, Base):
    __tablename__ = "protocol_authority_confirmations"

    confirmation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    command_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("service_command_events.command_id"), nullable=False
    )
    protocol_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_document_versions.protocol_version_id"),
        nullable=False,
    )
    authority_record_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_authority_records.authority_record_id"),
        nullable=False,
    )
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ProtocolIntegrityManifestRecord(AppendedRecordMixin, Base):
    __tablename__ = "protocol_integrity_manifests"

    manifest_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    protocol_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_document_versions.protocol_version_id"),
        nullable=False,
    )
    authority_record_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_authority_records.authority_record_id"),
        nullable=False,
    )


# ---------------------------------------------------------------------------
# 方案文档提取（Phase 3 切片 1，追加写）
# ---------------------------------------------------------------------------


class ProtocolSourceArtifactRecord(AppendedRecordMixin, Base):
    __tablename__ = "protocol_source_artifacts"

    source_artifact_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # 内容身份去重：相同 SHA-256 的不可变工件只登记一次。
    __table_args__ = (UniqueConstraint("sha256"),)


class ProtocolRenderArtifactRecord(AppendedRecordMixin, Base):
    __tablename__ = "protocol_render_artifacts"

    render_artifact_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_artifact_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("protocol_source_artifacts.source_artifact_id"), nullable=False
    )
    source_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    renderer: Mapped[str] = mapped_column(String(64), nullable=False)
    renderer_version: Mapped[str] = mapped_column(String(64), nullable=False)
    pdf_sha256: Mapped[str | None] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    render_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_protocol_render_artifacts_source_artifact_id", "source_artifact_id"),
    )


class ProtocolExtractionSnapshotRecord(AppendedRecordMixin, Base):
    __tablename__ = "protocol_extraction_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_artifact_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("protocol_source_artifacts.source_artifact_id"), nullable=False
    )
    source_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    parser_name: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    content_storage_ref: Mapped[str] = mapped_column(String(512), nullable=False)

    __table_args__ = (
        Index("ix_protocol_extraction_snapshots_source_artifact_id", "source_artifact_id"),
    )


class ProtocolSourceSpanRecord(AppendedRecordMixin, Base):
    __tablename__ = "protocol_source_spans"

    source_span_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("protocol_extraction_snapshots.snapshot_id"), nullable=False
    )
    source_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    document_part: Mapped[str] = mapped_column(String(32), nullable=False)
    precision: Mapped[str] = mapped_column(String(32), nullable=False)
    alignment_status: Mapped[str] = mapped_column(String(32), nullable=False)
    render_artifact_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("protocol_render_artifacts.render_artifact_id"), nullable=True
    )
    render_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    table_path: Mapped[list | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("snapshot_id", "source_ref"),
        Index("ix_protocol_source_spans_source_ref", "source_ref"),
    )


class FrozenProtocolCatalogRecord(AppendedRecordMixin, Base):
    __tablename__ = "frozen_protocol_catalogs"

    catalog_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("protocol_extraction_snapshots.snapshot_id"), nullable=False
    )
    catalog_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    study_phase: Mapped[str] = mapped_column(String(32), nullable=False)
    frozen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("snapshot_id", "catalog_kind", "study_phase"),
        Index("ix_frozen_protocol_catalogs_snapshot_id", "snapshot_id"),
    )


# ---------------------------------------------------------------------------
# 方案元信息、期别适用图与解释材料（Phase 3 切片 2，追加写）
# ---------------------------------------------------------------------------


class ProtocolMetadataCandidateRecord(AppendedRecordMixin, Base):
    __tablename__ = "protocol_metadata_candidates"

    candidate_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("protocol_extraction_snapshots.snapshot_id"), nullable=False
    )
    field_category: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(512), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    identity_authority: Mapped[str] = mapped_column(String(16), nullable=False)
    priority_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    conflict_group_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        Index("ix_protocol_metadata_candidates_snapshot_id", "snapshot_id"),
        Index("ix_protocol_metadata_candidates_field_category", "field_category"),
    )


class ProtocolMetadataConflictRecord(AppendedRecordMixin, Base):
    __tablename__ = "protocol_metadata_conflicts"

    conflict_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("protocol_extraction_snapshots.snapshot_id"), nullable=False
    )
    field_category: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    selected_candidate_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        UniqueConstraint("snapshot_id", "field_category", "status"),
        Index("ix_protocol_metadata_conflicts_snapshot_id", "snapshot_id"),
    )


class ProtocolIdentityDecisionRecord(AppendedRecordMixin, Base):
    __tablename__ = "protocol_identity_decisions"

    identity_decision_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("protocol_extraction_snapshots.snapshot_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    project_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    project_code: Mapped[str | None] = mapped_column(String(256), nullable=True)
    protocol_code: Mapped[str | None] = mapped_column(String(256), nullable=True)
    official_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    official_date_value: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    official_date_precision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    study_phase: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (Index("ix_protocol_identity_decisions_snapshot_id", "snapshot_id"),)


class StudyPhaseCandidateRecord(AppendedRecordMixin, Base):
    __tablename__ = "study_phase_candidates"

    candidate_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("protocol_extraction_snapshots.snapshot_id"), nullable=False
    )
    design_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    priority_rank: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (Index("ix_study_phase_candidates_snapshot_id", "snapshot_id"),)


class StudyPhaseSelectionRecord(AppendedRecordMixin, Base):
    __tablename__ = "study_phase_selections"

    selection_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("protocol_extraction_snapshots.snapshot_id"), nullable=False
    )
    selected_phase: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (Index("ix_study_phase_selections_snapshot_id", "snapshot_id"),)


class ProtocolPhaseApplicabilityGraphRecord(AppendedRecordMixin, Base):
    __tablename__ = "protocol_phase_applicability_graphs"

    graph_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("protocol_extraction_snapshots.snapshot_id"), nullable=False
    )
    default_design_type: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (UniqueConstraint("snapshot_id"),)


class ProtocolPhaseProjectionRecord(AppendedRecordMixin, Base):
    __tablename__ = "protocol_phase_projections"

    projection_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    graph_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("protocol_phase_applicability_graphs.graph_id"), nullable=False
    )
    selected_phase: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        UniqueConstraint("graph_id", "selected_phase"),
        Index("ix_protocol_phase_projections_graph_id", "graph_id"),
    )


class InterpretationSourceRecord(AppendedRecordMixin, Base):
    __tablename__ = "interpretation_sources"

    interpretation_source_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    protocol_version_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("protocol_document_versions.protocol_version_id"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    authority: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    is_current_amendment: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (Index("ix_interpretation_sources_protocol_version_id", "protocol_version_id"),)


class InterpretationConflictRecord(AppendedRecordMixin, Base):
    __tablename__ = "interpretation_conflicts"

    conflict_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    protocol_version_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("protocol_document_versions.protocol_version_id"), nullable=False
    )
    interpretation_source_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("interpretation_sources.interpretation_source_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    blocks_publication: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (
        Index("ix_interpretation_conflicts_protocol_version_id", "protocol_version_id"),
        Index("ix_interpretation_conflicts_source_id", "interpretation_source_id"),
    )


# ---------------------------------------------------------------------------
# 证据链（追加写）
# ---------------------------------------------------------------------------


class SourceDocumentVersionRecord(AppendedRecordMixin, Base):
    __tablename__ = "source_document_versions"

    source_document_version_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_party: Mapped[str] = mapped_column(String(64), nullable=False)
    upload_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    review_stage: Mapped[str] = mapped_column(String(32), nullable=False)


class EvidenceSnapshotRecord(AppendedRecordMixin, Base):
    __tablename__ = "evidence_snapshots"

    evidence_snapshot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("subjects.subject_id"), nullable=False
    )
    review_episode_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey(
            "review_episodes.review_episode_id",
            deferrable=True,
            initially="DEFERRED",
        ),
        nullable=False,
    )
    upload_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    prior_snapshot_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("evidence_snapshots.evidence_snapshot_id"), nullable=True
    )

    __table_args__ = (Index("ix_evidence_snapshots_subject_id", "subject_id"),)


class EvidenceSpanRecord(AppendedRecordMixin, Base):
    __tablename__ = "evidence_spans"

    evidence_span_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_document_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("source_document_versions.source_document_version_id"),
        nullable=False,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    precision: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        Index("ix_evidence_spans_source_document_version_id", "source_document_version_id"),
    )


class ClinicalFactRecord(AppendedRecordMixin, Base):
    __tablename__ = "clinical_facts"

    fact_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("projects.project_id"), nullable=False
    )
    subject_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("subjects.subject_id"), nullable=False
    )
    review_episode_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_episodes.review_episode_id"), nullable=False
    )
    evidence_snapshot_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("evidence_snapshots.evidence_snapshot_id"), nullable=False
    )
    fact_type: Mapped[str] = mapped_column(String(128), nullable=False)
    polarity: Mapped[str] = mapped_column(String(16), nullable=False)
    certainty: Mapped[float] = mapped_column(Float, nullable=False)
    value_json: Mapped[str | int | float | bool | None] = mapped_column(JSON, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effective_date_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    conflict_group_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("conflict_groups.conflict_group_id"), nullable=True
    )

    __table_args__ = (
        Index("ix_clinical_facts_review_episode_id", "review_episode_id"),
        Index("ix_clinical_facts_subject_fact_type", "subject_id", "fact_type"),
    )


class ConflictGroupRecord(AppendedRecordMixin, Base):
    __tablename__ = "conflict_groups"

    conflict_group_id: Mapped[str] = mapped_column(String(128), primary_key=True)


class EvidenceNormalizationCandidateRecord(AppendedRecordMixin, Base):
    __tablename__ = "evidence_normalization_candidates"

    candidate_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("projects.project_id"), nullable=False
    )
    protocol_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_document_versions.protocol_version_id"),
        nullable=False,
    )
    subject_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("subjects.subject_id"), nullable=False
    )
    review_episode_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_episodes.review_episode_id"), nullable=False
    )
    evidence_snapshot_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("evidence_snapshots.evidence_snapshot_id"), nullable=False
    )
    created_by_agent_call_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("agent_calls.agent_call_id"), nullable=False
    )


class PatientProfileRecord(AppendedRecordMixin, Base):
    __tablename__ = "patient_profiles"

    patient_profile_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("subjects.subject_id"), nullable=False
    )
    review_episode_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_episodes.review_episode_id"), nullable=False
    )
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False)


# ---------------------------------------------------------------------------
# 审核与动作（ReviewRun 等追加写；ActionRequest 为可变根见上）
# ---------------------------------------------------------------------------


class ReviewRunRecord(AppendedRecordMixin, Base):
    __tablename__ = "review_runs"

    review_run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    review_episode_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_episodes.review_episode_id"), nullable=False
    )
    protocol_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_document_versions.protocol_version_id"),
        nullable=False,
    )
    rule_set_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    context_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("review_context_snapshots.context_id"), nullable=True
    )
    # 双谱系指针：legacy 快照与（V2 快照 + 完整处理修订）恰好一条，见 CHECK。
    evidence_snapshot_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("evidence_snapshots.evidence_snapshot_id"), nullable=True
    )
    evidence_snapshot_v2_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_snapshots_v2.evidence_snapshot_id"),
        nullable=True,
    )
    complete_processing_revision_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    supersedes_review_run_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("review_runs.review_run_id"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            REVIEW_EVIDENCE_LINEAGE_CHECK_SQL,
            name="ck_review_runs_evidence_lineage",
        ),
        CheckConstraint(
            "(evidence_snapshot_v2_id IS NULL AND context_id IS NULL) OR "
            "(evidence_snapshot_v2_id IS NOT NULL AND context_id IS NOT NULL)",
            name="ck_review_runs_context_lineage",
        ),
        Index("ix_review_runs_review_episode_id", "review_episode_id"),
    )


class AssessmentCandidateRecord(AppendedRecordMixin, Base):
    __tablename__ = "assessment_candidates"

    assessment_candidate_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    agent_call_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("agent_calls.agent_call_id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("projects.project_id"), nullable=False
    )
    protocol_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_document_versions.protocol_version_id"),
        nullable=False,
    )
    subject_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("subjects.subject_id"), nullable=False
    )
    review_episode_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_episodes.review_episode_id"), nullable=False
    )
    review_run_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_runs.review_run_id"), nullable=False
    )
    # 双谱系指针：legacy 快照与（V2 快照 + 完整处理修订）恰好一条，见 CHECK。
    evidence_snapshot_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("evidence_snapshots.evidence_snapshot_id"), nullable=True
    )
    evidence_snapshot_v2_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_snapshots_v2.evidence_snapshot_id"),
        nullable=True,
    )
    complete_processing_revision_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"),
        nullable=True,
    )
    rule_set_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_set_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_component_id: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        CheckConstraint(
            REVIEW_EVIDENCE_LINEAGE_CHECK_SQL,
            name="ck_assessment_candidates_evidence_lineage",
        ),
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision", "rule_component_id"],
            [
                "rule_components.rule_set_id",
                "rule_components.rule_set_revision",
                "rule_components.rule_component_id",
            ],
        ),
        Index("ix_assessment_candidates_review_episode_id", "review_episode_id"),
    )


class FinalAssessmentRecord(AppendedRecordMixin, Base):
    __tablename__ = "final_assessments"

    assessment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("projects.project_id"), nullable=False
    )
    protocol_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_document_versions.protocol_version_id"),
        nullable=False,
    )
    subject_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("subjects.subject_id"), nullable=False
    )
    review_episode_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_episodes.review_episode_id"), nullable=False
    )
    review_run_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_runs.review_run_id"), nullable=False
    )
    # 双谱系指针：legacy 快照与（V2 快照 + 完整处理修订）恰好一条，见 CHECK。
    evidence_snapshot_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("evidence_snapshots.evidence_snapshot_id"), nullable=True
    )
    evidence_snapshot_v2_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_snapshots_v2.evidence_snapshot_id"),
        nullable=True,
    )
    complete_processing_revision_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"),
        nullable=True,
    )
    rule_set_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_set_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_component_id: Mapped[str] = mapped_column(String(128), nullable=False)
    decision: Mapped[str] = mapped_column(String(48), nullable=False)
    blocking_level: Mapped[str] = mapped_column(String(32), nullable=False)
    gate_result_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("gate_results.gate_result_id"), nullable=False
    )
    publication_fingerprint: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)

    __table_args__ = (
        CheckConstraint(
            REVIEW_EVIDENCE_LINEAGE_CHECK_SQL,
            name="ck_final_assessments_evidence_lineage",
        ),
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision", "rule_component_id"],
            [
                "rule_components.rule_set_id",
                "rule_components.rule_set_revision",
                "rule_components.rule_component_id",
            ],
        ),
        Index("ix_final_assessments_review_episode_id", "review_episode_id"),
    )


class ActionTransitionRecord(AppendedRecordMixin, Base):
    __tablename__ = "action_transitions"

    transition_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    action_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("action_requests.action_id"), nullable=False
    )
    from_state: Mapped[str] = mapped_column(String(32), nullable=False)
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (Index("ix_action_transitions_action_id", "action_id"),)


class ReviewRunDiffRecord(AppendedRecordMixin, Base):
    __tablename__ = "review_run_diffs"

    review_run_diff_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    prior_review_run_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_runs.review_run_id"), nullable=False
    )
    current_review_run_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_runs.review_run_id"), nullable=False
    )


# ---------------------------------------------------------------------------
# Agent 与 Gate（追加写）
# ---------------------------------------------------------------------------


class PromptVersionRecord(AppendedRecordMixin, Base):
    __tablename__ = "prompt_versions"

    prompt_version_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    node: Mapped[str] = mapped_column(String(48), nullable=False)
    template_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    schema_version_id: Mapped[str] = mapped_column(String(128), nullable=False)


class ModelConfigRecord(AppendedRecordMixin, Base):
    __tablename__ = "model_configs"

    model_config_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    reasoning_effort: Mapped[str] = mapped_column(String(32), nullable=False)


class AgentCallRecord(AppendedRecordMixin, Base):
    __tablename__ = "agent_calls"

    agent_call_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    node: Mapped[str] = mapped_column(String(48), nullable=False)
    output_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    write_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_version_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("prompt_versions.prompt_version_id"), nullable=False
    )
    model_config_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("model_configs.model_config_id"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    project_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("projects.project_id"), nullable=False
    )
    protocol_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_document_versions.protocol_version_id"),
        nullable=False,
    )
    rule_set_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rule_set_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subject_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("subjects.subject_id"), nullable=True
    )
    review_episode_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("review_episodes.review_episode_id"), nullable=True
    )
    review_run_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("review_runs.review_run_id"), nullable=True
    )
    evidence_snapshot_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("evidence_snapshots.evidence_snapshot_id"), nullable=True
    )
    # V2 审核调用的资料谱系：与 legacy 成对互斥；协议-only 调用三列全空仍合法。
    evidence_snapshot_v2_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_snapshots_v2.evidence_snapshot_id"),
        nullable=True,
    )
    complete_processing_revision_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"),
        nullable=True,
    )
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        CheckConstraint(
            AGENT_CALL_EVIDENCE_LINEAGE_CHECK_SQL,
            name="ck_agent_calls_evidence_lineage",
        ),
        Index("ix_agent_calls_project_id", "project_id"),
        Index("ix_agent_calls_idempotency_key", "idempotency_key"),
    )


class GateResultRecord(AppendedRecordMixin, Base):
    __tablename__ = "gate_results"

    gate_result_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    gate_name: Mapped[str] = mapped_column(String(128), nullable=False)
    code_version: Mapped[str] = mapped_column(String(32), nullable=False)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    input_scope_hash: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    output_hash: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)

    __table_args__ = (Index("ix_gate_results_idempotency_key", "idempotency_key"),)


class CriticRunRecord(AppendedRecordMixin, Base):
    __tablename__ = "critic_runs"

    critic_run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    assessment_candidate_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("assessment_candidates.assessment_candidate_id"),
        nullable=False,
    )
    created_by_agent_call_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("agent_calls.agent_call_id"), nullable=False
    )
    critic_revision: Mapped[int] = mapped_column(Integer, nullable=False)


# ---------------------------------------------------------------------------
# 投影与上下文（可重建，追加写）
# ---------------------------------------------------------------------------


class EpisodeRollupRecord(AppendedRecordMixin, Base):
    __tablename__ = "episode_rollups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_episode_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_episodes.review_episode_id"), nullable=False
    )
    main_status: Mapped[str] = mapped_column(String(32), nullable=False)
    gate_result_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("gate_results.gate_result_id"), nullable=False
    )
    publication_fingerprint: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)

    __table_args__ = (
        UniqueConstraint("review_episode_id", "publication_fingerprint"),
        Index("ix_episode_rollups_review_episode_id", "review_episode_id"),
    )


class ReviewContextSnapshotRecord(AppendedRecordMixin, Base):
    __tablename__ = "review_context_snapshots"

    context_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    review_episode_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_episodes.review_episode_id"), nullable=False
    )


# ---------------------------------------------------------------------------
# 持久 Job（状态机逻辑由 workflow 层实现；此处只定义存储形状）
# ---------------------------------------------------------------------------


class JobRecord(RevisionedRecordMixin, Base):
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lease_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False)
    progress_completed: Mapped[int] = mapped_column(Integer, nullable=False)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_classification: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_event_seq: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (Index("ix_jobs_state", "state"),)


class JobStepRecord(RevisionedRecordMixin, Base):
    __tablename__ = "job_steps"

    job_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("jobs.job_id"), primary_key=True
    )
    step_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    waiting_user_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    progress_completed: Mapped[int] = mapped_column(Integer, nullable=False)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_classification: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retry_not_before: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (Index("ix_job_steps_job_id", "job_id"),)


class JobCheckpointRecord(AppendedRecordMixin, Base):
    __tablename__ = "job_checkpoints"

    checkpoint_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("jobs.job_id"), nullable=False
    )
    step_id: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "step_id"], ["job_steps.job_id", "job_steps.step_id"]
        ),
        Index("ix_job_checkpoints_job_id", "job_id"),
    )


class JobEventRecord(AppendedRecordMixin, Base):
    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("jobs.job_id"), nullable=False
    )
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    step_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    checkpoint_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("job_checkpoints.checkpoint_id"), nullable=True
    )
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    progress_completed: Mapped[int] = mapped_column(Integer, nullable=False)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "step_id"], ["job_steps.job_id", "job_steps.step_id"]
        ),
        UniqueConstraint("job_id", "event_seq"),
        Index("ix_job_events_job_id", "job_id"),
    )


# ---------------------------------------------------------------------------
# 幂等与 stale 状态（横切）
# ---------------------------------------------------------------------------


class IdempotencyRecordRow(Base):
    __tablename__ = "idempotency_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    result_type: Mapped[str] = mapped_column(String(64), nullable=False)
    result_id: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (UniqueConstraint("scope", "idempotency_key"),)


class EntityStalenessRow(Base):
    __tablename__ = "entity_staleness"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(String(256), nullable=False)
    source_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cleared_by_review_run_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("review_runs.review_run_id"), nullable=True
    )
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "target_type",
            "target_id",
            "reason",
            "source_entity_type",
            "source_entity_id",
            "source_revision",
        ),
        Index("ix_entity_staleness_target", "target_type", "target_id"),
    )


# ---------------------------------------------------------------------------
# Association tables（多值有序引用）
# ---------------------------------------------------------------------------


def _assoc_table(name: str, owner_column: str, owner_referred: str, ref_column: str, ref_referred: str) -> Table:
    """构造 ``(owner, ref, position)`` 有序关联表。

    ``owner_referred``/``ref_referred`` 为 ``"table.column"`` 形式；owner 侧可引用
    复合唯一键（如 rule_sets 的 (rule_set_id, revision)）。
    """
    return Table(
        name,
        Base.metadata,
        Column(owner_column, String(128), nullable=False),
        Column(ref_column, String(128), nullable=False),
        Column("position", Integer, nullable=False),
        UniqueConstraint(owner_column, ref_column),
        UniqueConstraint(owner_column, "position"),
        ForeignKeyConstraint([owner_column], [owner_referred]),
        ForeignKeyConstraint([ref_column], [ref_referred]),
    )


evidence_snapshot_documents = _assoc_table(
    "evidence_snapshot_documents",
    "evidence_snapshot_id",
    "evidence_snapshots.evidence_snapshot_id",
    "source_document_version_id",
    "source_document_versions.source_document_version_id",
)
clinical_fact_spans = _assoc_table(
    "clinical_fact_spans",
    "fact_id",
    "clinical_facts.fact_id",
    "evidence_span_id",
    "evidence_spans.evidence_span_id",
)
evidence_expectation_spans = _assoc_table(
    "evidence_expectation_spans",
    "expectation_id",
    "evidence_expectations.expectation_id",
    "evidence_span_id",
    "evidence_spans.evidence_span_id",
)
final_assessment_facts = _assoc_table(
    "final_assessment_facts",
    "assessment_id",
    "final_assessments.assessment_id",
    "fact_id",
    "clinical_facts.fact_id",
)
final_assessment_spans = _assoc_table(
    "final_assessment_spans",
    "assessment_id",
    "final_assessments.assessment_id",
    "evidence_span_id",
    "evidence_spans.evidence_span_id",
)
action_transition_spans = _assoc_table(
    "action_transition_spans",
    "transition_id",
    "action_transitions.transition_id",
    "evidence_span_id",
    "evidence_spans.evidence_span_id",
)
# V2 谱系的有序引用（与 legacy span/fact 关联表物理分离，绝不混写）：
# 正式评估引用 Phase 5 已发布事实与 Phase 4 locator，候选引用事实，转换引用 locator。
assessment_candidate_facts_v2 = _assoc_table(
    "assessment_candidate_facts_v2",
    "assessment_candidate_id",
    "assessment_candidates.assessment_candidate_id",
    "fact_id",
    "clinical_facts_v2.fact_id",
)
assessment_candidate_locators = _assoc_table(
    "assessment_candidate_locators",
    "assessment_candidate_id",
    "assessment_candidates.assessment_candidate_id",
    "locator_id",
    "evidence_locator_artifacts.locator_id",
)
final_assessment_facts_v2 = _assoc_table(
    "final_assessment_facts_v2",
    "assessment_id",
    "final_assessments.assessment_id",
    "fact_id",
    "clinical_facts_v2.fact_id",
)
final_assessment_locators = _assoc_table(
    "final_assessment_locators",
    "assessment_id",
    "final_assessments.assessment_id",
    "locator_id",
    "evidence_locator_artifacts.locator_id",
)
action_transition_locators = _assoc_table(
    "action_transition_locators",
    "transition_id",
    "action_transitions.transition_id",
    "locator_id",
    "evidence_locator_artifacts.locator_id",
)
agent_call_sources = Table(
    "agent_call_sources",
    Base.metadata,
    Column(
        "agent_call_id",
        String(128),
        ForeignKey("agent_calls.agent_call_id"),
        nullable=False,
    ),
    # source_ref 语义随节点类型不同（证据节点=文档ID，解构节点=方案来源定位），
    # 不设外键，由服务层校验；关联表本身仍保证有序、无逗号字符串。
    Column("source_ref", String(256), nullable=False),
    Column("position", Integer, nullable=False),
    UniqueConstraint("agent_call_id", "source_ref"),
    UniqueConstraint("agent_call_id", "position"),
)
agent_call_gate_results = _assoc_table(
    "agent_call_gate_results",
    "agent_call_id",
    "agent_calls.agent_call_id",
    "gate_result_id",
    "gate_results.gate_result_id",
)
job_step_dependencies = Table(
    "job_step_dependencies",
    Base.metadata,
    Column("job_id", String(128), nullable=False),
    Column("step_id", String(128), nullable=False),
    Column("depends_on_step_id", String(128), nullable=False),
    Column("position", Integer, nullable=False),
    ForeignKeyConstraint(
        ["job_id", "step_id"], ["job_steps.job_id", "job_steps.step_id"]
    ),
    ForeignKeyConstraint(
        ["job_id", "depends_on_step_id"],
        ["job_steps.job_id", "job_steps.step_id"],
    ),
    UniqueConstraint("job_id", "step_id", "depends_on_step_id"),
    UniqueConstraint("job_id", "step_id", "position"),
)
workflow_stage_requirements = Table(
    "workflow_stage_requirements",
    Base.metadata,
    Column(
        "workflow_stage_id",
        String(128),
        ForeignKey("workflow_stages.workflow_stage_id"),
        nullable=False,
    ),
    # requirement_id 仅在 (rule_set_id, rule_set_revision) 范围内唯一，
    # 无法作为全局外键目标；由服务层校验引用存在性。
    Column("requirement_id", String(128), nullable=False),
    Column("position", Integer, nullable=False),
    UniqueConstraint("workflow_stage_id", "requirement_id"),
    UniqueConstraint("workflow_stage_id", "position"),
)


# ---------------------------------------------------------------------------
# Phase 4 证据快照与资料版本（Slice 4.1）：独立表，注册到 Base.metadata。
# 表名/列/约束定义在 app.storage.evidence_models，迁移 0008 据此建表。
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Phase 4 上传预览/条目/确认（Slice 4.2）：独立表，注册到 Base.metadata。
# 表名/列/约束定义在 app.storage.evidence_upload_models，迁移 0008a 据此建表。
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Phase 4 OCR 持久化与基础证据处理修订（Slice 4.3）：独立表，注册到 Base.metadata。
# 表名/列/约束定义在 app.storage.ocr_models，迁移 0009 据此建表。
# ---------------------------------------------------------------------------
from app.storage import (
    evidence_models,  # noqa: F401  (register on Base.metadata)
    evidence_upload_models,  # noqa: F401  (register on Base.metadata)
    ocr_models,  # noqa: F401  (register on Base.metadata)
)
