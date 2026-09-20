"""Select auxiliary evidence per repeat before applying observation policy."""
from copy import deepcopy

from app.domain.contracts.qualified_binding_selection import QualifiedBindingIdentityOutcome
from app.domain.publication import canonical_hash
from app.services.ordered_observation_selection import observation_scope_reasons
from app.services.semantic_observation_selection import select_semantic_ordered_observation


def _reference_group(graph, target, role, target_kind="repeat"):
    if graph["structural_reasons"]:
        return None, list(graph["structural_reasons"])
    roles = {item["group_id"]: item["role"] for item in graph["acquisition_roles"]}
    if target_kind == "initial_without_repeat":
        if roles.get(target) == "initial" and role == "initial_observation":
            return target, []
        return None, ["repeat_condition_reference_unverified"]
    if roles.get(target) != "repeat":
        return None, ["repeat_origin_unverified"]
    if role == "target_observation":
        return target, []
    if role == "preceding_observation":
        candidates = {edge["prior_group_id"] for edge in graph["repeat_edges"]
                      if edge["repeat_group_id"] == target
                      and edge.get("reference_kind") == "preceding_observation"}
    else:
        predecessors = {}
        for edge in graph["repeat_edges"]:
            predecessors.setdefault(edge["repeat_group_id"], set()).add(edge["prior_group_id"])
        pending, visited = list(predecessors.get(target, ())), set()
        while pending:
            current = pending.pop()
            if current not in visited:
                visited.add(current)
                pending.extend(predecessors.get(current, ()))
        candidates = {key for key in visited if roles.get(key) == "initial"}
    if len(candidates) != 1:
        return None, ["repeat_condition_reference_unverified"]
    return next(iter(candidates)), []


def _evidence_scope(observation, target, role, identity, facts, accounting, records, target_kind="repeat"):
    """Exclude only sources positively assigned to a different acquisition."""
    audit = {"role": "unresolved" if role is None else role.role,
             "reference_group_id": None, "accounting_sha256": canonical_hash(accounting),
             "considered_fact_ids": sorted(facts), "outside_reference_fact_ids": [],
             "acquisition_scope_check": "unverified"}
    if role is None or role.role == "unresolved":
        return set(), ["repeat_condition_evidence_role_unverified"], audit
    if role.role == "external_context":
        audit["acquisition_scope_check"] = "not_applicable_external_context"
        return set(facts), [], audit
    reference, reasons = _reference_group(observation["relationship_graph"], target, role.role, target_kind)
    audit["reference_group_id"] = reference
    if reasons:
        return set(), reasons, audit
    if not observation["supplied_scope"]["complete"]:
        return set(), ["repeat_correspondence_sources_unverified"], audit
    rows = {item["fact_id"]: item for item in accounting}
    if len(rows) != len(accounting) or set(rows) != set(facts):
        return set(), ["candidate_enumeration_incomplete"], audit
    candidates = {key for key, row in rows.items() if row["status"] == "candidates_in_both_lanes"}
    if any(row["status"] not in {"candidates_in_both_lanes", "agreed_noncorrespondence"}
           for row in rows.values()):
        return set(), ["observation_scope_unverified"], audit
    source_pairs = {item.pair_id for item in records}
    disputed = {key[0] for key in observation["disputed_auxiliary_associations"]}
    if source_pairs & disputed or any(observation["auxiliary_unresolved_notes"].values()):
        return set(), ["repeat_condition_correspondence_unverified"], audit
    assignments = {}
    shared = {}
    for item in observation["qualified_auxiliary_associations"]:
        if item["identity_sha256"] == identity:
            assignments.setdefault(item["fact_id"], set()).add(item["acquisition_group_id"])
            shared.setdefault(item["fact_id"], []).append(item.get("shared_scope_verified") is True)
    if any(not assignments.get(key) or (len(assignments[key]) > 1
               and not all(shared[key])) for key in candidates):
        return set(), ["repeat_condition_correspondence_unverified"], audit
    selected = {key for key in candidates if reference in assignments[key]}
    audit["shared_scope_fact_ids"] = sorted(key for key in selected if len(assignments[key]) > 1)
    audit["outside_reference_fact_ids"] = sorted(candidates - selected)
    audit["acquisition_scope_check"] = "verified" if selected else "source_not_found"
    return selected, ([] if selected else ["repeat_condition_source_not_found"]), audit


