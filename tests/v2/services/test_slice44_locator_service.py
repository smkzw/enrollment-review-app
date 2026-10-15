"""Slice 4.4 occurrence-aware 定位服务测试（WP-44B）。

覆盖 §8.1 定位诚实性：raw_ocr text-only 路线绝不输出 bbox；原生文本有同源坐标
sidecar 才允许 authenticated bbox；重复文本降级 page_excerpt；未找到 page_only；
有效文本定位绑定完整修订投影哈希。
"""
from __future__ import annotations

import pytest

from app.domain.contracts.enums import (
    DisambiguationOutcome,
    LocatorAuthenticity,
    LocatorPrecision,
    LocatorSourceLayer,
)
from app.evidence.effective_text import project_effective_text
from app.services.evidence_correction_service import EvidenceCorrectionService
from app.services.evidence_locator_service import (
    EvidenceLocatorService,
    LocatorRequest,
)
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository,
    EvidenceLocatorRepository,
)
from app.storage.ocr_repositories import OcrPageRepository
from tests.v2.storage.test_slice44_repositories import (
    RAW_TEXT,
    _closed_revision,
    _seed_native_page,
    sha,
)


@pytest.fixture
def stack(revision_stack):
    session, fixture, keys = revision_stack
    session.commit()
    return session, fixture, keys

def _raw_request(keys, *, text_start=4, text_end=7, excerpt="5.6", **overrides):
    base = {
        "page_artifact_id": "pa-1",
        "ocr_page_id": "op-1",
        "source_layer": LocatorSourceLayer.RAW_OCR,
        "source_text_sha256": sha(RAW_TEXT.encode("utf-8")),
        "target_id": "t-1",
        "target_text_start": text_start,
        "target_text_end": text_end,
        "excerpt": excerpt,
    }
    base.update(overrides)
    return LocatorRequest(**base)

def test_raw_ocr_text_range_locator(stack, session_factory):
    _session, _fixture, keys = stack
    service = EvidenceLocatorService(session_factory)
    locator = service.create_locator(_raw_request(keys))
    assert locator.source_layer == LocatorSourceLayer.RAW_OCR
    assert locator.precision == LocatorPrecision.TEXT_RANGE
    assert locator.authenticity == LocatorAuthenticity.DEGRADED
    assert (locator.text_start, locator.text_end) == (4, 7)
    assert locator.degradation_reason
    # 回读仍通过同源回放校验。
    with session_factory() as fresh:
        got = EvidenceLocatorRepository(fresh).get(locator.locator_id)
        assert got.precision == LocatorPrecision.TEXT_RANGE

def test_raw_ocr_never_bbox(stack, session_factory):
    _session, _fixture, keys = stack
    service = EvidenceLocatorService(session_factory)
    locator = service.create_locator(_raw_request(keys))
    assert locator.precision != LocatorPrecision.BBOX
    assert locator.bbox is None
    assert locator.coordinate_frame is None

def test_raw_ocr_repeated_text_degrades_to_page_excerpt(stack, session_factory):
    _session, _fixture, keys = stack
    # op-1 原文 "ALT 5.6 mmol/L 且 AST 3.5 mmol/L"：'3.5' 唯一，用 'ALT' 出现一次。
    service = EvidenceLocatorService(session_factory)
    locator = service.create_locator(
        _raw_request(keys, excerpt="ALT", text_start=None, text_end=None)
    )
    assert locator.precision == LocatorPrecision.TEXT_RANGE
    assert "未返回经验证的页面坐标" in (locator.degradation_reason or "")
    assert not any(
        term in (locator.degradation_reason or "")
        for term in ("text-only", "sidecar", "bbox", "raw_ocr")
    )
    # 构造含重复文本的新 OCR 页 → 只给字符串必须降级。
    with session_factory() as s, s.begin():
        from app.storage.ocr_repositories import (
            OCRProfileRepository,
            PageArtifactRepository,
        )
        from tests.v2.storage.test_ocr_repositories import (
            make_artifact,
            make_ocr_page,
            make_profile,
        )

        profile = OCRProfileRepository(s).get_or_create(make_profile())
        PageArtifactRepository(s).get_or_create(
            make_artifact(artifact_id="pa-rep", version_id="doc-1", page_input="7" * 64)
        )
        OcrPageRepository(s).create(
            make_ocr_page(
                page_id="op-rep", artifact_id="pa-rep",
                raw_text="AST 3.5 且 AST 3.5", page_input="7" * 64,
                profile_sha=profile.profile_sha256,
            )
        )
    locator2 = service.create_locator(
        LocatorRequest(
            page_artifact_id="pa-rep", ocr_page_id="op-rep",
            source_layer=LocatorSourceLayer.RAW_OCR,
            source_text_sha256=sha("AST 3.5 且 AST 3.5".encode()),
            target_id="t-rep", excerpt="AST",
        )
    )
    assert locator2.precision == LocatorPrecision.PAGE_EXCERPT
    assert locator2.disambiguation == DisambiguationOutcome.REPEATED_TEXT_DEGRADED
    assert "多处相同文本" in (locator2.degradation_reason or "")

