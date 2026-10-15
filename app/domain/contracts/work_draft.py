"""Source-linked working results are separate from clinical signature records."""
from typing import Literal
from datetime import datetime

from pydantic import Field, StrictBool, model_validator

from .common import ContractModel
from .enums import ComponentDecision, RuleKind


class WorkDraftSourcePage(ContractModel):
    source_document_version_id: str
    page_artifact_id: str
    page_number: int = Field(ge=1)
    effective_text: str
    effective_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_category: str | None = None
    extraction_complete: bool = False

    @model_validator(mode="after")
    def validate_text(self):
        import hashlib
        if hashlib.sha256(self.effective_text.encode("utf-8")).hexdigest() != self.effective_text_sha256:
            raise ValueError("冻结资料文字与原有内容指纹不一致")
        return self


class SystemIssue(ContractModel):
    kind: Literal["method_unsupported", "page_unreadable", "model_output_invalid", "excerpt_unverified",
                  "extraction_failed", "component_unstructured", "fact_closure_failed", "model_unavailable"]
    affected_codes: list[str]
    detail: str = Field(min_length=1)
    alternative: str = Field(min_length=1)
    source_document_version_id: str | None = None
    page_artifact_id: str | None = None
    page_number: int | None = Field(default=None, ge=1)


class WorkDraftEvidenceRef(ContractModel):
    fact_id: str
    locator_id: str
    source_document_version_id: str
    page_artifact_id: str
    page_number: int = Field(ge=1)
    excerpt: str = Field(min_length=1)


class WorkDraftSourceRef(ContractModel):
    source_document_version_id: str
    page_artifact_id: str
    page_number: int = Field(ge=1)
    excerpt: str | None
    disposition: Literal["mentioned", "not_seen", "unresolved"]


class WorkDraftReasonPart(ContractModel):
    condition_id: str = Field(min_length=1)
    condition_text: str = Field(min_length=1)
    reason_text: str = Field(min_length=1)
    requires_attention: StrictBool


class WorkDraftItem(ContractModel):
    item_id: str
    review_run_id: str
    official_code: str
    rule_component_id: str | None = None
    rule_kind: RuleKind
    title: str
    source_text: str
    decision: ComponentDecision | None = None
    confidence: Literal["high", "low"] | None = None
    confidence_reason: str | None = None
    reason_text: str
    reason_parts: list[WorkDraftReasonPart] = Field(default_factory=list, exclude_if=lambda value: not value)
    evidence_refs: list[WorkDraftEvidenceRef] = Field(default_factory=list)
    source_read_refs: list[WorkDraftSourceRef] = Field(default_factory=list, exclude_if=lambda value: not value)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_group: str | None = None
    system_issue: SystemIssue | None = None
    acknowledgement_id: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)
    confirmation_kind: Literal["medical_manager", "builder_verification"] | None = Field(
        default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def validate_confidence(self):
        if len({part.condition_id for part in self.reason_parts}) != len(self.reason_parts):
            raise ValueError("判断依据的条件身份不得重复")
        determinate = self.decision in {
            ComponentDecision.INCLUSION_MET, ComponentDecision.INCLUSION_NOT_MET,
            ComponentDecision.EXCLUSION_TRIGGERED, ComponentDecision.EXCLUSION_NOT_TRIGGERED,
            ComponentDecision.REQUIREMENT_MET, ComponentDecision.REQUIREMENT_NOT_MET,
        }
        if determinate != (self.confidence is not None):
            raise ValueError("置信仅用于有据确定结果，且必须明示高或低")
        if self.system_issue is not None and self.decision is not None:
            raise ValueError("系统问题不能冒充临床结论")
        if (self.acknowledgement_id is None) != (self.confirmation_kind is None):
            raise ValueError("核实标记必须有对应的核实记录")
        if self.acknowledgement_id is not None and (not determinate or self.confidence != "high"):
            raise ValueError("只能核实已有确定结论，不能改变未决或系统问题")
        return self


class WorkDraftAcknowledgement(ContractModel):
    acknowledgement_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    official_code: str = Field(pattern=r"^(IN|EX|REQ)-\d{2}$")
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    base_review_run_id: str = Field(min_length=1)
    base_item_id: str = Field(min_length=1)
    work_draft_job_id: str = Field(min_length=1)
    actor_kind: Literal["medical_manager", "builder_verification"]
    created_at: datetime


def acknowledgement_input_hash(item: WorkDraftItem, evaluator_version: str) -> str:
    """Bind clinical content and calculation inputs, not result IDs or display confidence."""
    from app.domain.publication import canonical_hash
    return canonical_hash({"evaluator_version": evaluator_version, "item": item.model_dump(mode="json", exclude={
        "item_id", "review_run_id", "confidence", "confidence_reason", "acknowledgement_id", "confirmation_kind"})})
