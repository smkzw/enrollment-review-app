"""Control-layer composition only; caller must verify each atom's evidence.

Not a clinical acceptance entry point. Missing proofs remain unknown, and this
module does not convert evidence coverage or recommendations into exclusion.
"""
from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from app.domain.contracts.common import ContractModel
from app.domain.contracts.enums import TruthValue
from app.domain.contracts.control_evidence_dependency import validate_control_evidence_dependencies
from app.domain.contracts.control_time_binding import validate_control_time_bindings
from app.domain.contracts.protocol_controls import (
    ControlObligationKind, ControlObligationModality, ProtocolReviewControl,
)
from app.domain.publication import canonical_hash


class ObligationAtomResult(ContractModel):
    kind: ControlObligationKind
    modality: ControlObligationModality
    truth: TruthValue


class ControlEvidenceUse(ContractModel):
    layer: Literal["applicability", "trigger", "obligation", "exception", "repeat_trigger"]
    atom_id: str
    truth: TruthValue
    obligation_group_id: str | None = None
    obligation_activation: TruthValue | None = None
    modality: ControlObligationModality | None = None


class ControlLayerEvaluation(ContractModel):
    protocol_control_id: str
    control_sha256: str
    applicability: TruthValue
    trigger_branches: dict[str, TruthValue] = Field(default_factory=dict)
    exception_groups: dict[str, TruthValue] = Field(default_factory=dict)
    remaining_trigger_branches: dict[str, TruthValue] = Field(default_factory=dict)
    obligation_group_activation: dict[str, TruthValue] = Field(default_factory=dict)
    # Descriptive conjunction only; never an eligibility/blocking result.
    obligation_group_truth: dict[str, TruthValue] = Field(default_factory=dict)
    obligation_atoms: dict[str, ObligationAtomResult] = Field(default_factory=dict)
    atom_truths: dict[str, TruthValue] = Field(default_factory=dict)
    evidence_uses: dict[str, list[ControlEvidenceUse]] = Field(default_factory=dict)


def _all(values) -> TruthValue:
    values = tuple(values)
    if TruthValue.FALSE in values:
        return TruthValue.FALSE
    return TruthValue.UNKNOWN if TruthValue.UNKNOWN in values else TruthValue.TRUE


def _any(values) -> TruthValue:
    values = tuple(values)
    if TruthValue.TRUE in values:
        return TruthValue.TRUE
    return TruthValue.UNKNOWN if TruthValue.UNKNOWN in values else TruthValue.FALSE


def _not(value: TruthValue) -> TruthValue:
    return {TruthValue.TRUE: TruthValue.FALSE, TruthValue.FALSE: TruthValue.TRUE,
            TruthValue.UNKNOWN: TruthValue.UNKNOWN}[value]


def evaluate_control_condition(expression, atom_truths: Mapping[str, TruthValue]) -> TruthValue:
    """Evaluate a complete auxiliary DNF without activating control layers."""
    expected = [atom.condition_atom_id for group in expression.groups for atom in group.atoms]
    if (not expected or len(expected) != len(set(expected)) or set(atom_truths) != set(expected)
            or any(not isinstance(value, TruthValue) for value in atom_truths.values())):
        raise ValueError("独立复查条件须逐项保留完整的三值结果")
    return _any(_all(atom_truths[atom.condition_atom_id] for atom in group.atoms)
                for group in expression.groups)


