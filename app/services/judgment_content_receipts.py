"""Receipt proof and batch helpers for written-judgment content jobs.

Reconstructs dual-lane results from stored request/response material. Content
support never authorizes clinical adoption or eligibility decisions.
"""
from __future__ import annotations

import json
from typing import Any

from app.domain.contracts.binding_qualification import (
    BindingQualificationBatch,
    BindingQualificationPairContext,
    binding_qualification_batch_hash,
)
from app.domain.contracts.judgment_content import JUDGMENT_CONTENT_VERSION
from app.domain.publication import canonical_hash
from app.llm.binding_qualification import DEFAULT_PAIR_BATCH_MAX_CHARACTERS
from app.llm.judgment_content import (
    JudgmentContentRead,
    build_judgment_content_messages,
    validate_judgment_content_payload,
)
from app.llm.page_review_transport_options import page_completion_options
from app.services.judgment_content_comparison import compare_judgment_content
from app.services.judgment_content_input import load_judgment_content_input
from app.services.predicate_binding_job import LANES
from app.storage.codecs import verify_payload_sha256
from app.workflow.errors import InvalidJobDefinitionError
from app.workflow.jobstore import JobStore

JOB_TYPE = "judgment_content"
CONTRACT = "judgment-content-job/v1"
PURPOSE = "isolated_written_judgment_content_check"
PROMPT_VERSION = JUDGMENT_CONTENT_VERSION
SUMMARY_VERSION = "judgment-content-summary/v1"


def _verify_call_sequence(artifact_store, receipt_ids, *, job_id, step_id, attempt, route, messages):
    """Replay the shared reader's bounded 429/length policy, not just its last response."""
    budget = route.get("max_tokens")
    if (type(budget) is not int or not 65536 <= budget <= 131072
            or type(attempt) is not int or attempt < 1
            or not isinstance(receipt_ids, list) or not receipt_ids
            or any(not isinstance(value, str) for value in receipt_ids)
            or len(set(receipt_ids)) != len(receipt_ids)):
        raise InvalidJobDefinitionError("判断内容调用记录或额度无效")
    waits = 0
    length_seen = False
    for index, receipt_id in enumerate(receipt_ids):
        receipt = json.loads(artifact_store.read_by_sha("raw_response", receipt_id))
        if (receipt.get("job_id") != job_id or receipt.get("step_id") != step_id
                or receipt.get("attempt") != attempt or receipt.get("route_identity") != route):
            raise InvalidJobDefinitionError("判断内容回执不属于当前尝试或服务")
        request = json.loads(artifact_store.read_by_sha("raw_response", receipt["request_sha256"]))
        expected_request = {
            "model": route["model"], "reasoning_effort": route["reasoning_effort"],
            "messages": messages, "max_tokens": budget,
            **page_completion_options(route["provider"], messages, budget),
        }
        if request != expected_request:
            raise InvalidJobDefinitionError("判断内容请求与本次提示、参数或重试额度不一致")
        if "response_sha256" not in receipt:
            if receipt.get("status_code") != 429 or waits >= 12 or index == len(receipt_ids) - 1:
                raise InvalidJobDefinitionError("判断内容失败调用不能被后续回答掩盖")
            waits += 1
            continue
        if receipt.get("error_type") or receipt.get("status_code"):
            raise InvalidJobDefinitionError("判断内容回执同时声明回答与错误")
        response = json.loads(artifact_store.read_by_sha("raw_response", receipt["response_sha256"]))
        if response.get("finish_reason") == "length" and not length_seen and budget < 131072:
            length_seen = True
            budget = min(131072, budget * 2)
            continue
        if response.get("finish_reason") != "stop" or index != len(receipt_ids) - 1:
            raise InvalidJobDefinitionError("判断内容回答顺序或结束原因不符合本次读取约定")
        return response
    raise InvalidJobDefinitionError("判断内容调用没有完整最终回答")


