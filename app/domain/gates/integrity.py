from __future__ import annotations

from app.domain.contracts.review import FixtureV1
from app.domain.contracts.rules import RuleSet
from app.domain.contracts.enums import ReviewStage


class ProtocolIntegrityError(ValueError):
    pass


class StageIsolationError(ValueError):
    pass


def validate_protocol_integrity(
    rule_set: RuleSet,
    *,
    expected_official_codes: list[str],
) -> None:
    actual = [rule.official_code for rule in rule_set.rules]
    if actual != expected_official_codes:
        raise ProtocolIntegrityError(
            f"官方规则编号或顺序不一致: expected={expected_official_codes}, actual={actual}"
        )


def validate_fixture_scope(fixture: FixtureV1) -> None:
    project = fixture.project
    episode = fixture.review_episode
    snapshot = fixture.evidence_snapshot
    protocol_id = project.protocol_version.protocol_version_id
    if fixture.subject.project_id != project.project_id:
        raise StageIsolationError("Subject 必须属于当前 Project")
    if episode.subject_id != fixture.subject.subject_id:
        raise StageIsolationError("ReviewEpisode 必须属于当前 Subject")
    if episode.project_id != project.project_id:
        raise StageIsolationError("ReviewEpisode project_id 不一致")
    if episode.rule_set_id != fixture.rule_set.rule_set_id:
        raise StageIsolationError("ReviewEpisode rule_set_id 不一致")
    if episode.study_phase != project.study_phase or episode.study_phase != fixture.rule_set.study_phase:
        raise StageIsolationError("Project、RuleSet 与 ReviewEpisode 的研究期别必须一致")
    if project.rule_set_id != fixture.rule_set.rule_set_id:
        raise StageIsolationError("Project rule_set_id 不一致")
    if fixture.rule_set.protocol_version_id != protocol_id or episode.protocol_version_id != protocol_id:
        raise StageIsolationError("方案版本闭包不一致")
    if episode.rule_set_revision != fixture.rule_set.revision:
        raise StageIsolationError("ReviewEpisode 规则 revision 不一致")
    if snapshot.evidence_snapshot_id != episode.evidence_snapshot_id:
        raise StageIsolationError("ReviewEpisode 与 EvidenceSnapshot 不一致")
    if snapshot.subject_id != fixture.subject.subject_id:
        raise StageIsolationError("EvidenceSnapshot subject_id 不一致")
    if snapshot.review_episode_id != episode.review_episode_id:
        raise StageIsolationError("EvidenceSnapshot review_episode_id 不一致")

    stage_rank = {
        ReviewStage.PRE_SCREENING: 0,
        ReviewStage.SCREENING: 1,
        ReviewStage.RUN_IN: 2,
        ReviewStage.BASELINE: 3,
    }
    if episode.stage not in {item.stage for item in fixture.workflow_stages}:
        raise StageIsolationError("ReviewEpisode stage 不在项目工作流中")

    documents = {item.source_document_version_id: item for item in fixture.source_documents}
    if set(snapshot.source_document_version_ids) != set(documents):
        raise StageIsolationError("EvidenceSnapshot 文件版本集合不完整或越界")
    for span in fixture.evidence_spans:
        if span.source_document_version_id not in documents:
            raise StageIsolationError("EvidenceSpan 引用了快照外文件")
    if any(stage_rank[item.review_stage] > stage_rank[episode.stage] for item in documents.values()):
        raise StageIsolationError("当前 Episode 不得读取未来阶段文件")

    span_ids = {item.evidence_span_id for item in fixture.evidence_spans}
    fact_ids = {item.fact_id for item in fixture.facts}
    component_ids = {
        component.rule_component_id
        for rule in fixture.rule_set.rules
        for component in rule.components
    }
    requirement_ids = {
        requirement.requirement_id
        for rule in fixture.rule_set.rules
        for component in rule.components
        for requirement in component.evidence_requirements
    }
    call_ids = {item.agent_call_id for item in fixture.agent_calls}
    gate_ids = {item.gate_result_id for item in fixture.gate_results}
    prompt_ids = {item.prompt_version_id for item in fixture.prompt_versions}
    model_ids = {item.model_config_id for item in fixture.model_configs}
    run_ids = {item.review_run_id for item in fixture.review_runs}
    action_ids = {item.action_id for item in fixture.actions}
    for call in fixture.agent_calls:
        if call.prompt_version_id not in prompt_ids or call.model_config_id not in model_ids:
            raise StageIsolationError("AgentCall PromptVersion 或 ModelConfig 越界")
        if not set(call.gate_result_ids) <= gate_ids:
            raise StageIsolationError("AgentCall GateResult 越界")
        if not set(call.source_ids) <= set(documents):
            raise StageIsolationError("AgentCall 来源文件越界")
    for fact in fixture.facts:
        if not set(fact.evidence_span_ids) <= span_ids:
            raise StageIsolationError("ClinicalFact 引用了当前快照外 EvidenceSpan")
    for expectation in fixture.evidence_expectations:
        if expectation.review_episode_id != episode.review_episode_id:
            raise StageIsolationError("EvidenceExpectation episode 不一致")
        if expectation.requirement_id not in requirement_ids:
            raise StageIsolationError("EvidenceExpectation requirement 越界")
        if not set(expectation.evidence_span_ids) <= span_ids:
            raise StageIsolationError("EvidenceExpectation Span 越界")
    for candidate in fixture.assessment_candidates:
        if candidate.agent_call_id not in call_ids:
            raise StageIsolationError("AssessmentCandidate AgentCall 越界")
        if candidate.rule_component_id not in component_ids:
            raise StageIsolationError("AssessmentCandidate 规则组件越界")
        if not set(candidate.used_fact_ids) <= fact_ids or not set(candidate.evidence_span_ids) <= span_ids:
            raise StageIsolationError("AssessmentCandidate 事实或 Span 越界")
    for assessment in fixture.final_assessments:
        if assessment.review_run_id not in run_ids:
            raise StageIsolationError("FinalAssessment ReviewRun 越界")
        if assessment.rule_component_id not in component_ids:
            raise StageIsolationError("FinalAssessment 规则组件越界")
        if not set(assessment.used_fact_ids) <= fact_ids:
            raise StageIsolationError("FinalAssessment 事实越界")
        if not set(assessment.evidence_span_ids) <= span_ids:
            raise StageIsolationError("FinalAssessment Span 越界")
        if not set(assessment.action_ids) <= action_ids:
            raise StageIsolationError("FinalAssessment Action 越界")
        if assessment.gate_result_id not in gate_ids:
            raise StageIsolationError("FinalAssessment GateResult 越界")
    for action in fixture.actions:
        if action.rule_component_id not in component_ids:
            raise StageIsolationError("ActionRequest 规则组件越界")
        if action.trigger_evidence_span_id is not None and action.trigger_evidence_span_id not in span_ids:
            raise StageIsolationError("ActionRequest 触发 Span 越界")
    if fixture.patient_profile.subject_id != fixture.subject.subject_id:
        raise StageIsolationError("PatientProfile subject 不一致")
    if fixture.patient_profile.review_episode_id != episode.review_episode_id:
        raise StageIsolationError("PatientProfile episode 不一致")
    for event in fixture.patient_profile.events:
        if not set(event.fact_ids) <= fact_ids or not set(event.evidence_span_ids) <= span_ids:
            raise StageIsolationError("PatientProfileEvent 事实或 Span 越界")
        if not set(event.related_rule_component_ids) <= component_ids:
            raise StageIsolationError("PatientProfileEvent 规则组件越界")
    for conflict in fixture.conflict_groups:
        if not set(conflict.fact_ids) <= fact_ids:
            raise StageIsolationError("ConflictGroup 事实越界")
        if not set(conflict.affected_rule_component_ids) <= component_ids:
            raise StageIsolationError("ConflictGroup 规则组件越界")
        if not set(conflict.resolution_evidence_span_ids) <= span_ids:
            raise StageIsolationError("ConflictGroup 解决证据越界")
    for run in fixture.review_runs:
        if run.review_episode_id != episode.review_episode_id:
            raise StageIsolationError("ReviewRun episode 不一致")
        if run.protocol_version_id != protocol_id:
            raise StageIsolationError("ReviewRun 方案版本不一致")
        if run.rule_set_revision != fixture.rule_set.revision:
            raise StageIsolationError("ReviewRun 规则 revision 不一致")
        if run.evidence_snapshot_id != snapshot.evidence_snapshot_id:
            raise StageIsolationError("ReviewRun 快照不一致")
