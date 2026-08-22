"""V2 API 请求/响应契约：只做协议转换，中文词汇由 vocabulary 提供。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StepSpecIn(_StrictModel):
    step_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    max_attempts: int = Field(default=1, ge=1)
    retryable: bool = False
    depends_on: list[str] = Field(default_factory=list)


class CreateJobRequest(_StrictModel):
    idempotency_key: str = Field(min_length=1, max_length=256)
    job_type: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)
    steps: list[StepSpecIn] = Field(default_factory=list)


class CreateJobResponse(_StrictModel):
    job_id: str
    state: str
    state_label: str
    created: bool


class JobEventDTO(_StrictModel):
    seq: int = Field(ge=1)
    job_event_id: str
    event_type: str
    event_type_label: str
    step_id: str | None = None
    occurred_at: datetime
    attempt: int
    checkpoint_id: str | None = None
    retryable: bool
    progress_completed: int
    progress_total: int
    payload: dict[str, Any] = Field(default_factory=dict)


class JobStepDTO(_StrictModel):
    step_id: str
    name: str
    state: str
    state_label: str
    attempt: int
    max_attempts: int
    retryable: bool
    error_code: str | None = None
    error_classification: str | None = None
    retry_not_before: datetime | None = None
    depends_on: list[str] = Field(default_factory=list)


class JobStatusResponse(_StrictModel):
    job_id: str
    job_type: str
    state: str
    state_label: str
    cancel_requested: bool
    progress_completed: int
    progress_total: int
    error_code: str | None = None
    error_classification: str | None = None
    retryable_scope: list[str] = Field(default_factory=list)
    recovery_action: str
    created_at: datetime
    updated_at: datetime
    last_event_seq: int
    steps: list[JobStepDTO] = Field(default_factory=list)
    events: list[JobEventDTO] = Field(default_factory=list)


class JobActionResponse(_StrictModel):
    job_id: str
    state: str
    state_label: str
    changed: bool


class V2ErrorDetail(_StrictModel):
    code: str
    title: str
    detail: str
    recovery_action: str
    correlation_id: str
    context: dict[str, Any] | None = None


class V2ErrorEnvelope(_StrictModel):
    error: V2ErrorDetail


# ---------------------------------------------------------------------------
# Phase 4 受试者与审核节点（design.md §5.1）
# ---------------------------------------------------------------------------


class SubjectCreateRequest(_StrictModel):
    subject_code: str = Field(min_length=1, max_length=128)
    center_code: str | None = Field(default=None, max_length=128)
    center_name: str | None = Field(default=None, max_length=256)
    sex: str | None = Field(default=None, max_length=32)
    age_years: float | None = Field(default=None, ge=0)


class SubjectDTO(_StrictModel):
    subject_id: str
    subject_code: str
    project_id: str
    center_code: str | None = None
    center_name: str | None = None
    sex: str | None = None
    age_years: float | None = None
    revision: int


class SubjectListDTO(_StrictModel):
    project_id: str
    items: list[SubjectDTO] = Field(default_factory=list)


class EpisodeDTO(_StrictModel):
    review_episode_id: str
    subject_id: str
    project_id: str
    rule_set_id: str
    study_phase: str
    study_phase_label: str
    stage: str
    stage_label: str
    protocol_version_id: str
    rule_set_revision: int
    evidence_snapshot_id: str | None = None
    workflow_stage_id: str | None = None
    workflow_stage_label: str | None = None
    visit_window: str | None = None
    latest_evidence_snapshot_id: str | None = None
    active_evidence_snapshot_id: str | None = None
    active_evidence_processing_revision_id: str | None = None
    anchor_dates: dict[str, Any] = Field(default_factory=dict)
    due_at: datetime | None = None
    revision: int


class EpisodeListDTO(_StrictModel):
    subject_id: str
    items: list[EpisodeDTO] = Field(default_factory=list)
