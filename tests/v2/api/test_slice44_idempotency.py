"""Slice 4.4 幂等键 + 乐观并发测试（WP-44C 复查，§8.3 反例 4 / §8.4 反例 6）。

每个写命令家族（校对/风险核对/构建/激活/回滚/被提及资料 create-revise-confirm-
dismiss-resolve-unresolve）都必须：

- 同幂等键同归一化请求回放原结果（即使审核节点/链头修订号已前进）；
- 同幂等键异请求 -> 409 且不产生新历史；
- 新请求在写入前检查预期修订号/链头修订号（双标签页陈旧提交 -> 409 保留提交值
  与服务端差异）。
"""
from __future__ import annotations

from tests.v2.api.test_slice44_api import (
    COMPLETE1,
    OCR_PAGE_ID,
    REV1,
    SNAP1,
    _assert_envelope,
    _episode_revision,
    _seed_api_stack,
    _seed_ready_complete,
    _seed_scan_and_review_ctx,
)
from tests.v2.storage.test_ocr_repositories import sha
from tests.v2.storage.test_slice44_repositories import RAW_TEXT

# --------------------------------------------------------------------------- 校对


def _corr_body(episode_rev, *, key="key-corr", corrected="5.6 mmol/L", **overrides):
    body = {
        "raw_text_sha256": sha(RAW_TEXT.encode("utf-8")),
        "text_start": 4,
        "text_end": 7,
        "original_text": "5.6",
        "corrected_text": corrected,
        "change_kind": "other_text",
        "reason": "补充单位",
        "base_processing_revision_id": REV1,
        "expected_revision": episode_rev,
        "idempotency_key": key,
        "actor": "u",
        "confirmation": {"actor": "复核人", "at": "2026-08-22T02:00:00Z"},
    }
    body.update(overrides)
    return body


def test_correction_same_key_replays_after_revision_advances(client) -> None:
    """同键同请求：即使审核节点修订号已前进（如后续激活）也回放原结果。"""
    keys = _seed_api_stack(client)
    episode_rev = _episode_revision(client, keys["episode_id"])
    body = _corr_body(episode_rev)
    first = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=body)
    assert first.status_code == 201, first.text
    corr_id = first.json()["correction"]["correction_id"]
    # 模拟审核节点修订号前进（直接推进 episode revision）。
    with client.app.state.session_factory() as session, session.begin():
        from app.storage.repositories import EpisodeRepository

        episode = EpisodeRepository(session).get(keys["episode_id"])
        changed = episode.model_copy(update={"revision": episode.revision + 5})
        from app.storage.codecs import encode_contract
        from app.storage.models import ReviewEpisodeRecord

        row = session.get(ReviewEpisodeRecord, keys["episode_id"])
        payload, phash = encode_contract(changed)
        row.payload_json = payload
        row.payload_sha256 = phash
    # 同键同请求回放（即使 expected_revision 已过期）。
    replay = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=body)
    assert replay.status_code == 200, replay.text
    assert replay.json()["correction"]["correction_id"] == corr_id


def test_correction_same_key_different_request_409_no_history(client) -> None:
    """同幂等键异请求 -> 409，不产生新历史。"""
    keys = _seed_api_stack(client)
    episode_rev = _episode_revision(client, keys["episode_id"])
    first = _corr_body(episode_rev)
    assert (
        client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=first).status_code
        == 201
    )
    second = _corr_body(episode_rev, corrected="5.60")
    resp = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=second)
    assert resp.status_code == 409
    error = _assert_envelope(resp.json(), code="IDEMPOTENCY_CONFLICT", status=409)
    ctx = error["context"]
    assert "submitted" in ctx and "existing_result" in ctx
    # 不产生新历史：只有一条校对记录。
    with client.app.state.session_factory() as session:
        from app.storage.evidence_locator_repositories import CorrectionRepository

        assert len(CorrectionRepository(session).list_by_page(OCR_PAGE_ID)) == 1


