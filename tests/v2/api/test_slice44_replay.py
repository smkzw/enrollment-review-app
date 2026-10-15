"""Slice 4.4 精确历史回放测试（WP-44C 复查，§8.3/§8.4 反例 5）。

当指定处理修订读取时，页接口只返回该完整修订冻结的 risk scan / risk review /
correction / locator（属于请求页）；后加的旁路工件绝不混入旧修订 R1 回放。
对每个 sidecar 类别分别断言 R1 冻结集合在后来新增工件后仍然精确回放。
"""
from __future__ import annotations

from tests.v2.api.test_slice44_api import (
    COMPLETE1,
    OCR_PAGE_ID,
    REV1,
    _episode_revision,
    _seed_api_stack,
)
from tests.v2.storage.test_slice44_repositories import (
    _complete_revision,
    _locator,
    _scan,
)

RAW_TEXT = "ALT 5.6 mmol/L 且 AST 3.5 mmol/L"


def _seed_r1_with_locator(client, keys):
    """播种 R1（完整修订 complete-1，冻结一个 locator + 一个 scan + 一个 review）。"""
    from app.storage.evidence_locator_repositories import (
        CompleteEvidenceProcessingRevisionRepository,
        EvidenceLocatorRepository,
        OCRRiskReviewRepository,
        OCRRiskScanRepository,
    )
    from tests.v2.storage.test_slice44_repositories import _seed_metadata

    with client.app.state.session_factory() as session, session.begin():
        metadata_id = _seed_metadata(session, keys)
        EvidenceLocatorRepository(session).create(_locator(keys, locator_id="loc-r1"))
        scan, _ = OCRRiskScanRepository(session).get_or_create(
            _scan(keys, scan_id="scan-r1", scanner_rule_version="rules/v1")
        )
        from datetime import UTC, datetime

        from app.domain.contracts.enums import OcrRiskReviewDecision
        from app.domain.contracts.evidence_locator import OCRRiskReview

        OCRRiskReviewRepository(session).create(
            OCRRiskReview(
                review_id="rv-r1",
                risk_flag_id=f"{scan.scan_id}:r1",
                decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
                reason="已核对",
                actor="user",
                base_processing_revision_id=REV1,
                expected_revision=1,
                created_at=datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC),
            )
        )
        revision = _complete_revision(
            keys,
            session,
            evidence_processing_revision_id=COMPLETE1,
            producer_candidate_id="producer-complete-1",
            metadata_revision_ids=[metadata_id],
            locator_ids=["loc-r1"],
            risk_scan_ids=["scan-r1"],
            risk_review_ids=["rv-r1"],
        )
        CompleteEvidenceProcessingRevisionRepository(session).create(revision)


def _seed_r1_correction(client, keys):
    """通过 API 追加一条校对（未确认），再冻结 R1 选入该校对。"""
    expected = _episode_revision(client, keys["episode_id"])
    body = {
        "raw_text_sha256": __import__("tests.v2.storage.test_ocr_repositories", fromlist=["sha"]).sha(
            RAW_TEXT.encode("utf-8")
        ),
        "text_start": 4,
        "text_end": 7,
        "original_text": "5.6",
        "corrected_text": "5.6 mmol/L",
        "change_kind": "other_text",
        "reason": "补充单位",
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-r1-corr",
        "actor": "u",
        "confirmation": {"actor": "复核人", "at": "2026-08-22T02:00:00Z"},
    }
    resp = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["correction"]["correction_id"]


def _later_sidecars(client, keys, correction_id: str) -> None:
    """在 R1 冻结后追加：新 scan/review/locator + 新校对（不进入 R1）。"""
    from datetime import UTC, datetime

    from app.domain.contracts.enums import OcrRiskReviewDecision
    from app.domain.contracts.evidence_locator import OCRRiskReview
    from app.storage.evidence_locator_repositories import (
        EvidenceLocatorRepository,
        OCRRiskReviewRepository,
        OCRRiskScanRepository,
    )

    expected = _episode_revision(client, keys["episode_id"])
    # 后续校对（R1 之后追加，进入新的候选/修订，不进入 R1）。
    body = {
        "raw_text_sha256": __import__("tests.v2.storage.test_ocr_repositories", fromlist=["sha"]).sha(
            RAW_TEXT.encode("utf-8")
        ),
        "text_start": 4,
        "text_end": 7,
        "original_text": "5.6",
        "corrected_text": "5.60",
        "change_kind": "other_text",
        "reason": "后续校对",
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-later-corr",
        "actor": "u",
        "confirmation": {"actor": "复核人", "at": "2026-08-22T02:00:00Z"},
    }
    client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=body)
    with client.app.state.session_factory() as session, session.begin():
        # 后续定位使用不同原始范围，避免与 R1 冻结定位发生 occurrence 身份碰撞。
        EvidenceLocatorRepository(session).create(
            _locator(
                keys,
                locator_id="loc-later",
                text_start=8,
                text_end=16,
                excerpt="mmol/L 且",
            )
        )
        scan, _ = OCRRiskScanRepository(session).get_or_create(
            _scan(keys, scan_id="scan-later", scanner_rule_version="rules/v2")
        )
        OCRRiskReviewRepository(session).create(
            OCRRiskReview(
                review_id="rv-later",
                risk_flag_id=f"{scan.scan_id}:r1",
                decision=OcrRiskReviewDecision.NOT_APPLICABLE,
                reason="后续核对",
                actor="user",
                base_processing_revision_id=REV1,
                expected_revision=expected,
                created_at=datetime(2026, 8, 20, 12, 0, 0, tzinfo=UTC),
            )
        )


