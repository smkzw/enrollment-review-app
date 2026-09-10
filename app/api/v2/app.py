"""V2 持久任务 API 应用工厂。

启动序列（prd.md 验收）：

1. 解析 V2 数据根（``ENROLLMENT_V2_DATA_DIR``，默认 ``<repo>/data_v2``）；
2. ``upgrade_or_fail``：迁移到 head + schema/PRAGMA 验证，失败拒绝启动写服务；
3. 启动恢复：过期租约任务从最后成功 Checkpoint 恢复，不存在永久 processing；
4. 启动后台 JobRunner（可配置关闭，测试用）；
5. 关闭时停止 runner 并释放 Engine。

Phase 2 只新增独立 /api/v2 应用，不切换 legacy 默认入口；``app/main.py`` 不动。
启动方式：``uvicorn app.api.v2.app:create_app --factory``。
"""
from __future__ import annotations

import json
import threading
from collections.abc import Callable, Mapping
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any

from fastapi import FastAPI

from app.api.v2.errors import register_error_handlers
from app.api.v2.evidence import router as evidence_router
from app.api.v2.evidence_processing import router as evidence_processing_router
from app.api.v2.jobs import router as jobs_router
from app.api.v2.protocol_control import router as protocol_control_router
from app.api.v2.fact_corrections import router as fact_corrections_router
from app.api.v2.fact_normalization import router as fact_normalization_router
from app.api.v2.judgment_search import router as judgment_search_router
from app.api.v2.eligibility_review import router as eligibility_review_router
from app.api.v2.page_review import router as page_review_router
from app.services.judgment_search_job_service import JUDGMENT_SEARCH_JOB_TYPE
from app.services.page_review_runtime import PageReviewRuntime
from app.services.page_review_job_service import PAGE_REVIEW_JOB_TYPE
from app.api.v2.patient_profiles import router as patient_profiles_router
from app.api.v2.protocols import (
    projects_router as protocol_projects_router,
)
from app.api.v2.protocols import (
    router as protocols_router,
)
from app.api.v2.subjects import router as subjects_router
from app.domain.contracts.enums import FactNormalizationRunStatus
from app.domain.contracts.evidence_upload import EVIDENCE_PROCESSING_JOB_TYPE
from app.evidence.artifacts import ArtifactStore
from app.services.evidence_activation_service import EvidenceActivationService
from app.services.evidence_api_command_service import EvidenceApiCommandService
from app.services.evidence_api_read_service import EvidenceApiReadService
from app.services.evidence_app_bootstrap import DataPaths, upgrade_or_fail
from app.services.evidence_correction_service import EvidenceCorrectionService
from app.services.evidence_processing_executor import (
    EvidenceProcessingExecutorConfig,
    create_evidence_processing_executor,
    recover_evidence_ocr_runs,
)
from app.services.evidence_referenced_document_service import (
    EvidenceReferencedDocumentService,
)
from app.services.evidence_revision_build_executor import (
    EVIDENCE_REVISION_BUILD_JOB_TYPE,
    EvidenceRevisionBuildExecutorConfig,
    cancel_revision_candidate_for_job,
    create_evidence_revision_build_executor,
)
from app.services.evidence_revision_workflow import EvidenceRevisionWorkflow
from app.services.evidence_risk_service import EvidenceRiskScanService
from app.services.evidence_upload_service import EvidenceUploadService
from app.services.fact_normalization_executor import (
    FactNormalizationExecutorConfig,
    create_fact_normalization_executor,
)
from app.services.fact_correction_executor import (
    FactCorrectionExecutorConfig,
    create_fact_correction_executor,
)
from app.services.fact_correction_job_service import (
    FACT_CORRECTION_JOB_TYPE,
    FactCorrectionJobService,
)
from app.services.fact_normalization_command_service import (
    FactNormalizationCommandService,
    register_evidence_normalizer_runtime_config,
)
from app.services.fact_normalization_job_service import FACT_NORMALIZATION_JOB_TYPE
from app.services.fact_normalization_job_service import (
    FactNormalizationJobService,
    project_fact_normalization_run_status,
    recover_fact_normalization_runs,
)
from app.services.job_service import JobService
from app.services.omlx_gate import OmlxGateClient, omlx_http_inference
from app.services.patient_profile_service import PatientProfileService
from app.services.eligibility_review_projection import EligibilityReviewProjectionService
from app.services.selective_vision_postprocess_executor import (
    SelectiveVisionPostprocessExecutorConfig,
    create_selective_vision_postprocess_executor,
)
from app.services.selective_vision_postprocess_job_service import (
    SELECTIVE_VISION_POSTPROCESS_JOB_TYPE,
    SelectiveVisionPostprocessJobService,
)
from app.services.protocol_deconstruction_executor import (
    ProtocolDeconstructionExecutorConfig,
    create_protocol_deconstruction_executor,
)
from app.services.protocol_workbench_service import (
    PROTOCOL_DECONSTRUCTION_JOB_TYPE,
    ProtocolWorkbenchService,
)
from app.services.protocol_control_executor import (
    PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
    ProtocolControlExecutorConfig,
    create_protocol_control_executor,
)
from app.services.protocol_control_job_service import ProtocolControlJobService
from app.agents.protocol_semantic_route_preflight import (
    EndpointProber,
    preflight_protocol_semantic_routes,
    should_run_semantic_route_preflight,
)
from app.agents.protocol_semantic_model_router import (
    reset_active_protocol_semantic_routes,
)
from app.workflow.jobstore import DEFAULT_LEASE_TTL
from app.workflow.recovery import run_startup_recovery
from app.workflow.runner import JobRunner, StepExecutor


