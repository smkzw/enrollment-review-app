"""Auxiliary truth over qualified evidence, not retest permission or adoption."""
from dataclasses import dataclass, field
from typing import Literal

from app.domain.contracts.enums import TruthValue
from app.domain.expression import EvaluationContext, EvaluationResult, _evaluate_bound_predicates, _combine_bound_expression
from app.domain.publication import canonical_hash
from app.services.predicate_proposition_calculation import calculate_predicate_propositions
from app.services.qualified_binding_selection import (
    ReceiptVerifiedQualifiedBindingSelections,
    ReceiptVerifiedWorkDraftSelections,
)
from app.services.eligibility_review_projection import _phase3_date_value
from app.services.repeat_condition_selection import iter_scoped_repeat_conditions


@dataclass(frozen=True)
class RepeatTriggerCalculation:
    component_id: str
    condition_id: str
    condition_sha256: str
    repeat_group_id: str
    scope_sha256: str
    owner_references: tuple[tuple[str, Literal["trigger", "permission"]], ...]
    selection_sha256: str
    context_sha256: str
    result: EvaluationResult
    target_kind: Literal["repeat", "initial_without_repeat"] = "repeat"
    written_permission: EvaluationResult | None = None
    frequency_evaluations: dict[str, dict] = field(default_factory=dict)
    replacement_authorized: bool = field(default=False, init=False)


def calculate_repeat_trigger_conditions(
    selections: ReceiptVerifiedQualifiedBindingSelections | ReceiptVerifiedWorkDraftSelections,
    context: EvaluationContext,
) -> tuple[RepeatTriggerCalculation, ...]:
    """Evaluate each sealed target scope; truth alone never authorizes replacement."""
    if not isinstance(selections, (
        ReceiptVerifiedQualifiedBindingSelections, ReceiptVerifiedWorkDraftSelections,
    )):
        raise TypeError("复查条件只能读取已核实回执的资料选择")
    selections.require_unchanged()
    source = selections.predicate_frozen_input
    if selections.candidate_family != "predicate" or source is None:
        raise ValueError("官方复查条件须使用同类方案的资料选择")
    authority = source.authority
    if ((context.project_id, context.subject_id, context.review_episode_id, context.evidence_snapshot_id)
            != (authority.project_id, authority.subject_id, authority.review_episode_id,
                authority.evidence_snapshot_v2_id)
            or context.anchor_dates != source.episode.anchor_dates
            or set(context.accepted_fact_ids) != {item.fact_id for item in source.facts}):
        raise ValueError("复查条件与当前节点及资料范围不一致")
    source_facts = {item.fact_id: item for item in source.facts}
    for fact in context.facts:
        original = source_facts[fact.fact_id]
        if (any(getattr(fact, name) != getattr(original, name)
                for name in ("fact_type", "value", "unit", "polarity"))
                or fact.effective_date != _phase3_date_value(original.date_range)
                or fact.evidence_span_ids != original.locator_ids):
            raise ValueError("复查条件的计算资料与已核实原文内容不同")
    context_hash = canonical_hash(context.model_dump(mode="json"))
    calculations = []
    for parent_id, owner_id, condition, identities, row, outcomes in iter_scoped_repeat_conditions(selections):
        by_identity = {item.identity_sha256: item for item in outcomes}
        selected = {key: by_identity[identity] for key, identity in identities.items()}
        propositions = calculate_predicate_propositions(
            selections, context, repeat_triggers_only=True, condition_selection=row)
        from app.services.frequency_atom_calculation import calculate_frequency_atoms
        frequency = calculate_frequency_atoms(selections, context, condition_selection=row)
        frequency_by_predicate = {key: frequency[identity] for key, identity in identities.items() if identity in frequency}
        chosen = {key: list(frequency_by_predicate[key].result.used_fact_ids)
                  if key in frequency_by_predicate else list(item.fact_ids) for key, item in selected.items()}
        atom_results = _evaluate_bound_predicates(
            [condition.expression], context, predicate_fact_ids=chosen,
            unverified_predicate_ids=frozenset(key for key, item in selected.items() if item.status != "usable"),
            proposition_evaluations=propositions.get(parent_id, {}),
            frequency_evaluations=frequency_by_predicate,
        )
        result = _combine_bound_expression(condition.expression, atom_results)
        if result.truth == TruthValue.UNKNOWN:
            result.reason_codes = sorted(set(result.reason_codes) | {
                reason for item in outcomes for reason in item.unresolved_reasons})
        owner = next(item for component in source.components for item in component.binding_predicates
                     if item.predicate_identity_sha256 == owner_id)
        scheme = owner.predicate.repeat_scheme
        written_permission = None
        if scheme.permission_condition_id == condition.condition_id:
            from app.domain.contracts.predicate_binding import iter_binding_atoms
            from app.services.repeat_permission_calculation import written_permission_result, written_permission_scoped_to_target
            written = {atom.predicate.predicate_id for atom in iter_binding_atoms(condition.expression)
                       if atom.predicate.requires_professional_judgment
                       and written_permission_scoped_to_target(row, identities[atom.predicate.predicate_id])
                       and selected[atom.predicate.predicate_id].status == "usable"
                       and row.get("written_content_support", {}).get(identities[atom.predicate.predicate_id])}
            written_permission = written_permission_result(
                family="predicate", condition=condition, atom_results=atom_results, written_atom_ids=written)
        calculations.append(RepeatTriggerCalculation(
            component_id=parent_id, condition_id=condition.condition_id,
            condition_sha256=canonical_hash(condition.model_dump(mode="json")),
            repeat_group_id=row["repeat_group_id"], scope_sha256=canonical_hash(row),
            owner_references=tuple((owner_id, role) for role, reference in (
                ("trigger", scheme.trigger_condition_id), ("permission", scheme.permission_condition_id)
            ) if reference == condition.condition_id),
            selection_sha256=selections.material.selection_sha256, context_sha256=context_hash, result=result,
            target_kind=row["target_kind"],
            written_permission=written_permission,
            frequency_evaluations={key: value.model_dump(mode="json") for key, value in frequency.items()},
        ))
    return tuple(calculations)
