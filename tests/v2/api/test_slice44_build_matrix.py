"""Slice 4.4 构建命令身份 + 原子幂等矩阵（WP-44C 复查 #1）。

构建幂等主张按**完整命令身份**比较（scope/快照/base/扫描版本/定位/actor/预期
修订号），不再仅凭全局幂等键回放：

- 同键同命令 -> 回放原候选（即使审核节点修订号已前进）；
- 同键异命令 -> 409 IDEMPOTENCY_CONFLICT 且不产生新候选/事件/历史；
- 新键 + 过期预期修订号 -> 409 STALE_REVISION 且不产生候选；
- 候选创建 + 首事件 + 幂等主张同一事务提交（故障注入后无半提交）。
"""

from __future__ import annotations

import pytest

from app.services.evidence_revision_build_executor import (
    EVIDENCE_REVISION_BUILD_JOB_TYPE,
)
from app.services.evidence_risk_service import EvidenceRiskScanService
from app.storage.codecs import utc_now
from app.workflow.errors import ProcessDeath
from app.workflow.recovery import recover_expired_jobs
from app.workflow.runner import JobRunner
from tests.v2.api.test_slice44_api import (
    COMPLETE1,
    OCR_PAGE_ID,
    REV1,
    SNAP1,
    _assert_envelope,
    _episode_revision,
    _run_revision_job,
    _seed_api_stack,
    _seed_metadata_helper,
    _seed_ready_complete,
    _seed_reviews_for_blocking,
    _make_candidate_ready,
    _ready_snapshot,
    activate,
)
from tests.v2.workflow.conftest import expire_lease


def _build_body(
    client,
    keys,
    *,
    key="key-build-m1",
    expected_revision=None,
    actor="测试用户",
    **overrides,
):
    if expected_revision is None:
        expected_revision = _episode_revision(client, keys["episode_id"])
    body = {
        "evidence_snapshot_id": SNAP1,
        "base_processing_revision_id": REV1,
        "expected_revision": expected_revision,
        "idempotency_key": key,
        "actor": actor,
    }
    body.update(overrides)
    return body


def _seed_ready_build_inputs(client, keys) -> None:
    """播种元数据 + 全部 blocking 核对，使构建可成功冻结。"""
    _seed_metadata_helper(client, keys)
    scan = EvidenceRiskScanService(client.app.state.session_factory).scan_page(
        OCR_PAGE_ID
    )
    _seed_reviews_for_blocking(client, scan.scan_id)


def _candidate_count(client) -> int:
    from sqlalchemy import func, select, text

    with client.app.state.session_factory() as session:
        return int(
            session.execute(
                select(func.count()).select_from(text("evidence_processing_candidates"))
            ).scalar_one()
        )


def test_build_same_key_same_command_replays_after_advance(client) -> None:
    """同键同命令：即使审核节点修订号已前进也回放原候选（READY）。"""
    keys = _seed_api_stack(client)
    _seed_ready_build_inputs(client, keys)
    body = _build_body(client, keys)
    first = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert first.status_code == 201, first.text
    first_id = first.json()["candidate_id"]
    # 推进审核节点修订号（模拟另一动作）。
    with client.app.state.session_factory() as session, session.begin():
        from app.storage.codecs import encode_contract
        from app.storage.models import ReviewEpisodeRecord
        from app.storage.repositories import EpisodeRepository

        episode = EpisodeRepository(session).get(keys["episode_id"])
        changed = episode.model_copy(update={"revision": episode.revision + 5})
        row = session.get(ReviewEpisodeRecord, keys["episode_id"])
        payload, phash = encode_contract(changed)
        row.payload_json = payload
        row.payload_sha256 = phash
    replay = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert replay.status_code == 200, replay.text
    assert replay.json()["candidate_id"] == first_id
    assert replay.json()["created"] is False
    # 历史不变：仍只有一个候选。
    assert _candidate_count(client) == 1


def test_build_same_key_different_command_409_no_history(client) -> None:
    """同幂等键异命令（改 actor/定位/预期修订号）-> 409，不产生新历史。"""
    keys = _seed_api_stack(client)
    _seed_ready_build_inputs(client, keys)
    body = _build_body(client, keys, key="key-build-conflict")
    assert (
        client.post(
            "/api/v2/evidence-processing-revisions/build", json=body
        ).status_code
        == 201
    )
    # 改 actor：命令身份不同。
    body2 = _build_body(client, keys, key="key-build-conflict", actor="另一用户")
    resp = client.post("/api/v2/evidence-processing-revisions/build", json=body2)
    assert resp.status_code == 409
    error = _assert_envelope(resp.json(), code="IDEMPOTENCY_CONFLICT", status=409)
    assert error["context"]["submitted"]["actor"] == "另一用户"
    assert "existing_result" in error["context"]
    # 不产生新候选。
    assert _candidate_count(client) == 1


