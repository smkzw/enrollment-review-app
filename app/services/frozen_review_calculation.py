"""Calculate a frozen review with the workbench evaluator, without publishing it."""
from dataclasses import asdict, dataclass, field
from collections.abc import Mapping, Sequence

from app.agents.protocol_control_source_interpretation import normalize_source_excerpt
from app.domain.contracts.control_atom_binding import ControlBindingFrozenInput
from app.domain.contracts.control_catalog_publication import ControlCatalogPublication
from app.domain.contracts.protocol_controls import ProtocolControlDefinitionConsumerRecord
from app.domain.contracts.review_context_v2 import ReviewContextSnapshotV2
from app.domain.contracts.rules import RuleSet, iter_atomic_predicates
from app.domain.contracts.qualified_binding_selection import QualifiedBindingSelectionMaterial
from app.domain.expression import EvaluationContext, RepeatAtomEvaluation
from app.domain.contracts.evaluation_result import FrequencyAtomEvaluation, ComputationAtomEvaluation
from app.domain.publication import canonical_hash
from app.services.component_review import ComponentReviewResult, calculate_component_review
from app.services.predicate_binding_input import _frozen_fact
from app.projections.control_review_outcome import ControlReviewOutcome, project_control_review_outcomes
from app.projections.control_calculation_experiment import (
    ControlCalculationExperiment, evaluate_control_layers_experiment,
)
from app.services.eligibility_review_projection import (
    _expectation_views, _phase3_conflict_groups,
    _summary_gap_requirements, adapt_clinical_facts_v2, clause_to_rule_component,
)
from app.services.judgment_gap_selection import missing_judgment_predicates
from app.services.qualified_binding_selection import (
    ReceiptVerifiedWorkDraftSelections,
    ReceiptVerifiedQualifiedBindingSelections,
    assert_receipt_verified_selections_match_review_context,
    assert_qualified_selections_match_review_context,
)

EVALUATOR_VERSION = "component-review/v38"

#: Reason attached to a consumer whose source definition has no proven
#: consumer relation yet. It never replaces the evidence-based reason of an
#: unaffected sibling.
DEFINITION_CONSUMER_UNVERIFIED_REASON = "source_definition_consumer_unproven"


@dataclass(frozen=True)
class DefinitionConsumerConsumption:
    """What the working draft consumed from one saved definition relation."""

    batch_id: str
    source_statement_index: int
    structure_unit_id: str
    predicate_ids: tuple[tuple[str, str], ...]
    control_atom_identities: tuple[str, ...]


@dataclass(frozen=True)
class FrozenComponentCalculation:
    rule_component_id: str
    context_sha256: str
    result: ComponentReviewResult
    accepted: bool = field(default=False, init=False)


@dataclass(frozen=True)
class FrozenReviewCalculation:
    """Complete calculation scope, not permission to publish clinical results."""

    context_sha256: str
    selections_sha256: str
    components: tuple[FrozenComponentCalculation, ...]
    controls: ControlCalculationExperiment | None
    qualification_materials: tuple[QualifiedBindingSelectionMaterial, ...] = ()
    control_outcomes: tuple[ControlReviewOutcome, ...] = ()
    repeat_condition_calculations: tuple[dict, ...] = ()
    repeat_result_resolutions: tuple[dict, ...] = ()
    repeat_atom_evaluations: dict[str, dict[str, RepeatAtomEvaluation]] = field(default_factory=dict)
    frequency_atom_evaluations: dict[str, dict[str, FrequencyAtomEvaluation]] = field(default_factory=dict)
    computation_atom_evaluations: dict[str, dict[str, ComputationAtomEvaluation]] = field(default_factory=dict)
    definition_consumption: tuple[DefinitionConsumerConsumption, ...] = ()
    accepted: bool = field(default=False, init=False)


