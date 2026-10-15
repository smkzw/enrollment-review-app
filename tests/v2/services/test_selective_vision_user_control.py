"""Phase 5 冻结修订选择性视觉：用户控制闭环验收（worker_03）。

Acceptance boundary (worker_03 / selective_vision_user_control):
  ACCEPT —
    1. 任务关联：冻结修订 -> 独立视觉核验任务的解析幂等且稳定，跨服务实例
       （页面刷新/进程重启）、跨任务状态（取消/失败/恢复）不变；未知修订
       失败关闭且不产生任务行；
    2. 错误类型：未知任务 NOT_FOUND、状态冲突 JOB_STATE_CONFLICT、空修订
       INVALID_JOB_DEFINITION 稳定可辨，中文文案不携带工程细节；
    3. 重试/取消：人工重试只重置失败范围并清空错误字段（任务可再次完成）；
       取消对无租约任务立即收束、对运行中任务先持久化请求再在安全边界收束，
       重复取消为无副作用 no-op，终态/占用/非失败状态拒绝重试；
    4. 刷新恢复：取消请求与失败状态在服务实例重建后仍持久可见；进程崩溃 +
       租约过期恢复后同一修订仍解析到同一任务且只产生一条成功观察；
    5. 中文文案：任务/步骤/事件词汇表与恢复动作全部为非空中文；视觉核验
       步骤名以中文持久化并在界面原样展示；
    6. 无内部字段泄露：用户动作结果与错误文案不携带模型名、提示词、token、
       哈希、载荷、幂等键、租约或日志文本。
  REJECT —
    修改生产文件或既有测试（本文件为新增切片专属测试）；重试扩散到未失败
    范围；取消静默改写已完成内容；向用户界面暴露内部分类或载荷。

Aligned to production surface (现有持久任务机制，本切片复用)：
  app.services.selective_vision_postprocess_job_service（关联 + cancel/retry）
  app.workflow.jobstore（request_cancel / retry_failed / 快照）
  app.workflow.recovery（租约过期恢复）
  app.api.v2.vocabulary（中文状态/恢复动作投影）
"""

from __future__ import annotations

import asyncio
import dataclasses
import re
from datetime import timedelta

import pytest
from sqlalchemy import update

from app.api.v2.vocabulary import (
    EVENT_TYPE_LABELS,
    JOB_STATE_LABELS,
    STEP_STATE_LABELS,
    job_recovery_action,
)
from app.domain.contracts.enums import PageArtifactStatus
from app.domain.contracts.evidence_processing import EvidenceProcessingRevisionPage
from app.domain.contracts.evidence_locator import CompleteEvidenceProcessingRevision
from app.domain.contracts.selective_vision_observation import (
    SelectiveVisionObservationStatus,
)
from app.domain.publication import evidence_processing_manifest_hash
from app.evidence.selective_vision_review import (
    SelectiveVisionObservation,
    SelectiveVisionReviewOutcome,
    VISION_REASON_SCAN_OR_IMAGE_ONLY,
)
from app.services.evidence_app_errors import EvidenceAppError
from app.services.job_service import JOB_IDEMPOTENCY_SCOPE, JobService, StepSpec
from app.services.selective_vision_postprocess_executor import (
    SelectiveVisionPostprocessExecutorConfig,
    create_selective_vision_postprocess_executor,
)
from app.services.selective_vision_postprocess_job_service import (
    SELECTIVE_VISION_POSTPROCESS_JOB_TYPE,
    SELECTIVE_VISION_POSTPROCESS_STEP_ID,
    SelectiveVisionPostprocessJobService,
    enqueue_selective_vision_postprocess_for_revision,
    selective_vision_postprocess_idempotency_key,
)
from app.storage.codecs import encode_contract, to_utc_naive, utc_now
from app.storage.idempotency import IdempotencyRepository, request_hash
from app.storage.models import JobRecord
from app.storage.ocr_models import EvidenceProcessingRevisionRecord
from app.storage.ocr_repositories import EvidenceProcessingRevisionRepository
from app.storage.repositories import persist_fixture
from app.storage.selective_vision_observation_repository import (
    SelectiveVisionObservationRepository,
)
from app.workflow.errors import (
    InvalidJobDefinitionError,
    JobNotFoundError,
    JobStateConflictError,
    ProcessDeath,
    StepFailure,
)
from app.workflow.jobstore import JobLease, JobStore
from app.workflow.recovery import recover_expired_jobs
from app.workflow.runner import JobRunner
from tests.v2.services.test_selective_vision_postfreeze_orchestration import (
    _build_runner,
    _seed_frozen_revision,
)
from tests.v2.storage.test_ocr_repositories import make_revision
from tests.v2.storage.test_repositories_roundtrip import FIXTURES

JOB_TYPE = SELECTIVE_VISION_POSTPROCESS_JOB_TYPE
STEP_ID = SELECTIVE_VISION_POSTPROCESS_STEP_ID

# 用户可见文案中绝不允许出现的工程标记（模型/提示词/token/哈希/载荷/日志）。
_INTERNAL_MARKERS = (
    "mock-vlm",
    "prompt",
    "token",
    "usage",
    "sha256",
    "payload",
    "idempotency",
    "lease",
    "run_selective_vision",
    "SELECTIVE_VISION_PLAN_VERSION",
    "selective-vision-plan/",
    "log:",
    "stack",
    "Traceback",
)

_CJK = re.compile(r"[\u4e00-\u9fff]")