def test_build_rejects_unsupported_processing_configuration_without_history(client) -> None:
    """过期页面提交的处理配置在建立幂等主张和候选历史前被拒绝。"""
    keys = _seed_api_stack(client)
    _seed_ready_build_inputs(client, keys)
    body = _build_body(
        client,
        keys,
        key="key-build-unsupported-configuration",
        scanner_rule_version="rules/v9",
    )
    response = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert response.status_code == 422
    error = _assert_envelope(
        response.json(), code="BUILD_CONFIGURATION_UNAVAILABLE", status=422
    )
    assert error["title"] == "当前资料处理方式已更新"
    assert _candidate_count(client) == 0


def test_metadata_only_build_keeps_reviewed_scanner_version(client) -> None:
    """修改资料类型不应把已核对原件改用新扫描规则重审。"""
    from app.evidence.risk import _PREVIOUS_RISK_RULE_VERSION
    from app.services.evidence_revision_builder import EvidenceRevisionBuilder
    from app.storage.evidence_locator_repositories import (
        CompleteEvidenceProcessingRevisionRepository,
    )
    from tests.v2.storage.test_slice44_repositories import _complete_revision

    keys = _seed_api_stack(client)
    _seed_metadata_helper(client, keys)
    scan = EvidenceRiskScanService(client.app.state.session_factory).scan_page(
        OCR_PAGE_ID, rule_version=_PREVIOUS_RISK_RULE_VERSION
    )
    _seed_reviews_for_blocking(client, scan.scan_id)
    with client.app.state.session_factory() as session, session.begin():
        _ready_snapshot(session, keys)
        closure = EvidenceRevisionBuilder(
            artifact_store=client.app.state.artifact_store
        ).gather_closure(
            session,
            evidence_snapshot_id=SNAP1,
            base_processing_revision_id=REV1,
            scanner_rule_version=_PREVIOUS_RISK_RULE_VERSION,
        )
        revision = _complete_revision(
            keys, session,
            metadata_revision_ids=closure.metadata_revision_ids,
            risk_scan_ids=closure.risk_scan_ids,
            risk_review_ids=closure.risk_review_ids,
            locator_ids=closure.locator_ids,
        )
        created_revision = CompleteEvidenceProcessingRevisionRepository(
            session, client.app.state.artifact_store
        ).create(revision)
        _make_candidate_ready(
            session, created_revision.producer_candidate_id,
            created_revision.evidence_processing_revision_id,
        )
    activate(client, keys, COMPLETE1, "activate-before-metadata-update")
    metadata = client.patch(
        "/api/v2/source-document-versions/doc-1/metadata",
        json={
            "document_type": "检验报告",
            "source_party": "研究中心检验科",
            "reason": "核对资料类型",
            "expected_metadata_revision": 1,
            "idempotency_key": "metadata-only-update",
            "actor": "测试用户",
        },
    )
    assert metadata.status_code == 201, metadata.text
    new_metadata_id = metadata.json()["metadata"]["metadata_revision_id"]
    body = _build_body(client, keys, key="build-after-metadata-update")
    created = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert created.status_code == 201, created.text
    _run_revision_job(client, created.json()["job_id"])
    from app.storage.evidence_locator_repositories import EvidenceProcessingCandidateRepository
    with client.app.state.session_factory() as session:
        events = EvidenceProcessingCandidateRepository(
            session, client.app.state.artifact_store
        ).get_events(created.json()["candidate_id"])
    assert events[-1].to_status.value == "ready", [event.reason for event in events]
    with client.app.state.session_factory() as session:
        new_candidate = EvidenceProcessingCandidateRepository(
            session, client.app.state.artifact_store
        ).get(created.json()["candidate_id"])
        frozen = CompleteEvidenceProcessingRevisionRepository(
            session, client.app.state.artifact_store
        ).get(new_candidate.complete_revision_id)
    assert frozen.metadata_revision_ids == [new_metadata_id]
    client.app.state.evidence_api_command_service.build_revision(
        evidence_snapshot_id=SNAP1,
        base_processing_revision_id=REV1,
        expected_revision=body["expected_revision"],
        idempotency_key=body["idempotency_key"],
        actor=body["actor"],
    )
    completed = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert completed.status_code == 200, completed.text
    assert completed.json()["candidate_status"] == "ready"
    with client.app.state.session_factory() as session:
        revision = CompleteEvidenceProcessingRevisionRepository(
            session, client.app.state.artifact_store
        ).get(completed.json()["revision"]["evidence_processing_revision_id"])
    assert revision.metadata_revision_ids == [new_metadata_id]
    assert revision.risk_scan_ids == [scan.scan_id]
    assert revision.risk_review_ids == closure.risk_review_ids


