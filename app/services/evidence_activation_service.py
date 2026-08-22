"""Slice 4.4 证据版本原子激活/回滚服务（WP-44B）。

单一数据库事务内完成（§5.2）：重读并校验预期审核节点修订号与当前成对指针 → 完整
闭包门禁（base 修订永不可激活）→ 目标快照首次发布时追加 ``ready -> active`` 状态
事件（同一已激活快照的新处理修订不重复转换终态）→ 追加唯一连续 ``ActivationEvent``
→ 乐观锁更新 ``ReviewEpisode`` 两个活动指针并递增 revision。任一步失败则
ActivationEvent / 快照状态事件 / 审核节点更新全部回滚，绝不出现“事件成功但指针未变”
或“指针已变但事件缺失”（§8.4 反例 7）。

回滚（§5.3）只允许目标对曾在激活事件中出现且当前仍能完整回放；追加 ``rollback``
事件并切换成对指针，不改写旧快照/旧修订/旧审核结果。并发同 expected-revision 只
允许一个成功；败者只记录其候选 ``revision_conflict`` 转换，绝不追加成功激活事件。

当前版本唯一权威 = ``ReviewEpisode.active_evidence_snapshot_id`` +
``active_evidence_processing_revision_id``；本服务提供 ``current_snapshot`` /
``current_snapshot_id`` 供上传基准等读取路径消费（§5.5，绝不按时间/ID/状态回退）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.enums import (
    ActivationEventKind,
    EvidenceProcessingCandidateStatus,
    ProcessingCandidateEventKind,
    SnapshotStatus,
)
from app.domain.contracts.evidence_ingestion import (
    EvidenceSnapshot,
    EvidenceSnapshotStatusEvent,
)
from app.domain.contracts.evidence_locator import (
    CompleteEvidenceProcessingRevision,
    EvidenceActivationEvent,
    EvidenceProcessingCandidate,
    EvidenceProcessingCandidateEvent,
    activation_command_hash,
)
from app.storage.codecs import encode_contract
from app.storage.concurrency import FieldChange, StaleRevisionError
from app.storage.evidence_locator_models import EvidenceActivationEventRecord
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository,
    EvidenceActivationEventRepository,
    EvidenceProcessingCandidateRepository,
    OcrRevisionKindError,
)
from app.storage.evidence_models import EvidenceSnapshotStatusEventRecord
from app.storage.evidence_repositories import EvidenceSnapshotRepository
from app.storage.repositories import EpisodeRepository

__all__ = [
    "ActivationAlreadyActiveError",
    "ActivationGateError",
    "ActivationIdempotencyConflictError",
    "ActivationOutcome",
    "ActivationRevisionConflictError",
    "EvidenceActivationService",
    "RollbackTargetError",
]


def _utcnow():
    from datetime import UTC, datetime

    return datetime.now(UTC)


class ActivationServiceError(RuntimeError):
    """证据版本激活/回滚服务领域错误基类。"""


class ActivationGateError(ActivationServiceError):
    """完整修订闭包/作用域/状态不满足激活门禁。"""


class ActivationAlreadyActiveError(ActivationServiceError):
    """目标快照/处理修订对已是当前活动版本（拒绝无意义切换）。"""


class ActivationRevisionConflictError(ActivationServiceError):
    """预期审核节点修订号不匹配（并发败者）；未追加任何成功激活事件。"""


class RollbackTargetError(ActivationServiceError):
    """回滚目标未曾在激活事件中出现 / 已是当前版本 / 无法完整回放。"""


class ActivationIdempotencyConflictError(ActivationServiceError):
    """同一 event_id 已存在但请求的切换对不一致。"""


@dataclass(frozen=True)
class ActivationOutcome:
    """一次激活/回滚的结果：事件、更新后的审核节点与候选状态。"""

    event: EvidenceActivationEvent
    review_episode_id: str
    resulting_episode_revision: int
    active_snapshot_id: str
    active_revision_id: str
    snapshot_status_transitioned: bool = False
    candidate: EvidenceProcessingCandidate | None = None


class EvidenceActivationService:
    """原子激活/回滚服务 + 当前版本权威投影。"""

    def __init__(
        self, session_factory: sessionmaker, artifact_store: Any = None
    ) -> None:
        self.session_factory = session_factory
        self.artifact_store = artifact_store

    @staticmethod
    def _begin_write(session: Session) -> None:
        """SQLite 先取得写保留锁，避免两个延迟事务先读后写形成忙快照。"""
        if session.get_bind().dialect.name == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))
        else:
            session.begin()

    # ------------------------------------------------------------------ 激活

    def activate(
        self,
        *,
        target_snapshot_id: str,
        target_revision_id: str,
        expected_revision: int,
        actor: str,
        reason: str,
        candidate_id: str,
        job_id: str | None = None,
        event_id: str | None = None,
    ) -> ActivationOutcome:
        with self.session_factory() as session:
            self._begin_write(session)
            try:
                replay = self._replay_event(
                    session,
                    event_id=event_id,
                    event_kind=ActivationEventKind.ACTIVATE,
                    target_snapshot_id=target_snapshot_id,
                    target_revision_id=target_revision_id,
                    expected_revision=expected_revision,
                    actor=actor,
                    reason=reason,
                    job_id=job_id,
                    candidate_id=candidate_id,
                )
                if replay is not None:
                    session.commit()
                    return replay
                try:
                    with session.begin_nested():
                        outcome = self._activate_locked(
                            session,
                            target_snapshot_id=target_snapshot_id,
                            target_revision_id=target_revision_id,
                            expected_revision=expected_revision,
                            actor=actor,
                            reason=reason,
                            candidate_id=candidate_id,
                            job_id=job_id,
                            event_id=event_id,
                        )
                except StaleRevisionError as exc:
                    if candidate_id is not None:
                        self._record_candidate_conflict(
                            session, candidate_id, actor, exc
                        )
                        session.commit()
                    raise ActivationRevisionConflictError(
                        f"预期审核节点修订号 {expected_revision} 已失效（当前 "
                        f"{exc.current_revision}）；败者未追加任何成功激活事件"
                    ) from exc
            except BaseException:
                session.rollback()
                raise
            session.commit()
            return outcome

    def _activate_locked(
        self,
        session: Session,
        *,
        target_snapshot_id: str,
        target_revision_id: str,
        expected_revision: int,
        actor: str,
        reason: str,
        candidate_id: str,
        job_id: str | None,
        event_id: str | None,
    ) -> ActivationOutcome:
        snapshot = EvidenceSnapshotRepository(session).get(target_snapshot_id)
        episode = EpisodeRepository(session).get(snapshot.review_episode_id)
        if (snapshot.project_id, snapshot.subject_id) != (
            episode.project_id,
            episode.subject_id,
        ):
            raise ActivationGateError("目标快照与审核节点作用域不一致")
        self._require_episode_revision(episode, expected_revision)

        complete = self._load_activatable(session, target_revision_id)
        if complete.evidence_snapshot_id != target_snapshot_id:
            raise ActivationGateError("目标处理修订不属于目标快照")
        if complete.review_episode_id != episode.review_episode_id:
            raise ActivationGateError("目标处理修订与审核节点作用域不一致")

        status_transitioned = self._publish_snapshot_if_required(
            session, target_snapshot_id, actor, reason
        )

        from_snapshot = episode.active_evidence_snapshot_id
        from_revision = episode.active_evidence_processing_revision_id
        if (from_snapshot, from_revision) == (target_snapshot_id, target_revision_id):
            raise ActivationAlreadyActiveError(
                "该快照/处理修订对已是当前活动版本，拒绝无意义激活"
            )

        self._load_ready_candidate(
            session,
            candidate_id,
            target_snapshot_id,
            complete,
            expected_revision,
        )
        next_seq = self._next_activation_seq(session, episode.review_episode_id)
        command_sha256 = activation_command_hash(
            event_kind=ActivationEventKind.ACTIVATE,
            candidate_id=candidate_id,
            target_snapshot_id=target_snapshot_id,
            target_revision_id=target_revision_id,
            expected_revision=expected_revision,
            actor=actor,
            reason=reason,
            job_id=job_id,
        )
        event = EvidenceActivationEvent(
            event_id=event_id or f"evt-{command_sha256[:32]}",
            review_episode_id=episode.review_episode_id,
            activation_seq=next_seq,
            event_kind=ActivationEventKind.ACTIVATE,
            from_snapshot_id=from_snapshot,
            from_revision_id=from_revision,
            to_snapshot_id=target_snapshot_id,
            to_revision_id=target_revision_id,
            reason=reason,
            actor=actor,
            job_id=job_id,
            candidate_id=candidate_id,
            expected_revision=expected_revision,
            resulting_episode_revision=expected_revision + 1,
            snapshot_status_transitioned=status_transitioned,
            command_sha256=command_sha256,
            created_at=_utcnow(),
        )
        saved_event, updated, candidate = EvidenceActivationEventRepository(
            session
        ).append_and_switch(event)
        return ActivationOutcome(
            event=saved_event,
            review_episode_id=updated.review_episode_id,
            resulting_episode_revision=updated.revision,
            active_snapshot_id=target_snapshot_id,
            active_revision_id=target_revision_id,
            snapshot_status_transitioned=status_transitioned,
            candidate=candidate,
        )

    def activate_in_session(
        self,
        session: Session,
        *,
        target_snapshot_id: str,
        target_revision_id: str,
        expected_revision: int,
        actor: str,
        reason: str,
        candidate_id: str,
        job_id: str | None = None,
        event_id: str | None = None,
    ) -> ActivationOutcome:
        """在调用方事务内执行原子激活（不提交）。

        事件/快照状态/候选状态/成对指针全部写入调用方会话；提交或回滚由调用方
        负责。并发败者（StaleRevisionError）在**同一会话**记录候选
        revision_conflict 转换并抛 ``ActivationRevisionConflictError``，调用方可
        选择提交（保留败者冲突投影，WP-44B 语义）或回滚（故障注入无任何残留）。
        """
        try:
            # _activate_locked 先可能发布快照，后在指针乐观锁处失败。
            # 整段放入保存点，并发败者才不会留下“快照已活动、
            # 指针未切换”的半状态。
            with session.begin_nested():
                return self._activate_locked(
                    session,
                    target_snapshot_id=target_snapshot_id,
                    target_revision_id=target_revision_id,
                    expected_revision=expected_revision,
                    actor=actor,
                    reason=reason,
                    candidate_id=candidate_id,
                    job_id=job_id,
                    event_id=event_id,
                )
        except StaleRevisionError as exc:
            if candidate_id is not None:
                self._record_candidate_conflict(session, candidate_id, actor, exc)
            raise ActivationRevisionConflictError(
                f"预期审核节点修订号 {expected_revision} 已失效（当前 "
                f"{exc.current_revision}）；败者未追加任何成功激活事件"
            ) from exc

    # ------------------------------------------------------------------ 回滚

    def rollback(
        self,
        *,
        target_snapshot_id: str,
        target_revision_id: str,
        expected_revision: int,
        actor: str,
        reason: str,
        event_id: str | None = None,
    ) -> ActivationOutcome:
        with self.session_factory() as session:
            self._begin_write(session)
            try:
                replay = self._replay_event(
                    session,
                    event_id=event_id,
                    event_kind=ActivationEventKind.ROLLBACK,
                    target_snapshot_id=target_snapshot_id,
                    target_revision_id=target_revision_id,
                    expected_revision=expected_revision,
                    actor=actor,
                    reason=reason,
                    job_id=None,
                    candidate_id=None,
                )
                if replay is not None:
                    session.commit()
                    return replay
                outcome = self._rollback_locked(
                    session,
                    target_snapshot_id=target_snapshot_id,
                    target_revision_id=target_revision_id,
                    expected_revision=expected_revision,
                    actor=actor,
                    reason=reason,
                    event_id=event_id,
                )
            except BaseException:
                session.rollback()
                raise
            session.commit()
            return outcome

    def _rollback_locked(
        self,
        session: Session,
        *,
        target_snapshot_id: str,
        target_revision_id: str,
        expected_revision: int,
        actor: str,
        reason: str,
        event_id: str | None,
    ) -> ActivationOutcome:
        complete = self._load_activatable(session, target_revision_id)
        if complete.evidence_snapshot_id != target_snapshot_id:
            raise RollbackTargetError("回滚目标的处理修订不属于目标快照")
        episode = EpisodeRepository(session).get(complete.review_episode_id)
        self._require_episode_revision(episode, expected_revision)

        events = EvidenceActivationEventRepository(session).list_by_episode(
            episode.review_episode_id
        )
        if not any(
            e.to_snapshot_id == target_snapshot_id
            and e.to_revision_id == target_revision_id
            for e in events
        ):
            raise RollbackTargetError(
                "回滚目标对 (快照, 处理修订) 未曾在任何激活事件中出现过，拒绝回滚"
            )

        from_snapshot = episode.active_evidence_snapshot_id
        from_revision = episode.active_evidence_processing_revision_id
        if (from_snapshot, from_revision) == (target_snapshot_id, target_revision_id):
            raise RollbackTargetError("回滚目标对已是当前活动版本")

        next_seq = self._next_activation_seq(session, episode.review_episode_id)
        command_sha256 = activation_command_hash(
            event_kind=ActivationEventKind.ROLLBACK,
            candidate_id=None,
            target_snapshot_id=target_snapshot_id,
            target_revision_id=target_revision_id,
            expected_revision=expected_revision,
            actor=actor,
            reason=reason,
            job_id=None,
        )
        event = EvidenceActivationEvent(
            event_id=event_id or f"evt-{command_sha256[:32]}",
            review_episode_id=episode.review_episode_id,
            activation_seq=next_seq,
            event_kind=ActivationEventKind.ROLLBACK,
            from_snapshot_id=from_snapshot,
            from_revision_id=from_revision,
            to_snapshot_id=target_snapshot_id,
            to_revision_id=target_revision_id,
            reason=reason,
            actor=actor,
            job_id=None,
            candidate_id=None,
            expected_revision=expected_revision,
            resulting_episode_revision=expected_revision + 1,
            snapshot_status_transitioned=False,
            command_sha256=command_sha256,
            created_at=_utcnow(),
        )
        saved_event, updated, _candidate = EvidenceActivationEventRepository(
            session
        ).append_and_switch(event)
        return ActivationOutcome(
            event=saved_event,
            review_episode_id=updated.review_episode_id,
            resulting_episode_revision=updated.revision,
            active_snapshot_id=target_snapshot_id,
            active_revision_id=target_revision_id,
        )

    def rollback_in_session(
        self,
        session: Session,
        *,
        target_snapshot_id: str,
        target_revision_id: str,
        expected_revision: int,
        actor: str,
        reason: str,
        event_id: str | None = None,
    ) -> ActivationOutcome:
        """在调用方事务内执行回滚（不提交）；提交/回滚由调用方负责。"""
        try:
            with session.begin_nested():
                return self._rollback_locked(
                    session,
                    target_snapshot_id=target_snapshot_id,
                    target_revision_id=target_revision_id,
                    expected_revision=expected_revision,
                    actor=actor,
                    reason=reason,
                    event_id=event_id,
                )
        except StaleRevisionError as exc:
            raise ActivationRevisionConflictError(
                f"预期审核节点修订号 {expected_revision} 已失效（当前 "
                f"{exc.current_revision}）；未追加回滚事件"
            ) from exc

    # ------------------------------------------------------------------ 工具

    @staticmethod
    def _require_episode_revision(episode, expected_revision: int) -> None:
        if episode.revision == expected_revision:
            return
        raise StaleRevisionError(
            entity_type="review_episode",
            entity_id=episode.review_episode_id,
            expected_revision=expected_revision,
            current_revision=episode.revision,
            field_diff={
                "revision": FieldChange(
                    current=episode.revision,
                    submitted=expected_revision,
                )
            },
            current_record=episode,
        )

    def _load_activatable(
        self, session: Session, revision_id: str
    ) -> CompleteEvidenceProcessingRevision:
        """完整修订必须通过完整闭包门禁且可激活；base 修订永不可激活。"""
        try:
            complete = CompleteEvidenceProcessingRevisionRepository(
                session, self.artifact_store
            ).get(revision_id)
        except OcrRevisionKindError as exc:
            raise ActivationGateError(
                f"目标处理修订 {revision_id} 是基础修订（base），基础修订永不可激活"
            ) from exc
        if not complete.is_activatable or complete.status.value != "ready":
            raise ActivationGateError(
                f"目标处理修订 {revision_id} 不是可激活的完整修订（READY）"
            )
        return complete

    def _publish_snapshot_if_required(
        self, session: Session, snapshot_id: str, actor: str, reason: str
    ) -> bool:
        """目标快照首次发布：READY → 追加 ready→active；已激活则不重复转换终态。"""
        current = EvidenceSnapshotRepository(session).current_status(snapshot_id)
        if current == SnapshotStatus.ACTIVE:
            return False
        if current != SnapshotStatus.READY:
            raise ActivationGateError(
                f"目标快照 {snapshot_id} 当前状态为 {current.value}，不可激活"
                "（必须是 ready 或已激活）"
            )
        latest = session.execute(
            select(func.max(EvidenceSnapshotStatusEventRecord.seq)).where(
                EvidenceSnapshotStatusEventRecord.snapshot_id == snapshot_id
            )
        ).scalar_one()
        seq = int(latest or 0) + 1
        created_at = _utcnow()
        event_contract = EvidenceSnapshotStatusEvent(
            snapshot_id=snapshot_id,
            seq=seq,
            from_status=SnapshotStatus.READY,
            to_status=SnapshotStatus.ACTIVE,
            event="activate",
            actor=actor,
            reason=reason,
            created_at=created_at,
        )
        payload_json, payload_sha256 = encode_contract(event_contract)
        session.add(
            EvidenceSnapshotStatusEventRecord(
                snapshot_id=snapshot_id,
                seq=seq,
                from_status=SnapshotStatus.READY.value,
                to_status=SnapshotStatus.ACTIVE.value,
                event="activate",
                actor=actor,
                reason=reason,
                created_at=created_at,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
            )
        )
        return True

    def _load_ready_candidate(
        self,
        session: Session,
        candidate_id: str,
        target_snapshot_id: str,
        complete: CompleteEvidenceProcessingRevision,
        expected_revision: int,
    ) -> EvidenceProcessingCandidate:
        candidate = EvidenceProcessingCandidateRepository(
            session, self.artifact_store
        ).get(candidate_id)
        if candidate.status != EvidenceProcessingCandidateStatus.READY:
            raise ActivationGateError(
                f"候选 {candidate_id} 当前状态 {candidate.status.value}，不可激活"
            )
        if candidate.evidence_snapshot_id != target_snapshot_id:
            raise ActivationGateError("候选目标快照与激活目标不一致")
        if (
            candidate.base_processing_revision_id
            != complete.base_processing_revision_id
        ):
            raise ActivationGateError("候选基础修订与激活目标完整修订不一致")
        if candidate.complete_revision_id != complete.evidence_processing_revision_id:
            raise ActivationGateError("候选只能启用其构建并冻结的完整处理修订")
        if candidate.expected_revision != expected_revision:
            raise ActivationGateError("候选预期修订号与激活请求不一致")
        return candidate

    def _record_candidate_conflict(
        self, session: Session, candidate_id: str, actor: str, exc: StaleRevisionError
    ) -> None:
        """并发败者：只追加候选 revision-conflict 转换，绝不追加成功激活事件。"""
        repo = EvidenceProcessingCandidateRepository(session, self.artifact_store)
        candidate = repo.get(candidate_id)
        if candidate.status != EvidenceProcessingCandidateStatus.READY:
            return
        seq = len(repo.get_events(candidate_id)) + 1
        repo.append_event(
            EvidenceProcessingCandidateEvent(
                candidate_id=candidate_id,
                seq=seq,
                from_status=EvidenceProcessingCandidateStatus.READY,
                to_status=EvidenceProcessingCandidateStatus.REVISION_CONFLICT,
                event_kind=ProcessingCandidateEventKind.REVISION_MISMATCH,
                actor=actor,
                reason=f"并发激活：预期修订号 {exc.expected_revision} 已失效"
                f"（当前 {exc.current_revision}）",
                created_at=_utcnow(),
            )
        )

    @staticmethod
    def _next_activation_seq(session: Session, review_episode_id: str) -> int:
        latest = session.execute(
            select(func.max(EvidenceActivationEventRecord.activation_seq)).where(
                EvidenceActivationEventRecord.review_episode_id == review_episode_id
            )
        ).scalar_one()
        return int(latest or 0) + 1

    def _replay_event(
        self,
        session: Session,
        *,
        event_id: str | None,
        event_kind: ActivationEventKind,
        target_snapshot_id: str,
        target_revision_id: str,
        expected_revision: int,
        actor: str,
        reason: str,
        job_id: str | None,
        candidate_id: str | None,
    ) -> ActivationOutcome | None:
        """幂等回放必须核对完整命令身份，不能把激活事件冒充回滚。"""
        command_sha256 = activation_command_hash(
            event_kind=event_kind,
            candidate_id=candidate_id,
            target_snapshot_id=target_snapshot_id,
            target_revision_id=target_revision_id,
            expected_revision=expected_revision,
            actor=actor,
            reason=reason,
            job_id=job_id,
        )
        record = (
            session.get(EvidenceActivationEventRecord, event_id)
            if event_id is not None
            else None
        )
        if record is None:
            record = (
                session.execute(
                    select(EvidenceActivationEventRecord).where(
                        EvidenceActivationEventRecord.command_sha256 == command_sha256
                    )
                )
                .scalars()
                .first()
            )
        if record is None:
            return None
        event = EvidenceActivationEventRepository(session).get(record.event_id)
        if (
            event.command_sha256 != command_sha256
            or event.event_kind != event_kind
            or event.candidate_id != candidate_id
        ):
            raise ActivationIdempotencyConflictError(
                f"激活事件 {record.event_id} 已存在但动作、目标、修订号或说明不一致，"
                "拒绝幂等复用"
            )
        candidate = None
        if event.candidate_id is not None:
            candidate = EvidenceProcessingCandidateRepository(
                session, self.artifact_store
            ).get(event.candidate_id)
            if (
                candidate.status != EvidenceProcessingCandidateStatus.ACTIVE
                or candidate.complete_revision_id != event.to_revision_id
            ):
                raise ActivationGateError("幂等回放时生产候选状态或完整修订绑定已漂移")
        return ActivationOutcome(
            event=event,
            review_episode_id=event.review_episode_id,
            resulting_episode_revision=event.resulting_episode_revision,
            active_snapshot_id=event.to_snapshot_id,
            active_revision_id=event.to_revision_id,
            snapshot_status_transitioned=event.snapshot_status_transitioned,
            candidate=candidate,
        )

    # ------------------------------------------------------------------ 当前版本投影

    @staticmethod
    def current_snapshot(
        session: Session, review_episode_id: str
    ) -> EvidenceSnapshot | None:
        """当前活动快照（权威指针）；指针为 null 时返回 None，绝不按状态/时间回退。"""
        episode = EpisodeRepository(session).get(review_episode_id)
        if episode.active_evidence_snapshot_id is None:
            return None
        return EvidenceSnapshotRepository(session).get(
            episode.active_evidence_snapshot_id
        )

    @staticmethod
    def current_snapshot_id(session: Session, review_episode_id: str) -> str | None:
        episode = EpisodeRepository(session).get(review_episode_id)
        return episode.active_evidence_snapshot_id

    @staticmethod
    def current_revision_id(session: Session, review_episode_id: str) -> str | None:
        episode = EpisodeRepository(session).get(review_episode_id)
        return episode.active_evidence_processing_revision_id
