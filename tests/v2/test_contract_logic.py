from __future__ import annotations

from datetime import date, datetime, timezone
from typing import cast

import pytest
from pydantic import ValidationError

from app.domain.contracts.agents import AgentCallContract, AgentPublishedEntity, GateResult
from app.domain.contracts.agent_io import CoverageSummary, EligibilityAssessmentOutput
from app.domain.contracts.normalization import EvidenceNormalizationCandidate
from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import (
    ActionState,
    ActionTarget,
    AgentNode,
    AgentOutputKind,
    AgentWriteScope,
    BlockingLevel,
    ComponentDecision,
    DatePrecision,
    EpisodeMainStatus,
    ExpectationStatus,
    FactPolarity,
    GapType,
    LocatorPrecision,
    LogicalOperator,
    ReviewStage,
    RuleKind,
    StudyPhase,
    TruthValue,
    TimeDirection,
    UploadMode,
)
from app.domain.contracts.evidence import (
    BoundingBox,
    ClinicalFact,
    ConflictGroup,
    EvidenceExpectation,
    EvidenceSnapshot,
    EvidenceSpan,
)
from app.domain.contracts.projections import EpisodeRollup
from app.domain.contracts.review import (
    ActionRequest,
    AssessmentCandidate,
    FinalAssessment,
    PredicateObservation,
    ProtocolDocumentVersion,
)
from app.domain.contracts.rules import (
    AtomicExpression,
    AtomicPredicate as AtomicPredicateModel,
    EvidenceRequirement,
    LogicalExpression,
    RuleComponent,
    Rule,
    RuleSet,
    TimeConstraint,
    WorkflowStage,
)
from app.domain.expression import (
    EvaluationContext,
    evaluate_component,
    evaluate_expression,
)
from app.domain.gates import (
    ActionGateError,
    AgentPermissionError,
    AssessmentGateError,
    build_protocol_integrity_manifest,
    derive_action_blocking_level,
    publish_action_request,
    publish_assessment,
    publish_assessment_candidate_acceptance,
    publish_evidence_acceptance,
    validate_action_publication,
    require_agent_write_permission,
    assert_protocol_integrity,
    build_protocol_authority_record,
    publish_protocol_authority_acceptance,
)
from app.domain.policies import derive_assessment_blocking_level
from app.domain import publication as publication_module
from app.domain.publication import _build_gate_owned_model, canonical_hash
from app.domain.gates.actions import ActionPublication
from app.domain.gates.assessment import AssessmentPublication
from app.domain.rollup import publish_episode_rollup


EVALUATION_SCOPE = {
    "project_id": "project-1",
    "subject_id": "subject-1",
    "review_episode_id": "episode-1",
    "evidence_snapshot_id": "snapshot-1",
}


def AtomicPredicate(**kwargs):
    kwargs.setdefault(
        "predicate_id",
        f"predicate-{kwargs.get('subject')}-{kwargs.get('attribute')}-{kwargs.get('comparator')}",
    )
    return AtomicPredicateModel(**kwargs)


def clinical_fact(**kwargs) -> ClinicalFact:
    return ClinicalFact(**EVALUATION_SCOPE, **kwargs)


def evaluation_context(*, facts=None, **kwargs) -> EvaluationContext:
    scoped_facts = facts or []
    return EvaluationContext(
        **EVALUATION_SCOPE,
        accepted_fact_ids=[fact.fact_id for fact in scoped_facts],
        facts=scoped_facts,
        **kwargs,
    )


def candidate(decision: ComponentDecision, gaps: list[GapType]) -> AssessmentCandidate:
    truth = {
        ComponentDecision.EXCLUSION_TRIGGERED: TruthValue.TRUE,
        ComponentDecision.EXCLUSION_NOT_TRIGGERED: TruthValue.FALSE,
    }.get(decision, TruthValue.UNKNOWN)
    predicate_id = "predicate-history-condition_present-eq"
    return AssessmentCandidate(
        assessment_candidate_id="candidate-1",
        agent_call_id="call-1",
        project_id="project-1",
        protocol_version_id="protocol-1",
        subject_id="subject-1",
        rule_set_id="ruleset-1",
        rule_set_revision=1,
        review_run_id="run-1",
        rule_component_id="component-1",
        review_episode_id="episode-1",
        evidence_snapshot_id="snapshot-1",
        proposed_decision=decision,
        gap_types=gaps,
        used_fact_ids=[],
        evidence_span_ids=[],
        candidate_rationale="合成测试候选，不参与确定性逻辑。",
        predicate_observations=[
            PredicateObservation(predicate_id=predicate_id, truth=truth)
        ],
        processed_predicate_ids=[predicate_id],
        missing_predicate_ids=(
            [predicate_id] if truth == TruthValue.UNKNOWN else []
        ),
        candidate_confidence=0.9,
    )


def final_assessment(decision: ComponentDecision, gaps: list[GapType]):
    assessment = _build_gate_owned_model(
        FinalAssessment,
        entity_type="final_assessment",
        gate_result_id=f"gate-{decision.value}",
        data={
            "assessment_id": f"assessment-{decision.value}",
            "project_id": "project-1",
            "protocol_version_id": "protocol-1",
            "subject_id": "subject-1",
            "rule_set_id": "ruleset-1",
            "rule_set_revision": 1,
            "review_episode_id": "episode-1",
            "evidence_snapshot_id": "snapshot-1",
            "review_run_id": "run-1",
            "rule_component_id": "component-1",
            "decision": decision,
            "gap_types": gaps,
            "blocking_level": derive_assessment_blocking_level(decision, set(gaps)),
            "used_fact_ids": ["fact-1"],
            "evidence_span_ids": ["span-1"],
        },
    )
    return assessment


def assessment_publication(assessment: FinalAssessment) -> AssessmentPublication:
    gate = GateResult(
        gate_result_id=assessment.gate_result_id,
        gate_name="assessment-publication-gate",
        result="accepted",
        input_scope_hash="a" * 64,
        input_revision_map={assessment.review_episode_id: 1},
        input_entity_refs=["candidate-1"],
        accepted_entity_refs=[assessment.assessment_id],
        affected_scope=[assessment.rule_component_id],
        recompute_scope=[assessment.rule_component_id],
        idempotency_key=f"test:{assessment.assessment_id}",
        created_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
        output_hash=canonical_hash(assessment.model_dump(mode="json")),
    )
    return AssessmentPublication(assessment=assessment, gate_result=gate)


def gate_component(*, requirements=None, with_exception=False) -> RuleComponent:
    return RuleComponent(
        rule_component_id="component-1",
        parent_rule_id="rule-1",
        display_code="EX-01a",
        title="合成 Gate 组件",
        expression=AtomicExpression(
            predicate=AtomicPredicate(
                subject="history",
                attribute="condition_present",
                comparator="eq",
                value=True,
            )
        ),
        exception_expression=(
            AtomicExpression(
                predicate=AtomicPredicate(
                    subject="exception",
                    attribute="documented",
                    comparator="eq",
                    value=True,
                )
            )
            if with_exception
            else None
        ),
        evidence_requirements=requirements or [],
    )


def eligibility_call() -> AgentCallContract:
    return AgentCallContract(
        agent_call_id="call-1",
        node=AgentNode.ELIGIBILITY_ASSESSOR,
        output_kind=AgentOutputKind.CANDIDATE,
        write_scope=AgentWriteScope.ASSESSMENT_CANDIDATE,
        prompt_version_id="prompt-1",
        model_config_id="model-1",
        input_scope_hash="a" * 64,
        input_revision_map={"episode-1": 1},
        raw_output_hash="b" * 64,
        output_hash="c" * 64,
        idempotency_key="episode-1:assessment",
        attempt=1,
        max_attempts=2,
        duration_ms=100,
        started_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
        finished_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
        outcome="accepted",
        recompute_scope=["component-1"],
        trigger="test",
        project_id="project-1",
        protocol_version_id="protocol-1",
        rule_set_id="ruleset-1",
        rule_set_revision=1,
        subject_id="subject-1",
        review_episode_id="episode-1",
        review_run_id="run-1",
        evidence_snapshot_id="snapshot-1",
        source_ids=["document-1"],
        gate_result_ids=["gate-call-1"],
    )


