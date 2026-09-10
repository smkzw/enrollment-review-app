"""Phase 4 OCR 持久化仓储确定性测试（Slice 4.3，worker_01）。

以临时库 ``Base.metadata.create_all`` 建表（不依赖迁移，模型即权威），播种 Phase 3
fixture 与候选快照基座，然后证明：

- OCRProfile/原始工件内容寻址去重与身份冲突拒绝；
- PageArtifact 页级去重、同身份冲突与失败页语义；
- OCRPage 追加写不可变行：同一缓存键至多一条成功缓存项（部分唯一索引强制）、
  失败/取消/处理中可多条共存、失败→重试成功产生两条不可变行且失败行原样回放、
  第二成功不能覆盖/污染第一条、缓存命中/扫描全量校验与镜像漂移拒绝（缓存投毒反例）；
- OCRRun/OCRAttempt 追加写：attempt_number 自动递增、晚到尝试保留审计；
- PageWorkLease：条件领取/续租/释放/单调代次/晚到结果拒绝（含并发反例）；
  ``commit_guard`` 原子提交门禁（与结果写入同事务）拒绝过期代次；
- EvidenceProcessingRevision：不可变冻结、页清单三方交叉校验、不可激活、
  同一快照多修订共存、重复主键 ID 拒绝、活动指针零接触。

每个用例构造对象时用确定性 ID 与固定 UTC 时间，结果只由领域逻辑决定。
"""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.domain.contracts.enums import (
    ExtractionRoute,
    OcrAttemptStatus,
    OcrFailureCategory,
    OCRPageStatus,
    OcrRunStatus,
    PageArtifactStatus,
    ProcessingRevisionStatus,
    SnapshotMemberOrigin,
    SnapshotStatus,
    UploadMode,
)
from app.domain.contracts.evidence_ingestion import (
    EvidenceSnapshot,
    EvidenceSnapshotMember,
    SourceBlob,
    SourceDocumentVersion,
)
from app.domain.contracts.evidence_processing import (
    EvidenceProcessingRevision,
    EvidenceProcessingRevisionPage,
    OCRAttempt,
    OCRRun,
)
from app.domain.contracts.ocr import (
    OCRPage,
    OCRProfile,
    PageArtifact,
    PageQualityMetrics,
    RawOcrRequestArtifact,
    RawOcrResponseArtifact,
)
from app.domain.publication import (
    evidence_processing_manifest_hash,
    evidence_snapshot_collection_hash,
)
from app.evidence.fingerprint import build_ocr_cache_key, build_profile_fingerprint
from app.storage import ocr_repositories as orr
from app.storage.codecs import (
    PersistedContractInvalid,
    encode_contract,
    to_utc_naive,
    utc_now,
)
from app.storage.evidence_repositories import (
    BlobRepository,
    EvidenceSnapshotRepository,
    SourceDocumentRepository,
)
from app.storage.ocr_models import (
    EvidenceProcessingRevisionPageRecord,
    EvidenceProcessingRevisionRecord,
    OCRPageRecord,
    OCRProfileRecord,
    PageArtifactRecord,
    PageWorkLeaseRecord,
)
from app.storage.repositories import (
    DuplicateRecordError,
    InvalidReferenceError,
    ScopeViolationError,
    persist_fixture,
)
from tests.v2.storage.test_repositories_roundtrip import FIXTURES

FIXED_UTC = datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC)
_SHA = "0" * 64
_TRANSFORM = "t/v1"
_LAYOUT = "layout-v1"


@pytest.fixture
def ocr_engine(tmp_path, monkeypatch):
    monkeypatch.setenv("ENROLLMENT_V2_DATA_DIR", str(tmp_path / "data_v2"))
    from app.storage.config import resolve_data_paths
    from app.storage.db import Base, build_engine

    paths = resolve_data_paths()
    paths.ensure_directories()
    engine = build_engine(paths.db_path)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def seeded(ocr_engine):
    from app.storage.db import build_session_factory

    factory = build_session_factory(ocr_engine)
    with factory() as session:
        fixture = FIXTURES[0]
        persist_fixture(session, fixture)
        session.commit()
        yield session, fixture
        session.rollback()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def make_blob(
    content: bytes, media_type: str = "application/pdf", storage_ref: str | None = None
) -> SourceBlob:
    digest = sha(content)
    return SourceBlob(
        source_blob_id=digest,
        sha256=digest,
        byte_size=len(content),
        media_type=media_type,
        storage_ref=storage_ref or f"blobs/{digest}",
        created_at=FIXED_UTC,
    )


def make_version(
    *,
    version_id: str,
    logical_id: str,
    blob_sha: str,
    scope: tuple[str, str, str],
    page_count: int = 2,
) -> SourceDocumentVersion:
    project_id, subject_id, episode_id = scope
    return SourceDocumentVersion(
        source_document_version_id=version_id,
        logical_document_id=logical_id,
        source_blob_sha256=blob_sha,
        file_name="report.pdf",
        media_type="application/pdf",
        page_count=page_count,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        version_number=1,
        created_at=FIXED_UTC,
        created_by="tester",
    )


def make_snapshot(
    *, snapshot_id: str, scope: tuple[str, str, str], members: list[tuple[str, str, SnapshotMemberOrigin]]
) -> EvidenceSnapshot:
    project_id, subject_id, episode_id = scope
    member_models = [
        EvidenceSnapshotMember(
            member_id=f"{snapshot_id}-{logical}",
            snapshot_id=snapshot_id,
            logical_document_id=logical,
            source_document_version_id=version_id,
            origin=origin,
        )
        for logical, version_id, origin in members
    ]
    collection = evidence_snapshot_collection_hash(
        members=[(m.logical_document_id, m.source_document_version_id) for m in member_models]
    )
    return EvidenceSnapshot(
        evidence_snapshot_id=snapshot_id,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        members=member_models,
        collection_sha256=collection,
        status=SnapshotStatus.STAGED,
        created_at=FIXED_UTC,
        created_by="tester",
    )


def make_profile(profile_id: str = "profile-1", model_id: str = "GLM-OCR-bf16") -> OCRProfile:
    profile_sha = build_profile_fingerprint(
        extraction_route="vision_ocr",
        provider="omlx",
        model_id=model_id,
        model_revision="unknown",
        prompt_sha256=None,
        parser_version="v1",
        render_params_sha256=None,
        request_params_sha256=None,
        layout_parser_version=_LAYOUT,
        coordinate_transform_version=_TRANSFORM,
    )
    return OCRProfile(
        ocr_profile_id=profile_id,
        profile_sha256=profile_sha,
        extraction_route=ExtractionRoute.VISION_OCR,
        provider="omlx",
        model_id=model_id,
        model_revision="unknown",
        parser_version="v1",
        layout_parser_version=_LAYOUT,
        coordinate_transform_version=_TRANSFORM,
        created_at=FIXED_UTC,
    )


def make_artifact(
    *,
    artifact_id: str = "pa-1",
    version_id: str = "doc-1",
    page_number: int = 1,
    page_input: str | None = None,
    page_image: str | None = None,
    source_sha: str | None = None,
    status: PageArtifactStatus = PageArtifactStatus.SUCCEEDED,
    failure_reason: str | None = None,
    renderer_version: str = "renderer-1",
    decoder_version: str = "decoder-1",
    transform_version: str = _TRANSFORM,
    native_text_sha256: str | None = None,
    native_coordinates_sha256: str | None = None,
) -> PageArtifact:
    """合成页产物：页图字节哈希默认等于渲染输入哈希（测试等价），
    与 ``make_ocr_page`` 的 page_input 语义一致（OCRPage.page_input == 页图哈希）。"""
    page_input_value = page_input or ("b" * 64)
    return PageArtifact(
        page_artifact_id=artifact_id,
        source_document_version_id=version_id,
        page_number=page_number,
        original_frame=None,
        source_sha256=source_sha or _SHA,
        page_input_sha256=page_input_value,
        page_image_sha256=page_image or page_input_value,
        native_text_sha256=native_text_sha256,
        native_coordinates_sha256=native_coordinates_sha256,
        page_width=595.0,
        page_height=842.0,
        rotation=0,
        renderer_version=renderer_version,
        decoder_version=decoder_version,
        derivative_sha256="d" * 64,
        coordinate_transform_version=transform_version,
        status=status,
        failure_reason=failure_reason,
    )