def plan_judgment_content_batches(
    pairs: list[BindingQualificationPairContext],
    *,
    max_characters: int = DEFAULT_PAIR_BATCH_MAX_CHARACTERS,
    message_builder=build_judgment_content_messages,
) -> list[BindingQualificationBatch]:
    """Pack pairs by actual judgment prompt size; never truncate excerpts."""
    if max_characters < 1:
        raise ValueError("判断内容分批长度必须为正数")
    if not pairs:
        return []
    frozen = {item.frozen_input_sha256 for item in pairs}
    jobs = {item.candidate_job_id for item in pairs}
    if len(frozen) != 1 or len(jobs) != 1:
        raise ValueError("同一次判断内容分批只能覆盖同一冻结输入与候选任务")
    ordered = sorted(
        pairs,
        key=lambda item: (item.identity_sha256, item.fact_id, item.locator_id, item.pair_id),
    )
    batches: list[BindingQualificationBatch] = []
    pending: list[BindingQualificationPairContext] = []

    def materialize(items: list[BindingQualificationPairContext]) -> BindingQualificationBatch:
        payload = {
            "frozen_input_sha256": items[0].frozen_input_sha256,
            "candidate_job_id": items[0].candidate_job_id,
            "pair_ids": sorted(item.pair_id for item in items),
            "identity_sha256s": sorted({item.identity_sha256 for item in items}),
            "fact_ids": sorted({item.fact_id for item in items}),
            "locator_ids": sorted({item.locator_id for item in items}),
        }
        return BindingQualificationBatch.model_validate({
            **payload,
            "batch_sha256": binding_qualification_batch_hash(payload),
        })

    def size(items: list[BindingQualificationPairContext]) -> int:
        return len(json.dumps(
            message_builder(items, materialize(items)),
            ensure_ascii=False,
            separators=(",", ":"),
        ))

    for pair in ordered:
        proposed = [*pending, pair]
        if pending and size(proposed) > max_characters:
            batches.append(materialize(pending))
            pending = []
            proposed = [pair]
        if size(proposed) > max_characters:
            raise ValueError("单个配对及其完整原文超过判断内容分批长度，不能截断")
        pending = proposed
    if pending:
        batches.append(materialize(pending))
    return batches


def expected_judgment_content_input(payload: dict) -> dict[str, Any]:
    return {
        "version": payload["input_version"],
        "candidate_job_id": payload["candidate_job_id"],
        "review_context_id": payload["review_context_id"],
        "review_context_sha256": payload["review_context_sha256"],
        "frozen_input_sha256": payload["frozen_input_sha256"],
        "comparison_sha256": payload["comparison_sha256"],
        "candidate_receipt_sha256s": payload["candidate_receipt_sha256s"],
        "pairs": payload["pairs"],
        "excerpt_coverage": payload["excerpt_coverage"],
        "input_sha256": payload["input_sha256"],
    }


def rebuild_judgment_content_input(session, artifact_store, payload: dict) -> dict[str, Any]:
    rebuilt = load_judgment_content_input(
        session,
        artifact_store,
        candidate_job_id=payload["candidate_job_id"],
        context_id=payload["review_context_id"],
    )
    expected = expected_judgment_content_input(payload)
    actual = {key: rebuilt[key] for key in expected}
    if actual != expected:
        raise InvalidJobDefinitionError("判断内容输入与当前候选回执或审核准备不一致")
    return rebuilt


def compose_judgment_content_summary(
    *,
    payload: dict,
    pairs: list[BindingQualificationPairContext],
    batches: list[BindingQualificationBatch],
    lane_reads: dict[str, dict[str, JudgmentContentRead | None]],
    lane_receipts: dict[str, dict[str, list[str]]],
) -> dict[str, Any]:
    comparisons = []
    for batch in batches:
        reads = lane_reads.get(batch.batch_sha256) or {}
        left = reads.get("main-A")
        right = reads.get("main-B")
        if left is None or right is None:
            raise InvalidJobDefinitionError("判断内容汇总缺少完整双路读取结果")
        batch_pairs = [item for item in pairs if item.pair_id in set(batch.pair_ids)]
        comparison = compare_judgment_content(batch_pairs, batch, (left, right))
        comparisons.append({
            **comparison,
            "lane_receipt_sha256s": {
                lane.value: list((lane_receipts.get(batch.batch_sha256) or {}).get(lane.value) or [])
                for lane in LANES
            },
        })
    coverage = list(payload.get("excerpt_coverage") or [])
    ready_pairs = {pair.pair_id for pair in pairs}
    unresolved_coverage = [
        item for item in coverage
        if not item.get("content_check_ready") or not set(item.get("pair_ids") or []) & ready_pairs
    ]
    material = {
        "version": SUMMARY_VERSION,
        "prompt_version": PROMPT_VERSION,
        "purpose": PURPOSE,
        "candidate_job_id": payload["candidate_job_id"],
        "review_context_id": payload["review_context_id"],
        "review_context_sha256": payload["review_context_sha256"],
        "frozen_input_sha256": payload["frozen_input_sha256"],
        "comparison_sha256": payload["comparison_sha256"],
        "input_sha256": payload["input_sha256"],
        "candidate_receipt_sha256s": payload["candidate_receipt_sha256s"],
        "batches": [item.model_dump(mode="json") for item in batches],
        "selected_pair_ids": sorted(ready_pairs),
        "excerpt_coverage": coverage,
        "unresolved_excerpt_coverage": unresolved_coverage,
        "comparisons": comparisons,
        "empty_selected_pairs": not pairs,
        "empty_selection_notes": (
            ["empty_selected_pairs_retains_excerpt_coverage_without_missing_judgment_claim"]
            if not pairs else []
        ),
        "accepted": False,
        "authorized_clinical_adoption": False,
        "clinically_qualified": False,
        "content_support_is_not_clinical_adoption": True,
    }
    material["summary_sha256"] = canonical_hash({
        key: value for key, value in material.items() if key != "summary_sha256"
    })
    return material