def test_metadata_only_reuse_rejected_after_page_correction(client) -> None:
    """页校对变化时不能误用仅更新资料信息的快速路径。"""
    from app.storage.evidence_locator_repositories import CorrectionRepository
    from tests.v2.storage.test_slice44_repositories import _correction

    keys = _seed_ready_complete(client)
    activate(client, keys, COMPLETE1, "activate-before-correction")
    metadata = client.patch(
        "/api/v2/source-document-versions/doc-1/metadata",
        json={
            "document_type": "检验报告",
            "source_party": "研究中心检验科",
            "reason": "核对资料类型",
            "expected_metadata_revision": 1,
            "idempotency_key": "metadata-before-correction",
            "actor": "测试用户",
        },
    )
    assert metadata.status_code == 201, metadata.text
    with client.app.state.session_factory() as session, session.begin():
        CorrectionRepository(session).create(
            _correction(keys, correction_id="later-correction")
        )
    service = client.app.state.evidence_api_command_service
    with client.app.state.session_factory() as session:
        assert service._metadata_only_scanner_version(
            session,
            snapshot_id=SNAP1,
            base_processing_revision_id=REV1,
            selected_locator_ids=[],
            default_version="new-scanner-version",
        ) == "new-scanner-version"


def test_build_new_key_stale_revision_409_no_history(client) -> None:
    """新键 + 过期预期修订号 -> 409 STALE_REVISION，不产生候选/幂等记录。"""
    keys = _seed_api_stack(client)
    _seed_ready_build_inputs(client, keys)
    current = _episode_revision(client, keys["episode_id"])
    body = _build_body(
        client, keys, key="key-build-stale", expected_revision=current + 7
    )
    resp = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert resp.status_code == 409
    error = _assert_envelope(resp.json(), code="STALE_REVISION", status=409)
    ctx = error["context"]
    assert ctx["submitted"]["expected_revision"] == current + 7
    assert ctx["current_revision"] == current
    assert ctx["field_diff"]["revision"]["submitted"] == current + 7
    assert _candidate_count(client) == 0


def test_build_rejects_unfinished_referenced_document_before_job_creation(client) -> None:
    """被提及资料未确认/解除时直接列出待办，不创建必然失败的后台任务。"""
    keys = _seed_api_stack(client)
    _seed_ready_build_inputs(client, keys)
    created = client.post(
        f"/api/v2/subjects/{keys['subject_id']}/referenced-documents",
        json={
            "review_episode_id": keys["episode_id"],
            "expected_revision": _episode_revision(client, keys["episode_id"]),
            "idempotency_key": "key-refdoc-preflight",
            "description": "既往影像报告",
            "actor": "测试用户",
        },
    )
    assert created.status_code == 201, created.text

    response = client.post(
        "/api/v2/evidence-processing-revisions/build",
        json=_build_body(client, keys, key="key-build-refdoc-preflight"),
    )
    assert response.status_code == 409
    error = _assert_envelope(
        response.json(), code="EVIDENCE_REVIEW_INCOMPLETE", status=409
    )
    assert error["title"] == "资料核对尚未完成"
    assert "既往影像报告：请确认原文确有提及，或解除这项候选。" in error[
        "detail"
    ]
    assert error["context"]["pending_items"] == [
        {
            "referenced_document_id": created.json()["referenced_document_id"],
            "description": "既往影像报告",
            "action": "请确认原文确有提及，或解除这项候选。",
        }
    ]
    assert _candidate_count(client) == 0


def test_build_candidate_event_idempotency_claim_one_transaction(client) -> None:
    """候选创建 + 首事件 + 幂等主张原子：注入幂等主张失败无半提交，重试执行一次。"""
    from unittest import mock

    from app.storage.idempotency import IdempotencyRepository

    keys = _seed_api_stack(client)
    _seed_ready_build_inputs(client, keys)
    body = _build_body(client, keys, key="key-build-atomic")

    def _boom_resolve(
        self, *, scope, idempotency_key, submitted_hash, result_type, result_id
    ):
        raise RuntimeError("注入失败：幂等主张写入失败")

    with mock.patch.object(IdempotencyRepository, "resolve", _boom_resolve):
        try:
            client.app.state.evidence_api_command_service.build_revision(
                evidence_snapshot_id=SNAP1,
                base_processing_revision_id=REV1,
                expected_revision=body["expected_revision"],
                idempotency_key=body["idempotency_key"],
                actor=body["actor"],
            )
            raised = False
        except RuntimeError:
            raised = True
        assert raised
    # 幂等主张失败 -> 同一事务回滚，无候选残留。
    assert _candidate_count(client) == 0
    # 重试同命令可正常执行（无半提交、无陈旧冲突）。
    retry = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert retry.status_code == 201, retry.text
    assert retry.json()["created"] is True


