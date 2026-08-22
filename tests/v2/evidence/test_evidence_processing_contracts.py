"""Phase 4 OCR 持久化与基础证据处理修订合同冻结测试（Slice 4.3）。"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.contracts.enums import (
    OcrAttemptStatus,
    OcrFailureCategory,
    OcrRunStatus,
    PageArtifactStatus,
    ProcessingRevisionStatus,
)
from app.domain.contracts.evidence_processing import (
    EvidenceProcessingRevision,
    EvidenceProcessingRevisionPage,
    OCRAttempt,
    OCRRun,
    PageWorkLease,
)
from app.domain.publication import evidence_processing_manifest_hash

_ts = datetime(2026, 8, 19, 8, 0, 0, tzinfo=UTC)
_SHA = "a" * 64


def _page_entry(**overrides: Any) -> EvidenceProcessingRevisionPage:
    values: dict[str, Any] = {
        "entry_id": "e1",
        "position": 1,
        "source_document_version_id": "doc-1",
        "page_number": 1,
        "original_frame": None,
        "page_artifact_id": "pa-1",
        "ocr_page_id": "op-1",
        "status": PageArtifactStatus.SUCCEEDED,
        "failure_reason": None,
    }
    values.update(overrides)
    return EvidenceProcessingRevisionPage(**values)


def _revision(
    entries: list[EvidenceProcessingRevisionPage] | None = None,
    **overrides: Any,
) -> EvidenceProcessingRevision:
    pages = entries if entries is not None else [_page_entry()]
    manifest_hash = evidence_processing_manifest_hash(
        entries=[
            (
                e.source_document_version_id,
                e.page_number,
                e.original_frame,
                e.page_artifact_id,
                e.ocr_page_id,
                e.status.value,
            )
            for e in pages
        ]
    )
    values: dict[str, Any] = {
        "evidence_processing_revision_id": "rev-1",
        "evidence_snapshot_id": "snap-1",
        "project_id": "p",
        "subject_id": "s",
        "review_episode_id": "e",
        "manifest": pages,
        "manifest_sha256": manifest_hash,
        "status": ProcessingRevisionStatus.READY,
        "is_activatable": False,
        "created_at": _ts,
        "created_by": "tester",
    }
    values.update(overrides)
    return EvidenceProcessingRevision(**values)


def _run(**overrides: Any) -> OCRRun:
    values: dict[str, Any] = {
        "ocr_run_id": "run-1",
        "source_document_version_id": "doc-1",
        "ocr_profile_id": "prof-1",
        "ocr_profile_sha256": _SHA,
        "job_id": None,
        "status": OcrRunStatus.RUNNING,
        "page_total": 2,
        "page_succeeded": 0,
        "page_failed": 0,
        "started_at": _ts,
        "completed_at": None,
        "created_at": _ts,
    }
    values.update(overrides)
    return OCRRun(**values)


def _attempt(**overrides: Any) -> OCRAttempt:
    values: dict[str, Any] = {
        "attempt_id": "at-1",
        "ocr_run_id": "run-1",
        "ocr_page_id": "op-1",
        "cache_key": _SHA,
        "attempt_number": 1,
        "status": OcrAttemptStatus.SUCCEEDED,
        "failure_category": None,
        "rejection_reason": None,
        "started_at": _ts,
        "completed_at": _ts,
        "raw_request_artifact_id": None,
        "raw_response_artifact_id": None,
        "work_lease_owner": "w1",
        "work_lease_generation": 1,
        "omlx_lease_owner": None,
        "retry_of_attempt_id": None,
        "created_at": _ts,
    }
    values.update(overrides)
    return OCRAttempt(**values)


# ---------------------------------------------------------------------------
# EvidenceProcessingRevisionPage
# ---------------------------------------------------------------------------


def test_page_entry_succeeded_rejects_failure_reason() -> None:
    with pytest.raises(ValidationError, match="失败原因"):
        _page_entry(failure_reason="x")


def test_page_entry_degraded_requires_reason() -> None:
    with pytest.raises(ValidationError, match="降级原因"):
        _page_entry(status=PageArtifactStatus.DEGRADED)


def test_page_entry_failed_requires_reason_and_no_ocr() -> None:
    with pytest.raises(ValidationError, match="失败原因"):
        _page_entry(status=PageArtifactStatus.FAILED)
    with pytest.raises(ValidationError, match="失败页"):
        _page_entry(
            status=PageArtifactStatus.FAILED,
            failure_reason="decode failed",
            ocr_page_id="op-1",
        )


# ---------------------------------------------------------------------------
# EvidenceProcessingRevision（基础修订，不可激活）
# ---------------------------------------------------------------------------


def test_revision_readonly_default() -> None:
    rev = _revision()
    assert rev.status == ProcessingRevisionStatus.READY
    assert rev.is_activatable is False


def test_revision_rejects_non_ready_status() -> None:
    with pytest.raises(ValidationError, match="ready"):
        _revision(status="active")


def test_revision_rejects_activatable() -> None:
    with pytest.raises(ValidationError, match="False"):
        _revision(is_activatable=True)


def test_revision_requires_utc_created_at() -> None:
    with pytest.raises(ValidationError, match="UTC"):
        _revision(created_at=_ts.replace(tzinfo=None))


def test_revision_rejects_unsorted_or_duplicate_manifest() -> None:
    # 页码乱序（doc-1 页 2 在页 1 前）
    unsorted = [
        _page_entry(entry_id="e2", position=1, page_number=2),
        _page_entry(entry_id="e1", position=2, page_number=1),
    ]
    with pytest.raises(ValidationError, match="升序"):
        _revision(entries=unsorted)
    # 同一页重复
    dup = [
        _page_entry(entry_id="e1", position=1, page_number=1),
        _page_entry(entry_id="e2", position=2, page_number=1),
    ]
    with pytest.raises(ValidationError, match="重复同一页"):
        _revision(entries=dup)


def test_revision_rejects_duplicate_position() -> None:
    dup_pos = [
        _page_entry(entry_id="e1", position=1, page_number=1),
        _page_entry(entry_id="e2", position=1, page_number=2),
    ]
    with pytest.raises(ValidationError, match="位置不能重复"):
        _revision(entries=dup_pos)


def test_revision_rejects_non_contiguous_positions() -> None:
    pages = [
        _page_entry(entry_id="e1", position=1, page_number=1),
        _page_entry(entry_id="e2", position=3, page_number=2),
    ]
    with pytest.raises(ValidationError, match="连续递增"):
        _revision(entries=pages)


def test_revision_rejects_manifest_hash_mismatch() -> None:
    wrong = evidence_processing_manifest_hash(
        entries=[("doc-1", 9, None, "pa-x", "op-x", PageArtifactStatus.SUCCEEDED.value)]
    )
    with pytest.raises(ValidationError, match="清单哈希"):
        _revision(manifest_sha256=wrong)


def test_revision_manifest_hash_changes_on_reorder() -> None:
    h1 = evidence_processing_manifest_hash(
        entries=[
            ("doc-1", 1, None, "pa-1", "op-1", PageArtifactStatus.SUCCEEDED.value),
            ("doc-1", 2, None, "pa-2", "op-2", PageArtifactStatus.SUCCEEDED.value),
        ]
    )
    h2 = evidence_processing_manifest_hash(
        entries=[
            ("doc-1", 2, None, "pa-2", "op-2", PageArtifactStatus.SUCCEEDED.value),
            ("doc-1", 1, None, "pa-1", "op-1", PageArtifactStatus.SUCCEEDED.value),
        ]
    )
    assert h1 != h2


def test_revision_allows_empty_manifest() -> None:
    _revision(entries=[])


# ---------------------------------------------------------------------------
# OCRRun
# ---------------------------------------------------------------------------


def test_run_counts_cannot_exceed_total() -> None:
    with pytest.raises(ValidationError, match="不能超过总页数"):
        _run(page_total=1, page_succeeded=2)


def test_run_running_rejects_completed_at() -> None:
    with pytest.raises(ValidationError, match="完成时间"):
        _run(completed_at=_ts)


def test_run_succeeded_requires_completion_and_no_failed() -> None:
    with pytest.raises(ValidationError, match="完成时间"):
        _run(status=OcrRunStatus.SUCCEEDED, page_succeeded=2, page_failed=0)
    with pytest.raises(ValidationError, match="不能有失败页"):
        _run(
            status=OcrRunStatus.SUCCEEDED,
            page_succeeded=1,
            page_failed=1,
            completed_at=_ts,
        )


def test_run_failed_zero_page_rejected() -> None:
    with pytest.raises(ValidationError, match="零页文件"):
        _run(status=OcrRunStatus.FAILED, page_total=0, completed_at=_ts)


def test_run_timestamps_ordered() -> None:
    with pytest.raises(ValidationError, match="早于"):
        _run(
            status=OcrRunStatus.SUCCEEDED,
            page_succeeded=2,
            completed_at=_ts,
            started_at=datetime(2026, 8, 19, 9, 0, 0, tzinfo=UTC),
        )


def test_run_requires_utc() -> None:
    with pytest.raises(ValidationError, match="UTC"):
        _run(started_at=_ts.replace(tzinfo=None))


# ---------------------------------------------------------------------------
# OCRAttempt
# ---------------------------------------------------------------------------


def test_attempt_rejects_bad_cache_key() -> None:
    with pytest.raises(ValidationError, match="pattern"):
        _attempt(cache_key="not-a-hash")


def test_attempt_finished_requires_completed_at() -> None:
    with pytest.raises(ValidationError, match="完成时间"):
        _attempt(completed_at=None)


def test_attempt_failed_requires_failure_category() -> None:
    with pytest.raises(ValidationError, match="失败类别"):
        _attempt(status=OcrAttemptStatus.FAILED, failure_category=None)


def test_attempt_rejected_late_requires_reason() -> None:
    with pytest.raises(ValidationError, match="拒绝原因"):
        _attempt(status=OcrAttemptStatus.REJECTED_LATE, rejection_reason=None)


def test_attempt_cancelled_requires_reason() -> None:
    with pytest.raises(ValidationError, match="原因"):
        _attempt(status=OcrAttemptStatus.CANCELLED, rejection_reason=None)


def test_attempt_failure_category_only_on_failed() -> None:
    with pytest.raises(ValidationError, match="只有失败"):
        _attempt(
            status=OcrAttemptStatus.SUCCEEDED,
            failure_category=OcrFailureCategory.NETWORK,
        )


def test_attempt_rejection_reason_only_on_late_or_cancelled() -> None:
    with pytest.raises(ValidationError, match="只有晚到或取消"):
        _attempt(status=OcrAttemptStatus.FAILED, rejection_reason="x", failure_category=OcrFailureCategory.NETWORK)


def test_attempt_timestamps_ordered_and_utc() -> None:
    with pytest.raises(ValidationError, match="早于"):
        _attempt(
            started_at=datetime(2026, 8, 19, 9, 0, 0, tzinfo=UTC),
            completed_at=_ts,
        )
    with pytest.raises(ValidationError, match="UTC"):
        _attempt(started_at=_ts.replace(tzinfo=None))


# ---------------------------------------------------------------------------
# PageWorkLease
# ---------------------------------------------------------------------------


def test_lease_requires_content_addressed_work_item_id() -> None:
    with pytest.raises(ValidationError, match="pattern"):
        PageWorkLease(work_item_id="not-a-key", lease_generation=0, updated_at=_ts)


def test_lease_owner_requires_generation() -> None:
    with pytest.raises(ValidationError, match="代次"):
        PageWorkLease(
            work_item_id=_SHA,
            lease_owner="w1",
            lease_generation=0,
            lease_expires_at=_ts,
            updated_at=_ts,
        )


def test_lease_released_keeps_generation() -> None:
    lease = PageWorkLease(
        work_item_id=_SHA,
        lease_owner=None,
        lease_generation=3,
        lease_expires_at=None,
        updated_at=_ts,
    )
    assert lease.lease_generation == 3


def test_lease_requires_utc() -> None:
    with pytest.raises(ValidationError, match="UTC"):
        PageWorkLease(
            work_item_id=_SHA,
            lease_owner=None,
            lease_generation=0,
            updated_at=_ts.replace(tzinfo=None),
        )
