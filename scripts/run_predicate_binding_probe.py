"""Explicit read-only isolated probe of the product correspondence reader."""

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

from app.domain.publication import canonical_hash
from app.llm.page_review_harness import (
    direct_completion, preflight_page_reader_routes, require_page_reader_routes,
)
from app.llm.page_review_transport_options import page_completion_options
from app.llm.predicate_binding_candidates import read_predicate_candidates
from app.services.predicate_binding_input import build_predicate_binding_frozen_input
from app.services.predicate_binding_job import JOB_TYPE, PredicateBindingJobExecutor, enqueue_predicate_candidates
from app.evidence.artifacts import ArtifactStore
from app.storage.config import resolve_data_paths
from app.storage.codecs import verify_payload_sha256
from app.storage.db import build_engine, build_session_factory
from app.workflow.runner import JobRunner
from app.workflow.jobstore import JobStore
from scripts.run_frozen_product_reader import require_idle_local_reader


def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def inspect_saved_reads(session, artifacts: ArtifactStore, job_id: str):
    """Audit persisted attempts without treating a completed step as a valid read."""
    from app.services.predicate_binding_job import _reads

    store = JobStore(session)
    job = store.get_job(job_id)
    if job.job_type != JOB_TYPE:
        raise ValueError("不是资料对应试验任务")

    def load(sha):
        raw = artifacts.read_by_sha("raw_response", sha)
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError("已保存调用记录的校验值不一致")
        return json.loads(raw)

    reads = []
    for step_id, lane, _batch in _reads(verify_payload_sha256(job.payload_json, job.payload_sha256)):
        checkpoint = store.get_last_checkpoint(job_id, step_id)
        if checkpoint is None:
            reads.append({"step_id": step_id, "lane": lane.value,
                          "status": "not_recorded", "accepted": False, "calls": []})
            continue
        record = checkpoint[1]
        calls = []
        for sha in record.get("receipt_sha256s", []):
            receipt = load(sha)
            if receipt["job_id"] != job_id or receipt["step_id"] != step_id:
                raise ValueError("调用记录不属于当前任务步骤")
            request = load(receipt["request_sha256"])
            response = load(receipt["response_sha256"]) if receipt.get("response_sha256") else None
            calls.append({
                "receipt_sha256": sha, "request_sha256": receipt["request_sha256"],
                "response_sha256": receipt.get("response_sha256"),
                "model": request["model"], "effort": request["reasoning_effort"],
                "max_tokens": request["max_tokens"],
                "elapsed_seconds": receipt["elapsed_seconds"],
                "error_type": receipt.get("error_type"),
                "finish_reason": response.get("finish_reason") if response else None,
                "usage": response.get("usage") if response else None,
            })
        candidate = load(record["candidate_sha256"]) if record.get("candidate_sha256") else None
        reads.append({
            "step_id": step_id, "lane": lane.value, "status": record["status"],
            "failure": record.get("failure"), "accepted": False, "calls": calls,
            "candidate_sha256": record.get("candidate_sha256"),
            "candidate_count": sum(len(item["candidates"]) for item in candidate["payload"]["results"])
            if candidate is not None else None,
        })
    return {"job_id": job_id, "state": job.state, "accepted": False, "reads": reads}


