"""Frequency reading uses the existing persistent product task executor."""
from app.domain.contracts.frequency_evidence import FrequencyEvidenceContext
from app.llm.binding_qualification import DEFAULT_PAIR_BATCH_MAX_CHARACTERS
from app.llm.frequency_evidence import read_frequency_evidence
from app.services.content_job_verification import verify_completed_content_job
from app.services.judgment_content_job import JudgmentContentJobExecutor, _enqueue_content_job
from app.services.frequency_evidence_input import load_frequency_evidence_input, plan_frequency_evidence_batches
from app.services.frequency_evidence_receipts import (
    JOB_TYPE, CONTRACT, PURPOSE, PROMPT_VERSION, rebuild_frequency_evidence_input,
    reconstruct_frequency_evidence_lanes, compose_frequency_evidence_summary,
)
from app.storage.repositories import ScopeViolationError


class FrequencyEvidenceJobExecutor(JudgmentContentJobExecutor):
    job_type, contract, purpose, prompt_version = JOB_TYPE, CONTRACT, PURPOSE, PROMPT_VERSION
    pair_model = FrequencyEvidenceContext
    coverage_fields = ("identity_coverage",)
    step_name = "核对原文的发生次数、天数与期间"
    empty_name = "保留尚无原文依据的频次要求"
    summary_name = "汇集频次记载与待核实内容"
    error_prefix = "FREQUENCY_EVIDENCE"
    load_input = staticmethod(load_frequency_evidence_input)
    plan_batches = staticmethod(plan_frequency_evidence_batches)
    rebuild_input = staticmethod(rebuild_frequency_evidence_input)
    reconstruct = staticmethod(reconstruct_frequency_evidence_lanes)
    compose_summary = staticmethod(compose_frequency_evidence_summary)
    read_content = staticmethod(read_frequency_evidence)


def enqueue_frequency_evidence(
    session_factory, *, candidate_job_id, context_id, routes, artifact_store,
    pair_batch_max_characters=DEFAULT_PAIR_BATCH_MAX_CHARACTERS, product_runtime=False,
):
    try:
        return _enqueue_content_job(
            session_factory, candidate_job_id=candidate_job_id, context_id=context_id, routes=routes,
            artifact_store=artifact_store, pair_batch_max_characters=pair_batch_max_characters,
            product_runtime=product_runtime, definition=FrequencyEvidenceJobExecutor,
        )
    except ValueError as exc:
        raise ScopeViolationError("频次核对资料暂未核清，原记录已保留，请重新准备本次审核") from exc


def verify_completed_frequency_evidence(session, artifact_store, job_id):
    return verify_completed_content_job(session, artifact_store, job_id, definition=FrequencyEvidenceJobExecutor)
