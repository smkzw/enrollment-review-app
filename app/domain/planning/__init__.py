"""Phase 5 规划子域（Slice 5.3 确定性规划 / Slice 5.7 修订影响范围）。"""
from __future__ import annotations

from .fact_correction_impact import (
    NODE_RECOMPUTE_MESSAGE,
    SEED_KINDS,
    FactCorrectionImpactEntity,
    FactCorrectionImpactGraph,
    FactCorrectionImpactIndexFlags,
    FactCorrectionImpactSeed,
    FactReplacementSignature,
    LocatorDocumentBinding,
    LocatorEntityLink,
    ProfileRevisionIndex,
    plan_fact_correction_impact,
)
from .fact_normalization_planning import (
    FactNormalizationPlan,
    PageInput,
    PlannedCall,
    compute_call_input_hash,
    compute_input_scope_hash,
    plan_fact_normalization_calls,
    validate_calls_contiguous,
    validate_full_page_closure,
)

__all__ = [
    "NODE_RECOMPUTE_MESSAGE",
    "SEED_KINDS",
    "FactCorrectionImpactEntity",
    "FactCorrectionImpactGraph",
    "FactCorrectionImpactIndexFlags",
    "FactCorrectionImpactSeed",
    "FactReplacementSignature",
    "FactNormalizationPlan",
    "LocatorDocumentBinding",
    "LocatorEntityLink",
    "PageInput",
    "PlannedCall",
    "ProfileRevisionIndex",
    "compute_call_input_hash",
    "compute_input_scope_hash",
    "plan_fact_correction_impact",
    "plan_fact_normalization_calls",
    "validate_calls_contiguous",
    "validate_full_page_closure",
]
