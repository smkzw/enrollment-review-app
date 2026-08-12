from __future__ import annotations

from datetime import datetime

from app.domain.contracts.agents import GateResult
from app.domain.contracts.common import ContractModel
from app.domain.contracts.enums import (
    ActionState,
    ActionTarget,
    BlockingLevel,
    GapType,
    GateOutcome,
    ReviewStage,
)
from app.domain.contracts.review import ActionRequest, ActionTransition
from app.domain.policies import derive_action_blocking_level
from app.domain.publication import build_published_model, canonical_hash


class ActionGateError(ValueError):
    pass


class ActionPublication(ContractModel):
    action: ActionRequest
    gate_result: GateResult


def validate_action_request(action: ActionRequest) -> None:
    expected = derive_action_blocking_level(action.gap_type)
    if action.blocking_level != expected:
        raise ActionGateError(
            f"{action.gap_type.value} 的 blocking_level 必须由 Gate 推导为 {expected.value}"
        )


def publish_action_request(
    *,
    action_id: str,
    rule_component_id: str,
    gap_type: GapType,
    target_party: ActionTarget,
    requested_action: str,
    acceptable_evidence: str,
    due_stage: ReviewStage,
    state: ActionState,
    recompute_scope: list[str],
    gate_result_id: str,
    input_entity_refs: list[str],
    input_revision_map: dict[str, int],
    created_at: datetime,
    trigger_evidence_span_id: str | None = None,
    transitions: list[ActionTransition] | None = None,
    revision: int = 1,
) -> ActionPublication:
    blocking_level = derive_action_blocking_level(gap_type)
    action = build_published_model(
        ActionRequest,
        entity_type="action_request",
        gate_result_id=gate_result_id,
        data={
            "revision": revision,
            "action_id": action_id,
            "rule_component_id": rule_component_id,
            "gap_type": gap_type,
            "target_party": target_party,
            "requested_action": requested_action,
            "acceptable_evidence": acceptable_evidence,
            "due_stage": due_stage,
            "blocking_level": blocking_level,
            "trigger_evidence_span_id": trigger_evidence_span_id,
            "state": state,
            "recompute_scope": recompute_scope,
            "transitions": transitions or [],
        },
    )
    gate_result = GateResult(
        gate_result_id=gate_result_id,
        gate_name="action-publication-gate",
        result=GateOutcome.ACCEPTED,
        input_scope_hash=canonical_hash(
            {
                "input_entity_refs": input_entity_refs,
                "rule_component_id": rule_component_id,
                "gap_type": gap_type.value,
                "target_party": target_party.value,
                "requested_action": requested_action,
                "acceptable_evidence": acceptable_evidence,
                "due_stage": due_stage.value,
            }
        ),
        input_revision_map=input_revision_map,
        input_entity_refs=input_entity_refs,
        accepted_entity_refs=[action.action_id],
        affected_scope=recompute_scope,
        recompute_scope=recompute_scope,
        idempotency_key=f"action:{action_id}:{revision}",
        created_at=created_at,
        output_hash=canonical_hash(action.model_dump(mode="json")),
    )
    return ActionPublication(action=action, gate_result=gate_result)
