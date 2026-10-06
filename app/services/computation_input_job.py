"""Calculation-source checks share the existing runner, cancellation and receipts."""
import json

from app.domain.contracts.binding_qualification import BindingQualificationBatch
from app.domain.contracts.computation_input import ComputationInputContext
from app.domain.publication import canonical_hash
from app.llm.binding_qualification import DEFAULT_PAIR_BATCH_MAX_CHARACTERS
from app.llm.computation_input import read_computation_input, build_computation_input_messages
from app.services.computation_input_receipts import (
    JOB_TYPE, CONTRACT, PURPOSE, PROMPT_VERSION, rebuild_computation_input_sources,
    reconstruct_computation_input_lanes, compose_computation_input_summary,
)
from app.services.computation_input_sources import load_computation_input_sources, plan_computation_input_batches
from app.services.content_job_verification import verify_completed_content_job
from app.services.judgment_content_job import JudgmentContentJobExecutor, _enqueue_content_job


class ComputationInputJobExecutor(JudgmentContentJobExecutor):
    job_type, contract, purpose, prompt_version = JOB_TYPE, CONTRACT, PURPOSE, PROMPT_VERSION
    pair_model = ComputationInputContext
    coverage_fields = ("identity_coverage",)
    step_name = "核对计算输入的采集标识与日期角色"
    empty_name = "保存暂无来源可核对的计算要求"
    summary_name = "保存计算输入来源及未核清范围"
    error_prefix = "COMPUTATION_INPUT"
    load_input = staticmethod(load_computation_input_sources)
    plan_batches = staticmethod(plan_computation_input_batches)
    rebuild_input = staticmethod(rebuild_computation_input_sources)
    reconstruct = staticmethod(reconstruct_computation_input_lanes)
    compose_summary = staticmethod(compose_computation_input_summary)
    read_content = staticmethod(read_computation_input)

    @staticmethod
    def request_identity_fields(pairs, batches):
        persisted = [ComputationInputContext.model_validate(json.loads(json.dumps(
            item.model_dump(mode="json"), ensure_ascii=False, sort_keys=True,
        ))) for item in pairs]
        hashes = {}
        for index, raw in enumerate(batches):
            batch = BindingQualificationBatch.model_validate(
                raw if isinstance(raw, dict) else raw.model_dump(mode="json"))
            selected = [item for item in persisted if item.pair_id in set(batch.pair_ids)]
            digest = canonical_hash(build_computation_input_messages(selected, batch))
            for lane in ("main-A", "main-B"):
                hashes[f"content:{index}:{lane}"] = digest
        return {"request_messages_sha256s": hashes}


def enqueue_computation_input(session_factory, *, candidate_job_id, context_id, routes, artifact_store,
                              pair_batch_max_characters=DEFAULT_PAIR_BATCH_MAX_CHARACTERS,
                              product_runtime=False):
    return _enqueue_content_job(session_factory, candidate_job_id=candidate_job_id, context_id=context_id,
        routes=routes, artifact_store=artifact_store, pair_batch_max_characters=pair_batch_max_characters,
        product_runtime=product_runtime, definition=ComputationInputJobExecutor)


def verify_completed_computation_input(session, artifact_store, job_id):
    return verify_completed_content_job(session, artifact_store, job_id, definition=ComputationInputJobExecutor)
