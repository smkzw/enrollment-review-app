"""Isolated streaming measurements around the unchanged product page harness."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import time

import httpx

from app.domain.contracts.clause_pack import ClausePack
from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.page_review_context import PageReviewContext
from app.llm.independent_vlm import PageVisionInput
from app.llm.generation_repetition import repetitive_reasoning_tail, repetitive_closing_tag_tail
from app.llm.page_review_harness import PageCompletion, PageReaderRoute, PageReviewInput, read_page
from app.llm.page_review_transport_options import page_completion_options
from scripts.run_frozen_product_reader import require_idle_local_reader
from scripts.capture_mtplx_benchmark_metrics import FIELDS


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


async def await_idle(provider):
    # A finished stream can precede the platform's final resource release.
    for attempt in range(31):
        try:
            require_idle_local_reader(provider)
            return
        except RuntimeError:
            if attempt == 30:
                raise
            await asyncio.sleep(1)


async def metrics(route, response_id=None):
    path = "/api/status" if route.provider == "omlx" else "/metrics"
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=10) as client:
            response = await client.get(route.base_url.removesuffix("/v1")+path)
            response.raise_for_status()
            if route.provider == "mlx-serve":
                return {line.split()[0]: float(line.split()[1]) for line in response.text.splitlines()
                        if line.startswith("vllm:") and len(line.split()) == 2}
            value = response.json()
            if route.provider == "mtplx":
                return [{k: item.get(k) for k in FIELDS} for item in value.get("recent", [])
                        if response_id and item.get("request_id") == response_id]
            return {k: v for k, v in value.items() if k.startswith(("total_", "avg_", "cache_", "active_", "waiting_"))}
    except Exception as exc:
        return {"unavailable": type(exc).__name__}


class MeasuredCompletion:
    def __init__(self, output, tokenizer):
        self.output = output
        self.tokenizer = tokenizer
        self.receipts = []
        self.call_number = 0

    async def __call__(self, route, messages, budget, request_options=None):
        if budget > 131072:
            raise ValueError("Requested retry exceeds the authorized output ceiling")
        index = self.call_number
        self.call_number += 1
        request_path = self.output / f"request-{index}.json"
        body = dict(model=route.model, messages=messages, max_tokens=budget,
                    reasoning_effort=route.reasoning_effort, stream=True, stream_options={"include_usage": True})
        if request_options is None:
            options = page_completion_options(route.provider, messages, budget)
            body.update(options.pop("extra_body", {}))
            body.update(options)
        if request_options:
            body.update(request_options)
        save(request_path, body)
        # CPU-only tokenizer subprocess never loads weights or a second local runtime.
        code = """
import sys,json
from pathlib import Path
from transformers import AutoTokenizer
p=json.load(open(sys.argv[1])); images=0; messages=[]
for m in p['messages']:
 c=m['content']
 if isinstance(c,list):
  images+=sum(x.get('type')=='image_url' for x in c)
  c='\\n'.join(x['text'] for x in c if x.get('type')=='text')
 messages.append(dict(role=m['role'],content=c))
