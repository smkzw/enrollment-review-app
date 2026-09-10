"""选择性视觉观察后处理服务：显式调用、原生文字跳过、失败关闭且不改 OCR。

Aligned to worker_02 surface:
  app.services.selective_vision_observation_service
"""

from __future__ import annotations

import asyncio
from hashlib import sha256



from app.domain.contracts.enums import (
    ExtractionRoute,
    PageArtifactStatus,
    SnapshotMemberOrigin,
    SnapshotStatus,
)
from app.domain.contracts.selective_vision_observation import (
    SelectiveVisionObservationStatus,
)
from app.evidence.selective_vision_review import (
    SKIP_NATIVE_TEXT_PRIMARY,
    SelectiveVisionClosedError,
    SelectiveVisionObservation,
    SelectiveVisionPlan,
    SelectiveVisionReviewOutcome,
    VISION_REASON_SCAN_OR_IMAGE_ONLY,
)
from app.services.selective_vision_observation_service import (
    SelectiveVisionObservationBatchResult,
    SelectiveVisionObservationPageMaterial,
    SelectiveVisionObservationService,
)
from app.storage.evidence_repositories import (
    BlobRepository,
    EvidenceSnapshotRepository,
    SourceDocumentRepository,
)
from app.storage.ocr_repositories import (
    OcrPageRepository,
    OCRProfileRepository,
    PageArtifactRepository,
)
from app.storage.repositories import persist_fixture
from app.storage.selective_vision_observation_repository import (
    SelectiveVisionObservationRepository,
)
from tests.v2.storage.test_ocr_repositories import (
    make_artifact,
    make_blob,
    make_ocr_page,
    make_profile,
    make_snapshot,
    make_version,
)
from tests.v2.storage.test_repositories_roundtrip import FIXTURES


IMAGE_BYTES = b"\x89PNG\r\n\x1a\nselective-vision-page"
IMAGE_SHA = sha256(IMAGE_BYTES).hexdigest()
RAW_TEXT = "native text primary path for skip"


def _seed(session_factory) -> dict[str, str]:
    with session_factory() as session, session.begin():
        fixture = FIXTURES[0]
        persist_fixture(session, fixture)
        project_id = fixture.project.project_id
        subject_id = fixture.subject.subject_id
        episode_id = fixture.review_episode.review_episode_id
        scope = (project_id, subject_id, episode_id)
        blob = make_blob(b"pdf-bytes-svo-svc")
        BlobRepository(session).get_or_create_by_sha256(blob)
        version = make_version(
            version_id="doc-1", logical_id="log-1", blob_sha=blob.sha256, scope=scope
        )
        SourceDocumentRepository(session).create_version(version)
        snapshot = make_snapshot(
            snapshot_id="snap-1",
            scope=scope,
            members=[("log-1", "doc-1", SnapshotMemberOrigin.ADDED)],
        )
        EvidenceSnapshotRepository(session).create_full(snapshot)
        EvidenceSnapshotRepository(session).transition_status(
            "snap-1",
            event="worker_start",
            new_status=SnapshotStatus.PROCESSING,
            actor="tester",
            reason="start",
        )
        profile = OCRProfileRepository(session).get_or_create(make_profile())
        PageArtifactRepository(session).get_or_create(
            make_artifact(
                artifact_id="pa-1",
                version_id="doc-1",
                page_image=IMAGE_SHA,
                page_input=IMAGE_SHA,
                status=PageArtifactStatus.SUCCEEDED,
            )
        )
        page = OcrPageRepository(session).create(
            make_ocr_page(
                page_id="op-1",
                artifact_id="pa-1",
                profile_sha=profile.profile_sha256,
                page_input=IMAGE_SHA,
                raw_text=RAW_TEXT,
            )
        )
        return {
            "ocr_page_id": page.ocr_page_id,
            "raw_text": page.raw_text,
            "raw_text_sha256": page.raw_text_sha256,
        }


def _material(
    *,
    seeded: dict[str, str],
    media_kind: str = "pdf",
    extraction_route: str = ExtractionRoute.NATIVE_PDF_TEXT.value,
    has_native_text: bool = True,
    native_text_char_count: int = 64,
    has_page_image: bool = True,
    image_bytes: bytes | None = IMAGE_BYTES,
    complex_layout: bool = False,
    ocr_confidence: float | None = None,
) -> SelectiveVisionObservationPageMaterial:
    return SelectiveVisionObservationPageMaterial(
        page_artifact_id="pa-1",
        source_ref="pa-1",
        page_ordinal=1,
        page_image_sha256=IMAGE_SHA,
        media_kind=media_kind,
        extraction_route=extraction_route,
        page_artifact_status=PageArtifactStatus.SUCCEEDED.value,
        has_page_image=has_page_image,
        has_native_text=has_native_text,
        native_text_char_count=native_text_char_count,
        complex_layout_not_represented_by_native_text=complex_layout,
        ocr_confidence=ocr_confidence,
        ocr_page_id=seeded["ocr_page_id"],
        image_bytes=image_bytes,
    )


def _run(coro):
    return asyncio.run(coro)