def _select_atom(*, family, identity, meta, facts, rows, records, usable, relations,
                 review_context, anchor_dates, supported_pair_ids):
    from app.services.qualified_binding_selection import _select_facts_for_identity
    from app.services.ordered_observation_selection import select_ordered_observation

    predicate = meta["predicate"] if family == "predicate" else None
    spec = None if predicate is not None else meta.atom.evaluation
    policy = predicate.observation_policy if predicate is not None else (spec.observation_policy if spec else None)
    constraint = meta["time_constraint"] if predicate is not None else meta.atom.time_constraint
    semantic = (predicate.semantic_proposition is not None if predicate is not None
                else spec is not None and spec.determination_mode != "deterministic")
    purpose = "event_membership" if predicate is not None else (spec.time_purpose if spec else None)
    value_records = [item for item in usable if item.fact_attribute == "value"]
    written_verified = bool(value_records) and all(item.pair_id in supported_pair_ids for item in value_records)
    professional = predicate.requires_professional_judgment if predicate is not None else meta.atom.requires_professional_judgment
    if professional and not written_verified:
        return [], [], ["investigator_judgment_not_deterministic_value"], None, []
    frequency = predicate.occurrence_window if predicate is not None else (spec.predicate.occurrence_window
                if spec is not None and spec.predicate is not None else None)
    if frequency is not None and not semantic and not professional:
        ids = sorted({item.fact_id for item in usable})
        reasons = list(observation_scope_reasons(facts=facts, operand_fact_ids=ids, accounting=rows))
        return ids, sorted({item.pair_id for item in usable}), reasons, None, []
    if semantic:
        usable_ids = {item.pair_id for item in usable}
        relations = [deepcopy(item) for item in relations if item["pair_id"] in usable_ids]
        source_ids = {item.pair_id for item in records if item.fact_attribute in {"value", "assertion_basis"}}
        complete = source_ids == {item["pair_id"] for item in relations}
        for item in relations:
            item["scope_candidates_complete"] = complete
        if policy is not None and policy.selection is not None:
            selected = select_semantic_ordered_observation(
                policy=policy, facts=facts, relations=relations, usable_records=usable,
                source_records=records, accounting=rows, time_constraint=constraint,
                anchor_dates=anchor_dates, time_purpose=purpose, review_context=review_context,
            )
            return (list(selected.fact_ids), list(selected.pair_ids), list(selected.reasons),
                    selected.ordering, list(selected.selected_relations))
        ids = sorted({item["fact_id"] for item in relations})
        pairs = sorted({item["pair_id"] for item in relations})
        reasons = list(observation_scope_reasons(facts=facts, operand_fact_ids=ids, accounting=rows))
        if not complete or not relations:
            reasons.append("semantic_evidence_unverified")
        if policy is None or policy.mode == "unresolved":
            reasons.append("observation_selection_unverified")
        if constraint is not None:
            date_attribute = "date_range" if predicate is not None else spec.time_operand_attribute
            dates = [item for item in usable if item.fact_attribute == date_attribute]
            if date_attribute != "date_range" or not set(ids) <= {item.fact_id for item in dates}:
                reasons.append("declared_time_operand_not_qualified")
            pairs = sorted(set(pairs) | {item.pair_id for item in dates if item.fact_id in ids})
        return ids, pairs, reasons, None, relations
    operand = "value" if predicate is not None else (spec.operand_attribute if spec else None)
    ids = sorted({item.fact_id for item in usable if item.fact_attribute == operand})
    reasons = list(observation_scope_reasons(facts=facts, operand_fact_ids=ids, accounting=rows))
    if reasons:
        return [], [], reasons, None, []
    if policy is not None and policy.selection is not None:
        selection = select_ordered_observation(
            policy=policy, facts=facts, operand_fact_ids=ids,
            date_fact_ids=[item.fact_id for item in usable if item.fact_attribute == "date_range"],
            accounting=rows, time_constraint=constraint, anchor_dates=anchor_dates, time_purpose=purpose,
            conflicting_fact_ids=[key for group in review_context.conflict_groups for key in group.fact_ids]
            if review_context is not None else (),
        )
        audit = {"policy_sha256": canonical_hash(policy.model_dump(mode="json")),
                 "accounting_sha256": canonical_hash(rows), "selected_fact_ids": list(selection.fact_ids),
                 "not_selected": [{"fact_id": key, "reason": reason} for key, reason in selection.excluded]}
        pairs = sorted({item.pair_id for item in usable if item.fact_id in selection.fact_ids
                        and item.fact_attribute in {operand, "date_range"}})
        return list(selection.fact_ids), pairs, list(selection.reasons), audit, []
    ids, pairs, reasons = _select_facts_for_identity(
        family=family, identity=identity, usable_records=usable, expected_meta=meta,
        written_content_verified=written_verified,
    )
    return ids, pairs, reasons, None, []


