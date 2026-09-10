"""Freeze a genuine product input and exercise its unchanged page reader."""

import argparse
import asyncio
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import time
import urllib.request

from app.domain.contracts.clause_pack import ClausePack
from app.domain.contracts.page_review_context import PageReviewContext
from app.domain.contracts.page_review import PageReviewLane
from app.evidence.artifacts import ArtifactStore
from app.llm.independent_vlm import PageVisionInput
from app.llm.page_review_harness import read_page, PageReviewInput, PageCompletion, require_page_reader_routes, direct_openai_completion
from app.storage.config import resolve_data_paths
from app.config import PAGE_REVIEW_TIMEOUT_SECONDS


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def require_idle_local_reader(provider):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    if provider == 'mtplx':
        with opener.open('http://127.0.0.1:8002/v1/mtplx/metrics/stream', timeout=10) as stream:
            stream.readline()
            snapshot = json.loads(stream.readline().decode().removeprefix('data: '))
        if snapshot['in_flight']:
            raise RuntimeError('A local request is still active; no new request was submitted')
    elif provider == 'omlx':
        with opener.open('http://127.0.0.1:8001/api/status', timeout=10) as stream:
            snapshot = json.load(stream)
        if snapshot['active_requests'] or snapshot['waiting_requests']:
            raise RuntimeError('A local request is still active or queued; no new request was submitted')
    elif provider == 'mlx-serve':
        with opener.open('http://127.0.0.1:11234/metrics', timeout=10) as stream:
            metrics = dict(line.split() for line in stream.read().decode().splitlines()
                           if line.startswith(('vllm:num_requests_running ', 'vllm:num_requests_waiting ')))
        if any(float(metrics[name]) != 0 for name in
               ('vllm:num_requests_running', 'vllm:num_requests_waiting')):
            raise RuntimeError('MLX Serve is still active or queued; no new request was submitted')


