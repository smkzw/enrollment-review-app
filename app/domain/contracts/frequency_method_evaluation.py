"""Frequency evidence has its own source-fidelity approval, not a repeat-policy approval."""
from typing import Literal

from .judgment_method_evaluation import JudgmentEvaluationManifest


class FrequencyEvaluationManifest(JudgmentEvaluationManifest):
    version: Literal["frequency-evaluation-manifest/v1"] = "frequency-evaluation-manifest/v1"
    evaluation_kind: Literal["frequency_statement_fidelity"] = "frequency_statement_fidelity"
