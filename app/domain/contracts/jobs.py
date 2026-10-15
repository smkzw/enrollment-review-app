from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from .common import VersionedModel
from .enums import JobEventType


class JobEvent(VersionedModel):
    job_event_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    event_type: JobEventType
    step_id: str | None = None
    occurred_at: datetime
    attempt: int = Field(default=1, ge=1)
    checkpoint_id: str | None = None
    retryable: bool = False
    progress_completed: int = Field(default=0, ge=0)
    progress_total: int = Field(default=0, ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)


class ReviewRunDiff(VersionedModel):
    review_run_diff_id: str = Field(min_length=1)
    prior_review_run_id: str = Field(min_length=1)
    current_review_run_id: str = Field(min_length=1)
    changed_fact_ids: list[str] = Field(default_factory=list)
    changed_assessment_ids: list[str] = Field(default_factory=list)
    opened_action_ids: list[str] = Field(default_factory=list)
    closed_action_ids: list[str] = Field(default_factory=list)
    stale_projection_ids: list[str] = Field(default_factory=list)
