"""Persistent R3 job planning from an active episode, never client-supplied pages."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.page_review import PAGE_REVIEW_CONTRACT_VERSION, PageReviewLane
from app.domain.contracts.rules import RuleSet
from app.domain.contracts.page_review_context import PageReviewContext
from app.domain.publication import canonical_hash
from app.evidence.reading_view import READING_VIEW_VERSION
from app.domain.page_reconciliation import RECONCILIATION_VERSION
from app.llm.page_review_harness import PAGE_REVIEW_PROMPT_VERSION, PageReaderRoute
from app.llm.page_review_transport_options import PAGE_REVIEW_TRANSPORT_VERSION
from app.llm.page_reader_capabilities import LOCAL_PAGE_PROVIDERS, shared_reader_parallelism
from app.services.published_clause_pack import project_published_clause_pack
from app.services.evidence_app_errors import AppNotFoundError, EvidenceAppError
from app.services.fact_normalization_command_service import authority_from_active_episode
from app.services.job_service import CreateJobResult, JobService, StepSpec
from app.storage.codecs import decode_contract, verify_payload_sha256
from app.storage.models import RuleSetRecord
from app.storage.repositories import EpisodeRepository
from app.storage.ocr_repositories import PageArtifactRepository
from app.storage.evidence_locator_repositories import CompleteEvidenceProcessingRevisionRepository
from app.workflow.errors import InvalidJobDefinitionError, JobNotFoundError
from app.workflow.jobstore import JobActionOutcome, JobStore

PAGE_REVIEW_JOB_TYPE = "r3_page_review"
PAGE_REVIEW_JOB_CONTRACT = "r3-page-review-job/v12"

class PageReviewResumeNotReady(EvidenceAppError):
    status_code = 409
    code = "PAGE_REVIEW_RESUME_NOT_READY"
    title = "当前资料判读任务不能续跑"
    recovery = "资料、条款或判读配置发生变化后，请重新发起资料判读；已保存的历史结果仍保留。"


def page_review_execution_versions() -> dict[str, str]:
    return {"contract": PAGE_REVIEW_JOB_CONTRACT,
            "transport_version": PAGE_REVIEW_TRANSPORT_VERSION,
            "main_prompt_version": PAGE_REVIEW_PROMPT_VERSION,
            "reading_view_version": READING_VIEW_VERSION,
            "reconciliation_version": RECONCILIATION_VERSION,
            "page_review_contract_version": PAGE_REVIEW_CONTRACT_VERSION}


def page_review_steps(page_count: int, *, serial_lanes: bool = False) -> list[StepSpec]:
    if page_count < 1:
        raise InvalidJobDefinitionError("当前资料版本没有可判读页面")
    steps = []
    reconciliations = []
    for index in range(page_count):
        reads = tuple(f"read:{index}:{lane.value}" for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B))
        for lane, step_id in zip((PageReviewLane.MAIN_A, PageReviewLane.MAIN_B), reads, strict=True):
            preceding = ()
            if serial_lanes:
                if index:
                    preceding = (f"read:{index - 1}:{lane.value}",)
                elif lane == PageReviewLane.MAIN_B:
                    preceding = (f"read:{page_count - 1}:{PageReviewLane.MAIN_A.value}",)
            steps.append(StepSpec(step_id=step_id, name=f"第 {index + 1} 页资料判读",
                                  depends_on=preceding, max_attempts=2, retryable=True))
        reconciliation = f"reconcile:{index}"
        steps.append(StepSpec(step_id=reconciliation, name=f"第 {index + 1} 页资料核对",
                              depends_on=reads, max_attempts=2, retryable=True))
        reconciliations.append(reconciliation)
    steps.append(StepSpec(step_id="coverage", name="确认资料页处理完整性",
                          depends_on=tuple(reconciliations)))
    return steps


def route_identity(route: PageReaderRoute) -> dict:
    """Freeze public routing semantics; credentials must never enter job payloads."""
    from app.llm.mtplx_model_lifecycle import mtplx_deployment_identity

    identity = {key: getattr(route, key) for key in (
        "provider", "base_url", "model", "reasoning_effort", "max_tokens",
        "max_concurrency", "fallback_base_url",
    )}
    deployment = mtplx_deployment_identity(route.provider, route.base_url, route.model, route.reasoning_effort)
    if deployment:
        identity["deployment"] = deployment
    return identity


def main_reader_identity(routes: Mapping[PageReviewLane, PageReaderRoute]) -> str:
    """Bind downstream selection to the two independent main readers."""
    identities = {}
    for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B):
        public = route_identity(routes[lane])
        identities[lane.value] = {key: value for key, value in public.items()
                                 if key in {"provider", "base_url", "model", "reasoning_effort", "deployment"}}
    return canonical_hash(identities)


def plan_page_review_payload(session: Session, *, subject_id: str, review_episode_id: str,
                             routes: Mapping[PageReviewLane, PageReaderRoute],
                             reading_rotations: Mapping[str, int] | None = None) -> dict:
    """从审核节点当前活动状态冻结完整执行载荷；入队与续跑校验共用。"""
    authority = authority_from_active_episode(session, review_episode_id)
    if authority.subject_id != subject_id:
        raise InvalidJobDefinitionError("受试者与审核节点不一致")
    episode = EpisodeRepository(session).get(review_episode_id)
    review_context = PageReviewContext.model_validate(episode.model_dump(mode="json", include={
        "review_episode_id", "stage", "workflow_stage_id", "anchor_dates",
    }) | {"episode_revision": episode.revision})
    row = session.get(RuleSetRecord, (authority.rule_set_id, authority.rule_set_revision))
    if row is None:
        raise InvalidJobDefinitionError("审核节点引用的规则版本不存在")
    pack = project_published_clause_pack(session, decode_contract(RuleSet, row.payload_json, row.payload_sha256))
    revision = CompleteEvidenceProcessingRevisionRepository(session).get(authority.complete_processing_revision_id)
    from app.services.page_association_sources import page_association_sources
    sources = page_association_sources(session, revision)
    pages = []
    repository = PageArtifactRepository(session)
    for entry in revision.manifest:
        artifact = repository.get(entry.page_artifact_id)
        if not artifact.page_image_sha256:
            raise InvalidJobDefinitionError("资料页缺少原始图像，不能启动双模型判读")
        pages.append({"page_artifact_id": entry.page_artifact_id,
                      "source_document_version_id": entry.source_document_version_id,
                      "page_number": entry.page_number,
                      "page_image_sha256": artifact.page_image_sha256})
    rotations = dict(reading_rotations or {})
    if (set(rotations) - {page["page_artifact_id"] for page in pages}
            or any(type(angle) is not int or angle not in (90, 180, 270) for angle in rotations.values())):
        raise InvalidJobDefinitionError("阅读方向必须明确对应当前资料页，且仅支持直角旋转")
    return {**page_review_execution_versions(),
            **({"reading_rotations": rotations} if rotations else {}),
            "execution_control": {
                "serial_lanes": all(routes[lane].provider in LOCAL_PAGE_PROVIDERS
                                    for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)),
                "max_parallel_steps": shared_reader_parallelism(
                    [routes[lane] for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)]
                ),
                "parallelizable_step_ids": [f"read:{index}:{lane.value}" for index in range(len(pages))
                                            for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)],
            },
            "authority": authority.model_dump(mode="json"),
            "association_sources": {key: value.model_dump(mode="json") for key, value in sources.items()},
            "review_context": review_context.model_dump(mode="json"),
            "clause_pack": pack.model_dump(mode="json"), "pages": pages,
            "routes": {lane.value: route_identity(route) for lane, route in routes.items()}}


class PageReviewJobService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory
        self.jobs = JobService(session_factory)

    def enqueue(self, *, subject_id: str, review_episode_id: str,
                routes: Mapping[PageReviewLane, PageReaderRoute],
                predecessor_job_id: str | None = None, single_length_recovery: bool = False,
                reading_rotations: Mapping[str, int] | None = None) -> CreateJobResult:
        if single_length_recovery and predecessor_job_id is None:
            raise InvalidJobDefinitionError("额外补读必须引用前次失败任务")
        if not {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B} <= set(routes):
            raise InvalidJobDefinitionError("缺少两个独立主读配置")
        with self.session_factory() as session, session.begin():
            if predecessor_job_id is not None and reading_rotations is None:
                try:
                    predecessor = JobStore(session).get_job(predecessor_job_id)
                except JobNotFoundError as exc:
                    raise AppNotFoundError() from exc
                if predecessor.job_type != PAGE_REVIEW_JOB_TYPE:
                    raise AppNotFoundError()
                frozen = verify_payload_sha256(predecessor.payload_json, predecessor.payload_sha256)
                owner = frozen.get("authority", {})
                if (owner.get("subject_id") != subject_id
                        or owner.get("review_episode_id") != review_episode_id):
                    raise AppNotFoundError()
                reading_rotations = frozen.get("reading_rotations")
            payload = plan_page_review_payload(session, subject_id=subject_id,
                                               review_episode_id=review_episode_id, routes=routes,
                                               reading_rotations=reading_rotations)
            if predecessor_job_id is not None:
                from app.services.page_review_recovery import plan_page_reread
                payload["recovery"] = plan_page_reread(session, predecessor_job_id, payload,
                                                       single_length_recovery=single_length_recovery)
            steps = page_review_steps(len(payload["pages"]),
                                      serial_lanes=payload["execution_control"]["serial_lanes"])
            return self.jobs.create_job_in_session(
                session, idempotency_key=f"{PAGE_REVIEW_JOB_TYPE}:{canonical_hash(payload)}",
                job_type=PAGE_REVIEW_JOB_TYPE, payload=payload, steps=steps,
            )

    def resume(self, *, job_id: str, subject_id: str, review_episode_id: str,
               routes: Mapping[PageReviewLane, PageReaderRoute]) -> JobActionOutcome:
        """受控续跑已取消任务：冻结身份一致才恢复，历史检查点保持原样。"""
        if not {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B} <= set(routes):
            raise InvalidJobDefinitionError("缺少两个独立主读配置")
        with self.session_factory() as session, session.begin():
            store = JobStore(session)
            try:
                job = store.get_job(job_id)
            except JobNotFoundError as exc:
                raise AppNotFoundError() from exc
            if job.job_type != PAGE_REVIEW_JOB_TYPE:
                raise AppNotFoundError()
            frozen = verify_payload_sha256(job.payload_json, job.payload_sha256)
            authority = frozen.get("authority", {})
            if (authority.get("subject_id") != subject_id
                    or authority.get("review_episode_id") != review_episode_id):
                raise AppNotFoundError()
            if job.state != "cancelled":
                # 重复点击或任务已进入其他状态：无副作用返回当前状态。
                return JobActionOutcome(state=job.state, changed=False)
            try:
                plan = plan_page_review_payload(session, subject_id=subject_id,
                                                review_episode_id=review_episode_id, routes=routes,
                                                reading_rotations=frozen.get("reading_rotations"))
            except AppNotFoundError:
                raise
            except (EvidenceAppError, InvalidJobDefinitionError, ValidationError) as exc:
                raise PageReviewResumeNotReady(str(exc)) from exc
            comparable = {key: value for key, value in frozen.items() if key != "recovery"}
            # Legacy jobs were serial; adding scheduling does not change reading semantics.
            if "execution_control" not in comparable and "execution_control" in plan:
                comparable["execution_control"] = plan["execution_control"]
            if comparable != plan:
                raise PageReviewResumeNotReady()
            return store.resume_cancelled(job_id)
