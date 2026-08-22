"""Phase 4 OCR/证据合同冻结测试（Slice 4.0）。"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.contracts.enums import (
    CoordinateSpace,
    DisambiguationOutcome,
    ExtractionRoute,
    LocatorPrecision,
    OCRPageStatus,
    OcrRiskKind,
    OcrRiskLevel,
    PageArtifactStatus,
)
from app.domain.contracts.evidence import BoundingBox
from app.domain.contracts.ocr import (
    CoordinateFrame,
    LocatorResult,
    OCRPage,
    OCRProfile,
    OcrRiskFlag,
    PageArtifact,
    PageQualityMetrics,
    RawOcrRequestArtifact,
    RawOcrResponseArtifact,
)
from app.evidence.fingerprint import build_ocr_cache_key, build_profile_fingerprint

_T = "slice4.0/v1"
_ts = datetime(2026, 8, 19, 8, 0, 0, tzinfo=UTC)


def _frame(**overrides) -> CoordinateFrame:
    values: dict[str, Any] = {
        "space": CoordinateSpace.PDF_POINTS,
        "page_width": 595.0,
        "page_height": 842.0,
        "rotation": 0,
        "transform_version": _T,
    }
    values.update(overrides)
    return CoordinateFrame(**values)


def _page_artifact(**overrides) -> PageArtifact:
    values: dict[str, Any] = {
        "page_artifact_id": "page-1",
        "source_document_version_id": "doc-1",
        "page_number": 1,
        "source_sha256": "a" * 64,
        "page_input_sha256": "b" * 64,
        "page_image_sha256": "c" * 64,
        "page_width": 595.0,
        "page_height": 842.0,
        "rotation": 0,
        "renderer_version": "render/v1",
        "decoder_version": "decode/v1",
        "derivative_sha256": "d" * 64,
        "coordinate_transform_version": _T,
        "status": PageArtifactStatus.SUCCEEDED,
    }
    values.update(overrides)
    return PageArtifact(**values)


def _profile(**overrides) -> OCRProfile:
    base: dict[str, Any] = {
        "ocr_profile_id": "profile-1",
        "extraction_route": ExtractionRoute.VISION_OCR,
        "provider": "omlx",
        "model_id": "GLM-OCR-bf16",
        "model_revision": "unknown",
        "parser_version": "v1",
        "coordinate_transform_version": _T,
    }
    base.update(overrides)
    base["profile_sha256"] = build_profile_fingerprint(
        extraction_route=base["extraction_route"].value if isinstance(base["extraction_route"], ExtractionRoute) else base["extraction_route"],
        provider=base["provider"],
        model_id=base["model_id"],
        model_revision=base["model_revision"],
        prompt_sha256=base.get("prompt_sha256"),
        parser_version=base["parser_version"],
        render_params_sha256=base.get("render_params_sha256"),
        request_params_sha256=base.get("request_params_sha256"),
        layout_parser_version=base.get("layout_parser_version"),
        coordinate_transform_version=base["coordinate_transform_version"],
    )
    base.setdefault("created_at", _ts)
    return OCRProfile(**base)


# ---------------------------------------------------------------------------
# CoordinateFrame
# ---------------------------------------------------------------------------


def test_coordinate_frame_rejects_invalid_rotation() -> None:
    with pytest.raises(ValidationError, match="旋转"):
        _frame(rotation=45)


def test_coordinate_frame_accepts_pdf_and_image_spaces() -> None:
    assert _frame().space == CoordinateSpace.PDF_POINTS
    assert _frame(space=CoordinateSpace.PAGE_IMAGE_PIXELS).space == CoordinateSpace.PAGE_IMAGE_PIXELS


# ---------------------------------------------------------------------------
# PageArtifact
# ---------------------------------------------------------------------------


def test_page_artifact_succeeded_requires_image_and_no_failure() -> None:
    _page_artifact()
    with pytest.raises(ValidationError, match="页图内容哈希"):
        _page_artifact(page_image_sha256=None)
    with pytest.raises(ValidationError, match="失败原因"):
        _page_artifact(failure_reason="x")


def test_page_artifact_failed_requires_reason() -> None:
    with pytest.raises(ValidationError, match="失败原因"):
        _page_artifact(status=PageArtifactStatus.FAILED)
    _page_artifact(
        status=PageArtifactStatus.FAILED,
        page_image_sha256=None,
        failure_reason="无法解码页",
    )


def test_page_artifact_failed_all_unknown_fields_none() -> None:
    """失败页：无真实页输入/几何/页图，全部为 None，不得用伪值填充。"""
    failed = _page_artifact(
        status=PageArtifactStatus.FAILED,
        failure_reason="整文件无法分页",
        page_input_sha256=None,
        page_image_sha256=None,
        page_width=None,
        page_height=None,
        rotation=None,
        renderer_version=None,
        decoder_version=None,
    )
    assert failed.page_input_sha256 is None
    assert failed.page_width is None
    assert failed.page_height is None
    assert failed.rotation is None
    assert failed.page_image_sha256 is None


def test_page_artifact_succeeded_requires_real_geometry() -> None:
    """成功页：缺少真实页输入哈希/页宽/页高/旋转任一即拒绝。"""
    with pytest.raises(ValidationError, match="页图输入哈希"):
        _page_artifact(page_input_sha256=None)
    with pytest.raises(ValidationError, match="页宽与页高"):
        _page_artifact(page_width=None)
    with pytest.raises(ValidationError, match="页宽与页高"):
        _page_artifact(page_height=None)
    with pytest.raises(ValidationError, match="页面旋转"):
        _page_artifact(rotation=None)
    with pytest.raises(ValidationError, match="渲染与解码版本"):
        _page_artifact(renderer_version=None)
    with pytest.raises(ValidationError, match="渲染与解码版本"):
        _page_artifact(decoder_version=None)
    with pytest.raises(ValidationError, match="页图内容哈希"):
        _page_artifact(page_image_sha256=None)


def test_page_artifact_degraded_requires_real_geometry() -> None:
    """降级页：与成功页一样必须携带真实几何与页图哈希，且必须说明降级原因。"""
    with pytest.raises(ValidationError, match="降级原因"):
        _page_artifact(status=PageArtifactStatus.DEGRADED)
    with pytest.raises(ValidationError, match="页图输入哈希"):
        _page_artifact(
            status=PageArtifactStatus.DEGRADED,
            failure_reason="部分文本丢失",
            page_input_sha256=None,
        )
    with pytest.raises(ValidationError, match="页宽与页高"):
        _page_artifact(
            status=PageArtifactStatus.DEGRADED,
            failure_reason="部分文本丢失",
            page_width=None,
        )
    with pytest.raises(ValidationError, match="页面旋转"):
        _page_artifact(
            status=PageArtifactStatus.DEGRADED,
            failure_reason="部分文本丢失",
            rotation=None,
        )
    ok = _page_artifact(
        status=PageArtifactStatus.DEGRADED,
        failure_reason="部分文本丢失",
    )
    assert ok.status == PageArtifactStatus.DEGRADED


def test_page_artifact_native_text_without_coordinates_allowed() -> None:
    """原生文本可单独存在（如 TXT 无空间坐标），不得伪造坐标。"""
    artifact = _page_artifact(
        native_text_sha256="e" * 64,
        native_coordinates_sha256=None,
    )
    assert artifact.native_text_sha256 == "e" * 64
    assert artifact.native_coordinates_sha256 is None


def test_page_artifact_coordinates_without_text_rejected() -> None:
    """坐标哈希绝不允许在没有文本哈希时存在。"""
    with pytest.raises(ValidationError, match="不得伪造坐标"):
        _page_artifact(
            native_text_sha256=None,
            native_coordinates_sha256="f" * 64,
        )


def test_page_artifact_rejects_invalid_rotation() -> None:
    with pytest.raises(ValidationError, match="旋转"):
        _page_artifact(rotation=30)


# ---------------------------------------------------------------------------
# OCRProfile fingerprint
# ---------------------------------------------------------------------------


def test_ocr_profile_fingerprint_is_deterministic_and_identity_sensitive() -> None:
    p1 = _profile()
    p2 = _profile()
    assert p1.profile_sha256 == p2.profile_sha256
    changed = _profile(model_revision="r2")
    assert changed.profile_sha256 != p1.profile_sha256
    changed_parser = _profile(parser_version="v2")
    assert changed_parser.profile_sha256 != p1.profile_sha256


def test_ocr_profile_rejects_stale_fingerprint() -> None:
    base: dict[str, Any] = {
        "ocr_profile_id": "profile-1",
        "extraction_route": ExtractionRoute.VISION_OCR,
        "provider": "omlx",
        "model_id": "GLM-OCR-bf16",
        "model_revision": "unknown",
        "parser_version": "v1",
        "coordinate_transform_version": _T,
        "profile_sha256": "f" * 64,
        "created_at": _ts,
    }
    with pytest.raises(ValidationError, match="不一致"):
        OCRProfile(**base)


def test_ocr_timestamps_require_utc() -> None:
    with pytest.raises(ValidationError, match="UTC"):
        _profile(created_at=_ts.replace(tzinfo=None))
    with pytest.raises(ValidationError, match="UTC"):
        RawOcrRequestArtifact(
            raw_request_artifact_id="req-1",
            sha256="a" * 64,
            storage_ref="blobs/req-1.json",
            created_at=_ts.replace(tzinfo=None),
        )


# ---------------------------------------------------------------------------
# Raw artifacts
# ---------------------------------------------------------------------------


def test_raw_artifact_storage_ref_must_be_portable() -> None:
    RawOcrRequestArtifact(
        raw_request_artifact_id="req-1",
        sha256="a" * 64,
        storage_ref="blobs/ocr_requests/req-1.json",
        created_at=_ts,
    )
    with pytest.raises(ValidationError, match="本机绝对路径"):
        RawOcrRequestArtifact(
            raw_request_artifact_id="req-1",
            sha256="a" * 64,
            storage_ref="/Users/smkzw/secret.json",
            created_at=_ts,
        )
    with pytest.raises(ValidationError, match="本机绝对路径"):
        RawOcrResponseArtifact(
            raw_response_artifact_id="resp-1",
            sha256="b" * 64,
            storage_ref="../../etc/passwd",
            provider="omlx",
            model_id="m",
            created_at=_ts,
        )


# ---------------------------------------------------------------------------
# LocatorResult precision ladder
# ---------------------------------------------------------------------------


def _locator(precision, **kwargs) -> LocatorResult:
    values: dict[str, Any] = {
        "locator_id": "loc-1",
        "precision": precision,
        "locator_algorithm_version": "slice4.0/v1",
        "disambiguation": DisambiguationOutcome.UNIQUE_MATCH,
        "source_text_sha256": "a" * 64,
        "page_artifact_id": "artifact-1",
    }
    values.update(kwargs)
    return LocatorResult(**values)


def test_bbox_requires_coordinate_frame_and_unique_match() -> None:
    bbox = BoundingBox(x0=72, y0=749.2, x1=226, y1=763.2)
    _locator(LocatorPrecision.BBOX, bbox=bbox, coordinate_frame=_frame(), excerpt="否认高血压病史")
    with pytest.raises(ValidationError, match="坐标系"):
        _locator(LocatorPrecision.BBOX, bbox=bbox)
    with pytest.raises(ValidationError, match="唯一消歧"):
        _locator(
            LocatorPrecision.BBOX,
            bbox=bbox,
            coordinate_frame=_frame(),
            disambiguation=DisambiguationOutcome.REPEATED_TEXT_DEGRADED,
        )


def test_bbox_requires_page_bounds_and_provenance() -> None:
    with pytest.raises(ValidationError, match="页面边界"):
        _locator(
            LocatorPrecision.BBOX,
            bbox=BoundingBox(x0=72, y0=749.2, x1=600, y1=763.2),
            coordinate_frame=_frame(),
        )
    values: dict[str, Any] = {
        "bbox": BoundingBox(x0=72, y0=749.2, x1=226, y1=763.2),
        "coordinate_frame": _frame(),
    }
    with pytest.raises(ValidationError):
        _locator(LocatorPrecision.BBOX, **{**values, "source_text_sha256": None})
    with pytest.raises(ValidationError):
        _locator(LocatorPrecision.BBOX, **{**values, "page_artifact_id": None})


def test_non_bbox_cannot_carry_coordinates() -> None:
    bbox = BoundingBox(x0=72, y0=749.2, x1=226, y1=763.2)
    with pytest.raises(ValidationError, match="坐标"):
        _locator(
            LocatorPrecision.PAGE_EXCERPT,
            bbox=bbox,
            coordinate_frame=_frame(),
            excerpt="否认高血压病史",
            degradation_reason="重复文本",
            disambiguation=DisambiguationOutcome.REPEATED_TEXT_DEGRADED,
        )


def test_text_range_requires_unique_and_source_hash() -> None:
    _locator(
        LocatorPrecision.TEXT_RANGE,
        text_start=4,
        text_end=10,
        source_text_sha256="a" * 64,
        excerpt="高血压",
    )
    with pytest.raises(ValidationError):
        _locator(
            LocatorPrecision.TEXT_RANGE,
            text_start=4,
            text_end=10,
            page_artifact_id=None,
        )
    with pytest.raises(ValidationError, match="唯一消歧"):
        _locator(
            LocatorPrecision.TEXT_RANGE,
            text_start=4,
            text_end=10,
            source_text_sha256="a" * 64,
            disambiguation=DisambiguationOutcome.REPEATED_TEXT_DEGRADED,
        )


def test_page_excerpt_repeated_must_justify_degradation() -> None:
    _locator(
        LocatorPrecision.PAGE_EXCERPT,
        excerpt="否认高血压病史",
        degradation_reason="多处相同文本无法稳定消歧",
        disambiguation=DisambiguationOutcome.REPEATED_TEXT_DEGRADED,
    )
    with pytest.raises(ValidationError, match="降级原因"):
        _locator(
            LocatorPrecision.PAGE_EXCERPT,
            excerpt="x",
            disambiguation=DisambiguationOutcome.REPEATED_TEXT_DEGRADED,
        )
    with pytest.raises(ValidationError, match="未找到"):
        _locator(
            LocatorPrecision.PAGE_EXCERPT,
            excerpt="x",
            disambiguation=DisambiguationOutcome.NOT_FOUND,
            degradation_reason="未找到",
        )


def test_page_only_requires_reason_and_not_found() -> None:
    _locator(
        LocatorPrecision.PAGE_ONLY,
        degradation_reason="目标文本未在原生文本中找到",
        disambiguation=DisambiguationOutcome.NOT_FOUND,
        match_confidence=0.0,
    )
    with pytest.raises(ValidationError, match="降级原因"):
        _locator(LocatorPrecision.PAGE_ONLY)
    with pytest.raises(ValidationError, match="未找到时产生"):
        _locator(
            LocatorPrecision.PAGE_ONLY,
            degradation_reason="x",
            disambiguation=DisambiguationOutcome.UNIQUE_MATCH,
        )


# ---------------------------------------------------------------------------
# OcrRiskFlag
# ---------------------------------------------------------------------------


def test_risk_flag_range_matches_text() -> None:
    OcrRiskFlag(
        risk_id="risk-1",
        kind=OcrRiskKind.NUMERIC_VALUE,
        level=OcrRiskLevel.BLOCKING,
        text="76.1",
        text_start=8,
        text_end=12,
        rule_version="slice4.0/v1",
    )
    with pytest.raises(ValidationError, match="长度"):
        OcrRiskFlag(
            risk_id="risk-1",
            kind=OcrRiskKind.NUMERIC_VALUE,
            level=OcrRiskLevel.BLOCKING,
            text="76.1",
            text_start=8,
            text_end=9,
            rule_version="slice4.0/v1",
        )


# ---------------------------------------------------------------------------
# OCRPage
# ---------------------------------------------------------------------------


def test_ocr_page_requires_matching_raw_text_hash() -> None:
    from hashlib import sha256

    raw = "否认高血压病史"
    base: dict[str, Any] = {
        "ocr_page_id": "page-1",
        "page_artifact_id": "artifact-1",
        "source_sha256": "c" * 64,
        "page_number": 1,
        "page_input_sha256": "d" * 64,
        "ocr_profile_sha256": "a" * 64,
        "cache_key": build_ocr_cache_key(
            source_sha256="c" * 64,
            page_number=1,
            ocr_profile_sha256="a" * 64,
            page_input_sha256="d" * 64,
            layout_parser_version=None,
            coordinate_transform_version=_T,
        ),
        "coordinate_transform_version": _T,
        "raw_text": raw,
        "raw_text_sha256": sha256(raw.encode("utf-8")).hexdigest(),
        "quality": PageQualityMetrics(char_count=len(raw), word_count=1),
        "status": OCRPageStatus.SUCCEEDED,
        "started_at": _ts,
        "completed_at": _ts,
    }
    OCRPage(**base)
    with pytest.raises(ValidationError, match="不一致"):
        OCRPage(**{**base, "raw_text_sha256": "c" * 64})


def test_ocr_page_failed_requires_reason() -> None:
    with pytest.raises(ValidationError, match="原因"):
        OCRPage(
            ocr_page_id="p",
            page_artifact_id="a",
            source_sha256="c" * 64,
            page_number=1,
            page_input_sha256="d" * 64,
            ocr_profile_sha256="a" * 64,
            cache_key=build_ocr_cache_key(
                source_sha256="c" * 64,
                page_number=1,
                ocr_profile_sha256="a" * 64,
                page_input_sha256="d" * 64,
                layout_parser_version=None,
                coordinate_transform_version=_T,
            ),
            coordinate_transform_version=_T,
            raw_text="",
            raw_text_sha256=__import__("hashlib").sha256(b"").hexdigest(),
            quality=PageQualityMetrics(char_count=0, word_count=0),
            status=OCRPageStatus.FAILED,
            completed_at=_ts,
        )


def test_ocr_page_cache_status_time_and_risk_ranges_are_closed() -> None:
    from hashlib import sha256

    raw = "数值 76.1"
    base: dict[str, Any] = {
        "ocr_page_id": "page-1",
        "page_artifact_id": "artifact-1",
        "source_sha256": "c" * 64,
        "page_number": 1,
        "page_input_sha256": "d" * 64,
        "ocr_profile_sha256": "a" * 64,
        "cache_key": build_ocr_cache_key(
            source_sha256="c" * 64,
            page_number=1,
            ocr_profile_sha256="a" * 64,
            page_input_sha256="d" * 64,
            layout_parser_version=None,
            coordinate_transform_version=_T,
        ),
        "coordinate_transform_version": _T,
        "raw_text": raw,
        "raw_text_sha256": sha256(raw.encode("utf-8")).hexdigest(),
        "quality": PageQualityMetrics(char_count=len(raw), word_count=2),
        "status": OCRPageStatus.SUCCEEDED,
        "started_at": _ts,
        "completed_at": _ts,
    }
    OCRPage(**base)
    with pytest.raises(ValidationError, match="缓存键"):
        OCRPage(**{**base, "page_number": 2})
    with pytest.raises(ValidationError, match="风险项范围"):
        OCRPage(
            **base,
            risk_items=[
                OcrRiskFlag(
                    risk_id="risk-1",
                    kind=OcrRiskKind.NUMERIC_VALUE,
                    level=OcrRiskLevel.BLOCKING,
                    text="76.1",
                    text_start=100,
                    text_end=104,
                    rule_version="slice4.0/v1",
                )
            ],
        )
    with pytest.raises(ValidationError, match="同时提供开始"):
        OCRPage(**{**base, "started_at": None})
    with pytest.raises(ValidationError, match="同时提供开始"):
        OCRPage(**{**base, "completed_at": None})
    with pytest.raises(ValidationError, match="早于"):
        OCRPage(**{**base, "completed_at": datetime(2026, 8, 19, 7, 0, 0, tzinfo=UTC)})
