"""Project source-bound operand arithmetic, not accepted atom verdicts."""
from collections.abc import Iterable
from typing import Literal

from app.domain.contracts.common import ContractModel, DateValue
from app.domain.contracts.control_atom_binding import ControlBindingFrozenInput
from app.domain.contracts.enums import TruthValue
from app.domain.contracts.control_evaluation_spec import ControlTimePurpose, validate_control_atom_evaluation
from app.domain.expression import EvaluationResult, evaluate_observed_value, evaluate_time_constraint
from app.domain.publication import canonical_hash
from app.projections.control_atom_binding_input import project_control_atom_identities


class ControlOperandCalculation(ContractModel):
    frozen_input_sha256: str
    atom_identity_sha256: str
    fact_id: str
    locator_ids: list[str]
    anchors_sha256: str
    time_purpose: ControlTimePurpose | None = None
    accepted: Literal[False] = False
    value_result: EvaluationResult | None = None
    time_result: EvaluationResult | None = None
    unresolved_reason: str | None = None


def calculate_control_operand(
    frozen: ControlBindingFrozenInput, *, atom_identity_sha256: str,
    fact_id: str,
) -> ControlOperandCalculation:
    return calculate_control_operands(
        frozen, selections=[(atom_identity_sha256, fact_id)],
    )[(atom_identity_sha256, fact_id)]


def calculate_control_operands(
    frozen: ControlBindingFrozenInput, *, selections: Iterable[tuple[str, str]],
) -> dict[tuple[str, str], ControlOperandCalculation]:
    """Validate one immutable input once for all selected operand calculations."""
    frozen = ControlBindingFrozenInput.model_validate(frozen.model_dump(mode="json"))
    identities = {item.identity_sha256: item
                  for item in project_control_atom_identities(frozen.publication, include_repeat_triggers=True)}
    facts = {item.fact_id: item for item in frozen.evidence_input.facts}
    keys = list(dict.fromkeys(selections))
    if any(atom_id not in identities or fact_id not in facts for atom_id, fact_id in keys):
        raise ValueError("计算操作数不属于当前冻结的方案与事实")
    anchors = frozen.evidence_input.episode.anchor_dates
    anchors_sha256 = canonical_hash({key.value: value.model_dump(mode="json")
                                    for key, value in anchors.items()})
    return {
        (atom_id, fact_id): _calculate_operand(
            frozen, identity=identities[atom_id], fact=facts[fact_id],
            anchors_sha256=anchors_sha256,
        )
        for atom_id, fact_id in keys
    }


def _calculate_operand(frozen, *, identity, fact, anchors_sha256):
    """Calculate a selected candidate without certifying the selection.

    Keep time membership/validity separate from a clinical comparison: an old
    report does not prove failure of its clinical threshold. Anchors come only
    from the frozen episode. Their source verification, object correspondence
    and multiple-observation selection remain upstream.
    """
    anchors = frozen.evidence_input.episode.anchor_dates
    result = ControlOperandCalculation(
        frozen_input_sha256=frozen.frozen_input_sha256,
        atom_identity_sha256=identity.identity_sha256, fact_id=fact.fact_id,
        locator_ids=list(fact.locator_ids),
        anchors_sha256=anchors_sha256,
    )
    atom = identity.atom
    validate_control_atom_evaluation(atom)
    spec = atom.evaluation
    result.time_purpose = spec.time_purpose if spec is not None else None
    if spec is None or (spec.determination_mode != "deterministic"
                        and spec.version not in {"control-atom-evaluation/v2", "control-atom-evaluation/v3", "control-atom-evaluation/v4"}):
        return result.model_copy(update={"unresolved_reason": "尚无可执行的确定性规格"})
    predicate = spec.predicate
    if predicate is not None and any((
        predicate.occurrence_window, predicate.prospective_window, predicate.prospective_period,
    )):
        return result.model_copy(update={"unresolved_reason": "频次或未来期间仍需独立核实"})
    if spec.determination_mode == "deterministic" and getattr(atom, "prospective_period", None) is not None:
        return result.model_copy(update={"unresolved_reason": "未来期间仍需独立核实"})
    if predicate is not None:
        result.value_result = evaluate_observed_value(
            predicate, value=fact.value, unit=fact.unit, polarity=fact.polarity,
        )
    if atom.time_constraint is not None:
        if spec.time_purpose == "unresolved":
            result.time_result = EvaluationResult(truth=TruthValue.UNKNOWN, reason_codes=["time_purpose_unresolved"])
            return result
        attribute = spec.operand_attribute if spec.operation == "time_constraint" else spec.time_operand_attribute
        event = None
        if attribute == "date_range" and fact.date_range is not None:
            event = DateValue(value=fact.date_range.lower_bound, precision=fact.date_range.precision,
                              source_text=fact.date_range.source_text)
        elif attribute == "record_time":
            # Stored timestamps are UTC; they do not retain the source calendar date.
            result.time_result = EvaluationResult(
                truth=TruthValue.UNKNOWN,
                reason_codes=["source_calendar_date_unverified" if fact.record_time is not None
                              else "date_or_anchor_missing"],
            )
            return result
        result.time_result = evaluate_time_constraint(
            atom.time_constraint, event_value=event,
            anchor_value=anchors.get(atom.time_constraint.anchor_type),
        )
    elif spec.time_purpose == "unresolved":
        result.unresolved_reason = "时间要求尚未核实，不可忽略"
    return result
