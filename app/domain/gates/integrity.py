from __future__ import annotations

from app.domain.contracts.review import FixtureV1, ProtocolDocumentVersion
from app.domain.contracts.rules import (
    ProtocolAuthorityRecord,
    ProtocolIntegrityManifest,
    RuleSet,
    WorkflowStage,
)
from app.domain.contracts.agents import GateResult
from app.domain.contracts.enums import (
    ComponentDecision,
    ExpectationStatus,
    GateOutcome,
    ReviewStage,
)
from app.domain.publication import canonical_hash
from datetime import datetime


class ProtocolIntegrityError(ValueError):
    pass


class StageIsolationError(ValueError):
    pass


def build_protocol_authority_record(
    *,
    authority_record_id: str,
    protocol_version_id: str,
    protocol_document_sha256: str,
    study_phase,
    official_rules,
    official_workflow_stages,
    rule_source_anchor_refs: dict[str, list[str]],
    verified_by: str,
    verified_at: datetime,
) -> ProtocolAuthorityRecord:
    data = {
        "authority_record_id": authority_record_id,
        "protocol_version_id": protocol_version_id,
        "protocol_document_sha256": protocol_document_sha256,
        "study_phase": study_phase,
        "official_rules": official_rules,
        "official_workflow_stages": official_workflow_stages,
        "rule_source_anchor_refs": rule_source_anchor_refs,
        "verified_by": verified_by,
        "verified_at": verified_at,
        "verification_method": "human_verified_official_protocol",
    }
    draft = ProtocolAuthorityRecord.model_construct(
        **data,
        authority_record_sha256="0" * 64,
    )
    return ProtocolAuthorityRecord(
        **data,
        authority_record_sha256=canonical_hash(
            draft.model_dump(mode="json", exclude={"authority_record_sha256"})
        ),
    )


def publish_protocol_authority_acceptance(
    record: ProtocolAuthorityRecord,
    *,
    gate_result_id: str,
    created_at: datetime,
) -> GateResult:
    payload = record.model_dump(mode="json")
    return GateResult(
        gate_result_id=gate_result_id,
        gate_name="protocol-authority-human-acceptance-gate",
        result=GateOutcome.ACCEPTED,
        input_scope_hash=canonical_hash(payload),
        input_revision_map={record.protocol_version_id: 1},
        input_entity_refs=[
            record.protocol_version_id,
            record.protocol_document_sha256,
            *record.rule_source_anchor_refs,
        ],
        accepted_entity_refs=[record.authority_record_id],
        affected_scope=[record.protocol_version_id],
        recompute_scope=[record.protocol_version_id],
        idempotency_key=f"protocol-authority:{record.protocol_version_id}",
        created_at=created_at,
        output_hash=canonical_hash(payload),
    )


