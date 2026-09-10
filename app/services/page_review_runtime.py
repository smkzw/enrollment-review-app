"""Application-owned R3 runtime; no external agent configuration discovery."""

import asyncio
import threading

from app.llm.page_review_harness import PageReviewConfigError, preflight_page_reader_routes, require_page_reader_routes
from app.llm.page_review_admission import PageReviewAdmission
from app.services.evidence_app_errors import EvidenceAppError, app_error_boundary
from app.services.judgment_search_job_executor import JudgmentSearchJobExecutor
from app.services.judgment_search_job_service import (
    JUDGMENT_SEARCH_JOB_TYPE,
    JudgmentSearchJobService,
    JudgmentSearchResumeNotReady,
)
from app.services.page_review_job_executor import PageReviewJobExecutor
from app.services.page_review_job_service import PageReviewJobService, PageReviewResumeNotReady, main_reader_identity, route_identity
from app.services.targeted_page_review_executor import TargetedPageReviewExecutor
from app.services.targeted_page_review_jobs import TARGETED_REVIEW_JOB_TYPE, enqueue_targeted_review


class PageReviewUnavailable(EvidenceAppError):
    status_code = 503
    code = "PAGE_REVIEW_UNAVAILABLE"
    title = "资料判读暂不可用"
    recovery = "请检查资料判读服务配置后重试，现有资料不会丢失。"


class JudgmentSearchUnavailable(EvidenceAppError):
    status_code = 503
    code = "JUDGMENT_SEARCH_UNAVAILABLE"
    title = "书面判断检索暂不可用"
    recovery = "请检查资料判读服务配置后重试，现有资料不会丢失。"


class PageReviewRuntime:
    def __init__(self, session_factory, artifact_store):
        self.session_factory = session_factory
        self.artifact_store = artifact_store
        self.jobs = PageReviewJobService(session_factory)
        self.judgment_search_jobs = JudgmentSearchJobService(session_factory)
        self._lock = threading.Lock()
        self._routes = None
        self._executor = None
        self._targeted_executor = None
        self._judgment_search_executor = None

    def main_reader_identity(self):
        # No network/model initialization while selecting an existing result.
        try:
            return main_reader_identity(self._routes or require_page_reader_routes(require_credentials=False))
        except PageReviewConfigError as exc:
            raise PageReviewUnavailable() from exc

    def _prepare(self):
        # Publish routes and executor together; failed preflight remains retryable.
        with self._lock:
            if self._executor is None:
                try:
                    routes = asyncio.run(preflight_page_reader_routes(require_page_reader_routes()))
                except Exception as exc:
                    raise PageReviewUnavailable() from exc
                admission = PageReviewAdmission(routes)
                self._targeted_executor = TargetedPageReviewExecutor(
                    self.session_factory, self.artifact_store, routes, completion=admission)
                self._executor = PageReviewJobExecutor(
                    self.session_factory, self.artifact_store, routes,
                    completion=admission,
                )
                self._judgment_search_executor = JudgmentSearchJobExecutor(
                    self.session_factory, self.artifact_store, routes,
                    completion=admission,
                )
                self._routes = routes
        return self._executor

    @app_error_boundary
    def enqueue(self, *, subject_id, review_episode_id, predecessor_job_id=None, single_length_recovery=False):
        self._prepare()
        return self.jobs.enqueue(subject_id=subject_id, review_episode_id=review_episode_id,
                                 routes=self._routes, predecessor_job_id=predecessor_job_id,
                                 single_length_recovery=single_length_recovery)

    @app_error_boundary
    def enqueue_targeted(self, **kwargs):
        self._prepare()
        return enqueue_targeted_review(self.session_factory, routes=self._routes, **kwargs)

    @app_error_boundary
    def enqueue_judgment_search(self, *, subject_id, review_episode_id, requirement_ids=None):
        self._prepare()
        return self.judgment_search_jobs.enqueue(
            subject_id=subject_id, review_episode_id=review_episode_id,
            routes=self._routes, requirement_ids=requirement_ids)

    @app_error_boundary
    def resume_judgment_search(self, *, subject_id, review_episode_id, job_id):
        if self._routes is None:
            self._prepare()
        return self.judgment_search_jobs.resume(
            job_id=job_id, subject_id=subject_id,
            review_episode_id=review_episode_id, routes=self._routes)

    @app_error_boundary
    def resume(self, *, subject_id, review_episode_id, job_id):
        # Resume is an explicit command: resolve actual service identities before changing state.
        if self._routes is None:
            self._prepare()
        else:
            try:
                current_routes = asyncio.run(preflight_page_reader_routes(require_page_reader_routes()))
            except Exception as exc:
                raise PageReviewUnavailable() from exc
            if ({lane: route_identity(route) for lane, route in current_routes.items()}
                    != {lane: route_identity(route) for lane, route in self._routes.items()}):
                raise PageReviewResumeNotReady()
        return self.jobs.resume(job_id=job_id, subject_id=subject_id,
                                review_episode_id=review_episode_id, routes=self._routes)

    def __call__(self, context):
        executor = self._prepare()
        if context.job_type == TARGETED_REVIEW_JOB_TYPE:
            return self._targeted_executor(context)
        if context.job_type == JUDGMENT_SEARCH_JOB_TYPE:
            return self._judgment_search_executor(context)
        return executor(context)
