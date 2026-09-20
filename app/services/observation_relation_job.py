"""Observation relationships use the existing product runner and cancellation."""
from app.domain.contracts.observation_relation import ObservationRelationContext
from app.llm.binding_qualification import DEFAULT_PAIR_BATCH_MAX_CHARACTERS
from app.llm.observation_relation import read_observation_relation
from app.services.content_job_verification import verify_completed_content_job
from app.services.judgment_content_job import JudgmentContentJobExecutor, _enqueue_content_job
from app.services.observation_relation_input import load_observation_relation_input, plan_observation_relation_batches
from app.services.observation_relation_receipts import (
    JOB_TYPE, CONTRACT, PURPOSE, PROMPT_VERSION, rebuild_observation_relation_input,
    reconstruct_observation_relation_lanes, compose_observation_relation_summary,
)
from app.storage.repositories import ScopeViolationError


class ObservationRelationJobExecutor(JudgmentContentJobExecutor):
    job_type, contract, purpose, prompt_version = JOB_TYPE, CONTRACT, PURPOSE, PROMPT_VERSION
    pair_model = ObservationRelationContext
    coverage_fields = ("identity_coverage",)
    step_name = "核实初查、复查及重复记录的原文关系"
    empty_name = "保存尚无原文可核对的复查要求"
    summary_name = "汇集观察关系及尚未核清的记录"
    error_prefix = "OBSERVATION_RELATION"
    load_input = staticmethod(load_observation_relation_input)
    plan_batches = staticmethod(plan_observation_relation_batches)
    rebuild_input = staticmethod(rebuild_observation_relation_input)
    reconstruct = staticmethod(reconstruct_observation_relation_lanes)
    compose_summary = staticmethod(compose_observation_relation_summary)
    read_content = staticmethod(read_observation_relation)


def enqueue_observation_relation(
    session_factory, *, candidate_job_id, context_id, routes, artifact_store,
    pair_batch_max_characters=DEFAULT_PAIR_BATCH_MAX_CHARACTERS, product_runtime=False,
):
    try:
        return _enqueue_content_job(
            session_factory, candidate_job_id=candidate_job_id, context_id=context_id, routes=routes,
            artifact_store=artifact_store, pair_batch_max_characters=pair_batch_max_characters,
            product_runtime=product_runtime, definition=ObservationRelationJobExecutor,
        )
    except ValueError as exc:
        raise ScopeViolationError("复查对应资料暂未核清，原记录已保留，请重新准备本次审核") from exc


def verify_completed_observation_relation(session, artifact_store, job_id):
    return verify_completed_content_job(session, artifact_store, job_id, definition=ObservationRelationJobExecutor)
