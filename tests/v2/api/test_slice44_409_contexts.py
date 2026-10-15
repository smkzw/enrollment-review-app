"""Slice 4.4 诚实 409 上下文测试（WP-44C 复查，§7.1/§8.4 反例 4）。

每个写侧 409 必须携带结构化 ``submitted`` / ``current_record`` / ``field_diff``；
待核对与门禁失败额外列出实际未解除/未通过的门禁；不暴露 ORM 对象、枚举、绝对
路径、非必要哈希或技术异常文本。
"""

from __future__ import annotations

from tests.v2.api.test_slice44_api import (
    COMPLETE1,
    OCR_PAGE_ID,
    REV1,
    SNAP1,
    _assert_envelope,
    _episode_revision,
    _run_revision_job,
    _seed_api_stack,
    _seed_metadata_helper,
    _seed_ready_complete,
    _seed_reviews_for_blocking,
    _seed_scan_and_review_ctx,
    activate,
)
from tests.v2.storage.test_ocr_repositories import sha
from tests.v2.storage.test_slice44_repositories import RAW_TEXT

#: 信封上下文不得包含的键（技术细节，任意嵌套深度）。
_FORBIDDEN_CONTEXT_KEYS = {
    "payload_json",
    "payload_sha256",
    "storage_ref",
    "absolute_path",
    "stacktrace",
    "exception_type",
}
_FORBIDDEN_TEXT_FRAGMENTS = (
    "payload_sha256",
    "storage_ref",
    "/Users/",
    "Traceback",
    "sqlalchemy",
    "at 0x",  # ORM 对象 repr
)


def _assert_clean_context(ctx: dict) -> None:
    """409 上下文不得暴露 ORM/哈希/路径/异常文本（递归任意嵌套深度）。"""
    if isinstance(ctx, dict):
        for key, value in ctx.items():
            assert key not in _FORBIDDEN_CONTEXT_KEYS, f"409 上下文不得暴露 {key}"
            _assert_clean_context(value)
    elif isinstance(ctx, list):
        for item in ctx:
            _assert_clean_context(item)
    elif isinstance(ctx, str):
        for fragment in _FORBIDDEN_TEXT_FRAGMENTS:
            assert fragment not in ctx, f"409 上下文文本不得包含 {fragment}"


def _assert_common_conflict_fields(ctx: dict) -> None:
    """每个写侧 409 都必须携带 submitted/current_record/field_diff。"""
    assert "submitted" in ctx, "409 上下文必须携带 submitted"
    assert "current_record" in ctx, "409 上下文必须携带 current_record"
    assert "field_diff" in ctx, "409 上下文必须携带 field_diff"
    assert isinstance(ctx["submitted"], dict)
    assert isinstance(ctx["current_record"], dict)
    assert isinstance(ctx["field_diff"], dict)
    _assert_clean_context(ctx)


