"""Phase 5 临床事实与 Patient Profile ORM（Slice 5.1，纯存储形状，无仓储逻辑）。

与 ``app/storage/models.py`` 的 Phase 2/3 占位事实表（``clinical_facts`` /
``conflict_groups`` / ``evidence_normalization_candidates`` / ``evidence_expectations`` /
``patient_profiles``）物理隔离：Phase 5 全部使用独立 v2 表名，绝不改写旧表；迁移
``0013_clinical_facts_profile_v2``（worker_02）必须以本模块的表名/列/约束为准创建
下列表，旧占位表保持只读回归锚点，不进入任何 Phase 5 读路径。

设计书 §2.2 新写表：

- ``fact_normalization_runs``          规范化运行（冻结不可变权威元组、幂等键、
                                       PromptVersion/ModelConfig 与输入范围哈希）；
- ``fact_normalization_calls``         一次规范化调用（显式页清单；超长文档按连续
                                       页组切片）；
- ``fact_normalization_candidates``    候选完整合同（与发布表物理分离）；
- ``fact_gate_results``                逐候选门禁结果（设计书 §4.2 九步顺序）；
- ``clinical_facts_v2``                发布接受的临床事实（Gate id + 权威元组 +
                                       来源强度 + 稳定身份 + revision）；
- ``clinical_events_v2``               发布接受的事件（发生时间范围 + 记录时间 +
                                       事实/证据引用 + 来源强度）；
- ``medication_exposures_v2``          发布接受的用药/治疗暴露（保留原始药名、
                                       起止范围与持续状态）；
- ``fact_evidence_locator_links``      发布实体/期望到 Phase 4 ``EvidenceLocatorArtifact``
                                       的不可变引用（``entity_kind`` 判别，locator 外键
                                       强约束；定位只有一个真相源）；
- ``event_fact_links`` / ``exposure_fact_links`` / ``clinical_conflict_members_v2``
                                       事件/暴露/冲突组到发布事实的有序引用；
- ``clinical_conflict_groups_v2``      未解决冲突组（并列展示，不自动择优；
                                       ``resolution_revision > 0`` 只由来源校对或
                                       人工事实修订生成新 revision 后变化）；
- ``fact_rule_links_v2``               事实到已发布 RuleComponent/EvidenceRequirement
                                       的双向索引（精确身份匹配，可完全重建）；
- ``evidence_expectations_v2``         受试者级期望覆盖投影（五类状态 + 细分缺口
                                       类型，绑定权威元组与模板）；
- ``patient_profile_revisions_v2``     不可变 Profile revision（绑定权威元组、
                                       状态与首屏突出集合）。

约定与 ``evidence_models.py`` 一致：追加写记录保存 canonical JSON payload + SHA-256，
规范化列用于检索并在读取时与 payload 交叉核对；时间列统一 UTC naive。``episode_revision``
与 ``complete_processing_revision_id`` 一起冻结运行时审核节点指针，指针变化时结果
记为陈旧并拒绝发布（仓储层校验，worker_03）。候选完整 JSON、原始输出哈希、输入闭包
哈希与逐候选门禁结果保存在运行/调用/候选/门禁记录中；Agent 无权写
发布表。稳定身份 ``(stable_identity, revision)`` 唯一：同身份多来源合并为一条事实，
人工修订/增量重算追加更高 revision，绝不覆盖旧行。
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.storage.db import Base
from app.storage.evidence_models import PAYLOAD_SHA_LEN, EvidenceAppendedRecordMixin


def _rule_set_fk() -> ForeignKeyConstraint:
    """权威元组中 (rule_set_id, rule_set_revision) 到 rule_sets 的复合外键。"""
    return ForeignKeyConstraint(
        ["rule_set_id", "rule_set_revision"],
        ["rule_sets.rule_set_id", "rule_sets.revision"],
    )


class FactAuthorityColumns:
    """不可变权威元组（设计书 §2.1）规范化列：每个发布实体绑定同一活动证据快照与
    完整处理修订。``episode_revision`` 与 ``complete_processing_revision_id`` 一起
    冻结运行时审核节点指针；指针或修订变化时结果记为陈旧并拒绝发布。
    """

    @declared_attr
    def project_id(cls) -> Mapped[str]:
        return mapped_column(
            String(128), ForeignKey("projects.project_id"), nullable=False
        )

    @declared_attr
    def subject_id(cls) -> Mapped[str]:
        return mapped_column(
            String(128), ForeignKey("subjects.subject_id"), nullable=False
        )

    @declared_attr
    def review_episode_id(cls) -> Mapped[str]:
        return mapped_column(
            String(128), ForeignKey("review_episodes.review_episode_id"), nullable=False
        )

    @declared_attr
    def episode_revision(cls) -> Mapped[int]:
        return mapped_column(Integer, nullable=False)

    @declared_attr
    def protocol_version_id(cls) -> Mapped[str]:
        return mapped_column(
            String(128),
            ForeignKey("protocol_document_versions.protocol_version_id"),
            nullable=False,
        )

    @declared_attr
    def rule_set_id(cls) -> Mapped[str]:
        return mapped_column(String(128), nullable=False)

    @declared_attr
    def rule_set_revision(cls) -> Mapped[int]:
        return mapped_column(Integer, nullable=False)

    @declared_attr
    def evidence_snapshot_v2_id(cls) -> Mapped[str]:
        return mapped_column(
            String(128),
            ForeignKey("evidence_snapshots_v2.evidence_snapshot_id"),
            nullable=False,
        )

    @declared_attr
    def complete_processing_revision_id(cls) -> Mapped[str]:
        return mapped_column(
            String(128),
            ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"),
            nullable=False,
        )


# ---------------------------------------------------------------------------
# 运行 / 调用 / 门禁记录
# ---------------------------------------------------------------------------


class FactNormalizationRunRecord(EvidenceAppendedRecordMixin, FactAuthorityColumns, Base):
    """一次规范化运行：冻结权威元组、幂等键、Prompt/ModelConfig 与输入范围哈希。

    ``idempotency_key`` 全局唯一：同一活动处理修订、PromptVersion、ModelConfig 与
    输入范围重复运行不得创建重复事实或 Profile；重复提交返回原运行（仓储层按键
    复用，不伪造 Phase 6 ReviewRun）。``job_id`` 可空关联持久 Job 设施。
    """

    __tablename__ = "fact_normalization_runs"

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )
    prompt_version_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("prompt_versions.prompt_version_id"), nullable=False
    )
    model_config_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("model_configs.model_config_id"), nullable=False
    )
    input_scope_sha256: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    job_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("jobs.job_id"), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        _rule_set_fk(),
        UniqueConstraint("idempotency_key", name="uq_fact_normalization_runs_idempotency_key"),
        Index("ix_fnr_review_episode_id", "review_episode_id"),
        Index("ix_fnr_complete_processing_revision_id", "complete_processing_revision_id"),
        Index("ix_fnr_status", "status"),
    )


class FactNormalizationCallRecord(EvidenceAppendedRecordMixin, Base):
    """一次规范化调用：默认每个逻辑文档一次；超长文档按连续页组切片。

    每次调用显式声明页清单（``page_numbers_json``），页覆盖门禁要求所有页已处理或
    有逐页未解决原因；整页遗漏、空输出、跨节点定位、虚构定位或活动指针变化均失败，
    不生成空 Profile。
    """

    __tablename__ = "fact_normalization_calls"

    call_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("fact_normalization_runs.run_id"), nullable=False
    )
    logical_document_id: Mapped[str] = mapped_column(String(128), nullable=False)
    page_numbers_json: Mapped[list] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    input_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    raw_output_sha256: Mapped[str | None] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("call_id", "run_id", name="uq_fnc_call_run"),
        Index("ix_fnc_run_id", "run_id"),
        Index("ix_fnc_logical_document_id", "logical_document_id"),
    )


class FactNormalizationCandidateRecord(EvidenceAppendedRecordMixin, Base):
    """规范化候选的不可变完整合同，与发布实体物理分离。"""

    __tablename__ = "fact_normalization_candidates"

    candidate_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("fact_normalization_runs.run_id"), nullable=False
    )
    call_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("fact_normalization_calls.call_id"), nullable=False
    )
    candidate_kind: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["call_id", "run_id"],
            ["fact_normalization_calls.call_id", "fact_normalization_calls.run_id"],
            name="fk_fncandidate_call_run",
        ),
        UniqueConstraint(
            "candidate_id", "call_id", "run_id", name="uq_fncandidate_id_call_run"
        ),
        CheckConstraint(
            "candidate_kind IN ('fact', 'event', 'exposure')",
            name="ck_fncandidate_kind",
        ),
        Index("ix_fncandidate_run_id", "run_id"),
        Index("ix_fncandidate_call_id", "call_id"),
    )


class FactGateResultRecord(EvidenceAppendedRecordMixin, Base):
    """逐候选门禁结果（设计书 §4.2 九步顺序）；ACCEPTED 可空原因，REJECTED/BLOCKED
    必须有原因。``candidate_id`` 外键绑定门禁实际审查的不可变候选合同。
    """

    __tablename__ = "fact_gate_results"

    gate_result_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("fact_normalization_runs.run_id"), nullable=False
    )
    call_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("fact_normalization_calls.call_id"), nullable=False
    )
    candidate_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("fact_normalization_candidates.candidate_id"),
        nullable=False,
    )
    gate: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    reasons_json: Mapped[list] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["call_id", "run_id"],
            ["fact_normalization_calls.call_id", "fact_normalization_calls.run_id"],
            name="fk_fgr_call_run",
        ),
        ForeignKeyConstraint(
            ["candidate_id", "call_id", "run_id"],
            [
                "fact_normalization_candidates.candidate_id",
                "fact_normalization_candidates.call_id",
                "fact_normalization_candidates.run_id",
            ],
            name="fk_fgr_candidate_call_run",
        ),
        UniqueConstraint("candidate_id", "gate", name="uq_fgr_candidate_gate"),
        Index("ix_fgr_run_id", "run_id"),
        Index("ix_fgr_call_id", "call_id"),
        Index("ix_fgr_candidate_id", "candidate_id"),
    )


# ---------------------------------------------------------------------------
# 发布实体：事实 / 事件 / 暴露 / 冲突组
# ---------------------------------------------------------------------------


class ClinicalFactV2Record(EvidenceAppendedRecordMixin, FactAuthorityColumns, Base):
    """发布接受的临床事实：绑定权威元组、Gate id、来源强度与稳定身份。

    未知极性不得携带被断言值（``value_json`` 可空）；肯定/否定事实必须携带明确断言
    依据（``assertion_*`` 列）。``stable_identity`` 由权威元组/类型/极性/规范值/单位/
    日期范围推导，不含置信度与定位；``(stable_identity, revision)`` 唯一，同身份多
    来源合并为一条事实并保留全部定位（``fact_evidence_locator_links``）。
    """

    __tablename__ = "clinical_facts_v2"

    fact_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("fact_normalization_runs.run_id"), nullable=False
    )
    gate_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("fact_gate_results.gate_result_id"), nullable=False
    )
    fact_type: Mapped[str] = mapped_column(String(128), nullable=False)
    polarity: Mapped[str] = mapped_column(String(16), nullable=False)
    value_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_strength: Mapped[str] = mapped_column(String(32), nullable=False)
    date_precision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    date_lower_bound: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_upper_bound: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    record_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    assertion_object: Mapped[str | None] = mapped_column(String(256), nullable=True)
    assertion_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    assertion_locator_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("evidence_locator_artifacts.locator_id"), nullable=True
    )
    assertion_source_text_sha256: Mapped[str | None] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=True
    )
    stable_identity: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        _rule_set_fk(),
        UniqueConstraint("stable_identity", "revision", name="uq_cfv2_stable_identity_revision"),
        Index("ix_cfv2_review_episode_id", "review_episode_id"),
        Index("ix_cfv2_subject_fact_type", "subject_id", "fact_type"),
    )


class ClinicalEventV2Record(EvidenceAppendedRecordMixin, FactAuthorityColumns, Base):
    """发布接受的事件：发生时间范围、记录时间、事实/证据定位引用与来源强度。

    事件的事实引用（``event_fact_links``）与证据定位引用（
    ``fact_evidence_locator_links``）必须属于同一审核节点与处理修订（权威元组一致），
    跨实体核对在仓储层执行；本表保证 ``(stable_identity, revision)`` 唯一。
    """

    __tablename__ = "clinical_events_v2"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("fact_normalization_runs.run_id"), nullable=False
    )
    gate_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("fact_gate_results.gate_result_id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    start_precision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    start_lower_bound: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_upper_bound: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    end_precision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    end_lower_bound: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_upper_bound: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_status: Mapped[str] = mapped_column(String(16), nullable=False)
    record_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_strength: Mapped[str] = mapped_column(String(32), nullable=False)
    stable_identity: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        _rule_set_fk(),
        UniqueConstraint("stable_identity", "revision", name="uq_cev2_stable_identity_revision"),
        Index("ix_cev2_review_episode_id", "review_episode_id"),
        Index("ix_cev2_event_type", "event_type"),
    )


class MedicationExposureV2Record(EvidenceAppendedRecordMixin, FactAuthorityColumns, Base):
    """发布接受的用药/治疗暴露：保留原始药名、类别、适应证、剂量/单位/频次/途径、
    起止日期范围与持续状态；本阶段不判断是否违反洗脱期。ENDED 必须由资料明确给出
    终止信息（不得由“既往”推断）；ONGOING 不得携带终止范围（合同层校验）。
    """

    __tablename__ = "medication_exposures_v2"

    exposure_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("fact_normalization_runs.run_id"), nullable=False
    )
    gate_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("fact_gate_results.gate_result_id"), nullable=False
    )
    medication_name: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    indication: Mapped[str | None] = mapped_column(Text, nullable=True)
    dose: Mapped[str | None] = mapped_column(String(128), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(128), nullable=True)
    route: Mapped[str | None] = mapped_column(String(128), nullable=True)
    start_precision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    start_lower_bound: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_upper_bound: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    end_precision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    end_lower_bound: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_upper_bound: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_status: Mapped[str] = mapped_column(String(16), nullable=False)
    record_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_strength: Mapped[str] = mapped_column(String(32), nullable=False)
    stable_identity: Mapped[str] = mapped_column(
        String(PAYLOAD_SHA_LEN), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        _rule_set_fk(),
        UniqueConstraint("stable_identity", "revision", name="uq_mev2_stable_identity_revision"),
        Index("ix_mev2_review_episode_id", "review_episode_id"),
        Index("ix_mev2_medication_name", "medication_name"),
    )


class ClinicalConflictGroupV2Record(EvidenceAppendedRecordMixin, FactAuthorityColumns, Base):
    """同一语义对象的不同来源不兼容值/极性/日期/持续状态时的未解决冲突组。

    冲突并列展示，不自动择优或覆盖；``resolution_revision > 0`` 只由来源校对或
    人工事实修订生成新 revision 后变化，Agent 无权选择赢家。成员事实按
    ``clinical_conflict_members_v2`` 有序引用。
    """

    __tablename__ = "clinical_conflict_groups_v2"

    conflict_group_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("fact_normalization_runs.run_id"), nullable=False
    )
    gate_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("fact_gate_results.gate_result_id"), nullable=False
    )
    resolution_revision: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        _rule_set_fk(),
        CheckConstraint(
            "resolution_revision = 0", name="ck_ccgv2_unresolved_slice51"
        ),
        Index("ix_ccgv2_review_episode_id", "review_episode_id"),
        Index("ix_ccgv2_subject_id", "subject_id"),
    )


# ---------------------------------------------------------------------------
# 有序引用（关联表）
# ---------------------------------------------------------------------------


class FactEvidenceLocatorLinkRecord(Base):
    """发布实体/期望到 Phase 4 ``EvidenceLocatorArtifact`` 的不可变引用。

    ``entity_kind`` 判别实体种类（fact/event/exposure/conflict/expectation）；
    ``(entity_kind, entity_id, position)`` 复合主键保证每个实体的有序定位闭包唯一。
    locator 外键强约束：候选只能引用当前完整处理修订闭包中的 locator id，残余的
    新定位建议须经过 Phase 4 定位门禁后才可引用。定位只有一个真相源，不复制出
    另一套可漂移的定位真相。
    """

    __tablename__ = "fact_evidence_locator_links"

    entity_kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    locator_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("evidence_locator_artifacts.locator_id"), nullable=False
    )
    fact_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("clinical_facts_v2.fact_id"), nullable=True
    )
    event_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("clinical_events_v2.event_id"), nullable=True
    )
    exposure_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("medication_exposures_v2.exposure_id"), nullable=True
    )
    conflict_group_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("clinical_conflict_groups_v2.conflict_group_id"),
        nullable=True,
    )
    expectation_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("evidence_expectations_v2.expectation_id"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "entity_kind IN ('fact', 'event', 'exposure', 'conflict', 'expectation')",
            name="ck_fel_entity_kind",
        ),
        CheckConstraint(
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
        UniqueConstraint("entity_kind", "entity_id", "locator_id", name="uq_fel_entity_locator"),
        Index("ix_fel_locator_id", "locator_id"),
    )


class EventFactLinkRecord(Base):
    """发布事件到发布事实的有序引用（``(event_id, position)`` 主键）。"""

    __tablename__ = "event_fact_links"

    event_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("clinical_events_v2.event_id"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    fact_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("clinical_facts_v2.fact_id"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("event_id", "fact_id", name="uq_efl_event_fact"),
        Index("ix_efl_fact_id", "fact_id"),
    )


class ExposureFactLinkRecord(Base):
    """发布暴露到发布事实的有序引用（``(exposure_id, position)`` 主键）。"""

    __tablename__ = "exposure_fact_links"

    exposure_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("medication_exposures_v2.exposure_id"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    fact_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("clinical_facts_v2.fact_id"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("exposure_id", "fact_id", name="uq_xfl_exposure_fact"),
        Index("ix_xfl_fact_id", "fact_id"),
    )


class ClinicalConflictMemberV2Record(Base):
    """冲突组成员事实的有序引用（``(conflict_group_id, position)`` 主键）。

    同一冲突组至少两名成员（合同层校验，``fact_ids`` min_length=2）。
    """

    __tablename__ = "clinical_conflict_members_v2"

    conflict_group_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("clinical_conflict_groups_v2.conflict_group_id"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    fact_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("clinical_facts_v2.fact_id"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("conflict_group_id", "fact_id", name="uq_ccm_conflict_fact"),
        Index("ix_ccm_fact_id", "fact_id"),
    )


# ---------------------------------------------------------------------------
# 规则索引 / 资料期望 / Profile revision
# ---------------------------------------------------------------------------


class FactRuleLinkV2Record(Base):
    """事实到已发布 RuleComponent/EvidenceRequirement 的双向索引。

    只基于明确身份和版本化映射建立；``target_kind`` 判别目标种类，``rule_set_id`` +
    ``rule_set_revision`` 绑定规则集（复合外键），``target_id`` 为目标主键（
    rule_component_id 或 requirement_id，外键目标随种类不同，存在性由仓储层校验）。
    禁止自由文本模糊相似度；索引可完全重建且不写回方案规则。
    """

    __tablename__ = "fact_rule_links_v2"

    link_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    fact_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("clinical_facts_v2.fact_id"), nullable=False
    )
    target_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_set_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_set_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_component_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    evidence_requirement_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )

    __table_args__ = (
        _rule_set_fk(),
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision", "rule_component_id"],
            [
                "rule_components.rule_set_id",
                "rule_components.rule_set_revision",
                "rule_components.rule_component_id",
            ],
            name="fk_frl_rule_component",
        ),
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision", "evidence_requirement_id"],
            [
                "evidence_requirements.rule_set_id",
                "evidence_requirements.rule_set_revision",
                "evidence_requirements.requirement_id",
            ],
            name="fk_frl_evidence_requirement",
        ),
        CheckConstraint(
            "target_kind IN ('rule_component', 'evidence_requirement')",
            name="ck_frl_target_kind",
        ),
        CheckConstraint(
            "(target_kind = 'rule_component' AND rule_component_id = target_id "
            "AND evidence_requirement_id IS NULL) OR "
            "(target_kind = 'evidence_requirement' AND evidence_requirement_id = target_id "
            "AND rule_component_id IS NULL)",
            name="ck_frl_target_parent",
        ),
        UniqueConstraint("fact_id", "target_kind", "target_id", name="uq_frl_fact_target"),
        Index("ix_frl_target_kind_target", "target_kind", "target_id"),
        Index("ix_frl_rule_set", "rule_set_id", "rule_set_revision"),
    )


class EvidenceExpectationV2Record(EvidenceAppendedRecordMixin, FactAuthorityColumns, Base):
    """受试者级期望覆盖投影（五类状态 + 细分缺口类型，绑定权威元组与模板）。

    从当前审核节点绑定的 ``EvidenceExpectationTemplate`` 确定性投影；覆盖状态必须
    给出定位引用（``fact_evidence_locator_links``，entity_kind='expectation'）、具体
    缺口类型（``gap_type``）与关联规则（模板 requirement）。``(review_episode_id,
    template_id, revision)`` 唯一：同一节点同一模板的刷新追加更高 revision，绝不覆盖
    旧投影。沉默/未提及/缺页只形成期望缺口，不生成否认或正常事实。
    """

    __tablename__ = "evidence_expectations_v2"

    expectation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    template_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_expectation_templates.template_id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    gap_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        _rule_set_fk(),
        UniqueConstraint(
            "review_episode_id", "template_id", "revision",
            name="uq_eev2_episode_template_revision",
        ),
        Index("ix_eev2_review_episode_id", "review_episode_id"),
        Index("ix_eev2_template_id", "template_id"),
        Index("ix_eev2_status", "status"),
    )


class PatientProfileRevisionV2Record(
    EvidenceAppendedRecordMixin, FactAuthorityColumns, Base
):
    """不可变 Profile revision：绑定权威元组、状态与首屏突出集合。

    每个 Profile 均带审核节点、证据快照和处理修订身份；``(review_episode_id,
    revision)`` 唯一，增量重算追加新 revision，旧 revision 可按原权威元组回放，
    后期节点资料不静默改写早期审核节点的活动 Profile。``status`` 稳定机器值：
    succeeded / generating / failed / stale（活动证据版本变化时旧 Profile 标记为
    stale 并创建新 revision）。``highlights_json`` 为首屏突出集合的确定性投影。
    """

    __tablename__ = "patient_profile_revisions_v2"

    patient_profile_revision_id: Mapped[str] = mapped_column(
        String(128), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    highlights_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        _rule_set_fk(),
        CheckConstraint(
            "status IN ('succeeded', 'generating', 'failed', 'stale')",
            name="ck_pprv2_status",
        ),
        UniqueConstraint("review_episode_id", "revision", name="uq_pprv2_episode_revision"),
        Index("ix_pprv2_review_episode_id", "review_episode_id"),
        Index("ix_pprv2_status", "status"),
    )
