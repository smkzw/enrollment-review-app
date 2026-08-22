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
from app.api.v2.protocols import (
    projects_router as protocol_projects_router,
)
from app.api.v2.protocols import (
    router as protocols_router,
)
from app.api.v2.subjects import router as subjects_router
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
from app.services.job_service import JobService
from app.services.omlx_gate import OmlxGateClient, omlx_http_inference
from app.services.protocol_deconstruction_executor import (
    ProtocolDeconstructionExecutorConfig,
    create_protocol_deconstruction_executor,
)
from app.services.protocol_workbench_service import (
    PROTOCOL_DECONSTRUCTION_JOB_TYPE,
    ProtocolWorkbenchService,
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
) -> FastAPI:
    """构造 V2 应用；测试可注入临时数据根、执行器与循环参数。"""
    executors = dict(executors or {})

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        paths, engine, session_factory = upgrade_or_fail(data_paths)
        recovery_report = run_startup_recovery(session_factory)
        recover_evidence_ocr_runs(
            session_factory,
            recovered_job_ids=recovery_report.recovered_jobs,
            cancelled_job_ids=recovery_report.cancelled_jobs,
            failed_final_job_ids=recovery_report.failed_final_jobs,
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
        app.state.sse_poll_interval = sse_poll_interval
        app.state.sse_heartbeat_seconds = sse_heartbeat_seconds
        evidence_ocr_gate = OmlxGateClient(owner="phase4-evidence-ocr-v2")
        default_executors = {
            PROTOCOL_DECONSTRUCTION_JOB_TYPE: create_protocol_deconstruction_executor(
                ProtocolDeconstructionExecutorConfig(
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
        }
        merged_executors = {**default_executors, **executors}
        app.state.job_executors = merged_executors
        app.state.job_cancelled_callback = project_cancelled_evidence_job
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
            )
            thread = threading.Thread(
                target=runner.serve, name="v2-job-runner", daemon=True
            )
            app.state.job_runner = runner
            thread.start()
        try:
            yield
        finally:
            if runner is not None:
                runner.request_stop()
            if thread is not None:
                thread.join(timeout=5.0)
            engine.dispose()

    app = FastAPI(title="入排审核 V2 持久任务 API", lifespan=lifespan)
    app.include_router(jobs_router)
    app.include_router(protocols_router)
    app.include_router(protocol_projects_router)
    app.include_router(subjects_router)
    app.include_router(evidence_router)
    app.include_router(evidence_processing_router)
    register_error_handlers(app)
    return app
