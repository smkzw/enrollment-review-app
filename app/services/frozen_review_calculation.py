"""Calculate a frozen review with the workbench evaluator, without publishing it."""
from dataclasses import asdict, dataclass, field
from collections.abc import Mapping, Sequence

from app.domain.contracts.control_atom_binding import ControlBindingFrozenInput
from app.domain.contracts.review_context_v2 import ReviewContextSnapshotV2
from app.domain.contracts.rules import RuleSet
from app.domain.contracts.qualified_binding_selection import QualifiedBindingSelectionMaterial
from app.domain.expression import EvaluationContext, RepeatAtomEvaluation
from app.domain.contracts.evaluation_result import FrequencyAtomEvaluation
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

EVALUATOR_VERSION = "component-review/v35"


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
    accepted: bool = field(default=False, init=False)


def _calculate_controls(frozen, control_input, control_selections, unverified_atom_reasons=None,
                        proposition_relations=(), proposition_pair_gaps=(), repeat_evaluations=None,
                        frequency_evaluations=None):
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


def calculate_frozen_review(
    frozen: ReviewContextSnapshotV2, rule_set: RuleSet,
    *,
    predicate_fact_ids_by_component: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
    control_input: ControlBindingFrozenInput | None = None,
    control_selections: Mapping[str, Sequence[str]] | None = None,
    qualified_binding_selections: ReceiptVerifiedQualifiedBindingSelections | Sequence[ReceiptVerifiedQualifiedBindingSelections] | None = None,
    work_draft_selections: ReceiptVerifiedWorkDraftSelections | Sequence[ReceiptVerifiedWorkDraftSelections] | None = None,
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
            control_selections = {key: list(values) for key, values in control_selections.items()}
            control_unverified = {key: values for key, values in (control_unverified or {}).items() if key not in evaluated}
            control_relations = [row for row in control_relations if row["identity_sha256"] not in evaluated]
            control_pair_gaps = [row for row in control_pair_gaps if row["identity_sha256"] not in evaluated]
            for observation in item.material.observation_relations:
                key = observation["identity_sha256"]
                chosen = list(evaluated[key].result.used_fact_ids)
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
            control_selections = {key: list(values) for key, values in control_selections.items()}
            control_unverified = {key: values for key, values in (control_unverified or {}).items() if key not in evaluated}
            control_relations = [row for row in control_relations if row["identity_sha256"] not in evaluated]
            control_pair_gaps = [row for row in control_pair_gaps if row["identity_sha256"] not in evaluated]
            for key, value in evaluated.items():
                control_selections[key] = list(value.result.used_fact_ids)
    controls = _calculate_controls(frozen, control_input, control_selections, control_unverified,
                                   control_relations, control_pair_gaps, repeat_atom_evaluations.get("control"),
                                   frequency_atom_evaluations.get("control"))
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
    return FrozenReviewCalculation(
        context_sha256=frozen.context_sha256,
        selections_sha256=canonical_hash(selection_payload),
        components=tuple(result), controls=controls,
        repeat_condition_calculations=tuple(repeat_condition_calculations),
        repeat_result_resolutions=repeat_result_resolutions,
        repeat_atom_evaluations=repeat_atom_evaluations,
        frequency_atom_evaluations=frequency_atom_evaluations,
        qualification_materials=tuple(
            item.material.model_copy(deep=True)
            for item in formal_items
        ),
        control_outcomes=(project_control_review_outcomes(control_input, controls, observation_ordering=control_ordering)
                          if controls is not None else ()),
    )
