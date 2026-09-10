"""Plan a source-frozen successor without rewriting completed page receipts."""

from app.storage.codecs import verify_payload_sha256
from app.storage.page_review_repository import PageReviewRepository
from app.services.evidence_app_errors import EvidenceAppError, AppNotFoundError
from app.workflow.errors import JobNotFoundError
from app.workflow.jobstore import JobStore


class PageRereadNotReady(EvidenceAppError):
    status_code = 409
    code = "PAGE_REREAD_NOT_READY"
    title = "当前任务不能局部重读"
    recovery = "请查看原任务状态；资料或处理方式变化后需重新判读。历史结果仍保留。"


def plan_page_reread(session, predecessor_job_id, payload, *, single_length_recovery=False):
    store = JobStore(session)
    try:
        previous = store.get_job(predecessor_job_id)
    except JobNotFoundError as exc:
        raise AppNotFoundError() from exc
    if previous.state != "completed" or previous.cancel_requested:
        raise PageRereadNotReady("前次资料判读尚未结束，请先查看或恢复原任务")
    old = verify_payload_sha256(previous.payload_json, previous.payload_sha256)
    if old.get("recovery", {}).get("length_override"):
        raise PageRereadNotReady("本次额外补读已执行，不得继续扩大额度或重复补读")
    comparable = {k: v for k, v in old.items() if k != "recovery"}
    # Legacy jobs were serial; adding scheduling does not change reading semantics.
    if "execution_control" not in comparable and "execution_control" in payload:
        comparable["execution_control"] = payload["execution_control"]
    if previous.job_type != "r3_page_review" or comparable != payload:
        raise PageRereadNotReady("前次判读与当前资料、条款或处理配置不一致，不能局部重读")

    def receipt(step_id):
        checkpoint = store.get_last_checkpoint(predecessor_job_id, step_id)
        if checkpoint is None:
            raise PageRereadNotReady("前次判读缺少处理记录，不能局部重读")
        return checkpoint[1]

    coverage = PageReviewRepository(session).get_coverage(receipt("coverage")["coverage_id"])
    authority = payload["authority"]
    expected = {"subject_id": authority["subject_id"],
                "review_episode_id": authority["review_episode_id"],
                "evidence_snapshot_id": authority["evidence_snapshot_v2_id"],
                "evidence_processing_revision_id": authority["complete_processing_revision_id"],
                "clause_pack_sha256": payload["clause_pack"]["clause_pack_sha256"],
                "expected_page_artifact_ids": [page["page_artifact_id"] for page in payload["pages"]]}
    if any(getattr(coverage, field) != value for field, value in expected.items()):
        raise PageRereadNotReady("前次判读的覆盖记录与当前资料不一致")
    if not any(entry.lane_failures for entry in coverage.entries):
        raise PageRereadNotReady("前次判读没有读取失败的页面，无需重读")
    reusable = {}
    for index, entry in enumerate(coverage.entries):
        if entry.page_artifact_id != payload["pages"][index]["page_artifact_id"]:
            raise PageRereadNotReady("前次判读页面顺序与当前资料不一致")
        for lane in ("main-A", "main-B"):
            step = f"read:{index}:{lane}"
            value = receipt(step)
            if "page_review_id" in value:
                # Read through the repository to verify persisted content before reuse.
                record = PageReviewRepository(session).get_review(value["page_review_id"])
                page = payload["pages"][index]
                binding = {**page, "clause_pack_id": payload["clause_pack"]["clause_pack_id"],
                           "clause_pack_sha256": payload["clause_pack"]["clause_pack_sha256"],
                           "contract_version": payload["page_review_contract_version"],
                           "prompt_version": payload["main_prompt_version"]}
                if record.lane.value != lane or any(getattr(record, key) != val for key, val in binding.items()):
                    raise PageRereadNotReady("已完成的主读记录与当前资料不一致，不能复用")
                reusable[step] = value
        if not entry.lane_failures:
            reusable[f"reconcile:{index}"] = {"entry": entry.model_dump(mode="json")}
    recovery = {"predecessor_job_id": predecessor_job_id,
            "predecessor_coverage_id": coverage.coverage_id,
            "reusable_receipts": reusable}
    if single_length_recovery:
        missing = [f"read:{index}:{lane}" for index in range(len(payload["pages"]))
                   for lane in ("main-A", "main-B") if f"read:{index}:{lane}" not in reusable]
        if len(missing) != 1 or receipt(missing[0]).get("lane_failure", {}).get("failure_kind") != "length":
            raise PageRereadNotReady("额外补读仅适用于一个因输出截断而失败的读道")
        recovery["length_override"] = {"step_id": missing[0], "max_tokens": 48000,
                                       "budget_scope": "combined_generation", "retry_length": False}
    return recovery
