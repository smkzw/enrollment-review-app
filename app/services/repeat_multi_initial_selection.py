"""Apply a source-declared result policy separately to explicit acquisition chains."""
from dataclasses import asdict

from app.domain.contracts.enums import TruthValue
from app.domain.publication import canonical_hash
from app.domain.repeat_acquisition_chains import decompose_repeat_chains
from app.domain.repeat_result_selection import select_repeat_result_groups


def select_multi_initial_results(scheme, graph, scope, checks, absence_triggers):
    policy = scheme.multi_initial_result
    result = {"version": "repeat-multi-initial-selection/v1", "operation": None,
              "chains": [], "reason_codes": []}
    if policy is None or policy.mode == "unresolved":
        result["reason_codes"] = ["repeat_multi_initial_policy_unverified"]
        return result
    result["operation"] = "all" if policy.mode == "per_initial_then_all" else "any"
    chains = decompose_repeat_chains(graph)
    if chains["reason_codes"] or not scope["complete"]:
        result["reason_codes"] = chains["reason_codes"] or ["repeat_result_scope_incomplete"]
        return result
    # Full supplied-scope qualification includes all source origins and links.
    # It does not claim that every historical record has been provided.
    check_by_group = {row["repeat_group_id"]: row for row in checks}
    for chain in chains["chains"]:
        initial, repeats = chain["initial_group_id"], chain["repeat_group_ids"]
        absence = absence_triggers.get(initial)
        selected = select_repeat_result_groups(
            scheme, graph, initial_group_id=initial, repeat_group_ids=tuple(repeats),
            scope_complete=True, supplied_scope_sha256=canonical_hash(scope), initial_scope_complete=True,
            absence_trigger_truth=None if absence is None else absence.truth,
        )
        reasons = list(selected.reason_codes)
        if scheme.result_use != "retain_initial":
            for repeat in repeats:
                check = check_by_group[repeat]
                if check["status"] != "requirements_met":
                    reasons.append("repeat_execution_nonconforming" if check["status"] == "does_not_meet_requirements"
                                   else "repeat_execution_unverified")
                    reasons.extend(reason for value in check["checks"].values()
                                   if value["truth"] != TruthValue.TRUE.value for reason in value["reason_codes"])
        result["chains"].append({**chain, "policy_selection": asdict(selected),
                                 "selected_group_ids": [] if reasons else list(selected.selected_group_ids),
                                 "reason_codes": sorted(set(reasons)),
                                 "absence_trigger": None if absence is None else absence.model_dump(mode="json")})
    return result
