"""Attribute a searched absence without guessing requirement/predicate links."""
from collections.abc import Mapping, Sequence

from app.domain.contracts.enums import GapType, ReviewStage
from app.domain.contracts.rules import RuleComponent, iter_atomic_predicates
from app.domain.policies import STAGE_RANK


def missing_judgment_predicates(
    component: RuleComponent, gaps: Mapping[str, GapType],
    selections: Mapping[str, Sequence[str]],
    *, episode_stage: ReviewStage, workflow_stage_id: str | None,
    requirement_workflow_stage_ids: Mapping[str, str],
) -> frozenset[str]:
    """Only an explicit, fully absent group replaces that predicate's uncertainty.

    No truth is inferred and no fact is selected. Legacy unattributed judgment
    requirements cannot establish which predicate's uncertainty they explain.
    """
    requirements = [item for item in component.evidence_requirements
                    if STAGE_RANK[item.due_stage] <= STAGE_RANK[episode_stage]
                    and not (item.due_stage == episode_stage
                             and requirement_workflow_stage_ids.get(item.requirement_id)
                             != workflow_stage_id)
                    and (item.requirement_id in gaps or "investigator_assessment" in {
                        value.strip().casefold() for value in item.required_source_types})]
    if any(not item.predicate_ids for item in requirements):
        return frozenset()
    professional = {item.predicate_id for expression in (
        component.expression, component.exception_expression,
    ) if expression is not None for item in iter_atomic_predicates(expression)
                    if item.requires_professional_judgment}
    missing = set()
    for predicate_id in professional:
        linked = [item for item in requirements if predicate_id in item.predicate_ids]
        if (linked and predicate_id in selections and not selections[predicate_id]
                and all(gaps.get(item.requirement_id) == GapType.PROFESSIONAL_JUDGMENT
                        for item in linked)):
            missing.add(predicate_id)
    return frozenset(missing)
