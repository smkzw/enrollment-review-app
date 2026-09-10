"""Read-only source replay through the current product normalizer, not a publication."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agents.evidence_normalizer import (
    DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE, EvidenceNormalizerRunner,
    build_evidence_normalizer_prompt,
    _model_input_payload,
)
from app.projections.normalizer_reference_aliases import NormalizerReferenceAliases
from app.agents.verified_evidence_prompt import VERIFIED_EVIDENCE_PROMPT_VERSION
from app.agents.deepseek_evidence_normalizer_transport import evidence_normalizer_transport_from_model_config
from app.domain.contracts.facts import FactAuthority
from app.projections.pending_observations_report import pending_retention_items
from app.services.fact_normalization_executor import _build_input, AppendRepository, MODEL_CONFIG_CONFIG
from app.storage.fact_repositories import FactNormalizationRunRepository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--call", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pending-details-retained", action="store_true")
    parser.add_argument("--compact-references", action="store_true")
    parser.add_argument("--verified-scope-prompt", action="store_true")
    args = parser.parse_args()
    uri = args.database.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        row = db.execute("SELECT payload_json FROM jobs WHERE job_id=?", (args.job,)).fetchone()
        if row is None:
            raise ValueError("Source job not found")
        payload = json.loads(row[0])
    call = next(item for item in payload["calls"] if item["call_id"] == args.call)
    engine = create_engine("sqlite://", creator=lambda: sqlite3.connect(uri, uri=True))
    try:
        with Session(engine) as session:
            run = FactNormalizationRunRepository(session).get(payload["run_id"])
            model = AppendRepository(session, MODEL_CONFIG_CONFIG).get(payload["model_config_id"])
            if model.provider != "zhipu-coding-plan" or model.model.lower() != "glm-5.3-flash":
                raise ValueError("This probe only permits the current GLM product normalizer")
            evidence = _build_input(session, FactAuthority.model_validate(payload["authority"]),
                payload["run_id"], call, max_pages_per_call=payload["max_pages_per_call"],
                created_at=run.created_at, page_review_coverage_id=payload["page_review_coverage_id"],
                include_visual_sources=payload.get("visual_source_policy") == "page-review-visual-sources/v1")
    finally:
        engine.dispose()
    args.output.mkdir(parents=True, exist_ok=False)

    def save(name, value):
        with (args.output / name).open("x", encoding="utf-8") as file:
            json.dump(value, file, ensure_ascii=False, indent=2)

    shutil.copytree("app", args.output / "product-code", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(__file__, args.output / "runner.py")
    save("input.json", evidence.model_dump(mode="json"))
    aliases = (NormalizerReferenceAliases.from_payload(_model_input_payload(evidence,
               pending_details_retained=args.pending_details_retained)) if args.compact_references else None)
    if aliases is not None:
        save("reference-aliases.json", aliases.aliases)
    prompt = build_evidence_normalizer_prompt(evidence, prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
                                            pending_details_retained=args.pending_details_retained,
                                            reference_aliases=aliases,
                                            verified_scope_prompt=args.verified_scope_prompt)
    save("request.json", {"prompt": prompt, "model_config": model.model_dump(mode="json"),
         "source_job": args.job, "source_call": args.call, "clinical_acceptance": False,
         "publication": False, "pending_details_retained": args.pending_details_retained,
         "compact_references": args.compact_references,
         "verified_scope_prompt": args.verified_scope_prompt,
         "verified_scope_prompt_version": VERIFIED_EVIDENCE_PROMPT_VERSION if args.verified_scope_prompt else None,
         "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()})
    save("retained-pending.json", [item.model_dump(mode="json") for item in pending_retention_items(evidence)])
    receipts = []

    def receipt(value):
        save(f"receipt-{len(receipts):02d}.json", value)
        receipts.append(value)

    transport = evidence_normalizer_transport_from_model_config(model, receipt_callback=receipt)
    start = time.monotonic()
    result = EvidenceNormalizerRunner(max_transport_retries=0, max_schema_repairs=2).run(
        evidence, transport, prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
        pending_details_retained=args.pending_details_retained, compact_references=args.compact_references,
        verified_scope_prompt=args.verified_scope_prompt)
    elapsed = time.monotonic() - start
    save("result.json", result.model_dump(mode="json"))
    summary = {"elapsed_seconds": elapsed, "usable_output": result.final_output is not None,
               "attempts": len(result.attempts), "clinical_acceptance": False, "publication": False}
    save("summary.json", summary)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
