"""Read one explicitly selected source image with the product harness only."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path

from app.domain.contracts.clause_pack import ClausePack
from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.page_review_context import PageReviewContext
from app.domain.contracts.page_review_focus import PageReviewFocus
from app.llm.independent_vlm import PageVisionInput
from app.llm.page_review_harness import (
    PAGE_REVIEW_PROMPT_VERSION,
    PageReviewInput, direct_completion, preflight_page_reader_routes,
    require_page_reader_routes, read_page,
)
from app.projections.clause_pack import verify_clause_pack
from app.services.page_review_execution import review_page


def load_input(image: Path, expected_sha256: str, page_number: int, pack_path: Path):
    data = image.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise ValueError("Source image hash mismatch")
    media_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(image.suffix.lower())
    if media_type is None:
        raise ValueError("Expected PNG or JPEG source image")
    pack = ClausePack.model_validate_json(pack_path.read_text(encoding="utf-8"))
    verify_clause_pack(pack)
    # Diagnostic identity is deliberately separate from any clinical repository.
    page = PageReviewInput(
        page_artifact_id=f"diagnostic-page:{digest}",
        source_document_version_id=f"diagnostic-image:{digest}",
        page_number=page_number, page_image_sha256=digest,
        page=PageVisionInput(source_ref=f"diagnostic-page:{digest}",
                             page_ordinal=page_number, image_bytes=data, media_type=media_type),
    )
    return page, pack


def without_clause_context(messages):
    """Diagnostic ablation only; never used by the product job executor."""
    copied = json.loads(json.dumps(messages))
    for message in copied:
        if message["role"] != "user":
            continue
        for part in message["content"]:
            if part["type"] == "text":
                payload = json.loads(part["text"])
                payload.pop("clause_pack", None)
                part["text"] = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return copied


async def run(args) -> None:
    focus = None
    if args.frozen_input:
        if not args.targets or args.page_index is None or args.without_clause_context or args.image_detail:
            raise ValueError("Frozen focus requires page index and targets, without ablation")
        payload = json.loads(args.frozen_input.read_text())
        if not 0 <= args.page_index < len(payload["pages"]):
            raise ValueError("Frozen page index outside source pages")
        if any((args.image, args.sha256, args.page_number, args.clause_pack)):
            raise ValueError("Do not mix frozen and standalone source identities")
        metadata = payload["pages"][args.page_index]
        image_path = args.frozen_input.parent / "pages" / metadata["page_image_sha256"]
        page = PageReviewInput(**metadata,
            review_context=PageReviewContext.model_validate(payload["review_context"]),
            page=PageVisionInput(source_ref=metadata["page_artifact_id"],
                page_ordinal=metadata["page_number"], image_bytes=image_path.read_bytes()))
        pack = ClausePack.model_validate(payload["clause_pack"])
        verify_clause_pack(pack)
        focus = PageReviewFocus(original_reconciliation_id="isolated-diagnostic-not-persisted",
            page_image_sha256=page.page_image_sha256,
            review_episode_id=page.review_context.review_episode_id, round_number=1,
            targets=tuple(args.targets))
    else:
        if not all((args.image, args.sha256, args.page_number, args.clause_pack)) or args.targets:
            raise ValueError("Require image identity and ClausePack, or a frozen focused input")
        page, pack = load_input(args.image, args.sha256, args.page_number, args.clause_pack)
        image_path = args.image
    args.output.mkdir(parents=True, exist_ok=False)

    def save(name, value):
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    save("input.json", {"diagnostic_only": True, "clinical_acceptance": False,
         "without_clause_context": args.without_clause_context,
         "image_detail": args.image_detail,
         "prompt_versions": {"main": PAGE_REVIEW_PROMPT_VERSION},
         "image": str(image_path.resolve()), "image_sha256": page.page_image_sha256,
         "focus": focus.model_dump(mode="json") if focus else None,
         "page_number": page.page_number, "clause_pack": pack.model_dump(mode="json")})
    root = Path(__file__).resolve().parents[1]
    source_paths = [Path(__file__).resolve(), root / "app/llm/page_review_harness.py",
                    root / "app/domain/contracts/page_review_focus.py"]
    if args.frozen_input:
        source_paths.append(args.frozen_input.resolve())
    save("source-hashes.json", {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in source_paths})
    receipts = []

    async def completion(route, messages, budget):
        if args.without_clause_context:
            messages = without_clause_context(messages)
        if args.image_detail:
            messages = json.loads(json.dumps(messages))
            for message in messages:
                if message["role"] == "user":
                    for part in message["content"]:
                        if part["type"] == "image_url":
                            part["image_url"]["detail"] = args.image_detail
        receipt = {"lane": route.lane.value, "model": route.model, "budget": budget,
                   "effort": route.reasoning_effort,
                   "messages_sha256": hashlib.sha256(json.dumps(messages, ensure_ascii=False,
                       sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()}
        started = time.monotonic()
        save(f"request-{route.lane.value}-{len(receipts)}.json", {
            "messages": messages, "model": route.model, "effort": route.reasoning_effort,
            "budget": budget, "provider": route.provider,
        })
        try:
            result = await direct_completion(route, messages, budget)
            receipt.update(finish_reason=result.finish_reason, usage=result.usage,
                           response_model=result.response_model, response_id=result.response_id)
            save(f"response-{route.lane.value}-{len(receipts)}.json", {"text": result.text})
            return result
        except Exception as exc:
            receipt.update(error_type=type(exc).__name__, status_code=getattr(exc, "status_code", None))
            raise
        finally:
            receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
            receipts.append(receipt)
            save("receipts.json", receipts)

    try:
        routes = await preflight_page_reader_routes(require_page_reader_routes())
        if focus:
            lanes = (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)
            records = await asyncio.gather(*(
                read_page(replace(routes[lane], reasoning_effort="high"), page, pack,
                          completion=completion, review_focus=focus) for lane in lanes
            ), return_exceptions=True)
            save("result.json", {"diagnostic_only": True, "clinical_acceptance": False,
                 "records": [r.model_dump(mode="json") for r in records if not isinstance(r, BaseException)],
                 "failures": [type(r).__name__ for r in records if isinstance(r, BaseException)],
                 "focus": focus.model_dump(mode="json")})
            print(json.dumps({"records": sum(not isinstance(r, BaseException) for r in records),
                              "clinical_acceptance": False}), flush=True)
            return
        result = await review_page(routes, page, pack, completion=completion)
    except Exception as exc:
        save("failure.json", {"error_type": type(exc).__name__,
                              "failure_kind": getattr(exc, "failure_kind", None)})
        raise SystemExit("Diagnostic failed; see redacted failure.json") from None
    save("result.json", {"diagnostic_only": True, "clinical_acceptance": False,
         "coverage": result.coverage_entry.model_dump(mode="json"),
         "records": [record.model_dump(mode="json") for record in result.records],
         "reconciliation": result.reconciliation.model_dump(mode="json") if result.reconciliation else None})
    print(json.dumps({"output": str(args.output), "records": len(result.records),
                      "disposition": result.coverage_entry.disposition.value}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path)
    parser.add_argument("--sha256")
    parser.add_argument("--page-number", type=int)
    parser.add_argument("--clause-pack", type=Path)
    parser.add_argument("--frozen-input", type=Path)
    parser.add_argument("--page-index", type=int)
    parser.add_argument("--targets", nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--without-clause-context", action="store_true",
                        help="Diagnostic ablation only; not a product review")
    parser.add_argument("--image-detail", choices=("high", "low", "auto"))
    asyncio.run(run(parser.parse_args()))
