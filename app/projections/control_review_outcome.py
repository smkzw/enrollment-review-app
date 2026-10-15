"""Describe frozen control obligations without inventing an eligibility verdict."""
from app.domain.contracts.control_review_outcome import ControlObligationOutcome, ControlReviewOutcome
from app.domain.contracts.control_atom_binding import ControlBindingFrozenInput
from app.domain.contracts.enums import TruthValue
from app.domain.publication import canonical_hash
from app.projections.control_atom_binding_input import project_control_atom_identities
from app.projections.control_calculation_experiment import ControlCalculationExperiment


def project_control_review_outcomes(
    frozen: ControlBindingFrozenInput,
    calculation: ControlCalculationExperiment,
    *, observation_ordering=None,
) -> tuple[ControlReviewOutcome, ...]:
    """Preserve each group, modality and unknown prerequisite separately.

    This is a calculation projection, not evidence qualification or permission
    to publish. In particular, no OR/AND eligibility verdict is inferred from
    obligation groups, and prohibition kinds never invert the source predicate.
    """
    if calculation.frozen_input_sha256 != frozen.frozen_input_sha256:
        raise ValueError("补充要求结果与本次冻结资料不一致")
    layers = {item.protocol_control_id: item for item in calculation.layers}
    controls = frozen.publication.catalog.controls
    if len(layers) != len(calculation.layers) or set(layers) != {
        item.protocol_control_id for item in controls
    }:
        raise ValueError("补充要求结果有重复或遗漏")
    identities = project_control_atom_identities(frozen.publication)
    ordering = observation_ordering or {}
    if not set(ordering) <= {item.identity_sha256 for item in identities}:
        raise ValueError("检查选择依据不属于本次补充要求")
    identity_by_control = {}
    for identity in identities:
        identity_by_control.setdefault(identity.protocol_control_id, {})[identity.atom_id] = identity.identity_sha256
    result = []
    for control in controls:
        layer = layers[control.protocol_control_id]
        if layer.control_sha256 != canonical_hash(control.model_dump(mode="json")):
            raise ValueError("补充要求原文已变化，不能沿用计算结果")
        atom_ids = identity_by_control[control.protocol_control_id]
        if set(layer.atom_truths) != set(atom_ids):
            raise ValueError("补充要求未保留完整逐项结果")
        unresolved = {
            identity: list(calculation.unresolved_atoms.get(identity, ["observation_unverified"]))
            for atom_id, identity in atom_ids.items()
            if layer.atom_truths[atom_id] == TruthValue.UNKNOWN
        }
        obligations = []
        for group in control.obligation_expression.groups:
            activation = layer.obligation_group_activation[group.obligation_group_id]
            for atom in group.atoms:
                truth = layer.atom_truths[atom.obligation_id]
                if activation == TruthValue.FALSE:
                    status = "not_applicable"
                elif activation == TruthValue.UNKNOWN or truth == TruthValue.UNKNOWN:
                    status = "unverified"
                else:
                    status = "fulfilled" if truth == TruthValue.TRUE else "unfulfilled"
                # Preserve unresolved prerequisites at control level rather than
                # misattribute an unrelated sibling to this obligation.
                unknown = {atom_ids[atom.obligation_id]} & set(unresolved)
                operands = [item for item in calculation.calculations
                            if item.atom_identity_sha256 == atom_ids[atom.obligation_id]]
                observations = calculation.observations.get(atom_ids[atom.obligation_id], ())
                evidence_gaps = [item for item in calculation.proposition_pair_gaps
                                 if item.identity_sha256 == atom_ids[atom.obligation_id]]
                obligations.append(ControlObligationOutcome(
                    obligation_id=atom.obligation_id,
                    obligation_group_id=group.obligation_group_id,
                    identity_sha256=atom_ids[atom.obligation_id],
                    statement=atom.statement,
                    proposition=atom.evaluation.proposition if atom.evaluation else None,
                    kind=atom.kind, modality=atom.modality,
                    activation_route=("exception_replacement" if group.activated_by_exception_group_ids
                                      else "default_remaining"),
                    trigger_branch_ids=sorted(group.applies_to_trigger_branch_ids or layer.trigger_branches),
                    exception_group_ids=sorted(group.activated_by_exception_group_ids),
                    activation=activation, observation_truth=truth, status=status,
                    unresolved_atom_identities=sorted(unknown),
                    reason_codes=(["activation_unverified"]
                                  if activation == TruthValue.UNKNOWN else []),
                    used_fact_ids=sorted({item.fact_id for item in operands}),
                    locator_ids=sorted({locator for item in operands for locator in item.locator_ids}),
                    unverified_evidence=evidence_gaps,
                    observation_reason_codes=sorted({reason for item in observations for reason in item.reason_codes}
                        | set(unresolved.get(atom_ids[atom.obligation_id], ()))),
                    protocol_span_ids=list(atom.source_span_ids),
                    protocol_excerpts=list(atom.source_excerpts),
                ))
        result.append(ControlReviewOutcome(
            protocol_control_id=control.protocol_control_id,
            control_sha256=layer.control_sha256,
            frozen_input_sha256=frozen.frozen_input_sha256,
            selections_sha256=calculation.selections_sha256,
            obligations=obligations, unresolved_atoms=unresolved,
            observation_ordering={identity: audit for identity, audit in ordering.items()
                                  if identity in atom_ids.values()},
            repeat_evaluations={identity: value for identity, value in calculation.repeat_evaluations.items()
                                if identity in atom_ids.values()},
            frequency_evaluations={identity: value for identity, value in calculation.frequency_evaluations.items()
                                   if identity in atom_ids.values()},
        ))
    return tuple(result)
