"""Slice 4.4 校对覆盖层与有效文本投影服务测试（WP-44B）。

覆盖 §8.3 校对与回放：关键变化缺二次确认拒绝；原 OCR raw_text/hash 永不改写；
supersede 显式替代链；有效文本由不可变 raw + 完整修订所选校对确定性投影、每次
重算哈希；重叠/越界/原文不匹配拒绝。
"""
from __future__ import annotations

from hashlib import sha256

import pytest
from sqlalchemy import event

from app.domain.contracts.enums import (
    CorrectionChangeKind,
    OcrRiskKind,
    OcrRiskLevel,
    OcrRiskReviewDecision,
)
from app.domain.contracts.evidence_locator import (
    CorrectionRecord,
    OcrRiskFlag,
    OCRRiskReview,
)
from app.evidence.risk import OCR_RISK_RULE_VERSION
from app.services.evidence_api_read_service import EvidenceApiReadService
from app.services.evidence_correction_service import (
    CorrectionConfirmationRequiredError,
    CorrectionRangeError,
    EvidenceCorrectionService,
)
from app.storage.evidence_locator_repositories import CorrectionRepository
from app.storage.ocr_models import OCRPageRecord
from tests.v2.storage.test_slice44_repositories import (
    FIXED_UTC,
    RAW_TEXT,
    _correction,
    _closed_revision,
    _scan,
    _seed_two_page_revision,
    sha,
)


@pytest.fixture
def stack(revision_stack):
    session, fixture, keys = revision_stack
    session.commit()
    return session, fixture, keys

def test_key_correction_requires_confirmation(stack, session_factory):
    _session, _fixture, _keys = stack
    service = EvidenceCorrectionService(session_factory)
    with pytest.raises(CorrectionConfirmationRequiredError, match="二次确认"):
        service.create_correction(
            ocr_page_id="op-1",
            text_start=4,
            text_end=7,
            original_text="5.6",
            corrected_text="5.60",
            change_kind=CorrectionChangeKind.DECIMAL,
            reason="确认小数点",
            actor="user",
            base_processing_revision_id="rev-1",
        )

def test_key_correction_with_confirmation_ok_and_ocr_unchanged(stack, session_factory):
    session, _fixture, _keys = stack
    before = session.get(OCRPageRecord, "op-1")
    service = EvidenceCorrectionService(session_factory)
    corr = service.create_correction(
        ocr_page_id="op-1",
        text_start=4,
        text_end=7,
        original_text="5.6",
        corrected_text="5.60",
        change_kind=CorrectionChangeKind.DECIMAL,
        reason="确认小数点",
        actor="user",
        base_processing_revision_id="rev-1",
        confirmation_actor="reviewer",
        confirmation_at="2026-08-19T12:00:00+00:00",
    )
    assert corr.change_kind == CorrectionChangeKind.DECIMAL
    assert corr.requires_confirmation is True
    assert corr.confirmation_actor == "reviewer"
    with session_factory() as fresh:
        page = fresh.get(OCRPageRecord, "op-1")
        assert page.raw_text == RAW_TEXT
        assert page.payload_json == before.payload_json
        assert page.payload_sha256 == before.payload_sha256


def test_key_insertion_uses_existing_confirmation_gate_and_keeps_ocr_unchanged(
    stack, session_factory
):
    session, _fixture, _keys = stack
    before = session.get(OCRPageRecord, "op-1")
    service = EvidenceCorrectionService(session_factory)

    with pytest.raises(CorrectionConfirmationRequiredError, match="二次确认"):
        service.create_correction(
            ocr_page_id="op-1",
            text_start=len(RAW_TEXT),
            text_end=len(RAW_TEXT),
            original_text="",
            corrected_text=" 2026-08-19",
            change_kind=CorrectionChangeKind.DATE,
            reason="补入漏识别日期",
            actor="user",
            base_processing_revision_id="rev-1",
        )

    correction = service.create_correction(
        ocr_page_id="op-1",
        text_start=len(RAW_TEXT),
        text_end=len(RAW_TEXT),
        original_text="",
        corrected_text=" 2026-08-19",
        change_kind=CorrectionChangeKind.DATE,
        reason="补入漏识别日期",
        actor="user",
        base_processing_revision_id="rev-1",
        confirmation_actor="reviewer",
        confirmation_at="2026-08-19T12:00:00+00:00",
    )
    assert correction.text_start == correction.text_end == len(RAW_TEXT)
    assert correction.original_text == ""
    with session_factory() as fresh:
        page = fresh.get(OCRPageRecord, "op-1")
        assert page.raw_text == RAW_TEXT
        assert page.payload_json == before.payload_json
        assert page.payload_sha256 == before.payload_sha256


