"""A content-changing format repair remains a failed read with raw receipts."""

import json

from app.evidence.artifacts import ArtifactStore
from app.llm.page_review_harness import PageCompletion
from app.services.page_review_job_executor import PageReviewJobExecutor
from app.services.page_review_job_service import PAGE_REVIEW_JOB_TYPE, PageReviewJobService
from app.storage.page_review_repository import PageReviewRepository
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner
from tests.v2.services.test_fact_normalization_persistence import _seed_chain
from tests.v2.services.test_page_review_execution import _routes
from tests.v2.services.test_targeted_page_review_jobs import response


def test_changed_repair_keeps_both_answers_and_failed_page(session_factory, data_paths):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="repair-receipts")
    artifacts = ArtifactStore(data_paths)
    artifacts.put("page_image", b"repair-receipts-page-input")
    routes = _routes()
    calls = {"main-A": [], "main-B": []}

    async def completion(route, messages, *_args):
        lane = route.lane.value
        if lane == "main-A":
            answer = response("4.2")
        elif not calls[lane]:
            payload = json.loads(response("4.2").text)
            payload["has_eligibility_value"] = False
            answer = PageCompletion(json.dumps(payload), "stop", {})
        else:
            answer = response("9.1")
        calls[lane].append(answer.text)
        return answer

    job = PageReviewJobService(session_factory).enqueue(subject_id=chain["subject_id"],
        review_episode_id=chain["episode_id"], routes=routes)
    runner = JobRunner(session_factory, {PAGE_REVIEW_JOB_TYPE: PageReviewJobExecutor(
        session_factory, artifacts, routes, completion=completion)})
    assert runner.run_job(job.job_id)
    with session_factory() as session:
        store = JobStore(session)
        read = store.get_last_checkpoint(job.job_id, "read:0:main-B")[1]
        assert read["lane_failure"]["failure_kind"] == "schema"
        assert "page_review_id" not in read
        assert len(read["response_attempts"]) == 2
        assert [artifacts.read_by_sha("raw_response", item["response_sha256"]).decode()
                for item in read["response_attempts"]] == calls["main-B"]
        for item in read["response_attempts"]:
            assert item["request_sha256"]
        coverage_id = store.get_last_checkpoint(job.job_id, "coverage")[1]["coverage_id"]
        coverage = PageReviewRepository(session).get_coverage(coverage_id)
        assert coverage.entries[0].lane_failures
    runner.run_job(job.job_id)
    assert len(calls["main-A"]) == 1
    assert len(calls["main-B"]) == 2
