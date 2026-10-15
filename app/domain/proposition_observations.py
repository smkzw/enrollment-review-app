"""Combine source relations without treating supplied records as complete history."""
from app.domain.contracts.enums import TruthValue


def combine_observations(policy, observations, *, deterministic=False,
                         scope_verified=False, universal_facts=frozenset(),
                         individual_facts=None, universal_ready=False):
    if not observations:
        return TruthValue.UNKNOWN, ["selected_observation_missing"]
    if policy is None or policy.mode == "unresolved":
        return TruthValue.UNKNOWN, ["observation_selection_unverified"]
    if policy.mode == "single" and len(observations) != 1:
        return TruthValue.UNKNOWN, ["observation_selection_unverified"]
    if policy.mode == "single" and not deterministic and not scope_verified:
        return TruthValue.UNKNOWN, list(dict.fromkeys(
            ["observation_scope_completeness_unverified",
             *(reason for item in observations for reason in item.reason_codes)]
        ))
    if policy.mode == "action_completion":
        truths = {item.truth for item in observations}
        if TruthValue.UNKNOWN in truths:
            return TruthValue.UNKNOWN, list(dict.fromkeys(
                reason for item in observations if item.truth == TruthValue.UNKNOWN
                for reason in item.reason_codes
            ))
        if len(truths) > 1:
            return TruthValue.UNKNOWN, ["proposition_relation_conflict"]
        if not scope_verified:
            return TruthValue.UNKNOWN, ["observation_scope_completeness_unverified"]
        return observations[0].truth, list(dict.fromkeys(
            reason for item in observations for reason in item.reason_codes
        ))
    individual_truths = [item.truth for item in observations
                         if individual_facts is None or item.fact_id in individual_facts]
    universal_truths = [item.truth for item in observations if item.fact_id in universal_facts]
    if policy.mode == "single":
        return observations[0].truth, observations[0].reason_codes
    decisive = TruthValue.TRUE if policy.mode == "any" else TruthValue.FALSE
    opposite = TruthValue.FALSE if decisive == TruthValue.TRUE else TruthValue.TRUE
    if decisive in individual_truths:
        if opposite in universal_truths:
            return TruthValue.UNKNOWN, ["proposition_relation_conflict"]
        return decisive, list(dict.fromkeys(
            reason for item in observations if item.truth == decisive for reason in item.reason_codes
        ))
    truths = [item.truth for item in observations]
    if TruthValue.UNKNOWN in truths:
        return TruthValue.UNKNOWN, list(dict.fromkeys(
            reason for item in observations if item.truth == TruthValue.UNKNOWN for reason in item.reason_codes
        ))
    if universal_ready:
        if set(truths) == {opposite}:
            return opposite, list(dict.fromkeys(reason for item in observations for reason in item.reason_codes))
        if opposite in truths:
            return TruthValue.UNKNOWN, ["proposition_relation_conflict"]
        return TruthValue.UNKNOWN, ["universal_statement_not_forward_witness"]
    return TruthValue.UNKNOWN, ["observation_scope_completeness_unverified"]


def scope_supported(records):
    return bool(records) and all(
        set(record.get("lanes", {})) == {"main-A", "main-B"}
        and all(lane.get("scope_correspondence") == "supported"
                and isinstance(lane.get("scope_quote"), str) and lane["scope_quote"].strip()
                for lane in record["lanes"].values()) for record in records
    )


def universal_statement(records, *, require_population=False):
    return scope_supported(records) and all(
        record.get("scope_candidates_complete") is True
        and all(lane.get("assertion_extent") == "universal_over_declared_scope"
                and (not require_population or (
                    lane.get("scope_population") == "nonempty"
                    and isinstance(lane.get("population_quote"), str)
                    and lane["population_quote"].strip()))
                for lane in record["lanes"].values()) for record in records
    )
