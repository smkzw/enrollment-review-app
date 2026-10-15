"""页级判读已取消任务的受控续跑入口：身份一致才恢复，历史保持原样。"""

import pytest
import asyncio
from dataclasses import replace
from pydantic import ValidationError
from sqlalchemy import update

from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.review import ReviewEpisode
from app.domain.contracts.rules import RuleSet
from app.llm.page_review_harness import PageCompletion, PageReviewConfigError
from app.services import page_review_job_service, page_review_runtime
from app.services.page_review_job_service import PageReviewJobService
from app.storage.codecs import decode_contract, encode_contract
from app.storage.models import ReviewEpisodeRecord, RuleSetRecord
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner
from tests.v2.services.test_fact_normalization_persistence import _seed_chain
from tests.v2.services.test_page_review_execution import _fact_payload, _routes


def _prepare_runtime(client, monkeypatch):
    monkeypatch.setattr(page_review_runtime, "require_page_reader_routes", _routes)

    async def preflight(routes):
        return routes

    monkeypatch.setattr(page_review_runtime, "preflight_page_reader_routes", preflight)
    return client.app.state.page_review_runtime


def _cancelled_queued_job(client, monkeypatch, prefix):
    """入队后在排队状态直接取消：全部步骤已取消，历史检查点为空。"""
    _prepare_runtime(client, monkeypatch)
    with client.app.state.session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix=prefix)
    url = f"/api/v2/subjects/{chain['subject_id']}/review-episodes/{chain['episode_id']}/page-review-jobs"
    job_id = client.post(url, json={}).json()["job_id"]
    assert client.post(f"/api/v2/jobs/{job_id}/cancel").json()["state"] == "cancelled"
    return chain, url, job_id


def _resume(client, url, job_id):
    return client.post(f"{url}/{job_id}/resume")


def test_invalid_current_contract_cannot_resume(client, monkeypatch):
    _, url, job_id = _cancelled_queued_job(client, monkeypatch, "resume-invalid-contract")

    def invalid_plan(*args, **kwargs):
        raise ValidationError.from_exception_data("RuleSet", [{
            "type": "missing", "loc": ("rules",), "input": {},
        }])

    monkeypatch.setattr(page_review_job_service, "plan_page_review_payload", invalid_plan)
    response = _resume(client, url, job_id)
    assert response.status_code == 409
    with client.app.state.session_factory() as session:
        assert JobStore(session).get_job(job_id).state == "cancelled"


def test_restart_resume_resolves_the_same_two_main_readers(client, monkeypatch):
    runtime = _prepare_runtime(client, monkeypatch)
    routes = _routes()
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix="resume-restart-mains")
    job = PageReviewJobService(factory).enqueue(subject_id=chain["subject_id"],
        review_episode_id=chain["episode_id"], routes=routes)
    assert client.post(f"/api/v2/jobs/{job.job_id}/cancel").json()["state"] == "cancelled"
    checked = []

    async def preflight(configured):
        checked.append(True)
        return dict(configured)

    monkeypatch.setattr(page_review_runtime, "preflight_page_reader_routes", preflight)
    url = f"/api/v2/subjects/{chain['subject_id']}/review-episodes/{chain['episode_id']}/page-review-jobs"
    assert client.get(f"{url}/{job.job_id}").status_code == 200
    assert checked == []
    result = _resume(client, url, job.job_id)
    assert result.status_code == 200, result.text
    assert result.json()["changed"] is True
    assert checked == [True]
    assert set(runtime._routes) == {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}


