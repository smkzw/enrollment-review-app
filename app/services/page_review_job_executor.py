"""R3 persistent step executor: model calls outside transactions, atomic receipts."""

from __future__ import annotations

import asyncio
import json
import logging
from time import monotonic
from collections.abc import Mapping
from dataclasses import replace

from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.clause_pack import ClausePack
from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.page_review_context import PageReviewContext
from app.domain.contracts.page_review import PageCoverageEntry, PageReviewLane, SubjectPageCoverage
from app.domain.publication import canonical_hash
from app.evidence.artifacts import ArtifactStore
from app.llm.independent_vlm import PageVisionInput
from app.llm.page_review_harness import (
    Completion, PageReaderRoute, PageReviewInput, PageReviewHarnessError, direct_completion, read_page,
)
from app.services.page_review_execution import reconcile_completed_reads
from app.services.page_review_job_service import page_review_execution_versions, route_identity, main_reader_identity
from app.services.page_request_receipt import store_page_request
from app.services.page_review_cancellation import run_cancellable
from app.storage.fact_authority import FactAuthorityValidator
from app.storage.page_review_repository import PageReviewRepository
from app.workflow.errors import StepFailure
from app.workflow.jobstore import JobStore
from app.workflow.runner import PreparedStepResult, StepContext


class PageReviewJobExecutor:
    def __init__(self, session_factory: sessionmaker[Session], artifact_store: ArtifactStore,
                 routes: Mapping[PageReviewLane, PageReaderRoute], *,
                 completion: Completion = direct_completion, review_focus=None) -> None:
        self.session_factory = session_factory
        self.artifact_store = artifact_store
        self.routes = routes
        self.completion = completion
        self.review_focus = review_focus

    def __call__(self, context: StepContext) -> PreparedStepResult:
        payload = context.job_payload
        expected_versions = page_review_execution_versions()
        if any(payload.get(key) != value for key, value in expected_versions.items()):
            raise StepFailure(
                retryable=False, error_code="R3_EXECUTION_VERSION_CHANGED",
                detail="资料处理方式已更新，请保留现有结果并新建处理任务",
            )
        authority = FactAuthority.model_validate(payload["authority"])
        pack = ClausePack.model_validate(payload["clause_pack"])
        if payload["routes"] != {lane.value: route_identity(route) for lane, route in self.routes.items()}:
            raise StepFailure(retryable=False, error_code="R3_ROUTE_CHANGED", detail="判读配置已变化，请重新建立处理任务")
        with self.session_factory() as session:
            FactAuthorityValidator(session).validate(authority)

        recovery = payload.get("recovery", {})
        reusable = recovery.get("reusable_receipts", {}).get(context.step_id)
        if reusable is not None:
            def apply_reused(session):
                FactAuthorityValidator(session).validate(authority)
            return PreparedStepResult(checkpoint=reusable, apply=apply_reused)

        def checkpoint(session, step_id):
            found = JobStore(session).get_last_checkpoint(context.job_id, step_id)
            if found is None:
                raise StepFailure(retryable=False, error_code="R3_CHECKPOINT_MISSING")
            return found[1]

        if context.step_id == "coverage":
            with self.session_factory() as session:
                entries = [PageCoverageEntry.model_validate(checkpoint(session, f"reconcile:{i}")["entry"])
                           for i in range(len(payload["pages"]))]
            fields = dict(execution_versions=expected_versions,
                          main_reader_identity_sha256=main_reader_identity(self.routes),
                          subject_id=authority.subject_id, review_episode_id=authority.review_episode_id,
                          evidence_snapshot_id=authority.evidence_snapshot_v2_id,
                          evidence_processing_revision_id=authority.complete_processing_revision_id,
                          clause_pack_sha256=pack.clause_pack_sha256,
                          expected_page_artifact_ids=[p["page_artifact_id"] for p in payload["pages"]],
                          entries=[entry.model_dump(mode="json") for entry in entries])
            if recovery:
                fields["predecessor_coverage_id"] = recovery["predecessor_coverage_id"]
            coverage = SubjectPageCoverage(coverage_id="subject-page-coverage:" + canonical_hash(fields)[:32], **fields)

            def apply(session):
                FactAuthorityValidator(session).validate(authority)
                PageReviewRepository(session).save_coverage(coverage)
            return PreparedStepResult(checkpoint={"coverage_id": coverage.coverage_id}, apply=apply)

        parts = context.step_id.split(":")
        index = 0 if self.review_focus is not None else int(parts[1])
        page = payload["pages"][index]
        image = self.artifact_store.read_by_sha("page_image", page["page_image_sha256"])
        page_input = PageReviewInput(**page, review_context=PageReviewContext.model_validate(payload["review_context"]),
                                    page=PageVisionInput(source_ref=page["page_artifact_id"],
                                                                page_ordinal=page["page_number"], image_bytes=image))
        attempts = []

        async def recorded_completion(route, messages, max_tokens):
            request_sha256 = store_page_request(self.artifact_store, route, messages, max_tokens)
            started = monotonic()
            try:
                result = await self.completion(route, messages, max_tokens)
            except Exception as exc:
                receipt = {
                    "job_id": context.job_id, "step_id": context.step_id,
                    "step_attempt": context.attempt, "request_index": len(attempts),
                    "lane": route.lane.value, "provider": route.provider,
                    "model": route.model, "max_tokens": max_tokens,
                    "request_sha256": request_sha256,
                    "error_type": type(exc).__name__,
                    "status_code": getattr(exc, "status_code", None),
                    "failure_kind": getattr(exc, "failure_kind", None),
                    "elapsed_seconds": round(monotonic() - started, 3),
                }
                artifact = self.artifact_store.put(
                    "raw_response", json.dumps(receipt, sort_keys=True).encode("utf-8")
                )
                attempts.append({**receipt, "error_receipt_sha256": artifact.sha256})
                logging.getLogger(__name__).info(
                    "Page request failed job=%s step=%s receipt=%s",
                    context.job_id, context.step_id, artifact.sha256,
                )
                raise
            artifact = self.artifact_store.put("raw_response", result.text.encode("utf-8"))
            attempts.append({"lane": route.lane.value,
                             "request_sha256": request_sha256,
                             "response_sha256": artifact.sha256,
                             "finish_reason": result.finish_reason,
                             "response_model": result.response_model,
                             "response_id": result.response_id,
                             "usage": result.usage,
                             "output_lengths": result.output_lengths,
                             "max_tokens": max_tokens,
                             "elapsed_seconds": round(monotonic() - started, 3)})
            return result

        if parts[0] == "read":
            lane = PageReviewLane(parts[2])
            route = self.routes[lane]
            override = recovery.get("length_override", {})
            extra_read = override.get("step_id") == context.step_id
            if extra_read:
                if (self.review_focus is not None or override != {
                    "step_id": context.step_id, "max_tokens": 48000,
                    "budget_scope": "combined_generation", "retry_length": False,
                } or context.max_attempts != 1):
                    raise StepFailure(retryable=False, error_code="R3_LENGTH_RECOVERY_INVALID")
                route = replace(route, max_tokens=48000, fallback_base_url="")
            try:
                record = asyncio.run(run_cancellable(
                    lambda: read_page(route, page_input, pack, completion=recorded_completion,
                                     review_focus=self.review_focus, retry_length=not extra_read),
                    self.session_factory, context.job_id))
            except PageReviewHarnessError as exc:
                if exc.failure_kind == "endpoint" and context.attempt < context.max_attempts:
                    raise StepFailure(retryable=True, error_code="R3_PAGE_READ_UNAVAILABLE",
                                      detail="原件暂未完成判读，将重试") from exc

                def apply_failure(session):
                    FactAuthorityValidator(session).validate(authority)

                return PreparedStepResult(
                    checkpoint={"lane_failure": {"lane": lane.value, "failure_kind": exc.failure_kind},
                                "response_attempts": attempts},
                    apply=apply_failure,
                )

            def apply(session):
                FactAuthorityValidator(session).validate(authority)
                if self.review_focus is None:
                    PageReviewRepository(session).save_review(record)
            return PreparedStepResult(checkpoint={"page_review_id": record.page_review_id,
                                                  **({"auxiliary_review": record.model_dump(mode="json")}
                                                     if self.review_focus is not None else {}),
                                                  "response_attempts": attempts}, apply=apply)

        if parts[0] != "reconcile":
            raise StepFailure(retryable=False, error_code="R3_STEP_UNKNOWN")
        with self.session_factory() as session:
            repository = PageReviewRepository(session)
            receipts = [checkpoint(session, f"read:{index}:{lane.value}")
                        for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)]
            failures = [receipt["lane_failure"] for receipt in receipts if "lane_failure" in receipt]
            if failures:
                entry = PageCoverageEntry(
                    page_artifact_id=page["page_artifact_id"],
                    source_document_version_id=page["source_document_version_id"],
                    page_number=page["page_number"], disposition="failed_pending_reread",
                    lane_failures=failures,
                )

                def apply_failure(session):
                    FactAuthorityValidator(session).validate(authority)

                return PreparedStepResult(checkpoint={"entry": entry.model_dump(mode="json")},
                                          apply=apply_failure)
            records = [repository.get_review(receipt["page_review_id"]) for receipt in receipts]
        from app.domain.page_source_association import PageAssociationSource
        raw_source = payload["association_sources"].get(page["page_artifact_id"])
        source = PageAssociationSource.model_validate(raw_source) if raw_source is not None else None
        result = asyncio.run(run_cancellable(
            lambda: reconcile_completed_reads(page_input, pack, records, association_source=source),
            self.session_factory, context.job_id))

        def apply(session):
            FactAuthorityValidator(session).validate(authority)
            repository = PageReviewRepository(session)
            for record in result.records:
                repository.save_review(record)
            if result.reconciliation:
                repository.save_reconciliation(result.reconciliation)
        return PreparedStepResult(checkpoint={"entry": result.coverage_entry.model_dump(mode="json"),
                                              "response_attempts": attempts}, apply=apply)