def test_every_write_409_carries_common_fields(client) -> None:
    """各写命令家族（校对/核对/构建/激活/回滚/被提及资料）的 409 都携带三公共字段。"""
    from app.storage.evidence_locator_repositories import (
        CompleteEvidenceProcessingRevisionRepository,
    )
    from tests.v2.api.test_slice44_api import (
        _closed_revision,
        _make_candidate_ready,
        _ready_snapshot,
    )

    # 先构建 READY 完整修订（内部播种元数据 + scan-1 + rv-1 + 候选 READY）。
    keys = _seed_api_stack(client)
    ep = _episode_revision(client, keys["episode_id"])
    with client.app.state.session_factory() as session, session.begin():
        _ready_snapshot(session, keys)
        revision = _closed_revision(keys, session)
        created = CompleteEvidenceProcessingRevisionRepository(session).create(revision)
        _make_candidate_ready(
            session,
            created.producer_candidate_id,
            created.evidence_processing_revision_id,
        )

    # 校对陈旧 409。
    r = client.post(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections",
        json={
            "raw_text_sha256": sha(RAW_TEXT.encode("utf-8")),
            "text_start": 4,
            "text_end": 7,
            "original_text": "5.6",
            "corrected_text": "5.6 mmol/L",
            "change_kind": "other_text",
            "reason": "补单位",
            "base_processing_revision_id": REV1,
            "expected_revision": ep + 3,
            "idempotency_key": "key-ctx-corr",
        },
    )
    assert r.status_code == 409
    _assert_common_conflict_fields(r.json()["error"]["context"])

    # 风险核对幂等冲突 409（scan-1 已由 _closed_revision 播种）。
    rv = {
        "risk_flag_id": "scan-1:r1",
        "decision": "confirmed_as_read",
        "reason": "已核对",
        "base_processing_revision_id": REV1,
        "expected_revision": ep,
        "idempotency_key": "key-ctx-idem",
    }
    assert (
        client.post(
            f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-reviews", json=rv
        ).status_code
        == 201
    )
    r = client.post(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-reviews", json=dict(rv, reason="不同")
    )
    assert r.status_code == 409
    ctx = r.json()["error"]["context"]
    _assert_common_conflict_fields(ctx)
    assert "existing_result" in ctx  # 幂等冲突额外携带既有结果摘要

    # 被提及资料登记陈旧 409（同一 stack）。
    r = client.post(
        f"/api/v2/subjects/{keys['subject_id']}/referenced-documents",
        json={
            "review_episode_id": keys["episode_id"],
            "expected_revision": ep + 4,
            "idempotency_key": "key-ctx-ref",
            "description": "心电图",
            "actor": "u",
        },
    )
    assert r.status_code == 409
    _assert_common_conflict_fields(r.json()["error"]["context"])

    # 激活陈旧 409（完整修订已 READY）。
    r = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate",
        json={
            "expected_revision": ep + 5,
            "idempotency_key": "key-ctx-act",
            "actor": "u",
            "reason": "发布",
        },
    )
    assert r.status_code == 409
    _assert_common_conflict_fields(r.json()["error"]["context"])


# --------------------------------------------------------------------------- 非完整修订


def test_base_revision_activation_409_context(client) -> None:
    """base 修订激活 -> 409 NON_COMPLETE_REVISION，携带 revision_id + submitted。"""
    keys = _seed_api_stack(client)
    body = {
        "expected_revision": _episode_revision(client, keys["episode_id"]),
        "idempotency_key": "key-base-409",
        "actor": "u",
        "reason": "不应激活 base",
    }
    resp = client.post(
        f"/api/v2/evidence-processing-revisions/{REV1}/activate", json=body
    )
    assert resp.status_code == 409
    error = _assert_envelope(resp.json(), code="NON_COMPLETE_REVISION", status=409)
    assert error["context"]["revision_id"] == REV1
    assert error["context"]["submitted"]["reason"] == "不应激活 base"
    _assert_common_conflict_fields(error["context"])
    _assert_clean_context(error["context"])


# --------------------------------------------------------------------------- 待核对（门禁列表）


def test_pending_review_409_lists_unresolved_gates(client) -> None:
    """排队立即返回；后台发现阻断风险后回放才返回待核对上下文。"""
    keys = _seed_api_stack(client)
    _seed_metadata_helper(client, keys)  # 有元数据但无核对/校对
    expected = _episode_revision(client, keys["episode_id"])
    body = {
        "evidence_snapshot_id": SNAP1,
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-pending-409",
    }
    resp = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert resp.status_code == 201
    queued = resp.json()
    assert queued["candidate_status"] == "staged"
    _run_revision_job(client, queued["job_id"])
    replay = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert replay.status_code == 409
    error = _assert_envelope(replay.json(), code="REVIEW_PENDING", status=409)
    ctx = error["context"]
    assert ctx["candidate_status"] == "needs_attention"
    assert ctx["candidate_id"]
    assert ctx["unresolved_gates"], "待核对 409 必须列出实际未解除风险"
    flag = ctx["unresolved_gates"][0]
    assert "scan_id" in flag and "risk_id" in flag and "text" in flag
    assert "submitted" in ctx
    _assert_common_conflict_fields(ctx)
    _assert_clean_context(ctx)


# --------------------------------------------------------------------------- 激活门禁失败


