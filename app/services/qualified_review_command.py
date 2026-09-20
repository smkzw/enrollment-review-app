"""Prepare per-job authorizations from approved methods, then publish atomically.

Used by the HTTP adapter. Does not create evaluation evidence or user approval.
The application command owns the outer transaction and commit.
"""
from datetime import UTC, datetime
from pydantic import ValidationError

from app.domain.contracts.agents import GateResult
from app.domain.contracts.enums import GateOutcome
from app.domain.contracts.qualified_binding_selection import (
    QUALIFIED_BINDING_CONSUMER_ALGORITHM, QualificationAdoptionAuthorization,
    JudgmentContentAdoption, PropositionEvidenceAdoption, ObservationRelationAdoption, FrequencyEvidenceAdoption,
)
from app.domain.publication import canonical_hash
from app.services.binding_qualification_support import verify_completed_binding_qualification
from app.services.frozen_review_calculation import EVALUATOR_VERSION
from app.services.frozen_review_publication import PUBLICATION_VERSION, publish_frozen_review
from app.services.review_method_evidence import read_review_method_approval, require_evaluated_binding_method
from app.storage.repositories import (
    AppendRepository, DuplicateRecordError, GATE_RESULT_CONFIG, ScopeViolationError,
)
from app.storage.review_context_repository import ReviewContextV2Repository
from app.evidence.artifacts import ArtifactStoreError
from app.workflow.errors import InvalidJobDefinitionError


def _save_authorization_gate(session, repository, gate: GateResult) -> None:
    existing = repository.get_or_none(gate.gate_result_id)
    if existing is None:
        try:
            # Isolate a concurrent duplicate without rolling back the batch.
            with session.begin_nested():
                repository.save(gate)
            return
        except DuplicateRecordError:
            existing = repository.get_or_none(gate.gate_result_id)
            if existing is None:
                raise
    if (existing.model_dump(mode="json", exclude={"created_at"})
            != gate.model_dump(mode="json", exclude={"created_at"})):
        raise ScopeViolationError("已保存的采用依据与本次记录不同，未覆盖历史")


def submit_qualified_review(
    session, artifact_store, *, subject_id: str, review_episode_id: str,
    context_id: str, qualification_job_ids: list[str],
    method_approval_gate_id: str, idempotency_key: str,
    judgment_content_job_ids: dict[str, str] | None = None,
    proposition_evidence_job_ids: dict[str, str] | None = None,
    observation_relation_job_ids: dict[str, str] | None = None,
    frequency_evidence_job_ids: dict[str, str] | None = None,
) -> str:
    """Bind the HTTP subject/node to the frozen context before any writes."""
    context = ReviewContextV2Repository(session).get(context_id)
    if (context.authority.subject_id != subject_id
            or context.authority.review_episode_id != review_episode_id):
        raise ScopeViolationError("所选审核记录不属于当前受试者及审核节点")
    try:
        return publish_review_from_qualified_jobs(
            session, artifact_store, context_id=context_id,
            qualification_job_ids=qualification_job_ids,
            method_approval_gate_id=method_approval_gate_id, idempotency_key=idempotency_key,
            judgment_content_job_ids=judgment_content_job_ids,
            proposition_evidence_job_ids=proposition_evidence_job_ids,
            observation_relation_job_ids=observation_relation_job_ids,
            frequency_evidence_job_ids=frequency_evidence_job_ids,
        )
    except (InvalidJobDefinitionError, ArtifactStoreError, ValidationError) as exc:
        raise ScopeViolationError(
            "本次资料核实或方法采用记录尚不完整，未保存审核结果。请核对原记录后重试。"
        ) from exc


