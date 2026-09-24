"""Durable two-stage execution for protocol-control discovery and deep analysis.

The execution path consumes the completed protocol deconstruction job's frozen
structure snapshot exactly once while creating a new durable job.  Every later
step consumes typed, persisted contracts only; it never reopens the original
DOCX and never routes through the legacy semantic reviewer.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from app.agents.protocol_control_agent_transport import (
    protocol_control_transport_from_environment,
)
from app.agents.protocol_control_deconstructor import (
    DEFAULT_MAX_SCHEMA_REPAIRS,
    DEFAULT_MAX_TRANSPORT_RETRIES,
    DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE,
    DEFAULT_PROTOCOL_CONTROL_DISCOVERY_PROMPT_TEMPLATE,
    ProtocolControlAgentRunner,
    ProtocolControlAgentRunResult,
    ProtocolControlAgentTransport,
    ProtocolControlDiscoveryAgentRunner,
    ProtocolControlDiscoveryAgentRunResult,
    ProtocolControlDiscoveryAgentTransport,
    protocol_control_agent_prompt_template_sha256,
    protocol_control_discovery_prompt_template_sha256,
)
from app.agents.protocol_control_discovery_transport import (
    protocol_control_discovery_transport_from_environment,
)
from app.domain.contracts.agent_io import ProtocolDeconstructionInput
from app.domain.contracts.enums import ExtractionStatus, PhaseScope, StudyPhase
from app.domain.contracts.protocol_controls import (
    ProtocolControlBatchDispositionHydrated,
    ProtocolControlBatchPlan,
    ProtocolControlDiscoveryBatch,
    ProtocolControlDiscoveryDecision,
    ProtocolControlDiscoveryDisposition,
    ProtocolControlDiscoveryPlan,
    ProtocolControlDiscoveryToDeepPlan,
    ProtocolControlDispositionBatch,
    ProtocolControlUnitDisposition,
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    PublishedProtocolControlCatalog,
    StructureUnitDispositionKind,
    stable_protocol_control_batch_id,
    stable_protocol_control_manifest_structure_unit_ids_sha256,
)
from app.domain.contracts.protocol_ingestion import (
    ProtocolExtractionSnapshot,
    ProtocolSourceSpan,
)
from app.domain.contracts.protocol_metadata import PhaseApplicabilityGraph, PhaseProjection
from app.domain.contracts.rules import WorkflowStage
from app.protocols.docx_structure import StructureBlock, block_set_hash
from app.protocols.full_protocol_coverage import (
    FullProtocolCoverageError,
    build_full_protocol_coverage_manifest,
)
from app.protocols.protocol_control_gate import (
    CONTROL_PUBLICATION_GATE_VERSION,
    ProtocolControlGateError,
    ProtocolControlGateIssue,
    check_protocol_control_batch_candidates,
    validate_protocol_control_publication,
)
from app.protocols.protocol_control_repair_errors import (
    CANDIDATE_REPARTITION_GATE_CODES,
    SOURCE_CLOSURE_REWRITE_GATE_CODES,
    publication_repair_error,
)
from app.config import (
    PROTOCOL_CONTROL_ADAPTIVE_BATCHING,
    PROTOCOL_CONTROL_DISCOVERY_ADAPTIVE_UNIT_CAP,
    PROTOCOL_CONTROL_DISCOVERY_CHARS_PER_TOKEN,
    PROTOCOL_CONTROL_DISCOVERY_MAX_INPUT_TOKENS,
    PROTOCOL_CONTROL_DISCOVERY_MAX_OUTPUT_TOKENS,
    PROTOCOL_CONTROL_DISCOVERY_MAX_PARALLEL,
    PROTOCOL_CONTROL_DISCOVERY_OUTPUT_TOKENS_PER_UNIT,
    PROTOCOL_CONTROL_DISCOVERY_TEMPLATE_OVERHEAD_TOKENS,
)
from app.protocols.adaptive_batch_budget import (
    AdaptiveBatchBudget,
    default_discovery_batch_budget,
)
from app.protocols.protocol_control_planning import (
    DEFAULT_PROTOCOL_CONTROL_DISCOVERY_BATCH_UNITS,
    ProtocolControlPlanningError,
    plan_protocol_control_deep_batches_from_discovery,
    plan_protocol_control_discovery,
    validate_protocol_control_discovery_results,
)
from app.services.evidence_app_errors import EvidenceAppError, app_error_boundary
from app.services.job_service import JobService, StepSpec
from app.services.protocol_workbench_service import (
    PROTOCOL_DECONSTRUCTION_JOB_TYPE,
)
from app.storage.codecs import utc_now, verify_payload_sha256
from app.storage.config import DataPaths
from app.workflow.errors import JobNotFoundError, StepFailure
from app.workflow.jobstore import DEFAULT_LEASE_TTL, JobStore
from app.workflow.runner import PreparedStepResult, StepContext, StepExecutor


PROTOCOL_CONTROL_EXECUTION_JOB_TYPE = "protocol_control_execution"
# A short alias keeps callers independent from the longer API-facing name.
PROTOCOL_CONTROL_JOB_TYPE = PROTOCOL_CONTROL_EXECUTION_JOB_TYPE
PROTOCOL_CONTROL_EXECUTION_VERSION = "phase5/protocol-control-execution/v96"
PROTOCOL_CONTROL_EXECUTION_CONTROL_SCHEMA = (
    "phase5/protocol-control-execution-control/v1"
)

STEP_CLOSURE = "deterministic_closure"
STEP_HYDRATE = "hydrate"
STEP_GATE = "gate"
CANDIDATE_CONTROL_PACKAGE_RESULT_KIND = "hydrated_candidate_control_package"
FORMAL_CATALOG_STATUS_NOT_MATERIALIZED = "not_materialized"


_DISCOVERY_STEP_PREFIX = "discovery_"
_DEEP_STEP_PREFIX = "deep_"
_SOURCE_DECONSTRUCTION_JOB_TYPE = PROTOCOL_DECONSTRUCTION_JOB_TYPE
_SOURCE_STEP_ORDER = (
    "register_file",
    "extract_structure",
    "render_and_align",
    "identify_identity_phase",
    "await_identity_confirm",
    "freeze_deconstruction_input",
)
_DEFAULT_OUTER_STEP_ATTEMPTS = 2
_MAX_BATCH_UNITS = 256
_MAX_CONTEXT_RADIUS = 64
_MAX_DISCOVERY_PARALLEL = 32

Now = Callable[[], datetime]


class ProtocolControlExecutionError(EvidenceAppError):
    """Safe application error raised before a control job is created."""

    status_code = 422
    code = "PROTOCOL_CONTROL_EXECUTION_INVALID"
    title = "方案控制任务无法建立"
    recovery = "请确认方案解构任务已完成结构快照与期别确认后重试。"

    def __init__(
        self,
        code: str,
        detail: str,
        *,
        status_code: int = 422,
        title: str | None = None,
        recovery: str | None = None,
    ) -> None:
        self.code = code
        self.status_code = status_code
        if title is not None:
            self.title = title
        if recovery is not None:
            self.recovery = recovery
        super().__init__(detail)


@dataclass(frozen=True)
class ProtocolControlExecutionResult:
    job_id: str
    state: str
    created: bool
    source_job_id: str
    snapshot_id: str
    manifest_id: str


@dataclass
class ProtocolControlExecutorConfig:
    """Injectable durable executor configuration.

    ``discovery_transport`` and ``deep_transport`` are deliberately separate.
    The generic ``transport`` aliases are retained only as an injection
    convenience for deterministic tests; environment construction still uses
    two dedicated strict response-format adapters.
    """

    data_paths: DataPaths
    session_factory: sessionmaker[Session]
    now: Now = utc_now
    discovery_transport: ProtocolControlDiscoveryAgentTransport | Any | None = None
    deep_transport: ProtocolControlAgentTransport | Any | None = None
    discovery_transport_factory: Callable[[], Any] | None = None
    deep_transport_factory: Callable[[], Any] | None = None
    transport: Any | None = None
    transport_factory: Callable[[], Any] | None = None
    require_frozen_routes: bool = False
    discovery_prompt_template: str = DEFAULT_PROTOCOL_CONTROL_DISCOVERY_PROMPT_TEMPLATE
    deep_prompt_template: str = DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE
    # Compatibility with callers that configure one prompt for a fake route.
    prompt_template: str | None = None
    discovery_max_transport_retries: int = DEFAULT_MAX_TRANSPORT_RETRIES
    discovery_max_schema_repairs: int = DEFAULT_MAX_SCHEMA_REPAIRS
    deep_max_transport_retries: int = DEFAULT_MAX_TRANSPORT_RETRIES
    deep_max_schema_repairs: int = DEFAULT_MAX_SCHEMA_REPAIRS
    # Compatibility aliases for a shared bounded runner configuration.
    max_transport_retries: int | None = None
    max_schema_repairs: int | None = None

    def prompt_for(self, stage: str) -> str:
        if self.prompt_template is not None:
            return self.prompt_template
        return (
            self.discovery_prompt_template
            if stage == "discovery"
            else self.deep_prompt_template
        )

    def limits_for(self, stage: str) -> tuple[int, int]:
        transport_retries = (
            self.discovery_max_transport_retries
            if stage == "discovery"
            else self.deep_max_transport_retries
        )
        schema_repairs = (
            self.discovery_max_schema_repairs
            if stage == "discovery"
            else self.deep_max_schema_repairs
        )
        if self.max_transport_retries is not None:
            transport_retries = self.max_transport_retries
        if self.max_schema_repairs is not None:
            schema_repairs = self.max_schema_repairs
        if transport_retries < 0 or schema_repairs < 0:
            raise ValueError("协议控制重试上限必须为非负整数")
        return transport_retries, schema_repairs


@dataclass(frozen=True)
class _PreparedSource:
    source_job_id: str
    source_input: ProtocolDeconstructionInput
    snapshot: ProtocolExtractionSnapshot
    phase_graph: PhaseApplicabilityGraph
    projection: PhaseProjection
    source_spans: tuple[ProtocolSourceSpan, ...]
    workflow_stages: tuple[WorkflowStage, ...]
    coverage_manifest: ProtocolSectionCoverageManifest
    discovery_plan: ProtocolControlDiscoveryPlan


class ProtocolControlJobService:
    """Create idempotent durable control jobs from a frozen deconstruction job."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        data_paths: DataPaths,
        now: Now = utc_now,
        lease_ttl: timedelta = DEFAULT_LEASE_TTL,
        max_discovery_units_per_batch: int = (
            DEFAULT_PROTOCOL_CONTROL_DISCOVERY_BATCH_UNITS
        ),
        discovery_context_radius: int = 1,
        max_deep_units_per_batch: int = 12,
        adaptive_batching: bool | None = None,
        discovery_batch_budget: AdaptiveBatchBudget | None = None,
        discovery_max_parallel: int | None = None,
        actor: str = "系统",
        workflow_stages: Sequence[WorkflowStage] = (),
        discovery_prompt_template: str = DEFAULT_PROTOCOL_CONTROL_DISCOVERY_PROMPT_TEMPLATE,
        deep_prompt_template: str = DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE,
        discovery_step_max_attempts: int = _DEFAULT_OUTER_STEP_ATTEMPTS,
        deep_step_max_attempts: int = _DEFAULT_OUTER_STEP_ATTEMPTS,
        discovery_max_transport_retries: int = DEFAULT_MAX_TRANSPORT_RETRIES,
        discovery_max_schema_repairs: int = DEFAULT_MAX_SCHEMA_REPAIRS,
        deep_max_transport_retries: int = DEFAULT_MAX_TRANSPORT_RETRIES,
        deep_max_schema_repairs: int = DEFAULT_MAX_SCHEMA_REPAIRS,
        route_identity_factory: Callable[[str], str] | None = None,
    ) -> None:
        if discovery_step_max_attempts < 1 or deep_step_max_attempts < 1:
            raise ValueError("协议控制步骤尝试次数必须为正整数")
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("协议控制系统操作人不能为空")
        workflow_stages = tuple(workflow_stages)
        for stage in workflow_stages:
            if not isinstance(stage, WorkflowStage):
                raise ValueError("审核流程节点必须是已冻结的结构化流程合同")
        self._validate_batch_arguments(
            max_discovery_units_per_batch,
            discovery_context_radius,
            max_deep_units_per_batch,
        )
        self.session_factory = session_factory
        self.data_paths = data_paths
        self.now = now
        self.lease_ttl = lease_ttl
        self.max_discovery_units_per_batch = max_discovery_units_per_batch
        self.discovery_context_radius = discovery_context_radius
        self.max_deep_units_per_batch = max_deep_units_per_batch
        resolved_discovery_max_parallel = (
            PROTOCOL_CONTROL_DISCOVERY_MAX_PARALLEL
            if discovery_max_parallel is None
            else discovery_max_parallel
        )
        if (
            isinstance(resolved_discovery_max_parallel, bool)
            or not isinstance(resolved_discovery_max_parallel, int)
            or resolved_discovery_max_parallel < 1
            or resolved_discovery_max_parallel > _MAX_DISCOVERY_PARALLEL
        ):
            raise ValueError("发现步骤并行上限必须是 1 到 32 的整数")
        self.discovery_max_parallel = resolved_discovery_max_parallel
        self.adaptive_batching = (
            PROTOCOL_CONTROL_ADAPTIVE_BATCHING
            if adaptive_batching is None
            else bool(adaptive_batching)
        )
        if discovery_batch_budget is not None:
            self.discovery_batch_budget = discovery_batch_budget
        else:
            self.discovery_batch_budget = default_discovery_batch_budget(
                max_input_tokens=PROTOCOL_CONTROL_DISCOVERY_MAX_INPUT_TOKENS,
                max_output_tokens=PROTOCOL_CONTROL_DISCOVERY_MAX_OUTPUT_TOKENS,
                output_tokens_per_unit=PROTOCOL_CONTROL_DISCOVERY_OUTPUT_TOKENS_PER_UNIT,
                template_overhead_tokens=PROTOCOL_CONTROL_DISCOVERY_TEMPLATE_OVERHEAD_TOKENS,
                chars_per_token=PROTOCOL_CONTROL_DISCOVERY_CHARS_PER_TOKEN,
                max_units_hard_cap=min(
                    self.max_discovery_units_per_batch,
                    PROTOCOL_CONTROL_DISCOVERY_ADAPTIVE_UNIT_CAP,
                ),
            )
        self.actor = actor.strip()
        self.workflow_stages = workflow_stages
        self.discovery_prompt_template = discovery_prompt_template
        self.deep_prompt_template = deep_prompt_template
        self.discovery_step_max_attempts = discovery_step_max_attempts
        self.deep_step_max_attempts = deep_step_max_attempts
        self.discovery_max_transport_retries = discovery_max_transport_retries
        self.discovery_max_schema_repairs = discovery_max_schema_repairs
        self.deep_max_transport_retries = deep_max_transport_retries
        self.deep_max_schema_repairs = deep_max_schema_repairs
        self.route_identity_factory = route_identity_factory
        self.jobs = JobService(session_factory, now=now, lease_ttl=lease_ttl)

    @app_error_boundary
    def create_from_deconstruction(
        self,
        *,
        source_job_id: str,
        idempotency_key: str,
        discovery_source_job_id: str | None = None,
    ) -> ProtocolControlExecutionResult:
        """Freeze the source chain and create the durable execution job atomically."""

        if not source_job_id.strip():
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_SOURCE_MISSING",
                "方案解构任务编号不能为空。",
                status_code=422,
            )
        if not idempotency_key.strip():
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_IDEMPOTENCY_MISSING",
                "幂等标识不能为空。",
                status_code=422,
            )

        with self.session_factory() as session, session.begin():
            prepared = self._prepare_source_in_session(
                session,
                source_job_id=source_job_id,
                max_discovery_units_per_batch=self.max_discovery_units_per_batch,
                discovery_context_radius=self.discovery_context_radius,
            )
            payload = self._job_payload(prepared)
            if discovery_source_job_id is not None:
                store = JobStore(session, now=self.jobs.now)
                try:
                    _validated_discovery_source(
                        store, payload, discovery_source_job_id
                    )
                except (JobNotFoundError, StepFailure) as exc:
                    raise ProtocolControlExecutionError(
                        "PROTOCOL_CONTROL_DISCOVERY_SOURCE_INVALID",
                        "既有方案发现结果与本次原件、批次或模型线路不一致，未建立新任务。",
                        status_code=409,
                    ) from exc
                payload["discovery_source_job_id"] = discovery_source_job_id
            discovery_entries = [
                {
                    "step_id": self._discovery_step_id(batch),
                    "discovery_batch_id": batch.discovery_batch_id,
                }
                for batch in prepared.discovery_plan.batches
            ]
            steps = [
                StepSpec(
                    step_id=entry["step_id"],
                    name=f"发现批次 {number:04d}",
                    max_attempts=self.discovery_step_max_attempts,
                    # Model uncertainty is terminal for automatic execution.
                    # Only an explicit manual job retry may open another
                    # session for this batch.
                    retryable=False,
                )
                for number, entry in enumerate(discovery_entries, start=1)
            ]
            steps.append(
                StepSpec(
                    step_id=STEP_CLOSURE,
                    name="确定性闭包",
                    depends_on=tuple(entry["step_id"] for entry in discovery_entries),
                )
            )
            created = self.jobs.create_job_in_session(
                session,
                idempotency_key=idempotency_key,
                job_type=PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
                payload=payload,
                steps=steps,
            )

        return ProtocolControlExecutionResult(
            job_id=created.job_id,
            state=created.state,
            created=created.created,
            source_job_id=prepared.source_job_id,
            snapshot_id=prepared.snapshot.snapshot_id,
            manifest_id=prepared.coverage_manifest.manifest_id,
        )

    # Naming aliases keep the application boundary discoverable.
    start = create_from_deconstruction
    create_execution = create_from_deconstruction
    start_execution = create_from_deconstruction
    @staticmethod
    def _validate_batch_arguments(
        max_discovery_units_per_batch: int,
        discovery_context_radius: int,
        max_deep_units_per_batch: int,
    ) -> None:
        if (
            isinstance(max_discovery_units_per_batch, bool)
            or max_discovery_units_per_batch < 1
            or max_discovery_units_per_batch > _MAX_BATCH_UNITS
        ):
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_BATCH_SIZE_INVALID",
                "发现批次大小超出允许范围。",
                status_code=422,
            )
        if (
            isinstance(max_deep_units_per_batch, bool)
            or max_deep_units_per_batch < 1
            or max_deep_units_per_batch > _MAX_BATCH_UNITS
        ):
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_DEEP_BATCH_SIZE_INVALID",
                "深析批次大小超出允许范围。",
                status_code=422,
            )
        if (
            isinstance(discovery_context_radius, bool)
            or discovery_context_radius < 0
            or discovery_context_radius > _MAX_CONTEXT_RADIUS
        ):
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_CONTEXT_RADIUS_INVALID",
                "发现上下文范围超出允许范围。",
                status_code=422,
            )

    def _prepare_source_in_session(
        self,
        session: Session,
        *,
        source_job_id: str,
        max_discovery_units_per_batch: int,
        discovery_context_radius: int,
    ) -> _PreparedSource:
        store = JobStore(session, now=self.now, lease_ttl=self.lease_ttl)
        source_job = store.get_job(source_job_id)
        if source_job.job_type != _SOURCE_DECONSTRUCTION_JOB_TYPE:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_SOURCE_TYPE_INVALID",
                "来源任务不是已登记的方案解构任务。",
                status_code=409,
            )
        merged = dict(verify_payload_sha256(source_job.payload_json, source_job.payload_sha256))
        for step_id in _SOURCE_STEP_ORDER:
            for _, checkpoint in store.list_checkpoints(source_job_id, step_id):
                merged.update(
                    {
                        key: value
                        for key, value in checkpoint.items()
                        if key != "attempt"
                    }
                )

        source_input = self._model_from_source(
            merged.get("source_input"), ProtocolDeconstructionInput, "来源方案输入"
        )
        snapshot = self._model_from_source(
            merged.get("extraction_snapshot"),
            ProtocolExtractionSnapshot,
            "来源结构快照",
        )
        phase_graph = self._model_from_source(
            merged.get("phase_graph"), PhaseApplicabilityGraph, "来源期别适用图"
        )
        projection = self._model_from_source(
            merged.get("phase_projection"), PhaseProjection, "来源期别投影"
        )
        if snapshot.status != ExtractionStatus.COMPLETED:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_SNAPSHOT_NOT_COMPLETED",
                "来源方案结构快照尚未完成，不能建立控制任务。",
                status_code=409,
            )
        if snapshot.snapshot_id != source_input.extraction_snapshot_id:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_SNAPSHOT_MISMATCH",
                "来源方案输入与结构快照身份不一致。",
                status_code=409,
            )
        if snapshot.source_sha256 != source_input.protocol_file_sha256:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_SOURCE_HASH_MISMATCH",
                "来源方案输入与结构快照文件摘要不一致。",
                status_code=409,
            )
        if phase_graph.graph_id != projection.graph_id:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_PHASE_GRAPH_MISMATCH",
                "来源期别图与期别投影身份不一致。",
                status_code=409,
            )
        if phase_graph.snapshot_id != snapshot.snapshot_id:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_PHASE_SNAPSHOT_MISMATCH",
                "来源期别图与结构快照身份不一致。",
                status_code=409,
            )
        if projection.selected_phase != source_input.selected_phase:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_PHASE_MISMATCH",
                "来源期别输入与期别投影不一致。",
                status_code=409,
            )
        if projection.projection_id != source_input.phase_projection_id:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_PROJECTION_MISMATCH",
                "来源方案输入与期别投影身份不一致。",
                status_code=409,
            )

        source_spans = self._source_spans(merged.get("source_spans"), snapshot.snapshot_id)
        blocks = self._load_snapshot_blocks(snapshot)
        span_ids_by_ref: dict[str, list[str]] = {}
        for span in source_spans:
            span_ids_by_ref.setdefault(span.source_ref, []).append(span.source_span_id)
        span_map = {
            source_ref: sorted(set(span_ids))
            for source_ref, span_ids in span_ids_by_ref.items()
        }
        allowed_span_ids = set(source_input.allowed_source_span_ids)
        persisted_span_ids = {span.source_span_id for span in source_spans}
        if not allowed_span_ids <= persisted_span_ids:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_SOURCE_SPANS_INCOMPLETE",
                "来源方案输入引用的原文定位未全部持久化。",
                status_code=409,
            )
        try:
            coverage_manifest = build_full_protocol_coverage_manifest(
                blocks,
                projection,
                phase_graph,
                protocol_version_id=source_input.protocol_version_id,
                protocol_document_sha256=source_input.protocol_file_sha256,
                snapshot_id=snapshot.snapshot_id,
                source_span_ids=span_map,
                priority_keywords=(),
            )
            discovery_budget = (
                self.discovery_batch_budget if self.adaptive_batching else None
            )
            discovery_plan = plan_protocol_control_discovery(
                coverage_manifest,
                max_units_per_batch=max_discovery_units_per_batch,
                context_radius=discovery_context_radius,
                batch_budget=discovery_budget,
            )
        except (FullProtocolCoverageError, ProtocolControlPlanningError) as exc:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_PLAN_INVALID",
                "来源方案无法建立完整覆盖清单或发现计划。",
                status_code=409,
            ) from exc
        workflow_stages = self.workflow_stages or _workflow_stages_from_frozen_source(
            source_input
        )
        return _PreparedSource(
            source_job_id=source_job_id,
            source_input=source_input,
            snapshot=snapshot,
            phase_graph=phase_graph,
            projection=projection,
            source_spans=source_spans,
            workflow_stages=workflow_stages,
            coverage_manifest=coverage_manifest,
            discovery_plan=discovery_plan,
        )

    @staticmethod
    def _model_from_source(raw: Any, model_type: Any, label: str) -> Any:
        if not isinstance(raw, Mapping):
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_SOURCE_CHAIN_INCOMPLETE",
                f"{label}未写入来源解构检查点。",
                status_code=409,
            )
        try:
            return model_type.model_validate(raw)
        except (ValidationError, ValueError) as exc:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_SOURCE_CHAIN_INVALID",
                f"{label}内容无法通过冻结合同校验。",
                status_code=409,
            ) from exc

    @staticmethod
    def _source_spans(raw: Any, snapshot_id: str) -> tuple[ProtocolSourceSpan, ...]:
        if isinstance(raw, Mapping):
            values = list(raw.values())
        elif isinstance(raw, list):
            values = raw
        else:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_SOURCE_SPANS_MISSING",
                "来源方案原文定位未写入解构检查点。",
                status_code=409,
            )
        spans: list[ProtocolSourceSpan] = []
        for value in values:
            try:
                span = ProtocolSourceSpan.model_validate(value)
            except (ValidationError, ValueError) as exc:
                raise ProtocolControlExecutionError(
                    "PROTOCOL_CONTROL_SOURCE_SPANS_INVALID",
                    "来源方案原文定位无法通过冻结合同校验。",
                    status_code=409,
                ) from exc
            if span.snapshot_id != snapshot_id:
                raise ProtocolControlExecutionError(
                    "PROTOCOL_CONTROL_SOURCE_SPAN_SNAPSHOT_MISMATCH",
                    "来源方案原文定位与结构快照身份不一致。",
                    status_code=409,
                )
            spans.append(span)
        ids = [span.source_span_id for span in spans]
        if not spans or len(ids) != len(set(ids)):
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_SOURCE_SPANS_INVALID",
                "来源方案原文定位为空或存在重复身份。",
                status_code=409,
            )
        return tuple(sorted(spans, key=lambda span: (span.block_order, span.source_span_id)))

    def _load_snapshot_blocks(
        self,
        snapshot: ProtocolExtractionSnapshot,
    ) -> tuple[StructureBlock, ...]:
        base = self.data_paths.blobs_dir.resolve()
        path = (base / snapshot.content_storage_ref).resolve()
        if path != base and base not in path.parents:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_SNAPSHOT_PATH_INVALID",
                "来源结构快照存储引用不在受控数据目录内。",
                status_code=409,
            )
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_SNAPSHOT_UNAVAILABLE",
                "来源结构快照暂时不可用，不能建立控制任务。",
                status_code=503,
                recovery="请确认持久化数据目录可读后重试；系统不会重新解析原始方案文件。",
            ) from exc
        if hashlib.sha256(content).hexdigest() != snapshot.content_sha256:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_SNAPSHOT_HASH_INVALID",
                "来源结构快照完整性校验失败，不能建立控制任务。",
                status_code=409,
            )
        try:
            raw_blocks = json.loads(content.decode("utf-8"))
            if not isinstance(raw_blocks, list):
                raise ValueError("结构快照不是列表")
            blocks = tuple(StructureBlock.model_validate(item) for item in raw_blocks)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, ValidationError) as exc:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_SNAPSHOT_INVALID",
                "来源结构快照内容无法通过结构合同校验。",
                status_code=409,
            ) from exc
        if not blocks or block_set_hash(blocks) != snapshot.content_sha256:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_SNAPSHOT_HASH_INVALID",
                "来源结构快照内容与持久化摘要不一致。",
                status_code=409,
            )
        return blocks

    def _job_payload(
        self,
        prepared: _PreparedSource,
    ) -> dict[str, Any]:
        discovery_steps = [
            {
                "step_id": self._discovery_step_id(batch),
                "discovery_batch_id": batch.discovery_batch_id,
            }
            for batch in prepared.discovery_plan.batches
        ]
        from app.llm.mtplx_model_lifecycle import local_deployment_job_fields

        try:
            frozen_routes = (
                {
                    stage: self.route_identity_factory(stage)
                    for stage in ("discovery", "deep")
                }
                if self.route_identity_factory is not None
                else None
            )
        except (ValueError, RuntimeError) as exc:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_ROUTE_UNAVAILABLE",
                "方案分析模型配置当前不可用，任务未建立。",
                status_code=503,
            ) from exc
        if frozen_routes is not None and any(
            not isinstance(digest, str) or len(digest) != 64
            for digest in frozen_routes.values()
        ):
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_ROUTE_IDENTITY_INVALID",
                "方案分析模型配置无法冻结，任务未建立。",
                status_code=503,
            )

        return {
            "execution_version": PROTOCOL_CONTROL_EXECUTION_VERSION,
            "frozen_model_routes": frozen_routes,
            **local_deployment_job_fields(),
            "source_deconstruction_job_id": prepared.source_job_id,
            "actor": self.actor,
            "source_snapshot_id": prepared.snapshot.snapshot_id,
            "source_content_sha256": prepared.snapshot.content_sha256,
            "source_input": prepared.source_input.model_dump(mode="json"),
            "extraction_snapshot": prepared.snapshot.model_dump(mode="json"),
            "phase_graph": prepared.phase_graph.model_dump(mode="json"),
            "phase_projection": prepared.projection.model_dump(mode="json"),
            "source_spans": {
                span.source_span_id: span.model_dump(mode="json")
                for span in prepared.source_spans
            },
            "coverage_manifest": prepared.coverage_manifest.model_dump(mode="json"),
            "discovery_plan": prepared.discovery_plan.model_dump(mode="json"),
            "discovery_step_ids": discovery_steps,
            "max_deep_units_per_batch": self.max_deep_units_per_batch,
            "discovery_step_max_attempts": self.discovery_step_max_attempts,
            "deep_step_max_attempts": self.deep_step_max_attempts,
            "workflow_stages": [
                stage.model_dump(mode="json") for stage in prepared.workflow_stages
            ],
            "prompt_templates": {
                "discovery": self.discovery_prompt_template,
                "deep": self.deep_prompt_template,
            },
            "runner_limits": {
                "discovery_max_transport_retries": self.discovery_max_transport_retries,
                "discovery_max_schema_repairs": self.discovery_max_schema_repairs,
                "deep_max_transport_retries": self.deep_max_transport_retries,
                "deep_max_schema_repairs": self.deep_max_schema_repairs,
            },
            "adaptive_batching": {
                "enabled": self.adaptive_batching,
                "packing_mode": (
                    "adaptive_token_budget"
                    if self.adaptive_batching
                    else "fixed_unit_count"
                ),
                "budget": {
                    "max_input_tokens": self.discovery_batch_budget.max_input_tokens,
                    "max_output_tokens": self.discovery_batch_budget.max_output_tokens,
                    "output_tokens_per_unit": (
                        self.discovery_batch_budget.output_tokens_per_unit
                    ),
                    "template_overhead_tokens": (
                        self.discovery_batch_budget.template_overhead_tokens
                    ),
                    "chars_per_token": self.discovery_batch_budget.chars_per_token,
                    "max_units_hard_cap": self.discovery_batch_budget.max_units_hard_cap,
                },
                "notes": [
                    "Do not resume paused fixed-unit serial discovery jobs under a mixed adaptive config.",
                    "Adaptive packing is project-agnostic and never drops coverage.",
                    "Discovery concurrency is frozen per job and never applies to deep/hydrate/gate.",
                ],
            },
            "execution_control": {
                "schema": PROTOCOL_CONTROL_EXECUTION_CONTROL_SCHEMA,
                "max_parallel_steps": self.discovery_max_parallel,
                "parallelizable_step_ids": [
                    entry["step_id"] for entry in discovery_steps
                ],
                "parallel_scope": "discovery_batches_only",
                "notes": [
                    "Only explicitly listed independent discovery steps may share one lease wave.",
                    "Jobs without execution_control keep the historical serial runner path.",
                    "Do not rewrite paused serial discovery jobs to a mixed parallel config.",
                ],
            },
        }

    @staticmethod
    def _discovery_step_id(batch: ProtocolControlDiscoveryBatch) -> str:
        return f"{_DISCOVERY_STEP_PREFIX}{batch.batch_number:04d}"


