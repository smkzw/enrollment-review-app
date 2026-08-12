from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel, VersionedModel
from .enums import (
    AgentNode,
    AgentOutputKind,
    AgentWriteScope,
    CriticAction,
    GateOutcome,
    RunOutcome,
)


class PromptVersion(VersionedModel):
    prompt_version_id: str = Field(min_length=1)
    node: AgentNode
    template_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version_id: str = Field(min_length=1)


class ModelConfigContract(VersionedModel):
    model_config_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    reasoning_effort: str = Field(min_length=1)
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)


class AgentCallContract(VersionedModel):
    agent_call_id: str = Field(min_length=1)
    node: AgentNode
    output_kind: AgentOutputKind
    write_scope: AgentWriteScope
    prompt_version_id: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
    input_scope_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_revision_map: dict[str, int] = Field(default_factory=dict)
    raw_output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=1)
    attempt: int = Field(ge=1)
    max_attempts: int = Field(ge=1, le=3)
    duration_ms: int = Field(ge=0)
    started_at: datetime
    finished_at: datetime
    outcome: RunOutcome
    error_codes: list[str] = Field(default_factory=list)
    recompute_scope: list[str] = Field(min_length=1)
    trigger: str = Field(min_length=1)
    parent_event_id: str | None = None
    same_session_group_id: str | None = None
    project_id: str | None = None
    subject_id: str | None = None
    review_episode_id: str | None = None
    review_run_id: str | None = None
    evidence_snapshot_id: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    gate_result_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_node_scope(self) -> "AgentCallContract":
        expected = {
            AgentNode.PROTOCOL_DECONSTRUCTOR: (AgentOutputKind.DRAFT, AgentWriteScope.PROTOCOL_DRAFT),
            AgentNode.EVIDENCE_NORMALIZER: (AgentOutputKind.CANDIDATE, AgentWriteScope.EVIDENCE_CANDIDATE),
            AgentNode.ELIGIBILITY_ASSESSOR: (AgentOutputKind.CANDIDATE, AgentWriteScope.ASSESSMENT_CANDIDATE),
            AgentNode.SAFETY_PROVENANCE_CRITIC: (AgentOutputKind.CRITIC_RUN, AgentWriteScope.CRITIC_RUN),
        }[self.node]
        if (self.output_kind, self.write_scope) != expected:
            raise ValueError("Agent 节点的输出类型或写入范围不匹配")
        if self.attempt > self.max_attempts:
            raise ValueError("attempt 不能大于 max_attempts")
        if self.finished_at < self.started_at:
            raise ValueError("finished_at 不能早于 started_at")
        return self


class CriticRun(VersionedModel):
    critic_run_id: str = Field(min_length=1)
    assessment_candidate_id: str = Field(min_length=1)
    disposition: CriticAction
    trigger_codes: list[str] = Field(min_length=1)
    reason_codes: list[str] = Field(min_length=1)
    evidence_span_ids: list[str] = Field(default_factory=list)
    rationale: str = Field(min_length=1)
    affected_scope: list[str] = Field(min_length=1)
    required_followup: list[str] = Field(default_factory=list)
    input_scope_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    gate_result_ids: list[str] = Field(default_factory=list)
    created_by_agent_call_id: str = Field(min_length=1)
    revision: int = Field(default=1, ge=1)


class GateResult(VersionedModel):
    gate_result_id: str = Field(min_length=1)
    gate_name: str = Field(min_length=1)
    code_version: Literal["gate_contract/v1"] = "gate_contract/v1"
    result: GateOutcome
    input_scope_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_revision_map: dict[str, int] = Field(default_factory=dict)
    input_entity_refs: list[str] = Field(min_length=1)
    error_codes: list[str] = Field(default_factory=list)
    accepted_entity_refs: list[str] = Field(default_factory=list)
    rejected_entity_refs: list[str] = Field(default_factory=list)
    affected_scope: list[str] = Field(min_length=1)
    recompute_scope: list[str] = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    parent_event_id: str | None = None
    created_at: datetime
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


AgentPublishedEntity = Literal[
    "protocol_draft",
    "evidence_candidate",
    "assessment_candidate",
    "critic_run",
    "final_assessment",
    "action_request",
    "episode_rollup",
]
