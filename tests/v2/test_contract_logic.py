from __future__ import annotations

from datetime import date
from typing import cast

import pytest
from pydantic import ValidationError

from app.domain.contracts.agents import AgentCallContract, AgentPublishedEntity
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
    UploadMode,
)
from app.domain.contracts.evidence import (
    BoundingBox,
    ClinicalFact,
    EvidenceExpectation,
    EvidenceSnapshot,
    EvidenceSpan,
)
from app.domain.contracts.review import ActionRequest, AssessmentCandidate
from app.domain.contracts.rules import (
    AtomicExpression,
    AtomicPredicate,
    LogicalExpression,
    RuleComponent,
    Rule,
    RuleSet,
    TimeConstraint,
)
from app.domain.expression import evaluate_expression
from app.domain.gates import (
    ActionGateError,
    AgentPermissionError,
    AssessmentGateError,
    derive_action_blocking_level,
    publish_assessment,
    require_agent_write_permission,
    validate_action_request,
)
from app.domain.rollup import rollup_episode


def candidate(decision: ComponentDecision, gaps: list[GapType]) -> AssessmentCandidate:
    return AssessmentCandidate(
        assessment_candidate_id="candidate-1",
        agent_call_id="call-1",
        rule_component_id="component-1",
        proposed_decision=decision,
        gap_types=gaps,
        used_fact_ids=["fact-1"],
        evidence_span_ids=["span-1"],
        candidate_rationale="合成测试候选，不参与确定性逻辑。",
    )


def final_assessment(decision: ComponentDecision, gaps: list[GapType]):
    return publish_assessment(
        candidate(decision, gaps),
        assessment_id=f"assessment-{decision.value}",
        review_run_id="run-1",
        gate_result_id="gate-1",
    )


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
    values = {"a": True, "b": False}
    resolve = lambda predicate: values[predicate.attribute]

    assert evaluate_expression(LogicalExpression(operator=LogicalOperator.ALL, children=predicates), resolve) is False
    assert evaluate_expression(LogicalExpression(operator=LogicalOperator.ANY, children=predicates), resolve) is True
    assert evaluate_expression(
        LogicalExpression(operator=LogicalOperator.NOT, children=[predicates[0]]), resolve
    ) is False


def test_indicator_identity_is_part_of_predicate_resolution() -> None:
    ggt = AtomicExpression(
        predicate=AtomicPredicate(
            subject="laboratory",
            attribute="ggt_multiple_of_uln",
            comparator="gte",
            value=1.5,
        )
    )
    alt = AtomicExpression(
        predicate=AtomicPredicate(
            subject="laboratory",
            attribute="alt_multiple_of_uln",
            comparator="gte",
            value=1.5,
        )
    )
    observed = {("laboratory", "ggt_multiple_of_uln"): True}
    resolve = lambda predicate: observed.get((predicate.subject, predicate.attribute), False)

    assert evaluate_expression(ggt, resolve) is True
    assert evaluate_expression(alt, resolve) is False


def test_negated_fact_and_unrecorded_fact_are_distinct() -> None:
    base = {
        "fact_id": "fact-1",
        "fact_type": "history.heavy_alcohol_use",
        "certainty": 0.95,
        "evidence_span_ids": ["span-1"],
    }
    denied = ClinicalFact(**base, value=False, polarity=FactPolarity.NEGATED)
    unrecorded = ClinicalFact(**{**base, "fact_id": "fact-2"}, value=None, polarity=FactPolarity.UNKNOWN)

    assert denied.polarity != unrecorded.polarity
    assert denied.value is False
    assert unrecorded.value is None


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
    with pytest.raises(AssessmentGateError):
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
        "raw_output_hash": "b" * 64,
        "idempotency_key": "episode-1:component-1",
        "attempt": 1,
        "max_attempts": 2,
        "duration_ms": 100,
    }
    assert AgentCallContract(**base).node == AgentNode.ELIGIBILITY_ASSESSOR
    with pytest.raises(ValidationError, match="写入范围"):
        AgentCallContract(**{**base, "write_scope": AgentWriteScope.EVIDENCE_CANDIDATE})
    with pytest.raises(ValidationError, match="attempt"):
        AgentCallContract(**{**base, "attempt": 3})


def test_agent_cannot_publish_final_state_or_action() -> None:
    require_agent_write_permission(AgentNode.ELIGIBILITY_ASSESSOR, "assessment_candidate")
    for forbidden in ("final_assessment", "action_request", "episode_rollup"):
        with pytest.raises(AgentPermissionError):
            require_agent_write_permission(
                AgentNode.ELIGIBILITY_ASSESSOR,
                cast(AgentPublishedEntity, forbidden),
            )


def test_rollup_priority_counts_and_provenance_are_deterministic() -> None:
    assessments = [
        final_assessment(ComponentDecision.INCLUSION_NOT_MET, []),
        final_assessment(ComponentDecision.CONFLICT, [GapType.SOURCE_CONFLICT]),
    ]
    expectation = EvidenceExpectation(
        expectation_id="expectation-1",
        requirement_id="requirement-1",
        review_episode_id="episode-1",
        status=ExpectationStatus.NOT_DUE,
        gap_type=GapType.FUTURE_STAGE_NOT_DUE,
    )
    action = ActionRequest(
        action_id="action-1",
        rule_component_id="component-1",
        gap_type=GapType.PROVENANCE_FOLLOWUP,
        target_party=ActionTarget.CRA,
        requested_action="后续核对来源",
        acceptable_evidence="来源链接或核对记录",
        due_stage=ReviewStage.BASELINE,
        blocking_level=BlockingLevel.NONE,
        state=ActionState.OPEN,
        recompute_scope=["component-1"],
    )
    result = rollup_episode(assessments, [expectation], [action])
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
    ],
)
def test_rollup_truth_table_covers_each_main_status(decision, gaps, expected) -> None:
    result = rollup_episode([final_assessment(decision, gaps)], [], [])
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
    assert rollup_episode(assessments, [], []).main_status == EpisodeMainStatus.CURRENT_GAP
    assert rollup_episode(assessments[1:], [], []).main_status == EpisodeMainStatus.CONFLICT
    assert rollup_episode(assessments[2:], [], []).main_status == EpisodeMainStatus.PROFESSIONAL_JUDGMENT
    assert rollup_episode(assessments[3:], [], []).main_status == EpisodeMainStatus.FUTURE_ATTENTION


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
    action = ActionRequest(
        action_id="action-1",
        rule_component_id="component-1",
        gap_type=gap,
        target_party=ActionTarget.INVESTIGATOR,
        requested_action="补充可核对的信息",
        acceptable_evidence="含日期及来源定位的记录",
        due_stage=ReviewStage.BASELINE,
        blocking_level=expected,
        state=ActionState.OPEN,
        recompute_scope=["component-1"],
    )
    validate_action_request(action)
    with pytest.raises(ActionGateError):
        validate_action_request(action.model_copy(update={"blocking_level": BlockingLevel.NONE if expected != BlockingLevel.NONE else BlockingLevel.BLOCKING}))


def test_date_value_does_not_accept_known_precision_without_date() -> None:
    with pytest.raises(ValidationError):
        DateValue(precision=DatePrecision.DAY)
    assert DateValue(value=date(2026, 8, 12), precision=DatePrecision.DAY).value == date(2026, 8, 12)