def _workflow_stages_from_frozen_source(
    source_input: ProtocolDeconstructionInput,
) -> tuple[WorkflowStage, ...]:
    """Build one stable review node per frozen stage and visit identity."""

    stages: list[WorkflowStage] = []
    seen: set[tuple[str, str]] = set()
    for item in sorted(
        source_input.required_procedure_catalog.items,
        key=lambda value: value.position,
    ):
        if item.review_stage is None or not item.visit_instance:
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_WORKFLOW_SOURCE_INVALID",
                "冻结必做项目缺少审核阶段或访视实例，不能建立方案控制任务。",
                status_code=409,
            )
        key = (item.review_stage.value, item.visit_instance)
        if key in seen:
            continue
        seen.add(key)
        identity = hashlib.sha256("\0".join(key).encode("utf-8")).hexdigest()[:16]
        stages.append(
            WorkflowStage(
                workflow_stage_id=f"workflow-stage-{identity}",
                stage=item.review_stage,
                display_name=item.visit_instance,
                visit_instance=item.visit_instance,
            )
        )
    return tuple(stages)


# ---------------------------------------------------------------------------
# Step executor
# ---------------------------------------------------------------------------


def create_protocol_control_executor(
    config: ProtocolControlExecutorConfig,
) -> StepExecutor:
    """Create the only executor for ``protocol_control_execution`` jobs."""

    def execute(context: StepContext) -> dict[str, Any] | PreparedStepResult:
        try:
            if context.job_payload.get("execution_version") != PROTOCOL_CONTROL_EXECUTION_VERSION:
                raise StepFailure(
                    retryable=False,
                    error_code="PROTOCOL_CONTROL_EXECUTION_VERSION_MISMATCH",
                    detail="此任务使用较早的整理要求，不能与当前版本混合续算；原结果保留，请从方案整理建立新任务。",
                )
            if context.last_checkpoint is not None:
                return _replay_checkpoint(context)
            from app.llm.mtplx_model_lifecycle import MtplxOwnershipError, require_local_deployment_job

            try:
                require_local_deployment_job(context.job_payload)
            except MtplxOwnershipError as exc:
                raise StepFailure(retryable=False, error_code="MODEL_DEPLOYMENT_CHANGED", detail=str(exc)) from exc
            if context.step_id.startswith(_DISCOVERY_STEP_PREFIX):
                return _execute_discovery(context, config)
            if context.step_id == STEP_CLOSURE:
                return _execute_closure(context, config)
            if context.step_id.startswith(_DEEP_STEP_PREFIX):
                return _execute_deep(context, config)
            if context.step_id == STEP_HYDRATE:
                return _execute_hydrate(context, config)
            if context.step_id == STEP_GATE:
                return _execute_gate(context, config)
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_STEP_UNSUPPORTED",
                detail="当前方案控制阶段无法识别，任务已安全停止。",
            )
        except StepFailure:
            raise
        except ProtocolControlGateError as exc:
            raise StepFailure(
                retryable=False,
                error_code=exc.code,
                detail=str(exc)[:4000],
            ) from exc
        except ProtocolControlPlanningError as exc:
            raise StepFailure(
                retryable=False,
                error_code=exc.code,
                detail=str(exc)[:4000],
            ) from exc
        except (ValidationError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
                detail=f"方案控制持久合同无法通过校验：{str(exc)[:3500]}",
            ) from exc
        except OSError as exc:
            raise StepFailure(
                retryable=True,
                error_code="PROTOCOL_CONTROL_STORAGE_UNAVAILABLE",
                detail="方案控制持久数据暂时不可用，请稍后重试。",
            ) from exc

    return execute


