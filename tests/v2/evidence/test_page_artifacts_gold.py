"""不可变页产物生成金标准测试（worker_02）。

用 Slice 4.0 合成金标准验证逐页路由与 ``PageArtifact`` 生成：原生 PDF 页保存
原生文本/坐标工件与页图，扫描/图片/TIFF 帧走 vision 路由（text-only、无坐标），
TXT 走文本解码；失败文件显式失败页；页产物可复现（同一输入同一哈希）且经仓储
内容去重持久化；不可变工件库读回复核哈希、拒绝投毒。
"""
from __future__ import annotations

import hashlib
import json

import pytest

from app.domain.contracts.enums import (
    ExtractionRoute,
    PageArtifactStatus,
)
from app.evidence.artifacts import ArtifactIntegrityError, ArtifactStore
from app.evidence.page_processor import (
    DECODER_VERSION_BY_KIND,
    build_page_artifact,
    decide_route,
)
from app.evidence.paging import page_source_document
from app.storage import ocr_repositories as orr
from app.storage.evidence_repositories import (
    BlobRepository,
    SourceDocumentRepository,
)
from app.storage.repositories import persist_fixture
from tests.v2.storage.test_repositories_roundtrip import FIXTURES

FIXED = __import__("datetime").datetime(
    2026, 8, 19, 12, 0, 0, tzinfo=__import__("datetime").timezone.utc
)


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


@pytest.fixture
def artifact_store(ocr_engine):
    from app.storage.config import resolve_data_paths

    return ArtifactStore(resolve_data_paths())


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _scope(fixture):
    return (
        fixture.project.project_id,
        fixture.subject.subject_id,
        fixture.review_episode.review_episode_id,
    )


def _seed_version(session, fixture, *, file_ref, content, version_id, media_type):
    from app.domain.contracts.evidence_ingestion import (
        SourceBlob,
        SourceDocumentVersion,
    )

    project_id, subject_id, episode_id = _scope(fixture)
    blob = SourceBlob(
        source_blob_id=sha(content),
        sha256=sha(content),
        byte_size=len(content),
        media_type=media_type,
        storage_ref=f"blobs/{sha(content)}",
        created_at=FIXED,
    )
    BlobRepository(session).get_or_create_by_sha256(blob)
    version = SourceDocumentVersion(
        source_document_version_id=version_id,
        logical_document_id=f"log-{version_id}",
        source_blob_sha256=blob.sha256,
        file_name=file_ref,
        media_type=media_type,
        page_count=None,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        version_number=1,
        created_at=FIXED,
        created_by="tester",
    )
    SourceDocumentRepository(session).create_version(version)
    session.flush()
    return version


def test_native_pdf_artifacts_with_native_coordinates(
    seeded, artifact_store, gold_root, gold_set
):
    session, fixture = seeded
    content = (gold_root / "native-01.pdf").read_bytes()
    version_id = "doc-native-01"
    version = _seed_version(
        session, fixture, file_ref="native-01.pdf", content=content,
        version_id=version_id, media_type="application/pdf",
    )
    repo = orr.PageArtifactRepository(session)
    artifacts = []
    for page_input in page_source_document(
        content=content, media_kind="pdf", source_sha256=sha(content)
    ).pages:
        artifacts.append(
            build_page_artifact(
                page_input=page_input,
                source_document_version_id=version.source_document_version_id,
                source_sha256=sha(content),
                artifact_store=artifact_store,
                persist=repo.get_or_create,
            )
        )
    assert len(artifacts) == 3
    assert [a.page_number for a in artifacts] == [1, 2, 3]
    for artifact in artifacts:
        assert artifact.status == PageArtifactStatus.SUCCEEDED
        assert artifact.page_image_sha256
        assert artifact.native_text_sha256
        assert artifact.native_coordinates_sha256
        assert artifact.page_width == 595.0
        assert artifact.page_height == 842.0
        assert artifact.rotation == 0
    # 坐标工件可解析且含词坐标。
    coords = json.loads(
        artifact_store.read(
            f"artifacts/native_coordinates/{artifacts[0].native_coordinates_sha256}"
        )
    )
    assert coords["schema"] == "native_coordinates/v1"
    assert coords["words"]
    assert coords["chars"]
    # 持久化 + 按资料版本有序回读。
    listed = repo.list_by_source_document_version(version.source_document_version_id)
    assert [a.page_artifact_id for a in listed] == [a.page_artifact_id for a in artifacts]