def make_failed_artifact(
    *,
    artifact_id: str = "pa-f1",
    version_id: str = "doc-1",
    page_number: int = 1,
    failure_reason: str = "页面解码失败",
) -> PageArtifact:
    """失败页产物：无真实页输入哈希、几何与页图（全部为 None，不用伪值）。"""
    return PageArtifact(
        page_artifact_id=artifact_id,
        source_document_version_id=version_id,
        page_number=page_number,
        original_frame=None,
        source_sha256=_SHA,
        page_input_sha256=None,
        page_image_sha256=None,
        native_text_sha256=None,
        native_coordinates_sha256=None,
        page_width=None,
        page_height=None,
        rotation=None,
        renderer_version=None,
        decoder_version=None,
        derivative_sha256="d" * 64,
        coordinate_transform_version=_TRANSFORM,
        status=PageArtifactStatus.FAILED,
        failure_reason=failure_reason,
    )


def make_ocr_page(
    *,
    page_id: str = "op-1",
    artifact_id: str = "pa-1",
    page_number: int = 1,
    profile_sha: str | None = None,
    page_input: str | None = None,
    source_sha: str | None = None,
    cache_key: str | None = None,
    status: OCRPageStatus = OCRPageStatus.SUCCEEDED,
    raw_text: str = "GLUCOSE 5.6 mmol/L",
    failure_reason: str | None = None,
    started_at=FIXED_UTC,
    completed_at: datetime | None = None,
) -> OCRPage:
    profile_sha = profile_sha or build_profile_fingerprint(
        extraction_route="vision_ocr",
        provider="omlx",
        model_id="GLM-OCR-bf16",
        model_revision="unknown",
        prompt_sha256=None,
        parser_version="v1",
        render_params_sha256=None,
        request_params_sha256=None,
        layout_parser_version=_LAYOUT,
        coordinate_transform_version=_TRANSFORM,
    )
    page_input = page_input or ("b" * 64)
    source_sha = source_sha or _SHA
    if cache_key is None:
        cache_key = build_ocr_cache_key(
            page_artifact_id=artifact_id,
            source_sha256=source_sha,
            page_number=page_number,
            ocr_profile_sha256=profile_sha,
            page_input_sha256=page_input,
            layout_parser_version=_LAYOUT,
            coordinate_transform_version=_TRANSFORM,
        )
    if completed_at is None and status == OCRPageStatus.SUCCEEDED:
        completed_at = FIXED_UTC
    return OCRPage(
        ocr_page_id=page_id,
        page_artifact_id=artifact_id,
        source_sha256=source_sha,
        page_number=page_number,
        page_input_sha256=page_input,
        ocr_profile_sha256=profile_sha,
        cache_key=cache_key,
        layout_parser_version=_LAYOUT,
        coordinate_transform_version=_TRANSFORM,
        raw_text=raw_text,
        raw_text_sha256=sha(raw_text.encode("utf-8")),
        normalized_text=raw_text,
        quality=PageQualityMetrics(char_count=len(raw_text), word_count=2),
        status=status,
        failure_reason=failure_reason,
        started_at=started_at,
        completed_at=completed_at,
    )


def make_run(*, run_id: str = "run-1", profile_sha: str | None = None) -> OCRRun:
    profile_sha = profile_sha or make_profile().profile_sha256
    return OCRRun(
        ocr_run_id=run_id,
        source_document_version_id="doc-1",
        ocr_profile_id="profile-1",
        ocr_profile_sha256=profile_sha,
        job_id=None,
        status=OcrRunStatus.RUNNING,
        page_total=1,
        page_succeeded=0,
        page_failed=0,
        started_at=FIXED_UTC,
        created_at=FIXED_UTC,
    )


def make_attempt(
    *,
    attempt_id: str = "at-1",
    run_id: str = "run-1",
    page_id: str = "op-1",
    cache_key: str = _SHA,
    status: OcrAttemptStatus = OcrAttemptStatus.SUCCEEDED,
    failure_category: OcrFailureCategory | None = None,
    rejection_reason: str | None = None,
    generation: int = 1,
    owner: str = "worker-A",
    retry_of: str | None = None,
) -> OCRAttempt:
    return OCRAttempt(
        attempt_id=attempt_id,
        ocr_run_id=run_id,
        ocr_page_id=page_id,
        cache_key=cache_key,
        attempt_number=1,
        status=status,
        failure_category=failure_category,
        rejection_reason=rejection_reason,
        started_at=FIXED_UTC,
        completed_at=FIXED_UTC,
        raw_request_artifact_id=None,
        raw_response_artifact_id=None,
        work_lease_owner=owner,
        work_lease_generation=generation,
        omlx_lease_owner=None,
        retry_of_attempt_id=retry_of,
        created_at=FIXED_UTC,
    )


def _seed_document(session, fixture) -> tuple[str, str, str]:
    """只播种 blob + 资料版本 doc-1（页产物测试的作用域基座）。"""
    project_id, subject_id, episode_id = (
        fixture.project.project_id,
        fixture.subject.subject_id,
        fixture.review_episode.review_episode_id,
    )
    scope = (project_id, subject_id, episode_id)
    blob = make_blob(b"pdf-bytes")
    BlobRepository(session).get_or_create_by_sha256(blob)
    version = make_version(
        version_id="doc-1", logical_id="log-1", blob_sha=blob.sha256, scope=scope
    )
    SourceDocumentRepository(session).create_version(version)
    session.flush()
    return scope


def _seed_stack(session, fixture) -> dict[str, Any]:
    """播种 blob/资料版本/候选快照/Profile/页产物/OCR 页，返回身份键。"""
    project_id, subject_id, episode_id = (
        fixture.project.project_id,
        fixture.subject.subject_id,
        fixture.review_episode.review_episode_id,
    )
    scope = (project_id, subject_id, episode_id)
    blob = make_blob(b"pdf-bytes")
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
    profile = orr.OCRProfileRepository(session).get_or_create(make_profile())
    orr.PageArtifactRepository(session).get_or_create(make_artifact(version_id="doc-1"))
    page = orr.OcrPageRepository(session).create(
        make_ocr_page(page_id="op-1", artifact_id="pa-1", profile_sha=profile.profile_sha256)
    )
    session.flush()
    return {
        "project_id": project_id,
        "subject_id": subject_id,
        "episode_id": episode_id,
        "profile_sha": profile.profile_sha256,
        "cache_key": page.cache_key,
    }


def _tamper(session, record_cls, filter_attr: str, filter_value, attr: str, value) -> None:
    """直接改规范化列模拟漂移；expire_all 让后续读取重新加载。"""
    session.execute(
        update(record_cls)
        .where(getattr(record_cls, filter_attr) == filter_value)
        .values(**{attr: value})
    )
    session.expire_all()


# ---------------------------------------------------------------------------
# OCRProfileRepository
# ---------------------------------------------------------------------------


def test_profile_get_or_create_dedup(seeded):
    session, _fixture = seeded
    repo = orr.OCRProfileRepository(session)
    first = repo.get_or_create(make_profile())
    second = repo.get_or_create(make_profile())
    assert first.ocr_profile_id == second.ocr_profile_id
    assert len(session.execute(select(OCRProfileRecord)).scalars().all()) == 1


def test_profile_same_fingerprint_different_fields_rejected(seeded):
    session, _fixture = seeded
    repo = orr.OCRProfileRepository(session)
    repo.get_or_create(make_profile())
    other = make_profile(profile_id="profile-2")
    other = other.model_copy(update={"model_id": "OTHER-MODEL"})
    with pytest.raises(orr.OcrIdentityError, match="身份字段不一致"):
        repo.get_or_create(other)


def test_profile_missing_get_rejected(seeded):
    session, _fixture = seeded
    with pytest.raises(InvalidReferenceError):
        orr.OCRProfileRepository(session).get("nope")


# ---------------------------------------------------------------------------
# 原始请求/响应工件
# ---------------------------------------------------------------------------


def test_raw_request_artifact_dedup_and_conflict(seeded):
    session, _fixture = seeded
    repo = orr.RawOcrRequestArtifactRepository(session)
    artifact = RawOcrRequestArtifact(
        raw_request_artifact_id="req-1",
        sha256="b" * 64,
        storage_ref="ocr-requests/" + "b" * 64,
        created_at=FIXED_UTC,
    )
    first = repo.get_or_create(artifact)
    assert first.raw_request_artifact_id == "req-1"
    conflict = artifact.model_copy(update={"storage_ref": "ocr-requests/other"})
    with pytest.raises(orr.OcrIdentityError, match="存储引用不一致"):
        repo.get_or_create(conflict)


def test_raw_request_artifact_rejects_absolute_path():
    with pytest.raises(ValidationError, match="绝对路径"):
        RawOcrRequestArtifact(
            raw_request_artifact_id="req-1",
            sha256="b" * 64,
            storage_ref="/Users/x/secret/req.bin",
            created_at=FIXED_UTC,
        )


