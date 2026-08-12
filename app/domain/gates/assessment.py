from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.domain.contracts.agents import AgentCallContract, GateResult
from app.domain.contracts.common import ContractModel, DateValue
from app.domain.contracts.enums import (
    AgentNode,
    AnchorType,
    ComponentDecision,
    ExpectationStatus,
    GapType,
    GateOutcome,
    ReviewStage,
    RuleKind,
    TruthValue,
)
from app.domain.contracts.evidence import (
    ClinicalFact,
    ConflictGroup,
    EvidenceExpectation,
    EvidenceSpan,
)
from app.domain.contracts.review import AssessmentCandidate, FinalAssessment
from app.domain.contracts.normalization import EvidenceNormalizationCandidate
from app.domain.contracts.rules import RuleComponent, RuleSet
from app.domain.contracts.rules import iter_atomic_predicates
from app.domain.expression import ComponentEvaluation, EvaluationContext, evaluate_component
from app.domain.gates.evidence import require_accepted_evidence_gate
from .permissions import require_accepted_agent_call
from app.domain.policies import derive_assessment_blocking_level, validate_decision_gap_matrix
from app.domain.publication import _build_gate_owned_model, canonical_hash


class AssessmentGateError(ValueError):
    pass


class AssessmentPublication(ContractModel):
    assessment: FinalAssessment
    gate_result: GateResult
    rule_set: RuleSet
    candidate: AssessmentCandidate
    candidate_gate_result: GateResult
    agent_call: AgentCallContract
    agent_call_gate_result: GateResult
    evidence_candidate: EvidenceNormalizationCandidate
    evidence_gate_result: GateResult
    evidence_agent_call: AgentCallContract
    evidence_agent_call_gate_result: GateResult
    anchor_dates: dict[AnchorType, DateValue]
    half_life_days: dict[str, float] = Field(default_factory=dict)
    episode_stage: ReviewStage
    expectations: list[EvidenceExpectation]
    conflict_groups: list[ConflictGroup]


def publish_assessment_candidate_acceptance(
    candidate: AssessmentCandidate,
    *,
    agent_call: AgentCallContract,
    agent_call_gate_result: GateResult,
    gate_result_id: str,
    created_at: datetime,
) -> GateResult:
    require_accepted_agent_call(agent_call, agent_call_gate_result)
    if agent_call.typed_output_hashes.get(
        candidate.assessment_candidate_id
    ) != canonical_hash(candidate.model_dump(mode="json")):
        raise AssessmentGateError(
            "AssessmentCandidate 未绑定 AgentCall 实际 typed output"
        )
    expected_scope = (
        agent_call.project_id,
        agent_call.protocol_version_id,
        agent_call.subject_id,
        agent_call.rule_set_id,
        agent_call.rule_set_revision,
        agent_call.review_episode_id,
        agent_call.review_run_id,
        agent_call.evidence_snapshot_id,
    )
    candidate_scope = (
        candidate.project_id,
        candidate.protocol_version_id,
        candidate.subject_id,
        candidate.rule_set_id,
        candidate.rule_set_revision,
        candidate.review_episode_id,
        candidate.review_run_id,
        candidate.evidence_snapshot_id,
    )
    if (
        agent_call.node != AgentNode.ELIGIBILITY_ASSESSOR
        or candidate.agent_call_id != agent_call.agent_call_id
        or candidate_scope != expected_scope
    ):
        raise AssessmentGateError("AssessmentCandidate 与 Eligibility AgentCall scope 不一致")
    payload = candidate.model_dump(mode="json")
    return GateResult(
        gate_result_id=gate_result_id,
        gate_name="assessment-candidate-gate",
        result=GateOutcome.ACCEPTED,
        input_scope_hash=agent_call.input_scope_hash,
        input_revision_map=agent_call.input_revision_map,
        input_entity_refs=[
            agent_call.agent_call_id,
            agent_call_gate_result.gate_result_id,
        ],
        accepted_entity_refs=[candidate.assessment_candidate_id],
        affected_scope=[candidate.rule_component_id],
        recompute_scope=[candidate.rule_component_id],
        idempotency_key=(
            f"candidate:{agent_call.agent_call_id}:{candidate.assessment_candidate_id}"
        ),
        created_at=created_at,
        output_hash=canonical_hash(payload),
    )


STAGE_RANK = {
    ReviewStage.PRE_SCREENING: 0,
    ReviewStage.SCREENING: 1,
    ReviewStage.RUN_IN: 2,
    ReviewStage.BASELINE: 3,
}


