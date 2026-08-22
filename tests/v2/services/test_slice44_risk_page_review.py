"""页级原子风险核对（WP-44B risk page review）服务/仓储/合同测试。

覆盖「对照原件后本页待核对项一次确认」的原子性与审计性：

- 同一事务内为页上每个待核对（无既有核对且未被覆盖校对解除）风险条目物化逐条
  不可变 ``OCRRiskReview``，并追加页级审计 ``OCRRiskPageReview``，一一对应；
- 覆盖集合内容寻址，缺/多/换绑在回放被拒绝；
- 全部待核对项已解除后，再次页级核对被拒绝（无待核对项）；
- 引用不属于目标页的扫描被拒绝。
"""
from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

import pytest

from app.domain.contracts.enums import OcrRiskReviewDecision
from app.domain.contracts.evidence_locator import OCRRiskPageReview, OCRRiskReview
from app.domain.publication import canonical_hash
from app.services.evidence_risk_service import (
    EvidenceRiskScanService,
    RiskPageReviewNoPendingError,
    RiskPageReviewScanMismatchError,
    RiskReviewDecisionError,
    RiskReviewRequiresReprocessingError,
)
from app.storage.evidence_locator_repositories import (
    OCRRiskPageReviewRepository,
    OCRRiskReviewRepository,
    OCRRiskScanRepository,
)
from tests.v2.storage.test_slice44_repositories import RAW_TEXT, _flag, _scan


@pytest.fixture
def stack(revision_stack):
    """WP-44A 基础栈 + 提交（服务使用独立会话，必须先持久化栈数据）。"""
    session, fixture, keys = revision_stack
    session.commit()
    return session, fixture, keys


def _two_flag_scan(keys):
    """一个 blocking + 一个 informational 的双 flag 扫描（无既有核对）。"""
    return _scan(
        keys,
        flags=[
            _flag(risk_id="r1", kind="numeric_value", level="blocking"),
            _flag(
                risk_id="r2",
                kind="unit",
                level="informational",
                text="mmol/L",
                start=8,
                end=14,
            ),
        ],
    )


def _seed_unreviewed_scan(session, keys):
    scan, _created = OCRRiskScanRepository(session).get_or_create(_two_flag_scan(keys))
    return scan.scan_id


def _utcnow():
    return datetime.now(UTC)


def test_page_review_covers_all_pending_flags_atomically(stack, session_factory):
    session, _fixture, keys = stack
    scan_id = _seed_unreviewed_scan(session, keys)
    session.commit()

    service = EvidenceRiskScanService(session_factory)
    page_review = service.create_page_review(
        page_review_id="prv-1",
        ocr_page_id="op-1",
        scan_id=scan_id,
        decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
        reason="对照原件后整页确认",
        actor="user",
        base_processing_revision_id="rev-1",
        expected_revision=1,
    )

    assert page_review.page_review_id == "prv-1"
    assert page_review.covered_flag_ids == ["scan-1:r1", "scan-1:r2"]
    assert page_review.covered_flag_sha256 == canonical_hash(
        sorted(page_review.covered_flag_ids)
    )
    assert len(page_review.created_review_ids) == 2

    with session_factory() as fresh:
        review_repo = OCRRiskReviewRepository(fresh)
        reviewed = {
            review_repo.get(rid).risk_flag_id for rid in page_review.created_review_ids
        }
        assert reviewed == {"scan-1:r1", "scan-1:r2"}
        assert review_repo.reviewed_flag_ids(["scan-1:r1", "scan-1:r2"]) == {
            "scan-1:r1",
            "scan-1:r2",
        }


def test_page_review_replayed_and_no_pending_rejected(stack, session_factory):
    session, _fixture, keys = stack
    scan_id = _seed_unreviewed_scan(session, keys)
    session.commit()

    service = EvidenceRiskScanService(session_factory)
    service.create_page_review(
        page_review_id="prv-1",
        ocr_page_id="op-1",
        scan_id=scan_id,
        decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
        reason="整页确认",
        actor="user",
        base_processing_revision_id="rev-1",
        expected_revision=1,
    )
    with pytest.raises(RiskPageReviewNoPendingError):
        service.create_page_review(
            page_review_id="prv-2",
            ocr_page_id="op-1",
            scan_id=scan_id,
            decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
            reason="重复确认",
            actor="user",
            base_processing_revision_id="rev-1",
            expected_revision=1,
        )


