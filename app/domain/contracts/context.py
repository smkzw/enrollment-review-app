from __future__ import annotations

from pydantic import Field, model_validator

from .common import VersionedModel
from .evidence import ConflictGroup, EvidenceExpectation
from .review import ReviewEpisode


class ReviewContextSnapshot(VersionedModel):
    context_id: str = Field(min_length=1)
    review_episode: ReviewEpisode
    rule_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    protocol_integrity_gate_result_id: str = Field(min_length=1)
    evidence_gate_result_id: str = Field(min_length=1)
    expectations: list[EvidenceExpectation]
    conflict_groups: list[ConflictGroup]
    half_life_days: dict[str, float] = Field(default_factory=dict)
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_context(self) -> "ReviewContextSnapshot":
        from app.domain.publication import canonical_hash

        episode_id = self.review_episode.review_episode_id
        if any(item.review_episode_id != episode_id for item in self.expectations):
            raise ValueError("审核上下文中的证据要求必须属于当前审核节点")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"context_sha256"})
        )
        if self.context_sha256 != expected:
            raise ValueError("审核上下文快照哈希无效")
        return self
