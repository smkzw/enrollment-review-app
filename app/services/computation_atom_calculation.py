"""Exact arithmetic on sealed source inputs, never synthetic ClinicalFacts."""
from app.domain.contracts.evaluation_result import ComputationAtomEvaluation, EvaluationResult
from app.domain.contracts.enums import TruthValue
from app.domain.contracts.rules import AtomicExpression
from app.domain.expression import evaluate_calculated_numeric_value
from app.domain.publication import canonical_hash
from app.domain.repeat_numeric_result import aggregate_numeric_acquisitions
from app.services.qualified_binding_selection import ReceiptVerifiedWorkDraftSelections

VERSION = "computation-atom-calculation/v1"

_INPUT_REASONS = {
    "computation_selection_policy_unsupported": "计算记录的选取方式、数量或时间范围尚不能核实",
    "computation_missing_policy_unsupported": "方案的缺失记录处理尚未接通",
    "computation_operator_unsupported": "方案规定的计算操作尚不支持",
    "computation_period_quantity_unsupported": "方案规定的每期间数量及换算依据已保留，相关计算尚未接通",
    "computation_scope_policy_unsupported": "计算的适用对象或时间条件尚不能核实",
    "computation_input_membership_unverified": "部分原始记录是否属于本项计算尚未核清",
    "computation_acquisition_identity_unverified": "尚不能确认记录分别来自哪些独立采集",
    "computation_required_inputs_incomplete": "已核实的独立采集数与方案要求不一致",
    "computation_source_appearances_incomplete": "相关原文位置尚未全部核对",
    "computation_source_scope_unresolved": "计算记录的来源关系仍有疑问",
    "computation_source_unqualified": "计算记录的来源或内容尚未通过核对",
    "computation_source_policy_unverified": "计算记录是否属于方案允许的来源尚未核清",
    "computation_source_correspondence_unverified": "计算记录与本项要求的对应关系尚未核清",
    "computation_unit_unverified": "计算记录的单位尚未核对一致",
    "computation_value_changed": "计算记录的数值已变化，需重新核对",
}


def computation_result_note(evaluation):
    """User-facing source scope and exact arithmetic, not raw engineering codes."""
    if evaluation is None:
        return ""
    if evaluation.result.truth == TruthValue.UNKNOWN:
        notes = sorted({_INPUT_REASONS[reason] for reason in evaluation.result.reason_codes if reason in _INPUT_REASONS})
        return "计算依据：" + "；".join(notes or ["计算所需原始记录或计算结果尚未核清"]) + "。"
    exact = evaluation.resolution["exact_value"]
    number = exact["numerator"] if exact["denominator"] == "1" else exact["numerator"] + "/" + exact["denominator"]
    operation = evaluation.resolution["input_qualification"]["source_computation"]["operator"]
    label = {"mean": "均值", "sum": "合计", "minimum": "最小值", "maximum": "最大值"}[operation]
    count = len(evaluation.resolution["input_qualification"]["acquisition_fact_ids"])
    unit = evaluation.resolution["unit"]
    return f"按本次已提供并核实的{count}次采集计算，{label}为{number}{(' ' + unit) if unit else ''}。"