def evidence_span(span_id: str) -> EvidenceSpan:
    return EvidenceSpan(
        evidence_span_id=span_id,
        source_document_version_id="document-1",
        page_number=1,
        precision=LocatorPrecision.PAGE_EXCERPT,
        excerpt="合成测试证据",
        locator_algorithm_version="test-v1",
    )


def evidence_normalizer_call() -> AgentCallContract:
    return eligibility_call().model_copy(
        update={
            "agent_call_id": "call-evidence-1",
            "node": AgentNode.EVIDENCE_NORMALIZER,
            "output_kind": AgentOutputKind.CANDIDATE,
            "write_scope": AgentWriteScope.EVIDENCE_CANDIDATE,
            "idempotency_key": "episode-1:evidence",
        }
    )


def agent_call_gate(call: AgentCallContract) -> GateResult:
    return GateResult(
        gate_result_id=call.gate_result_ids[0],
        gate_name="agent-output-schema-gate",
        result="accepted",
        input_scope_hash=call.input_scope_hash,
        input_revision_map=call.input_revision_map,
        input_entity_refs=[call.agent_call_id],
        accepted_entity_refs=[call.agent_call_id],
        affected_scope=call.recompute_scope,
        recompute_scope=call.recompute_scope,
        idempotency_key=f"gate:{call.idempotency_key}",
        created_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
        output_hash=call.output_hash,
    )


def evidence_candidate(
    facts: list[ClinicalFact], spans: list[EvidenceSpan]
) -> EvidenceNormalizationCandidate:
    return EvidenceNormalizationCandidate(
        candidate_id="evidence-candidate-1",
        protocol_version_id="protocol-1",
        **EVALUATION_SCOPE,
        clinical_fact_candidates=facts,
        evidence_span_candidates=spans,
        source_refs=["document-1"],
        coverage=CoverageSummary(processed_refs=["document-1"]),
        created_by_agent_call_id="call-evidence-1",
    )


def test_evidence_gate_rejects_candidate_from_another_agent_scope() -> None:
    facts = [
        clinical_fact(
            fact_id="fact-evidence-scope",
            fact_type="history.condition_present",
            value=True,
            polarity=FactPolarity.AFFIRMED,
            certainty=1,
            evidence_span_ids=["span-evidence-scope"],
        )
    ]
    spans = [evidence_span("span-evidence-scope")]
    normalized = evidence_candidate(facts, spans).model_copy(
        update={"created_by_agent_call_id": "call-other"}
    )
    with pytest.raises(ValueError, match="AgentCall scope"):
        publish_evidence_acceptance(
            candidate=normalized,
            agent_call=(call := evidence_normalizer_call()),
            agent_call_gate_result=agent_call_gate(call),
            gate_result_id="gate-evidence-scope",
            input_revision_map={"episode-1": 1},
            created_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
        )


def test_assessment_rejects_facts_not_in_accepted_evidence_candidate() -> None:
    component = gate_component()
    accepted_facts = [
        clinical_fact(
            fact_id="fact-accepted",
            fact_type="history.condition_present",
            value=False,
            polarity=FactPolarity.AFFIRMED,
            certainty=1,
            evidence_span_ids=["span-accepted"],
        )
    ]
    accepted_spans = [evidence_span("span-accepted")]
    normalized = evidence_candidate(accepted_facts, accepted_spans)
    evidence_call = evidence_normalizer_call()
    evidence_gate = publish_evidence_acceptance(
        candidate=normalized,
        agent_call=evidence_call,
        agent_call_gate_result=agent_call_gate(evidence_call),
        gate_result_id="gate-evidence-accepted",
        input_revision_map={"episode-1": 1},
        created_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
    )
    value = align_candidate(
        candidate(ComponentDecision.EXCLUSION_NOT_TRIGGERED, []),
        component,
        accepted_facts,
    )
    call = eligibility_call()
    candidate_gate = publish_assessment_candidate_acceptance(
        value,
        agent_call=call,
        agent_call_gate_result=agent_call_gate(call),
        gate_result_id="gate-candidate-evidence-substitution",
        created_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
    )
    substituted_facts = [
        accepted_facts[0].model_copy(update={"value": True})
    ]
    with pytest.raises(ValueError, match="accepted Evidence Candidate"):
        publish_assessment(
            value,
            agent_call=call,
            agent_call_gate_result=agent_call_gate(call),
            candidate_gate_result=candidate_gate,
            evidence_gate_result=evidence_gate,
            evidence_candidate=normalized,
            evidence_agent_call=evidence_call,
            evidence_agent_call_gate_result=agent_call_gate(evidence_call),
            component=component,
            rule_kind=RuleKind.EXCLUSION,
            facts=substituted_facts,
            evidence_spans=accepted_spans,
            anchor_dates={},
            episode_stage=ReviewStage.SCREENING,
            expectations=[],
            conflict_groups=[],
            assessment_id="assessment-evidence-substitution",
            gate_result_id="gate-assessment-evidence-substitution",
            input_revision_map={"episode-1": 1},
            created_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
        )


def align_candidate(
    value: AssessmentCandidate,
    component: RuleComponent,
    facts: list[ClinicalFact],
) -> AssessmentCandidate:
    context = evaluation_context(facts=facts)
    evaluation = evaluate_component(component, context)
    facts_by_id = {item.fact_id: item for item in facts}
    observations = [
        PredicateObservation(
            predicate_id=predicate_id,
            truth=result.truth,
            observed_value=result.observed_value,
            observed_unit=result.observed_unit,
            fact_ids=result.used_fact_ids,
            evidence_span_ids=result.evidence_span_ids,
            reason_codes=result.reason_codes,
        )
        for predicate_id, result in evaluation.predicate_evaluations.items()
    ]
    used_fact_ids = list(evaluation.trigger.used_fact_ids)
    if evaluation.exception is not None and evaluation.trigger.truth == TruthValue.TRUE:
        used_fact_ids.extend(evaluation.exception.used_fact_ids)
    used_fact_ids = list(dict.fromkeys(used_fact_ids))
    return value.model_copy(
        update={
            "used_fact_ids": used_fact_ids,
            "evidence_span_ids": list(
                dict.fromkeys(
                    span_id
                    for fact_id in used_fact_ids
                    for span_id in facts_by_id[fact_id].evidence_span_ids
                )
            ),
            "predicate_observations": observations,
            "processed_predicate_ids": [item.predicate_id for item in observations],
            "missing_predicate_ids": [
                item.predicate_id
                for item in observations
                if item.truth == TruthValue.UNKNOWN
            ],
        }
    )


def publish_test_assessment(
    value: AssessmentCandidate,
    *,
    component: RuleComponent,
    facts: list[ClinicalFact],
    rule_kind: RuleKind = RuleKind.EXCLUSION,
    expectations: list[EvidenceExpectation] | None = None,
    conflicts: list[ConflictGroup] | None = None,
    stage: ReviewStage = ReviewStage.SCREENING,
) -> AssessmentPublication:
    call = eligibility_call()
    evidence_call = evidence_normalizer_call()
    spans = [
        evidence_span(span_id)
        for span_id in dict.fromkeys(
            span_id for fact in facts for span_id in fact.evidence_span_ids
        )
    ]
    candidate_gate = publish_assessment_candidate_acceptance(
        value,
        agent_call=call,
        agent_call_gate_result=agent_call_gate(call),
        gate_result_id=f"gate-{value.assessment_candidate_id}",
        created_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
    )
    normalized = evidence_candidate(facts, spans)
    evidence_gate = publish_evidence_acceptance(
        candidate=normalized,
        agent_call=evidence_call,
        agent_call_gate_result=agent_call_gate(evidence_call),
        gate_result_id="gate-evidence-1",
        input_revision_map={"episode-1": 1},
        created_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
    )
    return publish_assessment(
        value,
        agent_call=call,
        agent_call_gate_result=agent_call_gate(call),
        candidate_gate_result=candidate_gate,
        evidence_gate_result=evidence_gate,
        evidence_candidate=normalized,
        evidence_agent_call=evidence_call,
        evidence_agent_call_gate_result=agent_call_gate(evidence_call),
        component=component,
        rule_kind=rule_kind,
        facts=facts,
        evidence_spans=spans,
        anchor_dates={},
        episode_stage=stage,
        expectations=expectations or [],
        conflict_groups=conflicts or [],
        assessment_id="assessment-test-1",
        gate_result_id="gate-assessment-test-1",
        input_revision_map={"episode-1": 1},
        created_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
    )


