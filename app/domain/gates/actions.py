from __future__ import annotations

from datetime import datetime

from app.domain.contracts.agents import GateResult
from app.domain.contracts.common import ContractModel
from app.domain.contracts.enums import (
    ActionState,
    BlockingLevel,
    GapType,
    GateOutcome,
)
from app.domain.contracts.review import ActionRequest
from app.domain.gates.assessment import (
    AssessmentPublication,
    validate_assessment_publication,
)
from app.domain.policies import (
    derive_action_blocking_level,
    derive_action_directive,
)
from app.domain.publication import _build_gate_owned_model, canonical_hash
from app.domain.registry import TrustedPublicationRegistry


class ActionGateError(ValueError):
    pass


class ActionPublication(ContractModel):
    action: ActionRequest
    gate_result: GateResult
    assessment_publication: AssessmentPublication


def _validate_action_request_state(action: ActionRequest) -> None:
    expected = derive_action_blocking_level(action.gap_type)
    if action.blocking_level != expected:
        raise ActionGateError(
            f"{action.gap_type.value} 的 blocking_level 必须由 Gate 推导为 {expected.value}"
        )


def publish_action_request(
    *,
    assessment_publication: AssessmentPublication,
    action_id: str,
    gap_type: GapType,
    gate_result_id: str,
    input_revision_map: dict[str, int],
    created_at: datetime,
    registry: TrustedPublicationRegistry,
) -> ActionPublication:
    assessment = assessment_publication.assessment
    assessment_gate = assessment_publication.gate_result
    registry.require("final_assessment", assessment.assessment_id, assessment)
    registry.require("gate_result", assessment_gate.gate_result_id, assessment_gate)
    validate_assessment_publication(assessment_publication, registry)
    if (
        assessment_gate.gate_name != "assessment-publication-gate"
        or assessment_gate.result != GateOutcome.ACCEPTED
        or assessment.assessment_id not in assessment_gate.accepted_entity_refs
        or assessment_gate.output_hash
        != canonical_hash(assessment.model_dump(mode="json"))
    ):
        raise ActionGateError("ActionRequest 只能由 accepted FinalAssessment 触发")
    if gap_type not in assessment.gap_types:
        raise ActionGateError("ActionRequest gap_type 必须来自 FinalAssessment")
    rule_set = registry.require("rule_set", assessment.rule_set_id)
    component_matches = [
        component
        for rule in rule_set.rules
        for component in rule.components
        if component.rule_component_id == assessment.rule_component_id
    ]
    if len(component_matches) != 1:
        raise ActionGateError("ActionRequest 必须唯一对应当前规则组件")
    review_context = registry.require(
        "review_context",
        assessment_publication.review_context.context_id,
        assessment_publication.review_context,
    )
    directive = derive_action_directive(
        gap_type=gap_type,
        component=component_matches[0],
        expectations=review_context.expectations,
        episode_stage=review_context.review_episode.stage,
        assessment_evidence_span_ids=assessment.evidence_span_ids,
    )
    blocking_level = derive_action_blocking_level(gap_type)
    action = _build_gate_owned_model(
        ActionRequest,
        entity_type="action_request",
        gate_result_id=gate_result_id,
        data={
            "revision": 1,
            "action_id": action_id,
            "project_id": assessment.project_id,
            "protocol_version_id": assessment.protocol_version_id,
            "subject_id": assessment.subject_id,
            "rule_set_id": assessment.rule_set_id,
            "rule_set_revision": assessment.rule_set_revision,
            "review_episode_id": assessment.review_episode_id,
            "evidence_snapshot_id": assessment.evidence_snapshot_id,
            "review_run_id": assessment.review_run_id,
            "assessment_id": assessment.assessment_id,
            "rule_component_id": assessment.rule_component_id,
            "gap_type": gap_type,
            "target_party": directive.target_party,
            "requested_action": directive.requested_action,
            "acceptable_evidence": directive.acceptable_evidence,
            "due_stage": directive.due_stage,
            "blocking_level": blocking_level,
            "trigger_evidence_span_id": directive.trigger_evidence_span_id,
            "state": ActionState.OPEN,
            "recompute_scope": list(directive.recompute_scope),
            "transitions": [],
        },
    )
    related_expectation_ids = sorted(
        item.expectation_id
        for item in review_context.expectations
        if item.requirement_id
        in {
            requirement.requirement_id
            for requirement in component_matches[0].evidence_requirements
        }
    )
    input_entity_refs = [
        assessment.assessment_id,
        assessment_gate.gate_result_id,
        review_context.context_id,
        component_matches[0].rule_component_id,
        *related_expectation_ids,
    ]
    input_payload = {
        "assessment": assessment.model_dump(mode="json"),
        "assessment_gate": assessment_gate.model_dump(mode="json"),
        "review_context_sha256": review_context.context_sha256,
        "component": component_matches[0].model_dump(mode="json"),
        "gap_type": gap_type.value,
        "directive": {
            "target_party": directive.target_party.value,
            "requested_action": directive.requested_action,
            "acceptable_evidence": directive.acceptable_evidence,
            "due_stage": directive.due_stage.value,
            "recompute_scope": list(directive.recompute_scope),
            "trigger_evidence_span_id": directive.trigger_evidence_span_id,
        },
    }
    gate_result = GateResult(
        gate_result_id=gate_result_id,
        gate_name="action-publication-gate",
        result=GateOutcome.ACCEPTED,
        input_scope_hash=canonical_hash(input_payload),
        input_revision_map=input_revision_map,
        input_entity_refs=input_entity_refs,
        accepted_entity_refs=[action.action_id],
        affected_scope=list(directive.recompute_scope),
        recompute_scope=list(directive.recompute_scope),
        idempotency_key=f"action:{action_id}:1",
        created_at=created_at,
        output_hash=canonical_hash(action.model_dump(mode="json")),
    )
    return ActionPublication(
        action=action,
        gate_result=gate_result,
        assessment_publication=assessment_publication,
    )


