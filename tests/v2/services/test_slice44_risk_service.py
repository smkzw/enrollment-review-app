"""Slice 4.4 OCR 风险旁路核对服务测试（WP-44B）。

覆盖 §8.2 风险不越权与模块边界：扫描前后原 OCR 字节/hash/数据库行逐字不变；
冻结复合句只产生风险 flags，连接词与全文逐字不变，无 RuleExpression/ClinicalFact
写入；同一 (页, 原文哈希, 规则版本) 三元组幂等；风险核对决议追加写。
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.domain.contracts.enums import (
    OcrRiskKind,
    OcrRiskReviewDecision,
)
from app.services.evidence_risk_service import (
    EvidenceRiskScanService,
)
from app.storage.evidence_locator_repositories import OCRRiskScanRepository
from app.storage.ocr_models import OCRPageRecord
from app.storage.ocr_repositories import OcrPageRepository
from tests.v2.storage.test_ocr_repositories import make_ocr_page
from tests.v2.storage.test_slice44_repositories import (
    RAW_TEXT,
    sha,
)


@pytest.fixture
def stack(revision_stack):
    """WP-44A 基础栈 + 提交（服务使用独立会话，必须先持久化栈数据）。"""
    session, fixture, keys = revision_stack
    session.commit()
    return session, fixture, keys

# ---------------------------------------------------------------------------
# 模块边界：原 OCR 逐字不变
# ---------------------------------------------------------------------------

def test_scan_creates_sidecar_and_ocr_unchanged(stack, session_factory):
    session, _fixture, _keys = stack
    before = session.get(OCRPageRecord, "op-1")
    before_payload = before.payload_json
    before_sha = before.payload_sha256

    service = EvidenceRiskScanService(session_factory)
    scan = service.scan_page("op-1")
    assert scan.ocr_page_id == "op-1"
    assert scan.scanner_rule_version != ""
    assert {f.kind.value for f in scan.flags} == {
        "numeric_value",
        "decimal_point",
        "unit",
    }

    # 扫描后重读：raw text/hash/payload 逐字不变。
    with session_factory() as fresh:
        page = fresh.get(OCRPageRecord, "op-1")
        assert page.raw_text == RAW_TEXT
        assert page.raw_text_sha256 == sha(RAW_TEXT.encode("utf-8"))
        assert page.payload_json == before_payload
        assert page.payload_sha256 == before_sha

    # 三元组幂等：再次扫描复用同一 scan，不产生第二份。
    again = service.scan_page("op-1")
    assert again.scan_id == scan.scan_id
    with session_factory() as fresh:
        scans = OCRRiskScanRepository(fresh).list_by_page("op-1")
        assert len(scans) == 1

def test_frozen_compound_sentence_flags_only_no_side_effects(stack, session_factory):
    """§4.3 冻结复合反例：ALT > 3×ULN 且 AST > 3×ULN，或总胆红素 > 2×ULN。"""
    _session, _fixture, _keys = stack
    frozen = "ALT > 3×ULN 且 AST > 3×ULN，或总胆红素 > 2×ULN。"
    with session_factory() as s, s.begin():
        from app.storage.ocr_repositories import (
            OCRProfileRepository,
            PageArtifactRepository,
        )
        from tests.v2.storage.test_ocr_repositories import make_artifact, make_profile

        profile = OCRProfileRepository(s).get_or_create(make_profile())
        PageArtifactRepository(s).get_or_create(
            make_artifact(artifact_id="pa-frozen", version_id="doc-1", page_input="f" * 64)
        )
        OcrPageRepository(s).create(
            make_ocr_page(
                page_id="op-frozen",
                artifact_id="pa-frozen",
                raw_text=frozen,
                page_input="f" * 64,
                profile_sha=profile.profile_sha256,
            )
        )

    counts_before = _count_table(session_factory, "clinical_facts")
    rules_before = _count_table(session_factory, "rule_components")
    runs_before = _count_table(session_factory, "review_runs")

    service = EvidenceRiskScanService(session_factory)
    scan = service.scan_page("op-frozen")

    # 只产生结构化风险 flags（数值），绝不输出修正文。
    assert scan.flags, "复合句至少应产生数值风险 flags"
    assert all(flag.text in frozen for flag in scan.flags)
    assert all(f.kind == OcrRiskKind.NUMERIC_VALUE for f in scan.flags)

    with session_factory() as fresh:
        page = fresh.get(OCRPageRecord, "op-frozen")
        # 连接词“且/或”与全文逐字不变。
        assert page.raw_text == frozen
        assert "且" in page.raw_text and "或" in page.raw_text
        assert page.raw_text_sha256 == sha(frozen.encode("utf-8"))

    # 模块边界：不写临床事实、规则表达式、评审运行。
    assert _count_table(session_factory, "clinical_facts") == counts_before
    assert _count_table(session_factory, "rule_components") == rules_before
    assert _count_table(session_factory, "review_runs") == runs_before

def test_scan_rule_version_mismatch_rejected(stack, session_factory):
    _session, _fixture, _keys = stack
    service = EvidenceRiskScanService(session_factory)
    with pytest.raises(ValueError, match="不支持的扫描规则版本"):
        service.scan_page("op-1", rule_version="not-a-version")

def test_review_creation_append_only(stack, session_factory):
    _session, _fixture, _keys = stack
    service = EvidenceRiskScanService(session_factory)
    scan = service.scan_page("op-1")
    flag_id = f"{scan.scan_id}:{scan.flags[0].risk_id}"
    review = service.create_review(
        review_id=None,
        risk_flag_id=flag_id,
        decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
        reason="已人工核对",
        actor="user",
        base_processing_revision_id="rev-1",
        expected_revision=1,
    )
    assert review.risk_flag_id == flag_id
    assert review.decision == OcrRiskReviewDecision.CONFIRMED_AS_READ
    with session_factory() as fresh:
        assert OCRRiskScanRepository(fresh).get(scan.scan_id).scan_id == scan.scan_id

def _count_table(session_factory, table: str) -> int:
    with session_factory() as session:
        return int(
            session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        )