def assert_protocol_integrity(
    rule_set: RuleSet,
    *,
    workflow_stages: list[WorkflowStage],
    protocol_version: ProtocolDocumentVersion,
    manifest: ProtocolIntegrityManifest,
    authority_record: ProtocolAuthorityRecord,
    authority_gate_result: GateResult,
) -> None:
    if (
        manifest.protocol_version_id != protocol_version.protocol_version_id
        or manifest.protocol_document_sha256 != protocol_version.sha256
        or manifest.manifest_sha256 != protocol_version.integrity_manifest_sha256
        or authority_record.authority_record_sha256
        != protocol_version.authority_record_sha256
        or authority_record.authority_record_id != manifest.authority_record_id
        or authority_record.authority_record_sha256
        != manifest.authority_record_sha256
        or authority_record.protocol_version_id != protocol_version.protocol_version_id
        or authority_record.protocol_document_sha256 != protocol_version.sha256
        or rule_set.protocol_version_id != protocol_version.protocol_version_id
        or rule_set.study_phase != manifest.study_phase
    ):
        raise ProtocolIntegrityError("RuleSet、权威 Manifest 与正式方案版本闭包不一致")
    if (
        authority_gate_result.gate_result_id
        != protocol_version.authority_gate_result_id
        or authority_gate_result.gate_name
        != "protocol-authority-human-acceptance-gate"
        or authority_gate_result.result != GateOutcome.ACCEPTED
        or authority_record.authority_record_id
        not in authority_gate_result.accepted_entity_refs
        or authority_gate_result.output_hash
        != canonical_hash(authority_record.model_dump(mode="json"))
    ):
        raise ProtocolIntegrityError("正式方案权威记录未通过独立人工验收 Gate")
    actual_rules = [item.model_dump(mode="json") for item in rule_set.rules]
    expected_rules = [
        item.model_dump(mode="json") for item in authority_record.official_rules
    ]
    if actual_rules != expected_rules:
        expected_codes = [item.official_code for item in authority_record.official_rules]
        actual_codes = [item.official_code for item in rule_set.rules]
        raise ProtocolIntegrityError(
            "官方规则编号、父子组件、逻辑、单位、时间窗、例外或证据要求与权威方案不一致: "
            f"expected_codes={expected_codes}, actual_codes={actual_codes}"
        )
    if [item.model_dump(mode="json") for item in workflow_stages] != [
        item.model_dump(mode="json")
        for item in authority_record.official_workflow_stages
    ]:
        raise ProtocolIntegrityError("审核阶段或 requirement 到期结构与权威方案不一致")
    if manifest.authoritative_rule_set_sha256 != canonical_hash(expected_rules):
        raise ProtocolIntegrityError("Manifest 的权威规则哈希与 AuthorityRecord 不一致")
    expected_workflow = [
        item.model_dump(mode="json") for item in authority_record.official_workflow_stages
    ]
    if manifest.authoritative_workflow_sha256 != canonical_hash(expected_workflow):
        raise ProtocolIntegrityError("Manifest 的工作流哈希与 AuthorityRecord 不一致")


def publish_protocol_integrity_acceptance(
    rule_set: RuleSet,
    *,
    workflow_stages: list[WorkflowStage],
    protocol_version: ProtocolDocumentVersion,
    manifest: ProtocolIntegrityManifest,
    authority_record: ProtocolAuthorityRecord,
    authority_gate_result: GateResult,
    gate_result_id: str,
    input_revision_map: dict[str, int],
    created_at: datetime,
) -> GateResult:
    assert_protocol_integrity(
        rule_set,
        workflow_stages=workflow_stages,
        protocol_version=protocol_version,
        manifest=manifest,
        authority_record=authority_record,
        authority_gate_result=authority_gate_result,
    )
    if gate_result_id != protocol_version.integrity_gate_result_id:
        raise ProtocolIntegrityError("ProtocolVersion 未绑定当前 Integrity Gate ID")
    payload = {
        "rule_set": rule_set.model_dump(mode="json"),
        "workflow_stages": [item.model_dump(mode="json") for item in workflow_stages],
        "protocol_version": protocol_version.model_dump(mode="json"),
        "manifest": manifest.model_dump(mode="json"),
        "authority_record": authority_record.model_dump(mode="json"),
        "authority_gate_result_id": authority_gate_result.gate_result_id,
    }
    return GateResult(
        gate_result_id=gate_result_id,
        gate_name="protocol-integrity-gate",
        result=GateOutcome.ACCEPTED,
        input_scope_hash=canonical_hash(payload),
        input_revision_map=input_revision_map,
        input_entity_refs=[
            protocol_version.protocol_version_id,
            authority_record.authority_record_id,
            authority_gate_result.gate_result_id,
            manifest.manifest_id,
            rule_set.rule_set_id,
        ],
        accepted_entity_refs=[manifest.manifest_id, rule_set.rule_set_id],
        affected_scope=[protocol_version.protocol_version_id],
        recompute_scope=[protocol_version.protocol_version_id],
        idempotency_key=(
            f"protocol-integrity:{protocol_version.protocol_version_id}:"
            f"{rule_set.revision}"
        ),
        created_at=created_at,
        output_hash=canonical_hash(payload),
    )