def _assert_chinese(text: str) -> None:
    assert text.strip(), "用户可见文案不能为空"
    assert _CJK.search(text), f"用户可见文案必须包含中文：{text!r}"


def _assert_no_internal_markers(text: str) -> None:
    lowered = text.lower()
    for marker in _INTERNAL_MARKERS:
        assert marker.lower() not in lowered, (
            f"用户可见文案泄露工程标记 {marker!r}：{text!r}"
        )


def _success_runner():
    async def runner(plan, inputs):
        page = inputs[0]
        return SelectiveVisionReviewOutcome(
            plan=plan,
            observations=(
                SelectiveVisionObservation(
                    source_refs=(page.source_ref,),
                    page_ordinals=(page.page_ordinal,),
                    reasons=(VISION_REASON_SCAN_OR_IMAGE_ONLY,),
                    text=f"source_ref={page.source_ref}\nuser control closed loop",
                    model="mock-vlm",
                    finish_reason="stop",
                    usage={"prompt_tokens": 2},
                ),
            ),
        )

    return runner


def _seed_sibling_revision(session_factory, base: dict, revision_id: str) -> None:
    """在已播种 fixture 的同一快照/页产物上追加第二个冻结修订（避免重复建 fixture）。"""
    with session_factory() as session, session.begin():
        fixture = FIXTURES[0]
        entry = EvidenceProcessingRevisionPage(
            entry_id=f"e-{revision_id}",
            position=1,
            source_document_version_id="doc-svo-1",
            page_number=1,
            original_frame=None,
            page_artifact_id=base["page_artifact_id"],
            ocr_page_id=base["ocr_page_id"],
            status=PageArtifactStatus.SUCCEEDED,
        )
        manifest_hash = evidence_processing_manifest_hash(
            entries=[
                (
                    "doc-svo-1",
                    1,
                    None,
                    base["page_artifact_id"],
                    base["ocr_page_id"],
                    PageArtifactStatus.SUCCEEDED.value,
                )
            ]
        )
        EvidenceProcessingRevisionRepository(session).create(
            make_revision(
                {
                    "project_id": fixture.project.project_id,
                    "subject_id": fixture.subject.subject_id,
                    "episode_id": fixture.review_episode.review_episode_id,
                    "entry": entry,
                    "manifest_hash": manifest_hash,
                },
                evidence_processing_revision_id=revision_id,
                evidence_snapshot_id="snap-svo-1",
            )
        )


def _seed_complete_revision_alias(
    session_factory, base_revision_id: str, complete_revision_id: str
) -> None:
    """模拟已通过完整闭包门禁的活动修订根记录，指向既有 base 修订。"""
    with session_factory() as session, session.begin():
        base = EvidenceProcessingRevisionRepository(session).get(base_revision_id)
        complete = CompleteEvidenceProcessingRevision(
            evidence_processing_revision_id=complete_revision_id,
            evidence_snapshot_id=base.evidence_snapshot_id,
            project_id=base.project_id,
            subject_id=base.subject_id,
            review_episode_id=base.review_episode_id,
            base_processing_revision_id=base_revision_id,
            producer_candidate_id=f"producer-{complete_revision_id}",
            candidate_input_sha256="a" * 64,
            manifest=base.manifest,
            manifest_sha256=base.manifest_sha256,
            completion_manifest_sha256="b" * 64,
            created_at=base.created_at,
            created_by="tester",
        )
        payload_json, payload_sha256 = encode_contract(complete)
        session.add(
            EvidenceProcessingRevisionRecord(
                evidence_processing_revision_id=complete_revision_id,
                evidence_snapshot_id=base.evidence_snapshot_id,
                project_id=base.project_id,
                subject_id=base.subject_id,
                review_episode_id=base.review_episode_id,
                manifest_sha256=base.manifest_sha256,
                status=complete.status.value,
                is_activatable=True,
                revision_kind="complete",
                base_processing_revision_id=base_revision_id,
                producer_candidate_id=complete.producer_candidate_id,
                candidate_input_sha256=complete.candidate_input_sha256,
                completion_manifest_sha256=complete.completion_manifest_sha256,
                created_by=complete.created_by,
                created_at=to_utc_naive(complete.created_at),
                payload_json=payload_json,
                payload_sha256=payload_sha256,
            )
        )


def _snap(session_factory, job_id: str):
    with session_factory() as session:
        return JobStore(session, now=utc_now).snapshot(job_id)


def _set_lease(session_factory, job_id: str, *, owner: str, expired: bool) -> None:
    expires = utc_now() + (timedelta(seconds=-5) if expired else timedelta(seconds=60))
    with session_factory() as session, session.begin():
        session.execute(
            update(JobRecord)
            .where(JobRecord.job_id == job_id)
            .values(
                state="running",
                lease_owner=owner,
                lease_generation=1,
                lease_expires_at=expires,
            )
        )


def _succeeded_observations(session_factory, page_artifact_id: str):
    with session_factory() as session:
        listed = SelectiveVisionObservationRepository(session).list_by_page_artifact(
            page_artifact_id
        )
        return [
            row
            for row in listed
            if row.status == SelectiveVisionObservationStatus.SUCCEEDED
        ]


# ---------------------------------------------------------------------------
# 1) 任务关联：修订 -> 视觉核验任务稳定解析
# ---------------------------------------------------------------------------


