"""Auxiliary repeat-condition arithmetic; never an eligibility or adoption result."""
from dataclasses import dataclass, field
from typing import Literal

from app.domain.control_layer_evaluation import evaluate_control_condition
from app.domain.expression import EvaluationResult
from app.domain.publication import canonical_hash
from app.projections.control_atom_binding_input import project_control_atom_identities
from app.projections.control_calculation_experiment import _evaluate_control_selection
from app.services.qualified_binding_selection import (
    ReceiptVerifiedQualifiedBindingSelections,
    ReceiptVerifiedWorkDraftSelections,
)
from app.services.repeat_condition_selection import iter_scoped_repeat_conditions


@dataclass(frozen=True)
class ControlRepeatTriggerCalculation:
    protocol_control_id: str
    condition_id: str
    condition_sha256: str
    repeat_group_id: str
    scope_sha256: str
    owner_references: tuple[tuple[str, Literal["trigger", "permission"]], ...]
    frozen_input_sha256: str
    selection_sha256: str
    selections_sha256: str
    result: EvaluationResult
    target_kind: Literal["repeat", "initial_without_repeat"] = "repeat"
    written_permission: EvaluationResult | None = None
    frequency_evaluations: dict[str, dict] = field(default_factory=dict)
    replacement_authorized: bool = field(default=False, init=False)


def calculate_control_repeat_triggers(selections, *, conflict_groups, context=None) -> tuple[ControlRepeatTriggerCalculation, ...]:
    """Apply the existing arithmetic to each receipt-qualified observation scope."""
    if not isinstance(selections, (
        ReceiptVerifiedQualifiedBindingSelections, ReceiptVerifiedWorkDraftSelections,
    )):
        raise TypeError("复查条件只能读取已核实回执的资料选择")
    selections.require_unchanged()
    frozen = selections.control_input
    if selections.candidate_family != "control" or frozen is None:
        raise ValueError("补充要求的复查条件须使用同类方案资料")
    all_identities = project_control_atom_identities(frozen.publication, include_repeat_triggers=True)
    auxiliary_ids = {item.identity_sha256 for item in all_identities if item.layer == "repeat_trigger"}
    facts = {item.fact_id: item for item in frozen.evidence_input.facts}
    results = []
    for parent_id, owner_id, condition, identities, row, outcomes in iter_scoped_repeat_conditions(selections):
        chosen = {key: [] for key in auxiliary_ids}
        reasons_by_identity = {key: ["repeat_condition_outside_target"] for key in auxiliary_ids - set(identities.values())}
        for outcome in outcomes:
            chosen[outcome.identity_sha256] = list(outcome.fact_ids)
            if outcome.status != "usable":
                reasons_by_identity[outcome.identity_sha256] = list(outcome.unresolved_reasons)
        frequency = {}
        if context is not None:
            from app.services.frequency_atom_calculation import calculate_frequency_atoms
            frequency = calculate_frequency_atoms(selections, context, condition_selection=row)
            for identity, value in frequency.items():
                chosen[identity] = list(value.result.used_fact_ids)
        calculation, truths = _evaluate_control_selection(
            frozen, frozen_input_sha256=frozen.frozen_input_sha256, selections=chosen,
            conflict_groups=conflict_groups, unverified_atom_reasons=reasons_by_identity,
            proposition_relations=row["proposition_relations"],
            proposition_pair_gaps=row["unresolved_proposition_pairs"], repeat_triggers_only=True,
            frequency_evaluations=frequency,
        )
        selected_ids = set(identities.values())
        used = sorted({fact_id for identity in selected_ids for fact_id in chosen[identity]})
        reasons = {reason for identity in selected_ids for reason in calculation.unresolved_atoms.get(identity, ())}
        reasons.update(reason for identity in selected_ids for observation in calculation.observations.get(identity, ())
                       for reason in observation.reason_codes)
        result = EvaluationResult(
            truth=evaluate_control_condition(condition.expression, {
                atom_id: truths[parent_id][atom_id] for atom_id in identities}),
            reason_codes=sorted(reasons), used_fact_ids=used,
            evidence_span_ids=sorted({locator for fact_id in used for locator in facts[fact_id].locator_ids}),
        )
        scheme = next(item.atom.evaluation.repeat_scheme for item in all_identities if item.identity_sha256 == owner_id)
        written_permission = None
        if scheme.permission_condition_id == condition.condition_id:
            from app.services.repeat_permission_calculation import written_permission_result, written_permission_scoped_to_target
            entries = {item.atom_id: item for item in all_identities if item.identity_sha256 in selected_ids}
            atom_results = {key: EvaluationResult(
                truth=truths[parent_id][key], used_fact_ids=chosen[identity],
                evidence_span_ids=sorted({locator for fact_id in chosen[identity] for locator in facts[fact_id].locator_ids}),
            ) for key, identity in identities.items()}
            written = {key for key, identity in identities.items()
                       if entries[key].atom.requires_professional_judgment
                       and written_permission_scoped_to_target(row, identity)
                       and row.get("written_content_support", {}).get(identity)
                       and any(item.identity_sha256 == identity and item.status == "usable" for item in outcomes)}
            written_permission = written_permission_result(
                family="control", condition=condition, atom_results=atom_results, written_atom_ids=written)
        results.append(ControlRepeatTriggerCalculation(
            protocol_control_id=parent_id, condition_id=condition.condition_id,
            condition_sha256=canonical_hash(condition.model_dump(mode="json")),
            repeat_group_id=row["repeat_group_id"], scope_sha256=canonical_hash(row),
            owner_references=tuple((owner_id, role) for role, reference in (
                ("trigger", scheme.trigger_condition_id), ("permission", scheme.permission_condition_id)
            ) if reference == condition.condition_id),
            frozen_input_sha256=frozen.frozen_input_sha256,
            selection_sha256=selections.material.selection_sha256,
            selections_sha256=calculation.selections_sha256, result=result, written_permission=written_permission,
            target_kind=row["target_kind"],
            frequency_evaluations={key: value.model_dump(mode="json") for key, value in frequency.items()},
        ))
    return tuple(results)
