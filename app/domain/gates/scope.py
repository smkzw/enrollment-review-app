from __future__ import annotations

from dataclasses import dataclass

from app.domain.contracts.agents import AgentCallContract, ModelConfigContract, PromptVersion
from app.domain.contracts.evidence import EvidenceSnapshot
from app.domain.contracts.enums import ReviewStage
from app.domain.contracts.review import (
    Project,
    ProtocolDocumentVersion,
    ReviewEpisode,
    ReviewRun,
    Subject,
)
from app.domain.contracts.rules import RuleSet
from app.domain.publication import canonical_hash
from app.domain.registry import TrustedPublicationRegistry


class ReviewScopeError(ValueError):
    pass


STAGE_RANK = {
    ReviewStage.PRE_SCREENING: 0,
    ReviewStage.SCREENING: 1,
    ReviewStage.RUN_IN: 2,
    ReviewStage.BASELINE: 3,
}


@dataclass(frozen=True)
class RegisteredReviewScope:
    project: Project
    protocol_version: ProtocolDocumentVersion
    rule_set: RuleSet
    subject: Subject
    episode: ReviewEpisode
    snapshot: EvidenceSnapshot
    review_run: ReviewRun
    prompt_version: PromptVersion
    model_config: ModelConfigContract


def require_registered_review_scope(
    agent_call: AgentCallContract,
    *,
    registry: TrustedPublicationRegistry,
    expected_schema_version: str,
) -> RegisteredReviewScope:
    """Resolve one immutable review scope and reject every mixed-version graph."""

    required_ids = {
        "project_id": agent_call.project_id,
        "protocol_version_id": agent_call.protocol_version_id,
        "rule_set_id": agent_call.rule_set_id,
        "subject_id": agent_call.subject_id,
        "review_episode_id": agent_call.review_episode_id,
        "review_run_id": agent_call.review_run_id,
        "evidence_snapshot_id": agent_call.evidence_snapshot_id,
    }
    missing = [name for name, value in required_ids.items() if value is None]
    if missing:
        raise ReviewScopeError(
            f"受试者审核调用缺少完整登记作用域: {', '.join(missing)}"
        )

    project = registry.require("project", agent_call.project_id)
    protocol_version = registry.require(
        "protocol_document_version", agent_call.protocol_version_id
    )
    rule_set = registry.require("rule_set", agent_call.rule_set_id)
    subject = registry.require("subject", agent_call.subject_id)
    episode = registry.require("review_episode", agent_call.review_episode_id)
    snapshot = registry.require("evidence_snapshot", agent_call.evidence_snapshot_id)
    review_run = registry.require("review_run", agent_call.review_run_id)
    prompt_version = registry.require("prompt_version", agent_call.prompt_version_id)
    model_config = registry.require("model_config", agent_call.model_config_id)
    source_documents = [
        registry.require("source_document_version", source_id)
        for source_id in agent_call.source_ids
    ]
    gate_results = [
        registry.require("gate_result", gate_id)
        for gate_id in agent_call.gate_result_ids
    ]

    if canonical_hash(project.protocol_version.model_dump(mode="json")) != canonical_hash(
        protocol_version.model_dump(mode="json")
    ):
        raise ReviewScopeError("项目内方案版本与服务端独立登记版本不一致")
    if (
        project.project_id != agent_call.project_id
        or project.rule_set_id != rule_set.rule_set_id
        or protocol_version.protocol_version_id != rule_set.protocol_version_id
        or subject.project_id != project.project_id
        or episode.project_id != project.project_id
        or episode.subject_id != subject.subject_id
        or episode.protocol_version_id != protocol_version.protocol_version_id
        or episode.rule_set_id != rule_set.rule_set_id
        or episode.rule_set_revision != rule_set.revision
        or episode.study_phase != project.study_phase
        or rule_set.study_phase != project.study_phase
        or episode.evidence_snapshot_id != snapshot.evidence_snapshot_id
        or snapshot.subject_id != subject.subject_id
        or snapshot.review_episode_id != episode.review_episode_id
        or review_run.review_episode_id != episode.review_episode_id
        or review_run.protocol_version_id != protocol_version.protocol_version_id
        or review_run.rule_set_revision != rule_set.revision
        or review_run.evidence_snapshot_id != snapshot.evidence_snapshot_id
        or set(snapshot.source_document_version_ids) != set(agent_call.source_ids)
        or len(snapshot.source_document_version_ids)
        != len(set(snapshot.source_document_version_ids))
        or len(set(agent_call.source_ids)) != len(agent_call.source_ids)
        or len(source_documents) != len(agent_call.source_ids)
    ):
        raise ReviewScopeError(
            "审核调用未绑定同一项目、方案版本、规则集、受试者、审核节点、运行和证据快照"
        )
    if any(
        STAGE_RANK[source.review_stage] > STAGE_RANK[episode.stage]
        for source in source_documents
    ):
        raise ReviewScopeError("当前审核节点不得读取未来节点的来源文件")
    if len(agent_call.gate_result_ids) != len(set(agent_call.gate_result_ids)):
        raise ReviewScopeError("审核调用的验收结果引用不得重复")
    schema_gates = [
        gate for gate in gate_results if gate.gate_name == "agent-output-schema-gate"
    ]
    if len(schema_gates) != 1:
        raise ReviewScopeError("审核调用必须且只能绑定一个结构化输出验收结果")
    if prompt_version.node != agent_call.node:
        raise ReviewScopeError("提示词版本所属节点与当前审核调用不一致")
    if prompt_version.schema_version_id != expected_schema_version:
        raise ReviewScopeError("提示词版本的结构化输出合同与当前候选不一致")

    return RegisteredReviewScope(
        project=project,
        protocol_version=protocol_version,
        rule_set=rule_set,
        subject=subject,
        episode=episode,
        snapshot=snapshot,
        review_run=review_run,
        prompt_version=prompt_version,
        model_config=model_config,
    )
