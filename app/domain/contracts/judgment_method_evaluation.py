"""Evaluation identity for the conjunction of source and written-content checks."""
from datetime import datetime, timedelta
from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel
from .review_method_adoption import Digest, Text, EvaluatedBindingMethod, EvaluatedRoute, EvaluationMetric


class EvaluatedJudgmentMethod(ContractModel):
    candidate_family: Literal["predicate", "control"]
    source_qualification_method: EvaluatedBindingMethod
    content_contract: Text
    content_prompt_version: Text
    content_summary_version: Text
    content_routes: dict[Literal["main-A", "main-B"], EvaluatedRoute]
    content_consumer_version: Text

    @model_validator(mode="after")
    def require_same_family_and_dual_routes(self):
        if self.source_qualification_method.candidate_family != self.candidate_family:
            raise ValueError("书面判断评测与来源核实须属于同类审核要求")
        if set(self.content_routes) != {"main-A", "main-B"}:
            raise ValueError("书面判断评测须完整记录两路独立模型")
        return self


class JudgmentEvaluationManifest(ContractModel):
    version: Literal["judgment-evaluation-manifest/v1"] = "judgment-evaluation-manifest/v1"
    evaluation_kind: Literal["written_judgment_content_fidelity"] = "written_judgment_content_fidelity"
    source_corpus_sha256: Digest
    gold_split_sha256: Digest
    scoring_version: Text
    scoring_report_sha256: Digest
    methods: list[EvaluatedJudgmentMethod] = Field(min_length=1)
    observed_metrics: list[EvaluationMetric] = Field(min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def require_unique_scope(self):
        families = [item.candidate_family for item in self.methods]
        names = [item.name for item in self.observed_metrics]
        if len(families) != len(set(families)) or len(names) != len(set(names)):
            raise ValueError("书面判断评测范围及指标名称不得重复")
        if self.created_at.utcoffset() != timedelta(0):
            raise ValueError("书面判断评测时间须明确采用UTC")
        return self