def test_routes_decided_per_format(gold_root, gold_set):
    cases = {
        "native-01.pdf": ("pdf", ExtractionRoute.NATIVE_PDF_TEXT),
        "scanned-01.pdf": ("pdf", ExtractionRoute.VISION_OCR),
        "photo-01.jpg": ("image", ExtractionRoute.VISION_OCR),
        "txt-01.txt": ("text", ExtractionRoute.SOURCE_TEXT),
    }
    for file_ref, (kind, expected_route) in cases.items():
        content = (gold_root / file_ref).read_bytes()
        plan = page_source_document(content=content, media_kind=kind, source_sha256=sha(content))
        for page_input in plan.pages:
            assert decide_route(page_input) == expected_route, file_ref


def test_tiff_frames_route_to_vision(gold_root, gold_set):
    content = (gold_root / "multi-01.tiff").read_bytes()
    plan = page_source_document(content=content, media_kind="image", source_sha256=sha(content))
    assert plan.page_total == 2
    for page_input in plan.pages:
        assert decide_route(page_input) == ExtractionRoute.VISION_OCR


def test_scanned_image_artifact_is_text_only_no_coordinates(
    seeded, artifact_store, gold_root, gold_set
):
    """扫描/图片页：text-only 路由，无原生文本/坐标，页图存在。"""
    session, fixture = seeded
    for file_ref, kind, version_id in (
        ("scanned-01.pdf", "pdf", "doc-scanned"),
        ("photo-01.jpg", "image", "doc-photo"),
    ):
        content = (gold_root / file_ref).read_bytes()
        version = _seed_version(
            session, fixture, file_ref=file_ref, content=content,
            version_id=version_id,
            media_type="application/pdf" if kind == "pdf" else "image/jpeg",
        )
        repo = orr.PageArtifactRepository(session)
        page_input = page_source_document(
            content=content, media_kind=kind, source_sha256=sha(content)
        ).pages[0]
        artifact = build_page_artifact(
            page_input=page_input,
            source_document_version_id=version.source_document_version_id,
            source_sha256=sha(content),
            artifact_store=artifact_store,
            persist=repo.get_or_create,
        )
        assert artifact.status == PageArtifactStatus.SUCCEEDED
        assert artifact.page_image_sha256
        assert artifact.native_text_sha256 is None
        assert artifact.native_coordinates_sha256 is None
        assert artifact.rotation == 0
        assert artifact.decoder_version == DECODER_VERSION_BY_KIND[kind]


def test_failed_files_produce_explicit_failed_artifacts(
    seeded, artifact_store, gold_root, gold_set
):
    session, fixture = seeded
    for file_ref, kind, version_id in (
        ("corrupt-01.pdf", "pdf", "doc-corrupt"),
        ("bad-image-01.png", "image", "doc-badimg"),
        ("unsupported-01.doc", "doc", "doc-baddoc"),
    ):
        content = (gold_root / file_ref).read_bytes()
        version = _seed_version(
            session, fixture, file_ref=file_ref, content=content,
            version_id=version_id, media_type="application/octet-stream",
        )
        repo = orr.PageArtifactRepository(session)
        plan = page_source_document(content=content, media_kind=kind, source_sha256=sha(content))
        assert len(plan.pages) == 1
        page_input = plan.pages[0]
        assert page_input.expects_failure
        artifact = build_page_artifact(
            page_input=page_input,
            source_document_version_id=version.source_document_version_id,
            source_sha256=sha(content),
            artifact_store=artifact_store,
            persist=repo.get_or_create,
        )
        assert artifact.status == PageArtifactStatus.FAILED
        assert artifact.failure_reason
        assert artifact.page_image_sha256 is None
        assert artifact.native_text_sha256 is None
        assert artifact.native_coordinates_sha256 is None
        assert artifact.renderer_version is None
        # 失败页不伪造任何几何/输入：全部 None（无 0*64/1x1/rotation=0 伪值）。
        assert artifact.page_input_sha256 is None
        assert artifact.page_width is None
        assert artifact.page_height is None
        assert artifact.rotation is None


