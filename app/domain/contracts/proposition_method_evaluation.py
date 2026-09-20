"""Version-bound evaluation evidence for source-qualified proposition relations."""
from typing import Literal

from pydantic import model_validator

from .judgment_method_evaluation import JudgmentEvaluationManifest


class PropositionEvaluationManifest(JudgmentEvaluationManifest):
    version: Literal["proposition-evaluation-manifest/v1", "proposition-evaluation-manifest/v2"] = "proposition-evaluation-manifest/v2"
    evaluation_kind: Literal["pair_local_proposition_relation"] = "pair_local_proposition_relation"

    @model_validator(mode="after")
    def preserve_historical_scope(self):
        if self.version == "proposition-evaluation-manifest/v1" and any(
                method.candidate_family != "control" for method in self.methods):
            raise ValueError("旧版命题关系评测不能用于正式入排条件")
        return self