def _calculate_controls(frozen, control_input, control_selections, unverified_atom_reasons=None,
                        proposition_relations=(), proposition_pair_gaps=(), repeat_evaluations=None,
                        frequency_evaluations=None, computation_evaluations=None):
    publication = frozen.clause_pack.control_publication
    if publication is None or not publication.catalog.controls:
        if control_input is not None or control_selections:
            raise ValueError("本次审核没有补充要求，不能夹带其他方案的计算")
        return None
    if control_input is None or not isinstance(control_selections, Mapping):
        raise ValueError("本方案含跨章节要求，须同时提供其完整资料对应清单")
    control_input = ControlBindingFrozenInput.model_validate(control_input.model_dump(mode="json"))
    source = control_input.evidence_input
    expected_facts = sorted((_frozen_fact(item).model_dump(mode="json") for item in frozen.facts),
                            key=lambda item: item["fact_id"])
    supplied_facts = sorted((item.model_dump(mode="json") for item in source.facts),
                            key=lambda item: item["fact_id"])
    if (control_input.publication != publication
            or source.authority != frozen.authority
            or source.episode != frozen.review_episode
            or canonical_hash(expected_facts) != canonical_hash(supplied_facts)):
        raise ValueError("补充要求计算必须使用本次审核相同的方案、节点和完整事实集合")
    from app.services.control_judgment_gaps import missing_control_judgments

    reasons = {key: list(value) for key, value in (unverified_atom_reasons or {}).items()}
    for identity in missing_control_judgments(frozen, control_selections):
        reasons[identity] = sorted(set(reasons.get(identity, ())) | {"professional_judgment_missing"})
    return evaluate_control_layers_experiment(
        control_input, frozen_input_sha256=control_input.frozen_input_sha256,
        selections=control_selections,
        conflict_groups=frozen.conflict_groups,
        unverified_atom_reasons=reasons if reasons else unverified_atom_reasons,
        proposition_relations=proposition_relations,
        proposition_pair_gaps=proposition_pair_gaps,
        repeat_evaluations=repeat_evaluations,
        frequency_evaluations=frequency_evaluations,
        computation_evaluations=computation_evaluations,
    )


def _resolve_selection_inputs(
    *,
    predicate_fact_ids_by_component: Mapping[str, Mapping[str, Sequence[str]]] | None,
    control_input: ControlBindingFrozenInput | None,
    control_selections: Mapping[str, Sequence[str]] | None,
    qualified_binding_selections: ReceiptVerifiedQualifiedBindingSelections | Sequence[ReceiptVerifiedQualifiedBindingSelections] | None,
    frozen: ReviewContextSnapshotV2,
    rule_set: RuleSet,
) -> tuple[
    Mapping[str, Mapping[str, Sequence[str]]],
    ControlBindingFrozenInput | None,
    Mapping[str, Sequence[str]] | None,
]:
    """Accept either caller-built explicit maps or sealed receipt-verified selections."""
    if qualified_binding_selections is None:
        if predicate_fact_ids_by_component is None:
            raise ValueError("资料对应清单必须完整列出本次审核的每项条件")
        return predicate_fact_ids_by_component, control_input, control_selections
    if any(value is not None for value in (
        predicate_fact_ids_by_component, control_input, control_selections,
    )):
        raise ValueError("已核实的审核输入不能夹带手工资料选择")
    items = _qualification_inputs(qualified_binding_selections)
    by_family = {item.candidate_family: item for item in items}
    publication = frozen.clause_pack.control_publication
    expected = {"predicate"}
    if publication is not None and publication.catalog.controls:
        expected.add("control")
    if len(by_family) != len(items) or set(by_family) != expected:
        raise ValueError("须同时提供本次官方条款和补充要求的完整核实结果，不得重复或遗漏")
    for item in items:
        assert_qualified_selections_match_review_context(
            frozen_review=frozen, rule_set=rule_set, selections=item,
        )
    predicate_map = by_family["predicate"].predicate_fact_ids_by_component
    if predicate_map is None:
        raise ValueError("核实结果缺少官方条件清单")
    control = by_family.get("control")
    if control is not None and (control.control_input is None or control.control_selections is None):
        raise ValueError("核实结果缺少补充要求清单")
    return (predicate_map, None if control is None else control.control_input,
            None if control is None else control.control_selections)


def _qualification_inputs(value) -> tuple[ReceiptVerifiedQualifiedBindingSelections, ...]:
    if value is None:
        return ()
    if isinstance(value, ReceiptVerifiedQualifiedBindingSelections):
        return (value,)
    if (not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value
            or any(not isinstance(item, ReceiptVerifiedQualifiedBindingSelections) for item in value)):
        raise ValueError("资格选择须为已核实的官方条件或补充要求清单")
    return tuple(sorted(value, key=lambda item: item.candidate_family))


def _work_draft_inputs(value) -> tuple[ReceiptVerifiedWorkDraftSelections, ...]:
    if value is None:
        return ()
    if isinstance(value, ReceiptVerifiedWorkDraftSelections):
        return (value,)
    if (not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value
            or any(not isinstance(item, ReceiptVerifiedWorkDraftSelections) for item in value)):
        raise ValueError("工作稿资格选择须为回执已核实的官方条件或补充要求清单")
    return tuple(sorted(value, key=lambda item: item.candidate_family))