def test_resume_api_continues_cancelled_job_without_repeating_reads(client, monkeypatch):
    runtime = _prepare_runtime(client, monkeypatch)
    factory = client.app.state.session_factory
    prefix = "resume-ok"
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix=prefix)
    url = f"/api/v2/subjects/{chain['subject_id']}/review-episodes/{chain['episode_id']}/page-review-jobs"
    job_id = client.post(url, json={}).json()["job_id"]
    runtime.artifact_store.put("page_image", f"{prefix}-page-input".encode())
    calls = []

    async def cancel_during_first_read(route, *_args):
        calls.append(route.lane.value)
        if route.lane.value == "main-A" and calls.count("main-A") == 1:
            with factory() as session, session.begin():
                JobStore(session).request_cancel(job_id)
        return PageCompletion(_fact_payload(), "stop", {})

    runtime._executor.completion = cancel_during_first_read
    assert JobRunner(factory, client.app.state.job_executors).run_job(job_id)
    with factory() as session:
        store = JobStore(session)
        assert store.get_job(job_id).state == "cancelled"
        assert store.get_last_checkpoint(job_id, "coverage") is None
        preserved = {lane: store.get_last_checkpoint(job_id, f"read:0:{lane}")
                     for lane in ("main-A", "main-B")}
        assert any(receipt is not None for receipt in preserved.values())
    stopped = client.get(f"{url}/{job_id}").json()
    assert stopped["state"] == "cancelled"
    assert stopped["review_status"] == "stopped"

    def forbidden_prepare():
        pytest.fail("续跑入口不得初始化模型运行时")

    with monkeypatch.context() as no_prepare:
        no_prepare.setattr(runtime, "_prepare", forbidden_prepare)
        resumed = _resume(client, url, job_id)
        assert resumed.status_code == 200, resumed.text
        body = resumed.json()
        assert body["changed"] is True
        assert body["state"] == "queued"
        assert body["state_label"] == "等待处理"
        duplicate = _resume(client, url, job_id)
        assert duplicate.status_code == 200
        assert duplicate.json()["changed"] is False
        assert duplicate.json()["state"] == "queued"

    async def successful(route, *_args):
        calls.append(route.lane.value)
        return PageCompletion(_fact_payload(), "stop", {})

    runtime._executor.completion = successful
    assert JobRunner(factory, client.app.state.job_executors).run_job(job_id)
    final = client.get(f"{url}/{job_id}").json()
    assert final["state"] == "completed"
    assert final["review_status"] == "ready"
    with factory() as session:
        store = JobStore(session)
        assert store.get_last_checkpoint(job_id, "coverage") is not None
        for lane, receipt in preserved.items():
            if receipt is not None:
                assert store.get_last_checkpoint(job_id, f"read:0:{lane}") == receipt
                assert calls.count(lane) == 1
    finished = _resume(client, url, job_id)
    assert finished.status_code == 200
    assert finished.json()["changed"] is False
    assert finished.json()["state"] == "completed"


def test_durable_cancel_interrupts_inflight_page_request(client, monkeypatch):
    runtime = _prepare_runtime(client, monkeypatch)
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix="cancel-inflight")
    url = f"/api/v2/subjects/{chain['subject_id']}/review-episodes/{chain['episode_id']}/page-review-jobs"
    job_id = client.post(url, json={}).json()["job_id"]
    runtime.artifact_store.put("page_image", b"cancel-inflight-page-input")
    interrupted = []

    async def pending(route, *_):
        if route.lane == PageReviewLane.MAIN_A:
            with factory() as session, session.begin():
                JobStore(session).request_cancel(job_id)
            try:
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                interrupted.append(True)
                raise
        return PageCompletion(_fact_payload(), "stop", {})

    runtime._executor.completion = pending
    assert JobRunner(factory, client.app.state.job_executors).run_job(job_id)
    assert interrupted == [True]
    with factory() as session:
        store = JobStore(session)
        assert store.get_job(job_id).state == "cancelled"
        assert store.get_last_checkpoint(job_id, "read:0:main-A") is None
        assert store.get_last_checkpoint(job_id, "coverage") is None


def test_resume_refuses_changed_execution_version(client, monkeypatch):
    _, url, job_id = _cancelled_queued_job(client, monkeypatch, "resume-version")
    with monkeypatch.context() as changed:
        changed.setattr(page_review_job_service, "PAGE_REVIEW_JOB_CONTRACT", "future")
        refused = _resume(client, url, job_id)
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "PAGE_REVIEW_RESUME_NOT_READY"
    with client.app.state.session_factory() as session:
        store = JobStore(session)
        assert store.get_job(job_id).state == "cancelled"
        assert {step.state for step in store.list_steps(job_id)} == {"cancelled"}


