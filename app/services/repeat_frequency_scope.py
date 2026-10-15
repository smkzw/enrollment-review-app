"""Recalculate frequency evidence within an already sealed repeat-source scope."""
from app.domain.contracts.frequency_evidence import FrequencyStatement
from app.domain.frequency_individual_qualification import qualify_individual_days, qualify_individual_occurrences
from app.domain.frequency_period_qualification import qualify_total_period
from app.domain.publication import canonical_hash
from app.services.frequency_quantified_calculation import calculate_quantified_frequency


def scope_repeat_frequency(qualified, outcome, row, window, episode):
    allowed = set(outcome.usable_pair_ids)
    pairs = {key: value for key, value in qualified["statement_source_pairs"].items()
             if key in allowed and value["fact_id"] in outcome.fact_ids}
    statements = {key: value for key, value in qualified["qualified_statements"].items()
                  if value["source_pair_id"] in pairs}
    links, crossed = [], []
    for relation, left, right in qualified["qualified_relationships"]:
        if left in statements and right in statements:
            links.append([relation, left, right])
        elif left in statements or right in statements:
            crossed.append([relation, left, right])
    unresolved = list(qualified["source_unresolved"])
    if crossed:
        unresolved.append({"relationships": crossed, "reason_codes": ["frequency_relation_crosses_repeat_scope"]})
    if outcome.status != "usable":
        unresolved.append({"reason_codes": list(outcome.unresolved_reasons) or ["repeat_condition_source_not_found"]})
    return {
        **qualified, "qualified_statements": statements, "qualified_relationships": links,
        "statement_source_pairs": pairs, "source_unresolved": unresolved,
        "repeat_scope_sha256": canonical_hash(row),
        "unscoped_frequency_sha256": canonical_hash(qualified),
        "individual_calculation": qualify_individual_occurrences(statements, links, window, episode),
        "day_calculation": qualify_individual_days(statements, window, episode),
        "statement_period_calculations": {
            key: qualify_total_period(FrequencyStatement.model_validate(
                {**value, "statement_index": 0, "explanation": "已核实原文"}), window, episode)
            for key, value in statements.items() if value["kind"] == "stated_total"
        },
        "quantified_calculations": calculate_quantified_frequency(statements, links, window, episode),
    }
