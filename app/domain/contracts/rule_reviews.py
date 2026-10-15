from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from .common import VersionedModel

ReviewerKind = Literal["medical_manager", "builder_verification"]


class RuleReviewRecord(VersionedModel):
    record_id: str = Field(min_length=1)
    draft_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    official_code: str = Field(min_length=1)
    rule_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewer_kind: ReviewerKind
    reviewed_by: str = Field(min_length=1)
    reviewed_at: datetime
    action: Literal["approved", "revoked"]
    note: str | None = None
    result_variables: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result_variables(self):
        if any(not value.strip() for value in self.result_variables):
            raise ValueError("必需结果变量不能为空")
        if len(set(self.result_variables)) != len(self.result_variables):
            raise ValueError("必需结果变量不得重复")
        return self