def test_native_bbox_requires_sidecar_and_succeeds(stack, session_factory, artifact_store):
    session, _fixture, keys = stack
    _seed_native_page(session, keys, artifact_store)
    session.commit()
    service = EvidenceLocatorService(session_factory, artifact_store)
    locator = service.create_locator(
        LocatorRequest(
            page_artifact_id="pa-native", ocr_page_id="op-native",
            source_layer=LocatorSourceLayer.NATIVE_TEXT,
            source_text_sha256=sha(RAW_TEXT.encode("utf-8")),
            target_id="t-bbox", target_text_start=4, target_text_end=7, excerpt="5.6",
        )
    )
    assert locator.precision == LocatorPrecision.BBOX
    assert locator.authenticity == LocatorAuthenticity.AUTHENTICATED
    assert locator.sidecar_sha256 == keys["native_coords_sha"]
    assert locator.bbox is not None
    assert locator.coordinate_frame is not None
    assert locator.coordinate_frame.space.value == "page_image_pixels"
    assert locator.coordinate_frame.page_width == 595.0
    assert locator.coordinate_frame.page_height == 842.0
    # 原生 PDF points 原点在左下；浏览器页图原点在左上。不能把两者混为同一坐标。
    assert locator.bbox.model_dump() == {
        "x0": 30.0,
        "y0": 782.0,
        "x1": 45.0,
        "y1": 792.0,
    }

def test_native_text_without_coordinates_degrades(stack, session_factory, artifact_store):
    """原生文本工件存在但页产物无坐标 sidecar → 诚实降级 text_range，不生成伪框。"""
    _session, _fixture, _keys = stack
    # 直接构造：原生文本工件 + 无坐标 sidecar 的页产物。
    native = RAW_TEXT.encode("utf-8")
    text_sha = sha(native)
    from app.storage.ocr_repositories import PageArtifactRepository
    from tests.v2.storage.test_ocr_repositories import make_artifact

    artifact_store.put("native_text", native)
    with session_factory() as s, s.begin():
        PageArtifactRepository(s).get_or_create(
            make_artifact(
                artifact_id="pa-notex", version_id="doc-1", page_number=1,
                page_input="5" * 64, native_text_sha256=text_sha,
                native_coordinates_sha256=None,
            )
        )
    service = EvidenceLocatorService(session_factory, artifact_store)
    locator = service.create_locator(
        LocatorRequest(
            page_artifact_id="pa-notex", source_layer=LocatorSourceLayer.NATIVE_TEXT,
            source_text_sha256=text_sha, target_id="t-nt",
            target_text_start=4, target_text_end=7, excerpt="5.6",
        )
    )
    assert locator.precision == LocatorPrecision.TEXT_RANGE
    assert locator.authenticity == LocatorAuthenticity.DEGRADED
    assert locator.bbox is None

def test_effective_text_locator_binds_revision_projection(stack, session_factory):
    session, _fixture, keys = stack
    corr_service = EvidenceCorrectionService(session_factory)
    corr = corr_service.create_correction(
        ocr_page_id="op-1", text_start=4, text_end=7, original_text="5.6",
        corrected_text="5.60", change_kind="decimal", reason="r", actor="u",
        base_processing_revision_id="rev-1",
        confirmation_actor="reviewer", confirmation_at="2026-08-19T12:00:00+00:00",
    )
    revision = _closed_revision(keys, session, correction_ids=[corr.correction_id])
    created = CompleteEvidenceProcessingRevisionRepository(session).create(revision)
    session.commit()

    projection = project_effective_text(RAW_TEXT, [corr])
    assert created.evidence_processing_revision_id
    service = EvidenceLocatorService(session_factory)
    locator = service.create_locator(
        LocatorRequest(
            page_artifact_id="pa-1", ocr_page_id="op-1",
            source_layer=LocatorSourceLayer.EFFECTIVE_TEXT,
            source_text_sha256=projection.effective_text_sha256,
            target_id="t-eff",
            target_text_start=4, target_text_end=9,
            excerpt=projection.effective_text[4:9],
            processing_revision_id=created.evidence_processing_revision_id,
            effective_text_sha256=projection.effective_text_sha256,
        )
    )
    assert locator.source_layer == LocatorSourceLayer.EFFECTIVE_TEXT
    assert locator.precision == LocatorPrecision.TEXT_RANGE
    assert locator.processing_revision_id == created.evidence_processing_revision_id
    # 校对后文本没有可验证的页内坐标时不输出伪框，用户说明不含工程术语。
    assert locator.bbox is None
    assert "无法可靠映射到原件区域" in (locator.degradation_reason or "")
    assert not any(
        term in (locator.degradation_reason or "")
        for term in ("text-only", "sidecar", "bbox", "effective_text")
    )

def test_effective_text_locator_rejects_wrong_hash(stack, session_factory):
    session, _fixture, keys = stack
    from app.services.evidence_locator_service import LocatorInputError

    corr_service = EvidenceCorrectionService(session_factory)
    corr = corr_service.create_correction(
        ocr_page_id="op-1", text_start=4, text_end=7, original_text="5.6",
        corrected_text="5.60", change_kind="decimal", reason="r", actor="u",
        base_processing_revision_id="rev-1",
        confirmation_actor="reviewer", confirmation_at="2026-08-19T12:00:00+00:00",
    )
    revision = _closed_revision(keys, session, correction_ids=[corr.correction_id])
    created = CompleteEvidenceProcessingRevisionRepository(session).create(revision)
    session.commit()

    service = EvidenceLocatorService(session_factory)
    with pytest.raises(LocatorInputError, match="投影重算结果不一致"):
        service.create_locator(
            LocatorRequest(
                page_artifact_id="pa-1", ocr_page_id="op-1",
                source_layer=LocatorSourceLayer.EFFECTIVE_TEXT,
                source_text_sha256="b" * 64, target_id="t-bad",
                processing_revision_id=created.evidence_processing_revision_id,
                effective_text_sha256="c" * 64,
            )
        )
