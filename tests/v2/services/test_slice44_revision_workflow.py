"""Slice 4.4 完整处理修订构建工作流测试（WP-44B）。

覆盖候选状态机（staged→processing→ready / needs_attention / retryable_failure）、
闭包冻结、幂等键回放/冲突、故障注入不留下可激活半闭包根，以及候选失败/待核对
不触碰审核节点活动指针（§5.4 候选隔离）。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest

from app.domain.contracts.enums import (
    EvidenceProcessingCandidateStatus,
    OcrRiskLevel,
    OcrRiskReviewDecision,
    SnapshotStatus,
)
from app.domain.contracts.evidence_locator import OCRRiskReview
from app.services.evidence_activation_service import EvidenceActivationService
from app.services.evidence_revision_workflow import (
    BuildNeedsAttentionError,
    BuildRetryableFailureError,
    EvidenceRevisionBuildRequest,
    EvidenceRevisionWorkflow,
)
from app.services.evidence_risk_service import EvidenceRiskScanService
from app.storage.evidence_locator_repositories import (
    CandidateIdempotencyConflictError,
    CompleteEvidenceProcessingRevisionRepository,
    EvidenceLocatorRepository,
    EvidenceProcessingCandidateRepository,
    OCRRiskReviewRepository,
)
from app.storage.evidence_repositories import EvidenceSnapshotRepository
from app.storage.repositories import EpisodeRepository
from tests.v2.storage.test_slice44_repositories import (
    FIXED_UTC,
    _locator,
    _seed_metadata,
)


@pytest.fixture
def stack(revision_stack):
    session, fixture, keys = revision_stack
    session.commit()
    return session, fixture, keys

def _request(keys, **overrides):
    base = {
        "evidence_snapshot_id": "snap-1",
        "base_processing_revision_id": "rev-1",
        "project_id": keys["project_id"],
        "subject_id": keys["subject_id"],
        "review_episode_id": keys["episode_id"],
        "expected_revision": 1,
        "idempotency_key": "key-1",
        "created_by": "tester",
    }
    base.update(overrides)
    return EvidenceRevisionBuildRequest(**base)

def _prepare_reviewed_closure(session_factory, keys, *, review=True):
    """预置元数据链头 + 每页风险扫描 + blocking 风险核对，供工作流成功构建。"""
    with session_factory() as s, s.begin():
        _seed_metadata(s, keys)
    risk = EvidenceRiskScanService(session_factory)
    scan = risk.scan_page("op-1")
    if review:
        with session_factory() as s, s.begin():
            review_repo = OCRRiskReviewRepository(s)
            for flag in scan.flags:
                if flag.level == OcrRiskLevel.BLOCKING:
                    review_repo.create(
                        OCRRiskReview(
                            review_id=f"rv-{flag.risk_id}",
                            risk_flag_id=f"{scan.scan_id}:{flag.risk_id}",
                            decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
                            reason="已核对",
                            actor="tester",
                            base_processing_revision_id="rev-1",
                            expected_revision=1,
                            created_at=FIXED_UTC,
                        )
                    )
    return scan

def test_workflow_start_creates_processing_candidate(stack, session_factory):
    _session, _fixture, keys = stack
    workflow = EvidenceRevisionWorkflow(session_factory)
    candidate = workflow.start(_request(keys))
    assert candidate.status == EvidenceProcessingCandidateStatus.PROCESSING
    assert candidate.base_processing_revision_id == "rev-1"

def test_workflow_run_build_freeze_closure_ready(stack, session_factory):
    _session, _fixture, keys = stack
    scan = _prepare_reviewed_closure(session_factory, keys)
    workflow = EvidenceRevisionWorkflow(session_factory)
    candidate = workflow.start(_request(keys))
    built = workflow.run_build(candidate.candidate_id)
    assert built.status == EvidenceProcessingCandidateStatus.READY
    with session_factory() as fresh:
        assert (
            EvidenceSnapshotRepository(fresh).current_status("snap-1")
            == SnapshotStatus.READY
        )
        complete = CompleteEvidenceProcessingRevisionRepository(fresh)
        revisions = complete.list_by_snapshot("snap-1")
        assert len(revisions) == 1
        rev = revisions[0]
        assert rev.metadata_revision_ids == ["mdr-1"]
        assert rev.risk_scan_ids == [scan.scan_id]
        assert rev.risk_review_ids != []
        assert rev.is_activatable is True
        # 闭包哈希在读取时重算通过（revisions 已全量校验）。
        assert rev.completion_manifest_sha256


def test_workflow_freezes_started_locator_input_and_replays_ready_candidate(
    stack, session_factory
):
    _session, _fixture, keys = stack
    with session_factory() as session, session.begin():
        EvidenceLocatorRepository(session).create(
            _locator(keys, locator_id="loc-frozen")
        )
    _prepare_reviewed_closure(session_factory, keys)
    workflow = EvidenceRevisionWorkflow(session_factory)
    candidate = workflow.start(
        _request(keys, selected_locator_ids=["loc-frozen"])
    )
    built = workflow.run_build(candidate.candidate_id)
    replay = workflow.run_build(candidate.candidate_id)
    assert built.complete_revision_id == replay.complete_revision_id
    assert built.selected_locator_ids == ["loc-frozen"]
    with session_factory() as fresh:
        revisions = CompleteEvidenceProcessingRevisionRepository(fresh).list_by_snapshot(
            "snap-1"
        )
        assert len(revisions) == 1
        assert revisions[0].locator_ids == ["loc-frozen"]


def test_build_request_rejects_duplicate_locator_ids():
    with pytest.raises(ValueError, match="定位编号不能重复"):
        EvidenceRevisionBuildRequest(
            evidence_snapshot_id="snapshot-1",
            base_processing_revision_id="base-1",
            project_id="project-1",
            subject_id="subject-1",
            review_episode_id="episode-1",
            expected_revision=1,
            idempotency_key="duplicate-locator",
            created_by="tester",
            selected_locator_ids=["locator-1", "locator-1"],
        )

def test_workflow_unresolved_blocking_enters_needs_attention(stack, session_factory):
    _session, _fixture, keys = stack
    _prepare_reviewed_closure(session_factory, keys, review=False)
    workflow = EvidenceRevisionWorkflow(session_factory)
    candidate = workflow.start(_request(keys))
    with pytest.raises(BuildNeedsAttentionError, match="blocking 风险"):
        workflow.run_build(candidate.candidate_id)
    with session_factory() as fresh:
        from app.storage.evidence_locator_repositories import (
            EvidenceProcessingCandidateRepository,
        )

        got = EvidenceProcessingCandidateRepository(fresh).get(candidate.candidate_id)
        assert got.status == EvidenceProcessingCandidateStatus.NEEDS_ATTENTION
        # 未产生可激活半闭包根。
        assert CompleteEvidenceProcessingRevisionRepository(fresh).list_by_snapshot("snap-1") == []


def test_resumed_candidate_projects_latest_input_hash_for_activation(
    stack, session_factory
):
    """核对后重新排队的输入指纹必须同步到列存投影，否则启用会误拒绝。"""
    _session, _fixture, keys = stack
    scan = _prepare_reviewed_closure(session_factory, keys, review=False)
    workflow = EvidenceRevisionWorkflow(session_factory)
    candidate = workflow.start(_request(keys))
    with pytest.raises(BuildNeedsAttentionError):
        workflow.run_build(candidate.candidate_id)

    with session_factory() as session:
        risk_reviews = []
        with session.begin():
            review_repo = OCRRiskReviewRepository(session)
            for flag in scan.flags:
                if flag.level != OcrRiskLevel.BLOCKING:
                    continue
                review = OCRRiskReview(
                    review_id=f"rv-resume-{flag.risk_id}",
                    risk_flag_id=f"{scan.scan_id}:{flag.risk_id}",
                    decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
                    reason="已核对",
                    actor="tester",
                    base_processing_revision_id="rev-1",
                    expected_revision=1,
                    created_at=FIXED_UTC,
                )
                review_repo.create(review)
                risk_reviews.append(review.review_id)
            current = EvidenceProcessingCandidateRepository(session).get(
                candidate.candidate_id
            )
            resumed = workflow.resume_after_attention_in_session(
                session,
                candidate_id=candidate.candidate_id,
                attempt_manifest=current.attempt_manifest.model_copy(
                    update={"risk_review_ids": sorted(risk_reviews)}
                ),
                actor="tester",
                reason="已完成识别核对",
            )

    workflow.begin_attempt(resumed.candidate_id, actor="tester")
    built = workflow.run_build(resumed.candidate_id)
    outcome = EvidenceActivationService(
        session_factory, keys["artifact_store"]
    ).activate(
        target_snapshot_id="snap-1",
        target_revision_id=built.complete_revision_id,
        expected_revision=1,
        actor="tester",
        reason="已完成资料与识别核对",
        candidate_id=built.candidate_id,
    )
    assert outcome.active_revision_id == built.complete_revision_id

def test_workflow_failure_injection_retryable_no_partial_rows(
    stack, session_factory, monkeypatch
):
    _session, _fixture, keys = stack
    _prepare_reviewed_closure(session_factory, keys)
    workflow = EvidenceRevisionWorkflow(session_factory)
    candidate = workflow.start(_request(keys))

    def _boom(self, revision, **_kwargs):
        from app.storage.evidence_locator_repositories import RevisionClosureError

        raise RevisionClosureError("注入的闭包失败")

    monkeypatch.setattr(
        "app.services.evidence_revision_builder.CompleteEvidenceProcessingRevisionRepository.create",
        _boom,
    )
    with pytest.raises(BuildRetryableFailureError, match="注入"):
        workflow.run_build(candidate.candidate_id)
    monkeypatch.undo()
    with session_factory() as fresh:
        from app.storage.evidence_locator_repositories import (
            EvidenceProcessingCandidateRepository,
        )

        got = EvidenceProcessingCandidateRepository(fresh).get(candidate.candidate_id)
        assert got.status == EvidenceProcessingCandidateStatus.RETRYABLE_FAILURE
        assert CompleteEvidenceProcessingRevisionRepository(fresh).list_by_snapshot("snap-1") == []

def test_workflow_idempotency_same_input_replays(stack, session_factory):
    _session, _fixture, keys = stack
    workflow = EvidenceRevisionWorkflow(session_factory)
    first = workflow.start(_request(keys))
    second = workflow.start(_request(keys))
    assert second.candidate_id == first.candidate_id
    assert second.status == EvidenceProcessingCandidateStatus.PROCESSING

def test_workflow_idempotency_different_input_conflicts(stack, session_factory):
    _session, _fixture, keys = stack
    workflow = EvidenceRevisionWorkflow(session_factory)
    workflow.start(_request(keys))
    with pytest.raises(CandidateIdempotencyConflictError, match="不同输入"):
        workflow.start(_request(keys, base_processing_revision_id="rev-other"))

def test_workflow_failure_leaves_episode_pointers_untouched(stack, session_factory):
    """候选失败/待核对绝不写审核节点活动指针或旧结果（§5.4 候选隔离）。"""
    _session, _fixture, keys = stack
    _prepare_reviewed_closure(session_factory, keys, review=False)
    workflow = EvidenceRevisionWorkflow(session_factory)
    candidate = workflow.start(_request(keys))
    with pytest.raises(BuildNeedsAttentionError):
        workflow.run_build(candidate.candidate_id)
    with session_factory() as fresh:
        episode = EpisodeRepository(fresh).get(keys["episode_id"])
        assert episode.active_evidence_snapshot_id is None
        assert episode.active_evidence_processing_revision_id is None


def test_workflow_unexpected_exception_becomes_retryable(
    stack, session_factory, monkeypatch
):
    _session, _fixture, keys = stack
    _prepare_reviewed_closure(session_factory, keys)
    workflow = EvidenceRevisionWorkflow(session_factory)
    candidate = workflow.start(_request(keys))

    def _boom(*_args, **_kwargs):
        raise RuntimeError("未预期故障")

    monkeypatch.setattr(workflow, "_scan_and_build", _boom)
    with pytest.raises(BuildRetryableFailureError, match="未预期错误"):
        workflow.run_build(candidate.candidate_id)
    with session_factory() as fresh:
        from app.storage.evidence_locator_repositories import (
            EvidenceProcessingCandidateRepository,
        )

        got = EvidenceProcessingCandidateRepository(fresh).get(candidate.candidate_id)
        assert got.status == EvidenceProcessingCandidateStatus.RETRYABLE_FAILURE
        assert got.complete_revision_id is None


def test_workflow_retry_resumes_same_candidate(stack, session_factory, monkeypatch):
    _session, _fixture, keys = stack
    _prepare_reviewed_closure(session_factory, keys)
    workflow = EvidenceRevisionWorkflow(session_factory)
    candidate = workflow.start(_request(keys))

    original = workflow._scan_and_build

    def _boom(*_args, **_kwargs):
        raise RuntimeError("暂时故障")

    monkeypatch.setattr(workflow, "_scan_and_build", _boom)
    with pytest.raises(BuildRetryableFailureError):
        workflow.run_build(candidate.candidate_id)
    monkeypatch.setattr(workflow, "_scan_and_build", original)

    retried = workflow.retry(candidate.candidate_id, actor="tester", reason="重试")
    assert retried.candidate_id == candidate.candidate_id
    assert retried.status == EvidenceProcessingCandidateStatus.READY
    assert retried.complete_revision_id is not None


def test_workflow_cancel_processing_at_safe_boundary(stack, session_factory):
    _session, _fixture, keys = stack
    workflow = EvidenceRevisionWorkflow(session_factory)
    candidate = workflow.start(_request(keys))
    cancelled = workflow.cancel(candidate.candidate_id, actor="tester", reason="用户取消")
    assert cancelled.status == EvidenceProcessingCandidateStatus.CANCELLED
    assert cancelled.complete_revision_id is None


def test_workflow_recovers_stale_processing_candidate(stack, session_factory):
    _session, _fixture, keys = stack
    workflow = EvidenceRevisionWorkflow(session_factory)
    candidate = workflow.start(_request(keys))

    recovered = workflow.recover_stale_processing(
        stale_before=datetime.now(UTC) + timedelta(seconds=1),
        actor="system",
        reason="服务中断后恢复",
    )
    assert [item.candidate_id for item in recovered] == [candidate.candidate_id]
    assert recovered[0].status == EvidenceProcessingCandidateStatus.RETRYABLE_FAILURE


def test_workflow_stale_recovery_keeps_recent_candidate(stack, session_factory):
    _session, _fixture, keys = stack
    workflow = EvidenceRevisionWorkflow(session_factory)
    candidate = workflow.start(_request(keys))

    recovered = workflow.recover_stale_processing(
        stale_before=datetime.now(UTC) - timedelta(hours=1),
        actor="system",
        reason="服务中断后恢复",
    )
    assert recovered == []
    with session_factory() as fresh:
        from app.storage.evidence_locator_repositories import (
            EvidenceProcessingCandidateRepository,
        )

        got = EvidenceProcessingCandidateRepository(fresh).get(candidate.candidate_id)
        assert got.status == EvidenceProcessingCandidateStatus.PROCESSING


def test_workflow_concurrent_start_reuses_one_candidate(stack, session_factory):
    _session, _fixture, keys = stack
    request = _request(keys, idempotency_key="concurrent-start")
    barrier = Barrier(2)

    def _start(candidate_id):
        barrier.wait()
        return EvidenceRevisionWorkflow(session_factory).start(
            request,
            candidate_id=candidate_id,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(_start, ["candidate-a", "candidate-b"]))
    assert results[0].candidate_id == results[1].candidate_id
    with session_factory() as fresh:
        from sqlalchemy import func, select

        from app.storage.evidence_locator_models import (
            EvidenceProcessingCandidateRecord,
        )

        count = fresh.execute(
            select(func.count()).select_from(EvidenceProcessingCandidateRecord)
        ).scalar_one()
        assert count == 1


def test_workflow_concurrent_build_freezes_one_complete_revision(
    stack, session_factory
):
    _session, _fixture, keys = stack
    _prepare_reviewed_closure(session_factory, keys)
    workflow = EvidenceRevisionWorkflow(session_factory)
    candidate = workflow.start(_request(keys, idempotency_key="concurrent-build"))
    barrier = Barrier(2)

    def _build(_index):
        barrier.wait()
        return EvidenceRevisionWorkflow(session_factory).run_build(
            candidate.candidate_id
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(_build, range(2)))
    assert results[0].complete_revision_id == results[1].complete_revision_id
    assert all(
        item.status == EvidenceProcessingCandidateStatus.READY for item in results
    )
    with session_factory() as fresh:
        revisions = CompleteEvidenceProcessingRevisionRepository(
            fresh
        ).list_by_snapshot("snap-1")
        assert len(revisions) == 1
