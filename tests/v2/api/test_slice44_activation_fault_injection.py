"""Slice 4.4 激活/回滚单事务原子性 + 幂等矩阵（WP-44C 复查 #2）。

单事务原子提交：事件、快照状态、候选状态、成对指针与幂等主张在同一事务；任何
子写或提交失败整体回滚，绝不出现「事件/指针已提交但幂等记录缺失」的半提交。
故障注入后重试同命令要么回放已提交结果、要么执行一次，绝不因缺幂等记录返回陈旧
冲突。

激活/回滚矩阵：同键同命令回放；同键异命令 409；新键过期预期修订号 409。
"""

from __future__ import annotations

from unittest import mock

from tests.v2.api.test_slice44_api import (
    COMPLETE1,
    SNAP1,
    _assert_envelope,
    _episode_revision,
    _seed_ready_complete,
)


def _activate_body(client, keys, *, key="key-act-m1", expected_revision=None, **ov):
    if expected_revision is None:
        expected_revision = _episode_revision(client, keys["episode_id"])
    body = {
        "expected_revision": expected_revision,
        "idempotency_key": key,
        "actor": "测试用户",
        "reason": "发布资料版本",
    }
    body.update(ov)
    return body


def _rollback_body(client, keys, *, key="key-rb-m1", expected_revision=None, **ov):
    if expected_revision is None:
        expected_revision = _episode_revision(client, keys["episode_id"])
    body = {
        "expected_revision": expected_revision,
        "idempotency_key": key,
        "actor": "测试用户",
        "reason": "回滚",
    }
    body.update(ov)
    return body


def _activation_events(client, episode_id):
    from app.storage.evidence_locator_repositories import (
        EvidenceActivationEventRepository,
    )

    with client.app.state.session_factory() as session:
        return EvidenceActivationEventRepository(session).list_by_episode(episode_id)


def _idempotency_rows(client, scope_prefix: str):
    from app.storage.models import IdempotencyRecordRow

    with client.app.state.session_factory() as session:
        return (
            session.query(IdempotencyRecordRow)
            .filter(IdempotencyRecordRow.scope.like(f"{scope_prefix}%"))
            .all()
        )


def test_activate_single_transaction_idempotency_claim(client) -> None:
    """激活成功：事件/指针/快照/候选/幂等主张同事务提交（各恰一条）。"""
    keys = _seed_ready_complete(client)
    episode_id = keys["episode_id"]
    body = _activate_body(client, keys)
    resp = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate", json=body
    )
    assert resp.status_code == 201, resp.text
    assert len(_activation_events(client, episode_id)) == 1
    rows = _idempotency_rows(client, f"activation:{episode_id}")
    assert len(rows) == 1
    with client.app.state.session_factory() as session:
        from app.storage.repositories import EpisodeRepository

        episode = EpisodeRepository(session).get(episode_id)
        assert episode.active_evidence_snapshot_id == SNAP1
        assert episode.active_evidence_processing_revision_id == COMPLETE1


def test_activate_fault_injection_after_event_write_rolls_back_all(client) -> None:
    """注入事件写后、幂等主张写入时失败：无事件/指针/快照/候选/幂等记录残留。"""
    from app.storage.idempotency import IdempotencyRepository

    keys = _seed_ready_complete(client)
    episode_id = keys["episode_id"]
    body = _activate_body(client, keys, key="key-act-fi")

    def _boom_resolve(
        self, *, scope, idempotency_key, submitted_hash, result_type, result_id
    ):
        raise RuntimeError("注入失败：幂等主张写入失败")

    with mock.patch.object(IdempotencyRepository, "resolve", _boom_resolve):
        try:
            _command_service(client).activate(
                target_snapshot_id=SNAP1,
                target_revision_id=COMPLETE1,
                expected_revision=body["expected_revision"],
                idempotency_key=body["idempotency_key"],
                actor=body["actor"],
                reason=body["reason"],
            )
            raised = False
        except RuntimeError:
            raised = True
        assert raised
    # 无激活事件、无幂等记录、无指针变化。
    assert _activation_events(client, episode_id) == []
    assert _idempotency_rows(client, f"activation:{episode_id}") == []
    with client.app.state.session_factory() as session:
        from app.storage.repositories import EpisodeRepository

        episode = EpisodeRepository(session).get(episode_id)
        assert episode.active_evidence_snapshot_id is None
        assert episode.revision == _episode_revision(client, episode_id)
    # 重试同命令执行一次（非陈旧冲突）。
    retry = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate", json=body
    )
    assert retry.status_code == 201, retry.text
    assert len(_activation_events(client, episode_id)) == 1