def test_correction_two_tab_stale_submission_409(client) -> None:
    """双标签页：A 提交后 B 用旧预期修订号提交 -> 409 保留提交值 + 差异。"""
    keys = _seed_api_stack(client)
    episode_rev = _episode_revision(client, keys["episode_id"])
    body_a = _corr_body(episode_rev, key="key-a", corrected="5.6 A")
    assert (
        client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=body_a).status_code
        == 201
    )
    # B 标签页携带已过期预期修订号（episode 已前进，例如另一动作推进了 revision）。
    stale = _corr_body(episode_rev + 5, key="key-c", corrected="5.6 C")
    resp = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=stale)
    assert resp.status_code == 409
    error = _assert_envelope(resp.json(), code="STALE_REVISION", status=409)
    ctx = error["context"]
    assert ctx["submitted"]["expected_revision"] == episode_rev + 5
    assert ctx["current_revision"] == episode_rev
    assert ctx["field_diff"]["revision"]["submitted"] == episode_rev + 5


# --------------------------------------------------------------------------- 风险核对


def test_risk_review_same_key_different_request_409(client) -> None:
    keys = _seed_api_stack(client)
    scan_id = _seed_scan_and_review_ctx(client, keys)
    episode_rev = _episode_revision(client, keys["episode_id"])
    body = {
        "risk_flag_id": f"{scan_id}:r1",
        "decision": "confirmed_as_read",
        "reason": "已核对",
        "base_processing_revision_id": REV1,
        "expected_revision": episode_rev,
        "idempotency_key": "key-rv-same",
    }
    assert (
        client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-reviews", json=body).status_code
        == 201
    )
    body2 = dict(body, reason="不同理由")
    resp = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-reviews", json=body2)
    assert resp.status_code == 409
    _assert_envelope(resp.json(), code="IDEMPOTENCY_CONFLICT", status=409)


# --------------------------------------------------------------------------- 构建


def test_build_same_key_replays_after_revision_advances(client) -> None:
    """构建同键同输入：即使审核节点修订号前进也回放既有候选（READY）。"""
    keys = _seed_api_stack(client)
    from tests.v2.api.test_slice44_api import (
        _seed_metadata_helper,
        _seed_reviews_for_blocking,
    )

    _seed_metadata_helper(client, keys)
    from app.services.evidence_risk_service import EvidenceRiskScanService

    scan = EvidenceRiskScanService(client.app.state.session_factory).scan_page(OCR_PAGE_ID)
    _seed_reviews_for_blocking(client, scan.scan_id)
    expected = _episode_revision(client, keys["episode_id"])
    body = {
        "evidence_snapshot_id": SNAP1,
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-build-same",
    }
    first = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert first.status_code == 201, first.text
    first_id = first.json()["candidate_id"]
    # 推进 episode revision。
    with client.app.state.session_factory() as session, session.begin():
        from app.storage.codecs import encode_contract
        from app.storage.models import ReviewEpisodeRecord
        from app.storage.repositories import EpisodeRepository

        episode = EpisodeRepository(session).get(keys["episode_id"])
        changed = episode.model_copy(update={"revision": episode.revision + 5})
        row = session.get(ReviewEpisodeRecord, keys["episode_id"])
        payload, phash = encode_contract(changed)
        row.payload_json = payload
        row.payload_sha256 = phash
    replay = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert replay.status_code == 200, replay.text
    assert replay.json()["candidate_id"] == first_id


# --------------------------------------------------------------------------- 激活 / 回滚


def test_activate_same_key_different_request_409(client) -> None:
    keys = _seed_ready_complete(client)
    body = {
        "expected_revision": _episode_revision(client, keys["episode_id"]),
        "idempotency_key": "key-act-same",
        "actor": "u",
        "reason": "发布",
    }
    assert (
        client.post(
            f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate", json=body
        ).status_code
        == 201
    )
    body2 = dict(body, reason="不同理由")
    resp = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate", json=body2
    )
    assert resp.status_code == 409
    _assert_envelope(resp.json(), code="IDEMPOTENCY_CONFLICT", status=409)
    # 不产生新历史：只有一条激活事件。
    with client.app.state.session_factory() as session:
        from app.storage.evidence_locator_repositories import (
            EvidenceActivationEventRepository,
        )

        assert len(
            EvidenceActivationEventRepository(session).list_by_episode(keys["episode_id"])
        ) == 1


