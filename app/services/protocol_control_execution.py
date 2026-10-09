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
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agents.protocol_control_agent_transport import (
    protocol_control_transport_from_environment,
    PROTOCOL_CONTROL_LENGTH_RETRY_MAX_TOKENS,
    ProtocolControlAgentCallError,
    protocol_control_call_failure_code,
)
from app.agents.protocol_control_definition_scope import (
    DefinitionScopeReview, build_definition_scope_prompt,
)
from app.agents.protocol_control_deconstructor import (
    DEFAULT_MAX_SCHEMA_REPAIRS,
    DEFAULT_MAX_TRANSPORT_RETRIES,
    DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE,
    DEFAULT_PROTOCOL_CONTROL_DISCOVERY_PROMPT_TEMPLATE,
    SOURCE_TARGET_REPAIR_VERSION,
    SOURCE_REQUIREMENT_FAILURE_REASON_VERSION,
    ProtocolControlAgentRunner,
    ProtocolControlAgentAttempt,
    ProtocolControlAgentRunResult,
    ProtocolControlAgentWire,
    ProtocolControlAgentWireValidationError,
    ProtocolControlAgentTransport,
    ProtocolControlDiscoveryAgentRunner,
    ProtocolControlDiscoveryAgentRunResult,
    ProtocolControlDiscoveryAgentTransport,
    protocol_control_agent_json_schema,
    protocol_control_agent_prompt_template_sha256,
    protocol_control_agent_repair_contract_sha256,
    PUBLICATION_REPAIR_SCOPE_VERSION,
    hydrate_protocol_control_agent_output,
    hydrated_source_coverage_indexes,
    source_statement_coverage,
    protocol_control_discovery_prompt_template_sha256,
)
from app.agents.protocol_control_stage_compiler import (
    RELATIVE_STAGE_PREFLIGHT_VERSION,
    RELATIVE_STAGE_SOURCE_DIMENSION_VERSION,
    RELATIVE_STAGE_REQUIREMENT_VERSION,
    SHARED_PROHIBITION_REQUIREMENT_VERSION,
    STAGE_BOUND_REQUIREMENT_VERSION,
)
from app.agents.protocol_control_discovery_transport import (
    protocol_control_discovery_transport_from_environment,
)
from app.agents.protocol_control_source_interpretation import (
    SOURCE_COVERAGE_VALIDATION_VERSION,
    SOURCE_ATTRIBUTION_VALIDATION_VERSION,
    SOURCE_TARGET_REVIEW_VALIDATION_VERSION,
    SOURCE_TARGET_REVIEW_GAP_VERSION,
    SOURCE_TARGET_CONTEXT_RECHECK_VERSION,
    SOURCE_TARGET_COCITED_CONTEXT_VERSION,
    SOURCE_QUOTE_RECOVERY_VERSION,
    SOURCE_TARGET_REVIEW_VERSION,
    SourceDefinitionConsumers,
    SourceInterpretation,
    NATIVE_SCOPE_QUESTION_GUIDANCE_VERSION,
    SourceInterpretationValidationError,
    SourceScopeCorrection,
    SourceQuoteCorrection,
    SourceStatementCoverage,
    SourceTargetReview,
    SourceTargetReviewValidationError,
    is_non_action_definition,
    is_post_eligibility_calculation,
    is_study_phase_label,
    source_definition_statement_indexes,
    normalize_source_excerpt,
    parse_product_source_interpretation,
    apply_source_scope_correction,
    apply_source_scope_question_recheck,
    source_question_context_identity,
    apply_source_quote_correction,
    validate_source_definition_consumers,
    validate_source_interpretation,
    normalize_schedule_randomization_anchors,
    normalize_mixed_schedule_scopes,
    schedule_column_links,
    validate_source_target_review,
    validated_source_review_seed,
    target_review_indexes,
    _time_words_cover_stage_label,
)
from app.agents.protocol_control_source_function import (
    SOURCE_FUNCTION_FIELD_REPAIR_VERSION,
    SOURCE_FUNCTION_RECHECK_VERSION,
)
from app.agents.protocol_control_candidate_alignment import (
    NATIVE_TABLE_ALIGNMENT_CONTEXT_VERSION,
    NATIVE_ROW_ACTION_COVERAGE_VERSION,
    SOURCE_CANDIDATE_ALIGNMENT_VERSION,
    SOURCE_CANDIDATE_QUOTE_SCOPE_VERSION,
    SourceCandidateAlignment,
    SourceCandidateAlignmentItem,
    SourceCandidateAlignmentProof,
    alignment_with_items,
    SourceCandidateAlignmentValidationError,
    reusable_proven_alignment_items,
    evidence_policy_alignment_pairs,
    require_evidence_policy_alignment,
    validate_candidate_alignment,
)
from app.services.protocol_control_definition_scope import (
    close_definition_scope, definition_scope_inputs,
)
from app.llm.logical_call_budget import LogicalCallBudget
from app.services.protocol_control_restricted_source import (
    _coverage_matches_current_proofs,
    _temporal_restriction_indexes,
    TEMPORAL_RESTRICTION_VERSION,
    WHOLE_UNIT_RESTRICTION_VERSION,
    PROCEDURE_RESTRICTION_VALIDATION_VERSION,
    CITATION_CLOSURE_RESTRICTION_VALIDATION_VERSION,
    PROCEDURE_SOURCE_CONTEXT_VERSION,
    procedure_correspondence_source_gaps,
    procedure_correspondence_scope_indexes,
    RESTRICTED_DEFINITION_VALIDATION_VERSION,
    restricted_batch_from_review,
)
from app.domain.contracts.agent_io import ProtocolDeconstructionInput
from app.domain.contracts.enums import ExtractionStatus, PhaseScope, StudyPhase
from app.domain.contracts.protocol_controls import (
    CONTROL_CONTINUATION_SOURCE_VERSION,
    ControlRelationTargetKind,
    KnownOfficialRuleTarget,
    ProtocolControlBatchDispositionHydrated,
    ProtocolControlBatchPlan,
    ProtocolControlDefinitionAtomConsumption,
    ProtocolControlDefinitionConsumerRecord,
    ProtocolControlDiscoveryBatch,
    ProtocolControlDiscoveryDecision,
    ProtocolControlDiscoveryDisposition,
    ProtocolControlDiscoveryPlan,
    ProtocolControlDiscoveryToDeepPlan,
    ProtocolControlDispositionBatch,
    ProtocolControlSourceUnitRelation,
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
from app.domain.contracts.rules import WorkflowStage, iter_atomic_predicates
from app.protocols.docx_structure import StructureBlock, block_set_hash
from app.protocols.full_protocol_coverage import (
    FullProtocolCoverageError,
    build_full_protocol_coverage_manifest,
)
from app.protocols.procedure_catalog import schedule_row_values, table_footnote_context_links
from app.protocols.protocol_control_gate import (
    CONTROL_PUBLICATION_GATE_VERSION,
    ProtocolControlGateError,
    ProtocolControlGateIssue,
    check_protocol_control_batch_candidates,
    validate_protocol_control_publication,
)
from app.protocols.protocol_control_repair_errors import (
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
from app.evidence.artifacts import ArtifactStore, ArtifactStoreError
from app.services.job_service import JobService, StepSpec
from app.services.protocol_workbench_service import (
    PROTOCOL_DECONSTRUCTION_JOB_TYPE,
    PROTOCOL_DECONSTRUCTION_STEPS,
    STEP_GENERATE as SOURCE_STEP_GENERATE,
    STEP_AWAIT_REVIEW as SOURCE_STEP_AWAIT_REVIEW,
    STEP_PUBLISH as SOURCE_STEP_PUBLISH,
)
from app.storage.codecs import PersistedContractInvalid, utc_now, verify_payload_sha256
from app.storage.config import DataPaths
from app.storage.models import JobCheckpointRecord
from app.storage.repositories import NotFoundError, ProtocolDraftRevisionRepository
from app.workflow.errors import JobNotFoundError, StepFailure
from app.workflow.jobstore import DEFAULT_LEASE_TTL, JobStore
from app.workflow.runner import PreparedStepResult, StepContext, StepExecutor


PROTOCOL_CONTROL_EXECUTION_JOB_TYPE = "protocol_control_execution"
# A short alias keeps callers independent from the longer API-facing name.
PROTOCOL_CONTROL_JOB_TYPE = PROTOCOL_CONTROL_EXECUTION_JOB_TYPE
PROTOCOL_CONTROL_EXECUTION_VERSION = "phase5/protocol-control-execution/v217"
PROTOCOL_CONTROL_EXECUTION_CONTROL_SCHEMA = (
    "phase5/protocol-control-execution-control/v2"
)

STEP_CLOSURE = "deterministic_closure"
STEP_SCOPE = "definition_scope"
STEP_HYDRATE = "hydrate"
STEP_GATE = "gate"
CANDIDATE_CONTROL_PACKAGE_RESULT_KIND = "hydrated_candidate_control_package"
FORMAL_CATALOG_STATUS_NOT_MATERIALIZED = "not_materialized"


_DISCOVERY_STEP_PREFIX = "discovery_"
_DEEP_STEP_PREFIX = "deep_"
_INDEPENDENT_DEEP_READ_POLICY = {
    "step_prefix": _DEEP_STEP_PREFIX,
    "error_codes": ["PROTOCOL_CONTROL_SOURCE_TARGET_REVIEW_UNRESOLVED"],
    "max_failed_steps": 2,
}
# Recorded on every relation with verified consumers: this per-batch closure
# cannot see a consumer in another batch, so completeness stays unproven.
_DEFINITION_CONSUMER_SCOPE_UNPROVEN = "定义消费范围完整性尚未证实（含跨批消费者）"
_SOURCE_DECONSTRUCTION_JOB_TYPE = PROTOCOL_DECONSTRUCTION_JOB_TYPE
# Source registrations at the review/publish boundary must travel with the
# exact draft. Use the workbench's order, not only its initial freeze.
_SOURCE_STEP_ORDER = tuple(step.step_id for step in PROTOCOL_DECONSTRUCTION_STEPS)
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
    table_footnote_context_links: dict[str, dict[str, list[str]]]
    draft_revision_id: str | None = None
    draft_content_sha256: str | None = None


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
        deep_workflow_variant: str = "RV1001-BASELINE",
        deep_request_limit: int | None = None,
        deep_independent_reads_after_unresolved: bool = False,
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
        from app.agents.protocol_control_fixed_flow import workflow_template
        self.deep_workflow_variant = deep_workflow_variant
        if (deep_request_limit is not None and
                (type(deep_request_limit) is not int or deep_request_limit < 1)):
            raise ValueError("方案深审累计请求上限必须为正整数")
        if deep_workflow_variant == "RV1001-FLOW" and deep_request_limit is None:
            raise ValueError("隔离固定流程必须显式冻结累计请求上限")
        self.deep_request_limit = deep_request_limit
        if type(deep_independent_reads_after_unresolved) is not bool:
            raise ValueError("独立来源读取设置必须为明确的布尔值")
        self.deep_independent_reads_after_unresolved = deep_independent_reads_after_unresolved
        self.deep_prompt_template = workflow_template(deep_prompt_template, deep_workflow_variant)
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
        draft_revision_id: str | None = None,
        discovery_source_job_id: str | None = None,
        deep_source_job_id: str | None = None,
        recompute_missing_diagnostic_steps: Sequence[str] = (),
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
        if (len(set(recompute_missing_diagnostic_steps)) != len(recompute_missing_diagnostic_steps)
                or any(not isinstance(step, str) or len(step) != 9
                       or not step.startswith("deep_") or not step[5:].isdigit()
                       for step in recompute_missing_diagnostic_steps)
                or (recompute_missing_diagnostic_steps and deep_source_job_id is None)):
            raise ProtocolControlExecutionError(
                "PROTOCOL_CONTROL_RECOMPUTE_SCOPE_INVALID",
                "重新读取范围必须明确对应缺少失败记录的原深审批次。", status_code=422,
            )

        with self.session_factory() as session, session.begin():
            prepared = self._prepare_source_in_session(
                session,
                source_job_id=source_job_id,
                max_discovery_units_per_batch=self.max_discovery_units_per_batch,
                discovery_context_radius=self.discovery_context_radius,
            )
            if draft_revision_id is not None and draft_revision_id != prepared.draft_revision_id:
                raise ProtocolControlExecutionError(
                    "PROTOCOL_CONTROL_DRAFT_CHANGED",
                    "方案草稿版本已变化，请刷新后重新整理补充审核要求。",
                    status_code=409,
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
            if deep_source_job_id is not None:
                store = JobStore(session, now=self.jobs.now)
                try:
                    reuse_plan = _preflight_deep_source(
                        store, payload, deep_source_job_id,
                        self.deep_prompt_template,
                        recompute_missing_diagnostic_steps=recompute_missing_diagnostic_steps,
                    )
                except (JobNotFoundError, ValueError, KeyError, TypeError,
                        ValidationError, StepFailure, PersistedContractInvalid) as exc:
                    raise ProtocolControlExecutionError(
                        "PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
                        "既有深审结果与本次原件、版本或模型线路不一致，未建立新任务。",
                        status_code=409,
                    ) from exc
                payload["deep_source_job_id"] = deep_source_job_id
                payload["deep_reuse_plan"] = reuse_plan
                artifact = ArtifactStore(self.data_paths).put(
                    "protocol_control_reuse_plan",
                    json.dumps(reuse_plan, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":")).encode("utf-8"),
                )
                payload["deep_reuse_plan_artifact_ref"] = artifact.storage_ref
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

        for step_id in (SOURCE_STEP_GENERATE, SOURCE_STEP_AWAIT_REVIEW, SOURCE_STEP_PUBLISH):
            checkpoint = store.get_last_checkpoint(source_job_id, step_id)
            if checkpoint is not None and "draft_revision_id" in checkpoint[1]:
                merged["draft_revision_id"] = checkpoint[1]["draft_revision_id"]

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
        draft_revision_id = merged.get("draft_revision_id")
        draft_content_sha256 = None
        if draft_revision_id is not None:
            if not isinstance(draft_revision_id, str) or not draft_revision_id:
                raise ProtocolControlExecutionError(
                    "PROTOCOL_CONTROL_DRAFT_INVALID", "方案草稿修订身份无效。", status_code=409,
                )
            try:
                revision = ProtocolDraftRevisionRepository(session).get(draft_revision_id)
            except NotFoundError as exc:
                raise ProtocolControlExecutionError(
                    "PROTOCOL_CONTROL_DRAFT_MISSING", "方案草稿修订无法核对。", status_code=409,
                ) from exc
            if (revision.project_id, revision.protocol_version_id, revision.study_phase) != (
                source_input.project_id, source_input.protocol_version_id, source_input.selected_phase
            ):
                raise ProtocolControlExecutionError(
                    "PROTOCOL_CONTROL_DRAFT_SCOPE_INVALID", "方案草稿与补充审核要求的来源不一致。", status_code=409,
                )
            draft_content_sha256 = revision.content_sha256
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
            table_footnote_context_links=table_footnote_context_links(blocks, coverage_manifest.units),
            draft_revision_id=draft_revision_id,
            draft_content_sha256=draft_content_sha256,
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
            "deep_workflow_variant": self.deep_workflow_variant,
            "deep_request_limit": self.deep_request_limit,
            "frozen_model_routes": frozen_routes,
            **local_deployment_job_fields(),
            "source_deconstruction_job_id": prepared.source_job_id,
            **({
                "draft_revision_id": prepared.draft_revision_id,
                "draft_content_sha256": prepared.draft_content_sha256,
            } if prepared.draft_revision_id is not None else {}),
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
            **({"table_footnote_context_links": prepared.table_footnote_context_links}
               if prepared.table_footnote_context_links else {}),
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
                **({"continue_after_final_failure": {
                       **_INDEPENDENT_DEEP_READ_POLICY,
                       "error_codes": list(_INDEPENDENT_DEEP_READ_POLICY["error_codes"]),
                   }}
                   if self.deep_independent_reads_after_unresolved else {}),
                "max_parallel_steps": self.discovery_max_parallel,
                "parallelizable_step_ids": [
                    entry["step_id"] for entry in discovery_steps
                ],
                "parallel_scope": "discovery_batches_only",
                "notes": [
                    "Only explicitly listed independent discovery steps may share one lease wave.",
                    "Jobs without execution_control keep the historical serial runner path.",
                    "Do not rewrite paused serial discovery jobs to a mixed parallel config.",
                    ("One source-target unresolved unit stays failed while independent reads continue; a second stops. Publication remains blocked."
                     if self.deep_independent_reads_after_unresolved else
                     "A terminal deep failure stops new inference; completed receipts remain available for verified reuse."),
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
            if (
                context.last_checkpoint is not None
                and not context.last_checkpoint_is_diagnostic
                and context.last_checkpoint.get("stage") not in {
                    "deep_failure_diagnostic", "definition_scope_failure_diagnostic",
                }
            ):
                if context.step_id == STEP_SCOPE:
                    _verified_definition_scope(context, config, checkpoint=context.last_checkpoint)
                    return {key: value for key, value in context.last_checkpoint.items() if key != "attempt"}
                if context.step_id in {STEP_HYDRATE, STEP_GATE}:
                    saved = _replay_checkpoint(context, config)
                    current = (_execute_hydrate(context, config) if context.step_id == STEP_HYDRATE
                               else _execute_gate(context, config))
                    if {key: value for key, value in saved.items() if key != "attempt"} != current:
                        raise StepFailure(
                            retryable=False, error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
                            detail="已保存的整理结果与当前冻结来源及核对依据不一致，原记录保留。",
                        )
                    return {key: value for key, value in saved.items() if key != "attempt"}
                return _replay_checkpoint(context, config)
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
            if context.step_id == STEP_SCOPE:
                return _execute_definition_scope(context, config)
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


def _replay_checkpoint(
    context: StepContext, config: ProtocolControlExecutorConfig,
) -> dict[str, Any]:
    """Validate a completed checkpoint without re-calling a model or source file."""

    checkpoint = dict(context.last_checkpoint or {})
    if checkpoint.get("restricted_registration_failed"):
        raise StepFailure(
            retryable=False, error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
            detail="定义登记失败的记录仅供恢复诊断，不是已完成结果。",
        )
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
        closure = _closure_checkpoint(context, config)
        deep_plan = ProtocolControlDiscoveryToDeepPlan.model_validate(closure.get("deep_plan"))
        scoped_context = replace(context, job_payload={
            **context.job_payload, "deep_step_ids": closure.get("deep_step_ids", []),
        })
        batch = _deep_batch_for_step(scoped_context, deep_plan)
        prompt_template = _prompt_from_payload(context, "deep", config)
        transport = _resolve_transport(config, stage="deep")
        try:
            _require_frozen_route(context, config, transport, stage="deep")
            transport_identity = _transport_identity(transport, stage="deep")
        finally:
            if isinstance(config, ProtocolControlExecutorConfig) and all(
                value is None for value in (
                    config.deep_transport, config.deep_transport_factory,
                    config.transport, config.transport_factory,
                )
            ):
                client = getattr(transport, "_client", None)
                close = getattr(client, "close", None)
                if callable(close):
                    close()
        if (checkpoint.get("batch_id") != batch.batch_id
                or checkpoint.get("prompt_template_sha256")
                != protocol_control_agent_prompt_template_sha256(prompt_template)
                or checkpoint.get("component_identity")
                != _deep_component_identity(context.job_payload, prompt_template)
                or checkpoint.get("transport_identity") != transport_identity
                or not _repair_material_matches(checkpoint)):
            raise StepFailure(
                retryable=False, error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
                detail="已保存的深审结果与当前冻结来源、提示或模型线路不一致。",
            )
        try:
            run_result = _saved_deep_run_result(checkpoint)
            if (run_result.source_definition_consumers is None
                    and run_result.restricted_source_definition_consumer_attempts):
                raise ValueError("定义登记尝试未形成合法登记，不是已完成结果")
        except (TypeError, ValueError) as exc:
            raise StepFailure(
                retryable=False, error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
                detail="深审恢复缺少完整且身份一致的原答回执，未重新读取。",
            ) from exc
        if run_result.batch_id != batch.batch_id:
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
                detail="深析阶段检查点身份不一致。",
            )
        try:
            if checkpoint.get("restricted_batch") is not None:
                expected = restricted_batch_from_review(batch, run_result)
                saved = ProtocolControlBatchDispositionHydrated.model_validate(checkpoint["restricted_batch"])
                if expected is None or saved != expected:
                    raise ValueError("受限来源与逐项核对不一致")
                _validate_deep_batch_output(batch, saved)
            else:
                if run_result.status not in {"已解析", "待跨章核验"} or run_result.final_output is None:
                    raise ValueError("深析结果缺少已完成的处置")
                _validate_saved_source_review(batch, run_result)
                _validate_deep_batch_output(batch, run_result.final_output)
            if _source_interpretation_requires_refresh(batch, run_result):
                raise ValueError("来源核对需按当前冻结结构重新验证")
            restricted_indexes = ({item.source_statement_index for item in saved.restricted_statements}
                                  if checkpoint.get("restricted_batch") is not None else set())
            pending_relations = any(
                item.decision == "potential_same_requirement"
                and item.statement_index not in restricted_indexes
                for item in (run_result.source_target_review.items
                             if run_result.source_target_review else [])
            )
            if (pending_relations != (run_result.status == "待跨章核验")
                    and not (pending_relations and run_result.status == "需要核对"
                             and checkpoint.get("restricted_batch") is not None)):
                raise ValueError("跨章节待核状态与实际来源对应不一致")
        except (TypeError, ValueError, ProtocolControlGateError) as exc:
            raise StepFailure(
                retryable=False, error_code="PROTOCOL_CONTROL_CHECKPOINT_INVALID",
                detail="已保存的深审处置未通过当前来源及输出校验。",
            ) from exc
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
    if stage == "deep":
        from app.agents.protocol_control_fixed_flow import BASELINE, FIXED_FLOW, FIXED_FLOW_VERSION
        variant = context.job_payload.get("deep_workflow_variant", BASELINE)
        if variant not in {BASELINE, FIXED_FLOW} or (
            prompt.endswith("\n" + FIXED_FLOW_VERSION) != (variant == FIXED_FLOW)
        ):
            raise StepFailure(
                retryable=False, error_code="PROTOCOL_CONTROL_WORKFLOW_IDENTITY_INVALID",
                detail="冻结工作流程与提示身份不一致，不能发送方案读取请求。",
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
        "response_validation_version",
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
    take_receipts = getattr(transport, "take_call_receipts", None)
    model_call_receipts = take_receipts() if callable(take_receipts) else []
    if result.status not in {"已解析", "待跨章核验"} or result.final_output is None:
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_DISCOVERY_NEEDS_REVIEW",
            detail=_run_diagnostics(
                result.attempts,
                "发现批次未产出可接受的完整结果；本步骤已进入人工核对边界，"
                "外层 JobRunner 不会自动新建模型会话。"
                "仅人工调用任务重试后才会再次执行该批次。",
            ),
            diagnostic_checkpoint={
                "stage": "discovery_failure_diagnostic",
                "schema_version": "phase5/discovery-failure-diagnostic/v1",
                "discovery_batch_id": batch.discovery_batch_id,
                "model_call_receipts": model_call_receipts,
            },
        )
    return {
        "stage": "discovery",
        "model_call_receipts": model_call_receipts,
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
        source_materials=source_input.source_materials,
        table_footnote_context_links=context.job_payload.get("table_footnote_context_links"),
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
        if STEP_SCOPE not in existing_steps:
            store.create_step(
                step_id=STEP_SCOPE,
                job_id=context.job_id,
                name="核对定义影响范围",
                depends_on=tuple(
                    f"{_DEEP_STEP_PREFIX}{number:04d}"
                    for number in range(1, len(deep_plan.batches) + 1)
                )
                or (STEP_CLOSURE,),
            )
        existing_steps = {step.step_id: step for step in store.list_steps(context.job_id)}
        if STEP_HYDRATE not in existing_steps:
            store.create_step(
                step_id=STEP_HYDRATE, job_id=context.job_id,
                name="聚合水合结果", depends_on=(STEP_SCOPE,),
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
    # The scope mapper prioritizes structural recovery without discarding
    # other findings: a source-bound hard failure must still stop the runner.
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
                json_path=error.json_path,
            )
            for error in errors
        ],
        candidate_by_id=candidate_by_id,
        control_to_candidate={},
        default_structure_unit_ids=list(batch.owned_structure_unit_ids),
    )


_DEEP_SOURCE_IDENTITY_FIELDS = (
    "source_deconstruction_job_id", "source_snapshot_id", "source_content_sha256",
    "coverage_manifest", "discovery_plan",
    "workflow_stages", "phase_projection", "max_deep_units_per_batch",
    "frozen_model_routes",
)


def _require_compatible_deep_source(
    current: Mapping[str, Any], previous: Mapping[str, Any],
) -> None:
    if any(current.get(field) != previous.get(field)
           for field in _DEEP_SOURCE_IDENTITY_FIELDS):
        raise StepFailure(
            retryable=False, error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
            detail="来源、分包或模型线路不一致。",
        )


def _require_schedule_member_sources(units: Sequence[ProtocolStructureUnit]) -> None:
    for unit in units:
        row_token = unit.source_ref.rpartition(".r")[2].partition(".")[0]
        if (unit.table_context is not None
                and row_token.isdigit()):
            if unit.member_texts is None:
                raise ValueError(
                    f"冻结表格行缺少逐格原文，须从原方案重建来源清单：{unit.structure_unit_id}"
                )
            try:
                schedule_row_values(unit)
            except ValueError as exc:
                raise ValueError(
                    f"冻结表格行来源结构不一致：{unit.structure_unit_id}；{exc}"
                ) from exc


def _deep_component_identity(
    payload: Mapping[str, Any], prompt_template: str,
) -> dict[str, Any]:
    def digest(value: Any) -> str:
        return hashlib.sha256(json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()

    return {
        "schema_version": "phase5/deep-component-identity/v3",
        "source_sha256": payload.get("source_content_sha256"),
        "draft_revision_id": payload.get("draft_revision_id"),
        "draft_content_sha256": payload.get("draft_content_sha256"),
        "discovery_plan_sha256": digest(payload.get("discovery_plan")),
        "coverage_manifest_sha256": digest(payload.get("coverage_manifest")),
        "prompt_text_sha256": hashlib.sha256(prompt_template.strip().encode("utf-8")).hexdigest(),
        "prompt_material_sha256": protocol_control_agent_prompt_template_sha256(prompt_template),
        "wire_schema_sha256": digest(protocol_control_agent_json_schema()),
        "compiler_versions": [
            CONTROL_CONTINUATION_SOURCE_VERSION,
            "observation-policy-patch-staging/v1",
            "bounded-atom-position-preservation/v1",
            "temporal-candidate-alignment-before-insert/v1",
            STAGE_BOUND_REQUIREMENT_VERSION, RELATIVE_STAGE_REQUIREMENT_VERSION,
            SHARED_PROHIBITION_REQUIREMENT_VERSION,
            "stage-period-inside-visit-scope/v3",
            "source-statement-coverage/v6",
            SOURCE_CANDIDATE_ALIGNMENT_VERSION,
            SOURCE_FUNCTION_RECHECK_VERSION,
            SOURCE_TARGET_REPAIR_VERSION,
            SOURCE_QUOTE_RECOVERY_VERSION,
            PUBLICATION_REPAIR_SCOPE_VERSION,
            "source-candidate-index-projection/v1",
            "source-insert-cited-statement-stop/v1",
            "source-interpretation-local-scope/v2",
            "source-unresolved-covered-review/v1",
            "source-stage-time-complete/v1",
            "source-stage-literal-list-time-coverage/v1",
            "restricted-nonreview-unit-preservation/v1",
            "restricted-independent-candidate-preservation/v1",
            TEMPORAL_RESTRICTION_VERSION,
            WHOLE_UNIT_RESTRICTION_VERSION,
            "saved-review-temporal-failure-classification/v1",
            "source-intraday-scope-preservation/v1",
            "source-numeric-unscoped-repair-stop/v1",
            "source-clock-capability-disposition/v1",
            "schedule-sibling-header-and-multiblock-cell/v1",
            "schedule-native-member-source/v2",
            "source-insert-partial-resume/v1",
            "source-insert-batch-merge/v1",
            "source-insert-pending-authority-and-append-order/v1",
            "multi-candidate-focused-repair/v2",
            "calendar-bound-wrapper-normalization/v1",
            "calendar-bound-distinct-atom-repair/v1",
            "calendar-bound-evaluation-pair/v1",
            "calendar-bound-frozen-stage-context/v1",
            "source-time-completeness/v1",
            "frequency-source-text-temporal-guard/v1",
            "source-scope-correction-trigger-witness/v1",
            "source-quote-correction-trigger-replay/v1",
            "source-and-author-shared-repair-budget/v1",
            "procedure-link-field-repair-before-repartition/v1",
            "procedure-link-selected-patch-host-merge/v1",
            "inline-scope-citation-assembly/v1",
            "pending-definition-consumer-diagnostic/v1",
        ],
        "validator_version": "/".join((CONTROL_PUBLICATION_GATE_VERSION,
                                       RESTRICTED_DEFINITION_VALIDATION_VERSION,
                                       SOURCE_COVERAGE_VALIDATION_VERSION,
                                       SOURCE_ATTRIBUTION_VALIDATION_VERSION,
                                       SOURCE_TARGET_REVIEW_VALIDATION_VERSION,
                                       SOURCE_TARGET_REVIEW_GAP_VERSION,
                                       SOURCE_TARGET_CONTEXT_RECHECK_VERSION,
                                       SOURCE_TARGET_COCITED_CONTEXT_VERSION,
                                       PROCEDURE_RESTRICTION_VALIDATION_VERSION,
                                       CITATION_CLOSURE_RESTRICTION_VALIDATION_VERSION,
                                       "source-target-additional-recovery/v1",
                                       PROCEDURE_SOURCE_CONTEXT_VERSION,
                                       RELATIVE_STAGE_PREFLIGHT_VERSION,
                                       RELATIVE_STAGE_SOURCE_DIMENSION_VERSION,
                                       "native-row-source-normalization/v1",
                                       "native-table-scope-recovery/v4",
                                       "native-table-visit-correspondence/v1",
                                       "reviewed-source-type-field-recovery/v1",
                                       "validated-snapshot-scoped-session/v1",
                                       SOURCE_FUNCTION_FIELD_REPAIR_VERSION,
                                       "native-author-note-projection-and-procedure-row-gate/v1",
                                       "invalid-wire-scoped-post-enrollment-repair/v1",
                                       NATIVE_ROW_ACTION_COVERAGE_VERSION,
                                       NATIVE_SCOPE_QUESTION_GUIDANCE_VERSION,
                                       NATIVE_TABLE_ALIGNMENT_CONTEXT_VERSION,
                                       "located-publication-recovery/v1",
                                       SOURCE_CANDIDATE_QUOTE_SCOPE_VERSION,
                                       "scoped-exception-dnf/v1")),
        "requested_route_sha256": (
            payload.get("frozen_model_routes") or {}
        ).get("deep"),
    }


def _same_deep_components_with_current_gate(
    saved: Mapping[str, Any], current: Mapping[str, Any],
) -> bool:
    if saved == current:
        return True
    return (
        set(saved) == set(current)
        and isinstance(saved.get("validator_version"), str)
        and bool(saved["validator_version"])
        and all(
            saved[name] == value
            for name, value in current.items()
            if name != "validator_version"
        )
    )


def _same_deep_batch_material(
    previous: ProtocolControlDispositionBatch,
    current: ProtocolControlDispositionBatch,
) -> bool:
    """Changing only the total batch count does not change this batch's input."""

    old = previous.model_dump(mode="json")
    new = current.model_dump(mode="json")
    old.pop("batch_total")
    new.pop("batch_total")
    return old == new


@dataclass(frozen=True)
class _ResumedSourceReview:
    """State of the saved per-statement source review carried into a rerun.

    ``state`` is explicit so a refreshed review is never a silent drop:
    ``absent`` (nothing was saved), ``reused`` (all expected decisions still
    pass), ``partially_reused`` (only individually current siblings seed the
    next read) or ``refresh_required`` (only the affected
    statements are sent back to the reader while the proven candidate/source
    base stays reusable).
    """

    state: str
    reason: str
    review: SourceTargetReview | None = None
    coverage: tuple[SourceStatementCoverage, ...] = ()
    source_seed_proof: Mapping[str, Any] | None = None
    source_scope_correction_indexes: tuple[int, ...] = ()


def _resumable_saved_candidate_alignment(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    coverage: Sequence[SourceStatementCoverage],
    wire: ProtocolControlAgentWire | None,
    saved: Mapping[str, Any],
) -> SourceCandidateAlignment | None:
    """Revalidate saved candidate pairs before any alignment reader call is skipped.

    Only fully_expressed items that still pass the current source/candidate
    validators are returned. Incomplete, uncertain, malformed, or provenance-
    broken responses never become a skip token.
    """

    if wire is None:
        return None
    payload = saved.get("source_candidate_alignment")
    if payload is None:
        return None
    if (not isinstance(payload, Mapping)
            or payload.get("version") != SOURCE_CANDIDATE_ALIGNMENT_VERSION
            or not isinstance(payload.get("items"), list)
            or not isinstance(payload.get("proofs"), list)):
        return None
    items, proofs = [], []
    for entry in payload["items"]:
        try:
            items.append(SourceCandidateAlignmentItem.model_validate(entry))
        except (TypeError, ValidationError):
            continue
    for entry in payload["proofs"]:
        try:
            proofs.append(SourceCandidateAlignmentProof.model_validate(entry))
        except (TypeError, ValidationError):
            continue
    if not items:
        return None
    alignment = SourceCandidateAlignment(
        version=SOURCE_CANDIDATE_ALIGNMENT_VERSION, items=items, proofs=proofs,
    )
    proven = reusable_proven_alignment_items(
        batch, interpretation, coverage, wire, alignment,
    )
    if not proven:
        return None
    return alignment_with_items(alignment, proven)


def _resumable_saved_source_review(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    saved: Mapping[str, Any],
) -> _ResumedSourceReview:
    """Prove a saved source review still holds before any reader call is skipped.

    The saved scope and coverage identity are checked before each decision is
    revalidated against the restored source and batch. A partial seed is not a
    complete review; final consumption still requires the full gate. A saved
    review is provable without a partial wire: the frozen
    batch/route/prompt identity checked by the caller plus these current
    validators carry the proof. A review whose saved coverage is missing or
    unprovable stays out of the reuse seed and goes back through the existing
    reader path.
    """

    payload = saved.get("source_target_review")
    if payload is None:
        front = saved.get("source_front_target_review")
        if (front is None or saved.get("workflow_path_executed") != "front_stage_flow"
                or saved.get("partial_wire") is not None):
            return _ResumedSourceReview(state="absent", reason="no_saved_source_review")
        from app.agents.protocol_control_fixed_flow import (
            FRONT_REVIEW_CORRECTION_CODES, pending_front_wire, validate_front_review,
        )

        review = SourceTargetReview.model_validate(front)
        validate_front_review(batch, interpretation, review)
        witnessed = False
        reconstructed = None
        correction_count = 0
        coverage = source_statement_coverage(batch, interpretation, pending_front_wire(batch))
        for attempt in saved.get("attempts", []):
            if not isinstance(attempt, Mapping) or not isinstance(attempt.get("error_detail"), Mapping):
                continue
            phase = attempt["error_detail"].get("workflow_phase")
            if phase not in {"source_review", "source_review_correction"}:
                continue
            raw = attempt.get("raw_output_text")
            if (not isinstance(raw, str) or not isinstance(attempt.get("session_id"), str)
                    or hashlib.sha256(raw.encode()).hexdigest() != attempt.get("raw_output_sha256")):
                raise ValueError("前置来源核对与实际保存原答不一致，不能复用")
            actual = SourceTargetReview.model_validate_json(raw)
            if phase == "source_review":
                if reconstructed is not None:
                    raise ValueError("前置来源核对含多个起始原答，不能复用")
                reconstructed = actual
            else:
                if reconstructed is None or correction_count:
                    raise ValueError("局部来源核对缺少唯一前置原答，不能复用")
                try:
                    validate_source_target_review(batch, interpretation, coverage, reconstructed)
                except SourceTargetReviewValidationError as exc:
                    index = exc.statement_index
                    if exc.code not in FRONT_REVIEW_CORRECTION_CODES:
                        raise ValueError("来源错误不属于允许的局部关系复核范围") from exc
                else:
                    raise ValueError("局部来源核对不能替换已通过的兄弟条目")
                if index is None:
                    raise ValueError("整个来源范围错误不能降为单条修复")
                selected = [entry for entry in coverage if entry.statement_index == index]
                validate_source_target_review(batch, interpretation, selected, actual)
                reconstructed = reconstructed.model_copy(update={"items": [
                    actual.items[0] if item.statement_index == index else item
                    for item in reconstructed.items
                ]})
                correction_count += 1
            witnessed = True
        if not witnessed:
            return _ResumedSourceReview(state="refresh_required", reason="front_review_receipt_unproven")
        if reconstructed != review:
            raise ValueError("前置来源核对与实际保存原答不一致，不能复用")
        return _ResumedSourceReview(
            state="reused", reason="verified_pending_front_review",
            review=review, coverage=tuple(coverage),
        )
    coverage_payload = saved.get("source_statement_coverage")
    if not isinstance(coverage_payload, list) or not coverage_payload:
        return _ResumedSourceReview(
            state="refresh_required", reason="saved_source_review_without_wire_proof",
        )
    try:
        review = SourceTargetReview.model_validate(payload)
        coverage = [
            SourceStatementCoverage.model_validate(item) for item in coverage_payload
        ]
    except (TypeError, ValidationError):
        return _ResumedSourceReview(
            state="refresh_required", reason="saved_source_review_invalid",
        )
    if sorted(entry.statement_index for entry in coverage) != list(
        range(len(interpretation.statements))
    ):
        return _ResumedSourceReview(
            state="refresh_required", reason="saved_source_coverage_identity_invalid",
        )
    try:
        expected = target_review_indexes(interpretation, coverage, batch)
        retained = validated_source_review_seed(batch, interpretation, coverage, review)
    except SourceTargetReviewValidationError:
        return _ResumedSourceReview(
            state="refresh_required", reason="current_validators_reject_saved_source_review",
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise StepFailure(
            retryable=False, error_code="PROTOCOL_CONTROL_SOURCE_REVIEW_VALIDATION_FAILED",
            detail="保存核对的程序校验失败，不能作为再次读取模型的理由。",
        ) from exc
    if not review.items:
        return _ResumedSourceReview(state="absent", reason="no_saved_source_review")
    if retained is None:
        return _ResumedSourceReview(
            state="refresh_required", reason="no_saved_source_review_item_still_valid",
        )
    kept_indexes = {item.statement_index for item in retained.items}
    state = "reused" if kept_indexes == set(expected) else "partially_reused"
    return _ResumedSourceReview(
        state=state,
        reason=(
            "saved_source_review_still_current" if state == "reused"
            else "affected_source_review_statements_require_refresh"
        ),
        review=retained,
        coverage=tuple(entry for entry in coverage if entry.statement_index in kept_indexes),
    )


def _unrepaired_source_seed_proof(
    batch: ProtocolControlDispositionBatch,
    saved: Mapping[str, Any],
    *, source_job_id: str, step_id: str, checkpoint_id: str,
) -> dict[str, Any] | None:
    """Prove the source read independently of later author/repair history."""
    if saved.get("partial_wire") is not None:
        return None
    attempts = saved.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        return None
    first = attempts[0]
    recorded_session = first.get("session_id", saved.get("session_id")) if isinstance(first, Mapping) else None
    if (not isinstance(first, Mapping) or type(first.get("attempt")) is not int
            or first["attempt"] != 1 or first.get("outcome") != "parsed"
            or first.get("error_classes")
            or not isinstance(recorded_session, str)
            or not recorded_session.strip()):
        return None
    raw = first.get("raw_output_text")
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("已解析来源的原始回答记录损坏")
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    if first.get("raw_output_sha256") != digest:
        raise ValueError("已解析来源的原始回答摘要不一致")
    try:
        actual = parse_product_source_interpretation(batch, raw)
        actual, _ = normalize_schedule_randomization_anchors(batch, actual)
        actual, _ = normalize_mixed_schedule_scopes(batch, actual)
        validate_source_interpretation(batch, actual)
    except (ValueError, KeyError, TypeError):
        return None
    if actual.model_dump(mode="json") != saved.get("source_interpretation"):
        return None
    return {
        "schema_version": "phase5/unrepaired-source-seed-proof/v1",
        "source_job_id": source_job_id, "step_id": step_id,
        "checkpoint_id": checkpoint_id,
        "raw_output_sha256": digest, "raw_output_chars": len(raw),
        "recorded_session_id": recorded_session,
        "session_record_scope": "attempt" if "session_id" in first else "checkpoint",
        "base_prompt_sha256": saved["prompt_template_sha256"],
        "component_identity_sha256": hashlib.sha256(json.dumps(
            saved["component_identity"], ensure_ascii=False, sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
        "validator_version": CONTROL_PUBLICATION_GATE_VERSION,
        "current_source_equal": True,
        "reused": ["source_interpretation"],
        "discarded": ["partial_wire", "source_target_review", "source_statement_coverage",
                      "source_candidate_alignment", "session_id"],
    }


def _revalidated_source_seed_proof(
    batch: ProtocolControlDispositionBatch, saved: Mapping[str, Any],
    current_components: Mapping[str, Any], *, source_job_id: str,
    step_id: str, checkpoint_id: str,
    max_source_corrections: int = DEFAULT_MAX_SCHEMA_REPAIRS,
) -> dict[str, Any] | None:
    """Replay the actual source read only; never reuse its downstream author result."""
    if type(max_source_corrections) is not int or max_source_corrections < 0:
        raise ValueError("来源作业的局部核对额度无效")
    components = saved.get("component_identity")
    if (not isinstance(components, Mapping) or set(components) != set(current_components)
            or any(components[name] != value for name, value in current_components.items()
                   if name not in {"compiler_versions", "validator_version"})
            or not isinstance(components.get("compiler_versions"), list)
            or not components["compiler_versions"]
            or any(not isinstance(value, str) or not value for value in components["compiler_versions"])):
        return None
    attempts = saved.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        return None

    source_snapshot = saved.get("source_interpretation")
    snapshot_field = "source_interpretation"
    if source_snapshot is None and saved.get("pending_source_interpretation") is not None:
        last = attempts[-1]
        detail = last.get("error_detail") if isinstance(last, Mapping) else None
        if (any(saved.get(name) is not None for name in (
                "partial_wire", "capability_wire", "source_target_review", "source_front_target_review",
                "source_candidate_alignment"))
                or not isinstance(detail, Mapping)
                or detail.get("workflow_phase") != "source_correction_pending"
                or detail.get("code") != "SOURCE_STAGE_TIME_MISSING"
                or last.get("outcome") != "schema_invalid"
                or last.get("raw_output_text") is not None):
            return None
        source_snapshot = saved["pending_source_interpretation"]
        try:
            pending = SourceInterpretation.model_validate(source_snapshot)
        except (TypeError, ValueError):
            return None
        index = detail.get("statement_id")
        if type(index) is not int or not 0 <= index < len(pending.statements):
            return None
        statement = pending.statements[index]
        unit = next((item for item in batch.owned_units
                     if item.structure_unit_id == statement.structure_unit_id), None)
        stage = normalize_source_excerpt(statement.affected_stage or "")
        if (unit is None or not stage
                or detail.get("source_refs") != list(unit.source_span_ids)
                or detail.get("json_path") != f"statements[{index}].time_words"
                or not _time_words_cover_stage_label(stage, statement.time_words)
                or any(stage in normalize_source_excerpt(word) for word in statement.time_words)):
            return None
        snapshot_field = "pending_source_interpretation"

    def actual_text(attempt: Mapping[str, Any]) -> str | None:
        raw = attempt.get("raw_output_text")
        if raw is None:
            return None
        if (not isinstance(raw, str) or not raw.strip()
                or hashlib.sha256(raw.encode()).hexdigest() != attempt.get("raw_output_sha256")):
            raise ValueError("来源读取的实际原答摘要损坏，不能作为缓存未命中处理")
        if not isinstance(attempt.get("session_id"), str) or not attempt["session_id"].strip():
            return None
        return raw

    first = attempts[0]
    if (not isinstance(first, Mapping) or type(first.get("attempt")) is not int
            or first["attempt"] != 1):
        return None
    raw = actual_text(first)
    if raw is None:
        return None
    try:
        actual = parse_product_source_interpretation(batch, raw)
        actual, _ = normalize_schedule_randomization_anchors(batch, actual)
        actual, _ = normalize_mixed_schedule_scopes(batch, actual)
    except (ValueError, KeyError, TypeError):
        return None
    witnessed = [first["raw_output_sha256"]]
    corrected: set[int] = set()
    quote_corrected: set[int] = set()
    for offset in range(max_source_corrections + 1):
        try:
            validate_source_interpretation(batch, actual)
        except SourceInterpretationValidationError as issue:
            if (offset == max_source_corrections or issue.code not in {
                    "SOURCE_TIME_UNGROUNDED", "SOURCE_SCOPE_UNGROUNDED", "SOURCE_TIME_INCOMPLETE",
                    "SOURCE_SCOPE_CONTEXT_INVALID", "SOURCE_STAGE_UNGROUNDED",
                    "SOURCE_STAGE_TIME_MISSING", "STUDY_PHASE_NOT_VISIT_TIME", "STUDY_PHASE_NOT_VISIT_STAGE",
                    "SOURCE_QUOTE_UNGROUNDED", "POST_ELIGIBILITY_SEQUENCE_UNGROUNDED",
                } or issue.statement_id in corrected or offset + 1 >= len(attempts)):
                return None
            if offset == 0:
                detail = first.get("error_detail")
                if (first.get("outcome") != "schema_invalid" or not isinstance(detail, Mapping)
                        or detail.get("code") != issue.code
                        or detail.get("statement_id") != issue.statement_id
                        or detail.get("source_refs") != issue.source_refs):
                    return None
            correction_attempt = attempts[offset + 1]
            if (not isinstance(correction_attempt, Mapping)
                    or type(correction_attempt.get("attempt")) is not int
                    or correction_attempt["attempt"] != offset + 2
                    or correction_attempt.get("outcome") != "parsed"
                    or correction_attempt.get("error_classes")):
                return None
            detail = correction_attempt.get("error_detail")
            quote_correction = issue.code in {
                "SOURCE_QUOTE_UNGROUNDED", "POST_ELIGIBILITY_SEQUENCE_UNGROUNDED",
            }
            # Legacy first corrections have their trigger on the initial answer.
            if detail is None and offset == 0 and not quote_correction:
                detail = first.get("error_detail")
            if (not isinstance(detail, Mapping) or detail.get("code") != issue.code
                    or detail.get("statement_id") != issue.statement_id
                    or detail.get("source_refs") != issue.source_refs):
                return None
            if quote_correction and (
                detail.get("workflow_phase") != "source_quote_correction"
                or detail.get("structure_unit_id") != issue.structure_unit_id
            ):
                return None
            text = actual_text(correction_attempt)
            if text is None:
                return None
            try:
                if quote_correction:
                    correction = SourceQuoteCorrection.model_validate_json(text)
                    actual = apply_source_quote_correction(batch, actual, issue.statement_id, correction)
                    quote_corrected.add(issue.statement_id)
                else:
                    correction = SourceScopeCorrection.model_validate_json(text)
                    statement = actual.statements[issue.statement_id]
                    if issue.code in {
                        "STUDY_PHASE_NOT_VISIT_TIME", "SOURCE_TIME_INCOMPLETE", "SOURCE_STAGE_TIME_MISSING",
                    } and (
                        correction.scope_quote != statement.scope_quote
                        or correction.scope_context_unit_id != statement.scope_context_unit_id
                        or correction.affected_stage != statement.affected_stage
                    ):
                        return None
                    actual = apply_source_scope_correction(batch, actual, issue.statement_id, correction)
            except (ValueError, KeyError, TypeError):
                return None
            corrected.add(issue.statement_id)
            witnessed.append(correction_attempt["raw_output_sha256"])
        else:
            if not corrected and (first.get("outcome") != "parsed" or first.get("error_classes")):
                return None
            break
    question_corrected: set[int] = set()
    for attempt in attempts[len(witnessed):]:
        detail = attempt.get("error_detail") if isinstance(attempt, Mapping) else None
        if not isinstance(detail, Mapping) or detail.get("workflow_phase") != "source_scope_question_recheck":
            break
        index = detail.get("statement_id")
        if (len(corrected) + len(question_corrected) >= max_source_corrections
                or type(index) is not int or not 0 <= index < len(actual.statements)
                or index in question_corrected or attempt.get("outcome") != "parsed"
                or attempt.get("error_classes") or attempt.get("attempt") != len(witnessed) + 1):
            return None
        statement = actual.statements[index]
        unit = next(unit for unit in batch.owned_units
                    if unit.structure_unit_id == statement.structure_unit_id)
        if (detail.get("code") != "SOURCE_SCOPE_QUESTION_RECHECK"
                or detail.get("json_path") != f"statements[{index}].unresolved"
                or detail.get("source_refs") != list(unit.source_span_ids)
                or detail.get("source_context_sha256") != source_question_context_identity(statement, batch)
                or detail.get("precondition_sha256") != hashlib.sha256(statement.model_dump_json().encode()).hexdigest()):
            return None
        text = actual_text(attempt)
        if text is None:
            return None
        try:
            actual = apply_source_scope_question_recheck(
                batch, actual, index, SourceInterpretation.model_validate_json(text),
            )
        except (ValueError, KeyError, TypeError):
            return None
        question_corrected.add(index)
        witnessed.append(attempt["raw_output_sha256"])
    if actual.model_dump(mode="json") != source_snapshot:
        return None
    return {
        "schema_version": ("phase5/revalidated-source-seed-proof/v5" if question_corrected else
                           "phase5/revalidated-source-seed-proof/v4"
                           if snapshot_field == "pending_source_interpretation"
                           else "phase5/revalidated-source-seed-proof/v3"),
        **({"source_snapshot_field": snapshot_field}
           if snapshot_field == "pending_source_interpretation" else {}),
        "source_repair_limit": max_source_corrections,
        "source_job_id": source_job_id, "step_id": step_id, "checkpoint_id": checkpoint_id,
        "source_response_sha256": witnessed,
        "scope_correction_indexes": sorted(corrected - quote_corrected),
        "quote_correction_indexes": sorted(quote_corrected),
        **({"scope_question_indexes": sorted(question_corrected)} if question_corrected else {}),
        "base_prompt_sha256": saved["prompt_template_sha256"],
        "source_sha256": hashlib.sha256(actual.model_dump_json().encode()).hexdigest(),
        "validator_version": CONTROL_PUBLICATION_GATE_VERSION,
        "changed_components": [name for name, value in current_components.items() if components[name] != value],
        "current_source_equal": True, "reused": ["source_interpretation"],
        "discarded": ["partial_wire", "source_target_review", "source_statement_coverage",
                      "source_candidate_alignment", "session_id"],
    }


def _obsolete_native_author_basis(
    batch: ProtocolControlDispositionBatch, saved: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Locate an unaccepted row link inherited from an invalid initial author answer."""
    if not isinstance(saved.get("partial_wire"), Mapping):
        return None
    alignment = saved.get("source_candidate_alignment")
    if not isinstance(alignment, Mapping) or not any(
        isinstance(item, Mapping) and item.get("decision") in {"incomplete", "uncertain"}
        for item in alignment.get("items", [])
    ):
        return None
    partial = ProtocolControlAgentWire.model_validate(saved["partial_wire"])
    attempts = saved.get("attempts")
    if not isinstance(attempts, list):
        return None
    for attempt in attempts:
        if not isinstance(attempt, Mapping):
            raise ValueError("作者读取的诊断结构损坏")
        raw = attempt.get("raw_output_text")
        if raw is None:
            continue
        if (not isinstance(raw, str)
                or hashlib.sha256(raw.encode()).hexdigest() != attempt.get("raw_output_sha256")):
            raise ValueError("作者读取的实际原答摘要损坏")
        try:
            initial = ProtocolControlAgentWire.model_validate_json(raw)
        except ValueError:
            continue
        try:
            hydrate_protocol_control_agent_output(initial, batch)
        except ProtocolControlAgentWireValidationError as error:
            if error.code != "PROCEDURE_ROW_SOURCE_MISMATCH":
                return None
            affected = set(error.structure_unit_ids)
            links = {
                entry.structure_unit_id: sorted(set(entry.linked_procedure_catalog_item_ids)
                    | ({entry.linked_procedure_catalog_item_id}
                       if entry.linked_procedure_catalog_item_id else set()))
                for entry in initial.dispositions if entry.structure_unit_id in affected
            }
            retained = []
            for entry in partial.dispositions:
                unit_id = entry.structure_unit_id
                if unit_id not in links or not links[unit_id]:
                    continue
                actual_links = set(entry.linked_procedure_catalog_item_ids) | (
                    {entry.linked_procedure_catalog_item_id} if entry.linked_procedure_catalog_item_id else set())
                actual_links.update(relation.external_target_id
                    for candidate in partial.candidate_drafts if unit_id in candidate.source_structure_unit_ids
                    for relation in candidate.cross_source_relations
                    if relation.external_target_kind == ControlRelationTargetKind.REQUIRED_PROCEDURE)
                if set(links[unit_id]) <= actual_links:
                    retained.append(unit_id)
            if not retained:
                return None
            return {"code": error.code, "structure_unit_ids": sorted(retained),
                    "initial_author_sha256": attempt["raw_output_sha256"],
                    "retained_procedure_links": {unit: links[unit] for unit in retained}}
        return None
    return None


def _validated_deep_partial_source(
    store: JobStore,
    current_payload: Mapping[str, Any],
    source_job_id: str,
    batch: ProtocolControlDispositionBatch,
    step_id: str,
    prompt_template: str,
) -> tuple[str, Mapping[str, Any], _ResumedSourceReview] | None:
    """Resume a verified source interpretation or gate-valid draft, never its failed result."""

    source_job = store.get_job(source_job_id)
    source_payload = verify_payload_sha256(source_job.payload_json, source_job.payload_sha256)
    _require_compatible_deep_source(current_payload, source_payload)
    limits = source_payload.get("runner_limits")
    if limits is not None and not isinstance(limits, Mapping):
        raise ValueError("来源作业的冻结运行预算损坏")
    source_repair_limit = (
        limits.get("deep_max_schema_repairs")
        if limits is not None else DEFAULT_MAX_SCHEMA_REPAIRS
    )
    if type(source_repair_limit) is not int or source_repair_limit < 0:
        raise ValueError("来源作业的局部核对额度无效")
    source_step = next(
        (step for step in store.list_steps(source_job_id) if step.step_id == step_id), None
    )
    if source_step is None or source_step.state != "failed_final":
        return None
    closure = store.get_last_checkpoint(source_job_id, STEP_CLOSURE)
    if closure is None or closure[1].get("stage") != "closure":
        raise ValueError("来源任务缺少已完成的分包计划")
    source_plan = ProtocolControlDiscoveryToDeepPlan.model_validate(
        closure[1].get("deep_plan")
    )
    old_batch = next(
        (item for item in source_plan.batches if item.batch_number == batch.batch_number), None
    )
    if old_batch is None or not _same_deep_batch_material(old_batch, batch):
        return None
    checkpoint = store.get_last_checkpoint(source_job_id, step_id)
    if checkpoint is None:
        raise ValueError("失败批次缺少诊断检查点")
    checkpoint_id, saved = checkpoint
    if saved.get("stage") != "deep_failure_diagnostic":
        return None
    if (saved.get("schema_version") != "phase5/deep-failure-diagnostic/v3"
            or saved.get("batch_id") != old_batch.batch_id):
        raise ValueError("局部草稿与来源批次身份不一致")
    identity = saved.get("transport_identity")
    if not isinstance(identity, dict):
        raise ValueError("局部草稿缺少模型线路回执")
    actual_route = hashlib.sha256(json.dumps(
        identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    expected_route = (current_payload.get("frozen_model_routes") or {}).get("deep")
    if expected_route is not None and actual_route != expected_route:
        raise ValueError("局部草稿的实际模型线路与当前任务不一致")
    saved_components = saved.get("component_identity")
    current_components = _deep_component_identity(current_payload, prompt_template)
    if (saved.get("prompt_template_sha256")
            != protocol_control_agent_prompt_template_sha256(prompt_template)
            or not isinstance(saved_components, Mapping)):
        return None
    source = saved.get("source_interpretation")
    repair_identity = saved.get("repair_contract_sha256")
    if (not isinstance(repair_identity, str) or len(repair_identity) != 64
            or any(char not in "0123456789abcdef" for char in repair_identity)):
        raise ValueError("局部草稿修复合同身份缺失或损坏")
    source_seed_proof = None
    changed_components = not _same_deep_components_with_current_gate(
        saved_components, current_components,
    )
    pending_source = any(
        isinstance(attempt, Mapping) and isinstance(attempt.get("error_detail"), Mapping)
        and attempt["error_detail"].get("workflow_phase") == "source_correction_pending"
        for attempt in saved.get("attempts", [])
    )
    obsolete_basis = (
        _obsolete_native_author_basis(batch, saved)
        if saved_components.get("validator_version") != current_components["validator_version"]
        else None
    )
    # A changed compiler cannot justify reusing executable semantics. It may
    # rederive a wholly non-executable disposition from unchanged source and
    # request materials, checked again by the current validators.
    if (changed_components and not pending_source and obsolete_basis is None
            and repair_identity == protocol_control_agent_repair_contract_sha256()
            and set(saved_components) == set(current_components)
            and isinstance(saved_components.get("compiler_versions"), list)
            and bool(saved_components["compiler_versions"])
            and all(isinstance(value, str) and value
                    for value in saved_components["compiler_versions"])
            and isinstance(saved_components.get("validator_version"), str)
            and bool(saved_components["validator_version"])
            and all(saved_components[name] == value for name, value in current_components.items()
                    if name not in {"compiler_versions", "validator_version"})
            and _preserved_temporal_restriction_proof(batch, saved) is not None):
        interpretation = SourceInterpretation.model_validate(source)
        resumed_review = _resumable_saved_source_review(batch, interpretation, saved)
        if resumed_review.state == "reused":
            return checkpoint_id, saved, resumed_review
    if (changed_components or pending_source or obsolete_basis is not None
            or repair_identity != protocol_control_agent_repair_contract_sha256()):
        if saved.get("partial_wire") is not None:
            # A damaged wire hard-fails; outdated semantics are discarded, not reused.
            ProtocolControlAgentWire.model_validate(saved["partial_wire"])
        if not changed_components and saved.get("partial_wire") is None:
            source_seed_proof = _unrepaired_source_seed_proof(
                batch, saved, source_job_id=source_job_id, step_id=step_id,
                checkpoint_id=checkpoint_id,
            )
        if source_seed_proof is None:
            source_seed_proof = _revalidated_source_seed_proof(
                batch, saved, current_components, source_job_id=source_job_id,
                step_id=step_id, checkpoint_id=checkpoint_id,
                max_source_corrections=source_repair_limit,
            )
        if source_seed_proof is None:
            return None
        if obsolete_basis is not None:
            source_seed_proof = dict(source_seed_proof, rejected_author_basis=obsolete_basis)
    if source_seed_proof is not None:
        if source_seed_proof.get("source_snapshot_field") == "pending_source_interpretation":
            source = saved.get("pending_source_interpretation")
    if source is None and saved.get("partial_wire") is None:
        return None
    if not isinstance(source, Mapping):
        raise ValueError("局部草稿缺少有源解释")
    interpretation = SourceInterpretation.model_validate(source)
    validate_source_interpretation(batch, interpretation)
    if (saved.get("partial_wire") is not None and saved.get("source_target_review") is not None
            and saved.get("attempts")
            and set(saved["attempts"][-1].get("error_classes", []))
            in ({"SOURCE_TARGET_REVIEW_UNRESOLVED"}, {"SOURCE_CONTEXT_COMPLETION_INVALID"},
                {"SOURCE_CONTEXT_UNRESOLVED"}, {"SOURCE_CONTEXT_COMPLETION_TRANSPORT_FAILED"},
                {"TEMPORAL_SCOPE_UNRESOLVED"})):
        original_wire = ProtocolControlAgentWire.model_validate(saved["partial_wire"])
        _validate_deep_batch_output(batch, hydrate_protocol_control_agent_output(original_wire, batch))
        witnessed_review = _resumable_saved_source_review(batch, interpretation, saved)
        if (witnessed_review.state == "reused" and procedure_correspondence_source_gaps(
            batch, interpretation, original_wire, witnessed_review.review,
        )):
            indexes = procedure_correspondence_scope_indexes(
                batch, interpretation, original_wire, witnessed_review.review,
            )
            if indexes is None or source_seed_proof is not None:
                return None
            # Keep a verified seed, not its incomplete coverage. The bounded
            # scope reader supplies missing context; the host never fills it.
            return checkpoint_id, saved, replace(
                witnessed_review, reason="source_context_correction_required",
                source_scope_correction_indexes=indexes,
            )
    if source_seed_proof is not None:
        seed = dict(saved, source_interpretation=source, partial_wire=None, source_target_review=None,
                    source_statement_coverage=[], source_candidate_alignment=None,
                    session_id=None)
        return checkpoint_id, seed, _ResumedSourceReview(
            state="absent", reason="components_or_repair_changed_source_only",
            source_seed_proof=source_seed_proof,
        )
    wire = None
    if saved.get("partial_wire") is not None:
        if not isinstance(saved.get("session_id"), str):
            raise ValueError("局部草稿缺少会话身份")
        wire = ProtocolControlAgentWire.model_validate(saved["partial_wire"])
        try:
            output = hydrate_protocol_control_agent_output(wire, batch)
            _validate_deep_batch_output(batch, output)
        except (ProtocolControlGateError, ProtocolControlAgentWireValidationError):
            proof = _revalidated_source_seed_proof(
                batch, saved, current_components, source_job_id=source_job_id,
                step_id=step_id, checkpoint_id=checkpoint_id,
                max_source_corrections=source_repair_limit,
            )
            if proof is None:
                raise
            # Only the witnessed source survives; failed author/reviewer output does not.
            seed = dict(saved, partial_wire=None, source_target_review=None,
                        source_statement_coverage=[], source_candidate_alignment=None,
                        session_id=None)
            return checkpoint_id, seed, _ResumedSourceReview(
                state="absent", reason="invalid_author_witnessed_source_only",
                source_seed_proof=proof,
            )
    resumed_review = _resumable_saved_source_review(batch, interpretation, saved)
    return checkpoint_id, saved, resumed_review


def _preserved_unresolved_review_proof(
    batch: ProtocolControlDispositionBatch, saved: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Revalidate an actual local unresolved result, never turn it into success."""
    attempts = saved.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        return None
    last = attempts[-1]
    if not isinstance(last, Mapping):
        raise ValueError("原未决的终态诊断结构损坏")
    if (last.get("outcome") != "publication_invalid"
            or last.get("error_classes") != ["SOURCE_TARGET_REVIEW_UNRESOLVED"]
            or not isinstance(saved.get("partial_wire"), Mapping)
            or not isinstance(saved.get("source_target_review"), Mapping)):
        return None
    source = SourceInterpretation.model_validate(saved["source_interpretation"])
    wire = ProtocolControlAgentWire.model_validate(saved["partial_wire"])
    coverage = [SourceStatementCoverage.model_validate(entry)
                for entry in saved.get("source_statement_coverage", [])]
    review = SourceTargetReview.model_validate(saved["source_target_review"])
    validate_source_interpretation(batch, source)
    _validate_deep_batch_output(batch, hydrate_protocol_control_agent_output(wire, batch))
    if not _coverage_matches_current_proofs(batch, _saved_failed_deep_run_result(batch, saved)):
        raise ValueError("原未决的来源覆盖与当前草稿不一致")
    validate_source_target_review(batch, source, coverage, review)
    unresolved = sorted(item.statement_index for item in review.items if item.decision == "unresolved")
    # A definition with an available dependency route needs a fresh semantic
    # review, not a frozen failure caused by the older permission restriction.
    if any(is_non_action_definition(source.statements[index]) for index in unresolved):
        return None
    detail = last.get("error_detail")
    units = {source.statements[index].structure_unit_id for index in unresolved}
    spans = sorted({span for unit in batch.owned_units if unit.structure_unit_id in units
                    for span in unit.source_span_ids})
    if (not unresolved or not isinstance(detail, Mapping)
            or detail.get("code") != "SOURCE_TARGET_REVIEW_UNRESOLVED"
            or detail.get("statement_ids") != unresolved
            or any(type(index) is not int for index in detail.get("statement_ids", []))
            or detail.get("source_refs") != spans or detail.get("json_path") != "/items"):
        return None
    return {
        "schema_version": "phase5/preserved-unresolved-review-proof/v1",
        "diagnostic_sha256": hashlib.sha256(json.dumps(
            saved, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
        "statement_ids": unresolved, "source_refs": spans,
        "error_code": "PROTOCOL_CONTROL_SOURCE_TARGET_REVIEW_UNRESOLVED",
        "adopted": False,
    }


def _preserved_temporal_restriction_proof(
    batch: ProtocolControlDispositionBatch, saved: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Revalidate a typed temporal failure as a wholly non-executable result."""
    attempts = saved.get("attempts")
    if (not isinstance(attempts, list) or not attempts
            or not isinstance(attempts[-1], Mapping)
            or attempts[-1].get("error_classes") != ["TEMPORAL_SCOPE_UNRESOLVED"]):
        return None
    if not isinstance(saved.get("partial_wire"), Mapping):
        return None
    result = _saved_failed_deep_run_result(batch, saved)
    proven = _temporal_restriction_indexes(batch, result, whole_unit=True)
    if proven is None:
        return None
    restricted = restricted_batch_from_review(batch, result)
    if (restricted is None or restricted.candidates
            or not restricted.restricted_statements
            or any(item.independent_scope_proof is not None
                   for item in restricted.restricted_statements)):
        return None
    _validate_deep_batch_output(batch, restricted)
    return {
        "schema_version": "phase5/preserved-temporal-restriction-proof/v1",
        "diagnostic_sha256": hashlib.sha256(json.dumps(
            saved, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
        "restricted_batch_sha256": hashlib.sha256(json.dumps(
            restricted.model_dump(mode="json"), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
        "statement_ids": sorted(proven),
        "source_refs": result.attempts[-1].error_detail["source_refs"],
        "error_code": "PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID", "adopted": False,
    }


def _preserved_source_review_proof(
    batch: ProtocolControlDispositionBatch, saved: Mapping[str, Any],
) -> dict[str, Any] | None:
    return (_preserved_unresolved_review_proof(batch, saved)
            or _preserved_temporal_restriction_proof(batch, saved))


def _missing_failed_diagnostic_proof(store: JobStore, source_job_id: str, step_id: str) -> dict[str, Any]:
    step = next((item for item in store.list_steps(source_job_id) if item.step_id == step_id), None)
    if (step is None or step.state != "failed_final"
            or store.get_last_checkpoint(source_job_id, step_id) is not None):
        raise ValueError("仅可显式重新读取缺少诊断检查点的失败范围，不得跳过已有或损坏回执")
    return {"source_job_id": source_job_id, "step_id": step_id,
            "source_job_payload_sha256": store.get_job(source_job_id).payload_sha256,
            "state": step.state, "error_code": step.error_code,
            "missing_diagnostic": True, "reused": False}


def _resolve_unexecuted_deep_source(
    store: JobStore, current_payload: Mapping[str, Any], source_job_id: str,
    batch: ProtocolControlDispositionBatch, step_id: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Follow frozen reuse provenance, never search history for a better answer."""
    visited: set[str] = set()
    lineage: list[dict[str, Any]] = []
    while True:
        if source_job_id in visited:
            raise ValueError("深审复用来源形成循环")
        visited.add(source_job_id)
        job = store.get_job(source_job_id)
        payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
        _require_compatible_deep_source(current_payload, payload)
        step = next((item for item in store.list_steps(source_job_id) if item.step_id == step_id), None)
        if step is None:
            raise ValueError("来源任务缺少深审批次")
        if (step.state not in {"queued", "cancelled"}
                or job.state not in {"failed_final", "cancelled"}):
            return source_job_id, lineage
        reuse = payload.get("deep_reuse_plan")
        entry = reuse.get("decisions", {}).get(batch.batch_id) if isinstance(reuse, Mapping) else None
        if not isinstance(entry, Mapping) or entry.get("decision") == "refresh_required":
            return source_job_id, lineage
        if (entry.get("step_id") != step_id
                or entry.get("decision") not in {"reusable", "resume_partial", "preserve_unresolved"}
                or store.get_last_checkpoint(source_job_id, step_id) is not None
                or step.attempt != 0):
            raise ValueError("尚未执行的批次缺少合法冻结复用范围")
        upstream_id = payload.get("deep_source_job_id")
        if (not isinstance(upstream_id, str) or not upstream_id
                or reuse.get("source_job_id") != upstream_id):
            raise ValueError("冻结复用计划与来源任务不一致")
        upstream = store.get_job(upstream_id)
        upstream_payload = verify_payload_sha256(upstream.payload_json, upstream.payload_sha256)
        _require_compatible_deep_source(payload, upstream_payload)
        for job_id, hash_key in ((source_job_id, "current_plan_sha256"), (upstream_id, "source_plan_sha256")):
            closure = store.get_last_checkpoint(job_id, STEP_CLOSURE)
            if closure is None or closure[1].get("stage") != "closure":
                raise ValueError("冻结复用来源缺少分包检查点")
            plan = ProtocolControlDiscoveryToDeepPlan.model_validate(closure[1].get("deep_plan"))
            digest = hashlib.sha256(json.dumps(
                plan.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")).hexdigest()
            matching = [item for item in plan.batches if item.batch_number == batch.batch_number]
            if (reuse.get(hash_key) != digest or len(matching) != 1
                    or not _same_deep_batch_material(matching[0], batch)):
                raise ValueError("冻结复用分包或来源范围已改变")
        lineage.append({"job_id": source_job_id, "payload_sha256": job.payload_sha256,
                        "source_job_id": upstream_id, "step_id": step_id})
        source_job_id = upstream_id


def _deep_source_checkpoint_proof(checkpoint: tuple[str, dict[str, Any]]) -> dict[str, str]:
    return {"checkpoint_id": checkpoint[0], "payload_sha256": hashlib.sha256(json.dumps(
        checkpoint[1], ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()}


def _preflight_deep_source(
    store: JobStore,
    current_payload: Mapping[str, Any],
    source_job_id: str,
    prompt_template: str,
    *, recompute_missing_diagnostic_steps: Sequence[str] = (),
) -> dict[str, Any]:
    """Plan reuse before creating a long job, without inference or rewriting history."""

    source_job = store.get_job(source_job_id)
    _require_compatible_deep_source(current_payload, json.loads(source_job.payload_json))
    closure = store.get_last_checkpoint(source_job_id, STEP_CLOSURE)
    if closure is None or closure[1].get("stage") != "closure":
        raise ValueError("来源任务缺少已完成的分包计划")
    source_plan = ProtocolControlDiscoveryToDeepPlan.model_validate(
        closure[1].get("deep_plan")
    )
    coverage = ProtocolSectionCoverageManifest.model_validate(
        current_payload["coverage_manifest"]
    )
    _require_schedule_member_sources(coverage.units)
    discovery = ProtocolControlDiscoveryPlan.model_validate(
        current_payload["discovery_plan"]
    )
    if (source_plan.coverage_manifest_id != coverage.manifest_id
            or source_plan.discovery_plan_id != discovery.plan_id):
        raise ValueError("来源深审计划与当前冻结清单不一致")
    decision_by_id = {
        item.structure_unit_id: item for item in source_plan.discovery_decisions
    }
    if set(decision_by_id) != set(discovery.expected_structure_unit_ids):
        raise ValueError("来源发现结果未覆盖当前冻结清单")
    source_input = ProtocolDeconstructionInput.model_validate(
        current_payload["source_input"]
    )
    current_plan = plan_protocol_control_deep_batches_from_discovery(
        coverage,
        discovery,
        [
            [decision_by_id[unit_id] for unit_id in batch.target_structure_unit_ids]
            for batch in discovery.batches
        ],
        official_parent_catalog=source_input.parent_rule_catalog,
        required_procedure_catalog=source_input.required_procedure_catalog,
        max_owned_units_per_batch=int(current_payload["max_deep_units_per_batch"]),
        workflow_stages=[
            WorkflowStage.model_validate(item)
            for item in current_payload.get("workflow_stages", [])
        ],
        source_materials=source_input.source_materials,
        table_footnote_context_links=current_payload.get("table_footnote_context_links"),
    )
    source_steps = {item.step_id: item for item in store.list_steps(source_job_id)}
    old_batches_by_number = {
        item.batch_number: item for item in source_plan.batches
    }
    expected_prompt = protocol_control_agent_prompt_template_sha256(prompt_template)
    current_components = _deep_component_identity(current_payload, prompt_template)
    routes = current_payload.get("frozen_model_routes")
    expected_route = routes.get("deep") if isinstance(routes, Mapping) else None
    if expected_route is not None and (
        not isinstance(expected_route, str) or len(expected_route) != 64
    ):
        raise ValueError("当前深审模型线路身份无效")
    decisions: dict[str, dict[str, Any]] = {}
    acknowledged = set(recompute_missing_diagnostic_steps)
    if not acknowledged <= {f"{_DEEP_STEP_PREFIX}{batch.batch_number:04d}" for batch in current_plan.batches}:
        raise ValueError("重新读取范围不属于当前完整分包")
    for batch in current_plan.batches:
        step_id = f"{_DEEP_STEP_PREFIX}{batch.batch_number:04d}"
        batch_source_id, source_lineage = _resolve_unexecuted_deep_source(
            store, current_payload, source_job_id, batch, step_id,
        )
        step = (source_steps.get(step_id) if batch_source_id == source_job_id else
                next((item for item in store.list_steps(batch_source_id) if item.step_id == step_id), None))
        decision = "refresh_required"
        reason = "new_or_incomplete_batch"
        review_state = "not_applicable"
        partial = None
        checkpoint = None
        old_batch = old_batches_by_number.get(batch.batch_number)
        if source_lineage:
            inherited_closure = store.get_last_checkpoint(batch_source_id, STEP_CLOSURE)
            inherited_plan = ProtocolControlDiscoveryToDeepPlan.model_validate(inherited_closure[1]["deep_plan"])
            old_batch = next(item for item in inherited_plan.batches if item.batch_number == batch.batch_number)
        if step_id in acknowledged:
            if (old_batch is None
                    or old_batch.owned_structure_unit_ids != batch.owned_structure_unit_ids):
                raise ValueError("缺诊断重新读取范围的来源归属已改变，不能按旧步骤编号授权")
            proof = _missing_failed_diagnostic_proof(store, source_job_id, step_id)
            decisions[batch.batch_id] = {
                "step_id": step_id, "decision": "refresh_required",
                "reason": "missing_failed_diagnostic_explicit_recompute",
                "missing_failed_diagnostic_proof": proof,
            }
            continue
        if old_batch is not None and step is None:
            raise ValueError("来源任务缺少深审批次定义")
        if step is not None and step.state == "completed":
            checkpoint = store.get_last_checkpoint(batch_source_id, step_id)
            if checkpoint is None:
                raise ValueError("已完成的来源批次缺少检查点")
            saved = checkpoint[1]
            if (old_batch is None or saved.get("stage") != "deep"
                    or saved.get("batch_id") != old_batch.batch_id):
                raise ValueError("已完成的来源批次身份损坏")
            identity = saved.get("transport_identity")
            if not isinstance(identity, dict):
                raise ValueError("已完成的来源批次缺少模型回执身份")
            actual_route = hashlib.sha256(json.dumps(
                identity, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")).hexdigest()
            if expected_route is not None and actual_route != expected_route:
                raise StepFailure(
                    retryable=False, error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
                    detail="来源深审批次模型线路与当前任务不一致。",
                )
            saved_prompt = saved.get("prompt_template_sha256")
            if not isinstance(saved_prompt, str) or len(saved_prompt) != 64:
                raise ValueError("已完成的来源批次缺少实际提示摘要")
            saved_result = saved.get("run_result")
            if (not isinstance(saved_result, dict)
                    or saved_result.get("status") not in {"已解析", "待跨章核验", "需要核对"}
                    or saved_result.get("batch_id") != old_batch.batch_id
                    or (not isinstance(saved_result.get("final_output"), dict)
                        and not isinstance(saved.get("restricted_batch"), dict))):
                raise ValueError("已完成的来源批次结果身份损坏")
            saved_components = saved.get("component_identity")
            if saved_components is not None:
                if (not isinstance(saved_components, dict)
                        or set(saved_components) != set(current_components)):
                    raise ValueError("已完成的来源批次组成身份损坏")
                for name, value in saved_components.items():
                    if not name.endswith("sha256") or value is None:
                        continue
                    if (not isinstance(value, str) or len(value) != 64
                            or any(char not in "0123456789abcdef" for char in value)):
                        raise ValueError("已完成的来源批次组成摘要损坏")
                if saved_components.get("schema_version") in {
                    "phase5/deep-component-identity/v2",
                    "phase5/deep-component-identity/v3",
                }:
                    repair_hash = saved.get("repair_contract_sha256")
                    if (not isinstance(repair_hash, str) or len(repair_hash) != 64
                            or any(char not in "0123456789abcdef" for char in repair_hash)):
                        raise ValueError("已完成的来源批次补答材料摘要损坏")
            if not _same_deep_batch_material(old_batch, batch):
                reason = "planning_material_changed"
            elif saved_prompt != expected_prompt:
                reason = "prompt_material_changed"
            else:
                if saved_components is None:
                    reason = "legacy_component_identity_unproven"
                    decisions[batch.batch_id] = {
                        "step_id": step_id, "decision": decision, "reason": reason,
                        **({"effective_source_job_id": batch_source_id, "source_lineage": source_lineage}
                           if source_lineage else {}),
                    }
                    continue
                if not _same_deep_components_with_current_gate(saved_components, current_components):
                    reason = "component_material_changed"
                    decisions[batch.batch_id] = {
                        "step_id": step_id, "decision": decision, "reason": reason,
                        **({"effective_source_job_id": batch_source_id, "source_lineage": source_lineage}
                           if source_lineage else {}),
                    }
                    continue
                if not _repair_material_matches(saved):
                    reason = "repair_material_changed_or_unproven"
                    decisions[batch.batch_id] = {
                        "step_id": step_id, "decision": decision, "reason": reason,
                        **({"effective_source_job_id": batch_source_id, "source_lineage": source_lineage}
                           if source_lineage else {}),
                    }
                    continue
                result = _saved_deep_run_result(saved)
                if result.batch_id != batch.batch_id:
                    raise ValueError("已完成的来源批次结果损坏")
                if saved.get("restricted_batch") is not None:
                    restricted = ProtocolControlBatchDispositionHydrated.model_validate(saved["restricted_batch"])
                    try:
                        expected = restricted_batch_from_review(batch, result)
                    except SourceTargetReviewValidationError as exc:
                        if (exc.code != "SOURCE_UNRESOLVED_STILL_EXCLUDED"
                                or saved_components["validator_version"] == current_components["validator_version"]):
                            raise
                        # A newly enforced pending-scope check invalidates this
                        # old proof, not the unaffected siblings or raw record.
                        reason = "current_source_review_requires_refresh"
                    else:
                        if expected is None or expected != restricted:
                            raise ValueError("已保存的受限来源与当前逐项核对不一致")
                        if _source_interpretation_requires_refresh(batch, result):
                            reason = "current_source_links_require_refresh"
                        else:
                            decision, reason = "reusable", "same_restricted_source_and_current_gate"
                else:
                    if result.status not in {"已解析", "待跨章核验"} or result.final_output is None:
                        raise ValueError("已完成的来源批次结果损坏")
                    try:
                        _validate_saved_source_review(batch, result)
                    except (SourceInterpretationValidationError, SourceTargetReviewValidationError,
                            SourceCandidateAlignmentValidationError):
                        reason = "current_source_review_requires_refresh"
                    else:
                        try:
                            _validate_deep_batch_output(batch, result.final_output)
                        except (ProtocolControlGateError, ProtocolControlAgentWireValidationError):
                            reason = "current_gate_requires_refresh"
                        else:
                            if _source_interpretation_requires_refresh(batch, result):
                                reason = "current_source_links_require_refresh"
                            else:
                                decision, reason = "reusable", "same_material_and_current_gate"
        elif step is not None and step.state == "failed_final":
            checkpoint = store.get_last_checkpoint(batch_source_id, step_id)
            partial = _validated_deep_partial_source(
                store, current_payload, batch_source_id, batch, step_id, prompt_template,
            )
            if partial is not None:
                decision = "resume_partial"
                base_reason = (
                    "verified_unpublished_draft" if partial[1].get("partial_wire") is not None
                    else "verified_source_interpretation"
                )
                review_state = partial[2].state
                reason = (
                    base_reason if review_state == "absent"
                    else base_reason + "_source_review_reused"
                    if review_state == "reused"
                    else base_reason + "_source_review_partially_reused"
                    if review_state == "partially_reused"
                    else base_reason + "_source_review_refresh_required"
                )
                control = current_payload.get("execution_control")
                if (isinstance(control, Mapping)
                        and control.get("continue_after_final_failure") == _INDEPENDENT_DEEP_READ_POLICY
                        and partial[2].source_seed_proof is None):
                    preserved = _preserved_source_review_proof(batch, partial[1])
                    if preserved is not None:
                        decision, reason = "preserve_unresolved", "same_material_failed_review_no_new_inference"
        decisions[batch.batch_id] = {
            "step_id": step_id, "decision": decision, "reason": reason,
            "source_review": review_state,
        }
        if source_lineage:
            decisions[batch.batch_id].update(
                effective_source_job_id=batch_source_id, source_lineage=source_lineage,
            )
        if decision in {"reusable", "resume_partial", "preserve_unresolved"}:
            decisions[batch.batch_id]["source_checkpoint_proof"] = _deep_source_checkpoint_proof(checkpoint)
        if decision == "preserve_unresolved":
            decisions[batch.batch_id]["unresolved_review_proof"] = preserved
        if (step is not None and step.state == "failed_final"
                and partial is not None and partial[2].source_seed_proof is not None):
            decisions[batch.batch_id]["reason"] = (
                "verified_source_interpretation_components_revalidated"
                if partial[2].source_seed_proof["schema_version"] in {
                    "phase5/revalidated-source-seed-proof/v3", "phase5/revalidated-source-seed-proof/v4",
                    "phase5/revalidated-source-seed-proof/v5"}
                else "verified_source_interpretation_repair_material_changed"
            )
            decisions[batch.batch_id]["source_seed_proof"] = partial[2].source_seed_proof
    return {
        "schema_version": "phase5/deep-reuse-plan/v1",
        "source_job_id": source_job_id,
        "source_plan_sha256": hashlib.sha256(json.dumps(
            source_plan.model_dump(mode="json"), ensure_ascii=False,
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
        "current_plan_sha256": hashlib.sha256(json.dumps(
            current_plan.model_dump(mode="json"), ensure_ascii=False,
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
        "expected_prompt_sha256": expected_prompt,
        "expected_route_sha256": expected_route,
        "component_identity": current_components,
        "decisions": decisions,
    }


def _source_interpretation_requires_refresh(
    batch: ProtocolControlDispositionBatch,
    result: ProtocolControlAgentRunResult,
) -> bool:
    interpretation = result.source_interpretation
    if interpretation is None:
        return False
    if any(
        is_study_phase_label(word)
        for statement in interpretation.statements
        for word in statement.time_words
    ):
        return True
    _, changed_anchors = normalize_schedule_randomization_anchors(batch, interpretation)
    if changed_anchors:
        return True
    _, changed_scopes = normalize_mixed_schedule_scopes(batch, interpretation)
    if changed_scopes:
        return True
    prior_coverage = {
        entry.statement_index: entry for entry in result.source_statement_coverage
    }
    for index, statement in enumerate(interpretation.statements):
        current_links = schedule_column_links(
            batch, statement.structure_unit_id, statement.quoted_text,
        )
        if current_links and (
            index not in prior_coverage
            or prior_coverage[index].schedule_columns != current_links
            or prior_coverage[index].disposition == "post_treatment_execution"
        ):
            return True
    return False


def _repair_material_matches(saved: Mapping[str, Any]) -> bool:
    result = saved.get("run_result")
    if not isinstance(result, Mapping) or type(result.get("repair_used")) is not bool:
        return False
    if not result["repair_used"]:
        return True
    receipt = saved.get("repair_contract_sha256")
    if receipt == protocol_control_agent_repair_contract_sha256():
        return True
    old_atom = protocol_control_agent_repair_contract_sha256(legacy_atom_v2=True)
    old_current = protocol_control_agent_repair_contract_sha256(
        without_duration_guidance=True
    )
    old_base = protocol_control_agent_repair_contract_sha256(base_only=True)
    if receipt not in {old_atom, old_current, old_base}:
        return False
    attempts = result.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        return False
    affected = {"TREATMENT_DURATION_USED_AS_EVENT_WINDOW"}
    if receipt == old_atom:
        affected.update({
            "WIRE_SCHEMA_INVALID", "CANDIDATE_REPAIR_INVALID",
            "ATOM_REPAIR_INVALID", "OBSERVATION_REPAIR_INVALID",
        })
    if receipt == old_base:
        affected.update({"OPTIONAL_ACTION_MODALITY_DROPPED",
                         "SOURCE_TARGET_ADDITIONAL_REQUIREMENT", "SOURCE_INSERT_INVALID"})
    error_classes = {
        code
        for attempt in attempts if isinstance(attempt, Mapping)
        for code in (attempt.get("error_classes") or ())
        if isinstance(code, str)
    }
    if receipt == old_atom and not error_classes:
        return all(
            isinstance(attempt, Mapping) and attempt.get("outcome") == "parsed"
            for attempt in attempts
        )
    return bool(error_classes) and error_classes.isdisjoint(affected)


def _validate_saved_source_review(
    batch: ProtocolControlDispositionBatch, result: ProtocolControlAgentRunResult,
) -> None:
    front_alignment_verified = False
    interpretation = result.source_interpretation
    if interpretation is None:
        if result.source_target_review is not None:
            raise ValueError("来源逐项核对缺少有源陈述")
        raise SourceTargetReviewValidationError(
            "来源逐项核对缺少有源陈述",
            code="SOURCE_INTERPRETATION_ABSENT",
            statement_index=None,
            json_path="/source_interpretation",
        )
    validate_source_interpretation(batch, interpretation)
    if result.workflow_variant_requested == "RV1001-FLOW" and result.final_output is not None:
        from app.agents.protocol_control_fixed_flow import supports_front_stage_flow
        if supports_front_stage_flow(batch, interpretation) and result.source_front_target_review is None:
            raise ValueError("前置流程请求缺少实际来源核对，不能改路径名称绕过")
    if result.workflow_path_executed == "front_stage_flow" and result.source_front_target_review is None:
        raise ValueError("固定流程结果缺少已核前置来源证明")
    if result.source_front_target_review is not None:
        from app.agents.protocol_control_fixed_flow import validate_front_review
        validate_front_review(batch, interpretation, result.source_front_target_review)
        if any(item.decision not in {"additional_requirement", "covered_by_official", "covered_by_procedure", "background_context", "definition_dependency"}
               for item in result.source_front_target_review.items):
            raise ValueError("前置新增要求核对不能借已有覆盖或未决通过采用")
        if result.final_output is None or result.partial_wire is None:
            raise ValueError("前置来源核对缺少最终候选与装配结果")
        if hydrate_protocol_control_agent_output(result.partial_wire, batch) != result.final_output:
            raise ValueError("前置要求的保存候选与实际装配草稿不一致")
        raw_front_coverage = source_statement_coverage(batch, interpretation, result.partial_wire)
        derived = hydrated_source_coverage_indexes(
            batch, result.partial_wire, result.final_output,
            raw_front_coverage,
        )
        front_decisions = {item.statement_index: item.decision for item in result.source_front_target_review.items}
        from app.agents.protocol_control_fixed_flow import covered_front_wire
        expected_base = covered_front_wire(
            batch, interpretation, result.source_front_target_review, allow_additional_units=True,
        )
        base_dispositions = {item.structure_unit_id: item.disposition for item in expected_base.dispositions}
        if derived != result.source_statement_coverage or any(
            entry.status != ("expressed" if front_decisions.get(entry.statement_index) == "additional_requirement"
                             else "candidate_linked" if base_dispositions[entry.structure_unit_id]
                             == StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
                             else "linked_only" if base_dispositions[entry.structure_unit_id] in {
                                 StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY,
                                 StructureUnitDispositionKind.REQUIRED_PROCEDURE,
                             } else "not_located") for entry in derived
        ):
            raise ValueError("前置要求未由保存的正式候选逐项表达")
        actual_dispositions = {item.structure_unit_id: item for item in result.partial_wire.dispositions}
        for disposition in expected_base.dispositions:
            actual = actual_dispositions.get(disposition.structure_unit_id)
            if (disposition.disposition != StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
                    and actual != disposition):
                raise ValueError("已有覆盖的装配链接与实际来源核对不一致")
            if disposition.disposition == StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE and (
                actual is None or actual.disposition != disposition.disposition
                or actual.linked_official_code is not None
                or actual.linked_procedure_catalog_item_id is not None
                or actual.linked_procedure_catalog_item_ids
            ):
                raise ValueError("混合来源不能借整段链接宣称邻近要求已覆盖")
        if all(item.decision != "additional_requirement"
               for item in result.source_front_target_review.items):
            expected_wire = covered_front_wire(batch, interpretation, result.source_front_target_review)
            if expected_wire != result.partial_wire:
                raise ValueError("已有覆盖的装配链接与实际来源核对不一致")
            required_indexes = set(target_review_indexes(interpretation, derived, batch))
            validate_source_target_review(batch, interpretation, derived,
                result.source_front_target_review.model_copy(update={"items": [
                    item for item in result.source_front_target_review.items
                    if item.statement_index in required_indexes
                ]}))
        else:
            alignment = result.source_candidate_alignment
            pairs = {(entry.statement_index, index) for entry in raw_front_coverage
                     for index in entry.candidate_indexes}
            if alignment is None or not pairs:
                raise ValueError("前置装配要求缺少实际返回的含义核对证明")
            validate_candidate_alignment(batch, interpretation, raw_front_coverage, result.partial_wire, alignment)
            proven = reusable_proven_alignment_items(
                batch, interpretation, raw_front_coverage, result.partial_wire, alignment,
            )
            if (len(proven) != len(pairs) or
                    {(item.statement_index, item.candidate_index) for item in proven} != pairs):
                raise ValueError("前置装配要求的含义核对证明不完整或已失效")
            front_alignment_verified = True
    review = result.source_target_review or SourceTargetReview(
        version=SOURCE_TARGET_REVIEW_VERSION, items=[],
    )
    validate_source_target_review(
        batch, interpretation, result.source_statement_coverage, review,
    )
    if target_review_indexes(interpretation, result.source_statement_coverage, batch) and not result.source_target_review:
        raise ValueError("待核来源陈述缺少逐项核对结果")
    if any(item.decision == "unresolved" for item in review.items):
        raise ValueError("来源逐项核对仍有未闭合要求")
    policy_pairs = []
    if result.final_output is not None and result.partial_wire is not None:
        if hydrate_protocol_control_agent_output(result.partial_wire, batch) != result.final_output:
            raise SourceCandidateAlignmentValidationError("保存的候选与实际装配草稿不一致")
        raw_policy_coverage = source_statement_coverage(batch, interpretation, result.partial_wire)
        policy_pairs = evidence_policy_alignment_pairs(interpretation, raw_policy_coverage, result.partial_wire)
        require_evidence_policy_alignment(
            batch, interpretation, raw_policy_coverage, result.partial_wire, result.source_candidate_alignment,
        )
    additions = {item.statement_index for item in review.items
                 if item.decision == "additional_requirement"}
    if additions:
        if (result.final_output is None or result.partial_wire is None
                or result.source_candidate_alignment is None):
            raise SourceCandidateAlignmentValidationError("新增要求缺少已保存的候选语义核对")
        try:
            rehydrated = hydrate_protocol_control_agent_output(result.partial_wire, batch)
            if rehydrated != result.final_output:
                raise ValueError("候选正式身份与保存的原草稿不一致")
            validate_candidate_alignment(
                batch, interpretation, result.source_statement_coverage,
                result.partial_wire, result.source_candidate_alignment,
            )
            expected_coverage = hydrated_source_coverage_indexes(
                batch, result.partial_wire, result.final_output,
                source_statement_coverage(batch, interpretation, result.partial_wire),
            )
        except ValueError as exc:
            raise SourceCandidateAlignmentValidationError(str(exc)) from exc
        aligned = {item.statement_index for item in result.source_candidate_alignment.items
                   if item.decision == "fully_expressed" and item.statement_index in additions}
        expected_pairs = set(policy_pairs) | {
            (item.statement_index, item.candidate_index) for item in result.source_candidate_alignment.items
            if item.statement_index in additions
        }
        if aligned != additions or len(result.source_candidate_alignment.items) != len(expected_pairs):
            raise SourceCandidateAlignmentValidationError("新增要求与已核候选未逐项对应")
        proven = reusable_proven_alignment_items(
            batch, interpretation, result.source_statement_coverage,
            result.partial_wire, result.source_candidate_alignment,
        )
        if len(proven) != len(expected_pairs):
            raise SourceCandidateAlignmentValidationError("候选对应证明未绑定当前完整来源与候选")
        for item in result.source_candidate_alignment.items:
            if item.statement_index not in additions:
                continue
            entry = next((entry for entry in result.source_statement_coverage
                          if entry.statement_index == item.statement_index), None)
            expected = next((entry for entry in expected_coverage
                             if entry.statement_index == item.statement_index), None)
            if entry is None or expected is None:
                raise SourceCandidateAlignmentValidationError("已核候选缺少逐项来源覆盖账")
            mapped = hydrated_source_coverage_indexes(
                batch, result.partial_wire, result.final_output,
                [expected.model_copy(update={"candidate_indexes": [item.candidate_index]})],
            )[0]
            if (entry.status != "semantically_aligned"
                    or expected.status != "candidate_linked"
                    or entry.action_candidate_indexes != expected.action_candidate_indexes
                    or entry.candidate_indexes != mapped.candidate_indexes):
                raise SourceCandidateAlignmentValidationError("已核候选与来源覆盖账不一致")
    elif result.source_candidate_alignment is not None and not front_alignment_verified:
        if {(item.statement_index, item.candidate_index) for item in result.source_candidate_alignment.items} != set(policy_pairs):
            raise SourceCandidateAlignmentValidationError("没有对应要求却保留候选语义核对")
    if source_definition_statement_indexes(interpretation) and result.source_definition_consumers is None:
        raise ValueError("来源定义缺少实际依赖登记回执，不能以全量核对替代未执行步骤")
    if result.source_definition_consumers is not None:
        validate_source_definition_consumers(
            batch, interpretation, result.source_definition_consumers,
        )


def _validated_deep_source(
    store: JobStore,
    current_payload: Mapping[str, Any],
    source_job_id: str,
    batch: ProtocolControlDispositionBatch,
    step_id: str,
    transport: Any,
    prompt_template: str,
) -> tuple[str | None, dict[str, Any] | None]:
    try:
        source_job = store.get_job(source_job_id)
        _require_compatible_deep_source(
            current_payload, verify_payload_sha256(source_job.payload_json, source_job.payload_sha256)
        )
        closure = store.get_last_checkpoint(source_job_id, STEP_CLOSURE)
        if closure is None or closure[1].get("stage") != "closure":
            raise ValueError("来源任务缺少已完成的分包计划")
        source_plan = ProtocolControlDiscoveryToDeepPlan.model_validate(
            closure[1].get("deep_plan")
        )
        matching = [item for item in source_plan.batches
                    if item.batch_number == batch.batch_number]
        if len(matching) != 1 or not _same_deep_batch_material(matching[0], batch):
            return None, None
        steps = {item.step_id: item for item in store.list_steps(source_job_id)}
        source_step = steps.get(step_id)
        if source_step is None:
            raise ValueError("来源任务缺少对应深审批次")
        if source_step.state != "completed":
            return None, None
        saved_checkpoint = store.get_last_checkpoint(source_job_id, step_id)
        if saved_checkpoint is None:
            raise ValueError("已完成的来源批次缺少检查点")
        checkpoint_id, saved = saved_checkpoint
        identity = saved.get("transport_identity")
        if (
            saved.get("stage") != "deep"
            or saved.get("batch_id") != batch.batch_id
            or saved.get("prompt_template_sha256")
            != protocol_control_agent_prompt_template_sha256(prompt_template)
            or not isinstance(saved.get("component_identity"), Mapping)
            or not _same_deep_components_with_current_gate(
                saved["component_identity"],
                _deep_component_identity(current_payload, prompt_template),
            )
            or not _repair_material_matches(saved)
            or identity != _transport_identity(transport, stage="deep")
        ):
            raise ValueError("已完成的来源批次提示或模型回执身份不一致")
        result = _saved_deep_run_result(saved)
        if result.batch_id != batch.batch_id:
            raise ValueError("来源深审结果身份不一致")
        if saved.get("restricted_batch") is not None:
            expected = restricted_batch_from_review(batch, result)
            if (expected is None or expected != ProtocolControlBatchDispositionHydrated.model_validate(
                    saved["restricted_batch"]
            )):
                raise ValueError("已保存的受限来源与当前逐项核对不一致")
            if _source_interpretation_requires_refresh(batch, result):
                return None, None
            return checkpoint_id, saved
        if result.status not in {"已解析", "待跨章核验"} or result.final_output is None:
            raise ValueError("来源深审结果不完整")
        if _source_interpretation_requires_refresh(batch, result):
            return None, None
        try:
            _validate_saved_source_review(batch, result)
        except (SourceInterpretationValidationError, SourceTargetReviewValidationError,
                SourceCandidateAlignmentValidationError):
            return None, None
        _validate_deep_batch_output(batch, result.final_output)
        return checkpoint_id, saved
    except (JobNotFoundError, ValueError, KeyError, TypeError, ValidationError,
            ProtocolControlGateError, PersistedContractInvalid) as exc:
        raise StepFailure(
            retryable=False, error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
            detail="既有深审批次无法证明与当前来源和校验要求一致：" + str(exc)[:900],
        ) from exc


def _frozen_official_predicates(
    config: ProtocolControlExecutorConfig,
    payload: Mapping[str, Any],
    batch: ProtocolControlDispositionBatch | None = None,
    *, official_codes: set[str] | None = None,
) -> tuple[
    dict[str, list[tuple[str, str]]],
    dict[str, dict[tuple[str, str], tuple[str, ...]]],
]:
    revision_id = payload.get("draft_revision_id")
    expected_hash = payload.get("draft_content_sha256")
    if revision_id is None and expected_hash is None:
        return {}, {}
    if not isinstance(revision_id, str) or not isinstance(expected_hash, str):
        raise StepFailure(
            retryable=False, error_code="PROTOCOL_CONTROL_DRAFT_INVALID",
            detail="方案草稿修订身份不完整，不能核对正式子条件。",
        )
    with config.session_factory() as session:
        try:
            revision = ProtocolDraftRevisionRepository(session).get(revision_id)
        except NotFoundError as exc:
            raise StepFailure(
                retryable=False, error_code="PROTOCOL_CONTROL_DRAFT_INVALID",
                detail="方案草稿修订不存在，不能核对正式子条件。",
            ) from exc
        source = payload.get("source_input") or {}
        if (revision.content_sha256 != expected_hash
                or revision.project_id != source.get("project_id")
                or revision.protocol_version_id != source.get("protocol_version_id")
                or getattr(revision.study_phase, "value", revision.study_phase)
                != source.get("selected_phase")):
            raise StepFailure(
                retryable=False, error_code="PROTOCOL_CONTROL_DRAFT_INVALID",
                detail="方案草稿修订与本次冻结来源不一致。",
            )
        rules = revision.content.proposed_rules
    allowed = (official_codes if official_codes is not None else
               ({target.official_code for target in batch.known_official_targets}
                if batch is not None else None))
    identities: dict[str, list[tuple[str, str]]] = {}
    excerpts: dict[str, dict[tuple[str, str], tuple[str, ...]]] = {}
    for rule in rules:
        if allowed is not None and rule.official_code not in allowed:
            continue
        for component in rule.components:
            expressions = [component.expression, component.exception_expression]
            expressions.extend(item.expression for item in component.repeat_trigger_conditions)
            for expression in expressions:
                if expression is None:
                    continue
                for predicate in iter_atomic_predicates(expression):
                    source_clauses = tuple(predicate.exact_source_clauses)
                    if not source_clauses:
                        continue
                    key = (component.rule_component_id, predicate.predicate_id)
                    if key in excerpts.setdefault(rule.official_code, {}):
                        raise StepFailure(
                            retryable=False, error_code="PROTOCOL_CONTROL_DRAFT_INVALID",
                            detail="方案草稿正式子条件身份重复。",
                        )
                    excerpts[rule.official_code][key] = source_clauses
                    identities.setdefault(rule.official_code, []).append(key)
    return identities, excerpts


def _bind_control_request_budget(
    context: StepContext, config: ProtocolControlExecutorConfig,
    transport: Any, *, request_basis: Callable[[], Mapping[str, Any]],
) -> LogicalCallBudget | None:
    """Bind one frozen work-unit allowance, including probes and nested retries."""
    request_limit = context.job_payload.get("deep_request_limit")
    binder = getattr(transport, "bind_logical_call_budget", None)
    if request_limit is None:
        if context.job_payload.get("deep_workflow_variant") == "RV1001-FLOW":
            raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_BUDGET_INVALID",
                              detail="隔离固定流程缺少冻结的累计请求上限，未发送请求。")
        if callable(binder):
            binder(None)
        return
    if type(request_limit) is not int or request_limit < 1:
        raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_BUDGET_INVALID",
                          detail="冻结的累计请求上限无效，未发送请求。")
    if not callable(binder):
        raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_BUDGET_UNSUPPORTED",
                          detail="模型传输尚不支持累计预算，未发送请求。")
    from app.services.protocol_deconstruction_executor import _ProtocolSemanticBatchFileCache
    identity = hashlib.sha256(json.dumps({
        "job_id": context.job_id, "step_id": context.step_id,
        "policy": "rv1001/deep-request-budget/v1",
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    contract = hashlib.sha256(json.dumps({
        **request_basis(), "transport": _transport_identity(transport, stage="deep"),
        "request_limit": request_limit,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    cache = _ProtocolSemanticBatchFileCache(config.data_paths, context.job_id)
    try:
        saved = cache.load_call_budget(identity)
        previous_payloads = [context.last_checkpoint] if getattr(context, "last_checkpoint", None) else []
        if getattr(config, "session_factory", None) is not None:
            with config.session_factory() as session:
                rows = session.scalars(select(JobCheckpointRecord).where(
                    JobCheckpointRecord.job_id == context.job_id,
                    JobCheckpointRecord.step_id == context.step_id,
                ))
                previous_payloads.extend(verify_payload_sha256(row.payload_json, row.payload_sha256)
                                         for row in rows)
        for previous in previous_payloads:
            snapshots = [previous.get("logical_call_budget")]
            snapshots.extend(receipt.get("logical_call_budget") for receipt in
                             previous.get("model_call_receipts", []) if isinstance(receipt, Mapping))
            for snapshot in snapshots:
                if not isinstance(snapshot, Mapping) or snapshot.get("logical_task_id") != identity:
                    continue
                used = snapshot.get("requests_used")
                reserved = snapshot.get("reserved_output_tokens")
                if used == 0 and reserved == 0 and snapshot.get("requests") == []:
                    continue
                if (type(used) is not int or type(reserved) is not int
                        or used < 0 or reserved < 0 or saved is None
                        or saved.get("requests_used", -1) < used
                        or saved.get("reserved_output_tokens", -1) < reserved
                        or saved.get("requests", [])[:used] != snapshot.get("requests")):
                    raise ValueError("已有步骤回执证明调用额度曾被使用，预算记录缺失或回退")
        budget = LogicalCallBudget(
            identity, max_requests=request_limit,
            max_output_tokens=request_limit * max(transport.max_tokens, PROTOCOL_CONTROL_LENGTH_RETRY_MAX_TOKENS),
            contract_sha256=contract, saved=saved,
            persist=cache.store_call_budget,
        )
        binder(budget)
        return budget
    except (ValueError, OSError, TypeError, KeyError, AttributeError) as exc:
        raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_BUDGET_RECORD_INVALID",
                          detail="累计请求记录缺失、回退或读取范围已变，未发送请求；请保留原记录，从方案整理建立有据的新任务。") from exc


def _restricted_deep_checkpoint(
    context: StepContext, batch: ProtocolControlDispositionBatch, transport: Any,
    prompt_template: str, result: ProtocolControlAgentRunResult,
    restricted_batch: ProtocolControlBatchDispositionHydrated,
    model_call_receipts: list[dict[str, Any]], resume_review: _ResumedSourceReview,
    *, failed: bool = False,
) -> dict[str, Any]:
    run_view = result.model_dump(mode="json")
    return {
        **({**run_view,
            "schema_version": "phase5/deep-failure-diagnostic/v3",
            "failure_reason_version": SOURCE_REQUIREMENT_FAILURE_REASON_VERSION,
            "restricted_registration_failed": True,
        } if failed else {}),
        "stage": "deep_failure_diagnostic" if failed else "deep",
        "workflow_variant": context.job_payload.get("deep_workflow_variant", "RV1001-BASELINE"),
        "model_call_receipts": model_call_receipts,
        "batch_id": batch.batch_id,
        "prompt_template_sha256": protocol_control_agent_prompt_template_sha256(prompt_template),
        "transport_identity": _transport_identity(transport, stage="deep"),
        "component_identity": _deep_component_identity(context.job_payload, prompt_template),
        "repair_contract_sha256": protocol_control_agent_repair_contract_sha256(),
        "run_result": run_view,
        **({"source_scope_question_history": result.source_scope_question_history}
           if result.source_scope_question_history else {}),
        "attempt_raw_outputs": _deep_attempt_raw_outputs(result),
        "source_review_reuse": _source_review_reuse_record(resume_review),
        "restricted_batch": restricted_batch.model_dump(mode="json"),
    }


def _saved_source_scope_question_history(saved: Mapping[str, Any] | None) -> list[dict[str, object]]:
    if saved is None:
        return []
    history = saved.get("source_scope_question_history")
    if history is None:
        run_result = saved.get("run_result")
        nested = isinstance(run_result, Mapping) and "attempts" not in saved
        attempts = run_result.get("attempts", []) if nested else saved.get("attempts", [])
        history = [attempt for attempt in attempts
                   if isinstance(attempt, Mapping) and isinstance(attempt.get("error_detail"), Mapping)
                   and attempt["error_detail"].get("workflow_phase") in {
                       "source_scope_question_recheck", "source_context_completion",
                   }]
        if nested and history:
            outputs = saved.get("attempt_raw_outputs", [])
            if not isinstance(outputs, list):
                raise ValueError("来源疑问的历史原答账损坏")
            restored = []
            for attempt in history:
                matches = [item for item in outputs if isinstance(item, Mapping)
                           and item.get("role") is None
                           and item.get("attempt") == attempt.get("attempt")
                           and item.get("session_id") == attempt.get("session_id")]
                if len(matches) != 1:
                    raise ValueError("来源疑问的历史原答缺失或重复")
                answer = matches[0].get("raw_output_text")
                failed_without_answer = answer is None and attempt.get("outcome") == "transport_failed"
                if (not failed_without_answer and (not isinstance(answer, str)
                        or len(answer) != attempt.get("raw_output_chars")
                        or hashlib.sha256(answer.encode("utf-8")).hexdigest()
                        != attempt.get("raw_output_sha256"))):
                    raise ValueError("来源疑问的历史原答与回执不一致")
                restored.append({**attempt, "raw_output_text": answer})
            history = restored
    if not isinstance(history, list) or any(not isinstance(item, Mapping) for item in history):
        raise ValueError("来源疑问的历史核对账损坏")
    for item in history:
        answer = item.get("raw_output_text")
        if answer is None and item.get("outcome") == "transport_failed":
            continue
        if (not isinstance(answer, str) or len(answer) != item.get("raw_output_chars")
                or hashlib.sha256(answer.encode("utf-8")).hexdigest() != item.get("raw_output_sha256")):
            raise ValueError("来源疑问的历史原答与回执不一致")
    return [dict(item) for item in history]


def _complete_restricted_deep_source(
    context: StepContext, config: ProtocolControlExecutorConfig,
    batch: ProtocolControlDispositionBatch, transport: Any,
    prompt_template: str, result: ProtocolControlAgentRunResult,
    restricted_batch: ProtocolControlBatchDispositionHydrated,
    model_call_receipts: list[dict[str, Any]], resume_review: _ResumedSourceReview,
    *, official_predicate_identities: Mapping[str, Any],
    official_predicate_sources: Mapping[str, Any],
    bind_budget: bool = False,
) -> dict[str, Any]:
    if (source_definition_statement_indexes(result.source_interpretation)
            and result.source_definition_consumers is None):
        from app.agents.protocol_control_deconstructor import declare_source_definition_consumers
        if bind_budget:
            _bind_control_request_budget(context, config, transport, request_basis=lambda: {
                "batch": batch.model_dump(mode="json"),
                "prompt": protocol_control_agent_prompt_template_sha256(prompt_template),
            })
        declarations: list[ProtocolControlAgentAttempt] = []
        declaration, failed = declare_source_definition_consumers(
            batch, transport, result.source_interpretation, restricted_batch, declarations,
            official_predicate_identities=official_predicate_identities,
            official_predicate_sources=official_predicate_sources,
        )
        result = result.model_copy(update={
            "source_definition_consumers": declaration,
            "restricted_source_definition_consumer_attempts": declarations,
        })
        take_receipts = getattr(transport, "take_call_receipts", None)
        model_call_receipts.extend(take_receipts() if callable(take_receipts) else [])
        if failed:
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_INVALID",
                detail="受限原文已保留，但定义依赖尚未实际登记，不能作为完整采用依据。",
                diagnostic_checkpoint=_restricted_deep_checkpoint(
                    context, batch, transport, prompt_template, result, restricted_batch,
                    model_call_receipts, resume_review, failed=True,
                ),
            )
        try:
            revalidated = restricted_batch_from_review(batch, result)
        except ValueError as exc:
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_INVALID",
                detail="定义登记未通过原答与来源核验，原文和失败记录保留。",
                diagnostic_checkpoint=_restricted_deep_checkpoint(
                    context, batch, transport, prompt_template, result, restricted_batch,
                    model_call_receipts, resume_review, failed=True,
                ),
            ) from exc
        if revalidated != restricted_batch:
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_INVALID",
                detail="定义登记后受限来源发生变化，未保存为可消费结果。",
                diagnostic_checkpoint=_restricted_deep_checkpoint(
                    context, batch, transport, prompt_template, result, restricted_batch,
                    model_call_receipts, resume_review, failed=True,
                ),
            )
    return _restricted_deep_checkpoint(
        context, batch, transport, prompt_template, result, restricted_batch,
        model_call_receipts, resume_review,
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
    try:
        _require_schedule_member_sources([*batch.owned_units, *batch.context_units])
    except ValueError as exc:
        raise StepFailure(
            retryable=False, error_code="PROTOCOL_CONTROL_TABLE_SOURCE_INVALID",
            detail=str(exc),
        ) from exc
    official_predicate_identities, official_predicate_sources = _frozen_official_predicates(
        config, context.job_payload, batch,
    )
    prompt_template = _prompt_from_payload(context, "deep", config)
    reuse_plan = context.job_payload.get("deep_reuse_plan")
    if reuse_plan is not None:
        ref = context.job_payload.get("deep_reuse_plan_artifact_ref")
        if not isinstance(reuse_plan, Mapping) or not isinstance(ref, str):
            raise StepFailure(retryable=False,
                error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
                detail="深审复用计划身份不完整。")
        try:
            persisted = json.loads(ArtifactStore(config.data_paths).read(ref))
        except (ArtifactStoreError, TypeError, ValueError) as exc:
            raise StepFailure(retryable=False,
                error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
                detail="深审复用计划工件无法核验。") from exc
        plan_hash = hashlib.sha256(json.dumps(
            deep_plan.model_dump(mode="json"), ensure_ascii=False,
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        if (persisted != reuse_plan
                or reuse_plan.get("schema_version") != "phase5/deep-reuse-plan/v1"
                or reuse_plan.get("current_plan_sha256") != plan_hash
                or reuse_plan.get("expected_prompt_sha256")
                != protocol_control_agent_prompt_template_sha256(prompt_template)
                or reuse_plan.get("component_identity")
                != _deep_component_identity(context.job_payload, prompt_template)):
            raise StepFailure(retryable=False,
                error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
                detail="深审复用计划与当前批次或提示不一致。")
    max_transport_retries, max_schema_repairs = _limits_from_payload(
        context, "deep", config
    )
    transport = _resolve_transport(config, stage="deep")
    _require_frozen_route(context, config, transport, stage="deep")

    resume_wire = None
    resume_interpretation = None
    resume_session_id = None
    resume_review = _ResumedSourceReview(state="absent", reason="no_saved_source_review")
    resume_alignment_saved: Mapping[str, Any] | None = None
    previous = context.last_checkpoint
    if isinstance(previous, Mapping) and previous.get("stage") == "deep_failure_diagnostic":
        saved_wire = previous.get("partial_wire")
        saved_source = previous.get("source_interpretation")
        if saved_wire is not None or saved_source is not None:
            if (
                previous.get("schema_version") != "phase5/deep-failure-diagnostic/v3"
                or previous.get("batch_id") != batch.batch_id
                or previous.get("prompt_template_sha256")
                != protocol_control_agent_prompt_template_sha256(prompt_template)
                or previous.get("transport_identity") != _transport_identity(transport, stage="deep")
                or previous.get("component_identity")
                != _deep_component_identity(context.job_payload, prompt_template)
                or previous.get("repair_contract_sha256")
                != protocol_control_agent_repair_contract_sha256()
                or not isinstance(saved_source, Mapping)
                or (saved_wire is not None and not isinstance(previous.get("session_id"), str))
            ):
                raise StepFailure(retryable=False,
                    error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
                    detail="局部深审草稿与当前来源、提示或模型线路不一致。")
            try:
                resume_interpretation = SourceInterpretation.model_validate(
                    saved_source
                )
                validate_source_interpretation(batch, resume_interpretation)
                if saved_wire is not None:
                    resume_wire = ProtocolControlAgentWire.model_validate(saved_wire)
                    _validate_deep_batch_output(
                        batch, hydrate_protocol_control_agent_output(resume_wire, batch)
                    )
            except (TypeError, ValueError) as exc:
                raise StepFailure(retryable=False,
                    error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
                    detail="局部深审草稿结构损坏，不得作为已核结果继续。") from exc
            if resume_wire is not None:
                resume_session_id = previous["session_id"]
            # A saved review is proven against the current batch even when the
            # failed run had no reusable partial wire; an unproven one is
            # recorded as refresh_required and never silently adopted.
            resume_review = _resumable_saved_source_review(
                batch, resume_interpretation, previous,
            )
            resume_alignment_saved = previous

    deep_source_job_id = context.job_payload.get("deep_source_job_id")
    if deep_source_job_id is not None:
        if not isinstance(deep_source_job_id, str) or deep_source_job_id == context.job_id:
            raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID", detail="深审来源任务编号无效。")
        plan = reuse_plan
        decision = None
        if isinstance(plan, Mapping):
            entry = plan.get("decisions", {}).get(batch.batch_id)
            if not isinstance(entry, Mapping) or entry.get("step_id") != context.step_id:
                raise StepFailure(retryable=False,
                    error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
                    detail="深审复用计划与当前批次不一致。")
            decision = entry.get("decision")
            if decision not in {"reusable", "refresh_required", "resume_partial", "preserve_unresolved"}:
                raise StepFailure(retryable=False,
                    error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
                    detail="深审复用计划的批次处置无效。")
            try:
                with config.session_factory() as session:
                    actual_source, actual_lineage = _resolve_unexecuted_deep_source(
                        JobStore(session, now=config.now), context.job_payload,
                        deep_source_job_id, batch, context.step_id,
                    )
                if (entry.get("effective_source_job_id", deep_source_job_id) != actual_source
                        or entry.get("source_lineage", []) != actual_lineage):
                    raise ValueError("实际来源关系与入队前证明不一致")
                deep_source_job_id = actual_source
                if entry.get("source_checkpoint_proof") is not None:
                    with config.session_factory() as session:
                        frozen_checkpoint = JobStore(session, now=config.now).get_last_checkpoint(
                            deep_source_job_id, context.step_id,
                        )
                    if (frozen_checkpoint is None or _deep_source_checkpoint_proof(frozen_checkpoint)
                            != entry["source_checkpoint_proof"]):
                        raise ValueError("已核检查点与入队前证明不一致")
            except (JobNotFoundError, ValueError, KeyError, TypeError, PersistedContractInvalid) as exc:
                raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
                                  detail="已核来源的复用关系无法核实，未发送请求。") from exc
            if entry.get("missing_failed_diagnostic_proof") is not None:
                try:
                    if decision != "refresh_required":
                        raise ValueError("缺记录范围不得复用")
                    with config.session_factory() as session:
                        actual = _missing_failed_diagnostic_proof(
                            JobStore(session, now=config.now), deep_source_job_id, context.step_id,
                        )
                    if actual != entry["missing_failed_diagnostic_proof"]:
                        raise ValueError("缺记录范围与前置证明不一致")
                except ValueError as exc:
                    raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
                                      detail="原失败记录状态已变化，未继续重新读取。") from exc
        checkpoint_id, saved = None, None
        if decision == "preserve_unresolved":
            control = context.job_payload.get("execution_control")
            if (not isinstance(control, Mapping)
                    or control.get("continue_after_final_failure") != _INDEPENDENT_DEEP_READ_POLICY):
                raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
                                  detail="保留原未决仅限已冻结的独立来源核查，未发送请求。")
            try:
                with config.session_factory() as session:
                    partial = _validated_deep_partial_source(
                        JobStore(session, now=config.now), context.job_payload,
                        deep_source_job_id, batch, context.step_id, prompt_template,
                    )
                proof = (_preserved_source_review_proof(batch, partial[1])
                         if partial is not None and partial[2].source_seed_proof is None else None)
            except ValueError as exc:
                raise StepFailure(
                    retryable=False, error_code="PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID",
                    detail="已保存的未决来源未通过当前逐项重核，原记录保持。",
                ) from exc
            if proof is None or proof != entry.get("unresolved_review_proof"):
                raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
                                  detail="原未决与入队前证明不一致，未发送请求。")
            checkpoint_id, diagnostic, prior_review = partial
            try:
                prior_result = _saved_failed_deep_run_result(batch, diagnostic)
                restricted = restricted_batch_from_review(batch, prior_result)
            except ValueError as exc:
                raise StepFailure(
                    retryable=False, error_code="PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID",
                    detail="已保存的未决来源未通过当前逐项重核，原记录保持。",
                ) from exc
            if restricted is not None:
                checkpoint = _complete_restricted_deep_source(
                    context, config, batch, transport, prompt_template, prior_result,
                    restricted, [], prior_review,
                    official_predicate_identities=official_predicate_identities,
                    official_predicate_sources=official_predicate_sources,
                    bind_budget=True,
                )
                return {
                    **checkpoint,
                    "revalidated_restricted_from": {
                        "job_id": deep_source_job_id, "checkpoint_id": checkpoint_id,
                        "proof": proof,
                    },
                    "new_model_calls": len(checkpoint["model_call_receipts"]), "adopted": False,
                }
            raise StepFailure(
                retryable=False, error_code=proof["error_code"],
                detail="原文对应关系仍未核清，本次保留原未决且不重复读取；其他独立来源可继续核查。",
                diagnostic_checkpoint={**diagnostic, "model_call_receipts": [],
                    "preserved_unresolved_from": {"job_id": deep_source_job_id,
                        "checkpoint_id": checkpoint_id, "proof": proof},
                    "new_model_calls": 0, "adopted": False},
            )
        if decision == "reusable":
            with config.session_factory() as session:
                checkpoint_id, saved = _validated_deep_source(
                    JobStore(session, now=config.now), context.job_payload,
                    deep_source_job_id, batch, context.step_id, transport,
                    prompt_template,
                )
            if (saved is None or (entry.get("source_checkpoint_proof") is not None
                    and _deep_source_checkpoint_proof((checkpoint_id, saved)) != entry["source_checkpoint_proof"])):
                raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
                                  detail="已核结果与入队前证明不一致，未发送请求。")
        if saved is not None:
            current_components = _deep_component_identity(context.job_payload, prompt_template)
            prior_components = saved["component_identity"]
            return {**saved, "component_identity": current_components,
                    "revalidated_from_gate_version": (
                        prior_components["validator_version"]
                        if prior_components["validator_version"] != current_components["validator_version"]
                        else None
                    ), "adopted_from": {
                "job_id": deep_source_job_id, "checkpoint_id": checkpoint_id,
                **({"source_lineage": entry["source_lineage"]}
                   if isinstance(plan, Mapping) and entry.get("source_lineage") else {}),
            }}
        if decision == "resume_partial" and resume_wire is None:
            with config.session_factory() as session:
                partial = _validated_deep_partial_source(
                    JobStore(session, now=config.now), context.job_payload,
                    deep_source_job_id, batch, context.step_id, prompt_template,
                )
            if partial is None:
                raise StepFailure(
                    retryable=False, error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
                    detail="已核局部草稿不再符合当前方案或批次，未继续执行。",
                )
            _, draft, resume_review = partial
            if (isinstance(plan, Mapping)
                    and plan["decisions"][batch.batch_id].get("source_seed_proof")
                    != resume_review.source_seed_proof):
                raise StepFailure(
                    retryable=False, error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
                    detail="来源解释复用证明与入队前计划不一致。",
                )
            if draft.get("transport_identity") != _transport_identity(transport, stage="deep"):
                raise StepFailure(
                    retryable=False, error_code="PROTOCOL_CONTROL_DEEP_SOURCE_INVALID",
                    detail="局部草稿的实际模型线路与当前任务不一致。",
                )
            resume_interpretation = SourceInterpretation.model_validate(
                draft["source_interpretation"]
            )
            if draft.get("partial_wire") is not None:
                resume_wire = ProtocolControlAgentWire.model_validate(draft["partial_wire"])
                resume_session_id = draft["session_id"]
            resume_alignment_saved = draft

    resume_candidate_alignment = None
    if resume_wire is not None and context.job_payload.get("deep_workflow_variant") == "RV1001-FLOW":
        raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_FLOW_RESUME_PROOF_REQUIRED",
                          detail="该局部装配尚无经过恢复消费者核验的前置证明；旧产物保留，未发送模型请求。")
    if (resume_alignment_saved is not None and resume_interpretation is not None
            and resume_wire is not None):
        coverage_payload = resume_alignment_saved.get("source_statement_coverage")
        alignment_coverage: list[SourceStatementCoverage]
        if isinstance(coverage_payload, list) and coverage_payload:
            try:
                alignment_coverage = [
                    SourceStatementCoverage.model_validate(item)
                    for item in coverage_payload
                ]
            except (TypeError, ValidationError):
                alignment_coverage = []
        else:
            alignment_coverage = []
        resume_candidate_alignment = _resumable_saved_candidate_alignment(
            batch, resume_interpretation, alignment_coverage, resume_wire,
            resume_alignment_saved,
        )

    if not callable(getattr(transport, "start_source_interpretation", None)):
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_SOURCE_READER_UNAVAILABLE",
            detail="方案来源逐项核对服务不可用，不能跳过来源陈述直接生成控制。",
        )
    _bind_control_request_budget(context, config, transport, request_basis=lambda: {
        "batch": batch.model_dump(mode="json"),
        "prompt": protocol_control_agent_prompt_template_sha256(prompt_template),
    })
    result = ProtocolControlAgentRunner(
        max_transport_retries=max_transport_retries,
        max_schema_repairs=max_schema_repairs,
    ).run(
        batch,
        transport,
        prompt_template=prompt_template,
        output_validator=lambda output: _validate_deep_batch_output(batch, output),
        resume_wire=resume_wire,
        resume_source_interpretation=resume_interpretation,
        resume_session_id=resume_session_id,
        resume_source_target_review=(
            resume_review.review if resume_interpretation is not None else None
        ),
        resume_source_statement_coverage=(
            resume_review.coverage if resume_interpretation is not None else ()
        ),
        resume_source_candidate_alignment=resume_candidate_alignment,
        resume_source_scope_question_history=_saved_source_scope_question_history(resume_alignment_saved),
        resume_source_scope_correction_indexes=resume_review.source_scope_correction_indexes,
        official_predicate_identities=official_predicate_identities,
        official_predicate_sources=official_predicate_sources,
        workflow_variant=context.job_payload.get("deep_workflow_variant", "RV1001-BASELINE"),
    )
    take_receipts = getattr(transport, "take_call_receipts", None)
    model_call_receipts = take_receipts() if callable(take_receipts) else []
    restricted_batch = None
    restricted_error: ValueError | None = None
    try:
        if isinstance(result, ProtocolControlAgentRunResult):
            if result.final_output is not None:
                _validate_saved_source_review(batch, result)
            restricted_batch = restricted_batch_from_review(batch, result)
    except ValueError as exc:
        restricted_error = exc
    if restricted_batch is not None:
        return _complete_restricted_deep_source(
            context, config, batch, transport, prompt_template, result, restricted_batch,
            model_call_receipts, resume_review,
            official_predicate_identities=official_predicate_identities,
            official_predicate_sources=official_predicate_sources,
        )
    if (restricted_error is not None or result.status not in {"已解析", "待跨章核验"}
            or result.final_output is None):
        source_review_failure_codes = {
            "SOURCE_COVERAGE_INVALID",
            "LOGICAL_BUDGET_EXHAUSTED",
            "FLOW_TRANSPORT_FAILED", "FLOW_COMPLETION_UNCERTAIN", "FLOW_RESPONSE_INVALID", "FLOW_ASSEMBLY_INVALID",
            "FLOW_SOURCE_SCOPE_UNRESOLVED", "FLOW_TARGET_ALREADY_COVERED",
            "FLOW_COMPILER_CAPABILITY_GAP",
            "SOURCE_FUNCTION_RECHECK_TRANSPORT_FAILED",
            "SOURCE_FUNCTION_RECHECK_SCHEMA_INVALID",
            "SOURCE_FUNCTION_RECHECK_INVALID",
            "SOURCE_FUNCTION_RECHECK_UNRESOLVED",
            "SOURCE_FUNCTION_FIELD_REPAIR_TRANSPORT_FAILED", "SOURCE_FUNCTION_FIELD_REPAIR_INVALID",
            "SOURCE_TARGET_REVIEW_TRANSPORT_FAILED",
            "SOURCE_TARGET_FOCUSED_TRANSPORT_FAILED",
            "SOURCE_TARGET_FOCUSED_INVALID",
            "SOURCE_TARGET_FOCUSED_SCHEMA_INVALID",
            "SOURCE_TARGET_REVIEW_UNAVAILABLE",
            "SOURCE_TARGET_REVIEW_UNRESOLVED",
            "SOURCE_TARGET_REVIEW_INVALID",
            "SOURCE_SCOPE_CORRECTION_JSON_INVALID",
            "SOURCE_REQUIREMENT_CONSUMER_UNAVAILABLE",
            "SOURCE_REQUIREMENT_INSERTION_LIMIT_REACHED",
            "SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED",
            "SOURCE_CANDIDATE_ALIGNMENT_TRANSPORT_FAILED",
            "SOURCE_REQUIREMENT_TRANSPORT_FAILED",
            "SOURCE_INTERPRETATION_CORRECTION_TRANSPORT_FAILED",
            "EVIDENCE_POLICY_REVIEW_UNAVAILABLE", "EVIDENCE_POLICY_UNJUSTIFIED",
            "MODEL_IDENTITY_INVALID",
        }
        source_review_failure = next((code for code in (
            result.attempts[-1].error_classes if result.attempts else []
        ) if code in source_review_failure_codes or result.workflow_path_executed == "front_stage_flow"), None)
        raise StepFailure(
            retryable=(restricted_error is None
                       and source_review_failure in {
                           "FLOW_TRANSPORT_FAILED",
                           "SOURCE_FUNCTION_RECHECK_TRANSPORT_FAILED",
                           "SOURCE_FUNCTION_FIELD_REPAIR_TRANSPORT_FAILED",
                           "SOURCE_TARGET_REVIEW_TRANSPORT_FAILED",
                           "SOURCE_TARGET_FOCUSED_TRANSPORT_FAILED",
                           "SOURCE_CANDIDATE_ALIGNMENT_TRANSPORT_FAILED",
                           "SOURCE_REQUIREMENT_TRANSPORT_FAILED",
                       }),
            error_code=("PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID" if restricted_error
                        else "PROTOCOL_CONTROL_" + source_review_failure if source_review_failure
                        else "PROTOCOL_CONTROL_CAPABILITY_RESTRICTION_UNPROVEN"
                        if result.capability_wire is not None
                        else "PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID"),
            detail=_run_diagnostics(
                result.attempts,
                ("来源逐项核对与未决陈述相矛盾：" + str(restricted_error)[:500]
                 if restricted_error else
                 "原文要求小时或分钟精度，但该批尚未满足有源局部采用条件；结果保持未采信。"
                 if result.capability_wire is not None else
                 {
                     "SOURCE_SCOPE_CORRECTION_JSON_INVALID":
                         "模型未按要求返回本条来源范围，修订尚未应用；原文和已核内容保留。",
                     "SOURCE_TARGET_REVIEW_UNRESOLVED":
                         "原文已保存，但它与审核要求的对应关系仍需核清；尚不能作为完整采用依据。",
                     "SOURCE_REQUIREMENT_CONSUMER_UNAVAILABLE":
                         "原文支持的补充要求尚缺可靠的装配核验能力，由系统建设继续处理。",
                     "SOURCE_REQUIREMENT_INSERTION_LIMIT_REACHED":
                         "补充要求在本次限定修订次数内尚未核验完成；已核清的部分保留。",
                     "SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED":
                         "已保存原文引用，但尚未证明审核要求忠实表达了原文含义。",
                 }.get(source_review_failure, "深析批次在限定修复次数内未产出合规输出。")),
            ),
            diagnostic_checkpoint={
                "stage": "deep_failure_diagnostic",
                "workflow_variant": context.job_payload.get("deep_workflow_variant", "RV1001-BASELINE"),
                "model_call_receipts": model_call_receipts,
                "schema_version": "phase5/deep-failure-diagnostic/v3",
                "failure_reason_version": SOURCE_REQUIREMENT_FAILURE_REASON_VERSION,
                "batch_id": batch.batch_id,
                "session_id": result.session_id,
                "partial_wire": (
                    result.partial_wire.model_dump(mode="json")
                    if result.partial_wire is not None else None
                ),
                "capability_wire": (
                    result.capability_wire.model_dump(mode="json")
                    if result.capability_wire is not None else None
                ),
                "prompt_template_sha256": protocol_control_agent_prompt_template_sha256(
                    prompt_template
                ),
                "transport_identity": _transport_identity(transport, stage="deep"),
                "component_identity": _deep_component_identity(context.job_payload, prompt_template),
                "repair_contract_sha256": protocol_control_agent_repair_contract_sha256(),
                "source_interpretation": (
                    result.source_interpretation.model_dump(mode="json")
                    if result.source_interpretation is not None else None
                ),
                "pending_source_interpretation": (
                    result.pending_source_interpretation.model_dump(mode="json")
                    if result.pending_source_interpretation is not None else None
                ),
                "source_statement_coverage": [
                    item.model_dump(mode="json")
                    for item in result.source_statement_coverage
                ],
                "source_target_review": (
                    result.source_target_review.model_dump(mode="json")
                    if result.source_target_review is not None else None
                ),
                "source_front_target_review": (
                    result.source_front_target_review.model_dump(mode="json")
                    if result.source_front_target_review is not None else None
                ),
                "workflow_path_executed": result.workflow_path_executed,
                "source_candidate_alignment": (
                    result.source_candidate_alignment.model_dump(mode="json")
                    if result.source_candidate_alignment is not None else None
                ),
                "source_review_reuse": _source_review_reuse_record(resume_review),
                "attempts": [
                    {
                        "attempt": item.attempt,
                        "session_id": item.session_id,
                        "outcome": item.outcome,
                        "raw_output_sha256": item.raw_output_sha256,
                        "raw_output_chars": item.raw_output_chars,
                        "raw_output_text": item.raw_output_text,
                        "error_classes": item.error_classes,
                        "error_detail": item.error_detail,
                        "issues": item.issues,
                    }
                    for item in result.attempts
                ],
                **({"source_scope_question_history": result.source_scope_question_history}
                   if result.source_scope_question_history else {}),
                **_pending_definition_consumer_checkpoint(result),
            },
        )
    return {
        "stage": "deep",
        "workflow_variant": context.job_payload.get("deep_workflow_variant", "RV1001-BASELINE"),
        "model_call_receipts": model_call_receipts,
        "batch_id": batch.batch_id,
        "prompt_template_sha256": protocol_control_agent_prompt_template_sha256(
            prompt_template
        ),
        "transport_identity": _transport_identity(transport, stage="deep"),
        "component_identity": _deep_component_identity(context.job_payload, prompt_template),
        "repair_contract_sha256": protocol_control_agent_repair_contract_sha256(),
        "run_result": result.model_dump(mode="json"),
        **({"source_scope_question_history": result.source_scope_question_history}
           if result.source_scope_question_history else {}),
        "attempt_raw_outputs": _deep_attempt_raw_outputs(result),
        "source_review_reuse": _source_review_reuse_record(resume_review),
    }


def _deep_attempt_raw_outputs(result: ProtocolControlAgentRunResult) -> list[dict[str, Any]]:
    """Keep answer evidence in the private checkpoint, outside the public run model."""

    outputs = [{
        "attempt": item.attempt,
        "session_id": item.session_id,
        "raw_output_sha256": item.raw_output_sha256,
        "raw_output_chars": item.raw_output_chars,
        "raw_output_text": item.raw_output_text,
    } for item in result.attempts]
    # The pending definition-consumer diagnostic keeps its own 1-based attempt
    # sequence. Only these entries carry a role, so an existing consumer of the
    # author/source-target answers reads the unchanged legacy shape.
    outputs.extend({
        "attempt": item.attempt,
        "session_id": item.session_id,
        "raw_output_sha256": item.raw_output_sha256,
        "raw_output_chars": item.raw_output_chars,
        "raw_output_text": item.raw_output_text,
        "role": "pending_source_definition_consumer",
    } for item in result.pending_source_definition_consumer_attempts)
    outputs.extend({
        "attempt": item.attempt,
        "session_id": item.session_id,
        "raw_output_sha256": item.raw_output_sha256,
        "raw_output_chars": item.raw_output_chars,
        "raw_output_text": item.raw_output_text,
        "role": "restricted_source_definition_consumer",
    } for item in result.restricted_source_definition_consumer_attempts)
    return outputs


def _saved_deep_run_result(payload: Mapping[str, Any]) -> ProtocolControlAgentRunResult:
    """Restore only source-bound private answers; public result bytes stay unchanged."""
    result = ProtocolControlAgentRunResult.model_validate(payload.get("run_result"))
    question_history = _saved_source_scope_question_history(payload)
    if question_history:
        result = result.model_copy(update={"source_scope_question_history": question_history})
    attempts = result.restricted_source_definition_consumer_attempts
    if not attempts:
        return result
    outputs = payload.get("attempt_raw_outputs", [])
    if not isinstance(outputs, list):
        raise ValueError("受限定义登记原答清单损坏")
    saved = [item for item in outputs
             if isinstance(item, Mapping)
             and item.get("role") == "restricted_source_definition_consumer"]
    if len(saved) != len(attempts):
        raise ValueError("受限定义登记原答回执缺失或重复")
    restored = []
    for attempt, answer in zip(attempts, saved, strict=True):
        if any(answer.get(key) != getattr(attempt, key) for key in (
            "attempt", "session_id", "raw_output_sha256", "raw_output_chars",
        )):
            raise ValueError("受限定义登记原答身份不一致")
        raw = answer.get("raw_output_text")
        if (not isinstance(raw, str) or len(raw) != attempt.raw_output_chars
                or hashlib.sha256(raw.encode("utf-8")).hexdigest() != attempt.raw_output_sha256):
            raise ValueError("受限定义登记原答损坏")
        restored.append(attempt.model_copy(update={"raw_output_text": raw}))
    return result.model_copy(update={"restricted_source_definition_consumer_attempts": restored})


def _saved_failed_deep_run_result(
    batch: ProtocolControlDispositionBatch, saved: Mapping[str, Any],
) -> ProtocolControlAgentRunResult:
    fields = {key: value for key, value in saved.items()
              if key in ProtocolControlAgentRunResult.model_fields}
    pending = fields.get("pending_source_definition_consumer_attempts")
    if pending is not None:
        if not isinstance(pending, list):
            raise ValueError("待核定义登记回执清单损坏")
        projected = []
        for item in pending:
            if not isinstance(item, Mapping):
                raise ValueError("待核定义登记回执损坏")
            record = dict(item)
            has_envelope = "role" in record
            if "role" in record:
                if record.pop("role") != "pending_source_definition_consumer":
                    raise ValueError("待核定义登记回执角色不一致")
            raw = record.get("raw_output_text")
            if (raw is not None and (not isinstance(raw, str)
                    or len(raw) != record.get("raw_output_chars")
                    or hashlib.sha256(raw.encode("utf-8")).hexdigest()
                    != record.get("raw_output_sha256"))):
                raise ValueError("待核定义登记原答损坏")
            if has_envelope and raw is None and record.get("raw_output_chars") is not None:
                raise ValueError("待核定义登记原答缺失")
            # Only the producer's private role envelope is removed. Unknown
            # fields still fail the unchanged strict attempt contract.
            projected.append(record)
        fields["pending_source_definition_consumer_attempts"] = projected
    return _saved_deep_run_result({
        "run_result": {
            **fields,
            "status": "需要核对", "batch_id": batch.batch_id,
        },
        "attempt_raw_outputs": saved.get("attempt_raw_outputs"),
        "source_scope_question_history": _saved_source_scope_question_history(saved),
    })


def _pending_definition_consumer_checkpoint(
    result: ProtocolControlAgentRunResult,
) -> dict[str, Any]:
    """Persist the bounded pending declaration diagnostic, only when one exists.

    The proposal and its own attempts stay separate from the original failure
    fields, and raw answers stay in this private checkpoint instead of any
    public result or log.
    """

    if (result.pending_source_definition_consumers is None
            and not result.pending_source_definition_consumer_attempts):
        return {}
    return {
        "pending_source_definition_consumer_output_sha256": (
            result.pending_source_definition_consumer_output_sha256
        ),
        "pending_source_definition_consumer_adoptable": False,
        "pending_source_definition_consumers": (
            result.pending_source_definition_consumers.model_dump(mode="json")
            if result.pending_source_definition_consumers is not None else None
        ),
        "pending_source_definition_consumer_attempts": [{
            "attempt": item.attempt,
            "session_id": item.session_id,
            "outcome": item.outcome,
            "raw_output_sha256": item.raw_output_sha256,
            "raw_output_chars": item.raw_output_chars,
            "raw_output_text": item.raw_output_text,
            "error_classes": item.error_classes,
            "error_detail": item.error_detail,
            "issues": item.issues,
            "role": "pending_source_definition_consumer",
        } for item in result.pending_source_definition_consumer_attempts],
    }


def _source_review_reuse_record(resume_review: _ResumedSourceReview) -> dict[str, Any]:
    """Record the validated source seed, not candidate acceptance or saved calls."""

    record = {
        "state": resume_review.state,
        "reason": resume_review.reason,
        "proof_scope": "saved_source_target_review",
        "verified_seed_statements": sorted(
            item.statement_index for item in (
                resume_review.review.items if resume_review.review is not None else ()
            )
        ),
    }
    if resume_review.source_scope_correction_indexes:
        record["source_scope_correction_indexes"] = list(resume_review.source_scope_correction_indexes)
    if resume_review.source_seed_proof is not None:
        record["proof_scope"] = (
            "revalidated_source_interpretation"
            if resume_review.source_seed_proof["schema_version"] in {
                "phase5/revalidated-source-seed-proof/v3", "phase5/revalidated-source-seed-proof/v4",
                "phase5/revalidated-source-seed-proof/v5"}
            else "unrepaired_source_interpretation"
        )
        record["source_seed_proof"] = dict(resume_review.source_seed_proof)
    return record


def _definition_consumer_atom(
    candidate: Any, consumer: ProtocolControlDefinitionAtomConsumption,
) -> tuple[Any, list[str]]:
    """Resolve one declared consumer position inside a frozen candidate."""

    if consumer.consumer_kind != "control_atom":
        raise ValueError("官方条件消费不能按控制原子解析")
    semantics = getattr(candidate, "semantics", None)
    if semantics is None:
        raise ValueError("消费原子所属候选缺少冻结语义")
    if consumer.layer == "repeat_trigger":
        condition = next(
            (item for item in semantics.repeat_trigger_conditions
             if item.condition_id == consumer.condition_id),
            None,
        )
        expression = condition.expression if condition is not None else None
    else:
        expression = getattr(semantics, f"{consumer.layer}_expression", None)
    groups = expression.groups if expression is not None else ()
    if consumer.group_index >= len(groups):
        raise ValueError("消费原子引用了不存在的条件组")
    atoms = groups[consumer.group_index].atoms
    if consumer.atom_index >= len(atoms):
        raise ValueError("消费原子引用了不存在的原子")
    atom = atoms[consumer.atom_index]
    excerpts = [value for value in atom.source_excerpts if value]
    continuation = getattr(atom, "continuing_obligation", None)
    if continuation is not None:
        excerpts.extend(value for value in continuation.source_excerpts if value)
    return atom, excerpts


def _definition_consumer_official_target(
    consumer: ProtocolControlDefinitionAtomConsumption,
    targets: Mapping[str, KnownOfficialRuleTarget],
) -> list[str]:
    """Resolve a declared official consumer against the batch's frozen targets.

    This proves the declared official code is one of the batch's frozen official
    targets and returns that target's own declared excerpts. The finer
    ``(rule_component_id, predicate_id)`` identity is proven against the frozen
    RuleSet where it exists (publication and working draft); a parent code alone
    never selects a consumer.
    """

    if consumer.consumer_kind != "official_predicate":
        raise ValueError("控制原子消费不能按官方条件解析")
    target = targets.get(consumer.official_code)
    if target is None:
        raise ValueError("官方条件消费引用了本批冻结官方目标之外的编号")
    return [value for value in target.source_excerpts if value]


def _source_definition_consumers(
    deep_plan: ProtocolControlDiscoveryToDeepPlan,
    outputs: Mapping[str, ProtocolControlBatchDispositionHydrated],
    reviewed: Mapping[str, ProtocolControlAgentRunResult],
) -> list[ProtocolControlDefinitionConsumerRecord]:
    """Close declared definition consumers into frozen, identity-bound records.

    Every calculation definition of every deep batch yields exactly one record.
    Each side of the relation is verified against its own frozen source: the
    definition quote stays on the record, and the declared consumer excerpt must
    occur in that consumer's own declared frozen excerpts — a control candidate
    atom resolved by position, or a frozen official target resolved by code. The
    two anchors are never required to contain each other, and ``scope_complete``
    is never claimed here, because this per-batch closure cannot prove the
    complete consumer scope including consumers in other batches.
    """

    records: list[ProtocolControlDefinitionConsumerRecord] = []
    for batch in deep_plan.batches:
        run = reviewed[batch.batch_id]
        interpretation = run.source_interpretation
        if interpretation is None:
            continue
        output = outputs[batch.batch_id]
        units = {unit.structure_unit_id: unit for unit in batch.owned_units}
        declared = (
            {item.statement_index: item for item in run.source_definition_consumers.items}
            if run.source_definition_consumers is not None else {}
        )
        reviews = (
            {item.statement_index: item for item in run.source_target_review.items}
            if run.source_target_review is not None else {}
        )
        definition_indexes = set(source_definition_statement_indexes(interpretation))
        stray = sorted(set(declared) - definition_indexes)
        if stray:
            raise StepFailure(
                retryable=False,
                error_code="PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_INVALID",
                detail="定义消费登记引用了非定义来源陈述：" + ",".join(map(str, stray)),
            )
        for index, statement in enumerate(interpretation.statements):
            if index not in definition_indexes:
                continue
            unit = units.get(statement.structure_unit_id)
            if unit is None:
                raise StepFailure(
                    retryable=False,
                    error_code="PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_INVALID",
                    detail="定义所在来源单元不属于本批冻结来源。",
                )
            review = reviews.get(index)
            if is_post_eligibility_calculation(statement, review):
                continue
            reasons = {
                *statement.unresolved,
                *(review.unresolved_aspects if review is not None else ()),
            }
            if run.source_definition_consumers is None:
                reasons.add("来源定义缺少实际依赖登记回执，需补齐后重新核对")
            entry = declared.get(index)
            consumers: list[ProtocolControlDefinitionAtomConsumption] = []
            official_targets = {
                target.official_code: target for target in batch.known_official_targets
            }
            if entry is not None:
                reasons.update(entry.unresolved_aspects)
                for consumer in entry.consumers:
                    if consumer.consumer_kind == "restricted_statement":
                        targets = {item.restricted_statement_id: item for item in output.restricted_statements}
                        target = targets.get(consumer.restricted_statement_id)
                        if (target is None or target.source_structure_unit_id not in units
                                or (target.source_structure_unit_id, target.source_statement_index)
                                == (statement.structure_unit_id, index)):
                            raise StepFailure(retryable=False,
                                error_code="PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_INVALID",
                                detail="定义消费登记未对应实际受限陈述，不能猜补或借用原子身份。")
                        excerpts = [target.source_quote]
                    elif consumer.consumer_kind == "official_predicate":
                        try:
                            excerpts = _definition_consumer_official_target(
                                consumer, official_targets,
                            )
                        except ValueError as exc:
                            raise StepFailure(
                                retryable=False,
                                error_code="PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_INVALID",
                                detail="官方条件消费未绑定本批冻结官方目标：" + str(exc),
                            ) from exc
                    else:
                        if consumer.candidate_index >= len(output.candidates):
                            raise StepFailure(
                                retryable=False,
                                error_code="PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_INVALID",
                                detail="定义消费原子引用了不存在的候选。",
                            )
                        candidate = output.candidates[consumer.candidate_index]
                        try:
                            _, excerpts = _definition_consumer_atom(candidate, consumer)
                        except ValueError as exc:
                            raise StepFailure(
                                retryable=False,
                                error_code="PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_INVALID",
                                detail="定义消费原子未绑定冻结候选原子：" + str(exc),
                            ) from exc
                    consumer_excerpt = normalize_source_excerpt(consumer.consumer_excerpt)
                    if not consumer_excerpt or not any(
                        consumer_excerpt in normalize_source_excerpt(excerpt)
                        for excerpt in excerpts
                    ):
                        raise StepFailure(
                            retryable=False,
                            error_code="PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_UNGROUNDED",
                            detail="消费来源摘录不在该消费者自身声明的冻结原文中。",
                        )
                    if consumer.consumer_kind == "restricted_statement":
                        consumers.append(ProtocolControlDefinitionAtomConsumption(
                            consumer_kind="restricted_statement",
                            restricted_statement_id=consumer.restricted_statement_id,
                            consumer_excerpt=consumer.consumer_excerpt,
                            relation_note=consumer.relation_note,
                        ))
                    elif consumer.consumer_kind == "official_predicate":
                        consumers.append(ProtocolControlDefinitionAtomConsumption(
                            consumer_kind="official_predicate",
                            rule_component_id=consumer.rule_component_id,
                            predicate_id=consumer.predicate_id,
                            consumer_excerpt=consumer.consumer_excerpt,
                            relation_note=consumer.relation_note,
                        ))
                    else:
                        consumers.append(ProtocolControlDefinitionAtomConsumption(
                            control_candidate_id=candidate.control_candidate_id,
                            layer=consumer.layer,
                            condition_id=consumer.condition_id,
                            group_index=consumer.group_index,
                            atom_index=consumer.atom_index,
                            consumer_excerpt=consumer.consumer_excerpt,
                            relation_note=consumer.relation_note,
                        ))
            # A missing declaration is not proof that no other batch consumes
            # this definition; the per-batch view never closes global scope.
            reasons.add(_DEFINITION_CONSUMER_SCOPE_UNPROVEN)
            records.append(ProtocolControlDefinitionConsumerRecord(
                batch_id=batch.batch_id,
                source_structure_unit_id=statement.structure_unit_id,
                source_statement_index=index,
                source_quote=statement.quoted_text,
                source_span_ids=sorted(unit.source_span_ids),
                consumers=consumers,
                scope_complete=False,
                unresolved_reasons=sorted(reasons),
            ))
    return records


def _require_definition_consumer_checkpoint_match(
    hydrate: Mapping[str, Any],
    verified: Sequence[ProtocolControlDefinitionConsumerRecord],
) -> None:
    """A pre-contract checkpoint must not acquire the relation by re-derivation."""

    if hydrate.get("source_definition_consumers", []) != [
        item.model_dump(mode="json") for item in verified
    ]:
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_INVALID",
            detail="来源定义消费关系与已核深审批次不一致。",
        )


def _deep_results(
    context: StepContext,
    config: ProtocolControlExecutorConfig,
    closure: Mapping[str, Any],
) -> tuple[
    dict[str, ProtocolControlBatchDispositionHydrated],
    list[ProtocolControlSourceUnitRelation],
    list[ProtocolControlDefinitionConsumerRecord],
]:
    deep_plan = ProtocolControlDiscoveryToDeepPlan.model_validate(closure["deep_plan"])
    deep_step_ids = closure.get("deep_step_ids") or []
    if not isinstance(deep_step_ids, list) or len(deep_step_ids) != len(deep_plan.batches):
        raise StepFailure(
            retryable=False,
            error_code="PROTOCOL_CONTROL_DEEP_PLAN_INVALID",
            detail="深析步骤与冻结批次数量不一致。",
        )
    output: dict[str, ProtocolControlBatchDispositionHydrated] = {}
    reviewed: dict[str, ProtocolControlAgentRunResult] = {}
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
            try:
                run_result = _saved_deep_run_result(payload)
            except (TypeError, ValueError) as exc:
                raise StepFailure(
                    retryable=False, error_code="PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID",
                    detail="已保存的深审原答回执缺失或损坏，不能作为采用依据。",
                ) from exc
            if payload.get("restricted_batch") is not None:
                try:
                    expected = restricted_batch_from_review(batch, run_result)
                    restricted = ProtocolControlBatchDispositionHydrated.model_validate(
                        payload["restricted_batch"]
                    )
                    if expected is None or restricted != expected:
                        raise ValueError("受限来源与已保存的原文核对不一致")
                except (TypeError, ValueError) as exc:
                    raise StepFailure(
                        retryable=False,
                        error_code="PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID",
                        detail="受限来源陈述未通过逐条原文重核。",
                    ) from exc
                output[batch.batch_id] = restricted
                reviewed[batch.batch_id] = run_result
                continue
            if (
                run_result.status not in {"已解析", "待跨章核验"}
                or run_result.final_output is None
                or run_result.batch_id != batch.batch_id
            ):
                raise StepFailure(
                    retryable=False,
                    error_code="PROTOCOL_CONTROL_DEEP_INCOMPLETE",
                    detail="深析阶段存在未接受或身份不一致的批次结果。",
                )
            try:
                _validate_saved_source_review(batch, run_result)
            except ValueError as exc:
                raise StepFailure(
                    retryable=False,
                    error_code="PROTOCOL_CONTROL_SOURCE_REVIEW_INVALID",
                    detail="深析来源与逐项核对结果不一致：" + str(exc)[:500],
                ) from exc
            result = run_result.final_output
            if list(result.owned_structure_unit_ids) != list(batch.owned_structure_unit_ids):
                raise StepFailure(
                    retryable=False,
                    error_code="PROTOCOL_CONTROL_DEEP_SCOPE_INVALID",
                    detail="深析结果未闭合到冻结 owned 结构单元。",
                )
            output[batch.batch_id] = result
            reviewed[batch.batch_id] = run_result
    owner = {
        unit.structure_unit_id: (batch, unit)
        for batch in deep_plan.batches for unit in batch.owned_units
    }
    relations: list[ProtocolControlSourceUnitRelation] = []
    for batch in deep_plan.batches:
        run_result = reviewed[batch.batch_id]
        restricted_indexes = {item.source_statement_index
                              for item in output[batch.batch_id].restricted_statements}
        pending = [item for item in (run_result.source_target_review.items
                                     if run_result.source_target_review else [])
                   if item.decision == "potential_same_requirement"
                   and item.statement_index not in restricted_indexes]
        if (bool(pending) != (run_result.status == "待跨章核验")
                and not (pending and run_result.status == "需要核对" and restricted_indexes)):
            raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_SOURCE_RELATION_INVALID",
                              detail="跨章节待核状态与逐项来源对应不一致。")
        if pending and (run_result.source_interpretation is None or run_result.source_target_review is None):
            raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_SOURCE_RELATION_INVALID",
                              detail="跨章节对应缺少逐项来源核对原始结果。")
        source_statements = run_result.source_interpretation.statements if run_result.source_interpretation else []
        if pending:
            try:
                validate_source_target_review(
                    batch, run_result.source_interpretation,
                    run_result.source_statement_coverage, run_result.source_target_review,
                )
            except ValueError as exc:
                raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_SOURCE_RELATION_INVALID",
                                  detail="跨章节来源复核未通过原文校验。") from exc
        for item in pending:
            if item.statement_index >= len(source_statements):
                raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_SOURCE_RELATION_INVALID",
                                  detail="跨章节来源陈述序位不属于已核批次。")
            statement = source_statements[item.statement_index]
            source_unit = next((unit for unit in batch.owned_units
                                if unit.structure_unit_id == statement.structure_unit_id), None)
            target_owner = owner.get(item.target_id or "")
            if (source_unit is None or target_owner is None
                    or item.target_id not in batch.context_structure_unit_ids):
                raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_SOURCE_RELATION_INVALID",
                                  detail="跨章节关系的两端不属于冻结原文及只读范围。")
            target_batch, target_unit = target_owner
            target_run = reviewed[target_batch.batch_id]
            target_statements = (target_run.source_interpretation.statements
                                 if target_run.source_interpretation else [])
            matches = [entry for entry in target_run.source_statement_coverage
                       if entry.status in {"expressed", "semantically_aligned"}
                       and entry.statement_index < len(target_statements)
                       and target_statements[entry.statement_index].structure_unit_id == target_unit.structure_unit_id
                       and target_statements[entry.statement_index].force == statement.force
                       and normalize_source_excerpt(item.target_object_excerpt or "")
                       in normalize_source_excerpt(target_statements[entry.statement_index].quoted_text)
                       and normalize_source_excerpt(item.target_action_excerpt or "")
                       in normalize_source_excerpt(target_statements[entry.statement_index].quoted_text)
                       and normalize_source_excerpt(item.target_scope_excerpt or "")
                       in normalize_source_excerpt(" ".join(filter(None, (
                           target_statements[entry.statement_index].quoted_text,
                           target_statements[entry.statement_index].scope_quote,
                       ))))]
            candidate_indexes = {index for entry in matches for index in entry.candidate_indexes}
            if target_run.status != "已解析" or len(candidate_indexes) != 1:
                raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_SOURCE_RELATION_UNRESOLVED",
                                  detail="另一章节尚无唯一且已核实的同一要求，不能合并来源。")
            candidate = output[target_batch.batch_id].candidates[next(iter(candidate_indexes))]
            atom_excerpts = []
            if candidate.semantics is not None:
                for expression in (
                    candidate.semantics.applicability_expression,
                    candidate.semantics.trigger_expression,
                    candidate.semantics.obligation_expression,
                    candidate.semantics.exception_expression,
                ):
                    if expression is not None:
                        atom_excerpts.extend(excerpt for group in expression.groups
                                             for atom in group.atoms for excerpt in atom.source_excerpts)
            if (target_unit.structure_unit_id not in candidate.frozen_structure_unit_ids
                    or not all(any(normalize_source_excerpt(phrase) in normalize_source_excerpt(excerpt)
                                   for excerpt in atom_excerpts)
                               for phrase in (item.target_object_excerpt, item.target_action_excerpt,
                                              item.target_scope_excerpt))):
                raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_SOURCE_RELATION_UNRESOLVED",
                                  detail="另一章节的正式候选未同时表达原文动作和适用时期。")
            relations.append(ProtocolControlSourceUnitRelation(
                source_structure_unit_id=source_unit.structure_unit_id,
                source_statement_index=item.statement_index,
                source_action_excerpt=item.source_action_excerpt,
                source_object_excerpt=item.source_object_excerpt or "",
                source_span_ids=sorted(source_unit.source_span_ids),
                target_structure_unit_id=target_unit.structure_unit_id,
                target_action_excerpt=item.target_action_excerpt or "",
                target_object_excerpt=item.target_object_excerpt or "",
                target_scope_excerpt=item.target_scope_excerpt or "",
                target_span_ids=sorted(target_unit.source_span_ids),
                target_candidate_id=candidate.control_candidate_id,
            ))
    return (
        output,
        sorted(relations, key=lambda item: (
            item.source_structure_unit_id, item.source_statement_index,
        )),
        _source_definition_consumers(deep_plan, output, reviewed),
    )


def _definition_scope_basis(
    context: StepContext, config: ProtocolControlExecutorConfig,
) -> tuple[list[ProtocolControlDefinitionConsumerRecord], dict[str, object], dict]:
    closure = _closure_checkpoint(context, config)
    outputs, _, records = _deep_results(context, config, closure)
    _, official_sources = _frozen_official_predicates(
        config, context.job_payload,
    )
    inventory, keyed = definition_scope_inputs(records, outputs, official_sources)
    return records, inventory, keyed


def _execute_definition_scope(
    context: StepContext, config: ProtocolControlExecutorConfig,
) -> dict[str, Any]:
    records, inventory, keyed = _definition_scope_basis(context, config)
    review = None
    session_id = None
    prompt_sha256 = None
    raw_output_sha256 = None
    source_scope_evidence: dict[str, str] = {}
    model_call_receipts: list[dict[str, object]] = []
    prior_unassigned_model_receipts: list[dict[str, object]] = []
    logical_call_budget = None
    budget = None
    if records:
        transport = _resolve_transport(config, stage="deep")
        _require_frozen_route(context, config, transport, stage="deep")
        reader = getattr(transport, "start_definition_scope", None)
        if not callable(reader):
            raise StepFailure(
                retryable=False, error_code="PROTOCOL_CONTROL_DEFINITION_SCOPE_UNAVAILABLE",
                detail="本次方案分析模型没有全批次定义核对能力。",
            )
        try:
            prompt = build_definition_scope_prompt(inventory)
            prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            take_receipts = getattr(transport, "take_call_receipts", None)
            if callable(take_receipts):
                prior_unassigned_model_receipts = take_receipts()
            budget = _bind_control_request_budget(context, config, transport, request_basis=lambda: {
                "inventory_sha256": inventory["sha256"], "prompt": prompt_sha256,
            })
            artifacts = ArtifactStore(config.data_paths)
            source_scope_evidence["raw_request_ref"] = artifacts.put(
                "raw_request", prompt.encode("utf-8"),
            ).storage_ref
            response = reader(prompt=prompt)
            take_receipts = getattr(transport, "take_call_receipts", None)
            if callable(take_receipts):
                model_call_receipts = take_receipts()
            logical_call_budget = budget.snapshot() if budget is not None else None
            session_id = response.session_id
            raw_output_sha256 = hashlib.sha256(response.text.encode("utf-8")).hexdigest()
            source_scope_evidence["raw_response_ref"] = artifacts.put(
                "raw_response", response.text.encode("utf-8"),
            ).storage_ref
            review = DefinitionScopeReview.model_validate_json(response.text)
            closed = close_definition_scope(
                records, review, inventory, keyed,
                scope_unproven_reason=_DEFINITION_CONSUMER_SCOPE_UNPROVEN,
            )
        except ProtocolControlAgentCallError as exc:
            failure = protocol_control_call_failure_code(exc)
            code = {
                "MODEL_IDENTITY_INVALID": "MODEL_IDENTITY_INVALID",
                "LOGICAL_BUDGET_EXHAUSTED": "PROTOCOL_CONTROL_LOGICAL_BUDGET_EXHAUSTED",
                "FLOW_COMPLETION_UNCERTAIN": "PROTOCOL_CONTROL_DEFINITION_SCOPE_COMPLETION_UNCERTAIN",
            }.get(failure, "PROTOCOL_CONTROL_DEFINITION_SCOPE_TRANSPORT_FAILED")
            take_receipts = getattr(transport, "take_call_receipts", None)
            raise StepFailure(
                retryable=failure is None, error_code=code,
                detail=("定义影响范围的本次读取未完成，原记录保留；"
                        "连接故障、可能已执行的断流与额度用尽分别处理。"),
                diagnostic_checkpoint={
                    "stage": "definition_scope_failure_diagnostic", "inventory_sha256": inventory["sha256"],
                    "prompt_sha256": prompt_sha256, "raw_output_sha256": raw_output_sha256,
                    "session_id": exc.session_id, "source_scope_evidence": source_scope_evidence,
                    "model_call_receipts": take_receipts() if callable(take_receipts) else [],
                    "prior_unassigned_model_receipts": prior_unassigned_model_receipts,
                    "logical_call_budget": budget.snapshot() if budget is not None else None,
                },
            ) from exc
        except StepFailure as exc:
            raise StepFailure(
                retryable=exc.retryable, error_code=exc.error_code, detail=exc.detail,
                diagnostic_checkpoint={
                    "stage": "definition_scope_failure_diagnostic", "inventory_sha256": inventory["sha256"],
                    "prompt_sha256": prompt_sha256, "source_scope_evidence": source_scope_evidence,
                    "model_call_receipts": [],
                    "prior_unassigned_model_receipts": prior_unassigned_model_receipts,
                },
            ) from exc
        except (ValueError, TypeError, AttributeError, ArtifactStoreError, OSError) as exc:
            raise StepFailure(
                retryable=False, error_code="PROTOCOL_CONTROL_DEFINITION_SCOPE_INVALID",
                detail="全批次定义影响范围未核清：" + str(exc)[:900],
                diagnostic_checkpoint={
                    "stage": "definition_scope_failure_diagnostic", "inventory_sha256": inventory["sha256"],
                    "prompt_sha256": prompt_sha256, "raw_output_sha256": raw_output_sha256,
                    "session_id": session_id, "source_scope_evidence": source_scope_evidence,
                    "model_call_receipts": model_call_receipts,
                    "prior_unassigned_model_receipts": prior_unassigned_model_receipts,
                    "logical_call_budget": logical_call_budget,
                },
            ) from exc
    else:
        closed = []
    return {
        "stage": STEP_SCOPE,
        "inventory_sha256": inventory["sha256"],
        "prompt_sha256": prompt_sha256,
        "raw_output_sha256": raw_output_sha256,
        "review": None if review is None else review.model_dump(mode="json"),
        "session_id": session_id,
        "source_scope_evidence": source_scope_evidence,
        "model_call_receipts": model_call_receipts,
        "prior_unassigned_model_receipts": prior_unassigned_model_receipts,
        "logical_call_budget": logical_call_budget,
        "source_definition_consumers": [item.model_dump(mode="json") for item in closed],
    }


def _verified_definition_scope(
    context: StepContext, config: ProtocolControlExecutorConfig,
    *, checkpoint: Mapping[str, Any] | None = None,
) -> list[ProtocolControlDefinitionConsumerRecord]:
    if checkpoint is None:
        checkpoint = _checkpoint_for_step(context, STEP_SCOPE, config)
    records, inventory, keyed = _definition_scope_basis(context, config)
    if (checkpoint.get("stage") != STEP_SCOPE
            or checkpoint.get("inventory_sha256") != inventory["sha256"]):
        raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DEFINITION_SCOPE_INVALID",
                          detail="全批次定义核对与当前冻结来源不一致。")
    raw = checkpoint.get("review")
    if records:
        if raw is None:
            raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DEFINITION_SCOPE_INVALID",
                              detail="计算定义缺少全批次影响范围核对。")
        expected_prompt = hashlib.sha256(
            build_definition_scope_prompt(inventory).encode("utf-8")
        ).hexdigest()
        if (checkpoint.get("prompt_sha256") != expected_prompt
                or not isinstance(checkpoint.get("raw_output_sha256"), str)
                or len(checkpoint["raw_output_sha256"]) != 64
                or not checkpoint.get("session_id")):
            raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DEFINITION_SCOPE_INVALID",
                              detail="全批次定义核对缺少对应提示与模型返回身份。")
        try:
            evidence = checkpoint.get("source_scope_evidence")
            if (not isinstance(evidence, dict)
                    or set(evidence) != {"raw_request_ref", "raw_response_ref"}
                    or not all(isinstance(ref, str) for ref in evidence.values())
                    or evidence["raw_request_ref"] != "artifacts/raw_request/" + expected_prompt
                    or evidence["raw_response_ref"] != "artifacts/raw_response/" + checkpoint["raw_output_sha256"]):
                raise ValueError("缺少本次实际提示与原始返回工件，旧哈希记录不能替代核对依据")
            artifacts = ArtifactStore(config.data_paths)
            prompt_bytes = artifacts.read(evidence["raw_request_ref"])
            response_bytes = artifacts.read(evidence["raw_response_ref"])
            if prompt_bytes != build_definition_scope_prompt(inventory).encode("utf-8"):
                raise ValueError("核对提示工件与当前来源清单不一致")
            actual_review = DefinitionScopeReview.model_validate_json(response_bytes)
            if actual_review.model_dump(mode="json") != raw:
                raise ValueError("已保存核对内容与实际模型原始返回不一致")
            reviewed = close_definition_scope(
                records, actual_review, inventory, keyed,
                scope_unproven_reason=_DEFINITION_CONSUMER_SCOPE_UNPROVEN,
            )
        except (TypeError, ValueError, AttributeError, ArtifactStoreError, OSError) as exc:
            raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DEFINITION_SCOPE_INVALID",
                              detail="全批次定义核对内容无效：" + str(exc)[:900]) from exc
    else:
        if (raw is not None or checkpoint.get("prompt_sha256") is not None
                or checkpoint.get("raw_output_sha256") is not None
                or checkpoint.get("source_scope_evidence")):
            raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DEFINITION_SCOPE_INVALID",
                              detail="无计算定义的任务不能夹带模型核对。")
        reviewed = []
    if checkpoint.get("source_definition_consumers") != [
        item.model_dump(mode="json") for item in reviewed
    ]:
        raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_DEFINITION_SCOPE_INVALID",
                          detail="全批次定义核对记录与已保存结果不一致。")
    return reviewed


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
    deep_results, source_unit_relations, _ = _deep_results(
        context, config, closure,
    )
    source_definition_consumers = _verified_definition_scope(context, config)
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
        "source_unit_relations": [item.model_dump(mode="json") for item in source_unit_relations],
        "source_definition_consumers": [
            item.model_dump(mode="json") for item in source_definition_consumers
        ],
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
    _, verified_relations, _ = _deep_results(
        context, config, _closure_checkpoint(context, config),
    )
    verified_definition_consumers = _verified_definition_scope(context, config)
    if hydrate.get("source_unit_relations", []) != [
        item.model_dump(mode="json") for item in verified_relations
    ]:
        raise StepFailure(retryable=False, error_code="PROTOCOL_CONTROL_SOURCE_RELATION_INVALID",
                          detail="跨章节来源对应与已核深审批次不一致。")
    _require_definition_consumer_checkpoint_match(hydrate, verified_definition_consumers)

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
        restricted_statements=sorted(
            (statement for batch in batch_results
             for statement in batch.restricted_statements),
            key=lambda item: (item.source_structure_unit_id, item.source_statement_index),
        ),
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
        "source_unit_relations": hydrate.get("source_unit_relations", []),
        "source_definition_consumers": hydrate.get("source_definition_consumers", []),
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
    "STEP_SCOPE",
    "STEP_GATE",
    "STEP_HYDRATE",
    "create_protocol_control_executor",
    "protocol_control_route_identity_from_config",
]
