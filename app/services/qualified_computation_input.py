"""Qualify supplied calculation inputs, without adoption or a second fact store."""
from app.domain.contracts.computation_input import ComputationSourceDescription
from app.domain.expression import _canonical_unit
from app.domain.observation_relation_graph import analyze_computation_acquisitions
from app.domain.publication import canonical_hash
from app.services.binding_qualification_support import SEMANTIC_DIMENSIONS
from app.services.ordered_observation_selection import observation_scope_reasons

VERSION = "qualified-computation-input/v2"


def _reused_fact_bindings(partition, numeric, descriptions):
    """Semantic deduplication is not acquisition deduplication.

    A reused semantic fact needs an explicit, quoted acquisition handle at
    every appearance, equal within each group and different across its groups.
    Existing graph checks still require a proven distinct relationship.
    """
    by_fact = {}
    for index, keys in enumerate(partition["groups"]):
        for key in keys:
            if key in numeric:
                by_fact.setdefault(numeric[key].fact_id, {}).setdefault(index, []).append(key)
    bindings, reasons = [], []
    for fact_id, appearances in sorted(by_fact.items()):
        if len(appearances) < 2:
            continue
        handles = []
        for index, keys in sorted(appearances.items()):
            values = [descriptions.get(key) for key in keys]
            known = { (item.token_kind, item.collection_token) for item in values
                     if item is not None and item.token_kind != "unresolved"}
            if len(known) != 1 or any(item is None or item.token_kind == "unresolved" for item in values):
                reasons.append("computation_acquisition_identity_unverified")
                continue
            kind, token = next(iter(known))
            handles.append((kind, token))
            bindings.append({"fact_id": fact_id, "acquisition_index": index,
                             "pair_ids": sorted(keys), "token_kind": kind, "collection_token": token})
        if len(handles) != len(appearances) or len({token for _, token in handles}) != len(handles):
            reasons.append("computation_acquisition_identity_unverified")
    return bindings, reasons


def _contradictory_group_handles(partition, numeric, descriptions):
    """A stated distinct edge cannot override the same quoted collection handle.

    Missing or different handles do not prove independence; the source graph
    remains required. Kind labels alone cannot make one token two collections.
    """
    seen = set()
    for keys in partition["groups"]:
        tokens = {descriptions[key].collection_token for key in keys
                  if key in numeric and key in descriptions
                  and descriptions[key].token_kind != "unresolved"}
        if seen & tokens:
            return ["computation_acquisition_identity_unverified"]
        seen.update(tokens)
    return []


def _source_reasons(record, member, unit):
    reasons = []
    if (record is None or record.pair_id != member.pair_id
            or record.fact_id != member.fact_id or record.locator_id != member.locator_id
            or record.identity_sha256 != member.identity_sha256
            or not record.structurally_valid or not record.structural.body_matches_frozen
            or record.structural.operand_shape != "source_computation_input"):
        return ["computation_source_unqualified"]
    if record.structural.source_policy_status != "present":
        reasons.append("computation_source_policy_unverified")
    judgments = [item for item in record.lane_judgments.values() if item is not None]
    if (len(judgments) != 2 or not record.dual_agreement
            or judgments[0].public_agreement_key() != judgments[1].public_agreement_key()
            or set(record.semantic_dimensions_rechecked) != set(SEMANTIC_DIMENSIONS)):
        reasons.append("computation_source_correspondence_unverified")
    elif any(item.source_admissibility != "admissible" or item.object_match != "supported"
             or item.denial_scope != "compatible" or item.temporal_role != "not_applicable"
             or item.attribute_match not in {"direct", "derivation_operand"}
             for item in judgments):
        reasons.append("computation_source_correspondence_unverified")
    # Derivation operands intentionally cannot be used as the final attribute.
    # Their free-text notes remain in the original receipts, never parsed to grant authority.
    if any(item.attribute_match == "direct" and (
            item.direct_operand_usable != "usable" or item.unresolved_reasons) for item in judgments):
        reasons.append("computation_source_correspondence_unverified")
    if any(item.attribute_match == "derivation_operand" and item.direct_operand_usable != "not_usable"
           for item in judgments):
        reasons.append("computation_source_correspondence_unverified")
    allowed = {"clinical_adoption_not_authorized", "evaluation_activation_absent",
               "semantic_correspondence_unverified", "temporal_applicability_unverified",
               "source_computation_input_set_unverified", "unit_equivalence_unverified"}
    reasons.extend(item for item in record.remaining_unverified if item not in allowed)
    reasons.extend(item for item in record.structural.pending_checks if item not in allowed)
    if _canonical_unit(unit) != _canonical_unit(record.structural.referenced_unit):
        reasons.append("computation_unit_unverified")
    if record.structural.referenced_value != member.fact.get("value"):
        reasons.append("computation_value_changed")
    return reasons


