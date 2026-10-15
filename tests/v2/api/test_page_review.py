import json
import pytest

from sqlalchemy import func, select

from app.services.page_review_job_service import PAGE_REVIEW_JOB_TYPE
from app.storage.models import JobRecord
from tests.v2.services.test_fact_normalization_persistence import _seed_chain
from tests.v2.services.test_page_review_execution import _routes, _fact_payload
from app.llm.page_review_harness import PageCompletion
from app.workflow.runner import JobRunner
from app.workflow.jobstore import JobStore
from app.storage.page_review_repository import PageReviewRepository


@pytest.mark.parametrize("cancel_before_read", [False, True])
def test_targeted_review_api_keeps_rounds_server_owned(client, monkeypatch, cancel_before_read):
    from app.services import page_review_runtime
    from tests.v2.services.test_targeted_page_review_jobs import response
    from app.services.targeted_page_review_jobs import TARGETED_REVIEW_JOB_TYPE

    monkeypatch.setattr(page_review_runtime, "require_page_reader_routes", _routes)

    async def preflight(routes):
        return routes

    monkeypatch.setattr(page_review_runtime, "preflight_page_reader_routes", preflight)
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix="targeted-http")
    base = f"/api/v2/subjects/{chain['subject_id']}/review-episodes/{chain['episode_id']}"
    original = client.post(base + "/page-review-jobs", json={}).json()["job_id"]
    url = base + "/targeted-review-jobs"
    body = {"original_job_id": original, "page_index": 0}
    assert client.post(url, json=body).status_code == 409
    runtime = client.app.state.page_review_runtime
    assert runtime._executor.completion is runtime._targeted_executor.completion
    runtime.artifact_store.put("page_image", b"targeted-http-page-input")

    async def completion(route, *_args):
        return response("4.2" if route.lane.value == "main-A" else "5.2")

    runtime._executor.completion = completion
    runner = JobRunner(factory, client.app.state.job_executors)
    assert runner.run_job(original)
    candidates = client.get(base + "/page-review-jobs/" + original + "/conflicts")
    assert candidates.status_code == 200, candidates.text
    assert candidates.json()["pages"][0]["page_index"] == 0
    assert candidates.json()["pages"][0]["field_count"] > 0
    submitted = client.post(url, json=body)
    assert submitted.status_code == 201, submitted.text
    assert client.post(url, json=body).status_code == 200
    assert client.post(url, json={**body, "round_number": 3}).status_code == 422
    assert client.post(url, json={**body, "page_index": True}).status_code == 422
    assert TARGETED_REVIEW_JOB_TYPE in client.app.state.job_executors
    targeted_id = submitted.json()["job_id"]
    if cancel_before_read:
        cancelled = client.post(f"/api/v2/jobs/{targeted_id}/cancel")
        assert cancelled.status_code == 200, cancelled.text
        stopped = client.get(url + "/" + targeted_id)
        assert stopped.status_code == 200
        assert "停止" in stopped.json()["status_label"]
        assert stopped.json()["outcome"] is None
        assert stopped.json()["rounds_with_receipts"] == 0
        return
    runtime._targeted_executor.completion = completion
    assert runner.run_job(submitted.json()["job_id"])
    with factory() as session:
        assert JobStore(session).get_job(submitted.json()["job_id"]).state == "completed"
    def forbidden_prepare():
        pytest.fail("读取复核结果不得启动模型")
    monkeypatch.setattr(runtime, "_prepare", forbidden_prepare)
    status = client.get(url + "/" + submitted.json()["job_id"])
    assert status.status_code == 200
    assert status.json()["rounds_with_receipts"] == 2
    assert status.json()["outcome"]["outcome_kind"] == "conflict_pending_user"
    assert status.json()["outcome"]["candidate_auto_accept"] is False
    evidence = client.get(url + "/" + targeted_id + "/evidence")
    assert evidence.status_code == 200, evidence.text
    assert {item["round_number"] for item in evidence.json()["excerpts"]} == {0, 1, 2}
    assert {item["read_number"] for item in evidence.json()["excerpts"]} == {1, 2}
    assert evidence.json()["candidate_auto_accept"] is False
    assert client.get(evidence.json()["image_path"]).content == b"targeted-http-page-input"