def _definition_records_for_review(
    publication: ControlCatalogPublication | None,
    supplied: Sequence[ProtocolControlDefinitionConsumerRecord] | None,
) -> Sequence[ProtocolControlDefinitionConsumerRecord] | None:
    if publication is None or publication.schema_version == "control-catalog/v1":
        return supplied
    if publication.schema_version not in {"control-catalog/v2", "control-catalog/v3"}:
        raise ValueError("补充要求的发布版本尚不能用于本次审核")
    published = publication.definition_consumer_records
    if supplied is not None and [
        ProtocolControlDefinitionConsumerRecord.model_validate(item).model_dump(mode="json")
        for item in supplied
    ] != [item.model_dump(mode="json") for item in published]:
        raise ValueError("来源定义消费关系与本次冻结发布版本不一致")
    return published


def _eligible_control_calculations(evaluated, definition_unverified):
    """A derived repeat/frequency result cannot settle an unverified definition."""
    return {
        identity: result for identity, result in evaluated.items()
        if identity not in definition_unverified
    }


def _withhold_unverified_definition_predicates(
    selections, derived_by_family, unverified, affected,
) -> None:
    """Remove only the consumers of unproven source definitions."""
    for component_id, predicate_ids in affected.items():
        choices = selections.get(component_id)
        if choices is None or any(predicate_id not in choices for predicate_id in predicate_ids):
            raise ValueError("来源定义消费条件不在本次审核的完整资料对应清单内")
        for predicate_id in predicate_ids:
            choices[predicate_id] = []
        for family in derived_by_family:
            evaluated = family.get(component_id)
            if evaluated is not None:
                for predicate_id in predicate_ids:
                    evaluated.pop(predicate_id, None)
        unverified[component_id] = frozenset(unverified.get(component_id, ())) | predicate_ids


def _definition_consumer_consumption(
    pack, rule_set: RuleSet, records,
) -> tuple[dict[str, frozenset[str]], dict[str, tuple[str, ...]], tuple[DefinitionConsumerConsumption, ...]]:
    """Turn saved definition→consumer relations into working-draft unknowns.

    Each consumer is resolved against the same frozen identities the
    publication path re-verified: an official predicate by its owning rule
    component and content-derived predicate id inside this ``rule_set``, a
    control atom by its originating candidate plus frozen atom position inside
    this review's control publication. A relation that does not resolve fails
    closed instead of being ignored, and only the listed consumers are marked;
    every sibling keeps its evidence-based status.
    """

    if records is None:
        return {}, {}, ()
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise ValueError("来源定义消费关系必须是已保存记录的完整清单")
    records = [ProtocolControlDefinitionConsumerRecord.model_validate(
        item.model_dump(mode="json") if hasattr(item, "model_dump") else item,
    ) for item in records]
    clause_components = {
        clause.rule_component_id for clause in [*pack.clauses, *pack.restricted_clauses]
    }
    predicates_by_component: dict[str, set[str]] = {}
    source_excerpts_by_predicate: dict[tuple[str, str], list[str]] = {}
    for rule in rule_set.rules:
        for component in rule.components:
            component_predicates = predicates_by_component.setdefault(
                component.rule_component_id, set(),
            )
            for expression in (component.expression, component.exception_expression,
                               *(item.expression for item in component.repeat_trigger_conditions)):
                if expression is None:
                    continue
                for predicate in iter_atomic_predicates(expression):
                    component_predicates.add(predicate.predicate_id)
                    source_excerpts_by_predicate[(
                        component.rule_component_id, predicate.predicate_id,
                    )] = list(predicate.exact_source_clauses)
    publication = pack.control_publication
    catalog = None if publication is None else publication.catalog
    controls_by_candidate: dict[str, str] = {}
    atom_identity_by_position: dict[tuple, str] = {}
    if catalog is not None:
        from app.projections.control_atom_binding_input import project_control_atom_identities

        controls_by_candidate = {
            control.originating_candidate_id: control.protocol_control_id
            for control in catalog.controls
        }
        atom_identity_by_position = {
            (identity.protocol_control_id, identity.layer, identity.condition_id,
             identity.group_index, identity.atom_index): identity.identity_sha256
            for identity in project_control_atom_identities(publication, include_repeat_triggers=True)
        }
    predicate_unverified: dict[str, frozenset[str]] = {}
    control_unverified: dict[str, tuple[str, ...]] = {}
    consumed: list[DefinitionConsumerConsumption] = []
    for record in records:
        record_predicates: list[tuple[str, str]] = []
        record_identities: list[str] = []
        for consumer in record.consumers:
            if consumer.consumer_kind == "official_predicate":
                if consumer.rule_component_id not in clause_components:
                    raise ValueError("来源定义消费条件不属于本次审核的冻结条款")
                if consumer.predicate_id not in predicates_by_component.get(
                    consumer.rule_component_id, set()
                ):
                    raise ValueError("来源定义消费条件未绑定当前冻结规则条件")
                excerpt = normalize_source_excerpt(consumer.consumer_excerpt)
                if not excerpt or not any(
                    excerpt in normalize_source_excerpt(value)
                    for value in source_excerpts_by_predicate[(
                        consumer.rule_component_id, consumer.predicate_id,
                    )]
                ):
                    raise ValueError("消费来源摘录不在该条件自身声明的冻结原文中")
                record_predicates.append(
                    (consumer.rule_component_id, consumer.predicate_id)
                )
            else:
                published_id = controls_by_candidate.get(consumer.control_candidate_id)
                if published_id is None:
                    raise ValueError("来源定义消费原子引用了非本次发布的补充要求")
                identity = atom_identity_by_position.get((
                    published_id, consumer.layer, consumer.condition_id,
                    consumer.group_index, consumer.atom_index,
                ))
                if identity is None:
                    raise ValueError("来源定义消费原子未绑定冻结控制原子位置")
                record_identities.append(identity)
        if not record_predicates and not record_identities:
            continue
        for rule_component_id, predicate_id in record_predicates:
            predicate_unverified[rule_component_id] = (
                predicate_unverified.get(rule_component_id, frozenset()) | {predicate_id}
            )
        for identity in record_identities:
            control_unverified[identity] = tuple(sorted({
                *control_unverified.get(identity, ()),
                DEFINITION_CONSUMER_UNVERIFIED_REASON,
            }))
        consumed.append(DefinitionConsumerConsumption(
            batch_id=record.batch_id,
            source_statement_index=record.source_statement_index,
            structure_unit_id=record.source_structure_unit_id,
            predicate_ids=tuple(sorted(record_predicates)),
            control_atom_identities=tuple(sorted(record_identities)),
        ))
    return predicate_unverified, control_unverified, tuple(consumed)


