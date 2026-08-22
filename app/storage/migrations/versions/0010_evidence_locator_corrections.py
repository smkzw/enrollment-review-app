"""Slice 4.4 定位、风险、校对、完整处理修订、处理候选与活动版本（WP-44A）。

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-19

本迁移只做追加/修复，不回写 4.3 原 OCR、基础修订 payload/hash 或页清单，也不按
时间/ID/历史 ``ACTIVE`` 状态回填活动指针：

1. ``evidence_processing_revisions`` 追加 base/complete 辨别列
   ``revision_kind``（默认 ``base``）、可空 ``base_processing_revision_id``（自引用
   外键）与可空 ``completion_manifest_sha256``。迁移前的 4.3 行保持
   ``revision_kind='base'``、payload/hash 逐字不变、永不可激活。
2. 重建 ``review_episodes``：legacy ``evidence_snapshot_id`` 保留原义（含
   deferrable FK），新增可空成对活动指针 ``active_evidence_snapshot_id`` 与
   ``active_evidence_processing_revision_id``（FK 到 0008/0009 表）并加 CHECK
   「同时为空或同时非空」。重建采用「建新表 -> 拷贝 -> 删旧表 -> 改名」，
   子表引用外键与全部行原样保留，重建完成后用 ``PRAGMA foreign_key_check`` 验证。
   迁移不按任何字段回填指针；升级时全部保持 NULL，由正式激活命令建立。
3. 新增 17 张 Slice 4.4 旁路工件/事件/关联表（见 ``evidence_locator_models.py``）。

降级只在「空绿地库」允许：任一 0010 表有行、任一活动指针非空、任一修订
``revision_kind != base`` 或 ``base_processing_revision_id``/``completion_manifest_sha256``
非空时，必须拒绝有损降级（由管理器从迁移前备份恢复），不得静默丢弃不可变历史。
"""
from collections.abc import Sequence

from alembic import op
from sqlalchemy import (
    JSON,
    Boolean,
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

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PAYLOAD_SHA_LEN = 64

#: 降级时按依赖逆序检查是否被正式数据占用。
_SLICE44_TABLES = (
    "processing_revision_resolutions",
    "processing_revision_referenced_documents",
    "processing_revision_metadata_revisions",
    "processing_revision_corrections",
    "processing_revision_risk_reviews",
    "processing_revision_risk_scans",
    "processing_revision_locators",
    "evidence_activation_events",
    "evidence_processing_candidate_events",
    "evidence_processing_candidates",
    "referenced_document_resolution_revisions",
    "referenced_document_revisions",
    "correction_records",
    "ocr_risk_reviews",
    "ocr_risk_flags",
    "ocr_risk_scans",
    "evidence_locator_artifacts",
)

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(referred_table_name)s_%(column_0_N_name)s",
        "pk": "pk_%(table_name)s",
    }
)

# 0002/0008/0008a/0009 父表；轻量 stub 只用于解析外键，不重建父表。
projects = Table(
    "projects", metadata, Column("project_id", String(128), primary_key=True)
)
subjects = Table(
    "subjects", metadata, Column("subject_id", String(128), primary_key=True)
)
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
page_artifacts = Table(
    "page_artifacts", metadata, Column("page_artifact_id", String(128), primary_key=True)
)
ocr_pages = Table(
    "ocr_pages", metadata, Column("ocr_page_id", String(128), primary_key=True)
)
source_document_versions_v2 = Table(
    "source_document_versions_v2",
    metadata,
    Column("source_document_version_id", String(128), primary_key=True),
)
source_document_metadata_revisions = Table(
    "source_document_metadata_revisions",
    metadata,
    Column("metadata_revision_id", String(128), primary_key=True),
)
jobs = Table("jobs", metadata, Column("job_id", String(128), primary_key=True))
review_episodes_stub = Table(
    "review_episodes", metadata, Column("review_episode_id", String(128), primary_key=True)
)


def _new_review_episodes_table(table_name: str, target: MetaData) -> Table:
    """0002 形状 + Slice 4.4 成对活动指针（legacy evidence_snapshot_id 原义保留）。"""
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


