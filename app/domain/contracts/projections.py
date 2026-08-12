from __future__ import annotations

from pydantic import Field, model_validator

from .common import VersionedModel
from .enums import EpisodeMainStatus


STATUS_SORT_RANK = {
    EpisodeMainStatus.CLEAR_BARRIER: 0,
    EpisodeMainStatus.CURRENT_GAP: 1,
    EpisodeMainStatus.CONFLICT: 2,
    EpisodeMainStatus.PROFESSIONAL_JUDGMENT: 3,
    EpisodeMainStatus.FUTURE_ATTENTION: 4,
    EpisodeMainStatus.NO_CLEAR_BARRIER: 5,
}


def main_status_from_counts(
    *,
    barrier_count: int,
    current_gap_count: int,
    conflict_count: int,
    professional_count: int,
    future_count: int,
) -> EpisodeMainStatus:
    if barrier_count:
        return EpisodeMainStatus.CLEAR_BARRIER
    if current_gap_count:
        return EpisodeMainStatus.CURRENT_GAP
    if conflict_count:
        return EpisodeMainStatus.CONFLICT
    if professional_count:
        return EpisodeMainStatus.PROFESSIONAL_JUDGMENT
    if future_count:
        return EpisodeMainStatus.FUTURE_ATTENTION
    return EpisodeMainStatus.NO_CLEAR_BARRIER


class EpisodeRollup(VersionedModel):
    review_episode_id: str = Field(min_length=1)
    input_assessment_ids: list[str] = Field(default_factory=list)
    input_expectation_ids: list[str] = Field(default_factory=list)
    input_action_ids: list[str] = Field(default_factory=list)
    main_status: EpisodeMainStatus
    sort_rank: int = Field(ge=0)
    barrier_count: int = Field(ge=0)
    current_gap_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    professional_judgment_count: int = Field(ge=0)
    future_attention_count: int = Field(ge=0)
    provenance_followup_count: int = Field(ge=0)
    gap_counts: dict[str, int]
    gate_result_id: str = Field(min_length=1)
    publication_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_projection_consistency(self) -> "EpisodeRollup":
        expected = main_status_from_counts(
            barrier_count=self.barrier_count,
            current_gap_count=self.current_gap_count,
            conflict_count=self.conflict_count,
            professional_count=self.professional_judgment_count,
            future_count=self.future_attention_count,
        )
        if self.main_status != expected:
            raise ValueError(f"EpisodeRollup 主状态必须由计数推导为 {expected.value}")
        if self.sort_rank != STATUS_SORT_RANK[expected]:
            raise ValueError("EpisodeRollup sort_rank 与主状态不一致")
        from app.domain.publication import publication_fingerprint

        payload = self.model_dump(mode="json", exclude={"publication_fingerprint"})
        expected_fingerprint = publication_fingerprint(
            entity_type="episode_rollup",
            gate_result_id=self.gate_result_id,
            payload=payload,
        )
        if self.publication_fingerprint != expected_fingerprint:
            raise ValueError("EpisodeRollup 缺少有效的 Projection Gate 发布指纹")
        return self