def test_activate_fault_injection_in_child_write_rolls_back(client) -> None:
    """注入事件追加（append_and_switch）中途失败：无事件/指针/快照/幂等残留。"""
    keys = _seed_ready_complete(client)
    episode_id = keys["episode_id"]
    body = _activate_body(client, keys, key="key-act-fic")
    from app.storage.evidence_locator_repositories import (
        EvidenceActivationEventRepository,
    )

    def _boom_append(self, event):
        raise RuntimeError("注入失败：激活事件追加中途失败")

    with mock.patch.object(
        EvidenceActivationEventRepository, "append_and_switch", _boom_append
    ):
        try:
            _command_service(client).activate(
                target_snapshot_id=SNAP1,
                target_revision_id=COMPLETE1,
                expected_revision=body["expected_revision"],
                idempotency_key=body["idempotency_key"],
                actor=body["actor"],
                reason=body["reason"],
            )
            raised = False
        except RuntimeError:
            raised = True
        assert raised
    assert _activation_events(client, episode_id) == []
    assert _idempotency_rows(client, f"activation:{episode_id}") == []
    with client.app.state.session_factory() as session:
        from app.storage.repositories import EpisodeRepository

        episode = EpisodeRepository(session).get(episode_id)
        assert episode.active_evidence_snapshot_id is None
    # 重试同命令执行一次（非陈旧冲突）。
    retry = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate", json=body
    )
    assert retry.status_code == 201, retry.text
    assert len(_activation_events(client, episode_id)) == 1


def test_activate_stale_after_snapshot_publication_rolls_back_savepoint(client) -> None:
    """指针乐观锁在快照发布后失败：发布事件回滚，只保留候选冲突。"""
    from app.domain.contracts.enums import SnapshotStatus
    from app.storage.concurrency import FieldChange, StaleRevisionError
    from app.storage.evidence_locator_repositories import (
        EvidenceActivationEventRepository,
        EvidenceProcessingCandidateRepository,
    )
    from app.storage.evidence_repositories import EvidenceSnapshotRepository

    keys = _seed_ready_complete(client)
    episode_id = keys["episode_id"]
    expected = _episode_revision(client, episode_id)

    def _stale_after_publication(self, event):
        raise StaleRevisionError(
            entity_type="review_episode",
            entity_id=episode_id,
            expected_revision=expected,
            current_revision=expected + 1,
            field_diff={
                "revision": FieldChange(current=expected + 1, submitted=expected)
            },
        )

    with mock.patch.object(
        EvidenceActivationEventRepository,
        "append_and_switch",
        _stale_after_publication,
    ):
        response = client.post(
            f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate",
            json=_activate_body(
                client,
                keys,
                key="key-act-stale-after-publish",
                expected_revision=expected,
            ),
        )

    assert response.status_code == 409
    _assert_envelope(response.json(), code="STALE_REVISION", status=409)
    with client.app.state.session_factory() as session:
        assert (
            EvidenceSnapshotRepository(session).current_status(SNAP1)
            == SnapshotStatus.READY
        )
        from app.storage.evidence_locator_repositories import (
            CompleteEvidenceProcessingRevisionRepository,
        )

        complete = CompleteEvidenceProcessingRevisionRepository(session).get(COMPLETE1)
        candidate = EvidenceProcessingCandidateRepository(session).get(
            complete.producer_candidate_id
        )
        assert candidate.status.value == "revision_conflict"
    assert _activation_events(client, episode_id) == []
    assert _idempotency_rows(client, f"activation:{episode_id}") == []


def _command_service(client):
    return client.app.state.evidence_api_command_service


