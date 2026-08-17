"""V2 方案解构工作台 API 契约。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.contracts.agent_io import ProtocolDeconstructionDraft
from app.domain.contracts.enums import DatePrecision, StudyPhase
from app.domain.contracts.protocol_drafts import DraftFeedbackKind


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartDeconstructionResponse(_StrictModel):
    job_id: str
    state: str
    state_label: str
    created: bool
    source_artifact_id: str
    file_name: str


class OfficialProjectDTO(_StrictModel):
    """正式项目投影（重新解构选择使用）。"""

    project_id: str
    project_code: str
    project_name: str
    study_phase: StudyPhase
    study_phase_label: str
    protocol_code: str
    official_version: str
    official_date_value: str | None = None
    official_date_precision: DatePrecision | None = None
    rule_set_id: str
    rule_set_revision: int


class OfficialProjectListResponse(_StrictModel):
    projects: list[OfficialProjectDTO]


class ProjectVersionDTO(_StrictModel):
    """某个已发布规则版本：revision、方案版本、哈希与规则条数。"""

    rule_set_revision: int
    protocol_version_id: str
    official_version: str
    official_date_value: str | None = None
    official_date_precision: DatePrecision | None = None
    sha256: str
    rule_count: int
    published_at: str


class ProjectOfficialVersionResponse(_StrictModel):
    project: OfficialProjectDTO
    versions: list[ProjectVersionDTO]
    publication_count: int


class ProtocolSessionResponse(_StrictModel):
    job_id: str
    job_type: str
    state: str
    state_label: str
    progress_completed: int
    progress_total: int
    session_kind: str
    awaiting_user: str | None = None
    awaiting_user_label: str | None = None
    source_artifact_id: str | None = None
    file_name: str | None = None
    snapshot_id: str | None = None
    draft_id: str | None = None
    draft_revision_id: str | None = None
    draft_revision_number: int | None = None
    draft_status: str | None = None
    draft_status_label: str | None = None
    selected_phase: StudyPhase | None = None
    selected_phase_label: str | None = None
    protocol_code: str | None = None
    official_version: str | None = None
    recovery_checkpoint_id: str | None = None
    recovery_step_id: str | None = None
    next_action: str
    publishable: bool | None = None
    # 重新解构：目标正式项目投影（session_kind="re_deconstruction" 时有值）。
    target_project_id: str | None = None
    target_project_name: str | None = None
    target_project_code: str | None = None
    target_protocol_code: str | None = None
    target_study_phase: StudyPhase | None = None
    target_study_phase_label: str | None = None
    target_official_version: str | None = None
    target_rule_set_revision: int | None = None


class IdentityDecisionDTO(_StrictModel):
    identity_decision_id: str
    snapshot_id: str
    status: str
    status_label: str
    project_name: str | None = None
    project_code: str | None = None
    protocol_code: str | None = None
    official_version: str | None = None
    official_date_value: str | None = None
    official_date_precision: DatePrecision | None = None
    study_phase: StudyPhase | None = None
    study_phase_label: str | None = None
    confirmation_required: bool
    conflict_ids: list[str] = Field(default_factory=list)
    selected_candidate_ids: list[str] = Field(default_factory=list)


class PhaseCandidateDTO(_StrictModel):
    candidate_id: str
    phase: StudyPhase
    phase_label: str
    rationale: str
    source_excerpt: str


class MetadataCandidateDTO(_StrictModel):
    candidate_id: str
    field: str
    field_label: str
    value: str
    source_label: str
    source_excerpt: str
    is_fallback: bool


class MetadataConflictCandidateDTO(_StrictModel):
    candidate_id: str
    value: str
    source_label: str


class MetadataConflictDTO(_StrictModel):
    conflict_id: str
    field: str
    field_label: str
    reason: str
    candidates: list[MetadataConflictCandidateDTO] = Field(default_factory=list)


class IdentityReviewResponse(_StrictModel):
    job_id: str
    snapshot_id: str
    confirmation_required: bool
    identity: IdentityDecisionDTO
    phase_candidates: list[PhaseCandidateDTO] = Field(default_factory=list)
    metadata_candidates: list[MetadataCandidateDTO] = Field(default_factory=list)
    metadata_conflicts: list[MetadataConflictDTO] = Field(default_factory=list)


class ConfirmIdentityRequest(_StrictModel):
    protocol_code: str = Field(min_length=1, max_length=128)
    project_name: str = Field(min_length=1, max_length=256)
    project_code: str | None = Field(default=None, max_length=128)
    official_version: str = Field(min_length=1, max_length=64)
    official_date_value: str = Field(min_length=1, max_length=64)
    official_date_precision: Literal["year", "month", "day"]
    study_phase: StudyPhase
    selected_candidate_ids: list[str] = Field(default_factory=list)
    actor: str = Field(default="用户", min_length=1, max_length=128)


class DraftRevisionResponse(_StrictModel):
    job_id: str
    revision_id: str
    draft_id: str
    revision_number: int
    status: str
    status_label: str
    reason: str
    reason_label: str
    actor: str
    created_at: datetime
    study_phase: StudyPhase
    study_phase_label: str
    protocol_code: str | None = None
    official_version: str | None = None
    rule_count: int
    workflow_stage_count: int
    content: dict[str, Any]
    diff: dict[str, Any] | None = None


class ManualEditRequest(_StrictModel):
    expected_revision_id: str = Field(min_length=1, max_length=128)
    draft: ProtocolDeconstructionDraft
    actor: str = Field(default="用户", min_length=1, max_length=128)


class FeedbackRequest(_StrictModel):
    expected_revision_id: str = Field(min_length=1, max_length=128)
    draft: ProtocolDeconstructionDraft
    feedback_kind: DraftFeedbackKind
    feedback_note: str | None = None
    actor: str = Field(default="用户", min_length=1, max_length=128)


class DraftActionRequest(_StrictModel):
    expected_revision_id: str = Field(min_length=1, max_length=128)


class IntegrityIssueDTO(_StrictModel):
    issue_code: str
    check_name: str
    level: str
    problem: str
    impact: str
    next_action: str
    affected_refs: list[str]
    repair_scope: list[str]


class IntegrityCheckDTO(_StrictModel):
    check_name: str
    passed: bool
    issue_count: int


class IntegrityResponse(_StrictModel):
    job_id: str
    publishable: bool
    blocking_count: int
    review_count: int
    reminder_count: int
    summary: str
    checks: list[IntegrityCheckDTO]
    issues: list[IntegrityIssueDTO]


class SourcesResponse(_StrictModel):
    job_id: str
    snapshot_id: str
    selected_phase: StudyPhase
    selected_phase_label: str
    source_spans: dict[str, Any]
    source_materials: dict[str, Any]


class PublishRequest(_StrictModel):
    idempotency_key: str = Field(min_length=1, max_length=256)
    actor: str = Field(default="用户", min_length=1, max_length=128)


class PublishResponse(_StrictModel):
    job_id: str
    project_id: str
    protocol_version_id: str
    rule_set_id: str
    rule_set_revision: int
    replay: bool
