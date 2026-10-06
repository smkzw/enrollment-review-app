"""方案解构工作台用例编排（Phase 3 切片 5）。

HTTP 层只做协议转换；本服务复用持久 Job、Slice 1–4 领域服务与仓储，
不在 API 路由内做临床判断。上传登记原始方案并创建 ``protocol_deconstruction``
任务；身份/期别确认、草稿 revision、完整性投影与首次发布均通过 Job 检查点
与既有服务完成，不另建平行存储。
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from app.llm.mtplx_model_lifecycle import local_deployment_job_fields

from app.domain.contracts.agent_io import (
    ProtocolDeconstructionDraft,
    ProtocolDeconstructionInput,
    ProtocolSemanticDeconstructionCandidate,
)
from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import DatePrecision, MetadataResolutionStatus, StudyPhase
from app.domain.contracts.protocol_drafts import DraftFeedbackKind, ProtocolDraftRevision
from app.evidence.artifacts import ArtifactStore
from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
from app.domain.contracts.rules import RestrictedRuleComponent, iter_atomic_predicates
from app.domain.contracts.protocol_metadata import (
    InterpretationSource,
    ProtocolIdentityDecision,
    StudyPhaseSelection,
)
from app.protocols.deconstruction_gate import (
    DECONSTRUCTION_GATE_VERSION,
    ProtocolDeconstructionGate,
    ProtocolDeconstructionGateResult,
    ProtocolDraftDiffDeclaration,
    ProtocolGateIssue,
    _localized_open_list_exception_requires_exclusivity,
    _source_proves_unsupported_member_frequency,
    _substantive_obligation_segments,
)
from app.protocols.ingestion import (
    SourceIngestionError,
    compute_sha256,
    register_source_artifact,
)
from app.protocols.metadata import MetadataExtractionError, confirm_protocol_identity
from app.services.job_service import JobService, StepSpec
from app.services.protocol_draft_service import (
    FormalBaselineError,
    ProtocolDraftService,
    compute_draft_diff,
    resolve_formal_baseline_revision,
)
from app.services.protocol_publication_service import (
    DuplicateFirstProjectError,
    ProtocolPublicationError,
    ProtocolPublicationRequest,
    ProtocolPublicationService,
    PublicationGateError,
    PublicationLineageError,
)
from app.storage.codecs import utc_now
from app.storage.idempotency import (
    IdempotencyConflict,
    IdempotencyRepository,
    request_hash,
)
from app.storage.config import DataPaths
from app.storage.models import JobRecord, JobStepRecord
from app.storage.repositories import (
    JobRepository,
    NotFoundError,
    ProjectRepository,
    ProtocolDraftRevisionRepository,
    count_rule_set_rules,
    get_project_row,
    list_projects_with_revision,
    list_rule_set_revisions,
)
from app.workflow.errors import JobNotFoundError, JobStateConflictError
from app.workflow.jobstore import JobStore

logger = logging.getLogger(__name__)

PROTOCOL_DECONSTRUCTION_JOB_TYPE = "protocol_deconstruction"

STEP_REGISTER = "register_file"
STEP_EXTRACT = "extract_structure"
STEP_RENDER = "render_and_align"
STEP_IDENTIFY = "identify_identity_phase"
STEP_AWAIT_IDENTITY = "await_identity_confirm"
STEP_FREEZE = "freeze_deconstruction_input"
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
    StepSpec(
        STEP_FREEZE,
        "冻结规则与流程目录",
        depends_on=(STEP_AWAIT_IDENTITY,),
    ),
    # 语义生成依赖远程模型，偶发空正文或单批结构无效不应
    # 立即把整个任务收口为终止失败。已完成的提取、渲染和期别确认
    # 由检查点保留，自动重试只重跑这一步。
    StepSpec(
        STEP_GENERATE,
        "生成草稿",
        max_attempts=2,
        retryable=True,
        depends_on=(STEP_FREEZE,),
    ),
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
FeedbackReviser = Callable[
    [
        ProtocolDeconstructionInput,
        ProtocolDeconstructionDraft,
        str,
        str,
    ],
    ProtocolDeconstructionDraft,
]


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
class OfficialProjectView:
    """正式项目投影（重新解构选择与当前正式版本读取）。"""

    project_id: str
    project_code: str
    project_name: str
    study_phase: str
    study_phase_label: str
    protocol_code: str
    official_version: str
    official_date_value: str | None
    official_date_precision: str | None
    rule_set_id: str
    rule_set_revision: int


@dataclass(frozen=True)
class ProjectVersionView:
    """单个正式（已发布）规则版本：revision、方案版本与规则条数。"""

    rule_set_revision: int
    protocol_version_id: str
    official_version: str
    official_date_value: str | None
    official_date_precision: str | None
    sha256: str
    rule_count: int
    published_at: str


@dataclass(frozen=True)
class ProjectOfficialVersionView:
    """项目的正式版本投影：当前正式版本 + 全部已发布规则 revision。"""

    project: OfficialProjectView
    versions: list[ProjectVersionView]
    publication_count: int


@dataclass(frozen=True)
class DraftComparisonSideView:
    """并列差异中的一侧：正式基线或新草稿。"""

    revision_id: str
    draft_id: str
    protocol_version_id: str
    official_version: str | None
    revision_number: int | None
    status: str | None
    rule_count: int
    workflow_stage_count: int
    is_formal_baseline: bool
    content: dict[str, Any]
    source_refs: list[str]


@dataclass(frozen=True)
class DraftComparisonView:
    """当前正式草稿与新草稿的并列比较投影（八类差异 + 来源定位信息）。"""

    job_id: str
    baseline: DraftComparisonSideView
    candidate: DraftComparisonSideView
    diff: dict[str, Any]
    source_bound: bool


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
    # 重新解构：目标正式项目投影（session_kind="re_deconstruction" 时有值）。
    target_project_id: str | None
    target_project_name: str | None
    target_project_code: str | None
    target_protocol_code: str | None
    target_study_phase: str | None
    target_study_phase_label: str | None
    target_official_version: str | None
    target_rule_set_revision: int | None


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


def _official_date_text(value: DateValue | None) -> str | None:
    """按确认精度投影正式日期文本（YYYY / YYYY-MM / YYYY-MM-DD）。"""
    if value is None or value.value is None:
        return None
    if value.precision == DatePrecision.YEAR:
        return f"{value.value.year:04d}"
    if value.precision == DatePrecision.MONTH:
        return f"{value.value.year:04d}-{value.value.month:02d}"
    return value.value.isoformat()


def _official_project_view(project, rule_set_revision: int) -> OfficialProjectView:
    version = project.protocol_version
    return OfficialProjectView(
        project_id=project.project_id,
        project_code=project.project_code,
        project_name=project.project_name,
        study_phase=project.study_phase.value,
        study_phase_label=_study_phase_label(project.study_phase.value),
        protocol_code=version.protocol_code,
        official_version=version.official_version,
        official_date_value=_official_date_text(version.official_date),
        official_date_precision=(
            version.official_date.precision.value if version.official_date else None
        ),
        rule_set_id=project.rule_set_id,
        rule_set_revision=rule_set_revision,
    )


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
        feedback_reviser: FeedbackReviser | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.data_paths = data_paths
        self.now = now
        self.gate = gate or ProtocolDeconstructionGate(artifact_reader=ArtifactStore(data_paths).read)
        self._uses_default_feedback_reviser = feedback_reviser is None
        self.feedback_reviser = feedback_reviser or self._revise_feedback_with_model
        self.jobs = JobService(session_factory, now=now)

    @staticmethod
    def _revise_feedback_with_model(
        source_input: ProtocolDeconstructionInput,
        current_draft: ProtocolDeconstructionDraft,
        target_rule_code: str,
        feedback_note: str,
        target_component_id: str | None = None,
        joint_source_repair: bool = False,
        preserve_review_items: bool = False,
        budget_store: Any = None,
        scope_review_store: ArtifactStore | None = None,
    ) -> ProtocolDeconstructionDraft:
        from app.agents.protocol_deconstructor import (
            ProtocolAgentCallError,
            revise_protocol_draft_from_feedback,
        )
        from app.agents.protocol_semantic_model_router import (
            GRADE_SHORT,
            NON_REPLAYABLE_ROUTE_ERRORS,
            build_transport_for_candidate,
            candidate_availability_error,
            resolve_route_mode,
            select_protocol_semantic_route_candidates,
        )
        from app.llm.logical_call_budget import LogicalCallBudget

        run_budget = None
        if budget_store is not None:
            run_id = hashlib.sha256(json.dumps({
                "source": source_input.protocol_file_sha256,
                "snapshot": source_input.extraction_snapshot_id,
                "role": "official-run-budget/v1",
            }, sort_keys=True).encode()).hexdigest()
            try:
                saved = budget_store.load_call_budget(run_id)
                if saved is None:
                    raise ProtocolAgentCallError(
                        "protocol-feedback-budget", "原方案读取额度记录不存在，未再次调用模型",
                        error_code="BUDGET_RECORD_MISSING",
                    )
                run_budget = LogicalCallBudget(
                    run_id, max_requests=saved["max_requests"],
                    max_output_tokens=saved["max_output_tokens"], saved=saved,
                    contract_sha256=saved["contract_sha256"], persist=budget_store.store_call_budget,
                )
            except (ValueError, TypeError, KeyError, OSError) as exc:
                raise ProtocolAgentCallError(
                    "protocol-feedback-budget", "原方案读取额度记录无法核实，未再次调用模型",
                    error_code="BUDGET_RECORD_INVALID",
                ) from exc

        # New provider sessions share persisted task/run allowances, not new budgets.
        candidates = select_protocol_semantic_route_candidates(
            GRADE_SHORT,
            route_mode=resolve_route_mode(),
        )
        last_error: Exception | None = None
        for candidate in candidates:
            skip_reason = candidate_availability_error(candidate)
            if skip_reason is not None:
                last_error = ValueError(skip_reason)
                continue
            try:
                transport = build_transport_for_candidate(candidate)
            except ValueError as exc:
                last_error = exc
                continue
            try:
                if budget_store is not None:
                    transport.bind_call_budget_store(budget_store)
                    transport.share_run_budget(run_budget)
                if scope_review_store is not None:
                    from app.agents.protocol_deconstructor import _configure_transport_output_scope
                    from app.services.protocol_scope_review_service import review_official_source_scope
                    _configure_transport_output_scope(transport, source_input, [target_rule_code])
                    return review_official_source_scope(
                        source_input, current_draft, official_code=target_rule_code,
                        transport=transport, store=scope_review_store,
                    )
                return revise_protocol_draft_from_feedback(
                    source_input,
                    current_draft,
                    target_rule_code=target_rule_code,
                    target_component_id=target_component_id,
                    feedback_note=feedback_note,
                    transport=transport,
                    joint_source_repair=joint_source_repair,
                    preserve_review_items=preserve_review_items,
                )
            except ProtocolAgentCallError as exc:
                if exc.error_code in NON_REPLAYABLE_ROUTE_ERRORS:
                    raise
                last_error = exc
                continue
            finally:
                close = getattr(getattr(transport, "_client", None), "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        logger.warning("方案修订连接关闭未完成", exc_info=True)
        if last_error is not None:
            raise last_error
        raise ProtocolAgentCallError(
            "protocol-feedback-route-exhausted",
            "短提示反馈修订路由候选均已显式跳过或失败，未产出可用修订。",
        )

    # ------------------------------------------------------------------ 上传

    @staticmethod
    def _require_supported_protocol_file(upload_path: Path, original_name: str) -> None:
        suffix = Path(original_name or upload_path.name).suffix.lower()
        if suffix == ".docx":
            return
        raise ProtocolWorkbenchError(
            "UNSUPPORTED_PROTOCOL_FILE",
            title="当前文件格式不能用于方案解构",
            detail="现阶段的结构提取和原文定位支持 DOCX 格式的正式研究方案；方案 PDF 上传入口已下线。",
            recovery="请以 DOCX 重新上传正式方案。",
        )

    def start_first_deconstruction(
        self,
        *,
        upload_path: Path,
        original_name: str,
        idempotency_key: str,
        actor: str = "用户",
    ) -> StartDeconstructionResult:
        display_name = original_name or upload_path.name
        self._require_supported_protocol_file(upload_path, display_name)
        try:
            sha256 = compute_sha256(upload_path)
        except SourceIngestionError as exc:
            raise ProtocolWorkbenchError(
                "SOURCE_INGESTION_FAILED",
                title="方案文件无法登记",
                detail=str(exc),
                recovery="请确认方案文件完整可读后重新上传。",
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
                recovery="请确认方案文件完整可读后重新上传。",
            ) from exc

        # 将登记结果写入 Job payload，保证 runner 即使在 API 写入首个检查点前
        # 抢到租约，也能从持久任务输入恢复 register_file 步骤。
        payload = {
            "session_kind": "first_deconstruction",
            **local_deployment_job_fields(),
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

    def start_saved_candidate_recovery(
        self,
        *,
        source_job_id: str,
        candidate_ref: str,
        candidate_origin: Literal["operator_imported_unpublished"],
        expected_freeze_sha256: str,
        idempotency_key: str,
        actor: str = "用户",
    ) -> StartDeconstructionResult:
        """导入保留提案供重新核对，不追认其为原失败任务的直接输出。"""
        from app.services.protocol_saved_draft_recovery import SavedDraftRecoveryError, load_saved_draft_recovery
        from app.evidence.artifacts import ArtifactStoreError
        from app.storage.codecs import PersistedContractInvalid

        if candidate_origin != "operator_imported_unpublished":
            raise ValueError("导入候选必须明确标为外部保留的未发布提案，不冒称原任务的模型输出。")
        source_steps = _CHECKPOINT_STEP_ORDER[:_CHECKPOINT_STEP_ORDER.index(STEP_GENERATE)]
        with self.session_factory() as session, session.begin():
            try:
                source, draft = load_saved_draft_recovery(
                    JobStore(session, now=self.now), self.data_paths,
                    source_job_id=source_job_id, candidate_ref=candidate_ref,
                    expected_freeze_sha256=expected_freeze_sha256, source_steps=source_steps,
                )
            except (SavedDraftRecoveryError, ArtifactStoreError, PersistedContractInvalid, ValueError) as exc:
                raise ProtocolWorkbenchError(
                    "SAVED_DRAFT_RECOVERY_INVALID", title="保存提案无法恢复",
                    detail=str(exc), recovery="请核对原任务、原件与保存提案，不要覆盖原记录。",
                ) from exc
            result = self.jobs.create_job_in_session(
                session, idempotency_key=idempotency_key,
                job_type=PROTOCOL_DECONSTRUCTION_JOB_TYPE,
                payload={
                    "session_kind": "first_deconstruction",
                    **local_deployment_job_fields(),
                    "source_artifact_id": source["source_artifact_id"],
                    "file_name": source["file_name"],
                    "actor": actor,
                    "awaiting_user": None,
                    "saved_candidate_recovery": {
                        "version": "saved-draft-recovery/v2",
                        "source_job_id": source_job_id,
                        "candidate_ref": candidate_ref,
                        "candidate_origin": candidate_origin,
                        "expected_freeze_sha256": expected_freeze_sha256,
                    },
                },
                steps=[
                    StepSpec(STEP_FREEZE, "复核已存来源与目录"),
                    StepSpec(STEP_GENERATE, "保存恢复提案", depends_on=(STEP_FREEZE,)),
                    StepSpec(STEP_INTEGRITY, "完整性检查", depends_on=(STEP_GENERATE,)),
                    StepSpec(STEP_AWAIT_REVIEW, "等待审阅", depends_on=(STEP_INTEGRITY,), waiting_user_kind="review"),
                    StepSpec(STEP_PUBLISH, "发布", depends_on=(STEP_AWAIT_REVIEW,), waiting_user_kind="publish"),
                ],
            )
            if result.created and ProtocolDraftRevisionRepository(session).find_by_generation_scope(
                    project_id=draft.project_id, protocol_version_id=draft.protocol_version_id):
                raise ProtocolWorkbenchError(
                    "SAVED_DRAFT_ALREADY_REGISTERED", title="该来源已有正式保存草稿",
                    detail="不能为同一草稿另建首稿；原有草稿和本次请求均未被覆盖。",
                    recovery="请在现有草稿中继续核对或修订。",
                )
        return StartDeconstructionResult(
            job_id=result.job_id, state=result.state, created=result.created,
            source_artifact_id=source["source_artifact_id"], file_name=source["file_name"],
        )

    def start_re_deconstruction(
        self,
        *,
        upload_path: Path,
        original_name: str,
        project_id: str,
        idempotency_key: str,
        actor: str = "用户",
    ) -> StartDeconstructionResult:
        """重新解构：目标项目必须在持久任务中保存，上传的新版方案在同一项目中
        生成新的不可变规则版本。目标项目不存在时直接拒绝，不创建任务。"""
        display_name = original_name or upload_path.name
        self._require_supported_protocol_file(upload_path, display_name)
        try:
            sha256 = compute_sha256(upload_path)
        except SourceIngestionError as exc:
            raise ProtocolWorkbenchError(
                "SOURCE_INGESTION_FAILED",
                title="方案文件无法登记",
                detail=str(exc),
                recovery="请确认方案文件完整可读后重新上传。",
            ) from exc

        with self.session_factory() as session:
            row = get_project_row(session, project_id)
            if row is None:
                raise ProtocolWorkbenchError(
                    "PROJECT_NOT_FOUND",
                    title="找不到正式项目",
                    detail=f"项目 {project_id} 不存在正式发布记录，无法发起重新解构。",
                    recovery="请返回项目列表重新选择，或先完成首次解构与发布。",
                    context={"project_id": project_id},
                )
            target_project, target_rule_set_revision = row

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
                recovery="请确认方案文件完整可读后重新上传。",
            ) from exc

        target_version = target_project.protocol_version
        payload = {
            "session_kind": "re_deconstruction",
            **local_deployment_job_fields(),
            "file_name": display_name,
            "sha256": artifact.sha256,
            "mime_type": artifact.mime_type,
            "size_bytes": artifact.size_bytes,
            "storage_ref": artifact.storage_ref,
            "source_artifact_id": artifact.source_artifact_id,
            "actor": actor,
            "awaiting_user": None,
            # 目标项目持久保存：发布编排与待命视图据此加载谱系/期别并进行校验。
            "target_project_id": target_project.project_id,
            "target_project_code": target_project.project_code,
            "target_project_name": target_project.project_name,
            "target_protocol_code": target_version.protocol_code,
            "target_study_phase": target_project.study_phase.value,
            "target_official_version": target_version.official_version,
            "target_rule_set_revision": target_rule_set_revision,
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

    def start_feedback_re_deconstruction(
        self,
        *,
        project_id: str,
        idempotency_key: str,
        interpretation_sources: Sequence[InterpretationSource] = (),
        actor: str = "用户",
    ) -> StartDeconstructionResult:
        """无需上传新版文件，复制当前正式草稿为候选稿并进入反馈修订。

        该路径仍必须恢复正式版本发布时使用的方案输入与来源定位；若历史任务已
        缺失这些权威上下文则失败关闭，不能用只有规则正文的无来源副本继续发布。
        """
        with self.session_factory() as session:
            row = get_project_row(session, project_id)
            if row is None:
                raise ProtocolWorkbenchError(
                    "PROJECT_NOT_FOUND",
                    title="找不到正式项目",
                    detail=f"项目 {project_id} 不存在正式发布记录，无法发起反馈修订。",
                    recovery="请返回项目列表重新选择，或先完成首次解构与发布。",
                    context={"project_id": project_id},
                )
            target_project, target_rule_set_revision = row
            try:
                baseline = resolve_formal_baseline_revision(
                    session=session,
                    project_id=project_id,
                )
            except FormalBaselineError as exc:
                raise ProtocolWorkbenchError(
                    exc.code,
                    title="无法读取当前正式草稿",
                    detail=str(exc),
                    recovery=exc.recovery,
                ) from exc

        target_version = target_project.protocol_version
        source_context = self._source_context_for_revision(baseline.revision_id)
        if source_context is None:
            raise ProtocolWorkbenchError(
                "FORMAL_SOURCE_CONTEXT_MISSING",
                title="当前正式版本缺少可复用的来源定位",
                detail="系统找到了正式规则，但没有找到该版本发布时的方案输入和原文定位，不能直接生成反馈修订稿。",
                recovery="请改用“上传新版方案”并重新选择当前正式方案文件；系统会重新建立来源定位后再比较。",
                context={"project_id": project_id},
            )

        feedback_identity = hashlib.sha256(
            f"{project_id}:{idempotency_key}".encode("utf-8")
        ).hexdigest()
        # 草稿与语义候选的往返合同固定为 ``draft:<candidate_id>``。
        # 保留 feedback 命名空间，但必须放在 draft: 之后，否则局部修订水合时
        # 会生成第二个草稿身份并触发错误的并发冲突。
        new_draft_id = f"draft:feedback:{feedback_identity}"
        new_protocol_version_id = f"protocol-version-feedback:{feedback_identity}"
        previous_source_input = ProtocolDeconstructionInput.model_validate(
            source_context["source_input"]
        )
        source_candidates = {
            item.interpretation_source_id: item
            for item in previous_source_input.interpretation_sources
        }
        for item in interpretation_sources:
            if item.protocol_version_id != target_version.protocol_version_id:
                raise ProtocolWorkbenchError(
                    "INTERPRETATION_VERSION_MISMATCH",
                    title="解释材料不属于当前方案版本",
                    detail="解释材料必须针对当前正式方案版本登记，不能带入其他版本或其他项目。",
                    recovery="请返回当前项目版本后重新添加解释材料。",
                )
            existing = source_candidates.get(item.interpretation_source_id)
            if existing is not None and existing != item:
                raise ProtocolWorkbenchError(
                    "INTERPRETATION_SOURCE_CONFLICT",
                    title="解释材料身份重复",
                    detail="同一解释材料编号对应了不同内容，系统未创建修订任务。",
                    recovery="请保留一份来源明确、内容一致的解释材料后重试。",
                )
            source_candidates[item.interpretation_source_id] = item
        if any(
            item.protocol_version_id != target_version.protocol_version_id
            for item in source_candidates.values()
        ):
            raise ProtocolWorkbenchError(
                "INTERPRETATION_VERSION_MISMATCH",
                title="解释材料不属于当前方案版本",
                detail="当前正式版本保存的解释材料与方案版本不一致，系统未创建修订任务。",
                recovery="请重新核对当前项目的解释材料来源后再试。",
            )
        rebound_sources = []
        for item in source_candidates.values():
            bound_id = "interpretation:" + hashlib.sha256(
                f"{new_protocol_version_id}:{item.interpretation_source_id}".encode(
                    "utf-8"
                )
            ).hexdigest()[:32]
            rebound_sources.append(
                InterpretationSource.model_validate(
                    item.model_dump(mode="json")
                    | {
                        "interpretation_source_id": bound_id,
                        "protocol_version_id": new_protocol_version_id,
                    }
                )
            )
        source_input = ProtocolDeconstructionInput.model_validate(
            previous_source_input.model_dump(mode="json")
            | {
                "protocol_version_id": new_protocol_version_id,
                "interpretation_source_ids": [
                    item.interpretation_source_id for item in rebound_sources
                ],
                "interpretation_sources": [
                    item.model_dump(mode="json") for item in rebound_sources
                ],
            }
        )
        source_input_payload = source_input.model_dump(mode="json")
        candidate = ProtocolDeconstructionDraft.model_validate(
            baseline.content.model_dump(mode="json")
            | {
                "draft_id": new_draft_id,
                "draft_revision": 1,
                "previous_draft_id": None,
                "project_id": target_project.project_id,
                "protocol_version_id": new_protocol_version_id,
            }
        )
        file_name = str(source_context.get("file_name") or "当前正式方案")
        payload = {
            "session_kind": "re_deconstruction",
            "re_deconstruction_origin": "formal_feedback",
            **local_deployment_job_fields(),
            "file_name": file_name,
            "source_artifact_id": source_context.get("source_artifact_id"),
            "actor": actor,
            "awaiting_user": "review",
            "source_input": source_input_payload,
            "source_spans": source_context["source_spans"],
            "snapshot_id": source_context.get("snapshot_id"),
            "selected_phase": target_project.study_phase.value,
            "protocol_code": target_version.protocol_code,
            "official_version": target_version.official_version,
            "target_project_id": target_project.project_id,
            "target_project_code": target_project.project_code,
            "target_project_name": target_project.project_name,
            "target_protocol_code": target_version.protocol_code,
            "target_study_phase": target_project.study_phase.value,
            "target_official_version": target_version.official_version,
            "target_rule_set_revision": target_rule_set_revision,
        }
        source_spans = {
            key: ProtocolSourceSpan.model_validate(value)
            for key, value in source_context["source_spans"].items()
        }
        with self.session_factory() as session:
            with session.begin():
                # 任务、初稿和全部已完成检查点一次提交。后台 runner 在提交前
                # 看不到 queued 任务，因此不能抢先取得租约并破坏同步初始化。
                result = self.jobs.create_job_in_session(
                    session,
                    idempotency_key=idempotency_key,
                    job_type=PROTOCOL_DECONSTRUCTION_JOB_TYPE,
                    payload=payload,
                    steps=list(PROTOCOL_DECONSTRUCTION_STEPS),
                )
                if not result.created:
                    return StartDeconstructionResult(
                        job_id=result.job_id,
                        state=result.state,
                        created=False,
                        source_artifact_id=str(
                            source_context.get("source_artifact_id") or ""
                        ),
                        file_name=file_name,
                    )
                revision = ProtocolDraftService(session).save_initial_draft(
                    candidate,
                    actor=actor,
                    created_at=self.now(),
                    baseline=baseline.content,
                )
                gate = self.gate.evaluate(
                    source_input,
                    candidate,
                    source_spans=source_spans,
                    previous_draft=baseline.content,
                    declared_diff=ProtocolDraftDiffDeclaration(
                        **revision.diff.model_dump(mode="python")
                    ),
                )
                store = JobStore(session, now=self.now)
                lease = store.claim_job(result.job_id, self.WORKER_ID)
                if lease is None:
                    raise ProtocolWorkbenchError(
                        "JOB_CLAIM_FAILED",
                        title="反馈修订任务未能建立",
                        detail="系统未能取得新任务的处理权。",
                        recovery="请返回工作台后重试；若仍失败，请联系维护人员。",
                    )
                completed_payloads = {
                    STEP_REGISTER: {
                        "source_artifact_id": source_context.get("source_artifact_id"),
                        "file_name": file_name,
                    },
                    STEP_EXTRACT: {"source_input": source_input_payload},
                    STEP_RENDER: {
                        "source_spans": source_context["source_spans"],
                        "snapshot_id": source_context.get("snapshot_id"),
                    },
                    STEP_IDENTIFY: {
                        "selected_phase": target_project.study_phase.value,
                        "protocol_code": target_version.protocol_code,
                        "official_version": target_version.official_version,
                    },
                }
                for step_id, checkpoint in completed_payloads.items():
                    store.start_step(lease, step_id)
                    store.complete_step(lease, step_id, checkpoint_payload=checkpoint)
                store.enter_user_wait(
                    lease,
                    STEP_AWAIT_IDENTITY,
                    awaiting_user="identity",
                )
                store.complete_user_step(
                    result.job_id,
                    STEP_AWAIT_IDENTITY,
                    checkpoint_payload={
                        "selected_phase": target_project.study_phase.value,
                        "protocol_code": target_version.protocol_code,
                        "official_version": target_version.official_version,
                        "awaiting_user": None,
                    },
                )
                lease = store.claim_job(result.job_id, self.WORKER_ID)
                if lease is None:
                    raise ProtocolWorkbenchError(
                        "JOB_CLAIM_FAILED",
                        title="反馈修订任务未能进入审阅",
                        detail="系统未能继续准备正式草稿副本。",
                        recovery="请返回工作台后重试；若仍失败，请联系维护人员。",
                    )
                store.start_step(lease, STEP_GENERATE)
                store.complete_step(
                    lease,
                    STEP_GENERATE,
                    checkpoint_payload={
                        "draft_id": revision.draft_id,
                        "draft_revision_id": revision.revision_id,
                        "draft_status": revision.status.value,
                    },
                )
                store.start_step(lease, STEP_INTEGRITY)
                store.complete_step(
                    lease,
                    STEP_INTEGRITY,
                    checkpoint_payload={
                        "gate_result": gate.model_dump(mode="json"),
                        "gate_version": DECONSTRUCTION_GATE_VERSION,
                        "publishable": gate.publishable,
                    },
                )
                store.enter_user_wait(
                    lease,
                    STEP_AWAIT_REVIEW,
                    awaiting_user="review",
                )

        return StartDeconstructionResult(
            job_id=result.job_id,
            state="waiting_user",
            created=True,
            source_artifact_id=str(source_context.get("source_artifact_id") or ""),
            file_name=file_name,
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
            next_action=self._next_action(
                merged,
                gate_summary,
                awaiting_user=awaiting,
                job_state=snapshot.state,
            ),
            publishable=gate_summary.get("publishable"),
            target_project_id=merged.get("target_project_id"),
            target_project_name=merged.get("target_project_name"),
            target_project_code=merged.get("target_project_code"),
            target_protocol_code=merged.get("target_protocol_code"),
            target_study_phase=merged.get("target_study_phase"),
            target_study_phase_label=_study_phase_label(
                merged.get("target_study_phase")
            ),
            target_official_version=merged.get("target_official_version"),
            target_rule_set_revision=merged.get("target_rule_set_revision"),
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

    def get_generation_preview(self, job_id: str) -> dict[str, Any]:
        """生成期间的逐批只读预览：来自已验证批次的合并候选，非正式草稿。

        只有当任务尚未产生正式草稿 revision、且冻结输入与逐批预览文件都存在时
        才返回内容；任何解析失败都返回不可用状态，而不是把残缺内容当作预览。
        """
        from app.agents.protocol_deconstructor import hydrate_semantic_preview
        from app.services.protocol_deconstruction_executor import (
            SEMANTIC_PREVIEW_CONTRACT,
            _semantic_preview_path,
        )

        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        unavailable = lambda reason, detail=None: {  # noqa: E731
            "job_id": job_id,
            "available": False,
            "reason": reason,
            "detail": detail,
        }
        if merged.get("draft_revision_id"):
            return unavailable("final_draft_ready", "本轮生成已完成，请查看正式草稿。")
        source_input_payload = merged.get("source_input")
        if not isinstance(source_input_payload, dict):
            return unavailable("not_started", "解构输入尚未冻结，还没有可预览的内容。")
        path = _semantic_preview_path(self.data_paths, job_id)
        if not path.is_file() or path.is_symlink():
            return unavailable(
                "no_batch_ready", "首批语义候选尚未生成完成，请稍候。"
            )
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("contract") != SEMANTIC_PREVIEW_CONTRACT:
                return unavailable("unreadable", "预览记录版本不匹配，已停止显示。")
            if record.get("job_id") != job_id:
                return unavailable("unreadable", "保存内容不属于本次方案读取，已停止显示。")
            candidate = ProtocolSemanticDeconstructionCandidate.model_validate(
                record.get("candidate")
            )
            source_input = ProtocolDeconstructionInput.model_validate(
                source_input_payload
            )
            draft, pending_codes = hydrate_semantic_preview(source_input, candidate)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return unavailable("unreadable", f"预览内容暂时无法读取：{exc}")
        return {
            "job_id": job_id,
            "available": True,
            "preview_only": True,
            "batch_index": int(record.get("batch_index", 0)),
            "batch_total": int(record.get("batch_total", 0)),
            "updated_at": str(record.get("updated_at", "")),
            "pending_codes": pending_codes,
            "unresolved_count": len(candidate.unresolved_items),
            "content": draft.model_dump(mode="json"),
        }

    def get_draft_comparison(self, job_id: str) -> DraftComparisonView:
        """当前正式草稿与新草稿的并列比较（重新解构）。

        基线来自目标项目当前正式版本的已发布草稿 revision（不可变链），
        八类差异由确定性算法重算；来源定位信息随两侧内容一并返回。找不到
        基线或基线不一致时 fail-closed 并给出中文恢复动作。
        """
        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        if merged.get("session_kind") != "re_deconstruction":
            raise ProtocolWorkbenchError(
                "NOT_RE_DECONSTRUCTION_JOB",
                title="不是重新解构任务",
                detail="只有重新解构任务提供“当前正式版本与新草稿”并列比较。",
                recovery="请返回重新解构工作台选择项目后再比较。",
            )
        target_project_id = merged.get("target_project_id")
        if not target_project_id:
            raise ProtocolWorkbenchError(
                "TARGET_PROJECT_MISSING",
                title="缺少目标正式项目",
                detail="重新解构任务没有保存目标正式项目，无法确定比较基线。",
                recovery="请返回工作台首页重新选择项目并上传新版方案。",
            )
        candidate = self._load_draft_revision(merged)
        try:
            with self.session_factory() as session:
                baseline = resolve_formal_baseline_revision(
                    session=session,
                    project_id=target_project_id,
                )
        except FormalBaselineError as exc:
            raise ProtocolWorkbenchError(
                exc.code,
                title="无法确定当前正式草稿基线",
                detail=str(exc),
                recovery=exc.recovery,
            ) from exc
        diff = compute_draft_diff(baseline.content, candidate.content)
        return DraftComparisonView(
            job_id=job_id,
            baseline=self._comparison_side(
                baseline, formal=True, official_version=merged.get("target_official_version")
            ),
            candidate=self._comparison_side(candidate, formal=False),
            diff=diff.model_dump(mode="json"),
            source_bound=bool(candidate.content.source_refs),
        )

    @staticmethod
    def _comparison_side(
        revision: ProtocolDraftRevision,
        *,
        formal: bool,
        official_version: str | None = None,
    ) -> DraftComparisonSideView:
        content = revision.content
        return DraftComparisonSideView(
            revision_id=revision.revision_id,
            draft_id=revision.draft_id,
            protocol_version_id=revision.protocol_version_id,
            official_version=official_version
            if formal
            else content.protocol_metadata.version_candidate,
            revision_number=revision.revision_number,
            status=revision.status.value,
            rule_count=len(content.proposed_rules),
            workflow_stage_count=len(content.proposed_workflow_stages),
            is_formal_baseline=formal,
            content=content.model_dump(mode="json"),
            source_refs=sorted(set(content.source_refs)),
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
            "draft_revision_id": merged.get("draft_revision_id"),
            "protocol_version_id": source_input.protocol_version_id,
            "interpretation_sources": [
                item.model_dump(mode="json")
                for item in source_input.interpretation_sources
            ],
        }

    def register_interpretation_sources(
        self,
        job_id: str,
        *,
        expected_revision_id: str,
        idempotency_key: str,
        interpretation_sources: Sequence[InterpretationSource],
        actor: str = "用户",
    ) -> dict[str, Any]:
        """在活动草稿等待边界登记解释材料，并保留完整来源上下文。

        登记只更新任务检查点，不改变草稿 revision，也不会把解释材料混入
        方案原文 source_materials。后续 ``SOURCE_ERROR`` 反馈仍通过正式的
        草稿 revision 链执行，发布时由候选方案版本一次性持久化。
        """
        if not interpretation_sources:
            raise ProtocolWorkbenchError(
                "INTERPRETATION_SOURCES_REQUIRED",
                title="请至少登记一份解释材料",
                detail="解释材料列表为空，系统没有新增任何来源绑定。",
                recovery="请提供来源哈希、原文定位和解释内容后重试。",
            )
        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        self._require_draft_session(merged)
        current_revision = self._load_draft_revision(merged)
        submitted_hash = request_hash(
            {
                "expected_revision_id": expected_revision_id,
                "actor": actor,
                "interpretation_sources": [
                    item.model_dump(mode="json") for item in interpretation_sources
                ],
            }
        )
        created = False
        try:
            with self.session_factory() as session:
                with session.begin():
                    _record, created = IdempotencyRepository(session).resolve(
                        scope=f"protocol-interpretation-sources:{job_id}",
                        idempotency_key=idempotency_key,
                        submitted_hash=submitted_hash,
                        result_type="protocol_interpretation_sources",
                        result_id=job_id,
                    )
                    if created:
                        live_head = ProtocolDraftRevisionRepository(session).get_head(
                            current_revision.draft_id
                        )
                        if (
                            live_head is None
                            or expected_revision_id != live_head.revision_id
                        ):
                            raise ProtocolWorkbenchError(
                                "STALE_REVISION",
                                title="草稿版本已经更新",
                                detail="当前草稿已产生新的 revision，本次解释材料没有写入。",
                                recovery="请刷新草稿，使用最新 revision 重新登记解释材料。",
                                context={
                                    "submitted": {
                                        "expected_revision_id": expected_revision_id,
                                    },
                                    "current_revision_id": (
                                        live_head.revision_id if live_head else None
                                    ),
                                },
                            )
                        waiting_step_id = None
                        job = session.get(JobRecord, job_id)
                        if job is not None and job.state == "waiting_user":
                            for candidate_step_id in (STEP_AWAIT_REVIEW, STEP_PUBLISH):
                                step = session.get(
                                    JobStepRecord,
                                    {"job_id": job_id, "step_id": candidate_step_id},
                                )
                                if step is not None and step.state == "waiting_user":
                                    waiting_step_id = candidate_step_id
                                    break
                        if waiting_step_id is None:
                            raise ProtocolWorkbenchError(
                                "INTERPRETATION_SOURCE_REGISTRATION_NOT_ALLOWED",
                                title="当前草稿不在来源登记边界",
                                detail="解释材料只能在草稿审阅或发布确认等待边界登记。",
                                recovery="请刷新任务状态，进入草稿审阅后再登记解释材料。",
                            )

                        source_input = self._load_source_input(merged)
                        source_renewal = None
                        if merged.get("saved_candidate_recovery") is not None:
                            _budget_owner, source_input, source_renewal = self._validated_saved_recovery_context(merged)
                        source_by_id = {
                            item.interpretation_source_id: item
                            for item in source_input.interpretation_sources
                        }
                        allowed_rule_refs = {
                            item.official_code
                            for item in current_revision.content.proposed_rules
                        }
                        for item in interpretation_sources:
                            if item.protocol_version_id != source_input.protocol_version_id:
                                raise ProtocolWorkbenchError(
                                    "INTERPRETATION_VERSION_MISMATCH",
                                    title="解释材料不属于当前草稿版本",
                                    detail="解释材料必须绑定当前活动草稿的方案版本。",
                                    recovery="请从当前草稿来源页读取方案版本后重新登记。",
                                )
                            if not set(item.applies_to_rule_refs) <= allowed_rule_refs:
                                raise ProtocolWorkbenchError(
                                    "INTERPRETATION_SOURCE_SCOPE_INVALID",
                                    title="解释材料超出当前草稿范围",
                                    detail="解释材料声明的规则范围不属于当前活动草稿。",
                                    recovery="请只登记与当前草稿规则对应的解释材料。",
                                )
                            existing = source_by_id.get(item.interpretation_source_id)
                            if existing is not None and existing != item:
                                raise ProtocolWorkbenchError(
                                    "INTERPRETATION_SOURCE_CONFLICT",
                                    title="解释材料身份重复",
                                    detail="同一解释材料编号对应了不同内容，系统没有覆盖原登记。",
                                    recovery="请保留一份来源明确、内容一致的解释材料后重试。",
                                )
                            source_by_id[item.interpretation_source_id] = item
                        updated_input = ProtocolDeconstructionInput.model_validate(
                            source_input.model_dump(mode="json")
                            | {
                                "interpretation_source_ids": list(source_by_id),
                                "interpretation_sources": [
                                    item.model_dump(mode="json")
                                    for item in source_by_id.values()
                                ],
                            }
                        )
                        JobStore(session, now=self.now).record_user_update(
                            job_id,
                            waiting_step_id,
                            checkpoint_payload={
                                "source_input": updated_input.model_dump(mode="json"),
                                **({"saved_source_identity_revalidation": source_renewal}
                                   if source_renewal is not None else {}),
                                "interpretation_source_registration": {
                                    "actor": actor,
                                    "source_ids": [
                                        item.interpretation_source_id
                                        for item in interpretation_sources
                                    ],
                                },
                            },
                        )
                        previous = None
                        if live_head.previous_revision_id:
                            previous = ProtocolDraftRevisionRepository(session).get(
                                live_head.previous_revision_id
                            ).content
                        gate = self.gate.evaluate(
                            updated_input,
                            live_head.content,
                            source_spans=self._load_source_spans(merged),
                            previous_draft=previous,
                            declared_diff=(
                                ProtocolDraftDiffDeclaration(
                                    **live_head.diff.model_dump(mode="python")
                                )
                                if live_head.revision_number > 1
                                else None
                            ),
                        )
                        JobRepository(session).create_checkpoint(
                            checkpoint_id=uuid.uuid4().hex,
                            job_id=job_id,
                            step_id=STEP_INTEGRITY,
                            payload={
                                "gate_result": gate.model_dump(mode="json"),
                                "gate_version": DECONSTRUCTION_GATE_VERSION,
                                "publishable": gate.publishable,
                            },
                        )
        except IdempotencyConflict as exc:
            raise ProtocolWorkbenchError(
                "IDEMPOTENCY_CONFLICT",
                title="重复提交标识已经绑定其他内容",
                detail="该重复提交标识已经登记了不同的解释材料内容，系统没有覆盖原登记。",
                recovery="请使用新的重复提交标识，或重试原来的完全相同请求。",
                context=exc.as_dict(),
            ) from exc
        return self.get_sources(job_id)

    def get_integrity(self, job_id: str) -> IntegrityView:
        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        cached = merged.get("gate_result")
        if cached and merged.get("gate_version") == DECONSTRUCTION_GATE_VERSION:
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
            self._persist_gate_checkpoint(job_id, result)
        return self._integrity_view(job_id, result)

    # ------------------------------------------------------------- 项目正式版本读取

    def list_official_projects(self) -> list[OfficialProjectView]:
        """返回全部正式项目的当前投影（重新解构选择使用）。"""
        with self.session_factory() as session:
            rows = list_projects_with_revision(session)
        return [
            _official_project_view(project, rule_set_revision=revision)
            for project, revision in rows
        ]

    def get_project_official_version(
        self, project_id: str
    ) -> ProjectOfficialVersionView:
        """读取单个项目的正式版本投影：当前正式版本 + 全部已发布规则 revision。"""
        with self.session_factory() as session:
            row = get_project_row(session, project_id)
            if row is None:
                raise ProtocolWorkbenchError(
                    "PROJECT_NOT_FOUND",
                    title="找不到正式项目",
                    detail="该项目编号不存在正式发布记录，无法读取其正式版本。",
                    recovery="请返回项目列表重新选择，或先完成首次解构与发布。",
                    context={"project_id": project_id},
                )
            project, revision = row
            versions = []
            for rule_revision, version, published_at in list_rule_set_revisions(
                session, project.rule_set_id
            ):
                versions.append(
                    ProjectVersionView(
                        rule_set_revision=rule_revision,
                        protocol_version_id=version.protocol_version_id,
                        official_version=version.official_version,
                        official_date_value=_official_date_text(version.official_date),
                        official_date_precision=(
                            version.official_date.precision.value
                            if version.official_date
                            else None
                        ),
                        sha256=version.sha256,
                        rule_count=count_rule_set_rules(
                            session, project.rule_set_id, rule_revision
                        ),
                        published_at=published_at.isoformat(),
                    )
                )
        return ProjectOfficialVersionView(
            project=_official_project_view(project, rule_set_revision=revision),
            versions=versions,
            publication_count=len(versions),
        )

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
        self._validate_redeconstruction_lineage(
            merged,
            protocol_code=confirmed.protocol_code,
            study_phase=study_phase,
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
        expected_revision_id: str,
        feedback_kind: DraftFeedbackKind,
        feedback_note: str,
        target_rule_code: str,
        target_component_id: str | None = None,
        review_parent_scope: bool = False,
        actor: str,
    ) -> DraftDetailView:
        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        self._require_draft_session(merged)
        note = feedback_note.strip()
        if not note:
            raise ProtocolWorkbenchError(
                "FEEDBACK_NOTE_REQUIRED",
                title="请写明需要修订的内容",
                detail="反馈内容为空，系统无法判断需要核对或补充什么。",
                recovery="请选择一条入排标准，并写明原文理解问题或补充解释。",
            )
        with self.session_factory() as session:
            current_revision = ProtocolDraftRevisionRepository(session).get(
                expected_revision_id
            )
        current_draft = current_revision.content
        rule_codes = {rule.official_code for rule in current_draft.proposed_rules}
        if target_rule_code not in rule_codes:
            raise ProtocolWorkbenchError(
                "FEEDBACK_RULE_NOT_FOUND",
                title="找不到选中的入排标准",
                detail=f"当前草稿中没有 {target_rule_code}，未生成新稿。",
                recovery="请刷新页面，从当前入排标准列表中重新选择。",
            )
        target_rule = next(
            rule for rule in current_draft.proposed_rules
            if rule.official_code == target_rule_code
        )
        target_items = [*target_rule.components, *target_rule.restricted_components]
        if review_parent_scope and (feedback_kind != DraftFeedbackKind.SOURCE_ERROR or target_component_id is not None or not self._uses_default_feedback_reviser):
            raise ProtocolWorkbenchError(
                "SCOPE_REVIEW_REQUEST_INVALID", title="请单独核对总标题作用范围",
                detail="这项核对只检查总标题与各子项的关系，不修改条件或医学阈值。",
                recovery="请选择原文理解纠错，并以本条总标题为核对范围。",
            )
        if feedback_kind == DraftFeedbackKind.SOURCE_ERROR:
            joint_exception = False
            if target_component_id is None and len(target_items) > 1:
                source_input = self._load_source_input(merged)
                previous_gate = self.gate.evaluate(
                    source_input, current_draft,
                    source_spans=self._load_source_spans(merged),
                )
                joint_exception = self._joint_source_feedback_allowed(
                    source_input, current_draft, target_rule_code, previous_gate,
                )
            if target_component_id is None and len(target_items) > 1 and not joint_exception and not review_parent_scope:
                raise ProtocolWorkbenchError(
                    "FEEDBACK_COMPONENT_REQUIRED",
                    title="请选定需要纠正的子项",
                    detail="同一标准含有多项独立要求，不能把整条标准都当作本次修改范围。",
                    recovery="请选定具体子项，再写明需要纠正的原文含义。",
                )
            if target_component_id is not None and target_component_id not in {
                item.rule_component_id for item in target_items
            }:
                raise ProtocolWorkbenchError(
                    "FEEDBACK_COMPONENT_REQUIRED",
                    title="请选定需要纠正的子项",
                    detail="所选子项不属于当前标准或草稿已更新。",
                    recovery="请选定具体子项，再写明需要纠正的原文含义。",
                )
        draft = current_draft
        if feedback_kind == DraftFeedbackKind.SOURCE_ERROR:
            rejected_issue_codes: list[str] = []
            attempted_candidates: list[dict[str, Any]] = []
            attempts_made = 0
            try:
                from app.agents.protocol_deconstructor import (
                    ProtocolAgentCallError,
                    ProtocolRequirementIdentityError,
                    _affected_rule_codes,
                    issue_reduced_for_rule,
                    regressing_rule_codes,
                )

                source_input = self._load_source_input(merged)
                source_spans = self._load_source_spans(merged)
                previous_gate = self.gate.evaluate(
                    source_input,
                    current_draft,
                    source_spans=source_spans,
                )
                previous_issues = [
                    issue for check in previous_gate.checks for issue in check.issues
                ]
                model_note = (
                    f"本次仅修订子项 {target_component_id}；同条标准的其他子项及来源必须保持不变。\n"
                    if target_component_id is not None else ""
                ) + note
                if (joint_exception and target_component_id is None
                        and _source_proves_unsupported_member_frequency(
                            [target_rule.source_text]
                        )):
                    model_note += (
                        "\n本条多个子项共用一段冻结原文。先核对开放举例中的频次只限定其成员，"
                        "不得把该频次加到整个上位类别，也不得只保留一个不影响判定的冗余分支。"
                        "如当前表达与消费者无法忠实承接这个不可分割来源段，可提出一个"
                        " consumer_unavailable 的有源受限子项，逐字保留完整段落、"
                        "说明不能执行的具体关系，并撤下同段旧可执行子项及孤立资料要求；"
                        "这是审核方法缺口，不是研究者医学判断缺失。独立来源要求不得随之撤下。"
                    )
                elif joint_exception and target_component_id is None and target_rule.restricted_components:
                    model_note += (
                        "\n当前可执行子项均含尚未接入正式计算的适用人群条件，且同源的附加要求已作为"
                        "有源待核事项保留。若无法在现有消费者中逐项核实适用性，请以完整原文"
                        "提出单一有源能力缺口，保留其中的数量、时间和附加要求，撤下所有与整段"
                        "重叠的可执行子项及资料要求；不得把适用性缺口写成研究者书面判断缺失。"
                    )
                if self._uses_default_feedback_reviser:
                    target_gate_issues = [
                        issue
                        for issue in previous_issues
                        if target_rule_code
                        in _affected_rule_codes(
                            current_draft, [issue], fallback_all=False
                        )
                    ]
                    if target_component_id is not None:
                        target_gate_issues = self._feedback_issues_for_component(
                            target_rule, target_component_id, target_gate_issues,
                        )
                    if target_gate_issues:
                        model_note += "\n\n当前确定性完整性问题：" + "；".join(
                            f"{issue.issue_code}：{issue.problem}。{issue.next_action}"
                            + ("；问题定位（仅供核对原文）："
                               + json.dumps(issue.affected_refs, ensure_ascii=False)
                               if issue.affected_refs else "")
                            for issue in target_gate_issues
                        )
                # 模型局部修订有小幅随机性。首个候选若未通过确定性
                # 门禁，将具体问题回填后只重试一次；两次都不合格则
                # 保留原草稿。注入的测试修订器仍只执行一次。
                attempt_count = 2 if self._uses_default_feedback_reviser and not review_parent_scope else 1
                retry_guidance = ""
                if self._uses_default_feedback_reviser:
                    from app.services.protocol_deconstruction_executor import _ProtocolSemanticBatchFileCache
                    budget_owner = job_id
                    if merged.get("saved_candidate_recovery") is not None:
                        budget_owner, _validated_source, renewal = self._validated_saved_recovery_context(merged)
                        if renewal is not None:
                            raise ProtocolWorkbenchError(
                                "SAVED_SOURCE_REVALIDATION_REQUIRED", title="恢复来源的核对身份需要更新",
                                detail="目录内容未变，但恢复时的冻结记录不一致。系统尚未调用模型。",
                                recovery="请先在当前草稿登记来源核对，再继续局部修订。",
                            )
                    feedback_budget_store = _ProtocolSemanticBatchFileCache(self.data_paths, budget_owner)
                for attempt in range(attempt_count):
                    attempts_made += 1
                    regressing = False
                    new_core_semantics_issue = False
                    attempt_note = model_note + retry_guidance
                    if self._uses_default_feedback_reviser:
                        draft = self._revise_feedback_with_model(
                            source_input, current_draft, target_rule_code,
                            attempt_note, target_component_id,
                            joint_source_repair=joint_exception,
                            budget_store=feedback_budget_store,
                            **({"scope_review_store": ArtifactStore(self.data_paths)} if review_parent_scope else {}),
                        )
                    else:
                        draft = self.feedback_reviser(
                            source_input, current_draft, target_rule_code, attempt_note,
                        )
                    attempted_candidates.append(draft.model_dump(mode="json"))
                    if target_component_id is not None:
                        draft = self._retain_protected_feedback_issues(
                            current_draft, draft,
                            target_rule_code=target_rule_code,
                            target_component_id=target_component_id,
                        )
                    self._validate_source_error_scope(
                        current_draft,
                        draft,
                        target_rule_code=target_rule_code,
                        target_component_id=target_component_id,
                    )
                    if review_parent_scope:
                        self._validate_scope_review_only(current_draft, draft, target_rule_code)
                        from app.services.protocol_scope_review_service import validate_completed_scope_review
                        validate_completed_scope_review(source_input, draft, official_code=target_rule_code,
                                                        store=ArtifactStore(self.data_paths))
                    changed_codes = set(
                        compute_draft_diff(current_draft, draft).modified_rule_codes
                    )
                    if review_parent_scope and current_draft != draft:
                        changed_codes.add(target_rule_code)
                    # Scope validation above already proved that any issue change
                    # belongs to the selected rule or component.
                    unresolved_changed = (
                        current_draft.unresolved_items != draft.unresolved_items
                        or current_draft.structural_warnings != draft.structural_warnings
                    )
                    if changed_codes not in ({target_rule_code}, set()) or (
                        not changed_codes and not unresolved_changed
                    ):
                        rejection = (
                            "候选稿改动了选定标准以外的内容，或没有形成有效修订"
                        )
                    else:
                        revised_gate = self.gate.evaluate(
                            source_input,
                            draft,
                            source_spans=source_spans,
                        )
                        revised_issues = [
                            issue
                            for check in revised_gate.checks
                            for issue in check.issues
                        ]
                        regressing = target_rule_code in regressing_rule_codes(
                            current_draft,
                            previous_issues,
                            draft,
                            revised_issues,
                            [target_rule_code],
                        )
                        reduced = issue_reduced_for_rule(
                            current_draft,
                            previous_issues,
                            draft,
                            revised_issues,
                            target_rule_code,
                        )
                        # A completed scope-only review must save new uncertainty
                        # as well as clearance. Clinical/source content is frozen.
                        if review_parent_scope or (not regressing and reduced):
                            break
                        target_revised_issues = [
                            issue
                            for issue in revised_issues
                            if target_rule_code
                            in _affected_rule_codes(
                                draft, [issue], fallback_all=False
                            )
                        ]
                        if regressing:
                            previous_fingerprints = {
                                (issue.issue_code, tuple(sorted(issue.affected_refs)))
                                for issue in previous_issues
                            }
                            new_issues = [
                                issue for issue in target_revised_issues
                                if issue.level != "提醒"
                                and (issue.issue_code, tuple(sorted(issue.affected_refs)))
                                not in previous_fingerprints
                            ]
                            new_core_semantics_issue = any(
                                issue.check_name in {
                                    "boolean_logic", "numeric_semantics", "temporal_semantics",
                                }
                                for issue in new_issues
                            )
                            rejected_issue_codes = list(dict.fromkeys(
                                issue.issue_code
                                for issue in (new_issues or target_revised_issues)
                            ))
                            rejection = (
                                "候选稿产生了新的完整性问题："
                                + "；".join(
                                    f"{issue.issue_code}：{issue.problem}"
                                    for issue in (new_issues or target_revised_issues)
                                )
                            )
                        else:
                            rejected_issue_codes = list(dict.fromkeys(
                                issue.issue_code for issue in target_revised_issues
                            ))
                            rejection = (
                                "候选稿没有消除当前标准的任何一个既有完整性问题"
                            )
                    if attempt + 1 >= attempt_count:
                        raise ValueError(rejection)
                    if regressing and new_core_semantics_issue:
                        raise ValueError(rejection)
                    retry_guidance = (
                        "\n\n上一个候选稿未通过确定性完整性检查，不能保存。"
                        f"原因：{rejection}。请从当前草稿重新做最小范围修订，"
                        "不得用新问题替换旧问题。"
                    )
            except Exception as exc:
                from app.protocols.official_scope_review import OfficialScopeReviewError
                structured_call_error = isinstance(exc, (ProtocolAgentCallError, OfficialScopeReviewError))
                identity_error = isinstance(exc, ProtocolRequirementIdentityError)
                if structured_call_error:
                    rejected_issue_codes = [exc.error_code]
                call_failure_ref = None
                first_completion_failure = None
                if isinstance(exc, ProtocolAgentCallError):
                    first_completion_failure = exc.error_metadata.get("first_completion_failure")
                    try:
                        call_failure_ref = ArtifactStore(self.data_paths).put("evaluation_manifest", json.dumps({
                            "version": "protocol-feedback-call-failure/v1", "job_id": job_id,
                            "expected_revision_id": expected_revision_id,
                            "target_rule_code": target_rule_code, "target_component_id": target_component_id,
                            "error_code": exc.error_code, "call_metadata": exc.error_metadata,
                            "accepted": False,
                        }, ensure_ascii=False, sort_keys=True).encode()).storage_ref
                    except Exception as save_exc:
                        raise ProtocolWorkbenchError(
                            "FEEDBACK_FAILURE_RECORD_PERSISTENCE_FAILED", title="本次读取记录未能完整保存",
                            detail="系统未能保存本次失败的核对依据；原草稿保持不变，不会自行再读。",
                            recovery="请由维护人员检查保存位置及剩余空间，保留现有读取记录。",
                        ) from save_exc
                if identity_error and exc.candidate_draft is not None:
                    attempted_candidates.append(exc.candidate_draft)
                    rejected_issue_codes = [exc.error_code]
                candidate_hashes: list[str] = []
                for index, candidate in enumerate(attempted_candidates, start=1):
                    record = {
                        "format": "protocol-feedback-rejected-candidate/v1",
                        "accepted": False,
                        "job_id": job_id,
                        "expected_revision_id": expected_revision_id,
                        "target_rule_code": target_rule_code,
                        "target_component_id": target_component_id,
                        "attempt_index": index,
                        "candidate": candidate,
                    }
                    try:
                        candidate_hashes.append(ArtifactStore(self.data_paths).put(
                            "raw_response",
                            json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8"),
                        ).sha256)
                    except Exception:
                        logger.exception("未采用的方案局部候选未能保留 job_id=%s", job_id)
                logger.warning(
                    "方案草稿局部修订被拒绝 job_id=%s target_rule=%s revision=%s "
                    "error_type=%s error=%s candidate_hashes=%s",
                    job_id,
                    target_rule_code,
                    expected_revision_id,
                    type(exc).__name__,
                    str(exc)[:2000],
                    candidate_hashes,
                    exc_info=True,
                )
                call_failure_copy = {
                    "BUDGET_RECORD_MISSING": (
                        "原方案读取的次数记录未保留，本次没有再次读取；原草稿保持不变。",
                        "请由维护人员核对原读取记录及允许继续读取的范围；不要反复点击修订。",
                    ),
                    "BUDGET_RECORD_INVALID": (
                        "原方案读取的次数记录无法核实，本次没有再次读取；原草稿保持不变。",
                        "请由维护人员核对记录，不要删除记录后重新读取。",
                    ),
                    "LOGICAL_BUDGET_EXHAUSTED": (
                        "这项读取允许的次数已用完，本次没有再次读取；原草稿保持不变。",
                        "请先查看已保存的回答和具体问题，再决定是否需要额外核对。",
                    ),
                    "MODEL_IDENTITY_MISMATCH": (
                        "回答来源与指定模型不一致，本次回答未采用；原草稿保持不变。",
                        "请由维护人员核对模型连接，系统不会自行换模型继续读取。",
                    ),
                    "STREAM_INTERRUPTED": (
                        "模型回答中途断开，不能确认回答完整；原草稿保持不变。",
                        "请先核对已保存的回答和连接状态，系统不会自行重复读取。",
                    ),
                    "TRANSPORT_TIMEOUT": (
                        "等待模型回答超时，不能确认读取是否完成；原草稿保持不变。",
                        "请先核对已保存的读取记录，系统不会自行重复读取。",
                    ),
                }.get(exc.error_code) if structured_call_error else None
                if (structured_call_error and exc.error_code == "LOGICAL_BUDGET_EXHAUSTED"
                        and isinstance(first_completion_failure, dict)
                        and first_completion_failure.get("error_code") == "SCHEMA_INVALID"):
                    call_failure_copy = (
                        "本次回答的格式无法读取，后续核对次数也已用完；原草稿保持不变。",
                        "请先检查已保存回答的格式问题，不要把它当作方案含义不清或反复重新读取。",
                    )
                raise ProtocolWorkbenchError(
                    exc.error_code if identity_error or structured_call_error else "FEEDBACK_REVISION_FAILED",
                    title="未能完成本次反馈修订",
                    detail=(
                        call_failure_copy[0] if call_failure_copy else (
                        "删减后的资料要求无法与原稿逐项对应，原草稿保持不变。"
                        if identity_error else
                        "本次修订未能用方案原文证明各条件之间的任选关系，原草稿保持不变。"
                        if "DISJUNCTION_NOT_BOUND_TO_SOURCE" in rejected_issue_codes
                        else "系统未产出可安全读取的局部修订，原草稿保持不变。")
                    ),
                    recovery=(
                        call_failure_copy[1] if call_failure_copy else (
                        "请先单独处理已核实的多余要求，其他改动分开核对；相同内容不能区分时，先核明对应关系。"
                        if identity_error else
                        "请核对原文哪些内容是独立条件、哪些只是举例；未核清前不采用本次修订。"
                        if "DISJUNCTION_NOT_BOUND_TO_SOURCE" in rejected_issue_codes
                        else "请核对所选条款的原文和具体待核问题后再修订。")
                    ),
                    context={
                        "rule_code": target_rule_code,
                        "component_id": exc.component_id if identity_error else target_component_id,
                        "unchanged_revision_id": expected_revision_id,
                        "attempts": attempts_made,
                        "issue_codes": rejected_issue_codes,
                        **({"call_failure_ref": call_failure_ref} if call_failure_ref is not None else {}),
                        **({"affected_requirement_ids": list(exc.affected_requirement_ids),
                            "candidate_hashes": candidate_hashes} if identity_error else {}),
                    },
                ) from exc
        with self.session_factory() as session:
            with session.begin():
                service = ProtocolDraftService(session)
                revision = service.apply_feedback(
                    draft,
                    expected_revision_id=expected_revision_id,
                    feedback_kind=feedback_kind,
                    feedback_note=f"{target_rule_code}：{note}",
                    actor=actor,
                    created_at=self.now(),
                )
                self._update_draft_checkpoint(session, job_id, revision)
        return self.get_draft_detail(job_id)

    @staticmethod
    def _joint_source_feedback_allowed(
        source_input: ProtocolDeconstructionInput,
        draft: ProtocolDeconstructionDraft,
        rule_code: str,
        gate_result: ProtocolDeconstructionGateResult,
    ) -> bool:
        """Allow parent repair only when one frozen source binds every sibling."""

        rule = next(item for item in draft.proposed_rules if item.official_code == rule_code)
        catalog = next((item for item in source_input.parent_rule_catalog.items
                        if item.official_code == rule_code), None)
        if (catalog is None or len(catalog.source_span_ids) != 1
                or len(rule.components) < 2):
            return False
        source_id = catalog.source_span_ids[0]
        source = next((item.text for item in source_input.source_materials
                       if item.source_span_id == source_id), "")
        if source != rule.source_text:
            return False
        bindings = [item for item in draft.component_drafts
                    if item.parent_official_code == rule_code]
        component_ids = {item.rule_component_id for item in rule.components}
        if (len(bindings) != len(component_ids)
                or {item.proposed_component.rule_component_id for item in bindings} != component_ids
                or any(item.source_refs != [source_id] for item in bindings)):
            return False
        if rule.restricted_components:
            if any(set(item.source_span_ids) != {source_id}
                   for item in rule.restricted_components):
                return False
            population_issues = {
                ref for check in gate_result.checks for issue in check.issues
                if issue.issue_code == "APPLICABLE_POPULATION_NOT_EVALUATED"
                for ref in issue.affected_refs
            }
            for component in rule.components:
                predicates = [
                    predicate
                    for root in (component.expression, component.exception_expression)
                    if root is not None
                    for predicate in iter_atomic_predicates(root)
                ]
                if not predicates or any(
                    predicate.applicable_population is None
                    or predicate.predicate_id not in population_issues
                    for predicate in predicates
                ):
                    return False
            return True
        affected = {
            ref
            for check in gate_result.checks for issue in check.issues
            if issue.issue_code in {
                "LOCAL_EXCEPTION_REENTERED_OPEN_LIST",
                "LOCAL_EXCEPTION_MAY_WAIVE_CONCURRENT_TRIGGER",
            }
            for ref in issue.affected_refs
        }
        if (_localized_open_list_exception_requires_exclusivity([source])
                and component_ids <= affected):
            return True
        return (
            len(_substantive_obligation_segments(source)) == 1
            and _source_proves_unsupported_member_frequency([source])
            and any(
                issue.issue_code in {
                    "DISJUNCTION_NOT_BOUND_TO_SOURCE",
                    "FREQUENCY_DEFINITION_SCOPE_UNVERIFIED",
                    "FREQUENCY_WINDOW_NOT_STRUCTURED",
                }
                and set(issue.affected_refs) & component_ids
                for check in gate_result.checks for issue in check.issues
            )
        )

    @staticmethod
    def _feedback_scope_is_target_only(item: Any, target_rule_code: str) -> bool:
        codes = {
            code
            for ref in item.affected_scope
            for code in re.findall(r"(?:IN|EX)-\d{2}", ref)
        }
        return codes == {target_rule_code}

    @staticmethod
    def _feedback_issues_for_component(
        rule: Any,
        component_id: str,
        issues: Sequence[ProtocolGateIssue],
    ) -> list[ProtocolGateIssue]:
        items = [*rule.components, *rule.restricted_components]
        if len(items) == 1:
            return list(issues)
        selected = next(item for item in items if item.rule_component_id == component_id)
        identifiers = {selected.rule_component_id, selected.display_code}
        if not isinstance(selected, RestrictedRuleComponent):
            expressions = [selected.expression, selected.exception_expression]
            expressions.extend(item.expression for item in selected.repeat_trigger_conditions)
            identifiers.update(
                predicate.predicate_id
                for expression in expressions if expression is not None
                for predicate in iter_atomic_predicates(expression)
            )
            identifiers.update(item.requirement_id for item in selected.evidence_requirements)
        return [issue for issue in issues if identifiers.intersection(issue.affected_refs)]

    @staticmethod
    def _feedback_issue_is_selected_component_only(
        item: Any, *, target_rule_code: str, target_component_id: str,
        target_source_ids: set[str], sibling_source_ids: set[str],
        sibling_component_ids: set[str],
    ) -> bool:
        codes = {
            code for ref in item.affected_scope
            for code in re.findall(r"(?:IN|EX)-\d{2}", ref)
        }
        if codes - {target_rule_code}:
            return False
        scope = set(item.affected_scope)
        if scope & sibling_component_ids:
            return False
        if target_component_id in scope:
            return True
        refs = set(item.source_refs)
        return codes == {target_rule_code} and bool(refs) and refs <= target_source_ids and not refs & sibling_source_ids

    @staticmethod
    def _retain_protected_feedback_issues(
        previous: ProtocolDeconstructionDraft,
        revised: ProtocolDeconstructionDraft,
        *,
        target_rule_code: str,
        target_component_id: str,
    ) -> ProtocolDeconstructionDraft:
        before = next(rule for rule in previous.proposed_rules
                      if rule.official_code == target_rule_code)
        bindings = {
            item.proposed_component.rule_component_id: item
            for item in previous.component_drafts
            if item.parent_official_code == target_rule_code
        }
        items = (*before.components, *before.restricted_components)
        def source_ids(item):
            if isinstance(item, RestrictedRuleComponent):
                return set(item.source_span_ids)
            binding = bindings.get(item.rule_component_id)
            return set(binding.source_refs) if binding is not None else set()

        target_sources = next(source_ids(item) for item in items
                              if item.rule_component_id == target_component_id)
        siblings = [item for item in items
                    if item.rule_component_id != target_component_id]
        sibling_sources = set().union(*(source_ids(item) for item in siblings))
        sibling_ids = {item.rule_component_id for item in siblings}
        def selected(item):
            return ProtocolWorkbenchService._feedback_issue_is_selected_component_only(
                item, target_rule_code=target_rule_code,
                target_component_id=target_component_id,
                target_source_ids=target_sources,
                sibling_source_ids=sibling_sources,
                sibling_component_ids=sibling_ids,
            )

        return revised.model_copy(update={
            "unresolved_items": [
                *[item for item in previous.unresolved_items if not selected(item)],
                *[item for item in revised.unresolved_items if selected(item)],
            ],
            "structural_warnings": [
                *[item for item in previous.structural_warnings if not selected(item)],
                *[item for item in revised.structural_warnings if selected(item)],
            ],
        }, deep=True)

    @staticmethod
    def _validate_scope_review_only(previous, current, target_rule_code: str) -> None:
        def clinical_content(value):
            copy = value.model_copy(deep=True)
            for rule in copy.proposed_rules:
                if rule.official_code == target_rule_code:
                    for component in rule.components:
                        component.source_scope_review_ref = None
            for binding in copy.component_drafts:
                if binding.parent_official_code == target_rule_code:
                    binding.proposed_component.source_scope_review_ref = None
            return copy
        if clinical_content(previous) != clinical_content(current):
            raise ValueError("总标题核对只能保存来源核对记录，不得修改条件、来源或待核问题")

    @staticmethod
    def _validate_source_error_scope(
        previous: ProtocolDeconstructionDraft,
        current: ProtocolDeconstructionDraft,
        *,
        target_rule_code: str,
        target_component_id: str | None = None,
    ) -> None:
        """原文理解纠错只能重建选中的官方父规则及其附属结构。"""

        previous_rules = {
            rule.official_code: rule for rule in previous.proposed_rules
        }
        current_rules = {rule.official_code: rule for rule in current.proposed_rules}
        if (
            len(previous_rules) != len(previous.proposed_rules)
            or len(current_rules) != len(current.proposed_rules)
            or previous_rules.keys() != current_rules.keys()
        ):
            raise ValueError("原文理解纠错不得增删官方父规则")
        current_rule_ids = [rule.rule_id for rule in current.proposed_rules]
        if len(current_rule_ids) != len(set(current_rule_ids)):
            raise ValueError("原文理解纠错不得在不同父规则间复用规则身份")
        for code, rule in current_rules.items():
            if any(component.parent_rule_id != rule.rule_id for component in rule.components):
                raise ValueError("原文理解纠错不得改写任何子项的父子层级")
            if code != target_rule_code and rule != previous_rules[code]:
                raise ValueError("原文理解纠错不得修改未选中的官方父规则")

        if target_component_id is not None:
            before = previous_rules[target_rule_code]
            after = current_rules[target_rule_code]
            if (before.rule_id, before.source_text, before.kind, before.study_phase) != (
                after.rule_id, after.source_text, after.kind, after.study_phase
            ):
                raise ValueError("局部纠错不得修改所选标准的身份或原文")
            before_items = {
                item.rule_component_id: item
                for item in (*before.components, *before.restricted_components)
            }
            after_items = {
                item.rule_component_id: item
                for item in (*after.components, *after.restricted_components)
            }
            if (target_component_id not in before_items
                    or not set(before_items) <= set(after_items)):
                raise ValueError("局部纠错不得删除或重新编号同条标准的其他子项")
            new_ids = set(after_items) - set(before_items)
            if any(not item_id.startswith(f"{target_component_id}:split:")
                   for item_id in new_ids):
                raise ValueError("局部纠错新增分支必须属于所选子项")
            if any(
                before_items[item_id] != after_items[item_id]
                for item_id in before_items if item_id != target_component_id
            ):
                raise ValueError("局部纠错不得改写同条标准中未选中的子项")
            before_bindings = {
                item.proposed_component.rule_component_id: item
                for item in previous.component_drafts
                if item.parent_official_code == target_rule_code
            }
            after_bindings = {
                item.proposed_component.rule_component_id: item
                for item in current.component_drafts
                if item.parent_official_code == target_rule_code
            }
            if any(
                before_bindings.get(item_id) != after_bindings.get(item_id)
                for item_id in before_items if item_id != target_component_id
            ):
                raise ValueError("局部纠错不得改写未选中子项的来源映射")

            def item_sources(item_id: str) -> set[str]:
                restricted = before_items[item_id]
                if isinstance(restricted, RestrictedRuleComponent):
                    return set(restricted.source_span_ids)
                binding = before_bindings.get(item_id)
                return set(binding.source_refs) if binding is not None else set()

            target_sources = item_sources(target_component_id)
            target_excerpts = "\n".join(
                before_bindings[target_component_id].source_excerpts
            ) if target_component_id in before_bindings else ""
            for item_id in new_ids:
                binding = after_bindings.get(item_id)
                if binding is not None:
                    new_sources = set(binding.source_refs)
                    new_excerpts = binding.source_excerpts
                else:
                    restricted = after_items[item_id]
                    if not isinstance(restricted, RestrictedRuleComponent):
                        raise ValueError("局部纠错新增分支缺少原文来源")
                    new_sources = set(restricted.source_span_ids)
                    new_excerpts = restricted.source_excerpts
                if (not new_sources or not new_sources <= target_sources
                        or not all(excerpt in target_excerpts for excerpt in new_excerpts)):
                    raise ValueError("局部纠错新增分支不得借用所选子项以外的原文")
            sibling_sources = set().union(*(
                item_sources(item_id) for item_id in before_items if item_id != target_component_id
            ))
            sibling_ids = set(before_items) - {target_component_id}
            for before_issues, after_issues in (
                (previous.unresolved_items, current.unresolved_items),
                (previous.structural_warnings, current.structural_warnings),
            ):
                def protected(item: Any) -> bool:
                    return not ProtocolWorkbenchService._feedback_issue_is_selected_component_only(
                        item, target_rule_code=target_rule_code,
                        target_component_id=target_component_id,
                        target_source_ids=target_sources,
                        sibling_source_ids=sibling_sources,
                        sibling_component_ids=sibling_ids,
                    )
                if list(filter(protected, before_issues)) != list(filter(protected, after_issues)):
                    raise ValueError("局部纠错不得改写未选中子项或共用原文的待核问题")

        if target_component_id is None:
            for previous_items, current_items in (
                (previous.unresolved_items, current.unresolved_items),
                (previous.structural_warnings, current.structural_warnings),
            ):
                previous_outside = [
                    item
                    for item in previous_items
                    if not ProtocolWorkbenchService._feedback_scope_is_target_only(item, target_rule_code)
                ]
                current_outside = [
                    item
                    for item in current_items
                    if not ProtocolWorkbenchService._feedback_scope_is_target_only(item, target_rule_code)
                ]
                if previous_outside != current_outside:
                    raise ValueError("原文理解纠错不得改写其他入排标准的待确认事项")

        tree_components = [
            (code, component)
            for code, rule in current_rules.items()
            for component in rule.components
        ]
        tree_component_ids = [
            component.rule_component_id for _code, component in tree_components
        ]
        if len(tree_component_ids) != len(set(tree_component_ids)):
            raise ValueError("原文理解纠错不得在不同父规则间复用子项身份")
        tree_component_by_id = {
            component.rule_component_id: (code, component)
            for code, component in tree_components
        }

        draft_component_ids = [item.draft_component_id for item in current.component_drafts]
        bound_component_ids = [
            item.proposed_component.rule_component_id for item in current.component_drafts
        ]
        if (
            len(draft_component_ids) != len(set(draft_component_ids))
            or len(bound_component_ids) != len(set(bound_component_ids))
            or set(bound_component_ids) != set(tree_component_ids)
        ):
            raise ValueError("原文理解纠错后的规则树与子项来源映射必须保持全局一一对应")
        draft_component_by_id = {
            item.draft_component_id: item for item in current.component_drafts
        }
        for binding in current.component_drafts:
            tree_entry = tree_component_by_id.get(
                binding.proposed_component.rule_component_id
            )
            if (
                tree_entry is None
                or binding.parent_official_code != tree_entry[0]
                or binding.proposed_component != tree_entry[1]
            ):
                raise ValueError("子项来源映射必须指向规则树中的同一父规则和同一子项")

        tree_requirements = {
            requirement.requirement_id: (component.rule_component_id, requirement)
            for _code, component in tree_components
            for requirement in component.evidence_requirements
        }
        tree_requirement_count = sum(
            len(component.evidence_requirements)
            for _code, component in tree_components
        )
        if len(tree_requirements) != tree_requirement_count:
            raise ValueError("原文理解纠错不得跨子项复用资料要求身份")
        component_requirement_drafts = [
            item
            for item in current.evidence_requirement_drafts
            if item.draft_component_id is not None
        ]
        proposed_requirement_ids = [
            item.proposed_requirement.requirement_id
            for item in component_requirement_drafts
        ]
        if (
            len(proposed_requirement_ids) != len(set(proposed_requirement_ids))
            or set(proposed_requirement_ids) != set(tree_requirements)
        ):
            raise ValueError("规则树与资料要求来源映射必须保持全局一一对应")
        for requirement_draft in component_requirement_drafts:
            component_binding = draft_component_by_id.get(
                requirement_draft.draft_component_id
            )
            tree_entry = tree_requirements.get(
                requirement_draft.proposed_requirement.requirement_id
            )
            if (
                component_binding is None
                or tree_entry is None
                or tree_entry[0]
                != component_binding.proposed_component.rule_component_id
                or requirement_draft.proposed_requirement != tree_entry[1]
            ):
                raise ValueError("资料要求来源映射必须指向同一规则子项中的同一资料要求")

        target_component_ids = {
            component.rule_component_id
            for component in current_rules[target_rule_code].components
        }
        target_components = {
            component.rule_component_id: component
            for component in current_rules[target_rule_code].components
        }
        for binding in current.component_drafts:
            component = binding.proposed_component
            if binding.parent_official_code == target_rule_code:
                if (
                    component.rule_component_id not in target_component_ids
                    or component != target_components[component.rule_component_id]
                ):
                    raise ValueError("选中规则的子项来源映射与规则树不一致")
        previous_non_target_bindings = {
            item.draft_component_id: item
            for item in previous.component_drafts
            if item.parent_official_code != target_rule_code
        }
        current_non_target_bindings = {
            item.draft_component_id: item
            for item in current.component_drafts
            if item.parent_official_code != target_rule_code
        }
        if previous_non_target_bindings != current_non_target_bindings:
            raise ValueError("原文理解纠错不得改写未选中规则的子项或来源")

        target_draft_component_ids = {
            item.draft_component_id
            for item in [*previous.component_drafts, *current.component_drafts]
            if item.parent_official_code == target_rule_code
            and (target_component_id is None
                 or item.proposed_component.rule_component_id == target_component_id
                 or item.proposed_component.rule_component_id.startswith(
                     f"{target_component_id}:split:"
                 ))
        }
        previous_other_requirements = {
            item.draft_requirement_id: item
            for item in previous.evidence_requirement_drafts
            if item.draft_component_id not in target_draft_component_ids
        }
        current_other_requirements = {
            item.draft_requirement_id: item
            for item in current.evidence_requirement_drafts
            if item.draft_component_id not in target_draft_component_ids
        }
        if previous_other_requirements != current_other_requirements:
            raise ValueError("原文理解纠错不得改写其他规则或流程项目的资料要求")

        target_requirement_ids = {
            item.proposed_requirement.requirement_id
            for item in [
                *previous.evidence_requirement_drafts,
                *current.evidence_requirement_drafts,
            ]
            if item.draft_component_id in target_draft_component_ids
        }
        previous_stage_scope = {
            (
                stage.workflow_stage_id,
                stage.stage,
                stage.display_name,
                stage.visit_instance,
                stage.visit_window,
                stage.review_required,
            ): tuple(
                requirement_id
                for requirement_id in stage.due_requirement_ids
                if requirement_id not in target_requirement_ids
            )
            for stage in previous.proposed_workflow_stages
        }
        previous_stage_ids = {stage.workflow_stage_id for stage in previous.proposed_workflow_stages}
        current_stage_scope = {
            (
                stage.workflow_stage_id,
                stage.stage,
                stage.display_name,
                stage.visit_instance,
                stage.visit_window,
                stage.review_required,
            ): tuple(
                requirement_id
                for requirement_id in stage.due_requirement_ids
                if requirement_id not in target_requirement_ids
            )
            for stage in current.proposed_workflow_stages
            if (
                stage.workflow_stage_id in previous_stage_ids
                or not stage.due_requirement_ids
                or any(item not in target_requirement_ids for item in stage.due_requirement_ids)
            )
        }
        if previous_stage_scope != current_stage_scope:
            raise ValueError("原文理解纠错不得改写审核节点或移动未选中规则的资料要求")

        immutable_fields = (
            "draft_id",
            "project_id",
            "protocol_version_id",
            "selected_phase",
            "protocol_metadata",
            "parent_catalog_mappings",
            "procedure_catalog_mappings",
            "source_refs",
        )
        if any(getattr(previous, field) != getattr(current, field) for field in immutable_fields):
            raise ValueError("原文理解纠错不得改写项目身份、流程结构或全局来源范围")

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

    @staticmethod
    def _require_control_publication_references(
        *,
        control_job_id: str | None,
        control_checkpoint_id: str | None,
    ) -> None:
        if control_job_id is not None and control_checkpoint_id is not None:
            return
        raise ProtocolWorkbenchError(
            "CONTROL_COVERAGE_REQUIRED",
            title="补充审核要求尚未完成",
            detail=(
                "必须先完成整份方案的跨章节核对；即使未发现额外控制点，"
                "也需要保留本次全文覆盖结果。"
            ),
            recovery="请等待“方案其他审核要求”完成后再发布。",
        )

    def publish_first_project(
        self,
        job_id: str,
        *,
        idempotency_key: str,
        actor: str,
        control_job_id: str | None = None,
        control_checkpoint_id: str | None = None,
    ) -> PublicationView:
        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        self._require_control_publication_references(
            control_job_id=control_job_id,
            control_checkpoint_id=control_checkpoint_id,
        )
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
        self._ensure_publish_wait(job_id, revision.revision_id)
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
                    control_job_id=control_job_id,
                    control_checkpoint_id=control_checkpoint_id,
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

    def publish_re_deconstruction(
        self,
        job_id: str,
        *,
        idempotency_key: str,
        actor: str,
        control_job_id: str | None = None,
        control_checkpoint_id: str | None = None,
    ) -> PublicationView:
        """同谱系同期别发布编排：复用既有原子发布事务，把新草稿作为目标项目的
        新的不可变规则版本写入。目标项目在创建任务时已持久保存；谱系与期别一致
        由发布事务内的确定性门禁裁定（跨方案/跨期即拒绝并给出中文下一步）。"""
        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        self._require_control_publication_references(
            control_job_id=control_job_id,
            control_checkpoint_id=control_checkpoint_id,
        )
        if merged.get("session_kind") != "re_deconstruction":
            raise ProtocolWorkbenchError(
                "NOT_RE_DECONSTRUCTION_JOB",
                title="不是重新解构任务",
                detail="该任务不是面向已有正式项目的重新解构，不能按重新发布处理。",
                recovery="请返回首次解构入口完成发布，或重新选择项目发起重新解构。",
            )
        target_project_id = merged.get("target_project_id")
        if not target_project_id:
            raise ProtocolWorkbenchError(
                "TARGET_PROJECT_MISSING",
                title="缺少目标正式项目",
                detail="重新解构任务没有保存目标正式项目，无法完成发布。",
                recovery="请返回工作台首页重新选择项目并上传新版方案。",
            )
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
        new_version_id = revision.content.protocol_version_id
        self._ensure_publish_wait(job_id, revision.revision_id)
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
                    project_id=target_project_id,
                    protocol_version_id=new_version_id,
                    control_job_id=control_job_id,
                    control_checkpoint_id=control_checkpoint_id,
                    expected_rule_set_revision=merged.get(
                        "target_rule_set_revision"
                    ),
                )
            )
        except PublicationGateError as exc:
            raise ProtocolWorkbenchError(
                "PUBLICATION_GATE_REJECTED",
                title="发布前完整性检查未通过",
                detail="草稿仍未达到可发布标准，系统没有写入任何正式规则。",
                recovery="请根据完整性问题列表修正草稿后重新保存，再尝试发布。",
            ) from exc
        except PublicationLineageError as exc:
            raise ProtocolWorkbenchError(
                "PUBLICATION_LINEAGE_REJECTED",
                title="方案谱系或期别与目标项目不一致",
                detail=str(exc),
                recovery="请确认上传的新版方案属于目标项目的同一方案与研究期别。",
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
        merged = self._merged_payload(job_id)
        with self.session_factory() as session:
            with session.begin():
                draft_service = ProtocolDraftService(session)
                baseline = None
                if merged.get("session_kind") == "re_deconstruction":
                    target_project_id = merged.get("target_project_id")
                    if not target_project_id:
                        raise ValueError("重新解构测试夹具缺少目标项目")
                    try:
                        baseline = resolve_formal_baseline_revision(
                            session=session,
                            project_id=str(target_project_id),
                        )
                    except FormalBaselineError:
                        # 仅供 fail-closed 对抗测试构造“正式基线损坏”
                        # 状态；真实执行器不走此测试夹具，会在生成前停止。
                        baseline = None
                revision = draft_service.save_initial_draft(
                    draft,
                    actor=actor,
                    created_at=self.now(),
                    baseline=baseline.content if baseline is not None else None,
                )
                gate = gate_result or self.gate.evaluate(
                    source_input,
                    draft,
                    source_spans=source_spans,
                    previous_draft=(
                        baseline.content if baseline is not None else None
                    ),
                    declared_diff=(
                        ProtocolDraftDiffDeclaration(
                            **revision.diff.model_dump(mode="python")
                        )
                        if baseline is not None
                        else None
                    ),
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
                            "gate_version": DECONSTRUCTION_GATE_VERSION,
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

    def is_re_deconstruction(self, job_id: str) -> bool:
        """返回该解构任务是否为重新解构（重新发布到既有正式项目）。"""
        merged = self._merged_payload(job_id)
        self._require_protocol_job(job_id)
        return merged.get("session_kind") == "re_deconstruction"

    def _validated_saved_recovery_context(self, merged: dict[str, Any]):
        from app.services.protocol_saved_draft_recovery import load_saved_draft_recovery, reconcile_saved_source_identity
        from app.services.protocol_deconstruction_executor import ProtocolDeconstructionExecutorConfig, _assemble_input_package
        recovery = merged["saved_candidate_recovery"]
        if (not isinstance(recovery, dict) or recovery.get("version") != "saved-draft-recovery/v2"
                or recovery.get("candidate_origin") != "operator_imported_unpublished"):
            raise ProtocolWorkbenchError("SAVED_DRAFT_RECOVERY_INVALID", title="恢复提案身份不完整",
                detail="恢复记录版本或提案来源身份不受支持。", recovery="请保留原记录并核对恢复请求。")
        try:
            with self.session_factory() as session:
                original, _draft = load_saved_draft_recovery(
                    JobStore(session, now=self.now), self.data_paths,
                    source_job_id=recovery["source_job_id"], candidate_ref=recovery["candidate_ref"],
                    expected_freeze_sha256=recovery["expected_freeze_sha256"],
                    source_steps=_CHECKPOINT_STEP_ORDER[:_CHECKPOINT_STEP_ORDER.index(STEP_GENERATE)],
                )
            original_identity = ProtocolDeconstructionInput.model_validate(original["source_input"])
            rebuilt = _assemble_input_package(None, ProtocolDeconstructionExecutorConfig(
                data_paths=self.data_paths, session_factory=self.session_factory, now=self.now,
            ), original, source_identity=original_identity)
            source, proof = reconcile_saved_source_identity(self._load_source_input(merged), rebuilt.source_input)
        except (ValueError, KeyError) as exc:
            raise ProtocolWorkbenchError("SAVED_DRAFT_RECOVERY_INVALID", title="恢复来源无法复核",
                detail=str(exc), recovery="请核对原件、结构块和来源记录，不要重置读取额度。") from exc
        return recovery["source_job_id"], source, proof

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
                for _, payload in store.list_checkpoints(job_id, step_id):
                    merged.update(
                        {
                            key: value
                            for key, value in payload.items()
                            if key != "attempt"
                        }
                    )
            return merged

    def _source_context_for_revision(
        self,
        revision_id: str,
    ) -> dict[str, Any] | None:
        """从生成该正式草稿的持久任务恢复方案输入与原文定位。

        草稿 revision 本身只保存规则内容；来源图保存在任务检查点。按任务更新时间
        倒序查找精确引用该 revision 的任务，避免把另一版本的来源上下文拼接进来。
        """
        with self.session_factory() as session:
            job_ids = session.execute(
                select(JobRecord.job_id)
                .where(JobRecord.job_type == PROTOCOL_DECONSTRUCTION_JOB_TYPE)
                .order_by(JobRecord.updated_at.desc(), JobRecord.job_id.desc())
            ).scalars().all()
        for job_id in job_ids:
            try:
                merged = self._merged_payload(job_id)
            except (JobNotFoundError, ValueError):
                continue
            if merged.get("draft_revision_id") != revision_id:
                continue
            source_input = merged.get("source_input")
            source_spans = merged.get("source_spans")
            if not isinstance(source_input, dict) or not isinstance(source_spans, dict):
                continue
            return {
                "source_input": source_input,
                "source_spans": source_spans,
                "source_artifact_id": merged.get("source_artifact_id"),
                "snapshot_id": merged.get("snapshot_id"),
                "file_name": merged.get("file_name"),
            }
        return None

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

    def _ensure_publish_wait(self, job_id: str, revision_id: str) -> None:
        """把审阅边界推进到发布确认边界；重复调用保持幂等。

        发布事务只能在 ``publish`` 步骤已进入等待确认后执行，避免正式记录已经
        写入而工作流仍停在审阅步骤。发布失败时页面仍可读取同一草稿并重试。
        """
        with self.session_factory() as session:
            store = JobStore(session, now=self.now)
            job = store.get_job(job_id)
            review_step = session.get(
                JobStepRecord,
                {"job_id": job_id, "step_id": STEP_AWAIT_REVIEW},
            )
            publish_step = session.get(
                JobStepRecord,
                {"job_id": job_id, "step_id": STEP_PUBLISH},
            )
            if publish_step is not None and publish_step.state in {
                "waiting_user",
                "completed",
            }:
                return
            if review_step is None or review_step.state != "waiting_user":
                raise ProtocolWorkbenchError(
                    "REVIEW_NOT_READY_FOR_PUBLICATION",
                    title="草稿尚未完成发布前审阅",
                    detail="当前任务不在等待审阅状态，不能进入发布确认。",
                    recovery="请刷新页面并继续完成草稿审阅；若状态仍异常，请联系维护人员。",
                )

        self._complete_user_step(
            job_id,
            STEP_AWAIT_REVIEW,
            {
                "draft_revision_id": revision_id,
                "awaiting_user": None,
            },
        )
        with self.session_factory() as session:
            with session.begin():
                store = JobStore(session, now=self.now)
                lease = store.claim_job(job_id, self.WORKER_ID)
                if lease is None:
                    raise ProtocolWorkbenchError(
                        "JOB_CLAIM_FAILED",
                        title="未能进入发布确认",
                        detail="系统未能取得任务的处理权。",
                        recovery="请刷新页面后重试；若仍失败，请联系维护人员。",
                    )
                store.enter_user_wait(
                    lease,
                    STEP_PUBLISH,
                    awaiting_user="publish",
                )

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
            declared_diff=(
                ProtocolDraftDiffDeclaration(
                    **revision.diff.model_dump(mode="python")
                )
                if revision.revision_number > 1
                else None
            ),
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
                    "gate_version": DECONSTRUCTION_GATE_VERSION,
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

    def _persist_gate_checkpoint(
        self,
        job_id: str,
        gate: ProtocolDeconstructionGateResult,
    ) -> None:
        """保存按当前门禁语义重算的结果，并保留历史检查点。"""
        with self.session_factory() as session:
            with session.begin():
                JobRepository(session).create_checkpoint(
                    checkpoint_id=uuid.uuid4().hex,
                    job_id=job_id,
                    step_id=STEP_INTEGRITY,
                    payload={
                        "gate_result": gate.model_dump(mode="json"),
                        "gate_version": DECONSTRUCTION_GATE_VERSION,
                        "publishable": gate.publishable,
                    },
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
        if revision.revision_number <= 1:
            return None
        return ProtocolDraftDiffDeclaration(
            **revision.diff.model_dump(mode="python")
        )

    def _require_draft_session(self, merged: dict[str, Any]) -> None:
        if not merged.get("draft_revision_id"):
            raise ProtocolWorkbenchError(
                "DRAFT_NOT_READY",
                title="草稿尚未生成",
                detail="当前还不能编辑方案解构草稿。",
                recovery="请等待草稿生成完成。",
            )

    @staticmethod
    def _validate_redeconstruction_lineage(
        merged: dict[str, Any],
        *,
        protocol_code: str,
        study_phase: StudyPhase,
    ) -> None:
        """重新解构上传的新版方案只允许改变版本/日期/哈希；方案编号谱系与研究
        期别必须与持久保存的目标项目一致，否则在确认身份时即给出中文下一步。
        发布事务仍会复跑同一条确定性校验，此处为更早的人机提示。"""
        if merged.get("session_kind") != "re_deconstruction":
            return
        target_protocol_code = merged.get("target_protocol_code")
        target_study_phase = merged.get("target_study_phase")
        mismatched: list[str] = []
        if target_protocol_code and protocol_code != target_protocol_code:
            mismatched.append(
                f"方案编号（目标项目 {target_protocol_code}，本次 {protocol_code}）"
            )
        if target_study_phase and study_phase.value != target_study_phase:
            mismatched.append(
                f"研究期别（目标项目 {_study_phase_label(target_study_phase)}，"
                f"本次 {_study_phase_label(study_phase.value)}）"
            )
        if not mismatched:
            return
        raise ProtocolWorkbenchError(
            "REDECONSTRUCTION_LINEAGE_MISMATCH",
            title="新版方案与目标项目不一致",
            detail="上传的新版方案与所选项目的方案谱系/研究期别不一致：" + "、".join(mismatched),
            recovery=(
                "请返回项目列表确认目标项目，或上传与该项目同一方案编号、"
                "同一研究期别的正式新版本；已确认的方案信息不会应用到目标项目。"
            ),
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
        if not cached or merged.get("gate_version") != DECONSTRUCTION_GATE_VERSION:
            return {"publishable": None, "needs_recheck": True}
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
        job_state: str | None = None,
    ) -> str:
        awaiting = awaiting_user or merged.get("awaiting_user")
        redo = merged.get("session_kind") == "re_deconstruction"
        if awaiting == "identity":
            return (
                "请核对方案编号、版本、日期与研究期别；重新解构的新版方案必须与"
                "目标项目保持一致（版本、日期与文件哈希可更新）。"
                if redo
                else "请核对方案编号、版本、日期与研究期别后确认。"
            )
        if awaiting == "review":
            if gate_summary.get("publishable"):
                return (
                    "重新解构草稿已通过完整性检查，确认无误后可发布并更新正式规则。"
                    if redo
                    else "草稿已通过完整性检查，确认无误后可发布正式项目。"
                )
            blocking = gate_summary.get("blocking_count")
            if blocking:
                return f"草稿有 {blocking} 项阻止发布的问题，请先逐项核对修正。"
            return "请审阅草稿与来源定位，修正需要核对的项目。"
        if awaiting == "publish":
            return (
                "草稿已确认，确认后将把新的不可变规则版本发布到目标项目。"
                if redo
                else "草稿已确认，请确认后发布正式项目。"
            )
        if job_state == "failed_retryable":
            return "草稿生成暂未完成，系统会从生成草稿这一步自动再试。"
        if job_state == "failed_final":
            return (
                "草稿生成未能完成。可以重新生成草稿；已核对的方案信息"
                "和研究期别会保留，不需要重新上传。"
            )
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
    "DraftComparisonSideView",
    "DraftComparisonView",
    "OfficialProjectView",
    "ProjectOfficialVersionView",
    "ProjectVersionView",
    "ProtocolSessionView",
    "ProtocolWorkbenchError",
    "ProtocolWorkbenchService",
    "StartDeconstructionResult",
]
