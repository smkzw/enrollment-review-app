"""Request/response contracts for durable protocol-control execution."""
from __future__ import annotations

from pydantic import Field

from app.api.v2.schemas import _StrictModel
from app.domain.contracts.protocol_controls import ProtocolControlCandidate
from app.domain.contracts.rules import WorkflowStage


class StartProtocolControlExecutionRequest(_StrictModel):
    """Public start contract; execution tuning stays in server configuration."""

    source_job_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=256)


class StartProtocolControlExecutionResponse(_StrictModel):
    job_id: str
    state: str
    state_label: str
    created: bool
    source_job_id: str
    snapshot_id: str
    manifest_id: str


class ProtocolControlExecutionStatusResponse(_StrictModel):
    """只读发布检查点契约：只有完成且核对通过的整理结果才带检查点。"""

    job_id: str
    state: str
    state_label: str
    source_job_id: str
    status: str
    status_label: str
    publishable_checkpoint_id: str | None = None
    candidate_count: int | None = Field(default=None, ge=0)


class ProtocolControlRequirementsResponse(_StrictModel):
    job_id: str
    source_job_id: str
    checkpoint_id: str
    candidates: list[ProtocolControlCandidate]
    workflow_stages: list[WorkflowStage]
    relation_target_labels: dict[str, str]