def _replay_checkpoint(context: StepContext) -> dict[str, Any]:
    """Validate a completed checkpoint without re-calling a model or source file."""

    checkpoint = dict(context.last_checkpoint or {})
    stage = checkpoint.get("stage")
    if stage == "discovery":
        run_result = ProtocolControlDiscoveryAgentRunResult.model_validate(
            checkpoint.get("run_result")
        )
        if run_result.status != "已解析" or run_result.final_output is None:
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
                detail="发现阶段已保存的结果不是可恢复的完整结果。",
            )
        if run_result.discovery_batch_id != checkpoint.get("discovery_batch_id"):
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
                detail="发现阶段检查点身份不一致。",
            )
        return checkpoint
    if stage == "deep":
        run_result = ProtocolControlAgentRunResult.model_validate(
            checkpoint.get("run_result")
        )
        if run_result.status != "已解析" or run_result.final_output is None:
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
                detail="深析阶段已保存的结果不是可恢复的完整结果。",
            )
        if run_result.batch_id != checkpoint.get("batch_id"):
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
                detail="深析阶段检查点身份不一致。",
            )
        return checkpoint
    if stage == "closure":
        ProtocolControlDiscoveryToDeepPlan.model_validate(checkpoint.get("deep_plan"))
        ProtocolControlBatchPlan.model_validate(checkpoint.get("publication_plan"))
        return checkpoint
    if stage == "hydrate":
        ProtocolControlBatchPlan.model_validate(checkpoint.get("publication_plan"))
        results = checkpoint.get("batch_dispositions")
        if not isinstance(results, list) or not results:
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
                detail="水合阶段检查点缺少完整批次结果。",
            )
        for result in results:
            ProtocolControlBatchDispositionHydrated.model_validate(result)
        return checkpoint
    if stage == "gate":
        if checkpoint.get("result_kind") != CANDIDATE_CONTROL_PACKAGE_RESULT_KIND:
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
                detail="最终检查点必须明确标记为水合候选控制点包。",
            )
        if checkpoint.get("formal_catalog_status") != FORMAL_CATALOG_STATUS_NOT_MATERIALIZED:
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
                detail="候选控制点包不得伪装为已物化的正式控制目录。",
            )
        if checkpoint.get("accepted") is not True:
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
                detail="候选控制点包门禁检查点未记录已接受状态。",
            )
        if checkpoint.get("gate_version") != CONTROL_PUBLICATION_GATE_VERSION:
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
                detail="发布门禁版本与检查点不一致。",
            )
        ProtocolControlBatchPlan.model_validate(checkpoint.get("publication_plan"))
        results = checkpoint.get("batch_dispositions")
        if not isinstance(results, list) or not results:
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
                detail="候选控制点包缺少已验证批次处置。",
            )
        validated_results = [
            ProtocolControlBatchDispositionHydrated.model_validate(item)
            for item in results
        ]
        candidate_ids = checkpoint.get("candidate_ids")
        if not isinstance(candidate_ids, list) or any(
            not isinstance(item, str) or not item for item in candidate_ids
        ):
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
                detail="候选控制点包缺少有效候选身份。",
            )
        expected_candidate_ids = sorted(
            {
                candidate.control_candidate_id
                for result in validated_results
                for candidate in result.candidates
            }
        )
        if candidate_ids != expected_candidate_ids:
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
                detail="候选身份与已验证批次处置不一致。",
            )
        return checkpoint
    raise StepFailure(
        retryable=False,
        error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
        detail="方案控制检查点阶段无法识别。",
    )