def create_app(
    *,
    data_paths: DataPaths | None = None,
    executors: Mapping[str, StepExecutor] | None = None,
    run_runner: bool = True,
    worker_id: str = "v2-worker",
    poll_interval: float = 0.25,
    sse_poll_interval: float = 0.1,
    sse_heartbeat_seconds: float = 15.0,
    lease_ttl: timedelta = DEFAULT_LEASE_TTL,
    protocol_workbench_service_factory: Callable[
        [Any, DataPaths], ProtocolWorkbenchService
    ]
    | None = None,
    semantic_route_preflight: bool | None = None,
    semantic_route_endpoint_prober: EndpointProber | None = None,
) -> FastAPI:
    """构造 V2 应用；测试可注入临时数据根、执行器与循环参数。"""
    executors = dict(executors or {})

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if should_run_semantic_route_preflight(explicit=semantic_route_preflight):
            # Credential/endpoint gate before migrations or background jobs.
            # Injected probers keep tests off the real network.
            app.state.semantic_route_preflight = preflight_protocol_semantic_routes(
                endpoint_prober=semantic_route_endpoint_prober,
            )
        else:
            app.state.semantic_route_preflight = None
        paths, engine, session_factory = upgrade_or_fail(data_paths)
        if app.state.semantic_route_preflight is not None:
            paths.boundary.atomic_write_bytes(
                paths.root / "runtime" / "protocol-semantic-route-preflight.json",
                json.dumps(
                    app.state.semantic_route_preflight.as_audit_dict(),
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                ).encode("utf-8"),
            )
        recovery_report = run_startup_recovery(session_factory)
        recover_evidence_ocr_runs(
            session_factory,
            recovered_job_ids=recovery_report.recovered_jobs,
            cancelled_job_ids=recovery_report.cancelled_jobs,
            failed_final_job_ids=recovery_report.failed_final_jobs,
        )
        recover_fact_normalization_runs(session_factory)
        evidence_normalizer_runtime_config = (
            register_evidence_normalizer_runtime_config(session_factory)
        )
        app.state.data_paths = paths
        app.state.engine = engine
        app.state.session_factory = session_factory
        artifact_store = ArtifactStore(paths)
        app.state.artifact_store = artifact_store

        def project_cancelled_evidence_job(job_id: str) -> None:
            recover_evidence_ocr_runs(
                session_factory,
                cancelled_job_ids=[job_id],
            )
            cancel_revision_candidate_for_job(
                session_factory, job_id, artifact_store=artifact_store
            )
            project_fact_normalization_run_status(
                session_factory,
                job_id,
                FactNormalizationRunStatus.CANCELLED,
            )

        def project_failed_job(job_id: str) -> None:
            project_fact_normalization_run_status(
                session_factory,
                job_id,
                FactNormalizationRunStatus.FAILED,
            )

        app.state.job_service = JobService(
            session_factory,
            lease_ttl=lease_ttl,
            on_cancelled=project_cancelled_evidence_job,
        )
        app.state.protocol_workbench_service = (
            protocol_workbench_service_factory(session_factory, paths)
            if protocol_workbench_service_factory is not None
            else ProtocolWorkbenchService(session_factory, data_paths=paths)
        )
        app.state.evidence_upload_service = EvidenceUploadService(
            session_factory, paths
        )
        app.state.evidence_api_read_service = EvidenceApiReadService(
            session_factory, artifact_store
        )
        app.state.evidence_api_command_service = EvidenceApiCommandService(
            session_factory, artifact_store
        )
        app.state.evidence_correction_service = EvidenceCorrectionService(
            session_factory, artifact_store=artifact_store
        )
        app.state.evidence_risk_scan_service = EvidenceRiskScanService(
            session_factory
        )
        app.state.evidence_referenced_document_service = (
            EvidenceReferencedDocumentService(session_factory)
        )
        app.state.evidence_revision_workflow = EvidenceRevisionWorkflow(
            session_factory, artifact_store=artifact_store
        )
        app.state.evidence_activation_service = EvidenceActivationService(
            session_factory, artifact_store=artifact_store
        )
        app.state.patient_profile_service = PatientProfileService()
        app.state.eligibility_review_projection_service = EligibilityReviewProjectionService()
        app.state.fact_normalization_job_service = FactNormalizationJobService(
            session_factory, lease_ttl=lease_ttl
        )
        app.state.job_retry_services = {
            FACT_NORMALIZATION_JOB_TYPE: app.state.fact_normalization_job_service,
        }
        app.state.fact_normalization_command_service = FactNormalizationCommandService(
            session_factory,
            job_service=app.state.fact_normalization_job_service,
            registered_config=evidence_normalizer_runtime_config,
            require_page_review=True,
            page_reader_identity=lambda: app.state.page_review_runtime.main_reader_identity(),
        )
        app.state.evidence_normalizer_runtime_config = evidence_normalizer_runtime_config
        app.state.fact_correction_job_service = FactCorrectionJobService(
            session_factory, lease_ttl=lease_ttl
        )
        app.state.selective_vision_postprocess_job_service = (
            SelectiveVisionPostprocessJobService(
                session_factory, lease_ttl=lease_ttl
            )
        )
        app.state.sse_poll_interval = sse_poll_interval
        app.state.sse_heartbeat_seconds = sse_heartbeat_seconds
        evidence_ocr_gate = OmlxGateClient(owner="phase4-evidence-ocr-v2")
        app.state.page_review_runtime = PageReviewRuntime(session_factory, artifact_store)
        default_executors = {
            PAGE_REVIEW_JOB_TYPE: app.state.page_review_runtime,
            "r3_targeted_page_review": app.state.page_review_runtime,
            JUDGMENT_SEARCH_JOB_TYPE: app.state.page_review_runtime,
            PROTOCOL_DECONSTRUCTION_JOB_TYPE: create_protocol_deconstruction_executor(
                ProtocolDeconstructionExecutorConfig(
                    data_paths=paths,
                    session_factory=session_factory,
                )
            ),
            PROTOCOL_CONTROL_EXECUTION_JOB_TYPE: create_protocol_control_executor(
                ProtocolControlExecutorConfig(
                    data_paths=paths,
                    session_factory=session_factory,
                )
            ),
            EVIDENCE_PROCESSING_JOB_TYPE: create_evidence_processing_executor(
                EvidenceProcessingExecutorConfig(
                    data_paths=paths,
                    session_factory=session_factory,
                    gate=evidence_ocr_gate,
                    inference=omlx_http_inference(gate=evidence_ocr_gate),
                )
            ),
            EVIDENCE_REVISION_BUILD_JOB_TYPE: create_evidence_revision_build_executor(
                EvidenceRevisionBuildExecutorConfig(
                    session_factory=session_factory,
                    artifact_store=artifact_store,
                )
            ),
            FACT_NORMALIZATION_JOB_TYPE: create_fact_normalization_executor(
                FactNormalizationExecutorConfig(session_factory=session_factory, artifact_store=artifact_store)
            ),
            FACT_CORRECTION_JOB_TYPE: create_fact_correction_executor(
                FactCorrectionExecutorConfig(session_factory=session_factory)
            ),
            SELECTIVE_VISION_POSTPROCESS_JOB_TYPE: create_selective_vision_postprocess_executor(
                SelectiveVisionPostprocessExecutorConfig(
                    session_factory=session_factory,
                    data_paths=paths,
                    artifact_store=artifact_store,
                )
            ),
        }
        merged_executors = {**default_executors, **executors}
        app.state.protocol_control_job_service = ProtocolControlJobService(
            session_factory,
            data_paths=paths,
            lease_ttl=lease_ttl,
        )
        app.state.job_executors = merged_executors
        app.state.job_cancelled_callback = project_cancelled_evidence_job
        app.state.job_failed_callback = project_failed_job
        runner: JobRunner | None = None
        thread: threading.Thread | None = None
        if run_runner:
            runner = JobRunner(
                session_factory,
                merged_executors,
                worker_id=worker_id,
                poll_interval=poll_interval,
                lease_ttl=lease_ttl,
                on_cancelled=project_cancelled_evidence_job,
                on_failed=project_failed_job,
            )
            thread = threading.Thread(
                target=runner.serve, name="v2-job-runner", daemon=True
            )
            app.state.job_runner = runner
            thread.start()
        try:
            yield
        finally:
            reset_active_protocol_semantic_routes()
            if runner is not None:
                runner.request_stop()
            if thread is not None:
                thread.join(timeout=5.0)
            engine.dispose()

    app = FastAPI(title="入排审核 V2 持久任务 API", lifespan=lifespan)
    app.include_router(jobs_router)
    app.include_router(protocol_control_router)
    app.include_router(protocols_router)
    app.include_router(protocol_projects_router)
    app.include_router(subjects_router)
    app.include_router(evidence_router)
    app.include_router(evidence_processing_router)
    app.include_router(patient_profiles_router)
    app.include_router(fact_corrections_router)
    app.include_router(fact_normalization_router)
    app.include_router(page_review_router)
    app.include_router(judgment_search_router)
    app.include_router(eligibility_review_router)
    register_error_handlers(app)
    return app
