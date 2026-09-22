"""Product task intake; no model choices, facts or adoption supplied by clients."""
from typing import Literal

from app.services.review_runtime_ownership import OWNER
from app.services.review_context_assembly import (
    current_review_clinical_material_sha256,
    frozen_review_clinical_material_sha256,
)
from app.storage.codecs import verify_payload_sha256
from app.storage.fact_authority import FactAuthorityValidator
from app.storage.repositories import ScopeViolationError
from app.storage.review_context_repository import ReviewContextV2Repository
from app.workflow.jobstore import JobStore

ReviewTaskKind = Literal["predicate_candidates", "control_candidates", "qualification", "judgment_content", "proposition_evidence", "observation_relation", "frequency_evidence"]


def require_prepared_review_intent(session_factory, *, subject_id, review_episode_id,
                                   context_id, kind, candidate_job_id=None):
    if kind not in {"predicate_candidates", "control_candidates", "qualification", "judgment_content", "proposition_evidence", "observation_relation", "frequency_evidence"}:
        raise ScopeViolationError("所选审核步骤不存在")
    follows_candidate = kind in {"qualification", "judgment_content", "proposition_evidence", "observation_relation", "frequency_evidence"}
    if follows_candidate != (candidate_job_id is not None):
        raise ScopeViolationError("请使用本次审核对应的前一步记录")
    with session_factory() as session:
        context = ReviewContextV2Repository(session).get(context_id)
        if (context.authority.subject_id != subject_id
                or context.authority.review_episode_id != review_episode_id):
            raise ScopeViolationError("审核准备记录不属于当前受试者及节点")
        FactAuthorityValidator(session).validate(context.authority)
        if (
            current_review_clinical_material_sha256(session, context.authority)
            != frozen_review_clinical_material_sha256(context)
        ):
            raise ScopeViolationError("当前病史已经更新，请重新准备本次审核")
        if candidate_job_id is not None:
            parent = JobStore(session).get_job(candidate_job_id)
            if parent.state != "completed":
                raise ScopeViolationError("前一步核对尚未完成，请完成后再继续")
            payload = verify_payload_sha256(parent.payload_json, parent.payload_sha256)
            allowed = {"predicate_binding_candidates"}
            if kind in {"qualification", "judgment_content", "proposition_evidence", "observation_relation", "frequency_evidence"}:
                allowed.add("control_binding_candidates")
            if (parent.job_type not in allowed or payload.get("execution_owner") != OWNER
                    or payload.get("review_context_id") != context_id
                    or payload.get("review_context_sha256") != context.context_sha256):
                raise ScopeViolationError("前一步核对不属于本次正式审核")
        return context


def enqueue_prepared_review_task(session_factory, artifact_store, routes, *, subject_id,
                                 review_episode_id, context_id, kind: ReviewTaskKind,
                                 candidate_job_id=None):
    require_prepared_review_intent(
        session_factory, subject_id=subject_id, review_episode_id=review_episode_id,
        context_id=context_id, kind=kind, candidate_job_id=candidate_job_id,
    )
    if kind == "predicate_candidates":
        from app.services.predicate_binding_job import enqueue_predicate_candidates
        return enqueue_predicate_candidates(
            session_factory, review_episode_id=review_episode_id, component_ids=None,
            routes=routes, review_context_id=context_id, product_runtime=True,
        )
    if kind == "control_candidates":
        from app.services.control_binding_job import enqueue_control_candidates
        return enqueue_control_candidates(
            session_factory, review_episode_id=review_episode_id, routes=routes,
            review_context_id=context_id, product_runtime=True,
        )
    if kind == "qualification":
        from app.services.binding_qualification import enqueue_binding_qualification
        return enqueue_binding_qualification(
            session_factory, candidate_job_id=candidate_job_id, routes=routes,
            artifact_store=artifact_store, product_runtime=True,
        )
    if kind == "frequency_evidence":
        from app.services.frequency_evidence_job import enqueue_frequency_evidence
        return enqueue_frequency_evidence(
            session_factory, candidate_job_id=candidate_job_id, context_id=context_id,
            routes=routes, artifact_store=artifact_store, product_runtime=True,
        )
    if kind == "observation_relation":
        from app.services.observation_relation_job import enqueue_observation_relation
        return enqueue_observation_relation(
            session_factory, candidate_job_id=candidate_job_id, context_id=context_id,
            routes=routes, artifact_store=artifact_store, product_runtime=True,
        )
    if kind == "proposition_evidence":
        from app.services.proposition_evidence_job import enqueue_proposition_evidence
        return enqueue_proposition_evidence(
            session_factory, candidate_job_id=candidate_job_id, context_id=context_id,
            routes=routes, artifact_store=artifact_store, product_runtime=True,
        )
    from app.services.judgment_content_job import enqueue_judgment_content
    return enqueue_judgment_content(
        session_factory, candidate_job_id=candidate_job_id, context_id=context_id,
        routes=routes, artifact_store=artifact_store, product_runtime=True,
    )
