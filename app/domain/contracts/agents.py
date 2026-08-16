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
    RuntimeErrorCode,
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
    typed_output_hashes: dict[str, str] = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    attempt: int = Field(ge=1)
    max_attempts: int = Field(ge=1, le=3)
    duration_ms: int = Field(ge=0)
    started_at: datetime
    finished_at: datetime
    outcome: RunOutcome
    error_codes: list[RuntimeErrorCode] = Field(default_factory=list)
    recompute_scope: list[str] = Field(min_length=1)
    trigger: str = Field(min_length=1)
    parent_event_id: str | None = None
    same_session_group_id: str | None = None
    project_id: str | None = None
    protocol_version_id: str | None = None
    rule_set_id: str | None = None
    rule_set_revision: int | None = Field(default=None, ge=1)
    subject_id: str | None = None
    review_episode_id: str | None = None
    review_run_id: str | None = None
    evidence_snapshot_id: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    gate_result_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_node_scope(self) -> "AgentCallContract":
        from app.domain.publication import canonical_hash

        if any(
            len(value) != 64 or any(char not in "0123456789abcdef" for char in value)
            for value in self.typed_output_hashes.values()
        ):
            raise ValueError("typed_output_hashes 必须使用小写 SHA-256")
        if self.output_hash != canonical_hash(self.typed_output_hashes):
            raise ValueError("AgentCall.output_hash 必须绑定实际 typed output 哈希表")
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
        if not self.project_id or not self.protocol_version_id:
            raise ValueError("AgentCall 必须绑定 project_id 和 protocol_version_id")
        if self.node == AgentNode.PROTOCOL_DECONSTRUCTOR:
            if not self.source_ids:
                raise ValueError("方案解构 AgentCall 必须绑定方案来源")
            if self.attempt > 1 and not self.same_session_group_id:
                raise ValueError("方案解构的定向修复必须继续使用同一会话")
        elif not all(
            [
                self.subject_id,
                self.rule_set_id,
                self.rule_set_revision,
                self.review_episode_id,
                self.review_run_id,
                self.evidence_snapshot_id,
                self.source_ids,
            ]
        ):
            raise ValueError(
                "受试者 AgentCall 必须绑定 Subject/Episode/Run/Snapshot/Source"
            )
        return self


class CriticRun(VersionedModel):
    critic_run_id: str = Field(min_length=1)
    assessment_candidate_id: str = Field(min_length=1)
    target_refs: list[str] = Field(min_length=1)
    disposition: CriticAction
    trigger_codes: list[str] = Field(min_length=1)
    reason_codes: list[str] = Field(min_length=1)
    evidence_span_ids: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)
    affected_scope: list[str] = Field(min_length=1)
    required_followup: list[str] = Field(default_factory=list)
    input_scope_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    gate_result_refs: list[str] = Field(default_factory=list)
    created_by_agent_call_id: str = Field(min_length=1)
    critic_revision: int = Field(default=1, ge=1)


class GateResult(VersionedModel):
    gate_result_id: str = Field(min_length=1)
    gate_name: str = Field(min_length=1)
    code_version: Literal["gate_contract/v1"] = "gate_contract/v1"
    result: GateOutcome
    input_scope_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_revision_map: dict[str, int] = Field(default_factory=dict)
    input_entity_refs: list[str] = Field(min_length=1)
    error_codes: list[RuntimeErrorCode] = Field(default_factory=list)
    accepted_entity_refs: list[str] = Field(default_factory=list)
    rejected_entity_refs: list[str] = Field(default_factory=list)
    affected_scope: list[str] = Field(min_length=1)
    recompute_scope: list[str] = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    parent_event_id: str | None = None
    created_at: datetime
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_outcome_refs(self) -> "GateResult":
        if self.result == GateOutcome.ACCEPTED:
            if not self.accepted_entity_refs or self.rejected_entity_refs or self.error_codes:
                raise ValueError("accepted GateResult 必须仅包含已接受实体")
        elif not self.rejected_entity_refs or not self.error_codes:
            raise ValueError("rejected/blocked GateResult 必须说明被拒实体与错误代码")
        return self


AgentPublishedEntity = Literal[
    "protocol_draft",
    "evidence_candidate",
    "assessment_candidate",
    "critic_run",
    "final_assessment",
    "action_request",
    "episode_rollup",
]
