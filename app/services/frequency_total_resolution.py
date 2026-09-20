"""Resolve qualified, period-bound totals without inventing individual events."""
from app.domain.contracts.enums import TruthValue
from app.domain.contracts.evaluation_result import EvaluationResult
from app.domain.occurrence_count_bounds import OccurrenceCountBounds, evaluate_count_bounds, intersect_count_bounds


def _resolve_single_frequency(predicate, qualified, *, source_pairs, has_outer_time_constraint=False):
    """The caller must first verify the exact method, input and source receipts."""
    material = {
        "version": "frequency-total-resolution/v2", "identity_sha256": qualified["identity_sha256"],
        "group_id": qualified["group_id"], "bounds": None, "statement_sources": [],
        "period_calculations": qualified["statement_period_calculations"], "replacement_authorized": False,
        "individual_calculation": qualified["individual_calculation"],
        "day_calculation": qualified["day_calculation"],
    }
    def unresolved(reason, *details):
        return {**material, "result": EvaluationResult(
            truth=TruthValue.UNKNOWN, reason_codes=list(dict.fromkeys((reason, *details))),
        ).model_dump(mode="json")}
    if has_outer_time_constraint:
        return unresolved("frequency_outer_window_combination_unresolved")
    window = predicate.occurrence_window
    if window is None:
        raise ValueError("无频次条件不能消费计数结果")
    if predicate.comparator == "exists" and window.minimum_count is not None:
        comparator, threshold, unit = "gte", window.minimum_count, "occurrences"
    elif type(predicate.value) in {int, float} and predicate.unit in {"次", "天", "日", "day", "days"}:
        comparator, threshold = predicate.comparator, predicate.value
        unit = "occurrences" if predicate.unit == "次" else "days"
    else:
        return unresolved("frequency_threshold_structure_unresolved")
    if comparator not in {"eq", "ne", "gt", "gte", "lt", "lte"}:
        return unresolved("frequency_comparator_unresolved")
    if (qualified["source_unresolved"] or qualified["disputed_statement_sha256s"]
            or qualified["disputed_relationships"] or qualified["unresolved_notes"]):
        return unresolved("frequency_sources_unresolved")
    intervals = []
    individual = qualified["individual_calculation"]
    has_individual = any(item["kind"] == "individual_occurrence" for item in qualified["qualified_statements"].values())
    if has_individual:
        if unit != "occurrences" or individual.get("bounds") is None:
            return unresolved("frequency_detail_period_reconciliation_pending", *individual["reason_codes"])
        intervals.append(OccurrenceCountBounds(**individual["bounds"]))
    days = qualified["day_calculation"]
    if any(item["kind"] == "individual_day" for item in qualified["qualified_statements"].values()):
        if unit != "days" or days.get("bounds") is None:
            return unresolved("frequency_detail_period_reconciliation_pending", *days["reason_codes"])
        intervals.append(OccurrenceCountBounds(**days["bounds"]))
    for key, statement in qualified["qualified_statements"].items():
        if statement["kind"] not in {"stated_total", "individual_occurrence", "individual_day"}:
            continue
        if statement["count_unit"] != unit:
            return unresolved("frequency_count_unit_unresolved")
        if statement["kind"] == "stated_total":
            period = qualified["statement_period_calculations"].get(key)
            if period is None or period.get("bounds") is None:
                return unresolved("frequency_total_period_unverified", *((period or {}).get("reason_codes", ())))
            intervals.append(OccurrenceCountBounds(**period["bounds"]))
        pair = source_pairs.get(statement["source_pair_id"])
        if (pair is None or pair["identity_sha256"] != qualified["identity_sha256"]
                or pair["pair_id"] != statement["source_pair_id"]):
            raise ValueError("频次结果无法返回本要求的原文配对")
        material["statement_sources"].append({
            "statement_sha256": key, "pair_id": pair["pair_id"], "fact_id": pair["fact_id"], "locator_id": pair["locator_id"],
            "kind": statement["kind"], "count": statement["count"], "count_relation": statement.get("count_relation"), "count_unit": statement["count_unit"],
            "count_excerpt": statement["count_excerpt"], "period_excerpt": statement["period_excerpt"],
            "occurrence_date": statement.get("occurrence_date"),
        })
    if not intervals:
        return unresolved("frequency_total_not_available")
    combined = intersect_count_bounds(intervals)
    if combined is None:
        return unresolved("occurrence_count_bounds_conflict")
    result = evaluate_count_bounds(combined, comparator=comparator, threshold=threshold)
    result = result.model_copy(update={
        "used_fact_ids": sorted({item["fact_id"] for item in material["statement_sources"]}),
        "observed_value": combined.lower if combined.lower == combined.upper else None,
        "observed_unit": "次" if unit == "occurrences" else "天",
    })
    return {**material, "bounds": {"lower": combined.lower, "upper": combined.upper},
            "result": result.model_dump(mode="json")}


def resolve_frequency_totals(predicate, qualified, *, source_pairs, has_outer_time_constraint=False):
    quantified = qualified.get("quantified_calculations")
    if quantified is None:
        return _resolve_single_frequency(predicate, qualified, source_pairs=source_pairs,
                                         has_outer_time_constraint=has_outer_time_constraint)
    domain = quantified["domain"]
    rows = [{"period": row["period"], "calculation": _resolve_single_frequency(
        predicate, {**qualified, **row}, source_pairs=source_pairs,
        has_outer_time_constraint=has_outer_time_constraint,
    )} for row in quantified["period_calculations"]]
    results = [EvaluationResult.model_validate(row["calculation"]["result"]) for row in rows]
    quantifier = quantified["quantifier"]
    if quantifier not in {"any", "every"}:
        raise ValueError("多个计数期间缺少明确量词")
    witness_truth = TruthValue.TRUE if quantifier == "any" else TruthValue.FALSE
    witnesses = [result for result in results if result.truth == witness_truth]
    reasons = list(domain["reason_codes"])
    # Only a processing limit permits a sound prefix witness. Other failures
    # leave the domain interpretation unverified, even if a prefix exists.
    domain_valid = not reasons or reasons == ["frequency_period_processing_limit"]
    if witnesses and domain_valid:
        truth, used = witness_truth, witnesses
        reasons = []
    elif domain["domain_complete"] and domain_valid and results and all(
            result.truth != TruthValue.UNKNOWN for result in results):
        truth = TruthValue.FALSE if quantifier == "any" else TruthValue.TRUE
        used = results
    else:
        truth, used = TruthValue.UNKNOWN, results
        reasons.extend(reason for result in results for reason in result.reason_codes)
        reasons.append("frequency_quantified_periods_unresolved")
    result = EvaluationResult(truth=truth, reason_codes=list(dict.fromkeys(reasons)),
                              used_fact_ids=sorted({key for value in used for key in value.used_fact_ids}))
    return {"version": "frequency-total-resolution/v3", "identity_sha256": qualified["identity_sha256"],
            "group_id": qualified["group_id"], "bounds": None, "statement_sources": [],
            "quantifier": quantifier, "domain": domain, "period_results": rows,
            "replacement_authorized": False, "result": result.model_dump(mode="json")}