def publish_review_from_qualified_jobs(
    session, artifact_store, *, context_id: str, qualification_job_ids: list[str],
    method_approval_gate_id: str, idempotency_key: str,
    judgment_content_job_ids: dict[str, str] | None = None,
    proposition_evidence_job_ids: dict[str, str] | None = None,
    observation_relation_job_ids: dict[str, str] | None = None,
    frequency_evidence_job_ids: dict[str, str] | None = None,
) -> str:
    """Callers supply job identities, not handmade authorization payloads."""
    if (not 1 <= len(qualification_job_ids) <= 2
            or len(set(qualification_job_ids)) != len(qualification_job_ids)
            or any(not item.strip() for item in qualification_job_ids)):
        raise ScopeViolationError("请提供本次审核对应的完整核对记录")
    _, manifests = read_review_method_approval(session, artifact_store, method_approval_gate_id)
    content_jobs = judgment_content_job_ids or {}
    proposition_jobs = proposition_evidence_job_ids or {}
    observation_jobs = observation_relation_job_ids or {}
    frequency_jobs = frequency_evidence_job_ids or {}
    if (not set(frequency_jobs) <= set(qualification_job_ids)
            or any(not isinstance(value, str) or not value.strip() for value in frequency_jobs.values())
            or len(set(frequency_jobs.values())) != len(frequency_jobs)):
        raise ScopeViolationError("频次核实须逐一归属于本次来源核对任务")
    if (not set(observation_jobs) <= set(qualification_job_ids)
            or any(not isinstance(value, str) or not value.strip() for value in observation_jobs.values())
            or len(set(observation_jobs.values())) != len(observation_jobs)):
        raise ScopeViolationError("复查对应须逐一归属于本次来源核对任务")
    if (not set(proposition_jobs) <= set(qualification_job_ids)
            or any(not isinstance(value, str) or not value.strip() for value in proposition_jobs.values())
            or len(set(proposition_jobs.values())) != len(proposition_jobs)):
        raise ScopeViolationError("原文含义核实须对应本次来源核对任务")
    if (not set(content_jobs) <= set(qualification_job_ids)
            or any(not isinstance(value, str) or not value.strip() for value in content_jobs.values())
            or len(set(content_jobs.values())) != len(content_jobs)):
        raise ScopeViolationError("书面判断任务须逐一归属于本次核对任务")
    review_context = ReviewContextV2Repository(session).get(context_id)
    authorizations, prepared_gates, families = [], [], set()
    for job_id in sorted(qualification_job_ids):
        verified = verify_completed_binding_qualification(
            session, artifact_store, job_id, require_candidate_route_receipts=True,
        )
        preparation = verified["payload"]
        if "review_context_id" in preparation or "review_context_sha256" in preparation:
            if (preparation.get("review_context_id") != context_id
                    or preparation.get("review_context_sha256") != review_context.context_sha256):
                raise ScopeViolationError("本次核对任务属于另一份审核准备记录，未保存到当前审核")
        family = verified["candidate_family"]
        if family in families:
            raise ScopeViolationError("同类核对记录只能指定一份")
        families.add(family)
        matches = [(digest, manifest) for digest, manifest in manifests.items()
                   if manifest.evaluation_kind == "binding_semantic_correspondence"
                   and any(method.candidate_family == family for method in manifest.methods)]
        if len(matches) != 1:
            raise ScopeViolationError("采用确认未覆盖本次核对方法")
        digest, manifest = matches[0]
        method = require_evaluated_binding_method(manifest, verified, QUALIFIED_BINDING_CONSUMER_ALGORITHM)
        if method.evaluator_version != EVALUATOR_VERSION or method.publication_version != PUBLICATION_VERSION:
            raise ScopeViolationError("采用确认未覆盖当前审核计算版本")
        content_adoption = None
        if job_id in content_jobs:
            from app.services.judgment_content_receipts import verify_completed_judgment_content
            from app.services.qualified_judgment_content import require_content_method
            content = verify_completed_judgment_content(session, artifact_store, content_jobs[job_id])
            content_matches = [(key, value) for key, value in manifests.items()
                               if value.evaluation_kind == "written_judgment_content_fidelity"
                               and any(item.candidate_family == family for item in value.methods)]
            if len(content_matches) != 1:
                raise ScopeViolationError("采用确认未覆盖本次书面判断核实")
            content_digest, content_manifest = content_matches[0]
            require_content_method(content_manifest, method, content)
            content_adoption = JudgmentContentAdoption(
                job_id=content_jobs[job_id], summary_logical_sha256=content["summary_sha256"],
                summary_artifact_sha256=content["summary_artifact_sha256"], evaluation_sha256=content_digest,
            )
        proposition_adoption = None
        if job_id in proposition_jobs:
            from app.services.proposition_evidence_receipts import verify_completed_proposition_evidence
            from app.services.qualified_proposition_evidence import require_proposition_method
            proposition = verify_completed_proposition_evidence(session, artifact_store, proposition_jobs[job_id])
            proposition_matches = [(key, value) for key, value in manifests.items()
                                   if value.evaluation_kind == "pair_local_proposition_relation"
                                   and any(item.candidate_family == family for item in value.methods)]
            if len(proposition_matches) != 1:
                raise ScopeViolationError("采用确认未覆盖本次原文含义核实")
            proposition_digest, proposition_manifest = proposition_matches[0]
            require_proposition_method(proposition_manifest, method, proposition)
            proposition_adoption = PropositionEvidenceAdoption(
                job_id=proposition_jobs[job_id], summary_logical_sha256=proposition["summary_sha256"],
                summary_artifact_sha256=proposition["summary_artifact_sha256"],
                evaluation_sha256=proposition_digest,
            )
        observation_adoption = None
        if job_id in observation_jobs:
            from app.services.observation_relation_job import verify_completed_observation_relation
            from app.services.qualified_observation_relation import require_observation_method
            observation = verify_completed_observation_relation(session, artifact_store, observation_jobs[job_id])
            observation_matches = [(key, value) for key, value in manifests.items()
                                   if value.evaluation_kind == "observation_relationship_fidelity"
                                   and any(item.candidate_family == family for item in value.methods)]
            if len(observation_matches) != 1:
                raise ScopeViolationError("采用确认未覆盖本次复查对应核实")
            observation_digest, observation_manifest = observation_matches[0]
            require_observation_method(observation_manifest, method, observation)
            observation_adoption = ObservationRelationAdoption(
                job_id=observation_jobs[job_id], summary_logical_sha256=observation["summary_sha256"],
                summary_artifact_sha256=observation["summary_artifact_sha256"],
                evaluation_sha256=observation_digest,
            )
        frequency_adoption = None
        if job_id in frequency_jobs:
            from app.services.frequency_evidence_job import verify_completed_frequency_evidence
            from app.services.qualified_frequency_evidence import require_frequency_method
            frequency = verify_completed_frequency_evidence(session, artifact_store, frequency_jobs[job_id])
            frequency_matches = [(key, value) for key, value in manifests.items()
                                 if value.evaluation_kind == "frequency_statement_fidelity"
                                 and any(item.candidate_family == family for item in value.methods)]
            if len(frequency_matches) != 1:
                raise ScopeViolationError("采用确认未覆盖本次频次原文核实")
            frequency_digest, frequency_manifest = frequency_matches[0]
            require_frequency_method(frequency_manifest, method, frequency)
            frequency_adoption = FrequencyEvidenceAdoption(
                job_id=frequency_jobs[job_id], summary_logical_sha256=frequency["summary_sha256"],
                summary_artifact_sha256=frequency["summary_artifact_sha256"],
                evaluation_sha256=frequency_digest,
            )
        auth_id = "binding-adoption:" + canonical_hash({
            "approval": method_approval_gate_id, "job": job_id,
            "summary": verified["summary_artifact_sha256"],
            "content": None if content_adoption is None else content_adoption.model_dump(mode="json"),
            "proposition": None if proposition_adoption is None else proposition_adoption.model_dump(mode="json"),
            **({"observation": observation_adoption.model_dump(mode="json")}
               if observation_adoption is not None else {}),
            **({"frequency": frequency_adoption.model_dump(mode="json")}
               if frequency_adoption is not None else {}),
        })
        authorization = QualificationAdoptionAuthorization(
            authorization_id=auth_id, authorizing_service="qualified-review-command/v1",
            qualification_job_id=job_id, candidate_family=family,
            frozen_input_sha256=verified["frozen_input_sha256"],
            comparison_sha256=verified["comparison_sha256"],
            summary_logical_sha256=verified["summary_sha256"],
            summary_artifact_sha256=verified["summary_artifact_sha256"],
            route_identities=verified["routes"], approved_evaluation_evidence_sha256=digest,
            judgment_content=content_adoption,
            proposition_evidence=proposition_adoption,
            observation_relation=observation_adoption,
            frequency_evidence=frequency_adoption,
        )
        gate = GateResult(
            gate_result_id=auth_id, gate_name="binding-adoption-authorization", result=GateOutcome.ACCEPTED,
            input_scope_hash=canonical_hash({"method_approval": method_approval_gate_id,
                "evaluation": digest, "summary": verified["summary_artifact_sha256"]}),
            input_revision_map={}, input_entity_refs=[method_approval_gate_id, digest, job_id,
                *([] if content_adoption is None else [content_adoption.job_id, content_adoption.evaluation_sha256]),
                *([] if proposition_adoption is None else [proposition_adoption.job_id, proposition_adoption.evaluation_sha256]),
                *([] if observation_adoption is None else [observation_adoption.job_id, observation_adoption.evaluation_sha256]),
                *([] if frequency_adoption is None else [frequency_adoption.job_id, frequency_adoption.evaluation_sha256])],
            accepted_entity_refs=[job_id], affected_scope=[job_id], recompute_scope=[job_id],
            idempotency_key=auth_id, created_at=datetime.now(UTC),
            output_hash=canonical_hash(authorization.model_dump(mode="json")),
        )
        authorizations.append(authorization)
        prepared_gates.append(gate)
    with session.begin_nested():
        repository = AppendRepository(session, GATE_RESULT_CONFIG)
        for gate in prepared_gates:
            _save_authorization_gate(session, repository, gate)
        return publish_frozen_review(
            session, artifact_store, context_id=context_id, authorizations=authorizations,
            method_approval_gate_id=method_approval_gate_id, idempotency_key=idempotency_key,
        )
