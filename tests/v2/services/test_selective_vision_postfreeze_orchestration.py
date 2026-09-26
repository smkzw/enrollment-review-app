"""Phase 5 冻结修订后选择性视觉独立持久任务编排验收（worker_03）。

Acceptance boundary (worker_03 / postfreeze orchestration):
  ACCEPT —
    1. 冻结修订路径只幂等入队独立视觉后处理 Job，不 await/阻塞 VLM；
    2. 远端 VLM 调用不得持有数据库写事务；
    3. Job 重复入队复用同一任务；崩溃恢复/租约过期可继续且不重复成功观察；
    4. 提供方失败关闭只追加 closed，原生文字充分跳过模型；全程 OCR 原文不可变；
    5. EvidenceProcessingExecutor 冻结后接线仅 enqueue，不内联 run_postprocess。
  REJECT —
    在 OCR 核心事务/页租约内调用 VLM；入队时等待远端；改写 OCR raw_text；
    修改既有测试或生产文件（本文件仅为新增独立测试）。

Aligned to worker_02 production surface:
  app.services.selective_vision_postprocess_job_service
  app.services.selective_vision_postprocess_executor
  app.services.selective_vision_observation_service (事务外 VLM)
  app.services.evidence_processing_executor (freeze enqueue)
"""

from __future__ import annotations

import ast
import asyncio
import time
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
import fitz
from sqlalchemy import update

from app.domain.contracts.enums import (
    ExtractionRoute,
    PageArtifactStatus,
    SnapshotMemberOrigin,
    SnapshotStatus,
)
from app.domain.contracts.evidence_processing import EvidenceProcessingRevisionPage
from app.domain.contracts.ocr import OCRProfile
from app.domain.contracts.selective_vision_observation import (
    SelectiveVisionObservationStatus,
)
from app.domain.publication import evidence_processing_manifest_hash
from app.evidence.artifacts import ArtifactStore
from app.evidence.fingerprint import build_profile_fingerprint
from app.evidence.selective_vision_review import (
    SKIP_NATIVE_TEXT_PRIMARY,
    VISION_REASON_COMPLEX_VISUAL_OR_TABLE,
    VISION_REASON_NATIVE_EXTRACTION_ANOMALY,
    SelectiveVisionClosedError,
    SelectiveVisionObservation,
    SelectiveVisionPlan,
    SelectiveVisionReviewOutcome,
    VISION_REASON_SCAN_OR_IMAGE_ONLY,
    assess_page_vision_eligibility,
)
from app.services.selective_vision_observation_service import (
    SelectiveVisionObservationPageMaterial,
    SelectiveVisionObservationService,
)
from app.services.selective_vision_postprocess_executor import (
    SelectiveVisionPostprocessExecutorConfig,
    _pdf_non_text_marks,
    create_selective_vision_postprocess_executor,
)
from app.services.selective_vision_postprocess_job_service import (
    SELECTIVE_VISION_POSTPROCESS_JOB_TYPE,
    SELECTIVE_VISION_POSTPROCESS_STEP_ID,
    SelectiveVisionPostprocessJobService,
    enqueue_selective_vision_postprocess_for_revision,
)
from app.storage.codecs import utc_now
from app.storage.evidence_repositories import (
    BlobRepository,
    EvidenceSnapshotRepository,
    SourceDocumentRepository,
)
from app.storage.models import JobRecord
from app.storage.ocr_repositories import (
    EvidenceProcessingRevisionRepository,
    OcrPageRepository,
    OCRProfileRepository,
    PageArtifactRepository,
)
from app.storage.repositories import persist_fixture
from app.storage.selective_vision_observation_repository import (
    SelectiveVisionObservationRepository,
)
from app.workflow.errors import ProcessDeath, StepFailure
from app.workflow.jobstore import JobStore
from app.workflow.recovery import recover_expired_jobs
from app.workflow.runner import JobRunner, StepContext
from tests.v2.storage.test_ocr_repositories import (
    FIXED_UTC,
    make_artifact,
    make_blob,
    make_ocr_page,
    make_profile,
    make_revision,
    make_snapshot,
    make_version,
)
from tests.v2.storage.test_repositories_roundtrip import FIXTURES

REPO_ROOT = Path(__file__).resolve().parents[3]
EXECUTOR_PATH = REPO_ROOT / "app" / "services" / "evidence_processing_executor.py"
IMAGE_BYTES = b"\x89PNG\r\n\x1a\nselective-vision-postfreeze"
IMAGE_SHA = sha256(IMAGE_BYTES).hexdigest()
# 视觉任务夹具模拟“已有识别尝试，但正文不足以直接采信”。仍保留一个字符，
# 以便验证选择性视觉处理前后不会改写既有 OCR 原文或哈希。
RAW_TEXT = "x"
NATIVE_RAW_TEXT = "native text primary path for skip after freeze"


