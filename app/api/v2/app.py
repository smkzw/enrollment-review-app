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
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, Callable, Mapping

from fastapi import FastAPI

from app.api.v2.errors import register_error_handlers
from app.api.v2.jobs import router as jobs_router
from app.api.v2.protocols import (
    projects_router as protocol_projects_router,
    router as protocols_router,
)
from app.services.job_service import JobService, StepSpec
from app.services.protocol_deconstruction_executor import (
    ProtocolDeconstructionExecutorConfig,
    create_protocol_deconstruction_executor,
)
from app.services.protocol_workbench_service import (
    PROTOCOL_DECONSTRUCTION_JOB_TYPE,
    ProtocolWorkbenchService,
)
from app.storage.config import DataPaths
from app.storage.db import build_session_factory
from app.storage.migrate import upgrade_or_fail
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
        run_startup_recovery(session_factory)
        app.state.data_paths = paths
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.job_service = JobService(session_factory, lease_ttl=lease_ttl)
        app.state.protocol_workbench_service = (
            protocol_workbench_service_factory(session_factory, paths)
            if protocol_workbench_service_factory is not None
            else ProtocolWorkbenchService(session_factory, data_paths=paths)
        )
        app.state.sse_poll_interval = sse_poll_interval
        app.state.sse_heartbeat_seconds = sse_heartbeat_seconds
        default_executors = {
            PROTOCOL_DECONSTRUCTION_JOB_TYPE: create_protocol_deconstruction_executor(
                ProtocolDeconstructionExecutorConfig(
                    data_paths=paths,
                    session_factory=session_factory,
                )
            ),
        }
        merged_executors = {**default_executors, **executors}
        runner: JobRunner | None = None
        thread: threading.Thread | None = None
        if run_runner:
            runner = JobRunner(
                session_factory,
                merged_executors,
                worker_id=worker_id,
                poll_interval=poll_interval,
                lease_ttl=lease_ttl,
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
    register_error_handlers(app)
    return app
