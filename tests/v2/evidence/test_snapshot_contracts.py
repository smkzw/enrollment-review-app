"""Phase 4 证据快照与资料版本合同冻结测试（Slice 4.1）。

用确定性断言证明：来源对象内容寻址、逻辑资料版本显式替代、元数据修订链、
补充/完整快照上传语义、集合哈希、活动指针一致性，以及 Phase 4 合同不与
Phase 3 投影合同在包根互相遮蔽。
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.contracts import (
    EvidenceSnapshotMember,
    EvidenceSnapshotStatusEvent,
    SourceBlob,
    SourceDocumentMetadataRevision,
    evidence_ingestion,
)
from app.domain.contracts import evidence as phase3_evidence
from app.domain.contracts.enums import (
    ReviewStage,
    SnapshotMemberOrigin,
    SnapshotStatus,
    StudyPhase,
    UploadMode,
)
from app.domain.publication import evidence_snapshot_collection_hash

_ts = datetime(2026, 8, 19, 8, 0, 0, tzinfo=UTC)
_SHA = "a" * 64


def _blob(**overrides) -> SourceBlob:
    values: dict[str, Any] = {
        "source_blob_id": _SHA,
        "sha256": _SHA,
        "byte_size": 4096,
        "media_type": "application/pdf",
        "storage_ref": "blobs/evidence/" + _SHA,
        "created_at": _ts,
    }
    values.update(overrides)
    return SourceBlob(**values)


def _version(**overrides) -> evidence_ingestion.SourceDocumentVersion:
    values: dict[str, Any] = {
        "source_document_version_id": "doc-v1",
        "logical_document_id": "logical-lab-1",
        "source_blob_sha256": _SHA,
        "file_name": "lab.pdf",
        "media_type": "application/pdf",
        "page_count": 3,
        "project_id": "proj-1",
        "subject_id": "subj-1",
        "review_episode_id": "ep-1",
        "version_number": 1,
        "supersedes_version_id": None,
        "created_at": _ts,
        "created_by": "monitor-1",
    }
    values.update(overrides)
    return evidence_ingestion.SourceDocumentVersion(**values)


def _metadata(**overrides) -> SourceDocumentMetadataRevision:
    values: dict[str, Any] = {
        "metadata_revision_id": "meta-1",
        "source_document_version_id": "doc-v1",
        "document_type": "lab_report",
        "source_party": "site",
        "reason": "自动分类建议",
        "is_auto_suggestion": True,
        "supersedes_metadata_revision_id": None,
        "created_at": _ts,
        "created_by": "system",
    }
    values.update(overrides)
    return SourceDocumentMetadataRevision(**values)


def _member(**overrides) -> EvidenceSnapshotMember:
    values: dict[str, Any] = {
        "member_id": "mem-1",
        "snapshot_id": "snap-1",
        "logical_document_id": "logical-lab-1",
        "source_document_version_id": "doc-v1",
        "origin": SnapshotMemberOrigin.ADDED,
    }
    values.update(overrides)
    return EvidenceSnapshotMember(**values)


def _snapshot(**overrides) -> evidence_ingestion.EvidenceSnapshot:
    members = [_member()]
    values: dict[str, Any] = {
        "evidence_snapshot_id": "snap-1",
        "project_id": "proj-1",
        "subject_id": "subj-1",
        "review_episode_id": "ep-1",
        "upload_mode": UploadMode.FULL,
        "prior_snapshot_id": None,
        "comparison_snapshot_id": None,
        "members": members,
        "collection_sha256": evidence_snapshot_collection_hash(
            members=[
                (m.logical_document_id, m.source_document_version_id) for m in members
            ]
        ),
        "status": SnapshotStatus.STAGED,
        "created_at": _ts,
        "created_by": "monitor-1",
    }
    values.update(overrides)
    return evidence_ingestion.EvidenceSnapshot(**values)


# ---------------------------------------------------------------------------
# SourceBlob 内容寻址与可移植引用
# ---------------------------------------------------------------------------


def test_source_blob_identity_equals_sha256() -> None:
    blob = _blob()
    assert blob.source_blob_id == blob.sha256


def test_source_blob_rejects_mismatched_identity() -> None:
    with pytest.raises(ValidationError, match="内容身份必须等于其 SHA-256"):
        _blob(source_blob_id="b" * 64)


def test_source_blob_rejects_absolute_or_traversal_storage_ref() -> None:
    with pytest.raises(ValidationError, match="可移植内容寻址引用"):
        _blob(storage_ref="/Users/x/raw/lab.pdf")
    with pytest.raises(ValidationError, match="可移植内容寻址引用"):
        _blob(storage_ref="blobs/../raw/lab.pdf")


def test_source_blob_requires_utc() -> None:
    with pytest.raises(ValidationError, match="UTC"):
        _blob(created_at=datetime.fromisoformat("2026-08-19T08:00:00"))


def test_snapshot_status_event_requires_utc_timestamp_and_sequence() -> None:
    event = EvidenceSnapshotStatusEvent(
        snapshot_id="snap-1",
        seq=1,
        from_status=SnapshotStatus.STAGED,
        to_status=SnapshotStatus.PROCESSING,
        event="worker_start",
        actor="worker-1",
        reason="start",
        created_at=_ts,
    )
    assert event.seq == 1
    with pytest.raises(ValidationError, match="UTC"):
        EvidenceSnapshotStatusEvent(
            snapshot_id="snap-1",
            seq=1,
            from_status=SnapshotStatus.STAGED,
            to_status=SnapshotStatus.PROCESSING,
            event="worker_start",
            actor="worker-1",
            reason="start",
            created_at=_ts.replace(tzinfo=None),
        )
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        EvidenceSnapshotStatusEvent(
            snapshot_id="snap-1",
            seq=0,
            from_status=SnapshotStatus.STAGED,
            to_status=SnapshotStatus.PROCESSING,
            event="worker_start",
            actor="worker-1",
            reason="start",
            created_at=_ts,
        )


# ---------------------------------------------------------------------------
# SourceDocumentVersion 作用域与显式替代
# ---------------------------------------------------------------------------


def test_version_requires_full_scope() -> None:
    _version()
    with pytest.raises(ValidationError):
        _version(review_episode_id="")
    with pytest.raises(ValidationError):
        _version(subject_id="")


def test_version_supersedes_requires_min_version_2() -> None:
    with pytest.raises(ValidationError, match="版本号必须大于等于 2"):
        _version(supersedes_version_id="doc-v0")
    ok = _version(supersedes_version_id="doc-v0", version_number=2)
    assert ok.supersedes_version_id == "doc-v0"
    assert ok.version_number == 2
    with pytest.raises(ValidationError, match="非首版本必须显式替代"):
        _version(version_number=2, supersedes_version_id=None)


# ---------------------------------------------------------------------------
# SourceDocumentMetadataRevision 不可变修订链
# ---------------------------------------------------------------------------


def test_metadata_initial_revision_has_no_predecessor() -> None:
    _metadata()
    with pytest.raises(ValidationError, match="初始元数据修订不能引用前序修订"):
        _metadata(supersedes_metadata_revision_id="meta-0")


def test_metadata_followup_revision_must_reference_predecessor() -> None:
    _metadata(revision=2, supersedes_metadata_revision_id="meta-1")
    with pytest.raises(ValidationError, match="非初始元数据修订必须引用其前序修订"):
        _metadata(revision=2)


def test_metadata_auto_suggestion_is_explicit() -> None:
    suggested = _metadata()
    assert suggested.is_auto_suggestion is True
    confirmed = _metadata(
        metadata_revision_id="meta-2",
        revision=2,
        is_auto_suggestion=False,
        reason="医学监查确认",
        supersedes_metadata_revision_id="meta-1",
    )
    assert confirmed.is_auto_suggestion is False


# ---------------------------------------------------------------------------
# EvidenceSnapshot 上传语义与成员约束
# ---------------------------------------------------------------------------


def test_incremental_snapshot_requires_single_predecessor() -> None:
    with pytest.raises(ValidationError, match="必须引用唯一的有效前序快照"):
        _snapshot(upload_mode=UploadMode.INCREMENTAL)


def test_full_snapshot_forbids_predecessor() -> None:
    with pytest.raises(ValidationError, match="不能静默继承前序快照"):
        _snapshot(prior_snapshot_id="snap-0")


def test_incremental_comparison_must_equal_predecessor() -> None:
    base = _snapshot()
    prior = base.evidence_snapshot_id
    _snapshot(
        upload_mode=UploadMode.INCREMENTAL,
        prior_snapshot_id=prior,
        comparison_snapshot_id=prior,
    )
    with pytest.raises(ValidationError, match="差异基线必须等于其前序快照"):
        _snapshot(
            upload_mode=UploadMode.INCREMENTAL,
            prior_snapshot_id=prior,
            comparison_snapshot_id="other-snap",
        )


def test_member_must_belong_to_snapshot() -> None:
    with pytest.raises(ValidationError, match="必须属于当前快照"):
        _snapshot(members=[_member(snapshot_id="other-snap")])


def test_snapshot_forbids_duplicate_logical_document() -> None:
    with pytest.raises(ValidationError, match="只能有一个活动版本"):
        _snapshot(
            members=[
                _member(),
                _member(member_id="mem-2", source_document_version_id="doc-v2"),
            ]
        )


def test_full_snapshot_members_must_be_added() -> None:
    with pytest.raises(ValidationError, match="不得继承前序"):
        _snapshot(
            members=[_member(origin=SnapshotMemberOrigin.INHERITED)],
            collection_sha256=evidence_snapshot_collection_hash(
                members=[("logical-lab-1", "doc-v1")]
            ),
        )


def test_snapshot_rejects_stale_collection_hash() -> None:
    with pytest.raises(ValidationError, match="集合哈希与活动成员集合不一致"):
        _snapshot(collection_sha256="b" * 64)


def test_ready_snapshot_cannot_be_empty() -> None:
    with pytest.raises(ValidationError, match="不能为空集合"):
        _snapshot(
            members=[],
            status=SnapshotStatus.READY,
            collection_sha256=evidence_snapshot_collection_hash(members=[]),
        )


# ---------------------------------------------------------------------------
# 集合哈希：确定性、顺序无关、对成员身份敏感
# ---------------------------------------------------------------------------


def test_collection_hash_is_order_independent() -> None:
    pairs = [
        ("logical-a", "doc-a2"),
        ("logical-b", "doc-b1"),
        ("logical-c", "doc-c3"),
    ]
    assert evidence_snapshot_collection_hash(members=pairs) == (
        evidence_snapshot_collection_hash(members=list(reversed(pairs)))
    )


def test_collection_hash_is_deterministic() -> None:
    pairs = [("logical-a", "doc-a2"), ("logical-b", "doc-b1")]
    assert evidence_snapshot_collection_hash(members=pairs) == (
        evidence_snapshot_collection_hash(members=pairs)
    )


def test_collection_hash_changes_with_member_version() -> None:
    base = [("logical-a", "doc-a2"), ("logical-b", "doc-b1")]
    changed = [("logical-a", "doc-a3"), ("logical-b", "doc-b1")]
    assert evidence_snapshot_collection_hash(members=base) != (
        evidence_snapshot_collection_hash(members=changed)
    )


def test_collection_hash_distinguishes_logical_documents_of_same_content() -> None:
    # 同一原始内容在不同逻辑资料下不碰撞（去重不合并临床作用域）。
    a = evidence_snapshot_collection_hash(members=[("logical-a", "doc-v1")])
    b = evidence_snapshot_collection_hash(members=[("logical-b", "doc-v1")])
    assert a != b


# ---------------------------------------------------------------------------
# ReviewEpisode 活动指针一致性
# ---------------------------------------------------------------------------


def _episode(**overrides) -> evidence_ingestion.ReviewEpisode:
    values: dict[str, Any] = {
        "revision": 1,
        "review_episode_id": "ep-1",
        "subject_id": "subj-1",
        "project_id": "proj-1",
        "rule_set_id": "rs-1",
        "study_phase": StudyPhase.PHASE_II,
        "stage": ReviewStage.SCREENING,
        "protocol_version_id": "pv-1",
        "rule_set_revision": 1,
        "evidence_snapshot_id": "snap-legacy",
        "active_evidence_snapshot_id": None,
        "active_evidence_processing_revision_id": None,
        "anchor_dates": {},
        "due_at": None,
    }
    values.update(overrides)
    return evidence_ingestion.ReviewEpisode(**values)


def test_episode_active_pointers_are_pairwise_consistent() -> None:
    _episode()
    _episode(
        active_evidence_snapshot_id="snap-1",
        active_evidence_processing_revision_id="pr-1",
    )
    with pytest.raises(ValidationError, match="必须同时存在或同时为空"):
        _episode(active_evidence_snapshot_id="snap-1")
    with pytest.raises(ValidationError, match="必须同时存在或同时为空"):
        _episode(active_evidence_processing_revision_id="pr-1")


def test_episode_due_at_requires_utc() -> None:
    with pytest.raises(ValidationError, match="UTC"):
        _episode(due_at=datetime.fromisoformat("2026-08-20T08:00:00"))


# ---------------------------------------------------------------------------
# 包根导出不遮蔽 Phase 3 投影合同
# ---------------------------------------------------------------------------


def test_package_root_snapshot_stays_phase3_and_phase4_is_module_scoped() -> None:
    from app.domain.contracts import EvidenceSnapshot as root_snapshot

    assert root_snapshot is phase3_evidence.EvidenceSnapshot
    assert root_snapshot is not evidence_ingestion.EvidenceSnapshot
    assert evidence_ingestion.EvidenceSnapshot is not phase3_evidence.EvidenceSnapshot


def test_package_root_exports_phase4_unique_names() -> None:
    assert SourceBlob is evidence_ingestion.SourceBlob
    assert EvidenceSnapshotMember is evidence_ingestion.EvidenceSnapshotMember
    assert SourceDocumentMetadataRevision is evidence_ingestion.SourceDocumentMetadataRevision