def test_pdf_mark_probe_distinguishes_plain_text_from_drawn_annotation():
    pdf = fitz.open()
    plain = pdf.new_page()
    plain.insert_text((72, 72), "Printed clinical observation", fontsize=12)
    marked = pdf.new_page()
    marked.insert_text((72, 72), "Printed clinical observation", fontsize=12)
    marked.draw_rect(fitz.Rect(65, 55, 245, 82), color=(1, 0, 0))
    inked = pdf.new_page()
    inked.insert_text((72, 72), "Printed clinical observation", fontsize=12)
    inked.add_ink_annot([[(72, 90), (90, 90), (120, 80)]])
    linked = pdf.new_page()
    linked.insert_text((72, 72), "Printed clinical observation", fontsize=12)
    linked.insert_link({
        "kind": fitz.LINK_URI,
        "from": fitz.Rect(72, 55, 250, 75),
        "uri": "https://example.org",
    })

    counts = _pdf_non_text_marks(pdf.tobytes())

    assert counts[1] == 0
    assert counts[2] > 0
    assert counts[3] > 0
    assert counts[4] == 0


def _run(coro):
    return asyncio.run(coro)


def _native_profile() -> OCRProfile:
    profile_sha = build_profile_fingerprint(
        extraction_route="native_pdf_text",
        provider="native",
        model_id="native-pdf",
        model_revision="unknown",
        prompt_sha256=None,
        parser_version="v1",
        render_params_sha256=None,
        request_params_sha256=None,
        layout_parser_version="layout-v1",
        coordinate_transform_version="transform-v1",
    )
    return OCRProfile(
        ocr_profile_id="profile-native-pdf",
        profile_sha256=profile_sha,
        extraction_route=ExtractionRoute.NATIVE_PDF_TEXT,
        provider="native",
        model_id="native-pdf",
        model_revision="unknown",
        parser_version="v1",
        layout_parser_version="layout-v1",
        coordinate_transform_version="transform-v1",
        created_at=FIXED_UTC,
    )


def _seed_frozen_revision(
    session_factory,
    data_paths,
    *,
    revision_id: str,
    raw_text: str = RAW_TEXT,
    native_route: bool = False,
    put_native_text: bool = False,
    source_bytes: bytes | None = None,
) -> dict[str, Any]:
    """播种已冻结基础处理修订 + 页产物/OCR + 内容寻址页图。"""
    store = ArtifactStore(data_paths)
    stored = store.put("page_image", IMAGE_BYTES)
    assert stored.sha256 == IMAGE_SHA
    native_text_sha = None
    if put_native_text:
        native_text_sha = store.put("native_text", raw_text.encode("utf-8")).sha256

    with session_factory() as session, session.begin():
        fixture = FIXTURES[0]
        persist_fixture(session, fixture)
        project_id = fixture.project.project_id
        subject_id = fixture.subject.subject_id
        episode_id = fixture.review_episode.review_episode_id
        scope = (project_id, subject_id, episode_id)

        blob = make_blob(source_bytes if source_bytes is not None else b"pdf-bytes-svo-postfreeze")
        BlobRepository(session).get_or_create_by_sha256(blob)
        if source_bytes is not None:
            target = data_paths.boundary.require_v2_target(data_paths.root / blob.storage_ref)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source_bytes)
        version = make_version(
            version_id="doc-svo-1",
            logical_id="log-svo-1",
            blob_sha=blob.sha256,
            scope=scope,
            page_count=1,
        )
        SourceDocumentRepository(session).create_version(version)
        snapshot = make_snapshot(
            snapshot_id="snap-svo-1",
            scope=scope,
            members=[("log-svo-1", "doc-svo-1", SnapshotMemberOrigin.ADDED)],
        )
        EvidenceSnapshotRepository(session).create_full(snapshot)
        EvidenceSnapshotRepository(session).transition_status(
            "snap-svo-1",
            event="worker_start",
            new_status=SnapshotStatus.PROCESSING,
            actor="tester",
            reason="start",
        )
        profile = OCRProfileRepository(session).get_or_create(
            _native_profile() if native_route else make_profile()
        )
        PageArtifactRepository(session).get_or_create(
            make_artifact(
                artifact_id="pa-svo-1",
                version_id="doc-svo-1",
                page_image=IMAGE_SHA,
                page_input=IMAGE_SHA,
                status=PageArtifactStatus.SUCCEEDED,
                native_text_sha256=native_text_sha,
            )
        )
        page = OcrPageRepository(session).create(
            make_ocr_page(
                page_id="op-svo-1",
                artifact_id="pa-svo-1",
                profile_sha=profile.profile_sha256,
                page_input=IMAGE_SHA,
                raw_text=raw_text,
            )
        )
        entry = EvidenceProcessingRevisionPage(
            entry_id="e-svo-1",
            position=1,
            source_document_version_id="doc-svo-1",
            page_number=1,
            original_frame=None,
            page_artifact_id="pa-svo-1",
            ocr_page_id=page.ocr_page_id,
            status=PageArtifactStatus.SUCCEEDED,
        )
        manifest_hash = evidence_processing_manifest_hash(
            entries=[
                (
                    "doc-svo-1",
                    1,
                    None,
                    "pa-svo-1",
                    page.ocr_page_id,
                    PageArtifactStatus.SUCCEEDED.value,
                )
            ]
        )
        EvidenceProcessingRevisionRepository(session).create(
            make_revision(
                {
                    "project_id": project_id,
                    "subject_id": subject_id,
                    "episode_id": episode_id,
                    "entry": entry,
                    "manifest_hash": manifest_hash,
                },
                evidence_processing_revision_id=revision_id,
                evidence_snapshot_id="snap-svo-1",
            )
        )
        return {
            "revision_id": revision_id,
            "page_artifact_id": "pa-svo-1",
            "ocr_page_id": page.ocr_page_id,
            "raw_text": page.raw_text,
            "raw_text_sha256": page.raw_text_sha256,
            "image_sha": IMAGE_SHA,
        }