def test_revision_to_job_association_is_stable_across_service_instances(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-assoc"
    )
    first = SelectiveVisionPostprocessJobService(session_factory).enqueue_for_revision(
        seeded["revision_id"]
    )
    assert first.created is True

    # 模拟页面刷新/进程重启：全新服务实例 + 全新会话仍解析到同一任务。
    restarted = SelectiveVisionPostprocessJobService(session_factory).enqueue_for_revision(
        seeded["revision_id"]
    )
    assert restarted.job_id == first.job_id
    assert restarted.created is False
    assert restarted.evidence_processing_revision_id == seeded["revision_id"]

    status = SelectiveVisionPostprocessJobService(session_factory).get_job(first.job_id)
    assert status["job_type"] == JOB_TYPE
    assert status["state"] == "queued"
    assert (
        status["payload"]["evidence_processing_revision_id"] == seeded["revision_id"]
    )


def test_association_is_scoped_per_revision_and_records_revision_id(
    session_factory, data_paths
):
    seeded_a = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-scope-a"
    )
    _seed_sibling_revision(
        session_factory, seeded_a, "rev-svo-uc-scope-b"
    )
    seeded_b = {"revision_id": "rev-svo-uc-scope-b"}
    service = SelectiveVisionPostprocessJobService(session_factory)
    job_a = service.enqueue_for_revision(seeded_a["revision_id"])
    job_b = service.enqueue_for_revision(seeded_b["revision_id"])

    assert job_a.job_id != job_b.job_id
    assert service.get_job(job_a.job_id)["payload"][
        "evidence_processing_revision_id"
    ] == seeded_a["revision_id"]
    assert service.get_job(job_b.job_id)["payload"][
        "evidence_processing_revision_id"
    ] == seeded_b["revision_id"]


def test_association_survives_terminal_states_without_recreating_jobs(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-terminal"
    )
    service = SelectiveVisionPostprocessJobService(session_factory)
    enq = service.enqueue_for_revision(seeded["revision_id"])

    cancelled = service.cancel(enq.job_id)
    assert cancelled.changed is True
    assert cancelled.state == "cancelled"

    # 取消后同一修订仍指向同一任务：关联是身份，不随状态漂移，也不新建任务。
    again = service.enqueue_for_revision(seeded["revision_id"])
    assert again.job_id == enq.job_id
    assert again.created is False
    assert _snap(session_factory, enq.job_id).state == "cancelled"


def test_idempotency_key_is_revision_and_plan_scoped_and_rejects_blank():
    key_a = selective_vision_postprocess_idempotency_key("rev-1")
    assert key_a == selective_vision_postprocess_idempotency_key("rev-1")
    assert key_a != selective_vision_postprocess_idempotency_key("rev-2")
    assert key_a.startswith("selective_vision_postprocess:rev-1:")
    assert (
        selective_vision_postprocess_idempotency_key("rev-1", plan_version="p/v2")
        != key_a
    )
    with pytest.raises(InvalidJobDefinitionError):
        selective_vision_postprocess_idempotency_key("   ")


def test_model_route_change_requires_new_task_identity(session_factory, data_paths, monkeypatch):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-route-change"
    )
    service = SelectiveVisionPostprocessJobService(session_factory)
    initial = service.enqueue_for_revision(seeded["revision_id"])
    initial_key = selective_vision_postprocess_idempotency_key(seeded["revision_id"])
    monkeypatch.setenv("INDEPENDENT_VLM_REASONING_EFFORT", "low")
    assert selective_vision_postprocess_idempotency_key(seeded["revision_id"]) != initial_key
    assert service.get_revision_task(seeded["revision_id"]).plan_supported is False
    service.cancel(initial.job_id)
    next_task = service.retry_revision_task(seeded["revision_id"])
    assert next_task.job_id != initial.job_id
    assert service.get_revision_task(seeded["revision_id"]).plan_supported is True
    assert _snap(session_factory, initial.job_id).state == "cancelled"


def test_queued_task_rejects_changed_route_before_reading_pages(session_factory, data_paths, monkeypatch):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-route-drift"
    )
    service = SelectiveVisionPostprocessJobService(session_factory)
    queued = service.enqueue_for_revision(seeded["revision_id"])
    monkeypatch.setenv("INDEPENDENT_VLM_REASONING_EFFORT", "low")
    assert _build_runner(session_factory, data_paths, review_runner=_success_runner()).run_once()
    step = _snap(session_factory, queued.job_id).steps[0]
    assert step.state == "failed_final"
    assert step.error_code == "SELECTIVE_VISION_ROUTE_CHANGED"


def test_invalid_vision_provider_still_allows_freeze_task_record(session_factory, data_paths, monkeypatch):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-invalid-route"
    )
    monkeypatch.setenv("INDEPENDENT_VLM_PROVIDER", "unconfigured-provider")
    service = SelectiveVisionPostprocessJobService(session_factory)
    created = service.enqueue_for_revision(seeded["revision_id"])
    assert created.created is True
    assert service.get_revision_task(seeded["revision_id"]).plan_supported is True


def test_enqueue_unknown_revision_fails_closed_without_job_row(
    session_factory, data_paths
):
    service = SelectiveVisionPostprocessJobService(session_factory)
    with pytest.raises(EvidenceAppError) as error:
        service.enqueue_for_revision("revision-does-not-exist")
    assert error.value.status_code == 404
    assert error.value.code == "NOT_FOUND"
    _assert_chinese(error.value.title)
    _assert_chinese(error.value.recovery)

    with session_factory() as session:
        assert session.query(JobRecord).count() == 0