def test_raw_response_artifact_dedup_and_conflict(seeded):
    session, _fixture = seeded
    repo = orr.RawOcrResponseArtifactRepository(session)
    artifact = RawOcrResponseArtifact(
        raw_response_artifact_id="resp-1",
        sha256="f" * 64,
        storage_ref="ocr-responses/" + "f" * 64,
        provider="omlx",
        model_id="GLM-OCR-bf16",
        model_revision="unknown",
        created_at=FIXED_UTC,
    )
    repo.get_or_create(artifact)
    conflict = artifact.model_copy(update={"model_id": "OTHER"})
    with pytest.raises(orr.OcrIdentityError, match="provider 身份不一致"):
        repo.get_or_create(conflict)


# ---------------------------------------------------------------------------
# PageArtifactRepository
# ---------------------------------------------------------------------------


def test_page_artifact_dedup_by_doc_page_input(seeded):
    session, _fixture = seeded
    _seed_document(session, _fixture)
    repo = orr.PageArtifactRepository(session)
    first = repo.get_or_create(make_artifact(version_id="doc-1"))
    second = repo.get_or_create(make_artifact(version_id="doc-1"))
    assert first.page_artifact_id == second.page_artifact_id
    assert len(session.execute(select(PageArtifactRecord)).scalars().all()) == 1


def test_page_artifact_processing_versions_create_distinct_artifacts(seeded):
    session, _fixture = seeded
    _seed_document(session, _fixture)
    repo = orr.PageArtifactRepository(session)
    first = repo.get_or_create(
        make_artifact(artifact_id="pa-v1", version_id="doc-1", renderer_version="renderer-1")
    )
    second = repo.get_or_create(
        make_artifact(artifact_id="pa-v2", version_id="doc-1", renderer_version="renderer-2")
    )
    third = repo.get_or_create(
        make_artifact(artifact_id="pa-v3", version_id="doc-1", decoder_version="decoder-2")
    )
    fourth = repo.get_or_create(
        make_artifact(artifact_id="pa-v4", version_id="doc-1", transform_version="transform-2")
    )
    assert {first.page_artifact_id, second.page_artifact_id, third.page_artifact_id, fourth.page_artifact_id} == {
        "pa-v1", "pa-v2", "pa-v3", "pa-v4"
    }


def test_page_artifact_failed_requires_reason():
    with pytest.raises(ValidationError, match="失败原因"):
        make_artifact(status=PageArtifactStatus.FAILED)


def test_page_artifact_failed_persist_all_unknown_fields_none(seeded):
    """失败页产物：几何/输入/页图全部为 None 可持久化并原样回读。"""
    session, _fixture = seeded
    _seed_document(session, _fixture)
    repo = orr.PageArtifactRepository(session)
    failed = make_failed_artifact(artifact_id="pa-f1", version_id="doc-1")
    assert failed.page_input_sha256 is None and failed.page_width is None
    persisted = repo.get_or_create(failed)
    got = repo.get("pa-f1")
    assert got.page_input_sha256 is None
    assert got.page_width is None and got.page_height is None and got.rotation is None
    assert got.page_image_sha256 is None
    assert got.status == PageArtifactStatus.FAILED
    assert got.failure_reason == "页面解码失败"
    assert persisted.page_artifact_id == "pa-f1"


def test_page_artifact_failed_same_id_different_content_rejected(seeded):
    """同 ID 不同内容的失败页被拒绝（确定性 ID 由 worker_02 负责，仓储仍校验内容）。"""
    session, _fixture = seeded
    _seed_document(session, _fixture)
    repo = orr.PageArtifactRepository(session)
    repo.get_or_create(make_failed_artifact(artifact_id="pa-f1", version_id="doc-1"))
    different = make_failed_artifact(
        artifact_id="pa-f1", version_id="doc-1", failure_reason="另一种解码失败"
    )
    with pytest.raises(orr.PageArtifactIdentityConflictError, match="身份不一致"):
        repo.get_or_create(different)


def test_page_artifact_distinct_failures_coexist_and_replay(seeded):
    """同一页的不同失败原因使用不同确定性 ID，均追加保存且可独立回放。"""
    session, _fixture = seeded
    _seed_document(session, _fixture)
    repo = orr.PageArtifactRepository(session)
    first = repo.get_or_create(
        make_failed_artifact(artifact_id="pa-f1", version_id="doc-1")
    )
    second = repo.get_or_create(
        make_failed_artifact(
            artifact_id="pa-f2",
            version_id="doc-1",
            failure_reason="页面结构无法解析",
        )
    )
    assert first.failure_reason == "页面解码失败"
    assert second.failure_reason == "页面结构无法解析"
    assert repo.get("pa-f1") == first
    assert repo.get("pa-f2") == second


def test_page_artifact_list_ordered(seeded):
    session, _fixture = seeded
    _seed_document(session, _fixture)
    repo = orr.PageArtifactRepository(session)
    repo.get_or_create(make_artifact(artifact_id="pa-1", version_id="doc-1", page_number=1))
    repo.get_or_create(make_artifact(artifact_id="pa-2", version_id="doc-1", page_number=2))
    listed = repo.list_by_source_document_version("doc-1")
    assert [a.page_number for a in listed] == [1, 2]


def test_page_artifact_drift_rejected_on_read(seeded):
    session, _fixture = seeded
    _seed_document(session, _fixture)
    repo = orr.PageArtifactRepository(session)
    repo.get_or_create(make_artifact(version_id="doc-1"))
    _tamper(session, PageArtifactRecord, "page_artifact_id", "pa-1", "page_number", 99)
    with pytest.raises(PersistedContractInvalid, match="不一致"):
        repo.get("pa-1")


# ---------------------------------------------------------------------------
# OcrPageRepository（追加写不可变行 + 单成功缓存不变量）
# ---------------------------------------------------------------------------


def test_ocr_page_append_and_cache_hit(seeded):
    session, _fixture = seeded
    keys = _seed_stack(session, fixture=_fixture)
    repo = orr.OcrPageRepository(session)
    cached = repo.get_successful_by_cache_key(keys["cache_key"])
    assert cached is not None and cached.status == OCRPageStatus.SUCCEEDED
    assert cached.ocr_page_id == "op-1"
    # 追加写语义：种子只产生一条不可变行
    rows = repo.list_by_cache_key(keys["cache_key"])
    assert len(rows) == 1 and rows[0].ocr_page_id == "op-1"


def test_ocr_page_second_success_cannot_poison_first(seeded):
    session, _fixture = seeded
    keys = _seed_stack(session, fixture=_fixture)
    repo = orr.OcrPageRepository(session)
    # 第二个成功（新 ocr_page_id、同缓存键、不同原文）→ 拒绝，绝不覆盖/污染
    poisoned = make_ocr_page(
        page_id="op-poison",
        artifact_id="pa-1",
        profile_sha=keys["profile_sha"],
        raw_text="TAMPERED DIFFERENT RESULT",
    )
    with pytest.raises(DuplicateRecordError, match="已存在不可变成功缓存项"):
        repo.create(poisoned)
    cached = repo.get_successful_by_cache_key(keys["cache_key"])
    assert cached is not None and cached.raw_text == "GLUCOSE 5.6 mmol/L"


def test_ocr_page_failed_then_retry_success_two_immutable_rows(seeded):
    """失败 → 重试成功：产生两条不可变行，失败行原样回放，成功行成为缓存命中。"""
    session, _fixture = seeded
    keys = _seed_stack(session, fixture=_fixture)
    repo = orr.OcrPageRepository(session)
    # 独立页图输入 → 独立缓存键（另一个识别计算）
    page_input = "e" * 64
    failed = make_ocr_page(
        page_id="op-f1",
        artifact_id="pa-1",
        page_input=page_input,
        profile_sha=keys["profile_sha"],
        status=OCRPageStatus.FAILED,
        failure_reason="provider timeout",
        started_at=FIXED_UTC,
        completed_at=FIXED_UTC,
    )
    repo.create(failed)
    # 失败结果不会命中成功缓存
    assert repo.get_successful_by_cache_key(failed.cache_key) is None
    # 重试成功：追加第二条不可变行（同缓存键）
    retried = make_ocr_page(
        page_id="op-f2",
        artifact_id="pa-1",
        page_input=page_input,
        profile_sha=keys["profile_sha"],
        status=OCRPageStatus.SUCCEEDED,
    )
    done = repo.create(retried)
    assert done.status == OCRPageStatus.SUCCEEDED
    rows = repo.list_by_cache_key(failed.cache_key)
    assert len(rows) == 2
    failed_replayed = next(r for r in rows if r.ocr_page_id == "op-f1")
    assert failed_replayed.status == OCRPageStatus.FAILED
    assert failed_replayed.failure_reason == "provider timeout"
    assert failed_replayed.raw_text == "GLUCOSE 5.6 mmol/L"
    winner = repo.get_successful_by_cache_key(failed.cache_key)
    assert winner is not None and winner.ocr_page_id == "op-f2"


