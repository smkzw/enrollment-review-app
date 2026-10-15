"""v2 领域 schema：领域 ORM、幂等、stale 与持久 Job 表

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-14

本文件的 Table 定义由 ORM metadata 生成后冻结；表结构变更必须新增迁移，
不得修改本文件。约束命名遵循与 app.storage.db 相同的 naming convention。
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
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

revision: str = "0002"
down_revision: Union[str, None] = "0001"
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

conflict_groups = Table(
        "conflict_groups",
        metadata,
        Column("conflict_group_id", String(128), nullable=False, primary_key=True),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
    )


evidence_snapshots = Table(
        "evidence_snapshots",
        metadata,
        Column("evidence_snapshot_id", String(128), nullable=False, primary_key=True),
        Column("subject_id", String(128), nullable=False),
        Column("review_episode_id", String(128), nullable=False),
        Column("upload_mode", String(16), nullable=False),
        Column("prior_snapshot_id", String(128)),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["review_episode_id"], ["review_episodes.review_episode_id"], deferrable="True", initially="DEFERRED"),
        ForeignKeyConstraint(["prior_snapshot_id"], ["evidence_snapshots.evidence_snapshot_id"]),
        ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
    )


gate_results = Table(
        "gate_results",
        metadata,
        Column("gate_result_id", String(128), nullable=False, primary_key=True),
        Column("gate_name", String(128), nullable=False),
        Column("code_version", String(32), nullable=False),
        Column("result", String(16), nullable=False),
        Column("input_scope_hash", String(64), nullable=False),
        Column("idempotency_key", String(256), nullable=False),
        Column("output_hash", String(64), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
    )


idempotency_records = Table(
        "idempotency_records",
        metadata,
        Column("id", Integer, nullable=False, primary_key=True),
        Column("scope", String(128), nullable=False),
        Column("idempotency_key", String(256), nullable=False),
        Column("request_sha256", String(64), nullable=False),
        Column("result_type", String(64), nullable=False),
        Column("result_id", String(256), nullable=False),
        Column("status", String(16), nullable=False),
        Column("created_at", DateTime, nullable=False),
        UniqueConstraint("scope", "idempotency_key"),
    )


jobs = Table(
        "jobs",
        metadata,
        Column("job_id", String(128), nullable=False, primary_key=True),
        Column("job_type", String(64), nullable=False),
        Column("state", String(32), nullable=False),
        Column("lease_owner", String(128)),
        Column("lease_expires_at", DateTime),
        Column("lease_generation", Integer, nullable=False),
        Column("cancel_requested", Boolean, nullable=False),
        Column("progress_completed", Integer, nullable=False),
        Column("progress_total", Integer, nullable=False),
        Column("error_code", String(64)),
        Column("error_classification", String(64)),
        Column("last_event_seq", Integer, nullable=False),
        Column("revision", Integer, nullable=False),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
    )


model_configs = Table(
        "model_configs",
        metadata,
        Column("model_config_id", String(128), nullable=False, primary_key=True),
        Column("provider", String(64), nullable=False),
        Column("model", String(128), nullable=False),
        Column("reasoning_effort", String(32), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
    )


prompt_versions = Table(
        "prompt_versions",
        metadata,
        Column("prompt_version_id", String(128), nullable=False, primary_key=True),
        Column("node", String(48), nullable=False),
        Column("template_sha256", String(64), nullable=False),
        Column("schema_version_id", String(128), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
    )


protocol_document_versions = Table(
        "protocol_document_versions",
        metadata,
        Column("protocol_version_id", String(128), nullable=False, primary_key=True),
        Column("protocol_code", String(128), nullable=False),
        Column("official_version", String(64), nullable=False),
        Column("official_date_value", DateTime),
        Column("official_date_precision", String(16), nullable=False),
        Column("sha256", String(64), nullable=False),
        Column("integrity_manifest_sha256", String(64), nullable=False),
        Column("authority_record_sha256", String(64), nullable=False),
        Column("authority_confirmation_id", String(128), nullable=False),
        Column("authority_gate_result_id", String(128), nullable=False),
        Column("integrity_gate_result_id", String(128), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
    )


review_episodes = Table(
        "review_episodes",
        metadata,
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
        Column("due_at", DateTime),
        Column("revision", Integer, nullable=False),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        ForeignKeyConstraint(["protocol_version_id"], ["protocol_document_versions.protocol_version_id"]),
        ForeignKeyConstraint(["rule_set_id", "rule_set_revision"], ["rule_sets.rule_set_id", "rule_sets.revision"]),
        ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        ForeignKeyConstraint(["evidence_snapshot_id"], ["evidence_snapshots.evidence_snapshot_id"], deferrable="True", initially="DEFERRED"),
        ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
    )


source_document_versions = Table(
        "source_document_versions",
        metadata,
        Column("source_document_version_id", String(128), nullable=False, primary_key=True),
        Column("sha256", String(64), nullable=False),
        Column("document_type", String(64), nullable=False),
        Column("source_party", String(64), nullable=False),
        Column("upload_mode", String(16), nullable=False),
        Column("review_stage", String(32), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
    )


episode_rollups = Table(
        "episode_rollups",
        metadata,
        Column("id", Integer, nullable=False, primary_key=True),
        Column("review_episode_id", String(128), nullable=False),
        Column("main_status", String(32), nullable=False),
        Column("gate_result_id", String(128), nullable=False),
        Column("publication_fingerprint", String(64), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        UniqueConstraint("review_episode_id", "publication_fingerprint"),
        ForeignKeyConstraint(["gate_result_id"], ["gate_results.gate_result_id"]),
        ForeignKeyConstraint(["review_episode_id"], ["review_episodes.review_episode_id"]),
    )


evidence_snapshot_documents = Table(
        "evidence_snapshot_documents",
        metadata,
        Column("evidence_snapshot_id", String(128), nullable=False),
        Column("source_document_version_id", String(128), nullable=False),
        Column("position", Integer, nullable=False),
        UniqueConstraint("evidence_snapshot_id", "source_document_version_id"),
        ForeignKeyConstraint(["evidence_snapshot_id"], ["evidence_snapshots.evidence_snapshot_id"]),
        UniqueConstraint("evidence_snapshot_id", "position"),
        ForeignKeyConstraint(["source_document_version_id"], ["source_document_versions.source_document_version_id"]),
    )


evidence_spans = Table(
        "evidence_spans",
        metadata,
        Column("evidence_span_id", String(128), nullable=False, primary_key=True),
        Column("source_document_version_id", String(128), nullable=False),
        Column("page_number", Integer, nullable=False),
        Column("precision", String(32), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["source_document_version_id"], ["source_document_versions.source_document_version_id"]),
    )


job_steps = Table(
        "job_steps",
        metadata,
        Column("job_id", String(128), nullable=False, primary_key=True),
        Column("step_id", String(128), nullable=False, primary_key=True),
        Column("name", String(128), nullable=False),
        Column("state", String(32), nullable=False),
        Column("attempt", Integer, nullable=False),
        Column("max_attempts", Integer, nullable=False),
        Column("retryable", Boolean, nullable=False),
        Column("progress_completed", Integer, nullable=False),
        Column("progress_total", Integer, nullable=False),
        Column("error_code", String(64)),
        Column("error_classification", String(64)),
        Column("revision", Integer, nullable=False),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        ForeignKeyConstraint(["job_id"], ["jobs.job_id"]),
    )


protocol_authority_records = Table(
        "protocol_authority_records",
        metadata,
        Column("authority_record_id", String(128), nullable=False, primary_key=True),
        Column("protocol_version_id", String(128), nullable=False),
        Column("study_phase", String(32), nullable=False),
        Column("verified_at", DateTime, nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["protocol_version_id"], ["protocol_document_versions.protocol_version_id"]),
    )


protocol_source_records = Table(
        "protocol_source_records",
        metadata,
        Column("source_ref", String(256), nullable=False, primary_key=True),
        Column("protocol_version_id", String(128), nullable=False),
        Column("protocol_document_sha256", String(64), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["protocol_version_id"], ["protocol_document_versions.protocol_version_id"]),
    )


review_context_snapshots = Table(
        "review_context_snapshots",
        metadata,
        Column("context_id", String(128), nullable=False, primary_key=True),
        Column("review_episode_id", String(128), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["review_episode_id"], ["review_episodes.review_episode_id"]),
    )


review_runs = Table(
        "review_runs",
        metadata,
        Column("review_run_id", String(128), nullable=False, primary_key=True),
        Column("review_episode_id", String(128), nullable=False),
        Column("protocol_version_id", String(128), nullable=False),
        Column("rule_set_revision", Integer, nullable=False),
        Column("evidence_snapshot_id", String(128), nullable=False),
        Column("started_at", DateTime, nullable=False),
        Column("completed_at", DateTime),
        Column("supersedes_review_run_id", String(128)),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["supersedes_review_run_id"], ["review_runs.review_run_id"]),
        ForeignKeyConstraint(["protocol_version_id"], ["protocol_document_versions.protocol_version_id"]),
        ForeignKeyConstraint(["review_episode_id"], ["review_episodes.review_episode_id"]),
        ForeignKeyConstraint(["evidence_snapshot_id"], ["evidence_snapshots.evidence_snapshot_id"]),
    )


rule_sets = Table(
        "rule_sets",
        metadata,
        Column("rule_set_id", String(128), nullable=False, primary_key=True),
        Column("revision", Integer, nullable=False, primary_key=True),
        Column("protocol_version_id", String(128), nullable=False),
        Column("study_phase", String(32), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["protocol_version_id"], ["protocol_document_versions.protocol_version_id"]),
    )


workflow_stages = Table(
        "workflow_stages",
        metadata,
        Column("workflow_stage_id", String(128), nullable=False, primary_key=True),
        Column("protocol_version_id", String(128), nullable=False),
        Column("stage", String(32), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["protocol_version_id"], ["protocol_document_versions.protocol_version_id"]),
    )


entity_staleness = Table(
        "entity_staleness",
        metadata,
        Column("id", Integer, nullable=False, primary_key=True),
        Column("target_type", String(64), nullable=False),
        Column("target_id", String(128), nullable=False),
        Column("reason", String(256), nullable=False),
        Column("source_entity_type", String(64), nullable=False),
        Column("source_entity_id", String(128), nullable=False),
        Column("source_revision", Integer, nullable=False),
        Column("opened_at", DateTime, nullable=False),
        Column("cleared_by_review_run_id", String(128)),
        Column("cleared_at", DateTime),
        UniqueConstraint("target_type", "target_id", "reason", "source_entity_type", "source_entity_id", "source_revision"),
        ForeignKeyConstraint(["cleared_by_review_run_id"], ["review_runs.review_run_id"]),
    )


job_checkpoints = Table(
        "job_checkpoints",
        metadata,
        Column("checkpoint_id", String(128), nullable=False, primary_key=True),
        Column("job_id", String(128), nullable=False),
        Column("step_id", String(128), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["job_id"], ["jobs.job_id"]),
        ForeignKeyConstraint(["job_id", "step_id"], ["job_steps.job_id", "job_steps.step_id"]),
    )


job_step_dependencies = Table(
        "job_step_dependencies",
        metadata,
        Column("job_id", String(128), nullable=False),
        Column("step_id", String(128), nullable=False),
        Column("depends_on_step_id", String(128), nullable=False),
        Column("position", Integer, nullable=False),
        ForeignKeyConstraint(["job_id", "step_id"], ["job_steps.job_id", "job_steps.step_id"]),
        UniqueConstraint("job_id", "step_id", "depends_on_step_id"),
        UniqueConstraint("job_id", "step_id", "position"),
        ForeignKeyConstraint(["job_id", "depends_on_step_id"], ["job_steps.job_id", "job_steps.step_id"]),
    )


projects = Table(
        "projects",
        metadata,
        Column("project_id", String(128), nullable=False, primary_key=True),
        Column("project_code", String(128), nullable=False),
        Column("project_name", String(256), nullable=False),
        Column("study_phase", String(32), nullable=False),
        Column("protocol_version_id", String(128), nullable=False),
        Column("rule_set_id", String(128), nullable=False),
        Column("rule_set_revision", Integer, nullable=False),
        Column("revision", Integer, nullable=False),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        ForeignKeyConstraint(["protocol_version_id"], ["protocol_document_versions.protocol_version_id"]),
        ForeignKeyConstraint(["rule_set_id", "rule_set_revision"], ["rule_sets.rule_set_id", "rule_sets.revision"]),
    )


protocol_integrity_manifests = Table(
        "protocol_integrity_manifests",
        metadata,
        Column("manifest_id", String(128), nullable=False, primary_key=True),
        Column("protocol_version_id", String(128), nullable=False),
        Column("authority_record_id", String(128), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["protocol_version_id"], ["protocol_document_versions.protocol_version_id"]),
        ForeignKeyConstraint(["authority_record_id"], ["protocol_authority_records.authority_record_id"]),
    )


review_run_diffs = Table(
        "review_run_diffs",
        metadata,
        Column("review_run_diff_id", String(128), nullable=False, primary_key=True),
        Column("prior_review_run_id", String(128), nullable=False),
        Column("current_review_run_id", String(128), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["prior_review_run_id"], ["review_runs.review_run_id"]),
        ForeignKeyConstraint(["current_review_run_id"], ["review_runs.review_run_id"]),
    )


rules = Table(
        "rules",
        metadata,
        Column("rule_set_id", String(128), nullable=False, primary_key=True),
        Column("rule_set_revision", Integer, nullable=False, primary_key=True),
        Column("rule_id", String(128), nullable=False, primary_key=True),
        Column("official_code", String(16), nullable=False),
        Column("kind", String(32), nullable=False),
        Column("study_phase", String(32), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["rule_set_id", "rule_set_revision"], ["rule_sets.rule_set_id", "rule_sets.revision"]),
    )


service_command_events = Table(
        "service_command_events",
        metadata,
        Column("command_id", String(128), nullable=False, primary_key=True),
        Column("protocol_version_id", String(128), nullable=False),
        Column("authority_record_id", String(128), nullable=False),
        Column("occurred_at", DateTime, nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["protocol_version_id"], ["protocol_document_versions.protocol_version_id"]),
        ForeignKeyConstraint(["authority_record_id"], ["protocol_authority_records.authority_record_id"]),
    )


workflow_stage_requirements = Table(
        "workflow_stage_requirements",
        metadata,
        Column("workflow_stage_id", String(128), nullable=False),
        Column("requirement_id", String(128), nullable=False),
        Column("position", Integer, nullable=False),
        UniqueConstraint("workflow_stage_id", "requirement_id"),
        UniqueConstraint("workflow_stage_id", "position"),
        ForeignKeyConstraint(["workflow_stage_id"], ["workflow_stages.workflow_stage_id"]),
    )


job_events = Table(
        "job_events",
        metadata,
        Column("id", Integer, nullable=False, primary_key=True),
        Column("job_id", String(128), nullable=False),
        Column("event_seq", Integer, nullable=False),
        Column("event_type", String(32), nullable=False),
        Column("step_id", String(128)),
        Column("occurred_at", DateTime, nullable=False),
        Column("attempt", Integer, nullable=False),
        Column("checkpoint_id", String(128)),
        Column("retryable", Boolean, nullable=False),
        Column("progress_completed", Integer, nullable=False),
        Column("progress_total", Integer, nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["checkpoint_id"], ["job_checkpoints.checkpoint_id"]),
        ForeignKeyConstraint(["job_id"], ["jobs.job_id"]),
        ForeignKeyConstraint(["job_id", "step_id"], ["job_steps.job_id", "job_steps.step_id"]),
        UniqueConstraint("job_id", "event_seq"),
    )


protocol_authority_confirmations = Table(
        "protocol_authority_confirmations",
        metadata,
        Column("confirmation_id", String(128), nullable=False, primary_key=True),
        Column("command_id", String(128), nullable=False),
        Column("protocol_version_id", String(128), nullable=False),
        Column("authority_record_id", String(128), nullable=False),
        Column("confirmed_at", DateTime, nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["protocol_version_id"], ["protocol_document_versions.protocol_version_id"]),
        ForeignKeyConstraint(["authority_record_id"], ["protocol_authority_records.authority_record_id"]),
        ForeignKeyConstraint(["command_id"], ["service_command_events.command_id"]),
    )


rule_components = Table(
        "rule_components",
        metadata,
        Column("rule_set_id", String(128), nullable=False, primary_key=True),
        Column("rule_set_revision", Integer, nullable=False, primary_key=True),
        Column("rule_component_id", String(128), nullable=False, primary_key=True),
        Column("parent_rule_id", String(128), nullable=False),
        Column("display_code", String(16), nullable=False),
        Column("title", String(256), nullable=False),
        Column("expression_json", JSON, nullable=False),
        Column("expression_sha256", String(64), nullable=False),
        Column("exception_expression_json", JSON),
        Column("exception_expression_sha256", String(64)),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["rule_set_id", "rule_set_revision", "parent_rule_id"], ["rules.rule_set_id", "rules.rule_set_revision", "rules.rule_id"]),
        ForeignKeyConstraint(["rule_set_id", "rule_set_revision"], ["rule_sets.rule_set_id", "rule_sets.revision"]),
    )


subjects = Table(
        "subjects",
        metadata,
        Column("subject_id", String(128), nullable=False, primary_key=True),
        Column("subject_code", String(128), nullable=False),
        Column("project_id", String(128), nullable=False),
        Column("center_code", String(128)),
        Column("center_name", String(256)),
        Column("sex", String(32)),
        Column("age_years", Float),
        Column("revision", Integer, nullable=False),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
    )


agent_calls = Table(
        "agent_calls",
        metadata,
        Column("agent_call_id", String(128), nullable=False, primary_key=True),
        Column("node", String(48), nullable=False),
        Column("output_kind", String(32), nullable=False),
        Column("write_scope", String(32), nullable=False),
        Column("prompt_version_id", String(128), nullable=False),
        Column("model_config_id", String(128), nullable=False),
        Column("idempotency_key", String(256), nullable=False),
        Column("attempt", Integer, nullable=False),
        Column("outcome", String(32), nullable=False),
        Column("started_at", DateTime, nullable=False),
        Column("finished_at", DateTime, nullable=False),
        Column("project_id", String(128), nullable=False),
        Column("protocol_version_id", String(128), nullable=False),
        Column("rule_set_id", String(128)),
        Column("rule_set_revision", Integer),
        Column("subject_id", String(128)),
        Column("review_episode_id", String(128)),
        Column("review_run_id", String(128)),
        Column("evidence_snapshot_id", String(128)),
        Column("input_tokens", Integer),
        Column("output_tokens", Integer),
        Column("estimated_cost", Float),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        ForeignKeyConstraint(["evidence_snapshot_id"], ["evidence_snapshots.evidence_snapshot_id"]),
        ForeignKeyConstraint(["review_run_id"], ["review_runs.review_run_id"]),
        ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
        ForeignKeyConstraint(["prompt_version_id"], ["prompt_versions.prompt_version_id"]),
        ForeignKeyConstraint(["review_episode_id"], ["review_episodes.review_episode_id"]),
        ForeignKeyConstraint(["protocol_version_id"], ["protocol_document_versions.protocol_version_id"]),
        ForeignKeyConstraint(["model_config_id"], ["model_configs.model_config_id"]),
    )


clinical_facts = Table(
        "clinical_facts",
        metadata,
        Column("fact_id", String(128), nullable=False, primary_key=True),
        Column("project_id", String(128), nullable=False),
        Column("subject_id", String(128), nullable=False),
        Column("review_episode_id", String(128), nullable=False),
        Column("evidence_snapshot_id", String(128), nullable=False),
        Column("fact_type", String(128), nullable=False),
        Column("polarity", String(16), nullable=False),
        Column("certainty", Float, nullable=False),
        Column("value_json", JSON),
        Column("unit", String(64)),
        Column("effective_date_json", JSON),
        Column("conflict_group_id", String(128)),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["review_episode_id"], ["review_episodes.review_episode_id"]),
        ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        ForeignKeyConstraint(["evidence_snapshot_id"], ["evidence_snapshots.evidence_snapshot_id"]),
        ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
        ForeignKeyConstraint(["conflict_group_id"], ["conflict_groups.conflict_group_id"]),
    )


evidence_requirements = Table(
        "evidence_requirements",
        metadata,
        Column("rule_set_id", String(128), nullable=False, primary_key=True),
        Column("rule_set_revision", Integer, nullable=False, primary_key=True),
        Column("requirement_id", String(128), nullable=False, primary_key=True),
        Column("rule_component_id", String(128), nullable=False),
        Column("fact_type", String(128), nullable=False),
        Column("due_stage", String(32), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["rule_set_id", "rule_set_revision", "rule_component_id"], ["rule_components.rule_set_id", "rule_components.rule_set_revision", "rule_components.rule_component_id"]),
        ForeignKeyConstraint(["rule_set_id", "rule_set_revision"], ["rule_sets.rule_set_id", "rule_sets.revision"]),
    )


final_assessments = Table(
        "final_assessments",
        metadata,
        Column("assessment_id", String(128), nullable=False, primary_key=True),
        Column("project_id", String(128), nullable=False),
        Column("protocol_version_id", String(128), nullable=False),
        Column("subject_id", String(128), nullable=False),
        Column("review_episode_id", String(128), nullable=False),
        Column("review_run_id", String(128), nullable=False),
        Column("evidence_snapshot_id", String(128), nullable=False),
        Column("rule_set_id", String(128), nullable=False),
        Column("rule_set_revision", Integer, nullable=False),
        Column("rule_component_id", String(128), nullable=False),
        Column("decision", String(48), nullable=False),
        Column("blocking_level", String(32), nullable=False),
        Column("gate_result_id", String(128), nullable=False),
        Column("publication_fingerprint", String(64), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["gate_result_id"], ["gate_results.gate_result_id"]),
        ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
        ForeignKeyConstraint(["review_episode_id"], ["review_episodes.review_episode_id"]),
        ForeignKeyConstraint(["rule_set_id", "rule_set_revision", "rule_component_id"], ["rule_components.rule_set_id", "rule_components.rule_set_revision", "rule_components.rule_component_id"]),
        ForeignKeyConstraint(["protocol_version_id"], ["protocol_document_versions.protocol_version_id"]),
        ForeignKeyConstraint(["evidence_snapshot_id"], ["evidence_snapshots.evidence_snapshot_id"]),
        ForeignKeyConstraint(["review_run_id"], ["review_runs.review_run_id"]),
        ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
    )


patient_profiles = Table(
        "patient_profiles",
        metadata,
        Column("patient_profile_id", String(128), nullable=False, primary_key=True),
        Column("subject_id", String(128), nullable=False),
        Column("review_episode_id", String(128), nullable=False),
        Column("stale", Boolean, nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        ForeignKeyConstraint(["review_episode_id"], ["review_episodes.review_episode_id"]),
    )


action_requests = Table(
        "action_requests",
        metadata,
        Column("action_id", String(128), nullable=False, primary_key=True),
        Column("project_id", String(128), nullable=False),
        Column("protocol_version_id", String(128), nullable=False),
        Column("subject_id", String(128), nullable=False),
        Column("rule_set_id", String(128), nullable=False),
        Column("rule_set_revision", Integer, nullable=False),
        Column("rule_component_id", String(128), nullable=False),
        Column("review_episode_id", String(128), nullable=False),
        Column("evidence_snapshot_id", String(128), nullable=False),
        Column("review_run_id", String(128), nullable=False),
        Column("assessment_id", String(128), nullable=False),
        Column("gap_type", String(64), nullable=False),
        Column("target_party", String(64), nullable=False),
        Column("requested_action", Text, nullable=False),
        Column("acceptable_evidence", Text, nullable=False),
        Column("due_stage", String(32), nullable=False),
        Column("blocking_level", String(32), nullable=False),
        Column("trigger_evidence_span_id", String(128)),
        Column("state", String(32), nullable=False),
        Column("recompute_scope_json", JSON, nullable=False),
        Column("gate_result_id", String(128), nullable=False),
        Column("publication_fingerprint", String(64), nullable=False),
        Column("revision", Integer, nullable=False),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        ForeignKeyConstraint(["trigger_evidence_span_id"], ["evidence_spans.evidence_span_id"]),
        ForeignKeyConstraint(["rule_set_id", "rule_set_revision", "rule_component_id"], ["rule_components.rule_set_id", "rule_components.rule_set_revision", "rule_components.rule_component_id"]),
        ForeignKeyConstraint(["assessment_id"], ["final_assessments.assessment_id"]),
        ForeignKeyConstraint(["gate_result_id"], ["gate_results.gate_result_id"]),
        ForeignKeyConstraint(["evidence_snapshot_id"], ["evidence_snapshots.evidence_snapshot_id"]),
        ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        ForeignKeyConstraint(["protocol_version_id"], ["protocol_document_versions.protocol_version_id"]),
        ForeignKeyConstraint(["review_episode_id"], ["review_episodes.review_episode_id"]),
        ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
        ForeignKeyConstraint(["review_run_id"], ["review_runs.review_run_id"]),
    )


agent_call_gate_results = Table(
        "agent_call_gate_results",
        metadata,
        Column("agent_call_id", String(128), nullable=False),
        Column("gate_result_id", String(128), nullable=False),
        Column("position", Integer, nullable=False),
        UniqueConstraint("agent_call_id", "gate_result_id"),
        UniqueConstraint("agent_call_id", "position"),
        ForeignKeyConstraint(["agent_call_id"], ["agent_calls.agent_call_id"]),
        ForeignKeyConstraint(["gate_result_id"], ["gate_results.gate_result_id"]),
    )


agent_call_sources = Table(
        "agent_call_sources",
        metadata,
        Column("agent_call_id", String(128), nullable=False),
        Column("source_ref", String(256), nullable=False),
        Column("position", Integer, nullable=False),
        UniqueConstraint("agent_call_id", "position"),
        ForeignKeyConstraint(["agent_call_id"], ["agent_calls.agent_call_id"]),
        UniqueConstraint("agent_call_id", "source_ref"),
    )


assessment_candidates = Table(
        "assessment_candidates",
        metadata,
        Column("assessment_candidate_id", String(128), nullable=False, primary_key=True),
        Column("agent_call_id", String(128), nullable=False),
        Column("project_id", String(128), nullable=False),
        Column("protocol_version_id", String(128), nullable=False),
        Column("subject_id", String(128), nullable=False),
        Column("review_episode_id", String(128), nullable=False),
        Column("review_run_id", String(128), nullable=False),
        Column("evidence_snapshot_id", String(128), nullable=False),
        Column("rule_set_id", String(128), nullable=False),
        Column("rule_set_revision", Integer, nullable=False),
        Column("rule_component_id", String(128), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        ForeignKeyConstraint(["evidence_snapshot_id"], ["evidence_snapshots.evidence_snapshot_id"]),
        ForeignKeyConstraint(["review_episode_id"], ["review_episodes.review_episode_id"]),
        ForeignKeyConstraint(["rule_set_id", "rule_set_revision", "rule_component_id"], ["rule_components.rule_set_id", "rule_components.rule_set_revision", "rule_components.rule_component_id"]),
        ForeignKeyConstraint(["protocol_version_id"], ["protocol_document_versions.protocol_version_id"]),
        ForeignKeyConstraint(["review_run_id"], ["review_runs.review_run_id"]),
        ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
        ForeignKeyConstraint(["agent_call_id"], ["agent_calls.agent_call_id"]),
    )


clinical_fact_spans = Table(
        "clinical_fact_spans",
        metadata,
        Column("fact_id", String(128), nullable=False),
        Column("evidence_span_id", String(128), nullable=False),
        Column("position", Integer, nullable=False),
        UniqueConstraint("fact_id", "evidence_span_id"),
        ForeignKeyConstraint(["evidence_span_id"], ["evidence_spans.evidence_span_id"]),
        UniqueConstraint("fact_id", "position"),
        ForeignKeyConstraint(["fact_id"], ["clinical_facts.fact_id"]),
    )


evidence_expectations = Table(
        "evidence_expectations",
        metadata,
        Column("expectation_id", String(128), nullable=False, primary_key=True),
        Column("requirement_id", String(128), nullable=False),
        Column("rule_set_id", String(128), nullable=False),
        Column("rule_set_revision", Integer, nullable=False),
        Column("review_episode_id", String(128), nullable=False),
        Column("status", String(32), nullable=False),
        Column("gap_type", String(64)),
        Column("revision", Integer, nullable=False),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        ForeignKeyConstraint(["rule_set_id", "rule_set_revision", "requirement_id"], ["evidence_requirements.rule_set_id", "evidence_requirements.rule_set_revision", "evidence_requirements.requirement_id"]),
        ForeignKeyConstraint(["review_episode_id"], ["review_episodes.review_episode_id"]),
    )


evidence_normalization_candidates = Table(
        "evidence_normalization_candidates",
        metadata,
        Column("candidate_id", String(128), nullable=False, primary_key=True),
        Column("project_id", String(128), nullable=False),
        Column("protocol_version_id", String(128), nullable=False),
        Column("subject_id", String(128), nullable=False),
        Column("review_episode_id", String(128), nullable=False),
        Column("evidence_snapshot_id", String(128), nullable=False),
        Column("created_by_agent_call_id", String(128), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["evidence_snapshot_id"], ["evidence_snapshots.evidence_snapshot_id"]),
        ForeignKeyConstraint(["review_episode_id"], ["review_episodes.review_episode_id"]),
        ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
        ForeignKeyConstraint(["created_by_agent_call_id"], ["agent_calls.agent_call_id"]),
        ForeignKeyConstraint(["protocol_version_id"], ["protocol_document_versions.protocol_version_id"]),
        ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
    )


final_assessment_facts = Table(
        "final_assessment_facts",
        metadata,
        Column("assessment_id", String(128), nullable=False),
        Column("fact_id", String(128), nullable=False),
        Column("position", Integer, nullable=False),
        UniqueConstraint("assessment_id", "fact_id"),
        UniqueConstraint("assessment_id", "position"),
        ForeignKeyConstraint(["assessment_id"], ["final_assessments.assessment_id"]),
        ForeignKeyConstraint(["fact_id"], ["clinical_facts.fact_id"]),
    )


final_assessment_spans = Table(
        "final_assessment_spans",
        metadata,
        Column("assessment_id", String(128), nullable=False),
        Column("evidence_span_id", String(128), nullable=False),
        Column("position", Integer, nullable=False),
        UniqueConstraint("assessment_id", "position"),
        ForeignKeyConstraint(["assessment_id"], ["final_assessments.assessment_id"]),
        ForeignKeyConstraint(["evidence_span_id"], ["evidence_spans.evidence_span_id"]),
        UniqueConstraint("assessment_id", "evidence_span_id"),
    )


action_transitions = Table(
        "action_transitions",
        metadata,
        Column("transition_id", String(128), nullable=False, primary_key=True),
        Column("action_id", String(128), nullable=False),
        Column("from_state", String(32), nullable=False),
        Column("to_state", String(32), nullable=False),
        Column("occurred_at", DateTime, nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["action_id"], ["action_requests.action_id"]),
    )


critic_runs = Table(
        "critic_runs",
        metadata,
        Column("critic_run_id", String(128), nullable=False, primary_key=True),
        Column("assessment_candidate_id", String(128), nullable=False),
        Column("created_by_agent_call_id", String(128), nullable=False),
        Column("critic_revision", Integer, nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("payload_sha256", String(64), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["assessment_candidate_id"], ["assessment_candidates.assessment_candidate_id"]),
        ForeignKeyConstraint(["created_by_agent_call_id"], ["agent_calls.agent_call_id"]),
    )


evidence_expectation_spans = Table(
        "evidence_expectation_spans",
        metadata,
        Column("expectation_id", String(128), nullable=False),
        Column("evidence_span_id", String(128), nullable=False),
        Column("position", Integer, nullable=False),
        UniqueConstraint("expectation_id", "evidence_span_id"),
        UniqueConstraint("expectation_id", "position"),
        ForeignKeyConstraint(["expectation_id"], ["evidence_expectations.expectation_id"]),
        ForeignKeyConstraint(["evidence_span_id"], ["evidence_spans.evidence_span_id"]),
    )


action_transition_spans = Table(
        "action_transition_spans",
        metadata,
        Column("transition_id", String(128), nullable=False),
        Column("evidence_span_id", String(128), nullable=False),
        Column("position", Integer, nullable=False),
        UniqueConstraint("transition_id", "position"),
        ForeignKeyConstraint(["transition_id"], ["action_transitions.transition_id"]),
        ForeignKeyConstraint(["evidence_span_id"], ["evidence_spans.evidence_span_id"]),
        UniqueConstraint("transition_id", "evidence_span_id"),
    )

TABLES = [
    conflict_groups,
    evidence_snapshots,
    gate_results,
    idempotency_records,
    jobs,
    model_configs,
    prompt_versions,
    protocol_document_versions,
    review_episodes,
    source_document_versions,
    episode_rollups,
    evidence_snapshot_documents,
    evidence_spans,
    job_steps,
    protocol_authority_records,
    protocol_source_records,
    review_context_snapshots,
    review_runs,
    rule_sets,
    workflow_stages,
    entity_staleness,
    job_checkpoints,
    job_step_dependencies,
    projects,
    protocol_integrity_manifests,
    review_run_diffs,
    rules,
    service_command_events,
    workflow_stage_requirements,
    job_events,
    protocol_authority_confirmations,
    rule_components,
    subjects,
    agent_calls,
    clinical_facts,
    evidence_requirements,
    final_assessments,
    patient_profiles,
    action_requests,
    agent_call_gate_results,
    agent_call_sources,
    assessment_candidates,
    clinical_fact_spans,
    evidence_expectations,
    evidence_normalization_candidates,
    final_assessment_facts,
    final_assessment_spans,
    action_transitions,
    critic_runs,
    evidence_expectation_spans,
    action_transition_spans,
]

INDEXES = [
    Index("ix_evidence_snapshots_subject_id", evidence_snapshots.c.subject_id),
    Index("ix_gate_results_idempotency_key", gate_results.c.idempotency_key),
    Index("ix_jobs_state", jobs.c.state),
    Index("ix_review_episodes_project_id", review_episodes.c.project_id),
    Index("ix_review_episodes_subject_id", review_episodes.c.subject_id),
    Index("ix_episode_rollups_review_episode_id", episode_rollups.c.review_episode_id),
    Index("ix_evidence_spans_source_document_version_id", evidence_spans.c.source_document_version_id),
    Index("ix_job_steps_job_id", job_steps.c.job_id),
    Index("ix_review_runs_review_episode_id", review_runs.c.review_episode_id),
    Index("ix_rule_sets_protocol_version_id", rule_sets.c.protocol_version_id),
    Index("ix_entity_staleness_target", entity_staleness.c.target_type, entity_staleness.c.target_id),
    Index("ix_job_checkpoints_job_id", job_checkpoints.c.job_id),
    Index("ix_rules_official_code", rules.c.official_code),
    Index("ix_job_events_job_id", job_events.c.job_id),
    Index("ix_subjects_project_id", subjects.c.project_id),
    Index("ix_agent_calls_idempotency_key", agent_calls.c.idempotency_key),
    Index("ix_agent_calls_project_id", agent_calls.c.project_id),
    Index("ix_clinical_facts_review_episode_id", clinical_facts.c.review_episode_id),
    Index("ix_clinical_facts_subject_fact_type", clinical_facts.c.subject_id, clinical_facts.c.fact_type),
    Index("ix_evidence_requirements_fact_type", evidence_requirements.c.fact_type),
    Index("ix_final_assessments_review_episode_id", final_assessments.c.review_episode_id),
    Index("ix_action_requests_review_episode_id", action_requests.c.review_episode_id),
    Index("ix_action_requests_state", action_requests.c.state),
    Index("ix_assessment_candidates_review_episode_id", assessment_candidates.c.review_episode_id),
    Index("ix_evidence_expectations_review_episode_id", evidence_expectations.c.review_episode_id),
    Index("ix_action_transitions_action_id", action_transitions.c.action_id),
]


def upgrade() -> None:
    """创建全部领域表；索引附着在 Table 上随表创建（CREATE INDEX 一并发出）。"""
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind)


def downgrade() -> None:
    """反向删除全部领域表；SQLite DROP TABLE 会连带删除其索引。"""
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind)