def _reconstruct_judgment_content_lane_state(
    *,
    session,
    artifact_store,
    job_id: str,
    payload: dict,
    pairs: list[BindingQualificationPairContext],
    batches: list[BindingQualificationBatch],
    routes: dict[str, dict],
    message_builder=build_judgment_content_messages,
    payload_validator=validate_judgment_content_payload,
    read_type=JudgmentContentRead,
) -> tuple[
    dict[str, dict[str, JudgmentContentRead | None]],
    dict[str, dict[str, list[str]]],
]:
    store = JobStore(session)
    lane_reads = {batch.batch_sha256: {lane.value: None for lane in LANES} for batch in batches}
    lane_receipts = {batch.batch_sha256: {lane.value: [] for lane in LANES} for batch in batches}
    if not pairs:
        return lane_reads, lane_receipts
    for index, batch in enumerate(batches):
        batch_pairs = [item for item in pairs if item.pair_id in set(batch.pair_ids)]
        messages = message_builder(batch_pairs, batch)
        expected_messages = canonical_hash(messages)
        for lane in LANES:
            step_id = f"content:{index}:{lane.value}"
            checkpoint = store.get_last_checkpoint(job_id, step_id)
            if checkpoint is None:
                raise InvalidJobDefinitionError("判断内容任务缺少完整双路检查点")
            record = checkpoint[1]
            if (
                record.get("frozen_input_sha256") != payload["frozen_input_sha256"]
                or record.get("input_sha256") != payload["input_sha256"]
                or record.get("batch_sha256") != batch.batch_sha256
                or record.get("lane") != lane.value
                or record.get("accepted") is not False
                or record.get("authorized_clinical_adoption") is not False
                or record.get("clinically_qualified") is not False
                or record.get("comparison_sha256") != payload["comparison_sha256"]
                or record.get("status") != "unverified"
            ):
                raise InvalidJobDefinitionError("判断内容读取检查点范围或状态无效")
            artifact = json.loads(
                artifact_store.read_by_sha("raw_response", record["content_sha256"]),
            )
            if artifact.get("accepted") is not False:
                raise InvalidJobDefinitionError("判断内容工件不得声明已采信")
            if (
                artifact.get("input_sha256") != payload["input_sha256"]
                or artifact.get("frozen_input_sha256") != payload["frozen_input_sha256"]
                or artifact.get("candidate_job_id") != payload["candidate_job_id"]
                or artifact.get("review_context_id") != payload["review_context_id"]
                or artifact.get("comparison_sha256") != payload["comparison_sha256"]
                or artifact.get("authorized_clinical_adoption") is not False
                or artifact.get("clinically_qualified") is not False
            ):
                raise InvalidJobDefinitionError("判断内容工件范围或采信状态无效")
            validated = payload_validator(
                batch_pairs,
                json.dumps(artifact["payload"], ensure_ascii=False),
            )
            receipt_ids = record.get("receipt_sha256s") or []
            if not receipt_ids:
                raise InvalidJobDefinitionError("判断内容任务缺少原始调用回执")
            route = routes[lane.value]
            response = _verify_call_sequence(
                artifact_store, receipt_ids, job_id=job_id, step_id=step_id,
                attempt=record.get("attempt"), route=route, messages=messages,
            )
            if (
                artifact.get("messages_sha256") != expected_messages
                or artifact.get("batch_sha256") != batch.batch_sha256
            ):
                raise InvalidJobDefinitionError("判断内容请求/回答与冻结提示或路由不一致")
            original = payload_validator(batch_pairs, response["text"])
            if original != validated:
                raise InvalidJobDefinitionError("判断内容工件与最终原始回答不一致")
            lane_reads[batch.batch_sha256][lane.value] = read_type(
                frozen_input_sha256=batch.frozen_input_sha256,
                batch_sha256=batch.batch_sha256,
                messages_sha256=expected_messages,
                requested_provider=route["provider"],
                requested_model=route["model"],
                requested_effort=route["reasoning_effort"],
                lane=lane.value,
                payload=validated,
                completions=(),
                budgets=(),
            )
            lane_receipts[batch.batch_sha256][lane.value] = list(receipt_ids)
    return lane_reads, lane_receipts