def decision_for_action_gap(gap: GapType) -> ComponentDecision:
    return (
        ComponentDecision.PROFESSIONAL_JUDGMENT
        if gap == GapType.PROFESSIONAL_JUDGMENT
        else ComponentDecision.CONFLICT
        if gap in {GapType.SOURCE_CONFLICT, GapType.INTERPRETATION_CONFLICT}
        else ComponentDecision.NOT_DUE
        if gap == GapType.FUTURE_STAGE_NOT_DUE
        else ComponentDecision.EXCLUSION_NOT_TRIGGERED
        if gap == GapType.PROVENANCE_FOLLOWUP
        else ComponentDecision.INDETERMINATE
    )


def action_source_assessment(gap: GapType) -> AssessmentPublication:
    return assessment_publication(final_assessment(decision_for_action_gap(gap), [gap]))


def action_request(gap: GapType) -> ActionPublication:
    assessment_input = assessment_publication(
        final_assessment(decision_for_action_gap(gap), [gap])
    )
    return publish_action_request(
        assessment_publication=assessment_input,
        action_id=f"action-{gap.value}",
        rule_component_id="component-1",
        gap_type=gap,
        target_party=ActionTarget.INVESTIGATOR,
        requested_action="补充可核对的信息",
        acceptable_evidence="含日期及来源定位的记录",
        due_stage=ReviewStage.BASELINE,
        state=ActionState.OPEN,
        recompute_scope=["component-1"],
        gate_result_id=f"gate-action-{gap.value}",
        input_revision_map={"episode-1": 1},
        created_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
    )


def episode_rollup(assessments, expectations, actions):
    assessment_publications = [
        item if isinstance(item, AssessmentPublication) else assessment_publication(item)
        for item in assessments
    ]
    action_publications = []
    for action in actions:
        if isinstance(action, ActionPublication):
            action_publications.append(action)
            continue
        gate = GateResult(
            gate_result_id=action.gate_result_id,
            gate_name="action-publication-gate",
            result="accepted",
            input_scope_hash="b" * 64,
            input_revision_map={"episode-1": 1},
            input_entity_refs=[action.assessment_id],
            accepted_entity_refs=[action.action_id],
            affected_scope=[action.rule_component_id],
            recompute_scope=[action.rule_component_id],
            idempotency_key=f"test:{action.action_id}",
            created_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
            output_hash=canonical_hash(action.model_dump(mode="json")),
        )
        action_publications.append(ActionPublication(action=action, gate_result=gate))
    return publish_episode_rollup(
        review_episode_id="episode-1",
        assessment_publications=assessment_publications,
        expectations=expectations,
        action_publications=action_publications,
        gate_result_id="gate-rollup-1",
        input_revision_map={"episode-1": 1},
        created_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
    ).rollup


def test_rule_expression_preserves_all_any_not_and_professional_judgment() -> None:
    expression = LogicalExpression(
        operator=LogicalOperator.ALL,
        children=[
            AtomicExpression(
                predicate=AtomicPredicate(
                    subject="laboratory",
                    attribute="abnormal",
                    comparator="eq",
                    value=True,
                )
            ),
            LogicalExpression(
                operator=LogicalOperator.ANY,
                children=[
                    AtomicExpression(
                        predicate=AtomicPredicate(
                            subject="investigator",
                            attribute="unacceptable_risk",
                            comparator="eq",
                            value=True,
                            requires_professional_judgment=True,
                        )
                    ),
                    LogicalExpression(
                        operator=LogicalOperator.NOT,
                        children=[
                            AtomicExpression(
                                predicate=AtomicPredicate(
                                    subject="exception",
                                    attribute="documented",
                                    comparator="eq",
                                    value=True,
                                )
                            )
                        ],
                    ),
                ],
            ),
        ],
    )
    dumped = expression.model_dump(mode="json")
    assert dumped["operator"] == "all"
    assert dumped["children"][1]["operator"] == "any"
    assert dumped["children"][1]["children"][1]["operator"] == "not"


def test_rule_expression_all_any_not_have_distinct_truth_semantics() -> None:
    predicates = [
        AtomicExpression(predicate=AtomicPredicate(subject="x", attribute="a", comparator="eq", value=True)),
        AtomicExpression(predicate=AtomicPredicate(subject="x", attribute="b", comparator="eq", value=True)),
    ]
    context = evaluation_context(
        facts=[
            clinical_fact(
                fact_id="fact-a",
                fact_type="x.a",
                value=True,
                polarity=FactPolarity.AFFIRMED,
                certainty=1,
                evidence_span_ids=["span-1"],
            ),
            clinical_fact(
                fact_id="fact-b",
                fact_type="x.b",
                value=True,
                polarity=FactPolarity.NEGATED,
                certainty=1,
                evidence_span_ids=["span-2"],
            ),
        ]
    )

    assert evaluate_expression(
        LogicalExpression(operator=LogicalOperator.ALL, children=predicates), context
    ).truth == TruthValue.FALSE
    assert evaluate_expression(
        LogicalExpression(operator=LogicalOperator.ANY, children=predicates), context
    ).truth == TruthValue.TRUE
    assert evaluate_expression(
        LogicalExpression(operator=LogicalOperator.NOT, children=[predicates[0]]), context
    ).truth == TruthValue.FALSE


def test_indicator_identity_is_part_of_predicate_resolution() -> None:
    ggt = AtomicExpression(
        predicate=AtomicPredicate(
            subject="laboratory",
            attribute="ggt_multiple_of_uln",
            comparator="gte",
            value=1.5,
            unit="xULN",
        )
    )
    alt = AtomicExpression(
        predicate=AtomicPredicate(
            subject="laboratory",
            attribute="alt_multiple_of_uln",
            comparator="gte",
            value=1.5,
            unit="xULN",
        )
    )
    context = evaluation_context(
        facts=[
            clinical_fact(
                fact_id="fact-ggt",
                fact_type="laboratory.ggt_multiple_of_uln",
                value=1.8,
                unit="xULN",
                polarity=FactPolarity.AFFIRMED,
                certainty=1,
                evidence_span_ids=["span-1"],
            )
        ]
    )

    assert evaluate_expression(ggt, context).truth == TruthValue.TRUE
    assert evaluate_expression(alt, context).truth == TruthValue.UNKNOWN


def test_negated_fact_and_unrecorded_fact_are_distinct() -> None:
    base = {
        "fact_id": "fact-1",
        "fact_type": "history.heavy_alcohol_use",
        "certainty": 0.95,
        "evidence_span_ids": ["span-1"],
    }
    denied = clinical_fact(**base, value=True, polarity=FactPolarity.NEGATED)
    unrecorded = clinical_fact(**{**base, "fact_id": "fact-2"}, value=None, polarity=FactPolarity.UNKNOWN)

    assert denied.polarity != unrecorded.polarity
    assert denied.value is True
    assert unrecorded.value is None

    expression = AtomicExpression(
        predicate=AtomicPredicate(
            subject="history",
            attribute="heavy_alcohol_use",
            comparator="eq",
            value=True,
        )
    )
    assert evaluate_expression(expression, evaluation_context(facts=[denied])).truth == TruthValue.FALSE
    assert evaluate_expression(expression, evaluation_context(facts=[unrecorded])).truth == TruthValue.UNKNOWN


