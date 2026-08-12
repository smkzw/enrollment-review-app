from __future__ import annotations

from collections import Counter
from datetime import datetime

from app.domain.contracts.agents import GateResult
from app.domain.contracts.common import VersionedModel
from app.domain.contracts.enums import (
    ActionState,
    BlockingLevel,
    ComponentDecision,
    ExpectationStatus,
    GapType,
    GateOutcome,
)
from app.domain.contracts.evidence import EvidenceExpectation
from app.domain.contracts.projections import (
    EpisodeRollup,
    STATUS_SORT_RANK,
    main_status_from_counts,
)
from app.domain.gates.actions import ActionPublication, validate_action_publication
from app.domain.gates.assessment import (
    AssessmentPublication,
    validate_assessment_publication,
)
from app.domain.policies import derive_expectation_blocking_level
from app.domain.publication import _build_gate_owned_model, canonical_hash
from app.domain.registry import TrustedPublicationRegistry


class EpisodeRollupPublication(VersionedModel):
    rollup: EpisodeRollup
    gate_result: GateResult


def derive_episode_rollup(
    *,
    review_episode_id: str,
    assessments,
    expectations: list[EvidenceExpectation],
    actions,
    gate_result_id: str,
) -> EpisodeRollup:
    """Derive the projection from already-authorized inputs.

    Publication callers must validate the complete upstream closure before using
    this pure function. Keeping the truth table separate lets tests exercise the
    projection without manufacturing accepted GateResults.
    """
    decisions = Counter(item.decision for item in assessments)
    gaps = Counter(gap for item in assessments for gap in item.gap_types)
    expectation_gaps = Counter(
        item.gap_type for item in expectations if item.gap_type is not None
    )
    all_gaps = gaps + expectation_gaps

    barrier_count = (
        decisions[ComponentDecision.INCLUSION_NOT_MET]
        + decisions[ComponentDecision.EXCLUSION_TRIGGERED]
    )
    current_gap_count = sum(
        1
        for item in assessments
        if item.decision
        in {ComponentDecision.INDETERMINATE, ComponentDecision.REQUIREMENT_NOT_MET}
        and item.blocking_level == BlockingLevel.BLOCKING
    ) + sum(
        1
        for item in expectations
        if derive_expectation_blocking_level(item.status, item.gap_type)
        == BlockingLevel.BLOCKING
    )
    conflict_count = decisions[ComponentDecision.CONFLICT]
    professional_count = decisions[ComponentDecision.PROFESSIONAL_JUDGMENT]
    future_count = decisions[ComponentDecision.NOT_DUE] + sum(
        1 for item in expectations if item.status == ExpectationStatus.NOT_DUE
    )
    provenance_count = sum(
        1
        for action in actions
        if action.gap_type == GapType.PROVENANCE_FOLLOWUP
        and action.state in {ActionState.OPEN, ActionState.REOPENED}
    )

    main_status = main_status_from_counts(
        barrier_count=barrier_count,
        current_gap_count=current_gap_count,
        conflict_count=conflict_count,
        professional_count=professional_count,
        future_count=future_count,
    )
    return _build_gate_owned_model(
        EpisodeRollup,
        entity_type="episode_rollup",
        gate_result_id=gate_result_id,
        data={
            "review_episode_id": review_episode_id,
            "input_assessment_ids": [item.assessment_id for item in assessments],
            "input_expectation_ids": [item.expectation_id for item in expectations],
            "input_action_ids": [item.action_id for item in actions],
            "main_status": main_status,
            "sort_rank": STATUS_SORT_RANK[main_status],
            "barrier_count": barrier_count,
            "current_gap_count": current_gap_count,
            "conflict_count": conflict_count,
            "professional_judgment_count": professional_count,
            "future_attention_count": future_count,
            "provenance_followup_count": provenance_count,
            "gap_counts": {
                key.value: value
                for key, value in sorted(all_gaps.items(), key=lambda item: item[0].value)
            },
        },
    )


