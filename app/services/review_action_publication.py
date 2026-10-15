"""Create follow-ups from a persisted V2 assessment, within its owner's transaction."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.contracts.agents import GateResult
from app.domain.contracts.enums import ActionState, GateOutcome
from app.domain.contracts.review import ActionRequest
from app.domain.policies import derive_action_blocking_level
from app.domain.publication import _build_gate_owned_model, canonical_hash
from app.domain.review_action_directives import REVIEW_ACTION_DIRECTIVE_VERSION, derive_review_action_directive
from app.storage.models import ActionRequestRecord
from app.storage.repositories import (
    FINAL_ASSESSMENT_CONFIG, GATE_RESULT_CONFIG, REVIEW_RUN_CONFIG,
    ActionRequestRepository, AppendRepository, ScopeViolationError,
)
from app.storage.review_context_repository import ReviewContextV2Repository


def publish_review_actions(session: Session, *, assessment_id: str) -> tuple[ActionRequest, ...]:
    """No candidate/model input: upstream assessment publication is a prerequisite.

    Re-entry verifies the original creation receipt and preserves later handling.
    This helper neither commits nor registers a clinical assessment as accepted.
    """
    assessment = AppendRepository(session, FINAL_ASSESSMENT_CONFIG).get(assessment_id)
    run = AppendRepository(session, REVIEW_RUN_CONFIG).get(assessment.review_run_id)
    if assessment.schema_version != "review/v2" or run.schema_version != "review/v2":
        raise ScopeViolationError("新版办理入口只接受正式保存的新版审核结论")
    context = ReviewContextV2Repository(session).get(run.context_id)
    gates = AppendRepository(session, GATE_RESULT_CONFIG)
    assessment_gate = gates.get(assessment.gate_result_id)
    if (
        context.review_run_id != run.review_run_id
        or run.episode_revision != context.authority.episode_revision
        or any(getattr(run, key) != getattr(context.authority, key) for key in (
            "review_episode_id", "protocol_version_id", "rule_set_revision",
            "evidence_snapshot_v2_id", "complete_processing_revision_id",
        ))
        or any(getattr(assessment, key) != getattr(context.authority, key) for key in (
            "project_id", "subject_id", "review_episode_id", "protocol_version_id",
            "rule_set_id", "rule_set_revision", "evidence_snapshot_v2_id",
            "complete_processing_revision_id",
        ))
        or assessment_gate.gate_name != "assessment-publication-gate"
        or assessment_gate.result != GateOutcome.ACCEPTED
        or assessment_id not in assessment_gate.accepted_entity_refs
        or context.context_id not in assessment_gate.input_entity_refs
        or assessment_gate.output_hash != canonical_hash(assessment.model_dump(mode="json"))
    ):
        raise ScopeViolationError("该审核结论缺少完整的正式保存依据，未生成办理事项")
    repository = ActionRequestRepository(session)
    result = []
    for gap in sorted(set(assessment.gap_types), key=lambda value: value.value):
        directive = derive_review_action_directive(assessment=assessment, context=context, gap_type=gap)
        action_id = f"review-action:{canonical_hash([assessment_id, gap.value])[:32]}"
        gate_id = f"gate:{action_id}:1"
        data = {key: getattr(assessment, key) for key in (
            "project_id", "subject_id", "protocol_version_id", "rule_set_id", "rule_set_revision",
            "review_episode_id", "review_run_id", "assessment_id", "rule_component_id",
            "evidence_snapshot_v2_id", "complete_processing_revision_id",
        )}
        data.update(
            schema_version="review/v2", revision=1, action_id=action_id, gap_type=gap,
            state=ActionState.OPEN, transitions=[], target_party=directive.target_party,
            requested_action=directive.requested_action, acceptable_evidence=directive.acceptable_evidence,
            due_stage=directive.due_stage, blocking_level=derive_action_blocking_level(gap),
            recompute_scope=list(directive.recompute_scope), trigger_locator_id=directive.trigger_locator_id,
        )
        action = _build_gate_owned_model(ActionRequest, entity_type="action_request", gate_result_id=gate_id, data=data)
        gate = GateResult(
            gate_result_id=gate_id, gate_name="action-publication-gate", result=GateOutcome.ACCEPTED,
            input_scope_hash=canonical_hash({"version": REVIEW_ACTION_DIRECTIVE_VERSION,
                "context_sha256": context.context_sha256,
                "assessment": assessment.model_dump(mode="json"),
                "assessment_gate": assessment_gate.model_dump(mode="json"), "gap_type": gap.value}),
            input_revision_map={context.authority.review_episode_id: context.authority.episode_revision},
            input_entity_refs=[context.context_id, assessment_id, assessment_gate.gate_result_id],
            accepted_entity_refs=[action_id], affected_scope=[assessment.rule_component_id],
            recompute_scope=list(directive.recompute_scope), idempotency_key=f"action:{action_id}:1",
            created_at=assessment_gate.created_at, output_hash=canonical_hash(action.model_dump(mode="json")),
        )
        existing_gate = gates.get_or_none(gate_id)
        if existing_gate is not None:
            if existing_gate != gate:
                raise ScopeViolationError("已保存的办理要求与首次生成依据不同，未覆盖历史")
            current = repository.get(action_id)
            original_fields = set(data) - {"revision", "state", "transitions"}
            if any(getattr(current, key) != getattr(action, key) for key in original_fields):
                raise ScopeViolationError("办理事项的原始要求已变化，未重新创建")
            result.append(current)
        else:
            if session.get(ActionRequestRecord, action_id) is not None:
                raise ScopeViolationError("办理事项缺少首次保存依据，未覆盖历史")
            gates.save(gate)
            result.append(repository.save(action))
    return tuple(result)
