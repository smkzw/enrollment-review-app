import dataclasses
import asyncio
import json

import httpx
import pytest
from openai import APITimeoutError

from app.domain.contracts.page_review import PageReviewLane
from app.evidence.artifacts import ArtifactStore
from app.llm.page_review_harness import PageCompletion
from app.services.predicate_binding_job import (
    JOB_TYPE, PredicateBindingJobExecutor, enqueue_predicate_candidates,
)
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner
from scripts import recover_predicate_binding_read as recovery
from tests.v2.llm.test_predicate_binding_candidates import _case, _route


@pytest.fixture
def timed_out_read(session_factory, data_paths, monkeypatch):
    frozen, payload = _case()
    monkeypatch.setattr("app.services.predicate_binding_job.build_predicate_binding_frozen_input",
                        lambda *a, **k: frozen)
    monkeypatch.setattr(recovery, "build_predicate_binding_frozen_input", lambda *a, **k: frozen)
    routes = {lane: _route(lane=lane) for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)}
    async def complete(route, *args):
        if route.lane == PageReviewLane.MAIN_B:
            raise APITimeoutError(request=httpx.Request("POST", "http://localhost/test"))
        return PageCompletion(json.dumps(payload), "stop", {})
    artifacts = ArtifactStore(data_paths)
    job = enqueue_predicate_candidates(session_factory, review_episode_id="synthetic",
                                      component_ids=["component-a"], routes=routes)
    JobRunner(session_factory, {JOB_TYPE: PredicateBindingJobExecutor(
        session_factory, artifacts, routes, completion=complete)}).run_job(job.job_id)
    return job.job_id, artifacts, routes, frozen


def test_only_failed_read_is_prepared_and_original_state_unchanged(session_factory, timed_out_read):
    job_id, artifacts, routes, frozen = timed_out_read
    with session_factory() as session:
        store = JobStore(session)
        before = store.get_last_checkpoint(job_id, "read:main-B")
        result = recovery.prepare_recovery(session, artifacts, job_id, "read:main-B", routes)
        assert result[0] == frozen
        assert result[1].lane == PageReviewLane.MAIN_B
        assert result[3]["accepted"] is False
        assert store.get_job(job_id).state == "failed_final"
        assert store.get_last_checkpoint(job_id, "read:main-B") == before
        with pytest.raises(ValueError, match="未完成回执"):
            recovery.prepare_recovery(session, artifacts, job_id, "read:main-A", routes)


def test_recovery_rejects_changed_input(session_factory, timed_out_read, monkeypatch):
    job_id, artifacts, routes, _ = timed_out_read
    monkeypatch.setattr(recovery, "build_predicate_binding_frozen_input", lambda *a, **k: _case(source=None)[0])
    with session_factory() as session, pytest.raises(ValueError, match="资料已变化"):
        recovery.prepare_recovery(session, artifacts, job_id, "read:main-B", routes)


def test_recovery_rejects_changed_route(session_factory, timed_out_read):
    job_id, artifacts, routes, _ = timed_out_read
    routes[PageReviewLane.MAIN_B] = dataclasses.replace(routes[PageReviewLane.MAIN_B], max_tokens=131072)
    with session_factory() as session, pytest.raises(ValueError, match="模型配置"):
        recovery.prepare_recovery(session, artifacts, job_id, "read:main-B", routes)


@pytest.mark.parametrize("version", ["PROMPT_VERSION", "BATCH_PROMPT_VERSION"])
def test_recovery_rejects_prompt_drift_with_same_job_contract(
        session_factory, timed_out_read, monkeypatch, version):
    job_id, artifacts, routes, _ = timed_out_read
    monkeypatch.setattr(recovery, version, "new-prompt-version")
    with session_factory() as session, pytest.raises(ValueError, match="当前合同"):
        recovery.prepare_recovery(session, artifacts, job_id, "read:main-B", routes)