def test_fact_polarity_cannot_contradict_normalized_value() -> None:
    base = {
        "fact_id": "fact-contradiction",
        "fact_type": "history.prohibited_exposure",
        "certainty": 1,
        "evidence_span_ids": ["span-1"],
    }
    with pytest.raises(ValidationError, match="typed value"):
        clinical_fact(**base, value=None, polarity=FactPolarity.NEGATED)
    with pytest.raises(ValidationError, match="typed value"):
        clinical_fact(**base, value=None, polarity=FactPolarity.AFFIRMED)

    denied_named_condition = clinical_fact(
        **{
            **base,
            "fact_id": "fact-denied-diabetes",
            "fact_type": "history.condition_name",
        },
        value="diabetes",
        polarity=FactPolarity.NEGATED,
    )
    named_predicate = AtomicExpression(
        predicate=AtomicPredicate(
            subject="history",
            attribute="condition_name",
            comparator="eq",
            value="diabetes",
        )
    )
    assert evaluate_expression(
        named_predicate,
        evaluation_context(facts=[denied_named_condition]),
    ).truth == TruthValue.FALSE


def test_numeric_predicate_requires_explicit_unit_and_context_rejects_cross_scope_fact() -> None:
    with pytest.raises(ValidationError, match="数值谓词"):
        AtomicPredicate(
            subject="laboratory",
            attribute="result",
            comparator="gte",
            value=1.5,
        )
    unitless = AtomicPredicate(
        subject="score",
        attribute="total",
        comparator="gte",
        value=10,
        unit="unitless",
    )
    assert unitless.unit == "unitless"

    fact = clinical_fact(
        fact_id="fact-other-subject",
        fact_type="history.event_present",
        value=True,
        polarity=FactPolarity.AFFIRMED,
        certainty=1,
        evidence_span_ids=["span-1"],
    ).model_copy(update={"subject_id": "subject-other"})
    with pytest.raises(ValidationError, match="超出当前"):
        evaluation_context(facts=[fact])


def test_exception_tree_is_not_merged_into_trigger_tree() -> None:
    component = RuleComponent(
        rule_component_id="component-1",
        parent_rule_id="rule-ex-01",
        display_code="EX-01a",
        title="合成例外结构",
        expression=AtomicExpression(
            predicate=AtomicPredicate(
                subject="infection",
                attribute="specific_antibody_positive",
                comparator="eq",
                value=True,
            )
        ),
        exception_expression=LogicalExpression(
            operator=LogicalOperator.ALL,
            children=[
                AtomicExpression(
                    predicate=AtomicPredicate(
                        subject="infection",
                        attribute="nonspecific_antibody_negative",
                        comparator="eq",
                        value=True,
                    )
                ),
                AtomicExpression(
                    predicate=AtomicPredicate(
                        subject="investigator",
                        attribute="prior_infection_cured",
                        comparator="eq",
                        value=True,
                        requires_professional_judgment=True,
                    )
                ),
            ],
        ),
    )
    assert component.expression.kind == "predicate"
    assert component.exception_expression is not None
    assert component.exception_expression.kind == "logical"


def test_randomization_and_baseline_anchors_are_not_screening_date() -> None:
    randomization = TimeConstraint(
        anchor_type="randomization_date",
        direction="before",
        lower_bound_days=28,
    )
    baseline = TimeConstraint(
        anchor_type="baseline_date",
        direction="before",
        lower_bound_days=28,
    )
    screening = TimeConstraint(
        anchor_type="screening_date",
        direction="before",
        lower_bound_days=28,
    )
    assert randomization.anchor_type != screening.anchor_type
    assert baseline.anchor_type != screening.anchor_type


@pytest.mark.parametrize(
    ("distance_days", "expected"),
    [(27, TruthValue.FALSE), (28, TruthValue.TRUE), (29, TruthValue.TRUE)],
)
def test_time_window_uses_explicit_randomization_anchor_and_boundaries(
    distance_days,
    expected,
) -> None:
    expression = AtomicExpression(
        predicate=AtomicPredicate(
            subject="medication",
            attribute="prohibited_exposure",
            comparator="eq",
            value=True,
        ),
        time_constraint=TimeConstraint(
            anchor_type="randomization_date",
            direction="before",
            lower_bound_days=28,
        ),
    )
    event_date = date(2026, 8, 31).fromordinal(date(2026, 8, 31).toordinal() - distance_days)
    fact = clinical_fact(
        fact_id="fact-medication",
        fact_type="medication.prohibited_exposure",
        value=True,
        polarity=FactPolarity.AFFIRMED,
        certainty=1,
        effective_date=DateValue(value=event_date, precision=DatePrecision.DAY),
        evidence_span_ids=["span-1"],
    )
    context = evaluation_context(
        facts=[fact],
        anchor_dates={
            "randomization_date": DateValue(
                value=date(2026, 8, 31), precision=DatePrecision.DAY
            )
        },
    )
    assert evaluate_expression(expression, context).truth == expected

    missing_anchor = evaluation_context(
        facts=[fact],
        anchor_dates={
            "screening_date": DateValue(
                value=date(2026, 8, 31), precision=DatePrecision.DAY
            )
        },
    )
    result = evaluate_expression(expression, missing_anchor)
    assert result.truth == TruthValue.UNKNOWN
    assert "date_or_anchor_missing" in result.reason_codes


def test_unit_mismatch_and_silent_fact_do_not_become_false_or_pass() -> None:
    expression = AtomicExpression(
        predicate=AtomicPredicate(
            subject="laboratory",
            attribute="target_ratio_uln",
            comparator="gte",
            value=1.5,
            unit="xULN",
        )
    )
    silent = evaluate_expression(expression, evaluation_context())
    assert silent.truth == TruthValue.UNKNOWN
    mismatch = evaluate_expression(
        expression,
        evaluation_context(
            facts=[
                clinical_fact(
                    fact_id="fact-lab",
                    fact_type="laboratory.target_ratio_uln",
                    value=2.0,
                    unit="mg/L",
                    polarity=FactPolarity.AFFIRMED,
                    certainty=1,
                    evidence_span_ids=["span-1"],
                )
            ]
        ),
    )
    assert mismatch.truth == TruthValue.UNKNOWN
    assert "unit_mismatch" in mismatch.reason_codes


def test_comparator_mutation_changes_boundary_result() -> None:
    context = evaluation_context(
        facts=[
            clinical_fact(
                fact_id="fact-threshold",
                fact_type="laboratory.target_ratio_uln",
                value=1.5,
                unit="xULN",
                polarity=FactPolarity.AFFIRMED,
                certainty=1,
                evidence_span_ids=["span-1"],
            )
        ]
    )
    gte = AtomicExpression(
        predicate=AtomicPredicate(
            subject="laboratory",
            attribute="target_ratio_uln",
            comparator="gte",
            value=1.5,
            unit="xULN",
        )
    )
    gt = gte.model_copy(
        update={"predicate": gte.predicate.model_copy(update={"comparator": "gt"})}
    )
    assert evaluate_expression(gte, context).truth == TruthValue.TRUE
    assert evaluate_expression(gt, context).truth == TruthValue.FALSE


