from __future__ import annotations

import json
from datetime import timedelta

import pytest

from app.services.page_review_job_executor import PageReviewJobExecutor
from app.evidence.artifacts import ArtifactStore
from app.llm.page_review_harness import PageCompletion, PageReviewHarnessError
from app.services.page_review_job_service import PAGE_REVIEW_JOB_TYPE, PageReviewJobService
from app.storage.models import JobRecord
from app.workflow.errors import StepFailure
from app.workflow.runner import StepContext
from app.workflow.runner import JobRunner
from app.workflow.jobstore import JobStore
from app.storage.page_review_repository import PageReviewRepository
from tests.v2.services.test_fact_normalization_persistence import _seed_chain
from tests.v2.services.test_page_review_execution import _fact_payload, _routes


@pytest.mark.parametrize("cancel_requested", [False, True])
def test_restart_before_reconciliation_reuses_committed_reads(session_factory, data_paths, cancel_requested):
    from app.storage.codecs import utc_now
    from app.workflow.recovery import recover_expired_jobs

    class ProcessDeath(BaseException):
        pass

    prefix = "r3-restart-reconcile"
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix=prefix)
    artifacts = ArtifactStore(data_paths)
    artifacts.put("page_image", f"{prefix}-page-input".encode())
    routes = _routes()
    job = PageReviewJobService(session_factory).enqueue(
        subject_id=chain["subject_id"], review_episode_id=chain["episode_id"], routes=routes)
    calls = []

    async def completion(route, *_args):
        calls.append(route.lane.value)
        return PageCompletion(_fact_payload(), "stop", {})

    executor = PageReviewJobExecutor(session_factory, artifacts, routes, completion=completion)

    def interrupted(context):
        if context.step_id == "reconcile:0":
            raise ProcessDeath()
        return executor(context)

    with pytest.raises(ProcessDeath):
        JobRunner(session_factory, {PAGE_REVIEW_JOB_TYPE: interrupted}).run_job(job.job_id)
    with session_factory() as session, session.begin():
        store = JobStore(session)
        assert store.get_job(job.job_id).state == "running"
        preserved = {lane: store.get_last_checkpoint(job.job_id, f"read:0:{lane}")
                     for lane in ("main-A", "main-B")}
        assert all(preserved.values())
        assert store.get_last_checkpoint(job.job_id, "coverage") is None
        if cancel_requested:
            store.request_cancel(job.job_id)
        session.get(JobRecord, job.job_id).lease_expires_at = utc_now() - timedelta(seconds=1)
    report = recover_expired_jobs(session_factory)
    if cancel_requested:
        assert job.job_id in report.cancelled_jobs
        assert job.job_id not in report.requeued_jobs
        with session_factory() as session, session.begin():
            store = JobStore(session)
            assert store.get_job(job.job_id).state == "cancelled"
            store.resume_cancelled(job.job_id)
    else:
        assert job.job_id in report.requeued_jobs
    fresh_executor = PageReviewJobExecutor(session_factory, artifacts, routes, completion=completion)
    assert JobRunner(session_factory, {PAGE_REVIEW_JOB_TYPE: fresh_executor},
                     worker_id="restarted-worker").run_job(job.job_id)
    with session_factory() as session:
        store = JobStore(session)
        assert store.get_job(job.job_id).state == "completed"
        assert store.get_last_checkpoint(job.job_id, "coverage") is not None
        for lane, receipt in preserved.items():
            assert store.get_last_checkpoint(job.job_id, f"read:0:{lane}") == receipt
            assert calls.count(lane) == 1


