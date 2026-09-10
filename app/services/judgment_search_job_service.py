"""研究者书面判断检索的持久任务规划（复用既有 JobService/JobRunner 模式）。

目标组按与 ``fact_expectation_gaps`` 回退循环一致的适用性规则从服务端当前
权威推导：到期阶段不晚于当前审核节点、同阶段必须同审核节点、资料要求需要
研究者书面判断（``investigator_assessment``）。显式传入 requirement_ids 时
逐条校验，不支持项（流程必做目录来源）直接拒绝；推导模式下不支持项跳过并
保留原回退缺口，不伪造检索范围。

页域与目标文本入队时经 ``prepare_judgment_search_target`` 完整冻结进载荷；
执行器与摘要步骤按同一哈希复验，漂移即拒绝。
"""

from __future__ import annotations

import hashlib

from collections.abc import Mapping

from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.judgment_search import JudgmentSearchScope
from app.domain.contracts.page_review import PageReviewLane
from app.llm.judgment_search_reader import (
    JUDGMENT_SEARCH_BATCH_PROMPT_VERSION,
    JUDGMENT_SEARCH_PROMPT_VERSION,
)
from app.llm.page_review_harness import PageReaderRoute
from app.projections.evidence_expectations import stage_rank
from app.services.evidence_app_errors import AppNotFoundError, EvidenceAppError
from app.services.fact_normalization_command_service import authority_from_active_episode
from app.services.judgment_search_source import (
    JudgmentSearchSourceError,
    prepare_judgment_search_target,
)
from app.services.job_service import CreateJobResult, JobService, StepSpec
from app.services.page_review_job_service import route_identity
from app.storage.codecs import verify_payload_sha256
from app.storage.repositories import (
    EpisodeRepository,
    get_evidence_requirement,
    list_expectation_templates,
)
from app.workflow.errors import InvalidJobDefinitionError, JobNotFoundError
from app.workflow.jobstore import JobActionOutcome, JobStore

JUDGMENT_SEARCH_JOB_TYPE = "judgment_search"
JUDGMENT_SEARCH_JOB_CONTRACT = "judgment-search-job/v1"


class JudgmentSearchResumeNotReady(EvidenceAppError):
    status_code = 409
    code = "JUDGMENT_SEARCH_RESUME_NOT_READY"
    title = "当前书面判断检索任务不能续跑"
    recovery = "资料、规则或检索配置发生变化后，请重新发起书面判断检索；已保存的历史结果仍保留。"


def judgment_search_execution_versions() -> dict[str, str]:
    return {
        "contract": JUDGMENT_SEARCH_JOB_CONTRACT,
        "batch_prompt_version": JUDGMENT_SEARCH_BATCH_PROMPT_VERSION,
        "single_prompt_version": JUDGMENT_SEARCH_PROMPT_VERSION,
    }


def judgment_search_steps(page_count: int) -> list[StepSpec]:
    if page_count < 1:
        raise InvalidJobDefinitionError("当前资料版本没有可检索页面")
    steps = []
    reads = []
    for index in range(page_count):
        for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B):
            step_id = f"read:{index}:{lane.value}"
            steps.append(StepSpec(step_id=step_id, name=f"第 {index + 1} 页书面判断检索",
                                  max_attempts=2, retryable=True))
            reads.append(step_id)
    steps.append(StepSpec(step_id="summary", name="汇总书面判断检索结果",
                          depends_on=tuple(reads)))
    return steps


def select_judgment_search_requirements(
    session: Session, authority: FactAuthority,
) -> list[str]:
    """推导当前权威下需要书面判断检索的 requirement（与缺口回退循环同规则）。"""
    episode = EpisodeRepository(session).get(authority.review_episode_id)
    templates = list_expectation_templates(
        session, authority.rule_set_id, authority.rule_set_revision
    )
    selected: list[str] = []
    for template in templates:
        if stage_rank(template.due_stage) > stage_rank(episode.stage):
            continue
        if (
            template.due_stage == episode.stage
            and template.workflow_stage_id != episode.workflow_stage_id
        ):
            continue
        required = {item.strip().casefold() for item in template.required_source_types}
        if "investigator_assessment" not in required:
            continue
        selected.append(template.requirement_id)
    return sorted(selected)