def test_recovery_rejects_stop_with_missing_condition(
        session_factory, data_paths, monkeypatch):
    frozen, payload = _case()
    monkeypatch.setattr("app.services.predicate_binding_job.build_predicate_binding_frozen_input",
                        lambda *a, **k: frozen)
    monkeypatch.setattr(recovery, "build_predicate_binding_frozen_input", lambda *a, **k: frozen)
    routes = {lane: _route(lane=lane) for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)}
    async def complete(route, *args):
        results = payload["results"] if route.lane == PageReviewLane.MAIN_A else payload["results"][:-1]
        return PageCompletion(json.dumps({"results": results}), "stop", {})
    artifacts = ArtifactStore(data_paths)
    job = enqueue_predicate_candidates(session_factory, review_episode_id="synthetic",
                                      component_ids=["component-a"], routes=routes)
    JobRunner(session_factory, {JOB_TYPE: PredicateBindingJobExecutor(
        session_factory, artifacts, routes, completion=complete)}).run_job(job.job_id)
    with session_factory() as session:
        store = JobStore(session)
        before = store.get_last_checkpoint(job.job_id, "read:main-B")
        assert before[1]["status"] == "incomplete"
        with pytest.raises(ValueError, match="未取得回答"):
            recovery.prepare_recovery(session, artifacts, job.job_id, "read:main-B", routes)
        assert store.get_job(job.job_id).state == "failed_final"
        assert store.get_last_checkpoint(job.job_id, "read:main-B") == before


def test_recovery_rejects_request_drift(session_factory, timed_out_read, monkeypatch):
    job_id, artifacts, routes, _ = timed_out_read
    monkeypatch.setattr(recovery, "build_predicate_binding_messages", lambda *a, **k: [])
    with session_factory() as session, pytest.raises(ValueError, match="当前请求"):
        recovery.prepare_recovery(session, artifacts, job_id, "read:main-B", routes)


def test_recovery_rejects_corrupt_receipt(session_factory, timed_out_read, monkeypatch):
    job_id, artifacts, routes, _ = timed_out_read
    monkeypatch.setattr(artifacts, "read_by_sha", lambda *a: b"{}")
    with session_factory() as session, pytest.raises(ValueError, match="校验失败"):
        recovery.prepare_recovery(session, artifacts, job_id, "read:main-B", routes)


def test_isolated_attempt_calls_only_selected_lane_and_preserves_job(
        session_factory, data_paths, timed_out_read, monkeypatch, tmp_path):
    job_id, artifacts, routes, _ = timed_out_read
    source = tmp_path / "source"
    source.mkdir()
    (source / "job.json").write_text(json.dumps({"job_id": job_id}))
    output = tmp_path / "recovery"
    monkeypatch.setattr(recovery, "resolve_data_paths", lambda _: data_paths)
    monkeypatch.setattr(recovery, "require_page_reader_routes", lambda: routes)
    async def preflight(route):
        return route
    monkeypatch.setattr(recovery, "resolve_route_model", preflight)
    calls = []
    async def complete(route, messages, budget):
        calls.append((route.lane, budget))
        return PageCompletion(json.dumps(_case()[1]), "stop", {})
    monkeypatch.setattr(recovery, "direct_completion", complete)
    with session_factory() as session:
        original = JobStore(session).get_last_checkpoint(job_id, "read:main-B")
    asyncio.run(recovery.run(source, "read:main-B", output))
    assert calls == [(PageReviewLane.MAIN_B, 65536)]
    result = json.loads((output / "candidates.json").read_text())
    assert result["accepted"] is False
    assert result["source_job_id"] == job_id
    assert result["source_checkpoint_id"] == original[0]
    with session_factory() as session:
        store = JobStore(session)
        assert store.get_job(job_id).state == "failed_final"
        assert store.get_last_checkpoint(job_id, "read:main-B") == original
        assert store.get_last_checkpoint(job_id, "summary") is None
    with pytest.raises(FileExistsError):
        asyncio.run(recovery.run(source, "read:main-B", output))
    assert calls == [(PageReviewLane.MAIN_B, 65536)]