def test_ocr_page_multiple_non_success_rows_coexist(seeded):
    """同一缓存键允许多条非成功行共存；成功行追加后三者互不覆盖。"""
    session, _fixture = seeded
    keys = _seed_stack(session, fixture=_fixture)
    repo = orr.OcrPageRepository(session)
    page_input = "e" * 64
    failed_1 = make_ocr_page(
        page_id="op-f1",
        artifact_id="pa-1",
        page_input=page_input,
        profile_sha=keys["profile_sha"],
        status=OCRPageStatus.FAILED,
        failure_reason="timeout",
        started_at=FIXED_UTC,
        completed_at=FIXED_UTC,
    )
    repo.create(failed_1)
    failed_2 = make_ocr_page(
        page_id="op-f2",
        artifact_id="pa-1",
        page_input=page_input,
        profile_sha=keys["profile_sha"],
        status=OCRPageStatus.FAILED,
        failure_reason="network",
        started_at=FIXED_UTC,
        completed_at=FIXED_UTC,
    )
    repo.create(failed_2)
    rows = repo.list_by_cache_key(failed_1.cache_key)
    assert len(rows) == 2 and {r.ocr_page_id for r in rows} == {"op-f1", "op-f2"}
    ok = make_ocr_page(
        page_id="op-f3",
        artifact_id="pa-1",
        page_input=page_input,
        profile_sha=keys["profile_sha"],
        status=OCRPageStatus.SUCCEEDED,
    )
    repo.create(ok)
    winner = repo.get_successful_by_cache_key(failed_1.cache_key)
    assert winner is not None and winner.ocr_page_id == "op-f3"
    rows = repo.list_by_cache_key(failed_1.cache_key)
    assert len(rows) == 3
    by_id = {r.ocr_page_id: r for r in rows}
    assert by_id["op-f1"].failure_reason == "timeout"
    assert by_id["op-f2"].failure_reason == "network"
    assert by_id["op-f3"].status == OCRPageStatus.SUCCEEDED


def test_ocr_page_partial_unique_index_enforced_at_db(seeded):
    """绕过仓储预检直插第二条成功行：部分唯一索引在存储层拒绝。"""
    session, _fixture = seeded
    keys = _seed_stack(session, fixture=_fixture)
    session.commit()  # 种子先落盘，后续 rollback 不吞掉基座
    dup = make_ocr_page(
        page_id="op-db-dup",
        artifact_id="pa-1",
        profile_sha=keys["profile_sha"],
    )
    _raw_append(session, dup)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
    # 同缓存键失败行 + 成功行可共存（部分索引只约束 success 行）
    page_input = "e" * 64
    failed = make_ocr_page(
        page_id="op-f1",
        artifact_id="pa-1",
        page_input=page_input,
        profile_sha=keys["profile_sha"],
        status=OCRPageStatus.FAILED,
        failure_reason="timeout",
        started_at=FIXED_UTC,
        completed_at=FIXED_UTC,
    )
    orr.OcrPageRepository(session).create(failed)
    orr.OcrPageRepository(session).create(
        make_ocr_page(
            page_id="op-f2",
            artifact_id="pa-1",
            page_input=page_input,
            profile_sha=keys["profile_sha"],
            status=OCRPageStatus.SUCCEEDED,
        )
    )
    session.flush()


def _raw_append(session, page: OCRPage) -> None:
    """绕过仓储预检，按 ORM 形状直接追加一条 OCRPage 行（验证存储层约束）。"""
    payload_json, payload_sha256 = encode_contract(page)
    session.add(
        OCRPageRecord(
            ocr_page_id=page.ocr_page_id,
            page_artifact_id=page.page_artifact_id,
            source_sha256=page.source_sha256,
            page_number=page.page_number,
            page_input_sha256=page.page_input_sha256,
            ocr_profile_id="profile-1",
            ocr_profile_sha256=page.ocr_profile_sha256,
            cache_key=page.cache_key,
            layout_parser_version=page.layout_parser_version,
            coordinate_transform_version=page.coordinate_transform_version,
            raw_text=page.raw_text,
            raw_text_sha256=page.raw_text_sha256,
            normalized_text=page.normalized_text,
            layout_sidecar_sha256=page.layout_sidecar_sha256,
            quality_json=json.dumps(
                page.quality.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            risk_items_json="[]",
            status=page.status.value,
            failure_reason=page.failure_reason,
            started_at=to_utc_naive(page.started_at),
            completed_at=to_utc_naive(page.completed_at),
            created_at=utc_now(),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
        )
    )


def test_ocr_page_cache_key_identity_drift_rejected(seeded):
    session, _fixture = seeded
    keys = _seed_stack(session, fixture=_fixture)
    _tamper(session, OCRPageRecord, "ocr_page_id", "op-1", "page_number", 77)
    with pytest.raises(PersistedContractInvalid, match="不一致"):
        orr.OcrPageRepository(session).get("op-1")
    with pytest.raises(PersistedContractInvalid, match="不一致"):
        orr.OcrPageRepository(session).get_successful_by_cache_key(keys["cache_key"])


def test_ocr_page_quality_mirror_drift_rejected(seeded):
    session, _fixture = seeded
    _seed_stack(session, fixture=_fixture)
    _tamper(session, OCRPageRecord, "ocr_page_id", "op-1", "quality_json", '{"char_count": 0, "word_count": 0}')
    with pytest.raises(PersistedContractInvalid, match="quality"):
        orr.OcrPageRepository(session).get("op-1")


def test_ocr_page_drift_in_non_success_row_surfaced_on_cache_scan(seeded):
    """损坏的非成功行在缓存扫描/命中路径上必须被暴露，不能被静默隐藏。"""
    session, _fixture = seeded
    keys = _seed_stack(session, fixture=_fixture)
    repo = orr.OcrPageRepository(session)
    page_input = "e" * 64
    failed = make_ocr_page(
        page_id="op-f1",
        artifact_id="pa-1",
        page_input=page_input,
        profile_sha=keys["profile_sha"],
        status=OCRPageStatus.FAILED,
        failure_reason="timeout",
        started_at=FIXED_UTC,
        completed_at=FIXED_UTC,
    )
    repo.create(failed)
    _tamper(session, OCRPageRecord, "ocr_page_id", "op-f1", "quality_json", '{"char_count": 0, "word_count": 0}')
    # 全量扫描（list）拒绝坏行
    with pytest.raises(PersistedContractInvalid, match="quality"):
        repo.list_by_cache_key(failed.cache_key)
    # 成功缓存命中路径同样扫描全部行 → 坏行被暴露
    with pytest.raises(PersistedContractInvalid, match="quality"):
        repo.get_successful_by_cache_key(failed.cache_key)


def test_ocr_page_profile_closure_mismatch_rejected(seeded):
    session, _fixture = seeded
    _seed_stack(session, fixture=_fixture)
    # 把页的 ocr_profile_id 指向另一个指纹不同的 Profile
    other = make_profile(profile_id="profile-2", model_id="OTHER-MODEL")
    orr.OCRProfileRepository(session).get_or_create(other)
    _tamper(session, OCRPageRecord, "ocr_page_id", "op-1", "ocr_profile_id", "profile-2")
    with pytest.raises(PersistedContractInvalid, match="指纹"):
        orr.OcrPageRepository(session).get("op-1")


# ---------------------------------------------------------------------------
# OCRRunRepository / OcrAttemptRepository
# ---------------------------------------------------------------------------


def test_ocr_run_create_and_status_transition(seeded):
    session, _fixture = seeded
    keys = _seed_stack(session, _fixture)
    repo = orr.OcrRunRepository(session)
    run = make_run(profile_sha=keys["profile_sha"])
    repo.create(run)
    with pytest.raises(DuplicateRecordError):
        repo.create(run)
    finished = repo.update_status(
        "run-1",
        status=OcrRunStatus.SUCCEEDED,
        page_succeeded=1,
        page_failed=0,
        completed_at=FIXED_UTC,
    )
    assert finished.status == OcrRunStatus.SUCCEEDED
    with pytest.raises(orr.OcrRepositoryError, match="非法"):
        repo.update_status(
            "run-1", status=OcrRunStatus.RUNNING, page_succeeded=1, page_failed=0
        )


def test_ocr_attempt_append_only_with_auto_numbering(seeded):
    session, _fixture = seeded
    keys = _seed_stack(session, _fixture)
    orr.OcrRunRepository(session).create(make_run(profile_sha=keys["profile_sha"]))
    repo = orr.OcrAttemptRepository(session)
    first = repo.append(make_attempt(attempt_id="at-1", cache_key=keys["cache_key"]))
    assert first.attempt_number == 1
    late = make_attempt(
        attempt_id="at-2",
        cache_key=keys["cache_key"],
        status=OcrAttemptStatus.REJECTED_LATE,
        rejection_reason="租约代次过期，晚到结果被拒绝",
        generation=1,
        owner="worker-A",
    )
    second = repo.append(late)
    assert second.attempt_number == 2
    assert second.retry_of_attempt_id == first.attempt_id
    history = repo.list_by_cache_key(keys["cache_key"])
    assert [(a.attempt_number, a.status.value) for a in history] == [
        (1, "succeeded"),
        (2, "rejected_late"),
    ]


def test_ocr_attempt_retry_chain_linked(seeded):
    session, _fixture = seeded
    keys = _seed_stack(session, _fixture)
    orr.OcrRunRepository(session).create(make_run(profile_sha=keys["profile_sha"]))
    repo = orr.OcrAttemptRepository(session)
    first = repo.append(make_attempt(attempt_id="at-1", cache_key=keys["cache_key"]))
    retry = repo.append(
        make_attempt(
            attempt_id="at-2",
            cache_key=keys["cache_key"],
            status=OcrAttemptStatus.FAILED,
            failure_category=OcrFailureCategory.TIMEOUT,
            retry_of=first.attempt_id,
        )
    )
    assert retry.retry_of_attempt_id == "at-1"
    assert retry.failure_category == OcrFailureCategory.TIMEOUT


def test_ocr_attempt_requires_existing_run(seeded):
    session, _fixture = seeded
    with pytest.raises(InvalidReferenceError):
        orr.OcrAttemptRepository(session).append(make_attempt())


# ---------------------------------------------------------------------------
# PageWorkLeaseRepository（代次/晚到拒绝）
# ---------------------------------------------------------------------------


def test_lease_claim_heartbeat_release_roundtrip(seeded):
    session, _fixture = seeded
    repo = orr.PageWorkLeaseRepository(session)
    key = _SHA
    lease = repo.claim(key, "worker-A", timedelta(seconds=30))
    assert lease.lease_generation == 1 and lease.lease_owner == "worker-A"
    repo.heartbeat(key, "worker-A", 1, timedelta(seconds=60))
    repo.assert_current(key, "worker-A", 1)
    repo.release(key, "worker-A", 1)
    released = repo.get(key)
    assert released is not None
    assert released.lease_owner is None and released.lease_generation == 1
    # 代次单调递增
    reclaimed = repo.claim(key, "worker-B", timedelta(seconds=30))
    assert reclaimed.lease_generation == 2


def test_lease_busy_while_held(seeded):
    session, _fixture = seeded
    repo = orr.PageWorkLeaseRepository(session)
    key = _SHA
    repo.claim(key, "worker-A", timedelta(seconds=30))
    with pytest.raises(orr.PageLeaseBusyError, match="拒绝重复领取"):
        repo.claim(key, "worker-B", timedelta(seconds=30))


def test_lease_stale_generation_result_rejected(seeded):
    session, _fixture = seeded
    repo = orr.PageWorkLeaseRepository(session)
    key = _SHA
    lease_a = repo.claim(key, "worker-A", timedelta(seconds=30))
    # worker-A 结果晚到前，租约已被释放并转给 worker-B（代次推进）
    repo.release(key, "worker-A", lease_a.lease_generation)
    repo.claim(key, "worker-B", timedelta(seconds=30))
    with pytest.raises(orr.PageLeaseLostError, match="晚到结果被拒绝"):
        repo.assert_current(key, "worker-A", lease_a.lease_generation)


def test_lease_expired_claim_reclaims_and_stale_owner_rejected(seeded):
    session, _fixture = seeded
    repo = orr.PageWorkLeaseRepository(session)
    key = _SHA
    lease = repo.claim(key, "worker-A", timedelta(seconds=1))
    # 直接让过期列过期
    _tamper(session, PageWorkLeaseRecord, "work_item_id", key, "lease_expires_at", datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC))
    reclaimed = repo.claim(key, "worker-B", timedelta(seconds=30))
    assert reclaimed.lease_generation == lease.lease_generation + 1
    with pytest.raises(orr.PageLeaseLostError, match="晚到结果被拒绝"):
        repo.assert_current(key, "worker-A", lease.lease_generation)