def test_activation_gate_failure_lists_failed_gates(client) -> None:
    """激活门禁失败（如候选状态不对）-> 409，列出未通过门禁。"""
    keys = _seed_api_stack(client)
    # 快照 READY、完整修订已冻结，但生产候选停留在 PROCESSING（未 READY）-> 门禁失败。
    from app.storage.evidence_locator_repositories import (
        CompleteEvidenceProcessingRevisionRepository,
    )
    from tests.v2.api.test_slice44_api import _ready_snapshot
    from tests.v2.storage.test_slice44_repositories import _closed_revision

    with client.app.state.session_factory() as session, session.begin():
        _ready_snapshot(session, keys)
        revision = _closed_revision(keys, session)
        CompleteEvidenceProcessingRevisionRepository(session).create(revision)
        # 不推进候选到 READY（保持 PROCESSING）。
    body = {
        "expected_revision": _episode_revision(client, keys["episode_id"]),
        "idempotency_key": "key-gate-409",
        "actor": "u",
        "reason": "发布",
    }
    resp = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate", json=body
    )
    assert resp.status_code == 409
    error = _assert_envelope(resp.json(), code="ACTIVATION_GATE_FAILED", status=409)
    ctx = error["context"]
    assert ctx["revision_id"] == COMPLETE1
    assert ctx["failed_gates"], "激活门禁失败必须列出实际未通过门禁"
    assert "submitted" in ctx
    _assert_common_conflict_fields(ctx)
    _assert_clean_context(ctx)


def test_invalid_rollback_target_carries_common_conflict_fields(client) -> None:
    """回滚到当前版本时仍保留本次提交、当前指针和实际差异。"""
    keys = _seed_ready_complete(client)
    activate(client, keys, COMPLETE1, "key-context-activate")
    response = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/rollback",
        json={
            "expected_revision": _episode_revision(client, keys["episode_id"]),
            "idempotency_key": "key-context-rollback",
            "actor": "u",
            "reason": "回滚当前版本",
        },
    )
    assert response.status_code == 409
    error = _assert_envelope(
        response.json(), code="ROLLBACK_TARGET_INVALID", status=409
    )
    _assert_common_conflict_fields(error["context"])
    assert error["context"]["submitted"]["target_revision_id"] == COMPLETE1
    assert (
        error["context"]["current_record"]["active_evidence_processing_revision_id"]
        == COMPLETE1
    )


# --------------------------------------------------------------------------- 幂等冲突上下文


def test_idempotency_conflict_409_preserves_submitted_and_existing(client) -> None:
    """幂等冲突 409：submitted 保留提交值，existing_result 提供既有结果摘要。"""
    keys = _seed_api_stack(client)
    scan_id = _seed_scan_and_review_ctx(client, keys)
    episode_rev = _episode_revision(client, keys["episode_id"])
    body = {
        "risk_flag_id": f"{scan_id}:r1",
        "decision": "confirmed_as_read",
        "reason": "已核对",
        "base_processing_revision_id": REV1,
        "expected_revision": episode_rev,
        "idempotency_key": "key-ctx-409",
    }
    assert (
        client.post(
            f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-reviews", json=body
        ).status_code
        == 201
    )
    body2 = dict(body, reason="不同理由")
    resp = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-reviews", json=body2)
    assert resp.status_code == 409
    error = _assert_envelope(resp.json(), code="IDEMPOTENCY_CONFLICT", status=409)
    ctx = error["context"]
    assert ctx["submitted"]["reason"] == "不同理由"
    assert ctx["current_record"]["reason"] == "已核对"
    assert ctx["field_diff"]["reason"] == {
        "current": "已核对",
        "submitted": "不同理由",
    }
    assert "command_identity" not in ctx["field_diff"]
    assert "existing_result" in ctx
    assert ctx["existing_result"]["risk_flag_id"] == f"{scan_id}:r1"
    _assert_common_conflict_fields(ctx)
    _assert_clean_context(ctx)