def plan_judgment_search_payload(
    session: Session, *, subject_id: str, review_episode_id: str,
    routes: Mapping[PageReviewLane, PageReaderRoute],
    requirement_ids: list[str] | None = None,
) -> dict:
    """从活动审核节点冻结检索载荷：权威、目标组、共享页域、路由与提示版本。"""
    authority = authority_from_active_episode(session, review_episode_id)
    if authority.subject_id != subject_id:
        raise InvalidJobDefinitionError("受试者与审核节点不一致")
    if requirement_ids is None:
        requirement_ids = select_judgment_search_requirements(session, authority)
        if not requirement_ids:
            raise InvalidJobDefinitionError("当前审核节点没有需要检索研究者书面判断的资料要求")
    elif not requirement_ids:
        raise InvalidJobDefinitionError("书面判断检索至少需要一条资料要求")
    elif len(set(requirement_ids)) != len(requirement_ids):
        raise InvalidJobDefinitionError("书面判断检索的资料要求存在重复")

    requirements = []
    pages: list[dict] | None = None
    for requirement_id in requirement_ids:
        try:
            scope, target_text = prepare_judgment_search_target(
                session, authority, requirement_id
            )
        except JudgmentSearchSourceError as exc:
            raise InvalidJobDefinitionError(
                f"资料要求 {requirement_id} 无法准备书面判断检索目标：{exc}"
            ) from exc
        scope_pages = [page.model_dump(mode="json") for page in scope.pages]
        if pages is None:
            pages = scope_pages
        elif pages != scope_pages:
            raise InvalidJobDefinitionError("资料要求的检索页域不一致，拒绝混合检索")
        requirements.append({
            "requirement_id": requirement_id,
            "scope": scope.model_dump(mode="json"),
            "target_text": target_text,
            "target_sha256": hashlib.sha256(
                target_text.encode("utf-8")
            ).hexdigest(),
        })
    read_step_ids = [
        f"read:{index}:{lane.value}"
        for index in range(len(pages))
        for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)
    ]
    return {
        "contract": JUDGMENT_SEARCH_JOB_CONTRACT,
        "execution_control": {
            "max_parallel_steps": sum(
                routes[lane].max_concurrency
                for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)
            ),
            "parallelizable_step_ids": read_step_ids,
        },
        "authority": authority.model_dump(mode="json"),
        "requirements": requirements,
        "pages": pages,
        "routes": {lane.value: route_identity(route) for lane, route in routes.items()},
        "batch_prompt_version": JUDGMENT_SEARCH_BATCH_PROMPT_VERSION,
        "single_prompt_version": JUDGMENT_SEARCH_PROMPT_VERSION,
    }


class JudgmentSearchJobService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory
        self.jobs = JobService(session_factory)

    def enqueue(
        self, *, subject_id: str, review_episode_id: str,
        routes: Mapping[PageReviewLane, PageReaderRoute],
        requirement_ids: list[str] | None = None,
    ) -> CreateJobResult:
        from app.domain.publication import canonical_hash

        if not {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B} <= set(routes):
            raise InvalidJobDefinitionError("缺少两个独立主读配置")
        with self.session_factory() as session, session.begin():
            payload = plan_judgment_search_payload(
                session, subject_id=subject_id, review_episode_id=review_episode_id,
                routes=routes, requirement_ids=requirement_ids,
            )
            steps = judgment_search_steps(len(payload["pages"]))
            return self.jobs.create_job_in_session(
                session,
                idempotency_key=f"{JUDGMENT_SEARCH_JOB_TYPE}:{canonical_hash(payload)}",
                job_type=JUDGMENT_SEARCH_JOB_TYPE, payload=payload, steps=steps,
            )

    def resume(self, *, job_id: str, subject_id: str, review_episode_id: str,
               routes: Mapping[PageReviewLane, PageReaderRoute]) -> JobActionOutcome:
        """受控续跑已取消检索：冻结身份一致才恢复，历史检查点保持原样。"""
        if not {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B} <= set(routes):
            raise InvalidJobDefinitionError("缺少两个独立主读配置")
        with self.session_factory() as session, session.begin():
            store = JobStore(session)
            try:
                job = store.get_job(job_id)
            except JobNotFoundError as exc:
                raise AppNotFoundError() from exc
            if job.job_type != JUDGMENT_SEARCH_JOB_TYPE:
                raise AppNotFoundError()
            frozen = verify_payload_sha256(job.payload_json, job.payload_sha256)
            authority = frozen.get("authority", {})
            if (authority.get("subject_id") != subject_id
                    or authority.get("review_episode_id") != review_episode_id):
                raise AppNotFoundError()
            if job.state != "cancelled":
                return JobActionOutcome(state=job.state, changed=False)
            try:
                plan = plan_judgment_search_payload(
                    session, subject_id=subject_id,
                    review_episode_id=review_episode_id, routes=routes,
                )
            except AppNotFoundError:
                raise
            except (InvalidJobDefinitionError, JudgmentSearchSourceError) as exc:
                raise JudgmentSearchResumeNotReady(str(exc)) from exc
            if frozen != plan:
                raise JudgmentSearchResumeNotReady()
            return store.resume_cancelled(job_id)
