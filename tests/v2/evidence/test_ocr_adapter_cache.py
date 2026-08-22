"""OCR 配置指纹与页级缓存适配测试（worker_02）。

验证：任一决定性输入变化产生新指纹/新缓存键；缓存命中不可变且作用域中立但
绝不绕过内容/身份校验（投毒反例）；text-only 冻结路线不产生坐标并携带真实降级
原因；原始请求/响应工件不可变内容寻址落盘；推理失败产出失败 OCRPage。
"""
from __future__ import annotations

import hashlib
import json
from io import BytesIO
from typing import Any

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import update

from app.domain.contracts.enums import (
    ExtractionRoute,
    OcrFailureCategory,
    OCRPageStatus,
)
from app.evidence.ocr_adapter import (
    DEFAULT_REQUEST_PARAMS,
    TEXT_ONLY_DEGRADATION_REASON,
    InferenceResult,
    OcrFailure,
    TextOnlyOcrAdapter,
)
from app.evidence.page_processor import build_page_artifact
from app.evidence.paging import page_source_document
from app.evidence.segmentation import SegmentationConfig
from app.storage import ocr_repositories as orr
from app.storage.codecs import PersistedContractInvalid
from app.storage.evidence_repositories import (
    BlobRepository,
    SourceDocumentRepository,
)
from app.storage.repositories import persist_fixture
from tests.v2.storage.test_repositories_roundtrip import FIXTURES

FIXED = __import__("datetime").datetime(
    2026, 8, 19, 12, 0, 0, tzinfo=__import__("datetime").timezone.utc
)
TRANSFORM = "slice4.0/v1"


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
    from app.evidence.artifacts import ArtifactStore
    from app.storage.config import resolve_data_paths

    return ArtifactStore(resolve_data_paths())


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def make_adapter(**overrides: Any) -> TextOnlyOcrAdapter:
    defaults: dict[str, Any] = {
        "provider": "omlx",
        "model_id": "GLM-OCR-bf16",
        "model_revision": "unknown",
        "parser_version": "slice4.3/text-only/v1",
        "coordinate_transform_version": TRANSFORM,
    }
    defaults.update(overrides)
    return TextOnlyOcrAdapter(**defaults)


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


def _seed_vision_page(session, artifact_store, fixture, *, content, version_id, media_type="application/pdf"):
    """分页+构建并持久化视觉页的 PageArtifact；页图字节从不可变工件库读回。"""
    plan = page_source_document(content=content, media_kind="pdf", source_sha256=sha(content))
    page_input = plan.pages[0]
    version = _seed_version(
        session, fixture, file_ref="scanned-01.pdf", content=content,
        version_id=version_id, media_type=media_type,
    )
    repo = orr.PageArtifactRepository(session)
    artifact = build_page_artifact(
        page_input=page_input,
        source_document_version_id=version.source_document_version_id,
        source_sha256=sha(content),
        artifact_store=artifact_store,
        persist=repo.get_or_create,
    )
    page_image_sha = artifact.page_image_sha256
    assert page_image_sha is not None  # SUCCEEDED 页产物必然携带页图哈希
    # OCR 输入恰好是不可变存储的页图字节（不重渲染）。
    image_bytes = artifact_store.read_by_sha("page_image", page_image_sha)
    assert sha(image_bytes) == page_image_sha
    return artifact, image_bytes, page_image_sha


def make_inference(recognized_text: str = "GLUCOSE 5.6 mmol/L"):
    state = {"calls": 0}

    def inference(payload, image_bytes):
        state["calls"] += 1
        raw = json.dumps(
            {"choices": [{"message": {"content": recognized_text}}], "model": "GLM-OCR-bf16"},
            ensure_ascii=False,
        ).encode("utf-8")
        return InferenceResult(raw_response=raw, recognized_text=recognized_text)

    return inference, state


