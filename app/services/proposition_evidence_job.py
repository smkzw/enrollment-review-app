"""Persist proposition checks through the existing dual-content job machinery."""
from app.llm.binding_qualification import DEFAULT_PAIR_BATCH_MAX_CHARACTERS
from app.llm.proposition_evidence import read_proposition_evidence
from app.services.judgment_content_job import JudgmentContentJobExecutor, _enqueue_content_job
from app.services.proposition_evidence_input import (
    load_proposition_evidence_input, plan_proposition_evidence_batches,
)
from app.services.proposition_evidence_receipts import (
    JOB_TYPE, CONTRACT, PURPOSE, PROMPT_VERSION,
    rebuild_proposition_evidence_input, reconstruct_proposition_evidence_lanes,
    compose_proposition_evidence_summary,
)


class PropositionEvidenceJobExecutor(JudgmentContentJobExecutor):
    job_type = JOB_TYPE
    contract = CONTRACT
    purpose = PURPOSE
    prompt_version = PROMPT_VERSION
    coverage_fields = ("skipped_pairs", "identity_coverage")
    step_name = "结合原文核实本项要求涉及的事实"
    empty_name = "保存本次尚无对应原文的要求"
    summary_name = "汇集两次原文核实及未确定事项"
    error_prefix = "PROPOSITION_EVIDENCE"
    load_input = staticmethod(load_proposition_evidence_input)
    plan_batches = staticmethod(plan_proposition_evidence_batches)
    rebuild_input = staticmethod(rebuild_proposition_evidence_input)
    reconstruct = staticmethod(reconstruct_proposition_evidence_lanes)
    compose_summary = staticmethod(compose_proposition_evidence_summary)
    read_content = staticmethod(read_proposition_evidence)


def enqueue_proposition_evidence(
    session_factory, *, candidate_job_id, context_id, routes, artifact_store,
    pair_batch_max_characters=DEFAULT_PAIR_BATCH_MAX_CHARACTERS, product_runtime=False,
):
    return _enqueue_content_job(
        session_factory, candidate_job_id=candidate_job_id, context_id=context_id,
        routes=routes, artifact_store=artifact_store,
        pair_batch_max_characters=pair_batch_max_characters,
        product_runtime=product_runtime, definition=PropositionEvidenceJobExecutor,
    )
