"""Replay persisted responses through product validation, without model calls."""

import argparse
import asyncio
import json
from pathlib import Path
import sqlite3

from pydantic import ValidationError

from app.domain.contracts.clause_pack import ClausePack
from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.page_review_context import PageReviewContext
from app.evidence.artifacts import ArtifactStore
from app.llm.independent_vlm import PageVisionInput
from app.llm.page_review_harness import PageCompletion, PageReviewInput, read_page, require_page_reader_routes
from app.storage.config import resolve_data_paths


def run(root, job):
    root = Path(root).resolve()
    with sqlite3.connect((root / "enrollment-review-v2.sqlite3").as_uri() + "?mode=ro", uri=True) as connection:
        payload = json.loads(connection.execute("SELECT payload_json FROM jobs WHERE job_id=?", (job,)).fetchone()[0])
        rows = connection.execute("SELECT step_id,payload_json FROM job_checkpoints WHERE job_id=? ORDER BY created_at", (job,)).fetchall()
    store = ArtifactStore(resolve_data_paths(str(root)))
    routes = require_page_reader_routes()
    report = []
    for step, raw in rows:
        receipt = json.loads(raw)
        if receipt.get("lane_failure", {}).get("failure_kind") != "schema":
            continue
        page = payload["pages"][int(step.split(":")[1])]
        lane = PageReviewLane(step.split(":")[2])
        attempt = receipt["response_attempts"][-1]
        body = store.read_by_sha("raw_response", attempt["response_sha256"]).decode()

        async def replay(*_args):
            return PageCompletion(text=body, finish_reason=attempt["finish_reason"], usage=attempt.get("usage"))

        page_input = PageReviewInput(**page, review_context=PageReviewContext.model_validate(payload["review_context"]),
            page=PageVisionInput(source_ref=page["page_artifact_id"], page_ordinal=page["page_number"],
                                image_bytes=store.read_by_sha("page_image", page["page_image_sha256"])))
        try:
            asyncio.run(read_page(routes[lane], page_input, ClausePack.model_validate(payload["clause_pack"]), completion=replay))
            errors = []
        except Exception as exc:
            cause = exc.__cause__
            errors = ([{"loc": list(item["loc"]), "type": item["type"]} for item in cause.errors()]
                      if isinstance(cause, ValidationError) else [{"error_type": type(exc).__name__, "detail": str(exc)[:120]}])
        report.append({"step": step, "response_sha256": attempt["response_sha256"], "errors": errors})
    target = root / "schema-failure-replay.json"
    if target.exists():
        raise ValueError("Diagnostic output already exists")
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    run(args.root, args.job)
