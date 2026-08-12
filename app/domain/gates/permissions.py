from __future__ import annotations

from app.domain.contracts.agents import AgentCallContract, AgentPublishedEntity, GateResult
from app.domain.contracts.enums import AgentNode, GateOutcome


class AgentPermissionError(ValueError):
    pass


ALLOWED_OUTPUTS: dict[AgentNode, set[AgentPublishedEntity]] = {
    AgentNode.PROTOCOL_DECONSTRUCTOR: {"protocol_draft"},
    AgentNode.EVIDENCE_NORMALIZER: {"evidence_candidate"},
    AgentNode.ELIGIBILITY_ASSESSOR: {"assessment_candidate"},
    AgentNode.SAFETY_PROVENANCE_CRITIC: {"critic_run"},
}


def require_agent_write_permission(node: AgentNode, entity: AgentPublishedEntity) -> None:
    if entity not in ALLOWED_OUTPUTS[node]:
        raise AgentPermissionError(f"{node.value} 无权写入 {entity}")


def require_accepted_agent_call(
    agent_call: AgentCallContract, gate_result: GateResult
) -> None:
    if (
        gate_result.gate_name != "agent-output-schema-gate"
        or gate_result.result != GateOutcome.ACCEPTED
        or agent_call.agent_call_id not in gate_result.input_entity_refs
        or agent_call.agent_call_id not in gate_result.accepted_entity_refs
        or gate_result.input_scope_hash != agent_call.input_scope_hash
        or gate_result.input_revision_map != agent_call.input_revision_map
        or gate_result.output_hash != agent_call.output_hash
        or gate_result.gate_result_id not in agent_call.gate_result_ids
    ):
        raise AgentPermissionError("AgentCall 未通过绑定输出哈希的 accepted GateResult")