def _payload_model(
    context: StepContext,
    key: str,
    model_type: Any,
) -> Any:
    return model_type.model_validate(context.job_payload.get(key))


def _prompt_from_payload(context: StepContext, stage: str, config: ProtocolControlExecutorConfig) -> str:
    templates = context.job_payload.get("prompt_templates")
    if isinstance(templates, Mapping) and isinstance(templates.get(stage), str):
        prompt = templates[stage]
    else:
        prompt = config.prompt_for(stage)
    if not prompt.strip():
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_PROMPT_INVALID",
            detail="方案控制模型提示模板不能为空。",
        )
    return prompt


def _limits_from_payload(
    context: StepContext,
    stage: str,
    config: ProtocolControlExecutorConfig,
) -> tuple[int, int]:
    limits = context.job_payload.get("runner_limits")
    if isinstance(limits, Mapping):
        prefix = "discovery" if stage == "discovery" else "deep"
        transport_retries = limits.get(f"{prefix}_max_transport_retries")
        schema_repairs = limits.get(f"{prefix}_max_schema_repairs")
        if isinstance(transport_retries, int) and isinstance(schema_repairs, int):
            if transport_retries < 0 or schema_repairs < 0:
                raise StepFailure(
                    retryable=False,
                    error_code="PROTOCOL_CONTROL_RUNNER_LIMIT_INVALID",
                    detail="方案控制模型修复预算无效。",
                )
            return transport_retries, schema_repairs
    return config.limits_for(stage)


