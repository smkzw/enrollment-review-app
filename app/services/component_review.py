"""One component calculation shared by projections and formal review assembly.

This calculation does not validate model correspondence or grant publication.
Callers must supply source-validated inputs; the publication boundary rechecks them.
"""
from dataclasses import dataclass
from collections.abc import Mapping, Sequence

from app.domain.contracts.enums import BlockingLevel, ComponentDecision, GapType, ReviewStage, RuleKind
from app.domain.contracts.evidence import ConflictGroup
from app.domain.contracts.evaluation_result import FrequencyAtomEvaluation
from app.domain.contracts.rules import RuleComponent
from app.domain.expression import ComponentEvaluation, EvaluationContext, EvaluationResult, RepeatAtomEvaluation, evaluate_component
from app.domain.gates.assessment import RequirementGapState, derive_component_decision, derive_gate_gap_types
from app.domain.policies import derive_assessment_blocking_level


@dataclass(frozen=True)
class ComponentReviewResult:
    evaluation: ComponentEvaluation
    gaps: frozenset[GapType]
    decision: ComponentDecision
    blocking_level: BlockingLevel


def calculate_component_review(
    *, component: RuleComponent, rule_kind: RuleKind, context: EvaluationContext,
    episode_stage: ReviewStage, expectations: Sequence[RequirementGapState],
    conflicts: Sequence[ConflictGroup], source_gaps: frozenset[GapType] = frozenset(),
    workflow_stage_id: str | None = None,
    requirement_workflow_stage_ids: Mapping[str, str] | None = None,
    predicate_fact_ids: Mapping[str, Sequence[str]] | None = None,
    unverified_predicate_ids: frozenset[str] = frozenset(),
    missing_judgment_predicate_ids: frozenset[str] = frozenset(),
    judgment_gap_by_requirement: Mapping[str, GapType] | None = None,
    verified_judgment_requirement_ids: frozenset[str] = frozenset(),
    proposition_evaluations: Mapping[str, EvaluationResult] | None = None,
    repeat_evaluations: Mapping[str, RepeatAtomEvaluation] | None = None,
    frequency_evaluations: Mapping[str, FrequencyAtomEvaluation] | None = None,
) -> ComponentReviewResult:
    evaluation = evaluate_component(
        component, context, predicate_fact_ids=predicate_fact_ids,
        unverified_predicate_ids=unverified_predicate_ids,
        missing_judgment_predicate_ids=missing_judgment_predicate_ids,
        proposition_evaluations=proposition_evaluations,
        repeat_evaluations=repeat_evaluations,
        frequency_evaluations=frequency_evaluations,
    )
    gaps = derive_gate_gap_types(
        component=component, evaluation=evaluation, episode_stage=episode_stage,
        expectations=list(expectations), conflict_groups=list(conflicts),
        workflow_stage_id=workflow_stage_id,
        requirement_workflow_stage_ids=requirement_workflow_stage_ids,
        source_gaps=source_gaps,
        requirement_gap_overrides=judgment_gap_by_requirement,
        verified_judgment_requirement_ids=verified_judgment_requirement_ids,
    )
    decision = derive_component_decision(rule_kind=rule_kind, evaluation=evaluation, gaps=gaps)
    return ComponentReviewResult(
        evaluation=evaluation, gaps=frozenset(gaps), decision=decision,
        blocking_level=derive_assessment_blocking_level(decision, gaps),
    )