def test_unknown_finish_persists_failed_coverage_not_a_successful_read(session_factory, data_paths):
    prefix = "r3-unknown-finish"
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix=prefix)
    artifacts = ArtifactStore(data_paths)
    artifacts.put("page_image", f"{prefix}-page-input".encode())
    routes = _routes()
    job = PageReviewJobService(session_factory).enqueue(
        subject_id=chain["subject_id"], review_episode_id=chain["episode_id"], routes=routes)

    async def completion(route, *_args):
        return PageCompletion(_fact_payload(), None if route.lane.value == "main-B" else "stop", {})

    executor = PageReviewJobExecutor(session_factory, artifacts, routes, completion=completion)
    assert JobRunner(session_factory, {PAGE_REVIEW_JOB_TYPE: executor}).run_job(job.job_id)
    with session_factory() as session:
        store = JobStore(session)
        receipt = store.get_last_checkpoint(job.job_id, "read:0:main-B")[1]
        assert "page_review_id" not in receipt
        assert receipt["response_attempts"][0]["finish_reason"] is None
        coverage_id = store.get_last_checkpoint(job.job_id, "coverage")[1]["coverage_id"]
        entry, = PageReviewRepository(session).get_coverage(coverage_id).entries
        assert entry.disposition.value == "failed_pending_reread"
        assert entry.lane_failures[0].lane.value == "main-B"


@pytest.mark.parametrize("malformed", [False, True])
def test_main_read_raw_response_is_retained_even_when_schema_rejected(session_factory, data_paths, malformed):
    prefix = "r3-main-receipt"
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix=prefix)
    artifacts = ArtifactStore(data_paths)
    artifacts.put("page_image", f"{prefix}-page-input".encode())
    routes = _routes()
    job = PageReviewJobService(session_factory).enqueue(
        subject_id=chain["subject_id"], review_episode_id=chain["episode_id"], routes=routes)
    raw = '{"unexpected": true}' if malformed else _fact_payload()

    async def completion(route, *_args):
        if route.lane.value == "main-B":
            return PageCompletion(raw, "stop", {"completion_tokens": 17},
                                  output_lengths={"content_characters": len(raw), "reasoning_content_characters": 90})
        return PageCompletion(_fact_payload(), "stop", {})

    executor = PageReviewJobExecutor(session_factory, artifacts, routes, completion=completion)
    assert JobRunner(session_factory, {PAGE_REVIEW_JOB_TYPE: executor}).run_job(job.job_id)
    with session_factory() as session:
        receipt = JobStore(session).get_last_checkpoint(job.job_id, "read:0:main-B")[1]
        if malformed:
            assert "page_review_id" not in receipt
            # 一次性格式纠正重读仍失败：两次真实模型调用都留有请求与响应凭据。
            assert len(receipt["response_attempts"]) == 2
            repair_request = json.loads(artifacts.read_by_sha(
                "raw_request", receipt["response_attempts"][1]["request_sha256"]))
            assert len(repair_request["messages"]) == 3
            assert "format_repair" in repair_request["messages"][2]["content"]
        else:
            assert receipt["page_review_id"]
            assert len(receipt["response_attempts"]) == 1
        for attempt in receipt["response_attempts"]:
            assert attempt["lane"] == "main-B"
            assert attempt["usage"] == {"completion_tokens": 17}
            assert attempt["output_lengths"] == {"content_characters": len(raw), "reasoning_content_characters": 90}
            assert artifacts.read_by_sha("raw_response", attempt["response_sha256"]).decode() == raw


@pytest.mark.parametrize("field", ["contract", "main_prompt_version", "reconciliation_version", "page_review_contract_version", "transport_version"])
def test_changed_execution_contract_is_rejected_before_artifact_or_model_access(session_factory, field):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="r3-executor-version")
    routes = _routes()
    job = PageReviewJobService(session_factory).enqueue(
        subject_id=chain["subject_id"], review_episode_id=chain["episode_id"], routes=routes,
    )
    with session_factory() as session:
        payload = json.loads(session.get(JobRecord, job.job_id).payload_json)
    payload[field] = "historical-version"

    class NoArtifactAccess:
        def read_by_sha(self, *_args):
            pytest.fail("version mismatch must not read artifacts")

    async def no_completion(*_args):
        pytest.fail("version mismatch must not call a model")

    executor = PageReviewJobExecutor(session_factory, NoArtifactAccess(), routes, completion=no_completion)
    context = StepContext(job_id=job.job_id, job_type=PAGE_REVIEW_JOB_TYPE,
                          job_payload=payload, step_id="read:0:main-A", name="test",
                          attempt=1, last_checkpoint_id=None, last_checkpoint=None)
    with pytest.raises(StepFailure) as caught:
        executor(context)
    assert caught.value.error_code == "R3_EXECUTION_VERSION_CHANGED"
    assert not caught.value.retryable