def verify_completed_judgment_content(
    session,
    artifact_store,
    judgment_content_job_id: str,
) -> dict[str, Any]:
    """Rebuild a completed content job from frozen input plus two-lane receipts."""
    store = JobStore(session)
    job = store.get_job(judgment_content_job_id)
    if job.state != "completed":
        raise InvalidJobDefinitionError("只能消费已完成的判断内容核实任务")
    payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
    if (
        job.job_type != JOB_TYPE
        or payload.get("contract") != CONTRACT
        or payload.get("prompt_version") != PROMPT_VERSION
        or payload.get("purpose") != PURPOSE
    ):
        raise InvalidJobDefinitionError("判断内容任务合同或提示版本不是当前官方版本")
    routes = payload.get("routes") or {}
    if set(routes) != {lane.value for lane in LANES}:
        raise InvalidJobDefinitionError("判断内容任务缺少完整双路路由身份")
    rebuild_judgment_content_input(session, artifact_store, payload)
    pairs = [
        BindingQualificationPairContext.model_validate(item)
        for item in payload.get("pairs") or []
    ]
    expected_batches = [
        batch.model_dump(mode="json")
        for batch in plan_judgment_content_batches(
            pairs,
            max_characters=payload.get(
                "pair_batch_max_characters", DEFAULT_PAIR_BATCH_MAX_CHARACTERS,
            ),
        )
    ]
    if payload.get("batches") != expected_batches:
        raise InvalidJobDefinitionError("判断内容分批与配对材料不一致")
    batches = [BindingQualificationBatch.model_validate(item) for item in expected_batches]
    summary_checkpoint = store.get_last_checkpoint(judgment_content_job_id, "summary")
    if summary_checkpoint is None or summary_checkpoint[1].get("accepted") is not False:
        raise InvalidJobDefinitionError("判断内容任务缺少未采信的汇总检查点")
    summary_record = summary_checkpoint[1]
    if (
        summary_record.get("frozen_input_sha256") != payload["frozen_input_sha256"]
        or summary_record.get("input_sha256") != payload["input_sha256"]
        or summary_record.get("candidate_job_id") != payload["candidate_job_id"]
        or summary_record.get("review_context_id") != payload["review_context_id"]
        or summary_record.get("authorized_clinical_adoption") is not False
        or summary_record.get("clinically_qualified") is not False
        or summary_record.get("status") != "unverified"
    ):
        raise InvalidJobDefinitionError("判断内容汇总检查点范围或状态无效")
    stored_summary = json.loads(
        artifact_store.read_by_sha("raw_response", summary_record["summary_sha256"]),
    )
    if (
        stored_summary.get("version") != SUMMARY_VERSION
        or stored_summary.get("accepted") is not False
        or stored_summary.get("authorized_clinical_adoption") is not False
        or stored_summary.get("clinically_qualified") is not False
    ):
        raise InvalidJobDefinitionError("判断内容汇总工件版本或采信状态无效")
    lane_reads, lane_receipts = _reconstruct_judgment_content_lane_state(
        session=session,
        artifact_store=artifact_store,
        job_id=judgment_content_job_id,
        payload=payload,
        pairs=pairs,
        batches=batches,
        routes=routes,
    )
    rebuilt_summary = compose_judgment_content_summary(
        payload=payload,
        pairs=pairs,
        batches=batches,
        lane_reads=lane_reads,
        lane_receipts=lane_receipts,
    )
    if rebuilt_summary != stored_summary:
        raise InvalidJobDefinitionError("判断内容汇总工件与回执重建结果不一致")
    return {
        "judgment_content_job_id": judgment_content_job_id,
        "job_type": JOB_TYPE,
        "contract": CONTRACT,
        "prompt_version": PROMPT_VERSION,
        "payload": payload,
        "routes": routes,
        "pairs": pairs,
        "batches": batches,
        "summary": rebuilt_summary,
        "summary_sha256": rebuilt_summary["summary_sha256"],
        "summary_artifact_sha256": summary_record["summary_sha256"],
        "input_sha256": payload["input_sha256"],
        "frozen_input_sha256": payload["frozen_input_sha256"],
        "comparison_sha256": payload["comparison_sha256"],
        "review_context_id": payload["review_context_id"],
        "excerpt_coverage": list(payload.get("excerpt_coverage") or []),
        "lane_reads": lane_reads,
        "lane_receipts": lane_receipts,
        "accepted": False,
        "authorized_clinical_adoption": False,
        "clinically_qualified": False,
    }
