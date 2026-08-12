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
from app.domain.contracts.review import ActionRequest, FinalAssessment
from app.domain.policies import derive_expectation_blocking_level
from app.domain.publication import build_published_model, canonical_hash


class EpisodeRollupPublication(VersionedModel):
    rollup: EpisodeRollup
    gate_result: GateResult


def publish_episode_rollup(
    *,
    review_episode_id: str,
    assessments: list[FinalAssessment],
    expectations: list[EvidenceExpectation],
    actions: list[ActionRequest],
    gate_result_id: str,
    input_revision_map: dict[str, int],
    created_at: datetime,
) -> EpisodeRollupPublication:
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

    rollup = build_published_model(
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