def _legacy_review_episodes_table(table_name: str, target: MetaData) -> Table:
    """0002 形状（无活动指针），用于降级回 0009。"""
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
        Column("anchor_dates_json", JSON, nullable=False),
        Column("due_at", DateTime, nullable=True),
        Column("revision", Integer, nullable=False),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
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
        ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
    )
    Index("ix_review_episodes_subject_id", table.c.subject_id)
    Index("ix_review_episodes_project_id", table.c.project_id)
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
_downgrade_projects = Table(
    "projects", downgrade_metadata, Column("project_id", String(128), primary_key=True)
)
_downgrade_subjects = Table(
    "subjects", downgrade_metadata, Column("subject_id", String(128), primary_key=True)
)
_downgrade_rule_sets = Table(
    "rule_sets",
    downgrade_metadata,
    Column("rule_set_id", String(128), primary_key=True),
    Column("revision", Integer, primary_key=True),
)
_downgrade_protocol_document_versions = Table(
    "protocol_document_versions",
    downgrade_metadata,
    Column("protocol_version_id", String(128), primary_key=True),
)
_downgrade_evidence_snapshots = Table(
    "evidence_snapshots",
    downgrade_metadata,
    Column("evidence_snapshot_id", String(128), primary_key=True),
)


def _assoc_table(name: str, ref_column: str, ref_target: str) -> Table:
    return Table(
        name,
        metadata,
        Column("revision_id", String(128), nullable=False, primary_key=True),
        Column("position", Integer, nullable=False, primary_key=True),
        Column(ref_column, String(128), nullable=False),
        ForeignKeyConstraint(
            ["revision_id"],
            ["evidence_processing_revisions.evidence_processing_revision_id"],
        ),
        ForeignKeyConstraint([ref_column], [ref_target]),
    )