def test_partial_date_window_is_only_definitive_when_entire_interval_agrees() -> None:
    expression = AtomicExpression(
        predicate=AtomicPredicate(
            subject="history",
            attribute="event_present",
            comparator="eq",
            value=True,
        ),
        time_constraint=TimeConstraint(
            anchor_type="randomization_date",
            direction="before",
            lower_bound_days=28,
            allow_partial_date=True,
        ),
    )
    fact = clinical_fact(
        fact_id="fact-partial-date",
        fact_type="history.event_present",
        value=True,
        polarity=FactPolarity.AFFIRMED,
        certainty=1,
        effective_date=DateValue(
            value=date(2026, 8, 1),
            precision=DatePrecision.MONTH,
            source_text="2026年8月",
        ),
        evidence_span_ids=["span-1"],
    )
    context = evaluation_context(
        facts=[fact],
        anchor_dates={
            "randomization_date": DateValue(
                value=date(2026, 9, 15), precision=DatePrecision.DAY
            )
        },
    )
    result = evaluate_expression(expression, context)
    assert result.truth == TruthValue.UNKNOWN
    assert "ambiguous_time_window" in result.reason_codes


def test_logical_arity_and_time_window_are_rejected() -> None:
    with pytest.raises(ValidationError, match="ALL/ANY"):
        LogicalExpression(
            operator=LogicalOperator.ALL,
            children=[AtomicExpression(predicate=AtomicPredicate(subject="x", attribute="y", comparator="exists"))],
        )


def test_predicate_comparator_value_shape_is_enforced() -> None:
    with pytest.raises(ValidationError, match="exists"):
        AtomicPredicate(subject="x", attribute="y", comparator="exists", value=True)
    with pytest.raises(ValidationError, match="必须提供 value"):
        AtomicPredicate(subject="x", attribute="y", comparator="eq")
    with pytest.raises(ValidationError, match="值列表"):
        AtomicPredicate(subject="x", attribute="y", comparator="in", value="a")
    with pytest.raises(ValidationError, match="下界"):
        TimeConstraint(
            anchor_type="randomization_date",
            direction="before",
            lower_bound_days=30,
            upper_bound_days=7,
        )


@pytest.mark.parametrize(
    ("precision", "kwargs"),
    [
        (LocatorPrecision.BBOX, {"bbox": BoundingBox(x0=1, y0=1, x1=2, y1=2)}),
        (LocatorPrecision.TEXT_RANGE, {"text_start": 1, "text_end": 5}),
        (LocatorPrecision.PAGE_EXCERPT, {"excerpt": "合成页面摘录"}),
        (LocatorPrecision.PAGE_ONLY, {"degradation_reason": "当前解析器只返回页码"}),
    ],
)
def test_evidence_locator_precision_is_explicit(precision, kwargs) -> None:
    span = EvidenceSpan(
        evidence_span_id=f"span-{precision.value}",
        source_document_version_id="document-1",
        page_number=1,
        precision=precision,
        locator_algorithm_version="locator-v1",
        **kwargs,
    )
    assert span.precision == precision


def test_page_only_requires_degradation_reason() -> None:
    with pytest.raises(ValidationError, match="降级原因"):
        EvidenceSpan(
            evidence_span_id="span-1",
            source_document_version_id="document-1",
            page_number=1,
            precision=LocatorPrecision.PAGE_ONLY,
            locator_algorithm_version="locator-v1",
        )


def test_evidence_locator_cannot_claim_multiple_precision_layers() -> None:
    with pytest.raises(ValidationError, match="字符范围"):
        EvidenceSpan(
            evidence_span_id="span-mixed",
            source_document_version_id="document-1",
            page_number=1,
            precision=LocatorPrecision.BBOX,
            bbox=BoundingBox(x0=1, y0=1, x1=2, y1=2),
            text_start=1,
            text_end=2,
            locator_algorithm_version="locator-v1",
        )


def test_evidence_snapshot_full_and_incremental_lineage_are_distinct() -> None:
    base = {
        "evidence_snapshot_id": "snapshot-1",
        "subject_id": "subject-1",
        "review_episode_id": "episode-1",
        "source_document_version_ids": ["document-1"],
        "created_at": "2026-08-12T12:00:00Z",
    }
    assert EvidenceSnapshot(**base, upload_mode=UploadMode.FULL).prior_snapshot_id is None
    with pytest.raises(ValidationError, match="增量快照"):
        EvidenceSnapshot(**base, upload_mode=UploadMode.INCREMENTAL)
    with pytest.raises(ValidationError, match="全量快照"):
        EvidenceSnapshot(**base, upload_mode=UploadMode.FULL, prior_snapshot_id="snapshot-0")


def test_unknown_fact_cannot_smuggle_typed_value_or_unit() -> None:
    with pytest.raises(ValidationError, match="未知极性事实"):
        clinical_fact(
            fact_id="fact-unknown-with-value",
            fact_type="laboratory.alt",
            value=76.1,
            unit="U/L",
            polarity=FactPolarity.UNKNOWN,
            certainty=0.5,
            evidence_span_ids=["span-1"],
        )


@pytest.mark.parametrize(
    "invalid_field",
    ["lower_bound_days", "upper_bound_days", "half_life_multiplier"],
)
def test_on_time_constraint_rejects_window_and_half_life_parameters(invalid_field) -> None:
    with pytest.raises(ValidationError, match="on 仅表示"):
        TimeConstraint(
            anchor_type="baseline_date",
            direction=TimeDirection.ON,
            **{invalid_field: 1},
        )


def test_rule_set_rejects_parent_phase_and_kind_prefix_drift() -> None:
    expression = AtomicExpression(
        predicate=AtomicPredicate(subject="x", attribute="present", comparator="eq", value=True)
    )

    def build_rule(**changes):
        component = RuleComponent(
            rule_component_id="component-1",
            parent_rule_id=changes.pop("parent_rule_id", "rule-1"),
            display_code="IN-01a",
            title="合成组件",
            expression=expression,
        )
        return Rule(
            rule_id="rule-1",
            official_code=changes.pop("official_code", "IN-01"),
            kind=changes.pop("kind", RuleKind.INCLUSION),
            source_text="合成规则原文",
            study_phase=changes.pop("study_phase", StudyPhase.PHASE_III),
            components=[component],
            **changes,
        )

    RuleSet(
        rule_set_id="rules-1",
        protocol_version_id="protocol-1",
        study_phase=StudyPhase.PHASE_III,
        rules=[build_rule()],
    )
    with pytest.raises(ValidationError, match="parent_rule_id"):
        RuleSet(
            rule_set_id="rules-1",
            protocol_version_id="protocol-1",
            study_phase=StudyPhase.PHASE_III,
            rules=[build_rule(parent_rule_id="rule-other")],
        )
    with pytest.raises(ValidationError, match="编号前缀"):
        RuleSet(
            rule_set_id="rules-1",
            protocol_version_id="protocol-1",
            study_phase=StudyPhase.PHASE_III,
            rules=[build_rule(official_code="EX-01")],
        )
    with pytest.raises(ValidationError, match="规则期别"):
        RuleSet(
            rule_set_id="rules-1",
            protocol_version_id="protocol-1",
            study_phase=StudyPhase.PHASE_II,
            rules=[build_rule()],
        )


@pytest.mark.parametrize(
    ("decision", "gaps", "blocking"),
    [
        (ComponentDecision.INCLUSION_MET, [], BlockingLevel.NONE),
        (ComponentDecision.INCLUSION_NOT_MET, [], BlockingLevel.NONE),
        (ComponentDecision.EXCLUSION_NOT_TRIGGERED, [GapType.PROVENANCE_FOLLOWUP], BlockingLevel.ATTENTION),
        (ComponentDecision.EXCLUSION_TRIGGERED, [], BlockingLevel.NONE),
        (ComponentDecision.INDETERMINATE, [GapType.RECORD_INCOMPLETE], BlockingLevel.BLOCKING),
        (ComponentDecision.PROFESSIONAL_JUDGMENT, [GapType.PROFESSIONAL_JUDGMENT], BlockingLevel.BLOCKING),
        (ComponentDecision.CONFLICT, [GapType.SOURCE_CONFLICT], BlockingLevel.BLOCKING),
        (ComponentDecision.NOT_DUE, [GapType.FUTURE_STAGE_NOT_DUE], BlockingLevel.ATTENTION),
        (ComponentDecision.NOT_APPLICABLE, [], BlockingLevel.NONE),
        (ComponentDecision.REQUIREMENT_MET, [], BlockingLevel.NONE),
        (
            ComponentDecision.REQUIREMENT_NOT_MET,
            [GapType.REQUIRED_PROCEDURE_NOT_DONE],
            BlockingLevel.BLOCKING,
        ),
    ],
)
def test_assessment_gate_accepts_state_gap_matrix(decision, gaps, blocking) -> None:
    assessment = final_assessment(decision, gaps)
    assert assessment.decision == decision
    assert assessment.blocking_level == blocking


