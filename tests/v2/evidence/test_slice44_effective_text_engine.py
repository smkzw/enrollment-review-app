"""Slice 4.4 有效文本投影引擎确定性测试（WP-44B）。

覆盖 §8.3 校对与回放：原 OCR raw_text/hash 永不改写；投影按原始 offset 确定性
应用并重算内容哈希；重叠校对拒绝；每次读取从不可变 raw + 所选校对重算（不链式
沿用旧投影）。
"""
from __future__ import annotations

from hashlib import sha256

import pytest

from app.domain.contracts.evidence_locator import CorrectionRecord
from app.evidence.effective_text import (
    ProjectionOverlapError,
    project_effective_text,
)

RAW = "ALT 5.6 mmol/L 且 AST 3.5 mmol/L"


def _corr(correction_id, start, end, original, corrected, **overrides):
    base = {
        "correction_id": correction_id,
        "ocr_page_id": "op-1",
        "raw_text_sha256": sha256(RAW.encode("utf-8")).hexdigest(),
        "text_start": start,
        "text_end": end,
        "original_text": original,
        "corrected_text": corrected,
        "change_kind": "decimal",
        "requires_confirmation": True,
        "confirmation_actor": "user",
        "confirmation_at": "2026-08-19T12:00:00+00:00",
        "reason": "r",
        "actor": "user",
        "base_processing_revision_id": "rev-1",
        "created_at": "2026-08-19T12:00:00+00:00",
    }
    base.update(overrides)
    return CorrectionRecord(**base)


def test_no_corrections_is_raw_text_with_hash():
    projection = project_effective_text(RAW, [])
    assert projection.effective_text == RAW
    assert projection.effective_text_sha256 == sha256(RAW.encode("utf-8")).hexdigest()
    assert projection.applied == ()


def test_single_correction_replaces_range():
    projection = project_effective_text(RAW, [_corr("c1", 4, 7, "5.6", "5.60")])
    assert projection.effective_text == "ALT 5.60 mmol/L 且 AST 3.5 mmol/L"
    assert projection.effective_text_sha256 == sha256(
        projection.effective_text.encode("utf-8")
    ).hexdigest()


def test_multiple_non_overlapping_applied_in_original_order():
    corrections = [
        _corr("c1", 4, 7, "5.6", "5.60"),
        _corr("c2", 21, 24, "3.5", "3.50"),
    ]
    projection = project_effective_text(RAW, corrections)
    assert projection.effective_text == "ALT 5.60 mmol/L 且 AST 3.50 mmol/L"
    assert [c.correction_id for c in projection.applied] == ["c1", "c2"]


def test_insertions_and_adjacent_replacement_project_deterministically():
    corrections = [
        _corr("insert-after", 7, 7, "", "（复核）", change_kind="other_text",
              requires_confirmation=False, confirmation_actor=None,
              confirmation_at=None),
        _corr("replace", 4, 7, "5.6", "5.60"),
        _corr("insert-before", 4, 4, "", "漏：", change_kind="other_text",
              requires_confirmation=False, confirmation_actor=None,
              confirmation_at=None),
    ]
    projection = project_effective_text(RAW, corrections)
    assert projection.effective_text == "ALT 漏：5.60（复核） mmol/L 且 AST 3.5 mmol/L"
    assert [c.correction_id for c in projection.applied] == [
        "insert-before",
        "replace",
        "insert-after",
    ]
    assert project_effective_text(RAW, reversed(corrections)) == projection


def test_middle_source_anchor_inserts_at_exact_effective_text_position():
    insertion = _corr(
        "middle-insert",
        4,
        4,
        "",
        "漏识别：",
        change_kind="other_text",
        requires_confirmation=False,
        confirmation_actor=None,
        confirmation_at=None,
    )
    projection = project_effective_text(RAW, [insertion])
    assert projection.effective_text == "ALT 漏识别：5.6 mmol/L 且 AST 3.5 mmol/L"


def test_two_effective_root_insertions_at_same_position_are_rejected():
    insertions = [
        _corr("insert-a", 4, 4, "", "漏", change_kind="other_text",
              requires_confirmation=False, confirmation_actor=None,
              confirmation_at=None),
        _corr("insert-b", 4, 4, "", "行", change_kind="other_text",
              requires_confirmation=False, confirmation_actor=None,
              confirmation_at=None),
    ]
    with pytest.raises(ProjectionOverlapError, match="重叠"):
        project_effective_text(RAW, insertions)


def test_projection_is_deterministic_and_recomputed_each_call():
    corrections = [_corr("c1", 4, 7, "5.6", "5.60")]
    first = project_effective_text(RAW, corrections)
    second = project_effective_text(RAW, corrections)
    assert first.effective_text_sha256 == second.effective_text_sha256
    # 每次调用都从不可变 raw 重算（无缓存/无状态）。
    assert first.effective_text == second.effective_text


def test_overlapping_corrections_rejected():
    overlapping = [
        _corr("c1", 4, 8, "5.6 ", "5.60 "),
        _corr("c2", 6, 9, "6 m", "6.0 "),
    ]
    with pytest.raises(ProjectionOverlapError, match="重叠"):
        project_effective_text(RAW, overlapping)


def test_wrong_raw_hash_rejected():
    bad = _corr("c1", 4, 7, "5.6", "5.60", raw_text_sha256="b" * 64)
    with pytest.raises(ProjectionOverlapError, match="raw_text_sha256"):
        project_effective_text(RAW, [bad])


def test_out_of_range_rejected():
    bad = _corr("c1", 40, 45, "xxxxx", "yyyyy")
    with pytest.raises(ProjectionOverlapError, match="范围越出"):
        project_effective_text(RAW, [bad])


def test_original_text_mismatch_rejected():
    bad = _corr("c1", 4, 7, "5.7", "5.60")
    with pytest.raises(ProjectionOverlapError, match="原文本"):
        project_effective_text(RAW, [bad])


def test_corrected_must_differ_from_original_rejected():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _corr("c1", 4, 7, "5.6", "5.6")
