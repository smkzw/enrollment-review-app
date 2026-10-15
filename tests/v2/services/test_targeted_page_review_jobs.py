import json

import pytest

from app.evidence.artifacts import ArtifactStore
from app.llm.page_review_harness import PageCompletion
from app.services.page_review_job_executor import PageReviewJobExecutor
from app.services.page_review_job_service import PAGE_REVIEW_JOB_TYPE, PageReviewJobService
from app.services.targeted_page_review_executor import TargetedPageReviewExecutor
from app.services.targeted_page_review_jobs import TARGETED_REVIEW_JOB_TYPE, enqueue_targeted_review
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner
from tests.v2.services.test_fact_normalization_persistence import _seed_chain
from tests.v2.services.test_page_review_execution import _fact_payload, _routes


def response(value, handwriting=False):
    payload = json.loads(_fact_payload())
    if handwriting:
        from tests.v2.domain.test_page_review_contracts import _handwriting
        note = _handwriting().model_dump(mode="json")
        note.update(raw_text=value, region={"excerpt": value})
        note.pop("normalized_text")
        note.pop("normalization_key")
        payload.update(facts=[], handwriting=[note], clause_signals=[])
        if handwriting == "mixed":
            payload["facts"] = json.loads(response("4.2" if value == "CS" else "5.2").text)["facts"]
        return PageCompletion(json.dumps(payload), "stop", {})
    fact = payload["facts"][0]
    fact.update(raw_value=value, raw_text=f"检查值 {value}", region={"excerpt": f"检查值 {value}"})
    for key in ("normalized_value", "normalized_unit", "normalization_key"):
        fact.pop(key)
    return PageCompletion(json.dumps(payload), "stop", {})


def test_text_summary_difference_does_not_start_value_reread(session_factory, data_paths):
    from app.services.targeted_page_review_jobs import TargetedReviewNotReady
    prefix = "targeted-text"
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix=prefix)
    artifacts = ArtifactStore(data_paths)
    artifacts.put("page_image", f"{prefix}-page-input".encode())
    routes = _routes()
    original = PageReviewJobService(session_factory).enqueue(subject_id=chain["subject_id"],
        review_episode_id=chain["episode_id"], routes=routes)

    async def completion(route, *_args):
        return response("某药10mg每日一次治疗" if route.lane.value == "main-A" else "某药10mg每日一次")

    JobRunner(session_factory, {PAGE_REVIEW_JOB_TYPE: PageReviewJobExecutor(
        session_factory, artifacts, routes, completion=completion)}).run_job(original.job_id)
    with pytest.raises(TargetedReviewNotReady):
        enqueue_targeted_review(session_factory, original_job_id=original.job_id, page_index=0,
            subject_id=chain["subject_id"], review_episode_id=chain["episode_id"], routes=routes)


@pytest.mark.parametrize("time_found", [True, False])
def test_one_sided_missing_time_can_enter_durable_reread(session_factory, data_paths, time_found):
    prefix = "targeted-time-gap"
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix=prefix)
    artifacts = ArtifactStore(data_paths)
    artifacts.put("page_image", f"{prefix}-page-input".encode())
    routes = _routes()
    original = PageReviewJobService(session_factory).enqueue(subject_id=chain["subject_id"],
        review_episode_id=chain["episode_id"], routes=routes)

    async def completion(route, *_args):
        payload = json.loads(response("4.2").text)
        payload["facts"][0]["context"]["time_text"] = (
            "2026-01-17" if route.lane.value == "main-A" else None)
        return PageCompletion(json.dumps(payload), "stop", {})

    assert JobRunner(session_factory, {PAGE_REVIEW_JOB_TYPE: PageReviewJobExecutor(
        session_factory, artifacts, routes, completion=completion)}).run_job(original.job_id)
    with session_factory() as session:
        before = JobStore(session).get_last_checkpoint(original.job_id, "coverage")
    kwargs = dict(original_job_id=original.job_id, page_index=0, subject_id=chain["subject_id"],
                  review_episode_id=chain["episode_id"], routes=routes)
    job = enqueue_targeted_review(session_factory, **kwargs)
    assert enqueue_targeted_review(session_factory, **kwargs).job_id == job.job_id
    with session_factory() as session:
        store = JobStore(session)
        payload = json.loads(store.get_job(job.job_id).payload_json)
        assert payload["focus"]["targets"]
        assert payload["focus"]["round_number"] == 1
        assert store.get_last_checkpoint(original.job_id, "coverage") == before
    calls = []

    async def reread(route, *_args):
        calls.append(route.lane.value)
        payload = json.loads(response("4.2").text)
        payload["facts"][0]["context"]["time_text"] = "2026-01-17" if time_found else None
        return PageCompletion(json.dumps(payload), "stop", {})

    runner = JobRunner(session_factory, {TARGETED_REVIEW_JOB_TYPE: TargetedPageReviewExecutor(
        session_factory, artifacts, routes, completion=reread)})
    assert runner.run_job(job.job_id)
    with session_factory() as session:
        store = JobStore(session)
        outcome = store.get_last_checkpoint(job.job_id, "compare:2")[1]
        assert outcome["candidate_auto_accept"] is False
        assert outcome["requires_user_review"] is (not time_found)
        assert bool(outcome["pending_targets"]) is (not time_found)
        assert store.get_last_checkpoint(original.job_id, "coverage") == before
    assert len(calls) == (2 if time_found else 4)
    assert enqueue_targeted_review(session_factory, **kwargs).job_id == job.job_id
    runner.run_job(job.job_id)
    assert len(calls) == (2 if time_found else 4)


