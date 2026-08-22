"""坐标系统：PDF points 与渲染页图像素之间的确定性换算。

PDF 原生坐标原点在页面左下、y 向上（PDF 规范）；渲染页图像素坐标原点在左上、
y 向下。本模块只做纯数学换算，不访问文件。变换规则以 ``CoordinateFrame`` 冻结，
坐标从 pdfplumber 原生对象直接映射到页图坐标系，供定位真实性门禁使用。
"""
from __future__ import annotations

from app.domain.contracts.enums import CoordinateSpace
from app.domain.contracts.evidence import BoundingBox
from app.domain.contracts.ocr import CoordinateFrame

COORDINATE_TRANSFORM_VERSION = "slice4.0/v1"


class CoordinateError(ValueError):
    """坐标越界或不属于目标坐标空间的错误。"""


def pdf_points_to_image_pixels(
    bbox: BoundingBox,
    frame: CoordinateFrame,
    *,
    pixels_per_point: float,
) -> BoundingBox:
    """把 PDF points 坐标系（原点左下、y 向上）的 bbox 换算到页图像素坐标。

    ``frame`` 必须使用 pdfplumber/渲染器的可视页尺寸；90/270 度页面的宽高交换已经
    包含在 frame 中，函数不会再次应用 rotation。``pixels_per_point`` 由渲染 DPI 决定（``dpi / 72.0``）。换算规则：
    ``x_px = x_pdf * s``；``y_px = (page_height_pdf - y_pdf) * s``。
    """
    if frame.space != CoordinateSpace.PDF_POINTS:
        raise CoordinateError("pdf_points_to_image_pixels 需要 pdf_points 坐标系")
    if pixels_per_point <= 0:
        raise CoordinateError("pixels_per_point 必须为正")
    _require_within(bbox, frame)
    x0 = bbox.x0 * pixels_per_point
    y0 = (frame.page_height - bbox.y1) * pixels_per_point
    x1 = bbox.x1 * pixels_per_point
    y1 = (frame.page_height - bbox.y0) * pixels_per_point
    return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)


def image_pixels_to_pdf_points(
    bbox: BoundingBox,
    frame: CoordinateFrame,
    *,
    pixels_per_point: float,
) -> BoundingBox:
    """把页图像素坐标（原点左上、y 向下）的 bbox 换算回 PDF points。"""
    if frame.space != CoordinateSpace.PAGE_IMAGE_PIXELS:
        raise CoordinateError("image_pixels_to_pdf_points 需要 page_image_pixels 坐标系")
    if pixels_per_point <= 0:
        raise CoordinateError("pixels_per_point 必须为正")
    x0 = bbox.x0 / pixels_per_point
    y1 = frame.page_height - bbox.y0 / pixels_per_point
    x1 = bbox.x1 / pixels_per_point
    y0 = frame.page_height - bbox.y1 / pixels_per_point
    result = BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)
    _require_within(result, frame)
    return result


def _require_within(bbox: BoundingBox, frame: CoordinateFrame) -> None:
    if (
        bbox.x0 < 0
        or bbox.y0 < 0
        or bbox.x1 > frame.page_width
        or bbox.y1 > frame.page_height
    ):
        raise CoordinateError(
            "坐标越出页面边界: "
            f"bbox=({bbox.x0:.2f},{bbox.y0:.2f},{bbox.x1:.2f},{bbox.y1:.2f}) "
            f"page=({frame.page_width:.2f}x{frame.page_height:.2f})"
        )


def bbox_overlap_ratio(a: BoundingBox, b: BoundingBox) -> float:
    """返回两个 bbox 的 IoU 交并比（0..1）；无重叠为 0。"""
    inter_x0 = max(a.x0, b.x0)
    inter_y0 = max(a.y0, b.y0)
    inter_x1 = min(a.x1, b.x1)
    inter_y1 = min(a.y1, b.y1)
    if inter_x1 <= inter_x0 or inter_y1 <= inter_y0:
        return 0.0
    inter_area = (inter_x1 - inter_x0) * (inter_y1 - inter_y0)
    a_area = (a.x1 - a.x0) * (a.y1 - a.y0)
    b_area = (b.x1 - b.x0) * (b.y1 - b.y0)
    union = a_area + b_area - inter_area
    return inter_area / union if union > 0 else 0.0


def bbox_contains(container: BoundingBox, inner: BoundingBox, *, tolerance: float = 0.0) -> bool:
    """``inner`` 是否完全位于 ``container`` 内（允许 ``tolerance`` 的外扩）。"""
    return (
        container.x0 - tolerance <= inner.x0
        and container.y0 - tolerance <= inner.y0
        and container.x1 + tolerance >= inner.x1
        and container.y1 + tolerance >= inner.y1
    )