def test_resume_rechecks_live_identity_without_replacing_cached_runtime(client, monkeypatch):
    _, url, job_id = _cancelled_queued_job(client, monkeypatch, "resume-live-drift")
    runtime = client.app.state.page_review_runtime
    original = runtime._routes
    checked = []

    async def changed_live_model(routes):
        checked.append(True)
        changed = dict(routes)
        changed[PageReviewLane.MAIN_B] = replace(changed[PageReviewLane.MAIN_B], model="different-live-model")
        return changed

    monkeypatch.setattr(page_review_runtime, "preflight_page_reader_routes", changed_live_model)
    assert client.get(f"{url}/{job_id}").status_code == 200
    assert checked == []
    refused = _resume(client, url, job_id)
    assert refused.status_code == 409, refused.text
    assert checked == [True]
    assert runtime._routes is original
    with client.app.state.session_factory() as session:
        assert JobStore(session).get_job(job_id).state == "cancelled"


def test_resume_refuses_changed_main_reader_identity(client, monkeypatch):
    runtime = _prepare_runtime(client, monkeypatch)
    _, url, job_id = _cancelled_queued_job(client, monkeypatch, "resume-main-reader")
    routes = dict(runtime._routes)
    original_route = routes[PageReviewLane.MAIN_A]
    routes[PageReviewLane.MAIN_A] = replace(original_route,
        reasoning_effort="xhigh" if original_route.reasoning_effort == "high" else "high")
    assert routes[PageReviewLane.MAIN_A].reasoning_effort != original_route.reasoning_effort
    monkeypatch.setattr(runtime, "_routes", routes)
    refused = _resume(client, url, job_id)
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "PAGE_REVIEW_RESUME_NOT_READY"
    with client.app.state.session_factory() as session:
        assert JobStore(session).get_job(job_id).state == "cancelled"


def test_resume_refuses_advanced_episode_revision(client, monkeypatch):
    chain, url, job_id = _cancelled_queued_job(client, monkeypatch, "resume-episode")
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        record = session.get(ReviewEpisodeRecord, chain["episode_id"])
        decoded = decode_contract(ReviewEpisode, record.payload_json, record.payload_sha256)
        bumped = decoded.model_copy(update={"revision": decoded.revision + 1})
        payload_json, payload_sha256 = encode_contract(bumped)
        session.execute(
            update(ReviewEpisodeRecord)
            .where(ReviewEpisodeRecord.review_episode_id == chain["episode_id"])
            .values(payload_json=payload_json, payload_sha256=payload_sha256,
                    revision=bumped.revision)
        )
    refused = _resume(client, url, job_id)
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "PAGE_REVIEW_RESUME_NOT_READY"
    with factory() as session:
        assert JobStore(session).get_job(job_id).state == "cancelled"


def test_resume_refuses_changed_clause_pack_content(client, monkeypatch):
    chain, url, job_id = _cancelled_queued_job(client, monkeypatch, "resume-pack")
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        record = session.get(RuleSetRecord,
                             (chain["rule_set_id"], chain["authority"].rule_set_revision))
        rule_set = decode_contract(RuleSet, record.payload_json, record.payload_sha256)
        rule = rule_set.rules[0]
        component = rule.components[0]
        changed = rule_set.model_copy(update={"rules": [rule.model_copy(update={
            "components": [component.model_copy(update={"title": component.title + "（已修订）"})],
        })]})
        record.payload_json, record.payload_sha256 = encode_contract(changed)
    refused = _resume(client, url, job_id)
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "PAGE_REVIEW_RESUME_NOT_READY"
    with factory() as session:
        assert JobStore(session).get_job(job_id).state == "cancelled"


