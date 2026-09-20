"""Replay completed two-lane content work through its declared source definition."""
import json

from app.llm.binding_qualification import DEFAULT_PAIR_BATCH_MAX_CHARACTERS
from app.storage.codecs import verify_payload_sha256
from app.workflow.errors import InvalidJobDefinitionError
from app.workflow.jobstore import JobStore


def verify_completed_content_job(session, artifact_store, job_id, *, definition):
    store = JobStore(session)
    job = store.get_job(job_id)
    payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
    if (job.state != "completed" or job.job_type != definition.job_type
            or payload.get("contract") != definition.contract
            or payload.get("prompt_version") != definition.prompt_version
            or payload.get("purpose") != definition.purpose):
        raise InvalidJobDefinitionError("只能读取当前版本已完成的原文核实任务")
    definition.rebuild_input(session, artifact_store, payload)
    routes = payload.get("routes") or {}
    if set(routes) != {"main-A", "main-B"}:
        raise InvalidJobDefinitionError("原文核实缺少完整的独立读取配置")
    pairs = [definition.pair_model.model_validate(item) for item in payload["pairs"]]
    batches = definition.plan_batches(
        pairs, max_characters=payload.get("pair_batch_max_characters", DEFAULT_PAIR_BATCH_MAX_CHARACTERS),
    )
    if payload.get("batches") != [batch.model_dump(mode="json") for batch in batches]:
        raise InvalidJobDefinitionError("原文核实分批与本次材料不一致")
    checkpoint = store.get_last_checkpoint(job_id, "summary")
    if checkpoint is None:
        raise InvalidJobDefinitionError("原文核实尚未保存完整结果")
    record = checkpoint[1]
    if (record.get("status") != "unverified"
            or any(record.get(key) is not False for key in (
                "accepted", "authorized_clinical_adoption", "clinically_qualified"))
            or any(record.get(key) != payload[key] for key in (
                "frozen_input_sha256", "input_sha256", "comparison_sha256",
                "candidate_job_id", "review_context_id"))):
        raise InvalidJobDefinitionError("原文核实保存范围或状态不一致")
    lane_reads, lane_receipts = definition.reconstruct(
        session=session, artifact_store=artifact_store, job_id=job_id, payload=payload,
        pairs=pairs, batches=batches, routes=routes,
    )
    summary = definition.compose_summary(
        payload=payload, pairs=pairs, batches=batches,
        lane_reads=lane_reads, lane_receipts=lane_receipts,
    )
    stored = json.loads(artifact_store.read_by_sha("raw_response", record["summary_sha256"]))
    if stored != summary:
        raise InvalidJobDefinitionError("原文核实结果与原始回答重建内容不一致")
    return {f"{definition.job_type}_job_id": job_id, "job_type": definition.job_type,
            "contract": definition.contract, "prompt_version": definition.prompt_version,
            "payload": payload, "routes": routes, "pairs": pairs, "batches": batches,
            "summary": summary, "summary_sha256": summary["summary_sha256"],
            "summary_artifact_sha256": record["summary_sha256"]}
