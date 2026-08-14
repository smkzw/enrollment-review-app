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
