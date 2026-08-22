"""Phase 4 OCR 持久化与基础证据处理修订（Slice 4.3）：OCR 工件与页租约表

Revision ID: 0009
Revises: 0008a
Create Date: 2026-08-19

本迁移只新增 Phase 4 OCR/基础处理修订表，不回改已验收的 ``0008_evidence_ingestion``
与 ``0008a_evidence_upload_previews``，也不创建任何激活/活动指针路径。表名/列/约束
以 ``app/storage/ocr_models.py`` 为权威，由 ``verify_schema_matches_metadata``
在迁移后逐表交叉核对。降级按依赖逆序删除。

新增表：

- ``ocr_profiles``                      识别配置稳定指纹（profile_sha256 唯一）；
- ``page_artifacts``                    不可变页产物（页级内容去重
                                        (资料版本, 页码, 页图输入哈希)；成功/降级页
                                        携带真实几何，失败页几何列为 NULL，
                                        不得用伪值填充；失败页身份由确定性 ID 负责）；
- ``raw_ocr_request_artifacts`` / ``raw_ocr_response_artifacts``
                                        不可变原始请求/响应工件（内容寻址去重）；
- ``ocr_pages``                         页级识别结果（追加写不可变行；同一缓存键
                                        最多一条成功结果，部分唯一索引
                                        ``uq_ocr_pages_cache_key_succeeded`` 强制）；
- ``ocr_runs``                          文件级 OCR 运行（Profile/任务/状态/汇总）；
- ``ocr_attempts``                      每次真实请求的追加写尝试
                                        ((cache_key, attempt_number) 唯一)；
- ``evidence_processing_revisions``     不可变基础证据处理修订（不可激活）；
- ``evidence_processing_revision_pages`` 修订有序页清单（(revision_id, position) 主键）；
- ``page_work_leases``                  页工作租约（owner/过期/单调递增代次，
                                        只防重复执行，不保存 payload）。

外键：页产物/OCR 页/修订/清单分别指向 0008/0008a 及 Phase 3 的
``source_document_versions_v2``/``evidence_snapshots_v2``/``projects``/``subjects``/
``review_episodes``/``jobs`` 表；``ocr_attempts.retry_of_attempt_id`` 为自引用外键。
迁移后 ``PRAGMA foreign_key_check`` 必须无违规。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | None = "0008a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PAYLOAD_SHA_LEN = 64

# 降级时按依赖逆序检查是否被正式数据占用。
_OCR_TABLES = (
    "evidence_processing_revision_pages",
    "evidence_processing_revisions",
    "page_work_leases",
    "ocr_attempts",
    "ocr_runs",
    "ocr_pages",
    "raw_ocr_response_artifacts",
    "raw_ocr_request_artifacts",
    "page_artifacts",
    "ocr_profiles",
)


def upgrade() -> None:
    op.create_table(
        "raw_ocr_request_artifacts",
        sa.Column("raw_request_artifact_id", sa.String(length=128), nullable=False),
        sa.Column("sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("storage_ref", sa.String(length=512), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("raw_request_artifact_id", name="pk_raw_ocr_request_artifacts"),
        sa.UniqueConstraint("sha256", name="uq_raw_ocr_request_artifacts_sha256"),
    )
    op.create_table(
        "raw_ocr_response_artifacts",
        sa.Column("raw_response_artifact_id", sa.String(length=128), nullable=False),
        sa.Column("sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("storage_ref", sa.String(length=512), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("model_revision", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("raw_response_artifact_id", name="pk_raw_ocr_response_artifacts"),
        sa.UniqueConstraint("sha256", name="uq_raw_ocr_response_artifacts_sha256"),
    )
    op.create_table(
        "ocr_profiles",
        sa.Column("ocr_profile_id", sa.String(length=128), nullable=False),
        sa.Column("profile_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("extraction_route", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("model_revision", sa.String(length=128), nullable=False),
        sa.Column("prompt_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=True),
        sa.Column("parser_version", sa.String(length=128), nullable=False),
        sa.Column("render_params_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=True),
        sa.Column("request_params_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=True),
        sa.Column("layout_parser_version", sa.String(length=128), nullable=True),
        sa.Column("coordinate_transform_version", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("ocr_profile_id", name="pk_ocr_profiles"),
        sa.UniqueConstraint("profile_sha256", name="uq_ocr_profiles_profile_sha256"),
    )
    op.create_table(
        "page_artifacts",
        sa.Column("page_artifact_id", sa.String(length=128), nullable=False),
        sa.Column("source_document_version_id", sa.String(length=128), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("original_frame", sa.String(length=128), nullable=True),
        sa.Column("source_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("page_input_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=True),
        sa.Column("page_image_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=True),
        sa.Column("native_text_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=True),
        sa.Column("native_coordinates_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=True),
        sa.Column("page_width", sa.Float(), nullable=True),
        sa.Column("page_height", sa.Float(), nullable=True),
        sa.Column("rotation", sa.Integer(), nullable=True),
        sa.Column("renderer_version", sa.String(length=128), nullable=True),
        sa.Column("decoder_version", sa.String(length=128), nullable=True),
        sa.Column("derivative_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("coordinate_transform_version", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_document_version_id"],
            ["source_document_versions_v2.source_document_version_id"],
            name="fk_page_artifacts_source_document_versions_v2_source_document_version_id",
        ),
        sa.PrimaryKeyConstraint("page_artifact_id", name="pk_page_artifacts"),
        sa.UniqueConstraint(
            "source_document_version_id",
            "page_number",
            "page_input_sha256",
            "renderer_version",
            "decoder_version",
            "coordinate_transform_version",
            name="uq_page_artifacts_doc_page_input_config",
        ),
    )
    op.create_index(
        "ix_page_artifacts_source_document",
        "page_artifacts",
        ["source_document_version_id", "page_number"],
    )
    op.create_table(
        "ocr_pages",
        sa.Column("ocr_page_id", sa.String(length=128), nullable=False),
        sa.Column("page_artifact_id", sa.String(length=128), nullable=False),
        sa.Column("source_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("page_input_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("ocr_profile_id", sa.String(length=128), nullable=False),
        sa.Column("ocr_profile_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("cache_key", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("layout_parser_version", sa.String(length=128), nullable=True),
        sa.Column("coordinate_transform_version", sa.String(length=128), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("raw_text_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("layout_sidecar_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=True),
        sa.Column("quality_json", sa.Text(), nullable=False),
        sa.Column("risk_items_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["page_artifact_id"], ["page_artifacts.page_artifact_id"],
            name="fk_ocr_pages_page_artifacts_page_artifact_id",
        ),
        sa.ForeignKeyConstraint(
            ["ocr_profile_id"], ["ocr_profiles.ocr_profile_id"],
            name="fk_ocr_pages_ocr_profiles_ocr_profile_id",
        ),
        sa.PrimaryKeyConstraint("ocr_page_id", name="pk_ocr_pages"),
    )
    op.create_index(
        "uq_ocr_pages_cache_key_succeeded",
        "ocr_pages",
        ["cache_key"],
        unique=True,
        sqlite_where=sa.text("status = 'succeeded'"),
    )
    op.create_index("ix_ocr_pages_cache_key", "ocr_pages", ["cache_key"])
    op.create_index("ix_ocr_pages_page_artifact_id", "ocr_pages", ["page_artifact_id"])
    op.create_index("ix_ocr_pages_ocr_profile_id", "ocr_pages", ["ocr_profile_id"])
    op.create_table(
        "ocr_runs",
        sa.Column("ocr_run_id", sa.String(length=128), nullable=False),
        sa.Column("source_document_version_id", sa.String(length=128), nullable=False),
        sa.Column("ocr_profile_id", sa.String(length=128), nullable=False),
        sa.Column("ocr_profile_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("page_total", sa.Integer(), nullable=False),
        sa.Column("page_succeeded", sa.Integer(), nullable=False),
        sa.Column("page_failed", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_document_version_id"],
            ["source_document_versions_v2.source_document_version_id"],
            name="fk_ocr_runs_source_document_versions_v2_source_document_version_id",
        ),
        sa.ForeignKeyConstraint(
            ["ocr_profile_id"], ["ocr_profiles.ocr_profile_id"],
            name="fk_ocr_runs_ocr_profiles_ocr_profile_id",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.job_id"], name="fk_ocr_runs_jobs_job_id"
        ),
        sa.PrimaryKeyConstraint("ocr_run_id", name="pk_ocr_runs"),
    )
    op.create_index(
        "ix_ocr_runs_source_document_version_id",
        "ocr_runs",
        ["source_document_version_id"],
    )
    op.create_index("ix_ocr_runs_job_id", "ocr_runs", ["job_id"])
    op.create_table(
        "ocr_attempts",
        sa.Column("attempt_id", sa.String(length=128), nullable=False),
        sa.Column("ocr_run_id", sa.String(length=128), nullable=False),
        sa.Column("ocr_page_id", sa.String(length=128), nullable=True),
        sa.Column("cache_key", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("failure_category", sa.String(length=32), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("raw_request_artifact_id", sa.String(length=128), nullable=True),
        sa.Column("raw_response_artifact_id", sa.String(length=128), nullable=True),
        sa.Column("work_lease_owner", sa.String(length=128), nullable=True),
        sa.Column("work_lease_generation", sa.Integer(), nullable=True),
        sa.Column("omlx_lease_owner", sa.String(length=128), nullable=True),
        sa.Column("retry_of_attempt_id", sa.String(length=128), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ocr_run_id"], ["ocr_runs.ocr_run_id"], name="fk_ocr_attempts_ocr_runs_ocr_run_id"
        ),
        sa.ForeignKeyConstraint(
            ["ocr_page_id"], ["ocr_pages.ocr_page_id"], name="fk_ocr_attempts_ocr_pages_ocr_page_id"
        ),
        sa.ForeignKeyConstraint(
            ["raw_request_artifact_id"],
            ["raw_ocr_request_artifacts.raw_request_artifact_id"],
            name="fk_ocr_attempts_raw_ocr_request_artifacts_raw_request_artifact_id",
        ),
        sa.ForeignKeyConstraint(
            ["raw_response_artifact_id"],
            ["raw_ocr_response_artifacts.raw_response_artifact_id"],
            name="fk_ocr_attempts_raw_ocr_response_artifacts_raw_response_artifact_id",
        ),
        sa.ForeignKeyConstraint(
            ["retry_of_attempt_id"], ["ocr_attempts.attempt_id"],
            name="fk_ocr_attempts_ocr_attempts_retry_of_attempt_id",
        ),
        sa.PrimaryKeyConstraint("attempt_id", name="pk_ocr_attempts"),
        sa.UniqueConstraint(
            "cache_key", "attempt_number", name="uq_ocr_attempts_cache_attempt"
        ),
    )
    op.create_index("ix_ocr_attempts_cache_key", "ocr_attempts", ["cache_key"])
    op.create_index("ix_ocr_attempts_ocr_page_id", "ocr_attempts", ["ocr_page_id"])
    op.create_table(
        "evidence_processing_revisions",
        sa.Column("evidence_processing_revision_id", sa.String(length=128), nullable=False),
        sa.Column("evidence_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("review_episode_id", sa.String(length=128), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("is_activatable", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["evidence_snapshot_id"],
            ["evidence_snapshots_v2.evidence_snapshot_id"],
            name="fk_evidence_processing_revisions_evidence_snapshots_v2_evidence_snapshot_id",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"],
            name="fk_evidence_processing_revisions_projects_project_id",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.subject_id"],
            name="fk_evidence_processing_revisions_subjects_subject_id",
        ),
        sa.ForeignKeyConstraint(
            ["review_episode_id"], ["review_episodes.review_episode_id"],
            name="fk_evidence_processing_revisions_review_episodes_review_episode_id",
        ),
        sa.PrimaryKeyConstraint(
            "evidence_processing_revision_id", name="pk_evidence_processing_revisions"
        ),
    )
    op.create_index(
        "ix_epr_evidence_snapshot_id",
        "evidence_processing_revisions",
        ["evidence_snapshot_id"],
    )
    op.create_index(
        "ix_epr_review_episode_id",
        "evidence_processing_revisions",
        ["review_episode_id"],
    )
    op.create_table(
        "evidence_processing_revision_pages",
        sa.Column("revision_id", sa.String(length=128), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("entry_id", sa.String(length=128), nullable=False),
        sa.Column("source_document_version_id", sa.String(length=128), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("original_frame", sa.String(length=128), nullable=True),
        sa.Column("page_artifact_id", sa.String(length=128), nullable=False),
        sa.Column("ocr_page_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["evidence_processing_revisions.evidence_processing_revision_id"],
            name="fk_evidence_processing_revision_pages_evidence_processing_revisions_revision_id",
        ),
        sa.ForeignKeyConstraint(
            ["source_document_version_id"],
            ["source_document_versions_v2.source_document_version_id"],
            name="fk_evidence_processing_revision_pages_source_document_versions_v2_source_document_version_id",
        ),
        sa.ForeignKeyConstraint(
            ["page_artifact_id"], ["page_artifacts.page_artifact_id"],
            name="fk_evidence_processing_revision_pages_page_artifacts_page_artifact_id",
        ),
        sa.ForeignKeyConstraint(
            ["ocr_page_id"], ["ocr_pages.ocr_page_id"],
            name="fk_evidence_processing_revision_pages_ocr_pages_ocr_page_id",
        ),
        sa.PrimaryKeyConstraint(
            "revision_id", "position", name="pk_evidence_processing_revision_pages"
        ),
        sa.UniqueConstraint(
            "revision_id",
            "source_document_version_id",
            "page_number",
            name="uq_eprp_revision_doc_page",
        ),
    )
    op.create_index(
        "ix_eprp_page_artifact_id", "evidence_processing_revision_pages", ["page_artifact_id"]
    )
    op.create_table(
        "page_work_leases",
        sa.Column("work_item_id", sa.String(length=_PAYLOAD_SHA_LEN), nullable=False),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("lease_generation", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("work_item_id", name="pk_page_work_leases"),
    )


def downgrade() -> None:
    # 0009 的 OCR/处理修订历史不可通过降级静默丢失；空表绿地库才允许反向删除。
    bind = op.get_bind()
    populated = [
        table_name
        for table_name in _OCR_TABLES
        if bind.exec_driver_sql(f"SELECT 1 FROM {table_name} LIMIT 1").first() is not None
    ]
    if populated:
        raise RuntimeError(
            "0009 含有 OCR 工件或基础处理修订数据，拒绝降级以避免丢失不可变历史："
            + ", ".join(populated)
        )

    # 依赖逆序删除：先删子表/清单，再删主表与工件。
    op.drop_table("evidence_processing_revision_pages")
    op.drop_table("evidence_processing_revisions")
    op.drop_table("page_work_leases")
    op.drop_table("ocr_attempts")
    op.drop_table("ocr_runs")
    op.drop_table("ocr_pages")
    op.drop_table("raw_ocr_response_artifacts")
    op.drop_table("raw_ocr_request_artifacts")
    op.drop_table("page_artifacts")
    op.drop_table("ocr_profiles")
