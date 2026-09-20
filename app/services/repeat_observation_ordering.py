"""Require source-declared ordering and repeat selection to agree."""
from dataclasses import asdict

from app.domain.publication import canonical_hash
from app.services.ordered_observation_selection import select_qualified_observation_dates


def reconcile_repeat_ordering(*, policy, observation, resolution, facts, qualified,
                             operand, semantic, time_constraint, anchor_dates, time_purpose,
                             conflicting_fact_ids):
    if policy is None or policy.selection is None:
        return (), None
    audit = {"policy_sha256": canonical_hash(policy.model_dump(mode="json")),
             "criterion": policy.selection.criterion, "agrees_with_repeat_selection": None,
             "representative_fact_ids": {}, "ordering": None,
             "selected_group_ids": list(resolution["selected_group_ids"])}
    if not observation["supplied_scope"]["complete"]:
        return ("repeat_result_scope_incomplete",), audit
    if (resolution.get("multi_initial_selection") is not None or resolution["policy_selection"] is None
            or len(resolution["selected_group_ids"]) != 1 or resolution["policy_selection"]["combination"] is not None):
        return ("repeat_ordering_combination_unverified",), audit
    representatives = {}
    for group in observation["relationship_graph"]["acquisition_groups"]:
        ids = group["fact_ids"]
        if not ids or not set(ids) <= set(facts):
            return ("repeat_result_value_unverified",), audit
        if any((not any((key, attribute) in qualified for attribute in ("value", "assertion_basis"))
                if semantic else (key, operand) not in qualified) for key in ids):
            return ("repeat_result_value_unverified",), audit
        if any((key, "date_range") not in qualified for key in ids):
            return ("known_date_unqualified",), audit
        if set(ids).intersection(conflicting_fact_ids):
            return ("source_conflict",), audit
        dates = {canonical_hash(None if facts[key].date_range is None else
                               facts[key].date_range.model_dump(mode="json", exclude={"source_text"}))
                 for key in ids}
        if len(dates) != 1:
            return ("repeat_same_acquisition_date_conflict",), audit
        # Only identical acquisition dates are represented once. All original
        # result records still participate in the downstream group calculation.
        representatives[group["group_id"]] = min(ids)
    audit["representative_fact_ids"] = representatives
    ordered = select_qualified_observation_dates(
        policy=policy, facts={key: facts[key] for key in representatives.values()},
        operand_fact_ids=tuple(representatives.values()), date_fact_ids=tuple(representatives.values()),
        time_constraint=time_constraint, anchor_dates=anchor_dates, time_purpose=time_purpose,
    )
    audit["ordering"] = asdict(ordered)
    if ordered.reasons:
        return ordered.reasons, audit
    selected = {group for group, key in representatives.items() if key in ordered.fact_ids}
    audit["agrees_with_repeat_selection"] = selected == set(resolution["selected_group_ids"])
    if selected != set(resolution["selected_group_ids"]):
        return ("repeat_ordering_policy_disagreement",), audit
    return (), audit
