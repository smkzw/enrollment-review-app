"""Typed evaluation evidence and explicit method approval, never case signoff."""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import ContractModel

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Text = Annotated[str, Field(min_length=1, pattern=r"\S")]


class EvaluatedRoute(ContractModel):
    provider: Text
    base_url: Text
    model: Text
    reasoning_effort: Text
    max_tokens: int = Field(gt=0, strict=True)
    max_concurrency: int = Field(gt=0, strict=True)
    fallback_base_url: str


class EvaluatedBindingMethod(ContractModel):
    candidate_family: Literal["predicate", "control"]
    candidate_job_type: Text
    candidate_contract: Text
    candidate_prompt_version: Text
    candidate_batch_prompt_version: str | None
    qualification_contract: Text
    qualification_prompt_version: Text
    qualification_summary_version: Text
    consumer_algorithm_version: Text
    evaluator_version: Text
    publication_version: Text
    candidate_routes: dict[Literal["main-A", "main-B"], EvaluatedRoute]
    qualification_routes: dict[Literal["main-A", "main-B"], EvaluatedRoute]

    @model_validator(mode="after")
    def require_dual_routes(self):
        for routes in (self.candidate_routes, self.qualification_routes):
            if set(routes) != {"main-A", "main-B"}:
                raise ValueError("评测方法须完整记录两路独立读取配置")
        return self


class EvaluationMetric(ContractModel):
    name: Text
    definition: Text
    value: Decimal | None
    unit: Text
    unavailable_reason: str | None

    @model_validator(mode="after")
    def require_observed_or_unknown(self):
        if self.value is None:
            if not (self.unavailable_reason or "").strip():
                raise ValueError("未取得的指标须说明原因，不能记为零")
        elif not self.value.is_finite() or self.unavailable_reason is not None:
            raise ValueError("已取得的指标须为有限数值且不得同时标为未知")
        return self


class BindingEvaluationManifest(ContractModel):
    version: Literal["binding-evaluation-manifest/v1"] = "binding-evaluation-manifest/v1"
    evaluation_kind: Literal["binding_semantic_correspondence"] = "binding_semantic_correspondence"
    source_corpus_sha256: Digest
    gold_split_sha256: Digest
    scoring_version: Text
    scoring_report_sha256: Digest
    methods: list[EvaluatedBindingMethod] = Field(min_length=1)
    observed_metrics: list[EvaluationMetric] = Field(min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def require_unique_scope(self):
        families = [item.candidate_family for item in self.methods]
        names = [item.name for item in self.observed_metrics]
        if len(families) != len(set(families)) or len(names) != len(set(names)):
            raise ValueError("评测方法范围及指标名称不得重复")
        if self.created_at.utcoffset() != timedelta(0):
            raise ValueError("评测时间须明确采用UTC")
        return self


class ReviewMethodApproval(ContractModel):
    version: Literal["review-method-approval/v1"] = "review-method-approval/v1"
    evaluation_manifest_sha256s: list[Digest] = Field(min_length=1)
    approving_principal: Text
    approval_source_sha256: Digest
    approved_at: datetime
    decision: Literal["adopt_method_for_formal_calculation"]
    clinical_case_signoff: Literal[False] = False

    @model_validator(mode="after")
    def require_explicit_scope(self):
        if len(self.evaluation_manifest_sha256s) != len(set(self.evaluation_manifest_sha256s)):
            raise ValueError("批准所对应的评测记录不得重复")
        if self.approved_at.utcoffset() != timedelta(0):
            raise ValueError("批准时间须明确采用UTC")
        return self
