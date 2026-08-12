#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
from datetime import date, datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from app.domain.contracts.agents import (
    AgentCallContract,
    GateResult,
    ModelConfigContract,
    PromptVersion,
)
from app.domain.contracts.agent_io import AgentContractsV1
from app.domain.contracts.api import (
    ActionOverrideCommand,
    ActionOverrideResponse,
    JobStatusResponse,
    ProjectListResponse,
    SubjectListResponse,
    WorkspaceResponse,
)
from app.domain.contracts.common import DateValue, ErrorEnvelope
from app.domain.contracts.enums import (
    ActionState,
    ActionTarget,
    AgentNode,
    AgentOutputKind,
    AgentWriteScope,
    BlockingLevel,
    ComponentDecision,
    DatePrecision,
    ExpectationStatus,
    FactPolarity,
    GateOutcome,
    GapType,
    LocatorPrecision,
    LogicalOperator,
    ProfileLane,
    ReviewStage,
    RuleKind,
    RunOutcome,
    StudyPhase,
    UploadMode,
)
from app.domain.contracts.evidence import (
    BoundingBox,
    ClinicalFact,
    ConflictGroup,
    EvidenceExpectation,
    EvidenceSnapshot,
    EvidenceSpan,
    PatientProfile,
    PatientProfileEvent,
    SourceDocumentVersion,
)
from app.domain.contracts.jobs import JobEvent
from app.domain.contracts.review import (
    ActionRequest,
    AssessmentCandidate,
    FixtureV1,
    Project,
    ProtocolDocumentVersion,
    ReviewEpisode,
    ReviewRun,
    PredicateObservation,
    Subject,
)
from app.domain.contracts.rules import (
    AtomicExpression,
    AtomicPredicate,
    EvidenceRequirement,
    LogicalExpression,
    Rule,
    RuleComponent,
    RuleSet,
    TimeConstraint,
    WorkflowStage,
    iter_atomic_predicates,
)
from app.domain.contracts.uat import ProtocolDiffExample, UatWorkspaceFixture
from app.domain.expression import EvaluationContext, evaluate_component, evaluate_expression
from app.domain.gates import (
    build_protocol_integrity_manifest,
    derive_component_decision,
    derive_gate_gap_types,
    publish_action_request,
    publish_assessment,
)
from app.domain.rollup import publish_episode_rollup
from app.domain.publication import canonical_hash


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = ROOT / "contracts" / "v1"
SCHEMA_ROOT = CONTRACT_ROOT / "schema"
FIXTURE_ROOT = CONTRACT_ROOT / "fixtures"
NOW = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def atomic_predicate(subject: str, attribute: str, comparator: str, value, **kwargs):
    return AtomicExpression(
        predicate=AtomicPredicate(
            predicate_id=kwargs.pop(
                "predicate_id",
                f"predicate-{subject}-{attribute}-{comparator}",
            ),
            subject=subject,
            attribute=attribute,
            comparator=comparator,
            value=value,
            **kwargs,
        )
    )


def clinical_fact_for(episode: ReviewEpisode, **kwargs) -> ClinicalFact:
    return ClinicalFact(
        project_id=episode.project_id,
        subject_id=episode.subject_id,
        review_episode_id=episode.review_episode_id,
        evidence_snapshot_id=episode.evidence_snapshot_id,
        **kwargs,
    )


def assessment_candidate_for(
    episode: ReviewEpisode,
    **kwargs,
) -> AssessmentCandidate:
    return AssessmentCandidate(
        review_episode_id=episode.review_episode_id,
        evidence_snapshot_id=episode.evidence_snapshot_id,
        processed_predicate_ids=[],
        candidate_confidence=0.9,
        **kwargs,
    )


def hydrate_candidate_observations(
    candidate: AssessmentCandidate,
    component: RuleComponent,
    context: EvaluationContext,
) -> AssessmentCandidate:
    facts_by_id = {fact.fact_id: fact for fact in context.facts}
    expressions = [component.expression]
    if component.exception_expression is not None:
        expressions.append(component.exception_expression)
    observations = []
    for expression in expressions:
        for predicate in iter_atomic_predicates(expression):
            atomic = next(
                item
                for item in _iter_atomic_expressions(expression)
                if item.predicate.predicate_id == predicate.predicate_id
            )
            result = evaluate_expression(atomic, context)
            used_facts = [
                facts_by_id[fact_id]
                for fact_id in result.used_fact_ids
                if fact_id in facts_by_id
            ]
            observed_value = used_facts[0].value if len(used_facts) == 1 else None
            observed_unit = used_facts[0].unit if len(used_facts) == 1 else None
            observations.append(
                PredicateObservation(
                    predicate_id=predicate.predicate_id,
                    truth=result.truth,
                    observed_value=observed_value,
                    observed_unit=observed_unit,
                    fact_ids=result.used_fact_ids,
                    evidence_span_ids=list(
                        dict.fromkeys(
                            span_id
                            for fact in used_facts
                            for span_id in fact.evidence_span_ids
                        )
                    ),
                    reason_codes=result.reason_codes,
                )
            )
    processed_ids = [item.predicate_id for item in observations]
    reason_codes = list(
        dict.fromkeys(code for item in observations for code in item.reason_codes)
    )
    return candidate.model_copy(
        update={
            "predicate_observations": observations,
            "processed_predicate_ids": processed_ids,
            "missing_predicate_ids": [
                item.predicate_id
                for item in observations
                if item.truth == "unknown"
            ],
            "reason_codes": reason_codes,
            "uncertainty_codes": reason_codes,
        }
    )


def _iter_atomic_expressions(expression):
    if expression.kind == "predicate":
        yield expression
        return
    for child in expression.children:
        yield from _iter_atomic_expressions(child)


