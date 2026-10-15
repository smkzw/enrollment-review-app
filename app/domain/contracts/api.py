from __future__ import annotations

from pydantic import Field

from .common import VersionedModel
from .enums import ActionState
from .jobs import JobEvent
from .review import ActionRequest, FixtureV1, Project, Subject


class ProjectListResponse(VersionedModel):
    items: list[Project]


class SubjectListResponse(VersionedModel):
    project_id: str = Field(min_length=1)
    items: list[Subject]


class WorkspaceResponse(VersionedModel):
    workspace: FixtureV1


class ActionOverrideCommand(VersionedModel):
    expected_revision: int = Field(ge=1)
    to_state: ActionState
    reason: str = Field(min_length=1)
    evidence_span_ids: list[str] = Field(default_factory=list)


class ActionOverrideResponse(VersionedModel):
    action: ActionRequest


class JobStatusResponse(VersionedModel):
    job_id: str = Field(min_length=1)
    events: list[JobEvent]
