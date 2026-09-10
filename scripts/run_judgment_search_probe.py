"""Two-step isolated probe of the product candidate reader; never writes the source DB."""

import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sqlite3
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.page_review import PageReviewLane
from app.evidence.artifacts import ArtifactStore
from app.llm.independent_vlm import PageVisionInput
from app.llm.judgment_search_reader import read_judgment_search_page, read_judgment_search_page_batch
from app.llm.page_review_harness import (
    PageReviewInput, direct_completion, require_page_reader_routes, resolve_route_model,
)
from app.services.judgment_search_source import prepare_judgment_search_target
from app.services.judgment_search_artifacts import save_judgment_search_receipt, load_judgment_search_receipt
from app.services.judgment_search_results import assemble_judgment_search_coverage
from app.storage.config import resolve_data_paths


def save(path, payload):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)


def prepare_source(runtime, source_job, requirement, page_artifact):
    database = runtime.resolve() / "enrollment-review-v2.sqlite3"
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute("SELECT payload_json FROM jobs WHERE job_id=?", (source_job,)).fetchone()
        if row is None:
            raise ValueError("指定来源作业不存在")
        authority = FactAuthority.model_validate(json.loads(row[0])["authority"])
    engine = create_engine("sqlite:///" + database.as_uri() + "?mode=ro&uri=true")
    try:
        with Session(engine) as session:
            scope, target = prepare_judgment_search_target(session, authority, requirement)
    finally:
        engine.dispose()
    matches = [page for page in scope.pages if page.page_artifact_id == page_artifact]
    if len(matches) != 1:
        raise ValueError("所选页不在当前来源范围内")
    page = matches[0]
    image = ArtifactStore(resolve_data_paths(str(runtime))).read_by_sha("page_image", page.page_image_sha256)
    page_input = PageReviewInput(
        page_artifact_id=page.page_artifact_id,
        source_document_version_id=page.source_document_version_id,
        page_number=page.page_number,
        page_image_sha256=page.page_image_sha256,
        page=PageVisionInput(source_ref=page.page_artifact_id, page_ordinal=page.page_number,
                             image_bytes=image, media_type="image/png"),
    )
    return scope, target, page_input, image


