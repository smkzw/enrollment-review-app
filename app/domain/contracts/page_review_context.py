"""Minimal server-frozen episode context for independent page reads."""

from pydantic import Field

from .common import ContractModel, DateValue
from .enums import AnchorType, ReviewStage


class PageReviewContext(ContractModel):
    review_episode_id: str = Field(min_length=1)
    episode_revision: int = Field(ge=1)
    stage: ReviewStage
    workflow_stage_id: str | None = None
    anchor_dates: dict[AnchorType, DateValue] = Field(default_factory=dict)
