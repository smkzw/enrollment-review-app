"""Resolve result-use prerequisites from sealed, per-acquisition evidence.

This is not an eligibility evaluator: a permissible repeat is not a passing
eligibility result. The final calculation and publication keep their own guards.
"""
from dataclasses import asdict

from app.domain.contracts.enums import TruthValue
from app.domain.expression import EvaluationResult
from app.domain.publication import canonical_hash
from app.domain.repeat_acquisition_chains import decompose_repeat_chains
from app.domain.repeat_observation_count import evaluate_repeat_count
from app.domain.repeat_result_selection import select_repeat_result_groups
from app.services.qualified_binding_selection import (
    ReceiptVerifiedQualifiedBindingSelections,
    ReceiptVerifiedWorkDraftSelections,
)
from app.services.repeat_condition_selection import iter_scoped_repeat_conditions


def resolve_repeat_result_selection(selections, condition_calculations):
    """Join exact target scopes, not merely matching condition names or truths.

    Invalid repeats are retained as evidence. They are not silently discarded
    to make another result the last, single or favorable observation. Absence
    of a repeat does not imply an undocumented initial-result fallback.
    """
    if not isinstance(selections, (
        ReceiptVerifiedQualifiedBindingSelections, ReceiptVerifiedWorkDraftSelections,
    )):
        raise TypeError("复查结果须使用已经核实来源的资料")
    selections.require_unchanged()
    family = selections.candidate_family
    frozen = selections.predicate_frozen_input if family == "predicate" else selections.control_input
    from app.services.qualified_binding_selection import _expected_predicate_identities, _expected_control_identities

    expected = (_expected_predicate_identities(frozen) if family == "predicate"
                else _expected_control_identities(frozen))
    conditions = {}
    for parent, owner, condition, _, row, _ in iter_scoped_repeat_conditions(selections):
        key = owner, row["repeat_group_id"], condition.condition_id
        conditions[key] = (parent, condition, row)
    calculations = {}
    written_calculations = {}
    frequency_calculations = {}
    for raw in condition_calculations:
        if raw["family"] != family:
            continue
        if (raw["selection_sha256"] != selections.material.selection_sha256
                or (family == "control" and raw["frozen_input_sha256"] != frozen.frozen_input_sha256)):
            raise ValueError("复查条件计算与本次核实资料不同")
        for owner, role in raw["owner_references"]:
            key = owner, raw["repeat_group_id"], raw["condition_id"]
            source = conditions.get(key)
            if source is None or key in calculations:
                raise ValueError("复查条件计算有重复或不属于当前检查")
            parent, condition, row = source
            parent_field = "component_id" if family == "predicate" else "protocol_control_id"
            meta = expected[owner]
            scheme = meta["predicate"].repeat_scheme if family == "predicate" else meta.atom.evaluation.repeat_scheme
            reference = scheme.trigger_condition_id if role == "trigger" else scheme.permission_condition_id
            if (role not in {"trigger", "permission"} or reference != condition.condition_id
                    or raw[parent_field] != parent
                    or raw["condition_sha256"] != canonical_hash(condition.model_dump(mode="json"))
                    or raw.get("target_kind") != row["target_kind"]
                    or raw["scope_sha256"] != canonical_hash(row)):
                raise ValueError("复查条件的作用对象、用途或原文范围不一致")
            calculations[key] = EvaluationResult.model_validate(raw["result"])
            frequency = raw.get("frequency_evaluations", {})
            if frequency:
                from app.domain.contracts.evaluation_result import FrequencyAtomEvaluation
                identities = {item["identity_sha256"] for item in row["identity_outcomes"]}
                for identity, value in frequency.items():
                    parsed = FrequencyAtomEvaluation.model_validate(value)
                    if (identity not in identities or parsed.resolution.get("repeat_scope_sha256") != canonical_hash(row)):
                        raise ValueError("复查频次计算与逐次条件范围不同")
                frequency_calculations[key] = frequency
            if raw.get("written_permission") is not None:
                written = EvaluationResult.model_validate(raw["written_permission"])
                if (condition.condition_id != scheme.permission_condition_id
                        or not set(written.used_fact_ids) <= set(calculations[key].used_fact_ids)
                        or not set(written.evidence_span_ids) <= set(calculations[key].evidence_span_ids)):
                    raise ValueError("书面许可核实须来自同一许可条件的实际采用原文")
                written_calculations[key] = written.model_dump(mode="json")
    if set(calculations) != set(conditions):
        raise ValueError("尚未逐次计算本次复查的全部触发及许可条件")

    def fixed(truth, reason):
        return EvaluationResult(truth=truth, reason_codes=[reason]).model_dump(mode="json")

    results = []
    owners = set()
    for observation in selections.material.observation_relations:
        owner = observation["identity_sha256"]
        if owner in owners:
            raise ValueError("同一要求的复查来源不能重复采用")
        owners.add(owner)
        meta = expected[owner]
        if family == "predicate":
            scheme = meta["predicate"].repeat_scheme
            parent = meta["rule_component_id"]
        else:
            scheme = meta.atom.evaluation.repeat_scheme
            parent = meta.protocol_control_id
        graph, scope = observation["relationship_graph"], observation["supplied_scope"]
        constraints = observation["series_constraints"]
        scheme_hash, scope_hash = canonical_hash(scheme.model_dump(mode="json")), canonical_hash(scope)
        if (graph["graph_sha256"] != canonical_hash({key: value for key, value in graph.items()
                                                    if key != "graph_sha256"})
                or constraints["version"] not in {"repeat-series-constraints/v2", "repeat-series-constraints/v3"}
                or constraints["scheme_sha256"] != scheme_hash
                or constraints["graph_sha256"] != graph["graph_sha256"]
                or constraints["supplied_scope_sha256"] != scope_hash):
            raise ValueError("复查次数与期限计算不属于本次方案和原件")
        roles = graph["acquisition_roles"]
        initial_ids = [item["group_id"] for item in roles if item["role"] == "initial"]
        repeat_ids = tuple(sorted(item["group_id"] for item in roles if item["role"] == "repeat"))
        times = {item["repeat_group_id"]: item for item in constraints["time_checks"]}
        if (len(times) != len(constraints["time_checks"]) or set(times) != set(repeat_ids)
                or set(constraints["observed_repeat_group_ids"]) != set(repeat_ids)):
            raise ValueError("复查期限或次数未覆盖本次每一次检查")
        if constraints["version"] == "repeat-series-constraints/v3":
            chains = decompose_repeat_chains(graph)
            expected_counts = {}
            if (scheme.count_status == "specified" and scheme.count_scope == "per_initial_acquisition"
                    and not chains["reason_codes"]):
                for chain in chains["chains"]:
                    count = evaluate_repeat_count(
                        scheme, repeat_group_ids=tuple(chain["repeat_group_ids"]),
                        qualified_scope="per_initial_acquisition", scope_complete=scope["complete"],
                    )
                    expected_counts[chain["initial_group_id"]] = {
                        "repeat_group_ids": chain["repeat_group_ids"],
                        "result": count.result.model_dump(mode="json"), "scope_complete": count.scope_complete,
                    }
            if (constraints["acquisition_chains"] != chains or constraints["count_by_initial"] != expected_counts):
                raise ValueError("逐次初查的复查次数与原件对应关系不一致")

        def condition_result(target, reference, missing_reason):
            if reference is None:
                return fixed(TruthValue.UNKNOWN, missing_reason)
            return calculations[(owner, target, reference)].model_dump(mode="json")

        checks = []
        for target in repeat_ids:
            trigger = (fixed(TruthValue.TRUE, "repeat_trigger_unconditional") if scheme.trigger == "unconditional"
                       else condition_result(target, scheme.trigger_condition_id, "repeat_trigger_unverified"))
            if scheme.permission == "forbidden":
                permission = fixed(TruthValue.FALSE, "repeat_not_permitted")
            elif scheme.permission == "unresolved":
                permission = fixed(TruthValue.UNKNOWN, "repeat_permission_unverified")
            elif scheme.permission_condition_id is not None:
                permission = condition_result(target, scheme.permission_condition_id, "repeat_permission_unverified")
            elif scheme.permission == "investigator_discretion":
                permission = fixed(TruthValue.UNKNOWN, "professional_judgment_unverified")
            else:
                permission = fixed(TruthValue.TRUE, "repeat_permission_declared")
            count_result = constraints["count_result"]
            if scheme.count_scope == "per_initial_acquisition" and constraints["version"] == "repeat-series-constraints/v3":
                count_owners = [row for row in constraints["count_by_initial"].values() if target in row["repeat_group_ids"]]
                if len(count_owners) == 1:
                    count_result = count_owners[0]["result"]
            operands = {"trigger": trigger, "permission": permission,
                        "count": count_result, "time": times[target]["result"]}
            if scheme.permission == "investigator_discretion":
                # A decisive branch must actually contain verified investigator
                # content; generic permission-condition truth is insufficient.
                operands["written_permission"] = written_calculations.get(
                    (owner, target, scheme.permission_condition_id),
                    fixed(TruthValue.UNKNOWN, "repeat_written_permission_unverified"),
                )
            truths = {EvaluationResult.model_validate(item).truth for item in operands.values()}
            status = ("does_not_meet_requirements" if TruthValue.FALSE in truths else
                      "unverified" if TruthValue.UNKNOWN in truths else "requirements_met")
            checks.append({"repeat_group_id": target, "status": status, "checks": operands})

        selection = None
        multi_selection = None
        reasons = []
        absence_trigger = None
        if (not repeat_ids and len(initial_ids) == 1
                and scheme.no_repeat_result_use == "retain_initial_when_trigger_false"):
            absence_trigger = calculations.get((owner, initial_ids[0], scheme.trigger_condition_id))
        if len(initial_ids) > 1 and scheme.version == "repeat-scheme/v4":
            from app.services.repeat_multi_initial_selection import select_multi_initial_results
            multi_selection = select_multi_initial_results(
                scheme, graph, scope, checks,
                {key: calculations[(owner, key, scheme.trigger_condition_id)] for key in initial_ids
                 if (owner, key, scheme.trigger_condition_id) in calculations},
            )
            reasons.extend(multi_selection["reason_codes"])
        elif len(initial_ids) != 1:
            reasons.append("repeat_initial_scope_not_unique" if initial_ids else "repeat_initial_scope_unverified")
        else:
            selection = select_repeat_result_groups(
                scheme, graph, initial_group_id=initial_ids[0], repeat_group_ids=repeat_ids,
                scope_complete=scope["complete"], supplied_scope_sha256=scope_hash,
                initial_scope_complete=scope.get("initial_scope", {}).get("complete"),
                absence_trigger_truth=None if absence_trigger is None else absence_trigger.truth,
            )
            reasons.extend(selection.reason_codes)
        # retain_initial is not a fallback: it is an explicit source policy.
        # Its initial/source graph guard stays in force; repeat execution issues
        # remain in checks but are not themselves the initial measurement truth.
        if scheme.result_use != "retain_initial" and multi_selection is None:
            for item in checks:
                if item["status"] != "requirements_met":
                    reasons.append("repeat_execution_nonconforming" if item["status"] == "does_not_meet_requirements"
                                   else "repeat_execution_unverified")
                    reasons.extend(reason for value in item["checks"].values()
                                   if EvaluationResult.model_validate(value).truth != TruthValue.TRUE
                                   for reason in value["reason_codes"])
        chosen = [] if selection is None or reasons else list(selection.selected_group_ids)
        if multi_selection is not None and not reasons:
            chosen = sorted({key for chain in multi_selection["chains"] for key in chain["selected_group_ids"]})
        results.append({
            "version": "repeat-result-resolution/v1", "family": family, "parent_id": parent,
            "owner_identity_sha256": owner, "selection_sha256": selections.material.selection_sha256,
            "scheme_sha256": scheme_hash, "graph_sha256": graph["graph_sha256"],
            "supplied_scope_sha256": scope_hash, "scope": "supplied_facts_only",
            "source_observation_sha256": canonical_hash(observation),
            "condition_scope_sha256s": sorted(canonical_hash(row) for key, (_, _, row) in conditions.items()
                                              if key[0] == owner),
            "condition_frequency_evaluations": [{"repeat_group_id": key[1], "condition_id": key[2],
                                                  "evaluations": values}
                                                 for key, values in frequency_calculations.items() if key[0] == owner],
            "initial_group_ids": initial_ids, "repeat_checks": checks,
            "count_scope": {
                "kind": scheme.count_scope,
                "counted_repeat_group_ids": constraints["counted_repeat_group_ids"],
                "complete": constraints["count_scope_complete"],
                "episode_sha256": constraints["episode_sha256"],
                "acquisition_episode_memberships": constraints["acquisition_episode_memberships"],
                **({"count_by_initial": constraints["count_by_initial"],
                    "acquisition_chains": constraints["acquisition_chains"]}
                   if constraints["version"] == "repeat-series-constraints/v3" else {}),
            },
            "absence_trigger": None if absence_trigger is None else absence_trigger.model_dump(mode="json"),
            "policy_selection": None if selection is None else asdict(selection),
            **({"multi_initial_selection": multi_selection} if multi_selection is not None else {}),
            "selected_group_ids": chosen, "reason_codes": sorted(set(reasons)),
            "replacement_authorized": False,
        })
    return tuple(results)