REASON_GAPS = {
    "source_conflict": GapType.SOURCE_CONFLICT,
    "professional_judgment_missing": GapType.PROFESSIONAL_JUDGMENT,
    "date_or_anchor_missing": GapType.DATE_OR_ANCHOR_MISSING,
    "half_life_missing": GapType.DATE_OR_ANCHOR_MISSING,
    "unit_mismatch": GapType.OCR_OR_PARSE_RISK,
    "fact_polarity_unknown": GapType.OCR_OR_PARSE_RISK,
    "ambiguous_partial_date": GapType.DATE_OR_ANCHOR_MISSING,
    "ambiguous_time_direction": GapType.DATE_OR_ANCHOR_MISSING,
    "ambiguous_time_window": GapType.DATE_OR_ANCHOR_MISSING,
}


def derive_gate_gap_types(
    *,
    component: RuleComponent,
    evaluation: ComponentEvaluation,
    episode_stage: ReviewStage,
    expectations: list[EvidenceExpectation],
    conflict_groups: list[ConflictGroup],
) -> set[GapType]:
    component_requirement_ids = {
        requirement.requirement_id for requirement in component.evidence_requirements
    }
    relevant_expectations = [
        expectation
        for expectation in expectations
        if expectation.requirement_id in component_requirement_ids
    ]
    expectation_by_requirement = {
        expectation.requirement_id: expectation
        for expectation in relevant_expectations
    }
    if len(expectation_by_requirement) != len(relevant_expectations):
        raise AssessmentGateError("同一组件的 EvidenceExpectation requirement_id 必须唯一")

    gaps: set[GapType] = set()
    future_requirements = 0
    due_requirements = 0
    for requirement in component.evidence_requirements:
        if STAGE_RANK[requirement.due_stage] > STAGE_RANK[episode_stage]:
            future_requirements += 1
            continue
        due_requirements += 1
        expectation = expectation_by_requirement.get(requirement.requirement_id)
        if expectation is None:
            gaps.add(GapType.RECORD_INCOMPLETE)
            continue
        if expectation.status == ExpectationStatus.NOT_DUE:
            raise AssessmentGateError("已到期 EvidenceRequirement 不能保持 not_due")
        if expectation.gap_type is not None:
            gaps.add(expectation.gap_type)

    if future_requirements and not due_requirements:
        # Before the component is due, current evidence conflicts or missing
        # predicates must not turn a future review item into a current blocker.
        return {GapType.FUTURE_STAGE_NOT_DUE}

    for conflict in conflict_groups:
        if not conflict.resolved and component.rule_component_id in conflict.affected_rule_component_ids:
            gaps.add(GapType.SOURCE_CONFLICT)

    # A definitive trigger result must not inherit uncertainty from a sibling
    # branch that cannot change that result (for example FALSE in an ALL tree).
    reason_codes = (
        set(evaluation.trigger.reason_codes)
        if evaluation.trigger.truth == TruthValue.UNKNOWN
        else set()
    )
    if (
        evaluation.exception is not None
        and evaluation.trigger.truth == TruthValue.TRUE
        and evaluation.exception.truth == TruthValue.UNKNOWN
    ):
        reason_codes.update(evaluation.exception.reason_codes)
    gaps.update(REASON_GAPS[code] for code in reason_codes if code in REASON_GAPS)

    if (
        evaluation.trigger.truth == TruthValue.UNKNOWN
        or evaluation.applicable == TruthValue.UNKNOWN
        or (
            evaluation.exception is not None
            and evaluation.trigger.truth == TruthValue.TRUE
            and evaluation.exception.truth == TruthValue.UNKNOWN
        )
    ) and not gaps:
        gaps.add(GapType.RECORD_INCOMPLETE)
    return gaps


def _decision_for_unknown(gaps: set[GapType]) -> ComponentDecision:
    if gaps.intersection({GapType.SOURCE_CONFLICT, GapType.INTERPRETATION_CONFLICT}):
        return ComponentDecision.CONFLICT
    if GapType.PROFESSIONAL_JUDGMENT in gaps:
        return ComponentDecision.PROFESSIONAL_JUDGMENT
    if gaps == {GapType.FUTURE_STAGE_NOT_DUE}:
        return ComponentDecision.NOT_DUE
    return ComponentDecision.INDETERMINATE


