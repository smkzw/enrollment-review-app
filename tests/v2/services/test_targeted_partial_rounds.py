"""Keep complete same-round agreements when a different target needs round two."""

import json

import pytest

from app.evidence.artifacts import ArtifactStore
from app.llm.page_review_harness import PageCompletion
from app.services.page_review_job_executor import PageReviewJobExecutor
from app.services.page_review_job_service import PAGE_REVIEW_JOB_TYPE, PageReviewJobService
from app.services.targeted_page_review_executor import TargetedPageReviewExecutor
from app.services.targeted_page_review_jobs import TARGETED_REVIEW_JOB_TYPE, enqueue_targeted_review
from app.services.targeted_page_review_status import targeted_review_status
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner
from tests.v2.services.test_fact_normalization_persistence import _seed_chain
from tests.v2.services.test_page_review_execution import _routes
from tests.v2.services.test_targeted_page_review_jobs import response


def _response(values):
    payload = json.loads(response("4.2").text)
    facts = []
    for name, value in values.items():
        fact = json.loads(response(value).text)["facts"][0]
        fact.update(observation_id=name, field_name=name, raw_text=f"{name} {value}", region={"excerpt": f"{name} {value}"})
        fact["context"]["target_text"] = name
        facts.append(fact)
    payload.update(facts=facts, clause_signals=[])
    return PageCompletion(json.dumps(payload), "stop", {})


@pytest.mark.parametrize("second_resolves", [True, False])
def test_partial_first_round_agreement_survives_second_round(session_factory, data_paths, second_resolves):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="partial-round")
    artifacts = ArtifactStore(data_paths)
    artifacts.put("page_image", b"partial-round-page-input")
    routes = _routes()

    async def original_read(route, *_args):
        value = "4.2" if route.lane.value == "main-A" else "5.2"
        return _response({"项目甲": value, "项目乙": value})

    original = PageReviewJobService(session_factory).enqueue(subject_id=chain["subject_id"],
        review_episode_id=chain["episode_id"], routes=routes)
    assert JobRunner(session_factory, {PAGE_REVIEW_JOB_TYPE: PageReviewJobExecutor(
        session_factory, artifacts, routes, completion=original_read)}).run_job(original.job_id)
    job = enqueue_targeted_review(session_factory, original_job_id=original.job_id, page_index=0,
        subject_id=chain["subject_id"], review_episode_id=chain["episode_id"], routes=routes)
    calls = []

    async def reread(route, messages, *_args):
        focus = json.loads(messages[-1]["content"])
        calls.append((route.lane.value, focus["targets"]))
        value = "4.2" if route.lane.value == "main-A" or (len(calls) > 2 and second_resolves) else "5.2"
        if len(calls) > 2 and not second_resolves:
            value = "5.2" if route.lane.value == "main-A" else "4.2"
        return _response({name: "4.2" if name == "项目甲" else value for name in focus["targets"]})

    assert JobRunner(session_factory, {TARGETED_REVIEW_JOB_TYPE: TargetedPageReviewExecutor(
        session_factory, artifacts, routes, completion=reread)}).run_job(job.job_id)
    status = targeted_review_status(session_factory, subject_id=chain["subject_id"],
        review_episode_id=chain["episode_id"], job_id=job.job_id)
    outcome = status["outcome"]
    assert set(outcome["agreed_candidate_targets"]) == ({"项目甲", "项目乙"} if second_resolves else {"项目甲"})
    assert outcome["pending_targets"] == ([] if second_resolves else ["项目乙"])
    assert outcome["candidate_auto_accept"] is False
    assert outcome["agreed_candidate_rounds"] == ({"项目甲": 1, "项目乙": 2} if second_resolves else {"项目甲": 1})
    assert len(calls) == 4
    assert all(targets == ["项目乙"] for _, targets in calls[2:])
    with session_factory() as session:
        assert JobStore(session).get_last_checkpoint(job.job_id, "coverage") is None
