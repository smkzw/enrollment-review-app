"""Rebuild frozen search results from product receipts, without model calls."""
from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.review_context_v2 import (
    FrozenJudgmentSearchResult,
    FrozenSearchCheckpoint,
)
from app.evidence.artifacts import ArtifactStore
from app.services.judgment_search_artifacts import load_judgment_search_receipt
from app.services.judgment_search_job_service import JUDGMENT_SEARCH_JOB_TYPE
from app.services.judgment_search_results import assemble_judgment_search_coverage
from app.services.judgment_search_source import prepare_judgment_search_target
from app.storage.codecs import verify_payload_sha256
from app.storage.judgment_search_repository import JudgmentSearchSummaryRepository
from app.storage.models import JobCheckpointRecord, JobRecord, JobStepRecord
from app.storage.repositories import InvalidReferenceError


def freeze_judgment_search_result(
    session: Session, artifact_store: ArtifactStore, *, authority: FactAuthority,
    summary_id: str,
) -> FrozenJudgmentSearchResult:
    """Select checkpoint identities once; all subsequent checks use those identities."""
    entry = JudgmentSearchSummaryRepository(session).get_entry(summary_id, authority=authority)
    job = session.get(JobRecord, entry.job_id)
    if job is None:
        raise InvalidReferenceError("书面判断检索的原任务不存在")
    payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
    checkpoints = []
    for index in range(len(payload.get("pages", []))):
        for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B):
            step_id = f"read:{index}:{lane.value}"
            row = session.scalar(
                select(JobCheckpointRecord).where(
                    JobCheckpointRecord.job_id == job.job_id,
                    JobCheckpointRecord.step_id == step_id,
                ).order_by(
                    JobCheckpointRecord.created_at.desc(),
                    JobCheckpointRecord.checkpoint_id.desc(),
                ).limit(1)
            )
            if row is None:
                raise InvalidReferenceError("书面判断检索缺少逐页执行记录")
            checkpoints.append(FrozenSearchCheckpoint(
                checkpoint_id=row.checkpoint_id, step_id=step_id,
                payload_sha256=row.payload_sha256,
            ))
    return _rebuild(
        session, artifact_store, authority=authority, summary_id=summary_id,
        job_payload_sha256=job.payload_sha256, checkpoints=tuple(checkpoints),
    )


def verify_frozen_judgment_search_result(
    session: Session, artifact_store: ArtifactStore, *, authority: FactAuthority,
    frozen: FrozenJudgmentSearchResult,
) -> None:
    """Publication replays exact references, never the latest search or checkpoint."""
    rebuilt = _rebuild(
        session, artifact_store, authority=authority, summary_id=frozen.summary_id,
        job_payload_sha256=frozen.job_payload_sha256, checkpoints=frozen.checkpoints,
    )
    if rebuilt != frozen:
        raise InvalidReferenceError("冻结的书面判断检索结果与原执行记录不一致")


def _rebuild(
    session: Session, artifact_store: ArtifactStore, *, authority: FactAuthority,
    summary_id: str, job_payload_sha256: str,
    checkpoints: tuple[FrozenSearchCheckpoint, ...],
) -> FrozenJudgmentSearchResult:
    entry = JudgmentSearchSummaryRepository(session).get_entry(summary_id, authority=authority)
    job = session.get(JobRecord, entry.job_id)
    if (
        job is None or job.job_type != JUDGMENT_SEARCH_JOB_TYPE
        or job.state != "completed" or job.cancel_requested
        or job.payload_sha256 != job_payload_sha256
    ):
        raise InvalidReferenceError("书面判断检索尚未完成，或原任务身份不一致")
    payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
    if FactAuthority.model_validate(payload["authority"]) != authority:
        raise InvalidReferenceError("书面判断检索来自其他审核资料版本")
    scope, target = prepare_judgment_search_target(session, authority, entry.summary.requirement_id)
    targets = [item for item in payload["requirements"]
               if item["requirement_id"] == scope.requirement_id]
    if len(targets) != 1 or targets[0] != {
        "requirement_id": scope.requirement_id,
        "scope": scope.model_dump(mode="json"), "target_text": target,
        "target_sha256": hashlib.sha256(target.encode("utf-8")).hexdigest(),
    } or payload["pages"] != [page.model_dump(mode="json") for page in scope.pages]:
        raise InvalidReferenceError("检索要求或逐页来源与正式审核输入不一致")
    expected_steps = [
        (f"read:{index}:{lane.value}", page, lane)
        for index, page in enumerate(scope.pages)
        for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)
    ]
    if [item.step_id for item in checkpoints] != [item[0] for item in expected_steps]:
        raise InvalidReferenceError("冻结检索未覆盖原任务全部双读步骤")
    receipts = []
    receipt_refs = []
    for pinned, (step_id, page, lane) in zip(checkpoints, expected_steps, strict=True):
        step = session.get(JobStepRecord, (job.job_id, step_id))
        row = session.get(JobCheckpointRecord, pinned.checkpoint_id)
        if (
            step is None or step.state != "completed" or row is None
            or (row.job_id, row.step_id, row.payload_sha256)
            != (job.job_id, step_id, pinned.payload_sha256)
        ):
            raise InvalidReferenceError("逐页检索的原执行记录未完成或引用不一致")
        content = verify_payload_sha256(row.payload_json, row.payload_sha256)
        refs = content.get("receipt_refs")
        if refs is None:
            failure = content.get("page_failure")
            if not isinstance(failure, dict) or failure.get("lane") != lane.value:
                raise InvalidReferenceError("逐页检索既无回执也无明确失败记录")
            # Failed reads remain missing coverage in the existing assembler.
            continue
        selected = [item for item in refs if item.get("requirement_id") == scope.requirement_id]
        if len(selected) != 1:
            raise InvalidReferenceError("逐页检索缺少本条要求的唯一回执")
        ref = selected[0]["storage_ref"]
        receipt = load_judgment_search_receipt(
            artifact_store, scope=scope, target_text=target, storage_ref=ref,
        )
        route = payload["routes"][lane.value]
        if receipt.page != page or receipt.requested.lane != lane or any(
            getattr(receipt.requested, key) != route[key]
            for key in ("provider", "model", "reasoning_effort", "max_tokens")
        ):
            raise InvalidReferenceError("逐页回执的模型身份或原始页面不一致")
        receipts.append(receipt)
        receipt_refs.append(ref)
    summary = assemble_judgment_search_coverage(scope=scope, target_text=target, receipts=receipts)
    if summary != entry.summary:
        raise InvalidReferenceError("原始逐页回执不能重建已保存的检索摘要")
    return FrozenJudgmentSearchResult(
        summary_id=entry.summary_id, job_id=entry.job_id,
        job_payload_sha256=job_payload_sha256, checkpoints=checkpoints,
        payload_sha256=entry.payload_sha256, summary=summary,
        scope=scope, target_text=target, receipt_refs=tuple(receipt_refs),
    )