def test_replay_r1_frozen_locators_not_later(client) -> None:
    """R1 只回放其冻结的 locator；后来追加的 locator 不出现。"""
    keys = _seed_api_stack(client)
    _seed_r1_with_locator(client, keys)
    # 追加一个后续 locator（不同原始范围，避免 occurrence 身份碰撞）。
    from app.storage.evidence_locator_repositories import EvidenceLocatorRepository

    with client.app.state.session_factory() as session, session.begin():
        EvidenceLocatorRepository(session).create(
            _locator(
                keys,
                locator_id="loc-later",
                text_start=8,
                text_end=16,
                excerpt="mmol/L 且",
            )
        )

    body = client.get(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}",
        params={"processing_revision_id": COMPLETE1},
    ).json()
    locator_ids = [l["locator_id"] for l in body["locators"]]
    assert locator_ids == ["loc-r1"]
    assert "loc-later" not in locator_ids


def test_replay_r1_frozen_risk_scans_not_later(client) -> None:
    """R1 只回放其冻结的 scan；后来追加的 scan 不出现。"""
    keys = _seed_api_stack(client)
    _seed_r1_with_locator(client, keys)
    from app.storage.evidence_locator_repositories import OCRRiskScanRepository

    with client.app.state.session_factory() as session, session.begin():
        OCRRiskScanRepository(session).get_or_create(
            _scan(keys, scan_id="scan-later", scanner_rule_version="rules/v2")
        )

    body = client.get(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}",
        params={"processing_revision_id": COMPLETE1},
    ).json()
    scan_ids = [s["scan_id"] for s in body["risk_scans"]]
    assert scan_ids == ["scan-r1"]
    assert "scan-later" not in scan_ids


def test_replay_r1_frozen_reviews_not_later(client) -> None:
    """R1 只回放其冻结的 review；后来追加的 review 不出现。"""
    keys = _seed_api_stack(client)
    _seed_r1_with_locator(client, keys)
    _later_sidecars(client, keys, correction_id=None)
    body = client.get(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}",
        params={"processing_revision_id": COMPLETE1},
    ).json()
    review_ids = [r["review_id"] for r in body["risk_reviews"]]
    assert review_ids == ["rv-r1"]
    assert "rv-later" not in review_ids


def test_replay_r1_frozen_corrections_not_later(client) -> None:
    """R1 只回放其冻结的校对；后来追加的校对不出现。"""
    from app.storage.evidence_locator_repositories import (
        CompleteEvidenceProcessingRevisionRepository,
    )
    from app.domain.contracts.evidence_locator import SOURCE_LINE_TARGET_PREFIX
    from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord
    from sqlalchemy import select
    from tests.v2.storage.test_slice44_repositories import (
        _seed_metadata,
        _seed_scan_and_review,
    )

    keys = _seed_api_stack(client)
    correction_id = _seed_r1_correction(client, keys)
    with client.app.state.session_factory() as session, session.begin():
        metadata_id = _seed_metadata(session, keys)
        scan_id, review_ids = _seed_scan_and_review(session, keys)
        locator_ids = session.execute(
            select(EvidenceLocatorArtifactRecord.locator_id).where(
                EvidenceLocatorArtifactRecord.target_id.startswith(
                    SOURCE_LINE_TARGET_PREFIX
                )
            )
        ).scalars().all()
        revision = _complete_revision(
            keys,
            session,
            evidence_processing_revision_id=COMPLETE1,
            producer_candidate_id="producer-complete-1",
            metadata_revision_ids=[metadata_id],
            risk_scan_ids=[scan_id],
            risk_review_ids=review_ids,
            correction_ids=[correction_id],
            locator_ids=sorted(locator_ids),
        )
        CompleteEvidenceProcessingRevisionRepository(session).create(revision)
    _later_sidecars(client, keys, correction_id)
    body = client.get(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}",
        params={"processing_revision_id": COMPLETE1},
    ).json()
    correction_ids = [c["correction_id"] for c in body["selected_corrections"]]
    assert correction_ids == [correction_id]
    assert len(correction_ids) == 1


def test_replay_r1_live_view_shows_current_sidecars(client) -> None:
    """未指定修订（无活动指针）时返回当前旁路工件（非冻结回放）。"""
    keys = _seed_api_stack(client)
    _seed_r1_with_locator(client, keys)
    _later_sidecars(client, keys, correction_id=None)
    body = client.get(f"/api/v2/ocr-pages/{OCR_PAGE_ID}").json()
    assert body["processing_revision_id"] is None  # 无活动指针
    locator_ids = {l["locator_id"] for l in body["locators"]}
    scan_ids = {s["scan_id"] for s in body["risk_scans"]}
    assert "loc-r1" in locator_ids and "loc-later" in locator_ids
    assert "scan-r1" in scan_ids and "scan-later" in scan_ids


def test_live_view_prefers_current_risk_rule_after_rescan(client) -> None:
    """一旦现行规则完成重扫，当前视图不再混入旧规则扫描。"""
    from app.evidence.risk import OCR_RISK_RULE_VERSION
    from app.storage.evidence_locator_repositories import OCRRiskScanRepository

    keys = _seed_api_stack(client)
    _seed_r1_with_locator(client, keys)
    with client.app.state.session_factory() as session, session.begin():
        OCRRiskScanRepository(session).get_or_create(
            _scan(
                keys,
                scan_id="scan-current",
                scanner_rule_version=OCR_RISK_RULE_VERSION,
            )
        )

    body = client.get(f"/api/v2/ocr-pages/{OCR_PAGE_ID}").json()
    assert [scan["scan_id"] for scan in body["risk_scans"]] == ["scan-current"]