def publish_episode_rollup(
    *,
    review_episode_id: str,
    assessment_publications: list[AssessmentPublication],
    expectations: list[EvidenceExpectation],
    action_publications: list[ActionPublication],
    gate_result_id: str,
    input_revision_map: dict[str, int],
    created_at: datetime,
    registry: TrustedPublicationRegistry,
) -> EpisodeRollupPublication:
    episode = registry.require("review_episode", review_episode_id)
    rule_set = registry.require("rule_set", episode.rule_set_id)
    expected_component_ids = {
        component.rule_component_id
        for rule in rule_set.rules
        for component in rule.components
    }
    assessments = [item.assessment for item in assessment_publications]
    actions = [item.action for item in action_publications]
    assessment_ids = [item.assessment_id for item in assessments]
    assessment_component_ids = [item.rule_component_id for item in assessments]
    if len(assessment_ids) != len(set(assessment_ids)) or len(
        assessment_component_ids
    ) != len(set(assessment_component_ids)):
        raise ValueError("EpisodeRollup 不接受重复 Assessment 或重复规则组件")
    if set(assessment_component_ids) != expected_component_ids:
        raise ValueError("EpisodeRollup 必须包含当前规则集全部规则组件的审核结果")
    registered_assessments = {
        item.assessment_id: item
        for item in registry.all("final_assessment")
        if item.review_episode_id == review_episode_id
    }
    if set(assessment_ids) != set(registered_assessments):
        raise ValueError("EpisodeRollup Assessment 集合与服务端已登记结果不一致")
    for publication in assessment_publications:
        validate_assessment_publication(publication, registry)
        assessment = publication.assessment
        gate = publication.gate_result
        if (
            gate.gate_name != "assessment-publication-gate"
            or gate.result != GateOutcome.ACCEPTED
            or assessment.assessment_id not in gate.accepted_entity_refs
            or gate.output_hash != canonical_hash(assessment.model_dump(mode="json"))
            or assessment.review_episode_id != review_episode_id
        ):
            raise ValueError("EpisodeRollup 输入包含未验收或跨 Episode 的 Assessment")
    assessment_id_set = {
        item.assessment.assessment_id for item in assessment_publications
    }
    expected_expectations = {
        item.expectation_id: item
        for item in registry.all("evidence_expectation")
        if item.review_episode_id == review_episode_id
    }
    expectation_ids = [item.expectation_id for item in expectations]
    expectation_requirement_ids = [item.requirement_id for item in expectations]
    expected_requirement_ids = {
        requirement.requirement_id
        for rule in rule_set.rules
        for component in rule.components
        for requirement in component.evidence_requirements
    }
    if len(expectation_ids) != len(set(expectation_ids)):
        raise ValueError("EpisodeRollup 不接受重复 EvidenceExpectation")
    if len(expectation_requirement_ids) != len(set(expectation_requirement_ids)):
        raise ValueError("EpisodeRollup 每项证据要求必须且只能对应一个覆盖状态")
    if set(expectation_requirement_ids) != expected_requirement_ids:
        raise ValueError("EpisodeRollup 必须包含当前规则集全部应备证据状态")
    if set(expectation_ids) != set(expected_expectations):
        raise ValueError("EpisodeRollup EvidenceExpectation 集合不完整")
    for expectation in expectations:
        registry.require(
            "evidence_expectation", expectation.expectation_id, expectation
        )

    action_ids = [item.action_id for item in actions]
    action_keys = [(item.assessment_id, item.gap_type) for item in actions]
    if len(action_ids) != len(set(action_ids)) or len(action_keys) != len(
        set(action_keys)
    ):
        raise ValueError("EpisodeRollup 不接受重复 ActionRequest")
    expected_action_keys = {
        (assessment.assessment_id, gap_type)
        for assessment in assessments
        for gap_type in assessment.gap_types
    }
    if set(action_keys) != expected_action_keys:
        raise ValueError("EpisodeRollup 必须为每个已确认缺口包含一项对应待办")
    registered_actions = {
        item.action_id: item
        for item in registry.all("action_request")
        if item.review_episode_id == review_episode_id
    }
    if set(action_ids) != set(registered_actions):
        raise ValueError("EpisodeRollup ActionRequest 集合与服务端已登记结果不一致")
    for publication in action_publications:
        action = publication.action
        if action.assessment_id not in assessment_id_set:
            raise ValueError("EpisodeRollup Action 未引用当前输入 Assessment")
        validate_action_publication(publication, registry)
        if (
            action.review_episode_id != review_episode_id
            or action.assessment_id not in assessment_id_set
        ):
            raise ValueError("EpisodeRollup 输入包含跨 Episode/Assessment 的 Action")
    if any(item.review_episode_id != review_episode_id for item in expectations):
        raise ValueError("EpisodeRollup 输入包含跨 Episode 的 EvidenceExpectation")
    rollup = derive_episode_rollup(
        review_episode_id=review_episode_id,
        assessments=assessments,
        expectations=expectations,
        actions=actions,
        gate_result_id=gate_result_id,
    )
    input_entity_refs = [
        review_episode_id,
        *[item.gate_result.gate_result_id for item in assessment_publications],
        *[item.gate_result.gate_result_id for item in action_publications],
        *rollup.input_assessment_ids,
        *rollup.input_expectation_ids,
        *rollup.input_action_ids,
    ]
    gate_result = GateResult(
        gate_result_id=gate_result_id,
        gate_name="episode-rollup-projection-gate",
        result=GateOutcome.ACCEPTED,
        input_scope_hash=canonical_hash(input_entity_refs),
        input_revision_map=input_revision_map,
        input_entity_refs=input_entity_refs,
        accepted_entity_refs=[review_episode_id, f"rollup:{review_episode_id}"],
        affected_scope=[review_episode_id],
        recompute_scope=[review_episode_id],
        idempotency_key=f"rollup:{review_episode_id}:{canonical_hash(input_revision_map)}",
        created_at=created_at,
        output_hash=canonical_hash(rollup.model_dump(mode="json")),
    )
    return EpisodeRollupPublication(rollup=rollup, gate_result=gate_result)
