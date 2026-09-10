"""Retry a frozen isolated normalization job through its product API."""

import argparse
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.v2.app import create_app
from app.agents.verified_evidence_prompt import verified_evidence_strategy
from app.storage.config import resolve_data_paths
from app.workflow.runner import JobRunner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    frozen = json.loads((args.runtime / "controlled-attempt.json").read_text())
    if frozen["normalization_submission"]["job_id"] != args.job:
        raise ValueError("Job differs from the isolated attempt")
    for name, expected in frozen["product_files"].items():
        current = Path("app") / Path(name).relative_to("product-code")
        if hashlib.sha256(current.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Product changed since the attempt: {current}")
    with args.receipt.open("x") as output:
        record = {"job_id": args.job, "claims_complete": False}

        def save():
            output.seek(0)
            json.dump(record, output, ensure_ascii=False, indent=2)
            output.truncate()
            output.flush()

        save()
        app = create_app(data_paths=resolve_data_paths(str(args.runtime)),
                         run_runner=False, semantic_route_preflight=False)
        with TestClient(app) as client:
            payload = app.state.fact_normalization_command_service.job_service.get_job(args.job)["payload"]
            if payload.get("verified_evidence_strategy") != verified_evidence_strategy():
                raise ValueError("Frozen strategy differs; refusing cross-version retry")
            before = client.get(f"/api/v2/jobs/{args.job}")
            before.raise_for_status()
            record["before"] = before.json()
            if record["before"]["state"] != "failed_retryable":
                raise ValueError("Job is not a terminal retryable failure")
            response = client.post(f"/api/v2/jobs/{args.job}/retry")
            record["retry_http_status"] = response.status_code
            record["retry"] = response.json()
            save()
            response.raise_for_status()
            runner = JobRunner(app.state.session_factory, app.state.job_executors,
                               on_cancelled=app.state.job_cancelled_callback,
                               on_failed=app.state.job_failed_callback)
            runner.run_job(args.job)
            status = client.get(f"/api/v2/jobs/{args.job}")
            status.raise_for_status()
            record["after"] = status.json()
            save()
            print(json.dumps(record["after"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
