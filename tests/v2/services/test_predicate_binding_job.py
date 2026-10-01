"""Real JobRunner, synthetic frozen input, no clinical/model acceptance."""
import json
import asyncio
import threading

import pytest

from app.domain.contracts.page_review import PageReviewLane
from app.evidence.artifacts import ArtifactStore
from app.llm.page_review_harness import PageCompletion
from app.services.predicate_binding_job import (
    JOB_TYPE, PredicateBindingJobExecutor, enqueue_predicate_candidates,
)
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner
from tests.v2.llm.test_predicate_binding_candidates import _case, _route


@pytest.mark.parametrize("fail_b", [False, True])
@pytest.mark.parametrize("repair_a", [False, True])
def test_persistent_candidates_never_become_accepted(
        session_factory, data_paths, monkeypatch, fail_b, repair_a):
    frozen, payload = _case()
    monkeypatch.setattr("app.services.predicate_binding_job.build_predicate_binding_frozen_input",
                        lambda *args, **kwargs: frozen)
    routes = {lane: _route(lane=lane) for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)}
    calls = []
    raw = json.dumps(payload)
    final_array = raw.rfind("]")
    repaired_input = raw[:final_array - 1] + raw[final_array:]
    async def complete(route, messages, budget):
        calls.append(route.lane)
        return PageCompletion("invalid" if fail_b and route.lane == PageReviewLane.MAIN_B
                              else repaired_input if repair_a and route.lane == PageReviewLane.MAIN_A
                              else raw, "stop", {})
    artifact_store = ArtifactStore(data_paths)
    job = enqueue_predicate_candidates(session_factory, review_episode_id="synthetic",
                                       component_ids=["component-a"], routes=routes)
    same = enqueue_predicate_candidates(session_factory, review_episode_id="synthetic",
                                        component_ids=["component-a"], routes=routes)
    assert same.job_id == job.job_id
    executor = PredicateBindingJobExecutor(session_factory, artifact_store, routes, completion=complete)
    runner = JobRunner(session_factory, {JOB_TYPE: executor})
    assert runner.run_job(job.job_id)
    assert not runner.run_job(job.job_id)
    assert len(calls) == 2
    assert set(calls) == {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}
    with session_factory() as session:
        store = JobStore(session)
        found = store.get_last_checkpoint(job.job_id, "summary")
        if fail_b:
            assert found is None
            assert store.get_job(job.job_id).state == "failed_final"
        else:
            assert found[1]["accepted"] is False
            assert found[1]["status"] == "unverified"
            from app.services.binding_qualification_support import verify_completed_candidate_comparison
            assert verify_completed_candidate_comparison(session, artifact_store, job.job_id)["comparison"]["accepted"] is False
        reads = {lane.value: store.get_last_checkpoint(job.job_id, f"read:{lane.value}")[1] for lane in routes}
        from scripts.run_predicate_binding_probe import inspect_saved_reads
        audit = inspect_saved_reads(session, artifact_store, job.job_id)
        assert audit["accepted"] is False
        assert len(audit["reads"]) == 2
        assert audit["reads"][1]["status"] == ("incomplete" if fail_b else "unverified")
        assert audit["reads"][1]["candidate_count"] == (
            None if fail_b else sum(len(item["candidates"]) for item in payload["results"]))
    for lane, read in reads.items():
        assert read["accepted"] is False
        receipt = json.loads(artifact_store.read_by_sha("raw_response", read["receipt_sha256s"][0]))
        response = json.loads(artifact_store.read_by_sha("raw_response", receipt["response_sha256"]))
        assert response["text"] == ("invalid" if fail_b and lane == "main-B"
                                    else repaired_input if repair_a and lane == "main-A" else raw)
        if read.get("candidate_sha256"):
            artifact = json.loads(artifact_store.read_by_sha("raw_response", read["candidate_sha256"]))
            assert artifact["format_repair"] == (
                "predicate-candidate-trailing-closure/v1" if repair_a and lane == "main-A" else None
            )
        request = json.loads(artifact_store.read_by_sha("raw_response", receipt["request_sha256"]))
        assert request["max_tokens"] == 65536
        assert "api_key" not in request


