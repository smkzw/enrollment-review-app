"""Existing-record browsing without model, migration or recovery startup."""
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import APIRouter, FastAPI, Request
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse

from app.api.v2.errors import register_error_handlers
from app.api.v2.evidence import router as evidence_router
from app.api.v2.evidence_processing import router as processing_router
from app.api.v2.patient_profiles import router as profiles_router
from app.api.v2.protocols import projects_router
from app.api.v2.review_history import router as history_router
from app.api.v2.subjects import router as subjects_router
from app.evidence.artifacts import ArtifactStore
from app.services.evidence_app_bootstrap import DataPaths, open_read_only
from app.services.evidence_api_read_service import EvidenceApiReadService
from app.services.evidence_upload_service import EvidenceUploadService
from app.services.patient_profile_service import PatientProfileService
from app.services.protocol_workbench_service import ProtocolWorkbenchService
from app.services.selective_vision_postprocess_job_service import SelectiveVisionPostprocessJobService


def create_browse_app(*, data_paths: DataPaths | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        paths, engine, sessions = open_read_only(data_paths)
        try:
            store = ArtifactStore(paths)
            app.state.data_paths = paths
            app.state.session_factory = sessions
            app.state.evidence_api_read_service = EvidenceApiReadService(sessions, store)
            app.state.evidence_upload_service = EvidenceUploadService(sessions, paths)
            app.state.protocol_workbench_service = ProtocolWorkbenchService(sessions, data_paths=paths)
            app.state.patient_profile_service = PatientProfileService()
            app.state.selective_vision_postprocess_job_service = SelectiveVisionPostprocessJobService(sessions)
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="入排审核 · 仅查看", lifespan=lifespan)

    @app.middleware("http")
    async def prevent_changes(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            return JSONResponse(status_code=403, content={"error": {
                "code": "BROWSE_ONLY", "title": "当前仅可查看已有资料",
                "detail": "本次打开不会上传、修改资料或开始新的审核。",
                "recovery_action": "需要补充资料或继续审核时，请正常启动系统。",
                "correlation_id": uuid4().hex,
            }})
        return await call_next(request)

    @app.get("/api/v2/application-status")
    def application_status():
        return {"mode": "browse_only", "can_modify": False}

    # Only record-reading surfaces: no live calculation, queue or model routes.
    for router in (projects_router, subjects_router, evidence_router, processing_router,
                   profiles_router, history_router):
        app.include_router(APIRouter(routes=[
            route for route in router.routes
            if isinstance(route, APIRoute) and route.methods <= {"GET", "HEAD", "OPTIONS"}
        ]))
    register_error_handlers(app)
    return app