def test_lease_heartbeat_after_reclaim_lost(seeded):
    session, _fixture = seeded
    repo = orr.PageWorkLeaseRepository(session)
    key = _SHA
    lease = repo.claim(key, "worker-A", timedelta(seconds=30))
    repo.release(key, "worker-A", lease.lease_generation)
    repo.claim(key, "worker-B", timedelta(seconds=30))
    with pytest.raises(orr.PageLeaseLostError, match="续租失败"):
        repo.heartbeat(key, "worker-A", lease.lease_generation, timedelta(seconds=30))


def test_lease_work_identity_must_match_frozen_inputs(seeded):
    session, _fixture = seeded
    repo = orr.PageWorkLeaseRepository(session)
    with pytest.raises(orr.OcrIdentityError, match="身份不符"):
        repo.validate_work_identity(
            _SHA,
            page_artifact_id="pa-identity",
            source_sha256="a" * 64,
            page_number=1,
            ocr_profile_sha256="e" * 64,
            page_input_sha256="b" * 64,
            layout_parser_version=_LAYOUT,
            coordinate_transform_version=_TRANSFORM,
        )
    # 正确输入通过
    key = build_ocr_cache_key(
        page_artifact_id="pa-identity",
        source_sha256="a" * 64,
        page_number=1,
        ocr_profile_sha256="e" * 64,
        page_input_sha256="b" * 64,
        layout_parser_version=_LAYOUT,
        coordinate_transform_version=_TRANSFORM,
    )
    assert repo.validate_work_identity(
        key,
        page_artifact_id="pa-identity",
        source_sha256="a" * 64,
        page_number=1,
        ocr_profile_sha256="e" * 64,
        page_input_sha256="b" * 64,
        layout_parser_version=_LAYOUT,
        coordinate_transform_version=_TRANSFORM,
    ) == key


def test_lease_rejects_non_content_addressed_id(seeded):
    session, _fixture = seeded
    with pytest.raises(orr.OcrIdentityError, match="缓存唯一键"):
        orr.PageWorkLeaseRepository(session).claim("file-name.pdf", "w", timedelta(seconds=1))


def test_lease_concurrent_claim_single_winner(seeded):
    """双 worker 并发领取同一页工作项：只有一方成功，另一方收到忙错误。"""
    session, _fixture = seeded
    from app.storage.db import build_session_factory

    factory = build_session_factory(session.get_bind())
    key = _SHA

    def try_claim(owner: str):
        with factory() as own_session:
            repo = orr.PageWorkLeaseRepository(own_session)
            try:
                lease = repo.claim(key, owner, timedelta(seconds=60))
                own_session.commit()
                return ("ok", owner, lease.lease_generation)
            except orr.PageLeaseBusyError:
                own_session.rollback()
                return ("busy", owner, None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda owner: try_claim(owner), ["A", "B"]))
    outcomes = sorted(r[0] for r in results)
    assert outcomes == ["busy", "ok"]
    winner = next(r for r in results if r[0] == "ok")
    assert winner[2] == 1


# ---------------------------------------------------------------------------
# EvidenceProcessingRevisionRepository（不可变冻结 + 不可激活）
# ---------------------------------------------------------------------------


def _seed_revision_stack(session, fixture) -> dict[str, Any]:
    keys = _seed_stack(session, fixture)
    keys["entry"] = EvidenceProcessingRevisionPage(
        entry_id="e1",
        position=1,
        source_document_version_id="doc-1",
        page_number=1,
        original_frame=None,
        page_artifact_id="pa-1",
        ocr_page_id="op-1",
        status=PageArtifactStatus.SUCCEEDED,
    )
    keys["manifest_hash"] = evidence_processing_manifest_hash(
        entries=[("doc-1", 1, None, "pa-1", "op-1", PageArtifactStatus.SUCCEEDED.value)]
    )
    return keys


def make_revision(keys: dict[str, Any], **overrides) -> EvidenceProcessingRevision:
    values = {
        "evidence_processing_revision_id": "rev-1",
        "evidence_snapshot_id": "snap-1",
        "project_id": keys["project_id"],
        "subject_id": keys["subject_id"],
        "review_episode_id": keys["episode_id"],
        "manifest": [keys["entry"]],
        "manifest_sha256": keys["manifest_hash"],
        "status": "ready",
        "is_activatable": False,
        "created_at": FIXED_UTC,
        "created_by": "tester",
    }
    values.update(overrides)
    return EvidenceProcessingRevision(**values)