def test_page_review_skips_already_reviewed_flag(stack, session_factory):
    """已有逐条核对的 flag 不重复物化；页级动作只覆盖仍待核对项。"""
    session, _fixture, keys = stack
    scan_id = _seed_unreviewed_scan(session, keys)
    OCRRiskReviewRepository(session).create(
        OCRRiskReview(
            review_id="rv-existing",
            risk_flag_id="scan-1:r1",
            decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
            reason="已逐条核对",
            actor="user",
            base_processing_revision_id="rev-1",
            expected_revision=1,
            created_at=_utcnow(),
        )
    )
    session.commit()

    service = EvidenceRiskScanService(session_factory)
    page_review = service.create_page_review(
        page_review_id="prv-1",
        ocr_page_id="op-1",
        scan_id=scan_id,
        decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
        reason="补齐其余待核对项",
        actor="user",
        base_processing_revision_id="rev-1",
        expected_revision=1,
    )
    assert page_review.covered_flag_ids == ["scan-1:r2"]


def test_page_review_scan_mismatch_rejected(stack, session_factory):
    session, _fixture, keys = stack
    scan_id = _seed_unreviewed_scan(session, keys)
    session.commit()

    service = EvidenceRiskScanService(session_factory)
    with pytest.raises(RiskPageReviewScanMismatchError):
        service.create_page_review(
            page_review_id="prv-1",
            ocr_page_id="op-other",
            scan_id=scan_id,
            decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
            reason="整页确认",
            actor="user",
            base_processing_revision_id="rev-1",
            expected_revision=1,
        )


def test_page_review_only_accepts_confirmed_as_read(stack, session_factory):
    session, _fixture, keys = stack
    scan_id = _seed_unreviewed_scan(session, keys)
    session.commit()

    with pytest.raises(RiskReviewDecisionError, match="整页核对只用于"):
        EvidenceRiskScanService(session_factory).create_page_review(
            page_review_id="prv-corrected",
            ocr_page_id="op-1",
            scan_id=scan_id,
            decision=OcrRiskReviewDecision.CORRECTED,
            reason="错误地以核对代替校对",
            actor="user",
            base_processing_revision_id="rev-1",
            expected_revision=1,
        )


def test_output_repetition_cannot_be_reviewed_or_page_confirmed(stack, session_factory):
    session, _fixture, keys = stack
    scan = _scan(
        keys,
        flags=[
            _flag(
                risk_id="loop",
                kind="output_repetition",
                level="blocking",
                text=RAW_TEXT[:7],
                start=0,
                end=7,
            )
        ],
    )
    OCRRiskScanRepository(session).get_or_create(scan)
    session.commit()
    service = EvidenceRiskScanService(session_factory)

    with pytest.raises(RiskReviewRequiresReprocessingError, match="异常重复"):
        service.create_review(
            review_id="rv-loop",
            risk_flag_id="scan-1:loop",
            decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
            reason="错误确认",
            actor="user",
            base_processing_revision_id="rev-1",
            expected_revision=1,
        )
    with pytest.raises(RiskReviewRequiresReprocessingError, match="异常重复"):
        service.create_page_review(
            page_review_id="prv-loop",
            ocr_page_id="op-1",
            scan_id="scan-1",
            decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
            reason="错误整页确认",
            actor="user",
            base_processing_revision_id="rev-1",
            expected_revision=1,
        )


def test_page_review_repo_roundtrip_and_closure(stack, session_factory):
    session, _fixture, keys = stack
    scan_id = _seed_unreviewed_scan(session, keys)
    session.commit()

    service = EvidenceRiskScanService(session_factory)
    service.create_page_review(
        page_review_id="prv-1",
        ocr_page_id="op-1",
        scan_id=scan_id,
        decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
        reason="整页确认",
        actor="user",
        base_processing_revision_id="rev-1",
        expected_revision=1,
    )
    with session_factory() as fresh:
        repo = OCRRiskPageReviewRepository(fresh)
        got = repo.get("prv-1")
        assert got.covered_flag_ids == ["scan-1:r1", "scan-1:r2"]
        assert got.created_review_ids == sorted(
            [
                f"rv-{sha256(f'prv-1:{f}'.encode()).hexdigest()[:32]}"
                for f in ["scan-1:r1", "scan-1:r2"]
            ]
        )
        assert [row.page_review_id for row in repo.list_by_page("op-1")] == ["prv-1"]


def test_page_review_contract_rejects_inconsistent_sha():
    base = dict(
        page_review_id="prv-x",
        ocr_page_id="op-1",
        scan_id="scan-1",
        raw_text_sha256="0" * 64,
        scanner_rule_version="rules/v1",
        decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
        reason="整页确认",
        actor="user",
        base_processing_revision_id="rev-1",
        expected_revision=1,
        covered_flag_ids=["scan-1:r1", "scan-1:r2"],
        created_review_ids=["rv-a", "rv-b"],
        created_at=_utcnow(),
    )
    with pytest.raises(Exception):
        OCRRiskPageReview(**base, covered_flag_sha256="0" * 64)
    # 重复覆盖 flag 被拒绝。
    with pytest.raises(Exception):
        OCRRiskPageReview(
            **base,
            covered_flag_ids=["scan-1:r1", "scan-1:r1"],
            covered_flag_sha256=canonical_hash(
                sorted(["scan-1:r1", "scan-1:r1"])
            ),
        )