def rule_set() -> RuleSet:
    age_requirement = EvidenceRequirement(
        requirement_id="req-age",
        rule_component_id="component-in-01",
        fact_type="demographics.age_years",
        required_source_types=["screening_record", "identity_record"],
        due_stage=ReviewStage.SCREENING,
        description="筛选节点应有可定位的年龄记录。",
    )
    risk_requirement = EvidenceRequirement(
        requirement_id="req-composite-risk",
        rule_component_id="component-ex-01",
        fact_type="laboratory_and_investigator_risk",
        required_source_types=["laboratory_report", "investigator_assessment"],
        due_stage=ReviewStage.SCREENING,
        description="异常指标与研究者不可接受风险判断必须同时有证据。",
    )
    inclusion = Rule(
        rule_id="rule-in-01",
        official_code="IN-01",
        kind=RuleKind.INCLUSION,
        source_text="合成规则：年龄应不低于18岁。",
        study_phase=StudyPhase.PHASE_III,
        components=[
            RuleComponent(
                rule_component_id="component-in-01",
                parent_rule_id="rule-in-01",
                display_code="IN-01",
                title="年龄要求",
                expression=atomic_predicate("demographics", "age_years", "gte", 18, unit="year"),
                evidence_requirements=[age_requirement],
            )
        ],
    )
    exclusion = Rule(
        rule_id="rule-ex-01",
        official_code="EX-01",
        kind=RuleKind.EXCLUSION,
        source_text=(
            "合成规则：研究者判断构成不可接受风险，且实验室指标"
            "达到阈值或随机前28天内存在禁用用药，且关键测量未被判定无效时排除。"
        ),
        study_phase=StudyPhase.PHASE_III,
        components=[
            RuleComponent(
                rule_component_id="component-ex-01",
                parent_rule_id="rule-ex-01",
                display_code="EX-01a",
                title="实验室异常与研究者风险的复合条件",
                expression=LogicalExpression(
                    operator=LogicalOperator.ALL,
                    children=[
                        atomic_predicate(
                            "investigator",
                            "unacceptable_participation_risk",
                            "eq",
                            True,
                            requires_professional_judgment=True,
                        ),
                        LogicalExpression(
                            operator=LogicalOperator.ANY,
                            children=[
                                atomic_predicate(
                                    "laboratory",
                                    "target_ratio_uln",
                                    "gte",
                                    1.5,
                                    unit="xULN",
                                ),
                                AtomicExpression(
                                    predicate=AtomicPredicate(
                                        predicate_id="predicate-medication-prohibited-window",
                                        subject="medication",
                                        attribute="prohibited_exposure",
                                        comparator="eq",
                                        value=True,
                                    ),
                                    time_constraint=TimeConstraint(
                                        anchor_type="randomization_date",
                                        direction="before",
                                        upper_bound_days=28,
                                    ),
                                ),
                            ],
                        ),
                        LogicalExpression(
                            operator=LogicalOperator.NOT,
                            children=[
                                atomic_predicate(
                                    "laboratory",
                                    "critical_measurement_invalid",
                                    "eq",
                                    True,
                                )
                            ],
                        ),
                    ],
                ),
                exception_expression=LogicalExpression(
                    operator=LogicalOperator.ALL,
                    children=[
                        atomic_predicate("exception", "protocol_exception_documented", "eq", True),
                        atomic_predicate(
                            "investigator",
                            "exception_confirmed",
                            "eq",
                            True,
                            requires_professional_judgment=True,
                        ),
                    ],
                ),
                evidence_requirements=[risk_requirement],
            )
        ],
    )
    auxiliary_specs = [
        (
            "rule-ex-02",
            "EX-02",
            RuleKind.EXCLUSION,
            "component-ex-02",
            "待研究者判断的合成规则",
            "req-professional",
            "investigator.rule_specific_judgment",
            ReviewStage.SCREENING,
        ),
        (
            "rule-ex-03",
            "EX-03",
            RuleKind.EXCLUSION,
            "component-ex-03",
            "后续节点才到期的合成规则",
            "req-future",
            "baseline.future_assessment",
            ReviewStage.BASELINE,
        ),
        (
            "rule-ex-04",
            "EX-04",
            RuleKind.EXCLUSION,
            "component-ex-04",
            "病历引用资料必须提供的合成规则",
            "req-referenced",
            "history.referenced_document",
            ReviewStage.SCREENING,
        ),
        (
            "rule-req-01",
            "REQ-01",
            RuleKind.REQUIRED_PROCEDURE,
            "component-req-01",
            "当前节点必做检查的合成规则",
            "req-procedure",
            "procedure.required_completed",
            ReviewStage.SCREENING,
        ),
        (
            "rule-req-02",
            "REQ-02",
            RuleKind.REQUIRED_PROCEDURE,
            "component-req-02",
            "检验结果关键字段的合成规则",
            "req-result-fields",
            "laboratory.required_fields_complete",
            ReviewStage.SCREENING,
        ),
    ]
    auxiliary_rules = []
    for rule_id, code, kind, component_id, title, requirement_id, fact_type, due_stage in auxiliary_specs:
        requirement = EvidenceRequirement(
            requirement_id=requirement_id,
            rule_component_id=component_id,
            fact_type=fact_type,
            required_source_types=["screening_record"],
            due_stage=due_stage,
            description=title,
        )
        auxiliary_rules.append(
            Rule(
                rule_id=rule_id,
                official_code=code,
                kind=kind,
                source_text=title,
                study_phase=StudyPhase.PHASE_III,
                components=[
                    RuleComponent(
                        rule_component_id=component_id,
                        parent_rule_id=rule_id,
                        display_code=f"{code}a",
                        title=title,
                        expression=atomic_predicate(
                            fact_type.rsplit(".", 1)[0],
                            fact_type.rsplit(".", 1)[1],
                            "eq",
                            True,
                            requires_professional_judgment=(code == "EX-02"),
                        ),
                        evidence_requirements=[requirement],
                    )
                ],
            )
        )
    return RuleSet(
        rule_set_id="ruleset-synthetic-phase-iii",
        protocol_version_id="protocol-v1",
        study_phase=StudyPhase.PHASE_III,
        rules=[inclusion, exclusion, *auxiliary_rules],
    )


def base_objects(suffix: str, rules: RuleSet):
    workflow_stages = [
        WorkflowStage(
            workflow_stage_id="stage-pre-screening",
            stage=ReviewStage.PRE_SCREENING,
            display_name="预筛期审核",
            visit_window="签署知情同意前",
            due_requirement_ids=[],
        ),
        WorkflowStage(
            workflow_stage_id="stage-screening",
            stage=ReviewStage.SCREENING,
            display_name="筛选期审核",
            visit_window="D-28至D-1",
            due_requirement_ids=[
                "req-age",
                "req-composite-risk",
                "req-professional",
                "req-referenced",
                "req-procedure",
                "req-result-fields",
            ],
        ),
        WorkflowStage(
            workflow_stage_id="stage-run-in",
            stage=ReviewStage.RUN_IN,
            display_name="导入/洗脱期审核",
            visit_window="筛选后至基线前",
            due_requirement_ids=[],
        ),
        WorkflowStage(
            workflow_stage_id="stage-baseline",
            stage=ReviewStage.BASELINE,
            display_name="基线/随机前审核",
            visit_window="D1随机前",
            due_requirement_ids=["req-future"],
        ),
    ]
    manifest = build_protocol_integrity_manifest(
        manifest_id="manifest-protocol-v1-phase-iii",
        protocol_version_id="protocol-v1",
        protocol_document_sha256="a" * 64,
        study_phase=StudyPhase.PHASE_III,
        source_refs=["protocol-v1:p1", "protocol-v1:p20-p24", "protocol-v1:flow-table"],
        authoritative_rules=rules.rules,
        authoritative_workflow_stages=workflow_stages,
    )
    protocol = ProtocolDocumentVersion(
        protocol_version_id="protocol-v1",
        protocol_code="SYNTHETIC-001",
        official_version="V1.0",
        official_date=DateValue(value=date(2026, 8, 1), precision=DatePrecision.DAY),
        sha256="a" * 64,
        integrity_manifest_sha256=manifest.manifest_sha256,
    )
    project = Project(
        project_id="project-synthetic-phase-iii",
        project_code="SYNTHETIC-001-III",
        project_name="合成Ⅲ期入排审核项目",
        study_phase=StudyPhase.PHASE_III,
        protocol_version=protocol,
        rule_set_id="ruleset-synthetic-phase-iii",
    )
    subject = Subject(
        subject_id=f"subject-{suffix}",
        subject_code=f"S-{suffix.upper()}",
        project_id=project.project_id,
        center_code="01",
        center_name="合成研究中心",
    )
    episode = ReviewEpisode(
        review_episode_id=f"episode-{suffix}",
        subject_id=subject.subject_id,
        project_id=project.project_id,
        rule_set_id=project.rule_set_id,
        study_phase=project.study_phase,
        stage=ReviewStage.SCREENING,
        protocol_version_id=protocol.protocol_version_id,
        rule_set_revision=1,
        evidence_snapshot_id=f"snapshot-{suffix}",
        anchor_dates={
            "screening_date": DateValue(value=date(2026, 8, 10), precision=DatePrecision.DAY)
        },
    )
    document = SourceDocumentVersion(
        source_document_version_id=f"document-{suffix}",
        file_name=f"合成筛选资料-{suffix}.pdf",
        sha256=(suffix[0] if suffix[0] in "abcdef" else "b") * 64,
        document_type="screening_record",
        source_party="investigator",
        upload_mode=UploadMode.FULL,
        review_stage=ReviewStage.SCREENING,
    )
    snapshot = EvidenceSnapshot(
        evidence_snapshot_id=f"snapshot-{suffix}",
        subject_id=subject.subject_id,
        review_episode_id=episode.review_episode_id,
        source_document_version_ids=[document.source_document_version_id],
        upload_mode=UploadMode.FULL,
        created_at=NOW,
    )
    review_run = ReviewRun(
        review_run_id=f"run-{suffix}",
        review_episode_id=episode.review_episode_id,
        protocol_version_id=protocol.protocol_version_id,
        rule_set_revision=1,
        evidence_snapshot_id=snapshot.evidence_snapshot_id,
        started_at=NOW,
        completed_at=NOW,
    )
    return project, manifest, subject, episode, workflow_stages, document, snapshot, review_run


def agent_calls(suffix: str) -> list[AgentCallContract]:
    calls = []
    definitions = [
        (AgentNode.EVIDENCE_NORMALIZER, AgentOutputKind.CANDIDATE, AgentWriteScope.EVIDENCE_CANDIDATE),
        (AgentNode.ELIGIBILITY_ASSESSOR, AgentOutputKind.CANDIDATE, AgentWriteScope.ASSESSMENT_CANDIDATE),
    ]
    for index, (node, output_kind, write_scope) in enumerate(definitions, start=1):
        calls.append(
            AgentCallContract(
                agent_call_id=f"call-{suffix}-{index}",
                node=node,
                output_kind=output_kind,
                write_scope=write_scope,
                prompt_version_id=f"prompt-{node.value}-v1",
                model_config_id="model-baseline-v1",
                input_scope_hash=str(index) * 64,
                input_revision_map={f"snapshot-{suffix}": 1},
                raw_output_hash=str(index + 2) * 64,
                output_hash=str(index + 4) * 64,
                idempotency_key=f"{suffix}:{node.value}:v1",
                attempt=1,
                max_attempts=2,
                duration_ms=1200 + index,
                started_at=NOW,
                finished_at=NOW,
                outcome=RunOutcome.ACCEPTED,
                recompute_scope=[f"subject-{suffix}"],
                trigger="fixture_generation",
                project_id="project-synthetic-phase-iii",
                subject_id=f"subject-{suffix}",
                review_episode_id=f"episode-{suffix}",
                review_run_id=f"run-{suffix}",
                evidence_snapshot_id=f"snapshot-{suffix}",
                source_ids=[f"document-{suffix}"],
                input_tokens=100 + index,
                output_tokens=50 + index,
                estimated_cost=0.01 * index,
                gate_result_ids=[f"gate-{suffix}-{index}"],
            )
        )
    return calls