def test_other_text_cannot_bypass_detected_critical_insertion(stack, session_factory):
    _session, _fixture, _keys = stack
    service = EvidenceCorrectionService(session_factory)
    inserted = "参与者否认2026-03-10使用过全身免疫抑制剂。"

    with pytest.raises(CorrectionConfirmationRequiredError, match="二次确认"):
        service.create_correction(
            ocr_page_id="op-1",
            text_start=len(RAW_TEXT),
            text_end=len(RAW_TEXT),
            original_text="",
            corrected_text=inserted,
            change_kind=CorrectionChangeKind.OTHER_TEXT,
            reason="补入原件中漏识别的一行",
            actor="user",
            base_processing_revision_id="rev-1",
        )

    correction = service.create_correction(
        ocr_page_id="op-1",
        text_start=len(RAW_TEXT),
        text_end=len(RAW_TEXT),
        original_text="",
        corrected_text=inserted,
        change_kind=CorrectionChangeKind.OTHER_TEXT,
        reason="补入原件中漏识别的一行",
        actor="user",
        base_processing_revision_id="rev-1",
        confirmation_actor="reviewer",
        confirmation_at="2026-08-19T12:00:00+00:00",
    )
    assert correction.change_kind == CorrectionChangeKind.OTHER_TEXT
    assert correction.requires_confirmation is True


def test_other_text_cannot_bypass_detected_polarity_replacement(stack, session_factory):
    _session, _fixture, _keys = stack
    service = EvidenceCorrectionService(session_factory)
    raw = "ALT 5.6 mmol/L 且 AST 3.5 mmol/L"
    start = raw.index("且")

    with pytest.raises(CorrectionConfirmationRequiredError, match="二次确认"):
        service.create_correction(
            ocr_page_id="op-1",
            text_start=start,
            text_end=start + 1,
            original_text="且",
            corrected_text="或",
            change_kind=CorrectionChangeKind.OTHER_TEXT,
            reason="核对逻辑连接词",
            actor="user",
            base_processing_revision_id="rev-1",
        )


def test_plain_other_text_still_avoids_unnecessary_confirmation(stack, session_factory):
    _session, _fixture, _keys = stack
    service = EvidenceCorrectionService(session_factory)
    correction = service.create_correction(
        ocr_page_id="op-1",
        text_start=0,
        text_end=3,
        original_text="ALT",
        corrected_text="丙氨酸氨基转移酶",
        change_kind=CorrectionChangeKind.OTHER_TEXT,
        reason="补全检验项目名称",
        actor="user",
        base_processing_revision_id="rev-1",
    )
    assert correction.requires_confirmation is False


def test_base_revision_risk_summary_ignores_review_from_another_revision(
    stack, session_factory
):
    session, _fixture, keys = stack
    from app.storage.evidence_locator_repositories import (
        OCRRiskReviewRepository,
        OCRRiskScanRepository,
    )

    _seed_two_page_revision(session, keys)
    OCRRiskScanRepository(session).get_or_create(_scan(keys))
    OCRRiskReviewRepository(session).create(
        OCRRiskReview(
            review_id="review-other-revision",
            risk_flag_id="scan-1:r1",
            decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
            reason="仅核对另一处理版本",
            actor="user",
            base_processing_revision_id="rev-2p",
            expected_revision=1,
            created_at=FIXED_UTC,
        )
    )
    CorrectionRepository(session).create(
        _correction(
            keys,
            correction_id="correction-other-revision",
            base_processing_revision_id="rev-2p",
        )
    )
    session.commit()

    view = EvidenceApiReadService(
        session_factory,
        artifact_store=keys["artifact_store"],
    ).revision_view("rev-1")
    assert view.risk_flag_count == 1
    assert view.pending_risk_flag_count == 1


def test_base_revision_repetition_risk_stays_pending_after_review_only(
    stack, session_factory
):
    session, _fixture, keys = stack
    from app.storage.evidence_locator_repositories import (
        OCRRiskReviewRepository,
        OCRRiskScanRepository,
    )

    repetition_flag = OcrRiskFlag(
        risk_id="repetition-1",
        kind=OcrRiskKind.OUTPUT_REPETITION,
        level=OcrRiskLevel.BLOCKING,
        text=RAW_TEXT,
        text_start=0,
        text_end=len(RAW_TEXT),
        detail="识别结果存在严重重复",
        rule_version=OCR_RISK_RULE_VERSION,
    )
    scan = _scan(
        keys,
        scan_id="scan-repetition",
        scanner_rule_version=OCR_RISK_RULE_VERSION,
        flags=[repetition_flag],
    )
    OCRRiskScanRepository(session).get_or_create(scan)
    OCRRiskReviewRepository(session).create(
        OCRRiskReview(
            review_id="review-repetition",
            risk_flag_id="scan-repetition:repetition-1",
            decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
            reason="已对照原件",
            actor="user",
            base_processing_revision_id="rev-1",
            expected_revision=1,
            created_at=FIXED_UTC,
        )
    )
    session.commit()

    view = EvidenceApiReadService(
        session_factory,
        artifact_store=keys["artifact_store"],
    ).revision_view("rev-1")
    assert view.risk_flag_count == 1
    assert view.pending_risk_flag_count == 1