def test_build_same_key_resumes_candidate_after_request_process_ends(client) -> None:
    """HTTP 返回后由新后台执行器接管；同键重试始终指向原候选。"""
    keys = _seed_api_stack(client)
    _seed_ready_build_inputs(client, keys)
    body = _build_body(client, keys, key="key-build-interrupted")
    first = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert first.status_code == 201, first.text
    candidate_id = first.json()["candidate_id"]
    job_id = first.json()["job_id"]
    assert first.json()["candidate_status"] == "staged"
    assert _candidate_count(client) == 1

    # 模拟请求进程已经结束但后台尚未取得租约：回放不能新建候选或同步执行构建。
    retry = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert retry.status_code == 200, retry.text
    assert retry.json()["created"] is False
    assert retry.json()["candidate_id"] == candidate_id
    assert retry.json()["candidate_status"] == "staged"
    assert retry.json()["revision"] is None

    # 新 runner 仅依赖持久任务接管，完成后同一命令仍回放同一候选。
    _run_revision_job(client, job_id)
    completed = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert completed.status_code == 200, completed.text
    assert completed.json()["candidate_id"] == candidate_id
    assert completed.json()["candidate_status"] == "ready"
    assert completed.json()["revision"]["evidence_processing_revision_id"]
    assert _candidate_count(client) == 1


def test_ready_candidate_recovers_same_job_after_checkpoint_process_death(client) -> None:
    """完整版本已落盘、任务检查点未提交时重启：同任务幂等收敛为完成。"""
    from datetime import timedelta

    from app.storage.evidence_locator_repositories import (
        CompleteEvidenceProcessingRevisionRepository,
        EvidenceProcessingCandidateRepository,
    )

    keys = _seed_api_stack(client)
    _seed_ready_build_inputs(client, keys)
    body = _build_body(client, keys, key="key-ready-before-checkpoint")
    created = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert created.status_code == 201, created.text
    candidate_id = created.json()["candidate_id"]
    job_id = created.json()["job_id"]
    normal_executor = client.app.state.job_executors[
        EVIDENCE_REVISION_BUILD_JOB_TYPE
    ]

    def die_after_build(context):
        normal_executor(context)
        raise ProcessDeath()

    dying_runner = JobRunner(
        client.app.state.session_factory,
        {
            **client.app.state.job_executors,
            EVIDENCE_REVISION_BUILD_JOB_TYPE: die_after_build,
        },
        worker_id="revision-worker-before-restart",
    )
    with pytest.raises(ProcessDeath):
        dying_runner.run_job(job_id)

    with client.app.state.session_factory() as session:
        candidate_repo = EvidenceProcessingCandidateRepository(session)
        ready = candidate_repo.get(candidate_id)
        event_count = len(candidate_repo.get_events(candidate_id))
        assert ready.status.value == "ready"
        assert len(
            CompleteEvidenceProcessingRevisionRepository(
                session, client.app.state.artifact_store
            ).list_by_snapshot(SNAP1)
        ) == 1
    assert client.app.state.job_service.get_job_state(job_id) == "running"

    expire_lease(
        client.app.state.session_factory,
        job_id,
        before=utc_now() - timedelta(seconds=1),
    )
    report = recover_expired_jobs(client.app.state.session_factory)
    assert report.recovered_jobs == [job_id]
    fresh_runner = JobRunner(
        client.app.state.session_factory,
        client.app.state.job_executors,
        worker_id="revision-worker-after-restart",
    )
    assert fresh_runner.run_job(job_id) is True
    assert client.app.state.job_service.get_job_state(job_id) == "completed"
    with client.app.state.session_factory() as session:
        candidate_repo = EvidenceProcessingCandidateRepository(session)
        recovered = candidate_repo.get(candidate_id)
        assert recovered.status.value == "ready"
        assert len(candidate_repo.get_events(candidate_id)) == event_count
        assert len(
            CompleteEvidenceProcessingRevisionRepository(
                session, client.app.state.artifact_store
            ).list_by_snapshot(SNAP1)
        ) == 1
