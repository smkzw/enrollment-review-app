"""Slice 4.4 occurrence-aware 定位引擎确定性测试（WP-44B）。

覆盖 §8.1 定位诚实性与 §4.2 重复文本规则：可信原始范围直接定位该 occurrence；
只给字符串时按出现次数 TEXT_RANGE / PAGE_EXCERPT（重复降级）/ PAGE_ONLY；
身份按范围/锚点确定性计算，同页两处相同文本以不同范围各自定位互不碰撞；
0 个命中绝不伪装为布局通过。
"""
from __future__ import annotations

from hashlib import sha256

import pytest

from app.domain.contracts.enums import (
    DisambiguationOutcome,
    LocatorPrecision,
    LocatorSourceLayer,
)
from app.evidence.locator import (
    locate_in_text,
    occurrence_locator_id,
)

TEXT = "AST 3.5 且 AST 3.5 或 总胆红素 2.0"


def test_unique_string_maps_to_text_range():
    decision = locate_in_text(TEXT, excerpt="总胆红素")
    assert decision.precision == LocatorPrecision.TEXT_RANGE
    assert decision.disambiguation == DisambiguationOutcome.UNIQUE_MATCH
    assert TEXT[decision.text_start:decision.text_end] == "总胆红素"


def test_repeated_string_degrades_to_page_excerpt():
    decision = locate_in_text(TEXT, excerpt="AST")
    assert decision.precision == LocatorPrecision.PAGE_EXCERPT
    assert decision.disambiguation == DisambiguationOutcome.REPEATED_TEXT_DEGRADED
    assert decision.excerpt == "AST"
    assert "多处相同文本" in (decision.degradation_reason or "")


def test_overlapping_repeated_string_degrades_to_page_excerpt():
    decision = locate_in_text("AAA", excerpt="AA")
    assert decision.precision == LocatorPrecision.PAGE_EXCERPT
    assert decision.disambiguation == DisambiguationOutcome.REPEATED_TEXT_DEGRADED


def test_overlapping_repeated_string_with_whitespace_degrades():
    decision = locate_in_text("A A A", excerpt="AA")
    assert decision.precision == LocatorPrecision.PAGE_EXCERPT
    assert decision.disambiguation == DisambiguationOutcome.REPEATED_TEXT_DEGRADED


def test_not_found_degrades_to_page_only():
    decision = locate_in_text(TEXT, excerpt="不存在")
    assert decision.precision == LocatorPrecision.PAGE_ONLY
    assert decision.disambiguation == DisambiguationOutcome.NOT_FOUND
    assert decision.text_start is None and decision.text_end is None
    assert decision.excerpt is None


def test_trusted_range_locates_that_occurrence():
    # 明确指定第一处 AST 的 occurrence 范围。
    decision = locate_in_text(TEXT, excerpt="AST", text_start=0, text_end=3)
    assert decision.precision == LocatorPrecision.TEXT_RANGE
    assert decision.disambiguation == DisambiguationOutcome.UNIQUE_MATCH
    assert (decision.text_start, decision.text_end) == (0, 3)


def test_trusted_range_second_occurrence():
    decision = locate_in_text(TEXT, excerpt="AST", text_start=10, text_end=13)
    assert (decision.text_start, decision.text_end) == (10, 13)


def test_range_mismatch_excerpt_rejected():
    with pytest.raises(ValueError, match="逐字等于"):
        locate_in_text(TEXT, excerpt="AST", text_start=0, text_end=4)


def test_range_only_derives_excerpt():
    decision = locate_in_text(TEXT, excerpt=None, text_start=10, text_end=13)
    assert decision.excerpt == "AST"
    assert decision.precision == LocatorPrecision.TEXT_RANGE


def test_range_out_of_bounds_rejected():
    with pytest.raises(ValueError, match="范围必须有效"):
        locate_in_text(TEXT, excerpt="AST", text_start=0, text_end=999)


def test_occurrence_ids_distinct_for_distinct_ranges():
    sha_of = sha256(TEXT.encode("utf-8")).hexdigest()
    first = occurrence_locator_id(
        page_artifact_id="pa-1", source_layer=LocatorSourceLayer.RAW_OCR,
        source_text_sha256=sha_of, precision=LocatorPrecision.TEXT_RANGE,
        target_id="t", text_start=0, text_end=3,
    )
    second = occurrence_locator_id(
        page_artifact_id="pa-1", source_layer=LocatorSourceLayer.RAW_OCR,
        source_text_sha256=sha_of, precision=LocatorPrecision.TEXT_RANGE,
        target_id="t", text_start=9, text_end=12,
    )
    assert first != second


def test_occurrence_id_same_range_deterministic():
    sha_of = sha256(TEXT.encode("utf-8")).hexdigest()
    a = occurrence_locator_id(
        page_artifact_id="pa-1", source_layer=LocatorSourceLayer.RAW_OCR,
        source_text_sha256=sha_of, precision=LocatorPrecision.TEXT_RANGE,
        target_id="t", text_start=0, text_end=3,
    )
    b = occurrence_locator_id(
        page_artifact_id="pa-1", source_layer=LocatorSourceLayer.RAW_OCR,
        source_text_sha256=sha_of, precision=LocatorPrecision.TEXT_RANGE,
        target_id="t", text_start=0, text_end=3,
    )
    assert a == b


def test_occurrence_id_bbox_requires_range():
    with pytest.raises(ValueError, match="范围"):
        occurrence_locator_id(
            page_artifact_id="pa-1", source_layer=LocatorSourceLayer.RAW_OCR,
            source_text_sha256="a" * 64, precision=LocatorPrecision.BBOX,
            target_id="t",
        )


def test_page_only_distinct_targets_distinct_ids():
    sha_of = sha256(TEXT.encode("utf-8")).hexdigest()
    a = occurrence_locator_id(
        page_artifact_id="pa-1", source_layer=LocatorSourceLayer.RAW_OCR,
        source_text_sha256=sha_of, precision=LocatorPrecision.PAGE_ONLY,
        target_id="t-a", disambiguation=DisambiguationOutcome.NOT_FOUND,
        degradation_reason="未找到",
    )
    b = occurrence_locator_id(
        page_artifact_id="pa-1", source_layer=LocatorSourceLayer.RAW_OCR,
        source_text_sha256=sha_of, precision=LocatorPrecision.PAGE_ONLY,
        target_id="t-b", disambiguation=DisambiguationOutcome.NOT_FOUND,
        degradation_reason="未找到",
    )
    assert a != b
