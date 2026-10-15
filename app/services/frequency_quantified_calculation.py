"""Apply the same qualified evidence independently to declared period instances."""
from datetime import date

from app.domain.contracts.frequency_evidence import FrequencyStatement
from app.domain.frequency_individual_qualification import qualify_individual_days, qualify_individual_occurrences
from app.domain.frequency_period_qualification import qualify_total_period
from app.domain.frequency_quantified_periods import enumerate_frequency_periods
from app.domain.publication import canonical_hash


def calculate_quantified_frequency(statements, relationships, window, episode):
    if window.scope is None or window.scope.quantifier not in {"any", "every"}:
        return None
    domain = enumerate_frequency_periods(window, episode)
    domain_sha256 = canonical_hash(domain)
    rows = []
    totals = {key: FrequencyStatement.model_validate({**value, "statement_index": 0, "explanation": "已核实原文"})
              for key, value in statements.items() if value["kind"] == "stated_total"}
    for period in domain["periods"]:
        required = ((date.fromisoformat(period["start"]),), (date.fromisoformat(period["end"]),),
                    {"reason_codes": [], "quantified_period": period,
                     "domain_sha256": domain_sha256})
        rows.append({
            "period": period,
            "individual_calculation": qualify_individual_occurrences(
                statements, relationships, window, episode, required_period=required),
            "day_calculation": qualify_individual_days(statements, window, episode, required_period=required),
            "statement_period_calculations": {
                key: qualify_total_period(value, window, episode, required_period=required)
                for key, value in totals.items()
            },
        })
    return {"version": "frequency-quantified-calculation/v1", "quantifier": window.scope.quantifier,
            "domain": domain, "period_calculations": rows}