def _condition_targets(scheme, graph):
    repeats = sorted(item["group_id"] for item in graph["acquisition_roles"] if item["role"] == "repeat")
    targets = [(key, "repeat", scheme.ancillary_condition_ids) for key in repeats]
    initials = [item["group_id"] for item in graph["acquisition_roles"] if item["role"] == "initial"]
    if scheme.no_repeat_result_use == "retain_initial_when_trigger_false":
        if not repeats and len(initials) == 1:
            targets.append((initials[0], "initial_without_repeat", (scheme.trigger_condition_id,)))
        elif scheme.multi_initial_result is not None and scheme.multi_initial_result.mode != "unresolved":
            from app.domain.repeat_acquisition_chains import decompose_repeat_chains
            chains = decompose_repeat_chains(graph)
            if not chains["reason_codes"]:
                targets.extend((chain["initial_group_id"], "initial_without_repeat", (scheme.trigger_condition_id,))
                               for chain in chains["chains"] if not chain["repeat_group_ids"])
    return targets


def build_repeat_condition_selections(*, frozen, family, observation_relations, records, by_identity, identity_records,
                                      accounting, proposition_relations, proposition_pair_gaps,
                                      supported_pair_ids, review_context):
    """Called inside the receipt-verified factory before global selection discards sources."""
    from app.services.qualified_binding_selection import _expected_predicate_identities, _expected_control_identities
    source = frozen if family == "predicate" else frozen.evidence_input
    expected = (_expected_predicate_identities(frozen) if family == "predicate"
                else _expected_control_identities(frozen))
    facts = {item.fact_id: item for item in source.facts}
    identity_field = "predicate_identity_sha256" if family == "predicate" else "atom_identity_sha256"
    for observation in observation_relations:
        owner = expected[observation["identity_sha256"]]
        if family == "predicate":
            parent_id = owner["rule_component_id"]
            parent = next(item for item in frozen.components if item.rule_component_id == parent_id)
            scheme = owner["predicate"].repeat_scheme
            identities = {item.predicate_id: item.predicate_identity_sha256 for item in parent.repeat_trigger_predicates}
        else:
            parent_id = owner.protocol_control_id
            parent = next(item for item in frozen.publication.catalog.controls if item.protocol_control_id == parent_id)
            scheme = owner.atom.evaluation.repeat_scheme
            identities = {item.atom_id: key for key, item in expected.items()
                          if item.protocol_control_id == parent_id and item.layer == "repeat_trigger"}
        graph = observation["relationship_graph"]
        if graph["graph_sha256"] != canonical_hash({key: value for key, value in graph.items() if key != "graph_sha256"}):
            raise ValueError("复查关系内容已变化，不能限定条件的取证范围")
        owner_id = observation["identity_sha256"]
        usable_pairs = {item.pair_id for item in by_identity.get(owner_id, ())}
        observation["result_sources"] = {
            "version": "repeat-result-sources/v1", "owner_identity_sha256": owner_id,
            "qualified_pairs": [
                {"pair_id": item.pair_id, "fact_id": item.fact_id,
                 "fact_attribute": item.fact_attribute,
                 "written_content_verified": item.pair_id in supported_pair_ids}
                for item in by_identity.get(owner_id, ())
            ],
            "source_content_pairs": [
                {"pair_id": item.pair_id, "fact_id": item.fact_id}
                for item in records if item.identity_sha256 == owner_id
                and item.fact_attribute in {"value", "assertion_basis"}
            ],
            "proposition_relations": [deepcopy(item) for item in proposition_relations
                                      if item["identity_sha256"] == owner_id and item["pair_id"] in usable_pairs],
            "proposition_pair_gaps": [deepcopy(item) for item in proposition_pair_gaps
                                      if item["identity_sha256"] == owner_id],
        }
        selected_conditions = []
        for target, target_kind, condition_ids in _condition_targets(scheme, graph):
            for condition in parent.repeat_trigger_conditions:
                if condition.condition_id not in condition_ids:
                    continue
                if family == "predicate":
                    from app.domain.contracts.predicate_binding import iter_binding_atoms
                    atom_ids = {item.predicate.predicate_id for item in iter_binding_atoms(condition.expression)}
                else:
                    atom_ids = {item.condition_atom_id for group in condition.expression.groups for item in group.atoms}
                outcomes, scopes, selected_relations, selected_gaps = [], [], [], []
                for atom_id in sorted(atom_ids):
                    identity = identities[atom_id]
                    role = condition.predicate_evidence_roles.get(atom_id)
                    if (role is not None and role.role == "target_observation"
                            and condition.condition_id != scheme.permission_condition_id):
                        role = None
                    local_records = [item for item in records if item.identity_sha256 == identity]
                    rows = [row for item in accounting if item[identity_field] == identity for row in item["fact_accounting"]]
                    allowed, reasons, scope = _evidence_scope(
                        observation, target, role, identity,
                        facts, rows, local_records, target_kind,
                    )
                    scope.update(identity_sha256=identity, atom_id=atom_id)
                    scopes.append(scope)
                    recorded = identity_records.get(identity, ())
                    if not recorded:
                        reasons.append("identity_absent_from_qualification")
                    elif all(item.status == "no_candidates_in_supplied_input" for item in recorded):
                        reasons.append("no_candidate_pairs_in_completed_job")
                    ids, pair_ids, ordering, relations = [], [], None, []
                    gaps = [item for item in proposition_pair_gaps if item["identity_sha256"] == identity
                            and item["fact_id"] in allowed]
                    if not reasons:
                        ids, pair_ids, reasons, ordering, relations = _select_atom(
                            family=family, identity=identity, meta=expected[identity],
                            facts={key: value for key, value in facts.items() if key in allowed},
                            rows=[item for item in rows if item["fact_id"] in allowed],
                            records=[item for item in local_records if item.fact_id in allowed],
                            usable=[item for item in by_identity.get(identity, ()) if item.fact_id in allowed],
                            relations=[item for item in proposition_relations if item["identity_sha256"] == identity
                                       and item["fact_id"] in allowed],
                            review_context=review_context, anchor_dates=source.episode.anchor_dates,
                            supported_pair_ids=supported_pair_ids,
                        )
                    if reasons:
                        ids, pair_ids, ordering, relations = [], [], None, []
                    outcome = QualifiedBindingIdentityOutcome(
                        identity_field=identity_field, identity_sha256=identity,
                        status="unresolved" if reasons else "usable", fact_ids=ids, usable_pair_ids=pair_ids,
                        unresolved_reasons=sorted(set(reasons)), observation_ordering=ordering,
                    )
                    outcomes.append(outcome.model_dump(mode="json"))
                    selected_relations.extend(relations)
                    selected_gaps.extend(gaps)
                selected_conditions.append({
                    "version": "repeat-condition-selection/v3", "parent_id": parent_id,
                    "target_kind": target_kind,
                    "owner_identity_sha256": observation["identity_sha256"], "repeat_group_id": target,
                    "condition_id": condition.condition_id,
                    "condition_sha256": canonical_hash(condition.model_dump(mode="json")),
                    "graph_sha256": graph["graph_sha256"], "evidence_scopes": scopes,
                    "identity_outcomes": outcomes, "proposition_relations": selected_relations,
                    "unresolved_proposition_pairs": selected_gaps,
                    "written_content_support": {
                        outcome["identity_sha256"]: sorted(set(outcome["usable_pair_ids"]) & set(supported_pair_ids))
                        for outcome in outcomes
                    },
                })
        observation["condition_selections"] = selected_conditions