def test_revision_create_and_frozen_replay(seeded):
    session, fixture = seeded
    keys = _seed_revision_stack(session, fixture)
    repo = orr.EvidenceProcessingRevisionRepository(session)
    repo.create(make_revision(keys))
    got = repo.get("rev-1")
    assert got.evidence_processing_revision_id == "rev-1"
    assert len(got.manifest) == 1
    assert got.manifest[0].page_artifact_id == "pa-1"
    assert got.manifest[0].ocr_page_id == "op-1"
    assert got.is_activatable is False
    assert got.status.value == "ready"
    # 回放完整：页产物与 OCR 页身份一致
    assert got.manifest[0].source_document_version_id == "doc-1"


def test_revision_multiple_revisions_per_snapshot_coexist_and_replay(seeded):
    """同一快照允许并存多个不可变修订（校对/完整修订均派生新修订），各自回放不变。"""
    session, fixture = seeded
    keys = _seed_revision_stack(session, fixture)
    repo = orr.EvidenceProcessingRevisionRepository(session)
    rev_1 = make_revision(keys, evidence_processing_revision_id="rev-1")
    repo.create(rev_1)
    rev_2 = make_revision(keys, evidence_processing_revision_id="rev-2")
    repo.create(rev_2)
    got_1 = repo.get("rev-1")
    got_2 = repo.get("rev-2")
    assert got_1.evidence_processing_revision_id == "rev-1"
    assert got_2.evidence_processing_revision_id == "rev-2"
    assert got_1.manifest == rev_1.manifest and got_1.manifest_sha256 == rev_1.manifest_sha256
    assert got_2.manifest == rev_2.manifest and got_2.manifest_sha256 == rev_2.manifest_sha256
    listed = repo.list_by_snapshot("snap-1")
    assert [r.evidence_processing_revision_id for r in listed] == ["rev-1", "rev-2"]
    # 再次回放仍不变（不可变）
    assert repo.get("rev-1").manifest_sha256 == rev_1.manifest_sha256
    assert repo.get("rev-2").manifest_sha256 == rev_2.manifest_sha256


def test_revision_duplicate_primary_id_rejected(seeded):
    """重复主键 ID 必须失败；幂等由创建命令/Job 负责，不是存储不变量。"""
    session, fixture = seeded
    keys = _seed_revision_stack(session, fixture)
    repo = orr.EvidenceProcessingRevisionRepository(session)
    repo.create(make_revision(keys))
    with pytest.raises(DuplicateRecordError, match="已存在"):
        repo.create(make_revision(keys))


def test_revision_never_touches_active_pointer(seeded):
    """基础修订创建/读取不推断也不更新任何活动指针（候选快照状态零变化）。"""
    session, fixture = seeded
    keys = _seed_revision_stack(session, fixture)
    snapshot_repo = EvidenceSnapshotRepository(session)
    assert snapshot_repo.current_status("snap-1") == SnapshotStatus.PROCESSING
    orr.EvidenceProcessingRevisionRepository(session).create(make_revision(keys))
    session.flush()
    # 快照仍是候选状态，无激活事件、无指针列更新（仓储没有任何激活方法）
    assert snapshot_repo.current_status("snap-1") == SnapshotStatus.PROCESSING
    assert not hasattr(orr.EvidenceProcessingRevisionRepository, "activate")
    assert not hasattr(orr.EvidenceProcessingRevisionRepository, "rollback")


def test_revision_rejects_cancelled_snapshot(seeded):
    session, fixture = seeded
    keys = _seed_revision_stack(session, fixture)
    EvidenceSnapshotRepository(session).transition_status(
        "snap-1",
        event="cancel_at_safe_boundary",
        new_status=SnapshotStatus.CANCELLED,
        actor="tester",
        reason="user cancelled",
    )
    session.flush()
    with pytest.raises(orr.RevisionManifestError, match="不能冻结"):
        orr.EvidenceProcessingRevisionRepository(session).create(make_revision(keys))


def test_revision_rejects_missing_page_artifact(seeded):
    session, fixture = seeded
    keys = _seed_revision_stack(session, fixture)
    bad = make_revision(keys)
    bad = bad.model_copy(
        update={
            "manifest": [
                bad.manifest[0].model_copy(update={"page_artifact_id": "pa-ghost"})
            ]
        }
    )
    with pytest.raises(orr.RevisionManifestError, match="不存在"):
        orr.EvidenceProcessingRevisionRepository(session).create(bad)


def test_revision_rejects_artifact_identity_mismatch(seeded):
    session, fixture = seeded
    keys = _seed_revision_stack(session, fixture)
    bad = make_revision(keys)
    bad = bad.model_copy(
        update={
            "manifest": [
                bad.manifest[0].model_copy(update={"page_number": 9})
            ]
        }
    )
    with pytest.raises(orr.RevisionManifestError, match="页码与页产物不一致"):
        orr.EvidenceProcessingRevisionRepository(session).create(bad)


def test_revision_rejects_non_terminal_ocr_page(seeded):
    """清单引用尚未完成的 OCR 页时拒绝冻结（处理中页不能被冻结进修订）。"""
    session, fixture = seeded
    keys = _seed_stack(session, fixture)
    # 第 2 页：真实页产物 + 处理中（PROCESSING）OCR 页（独立缓存键）
    page2_input = "f" * 64
    orr.PageArtifactRepository(session).get_or_create(
        make_artifact(artifact_id="pa-2", version_id="doc-1", page_number=2, page_input=page2_input)
    )
    processing_page = make_ocr_page(
        page_id="op-2",
        artifact_id="pa-2",
        page_number=2,
        page_input=page2_input,
        profile_sha=keys["profile_sha"],
        status=OCRPageStatus.PROCESSING,
        started_at=FIXED_UTC,
        completed_at=None,
    )
    orr.OcrPageRepository(session).create(processing_page)
    entry2 = EvidenceProcessingRevisionPage(
        entry_id="e2",
        position=1,
        source_document_version_id="doc-1",
        page_number=2,
        page_artifact_id="pa-2",
        ocr_page_id="op-2",
        status=PageArtifactStatus.SUCCEEDED,
    )
    keys["entry"] = entry2
    keys["manifest_hash"] = evidence_processing_manifest_hash(
        entries=[
            ("doc-1", 2, None, "pa-2", "op-2", PageArtifactStatus.SUCCEEDED.value)
        ]
    )
    with pytest.raises(orr.RevisionManifestError, match="尚未完成"):
        orr.EvidenceProcessingRevisionRepository(session).create(make_revision(keys))


def test_revision_rejects_ocr_page_input_not_matching_page_image(seeded):
    """闭包必须校验 OCRPage.page_input_sha256 == PageArtifact.page_image_sha256。

    实际送入 OCR 的页图字节哈希与页产物页图哈希错配时拒绝冻结，防止缓存/清单
    引用错误页图。
    """
    session, fixture = seeded
    keys = _seed_revision_stack(session, fixture)
    # pa-1 的 page_image_sha256 = "b"*64（make_artifact 页图=输入）；
    # 构造一条 page_input 与页图哈希不一致的 OCRPage（独立缓存键）
    wrong_input = "9" * 64
    orr.OcrPageRepository(session).create(
        make_ocr_page(
            page_id="op-wrong-input",
            artifact_id="pa-1",
            page_input=wrong_input,
            profile_sha=keys["profile_sha"],
        )
    )
    bad = make_revision(keys)
    bad = bad.model_copy(
        update={
            "manifest": [
                bad.manifest[0].model_copy(update={"ocr_page_id": "op-wrong-input"})
            ],
            "manifest_sha256": evidence_processing_manifest_hash(
                entries=[
                    (
                        "doc-1",
                        1,
                        None,
                        "pa-1",
                        "op-wrong-input",
                        PageArtifactStatus.SUCCEEDED.value,
                    )
                ]
            ),
        }
    )
    with pytest.raises(orr.RevisionManifestError, match="页图字节哈希不一致"):
        orr.EvidenceProcessingRevisionRepository(session).create(bad)


def test_revision_rejects_failed_artifact_binding_ocr_page(seeded):
    """失败页产物无页图，清单不得绑定任何 OCR 结果。"""
    session, fixture = seeded
    keys = _seed_revision_stack(session, fixture)
    orr.PageArtifactRepository(session).get_or_create(
        make_failed_artifact(artifact_id="pa-f1", version_id="doc-1")
    )
    bad = make_revision(keys)
    bad = bad.model_copy(
        update={
            "manifest": [
                bad.manifest[0].model_copy(
                    update={
                        "entry_id": "e-fail",
                        "page_artifact_id": "pa-f1",
                        "ocr_page_id": "op-1",
                        "status": PageArtifactStatus.FAILED,
                        "failure_reason": "页面解码失败",
                    }
                )
            ],
            "manifest_sha256": evidence_processing_manifest_hash(
                entries=[
                    (
                        "doc-1",
                        1,
                        None,
                        "pa-f1",
                        "op-1",
                        PageArtifactStatus.FAILED.value,
                    )
                ]
            ),
        }
    )
    # 合同层已拒绝失败页携带 OCR 结果；若绕过后，仓储闭包同样拒绝
    with pytest.raises(orr.RevisionManifestError, match="不得绑定 OCR 结果"):
        orr.EvidenceProcessingRevisionRepository(session).create(bad)


