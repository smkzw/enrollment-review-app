from __future__ import annotations

from collections import Counter

from pydantic import Field

from app.domain.contracts.common import VersionedModel
from app.domain.contracts.enums import (
    ActionState,
    BlockingLevel,
    ComponentDecision,
    EpisodeMainStatus,
    ExpectationStatus,
    GapType,
)
from app.domain.contracts.evidence import EvidenceExpectation
from app.domain.contracts.review import ActionRequest, FinalAssessment


STATUS_SORT_RANK = {
    EpisodeMainStatus.CLEAR_BARRIER: 0,
    EpisodeMainStatus.CURRENT_GAP: 1,
    EpisodeMainStatus.CONFLICT: 2,
    EpisodeMainStatus.PROFESSIONAL_JUDGMENT: 3,
    EpisodeMainStatus.FUTURE_ATTENTION: 4,
    EpisodeMainStatus.NO_CLEAR_BARRIER: 5,
}


class EpisodeRollup(VersionedModel):
    main_status: EpisodeMainStatus
    sort_rank: int = Field(ge=0)
    barrier_count: int = Field(ge=0)
    current_gap_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    professional_judgment_count: int = Field(ge=0)
    future_attention_count: int = Field(ge=0)
    provenance_followup_count: int = Field(ge=0)
    gap_counts: dict[str, int]


def rollup_episode(
    assessments: list[FinalAssessment],
    expectations: list[EvidenceExpectation],
    actions: list[ActionRequest],
) -> EpisodeRollup:
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
        if item.decision == ComponentDecision.INDETERMINATE
        and item.blocking_level == BlockingLevel.BLOCKING
    ) + sum(
        1
        for item in expectations
        if item.status in {ExpectationStatus.ABSENT, ExpectationStatus.REFERENCED_MISSING}
        and item.gap_type != GapType.FUTURE_STAGE_NOT_DUE
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

    if barrier_count:
        main_status = EpisodeMainStatus.CLEAR_BARRIER
    elif current_gap_count:
        main_status = EpisodeMainStatus.CURRENT_GAP
    elif conflict_count:
        main_status = EpisodeMainStatus.CONFLICT
    elif professional_count:
        main_status = EpisodeMainStatus.PROFESSIONAL_JUDGMENT
    elif future_count:
        main_status = EpisodeMainStatus.FUTURE_ATTENTION
    else:
        main_status = EpisodeMainStatus.NO_CLEAR_BARRIER

    return EpisodeRollup(
        main_status=main_status,
        sort_rank=STATUS_SORT_RANK[main_status],
        barrier_count=barrier_count,
        current_gap_count=current_gap_count,
        conflict_count=conflict_count,
        professional_judgment_count=professional_count,
        future_attention_count=future_count,
        provenance_followup_count=provenance_count,
        gap_counts={key.value: value for key, value in sorted(all_gaps.items(), key=lambda item: item[0].value)},
    )