def publish_fixture_assessment(
    rules: RuleSet,
    candidate: AssessmentCandidate,
    facts: list[ClinicalFact],
    episode: ReviewEpisode,
    expectations: list[EvidenceExpectation],
    conflict_groups: list[ConflictGroup],
    gate_results: list[GateResult],
    *,
    assessment_id: str,
    review_run_id: str,
    gate_result_id: str,
    action_ids: list[str] | None = None,
):
    for rule in rules.rules:
        for component in rule.components:
            if component.rule_component_id == candidate.rule_component_id:
                evaluation = evaluate_component(
                    component,
                    EvaluationContext(
                        project_id=episode.project_id,
                        subject_id=episode.subject_id,
                        review_episode_id=episode.review_episode_id,
                        evidence_snapshot_id=episode.evidence_snapshot_id,
                        accepted_fact_ids=[fact.fact_id for fact in facts],
                        facts=facts,
                        anchor_dates=episode.anchor_dates,
                    ),
                )
                hydrated = hydrate_candidate_observations(
                    candidate,
                    component,
                    EvaluationContext(
                        project_id=episode.project_id,
                        subject_id=episode.subject_id,
                        review_episode_id=episode.review_episode_id,
                        evidence_snapshot_id=episode.evidence_snapshot_id,
                        accepted_fact_ids=[fact.fact_id for fact in facts],
                        facts=facts,
                        anchor_dates=episode.anchor_dates,
                    ),
                )
                candidate.predicate_observations = hydrated.predicate_observations
                candidate.processed_predicate_ids = hydrated.processed_predicate_ids
                candidate.missing_predicate_ids = hydrated.missing_predicate_ids
                candidate.reason_codes = hydrated.reason_codes
                candidate.uncertainty_codes = hydrated.uncertainty_codes
                publication = publish_assessment(
                    candidate,
                    component=component,
                    rule_kind=rule.kind,
                    evaluation=evaluation,
                    episode_stage=episode.stage,
                    expectations=expectations,
                    conflict_groups=conflict_groups,
                    assessment_id=assessment_id,
                    review_run_id=review_run_id,
                    gate_result_id=gate_result_id,
                    input_revision_map={episode.review_episode_id: episode.revision},
                    created_at=NOW,
                    action_ids=action_ids,
                )
                gate_results.append(publication.gate_result)
                return publication.assessment
    raise ValueError(f"未找到规则组件: {candidate.rule_component_id}")


def fixture_action(
    gate_results: list[GateResult],
    *,
    episode: ReviewEpisode,
    **kwargs,
) -> ActionRequest:
    action_id = kwargs["action_id"]
    publication = publish_action_request(
        **kwargs,
        gate_result_id=f"gate-{action_id}",
        input_entity_refs=[episode.review_episode_id, kwargs["rule_component_id"]],
        input_revision_map={episode.review_episode_id: episode.revision},
        created_at=NOW,
    )
    gate_results.append(publication.gate_result)
    return publication.action