def test_changed_input_blocks_call(session_factory, data_paths, monkeypatch):
    frozen, _ = _case()
    current = [frozen]
    monkeypatch.setattr("app.services.predicate_binding_job.build_predicate_binding_frozen_input",
                        lambda *args, **kwargs: current[0])
    routes = {lane: _route(lane=lane) for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)}
    job = enqueue_predicate_candidates(session_factory, review_episode_id="synthetic",
                                       component_ids=["component-a"], routes=routes)
    current[0] = _case(source=None)[0]
    async def complete(*args):
        pytest.fail("must reject before calling model")
    runner = JobRunner(session_factory, {JOB_TYPE: PredicateBindingJobExecutor(
        session_factory, ArtifactStore(data_paths), routes, completion=complete,
    )})
    assert runner.run_job(job.job_id)
    with session_factory() as session:
        assert JobStore(session).get_last_checkpoint(job.job_id, "summary") is None
        assert JobStore(session).get_job(job.job_id).state == "failed_final"


def test_cancellation_preserves_interrupted_request_receipt(session_factory, data_paths, monkeypatch):
    frozen, _ = _case()
    monkeypatch.setattr("app.services.predicate_binding_job.build_predicate_binding_frozen_input",
                        lambda *args, **kwargs: frozen)
    routes = {lane: _route(lane=lane) for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)}
    job = enqueue_predicate_candidates(session_factory, review_episode_id="synthetic",
                                      component_ids=["component-a"], routes=routes)
    async def complete(*args):
        with session_factory() as session, session.begin():
            JobStore(session).request_cancel(job.job_id)
        await asyncio.sleep(30)
        pytest.fail("cancelled request must not finish normally")
    artifacts = ArtifactStore(data_paths)
    runner = JobRunner(session_factory, {JOB_TYPE: PredicateBindingJobExecutor(
        session_factory, artifacts, routes, completion=complete)})
    assert runner.run_job(job.job_id)
    assert not runner.run_job(job.job_id)
    with session_factory() as session:
        store = JobStore(session)
        assert store.get_job(job.job_id).state == "cancelled"
        assert store.get_last_checkpoint(job.job_id, "summary") is None
        read = store.get_last_checkpoint(job.job_id, "read:main-A")[1]
        from scripts.run_predicate_binding_probe import inspect_saved_reads
        audit = inspect_saved_reads(session, artifacts, job.job_id)
        assert audit["reads"][0]["calls"][0]["usage"] is None
        assert audit["reads"][0]["calls"][0]["finish_reason"] is None
        assert audit["reads"][0]["candidate_count"] is None
        assert audit["reads"][1]["status"] in {"not_recorded", "incomplete"}
    assert read["accepted"] is False
    assert read["status"] == "incomplete"
    receipt = json.loads(artifacts.read_by_sha("raw_response", read["receipt_sha256s"][0]))
    assert receipt["error_type"] == "CancelledError"
    assert "response_sha256" not in receipt
    request = json.loads(artifacts.read_by_sha("raw_response", receipt["request_sha256"]))
    assert request["max_tokens"] == 65536


def test_probe_writes_only_new_copy(data_paths, session_factory, tmp_path, monkeypatch):
    from scripts import run_predicate_binding_probe as probe
    from sqlalchemy import text
    frozen, payload = _case()
    routes = {lane: _route(lane=lane) for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)}
    monkeypatch.setattr("app.services.predicate_binding_job.build_predicate_binding_frozen_input",
                        lambda *args, **kwargs: frozen)
    monkeypatch.setattr(probe, "require_page_reader_routes", lambda: routes)
    async def preflight(value):
        return value
    async def complete(*args):
        return PageCompletion(json.dumps(payload), "stop", {})
    monkeypatch.setattr(probe, "preflight_page_reader_routes", preflight)
    monkeypatch.setattr(probe, "direct_completion", complete)
    output = tmp_path / "probe"
    asyncio.run(probe.run_persistent(data_paths.db_path, "synthetic", ["component-a"], output))
    result = json.loads((output / "result.json").read_text())
    assert result["state"] == "completed"
    assert result["accepted"] is False
    with session_factory() as session:
        assert session.execute(text("SELECT count(*) FROM jobs")).scalar_one() == 0