# ---------------------------------------------------------------------------
# 2) 错误类型：用户动作的稳定错误分类
# ---------------------------------------------------------------------------


def test_user_actions_on_unknown_job_raise_not_found(session_factory, data_paths):
    service = SelectiveVisionPostprocessJobService(session_factory)
    with pytest.raises(JobNotFoundError) as cancel_error:
        service.cancel("job-does-not-exist")
    assert cancel_error.value.code == "NOT_FOUND"

    with pytest.raises(JobNotFoundError) as retry_error:
        service.retry("job-does-not-exist")
    assert retry_error.value.code == "NOT_FOUND"


def test_retry_rejects_non_failed_states_with_state_conflict(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-conflict"
    )
    runner = _success_runner()
    service = SelectiveVisionPostprocessJobService(session_factory)
    enq = service.enqueue_for_revision(seeded["revision_id"])

    # queued：未失败不可重试。
    with pytest.raises(JobStateConflictError) as queued_error:
        service.retry(enq.job_id)
    assert queued_error.value.current_state == "queued"
    _assert_chinese(str(queued_error.value))

    # completed：完成后不可重试，已完成内容不得重跑。
    assert _build_runner(
        session_factory, data_paths, review_runner=runner
    ).run_once()
    assert _snap(session_factory, enq.job_id).state == "completed"
    verified_scope = service.verified_observation_scope(seeded["revision_id"])
    assert verified_scope is not None
    assert len(verified_scope[0]) == len(verified_scope[1]) == 1
    with pytest.raises(JobStateConflictError) as completed_error:
        service.retry(enq.job_id)
    assert completed_error.value.current_state == "completed"

    # cancelled：取消后不可重试；重新入队复用同一任务（不产生第二条任务）。
    # 注意：取消已完成任务是无副作用 no-op，任务保持 completed，内容不得被改写。
    cancelled = service.cancel(enq.job_id)
    assert cancelled.changed is False, "已完成任务取消应为无副作用 no-op"
    assert _snap(session_factory, enq.job_id).state == "completed"
    with pytest.raises(JobStateConflictError) as cancelled_error:
        service.retry(enq.job_id)
    assert cancelled_error.value.current_state == "completed"

    again = service.enqueue_for_revision(seeded["revision_id"])
    assert again.job_id == enq.job_id
    assert again.created is False


def test_retry_rejects_failed_job_held_by_active_lease(session_factory, data_paths):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-lease"
    )
    state = {"armed": True}

    def flaky(context):
        if state["armed"]:
            state["armed"] = False
            raise StepFailure(
                retryable=True,
                error_code="VISION_PROVIDER_RETRYABLE",
                detail="视觉提供方暂时不可用",
            )
        return create_selective_vision_postprocess_executor(
            SelectiveVisionPostprocessExecutorConfig(
                session_factory=session_factory,
                data_paths=data_paths,
                review_runner=_success_runner(),
            )
        )(context)

    enq = enqueue_selective_vision_postprocess_for_revision(
        session_factory, seeded["revision_id"]
    )
    runner = JobRunner(
        session_factory,
        {JOB_TYPE: flaky},
        worker_id="uc-lease-worker",
        now=utc_now,
        poll_interval=0.01,
    )
    runner.run_once()
    assert _snap(session_factory, enq.job_id).state == "failed_retryable"

    # 模拟仍有 worker 持有租约：人工重试必须拒绝，避免双写。
    with session_factory() as session, session.begin():
        session.execute(
            update(JobRecord)
            .where(JobRecord.job_id == enq.job_id)
            .values(
                lease_owner="still-working",
                lease_expires_at=utc_now() + timedelta(seconds=60),
            )
        )
    with pytest.raises(JobStateConflictError) as error:
        SelectiveVisionPostprocessJobService(session_factory).retry(enq.job_id)
    assert error.value.current_state == "failed_retryable"
    _assert_chinese(str(error.value))
    _assert_no_internal_markers(str(error.value))


# ---------------------------------------------------------------------------
# 3) 重试/取消：人工控制闭环
# ---------------------------------------------------------------------------


def test_cancel_queued_job_is_immediate_idempotent_and_blocks_retry(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-cancel"
    )
    service = SelectiveVisionPostprocessJobService(session_factory)
    enq = service.enqueue_for_revision(seeded["revision_id"])

    outcome = service.cancel(enq.job_id)
    assert outcome.state == "cancelled"
    assert outcome.changed is True

    snapshot = _snap(session_factory, enq.job_id)
    assert snapshot.state == "cancelled"
    assert snapshot.cancel_requested is True
    assert all(step.state == "cancelled" for step in snapshot.steps)

    # 重复取消：无副作用 no-op，不追加新的状态漂移。
    repeat = service.cancel(enq.job_id)
    assert repeat.changed is False
    assert repeat.state == "cancelled"

    # 取消后的任务不允许人工重试。
    with pytest.raises(JobStateConflictError) as error:
        service.retry(enq.job_id)
    assert error.value.current_state == "cancelled"