def test_base_revision_risk_summary_query_count_is_page_bounded(
    stack, session_factory, migrated_engine
):
    session, _fixture, keys = stack
    _seed_two_page_revision(session, keys)
    session.commit()
    service = EvidenceApiReadService(
        session_factory,
        artifact_store=keys["artifact_store"],
    )
    with session_factory() as read_session:
        from app.storage.ocr_repositories import EvidenceProcessingRevisionRepository

        revisions = EvidenceProcessingRevisionRepository(read_session)
        manifests = {
            revision_id: revisions.get(revision_id).manifest
            for revision_id in ("rev-1", "rev-2p")
        }

    def count_selects(revision_id: str) -> int:
        statements: list[str] = []

        def record_statement(_conn, _cursor, statement, _parameters, _context, _many):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(migrated_engine, "before_cursor_execute", record_statement)
        try:
            with session_factory() as aggregate_session:
                service._risk_counts(
                    aggregate_session,
                    revision_id=revision_id,
                    manifest=manifests[revision_id],
                    complete=None,
                )
        finally:
            event.remove(migrated_engine, "before_cursor_execute", record_statement)
        return len(statements)

    one_page_queries = count_selects("rev-1")
    two_page_queries = count_selects("rev-2p")

    assert two_page_queries == one_page_queries
    assert two_page_queries <= 8


def test_whole_page_submission_persists_only_actual_changed_character(
    stack, session_factory
):
    service = EvidenceCorrectionService(session_factory)
    corrected = RAW_TEXT.replace("且", "或")
    correction = service.create_correction(
        ocr_page_id="op-1",
        text_start=0,
        text_end=len(RAW_TEXT),
        original_text=RAW_TEXT,
        corrected_text=corrected,
        change_kind=CorrectionChangeKind.SEMANTIC_CONNECTOR,
        reason="逐字核对连接词",
        actor="user",
        base_processing_revision_id="rev-1",
        confirmation_actor="reviewer",
        confirmation_at="2026-08-19T12:00:00+00:00",
    )

    changed_at = RAW_TEXT.index("且")
    assert (correction.text_start, correction.text_end) == (
        changed_at,
        changed_at + 1,
    )
    assert correction.original_text == "且"
    assert correction.corrected_text == "或"


def test_minimal_range_preserves_insert_delete_and_rejects_no_change(
    stack, session_factory
):
    service = EvidenceCorrectionService(session_factory)
    inserted = service.create_correction(
        ocr_page_id="op-1",
        text_start=4,
        text_end=7,
        original_text="5.6",
        corrected_text="5.60",
        change_kind=CorrectionChangeKind.DECIMAL,
        reason="补回末位零",
        actor="user",
        base_processing_revision_id="rev-1",
        confirmation_actor="reviewer",
        confirmation_at="2026-08-19T12:00:00+00:00",
    )
    assert inserted.text_start == inserted.text_end == 7
    assert inserted.original_text == ""
    assert inserted.corrected_text == "0"

    deleted = service.create_correction(
        ocr_page_id="op-1",
        text_start=8,
        text_end=14,
        original_text="mmol/L",
        corrected_text="mmol/",
        change_kind=CorrectionChangeKind.UNIT,
        reason="删除多识别字符",
        actor="user",
        base_processing_revision_id="rev-1",
        confirmation_actor="reviewer",
        confirmation_at="2026-08-19T12:00:00+00:00",
    )
    assert (deleted.text_start, deleted.text_end) == (13, 14)
    assert deleted.original_text == "L"
    assert deleted.corrected_text == ""

    with pytest.raises(CorrectionRangeError, match="没有实际变化"):
        service.create_correction(
            ocr_page_id="op-1",
            text_start=0,
            text_end=len(RAW_TEXT),
            original_text=RAW_TEXT,
            corrected_text=RAW_TEXT,
            change_kind=CorrectionChangeKind.OTHER_TEXT,
            reason="无变化",
            actor="user",
            base_processing_revision_id="rev-1",
        )