def test_page_review_http_freezes_server_authority_and_is_idempotent(client, monkeypatch):
    from app.services import page_review_runtime

    monkeypatch.setattr(page_review_runtime, "require_page_reader_routes", _routes)

    async def preflight(routes):
        return routes

    monkeypatch.setattr(page_review_runtime, "preflight_page_reader_routes", preflight)
    with client.app.state.session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="r3-http")
    url = f"/api/v2/subjects/{chain['subject_id']}/review-episodes/{chain['episode_id']}/page-review-jobs"
    first = client.post(url, json={})
    assert first.status_code == 201, first.text
    normalizer_url = url.replace("page-review-jobs", "fact-normalization-jobs")
    assert client.post(normalizer_url, json={}).status_code == 409
    second = client.post(url, json={})
    assert second.status_code == 200, second.text
    assert first.json()["job_id"] == second.json()["job_id"]
    assert PAGE_REVIEW_JOB_TYPE in client.app.state.job_executors
    with client.app.state.session_factory() as session:
        payload = json.loads(session.get(JobRecord, first.json()["job_id"]).payload_json)
    assert payload["authority"]["subject_id"] == chain["subject_id"]
    assert payload["pages"][0]["page_artifact_id"] == chain["page_artifact_id"]
    assert "api_key" not in json.dumps(payload)
    assert client.post(url, json={"pages": []}).status_code == 422

    runtime = client.app.state.page_review_runtime
    runtime.artifact_store.put("page_image", b"r3-http-page-input")

    async def completion(*_args):
        return PageCompletion(_fact_payload(), "stop", {})

    runtime._executor.completion = completion
    assert JobRunner(client.app.state.session_factory, client.app.state.job_executors).run_job(first.json()["job_id"])
    with client.app.state.session_factory() as session:
        receipt = JobStore(session).get_last_checkpoint(first.json()["job_id"], "coverage")
        coverage = PageReviewRepository(session).get_coverage(receipt[1]["coverage_id"])
        assert coverage.entries[0].disposition.value == "accepted"
    with client.app.state.session_factory() as session, session.begin():
        legacy = coverage.model_copy(update={"coverage_id": "legacy-coverage", "execution_versions": {}})
        PageReviewRepository(session).save_coverage(legacy)
    normalized = client.post(normalizer_url, json={})
    assert normalized.status_code == 201, normalized.text
    with client.app.state.session_factory() as session:
        payload = json.loads(session.get(JobRecord, normalized.json()["job_id"]).payload_json)
        assert payload["page_review_coverage_id"] == coverage.coverage_id
    from app.services import page_review_coverage_selection
    with monkeypatch.context() as versions:
        versions.setattr(page_review_coverage_selection, "page_review_execution_versions", lambda: {"contract": "future"})
        assert client.post(normalizer_url, json={}).status_code == 409
    monkeypatch.setattr(page_review_coverage_selection, "PAGE_REVIEW_PROMPT_VERSION", "new-prompt-version")
    assert client.post(normalizer_url, json={}).status_code == 409


def test_failed_preflight_creates_no_job_and_does_not_expose_error(client, monkeypatch):
    from app.services import page_review_runtime

    def unavailable():
        raise ValueError("private-provider-detail")

    monkeypatch.setattr(page_review_runtime, "require_page_reader_routes", unavailable)
    with client.app.state.session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="r3-http-unavailable")
        before = session.scalar(select(func.count()).select_from(JobRecord))
    url = f"/api/v2/subjects/{chain['subject_id']}/review-episodes/{chain['episode_id']}/page-review-jobs"
    result = client.post(url, json={})
    assert result.status_code == 503, result.text
    assert "private-provider-detail" not in result.text
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(JobRecord)) == before


