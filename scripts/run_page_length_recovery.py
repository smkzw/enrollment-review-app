"""Run the explicitly approved single-lane recovery through the product API."""

import argparse
import json
from pathlib import Path
import sqlite3
import time

from fastapi.testclient import TestClient

from app.api.v2.app import create_app
from app.storage.config import resolve_data_paths
from app.workflow.runner import JobRunner


def run(runtime, predecessor):
    root = Path(runtime).resolve()
    receipt_path = root / "length-recovery-48000.json"
    if receipt_path.exists():
        raise ValueError("Recovery receipt already exists; inspect it instead of submitting again")
    with sqlite3.connect((root / "enrollment-review-v2.sqlite3").as_uri() + "?mode=ro", uri=True) as db:
        if db.execute("SELECT 1 FROM jobs WHERE state IN ('running','cancel_requested') LIMIT 1").fetchone():
            raise ValueError("Runtime contains unresolved active jobs")
        row = db.execute("SELECT state,payload_json FROM jobs WHERE job_id=?", (predecessor,)).fetchone()
        if row is None or row[0] != "completed":
            raise ValueError("Predecessor is not complete")
        authority = json.loads(row[1])["authority"]
    app = create_app(data_paths=resolve_data_paths(str(root)), run_runner=False, semantic_route_preflight=False)
    base = f"/api/v2/subjects/{authority['subject_id']}/review-episodes/{authority['review_episode_id']}/page-review-jobs"
    receipt = {"predecessor_job_id": predecessor, "budget_scope": "combined_generation",
               "max_tokens": 48000, "length_retry": False, "claims_complete": False}

    def save():
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2))

    with TestClient(app) as client:
        response = client.post(base, json={"predecessor_job_id": predecessor, "single_length_recovery": True})
        if response.status_code != 201:
            raise RuntimeError(f"Submission rejected: {response.status_code}; no job executed")
        job_id = response.json()["job_id"]
        receipt["job_id"] = job_id
        save()
        print(json.dumps(receipt), flush=True)
        runner = JobRunner(app.state.session_factory, app.state.job_executors)
        while True:
            runner.run_job(job_id)
            status = client.get(base + "/" + job_id)
            status.raise_for_status()
            receipt["status"] = status.json()
            save()
            if status.json()["state"] in {"completed", "cancelled", "failed_final", "waiting_user"}:
                print(json.dumps(receipt, ensure_ascii=False), flush=True)
                return
            time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--predecessor", required=True)
    args = parser.parse_args()
    run(args.runtime, args.predecessor)
