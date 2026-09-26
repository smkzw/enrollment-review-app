"""Isolated consumption of explicit selections; not semantic acceptance."""
from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import Field, model_serializer, model_validator

from app.domain.contracts.common import ContractModel
from app.domain.contracts.control_atom_binding import ControlBindingFrozenInput
from app.domain.contracts.enums import TruthValue
from app.domain.contracts.evaluation_result import FrequencyAtomEvaluation
from app.domain.contracts.facts import ClinicalConflictGroupV2
from app.domain.contracts.proposition_evidence import PropositionPairGap, ProspectiveEvidenceCheck
from app.domain.control_layer_evaluation import ControlLayerEvaluation, compose_control_layers
from app.domain.publication import canonical_hash
from app.domain.expression import RepeatAtomEvaluation
from app.domain.proposition_observations import (
    combine_observations, scope_supported as _scope_supported,
    universal_statement as _universal_statement,
)
from app.projections.control_atom_binding_input import project_control_atom_identities
from app.projections.control_operand_calculation import (
    ControlOperandCalculation, calculate_control_operands,
)


class ControlConditionalObservation(ContractModel):
    fact_id: str
    truth: TruthValue
    reason_codes: list[str]


class ControlCalculationExperiment(ContractModel):
    version: Literal["control-calculation-experiment/v3", "control-calculation-experiment/v4", "control-calculation-experiment/v5", "control-calculation-experiment/v6", "control-calculation-experiment/v7", "control-calculation-experiment/v8", "control-calculation-experiment/v9", "control-calculation-experiment/v10", "control-calculation-experiment/v11", "control-calculation-experiment/v12", "control-calculation-experiment/v13", "control-calculation-experiment/v14", "control-calculation-experiment/v15"] = "control-calculation-experiment/v15"
    frozen_input_sha256: str
    selections_sha256: str
    accepted: Literal[False] = False
    purpose: Literal["four_layer", "auxiliary_repeat_trigger"] = "four_layer"
    layers: list[ControlLayerEvaluation]
    calculations: list[ControlOperandCalculation]
    observations: dict[str, list[ControlConditionalObservation]] = Field(default_factory=dict)
    unresolved_atoms: dict[str, list[str]] = Field(default_factory=dict)
    source_conflicts: dict[str, list[str]] = Field(default_factory=dict)
    observation_scopes: dict[str, bool] = Field(default_factory=dict)
    proposition_pair_gaps: list[PropositionPairGap] = Field(default_factory=list)
    repeat_evaluations: dict[str, RepeatAtomEvaluation] = Field(default_factory=dict)
    frequency_evaluations: dict[str, FrequencyAtomEvaluation] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_repeat_scope(self):
        if self.repeat_evaluations and (self.version not in {"control-calculation-experiment/v11", "control-calculation-experiment/v12", "control-calculation-experiment/v13", "control-calculation-experiment/v14", "control-calculation-experiment/v15"} or self.purpose != "four_layer"):
            raise ValueError("旧计算或复查触发条件不能夹带新的最终复查求值")
        if self.frequency_evaluations and (self.version not in {"control-calculation-experiment/v12", "control-calculation-experiment/v13", "control-calculation-experiment/v14", "control-calculation-experiment/v15"}
                or (self.version == "control-calculation-experiment/v12" and self.purpose != "four_layer")):
            raise ValueError("频次计算须使用当前完整审核，不能补写历史")
        return self

    @model_serializer(mode="wrap")
    def preserve_four_layer_material(self, handler):
        value = handler(self)
        if self.purpose == "four_layer":
            value.pop("purpose", None)
        if not self.repeat_evaluations:
            value.pop("repeat_evaluations", None)
        if not self.frequency_evaluations:
            value.pop("frequency_evaluations", None)
        return value


def _conditional_truth(atom, observations, *, scope_verified=False, universal_facts=frozenset(),
                       individual_facts=None, universal_ready=False):
    """Aggregate only by source-declared policy over the supplied selections."""
    spec = atom.evaluation
    if spec is None:
        return TruthValue.UNKNOWN, ["semantic_evidence_unverified"]
    return combine_observations(
        spec.observation_policy, observations,
        deterministic=spec.determination_mode == "deterministic",
        scope_verified=scope_verified, universal_facts=universal_facts,
        individual_facts=individual_facts, universal_ready=universal_ready,
    )


