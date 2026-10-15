"""Source closure only; an exact excerpt is not proof of semantic correctness."""
from collections.abc import Sequence

from app.domain.contracts.protocol_controls import ControlMinimumEvidence, ProtocolStructureUnit


def validate_control_evidence_policy_sources(
    evidence: Sequence[ControlMinimumEvidence],
    source_span_ids: set[str],
    units: Sequence[ProtocolStructureUnit],
) -> None:
    for item in evidence:
        policy = item.source_policy
        if policy is None:
            raise ValueError("最低证据须明确记录来源要求；无法确定的事项应保留未知")
        if not set(policy.source_span_ids).issubset(source_span_ids):
            raise ValueError("资料来源要求引用了当前控制以外的原文")
        for span_id, excerpt in zip(policy.source_span_ids, policy.source_excerpts, strict=True):
            if not any(span_id in unit.source_span_ids and excerpt.strip() in unit.excerpt for unit in units):
                raise ValueError("资料来源要求的摘录无法在当前控制原文中核实")