@pytest.mark.parametrize("source_assisted", [False, True])
@pytest.mark.parametrize("native_local", [False, True])
def test_runner_persists_each_read_and_closed_coverage(session_factory, data_paths, source_assisted, native_local, monkeypatch):
    prefix = "r3-executor-complete"
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix=prefix)
    artifacts = ArtifactStore(data_paths)
    artifacts.put("page_image", f"{prefix}-page-input".encode())
    routes = _routes()
    if native_local:
        from dataclasses import replace
        from app.domain.contracts.page_review import PageReviewLane
        routes[PageReviewLane.MAIN_B] = replace(
            routes[PageReviewLane.MAIN_B], provider="mtplx", model="mtplx-flash-next-optimized-speed",
            reasoning_effort="xhigh",
        )
    job = PageReviewJobService(session_factory).enqueue(
        subject_id=chain["subject_id"], review_episode_id=chain["episode_id"], routes=routes,
    )
    calls = []
    from threading import Barrier
    both_readers_started = Barrier(2)

    async def completion(route, *_args):
        both_readers_started.wait(timeout=5)
        calls.append(route.lane.value)
        response = json.loads(_fact_payload())
        if source_assisted:
            fact = response["facts"][0]
            fact.update(field_name="ALT", raw_text="ALT 5.6 mmol/L", raw_value="5.6 mmol/L",
                        region={"excerpt": "ALT 5.6 mmol/L"},
                        context={"target_text": "ALT", "polarity": "asserted",
                                 "location_text": route.lane.value})
            for key in ("normalized_value", "normalized_unit", "normalization_key"):
                fact.pop(key)
        from app.llm.page_review_transport_options import page_transport_contract
        return PageCompletion(json.dumps(response), "stop", {}, transport_contract=page_transport_contract(route.provider))

    executor = PageReviewJobExecutor(session_factory, artifacts, routes, completion=completion)
    assert JobRunner(session_factory, {PAGE_REVIEW_JOB_TYPE: executor}).run_job(job.job_id)
    with session_factory() as session:
        store = JobStore(session)
        coverage_checkpoint = store.get_last_checkpoint(job.job_id, "coverage")
        assert coverage_checkpoint is not None
        repository = PageReviewRepository(session)
        coverage = repository.get_coverage(coverage_checkpoint[1]["coverage_id"])
        assert coverage.expected_page_artifact_ids == [chain["page_artifact_id"]]
        assert coverage.entries[0].disposition.value == "accepted"
        reconciliation = repository.get_reconciliation(coverage.entries[0].reconciliation_id)
        payload = json.loads(session.get(JobRecord, job.job_id).payload_json)
        frozen_source = payload["association_sources"][chain["page_artifact_id"]]
        assert reconciliation.association_text_sha256 == frozen_source["text_sha256"]
        assert len(reconciliation.accepted_fact_keys) == (2 if source_assisted else 1)
        for lane in ("main-A", "main-B"):
            receipt = store.get_last_checkpoint(job.job_id, f"read:0:{lane}")
            assert repository.get_review(receipt[1]["page_review_id"]).lane.value == lane
        from hashlib import sha256
        from app.domain.contracts.facts import FactAuthority
        from app.services.page_review_coverage_selection import select_normalizer_coverage, PageCoverageNotReady
        from app.services import page_association_sources as source_service
        from app.storage.evidence_locator_repositories import CompleteEvidenceProcessingRevisionRepository
        authority = FactAuthority.model_validate(payload["authority"])
        assert select_normalizer_coverage(session, authority) == coverage.coverage_id
        from app.services.page_review_job_service import main_reader_identity
        reader_identity = main_reader_identity(routes)
        assert coverage.main_reader_identity_sha256 == reader_identity
        historical = coverage.model_dump(mode="json")
        historical.pop("main_reader_identity_sha256")
        assert type(coverage).model_validate(historical).model_dump(mode="json") == historical
        with session.begin_nested() as nested:
            other_route = coverage.model_dump(mode="json")
            other_route.update(coverage_id="other-reader-combination", main_reader_identity_sha256="a" * 64)
            repository.save_coverage(type(coverage).model_validate(other_route))
            assert select_normalizer_coverage(session, authority,
                main_reader_identity_sha256=reader_identity) == coverage.coverage_id
            with pytest.raises(PageCoverageNotReady):
                select_normalizer_coverage(session, authority, main_reader_identity_sha256="b" * 64)
            nested.rollback()
        from app.domain.contracts.page_review import SubjectPageCoverage
        failed_history = coverage.model_dump(mode="json")
        failed_history["coverage_id"] = "older-failed-coverage"
        failed_history["entries"][0].update(
            disposition="failed_pending_reread", reconciliation_id=None,
            lane_failures=[{"lane": "main-B", "failure_kind": "schema"}])
        repository.save_coverage(SubjectPageCoverage.model_validate(failed_history))
        assert select_normalizer_coverage(session, authority) == coverage.coverage_id
        with session.begin_nested() as nested:
            competing = coverage.model_dump(mode="json")
            competing["coverage_id"] = "another-successful-coverage"
            repository.save_coverage(SubjectPageCoverage.model_validate(competing))
            with pytest.raises(PageCoverageNotReady, match="唯一"):
                select_normalizer_coverage(session, authority)
            with pytest.raises(PageCoverageNotReady, match="唯一"):
                select_normalizer_coverage(session, authority, main_reader_identity_sha256=reader_identity)
            nested.rollback()
        with session.begin_nested() as nested:
            from app.storage.repositories import ScopeViolationError
            successor = dict(failed_history, coverage_id="failed-successor",
                             predecessor_coverage_id=coverage.coverage_id)
            with pytest.raises(ScopeViolationError, match="没有失败页面"):
                repository.save_coverage(SubjectPageCoverage.model_validate(successor))
            nested.rollback()
        sources = source_service.page_association_sources(
            session, CompleteEvidenceProcessingRevisionRepository(session).get(authority.complete_processing_revision_id))
        changed_text = sources[chain["page_artifact_id"]].text + "\n来源变化"
        sources[chain["page_artifact_id"]] = sources[chain["page_artifact_id"]].model_copy(update={
            "text": changed_text, "text_sha256": sha256(changed_text.encode()).hexdigest()})
        monkeypatch.setattr(source_service, "page_association_sources", lambda *_args: sources)
        with pytest.raises(PageCoverageNotReady, match="不一致"):
            select_normalizer_coverage(session, authority)
    assert sorted(calls) == ["main-A", "main-B"]


