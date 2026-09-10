"""证据处理持久执行器确定性测试（Slice 4.3，worker_03）。

覆盖执行器编排：页工作租约 + 共享门禁固定顺序、晚到结果拒绝、渲染背压、
文件页检查点、限定重试只重跑失败页、取消在页边界生效、崩溃恢复无永久处理中、
缓存写失败不污染成功缓存、部分文件失败显式失败页、门禁满槽按可重试失败处理、
不可变基础处理修订冻结（不可激活）与 page_progress 只读事件。

所有推理均为合成函数（无 PHI）；共享门禁使用临时 SQLite 库（真实门禁代码，
不绕过）。``live_peak_probe`` 的多进程峰值见 ``test_omlx_gate.py``。
"""
from __future__ import annotations

import hashlib
import io
import json
import threading
import time
from datetime import UTC, datetime, timedelta

import fitz
import pytest
from PIL import Image
from sqlalchemy import func, select

from app.domain.contracts.enums import (
    ExtractionRoute,
    JobEventType,
    OcrAttemptStatus,
    OCRPageStatus,
    OcrRunStatus,
    PageArtifactStatus,
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
from app.domain.contracts.evidence_processing import OCRRun
from app.domain.contracts.evidence_upload import EVIDENCE_PROCESSING_JOB_TYPE
from app.domain.publication import (
    evidence_processing_manifest_hash,
    evidence_snapshot_collection_hash,
)
from app.evidence.artifacts import ArtifactStore
from app.evidence.ocr_adapter import InferenceResult, TextOnlyOcrAdapter
from app.evidence.segmentation import SegmentationConfig
from app.services.evidence_processing_executor import (
    EVIDENCE_PROCESSING_MAX_ATTEMPTS,
    EvidenceProcessingExecutorConfig,
    _process_visual_page,
    create_evidence_processing_executor,
    recover_evidence_ocr_runs,
)
from app.services.job_service import JobService, StepSpec
from app.services.omlx_gate import OmlxGateClient, OmlxInferenceResponseError
from app.storage.codecs import utc_now
from app.storage.evidence_locator_models import (
    EvidenceLocatorArtifactRecord,
    OCRRiskScanRecord,
)
from app.storage.evidence_repositories import (
    BlobRepository,
    EvidenceSnapshotRepository,
    SourceDocumentRepository,
)
from app.storage.ocr_models import (
    EvidenceProcessingRevisionRecord,
    OCRAttemptRecord,
    OCRPageRecord,
    OCRProfileRecord,
    PageWorkLeaseRecord,
)
from app.storage.ocr_repositories import (
    EvidenceProcessingRevisionRepository,
    OcrAttemptRepository,
    OcrPageRepository,
    OCRProfileRepository,
    OcrRunRepository,
    PageArtifactRepository,
    PageWorkLeaseRepository,
    RawOcrResponseArtifactRepository,
)
from app.storage.repositories import persist_fixture
from app.workflow.errors import ProcessDeath
from app.workflow.jobstore import JobStore
from app.workflow.recovery import run_startup_recovery
from app.workflow.runner import JobRunner
from tests.v2.storage.test_repositories_roundtrip import FIXTURES

FIXED_UTC = datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC)
STEP_ID = "evidence_processing"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def png_bytes(text_pixel: int = 200, size: int = 24) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), (text_pixel, 120, 120)).save(buf, format="PNG")
    return buf.getvalue()


def tiff_bytes(frame_count: int = 2, *, base_pixel: int = 100) -> bytes:
    buf = io.BytesIO()
    frames = [
        Image.new("RGB", (16, 16), (base_pixel + i * 40, 0, 0))
        for i in range(frame_count)
    ]
    frames[0].save(buf, format="TIFF", save_all=True, append_images=frames[1:])
    return buf.getvalue()


def text_bytes(text: str = "受试者化验单\nGLUCOSE 5.6 mmol/L\n") -> bytes:
    return text.encode("utf-8")


def native_pdf_bytes() -> bytes:
    document = fitz.open()
    for page_text in ("Subject report GLUCOSE 5.6 mmol/L", "Visit date 2026-08-21"):
        page = document.new_page()  # type: ignore[attr-defined] - fitz stub
        page.insert_text((72, 72), page_text)
    payload = document.tobytes(garbage=True, deflate=True, no_new_id=True)
    document.close()
    return payload


class FakeInference:
    """合成推理：记录调用页序，可注入逐页失败/崩溃/阻塞。"""

    def __init__(
        self,
        text: str = "GLUCOSE 5.6 mmol/L\n",
        *,
        fail_pages: set[int] | None = None,
        crash_after_inference: bool = False,
        block_event: threading.Event | None = None,
        wait_event: threading.Event | None = None,
    ) -> None:
        self.text = text
        self.fail_pages = set(fail_pages or [])
        self.crash_after_inference = crash_after_inference
        self.block_event = block_event
        self.wait_event = wait_event
        self.calls: list[int] = []

    def __call__(self, payload: dict, image_bytes: bytes) -> InferenceResult:
        page = int(payload["page"]["page_number"])
        self.calls.append(page)
        if self.block_event is not None:
            self.block_event.set()
            if self.wait_event is not None:
                self.wait_event.wait(timeout=30)
        if self.crash_after_inference:
            raise ProcessDeath()
        if page in self.fail_pages:
            raise RuntimeError("provider transient failure")
        raw = (
            b'{"model":"GLM-OCR-bf16","choices":[{"message":{"content":"'
            + self.text.encode("utf-8")
            + b'"}}]}'
        )
        return InferenceResult(
            raw_response=raw,
            recognized_text=self.text,
            verified_coordinates=False,
        )


class ForbiddenGate:
    """源文本路线不得触达共享外部推理门禁。"""

    def run_under_lease(self, *_args, **_kwargs):
        raise AssertionError("源文本路线不应获取 oMLX 门禁租约")


# ---------------------------------------------------------------------------
# 环境与播种
# ---------------------------------------------------------------------------


@pytest.fixture
def env(tmp_path, monkeypatch):
    """临时 V2 数据根 + create_all 引擎 + Phase 3 fixture + 临时共享门禁库。"""
    monkeypatch.setenv("ENROLLMENT_V2_DATA_DIR", str(tmp_path / "data_v2"))
    from app.storage.config import resolve_data_paths
    from app.storage.db import Base, build_engine, build_session_factory

    paths = resolve_data_paths()
    paths.ensure_directories()
    engine = build_engine(paths.db_path)
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    with factory() as session:
        fixture = FIXTURES[0]
        persist_fixture(session, fixture)
        session.commit()
        scope = (
            fixture.project.project_id,
            fixture.subject.subject_id,
            fixture.review_episode.review_episode_id,
        )
    gate = OmlxGateClient(db_path=tmp_path / "gate.sqlite3", owner="test-evidence")
    yield {
        "factory": factory,
        "paths": paths,
        "scope": scope,
        "gate": gate,
        "engine": engine,
    }
    engine.dispose()


def add_file(env, *, content: bytes, media_type: str, file_name: str, version_id: str) -> str:
    """落 blob（含磁盘字节）+ 资料版本；返回 blob sha256。"""
    digest = sha(content)
    target = env["paths"].root / "blobs" / digest
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    project_id, subject_id, episode_id = env["scope"]
    blob = SourceBlob(
        source_blob_id=digest,
        sha256=digest,
        byte_size=len(content),
        media_type=media_type,
        storage_ref=f"blobs/{digest}",
        created_at=FIXED_UTC,
    )
    version = SourceDocumentVersion(
        source_document_version_id=version_id,
        logical_document_id=f"logical-{version_id}",
        source_blob_sha256=digest,
        file_name=file_name,
        media_type=media_type,
        page_count=None,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        version_number=1,
        created_at=FIXED_UTC,
        created_by="tester",
    )
    with env["factory"]() as session, session.begin():
        BlobRepository(session).get_or_create_by_sha256(blob)
        SourceDocumentRepository(session).create_version(version)
    return digest


def make_snapshot(env, *, snapshot_id: str, members: list[tuple[str, str, SnapshotMemberOrigin]]):
    """播种一个 FULL/STAGED 候选快照（成员必须已由 add_file 建立）。"""
    project_id, subject_id, episode_id = env["scope"]
    member_models = [
        EvidenceSnapshotMember(
            member_id=f"{snapshot_id}-{version_id}",
            snapshot_id=snapshot_id,
            logical_document_id=f"logical-{version_id}",
            source_document_version_id=version_id,
            origin=origin,
        )
        for _logical, version_id, origin in members
    ]
    snapshot = EvidenceSnapshot(
        evidence_snapshot_id=snapshot_id,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        members=member_models,
        collection_sha256=evidence_snapshot_collection_hash(
            members=[(m.logical_document_id, m.source_document_version_id) for m in member_models]
        ),
        status=SnapshotStatus.STAGED,
        created_at=FIXED_UTC,
        created_by="tester",
    )
    with env["factory"]() as session, session.begin():
        EvidenceSnapshotRepository(session).create_full(snapshot)
    return snapshot


