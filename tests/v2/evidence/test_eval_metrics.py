"""验收度量算法测试：回读、定位、布局候选与风险种子度量。"""
from __future__ import annotations

import pytest

from app.domain.contracts.enums import (
    DisambiguationOutcome,
    ExtractionRoute,
    LocatorPrecision,
    OcrRiskKind,
    OcrRiskLevel,
)
from app.domain.contracts.evidence import BoundingBox
from app.domain.contracts.ocr import LocatorResult, OcrRiskFlag
from app.evidence import (
    LayoutCandidate,
    evaluate_layout_candidates,
    evaluate_locators,
    evaluate_readback,
    evaluate_risk_seed,
    precision_rank,
    target_locator_success,
)
from app.evidence.goldset import GoldPage, GoldSet, GoldTarget


def _gold_set(*pages: GoldPage) -> GoldSet:
    return GoldSet(name="test", pages=tuple(pages))


def _page(pid: str, targets=(), risks=(), route=ExtractionRoute.NATIVE_PDF_TEXT) -> GoldPage:
    return GoldPage(
        gold_page_id=pid,
        file_ref=f"{pid}.pdf",
        page_number=1,
        expected_text="目标文本",
        route=route,
        targets=tuple(targets),
        expected_risk_kinds=tuple(risks),
    )


def _locator(precision, **kwargs) -> LocatorResult:
    values = {
        "locator_id": "l1",
        "precision": precision,
        "locator_algorithm_version": "v1",
        "disambiguation": DisambiguationOutcome.UNIQUE_MATCH,
        "source_text_sha256": "a" * 64,
        "page_artifact_id": "artifact-1",
    }
    values.update(kwargs)
    return LocatorResult(**values)


def test_precision_rank_order() -> None:
    assert precision_rank(LocatorPrecision.BBOX) > precision_rank(LocatorPrecision.TEXT_RANGE)
    assert precision_rank(LocatorPrecision.TEXT_RANGE) > precision_rank(
        LocatorPrecision.PAGE_EXCERPT
    )
    assert precision_rank(LocatorPrecision.PAGE_EXCERPT) > precision_rank(
        LocatorPrecision.PAGE_ONLY
    )


def test_readback_metric_counts_only_exact_pages() -> None:
    exact = _page("p1")
    scanned = GoldPage(
        gold_page_id="p2",
        file_ref="p2.pdf",
        page_number=1,
        expected_text="扫描页",
        expected_readback_exact=False,
        route=ExtractionRoute.VISION_OCR,
    )
    result = evaluate_readback(_gold_set(exact, scanned), {"p1": "目标文本"})
    assert result.total == 1
    assert result.exact_count == 1
    assert result.rate == 1.0


def test_locator_metric_scoped_to_native_route() -> None:
    native = _page("p1", targets=(GoldTarget("目标文本"),))
    scanned = _page(
        "p2",
        targets=(GoldTarget("扫描目标", expected_precision=LocatorPrecision.BBOX),),
        route=ExtractionRoute.VISION_OCR,
    )
    result = evaluate_locators(
        _gold_set(native, scanned),
        {("p1", "目标文本"): _bbox_locator()},
    )
    # 扫描页目标不在原生定位度量范围内。
    assert result.total == 1
    assert result.success_count == 1


def _bbox_locator() -> LocatorResult:
    from app.domain.contracts.enums import CoordinateSpace
    from app.domain.contracts.ocr import CoordinateFrame

    return _locator(
        LocatorPrecision.BBOX,
        bbox=BoundingBox(x0=1, y0=1, x1=2, y1=2),
        coordinate_frame=CoordinateFrame(
            space=CoordinateSpace.PDF_POINTS,
            page_width=595.0,
            page_height=842.0,
            rotation=0,
            transform_version="v1",
        ),
    )


def test_repeated_target_must_degrade_to_pass() -> None:
    repeated = GoldTarget("重复句", expected_precision=LocatorPrecision.PAGE_EXCERPT, allow_exact=False)
    bbox_result = _bbox_locator()
    assert not target_locator_success(repeated, bbox_result)  # 伪精确失败
    degraded = _locator(
        LocatorPrecision.PAGE_EXCERPT,
        excerpt="重复句",
        disambiguation=DisambiguationOutcome.REPEATED_TEXT_DEGRADED,
        degradation_reason="多处相同文本无法稳定消歧",
    )
    assert target_locator_success(repeated, degraded)