def test_nested_build_failure_detail_is_whitelisted(client) -> None:
    """后台构建异常只投影稳定错误码，不泄漏路径或存储异常。"""
    from unittest import mock

    from app.services.evidence_revision_builder import EvidenceRevisionBuilder

    keys = _seed_api_stack(client)
    from app.services.evidence_risk_service import EvidenceRiskScanService

    scan = EvidenceRiskScanService(client.app.state.session_factory).scan_page(
        OCR_PAGE_ID
    )
    _seed_reviews_for_blocking(client, scan.scan_id)
    expected = _episode_revision(client, keys["episode_id"])
    technical = "payload_sha256=/Users/private/db.sqlite sqlalchemy.exc.IntegrityError"
    with mock.patch.object(
        EvidenceRevisionBuilder,
        "build",
        side_effect=RuntimeError(technical),
    ):
        response = client.post(
            "/api/v2/evidence-processing-revisions/build",
            json={
                "evidence_snapshot_id": SNAP1,
                "base_processing_revision_id": REV1,
                "expected_revision": expected,
                "idempotency_key": "key-nested-scrub",
            },
        )
        assert response.status_code == 201
        queued = response.json()
        _run_revision_job(client, queued["job_id"])

    status = client.get(f"/api/v2/jobs/{queued['job_id']}")
    assert status.status_code == 200
    status_body = status.json()
    assert status_body["state"] == "failed_retryable"
    assert status_body["error_code"] == "REVISION_BUILD_RETRYABLE"
    assert technical not in status.text

    replay = client.post(
        "/api/v2/evidence-processing-revisions/build",
        json={
            "evidence_snapshot_id": SNAP1,
            "base_processing_revision_id": REV1,
            "expected_revision": expected,
            "idempotency_key": "key-nested-scrub",
        },
    )
    assert replay.status_code == 200
    assert replay.json()["candidate_status"] == "retryable_failure"
    assert technical not in replay.text


# --------------------------------------------------------------------------- 陈旧修订上下文


def test_stale_revision_409_context_shapes(client) -> None:
    """陈旧修订 409：submitted/current_record/field_diff 齐全且结构正确。"""
    keys = _seed_api_stack(client)
    episode_rev = _episode_revision(client, keys["episode_id"])
    body = {
        "raw_text_sha256": sha(RAW_TEXT.encode("utf-8")),
        "text_start": 4,
        "text_end": 7,
        "original_text": "5.6",
        "corrected_text": "5.6 mmol/L",
        "change_kind": "other_text",
        "reason": "补充单位",
        "base_processing_revision_id": REV1,
        "expected_revision": episode_rev + 9,
        "idempotency_key": "key-stale-ctx",
    }
    resp = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=body)
    assert resp.status_code == 409
    error = _assert_envelope(resp.json(), code="STALE_REVISION", status=409)
    ctx = error["context"]
    assert set(ctx) >= {"submitted", "current_record", "field_diff"}
    assert ctx["current_record"]["review_episode_id"] == keys["episode_id"]
    assert ctx["current_record"]["revision"] == episode_rev
    assert ctx["field_diff"]["revision"]["current"] == episode_rev
    assert ctx["field_diff"]["revision"]["submitted"] == episode_rev + 9
    _assert_clean_context(ctx)


def test_409_context_never_exposes_orm_or_hashes(client) -> None:
    """信封正文与上下文都不得包含存储内部键。"""
    keys = _seed_api_stack(client)
    episode_rev = _episode_revision(client, keys["episode_id"])
    body = {
        "raw_text_sha256": sha(RAW_TEXT.encode("utf-8")),
        "text_start": 4,
        "text_end": 7,
        "original_text": "5.6",
        "corrected_text": "5.6 mmol/L",
        "change_kind": "other_text",
        "reason": "补充单位",
        "base_processing_revision_id": REV1,
        "expected_revision": episode_rev + 3,
        "idempotency_key": "key-clean-409",
    }
    resp = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=body)
    assert resp.status_code == 409
    raw = resp.text
    for forbidden in (
        "payload_json",
        "payload_sha256",
        "storage_ref",
        "sqlalchemy",
        "Traceback",
        "/Users/",
    ):
        assert forbidden not in raw, f"409 响应不得包含 {forbidden}"