def build_fixture(scenario: str) -> FixtureV1:
    rules = rule_set()
    project, manifest, subject, episode, stages, document, snapshot, review_run = base_objects(
        scenario,
        rules,
    )
    calls = agent_calls(scenario)
    conflict_groups: list[ConflictGroup] = []
    actions: list[ActionRequest] = []
    publication_gate_results: list[GateResult] = []

    if scenario == "clear":
        spans = [
            EvidenceSpan(
                evidence_span_id="span-clear-age",
                source_document_version_id=document.source_document_version_id,
                page_number=1,
                precision=LocatorPrecision.BBOX,
                bbox=BoundingBox(x0=12, y0=20, x1=110, y1=38),
                excerpt="年龄：36岁",
                locator_algorithm_version="locator-v1",
                anchor_hash="a" * 64,
                match_confidence=0.99,
            ),
            EvidenceSpan(
                evidence_span_id="span-clear-history",
                source_document_version_id=document.source_document_version_id,
                page_number=2,
                precision=LocatorPrecision.TEXT_RANGE,
                text_start=10,
                text_end=28,
                excerpt="既往病程由筛选病历转述",
                locator_algorithm_version="locator-v1",
                anchor_hash="b" * 64,
                match_confidence=0.96,
            ),
        ]
        facts = [
            clinical_fact_for(episode,
                fact_id="fact-clear-age",
                fact_type="demographics.age_years",
                value=36,
                unit="year",
                polarity=FactPolarity.AFFIRMED,
                certainty=1,
                evidence_span_ids=["span-clear-age"],
            ),
            clinical_fact_for(episode,
                fact_id="fact-clear-risk",
                fact_type="investigator.unacceptable_participation_risk",
                value=True,
                polarity=FactPolarity.NEGATED,
                certainty=0.95,
                evidence_span_ids=["span-clear-history"],
            ),
        ]
        expectations = [
            EvidenceExpectation(
                expectation_id="expectation-clear-age",
                requirement_id="req-age",
                review_episode_id=episode.review_episode_id,
                status=ExpectationStatus.OBSERVED,
                evidence_span_ids=["span-clear-age"],
            ),
            EvidenceExpectation(
                expectation_id="expectation-clear-history",
                requirement_id="req-composite-risk",
                review_episode_id=episode.review_episode_id,
                status=ExpectationStatus.OBSERVED_WEAK,
                evidence_span_ids=["span-clear-history"],
                gap_type=GapType.PROVENANCE_FOLLOWUP,
            ),
        ]
        candidates = [
            assessment_candidate_for(episode,
                assessment_candidate_id="candidate-clear-in",
                agent_call_id=calls[1].agent_call_id,
                rule_component_id="component-in-01",
                proposed_decision=ComponentDecision.INCLUSION_MET,
                used_fact_ids=["fact-clear-age"],
                evidence_span_ids=["span-clear-age"],
                candidate_rationale="年龄达到合成规则阈值。",
            ),
            assessment_candidate_for(episode,
                assessment_candidate_id="candidate-clear-ex",
                agent_call_id=calls[1].agent_call_id,
                rule_component_id="component-ex-01",
                proposed_decision=ComponentDecision.EXCLUSION_NOT_TRIGGERED,
                gap_types=[GapType.PROVENANCE_FOLLOWUP],
                used_fact_ids=["fact-clear-risk"],
                evidence_span_ids=["span-clear-history"],
                candidate_rationale="复合排除条件未同时满足。",
            ),
        ]
        final = [
            publish_fixture_assessment(rules, candidates[0], facts, episode, expectations, conflict_groups, publication_gate_results, assessment_id="assessment-clear-in", review_run_id=review_run.review_run_id, gate_result_id="gate-clear-in"),
            publish_fixture_assessment(rules, candidates[1], facts, episode, expectations, conflict_groups, publication_gate_results, assessment_id="assessment-clear-ex", review_run_id=review_run.review_run_id, gate_result_id="gate-clear-ex", action_ids=["action-clear-provenance"]),
        ]
        actions = [
            fixture_action(publication_gate_results, episode=episode,
                action_id="action-clear-provenance",
                rule_component_id="component-ex-01",
                gap_type=GapType.PROVENANCE_FOLLOWUP,
                target_party=ActionTarget.CRA,
                requested_action="在后续阶段核对阳性既往史转述来源。",
                acceptable_evidence="来源链接或核对记录。",
                due_stage=ReviewStage.BASELINE,
                trigger_evidence_span_id="span-clear-history",
                state=ActionState.OPEN,
                recompute_scope=["component-ex-01"],
            )
        ]
    elif scenario == "barrier":
        spans = [
            EvidenceSpan(
                evidence_span_id="span-barrier-risk",
                source_document_version_id=document.source_document_version_id,
                page_number=3,
                precision=LocatorPrecision.PAGE_EXCERPT,
                excerpt="合成数据：指标超过阈值，研究者判断参与构成不可接受风险。",
                locator_algorithm_version="locator-v1",
                anchor_hash="c" * 64,
                match_confidence=0.91,
            )
        ]
        facts = [
            clinical_fact_for(episode,
                fact_id="fact-barrier-age",
                fact_type="demographics.age_years",
                value=45,
                unit="year",
                polarity=FactPolarity.AFFIRMED,
                certainty=1,
                evidence_span_ids=["span-barrier-risk"],
            ),
            clinical_fact_for(episode,
                fact_id="fact-barrier-no-exception",
                fact_type="exception.protocol_exception_documented",
                value=True,
                polarity=FactPolarity.NEGATED,
                certainty=1,
                evidence_span_ids=["span-barrier-risk"],
            ),
            clinical_fact_for(episode,
                fact_id="fact-barrier-lab",
                fact_type="laboratory.target_ratio_uln",
                value=2.1,
                unit="xULN",
                polarity=FactPolarity.AFFIRMED,
                certainty=1,
                evidence_span_ids=["span-barrier-risk"],
            ),
            clinical_fact_for(episode,
                fact_id="fact-barrier-risk",
                fact_type="investigator.unacceptable_participation_risk",
                value=True,
                polarity=FactPolarity.AFFIRMED,
                certainty=1,
                evidence_span_ids=["span-barrier-risk"],
            ),
            clinical_fact_for(episode,
                fact_id="fact-barrier-measurement-invalid",
                fact_type="laboratory.critical_measurement_invalid",
                value=True,
                polarity=FactPolarity.NEGATED,
                certainty=1,
                evidence_span_ids=["span-barrier-risk"],
            ),
        ]
        expectations = [
            EvidenceExpectation(
                expectation_id="expectation-barrier-age",
                requirement_id="req-age",
                review_episode_id=episode.review_episode_id,
                status=ExpectationStatus.OBSERVED,
                evidence_span_ids=["span-barrier-risk"],
            ),
            EvidenceExpectation(
                expectation_id="expectation-barrier-risk",
                requirement_id="req-composite-risk",
                review_episode_id=episode.review_episode_id,
                status=ExpectationStatus.OBSERVED,
                evidence_span_ids=["span-barrier-risk"],
            )
        ]
        candidates = [
            assessment_candidate_for(episode,
                assessment_candidate_id="candidate-barrier-in",
                agent_call_id=calls[1].agent_call_id,
                rule_component_id="component-in-01",
                proposed_decision=ComponentDecision.INCLUSION_MET,
                used_fact_ids=["fact-barrier-age"],
                evidence_span_ids=["span-barrier-risk"],
                candidate_rationale="年龄达到合成规则阈值。",
            ),
            assessment_candidate_for(episode,
                assessment_candidate_id="candidate-barrier-ex",
                agent_call_id=calls[1].agent_call_id,
                rule_component_id="component-ex-01",
                proposed_decision=ComponentDecision.EXCLUSION_TRIGGERED,
                used_fact_ids=[
                    "fact-barrier-lab",
                    "fact-barrier-risk",
                    "fact-barrier-measurement-invalid",
                    "fact-barrier-no-exception",
                ],
                evidence_span_ids=["span-barrier-risk"],
                candidate_rationale="阈值和研究者判断两个 AND 组件均满足。",
            ),
        ]
        final = [
            publish_fixture_assessment(rules, candidates[0], facts, episode, expectations, conflict_groups, publication_gate_results, assessment_id="assessment-barrier-in", review_run_id=review_run.review_run_id, gate_result_id="gate-barrier-in"),
            publish_fixture_assessment(rules, candidates[1], facts, episode, expectations, conflict_groups, publication_gate_results, assessment_id="assessment-barrier-ex", review_run_id=review_run.review_run_id, gate_result_id="gate-barrier-ex"),
        ]
    else:
        spans = [
            EvidenceSpan(
                evidence_span_id="span-gap-page",
                source_document_version_id=document.source_document_version_id,
                page_number=4,
                precision=LocatorPrecision.PAGE_ONLY,
                locator_algorithm_version="locator-v1",
                degradation_reason="扫描页无法稳定定位字符或坐标。",
                match_confidence=0.6,
            )
        ]
        facts = [
            clinical_fact_for(episode,
                fact_id="fact-gap-risk-positive",
                fact_type="investigator.unacceptable_participation_risk",
                value=True,
                polarity=FactPolarity.AFFIRMED,
                certainty=0.7,
                evidence_span_ids=["span-gap-page"],
                conflict_group_id="conflict-gap-risk",
            ),
            clinical_fact_for(episode,
                fact_id="fact-gap-risk-negative",
                fact_type="investigator.unacceptable_participation_risk",
                value=True,
                polarity=FactPolarity.NEGATED,
                certainty=0.7,
                evidence_span_ids=["span-gap-page"],
                conflict_group_id="conflict-gap-risk",
            ),
        ]
        conflict_groups = [
            ConflictGroup(
                conflict_group_id="conflict-gap-risk",
                fact_ids=["fact-gap-risk-positive", "fact-gap-risk-negative"],
                affected_rule_component_ids=["component-ex-01"],
            )
        ]
        expectations = [
            EvidenceExpectation(
                expectation_id="expectation-gap-age",
                requirement_id="req-age",
                review_episode_id=episode.review_episode_id,
                status=ExpectationStatus.ABSENT,
                gap_type=GapType.RECORD_INCOMPLETE,
            ),
            EvidenceExpectation(
                expectation_id="expectation-gap-risk",
                requirement_id="req-composite-risk",
                review_episode_id=episode.review_episode_id,
                status=ExpectationStatus.OBSERVED_WEAK,
                evidence_span_ids=["span-gap-page"],
                gap_type=GapType.OCR_OR_PARSE_RISK,
            ),
            EvidenceExpectation(
                expectation_id="expectation-gap-professional",
                requirement_id="req-professional",
                review_episode_id=episode.review_episode_id,
                status=ExpectationStatus.ABSENT,
                gap_type=GapType.DESCRIPTION_INSUFFICIENT,
            ),
            EvidenceExpectation(
                expectation_id="expectation-gap-future",
                requirement_id="req-future",
                review_episode_id=episode.review_episode_id,
                status=ExpectationStatus.NOT_DUE,
                gap_type=GapType.FUTURE_STAGE_NOT_DUE,
            ),
            EvidenceExpectation(
                expectation_id="expectation-gap-referenced",
                requirement_id="req-referenced",
                review_episode_id=episode.review_episode_id,
                status=ExpectationStatus.REFERENCED_MISSING,
                gap_type=GapType.REFERENCED_FILE_MISSING,
            ),
            EvidenceExpectation(
                expectation_id="expectation-gap-procedure",
                requirement_id="req-procedure",
                review_episode_id=episode.review_episode_id,
                status=ExpectationStatus.ABSENT,
                gap_type=GapType.REQUIRED_PROCEDURE_NOT_DONE,
            ),
            EvidenceExpectation(
                expectation_id="expectation-gap-result-fields",
                requirement_id="req-result-fields",
                review_episode_id=episode.review_episode_id,
                status=ExpectationStatus.ABSENT,
                gap_type=GapType.RESULT_FIELDS_MISSING,
            ),
        ]
        candidates = [
            assessment_candidate_for(episode,
                assessment_candidate_id="candidate-gap-in",
                agent_call_id=calls[1].agent_call_id,
                rule_component_id="component-in-01",
                proposed_decision=ComponentDecision.INDETERMINATE,
                gap_types=[GapType.RECORD_INCOMPLETE],
                evidence_span_ids=[],
                candidate_rationale="筛选记录未提供年龄。",
            ),
            assessment_candidate_for(episode,
                assessment_candidate_id="candidate-gap-ex",
                agent_call_id=calls[1].agent_call_id,
                rule_component_id="component-ex-01",
                proposed_decision=ComponentDecision.CONFLICT,
                gap_types=[GapType.SOURCE_CONFLICT, GapType.OCR_OR_PARSE_RISK],
                used_fact_ids=["fact-gap-risk-positive", "fact-gap-risk-negative"],
                evidence_span_ids=["span-gap-page"],
                candidate_rationale="同一研究者风险判断存在冲突来源。",
            ),
            assessment_candidate_for(episode,
                assessment_candidate_id="candidate-gap-professional",
                agent_call_id=calls[1].agent_call_id,
                rule_component_id="component-ex-02",
                proposed_decision=ComponentDecision.PROFESSIONAL_JUDGMENT,
                gap_types=[GapType.DESCRIPTION_INSUFFICIENT, GapType.PROFESSIONAL_JUDGMENT],
                evidence_span_ids=["span-gap-page"],
                candidate_rationale="客观资料存在，但缺少针对本规则的研究者判断。",
            ),
            assessment_candidate_for(episode,
                assessment_candidate_id="candidate-gap-future",
                agent_call_id=calls[1].agent_call_id,
                rule_component_id="component-ex-03",
                proposed_decision=ComponentDecision.NOT_DUE,
                gap_types=[GapType.FUTURE_STAGE_NOT_DUE],
                candidate_rationale="该要求在基线节点到期。",
            ),
            assessment_candidate_for(episode,
                assessment_candidate_id="candidate-gap-referenced",
                agent_call_id=calls[1].agent_call_id,
                rule_component_id="component-ex-04",
                proposed_decision=ComponentDecision.INDETERMINATE,
                gap_types=[GapType.REFERENCED_FILE_MISSING],
                candidate_rationale="病历引用的资料尚未提供。",
            ),
            assessment_candidate_for(episode,
                assessment_candidate_id="candidate-gap-procedure",
                agent_call_id=calls[1].agent_call_id,
                rule_component_id="component-req-01",
                proposed_decision=ComponentDecision.INDETERMINATE,
                gap_types=[GapType.REQUIRED_PROCEDURE_NOT_DONE],
                candidate_rationale="当前节点必做检查尚未完成。",
            ),
            assessment_candidate_for(episode,
                assessment_candidate_id="candidate-gap-result-fields",
                agent_call_id=calls[1].agent_call_id,
                rule_component_id="component-req-02",
                proposed_decision=ComponentDecision.INDETERMINATE,
                gap_types=[GapType.RESULT_FIELDS_MISSING],
                candidate_rationale="检验结果缺少判定所需字段。",
            ),
        ]
        final = [
            publish_fixture_assessment(rules, candidates[0], facts, episode, expectations, conflict_groups, publication_gate_results, assessment_id="assessment-gap-in", review_run_id=review_run.review_run_id, gate_result_id="gate-gap-in", action_ids=["action-gap-age"]),
            publish_fixture_assessment(rules, candidates[1], facts, episode, expectations, conflict_groups, publication_gate_results, assessment_id="assessment-gap-ex", review_run_id=review_run.review_run_id, gate_result_id="gate-gap-ex", action_ids=["action-gap-conflict"]),
            publish_fixture_assessment(rules, candidates[2], facts, episode, expectations, conflict_groups, publication_gate_results, assessment_id="assessment-gap-professional", review_run_id=review_run.review_run_id, gate_result_id="gate-gap-professional", action_ids=["action-gap-professional"]),
            publish_fixture_assessment(rules, candidates[3], facts, episode, expectations, conflict_groups, publication_gate_results, assessment_id="assessment-gap-future", review_run_id=review_run.review_run_id, gate_result_id="gate-gap-future", action_ids=["action-gap-future"]),
            publish_fixture_assessment(rules, candidates[4], facts, episode, expectations, conflict_groups, publication_gate_results, assessment_id="assessment-gap-referenced", review_run_id=review_run.review_run_id, gate_result_id="gate-gap-referenced", action_ids=["action-gap-referenced"]),
            publish_fixture_assessment(rules, candidates[5], facts, episode, expectations, conflict_groups, publication_gate_results, assessment_id="assessment-gap-procedure", review_run_id=review_run.review_run_id, gate_result_id="gate-gap-procedure", action_ids=["action-gap-procedure"]),
            publish_fixture_assessment(rules, candidates[6], facts, episode, expectations, conflict_groups, publication_gate_results, assessment_id="assessment-gap-result-fields", review_run_id=review_run.review_run_id, gate_result_id="gate-gap-result-fields", action_ids=["action-gap-result-fields"]),
        ]
        actions = [
            fixture_action(publication_gate_results, episode=episode,
                action_id="action-gap-age",
                rule_component_id="component-in-01",
                gap_type=GapType.RECORD_INCOMPLETE,
                target_party=ActionTarget.INVESTIGATOR,
                requested_action="在筛选病历补充受试者年龄及来源。",
                acceptable_evidence="具日期和来源的年龄记录。",
                due_stage=ReviewStage.SCREENING,
                state=ActionState.OPEN,
                recompute_scope=["component-in-01"],
            ),
            fixture_action(publication_gate_results, episode=episode,
                action_id="action-gap-conflict",
                rule_component_id="component-ex-01",
                gap_type=GapType.SOURCE_CONFLICT,
                target_party=ActionTarget.INVESTIGATOR,
                requested_action="核实并记录针对本条的研究者判断。",
                acceptable_evidence="具名、具日期且链接来源的冲突核实记录。",
                due_stage=ReviewStage.SCREENING,
                trigger_evidence_span_id="span-gap-page",
                state=ActionState.OPEN,
                recompute_scope=["component-ex-01"],
            ),
            fixture_action(publication_gate_results, episode=episode,
                action_id="action-gap-professional",
                rule_component_id="component-ex-02",
                gap_type=GapType.PROFESSIONAL_JUDGMENT,
                target_party=ActionTarget.INVESTIGATOR,
                requested_action="研究者针对本规则记录是否构成方案所述风险。",
                acceptable_evidence="具名、具日期并关联本规则的研究者判断。",
                due_stage=ReviewStage.SCREENING,
                trigger_evidence_span_id="span-gap-page",
                state=ActionState.OPEN,
                recompute_scope=["component-ex-02"],
            ),
            fixture_action(publication_gate_results, episode=episode,
                action_id="action-gap-future",
                rule_component_id="component-ex-03",
                gap_type=GapType.FUTURE_STAGE_NOT_DUE,
                target_party=ActionTarget.CRC,
                requested_action="在基线节点完成并上传该项评估。",
                acceptable_evidence="基线日期锚点和对应评估记录。",
                due_stage=ReviewStage.BASELINE,
                state=ActionState.OPEN,
                recompute_scope=["component-ex-03"],
            ),
            fixture_action(publication_gate_results, episode=episode,
                action_id="action-gap-referenced",
                rule_component_id="component-ex-04",
                gap_type=GapType.REFERENCED_FILE_MISSING,
                target_party=ActionTarget.CRC,
                requested_action="补充病历中明确引用的原始资料。",
                acceptable_evidence="被引用文件及其日期、版本和来源。",
                due_stage=ReviewStage.SCREENING,
                trigger_evidence_span_id="span-gap-page",
                state=ActionState.OPEN,
                recompute_scope=["component-ex-04"],
            ),
            fixture_action(publication_gate_results, episode=episode,
                action_id="action-gap-procedure",
                rule_component_id="component-req-01",
                gap_type=GapType.REQUIRED_PROCEDURE_NOT_DONE,
                target_party=ActionTarget.CRC,
                requested_action="完成当前节点必做检查。",
                acceptable_evidence="检查执行记录和完整结果。",
                due_stage=ReviewStage.SCREENING,
                state=ActionState.OPEN,
                recompute_scope=["component-req-01"],
            ),
            fixture_action(publication_gate_results, episode=episode,
                action_id="action-gap-result-fields",
                rule_component_id="component-req-02",
                gap_type=GapType.RESULT_FIELDS_MISSING,
                target_party=ActionTarget.CRC,
                requested_action="补充检验结果的数值、单位和参考范围。",
                acceptable_evidence="同一检验报告中的完整结果字段。",
                due_stage=ReviewStage.SCREENING,
                state=ActionState.OPEN,
                recompute_scope=["component-req-02"],
            ),
        ]

    events = [
        PatientProfileEvent(
            event_id=f"event-{scenario}-summary",
            lane=ProfileLane.DEMOGRAPHICS if scenario != "gap_conflict" else ProfileLane.EVIDENCE_QUALITY,
            event_type="screening_summary",
            title={"clear": "当前未发现明确障碍", "barrier": "发现明确排除障碍"}.get(scenario, "资料缺口与冲突待处理"),
            start_date=DateValue(value=date(2026, 8, 10), precision=DatePrecision.DAY),
            fact_ids=[fact.fact_id for fact in facts],
            evidence_span_ids=[span.evidence_span_id for span in spans],
            related_rule_component_ids=["component-in-01", "component-ex-01"],
            risk_labels=[] if scenario == "clear" else ["入排相关"],
            is_abnormal=scenario == "barrier",
            is_critical=scenario == "barrier",
        )
    ]
    if scenario == "gap_conflict":
        profile_event_specs = [
            (ProfileLane.STUDY_MILESTONE, "筛选节点", ["阶段隔离"]),
            (ProfileLane.TARGET_DISEASE, "目标疾病病程待补充", ["记录不完整"]),
            (ProfileLane.MEDICATION, "合并用药时间轴待核对", ["日期锚点"]),
            (ProfileLane.TEST_EXAM_SCORE, "必做检查和结果字段待补", ["当前节点缺口"]),
            (ProfileLane.MEDICAL_HISTORY, "既往资料被引用但未提供", ["来源缺失"]),
            (ProfileLane.EVIDENCE_QUALITY, "同一判断存在冲突来源", ["来源冲突"]),
        ]
        for index, (lane, title, labels) in enumerate(profile_event_specs, start=1):
            events.append(
                PatientProfileEvent(
                    event_id=f"event-gap-detail-{index}",
                    lane=lane,
                    event_type="risk_or_gap",
                    title=title,
                    start_date=DateValue(value=date(2026, 8, 10), precision=DatePrecision.DAY),
                    evidence_span_ids=["span-gap-page"],
                    related_rule_component_ids=["component-ex-01"],
                    risk_labels=labels,
                    is_abnormal=lane == ProfileLane.EVIDENCE_QUALITY,
                    has_trend_change=lane == ProfileLane.MEDICATION,
                )
            )
    profile = PatientProfile(
        patient_profile_id=f"profile-{scenario}",
        subject_id=subject.subject_id,
        review_episode_id=episode.review_episode_id,
        events=events,
        highlighted_event_ids=[events[0].event_id],
        missing_expectation_ids=[item.expectation_id for item in expectations if item.status == ExpectationStatus.ABSENT],
    )
    rollup_publication = publish_episode_rollup(
        review_episode_id=episode.review_episode_id,
        assessments=final,
        expectations=expectations,
        actions=actions,
        gate_result_id=f"gate-rollup-{scenario}",
        input_revision_map={episode.review_episode_id: episode.revision},
        created_at=NOW,
    )
    publication_gate_results.append(rollup_publication.gate_result)
    gates = [
        GateResult(
            gate_result_id=call.gate_result_ids[0],
            gate_name="agent-output-schema-gate",
            result=GateOutcome.ACCEPTED,
            input_scope_hash=call.input_scope_hash,
            input_revision_map=call.input_revision_map,
            input_entity_refs=[call.agent_call_id],
            accepted_entity_refs=[call.agent_call_id],
            affected_scope=call.recompute_scope,
            recompute_scope=call.recompute_scope,
            idempotency_key=f"gate:{call.idempotency_key}",
            created_at=NOW,
            output_hash=call.output_hash,
        )
        for index, call in enumerate(calls, start=1)
    ] + publication_gate_results
    jobs = [
        JobEvent(
            job_event_id=f"job-event-{scenario}-1",
            job_id=f"job-{scenario}",
            event_type="created",
            occurred_at=NOW,
            progress_total=2,
        ),
        JobEvent(
            job_event_id=f"job-event-{scenario}-2",
            job_id=f"job-{scenario}",
            event_type="completed",
            occurred_at=NOW,
            progress_completed=2,
            progress_total=2,
        ),
    ]
    if scenario == "gap_conflict":
        jobs[1:1] = [
            JobEvent(
                job_event_id="job-event-gap-step-failed",
                job_id="job-gap_conflict",
                event_type="step_failed",
                step_id="normalize-page-4",
                occurred_at=NOW,
                retryable=True,
                progress_completed=1,
                progress_total=2,
                payload={"error_code": "ocr_or_parse_risk"},
            ),
            JobEvent(
                job_event_id="job-event-gap-retry",
                job_id="job-gap_conflict",
                event_type="retry_scheduled",
                step_id="normalize-page-4",
                occurred_at=NOW,
                attempt=2,
                checkpoint_id="checkpoint-gap-page-3",
                retryable=True,
                progress_completed=1,
                progress_total=2,
            ),
            JobEvent(
                job_event_id="job-event-gap-step-complete",
                job_id="job-gap_conflict",
                event_type="step_completed",
                step_id="normalize-page-4",
                occurred_at=NOW,
                attempt=2,
                checkpoint_id="checkpoint-gap-page-4",
                progress_completed=2,
                progress_total=2,
            ),
        ]
    return FixtureV1(
        fixture_id=f"fixture-{scenario}",
        scenario=scenario,
        project=project,
        protocol_integrity_manifest=manifest,
        rule_set=rules,
        workflow_stages=stages,
        subject=subject,
        review_episode=episode,
        evidence_snapshot=snapshot,
        review_runs=[review_run],
        source_documents=[document],
        evidence_spans=spans,
        evidence_expectations=expectations,
        facts=facts,
        conflict_groups=conflict_groups,
        patient_profile=profile,
        assessment_candidates=candidates,
        final_assessments=final,
        actions=actions,
        episode_rollup=rollup_publication.rollup,
        prompt_versions=[
            PromptVersion(
                prompt_version_id="prompt-evidence_normalizer-v1",
                node=AgentNode.EVIDENCE_NORMALIZER,
                template_sha256="d" * 64,
                schema_version_id="fixture/v1",
            ),
            PromptVersion(
                prompt_version_id="prompt-eligibility_assessor-v1",
                node=AgentNode.ELIGIBILITY_ASSESSOR,
                template_sha256="e" * 64,
                schema_version_id="fixture/v1",
            ),
        ],
        model_configs=[
            ModelConfigContract(
                model_config_id="model-baseline-v1",
                provider="configured-review-provider",
                model="configured-review-model",
                reasoning_effort="max",
                parameters={"temperature": 0},
            )
        ],
        agent_calls=calls,
        gate_results=gates,
        job_events=jobs,
    )


