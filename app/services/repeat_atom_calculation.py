"""Calculate repeat-owning atoms from verified sources, without changing rules."""
from copy import deepcopy

from app.domain.contracts.enums import LogicalOperator, TruthValue
from app.domain.contracts.rules import AtomicExpression
from app.domain.expression import (
    EvaluationResult, RepeatAtomEvaluation, _evaluate_atomic, _evaluate_logical,
    evaluate_calculated_numeric_value,
)
from app.domain.proposition_observations import scope_supported
from app.domain.publication import canonical_hash
from app.domain.repeat_numeric_result import calculate_repeat_numeric_result
from app.domain.repeat_result_selection import RepeatResultSelection
from app.services.qualified_binding_selection import ReceiptVerifiedQualifiedBindingSelections


def calculate_repeat_atoms(selections, context, resolutions):
    """Only the formal receipt-rebuilding caller may use this for publication.

    Results keep original atom/context identities. A temporary arithmetic view
    omits the already-resolved repeat policy, never any threshold or time rule;
    that view is not saved as a protocol revision or as a clinical fact.
    """
    if not isinstance(selections, ReceiptVerifiedQualifiedBindingSelections):
        raise TypeError("复查求值须使用本次来源核实结果")
    selections.require_unchanged()
    family = selections.candidate_family
    frozen = selections.predicate_frozen_input if family == "predicate" else selections.control_input
    source = frozen if family == "predicate" else frozen.evidence_input
    authority = source.authority
    if ((context.project_id, context.subject_id, context.review_episode_id, context.evidence_snapshot_id)
            != (authority.project_id, authority.subject_id, authority.review_episode_id, authority.evidence_snapshot_v2_id)
            or context.anchor_dates != source.episode.anchor_dates
            or set(context.accepted_fact_ids) != {item.fact_id for item in source.facts}):
        raise ValueError("复查求值与当前节点及原件范围不一致")
    from app.services.eligibility_review_projection import _phase3_date_value
    originals = {item.fact_id: item for item in source.facts}
    for fact in context.facts:
        original = originals[fact.fact_id]
        if (any(getattr(fact, name) != getattr(original, name) for name in ("fact_type", "value", "unit", "polarity"))
                or fact.effective_date != _phase3_date_value(original.date_range)
                or fact.evidence_span_ids != original.locator_ids):
            raise ValueError("复查求值的原始数值、日期或原文定位已变化")
    if family == "predicate":
        entries = {item.predicate_identity_sha256: item for component in frozen.components
                   for item in (*component.trigger_predicates, *component.exception_predicates)}
    else:
        from app.projections.control_atom_binding_input import project_control_atom_identities
        entries = {item.identity_sha256: item for item in project_control_atom_identities(frozen.publication)}
    observations = {item["identity_sha256"]: item for item in selections.material.observation_relations}
    facts = {item.fact_id: item for item in context.facts}
    result = {}
    for resolution in resolutions:
        if resolution["family"] != family:
            continue
        owner = resolution["owner_identity_sha256"]
        if owner not in observations or owner not in entries or owner in result:
            raise ValueError("复查结果不能用于其他条件或重复应用")
        observation, entry = observations[owner], entries[owner]
        if (resolution["selection_sha256"] != selections.material.selection_sha256
                or resolution["source_observation_sha256"] != canonical_hash(observation)):
            raise ValueError("复查结果采用依据与已核实的来源不同")
        sources = observation.get("result_sources")
        if sources is None or sources["version"] != "repeat-result-sources/v1" or sources["owner_identity_sha256"] != owner:
            raise ValueError("原核对未保留逐次结果原文，须按当前方法准备")
        graph = observation["relationship_graph"]
        group_facts = {item["group_id"]: item["fact_ids"] for item in graph["acquisition_groups"]}
        source_ids = sorted({key for ids in group_facts.values() for key in ids})
        if not set(source_ids) <= set(facts):
            raise ValueError("复查结果包含本次范围外的原文")
        pairs = sources["qualified_pairs"]
        qualified = {(item["fact_id"], item["fact_attribute"]) for item in pairs}
        pair_ids = {item["pair_id"] for item in pairs}
        if len(pair_ids) != len(pairs):
            raise ValueError("复查结果的来源配对重复")
        relations = sources["proposition_relations"]
        seen = set()
        for record in relations:
            if (record["pair_id"] not in pair_ids or record["pair_id"] in seen
                    or record["identity_sha256"] != owner or record["scope"] != "pair_local"
                    or record["status"] not in {"entails_agreed", "contradicts_agreed"}
                    or set(record["lanes"]) != {"main-A", "main-B"}):
                raise ValueError("复查原文含义与本次已核实配对不同")
            seen.add(record["pair_id"])
        if family == "predicate":
            predicate, spec = entry.predicate, None
            atom = AtomicExpression(predicate=predicate, time_constraint=entry.time_constraint)
            scheme, policy = predicate.repeat_scheme, predicate.observation_policy
            semantic = predicate.semantic_proposition is not None
            professional = predicate.requires_professional_judgment
            operand, date_attribute = "value", "date_range" if entry.time_constraint is not None else None
            atom_hash = canonical_hash(atom.model_dump(mode="json"))
            arithmetic_atom = atom.model_copy(update={"predicate": predicate.model_copy(update={"repeat_scheme": None})})
            control_operands = {}
        else:
            atom, spec = entry.atom, entry.atom.evaluation
            predicate, scheme, policy = spec.predicate, spec.repeat_scheme, spec.observation_policy
            semantic = spec.determination_mode != "deterministic"
            professional = atom.requires_professional_judgment
            operand = "value" if semantic else spec.operand_attribute
            date_attribute = spec.time_operand_attribute
            atom_hash = canonical_hash(atom.model_dump(mode="json"))
            from app.projections.control_operand_calculation import calculate_control_operands
            control_operands = calculate_control_operands(frozen, selections=[(owner, key) for key in source_ids])

        from app.services.repeat_observation_ordering import reconcile_repeat_ordering
        ordering_reasons, ordering_audit = reconcile_repeat_ordering(
            policy=policy, observation=observation, resolution=resolution, facts=originals,
            qualified=qualified, operand=operand, semantic=semantic,
            time_constraint=entry.time_constraint if family == "predicate" else atom.time_constraint,
            anchor_dates=source.episode.anchor_dates,
            time_purpose="event_membership" if family == "predicate" else spec.time_purpose,
            conflicting_fact_ids=frozenset(key for key, fact in facts.items() if fact.conflict_group_id),
        )

        def unknown(*reasons):
            return EvaluationResult(truth=TruthValue.UNKNOWN, reason_codes=sorted(set(reasons)))

        def fact_result(fact_id):
            fact = facts[fact_id]
            if (not any((fact_id, attribute) in qualified for attribute in ("value", "assertion_basis"))
                    if semantic else (fact_id, operand) not in qualified):
                return unknown("repeat_result_value_unverified")
            if date_attribute is not None and (fact_id, date_attribute) not in qualified:
                return unknown("declared_time_operand_not_qualified")
            if fact.conflict_group_id:
                return unknown("source_conflict")
            if professional:
                written = [item for item in pairs if item["fact_id"] == fact_id and item["fact_attribute"] == "value"]
                if not written or not all(item["written_content_verified"] for item in written):
                    return unknown("professional_judgment_unverified")
            if policy is None or policy.mode == "unresolved":
                return unknown("repeat_observation_policy_unverified")
            if semantic:
                local = [item for item in relations if item["fact_id"] == fact_id]
                expected_pairs = {item["pair_id"] for item in sources["source_content_pairs"] if item["fact_id"] == fact_id}
                if (not expected_pairs or expected_pairs != {item["pair_id"] for item in local}
                        or not scope_supported(local)):
                    return unknown("semantic_evidence_unverified")
                if family == "predicate":
                    from app.services.predicate_proposition_calculation import calculate_predicate_proposition_fact
                    calculated = calculate_predicate_proposition_fact(entry, fact, local, context)
                    value = EvaluationResult(truth=calculated.truth, reason_codes=calculated.reason_codes)
                else:
                    from app.projections.control_calculation_experiment import _proposition_observation
                    truth, reasons = _proposition_observation(atom, local, control_operands[(owner, fact_id)])
                    value = EvaluationResult(truth=truth, reason_codes=reasons)
            elif family == "predicate":
                value = _evaluate_atomic(arithmetic_atom, context, [fact_id])
            else:
                from app.projections.control_calculation_experiment import _conditional_observation
                truth, reasons = _conditional_observation(atom, control_operands[(owner, fact_id)])
                value = EvaluationResult(
                    truth=truth, reason_codes=reasons,
                    observed_value=fact.value if spec.operation == "value_comparison" else None,
                    observed_unit=fact.unit if spec.operation == "value_comparison" else None,
                )
            value.used_fact_ids = [fact_id]
            value.evidence_span_ids = list(fact.evidence_span_ids)
            return value

        group_results = {}
        for group_id, ids in group_facts.items():
            values = [fact_result(key) for key in ids]
            if not values:
                group_results[group_id] = unknown("repeat_result_missing")
                continue
            compared = {canonical_hash([facts[key].value, facts[key].unit, facts[key].polarity]) for key in ids}
            dates = {canonical_hash(None if facts[key].effective_date is None else
                                    facts[key].effective_date.model_dump(mode="json", exclude={"source_text"})) for key in ids}
            if (date_attribute == "date_range" or operand == "date_range") and len(dates) != 1:
                group_results[group_id] = unknown("repeat_same_acquisition_date_conflict")
            elif not semantic and operand == "value" and len(compared) != 1:
                group_results[group_id] = unknown("repeat_same_acquisition_value_conflict")
            elif {TruthValue.TRUE, TruthValue.FALSE} <= {item.truth for item in values}:
                group_results[group_id] = unknown("repeat_same_acquisition_value_conflict")
            elif TruthValue.UNKNOWN in {item.truth for item in values}:
                group_results[group_id] = unknown(*(reason for item in values for reason in item.reason_codes))
            else:
                group_results[group_id] = _evaluate_logical(LogicalOperator.ALL, values)
                if not semantic and len(compared) == 1:
                    group_results[group_id].observed_value = values[0].observed_value
                    group_results[group_id].observed_unit = values[0].observed_unit
        def calculate_selected(chosen, raw):
            numeric = None
            if not chosen:
                return unknown("repeat_result_missing"), None
            values = [group_results[key] for key in chosen]
            operation = raw["combination"]
            if operation in {"all", "any"}:
                calculated = _evaluate_logical(LogicalOperator.ALL if operation == "all" else LogicalOperator.ANY, values)
            elif operation is None and len(values) == 1:
                calculated = values[0].model_copy(deep=True)
            elif operation in {"sum", "mean", "minimum", "maximum"} and not semantic and predicate is not None:
                failures = [value for value in values if value.truth == TruthValue.UNKNOWN]
                if failures:
                    calculated = unknown(*(reason for value in failures for reason in value.reason_codes))
                else:
                    selection = RepeatResultSelection(**{key: (tuple(value) if key in {
                        "considered_group_ids", "selected_group_ids", "reason_codes"} else value)
                        for key, value in raw.items() if key not in {"scope", "replacement_authorized"}})
                    numeric = calculate_repeat_numeric_result(
                        selection, graph, context, scheme=scheme,
                        qualified_value_fact_ids=frozenset(key for key, attribute in qualified if attribute == "value"),
                        unit_required=predicate.unit is not None,
                    )
                    calculated = (unknown(*numeric.reason_codes) if numeric.value is None else
                                  evaluate_calculated_numeric_value(predicate, value=numeric.value, unit=numeric.unit))
                    calculated.used_fact_ids = list(numeric.fact_ids)
                    calculated.evidence_span_ids = sorted({span for key in numeric.fact_ids for span in facts[key].evidence_span_ids})
            else:
                calculated = unknown("repeat_result_combination_unverified")
            return calculated, numeric

        chosen = resolution["selected_group_ids"]
        numeric = None
        chain_results = []
        multi = resolution.get("multi_initial_selection")
        if resolution["reason_codes"] or ordering_reasons:
            calculated = unknown(*(resolution["reason_codes"] + list(ordering_reasons)))
        elif multi is not None:
            if policy is None or policy.mode != multi["operation"]:
                calculated = unknown("repeat_multi_initial_policy_disagreement")
            else:
                for chain in multi["chains"]:
                    chain_result, chain_numeric = ((unknown(*chain["reason_codes"]), None) if chain["reason_codes"] else
                        calculate_selected(chain["selected_group_ids"], chain["policy_selection"]))
                    chain_results.append({"initial_group_id": chain["initial_group_id"],
                                          "result": chain_result.model_dump(mode="json"),
                                          "numeric_result": None if chain_numeric is None else chain_numeric.as_material()})
                calculated = (_evaluate_logical(
                    LogicalOperator.ALL if multi["operation"] == "all" else LogicalOperator.ANY,
                    [EvaluationResult.model_validate(row["result"]) for row in chain_results],
                ) if chain_results else unknown("repeat_result_missing"))
        elif not chosen:
            calculated = unknown("repeat_result_missing")
        else:
            calculated, numeric = calculate_selected(chosen, resolution["policy_selection"])
        audit = deepcopy(resolution)
        if multi is not None:
            audit["multi_initial_results"] = chain_results
        if ordering_audit is not None:
            audit["observation_ordering"] = ordering_audit
        audit["acquisition_results"] = [{"group_id": key, "fact_ids": group_facts[key],
                                         "result": value.model_dump(mode="json")}
                                        for key, value in group_results.items()]
        result[owner] = RepeatAtomEvaluation(
            context_sha256=canonical_hash(context.model_dump(mode="json")) if family == "predicate" else frozen.frozen_input_sha256,
            atom_sha256=atom_hash, resolution_sha256=canonical_hash(audit), source_fact_ids=source_ids,
            result=calculated, resolution=audit, numeric_result=None if numeric is None else numeric.as_material(),
        )
    if set(result) != set(observations):
        raise ValueError("本次复查结果尚未逐项计算完整")
    return result