def compose_control_layers(
    control: ProtocolReviewControl, *, control_sha256: str,
    atom_truths: Mapping[str, TruthValue],
) -> ControlLayerEvaluation:
    """Compose explicit source branches; do not infer truth from fact categories."""
    control = ProtocolReviewControl.model_validate(control.model_dump(mode="json"))
    if canonical_hash(control.model_dump(mode="json")) != control_sha256:
        raise ValueError("补充控制内容已变化，不能沿用原子求值")
    if control.obligation_expression is None:
        raise ValueError("补充控制未保留完整条件结构")
    validate_control_time_bindings(control, require_explicit=True)
    expected = []
    for layer in ("applicability", "trigger", "obligation", "exception"):
        expression = getattr(control, f"{layer}_expression")
        if expression is not None:
            expected.extend(
                atom.obligation_id if layer == "obligation" else atom.condition_atom_id
                for group in expression.groups for atom in group.atoms
            )
    if len(expected) != len(set(expected)) or set(atom_truths) != set(expected):
        raise ValueError("控制原子求值必须完整且身份唯一，未核实项须明确为未知")
    if any(not isinstance(value, TruthValue) for value in atom_truths.values()):
        raise ValueError("控制原子求值只能使用明确的三值结果")
    validate_control_evidence_dependencies(control, require_explicit=False)

    def condition(group):
        return _all(atom_truths[atom.condition_atom_id] for atom in group.atoms)

    applicability = (
        _any(condition(group) for group in control.applicability_expression.groups)
        if control.applicability_expression is not None else TruthValue.TRUE
    )
    triggers = {}
    if control.trigger_expression is not None:
        for group in control.trigger_expression.groups:
            if not group.trigger_branch_id or group.trigger_branch_id in triggers:
                raise ValueError("触发分支必须保留唯一的正式身份")
            triggers[group.trigger_branch_id] = condition(group)
    exceptions = {}
    exception_groups = control.exception_expression.groups if control.exception_expression else ()
    for group in exception_groups:
        if not group.exception_group_id or group.exception_group_id in exceptions:
            raise ValueError("例外分支必须保留唯一的正式身份")
        if not set(group.waives_trigger_branch_ids).issubset(triggers):
            raise ValueError("例外引用了不存在的触发分支")
        exceptions[group.exception_group_id] = condition(group)
    remaining = {
        key: _all((truth, _not(_any(
            exceptions[group.exception_group_id] for group in exception_groups
            if key in group.waives_trigger_branch_ids
        ))))
        for key, truth in triggers.items()
    }
    exception_by_id = {group.exception_group_id: group for group in exception_groups}
    obligation_by_id = {
        group.obligation_group_id: group for group in control.obligation_expression.groups
    }
    for exception_id, exception in exception_by_id.items():
        for obligation_id in exception.activates_obligation_group_ids:
            target = obligation_by_id.get(obligation_id)
            if target is None or exception_id not in target.activated_by_exception_group_ids:
                raise ValueError("例外与替代义务的双向关系不一致")
    activation, obligations = {}, {}
    for group in control.obligation_expression.groups:
        key = group.obligation_group_id
        if not key or key in activation:
            raise ValueError("义务分支必须保留唯一的正式身份")
        if not set(group.applies_to_trigger_branch_ids).issubset(triggers):
            raise ValueError("义务引用了不存在的触发分支")
        if not set(group.activated_by_exception_group_ids).issubset(exceptions):
            raise ValueError("替代义务引用了不存在的例外分支")
        if group.activated_by_exception_group_ids:
            # Replacement consequences depend on original triggers, not waived ones.
            branch_truths = triggers
            routes = []
            for exception_id in group.activated_by_exception_group_ids:
                exception = exception_by_id[exception_id]
                if key not in exception.activates_obligation_group_ids:
                    raise ValueError("例外与替代义务的双向关系不一致")
                affected = set(exception.waives_trigger_branch_ids)
                if group.applies_to_trigger_branch_ids:
                    affected &= set(group.applies_to_trigger_branch_ids)
                    if not affected:
                        raise ValueError("替代义务与例外豁免的触发分支不相交")
                affected_truth = _any(triggers[item] for item in affected) if triggers else TruthValue.TRUE
                routes.append(_all((exceptions[exception_id], affected_truth)))
            route = _any(routes)
        else:
            branch_truths = remaining
            # With no explicit trigger, the exception concerns the implicit
            # unconditional route. Unknown still suspends, never waives it.
            route = (_not(_any(exceptions.values())) if not triggers else TruthValue.TRUE)
        selected = group.applies_to_trigger_branch_ids or tuple(branch_truths)
        trigger_truth = _any(branch_truths[item] for item in selected) if triggers else TruthValue.TRUE
        activation[key] = _all((applicability, trigger_truth, route))
        obligations[key] = _all(atom_truths[atom.obligation_id] for atom in group.atoms)
    evidence_uses = {}
    for evidence in control.minimum_evidence:
        uses = []
        for ref in evidence.atom_refs:
            if ref.layer == "repeat_trigger":
                condition = next(item for item in control.repeat_trigger_conditions
                                 if item.condition_id == ref.condition_id)
                atom = condition.expression.groups[ref.group_index].atoms[ref.atom_index]
                # Auxiliary evidence is not a fifth eligibility layer or resolved by coverage.
                uses.append(ControlEvidenceUse(layer=ref.layer, atom_id=atom.condition_atom_id,
                                               truth=TruthValue.UNKNOWN))
                continue
            group = getattr(control, f"{ref.layer}_expression").groups[ref.group_index]
            atom = group.atoms[ref.atom_index]
            obligation = ref.layer == "obligation"
            atom_id = atom.obligation_id if obligation else atom.condition_atom_id
            uses.append(ControlEvidenceUse(
                layer=ref.layer, atom_id=atom_id, truth=atom_truths[atom_id],
                obligation_group_id=group.obligation_group_id if obligation else None,
                obligation_activation=activation[group.obligation_group_id] if obligation else None,
                modality=atom.modality if obligation else None,
            ))
        # Empty historical dependencies mean unknown, not an unused requirement.
        # Never merge a resolved prerequisite or inactive sibling over other uses.
        evidence_uses[evidence.evidence_key] = uses
    return ControlLayerEvaluation(
        protocol_control_id=control.protocol_control_id, control_sha256=control_sha256,
        applicability=applicability, trigger_branches=triggers, exception_groups=exceptions,
        remaining_trigger_branches=remaining, obligation_group_activation=activation,
        obligation_group_truth=obligations, atom_truths=dict(atom_truths),
        evidence_uses=evidence_uses,
        obligation_atoms={
            atom.obligation_id: ObligationAtomResult(
                kind=atom.kind, modality=atom.modality, truth=atom_truths[atom.obligation_id],
            )
            for group in control.obligation_expression.groups for atom in group.atoms
        },
    )