def _transport_identity(transport: Any, *, stage: str) -> dict[str, Any]:
    """Persist non-secret adapter identity so retries remain auditable."""

    identity: dict[str, Any] = {
        "stage": stage,
        "transport_class": f"{type(transport).__module__}.{type(transport).__qualname__}",
    }
    for name in (
        "provider",
        "backend",
        "model",
        "reasoning_effort",
        "max_tokens",
        "base_url",
        "temperature",
        "timeout",
        "max_retries",
        "response_format_sha256",
        "response_format_mode",
        "model_identity_policy",
    ):
        try:
            value = getattr(transport, name)
        except Exception:  # noqa: BLE001 - identity is best effort and secret-free
            continue
        if callable(value):
            continue
        if value is None or isinstance(value, (str, int, float, bool)):
            identity[name] = value
    return identity


def _transport_identity_digest(transport: Any, *, stage: str) -> str:
    identity = _transport_identity(transport, stage=stage)
    payload = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def protocol_control_route_identity_from_config(
    config: ProtocolControlExecutorConfig, *, stage: str
) -> str:
    """Resolve a route without requesting inference, then release its client."""

    owns_transport = all(
        value is None
        for value in (
            config.discovery_transport if stage == "discovery" else config.deep_transport,
            config.discovery_transport_factory if stage == "discovery" else config.deep_transport_factory,
            config.transport,
            config.transport_factory,
        )
    )
    transport = _resolve_transport(config, stage=stage)
    try:
        return _transport_identity_digest(transport, stage=stage)
    finally:
        # Injected transports/factories can be shared with an executor.
        if owns_transport:
            client = getattr(transport, "_client", None)
            close = getattr(client, "close", None)
            if callable(close):
                close()


def _require_frozen_route(
    context: StepContext,
    config: ProtocolControlExecutorConfig,
    transport: Any,
    *,
    stage: str,
) -> None:
    routes = context.job_payload.get("frozen_model_routes")
    if routes is None and not config.require_frozen_routes:
        return
    expected = routes.get(stage) if isinstance(routes, Mapping) else None
    if not isinstance(expected, str) or expected != _transport_identity_digest(
        transport, stage=stage
    ):
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_ROUTE_CHANGED",
            detail="方案分析任务的模型线路与建立任务时不同；原进度保留，请使用原配置或建立新任务。",
        )


def _resolve_transport(
    config: ProtocolControlExecutorConfig,
    *,
    stage: str,
) -> Any:
    if stage == "discovery":
        if config.discovery_transport is not None:
            return config.discovery_transport
        if config.discovery_transport_factory is not None:
            return config.discovery_transport_factory()
        if config.transport is not None:
            return config.transport
        if config.transport_factory is not None:
            return config.transport_factory()
        return protocol_control_discovery_transport_from_environment()
    if config.deep_transport is not None:
        return config.deep_transport
    if config.deep_transport_factory is not None:
        return config.deep_transport_factory()
    if config.transport is not None:
        return config.transport
    if config.transport_factory is not None:
        return config.transport_factory()
    return protocol_control_transport_from_environment()


def _discovery_batch_for_step(
    context: StepContext,
) -> ProtocolControlDiscoveryBatch:
    plan = _payload_model(context, "discovery_plan", ProtocolControlDiscoveryPlan)
    mapping = context.job_payload.get("discovery_step_ids")
    if not isinstance(mapping, list):
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_PLAN_INVALID",
            detail="发现步骤映射缺失。",
        )
    entry = next(
        (
            value
            for value in mapping
            if isinstance(value, Mapping) and value.get("step_id") == context.step_id
        ),
        None,
    )
    if entry is None:
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_PLAN_INVALID",
            detail="发现步骤未绑定冻结批次。",
        )
    batch_id = entry.get("discovery_batch_id")
    for batch in plan.batches:
        if batch.discovery_batch_id == batch_id:
            return batch
    raise StepFailure(
        retryable=False,
        error_code="PROTOCOL_CONTROL_PLAN_INVALID",
        detail="发现步骤引用了不存在的冻结批次。",
    )


def _validated_discovery_source(
    store: JobStore,
    current_payload: Mapping[str, Any],
    source_job_id: str,
    *,
    step_id: str | None = None,
) -> dict[str, tuple[str, dict[str, Any]]]:
    """Reuse accepted model decisions only when their complete discovery input matches."""

    source_job = store.get_job(source_job_id)
    if source_job.job_type != PROTOCOL_CONTROL_EXECUTION_JOB_TYPE:
        raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DISCOVERY_SOURCE_INVALID", detail="发现来源任务类型不符。")
    source_payload = verify_payload_sha256(source_job.payload_json, source_job.payload_sha256)
    for key in (
        "source_deconstruction_job_id", "source_snapshot_id", "source_content_sha256",
        "source_input", "extraction_snapshot", "phase_graph", "phase_projection",
        "source_spans", "coverage_manifest", "discovery_plan", "discovery_step_ids",
    ):
        if source_payload.get(key) != current_payload.get(key):
            raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DISCOVERY_SOURCE_INVALID", detail="发现来源与当前冻结原件或批次不一致。")
    source_prompts = source_payload.get("prompt_templates")
    current_prompts = current_payload.get("prompt_templates")
    if (
        not isinstance(source_prompts, Mapping)
        or not isinstance(current_prompts, Mapping)
        or source_prompts.get("discovery") != current_prompts.get("discovery")
    ):
        raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DISCOVERY_SOURCE_INVALID", detail="发现提示版本不一致。")
    source_routes = source_payload.get("frozen_model_routes")
    current_routes = current_payload.get("frozen_model_routes")
    if (
        not isinstance(source_routes, Mapping)
        or not isinstance(current_routes, Mapping)
        or not isinstance(current_routes.get("discovery"), str)
        or source_routes.get("discovery") != current_routes.get("discovery")
    ):
        raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DISCOVERY_SOURCE_INVALID", detail="发现模型线路身份不一致。")
    prompt_sha = protocol_control_discovery_prompt_template_sha256(
        current_prompts["discovery"]
    )
    plan = ProtocolControlDiscoveryPlan.model_validate(current_payload["discovery_plan"])
    mapping = current_payload["discovery_step_ids"]
    steps = {item.step_id: item for item in store.list_steps(source_job_id)}
    validated: dict[str, tuple[str, dict[str, Any]]] = {}
    for entry, batch in zip(mapping, plan.batches, strict=True):
        entry_step_id = entry["step_id"]
        if step_id is not None and entry_step_id != step_id:
            continue
        if entry["discovery_batch_id"] != batch.discovery_batch_id:
            raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DISCOVERY_SOURCE_INVALID", detail="发现批次映射不一致。")
        source_step = steps.get(entry_step_id)
        checkpoint = store.get_last_checkpoint(source_job_id, entry_step_id)
        if source_step is None or source_step.state != "completed" or checkpoint is None:
            raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DISCOVERY_SOURCE_INVALID", detail="发现来源包含未完成批次。")
        checkpoint_id, saved = checkpoint
        identity = saved.get("transport_identity")
        if (
            saved.get("stage") != "discovery"
            or saved.get("discovery_batch_id") != batch.discovery_batch_id
            or saved.get("prompt_template_sha256") != prompt_sha
            or not isinstance(identity, Mapping)
            or hashlib.sha256(
                json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest() != current_routes["discovery"]
        ):
            raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DISCOVERY_SOURCE_INVALID", detail="发现来源回执身份不一致。")
        result = ProtocolControlDiscoveryAgentRunResult.model_validate(saved.get("run_result"))
        if (
            result.status != "已解析"
            or result.final_output is None
            or result.discovery_batch_id != batch.discovery_batch_id
            or [item.structure_unit_id for item in result.final_output]
            != batch.target_structure_unit_ids
        ):
            raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DISCOVERY_SOURCE_INVALID", detail="发现来源未完整覆盖原文单元。")
        validated[entry_step_id] = checkpoint_id, saved
    if step_id is not None and step_id not in validated:
        raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DISCOVERY_SOURCE_INVALID", detail="当前发现批次不在来源任务中。")
    return validated


def _execute_discovery(
    context: StepContext,
    config: ProtocolControlExecutorConfig,
) -> dict[str, Any]:
    batch = _discovery_batch_for_step(context)
    prompt_template = _prompt_from_payload(context, "discovery", config)
    max_transport_retries, max_schema_repairs = _limits_from_payload(
        context, "discovery", config
    )
    transport = _resolve_transport(config, stage="discovery")
    _require_frozen_route(context, config, transport, stage="discovery")
    source_job_id = context.job_payload.get("discovery_source_job_id")
    if source_job_id is not None:
        if not isinstance(source_job_id, str) or source_job_id == context.job_id:
            raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DISCOVERY_SOURCE_INVALID", detail="发现来源任务编号无效。")
        with config.session_factory() as session:
            store = JobStore(session, now=config.now)
            checkpoint_id, saved = _validated_discovery_source(
                store, context.job_payload, source_job_id, step_id=context.step_id
            )[context.step_id]
        return {
            **saved,
            "adopted_from": {"job_id": source_job_id, "checkpoint_id": checkpoint_id},
        }
    result = ProtocolControlDiscoveryAgentRunner(
        max_transport_retries=max_transport_retries,
        max_schema_repairs=max_schema_repairs,
    ).run(
        batch,
        transport,
        prompt_template=prompt_template,
    )
    if result.status != "已解析" or result.final_output is None:
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_DISCOVERY_NEEDS_REVIEW",
            detail=_run_diagnostics(
                result.attempts,
                "发现批次未产出可接受的完整结果；本步骤已进入人工核对边界，"
                "外层 JobRunner 不会自动新建模型会话。"
                "仅人工调用任务重试后才会再次执行该批次。",
            ),
        )
    return {
        "stage": "discovery",
        "discovery_batch_id": batch.discovery_batch_id,
        "prompt_template_sha256": protocol_control_discovery_prompt_template_sha256(
            prompt_template
        ),
        "transport_identity": _transport_identity(transport, stage="discovery"),
        "run_result": result.model_dump(mode="json"),
    }