def freeze(source, destination, job_id):
    destination.mkdir(parents=True, exist_ok=False)
    database = source / "enrollment-review-v2.sqlite3"
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute("SELECT state,payload_json FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None or row[0] != "completed":
            raise ValueError("Expected a completed source job")
        payload = json.loads(row[1])
        with sqlite3.connect(destination / database.name) as target:
            db.backup(target)
    store = ArtifactStore(resolve_data_paths(str(source)))
    pages = destination / "pages"
    pages.mkdir()
    for page in payload["pages"]:
        digest = page["page_image_sha256"]
        image = store.read_by_sha("page_image", digest)
        if hashlib.sha256(image).hexdigest() != digest:
            raise ValueError("Source image mismatch")
        (pages / digest).write_bytes(image)
    # Retain original uploaded files as well as the exact rendered reader input.
    shutil.copytree(source / "blobs", destination / "blobs")
    save(destination / "input.json", payload)
    code = destination / "product-code"
    shutil.copytree(Path("app"), code, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(__file__, destination / "runner.py")
    plan = Path(".trellis/tasks/09-05-phase55-dual-vlm-page-review/MODEL_COMPARISON_20260907.md")
    shutil.copy2(plan, destination / "test-plan.md")
    manifest = {str(p.relative_to(destination)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in destination.rglob("*") if p.is_file()}
    save(destination / "manifest.json", {"source_job": job_id, "files": manifest,
         "clinical_acceptance": False, "gold_in_model_input": False})


async def run(args):
    if args.output is None or args.page_index < 0 or (args.provider and not args.model):
        raise ValueError('Require output, nonnegative page index, and explicit model for provider override')
    payload = json.loads((args.frozen / "input.json").read_text())
    indices = args.batch_pages or [args.page_index]
    if len(set(indices)) != len(indices) or any(i < 0 or i >= len(payload['pages']) for i in indices):
        raise ValueError('Page indices must be unique and in the frozen input')
    if args.batch_pages and args.context_layout != 'baseline':
        raise ValueError('Batch experiment must preserve the full baseline ClausePack')
    manifest = json.loads((args.frozen / "manifest.json").read_text())
    for name, digest in manifest["files"].items():
        if hashlib.sha256((args.frozen / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Frozen input changed: " + name)
        if name.startswith("product-code/"):
            current = Path("app") / Path(name).relative_to("product-code")
            if hashlib.sha256(current.read_bytes()).hexdigest() != digest:
                raise ValueError("Product version changed; create a new benchmark version")
    route = require_page_reader_routes()[PageReviewLane(args.lane)]
    if route.max_tokens < 65536:
        raise ValueError('Formal benchmark requires PAGE_REVIEW_MAX_TOKENS >= 65536; no request submitted')
    route = replace(route, reasoning_effort=args.effort or route.reasoning_effort, fallback_base_url="")
    if args.model:
        route = replace(route, model=args.model)
    if args.provider:
        route = replace(route, provider=args.provider, api_key="local-benchmark" if args.provider in {"omlx", "mtplx", "mlx-serve"} else "",
            base_url={"google-antigravity": "https://daily-cloudcode-pa.googleapis.com",
                      "opencode-go": "https://opencode.ai/zen/go/v1",
                      "openai-codex": "https://chatgpt.com/backend-api/codex",
                      "omlx": "http://127.0.0.1:8001/v1",
                      "mtplx": "http://127.0.0.1:8002/v1",
                      "mlx-serve": "http://127.0.0.1:11234/v1"}[args.provider])
    require_idle_local_reader(args.provider)
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.output / "runner.py")
    save(args.output / 'run-contract.json', {
        'frozen': str(args.frozen.resolve()), 'lane': args.lane, 'effort': route.reasoning_effort,
        'context_layout': args.context_layout,
        'page_indices': indices, 'multi_page_request': bool(args.batch_pages),
        'manifest_sha256': hashlib.sha256((args.frozen / 'manifest.json').read_bytes()).hexdigest(),
    })
    if args.provider:
        shutil.copy2(Path(__file__).with_name("benchmark_direct_transports.py"),
                     args.output / "transport.py")
    page_inputs = []
    for index in indices:
        page = payload['pages'][index]
        image = (args.frozen / 'pages' / page['page_image_sha256']).read_bytes()
        page_inputs.append(PageReviewInput(**page,
            review_context=PageReviewContext.model_validate(payload['review_context']),
            page=PageVisionInput(source_ref=page['page_artifact_id'],
                page_ordinal=page['page_number'], image_bytes=image)))
    page_input = page_inputs[0]
    receipts = []

    async def completion(active_route, messages, budget):
        index = len(receipts)
        save(args.output / f"request-{index}.json", {"messages": messages, "budget": budget,
             "model": active_route.model, "effort": active_route.reasoning_effort})
        started = time.monotonic()
        receipt = {"model": active_route.model, "effort": active_route.reasoning_effort,
                   "requested_budget": budget, "output_budget_enforced": args.provider != "openai-codex"}
        try:
            if args.provider in {"google-antigravity", "openai-codex", "opencode-go"}:
                from scripts.benchmark_direct_transports import subscription_completion, normalized_finish
                wire = await subscription_completion(active_route.provider, active_route.model,
                    active_route.reasoning_effort, messages, budget, timeout=PAGE_REVIEW_TIMEOUT_SECONDS)
                save(args.output / f"transport-{index}.json", wire)
                if wire.get("http_status") != 200 or wire.get("error"):
                    error = RuntimeError("Subscription transport failed; see retained receipt")
                    error.status_code = wire.get("http_status")
                    raise error
                finish = normalized_finish(wire)
                result = PageCompletion(text=wire["text"], finish_reason=finish,
                    usage=wire["usage"], response_model=wire["response_model"],
                    response_id=wire["response_id"], output_lengths={
                        "content_characters": len(wire["text"]),
                        "reasoning_content_characters": wire.get("thought_characters")})
            else:
                result = await direct_openai_completion(active_route, messages, budget)
            save(args.output / f"response-{index}.json", {"text": result.text,
                 "finish_reason": result.finish_reason, "usage": result.usage,
                 "response_model": result.response_model, "response_id": result.response_id,
                 "output_lengths": result.output_lengths})
            receipt.update(usage=result.usage, finish_reason=result.finish_reason,
                           response_model=result.response_model, output_lengths=result.output_lengths)
            return result
        except Exception as exc:
            receipt.update(error_type=type(exc).__name__, status_code=getattr(exc, "status_code", None))
            raise
        finally:
            receipt["elapsed_seconds"] = time.monotonic() - started
            receipts.append(receipt)
            save(args.output / "receipts.json", receipts)

    try:
        if args.batch_pages:
            from app.llm.page_review_batch_experiment import read_page_batch
            shutil.copy2('app/llm/page_review_batch_experiment.py', args.output / 'batch_variant.py')
            result = await read_page_batch(route, page_inputs,
                ClausePack.model_validate(payload['clause_pack']), completion=completion)
            save(args.output / 'batch.json', {
                'batch_id': result.batch_id, 'prompt_version': result.prompt_version,
                'batch_request_sha256': result.batch_request_sha256,
                'finish_reason': result.finish_reason, 'usage': result.usage,
                'failures': [asdict(item) for item in result.failures],
                'records': [record.model_dump(mode='json') for record in result.records],
                'clinical_acceptance': False,
            })
            status = {'state': 'batch_partial' if result.failures else 'batch_completed',
                      'clinical_acceptance': False, 'records': len(result.records),
                      'failures': len(result.failures)}
            save(args.output / 'status.json', status)
            print(json.dumps(status), flush=True)
            return
        reader = read_page
        if args.context_layout != 'baseline':
            from app.llm.page_review_context_layout import read_page_stable_prefix, read_page_source_reading
            variant = Path('app/llm/page_review_context_layout.py')
            shutil.copy2(variant, args.output / variant.name)
            reader = {'stable-prefix': read_page_stable_prefix,
                      'source-reading': read_page_source_reading}[args.context_layout]
        result = await reader(route, page_input, ClausePack.model_validate(payload["clause_pack"]),
                                 completion=completion)
        save(args.output / "record.json", result.model_dump(mode="json"))
        status = {"state": "reader_completed", "clinical_acceptance": False}
    except Exception as exc:
        status = {"state": "reader_failed", "error_type": type(exc).__name__,
                  "failure_kind": getattr(exc, "failure_kind", None), "clinical_acceptance": False}
        if args.batch_pages:
            status['state'] = 'batch_failed'
            status['failed_page_artifact_ids'] = [page.page_artifact_id for page in page_inputs]
        if status["failure_kind"] in {"schema", "invalid_json", "length"}:
            status["contract_error"] = str(exc)
        if hasattr(exc, "errors"):
            status["validation_errors"] = exc.errors(include_input=False, include_context=False)
    save(args.output / "status.json", status)
    print(json.dumps(status), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-source", type=Path)
    parser.add_argument("--source-job")
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--lane", choices=("main-A", "main-B"), default="main-A")
    parser.add_argument("--effort", choices=("low", "high", "max"))
    parser.add_argument("--model")
    parser.add_argument("--provider", choices=("google-antigravity", "openai-codex", "opencode-go", "omlx", "mtplx", "mlx-serve"))
    parser.add_argument("--page-index", type=int, default=0)
    parser.add_argument('--batch-pages', nargs='+', type=int,
                        help='Opt-in multi-page request; default remains one page')
    parser.add_argument("--context-layout", choices=('baseline', 'stable-prefix', 'source-reading'), default='baseline')
    args = parser.parse_args()
    if args.freeze_source:
        freeze(args.freeze_source.resolve(), args.frozen, args.source_job)
    else:
        asyncio.run(run(args))