def test_page_artifact_reproducible_identical_hashes(
    seeded, artifact_store, gold_root, gold_set
):
    """同一输入重复生成页产物 -> 同一页图/原生文本/坐标哈希（确定性渲染）。"""
    session, fixture = seeded
    content = (gold_root / "scanned-01.pdf").read_bytes()
    version = _seed_version(
        session, fixture, file_ref="scanned-01.pdf", content=content,
        version_id="doc-repro", media_type="application/pdf",
    )
    repo = orr.PageArtifactRepository(session)
    page_input = page_source_document(
        content=content, media_kind="pdf", source_sha256=sha(content)
    ).pages[0]
    first = build_page_artifact(
        page_input=page_input,
        source_document_version_id=version.source_document_version_id,
        source_sha256=sha(content),
        artifact_store=artifact_store,
        persist=repo.get_or_create,
    )
    second = build_page_artifact(
        page_input=page_input,
        source_document_version_id=version.source_document_version_id,
        source_sha256=sha(content),
        artifact_store=artifact_store,
        persist=repo.get_or_create,
    )
    assert first.page_artifact_id == second.page_artifact_id
    assert first.page_image_sha256 == second.page_image_sha256
    assert first.derivative_sha256 == second.derivative_sha256


def test_artifact_store_content_addressed_dedup_and_integrity(
    artifact_store, gold_root, gold_set
):
    payload = (gold_root / "photo-01.jpg").read_bytes()
    first = artifact_store.put("page_image", payload)
    second = artifact_store.put("page_image", payload)
    assert first.sha256 == second.sha256 == sha(payload)
    assert first.storage_ref == second.storage_ref
    assert artifact_store.read(first.storage_ref) == payload
    # 投毒：改坏已存字节后读取复核拒绝。
    target = artifact_store.data_paths.root / first.storage_ref
    target.write_bytes(b"tampered")
    with pytest.raises(ArtifactIntegrityError):
        artifact_store.read(first.storage_ref)


def test_artifact_store_rejects_unknown_kind(artifact_store):
    from app.evidence.artifacts import UnknownArtifactKindError

    with pytest.raises(UnknownArtifactKindError):
        artifact_store.put("nonsense", b"x")


def test_artifact_store_rejects_absolute_storage_ref(artifact_store):
    from app.evidence.artifacts import ArtifactStoreError

    with pytest.raises(ArtifactStoreError):
        artifact_store.read("/etc/passwd")


def test_failed_artifact_same_failure_retry_idempotent(
    seeded, artifact_store, gold_root, gold_set
):
    """同失败重试：确定性失败 ID + 仓储去重 -> 同一不可变失败页产物。"""
    session, fixture = seeded
    content = (gold_root / "corrupt-01.pdf").read_bytes()
    version = _seed_version(
        session, fixture, file_ref="corrupt-01.pdf", content=content,
        version_id="doc-fail-dup", media_type="application/pdf",
    )
    repo = orr.PageArtifactRepository(session)
    plan = page_source_document(content=content, media_kind="pdf", source_sha256=sha(content))
    first = build_page_artifact(
        page_input=plan.pages[0],
        source_document_version_id=version.source_document_version_id,
        source_sha256=sha(content),
        artifact_store=artifact_store,
        persist=repo.get_or_create,
    )
    second = build_page_artifact(
        page_input=plan.pages[0],
        source_document_version_id=version.source_document_version_id,
        source_sha256=sha(content),
        artifact_store=artifact_store,
        persist=repo.get_or_create,
    )
    assert first.page_artifact_id == second.page_artifact_id
    assert first.failure_reason == second.failure_reason
    assert first.derivative_sha256 == second.derivative_sha256
    listed = repo.list_by_source_document_version(version.source_document_version_id)
    assert len(listed) == 1  # 幂等去重：只存在一条失败页产物