@pytest.mark.parametrize("failure_kind,expected_calls", [
    ("endpoint", 2), ("length", 2), ("content_filter", 1), ("schema", 2),
])
def test_failed_lane_retains_successful_read_and_failed_page_coverage(session_factory, data_paths, failure_kind, expected_calls):
    prefix = "r3-executor-failure"
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix=prefix)
    artifacts = ArtifactStore(data_paths)
    artifacts.put("page_image", f"{prefix}-page-input".encode())
    routes = _routes()
    job = PageReviewJobService(session_factory).enqueue(
        subject_id=chain["subject_id"], review_episode_id=chain["episode_id"], routes=routes)
    calls = []

    async def completion(route, *_args):
        calls.append(route.lane.value)
        if route.lane.value == "main-B":
            if failure_kind == "endpoint":
                raise PageReviewHarnessError("unavailable", failure_kind="endpoint")
            if failure_kind == "schema":
                return PageCompletion(json.dumps({"unexpected": True}), "stop", {})
            return PageCompletion("{}", failure_kind, {})
        return PageCompletion(_fact_payload(), "stop", {})

    executor = PageReviewJobExecutor(session_factory, artifacts, routes, completion=completion)
    runner = JobRunner(session_factory, {PAGE_REVIEW_JOB_TYPE: executor}, backoff=lambda _: timedelta(0))
    for _ in range(3):
        with session_factory() as session, session.begin():
            JobStore(session).requeue_due_retries()
        runner.run_job(job.job_id)
    with session_factory() as session:
        store = JobStore(session)
        receipt = store.get_last_checkpoint(job.job_id, "coverage")
        assert receipt is not None
        repository = PageReviewRepository(session)
        coverage = repository.get_coverage(receipt[1]["coverage_id"])
        assert coverage.entries[0].disposition.value == "failed_pending_reread"
        assert coverage.entries[0].lane_failures[0].lane.value == "main-B"
        assert coverage.entries[0].lane_failures[0].failure_kind == failure_kind
        attempts = store.get_last_checkpoint(job.job_id, "read:0:main-B")[1]["response_attempts"]
        assert len(attempts) == (1 if failure_kind == "endpoint" else expected_calls)
        for attempt in attempts:
            if failure_kind == "endpoint":
                raw = artifacts.read_by_sha("raw_response", attempt["error_receipt_sha256"])
                failure = json.loads(raw)
                assert failure["job_id"] == job.job_id
                assert failure["lane"] == "main-B"
                assert failure["error_type"] == "PageReviewHarnessError"
                assert "unavailable" not in raw.decode()
            else:
                raw = artifacts.read_by_sha("raw_response", attempt["response_sha256"]).decode()
                assert json.loads(raw) == ({"unexpected": True} if failure_kind == "schema" else {})
            assert attempt["elapsed_seconds"] >= 0
        if failure_kind == "length":
            assert attempts[1]["max_tokens"] == 2 * attempts[0]["max_tokens"]
        assert store.get_last_checkpoint(job.job_id, "read:0:main-A") is not None
    if failure_kind == "endpoint":
        failures = []
        for path in (data_paths.root / "artifacts" / "raw_response").iterdir():
            value = json.loads(artifacts.read_by_sha("raw_response", path.name))
            if value.get("job_id") == job.job_id and value.get("lane") == "main-B":
                failures.append(value)
        assert len(failures) == expected_calls
        assert {value["step_attempt"] for value in failures} == {1, 2}
    assert calls.count("main-A") == 1
    assert calls.count("main-B") == expected_calls


