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
from app.domain.gates.assessment import AssessmentPublication
from app.domain.policies import derive_expectation_blocking_level
from app.domain.publication import _build_gate_owned_model, canonical_hash


class EpisodeRollupPublication(VersionedModel):
    rollup: EpisodeRollup
    gate_result: GateResult


def publish_episode_rollup(
    *,
    review_episode_id: str,
    assessment_publications: list[AssessmentPublication],
    expectations: list[EvidenceExpectation],
    action_publications: list[ActionPublication],
    gate_result_id: str,
    input_revision_map: dict[str, int],
    created_at: datetime,
) -> EpisodeRollupPublication:
    assessments = [item.assessment for item in assessment_publications]
    actions = [item.action for item in action_publications]
    for publication in assessment_publications:
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
    assessment_publication_by_id = {
        item.assessment.assessment_id: item for item in assessment_publications
    }
    assessment_ids = set(assessment_publication_by_id)
    for publication in action_publications:
        action = publication.action
        assessment_publication = assessment_publication_by_id.get(action.assessment_id)
        if assessment_publication is None:
            raise ValueError("EpisodeRollup Action 未引用当前输入 Assessment")
        validate_action_publication(
            publication,
            assessment_publication=assessment_publication,
        )
        if (
            action.review_episode_id != review_episode_id
            or action.assessment_id not in assessment_ids
        ):
            raise ValueError("EpisodeRollup 输入包含跨 Episode/Assessment 的 Action")
    if any(item.review_episode_id != review_episode_id for item in expectations):
        raise ValueError("EpisodeRollup 输入包含跨 Episode 的 EvidenceExpectation")
    decisions = Counter(item.decision for item in assessments)
    gaps = Counter(gap for item in assessments for gap in item.gap_types)
    expectation_gaps = Counter(item.gap_type for item in expectations if item.gap_type is not None)
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

    rollup = _build_gate_owned_model(
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
