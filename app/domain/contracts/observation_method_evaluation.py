"""Version-bound evaluation for source-local observation correspondence."""
from typing import Literal

from .judgment_method_evaluation import JudgmentEvaluationManifest


class ObservationEvaluationManifest(JudgmentEvaluationManifest):
    version: Literal["observation-evaluation-manifest/v1"] = "observation-evaluation-manifest/v1"
    evaluation_kind: Literal["observation_relationship_fidelity"] = "observation_relationship_fidelity"
