"""R3 逐页双主读执行：互盲读页与页覆盖处置。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Mapping, Sequence

from sqlalchemy.orm import Session

from app.domain.contracts.clause_pack import ClausePack
from app.domain.contracts.page_review import (
    PAGE_REVIEW_CONTRACT_VERSION,
    PageCoverageEntry,
    PageDisposition,
    PageLaneFailure,
    PageReconciliation,
    PageReviewLane,
    PageReviewRecord,
    SubjectPageCoverage,
)
from app.domain.page_reconciliation import reconcile_page_reviews
from app.domain.publication import canonical_hash
from app.llm.page_review_harness import (
    Completion,
    PageReaderRoute,
    PageReviewHarnessError,
    PageReviewInput,
    direct_completion,
    read_page,
)
from app.storage.page_review_repository import PageReviewRepository


@dataclass(frozen=True)
class PageExecutionResult:
    page_input: PageReviewInput
    records: tuple[PageReviewRecord, ...]
    reconciliation: PageReconciliation | None
    coverage_entry: PageCoverageEntry


def _failure(lane: PageReviewLane, exc: BaseException) -> PageLaneFailure:
    kind = (
        exc.failure_kind
        if isinstance(exc, PageReviewHarnessError)
        else "unexpected"
    )
    return PageLaneFailure(lane=lane, failure_kind=kind)


async def review_page(
    routes: Mapping[PageReviewLane, PageReaderRoute],
    page_input: PageReviewInput,
    clause_pack: ClausePack,
    *,
    completion: Completion = direct_completion,
) -> PageExecutionResult:
    """Run independent main reads; the optional reader never substitutes a main lane."""
    main_lanes = (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)
    main_results = await asyncio.gather(
        *(
            read_page(routes[lane], page_input, clause_pack, completion=completion)
            for lane in main_lanes
        ),
        return_exceptions=True,
    )
    main_failures = [
        _failure(lane, result)
        for lane, result in zip(main_lanes, main_results, strict=True)
        if isinstance(result, BaseException)
    ]
    records = tuple(
        result
        for result in main_results
        if isinstance(result, PageReviewRecord)
    )
    if main_failures:
        return PageExecutionResult(
            page_input=page_input,
            records=records,
            reconciliation=None,
            coverage_entry=PageCoverageEntry(
                page_artifact_id=page_input.page_artifact_id,
                source_document_version_id=page_input.source_document_version_id,
                page_number=page_input.page_number,
                disposition=PageDisposition.FAILED_PENDING_REREAD,
                lane_failures=main_failures,
            ),
        )

    return await reconcile_completed_reads(page_input, clause_pack, records)


async def reconcile_completed_reads(
    page_input: PageReviewInput,
    clause_pack: ClausePack,
    records: Sequence[PageReviewRecord],
    *,
    association_source=None,
) -> PageExecutionResult:
    """Finish persisted main reads without calling either main model again."""
    if {record.lane for record in records} != {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B} or len(records) != 2:
        raise ValueError("页面核对必须提供两个不同主读结果")
    if any(record.contract_version != PAGE_REVIEW_CONTRACT_VERSION
           or record.page_artifact_id != page_input.page_artifact_id
           or record.source_document_version_id != page_input.source_document_version_id
           or record.page_number != page_input.page_number
           or record.page_image_sha256 != page_input.page_image_sha256
           or record.clause_pack_id != clause_pack.clause_pack_id
           or record.clause_pack_sha256 != clause_pack.clause_pack_sha256 for record in records):
        raise ValueError("主读结果与当前页面或条款包不一致")
    records = tuple(records)
    if all(not record.has_eligibility_value for record in records):
        return PageExecutionResult(
            page_input=page_input,
            records=records,
            reconciliation=None,
            coverage_entry=PageCoverageEntry(
                page_artifact_id=page_input.page_artifact_id,
                source_document_version_id=page_input.source_document_version_id,
                page_number=page_input.page_number,
                disposition=PageDisposition.DISCARDED_NO_ELIGIBILITY_VALUE,
                discard_reason=(
                    "两个主读道均未发现与当前入排条款有关的内容。"
                ),
            ),
        )

    modes = {item.clause_id: item.determination_mode for item in clause_pack.clauses}
    reconciliation = reconcile_page_reviews(
        records,
        determination_modes=modes,
        association_source=association_source,
    )
    return PageExecutionResult(
        page_input=page_input,
        records=tuple(records),
        reconciliation=reconciliation,
        coverage_entry=PageCoverageEntry(
            page_artifact_id=page_input.page_artifact_id,
            source_document_version_id=page_input.source_document_version_id,
            page_number=page_input.page_number,
            disposition=PageDisposition.ACCEPTED,
            reconciliation_id=reconciliation.reconciliation_id,
        ),
    )


async def review_pages(
    routes: Mapping[PageReviewLane, PageReaderRoute],
    pages: Sequence[PageReviewInput],
    clause_pack: ClausePack,
    *,
    completion: Completion = direct_completion,
) -> list[PageExecutionResult]:
    """Review pages concurrently while honoring each product route's own cap."""
    semaphores = {
        lane: asyncio.Semaphore(route.max_concurrency)
        for lane, route in routes.items()
    }

    async def limited(
        route: PageReaderRoute,
        messages: list[dict[str, object]],
        max_tokens: int,
    ):
        async with semaphores[route.lane]:
            return await completion(route, messages, max_tokens)

    return list(
        await asyncio.gather(
            *(
                review_page(routes, page, clause_pack, completion=limited)
                for page in pages
            )
        )
    )


def build_subject_page_coverage(
    *,
    subject_id: str,
    review_episode_id: str,
    evidence_snapshot_id: str,
    evidence_processing_revision_id: str,
    clause_pack: ClausePack,
    results: Sequence[PageExecutionResult],
) -> SubjectPageCoverage:
    entries = [item.coverage_entry for item in results]
    coverage_fields = {
        "subject_id": subject_id,
        "review_episode_id": review_episode_id,
        "evidence_snapshot_id": evidence_snapshot_id,
        "evidence_processing_revision_id": evidence_processing_revision_id,
        "clause_pack_sha256": clause_pack.clause_pack_sha256,
        "expected_page_artifact_ids": [
            item.page_input.page_artifact_id for item in results
        ],
    }
    identity = {
        **coverage_fields,
        "entries": [item.model_dump(mode="json") for item in entries],
    }
    return SubjectPageCoverage(
        coverage_id="subject-page-coverage:" + canonical_hash(identity)[:32],
        **coverage_fields,
        entries=entries,
    )


def persist_page_review_results(
    session: Session,
    *,
    results: Sequence[PageExecutionResult],
    coverage: SubjectPageCoverage,
) -> SubjectPageCoverage:
    """Persist one completed batch inside the caller-owned transaction."""
    repository = PageReviewRepository(session)
    for result in results:
        for record in result.records:
            repository.save_review(record)
        if result.reconciliation is not None:
            repository.save_reconciliation(result.reconciliation)
    return repository.save_coverage(coverage)


__all__ = [
    "PageExecutionResult",
    "build_subject_page_coverage",
    "persist_page_review_results",
    "review_page",
    "reconcile_completed_reads",
    "review_pages",
]
