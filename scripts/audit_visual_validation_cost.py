"""Compare full and batched source verification on a read-only frozen database."""

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from time import perf_counter

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord
from app.storage.evidence_locator_repositories import EvidenceLocatorRepository
from app.storage.page_review_visual_locator_validation import VisualLocatorBatchContext, verify_visual_locator


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    uri = args.database.resolve().as_uri() + "?mode=ro"
    engine = create_engine("sqlite://", creator=lambda: sqlite3.connect(uri, uri=True))
    results = []
    for use_batch in (False, True):
        counter = [0]

        def count(*unused):
            counter[0] += 1

        with Session(engine) as session:
            rows = session.scalars(select(EvidenceLocatorArtifactRecord).where(
                EvidenceLocatorArtifactRecord.source_layer == "page_review_visual"
            ).order_by(EvidenceLocatorArtifactRecord.locator_id).limit(args.limit)).all()
            artifacts = [EvidenceLocatorRepository._decode(row) for row in rows]
            batch = VisualLocatorBatchContext(session) if use_batch else None
            event.listen(engine, "before_cursor_execute", count)
            start = perf_counter()
            verdicts = []
            try:
                for artifact in artifacts:
                    coverage = verify_visual_locator(session, artifact, batch=batch)
                    verdicts.append(hashlib.sha256(coverage.model_dump_json().encode()).hexdigest())
            finally:
                event.remove(engine, "before_cursor_execute", count)
            results.append({"batch": use_batch, "seconds": perf_counter() - start,
                            "queries": counter[0], "locator_ids": [a.locator_id for a in artifacts],
                            "coverage_hashes": verdicts})
    engine.dispose()
    assert results[0]["locator_ids"] == results[1]["locator_ids"]
    assert results[0]["coverage_hashes"] == results[1]["coverage_hashes"]
    report = {"read_only": True, "database": str(args.database), "results": results,
              "clinical_acceptance": False}
    with args.output.open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