def _proposition_observation(atom, records, calculation):
    spec = atom.evaluation
    if spec is None or not records:
        return TruthValue.UNKNOWN, ["semantic_evidence_unverified"]
    if getattr(atom, "prospective_period", None) is not None:
        period_reasons = []
        for record in records:
            lanes = record.get("lanes", {})
            if set(lanes) != {"main-A", "main-B"}:
                return TruthValue.UNKNOWN, ["prospective_statement_period_unverified"]
            for lane in lanes.values():
                future = lane.get("prospective_evidence")
                if future is None:
                    period_reasons.append("prospective_statement_period_unverified")
                else:
                    period_reasons.extend(ProspectiveEvidenceCheck.model_validate(future).unresolved_codes())
        if period_reasons:
            return TruthValue.UNKNOWN, sorted(set(period_reasons))
    if spec.time_purpose == "unresolved":
        return TruthValue.UNKNOWN, ["semantic_observation_time_unverified"]
    if atom.time_constraint is not None:
        if calculation.unresolved_reason or calculation.time_result is None:
            return TruthValue.UNKNOWN, ["semantic_observation_time_unverified"]
        temporal = calculation.time_result
        if temporal.truth == TruthValue.UNKNOWN:
            return TruthValue.UNKNOWN, list(temporal.reason_codes)
        if spec.time_purpose == "source_validity":
            if spec.observation_policy is None or spec.observation_policy.mode != "single":
                return TruthValue.UNKNOWN, ["source_validity_policy_unverified"]
            if temporal.truth == TruthValue.FALSE:
                return TruthValue.UNKNOWN, ["source_outside_validity_window"]
        if spec.time_purpose == "event_membership" and temporal.truth == TruthValue.FALSE:
            return TruthValue.UNKNOWN, ["observation_out_of_window"]
        if spec.time_purpose == "interval_condition" and temporal.truth == TruthValue.FALSE:
            return TruthValue.UNKNOWN, ["interval_condition_requires_scope_review"]
    if spec.observation_policy is not None and spec.observation_policy.mode == "single" and not _scope_supported(records):
        return TruthValue.UNKNOWN, ["observation_scope_completeness_unverified"]
    relations = {record["status"] for record in records}
    if len(relations) != 1:
        return TruthValue.UNKNOWN, ["proposition_relation_conflict"]
    if atom.time_constraint is not None and calculation.time_result.truth == TruthValue.FALSE:
        return TruthValue.FALSE, list(calculation.time_result.reason_codes)
    notes = (["prospective_statement_verified"]
             if getattr(atom, "prospective_period", None) is not None else [])
    return (TruthValue.TRUE if relations == {"entails_agreed"} else TruthValue.FALSE), notes


def _conditional_observation(atom, item):
    """Interpret time by its declared role, never by obligation category."""
    spec = atom.evaluation
    if item.unresolved_reason:
        return TruthValue.UNKNOWN, [item.unresolved_reason]
    temporal = item.time_result
    if spec.time_purpose == "source_validity":
        if spec.observation_policy is None or spec.observation_policy.mode != "single":
            return TruthValue.UNKNOWN, ["source_validity_policy_unverified"]
        if temporal is None:
            return TruthValue.UNKNOWN, ["time_calculation_missing"]
        # Freshness qualifies a clinical value; an expired source does not prove
        # that the value fails its threshold. A time-only proposition is separate.
        if spec.operation == "value_comparison" and temporal.truth == TruthValue.FALSE:
            return TruthValue.UNKNOWN, ["source_outside_validity_window"]
    if temporal is not None:
        if temporal.truth == TruthValue.UNKNOWN:
            return TruthValue.UNKNOWN, list(temporal.reason_codes)
        if temporal.truth == TruthValue.FALSE and spec.time_purpose == "event_membership":
            return TruthValue.UNKNOWN, ["observation_out_of_window"]
    if spec.operation == "time_constraint":
        if temporal is None:
            return TruthValue.UNKNOWN, ["time_calculation_missing"]
        return temporal.truth, list(temporal.reason_codes)
    value = item.value_result
    if value is None:
        return TruthValue.UNKNOWN, ["value_calculation_missing"]
    if atom.time_constraint is not None and temporal is None:
        return TruthValue.UNKNOWN, ["time_calculation_missing"]
    if temporal is not None and temporal.truth == TruthValue.FALSE:
        return TruthValue.FALSE, list(temporal.reason_codes)
    return value.truth, list(value.reason_codes)