def _discovery_results_for_job(
    context: StepContext,
    config: ProtocolControlExecutorConfig,
) -> tuple[ProtocolControlDiscoveryPlan, list[list[ProtocolControlDiscoveryDecision]]]:
    plan = _payload_model(context, "discovery_plan", ProtocolControlDiscoveryPlan)
    mapping = context.job_payload.get("discovery_step_ids")
    if not isinstance(mapping, list) or len(mapping) != len(plan.batches):
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_PLAN_INVALID",
            detail="发现计划与持久步骤映射不一致。",
        )
    batch_decisions: list[list[ProtocolControlDiscoveryDecision]] = []
    with config.session_factory() as session:
        store = JobStore(session, now=config.now)
        for entry, batch in zip(mapping, plan.batches, strict=True):
            if not isinstance(entry, Mapping):
                raise StepFailure(
                    retryable=False,
                    error_code="PROTOCOL_CONTROL_PLAN_INVALID",
                    detail="发现步骤映射内容无效。",
                )
            step_id = entry.get("step_id")
            if not isinstance(step_id, str) or entry.get("discovery_batch_id") != batch.discovery_batch_id:
                raise StepFailure(
                    retryable=False,
                    error_code="PROTOCOL_CONTROL_PLAN_INVALID",
                    detail="发现步骤映射身份不一致。",
                )
            checkpoint = store.get_last_checkpoint(context.job_id, step_id)
            if checkpoint is None:
                raise StepFailure(
                    retryable=False,
                    error_code="PROTOCOL_CONTROL_DISCOVERY_INCOMPLETE",
                    detail="发现阶段仍缺少已接受的批次结果。",
                )
            _, payload = checkpoint
            run_result = ProtocolControlDiscoveryAgentRunResult.model_validate(
                payload.get("run_result")
            )
            if (
                run_result.status != "已解析"
                or run_result.final_output is None
                or run_result.discovery_batch_id != batch.discovery_batch_id
            ):
                raise StepFailure(
                    retryable=False,
                    error_code="PROTOCOL_CONTROL_DISCOVERY_INCOMPLETE",
                    detail="发现阶段存在未接受或身份不一致的批次结果。",
                )
            batch_decisions.append(list(run_result.final_output))
    return plan, batch_decisions


def _closure_checkpoint(
    context: StepContext,
    config: ProtocolControlExecutorConfig,
) -> dict[str, Any]:
    with config.session_factory() as session:
        store = JobStore(session, now=config.now)
        checkpoint = store.get_last_checkpoint(context.job_id, STEP_CLOSURE)
    if checkpoint is None:
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_CLOSURE_MISSING",
            detail="确定性闭包检查点缺失。",
        )
    return checkpoint[1]


def _execute_closure(
    context: StepContext,
    config: ProtocolControlExecutorConfig,
) -> PreparedStepResult:
    coverage_manifest = _payload_model(
        context, "coverage_manifest", ProtocolSectionCoverageManifest
    )
    discovery_plan, batch_decisions = _discovery_results_for_job(context, config)
    decisions = validate_protocol_control_discovery_results(
        discovery_plan,
        batch_decisions,
    )
    source_input = _payload_model(context, "source_input", ProtocolDeconstructionInput)
    workflow_stages = tuple(
        WorkflowStage.model_validate(item)
        for item in context.job_payload.get("workflow_stages", [])
    )
    deep_plan = plan_protocol_control_deep_batches_from_discovery(
        coverage_manifest,
        discovery_plan,
        batch_decisions,
        official_parent_catalog=source_input.parent_rule_catalog,
        required_procedure_catalog=source_input.required_procedure_catalog,
        max_owned_units_per_batch=int(context.job_payload["max_deep_units_per_batch"]),
        workflow_stages=workflow_stages,
    )
    publication_plan = _build_publication_plan(coverage_manifest, deep_plan)
    deep_steps = [
        {
            "step_id": f"{_DEEP_STEP_PREFIX}{batch.batch_number:04d}",
            "batch_id": batch.batch_id,
        }
        for batch in deep_plan.batches
    ]
    checkpoint = {
        "stage": "closure",
        "coverage_manifest_id": coverage_manifest.manifest_id,
        "discovery_plan_id": discovery_plan.plan_id,
        "discovery_decisions": [
            item.model_dump(mode="json") for item in deep_plan.discovery_decisions
        ],
        "deep_plan": deep_plan.model_dump(mode="json"),
        "publication_plan": publication_plan.model_dump(mode="json"),
        "deep_step_ids": deep_steps,
        "non_deep_structure_unit_ids": list(deep_plan.non_deep_structure_unit_ids),
        "manifest_structure_unit_ids_sha256": stable_protocol_control_manifest_structure_unit_ids_sha256(
            [unit.structure_unit_id for unit in coverage_manifest.units]
        ),
    }

    def apply(session: Session) -> None:
        store = JobStore(session, now=config.now)
        job = store.get_job(context.job_id)
        existing_steps = {step.step_id: step for step in store.list_steps(context.job_id)}
        for number, batch in enumerate(deep_plan.batches, start=1):
            step_id = f"{_DEEP_STEP_PREFIX}{number:04d}"
            if step_id not in existing_steps:
                store.create_step(
                    step_id=step_id,
                    job_id=context.job_id,
                    name=f"深析批次 {number:04d}",
                    max_attempts=int(
                        context.job_payload.get(
                            "deep_step_max_attempts", _DEFAULT_OUTER_STEP_ATTEMPTS
                        )
                    ),
                    # See discovery steps: model uncertainty is terminal for
                    # automatic execution and only explicit manual retry may
                    # call the model again.
                    retryable=False,
                    depends_on=(STEP_CLOSURE,),
                )
        existing_steps = {step.step_id: step for step in store.list_steps(context.job_id)}
        if STEP_HYDRATE not in existing_steps:
            store.create_step(
                step_id=STEP_HYDRATE,
                job_id=context.job_id,
                name="聚合水合结果",
                depends_on=tuple(
                    f"{_DEEP_STEP_PREFIX}{number:04d}"
                    for number in range(1, len(deep_plan.batches) + 1)
                )
                or (STEP_CLOSURE,),
            )
        existing_steps = {step.step_id: step for step in store.list_steps(context.job_id)}
        if STEP_GATE not in existing_steps:
            store.create_step(
                step_id=STEP_GATE,
                job_id=context.job_id,
                name="发布门禁",
                depends_on=(STEP_HYDRATE,),
            )
        job.progress_total = len(store.list_steps(context.job_id))
        job.updated_at = config.now()
        session.flush()

    return PreparedStepResult(checkpoint=checkpoint, apply=apply)


def _deep_batch_for_step(
    context: StepContext,
    deep_plan: ProtocolControlDiscoveryToDeepPlan,
) -> ProtocolControlDispositionBatch:
    mapping = context.job_payload.get("deep_step_ids")
    if not isinstance(mapping, list):
        # The mapping is normally in the closure checkpoint, not the original job.
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_DEEP_PLAN_INVALID",
            detail="深析步骤映射缺失。",
        )
    entry = next(
        (
            value
            for value in mapping
            if isinstance(value, Mapping) and value.get("step_id") == context.step_id
        ),
        None,
    )
    if entry is None:
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_DEEP_PLAN_INVALID",
            detail="深析步骤未绑定冻结批次。",
        )
    batch_id = entry.get("batch_id")
    for batch in deep_plan.batches:
        if batch.batch_id == batch_id:
            return batch
    raise StepFailure(
        retryable=False,
        error_code="PROTOCOL_CONTROL_DEEP_PLAN_INVALID",
        detail="深析步骤引用了不存在的冻结批次。",
    )


