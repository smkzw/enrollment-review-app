"""New isolated attempt for one timed-out candidate read; never reset the old job."""

import argparse
import asyncio
import dataclasses
import hashlib
import json
import sqlite3
import time
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import PAGE_REVIEW_TIMEOUT_SECONDS
from app.domain.contracts.predicate_binding import PredicateBindingFrozenInput
from app.evidence.artifacts import ArtifactStore
from app.llm.page_review_harness import (
    direct_completion, resolve_route_model, require_page_reader_routes,
)
from app.llm.page_review_transport_options import page_completion_options
from app.llm.predicate_binding_candidates import (
    PROMPT_VERSION, BATCH_PROMPT_VERSION, build_predicate_binding_messages, read_predicate_candidates,
    predicate_binding_prompt_input,
)
from app.llm.predicate_binding_batches import plan_binding_batches
from app.services.page_review_job_service import route_identity
from app.services.predicate_binding_input import build_predicate_binding_frozen_input
from app.services.predicate_binding_job import CONTRACT, JOB_TYPE, _reads
from app.storage.codecs import verify_payload_sha256
from app.storage.config import resolve_data_paths
from app.workflow.jobstore import JobStore
from scripts.run_frozen_product_reader import require_idle_local_reader
from scripts.run_predicate_binding_probe import write_json


def prepare_recovery(session, artifacts, job_id, step_id, routes):
    store = JobStore(session)
    job = store.get_job(job_id)
    payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
    if (job.job_type != JOB_TYPE or job.state != "failed_final"
            or payload.get("contract") != CONTRACT
            or payload.get("purpose") != "isolated_unverified_candidates"
            or payload.get("prompt_version") != PROMPT_VERSION
            or payload.get("batch_prompt_version") != BATCH_PROMPT_VERSION):
        raise ValueError("只能补测当前合同下已结束的失败任务")
    if payload["routes"] != {lane.value: route_identity(route) for lane, route in routes.items()}:
        raise ValueError("模型配置已变化，不能作为同输入补测")
    selected = next((item for item in _reads(payload) if item[0] == step_id), None)
    checkpoint = store.get_last_checkpoint(job_id, step_id)
    if selected is None or checkpoint is None or checkpoint[1].get("status") != "incomplete":
        raise ValueError("只能补测已有未完成回执的读取步骤")
    _, lane, batch = selected
    record = checkpoint[1]
    frozen = PredicateBindingFrozenInput.model_validate(payload["frozen_input"])
    expected_batches = None
    if payload.get("batch_max_characters") is not None:
        expected_batches = [b.model_dump(mode="json") for b in plan_binding_batches(
            frozen, predicate_binding_prompt_input(frozen),
            max_characters=payload["batch_max_characters"])]
    if payload.get("batches") != expected_batches:
        raise ValueError("原任务分批范围不符合完整输入合同")
    if (record.get("lane") != lane.value
            or record.get("frozen_input_sha256") != frozen.frozen_input_sha256
            or record.get("batch_sha256") != (batch.batch_sha256 if batch else None)):
        raise ValueError("原读取回执范围不一致")
    current = build_predicate_binding_frozen_input(
        session, frozen.authority.review_episode_id,
        component_ids=[c.rule_component_id for c in frozen.components],
    )
    if current.frozen_input_sha256 != frozen.frozen_input_sha256:
        raise ValueError("当前资料已变化，不能沿用原冻结输入")

    def load(sha):
        raw = artifacts.read_by_sha("raw_response", sha)
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError("原调用记录校验失败")
        return json.loads(raw)

    receipts = record.get("receipt_sha256s", [])
    if not receipts:
        raise ValueError("缺少原调用记录")
    receipt = load(receipts[-1])
    if (receipt.get("job_id") != job_id or receipt.get("step_id") != step_id
            or receipt.get("error_type") != "APITimeoutError"
            or receipt.get("response_sha256") is not None):
        raise ValueError("本入口仅用于未取得回答的超时，不重放内容失败")
    original_request = load(receipt["request_sha256"])
    route = routes[lane]
    messages = build_predicate_binding_messages(frozen, batch=batch)
    request = {"model": route.model, "reasoning_effort": route.reasoning_effort,
               "messages": messages, "max_tokens": route.max_tokens,
               **page_completion_options(route.provider, messages, route.max_tokens)}
    if request != original_request:
        raise ValueError("当前请求与原失败请求不同，不能作为同输入补测")
    return frozen, route, batch, {
        "source_job_id": job_id, "source_step_id": step_id,
        "source_checkpoint_id": checkpoint[0], "source_receipt_sha256": receipts[-1],
        "source_request_sha256": receipt["request_sha256"],
        "frozen_input_sha256": frozen.frozen_input_sha256,
        "batch_sha256": batch.batch_sha256 if batch else None,
        "accepted": False,
    }


async def run(source_run, step_id, output):
    source_run = source_run.resolve(strict=True)
    paths = resolve_data_paths(str(source_run / "data"))
    source_job = json.loads((source_run / "job.json").read_text())["job_id"]
    engine = create_engine("sqlite://", creator=lambda: sqlite3.connect(
        paths.db_path.as_uri() + "?mode=ro", uri=True))
    routes = require_page_reader_routes()
    try:
        with Session(engine) as session:
            frozen, route, batch, lineage = prepare_recovery(
                session, ArtifactStore(paths), source_job, step_id, routes)
    finally:
        engine.dispose()
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "lineage.json", {
        **lineage, "timeout_seconds": PAGE_REVIEW_TIMEOUT_SECONDS,
        "note": "独立补测，不改旧作业；运行条件单独记录，不视为原轮完成",
    })
    receipts = []

    async def recorded(route, messages, budget):
        if route.provider in {"mtplx", "omlx", "mlx-serve"}:
            require_idle_local_reader(route.provider)
        number = len(receipts)
        request = {"model": route.model, "reasoning_effort": route.reasoning_effort,
                   "messages": messages, "max_tokens": budget,
                   **page_completion_options(route.provider, messages, budget)}
        write_json(output / f"request-{number}.json", request)
        receipt = {"request_number": number, "usage": None}
        start = time.monotonic()
        try:
            response = await direct_completion(route, messages, budget)
            write_json(output / f"response-{number}.json", dataclasses.asdict(response))
            receipt.update(usage=dict(response.usage), finish_reason=response.finish_reason)
            return response
        except BaseException as exc:
            receipt["error_type"] = type(exc).__name__
            raise
        finally:
            receipt["elapsed_seconds"] = time.monotonic() - start
            receipts.append(receipt)
            write_json(output / "receipts.json", receipts)

    try:
        await resolve_route_model(route)
        result = await read_predicate_candidates(frozen, route, completion=recorded, batch=batch)
        write_json(output / "candidates.json", {
            **lineage, "payload": result.payload.model_dump(mode="json"),
            "messages_sha256": result.messages_sha256, "source_excerpts": result.source_excerpts,
        })
    except BaseException as exc:
        write_json(output / "failure.json", {**lineage, "error_type": type(exc).__name__, "detail": str(exc)})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", required=True, type=Path)
    parser.add_argument("--step", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.source_run, args.step, args.output))
