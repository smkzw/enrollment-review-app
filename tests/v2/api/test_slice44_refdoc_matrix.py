"""Slice 4.4 被提及资料六命令家族幂等 + 并发矩阵（WP-44C 复查 #3）。

统一命令身份策略：路径资源/作用域 + 全部业务字段 + actor + 预期修订号。每个家族
create/revise/confirm/dismiss/resolve/unresolve 都覆盖：

- 同键同命令 -> 回放原结果（修订 ID 稳定）；
- 同键异命令（改 actor / 预期修订号 / 业务字段 / 路径资源）-> 409 且无新历史；
- 新键 + 过期（episode/链头/满足链头）修订号 -> 409 STALE_REVISION 且无新历史；
- 不可变历史计数：旧修订永不删除，新修订追加。
"""

from __future__ import annotations

from tests.v2.api.test_slice44_api import (
    COMPLETE1,
    _assert_envelope,
    _episode_revision,
    _seed_ready_complete,
    activate,
)
from tests.v2.storage.test_slice44_repositories import _locator


def _seed_refdoc_stack(client):
    from app.storage.evidence_locator_repositories import EvidenceLocatorRepository

    keys = _seed_ready_complete(client)
    with client.app.state.session_factory() as session, session.begin():
        EvidenceLocatorRepository(session).create(_locator(keys, locator_id="loc-1"))
    activate(client, keys, COMPLETE1, "key-refdoc-activate")
    return keys


def _revision_count(client, ref_id: str) -> int:
    from sqlalchemy import func, select, text

    with client.app.state.session_factory() as session:
        return int(
            session.execute(
                select(func.count())
                .select_from(text("referenced_document_revisions"))
                .where(text("referenced_document_id = :rid")),
                {"rid": ref_id},
            ).scalar_one()
        )


def _resolution_count(client, ref_id: str) -> int:
    from sqlalchemy import func, select, text

    with client.app.state.session_factory() as session:
        return int(
            session.execute(
                select(func.count())
                .select_from(text("referenced_document_resolution_revisions"))
                .where(text("referenced_document_id = :rid")),
                {"rid": ref_id},
            ).scalar_one()
        )


def _create(client, keys, *, key, expected_revision=None, actor="u", **ov):
    if expected_revision is None:
        expected_revision = _episode_revision(client, keys["episode_id"])
    body = {
        "review_episode_id": keys["episode_id"],
        "expected_revision": expected_revision,
        "idempotency_key": key,
        "description": "既往心电图",
        "actor": actor,
    }
    body.update(ov)
    return client.post(
        f"/api/v2/subjects/{keys['subject_id']}/referenced-documents", json=body
    )


# --------------------------------------------------------------------------- create


def test_create_same_same_replays_and_different_409(client) -> None:
    keys = _seed_refdoc_stack(client)
    first = _create(client, keys, key="key-c-1")
    assert first.status_code == 201, first.text
    ref_id = first.json()["referenced_document_id"]
    # 同键同命令回放。
    replay = _create(client, keys, key="key-c-1")
    assert replay.status_code == 200
    assert replay.json()["referenced_document_id"] == ref_id
    assert _revision_count(client, ref_id) == 1
    # 同键异命令（改 actor）-> 409，无新历史。
    resp = _create(client, keys, key="key-c-1", actor="另一用户")
    assert resp.status_code == 409
    _assert_envelope(resp.json(), code="IDEMPOTENCY_CONFLICT", status=409)
    assert _revision_count(client, ref_id) == 1
    # 同键异命令（改 description）-> 409。
    resp2 = _create(client, keys, key="key-c-1", description="不同描述")
    assert resp2.status_code == 409
    assert _revision_count(client, ref_id) == 1


def test_create_new_key_stale_episode_409(client) -> None:
    keys = _seed_refdoc_stack(client)
    current = _episode_revision(client, keys["episode_id"])
    resp = _create(client, keys, key="key-c-stale", expected_revision=current + 5)
    assert resp.status_code == 409
    error = _assert_envelope(resp.json(), code="STALE_REVISION", status=409)
    assert error["context"]["submitted"]["expected_revision"] == current + 5
    assert error["context"]["current_revision"] == current


# --------------------------------------------------------------------------- revise/confirm/dismiss