def _validate_deep_batch_output(
    batch: ProtocolControlDispositionBatch,
    output: ProtocolControlBatchDispositionHydrated,
) -> None:
    """Use the product's scoped repair contract for a frozen deep batch."""

    errors = check_protocol_control_batch_candidates(batch, output)
    if not errors:
        return
    structural_codes = CANDIDATE_REPARTITION_GATE_CODES | SOURCE_CLOSURE_REWRITE_GATE_CODES
    if any(error.code == "ENROLLMENT_PROHIBITION_UNCOVERED" for error in errors):
        errors = tuple(
            error for error in errors
            if error.code == "ENROLLMENT_PROHIBITION_UNCOVERED"
        )
    # Structural regrouping changes candidate identities. Resolve it before
    # independent field repairs so the granted repair scope remains exact.
    if any(error.code in structural_codes for error in errors):
        errors = tuple(error for error in errors if error.code in structural_codes)
    candidate_by_id = {
        candidate.control_candidate_id: candidate
        for candidate in output.candidates
    }
    raise publication_repair_error(
        issues=[
            ProtocolControlGateIssue(
                code=error.code,
                message=error.message,
                entity_id=error.entity_id,
                structure_unit_ids=error.structure_unit_ids,
                candidate_ids=error.candidate_ids,
                obligation_source_span_ids=error.obligation_source_span_ids,
            )
            for error in errors
        ],
        candidate_by_id=candidate_by_id,
        control_to_candidate={},
        default_structure_unit_ids=list(batch.owned_structure_unit_ids),
    )


def _execute_deep(
    context: StepContext,
    config: ProtocolControlExecutorConfig,
) -> dict[str, Any]:
    closure = _closure_checkpoint(context, config)
    deep_plan = ProtocolControlDiscoveryToDeepPlan.model_validate(closure["deep_plan"])
    # The dynamic mapping is part of the closure checkpoint.  Keep it in a
    # local context copy so the executor remains independent of mutable state.
    job_payload = dict(context.job_payload)
    job_payload["deep_step_ids"] = closure.get("deep_step_ids", [])
    effective_context = StepContext(
        job_id=context.job_id,
        job_type=context.job_type,
        job_payload=job_payload,
        step_id=context.step_id,
        name=context.name,
        attempt=context.attempt,
        last_checkpoint_id=context.last_checkpoint_id,
        last_checkpoint=context.last_checkpoint,
        max_attempts=context.max_attempts,
    )
    batch = _deep_batch_for_step(effective_context, deep_plan)
    prompt_template = _prompt_from_payload(context, "deep", config)
    max_transport_retries, max_schema_repairs = _limits_from_payload(
        context, "deep", config
    )
    transport = _resolve_transport(config, stage="deep")
    _require_frozen_route(context, config, transport, stage="deep")

    result = ProtocolControlAgentRunner(
        max_transport_retries=max_transport_retries,
        max_schema_repairs=max_schema_repairs,
    ).run(
        batch,
        transport,
        prompt_template=prompt_template,
        output_validator=lambda output: _validate_deep_batch_output(batch, output),
    )
    if result.status != "已解析" or result.final_output is None:
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID",
            detail=_run_diagnostics(
                result.attempts,
                "深析批次在限定修复次数内未产出合规输出。",
            ),
            diagnostic_checkpoint={
                "stage": "deep_failure_diagnostic",
                "schema_version": "phase5/deep-failure-diagnostic/v2",
                "batch_id": batch.batch_id,
                "prompt_template_sha256": protocol_control_agent_prompt_template_sha256(
                    prompt_template
                ),
                "transport_identity": _transport_identity(transport, stage="deep"),
                "source_interpretation": (
                    result.source_interpretation.model_dump(mode="json")
                    if result.source_interpretation is not None else None
                ),
                "source_statement_coverage": [
                    item.model_dump(mode="json")
                    for item in result.source_statement_coverage
                ],
                "source_target_review": (
                    result.source_target_review.model_dump(mode="json")
                    if result.source_target_review is not None else None
                ),
                "attempts": [
                    {
                        "attempt": item.attempt,
                        "outcome": item.outcome,
                        "raw_output_sha256": item.raw_output_sha256,
                        "raw_output_chars": item.raw_output_chars,
                        "raw_output_text": item.raw_output_text,
                        "error_classes": item.error_classes,
                        "issues": item.issues,
                    }
                    for item in result.attempts
                ],
            },
        )
    return {
        "stage": "deep",
        "batch_id": batch.batch_id,
        "prompt_template_sha256": protocol_control_agent_prompt_template_sha256(
            prompt_template
        ),
        "transport_identity": _transport_identity(transport, stage="deep"),
        "run_result": result.model_dump(mode="json"),
    }


def _deep_results(
    context: StepContext,
    config: ProtocolControlExecutorConfig,
    closure: Mapping[str, Any],
) -> dict[str, ProtocolControlBatchDispositionHydrated]:
    deep_plan = ProtocolControlDiscoveryToDeepPlan.model_validate(closure["deep_plan"])
    deep_step_ids = closure.get("deep_step_ids") or []
    if not isinstance(deep_step_ids, list) or len(deep_step_ids) != len(deep_plan.batches):
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_DEEP_PLAN_INVALID",
            detail="深析步骤与冻结批次数量不一致。",
        )
    output: dict[str, ProtocolControlBatchDispositionHydrated] = {}
    with config.session_factory() as session:
        store = JobStore(session, now=config.now)
        for entry, batch in zip(deep_step_ids, deep_plan.batches, strict=True):
            if not isinstance(entry, Mapping):
                raise StepFailure(
                    retryable=False,
                    error_code="PROTOCOL_CONTROL_DEEP_PLAN_INVALID",
                    detail="深析步骤映射内容无效。",
                )
            step_id = entry.get("step_id")
            if entry.get("batch_id") != batch.batch_id or not isinstance(step_id, str):
                raise StepFailure(
                    retryable=False,
                    error_code="PROTOCOL_CONTROL_DEEP_PLAN_INVALID",
                    detail="深析步骤映射身份不一致。",
                )
            checkpoint = store.get_last_checkpoint(context.job_id, step_id)
            if checkpoint is None:
                raise StepFailure(
                    retryable=False,
                    error_code="PROTOCOL_CONTROL_DEEP_INCOMPLETE",
                    detail="深析阶段仍缺少已接受的批次结果。",
                )
            _, payload = checkpoint
            run_result = ProtocolControlAgentRunResult.model_validate(
                payload.get("run_result")
            )
            if (
                run_result.status != "已解析"
                or run_result.final_output is None
                or run_result.batch_id != batch.batch_id
            ):
                raise StepFailure(
                    retryable=False,
                    error_code="PROTOCOL_CONTROL_DEEP_INCOMPLETE",
                    detail="深析阶段存在未接受或身份不一致的批次结果。",
                )
            result = run_result.final_output
            if list(result.owned_structure_unit_ids) != list(batch.owned_structure_unit_ids):
                raise StepFailure(
                    retryable=False,
                    error_code="PROTOCOL_CONTROL_DEEP_SCOPE_INVALID",
                    detail="深析结果未闭合到冻结 owned 结构单元。",
                )
            output[batch.batch_id] = result
    return output


def _execute_hydrate(
    context: StepContext,
    config: ProtocolControlExecutorConfig,
) -> dict[str, Any]:
    closure = _closure_checkpoint(context, config)
    coverage_manifest = _payload_model(
        context, "coverage_manifest", ProtocolSectionCoverageManifest
    )
    deep_plan = ProtocolControlDiscoveryToDeepPlan.model_validate(closure["deep_plan"])
    publication_plan = ProtocolControlBatchPlan.model_validate(
        closure["publication_plan"]
    )
    deep_results = _deep_results(context, config, closure)
    decisions = [
        ProtocolControlDiscoveryDecision.model_validate(item)
        for item in closure.get("discovery_decisions", [])
    ]
    decision_by_id = {item.structure_unit_id: item for item in decisions}
    hydrated_by_batch = dict(deep_results)
    deep_batch_ids = set(deep_results)
    all_results: list[ProtocolControlBatchDispositionHydrated] = []
    for batch in publication_plan.batches:
        if batch.batch_id in deep_batch_ids:
            all_results.append(hydrated_by_batch[batch.batch_id])
            continue
        if len(batch.owned_structure_unit_ids) != 1:
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_PUBLICATION_PLAN_INVALID",
                detail="非深析结构单元发布批次必须保持单元级闭包。",
            )
        unit_id = batch.owned_structure_unit_ids[0]
        decision = decision_by_id.get(unit_id)
        if decision is None or decision.disposition not in {
            ProtocolControlDiscoveryDisposition.CONTEXT_ONLY,
            ProtocolControlDiscoveryDisposition.NON_CONTROL,
        }:
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_DISCOVERY_CLOSURE_INVALID",
                detail="非深析结构单元没有合法的发现处置。",
            )
        unit = next(
            item for item in coverage_manifest.units if item.structure_unit_id == unit_id
        )
        excluded_scope = (
            PhaseScope.PHASE_II
            if coverage_manifest.study_phase == StudyPhase.PHASE_III
            else (
                PhaseScope.PHASE_III
                if coverage_manifest.study_phase == StudyPhase.PHASE_II
                else None
            )
        )
        disposition_kind = (
            StructureUnitDispositionKind.PHASE_EXCLUDED
            if excluded_scope is not None and excluded_scope in unit.phase_scopes
            else StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT
        )
        all_results.append(
            ProtocolControlBatchDispositionHydrated(
                batch_id=batch.batch_id,
                coverage_manifest_id=coverage_manifest.manifest_id,
                owned_structure_unit_ids=[unit_id],
                owned_source_span_ids=sorted(unit.source_span_ids),
                dispositions=[
                    ProtocolControlUnitDisposition(
                        structure_unit_id=unit_id,
                        disposition=disposition_kind,
                        notes=f"discovery disposition: {decision.disposition.value}",
                    )
                ],
                candidates=[],
            )
        )
    if len(all_results) != len(publication_plan.batches):
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_PUBLICATION_PLAN_INVALID",
            detail="水合结果未覆盖确定性发布计划。",
        )
    return {
        "stage": "hydrate",
        "deep_plan": deep_plan.model_dump(mode="json"),
        "publication_plan": publication_plan.model_dump(mode="json"),
        "batch_dispositions": [item.model_dump(mode="json") for item in all_results],
        "deep_batch_ids": sorted(deep_batch_ids),
        "candidate_ids": sorted(
            candidate.control_candidate_id
            for item in all_results
            for candidate in item.candidates
        ),
        "hydration": "system_hydrated_and_revalidated",
    }