def test_cancel_running_job_persists_request_then_stops_at_boundary(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-cancel-running"
    )
    service = SelectiveVisionPostprocessJobService(session_factory)
    enq = service.enqueue_for_revision(seeded["revision_id"])
    _set_lease(session_factory, enq.job_id, owner="uc-running-worker", expired=False)

    # 运行中：取消请求持久化，不立即抢占租约。
    outcome = service.cancel(enq.job_id)
    assert outcome.state == "cancel_requested"
    assert outcome.changed is True
    requested = _snap(session_factory, enq.job_id)
    assert requested.state == "cancel_requested"
    assert requested.cancel_requested is True

    # worker 安全边界执行取消：租约持有者收束为 cancelled，历史保留。
    with session_factory() as session, session.begin():
        store = JobStore(session, now=utc_now)
        store.cancel_at_boundary(
            JobLease(
                job_id=enq.job_id,
                owner="uc-running-worker",
                generation=1,
                expires_at=utc_now() + timedelta(seconds=60),
            )
        )

    final = _snap(session_factory, enq.job_id)
    assert final.state == "cancelled"
    assert final.cancel_requested is True
    assert all(step.state == "cancelled" for step in final.steps)


def test_manual_retry_resets_only_failed_scope_then_job_completes_again(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-retry-loop"
    )
    state = {"armed": True}
    real_executor = create_selective_vision_postprocess_executor(
        SelectiveVisionPostprocessExecutorConfig(
            session_factory=session_factory,
            data_paths=data_paths,
            review_runner=_success_runner(),
        )
    )

    def flaky(context):
        if state["armed"]:
            state["armed"] = False
            raise StepFailure(
                retryable=True,
                error_code="VISION_PROVIDER_RETRYABLE",
                detail="视觉提供方暂时不可用",
            )
        return real_executor(context)

    service = SelectiveVisionPostprocessJobService(session_factory)
    enq = service.enqueue_for_revision(seeded["revision_id"])

    runner = JobRunner(
        session_factory,
        {JOB_TYPE: flaky},
        worker_id="uc-retry-worker",
        now=utc_now,
        poll_interval=0.01,
    )
    runner.run_once()

    failed = _snap(session_factory, enq.job_id)
    assert failed.state == "failed_retryable"
    assert failed.error_code == "VISION_PROVIDER_RETRYABLE"
    assert failed.steps[0].state == "failed_retryable"
    assert failed.steps[0].retry_not_before is not None

    # 自动退避本身也会追加一条 retry_scheduled：人工重试应使其数量 +1。
    with session_factory() as session:
        rows = JobStore(session, now=utc_now).list_event_rows(enq.job_id)
        auto_retry_count = sum(
            1
            for row in rows
            if row.event.event_type.value == "retry_scheduled"
        )
        assert auto_retry_count >= 1, "首次可重试失败应先安排自动退避"

    # 人工重试：失败范围重置回 queued，错误字段清空，不新建任务。
    outcome = service.retry(enq.job_id)
    assert outcome.state == "queued"
    assert outcome.changed is True

    retried = _snap(session_factory, enq.job_id)
    assert retried.state == "queued"
    assert retried.error_code is None
    assert retried.job_id == enq.job_id
    assert retried.steps[0].state == "queued"
    assert retried.steps[0].error_code is None
    assert retried.steps[0].retry_not_before is None

    with session_factory() as session:
        rows = JobStore(session, now=utc_now).list_event_rows(enq.job_id)
        retry_events = [
            row
            for row in rows
            if row.event.event_type.value == "retry_scheduled"
        ]
        assert len(retry_events) == auto_retry_count + 1
        assert retry_events[-1].event.payload == {"retry_scope": [STEP_ID]}

    # 重试后闭环可完成：同一步骤完成，只产生一条成功观察。
    finisher = JobRunner(
        session_factory,
        {JOB_TYPE: real_executor},
        worker_id="uc-finish-worker",
        now=utc_now,
        poll_interval=0.01,
    )
    assert finisher.run_once()

    completed = _snap(session_factory, enq.job_id)
    assert completed.state == "completed"
    succeeded = _succeeded_observations(session_factory, seeded["page_artifact_id"])
    assert len(succeeded) == 1


def test_retry_after_final_failure_requeues_same_scope_without_new_job(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-final"
    )
    # 规划版本漂移 -> 确定性 failed_final（非重试类失败）。
    enq = SelectiveVisionPostprocessJobService(session_factory).enqueue_for_revision(
        seeded["revision_id"],
        plan_version="selective-vision-plan/obsolete",
    )
    runner = JobRunner(
        session_factory,
        {
            JOB_TYPE: create_selective_vision_postprocess_executor(
                SelectiveVisionPostprocessExecutorConfig(
                    session_factory=session_factory,
                    data_paths=data_paths,
                    review_runner=_success_runner(),
                )
            )
        },
        worker_id="uc-final-worker",
        now=utc_now,
        poll_interval=0.01,
    )
    runner.run_once()

    failed = _snap(session_factory, enq.job_id)
    assert failed.state == "failed_final"
    assert failed.error_code == "SELECTIVE_VISION_PLAN_VERSION_UNSUPPORTED"

    service = SelectiveVisionPostprocessJobService(session_factory)
    outcome = service.retry(enq.job_id)
    assert outcome.state == "queued"
    assert outcome.changed is True

    # 重跑同一失败范围：失败复现且错误类型稳定，不新建任务、不产生成功观察。
    runner.run_once()
    refailed = _snap(session_factory, enq.job_id)
    assert refailed.state == "failed_final"
    assert refailed.error_code == "SELECTIVE_VISION_PLAN_VERSION_UNSUPPORTED"
    assert refailed.job_id == enq.job_id
    assert _succeeded_observations(session_factory, seeded["page_artifact_id"]) == []

    again = service.enqueue_for_revision(
        seeded["revision_id"],
        plan_version="selective-vision-plan/obsolete",
    )
    assert again.job_id == enq.job_id
    assert again.created is False