def _eligible_material(seeded: dict[str, Any]) -> SelectiveVisionObservationPageMaterial:
    return SelectiveVisionObservationPageMaterial(
        page_artifact_id=seeded["page_artifact_id"],
        source_ref=seeded["page_artifact_id"],
        page_ordinal=1,
        page_image_sha256=seeded["image_sha"],
        media_kind="image",
        extraction_route=ExtractionRoute.VISION_OCR.value,
        page_artifact_status=PageArtifactStatus.SUCCEEDED.value,
        has_page_image=True,
        has_native_text=False,
        native_text_char_count=0,
        ocr_page_id=seeded["ocr_page_id"],
        image_bytes=IMAGE_BYTES,
    )


def test_frozen_pdf_marks_reach_page_review_plan(session_factory, data_paths):
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Printed clinical observation", fontsize=12)
    page.draw_rect(fitz.Rect(65, 55, 245, 82), color=(1, 0, 0))
    seeded = _seed_frozen_revision(
        session_factory, data_paths,
        revision_id="rev-svo-pdf-marks", native_route=True,
        put_native_text=True, raw_text="Printed clinical observation",
        source_bytes=pdf.tobytes(),
    )
    from app.services.selective_vision_postprocess_executor import (
        load_selective_vision_page_materials_for_revision,
    )

    with session_factory() as session:
        materials = load_selective_vision_page_materials_for_revision(
            session, evidence_processing_revision_id=seeded["revision_id"],
            artifact_store=ArtifactStore(data_paths),
        )
    assert len(materials) == 1
    assert materials[0].non_text_mark_count is not None
    assert materials[0].non_text_mark_count > 0
    signals = SelectiveVisionObservationService(session_factory)._to_signals(materials[0])
    decision = assess_page_vision_eligibility(signals)
    assert decision.eligible
    assert VISION_REASON_COMPLEX_VISUAL_OR_TABLE in decision.reasons


def test_unreadable_pdf_marks_require_original_page_review(session_factory, data_paths):
    seeded = _seed_frozen_revision(
        session_factory, data_paths,
        revision_id="rev-svo-bad-pdf", native_route=True,
        put_native_text=True, raw_text="Printed clinical observation",
        source_bytes=b"not a valid PDF",
    )
    from app.services.selective_vision_postprocess_executor import (
        load_selective_vision_page_materials_for_revision,
    )

    with session_factory() as session:
        materials = load_selective_vision_page_materials_for_revision(
            session, evidence_processing_revision_id=seeded["revision_id"],
            artifact_store=ArtifactStore(data_paths),
        )
    assert materials[0].non_text_mark_count is None
    assert materials[0].native_extraction_anomaly
    signals = SelectiveVisionObservationService(session_factory)._to_signals(materials[0])
    assert VISION_REASON_NATIVE_EXTRACTION_ANOMALY in assess_page_vision_eligibility(signals).reasons


def test_changed_pdf_original_stops_mark_planning(session_factory, data_paths):
    original = b"not a valid PDF"
    seeded = _seed_frozen_revision(
        session_factory, data_paths,
        revision_id="rev-svo-changed-pdf", native_route=True,
        put_native_text=True, raw_text="Printed clinical observation",
        source_bytes=original,
    )
    from app.services.selective_vision_postprocess_executor import (
        load_selective_vision_page_materials_for_revision,
    )

    with session_factory() as session:
        blob = BlobRepository(session).get(sha256(original).hexdigest())
        source_path = data_paths.boundary.require_v2_target(data_paths.root / blob.storage_ref)
        source_path.write_bytes(b"changed source bytes")
        with pytest.raises(ValueError, match="source blob digest mismatch"):
            load_selective_vision_page_materials_for_revision(
                session, evidence_processing_revision_id=seeded["revision_id"],
                artifact_store=ArtifactStore(data_paths),
            )