def test_resume_is_node_scoped_and_rejects_unknown_or_foreign_jobs(client, monkeypatch):
    from app.storage.models import ProjectRecord
    from app.storage.repositories import EpisodeRepository, SubjectRepository
    from tests.v2.storage.test_repositories_roundtrip import FIXTURES

    _prepare_runtime(client, monkeypatch)
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix="resume-scope-a")
    with factory() as session, session.begin():
        # 另一个合法受试者/审核节点（无需完整证据链），用于跨节点拒绝。
        fixture = FIXTURES[0]
        assert session.get(ProjectRecord, fixture.project.project_id) is not None
        other_subject = fixture.subject.model_copy(update={
            "subject_id": "resume-scope-subject-b", "subject_code": "S-RESUME-B"})
        SubjectRepository(session).save(other_subject)
        other_episode = fixture.review_episode.model_copy(update={
            "review_episode_id": "resume-scope-episode-b",
            "subject_id": other_subject.subject_id})
        EpisodeRepository(session).save(other_episode)
    url = f"/api/v2/subjects/{chain['subject_id']}/review-episodes/{chain['episode_id']}/page-review-jobs"
    other_url = (f"/api/v2/subjects/{other_subject.subject_id}"
                 f"/review-episodes/{other_episode.review_episode_id}/page-review-jobs")
    job_id = client.post(url, json={}).json()["job_id"]
    assert client.post(f"/api/v2/jobs/{job_id}/cancel").json()["state"] == "cancelled"
    assert _resume(client, other_url, job_id).status_code == 404
    assert client.get(f"{url}/{job_id}").json()["state"] == "cancelled"
    assert _resume(client, url, "missing").status_code == 404
    demo = client.post("/api/v2/jobs", json={
        "idempotency_key": "resume-scope-demo", "job_type": "demo",
        "payload": {}, "steps": [{"step_id": "s1", "name": "步骤"}]})
    assert _resume(client, url, demo.json()["job_id"]).status_code == 404
    assert client.post(f"/api/v2/jobs/{demo.json()['job_id']}/cancel").json()["state"] == "cancelled"
    assert _resume(client, url, demo.json()["job_id"]).status_code == 404


def test_resume_rejects_cancelled_targeted_review_jobs(client, monkeypatch):
    runtime = _prepare_runtime(client, monkeypatch)
    factory = client.app.state.session_factory
    prefix = "resume-targeted"
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix=prefix)
    base = f"/api/v2/subjects/{chain['subject_id']}/review-episodes/{chain['episode_id']}"
    original = client.post(base + "/page-review-jobs", json={}).json()["job_id"]
    runtime.artifact_store.put("page_image", f"{prefix}-page-input".encode())
    from tests.v2.services.test_targeted_page_review_jobs import response

    async def conflicting(route, *_args):
        return response("4.2" if route.lane.value == "main-A" else "5.2")

    runtime._executor.completion = conflicting
    assert JobRunner(factory, client.app.state.job_executors).run_job(original)
    submitted = client.post(base + "/targeted-review-jobs",
                            json={"original_job_id": original, "page_index": 0})
    assert submitted.status_code == 201, submitted.text
    targeted_id = submitted.json()["job_id"]
    assert client.post(f"/api/v2/jobs/{targeted_id}/cancel").json()["state"] == "cancelled"
    refused = client.post(f"{base}/page-review-jobs/{targeted_id}/resume")
    assert refused.status_code == 404, refused.text
    with factory() as session:
        store = JobStore(session)
        assert store.get_job(targeted_id).state == "cancelled"
        # 两轮复核的步骤预算保持原样，未被子入口重置。
        rounds = {step.step_id: (step.max_attempts, step.attempt)
                  for step in store.list_steps(targeted_id)}
        assert rounds["read:2:main-A"][0] == 2


def test_resume_reports_unavailable_without_reader_configuration(client, monkeypatch):
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix="resume-noconfig")
    job = PageReviewJobService(factory).enqueue(
        subject_id=chain["subject_id"], review_episode_id=chain["episode_id"], routes=_routes())
    url = f"/api/v2/subjects/{chain['subject_id']}/review-episodes/{chain['episode_id']}/page-review-jobs"
    assert client.post(f"/api/v2/jobs/{job.job_id}/cancel").json()["state"] == "cancelled"

    def no_config(*_args, **_kwargs):
        raise PageReviewConfigError("缺少逐页判读凭据")

    monkeypatch.setattr(page_review_runtime, "require_page_reader_routes", no_config)
    refused = _resume(client, url, job.job_id)
    assert refused.status_code == 503, refused.text
    assert refused.json()["error"]["code"] == "PAGE_REVIEW_UNAVAILABLE"
    with factory() as session:
        store = JobStore(session)
        assert store.get_job(job.job_id).state == "cancelled"
        assert {step.state for step in store.list_steps(job.job_id)} == {"cancelled"}
