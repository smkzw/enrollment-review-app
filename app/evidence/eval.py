"""Slice 4.0 验收算法（确定性度量）。

冻结验收门槛：
- 原生 PDF 目标文本回读一致率 100%；
- 目标定位成功率 ≥ 95%；
- 扫描/照片布局候选正式采用时目标块定位成功率 ≥ 90%，且所有已输出区域
  均落在正确页并覆盖正确目标文本；达不到门槛则诚实降级；
- 关键风险种子集漏检为 0、页面级误报率 ≤ 10%。

本模块只计算度量；采用/降级决策由调用方按门槛判定。
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.domain.contracts.enums import ExtractionRoute, LocatorPrecision
from app.domain.contracts.evidence import BoundingBox
from app.domain.contracts.ocr import LocatorResult, OcrRiskFlag
from app.evidence.coordinates import bbox_contains
from app.evidence.goldset import (
    GoldPage,
    GoldSet,
    GoldTarget,
    precision_rank,
    target_requires_degradation,
)


@dataclass(frozen=True)
class ReadbackEval:
    exact_count: int
    total: int
    failures: list[GoldPage]

    @property
    def rate(self) -> float:
        return self.exact_count / self.total if self.total else 1.0


@dataclass(frozen=True)
class LocatorEval:
    success_count: int
    total: int
    failures: list[tuple[GoldPage, GoldTarget, LocatorResult | None]]

    @property
    def rate(self) -> float:
        return self.success_count / self.total if self.total else 1.0


@dataclass(frozen=True)
class LayoutCandidate:
    """布局解析器输出的候选区域（页图像素坐标）。"""

    page_number: int
    bbox: BoundingBox
    text: str


@dataclass(frozen=True)
class LayoutEval:
    success_count: int
    total: int
    page_mismatches: list[str] = field(default_factory=list)
    coverage_failures: list[str] = field(default_factory=list)
    text_failures: list[str] = field(default_factory=list)
    out_of_bounds: list[str] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return self.success_count / self.total if self.total else 1.0

    @property
    def all_regions_valid(self) -> bool:
        return not self.page_mismatches and not self.out_of_bounds


@dataclass(frozen=True)
class RiskEval:
    miss_count: int
    total_gold_kinds: int
    fp_pages: int
    clean_pages: int
    risk_pages: int
    processed_pages: int
    eligible_pages: int
    unprocessed_page_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def miss_rate(self) -> float:
        return self.miss_count / self.total_gold_kinds if self.total_gold_kinds else 0.0

    @property
    def fp_rate(self) -> float:
        return self.fp_pages / self.clean_pages if self.clean_pages else 0.0

    @property
    def complete(self) -> bool:
        """Whether every eligible gold page was included in the measurement."""
        return not self.unprocessed_page_ids


def _normalized(value: str) -> str:
    return "".join(value.split())


def evaluate_readback(gold_set: GoldSet, extracted_text_by_page: Mapping[str, str]) -> ReadbackEval:
    """文本回读一致率：仅对声明可精确回读的原生文本页计算。"""
    exact = 0
    total = 0
    failures: list[GoldPage] = []
    for page in gold_set.pages:
        if not page.expected_text or not page.expected_readback_exact:
            continue
        total += 1
        extracted = extracted_text_by_page.get(page.gold_page_id, "")
        if _normalized(extracted) == _normalized(page.expected_text):
            exact += 1
        else:
            failures.append(page)
    return ReadbackEval(exact_count=exact, total=total, failures=failures)


def target_locator_success(target: GoldTarget, result: LocatorResult) -> bool:
    """单个定位目标的成功判定。

    - 允许精确匹配的目标：结果精度不低于期望最低精度；
    - 重复文本目标（``allow_exact=False``）：必须诚实降级到摘录/页码并说明原因，
      任何区域定位都视为伪造精确而判失败。
    """
    if target_requires_degradation(target):
        return (
            result.precision in {LocatorPrecision.PAGE_EXCERPT, LocatorPrecision.PAGE_ONLY}
            and bool(result.degradation_reason)
        )
    return precision_rank(result.precision) >= precision_rank(target.expected_precision)


def evaluate_locators(
    gold_set: GoldSet,
    results: Mapping[tuple[str, str], LocatorResult],
) -> LocatorEval:
    """目标定位成功率：按 ``(gold_page_id, target.text) -> LocatorResult`` 判定。

    只评估原生 PDF 路线页面；扫描/照片布局候选走 ``evaluate_layout_candidates``，
    TXT/DOCX 派生页定位由后续切片评估。
    """
    success = 0
    total = 0
    failures: list[tuple[GoldPage, GoldTarget, LocatorResult | None]] = []
    for page in gold_set.pages:
        if page.route != ExtractionRoute.NATIVE_PDF_TEXT:
            continue
        for target in page.targets:
            total += 1
            result = results.get((page.gold_page_id, target.text))
            if result is None or not target_locator_success(target, result):
                failures.append((page, target, result))
                continue
            success += 1
    return LocatorEval(success_count=success, total=total, failures=failures)


def evaluate_layout_candidates(
    gold_set: GoldSet,
    candidates: Mapping[str, Sequence[LayoutCandidate]],
) -> LayoutEval:
    """布局候选定位成功率：区域必须落在正确页且覆盖目标真实绘制区域。"""
    success = 0
    total = 0
    page_mismatches: list[str] = []
    coverage_failures: list[str] = []
    text_failures: list[str] = []
    out_of_bounds: list[str] = []
    for page in gold_set.pages:
        if page.route != ExtractionRoute.VISION_OCR:
            continue
        for target in page.targets:
            if target.expected_pixel_bbox is None:
                continue
            total += 1
            page_candidates = candidates.get(page.gold_page_id, [])
            for candidate in page_candidates:
                if candidate.page_number != page.page_number:
                    page_mismatches.append(
                        f"{page.gold_page_id}: 候选在第 {candidate.page_number} 页，期望第 {page.page_number} 页"
                    )
                    continue
                if page.expected_pixel_size is not None:
                    page_width, page_height = page.expected_pixel_size
                    if candidate.bbox.x1 > page_width or candidate.bbox.y1 > page_height:
                        out_of_bounds.append(
                            f"{page.gold_page_id}: 候选区域越出页图边界 {page.expected_pixel_size}"
                        )
            hit = False
            for candidate in page_candidates:
                if candidate.page_number != page.page_number:
                    continue
                if bbox_contains(candidate.bbox, target.expected_pixel_bbox) and _normalized(target.text) in _normalized(candidate.text):
                    hit = True
                elif bbox_contains(candidate.bbox, target.expected_pixel_bbox):
                    text_failures.append(
                        f"{page.gold_page_id}: 候选区域覆盖目标但文本不包含「{target.text}」"
                    )
            if hit:
                success += 1
            else:
                coverage_failures.append(f"{page.gold_page_id}: 目标「{target.text}」未被任何候选区域覆盖")
    return LayoutEval(
        success_count=success,
        total=total,
        page_mismatches=page_mismatches,
        coverage_failures=coverage_failures,
        text_failures=text_failures,
        out_of_bounds=out_of_bounds,
    )


def evaluate_risk_seed(
    gold_set: GoldSet,
    flags_by_page: Mapping[str, Sequence[OcrRiskFlag]],
    page_ids: Sequence[str] | None = None,
) -> RiskEval:
    """关键风险漏检为 0、页面级误报率 ≤ 10% 的度量。

    漏检按「金标准风险类别未出现在该页输出类别集合」计数；误报按
    「无金标准风险的干净页被标记了任何风险」逐页计数。``page_ids`` 显式
    声明扫描器实际运行过的页面；未声明的金标准页仍进入覆盖检查，不能通过
    少量干净页或跳过风险页来冒充合规。``flags_by_page`` 必须为每个声明处理页
    提供条目（即使该页没有风险），否则直接拒绝该度量输入。
    """
    miss = 0
    total_kinds = 0
    fp_pages = 0
    clean_pages = 0
    risk_pages = 0
    eligible_pages = tuple(
        page
        for page in gold_set.pages
        if not page.expects_failure and page.expected_text is not None
    )
    eligible_ids = {page.gold_page_id for page in eligible_pages}
    output_ids = set(flags_by_page)
    unknown_output_ids = output_ids - eligible_ids
    if unknown_output_ids:
        raise ValueError(f"风险输出包含不属于金标准的页面: {sorted(unknown_output_ids)}")
    processed_ids = output_ids if page_ids is None else set(page_ids)
    unknown_ids = processed_ids - eligible_ids
    if unknown_ids:
        raise ValueError(f"风险度量包含不属于金标准的页面: {sorted(unknown_ids)}")
    missing_outputs = processed_ids - output_ids
    if missing_outputs:
        raise ValueError(f"风险度量声明已处理页面但缺少输出: {sorted(missing_outputs)}")
    unprocessed_ids = tuple(sorted(eligible_ids - processed_ids))

    for page in eligible_pages:
        flagged = (
            {flag.kind for flag in flags_by_page.get(page.gold_page_id, [])}
            if page.gold_page_id in processed_ids
            else set()
        )
        expected = set(page.expected_risk_kinds)
        if expected:
            risk_pages += 1
            total_kinds += len(expected)
            miss += len(expected - flagged)
        else:
            clean_pages += 1
            if flagged:
                fp_pages += 1
    return RiskEval(
        miss_count=miss,
        total_gold_kinds=total_kinds,
        fp_pages=fp_pages,
        clean_pages=clean_pages,
        risk_pages=risk_pages,
        processed_pages=len(processed_ids),
        eligible_pages=len(eligible_pages),
        unprocessed_page_ids=unprocessed_ids,
    )