def calculate_computation_atoms(selections, context):
    # Formal activation remains a separate, evaluated adoption boundary.
    if not isinstance(selections, ReceiptVerifiedWorkDraftSelections):
        return {}
    selections.require_unchanged()
    frozen = selections.predicate_frozen_input if selections.candidate_family == "predicate" else selections.control_input
    source = frozen if selections.candidate_family == "predicate" else frozen.evidence_input
    authority = source.authority
    if ((context.project_id, context.subject_id, context.review_episode_id, context.evidence_snapshot_id)
            != (authority.project_id, authority.subject_id, authority.review_episode_id, authority.evidence_snapshot_v2_id)
            or context.anchor_dates != source.episode.anchor_dates
            or sorted(context.accepted_fact_ids) != sorted(item.fact_id for item in source.facts)
            or sorted(item.fact_id for item in context.facts) != sorted(context.accepted_fact_ids)):
        raise ValueError("计算输入与本次节点、资料范围不一致")
    from app.services.eligibility_review_projection import _phase3_date_value
    originals = {item.fact_id: item for item in source.facts}
    facts = {item.fact_id: item for item in context.facts}
    for fact in facts.values():
        original = originals[fact.fact_id]
        if (any(getattr(fact, key) != getattr(original, key) for key in ("fact_type", "value", "unit", "polarity"))
                or fact.effective_date != _phase3_date_value(original.date_range)
                or fact.evidence_span_ids != original.locator_ids):
            raise ValueError("计算输入数值、时间或原文定位已变化")
    if selections.candidate_family == "predicate":
        entries = {item.predicate_identity_sha256: (item, AtomicExpression(
            predicate=item.predicate, time_constraint=item.time_constraint))
            for component in frozen.components for item in (*component.trigger_predicates, *component.exception_predicates)}
    else:
        from app.projections.control_atom_binding_input import project_control_atom_identities
        entries = {item.identity_sha256: (item, item.atom)
                   for item in project_control_atom_identities(frozen.publication)}
    results = {}
    for row in selections.computation_sources:
        identity = row["identity_sha256"]
        if identity not in entries:
            continue  # Auxiliary repeat inputs are not evaluated at the parent node.
        if identity in results:
            raise ValueError("同一计算条件不能重复应用")
        entry, atom = entries[identity]
        predicate = (entry.predicate if selections.candidate_family == "predicate"
                     else atom.evaluation.predicate)
        computation = predicate.source_computation
        qualified = row["input_qualification"]
        if (computation is None or qualified["identity_sha256"] != identity
                or qualified["source_computation"] != computation.model_dump(mode="json")
                or qualified["qualification_sha256"] != canonical_hash({
                    key: value for key, value in qualified.items() if key != "qualification_sha256"})):
            raise ValueError("计算输入证明与当前条件声明不一致")
        source_ids = qualified["fact_ids"]
        if not set(source_ids) <= facts.keys():
            raise ValueError("计算输入包含当前资料范围之外的事实")
        reasons = list(qualified["reason_codes"])
        if computation.quantity_basis is not None:
            reasons.append("computation_period_quantity_unsupported")
        value, unit = None, None
        if not reasons and qualified["input_set_qualified"]:
            value, unit, numeric_reasons = aggregate_numeric_acquisitions(
                [[facts[key].model_copy(update={"unit": facts[key].unit.strip() if facts[key].unit is not None else None})
                  for key in group]
                 for group in qualified["acquisition_fact_ids"]],
                operation=computation.operator, unit_required=predicate.unit is not None,
                allow_reused_facts=bool(qualified["reused_fact_source_bindings"]),
            )
            reasons.extend(numeric_reasons)
        else:
            reasons.append("source_computation_operands_unverified")
        if value is None or reasons:
            result = EvaluationResult(truth=TruthValue.UNKNOWN, reason_codes=sorted(set(reasons)))
        else:
            # Strip only the arithmetic declaration for the existing exact comparator.
            # The wrapper retains the full original atom, source proof and sealed selection.
            result = evaluate_calculated_numeric_value(
                predicate.model_copy(update={"source_computation": None}), value=value, unit=unit)
            result.used_fact_ids = list(source_ids)
            result.evidence_span_ids = sorted({span for key in source_ids for span in facts[key].evidence_span_ids})
        resolution = {"version": VERSION, "selection_sha256": selections.selection_sha256,
            "input_qualification": qualified,
            "exact_value": None if value is None else {
                "numerator": str(value.numerator), "denominator": str(value.denominator)},
            "unit": unit, "result": result.model_dump(mode="json")}
        results[identity] = ComputationAtomEvaluation(
            context_sha256=(canonical_hash(context.model_dump(mode="json")) if selections.candidate_family == "predicate"
                            else frozen.frozen_input_sha256),
            atom_sha256=canonical_hash(atom.model_dump(mode="json")),
            resolution_sha256=canonical_hash(resolution), source_fact_ids=source_ids,
            result=result, resolution=resolution)
    return results