@pytest.mark.parametrize(
    ("decision", "gaps"),
    [
        (ComponentDecision.INCLUSION_MET, [GapType.RECORD_INCOMPLETE]),
        (ComponentDecision.INDETERMINATE, []),
        (ComponentDecision.PROFESSIONAL_JUDGMENT, [GapType.RECORD_INCOMPLETE]),
        (ComponentDecision.CONFLICT, [GapType.DESCRIPTION_INSUFFICIENT]),
        (ComponentDecision.NOT_DUE, []),
    ],
)
def test_assessment_gate_rejects_invalid_state_gap_matrix(decision, gaps) -> None:
    with pytest.raises((ValueError, ValidationError)):
        final_assessment(decision, gaps)


def test_agent_call_node_scope_and_retry_budget_are_enforced() -> None:
    base = {
        "agent_call_id": "call-1",
        "node": AgentNode.ELIGIBILITY_ASSESSOR,
        "output_kind": AgentOutputKind.CANDIDATE,
        "write_scope": AgentWriteScope.ASSESSMENT_CANDIDATE,
        "prompt_version_id": "prompt-1",
        "model_config_id": "model-1",
        "input_scope_hash": "a" * 64,
        "input_revision_map": {"snapshot-1": 1},
        "raw_output_hash": "b" * 64,
        "output_hash": "c" * 64,
        "idempotency_key": "episode-1:component-1",
        "attempt": 1,
        "max_attempts": 2,
        "duration_ms": 100,
        "started_at": datetime(2026, 8, 12, tzinfo=timezone.utc),
        "finished_at": datetime(2026, 8, 12, tzinfo=timezone.utc),
        "outcome": "accepted",
        "recompute_scope": ["component-1"],
        "trigger": "manual_test",
        "project_id": "project-1",
        "protocol_version_id": "protocol-1",
        "rule_set_id": "ruleset-1",
        "rule_set_revision": 1,
        "subject_id": "subject-1",
        "review_episode_id": "episode-1",
        "review_run_id": "run-1",
        "evidence_snapshot_id": "snapshot-1",
        "source_ids": ["document-1"],
        "gate_result_ids": ["gate-call-1"],
    }
    assert AgentCallContract(**base).node == AgentNode.ELIGIBILITY_ASSESSOR
    with pytest.raises(ValidationError, match="写入范围"):
        AgentCallContract(**{**base, "write_scope": AgentWriteScope.EVIDENCE_CANDIDATE})
    with pytest.raises(ValidationError, match="attempt"):
        AgentCallContract(**{**base, "attempt": 3})
    with pytest.raises(ValidationError, match="Subject/Episode/Run/Snapshot/Source"):
        AgentCallContract(**{**base, "subject_id": None})
    with pytest.raises(ValidationError):
        AgentCallContract(**{**base, "gate_result_ids": []})


def test_eligibility_output_rejects_cross_scope_or_cross_call_candidate() -> None:
    value = candidate(ComponentDecision.EXCLUSION_NOT_TRIGGERED, [])
    base = {
        "project_id": "project-1",
        "protocol_version_id": "protocol-1",
        "subject_id": "subject-1",
        "rule_set_id": "ruleset-1",
        "rule_set_revision": 1,
        "review_episode_id": "episode-1",
        "review_run_id": "run-1",
        "evidence_snapshot_id": "snapshot-1",
        "candidates": [value],
        "coverage": CoverageSummary(),
        "created_by_agent_call_id": "call-1",
    }
    EligibilityAssessmentOutput(**base)
    forged = value.model_copy(update={"subject_id": "subject-other"})
    with pytest.raises(ValidationError, match="scope/call"):
        EligibilityAssessmentOutput(**{**base, "candidates": [forged]})


def test_agent_cannot_publish_final_state_or_action() -> None:
    require_agent_write_permission(AgentNode.ELIGIBILITY_ASSESSOR, "assessment_candidate")
    for forbidden in ("final_assessment", "action_request", "episode_rollup"):
        with pytest.raises(AgentPermissionError):
            require_agent_write_permission(
                AgentNode.ELIGIBILITY_ASSESSOR,
                cast(AgentPublishedEntity, forbidden),
            )


def test_candidate_gate_requires_accepted_agent_call_closure() -> None:
    call = eligibility_call()
    rejected_call_gate = agent_call_gate(call).model_copy(
        update={
            "result": "rejected",
            "accepted_entity_refs": [],
            "rejected_entity_refs": [call.agent_call_id],
            "error_codes": ["schema_validation_failed"],
        }
    )
    with pytest.raises(AgentPermissionError, match="AgentCall 未通过"):
        publish_assessment_candidate_acceptance(
            candidate(ComponentDecision.EXCLUSION_NOT_TRIGGERED, []),
            agent_call=call,
            agent_call_gate_result=rejected_call_gate,
            gate_result_id="gate-candidate-rejected-call",
            created_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
        )


def test_final_assessment_direct_construction_requires_gate_publication_fingerprint() -> None:
    with pytest.raises(ValidationError, match="publication_fingerprint"):
        FinalAssessment(
            assessment_id="assessment-invalid",
            project_id="project-1",
            protocol_version_id="protocol-1",
            subject_id="subject-1",
            rule_set_id="ruleset-1",
            rule_set_revision=1,
            review_episode_id="episode-1",
            evidence_snapshot_id="snapshot-1",
            review_run_id="run-1",
            rule_component_id="component-1",
            decision=ComponentDecision.INCLUSION_MET,
            gap_types=[GapType.RECORD_INCOMPLETE],
            blocking_level=BlockingLevel.BLOCKING,
            gate_result_id="gate-1",
        )


def test_gate_owned_publication_builder_is_not_public_api() -> None:
    assert not hasattr(publication_module, "build_published_model")


def test_assessment_gate_recomputes_and_rejects_wrong_agent_decision() -> None:
    component = gate_component()
    facts = [
        clinical_fact(
            fact_id="fact-condition-false",
            fact_type="history.condition_present",
            value=False,
            polarity=FactPolarity.AFFIRMED,
            certainty=1,
            evidence_span_ids=["span-condition-false"],
        )
    ]
    wrong = align_candidate(
        candidate(ComponentDecision.EXCLUSION_TRIGGERED, []), component, facts
    )
    with pytest.raises(AssessmentGateError, match="确定性结果"):
        publish_test_assessment(wrong, component=component, facts=facts)


def test_assessment_gate_rejects_forged_observed_value_unit_and_span() -> None:
    component = gate_component()
    facts = [
        clinical_fact(
            fact_id="fact-condition-false",
            fact_type="history.condition_present",
            value=False,
            polarity=FactPolarity.AFFIRMED,
            certainty=1,
            evidence_span_ids=["span-condition-false"],
        )
    ]
    aligned = align_candidate(
        candidate(ComponentDecision.EXCLUSION_NOT_TRIGGERED, []), component, facts
    )
    forged = aligned.model_copy(
        update={
            "predicate_observations": [
                aligned.predicate_observations[0].model_copy(
                    update={
                        "observed_value": 999,
                        "observed_unit": "wrong-unit",
                        "evidence_span_ids": ["unrelated-span"],
                    }
                )
            ]
        }
    )
    with pytest.raises(AssessmentGateError, match="Evaluator"):
        publish_test_assessment(forged, component=component, facts=facts)


