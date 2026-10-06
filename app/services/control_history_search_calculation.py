"""Apply sealed work-draft source search without changing fact qualification."""
from app.domain.contracts.enums import TruthValue
from app.domain.control_layer_evaluation import compose_control_layers
from app.domain.publication import canonical_hash
from app.projections.control_atom_binding_input import project_control_atom_identities
from app.projections.control_calculation_experiment import ControlCalculationExperiment
from app.services.history_source_search_calculation import calculate_history_not_seen


def apply_control_history_search(calculated, frozen, rows, *, blocked_identities=()):
    if not rows:
        return calculated
    raw = calculated.model_dump(mode="json")
    identities = project_control_atom_identities(frozen.publication)
    by_identity = {item.identity_sha256: item for item in identities}
    from app.services.history_source_search_input import history_search_targets
    eligible = {row["identity_sha256"] for row in history_search_targets(frozen, "control")}
    atoms = {control.protocol_control_id: {
        item.atom_id: layer.atom_truths[item.atom_id]
        for item in identities if item.protocol_control_id == control.protocol_control_id
        for layer in calculated.layers if layer.protocol_control_id == control.protocol_control_id}
        for control in frozen.publication.catalog.controls}
    consumed = []
    for row in rows:
        key = row["identity_sha256"]
        item = by_identity.get(key)
        if (item is None or key not in eligible or key in blocked_identities or item.atom.evaluation is None
                or item.atom.evaluation.determination_mode != "semantic"
                or calculated.observations.get(key) or item.atom.requires_professional_judgment):
            continue
        result = calculate_history_not_seen(row, item.atom.evaluation.record_semantics,
            time_constraint=item.atom.time_constraint, anchor_dates=frozen.evidence_input.episode.anchor_dates)
        if result is None or result.truth == TruthValue.UNKNOWN:
            continue
        atoms[item.protocol_control_id][item.atom_id] = result.truth
        raw["unresolved_atoms"].pop(key, None)
        consumed.append(row)
    if not consumed:
        return calculated
    raw["layers"] = [compose_control_layers(control,
        control_sha256=canonical_hash(control.model_dump(mode="json")),
        atom_truths=atoms[control.protocol_control_id]).model_dump(mode="json")
        for control in frozen.publication.catalog.controls]
    raw.update(version="control-calculation-experiment/v20", history_search_results=consumed,
               selections_sha256=canonical_hash({"base": calculated.selections_sha256,
                   "history_source_search": consumed}))
    return ControlCalculationExperiment.model_validate(raw)
