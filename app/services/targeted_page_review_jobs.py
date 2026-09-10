"""Two-round auxiliary review jobs on the existing durable runner."""

from dataclasses import replace

from app.domain.contracts.facts import FactAuthority
from app.domain.targeted_page_review import explicit_conflict_fields
from app.domain.targeted_handwriting_review import handwriting_needs_review
from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.page_review_focus import PageReviewFocus
from app.llm.page_review_harness import PAGE_REVIEW_PROMPT_VERSION, TARGETED_REVIEW_PROMPT_VERSION
from app.services.job_service import JobService, StepSpec
from app.services.page_review_job_service import PAGE_REVIEW_JOB_TYPE, route_identity
from app.storage.codecs import verify_payload_sha256
from app.storage.idempotency import IdempotencyConflict
from app.storage.fact_authority import FactAuthorityValidator
from app.storage.page_review_repository import PageReviewRepository
from app.workflow.jobstore import JobStore
from app.services.evidence_app_errors import EvidenceAppError


class TargetedReviewNotReady(EvidenceAppError):
    status_code = 409
    code = "TARGETED_REVIEW_NOT_READY"
    title = "当前资料不具备复核条件"
    recovery = "请查看原资料判读结果，确认需要核对的具体内容。"

TARGETED_REVIEW_JOB_TYPE = "r3_targeted_page_review"
TARGETED_REVIEW_VERSION = "targeted-page-review-job/v2"
MAIN_LANES = (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)


def targeted_routes(routes):
    return {lane: replace(routes[lane], reasoning_effort="high") for lane in MAIN_LANES}


def enqueue_targeted_review(session_factory, *, original_job_id, page_index,
                            subject_id, review_episode_id, routes):
    routes = targeted_routes(routes)
    with session_factory() as session, session.begin():
        store = JobStore(session)
        original = store.get_job(original_job_id)
        if original.job_type != PAGE_REVIEW_JOB_TYPE or original.state != "completed" or original.cancel_requested:
            raise TargetedReviewNotReady("原资料判读尚未完成，不能开始内容复核")
        old = verify_payload_sha256(original.payload_json, original.payload_sha256)
        authority = FactAuthority.model_validate(old["authority"])
        if authority.subject_id != subject_id or authority.review_episode_id != review_episode_id:
            raise TargetedReviewNotReady("原判读与当前受试者或审核节点不一致")
        FactAuthorityValidator(session).validate(authority)
        if isinstance(page_index, bool) or not isinstance(page_index, int) or not 0 <= page_index < len(old["pages"]):
            raise TargetedReviewNotReady("复核页面不存在")
        checkpoint = store.get_last_checkpoint(original_job_id, f"reconcile:{page_index}")
        reconciliation_id = checkpoint[1]["entry"].get("reconciliation_id") if checkpoint else None
        if not reconciliation_id:
            raise TargetedReviewNotReady("该页没有可复核的内容核对记录")
        repository = PageReviewRepository(session)
        reconciliation = repository.get_reconciliation(reconciliation_id)
        page = old["pages"][page_index]
        if (reconciliation.page_artifact_id != page["page_artifact_id"]
                or reconciliation.clause_pack_sha256 != old["clause_pack"]["clause_pack_sha256"]):
            raise TargetedReviewNotReady("核对记录与原件不一致")
        records = [repository.get_review(identity) for identity in reconciliation.page_review_ids]
        records = [record for record in records if record.lane in MAIN_LANES]
        if any(record.page_image_sha256 != page["page_image_sha256"] for record in records):
            raise TargetedReviewNotReady("复核原件图像不一致")
        targets = explicit_conflict_fields(records)
        handwriting = handwriting_needs_review(records)
        if not targets and not handwriting:
            raise TargetedReviewNotReady("该页没有明确的数值、日期或标记分歧；文字表述与对应关系需另行核对")
        focus = PageReviewFocus(original_reconciliation_id=reconciliation_id,
                               page_image_sha256=page["page_image_sha256"],
                               review_episode_id=review_episode_id, round_number=1, targets=targets,
                               handwriting_review=handwriting)
        payload = {"version": TARGETED_REVIEW_VERSION, "base_prompt_version": PAGE_REVIEW_PROMPT_VERSION,
                   "targeted_prompt_version": TARGETED_REVIEW_PROMPT_VERSION,
                   "original_job_id": original_job_id, "authority": old["authority"],
                   "page": page, "review_context": old["review_context"],
                   "clause_pack": old["clause_pack"], "focus": focus.model_dump(mode="json"),
                   "routes": {lane.value: route_identity(route) for lane, route in routes.items()}}
        steps = []
        for number in (1, 2):
            reads = tuple(f"read:{number}:{lane.value}" for lane in MAIN_LANES)
            for step_id in reads:
                steps.append(StepSpec(step_id=step_id, name=f"第{number}轮原件复核",
                                      depends_on=("compare:1",) if number == 2 else (),
                                      retryable=True, max_attempts=2))
            steps.append(StepSpec(step_id=f"compare:{number}", name=f"整理第{number}轮复核结果",
                                  depends_on=reads, retryable=True, max_attempts=2))
        # Stable case identity prevents a repeated click/config change resetting the round budget.
        try:
            return JobService(session_factory).create_job_in_session(
                session, idempotency_key=f"{TARGETED_REVIEW_JOB_TYPE}:{reconciliation_id}",
                job_type=TARGETED_REVIEW_JOB_TYPE, payload=payload, steps=steps)
        except IdempotencyConflict as exc:
            raise TargetedReviewNotReady(
                "本页已有不同版本的复核任务。请查看已有结果；不会重新计数或自动覆盖。"
            ) from exc
