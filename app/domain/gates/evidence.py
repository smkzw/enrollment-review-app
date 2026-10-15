from __future__ import annotations

from datetime import datetime

from app.domain.contracts.agents import AgentCallContract, GateResult
from app.domain.contracts.enums import AgentNode, GateOutcome
from app.domain.contracts.evidence import ClinicalFact, EvidenceSpan
from app.domain.contracts.normalization import EvidenceNormalizationCandidate
from app.domain.publication import canonical_hash
from app.domain.registry import TrustedPublicationRegistry
from .scope import require_registered_review_scope
from .permissions import require_accepted_agent_call


class EvidenceGateError(ValueError):
    pass


def evidence_scope_payload(
    *,
    candidate: EvidenceNormalizationCandidate,
    agent_call: AgentCallContract,
    agent_call_gate_result: GateResult,
    source_documents,
) -> dict:
    return {
        "candidate": candidate.model_dump(mode="json"),
        "agent_call_id": agent_call.agent_call_id,
        "agent_call_gate_result_id": agent_call_gate_result.gate_result_id,
        "agent_call_input_scope_hash": agent_call.input_scope_hash,
        "agent_call_output_hash": agent_call.output_hash,
        "source_documents": [
            item.model_dump(mode="json")
            for item in sorted(
                source_documents,
                key=lambda value: value.source_document_version_id,
            )
        ],
        "facts": [
            item.model_dump(mode="json")
            for item in sorted(
                candidate.clinical_fact_candidates,
                key=lambda value: value.fact_id,
            )
        ],
        "evidence_spans": [
            item.model_dump(mode="json")
            for item in sorted(
                candidate.evidence_span_candidates,
                key=lambda value: value.evidence_span_id,
            )
        ],
    }