def create_job(env, snapshot_id: str, *, key: str) -> str:
    project_id, subject_id, episode_id = env["scope"]
    service = JobService(env["factory"])
    result = service.create_job(
        idempotency_key=key,
        job_type=EVIDENCE_PROCESSING_JOB_TYPE,
        payload={
            "snapshot_id": snapshot_id,
            "project_id": project_id,
            "subject_id": subject_id,
            "review_episode_id": episode_id,
            "upload_mode": "full",
        },
        steps=[
            StepSpec(
                step_id=STEP_ID,
                name=STEP_ID,
                max_attempts=EVIDENCE_PROCESSING_MAX_ATTEMPTS,
                retryable=True,
            )
        ],
    )
    return result.job_id


def build_runner(env, *, inference=None, gate=None, **cfg):
    config = EvidenceProcessingExecutorConfig(
        session_factory=env["factory"],
        data_paths=env["paths"],
        worker_id="w1",
        inference=inference or FakeInference(),
        gate=gate or env["gate"],
        **cfg,
    )
    executor = create_evidence_processing_executor(config)
    return JobRunner(env["factory"], {EVIDENCE_PROCESSING_JOB_TYPE: executor}, worker_id="w1")


def job_state(env, job_id: str) -> str:
    with env["factory"]() as session:
        return JobStore(session).job_status(job_id).state


def snapshot_state(env, snapshot_id: str) -> SnapshotStatus:
    with env["factory"]() as session:
        return EvidenceSnapshotRepository(session).current_status(snapshot_id)


def count(env, model, *where) -> int:
    with env["factory"]() as session:
        query = select(func.count()).select_from(model)
        if where:
            query = query.where(*where)
        return int(session.execute(query).scalar_one())


def succeeded_pages(env) -> int:
    return count(env, OCRPageRecord, OCRPageRecord.status == "succeeded")


def ocr_runs(env, job_id: str) -> list:
    with env["factory"]() as session:
        return OcrRunRepository(session).list_by_job(job_id)


def retry_job(env, job_id: str) -> None:
    with env["factory"]() as session, session.begin():
        JobStore(session).retry_failed(job_id)


def _expire_job_lease(env, job_id: str) -> None:
    from sqlalchemy import update

    from app.storage.models import JobRecord

    with env["factory"]() as session, session.begin():
        session.execute(
            update(JobRecord)
            .where(JobRecord.job_id == job_id)
            .values(lease_expires_at=utc_now() - timedelta(seconds=1))
        )


# ---------------------------------------------------------------------------
# 基础：TXT 统一识别页 + 视觉页经门禁
# ---------------------------------------------------------------------------