def _native_material(seeded: dict[str, Any]) -> SelectiveVisionObservationPageMaterial:
    return SelectiveVisionObservationPageMaterial(
        page_artifact_id=seeded["page_artifact_id"],
        source_ref=seeded["page_artifact_id"],
        page_ordinal=1,
        page_image_sha256=seeded["image_sha"],
        media_kind="pdf",
        extraction_route=ExtractionRoute.NATIVE_PDF_TEXT.value,
        page_artifact_status=PageArtifactStatus.SUCCEEDED.value,
        has_page_image=True,
        has_native_text=True,
        native_text_char_count=max(64, len(NATIVE_RAW_TEXT)),
        ocr_page_id=seeded["ocr_page_id"],
        image_bytes=IMAGE_BYTES,
    )


def _assert_ocr_immutable(session_factory, seeded: dict[str, Any]) -> None:
    with session_factory() as session:
        ocr = OcrPageRepository(session).get(seeded["ocr_page_id"])
        assert ocr.raw_text == seeded["raw_text"]
        assert ocr.raw_text_sha256 == seeded["raw_text_sha256"]


def _build_runner(session_factory, data_paths, *, review_runner):
    return JobRunner(
        session_factory,
        {
            SELECTIVE_VISION_POSTPROCESS_JOB_TYPE: create_selective_vision_postprocess_executor(
                SelectiveVisionPostprocessExecutorConfig(
                    session_factory=session_factory,
                    data_paths=data_paths,
                    review_runner=review_runner,
                )
            )
        },
        worker_id="svo-postfreeze-worker",
        now=utc_now,
        poll_interval=0.01,
    )


class _BeginTracker:
    """统计 session.begin() 嵌套深度；用于断言远端调用不落在打开事务内。"""

    def __init__(self, inner_factory) -> None:
        self._inner = inner_factory
        self.active_begins = 0

    def __call__(self):
        session = self._inner()
        tracker = self
        original_begin = session.begin

        class _TrackedBegin:
            def __init__(self) -> None:
                self._cm = None

            def __enter__(self):
                tracker.active_begins += 1
                self._cm = original_begin()
                return self._cm.__enter__()

            def __exit__(self, exc_type, exc, tb):
                try:
                    return self._cm.__exit__(exc_type, exc, tb)
                finally:
                    tracker.active_begins -= 1

        session.begin = lambda *args, **kwargs: _TrackedBegin()  # type: ignore[method-assign]
        return session


# ---------------------------------------------------------------------------
# 1) 远端调用不得持有数据库事务
# ---------------------------------------------------------------------------


def test_remote_vlm_call_does_not_hold_database_transaction(session_factory, data_paths):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-txn"
    )
    tracker = _BeginTracker(session_factory)
    observed: dict[str, int | None] = {"active_begins_during_vlm": None}

    async def runner(plan: SelectiveVisionPlan, inputs):
        observed["active_begins_during_vlm"] = tracker.active_begins
        page = inputs[0]
        return SelectiveVisionReviewOutcome(
            plan=plan,
            observations=(
                SelectiveVisionObservation(
                    source_refs=(page.source_ref,),
                    page_ordinals=(page.page_ordinal,),
                    reasons=(VISION_REASON_SCAN_OR_IMAGE_ONLY,),
                    text=f"source_ref={page.source_ref}\npostfreeze txn probe",
                    model="mock-vlm",
                    finish_reason="stop",
                    usage={"prompt_tokens": 3},
                ),
            ),
        )

    service = SelectiveVisionObservationService(
        tracker, review_runner=runner, default_model_id="mock-vlm"
    )
    result = _run(service.run_postprocess([_eligible_material(seeded)]))

    assert observed["active_begins_during_vlm"] == 0, (
        "远端 VLM 调用期间仍处于打开的 session.begin() 中 "
        f"(active_begins={observed['active_begins_during_vlm']})"
    )
    assert result.closed_error is None
    assert result.observations
    _assert_ocr_immutable(session_factory, seeded)


# ---------------------------------------------------------------------------
# 2) 冻结后只幂等入队，不等待 VLM
# ---------------------------------------------------------------------------