def validate_action_publication(
    publication: ActionPublication,
    registry: TrustedPublicationRegistry,
) -> GateResult:
    action = publication.action
    gate = publication.gate_result
    assessment_publication = publication.assessment_publication
    assessment = assessment_publication.assessment
    assessment_gate = assessment_publication.gate_result
    registry.require("action_request", action.action_id, action)
    registry.require("gate_result", gate.gate_result_id, gate)
    validate_assessment_publication(assessment_publication, registry)
    _validate_action_request_state(action)
    if (
        gate.gate_name != "action-publication-gate"
        or gate.result != GateOutcome.ACCEPTED
        or action.action_id not in gate.accepted_entity_refs
        or action.assessment_id not in gate.input_entity_refs
        or assessment_gate.gate_result_id not in gate.input_entity_refs
        or gate.output_hash != canonical_hash(action.model_dump(mode="json"))
        or assessment_gate.result != GateOutcome.ACCEPTED
        or assessment.assessment_id not in assessment_gate.accepted_entity_refs
        or assessment_gate.output_hash
        != canonical_hash(assessment.model_dump(mode="json"))
        or action.assessment_id != assessment.assessment_id
        or action.rule_component_id != assessment.rule_component_id
        or (
            action.project_id,
            action.protocol_version_id,
            action.subject_id,
            action.rule_set_id,
            action.rule_set_revision,
            action.review_episode_id,
            action.evidence_snapshot_id,
            action.review_run_id,
        )
        != (
            assessment.project_id,
            assessment.protocol_version_id,
            assessment.subject_id,
            assessment.rule_set_id,
            assessment.rule_set_revision,
            assessment.review_episode_id,
            assessment.evidence_snapshot_id,
            assessment.review_run_id,
        )
    ):
        raise ActionGateError("ActionRequest 未通过 accepted GateResult 发布")
    expected = publish_action_request(
        assessment_publication=assessment_publication,
        action_id=action.action_id,
        gap_type=action.gap_type,
        gate_result_id=gate.gate_result_id,
        input_revision_map=gate.input_revision_map,
        created_at=gate.created_at,
        registry=registry,
    )
    if publication.model_dump(mode="json") != expected.model_dump(mode="json"):
        raise ActionGateError("ActionPublication 未通过完整上游 Gate 闭包重算")
    return gate
