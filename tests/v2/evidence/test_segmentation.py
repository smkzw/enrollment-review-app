"""密集视觉页水平分段的确定性与完整覆盖测试。"""
from __future__ import annotations

from io import BytesIO
from itertools import pairwise

import pytest
from PIL import Image, ImageDraw

from app.evidence.segmentation import SegmentationConfig, segment_page_image


def _png(width: int, height: int, *, dense: bool) -> bytes:
    image = Image.new("RGB", (width, height), "white")
    if dense:
        draw = ImageDraw.Draw(image)
        for y in range(12, height - 12, 38):
            draw.rectangle((40, y, width - 40, y + 18), fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_ordinary_page_keeps_original_bytes_exactly() -> None:
    original = _png(900, 1600, dense=False)
    plan = segment_page_image(original)

    assert plan.dense is False
    assert len(plan.segments) == 1
    assert plan.segments[0].image_bytes == original
    assert (plan.segments[0].y0, plan.segments[0].y1) == (0, 1600)


def test_standard_high_resolution_page_keeps_full_reading_order() -> None:
    original = _png(1200, 3600, dense=True)

    plan = segment_page_image(original)

    assert plan.dense is False
    assert len(plan.segments) == 1
    assert plan.segments[0].image_bytes == original


def test_standard_a4_portrait_is_not_treated_as_stitched_when_height_is_large() -> None:
    original = _png(900, 1273, dense=True)

    plan = segment_page_image(
        original,
        config=SegmentationConfig(min_page_height=1),
    )

    assert plan.dense is False
    assert len(plan.segments) == 1
    assert plan.segments[0].image_bytes == original


def test_long_stitched_page_segments_are_stable_ordered_and_gap_free() -> None:
    original = _png(1200, 7200, dense=True)

    first = segment_page_image(original)
    second = segment_page_image(original)

    assert first.dense is True
    assert len(first.segments) > 1
    assert first.audit_payload() == second.audit_payload()
    bands: dict[tuple[int, int], list] = {}
    for segment in first.segments:
        bands.setdefault((segment.y0, segment.y1), []).append(segment)
    ordered_bands = sorted(bands)
    assert ordered_bands[0][0] == 0
    assert ordered_bands[-1][1] == first.page_height
    for left, right in pairwise(ordered_bands):
        assert left[1] == right[0]
    for columns in bands.values():
        assert columns[0].x0 == 0
        assert columns[-1].x1 == first.page_width
        for left, right in pairwise(columns):
            assert left.x1 == right.x0
    assert [segment.index for segment in first.segments] == list(
        range(len(first.segments))
    )
    assert all(segment.y1 > segment.y0 for segment in first.segments)
    assert all(segment.x1 > segment.x0 for segment in first.segments)
    assert all(segment.y1 - segment.y0 <= 1600 for segment in first.segments)
    assert all(segment.crop_y0 <= segment.y0 for segment in first.segments)
    assert all(segment.crop_y1 >= segment.y1 for segment in first.segments)


@pytest.mark.parametrize("width,height", [(4930, 3428), (4721, 3257)])
def test_realistic_dense_landscape_pages_remain_single_full_page(
    width: int, height: int
) -> None:
    original = _png(width, height, dense=True)

    plan = segment_page_image(original)

    assert plan.dense is False
    assert len(plan.segments) == 1
    assert plan.segments[0].image_bytes == original


def test_config_change_changes_segmentation_decision() -> None:
    original = _png(900, 1600, dense=True)
    ordinary = segment_page_image(original)
    forced = segment_page_image(
        original,
        config=SegmentationConfig(
            min_page_height=1,
            min_active_row_ratio=0,
            min_ink_ratio=0,
            target_segment_height=500,
            min_segment_height=300,
            max_segment_height=700,
            max_segments=8,
        ),
    )

    assert ordinary.dense is False
    assert forced.dense is True
    assert len(forced.segments) > 1
