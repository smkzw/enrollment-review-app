from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel, VersionedModel
from .enums import AgentNode, AgentOutputKind, AgentWriteScope, CriticAction


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
    raw_output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=1)
    attempt: int = Field(ge=1)
    max_attempts: int = Field(ge=1, le=3)
    duration_ms: int = Field(ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    gate_result_id: str | None = None

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
        return self


class CriticRun(VersionedModel):
    critic_run_id: str = Field(min_length=1)
    assessment_candidate_id: str = Field(min_length=1)
    action: CriticAction
    evidence_span_ids: list[str] = Field(default_factory=list)
    rationale: str = Field(min_length=1)


class GateResult(VersionedModel):
    gate_result_id: str = Field(min_length=1)
    gate_name: str = Field(min_length=1)
    accepted: bool
    issue_codes: list[str] = Field(default_factory=list)
    output_entity_ids: list[str] = Field(default_factory=list)


AgentPublishedEntity = Literal[
    "protocol_draft",
    "evidence_candidate",
    "assessment_candidate",
    "critic_run",
    "final_assessment",
    "action_request",
    "episode_rollup",
]