async def run(database: Path, episode: str, components: list[str], output: Path):
    database = database.resolve(strict=True)
    output.mkdir(parents=True, exist_ok=False)
    engine = create_engine("sqlite://", creator=lambda: sqlite3.connect(
        database.as_uri() + "?mode=ro", uri=True,
    ))
    try:
        with Session(engine) as session:
            frozen = build_predicate_binding_frozen_input(session, episode, component_ids=components)
    finally:
        engine.dispose()
    write_json(output / "input.json", frozen.model_dump(mode="json"))
    routes = await preflight_page_reader_routes(require_page_reader_routes())
    receipts = []

    async def recorded_completion(route, messages, budget):
        if route.provider in {"mtplx", "omlx", "mlx-serve"}:
            require_idle_local_reader(route.provider)
        number = len(receipts)
        request = {"model": route.model, "reasoning_effort": route.reasoning_effort,
                   "messages": messages, "max_tokens": budget,
                   **page_completion_options(route.provider, messages, budget)}
        write_json(output / f"request-{number}.json", request)
        receipt = {"lane": route.lane.value, "provider": route.provider,
                   "model": route.model, "effort": route.reasoning_effort,
                   "request_sha256": canonical_hash(request), "budget": budget}
        start = time.monotonic()
        try:
            response = await direct_completion(route, messages, budget)
            write_json(output / f"response-{number}.json", dataclasses.asdict(response))
            receipt.update(finish_reason=response.finish_reason, usage=dict(response.usage),
                           response_model=response.response_model)
            return response
        except Exception as exc:
            receipt.update(error_type=type(exc).__name__, status_code=getattr(exc, "status_code", None))
            raise
        finally:
            receipt["elapsed_seconds"] = time.monotonic() - start
            receipts.append(receipt)
            write_json(output / "receipts.json", receipts)

    for lane, route in routes.items():
        try:
            result = await read_predicate_candidates(frozen, route, completion=recorded_completion)
            write_json(output / f"candidates-{lane.value}.json", {
                "input_sha256": result.input_sha256, "messages_sha256": result.messages_sha256,
                "payload": result.payload.model_dump(mode="json"), "accepted": False,
                "source_excerpts": result.source_excerpts,
            })
        except Exception as exc:
            write_json(output / f"failure-{lane.value}.json", {
                "error_type": type(exc).__name__, "detail": str(exc), "accepted": False,
            })
    print(json.dumps({"output": str(output), "calls": len(receipts), "accepted": False}))


async def run_persistent(database: Path, episode: str, components: list[str], output: Path, *, batch_max_characters=None):
    """Copy SQLite consistently, then run only the newly created candidate job."""
    database = database.resolve(strict=True)
    output.mkdir(parents=True, exist_ok=False)
    paths = resolve_data_paths(str(output / "data"))
    paths.ensure_directories()
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as source:
        with sqlite3.connect(paths.db_path) as target:
            source.backup(target)
    engine = build_engine(paths.db_path)
    factory = build_session_factory(engine)
    try:
        routes = await preflight_page_reader_routes(require_page_reader_routes())
        async def completion(route, messages, budget):
            if route.provider in {"mtplx", "omlx", "mlx-serve"}:
                require_idle_local_reader(route.provider)
            return await direct_completion(route, messages, budget)
        job = enqueue_predicate_candidates(factory, review_episode_id=episode,
                                           component_ids=components, routes=routes,
                                           batch_max_characters=batch_max_characters)
        write_json(output / "job.json", {"job_id": job.job_id, "source_database": str(database),
                                        "database": str(paths.db_path), "accepted": False})
        executor = PredicateBindingJobExecutor(factory, ArtifactStore(paths), routes, completion=completion)
        await asyncio.to_thread(JobRunner(factory, {JOB_TYPE: executor}).run_job, job.job_id)
        with factory() as session:
            store = JobStore(session)
            result = {"job_id": job.job_id, "state": store.get_job(job.job_id).state,
                      "summary": store.get_last_checkpoint(job.job_id, "summary"), "accepted": False}
            result["read_audit"] = inspect_saved_reads(session, ArtifactStore(paths), job.job_id)
        write_json(output / "result.json", result)
        print(json.dumps({"job_id": job.job_id, "state": result["state"], "accepted": False}))
    finally:
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--episode", required=True)
    parser.add_argument("--component", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--persistent", action="store_true", help="在独立数据库副本中使用正式作业执行器")
    parser.add_argument("--batch-max-characters", type=int, help="隔离分批输入字符上限，不是token额度")
    args = parser.parse_args()
    if args.batch_max_characters is not None and not args.persistent:
        parser.error("分批测试须使用持久作业入口")
    if args.persistent:
        asyncio.run(run_persistent(args.database, args.episode, args.component, args.output,
                                  batch_max_characters=args.batch_max_characters))
    else:
        asyncio.run(run(args.database, args.episode, args.component, args.output))
