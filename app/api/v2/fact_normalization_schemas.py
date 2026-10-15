"""事实规范化 HTTP 契约（薄 DTO，无存储、无权威字段）。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.domain.contracts.evidence_normalizer import EvidenceNormalizerSourceTextRange


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FactNormalizationRequest(_StrictModel):
    """客户端仅可声明稳定意图；不得携带权威元组或配置编号。"""

    retry_failed_from_run_id: str | None = Field(default=None, min_length=1, max_length=128)
    revalidate_from_run_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def require_one_operation(self):
        if self.retry_failed_from_run_id and self.revalidate_from_run_id:
            raise ValueError("继续读取和核验已读记录不能混用")
        return self

    idempotency_intent: str | None = Field(
        default=None,
        description="可选的稳定意图标记；不参与权威派生或配置选择",
    )


class FactNormalizationSubmitDTO(_StrictModel):
    job_id: str
    run_id: str
    created: bool
    state: str
    state_label: str
    recovery_action: str


class NormalizationSourceDTO(_StrictModel):
    source_document_version_id: str
    page_artifact_id: str
    page_number: int = Field(ge=1)
    file_name: str


class NormalizationUnresolvedDTO(_StrictModel):
    item_id: str
    kind: Literal["unquoted_text", "reading_uncertainty"]
    message: str
    reason: str
    source_text_range: EvidenceNormalizerSourceTextRange | None
    sources: list[NormalizationSourceDTO]


class NormalizationUnresolvedPageDTO(_StrictModel):
    job_id: str
    content_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    run_id: str
    failed_page_count: int = Field(default=0, ge=0)
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    has_more: bool
    is_current: bool
    text_accounting_applied: bool
    can_revalidate_saved: bool = False
    revalidation_source_run_id: str | None = None
    evidence_snapshot_id: str
    processing_revision_id: str
    items: list[NormalizationUnresolvedDTO]