def _confirm(client, ref_id, *, key, expected_revision=1, actor="u", **ov):
    body = {
        "expected_revision": expected_revision,
        "idempotency_key": key,
        "trigger_locator_id": "loc-1",
        "reason": "原文明确提及",
        "actor": actor,
    }
    body.update(ov)
    return client.post(f"/api/v2/referenced-documents/{ref_id}/confirm", json=body)


def test_confirm_same_same_replays_different_409_stale_409(client) -> None:
    keys = _seed_refdoc_stack(client)
    created = _create(client, keys, key="key-cf-1").json()
    ref_id = created["referenced_document_id"]
    first = _confirm(client, ref_id, key="key-conf-1")
    assert first.status_code == 200, first.text
    rev2 = first.json()["revision"]
    assert rev2 == 2
    # 同键同命令回放。
    replay = _confirm(client, ref_id, key="key-conf-1", expected_revision=1)
    assert replay.status_code == 200
    assert replay.json()["revision"] == rev2
    assert _revision_count(client, ref_id) == 2
    # 同键异命令（改 actor）-> 409。
    resp = _confirm(
        client, ref_id, key="key-conf-1", expected_revision=1, actor="另一用户"
    )
    assert resp.status_code == 409
    _assert_envelope(resp.json(), code="IDEMPOTENCY_CONFLICT", status=409)
    assert _revision_count(client, ref_id) == 2
    # 新键 + 过期链头修订号（当前链头为 2）-> 409。
    stale = _confirm(client, ref_id, key="key-conf-stale", expected_revision=1)
    assert stale.status_code == 409
    error = _assert_envelope(stale.json(), code="STALE_REVISION", status=409)
    assert error["context"]["current_record"]["revision"] == 2
    assert error["context"]["submitted"]["expected_revision"] == 1
    assert _revision_count(client, ref_id) == 2


def test_revise_and_dismiss_matrix(client) -> None:
    keys = _seed_refdoc_stack(client)
    created = _create(client, keys, key="key-rd-1").json()
    ref_id = created["referenced_document_id"]
    # revise 同键同命令回放。
    r1 = client.patch(
        f"/api/v2/referenced-documents/{ref_id}",
        json={
            "expected_revision": 1,
            "idempotency_key": "key-rev-1",
            "description": "心电图报告",
            "reason": "补全",
            "actor": "u",
        },
    )
    assert r1.status_code == 200, r1.text
    r1_id = r1.json()["revision_id"]
    r1_replay = client.patch(
        f"/api/v2/referenced-documents/{ref_id}",
        json={
            "expected_revision": 1,
            "idempotency_key": "key-rev-1",
            "description": "心电图报告",
            "reason": "补全",
            "actor": "u",
        },
    )
    assert r1_replay.status_code == 200
    assert r1_replay.json()["revision_id"] == r1_id
    # revise 同键异命令（改 actor）-> 409。
    r2 = client.patch(
        f"/api/v2/referenced-documents/{ref_id}",
        json={
            "expected_revision": 1,
            "idempotency_key": "key-rev-1",
            "description": "心电图报告",
            "reason": "补全",
            "actor": "另一用户",
        },
    )
    assert r2.status_code == 409
    _assert_envelope(r2.json(), code="IDEMPOTENCY_CONFLICT", status=409)
    # revise 新键 + 过期链头（当前为 2）-> 409。
    r_stale = client.patch(
        f"/api/v2/referenced-documents/{ref_id}",
        json={
            "expected_revision": 1,
            "idempotency_key": "key-rev-stale",
            "description": "心电图报告",
            "reason": "再次修改",
            "actor": "u",
        },
    )
    assert r_stale.status_code == 409
    _assert_envelope(r_stale.json(), code="STALE_REVISION", status=409)
    assert _revision_count(client, ref_id) == 2

    # dismiss 同键同命令回放，同键异命令冲突。
    dismiss_body = {
        "expected_revision": 2,
        "idempotency_key": "key-dis-1",
        "reason": "不必补充",
        "actor": "u",
    }
    d_ok = client.post(
        f"/api/v2/referenced-documents/{ref_id}/dismiss", json=dismiss_body
    )
    assert d_ok.status_code == 200, d_ok.text
    d_id = d_ok.json()["revision_id"]
    d_replay = client.post(
        f"/api/v2/referenced-documents/{ref_id}/dismiss", json=dismiss_body
    )
    assert d_replay.status_code == 200
    assert d_replay.json()["revision_id"] == d_id
    d_conflict = client.post(
        f"/api/v2/referenced-documents/{ref_id}/dismiss",
        json=dict(dismiss_body, reason="另一理由"),
    )
    assert d_conflict.status_code == 409
    _assert_envelope(d_conflict.json(), code="IDEMPOTENCY_CONFLICT", status=409)
    assert _revision_count(client, ref_id) == 3
    from app.services.evidence_revision_builder import EvidenceRevisionBuilder

    with client.app.state.session_factory() as session:
        referenced_ids, resolution_ids = EvidenceRevisionBuilder._gather_referenced(
            session, keys["episode_id"]
        )
    assert referenced_ids == []
    assert resolution_ids == []

    # dismiss 新键 + 过期链头（当前为 3）-> 409。
    d1 = client.post(
        f"/api/v2/referenced-documents/{ref_id}/dismiss",
        json={
            "expected_revision": 1,
            "idempotency_key": "key-dis-stale",
            "reason": "不必要",
            "actor": "u",
        },
    )
    assert d1.status_code == 409
    _assert_envelope(d1.json(), code="STALE_REVISION", status=409)


