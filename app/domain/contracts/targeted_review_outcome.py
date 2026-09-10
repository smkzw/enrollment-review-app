"""Auxiliary factual outcomes cannot represent accepted facts or clinical findings."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.contracts.page_review import PageLaneFailure


class TargetedReviewOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    outcome_kind: Literal["candidate_agreement_unaccepted", "conflict_pending_user",
                          "conflict_preserved_read_failed", "next_round_pending"]
    round_number: Literal[1, 2]
    round_budget: Literal[2] = 2
    round_skipped: bool = False
    candidate_auto_accept: Literal[False] = False
    clinical_findings_allowed: Literal[False] = False
    cue_kind: Literal["blind", "prior_excerpts_visible"]
    agreed_candidate_targets: list[str] = Field(default_factory=list)
    pending_targets: list[str] = Field(default_factory=list)
    handwriting_candidate_agreement: bool = False
    handwriting_pending: bool = False
    read_failures: list[PageLaneFailure] = Field(default_factory=list)
    requires_user_review: bool

    @model_validator(mode="after")
    def check_outcome(self):
        if self.handwriting_candidate_agreement and self.handwriting_pending:
            raise ValueError("手写复核不能同时一致和待核实")
        pending = bool(self.pending_targets) or self.handwriting_pending
        expected = ("conflict_preserved_read_failed" if self.read_failures else
                    "candidate_agreement_unaccepted" if not pending else
                    "next_round_pending" if self.round_number == 1 else "conflict_pending_user")
        if self.outcome_kind != expected:
            raise ValueError("辅助复核结果与实际读道状态不一致")
        if not pending and not self.agreed_candidate_targets and not self.handwriting_candidate_agreement:
            raise ValueError("辅助复核不得把空结果视为一致")
        if self.requires_user_review != (expected in {"conflict_preserved_read_failed", "conflict_pending_user"}):
            raise ValueError("复核待办与结果不一致")
        return self
