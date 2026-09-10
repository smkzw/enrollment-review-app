"""Request/response contracts for durable protocol-control execution."""
from __future__ import annotations

from pydantic import Field

from app.api.v2.schemas import _StrictModel


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