def rewrite_openapi_refs(value):
    if isinstance(value, dict):
        return {key: rewrite_openapi_refs(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_openapi_refs(item) for item in value]
    if isinstance(value, str):
        return value.replace("#/$defs/", "#/components/schemas/")
    return value


def openapi_draft(fixture_schema: dict) -> dict:
    fixture_component = rewrite_openapi_refs(
        {key: value for key, value in fixture_schema.items() if key != "$defs"}
    )
    definitions = rewrite_openapi_refs(fixture_schema.get("$defs", {}))
    error_schema = ErrorEnvelope.model_json_schema(ref_template="#/components/schemas/{model}")
    definitions.update(error_schema.pop("$defs", {}))
    api_models = [
        ProjectListResponse,
        SubjectListResponse,
        WorkspaceResponse,
        ActionOverrideCommand,
        ActionOverrideResponse,
        JobStatusResponse,
    ]
    api_schemas: dict[str, dict] = {}
    for model in api_models:
        schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
        definitions.update(schema.pop("$defs", {}))
        api_schemas[model.__name__] = rewrite_openapi_refs(schema)

    def success_response(model_name: str) -> dict:
        return {
            "description": "成功",
            "content": {
                "application/json": {
                    "schema": {"$ref": f"#/components/schemas/{model_name}"}
                }
            },
        }

    def path_parameter(name: str) -> dict:
        return {
            "name": name,
            "in": "path",
            "required": True,
            "schema": {"type": "string", "minLength": 1},
        }
    error_response = {
        "description": "请求未完成",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ErrorEnvelope"}
            }
        },
    }
    return {
        "openapi": "3.1.0",
        "info": {"title": "入排审核系统 V2 Stub API", "version": "fixture/v1"},
        "paths": {
            "/api/v2/projects": {"get": {"summary": "读取项目看板", "responses": {"200": success_response("ProjectListResponse"), "500": error_response}}},
            "/api/v2/projects/{project_id}/subjects": {"get": {"summary": "读取项目受试者及分阶段状态", "parameters": [path_parameter("project_id")], "responses": {"200": success_response("SubjectListResponse"), "404": error_response}}},
            "/api/v2/review-episodes/{episode_id}/workspace": {"get": {"summary": "读取入排工作台", "parameters": [path_parameter("episode_id")], "responses": {"200": success_response("WorkspaceResponse"), "404": error_response}}},
            "/api/v2/actions/{action_id}/override": {"post": {"summary": "人工关闭或重新打开行动", "parameters": [path_parameter("action_id")], "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ActionOverrideCommand"}}}}, "responses": {"200": success_response("ActionOverrideResponse"), "409": error_response, "422": error_response}}},
            "/api/v2/jobs/{job_id}": {"get": {"summary": "读取后台任务状态", "parameters": [path_parameter("job_id")], "responses": {"200": success_response("JobStatusResponse"), "404": error_response}}},
        },
        "components": {
            "schemas": {
                "FixtureV1": fixture_component,
                **definitions,
                "ErrorEnvelope": rewrite_openapi_refs(error_schema),
                **api_schemas,
            }
        },
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