def derive_component_decision(
    *,
    rule_kind: RuleKind,
    evaluation: ComponentEvaluation,
    gaps: set[GapType],
) -> ComponentDecision:
    if evaluation.applicable == TruthValue.FALSE:
        return ComponentDecision.NOT_APPLICABLE
    if evaluation.applicable == TruthValue.UNKNOWN:
        return _decision_for_unknown(gaps)
    if gaps == {GapType.FUTURE_STAGE_NOT_DUE}:
        return ComponentDecision.NOT_DUE
    trigger = evaluation.trigger.truth
    if trigger == TruthValue.UNKNOWN:
        return _decision_for_unknown(gaps)
    if rule_kind == RuleKind.INCLUSION:
        return (
            ComponentDecision.INCLUSION_MET
            if trigger == TruthValue.TRUE
            else ComponentDecision.INCLUSION_NOT_MET
        )
    if rule_kind == RuleKind.REQUIRED_PROCEDURE:
        return (
            ComponentDecision.REQUIREMENT_MET
            if trigger == TruthValue.TRUE
            else ComponentDecision.REQUIREMENT_NOT_MET
        )
    if trigger == TruthValue.FALSE:
        return ComponentDecision.EXCLUSION_NOT_TRIGGERED
    if evaluation.exception is None or evaluation.exception.truth == TruthValue.FALSE:
        return ComponentDecision.EXCLUSION_TRIGGERED
    if evaluation.exception.truth == TruthValue.TRUE:
        return ComponentDecision.EXCLUSION_NOT_TRIGGERED
    return _decision_for_unknown(gaps)


def validate_assessment_candidate(
    candidate: AssessmentCandidate,
    *,
    component: RuleComponent,
    derived_gaps: set[GapType],
    evaluation: ComponentEvaluation,
) -> None:
    if set(candidate.gap_types) != derived_gaps:
        raise AssessmentGateError(
            "Agent 候选 gap_types 与 Gate 根据证据、阶段和求值结果重建的缺口不一致"
        )
    try:
        validate_decision_gap_matrix(candidate.proposed_decision, derived_gaps)
    except ValueError as exc:
        raise AssessmentGateError(str(exc)) from exc
    evaluated_fact_ids = set(evaluation.trigger.used_fact_ids)
    if (
        evaluation.exception is not None
        and evaluation.trigger.truth == TruthValue.TRUE
    ):
        evaluated_fact_ids.update(evaluation.exception.used_fact_ids)
    if set(candidate.used_fact_ids) != evaluated_fact_ids:
        raise AssessmentGateError(
            "Agent 候选 used_fact_ids 必须与确定性求值实际使用的事实完全一致"
        )
    expected_predicate_ids = {
        predicate.predicate_id
        for expression in [component.expression, component.exception_expression]
        if expression is not None
        for predicate in iter_atomic_predicates(expression)
    }
    processed = set(candidate.processed_predicate_ids)
    observation_ids = {
        observation.predicate_id for observation in candidate.predicate_observations
    }
    if len(observation_ids) != len(candidate.predicate_observations):
        raise AssessmentGateError("AssessmentCandidate 不得重复谓词观察")
    if processed != expected_predicate_ids or observation_ids != expected_predicate_ids:
        raise AssessmentGateError(
            "AssessmentCandidate 必须逐项覆盖当前 RuleComponent 的全部原子谓词"
        )
    if not set(candidate.missing_predicate_ids) <= expected_predicate_ids:
        raise AssessmentGateError("AssessmentCandidate missing_predicate_ids 越界")
    if set(evaluation.predicate_evaluations) != expected_predicate_ids:
        raise AssessmentGateError(
            "ComponentEvaluation 必须包含当前 RuleComponent 全部原子谓词的确定性求值"
        )
    observation_by_id = {
        observation.predicate_id: observation
        for observation in candidate.predicate_observations
    }
    for predicate_id, result in evaluation.predicate_evaluations.items():
        observation = observation_by_id[predicate_id]
        if (
            observation.truth != result.truth
            or set(observation.fact_ids) != set(result.used_fact_ids)
            or set(observation.reason_codes) != set(result.reason_codes)
            or observation.observed_value != result.observed_value
            or observation.observed_unit != result.observed_unit
            or set(observation.evidence_span_ids) != set(result.evidence_span_ids)
        ):
            raise AssessmentGateError(
                "AssessmentCandidate 谓词观察必须与确定性 Evaluator 结果一致"
            )