def require_protocol_integrity_acceptance(
    gate_result: GateResult,
    *,
    rule_set: RuleSet,
    workflow_stages: list[WorkflowStage],
    protocol_version: ProtocolDocumentVersion,
    manifest: ProtocolIntegrityManifest,
    authority_record: ProtocolAuthorityRecord,
    authority_gate_result: GateResult,
) -> None:
    expected = publish_protocol_integrity_acceptance(
        rule_set,
        workflow_stages=workflow_stages,
        protocol_version=protocol_version,
        manifest=manifest,
        authority_record=authority_record,
        authority_gate_result=authority_gate_result,
        gate_result_id=protocol_version.integrity_gate_result_id,
        input_revision_map=gate_result.input_revision_map,
        created_at=gate_result.created_at,
    )
    if gate_result.model_dump(mode="json") != expected.model_dump(mode="json"):
        raise ProtocolIntegrityError("存储的 Protocol Integrity GateResult 闭包无效")


def build_protocol_integrity_manifest(
    *,
    manifest_id: str,
    protocol_version_id: str,
    protocol_document_sha256: str,
    study_phase,
    source_refs: list[str],
    authority_record: ProtocolAuthorityRecord,
    authority_gate_result: GateResult,
) -> ProtocolIntegrityManifest:
    if (
        authority_gate_result.gate_name
        != "protocol-authority-human-acceptance-gate"
        or authority_gate_result.result != GateOutcome.ACCEPTED
        or authority_record.authority_record_id
        not in authority_gate_result.accepted_entity_refs
        or authority_gate_result.output_hash
        != canonical_hash(authority_record.model_dump(mode="json"))
    ):
        raise ProtocolIntegrityError("不能从未验收的 ProtocolAuthorityRecord 构建 Manifest")
    if (
        authority_record.protocol_version_id != protocol_version_id
        or authority_record.protocol_document_sha256 != protocol_document_sha256
        or authority_record.study_phase != study_phase
    ):
        raise ProtocolIntegrityError("AuthorityRecord 与方案版本或期别不一致")
    data = {
        "manifest_id": manifest_id,
        "protocol_version_id": protocol_version_id,
        "protocol_document_sha256": protocol_document_sha256,
        "study_phase": study_phase,
        "source_refs": source_refs,
        "authority_record_id": authority_record.authority_record_id,
        "authority_record_sha256": authority_record.authority_record_sha256,
        "authoritative_rule_set_sha256": canonical_hash(
            [item.model_dump(mode="json") for item in authority_record.official_rules]
        ),
        "authoritative_workflow_sha256": canonical_hash(
            [
                item.model_dump(mode="json")
                for item in authority_record.official_workflow_stages
            ]
        ),
    }
    draft = ProtocolIntegrityManifest.model_construct(
        **data,
        manifest_sha256="0" * 64,
    )
    return ProtocolIntegrityManifest(
        **data,
        manifest_sha256=canonical_hash(
            draft.model_dump(mode="json", exclude={"manifest_sha256"})
        ),
    )


