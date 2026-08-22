"""Slice 4.4 完整处理修订构建工作流（WP-44B）。

把「不可变完整修订」与「等待核对的可变过程」分开：``EvidenceProcessingCandidate``
管处理构建，快照管文档候选，激活事务负责二者汇合（§11 未决风险 5）。

- ``start``      绑定快照/base 修订/预期修订号/幂等键创建候选并进入 PROCESSING；
- ``run_build``  在单一事务内：逐页运行风险扫描（幂等旁路）→ 聚合闭包 → 前置
  blocking 门禁 → 冻结完整修订 → 追加 ``all_gates_passed`` → READY；失败按类型
  追加 ``blocking_risk_found``（NEEDS_ATTENTION）或 ``retryable_error``
  （RETRYABLE_FAILURE），绝不留下可激活半闭包根（§8.4 反例 2）。

候选失败/待核对不写 ``ReviewEpisode``、``ActivationEvent`` 或任何旧结果
stale/update-available 标记（§5.4 候选隔离）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.enums import (
    EvidenceProcessingCandidateStatus,
    ProcessingCandidateEventKind,
    SnapshotStatus,
)
from app.domain.contracts.evidence_locator import (
    CompleteEvidenceProcessingRevision,
    EvidenceProcessingCandidate,
    EvidenceProcessingCandidateEvent,
    ProcessingCandidateAttemptManifest,
    processing_candidate_input_hash,
)
from app.evidence.risk import OCR_RISK_RULE_VERSION
from app.services.evidence_revision_builder import (
    EvidenceRevisionBuilder,
    RevisionBuildError,
    UnresolvedBlockingRiskError,
)
from app.services.evidence_risk_service import EvidenceRiskScanService
from app.storage.codecs import PersistedContractInvalid
from app.storage.evidence_locator_models import EvidenceProcessingCandidateRecord
from app.storage.evidence_locator_repositories import (
    CandidateStateTransitionError,
    CompleteEvidenceProcessingRevisionRepository,
    EvidenceProcessingCandidateRepository,
    RevisionClosureError,
)
from app.storage.evidence_repositories import EvidenceSnapshotRepository
from app.storage.ocr_repositories import EvidenceProcessingRevisionRepository
from app.storage.repositories import InvalidReferenceError

__all__ = [
    "BuildNeedsAttentionError",
    "BuildRetryableFailureError",
    "EvidenceRevisionBuildRequest",
    "EvidenceRevisionWorkflow",
]




def _utcnow():
    from datetime import UTC, datetime

    return datetime.now(UTC)

class WorkflowError(RuntimeError):
    """处理候选构建工作流错误基类。"""


class BuildNeedsAttentionError(WorkflowError):
    """闭包存在未解除的 blocking 风险，候选进入 needs_attention 等待用户核对。"""


class BuildRetryableFailureError(WorkflowError):
    """构建遇可重试失败（缺扫描/闭包漂移/缺资料等），候选进入 retryable_failure。"""


@dataclass(frozen=True)
class EvidenceRevisionBuildRequest:
    """一次完整处理修订构建请求（绑定快照/base 修订/预期修订号/幂等键）。"""

    evidence_snapshot_id: str
    base_processing_revision_id: str
    project_id: str
    subject_id: str
    review_episode_id: str
    expected_revision: int
    idempotency_key: str
    created_by: str
    job_id: str | None = None
    scanner_rule_version: str = OCR_RISK_RULE_VERSION
    selected_locator_ids: list[str] = field(default_factory=list)
    attempt_manifest: ProcessingCandidateAttemptManifest = field(
        default_factory=ProcessingCandidateAttemptManifest
    )

    def __post_init__(self) -> None:
        if len(self.selected_locator_ids) != len(set(self.selected_locator_ids)):
            raise ValueError("所选证据定位编号不能重复")
        if (
            self.job_id is not None
            and sorted(self.selected_locator_ids) != self.attempt_manifest.locator_ids
        ):
            raise ValueError("候选定位选择必须与冻结尝试清单一致")

    def input_sha256(self) -> str:
        return processing_candidate_input_hash(
            evidence_snapshot_id=self.evidence_snapshot_id,
            base_processing_revision_id=self.base_processing_revision_id,
            expected_revision=self.expected_revision,
            scanner_rule_version=self.scanner_rule_version,
            selected_locator_ids=self.selected_locator_ids,
            attempt_manifest=self.attempt_manifest,
        )


class EvidenceRevisionWorkflow:
    """证据处理候选构建工作流（确定性；候选事件由追加事件投影状态）。"""

    def __init__(self, session_factory: sessionmaker, artifact_store=None) -> None:
        self.session_factory = session_factory
        self.artifact_store = artifact_store

    @staticmethod
    def _begin_write(session: Session) -> None:
        if session.get_bind().dialect.name == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))
        else:
            session.begin()

    def start(
        self, request: EvidenceRevisionBuildRequest, *, candidate_id: str | None = None
    ) -> EvidenceProcessingCandidate:
        candidate_id = candidate_id or f"cand-{uuid4().hex}"
        with self.session_factory() as session:
            self._begin_write(session)
            try:
                created = self.start_in_session(session, request, candidate_id=candidate_id)
                session.commit()
                if request.job_id is None:
                    return self.begin_attempt(
                        created.candidate_id, actor=request.created_by
                    )
                return created
            except BaseException:
                session.rollback()
                raise

    def start_in_session(
        self,
        session: Session,
        request: EvidenceRevisionBuildRequest,
        *,
        candidate_id: str | None = None,
    ) -> EvidenceProcessingCandidate:
        """在调用方事务内创建候选与首事件（不提交）。

        供命令服务在单一外事务（含幂等主张）中原子创建候选；提交/回滚由调用方
        负责，避免「候选已建但幂等记录缺失」或反向的半提交。
        """
        candidate_id = candidate_id or f"cand-{uuid4().hex}"
        repo = EvidenceProcessingCandidateRepository(
            session, self.artifact_store
        )
        candidate = EvidenceProcessingCandidate(
            candidate_id=candidate_id,
            evidence_snapshot_id=request.evidence_snapshot_id,
            base_processing_revision_id=request.base_processing_revision_id,
            project_id=request.project_id,
            subject_id=request.subject_id,
            review_episode_id=request.review_episode_id,
            expected_revision=request.expected_revision,
            job_id=request.job_id,
            idempotency_key=request.idempotency_key,
            scanner_rule_version=request.scanner_rule_version,
            selected_locator_ids=sorted(request.selected_locator_ids),
            attempt_manifest=request.attempt_manifest,
            candidate_input_sha256=request.input_sha256(),
            complete_revision_id=None,
            status=EvidenceProcessingCandidateStatus.STAGED,
            created_by=request.created_by,
            created_at=_utcnow(),
        )
        return repo.create(candidate)

    def begin_attempt(self, candidate_id: str, *, actor: str) -> EvidenceProcessingCandidate:
        """后台任务取得租约后进入处理；重试复用已冻结的同一尝试清单。"""
        with self.session_factory() as session:
            self._begin_write(session)
            try:
                repo = EvidenceProcessingCandidateRepository(
                    session, self.artifact_store
                )
                candidate = repo.get(candidate_id)
                if candidate.status == EvidenceProcessingCandidateStatus.PROCESSING:
                    session.commit()
                    return candidate
                event_kind = {
                    EvidenceProcessingCandidateStatus.STAGED:
                        ProcessingCandidateEventKind.WORKER_START,
                    EvidenceProcessingCandidateStatus.RETRYABLE_FAILURE:
                        ProcessingCandidateEventKind.RETRY,
                }.get(candidate.status)
                if event_kind is None:
                    raise WorkflowError("当前候选状态不能开始后台构建")
                started = repo.append_event(
                    EvidenceProcessingCandidateEvent(
                        candidate_id=candidate_id,
                        seq=len(repo.get_events(candidate_id)) + 1,
                        from_status=candidate.status,
                        to_status=EvidenceProcessingCandidateStatus.PROCESSING,
                        event_kind=event_kind,
                        actor=actor,
                        reason="后台任务已取得处理权",
                        attempt_manifest=candidate.attempt_manifest,
                        attempt_input_sha256=candidate.candidate_input_sha256,
                        created_at=_utcnow(),
                    )
                )
                session.commit()
                return started
            except BaseException:
                session.rollback()
                raise

    def get_candidate(self, candidate_id: str) -> EvidenceProcessingCandidate:
        """读取候选的持久状态，供后台执行器在恢复时做幂等终态判断。"""
        with self.session_factory() as session:
            return EvidenceProcessingCandidateRepository(
                session, self.artifact_store
            ).get(candidate_id)

    def resume_after_attention_in_session(
        self,
        session: Session,
        *,
        candidate_id: str,
        attempt_manifest: ProcessingCandidateAttemptManifest,
        actor: str,
        reason: str,
    ) -> EvidenceProcessingCandidate:
        """用户补完核对后，以新的冻结清单把同一候选重新排队。

        此处只持久化新一轮输入，不能提前进入 ``processing``；后台任务再次
        取得租约后，``begin_attempt`` 才追加真正的开始处理事件。
        """
        repo = EvidenceProcessingCandidateRepository(session, self.artifact_store)
        candidate = repo.get(candidate_id)
        if candidate.status != EvidenceProcessingCandidateStatus.NEEDS_ATTENTION:
            raise WorkflowError("目标资料版本当前不在等待核对状态")
        attempt_hash = processing_candidate_input_hash(
            evidence_snapshot_id=candidate.evidence_snapshot_id,
            base_processing_revision_id=candidate.base_processing_revision_id,
            expected_revision=candidate.expected_revision,
            scanner_rule_version=candidate.scanner_rule_version,
            selected_locator_ids=attempt_manifest.locator_ids,
            attempt_manifest=attempt_manifest,
        )
        return repo.append_event(
            EvidenceProcessingCandidateEvent(
                candidate_id=candidate_id,
                seq=len(repo.get_events(candidate_id)) + 1,
                from_status=EvidenceProcessingCandidateStatus.NEEDS_ATTENTION,
                to_status=EvidenceProcessingCandidateStatus.STAGED,
                event_kind=ProcessingCandidateEventKind.CORRECTION_OR_RESOLUTION,
                actor=actor,
                reason=reason,
                attempt_manifest=attempt_manifest,
                attempt_input_sha256=attempt_hash,
                created_at=_utcnow(),
            )
        )

    def run_build(self, candidate_id: str) -> EvidenceProcessingCandidate:
        """在单一事务内完成扫描→闭包→冻结→状态事件；失败按类型进入失败/待核对。

        失败时候选事件（blocking_risk_found / retryable_error）与已扫描的不可变
        旁路工件在同一事务提交（§4.3 工件可在失败后复用），再向调用方抛出类型化
        错误；完整修订根绝不为半闭包状态提交。
        """
        with self.session_factory() as session:
            self._begin_write(session)
            try:
                result = self._run_build_in_session(session, candidate_id)
            except BuildNeedsAttentionError:
                session.commit()
                raise
            except BuildRetryableFailureError:
                session.commit()
                raise
            except Exception as exc:
                session.rollback()
                self._record_unexpected_failure(candidate_id, exc)
                raise BuildRetryableFailureError(
                    "完整处理修订构建遇到未预期错误，已转为可重试状态"
                ) from exc
            except BaseException:
                session.rollback()
                raise
            else:
                session.commit()
                return result

    def _record_unexpected_failure(self, candidate_id: str, exc: Exception) -> None:
        """主事务回滚后独立落失败状态；落库不可用时由陈旧处理中恢复兜底。"""
        with self.session_factory() as session:
            self._begin_write(session)
            try:
                repo = EvidenceProcessingCandidateRepository(
                    session, self.artifact_store
                )
                candidate = repo.get(candidate_id)
                if candidate.status != EvidenceProcessingCandidateStatus.PROCESSING:
                    session.commit()
                    return
                repo.append_event(
                    EvidenceProcessingCandidateEvent(
                        candidate_id=candidate_id,
                        seq=len(repo.get_events(candidate_id)) + 1,
                        from_status=EvidenceProcessingCandidateStatus.PROCESSING,
                        to_status=EvidenceProcessingCandidateStatus.RETRYABLE_FAILURE,
                        event_kind=ProcessingCandidateEventKind.RETRYABLE_ERROR,
                        actor=candidate.created_by,
                        reason=f"构建异常已安全回滚：{type(exc).__name__}",
                        created_at=_utcnow(),
                    )
                )
                session.commit()
            except BaseException:
                session.rollback()
                raise

    def retry(self, candidate_id: str, *, actor: str, reason: str) -> EvidenceProcessingCandidate:
        """从可重试失败或待核对状态恢复，并立即重新执行冻结构建。"""
        with self.session_factory() as session:
            self._begin_write(session)
            try:
                repo = EvidenceProcessingCandidateRepository(
                    session, self.artifact_store
                )
                candidate = repo.get(candidate_id)
                event_kind = {
                    EvidenceProcessingCandidateStatus.RETRYABLE_FAILURE:
                        ProcessingCandidateEventKind.RETRY,
                    EvidenceProcessingCandidateStatus.NEEDS_ATTENTION:
                        ProcessingCandidateEventKind.CORRECTION_OR_RESOLUTION,
                }.get(candidate.status)
                if event_kind is None:
                    raise WorkflowError("当前候选状态不允许重新构建")
                repo.append_event(
                    EvidenceProcessingCandidateEvent(
                        candidate_id=candidate_id,
                        seq=len(repo.get_events(candidate_id)) + 1,
                        from_status=candidate.status,
                        to_status=EvidenceProcessingCandidateStatus.PROCESSING,
                        event_kind=event_kind,
                        actor=actor,
                        reason=reason,
                        attempt_manifest=candidate.attempt_manifest,
                        attempt_input_sha256=candidate.candidate_input_sha256,
                        created_at=_utcnow(),
                    )
                )
                session.commit()
            except BaseException:
                session.rollback()
                raise
        return self.run_build(candidate_id)

    def cancel(self, candidate_id: str, *, actor: str, reason: str) -> EvidenceProcessingCandidate:
        """取消未完成候选；活动指针和已冻结历史不受影响。"""
        with self.session_factory() as session:
            self._begin_write(session)
            try:
                repo = EvidenceProcessingCandidateRepository(
                    session, self.artifact_store
                )
                candidate = repo.get(candidate_id)
                if candidate.status == EvidenceProcessingCandidateStatus.PROCESSING:
                    event_kind = ProcessingCandidateEventKind.CANCEL_AT_SAFE_BOUNDARY
                elif candidate.status in {
                    EvidenceProcessingCandidateStatus.STAGED,
                    EvidenceProcessingCandidateStatus.RETRYABLE_FAILURE,
                    EvidenceProcessingCandidateStatus.NEEDS_ATTENTION,
                }:
                    event_kind = ProcessingCandidateEventKind.CANCEL
                else:
                    raise WorkflowError("当前候选状态不允许取消")
                cancelled = repo.append_event(
                    EvidenceProcessingCandidateEvent(
                        candidate_id=candidate_id,
                        seq=len(repo.get_events(candidate_id)) + 1,
                        from_status=candidate.status,
                        to_status=EvidenceProcessingCandidateStatus.CANCELLED,
                        event_kind=event_kind,
                        actor=actor,
                        reason=reason,
                        created_at=_utcnow(),
                    )
                )
                session.commit()
                return cancelled
            except BaseException:
                session.rollback()
                raise

    def recover_stale_processing(
        self,
        *,
        stale_before: datetime,
        actor: str,
        reason: str,
    ) -> list[EvidenceProcessingCandidate]:
        """把服务中断遗留的陈旧“正在构建”候选转为可重试状态。

        只读取每个候选的最后一条持久事件时间；仍在阈值之后活动的候选不受影响。
        SQLite 下使用写保留锁，使恢复扫描与正常构建不能同时改写同一事件链。
        """
        if stale_before.tzinfo is None or stale_before.utcoffset() is None:
            raise ValueError("陈旧处理阈值必须包含时区")
        recovered: list[EvidenceProcessingCandidate] = []
        with self.session_factory() as session:
            self._begin_write(session)
            try:
                repo = EvidenceProcessingCandidateRepository(
                    session, self.artifact_store
                )
                rows = session.execute(
                    select(EvidenceProcessingCandidateRecord)
                    .where(
                        EvidenceProcessingCandidateRecord.status
                        == EvidenceProcessingCandidateStatus.PROCESSING.value
                    )
                    .order_by(EvidenceProcessingCandidateRecord.candidate_id)
                ).scalars().all()
                for row in rows:
                    candidate = repo.get(row.candidate_id)
                    events = repo.get_events(candidate.candidate_id)
                    if not events or events[-1].created_at > stale_before:
                        continue
                    recovered.append(
                        repo.append_event(
                            EvidenceProcessingCandidateEvent(
                                candidate_id=candidate.candidate_id,
                                seq=len(events) + 1,
                                from_status=EvidenceProcessingCandidateStatus.PROCESSING,
                                to_status=(
                                    EvidenceProcessingCandidateStatus.RETRYABLE_FAILURE
                                ),
                                event_kind=ProcessingCandidateEventKind.RETRYABLE_ERROR,
                                actor=actor,
                                reason=reason,
                                created_at=_utcnow(),
                            )
                        )
                    )
                session.commit()
                return recovered
            except BaseException:
                session.rollback()
                raise

    def _run_build_in_session(
        self,
        session: Session,
        candidate_id: str,
    ) -> EvidenceProcessingCandidate:
        repo = EvidenceProcessingCandidateRepository(session, self.artifact_store)
        candidate = repo.get(candidate_id)
        if candidate.status in {
            EvidenceProcessingCandidateStatus.READY,
            EvidenceProcessingCandidateStatus.ACTIVE,
        }:
            if candidate.complete_revision_id is None:
                raise WorkflowError("候选已完成但没有绑定完整处理修订")
            CompleteEvidenceProcessingRevisionRepository(
                session, self.artifact_store
            ).get(
                candidate.complete_revision_id
            )
            return candidate
        if candidate.status != EvidenceProcessingCandidateStatus.PROCESSING:
            raise WorkflowError(
                f"候选 {candidate_id} 当前状态 {candidate.status.value} 不可构建"
            )
        try:
            complete = self._scan_and_build(session, candidate)
            seq = len(repo.get_events(candidate_id)) + 1
            repo.append_event(
                EvidenceProcessingCandidateEvent(
                    candidate_id=candidate_id,
                    seq=seq,
                    from_status=EvidenceProcessingCandidateStatus.PROCESSING,
                    to_status=EvidenceProcessingCandidateStatus.READY,
                    event_kind=ProcessingCandidateEventKind.ALL_GATES_PASSED,
                    actor=candidate.created_by,
                    reason="完整处理修订闭包门禁通过",
                    complete_revision_id=complete.evidence_processing_revision_id,
                    created_at=_utcnow(),
                )
            )
            snapshot_repo = EvidenceSnapshotRepository(session)
            snapshot_status = snapshot_repo.current_status(
                candidate.evidence_snapshot_id
            )
            if snapshot_status == SnapshotStatus.PROCESSING:
                snapshot_repo.transition_status(
                    candidate.evidence_snapshot_id,
                    event="all_gates_passed",
                    new_status=SnapshotStatus.READY,
                    actor=candidate.created_by,
                    reason="资料分类、页面识别与必要核对已完成，可以启用本次资料版本。",
                )
            elif snapshot_status not in {
                SnapshotStatus.READY,
                SnapshotStatus.ACTIVE,
            }:
                raise WorkflowError("当前资料快照状态不允许生成可启用版本")
            return repo.get(candidate_id)
        except UnresolvedBlockingRiskError as exc:
            seq = len(repo.get_events(candidate_id)) + 1
            repo.append_event(
                EvidenceProcessingCandidateEvent(
                    candidate_id=candidate_id,
                    seq=seq,
                    from_status=EvidenceProcessingCandidateStatus.PROCESSING,
                    to_status=EvidenceProcessingCandidateStatus.NEEDS_ATTENTION,
                    event_kind=ProcessingCandidateEventKind.BLOCKING_RISK_FOUND,
                    actor=candidate.created_by,
                    reason=str(exc),
                    created_at=_utcnow(),
                )
            )
            raise BuildNeedsAttentionError(str(exc)) from exc
        except (
            RevisionClosureError,
            PersistedContractInvalid,
            InvalidReferenceError,
            CandidateStateTransitionError,
            RevisionBuildError,
        ) as exc:
            seq = len(repo.get_events(candidate_id)) + 1
            repo.append_event(
                EvidenceProcessingCandidateEvent(
                    candidate_id=candidate_id,
                    seq=seq,
                    from_status=EvidenceProcessingCandidateStatus.PROCESSING,
                    to_status=EvidenceProcessingCandidateStatus.RETRYABLE_FAILURE,
                    event_kind=ProcessingCandidateEventKind.RETRYABLE_ERROR,
                    actor=candidate.created_by,
                    reason=str(exc),
                    created_at=_utcnow(),
                )
            )
            raise BuildRetryableFailureError(str(exc)) from exc

    def _scan_and_build(
        self,
        session: Session,
        candidate,
    ) -> CompleteEvidenceProcessingRevision:
        base = EvidenceProcessingRevisionRepository(session).get(
            candidate.base_processing_revision_id
        )
        risk = EvidenceRiskScanService(self.session_factory)
        for entry in base.manifest:
            if entry.ocr_page_id is not None:
                risk.scan_page_in_session(
                    session,
                    entry.ocr_page_id,
                    rule_version=candidate.scanner_rule_version,
                )
        builder = EvidenceRevisionBuilder(artifact_store=self.artifact_store)
        if candidate.job_id is None:
            closure = builder.gather_closure(
                session,
                evidence_snapshot_id=candidate.evidence_snapshot_id,
                base_processing_revision_id=candidate.base_processing_revision_id,
                scanner_rule_version=candidate.scanner_rule_version,
                selected_locator_ids=candidate.selected_locator_ids,
            )
        else:
            manifest = candidate.attempt_manifest
            closure = builder.closure_from_manifest(
                session,
                base_processing_revision_id=candidate.base_processing_revision_id,
                metadata_revision_ids=manifest.metadata_revision_ids,
                risk_scan_ids=manifest.risk_scan_ids,
                risk_review_ids=manifest.risk_review_ids,
                correction_ids=manifest.correction_ids,
                locator_ids=manifest.locator_ids,
                referenced_document_revision_ids=(
                    manifest.referenced_document_revision_ids
                ),
                resolution_revision_ids=manifest.resolution_revision_ids,
            )
        builder.assert_blocking_resolved(session, closure)
        return builder.build(
            session,
            closure=closure,
            evidence_snapshot_id=candidate.evidence_snapshot_id,
            project_id=candidate.project_id,
            subject_id=candidate.subject_id,
            review_episode_id=candidate.review_episode_id,
            created_by=candidate.created_by,
            producer_candidate_id=candidate.candidate_id,
            candidate_input_sha256=candidate.candidate_input_sha256,
            # 持久任务严格消费排队时冻结的清单；其后合法新增的旁路记录不能
            # 使旧任务吸收新输入，也不能反向破坏已冻结尝试。
            require_current_heads=candidate.job_id is None,
        )
