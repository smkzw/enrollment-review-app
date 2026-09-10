"""Read-only frozen-run provenance and input-size audit; no model invocation."""

import argparse
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agents.evidence_normalizer import _model_input_payload
from app.domain.contracts.facts import FactAuthority
from app.projections.page_review_sources import validate_accepted_candidate_sources
from app.services.fact_normalization_executor import _build_input
from app.storage.fact_repositories import FactNormalizationRunRepository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    uri = args.database.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    payload = json.loads(connection.execute(
        "SELECT payload_json FROM jobs WHERE job_id=?", (args.job_id,)
    ).fetchone()[0])
    engine = create_engine("sqlite://", creator=lambda: sqlite3.connect(uri, uri=True))
    results = []
    with Session(engine) as session:
        created = FactNormalizationRunRepository(session).get(payload["run_id"]).created_at
        for call in payload["calls"]:
            evidence = _build_input(session, FactAuthority.model_validate(payload["authority"]),
                                    payload["run_id"], call, max_pages_per_call=payload["max_pages_per_call"],
                                    created_at=created,
                                    page_review_coverage_id=payload["page_review_coverage_id"],
                                    include_visual_sources=payload.get("visual_source_policy") == "page-review-visual-sources/v1")
            projected = _model_input_payload(evidence)
            pages = projected["page_review"]["accepted_pages"]
            rows = connection.execute(
                "SELECT payload_json FROM fact_normalization_candidates WHERE call_id=?", (call["call_id"],)
            ).fetchall()
            candidates = [SimpleNamespace(**json.loads(row[0])) for row in rows]
            facts = [item for item in candidates if hasattr(item, "source_observation_refs")]
            issue = None
            try:
                validate_accepted_candidate_sources(SimpleNamespace(fact_candidates=facts), evidence.page_review,
                                                    locator_inputs=evidence.available_locators)
            except ValueError as exc:
                issue = str(exc)
            results.append({"call_id": call["call_id"], "pages": call["page_numbers"],
                            "component_chars": {key: len(json.dumps(value, ensure_ascii=False))
                                                for key, value in projected.items()},
                            "input_chars": len(json.dumps(projected, ensure_ascii=False)),
                            "accepted_observations": sum(len(p["accepted_observations"]) for p in pages),
                            "pending_observations": sum(
                                len(group["observations"]) for p in pages
                                for group in p["pending_observation_groups"]),
                            "persisted_candidates": len(candidates), "source_issue": issue})
    connection.close()
    engine.dispose()
    report = json.dumps({"job_id": args.job_id, "read_only": True, "calls": results}, ensure_ascii=False, indent=2)
    if args.output:
        with args.output.open("x") as stream:
            stream.write(report + "\n")
    print(report)


if __name__ == "__main__":
    main()
