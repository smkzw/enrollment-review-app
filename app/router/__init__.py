"""Router aggregation — all sub-routers for the enrollment review app."""

from app.router.health import router as health_router
from app.router.auth import router as auth_router
from app.router.projects import router as projects_router
from app.router.subjects import router as subjects_router
from app.router.pipeline import router as pipeline_router
from app.router.reports import router as reports_router

__all__ = [
    "health_router",
    "auth_router",
    "projects_router",
    "subjects_router",
    "pipeline_router",
    "reports_router",
]