def test_revision_allows_failed_page_without_ocr_entry(seeded):
    """失败页可冻结为清单条目：无 OCR 结果、无伪几何，状态与失败原因如实回放。"""
    session, fixture = seeded
    keys = _seed_revision_stack(session, fixture)
    orr.PageArtifactRepository(session).get_or_create(
        make_failed_artifact(artifact_id="pa-f1", version_id="doc-1")
    )
    entry = EvidenceProcessingRevisionPage(
        entry_id="e-fail",
        position=1,
        source_document_version_id="doc-1",
        page_number=1,
        original_frame=None,
        page_artifact_id="pa-f1",
        ocr_page_id=None,
        status=PageArtifactStatus.FAILED,
        failure_reason="页面解码失败",
    )
    manifest_hash = evidence_processing_manifest_hash(
        entries=[
            ("doc-1", 1, None, "pa-f1", None, PageArtifactStatus.FAILED.value)
        ]
    )
    revision = make_revision(keys, manifest=[entry], manifest_sha256=manifest_hash)
    created = orr.EvidenceProcessingRevisionRepository(session).create(revision)
    assert created.manifest[0].status == PageArtifactStatus.FAILED
    assert created.manifest[0].ocr_page_id is None


def test_revision_manifest_row_drift_rejected_on_read(seeded):
    session, fixture = seeded
    keys = _seed_revision_stack(session, fixture)
    repo = orr.EvidenceProcessingRevisionRepository(session)
    repo.create(make_revision(keys))
    _tamper(session, EvidenceProcessingRevisionPageRecord, "revision_id", "rev-1", "page_number", 55)
    with pytest.raises(PersistedContractInvalid, match="不一致"):
        repo.get("rev-1")


def test_revision_manifest_hash_column_drift_rejected_on_read(seeded):
    session, fixture = seeded
    keys = _seed_revision_stack(session, fixture)
    repo = orr.EvidenceProcessingRevisionRepository(session)
    repo.create(make_revision(keys))
    _tamper(session, EvidenceProcessingRevisionRecord, "evidence_processing_revision_id", "rev-1", "manifest_sha256", "f" * 64)
    with pytest.raises(PersistedContractInvalid, match="不一致"):
        repo.get("rev-1")


def test_revision_list_by_snapshot_and_episode_verified(seeded):
    session, fixture = seeded
    keys = _seed_revision_stack(session, fixture)
    repo = orr.EvidenceProcessingRevisionRepository(session)
    repo.create(make_revision(keys))
    by_snapshot = repo.list_by_snapshot("snap-1")
    assert [r.evidence_processing_revision_id for r in by_snapshot] == ["rev-1"]
    by_episode = repo.list_by_episode(keys["episode_id"])
    assert [r.evidence_processing_revision_id for r in by_episode] == ["rev-1"]
    # 列表读取同样拒绝漂移
    _tamper(session, EvidenceProcessingRevisionRecord, "evidence_processing_revision_id", "rev-1", "status", "active")
    with pytest.raises(PersistedContractInvalid):
        repo.list_by_snapshot("snap-1")


def test_revision_scope_mismatch_with_snapshot_rejected(seeded):
    session, fixture = seeded
    keys = _seed_revision_stack(session, fixture)
    other = FIXTURES[0]
    bad = make_revision(keys, subject_id="subject-other", project_id=other.project.project_id)
    with pytest.raises(ScopeViolationError, match="作用域"):
        orr.EvidenceProcessingRevisionRepository(session).create(bad)


# ---------------------------------------------------------------------------
# 端到端反例：晚到结果不能成为成功缓存/清单成员
# ---------------------------------------------------------------------------


def test_late_attempt_cannot_enter_cache_or_manifest(seeded):
    """worker-A 的晚到结果：代次已推进，原子门禁拒绝且不能进缓存/修订，只作审计。"""
    session, fixture = seeded
    keys = _seed_stack(session, fixture)
    session.commit()  # 基座落盘，后续 rollback 不吞掉
    # 独立页图输入 → 独立缓存键（与种子的成功行无关）
    fresh_input = "e" * 64
    fresh_key = build_ocr_cache_key(
        page_artifact_id="pa-2",
        source_sha256=_SHA,
        page_number=1,
        ocr_profile_sha256=keys["profile_sha"],
        page_input_sha256=fresh_input,
        layout_parser_version=_LAYOUT,
        coordinate_transform_version=_TRANSFORM,
    )
    orr.PageArtifactRepository(session).get_or_create(
        make_artifact(
            artifact_id="pa-2", version_id="doc-1", page_number=1, page_input=fresh_input
        )
    )
    orr.OcrRunRepository(session).create(make_run(profile_sha=keys["profile_sha"]))
    session.commit()  # run/pa-2 落盘，门禁失败事务回滚不吞掉审计基座
    lease_repo = orr.PageWorkLeaseRepository(session)
    page_repo = orr.OcrPageRepository(session)

    # worker-A 领取并持有租约（代次 1）
    lease_a = lease_repo.claim(fresh_key, "worker-A", timedelta(seconds=30))
    # 任务中断：租约过期并被恢复器接管给 worker-B（代次 2）
    _tamper(
        session,
        PageWorkLeaseRecord,
        "work_item_id",
        fresh_key,
        "lease_expires_at",
        datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC),
    )
    lease_b = lease_repo.claim(fresh_key, "worker-B", timedelta(seconds=30))
    assert lease_b.lease_generation == lease_a.lease_generation + 1
    session.commit()  # 代次推进落盘，晚到门禁失败事务回滚不吞掉接管结果

    # worker-A 晚到提交：原子门禁拒绝（同一事务内不得产生成功缓存行）
    with pytest.raises(orr.PageLeaseLostError, match="提交门禁未通过"):
        lease_repo.commit_guard(
            fresh_key,
            "worker-A",
            lease_a.lease_generation,
            page_artifact_id="pa-2",
            source_sha256=_SHA,
            page_number=1,
            ocr_profile_sha256=keys["profile_sha"],
            page_input_sha256=fresh_input,
            layout_parser_version=_LAYOUT,
            coordinate_transform_version=_TRANSFORM,
        )
    # 门禁失败后事务回滚；晚到尝试在独立审计事务追加
    session.rollback()
    attempt_repo = orr.OcrAttemptRepository(session)
    late = attempt_repo.append(
        make_attempt(
            attempt_id="at-late",
            cache_key=fresh_key,
            status=OcrAttemptStatus.REJECTED_LATE,
            rejection_reason="租约代次不匹配，晚到结果被拒绝",
            generation=lease_a.lease_generation,
            owner="worker-A",
        )
    )
    assert late.status == OcrAttemptStatus.REJECTED_LATE
    session.flush()

    # worker-B 在同一事务内通过门禁并提交成功结果
    guard = lease_repo.commit_guard(
        fresh_key,
        "worker-B",
        lease_b.lease_generation,
        page_artifact_id="pa-2",
        source_sha256=_SHA,
        page_number=1,
        ocr_profile_sha256=keys["profile_sha"],
        page_input_sha256=fresh_input,
        layout_parser_version=_LAYOUT,
        coordinate_transform_version=_TRANSFORM,
    )
    assert guard.lease_generation == lease_b.lease_generation
    page_b = page_repo.create(
        make_ocr_page(
            page_id="op-b",
            artifact_id="pa-2",
            page_input=fresh_input,
            profile_sha=keys["profile_sha"],
        )
    )
    assert page_b.status == OCRPageStatus.SUCCEEDED
    session.flush()

    # 晚到尝试不得进入成功缓存：缓存键仍指向 worker-B 的成功结果
    winner_page = page_repo.get_successful_by_cache_key(fresh_key)
    assert winner_page is not None and winner_page.ocr_page_id == "op-b"

    # 修订只能引用 worker-B 的成功页（晚到结果不能成为清单成员）
    entry = EvidenceProcessingRevisionPage(
        entry_id="e1",
        position=1,
        source_document_version_id="doc-1",
        page_number=1,
        original_frame=None,
        page_artifact_id="pa-2",
        ocr_page_id="op-b",
        status=PageArtifactStatus.SUCCEEDED,
    )
    manifest_hash = evidence_processing_manifest_hash(
        entries=[("doc-1", 1, None, "pa-2", "op-b", PageArtifactStatus.SUCCEEDED.value)]
    )
    revision = EvidenceProcessingRevision(
        evidence_processing_revision_id="rev-late",
        evidence_snapshot_id="snap-1",
        project_id=keys["project_id"],
        subject_id=keys["subject_id"],
        review_episode_id=keys["episode_id"],
        manifest=[entry],
        manifest_sha256=manifest_hash,
        status=ProcessingRevisionStatus.READY,
        is_activatable=False,
        created_at=FIXED_UTC,
        created_by="tester",
    )
    orr.EvidenceProcessingRevisionRepository(session).create(revision)
    got = orr.EvidenceProcessingRevisionRepository(session).get("rev-late")
    assert got.manifest[0].ocr_page_id == "op-b"

    # 尝试历史完整（含晚到审计）
    history = attempt_repo.list_by_cache_key(fresh_key)
    assert any(a.status == OcrAttemptStatus.REJECTED_LATE for a in history)