def test_missing_exception_cannot_be_silently_treated_as_exclusion_triggered() -> None:
    component = gate_component(with_exception=True)
    facts = [
        clinical_fact(
            fact_id="fact-condition-true",
            fact_type="history.condition_present",
            value=True,
            polarity=FactPolarity.AFFIRMED,
            certainty=1,
            evidence_span_ids=["span-condition-true"],
        )
    ]
    aligned = align_candidate(
        candidate(
            ComponentDecision.INDETERMINATE,
            [GapType.RECORD_INCOMPLETE],
        ),
        component,
        facts,
    )
    publication = publish_test_assessment(aligned, component=component, facts=facts)
    assert publication.assessment.decision == ComponentDecision.INDETERMINATE


def test_future_component_remains_not_due_even_if_current_sources_conflict() -> None:
    requirement = EvidenceRequirement(
        requirement_id="requirement-future",
        rule_component_id="component-1",
        fact_type="history.condition_present",
        due_stage=ReviewStage.BASELINE,
        description="基线才到期的合成要求。",
    )
    component = gate_component(requirements=[requirement])
    facts = [
        clinical_fact(
            fact_id="fact-1",
            fact_type="history.condition_present",
            value=True,
            polarity=FactPolarity.AFFIRMED,
            certainty=1,
            evidence_span_ids=["span-1"],
            conflict_group_id="conflict-1",
        ),
        clinical_fact(
            fact_id="fact-2",
            fact_type="history.condition_present",
            value=False,
            polarity=FactPolarity.AFFIRMED,
            certainty=1,
            evidence_span_ids=["span-2"],
            conflict_group_id="conflict-1",
        ),
    ]
    expectation = EvidenceExpectation(
        expectation_id="expectation-future",
        requirement_id="requirement-future",
        review_episode_id="episode-1",
        status=ExpectationStatus.NOT_DUE,
        gap_type=GapType.FUTURE_STAGE_NOT_DUE,
    )
    aligned = align_candidate(
        candidate(ComponentDecision.NOT_DUE, [GapType.FUTURE_STAGE_NOT_DUE]),
        component,
        facts,
    )
    publication = publish_test_assessment(
        aligned,
        component=component,
        facts=facts,
        expectations=[expectation],
        conflicts=[
            ConflictGroup(
                conflict_group_id="conflict-1",
                fact_ids=["fact-1", "fact-2"],
                affected_rule_component_ids=["component-1"],
            )
        ],
    )
    assert publication.assessment.decision == ComponentDecision.NOT_DUE


def test_rollup_priority_counts_and_provenance_are_deterministic() -> None:
    assessments = [
        final_assessment(ComponentDecision.INCLUSION_NOT_MET, []),
        final_assessment(ComponentDecision.CONFLICT, [GapType.SOURCE_CONFLICT]),
        final_assessment(
            ComponentDecision.EXCLUSION_NOT_TRIGGERED,
            [GapType.PROVENANCE_FOLLOWUP],
        ),
    ]
    expectation = EvidenceExpectation(
        expectation_id="expectation-1",
        requirement_id="requirement-1",
        review_episode_id="episode-1",
        status=ExpectationStatus.NOT_DUE,
        gap_type=GapType.FUTURE_STAGE_NOT_DUE,
    )
    action = action_request(GapType.PROVENANCE_FOLLOWUP)
    result = episode_rollup(assessments, [expectation], [action])
    assert result.main_status == EpisodeMainStatus.CLEAR_BARRIER
    assert result.barrier_count == 1
    assert result.conflict_count == 1
    assert result.future_attention_count == 1
    assert result.provenance_followup_count == 1


@pytest.mark.parametrize(
    ("decision", "gaps", "expected"),
    [
        (ComponentDecision.INCLUSION_NOT_MET, [], EpisodeMainStatus.CLEAR_BARRIER),
        (ComponentDecision.INDETERMINATE, [GapType.RECORD_INCOMPLETE], EpisodeMainStatus.CURRENT_GAP),
        (ComponentDecision.CONFLICT, [GapType.SOURCE_CONFLICT], EpisodeMainStatus.CONFLICT),
        (
            ComponentDecision.PROFESSIONAL_JUDGMENT,
            [GapType.PROFESSIONAL_JUDGMENT],
            EpisodeMainStatus.PROFESSIONAL_JUDGMENT,
        ),
        (ComponentDecision.NOT_DUE, [GapType.FUTURE_STAGE_NOT_DUE], EpisodeMainStatus.FUTURE_ATTENTION),
        (ComponentDecision.INCLUSION_MET, [], EpisodeMainStatus.NO_CLEAR_BARRIER),
        (ComponentDecision.REQUIREMENT_MET, [], EpisodeMainStatus.NO_CLEAR_BARRIER),
        (
            ComponentDecision.REQUIREMENT_NOT_MET,
            [GapType.REQUIRED_PROCEDURE_NOT_DONE],
            EpisodeMainStatus.CURRENT_GAP,
        ),
    ],
)
def test_rollup_truth_table_covers_each_main_status(decision, gaps, expected) -> None:
    result = episode_rollup([final_assessment(decision, gaps)], [], [])
    assert result.main_status == expected


def test_rollup_precedence_is_stable_without_narrative_input() -> None:
    assessments = [
        final_assessment(ComponentDecision.INDETERMINATE, [GapType.RECORD_INCOMPLETE]),
        final_assessment(ComponentDecision.CONFLICT, [GapType.SOURCE_CONFLICT]),
        final_assessment(
            ComponentDecision.PROFESSIONAL_JUDGMENT,
            [GapType.PROFESSIONAL_JUDGMENT],
        ),
        final_assessment(ComponentDecision.NOT_DUE, [GapType.FUTURE_STAGE_NOT_DUE]),
    ]
    assert episode_rollup(assessments, [], []).main_status == EpisodeMainStatus.CURRENT_GAP
    assert episode_rollup(assessments[1:], [], []).main_status == EpisodeMainStatus.CONFLICT
    assert episode_rollup(assessments[2:], [], []).main_status == EpisodeMainStatus.PROFESSIONAL_JUDGMENT
    assert episode_rollup(assessments[3:], [], []).main_status == EpisodeMainStatus.FUTURE_ATTENTION


def test_rollup_rejects_accepted_assessment_from_another_episode() -> None:
    cross_episode_assessment = _build_gate_owned_model(
        FinalAssessment,
        entity_type="final_assessment",
        gate_result_id="gate-cross-episode-assessment",
        data={
            "assessment_id": "assessment-cross-episode",
            "project_id": "project-1",
            "protocol_version_id": "protocol-1",
            "subject_id": "subject-1",
            "rule_set_id": "ruleset-1",
            "rule_set_revision": 1,
            "review_episode_id": "episode-other",
            "evidence_snapshot_id": "snapshot-1",
            "review_run_id": "run-1",
            "rule_component_id": "component-1",
            "decision": ComponentDecision.INCLUSION_MET,
            "gap_types": [],
            "blocking_level": BlockingLevel.NONE,
            "used_fact_ids": ["fact-1"],
            "evidence_span_ids": ["span-1"],
        },
    )
    cross_episode_publication = assessment_publication(cross_episode_assessment)
    with pytest.raises(ValueError, match="跨 Episode"):
        publish_episode_rollup(
            review_episode_id="episode-1",
            assessment_publications=[cross_episode_publication],
            expectations=[],
            action_publications=[],
            gate_result_id="gate-rollup-cross-episode",
            input_revision_map={"episode-1": 1},
            created_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
        )


