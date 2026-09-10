"""Synthetic contrast probe using the exact isolated real-page pairing prompt."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import time

from scripts.evaluate_observation_alignment import Proposal, pairing_messages, score_pairs
from app.domain.contracts.page_review import PageReviewLane
from app.llm.page_review_harness import (
    direct_openai_completion, extract_json_object, require_page_reader_routes,
    resolve_route_model,
)


async def run(output, selected=None):
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    def observation(key, field, target="血液", date="2026-08-01", polarity="asserted", value="0 g/L"):
        return {"id": key, "field": field, "value": value,
                "excerpt": f"{date} {target} {field} {value} {polarity}",
                "context": {"target_text": target, "time_text": date, "polarity": polarity}}
    cases = [
        ("different_field", observation("a", "项目甲"), observation("b", "项目乙"), False),
        ("different_date", observation("a", "项目甲"), observation("b", "项目甲", date="2026-08-02"), False),
        ("different_specimen", observation("a", "项目甲"), observation("b", "项目甲", target="尿液"), False),
        ("different_polarity", observation("a", "项目甲"), observation("b", "项目甲", polarity="negated"), False),
        ("equal_zero", observation("a", "项目甲"), observation("b", "项目甲"), True),
        ("unit_conflict", observation("a", "项目甲", value="3 mg/L"),
         observation("b", "项目甲", value="3 g/L"), True),
        ("value_conflict", observation("a", "项目甲", value="3 g/L"),
         observation("b", "项目甲", value="4 g/L"), True),
        ("missing_date", observation("a", "项目甲", date=""),
         observation("b", "项目甲"), False),
        ("missing_target", observation("a", "项目甲", target=""),
         observation("b", "项目甲"), False),
        ("different_event", observation("a", "首次用药", target="药物甲", value="1 mg"),
         observation("b", "末次用药", target="药物甲", value="1 mg"), False),
    ]
    if selected:
        unknown = set(selected) - {case[0] for case in cases}
        if unknown:
            raise ValueError(f"Unknown cases: {sorted(unknown)}")
        cases = [case for case in cases if case[0] in selected]
    frozen = [{"name": name, "source": {"main_A": [a], "main_B": [b]},
               "gold": {"pairs": [{"a": "a", "b": "b"}] if equal else []}}
              for name, a, b, equal in cases]
    (root / "frozen.json").write_text(json.dumps(frozen, ensure_ascii=False, indent=2))
    route = await resolve_route_model(require_page_reader_routes()[PageReviewLane.MAIN_A])
    for case in frozen:
        messages = pairing_messages(case["source"])
        (root / f"{case['name']}-request.json").write_text(json.dumps(messages, ensure_ascii=False, indent=2))
        start = time.monotonic()
        response = await direct_openai_completion(route, messages, 4000)
        result = {"name": case["name"], "raw": response.text,
                  "finish_reason": response.finish_reason, "response_id": response.response_id,
                  "model": response.response_model, "usage": response.usage,
                  "elapsed_seconds": time.monotonic() - start,
                  "messages_sha256": hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode()).hexdigest(),
                  "product_acceptance": False}
        path = root / f"{case['name']}.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        if response.finish_reason != "stop":
            raise ValueError("Incomplete response retained")
        result["score"] = score_pairs(
            Proposal.model_validate(extract_json_object(response.text)),
            Proposal.model_validate(case["gold"]),
        )
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps({"name": case["name"], **result["score"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--cases", help="Comma-separated cases; omit to run all")
    args = parser.parse_args()
    asyncio.run(run(args.output, args.cases.split(",") if args.cases else None))
