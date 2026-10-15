"""判断检索持久步骤执行器：模型调用在事务外，原子提交回执引用与摘要。

复用页判读执行器的结构约定（``PageReviewJobExecutor``）：

- 步骤前核对合同/提示版本/路由身份，漂移即不可重试失败；
- ``read:{index}:{lane}`` 用批次读器对整页全部目标恰好一次完成调用，
  回执逐条经 ``save_judgment_search_receipt`` 绑定核验后落内容寻址工件，
  检查点只保存 (requirement_id, storage_ref)；
- 传输类失败在尝试预算内可重试；其余失败落页级失败标记，摘要按覆盖不完整
  处理，绝不折叠成未发现；
- ``summary`` 步骤从当前数据库重新准备每条要求的 scope/target 并与冻结哈希
  比对，装载回执再次绑定核验后装配覆盖摘要，追加写仓储。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import UTC, datetime
from time import monotonic

from collections.abc import Mapping

from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.judgment_search import (
    JudgmentSearchCoverageSummary,
    JudgmentSearchScope,
)
from app.domain.contracts.page_review import PageReviewLane
from app.evidence.artifacts import ArtifactStore
from app.llm.independent_vlm import PageVisionInput
from app.llm.judgment_search_reader import (
    JudgmentSearchReaderError,
    JudgmentSearchReaderReceipt,
    read_judgment_search_page_batch,
)
from app.llm.page_review_harness import (
    Completion,
    PageReaderRoute,
    PageReviewInput,
    direct_completion,
)
from app.services.judgment_search_artifacts import (
    load_judgment_search_receipt,
    save_judgment_search_receipt,
)
from app.services.judgment_search_job_service import judgment_search_execution_versions
from app.services.judgment_search_results import (
    JudgmentSearchResultsError,
    assemble_judgment_search_coverage,
)
from app.services.judgment_search_source import prepare_judgment_search_target
from app.services.page_review_cancellation import run_cancellable
from app.services.page_review_job_service import route_identity
from app.storage.fact_authority import FactAuthorityValidator
from app.storage.judgment_search_repository import JudgmentSearchSummaryRepository
from app.workflow.errors import StepFailure
from app.workflow.jobstore import JobStore
from app.workflow.runner import PreparedStepResult, StepContext


class JudgmentSearchJobExecutor:
    def __init__(self, session_factory: sessionmaker[Session], artifact_store: ArtifactStore,
                 routes: Mapping[PageReviewLane, PageReaderRoute], *,
                 completion: Completion = direct_completion) -> None:
        self.session_factory = session_factory
        self.artifact_store = artifact_store
        self.routes = routes
        self.completion = completion

    def __call__(self, context: StepContext) -> PreparedStepResult:
        payload = context.job_payload
        expected = judgment_search_execution_versions()
        if (payload.get("contract") != expected["contract"]
                or payload.get("batch_prompt_version") != expected["batch_prompt_version"]
                or payload.get("single_prompt_version") != expected["single_prompt_version"]):
            raise StepFailure(
                retryable=False, error_code="JUDGMENT_SEARCH_VERSION_CHANGED",
                detail="书面判断检索方式已更新，请保留现有结果并新建检索任务",
            )
        if payload["routes"] != {lane.value: route_identity(route)
                                 for lane, route in self.routes.items()}:
            raise StepFailure(retryable=False, error_code="JUDGMENT_SEARCH_ROUTE_CHANGED",
                              detail="检索配置已变化，请重新建立检索任务")
        authority = FactAuthority.model_validate(payload["authority"])
        with self.session_factory() as session:
            FactAuthorityValidator(session).validate(authority)

        if context.step_id == "summary":
            return self._summary_step(context, payload, authority)
        parts = context.step_id.split(":")
        if parts[0] != "read" or len(parts) != 3:
            raise StepFailure(retryable=False, error_code="JUDGMENT_SEARCH_STEP_UNKNOWN")
        return self._read_step(context, payload, authority, parts)

    # ------------------------------------------------------------------ read

    def _read_step(self, context, payload, authority, parts) -> PreparedStepResult:
        index = int(parts[1])
        lane = PageReviewLane(parts[2])
        page = payload["pages"][index]
        requirements = payload["requirements"]
        targets = [
            (JudgmentSearchScope.model_validate(item["scope"]), item["target_text"])
            for item in requirements
        ]
        image = self.artifact_store.read_by_sha("page_image", page["page_image_sha256"])
        page_input = PageReviewInput(
            page_artifact_id=page["page_artifact_id"],
            source_document_version_id=page["source_document_version_id"],
            page_number=page["page_number"],
            page_image_sha256=page["page_image_sha256"],
            page=PageVisionInput(source_ref=page["page_artifact_id"],
                                 page_ordinal=page["page_number"], image_bytes=image),
        )
        route = self.routes[lane]
        attempts: list[dict] = []

        async def recorded_completion(route, messages, max_tokens):
            started = monotonic()
            try:
                result = await self.completion(route, messages, max_tokens)
            except Exception as exc:
                receipt = {
                    "job_id": context.job_id, "step_id": context.step_id,
                    "step_attempt": context.attempt, "lane": lane.value,
                    "provider": route.provider, "model": route.model,
                    "max_tokens": max_tokens,
                    "error_type": type(exc).__name__,
                    "failure_kind": getattr(exc, "failure_kind", None),
                    "elapsed_seconds": round(monotonic() - started, 3),
                }
                artifact = self.artifact_store.put(
                    "raw_response", json.dumps(receipt, sort_keys=True).encode("utf-8"))
                attempts.append({**receipt, "error_receipt_sha256": artifact.sha256})
                raise
            artifact = self.artifact_store.put("raw_response", result.text.encode("utf-8"))
            attempts.append({
                "lane": lane.value, "provider": route.provider, "model": route.model,
                "request_model": route.model, "response_model": result.response_model,
                "response_sha256": artifact.sha256, "finish_reason": result.finish_reason,
                "max_tokens": max_tokens, "usage": result.usage,
                "elapsed_seconds": round(monotonic() - started, 3),
            })
            return result

        try:
            receipts = asyncio.run(run_cancellable(
                lambda: read_judgment_search_page_batch(
                    page_input=page_input, route=route, targets=targets,
                    completion=recorded_completion,
                ),
                self.session_factory, context.job_id))
        except JudgmentSearchReaderError as exc:
            if (exc.failure_kind in ("transport", "length")
                    and context.attempt < context.max_attempts):
                raise StepFailure(
                    retryable=True, error_code="JUDGMENT_SEARCH_READ_UNAVAILABLE",
                    detail="该页书面判断检索暂未完成，将重试") from exc

            def apply_failure(session):
                FactAuthorityValidator(session).validate(authority)

            return PreparedStepResult(
                checkpoint={"page_failure": {"lane": lane.value,
                                             "failure_kind": exc.failure_kind},
                            "response_attempts": attempts},
                apply=apply_failure,
            )

        refs = []
        for item, receipt in zip(requirements, receipts):
            stored = save_judgment_search_receipt(
                self.artifact_store,
                JudgmentSearchScope.model_validate(item["scope"]),
                item["target_text"], receipt)
            refs.append({"requirement_id": item["requirement_id"],
                         "storage_ref": stored.storage_ref})

        def apply(session):
            FactAuthorityValidator(session).validate(authority)

        return PreparedStepResult(checkpoint={"receipt_refs": refs,
                                              "response_attempts": attempts},
                                  apply=apply)

    # --------------------------------------------------------------- summary

    def _summary_step(self, context, payload, authority) -> PreparedStepResult:
        read_ids = [f"read:{index}:{lane.value}"
                    for index in range(len(payload["pages"]))
                    for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)]
        summaries: list[JudgmentSearchCoverageSummary] = []
        with self.session_factory() as session:
            store = JobStore(session)
            read_checkpoints = []
            for step_id in read_ids:
                found = store.get_last_checkpoint(context.job_id, step_id)
                if found is None:
                    raise StepFailure(retryable=False,
                                      error_code="JUDGMENT_SEARCH_CHECKPOINT_MISSING")
                read_checkpoints.append(found[1])
            for item in payload["requirements"]:
                requirement_id = item["requirement_id"]
                current_scope, current_target = prepare_judgment_search_target(
                    session, authority, requirement_id)
                if (current_scope.scope_sha256
                        != JudgmentSearchScope.model_validate(item["scope"]).scope_sha256
                        or _target_sha(current_target) != item["target_sha256"]):
                    raise StepFailure(
                        retryable=False, error_code="JUDGMENT_SEARCH_SCOPE_CHANGED",
                        detail="资料或规则已变化，现有检索结果与当前内容不一致；"
                               "请新建检索任务，历史结果保留",
                    )
                receipts: list[JudgmentSearchReaderReceipt] = []
                for step_checkpoint in read_checkpoints:
                    refs = step_checkpoint.get("receipt_refs")
                    if refs is None:  # 页级失败读道：该页该读道无回执，覆盖保持不完整
                        continue
                    for ref in refs:
                        if ref["requirement_id"] == requirement_id:
                            receipts.append(load_judgment_search_receipt(
                                self.artifact_store, current_scope, current_target,
                                ref["storage_ref"]))
                try:
                    summaries.append(assemble_judgment_search_coverage(
                        current_scope, current_target, receipts))
                except JudgmentSearchResultsError as exc:
                    raise StepFailure(
                        retryable=False, error_code="JUDGMENT_SEARCH_ASSEMBLY_FAILED",
                        detail=f"书面判断检索结果与当前来源核对不一致：{exc}",
                    ) from exc
        created_at = datetime.now(UTC)

        def apply(session):
            FactAuthorityValidator(session).validate(authority)
            repository = JudgmentSearchSummaryRepository(session)
            for summary in summaries:
                repository.save_summary(summary, authority=authority,
                                        job_id=context.job_id, created_at=created_at)

        return PreparedStepResult(
            checkpoint={"requirement_statuses": [
                {"requirement_id": s.requirement_id, "status": s.status.value}
                for s in summaries]},
            apply=apply,
        )


def _target_sha(target_text: str) -> str:
    return hashlib.sha256(target_text.strip().encode("utf-8")).hexdigest()


__all__ = ["JudgmentSearchJobExecutor"]