# --------------------------------------------------------------------------- resolve/unresolve


def test_resolve_matrix(client) -> None:
    keys = _seed_refdoc_stack(client)
    created = _create(client, keys, key="key-rs-1").json()
    ref_id = created["referenced_document_id"]
    # 首次 resolve：满足链头 revision 0 -> 1。
    body = {
        "expected_revision": 0,
        "idempotency_key": "key-res-1",
        "status": "provided",
        "source_document_version_id": "doc-1",
        "actor": "u",
    }
    first = client.post(f"/api/v2/referenced-documents/{ref_id}/resolve", json=body)
    assert first.status_code == 201, first.text
    res_id = first.json()["resolution_revision_id"]
    # 同键同命令回放。
    replay = client.post(f"/api/v2/referenced-documents/{ref_id}/resolve", json=body)
    assert replay.status_code == 200
    assert replay.json()["resolution_revision_id"] == res_id
    assert _resolution_count(client, ref_id) == 1
    # 同键异命令（改 actor）-> 409。
    body2 = dict(body, actor="另一用户")
    resp = client.post(f"/api/v2/referenced-documents/{ref_id}/resolve", json=body2)
    assert resp.status_code == 409
    _assert_envelope(resp.json(), code="IDEMPOTENCY_CONFLICT", status=409)
    assert _resolution_count(client, ref_id) == 1
    # 新键 + 过期满足链头（当前为 1）-> 409。
    stale = client.post(
        f"/api/v2/referenced-documents/{ref_id}/resolve",
        json={
            "expected_revision": 0,
            "idempotency_key": "key-res-stale",
            "status": "provided",
            "source_document_version_id": "doc-1",
            "actor": "u",
        },
    )
    assert stale.status_code == 409
    _assert_envelope(stale.json(), code="STALE_REVISION", status=409)
    # unresolve：同键同命令回放，异命令 409。
    unresolve_body = {
        "expected_revision": 1,
        "idempotency_key": "key-unres-1",
    }
    u1 = client.delete(
        f"/api/v2/referenced-documents/{ref_id}/resolution",
        params=unresolve_body,
    )
    assert u1.status_code == 200, u1.text
    u1_id = u1.json()["resolution_revision_id"]
    u1_replay = client.delete(
        f"/api/v2/referenced-documents/{ref_id}/resolution",
        params=unresolve_body,
    )
    assert u1_replay.status_code == 200
    assert u1_replay.json()["resolution_revision_id"] == u1_id
    assert _resolution_count(client, ref_id) == 2
    # 同键异命令（改 actor）-> 409，不追加满足历史。
    u_conflict = client.delete(
        f"/api/v2/referenced-documents/{ref_id}/resolution",
        params={**unresolve_body, "actor": "另一用户"},
    )
    assert u_conflict.status_code == 409
    _assert_envelope(u_conflict.json(), code="IDEMPOTENCY_CONFLICT", status=409)
    assert _resolution_count(client, ref_id) == 2
    # 新键 + 过期满足链头（当前为 2）-> 409。
    u_stale = client.delete(
        f"/api/v2/referenced-documents/{ref_id}/resolution",
        params={"expected_revision": 1, "idempotency_key": "key-unres-stale"},
    )
    assert u_stale.status_code == 409
    _assert_envelope(u_stale.json(), code="STALE_REVISION", status=409)
    assert _resolution_count(client, ref_id) == 2
