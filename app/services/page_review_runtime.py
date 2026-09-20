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
        self._prepared_review_executors = {}

    def main_reader_identity(self):
        # No network/model initialization while selecting an existing result.
        return main_reader_identity(self.configured_review_routes())

    def configured_review_routes(self):
        """Read configured identities without preflight or executor initialization."""
        try:
            return self._routes or require_page_reader_routes(require_credentials=False)
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
                from app.services.predicate_binding_job import PredicateBindingJobExecutor
                from app.services.control_binding_job import ControlBindingJobExecutor
                from app.services.binding_qualification import BindingQualificationJobExecutor
                from app.services.judgment_content_job import JudgmentContentJobExecutor
                from app.services.proposition_evidence_job import PropositionEvidenceJobExecutor
                from app.services.observation_relation_job import ObservationRelationJobExecutor
                from app.services.frequency_evidence_job import FrequencyEvidenceJobExecutor
                self._prepared_review_executors = {
                    executor.job_type: executor(self.session_factory, self.artifact_store, routes,
                                                completion=admission)
                    for executor in (PredicateBindingJobExecutor, ControlBindingJobExecutor,
                                     BindingQualificationJobExecutor, JudgmentContentJobExecutor,
                                     PropositionEvidenceJobExecutor, ObservationRelationJobExecutor, FrequencyEvidenceJobExecutor)
                }
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
    def enqueue(self, *, subject_id, review_episode_id, predecessor_job_id=None, single_length_recovery=False,
                reading_rotations=None):
        self._prepare()
        return self.jobs.enqueue(subject_id=subject_id, review_episode_id=review_episode_id,
                                 routes=self._routes, predecessor_job_id=predecessor_job_id,
                                 single_length_recovery=single_length_recovery,
                                 reading_rotations=reading_rotations)

    @app_error_boundary
    def enqueue_targeted(self, **kwargs):
        self._prepare()
        return enqueue_targeted_review(self.session_factory, routes=self._routes, **kwargs)

    @app_error_boundary
    def enqueue_review_workflow(self, *, subject_id, review_episode_id, context_id):
        from app.services.prepared_review_intake import require_prepared_review_intent
        from app.services.prepared_review_workflow import enqueue_review_workflow
        require_prepared_review_intent(
            self.session_factory, subject_id=subject_id, review_episode_id=review_episode_id,
            context_id=context_id, kind="predicate_candidates",
        )
        self._prepare()
        return enqueue_review_workflow(
            self.session_factory, self._routes, subject_id=subject_id,
            review_episode_id=review_episode_id, context_id=context_id,
        )

    def prepared_review_routes(self):
        self._prepare()
        return self._routes

    @app_error_boundary
    def retry_review_workflow(self, **kwargs):
        from app.services.prepared_review_workflow import change_review_workflow, require_workflow_scope
        with self.session_factory() as session:
            require_workflow_scope(session, **kwargs)
        self._prepare()
        return change_review_workflow(self.session_factory, **kwargs, operation="retry", routes=self._routes)

    @app_error_boundary
    def enqueue_prepared_review(self, **kwargs):
        from app.services.prepared_review_intake import (
            enqueue_prepared_review_task, require_prepared_review_intent,
        )
        require_prepared_review_intent(self.session_factory, **kwargs)
        self._prepare()
        return enqueue_prepared_review_task(
            self.session_factory, self.artifact_store, self._routes, **kwargs,
        )

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
        if context.job_type in self._prepared_review_executors:
            return self._prepared_review_executors[context.job_type](context)
        if context.job_type == TARGETED_REVIEW_JOB_TYPE:
            return self._targeted_executor(context)
        if context.job_type == JUDGMENT_SEARCH_JOB_TYPE:
            return self._judgment_search_executor(context)
        return executor(context)