def test_supersede_chain_binds_same_occurrence(stack, session_factory):
    _session, _fixture, _keys = stack
    service = EvidenceCorrectionService(session_factory)
    first = service.create_correction(
        ocr_page_id="op-1", text_start=4, text_end=7, original_text="5.6",
        corrected_text="5.60", change_kind=CorrectionChangeKind.DECIMAL,
        reason="r", actor="user", base_processing_revision_id="rev-1",
        confirmation_actor="reviewer", confirmation_at="2026-08-19T12:00:00+00:00",
    )
    second = service.supersede_correction(
        supersedes_correction_id=first.correction_id,
        ocr_page_id="op-1", text_start=4, text_end=7, original_text="5.6",
        corrected_text="5.600", change_kind=CorrectionChangeKind.DECIMAL,
        reason="r2", actor="user", base_processing_revision_id="rev-1",
        confirmation_actor="reviewer", confirmation_at="2026-08-19T12:00:00+00:00",
    )
    assert second.supersedes_correction_id == first.correction_id
    with session_factory() as fresh:
        chain = CorrectionRepository(fresh).list_by_page("op-1")
        assert len(chain) == 2

def test_overlap_correction_rejected_by_engine(stack, session_factory):
    _session, _fixture, _keys = stack
    service = EvidenceCorrectionService(session_factory)
    service.create_correction(
        ocr_page_id="op-1", text_start=4, text_end=7, original_text="5.6",
        corrected_text="5.60", change_kind=CorrectionChangeKind.DECIMAL,
        reason="r", actor="user", base_processing_revision_id="rev-1",
        confirmation_actor="reviewer", confirmation_at="2026-08-19T12:00:00+00:00",
    )
    # 同一范围不能创建第二个根（仓储拒绝），因此构造后投影不会出现重叠。
    from app.storage.evidence_locator_repositories import CorrectionOverlapError

    with pytest.raises(CorrectionOverlapError, match="不能创建第二个起始版本"):
        service.create_correction(
            ocr_page_id="op-1", text_start=4, text_end=7, original_text="5.6",
            corrected_text="5.600", change_kind=CorrectionChangeKind.DECIMAL,
            reason="r2", actor="user", base_processing_revision_id="rev-1",
            confirmation_actor="reviewer", confirmation_at="2026-08-19T12:00:00+00:00",
        )

def test_effective_text_for_revision_projects_raw_plus_corrections(stack, session_factory):
    session, _fixture, keys = stack
    service = EvidenceCorrectionService(session_factory)
    corr = service.create_correction(
        ocr_page_id="op-1", text_start=4, text_end=7, original_text="5.6",
        corrected_text="5.60", change_kind=CorrectionChangeKind.DECIMAL,
        reason="确认小数点", actor="user", base_processing_revision_id="rev-1",
        confirmation_actor="reviewer", confirmation_at="2026-08-19T12:00:00+00:00",
    )
    # 冻结包含该校对链头的完整修订。
    revision = _closed_revision(keys, session, correction_ids=[corr.correction_id])
    from app.storage.evidence_locator_repositories import (
        CompleteEvidenceProcessingRevisionRepository,
    )

    created = CompleteEvidenceProcessingRevisionRepository(session).create(revision)
    session.commit()

    projections = service.effective_text_for_revision(created.evidence_processing_revision_id)
    proj = projections["op-1"]
    assert proj.effective_text == "ALT 5.60 mmol/L 且 AST 3.5 mmol/L"
    expected = sha256(proj.effective_text.encode("utf-8")).hexdigest()
    assert proj.effective_text_sha256 == expected

    # 每次读取重算，结果确定。
    again = service.effective_text_for_page(
        created.evidence_processing_revision_id, "op-1"
    )
    assert again is not None
    assert again.effective_text_sha256 == proj.effective_text_sha256

def test_effective_text_engine_rejects_wrong_hash_binding(session_factory, stack):
    """有效文本投影引擎拒绝锚定非同一 raw 哈希的校对（防偏移漂移）。"""
    from app.evidence.effective_text import ProjectionOverlapError

    other = CorrectionRecord(
        correction_id="c-x", ocr_page_id="op-1",
        raw_text_sha256=sha(b"different raw"), text_start=0, text_end=4,
        original_text="diff", corrected_text="diffs", change_kind=CorrectionChangeKind.OTHER_TEXT,
        reason="r", actor="u", base_processing_revision_id="rev-1", created_at="2026-08-19T12:00:00+00:00",
    )
    from app.evidence.effective_text import project_effective_text

    with pytest.raises(ProjectionOverlapError, match="raw_text_sha256"):
        project_effective_text(RAW_TEXT, [other])