def test_cancel_at_read_boundary_then_resume_preserves_committed_reads(session_factory, data_paths):
    prefix = "r3-cancel-resume"
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix=prefix)
    artifacts = ArtifactStore(data_paths)
    artifacts.put("page_image", f"{prefix}-page-input".encode())
    routes = _routes()
    job = PageReviewJobService(session_factory).enqueue(
        subject_id=chain["subject_id"], review_episode_id=chain["episode_id"], routes=routes)
    calls = []

    async def completion(route, *_args):
        calls.append(route.lane.value)
        if route.lane.value == "main-A" and calls.count("main-A") == 1:
            with session_factory() as session, session.begin():
                JobStore(session).request_cancel(job.job_id)
        return PageCompletion(_fact_payload(), "stop", {})

    runner = JobRunner(session_factory, {PAGE_REVIEW_JOB_TYPE: PageReviewJobExecutor(
        session_factory, artifacts, routes, completion=completion)})
    runner.run_job(job.job_id)
    with session_factory() as session, session.begin():
        store = JobStore(session)
        assert store.get_job(job.job_id).state == "cancelled"
        assert store.get_last_checkpoint(job.job_id, "coverage") is None
        preserved = {lane: store.get_last_checkpoint(job.job_id, f"read:0:{lane}")
                     for lane in ("main-A", "main-B")}
        assert any(receipt is not None for receipt in preserved.values())
        before_calls = list(calls)
        store.resume_cancelled(job.job_id)
    runner.run_job(job.job_id)
    with session_factory() as session:
        store = JobStore(session)
        assert store.get_job(job.job_id).state == "completed"
        assert store.get_last_checkpoint(job.job_id, "coverage") is not None
        for lane, receipt in preserved.items():
            if receipt is not None:
                assert store.get_last_checkpoint(job.job_id, f"read:0:{lane}") == receipt
                assert calls.count(lane) == before_calls.count(lane)