t=AutoTokenizer.from_pretrained(sys.argv[2],local_files_only=True,trust_remote_code=False)
ids=t.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,reasoning_effort=p['reasoning_effort'],enable_thinking=True)
if hasattr(ids,'keys'): ids=ids['input_ids']
if ids and isinstance(ids[0],list): ids=ids[0]
schema_tokens=len(t.encode(json.dumps(p['response_format'],ensure_ascii=False))) if p.get('response_format') else 0
print(json.dumps(dict(text_tokens=len(ids)+schema_tokens,image_allowance=images*16384)))
"""
        counted = subprocess.run([str(Path.home()/".mtplx/venv/bin/python"), "-c", code,
                                  str(request_path), str(self.tokenizer)],
                                 capture_output=True, text=True, check=True)
        count = json.loads(counted.stdout)
        if count["text_tokens"] + count["image_allowance"] > 65536:
            raise ValueError("Input exceeds conservative 64K admission; no request submitted")
        await await_idle(route.provider)
        before = await metrics(route)
        start = time.monotonic()
        receipt = {"provider": route.provider, "model": route.model, "requested_effort": route.reasoning_effort,
                   "requested_output_tokens": budget, "input_admission": count,
                   "ttft_seconds": None, "first_content_seconds": None,
                   "sampling": "platform defaults; no sampling overrides",
                   "response_format_name": body.get("response_format", {}).get("json_schema", {}).get("name"),
                   "response_format_sha256": (hashlib.sha256(json.dumps(
                       body["response_format"], ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode()).hexdigest()
                       if body.get("response_format") else None),
                   "request_sha256": hashlib.sha256(request_path.read_bytes()).hexdigest()}
        text, reasoning, usage, finish, model, response_id = "", "", {}, None, None, None
        repetition_check_length = 0
        content_check_length = 0
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=httpx.Timeout(7200, connect=15)) as client:
                async with client.stream("POST", route.base_url.rstrip("/")+"/chat/completions",
                                         json=body, headers={"Authorization": "Bearer "+route.api_key}) as response:
                    receipt["http_status"] = response.status_code
                    receipt["response_format_warning"] = response.headers.get("Warning")
                    if response.is_error:
                        await response.aread()
                        receipt["http_error_body"] = response.text
                    response.raise_for_status()
                    if (body.get("response_format") and "not enforced" in
                            (receipt["response_format_warning"] or "").lower()):
                        raise RuntimeError("Native output constraint was not enforced")
                    with (self.output / f"stream-{index}.jsonl").open("w") as events:
                        async for line in response.aiter_lines():
                            if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                                continue
                            event = json.loads(line[5:])
                            events.write(json.dumps(event, ensure_ascii=False)+"\n")
                            events.flush()
                            if event.get("error"):
                                raise ValueError("Provider stream error; see retained event")
                            model = event.get("model", model)
                            response_id = event.get("id", response_id)
                            usage = event.get("usage") or usage
                            for choice in event.get("choices", []):
                                delta = choice.get("delta", {})
                                thought = delta.get("reasoning_content") or delta.get("reasoning") or ""
                                content = delta.get("content") or ""
                                if (thought or content) and receipt["ttft_seconds"] is None:
                                    receipt["ttft_seconds"] = time.monotonic()-start
                                if content and receipt["first_content_seconds"] is None:
                                    receipt["first_content_seconds"] = time.monotonic()-start
                                text += content
                                reasoning += thought
                                finish = choice.get("finish_reason") or finish
                                if len(text) - content_check_length >= 2048:
                                    content_check_length = len(text)
                                    if repetitive_closing_tag_tail(text):
                                        receipt["failure_kind"] = "repetitive_content_tags"
                                        raise ValueError("Sustained closing-tag repetition; partial stream retained")
                                if len(reasoning) - repetition_check_length >= 2048:
                                    repetition_check_length = len(reasoning)
                                    if repetitive_reasoning_tail(reasoning):
                                        receipt["failure_kind"] = "repetitive_reasoning"
                                        raise ValueError("Sustained reasoning repetition; partial stream retained")
            if model != route.model:
                raise ValueError("Response model does not match requested identity")
            if usage.get("prompt_tokens", 0) > 65536:
                raise ValueError("Runtime reports input above authorized ceiling; result ineligible")
            return PageCompletion(text=text, finish_reason=finish, usage=usage,
                                  response_model=model, response_id=response_id,
                                  transport_contract=("omlx-schema-request-v1" if
                                      route.provider == "omlx" and body.get("response_format") else None),
                                  output_lengths={"content_characters": len(text),
                                                  "reasoning_content_characters": len(reasoning)})
        except Exception as exc:
            receipt["error_type"] = type(exc).__name__
            raise
        finally:
            receipt.update(elapsed_seconds=time.monotonic()-start, usage=usage,
                           finish_reason=finish, response_model=model, response_id=response_id)
            receipt["runtime_before"] = before
            receipt["runtime_after"] = await metrics(route, response_id)
            save(self.output/f"response-{index}.json", {**receipt, "text": text, "reasoning": reasoning})
            self.receipts.append(receipt)
            save(self.output/"receipts.json", self.receipts)


async def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    payload = json.loads((args.frozen/"input.json").read_text())
    source = payload["pages"][args.page]
    image = (args.frozen/"pages"/source["page_image_sha256"]).read_bytes()
    if hashlib.sha256(image).hexdigest() != source["page_image_sha256"]:
        raise ValueError("Source image changed")
    route = PageReaderRoute(PageReviewLane.MAIN_A, args.provider, args.url,
                            "local-benchmark", args.model, args.effort, 131072, 1)
    source_input = PageReviewInput(**source,
        review_context=PageReviewContext.model_validate(payload["review_context"]),
        page=PageVisionInput(source_ref=source["page_artifact_id"],
                             page_ordinal=source["page_number"], image_bytes=image))
    save(args.output/"contract.json", {"source": source, "frozen": str(args.frozen.resolve()),
        "input_sha256": hashlib.sha256((args.frozen/"input.json").read_bytes()).hexdigest(),
        "prompt_harness_sha256": hashlib.sha256(Path("app/llm/page_review_harness.py").read_bytes()).hexdigest(),
        "measurement_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "clinical_acceptance": False, "gold_in_input": False, "lane": "main-A",
        "offline_response_revalidation": str(args.replay_response) if args.replay_response else None})
    completion = MeasuredCompletion(args.output,args.tokenizer)
    if args.replay_response:
        original = json.loads(args.replay_response.read_text())
        request = json.loads(args.replay_response.with_name(
            args.replay_response.name.replace("response-", "request-")).read_text())

        async def completion(route, messages, budget):
            if (request["messages"] != messages or request["model"] != route.model
                    or request["reasoning_effort"] != route.reasoning_effort
                    or request["max_tokens"] != budget):
                raise ValueError("Replay request differs from original live request")
            return PageCompletion(text=original["text"], finish_reason=original["finish_reason"],
                usage=original["usage"], response_model=original["response_model"],
                response_id=original["response_id"], transport_contract=("omlx-schema-request-v1" if
                    route.provider == "omlx" and request.get("response_format") else None))
    try:
        record = await read_page(route, source_input, ClausePack.model_validate(payload["clause_pack"]),
                                 completion=completion)
        save(args.output/"record.json", record.model_dump(mode="json"))
        status = {"state": "completed", "clinical_acceptance": False}
    except Exception as exc:
        status = {"state": "failed", "type": type(exc).__name__, "detail": str(exc),
                  "clinical_acceptance": False}
    save(args.output/"status.json", status)
    print(json.dumps(status), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--provider", choices=["omlx","mtplx","mlx-serve"], required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", choices=["xhigh", "medium", "low"], default="xhigh")
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--replay-response", type=Path,
                        help="Offline revalidation of a retained live response; performs no model call")
    asyncio.run(main(parser.parse_args()))
