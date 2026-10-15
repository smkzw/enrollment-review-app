"""Create control follow-ups in the existing action table and lifecycle."""
from app.domain.contracts.agents import GateResult
from app.domain.contracts.control_action_origin import ControlActionOrigin
from app.domain.contracts.enums import ActionState, BlockingLevel, GateOutcome
from app.domain.contracts.review import ActionRequest
from app.domain.control_action_directives import control_action_targets
from app.domain.policies import ACTION_CONTENT, derive_action_blocking_level
from app.domain.publication import _build_gate_owned_model, canonical_hash
from app.storage.models import ActionRequestRecord
from app.storage.repositories import (
    ActionRequestRepository, AppendRepository, GATE_RESULT_CONFIG, ScopeViolationError,
)
from app.storage.review_context_repository import ReviewContextV2Repository
from app.storage.review_control_repository import ReviewControlRepository


def publish_control_actions(session, *, review_run_id: str) -> tuple[ActionRequest, ...]:
    """Caller owns the transaction. Only stored, verified control results enter."""
    snapshot = ReviewControlRepository(session).get_or_none(review_run_id)
    if snapshot is None:
        raise ScopeViolationError("尚未保存本次补充要求核对结果，不能生成办理事项")
    context = ReviewContextV2Repository(session).get(snapshot.context_id)
    authority = context.authority
    gates = AppendRepository(session, GATE_RESULT_CONFIG)
    source_gate = gates.get(snapshot.gate_result_id)
    repository = ActionRequestRepository(session)
    result = []
    for control in snapshot.outcomes:
        for obligation in control_action_targets(control):
            for gap in (obligation.gap_type,):
                action_id = "control-action:" + canonical_hash([
                    review_run_id, control.protocol_control_id,
                    obligation.obligation_id, obligation.obligation_group_id, gap.value,
                ])[:32]
                gate_id = f"gate:{action_id}:1"
                target, action, evidence = ACTION_CONTENT[gap]
                data = {key: getattr(authority, key) for key in (
                    "project_id", "subject_id", "protocol_version_id", "rule_set_id", "rule_set_revision",
                    "review_episode_id", "evidence_snapshot_v2_id", "complete_processing_revision_id",
                )}
                data.update(
                    schema_version="review/v2", revision=1, action_id=action_id,
                    review_run_id=review_run_id, assessment_id=None, rule_component_id=None,
                    control_origin=ControlActionOrigin(
                        review_run_id=review_run_id, protocol_control_id=control.protocol_control_id,
                        obligation_id=obligation.obligation_id, modality=obligation.modality,
                        obligation_group_id=obligation.obligation_group_id,
                    ),
                    gap_type=gap, target_party=target, requested_action=f"{obligation.statement}：{action}",
                    acceptable_evidence=evidence, due_stage=context.review_episode.stage,
                    blocking_level=(derive_action_blocking_level(gap) if obligation.modality.value == "mandatory"
                                    else BlockingLevel.ATTENTION),
                    trigger_locator_id=next(iter(obligation.locator_ids), None),
                    state=ActionState.OPEN, transitions=[], recompute_scope=[obligation.target_id],
                )
                candidate = _build_gate_owned_model(ActionRequest, entity_type="action_request", gate_result_id=gate_id, data=data)
                gate = GateResult(
                    gate_result_id=gate_id, gate_name="control-action-publication-gate", result=GateOutcome.ACCEPTED,
                    input_scope_hash=canonical_hash({"version": "control-action-directive/v1",
                        "snapshot": snapshot.model_dump(mode="json"), "source_gate": source_gate.model_dump(mode="json"),
                        "obligation_id": obligation.obligation_id,
                        "obligation_group_id": obligation.obligation_group_id, "gap_type": gap.value}),
                    input_revision_map={authority.review_episode_id: authority.episode_revision},
                    input_entity_refs=[context.context_id, review_run_id, source_gate.gate_result_id],
                    accepted_entity_refs=[action_id], affected_scope=[obligation.target_id],
                    recompute_scope=[obligation.target_id], idempotency_key=f"action:{action_id}:1",
                    created_at=snapshot.created_at, output_hash=canonical_hash(candidate.model_dump(mode="json")),
                )
                old_gate = gates.get_or_none(gate_id)
                if old_gate is not None:
                    if old_gate != gate:
                        raise ScopeViolationError("原办理要求与本次生成依据不同，未覆盖历史")
                    current = repository.get(action_id)
                    immutable = set(data) - {"revision", "state", "transitions"}
                    if any(getattr(current, key) != getattr(candidate, key) for key in immutable):
                        raise ScopeViolationError("已保存办理事项的原始要求不一致")
                    result.append(current)
                else:
                    if session.get(ActionRequestRecord, action_id) is not None:
                        raise ScopeViolationError("办理事项缺少首次保存依据，未重复创建")
                    gates.save(gate)
                    result.append(repository.save(candidate))
    return tuple(result)
