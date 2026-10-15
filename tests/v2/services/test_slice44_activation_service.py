"""Slice 4.4 证据版本原子激活/回滚服务测试（WP-44B）。

覆盖 §8.4 完整修订与活动版本：base 永不可激活；快照 READY 才首次发布；同一已激活
快照的新处理修订不重复转换终态；成对指针乐观锁原子更新；回滚只允许历史对；
并发同 expected-revision 只允许一个成功，败者只记候选 revision_conflict、不追加
成功激活事件；故障注入证明激活事件/快照状态事件/指针三者原子回滚；幂等回放；
指针为 null 但存在 ACTIVE 状态时不回退（§8.4 反例 4）。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from app.domain.contracts.enums import (
    ActivationEventKind,
    EvidenceProcessingCandidateStatus,
    SnapshotStatus,
)
from app.services.evidence_activation_service import (
    ActivationGateError,
    ActivationIdempotencyConflictError,
    ActivationRevisionConflictError,
    EvidenceActivationService,
    RollbackTargetError,
)
from app.storage.evidence_locator_models import EvidenceActivationEventRecord
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository,
    EvidenceActivationEventRepository,
    EvidenceProcessingCandidateRepository,
)
from app.storage.evidence_models import (
    EvidenceSnapshotStatusEventRecord,
    EvidenceSnapshotV2Record,
)
from app.storage.evidence_repositories import EvidenceSnapshotRepository
from app.storage.repositories import EpisodeRepository, InvalidReferenceError
from tests.v2.storage.test_slice44_repositories import (
    FIXED_UTC,
    _activation_event,
    _candidate,
    _candidate_event,
    _closed_revision,
    _complete_revision,
)


@pytest.fixture
def stack(revision_stack):
    session, fixture, keys = revision_stack
    session.commit()
    return session, fixture, keys

def _ready_snapshot(session, keys):
    EvidenceSnapshotRepository(session).transition_status(
        "snap-1",
        event="all_gates_passed",
        new_status=SnapshotStatus.READY,
        actor="tester",
        reason="就绪",
    )

def _build_complete(session, keys, *, revision_id="complete-1", correction_ids=()):
    revision = _closed_revision(keys, session, correction_ids=list(correction_ids))
    if revision_id != "complete-1":
        revision = revision.model_copy(
            update={"evidence_processing_revision_id": revision_id}
        )
    created = CompleteEvidenceProcessingRevisionRepository(session).create(revision)
    candidate_repo = EvidenceProcessingCandidateRepository(session)
    candidate = candidate_repo.get(created.producer_candidate_id)
    candidate_repo.append_event(
        _candidate_event(
            candidate.candidate_id,
            len(candidate_repo.get_events(candidate.candidate_id)) + 1,
            "processing",
            "all_gates_passed",
            "ready",
            complete_revision_id=created.evidence_processing_revision_id,
        )
    )
    return created

def _build_second_complete(
    session,
    keys,
    first,
    correction_ids,
    revision_id="complete-2",
    expected_revision=1,
):
    """复用首份修订闭包（元数据/扫描/核对），仅新增校对链头，构建第二份完整修订。"""
    producer_id = f"producer-{revision_id}"
    producer_repo = EvidenceProcessingCandidateRepository(session)
    producer = _candidate(
        keys,
        candidate_id=producer_id,
        idempotency_key=f"key-{producer_id}",
        expected_revision=expected_revision,
        scanner_rule_version="rules/v1",
    )
    producer_repo.create(
        producer,
        _candidate_event(
            producer_id,
            1,
            "staged",
            "worker_start",
            "processing",
        ),
    )
    revision = _complete_revision(
        keys,
        session,
        evidence_processing_revision_id=revision_id,
        producer_candidate_id=producer_id,
        candidate_input_sha256=producer.candidate_input_sha256,
        metadata_revision_ids=list(first.metadata_revision_ids),
        risk_scan_ids=list(first.risk_scan_ids),
        risk_review_ids=list(first.risk_review_ids),
        correction_ids=list(correction_ids),
    )
    created = CompleteEvidenceProcessingRevisionRepository(session).create(revision)
    candidate_repo = EvidenceProcessingCandidateRepository(session)
    candidate = candidate_repo.get(created.producer_candidate_id)
    candidate_repo.append_event(
        _candidate_event(
            candidate.candidate_id,
            len(candidate_repo.get_events(candidate.candidate_id)) + 1,
            "processing",
            "all_gates_passed",
            "ready",
            complete_revision_id=created.evidence_processing_revision_id,
        )
    )
    return created

def _ready_complete(session, keys, *, revision_id="complete-1", correction_ids=()):
    _ready_snapshot(session, keys)
    created = _build_complete(session, keys, revision_id=revision_id, correction_ids=correction_ids)
    session.commit()
    return created

def _activate(service, keys, *, target_revision_id="complete-1", expected_revision=1, **overrides):
    overrides.setdefault("candidate_id", f"producer-{target_revision_id}")
    return service.activate(
        target_snapshot_id="snap-1",
        target_revision_id=target_revision_id,
        expected_revision=expected_revision,
        actor="tester",
        reason="发布",
        **overrides,
    )

# --------------------------------------------------------------------------- 成功激活

def test_first_activation_sets_pointers_events_and_snapshot(stack, session_factory):
    session, _fixture, keys = stack
    _ready_complete(session, keys)
    service = EvidenceActivationService(session_factory)
    outcome = _activate(service, keys)
    assert outcome.event.activation_seq == 1
    assert outcome.event.event_kind == ActivationEventKind.ACTIVATE
    assert outcome.snapshot_status_transitioned is True
    with session_factory() as fresh:
        episode = EpisodeRepository(fresh).get(keys["episode_id"])
        assert episode.active_evidence_snapshot_id == "snap-1"
        assert episode.active_evidence_processing_revision_id == "complete-1"
        assert episode.revision == 2  # 乐观锁递增
        snapshot = EvidenceSnapshotRepository(fresh).get("snap-1")
        assert snapshot.status == SnapshotStatus.ACTIVE
        events = EvidenceActivationEventRepository(fresh).list_by_episode(keys["episode_id"])
        assert len(events) == 1

def test_base_revision_never_activatable(stack, session_factory):
    session, _fixture, keys = stack
    _ready_snapshot(session, keys)
    session.commit()
    service = EvidenceActivationService(session_factory)
    with pytest.raises(ActivationGateError, match="基础修订"):
        service.activate(
            target_snapshot_id="snap-1", target_revision_id="rev-1",
            expected_revision=1, actor="tester", reason="不应激活 base",
            candidate_id="producer-complete-1",
        )

def test_activation_requires_ready_snapshot(stack, session_factory):
    session, _fixture, keys = stack
    _build_complete(session, keys)  # 快照保持 PROCESSING（未 ready）
    session.commit()
    service = EvidenceActivationService(session_factory)
    with pytest.raises(ActivationGateError, match="不可激活"):
        _activate(service, keys)

def test_activation_same_command_without_event_id_replays_original(stack, session_factory):
    session, _fixture, keys = stack
    _ready_complete(session, keys)
    service = EvidenceActivationService(session_factory)
    original = _activate(service, keys)
    replay = _activate(service, keys)
    assert replay.event.event_id == original.event.event_id
    assert replay.resulting_episode_revision == original.resulting_episode_revision
    with session_factory() as fresh:
        assert len(
            EvidenceActivationEventRepository(fresh).list_by_episode(keys["episode_id"])
        ) == 1

def test_new_revision_on_active_snapshot_no_repeat_transition(stack, session_factory):
    session, _fixture, keys = stack
    # 第一次激活 complete-1。
    first = _ready_complete(session, keys)
    service = EvidenceActivationService(session_factory)
    first_outcome = _activate(service, keys)
    assert first_outcome.snapshot_status_transitioned is True
    # 在已激活快照上新增校对并冻结第二份完整修订 complete-2。
    with session_factory() as s, s.begin():
        from app.domain.contracts.enums import CorrectionChangeKind
        from app.services.evidence_correction_service import EvidenceCorrectionService

        corr = EvidenceCorrectionService(session_factory).create_correction_in_session(
            s, ocr_page_id="op-1", text_start=4, text_end=7, original_text="5.6",
            corrected_text="5.60", change_kind=CorrectionChangeKind.DECIMAL,
            reason="r", actor="u", base_processing_revision_id="rev-1",
            confirmation_actor="reviewer", confirmation_at="2026-08-19T12:00:00+00:00",
        )
    with session_factory() as s, s.begin():
        _build_second_complete(
            s,
            keys,
            first,
            correction_ids=[corr.correction_id],
            revision_id="complete-2",
            expected_revision=2,
        )
    outcome = service.activate(
        target_snapshot_id="snap-1", target_revision_id="complete-2",
        expected_revision=2, actor="tester", reason="新校对发布",
        candidate_id="producer-complete-2",
    )
    # 同一已激活快照的新处理修订：不重复转换快照终态。
    assert outcome.snapshot_status_transitioned is False
    with session_factory() as fresh:
        episode = EpisodeRepository(fresh).get(keys["episode_id"])
        assert episode.active_evidence_processing_revision_id == "complete-2"
        assert episode.revision == 3
        from sqlalchemy import select

        snapshot_events = fresh.execute(
            select(EvidenceSnapshotStatusEventRecord)
        ).scalars().all()
        # ready→active 只追加一次（不因新修订重复）。
        assert [e.event for e in snapshot_events].count("activate") == 1

# --------------------------------------------------------------------------- 回滚

def test_rollback_to_historical_pair(stack, session_factory):
    session, _fixture, keys = stack
    first = _ready_complete(session, keys)
    service = EvidenceActivationService(session_factory)
    _activate(service, keys)  # complete-1 激活，episode revision=2
    # 第二份修订激活。
    with session_factory() as s, s.begin():
        from app.domain.contracts.enums import CorrectionChangeKind
        from app.services.evidence_correction_service import EvidenceCorrectionService

        corr = EvidenceCorrectionService(session_factory).create_correction_in_session(
            s, ocr_page_id="op-1", text_start=4, text_end=7, original_text="5.6",
            corrected_text="5.60", change_kind=CorrectionChangeKind.DECIMAL,
            reason="r", actor="u", base_processing_revision_id="rev-1",
            confirmation_actor="reviewer", confirmation_at="2026-08-19T12:00:00+00:00",
        )
    with session_factory() as s, s.begin():
        _build_second_complete(
            s,
            keys,
            first,
            correction_ids=[corr.correction_id],
            revision_id="complete-2",
            expected_revision=2,
        )
    service.activate(
        target_snapshot_id="snap-1", target_revision_id="complete-2",
        expected_revision=2, actor="tester", reason="新校对发布",
        candidate_id="producer-complete-2",
    )
    # 回滚到历史对 complete-1。
    outcome = service.rollback(
        target_snapshot_id="snap-1", target_revision_id="complete-1",
        expected_revision=3, actor="tester", reason="回滚到前一版本",
    )
    assert outcome.event.event_kind == ActivationEventKind.ROLLBACK
    with session_factory() as fresh:
        episode = EpisodeRepository(fresh).get(keys["episode_id"])
        assert episode.active_evidence_processing_revision_id == "complete-1"
        assert episode.revision == 4
        events = EvidenceActivationEventRepository(fresh).list_by_episode(keys["episode_id"])
        assert [e.event_kind for e in events] == [
            ActivationEventKind.ACTIVATE,
            ActivationEventKind.ACTIVATE,
            ActivationEventKind.ROLLBACK,
        ]

def test_rollback_to_never_activated_pair_rejected(stack, session_factory):
    session, _fixture, keys = stack
    first = _ready_complete(session, keys)
    service = EvidenceActivationService(session_factory)
    _activate(service, keys)
    # 构建第二份但从未激活 → 不可作为回滚目标。
    with session_factory() as s, s.begin():
        _build_second_complete(s, keys, first, correction_ids=[], revision_id="complete-2")
    with pytest.raises(RollbackTargetError, match="未曾在任何激活事件"):
        service.rollback(
            target_snapshot_id="snap-1", target_revision_id="complete-2",
            expected_revision=2, actor="tester", reason="不应允许",
        )

# --------------------------------------------------------------------------- 并发

def test_concurrent_activation_one_success_loser_conflict(stack, session_factory):
    session, _fixture, keys = stack
    first = _ready_complete(session, keys)
    # 构建第二份完整修订（败者目标），其 base 也是 rev-1。
    with session_factory() as s, s.begin():
        _build_second_complete(s, keys, first, correction_ids=[], revision_id="complete-2")
    barrier = Barrier(2)

    def _run(revision_id):
        barrier.wait()
        try:
            outcome = EvidenceActivationService(session_factory).activate(
                target_snapshot_id="snap-1",
                target_revision_id=revision_id,
                expected_revision=1,
                actor=revision_id,
                reason="并发激活",
                candidate_id=f"producer-{revision_id}",
            )
            return "success", outcome.active_revision_id
        except ActivationRevisionConflictError:
            return "conflict", revision_id

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(_run, ["complete-1", "complete-2"]))
    assert sorted(kind for kind, _revision in results) == ["conflict", "success"]
    winner = next(revision for kind, revision in results if kind == "success")
    loser_revision = next(revision for kind, revision in results if kind == "conflict")
    with session_factory() as fresh:
        # 败者未追加成功激活事件（总数仍为 1）。
        events = EvidenceActivationEventRepository(fresh).list_by_episode(keys["episode_id"])
        assert len(events) == 1
        # 胜者指针保持。
        episode = EpisodeRepository(fresh).get(keys["episode_id"])
        assert episode.active_evidence_processing_revision_id == winner
        # 败者候选进入 revision_conflict。
        loser = EvidenceProcessingCandidateRepository(fresh).get(
            f"producer-{loser_revision}"
        )
        assert loser.status == EvidenceProcessingCandidateStatus.REVISION_CONFLICT

def test_activation_event_rollback_if_pointer_update_fails(stack, session_factory, monkeypatch):
    """故障注入：事件已追加后指针更新失败 → 整个事务回滚，三面无变化。"""
    session, _fixture, keys = stack
    _ready_complete(session, keys)
    service = EvidenceActivationService(session_factory)

    def _boom(*args, **kwargs):
        raise RuntimeError("注入的指针更新失败")

    monkeypatch.setattr(
        "app.storage.evidence_locator_repositories.apply_revisioned_update", _boom
    )
    with pytest.raises(RuntimeError, match="注入"):
        _activate(service, keys)
    monkeypatch.undo()
    with session_factory() as fresh:
        from sqlalchemy import select

        # 无激活事件。
        assert (
            fresh.execute(
                select(EvidenceActivationEventRecord)
            ).scalars().all() == []
        )
        # 快照状态未变（仍 READY，无 ready→active 事件）。
        snapshot_status_events = fresh.execute(
            select(EvidenceSnapshotStatusEventRecord)
        ).scalars().all()
        assert [e.event for e in snapshot_status_events].count("activate") == 0
        # 审核节点指针未变。
        episode = EpisodeRepository(fresh).get(keys["episode_id"])
        assert episode.active_evidence_snapshot_id is None
        assert episode.revision == 1


def test_repository_direct_activation_also_transitions_ready_candidate(
    stack, session_factory
):
    """唯一仓储入口不能留下“指针已启用、候选仍待启用”的分裂状态。"""
    session, _fixture, keys = stack
    first = _ready_complete(session, keys)
    service = EvidenceActivationService(session_factory)
    _activate(service, keys)
    with session_factory() as current, current.begin():
        _build_second_complete(
            current,
            keys,
            first,
            correction_ids=[],
            revision_id="complete-direct",
            expected_revision=2,
        )
    with session_factory() as direct, direct.begin():
        saved, updated, candidate = EvidenceActivationEventRepository(
            direct
        ).append_and_switch(
            _activation_event(
                keys,
                event_id="evt-direct",
                activation_seq=2,
                event_kind="activate",
                from_snapshot_id="snap-1",
                from_revision_id="complete-1",
                to_revision_id="complete-direct",
                candidate_id="producer-complete-direct",
                expected_revision=2,
                actor="tester",
                reason="仓储原子启用",
            )
        )
        assert saved.to_revision_id == "complete-direct"
        assert updated.active_evidence_processing_revision_id == "complete-direct"
        assert candidate is not None
        assert candidate.status == EvidenceProcessingCandidateStatus.ACTIVE


def test_repository_rejects_stale_ready_candidate_without_partial_commit(
    stack, session_factory
):
    """候选冻结修订号必须与启用命令一致；拒绝后四面均保持原状。"""
    session, _fixture, keys = stack
    first = _ready_complete(session, keys)
    service = EvidenceActivationService(session_factory)
    _activate(service, keys)
    with session_factory() as current, current.begin():
        _build_second_complete(
            current,
            keys,
            first,
            correction_ids=[],
            revision_id="complete-stale",
            expected_revision=1,
        )
    with (
        session_factory() as direct,
        pytest.raises(InvalidReferenceError, match="预期修订已失效"),
        direct.begin(),
    ):
        EvidenceActivationEventRepository(direct).append_and_switch(
            _activation_event(
                keys,
                event_id="evt-stale",
                activation_seq=2,
                event_kind="activate",
                from_snapshot_id="snap-1",
                from_revision_id="complete-1",
                to_revision_id="complete-stale",
                candidate_id="producer-complete-stale",
                expected_revision=2,
                actor="tester",
                reason="不应启用陈旧候选",
            )
        )
    with session_factory() as fresh:
        episode = EpisodeRepository(fresh).get(keys["episode_id"])
        assert episode.active_evidence_processing_revision_id == "complete-1"
        assert len(
            EvidenceActivationEventRepository(fresh).list_by_episode(keys["episode_id"])
        ) == 1
        stale = EvidenceProcessingCandidateRepository(fresh).get(
            "producer-complete-stale"
        )
        assert stale.status == EvidenceProcessingCandidateStatus.READY


def test_candidate_transition_failure_rolls_back_event_snapshot_and_pointers(
    stack, session_factory, monkeypatch
):
    """候选状态事件失败时，事件、快照启用和成对指针必须一并回滚。"""
    session, _fixture, keys = stack
    _ready_complete(session, keys)
    original = EvidenceProcessingCandidateRepository.append_event

    def _fail_activate(self, event):
        if event.event_kind.value == "activate":
            raise RuntimeError("注入的候选状态转换失败")
        return original(self, event)

    monkeypatch.setattr(EvidenceProcessingCandidateRepository, "append_event", _fail_activate)
    with pytest.raises(RuntimeError, match="候选状态转换失败"):
        _activate(EvidenceActivationService(session_factory), keys)
    with session_factory() as fresh:
        assert EvidenceActivationEventRepository(fresh).list_by_episode(
            keys["episode_id"]
        ) == []
        assert EvidenceSnapshotRepository(fresh).current_status("snap-1") == SnapshotStatus.READY
        episode = EpisodeRepository(fresh).get(keys["episode_id"])
        assert episode.active_evidence_snapshot_id is None
        candidate = EvidenceProcessingCandidateRepository(fresh).get(
            "producer-complete-1"
        )
        assert candidate.status == EvidenceProcessingCandidateStatus.READY

# --------------------------------------------------------------------------- 幂等

def test_activation_idempotency_replay(stack, session_factory):
    session, _fixture, keys = stack
    _ready_complete(session, keys)
    service = EvidenceActivationService(session_factory)
    service.activate(
        target_snapshot_id="snap-1", target_revision_id="complete-1",
        expected_revision=1, actor="tester", reason="发布", event_id="evt-fixed",
        candidate_id="producer-complete-1",
    )
    replay = service.activate(
        target_snapshot_id="snap-1", target_revision_id="complete-1",
        expected_revision=1, actor="tester", reason="发布", event_id="evt-fixed",
        candidate_id="producer-complete-1",
    )
    assert replay.event.event_id == "evt-fixed"
    with session_factory() as fresh:
        assert len(
            EvidenceActivationEventRepository(fresh).list_by_episode(keys["episode_id"])
        ) == 1


def test_activation_replay_returns_original_event_projection_after_later_activation(
    stack, session_factory
):
    session, _fixture, keys = stack
    first = _ready_complete(session, keys)
    with session_factory() as current, current.begin():
        _build_second_complete(
            current,
            keys,
            first,
            correction_ids=[],
            revision_id="complete-2",
            expected_revision=2,
        )
    service = EvidenceActivationService(session_factory)
    service.activate(
        target_snapshot_id="snap-1",
        target_revision_id="complete-1",
        expected_revision=1,
        actor="tester",
        reason="首次发布",
        event_id="evt-first",
        candidate_id="producer-complete-1",
    )
    service.activate(
        target_snapshot_id="snap-1",
        target_revision_id="complete-2",
        expected_revision=2,
        actor="tester",
        reason="第二次发布",
        candidate_id="producer-complete-2",
    )

    replay = service.activate(
        target_snapshot_id="snap-1",
        target_revision_id="complete-1",
        expected_revision=1,
        actor="tester",
        reason="首次发布",
        event_id="evt-first",
        candidate_id="producer-complete-1",
    )
    assert replay.active_revision_id == "complete-1"
    assert replay.resulting_episode_revision == 2
    with session_factory() as fresh:
        assert (
            EpisodeRepository(fresh)
            .get(keys["episode_id"])
            .active_evidence_processing_revision_id
            == "complete-2"
        )


def test_activation_event_id_cannot_replay_with_another_candidate(
    stack, session_factory
):
    session, _fixture, keys = stack
    first = _ready_complete(session, keys)
    with session_factory() as current, current.begin():
        _build_second_complete(
            current,
            keys,
            first,
            correction_ids=[],
            revision_id="complete-2",
        )
    service = EvidenceActivationService(session_factory)
    service.activate(
        target_snapshot_id="snap-1",
        target_revision_id="complete-1",
        expected_revision=1,
        actor="tester",
        reason="发布",
        event_id="evt-candidate",
        candidate_id="producer-complete-1",
    )
    with pytest.raises(ActivationIdempotencyConflictError, match="动作、目标"):
        service.activate(
            target_snapshot_id="snap-1",
            target_revision_id="complete-1",
            expected_revision=1,
            actor="tester",
            reason="发布",
            event_id="evt-candidate",
            candidate_id="producer-complete-2",
        )

def test_activation_idempotency_conflicting_target_rejected(stack, session_factory):
    session, _fixture, keys = stack
    first = _ready_complete(session, keys)
    with session_factory() as s, s.begin():
        _build_second_complete(s, keys, first, correction_ids=[], revision_id="complete-2")
    service = EvidenceActivationService(session_factory)
    service.activate(
        target_snapshot_id="snap-1", target_revision_id="complete-1",
        expected_revision=1, actor="tester", reason="发布", event_id="evt-fixed",
        candidate_id="producer-complete-1",
    )
    with pytest.raises(ActivationIdempotencyConflictError, match="动作、目标、修订号或说明不一致"):
        service.activate(
            target_snapshot_id="snap-1", target_revision_id="complete-2",
            expected_revision=2, actor="tester", reason="发布", event_id="evt-fixed",
            candidate_id="producer-complete-2",
        )


def test_activation_event_cannot_replay_as_rollback(stack, session_factory):
    session, _fixture, keys = stack
    _ready_complete(session, keys)
    service = EvidenceActivationService(session_factory)
    service.activate(
        target_snapshot_id="snap-1",
        target_revision_id="complete-1",
        expected_revision=1,
        actor="tester",
        reason="发布",
        event_id="evt-kind",
        candidate_id="producer-complete-1",
    )
    with pytest.raises(ActivationIdempotencyConflictError, match="动作、目标"):
        service.rollback(
            target_snapshot_id="snap-1",
            target_revision_id="complete-1",
            expected_revision=1,
            actor="tester",
            reason="发布",
            event_id="evt-kind",
        )


def test_candidate_cannot_activate_another_complete_revision(stack, session_factory):
    session, _fixture, keys = stack
    first = _ready_complete(session, keys)
    with session_factory() as current, current.begin():
        _build_second_complete(
            current,
            keys,
            first,
            correction_ids=[],
            revision_id="complete-2",
        )
    with pytest.raises(ActivationGateError, match="只能启用其构建"):
        EvidenceActivationService(session_factory).activate(
            target_snapshot_id="snap-1",
            target_revision_id="complete-2",
            expected_revision=1,
            actor="tester",
            reason="发布",
            candidate_id="producer-complete-1",
        )

# --------------------------------------------------------------------------- 指针权威

def test_current_snapshot_pointer_authority(stack, session_factory):
    """指针为 null 时即使存在 ACTIVE 状态也不回退（§8.4 反例 4）。"""
    session, _fixture, keys = stack
    service = EvidenceActivationService(session_factory)
    with session_factory() as fresh:
        # 指针未建立 → 无当前快照。
        assert EvidenceActivationService.current_snapshot_id(fresh, keys["episode_id"]) is None
        assert EvidenceActivationService.current_snapshot(fresh, keys["episode_id"]) is None
    # 新建一个无状态事件候选快照 snap-2（成员 doc-2，与 snap-1 集合不同）
    # 并伪造为 ACTIVE（指针仍 null）→ 仍不回退。
    from app.domain.contracts.enums import SnapshotMemberOrigin
    from app.domain.contracts.evidence_ingestion import (
        EvidenceSnapshot,
        EvidenceSnapshotMember,
    )
    from app.domain.publication import evidence_snapshot_collection_hash
    from app.storage.evidence_repositories import (
        BlobRepository,
        SourceDocumentRepository,
    )
    from tests.v2.storage.test_ocr_repositories import make_blob, make_version

    with session_factory() as fresh, fresh.begin():
        blob2 = make_blob(b"pdf-bytes-2")
        BlobRepository(fresh).get_or_create_by_sha256(blob2)
        SourceDocumentRepository(fresh).create_version(
            make_version(
                version_id="doc-2", logical_id="log-2", blob_sha=blob2.sha256,
                scope=(keys["project_id"], keys["subject_id"], keys["episode_id"]),
                page_count=1,
            )
        )
        snap2 = EvidenceSnapshot(
            evidence_snapshot_id="snap-2",
            project_id=keys["project_id"], subject_id=keys["subject_id"],
            review_episode_id=keys["episode_id"], upload_mode="full",
            members=[
                EvidenceSnapshotMember(
                    member_id="m-2", snapshot_id="snap-2",
                    logical_document_id="log-2", source_document_version_id="doc-2",
                    origin=SnapshotMemberOrigin.ADDED,
                )
            ],
            collection_sha256=evidence_snapshot_collection_hash(members=[("log-2", "doc-2")]),
            status=SnapshotStatus.STAGED, created_at=FIXED_UTC, created_by="tester",
        )
        EvidenceSnapshotRepository(fresh).create_full(snap2)
        from app.storage.codecs import encode_contract

        repo = EvidenceSnapshotRepository(fresh)
        contract = repo.get("snap-2")
        activated = contract.model_copy(update={"status": SnapshotStatus.ACTIVE})
        payload_json, payload_sha256 = encode_contract(activated)
        row = fresh.get(EvidenceSnapshotV2Record, "snap-2")
        row.status = SnapshotStatus.ACTIVE.value
        row.payload_json = payload_json
        row.payload_sha256 = payload_sha256
    with session_factory() as fresh:
        # 存在 ACTIVE 状态但指针为 null → 不得作为当前版本 fallback。
        assert EvidenceActivationService.current_snapshot_id(fresh, keys["episode_id"]) is None
        assert EvidenceActivationService.current_snapshot(fresh, keys["episode_id"]) is None
    # 正式激活后 → 指针权威生效。
    _ready_complete(session, keys)
    _activate(service, keys)
    with session_factory() as fresh:
        assert (
            EvidenceActivationService.current_snapshot_id(fresh, keys["episode_id"])
            == "snap-1"
        )
        snapshot = EvidenceActivationService.current_snapshot(fresh, keys["episode_id"])
        assert snapshot is not None and snapshot.evidence_snapshot_id == "snap-1"