LOCAL_ID_PREFIXES = (
    "job-event-",
    "assessment-",
    "expectation-",
    "candidate-",
    "document-",
    "snapshot-",
    "conflict-",
    "profile-",
    "episode-",
    "subject-",
    "action-",
    "event-",
    "fact-",
    "span-",
    "call-",
    "gate-",
    "job-",
    "run-",
)


def namespace_fixture(base: FixtureV1, *, subject_number: int, stage: ReviewStage) -> FixtureV1:
    subject_namespace = f"uat-{subject_number:02d}"
    episode_namespace = f"{subject_namespace}-{stage.value}"

    def transform(value):
        if isinstance(value, dict):
            return {transform(key): transform(item) for key, item in value.items()}
        if isinstance(value, list):
            return [transform(item) for item in value]
        if isinstance(value, str):
            for prefix in LOCAL_ID_PREFIXES:
                if value.startswith(prefix):
                    namespace = subject_namespace if prefix == "subject-" else episode_namespace
                    return f"{prefix}{namespace}-{value[len(prefix):]}"
        return value

    payload = transform(base.model_dump(mode="json"))
    payload["fixture_id"] = f"fixture-{episode_namespace}"
    payload["subject"]["subject_code"] = f"UAT-{subject_number:02d}"
    payload["review_episode"]["stage"] = stage.value
    payload["source_documents"][0]["review_stage"] = stage.value
    if stage == ReviewStage.PRE_SCREENING:
        payload["review_episode"]["anchor_dates"] = {
            "icf_date": DateValue(
                value=date(2026, 8, 1), precision=DatePrecision.DAY
            ).model_dump(mode="json")
        }
    elif stage == ReviewStage.SCREENING:
        payload["review_episode"]["anchor_dates"] = {
            "screening_date": DateValue(
                value=date(2026, 8, 10), precision=DatePrecision.DAY
            ).model_dump(mode="json")
        }
    elif stage == ReviewStage.RUN_IN:
        payload["review_episode"]["anchor_dates"] = {
            "screening_date": DateValue(
                value=date(2026, 8, 10), precision=DatePrecision.DAY
            ).model_dump(mode="json")
        }
    else:  # BASELINE
        payload["review_episode"]["anchor_dates"] = {
            "screening_date": DateValue(
                value=date(2026, 8, 10), precision=DatePrecision.DAY
            ).model_dump(mode="json"),
            "baseline_date": DateValue(
                value=date(2026, 8, 31), precision=DatePrecision.DAY
            ).model_dump(mode="json"),
            "randomization_date": DateValue(
                value=date(2026, 8, 31), precision=DatePrecision.DAY
            ).model_dump(mode="json"),
        }
    if stage in {ReviewStage.RUN_IN, ReviewStage.BASELINE}:
        payload["evidence_snapshot"]["upload_mode"] = UploadMode.INCREMENTAL.value
        payload["evidence_snapshot"]["prior_snapshot_id"] = (
            f"snapshot-{subject_namespace}-screening-{base.evidence_snapshot.evidence_snapshot_id[len('snapshot-') :]}"
        )
        payload["source_documents"][0]["upload_mode"] = UploadMode.INCREMENTAL.value

    episode = ReviewEpisode.model_validate(payload["review_episode"])
    rules = RuleSet.model_validate(payload["rule_set"])
    facts = [ClinicalFact.model_validate(item) for item in payload["facts"]]
    conflicts = [ConflictGroup.model_validate(item) for item in payload["conflict_groups"]]
    requirement_by_id = {
        requirement.requirement_id: requirement
        for rule in rules.rules
        for component in rule.components
        for requirement in component.evidence_requirements
    }
    component_to_rule = {
        component.rule_component_id: (component, rule)
        for rule in rules.rules
        for component in rule.components
    }
    stage_rank = {
        ReviewStage.PRE_SCREENING: 0,
        ReviewStage.SCREENING: 1,
        ReviewStage.RUN_IN: 2,
        ReviewStage.BASELINE: 3,
    }

    expectations: list[EvidenceExpectation] = []
    for item in payload["evidence_expectations"]:
        expectation = EvidenceExpectation.model_validate(item)
        requirement = requirement_by_id[expectation.requirement_id]
        if stage_rank[requirement.due_stage] > stage_rank[stage]:
            expectation = expectation.model_copy(
                update={
                    "status": ExpectationStatus.NOT_DUE,
                    "evidence_span_ids": [],
                    "gap_type": GapType.FUTURE_STAGE_NOT_DUE,
                }
            )
        elif expectation.status == ExpectationStatus.NOT_DUE:
            expectation = expectation.model_copy(
                update={
                    "status": ExpectationStatus.ABSENT,
                    "evidence_span_ids": [],
                    "gap_type": GapType.RECORD_INCOMPLETE,
                }
            )
        expectations.append(EvidenceExpectation.model_validate(expectation.model_dump()))

    context = EvaluationContext(
        project_id=episode.project_id,
        subject_id=episode.subject_id,
        review_episode_id=episode.review_episode_id,
        evidence_snapshot_id=episode.evidence_snapshot_id,
        accepted_fact_ids=[fact.fact_id for fact in facts],
        facts=facts,
        anchor_dates=episode.anchor_dates,
    )
    evaluations = {}
    derived_gaps = {}
    candidates: list[AssessmentCandidate] = []
    for item in payload["assessment_candidates"]:
        candidate = AssessmentCandidate.model_validate(item)
        component, rule = component_to_rule[candidate.rule_component_id]
        evaluation = evaluate_component(component, context)
        gaps = derive_gate_gap_types(
            component=component,
            evaluation=evaluation,
            episode_stage=stage,
            expectations=expectations,
            conflict_groups=conflicts,
        )
        decision = derive_component_decision(
            rule_kind=rule.kind,
            evaluation=evaluation,
            gaps=gaps,
        )
        candidate = candidate.model_copy(
            update={
                "review_episode_id": episode.review_episode_id,
                "evidence_snapshot_id": episode.evidence_snapshot_id,
                "proposed_decision": decision,
                "gap_types": sorted(gaps, key=lambda value: value.value),
                "candidate_rationale": (
                    f"合成 UAT 候选：{stage.value} 阶段按当前快照重新求值。"
                ),
            }
        )
        candidate = hydrate_candidate_observations(candidate, component, context)
        candidates.append(AssessmentCandidate.model_validate(candidate.model_dump()))
        evaluations[candidate.rule_component_id] = evaluation
        derived_gaps[candidate.rule_component_id] = gaps

    old_actions_by_component = {
        item["rule_component_id"]: item for item in payload["actions"]
    }
    gap_defaults = {
        GapType.RECORD_INCOMPLETE: (
            ActionTarget.INVESTIGATOR,
            "补充当前阶段未记录的关键信息及来源。",
            "可定位、具日期的完整病历或结果记录。",
        ),
        GapType.DESCRIPTION_INSUFFICIENT: (
            ActionTarget.INVESTIGATOR,
            "补充足以判定本规则的病历描述。",
            "具名、具日期且对应本规则的病历记录。",
        ),
        GapType.PROFESSIONAL_JUDGMENT: (
            ActionTarget.INVESTIGATOR,
            "研究者针对本规则完成明确的临床判断。",
            "具名、具日期并关联本规则的研究者判断。",
        ),
        GapType.SOURCE_CONFLICT: (
            ActionTarget.INVESTIGATOR,
            "核实相互冲突的来源并记录结论。",
            "具名、具日期且链接原始来源的核实记录。",
        ),
        GapType.FUTURE_STAGE_NOT_DUE: (
            ActionTarget.CRC,
            "在规则到期的后续阶段完成评估。",
            "对应阶段日期锚点与完整评估记录。",
        ),
        GapType.PROVENANCE_FOLLOWUP: (
            ActionTarget.CRA,
            "核对筛选病历转述所依据的原始来源。",
            "原始来源或已签名的溯源核对记录。",
        ),
    }
    fallback_default = (
        ActionTarget.CRC,
        "补充或核对本规则判定所需资料。",
        "可定位、具日期且能闭环当前缺口的资料。",
    )
    actions: list[ActionRequest] = []
    publication_gates: list[GateResult] = []
    action_ids_by_component: dict[str, list[str]] = {}
    for candidate in candidates:
        gaps = derived_gaps[candidate.rule_component_id]
        if not gaps:
            continue
        old = old_actions_by_component.get(candidate.rule_component_id)
        old_gap = GapType(old["gap_type"]) if old is not None else None
        chosen_gap = (
            old_gap
            if old_gap in gaps
            else sorted(gaps, key=lambda value: value.value)[0]
        )
        target, requested, acceptable = gap_defaults.get(chosen_gap, fallback_default)
        component, _ = component_to_rule[candidate.rule_component_id]
        due_stage = max(
            (requirement.due_stage for requirement in component.evidence_requirements),
            key=lambda value: stage_rank[value],
            default=stage,
        )
        action_id = (
            old["action_id"]
            if old is not None
            else f"action-{episode_namespace}-{candidate.rule_component_id}"
        )
        trigger_span = old.get("trigger_evidence_span_id") if old is not None else None
        publication = publish_action_request(
            action_id=action_id,
            rule_component_id=candidate.rule_component_id,
            gap_type=chosen_gap,
            target_party=target,
            requested_action=requested,
            acceptable_evidence=acceptable,
            due_stage=due_stage,
            state=ActionState.OPEN,
            recompute_scope=[candidate.rule_component_id],
            trigger_evidence_span_id=trigger_span,
            gate_result_id=f"gate-{action_id}",
            input_entity_refs=[
                episode.review_episode_id,
                candidate.assessment_candidate_id,
            ],
            input_revision_map={episode.review_episode_id: episode.revision},
            created_at=NOW,
        )
        actions.append(publication.action)
        publication_gates.append(publication.gate_result)
        action_ids_by_component.setdefault(candidate.rule_component_id, []).append(action_id)

    old_assessment_by_component = {
        item["rule_component_id"]: item for item in payload["final_assessments"]
    }
    assessments = []
    review_run_id = payload["review_runs"][0]["review_run_id"]
    for candidate in candidates:
        component, rule = component_to_rule[candidate.rule_component_id]
        old = old_assessment_by_component[candidate.rule_component_id]
        publication = publish_assessment(
            candidate,
            component=component,
            rule_kind=rule.kind,
            evaluation=evaluations[candidate.rule_component_id],
            episode_stage=stage,
            expectations=expectations,
            conflict_groups=conflicts,
            assessment_id=old["assessment_id"],
            review_run_id=review_run_id,
            gate_result_id=old["gate_result_id"],
            input_revision_map={episode.review_episode_id: episode.revision},
            created_at=NOW,
            action_ids=action_ids_by_component.get(candidate.rule_component_id, []),
        )
        assessments.append(publication.assessment)
        publication_gates.append(publication.gate_result)

    calls = []
    agent_gates = []
    for item in payload["agent_calls"]:
        item["idempotency_key"] = f"{episode_namespace}:{item['idempotency_key']}"
        item["input_revision_map"] = {episode.review_episode_id: episode.revision}
        item["input_scope_hash"] = canonical_hash(
            {
                "review_episode_id": episode.review_episode_id,
                "evidence_snapshot_id": episode.evidence_snapshot_id,
                "source_ids": item["source_ids"],
                "input_revision_map": item["input_revision_map"],
            }
        )
        call = AgentCallContract.model_validate(item)
        calls.append(call)
        agent_gates.append(
            GateResult(
                gate_result_id=call.gate_result_ids[0],
                gate_name="agent-output-schema-gate",
                result=GateOutcome.ACCEPTED,
                input_scope_hash=call.input_scope_hash,
                input_revision_map=call.input_revision_map,
                input_entity_refs=[call.agent_call_id],
                accepted_entity_refs=[call.agent_call_id],
                affected_scope=call.recompute_scope,
                recompute_scope=call.recompute_scope,
                idempotency_key=f"gate:{call.idempotency_key}",
                created_at=NOW,
                output_hash=call.output_hash,
            )
        )

    rollup_gate_id = payload["episode_rollup"]["gate_result_id"]
    rollup_publication = publish_episode_rollup(
        review_episode_id=episode.review_episode_id,
        assessments=assessments,
        expectations=expectations,
        actions=actions,
        gate_result_id=rollup_gate_id,
        input_revision_map={episode.review_episode_id: episode.revision},
        created_at=NOW,
    )
    publication_gates.append(rollup_publication.gate_result)

    payload["evidence_expectations"] = [
        item.model_dump(mode="json") for item in expectations
    ]
    payload["assessment_candidates"] = [
        item.model_dump(mode="json") for item in candidates
    ]
    payload["final_assessments"] = [
        item.model_dump(mode="json") for item in assessments
    ]
    payload["actions"] = [item.model_dump(mode="json") for item in actions]
    payload["episode_rollup"] = rollup_publication.rollup.model_dump(mode="json")
    payload["agent_calls"] = [item.model_dump(mode="json") for item in calls]
    payload["gate_results"] = [
        item.model_dump(mode="json")
        for item in [*agent_gates, *publication_gates]
    ]
    payload["patient_profile"]["missing_expectation_ids"] = [
        item.expectation_id
        for item in expectations
        if item.status
        in {ExpectationStatus.ABSENT, ExpectationStatus.REFERENCED_MISSING}
    ]
    return FixtureV1.model_validate(payload)