def test_enqueue_after_freeze_is_idempotent_and_does_not_await_vlm(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-enqueue"
    )
    vlm_calls = {"n": 0}

    async def blocking_vlm(plan, inputs):  # pragma: no cover
        vlm_calls["n"] += 1
        await asyncio.sleep(60)
        raise AssertionError("enqueue 不得进入 VLM")

    SelectiveVisionObservationService(
        session_factory, review_runner=blocking_vlm, default_model_id="mock-vlm"
    )

    started = time.monotonic()
    first = enqueue_selective_vision_postprocess_for_revision(
        session_factory,
        seeded["revision_id"],
        trigger="evidence_processing_freeze",
    )
    second = enqueue_selective_vision_postprocess_for_revision(
        session_factory,
        seeded["revision_id"],
        trigger="evidence_processing_freeze",
    )
    elapsed = time.monotonic() - started

    assert elapsed < 2.0, f"入队不应等待 VLM，耗时 {elapsed:.3f}s"
    assert vlm_calls["n"] == 0
    assert first.job_id
    assert second.job_id == first.job_id
    assert first.created is True
    assert second.created is False

    with session_factory() as session:
        job = session.get(JobRecord, first.job_id)
        assert job is not None
        assert job.job_type == SELECTIVE_VISION_POSTPROCESS_JOB_TYPE
        assert job.state == "queued"
        store = JobStore(session, now=utc_now)
        assert store.snapshot(first.job_id).progress_completed == 0


def test_job_service_enqueue_for_revision_matches_module_helper(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-service-enqueue"
    )
    service = SelectiveVisionPostprocessJobService(session_factory)
    first = service.enqueue_for_revision(seeded["revision_id"])
    second = service.enqueue_for_revision(seeded["revision_id"])
    assert first.job_id == second.job_id
    assert first.created is True
    assert second.created is False


def test_enqueue_rejects_unknown_revision_without_creating_job(
    session_factory, data_paths
) -> None:
    with pytest.raises(Exception, match="不存在|not found"):
        SelectiveVisionPostprocessJobService(session_factory).enqueue_for_revision(
            "revision-does-not-exist"
        )

    with session_factory() as session:
        assert session.query(JobRecord).count() == 0


def test_evidence_processing_executor_freeze_path_only_enqueues_ast() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(EXECUTOR_PATH))

    assert "enqueue_selective_vision_postprocess_for_revision" in source
    assert "selective_vision_postprocess_job_service" in source
    assert "run_postprocess" not in source
    assert "run_selective_vision_review" not in source
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            rendered = ast.unparse(node)
            assert "independent_vlm" not in rendered, rendered


# ---------------------------------------------------------------------------
# 3) Job 执行：原生跳过 / 失败关闭 / OCR 不可变 / 重复与恢复
# ---------------------------------------------------------------------------


def test_job_executor_native_text_skip_does_not_call_vlm_or_mutate_ocr(
    session_factory, data_paths
):
    pdf = fitz.open()
    pdf.new_page().insert_text((72, 72), NATIVE_RAW_TEXT)
    seeded = _seed_frozen_revision(
        session_factory,
        data_paths,
        revision_id="rev-svo-native-skip",
        raw_text=NATIVE_RAW_TEXT,
        native_route=True,
        put_native_text=True,
        source_bytes=pdf.tobytes(),
    )
    calls = {"n": 0}

    async def runner(plan, inputs):  # pragma: no cover
        calls["n"] += 1
        raise AssertionError("原生文字充分时 Job 执行器不得调用 VLM")

    created = enqueue_selective_vision_postprocess_for_revision(
        session_factory, seeded["revision_id"]
    )
    assert _build_runner(
        session_factory, data_paths, review_runner=runner
    ).run_once()
    assert calls["n"] == 0

    with session_factory() as session:
        store = JobStore(session, now=utc_now)
        assert store.snapshot(created.job_id).state == "completed"
        listed = SelectiveVisionObservationRepository(session).list_by_page_artifact(
            seeded["page_artifact_id"]
        )
        assert all(
            row.status != SelectiveVisionObservationStatus.SUCCEEDED for row in listed
        )
    _assert_ocr_immutable(session_factory, seeded)