# ---------------------------------------------------------------------------
# 4) 刷新恢复：重启/崩溃后用户仍能解析同一任务并收束
# ---------------------------------------------------------------------------


def test_cancel_request_survives_restart_and_still_stops_at_boundary(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-restart"
    )
    service = SelectiveVisionPostprocessJobService(session_factory)
    enq = service.enqueue_for_revision(seeded["revision_id"])
    _set_lease(session_factory, enq.job_id, owner="uc-restart-worker", expired=False)
    service.cancel(enq.job_id)

    # 进程重启 + 页面刷新：全新服务实例仍读到持久化的取消请求。
    restarted = SelectiveVisionPostprocessJobService(session_factory)
    snapshot = _snap(session_factory, enq.job_id)
    assert snapshot.state == "cancel_requested"
    assert snapshot.cancel_requested is True
    assert restarted.get_job(enq.job_id)["state"] == "cancel_requested"

    # 重启后的 worker 在安全边界收束取消。
    with session_factory() as session, session.begin():
        JobStore(session, now=utc_now).cancel_at_boundary(
            JobLease(
                job_id=enq.job_id,
                owner="uc-restart-worker",
                generation=1,
                expires_at=utc_now() + timedelta(seconds=60),
            )
        )
    assert _snap(session_factory, enq.job_id).state == "cancelled"

    # 刷新后重新入队：仍指向同一任务，不产生第二条视觉核验任务。
    again = restarted.enqueue_for_revision(seeded["revision_id"])
    assert again.job_id == enq.job_id
    assert again.created is False


def test_after_crash_and_lease_expiry_revision_resolves_same_job(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-crash"
    )
    real_executor = create_selective_vision_postprocess_executor(
        SelectiveVisionPostprocessExecutorConfig(
            session_factory=session_factory,
            data_paths=data_paths,
            review_runner=_success_runner(),
        )
    )
    state = {"armed": True}

    def crash_once(context):
        if state["armed"]:
            state["armed"] = False
            raise ProcessDeath("simulated crash during user control recovery probe")
        return real_executor(context)

    service = SelectiveVisionPostprocessJobService(session_factory)
    enq = service.enqueue_for_revision(seeded["revision_id"])

    with pytest.raises(ProcessDeath):
        JobRunner(
            session_factory,
            {JOB_TYPE: crash_once},
            worker_id="uc-doomed",
            now=utc_now,
            poll_interval=0.01,
        ).run_once()

    with session_factory() as session, session.begin():
        session.execute(
            update(JobRecord)
            .where(JobRecord.job_id == enq.job_id)
            .values(
                state="running",
                lease_owner="uc-doomed",
                lease_generation=1,
                lease_expires_at=utc_now() - timedelta(seconds=5),
            )
        )
    recover_expired_jobs(session_factory, now=utc_now)

    # 崩溃恢复后用户刷新：同一修订仍解析到同一任务。
    resumed = service.enqueue_for_revision(seeded["revision_id"])
    assert resumed.job_id == enq.job_id
    assert resumed.created is False

    assert JobRunner(
        session_factory,
        {JOB_TYPE: real_executor},
        worker_id="uc-reviver",
        now=utc_now,
        poll_interval=0.01,
    ).run_once()

    final = service.get_job(enq.job_id)
    assert final["state"] == "completed"
    assert len(_succeeded_observations(session_factory, seeded["page_artifact_id"])) == 1


# ---------------------------------------------------------------------------
# 5) 中文文案：状态/步骤/事件/恢复动作
# ---------------------------------------------------------------------------


def test_job_vocabulary_covers_lifecycle_with_non_empty_chinese():
    job_states = {
        "queued",
        "running",
        "completed",
        "failed_retryable",
        "failed_final",
        "cancel_requested",
        "cancelled",
        "recovering",
    }
    step_states = job_states - {"recovering", "cancel_requested"}
    event_types = {
        "created",
        "step_started",
        "step_completed",
        "step_failed",
        "retry_scheduled",
        "cancel_requested",
        "cancelled",
        "completed",
        "failed",
    }

    assert job_states <= set(JOB_STATE_LABELS), "视觉核验任务会经过的状态必须有中文标签"
    assert step_states <= set(STEP_STATE_LABELS)
    assert event_types <= set(EVENT_TYPE_LABELS)

    for state in job_states:
        _assert_chinese(JOB_STATE_LABELS[state])
        _assert_no_internal_markers(JOB_STATE_LABELS[state])
        recovery = job_recovery_action(state)
        _assert_chinese(recovery)
        _assert_no_internal_markers(recovery)
    for state in step_states:
        _assert_chinese(STEP_STATE_LABELS[state])
    for event in event_types:
        _assert_chinese(EVENT_TYPE_LABELS[event])

    # 未知状态必须落到中文兜底提示，而不是渲染原始状态字符串。
    fallback = job_recovery_action("unknown-state")
    _assert_chinese(fallback)


def test_selective_vision_step_name_is_persisted_in_chinese(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-stepname"
    )
    enq = enqueue_selective_vision_postprocess_for_revision(
        session_factory, seeded["revision_id"]
    )
    snapshot = _snap(session_factory, enq.job_id)
    assert snapshot.steps[0].step_id == STEP_ID
    assert snapshot.steps[0].name == "选择性视觉后处理"
    _assert_chinese(snapshot.steps[0].name)
    assert JOB_TYPE == "selective_vision_postprocess"