@pytest.mark.parametrize("both_local", [False, True])
def test_persistent_batches_read_every_fact_in_both_lanes(session_factory, data_paths, monkeypatch, both_local):
    from tests.v2.llm.test_predicate_binding_batches import _input
    from app.llm.predicate_binding_candidates import predicate_binding_prompt_input
    from app.llm.predicate_binding_batches import plan_binding_batches, project_binding_batch
    frozen = _input()
    monkeypatch.setattr(
        "app.llm.mtplx_model_lifecycle.mtplx_deployment_identity",
        lambda provider, *_: ({"lifecycle": "fixture"} if provider == "mtplx" else None),
    )
    prompt = predicate_binding_prompt_input(frozen)
    full = plan_binding_batches(frozen, prompt, max_characters=100000)[0]
    limit = len(json.dumps(project_binding_batch(prompt, frozen, full), ensure_ascii=False, separators=(",", ":"))) - 1
    monkeypatch.setattr("app.services.predicate_binding_job.build_predicate_binding_frozen_input",
                        lambda *args, **kwargs: frozen)
    routes = {
        PageReviewLane.MAIN_A: _route(provider="omlx" if both_local else "zhipu-coding-plan"),
        PageReviewLane.MAIN_B: _route(lane=PageReviewLane.MAIN_B, provider="mtplx"),
    }
    seen = {lane: [] for lane in routes}
    active = set()
    maximum = [0]
    lock = threading.Lock()
    rendezvous = threading.Barrier(2, timeout=10)
    async def complete(route, messages, budget):
        with lock:
            assert route.lane not in active
            active.add(route.lane)
            maximum[0] = max(maximum[0], len(active))
        if not both_local:
            await asyncio.to_thread(rendezvous.wait)
        request = json.loads(messages[1]["content"][0]["text"])
        provided = request["frozen_input"]
        source_columns = provided["sources"]["columns"]
        document_index = source_columns.index("source_document_version_id")
        assert len(provided["facts"]["rows"]) == len(provided["batch"]["fact_ids"])
        seen[route.lane].extend(
            row[document_index] for row in provided["sources"]["rows"]
        )
        await asyncio.sleep(0.01)
        with lock:
            active.remove(route.lane)
        return PageCompletion(json.dumps({"results": [{
            "predicate_identity_sha256": identity,
            "status": "unresolved", "candidates": [], "uncertainty": "仅本批尚未对应",
            "fact_accounting": {
                "accounting_version": "candidate-fact-accounting/v2",
                "grouped_dispositions": [],
                "default_group": {
                    "disposition": "uncertain", "reason_code": "category_match_only",
                    "note": "合成资料仅用于核对分包完整性",
                },
            },
        } for identity in request["required_predicate_identities"]]}), "stop", {})
    job = enqueue_predicate_candidates(session_factory, review_episode_id="synthetic",
        component_ids=["component-a"], routes=routes, batch_max_characters=limit)
    artifacts = ArtifactStore(data_paths)
    runner = JobRunner(session_factory, {JOB_TYPE: PredicateBindingJobExecutor(
        session_factory, artifacts, routes, completion=complete)})
    assert runner.run_job(job.job_id)
    assert not runner.run_job(job.job_id)
    assert maximum[0] == (1 if both_local else 2)
    for values in seen.values():
        assert sorted(values) == sorted(
            locator.source_document_version_id for locator in frozen.locators
        )
    with session_factory() as session:
        summary = JobStore(session).get_last_checkpoint(job.job_id, "summary")[1]
        assert len(summary["reads"]) > 2
        assert summary["status"] == "unverified"
        assert summary["accepted"] is False
        from app.services.binding_qualification_support import verify_completed_candidate_comparison
        verified = verify_completed_candidate_comparison(session, artifacts, job.job_id)
        expected_batches = {
            batch["batch_sha256"]: set(batch["fact_ids"])
            for batch in json.loads(JobStore(session).get_job(job.job_id).payload_json)["batches"]
        }
        assert len(verified["comparison"]["batches"]) == len(expected_batches)
        for compared in verified["comparison"]["batches"]:
            expected = expected_batches[compared["batch_sha256"]]
            for result in compared["results"]:
                assert {row["fact_id"] for row in result["fact_accounting"]} == expected