def test_job_executor_remote_failure_closes_without_mutating_ocr(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-fail-closed"
    )

    async def runner(plan: SelectiveVisionPlan, inputs):
        return SelectiveVisionReviewOutcome(
            plan=plan,
            closed_error=SelectiveVisionClosedError(
                "provider closed",
                failure_kind="remote_error",
                disabled=True,
            ),
        )

    created = enqueue_selective_vision_postprocess_for_revision(
        session_factory, seeded["revision_id"]
    )
    assert _build_runner(
        session_factory, data_paths, review_runner=runner
    ).run_once()

    with session_factory() as session:
        store = JobStore(session, now=utc_now)
        assert store.snapshot(created.job_id).state == "failed_final"
        listed = SelectiveVisionObservationRepository(session).list_by_page_artifact(
            seeded["page_artifact_id"]
        )
        assert listed, "失败关闭应追加 closed 审计行"
        assert all(
            row.status == SelectiveVisionObservationStatus.CLOSED for row in listed
        )
        assert all(row.observation_text is None for row in listed)
        assert all(row.failure_kind == "remote_error" for row in listed)
    assert SelectiveVisionPostprocessJobService(session_factory).retry_revision_task(
        seeded["revision_id"]
    ).state == "queued"

    async def recovered(plan: SelectiveVisionPlan, inputs):
        page = inputs[0]
        return SelectiveVisionReviewOutcome(
            plan=plan,
            observations=(SelectiveVisionObservation(
                source_refs=(page.source_ref,),
                page_ordinals=(page.page_ordinal,),
                reasons=(VISION_REASON_SCAN_OR_IMAGE_ONLY,),
                text=f"source_ref={page.source_ref}\n核对后的原文",
                model="mock-vlm",
                finish_reason="stop",
            ),),
        )

    assert _build_runner(session_factory, data_paths, review_runner=recovered).run_once()
    with session_factory() as session:
        assert JobStore(session, now=utc_now).snapshot(created.job_id).state == "completed"
        assert len([
            row for row in SelectiveVisionObservationRepository(session).list_by_page_artifact(
                seeded["page_artifact_id"]
            ) if row.status == SelectiveVisionObservationStatus.SUCCEEDED
        ]) == 1
    assert SelectiveVisionPostprocessJobService(session_factory).coverage_page_ids_match(
        seeded["revision_id"]
    ) is True
    _assert_ocr_immutable(session_factory, seeded)


def test_old_plan_receipt_is_not_accepted_as_current_coverage(session_factory, data_paths):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-legacy-plan"
    )
    service = SelectiveVisionPostprocessJobService(session_factory)
    service.enqueue_for_revision(seeded["revision_id"], plan_version="selective_vision_review/v1")
    view = service.get_revision_task(seeded["revision_id"])
    assert view.plan_supported is False
    assert service.coverage_page_ids_match(seeded["revision_id"]) is False


def test_empty_model_observation_cannot_complete_page_coverage(session_factory, data_paths):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-empty-model-output"
    )

    async def incomplete(plan: SelectiveVisionPlan, inputs):
        return SelectiveVisionReviewOutcome(plan=plan, observations=())

    created = enqueue_selective_vision_postprocess_for_revision(
        session_factory, seeded["revision_id"]
    )
    assert _build_runner(session_factory, data_paths, review_runner=incomplete).run_once()
    with session_factory() as session:
        assert JobStore(session, now=utc_now).snapshot(created.job_id).state == "failed_final"
    assert SelectiveVisionPostprocessJobService(session_factory).coverage_page_ids_match(
        seeded["revision_id"]
    ) is False


def test_completed_receipt_rejects_observation_from_another_page(
    session_factory, data_paths, monkeypatch,
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-mismatched-observation"
    )

    async def valid(plan: SelectiveVisionPlan, inputs):
        page = inputs[0]
        return SelectiveVisionReviewOutcome(
            plan=plan,
            observations=(SelectiveVisionObservation(
                source_refs=(page.source_ref,),
                page_ordinals=(page.page_ordinal,),
                reasons=(VISION_REASON_SCAN_OR_IMAGE_ONLY,),
                text=f"source_ref={page.source_ref}\n来源明确的页面观察",
                model="mock-vlm",
                finish_reason="stop",
                usage={},
            ),),
        )

    created = enqueue_selective_vision_postprocess_for_revision(
        session_factory, seeded["revision_id"]
    )
    assert _build_runner(session_factory, data_paths, review_runner=valid).run_once()
    service = SelectiveVisionPostprocessJobService(session_factory)
    assert service.coverage_page_ids_match(seeded["revision_id"])
    original = SelectiveVisionObservationRepository.get_or_none

    def wrong_page(self, observation_id):
        row = original(self, observation_id)
        return row.model_copy(update={"page_artifact_id": "another-page"}) if row else None

    monkeypatch.setattr(SelectiveVisionObservationRepository, "get_or_none", wrong_page)
    assert service.coverage_page_ids_match(seeded["revision_id"]) is False
    with session_factory() as session:
        assert JobStore(session, now=utc_now).snapshot(created.job_id).state == "completed"