def publish_evidence_acceptance(
    *,
    candidate: EvidenceNormalizationCandidate,
    agent_call: AgentCallContract,
    agent_call_gate_result: GateResult,
    gate_result_id: str,
    input_revision_map: dict[str, int],
    created_at: datetime,
    registry: TrustedPublicationRegistry,
) -> GateResult:
    registry.require("agent_call", agent_call.agent_call_id, agent_call)
    registry.require(
        "gate_result", agent_call_gate_result.gate_result_id, agent_call_gate_result
    )
    registry.require("evidence_candidate", candidate.candidate_id, candidate)
    require_accepted_agent_call(agent_call, agent_call_gate_result)
    if agent_call.review_run_id is None:
        raise EvidenceGateError("Evidence AgentCall 缺少 ReviewRun")
    scope = require_registered_review_scope(
        agent_call,
        registry=registry,
        expected_schema_version=candidate.schema_version,
    )
    source_documents = [
        registry.require("source_document_version", source_id)
        for source_id in agent_call.source_ids
    ]
    if (
        scope.project.project_id != candidate.project_id
        or scope.protocol_version.protocol_version_id
        != candidate.protocol_version_id
        or scope.subject.subject_id != candidate.subject_id
        or scope.episode.review_episode_id != candidate.review_episode_id
        or scope.snapshot.evidence_snapshot_id != candidate.evidence_snapshot_id
        or set(candidate.source_refs) != set(agent_call.source_ids)
        or len(candidate.source_refs) != len(set(candidate.source_refs))
    ):
        raise EvidenceGateError(
            "Evidence Candidate 未绑定服务端登记的受试者、审核节点、证据快照和完整文件集合"
        )
    if agent_call.typed_output_hashes.get(candidate.candidate_id) != canonical_hash(
        candidate.model_dump(mode="json")
    ):
        raise EvidenceGateError(
            "EvidenceNormalizationCandidate 未绑定 AgentCall 实际 typed output"
        )
    expected_candidate_scope = (
        candidate.project_id,
        candidate.protocol_version_id,
        candidate.subject_id,
        candidate.review_episode_id,
        candidate.evidence_snapshot_id,
    )
    if (
        agent_call.node != AgentNode.EVIDENCE_NORMALIZER
        or candidate.created_by_agent_call_id != agent_call.agent_call_id
        or expected_candidate_scope
        != (
            agent_call.project_id,
            agent_call.protocol_version_id,
            agent_call.subject_id,
            agent_call.review_episode_id,
            agent_call.evidence_snapshot_id,
        )
    ):
        raise EvidenceGateError(
            "EvidenceNormalizationCandidate 与 Evidence Normalizer AgentCall scope 不一致"
        )
    facts = candidate.clinical_fact_candidates
    evidence_spans = candidate.evidence_span_candidates
    fact_ids = [item.fact_id for item in facts]
    span_ids = [item.evidence_span_id for item in evidence_spans]
    if len(fact_ids) != len(set(fact_ids)) or len(span_ids) != len(set(span_ids)):
        raise EvidenceGateError("Evidence Gate 不接受重复事实或定位 ID")
    span_id_set = set(span_ids)
    fact_id_set = set(fact_ids)
    expected_fact_scope = (
        candidate.project_id,
        candidate.subject_id,
        candidate.review_episode_id,
        candidate.evidence_snapshot_id,
    )
    for fact in facts:
        if (
            fact.project_id,
            fact.subject_id,
            fact.review_episode_id,
            fact.evidence_snapshot_id,
        ) != expected_fact_scope:
            raise EvidenceGateError("ClinicalFact 超出 Evidence Gate scope")
        if not set(fact.evidence_span_ids) <= span_id_set:
            raise EvidenceGateError("ClinicalFact 引用了未验收的 EvidenceSpan")
    for conflict in candidate.conflict_candidates:
        if (
            not set(conflict.fact_ids) <= fact_id_set
            or not set(conflict.resolution_evidence_span_ids) <= span_id_set
        ):
            raise EvidenceGateError("ConflictCandidate 引用了候选范围外事实或 Span")
    candidate_span_refs = [
        *(
            span_id
            for item in candidate.clinical_event_candidates
            for span_id in item.evidence_span_ids
        ),
        *(
            span_id
            for item in candidate.medication_exposure_candidates
            for span_id in item.evidence_span_ids
        ),
        *(
            item.referenced_by_evidence_span_id
            for item in candidate.referenced_document_candidates
        ),
    ]
    if not set(candidate_span_refs) <= span_id_set:
        raise EvidenceGateError("EvidenceNormalizationCandidate 引用了候选范围外 Span")
    if not {
        item.source_document_version_id for item in evidence_spans
    } <= set(agent_call.source_ids):
        raise EvidenceGateError("EvidenceSpan 来源未包含在 AgentCall source_ids")
    payload = evidence_scope_payload(
        candidate=candidate,
        agent_call=agent_call,
        agent_call_gate_result=agent_call_gate_result,
        source_documents=source_documents,
    )
    accepted_refs = [candidate.candidate_id, *fact_ids, *span_ids]
    if not accepted_refs:
        accepted_refs = [f"evidence-snapshot:{candidate.evidence_snapshot_id}"]
    return GateResult(
        gate_result_id=gate_result_id,
        gate_name="evidence-acceptance-gate",
        result=GateOutcome.ACCEPTED,
        input_scope_hash=canonical_hash(payload),
        input_revision_map=input_revision_map,
        input_entity_refs=[
            agent_call.agent_call_id,
            agent_call_gate_result.gate_result_id,
            candidate.candidate_id,
            candidate.evidence_snapshot_id,
            *fact_ids,
            *span_ids,
        ],
        accepted_entity_refs=accepted_refs,
        affected_scope=[candidate.review_episode_id],
        recompute_scope=[candidate.review_episode_id],
        idempotency_key=(
            f"evidence:{candidate.review_episode_id}:"
            f"{candidate.evidence_snapshot_id}:{candidate.candidate_id}"
        ),
        created_at=created_at,
        output_hash=canonical_hash(payload),
    )


def require_accepted_evidence_gate(
    gate_result: GateResult,
    *,
    candidate: EvidenceNormalizationCandidate,
    agent_call: AgentCallContract,
    agent_call_gate_result: GateResult,
    registry: TrustedPublicationRegistry,
) -> None:
    expected = publish_evidence_acceptance(
        candidate=candidate,
        agent_call=agent_call,
        agent_call_gate_result=agent_call_gate_result,
        gate_result_id=gate_result.gate_result_id,
        input_revision_map=gate_result.input_revision_map,
        created_at=gate_result.created_at,
        registry=registry,
    )
    payload = evidence_scope_payload(
        candidate=candidate,
        agent_call=agent_call,
        agent_call_gate_result=agent_call_gate_result,
        source_documents=[
            registry.require("source_document_version", source_id)
            for source_id in agent_call.source_ids
        ],
    )
    accepted_refs = {
        candidate.candidate_id,
        *[item.fact_id for item in candidate.clinical_fact_candidates],
        *[item.evidence_span_id for item in candidate.evidence_span_candidates],
    }
    if (
        gate_result.model_dump(mode="json") != expected.model_dump(mode="json")
        or candidate.evidence_snapshot_id not in gate_result.input_entity_refs
        or not accepted_refs <= set(gate_result.accepted_entity_refs)
        or gate_result.output_hash != canonical_hash(payload)
        or gate_result.input_scope_hash != canonical_hash(payload)
    ):
        raise EvidenceGateError("Assessment 输入未形成 accepted Evidence Gate 闭包")
