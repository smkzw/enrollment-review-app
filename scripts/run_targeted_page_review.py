"""Submit one isolated two-round auxiliary review via the formal product API."""

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from app.api.v2.app import create_app
from app.storage.config import resolve_data_paths
from app.workflow.runner import JobRunner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--original-job", required=True)
    parser.add_argument("--page-index", type=int, required=True)
    parser.add_argument("--expected-image-sha256")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists():
        raise ValueError("Existing receipt must be inspected, not overwritten")
    root = args.runtime.resolve()
    with sqlite3.connect((root / "enrollment-review-v2.sqlite3").as_uri() + "?mode=ro", uri=True) as db:
        if db.execute("SELECT 1 FROM jobs WHERE state IN ('running','cancel_requested') LIMIT 1").fetchone():
            raise ValueError("Unresolved active job in isolated runtime")
        row = db.execute("SELECT state,payload_json FROM jobs WHERE job_id=?", (args.original_job,)).fetchone()
        if row is None or row[0] != "completed":
            raise ValueError("Original review is not complete")
        authority = json.loads(row[1])["authority"]
        source = json.loads(row[1])
        if args.expected_image_sha256 and source["pages"][args.page_index]["page_image_sha256"] != args.expected_image_sha256:
            raise ValueError("Selected page does not match the expected source image")
    app = create_app(data_paths=resolve_data_paths(str(root)), run_runner=False, semantic_route_preflight=False)
    base = f"/api/v2/subjects/{authority['subject_id']}/review-episodes/{authority['review_episode_id']}/targeted-review-jobs"
    with TestClient(app) as client:
        response = client.post(base, json={"original_job_id": args.original_job, "page_index": args.page_index})
        if response.status_code != 201:
            args.receipt.write_text(json.dumps({"submission_status": response.status_code,
                "error": response.json(), "original_job": args.original_job,
                "page_index": args.page_index, "claims_complete": False}, ensure_ascii=False, indent=2))
            raise RuntimeError(f"Submission status {response.status_code}; no existing job executed")
        receipt = {"submission": response.json(), "claims_complete": False,
                   "app_source_sha256": {
                       str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in sorted(Path("app").rglob("*.py"))
                   },
                   "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
        job_id = response.json()["job_id"]
        print(json.dumps({"submission": receipt["submission"], "claims_complete": False}), flush=True)
        JobRunner(app.state.session_factory, app.state.job_executors).run_job(job_id)
        status = client.get(base + "/" + job_id)
        status.raise_for_status()
        receipt["status"] = status.json()
        args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
        print(json.dumps({"status": receipt["status"], "claims_complete": False}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