def publish_assessment(
    candidate: AssessmentCandidate,
    *,
    agent_call: AgentCallContract,
    agent_call_gate_result: GateResult,
    candidate_gate_result: GateResult,
    evidence_gate_result: GateResult,
    evidence_candidate: EvidenceNormalizationCandidate,
    evidence_agent_call: AgentCallContract,
    evidence_agent_call_gate_result: GateResult,
    rule_set: RuleSet,
    anchor_dates: dict[AnchorType, DateValue],
    half_life_days: dict[str, float] | None = None,
    episode_stage: ReviewStage,
    expectations: list[EvidenceExpectation],
    conflict_groups: list[ConflictGroup],
    assessment_id: str,
    gate_result_id: str,
    input_revision_map: dict[str, int],
    created_at: datetime,
) -> AssessmentPublication:
    require_accepted_agent_call(agent_call, agent_call_gate_result)
    candidate_payload = candidate.model_dump(mode="json")
    if (
        candidate_gate_result.gate_name != "assessment-candidate-gate"
        or candidate_gate_result.result != GateOutcome.ACCEPTED
        or candidate.assessment_candidate_id
        not in candidate_gate_result.accepted_entity_refs
        or agent_call.agent_call_id not in candidate_gate_result.input_entity_refs
        or agent_call_gate_result.gate_result_id
        not in candidate_gate_result.input_entity_refs
        or candidate_gate_result.output_hash != canonical_hash(candidate_payload)
    ):
        raise AssessmentGateError("AssessmentCandidate 未通过绑定 AgentCall 的 accepted Gate")
    expected_scope = (
        agent_call.project_id,
        agent_call.protocol_version_id,
        agent_call.subject_id,
        agent_call.rule_set_id,
        agent_call.rule_set_revision,
        agent_call.review_episode_id,
        agent_call.review_run_id,
        agent_call.evidence_snapshot_id,
    )
    candidate_scope = (
        candidate.project_id,
        candidate.protocol_version_id,
        candidate.subject_id,
        candidate.rule_set_id,
        candidate.rule_set_revision,
        candidate.review_episode_id,
        candidate.review_run_id,
        candidate.evidence_snapshot_id,
    )
    if candidate_scope != expected_scope:
        raise AssessmentGateError("AssessmentCandidate 与 AgentCall scope 不一致")
    if (
        rule_set.rule_set_id != candidate.rule_set_id
        or rule_set.revision != candidate.rule_set_revision
    ):
        raise AssessmentGateError("AssessmentCandidate 与 RuleSet ID/revision 不一致")
    matches = [
        (rule, component)
        for rule in rule_set.rules
        for component in rule.components
        if component.rule_component_id == candidate.rule_component_id
    ]
    if len(matches) != 1:
        raise AssessmentGateError(
            "AssessmentCandidate rule_component_id 必须唯一属于当前 RuleSet"
        )
    rule, component = matches[0]
    require_accepted_evidence_gate(
        evidence_gate_result,
        candidate=evidence_candidate,
        agent_call=evidence_agent_call,
        agent_call_gate_result=evidence_agent_call_gate_result,
    )
    facts = evidence_candidate.clinical_fact_candidates
    evidence_spans = evidence_candidate.evidence_span_candidates
    context = EvaluationContext(
        project_id=candidate.project_id,
        subject_id=candidate.subject_id,
        review_episode_id=candidate.review_episode_id,
        evidence_snapshot_id=candidate.evidence_snapshot_id,
        accepted_fact_ids=[item.fact_id for item in facts],
        facts=facts,
        anchor_dates=anchor_dates,
        half_life_days=half_life_days or {},
    )
    evaluation = evaluate_component(component, context)
    if (component.exception_expression is None) != (evaluation.exception is None):
        raise AssessmentGateError(
            "ComponentEvaluation.exception 必须与 RuleComponent.exception_expression 结构一致"
        )
    gaps = derive_gate_gap_types(
        component=component,
        evaluation=evaluation,
        episode_stage=episode_stage,
        expectations=expectations,
        conflict_groups=conflict_groups,
    )
    decision = derive_component_decision(
        rule_kind=rule.kind,
        evaluation=evaluation,
        gaps=gaps,
    )
    if candidate.proposed_decision != decision:
        raise AssessmentGateError(
            f"Agent 候选状态 {candidate.proposed_decision.value} 与确定性结果 {decision.value} 不一致"
        )
    validate_assessment_candidate(
        candidate,
        component=component,
        derived_gaps=gaps,
        evaluation=evaluation,
    )
    blocking_level = derive_assessment_blocking_level(decision, gaps)
    fact_by_id = {item.fact_id: item for item in facts}
    derived_span_ids = list(
        dict.fromkeys(
            span_id
            for fact_id in candidate.used_fact_ids
            for span_id in fact_by_id[fact_id].evidence_span_ids
        )
    )
    if set(candidate.evidence_span_ids) != set(derived_span_ids):
        raise AssessmentGateError(
            "AssessmentCandidate evidence_span_ids 必须由实际依赖事实推导"
        )
    assessment = _build_gate_owned_model(
        FinalAssessment,
        entity_type="final_assessment",
        gate_result_id=gate_result_id,
        data={
            "assessment_id": assessment_id,
            "project_id": candidate.project_id,
            "protocol_version_id": candidate.protocol_version_id,
            "subject_id": candidate.subject_id,
            "rule_set_id": candidate.rule_set_id,
            "rule_set_revision": candidate.rule_set_revision,
            "review_episode_id": candidate.review_episode_id,
            "evidence_snapshot_id": candidate.evidence_snapshot_id,
            "review_run_id": candidate.review_run_id,
            "rule_component_id": candidate.rule_component_id,
            "decision": decision,
            "gap_types": sorted(gaps, key=lambda item: item.value),
            "blocking_level": blocking_level,
            "used_fact_ids": candidate.used_fact_ids,
            "evidence_span_ids": derived_span_ids,
        },
    )
    input_payload = {
        "candidate": candidate.model_dump(mode="json"),
        "candidate_gate_result": candidate_gate_result.model_dump(mode="json"),
        "evidence_gate_result": evidence_gate_result.model_dump(mode="json"),
        "component": component.model_dump(mode="json"),
        "rule_set_id": rule_set.rule_set_id,
        "rule_set_revision": rule_set.revision,
        "evaluation": evaluation.model_dump(mode="json"),
        "episode_stage": episode_stage.value,
        "expectations": [item.model_dump(mode="json") for item in expectations],
        "conflict_groups": [item.model_dump(mode="json") for item in conflict_groups],
    }
    gate_result = GateResult(
        gate_result_id=gate_result_id,
        gate_name="assessment-publication-gate",
        result=GateOutcome.ACCEPTED,
        input_scope_hash=canonical_hash(input_payload),
        input_revision_map=input_revision_map,
        input_entity_refs=[
            candidate.assessment_candidate_id,
            candidate_gate_result.gate_result_id,
            evidence_gate_result.gate_result_id,
            component.rule_component_id,
            candidate.review_run_id,
        ],
        accepted_entity_refs=[assessment.assessment_id],
        affected_scope=[component.rule_component_id],
        recompute_scope=[component.rule_component_id],
        idempotency_key=(
            f"assessment:{candidate.review_run_id}:{component.rule_component_id}"
        ),
        created_at=created_at,
        output_hash=canonical_hash(assessment.model_dump(mode="json")),
    )
    return AssessmentPublication(
        assessment=assessment,
        gate_result=gate_result,
        rule_set=rule_set,
        candidate=candidate,
        candidate_gate_result=candidate_gate_result,
        agent_call=agent_call,
        agent_call_gate_result=agent_call_gate_result,
        evidence_candidate=evidence_candidate,
        evidence_gate_result=evidence_gate_result,
        evidence_agent_call=evidence_agent_call,
        evidence_agent_call_gate_result=evidence_agent_call_gate_result,
        anchor_dates=anchor_dates,
        half_life_days=half_life_days or {},
        episode_stage=episode_stage,
        expectations=expectations,
        conflict_groups=conflict_groups,
    )


def validate_assessment_publication(
    publication: AssessmentPublication,
) -> GateResult:
    expected = publish_assessment(
        publication.candidate,
        agent_call=publication.agent_call,
        agent_call_gate_result=publication.agent_call_gate_result,
        candidate_gate_result=publication.candidate_gate_result,
        evidence_gate_result=publication.evidence_gate_result,
        evidence_candidate=publication.evidence_candidate,
        evidence_agent_call=publication.evidence_agent_call,
        evidence_agent_call_gate_result=publication.evidence_agent_call_gate_result,
        rule_set=publication.rule_set,
        anchor_dates=publication.anchor_dates,
        half_life_days=publication.half_life_days,
        episode_stage=publication.episode_stage,
        expectations=publication.expectations,
        conflict_groups=publication.conflict_groups,
        assessment_id=publication.assessment.assessment_id,
        gate_result_id=publication.gate_result.gate_result_id,
        input_revision_map=publication.gate_result.input_revision_map,
        created_at=publication.gate_result.created_at,
    )
    if publication.model_dump(mode="json") != expected.model_dump(mode="json"):
        raise AssessmentGateError(
            "AssessmentPublication 未通过完整上游 Gate 闭包重算"
        )
    return publication.gate_result