def test_activate_two_tab_stale_submission_409(client) -> None:
    keys = _seed_ready_complete(client)
    expected = _episode_revision(client, keys["episode_id"])
    # 第一个标签页成功激活。
    body = {
        "expected_revision": expected,
        "idempotency_key": "key-act-tab1",
        "actor": "u",
        "reason": "发布",
    }
    assert (
        client.post(
            f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate", json=body
        ).status_code
        == 201
    )
    # 第二个标签页用同一预期修订号、不同幂等键（新请求）：episode revision 已前进 -> 409。
    body2 = {
        "expected_revision": expected,
        "idempotency_key": "key-act-tab2",
        "actor": "u",
        "reason": "另一标签页发布",
    }
    resp = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate", json=body2
    )
    assert resp.status_code == 409
    error = _assert_envelope(resp.json(), code="STALE_REVISION", status=409)
    assert error["context"]["current_revision"] == expected + 1


# --------------------------------------------------------------------------- 被提及资料


def test_refdoc_same_key_different_request_409(client) -> None:
    keys = _seed_api_stack(client)
    subject_id = keys["subject_id"]
    episode_id = keys["episode_id"]
    episode_rev = _episode_revision(client, episode_id)
    created = client.post(
        f"/api/v2/subjects/{subject_id}/referenced-documents",
        json={
            "review_episode_id": episode_id,
            "expected_revision": episode_rev,
            "idempotency_key": "key-refdoc-same",
            "description": "心电图",
        },
    )
    assert created.status_code == 201, created.text
    # 同键异请求 -> 409。
    resp = client.post(
        f"/api/v2/subjects/{subject_id}/referenced-documents",
        json={
            "review_episode_id": episode_id,
            "expected_revision": episode_rev,
            "idempotency_key": "key-refdoc-same",
            "description": "不同描述",
        },
    )
    assert resp.status_code == 409
    _assert_envelope(resp.json(), code="IDEMPOTENCY_CONFLICT", status=409)


def test_refdoc_two_tab_stale_chain_head_409(client) -> None:
    """revise 的乐观并发：链头修订号已前进时旧预期修订号提交 -> 409 保留差异。"""
    keys = _seed_api_stack(client)
    subject_id = keys["subject_id"]
    episode_id = keys["episode_id"]
    episode_rev = _episode_revision(client, episode_id)
    created = client.post(
        f"/api/v2/subjects/{subject_id}/referenced-documents",
        json={
            "review_episode_id": episode_id,
            "expected_revision": episode_rev,
            "idempotency_key": "key-refdoc-2tab",
            "description": "心电图",
        },
    ).json()
    ref_id = created["referenced_document_id"]
    # 第一次修改：链头 revision=1。
    first = client.patch(
        f"/api/v2/referenced-documents/{ref_id}",
        json={
            "expected_revision": 1,
            "idempotency_key": "key-refdoc-rev-1",
            "description": "心电图报告",
            "reason": "补全",
            "actor": "u",
        },
    )
    assert first.status_code == 200, first.text
    # 第二个标签页仍用旧链头修订号 1 -> 409 STALE_REVISION（当前链头已为 2）。
    stale = client.patch(
        f"/api/v2/referenced-documents/{ref_id}",
        json={
            "expected_revision": 1,
            "idempotency_key": "key-refdoc-rev-2",
            "description": "另一标签页",
            "reason": "并发修改",
            "actor": "u",
        },
    )
    assert stale.status_code == 409
    error = _assert_envelope(stale.json(), code="STALE_REVISION", status=409)
    assert error["context"]["current_record"]["revision"] == 2
    assert error["context"]["submitted"]["description"] == "另一标签页"