def test_failed_artifact_materially_different_failure_no_collision(
    seeded, artifact_store, gold_root, gold_set
):
    """实质不同失败：不同失败原因 -> 不同失败 ID/派生指纹，绝不碰撞。"""
    session, fixture = seeded
    content = (gold_root / "corrupt-01.pdf").read_bytes()
    version = _seed_version(
        session, fixture, file_ref="corrupt-01.pdf", content=content,
        version_id="doc-fail-diff", media_type="application/pdf",
    )
    repo = orr.PageArtifactRepository(session)
    from app.domain.contracts.enums import PageArtifactStatus
    from app.evidence.paging import PageInput

    failure_a = PageInput(
        page_number=1, media_kind="pdf", original_frame=None,
        render_source=None, input_sha256=None,
        status=PageArtifactStatus.FAILED,
        failure_reason="PDF 文件被截断，无法解析页面结构",
    )
    # 构造「同一页、不同失败原因」的输入。
    failure_b = PageInput(
        page_number=1, media_kind="pdf", original_frame=None,
        render_source=None, input_sha256=None,
        status=PageArtifactStatus.FAILED,
        failure_reason="文档转换失败，LibreOffice 未成功产出 PDF",
    )
    artifact_a = build_page_artifact(
        page_input=failure_a,
        source_document_version_id=version.source_document_version_id,
        source_sha256=sha(content),
        artifact_store=artifact_store,
        persist=repo.get_or_create,
    )
    # 不同失败 -> 不同确定性 ID（不落库仅构造，证明 ID 不碰撞）。
    artifact_b = build_page_artifact(
        page_input=failure_b,
        source_document_version_id=version.source_document_version_id,
        source_sha256=sha(content),
        artifact_store=artifact_store,
        persist=None,
    )
    assert artifact_a.page_artifact_id != artifact_b.page_artifact_id
    assert artifact_a.derivative_sha256 != artifact_b.derivative_sha256
    # 落库时：不同失败原因使用不同确定性 ID，均保留且可独立回放。
    persisted_b = repo.get_or_create(artifact_b)
    assert persisted_b.page_artifact_id == artifact_b.page_artifact_id
    assert repo.get(artifact_a.page_artifact_id) == artifact_a
    assert repo.get(artifact_b.page_artifact_id) == artifact_b


def test_txt_roundtrip_preserves_native_text_no_coordinates(
    seeded, artifact_store, gold_root, gold_set
):
    """TXT 真相保留：原文存为原生文本工件，路线明确且无伪坐标。"""
    session, fixture = seeded
    content = (gold_root / "txt-gb18030.txt").read_bytes()
    version = _seed_version(
        session, fixture, file_ref="txt-gb18030.txt", content=content,
        version_id="doc-txt", media_type="text/plain",
    )
    repo = orr.PageArtifactRepository(session)
    plan = page_source_document(content=content, media_kind="text", source_sha256=sha(content))
    assert plan.page_total == 1
    assert decide_route(plan.pages[0]) == ExtractionRoute.SOURCE_TEXT
    artifact = build_page_artifact(
        page_input=plan.pages[0],
        source_document_version_id=version.source_document_version_id,
        source_sha256=sha(content),
        artifact_store=artifact_store,
        persist=repo.get_or_create,
    )
    assert artifact.status == PageArtifactStatus.SUCCEEDED
    # 原生文本工件落盘：读回原文（GB18030 解码后文本）。
    assert artifact.native_text_sha256 is not None
    stored_text = artifact_store.read_by_sha("native_text", artifact.native_text_sha256)
    assert stored_text.decode("utf-8") == "受试者甲：已接种疫苗，2026年6月30日。\n"
    # 无坐标 / 无红框精度。
    assert artifact.native_coordinates_sha256 is None
    # 页图存在供查看，页输入身份为来源内容哈希。
    assert artifact.page_image_sha256 is not None
    assert artifact.page_input_sha256 == sha(content)
    # 页图确实是渲染出的文本画布（非空 PNG）。
    image_bytes = artifact_store.read_by_sha("page_image", artifact.page_image_sha256)
    assert image_bytes.startswith(b"\x89PNG")


