"""Read frozen main-reader observations using product transports; no clinical writes."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import time
from dataclasses import replace

from app.domain.contracts.page_review import PageReviewLane, PageReviewRecord
from app.llm.page_review_harness import (
    direct_completion, extract_json_object, require_page_reader_routes,
    resolve_route_model,
)
from scripts.evaluate_observation_alignment import Proposal, check_pairs, load_database_samples
from scripts.medication_component_experiment import (
    MedicationObservation, MedicationComponentExtraction, build_component_prompt,
    validate_extraction, compare_component_outputs,
)


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


async def run(args):
    if args.max_tokens < 65536:
        raise ValueError("Experiment requires at least 65536 output tokens")
    if args.records:
        if args.source or args.database or args.coverage or args.indices:
            raise ValueError("Use records alone")
        records = [PageReviewRecord.model_validate_json(Path(path).read_text()) for path in args.records]
        source = json.dumps({"source_records": [r.model_dump(mode="json") for r in records]},
                            ensure_ascii=False).encode()
    elif args.source:
        if args.database or args.coverage or args.indices:
            raise ValueError("Use source file or database scope, not both")
        source = Path(args.source).read_bytes()
        payload = json.loads(source)
        keys = [key for key in ("source_records", "records") if key in payload]
        if len(keys) != 1:
            raise ValueError("Require one unambiguous saved reader collection")
        records = [PageReviewRecord.model_validate(x) for x in payload[keys[0]]]
    else:
        if not args.database or not args.coverage or not args.indices or len(args.indices) != 1:
            raise ValueError("Require exactly one frozen database page")
        _, a, b = load_database_samples(args)[0]
        records = [a, b]
        source = json.dumps({"source_records": [r.model_dump(mode="json") for r in records]},
                            ensure_ascii=False).encode()
    lanes = {r.lane: r for r in records}
    a, b = lanes[PageReviewLane.MAIN_A], lanes[PageReviewLane.MAIN_B]
    check_pairs(Proposal(pairs=[]), a, b)
    if len(records) != 2 or a.page_review_id == b.page_review_id:
        raise ValueError("Require distinct frozen main-reader records")
    pairs = [tuple(value.split(":")) for value in args.pair]
    if any(len(pair) != 2 for pair in pairs) or len(set(pairs)) != len(pairs):
        raise ValueError("Require unique a:b pairs")
    if any(len({pair[i] for pair in pairs}) != len(pairs) for i in (0, 1)):
        raise ValueError("Pairs must be one-to-one")
    facts = [{f.observation_id: f for f in r.facts} for r in (a, b)]
    for pair in pairs:
        for index, identity in enumerate(pair):
            if identity not in facts[index]:
                raise ValueError("Unknown frozen observation")
    routes = require_page_reader_routes()
    selected = [await resolve_route_model(routes[r.lane]) for r in (a, b)]
    if args.main_a_effort:
        selected[0] = replace(selected[0], reasoning_effort=args.main_a_effort)
    if (selected[0].provider, selected[0].model) == (selected[1].provider, selected[1].model):
        raise ValueError("Same model cannot count as independent readers")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    save(out / "source.json", json.loads(source))
    save(out / "contract.json", {
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "pairs": pairs, "max_tokens": args.max_tokens,
        "scope": "existing-observation-components-only/no-new-page-reading",
        "product_acceptance": False, "source_qc_required": True,
        "code_sha256": {name: hashlib.sha256(Path(name).read_bytes()).hexdigest()
                        for name in (__file__, "scripts/medication_component_experiment.py")},
    })
    semaphores = [asyncio.Semaphore(2), asyncio.Semaphore(2)]

    async def extract(pair_index, lane_index):
        record, route = (a, b)[lane_index], selected[lane_index]
        fact = facts[lane_index][pairs[pair_index][lane_index]]
        observation = MedicationObservation(
            observation_id=fact.observation_id, raw_value=fact.raw_value,
            lane=record.lane.value, page_review_id=record.page_review_id,
            excerpt=fact.region.excerpt,
            context=json.dumps(fact.context.model_dump(), ensure_ascii=False) if fact.context else None,
            page={key: getattr(record, key) for key in (
                "page_artifact_id", "source_document_version_id", "page_number",
                "page_image_sha256", "clause_pack_sha256")},
        )
        messages = build_component_prompt(observation)
        prefix = f"pair-{pair_index}-lane-{lane_index}"
        save(out / f"{prefix}-request.json", {
            "messages": messages, "max_tokens": args.max_tokens,
            "provider": route.provider, "model": route.model,
            "effort": route.reasoning_effort, "source_record": record.model_dump(mode="json"),
        })
        async with semaphores[lane_index]:
            started = time.monotonic()
            try:
                response = await direct_completion(route, messages, args.max_tokens)
                save(out / f"{prefix}-response.json", {
                    "elapsed_seconds": time.monotonic() - started,
                    "response_model": response.response_model, "response_id": response.response_id,
                    "finish_reason": response.finish_reason, "usage": response.usage,
                    "text": response.text, "product_acceptance": False,
                })
                if response.finish_reason != "stop":
                    raise ValueError("Incomplete response")
                result = validate_extraction(
                    MedicationComponentExtraction.model_validate(extract_json_object(response.text)),
                    observation,
                )
                save(out / f"{prefix}-bound.json", result.model_dump(mode="json"))
                return result
            except Exception as exc:
                save(out / f"{prefix}-failure.json", {
                    "type": type(exc).__name__, "elapsed_seconds": time.monotonic() - started,
                    "status_code": getattr(exc, "status_code", None), "product_acceptance": False,
                })
                return None

    results = await asyncio.gather(*(extract(i, lane) for i in range(len(pairs)) for lane in (0, 1)))
    comparisons = []
    for i in range(len(pairs)):
        left, right = results[i * 2:i * 2 + 2]
        comparisons.append(compare_component_outputs(left, right) if left and right else {
            "observation_ids": pairs[i], "status": "unresolved_extraction_failure",
            "product_acceptance": False, "source_qc_required": True,
        })
    save(out / "comparisons.json", comparisons)
    print(json.dumps({"pairs": len(pairs), "bound_outputs": sum(x is not None for x in results),
                      "product_acceptance": False}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source")
    parser.add_argument("--records", nargs=2)
    parser.add_argument("--database")
    parser.add_argument("--coverage")
    parser.add_argument("--indices", type=int, nargs="+")
    parser.add_argument("--pair", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-tokens", type=int, default=65536)
    parser.add_argument("--main-a-effort", choices=("low", "high"),
                        help="Isolated single-factor effort comparison; no product configuration change")
    asyncio.run(run(parser.parse_args()))
