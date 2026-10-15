"""WP08 singleton replay state capture: read-only snapshot of the C/B-chain state.

Captures the projection hash, active pointer, manifest identity, fact count,
document inventory, and judgment-search scope hashes so each replay step can
diff what actually recomputed and prove untouched artifacts stayed identical.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests


def capture(base_url: str, subject_id: str, episode_id: str) -> dict:
    from app.config import load_enrollment_env_file
    load_enrollment_env_file()
    from app.services.evidence_app_bootstrap import resolve_data_paths, upgrade_or_fail

    _, _engine, session_factory = upgrade_or_fail(resolve_data_paths())
    r = requests.get(
        f"{base_url}/api/v2/subjects/{subject_id}/review-episodes/{episode_id}/eligibility-review",
        timeout=300,
    )
    r.raise_for_status()
    projection = r.json()
    clauses_canon = json.dumps(projection["clauses"], sort_keys=True, ensure_ascii=False)

    state: dict = {
        "captured_at": __import__("datetime").datetime.now(
            __import__("datetime").UTC
        ).isoformat(),
        "subject_id": subject_id,
        "review_episode_id": episode_id,
        "projection_clause_count": len(projection["clauses"]),
        "projection_clauses_sha256": hashlib.sha256(clauses_canon.encode()).hexdigest(),
        "decision_counts": {},
        "documents": [],
    }
    for clause in projection["clauses"]:
        state["decision_counts"][clause["decision"]] = (
            state["decision_counts"].get(clause["decision"], 0) + 1
        )

    with session_factory() as session:
        from sqlalchemy import text

        row = session.execute(
            text(
                "SELECT active_evidence_snapshot_id, active_evidence_processing_revision_id "
                "FROM review_episodes WHERE review_episode_id=:e"
            ),
            {"e": episode_id},
        ).fetchone()
        state["active_snapshot_id"], state["active_revision_id"] = row
        rev = session.execute(
            text(
                "SELECT manifest_sha256, status, revision_kind FROM evidence_processing_revisions "
                "WHERE evidence_processing_revision_id=:r"
            ),
            {"r": state["active_revision_id"]},
        ).fetchone()
        state["manifest_sha256"], state["revision_status"], state["revision_kind"] = rev
        state["manifest_page_count"] = session.execute(
            text(
                "SELECT count(*) FROM evidence_processing_revision_pages "
                "WHERE revision_id=:r"
            ),
            {"r": state["active_revision_id"]},
        ).scalar()

        docs = session.execute(
            text(
                "SELECT payload_json FROM evidence_upload_items ORDER BY created_at"
            )
        ).fetchall()
        seen = set()
        for (payload_json,) in docs:
            item = json.loads(payload_json)
            name = item.get("file_name")
            if name and name not in seen:
                seen.add(name)
                state["documents"].append(
                    {
                        "file_name": name,
                        "existing_version_id": item.get("existing_version_id"),
                    }
                )

        tables = [
            "clinical_facts_v2",
            "evidence_expectations_v2",
            "fact_corrections",
            "fact_correction_commits",
            "source_document_metadata_revisions",
            "fact_rule_links_v2",
            "review_runs",
        ]
        for table in tables:
            try:
                state[f"count_{table}"] = session.execute(
                    text(f"SELECT count(*) FROM {table}")
                ).scalar()
            except Exception:
                state[f"count_{table}"] = None
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8902")
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--episode-id", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    state = capture(args.base_url, args.subject_id, args.episode_id)
    Path(args.out).write_text(
        json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps(state, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