def test_job_executor_success_is_idempotent_across_rerun(session_factory, data_paths):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-success-idem"
    )
    calls = {"n": 0}

    async def runner(plan: SelectiveVisionPlan, inputs):
        calls["n"] += 1
        page = inputs[0]
        return SelectiveVisionReviewOutcome(
            plan=plan,
            observations=(
                SelectiveVisionObservation(
                    source_refs=(page.source_ref,),
                    page_ordinals=(page.page_ordinal,),
                    reasons=(VISION_REASON_SCAN_OR_IMAGE_ONLY,),
                    text=f"source_ref={page.source_ref}\nstable observation body",
                    model="mock-vlm",
                    finish_reason="stop",
                    usage={"prompt_tokens": 8},
                ),
            ),
        )

    created = enqueue_selective_vision_postprocess_for_revision(
        session_factory, seeded["revision_id"]
    )
    runner_obj = _build_runner(session_factory, data_paths, review_runner=runner)
    assert runner_obj.run_once()

    with session_factory() as session:
        listed = SelectiveVisionObservationRepository(session).list_by_page_artifact(
            seeded["page_artifact_id"]
        )
        assert len(listed) == 1
        assert listed[0].status == SelectiveVisionObservationStatus.SUCCEEDED
        first_id = listed[0].observation_id

    again = enqueue_selective_vision_postprocess_for_revision(
        session_factory, seeded["revision_id"]
    )
    assert again.job_id == created.job_id
    assert again.created is False

    # 同输入再次显式后处理：成功观察身份幂等复用，不得新增第二条成功行。
    service = SelectiveVisionObservationService(
        session_factory, review_runner=runner, default_model_id="mock-vlm"
    )
    from app.services.selective_vision_postprocess_executor import (
        load_selective_vision_page_materials_for_revision,
    )

    with session_factory() as session:
        materials = load_selective_vision_page_materials_for_revision(
            session,
            evidence_processing_revision_id=seeded["revision_id"],
            artifact_store=ArtifactStore(data_paths),
        )
    replay = _run(service.run_postprocess(materials))
    assert replay.reused_observation_ids
    assert first_id in replay.reused_observation_ids

    with session_factory() as session:
        listed = SelectiveVisionObservationRepository(session).list_by_page_artifact(
            seeded["page_artifact_id"]
        )
        succeeded = [
            row
            for row in listed
            if row.status == SelectiveVisionObservationStatus.SUCCEEDED
        ]
        assert len(succeeded) == 1
        assert succeeded[0].observation_id == first_id
    _assert_ocr_immutable(session_factory, seeded)
    assert calls["n"] >= 1


def test_job_recovery_after_expired_lease_completes_without_duplicate_success(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-recover"
    )

    async def runner(plan: SelectiveVisionPlan, inputs):
        page = inputs[0]
        return SelectiveVisionReviewOutcome(
            plan=plan,
            observations=(
                SelectiveVisionObservation(
                    source_refs=(page.source_ref,),
                    page_ordinals=(page.page_ordinal,),
                    reasons=(VISION_REASON_SCAN_OR_IMAGE_ONLY,),
                    text=f"source_ref={page.source_ref}\nrecovered observation",
                    model="mock-vlm",
                    finish_reason="stop",
                    usage={"prompt_tokens": 5},
                ),
            ),
        )

    created = enqueue_selective_vision_postprocess_for_revision(
        session_factory, seeded["revision_id"]
    )
    with session_factory() as session, session.begin():
        session.execute(
            update(JobRecord)
            .where(JobRecord.job_id == created.job_id)
            .values(
                state="running",
                lease_owner="dead-worker",
                lease_generation=1,
                lease_expires_at=utc_now() - timedelta(seconds=5),
            )
        )

    recover_expired_jobs(session_factory, now=utc_now)
    assert _build_runner(
        session_factory, data_paths, review_runner=runner
    ).run_once()

    with session_factory() as session:
        store = JobStore(session, now=utc_now)
        assert store.snapshot(created.job_id).state == "completed"
        listed = SelectiveVisionObservationRepository(session).list_by_page_artifact(
            seeded["page_artifact_id"]
        )
        succeeded = [
            row
            for row in listed
            if row.status == SelectiveVisionObservationStatus.SUCCEEDED
        ]
        assert len(succeeded) == 1
    _assert_ocr_immutable(session_factory, seeded)


