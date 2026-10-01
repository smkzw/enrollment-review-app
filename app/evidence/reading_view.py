"""Lossless quarter-turn reading views with explicit source coordinates.

This module does not infer orientation or approve model observations.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import io
from typing import Literal

from PIL import Image

from app.domain.contracts.evidence import BoundingBox
from app.domain.publication import canonical_hash

READING_VIEW_VERSION = "reading-view/quarter-turn/v1"


@dataclass(frozen=True)
class ReadingView:
    source_page_artifact_id: str
    source_image_sha256: str
    source_width: int
    source_height: int
    clockwise_degrees: Literal[0, 90, 180, 270]
    image_bytes: bytes
    width: int
    height: int

    def __post_init__(self) -> None:
        if not self.source_page_artifact_id.strip():
            raise ValueError("阅读视图缺少原始页面身份")
        if (len(self.source_image_sha256) != 64
                or any(c not in "0123456789abcdef" for c in self.source_image_sha256)):
            raise ValueError("阅读视图缺少有效的原始页图哈希")
        if (type(self.clockwise_degrees) is not int
                or self.clockwise_degrees not in (0, 90, 180, 270)):
            raise ValueError("阅读视图仅支持明确指定的直角旋转")
        if any(type(value) is not int or value <= 0 for value in (
            self.source_width, self.source_height, self.width, self.height,
        )):
            raise ValueError("阅读视图的页面尺寸无效")
        expected = ((self.source_height, self.source_width)
                    if self.clockwise_degrees in (90, 270)
                    else (self.source_width, self.source_height))
        if (self.width, self.height) != expected:
            raise ValueError("阅读视图尺寸与旋转方向不一致")
        with Image.open(io.BytesIO(self.image_bytes)) as image:
            if image.size != expected or getattr(image, "n_frames", 1) != 1:
                raise ValueError("阅读视图尺寸与实际单页图片不一致")
        if self.clockwise_degrees == 0 and self.image_sha256 != self.source_image_sha256:
            raise ValueError("未旋转的阅读视图必须保留原始页图字节")

    @property
    def image_sha256(self) -> str:
        return sha256(self.image_bytes).hexdigest()

    def identity(self) -> dict[str, str | int]:
        return {
            "version": READING_VIEW_VERSION,
            "coordinate_space": "page_image_pixels",
            "source_page_artifact_id": self.source_page_artifact_id,
            "source_image_sha256": self.source_image_sha256,
            "source_width": self.source_width,
            "source_height": self.source_height,
            "clockwise_degrees": self.clockwise_degrees,
            "view_image_sha256": self.image_sha256,
            "view_width": self.width,
            "view_height": self.height,
        }

    @property
    def view_id(self) -> str:
        return "reading-view:" + canonical_hash(self.identity())

    def source_bbox(self, box: BoundingBox) -> BoundingBox:
        """Map continuous pixel edges, not pixel-center indices, to the source."""
        if box.x1 > self.width or box.y1 > self.height:
            raise ValueError("阅读视图中的标注超出页面范围")
        x0, y0, x1, y1 = box.x0, box.y0, box.x1, box.y1
        w, h = self.source_width, self.source_height
        if self.clockwise_degrees == 90:
            values = (y0, h - x1, y1, h - x0)
        elif self.clockwise_degrees == 180:
            values = (w - x1, h - y1, w - x0, h - y0)
        elif self.clockwise_degrees == 270:
            values = (w - y1, x0, w - y0, x1)
        else:
            values = (x0, y0, x1, y1)
        return BoundingBox(**dict(zip(("x0", "y0", "x1", "y1"), values)))


def make_reading_view(
    image_bytes: bytes, *, source_page_artifact_id: str,
    source_image_sha256: str, clockwise_degrees: Literal[0, 90, 180, 270],
) -> ReadingView:
    if not source_page_artifact_id.strip():
        raise ValueError("阅读视图缺少原始页面身份")
    if sha256(image_bytes).hexdigest() != source_image_sha256:
        raise ValueError("阅读视图的原始页图与记录不一致")
    if type(clockwise_degrees) is not int or clockwise_degrees not in (0, 90, 180, 270):
        raise ValueError("阅读视图仅支持明确指定的直角旋转")
    with Image.open(io.BytesIO(image_bytes)) as source:
        if getattr(source, "n_frames", 1) != 1:
            raise ValueError("阅读视图需要已分页的单张页图")
        w, h = source.size
        if clockwise_degrees:
            operation = {90: Image.Transpose.ROTATE_270,
                         180: Image.Transpose.ROTATE_180,
                         270: Image.Transpose.ROTATE_90}[clockwise_degrees]
            view = source.transpose(operation)
            buffer = io.BytesIO()
            view.save(buffer, format="PNG")
            result = buffer.getvalue()
            width, height = view.size
        else:
            result = image_bytes
            width, height = w, h
    return ReadingView(source_page_artifact_id, source_image_sha256, w, h,
                       clockwise_degrees, result, width, height)


@dataclass(frozen=True)
class ReadingRegion:
    """A source-bound crop; its coverage is a region, never a complete page."""

    reading_view: ReadingView
    view_bbox: BoundingBox
    image_bytes: bytes

    def __post_init__(self) -> None:
        self.reading_view.source_bbox(self.view_bbox)
        edges = self.pixel_edges
        if any(type(value) is not int for value in edges):
            raise ValueError("局部阅读须使用整数像素边界")
        with Image.open(io.BytesIO(self.image_bytes)) as image:
            if image.size != (edges[2] - edges[0], edges[3] - edges[1]):
                raise ValueError("局部图片尺寸与来源区域不一致")
            with Image.open(io.BytesIO(self.reading_view.image_bytes)) as page:
                expected = page.crop(edges)
                if image.mode != expected.mode or image.tobytes() != expected.tobytes():
                    raise ValueError("局部图片像素不属于声明的原件区域")

    @property
    def pixel_edges(self) -> tuple[int, int, int, int]:
        values = (self.view_bbox.x0, self.view_bbox.y0,
                  self.view_bbox.x1, self.view_bbox.y1)
        if any(not float(value).is_integer() for value in values):
            raise ValueError("局部阅读须使用整数像素边界")
        return tuple(int(value) for value in values)

    def identity(self) -> dict:
        return {
            "version": "reading-view/local-region/v1",
            "coverage_scope": "region_only",
            "reading_view": self.reading_view.identity(),
            "view_bbox": self.view_bbox.model_dump(mode="json"),
            "source_bbox": self.reading_view.source_bbox(self.view_bbox).model_dump(mode="json"),
            "region_image_sha256": sha256(self.image_bytes).hexdigest(),
        }


def make_reading_region(view: ReadingView, box: BoundingBox) -> ReadingRegion:
    view.source_bbox(box)
    values = (box.x0, box.y0, box.x1, box.y1)
    if any(not float(value).is_integer() for value in values):
        raise ValueError("局部阅读须使用整数像素边界")
    with Image.open(io.BytesIO(view.image_bytes)) as image:
        cropped = image.crop(tuple(int(value) for value in values))
        buffer = io.BytesIO()
        cropped.save(buffer, format="PNG")
    return ReadingRegion(view, box, buffer.getvalue())
