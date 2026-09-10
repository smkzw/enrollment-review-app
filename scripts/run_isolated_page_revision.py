"""Run one new product job in a consistent copy; never serve the historical queue."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import time

from fastapi.testclient import TestClient

from app.api.v2.app import create_app
from app.evidence.artifacts import ARTIFACTS_DIRNAME, ArtifactStore
from app.storage.config import resolve_data_paths
from app.workflow.runner import JobRunner
from app.domain.contracts.page_review import PageReviewLane
from app.llm.page_review_harness import require_page_reader_routes
from app.services.page_review_job_service import route_identity


def verify_normalizer_budget(budget):
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 65536:
        raise ValueError("Formal normalization requires at least 65536 output tokens")
    return budget


def verify_frozen_readers(payload, routes):
    readers = {}
    for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B):
        expected = route_identity(routes[lane])
        if expected["max_tokens"] < 65536:
            raise ValueError("Formal comparison requires at least 65536 output tokens")
        if payload["routes"].get(lane.value) != expected:
            raise ValueError("Submitted readers differ from the explicit test configuration")
        readers[lane.value] = expected
    return readers


def verify_page_inputs(root, pages):
    store = ArtifactStore(resolve_data_paths(str(root)))
    for page in pages:
        store.read_by_sha("page_image", page["page_image_sha256"])
    return len(pages)


def normalize_selected_job(client, runner, base, receipt, save):
    response = client.post(base.removesuffix("page-review-jobs") + "fact-normalization-jobs", json={})
    receipt["normalization_submission_status"] = response.status_code
    receipt["normalization_submission"] = response.json()
    save()
    if response.status_code != 201:
        raise RuntimeError("No fresh formal normalization job was created; response retained, no old job run")
    normalization_job = response.json()["job_id"]
    if "normalizer_max_tokens" in receipt:
        from app.storage.repositories import AppendRepository, MODEL_CONFIG_CONFIG
        frozen = client.app.state.fact_normalization_command_service.job_service.get_job(normalization_job)["payload"]
        with client.app.state.session_factory() as session:
            model = AppendRepository(session, MODEL_CONFIG_CONFIG).get(frozen["model_config_id"])
        receipt["frozen_normalizer"] = model.model_dump(mode="json")
        save()
        if verify_normalizer_budget(model.parameters.get("max_tokens")) != receipt["normalizer_max_tokens"]:
            raise RuntimeError("Frozen normalization budget differs; job not run")
    if receipt.get("verified_scope_prompt"):
        from app.agents.verified_evidence_prompt import verified_evidence_strategy
        frozen = client.app.state.fact_normalization_command_service.job_service.get_job(normalization_job)["payload"]
        receipt["verified_evidence_strategy"] = frozen.get("verified_evidence_strategy")
        save()
        if receipt["verified_evidence_strategy"] != verified_evidence_strategy():
            raise RuntimeError("Fresh job did not freeze the requested prompt strategy; job not run")
    while True:
        runner.run_job(normalization_job)
        status = client.get(f"/api/v2/jobs/{normalization_job}")
        status.raise_for_status()
        receipt["normalization_status"] = status.json()
        save()
        if status.json()["state"] == "failed_retryable":
            raise RuntimeError(
                "Normalization failed; receipt retained. Inspect the failure and use the formal retry endpoint."
            )
        if status.json()["state"] in {"completed", "cancelled", "failed_final", "waiting_user"}:
            print(json.dumps(status.json(), ensure_ascii=False), flush=True)
            break
        time.sleep(5)


def run(source, output, source_job, *, normalize=False, normalize_only=False, verified_scope_prompt=False):
    if verified_scope_prompt and not (normalize or normalize_only):
        raise ValueError("Verified scope requires a normalization run")
    from app import config
    normalizer_budget = (verify_normalizer_budget(config.EVIDENCE_NORMALIZER_MAX_TOKENS)
                         if normalize or normalize_only else None)
    routes = require_page_reader_routes()
    verify_frozen_readers({"routes": {lane.value: route_identity(route)
                                     for lane, route in routes.items()}}, routes)
    source = Path(source).resolve()
    output = Path(output).resolve()
    if output == source or source in output.parents or output in source.parents:
        raise ValueError("Source and output must be separate runtime roots")
    database = source / "enrollment-review-v2.sqlite3"
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        row = connection.execute("SELECT state,payload_json FROM jobs WHERE job_id=?", (source_job,)).fetchone()
        if row is None or row[0] != "completed":
            raise ValueError("Source job must be terminal and complete")
        payload = json.loads(row[1])
        if normalize_only:
            verify_frozen_readers(payload, routes)
        verify_page_inputs(source, payload["pages"])
        if connection.execute("SELECT 1 FROM jobs WHERE state IN ('running','cancel_requested') LIMIT 1").fetchone():
            raise ValueError("Source runtime has unresolved active jobs")
        output.mkdir(parents=True, exist_ok=False)
        with sqlite3.connect(output / database.name) as target:
            connection.backup(target)
    shutil.copytree(source / "blobs", output / "blobs")
    shutil.copytree(source / ARTIFACTS_DIRNAME, output / ARTIFACTS_DIRNAME)
    shutil.copytree(Path("app"), output / "product-code",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(__file__, output / "runner.py")
    shutil.copy2("plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md",
                 output / "test-plan.md")
    verified_pages = verify_page_inputs(output, payload["pages"])
    snapshot_hash = hashlib.sha256((output / database.name).read_bytes()).hexdigest()
    authority = payload["authority"]
    receipt = {"source_runtime": str(source), "source_job": source_job,
               "verified_scope_prompt": verified_scope_prompt,
               "copied_database_sha256": snapshot_hash, "historical_queue_started": False,
               "clinical_acceptance": False, "claims_complete": False,
               "verified_page_images": verified_pages,
               "product_files": {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in (output / "product-code").rglob("*") if path.is_file()}}
    if normalizer_budget is not None:
        receipt["normalizer_max_tokens"] = normalizer_budget

    def save():
        (output / "controlled-attempt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2))

    save()
    app = create_app(data_paths=resolve_data_paths(str(output)), run_runner=False,
                     semantic_route_preflight=False)
    base = (f"/api/v2/subjects/{authority['subject_id']}/review-episodes/"
            f"{authority['review_episode_id']}/page-review-jobs")
    with TestClient(app) as client:
        app.state.fact_normalization_command_service.verified_scope_prompt = verified_scope_prompt
        if normalize_only:
            receipt["reused_completed_page_job"] = source_job
            save()
            runner = JobRunner(
                app.state.session_factory, app.state.job_executors,
                on_cancelled=app.state.job_cancelled_callback,
                on_failed=app.state.job_failed_callback,
            )
            normalize_selected_job(client, runner, base, receipt, save)
            return
        response = client.post(base, json={})
        if response.status_code != 201:
            receipt.update(submission_status=response.status_code)
            save()
            raise RuntimeError("New isolated submission failed; no historical job was run")
        job_id = response.json()["job_id"]
        receipt.update(job_id=job_id, submitted=response.json())
        save()
        with sqlite3.connect((output / database.name).as_uri() + "?mode=ro", uri=True) as connection:
            submitted_payload = json.loads(connection.execute(
                "SELECT payload_json FROM jobs WHERE job_id=?", (job_id,)).fetchone()[0])
        receipt["verified_readers"] = verify_frozen_readers(submitted_payload, routes)
        save()
        print(json.dumps({"job_id": job_id, "output": str(output)}), flush=True)
        runner = JobRunner(
            app.state.session_factory, app.state.job_executors,
            on_cancelled=app.state.job_cancelled_callback,
            on_failed=app.state.job_failed_callback,
        )
        while True:
            runner.run_job(job_id)
            status = client.get(base + "/" + job_id)
            status.raise_for_status()
            receipt["status"] = status.json()
            save()
            if status.json()["state"] in {"completed", "cancelled", "failed_final", "waiting_user"}:
                print(json.dumps(status.json(), ensure_ascii=False), flush=True)
                break
            time.sleep(5)
        if normalize and receipt["status"]["state"] == "completed":
            normalize_selected_job(client, runner, base, receipt, save)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-job", required=True)
    parser.add_argument("--normalize", action="store_true", help="Submit normalization through the formal API after page review")
    parser.add_argument("--normalize-only", action="store_true", help="Reuse matching completed page reads in a fresh isolated normalization attempt")
    parser.add_argument("--verified-scope-prompt", action="store_true", help="Freeze the verified-observation prompt for the new normalization job")
    args = parser.parse_args()
    run(args.source, args.output, args.source_job, normalize=args.normalize,
        normalize_only=args.normalize_only, verified_scope_prompt=args.verified_scope_prompt)
