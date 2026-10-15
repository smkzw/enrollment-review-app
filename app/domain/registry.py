from __future__ import annotations

from collections.abc import Iterable
from types import MappingProxyType
from typing import Any

from app.domain.contracts.agents import (
    AgentCallContract,
    GateResult,
    ModelConfigContract,
    PromptVersion,
)
from app.domain.contracts.context import ReviewContextSnapshot
from app.domain.contracts.evidence import (
    EvidenceExpectation,
    EvidenceSnapshot,
    SourceDocumentVersion,
)
from app.domain.contracts.normalization import EvidenceNormalizationCandidate
from app.domain.contracts.review import (
    ActionRequest,
    AssessmentCandidate,
    FinalAssessment,
    Project,
    ProtocolDocumentVersion,
    ReviewEpisode,
    ReviewRun,
    Subject,
)
from app.domain.contracts.rules import (
    ProtocolAuthorityConfirmation,
    ProtocolAuthorityRecord,
    ProtocolIntegrityManifest,
    ProtocolSourceRecord,
    RuleSet,
    ServiceCommandEvent,
    WorkflowStage,
)
from app.domain.publication import canonical_hash


class RegistryLookupError(ValueError):
    pass


_SERVICE_ISSUER = object()


class TrustedPublicationRegistry:
    """Read-only view of entities already persisted by the application service.

    The domain layer can resolve and compare registered inputs, but cannot add or
    replace them. Phase 2 will back this interface with SQLite repositories.
    """

    def __init__(
        self,
        issuer,
        *,
        agent_calls: Iterable[AgentCallContract] = (),
        gate_results: Iterable[GateResult] = (),
        evidence_candidates: Iterable[EvidenceNormalizationCandidate] = (),
        assessment_candidates: Iterable[AssessmentCandidate] = (),
        final_assessments: Iterable[FinalAssessment] = (),
        action_requests: Iterable[ActionRequest] = (),
        rule_sets: Iterable[RuleSet] = (),
        review_contexts: Iterable[ReviewContextSnapshot] = (),
        projects: Iterable[Project] = (),
        protocol_document_versions: Iterable[ProtocolDocumentVersion] = (),
        subjects: Iterable[Subject] = (),
        review_episodes: Iterable[ReviewEpisode] = (),
        evidence_snapshots: Iterable[EvidenceSnapshot] = (),
        review_runs: Iterable[ReviewRun] = (),
        source_document_versions: Iterable[SourceDocumentVersion] = (),
        evidence_expectations: Iterable[EvidenceExpectation] = (),
        prompt_versions: Iterable[PromptVersion] = (),
        model_configs: Iterable[ModelConfigContract] = (),
        protocol_authority_records: Iterable[ProtocolAuthorityRecord] = (),
        protocol_authority_confirmations: Iterable[
            ProtocolAuthorityConfirmation
        ] = (),
        service_command_events: Iterable[ServiceCommandEvent] = (),
        protocol_source_records: Iterable[ProtocolSourceRecord] = (),
        protocol_integrity_manifests: Iterable[ProtocolIntegrityManifest] = (),
        workflow_stages: Iterable[WorkflowStage] = (),
        protocol_integrity_bindings: dict[str, str] | None = None,
    ) -> None:
        if issuer is not _SERVICE_ISSUER:
            raise RegistryLookupError("发布注册表只能由应用服务创建")
        self._entities = MappingProxyType(
            {
                "agent_call": self._index(agent_calls, "agent_call_id"),
                "gate_result": self._index(gate_results, "gate_result_id"),
                "evidence_candidate": self._index(
                    evidence_candidates, "candidate_id"
                ),
                "assessment_candidate": self._index(
                    assessment_candidates, "assessment_candidate_id"
                ),
                "final_assessment": self._index(
                    final_assessments, "assessment_id"
                ),
                "action_request": self._index(action_requests, "action_id"),
                "rule_set": self._index(rule_sets, "rule_set_id"),
                "review_context": self._index(review_contexts, "context_id"),
                "project": self._index(projects, "project_id"),
                "protocol_document_version": self._index(
                    protocol_document_versions, "protocol_version_id"
                ),
                "subject": self._index(subjects, "subject_id"),
                "review_episode": self._index(
                    review_episodes, "review_episode_id"
                ),
                "evidence_snapshot": self._index(
                    evidence_snapshots, "evidence_snapshot_id"
                ),
                "review_run": self._index(review_runs, "review_run_id"),
                "source_document_version": self._index(
                    source_document_versions, "source_document_version_id"
                ),
                "evidence_expectation": self._index(
                    evidence_expectations, "expectation_id"
                ),
                "prompt_version": self._index(
                    prompt_versions, "prompt_version_id"
                ),
                "model_config": self._index(model_configs, "model_config_id"),
                "protocol_authority_record": self._index(
                    protocol_authority_records, "authority_record_id"
                ),
                "protocol_authority_confirmation": self._index(
                    protocol_authority_confirmations, "confirmation_id"
                ),
                "service_command_event": self._index(
                    service_command_events, "command_id"
                ),
                "protocol_source_record": self._index(
                    protocol_source_records, "source_ref"
                ),
                "protocol_integrity_manifest": self._index(
                    protocol_integrity_manifests, "manifest_id"
                ),
                "workflow_stage": self._index(
                    workflow_stages, "workflow_stage_id"
                ),
            }
        )
        self._protocol_integrity_bindings = MappingProxyType(
            dict(protocol_integrity_bindings or {})
        )

    @staticmethod
    def _index(values: Iterable[Any], id_field: str):
        result = {}
        for value in values:
            entity_id = getattr(value, id_field)
            if entity_id in result:
                raise RegistryLookupError(f"已登记实体 ID 重复: {entity_id}")
            result[entity_id] = value.model_copy(deep=True)
        return MappingProxyType(result)

    def require(self, entity_type: str, entity_id: str, expected=None):
        try:
            entity = self._entities[entity_type][entity_id]
        except KeyError as exc:
            raise RegistryLookupError(
                f"未找到服务端已登记的 {entity_type}: {entity_id}"
            ) from exc
        if expected is not None and canonical_hash(
            entity.model_dump(mode="json")
        ) != canonical_hash(expected.model_dump(mode="json")):
            raise RegistryLookupError(
                f"{entity_type} 与服务端已登记版本不一致: {entity_id}"
            )
        return entity.model_copy(deep=True)

    def all(self, entity_type: str):
        """Return immutable-snapshot copies for deterministic completeness checks."""

        try:
            values = self._entities[entity_type].values()
        except KeyError as exc:
            raise RegistryLookupError(f"未知发布实体类型: {entity_type}") from exc
        return tuple(value.model_copy(deep=True) for value in values)

    def require_protocol_rule_binding(
        self, gate_result_id: str, rule_set: RuleSet
    ) -> None:
        expected = canonical_hash(rule_set.model_dump(mode="json"))
        if self._protocol_integrity_bindings.get(gate_result_id) != expected:
            raise RegistryLookupError("方案完整性验收结果未绑定当前完整规则集")


def _issue_trusted_registry(**kwargs) -> TrustedPublicationRegistry:
    """Application-service bootstrap; intentionally not exported by domain API."""

    return TrustedPublicationRegistry(_SERVICE_ISSUER, **kwargs)