def build_uat_workspace() -> UatWorkspaceFixture:
    scenarios = ["clear", "barrier", "gap_conflict", "gap_conflict", "clear", "barrier"]
    episodes = []
    primary_subject_ids = []
    for subject_number, scenario in enumerate(scenarios, start=1):
        base = build_fixture(scenario)
        subject_episodes = [
            namespace_fixture(base, subject_number=subject_number, stage=stage)
            for stage in (ReviewStage.SCREENING, ReviewStage.BASELINE)
        ]
        episodes.extend(subject_episodes)
        primary_subject_ids.append(subject_episodes[0].subject.subject_id)

    pre_screening = namespace_fixture(
        build_fixture("clear"),
        subject_number=7,
        stage=ReviewStage.PRE_SCREENING,
    )
    run_in = namespace_fixture(
        build_fixture("gap_conflict"),
        subject_number=8,
        stage=ReviewStage.RUN_IN,
    )
    episodes.extend([pre_screening, run_in])

    current_rules = rule_set()
    proposed_payload = current_rules.model_dump(mode="json")
    proposed_payload["revision"] = 2
    proposed_payload["protocol_version_id"] = "protocol-v2-draft"
    proposed_payload["rules"] = [
        rule for rule in proposed_payload["rules"] if rule["official_code"] != "REQ-02"
    ]
    for rule in proposed_payload["rules"]:
        if rule["official_code"] == "EX-01":
            rule["components"][0]["expression"]["children"][1]["children"][1][
                "time_constraint"
            ]["upper_bound_days"] = 35
    proposed_payload["rules"].append(
        Rule(
            rule_id="rule-ex-05",
            official_code="EX-05",
            kind=RuleKind.EXCLUSION,
            source_text="修订草案合成新增排除规则。",
            study_phase=StudyPhase.PHASE_III,
            components=[
                RuleComponent(
                    rule_component_id="component-ex-05",
                    parent_rule_id="rule-ex-05",
                    display_code="EX-05a",
                    title="修订草案新增条件",
                    expression=atomic_predicate(
                        "history", "new_exclusion_condition", "eq", True
                    ),
                )
            ],
        ).model_dump(mode="json")
    )
    proposed_rules = RuleSet.model_validate(proposed_payload)
    return UatWorkspaceFixture(
        workspace_id="uat-phase1-workspace",
        protocol_diff=ProtocolDiffExample(
            current_protocol_version_id="protocol-v1",
            proposed_protocol_version_id="protocol-v2-draft",
            current_rule_set=current_rules,
            proposed_rule_set_draft=proposed_rules,
            added_rule_codes=["EX-05"],
            deleted_rule_codes=["REQ-02"],
            changed_logic_or_window_codes=["EX-01"],
            source_refs=["protocol-v1:p10", "protocol-v2-draft:p12"],
        ),
        primary_subject_ids=primary_subject_ids,
        stage_template_episode_ids=[
            pre_screening.review_episode.review_episode_id,
            run_in.review_episode.review_episode_id,
        ],
        episodes=episodes,
    )


