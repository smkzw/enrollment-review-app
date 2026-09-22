"""Calculate declared frequency conditions from receipt-verified source totals."""
from app.domain.contracts.evaluation_result import EvaluationResult, FrequencyAtomEvaluation
from app.domain.contracts.enums import TruthValue
from app.domain.contracts.rules import AtomicExpression
from app.domain.publication import canonical_hash
from app.services.frequency_total_resolution import resolve_frequency_totals
from app.services.qualified_binding_selection import (
    ReceiptVerifiedQualifiedBindingSelections,
    ReceiptVerifiedWorkDraftSelections,
)


def calculate_frequency_atoms(selections, context, *, condition_selection=None):
    """Preserve source and rule identities; this does not authorize publication."""
    if not isinstance(selections, (
        ReceiptVerifiedQualifiedBindingSelections, ReceiptVerifiedWorkDraftSelections,
    )):
        raise TypeError("频次计算须使用本次来源核实结果")
    selections.require_unchanged()
    scoped_outcomes = None
    if condition_selection is not None:
        from app.services.repeat_condition_selection import iter_scoped_repeat_conditions
        matches = [outcomes for _, _, _, _, row, outcomes in iter_scoped_repeat_conditions(selections)
                   if row == condition_selection]
        if len(matches) != 1:
            raise ValueError("复查频次须对应唯一的本次封存条件范围")
        scoped_outcomes = {item.identity_sha256: item for item in matches[0]}
    family = selections.candidate_family
    frozen = selections.predicate_frozen_input if family == "predicate" else selections.control_input
    source = frozen if family == "predicate" else frozen.evidence_input
    authority = source.authority
    if ((context.project_id, context.subject_id, context.review_episode_id, context.evidence_snapshot_id)
            != (authority.project_id, authority.subject_id, authority.review_episode_id, authority.evidence_snapshot_v2_id)
            or context.anchor_dates != source.episode.anchor_dates
            or set(context.accepted_fact_ids) != {item.fact_id for item in source.facts}):
        raise ValueError("频次计算与当前节点及资料范围不一致")
    from app.services.eligibility_review_projection import _phase3_date_value
    originals = {item.fact_id: item for item in source.facts}
    for fact in context.facts:
        original = originals.get(fact.fact_id)
        if (original is None
                or any(getattr(fact, name) != getattr(original, name)
                       for name in ("fact_type", "value", "unit", "polarity"))
                or fact.effective_date != _phase3_date_value(original.date_range)
                or fact.evidence_span_ids != original.locator_ids):
            raise ValueError("频次计算的原始资料或定位已变化")
    if family == "predicate":
        entries = {item.predicate_identity_sha256: item for component in frozen.components
                   for item in component.binding_predicates}
        primary_ids = {item.predicate_identity_sha256 for component in frozen.components
                       for item in (*component.trigger_predicates, *component.exception_predicates)}
    else:
        from app.projections.control_atom_binding_input import project_control_atom_identities
        entries = {item.identity_sha256: item for item in project_control_atom_identities(
            frozen.publication, include_repeat_triggers=True)}
        primary_ids = {item.identity_sha256 for item in project_control_atom_identities(frozen.publication)}
    results = {}
    for qualified in selections.material.frequency_statements:
        identity = qualified["identity_sha256"]
        if identity not in entries or identity in results:
            raise ValueError("频次依据不能重复应用或用于其他条件")
        # Auxiliary conditions retain their qualified evidence, but must be
        # evaluated for their own repeat target rather than at the parent node.
        if scoped_outcomes is None and identity not in primary_ids:
            continue
        if scoped_outcomes is not None and (identity in primary_ids or identity not in scoped_outcomes):
            continue
        entry = entries[identity]
        if family == "predicate":
            predicate = entry.predicate
            atom = AtomicExpression(predicate=predicate, time_constraint=entry.time_constraint)
            professional = predicate.requires_professional_judgment
        else:
            atom = entry.atom
            spec = atom.evaluation
            if spec is None or spec.determination_mode != "deterministic":
                raise ValueError("频次计算不能替代原文含义或研究者判断")
            predicate = spec.predicate
            professional = atom.requires_professional_judgment
        if (predicate is None or predicate.occurrence_window is None
                or predicate.repeat_scheme is not None or professional):
            raise ValueError("当前条件不支持独立频次计算")
        if scoped_outcomes is not None:
            if condition_selection["version"] != "repeat-condition-selection/v3":
                raise ValueError("旧复查范围未核实频次来源，须按当前方法准备")
            from app.services.repeat_frequency_scope import scope_repeat_frequency
            qualified = scope_repeat_frequency(qualified, scoped_outcomes[identity], condition_selection,
                                                predicate.occurrence_window, source.episode.model_dump(mode="json"))
        pairs = qualified["statement_source_pairs"]
        source_ids = sorted({item["fact_id"] for item in pairs.values()})
        if any(item["fact_id"] not in originals
               or item["locator_id"] not in originals[item["fact_id"]].locator_ids
               or item["identity_sha256"] != identity
               or item["pair_id"] != key for key, item in pairs.items()):
            raise ValueError("频次依据包含本次范围外的资料或原文位置")
        resolution = resolve_frequency_totals(
            predicate, qualified, source_pairs=pairs,
            has_outer_time_constraint=atom.time_constraint is not None,
        )
        resolution["selection_sha256"] = selections.material.selection_sha256
        resolution["source_frequency_sha256"] = canonical_hash(qualified)
        if condition_selection is not None:
            resolution["repeat_scope_sha256"] = canonical_hash(condition_selection)
        calculated = EvaluationResult.model_validate(resolution["result"])
        if any(fact.conflict_group_id for fact in context.facts if fact.fact_id in source_ids):
            calculated = EvaluationResult(truth=TruthValue.UNKNOWN, reason_codes=["source_conflict"])
        calculated.evidence_span_ids = sorted({locator for key in calculated.used_fact_ids
                                               for locator in originals[key].locator_ids})
        resolution["result"] = calculated.model_dump(mode="json")
        results[identity] = FrequencyAtomEvaluation(
            context_sha256=(canonical_hash(context.model_dump(mode="json")) if family == "predicate"
                            else frozen.frozen_input_sha256),
            atom_sha256=canonical_hash(atom.model_dump(mode="json")),
            resolution_sha256=canonical_hash(resolution), source_fact_ids=source_ids,
            result=calculated, resolution=resolution,
        )
    return results