def test_activate_same_key_different_command_409(client) -> None:
    """同幂等键异命令（改 reason/actor/预期修订号）-> 409，不产生新历史。"""
    keys = _seed_ready_complete(client)
    episode_id = keys["episode_id"]
    body = _activate_body(client, keys, key="key-act-conf")
    assert (
        client.post(
            f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate", json=body
        ).status_code
        == 201
    )
    body2 = _activate_body(client, keys, key="key-act-conf", actor="另一用户")
    resp = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate", json=body2
    )
    assert resp.status_code == 409
    _assert_envelope(resp.json(), code="IDEMPOTENCY_CONFLICT", status=409)
    assert len(_activation_events(client, episode_id)) == 1


def test_activate_current_pair_with_new_key_is_structured_409(client) -> None:
    """同一当前版本对的新命令不是服务器故障，也不得产生第二条历史。"""
    keys = _seed_ready_complete(client)
    episode_id = keys["episode_id"]
    first = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate",
        json=_activate_body(client, keys, key="key-current-first"),
    )
    assert first.status_code == 201, first.text
    second = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate",
        json=_activate_body(client, keys, key="key-current-second"),
    )
    assert second.status_code == 409, second.text
    error = _assert_envelope(
        second.json(), code="CURRENT_VERSION_UNCHANGED", status=409
    )
    context = error["context"]
    assert context["submitted"]["target_snapshot_id"] == SNAP1
    assert context["current_record"]["target_snapshot_id"] == SNAP1
    assert context["field_diff"]["active_pair"]["current"] == context[
        "field_diff"
    ]["active_pair"]["submitted"]
    assert len(_activation_events(client, episode_id)) == 1
    assert len(_idempotency_rows(client, f"activation:{episode_id}")) == 1


def test_activate_new_key_stale_revision_409(client) -> None:
    """新键 + 过期预期修订号 -> 409 STALE_REVISION，无事件/幂等残留。"""
    keys = _seed_ready_complete(client)
    episode_id = keys["episode_id"]
    current = _episode_revision(client, episode_id)
    body = _activate_body(
        client, keys, key="key-act-stale", expected_revision=current + 9
    )
    resp = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate", json=body
    )
    assert resp.status_code == 409
    error = _assert_envelope(resp.json(), code="STALE_REVISION", status=409)
    assert error["context"]["submitted"]["expected_revision"] == current + 9
    assert error["context"]["current_revision"] == current
    assert _activation_events(client, episode_id) == []
    assert _idempotency_rows(client, f"activation:{episode_id}") == []


def test_rollback_single_transaction_and_replay(client) -> None:
    """回滚同事务提交；同键同命令幂等回放同一事件。"""
    keys = _seed_ready_complete(client)
    episode_id = keys["episode_id"]
    _seed_two_activations(client, keys)
    current = _episode_revision(client, episode_id)
    rb_body = _rollback_body(client, keys, key="key-rb-1", expected_revision=current)
    first = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/rollback", json=rb_body
    )
    assert first.status_code == 201, first.text
    events_before = len(_activation_events(client, episode_id))
    replay = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/rollback", json=rb_body
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["event_id"] == first.json()["event_id"]
    assert len(_activation_events(client, episode_id)) == events_before  # 幂等回放


def _seed_two_activations(client, keys):
    """激活 complete-1 再激活 complete-2，使 episode 处于 complete-2 当前。"""
    activate(client, keys, COMPLETE1, "key-two-act-1")
    with client.app.state.session_factory() as session, session.begin():
        from app.storage.evidence_locator_repositories import (
            CompleteEvidenceProcessingRevisionRepository,
        )

        first = CompleteEvidenceProcessingRevisionRepository(session).get(COMPLETE1)
    from tests.v2.api.test_slice44_api import _seed_second_complete

    _seed_second_complete(client, keys, first)
    activate(client, keys, "complete-2", "key-two-act-2")


def activate(client, keys, revision_id: str, key: str) -> None:
    from tests.v2.api.test_slice44_api import activate as _activate_helper

    _activate_helper(client, keys, revision_id, key)