def main() -> None:
    schema = FixtureV1.model_json_schema(ref_template="#/$defs/{model}")
    schema["$id"] = "https://local.enrollment-review.invalid/contracts/fixture-v1.schema.json"
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    write_json(SCHEMA_ROOT / "fixture-v1.schema.json", schema)
    write_json(SCHEMA_ROOT / "openapi-v1.draft.json", openapi_draft(schema))

    agent_schema = AgentContractsV1.model_json_schema(ref_template="#/$defs/{model}")
    agent_schema["$id"] = "https://local.enrollment-review.invalid/contracts/agent-contracts-v1.schema.json"
    agent_schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    write_json(SCHEMA_ROOT / "agent-contracts-v1.schema.json", agent_schema)

    uat_schema = UatWorkspaceFixture.model_json_schema(ref_template="#/$defs/{model}")
    uat_schema["$id"] = "https://local.enrollment-review.invalid/contracts/uat-phase1-workspace.schema.json"
    uat_schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    write_json(SCHEMA_ROOT / "uat-phase1-workspace.schema.json", uat_schema)

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for scenario in ("clear", "barrier", "gap_conflict"):
        fixture = build_fixture(scenario)
        payload = fixture.model_dump(mode="json")
        validator.validate(payload)
        write_json(FIXTURE_ROOT / f"subject-{scenario}.json", payload)
    write_json(
        FIXTURE_ROOT / "uat-phase1-workspace.json",
        build_uat_workspace().model_dump(mode="json"),
    )


if __name__ == "__main__":
    main()