def test_conversion_failure_does_not_leak_internal_details(
    seeded, artifact_store, gold_root, gold_set
):
    """转换失败：领域失败文本只含稳定中文，绝不泄露异常类型/消息/密钥/退出码。"""
    session, fixture = seeded
    content = (gold_root / "docx-01.docx").read_bytes()
    version = _seed_version(
        session, fixture, file_ref="docx-01.docx", content=content,
        version_id="doc-leak", media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    repo = orr.PageArtifactRepository(session)

    class SecretRaisingConverter:
        converter_version = "fake/v1"

        def convert_to_pdf(self, content: bytes, *, suffix: str) -> bytes:
            raise RuntimeError("Bearer secret-token-ABC at http://user:pass@host")

    plan = page_source_document(
        content=content, media_kind="docx",
        source_sha256=sha(content), doc_converter=SecretRaisingConverter(),
    )
    page_input = plan.pages[0]
    assert page_input.expects_failure
    artifact = build_page_artifact(
        page_input=page_input,
        source_document_version_id=version.source_document_version_id,
        source_sha256=sha(content),
        artifact_store=artifact_store,
        persist=repo.get_or_create,
    )
    assert artifact.status == PageArtifactStatus.FAILED
    assert artifact.failure_reason == "DOCX 转换失败，无法生成可处理页面"  # 稳定中文，无异常细节
    for secret in ("RuntimeError", "secret-token-ABC", "user:pass", "Bearer"):
        assert secret not in artifact.failure_reason


def test_text_layer_probe_failure_degrades_to_vision_no_leak(
    seeded, artifact_store, gold_root, gold_set, monkeypatch
):
    """文本层探测失败：按设计降级为扫描页（VISION_OCR），不泄露内部异常。"""
    import app.evidence.page_processor as pp

    session, fixture = seeded
    content = (gold_root / "native-01.pdf").read_bytes()
    version = _seed_version(
        session, fixture, file_ref="native-01.pdf", content=content,
        version_id="doc-probe", media_type="application/pdf",
    )
    repo = orr.PageArtifactRepository(session)

    def broken_extract(*args, **kwargs):
        raise RuntimeError("secret-probe-token")

    monkeypatch.setattr(pp, "extract_native_page", broken_extract)
    plan = page_source_document(content=content, media_kind="pdf", source_sha256=sha(content))
    page_input = plan.pages[0]
    assert decide_route(page_input) == ExtractionRoute.VISION_OCR  # 降级，不失败
    artifact = build_page_artifact(
        page_input=page_input,
        source_document_version_id=version.source_document_version_id,
        source_sha256=sha(content),
        artifact_store=artifact_store,
        persist=repo.get_or_create,
    )
    assert artifact.status == PageArtifactStatus.SUCCEEDED  # 扫描页成功
    assert artifact.native_text_sha256 is None
    assert artifact.native_coordinates_sha256 is None
    assert "secret-probe-token" not in (artifact.failure_reason or "")
    assert "RuntimeError" not in (artifact.failure_reason or "")


def test_page_artifact_id_changes_on_renderer_version(
    seeded, artifact_store, gold_root, gold_set
):
    """成功页产物身份包含渲染器版本：版本变化 -> 新 ID（同输入同配置复用）。"""
    session, fixture = seeded
    content = (gold_root / "scanned-01.pdf").read_bytes()
    version = _seed_version(
        session, fixture, file_ref="scanned-01.pdf", content=content,
        version_id="doc-render-v", media_type="application/pdf",
    )
    plan = page_source_document(content=content, media_kind="pdf", source_sha256=sha(content))
    page_input = plan.pages[0]
    a = build_page_artifact(
        page_input=page_input,
        source_document_version_id=version.source_document_version_id,
        source_sha256=sha(content),
        artifact_store=artifact_store,
        renderer_version="slice4.3/render/v1",
    )
    b = build_page_artifact(
        page_input=page_input,
        source_document_version_id=version.source_document_version_id,
        source_sha256=sha(content),
        artifact_store=artifact_store,
        renderer_version="slice4.3/render/v2",
    )
    same = build_page_artifact(
        page_input=page_input,
        source_document_version_id=version.source_document_version_id,
        source_sha256=sha(content),
        artifact_store=artifact_store,
        renderer_version="slice4.3/render/v1",
    )
    assert a.page_artifact_id == same.page_artifact_id
    assert a.page_artifact_id != b.page_artifact_id


def test_page_artifact_id_changes_on_decoder_version(
    seeded, artifact_store, gold_root, gold_set
):
    """成功页产物身份包含解码器版本：变化 -> 新 ID。"""
    session, fixture = seeded
    content = (gold_root / "scanned-01.pdf").read_bytes()
    version = _seed_version(
        session, fixture, file_ref="scanned-01.pdf", content=content,
        version_id="doc-decode-v", media_type="application/pdf",
    )
    plan = page_source_document(content=content, media_kind="pdf", source_sha256=sha(content))
    page_input = plan.pages[0]
    a = build_page_artifact(
        page_input=page_input,
        source_document_version_id=version.source_document_version_id,
        source_sha256=sha(content),
        artifact_store=artifact_store,
        decoder_version="slice4.3/pdfplumber/v1",
    )
    b = build_page_artifact(
        page_input=page_input,
        source_document_version_id=version.source_document_version_id,
        source_sha256=sha(content),
        artifact_store=artifact_store,
        decoder_version="slice4.3/pdfplumber/v2",
    )
    assert a.page_artifact_id != b.page_artifact_id


def test_page_artifact_id_changes_on_transform_version(
    seeded, artifact_store, gold_root, gold_set
):
    """成功页产物身份包含坐标变换版本：变化 -> 新 ID。"""
    session, fixture = seeded
    content = (gold_root / "scanned-01.pdf").read_bytes()
    version = _seed_version(
        session, fixture, file_ref="scanned-01.pdf", content=content,
        version_id="doc-transform-v", media_type="application/pdf",
    )
    plan = page_source_document(content=content, media_kind="pdf", source_sha256=sha(content))
    page_input = plan.pages[0]
    a = build_page_artifact(
        page_input=page_input,
        source_document_version_id=version.source_document_version_id,
        source_sha256=sha(content),
        artifact_store=artifact_store,
        transform_version="slice4.0/v1",
    )
    b = build_page_artifact(
        page_input=page_input,
        source_document_version_id=version.source_document_version_id,
        source_sha256=sha(content),
        artifact_store=artifact_store,
        transform_version="slice4.0/v2",
    )
    assert a.page_artifact_id != b.page_artifact_id


def test_page_artifact_identity_hash_pure_version_sensitivity():
    """纯函数：任一版本变化必然改变身份哈希；同配置稳定复用。"""
    from app.evidence.fingerprint import page_artifact_identity_hash

    base = {
        "source_document_version_id": "doc-1",
        "page_number": 1,
        "original_frame": None,
        "input_sha256": "a" * 64,
        "renderer_version": "render/v1",
        "decoder_version": "decode/v1",
        "coordinate_transform_version": "transform/v1",
    }
    first = page_artifact_identity_hash(**base)
    assert first == page_artifact_identity_hash(**base)
    for field in ("renderer_version", "decoder_version", "coordinate_transform_version"):
        changed = dict(base)
        changed[field] = changed[field] + "-x"
        assert page_artifact_identity_hash(**changed) != first, field


def test_conversion_failure_technical_detail_both_halves(
    seeded, artifact_store, gold_root, gold_set
):
    """技术诊断两半：用户可见原因干净；内部诊断保留在 outcome（非用户可见契约）。"""
    import app.evidence.page_processor as pp

    session, fixture = seeded
    content = (gold_root / "docx-01.docx").read_bytes()
    version = _seed_version(
        session, fixture, file_ref="docx-01.docx", content=content,
        version_id="doc-tech", media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    class SecretRaisingConverter:
        converter_version = "fake/v1"

        def convert_to_pdf(self, content: bytes, *, suffix: str) -> bytes:
            raise RuntimeError("Bearer secret-token-ABC")

    from app.evidence.ocr_adapter import InferenceResult

    def inference(payload, image_bytes):
        return InferenceResult(raw_response=b"RAW", recognized_text="x")

    repo = orr.OcrPageRepository(session)
    outcomes = pp.process_source(
        session=session,
        content=content,
        media_kind="docx",
        source_sha256=sha(content),
        source_document_version_id=version.source_document_version_id,
        artifact_store=artifact_store,
        adapter=None,  # type: ignore[arg-type] - 转换失败页不会触发 OCR
        inference=inference,
        persist_ocr_page=repo.create,
        doc_converter=SecretRaisingConverter(),
    )
    assert len(outcomes) == 1
    artifact = outcomes[0].page_artifact
    assert artifact.status == PageArtifactStatus.FAILED
    assert artifact.failure_reason == "DOCX 转换失败，无法生成可处理页面"
    assert outcomes[0].ocr_page is None
    # 内部诊断保留在 outcome（非用户可见），供 worker_03 技术记录。
    assert outcomes[0].technical_detail is not None
    assert "RuntimeError" in outcomes[0].technical_detail
    assert "secret-token-ABC" in outcomes[0].technical_detail