def test_rollup_uses_expectation_blocking_policy_for_weak_and_provenance_evidence() -> None:
    provenance = EvidenceExpectation(
        expectation_id="expectation-provenance",
        requirement_id="requirement-1",
        review_episode_id="episode-1",
        status=ExpectationStatus.OBSERVED_WEAK,
        evidence_span_ids=["span-1"],
        gap_type=GapType.PROVENANCE_FOLLOWUP,
    )
    ocr_risk = provenance.model_copy(
        update={
            "expectation_id": "expectation-ocr",
            "gap_type": GapType.OCR_OR_PARSE_RISK,
        }
    )
    historical_missing = provenance.model_copy(
        update={
            "expectation_id": "expectation-history-missing",
            "gap_type": GapType.HISTORICAL_SOURCE_UNAVAILABLE,
        }
    )
    assert episode_rollup([], [provenance], []).main_status == EpisodeMainStatus.NO_CLEAR_BARRIER
    assert episode_rollup([], [ocr_risk], []).main_status == EpisodeMainStatus.CURRENT_GAP
    assert episode_rollup([], [historical_missing], []).main_status == EpisodeMainStatus.CURRENT_GAP


def test_episode_rollup_direct_construction_cannot_bypass_status_precedence() -> None:
    with pytest.raises(ValidationError, match="主状态"):
        _build_gate_owned_model(
            EpisodeRollup,
            entity_type="episode_rollup",
            gate_result_id="gate-rollup-invalid",
            data={
                "review_episode_id": "episode-1",
                "input_assessment_ids": [],
                "input_expectation_ids": [],
                "input_action_ids": [],
                "main_status": EpisodeMainStatus.NO_CLEAR_BARRIER,
                "sort_rank": 5,
                "barrier_count": 1,
                "current_gap_count": 0,
                "conflict_count": 0,
                "professional_judgment_count": 0,
                "future_attention_count": 0,
                "provenance_followup_count": 0,
                "gap_counts": {},
            },
        )


def test_protocol_integrity_uses_authoritative_manifest_not_caller_codes() -> None:
    expression = AtomicExpression(
        predicate=AtomicPredicate(subject="x", attribute="present", comparator="eq", value=True)
    )
    rule = Rule(
        rule_id="rule-99",
        official_code="IN-99",
        kind=RuleKind.INCLUSION,
        source_text="合成规则原文",
        study_phase=StudyPhase.PHASE_III,
        components=[
            RuleComponent(
                rule_component_id="component-99",
                parent_rule_id="rule-99",
                display_code="IN-99a",
                title="合成组件",
                expression=expression,
            )
        ],
    )
    rules = RuleSet(
        rule_set_id="rules-99",
        protocol_version_id="protocol-1",
        study_phase=StudyPhase.PHASE_III,
        rules=[rule],
    )
    trusted_rule = Rule.model_validate(
        {
            **rule.model_dump(mode="json"),
            "rule_id": "rule-01",
            "official_code": "IN-01",
            "components": [
                {
                    **rule.components[0].model_dump(mode="json"),
                    "rule_component_id": "component-01",
                    "parent_rule_id": "rule-01",
                    "display_code": "IN-01a",
                }
            ],
        }
    )
    workflow = [
        WorkflowStage(
            workflow_stage_id="stage-screening",
            stage=ReviewStage.SCREENING,
            display_name="筛选期",
        )
    ]
    authority = build_protocol_authority_record(
        authority_record_id="authority-1",
        protocol_version_id="protocol-1",
        protocol_document_sha256="a" * 64,
        study_phase=StudyPhase.PHASE_III,
        official_rules=[trusted_rule],
        official_workflow_stages=workflow,
        rule_source_anchor_refs={"IN-01": ["protocol-1:p1"]},
        verified_by="test-reviewer",
        verified_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
    )
    authority_gate = publish_protocol_authority_acceptance(
        authority,
        gate_result_id="gate-authority-1",
        created_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
    )
    manifest = build_protocol_integrity_manifest(
        manifest_id="manifest-1",
        protocol_version_id="protocol-1",
        protocol_document_sha256="a" * 64,
        study_phase=StudyPhase.PHASE_III,
        source_refs=["protocol-1:p1"],
        authority_record=authority,
        authority_gate_result=authority_gate,
    )
    protocol = ProtocolDocumentVersion(
        protocol_version_id="protocol-1",
        protocol_code="SYN-1",
        official_version="V1.0",
        official_date=DateValue(value=date(2026, 8, 1), precision=DatePrecision.DAY),
        sha256="a" * 64,
        integrity_manifest_sha256=manifest.manifest_sha256,
        authority_record_sha256=authority.authority_record_sha256,
        authority_gate_result_id=authority_gate.gate_result_id,
        integrity_gate_result_id="gate-integrity-1",
    )
    with pytest.raises(ValueError, match="官方规则编号"):
        assert_protocol_integrity(
            rules,
            workflow_stages=workflow,
            protocol_version=protocol,
            manifest=manifest,
            authority_record=authority,
            authority_gate_result=authority_gate,
        )


def test_protocol_manifest_rejects_due_stage_drift() -> None:
    requirement = EvidenceRequirement(
        requirement_id="requirement-baseline",
        rule_component_id="component-1",
        fact_type="laboratory.baseline_result",
        due_stage=ReviewStage.BASELINE,
        description="基线必做结果。",
    )
    component = gate_component(requirements=[requirement])
    rule = Rule(
        rule_id="rule-1",
        official_code="EX-01",
        kind=RuleKind.EXCLUSION,
        source_text="合成到期阶段测试。",
        study_phase=StudyPhase.PHASE_III,
        components=[component],
    )
    wrong_workflow = [
        WorkflowStage(
            workflow_stage_id="stage-screening",
            stage=ReviewStage.SCREENING,
            display_name="筛选期",
            due_requirement_ids=[requirement.requirement_id],
        )
    ]
    with pytest.raises(ValidationError, match="due_stage"):
        build_protocol_authority_record(
            authority_record_id="authority-due-drift",
            protocol_version_id="protocol-1",
            protocol_document_sha256="a" * 64,
            study_phase=StudyPhase.PHASE_III,
            official_rules=[rule],
            official_workflow_stages=wrong_workflow,
            rule_source_anchor_refs={"EX-01": ["protocol-1:p1"]},
            verified_by="test-reviewer",
            verified_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize(
    ("gap", "expected"),
    [
        (
            gap,
            BlockingLevel.NONE
            if gap == GapType.PROVENANCE_FOLLOWUP
            else BlockingLevel.ATTENTION
            if gap == GapType.FUTURE_STAGE_NOT_DUE
            else BlockingLevel.BLOCKING,
        )
        for gap in GapType
    ],
)
def test_action_blocking_level_is_deterministic(gap, expected) -> None:
    assert derive_action_blocking_level(gap) == expected
    publication = action_request(gap)
    source_assessment = action_source_assessment(gap)
    assert (
        validate_action_publication(
            publication,
            assessment_publication=source_assessment,
        )
        == publication.gate_result
    )
    invalid = publication.action.model_copy(
        update={
            "blocking_level": (
                BlockingLevel.NONE
                if expected != BlockingLevel.NONE
                else BlockingLevel.BLOCKING
            )
        }
    )
    with pytest.raises((ActionGateError, ValidationError)):
        validate_action_publication(
            ActionPublication(action=invalid, gate_result=publication.gate_result),
            assessment_publication=source_assessment,
        )


def test_action_direct_construction_cannot_bypass_blocking_policy() -> None:
    with pytest.raises(ValidationError):
        ActionRequest(
            action_id="action-invalid",
            rule_component_id="component-1",
            gap_type=GapType.PROVENANCE_FOLLOWUP,
            target_party=ActionTarget.CRA,
            requested_action="核对来源",
            acceptable_evidence="来源核对记录",
            due_stage=ReviewStage.BASELINE,
            blocking_level=BlockingLevel.BLOCKING,
            state=ActionState.OPEN,
            recompute_scope=["component-1"],
            gate_result_id="gate-action-invalid",
        )


def test_date_value_does_not_accept_known_precision_without_date() -> None:
    with pytest.raises(ValidationError):
        DateValue(precision=DatePrecision.DAY)
    assert DateValue(value=date(2026, 8, 12), precision=DatePrecision.DAY).value == date(2026, 8, 12)