def dense_page_bytes() -> bytes:
    image = Image.new("RGB", (1000, 3000), "white")
    draw = ImageDraw.Draw(image)
    for y in range(10, 2990, 36):
        draw.rectangle((30, y, 970, y + 18), fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_profile_fingerprint_changes_on_every_deciding_input():
    base = make_adapter()
    assert base.request_params == DEFAULT_REQUEST_PARAMS
    cases = [
        ({"model_id": "other-model"}, "model_id"),
        ({"prompt": "不同提示词"}, "prompt"),
        ({"parser_version": "v2"}, "parser_version"),
        ({"render_params": {"dpi": 300}}, "render_params"),
        ({"request_params": {"max_tokens": 1024}}, "request_params"),
        ({"layout_parser_version": "layout-v2"}, "layout_parser_version"),
        ({"coordinate_transform_version": "t/v2"}, "coordinate_transform_version"),
    ]
    for kwargs, label in cases:
        changed = make_adapter(**kwargs)
        assert changed.profile_fingerprint != base.profile_fingerprint, label
    same = make_adapter()
    assert same.profile_fingerprint == base.profile_fingerprint
    explicit_defaults = make_adapter(request_params=dict(DEFAULT_REQUEST_PARAMS))
    assert explicit_defaults.profile_fingerprint == base.profile_fingerprint
    # 模型修订号参与指纹（unknown 显式冻结）。
    assert make_adapter(model_revision="r1").profile_fingerprint != base.profile_fingerprint
    assert make_adapter(
        segmentation_config=SegmentationConfig(min_page_height=1800)
    ).profile_fingerprint != base.profile_fingerprint


def test_dense_page_request_and_response_preserve_every_segment(
    seeded, artifact_store
):
    session, _fixture = seeded
    image_bytes = dense_page_bytes()
    adapter = make_adapter(
        segmentation_config=SegmentationConfig(min_page_height=1)
    )
    prepared = adapter.prepare(
        session=session,
        artifact_store=artifact_store,
        source_sha256="a" * 64,
        page_number=1,
        page_artifact_id="page-dense",
        page_input_sha256=sha(image_bytes),
        page_image_bytes=image_bytes,
        started_at=FIXED,
    )

    assert prepared.segmentation_plan.dense is True
    assert len(prepared.segments) > 1
    composite_request = json.loads(prepared.request_bytes)
    assert composite_request["schema"] == "phase4_segmented_ocr_request/v1"
    assert len(composite_request["segments"]) == len(prepared.segments)
    for segment in prepared.segments:
        assert artifact_store.read_by_sha(
            "raw_request", segment.request_artifact.sha256
        ) == segment.request_bytes

    calls: list[int] = []

    def inference(payload, _image_bytes):
        index = int(payload["segment"]["index"])
        calls.append(index)
        raw = json.dumps({"segment": index}, ensure_ascii=False).encode("utf-8")
        return InferenceResult(raw_response=raw, recognized_text=f"第{index + 1}段\n")

    recognition = adapter.recognize(
        session=session,
        artifact_store=artifact_store,
        source_sha256="b" * 64,
        page_number=2,
        page_artifact_id="page-dense-recognize",
        page_input_sha256=sha(image_bytes),
        page_image_bytes=image_bytes,
        inference=inference,
        started_at=FIXED,
    )

    assert calls == list(range(len(prepared.segments)))
    expected_bands: list[str] = []
    current_band: tuple[int, int] | None = None
    current_parts: list[str] = []
    for segment in prepared.segments:
        band = (segment.y0, segment.y1)
        if current_band is not None and band != current_band:
            expected_bands.append(" ".join(current_parts))
            current_parts = []
        current_band = band
        current_parts.append(f"第{segment.index + 1}段")
    expected_bands.append(" ".join(current_parts))
    assert recognition.ocr_page.raw_text == "\n".join(expected_bands)
    assert recognition.raw_response_artifact is not None
    composite_response = json.loads(
        artifact_store.read_by_sha(
            "raw_response", recognition.raw_response_artifact.sha256
        )
    )
    assert composite_response["status"] == "succeeded"
    assert len(composite_response["segments"]) == len(calls)


def test_dense_page_partial_failure_preserves_prior_and_failed_raw_responses(
    seeded, artifact_store
):
    session, _fixture = seeded
    image_bytes = dense_page_bytes()
    adapter = make_adapter(
        segmentation_config=SegmentationConfig(min_page_height=1)
    )
    state = {"calls": 0}

    class ProviderFailure(RuntimeError):
        raw_response = b'{"partial":"failed segment"}'

    def inference(payload, _image_bytes):
        index = int(payload["segment"]["index"])
        state["calls"] += 1
        if index == 1:
            raise ProviderFailure("truncated")
        return InferenceResult(
            raw_response=f'{{"segment":{index}}}'.encode(),
            recognized_text=f"第{index + 1}段",
        )

    recognition = adapter.recognize(
        session=session,
        artifact_store=artifact_store,
        source_sha256="c" * 64,
        page_number=3,
        page_artifact_id="page-dense-failure",
        page_input_sha256=sha(image_bytes),
        page_image_bytes=image_bytes,
        inference=inference,
        started_at=FIXED,
    )

    assert state["calls"] == 2
    assert recognition.ocr_page.status == OCRPageStatus.FAILED
    assert recognition.raw_response_artifact is not None
    failure = json.loads(
        artifact_store.read_by_sha(
            "raw_response", recognition.raw_response_artifact.sha256
        )
    )
    assert failure["status"] == "failed"
    assert len(failure["completed_segments"]) == 1
    assert failure["failed_segment"]["index"] == 1
    assert failure["failed_segment"]["raw_response_base64"] is not None


def test_cache_key_changes_on_deciding_input():
    adapter = make_adapter()
    key_a = adapter.cache_key(source_sha256="a" * 64, page_number=1, page_input_sha256="b" * 64)
    assert key_a == adapter.cache_key(source_sha256="a" * 64, page_number=1, page_input_sha256="b" * 64)
    assert key_a != adapter.cache_key(source_sha256="c" * 64, page_number=1, page_input_sha256="b" * 64)
    assert key_a != adapter.cache_key(source_sha256="a" * 64, page_number=2, page_input_sha256="b" * 64)
    assert key_a != adapter.cache_key(source_sha256="a" * 64, page_number=1, page_input_sha256="d" * 64)
    assert key_a != make_adapter(model_id="x").cache_key(
        source_sha256="a" * 64, page_number=1, page_input_sha256="b" * 64
    )
    assert key_a != make_adapter(coordinate_transform_version="t/v2").cache_key(
        source_sha256="a" * 64, page_number=1, page_input_sha256="b" * 64
    )


def test_recognize_persists_and_cache_hits_second_call(
    seeded, artifact_store, gold_root, gold_set
):
    session, fixture = seeded
    content = (gold_root / "scanned-01.pdf").read_bytes()
    artifact, image_bytes, page_image_sha = _seed_vision_page(
        session, artifact_store, fixture, content=content, version_id="doc-v1"
    )
    adapter = make_adapter()
    inference, state = make_inference()
    repo = orr.OcrPageRepository(session)
    first = adapter.recognize(
        session=session, artifact_store=artifact_store,
        source_sha256=sha(content), page_number=1,
        page_artifact_id=artifact.page_artifact_id,
        page_input_sha256=page_image_sha,
        page_image_bytes=image_bytes, inference=inference, persist=repo.create,
    )
    assert first.cached is False
    assert first.ocr_page.status == OCRPageStatus.SUCCEEDED
    assert state["calls"] == 1
    assert first.ocr_page.page_input_sha256 == artifact.page_image_sha256

    second = adapter.recognize(
        session=session, artifact_store=artifact_store,
        source_sha256=sha(content), page_number=1,
        page_artifact_id=artifact.page_artifact_id,
        page_input_sha256=page_image_sha,
        page_image_bytes=image_bytes, inference=inference, persist=repo.create,
    )
    assert second.cached is True
    assert state["calls"] == 1  # 缓存命中不重复推理
    assert second.ocr_page.ocr_page_id == first.ocr_page.ocr_page_id
    # 同一缓存键只有一条成功行。
    assert repo.get_successful_by_cache_key(second.ocr_page.cache_key) is not None


def test_cache_poisoning_drift_is_surfaced_not_bypassed(
    seeded, artifact_store, gold_root, gold_set
):
    session, fixture = seeded
    content = (gold_root / "scanned-01.pdf").read_bytes()
    artifact, image_bytes, page_image_sha = _seed_vision_page(
        session, artifact_store, fixture, content=content, version_id="doc-poison"
    )
    adapter = make_adapter()
    inference, _ = make_inference()
    repo = orr.OcrPageRepository(session)
    rec = adapter.recognize(
        session=session, artifact_store=artifact_store,
        source_sha256=sha(content), page_number=1,
        page_artifact_id=artifact.page_artifact_id,
        page_input_sha256=page_image_sha,
        page_image_bytes=image_bytes, inference=inference, persist=repo.create,
    )
    cache_key = rec.ocr_page.cache_key
    # 投毒：篡改成功行 raw_text 规范化列（漂移）。
    session.execute(
        update(orr.OCRPageRecord)
        .where(orr.OCRPageRecord.cache_key == cache_key)
        .values(raw_text="POISONED")
    )
    session.expire_all()
    # 缓存必须暴露漂移，绝不静默当作命中。
    with pytest.raises(PersistedContractInvalid):
        adapter.cached_page(
            session, cache_key=cache_key, source_sha256=sha(content),
            page_number=1, page_input_sha256=page_image_sha,
        )
    with pytest.raises(PersistedContractInvalid):
        repo.get_successful_by_cache_key(cache_key)


def test_cache_miss_for_different_profile_identity(
    seeded, artifact_store, gold_root, gold_set
):
    session, fixture = seeded
    content = (gold_root / "scanned-01.pdf").read_bytes()
    artifact, image_bytes, page_image_sha = _seed_vision_page(
        session, artifact_store, fixture, content=content, version_id="doc-prof"
    )
    repo = orr.OcrPageRepository(session)
    inference_a, _state_a = make_inference()
    adapter_a = make_adapter()
    adapter_a.recognize(
        session=session, artifact_store=artifact_store,
        source_sha256=sha(content), page_number=1,
        page_artifact_id=artifact.page_artifact_id,
        page_input_sha256=page_image_sha,
        page_image_bytes=image_bytes, inference=inference_a, persist=repo.create,
    )
    # 不同模型 -> 不同指纹 -> 不同缓存键 -> 不命中，需重新推理。
    inference_b, state_b = make_inference(recognized_text="OTHER MODEL TEXT")
    adapter_b = make_adapter(model_id="other-model")
    hit = adapter_b.cached_page(
        session, cache_key=adapter_b.cache_key(
            source_sha256=sha(content), page_number=1, page_input_sha256=page_image_sha
        ),
        source_sha256=sha(content), page_number=1, page_input_sha256=page_image_sha,
    )
    assert hit is None
    rec = adapter_b.recognize(
        session=session, artifact_store=artifact_store,
        source_sha256=sha(content), page_number=1,
        page_artifact_id=artifact.page_artifact_id,
        page_input_sha256=page_image_sha,
        page_image_bytes=image_bytes, inference=inference_b, persist=repo.create,
    )
    assert rec.cached is False
    assert state_b["calls"] == 1
    assert rec.ocr_page.raw_text == "OTHER MODEL TEXT"


def test_cache_is_scope_neutral_by_content_identity(
    seeded, artifact_store, gold_root, gold_set
):
    """同内容同识别配置：不同资料版本共享同一缓存命中（作用域中立）。"""
    session, fixture = seeded
    content = (gold_root / "scanned-01.pdf").read_bytes()
    artifact_v1, image_bytes, page_sha_v1 = _seed_vision_page(
        session, artifact_store, fixture, content=content, version_id="doc-s1"
    )
    adapter = make_adapter()
    repo = orr.OcrPageRepository(session)
    inference, state = make_inference()
    adapter.recognize(
        session=session, artifact_store=artifact_store,
        source_sha256=sha(content), page_number=1,
        page_artifact_id=artifact_v1.page_artifact_id,
        page_input_sha256=page_sha_v1,
        page_image_bytes=image_bytes, inference=inference, persist=repo.create,
    )
    # 第二个资料版本引用同一内容 blob -> 同一页图 -> 同一缓存键。
    _artifact_v2, _image_bytes2, page_sha_v2 = _seed_vision_page(
        session, artifact_store, fixture, content=content, version_id="doc-s2"
    )
    assert page_sha_v2 == page_sha_v1
    hit = adapter.cached_page(
        session, cache_key=adapter.cache_key(
            source_sha256=sha(content), page_number=1, page_input_sha256=page_sha_v2
        ),
        source_sha256=sha(content), page_number=1, page_input_sha256=page_sha_v2,
    )
    assert hit is not None
    assert hit.cache_key == adapter.cache_key(
        source_sha256=sha(content), page_number=1, page_input_sha256=page_sha_v2
    )
    assert state["calls"] == 1


def test_text_only_route_returns_no_coordinates_with_truthful_reason(
    seeded, artifact_store, gold_root, gold_set
):
    session, fixture = seeded
    content = (gold_root / "scanned-01.pdf").read_bytes()
    artifact, image_bytes, page_image_sha = _seed_vision_page(
        session, artifact_store, fixture, content=content, version_id="doc-nobox"
    )
    adapter = make_adapter()
    inference, _ = make_inference("胸部X线检查未见异常。")
    rec = adapter.recognize(
        session=session, artifact_store=artifact_store,
        source_sha256=sha(content), page_number=1,
        page_artifact_id=artifact.page_artifact_id,
        page_input_sha256=page_image_sha,
        page_image_bytes=image_bytes, inference=inference,
    )
    # text-only 冻结路线：无任何 bbox/坐标，且携带真实降级原因（用户可见中文工作措辞）。
    assert rec.degradation_reason == TEXT_ONLY_DEGRADATION_REASON
    assert rec.degradation_reason == "当前文字识别仅提供文本，未返回经验证的页面坐标，因此不显示区域标注"
    for term in ("text-only", "适配器", "OCR", "推理失败", "bbox"):
        assert term not in rec.degradation_reason
    assert rec.ocr_page.raw_text == "胸部X线检查未见异常。"
    assert "bbox" not in rec.ocr_page.raw_text
    # OCRPage 合同不承载 locator/bbox；页产物无原生坐标。
    assert artifact.native_coordinates_sha256 is None
    # Slice 4.3 only stores raw OCR; 4.4 owns risk scanning and activation gates.
    assert rec.ocr_page.risk_items == []


def test_raw_artifacts_immutable_and_content_addressed(
    seeded, artifact_store, gold_root, gold_set
):
    session, fixture = seeded
    content = (gold_root / "scanned-01.pdf").read_bytes()
    artifact, image_bytes, page_image_sha = _seed_vision_page(
        session, artifact_store, fixture, content=content, version_id="doc-raw"
    )
    adapter = make_adapter()
    inference, _ = make_inference()
    rec = adapter.recognize(
        session=session, artifact_store=artifact_store,
        source_sha256=sha(content), page_number=1,
        page_artifact_id=artifact.page_artifact_id,
        page_input_sha256=page_image_sha,
        page_image_bytes=image_bytes, inference=inference,
    )
    assert rec.raw_request_artifact is not None
    assert rec.raw_response_artifact is not None
    # 请求/响应工件分别内容寻址落盘，读回复核一致。
    request_bytes = artifact_store.read(rec.raw_request_artifact.storage_ref)
    assert sha(request_bytes) == rec.raw_request_artifact.sha256
    response_bytes = artifact_store.read(rec.raw_response_artifact.storage_ref)
    assert sha(response_bytes) == rec.raw_response_artifact.sha256
    # 请求载荷含页图 base64 且不含文件名/mtime。
    payload = json.loads(request_bytes)
    assert payload["page"]["source_sha256"] == sha(content)
    assert payload["image"]["sha256"] == artifact.page_image_sha256
    assert "file_name" not in payload
    # 仓储回读原始工件（不可变去重）。
    req_repo = orr.RawOcrRequestArtifactRepository(session)
    got = req_repo.get(rec.raw_request_artifact.raw_request_artifact_id)
    assert got == rec.raw_request_artifact
    resp_repo = orr.RawOcrResponseArtifactRepository(session)
    assert resp_repo.get(rec.raw_response_artifact.raw_response_artifact_id) == rec.raw_response_artifact


def test_inference_failure_produces_failed_ocr_page(
    seeded, artifact_store, gold_root, gold_set
):
    session, fixture = seeded
    content = (gold_root / "scanned-01.pdf").read_bytes()
    artifact, image_bytes, page_image_sha = _seed_vision_page(
        session, artifact_store, fixture, content=content, version_id="doc-fail"
    )
    adapter = make_adapter()
    repo = orr.OcrPageRepository(session)

    def failing(payload, image_bytes_):
        raise RuntimeError("Bearer secret-token-ABC network down")

    rec = adapter.recognize(
        session=session, artifact_store=artifact_store,
        source_sha256=sha(content), page_number=1,
        page_artifact_id=artifact.page_artifact_id,
        page_input_sha256=page_image_sha,
        page_image_bytes=image_bytes, inference=failing, persist=repo.create,
    )
    assert rec.ocr_page.status == OCRPageStatus.FAILED
    assert rec.ocr_page.failure_reason is not None
    # 用户可见稳定中文工作措辞：不泄露异常类型/消息/密钥。
    assert rec.ocr_page.failure_reason == "本页文字识别未完成，请稍后重试"
    assert "推理失败" not in rec.ocr_page.failure_reason
    for secret in ("RuntimeError", "secret-token-ABC", "Bearer", "network"):
        assert secret not in rec.ocr_page.failure_reason
    # 内部技术诊断保留（非用户可见），供 worker_03 技术记录。
    assert rec.technical_detail is not None
    assert "RuntimeError" in rec.technical_detail
    assert "secret-token-ABC" in rec.technical_detail
    # 原始请求工件仍落盘（审计）；无响应工件。
    assert rec.raw_request_artifact is not None
    assert rec.raw_response_artifact is None
    # 失败页可被缓存扫描读取（追加写不可变），但不是成功缓存。
    assert repo.get_successful_by_cache_key(rec.ocr_page.cache_key) is None


def test_prepare_performs_zero_inference(
    seeded, artifact_store, gold_root, gold_set
):
    """阶段 (a)：prepare 零推理 —— 调用即失败；只构建 Profile + 原始请求工件。"""
    session, fixture = seeded
    content = (gold_root / "scanned-01.pdf").read_bytes()
    artifact, image_bytes, page_image_sha = _seed_vision_page(
        session, artifact_store, fixture, content=content, version_id="doc-prep"
    )
    adapter = make_adapter()

    def forbidden(payload, image_bytes_):
        raise AssertionError("prepare 阶段不得调用外部推理")

    prepared = adapter.prepare(
        session=session, artifact_store=artifact_store,
        source_sha256=sha(content), page_number=1,
        page_artifact_id=artifact.page_artifact_id,
        page_input_sha256=page_image_sha,
        page_image_bytes=image_bytes,
    )
    # 零推理：请求工件已内容寻址落盘，Profile 已构建。
    assert prepared.request_artifact is not None
    assert prepared.request_artifact.sha256 == sha(prepared.request_bytes)
    assert artifact_store.read(prepared.request_artifact.storage_ref) == prepared.request_bytes
    # 同一输入 -> 同一请求身份（确定性、可重放检查点）。
    again = adapter.prepare(
        session=session, artifact_store=artifact_store,
        source_sha256=sha(content), page_number=1,
        page_artifact_id=artifact.page_artifact_id,
        page_input_sha256=page_image_sha,
        page_image_bytes=image_bytes,
    )
    assert again.request_artifact.sha256 == prepared.request_artifact.sha256
    assert again.cache_key == prepared.cache_key


def test_finalize_deterministic_content_addressed(
    seeded, artifact_store, gold_root, gold_set
):
    """阶段 (b)：finalize 确定性/内容寻址 —— 同响应字节 -> 同响应哈希/文本。"""
    session, fixture = seeded
    content = (gold_root / "scanned-01.pdf").read_bytes()
    artifact, image_bytes, page_image_sha = _seed_vision_page(
        session, artifact_store, fixture, content=content, version_id="doc-final"
    )
    adapter = make_adapter()
    prepared = adapter.prepare(
        session=session, artifact_store=artifact_store,
        source_sha256=sha(content), page_number=1,
        page_artifact_id=artifact.page_artifact_id,
        page_input_sha256=page_image_sha,
        page_image_bytes=image_bytes,
    )
    result = InferenceResult(
        raw_response=b'{"choices":[{"message":{"content":"GLUCOSE 5.6 mmol/L"}}]}',
        recognized_text="GLUCOSE 5.6 mmol/L",
    )
    first = adapter.finalize_success(
        session=session, artifact_store=artifact_store,
        prepared=prepared, result=result,
    )
    second = adapter.finalize_success(
        session=session, artifact_store=artifact_store,
        prepared=prepared, result=result,
    )
    # 响应工件内容寻址：同一响应字节 -> 同一哈希/引用。
    assert first.raw_response_artifact is not None
    assert second.raw_response_artifact is not None
    assert first.raw_response_artifact.sha256 == second.raw_response_artifact.sha256
    assert first.raw_response_artifact.sha256 == sha(result.raw_response)
    assert first.ocr_page.raw_text == second.ocr_page.raw_text == "GLUCOSE 5.6 mmol/L"
    assert first.ocr_page.cache_key == second.ocr_page.cache_key
    # 失败 finalize：无响应工件；稳定中文原因；失败页内容寻址身份正确。
    failure_rec = adapter.finalize_failure(
        session=session, prepared=prepared,
        failure=OcrFailure(
            category=OcrFailureCategory.NETWORK,
            reason="本页文字识别未完成，请稍后重试",
        ),
    )
    assert failure_rec.ocr_page.status == OCRPageStatus.FAILED
    assert failure_rec.raw_response_artifact is None
    assert failure_rec.raw_request_artifact is not None
    assert failure_rec.raw_request_artifact.sha256 == prepared.request_artifact.sha256

    rejected_response = b'{"model":"wrong-model","choices":[]}'
    failure_with_response = adapter.finalize_failure(
        session=session,
        artifact_store=artifact_store,
        prepared=prepared,
        failure=OcrFailure(
            category=OcrFailureCategory.PROVIDER,
            reason="本页文字识别未完成，请稍后重试",
            raw_response=rejected_response,
        ),
    )
    assert failure_with_response.raw_response_artifact is not None
    assert failure_with_response.raw_response_artifact.sha256 == sha(rejected_response)
    assert artifact_store.read_by_sha("raw_response", sha(rejected_response)) == rejected_response


def test_recognize_is_prepare_plus_inference_plus_finalize(
    seeded, artifact_store, gold_root, gold_set
):
    """recognize 便捷组合与分阶段结果一致（不改变语义）。"""
    session, fixture = seeded
    content = (gold_root / "scanned-01.pdf").read_bytes()
    artifact, image_bytes, page_image_sha = _seed_vision_page(
        session, artifact_store, fixture, content=content, version_id="doc-wrap"
    )
    adapter = make_adapter()
    prepared = adapter.prepare(
        session=session, artifact_store=artifact_store,
        source_sha256=sha(content), page_number=1,
        page_artifact_id=artifact.page_artifact_id,
        page_input_sha256=page_image_sha,
        page_image_bytes=image_bytes,
    )
    result = InferenceResult(raw_response=b"RAW", recognized_text="HELLO 5.6 mmol/L")
    staged = adapter.finalize_success(
        session=session, artifact_store=artifact_store,
        prepared=prepared, result=result,
    )
    inference, state = make_inference("HELLO 5.6 mmol/L")
    wrapped = adapter.recognize(
        session=session, artifact_store=artifact_store,
        source_sha256=sha(content), page_number=1,
        page_artifact_id=artifact.page_artifact_id,
        page_input_sha256=page_image_sha,
        page_image_bytes=image_bytes, inference=inference,
    )
    assert state["calls"] == 1
    assert wrapped.ocr_page.raw_text == staged.ocr_page.raw_text == "HELLO 5.6 mmol/L"
    assert wrapped.raw_request_artifact is not None
    assert staged.raw_request_artifact is not None
    assert wrapped.raw_request_artifact.sha256 == staged.raw_request_artifact.sha256


def test_process_source_renders_once_and_passes_exact_stored_bytes(
    seeded, artifact_store, gold_root, gold_set, monkeypatch
):
    """process_source 只渲染一次；OCR 输入 = 不可变存储页图字节（== page_input_sha256）。"""
    import app.evidence.page_processor as pp

    session, fixture = seeded
    content = (gold_root / "scanned-01.pdf").read_bytes()
    from app.domain.contracts.enums import (
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
    from app.domain.publication import evidence_snapshot_collection_hash
    from app.storage.evidence_repositories import EvidenceSnapshotRepository

    project_id, subject_id, episode_id = _scope(fixture)
    blob = SourceBlob(
        source_blob_id=sha(content), sha256=sha(content), byte_size=len(content),
        media_type="application/pdf", storage_ref=f"blobs/{sha(content)}",
        created_at=FIXED,
    )
    BlobRepository(session).get_or_create_by_sha256(blob)
    version = SourceDocumentVersion(
        source_document_version_id="doc-e2e",
        logical_document_id="log-e2e",
        source_blob_sha256=blob.sha256,
        file_name="scanned-01.pdf",
        media_type="application/pdf",
        page_count=None,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        version_number=1,
        created_at=FIXED,
        created_by="tester",
    )
    SourceDocumentRepository(session).create_version(version)
    member = EvidenceSnapshotMember(
        member_id="snap-e2e-log-e2e",
        snapshot_id="snap-e2e",
        logical_document_id="log-e2e",
        source_document_version_id=version.source_document_version_id,
        origin=SnapshotMemberOrigin.ADDED,
    )
    snapshot = EvidenceSnapshot(
        evidence_snapshot_id="snap-e2e",
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        members=[member],
        collection_sha256=evidence_snapshot_collection_hash(
            members=[(member.logical_document_id, member.source_document_version_id)]
        ),
        status=SnapshotStatus.STAGED,
        created_at=FIXED,
        created_by="tester",
    )
    EvidenceSnapshotRepository(session).create_full(snapshot)
    EvidenceSnapshotRepository(session).transition_status(
        "snap-e2e", event="worker_start", new_status=SnapshotStatus.PROCESSING,
        actor="tester", reason="start",
    )
    session.flush()

    adapter = make_adapter()
    repo = orr.OcrPageRepository(session)
    captured: dict[str, bytes] = {}

    def inference(payload, image_bytes):
        captured["image_bytes"] = image_bytes
        raw = json.dumps({"choices": [{"message": {"content": "GLUCOSE 5.6 mmol/L"}}]}).encode()
        return InferenceResult(raw_response=raw, recognized_text="GLUCOSE 5.6 mmol/L")

    real_render = pp.render_page_image
    calls = {"count": 0}

    def counting_render(page_input, **kwargs):
        calls["count"] += 1
        return real_render(page_input, **kwargs)

    monkeypatch.setattr(pp, "render_page_image", counting_render)

    outcomes = pp.process_source(
        session=session,
        content=content,
        media_kind="pdf",
        source_sha256=sha(content),
        source_document_version_id=version.source_document_version_id,
        artifact_store=artifact_store,
        adapter=adapter,
        inference=inference,
        persist_ocr_page=repo.create,
    )
    # 一页视觉页：页产物渲染一次，OCR 不再重渲染。
    assert calls["count"] == 1
    assert len(outcomes) == 1
    artifact = outcomes[0].page_artifact
    ocr_page = outcomes[0].ocr_page
    assert ocr_page is not None
    assert ocr_page.status == OCRPageStatus.SUCCEEDED
    # OCR 输入恰好是存储页图字节，哈希 == OCRPage.page_input_sha256 == 页产物页图哈希。
    stored = artifact_store.read_by_sha("page_image", artifact.page_image_sha256)
    assert captured["image_bytes"] == stored
    assert ocr_page.page_input_sha256 == artifact.page_image_sha256 == sha(stored)


def test_process_source_txt_route_is_decided_once(
    artifact_store, gold_root, gold_set, monkeypatch
):
    """TXT 的 SOURCE_TEXT 路线只决定一次，且不调用外部视觉识别。"""
    import app.evidence.page_processor as pp

    content = (gold_root / "txt-01.txt").read_bytes()
    calls = {"count": 0}
    real_decide = pp.decide_route_detailed

    def counting_decide(page_input):
        calls["count"] += 1
        return real_decide(page_input)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("TXT 不应调用文字识别")

    monkeypatch.setattr(pp, "decide_route_detailed", counting_decide)
    outcomes = pp.process_source(
        session=None,
        content=content,
        media_kind="text",
        source_sha256=sha(content),
        source_document_version_id="doc-txt-route-once",
        artifact_store=artifact_store,
        adapter=make_adapter(),
        inference=forbidden,
        persist_ocr_page=forbidden,
        persist_page_artifact=lambda artifact: artifact,
    )
    assert calls["count"] == 1
    assert outcomes[0].route == ExtractionRoute.SOURCE_TEXT
    assert outcomes[0].ocr_page is None
    assert outcomes[0].page_artifact.native_text_sha256 is not None


def test_process_source_end_to_end_revision_freeze(
    seeded, artifact_store, gold_root, gold_set
):
    """端到端：process_source 产物 + OCRPage 冻结为不可变证据处理修订（闭包校验通过）。"""
    import app.evidence.page_processor as pp
    from app.domain.contracts.enums import (
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
    )
    from app.domain.publication import (
        evidence_processing_manifest_hash,
        evidence_snapshot_collection_hash,
    )
    from app.storage.evidence_repositories import EvidenceSnapshotRepository

    session, fixture = seeded
    content = (gold_root / "scanned-01.pdf").read_bytes()
    project_id, subject_id, episode_id = _scope(fixture)
    blob = SourceBlob(
        source_blob_id=sha(content), sha256=sha(content), byte_size=len(content),
        media_type="application/pdf", storage_ref=f"blobs/{sha(content)}",
        created_at=FIXED,
    )
    BlobRepository(session).get_or_create_by_sha256(blob)
    version = SourceDocumentVersion(
        source_document_version_id="doc-freeze",
        logical_document_id="log-freeze",
        source_blob_sha256=blob.sha256,
        file_name="scanned-01.pdf",
        media_type="application/pdf",
        page_count=None,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        version_number=1,
        created_at=FIXED,
        created_by="tester",
    )
    SourceDocumentRepository(session).create_version(version)
    member = EvidenceSnapshotMember(
        member_id="snap-freeze-log",
        snapshot_id="snap-freeze",
        logical_document_id="log-freeze",
        source_document_version_id=version.source_document_version_id,
        origin=SnapshotMemberOrigin.ADDED,
    )
    snapshot = EvidenceSnapshot(
        evidence_snapshot_id="snap-freeze",
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        members=[member],
        collection_sha256=evidence_snapshot_collection_hash(
            members=[(member.logical_document_id, member.source_document_version_id)]
        ),
        status=SnapshotStatus.STAGED,
        created_at=FIXED,
        created_by="tester",
    )
    EvidenceSnapshotRepository(session).create_full(snapshot)
    EvidenceSnapshotRepository(session).transition_status(
        "snap-freeze", event="worker_start", new_status=SnapshotStatus.PROCESSING,
        actor="tester", reason="start",
    )
    session.flush()

    adapter = make_adapter()
    repo = orr.OcrPageRepository(session)

    def inference(payload, image_bytes):
        raw = json.dumps({"choices": [{"message": {"content": "GLUCOSE 5.6 mmol/L"}}]}).encode()
        return InferenceResult(raw_response=raw, recognized_text="GLUCOSE 5.6 mmol/L")

    outcomes = pp.process_source(
        session=session,
        content=content,
        media_kind="pdf",
        source_sha256=sha(content),
        source_document_version_id=version.source_document_version_id,
        artifact_store=artifact_store,
        adapter=adapter,
        inference=inference,
        persist_ocr_page=repo.create,
    )
    assert len(outcomes) == 1
    artifact = outcomes[0].page_artifact
    ocr_page = outcomes[0].ocr_page
    assert ocr_page is not None
    assert artifact.status == PageArtifactStatus.SUCCEEDED

    entry = EvidenceProcessingRevisionPage(
        entry_id="freeze-entry-1",
        position=1,
        source_document_version_id=version.source_document_version_id,
        page_number=1,
        original_frame=None,
        page_artifact_id=artifact.page_artifact_id,
        ocr_page_id=ocr_page.ocr_page_id,
        status=PageArtifactStatus.SUCCEEDED,
    )
    revision = EvidenceProcessingRevision(
        evidence_processing_revision_id="rev-freeze",
        evidence_snapshot_id="snap-freeze",
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        manifest=[entry],
        manifest_sha256=evidence_processing_manifest_hash(
            entries=[
                (
                    entry.source_document_version_id,
                    entry.page_number,
                    entry.original_frame,
                    entry.page_artifact_id,
                    entry.ocr_page_id,
                    entry.status.value,
                )
            ]
        ),
        status=ProcessingRevisionStatus.READY,
        is_activatable=False,
        created_at=FIXED,
        created_by="tester",
    )
    # worker_01 闭包校验通过：ocr_page.page_input_sha256 == 页产物页图哈希。
    revision_repo = orr.EvidenceProcessingRevisionRepository(session)
    frozen = revision_repo.create(revision)
    got = revision_repo.get(frozen.evidence_processing_revision_id)
    assert got.manifest[0].page_artifact_id == artifact.page_artifact_id
    assert got.manifest[0].ocr_page_id == ocr_page.ocr_page_id
    assert got.is_activatable is False
    # 失败页绝不绑定 OCRPage：corrupt PDF 的产物无 OCR 页。
    corrupt = (gold_root / "corrupt-01.pdf").read_bytes()
    corrupt_blob = SourceBlob(
        source_blob_id=sha(corrupt), sha256=sha(corrupt), byte_size=len(corrupt),
        media_type="application/pdf", storage_ref=f"blobs/{sha(corrupt)}",
        created_at=FIXED,
    )
    BlobRepository(session).get_or_create_by_sha256(corrupt_blob)
    corrupt_version = SourceDocumentVersion(
        source_document_version_id="doc-freeze-corrupt",
        logical_document_id="log-freeze-corrupt",
        source_blob_sha256=corrupt_blob.sha256,
        file_name="corrupt-01.pdf",
        media_type="application/pdf",
        page_count=None,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        version_number=1,
        created_at=FIXED,
        created_by="tester",
    )
    SourceDocumentRepository(session).create_version(corrupt_version)
    corrupt_outcomes = pp.process_source(
        session=session,
        content=corrupt,
        media_kind="pdf",
        source_sha256=sha(corrupt),
        source_document_version_id=corrupt_version.source_document_version_id,
        artifact_store=artifact_store,
        adapter=adapter,
        inference=inference,
        persist_ocr_page=repo.create,
    )
    assert corrupt_outcomes[0].page_artifact.status == PageArtifactStatus.FAILED
    assert corrupt_outcomes[0].ocr_page is None


def test_process_source_decides_route_once_and_extraction_failure_still_ocrs(
    seeded, artifact_store, gold_root, gold_set, monkeypatch
):
    """路线每页只探测一次；原生提取失败 -> 最终路线降级为视觉识别，页必有 OCR。

    有状态反例：第一次 ``extract_native_page``（路线探测）成功 -> 原生路线；
    第二次（页产物原生提取）失败。必须：探测仅一次、最终生效路线为 VISION、
    该页仍产生 OCRPage（绝不「既无原生文本又无 OCR」）、内部技术诊断保留。
    """
    import app.evidence.page_processor as pp
    from app.domain.contracts.enums import ExtractionRoute, PageArtifactStatus
    from app.domain.contracts.evidence_ingestion import (
        SourceBlob,
        SourceDocumentVersion,
    )

    session, fixture = seeded
    content = (gold_root / "native-01.pdf").read_bytes()
    project_id, subject_id, episode_id = _scope(fixture)
    blob = SourceBlob(
        source_blob_id=sha(content), sha256=sha(content), byte_size=len(content),
        media_type="application/pdf", storage_ref=f"blobs/{sha(content)}",
        created_at=FIXED,
    )
    BlobRepository(session).get_or_create_by_sha256(blob)
    version = SourceDocumentVersion(
        source_document_version_id="doc-route",
        logical_document_id="log-route",
        source_blob_sha256=blob.sha256,
        file_name="native-01.pdf",
        media_type="application/pdf",
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

    real_extract = pp.extract_native_page
    probe_counts = {"decide_route_detailed": 0}
    real_decide_detailed = pp.decide_route_detailed
    state = {"extract_calls": 0}

    def counting_decide(page_input):
        probe_counts["decide_route_detailed"] += 1
        return real_decide_detailed(page_input)

    def stateful_extract(source, index):
        # 第 1 次调用（路线探测）成功 -> 原生路线；后续调用（原生提取）失败。
        state["extract_calls"] += 1
        if state["extract_calls"] == 1:
            return real_extract(source, index)
        raise RuntimeError("transient-native-extraction-failure")

    monkeypatch.setattr(pp, "extract_native_page", stateful_extract)
    monkeypatch.setattr(pp, "decide_route_detailed", counting_decide)

    adapter = make_adapter()
    repo = orr.OcrPageRepository(session)

    def inference(payload, image_bytes):
        raw = json.dumps({"choices": [{"message": {"content": "GLUCOSE 5.6 mmol/L"}}]}).encode()
        return InferenceResult(raw_response=raw, recognized_text="GLUCOSE 5.6 mmol/L")

    outcomes = pp.process_source(
        session=session,
        content=content,
        media_kind="pdf",
        source_sha256=sha(content),
        source_document_version_id=version.source_document_version_id,
        artifact_store=artifact_store,
        adapter=adapter,
        inference=inference,
        persist_ocr_page=repo.create,
    )
    # 三页：路线探测恰好每页一次（不再二次探测）。
    assert probe_counts["decide_route_detailed"] == 3
    for outcome in outcomes:
        artifact = outcome.page_artifact
        # 原生提取失败 -> 最终生效路线 VISION；该页仍产生 OCRPage。
        assert outcome.route == ExtractionRoute.VISION_OCR
        assert outcome.ocr_page is not None
        assert outcome.ocr_page.status == OCRPageStatus.SUCCEEDED
        # 页产物无原生文本（提取失败），但有页图供 OCR。
        assert artifact.native_text_sha256 is None
        assert artifact.page_image_sha256 is not None
        assert artifact.status == PageArtifactStatus.SUCCEEDED
        # 内部技术诊断保留；用户可见失败文本为空（成功页）。
        assert outcome.technical_detail is not None
        assert "transient-native-extraction-failure" in outcome.technical_detail