def validate_fixture_scope(fixture: FixtureV1) -> None:
    project = fixture.project
    episode = fixture.review_episode
    snapshot = fixture.evidence_snapshot
    protocol_id = project.protocol_version.protocol_version_id
    authority_gate_result = next(
        (
            item
            for item in fixture.gate_results
            if item.gate_result_id
            == fixture.project.protocol_version.authority_gate_result_id
        ),
        None,
    )
    if authority_gate_result is None:
        raise StageIsolationError("Fixture 缺少方案权威人工验收 Gate")
    assert_protocol_integrity(
        fixture.rule_set,
        workflow_stages=fixture.workflow_stages,
        protocol_version=project.protocol_version,
        manifest=fixture.protocol_integrity_manifest,
        authority_record=fixture.protocol_authority_record,
        authority_gate_result=authority_gate_result,
    )
    integrity_gate_result = next(
        (
            item
            for item in fixture.gate_results
            if item.gate_result_id
            == fixture.project.protocol_version.integrity_gate_result_id
        ),
        None,
    )
    if integrity_gate_result is None:
        raise StageIsolationError("Fixture 缺少 Protocol Integrity Gate")
    require_protocol_integrity_acceptance(
        integrity_gate_result,
        rule_set=fixture.rule_set,
        workflow_stages=fixture.workflow_stages,
        protocol_version=fixture.project.protocol_version,
        manifest=fixture.protocol_integrity_manifest,
        authority_record=fixture.protocol_authority_record,
        authority_gate_result=authority_gate_result,
    )
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
    requirement_by_id = {
        requirement.requirement_id: requirement
        for rule in fixture.rule_set.rules
        for component in rule.components
        for requirement in component.evidence_requirements
    }
    component_by_id = {
        component.rule_component_id: component
        for rule in fixture.rule_set.rules
        for component in rule.components
    }
    call_ids = {item.agent_call_id for item in fixture.agent_calls}
    gate_ids = {item.gate_result_id for item in fixture.gate_results}
    if len(gate_ids) != len(fixture.gate_results):
        raise StageIsolationError("GateResult ID 必须唯一")
    gate_by_id = {item.gate_result_id: item for item in fixture.gate_results}
    prompt_ids = {item.prompt_version_id for item in fixture.prompt_versions}
    model_ids = {item.model_config_id for item in fixture.model_configs}
    run_ids = {item.review_run_id for item in fixture.review_runs}
    assessment_by_id = {
        item.assessment_id: item for item in fixture.final_assessments
    }
    assessment_ids = set(assessment_by_id)
    for call in fixture.agent_calls:
        if call.prompt_version_id not in prompt_ids or call.model_config_id not in model_ids:
            raise StageIsolationError("AgentCall PromptVersion 或 ModelConfig 越界")
        if not set(call.gate_result_ids) <= gate_ids:
            raise StageIsolationError("AgentCall GateResult 越界")
        if not set(call.source_ids) <= set(documents):
            raise StageIsolationError("AgentCall 来源文件越界")
        if (
            call.project_id != project.project_id
            or call.subject_id != fixture.subject.subject_id
            or call.review_episode_id != episode.review_episode_id
            or call.review_run_id not in run_ids
            or call.evidence_snapshot_id != snapshot.evidence_snapshot_id
        ):
            raise StageIsolationError("AgentCall 超出当前 Project/Subject/Episode/Run/Snapshot")
        for gate_id in call.gate_result_ids:
            gate = gate_by_id[gate_id]
            if (
                gate.result != GateOutcome.ACCEPTED
                or call.agent_call_id not in gate.accepted_entity_refs
                or gate.output_hash != call.output_hash
            ):
                raise StageIsolationError("AgentCall 未通过 accepted GateResult 发布")
    call_by_id = {item.agent_call_id: item for item in fixture.agent_calls}
    normalized_fact_ids: set[str] = set()
    normalized_span_ids: set[str] = set()
    from app.domain.gates.evidence import require_accepted_evidence_gate

    for candidate in fixture.evidence_normalization_candidates:
        call = call_by_id.get(candidate.created_by_agent_call_id)
        if call is None:
            raise StageIsolationError("EvidenceNormalizationCandidate AgentCall 越界")
        if (
            candidate.project_id != project.project_id
            or candidate.protocol_version_id != protocol_id
            or candidate.subject_id != fixture.subject.subject_id
            or candidate.review_episode_id != episode.review_episode_id
            or candidate.evidence_snapshot_id != snapshot.evidence_snapshot_id
        ):
            raise StageIsolationError(
                "EvidenceNormalizationCandidate 超出当前完整证据 scope"
            )
        normalized_fact_ids.update(
            item.fact_id for item in candidate.clinical_fact_candidates
        )
        normalized_span_ids.update(
            item.evidence_span_id for item in candidate.evidence_span_candidates
        )
        evidence_gates = [
            item
            for item in fixture.gate_results
            if item.gate_name == "evidence-acceptance-gate"
            and candidate.candidate_id in item.accepted_entity_refs
        ]
        if not evidence_gates:
            raise StageIsolationError(
                "EvidenceNormalizationCandidate 未通过 Evidence Gate 发布"
            )
        try:
            require_accepted_evidence_gate(
                evidence_gates[0],
                candidate=candidate,
                agent_call=call,
                agent_call_gate_result=gate_by_id[call.gate_result_ids[0]],
            )
        except ValueError as exc:
            raise StageIsolationError(str(exc)) from exc
    if normalized_fact_ids != fact_ids or normalized_span_ids != span_ids:
        raise StageIsolationError(
            "Fixture 事实和 Span 必须完整来自 accepted Evidence Candidate"
        )
    for fact in fixture.facts:
        if not set(fact.evidence_span_ids) <= span_ids:
            raise StageIsolationError("ClinicalFact 引用了当前快照外 EvidenceSpan")
        if (
            fact.project_id != project.project_id
            or fact.subject_id != fixture.subject.subject_id
            or fact.review_episode_id != episode.review_episode_id
            or fact.evidence_snapshot_id != snapshot.evidence_snapshot_id
        ):
            raise StageIsolationError(
                "ClinicalFact 超出当前 Project/Subject/Episode/Snapshot"
            )
    for expectation in fixture.evidence_expectations:
        if expectation.review_episode_id != episode.review_episode_id:
            raise StageIsolationError("EvidenceExpectation episode 不一致")
        if expectation.requirement_id not in requirement_ids:
            raise StageIsolationError("EvidenceExpectation requirement 越界")
        if not set(expectation.evidence_span_ids) <= span_ids:
            raise StageIsolationError("EvidenceExpectation Span 越界")
        requirement = requirement_by_id[expectation.requirement_id]
        is_due = stage_rank[requirement.due_stage] <= stage_rank[episode.stage]
        if is_due and expectation.status == ExpectationStatus.NOT_DUE:
            raise StageIsolationError("已到期 EvidenceRequirement 不能保持 not_due")
        if not is_due and expectation.status != ExpectationStatus.NOT_DUE:
            raise StageIsolationError("未来阶段 EvidenceRequirement 只能记录为 not_due")
    for candidate in fixture.assessment_candidates:
        if candidate.agent_call_id not in call_ids:
            raise StageIsolationError("AssessmentCandidate AgentCall 越界")
        if candidate.rule_component_id not in component_ids:
            raise StageIsolationError("AssessmentCandidate 规则组件越界")
        if not set(candidate.used_fact_ids) <= fact_ids or not set(candidate.evidence_span_ids) <= span_ids:
            raise StageIsolationError("AssessmentCandidate 事实或 Span 越界")
        if (
            candidate.project_id != project.project_id
            or candidate.protocol_version_id != protocol_id
            or candidate.subject_id != fixture.subject.subject_id
            or candidate.rule_set_id != fixture.rule_set.rule_set_id
            or candidate.rule_set_revision != fixture.rule_set.revision
            or candidate.review_run_id not in run_ids
            or candidate.review_episode_id != episode.review_episode_id
            or candidate.evidence_snapshot_id != snapshot.evidence_snapshot_id
        ):
            raise StageIsolationError("AssessmentCandidate 超出当前完整审核 scope")
    for assessment in fixture.final_assessments:
        if assessment.review_run_id not in run_ids:
            raise StageIsolationError("FinalAssessment ReviewRun 越界")
        if (
            assessment.project_id != project.project_id
            or assessment.protocol_version_id != protocol_id
            or assessment.subject_id != fixture.subject.subject_id
            or assessment.rule_set_id != fixture.rule_set.rule_set_id
            or assessment.rule_set_revision != fixture.rule_set.revision
            or assessment.review_episode_id != episode.review_episode_id
            or assessment.evidence_snapshot_id != snapshot.evidence_snapshot_id
        ):
            raise StageIsolationError("FinalAssessment 超出当前完整审核 scope")
        if assessment.rule_component_id not in component_ids:
            raise StageIsolationError("FinalAssessment 规则组件越界")
        if not set(assessment.used_fact_ids) <= fact_ids:
            raise StageIsolationError("FinalAssessment 事实越界")
        if not set(assessment.evidence_span_ids) <= span_ids:
            raise StageIsolationError("FinalAssessment Span 越界")
        if assessment.gate_result_id not in gate_ids:
            raise StageIsolationError("FinalAssessment GateResult 越界")
        gate = gate_by_id[assessment.gate_result_id]
        if (
            gate.result != GateOutcome.ACCEPTED
            or assessment.assessment_id not in gate.accepted_entity_refs
            or gate.output_hash
            != canonical_hash(assessment.model_dump(mode="json"))
        ):
            raise StageIsolationError("FinalAssessment 未通过 accepted GateResult 发布")
        component = component_by_id[assessment.rule_component_id]
        due_stages = [item.due_stage for item in component.evidence_requirements]
        all_future = bool(due_stages) and all(
            stage_rank[item] > stage_rank[episode.stage] for item in due_stages
        )
        if all_future and assessment.decision != ComponentDecision.NOT_DUE:
            raise StageIsolationError("未来阶段组件必须发布为 not_due")
        if not all_future and assessment.decision == ComponentDecision.NOT_DUE:
            raise StageIsolationError("当前已到期组件不能发布为 not_due")
    for action in fixture.actions:
        if action.rule_component_id not in component_ids:
            raise StageIsolationError("ActionRequest 规则组件越界")
        if (
            action.project_id != project.project_id
            or action.protocol_version_id != protocol_id
            or action.subject_id != fixture.subject.subject_id
            or action.rule_set_id != fixture.rule_set.rule_set_id
            or action.rule_set_revision != fixture.rule_set.revision
            or action.review_episode_id != episode.review_episode_id
            or action.evidence_snapshot_id != snapshot.evidence_snapshot_id
            or action.review_run_id not in run_ids
            or action.assessment_id not in assessment_ids
        ):
            raise StageIsolationError("ActionRequest 超出当前 Assessment/Episode scope")
        if action.trigger_evidence_span_id is not None and action.trigger_evidence_span_id not in span_ids:
            raise StageIsolationError("ActionRequest 触发 Span 越界")
        if action.gate_result_id not in gate_ids:
            raise StageIsolationError("ActionRequest GateResult 越界")
        gate = gate_by_id[action.gate_result_id]
        source_assessment = assessment_by_id[action.assessment_id]
        if (
            gate.result != GateOutcome.ACCEPTED
            or action.action_id not in gate.accepted_entity_refs
            or action.assessment_id not in gate.input_entity_refs
            or source_assessment.gate_result_id not in gate.input_entity_refs
            or gate.output_hash != canonical_hash(action.model_dump(mode="json"))
        ):
            raise StageIsolationError("ActionRequest 未通过 accepted GateResult 发布")
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

    rollup = fixture.episode_rollup
    if rollup.review_episode_id != episode.review_episode_id:
        raise StageIsolationError("EpisodeRollup episode 不一致")
    if set(rollup.input_assessment_ids) != {
        item.assessment_id for item in fixture.final_assessments
    }:
        raise StageIsolationError("EpisodeRollup Assessment 输入不完整")
    if set(rollup.input_expectation_ids) != {
        item.expectation_id for item in fixture.evidence_expectations
    }:
        raise StageIsolationError("EpisodeRollup Expectation 输入不完整")
    if set(rollup.input_action_ids) != {item.action_id for item in fixture.actions}:
        raise StageIsolationError("EpisodeRollup Action 输入不完整")
    if rollup.gate_result_id not in gate_ids:
        raise StageIsolationError("EpisodeRollup GateResult 越界")
    rollup_gate = gate_by_id[rollup.gate_result_id]
    if (
        rollup_gate.result != GateOutcome.ACCEPTED
        or f"rollup:{episode.review_episode_id}" not in rollup_gate.accepted_entity_refs
        or rollup_gate.output_hash != canonical_hash(rollup.model_dump(mode="json"))
    ):
        raise StageIsolationError("EpisodeRollup 未通过 accepted Projection Gate 发布")