def test_explicit_postprocess_persists_succeeded_observation(session_factory):
    seeded = _seed(session_factory)
    calls: list[tuple] = []

    async def runner(plan: SelectiveVisionPlan, inputs):
        calls.append((plan, tuple(inputs)))
        page = inputs[0]
        return SelectiveVisionReviewOutcome(
            plan=plan,
            observations=(
                SelectiveVisionObservation(
                    source_refs=(page.source_ref,),
                    page_ordinals=(page.page_ordinal,),
                    reasons=(VISION_REASON_SCAN_OR_IMAGE_ONLY,),
                    text=f"source_ref={page.source_ref}\nscan page visible",
                    model="mock-vlm",
                    finish_reason="stop",
                    usage={"prompt_tokens": 11, "api_key": "secret"},
                ),
            ),
        )

    service = SelectiveVisionObservationService(
        session_factory, review_runner=runner, default_model_id="mock-vlm"
    )
    result = _run(
        service.run_postprocess(
            [
                _material(
                    seeded=seeded,
                    media_kind="image",
                    extraction_route=ExtractionRoute.VISION_OCR.value,
                    has_native_text=False,
                    native_text_char_count=0,
                )
            ]
        )
    )
    assert isinstance(result, SelectiveVisionObservationBatchResult)
    assert calls, "显式后处理必须调用注入的 review_runner"
    assert len(result.observations) == 1
    assert result.observations[0].status == SelectiveVisionObservationStatus.SUCCEEDED
    assert "source_ref=pa-1" in (result.observations[0].observation_text or "")
    assert "api_key" not in result.observations[0].usage
    assert result.created_observation_ids
    assert result.closed_error is None

    with session_factory() as session:
        listed = SelectiveVisionObservationRepository(session).list_by_page_artifact("pa-1")
        assert len(listed) == 1
        ocr = OcrPageRepository(session).get(seeded["ocr_page_id"])
        assert ocr.raw_text == seeded["raw_text"]
        assert ocr.raw_text_sha256 == seeded["raw_text_sha256"]


def test_native_text_skip_does_not_call_model_or_write_rows(session_factory):
    seeded = _seed(session_factory)

    async def runner(plan, inputs):  # pragma: no cover - must not run
        raise AssertionError("原生文字充分时不得调用视觉模型")

    service = SelectiveVisionObservationService(
        session_factory, review_runner=runner, default_model_id="mock-vlm"
    )
    result = _run(
        service.run_postprocess(
            [
                _material(
                    seeded=seeded,
                    media_kind="pdf",
                    extraction_route=ExtractionRoute.NATIVE_PDF_TEXT.value,
                    has_native_text=True,
                    native_text_char_count=64,
                    image_bytes=IMAGE_BYTES,
                )
            ]
        )
    )
    assert not result.plan.eligible
    assert result.observations == ()
    assert result.closed == ()
    assert result.created_observation_ids == ()
    assert any(item.skip_reason == SKIP_NATIVE_TEXT_PRIMARY for item in result.skipped)

    with session_factory() as session:
        listed = SelectiveVisionObservationRepository(session).list_by_page_artifact("pa-1")
        assert listed == []
        ocr = OcrPageRepository(session).get(seeded["ocr_page_id"])
        assert ocr.raw_text == seeded["raw_text"]
        assert ocr.raw_text_sha256 == seeded["raw_text_sha256"]


def test_fail_closed_persists_closed_only_and_leaves_ocr_unchanged(session_factory):
    seeded = _seed(session_factory)

    async def runner(plan: SelectiveVisionPlan, inputs):
        return SelectiveVisionReviewOutcome(
            plan=plan,
            closed_error=SelectiveVisionClosedError(
                "provider closed",
                failure_kind="remote_error",
                disabled=True,
            ),
        )

    service = SelectiveVisionObservationService(
        session_factory, review_runner=runner, default_model_id="mock-vlm"
    )
    result = _run(
        service.run_postprocess(
            [
                _material(
                    seeded=seeded,
                    media_kind="image",
                    extraction_route=ExtractionRoute.VISION_OCR.value,
                    has_native_text=False,
                    native_text_char_count=0,
                )
            ]
        )
    )
    assert result.closed_error is not None
    assert result.closed_error.failure_kind == "remote_error"
    assert result.observations == ()
    assert len(result.closed) == 1
    closed = result.closed[0]
    assert closed.status == SelectiveVisionObservationStatus.CLOSED
    assert closed.observation_text is None
    assert closed.failure_kind == "remote_error"
    assert closed.usage == {}

    with session_factory() as session:
        listed = SelectiveVisionObservationRepository(session).list_by_page_artifact("pa-1")
        assert len(listed) == 1
        assert listed[0].status == SelectiveVisionObservationStatus.CLOSED
        ocr = OcrPageRepository(session).get(seeded["ocr_page_id"])
        assert ocr.raw_text == seeded["raw_text"] == RAW_TEXT
        assert ocr.raw_text_sha256 == seeded["raw_text_sha256"]


def test_missing_image_bytes_fail_closed_without_model_body(session_factory):
    seeded = _seed(session_factory)
    called = {"n": 0}

    async def runner(plan, inputs):  # pragma: no cover - missing image short-circuits
        called["n"] += 1
        raise AssertionError("缺图时不得进入 review_runner")

    service = SelectiveVisionObservationService(
        session_factory, review_runner=runner, default_model_id="mock-vlm"
    )
    result = _run(
        service.run_postprocess(
            [
                _material(
                    seeded=seeded,
                    media_kind="image",
                    extraction_route=ExtractionRoute.VISION_OCR.value,
                    has_native_text=False,
                    native_text_char_count=0,
                    image_bytes=None,
                )
            ]
        )
    )
    assert called["n"] == 0
    assert result.closed_error is not None
    assert result.closed_error.failure_kind == "missing_page_inputs"
    assert result.observations == ()
    assert len(result.closed) == 1
    assert result.closed[0].observation_text is None

    with session_factory() as session:
        ocr = OcrPageRepository(session).get(seeded["ocr_page_id"])
        assert ocr.raw_text == seeded["raw_text"]
