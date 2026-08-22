"""Phase 4 上传预览合同确定性测试（Slice 4.2）。

冻结上传方式/预览/条目/状态/冲突处置合同：文件名不是内容身份、确定性身份与摘要
重算一致、逐文件分类约束（新增/重复/冲突/不支持/无法读取/遗漏/预计重新识别）、
处理建议与分类映射、补充资料必须有前序、摘要与条目内容绑定。
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.contracts.enums import (
    UploadItemStatus,
    UploadMode,
    UploadPreviewStatus,
)
from app.domain.contracts.evidence_upload import (
    EvidenceUploadCommit,
    EvidenceUploadItem,
    EvidenceUploadPreview,
    evidence_preview_digest,
    logical_document_id,
    source_document_version_id,
)

NOW = datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC)
SHA = "a" * 64


def _item(**overrides) -> EvidenceUploadItem:
    base = {
        "item_id": uuid4().hex,
        "preview_id": "preview-1",
        "file_name": "report.pdf",
        "sha256": SHA,
        "byte_size": 10,
        "media_type": "application/pdf",
        "storage_ref": "staging/preview-1/" + SHA,
        "status": UploadItemStatus.ADDED,
        "processing_hint": "process_new",
        "logical_document_id": None,
        "existing_version_id": None,
        "error_detail": None,
    }
    base.update(overrides)
    return EvidenceUploadItem.model_validate(base)


def _preview(items: list[EvidenceUploadItem], **overrides) -> EvidenceUploadPreview:
    base = {
        "preview_id": "preview-1",
        "project_id": "project-1",
        "subject_id": "subject-1",
        "review_episode_id": "episode-1",
        "upload_mode": UploadMode.FULL,
        "base_revision": 1,
        "base_snapshot_id": None,
        "status": UploadPreviewStatus.STAGED,
        "items": items,
        "preview_sha256": "0" * 64,
        "created_at": NOW,
        "created_by": "tester",
    }
    base.update(overrides)
    like = EvidenceUploadPreview.model_construct(**base)
    base["preview_sha256"] = evidence_preview_digest(like)
    return EvidenceUploadPreview.model_validate(base)


# ---------------------------------------------------------------------------
# 条目合同
# ---------------------------------------------------------------------------


def test_added_item_requires_sha256_and_staging_ref():
    item = _item()
    assert item.status == UploadItemStatus.ADDED
    assert item.processing_hint == "process_new"
    with pytest.raises(ValidationError, match="SHA-256"):
        _item(sha256=None)
    with pytest.raises(ValidationError, match="暂存引用"):
        _item(storage_ref=None)


def test_item_hint_must_match_status():
    with pytest.raises(ValidationError, match="处理建议"):
        _item(status=UploadItemStatus.DUPLICATE, processing_hint="process_new")


def test_unsupported_item_requires_reason_and_staging_ref():
    item = _item(
        status=UploadItemStatus.UNSUPPORTED,
        processing_hint="rejected",
        media_type="application/zip",
        error_detail="压缩包格式暂不支持",
    )
    assert item.status == UploadItemStatus.UNSUPPORTED
    with pytest.raises(ValidationError, match="原因"):
        _item(
            status=UploadItemStatus.UNSUPPORTED,
            processing_hint="rejected",
            error_detail=None,
        )
    with pytest.raises(ValidationError, match="暂存引用"):
        _item(
            status=UploadItemStatus.UNSUPPORTED,
            processing_hint="rejected",
            storage_ref=None,
            error_detail="压缩包格式暂不支持",
        )


def test_unreadable_item_has_no_sha_or_ref_but_requires_reason():
    item = _item(
        status=UploadItemStatus.UNREADABLE,
        processing_hint="rejected",
        sha256=None,
        storage_ref=None,
        error_detail="无法识别文件格式",
    )
    assert item.sha256 is None and item.storage_ref is None
    with pytest.raises(ValidationError, match="原因"):
        _item(
            status=UploadItemStatus.UNREADABLE,
            processing_hint="rejected",
            sha256=None,
            storage_ref=None,
            error_detail=None,
        )
    with pytest.raises(ValidationError, match="不能登记内容哈希"):
        _item(
            status=UploadItemStatus.UNREADABLE,
            processing_hint="rejected",
            sha256=SHA,
            storage_ref=None,
            error_detail="无法识别文件格式",
        )


def test_conflict_item_requires_logical_and_existing_version():
    _item(
        status=UploadItemStatus.CONFLICT,
        processing_hint="require_resolution",
        logical_document_id="logical-1",
        existing_version_id="version-1",
    )
    with pytest.raises(ValidationError, match="基准快照中的逻辑资料与活动版本"):
        _item(
            status=UploadItemStatus.CONFLICT,
            processing_hint="require_resolution",
            logical_document_id=None,
            existing_version_id=None,
        )


def test_omission_item_has_no_staging_ref_but_keeps_identity():
    item = _item(
        status=UploadItemStatus.FULL_SNAPSHOT_OMISSION,
        processing_hint="omitted",
        storage_ref=None,
        logical_document_id="logical-1",
        existing_version_id="version-1",
    )
    assert item.storage_ref is None
    with pytest.raises(ValidationError, match="不能携带暂存引用"):
        _item(
            status=UploadItemStatus.FULL_SNAPSHOT_OMISSION,
            processing_hint="omitted",
            logical_document_id="logical-1",
            existing_version_id="version-1",
        )


def test_duplicate_item_allows_intra_preview_without_existing_version():
    # 内容重复可绑定基准版本，也可仅绑定逻辑资料（一次上传内同内容去重）。
    _item(
        status=UploadItemStatus.DUPLICATE,
        processing_hint="reuse_existing",
        logical_document_id="logical-1",
        existing_version_id="version-1",
    )
    _item(
        status=UploadItemStatus.DUPLICATE,
        processing_hint="reuse_existing",
        logical_document_id="logical-2",
        existing_version_id=None,
    )
    with pytest.raises(ValidationError, match="被去重的逻辑资料"):
        _item(
            status=UploadItemStatus.DUPLICATE,
            processing_hint="reuse_existing",
            logical_document_id=None,
            existing_version_id=None,
        )


def test_incremental_preview_requires_prior_snapshot():
    item = _item()
    with pytest.raises(ValidationError, match="补充资料预览必须绑定"):
        _preview(
            [item],
            upload_mode=UploadMode.INCREMENTAL,
            base_snapshot_id=None,
        )
    _preview(
        [item],
        upload_mode=UploadMode.INCREMENTAL,
        base_snapshot_id="snapshot-prior",
    )


def test_full_preview_may_carry_comparison_baseline():
    item = _item()
    # 无前序（首次完整快照）允许 base_snapshot_id 为空。
    _preview([item], upload_mode=UploadMode.FULL, base_snapshot_id=None)
    # 有上一有效快照时绑定比较基线。
    _preview([item], upload_mode=UploadMode.FULL, base_snapshot_id="snapshot-prior")


def test_preview_requires_items_belong_to_preview():
    item = _item(preview_id="other-preview")
    with pytest.raises(ValidationError, match="必须属于当前预览"):
        _preview([item])


def test_preview_digest_recomputed_and_tamper_resistant():
    item = _item()
    preview = _preview([item])
    assert preview.preview_sha256 == evidence_preview_digest(preview)
    # 摘要绑定逐文件内容身份（SHA-256/文件名），不绑定条目 ID。
    assert evidence_preview_digest(_preview([_item()])) == preview.preview_sha256
    # 篡改条目内容（更换 SHA-256）后摘要不一致：重新构造被拒。
    different = _item(sha256="b" * 64)
    with pytest.raises(ValidationError, match="摘要与逐文件内容不一致"):
        EvidenceUploadPreview.model_validate(
            {
                **preview.model_dump(mode="json"),
                "items": [different.model_dump(mode="json")],
            }
        )


def test_preview_digest_deterministic_and_name_independent():
    a = _item()
    p1 = _preview([a])
    p2 = _preview([_item()])  # 同内容不同条目对象
    assert p1.preview_sha256 == p2.preview_sha256
    # 同一内容改名后仍属同一逻辑资料身份（文件名不是内容身份）。
    logical1 = logical_document_id(
        project_id="p", subject_id="s", review_episode_id="e", sha256=SHA
    )
    logical2 = logical_document_id(
        project_id="p", subject_id="s", review_episode_id="e", sha256=SHA
    )
    assert logical1 == logical2
    assert logical_document_id(
        project_id="p", subject_id="other", review_episode_id="e", sha256=SHA
    ) != logical1


def test_version_id_is_deterministic_per_content_and_number():
    v1 = source_document_version_id(logical_document_id="L", version_number=1, sha256=SHA)
    assert v1 == source_document_version_id(
        logical_document_id="L", version_number=1, sha256=SHA
    )
    assert v1 != source_document_version_id(
        logical_document_id="L", version_number=2, sha256=SHA
    )
    assert v1 != source_document_version_id(
        logical_document_id="L", version_number=1, sha256="b" * 64
    )


def test_commit_requires_utc_and_duplicate_job_consistency():
    commit = EvidenceUploadCommit(
        commit_id="c1",
        preview_id="preview-1",
        evidence_snapshot_id="snapshot-1",
        project_id="p",
        subject_id="s",
        review_episode_id="e",
        upload_mode=UploadMode.FULL,
        preview_sha256=SHA,
        idempotency_key="key-1",
        job_id="job-1",
        duplicate=False,
        created_at=NOW,
        created_by="tester",
    )
    assert commit.job_id == "job-1"
    with pytest.raises(ValidationError, match="UTC"):
        EvidenceUploadCommit.model_validate(
            commit.model_dump(mode="json") | {"created_at": "2026-08-19T12:00:00"}
        )