def iter_scoped_repeat_conditions(selections):
    """Verify sealed target/owner/condition identities before using scoped outcomes."""
    selections.require_unchanged()
    family = selections.candidate_family
    frozen = selections.predicate_frozen_input if family == "predicate" else selections.control_input
    from app.services.qualified_binding_selection import _expected_predicate_identities, _expected_control_identities
    expected = (_expected_predicate_identities(frozen) if family == "predicate"
                else _expected_control_identities(frozen))
    for observation in selections.material.observation_relations:
        owner_id = observation["identity_sha256"]
        owner = expected[owner_id]
        if family == "predicate":
            parent_id = owner["rule_component_id"]
            parent = next(item for item in frozen.components if item.rule_component_id == parent_id)
            scheme = owner["predicate"].repeat_scheme
        else:
            parent_id = owner.protocol_control_id
            parent = next(item for item in frozen.publication.catalog.controls if item.protocol_control_id == parent_id)
            scheme = owner.atom.evaluation.repeat_scheme
        conditions = {item.condition_id: item for item in parent.repeat_trigger_conditions
                      if item.condition_id in scheme.ancillary_condition_ids}
        graph = observation["relationship_graph"]
        targets = {(target, key): kind for target, kind, ids in _condition_targets(scheme, graph) for key in ids}
        rows = observation.get("condition_selections")
        if rows is None:
            raise ValueError("原核对尚未区分每次复查的条件资料，须按当前方法重新准备")
        keys = [(row["repeat_group_id"], row["condition_id"]) for row in rows]
        if len(keys) != len(set(keys)) or set(keys) != set(targets):
            raise ValueError("每次复查的条件资料未完整对应方案")
        for row in rows:
            condition = conditions[row["condition_id"]]
            if (row["version"] not in {"repeat-condition-selection/v2", "repeat-condition-selection/v3"} or row["owner_identity_sha256"] != owner_id
                    or row.get("target_kind") != targets[(row["repeat_group_id"], row["condition_id"])]
                    or row["parent_id"] != parent_id or row["graph_sha256"] != graph["graph_sha256"]
                    or row["condition_sha256"] != canonical_hash(condition.model_dump(mode="json"))):
                raise ValueError("复查条件选择与原方案、对应检查或来源版本不一致")
            if family == "predicate":
                from app.domain.contracts.predicate_binding import iter_binding_atoms
                atom_ids = {item.predicate.predicate_id for item in iter_binding_atoms(condition.expression)}
                identities = {item.predicate_id: item.predicate_identity_sha256 for item in parent.repeat_trigger_predicates
                              if item.predicate_id in atom_ids}
            else:
                atom_ids = {item.condition_atom_id for group in condition.expression.groups for item in group.atoms}
                identities = {item.atom_id: key for key, item in expected.items()
                              if item.protocol_control_id == parent_id and item.layer == "repeat_trigger"
                              and item.atom_id in atom_ids}
            outcomes = [QualifiedBindingIdentityOutcome.model_validate(raw) for raw in row["identity_outcomes"]]
            if len(outcomes) != len(identities) or {item.identity_sha256 for item in outcomes} != set(identities.values()):
                raise ValueError("复查条件的逐项资料清单不完整")
            yield parent_id, owner_id, condition, identities, row, outcomes