# ---------------------------------------------------------------------------
# 6) 无内部字段泄露：用户动作结果与错误文案
# ---------------------------------------------------------------------------


def test_user_action_outcomes_and_errors_carry_no_engineering_markers(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-leak"
    )
    service = SelectiveVisionPostprocessJobService(session_factory)
    enq = service.enqueue_for_revision(seeded["revision_id"])

    # 入队结果只暴露业务字段。
    assert set(enq.__dataclass_fields__) == {
        "job_id",
        "evidence_processing_revision_id",
        "created",
        "state",
    }

    cancelled = service.cancel(enq.job_id)
    assert set(cancelled.__dataclass_fields__) == {"state", "changed"}
    _assert_no_internal_markers(cancelled.state)

    with pytest.raises(JobStateConflictError) as error:
        service.retry(enq.job_id)
    message = str(error.value)
    _assert_chinese(message)
    _assert_no_internal_markers(message)
    assert set(error.value.context) == {"current_state"}

    # 服务级任务读取只暴露六个业务键（payload 为工程内部读取面，非用户投影）。
    job_view = service.get_job(enq.job_id)
    assert set(job_view) == {
        "job_id",
        "job_type",
        "state",
        "payload",
        "progress_total",
        "progress_completed",
    }


# ---------------------------------------------------------------------------
# 7) 修订 -> 任务投影：刷新恢复主入口与用户动作前的服务端校验
# ---------------------------------------------------------------------------


def _view_fields(view) -> set[str]:
    return {f.name for f in dataclasses.fields(view)}


def test_revision_task_view_is_stable_after_refresh_and_business_fields_only(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-view"
    )
    service = SelectiveVisionPostprocessJobService(session_factory)
    enq = service.enqueue_for_revision(seeded["revision_id"])

    # 页面刷新/进程重启：凭修订编号恢复同一任务投影，不依赖前端保存任务编号。
    view = service.get_revision_task(seeded["revision_id"])
    assert view.found is True
    assert view.job_id == enq.job_id
    assert view.state == "queued"
    assert view.cancel_requested is False
    assert view.plan_supported is True
    assert view.progress_total == 1
    assert view.progress_completed == 0
    assert view.failed_step_names == ()
    assert view.created_at is not None
    assert view.updated_at is not None

    # 投影只含业务字段，不携带载荷/错误分类/租约等内部字段。
    assert _view_fields(view) == {
        "evidence_processing_revision_id",
        "found",
        "job_id",
        "state",
        "cancel_requested",
        "plan_supported",
        "progress_completed",
        "progress_total",
        "failed_step_names",
        "eligible_page_count",
        "skipped_page_count",
        "observation_page_count",
        "closed_page_count",
        "closed_failure_kind",
        "created_at",
        "updated_at",
    }
    for name in ("payload", "error_code", "error_classification", "lease"):
        assert name not in _view_fields(view)


def test_revision_task_view_marks_revision_without_job_as_not_found(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-view-nojob"
    )
    service = SelectiveVisionPostprocessJobService(session_factory)

    # 修订存在但从未入队：found=False 空投影（前端渲染“暂无页面视觉核验任务”）。
    view = service.get_revision_task(seeded["revision_id"])
    assert view.found is False
    assert view.job_id is None
    assert view.state is None
    assert view.cancel_requested is False

    # 修订不存在：404 失败关闭，中文标题/恢复指引。
    with pytest.raises(EvidenceAppError) as error:
        service.get_revision_task("revision-does-not-exist")
    assert error.value.status_code == 404
    assert error.value.code == "NOT_FOUND"
    _assert_chinese(error.value.title)
    _assert_chinese(error.value.recovery)


def test_complete_revision_alias_resolves_base_task_without_duplicate_job(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-alias-base"
    )
    complete_revision_id = "rev-svo-uc-alias-complete"
    _seed_complete_revision_alias(
        session_factory, seeded["revision_id"], complete_revision_id
    )
    service = SelectiveVisionPostprocessJobService(session_factory)
    enqueued = service.enqueue_for_revision(seeded["revision_id"])

    view = service.get_revision_task(complete_revision_id)

    assert view.evidence_processing_revision_id == complete_revision_id
    assert view.job_id == enqueued.job_id
    assert view.found is True
    with session_factory() as session:
        assert (
            session.query(JobRecord)
            .filter(JobRecord.job_type == SELECTIVE_VISION_POSTPROCESS_JOB_TYPE)
            .count()
            == 1
        )


def test_complete_revision_alias_controls_same_base_task(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-action-alias-base"
    )
    complete_revision_id = "rev-svo-uc-action-alias-complete"
    _seed_complete_revision_alias(
        session_factory, seeded["revision_id"], complete_revision_id
    )
    service = SelectiveVisionPostprocessJobService(session_factory)
    enqueued = service.enqueue_for_revision(seeded["revision_id"])

    cancelled = service.cancel_revision_task(complete_revision_id)

    assert cancelled.job_id == enqueued.job_id
    assert cancelled.state == "cancelled"
    assert service.get_revision_task(seeded["revision_id"]).state == "cancelled"


def test_revision_view_reports_unsupported_plan_without_mutating(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-view-plan"
    )
    service = SelectiveVisionPostprocessJobService(session_factory)
    enq = service.enqueue_for_revision(
        seeded["revision_id"],
        plan_version="selective-vision-plan/obsolete",
    )

    view = service.get_revision_task(seeded["revision_id"])
    assert view.found is True
    assert view.job_id == enq.job_id
    assert view.plan_supported is False


