"""Interpret sealed official source relations with the shared observation policy."""
from dataclasses import dataclass

from app.domain.contracts.enums import TruthValue
from app.domain.contracts.proposition_evidence import ProspectiveEvidenceCheck
from app.domain.expression import EvaluationResult, evaluate_time_constraint
from app.domain.proposition_observations import combine_observations, scope_supported, universal_statement


@dataclass(frozen=True)
class _Observation:
    fact_id: str
    truth: TruthValue
    reason_codes: list[str]


def calculate_predicate_proposition_fact(entry, fact, source_records, context):
    """One already-qualified source interpretation, shared by ordinary and repeat review."""
    predicate = entry.predicate
    reasons = []
    if fact.conflict_group_id:
        reasons.append("source_conflict")
    statuses = {item["status"] for item in source_records}
    if not statuses:
        reasons.append("semantic_evidence_unverified")
    elif len(statuses) != 1:
        reasons.append("proposition_relation_conflict")
    future_required = predicate.prospective_period is not None or predicate.prospective_window is not None
    if future_required:
        for record in source_records:
            for lane in record["lanes"].values():
                future = lane.get("prospective_evidence")
                reasons.extend(ProspectiveEvidenceCheck.model_validate(future).unresolved_codes()
                               if future is not None else ["prospective_statement_period_unverified"])
    if entry.time_constraint is not None:
        temporal = evaluate_time_constraint(
            entry.time_constraint, event_value=fact.effective_date,
            anchor_value=context.anchor_dates.get(entry.time_constraint.anchor_type),
            half_life_days=context.half_life_days.get(f"{predicate.subject}.{predicate.attribute}"),
        )
        if temporal.truth == TruthValue.FALSE:
            reasons.append("observation_out_of_window")
        elif temporal.truth == TruthValue.UNKNOWN:
            reasons.extend(temporal.reason_codes)
    truth = (TruthValue.UNKNOWN if reasons else
             TruthValue.TRUE if statuses == {"entails_agreed"} else TruthValue.FALSE)
    return _Observation(fact.fact_id, truth, sorted(set(reasons)) or (
        ["prospective_statement_verified"] if future_required else []))


def calculate_predicate_propositions(selections, context, *, repeat_triggers_only=False, condition_selection=None):
    material = selections.material
    by_identity = {item.identity_sha256: item for item in material.identity_outcomes}
    relations = material.proposition_relations
    pair_gaps = material.unresolved_proposition_pairs
    if condition_selection is not None:
        from app.domain.contracts.qualified_binding_selection import QualifiedBindingIdentityOutcome
        selections.require_unchanged()
        if not repeat_triggers_only or not any(
            condition_selection == row for observation in material.observation_relations
            for row in observation.get("condition_selections", ())
        ):
            raise ValueError("复查条件须使用本次封存的逐次资料选择")
        by_identity = {item.identity_sha256: item for raw in condition_selection["identity_outcomes"]
                       for item in (QualifiedBindingIdentityOutcome.model_validate(raw),)}
        relations = condition_selection["proposition_relations"]
        pair_gaps = condition_selection["unresolved_proposition_pairs"]
    facts = {item.fact_id: item for item in context.facts}
    result = {}
    for component in selections.predicate_frozen_input.components:
        if condition_selection is not None and component.rule_component_id != condition_selection["parent_id"]:
            continue
        outcomes = result.setdefault(component.rule_component_id, {})
        entries = (component.repeat_trigger_predicates if repeat_triggers_only else
                   (*component.trigger_predicates, *component.exception_predicates))
        for entry in entries:
            if condition_selection is not None and entry.predicate_identity_sha256 not in by_identity:
                continue
            predicate = entry.predicate
            if predicate.semantic_proposition is None:
                continue
            outcome = by_identity.get(entry.predicate_identity_sha256)
            if outcome is None:
                raise ValueError("所选资料缺少当前条件的核实结果，须按当前版本重新核对")
            records = [item for item in relations
                       if item["identity_sha256"] == entry.predicate_identity_sha256]
            gaps = [item for item in pair_gaps
                    if item["identity_sha256"] == entry.predicate_identity_sha256]
            if outcome.status != "usable" or material.proposition_evidence is None:
                outcomes[entry.predicate_id] = EvaluationResult(
                    truth=TruthValue.UNKNOWN,
                    reason_codes=sorted(set(outcome.unresolved_reasons or ["semantic_evidence_unverified"])
                                        | {reason for gap in gaps for reason in gap["reasons"]}),
                )
                continue
            by_fact = {fact_id: [] for fact_id in outcome.fact_ids}
            seen = set()
            for record in records:
                if (record["fact_id"] not in by_fact or record["pair_id"] in seen
                        or record["pair_id"] not in outcome.usable_pair_ids
                        or record.get("scope") != "pair_local"
                        or record.get("status") not in {"entails_agreed", "contradicts_agreed"}
                        or set(record.get("lanes", {})) != {"main-A", "main-B"}):
                    raise ValueError("正式条件的原文核实结果与所选资料不一致")
                seen.add(record["pair_id"])
                by_fact[record["fact_id"]].append(record)
            observations = []
            for fact_id, source_records in by_fact.items():
                observations.append(calculate_predicate_proposition_fact(entry, facts[fact_id], source_records, context))
            policy = predicate.observation_policy
            individual = {key for key, rows in by_fact.items() if any(
                all(lane.get("assertion_extent") == "individual" for lane in row["lanes"].values())
                for row in rows)}
            universal = {key for key, rows in by_fact.items() if any(
                lane.get("assertion_extent") == "universal_over_declared_scope"
                for row in rows for lane in row["lanes"].values())}
            universal_ready = bool(
                policy is not None and policy.mode in {"any", "all"} and not gaps
                and all(item.truth != TruthValue.UNKNOWN for item in observations)
                and any(universal_statement(by_fact[key], require_population=policy.mode == "all")
                        for key in universal))
            truth, reasons = combine_observations(
                policy, observations, individual_facts=individual, universal_facts=universal,
                universal_ready=universal_ready,
                scope_verified=len(observations) == 1 and scope_supported(records),
            )
            if truth == TruthValue.UNKNOWN:
                reasons = sorted(set(reasons) | {reason for gap in gaps for reason in gap["reasons"]})
            outcomes[entry.predicate_id] = EvaluationResult(
                truth=truth, reason_codes=reasons, used_fact_ids=list(outcome.fact_ids),
                evidence_span_ids=sorted({span for key in outcome.fact_ids for span in facts[key].evidence_span_ids}),
            )
    return result