@pytest.mark.parametrize("resolves", [True, False, "failure"])
@pytest.mark.parametrize("restart", [True, False])
@pytest.mark.parametrize("handwriting", [False, True, "mixed"])
def test_durable_round_limit_and_no_original_rewrite(session_factory, data_paths, resolves, restart, handwriting, monkeypatch):
    prefix = "targeted-review"
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix=prefix)
    artifacts = ArtifactStore(data_paths)
    artifacts.put("page_image", f"{prefix}-page-input".encode())
    routes = _routes()

    async def original_completion(route, *_args):
        value = ("CS" if route.lane.value == "main-A" else "NCS") if handwriting else (
            "4.2" if route.lane.value == "main-A" else "5.2")
        return response(value, handwriting)

    original = PageReviewJobService(session_factory).enqueue(subject_id=chain["subject_id"],
        review_episode_id=chain["episode_id"], routes=routes)
    assert JobRunner(session_factory, {PAGE_REVIEW_JOB_TYPE: PageReviewJobExecutor(
        session_factory, artifacts, routes, completion=original_completion)}).run_job(original.job_id)
    with session_factory() as session:
        before = JobStore(session).get_last_checkpoint(original.job_id, "coverage")
    kwargs = dict(original_job_id=original.job_id, page_index=0, subject_id=chain["subject_id"],
                  review_episode_id=chain["episode_id"], routes=routes)
    job = enqueue_targeted_review(session_factory, **kwargs)
    assert enqueue_targeted_review(session_factory, **kwargs).job_id == job.job_id
    calls = []

    async def reread(route, *_args):
        assert route.reasoning_effort == "high"
        calls.append(route.lane.value)
        if resolves == "failure" and route.lane.value == "main-B":
            return PageCompletion("{}", "stop", {})
        value = ("CS" if resolves or route.lane.value == "main-A" else "NCS") if handwriting else (
            "4.2" if resolves or route.lane.value == "main-A" else "5.2")
        return response(value, handwriting)

    executor = TargetedPageReviewExecutor(session_factory, artifacts, routes, completion=reread)
    if restart:
        from datetime import timedelta
        from app.storage.codecs import utc_now
        from app.storage.models import JobRecord
        from app.workflow.recovery import recover_expired_jobs

        class ProcessDeath(BaseException):
            pass

        def interrupted(context):
            if context.step_id == "compare:1":
                raise ProcessDeath()
            return executor(context)

        with pytest.raises(ProcessDeath):
            JobRunner(session_factory, {TARGETED_REVIEW_JOB_TYPE: interrupted}).run_job(job.job_id)
        with session_factory() as session, session.begin():
            session.get(JobRecord, job.job_id).lease_expires_at = utc_now() - timedelta(seconds=1)
        assert job.job_id in recover_expired_jobs(session_factory).requeued_jobs
    runner = JobRunner(session_factory, {TARGETED_REVIEW_JOB_TYPE: executor})
    assert runner.run_job(job.job_id)
    with session_factory() as session:
        store = JobStore(session)
        assert store.get_job(job.job_id).state == "completed"
        summary = store.get_last_checkpoint(job.job_id, "compare:2")[1]
        assert summary["candidate_auto_accept"] is False
        assert bool(summary["handwriting_pending"] if handwriting else summary["pending_targets"]) == (resolves is not True)
        assert summary["clinical_findings_allowed"] is False
        if resolves == "failure":
            assert summary["outcome_kind"] == "conflict_preserved_read_failed"
            assert summary["read_failures"]
            assert "professional_judgment" not in json.dumps(summary)
        assert store.get_last_checkpoint(original.job_id, "coverage") == before
        assert store.get_last_checkpoint(job.job_id, "coverage") is None
    # failure 场景中 format 失败的一读消耗一次性格式纠正重读，多计一次调用。
    expected_calls = (2 if resolves is True else 3 if resolves == "failure" else 4)
    assert len(calls) == expected_calls
    if handwriting:
        from app.services.targeted_page_review_detail import targeted_review_evidence
        detail = targeted_review_evidence(session_factory, subject_id=chain["subject_id"],
            review_episode_id=chain["episode_id"], job_id=job.job_id)
        notes = [item for item in detail.excerpts if item.field_name == "临床意义批注"]
        assert notes
        assert {item.raw_value for item in notes} <= {"CS", "NCS"}
    assert enqueue_targeted_review(session_factory, **kwargs).job_id == job.job_id
    runner.run_job(job.job_id)
    assert len(calls) == expected_calls
    from app.services import targeted_page_review_jobs as module
    monkeypatch.setattr(module, "TARGETED_REVIEW_VERSION", "different-contract")
    with pytest.raises(module.TargetedReviewNotReady, match="不同版本"):
        enqueue_targeted_review(session_factory, **kwargs)
    assert len(calls) == expected_calls