def test_process_death_before_persist_then_recover_single_success(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory, data_paths, revision_id="rev-svo-death"
    )
    state = {"armed": True}

    async def runner(plan: SelectiveVisionPlan, inputs):
        page = inputs[0]
        return SelectiveVisionReviewOutcome(
            plan=plan,
            observations=(
                SelectiveVisionObservation(
                    source_refs=(page.source_ref,),
                    page_ordinals=(page.page_ordinal,),
                    reasons=(VISION_REASON_SCAN_OR_IMAGE_ONLY,),
                    text=f"source_ref={page.source_ref}\nafter death recovery",
                    model="mock-vlm",
                    finish_reason="stop",
                    usage={"prompt_tokens": 4},
                ),
            ),
        )

    real_executor = create_selective_vision_postprocess_executor(
        SelectiveVisionPostprocessExecutorConfig(
            session_factory=session_factory,
            data_paths=data_paths,
            review_runner=runner,
        )
    )

    def crash_once(context):
        if state["armed"]:
            state["armed"] = False
            raise ProcessDeath("simulated crash before selective vision persist")
        return real_executor(context)

    created = enqueue_selective_vision_postprocess_for_revision(
        session_factory, seeded["revision_id"]
    )
    with pytest.raises(ProcessDeath):
        JobRunner(
            session_factory,
            {SELECTIVE_VISION_POSTPROCESS_JOB_TYPE: crash_once},
            worker_id="doomed",
            now=utc_now,
            poll_interval=0.01,
        ).run_once()

    with session_factory() as session:
        listed = SelectiveVisionObservationRepository(session).list_by_page_artifact(
            seeded["page_artifact_id"]
        )
        assert not any(
            row.status == SelectiveVisionObservationStatus.SUCCEEDED for row in listed
        )

    with session_factory() as session, session.begin():
        session.execute(
            update(JobRecord)
            .where(JobRecord.job_id == created.job_id)
            .values(
                state="running",
                lease_owner="doomed",
                lease_generation=1,
                lease_expires_at=utc_now() - timedelta(seconds=5),
            )
        )
    recover_expired_jobs(session_factory, now=utc_now)

    assert JobRunner(
        session_factory,
        {SELECTIVE_VISION_POSTPROCESS_JOB_TYPE: real_executor},
        worker_id="reviver",
        now=utc_now,
        poll_interval=0.01,
    ).run_once()

    with session_factory() as session:
        store = JobStore(session, now=utc_now)
        assert store.snapshot(created.job_id).state == "completed"
        listed = SelectiveVisionObservationRepository(session).list_by_page_artifact(
            seeded["page_artifact_id"]
        )
        succeeded = [
            row
            for row in listed
            if row.status == SelectiveVisionObservationStatus.SUCCEEDED
        ]
        assert len(succeeded) == 1
    _assert_ocr_immutable(session_factory, seeded)


def test_direct_service_native_skip_and_ocr_immutability_regression(
    session_factory, data_paths
):
    seeded = _seed_frozen_revision(
        session_factory,
        data_paths,
        revision_id="rev-svo-service-native",
        raw_text=NATIVE_RAW_TEXT,
        native_route=True,
    )

    async def runner(plan, inputs):  # pragma: no cover
        raise AssertionError("原生文字充分时不得调用视觉模型")

    service = SelectiveVisionObservationService(
        session_factory, review_runner=runner, default_model_id="mock-vlm"
    )
    result = _run(service.run_postprocess([_native_material(seeded)]))
    assert not result.plan.eligible
    assert result.observations == ()
    assert any(item.skip_reason == SKIP_NATIVE_TEXT_PRIMARY for item in result.skipped)
    with session_factory() as session:
        assert (
            SelectiveVisionObservationRepository(session).list_by_page_artifact(
                seeded["page_artifact_id"]
            )
            == []
        )
    _assert_ocr_immutable(session_factory, seeded)


def test_postprocess_step_id_constant_matches_job_definition() -> None:
    assert SELECTIVE_VISION_POSTPROCESS_STEP_ID == "run_selective_vision"


@pytest.mark.parametrize("stale_version", [
    "selective-vision-plan/obsolete", "selective_vision_review/v2",
    "selective_vision_review/v3",
])
def test_executor_rejects_frozen_plan_version_drift_before_loading_or_vlm(
    session_factory, data_paths, stale_version
) -> None:
    calls = {"n": 0}

    async def runner(plan, inputs):  # pragma: no cover - must not run
        calls["n"] += 1
        raise AssertionError("规划版本不一致时不得调用视觉模型")

    executor = create_selective_vision_postprocess_executor(
        SelectiveVisionPostprocessExecutorConfig(
            session_factory=session_factory,
            data_paths=data_paths,
            review_runner=runner,
        )
    )
    context = StepContext(
        job_id="job-plan-drift",
        job_type=SELECTIVE_VISION_POSTPROCESS_JOB_TYPE,
        job_payload={
            "evidence_processing_revision_id": "revision-must-not-be-loaded",
            "plan_version": stale_version,
        },
        step_id=SELECTIVE_VISION_POSTPROCESS_STEP_ID,
        name="选择性视觉后处理",
        attempt=1,
        last_checkpoint_id=None,
        last_checkpoint=None,
        max_attempts=3,
    )

    with pytest.raises(StepFailure) as error:
        executor(context)
    assert error.value.retryable is False
    assert error.value.error_code == "SELECTIVE_VISION_PLAN_VERSION_UNSUPPORTED"
    assert calls["n"] == 0
    assert SELECTIVE_VISION_POSTPROCESS_JOB_TYPE == "selective_vision_postprocess"