def test_revision_keyed_cancel_and_retry_validate_before_mutating(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-rev-actions"
    )
    service = SelectiveVisionPostprocessJobService(session_factory)
    enq = service.enqueue_for_revision(seeded["revision_id"])

    # 取消走修订入口：立即收束，投影同步反映。
    outcome = service.cancel_revision_task(seeded["revision_id"])
    assert outcome.job_id == enq.job_id
    assert outcome.state == "cancelled"
    assert outcome.changed is True
    view = service.get_revision_task(seeded["revision_id"])
    assert view.state == "cancelled"
    assert view.cancel_requested is True

    # 取消后的任务不允许重试：稳定状态冲突，中文文案。
    with pytest.raises(JobStateConflictError) as error:
        service.retry_revision_task(seeded["revision_id"])
    assert error.value.current_state == "cancelled"
    _assert_chinese(str(error.value))
    _assert_no_internal_markers(str(error.value))

    # 未知修订：404 失败关闭，不产生任何任务行。
    with pytest.raises(EvidenceAppError) as error:
        service.cancel_revision_task("revision-does-not-exist")
    assert error.value.status_code == 404
    assert error.value.code == "NOT_FOUND"
    with pytest.raises(EvidenceAppError) as error:
        service.retry_revision_task("revision-does-not-exist")
    assert error.value.status_code == 404
    assert error.value.code == "NOT_FOUND"
    with session_factory() as session:
        vision_rows = (
            session.query(JobRecord)
            .filter(JobRecord.job_type == JOB_TYPE)
            .all()
        )
        assert [row.job_id for row in vision_rows] == [enq.job_id], "失败关闭不得新建视觉核验任务"


def test_revision_retry_versions_old_plan_without_rewriting_history(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-rev-plan"
    )
    enq = SelectiveVisionPostprocessJobService(session_factory).enqueue_for_revision(
        seeded["revision_id"],
        plan_version="selective-vision-plan/obsolete",
    )
    runner = JobRunner(
        session_factory,
        {
            JOB_TYPE: create_selective_vision_postprocess_executor(
                SelectiveVisionPostprocessExecutorConfig(
                    session_factory=session_factory,
                    data_paths=data_paths,
                    review_runner=_success_runner(),
                )
            )
        },
        worker_id="uc-rev-plan-worker",
        now=utc_now,
        poll_interval=0.01,
    )
    runner.run_once()
    assert _snap(session_factory, enq.job_id).state == "failed_final"

    # 旧作业保持原状；人工重试建立新版任务，不借用旧完成回执。
    service = SelectiveVisionPostprocessJobService(session_factory)
    upgraded = service.retry_revision_task(seeded["revision_id"])
    assert upgraded.changed is True
    assert upgraded.state == "queued"
    assert upgraded.job_id != enq.job_id
    assert _snap(session_factory, enq.job_id).state == "failed_final"
    assert service.get_revision_task(seeded["revision_id"]).job_id == upgraded.job_id
    assert service.get_revision_task(seeded["revision_id"]).plan_supported is True


def test_user_actions_reject_foreign_job_type_without_touching_it(
    session_factory, data_paths
):
    """任务类型与修订关联不一致时，用户动作必须失败且不触碰外部任务。"""
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-uc-foreign"
    )
    revision_id = seeded["revision_id"]

    # 制造“修订指向外部类型任务”的损坏关联：外部任务负载声称属于该修订，
    # 幂等记录也指向它（业务路径只能经由类型扫描/幂等记录命中）。
    foreign = JobService(session_factory).create_job(
        idempotency_key="foreign-key-uc",
        job_type="some_other_type",
        payload={
            "evidence_processing_revision_id": revision_id,
            "plan_version": "selective-vision-plan/v1",
        },
        steps=[StepSpec(step_id="s1", name="外部步骤")],
    )
    with session_factory() as session, session.begin():
        IdempotencyRepository(session).resolve(
            scope=JOB_IDEMPOTENCY_SCOPE,
            idempotency_key=selective_vision_postprocess_idempotency_key(revision_id),
            submitted_hash=request_hash({"foreign": True}),
            result_type="job",
            result_id=foreign.job_id,
        )

    service = SelectiveVisionPostprocessJobService(session_factory)
    # 查询投影、取消、重试全部被类型校验拦截。
    for action in (
        lambda: service.get_revision_task(revision_id),
        lambda: service.cancel_revision_task(revision_id),
        lambda: service.retry_revision_task(revision_id),
    ):
        with pytest.raises(EvidenceAppError) as error:
            action()
        assert error.value.code == "INTERNAL_ERROR"
        _assert_chinese(error.value.title)

    # 外部任务未被取消、未被重试，保持原状态。
    assert _snap(session_factory, foreign.job_id).state == "queued"


def test_task_is_active_matches_polling_semantics():
    service = SelectiveVisionPostprocessJobService.__new__(
        SelectiveVisionPostprocessJobService
    )
    active = {"queued", "running", "failed_retryable", "recovering"}
    inactive = {"completed", "failed_final", "cancelled", "cancel_requested"}
    for state in active:
        assert service.task_is_active(state) is True, state
    for state in inactive:
        assert service.task_is_active(state) is False, state
    assert service.task_is_active(None) is False
