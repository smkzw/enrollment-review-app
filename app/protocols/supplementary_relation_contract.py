"""Shared supplementary-relation contract for wire hydration and publication gates."""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.contracts.enums import ReviewStage
from app.domain.contracts.protocol_controls import (
    ControlObligationKind,
    KnownRequiredProcedureTarget,
    KnownWorkflowStageTarget,
)

FUTURE_ANCHOR_TYPES = frozenset(
    {
        "baseline_date",
        "randomization_date",
        "first_dose_date",
        "study_drug_administration_date",
    }
)

SUBSEQUENT_CONTROL_OBLIGATION_KINDS = frozenset(
    {
        ControlObligationKind.VERIFY_RESULT_VALIDITY.value,
        ControlObligationKind.SELECT_BASELINE_VALUE.value,
    }
)


def _enum_value(value: object) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _iter_obligation_atoms(obligation_expression: object | None) -> list[object]:
    if obligation_expression is None:
        return []
    atoms: list[object] = []
    for group in getattr(obligation_expression, "groups", ()) or ():
        atoms.extend(getattr(group, "atoms", ()) or ())
    return atoms


def _workflow_stage_order(
    workflow_targets: Sequence[KnownWorkflowStageTarget],
) -> dict[str, int]:
    return {
        item.workflow_stage_id: index for index, item in enumerate(workflow_targets)
    }


def procedure_execution_workflow_stage_id(
    procedure: KnownRequiredProcedureTarget,
    workflow_targets: Sequence[KnownWorkflowStageTarget],
) -> str | None:
    review_stage = _enum_value(getattr(procedure, "review_stage", None))
    visit_instance = getattr(procedure, "visit_instance", None)
    for item in workflow_targets:
        if (
            _enum_value(getattr(item, "review_stage", None)) == review_stage
            and getattr(item, "visit_instance", None) == visit_instance
        ):
            return item.workflow_stage_id
    return None


def _atom_is_subsequent_control(atom: object) -> bool:
    kind = _enum_value(getattr(atom, "kind", None))
    if kind not in SUBSEQUENT_CONTROL_OBLIGATION_KINDS:
        return False
    if kind == ControlObligationKind.SELECT_BASELINE_VALUE.value:
        return True
    anchor = _enum_value(
        getattr(getattr(atom, "time_constraint", None), "anchor_type", None)
    )
    return anchor in FUTURE_ANCHOR_TYPES


def is_cross_stage_subsequent_control_supplement(
    *,
    obligation_expression: object | None,
    procedure: KnownRequiredProcedureTarget,
    affected_workflow_stage_id: str | None,
    workflow_targets: Sequence[KnownWorkflowStageTarget],
) -> bool:
    """Return True when supplement may decide at a later stage than execution."""

    execution_stage_id = procedure_execution_workflow_stage_id(
        procedure, workflow_targets
    )
    if not execution_stage_id or not affected_workflow_stage_id:
        return False
    if execution_stage_id == affected_workflow_stage_id:
        return False

    order = _workflow_stage_order(workflow_targets)
    execution_index = order.get(execution_stage_id)
    affected_index = order.get(affected_workflow_stage_id)
    if execution_index is None or affected_index is None:
        return False
    if affected_index <= execution_index:
        return False

    baseline_indexes = [
        order[item.workflow_stage_id]
        for item in workflow_targets
        if _enum_value(getattr(item, "review_stage", None))
        == ReviewStage.BASELINE.value
    ]
    if baseline_indexes and affected_index < min(baseline_indexes):
        return False

    subsequent_atoms = [
        atom
        for atom in _iter_obligation_atoms(obligation_expression)
        if _atom_is_subsequent_control(atom)
    ]
    return bool(subsequent_atoms)