def qualify_computation_inputs(evidence, records, *, frozen_facts, accounting):
    """Only explicit complete-count all/single policies in the supplied scope.

    Sorting, windows, missing-value handling, ratio and count are capability
    gaps until their actual consumers are implemented. Dual descriptions alone
    are never an input-set proof.
    """
    records = {item.pair_id: item for item in records}
    facts = {item.fact_id: item for item in frozen_facts}
    groups = {item.pair_id: item for item in evidence["pairs"]}
    output = []
    for comparison in evidence["summary"]["comparisons"]:
        group = groups[comparison["group_id"]]
        members = {item.pair_id: item for item in group.members}
        numeric = {key: item for key, item in members.items() if item.fact_attribute == "value"}
        descriptions = {item.pair_id: item for item in
                        map(ComputationSourceDescription.model_validate, comparison["agreed_source_descriptions"])}
        computation = group.computation
        reasons = []
        selection = computation.input_selection
        if (selection is None or selection.mode not in {"all", "single"}
                or selection.window_refs or computation.declared_input_count is None
                or computation.declared_input_count.value < 1):
            reasons.append("computation_selection_policy_unsupported")
        if computation.missing_policy != "not_specified" or computation.max_missing_count is not None:
            reasons.append("computation_missing_policy_unsupported")
        if computation.operator not in {"mean", "sum", "minimum", "maximum"}:
            reasons.append("computation_operator_unsupported")
        if computation.quantity_basis is not None:
            reasons.append("computation_period_quantity_unsupported")
        condition = group.members[0].condition
        atom = condition.get("atom") or condition
        predicate = condition.get("predicate") or ((atom.get("evaluation") or {}).get("predicate")) or {}
        if (atom.get("time_constraint") is not None or atom.get("requires_professional_judgment")
                or predicate.get("requires_professional_judgment")
                or any(predicate.get(key) is not None for key in (
                    "repeat_scheme", "semantic_proposition", "applicable_population", "occurrence_window",
                    "prospective_window", "prospective_period"))
                or (atom.get("evaluation") or {}).get("determination_mode", "deterministic") != "deterministic"):
            reasons.append("computation_scope_policy_unsupported")
        policy = predicate.get("observation_policy")
        spec = atom.get("evaluation")
        if ((policy and (policy.get("mode") == "unresolved" or policy.get("selection") is not None))
                or (spec and (spec.get("operation") != "value_comparison"
                              or spec.get("operand_attribute") != "value"
                              or spec.get("repeat_scheme") is not None
                              or (spec.get("observation_policy") or {}).get("mode") == "unresolved"
                              or (spec.get("observation_policy") or {}).get("selection") is not None))):
            reasons.append("computation_scope_policy_unsupported")
        if (comparison["disputed_relationships"] or any(
                lane["unresolved_notes"] for lane in comparison["lanes"].values())):
            reasons.append("computation_source_scope_unresolved")
        for key, member in numeric.items():
            description = descriptions.get(key)
            if description is None or description.input_role != "raw_input":
                reasons.append("computation_input_membership_unverified")
            reasons.extend(_source_reasons(records.get(key), member, predicate.get("unit")))
        fact_ids = sorted({item.fact_id for item in numeric.values()})
        rows = [row for item in accounting if item[group.members[0].identity_field] == group.identity_sha256
                for row in item["fact_accounting"]]
        reasons.extend(observation_scope_reasons(facts=facts, operand_fact_ids=fact_ids, accounting=rows))
        for fact_id in fact_ids:
            fact = facts.get(fact_id)
            locators = {item.locator_id for item in numeric.values() if item.fact_id == fact_id}
            if fact is None or locators != set(fact.locator_ids):
                reasons.append("computation_source_appearances_incomplete")
        partition = analyze_computation_acquisitions(group.members, comparison["agreed_relationships"])
        if partition["unproven_distinct_groups"]:
            reasons.append("computation_acquisition_identity_unverified")
        reasons.extend(_contradictory_group_handles(partition, numeric, descriptions))
        acquisition_facts = [sorted({numeric[key].fact_id for key in keys if key in numeric})
                             for keys in partition["groups"]]
        reused_bindings, reused_reasons = _reused_fact_bindings(partition, numeric, descriptions)
        reasons.extend(reused_reasons)
        proven_reused = {item["fact_id"] for item in reused_bindings} if not reused_reasons else set()
        owners = {}
        for index, items in enumerate(acquisition_facts):
            for key in items:
                fact = facts.get(key)
                if fact is None:
                    continue
                # Publication unions read provenance, not acquisition IDs.
                # Complete source appearances and explicit graph relations
                # qualify collections; reference count cannot replace them.
                for kind, refs in (("observation", fact.source_observation_refs), ("candidate", fact.source_candidate_ids)):
                    for ref in refs:
                        origin = kind, ref
                        if origin in owners and owners[origin] != (index, key) and not (
                                owners[origin][1] == key and key in proven_reused):
                            reasons.append("computation_acquisition_identity_unverified")
                        owners[origin] = index, key
        if (computation.declared_input_count is not None
                and len(acquisition_facts) != computation.declared_input_count.value):
            reasons.append("computation_required_inputs_incomplete")
        material = {"version": VERSION, "identity_sha256": group.identity_sha256,
            "source_computation": computation.model_dump(mode="json"), "source_group_id": group.pair_id,
            "source_summary_sha256": evidence["summary_sha256"],
            "source_summary_artifact_sha256": evidence["summary_artifact_sha256"],
            "source_input_sha256": evidence["payload"]["input_sha256"],
            "pair_ids": sorted(numeric), "fact_ids": fact_ids,
            "acquisition_fact_ids": acquisition_facts, "acquisition_partition": partition,
            "reused_fact_source_bindings": reused_bindings,
            "scope": "supplied_facts_only", "reason_codes": sorted(set(reasons)),
            "derivation_operand_notes": {
                key: {lane: list(judgment.unresolved_reasons)
                      for lane, judgment in sorted(records[key].lane_judgments.items())
                      if judgment is not None and judgment.attribute_match == "derivation_operand"}
                for key in sorted(numeric) if key in records and any(
                    item is not None and item.attribute_match == "derivation_operand"
                    for item in records[key].lane_judgments.values())},
            "input_set_qualified": not reasons,
            "authorized_clinical_adoption": False}
        output.append({**material, "qualification_sha256": canonical_hash(material)})
    return output
