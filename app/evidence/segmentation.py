"""密集视觉页的确定性阅读顺序分段。

仅使用页面尺寸与像素密度判断是否分段，不读取文件名、项目、中心或临床内容。
普通页面保持原始单段字节；密集长页切为行优先网格。每个网格保存无重叠核心范围，
真实送入识别的裁剪则带少量四周上下文，避免轻微倾斜页面在边界处切断字形。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from io import BytesIO
from itertools import pairwise
from typing import cast

from PIL import Image, ImageOps

SEGMENTATION_ALGORITHM_VERSION = "dense-reading-order/v5"


@dataclass(frozen=True)
class SegmentationConfig:
    """冻结的通用分段参数；任一字段变化都必须进入识别配置指纹。"""

    analysis_width: int = 960
    dark_pixel_threshold: int = 205
    active_row_ink_ratio: float = 0.004
    blank_row_ink_ratio: float = 0.0015
    blank_column_ink_ratio: float = 0.012
    min_page_height: int = 5000
    min_stitched_page_aspect_ratio: float = 1.6
    min_active_row_ratio: float = 0.42
    min_ink_ratio: float = 0.025
    # 标准高分辨率 A4/横向病历页由模型整页保序识别；只有真正的超长拼接页
    # 才进入全宽纵向兜底。上下文用于补全切点附近字形，绝不做多列重排。
    target_segment_height: int = 1200
    min_segment_height: int = 600
    max_segment_height: int = 1600
    max_segments: int = 16
    target_segment_width: int = 1250
    min_segment_width: int = 600
    max_segment_width: int = 1400
    max_columns: int = 1
    max_segment_aspect_ratio: float = 12.0
    horizontal_context_margin: int = 0
    vertical_context_margin: int = 32

    def fingerprint_payload(self) -> dict[str, object]:
        return {
            "algorithm_version": SEGMENTATION_ALGORITHM_VERSION,
            **asdict(self),
        }


DEFAULT_SEGMENTATION_CONFIG = SegmentationConfig()


@dataclass(frozen=True)
class PageSegment:
    index: int
    row_index: int
    column_index: int
    x0: int
    x1: int
    y0: int
    y1: int
    crop_x0: int
    crop_x1: int
    crop_y0: int
    crop_y1: int
    image_bytes: bytes
    image_sha256: str


@dataclass(frozen=True)
class SegmentationPlan:
    algorithm_version: str
    page_width: int
    page_height: int
    dense: bool
    ink_ratio: float
    active_row_ratio: float
    segments: tuple[PageSegment, ...]

    def audit_payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "page_width": self.page_width,
            "page_height": self.page_height,
            "dense": self.dense,
            "ink_ratio": round(self.ink_ratio, 8),
            "active_row_ratio": round(self.active_row_ratio, 8),
            "segments": [
                {
                    "index": item.index,
                    "row_index": item.row_index,
                    "column_index": item.column_index,
                    "x0": item.x0,
                    "x1": item.x1,
                    "y0": item.y0,
                    "y1": item.y1,
                    "crop_x0": item.crop_x0,
                    "crop_x1": item.crop_x1,
                    "crop_y0": item.crop_y0,
                    "crop_y1": item.crop_y1,
                    "image_sha256": item.image_sha256,
                }
                for item in self.segments
            ],
        }


def _row_ink_ratios(image: Image.Image, config: SegmentationConfig) -> list[float]:
    gray = ImageOps.grayscale(image)
    if gray.width > config.analysis_width:
        # 只压缩横向像素，保留原始纵向分辨率。若按宽高同比缩放，高分辨率病历
        # 页的多行文字会被压进同一分析行，行间留白消失，切点可能穿过字形并诱发
        # 模型对半行文字重复扩写。
        gray = gray.resize((config.analysis_width, gray.height), Image.Resampling.BILINEAR)
    width, height = gray.size
    pixels = gray.load()
    if pixels is None:
        raise ValueError("无法读取页面像素")
    return [
        sum(
            1
            for x in range(width)
            if cast(int, pixels[x, y]) < config.dark_pixel_threshold
        )
        / width
        for y in range(height)
    ]


def _best_cut(
    ratios: list[float],
    *,
    source_height: int,
    current_y: int,
    config: SegmentationConfig,
) -> int:
    scale = len(ratios) / source_height
    lower = current_y + config.min_segment_height
    upper = min(
        current_y + config.max_segment_height,
        source_height - config.min_segment_height,
    )
    target = min(current_y + config.target_segment_height, upper)
    if upper <= lower:
        return source_height
    low_row = max(0, round(lower * scale))
    high_row = min(len(ratios) - 1, round(upper * scale))
    target_row = round(target * scale)

    runs: list[tuple[int, int]] = []
    run_start: int | None = None
    for row in range(low_row, high_row + 1):
        if ratios[row] <= config.blank_row_ink_ratio:
            if run_start is None:
                run_start = row
        elif run_start is not None:
            runs.append((run_start, row - 1))
            run_start = None
    if run_start is not None:
        runs.append((run_start, high_row))
    if runs:
        start, end = min(
            runs,
            key=lambda run: (
                abs(((run[0] + run[1]) // 2) - target_row),
                -(run[1] - run[0]),
            ),
        )
        cut_row = (start + end) // 2
    else:
        cut_row = min(
            range(low_row, high_row + 1),
            key=lambda row: (ratios[row], abs(row - target_row)),
        )
    return min(upper, max(lower, round(cut_row / scale)))


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG", compress_level=6)
    return buffer.getvalue()


def segment_page_image(
    image_bytes: bytes,
    *,
    config: SegmentationConfig = DEFAULT_SEGMENTATION_CONFIG,
) -> SegmentationPlan:
    """返回稳定分段计划；解码失败由 Pillow 异常如实交给调用方处理。"""
    with Image.open(BytesIO(image_bytes)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        width, height = image.size
        ratios = _row_ink_ratios(image, config)
        ink_ratio = sum(ratios) / len(ratios)
        active_ratio = (
            sum(1 for ratio in ratios if ratio >= config.active_row_ink_ratio)
            / len(ratios)
        )
        dense = (
            height >= config.min_page_height
            and height / width >= config.min_stitched_page_aspect_ratio
            and active_ratio >= config.min_active_row_ratio
            and ink_ratio >= config.min_ink_ratio
        )
        if not dense:
            single = PageSegment(
                index=0,
                row_index=0,
                column_index=0,
                x0=0,
                x1=width,
                y0=0,
                y1=height,
                crop_x0=0,
                crop_x1=width,
                crop_y0=0,
                crop_y1=height,
                image_bytes=image_bytes,
                image_sha256=sha256(image_bytes).hexdigest(),
            )
            return SegmentationPlan(
                SEGMENTATION_ALGORITHM_VERSION,
                width,
                height,
                False,
                ink_ratio,
                active_ratio,
                (single,),
            )

        row_boundaries = [0]
        while (
            height - row_boundaries[-1] > config.max_segment_height
            and len(row_boundaries) < config.max_segments
        ):
            cut = _best_cut(
                ratios,
                source_height=height,
                current_y=row_boundaries[-1],
                config=config,
            )
            if cut <= row_boundaries[-1] or cut >= height:
                break
            row_boundaries.append(cut)
        row_boundaries.append(height)
        segments: list[PageSegment] = []
        for row_index, (y0, y1) in enumerate(pairwise(row_boundaries)):
            crop_y0 = max(0, y0 - config.vertical_context_margin)
            crop_y1 = min(height, y1 + config.vertical_context_margin)
            crop_bytes = _png_bytes(image.crop((0, crop_y0, width, crop_y1)))
            segments.append(
                PageSegment(
                    index=len(segments),
                    row_index=row_index,
                    column_index=0,
                    x0=0,
                    x1=width,
                    y0=y0,
                    y1=y1,
                    crop_x0=0,
                    crop_x1=width,
                    crop_y0=crop_y0,
                    crop_y1=crop_y1,
                    image_bytes=crop_bytes,
                    image_sha256=sha256(crop_bytes).hexdigest(),
                )
            )
        return SegmentationPlan(
            SEGMENTATION_ALGORITHM_VERSION,
            width,
            height,
            len(segments) > 1,
            ink_ratio,
            active_ratio,
            tuple(segments),
        )