def test_txt_file_creates_cached_source_text_page_without_external_ocr(env):
    source_text = "受试者化验单\nGLUCOSE 5.6 mmol/L\n"
    add_file(
        env,
        content=text_bytes(source_text),
        media_type="text/plain",
        file_name="lab.txt",
        version_id="doc-txt",
    )
    snapshot = make_snapshot(
        env, snapshot_id="snap-txt", members=[("logical-txt", "doc-txt", SnapshotMemberOrigin.ADDED)]
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-txt")
    inference = FakeInference()
    runner = build_runner(env, inference=inference, gate=ForbiddenGate())
    assert runner.run_job(job_id) is True

    assert job_state(env, job_id) == "completed"
    assert snapshot_state(env, snapshot.evidence_snapshot_id) == SnapshotStatus.PROCESSING
    # TXT 使用确定性源文本提取：有统一成功页，但无外部运行、尝试、门禁或推理。
    assert ocr_runs(env, job_id) == []
    assert inference.calls == []
    assert succeeded_pages(env) == 1
    assert count(env, OCRAttemptRecord) == 0
    with env["factory"]() as session:
        revision = EvidenceProcessingRevisionRepository(session).get(
            session.execute(
                select(EvidenceProcessingRevisionRecord.evidence_processing_revision_id)
            ).scalar_one()
        )
        entry = revision.manifest[0]
        assert entry.ocr_page_id is not None
        page = OcrPageRepository(session).get(entry.ocr_page_id)
        artifact = PageArtifactRepository(session).get(entry.page_artifact_id)
        profile_record = session.execute(
            select(OCRProfileRecord).where(
                OCRProfileRecord.profile_sha256 == page.ocr_profile_sha256
            )
        ).scalar_one()
        profile = OCRProfileRepository(session).get(profile_record.ocr_profile_id)

    assert len(revision.manifest) == 1
    assert entry.source_document_version_id == "doc-txt"
    assert entry.status == PageArtifactStatus.SUCCEEDED
    assert page.raw_text == source_text
    assert page.raw_text_sha256 == artifact.native_text_sha256
    assert page.page_input_sha256 == artifact.page_image_sha256
    assert page.layout_sidecar_sha256 is None
    assert profile.extraction_route == ExtractionRoute.SOURCE_TEXT
    assert profile.layout_parser_version is None
    assert revision.is_activatable is False

    first_page_id = page.ocr_page_id
    first_profile_count = count(env, OCRProfileRecord)
    job_id_2 = create_job(env, snapshot.evidence_snapshot_id, key="k-txt-2")
    assert build_runner(env, inference=inference, gate=ForbiddenGate()).run_job(job_id_2) is True
    assert inference.calls == []
    assert ocr_runs(env, job_id_2) == []
    assert count(env, OCRAttemptRecord) == 0
    assert succeeded_pages(env) == 1
    assert count(env, OCRProfileRecord) == first_profile_count
    with env["factory"]() as session:
        replayed = EvidenceProcessingRevisionRepository(session).get(
            revision.evidence_processing_revision_id
        )
    assert replayed.manifest[0].ocr_page_id == first_page_id


def test_native_pdf_creates_replayable_pages_without_external_ocr(env):
    content = native_pdf_bytes()
    add_file(
        env,
        content=content,
        media_type="application/pdf",
        file_name="native-01.pdf",
        version_id="doc-native-pdf",
    )
    snapshot = make_snapshot(
        env,
        snapshot_id="snap-native-pdf",
        members=[("logical-native-pdf", "doc-native-pdf", SnapshotMemberOrigin.ADDED)],
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-native-pdf")
    inference = FakeInference()

    assert build_runner(env, inference=inference, gate=ForbiddenGate()).run_job(job_id) is True
    assert job_state(env, job_id) == "completed"
    assert inference.calls == []
    assert ocr_runs(env, job_id) == []
    assert count(env, OCRAttemptRecord) == 0
    assert count(env, OCRRiskScanRecord) == 2
    assert count(env, EvidenceLocatorArtifactRecord) > 0

    store = ArtifactStore(env["paths"])
    with env["factory"]() as session:
        revision = EvidenceProcessingRevisionRepository(session).list_by_snapshot(
            snapshot.evidence_snapshot_id
        )[0]
        entries = list(revision.manifest)
        pages = [OcrPageRepository(session).get(entry.ocr_page_id or "") for entry in entries]
        artifacts = [PageArtifactRepository(session).get(entry.page_artifact_id) for entry in entries]
        profiles = []
        for page in pages:
            profile_record = session.execute(
                select(OCRProfileRecord).where(
                    OCRProfileRecord.profile_sha256 == page.ocr_profile_sha256
                )
            ).scalar_one()
            profiles.append(OCRProfileRepository(session).get(profile_record.ocr_profile_id))
        locators = session.execute(
            select(EvidenceLocatorArtifactRecord).order_by(
                EvidenceLocatorArtifactRecord.locator_id
            )
        ).scalars().all()

    assert len(entries) == 2
    assert all(entry.ocr_page_id is not None for entry in entries)
    assert revision.is_activatable is False
    assert locators
    source_lines = [locator for locator in locators if locator.target_id.startswith("source-line:")]
    native_locators = [locator for locator in locators if locator not in source_lines]
    assert source_lines and native_locators
    assert all(locator.source_layer == "raw_ocr" for locator in source_lines)
    assert all(locator.precision == "text_range" for locator in source_lines)
    assert all(locator.authenticity == "degraded" for locator in source_lines)
    assert all(locator.source_layer == "native_text" for locator in native_locators)
    assert all(locator.precision == "bbox" for locator in native_locators)
    assert all(locator.authenticity == "authenticated" for locator in native_locators)
    assert all(locator.bbox_x0 is not None for locator in native_locators)
    for page, artifact, profile in zip(pages, artifacts, profiles):
        assert page.status == OCRPageStatus.SUCCEEDED
        assert page.page_input_sha256 == artifact.page_image_sha256
        assert artifact.native_text_sha256 is not None
        assert page.raw_text == store.read_by_sha(
            "native_text", artifact.native_text_sha256
        ).decode("utf-8")
        assert page.raw_text_sha256 == artifact.native_text_sha256
        assert artifact.native_coordinates_sha256 is not None
        assert page.layout_sidecar_sha256 == artifact.native_coordinates_sha256
        assert profile.extraction_route == ExtractionRoute.NATIVE_PDF_TEXT
        assert profile.layout_parser_version == "native_coordinates/v1"

    first_page_ids = [page.ocr_page_id for page in pages]
    first_profile_count = count(env, OCRProfileRecord)
    first_locator_count = count(env, EvidenceLocatorArtifactRecord)
    job_id_2 = create_job(env, snapshot.evidence_snapshot_id, key="k-native-pdf-2")
    assert build_runner(env, inference=inference, gate=ForbiddenGate()).run_job(job_id_2) is True
    assert inference.calls == []
    assert ocr_runs(env, job_id_2) == []
    assert count(env, OCRAttemptRecord) == 0
    assert succeeded_pages(env) == len(first_page_ids)
    assert count(env, OCRProfileRecord) == first_profile_count
    assert count(env, OCRRiskScanRecord) == 2
    assert count(env, EvidenceLocatorArtifactRecord) == first_locator_count
    with env["factory"]() as session:
        replayed = EvidenceProcessingRevisionRepository(session).get(
            revision.evidence_processing_revision_id
        )
    assert [entry.ocr_page_id for entry in replayed.manifest] == first_page_ids


def test_processing_revision_preserves_confirmed_document_order(env):
    """三栏页序必须沿用用户确认顺序，不能按资料哈希或内部标识重排。"""
    for version_id, file_name in (
        ("doc-z-first", "01-筛选病历.txt"),
        ("doc-a-second", "02-既往病历.txt"),
    ):
        add_file(
            env,
            content=text_bytes(file_name),
            media_type="text/plain",
            file_name=file_name,
            version_id=version_id,
        )
    snapshot = make_snapshot(
        env,
        snapshot_id="snap-confirmed-order",
        members=[
            ("logical-doc-z-first", "doc-z-first", SnapshotMemberOrigin.ADDED),
            ("logical-doc-a-second", "doc-a-second", SnapshotMemberOrigin.ADDED),
        ],
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-confirmed-order")
    assert build_runner(env, inference=FakeInference(), gate=ForbiddenGate()).run_job(job_id)

    with env["factory"]() as session:
        revision = EvidenceProcessingRevisionRepository(session).list_by_snapshot(
            snapshot.evidence_snapshot_id
        )[0]
    assert [entry.source_document_version_id for entry in revision.manifest] == [
        "doc-z-first",
        "doc-a-second",
    ]


def test_visual_page_ocr_through_gate_and_cache_dedup(env):
    content = png_bytes()
    add_file(
        env, content=content, media_type="image/png", file_name="photo.png", version_id="doc-img"
    )
    snapshot = make_snapshot(
        env, snapshot_id="snap-img", members=[("logical-img", "doc-img", SnapshotMemberOrigin.ADDED)]
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-img")
    inference = FakeInference(text="GLUCOSE 5.6 mmol/L")
    runner = build_runner(env, inference=inference)
    assert runner.run_job(job_id) is True

    assert job_state(env, job_id) == "completed"
    assert succeeded_pages(env) == 1
    assert inference.calls == [1]
    runs = ocr_runs(env, job_id)
    assert len(runs) == 1
    assert runs[0].status == OcrRunStatus.SUCCEEDED
    assert runs[0].page_succeeded == 1
    # 第二次运行（新任务同一快照）：缓存命中，不再推理。
    job_id2 = create_job(env, snapshot.evidence_snapshot_id, key="k-img-2")
    runner2 = build_runner(env, inference=inference)
    assert runner2.run_job(job_id2) is True
    assert inference.calls == [1]
    assert succeeded_pages(env) == 1


def test_same_content_new_version_reuses_inference_and_owns_success_page(env):
    """执行器级根因回归：同内容新资料版本复用推理结果，落地自有成功页并冻结修订。

    基线期事故链：内容键（v1）使新资料版本**借用**他版成功页 -> 冻结清单
    ``ocr_page.page_artifact_id != entry.page_artifact_id`` 被完整性门禁拒绝
    -> EXECUTOR_ERROR。仅改 v2 键又会丢失内容级复用（同内容重传重新推理）。
    二者必须并存：同内容两页只推理一次，且每个版本冻结引用**自有**成功行的
    修订，历史行不改写。
    """
    content = png_bytes()
    add_file(
        env, content=content, media_type="image/png", file_name="a.png",
        version_id="doc-reuse-v1",
    )
    add_file(
        env, content=content, media_type="image/png", file_name="b.png",
        version_id="doc-reuse-v2",
    )
    snapshot = make_snapshot(
        env,
        snapshot_id="snap-reuse",
        members=[
            ("logical-reuse-v1", "doc-reuse-v1", SnapshotMemberOrigin.ADDED),
            ("logical-reuse-v2", "doc-reuse-v2", SnapshotMemberOrigin.ADDED),
        ],
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-reuse")
    inference = FakeInference(text="GLUCOSE 5.6 mmol/L")
    # 串行处理：确保第二页 prepare 时第一页成功行已提交（并发下内容复用源
    # 尚未存在则真实推理，属于合法状态，不是本回归的目标场景）。
    assert (
        build_runner(env, inference=inference, page_processing_concurrency=1).run_job(
            job_id
        )
        is True
    )

    assert job_state(env, job_id) == "completed"
    # 同内容两页只发生一次真实推理（第二页内容级复用，不再调用模型）。
    assert inference.calls == [1]
    assert succeeded_pages(env) == 2
    with env["factory"]() as session:
        revision = EvidenceProcessingRevisionRepository(session).list_by_snapshot(
            snapshot.evidence_snapshot_id
        )[0]
        page_repo = OcrPageRepository(session)
        rows_by_version = {}
        for entry in revision.manifest:
            page = page_repo.get(entry.ocr_page_id)
            rows_by_version[entry.source_document_version_id] = page
            # 清单条目绑定本版本页产物：复用绝不产生跨产物借用。
            assert page.page_artifact_id == entry.page_artifact_id
        v1 = rows_by_version["doc-reuse-v1"]
        v2 = rows_by_version["doc-reuse-v2"]
    assert v1.ocr_page_id != v2.ocr_page_id
    assert v1.raw_text == v2.raw_text == "GLUCOSE 5.6 mmol/L"
    assert v1.cache_key != v2.cache_key


def test_dense_page_uses_multiple_gate_calls_but_one_page_attempt(env):
    content = png_bytes(size=48)
    add_file(
        env,
        content=content,
        media_type="image/png",
        file_name="dense.png",
        version_id="doc-dense",
    )
    snapshot = make_snapshot(
        env,
        snapshot_id="snap-dense",
        members=[("logical-dense", "doc-dense", SnapshotMemberOrigin.ADDED)],
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-dense")
    adapter = TextOnlyOcrAdapter(
        segmentation_config=SegmentationConfig(
            min_page_height=1,
            min_stitched_page_aspect_ratio=0,
            min_active_row_ratio=0,
            min_ink_ratio=0,
            target_segment_height=16,
            min_segment_height=10,
            max_segment_height=20,
            max_segments=8,
        )
    )
    calls: list[int] = []

    def inference(payload, _image_bytes):
        index = int(payload["segment"]["index"])
        calls.append(index)
        return InferenceResult(
            raw_response=f'{{"segment":{index}}}'.encode(),
            recognized_text=f"第{index + 1}段\n",
        )

    assert build_runner(env, inference=inference, adapter=adapter).run_job(job_id) is True
    assert calls == list(range(len(calls)))
    assert len(calls) > 1
    run = ocr_runs(env, job_id)[0]
    with env["factory"]() as session:
        attempts = OcrAttemptRepository(session).list_by_run(run.ocr_run_id)
        page = OcrPageRepository(session).get(attempts[0].ocr_page_id or "")
        response = RawOcrResponseArtifactRepository(session).get(
            attempts[0].raw_response_artifact_id or ""
        )
    assert len(attempts) == 1
    assert attempts[0].status == OcrAttemptStatus.SUCCEEDED
    assert page.raw_text == "\n".join(f"第{index + 1}段" for index in calls)
    composite = json.loads(
        ArtifactStore(env["paths"]).read_by_sha("raw_response", response.sha256)
    )
    assert composite["status"] == "succeeded"
    assert len(composite["segments"]) == len(calls)


def test_dense_page_partial_failure_records_one_failed_attempt(env):
    content = png_bytes(size=48)
    add_file(
        env,
        content=content,
        media_type="image/png",
        file_name="dense-failure.png",
        version_id="doc-dense-failure",
    )
    snapshot = make_snapshot(
        env,
        snapshot_id="snap-dense-failure",
        members=[
            (
                "logical-dense-failure",
                "doc-dense-failure",
                SnapshotMemberOrigin.ADDED,
            )
        ],
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-dense-failure")
    adapter = TextOnlyOcrAdapter(
        segmentation_config=SegmentationConfig(
            min_page_height=1,
            min_stitched_page_aspect_ratio=0,
            min_active_row_ratio=0,
            min_ink_ratio=0,
            target_segment_height=16,
            min_segment_height=10,
            max_segment_height=20,
            max_segments=8,
        )
    )
    calls: list[int] = []

    def inference(payload, _image_bytes):
        index = int(payload["segment"]["index"])
        calls.append(index)
        if index == 1:
            raise OmlxInferenceResponseError(
                "second segment failed", raw_response=b'{"truncated":true}'
            )
        return InferenceResult(
            raw_response=f'{{"segment":{index}}}'.encode(),
            recognized_text=f"第{index + 1}段",
        )

    assert build_runner(env, inference=inference, adapter=adapter).run_job(job_id) is True
    assert calls == [0, 1]
    run = ocr_runs(env, job_id)[0]
    with env["factory"]() as session:
        attempts = OcrAttemptRepository(session).list_by_run(run.ocr_run_id)
        response = RawOcrResponseArtifactRepository(session).get(
            attempts[0].raw_response_artifact_id or ""
        )
    assert len(attempts) == 1
    assert attempts[0].status == OcrAttemptStatus.FAILED
    composite = json.loads(
        ArtifactStore(env["paths"]).read_by_sha("raw_response", response.sha256)
    )
    assert composite["status"] == "failed"
    assert len(composite["completed_segments"]) == 1
    assert composite["failed_segment"]["index"] == 1


def test_two_frame_tiff_processes_both_pages_ordered(env):
    content = tiff_bytes(2)
    add_file(
        env, content=content, media_type="image/tiff", file_name="scan.tif", version_id="doc-tif"
    )
    snapshot = make_snapshot(
        env, snapshot_id="snap-tif", members=[("logical-tif", "doc-tif", SnapshotMemberOrigin.ADDED)]
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-tif")
    inference = FakeInference()
    runner = build_runner(env, inference=inference)
    assert runner.run_job(job_id) is True
    assert job_state(env, job_id) == "completed"
    assert succeeded_pages(env) == 2
    assert sorted(inference.calls) == [1, 2]
    with env["factory"]() as session:
        revision = EvidenceProcessingRevisionRepository(session).get(
            session.execute(
                select(EvidenceProcessingRevisionRecord.evidence_processing_revision_id)
            ).scalar_one()
        )
    assert [entry.page_number for entry in revision.manifest] == [1, 2]
    assert all(entry.ocr_page_id is not None for entry in revision.manifest)


# ---------------------------------------------------------------------------
# 重试 / 取消 / 崩溃恢复
# ---------------------------------------------------------------------------


def test_retry_only_reruns_failed_pages(env):
    content = tiff_bytes(2)
    add_file(
        env, content=content, media_type="image/tiff", file_name="scan.tif", version_id="doc-tif2"
    )
    snapshot = make_snapshot(
        env, snapshot_id="snap-r", members=[("logical-r", "doc-tif2", SnapshotMemberOrigin.ADDED)]
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-r")
    inference = FakeInference(fail_pages={2})
    runner = build_runner(env, inference=inference)

    assert runner.run_job(job_id) is True
    assert job_state(env, job_id) == "failed_retryable"
    assert snapshot_state(env, snapshot.evidence_snapshot_id) == SnapshotStatus.RETRYABLE_FAILURE
    # 页 1 已成功且缓存，页 2 失败。
    assert succeeded_pages(env) == 1
    assert sorted(inference.calls) == [1, 2]

    # 修复后重试：只重跑页 2（页 1 缓存命中）。
    inference.fail_pages = set()
    retry_job(env, job_id)
    runner2 = build_runner(env, inference=inference)
    assert runner2.run_job(job_id) is True
    assert job_state(env, job_id) == "completed"
    assert snapshot_state(env, snapshot.evidence_snapshot_id) == SnapshotStatus.PROCESSING
    assert sorted(inference.calls) == [1, 2, 2]
    assert succeeded_pages(env) == 2
    # 页 2 存在失败与成功两条不可变 OCRPage 行。
    with env["factory"]() as session:
        attempts = OcrAttemptRepository(session).list_by_run(ocr_runs(env, job_id)[0].ocr_run_id)
    statuses = [a.status for a in attempts]
    assert OcrAttemptStatus.SUCCEEDED in statuses
    assert OcrAttemptStatus.FAILED in statuses


def test_cancel_at_page_boundary_preserves_completed_pages(env):
    add_file(
        env,
        content=tiff_bytes(2, base_pixel=80),
        media_type="image/tiff",
        file_name="a.tif",
        version_id="doc-ca",
    )
    add_file(
        env,
        content=tiff_bytes(2, base_pixel=120),
        media_type="image/tiff",
        file_name="b.tif",
        version_id="doc-cb",
    )
    snapshot = make_snapshot(
        env,
        snapshot_id="snap-c",
        members=[
            ("logical-ca", "doc-ca", SnapshotMemberOrigin.ADDED),
            ("logical-cb", "doc-cb", SnapshotMemberOrigin.ADDED),
        ],
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-c")

    # 第一个文件第一页推理时请求取消：随后在页边界安全停止。
    block = threading.Event()
    wait = threading.Event()
    inference = FakeInference(block_event=block, wait_event=wait)

    def request_cancel_later():
        block.wait(timeout=10)
        with env["factory"]() as session, session.begin():
            JobStore(session).request_cancel(job_id)
        wait.set()

    thread = threading.Thread(target=request_cancel_later, daemon=True)
    thread.start()
    runner = build_runner(
        env,
        inference=inference,
        page_processing_concurrency=2,
    )
    assert runner.run_job(job_id) is True
    thread.join(timeout=10)
    assert job_state(env, job_id) == "cancelled"
    assert snapshot_state(env, snapshot.evidence_snapshot_id) == SnapshotStatus.CANCELLED
    # 全局并行模式保留取消到达时已在途的页面，但不再补充提交待处理页。
    assert succeeded_pages(env) == 2
    assert sorted(inference.calls) == [1, 1]
    with env["factory"]() as session:
        revision_count = int(
            session.execute(
                select(func.count()).select_from(EvidenceProcessingRevisionRecord)
            ).scalar_one()
        )
    assert revision_count == 0  # 取消不冻结处理修订
    runs = ocr_runs(env, job_id)
    assert len(runs) == 2
    assert all(run.status == OcrRunStatus.CANCELLED for run in runs)


def test_cancel_after_last_page_does_not_freeze_revision(env):
    """单页最后边界收到取消时，不得先冻结基础处理修订。"""
    add_file(env, content=png_bytes(), media_type="image/png", file_name="p.png", version_id="doc-last-cancel")
    snapshot = make_snapshot(
        env,
        snapshot_id="snap-last-cancel",
        members=[("logical-last-cancel", "doc-last-cancel", SnapshotMemberOrigin.ADDED)],
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-last-cancel")

    def cancelling_inference(payload, image_bytes):
        result = FakeInference()(payload, image_bytes)
        with env["factory"]() as session, session.begin():
            JobStore(session).request_cancel(job_id)
        return result

    assert build_runner(env, inference=cancelling_inference).run_job(job_id) is True
    assert job_state(env, job_id) == "cancelled"
    assert snapshot_state(env, snapshot.evidence_snapshot_id) == SnapshotStatus.CANCELLED
    assert succeeded_pages(env) == 1
    with env["factory"]() as session:
        revision_count = int(
            session.execute(
                select(func.count()).select_from(EvidenceProcessingRevisionRecord)
            ).scalar_one()
        )
    assert revision_count == 0
    runs = ocr_runs(env, job_id)
    assert len(runs) == 1
    # 最后一页本身已完整提交；取消阻止的是修订冻结，不回写已完成的运行历史。
    assert runs[0].status == OcrRunStatus.SUCCEEDED


def test_crash_after_claim_recovers_and_completes(env):
    content = png_bytes()
    add_file(env, content=content, media_type="image/png", file_name="p.png", version_id="doc-cr1")
    snapshot = make_snapshot(
        env, snapshot_id="snap-cr1", members=[("logical-cr1", "doc-cr1", SnapshotMemberOrigin.ADDED)]
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-cr1")

    # 模拟：认领并启动步骤后进程死亡（执行器从未运行），租约随进程死亡过期。
    with env["factory"]() as session, session.begin():
        store = JobStore(session, now=utc_now)
        lease = store.claim_job(job_id, "w1")
        assert lease is not None
        store.start_step(lease, STEP_ID)
    _expire_job_lease(env, job_id)
    assert job_state(env, job_id) == "running"

    report = run_startup_recovery(env["factory"])
    assert job_id in report.recovered_jobs
    assert job_state(env, job_id) == "queued"
    # 重启后无永久处理中任务。
    assert not [j for j in report.recovered_jobs if job_state(env, j) == "running"]
    recover_evidence_ocr_runs(
        env["factory"],
        recovered_job_ids=report.recovered_jobs,
        cancelled_job_ids=report.cancelled_jobs,
        failed_final_job_ids=report.failed_final_jobs,
    )
    assert all(run.status != OcrRunStatus.RUNNING for run in ocr_runs(env, job_id))

    runner = build_runner(env, inference=FakeInference())
    assert runner.run_job(job_id) is True
    assert job_state(env, job_id) == "completed"
    assert succeeded_pages(env) == 1


def test_crash_after_inference_before_commit_recovers_no_stale_success(env):
    content = png_bytes()
    add_file(env, content=content, media_type="image/png", file_name="p.png", version_id="doc-cr2")
    snapshot = make_snapshot(
        env, snapshot_id="snap-cr2", members=[("logical-cr2", "doc-cr2", SnapshotMemberOrigin.ADDED)]
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-cr2")

    inference = FakeInference(crash_after_inference=True)
    runner = build_runner(env, inference=inference)
    with pytest.raises(ProcessDeath):
        runner.run_job(job_id)
    # 推理已完成但未提交：无成功缓存项、无处理中页残留成为成功。
    assert succeeded_pages(env) == 0
    assert job_state(env, job_id) == "running"
    # 真实进程死亡不得执行任何清理：页工作租约仍被原 worker 持有（未释放），
    # 必须由 TTL 过期 + 恢复器接管，而不是“优雅 finally 释放”。
    with env["factory"]() as session:
        row = session.execute(select(PageWorkLeaseRecord)).scalars().one()
        assert row.lease_owner == "w1"
        assert row.lease_expires_at is not None
        gen_before_reclaim = row.lease_generation
    # 进程死亡后页租约 + Job 租约过期，恢复器接管（代次 +1）并重新排队。
    _expire_page_leases(env)
    _expire_job_lease(env, job_id)
    report = run_startup_recovery(env["factory"])
    assert job_id in report.recovered_jobs
    assert job_state(env, job_id) == "queued"
    recover_evidence_ocr_runs(
        env["factory"],
        recovered_job_ids=report.recovered_jobs,
        cancelled_job_ids=report.cancelled_jobs,
        failed_final_job_ids=report.failed_final_jobs,
    )
    recovered_runs = ocr_runs(env, job_id)
    assert len(recovered_runs) == 1
    assert recovered_runs[0].status == OcrRunStatus.FAILED
    with env["factory"]() as session:
        row = session.execute(select(PageWorkLeaseRecord)).scalars().one()
        assert row.lease_generation >= gen_before_reclaim

    inference.crash_after_inference = False
    runner2 = build_runner(env, inference=inference)
    assert runner2.run_job(job_id) is True
    assert job_state(env, job_id) == "completed"
    assert succeeded_pages(env) == 1
    assert inference.calls == [1, 1]  # 只重跑未提交页，且旧结果未被接受


def test_orphan_ocr_run_scan_runs_without_explicit_recovery_ids(env):
    """启动恢复即使没有任务恢复清单，也必须收敛终态 Job 的孤儿 OCRRun。"""
    from app.storage.models import JobRecord

    add_file(env, content=png_bytes(), media_type="image/png", file_name="p.png", version_id="doc-orphan")
    snapshot = make_snapshot(
        env, snapshot_id="snap-orphan", members=[("logical-orphan", "doc-orphan", SnapshotMemberOrigin.ADDED)]
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-orphan")

    with pytest.raises(ProcessDeath):
        build_runner(env, inference=FakeInference(crash_after_inference=True)).run_job(job_id)

    # 模拟 Job 已由另一条终态路径收敛；本次 OCR 恢复调用不携带显式 ID。
    with env["factory"]() as session, session.begin():
        job = session.get(JobRecord, job_id)
        assert job is not None
        job.state = "failed_final"
        job.lease_owner = None
        job.lease_expires_at = None

    recover_evidence_ocr_runs(env["factory"])
    runs = ocr_runs(env, job_id)
    assert len(runs) == 1
    assert runs[0].status == OcrRunStatus.FAILED
    # 没有显式恢复 ID 时，终态扫描同时补齐候选终态；不会永久停在处理中。
    assert snapshot_state(env, snapshot.evidence_snapshot_id) == SnapshotStatus.TERMINAL_FAILURE


def test_retry_budget_exhaustion_closes_snapshot(env):
    """最后一次可重试失败不能让任务终败而快照仍显示可重试。"""
    add_file(env, content=png_bytes(), media_type="image/png", file_name="p.png", version_id="doc-budget")
    snapshot = make_snapshot(
        env, snapshot_id="snap-budget", members=[("logical-budget", "doc-budget", SnapshotMemberOrigin.ADDED)]
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-budget")
    inference = FakeInference(fail_pages={1})

    for attempt in range(EVIDENCE_PROCESSING_MAX_ATTEMPTS):
        assert build_runner(env, inference=inference).run_job(job_id) is True
        if attempt < EVIDENCE_PROCESSING_MAX_ATTEMPTS - 1:
            assert job_state(env, job_id) == "failed_retryable"
            assert snapshot_state(env, snapshot.evidence_snapshot_id) == SnapshotStatus.RETRYABLE_FAILURE
            retry_job(env, job_id)
        else:
            assert job_state(env, job_id) == "failed_final"

    assert snapshot_state(env, snapshot.evidence_snapshot_id) == SnapshotStatus.TERMINAL_FAILURE


# ---------------------------------------------------------------------------
# 晚到结果 / 租约 / 缓存写冲突
# ---------------------------------------------------------------------------


def _expire_page_leases(env) -> None:
    with env["factory"]() as session, session.begin():
        for row in session.execute(select(PageWorkLeaseRecord)).scalars():
            row.lease_expires_at = utc_now() - timedelta(seconds=10)


def test_stale_late_result_rejected_after_lease_reclaim(env):
    content = png_bytes()
    add_file(env, content=content, media_type="image/png", file_name="p.png", version_id="doc-late")
    snapshot = make_snapshot(
        env, snapshot_id="snap-late", members=[("logical-late", "doc-late", SnapshotMemberOrigin.ADDED)]
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-late")

    # 推理完成后、提交前：租约过期并被新 worker 接管（代次 +1）。
    block = threading.Event()
    wait = threading.Event()
    inference = FakeInference(block_event=block, wait_event=wait)

    def reclaim():
        block.wait(timeout=10)
        _expire_page_leases(env)
        with env["factory"]() as session, session.begin():
            # 新 worker 领取代次 +1（同一 work_item）。
            row = session.execute(
                select(PageWorkLeaseRecord).limit(1)
            ).scalars().one()
            PageWorkLeaseRepository(session).claim(row.work_item_id, "w2", timedelta(seconds=60))
        wait.set()

    thread = threading.Thread(target=reclaim, daemon=True)
    thread.start()
    runner = build_runner(env, inference=inference)
    assert runner.run_job(job_id) is True
    thread.join(timeout=10)
    assert job_state(env, job_id) == "failed_retryable"

    # 晚到结果被拒绝：无成功缓存；审计 REJECTED_LATE 尝试存在。
    assert succeeded_pages(env) == 0
    with env["factory"]() as session:
        late = session.execute(
            select(OCRAttemptRecord).where(
                OCRAttemptRecord.status == OcrAttemptStatus.REJECTED_LATE.value
            )
        ).scalars().all()
    assert len(late) == 1
    assert late[0].status == OcrAttemptStatus.REJECTED_LATE.value
    assert late[0].raw_response_artifact_id is not None
    with env["factory"]() as session:
        response_artifact = RawOcrResponseArtifactRepository(session).get(
            late[0].raw_response_artifact_id
        )
    assert ArtifactStore(env["paths"]).read(response_artifact.storage_ref) == (
        b'{"model":"GLM-OCR-bf16","choices":[{"message":{"content":"'
        b'GLUCOSE 5.6 mmol/L\n"}}]}'
    )


def test_cache_write_failure_does_not_pollute_success_cache(env):
    content = png_bytes()
    add_file(env, content=content, media_type="image/png", file_name="p.png", version_id="doc-cw")
    snapshot = make_snapshot(
        env, snapshot_id="snap-cw", members=[("logical-cw", "doc-cw", SnapshotMemberOrigin.ADDED)]
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-cw")

    # 共享适配器：racing inference 用同一指纹计算缓存键并先提交同键成功结果。
    from app.domain.contracts.ocr import OCRPage, PageQualityMetrics
    from app.evidence.ocr_adapter import TextOnlyOcrAdapter
    from app.storage.ocr_models import OCRPageRecord

    adapter = TextOnlyOcrAdapter()
    seeded = {"done": False}

    def racing_inference(payload, image_bytes):
        if not seeded["done"]:
            with env["factory"]() as session, session.begin():
                processing = (
                    session.execute(
                        select(OCRPageRecord).where(
                            OCRPageRecord.status == "processing",
                        )
                    )
                    .scalars()
                    .one()
                )
                cache_key = adapter.cache_key(
                    page_artifact_id=processing.page_artifact_id,
                    source_sha256=processing.source_sha256,
                    page_number=processing.page_number,
                    page_input_sha256=processing.page_input_sha256,
                )
                page = OCRPage(
                    ocr_page_id="ocr-page-seeded",
                    page_artifact_id=processing.page_artifact_id,
                    source_sha256=processing.source_sha256,
                    page_number=processing.page_number,
                    page_input_sha256=processing.page_input_sha256,
                    ocr_profile_sha256=processing.ocr_profile_sha256,
                    cache_key=cache_key,
                    layout_parser_version=processing.layout_parser_version,
                    coordinate_transform_version=processing.coordinate_transform_version,
                    raw_text="seeded",
                    raw_text_sha256=sha(b"seeded"),
                    normalized_text=None,
                    layout_sidecar_sha256=None,
                    quality=PageQualityMetrics(char_count=6, word_count=1),
                    risk_items=[],
                    status=OCRPageStatus.SUCCEEDED,
                    started_at=FIXED_UTC,
                    completed_at=FIXED_UTC,
                )
                OcrPageRepository(session).create(page)
            seeded["done"] = True
        return InferenceResult(
            raw_response=b'{"choices":[{"message":{"content":"x"}}]}',
            recognized_text="x",
            verified_coordinates=False,
        )

    runner = build_runner(env, inference=racing_inference, adapter=adapter)
    assert runner.run_job(job_id) is True
    assert job_state(env, job_id) == "failed_retryable"
    # 成功缓存未被污染：仍只有注入的那一条成功行，重复尝试被审计拒绝。
    with env["factory"]() as session:
        successes = (
            session.execute(
                select(OCRPageRecord).where(OCRPageRecord.status == "succeeded")
            )
            .scalars()
            .all()
        )
        late = (
            session.execute(
                select(OCRAttemptRecord).where(
                    OCRAttemptRecord.status == OcrAttemptStatus.REJECTED_LATE.value
                )
            )
            .scalars()
            .all()
        )
    assert len(successes) == 1
    assert successes[0].ocr_page_id == "ocr-page-seeded"
    assert len(late) >= 1


# ---------------------------------------------------------------------------
# 部分文件失败 / 门禁满槽 / 进度事件 / 检查点
# ---------------------------------------------------------------------------


def test_partial_file_failure_prevents_revision_and_completion(env):
    # 损坏图片（不可解码）作为失败页 + 正常 PNG 兄弟页。
    bad = b"\x89PNG\r\n\x1a\nnot-a-real-image-bytes"
    add_file(env, content=bad, media_type="image/png", file_name="bad.png", version_id="doc-bad")
    add_file(env, content=png_bytes(), media_type="image/png", file_name="ok.png", version_id="doc-ok")
    snapshot = make_snapshot(
        env,
        snapshot_id="snap-part",
        members=[
            ("logical-bad", "doc-bad", SnapshotMemberOrigin.ADDED),
            ("logical-ok", "doc-ok", SnapshotMemberOrigin.ADDED),
        ],
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-part")
    runner = build_runner(env, inference=FakeInference())
    assert runner.run_job(job_id) is True
    # 永久失败：任一失败页阻止冻结 READY 处理修订并阻止任务完成。
    assert job_state(env, job_id) == "failed_final"
    assert snapshot_state(env, snapshot.evidence_snapshot_id) == SnapshotStatus.TERMINAL_FAILURE
    assert succeeded_pages(env) == 1  # 兄弟成功页产物保持不可变
    with env["factory"]() as session:
        revision_count = int(
            session.execute(
                select(func.count()).select_from(EvidenceProcessingRevisionRecord)
            ).scalar_one()
        )
    assert revision_count == 0  # 不得以 READY 修订伪装“完整”
    # 兄弟页成功运行仍存在（不可变），失败页无 OCR 运行。
    runs = ocr_runs(env, job_id)
    ok_run = next(run for run in runs if run.source_document_version_id == "doc-ok")
    assert ok_run.status == OcrRunStatus.SUCCEEDED
    assert all(run.source_document_version_id != "doc-bad" for run in runs)


def test_gate_occupied_waits_then_retryable_failure(env):
    content = png_bytes()
    add_file(env, content=content, media_type="image/png", file_name="p.png", version_id="doc-g")
    snapshot = make_snapshot(
        env, snapshot_id="snap-g", members=[("logical-g", "doc-g", SnapshotMemberOrigin.ADDED)]
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-g")

    # 占满 8 个 OCR 槽位（与执行器共用同一门禁库，构成真实竞争）。
    occupant = OmlxGateClient(
        db_path=env["gate"].db_path, owner="occupier", acquire_timeout=1.0
    )
    held = []
    for _ in range(8):
        result = occupant.acquire(wait=False)
        assert result.get("lease_id"), "测试前置：应能占满 8 槽"
        held.append(result)
    try:
        waiter = OmlxGateClient(
            db_path=env["gate"].db_path, owner="waiter", acquire_timeout=0.3
        )
        runner = build_runner(env, inference=FakeInference(), gate=waiter)
        assert runner.run_job(job_id) is True
        assert job_state(env, job_id) == "failed_retryable"
        assert succeeded_pages(env) == 0
    finally:
        for lease in held:
            occupant.release(lease["lease_id"])


def test_nonretryable_ocr_failure_blocks_completion(env, tmp_path):
    """不可重试的 OCR 失败页必须进入文件失败汇总，不能伪装成成功运行。"""
    add_file(env, content=png_bytes(), media_type="image/png", file_name="p.png", version_id="doc-nr")
    snapshot = make_snapshot(
        env, snapshot_id="snap-nr", members=[("logical-nr", "doc-nr", SnapshotMemberOrigin.ADDED)]
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-nr")
    unavailable_gate = OmlxGateClient(
        script_path=tmp_path / "missing-omlx-gate.py",
        db_path=env["gate"].db_path,
        owner="missing-gate",
        acquire_timeout=0.1,
    )
    runner = build_runner(
        env,
        inference=FakeInference(),
        gate=unavailable_gate,
        gate_unavailable_retryable=False,
    )
    assert runner.run_job(job_id) is True
    assert job_state(env, job_id) == "failed_final"
    assert snapshot_state(env, snapshot.evidence_snapshot_id) == SnapshotStatus.TERMINAL_FAILURE
    runs = ocr_runs(env, job_id)
    assert len(runs) == 1
    assert runs[0].status == OcrRunStatus.PARTIAL
    assert runs[0].page_failed == 1


def test_rejected_provider_response_is_saved_for_replay(env):
    """已收到但不合格的 provider 原文也必须进入不可变响应工件。"""
    add_file(env, content=png_bytes(), media_type="image/png", file_name="p.png", version_id="doc-raw-failure")
    snapshot = make_snapshot(
        env,
        snapshot_id="snap-raw-failure",
        members=[("logical-raw-failure", "doc-raw-failure", SnapshotMemberOrigin.ADDED)],
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-raw-failure")
    raw_response = b'{"model":"wrong-model","choices":[{"message":{"content":""}}]}'

    def rejected_response(_payload, _image):
        raise OmlxInferenceResponseError(
            "model mismatch",
            raw_response=raw_response,
        )

    assert build_runner(env, inference=rejected_response).run_job(job_id) is True
    run = ocr_runs(env, job_id)[0]
    with env["factory"]() as session:
        attempt = OcrAttemptRepository(session).list_by_run(run.ocr_run_id)[0]
    assert attempt.raw_response_artifact_id is not None
    assert ArtifactStore(env["paths"]).read_by_sha("raw_response", sha(raw_response)) == raw_response


def test_page_progress_events_persisted_and_chinese(env):
    content = tiff_bytes(2)
    add_file(env, content=content, media_type="image/tiff", file_name="s.tif", version_id="doc-ev")
    snapshot = make_snapshot(
        env, snapshot_id="snap-ev", members=[("logical-ev", "doc-ev", SnapshotMemberOrigin.ADDED)]
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-ev")
    runner = build_runner(env, inference=FakeInference())
    assert runner.run_job(job_id) is True

    with env["factory"]() as session:
        store = JobStore(session)
        events = store.list_event_rows(job_id)
    progress = [row.event for row in events if row.event.event_type == JobEventType.PAGE_PROGRESS]
    assert len(progress) == 3  # 页面清单 + 每页一次持久进度快照
    assert progress[-1].payload["进度说明"] == "已处理第 2 页，共 2 页"
    assert "文件" in progress[-1].payload
    # 用户可见事件文本为中文，不暴露内部字段名。
    assert all(key.isascii() is False for key in progress[-1].payload)


def test_slow_visual_page_does_not_block_sibling_page(env):
    content = tiff_bytes(2)
    add_file(
        env,
        content=content,
        media_type="image/tiff",
        file_name="parallel.tif",
        version_id="doc-parallel",
    )
    snapshot = make_snapshot(
        env,
        snapshot_id="snap-parallel",
        members=[("logical-parallel", "doc-parallel", SnapshotMemberOrigin.ADDED)],
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-parallel")
    slow_started = threading.Event()
    release_slow = threading.Event()
    fast_finished = threading.Event()

    def inference(payload, _image_bytes):
        page = int(payload["page"]["page_number"])
        if page == 1:
            slow_started.set()
            assert release_slow.wait(timeout=10)
        else:
            fast_finished.set()
        text = f"第 {page} 页"
        return InferenceResult(
            raw_response=(
                b'{"model":"GLM-OCR-bf16","choices":[{"message":{"content":"'
                + text.encode("utf-8")
                + b'"}}]}'
            ),
            recognized_text=text,
            verified_coordinates=False,
        )

    runner = build_runner(
        env,
        inference=inference,
        page_processing_concurrency=2,
    )
    completed: list[bool] = []
    thread = threading.Thread(target=lambda: completed.append(runner.run_job(job_id)))
    thread.start()
    assert slow_started.wait(timeout=10)
    assert fast_finished.wait(timeout=3), "第 2 页不应等待第 1 页识别完成"
    release_slow.set()
    thread.join(timeout=15)

    assert thread.is_alive() is False
    assert completed == [True]
    assert job_state(env, job_id) == "completed"
    assert succeeded_pages(env) == 2


def test_blocked_file_does_not_head_of_line_block_sibling_and_global_cap(env):
    version_ids = ["doc-global-a", "doc-global-b", "doc-global-c", "doc-global-d"]
    source_hashes = {}
    for index, version_id in enumerate(version_ids):
        source_hashes[version_id] = add_file(
            env,
            content=png_bytes(text_pixel=120 + index),
            media_type="image/png",
            file_name=f"{version_id}.png",
            version_id=version_id,
        )
    snapshot = make_snapshot(
        env,
        snapshot_id="snap-global-pages",
        members=[
            (f"logical-{version_id}", version_id, SnapshotMemberOrigin.ADDED)
            for version_id in version_ids
        ],
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-global-pages")
    slow_started = threading.Event()
    release_slow = threading.Event()
    sibling_finished = threading.Event()
    counter_lock = threading.Lock()
    active = 0
    peak = 0
    blocked_source = None

    def inference(payload, _image_bytes):
        nonlocal active, peak, blocked_source
        source_sha256 = payload["page"]["source_sha256"]
        with counter_lock:
            # File preparation order does not guarantee inference entry order.
            if blocked_source is None:
                blocked_source = source_sha256
            is_blocked = source_sha256 == blocked_source
            active += 1
            peak = max(peak, active)
        try:
            if is_blocked:
                slow_started.set()
                assert release_slow.wait(timeout=10)
            else:
                sibling_finished.set()
            time.sleep(0.05)
            text = source_sha256[:12]
            return InferenceResult(
                raw_response=(
                    b'{"model":"GLM-OCR-bf16","choices":[{"message":{"content":"'
                    + text.encode("utf-8")
                    + b'"}}]}'
                ),
                recognized_text=text,
                verified_coordinates=False,
            )
        finally:
            with counter_lock:
                active -= 1

    runner = build_runner(
        env,
        inference=inference,
        page_processing_concurrency=2,
    )
    completed: list[bool] = []
    thread = threading.Thread(target=lambda: completed.append(runner.run_job(job_id)))
    thread.start()
    try:
        assert slow_started.wait(timeout=10)
        assert sibling_finished.wait(timeout=3), "另一份资料不应等待被阻塞资料完成"
        with counter_lock:
            assert peak == 2
            assert active <= 2
    finally:
        release_slow.set()
        thread.join(timeout=15)

    assert thread.is_alive() is False
    assert completed == [True]
    assert job_state(env, job_id) == "completed"
    assert succeeded_pages(env) == len(version_ids)
    with counter_lock:
        assert peak == 2
        assert active == 0
    with env["factory"]() as session:
        revision = EvidenceProcessingRevisionRepository(session).list_by_snapshot(
            snapshot.evidence_snapshot_id
        )[0]
    assert [entry.source_document_version_id for entry in revision.manifest] == version_ids
    assert [entry.page_number for entry in revision.manifest] == [1] * len(version_ids)


def test_checkpoint_summary_and_revision_frozen_once(env):
    content = tiff_bytes(2)
    add_file(env, content=content, media_type="image/tiff", file_name="s.tif", version_id="doc-ck")
    snapshot = make_snapshot(
        env, snapshot_id="snap-ck", members=[("logical-ck", "doc-ck", SnapshotMemberOrigin.ADDED)]
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-ck")

    def capturing_inference(payload, image_bytes):
        return FakeInference()(payload, image_bytes)

    runner = build_runner(env, inference=capturing_inference)
    assert runner.run_job(job_id) is True
    with env["factory"]() as session:
        checkpoint = JobStore(session).get_last_checkpoint(job_id, STEP_ID)
    assert checkpoint is not None
    _checkpoint_id, payload = checkpoint
    assert payload["snapshot_id"] == snapshot.evidence_snapshot_id
    assert payload["total_pages"] == 2
    assert payload["total_succeeded"] == 2
    assert payload["revision_id"]
    # 修订只冻结一次（不可变），不可激活。
    with env["factory"]() as session:
        revisions = EvidenceProcessingRevisionRepository(session).list_by_snapshot(
            snapshot.evidence_snapshot_id
        )
    assert len(revisions) == 1
    assert revisions[0].is_activatable is False
    assert revisions[0].manifest_sha256 == evidence_processing_manifest_hash(
        entries=[
            (e.source_document_version_id, e.page_number, e.original_frame,
             e.page_artifact_id, e.ocr_page_id, e.status.value)
            for e in revisions[0].manifest
        ]
    )


def test_revision_not_frozen_on_retryable_failure(env):
    content = png_bytes()
    add_file(env, content=content, media_type="image/png", file_name="p.png", version_id="doc-nf")
    snapshot = make_snapshot(
        env, snapshot_id="snap-nf", members=[("logical-nf", "doc-nf", SnapshotMemberOrigin.ADDED)]
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-nf")
    inference = FakeInference(fail_pages={1})
    runner = build_runner(env, inference=inference)
    assert runner.run_job(job_id) is True
    assert job_state(env, job_id) == "failed_retryable"
    with env["factory"]() as session:
        revision_count = int(
            session.execute(
                select(func.count()).select_from(EvidenceProcessingRevisionRecord)
            ).scalar_one()
        )
    assert revision_count == 0


# ---------------------------------------------------------------------------
# Codex 复核修复反例测试（worker_03 追加）
# ---------------------------------------------------------------------------


def _make_visual_inputs(env, *, worker: str):
    """构造一页视觉输入的 profile/run/artifact（供两竞争者直接调用页处理）。"""
    from app.domain.contracts.ocr import PageArtifact as _PA

    adapter = TextOnlyOcrAdapter()
    content = png_bytes()
    store = ArtifactStore(env["paths"])
    stored = store.put("page_image", content)
    project_id, subject_id, episode_id = env["scope"]
    digest = "b" * 64
    blob = SourceBlob(
        source_blob_id=digest, sha256=digest, byte_size=len(content),
        media_type="image/png", storage_ref=f"blobs/{digest}", created_at=FIXED_UTC,
    )
    version = SourceDocumentVersion(
        source_document_version_id="doc-2c",
        logical_document_id="logical-2c",
        source_blob_sha256=digest,
        file_name="p.png",
        media_type="image/png",
        page_count=None,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        version_number=1,
        created_at=FIXED_UTC,
        created_by="tester",
    )
    with env["factory"]() as session, session.begin():
        BlobRepository(session).get_or_create_by_sha256(blob)
        SourceDocumentRepository(session).create_version(version)
        profile = OCRProfileRepository(session).get_or_create(
            adapter.profile(created_at=FIXED_UTC)
        )
        run = OCRRun(
            ocr_run_id=f"run-2c-{worker}",
            source_document_version_id="doc-2c",
            ocr_profile_id=profile.ocr_profile_id,
            ocr_profile_sha256=profile.profile_sha256,
            job_id=None,
            status=OcrRunStatus.RUNNING,
            page_total=1,
            page_succeeded=0,
            page_failed=0,
            started_at=FIXED_UTC,
            completed_at=None,
            created_at=FIXED_UTC,
        )
        OcrRunRepository(session).create(run)
    artifact = _PA(
        page_artifact_id="pa-2c",
        source_document_version_id="doc-2c",
        page_number=1,
        original_frame=None,
        source_sha256="a" * 64,
        page_input_sha256=stored.sha256,
        page_image_sha256=stored.sha256,
        native_text_sha256=None,
        native_coordinates_sha256=None,
        page_width=24.0,
        page_height=24.0,
        rotation=0,
        renderer_version="r/v1",
        decoder_version="d/v1",
        derivative_sha256="d" * 64,
        coordinate_transform_version="t/v1",
        status=PageArtifactStatus.SUCCEEDED,
        failure_reason=None,
    )
    # OCRPage 外键要求页产物行存在：先持久化页产物（幂等）。
    with env["factory"]() as session, session.begin():
        PageArtifactRepository(session).get_or_create(artifact)
    return adapter, artifact, run.ocr_run_id, store


def test_two_contenders_no_orphan_processing_row(env):
    """两个竞争者处理同一页：只有一个胜者领取租约并写 PROCESSING 页/调模型。

    PageLeaseBusyError 竞争者不产生 PROCESSING 页、不调用模型；处理完成后该
    缓存键恰好 1 条 PROCESSING + 1 条 SUCCEEDED，无孤儿 PROCESSING 行。
    """
    adapter, artifact, run_id, store = _make_visual_inputs(env, worker="a")
    block = threading.Event()
    wait = threading.Event()
    inference = FakeInference(block_event=block, wait_event=wait)
    gate = OmlxGateClient(db_path=env["gate"].db_path, owner="test-2c", acquire_timeout=10)
    config_a = EvidenceProcessingExecutorConfig(
        session_factory=env["factory"], data_paths=env["paths"],
        worker_id="wA", inference=inference, gate=gate,
    )
    config_b = EvidenceProcessingExecutorConfig(
        session_factory=env["factory"], data_paths=env["paths"],
        worker_id="wB", inference=inference, gate=gate,
    )
    results: dict[str, object] = {}

    def run_a():
        results["A"] = _process_visual_page(
            config=config_a, ocr_run_id=run_id, page_number=1, artifact=artifact,
            source_sha256=artifact.source_sha256, adapter=adapter, gate=gate,
            artifact_store=store,
        )

    def run_b():
        results["B"] = _process_visual_page(
            config=config_b, ocr_run_id=run_id, page_number=1, artifact=artifact,
            source_sha256=artifact.source_sha256, adapter=adapter, gate=gate,
            artifact_store=store,
        )

    ta = threading.Thread(target=run_a, daemon=True)
    tb = threading.Thread(target=run_b, daemon=True)
    ta.start()
    tb.start()
    assert block.wait(timeout=10), "至少一个 worker 应取得租约并开始推理"
    time.sleep(0.5)  # 让竞争者完成（deferred）
    wait.set()
    ta.join(timeout=15)
    tb.join(timeout=15)

    winners = [k for k in ("A", "B") if getattr(results[k], "ocr_page", None) is not None]
    losers = [k for k in ("A", "B") if getattr(results[k], "deferred", False)]
    assert len(winners) == 1 and len(losers) == 1
    assert inference.calls == [1]  # 只有胜者调用模型

    cache_key = adapter.cache_key(
        page_artifact_id=artifact.page_artifact_id,
        source_sha256=artifact.source_sha256,
        page_number=1,
        page_input_sha256=artifact.page_image_sha256 or "",
    )
    with env["factory"]() as session:
        processing = session.execute(
            select(OCRPageRecord).where(
                OCRPageRecord.cache_key == cache_key,
                OCRPageRecord.status == "processing",
            )
        ).scalars().all()
        succeeded = session.execute(
            select(OCRPageRecord).where(
                OCRPageRecord.cache_key == cache_key,
                OCRPageRecord.status == "succeeded",
            )
        ).scalars().all()
    assert len(processing) == 1, "无孤儿 PROCESSING 行（竞争者不得创建）"
    assert len(succeeded) == 1


def test_page_lease_heartbeat_survives_long_inference(env):
    """页租约 TTL 短于推理时长：心跳必须续租，否则提交被晚到拒绝。

    页租约 TTL 2 秒、推理阻塞 3 秒：若无心跳，租约在推理期间过期，
    commit_guard 会拒绝晚到结果使任务可重试；有心跳则正常完成。
    """
    content = png_bytes()
    add_file(env, content=content, media_type="image/png", file_name="p.png", version_id="doc-hb")
    snapshot = make_snapshot(
        env, snapshot_id="snap-hb", members=[("logical-hb", "doc-hb", SnapshotMemberOrigin.ADDED)]
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-hb")
    block = threading.Event()
    wait = threading.Event()
    inference = FakeInference(block_event=block, wait_event=wait)
    runner = build_runner(
        env, inference=inference, page_lease_ttl=timedelta(seconds=2)
    )

    def release_later():
        block.wait(timeout=10)
        time.sleep(3.0)  # 超过页租约 TTL：心跳必须续租
        wait.set()

    t = threading.Thread(target=release_later, daemon=True)
    t.start()
    assert runner.run_job(job_id) is True
    t.join(timeout=15)
    assert job_state(env, job_id) == "completed"
    assert succeeded_pages(env) == 1


def test_page_lease_loss_during_heartbeat_shutdown_rejects_result(env, monkeypatch):
    """心跳停止阶段才发现租约丢失时，也不得进入成功缓存。"""
    from app.services import evidence_processing_executor as executor_module

    adapter, artifact, run_id, store = _make_visual_inputs(env, worker="shutdown")
    gate = OmlxGateClient(db_path=env["gate"].db_path, owner="shutdown-test")
    original_stop = executor_module._PageLeaseHeartbeat.stop

    def stop_and_mark_lost(heartbeat) -> None:
        original_stop(heartbeat)
        heartbeat.lost = True

    monkeypatch.setattr(
        executor_module._PageLeaseHeartbeat,
        "stop",
        stop_and_mark_lost,
    )
    outcome = _process_visual_page(
        config=EvidenceProcessingExecutorConfig(
            session_factory=env["factory"],
            data_paths=env["paths"],
            worker_id="shutdown-worker",
            inference=FakeInference(),
            gate=gate,
        ),
        ocr_run_id=run_id,
        page_number=1,
        artifact=artifact,
        source_sha256=artifact.source_sha256,
        adapter=adapter,
        gate=gate,
        artifact_store=store,
    )
    assert outcome.ocr_page is None
    assert outcome.deferred is True
    assert succeeded_pages(env) == 0
    with env["factory"]() as session:
        late = session.execute(
            select(OCRAttemptRecord).where(
                OCRAttemptRecord.status == OcrAttemptStatus.REJECTED_LATE.value
            )
        ).scalars().all()
    assert len(late) == 1


def test_retry_attempt_numbers_monotonic_per_cache_key(env):
    """同一缓存键跨重试：attempt_number 单调递增，旧行不原地改写。"""
    content = tiff_bytes(2)
    add_file(env, content=content, media_type="image/tiff", file_name="scan.tif", version_id="doc-at")
    snapshot = make_snapshot(
        env, snapshot_id="snap-at", members=[("logical-at", "doc-at", SnapshotMemberOrigin.ADDED)]
    )
    job_id = create_job(env, snapshot.evidence_snapshot_id, key="k-at")
    inference = FakeInference(fail_pages={2})
    runner = build_runner(env, inference=inference)
    assert runner.run_job(job_id) is True
    assert job_state(env, job_id) == "failed_retryable"

    inference.fail_pages = set()
    retry_job(env, job_id)
    runner2 = build_runner(env, inference=inference)
    assert runner2.run_job(job_id) is True
    assert job_state(env, job_id) == "completed"

    with env["factory"]() as session:
        rows = session.execute(
            select(OCRAttemptRecord).order_by(OCRAttemptRecord.attempt_number)
        ).scalars().all()
    by_cache: dict[str, list[tuple[int, str]]] = {}
    for row in rows:
        by_cache.setdefault(row.cache_key, []).append((row.attempt_number, row.status))
    retried = [v for v in by_cache.values() if len(v) >= 2]
    assert len(retried) == 1, "只有失败重试的页存在多次尝试"
    numbers = [n for n, _s in retried[0]]
    statuses = [s for _n, s in retried[0]]
    assert numbers == [1, 2]
    assert statuses == ["failed", "succeeded"]  # 旧失败行保留，新成功行追加
