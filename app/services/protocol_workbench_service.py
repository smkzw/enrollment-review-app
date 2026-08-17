"""方案解构工作台用例编排（Phase 3 切片 5）。

HTTP 层只做协议转换；本服务复用持久 Job、Slice 1–4 领域服务与仓储，
不在 API 路由内做临床判断。上传登记原始方案并创建 ``protocol_deconstruction``
任务；身份/期别确认、草稿 revision、完整性投影与首次发布均通过 Job 检查点
与既有服务完成，不另建平行存储。
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.agent_io import (
    ProtocolDeconstructionDraft,
    ProtocolDeconstructionInput,
)
from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import DatePrecision, MetadataResolutionStatus, StudyPhase
from app.domain.contracts.protocol_drafts import DraftFeedbackKind, ProtocolDraftRevision
from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
from app.domain.contracts.protocol_metadata import (
    ProtocolIdentityDecision,
    StudyPhaseSelection,
)
from app.protocols.deconstruction_gate import (
    ProtocolDeconstructionGate,
    ProtocolDeconstructionGateResult,
    ProtocolGateIssue,
)
from app.protocols.ingestion import (
    SourceIngestionError,
    compute_sha256,
    register_source_artifact,
)
from app.protocols.metadata import MetadataExtractionError, confirm_protocol_identity
from app.services.job_service import JobService, StepSpec
from app.services.protocol_draft_service import ProtocolDraftService
from app.services.protocol_publication_service import (
    DuplicateFirstProjectError,
    ProtocolPublicationError,
    ProtocolPublicationRequest,
    ProtocolPublicationService,
    PublicationGateError,
    PublicationLineageError,
)
from app.storage.codecs import utc_now
from app.storage.config import DataPaths
from app.storage.models import JobRecord, JobStepRecord
from app.storage.repositories import JobRepository, NotFoundError, ProtocolDraftRevisionRepository
from app.workflow.errors import JobNotFoundError, JobStateConflictError
from app.workflow.jobstore import JobStore

PROTOCOL_DECONSTRUCTION_JOB_TYPE = "protocol_deconstruction"

STEP_REGISTER = "register_file"
STEP_EXTRACT = "extract_structure"
STEP_RENDER = "render_and_align"
STEP_IDENTIFY = "identify_identity_phase"
STEP_AWAIT_IDENTITY = "await_identity_confirm"
STEP_GENERATE = "generate_draft"
STEP_INTEGRITY = "integrity_check"
STEP_AWAIT_REVIEW = "await_review"
STEP_PUBLISH = "publish"

PROTOCOL_DECONSTRUCTION_STEPS: tuple[StepSpec, ...] = (
    StepSpec(STEP_REGISTER, "登记文件"),
    StepSpec(STEP_EXTRACT, "提取结构", depends_on=(STEP_REGISTER,)),
    StepSpec(STEP_RENDER, "渲染并对齐", depends_on=(STEP_EXTRACT,)),
    StepSpec(STEP_IDENTIFY, "识别方案信息与研究期别", depends_on=(STEP_RENDER,)),
    StepSpec(
        STEP_AWAIT_IDENTITY,
        "等待方案信息确认",
        depends_on=(STEP_IDENTIFY,),
        waiting_user_kind="identity",
    ),
    StepSpec(STEP_GENERATE, "生成草稿", depends_on=(STEP_AWAIT_IDENTITY,)),
    StepSpec(STEP_INTEGRITY, "完整性检查", depends_on=(STEP_GENERATE,)),
    StepSpec(
        STEP_AWAIT_REVIEW,
        "等待审阅",
        depends_on=(STEP_INTEGRITY,),
        waiting_user_kind="review",
    ),
    StepSpec(
        STEP_PUBLISH,
        "发布",
        depends_on=(STEP_AWAIT_REVIEW,),
        waiting_user_kind="publish",
    ),
)

_CHECKPOINT_STEP_ORDER: tuple[str, ...] = tuple(step.step_id for step in PROTOCOL_DECONSTRUCTION_STEPS)

Now = Callable[[], datetime]


class ProtocolWorkbenchError(RuntimeError):
    """工作台前置条件或会话状态不满足。"""

    def __init__(
        self,
        code: str,
        *,
        title: str,
        detail: str,
        recovery: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.title = title
        self.detail = detail
        self.recovery = recovery
        self.context = context
        super().__init__(detail)


@dataclass(frozen=True)
class StartDeconstructionResult:
    job_id: str
    state: str
    created: bool
    source_artifact_id: str
    file_name: str


@dataclass(frozen=True)
class ProtocolSessionView:
    job_id: str
    job_type: str
    state: str
    state_label: str
    progress_completed: int
    progress_total: int
    session_kind: str
    awaiting_user: str | None
    awaiting_user_label: str | None
    source_artifact_id: str | None
    file_name: str | None
    snapshot_id: str | None
    draft_id: str | None
    draft_revision_id: str | None
    draft_revision_number: int | None
    draft_status: str | None
    selected_phase: str | None
    selected_phase_label: str | None
    protocol_code: str | None
    official_version: str | None
    recovery_checkpoint_id: str | None
    recovery_step_id: str | None
    next_action: str
    publishable: bool | None


@dataclass(frozen=True)
class IdentityReviewView:
    job_id: str
    snapshot_id: str
    confirmation_required: bool
    identity_decision: ProtocolIdentityDecision
    phase_candidates: list[dict[str, Any]]
    metadata_candidates: list[dict[str, Any]]
    metadata_conflicts: list[dict[str, Any]]


@dataclass(frozen=True)
class DraftDetailView:
    job_id: str
    revision: ProtocolDraftRevision
    diff: dict[str, Any] | None


@dataclass(frozen=True)
class IntegrityView:
    job_id: str
    publishable: bool
    blocking_count: int
    review_count: int
    reminder_count: int
    checks: list[dict[str, Any]]
    issues: list[dict[str, Any]]


@dataclass(frozen=True)
class PublicationView:
    job_id: str
    project_id: str
    protocol_version_id: str
    rule_set_id: str
    rule_set_revision: int
    replay: bool


def _study_phase_label(phase: str | None) -> str | None:
    labels = {
        StudyPhase.PHASE_II.value: "II 期",
        StudyPhase.PHASE_III.value: "III 期",
        StudyPhase.SEAMLESS_II_III.value: "II/III 期无缝设计",
        StudyPhase.OTHER.value: "其他",
    }
    return labels.get(phase) if phase else None


def _awaiting_user_label(kind: str | None) -> str | None:
    if kind == "identity":
        return "需要确认方案信息与研究期别"
    if kind == "review":
        return "等待审阅草稿"
    if kind == "publish":
        return "等待发布确认"
    return None


def _date_value_from_input(value: str, precision: str) -> DateValue:
    """把工作台输入的年/月/日文本规范化为领域日期值。

    ``DateValue`` 持久化的是可排序的具体日期，同时由 ``precision`` 保留
    用户确认的粒度。API 输入不能直接把 ``YYYY`` 或 ``YYYY-MM`` 交给
    Pydantic 的 ``date`` 字段，否则有效的低精度确认会变成 500。
    """
    normalized = value.strip()
    try:
        date_precision = DatePrecision(precision)
    except ValueError as exc:
        raise MetadataExtractionError("方案日期精度必须是年、月或日") from exc

    if date_precision == DatePrecision.UNKNOWN:
        raise MetadataExtractionError("方案日期确认必须提供年、月或日精度")

    try:
        if date_precision == DatePrecision.YEAR:
            if re.fullmatch(r"\d{4}", normalized) is None:
                raise ValueError
            parsed = date(int(normalized), 1, 1)
        elif date_precision == DatePrecision.MONTH:
            match = re.fullmatch(r"(\d{4})-(\d{2})", normalized)
            if match is None:
                raise ValueError
            parsed = date(int(match.group(1)), int(match.group(2)), 1)
        else:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized) is None:
                raise ValueError
            parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise MetadataExtractionError(
            "方案日期格式与精度不一致，请填写 YYYY、YYYY-MM 或 YYYY-MM-DD"
        ) from exc

    return DateValue(value=parsed, precision=date_precision, source_text=None)


class ProtocolWorkbenchService:
    """方案解构工作台用例服务。"""

    WORKER_ID = "protocol-workbench-api"

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        data_paths: DataPaths,
        now: Now = utc_now,
        gate: ProtocolDeconstructionGate | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.data_paths = data_paths
        self.now = now
        self.gate = gate or ProtocolDeconstructionGate()
        self.jobs = JobService(session_factory, now=now)

    # ------------------------------------------------------------------ 上传

    def start_first_deconstruction(
        self,
        *,
        upload_path: Path,
        original_name: str,
        idempotency_key: str,
        actor: str = "用户",
    ) -> StartDeconstructionResult:
        display_name = original_name or upload_path.name
        try:
            sha256 = compute_sha256(upload_path)
        except SourceIngestionError as exc:
            raise ProtocolWorkbenchError(
                "SOURCE_INGESTION_FAILED",
                title="方案文件无法登记",
                detail=str(exc),
                recovery="请确认文件完整可读且为支持的方案格式（DOCX/DOC/PDF/TXT）后重新上传。",
            ) from exc

        source_artifact_id = (
            f"source-{sha256}-{upload_path.suffix.lower().lstrip('.') or 'bin'}"
        )
        try:
            artifact = register_source_artifact(
                upload_path,
                source_artifact_id=source_artifact_id,
                storage_root=self.data_paths.blobs_dir,
                uploaded_at=self.now(),
            )
        except SourceIngestionError as exc:
            raise ProtocolWorkbenchError(
                "SOURCE_INGESTION_FAILED",
                title="方案文件无法登记",
                detail=str(exc),
                recovery="请确认文件完整可读且为支持的方案格式（DOCX/DOC/PDF/TXT）后重新上传。",
            ) from exc

        # 将登记结果写入 Job payload，保证 runner 即使在 API 写入首个检查点前
        # 抢到租约，也能从持久任务输入恢复 register_file 步骤。
        payload = {
            "session_kind": "first_deconstruction",
            "file_name": display_name,
            "sha256": artifact.sha256,
            "mime_type": artifact.mime_type,
            "size_bytes": artifact.size_bytes,
            "storage_ref": artifact.storage_ref,
            "source_artifact_id": artifact.source_artifact_id,
            "actor": actor,
            "awaiting_user": None,
        }
        result = self.jobs.create_job(
            idempotency_key=idempotency_key,
            job_type=PROTOCOL_DECONSTRUCTION_JOB_TYPE,
            payload=payload,
            steps=list(PROTOCOL_DECONSTRUCTION_STEPS),
        )
        if not result.created:
            merged = self._merged_payload(result.job_id)
            return StartDeconstructionResult(
                job_id=result.job_id,
                state=result.state,
                created=False,
                source_artifact_id=str(merged.get("source_artifact_id") or ""),
                file_name=str(merged.get("file_name") or display_name),
            )

        with self.session_factory() as session:
            with session.begin():
                store = JobStore(session, now=self.now)
                lease = store.claim_job(result.job_id, self.WORKER_ID)
                if lease is None:
                    # runner 可能已在 Job 创建后取得租约；源登记信息已在
                    # payload 中持久化，此时返回当前状态即可由前端继续恢复。
                    state = store.get_job(result.job_id).state
                else:
                    store.start_step(lease, STEP_REGISTER)
                    store.complete_step(
                        lease,
                        STEP_REGISTER,
                        checkpoint_payload={
                            "source_artifact_id": artifact.source_artifact_id,
                            "file_name": display_name,
                            "sha256": artifact.sha256,
                            "mime_type": artifact.mime_type,
                            "size_bytes": artifact.size_bytes,
                            "storage_ref": artifact.storage_ref,
                            "uploaded_at": artifact.uploaded_at.isoformat(),
                        },
                    )
                    job = store.get_job(result.job_id)
                    job.state = "queued"
                    job.lease_owner = None
                    job.lease_expires_at = None
                    session.flush()
                    state = job.state
        return StartDeconstructionResult(
            job_id=result.job_id,
            state=state,
            created=True,
            source_artifact_id=artifact.source_artifact_id,
            file_name=display_name,
        )

    # ------------------------------------------------------------------ 查询

    def get_session(self, job_id: str) -> ProtocolSessionView:
        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        snapshot = self.jobs.get_status(job_id)
        draft_summary = self._draft_summary(merged)
        gate_summary = self._gate_summary(merged)
        recovery_step, recovery_checkpoint = self._recovery_point(job_id)
        persisted_wait = next(
            (
                step.waiting_user_kind
                for step in snapshot.steps
                if step.state == "waiting_user" and step.waiting_user_kind is not None
            ),
            None,
        )
        awaiting = persisted_wait or merged.get("awaiting_user")
        return ProtocolSessionView(
            job_id=job_id,
            job_type=snapshot.job_type,
            state=snapshot.state,
            state_label=self._job_state_label(snapshot.state),
            progress_completed=snapshot.progress_completed,
            progress_total=snapshot.progress_total,
            session_kind=str(merged.get("session_kind", "first_deconstruction")),
            awaiting_user=awaiting,
            awaiting_user_label=_awaiting_user_label(awaiting),
            source_artifact_id=merged.get("source_artifact_id"),
            file_name=merged.get("file_name"),
            snapshot_id=merged.get("snapshot_id"),
            draft_id=merged.get("draft_id"),
            draft_revision_id=merged.get("draft_revision_id"),
            draft_revision_number=draft_summary.get("revision_number"),
            draft_status=draft_summary.get("status"),
            selected_phase=merged.get("selected_phase"),
            selected_phase_label=_study_phase_label(merged.get("selected_phase")),
            protocol_code=merged.get("protocol_code"),
            official_version=merged.get("official_version"),
            recovery_checkpoint_id=recovery_checkpoint,
            recovery_step_id=recovery_step,
            next_action=self._next_action(merged, gate_summary, awaiting_user=awaiting),
            publishable=gate_summary.get("publishable"),
        )

    def get_identity_review(self, job_id: str) -> IdentityReviewView:
        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        snapshot_id = merged.get("snapshot_id")
        if not snapshot_id:
            raise ProtocolWorkbenchError(
                "IDENTITY_NOT_READY",
                title="方案信息与研究期别尚未识别",
                detail="系统还在读取方案结构，或尚未完成方案信息与研究期别识别。",
                recovery="请稍后刷新；您也可以订阅任务事件了解最新进度。",
            )
        identity = self._load_identity_decision(merged)
        return IdentityReviewView(
            job_id=job_id,
            snapshot_id=snapshot_id,
            confirmation_required=identity.status != MetadataResolutionStatus.CONFIRMED,
            identity_decision=identity,
            phase_candidates=list(merged.get("phase_candidates") or []),
            metadata_candidates=list(merged.get("metadata_candidates") or []),
            metadata_conflicts=list(merged.get("metadata_conflicts") or []),
        )

    def get_draft_detail(self, job_id: str) -> DraftDetailView:
        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        revision = self._load_draft_revision(merged)
        diff_payload = None
        if revision.diff is not None:
            diff_payload = revision.diff.model_dump(mode="json")
        return DraftDetailView(
            job_id=job_id,
            revision=revision,
            diff=diff_payload,
        )

    def get_sources(self, job_id: str) -> dict[str, Any]:
        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        source_input = self._load_source_input(merged)
        spans = merged.get("source_spans") or {}
        materials = {
            item.source_span_id: item.model_dump(mode="json")
            for item in source_input.source_materials
        }
        return {
            "job_id": job_id,
            "snapshot_id": source_input.extraction_snapshot_id,
            "selected_phase": source_input.selected_phase.value,
            "selected_phase_label": _study_phase_label(source_input.selected_phase.value),
            "source_spans": spans,
            "source_materials": materials,
        }

    def get_integrity(self, job_id: str) -> IntegrityView:
        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        cached = merged.get("gate_result")
        if cached:
            result = ProtocolDeconstructionGateResult.model_validate(cached)
        else:
            source_input = self._load_source_input(merged)
            draft = self._load_draft_revision(merged).content
            spans = self._load_source_spans(merged)
            previous = self._load_previous_draft(merged)
            declared = self._load_declared_diff(merged)
            result = self.gate.evaluate(
                source_input,
                draft,
                source_spans=spans,
                previous_draft=previous,
                declared_diff=declared,
            )
        return self._integrity_view(job_id, result)

    # ------------------------------------------------------------------ 写入

    def confirm_identity(
        self,
        job_id: str,
        *,
        protocol_code: str,
        project_name: str,
        official_version: str,
        official_date_value: str,
        official_date_precision: str,
        study_phase: StudyPhase,
        actor: str,
        project_code: str | None = None,
        selected_candidate_ids: list[str] | None = None,
    ) -> ProtocolSessionView:
        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        snapshot = self.jobs.get_status(job_id)
        persisted_wait = next(
            (
                step.waiting_user_kind
                for step in snapshot.steps
                if step.state == "waiting_user" and step.waiting_user_kind is not None
            ),
            None,
        )
        if (persisted_wait or merged.get("awaiting_user")) != "identity":
            raise ProtocolWorkbenchError(
                "IDENTITY_CONFIRM_NOT_ALLOWED",
                title="当前不能确认方案信息",
                detail="任务尚未进入方案信息与研究期别确认步骤，或该步骤已经完成。",
                recovery="请刷新任务状态，按页面提示继续下一步。",
            )
        metadata_result = merged.get("metadata_extraction")
        pending = self._load_identity_decision(merged)
        if not metadata_result:
            raise ProtocolWorkbenchError(
                "IDENTITY_NOT_READY",
                title="缺少方案信息识别结果",
                detail="系统没有可供确认的方案信息与研究期别候选。",
                recovery="请等待识别步骤完成，或重新上传方案。",
            )
        from app.domain.contracts.protocol_metadata import (
            ProtocolMetadataCandidate,
            ProtocolMetadataConflict,
        )
        from app.protocols.metadata import MetadataExtractionResult

        raw = merged.get("metadata_extraction") or {}
        extraction = MetadataExtractionResult(
            snapshot_id=str(raw.get("snapshot_id") or pending.snapshot_id),
            candidates=tuple(
                ProtocolMetadataCandidate.model_validate(item)
                for item in raw.get("candidates") or []
            ),
            conflicts=tuple(
                ProtocolMetadataConflict.model_validate(item)
                for item in raw.get("conflicts") or []
            ),
        )
        try:
            confirmed = confirm_protocol_identity(
                extraction,
                pending,
                protocol_code=protocol_code,
                project_name=project_name,
                project_code=project_code,
                official_version=official_version,
                official_date=_date_value_from_input(
                    official_date_value,
                    official_date_precision,
                ),
                study_phase=study_phase,
                confirmed_by=actor,
                confirmed_at=self.now(),
                selected_candidate_ids=selected_candidate_ids,
            )
        except MetadataExtractionError as exc:
            raise ProtocolWorkbenchError(
                "IDENTITY_CONFIRM_INVALID",
                title="方案信息确认内容无效",
                detail=str(exc),
                recovery="请对照候选列表逐项确认；有冲突的字段必须明确选中一个候选值。",
            ) from exc

        phase_candidate_ids = [
            item.get("candidate_id", "")
            for item in merged.get("phase_candidates") or []
            if item.get("phase") == study_phase.value
        ]
        if not phase_candidate_ids:
            raise ProtocolWorkbenchError(
                "IDENTITY_CONFIRM_INVALID",
                title="研究期别确认内容无效",
                detail="所选研究期别没有对应的方案原文候选，不能建立可追溯的期别确认记录。",
                recovery="请重新选择页面列出的期别候选；如果没有合适候选，请返回并重新上传当前方案版本。",
            )

        phase_selection = StudyPhaseSelection(
            selection_id=merged.get("phase_selection_id") or uuid.uuid4().hex,
            snapshot_id=pending.snapshot_id,
            selected_phase=study_phase,
            candidate_ids=phase_candidate_ids,
            status=MetadataResolutionStatus.CONFIRMED,
            confirmed_by=actor,
            confirmed_at=self.now(),
        )
        checkpoint = {
            "identity_decision": confirmed.model_dump(mode="json"),
            "phase_selection": phase_selection.model_dump(mode="json"),
            "selected_phase": study_phase.value,
            "protocol_code": confirmed.protocol_code,
            "official_version": confirmed.official_version,
            "awaiting_user": None,
        }
        self._complete_user_step(job_id, STEP_AWAIT_IDENTITY, checkpoint)
        return self.get_session(job_id)

    def apply_manual_edit(
        self,
        job_id: str,
        *,
        draft: ProtocolDeconstructionDraft,
        expected_revision_id: str,
        actor: str,
    ) -> DraftDetailView:
        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        self._require_draft_session(merged)
        with self.session_factory() as session:
            with session.begin():
                service = ProtocolDraftService(session)
                revision = service.apply_manual_edit(
                    draft,
                    expected_revision_id=expected_revision_id,
                    actor=actor,
                    created_at=self.now(),
                )
                self._update_draft_checkpoint(session, job_id, revision)
        return self.get_draft_detail(job_id)

    def apply_feedback(
        self,
        job_id: str,
        *,
        draft: ProtocolDeconstructionDraft,
        expected_revision_id: str,
        feedback_kind: DraftFeedbackKind,
        feedback_note: str | None,
        actor: str,
    ) -> DraftDetailView:
        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        self._require_draft_session(merged)
        with self.session_factory() as session:
            with session.begin():
                service = ProtocolDraftService(session)
                revision = service.apply_feedback(
                    draft,
                    expected_revision_id=expected_revision_id,
                    feedback_kind=feedback_kind,
                    feedback_note=feedback_note,
                    actor=actor,
                    created_at=self.now(),
                )
                self._update_draft_checkpoint(session, job_id, revision)
        return self.get_draft_detail(job_id)

    def save_draft(
        self,
        job_id: str,
        *,
        expected_revision_id: str,
    ) -> DraftDetailView:
        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        draft_id = merged.get("draft_id")
        if not draft_id:
            raise ProtocolWorkbenchError(
                "DRAFT_NOT_READY",
                title="尚无已保存草稿",
                detail="解构草稿尚未生成，不能执行保存。",
                recovery="请等待草稿生成完成后再保存。",
            )
        with self.session_factory() as session:
            with session.begin():
                service = ProtocolDraftService(session)
                revision = service.save_draft(
                    draft_id=draft_id,
                    expected_revision_id=expected_revision_id,
                )
                self._update_draft_checkpoint(session, job_id, revision)
        return self.get_draft_detail(job_id)

    def cancel_draft(
        self,
        job_id: str,
        *,
        expected_revision_id: str,
    ) -> DraftDetailView:
        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        draft_id = merged.get("draft_id")
        if not draft_id:
            raise ProtocolWorkbenchError(
                "DRAFT_NOT_READY",
                title="尚无已保存草稿",
                detail="解构草稿尚未生成，不能取消。",
                recovery="若只是想放弃上传，可直接返回工作台首页。",
            )
        with self.session_factory() as session:
            with session.begin():
                service = ProtocolDraftService(session)
                revision = service.cancel_draft(
                    draft_id=draft_id,
                    expected_revision_id=expected_revision_id,
                )
                self._update_draft_checkpoint(session, job_id, revision)
        merged_after = self._merged_payload(job_id)
        if merged_after.get("awaiting_user") == "review":
            self._complete_user_step(
                job_id,
                STEP_AWAIT_REVIEW,
                {
                    "draft_revision_id": revision.revision_id,
                    "draft_status": revision.status.value,
                    "awaiting_user": None,
                },
            )
        return self.get_draft_detail(job_id)

    def publish_first_project(
        self,
        job_id: str,
        *,
        idempotency_key: str,
        actor: str,
    ) -> PublicationView:
        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        integrity = self.get_integrity(job_id)
        if not integrity.publishable:
            raise ProtocolWorkbenchError(
                "PUBLICATION_BLOCKED",
                title="草稿尚不能发布",
                detail=f"完整性检查仍有 {integrity.blocking_count} 项阻止发布的问题。",
                recovery="请先回到草稿逐项修正阻止发布的问题，再尝试发布。",
                context={"blocking_count": integrity.blocking_count},
            )
        source_input = self._load_source_input(merged)
        revision = self._load_draft_revision(merged)
        spans = self._load_source_spans(merged)
        publication = ProtocolPublicationService(self.session_factory, gate=self.gate)
        try:
            result = publication.publish(
                ProtocolPublicationRequest(
                    idempotency_key=idempotency_key,
                    draft_revision_id=revision.revision_id,
                    source_input=source_input,
                    source_spans=spans,
                    actor=actor,
                    published_at=self.now(),
                )
            )
        except PublicationGateError as exc:
            raise ProtocolWorkbenchError(
                "PUBLICATION_GATE_REJECTED",
                title="发布前完整性检查未通过",
                detail="草稿仍未达到可发布标准，系统没有写入任何正式规则。",
                recovery="请根据完整性问题列表修正草稿后重新保存，再尝试发布。",
            ) from exc
        except DuplicateFirstProjectError as exc:
            raise ProtocolWorkbenchError(
                "DUPLICATE_FIRST_PROJECT",
                title="已有同方案同期别的正式项目",
                detail=str(exc),
                recovery="请从“重新解构已有项目”入口继续，不要重复创建平行项目。",
            ) from exc
        except PublicationLineageError as exc:
            raise ProtocolWorkbenchError(
                "PUBLICATION_LINEAGE_REJECTED",
                title="方案谱系或期别不一致",
                detail=str(exc),
                recovery="请确认上传的是当前项目对应方案与研究期别，或另建独立项目。",
            ) from exc
        except ProtocolPublicationError as exc:
            raise ProtocolWorkbenchError(
                "PUBLICATION_FAILED",
                title="发布未能完成",
                detail=str(exc),
                recovery="请刷新草稿状态后重试；若仍失败，请联系维护人员并保留操作时间。",
            ) from exc

        if not result.replay:
            self._complete_user_step(
                job_id,
                STEP_PUBLISH,
                {
                    "project_id": result.project_id,
                    "protocol_version_id": result.protocol_version_id,
                    "rule_set_id": result.rule_set_id,
                    "awaiting_user": None,
                },
            )
        return PublicationView(
            job_id=job_id,
            project_id=result.project_id,
            protocol_version_id=result.protocol_version_id,
            rule_set_id=result.rule_set_id,
            rule_set_revision=result.rule_set_revision,
            replay=result.replay,
        )

    # ------------------------------------------------------------------ 测试/恢复辅助

    def seed_review_session(
        self,
        job_id: str,
        *,
        source_input: ProtocolDeconstructionInput,
        draft: ProtocolDeconstructionDraft,
        source_spans: dict[str, ProtocolSourceSpan],
        gate_result: ProtocolDeconstructionGateResult | None = None,
        actor: str = "测试用户",
        wait_at: str = STEP_AWAIT_REVIEW,
    ) -> None:
        """测试夹具：写入完整审阅态（不跑 OCR/Agent）。"""
        if wait_at not in (STEP_AWAIT_REVIEW, STEP_PUBLISH):
            raise ValueError(f"wait_at 必须是审阅或发布步骤，收到 {wait_at!r}")
        gate = gate_result or self.gate.evaluate(
            source_input,
            draft,
            source_spans=source_spans,
        )
        with self.session_factory() as session:
            with session.begin():
                draft_service = ProtocolDraftService(session)
                revision = draft_service.save_initial_draft(
                    draft, actor=actor, created_at=self.now()
                )
                repo = JobRepository(session)
                for step_id, payload in (
                    (STEP_EXTRACT, {"snapshot_id": source_input.extraction_snapshot_id}),
                    (
                        STEP_IDENTIFY,
                        {
                            "snapshot_id": source_input.extraction_snapshot_id,
                            "awaiting_user": "identity",
                            "identity_decision": source_input.identity_decision.model_dump(
                                mode="json"
                            ),
                            "phase_candidates": [
                                {
                                    "candidate_id": "phase-candidate-1",
                                    "phase": source_input.selected_phase.value,
                                }
                            ],
                            "metadata_candidates": [],
                            "metadata_conflicts": [],
                            "metadata_extraction": {
                                "snapshot_id": source_input.extraction_snapshot_id,
                                "candidates": [],
                                "conflicts": [],
                            },
                            "phase_selection_id": source_input.phase_selection.selection_id,
                        },
                    ),
                    (
                        STEP_AWAIT_IDENTITY,
                        {
                            "identity_decision": source_input.identity_decision.model_dump(
                                mode="json"
                            ),
                            "phase_selection": source_input.phase_selection.model_dump(
                                mode="json"
                            ),
                            "selected_phase": source_input.selected_phase.value,
                            "protocol_code": source_input.identity_decision.protocol_code,
                            "official_version": source_input.identity_decision.official_version,
                            "source_input": source_input.model_dump(mode="json"),
                            "source_spans": {
                                key: span.model_dump(mode="json")
                                for key, span in source_spans.items()
                            },
                            "awaiting_user": None,
                        },
                    ),
                    (
                        STEP_GENERATE,
                        {
                            "draft_id": draft.draft_id,
                            "draft_revision_id": revision.revision_id,
                        },
                    ),
                    (
                        STEP_INTEGRITY,
                        {
                            "gate_result": gate.model_dump(mode="json"),
                            "publishable": gate.publishable,
                        },
                    ),
                    (
                        STEP_AWAIT_REVIEW,
                        {
                            "draft_revision_id": revision.revision_id,
                            "draft_status": revision.status.value,
                            "awaiting_user": "review",
                        },
                    ),
                ):
                    repo.create_checkpoint(
                        checkpoint_id=uuid.uuid4().hex,
                        job_id=job_id,
                        step_id=step_id,
                        payload=payload,
                    )
                now = self.now()
                wait_index = _CHECKPOINT_STEP_ORDER.index(wait_at)
                completed_count = 0
                for step_id in _CHECKPOINT_STEP_ORDER:
                    step = session.get(JobStepRecord, {"job_id": job_id, "step_id": step_id})
                    if step is None:
                        continue
                    step_index = _CHECKPOINT_STEP_ORDER.index(step_id)
                    if step_index < wait_index:
                        step.state = "completed"
                        step.attempt = max(step.attempt, 1)
                        completed_count += 1
                    elif step_id == wait_at:
                        step.state = "waiting_user"
                        step.attempt = max(step.attempt, 1)
                    else:
                        step.state = "queued"
                    step.error_code = None
                    step.error_classification = None
                    step.retry_not_before = None
                    step.updated_at = now
                job = session.get(JobRecord, job_id)
                if job is not None:
                    job.state = "waiting_user"
                    job.progress_completed = completed_count
                    job.lease_owner = None
                    job.lease_expires_at = None
                    job.updated_at = now

    # ------------------------------------------------------------------ 内部

    def _require_protocol_job(self, job_id: str) -> None:
        snapshot = self.jobs.get_status(job_id)
        if snapshot.job_type != PROTOCOL_DECONSTRUCTION_JOB_TYPE:
            raise ProtocolWorkbenchError(
                "NOT_PROTOCOL_JOB",
                title="不是方案解构任务",
                detail="该任务编号不属于方案解构工作台。",
                recovery="请返回方案工作台重新选择任务。",
            )

    def _merged_payload(self, job_id: str) -> dict[str, Any]:
        with self.session_factory() as session:
            store = JobStore(session, now=self.now)
            try:
                job = store.get_job(job_id)
            except JobNotFoundError as exc:
                raise exc
            from app.storage.codecs import verify_payload_sha256

            merged = dict(verify_payload_sha256(job.payload_json, job.payload_sha256))
            for step_id in _CHECKPOINT_STEP_ORDER:
                checkpoint = store.get_last_checkpoint(job_id, step_id)
                if checkpoint is None:
                    continue
                _, payload = checkpoint
                merged.update(
                    {key: value for key, value in payload.items() if key != "attempt"}
                )
            return merged

    def _complete_user_step(
        self,
        job_id: str,
        step_id: str,
        checkpoint_payload: dict[str, Any],
    ) -> None:
        try:
            with self.session_factory() as session:
                with session.begin():
                    store = JobStore(session, now=self.now)
                    store.complete_user_step(
                        job_id,
                        step_id,
                        checkpoint_payload=checkpoint_payload,
                    )
        except JobStateConflictError as exc:
            raise ProtocolWorkbenchError(
                "STEP_STATE_CONFLICT",
                title="任务步骤状态不允许该操作",
                detail="当前步骤不在等待确认状态，不能重复提交。",
                recovery="请刷新任务状态后重试。",
                context={"current_state": exc.current_state},
            ) from exc

    def _force_complete_step(
        self,
        store: JobStore,
        job_id: str,
        step_id: str,
        checkpoint_payload: dict[str, Any],
    ) -> None:
        lease = store.claim_job(job_id, self.WORKER_ID)
        if lease is None:
            raise ProtocolWorkbenchError(
                "JOB_CLAIM_FAILED",
                title="测试夹具无法写入",
                detail="任务租约不可用。",
                recovery="请检查任务状态。",
            )
        step = store.list_steps(job_id)
        by_id = {item.step_id: item for item in step}
        if by_id[step_id].state == "queued":
            store.start_step(lease, step_id)
        store.complete_step(lease, step_id, checkpoint_payload=checkpoint_payload)

    def _update_draft_checkpoint(
        self,
        session: Session,
        job_id: str,
        revision: ProtocolDraftRevision,
    ) -> None:
        merged = self._merged_payload(job_id)
        source_input = self._load_source_input(merged)
        spans = self._load_source_spans(merged)
        previous = None
        if revision.previous_revision_id:
            repo = ProtocolDraftRevisionRepository(session)
            try:
                previous = repo.get(revision.previous_revision_id).content
            except NotFoundError:
                previous = None
        gate = self.gate.evaluate(
            source_input,
            revision.content,
            source_spans=spans,
            previous_draft=previous,
            declared_diff=revision.diff if revision.revision_number > 1 else None,
        )
        repo = JobRepository(session)
        for step_id, payload in (
            (
                STEP_GENERATE,
                {
                    "draft_id": revision.draft_id,
                    "draft_revision_id": revision.revision_id,
                    "draft_status": revision.status.value,
                },
            ),
            (
                STEP_INTEGRITY,
                {
                    "gate_result": gate.model_dump(mode="json"),
                    "publishable": gate.publishable,
                },
            ),
            (
                STEP_AWAIT_REVIEW,
                {
                    "draft_revision_id": revision.revision_id,
                    "draft_status": revision.status.value,
                    "awaiting_user": "review",
                },
            ),
        ):
            repo.create_checkpoint(
                checkpoint_id=uuid.uuid4().hex,
                job_id=job_id,
                step_id=step_id,
                payload=payload,
            )

    def _load_identity_decision(self, merged: dict[str, Any]) -> ProtocolIdentityDecision:
        raw = merged.get("identity_decision")
        if not raw:
            raise ProtocolWorkbenchError(
                "IDENTITY_NOT_READY",
                title="身份决策尚未生成",
                detail="系统还没有可供确认的方案信息。",
                recovery="请等待识别步骤完成。",
            )
        return ProtocolIdentityDecision.model_validate(raw)

    def _load_source_input(self, merged: dict[str, Any]) -> ProtocolDeconstructionInput:
        raw = merged.get("source_input")
        if not raw:
            raise ProtocolWorkbenchError(
                "SOURCE_INPUT_NOT_READY",
                title="解构输入尚未就绪",
                detail="方案信息与研究期别核对尚未完成，或输入资料尚未写入。",
                recovery="请先完成方案信息与研究期别确认。",
            )
        return ProtocolDeconstructionInput.model_validate(raw)

    def _load_source_spans(
        self, merged: dict[str, Any]
    ) -> dict[str, ProtocolSourceSpan]:
        raw = merged.get("source_spans") or {}
        return {
            key: ProtocolSourceSpan.model_validate(value) for key, value in raw.items()
        }

    def _load_draft_revision(self, merged: dict[str, Any]) -> ProtocolDraftRevision:
        revision_id = merged.get("draft_revision_id")
        if not revision_id:
            raise ProtocolWorkbenchError(
                "DRAFT_NOT_READY",
                title="草稿尚未生成",
                detail="方案解构草稿还未写入持久存储。",
                recovery="请等待解构完成或刷新任务状态。",
            )
        with self.session_factory() as session:
            repo = ProtocolDraftRevisionRepository(session)
            try:
                return repo.get(revision_id)
            except NotFoundError as exc:
                raise ProtocolWorkbenchError(
                    "DRAFT_NOT_FOUND",
                    title="找不到草稿版本",
                    detail="任务引用的草稿 revision 不存在或已被清理。",
                    recovery="请刷新页面；若仍异常，请联系维护人员。",
                ) from exc

    def _load_previous_draft(
        self, merged: dict[str, Any]
    ) -> ProtocolDeconstructionDraft | None:
        revision = self._load_draft_revision(merged)
        if not revision.previous_revision_id:
            return None
        with self.session_factory() as session:
            repo = ProtocolDraftRevisionRepository(session)
            try:
                previous = repo.get(revision.previous_revision_id)
            except NotFoundError:
                return None
            return previous.content

    def _load_declared_diff(self, merged: dict[str, Any]):
        revision = self._load_draft_revision(merged)
        return revision.diff if revision.revision_number > 1 else None

    def _require_draft_session(self, merged: dict[str, Any]) -> None:
        if not merged.get("draft_revision_id"):
            raise ProtocolWorkbenchError(
                "DRAFT_NOT_READY",
                title="草稿尚未生成",
                detail="当前还不能编辑方案解构草稿。",
                recovery="请等待草稿生成完成。",
            )

    def _draft_summary(self, merged: dict[str, Any]) -> dict[str, Any]:
        revision_id = merged.get("draft_revision_id")
        if not revision_id:
            return {}
        try:
            revision = self._load_draft_revision(merged)
        except ProtocolWorkbenchError:
            return {}
        return {
            "revision_number": revision.revision_number,
            "status": revision.status.value,
        }

    def _gate_summary(self, merged: dict[str, Any]) -> dict[str, Any]:
        cached = merged.get("gate_result")
        if not cached:
            return {"publishable": merged.get("publishable")}
        result = ProtocolDeconstructionGateResult.model_validate(cached)
        blocking = sum(
            1
            for check in result.checks
            for issue in check.issues
            if issue.level == "阻止发布"
        )
        return {"publishable": result.publishable, "blocking_count": blocking}

    def _recovery_point(self, job_id: str) -> tuple[str | None, str | None]:
        with self.session_factory() as session:
            store = JobStore(session, now=self.now)
            for step_id in reversed(_CHECKPOINT_STEP_ORDER):
                checkpoint = store.get_last_checkpoint(job_id, step_id)
                if checkpoint is not None:
                    return step_id, checkpoint[0]
        return None, None

    def _next_action(
        self,
        merged: dict[str, Any],
        gate_summary: dict[str, Any],
        *,
        awaiting_user: str | None = None,
    ) -> str:
        awaiting = awaiting_user or merged.get("awaiting_user")
        if awaiting == "identity":
            return "请核对方案编号、版本、日期与研究期别后确认。"
        if awaiting == "review":
            if gate_summary.get("publishable"):
                return "草稿已通过完整性检查，确认无误后可发布正式项目。"
            blocking = gate_summary.get("blocking_count")
            if blocking:
                return f"草稿有 {blocking} 项阻止发布的问题，请先逐项核对修正。"
            return "请审阅草稿与来源定位，修正需要核对的项目。"
        if awaiting == "publish":
            return "草稿已确认，请确认后发布正式项目。"
        if not merged.get("snapshot_id"):
            return "系统正在读取方案结构与基本信息，请稍候。"
        if not merged.get("draft_revision_id"):
            return "等待生成方案解构草稿。"
        return "请刷新查看最新进展。"

    @staticmethod
    def _job_state_label(state: str) -> str:
        from app.api.v2.vocabulary import JOB_STATE_LABELS

        return JOB_STATE_LABELS.get(state, state)

    def _integrity_view(
        self, job_id: str, result: ProtocolDeconstructionGateResult
    ) -> IntegrityView:
        issues: list[dict[str, Any]] = []
        checks: list[dict[str, Any]] = []
        blocking = review = reminder = 0
        for check in result.checks:
            checks.append(
                {
                    "check_name": check.check_name,
                    "passed": check.passed,
                    "issue_count": len(check.issues),
                }
            )
            for issue in check.issues:
                issues.append(self._issue_dto(issue))
                if issue.level == "阻止发布":
                    blocking += 1
                elif issue.level == "需要核对":
                    review += 1
                else:
                    reminder += 1
        return IntegrityView(
            job_id=job_id,
            publishable=result.publishable,
            blocking_count=blocking,
            review_count=review,
            reminder_count=reminder,
            checks=checks,
            issues=issues,
        )

    @staticmethod
    def _issue_dto(issue: ProtocolGateIssue) -> dict[str, Any]:
        return {
            "issue_code": issue.issue_code,
            "check_name": issue.check_name,
            "level": issue.level,
            "problem": issue.problem,
            "impact": issue.impact,
            "next_action": issue.next_action,
            "affected_refs": issue.affected_refs,
            "repair_scope": issue.repair_scope,
        }


__all__ = [
    "PROTOCOL_DECONSTRUCTION_JOB_TYPE",
    "PROTOCOL_DECONSTRUCTION_STEPS",
    "ProtocolSessionView",
    "ProtocolWorkbenchError",
    "ProtocolWorkbenchService",
    "StartDeconstructionResult",
]