def _evaluate_control_selection(
    frozen: ControlBindingFrozenInput, *, frozen_input_sha256: str,
    selections: Mapping[str, Sequence[str]],
    conflict_groups: Sequence[ClinicalConflictGroupV2] = (),
    unverified_atom_reasons: Mapping[str, Sequence[str]] | None = None,
    proposition_relations: Sequence[dict] = (),
    proposition_pair_gaps: Sequence[dict] = (),
    repeat_triggers_only: bool = False,
    repeat_evaluations: Mapping[str, RepeatAtomEvaluation] | None = None,
    frequency_evaluations: Mapping[str, FrequencyAtomEvaluation] | None = None,
) -> tuple[ControlCalculationExperiment, dict[str, dict[str, TruthValue]]]:
    """Consume an explicit full atom selection, with no category fallback.

    This entry records conditional arithmetic, not proof of the selections.
    It is shared with frozen whole-review calculation, but is not registered as
    a publication route. Semantic verification and approval of automatic
    correspondence remain separate.
    ANY/ALL concern only the supplied set: the caller's selection does not prove
    complete coverage of the protocol's population, interval or repeat visits.
    """
    frozen = ControlBindingFrozenInput.model_validate(frozen.model_dump(mode="json"))
    if frozen.frozen_input_sha256 != frozen_input_sha256:
        raise ValueError("资料或方案已变化，不能沿用原选择清单")
    identities = project_control_atom_identities(
        frozen.publication, include_repeat_triggers=repeat_triggers_only,
    )
    if repeat_triggers_only:
        identities = [item for item in identities if item.layer == "repeat_trigger"]
    if (not isinstance(selections, Mapping)
            or set(selections) != {item.identity_sha256 for item in identities}):
        raise ValueError("须逐项提供完整的控制原子选择清单，未找到资料时保留空清单")
    chosen = {}
    for key, values in selections.items():
        if (not isinstance(values, Sequence) or isinstance(values, (str, bytes))
                or any(not isinstance(value, str) for value in values)
                or len(values) != len(set(values))):
            raise ValueError("每个原子的事实选择须为无重复清单")
        chosen[key] = sorted(values)
    repeat_evaluations = dict(repeat_evaluations or {})
    repeat_atoms = {item.identity_sha256: item.atom for item in identities
                    if item.atom.evaluation is not None and item.atom.evaluation.repeat_scheme is not None}
    if repeat_evaluations:
        if repeat_triggers_only or not set(repeat_evaluations) <= set(repeat_atoms):
            raise ValueError("复查求值只能用于本次原方案的复查结果条件")
        available = {item.fact_id for item in frozen.evidence_input.facts}
        for key, item in repeat_evaluations.items():
            if (not isinstance(item, RepeatAtomEvaluation) or item.context_sha256 != frozen.frozen_input_sha256
                    or item.atom_sha256 != canonical_hash(repeat_atoms[key].model_dump(mode="json"))
                    or not set(item.source_fact_ids) <= available
                    or set(item.result.used_fact_ids) != set(chosen[key])):
                raise ValueError("补充要求的复查求值与本次方案或所选原件不一致")
    frequency_evaluations = dict(frequency_evaluations or {})
    frequency_atoms = {item.identity_sha256: item.atom for item in identities
                       if item.atom.evaluation is not None
                       and item.atom.evaluation.determination_mode == "deterministic"
                       and item.atom.evaluation.predicate is not None
                       and item.atom.evaluation.predicate.occurrence_window is not None
                       and item.atom.evaluation.repeat_scheme is None
                       and not item.atom.requires_professional_judgment}
    if frequency_evaluations:
        if (not set(frequency_evaluations) <= set(frequency_atoms)
                or set(frequency_evaluations) & set(repeat_evaluations)):
            raise ValueError("频次计算只能用于本次原方案的频次条件")
        available = {item.fact_id for item in frozen.evidence_input.facts}
        for key, item in frequency_evaluations.items():
            if (not isinstance(item, FrequencyAtomEvaluation)
                    or item.context_sha256 != frozen.frozen_input_sha256
                    or item.atom_sha256 != canonical_hash(frequency_atoms[key].model_dump(mode="json"))
                    or not set(item.source_fact_ids) <= available
                    or set(item.result.used_fact_ids) != set(chosen[key])):
                raise ValueError("频次计算与本次方案或所选原件不一致")
    relation_pairs = set()
    by_observation = {}
    for record in proposition_relations:
        identity, fact_id, pair_id = (record.get(key) for key in ("identity_sha256", "fact_id", "pair_id"))
        if (identity not in chosen or fact_id not in chosen[identity]
                or not isinstance(pair_id, str) or not pair_id or pair_id in relation_pairs
                or record.get("scope") != "pair_local"
                or record.get("status") not in {"entails_agreed", "contradicts_agreed"}):
            raise ValueError("原文关系必须逐项对应本次已核实的资料选择")
        relation_pairs.add(pair_id)
        by_observation.setdefault((identity, fact_id), []).append(record)
    gaps = [PropositionPairGap.model_validate(item) for item in proposition_pair_gaps]
    fact_by_id = {item.fact_id: item for item in frozen.evidence_input.facts}
    gap_pairs = set()
    semantic_identities = {item.identity_sha256 for item in identities if item.atom.evaluation is not None
                           and item.atom.evaluation.determination_mode != "deterministic"}
    for gap in gaps:
        fact = fact_by_id.get(gap.fact_id)
        if (gap.identity_sha256 not in semantic_identities or fact is None
                or gap.locator_id not in fact.locator_ids
                or gap.pair_id in relation_pairs or gap.pair_id in gap_pairs
                or any(not reason.strip() for reason in gap.reasons)):
            raise ValueError("原文核实疑问须逐项对应本次资料、原文位置和要求")
        gap_pairs.add(gap.pair_id)
    unverified = dict(unverified_atom_reasons or {})
    if (not set(unverified) <= set(chosen)
            or any(chosen[key] for key in unverified)
            or any(not isinstance(values, Sequence) or isinstance(values, (str, bytes))
                   or not values or any(not isinstance(value, str) or not value.strip() for value in values)
                   for values in unverified.values())):
        raise ValueError("未核实原因必须对应明确的空资料选择")
    calculations = calculate_control_operands(
        frozen, selections=((key, fact_id) for key, values in chosen.items() for fact_id in values),
    )
    conflict_by_fact = {}
    fact_ids = {item.fact_id for item in frozen.evidence_input.facts}
    groups = [ClinicalConflictGroupV2.model_validate(item.model_dump(mode="json"))
              for item in conflict_groups]
    if len({group.conflict_group_id for group in groups}) != len(groups):
        raise ValueError("争议来源不得重复")
    for group in groups:
        if group.authority != frozen.evidence_input.authority:
            raise ValueError("争议来源不属于本次审核资料")
        if group.member_kind != "fact":
            continue
        if not set(group.fact_ids).issubset(fact_ids):
            raise ValueError("争议来源与本次完整事实集合不一致")
        for fact_id in group.fact_ids:
            conflict_by_fact.setdefault(fact_id, set()).add(group.conflict_group_id)
    by_control, unresolved, observations, source_conflicts, observation_scopes = {}, {}, {}, {}, {}
    for identity in identities:
        items = [calculations[(identity.identity_sha256, fact_id)]
                 for fact_id in chosen[identity.identity_sha256]]
        interpreted = []
        selected_conflicts = sorted({group_id for item in items
                                    for group_id in conflict_by_fact.get(item.fact_id, ())})
        if selected_conflicts:
            source_conflicts[identity.identity_sha256] = selected_conflicts
        if identity.atom.evaluation is not None and identity.atom.evaluation.determination_mode == "deterministic":
            for item in items:
                truth, reasons = (
                    (TruthValue.UNKNOWN, ["source_conflict"])
                    if item.fact_id in conflict_by_fact
                    else _conditional_observation(identity.atom, item)
                )
                interpreted.append(ControlConditionalObservation(
                    fact_id=item.fact_id, truth=truth, reason_codes=reasons,
                ))
        elif identity.atom.evaluation is not None:
            for fact_id in chosen[identity.identity_sha256]:
                truth, reasons = ((TruthValue.UNKNOWN, ["source_conflict"])
                                  if fact_id in conflict_by_fact else _proposition_observation(
                                      identity.atom, by_observation.get((identity.identity_sha256, fact_id), []),
                                      calculations[(identity.identity_sha256, fact_id)]))
                interpreted.append(ControlConditionalObservation(fact_id=fact_id, truth=truth, reason_codes=reasons))
        observations[identity.identity_sha256] = interpreted
        spec = identity.atom.evaluation
        records_by_fact = {item.fact_id: by_observation.get((identity.identity_sha256, item.fact_id), [])
                           for item in interpreted}
        individual_facts = (None if spec is None or spec.determination_mode == "deterministic" else {
            fact_id for fact_id, records in records_by_fact.items()
            if any(set(record.get("lanes", {})) == {"main-A", "main-B"}
                   and all(lane.get("assertion_extent") == "individual" for lane in record["lanes"].values())
                   for record in records)
        })
        universal_facts = {
            fact_id for fact_id, records in records_by_fact.items()
            if any(lane.get("assertion_extent") == "universal_over_declared_scope"
                   for record in records
                   for lane in record.get("lanes", {}).values())
        }
        universal_ready = bool(
            spec is not None and spec.determination_mode != "deterministic"
            and spec.observation_policy is not None and spec.observation_policy.mode in {"any", "all"}
            and not selected_conflicts
            and not any(gap.identity_sha256 == identity.identity_sha256 for gap in gaps)
            and all(item.truth != TruthValue.UNKNOWN for item in interpreted)
            and any(_universal_statement(
                by_observation.get((identity.identity_sha256, fact_id), []),
                require_population=spec.observation_policy.mode == "all",
            ) for fact_id in universal_facts)
        )
        scope_verified = bool(
            spec is not None and spec.determination_mode != "deterministic"
            and spec.observation_policy is not None and spec.observation_policy.mode == "single"
            and len(interpreted) == 1 and interpreted[0].truth != TruthValue.UNKNOWN
            and not selected_conflicts and _scope_supported(by_observation.get(
                (identity.identity_sha256, interpreted[0].fact_id), []))
        )
        if (spec is not None and spec.determination_mode == "semantic"
                and spec.observation_policy is not None
                and spec.observation_policy.mode == "action_completion"):
            scope_verified = bool(
                interpreted and not selected_conflicts
                and not any(gap.identity_sha256 == identity.identity_sha256 for gap in gaps)
                and all(item.truth != TruthValue.UNKNOWN and _scope_supported(
                    by_observation.get((identity.identity_sha256, item.fact_id), [])
                ) for item in interpreted)
            )
        truth, reasons = _conditional_truth(identity.atom, interpreted, scope_verified=scope_verified,
                                           universal_facts=universal_facts, individual_facts=individual_facts,
                                           universal_ready=universal_ready)
        if identity.identity_sha256 in unverified:
            truth, reasons = TruthValue.UNKNOWN, list(unverified[identity.identity_sha256])
            scope_verified = False
        if identity.identity_sha256 in repeat_evaluations:
            calculated = repeat_evaluations[identity.identity_sha256].result
            if identity.identity_sha256 in unverified and calculated.truth != TruthValue.UNKNOWN:
                raise ValueError("复查求值不能覆盖尚未核实的条件")
            truth, reasons = calculated.truth, list(calculated.reason_codes)
            scope_verified = truth != TruthValue.UNKNOWN
        if identity.identity_sha256 in frequency_evaluations:
            calculated = frequency_evaluations[identity.identity_sha256].result
            if (identity.identity_sha256 in unverified or selected_conflicts) and calculated.truth != TruthValue.UNKNOWN:
                raise ValueError("频次计算不能覆盖未核实的条件或原文冲突")
            truth, reasons = calculated.truth, list(calculated.reason_codes)
            scope_verified = truth != TruthValue.UNKNOWN
        observation_scopes[identity.identity_sha256] = scope_verified
        by_control.setdefault(identity.protocol_control_id, {})[identity.atom_id] = truth
        if truth == TruthValue.UNKNOWN:
            pair_reasons = [reason for gap in gaps if gap.identity_sha256 == identity.identity_sha256
                            for reason in gap.reasons]
            partial_scope = any(
                lane.get("scope_correspondence") == "partial"
                for (atom_identity, _), records in by_observation.items()
                if atom_identity == identity.identity_sha256
                for record in records for lane in record.get("lanes", {}).values()
            )
            unresolved[identity.identity_sha256] = sorted(set([
                *reasons, *pair_reasons,
                *(["observation_scope_partially_covered"] if partial_scope else []),
            ]))
    layers = [compose_control_layers(
        control, control_sha256=canonical_hash(control.model_dump(mode="json")),
        atom_truths=by_control.get(control.protocol_control_id, {}),
    ) for control in frozen.publication.catalog.controls] if not repeat_triggers_only else []
    selection_payload = {
        "version": "control-calculation-experiment/v15",
        "frozen_input_sha256": frozen.frozen_input_sha256, "selections": chosen,
        "conflict_groups": [group.model_dump(mode="json") for group in sorted(
            groups, key=lambda group: group.conflict_group_id)],
        "proposition_relations": sorted(proposition_relations, key=lambda item: item["pair_id"]),
        "proposition_pair_gaps": [gap.model_dump(mode="json") for gap in sorted(gaps, key=lambda item: item.pair_id)],
    }
    if unverified_atom_reasons is not None:
        selection_payload["qualification_gap_policy"] = {
            "version": "unverified-control/v1",
            "reasons": {key: sorted(set(values)) for key, values in unverified.items()},
        }
    if repeat_triggers_only:
        selection_payload["purpose"] = "auxiliary-repeat-trigger/v1"
    if repeat_evaluations:
        selection_payload["repeat_evaluations"] = {key: item.model_dump(mode="json") for key, item in repeat_evaluations.items()}
    if frequency_evaluations:
        selection_payload["frequency_evaluations"] = {key: item.model_dump(mode="json") for key, item in frequency_evaluations.items()}
    return ControlCalculationExperiment(
        frozen_input_sha256=frozen.frozen_input_sha256,
        purpose="auxiliary_repeat_trigger" if repeat_triggers_only else "four_layer",
        selections_sha256=canonical_hash(selection_payload),
        layers=layers, calculations=list(calculations.values()),
        observations=observations, unresolved_atoms=unresolved, source_conflicts=source_conflicts,
        observation_scopes=observation_scopes,
        proposition_pair_gaps=gaps,
        repeat_evaluations=repeat_evaluations,
        frequency_evaluations=frequency_evaluations,
    ), by_control


def evaluate_control_layers_experiment(
    frozen: ControlBindingFrozenInput, *, frozen_input_sha256: str,
    selections: Mapping[str, Sequence[str]],
    conflict_groups: Sequence[ClinicalConflictGroupV2] = (),
    unverified_atom_reasons: Mapping[str, Sequence[str]] | None = None,
    proposition_relations: Sequence[dict] = (),
    proposition_pair_gaps: Sequence[dict] = (),
    repeat_evaluations: Mapping[str, RepeatAtomEvaluation] | None = None,
    frequency_evaluations: Mapping[str, FrequencyAtomEvaluation] | None = None,
) -> ControlCalculationExperiment:
    """Preserve the complete four-layer selection and composition contract."""
    calculated, _ = _evaluate_control_selection(
        frozen, frozen_input_sha256=frozen_input_sha256, selections=selections,
        conflict_groups=conflict_groups, unverified_atom_reasons=unverified_atom_reasons,
        proposition_relations=proposition_relations, proposition_pair_gaps=proposition_pair_gaps,
        repeat_evaluations=repeat_evaluations,
        frequency_evaluations=frequency_evaluations,
    )
    return calculated
