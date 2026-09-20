"""Frozen scope for targeted rereading, not a clinical decision or acceptance."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PageReviewFocus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    original_reconciliation_id: str = Field(min_length=1)
    page_image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    review_episode_id: str = Field(min_length=1)
    round_number: Literal[1, 2]
    targets: tuple[str, ...] = ()
    time_review_targets: tuple[str, ...] = ()
    handwriting_review: bool = False
    previous_round_review_ids: tuple[str, ...] = ()
    candidate_excerpts: tuple[str, ...] = ()

    @field_validator("round_number", mode="before")
    @classmethod
    def strict_round(cls, value):
        if type(value) is not int:
            raise ValueError("复核轮次必须为整数")
        return value

    @model_validator(mode="after")
    def validate_round(self):
        if not self.targets and not self.handwriting_review:
            raise ValueError("复核必须指定事实项目或手写批注范围")
        if any(not value.strip() for value in (*self.targets, *self.candidate_excerpts)):
            raise ValueError("复核项目与候选摘录不得为空")
        if len(set(self.targets)) != len(self.targets):
            raise ValueError("复核项目不得重复")
        if (len(set(self.time_review_targets)) != len(self.time_review_targets)
                or not set(self.time_review_targets).issubset(self.targets)):
            raise ValueError("日期归属复核项目须唯一且属于本次复核范围")
        if self.round_number == 1 and (self.previous_round_review_ids or self.candidate_excerpts):
            raise ValueError("首轮复核不得预先展示候选答案")
        if self.round_number == 2 and (
            len(self.previous_round_review_ids) != 2
            or len(set(self.previous_round_review_ids)) != 2
            or any(not value.strip() for value in self.previous_round_review_ids)
        ):
            raise ValueError("第二轮须关联上一轮两个不同主读记录")
        return self
