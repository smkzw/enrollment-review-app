"""Slice 4.4 证据写命令应用服务（WP-44C 薄 API 边界）。

本服务是全部写命令的唯一编排点，拥有幂等键 + 乐观并发 + 诚实 409 上下文：

- 每个写命令都必须携带稳定幂等键；同键同归一化请求回放原结果（即使审核节点/
  链头修订号已前进），同键异请求返回 409 且不产生任何新历史；
- 新请求在写入前检查其所属可变链的预期修订号（审核节点 revision 或被提及资料
  链头 revision / 满足链头 revision）；
- 幂等记录、预期修订校验与领域写入在同一事务内原子提交（SQLite BEGIN IMMEDIATE）；
- 任何写侧 409 都携带结构化 ``submitted``、``current_record`` 与 ``field_diff``；
  待核对/门禁失败额外列出实际未解除/未通过的门禁；
- 不暴露 ORM 对象、枚举、绝对路径、非必要哈希或技术异常文本。

存储层异常只能在本服务边界翻译；API 错误信封映射器不识别存储实现类型。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.enums import (
    CorrectionChangeKind,
    EvidenceProcessingCandidateStatus,
    ReferencedDocumentResolutionStatus,
)
from app.domain.contracts.evidence_ingestion import SourceDocumentMetadataRevision
from app.domain.contracts.evidence_locator import (
    CompleteEvidenceProcessingRevision,
    CorrectionRecord,
    OCRRiskPageReview,
    OCRRiskReview,
    ProcessingCandidateAttemptManifest,
    ReferencedDocumentResolutionRevision,
    ReferencedDocumentRevision,
    validate_correction_source_anchor,
)
from app.domain.publication import canonical_hash
from app.evidence.artifacts import ArtifactStore
from app.evidence.risk import allows_risk_review, correction_covers_risk
from app.services.evidence_activation_service import (
    ActivationAlreadyActiveError,
    ActivationGateError,
    ActivationIdempotencyConflictError,
    ActivationRevisionConflictError,
    EvidenceActivationService,
    RollbackTargetError,
)
from app.services.evidence_app_errors import (
    AppActivationGateError,
    AppAlreadyCurrentVersionError,
    AppBuildConfigurationError,
    AppBuildFailedError,
    AppCandidateStateConflictError,
    AppEvidenceReviewIncompleteError,
    AppIdempotencyConflictError,
    AppInternalError,
    AppInvalidReferenceError,
    AppMetadataUnchangedError,
    AppNonCompleteRevisionError,
    AppReviewPendingError,
    AppRollbackTargetError,
    AppScopeMismatchError,
    AppStaleRevisionError,
    AppSubjectInUseError,
    EvidenceAppError,
    app_error_boundary,
)
from app.services.evidence_command_identity_store import EvidenceCommandIdentityStore
from app.services.evidence_correction_service import (
    CorrectionRangeError,
    EvidenceCorrectionService,
)
from app.services.evidence_referenced_document_service import (
    EvidenceReferencedDocumentService,
)
from app.services.evidence_revision_build_executor import (
    EVIDENCE_REVISION_BUILD_JOB_TYPE,
    EVIDENCE_REVISION_BUILD_STEP_ID,
)
from app.services.evidence_revision_builder import (
    EvidenceRevisionBuilder,
    MissingMetadataRevisionError,
    MissingRiskScanError,
    UnresolvedBlockingRiskError,
)
from app.services.evidence_revision_workflow import (
    EvidenceRevisionBuildRequest,
    EvidenceRevisionWorkflow,
)
from app.services.evidence_sidecar_preparation import EvidenceSidecarPreparationService
from app.services.evidence_risk_service import (
    EvidenceRiskScanService as _EvidenceRiskScanService,
)
from app.services.job_service import JobService, StepSpec
from app.storage.evidence_locator_models import (
    EvidenceProcessingCandidateRecord,
    ReferencedDocumentRevisionRecord,
)
from app.storage.evidence_locator_repositories import (
    CandidateStateTransitionError,
    CompleteEvidenceProcessingRevisionRepository,
    CorrectionRepository,
    EvidenceActivationEventRepository,
    EvidenceProcessingCandidateRepository,
    OCRRiskPageReviewRepository,
    OCRRiskReviewRepository,
    ReferencedDocumentRepository,
    RevisionClosureError,
)
from app.storage.evidence_repositories import (
    EvidenceSnapshotRepository,
    SourceDocumentMetadataRevisionRepository,
    SourceDocumentRepository,
)
from app.storage.idempotency import IdempotencyRepository
from app.storage.ocr_repositories import (
    EvidenceProcessingRevisionRepository,
    OcrPageRepository,
    PageArtifactRepository,
)
from app.storage.repositories import (
    EpisodeRepository,
    NotFoundError,
)

__all__ = ["EvidenceApiCommandService"]

#: 稳定应用错误别名：内部 raise 点沿用原名称，但类型继承自
#: ``evidence_app_errors.EvidenceAppError``（API 错误映射器只导入应用错误模块）。
StaleRevision409Error = AppStaleRevisionError
IdempotencyConflict409Error = AppIdempotencyConflictError
ReviewPending409Error = AppReviewPendingError
BuildFailed409Error = AppBuildFailedError
NonCompleteRevision409Error = AppNonCompleteRevisionError
ActivationGate409Error = AppActivationGateError
CommandConflictError = EvidenceAppError


# ---------------------------------------------------------------------------
# 命令结果
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommandResult:
    """写命令结果：``created`` False = 同幂等键回放原结果。"""

    created: bool


@dataclass(frozen=True)
class CorrectionCommandResult(CommandResult):
    correction: CorrectionRecord
    candidate_id: str
    job_id: str
    candidate_status: str


@dataclass(frozen=True)
class RiskReviewCommandResult(CommandResult):
    review: OCRRiskReview
    candidate_id: str
    job_id: str
    candidate_status: str


@dataclass(frozen=True)
class RiskPageReviewCommandResult(CommandResult):
    page_review: OCRRiskPageReview
    reviews: list[OCRRiskReview]
    candidate_id: str
    job_id: str
    candidate_status: str


@dataclass(frozen=True)
class BuildCommandResult(CommandResult):
    candidate_id: str
    job_id: str
    candidate_status: str
    complete_revision_id: str | None = None


@dataclass(frozen=True)
class ActivationCommandResult(CommandResult):
    event: Any  # EvidenceActivationEvent


@dataclass(frozen=True)
class ReferencedDocumentCommandResult(CommandResult):
    revision: ReferencedDocumentRevision


@dataclass(frozen=True)
class MetadataRevisionCommandResult(CommandResult):
    revision: SourceDocumentMetadataRevision


@dataclass(frozen=True)
class ResolutionCommandResult(CommandResult):
    resolution: ReferencedDocumentResolutionRevision


class EvidenceApiCommandService:
    """证据写命令应用服务：幂等 + 乐观并发 + 原子提交。"""

    def __init__(
        self,
        session_factory: sessionmaker,
        artifact_store: ArtifactStore,
    ) -> None:
        self.session_factory = session_factory
        self.artifact_store = artifact_store
        self.command_identities = EvidenceCommandIdentityStore(
            artifact_store.data_paths
        )

    # ------------------------------------------------------------------ 工具

    @staticmethod
    def _begin_write(session: Session) -> None:
        if session.get_bind().dialect.name == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))
        else:
            session.begin()

    def _request_hash(self, payload: dict[str, Any]) -> str:
        """保存规范化命令并返回其内容身份。"""
        digest = self.command_identities.put(payload)
        if digest != canonical_hash(payload):
            raise RuntimeError("命令规范化算法不一致")
        return digest

    def _idempotency_conflict(
        self,
        *,
        record,
        submitted: dict[str, Any],
        existing_result: dict[str, Any],
        detail: str,
        scope: str,
        idempotency_key: str,
    ) -> AppIdempotencyConflictError:
        first_command = self.command_identities.get(record.request_sha256)
        return AppIdempotencyConflictError(
            scope=scope,
            idempotency_key=idempotency_key,
            submitted=submitted,
            existing_result=existing_result,
            current_record=first_command,
            detail=detail,
        )

    def _replay_or_conflict(
        self,
        session: Session,
        *,
        scope: str,
        idempotency_key: str,
        submitted: dict[str, Any],
        request_sha256: str,
        result_loader,
    ) -> Any | None:
        """幂等解析：同键同哈希回放原结果；同键异哈希 409 且不产生新历史。"""
        record = IdempotencyRepository(session).get(scope, idempotency_key)
        if record is None:
            return None
        if record.request_sha256 != request_sha256:
            existing_result: Any = result_loader(record.result_id, safe=True)
            raise self._idempotency_conflict(
                record=record,
                scope=scope,
                idempotency_key=idempotency_key,
                submitted=submitted,
                existing_result=existing_result,
                detail="同一幂等键已绑定不同命令，拒绝复用。",
            )
        return result_loader(record.result_id, safe=False)

    @staticmethod
    def _check_episode_revision(
        session: Session,
        review_episode_id: str,
        expected_revision: int,
        submitted: dict[str, Any],
    ) -> None:
        """新请求的乐观并发：审核节点预期修订号不匹配 -> 409 保留提交值 + 差异。"""
        episode = EpisodeRepository(session).get(review_episode_id)
        if episode.revision == expected_revision:
            return
        raise StaleRevision409Error(
            entity_type="review_episode",
            entity_id=review_episode_id,
            expected_revision=expected_revision,
            current_revision=episode.revision,
            submitted=submitted,
            current_record={
                "review_episode_id": review_episode_id,
                "revision": episode.revision,
                "active_evidence_snapshot_id": episode.active_evidence_snapshot_id,
                "active_evidence_processing_revision_id": (
                    episode.active_evidence_processing_revision_id
                ),
            },
            field_diff={
                "revision": {
                    "current": episode.revision,
                    "submitted": expected_revision,
                }
            },
        )

    def _episode_for_ocr_page(self, session, ocr_page_id: str) -> str:
        ocr = OcrPageRepository(session).get(ocr_page_id)  # 不存在 -> 404
        artifact = PageArtifactRepository(session).get(ocr.page_artifact_id)
        from app.storage.evidence_repositories import SourceDocumentRepository

        doc = SourceDocumentRepository(session).get(artifact.source_document_version_id)
        return doc.review_episode_id

    @app_error_boundary
    def revise_source_document_metadata(
        self,
        *,
        source_document_version_id: str,
        document_type: str,
        source_party: str,
        reason: str,
        expected_metadata_revision: int,
        idempotency_key: str,
        actor: str,
    ) -> MetadataRevisionCommandResult:
        """核对资料类型/来源方：同键回放先于链头校验，新写入只追加。"""
        document_type = document_type.strip()
        source_party = source_party.strip()
        reason = reason.strip()
        submitted = {
            "source_document_version_id": source_document_version_id,
            "document_type": document_type,
            "source_party": source_party,
            "reason": reason,
            "expected_metadata_revision": expected_metadata_revision,
            "actor": actor,
        }
        with self.session_factory() as session:
            self._begin_write(session)
            # 读取资料本身会重验 project/subject/episode 作用域。
            SourceDocumentRepository(session).get(source_document_version_id)
            scope = f"source_document_metadata:{source_document_version_id}"
            request_sha256 = self._request_hash(submitted)
            repository = SourceDocumentMetadataRevisionRepository(session)

            def _loader(result_id: str, *, safe: bool) -> Any:
                revision = repository.get(result_id)
                if safe:
                    return {
                        "metadata_revision_id": revision.metadata_revision_id,
                        "revision": revision.revision,
                        "document_type": revision.document_type,
                        "source_party": revision.source_party,
                    }
                return revision

            revision = self._replay_or_conflict(
                session,
                scope=scope,
                idempotency_key=idempotency_key,
                submitted=submitted,
                request_sha256=request_sha256,
                result_loader=_loader,
            )
            if revision is not None:
                session.rollback()
                return MetadataRevisionCommandResult(created=False, revision=revision)

            head = repository.head(source_document_version_id)
            current_revision = head.revision if head is not None else None
            if head is None or current_revision != expected_metadata_revision:
                raise StaleRevision409Error(
                    entity_type="source_document_metadata",
                    entity_id=source_document_version_id,
                    expected_revision=expected_metadata_revision,
                    current_revision=current_revision,
                    submitted=submitted,
                    current_record={
                        "source_document_version_id": source_document_version_id,
                        "revision": current_revision,
                        "document_type": head.document_type if head else None,
                        "source_party": head.source_party if head else None,
                        "is_auto_suggestion": head.is_auto_suggestion if head else None,
                    },
                    field_diff={
                        "revision": {
                            "current": current_revision,
                            "submitted": expected_metadata_revision,
                        }
                    },
                )
            if (
                not head.is_auto_suggestion
                and head.document_type == document_type
                and head.source_party == source_party
            ):
                raise AppMetadataUnchangedError("资料类型和来源方与当前记录一致。")

            revision_id = (
                "metadata-"
                + sha256(f"{scope}:{idempotency_key}".encode()).hexdigest()[:32]
            )
            revision = repository.append(
                SourceDocumentMetadataRevision(
                    metadata_revision_id=revision_id,
                    source_document_version_id=source_document_version_id,
                    revision=head.revision + 1,
                    document_type=document_type,
                    source_party=source_party,
                    reason=reason,
                    is_auto_suggestion=False,
                    supersedes_metadata_revision_id=head.metadata_revision_id,
                    created_at=datetime.now(UTC),
                    created_by=actor,
                )
            )
            IdempotencyRepository(session).resolve(
                scope=scope,
                idempotency_key=idempotency_key,
                submitted_hash=request_sha256,
                result_type="source_document_metadata_revision",
                result_id=revision.metadata_revision_id,
            )
            session.commit()
            return MetadataRevisionCommandResult(created=True, revision=revision)

    def _freeze_attempt_manifest(
        self,
        session: Session,
        *,
        evidence_snapshot_id: str,
        base_processing_revision_id: str,
        scanner_rule_version: str,
        selected_locator_ids: list[str],
        trigger_sidecar_id: str | None,
    ) -> ProcessingCandidateAttemptManifest:
        """在命令事务内冻结构建尝试，后台不得重新选择“最新”旁路记录。"""
        EvidenceSidecarPreparationService(
            self.session_factory, self.artifact_store
        ).prepare_in_session(
            session,
            base_processing_revision_id,
            scanner_rule_version=scanner_rule_version,
        )
        closure = EvidenceRevisionBuilder(
            artifact_store=self.artifact_store
        ).gather_closure(
            session,
            evidence_snapshot_id=evidence_snapshot_id,
            base_processing_revision_id=base_processing_revision_id,
            scanner_rule_version=scanner_rule_version,
            selected_locator_ids=selected_locator_ids,
        )
        return ProcessingCandidateAttemptManifest(
            metadata_revision_ids=sorted(closure.metadata_revision_ids),
            risk_scan_ids=sorted(closure.risk_scan_ids),
            risk_review_ids=sorted(closure.risk_review_ids),
            correction_ids=sorted(closure.correction_ids),
            locator_ids=sorted(closure.locator_ids),
            referenced_document_revision_ids=sorted(
                closure.referenced_document_revision_ids
            ),
            resolution_revision_ids=sorted(closure.resolution_revision_ids),
            trigger_sidecar_id=trigger_sidecar_id,
        )

    def _enqueue_build_in_session(
        self,
        session: Session,
        *,
        snapshot,
        base_processing_revision_id: str,
        expected_revision: int,
        idempotency_key: str,
        actor: str,
        target_candidate_id: str | None = None,
        expected_candidate_event_seq: int | None = None,
        scanner_rule_version: str,
        selected_locator_ids: list[str],
        trigger_sidecar_id: str | None,
    ):
        """原子创建 staged 候选与持久任务，并冻结完整尝试清单。"""
        from uuid import uuid4

        candidate_id = f"cand-{uuid4().hex}"
        manifest = self._freeze_attempt_manifest(
            session,
            evidence_snapshot_id=snapshot.evidence_snapshot_id,
            base_processing_revision_id=base_processing_revision_id,
            scanner_rule_version=scanner_rule_version,
            selected_locator_ids=selected_locator_ids,
            trigger_sidecar_id=trigger_sidecar_id,
        )
        job = JobService(self.session_factory).create_job_in_session(
            session,
            idempotency_key=f"evidence-revision-job:{idempotency_key}",
            job_type=EVIDENCE_REVISION_BUILD_JOB_TYPE,
            payload={
                "candidate_id": candidate_id,
                "review_episode_id": snapshot.review_episode_id,
            },
            steps=[
                StepSpec(
                    step_id=EVIDENCE_REVISION_BUILD_STEP_ID,
                    name="生成核对后的资料版本",
                    max_attempts=3,
                    retryable=True,
                )
            ],
        )
        request = EvidenceRevisionBuildRequest(
            evidence_snapshot_id=snapshot.evidence_snapshot_id,
            base_processing_revision_id=base_processing_revision_id,
            project_id=snapshot.project_id,
            subject_id=snapshot.subject_id,
            review_episode_id=snapshot.review_episode_id,
            expected_revision=expected_revision,
            idempotency_key=f"evidence-revision:{idempotency_key}",
            created_by=actor,
            job_id=job.job_id,
            scanner_rule_version=scanner_rule_version,
            selected_locator_ids=manifest.locator_ids,
            attempt_manifest=manifest,
        )
        candidate = EvidenceRevisionWorkflow(
            self.session_factory, self.artifact_store
        ).start_in_session(session, request, candidate_id=candidate_id)
        return candidate, job

    def _candidate_by_key(self, session: Session, candidate_key: str):
        row = session.execute(
            select(EvidenceProcessingCandidateRecord).where(
                EvidenceProcessingCandidateRecord.idempotency_key == candidate_key
            )
        ).scalars().first()
        if row is None:
            return None
        return EvidenceProcessingCandidateRepository(
            session, self.artifact_store
        ).get(row.candidate_id)

    def _continue_or_enqueue_after_sidecar(
        self,
        session: Session,
        *,
        episode_id: str,
        base_processing_revision_id: str,
        expected_revision: int,
        command_key: str,
        actor: str,
        trigger_sidecar_id: str,
        target_candidate_id: str | None,
        expected_candidate_event_seq: int | None,
    ):
        from app.evidence.risk import OCR_RISK_RULE_VERSION

        episode = EpisodeRepository(session).get(episode_id)
        workflow = EvidenceRevisionWorkflow(self.session_factory, self.artifact_store)
        if target_candidate_id is not None:
            repo = EvidenceProcessingCandidateRepository(session, self.artifact_store)
            candidate = repo.get(target_candidate_id)
            events = repo.get_events(target_candidate_id)
            if expected_candidate_event_seq is None or len(events) != expected_candidate_event_seq:
                raise StaleRevision409Error(
                    entity_type="evidence_processing_candidate",
                    entity_id=target_candidate_id,
                    expected_revision=expected_candidate_event_seq or 0,
                    current_revision=len(events),
                    submitted={"trigger_sidecar_id": trigger_sidecar_id},
                    current_record={
                        "candidate_id": target_candidate_id,
                        "status": candidate.status.value,
                        "event_seq": len(events),
                    },
                    field_diff={
                        "event_seq": {
                            "current": len(events),
                            "submitted": expected_candidate_event_seq,
                        }
                    },
                )
            if (
                candidate.review_episode_id != episode_id
                or candidate.base_processing_revision_id
                != base_processing_revision_id
            ):
                raise AppScopeMismatchError("目标资料版本与本次核对范围不一致")
            manifest = self._freeze_attempt_manifest(
                session,
                evidence_snapshot_id=candidate.evidence_snapshot_id,
                base_processing_revision_id=base_processing_revision_id,
                scanner_rule_version=candidate.scanner_rule_version,
                selected_locator_ids=candidate.attempt_manifest.locator_ids,
                trigger_sidecar_id=trigger_sidecar_id,
            )
            # 逐项核对只保存本项。仍有其他阻断风险或被提及资料待处理时，
            # 候选继续停留在“需要关注”，避免每保存一项就把整套资料重跑一次。
            if self._pending_referenced_document_actions(session, episode_id):
                return candidate, candidate.job_id
            builder = EvidenceRevisionBuilder(artifact_store=self.artifact_store)
            closure = builder.closure_from_manifest(
                session,
                base_processing_revision_id=base_processing_revision_id,
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
            try:
                builder.assert_blocking_resolved(session, closure)
            except UnresolvedBlockingRiskError:
                return candidate, candidate.job_id
            resumed = workflow.resume_after_attention_in_session(
                session,
                candidate_id=target_candidate_id,
                attempt_manifest=manifest,
                actor=actor,
                reason="识别核对已补充，继续生成资料版本",
            )
            if resumed.job_id is None:
                raise RuntimeError("等待核对的资料版本缺少持久任务")
            JobService(self.session_factory).resume_waiting_step_in_session(
                session,
                job_id=resumed.job_id,
                step_id=EVIDENCE_REVISION_BUILD_STEP_ID,
                checkpoint_payload={
                    "candidate_id": resumed.candidate_id,
                    "trigger_sidecar_id": trigger_sidecar_id,
                },
            )
            return resumed, resumed.job_id

        if (
            episode.active_evidence_processing_revision_id is not None
            and episode.active_evidence_processing_revision_id
            != base_processing_revision_id
        ):
            raise AppScopeMismatchError(
                "当前核对不是从现行资料版本发起，请刷新后重新操作"
            )
        open_row = session.execute(
            select(EvidenceProcessingCandidateRecord)
            .where(EvidenceProcessingCandidateRecord.review_episode_id == episode_id)
            .where(
                EvidenceProcessingCandidateRecord.base_processing_revision_id
                == base_processing_revision_id
            )
            .where(
                EvidenceProcessingCandidateRecord.status.in_(
                    ["staged", "processing", "needs_attention", "retryable_failure"]
                )
            )
        ).scalars().first()
        if open_row is not None:
            raise AppCandidateStateConflictError(
                "当前资料版本仍在生成或等待核对，请先完成该版本后再保存新的核对。",
                submitted={"trigger_sidecar_id": trigger_sidecar_id},
                current_record={
                    "candidate_id": open_row.candidate_id,
                    "status": open_row.status,
                },
                field_diff={
                    "candidate_id": {
                        "current": open_row.candidate_id,
                        "submitted": None,
                    },
                },
            )
        if episode.active_evidence_snapshot_id is not None:
            snapshot_id = episode.active_evidence_snapshot_id
        else:
            snapshot_id = EvidenceProcessingRevisionRepository(session).get(
                base_processing_revision_id
            ).evidence_snapshot_id
        snapshot = EvidenceSnapshotRepository(session).get(snapshot_id)
        candidate, job = self._enqueue_build_in_session(
            session,
            snapshot=snapshot,
            base_processing_revision_id=base_processing_revision_id,
            expected_revision=expected_revision,
            idempotency_key=command_key,
            actor=actor,
            scanner_rule_version=OCR_RISK_RULE_VERSION,
            selected_locator_ids=[],
            trigger_sidecar_id=trigger_sidecar_id,
        )
        return candidate, job.job_id

    @staticmethod
    def _require_subject_episode(session, subject_id: str, review_episode_id: str):
        episode = EpisodeRepository(session).get(review_episode_id)
        if episode.subject_id != subject_id:
            raise NotFoundError(
                f"审核节点 {review_episode_id} 不属于受试者 {subject_id}"
            )
        return episode

    @staticmethod
    def _current_pointer(session, review_episode_id: str):
        episode = EpisodeRepository(session).get(review_episode_id)
        return (
            episode.active_evidence_snapshot_id,
            episode.active_evidence_processing_revision_id,
        )

    def _load_complete(
        self, session, revision_id: str
    ) -> CompleteEvidenceProcessingRevision:
        return CompleteEvidenceProcessingRevisionRepository(
            session, self.artifact_store
        ).get(revision_id)

    # ------------------------------------------------------------------ 受试者

    @app_error_boundary
    def create_subject(self, subject: Any) -> Any:
        """创建受试者并原子建立其全部审核节点（P4-R01/P4-R04）。

        对正式已发布项目，按该项目当前发布的 RuleSet revision 的流程节点
        （``review_required=True``）逐一实例化 ``ReviewEpisode``：同一审核阶段下
        的多个访视实例各自独立节点，互不合并。任一节点写入失败则整个事务回滚，
        不产生半成品受试者。自动建立的节点没有 legacy 证据快照
        （``evidence_snapshot_id=None``），不伪造占位快照。
        """
        from uuid import uuid4

        from app.domain.contracts.review import ReviewEpisode
        from app.storage.repositories import (
            EpisodeRepository,
            SubjectRepository,
            get_project_row,
            list_workflow_stages_for_rule_set,
        )

        with self.session_factory() as session:
            project_row = get_project_row(session, subject.project_id)
            if project_row is None:
                raise AppInvalidReferenceError(
                    detail=f"项目 {subject.project_id} 不存在，无法新增受试者。"
                )
            project, rule_set_revision = project_row
            saved = SubjectRepository(session).save(subject)
            stages = [
                stage
                for stage in list_workflow_stages_for_rule_set(
                    session, project.rule_set_id, rule_set_revision
                )
                if stage.review_required
            ]
            for stage in stages:
                episode = ReviewEpisode(
                    review_episode_id=uuid4().hex,
                    subject_id=saved.subject_id,
                    project_id=project.project_id,
                    rule_set_id=project.rule_set_id,
                    rule_set_revision=rule_set_revision,
                    study_phase=project.study_phase,
                    stage=stage.stage,
                    protocol_version_id=project.protocol_version.protocol_version_id,
                    workflow_stage_id=stage.workflow_stage_id,
                    evidence_snapshot_id=None,
                    anchor_dates={},
                )
                EpisodeRepository(session).save(episode)
            session.commit()
            return saved

    @app_error_boundary
    def delete_subject(self, project_id: str, subject_id: str) -> Any:
        """删除受试者及其自动建立的空审核节点（P4-R04 边界）。

        只有在该受试者的全部审核节点均为「空节点」（无 legacy 证据快照、无活动
        版本指针、无任何 V2 快照/候选/处理修订/被提及资料/期望/运行等依赖），
        且受试者本身未被任何临床/审核内容引用时，才在同一事务内删除节点与受试者。
        任一节点承载不可变证据或审核内容即 409 拒绝；跨项目引用按不存在处理（404）。
        不可变证据一律不删除。
        """
        from app.api.v2.vocabulary import review_stage_label
        from app.storage.repositories import (
            EpisodeRepository,
            SubjectRepository,
            episode_dependent_counts,
            subject_dependent_counts,
        )

        def _stage_label(episode: Any) -> str:
            stage = episode.stage.value if hasattr(episode.stage, "value") else episode.stage
            return review_stage_label(str(stage))

        with self.session_factory() as session:
            subject = SubjectRepository(session).get(subject_id)  # 不存在 -> 404
            if subject.project_id != project_id:
                raise NotFoundError(f"Subject {subject_id} 不属于项目 {project_id}")
            episodes = EpisodeRepository(session).list_by_subject(
                subject_id, project_id=project_id
            )
            for episode in episodes:
                if episode.evidence_snapshot_id is not None:
                    raise AppSubjectInUseError(
                        detail=(
                            f"受试者 {subject.subject_code} 的「{_stage_label(episode)}」"
                            "审核节点已有历史证据快照，删除会破坏不可变证据。"
                        )
                    )
                if (
                    episode.active_evidence_snapshot_id is not None
                    or episode.active_evidence_processing_revision_id is not None
                ):
                    raise AppSubjectInUseError(
                        detail=(
                            f"受试者 {subject.subject_code} 的「{_stage_label(episode)}」"
                            "审核节点已有活动资料版本，删除会破坏不可变证据。"
                        )
                    )
                dependents = episode_dependent_counts(
                    session, episode.review_episode_id
                )
                if dependents:
                    raise AppSubjectInUseError(
                        detail=(
                            f"受试者 {subject.subject_code} 的「{_stage_label(episode)}」"
                            "审核节点已承载资料或审核记录"
                            f"（{len(dependents)} 类），删除会破坏历史。"
                        )
                    )
            # 受试者级依赖：除将删除的审核节点外，任何直接引用受试者的资料/审核内容都阻止删除。
            subject_dependents = subject_dependent_counts(session, subject_id)
            if subject_dependents:
                raise AppSubjectInUseError(
                    detail=(
                        f"受试者 {subject.subject_code} 已关联 "
                        f"{len(subject_dependents)} 类既有资料或审核记录，删除会破坏历史。"
                    )
                )
            for episode in episodes:
                EpisodeRepository(session).delete(episode.review_episode_id)
            deleted = SubjectRepository(session).delete(subject_id, project_id)
            session.commit()
            return deleted

    # ------------------------------------------------------------------ 校对

    @app_error_boundary
    def create_correction(
        self,
        *,
        ocr_page_id: str,
        raw_text_sha256: str,
        text_start: int,
        text_end: int,
        original_text: str,
        corrected_text: str,
        change_kind: CorrectionChangeKind,
        reason: str,
        base_processing_revision_id: str,
        expected_revision: int,
        idempotency_key: str,
        actor: str,
        supersedes_correction_id: str | None = None,
        confirmation_actor: str | None = None,
        confirmation_at=None,
        affected_scope: list[str] | None = None,
        target_candidate_id: str | None = None,
        expected_candidate_event_seq: int | None = None,
    ) -> CorrectionCommandResult:
        with self.session_factory() as session:
            self._begin_write(session)
            ocr = OcrPageRepository(session).get(ocr_page_id)
            if ocr.raw_text_sha256 != raw_text_sha256:
                raise CorrectionRangeError("提交的原始识别哈希与当前页不一致，拒绝保存")
            try:
                validate_correction_source_anchor(
                    ocr.raw_text,
                    text_start=text_start,
                    text_end=text_end,
                    original_text=original_text,
                )
            except ValueError as error:
                raise CorrectionRangeError(str(error)) from error

            episode_id = self._episode_for_ocr_page(session, ocr_page_id)
            scope = f"correction:{episode_id}"
            submitted = {
                "ocr_page_id": ocr_page_id,
                "raw_text_sha256": raw_text_sha256,
                "text_start": text_start,
                "text_end": text_end,
                "original_text": original_text,
                "corrected_text": corrected_text,
                "change_kind": (
                    change_kind.value if hasattr(change_kind, "value") else change_kind
                ),
                "reason": reason,
                "base_processing_revision_id": base_processing_revision_id,
                "expected_revision": expected_revision,
                "supersedes_correction_id": supersedes_correction_id,
                "confirmation": (
                    {
                        "actor": confirmation_actor,
                        "at": (
                            confirmation_at.isoformat()
                            if confirmation_at is not None
                            else None
                        ),
                    }
                    if confirmation_actor is not None
                    else None
                ),
                "actor": actor,
                "target_candidate_id": target_candidate_id,
                "expected_candidate_event_seq": expected_candidate_event_seq,
            }
            request_sha256 = self._request_hash(submitted)

            def _loader(result_id: str, *, safe: bool) -> Any:
                correction = CorrectionRepository(session).get(result_id)
                if safe:
                    return {
                        "correction_id": correction.correction_id,
                        "text_start": correction.text_start,
                        "text_end": correction.text_end,
                        "corrected_text": correction.corrected_text,
                    }
                return correction

            correction = self._replay_or_conflict(
                session,
                scope=scope,
                idempotency_key=idempotency_key,
                submitted=submitted,
                request_sha256=request_sha256,
                result_loader=_loader,
            )
            if correction is not None:
                candidate = (
                    EvidenceProcessingCandidateRepository(
                        session, self.artifact_store
                    ).get(
                        target_candidate_id
                    )
                    if target_candidate_id is not None
                    else self._candidate_by_key(
                        session,
                        f"evidence-revision:{episode_id}:correction:{idempotency_key}",
                    )
                )
                if candidate is None or candidate.job_id is None:
                    raise RuntimeError("校对记录缺少对应的持久资料版本任务")
                session.rollback()
                return CorrectionCommandResult(
                    created=False,
                    correction=correction,
                    candidate_id=candidate.candidate_id,
                    job_id=candidate.job_id,
                    candidate_status=candidate.status.value,
                )

            self._check_episode_revision(
                session, episode_id, expected_revision, submitted
            )
            correction_id = (
                "corr-"
                + sha256(f"{episode_id}:{idempotency_key}".encode()).hexdigest()[:32]
            )
            correction = EvidenceCorrectionService(
                self.session_factory, artifact_store=self.artifact_store
            ).create_correction_in_session(
                session,
                ocr_page_id=ocr_page_id,
                text_start=text_start,
                text_end=text_end,
                original_text=original_text,
                corrected_text=corrected_text,
                change_kind=change_kind,
                reason=reason,
                actor=actor,
                base_processing_revision_id=base_processing_revision_id,
                supersedes_correction_id=supersedes_correction_id,
                confirmation_actor=confirmation_actor,
                confirmation_at=confirmation_at,
                correction_id=correction_id,
                affected_scope=affected_scope,
            )
            candidate, job_id = self._continue_or_enqueue_after_sidecar(
                session,
                episode_id=episode_id,
                base_processing_revision_id=base_processing_revision_id,
                expected_revision=expected_revision,
                command_key=f"{episode_id}:correction:{idempotency_key}",
                actor=actor,
                trigger_sidecar_id=correction.correction_id,
                target_candidate_id=target_candidate_id,
                expected_candidate_event_seq=expected_candidate_event_seq,
            )
            IdempotencyRepository(session).resolve(
                scope=scope,
                idempotency_key=idempotency_key,
                submitted_hash=request_sha256,
                result_type="correction",
                result_id=correction.correction_id,
            )
            session.commit()
            return CorrectionCommandResult(
                created=True,
                correction=correction,
                candidate_id=candidate.candidate_id,
                job_id=job_id,
                candidate_status=candidate.status.value,
            )

    # ------------------------------------------------------------------ 风险核对

    @app_error_boundary
    def create_risk_review(
        self,
        *,
        ocr_page_id: str,
        risk_flag_id: str,
        decision: Any,
        reason: str,
        base_processing_revision_id: str,
        expected_revision: int,
        idempotency_key: str,
        actor: str,
        target_candidate_id: str | None = None,
        expected_candidate_event_seq: int | None = None,
    ) -> RiskReviewCommandResult:
        with self.session_factory() as session:
            self._begin_write(session)
            episode_id = self._episode_for_ocr_page(session, ocr_page_id)
            scope = f"risk_review:{episode_id}"
            submitted = {
                "ocr_page_id": ocr_page_id,
                "risk_flag_id": risk_flag_id,
                "decision": (
                    decision.value if hasattr(decision, "value") else decision
                ),
                "reason": reason,
                "base_processing_revision_id": base_processing_revision_id,
                "expected_revision": expected_revision,
                "actor": actor,
                "target_candidate_id": target_candidate_id,
                "expected_candidate_event_seq": expected_candidate_event_seq,
            }
            request_sha256 = self._request_hash(submitted)

            def _loader(result_id: str, *, safe: bool) -> Any:
                review = OCRRiskReviewRepository(session).get(result_id)
                if safe:
                    return {
                        "review_id": review.review_id,
                        "risk_flag_id": review.risk_flag_id,
                        "decision": (
                            review.decision.value
                            if hasattr(review.decision, "value")
                            else review.decision
                        ),
                    }
                return review

            review = self._replay_or_conflict(
                session,
                scope=scope,
                idempotency_key=idempotency_key,
                submitted=submitted,
                request_sha256=request_sha256,
                result_loader=_loader,
            )
            if review is not None:
                candidate = (
                    EvidenceProcessingCandidateRepository(
                        session, self.artifact_store
                    ).get(
                        target_candidate_id
                    )
                    if target_candidate_id is not None
                    else self._candidate_by_key(
                        session,
                        f"evidence-revision:{episode_id}:risk:{idempotency_key}",
                    )
                )
                if candidate is None or candidate.job_id is None:
                    raise RuntimeError("风险核对缺少对应的持久资料版本任务")
                session.rollback()
                return RiskReviewCommandResult(
                    created=False,
                    review=review,
                    candidate_id=candidate.candidate_id,
                    job_id=candidate.job_id,
                    candidate_status=candidate.status.value,
                )

            self._check_episode_revision(
                session, episode_id, expected_revision, submitted
            )
            review_id = (
                "rv-"
                + sha256(f"{episode_id}:{idempotency_key}".encode()).hexdigest()[:32]
            )
            review = _EvidenceRiskScanService(
                self.session_factory
            ).create_review_in_session(
                session,
                review_id=review_id,
                risk_flag_id=risk_flag_id,
                decision=decision,
                reason=reason,
                actor=actor,
                base_processing_revision_id=base_processing_revision_id,
                expected_revision=expected_revision,
            )
            candidate, job_id = self._continue_or_enqueue_after_sidecar(
                session,
                episode_id=episode_id,
                base_processing_revision_id=base_processing_revision_id,
                expected_revision=expected_revision,
                command_key=f"{episode_id}:risk:{idempotency_key}",
                actor=actor,
                trigger_sidecar_id=review.review_id,
                target_candidate_id=target_candidate_id,
                expected_candidate_event_seq=expected_candidate_event_seq,
            )
            IdempotencyRepository(session).resolve(
                scope=scope,
                idempotency_key=idempotency_key,
                submitted_hash=request_sha256,
                result_type="risk_review",
                result_id=review.review_id,
            )
            session.commit()
            return RiskReviewCommandResult(
                created=True,
                review=review,
                candidate_id=candidate.candidate_id,
                job_id=job_id,
                candidate_status=candidate.status.value,
            )

    @app_error_boundary
    def create_page_risk_review(
        self,
        *,
        ocr_page_id: str,
        scan_id: str,
        decision: Any,
        reason: str,
        base_processing_revision_id: str,
        expected_revision: int,
        idempotency_key: str,
        actor: str,
        target_candidate_id: str | None = None,
        expected_candidate_event_seq: int | None = None,
    ) -> RiskPageReviewCommandResult:
        """对页上全部待核对风险做一次原子核对；逐条不可变记录同事务物化。

        与逐条核对同一幂等/并发合同：同键同请求回放页级核对及其逐条记录，同键异
        请求 409 且不产生新历史；新请求检查预期修订号与候选事件序号。
        """
        with self.session_factory() as session:
            self._begin_write(session)
            self._episode_for_ocr_page(session, ocr_page_id)  # 404 校验页存在
            episode_id = self._episode_for_ocr_page(session, ocr_page_id)
            scope = f"risk_page_review:{episode_id}"
            submitted = {
                "ocr_page_id": ocr_page_id,
                "scan_id": scan_id,
                "decision": (
                    decision.value if hasattr(decision, "value") else decision
                ),
                "reason": reason,
                "base_processing_revision_id": base_processing_revision_id,
                "expected_revision": expected_revision,
                "actor": actor,
                "target_candidate_id": target_candidate_id,
                "expected_candidate_event_seq": expected_candidate_event_seq,
            }
            request_sha256 = self._request_hash(submitted)

            def _loader(result_id: str, *, safe: bool) -> Any:
                page_review = OCRRiskPageReviewRepository(session).get(result_id)
                if safe:
                    return {
                        "page_review_id": page_review.page_review_id,
                        "ocr_page_id": page_review.ocr_page_id,
                        "created_review_ids": list(page_review.created_review_ids),
                    }
                return page_review

            page_review = self._replay_or_conflict(
                session,
                scope=scope,
                idempotency_key=idempotency_key,
                submitted=submitted,
                request_sha256=request_sha256,
                result_loader=_loader,
            )
            if page_review is not None:
                reviews = [
                    OCRRiskReviewRepository(session).get(rid)
                    for rid in page_review.created_review_ids
                ]
                candidate = (
                    EvidenceProcessingCandidateRepository(
                        session, self.artifact_store
                    ).get(target_candidate_id)
                    if target_candidate_id is not None
                    else self._candidate_by_key(
                        session,
                        f"evidence-revision:{episode_id}:risk-page:{idempotency_key}",
                    )
                )
                if candidate is None or candidate.job_id is None:
                    raise RuntimeError("页级风险核对缺少对应的持久资料版本任务")
                session.rollback()
                return RiskPageReviewCommandResult(
                    created=False,
                    page_review=page_review,
                    reviews=reviews,
                    candidate_id=candidate.candidate_id,
                    job_id=candidate.job_id,
                    candidate_status=candidate.status.value,
                )

            self._check_episode_revision(
                session, episode_id, expected_revision, submitted
            )
            page_review_id = (
                "prv-"
                + sha256(f"{episode_id}:{idempotency_key}".encode()).hexdigest()[:32]
            )
            page_review = _EvidenceRiskScanService(
                self.session_factory
            ).create_page_review_in_session(
                session,
                page_review_id=page_review_id,
                ocr_page_id=ocr_page_id,
                scan_id=scan_id,
                decision=decision,
                reason=reason,
                actor=actor,
                base_processing_revision_id=base_processing_revision_id,
                expected_revision=expected_revision,
            )
            reviews = [
                OCRRiskReviewRepository(session).get(rid)
                for rid in page_review.created_review_ids
            ]
            candidate, job_id = self._continue_or_enqueue_after_sidecar(
                session,
                episode_id=episode_id,
                base_processing_revision_id=base_processing_revision_id,
                expected_revision=expected_revision,
                command_key=f"{episode_id}:risk-page:{idempotency_key}",
                actor=actor,
                trigger_sidecar_id=page_review.page_review_id,
                target_candidate_id=target_candidate_id,
                expected_candidate_event_seq=expected_candidate_event_seq,
            )
            IdempotencyRepository(session).resolve(
                scope=scope,
                idempotency_key=idempotency_key,
                submitted_hash=request_sha256,
                result_type="risk_page_review",
                result_id=page_review.page_review_id,
            )
            session.commit()
            return RiskPageReviewCommandResult(
                created=True,
                page_review=page_review,
                reviews=reviews,
                candidate_id=candidate.candidate_id,
                job_id=job_id,
                candidate_status=candidate.status.value,
            )

    # ------------------------------------------------------------------ 构建

    @app_error_boundary
    def build_revision(
        self,
        *,
        evidence_snapshot_id: str,
        base_processing_revision_id: str,
        expected_revision: int,
        idempotency_key: str,
        actor: str,
        scanner_rule_version: str | None = None,
        selected_locator_ids: list[str] | None = None,
    ) -> BuildCommandResult:
        from app.evidence.risk import OCR_RISK_RULE_VERSION
        resolved_scanner_rule_version = scanner_rule_version or OCR_RISK_RULE_VERSION
        if resolved_scanner_rule_version != OCR_RISK_RULE_VERSION:
            raise AppBuildConfigurationError(
                "页面提交的资料处理方式与当前服务不一致，本次未创建处理记录。"
            )
        with self.session_factory() as session:
            self._begin_write(session)
            snapshot = EvidenceSnapshotRepository(session).get(evidence_snapshot_id)
            episode_id = snapshot.review_episode_id
            scope = f"build:{episode_id}"
            submitted = {
                "evidence_snapshot_id": evidence_snapshot_id,
                "base_processing_revision_id": base_processing_revision_id,
                "expected_revision": expected_revision,
                "scanner_rule_version": resolved_scanner_rule_version,
                "selected_locator_ids": sorted(selected_locator_ids or []),
                "actor": actor,
            }
            request_sha256 = self._request_hash(submitted)
            # 幂等主张按完整命令身份比较（scope/快照/base/扫描版本/定位/actor/
            # 预期修订号）：同键异命令 409 且不产生新历史；同键同命令回放。
            replay = self._build_replay_or_conflict(
                session,
                scope=scope,
                idempotency_key=idempotency_key,
                request_sha256=request_sha256,
                submitted=submitted,
            )
            if isinstance(replay, BuildCommandResult):
                session.rollback()
                return replay
            self._check_episode_revision(
                session, episode_id, expected_revision, submitted
            )
            pending_referenced = self._pending_referenced_document_actions(
                session, episode_id
            )
            if pending_referenced:
                pending_summary = "；".join(
                    f"{item['description']}：{item['action']}"
                    for item in pending_referenced
                )
                raise AppEvidenceReviewIncompleteError(
                    pending_items=pending_referenced,
                    submitted=submitted,
                    detail=(
                        "以下被提及资料尚未完成核对："
                        f"{pending_summary}系统未建立资料版本生成任务。"
                    ),
                )
            candidate, job = self._enqueue_build_in_session(
                session,
                snapshot=snapshot,
                base_processing_revision_id=base_processing_revision_id,
                expected_revision=expected_revision,
                idempotency_key=f"{episode_id}:{idempotency_key}",
                actor=actor,
                scanner_rule_version=submitted["scanner_rule_version"],
                selected_locator_ids=submitted["selected_locator_ids"],
                trigger_sidecar_id=None,
            )
            IdempotencyRepository(session).resolve(
                scope=scope,
                idempotency_key=idempotency_key,
                submitted_hash=request_sha256,
                result_type="processing_candidate",
                result_id=candidate.candidate_id,
            )
            session.commit()
            return BuildCommandResult(
                created=True,
                candidate_id=candidate.candidate_id,
                job_id=job.job_id,
                candidate_status=candidate.status.value,
            )

    @staticmethod
    def _pending_referenced_document_actions(
        session: Session, review_episode_id: str
    ) -> list[dict[str, Any]]:
        """列出会阻断完整资料版本的被提及资料待办，不创建失败候选。"""
        rows = session.execute(
            select(ReferencedDocumentRevisionRecord).where(
                ReferencedDocumentRevisionRecord.review_episode_id
                == review_episode_id
            )
        ).scalars().all()
        superseded = {
            row.supersedes_revision_id
            for row in rows
            if row.supersedes_revision_id is not None
        }
        pending: list[dict[str, Any]] = []
        for row in sorted(
            (item for item in rows if item.revision_id not in superseded),
            key=lambda item: (item.referenced_document_id, item.revision),
        ):
            head = EvidenceReferencedDocumentService.revision_head(
                session, row.referenced_document_id
            )
            if head is None:
                continue
            status = head.status.value if hasattr(head.status, "value") else head.status
            if status == "proposed":
                pending.append(
                    {
                        "referenced_document_id": head.referenced_document_id,
                        "description": head.description,
                        "action": "请确认原文确有提及，或解除这项候选。",
                    }
                )
                continue
            if status == "dismissed":
                continue
            resolution = EvidenceReferencedDocumentService.resolution_head(
                session, head.referenced_document_id
            )
            if resolution is None:
                pending.append(
                    {
                        "referenced_document_id": head.referenced_document_id,
                        "description": head.description,
                        "action": "请关联已提供资料，或明确标记为尚未提供。",
                    }
                )
        return pending

    def _build_replay_or_conflict(
        self,
        session: Session,
        *,
        scope: str,
        idempotency_key: str,
        request_sha256: str,
        submitted: dict[str, Any],
    ) -> BuildCommandResult | None:
        """构建幂等回放：同键同命令回放原候选（按当前状态忠实投影），同键异
        命令 409 且不产生新历史。"""
        record = IdempotencyRepository(session).get(scope, idempotency_key)
        if record is None:
            return None
        if record.request_sha256 != request_sha256:
            raise self._idempotency_conflict(
                record=record,
                submitted=submitted,
                existing_result={"candidate_id": record.result_id},
                detail="同一幂等键已绑定不同构建命令，拒绝复用。",
                scope=scope,
                idempotency_key=idempotency_key,
            )
        candidate = EvidenceProcessingCandidateRepository(
            session, self.artifact_store
        ).get(record.result_id)
        if candidate.job_id is None:
            raise AppInternalError("资料版本候选缺少持久任务")
        job_id = candidate.job_id
        status = (
            candidate.status.value
            if hasattr(candidate.status, "value")
            else candidate.status
        )
        if candidate.complete_revision_id is not None:
            # READY/ACTIVE：回放冻结结果。
            return BuildCommandResult(
                created=False,
                candidate_id=candidate.candidate_id,
                job_id=job_id,
                candidate_status=status,
                complete_revision_id=candidate.complete_revision_id,
            )
        if status in {
            EvidenceProcessingCandidateStatus.STAGED.value,
            EvidenceProcessingCandidateStatus.PROCESSING.value,
            EvidenceProcessingCandidateStatus.RETRYABLE_FAILURE.value,
        }:
            return BuildCommandResult(
                created=False,
                candidate_id=candidate.candidate_id,
                job_id=job_id,
                candidate_status=status,
                complete_revision_id=None,
            )
        if status == EvidenceProcessingCandidateStatus.NEEDS_ATTENTION.value:
            raise AppReviewPendingError(
                candidate_id=candidate.candidate_id,
                candidate_status=status,
                unresolved_gates=self._unresolved_blocking_gates(session, candidate),
                submitted=submitted,
                detail="该构建存在未核对的识别风险，请完成核对后重新构建。",
            )
        if status == EvidenceProcessingCandidateStatus.ACTIVE.value:
            return BuildCommandResult(
                created=False,
                candidate_id=candidate.candidate_id,
                job_id=job_id,
                candidate_status=status,
                complete_revision_id=candidate.complete_revision_id,
            )
        raise AppBuildFailedError(
            candidate_id=candidate.candidate_id,
            candidate_status=status,
            failed_gates=[{"gate": "candidate", "detail": f"候选状态 {status}"}],
            submitted=submitted,
            detail="该构建命令此前未成功冻结完整处理修订。",
        )

    def _candidate_status(self, candidate_id: str) -> str:
        """读取候选最新状态（构建失败后事件已提交，须以 DB 为准）。"""
        with self.session_factory() as session:
            candidate = EvidenceProcessingCandidateRepository(
                session, self.artifact_store
            ).get(candidate_id)
            status = (
                candidate.status.value
                if hasattr(candidate.status, "value")
                else candidate.status
            )
            return status

    def _unresolved_blocking_gates(
        self,
        session: Session,
        candidate,
    ) -> list[dict[str, Any]]:
        """按候选冻结清单列出未解除风险，不吸收排队后的旁路记录。"""
        from app.domain.contracts.enums import OcrRiskLevel
        from app.storage.evidence_locator_models import (
            OCRRiskReviewRecord,
        )
        from app.storage.evidence_locator_repositories import (
            OCRRiskScanRepository,
        )

        manifest = candidate.attempt_manifest
        scan_repo = OCRRiskScanRepository(session)
        correction_repo = CorrectionRepository(session)
        corrections = [correction_repo.get(item) for item in manifest.correction_ids]
        page_lengths: dict[str, int] = {}
        reviewed_flag_ids = set(
            session.execute(
                select(OCRRiskReviewRecord.risk_flag_id).where(
                    OCRRiskReviewRecord.review_id.in_(manifest.risk_review_ids)
                )
            ).scalars()
        ) if manifest.risk_review_ids else set()
        unresolved: list[dict[str, Any]] = []
        for scan_id in manifest.risk_scan_ids:
            scan = scan_repo.get(scan_id)
            for flag in scan.flags:
                level = flag.level.value if hasattr(flag.level, "value") else flag.level
                if level != OcrRiskLevel.BLOCKING.value:
                    continue
                flag_id = f"{scan.scan_id}:{flag.risk_id}"
                if scan.ocr_page_id not in page_lengths:
                    page_lengths[scan.ocr_page_id] = len(
                        OcrPageRepository(session).get(scan.ocr_page_id).raw_text
                    )
                covered = any(
                    correction.ocr_page_id == scan.ocr_page_id
                    and correction_covers_risk(
                        flag,
                        correction_text_start=correction.text_start,
                        correction_text_end=correction.text_end,
                        page_text_length=page_lengths[scan.ocr_page_id],
                    )
                    for correction in corrections
                )
                reviewed = flag_id in reviewed_flag_ids and allows_risk_review(flag)
                if not reviewed and not covered:
                    unresolved.append(
                        {
                            "scan_id": scan.scan_id,
                            "risk_id": flag.risk_id,
                            "text": flag.text,
                            "text_start": flag.text_start,
                            "text_end": flag.text_end,
                        }
                    )
        return unresolved

    @staticmethod
    def _build_failed_gates(exc: Exception) -> list[dict[str, Any]]:
        if isinstance(exc, MissingRiskScanError):
            return [{"gate": "risk", "detail": "缺少当前识别版本的风险扫描结果"}]
        if isinstance(exc, MissingMetadataRevisionError):
            return [{"gate": "metadata", "detail": "缺少当前资料的有效分类修订"}]
        if isinstance(exc, UnresolvedBlockingRiskError):
            return [{"gate": "risk", "detail": "存在尚未完成核对的关键识别风险"}]
        if isinstance(exc, RevisionClosureError):
            return [
                {
                    "gate": "manifest",
                    "detail": "完整处理修订未覆盖当前资料的全部页面和来源",
                }
            ]
        if isinstance(exc, CandidateStateTransitionError):
            return [{"gate": "candidate", "detail": "当前处理候选状态不允许继续构建"}]
        return [{"gate": "closure", "detail": "完整处理修订未能通过闭包校验"}]

    # ------------------------------------------------------------------ 激活 / 回滚

    @app_error_boundary
    def activate(
        self,
        *,
        target_snapshot_id: str,
        target_revision_id: str,
        expected_revision: int,
        idempotency_key: str,
        actor: str,
        reason: str,
        candidate_id: str | None = None,
        job_id: str | None = None,
    ) -> ActivationCommandResult:
        """启用完整处理修订（单事务原子提交）。

        事件/快照状态/候选状态/成对指针与幂等主张在同一事务提交；任何子写或
        提交失败整体回滚，绝不出现「事件/指针已提交但幂等记录缺失」的半提交。
        命令身份包含 scope、目标对、预期修订号、reason 与 actor；同键异命令 409。
        """
        activation_service = EvidenceActivationService(
            self.session_factory, self.artifact_store
        )
        with self.session_factory() as session:
            self._begin_write(session)
            complete = self._load_complete(session, target_revision_id)
            episode_id = complete.review_episode_id
            scope = f"activation:{episode_id}"
            submitted = {
                "target_snapshot_id": target_snapshot_id,
                "target_revision_id": target_revision_id,
                "expected_revision": expected_revision,
                "reason": reason,
                "actor": actor,
            }
            request_sha256 = self._request_hash(submitted)
            # 幂等回放优先于乐观并发：同键同命令即使修订号已前进也返回原事件。
            replay = self._activation_replay(
                session,
                scope=scope,
                idempotency_key=idempotency_key,
                request_sha256=request_sha256,
                submitted=submitted,
            )
            if replay is not None:
                session.rollback()
                return ActivationCommandResult(created=False, event=replay)
            if complete.review_episode_id != episode_id:
                raise AppScopeMismatchError(
                    "目标处理修订与审核节点作用域不一致",
                    submitted=submitted,
                    current_record={"review_episode_id": episode_id},
                    field_diff={
                        "review_episode_id": {
                            "current": episode_id,
                            "submitted": complete.review_episode_id,
                        }
                    },
                )
            if complete.evidence_snapshot_id != target_snapshot_id:
                raise AppScopeMismatchError(
                    "目标处理修订不属于目标快照",
                    submitted=submitted,
                    current_record={
                        "evidence_snapshot_id": complete.evidence_snapshot_id
                    },
                    field_diff={
                        "target_snapshot_id": {
                            "current": complete.evidence_snapshot_id,
                            "submitted": target_snapshot_id,
                        }
                    },
                )
            event_id = (
                "evt-"
                + sha256(f"{episode_id}:{idempotency_key}".encode()).hexdigest()[:32]
            )
            try:
                outcome = activation_service.activate_in_session(
                    session,
                    target_snapshot_id=target_snapshot_id,
                    target_revision_id=target_revision_id,
                    expected_revision=expected_revision,
                    actor=actor,
                    reason=reason,
                    candidate_id=candidate_id or complete.producer_candidate_id,
                    job_id=job_id,
                    event_id=event_id,
                )
            except ActivationGateError as exc:
                raise self._activation_gate_error(
                    target_revision_id, submitted, exc
                ) from exc
            except ActivationAlreadyActiveError as exc:
                current = EpisodeRepository(session).get(episode_id)
                current_pair = {
                    "target_snapshot_id": current.active_evidence_snapshot_id,
                    "target_revision_id": (
                        current.active_evidence_processing_revision_id
                    ),
                }
                submitted_pair = {
                    "target_snapshot_id": target_snapshot_id,
                    "target_revision_id": target_revision_id,
                }
                raise AppAlreadyCurrentVersionError(
                    "所选快照和处理修订已经是当前使用版本，本次操作没有产生新历史。",
                    submitted=submitted,
                    current_record={
                        "review_episode_id": episode_id,
                        "revision": current.revision,
                        **current_pair,
                    },
                    field_diff={
                        "active_pair": {
                            "current": current_pair,
                            "submitted": submitted_pair,
                        }
                    },
                ) from exc
            except ActivationRevisionConflictError as exc:
                # 并发败者：提交候选 revision_conflict 投影（WP-44B 语义），
                # 不写幂等主张；调用方返回 409 STALE_REVISION。
                session.commit()
                raise self._stale_revision_error(
                    episode_id, expected_revision, submitted
                ) from exc
            except ActivationIdempotencyConflictError as exc:
                record = IdempotencyRepository(session).get(scope, idempotency_key)
                if record is None:
                    raise AppIdempotencyConflictError(
                        submitted=submitted,
                        existing_result={"event_id": event_id},
                        current_record={},
                        field_diff={},
                        detail="激活事件已存在但命令不一致，拒绝幂等复用。",
                    ) from exc
                raise self._idempotency_conflict(
                    record=record,
                    submitted=submitted,
                    existing_result={"event_id": event_id},
                    detail="激活事件已存在但命令不一致，拒绝幂等复用。",
                    scope=scope,
                    idempotency_key=idempotency_key,
                ) from exc
            IdempotencyRepository(session).resolve(
                scope=scope,
                idempotency_key=idempotency_key,
                submitted_hash=request_sha256,
                result_type="activation_event",
                result_id=outcome.event.event_id,
            )
            session.commit()
        return ActivationCommandResult(created=True, event=outcome.event)

    @app_error_boundary
    def rollback(
        self,
        *,
        target_snapshot_id: str,
        target_revision_id: str,
        expected_revision: int,
        idempotency_key: str,
        actor: str,
        reason: str,
    ) -> ActivationCommandResult:
        """回滚到历史活动版本对（单事务原子提交）。

        事件与成对指针及幂等主张在同一事务提交；任何失败整体回滚。命令身份包含
        scope、目标对、预期修订号、reason 与 actor；同键异命令 409。
        """
        activation_service = EvidenceActivationService(
            self.session_factory, self.artifact_store
        )
        with self.session_factory() as session:
            self._begin_write(session)
            complete = self._load_complete(session, target_revision_id)
            episode_id = complete.review_episode_id
            scope = f"rollback:{episode_id}"
            submitted = {
                "target_snapshot_id": target_snapshot_id,
                "target_revision_id": target_revision_id,
                "expected_revision": expected_revision,
                "reason": reason,
                "actor": actor,
            }
            request_sha256 = self._request_hash(submitted)
            replay = self._activation_replay(
                session,
                scope=scope,
                idempotency_key=idempotency_key,
                request_sha256=request_sha256,
                submitted=submitted,
            )
            if replay is not None:
                session.rollback()
                return ActivationCommandResult(created=False, event=replay)
            event_id = (
                "evt-"
                + sha256(
                    f"rollback:{episode_id}:{idempotency_key}".encode()
                ).hexdigest()[:32]
            )
            try:
                outcome = activation_service.rollback_in_session(
                    session,
                    target_snapshot_id=target_snapshot_id,
                    target_revision_id=target_revision_id,
                    expected_revision=expected_revision,
                    actor=actor,
                    reason=reason,
                    event_id=event_id,
                )
            except ActivationRevisionConflictError as exc:
                session.rollback()
                raise self._stale_revision_error(
                    episode_id, expected_revision, submitted
                ) from exc
            except RollbackTargetError as exc:
                episode = EpisodeRepository(session).get(episode_id)
                raise AppRollbackTargetError(
                    "选定的历史版本不能作为回滚目标。",
                    submitted=submitted,
                    current_record={
                        "review_episode_id": episode_id,
                        "revision": episode.revision,
                        "active_evidence_snapshot_id": episode.active_evidence_snapshot_id,
                        "active_evidence_processing_revision_id": episode.active_evidence_processing_revision_id,
                    },
                    field_diff={
                        "target": {
                            "current": {
                                "snapshot_id": episode.active_evidence_snapshot_id,
                                "revision_id": episode.active_evidence_processing_revision_id,
                            },
                            "submitted": {
                                "snapshot_id": target_snapshot_id,
                                "revision_id": target_revision_id,
                            },
                        }
                    },
                ) from exc
            IdempotencyRepository(session).resolve(
                scope=scope,
                idempotency_key=idempotency_key,
                submitted_hash=request_sha256,
                result_type="activation_event",
                result_id=outcome.event.event_id,
            )
            session.commit()
        return ActivationCommandResult(created=True, event=outcome.event)

    def _stale_revision_error(
        self,
        episode_id: str,
        expected_revision: int,
        submitted: dict[str, Any],
    ) -> AppStaleRevisionError:
        """从最新审核节点状态构造 409 STALE_REVISION（提交值 + 服务端差异）。"""
        with self.session_factory() as session:
            episode = EpisodeRepository(session).get(episode_id)
        return AppStaleRevisionError(
            entity_type="review_episode",
            entity_id=episode_id,
            expected_revision=expected_revision,
            current_revision=episode.revision,
            submitted=submitted,
            current_record={
                "review_episode_id": episode_id,
                "revision": episode.revision,
                "active_evidence_snapshot_id": episode.active_evidence_snapshot_id,
                "active_evidence_processing_revision_id": (
                    episode.active_evidence_processing_revision_id
                ),
            },
            field_diff={
                "revision": {
                    "current": episode.revision,
                    "submitted": expected_revision,
                }
            },
        )

    def _activation_replay(
        self,
        session: Session,
        *,
        scope: str,
        idempotency_key: str,
        request_sha256: str,
        submitted: dict[str, Any],
    ):
        """激活/回滚幂等回放：同键同命令返回原事件，同键异命令 409。"""
        record = IdempotencyRepository(session).get(scope, idempotency_key)
        if record is None:
            return None
        if record.request_sha256 != request_sha256:
            raise self._idempotency_conflict(
                record=record,
                submitted=submitted,
                existing_result={"event_id": record.result_id},
                detail="激活/回滚事件已存在但命令不一致，拒绝幂等复用。",
                scope=scope,
                idempotency_key=idempotency_key,
            )
        return EvidenceActivationEventRepository(session).get(record.result_id)

    def _activation_gate_error(
        self, revision_id: str, submitted: dict[str, Any], exc: Exception
    ) -> AppActivationGateError:
        """激活门禁失败：从读取服务重算逐门禁结果并列出未通过门禁。"""
        from app.services.evidence_api_read_service import EvidenceApiReadService

        read = EvidenceApiReadService(self.session_factory, self.artifact_store)
        view = read.revision_view(revision_id)
        failed = [
            {"gate": g.gate, "detail": g.detail}
            for g in view.gates
            if g.status != "passed"
        ]
        return AppActivationGateError(
            revision_id=revision_id,
            failed_gates=failed or [{"gate": "activation", "detail": "激活门禁未通过"}],
            submitted=submitted,
            detail="资料版本未通过启用门禁，请补齐要求后重试。",
        )

    # ------------------------------------------------------------------ 被提及资料

    @app_error_boundary
    def create_referenced_document(
        self,
        *,
        subject_id: str,
        review_episode_id: str,
        expected_revision: int,
        description: str,
        document_type: str | None,
        source_party: str | None,
        origin: Any,
        pattern_version: str | None,
        trigger_locator_id: str | None,
        idempotency_key: str,
        actor: str,
    ) -> ReferencedDocumentCommandResult:
        with self.session_factory() as session:
            self._begin_write(session)
            episode = self._require_subject_episode(
                session, subject_id, review_episode_id
            )
            scope = f"refdoc_create:{review_episode_id}"
            submitted = {
                "subject_id": subject_id,
                "review_episode_id": review_episode_id,
                "expected_revision": expected_revision,
                "description": description,
                "document_type": document_type,
                "source_party": source_party,
                "origin": origin.value if hasattr(origin, "value") else origin,
                "pattern_version": pattern_version,
                "trigger_locator_id": trigger_locator_id,
                "actor": actor,
            }
            request_sha256 = self._request_hash(submitted)

            def _loader(result_id: str, *, safe: bool) -> Any:
                revision = ReferencedDocumentRepository(session).get_revision(result_id)
                if safe:
                    return {
                        "revision_id": revision.revision_id,
                        "referenced_document_id": revision.referenced_document_id,
                        "description": revision.description,
                    }
                return revision

            revision = self._replay_or_conflict(
                session,
                scope=scope,
                idempotency_key=idempotency_key,
                submitted=submitted,
                request_sha256=request_sha256,
                result_loader=_loader,
            )
            if revision is not None:
                session.rollback()
                return ReferencedDocumentCommandResult(created=False, revision=revision)
            # 登记前校验审核节点预期修订号（§5.2 乐观并发）。
            self._check_episode_revision(
                session, review_episode_id, expected_revision, submitted
            )
            revision = EvidenceReferencedDocumentService(
                self.session_factory
            ).register_in_session(
                session,
                project_id=episode.project_id,
                subject_id=subject_id,
                review_episode_id=review_episode_id,
                description=description,
                document_type=document_type,
                source_party=source_party,
                origin=origin,
                pattern_version=pattern_version,
                trigger_locator_id=trigger_locator_id,
                created_by=actor,
                revision_id=f"rd-{sha256(f'{scope}:{idempotency_key}'.encode()).hexdigest()[:32]}",
                referenced_document_id=(
                    "refdoc-"
                    + sha256(f"{scope}:{idempotency_key}".encode()).hexdigest()[:32]
                ),
            )
            IdempotencyRepository(session).resolve(
                scope=scope,
                idempotency_key=idempotency_key,
                submitted_hash=request_sha256,
                result_type="referenced_document_revision",
                result_id=revision.revision_id,
            )
            session.commit()
            return ReferencedDocumentCommandResult(created=True, revision=revision)

    def _revise_chain_command(
        self,
        *,
        referenced_document_id: str,
        command: str,
        idempotency_key: str,
        submitted: dict[str, Any],
        expected_revision: int,
        write,
    ) -> ReferencedDocumentCommandResult:
        """revise/confirm/dismiss 公共编排：链头预期修订号校验 + 幂等。"""
        with self.session_factory() as session:
            self._begin_write(session)
            scope = f"refdoc_{command}:{referenced_document_id}"
            request_sha256 = self._request_hash(submitted)

            def _loader(result_id: str, *, safe: bool) -> Any:
                revision = ReferencedDocumentRepository(session).get_revision(result_id)
                if safe:
                    return {
                        "revision_id": revision.revision_id,
                        "referenced_document_id": revision.referenced_document_id,
                        "status": (
                            revision.status.value
                            if hasattr(revision.status, "value")
                            else revision.status
                        ),
                    }
                return revision

            revision = self._replay_or_conflict(
                session,
                scope=scope,
                idempotency_key=idempotency_key,
                submitted=submitted,
                request_sha256=request_sha256,
                result_loader=_loader,
            )
            if revision is not None:
                session.rollback()
                return ReferencedDocumentCommandResult(created=False, revision=revision)
            head = EvidenceReferencedDocumentService.revision_head(
                session, referenced_document_id
            )
            current_revision = head.revision if head is not None else None
            if current_revision != expected_revision:
                raise StaleRevision409Error(
                    entity_type="referenced_document",
                    entity_id=referenced_document_id,
                    expected_revision=expected_revision,
                    current_revision=current_revision,
                    submitted=submitted,
                    current_record={
                        "referenced_document_id": referenced_document_id,
                        "revision": current_revision,
                        "status": (
                            head.status.value
                            if head is not None and hasattr(head.status, "value")
                            else (head.status if head is not None else None)
                        ),
                    },
                    field_diff={
                        "revision": {
                            "current": current_revision,
                            "submitted": expected_revision,
                        }
                    },
                )
            revision_id = (
                "rd-" + sha256(f"{scope}:{idempotency_key}".encode()).hexdigest()[:32]
            )
            revision = write(
                session,
                revision_id=revision_id,
            )
            IdempotencyRepository(session).resolve(
                scope=scope,
                idempotency_key=idempotency_key,
                submitted_hash=request_sha256,
                result_type="referenced_document_revision",
                result_id=revision.revision_id,
            )
            session.commit()
            return ReferencedDocumentCommandResult(created=True, revision=revision)

    @app_error_boundary
    def revise_referenced_document(
        self,
        *,
        referenced_document_id: str,
        description: str,
        document_type: str | None,
        source_party: str | None,
        reason: str,
        expected_revision: int,
        idempotency_key: str,
        actor: str,
    ) -> ReferencedDocumentCommandResult:
        submitted = {
            "referenced_document_id": referenced_document_id,
            "description": description,
            "document_type": document_type,
            "source_party": source_party,
            "reason": reason,
            "expected_revision": expected_revision,
            "actor": actor,
        }
        service = EvidenceReferencedDocumentService(self.session_factory)

        def _write(session, *, revision_id: str):
            return service.revise_in_session(
                session,
                referenced_document_id=referenced_document_id,
                description=description,
                document_type=document_type,
                source_party=source_party,
                reason=reason,
                created_by=actor,
                revision_id=revision_id,
            )

        return self._revise_chain_command(
            referenced_document_id=referenced_document_id,
            command="revise",
            idempotency_key=idempotency_key,
            submitted=submitted,
            expected_revision=expected_revision,
            write=_write,
        )

    @app_error_boundary
    def confirm_referenced_document(
        self,
        *,
        referenced_document_id: str,
        trigger_locator_id: str,
        reason: str,
        expected_revision: int,
        idempotency_key: str,
        actor: str,
    ) -> ReferencedDocumentCommandResult:
        submitted = {
            "referenced_document_id": referenced_document_id,
            "trigger_locator_id": trigger_locator_id,
            "reason": reason,
            "expected_revision": expected_revision,
            "actor": actor,
        }
        service = EvidenceReferencedDocumentService(self.session_factory)

        def _write(session, *, revision_id: str):
            return service.confirm_in_session(
                session,
                referenced_document_id=referenced_document_id,
                trigger_locator_id=trigger_locator_id,
                reason=reason,
                created_by=actor,
                revision_id=revision_id,
            )

        return self._revise_chain_command(
            referenced_document_id=referenced_document_id,
            command="confirm",
            idempotency_key=idempotency_key,
            submitted=submitted,
            expected_revision=expected_revision,
            write=_write,
        )

    @app_error_boundary
    def dismiss_referenced_document(
        self,
        *,
        referenced_document_id: str,
        reason: str,
        expected_revision: int,
        idempotency_key: str,
        actor: str,
    ) -> ReferencedDocumentCommandResult:
        submitted = {
            "referenced_document_id": referenced_document_id,
            "reason": reason,
            "expected_revision": expected_revision,
            "actor": actor,
        }
        service = EvidenceReferencedDocumentService(self.session_factory)

        def _write(session, *, revision_id: str):
            return service.dismiss_in_session(
                session,
                referenced_document_id=referenced_document_id,
                reason=reason,
                created_by=actor,
                revision_id=revision_id,
            )

        return self._revise_chain_command(
            referenced_document_id=referenced_document_id,
            command="dismiss",
            idempotency_key=idempotency_key,
            submitted=submitted,
            expected_revision=expected_revision,
            write=_write,
        )

    @app_error_boundary
    def resolve_referenced_document(
        self,
        *,
        referenced_document_id: str,
        status: ReferencedDocumentResolutionStatus,
        source_document_version_id: str | None,
        expected_revision: int,
        idempotency_key: str,
        actor: str,
    ) -> ResolutionCommandResult:
        with self.session_factory() as session:
            self._begin_write(session)
            scope = f"refdoc_resolution:{referenced_document_id}"
            submitted = {
                "referenced_document_id": referenced_document_id,
                "status": status.value if hasattr(status, "value") else status,
                "source_document_version_id": source_document_version_id,
                "expected_revision": expected_revision,
                "actor": actor,
            }
            request_sha256 = self._request_hash(submitted)

            def _loader(result_id: str, *, safe: bool) -> Any:
                resolution = ReferencedDocumentRepository(session).get_resolution(
                    result_id
                )
                if safe:
                    return {
                        "resolution_revision_id": resolution.resolution_revision_id,
                        "referenced_document_id": resolution.referenced_document_id,
                        "status": (
                            resolution.status.value
                            if hasattr(resolution.status, "value")
                            else resolution.status
                        ),
                    }
                return resolution

            resolution = self._replay_or_conflict(
                session,
                scope=scope,
                idempotency_key=idempotency_key,
                submitted=submitted,
                request_sha256=request_sha256,
                result_loader=_loader,
            )
            if resolution is not None:
                session.rollback()
                return ResolutionCommandResult(created=False, resolution=resolution)
            head = EvidenceReferencedDocumentService.resolution_head(
                session, referenced_document_id
            )
            current_revision = head.revision if head is not None else 0
            if current_revision != expected_revision:
                raise StaleRevision409Error(
                    entity_type="referenced_document_resolution",
                    entity_id=referenced_document_id,
                    expected_revision=expected_revision,
                    current_revision=current_revision,
                    submitted=submitted,
                    current_record={
                        "referenced_document_id": referenced_document_id,
                        "resolution_revision": current_revision,
                        "status": (
                            head.status.value
                            if head is not None and hasattr(head.status, "value")
                            else (head.status if head is not None else None)
                        ),
                    },
                    field_diff={
                        "resolution_revision": {
                            "current": current_revision,
                            "submitted": expected_revision,
                        }
                    },
                )
            resolution = EvidenceReferencedDocumentService(
                self.session_factory
            ).resolve_in_session(
                session,
                referenced_document_id=referenced_document_id,
                status=status,
                source_document_version_id=source_document_version_id,
                created_by=actor,
                resolution_revision_id=(
                    "res-"
                    + sha256(f"{scope}:{idempotency_key}".encode()).hexdigest()[:32]
                ),
            )
            IdempotencyRepository(session).resolve(
                scope=scope,
                idempotency_key=idempotency_key,
                submitted_hash=request_sha256,
                result_type="referenced_document_resolution",
                result_id=resolution.resolution_revision_id,
            )
            session.commit()
            return ResolutionCommandResult(created=True, resolution=resolution)

    @app_error_boundary
    def unresolve_referenced_document(
        self,
        *,
        referenced_document_id: str,
        expected_revision: int,
        idempotency_key: str,
        actor: str,
    ) -> ResolutionCommandResult:
        return self.resolve_referenced_document(
            referenced_document_id=referenced_document_id,
            status=ReferencedDocumentResolutionStatus.UNRESOLVED,
            source_document_version_id=None,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
            actor=actor,
        )
