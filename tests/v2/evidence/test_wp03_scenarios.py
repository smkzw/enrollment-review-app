"""WP03 场景验收补充钉扎：A08（遮盖不失效、不生成补字）与 A09（显式缺页、
记录日期与事件日期分离）。

A02–A07 的机制与测试已在既有套件中（旋转坐标、重复文本降级、分段OCR、
手写对账主A优先、标量语法、单位必填合同），本文件只补齐无确定性验证的
两个薄弱场景，防止回归。
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.domain.contracts.enums import FactPolarity, ProfileLane
from app.domain.contracts.facts import AssertionBasis, ClinicalFactCandidateV2
from app.domain.contracts.enums import PageArtifactStatus
from app.evidence.paging import page_source_document
from app.evidence.risk import (
    OCR_RISK_LEVEL_MATRIX,
    OcrRiskKind,
    OcrRiskLevel,
    scan_ocr_risks,
    would_block_activation,
)


# ---------------------------------------------------------------- A08 遮盖

def test_low_confidence_is_informational_and_never_blocks_activation() -> None:
    """反光/涂改产生的低置信标记不得使整份病例处理失效（不阻断激活）。"""
    assert (
        OCR_RISK_LEVEL_MATRIX[OcrRiskKind.LOW_CONFIDENCE] is OcrRiskLevel.INFORMATIONAL
    )
    flags = scan_ocr_risks("阴影区域文字〔无法辨认〕其余正常")
    low_confidence_blockers = [
        f for f in flags if f.level is OcrRiskLevel.BLOCKING
    ]
    # 即使页面存在无法辨认片段，也不得仅因低置信而阻断。
    assert not low_confidence_blockers or any(
        f.kind is not OcrRiskKind.LOW_CONFIDENCE for f in low_confidence_blockers
    )


def test_ocr_prompt_forbids_synthesized_characters() -> None:
    """OCR提示合同钉扎：无法辨认必须显式标记，禁止补字/复写。"""
    from app.evidence.ocr_adapter import DEFAULT_PROMPT

    assert "〔无法辨认〕" in DEFAULT_PROMPT
    assert "不得重复生成" in DEFAULT_PROMPT
    assert "不总结、不推断、不改写" in DEFAULT_PROMPT


# ---------------------------------------------------------------- A09 跨页/缺页

def test_unknown_media_yields_explicit_failed_page_not_silent_drop() -> None:
    """未知类别必须产出显式失败页，缺页不得伪装成成功占位或静默消失。"""
    plan = page_source_document(
        content=b"not-a-real-file", media_kind="definitely-unknown",
        source_sha256="a" * 64,
    )
    assert plan.page_total >= 1
    statuses = {page.status for page in plan.pages}
    assert PageArtifactStatus.FAILED in statuses
    failed = [page for page in plan.pages if page.status is PageArtifactStatus.FAILED]
    assert all(page.failure_reason for page in failed)


def test_empty_content_yields_explicit_failed_page() -> None:
    plan = page_source_document(
        content=b"", media_kind="pdf", source_sha256="b" * 64,
    )
    failed = [page for page in plan.pages if page.status is PageArtifactStatus.FAILED]
    assert failed, "空内容必须显式失败，不得产出空成功页清单"


def _candidate(**overrides):
    fields = dict(
        candidate_id="cand-1",
        run_id="run-1",
        call_id="call-1",
        fact_type="hemoglobin",
        polarity=FactPolarity.AFFIRMED,
        asserted_object="受试者31001",
        raw_value="130",
        canonical_value="130",
        unit="g/L",
        record_time=datetime(2026, 6, 30, 8, 0, tzinfo=UTC),
        locator_ids=["loc-1"],
        candidate_source_semantics="ocr_primary",
        assertion_basis=AssertionBasis(
            asserted_object="受试者31001",
            assertion_text="血红蛋白130 g/L",
            locator_id="loc-1",
            source_text_sha256="c" * 64,
        ),
        model_uncertainty=0.1,
        created_at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    fields.update(overrides)
    return ClinicalFactCandidateV2.model_validate(fields)


def test_record_time_is_utc_and_distinct_from_event_date_range() -> None:
    """记录时刻（UTC）与事件日期区间是两个字段：记录日期不冒充事件日期。"""
    candidate = _candidate()
    dumped = candidate.model_dump(mode="json")
    assert dumped["record_time"] == "2026-06-30T08:00:00Z"
    assert "date_range" not in dumped or dumped["date_range"] is None


def test_record_time_naive_datetime_rejected() -> None:
    """记录时刻必须显式带时区；无时区时间不得静默采用。"""
    with pytest.raises(ValidationError):
        _candidate(record_time=datetime(2026, 6, 30, 8, 0))


def test_record_time_non_utc_offset_rejected() -> None:
    with pytest.raises(ValidationError):
        _candidate(
            record_time=datetime(2026, 6, 30, 8, 0, tzinfo=timezone(timedelta(hours=8))),
        )