# 升级新建的表（列/约束以 evidence_locator_models.py 为准）。
evidence_locator_artifacts = Table(
    "evidence_locator_artifacts",
    metadata,
    Column("locator_id", String(128), primary_key=True),
    Column("page_artifact_id", String(128), nullable=False),
    Column("ocr_page_id", String(128), nullable=True),
    Column("source_document_version_id", String(128), nullable=False),
    Column("page_number", Integer, nullable=False),
    Column("source_layer", String(16), nullable=False),
    Column("source_text_sha256", String(64), nullable=False),
    Column("target_id", String(128), nullable=False),
    Column("precision", String(16), nullable=False),
    Column("bbox_x0", Float, nullable=True),
    Column("bbox_y0", Float, nullable=True),
    Column("bbox_x1", Float, nullable=True),
    Column("bbox_y1", Float, nullable=True),
    Column("coordinate_space", String(32), nullable=True),
    Column("frame_page_width", Float, nullable=True),
    Column("frame_page_height", Float, nullable=True),
    Column("frame_rotation", Integer, nullable=True),
    Column("transform_version", String(128), nullable=True),
    Column("sidecar_sha256", String(64), nullable=True),
    Column("text_start", Integer, nullable=True),
    Column("text_end", Integer, nullable=True),
    Column("excerpt", Text, nullable=True),
    Column("anchor_hash", String(64), nullable=True),
    Column("disambiguation", String(32), nullable=False),
    Column("locator_algorithm_version", String(128), nullable=False),
    Column("coordinate_transform_version", String(128), nullable=True),
    Column("authenticity", String(16), nullable=False),
    Column("effective_text_sha256", String(64), nullable=True),
    Column("processing_revision_id", String(128), nullable=True),
    Column("match_confidence", Float, nullable=True),
    Column("degradation_reason", Text, nullable=True),
    Column("payload_json", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
    ForeignKeyConstraint(["page_artifact_id"], ["page_artifacts.page_artifact_id"]),
    ForeignKeyConstraint(["ocr_page_id"], ["ocr_pages.ocr_page_id"]),
    ForeignKeyConstraint(
        ["source_document_version_id"],
        ["source_document_versions_v2.source_document_version_id"],
    ),
    ForeignKeyConstraint(
        ["processing_revision_id"],
        ["evidence_processing_revisions.evidence_processing_revision_id"],
    ),
)
Index("ix_locator_page_artifact_id", evidence_locator_artifacts.c.page_artifact_id)
Index("ix_locator_target_id", evidence_locator_artifacts.c.target_id)

ocr_risk_scans = Table(
    "ocr_risk_scans",
    metadata,
    Column("scan_id", String(128), primary_key=True),
    Column("ocr_page_id", String(128), nullable=False),
    Column("raw_text_sha256", String(64), nullable=False),
    Column("scanner_rule_version", String(128), nullable=False),
    Column("flags_sha256", String(64), nullable=False),
    Column("coverage_status", String(32), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
    ForeignKeyConstraint(["ocr_page_id"], ["ocr_pages.ocr_page_id"]),
    UniqueConstraint(
        "ocr_page_id",
        "raw_text_sha256",
        "scanner_rule_version",
        name="uq_ocr_risk_scans_triple",
    ),
)
Index("ix_ocr_risk_scans_ocr_page_id", ocr_risk_scans.c.ocr_page_id)

ocr_risk_flags = Table(
    "ocr_risk_flags",
    metadata,
    Column("flag_id", String(128), primary_key=True),
    Column("scan_id", String(128), nullable=False),
    Column("risk_id", String(128), nullable=False),
    Column("ocr_page_id", String(128), nullable=False),
    Column("raw_text_sha256", String(64), nullable=False),
    Column("kind", String(32), nullable=False),
    Column("level", String(16), nullable=False),
    Column("text", Text, nullable=False),
    Column("text_start", Integer, nullable=False),
    Column("text_end", Integer, nullable=False),
    Column("detail", Text, nullable=True),
    Column("rule_version", String(128), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
    ForeignKeyConstraint(["scan_id"], ["ocr_risk_scans.scan_id"]),
    ForeignKeyConstraint(["ocr_page_id"], ["ocr_pages.ocr_page_id"]),
    UniqueConstraint("scan_id", "risk_id", name="uq_ocr_risk_flags_scan_risk"),
)
Index("ix_ocr_risk_flags_ocr_page_id", ocr_risk_flags.c.ocr_page_id)

ocr_risk_reviews = Table(
    "ocr_risk_reviews",
    metadata,
    Column("review_id", String(128), primary_key=True),
    Column("risk_flag_id", String(128), nullable=False),
    Column("decision", String(32), nullable=False),
    Column("reason", Text, nullable=False),
    Column("actor", String(128), nullable=False),
    Column("base_processing_revision_id", String(128), nullable=False),
    Column("expected_revision", Integer, nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
    ForeignKeyConstraint(["risk_flag_id"], ["ocr_risk_flags.flag_id"]),
    ForeignKeyConstraint(
        ["base_processing_revision_id"],
        ["evidence_processing_revisions.evidence_processing_revision_id"],
    ),
)
Index("ix_ocr_risk_reviews_risk_flag_id", ocr_risk_reviews.c.risk_flag_id)

correction_records = Table(
    "correction_records",
    metadata,
    Column("correction_id", String(128), primary_key=True),
    Column("ocr_page_id", String(128), nullable=False),
    Column("raw_text_sha256", String(64), nullable=False),
    Column("text_start", Integer, nullable=False),
    Column("text_end", Integer, nullable=False),
    Column("original_text", Text, nullable=False),
    Column("corrected_text", Text, nullable=False),
    Column("change_kind", String(32), nullable=False),
    Column("requires_confirmation", Boolean, nullable=False),
    Column("confirmation_actor", String(128), nullable=True),
    Column("confirmation_at", DateTime, nullable=True),
    Column("reason", Text, nullable=False),
    Column("actor", String(128), nullable=False),
    Column("base_processing_revision_id", String(128), nullable=False),
    Column("supersedes_correction_id", String(128), nullable=True),
    Column("affected_scope_json", JSON, nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
    ForeignKeyConstraint(["ocr_page_id"], ["ocr_pages.ocr_page_id"]),
    ForeignKeyConstraint(
        ["base_processing_revision_id"],
        ["evidence_processing_revisions.evidence_processing_revision_id"],
    ),
    ForeignKeyConstraint(
        ["supersedes_correction_id"], ["correction_records.correction_id"]
    ),
    UniqueConstraint(
        "supersedes_correction_id", name="uq_correction_single_successor"
    ),
)
Index("ix_correction_ocr_page_id", correction_records.c.ocr_page_id)
Index("ix_correction_supersedes", correction_records.c.supersedes_correction_id)
Index(
    "uq_correction_single_root",
    correction_records.c.base_processing_revision_id,
    correction_records.c.ocr_page_id,
    correction_records.c.raw_text_sha256,
    correction_records.c.text_start,
    correction_records.c.text_end,
    unique=True,
    sqlite_where=correction_records.c.supersedes_correction_id.is_(None),
)

referenced_document_revisions = Table(
    "referenced_document_revisions",
    metadata,
    Column("revision_id", String(128), primary_key=True),
    Column("referenced_document_id", String(128), nullable=False),
    Column("project_id", String(128), nullable=False),
    Column("subject_id", String(128), nullable=False),
    Column("review_episode_id", String(128), nullable=False),
    Column("description", Text, nullable=False),
    Column("document_type", String(128), nullable=True),
    Column("source_party", String(128), nullable=True),
    Column("trigger_locator_id", String(128), nullable=True),
    Column("origin", String(32), nullable=False),
    Column("pattern_version", String(128), nullable=True),
    Column("status", String(16), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("supersedes_revision_id", String(128), nullable=True),
    Column("created_by", String(128), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
    ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
    ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
    ForeignKeyConstraint(["review_episode_id"], ["review_episodes.review_episode_id"]),
    ForeignKeyConstraint(
        ["trigger_locator_id"], ["evidence_locator_artifacts.locator_id"]
    ),
    ForeignKeyConstraint(
        ["supersedes_revision_id"], ["referenced_document_revisions.revision_id"]
    ),
    UniqueConstraint(
        "referenced_document_id", "revision", name="uq_refdoc_revision_chain"
    ),
    UniqueConstraint(
        "supersedes_revision_id", name="uq_refdoc_revision_single_successor"
    ),
)
Index("ix_refdoc_review_episode_id", referenced_document_revisions.c.review_episode_id)

referenced_document_resolution_revisions = Table(
    "referenced_document_resolution_revisions",
    metadata,
    Column("resolution_revision_id", String(128), primary_key=True),
    Column("referenced_document_id", String(128), nullable=False),
    Column("status", String(16), nullable=False),
    Column("source_document_version_id", String(128), nullable=True),
    Column("revision", Integer, nullable=False),
    Column("supersedes_resolution_revision_id", String(128), nullable=True),
    Column("created_by", String(128), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
    ForeignKeyConstraint(
        ["source_document_version_id"],
        ["source_document_versions_v2.source_document_version_id"],
    ),
    ForeignKeyConstraint(
        ["supersedes_resolution_revision_id"],
        ["referenced_document_resolution_revisions.resolution_revision_id"],
    ),
    UniqueConstraint(
        "referenced_document_id", "revision", name="uq_refdoc_resolution_chain"
    ),
    UniqueConstraint(
        "supersedes_resolution_revision_id",
        name="uq_refdoc_resolution_single_successor",
    ),
)

evidence_activation_events = Table(
    "evidence_activation_events",
    metadata,
    Column("event_id", String(128), primary_key=True),
    Column("review_episode_id", String(128), nullable=False),
    Column("activation_seq", Integer, nullable=False),
    Column("event_kind", String(16), nullable=False),
    Column("from_snapshot_id", String(128), nullable=True),
    Column("from_revision_id", String(128), nullable=True),
    Column("to_snapshot_id", String(128), nullable=False),
    Column("to_revision_id", String(128), nullable=False),
    Column("reason", Text, nullable=False),
    Column("actor", String(128), nullable=False),
    Column("job_id", String(128), nullable=True),
    Column("candidate_id", String(128), nullable=True),
    Column("expected_revision", Integer, nullable=False),
    Column("resulting_episode_revision", Integer, nullable=False),
    Column("snapshot_status_transitioned", Boolean, nullable=False),
    Column("command_sha256", String(64), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
    ForeignKeyConstraint(["review_episode_id"], ["review_episodes.review_episode_id"]),
    ForeignKeyConstraint(
        ["from_snapshot_id"], ["evidence_snapshots_v2.evidence_snapshot_id"]
    ),
    ForeignKeyConstraint(
        ["from_revision_id"],
        ["evidence_processing_revisions.evidence_processing_revision_id"],
    ),
    ForeignKeyConstraint(
        ["to_snapshot_id"], ["evidence_snapshots_v2.evidence_snapshot_id"]
    ),
    ForeignKeyConstraint(
        ["to_revision_id"],
        ["evidence_processing_revisions.evidence_processing_revision_id"],
    ),
    ForeignKeyConstraint(["job_id"], ["jobs.job_id"]),
    ForeignKeyConstraint(
        ["candidate_id"], ["evidence_processing_candidates.candidate_id"]
    ),
    UniqueConstraint(
        "review_episode_id", "activation_seq", name="uq_activation_event_seq"
    ),
)
Index("ix_activation_event_episode", evidence_activation_events.c.review_episode_id)

evidence_processing_candidates = Table(
    "evidence_processing_candidates",
    metadata,
    Column("candidate_id", String(128), primary_key=True),
    Column("evidence_snapshot_id", String(128), nullable=False),
    Column("base_processing_revision_id", String(128), nullable=False),
    Column("project_id", String(128), nullable=False),
    Column("subject_id", String(128), nullable=False),
    Column("review_episode_id", String(128), nullable=False),
    Column("expected_revision", Integer, nullable=False),
    Column("job_id", String(128), nullable=True),
    Column("idempotency_key", String(128), nullable=False),
    Column("candidate_input_sha256", String(64), nullable=False),
    Column("scanner_rule_version", String(128), nullable=False),
    Column("selected_locator_ids_json", JSON, nullable=False),
    Column("complete_revision_id", String(128), nullable=True),
    Column("status", String(32), nullable=False),
    Column("created_by", String(128), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
    ForeignKeyConstraint(
        ["evidence_snapshot_id"], ["evidence_snapshots_v2.evidence_snapshot_id"]
    ),
    ForeignKeyConstraint(
        ["base_processing_revision_id"],
        ["evidence_processing_revisions.evidence_processing_revision_id"],
    ),
    ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
    ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
    ForeignKeyConstraint(["review_episode_id"], ["review_episodes.review_episode_id"]),
    ForeignKeyConstraint(["job_id"], ["jobs.job_id"]),
    ForeignKeyConstraint(
        ["complete_revision_id"],
        ["evidence_processing_revisions.evidence_processing_revision_id"],
    ),
    UniqueConstraint("idempotency_key", name="uq_candidate_idempotency_key"),
    UniqueConstraint(
        "complete_revision_id", name="uq_candidate_complete_revision_id"
    ),
)
Index("ix_candidate_review_episode_id", evidence_processing_candidates.c.review_episode_id)

evidence_processing_candidate_events = Table(
    "evidence_processing_candidate_events",
    metadata,
    Column("candidate_id", String(128), nullable=False, primary_key=True),
    Column("seq", Integer, nullable=False, primary_key=True),
    Column("from_status", String(32), nullable=False),
    Column("to_status", String(32), nullable=False),
    Column("event_kind", String(32), nullable=False),
    Column("actor", String(128), nullable=False),
    Column("reason", Text, nullable=False),
    Column("complete_revision_id", String(128), nullable=True),
    Column("payload_json", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
    ForeignKeyConstraint(
        ["candidate_id"], ["evidence_processing_candidates.candidate_id"]
    ),
    ForeignKeyConstraint(
        ["complete_revision_id"],
        ["evidence_processing_revisions.evidence_processing_revision_id"],
    ),
)

processing_revision_locators = _assoc_table(
    "processing_revision_locators", "locator_id", "evidence_locator_artifacts.locator_id"
)
processing_revision_risk_scans = _assoc_table(
    "processing_revision_risk_scans", "scan_id", "ocr_risk_scans.scan_id"
)
processing_revision_risk_reviews = _assoc_table(
    "processing_revision_risk_reviews", "review_id", "ocr_risk_reviews.review_id"
)
processing_revision_corrections = _assoc_table(
    "processing_revision_corrections", "correction_id", "correction_records.correction_id"
)
processing_revision_metadata_revisions = _assoc_table(
    "processing_revision_metadata_revisions",
    "metadata_revision_id",
    "source_document_metadata_revisions.metadata_revision_id",
)
processing_revision_referenced_documents = _assoc_table(
    "processing_revision_referenced_documents",
    "referenced_document_revision_id",
    "referenced_document_revisions.revision_id",
)
processing_revision_resolutions = _assoc_table(
    "processing_revision_resolutions",
    "resolution_revision_id",
    "referenced_document_resolution_revisions.resolution_revision_id",
)

_NEW_TABLES = (
    evidence_locator_artifacts,
    ocr_risk_scans,
    ocr_risk_flags,
    ocr_risk_reviews,
    correction_records,
    referenced_document_revisions,
    referenced_document_resolution_revisions,
    evidence_processing_candidates,
    evidence_activation_events,
    evidence_processing_candidate_events,
    processing_revision_locators,
    processing_revision_risk_scans,
    processing_revision_risk_reviews,
    processing_revision_corrections,
    processing_revision_metadata_revisions,
    processing_revision_referenced_documents,
    processing_revision_resolutions,
)


def _raw_dbapi(bind):
    """DBAPI 层连接：SQLAlchemy 的 autobegin 会让事务内 PRAGMA foreign_keys
    变成 no-op，因此 FK 开关与完整性检查必须在 raw 连接上执行。"""
    return bind.connection.driver_connection


def _disable_foreign_keys(bind) -> None:
    raw = _raw_dbapi(bind)
    # 无外层事务时 COMMIT 是空操作；有隐式事务时先结束事务让 PRAGMA 生效。
    try:
        raw.execute("COMMIT")
    except Exception:  # noqa: BLE001, S110 - 与 0006 同款模式；无事务 COMMIT 失败无害
        pass
    raw.execute("PRAGMA foreign_keys = OFF")


def _restore_foreign_keys(bind) -> None:
    raw = _raw_dbapi(bind)
    try:
        raw.execute("COMMIT")
    except Exception:  # noqa: BLE001, S110 - 与 0006 同款模式；无事务 COMMIT 失败无害
        pass
    raw.execute("PRAGMA foreign_keys = ON")


def _foreign_key_check_ok(bind) -> bool:
    raw = _raw_dbapi(bind)
    try:
        rows = raw.execute("PRAGMA foreign_key_check").fetchall()
    except Exception:  # noqa: BLE001 - 检查失败按不通过处理，由迁移管理器兜底
        return False
    return not rows


def _rebuild_review_episodes(*, with_pointers: bool) -> None:
    """建新表 -> 拷贝 -> 删旧表 -> 改名，保留子表外键目标与 legacy deferrable FK。"""
    bind = op.get_bind()
    _disable_foreign_keys(bind)
    try:
        op.execute("DROP INDEX IF EXISTS ix_review_episodes_subject_id")
        op.execute("DROP INDEX IF EXISTS ix_review_episodes_project_id")
        temp_name = "review_episodes_new" if with_pointers else "review_episodes_legacy"
        target = metadata if with_pointers else downgrade_metadata
        new_table = (
            _new_review_episodes_table(temp_name, target)
            if with_pointers
            else _legacy_review_episodes_table(temp_name, target)
        )
        new_table.create(bind=bind)
        if with_pointers:
            # 拷贝时把活动指针列为 NULL：迁移不按任何字段回填。
            columns = (
                "review_episode_id, subject_id, project_id, rule_set_id, "
                "rule_set_revision, study_phase, stage, protocol_version_id, "
                "evidence_snapshot_id, active_evidence_snapshot_id, "
                "active_evidence_processing_revision_id, anchor_dates_json, due_at, "
                "revision, created_at, updated_at, payload_json, payload_sha256"
            )
            source_columns = (
                "review_episode_id, subject_id, project_id, rule_set_id, "
                "rule_set_revision, study_phase, stage, protocol_version_id, "
                "evidence_snapshot_id, NULL, NULL, anchor_dates_json, due_at, "
                "revision, created_at, updated_at, payload_json, payload_sha256"
            )
        else:
            columns = (
                "review_episode_id, subject_id, project_id, rule_set_id, "
                "rule_set_revision, study_phase, stage, protocol_version_id, "
                "evidence_snapshot_id, anchor_dates_json, due_at, "
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
    # 1) evidence_processing_revisions 追加 base/complete 辨别列（batch 重建）。
    #    batch 重建会 DROP 被 evidence_processing_revision_pages 引用的旧表，
    #    必须在 raw 连接上临时关闭外键（见 0006 同款模式）。
    bind = op.get_bind()
    _disable_foreign_keys(bind)
    try:
        with op.batch_alter_table("evidence_processing_revisions") as batch_op:
            batch_op.add_column(
                Column("revision_kind", String(16), nullable=False, server_default="base")
            )
            batch_op.add_column(
                Column("base_processing_revision_id", String(128), nullable=True)
            )
            batch_op.add_column(
                Column("producer_candidate_id", String(128), nullable=True)
            )
            batch_op.add_column(
                Column("candidate_input_sha256", String(64), nullable=True)
            )
            batch_op.add_column(
                Column("completion_manifest_sha256", String(64), nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_epr_base_processing_revision_self",
                "evidence_processing_revisions",
                ["base_processing_revision_id"],
                ["evidence_processing_revision_id"],
            )
            batch_op.create_index("ix_epr_revision_kind", ["revision_kind"])
            batch_op.create_check_constraint(
                "ck_epr_revision_kind",
                "revision_kind IN ('base', 'complete')",
            )
            batch_op.create_check_constraint(
                "ck_epr_kind_shape",
                "(revision_kind = 'base' AND is_activatable = 0 "
                "AND base_processing_revision_id IS NULL "
                "AND producer_candidate_id IS NULL "
                "AND candidate_input_sha256 IS NULL "
                "AND completion_manifest_sha256 IS NULL) OR "
                "(revision_kind = 'complete' AND is_activatable = 1 "
                "AND base_processing_revision_id IS NOT NULL "
                "AND producer_candidate_id IS NOT NULL "
                "AND candidate_input_sha256 IS NOT NULL "
                "AND completion_manifest_sha256 IS NOT NULL)",
            )
            batch_op.create_unique_constraint(
                "uq_epr_producer_candidate", ["producer_candidate_id"]
            )
    finally:
        _restore_foreign_keys(bind)
    if not _foreign_key_check_ok(bind):
        raise RuntimeError(
            "迁移重建 evidence_processing_revisions 后外键完整性检查失败，禁止继续迁移"
        )

    # 2) 重建 review_episodes：legacy evidence_snapshot_id 原义保留，
    #    新增成对活动指针（迁移不按任何字段回填，指针全部 NULL）。
    _rebuild_review_episodes(with_pointers=True)

    # 3) 新建 17 张 Slice 4.4 表（列/约束/索引以模块级 Table 定义为准）。
    for table in _NEW_TABLES:
        table.create(bind=bind)



def _has_slice44_history(bind) -> bool:
    """是否存在任何 0010 正式历史；有则禁止有损降级。"""
    for table_name in _SLICE44_TABLES:
        count = bind.exec_driver_sql(f"SELECT COUNT(*) FROM {table_name}").scalar_one()
        if count:
            return True
    if bind.exec_driver_sql(
        "SELECT COUNT(*) FROM review_episodes WHERE "
        "active_evidence_snapshot_id IS NOT NULL OR "
        "active_evidence_processing_revision_id IS NOT NULL"
    ).scalar_one():
        return True
    return bool(
        bind.exec_driver_sql(
            "SELECT COUNT(*) FROM evidence_processing_revisions WHERE "
            "revision_kind != 'base' OR base_processing_revision_id IS NOT NULL OR "
            "completion_manifest_sha256 IS NOT NULL"
        ).scalar_one()
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_slice44_history(bind):
        raise RuntimeError(
            "0010 含有 Slice 4.4 正式历史（定位/风险/校对/被提及资料/激活事件/"
            "处理候选或活动指针），拒绝有损降级以避免丢失不可变历史"
        )

    # 先恢复 evidence_processing_revisions 的 0009 形状，再删除 0010 表。
    _disable_foreign_keys(bind)
    try:
        with op.batch_alter_table("evidence_processing_revisions") as batch_op:
            batch_op.drop_constraint("uq_epr_producer_candidate", type_="unique")
            batch_op.drop_index("ix_epr_revision_kind")
            batch_op.drop_constraint(
                "fk_epr_base_processing_revision_self", type_="foreignkey"
            )
            batch_op.drop_constraint("ck_epr_kind_shape", type_="check")
            batch_op.drop_constraint("ck_epr_revision_kind", type_="check")
            batch_op.drop_column("candidate_input_sha256")
            batch_op.drop_column("producer_candidate_id")
            batch_op.drop_column("completion_manifest_sha256")
            batch_op.drop_column("base_processing_revision_id")
            batch_op.drop_column("revision_kind")
    finally:
        _restore_foreign_keys(bind)

    # 依赖逆序删除 0010 表。
    for table_name in _SLICE44_TABLES:
        op.drop_table(table_name)

    # 重建 review_episodes 回 0009 形状（移除活动指针与成对 CHECK）。
    _rebuild_review_episodes(with_pointers=False)
