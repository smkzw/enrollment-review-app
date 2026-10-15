"""选择性视觉观察侧车仓储：追加写、成功身份幂等、来源闭包。

Aligned to worker_02 surface:
  app.domain.contracts.selective_vision_observation
  app.storage.selective_vision_observation_repository
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.domain.contracts.enums import (
    PageArtifactStatus,
    SnapshotMemberOrigin,
    SnapshotStatus,
)
from app.domain.contracts.selective_vision_observation import (
    SELECTIVE_VISION_PROMPT_VERSION,
    SelectiveVisionObservationRecord,
    SelectiveVisionObservationStatus,
    build_observation_identity_sha256,
    build_prompt_sha256,
    build_risk_reasons_sha256,
)
from app.storage.evidence_repositories import (
    BlobRepository,
    EvidenceSnapshotRepository,
    SourceDocumentRepository,
)
from app.storage.ocr_models import OCRPageRecord
from app.storage.ocr_repositories import (
    OcrPageRepository,
    OCRProfileRepository,
    PageArtifactRepository,
)
from app.storage.repositories import InvalidReferenceError, persist_fixture
from app.storage.selective_vision_observation_models import SelectiveVisionObservationORM
from app.storage.selective_vision_observation_repository import (
    SelectiveVisionObservationConflictError,
    SelectiveVisionObservationRepository,
    SelectiveVisionObservationSourceError,
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

FIXED_UTC = datetime(2026, 8, 31, 12, 0, 0, tzinfo=UTC)
_IMAGE_SHA = "b" * 64
_PROMPT_SHA = build_prompt_sha256(
    prompt_version=SELECTIVE_VISION_PROMPT_VERSION,
    system_prompt="sys",
    user_prompt="user",
)
_REASONS = ["scan_or_image_only"]
_REASONS_SHA = build_risk_reasons_sha256(_REASONS)


def _identity(*, page_artifact_id: str = "pa-1", model_id: str = "test-vlm") -> str:
    return build_observation_identity_sha256(
        page_artifact_id=page_artifact_id,
        page_image_sha256=_IMAGE_SHA,
        plan_version=SELECTIVE_VISION_PROMPT_VERSION,
        model_id=model_id,
        prompt_sha256=_PROMPT_SHA,
        risk_reasons_sha256=_REASONS_SHA,
    )


def _seed_stack(session, fixture) -> dict[str, str]:
    project_id = fixture.project.project_id
    subject_id = fixture.subject.subject_id
    episode_id = fixture.review_episode.review_episode_id
    scope = (project_id, subject_id, episode_id)
    blob = make_blob(b"pdf-bytes-svo")
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
            version_id="doc-1",
            page_image=_IMAGE_SHA,
            page_input=_IMAGE_SHA,
            status=PageArtifactStatus.SUCCEEDED,
        )
    )
    page = OcrPageRepository(session).create(
        make_ocr_page(
            page_id="op-1",
            artifact_id="pa-1",
            profile_sha=profile.profile_sha256,
            page_input=_IMAGE_SHA,
            raw_text="GLUCOSE 5.6 mmol/L",
        )
    )
    session.flush()
    return {
        "ocr_page_id": page.ocr_page_id,
        "raw_text_sha256": page.raw_text_sha256,
        "raw_text": page.raw_text,
    }


def _observation(
    *,
    observation_id: str,
    status: SelectiveVisionObservationStatus,
    seeded: dict[str, str],
    observation_text: str | None = "source_ref=pa-1\nvisible table",
    failure_kind: str | None = None,
    finish_reason: str | None = "stop",
    usage: dict | None = None,
    model_id: str = "test-vlm",
    source_ref: str = "pa-1",
    page_ordinal: int = 1,
    with_ocr: bool = True,
) -> SelectiveVisionObservationRecord:
    if status == SelectiveVisionObservationStatus.SUCCEEDED:
        text = observation_text
        fail = None
        finish = finish_reason
        usage_value = usage if usage is not None else {"prompt_tokens": 3}
    else:
        text = None
        fail = failure_kind or "remote_error"
        finish = None
        usage_value = {}
    return SelectiveVisionObservationRecord(
        observation_id=observation_id,
        page_artifact_id="pa-1",
        source_document_version_id="doc-1",
        source_ref=source_ref,
        page_ordinal=page_ordinal,
        page_image_sha256=_IMAGE_SHA,
        ocr_page_id=seeded["ocr_page_id"] if with_ocr else None,
        ocr_raw_text_sha256=seeded["raw_text_sha256"] if with_ocr else None,
        plan_version=SELECTIVE_VISION_PROMPT_VERSION,
        risk_reasons=list(_REASONS),
        risk_reasons_sha256=_REASONS_SHA,
        model_id=model_id,
        prompt_version=SELECTIVE_VISION_PROMPT_VERSION,
        prompt_sha256=_PROMPT_SHA,
        status=status,
        observation_text=text,
        finish_reason=finish,
        usage=usage_value,
        failure_kind=fail,
        observation_identity_sha256=_identity(model_id=model_id),
        created_at=FIXED_UTC,
    )


@pytest.fixture
def seeded_session(session_factory):
    with session_factory() as session:
        fixture = FIXTURES[0]
        persist_fixture(session, fixture)
        seeded = _seed_stack(session, fixture)
        session.commit()
        yield session, seeded
        session.rollback()


def test_get_or_create_succeeded_appends_and_replays(seeded_session):
    session, seeded = seeded_session
    repo = SelectiveVisionObservationRepository(session)
    first, created = repo.get_or_create_succeeded(
        _observation(
            observation_id="svo-1",
            status=SelectiveVisionObservationStatus.SUCCEEDED,
            seeded=seeded,
        )
    )
    assert created is True
    assert first.observation_id == "svo-1"
    assert "source_ref=pa-1" in (first.observation_text or "")
    replay = repo.get("svo-1")
    assert replay.observation_identity_sha256 == first.observation_identity_sha256
    assert replay.page_image_sha256 == _IMAGE_SHA


def test_get_or_create_succeeded_is_idempotent_on_same_identity(seeded_session):
    session, seeded = seeded_session
    repo = SelectiveVisionObservationRepository(session)
    first, created = repo.get_or_create_succeeded(
        _observation(
            observation_id="svo-a",
            status=SelectiveVisionObservationStatus.SUCCEEDED,
            seeded=seeded,
        )
    )
    assert created is True
    second, created_again = repo.get_or_create_succeeded(
        _observation(
            observation_id="svo-b",
            status=SelectiveVisionObservationStatus.SUCCEEDED,
            seeded=seeded,
        )
    )
    assert created_again is False
    assert second.observation_id == first.observation_id
    rows = session.execute(select(SelectiveVisionObservationORM)).scalars().all()
    assert len(rows) == 1


def test_get_or_create_succeeded_rejects_identity_conflict(seeded_session):
    session, seeded = seeded_session
    repo = SelectiveVisionObservationRepository(session)
    repo.get_or_create_succeeded(
        _observation(
            observation_id="svo-c1",
            status=SelectiveVisionObservationStatus.SUCCEEDED,
            seeded=seeded,
            observation_text="source_ref=pa-1\nfirst body",
        )
    )
    with pytest.raises(SelectiveVisionObservationConflictError, match="不一致"):
        repo.get_or_create_succeeded(
            _observation(
                observation_id="svo-c2",
                status=SelectiveVisionObservationStatus.SUCCEEDED,
                seeded=seeded,
                observation_text="source_ref=pa-1\nconflict body",
            )
        )


def test_append_closed_allows_multiple_and_forbids_pseudo_text(seeded_session):
    session, seeded = seeded_session
    repo = SelectiveVisionObservationRepository(session)
    first = repo.append_closed(
        _observation(
            observation_id="svo-closed-1",
            status=SelectiveVisionObservationStatus.CLOSED,
            seeded=seeded,
            failure_kind="remote_error",
        )
    )
    second = repo.append_closed(
        _observation(
            observation_id="svo-closed-2",
            status=SelectiveVisionObservationStatus.CLOSED,
            seeded=seeded,
            failure_kind="source_fidelity",
        )
    )
    assert first.observation_text is None
    assert second.observation_text is None
    listed = repo.list_by_page_artifact("pa-1")
    assert {item.observation_id for item in listed} == {
        "svo-closed-1",
        "svo-closed-2",
    }
    with pytest.raises(Exception, match="伪输出|observation_text|失败关闭"):
        SelectiveVisionObservationRecord(
            observation_id="svo-closed-bad",
            page_artifact_id="pa-1",
            source_document_version_id="doc-1",
            source_ref="pa-1",
            page_ordinal=1,
            page_image_sha256=_IMAGE_SHA,
            ocr_page_id=seeded["ocr_page_id"],
            ocr_raw_text_sha256=seeded["raw_text_sha256"],
            plan_version=SELECTIVE_VISION_PROMPT_VERSION,
            risk_reasons=list(_REASONS),
            risk_reasons_sha256=_REASONS_SHA,
            model_id="test-vlm",
            prompt_version=SELECTIVE_VISION_PROMPT_VERSION,
            prompt_sha256=_PROMPT_SHA,
            status=SelectiveVisionObservationStatus.CLOSED,
            observation_text="source_ref=pa-1\nfake model text",
            finish_reason=None,
            usage={},
            failure_kind="remote_error",
            observation_identity_sha256=_identity(),
            created_at=FIXED_UTC,
        )


def test_source_closure_rejects_missing_artifact(seeded_session):
    session, seeded = seeded_session
    repo = SelectiveVisionObservationRepository(session)
    ghost = _observation(
        observation_id="svo-missing-pa",
        status=SelectiveVisionObservationStatus.SUCCEEDED,
        seeded=seeded,
    ).model_copy(update={"page_artifact_id": "missing-pa"})
    # identity hash still computed against pa-1 in helper; rebuild for missing id path
    ghost = ghost.model_copy(
        update={
            "observation_identity_sha256": build_observation_identity_sha256(
                page_artifact_id="missing-pa",
                page_image_sha256=_IMAGE_SHA,
                plan_version=SELECTIVE_VISION_PROMPT_VERSION,
                model_id="test-vlm",
                prompt_sha256=_PROMPT_SHA,
                risk_reasons_sha256=_REASONS_SHA,
            )
        }
    )
    with pytest.raises(InvalidReferenceError, match="PageArtifact"):
        repo.get_or_create_succeeded(ghost)


def test_source_closure_rejects_ocr_raw_hash_mismatch(seeded_session):
    session, seeded = seeded_session
    repo = SelectiveVisionObservationRepository(session)
    bad = _observation(
        observation_id="svo-ocr-mismatch",
        status=SelectiveVisionObservationStatus.SUCCEEDED,
        seeded=seeded,
    ).model_copy(update={"ocr_raw_text_sha256": "c" * 64})
    with pytest.raises(SelectiveVisionObservationSourceError, match="ocr_raw_text_sha256"):
        repo.get_or_create_succeeded(bad)


def test_source_closure_rejects_page_ordinal_drift(seeded_session):
    session, seeded = seeded_session
    repo = SelectiveVisionObservationRepository(session)
    bad = _observation(
        observation_id="svo-ordinal",
        status=SelectiveVisionObservationStatus.SUCCEEDED,
        seeded=seeded,
        page_ordinal=2,
    )
    with pytest.raises(SelectiveVisionObservationSourceError, match="page_ordinal"):
        repo.get_or_create_succeeded(bad)


def test_append_and_get_do_not_mutate_ocr_raw_text(seeded_session):
    session, seeded = seeded_session
    before = session.get(OCRPageRecord, seeded["ocr_page_id"])
    assert before is not None
    before_text = before.raw_text
    before_sha = before.raw_text_sha256
    repo = SelectiveVisionObservationRepository(session)
    repo.get_or_create_succeeded(
        _observation(
            observation_id="svo-ocr-safe",
            status=SelectiveVisionObservationStatus.SUCCEEDED,
            seeded=seeded,
        )
    )
    repo.append_closed(
        _observation(
            observation_id="svo-ocr-safe-closed",
            status=SelectiveVisionObservationStatus.CLOSED,
            seeded=seeded,
            failure_kind="config_error",
        )
    )
    after = session.get(OCRPageRecord, seeded["ocr_page_id"])
    assert after is not None
    assert after.raw_text == before_text == seeded["raw_text"]
    assert after.raw_text_sha256 == before_sha == seeded["raw_text_sha256"]
