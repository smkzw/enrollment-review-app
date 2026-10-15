"""Bind agreed frequency statements to qualified original sources."""
from app.domain.contracts.frequency_evidence import FrequencyEvidenceResult
from app.domain.publication import canonical_hash
from app.domain.frequency_period_qualification import qualify_total_period
from app.domain.frequency_individual_qualification import qualify_individual_occurrences, qualify_individual_days
from app.services.frequency_evidence_job import verify_completed_frequency_evidence
from app.services.frequency_quantified_calculation import calculate_quantified_frequency
from app.services.review_method_evidence import read_method_evaluation
from app.storage.repositories import ScopeViolationError

FREQUENCY_CONSUMER_VERSION = "qualified-frequency-evidence/v6"


def require_frequency_method(manifest, binding_method, evidence):
    methods = [item for item in manifest.methods if item.candidate_family == binding_method.candidate_family]
    if manifest.evaluation_kind != "frequency_statement_fidelity" or len(methods) != 1:
        raise ScopeViolationError("频次核对尚无对应要求类型的独立评测")
    method = methods[0]
    if (method.source_qualification_method != binding_method
            or method.content_contract != evidence["contract"]
            or method.content_prompt_version != evidence["prompt_version"]
            or method.content_summary_version != evidence["summary"]["version"]
            or {key: value.model_dump(mode="json") for key, value in method.content_routes.items()} != evidence["routes"]
            or method.content_consumer_version != FREQUENCY_CONSUMER_VERSION):
        raise ScopeViolationError("频次核对的来源、提示、模型或采用版本与评测不一致")


def verify_qualified_frequency_evidence(session, artifact_store, *, source, binding_method, adoption):
    evidence = verify_completed_frequency_evidence(session, artifact_store, adoption.job_id)
    payload = evidence["payload"]
    if (payload["candidate_job_id"] != source["payload"]["candidate_job_id"]
            or any(payload.get(key) is None or payload[key] != source["payload"].get(key)
                   for key in ("review_context_id", "review_context_sha256", "frozen_input_sha256", "comparison_sha256"))
            or evidence["summary_sha256"] != adoption.summary_logical_sha256
            or evidence["summary_artifact_sha256"] != adoption.summary_artifact_sha256):
        raise ScopeViolationError("频次结果与当前资料或审核节点不一致")
    sources = {pair.pair_id: pair for pair in source["pairs"]}
    if any(sources.get(member.pair_id) != member or member.candidate_family != source["candidate_family"]
           for group in evidence["pairs"] for member in group.members):
        raise ScopeViolationError("频次原文不属于当前来源核对范围")
    require_frequency_method(read_method_evaluation(artifact_store, adoption.evaluation_sha256), binding_method, evidence)
    return evidence


def select_qualified_frequency_sources(evidence, source_records, *, source_validity_specs=None):
    """Preserve source-qualified statements without asserting their period coverage."""
    from app.services.qualified_binding_selection import (
        pair_direct_selection_rejection_reasons, source_validity_operand_calculable,
    )
    records = {item.pair_id: item for item in source_records}
    groups = {item.pair_id: item for item in evidence["pairs"]}
    specs = source_validity_specs or {}
    output = []
    for comparison in evidence["summary"]["comparisons"]:
        group = groups[comparison["group_id"]]
        members = {item.pair_id: item for item in group.members}
        lanes = {lane: FrequencyEvidenceResult.model_validate(comparison["lanes"][lane])
                 for lane in ("main-A", "main-B")}
        indexed = {lane: {canonical_hash(item.source_key()): item for item in answer.statements}
                   for lane, answer in lanes.items()}

        def quote_reasons(pair_id, quote):
            pair, record = members.get(pair_id), records.get(pair_id)
            if pair is None or record is None:
                return ["source_qualification_missing"]
            if any(getattr(record, key) != getattr(pair, key)
                   for key in ("identity_sha256", "fact_id", "locator_id", "fact_attribute")):
                return ["source_qualification_mismatch"]
            excerpt = pair.locator.get("excerpt")
            if (not isinstance(excerpt, str) or not isinstance(quote, str)
                    or not quote.strip() or quote not in excerpt):
                return ["frequency_quote_unverified"]
            return pair_direct_selection_rejection_reasons(
                record, written_content_verified=False,
                source_validity_calculable=source_validity_operand_calculable(record, specs.get(record.identity_sha256)),
            )

        accepted, unresolved = {}, []
        for key in comparison["agreed_statement_sha256s"]:
            statements = [indexed[lane][key] for lane in ("main-A", "main-B")]
            reasons = sorted({reason for statement in statements
                              for quote in (statement.count_excerpt, statement.period_excerpt,
                                            statement.occurrence_date.excerpt if statement.occurrence_date is not None else None,
                                            *(statement.period.source_quotes() if statement.period is not None else ()))
                              if quote is not None
                              for reason in quote_reasons(statement.source_pair_id, quote)})
            first = statements[0]
            if first.kind == "unresolved":
                reasons.append("frequency_statement_unresolved")
            if reasons:
                unresolved.append({"statement_sha256": key, "reason_codes": sorted(set(reasons))})
            else:
                accepted[key] = first.model_dump(mode="json", exclude={"statement_index", "explanation"})
        links = []
        for raw in comparison["agreed_relationships"]:
            relation, left, right = raw
            if left not in accepted or right not in accepted:
                unresolved.append({"relationship": raw, "reason_codes": ["frequency_statement_source_unverified"]})
                continue
            reasons = []
            for lane, answer in lanes.items():
                by_index = {item.statement_index: canonical_hash(item.source_key()) for item in answer.statements}
                matches = [link for link in answer.relationships if link.relation == relation
                           and {by_index[link.left_statement_index], by_index[link.right_statement_index]} == {left, right}]
                if len(matches) != 1:
                    raise ScopeViolationError("频次关系无法返回双路原始声明")
                for quote in matches[0].quotes:
                    reasons.extend(quote_reasons(quote.pair_id, quote.excerpt))
            if reasons:
                unresolved.append({"relationship": raw, "reason_codes": sorted(set(reasons))})
            else:
                links.append(raw)
        output.append({
            "identity_sha256": group.identity_sha256, "group_id": group.pair_id,
            "qualified_statements": accepted, "qualified_relationships": links,
            "quantified_calculations": calculate_quantified_frequency(
                accepted, links, group.window, group.members[0].episode),
            "individual_calculation": qualify_individual_occurrences(
                accepted, links, group.window, group.members[0].episode,
            ),
            "day_calculation": qualify_individual_days(accepted, group.window, group.members[0].episode),
            "statement_source_pairs": {
                pair_id: {key: getattr(members[pair_id], key) for key in (
                    "pair_id", "identity_sha256", "fact_id", "locator_id",
                )}
                for pair_id in sorted({item["source_pair_id"] for item in accepted.values()})
            },
            "statement_period_calculations": {
                key: qualify_total_period(indexed["main-A"][key], group.window, group.members[0].episode)
                for key in accepted if indexed["main-A"][key].kind == "stated_total"
            },
            "source_unresolved": unresolved, "disputed_statement_sha256s": comparison["disputed_statement_sha256s"],
            "disputed_relationships": comparison["disputed_relationships"],
            "unresolved_notes": sorted({note for answer in lanes.values() for note in answer.unresolved_notes}),
            "period_coverage_verified": False, "enumeration_complete": False,
            "consumer_version": FREQUENCY_CONSUMER_VERSION,
        })
    return output