# ---------------------------------------------------------------------------
# 原子提交门禁（commit_guard）：与结果写入同事务的晚到拒绝
# ---------------------------------------------------------------------------


def _seed_fresh_page_scope(session, fixture) -> dict[str, Any]:
    """播种 doc-1/profile/pa-2（fresh_input 页产物），返回身份键。"""
    keys = _seed_stack(session, fixture)
    fresh_input = "e" * 64
    orr.PageArtifactRepository(session).get_or_create(
        make_artifact(
            artifact_id="pa-2", version_id="doc-1", page_number=1, page_input=fresh_input
        )
    )
    fresh_key = build_ocr_cache_key(
        page_artifact_id="pa-2",
        source_sha256=_SHA,
        page_number=1,
        ocr_profile_sha256=keys["profile_sha"],
        page_input_sha256=fresh_input,
        layout_parser_version=_LAYOUT,
        coordinate_transform_version=_TRANSFORM,
    )
    keys.update({"fresh_input": fresh_input, "fresh_key": fresh_key, "fresh_artifact": "pa-2"})
    return keys


def test_commit_guard_success_path_same_transaction(seeded):
    """通过门禁后，OCRPage 成功行 + OCRAttempt 在同一事务内原子写入。"""
    session, fixture = seeded
    keys = _seed_fresh_page_scope(session, fixture)
    orr.OcrRunRepository(session).create(make_run(profile_sha=keys["profile_sha"]))
    lease_repo = orr.PageWorkLeaseRepository(session)
    page_repo = orr.OcrPageRepository(session)
    attempt_repo = orr.OcrAttemptRepository(session)

    lease = lease_repo.claim(keys["fresh_key"], "worker-A", timedelta(seconds=30))
    assert lease.lease_generation == 1
    guard = lease_repo.commit_guard(
        keys["fresh_key"],
        "worker-A",
        lease.lease_generation,
        page_artifact_id=keys["fresh_artifact"],
        source_sha256=_SHA,
        page_number=1,
        ocr_profile_sha256=keys["profile_sha"],
        page_input_sha256=keys["fresh_input"],
        layout_parser_version=_LAYOUT,
        coordinate_transform_version=_TRANSFORM,
    )
    assert guard.lease_generation == 1 and guard.lease_owner == "worker-A"
    page_repo.create(
        make_ocr_page(
            page_id="op-ok",
            artifact_id=keys["fresh_artifact"],
            page_input=keys["fresh_input"],
            profile_sha=keys["profile_sha"],
        )
    )
    attempt_repo.append(
        make_attempt(attempt_id="at-ok", cache_key=keys["fresh_key"], generation=1)
    )
    session.flush()
    winner = page_repo.get_successful_by_cache_key(keys["fresh_key"])
    assert winner is not None and winner.ocr_page_id == "op-ok"
    history = attempt_repo.list_by_cache_key(keys["fresh_key"])
    assert [a.status for a in history] == [OcrAttemptStatus.SUCCEEDED]


def test_commit_guard_stale_generation_rejected_two_sessions(seeded):
    """两会话反例：过期代次无法通过 commit_guard，也无法创建成功缓存行。

    worker-A（会话 A）领取代次 1 → 租约过期被恢复器接管给 worker-B（会话 B，
    代次 2）→ worker-A 晚到提交在同一事务内被门禁拒绝且成功行回滚；晚到尝试
    写入独立审计事务。之后 worker-B 的门禁+结果同事务成功。
    """
    session, fixture = seeded
    keys = _seed_fresh_page_scope(session, fixture)
    session.commit()
    from app.storage.db import build_session_factory

    factory = build_session_factory(session.get_bind())

    # 会话 A：worker-A 领取租约（代次 1）
    with factory() as s_a:
        lease_a = orr.PageWorkLeaseRepository(s_a).claim(
            keys["fresh_key"], "worker-A", timedelta(seconds=30)
        )
        assert lease_a.lease_generation == 1
        s_a.commit()

    # 会话 B：租约过期并被恢复器接管给 worker-B（代次 2）
    with factory() as s_b:
        s_b.execute(
            update(PageWorkLeaseRecord)
            .where(PageWorkLeaseRecord.work_item_id == keys["fresh_key"])
            .values(lease_expires_at=datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC))
        )
        s_b.commit()
    with factory() as s_b2:
        lease_b = orr.PageWorkLeaseRepository(s_b2).claim(
            keys["fresh_key"], "worker-B", timedelta(seconds=30)
        )
        assert lease_b.lease_generation == 2
        s_b2.commit()

    # 会话 A'：worker-A 晚到提交——commit_guard 与结果写在同一事务内，门禁失败回滚
    with factory() as s_run:
        # 独立事务：审计尝试外键基座（运行记录）
        orr.OcrRunRepository(s_run).create(make_run(profile_sha=keys["profile_sha"]))
        s_run.commit()
    with factory() as s_late:
        with pytest.raises(orr.PageLeaseLostError, match="提交门禁未通过"):
            orr.PageWorkLeaseRepository(s_late).commit_guard(
                keys["fresh_key"],
                "worker-A",
                lease_a.lease_generation,
                page_artifact_id=keys["fresh_artifact"],
                source_sha256=_SHA,
                page_number=1,
                ocr_profile_sha256=keys["profile_sha"],
                page_input_sha256=keys["fresh_input"],
                layout_parser_version=_LAYOUT,
                coordinate_transform_version=_TRANSFORM,
            )
        # 门禁失败事务回滚：不产生任何成功缓存行
        s_late.rollback()
        # 晚到尝试写入独立审计事务（运行记录来自已提交的独立事务）
        orr.OcrAttemptRepository(s_late).append(
            make_attempt(
                attempt_id="at-late",
                cache_key=keys["fresh_key"],
                status=OcrAttemptStatus.REJECTED_LATE,
                rejection_reason="租约代次不匹配，晚到结果被拒绝",
                generation=lease_a.lease_generation,
                owner="worker-A",
            )
        )
        s_late.commit()

    # 校验：没有晚到成功行
    with factory() as s_check:
        assert (
            orr.OcrPageRepository(s_check).get_successful_by_cache_key(keys["fresh_key"])
            is None
        )

    # 会话 B'：worker-B 门禁 + 成功结果同事务提交
    with factory() as s_win:
        page_repo_b = orr.OcrPageRepository(s_win)
        guard_b = orr.PageWorkLeaseRepository(s_win).commit_guard(
            keys["fresh_key"],
            "worker-B",
            lease_b.lease_generation,
            page_artifact_id=keys["fresh_artifact"],
            source_sha256=_SHA,
            page_number=1,
            ocr_profile_sha256=keys["profile_sha"],
            page_input_sha256=keys["fresh_input"],
            layout_parser_version=_LAYOUT,
            coordinate_transform_version=_TRANSFORM,
        )
        assert guard_b.lease_generation == 2
        page_repo_b.create(
            make_ocr_page(
                page_id="op-b",
                artifact_id=keys["fresh_artifact"],
                page_input=keys["fresh_input"],
                profile_sha=keys["profile_sha"],
            )
        )
        s_win.commit()
        winner = page_repo_b.get_successful_by_cache_key(keys["fresh_key"])
        assert winner is not None and winner.ocr_page_id == "op-b"

    # 晚到尝试完整审计，未进入成功缓存
    with factory() as s_final:
        history = orr.OcrAttemptRepository(s_final).list_by_cache_key(keys["fresh_key"])
        assert [a.status for a in history] == [OcrAttemptStatus.REJECTED_LATE]
        assert (
            orr.OcrPageRepository(s_final).get_successful_by_cache_key(keys["fresh_key"])
            is not None
        )