def test_layout_candidates_require_correct_page_and_coverage() -> None:
    target = GoldTarget(
        "区域文本",
        expected_precision=LocatorPrecision.BBOX,
        expected_pixel_bbox=BoundingBox(x0=100, y0=100, x1=200, y1=120),
    )
    page = _page("p1", targets=(target,), route=ExtractionRoute.VISION_OCR)
    # 正确页 + 覆盖目标 -> 通过
    good = evaluate_layout_candidates(
        _gold_set(page),
        {"p1": [LayoutCandidate(page_number=1, bbox=BoundingBox(x0=90, y0=90, x1=210, y1=130), text="区域文本")]},
    )
    assert good.success_count == 1 and good.rate == 1.0
    # 错误页 -> 失败并记录页错位
    wrong_page = evaluate_layout_candidates(
        _gold_set(page),
        {"p1": [LayoutCandidate(page_number=2, bbox=BoundingBox(x0=90, y0=90, x1=210, y1=130), text="区域文本")]},
    )
    assert wrong_page.success_count == 0
    assert wrong_page.page_mismatches
    # 不覆盖目标 -> 失败并记录覆盖失败
    partial = evaluate_layout_candidates(
        _gold_set(page),
        {"p1": [LayoutCandidate(page_number=1, bbox=BoundingBox(x0=1000, y0=1000, x1=1100, y1=1100), text="区域文本")]},
    )
    assert partial.success_count == 0
    assert partial.coverage_failures

    wrong_text = evaluate_layout_candidates(
        _gold_set(
            GoldPage(
                gold_page_id="p-text",
                file_ref="p-text.png",
                page_number=1,
                expected_text="扫描页",
                route=ExtractionRoute.VISION_OCR,
                targets=(target,),
                expected_pixel_size=(300, 300),
            )
        ),
        {"p-text": [LayoutCandidate(page_number=1, bbox=BoundingBox(x0=90, y0=90, x1=210, y1=130), text="其他文本")]},
    )
    assert wrong_text.success_count == 0
    assert wrong_text.text_failures

    out_of_bounds = evaluate_layout_candidates(
        _gold_set(
            GoldPage(
                gold_page_id="p-bounds",
                file_ref="p-bounds.png",
                page_number=1,
                expected_text="扫描页",
                route=ExtractionRoute.VISION_OCR,
                targets=(target,),
                expected_pixel_size=(300, 300),
            )
        ),
        {"p-bounds": [LayoutCandidate(page_number=1, bbox=BoundingBox(x0=90, y0=90, x1=310, y1=130), text="区域文本")]},
    )
    assert out_of_bounds.out_of_bounds


def test_risk_seed_metric_scoping() -> None:
    risky = _page("r1", risks=(OcrRiskKind.DATE,))
    clean = _page("c1")
    flags = {
        "r1": [
            OcrRiskFlag(
                risk_id="x", kind=OcrRiskKind.DATE, level=OcrRiskLevel.BLOCKING,
                text="2026-08-19", text_start=0, text_end=10, rule_version="v1",
            )
        ],
        "c1": [
            OcrRiskFlag(
                risk_id="y", kind=OcrRiskKind.UNIT, level=OcrRiskLevel.BLOCKING,
                text="U/L", text_start=0, text_end=3, rule_version="v1",
            )
        ],
    }
    # 未限定范围：干净页被误报 → fp_rate=1.0
    unscoped = evaluate_risk_seed(_gold_set(risky, clean), flags)
    assert unscoped.miss_count == 0
    assert unscoped.fp_pages == 1
    assert unscoped.fp_rate == 1.0
    # 限定范围只评估扫描器实际运行过的页
    scoped = evaluate_risk_seed(_gold_set(risky, clean), flags, page_ids=["r1"])
    assert scoped.fp_pages == 0
    assert scoped.miss_count == 0
    assert not scoped.complete
    assert scoped.unprocessed_page_ids == ("c1",)

    # Without an explicit page list, missing clean-page outputs remain uncovered;
    # a small subset of clean pages cannot be presented as a complete run.
    partial = evaluate_risk_seed(_gold_set(risky, clean), {"r1": flags["r1"]})
    assert not partial.complete
    assert partial.unprocessed_page_ids == ("c1",)
    with pytest.raises(ValueError, match="缺少输出"):
        evaluate_risk_seed(
            _gold_set(risky, clean),
            {"r1": flags["r1"]},
            page_ids=["r1", "c1"],
        )