async def run(args):
    out = args.output.resolve()
    if args.mode == "prepare":
        scope, target, page_input, image = prepare_source(
            args.runtime, args.source_job, args.requirement, args.page_artifact)
        extra = []
        requirements = [args.requirement, *args.additional_requirement]
        if len(requirements) != len(set(requirements)):
            raise ValueError("检索要求不得重复")
        for requirement in args.additional_requirement:
            other_scope, other_target, _, other_image = prepare_source(
                args.runtime, args.source_job, requirement, args.page_artifact)
            if other_image != image:
                raise ValueError("准备期间原件发生变化")
            extra.append({"requirement": requirement, "scope": other_scope.model_dump(mode="json"),
                          "target_text": other_target})
        out.mkdir(parents=True, exist_ok=False)
        with (out / "source.png").open("xb") as stream:
            stream.write(image)
        save(out / "input.json", {
            "runtime": str(args.runtime.resolve()), "source_job": args.source_job,
            "requirement": args.requirement, "page_artifact": args.page_artifact,
            "scope": scope.model_dump(mode="json"), "target_text": target,
            "additional_targets": extra,
            "product_acceptance": False, "claims_complete": False,
        })
        print(json.dumps({"prepared": True, "scope_pages": len(scope.pages),
                          "target_characters": len(target), "model_calls": 0}))
        return
    frozen = json.loads((out / "input.json").read_text())
    scope, target, page_input, image = prepare_source(
        Path(frozen["runtime"]), frozen["source_job"], frozen["requirement"], frozen["page_artifact"])
    if scope.model_dump(mode="json") != frozen["scope"] or target != frozen["target_text"]:
        raise ValueError("来源或已发布目标已经变化，拒绝沿用本次准备")
    if (out / "source.png").read_bytes() != image:
        raise ValueError("冻结图片与当前来源不一致")
    targets = [(scope, target)]
    for item in frozen.get("additional_targets", []):
        other_scope, other_target, _, other_image = prepare_source(
            Path(frozen["runtime"]), frozen["source_job"], item["requirement"], frozen["page_artifact"])
        if other_scope.model_dump(mode="json") != item["scope"] or other_target != item["target_text"] or other_image != image:
            raise ValueError("批次来源或目标已变化")
        targets.append((other_scope, other_target))
    routes = require_page_reader_routes()
    expected = {PageReviewLane.MAIN_A: ("zhipu-coding-plan", "glm-5.3-flash"),
                PageReviewLane.MAIN_B: ("google-antigravity", "gemini-3.7-flash")}
    for lane, identity in expected.items():
        route = routes[lane]
        if (route.provider, route.model.lower()) != identity or route.max_tokens < 65536:
            raise ValueError("本次仅允许已批准的GLM/Gemini及至少65536输出额度")
    attempt = out / "attempt"
    attempt.mkdir(exist_ok=False)
    receipt_store = ArtifactStore(resolve_data_paths(str(attempt / "receipt-store")))
    save(attempt / "code.json", {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in [Path(__file__), Path("app/llm/judgment_search_reader.py"),
                                          Path("app/services/judgment_search_source.py"),
                                          Path("app/services/judgment_search_results.py"),
                                          Path("app/services/judgment_search_artifacts.py")]})

    async def search(lane):
        prefix = attempt / lane.value
        started = time.monotonic()
        try:
            route = await resolve_route_model(routes[lane])

            async def recorded_completion(active_route, messages, budget):
                save(prefix.with_suffix(".request.json"), {"messages": messages, "budget": budget,
                     "provider": active_route.provider, "model": active_route.model,
                     "effort": active_route.reasoning_effort})
                response = await direct_completion(active_route, messages, budget)
                save(prefix.with_suffix(".response.json"), asdict(response))
                return response

            if len(targets) == 1:
                receipts = (await read_judgment_search_page(scope=scope, page_input=page_input,
                    target_text=target, route=route, completion=recorded_completion),)
                save(prefix.with_suffix(".receipt.json"), receipts[0].model_dump(mode="json"))
            else:
                receipts = await read_judgment_search_page_batch(targets=targets, page_input=page_input,
                    route=route, completion=recorded_completion)
                save(prefix.with_suffix(".receipts.json"), [r.model_dump(mode="json") for r in receipts])
            refs = []
            for (current_scope, current_target), receipt in zip(targets, receipts, strict=True):
                stored = save_judgment_search_receipt(receipt_store, current_scope, current_target, receipt)
                loaded = load_judgment_search_receipt(receipt_store, current_scope, current_target, stored.storage_ref)
                if loaded != receipt:
                    raise ValueError("保存后回读不一致")
                refs.append(stored.storage_ref)
            result = {"candidate_received": True, "receipt_refs": refs}
        except Exception as exc:
            result = {"candidate_received": False, "error_type": type(exc).__name__,
                      "failure_kind": getattr(exc, "failure_kind", None)}
        result.update(lane=lane.value, elapsed_seconds=time.monotonic()-started,
                      product_acceptance=False, claims_complete=False)
        save(prefix.with_suffix(".status.json"), result)
        return result

    results = await asyncio.gather(*(search(lane) for lane in expected))
    save(attempt / "summary.json", results)
    for index, (current_scope, current_target) in enumerate(targets):
        receipts = [load_judgment_search_receipt(receipt_store, current_scope, current_target,
                    result["receipt_refs"][index]) for result in results if result["candidate_received"]]
        coverage = assemble_judgment_search_coverage(current_scope, current_target, receipts)
        save(attempt / f"target-{index}.coverage.json", coverage.model_dump(mode="json"))
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "execute"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--source-job")
    parser.add_argument("--requirement")
    parser.add_argument("--additional-requirement", action="append", default=[])
    parser.add_argument("--page-artifact")
    args = parser.parse_args()
    if args.mode == "prepare" and not all((args.runtime, args.source_job, args.requirement, args.page_artifact)):
        parser.error("prepare requires runtime, source-job, requirement and page-artifact")
    asyncio.run(run(args))
