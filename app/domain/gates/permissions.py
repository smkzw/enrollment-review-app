from __future__ import annotations

from app.domain.contracts.agents import AgentPublishedEntity
from app.domain.contracts.enums import AgentNode


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