@pytest.mark.parametrize("fail_again", [False, True])
@pytest.mark.parametrize("legacy_serial", [False, True])
def test_controlled_reread_reuses_successful_lane_and_preserves_failed_history(client, monkeypatch, fail_again, legacy_serial):
    from app.services import page_review_runtime

    monkeypatch.setattr(page_review_runtime, "require_page_reader_routes", _routes)

    async def preflight(routes):
        return routes

    monkeypatch.setattr(page_review_runtime, "preflight_page_reader_routes", preflight)
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix="r3-http-reread")
    url = f"/api/v2/subjects/{chain['subject_id']}/review-episodes/{chain['episode_id']}/page-review-jobs"
    with monkeypatch.context() as legacy:
        if legacy_serial:
            from app.services.job_service import JobService
            create = JobService.create_job_in_session

            def serial_create(self, session, **kwargs):
                kwargs["payload"].pop("execution_control", None)
                return create(self, session, **kwargs)

            legacy.setattr(JobService, "create_job_in_session", serial_create)
        original = client.post(url, json={}).json()["job_id"]
    initial = client.get(f"{url}/{original}")
    assert initial.status_code == 200
    assert initial.json()["pending_pages"] == 1
    assert not initial.json()["can_reread"]
    # A running/queued task is resumed through its own lifecycle, not branched.
    assert client.post(url, json={"predecessor_job_id": original}).status_code == 409
    assert client.post(url, json={"predecessor_job_id": "missing"}).status_code == 404
    runtime = client.app.state.page_review_runtime
    runtime.artifact_store.put("page_image", b"r3-http-reread-page-input")
    calls = []

    async def failed_b(route, *_args):
        calls.append(route.lane.value)
        return PageCompletion("{}" if route.lane.value == "main-B" else _fact_payload(), "stop", {})

    runtime._executor.completion = failed_b
    runner = JobRunner(factory, client.app.state.job_executors)
    assert runner.run_job(original)
    # Invalid JSON shape gets one same-reader format repair, never a new A read.
    assert calls.count("main-A") == 1
    assert calls.count("main-B") == 2
    failed_status = client.get(f"{url}/{original}")
    assert failed_status.json()["state"] == "completed"
    assert failed_status.json()["review_status"] == "needs_reread"
    assert failed_status.json()["failed_pages"] == 1
    assert failed_status.json()["can_reread"]
    with factory() as session:
        store = JobStore(session)
        old_id = store.get_last_checkpoint(original, "coverage")[1]["coverage_id"]
        old_coverage = PageReviewRepository(session).get_coverage(old_id)
        saved_a = store.get_last_checkpoint(original, "read:0:main-A")[1]
    normalizer_url = url.replace("page-review-jobs", "fact-normalization-jobs")
    assert client.post(normalizer_url, json={}).status_code == 409
    from app.services import page_review_job_service
    with monkeypatch.context() as changed_version:
        changed_version.setattr(page_review_job_service, "PAGE_REVIEW_JOB_CONTRACT", "future")
        rejected = client.post(url, json={"predecessor_job_id": original})
        assert rejected.status_code == 409
        assert rejected.json()["error"]["code"] == "PAGE_REREAD_NOT_READY"
    with monkeypatch.context() as changed_route:
        from dataclasses import replace
        from app.domain.contracts.page_review import PageReviewLane
        routes = dict(runtime._routes)
        original_route = routes[PageReviewLane.MAIN_A]
        routes[PageReviewLane.MAIN_A] = replace(original_route,
            reasoning_effort="xhigh" if original_route.reasoning_effort == "high" else "high")
        assert routes[PageReviewLane.MAIN_A].reasoning_effort != original_route.reasoning_effort
        changed_route.setattr(runtime, "_routes", routes)
        rejected = client.post(url, json={"predecessor_job_id": original})
        assert rejected.status_code == 409
        assert rejected.json()["error"]["code"] == "PAGE_REREAD_NOT_READY"
    child = client.post(url, json={"predecessor_job_id": original})
    assert child.status_code == 201, child.text
    child_id = child.json()["job_id"]
    duplicate = client.post(url, json={"predecessor_job_id": original})
    assert duplicate.status_code == 200
    assert duplicate.json()["job_id"] == child_id

    if fail_again:
        assert runner.run_job(child_id)
        assert calls.count("main-A") == 1
        assert calls.count("main-B") == 4
        assert client.post(normalizer_url, json={}).status_code == 409
        grandchild = client.post(url, json={"predecessor_job_id": child_id})
        assert grandchild.status_code == 201, grandchild.text
        child_id = grandchild.json()["job_id"]

    async def successful(route, *_args):
        calls.append(route.lane.value)
        return PageCompletion(_fact_payload(), "stop", {})

    runtime._executor.completion = successful
    assert runner.run_job(child_id)
    ready = client.get(f"{url}/{child_id}").json()
    assert ready["review_status"] == "ready"
    assert ready["accepted_pages"] == 1
    assert ready["failed_pages"] == ready["pending_pages"] == 0
    assert calls.count("main-A") == 1
    assert calls.count("main-B") == (5 if fail_again else 3)
    with factory() as session:
        store = JobStore(session)
        assert store.get_last_checkpoint(child_id, "read:0:main-A")[1] == saved_a
        repository = PageReviewRepository(session)
        assert repository.get_coverage(old_id) == old_coverage
        new_id = store.get_last_checkpoint(child_id, "coverage")[1]["coverage_id"]
        predecessor = repository.get_coverage(new_id).predecessor_coverage_id
        if fail_again:
            assert repository.get_coverage(predecessor).predecessor_coverage_id == old_id
        else:
            assert predecessor == old_id
    normalized = client.post(normalizer_url, json={})
    assert normalized.status_code == 201, normalized.text
    with factory() as session:
        payload = json.loads(session.get(JobRecord, normalized.json()["job_id"]).payload_json)
        assert payload["page_review_coverage_id"] == new_id
    assert client.post(url, json={"predecessor_job_id": child_id}).status_code == 409
    # Viewing durable progress remains available when provider preparation fails.
    def unavailable():
        pytest.fail("状态查询不得初始化模型")
    monkeypatch.setattr(runtime, "_prepare", unavailable)
    assert client.get(f"{url}/{original}").json()["review_status"] == "needs_reread"
    assert client.get(f"{url}/{child_id}").json()["review_status"] == "ready"
    assert client.get(f"{url}/missing").status_code == 404
