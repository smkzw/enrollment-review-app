import pytest

from app.llm.page_review_harness import PageCompletion
from app.workflow.runner import JobRunner
from app.workflow.jobstore import JobStore
from tests.v2.services.test_fact_normalization_persistence import _seed_chain
from tests.v2.services.test_page_review_execution import _routes, _fact_payload


@pytest.mark.parametrize("mode", ["success", "length_again", "schema", "both_failed"])
def test_one_length_exception_preserves_success_and_never_doubles(client, monkeypatch, mode):
    from app.services import page_review_runtime
    monkeypatch.setattr(page_review_runtime, "require_page_reader_routes", _routes)

    async def preflight(routes):
        return routes

    monkeypatch.setattr(page_review_runtime, "preflight_page_reader_routes", preflight)
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix="length-http")
    url = f"/api/v2/subjects/{chain['subject_id']}/review-episodes/{chain['episode_id']}/page-review-jobs"
    original = client.post(url, json={}).json()["job_id"]
    runtime = client.app.state.page_review_runtime
    runtime.artifact_store.put("page_image", b"length-http-page-input")

    async def initial(route, *_args):
        if route.lane.value == "main-B" or mode == "both_failed":
            return PageCompletion("{}", "stop" if mode == "schema" else "length", {})
        return PageCompletion(_fact_payload(), "stop", {})

    runtime._executor.completion = initial
    runner = JobRunner(factory, client.app.state.job_executors)
    assert runner.run_job(original)
    with factory() as session:
        saved = JobStore(session).get_last_checkpoint(original, "read:0:main-A")[1]
    body = {"predecessor_job_id": original, "single_length_recovery": True}
    submitted = client.post(url, json=body)
    if mode in {"schema", "both_failed"}:
        assert submitted.status_code == 409, submitted.text
        return
    assert submitted.status_code == 201, submitted.text
    child = submitted.json()["job_id"]
    assert client.post(url, json=body).json()["job_id"] == child
    calls = []

    async def recovery(route, messages, max_tokens):
        calls.append((route.lane.value, max_tokens))
        assert route.reasoning_effort == "high"
        return PageCompletion(_fact_payload(), "length" if mode == "length_again" else "stop", {})

    runtime._executor.completion = recovery
    assert runner.run_job(child)
    assert calls == [("main-B", 48000)]
    with factory() as session:
        store = JobStore(session)
        assert store.get_last_checkpoint(child, "read:0:main-A")[1] == saved
        assert store.get_last_checkpoint(original, "read:0:main-A")[1] == saved
    assert client.post(url, json={"predecessor_job_id": child, "single_length_recovery": True}).status_code == 409
    status = client.get(url + "/" + child).json()
    assert not status["can_reread"]
    assert status["review_status"] == ("needs_reread" if mode == "length_again" else "ready")