def _execute_gate(
    context: StepContext,
    config: ProtocolControlExecutorConfig,
) -> dict[str, Any]:
    hydrate = _checkpoint_for_step(context, STEP_HYDRATE, config)
    if hydrate.get("stage") != "hydrate":
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
            detail="水合阶段检查点身份不一致。",
        )
    coverage_manifest = _payload_model(
        context, "coverage_manifest", ProtocolSectionCoverageManifest
    )
    publication_plan = ProtocolControlBatchPlan.model_validate(
        hydrate["publication_plan"]
    )
    batch_results = [
        ProtocolControlBatchDispositionHydrated.model_validate(item)
        for item in hydrate["batch_dispositions"]
    ]

    catalog_scaffold = PublishedProtocolControlCatalog(
        catalog_id=_stable_catalog_id(
            coverage_manifest.manifest_id,
            publication_plan.plan_id,
        ),
        protocol_version_id=coverage_manifest.protocol_version_id,
        protocol_document_sha256=coverage_manifest.protocol_document_sha256,
        study_phase=coverage_manifest.study_phase,
        coverage_manifest_id=coverage_manifest.manifest_id,
        allowed_source_span_ids=sorted(
            {
                span_id
                for unit in coverage_manifest.units
                for span_id in unit.source_span_ids
            }
        ),
        controls=[],
    )
    # The existing gate is reused as a closure validator only.  This empty
    # catalog scaffold is intentionally not returned or persisted: this
    # execution produces a validated candidate package, not a formal catalog.
    validate_protocol_control_publication(
        coverage_manifest,
        catalog_scaffold,
        plan=publication_plan,
        batch_dispositions=batch_results,
    )
    candidate_ids = sorted(
        {
            candidate.control_candidate_id
            for result in batch_results
            for candidate in result.candidates
        }
    )
    if candidate_ids != sorted(hydrate.get("candidate_ids", [])):
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_CANDIDATE_PACKAGE_INVALID",
            detail="门禁前候选身份与水合结果不一致。",
        )
    return {
        "stage": "gate",
        "gate_version": CONTROL_PUBLICATION_GATE_VERSION,
        "accepted": True,
        "result_kind": CANDIDATE_CONTROL_PACKAGE_RESULT_KIND,
        "formal_catalog_status": FORMAL_CATALOG_STATUS_NOT_MATERIALIZED,
        "coverage_manifest_id": coverage_manifest.manifest_id,
        "publication_plan": publication_plan.model_dump(mode="json"),
        "batch_dispositions": [
            item.model_dump(mode="json") for item in batch_results
        ],
        "candidate_ids": candidate_ids,
        "publication_plan_id": publication_plan.plan_id,
    }


def _checkpoint_for_step(
    context: StepContext,
    step_id: str,
    config: ProtocolControlExecutorConfig,
) -> dict[str, Any]:
    # The executor is outside the runner's transaction; read the predecessor's
    # durable result through the same session factory only when needed.
    with config.session_factory() as session:
        checkpoint = JobStore(session, now=config.now).get_last_checkpoint(
            context.job_id,
            step_id,
        )
    if checkpoint is None:
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_CHECKPOINT_MISSING",
            detail=f"前置步骤 {step_id} 的持久结果缺失。",
        )
    return checkpoint[1]



def _run_diagnostics(attempts: Sequence[Any], base: str) -> str:
    diagnostics: list[str] = []
    for attempt in reversed(attempts):
        issues = getattr(attempt, "issues", ()) or ()
        for issue in issues:
            text = " ".join(str(issue).split())[:600]
            if text and text not in diagnostics:
                diagnostics.append(text)
            if len(diagnostics) >= 3:
                break
        if len(diagnostics) >= 3:
            break
    if not diagnostics:
        return base
    return base + " 最近诊断：" + "；".join(diagnostics)[:1800]


def _stable_catalog_id(manifest_id: str, plan_id: str) -> str:
    digest = hashlib.sha256(
        json.dumps([manifest_id, plan_id], ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()[:24]
    return "pcc-" + digest



def _build_publication_plan(
    coverage_manifest: ProtocolSectionCoverageManifest,
    deep_plan: ProtocolControlDiscoveryToDeepPlan,
) -> ProtocolControlBatchPlan:
    """Add deterministic single-unit results for non-deep discovery outcomes."""

    units_by_id = {unit.structure_unit_id: unit for unit in coverage_manifest.units}
    deep_batches = list(deep_plan.batches)
    deep_ids = {batch.batch_id for batch in deep_batches}
    target_template = deep_batches[0] if deep_batches else None
    entries: list[tuple[int, int, str, ProtocolControlDispositionBatch]] = []
    for batch in deep_batches:
        first_order = min(units_by_id[item].source_order for item in batch.owned_structure_unit_ids)
        last_order = max(units_by_id[item].source_order for item in batch.owned_structure_unit_ids)
        entries.append((first_order, last_order, batch.batch_id, batch))
    decision_by_id = {item.structure_unit_id: item for item in deep_plan.discovery_decisions}
    for unit_id in deep_plan.non_deep_structure_unit_ids:
        unit = units_by_id[unit_id]
        number_hint = len(entries) + 1
        batch_id = stable_protocol_control_batch_id(
            coverage_manifest.manifest_id,
            number_hint,
            [unit_id],
        )
        synthetic = ProtocolControlDispositionBatch(
            batch_id=batch_id,
            coverage_manifest_id=coverage_manifest.manifest_id,
            protocol_version_id=coverage_manifest.protocol_version_id,
            study_phase=coverage_manifest.study_phase,
            batch_number=number_hint,
            batch_total=number_hint,
            priority_rank=unit.priority_rank,
            owned_units=[unit],
            context_units=[],
            owned_structure_unit_ids=[unit_id],
            context_structure_unit_ids=[],
            owned_source_span_ids=sorted(unit.source_span_ids),
            context_source_span_ids=[],
            known_official_targets=(
                list(target_template.known_official_targets)
                if target_template is not None
                else []
            ),
            known_procedure_targets=(
                list(target_template.known_procedure_targets)
                if target_template is not None
                else []
            ),
            known_workflow_stage_targets=(
                list(target_template.known_workflow_stage_targets)
                if target_template is not None
                else []
            ),
        )
        entries.append((unit.source_order, unit.source_order, batch_id, synthetic))
    if not entries:
        raise ProtocolControlPlanningError(
            "publication_plan_empty",
            "确定性发布计划不能为空。",
        )
    entries.sort(key=lambda item: (item[0], item[1], item[2]))
    total = len(entries)
    batches: list[ProtocolControlDispositionBatch] = []
    for number, (_first, _last, batch_id, batch) in enumerate(entries, start=1):
        if batch_id in deep_ids:
            batches.append(
                batch.model_copy(
                    update={"batch_number": number, "batch_total": total}
                )
            )
        else:
            batches.append(
                batch.model_copy(
                    update={"batch_number": number, "batch_total": total}
                )
            )
    plan_id = "pcpp-" + stable_protocol_control_batch_id(
        coverage_manifest.manifest_id,
        total,
        [batch.batch_id for batch in batches],
    ).removeprefix("pcb-")
    return ProtocolControlBatchPlan(
        plan_id=plan_id,
        coverage_manifest_id=coverage_manifest.manifest_id,
        protocol_version_id=coverage_manifest.protocol_version_id,
        study_phase=coverage_manifest.study_phase,
        max_owned_units_per_batch=max(
            1,
            deep_plan.max_owned_units_per_batch,
        ),
        context_radius=0,
        expected_structure_unit_ids=[unit.structure_unit_id for unit in coverage_manifest.units],
        batches=batches,
    )



__all__ = [
    "CANDIDATE_CONTROL_PACKAGE_RESULT_KIND",
    "FORMAL_CATALOG_STATUS_NOT_MATERIALIZED",
    "PROTOCOL_CONTROL_EXECUTION_JOB_TYPE",
    "PROTOCOL_CONTROL_EXECUTION_VERSION",
    "PROTOCOL_CONTROL_JOB_TYPE",
    "ProtocolControlExecutionError",
    "ProtocolControlExecutionResult",
    "ProtocolControlExecutorConfig",
    "ProtocolControlJobService",
    "STEP_CLOSURE",
    "STEP_GATE",
    "STEP_HYDRATE",
    "create_protocol_control_executor",
    "protocol_control_route_identity_from_config",
]