def calculate_frozen_review(
    frozen: ReviewContextSnapshotV2, rule_set: RuleSet,
    *,
    predicate_fact_ids_by_component: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
    control_input: ControlBindingFrozenInput | None = None,
    control_selections: Mapping[str, Sequence[str]] | None = None,
    qualified_binding_selections: ReceiptVerifiedQualifiedBindingSelections | Sequence[ReceiptVerifiedQualifiedBindingSelections] | None = None,
    work_draft_selections: ReceiptVerifiedWorkDraftSelections | Sequence[ReceiptVerifiedWorkDraftSelections] | None = None,
    definition_consumer_records: Sequence[ProtocolControlDefinitionConsumerRecord] | None = None,
) -> FrozenReviewCalculation:
    """Calculate explicit selections without category fallback or publication.

    The caller still has to verify the provenance and semantic qualification of
    these selections. This numerical result cannot establish that qualification.
    Every component and both trigger/exception atoms must be accounted for,
    including empty selections where no qualified evidence was established.

    ``qualified_binding_selections`` is an explicit alternative input produced only
    by the receipt-verified consumer under owning-service authorization. It does
    not enable clinical adoption or replace isolated evaluation / user approval.
    The pre-existing explicit-selection maps remain available and non-authoritative.

    New publications carry their verified definition relations in the same
    frozen catalog used by this review. Explicit records are retained for
    isolated diagnostics, but cannot override the published version.
    """
    frozen = ReviewContextSnapshotV2.model_validate(frozen.model_dump(mode="json"))
    if frozen.requirements_scope_version != "review-requirements-scope/v1":
        raise ValueError("原审核资料尚未核实方案要求是否齐全，请基于当前资料新建审核；历史记录不变")
    if (
        frozen.evaluator_version != EVALUATOR_VERSION
        or canonical_hash(rule_set.model_dump(mode="json")) != frozen.rule_set_sha256
    ):
        raise ValueError("规则内容或计算版本已变化，不能改算原审核记录")
    # The context validator verifies the stored pack; a newer projector must not
    # replace the clinical requirements frozen for this review.
    pack = frozen.clause_pack
    definition_consumer_records = _definition_records_for_review(
        pack.control_publication, definition_consumer_records,
    )
    has_restricted_controls = bool(
        pack.control_publication is not None
        and pack.control_publication.catalog.restricted_statements
    )
    if (pack.restricted_clauses or has_restricted_controls) and work_draft_selections is None:
        raise ValueError("本版方案仍含有源未决要求，不能按旧版完整签发路径计算")
    (
        definition_predicate_unverified,
        definition_control_unverified,
        definition_consumption,
    ) = _definition_consumer_consumption(pack, rule_set, definition_consumer_records)
    component_ids = {clause.rule_component_id for clause in pack.clauses}
    draft_items = _work_draft_inputs(work_draft_selections)
    formal_items = _qualification_inputs(qualified_binding_selections)
    if draft_items:
        if (qualified_binding_selections is not None
                or any(value is not None for value in (
                    predicate_fact_ids_by_component, control_input, control_selections,
                ))):
            raise ValueError("工作稿选择不能夹带正式授权或手工资料选择")
        by_family = {item.candidate_family: item for item in draft_items}
        expected_families = {"predicate"}
        if pack.control_publication is not None and pack.control_publication.catalog.controls:
            expected_families.add("control")
        if len(by_family) != len(draft_items) or set(by_family) != expected_families:
            raise ValueError("工作稿须同时包含本次官方条款和补充要求的完整核对结果")
        for item in draft_items:
            assert_receipt_verified_selections_match_review_context(
                frozen_review=frozen, rule_set=rule_set, selections=item,
            )
        predicate_fact_ids_by_component = by_family["predicate"].predicate_fact_ids_by_component
        control = by_family.get("control")
        control_input = None if control is None else control.control_input
        control_selections = None if control is None else control.control_selections
    else:
        (
            predicate_fact_ids_by_component,
            control_input,
            control_selections,
        ) = _resolve_selection_inputs(
            predicate_fact_ids_by_component=predicate_fact_ids_by_component,
            control_input=control_input,
            control_selections=control_selections,
            qualified_binding_selections=qualified_binding_selections,
            frozen=frozen,
            rule_set=rule_set,
        )
    if (not isinstance(predicate_fact_ids_by_component, Mapping)
            or set(predicate_fact_ids_by_component) != component_ids
            or any(not isinstance(value, Mapping)
                   for value in predicate_fact_ids_by_component.values())):
        raise ValueError("资料对应清单必须完整列出本次审核的每项条件")
    control_unverified = None
    control_relations = ()
    control_pair_gaps = ()
    control_ordering = {}
    for item in draft_items:
        if item.candidate_family == "control":
            final_identities = set(item.control_selections or {})
            control_ordering = {
                outcome.identity_sha256: outcome.observation_ordering
                for outcome in item.identity_outcomes
                if outcome.observation_ordering is not None
                and outcome.identity_sha256 in final_identities
            }
            control_unverified = {
                outcome.identity_sha256: tuple(outcome.unresolved_reasons)
                for outcome in item.identity_outcomes
                if outcome.status == "unresolved"
                and outcome.identity_sha256 in final_identities
            }
            control_relations = [
                relation for relation in item.proposition_relations
                if relation["identity_sha256"] in final_identities
            ]
            control_pair_gaps = [
                gap for gap in item.unresolved_proposition_pairs
                if gap["identity_sha256"] in final_identities
            ]
    for item in formal_items:
        if item.candidate_family == "control":
            final_identities = set(item.control_selections or {})
            control_ordering = {outcome.identity_sha256: outcome.observation_ordering
                                for outcome in item.material.identity_outcomes
                                if outcome.observation_ordering is not None
                                and outcome.identity_sha256 in final_identities}
            control_relations = [relation for relation in item.material.proposition_relations
                                 if relation["identity_sha256"] in final_identities]
            control_pair_gaps = [gap for gap in item.material.unresolved_proposition_pairs
                                 if gap["identity_sha256"] in final_identities]
            control_unverified = {outcome.identity_sha256: tuple(outcome.unresolved_reasons)
                                  for outcome in item.material.identity_outcomes
                                  if outcome.status == "unresolved"
                                  and outcome.identity_sha256 in final_identities}
    if definition_control_unverified:
        control_unverified = {**(control_unverified or {})}
        for identity, reasons in definition_control_unverified.items():
            control_unverified[identity] = tuple(sorted({
                *control_unverified.get(identity, ()), *reasons,
            }))
    facts = list(frozen.facts)
    links_by_fact = {}
    for link in frozen.fact_rule_links:
        links_by_fact.setdefault(link.fact_id, []).append(link)
    conflicts, conflict_by_fact = _phase3_conflict_groups(
        None, frozen.authority, facts, clauses=pack.clauses,
        current_groups=list(frozen.conflict_groups), frozen_links_by_fact=links_by_fact,
    )
    adapted = adapt_clinical_facts_v2(facts, conflict_group_by_fact=conflict_by_fact)
    authority = frozen.authority
    context = EvaluationContext(
        project_id=authority.project_id, subject_id=authority.subject_id,
        review_episode_id=authority.review_episode_id,
        evidence_snapshot_id=authority.evidence_snapshot_v2_id,
        accepted_fact_ids=[item.fact_id for item in adapted], facts=adapted,
        anchor_dates=dict(frozen.review_episode.anchor_dates),
    )
    calculation_items = draft_items or formal_items
    repeat_condition_calculations = []
    for item in calculation_items:
        if item.candidate_family == "predicate":
            from app.services.repeat_trigger_calculation import calculate_repeat_trigger_conditions
            repeat_results = calculate_repeat_trigger_conditions(item, context)
        else:
            from app.projections.control_repeat_trigger_calculation import calculate_control_repeat_triggers
            repeat_results = calculate_control_repeat_triggers(item, conflict_groups=frozen.conflict_groups, context=context)
        repeat_condition_calculations.extend({
            **asdict(value), "result": value.result.model_dump(mode="json"), "family": item.candidate_family,
        } for value in repeat_results)
    from app.services.repeat_result_resolution import resolve_repeat_result_selection
    repeat_result_resolutions = tuple(
        value for item in calculation_items
        for value in resolve_repeat_result_selection(item, repeat_condition_calculations)
    )
    from app.services.repeat_atom_calculation import calculate_repeat_atoms
    repeat_atom_evaluations = {
        item.candidate_family: calculate_repeat_atoms(item, context, repeat_result_resolutions)
        for item in calculation_items
    }
    repeat_by_component = {}
    control_repeat_for_review = {}
    predicate_fact_ids_by_component = {
        parent: {key: list(values) for key, values in choices.items()}
        for parent, choices in predicate_fact_ids_by_component.items()
    }
    for item in calculation_items:
        evaluated = repeat_atom_evaluations[item.candidate_family]
        if item.candidate_family == "predicate":
            for component in item.predicate_frozen_input.components:
                for entry in (*component.trigger_predicates, *component.exception_predicates):
                    value = evaluated.get(entry.predicate_identity_sha256)
                    if value is not None:
                        repeat_by_component.setdefault(component.rule_component_id, {})[entry.predicate_id] = value
                        predicate_fact_ids_by_component[component.rule_component_id][entry.predicate_id] = list(value.result.used_fact_ids)
        elif evaluated:
            control_repeat_for_review = _eligible_control_calculations(
                evaluated, definition_control_unverified,
            )
            control_selections = {key: list(values) for key, values in control_selections.items()}
            control_unverified = {key: values for key, values in (control_unverified or {}).items() if key not in control_repeat_for_review}
            control_relations = [row for row in control_relations if row["identity_sha256"] not in control_repeat_for_review]
            control_pair_gaps = [row for row in control_pair_gaps if row["identity_sha256"] not in control_repeat_for_review]
            for observation in item.material.observation_relations:
                key = observation["identity_sha256"]
                if key not in control_repeat_for_review:
                    continue
                chosen = list(control_repeat_for_review[key].result.used_fact_ids)
                control_selections[key] = chosen
                control_relations.extend(row for row in observation["result_sources"]["proposition_relations"]
                                         if row["fact_id"] in chosen)
                control_pair_gaps.extend(observation["result_sources"]["proposition_pair_gaps"])
    from app.services.frequency_atom_calculation import calculate_frequency_atoms
    frequency_atom_evaluations = {
        item.candidate_family: calculate_frequency_atoms(item, context)
        for item in calculation_items
    }
    frequency_by_component = {}
    control_frequency_for_review = {}
    for item in calculation_items:
        evaluated = frequency_atom_evaluations[item.candidate_family]
        if item.candidate_family == "predicate":
            for component in item.predicate_frozen_input.components:
                for entry in (*component.trigger_predicates, *component.exception_predicates):
                    value = evaluated.get(entry.predicate_identity_sha256)
                    if value is not None:
                        frequency_by_component.setdefault(component.rule_component_id, {})[entry.predicate_id] = value
                        predicate_fact_ids_by_component[component.rule_component_id][entry.predicate_id] = list(value.result.used_fact_ids)
        elif evaluated:
            control_frequency_for_review = _eligible_control_calculations(
                evaluated, definition_control_unverified,
            )
            control_selections = {key: list(values) for key, values in control_selections.items()}
            control_unverified = {key: values for key, values in (control_unverified or {}).items() if key not in control_frequency_for_review}
            control_relations = [row for row in control_relations if row["identity_sha256"] not in control_frequency_for_review]
            control_pair_gaps = [row for row in control_pair_gaps if row["identity_sha256"] not in control_frequency_for_review]
            for key, value in control_frequency_for_review.items():
                control_selections[key] = list(value.result.used_fact_ids)
    from app.services.computation_atom_calculation import calculate_computation_atoms
    computation_atom_evaluations = {
        item.candidate_family: calculate_computation_atoms(item, context)
        for item in calculation_items
    }
    computation_by_component = {}
    control_computation_for_review = {}
    for item in calculation_items:
        evaluated = computation_atom_evaluations[item.candidate_family]
        if item.candidate_family == "predicate":
            for component in item.predicate_frozen_input.components:
                for entry in (*component.trigger_predicates, *component.exception_predicates):
                    value = evaluated.get(entry.predicate_identity_sha256)
                    if value is not None:
                        computation_by_component.setdefault(component.rule_component_id, {})[entry.predicate_id] = value
                        predicate_fact_ids_by_component[component.rule_component_id][entry.predicate_id] = list(value.result.used_fact_ids)
        else:
            control_computation_for_review = _eligible_control_calculations(evaluated, definition_control_unverified)
            control_selections = {key: list(values) for key, values in control_selections.items()}
            control_unverified = {key: values for key, values in (control_unverified or {}).items()
                                  if key not in control_computation_for_review}
            control_relations = [row for row in control_relations
                                 if row["identity_sha256"] not in control_computation_for_review]
            control_pair_gaps = [row for row in control_pair_gaps
                                 if row["identity_sha256"] not in control_computation_for_review]
            for key, value in control_computation_for_review.items():
                control_selections[key] = list(value.result.used_fact_ids)
    if definition_control_unverified:
        if not isinstance(control_selections, Mapping):
            raise ValueError("来源定义消费原子缺少本次审核的补充要求资料对应清单")
        control_selections = {key: list(values) for key, values in control_selections.items()}
        for identity in definition_control_unverified:
            if identity not in control_selections:
                raise ValueError("来源定义消费原子不在本次审核的完整资料对应清单内")
            control_selections[identity] = []
    controls = _calculate_controls(frozen, control_input, control_selections, control_unverified,
                                   control_relations, control_pair_gaps, control_repeat_for_review,
                                   control_frequency_for_review, control_computation_for_review)
    templates = {item.template_id: item for item in frozen.expectation_templates}
    templates_by_requirement = {item.requirement_id: item for item in templates.values()}
    expectations = _expectation_views(frozen.expectations, templates)
    summaries = {item.summary.requirement_id: item.summary for item in frozen.judgment_search_results}
    unverified_by_component = {}
    proposition_by_component = {}
    for item in calculation_items:
        if item.candidate_family != "predicate":
            continue
        from app.services.predicate_proposition_calculation import calculate_predicate_propositions
        proposition_by_component = calculate_predicate_propositions(item, context)
        for parent, evaluated in repeat_by_component.items():
            for key in evaluated:
                proposition_by_component.get(parent, {}).pop(key, None)
        for parent, evaluated in frequency_by_component.items():
            for key in evaluated:
                proposition_by_component.get(parent, {}).pop(key, None)
        for parent, evaluated in computation_by_component.items():
            for key in evaluated:
                proposition_by_component.get(parent, {}).pop(key, None)
        unresolved = {
            outcome.identity_sha256 for outcome in item.material.identity_outcomes
            if outcome.status == "unresolved"
        }
        for component in item.predicate_frozen_input.components:
            unverified_by_component[component.rule_component_id] = frozenset(
                predicate.predicate_id
                for predicate in (*component.trigger_predicates, *component.exception_predicates)
                if predicate.predicate_identity_sha256 in unresolved
                and predicate.predicate_id not in repeat_by_component.get(component.rule_component_id, {})
                and predicate.predicate_id not in frequency_by_component.get(component.rule_component_id, {})
                and predicate.predicate_id not in computation_by_component.get(component.rule_component_id, {})
            )
    # A consumer of an unproven source definition cannot keep its evidence
    # result: its selection is cleared and it is marked unverified. Siblings are
    # never touched, so an unaffected predicate keeps its real status. The
    # evaluator only accepts an unverified atom with an explicitly empty
    # selection, so any repeat / frequency / proposition result for it must be
    # dropped as well instead of being carried past the unverified state.
    _withhold_unverified_definition_predicates(
        predicate_fact_ids_by_component,
        (proposition_by_component, repeat_by_component, frequency_by_component, computation_by_component),
        unverified_by_component, definition_predicate_unverified,
    )
    result = []
    verified_judgment_requirements = frozenset(
        requirement for item in calculation_items
        for requirement in item.material.verified_judgment_requirement_ids
    )
    for clause in pack.clauses:
        component = clause_to_rule_component(clause)
        judgment_gaps = _summary_gap_requirements(
            clause, episode_stage=frozen.review_episode.stage, summaries=summaries,
            templates_by_requirement=templates_by_requirement, expectations=expectations,
            workflow_stage_id=frozen.review_episode.workflow_stage_id,
        )
        verified_for_clause = verified_judgment_requirements & {
            item.requirement_id for item in clause.evidence_requirements
        }
        judgment_gaps = {key: value for key, value in judgment_gaps.items() if key not in verified_for_clause}
        choices = predicate_fact_ids_by_component[clause.rule_component_id]
        calculated = calculate_component_review(
            component=component, rule_kind=clause.kind,
            context=context, episode_stage=frozen.review_episode.stage,
            predicate_fact_ids=choices,
            proposition_evaluations=proposition_by_component.get(clause.rule_component_id),
            repeat_evaluations=repeat_by_component.get(clause.rule_component_id),
            frequency_evaluations=frequency_by_component.get(clause.rule_component_id),
            computation_evaluations=computation_by_component.get(clause.rule_component_id),
            unverified_predicate_ids=unverified_by_component.get(clause.rule_component_id, frozenset()),
            missing_judgment_predicate_ids=missing_judgment_predicates(
                component, judgment_gaps, choices,
                episode_stage=frozen.review_episode.stage,
                workflow_stage_id=frozen.review_episode.workflow_stage_id,
                requirement_workflow_stage_ids={key: item.workflow_stage_id
                                              for key, item in templates_by_requirement.items()},
            ),
            judgment_gap_by_requirement=judgment_gaps,
            verified_judgment_requirement_ids=frozenset(verified_for_clause),
            expectations=expectations, conflicts=conflicts,
            workflow_stage_id=frozen.review_episode.workflow_stage_id,
            requirement_workflow_stage_ids={key: item.workflow_stage_id
                                          for key, item in templates_by_requirement.items()},
        )
        result.append(FrozenComponentCalculation(clause.rule_component_id, frozen.context_sha256, calculated))
    selection_payload = {
        "evaluator_version": EVALUATOR_VERSION,
        "context_sha256": frozen.context_sha256,
        "components": {
            component_id: {predicate_id: sorted(values) for predicate_id, values in choices.items()}
            for component_id, choices in predicate_fact_ids_by_component.items()
        },
        "controls": controls.selections_sha256 if controls is not None else None,
    }
    if calculation_items:
        if any(computation_atom_evaluations.values()):
            selection_payload["computation_atom_evaluations"] = {
                family: {key: value.model_dump(mode="json") for key, value in items.items()}
                for family, items in computation_atom_evaluations.items()
            }
        selection_payload["repeat_condition_calculations"] = repeat_condition_calculations
        selection_payload["frequency_atom_evaluations"] = {
            family: {key: value.model_dump(mode="json") for key, value in items.items()}
            for family, items in frequency_atom_evaluations.items()
        }
        selection_payload["repeat_result_resolutions"] = repeat_result_resolutions
        selection_payload["repeat_atom_evaluations"] = {
            family: {key: value.model_dump(mode="json") for key, value in items.items()}
            for family, items in repeat_atom_evaluations.items()
        }
        selection_payload["qualification_gap_policy_version"] = "unverified-predicate/v2"
        if formal_items:
            selection_payload["qualified_binding_selections"] = [
                {"family": item.candidate_family,
                 "selection_sha256": item.material.selection_sha256,
                 "frozen_input_sha256": item.material.frozen_input_sha256}
                for item in formal_items
            ]
    if draft_items:
        selection_payload["work_draft_policy_version"] = "receipt-verified-work-draft/v1"
        selection_payload["work_draft_selections"] = [
            {
                "family": item.candidate_family,
                "selection_sha256": item.selection_sha256,
                "frozen_input_sha256": item.frozen_input_sha256,
            }
            for item in draft_items
        ]
    if definition_consumption:
        # The consumed relation is part of the calculation identity, so a later
        # comparison cannot read this result as one computed without it.
        selection_payload["definition_consumption"] = [
            {
                "batch_id": item.batch_id,
                "source_statement_index": item.source_statement_index,
                "structure_unit_id": item.structure_unit_id,
                "predicate_ids": [list(pair) for pair in item.predicate_ids],
                "control_atom_identities": list(item.control_atom_identities),
            }
            for item in definition_consumption
        ]
    return FrozenReviewCalculation(
        context_sha256=frozen.context_sha256,
        selections_sha256=canonical_hash(selection_payload),
        components=tuple(result), controls=controls,
        repeat_condition_calculations=tuple(repeat_condition_calculations),
        repeat_result_resolutions=repeat_result_resolutions,
        repeat_atom_evaluations=repeat_atom_evaluations,
        frequency_atom_evaluations=frequency_atom_evaluations,
        computation_atom_evaluations=computation_atom_evaluations,
        qualification_materials=tuple(
            item.material.model_copy(deep=True)
            for item in formal_items
        ),
        control_outcomes=(project_control_review_outcomes(control_input, controls, observation_ordering=control_ordering)
                          if controls is not None else ()),
        definition_consumption=definition_consumption,
    )
