"""脱敏/合成页级金标准数据模型（纯数据，无文件 I/O）。

金标准用于 Slice 4.0 冻结验收算法：原生 PDF 文本回读一致率、目标定位成功率、
扫描/照片布局候选定位成功率与关键风险漏检/误报。每个目标条目固定期望精度与
是否允许精确匹配；重复文本条目必须预期降级，防止「有一个命中就伪造精确」。
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from app.domain.contracts.enums import ExtractionRoute, LocatorPrecision, OcrRiskKind
from app.domain.contracts.evidence import BoundingBox

# 定位精度阶梯排序：区域坐标 > 文本范围 > 页内摘录 > 仅页码。
_PRECISION_RANK = {
    LocatorPrecision.BBOX: 4,
    LocatorPrecision.TEXT_RANGE: 3,
    LocatorPrecision.PAGE_EXCERPT: 2,
    LocatorPrecision.PAGE_ONLY: 1,
}


@dataclass(frozen=True)
class GoldTarget:
    """一个待定位目标：期望最低精度与是否允许精确匹配。

    ``expected_pixel_bbox`` 是布局候选（扫描/照片）评估时的真实绘制区域
    （页图像素坐标），由合成生成器记录，用于覆盖校验。
    """

    text: str
    expected_precision: LocatorPrecision = LocatorPrecision.BBOX
    allow_exact: bool = True
    expected_pixel_bbox: BoundingBox | None = None


@dataclass(frozen=True)
class GoldPage:
    """一页金标准：期望文本、定位目标、期望风险类别与识别路线。

    ``expected_failure_reason`` 表示该文件/页必须失败（损坏、格式不支持、
    解码失败），不产生任何成功页产物；与成功页的期望字段互斥使用。
    """

    gold_page_id: str
    file_ref: str
    page_number: int
    expected_text: str | None = None
    expected_readback_exact: bool = True
    targets: tuple[GoldTarget, ...] = ()
    expected_risk_kinds: tuple[OcrRiskKind, ...] = ()
    route: ExtractionRoute | None = None
    expected_failure_reason: str | None = None
    expected_pixel_size: tuple[int, int] | None = None

    @property
    def expects_failure(self) -> bool:
        return self.expected_failure_reason is not None


@dataclass(frozen=True)
class GoldSet:
    name: str
    pages: tuple[GoldPage, ...]
    source_sha256_by_file: Mapping[str, str] = field(default_factory=dict)

    def pages_for(self, file_ref: str) -> tuple[GoldPage, ...]:
        return tuple(p for p in self.pages if p.file_ref == file_ref)


def precision_rank(precision: LocatorPrecision) -> int:
    return _PRECISION_RANK[precision]


def target_requires_degradation(target: GoldTarget) -> bool:
    """重复文本目标必须诚实降级（不允许区域定位）。"""
    return not target.allow_exact
