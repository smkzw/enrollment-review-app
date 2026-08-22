"""Phase 4 上传预览服务确定性测试（Slice 4.2）。

覆盖服务全链：暂存/指纹/格式探测、差异分类、取消清理、补充/完整集合计算、确认
事务（候选快照 + 确认记录 + 幂等记录 + 初始持久 Job 同一事务创建/复用）、重复集合
no-op、同名异内容处置、崩溃回滚、并发确认、跨作用域、基准修订过期、摘要漂移与
损坏暂存拒绝。任何用例都不触发 OCR。
"""
from __future__ import annotations

import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest
from sqlalchemy import func, select, text

from app.domain.contracts.enums import (
    SnapshotMemberOrigin,
    SnapshotStatus,
    UploadConflictResolution,
    UploadItemStatus,
    UploadMode,
    UploadPreviewStatus,
)
from app.domain.contracts.evidence_upload import (
    EvidenceUploadConfirmInput,
)
from app.services.evidence_app_errors import (
    AppEvidenceUploadError,
    AppIdempotencyConflictError,
    AppScopeMismatchError,
)
from app.services.evidence_upload_service import (
    EvidenceUploadService,
    EvidenceUploadServiceError,
    UploadedFileInput,
    detect_file_format,
)
from app.storage.evidence_models import (
    EvidenceSnapshotV2Record,
    SourceDocumentVersionV2Record,
)
from app.storage.evidence_repositories import (
    EvidenceSnapshotRepository,
    SourceDocumentMetadataRevisionRepository,
)
from app.storage.evidence_upload_models import (
    EvidenceUploadCommitRecord,
    EvidenceUploadPreviewRecord,
)
from app.storage.repositories import (
    EpisodeRepository,
    persist_fixture,
)
from tests.v2.storage.test_repositories_roundtrip import FIXTURES

PDF_HEAD = b"%PDF-1.7\n"


@contextmanager
def raises_upload_error(code: str):
    """公共上传服务只向调用方暴露稳定的应用错误。"""
    with pytest.raises(AppEvidenceUploadError) as captured:
        yield
    assert captured.value.code == code


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def pdf(content: bytes, name: str = "report.pdf") -> UploadedFileInput:
    return UploadedFileInput(file_name=name, content=PDF_HEAD + content)


def zipfile(content: bytes, name: str = "archive.zip") -> UploadedFileInput:
    return UploadedFileInput(file_name=name, content=b"PK\x03\x04" + content)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """临时 V2 数据根 + create_all 引擎 + 已播种 Phase 3 fixture 的服务。"""
    monkeypatch.setenv("ENROLLMENT_V2_DATA_DIR", str(tmp_path / "data_v2"))
    from app.storage.config import resolve_data_paths
    from app.storage.db import Base, build_engine, build_session_factory

    paths = resolve_data_paths()
    paths.ensure_directories()
    engine = build_engine(paths.db_path)
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    with factory() as session:
        fixture = FIXTURES[0]
        persist_fixture(session, fixture)
        session.commit()
        scope = (
            fixture.project.project_id,
            fixture.subject.subject_id,
            fixture.review_episode.review_episode_id,
        )
        job_baseline = int(
            session.execute(select(func.count()).select_from(text("jobs"))).scalar_one()
        )
    service = EvidenceUploadService(factory, paths)
    yield {
        "factory": factory,
        "service": service,
        "paths": paths,
        "scope": scope,
        "fixture": fixture,
        "job_baseline": job_baseline,
    }
    engine.dispose()


def make_command(
    preview,
    *,
    scope=None,
    resolutions: dict[str, UploadConflictResolution] | None = None,
    idempotency_key: str | None = None,
    preview_sha256: str | None = None,
    base_revision: int | None = None,
) -> EvidenceUploadConfirmInput:
    project_id, subject_id, episode_id = scope or (
        preview.project_id,
        preview.subject_id,
        preview.review_episode_id,
    )
    return EvidenceUploadConfirmInput(
        preview_id=preview.preview_id,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=preview.upload_mode,
        base_revision=base_revision if base_revision is not None else preview.base_revision,
        preview_sha256=preview_sha256 or preview.preview_sha256,
        idempotency_key=idempotency_key or "key-1",
        resolutions=resolutions or {},
    )


def count(env, table: str) -> int:
    with env["factory"]() as session:
        return int(session.execute(select(func.count()).select_from(text(table))).scalar_one())


def jobs(env) -> int:
    """新增任务数（扣除 fixture 播种的最小 Job 行）。"""
    return count(env, "jobs") - env["job_baseline"]


def confirm_full(env, files, *, key="key-full"):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=files,
        created_by="tester",
    )
    result = service.confirm(make_command(preview, idempotency_key=key), created_by="tester")
    return preview, result


def _establish_active_pair(env, snapshot_id: str) -> None:
    """模拟 Slice 4.4 激活后的状态（测试脚手架）：快照 ACTIVE + 审核节点活动指针对。

    上传测试不构建 OCR 栈，因此以最小 ORM 行建立 base/complete 修订对满足外键与
    形态 CHECK，并直接写入审核节点成对指针；上传服务只消费指针，不读取该修订闭包。
    这是对“激活后基准”的仿真，真实激活路径由 ``EvidenceActivationService`` 完成。
    """
    from datetime import UTC, datetime

    from app.domain.contracts.evidence_locator import CompleteEvidenceProcessingRevision
    from app.domain.contracts.evidence_processing import EvidenceProcessingRevision
    from app.domain.publication import evidence_processing_manifest_hash
    from app.storage.codecs import encode_contract, to_utc_naive
    from app.storage.evidence_repositories import EvidenceSnapshotRepository
    from app.storage.models import ReviewEpisodeRecord
    from app.storage.ocr_models import EvidenceProcessingRevisionRecord

    fixed = datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC)
    with env["factory"]() as session, session.begin():
        repo = EvidenceSnapshotRepository(session)
        contract = repo.get(snapshot_id)
        activated = contract.model_copy(update={"status": SnapshotStatus.ACTIVE})
        payload_json, payload_sha256 = encode_contract(activated)
        row = session.get(EvidenceSnapshotV2Record, snapshot_id)
        row.status = SnapshotStatus.ACTIVE.value
        row.payload_json = payload_json
        row.payload_sha256 = payload_sha256

        base_id = f"base-{snapshot_id}"
        complete_id = f"complete-{snapshot_id}"
        empty_manifest = evidence_processing_manifest_hash(entries=[])
        existing_complete = session.get(
            EvidenceProcessingRevisionRecord, complete_id
        )
        if existing_complete is None:
            base_contract = EvidenceProcessingRevision(
                evidence_processing_revision_id=base_id,
                evidence_snapshot_id=snapshot_id,
                project_id=contract.project_id,
                subject_id=contract.subject_id,
                review_episode_id=contract.review_episode_id,
                manifest=[],
                manifest_sha256=empty_manifest,
                created_at=fixed,
                created_by="scaffold",
            )
            bj, bsh = encode_contract(base_contract)
            session.add(
                EvidenceProcessingRevisionRecord(
                    evidence_processing_revision_id=base_id,
                    evidence_snapshot_id=snapshot_id,
                    project_id=contract.project_id,
                    subject_id=contract.subject_id,
                    review_episode_id=contract.review_episode_id,
                    manifest_sha256=empty_manifest,
                    status="ready",
                    is_activatable=False,
                    revision_kind="base",
                    created_by="scaffold",
                    created_at=to_utc_naive(fixed),
                    payload_json=bj,
                    payload_sha256=bsh,
                )
            )
            complete_contract = CompleteEvidenceProcessingRevision(
                evidence_processing_revision_id=complete_id,
                evidence_snapshot_id=snapshot_id,
                project_id=contract.project_id,
                subject_id=contract.subject_id,
                review_episode_id=contract.review_episode_id,
                base_processing_revision_id=base_id,
                producer_candidate_id=f"scaffold-producer-{snapshot_id}",
                candidate_input_sha256="f" * 64,
                manifest=[],
                manifest_sha256=empty_manifest,
                completion_manifest_sha256="0" * 64,
                created_at=fixed,
                created_by="scaffold",
            )
            cj, csh = encode_contract(complete_contract)
            session.add(
                EvidenceProcessingRevisionRecord(
                    evidence_processing_revision_id=complete_id,
                    evidence_snapshot_id=snapshot_id,
                    project_id=contract.project_id,
                    subject_id=contract.subject_id,
                    review_episode_id=contract.review_episode_id,
                    manifest_sha256=empty_manifest,
                    status="ready",
                    is_activatable=True,
                    revision_kind="complete",
                    base_processing_revision_id=base_id,
                    producer_candidate_id=f"scaffold-producer-{snapshot_id}",
                    candidate_input_sha256="f" * 64,
                    completion_manifest_sha256="0" * 64,
                    created_by="scaffold",
                    created_at=to_utc_naive(fixed),
                    payload_json=cj,
                    payload_sha256=csh,
                )
            )
        # 审核节点活动指针对：指针为当前版本唯一权威。
        # （脚手架不改修订号，避免打破硬编码 base_revision=1 的上传基准测试；
        # 真实激活事务会按预期修订号乐观锁递增 revision。）
        episode = EpisodeRepository(session).get(contract.review_episode_id)
        new_episode = episode.model_copy(
            update={
                "active_evidence_snapshot_id": snapshot_id,
                "active_evidence_processing_revision_id": complete_id,
            }
        )
        ep_payload, ep_sha = encode_contract(new_episode)
        episode_row = session.get(ReviewEpisodeRecord, contract.review_episode_id)
        episode_row.active_evidence_snapshot_id = snapshot_id
        episode_row.active_evidence_processing_revision_id = complete_id
        episode_row.payload_json = ep_payload
        episode_row.payload_sha256 = ep_sha


def activate_full(env, files, *, key="key-active"):
    """确认一个完整快照并立即建立活动指针对（形成有效基准，供补充/遗漏测试）。"""
    _preview, result = confirm_full(env, files, key=key)
    _establish_active_pair(env, result.evidence_snapshot_id)
    return result


# ---------------------------------------------------------------------------
# 格式探测
# ---------------------------------------------------------------------------


def test_detect_file_format_supported_and_archives():
    assert detect_file_format("a.pdf", b"%PDF-1.4 x").supported
    assert detect_file_format("a.txt", "正常文本".encode()).supported
    assert detect_file_format("a.txt", "GBK文本".encode("gb18030")).supported
    assert detect_file_format("a.jpg", b"\xff\xd8\xff\xe0").supported
    assert detect_file_format("a.png", b"\x89PNG\r\n\x1a\n").supported
    assert detect_file_format("a.bmp", b"BM\x00\x00").supported
    assert detect_file_format("a.tif", b"II*\x00").supported
    assert detect_file_format("a.webp", b"RIFF\x00\x00\x00\x00WEBP").supported
    assert detect_file_format("a.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1").supported
    assert detect_file_format("a.docx", b"PK\x03\x04word/document.xml").supported
    for name, head in [
        ("a.zip", b"PK\x03\x04rest"),
        ("a.rar", b"Rar!\x1a\x07\x00"),
        ("a.7z", b"7z\xbc\xaf\x27\x1c"),
        ("a.gz", b"\x1f\x8b\x08\x00"),
    ]:
        result = detect_file_format(name, head)
        assert not result.supported and result.kind == "archive", name
    assert detect_file_format("empty.pdf", b"").kind == "unreadable"
    assert detect_file_format("junk.bin", b"\x00\x01\x02").kind == "unreadable"
    assert detect_file_format("fake.pdf", b"not a pdf").kind == "unreadable"


# ---------------------------------------------------------------------------
# 预览创建
# ---------------------------------------------------------------------------


def test_create_preview_stages_files_with_fingerprint(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"one"), pdf(b"two", name="second.pdf")],
        created_by="tester",
    )
    assert preview.status == UploadPreviewStatus.STAGED
    assert {item.file_name for item in preview.items} == {"report.pdf", "second.pdf"}
    assert all(item.status == UploadItemStatus.ADDED for item in preview.items)
    # 暂存文件按内容 SHA-256 命名且内容与指纹一致。
    for item in preview.items:
        staged = env["paths"].root / item.storage_ref
        assert staged.is_file()
        assert sha(staged.read_bytes()) == item.sha256
        assert item.storage_ref.startswith(f"staging/{preview.preview_id}/")
    # 摘要与条目内容绑定，服务端可重算。
    from app.domain.contracts.evidence_upload import evidence_preview_digest

    assert preview.preview_sha256 == evidence_preview_digest(preview)


def test_create_preview_incremental_without_prior_rejected(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    with raises_upload_error("NO_EFFECTIVE_SNAPSHOT"):
        service.create_preview(
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=episode_id,
            upload_mode=UploadMode.INCREMENTAL,
            base_revision=1,
            files=[pdf(b"one")],
            created_by="tester",
        )


def test_create_preview_scope_and_revision_checks(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    with pytest.raises(AppScopeMismatchError):
        service.create_preview(
            project_id=project_id,
            subject_id="other-subject",
            review_episode_id=episode_id,
            upload_mode=UploadMode.FULL,
            base_revision=1,
            files=[pdf(b"one")],
            created_by="tester",
        )
    with raises_upload_error("STALE_BASE_REVISION"):
        service.create_preview(
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=episode_id,
            upload_mode=UploadMode.FULL,
            base_revision=99,
            files=[pdf(b"one")],
            created_by="tester",
        )
    with raises_upload_error("EMPTY_UPLOAD"):
        service.create_preview(
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=episode_id,
            upload_mode=UploadMode.FULL,
            base_revision=1,
            files=[],
            created_by="tester",
        )


def test_preview_classifies_duplicate_conflict_unsupported_unreadable_omission(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    # 基准：report.pdf(X)、lab.pdf(Y) 的完整快照（激活为有效基准）。
    activate_full(env, [pdf(b"X"), pdf(b"Y", name="lab.pdf")], key="key-base")
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[
            pdf(b"X"),  # 与基准同内容 -> 预计重新识别
            pdf(b"Z"),  # 同名异内容 -> 冲突
            pdf(b"W", name="new.pdf"),  # 新增
            zipfile(b"stuff"),  # 压缩包 -> 不支持
            UploadedFileInput(file_name="empty.txt", content=b""),  # 无法读取
        ],
        created_by="tester",
    )
    by_key = {(item.file_name, item.status): item for item in preview.items}
    reprocessed = by_key[("report.pdf", UploadItemStatus.EXPECTED_REPROCESSING)]
    assert reprocessed.logical_document_id is not None
    assert reprocessed.existing_version_id is not None
    assert reprocessed.processing_hint == "reprocess"
    assert by_key[("lab.pdf", UploadItemStatus.FULL_SNAPSHOT_OMISSION)].processing_hint == "omitted"
    assert by_key[("lab.pdf", UploadItemStatus.FULL_SNAPSHOT_OMISSION)].storage_ref is None
    assert by_key[("new.pdf", UploadItemStatus.ADDED)].status == UploadItemStatus.ADDED
    assert by_key[("archive.zip", UploadItemStatus.UNSUPPORTED)].status == UploadItemStatus.UNSUPPORTED
    assert "压缩包" in by_key[("archive.zip", UploadItemStatus.UNSUPPORTED)].error_detail
    assert by_key[("empty.txt", UploadItemStatus.UNREADABLE)].error_detail
    assert by_key[("empty.txt", UploadItemStatus.UNREADABLE)].sha256 is None


def test_incremental_preview_classifies_duplicate_and_conflict(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    activate_full(env, [pdf(b"X")], key="key-base")
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.INCREMENTAL,
        base_revision=1,
        files=[pdf(b"X"), pdf(b"Z")],
        created_by="tester",
    )
    by_status = {(item.file_name, item.status): item for item in preview.items}
    duplicate = by_status[("report.pdf", UploadItemStatus.DUPLICATE)]
    assert duplicate.processing_hint == "reuse_existing"
    assert duplicate.existing_version_id is not None
    conflict = by_status[("report.pdf", UploadItemStatus.CONFLICT)]
    assert conflict.logical_document_id is not None
    assert conflict.existing_version_id is not None


def test_intra_preview_duplicate_content_classified_duplicate(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"X"), pdf(b"X", name="copy.pdf")],
        created_by="tester",
    )
    statuses = {(item.file_name, item.status) for item in preview.items}
    assert (("report.pdf", UploadItemStatus.ADDED)) in statuses
    assert (("copy.pdf", UploadItemStatus.DUPLICATE)) in statuses


# ---------------------------------------------------------------------------
# 确认：完整快照
# ---------------------------------------------------------------------------


def test_confirm_full_creates_snapshot_commit_job_in_one_transaction(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"one"), pdf(b"two", name="lab.pdf")],
        created_by="tester",
    )
    result = service.confirm(make_command(preview), created_by="tester")
    assert result.created and not result.duplicate
    assert result.job_id is not None
    assert result.snapshot.upload_mode == UploadMode.FULL
    assert len(result.snapshot.members) == 2
    assert all(m.origin == SnapshotMemberOrigin.ADDED for m in result.snapshot.members)
    assert result.snapshot.status == SnapshotStatus.STAGED
    assert count(env, "evidence_snapshots_v2") == 1
    assert count(env, "evidence_upload_commits") == 1
    assert jobs(env) == 1
    assert count(env, "source_blobs") == 2
    assert count(env, "source_document_versions_v2") == 2
    assert count(env, "source_document_metadata_revisions") == 2
    with env["factory"]() as session:
        members = {
            member.source_document_version_id: member
            for member in result.snapshot.members
        }
        suggested = {
            SourceDocumentMetadataRevisionRepository(session)
            .head(version_id)
            .document_type
            for version_id in members
        }
        assert suggested == {"其他资料（待确认）", "实验室检验结果"}
        assert all(
            SourceDocumentMetadataRevisionRepository(session)
            .head(version_id)
            .is_auto_suggestion
            for version_id in members
        )
    # blob 文件落盘且可读。
    for blob in result.snapshot.members:
        with env["factory"]() as session:
            from app.storage.evidence_models import SourceDocumentVersionV2Record
            from app.storage.evidence_repositories import SourceDocumentRepository

            row = session.get(SourceDocumentVersionV2Record, blob.source_document_version_id)
            version = SourceDocumentRepository._decode(row)
            blob_path = env["paths"].blobs_dir / version.source_blob_sha256
            assert blob_path.is_file()
    # 预览转为已确认；确认记录绑定任务。
    with env["factory"]() as session:
        row = session.get(EvidenceUploadPreviewRecord, preview.preview_id)
        assert row.status == UploadPreviewStatus.COMMITTED.value
        commit_row = session.get(EvidenceUploadCommitRecord, result.commit_id)
        assert commit_row.job_id == result.job_id


def test_confirm_duplicate_collection_is_noop_without_new_job(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    _first_preview, first = confirm_full(env, [pdf(b"one")], key="key-first")
    # 同一集合经新预览再次确认 -> 返回既有快照，不创建新快照/新 Job。
    second_preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"one")],
        created_by="tester",
    )
    second = service.confirm(
        make_command(second_preview, idempotency_key="key-second"), created_by="tester"
    )
    assert not second.created and second.duplicate
    assert second.evidence_snapshot_id == first.evidence_snapshot_id
    assert second.job_id is None
    assert count(env, "evidence_snapshots_v2") == 1
    assert jobs(env) == 1
    assert count(env, "evidence_upload_commits") == 2  # 重复请求仍留审计记录


def test_incremental_same_collection_as_active_full_is_cross_mode_noop(env):
    """上传方式不是集合身份：补充同一文件不得制造第二个快照或任务。"""
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    _first_preview, first = confirm_full(env, [pdf(b"one")], key="key-full")
    _establish_active_pair(env, first.evidence_snapshot_id)

    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.INCREMENTAL,
        base_revision=1,
        files=[pdf(b"one")],
        created_by="tester",
    )
    result = service.confirm(
        make_command(preview, idempotency_key="key-incremental-same"),
        created_by="tester",
    )

    assert result.duplicate and not result.created
    assert result.evidence_snapshot_id == first.evidence_snapshot_id
    assert result.job_id is None
    assert count(env, "evidence_snapshots_v2") == 1
    assert jobs(env) == 1


def test_confirm_idempotent_retry_same_key_returns_same_result(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"one")],
        created_by="tester",
    )
    command = make_command(preview, idempotency_key="retry-key")
    first = service.confirm(command, created_by="tester")
    # 客户端重试同一命令（同键同内容）-> 返回同一确认结果，不创建新 Job/Commit。
    retried = service.confirm(command, created_by="tester")
    assert retried.commit_id == first.commit_id
    assert retried.evidence_snapshot_id == first.evidence_snapshot_id
    assert retried.job_id == first.job_id
    assert count(env, "evidence_upload_commits") == 1
    assert jobs(env) == 1


def test_confirm_same_key_different_content_conflicts(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"one")],
        created_by="tester",
    )
    command = make_command(preview, idempotency_key="key-1")
    service.confirm(command, created_by="tester")
    tampered = make_command(
        preview,
        idempotency_key="key-1",
        preview_sha256="b" * 64,
    )
    with pytest.raises(AppIdempotencyConflictError):
        service.confirm(tampered, created_by="tester")


def test_confirm_cross_scope_rejected(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"one")],
        created_by="tester",
    )
    cross = make_command(preview, scope=(project_id, "other-subject", episode_id))
    with pytest.raises(AppScopeMismatchError, match="作用域"):
        service.confirm(cross, created_by="tester")


def test_confirm_digest_mismatch_rejected(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"one")],
        created_by="tester",
    )
    command = make_command(preview, preview_sha256="c" * 64)
    with raises_upload_error("PREVIEW_DIGEST_MISMATCH"):
        service.confirm(command, created_by="tester")
    assert count(env, "evidence_snapshots_v2") == 0


def test_confirm_stale_base_revision_rejected(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"one")],
        created_by="tester",
    )
    # 预览创建后审核节点修订号被推进 -> 确认必须拒绝（stale）。
    with env["factory"]() as session, session.begin():
        from app.domain.contracts.enums import ReviewStage

        EpisodeRepository(session).update(
            episode_id,
            expected_revision=1,
            changes={"stage": ReviewStage.SCREENING},
        )
    command = make_command(preview)
    with raises_upload_error("STALE_BASE_REVISION"):
        service.confirm(command, created_by="tester")
    assert count(env, "evidence_snapshots_v2") == 0


def test_confirm_stale_base_snapshot_rejected(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    # 预览 A 基于 ACTIVE 基准 S1；随后活动基准切换为 S2，A 的基准已过期。
    base_s1 = activate_full(env, [pdf(b"one")], key="key-s1")
    preview_a = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"two", name="other.pdf")],
        created_by="tester",
    )
    assert preview_a.base_snapshot_id == base_s1.evidence_snapshot_id
    # 活动基准改变：S2 激活后成为最新有效快照。
    activate_full(env, [pdf(b"three", name="third.pdf")], key="key-s2")
    with raises_upload_error("STALE_BASE_REVISION"):
        service.confirm(make_command(preview_a, idempotency_key="key-stale-snapshot"), created_by="tester")
    assert count(env, "evidence_snapshots_v2") == 2  # 只有 S1/S2，没有为旧预览建新快照


def test_confirm_empty_selection_rejected(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[zipfile(b"stuff")],
        created_by="tester",
    )
    with raises_upload_error("EMPTY_SELECTION"):
        service.confirm(make_command(preview), created_by="tester")
    assert count(env, "evidence_snapshots_v2") == 0


def test_confirm_full_does_not_inherit_and_reports_omission(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    activate_full(env, [pdf(b"X"), pdf(b"Y", name="lab.pdf")], key="key-base")
    # 新完整快照只含本次选择：report.pdf(Z 新内容) + new.pdf；lab.pdf 被遗漏。
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"Z"), pdf(b"W", name="new.pdf")],
        created_by="tester",
    )
    omissions = [
        item for item in preview.items if item.status == UploadItemStatus.FULL_SNAPSHOT_OMISSION
    ]
    assert [item.file_name for item in omissions] == ["lab.pdf"]
    conflict = next(
        item for item in preview.items if item.status == UploadItemStatus.CONFLICT
    )
    result = service.confirm(
        make_command(
            preview,
            idempotency_key="key-new",
            resolutions={conflict.item_id: UploadConflictResolution.NEW_VERSION},
        ),
        created_by="tester",
    )
    assert result.snapshot.upload_mode == UploadMode.FULL
    assert result.snapshot.prior_snapshot_id is None
    assert len(result.snapshot.members) == 2
    assert all(m.origin == SnapshotMemberOrigin.ADDED for m in result.snapshot.members)
    assert count(env, "evidence_snapshots_v2") == 2  # 旧快照保留


# ---------------------------------------------------------------------------
# 确认：同名异内容处置
# ---------------------------------------------------------------------------


def _conflict_preview(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    activate_full(env, [pdf(b"X")], key="key-conflict-base")
    return service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.INCREMENTAL,
        base_revision=1,
        files=[pdf(b"Z")],
        created_by="tester",
    )


def test_confirm_conflict_requires_explicit_resolution(env):
    service = env["service"]
    preview = _conflict_preview(env)
    with raises_upload_error("MISSING_RESOLUTION"):
        service.confirm(make_command(preview), created_by="tester")
    conflict = next(item for item in preview.items if item.status == UploadItemStatus.CONFLICT)
    with raises_upload_error("UNKNOWN_RESOLUTION"):
        service.confirm(
            make_command(
                preview,
                resolutions={
                    conflict.item_id: UploadConflictResolution.NEW_VERSION,
                    "bogus-item": UploadConflictResolution.NEW_VERSION,
                },
            ),
            created_by="tester",
        )
    # 提供合法处置后确认成功。
    result = service.confirm(
        make_command(
            preview,
            idempotency_key="key-resolved",
            resolutions={conflict.item_id: UploadConflictResolution.NEW_VERSION},
        ),
        created_by="tester",
    )
    assert result.created
    assert count(env, "evidence_snapshots_v2") == 2


def test_confirm_conflict_new_version_replaces_through_version_chain(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    _base = activate_full(env, [pdf(b"X")], key="key-base")
    preview = _conflict_preview(env)
    conflict = next(item for item in preview.items if item.status == UploadItemStatus.CONFLICT)
    result = service.confirm(
        make_command(
            preview,
            resolutions={conflict.item_id: UploadConflictResolution.NEW_VERSION},
        ),
        created_by="tester",
    )
    member = result.snapshot.members[0]
    assert member.origin == SnapshotMemberOrigin.REPLACED
    assert member.logical_document_id == conflict.logical_document_id
    # 版本链：同一逻辑资料两个版本，新版本显式替代旧版本。
    with env["factory"]() as session:
        from app.storage.evidence_repositories import SourceDocumentRepository

        versions = SourceDocumentRepository(session).list_by_scope(
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=episode_id,
        )
        assert len(versions) == 2
        versions.sort(key=lambda version: version.version_number)
        assert versions[0].version_number == 1
        assert versions[1].version_number == 2
        assert versions[1].supersedes_version_id == versions[0].source_document_version_id
        assert versions[1].source_blob_sha256 == sha(PDF_HEAD + b"Z")


def test_confirm_conflict_keep_parallel_keeps_old_document(env):
    service = env["service"]
    preview = _conflict_preview(env)
    conflict = next(item for item in preview.items if item.status == UploadItemStatus.CONFLICT)
    result = service.confirm(
        make_command(
            preview,
            resolutions={conflict.item_id: UploadConflictResolution.KEEP_PARALLEL},
        ),
        created_by="tester",
    )
    # 旧逻辑资料保持继承 + 新逻辑资料并列保留：快照含两个成员。
    assert len(result.snapshot.members) == 2
    origins = {m.origin for m in result.snapshot.members}
    assert origins == {SnapshotMemberOrigin.INHERITED, SnapshotMemberOrigin.ADDED}
    assert result.snapshot.prior_snapshot_id is not None
    assert count(env, "source_document_versions_v2") == 2


def test_confirm_incremental_inherits_all_baseline_members(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    activate_full(env, [pdf(b"X"), pdf(b"Y", name="lab.pdf")], key="key-base")
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.INCREMENTAL,
        base_revision=1,
        files=[pdf(b"W", name="new.pdf")],
        created_by="tester",
    )
    result = service.confirm(make_command(preview, idempotency_key="key-inc"), created_by="tester")
    assert len(result.snapshot.members) == 3  # 2 继承 + 1 新增，无静默丢失
    inherited = [m for m in result.snapshot.members if m.origin == SnapshotMemberOrigin.INHERITED]
    assert len(inherited) == 2
    assert result.snapshot.prior_snapshot_id is not None
    assert result.snapshot.comparison_snapshot_id == result.snapshot.prior_snapshot_id


# ---------------------------------------------------------------------------
# 取消清理
# ---------------------------------------------------------------------------


def test_cancel_cleans_staging_and_appends_cancelled_state(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"one")],
        created_by="tester",
    )
    staging_dir = env["paths"].root / f"staging/{preview.preview_id}"
    assert staging_dir.is_dir()
    cancelled = service.cancel(preview.preview_id, actor="tester")
    assert cancelled.status == UploadPreviewStatus.CANCELLED
    assert not staging_dir.exists(), "取消必须清理预览自有暂存"
    # 不触碰共享 blob 或历史；幂等取消可重复。
    assert count(env, "evidence_snapshots_v2") == 0
    assert count(env, "source_blobs") == 0
    again = service.cancel(preview.preview_id, actor="tester")
    assert again.status == UploadPreviewStatus.CANCELLED
    with env["factory"]() as session:
        row = session.get(EvidenceUploadPreviewRecord, preview.preview_id)
        assert row.status == UploadPreviewStatus.CANCELLED.value


def test_cancel_after_commit_rejected(env):
    service = env["service"]
    _preview, _result = confirm_full(env, [pdf(b"one")])
    preview = _preview
    with raises_upload_error("PREVIEW_STATE_CONFLICT"):
        service.cancel(preview.preview_id, actor="tester")
    assert count(env, "evidence_snapshots_v2") == 1


def test_cancel_removes_only_preview_owned_staging_not_blobs(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    _preview, _result = confirm_full(env, [pdf(b"shared")], key="key-shared")
    blob_count_before = count(env, "source_blobs")
    second = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"shared"), pdf(b"other", name="other.pdf")],
        created_by="tester",
    )
    service.cancel(second.preview_id, actor="tester")
    assert count(env, "source_blobs") == blob_count_before
    # 已确认的共享 blob 文件未被取消删除。
    with env["factory"]() as session:
        from app.storage.evidence_models import SourceBlobRecord

        rows = session.execute(select(SourceBlobRecord)).scalars().all()
        for row in rows:
            assert (env["paths"].blobs_dir / row.storage_ref.removeprefix("blobs/")).is_file()


# ---------------------------------------------------------------------------
# 崩溃/回滚/损坏暂存
# ---------------------------------------------------------------------------


def test_confirm_corrupted_staging_rejected(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"one"), pdf(b"two", name="lab.pdf")],
        created_by="tester",
    )
    # 删除其中一个暂存文件模拟损坏。
    victim = next(item for item in preview.items if item.file_name == "lab.pdf")
    (env["paths"].root / victim.storage_ref).unlink()
    with raises_upload_error("STAGING_CORRUPTED"):
        service.confirm(make_command(preview), created_by="tester")
    assert count(env, "evidence_snapshots_v2") == 0
    assert count(env, "evidence_upload_commits") == 0
    assert jobs(env) == 0
    # 预览保持可再次确认（暂存仍可重建）：补回文件后可成功。
    (env["paths"].root / victim.storage_ref).write_bytes(PDF_HEAD + b"two")
    result = service.confirm(make_command(preview, idempotency_key="key-retry"), created_by="tester")
    assert result.created and count(env, "evidence_snapshots_v2") == 1


def test_confirm_crash_rollback_leaves_no_orphans(env, monkeypatch):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"one"), pdf(b"two", name="lab.pdf")],
        created_by="tester",
    )
    calls = {"count": 0}
    original = service._promote_blob

    def boom(session, *, item, contents):
        calls["count"] += 1
        if calls["count"] == 1:
            return original(session, item=item, contents=contents)
        raise EvidenceUploadServiceError("注入的中间故障")

    monkeypatch.setattr(service, "_promote_blob", boom)
    with raises_upload_error("EVIDENCE_UPLOAD_REJECTED"):
        service.confirm(make_command(preview), created_by="tester")
    # 整个事务回滚：无孤立快照/确认/任务/版本；预览仍为 staged；暂存保留。
    assert count(env, "evidence_snapshots_v2") == 0
    assert count(env, "evidence_upload_commits") == 0
    assert jobs(env) == 0
    assert count(env, "source_document_versions_v2") == 0
    assert count(env, "source_blobs") == 0
    with env["factory"]() as session:
        row = session.get(EvidenceUploadPreviewRecord, preview.preview_id)
        assert row.status == UploadPreviewStatus.STAGED.value
    staging_dir = env["paths"].root / f"staging/{preview.preview_id}"
    assert staging_dir.is_dir()


# ---------------------------------------------------------------------------
# 并发确认
# ---------------------------------------------------------------------------


def test_concurrent_confirm_same_collection_single_snapshot_and_job(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    files = [pdf(b"one"), pdf(b"two", name="lab.pdf")]
    p1 = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=files,
        created_by="tester",
    )
    p2 = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=files,
        created_by="tester",
    )
    results: list = []
    errors: list = []

    def run(preview, key):
        try:
            results.append(
                service.confirm(make_command(preview, idempotency_key=key), created_by="tester")
            )
        except Exception as exc:  # noqa: BLE001 - 并发反例测试收集任意失败
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(run, p1, "key-c1"),
            pool.submit(run, p2, "key-c2"),
        ]
        for future in futures:
            future.result(timeout=60)

    assert len(results) == 2 and not errors, f"并发确认失败：{errors}"
    assert sum(1 for r in results if r.created) == 1
    assert sum(1 for r in results if r.duplicate) == 1
    assert results[0].evidence_snapshot_id == results[1].evidence_snapshot_id
    # 恰好一个快照、一个确认（非重复）、一个 Job。
    assert count(env, "evidence_snapshots_v2") == 1
    assert jobs(env) == 1
    with env["factory"]() as session:
        commits = session.execute(select(EvidenceUploadCommitRecord)).scalars().all()
        assert len(commits) == 2
        assert sum(1 for c in commits if not c.duplicate) == 1
        assert sum(1 for c in commits if c.duplicate) == 1
        previews = session.execute(select(EvidenceUploadPreviewRecord)).scalars().all()
        assert all(p.status == UploadPreviewStatus.COMMITTED.value for p in previews)


def test_concurrent_confirm_same_preview_single_commit(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"one")],
        created_by="tester",
    )
    outcomes: list[str] = []
    thread_errors: list[Exception] = []

    def run(key):
        try:
            result = service.confirm(
                make_command(preview, idempotency_key=key), created_by="tester"
            )
            outcomes.append("ok" if result.created else "noop")
        except AppEvidenceUploadError:
            outcomes.append("rejected")
        except Exception as exc:  # noqa: BLE001 - 并发反例测试收集任意失败
            thread_errors.append(exc)
            outcomes.append("error")

    threads = [
        threading.Thread(target=run, args=("key-a",)),
        threading.Thread(target=run, args=("key-b",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert not thread_errors, f"并发确认出现未预期异常：{thread_errors}"
    assert sorted(outcomes) == ["ok", "rejected"]
    assert count(env, "evidence_snapshots_v2") == 1
    assert jobs(env) == 1
    assert count(env, "evidence_upload_commits") == 1


def test_snapshot_members_are_content_addressed_and_deduplicated(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    confirm_full(env, [pdf(b"X")], key="key-1")
    # 第二个完整快照重新纳入同一内容：blob 复用，不新增原始二进制。
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"X"), pdf(b"W", name="new.pdf")],
        created_by="tester",
    )
    result = service.confirm(make_command(preview, idempotency_key="key-2"), created_by="tester")
    assert result.created
    assert count(env, "source_blobs") == 2  # X 复用 + W 新增
    assert len(result.snapshot.members) == 2


def test_full_snapshot_preserves_user_confirmed_file_order(env):
    _preview, result = confirm_full(
        env,
        [
            pdf(b"first", name="01-screening.pdf"),
            pdf(b"second", name="02-lab.pdf"),
            pdf(b"third", name="03-history.pdf"),
        ],
        key="key-order",
    )

    with env["factory"]() as session:
        file_names = [
            session.get(
                SourceDocumentVersionV2Record,
                member.source_document_version_id,
            ).file_name
            for member in result.snapshot.members
        ]

    assert file_names == [
        "01-screening.pdf",
        "02-lab.pdf",
        "03-history.pdf",
    ]


def test_preview_reports_matching_staged_snapshot_before_confirmation(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    _first_preview, first = confirm_full(
        env,
        [pdf(b"one", name="01-screening.pdf"), pdf(b"two", name="02-lab.pdf")],
        key="key-matching-candidate",
    )

    repeated = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"one", name="01-screening.pdf"), pdf(b"two", name="02-lab.pdf")],
        created_by="tester",
    )

    assert repeated.matching_snapshot_id == first.evidence_snapshot_id
    assert repeated.matching_snapshot_status == SnapshotStatus.STAGED


def test_preview_matches_whole_set_despite_reordered_files_and_baseline_omission(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    activate_full(
        env,
        [pdf(b"legacy", name="00-legacy.pdf")],
        key="key-matching-baseline",
    )
    _first_preview, first = confirm_full(
        env,
        [pdf(b"one", name="01-screening.pdf"), pdf(b"two", name="02-lab.pdf")],
        key="key-matching-with-omission",
    )

    repeated = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"two", name="02-lab.pdf"), pdf(b"one", name="01-screening.pdf")],
        created_by="tester",
    )

    assert any(
        item.status == UploadItemStatus.FULL_SNAPSHOT_OMISSION
        for item in repeated.items
    )
    assert repeated.matching_snapshot_id == first.evidence_snapshot_id
    assert repeated.matching_snapshot_status == SnapshotStatus.STAGED
    with env["factory"]() as session:
        persisted = EvidenceSnapshotRepository(session).get(first.evidence_snapshot_id)
        file_names = [
            session.get(
                SourceDocumentVersionV2Record,
                member.source_document_version_id,
            ).file_name
            for member in persisted.members
        ]
    assert file_names == ["01-screening.pdf", "02-lab.pdf"]


# ---------------------------------------------------------------------------
# 有效基准语义（Slice 4.2 修订）：只有 ACTIVE 快照才是有效前序/比较基线
# ---------------------------------------------------------------------------


def test_incremental_requires_active_base_not_candidate(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    # 只有 STAGED 候选（尚未激活，指针为空）：补充资料预览必须拒绝。
    confirm_full(env, [pdf(b"X")], key="key-candidate")
    with raises_upload_error("NO_EFFECTIVE_SNAPSHOT"):
        service.create_preview(
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=episode_id,
            upload_mode=UploadMode.INCREMENTAL,
            base_revision=1,
            files=[pdf(b"W", name="new.pdf")],
            created_by="tester",
        )
    # 建立活动指针对后成为有效基准：补充资料预览绑定指针指向快照。
    _preview2, result = confirm_full(env, [pdf(b"Y", name="lab.pdf")], key="key-cand2")
    _establish_active_pair(env, result.evidence_snapshot_id)
    with env["factory"]() as session:
        pointer = EpisodeRepository(session).get(episode_id).active_evidence_snapshot_id
    incremental = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.INCREMENTAL,
        base_revision=1,
        files=[pdf(b"W", name="new.pdf")],
        created_by="tester",
    )
    assert incremental.base_snapshot_id == pointer == result.evidence_snapshot_id


def test_confirm_stale_revision_blocks_noop_duplicate(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    # 首确认创建 STAGED 候选 S（成员集合 C）。
    confirm_full(env, [pdf(b"one")], key="key-first")
    assert count(env, "evidence_snapshots_v2") == 1
    # 同成员集合的新预览（新幂等键）本来会命中重复 no-op，但预览生成后审核节点
    # 修订号被推进：新确认必须先因旧修订被拒绝，不能命中 no-op。
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"one")],
        created_by="tester",
    )
    with env["factory"]() as session, session.begin():
        from app.domain.contracts.enums import ReviewStage

        EpisodeRepository(session).update(
            episode_id,
            expected_revision=1,
            changes={"stage": ReviewStage.SCREENING},
        )
    with raises_upload_error("STALE_BASE_REVISION"):
        service.confirm(make_command(preview, idempotency_key="key-stale-noop"), created_by="tester")
    # 不产生新快照/新确认记录/新 Job。
    assert count(env, "evidence_snapshots_v2") == 1
    assert count(env, "evidence_upload_commits") == 1
    assert jobs(env) == 1


def test_confirm_stale_active_base_blocks_noop_duplicate(env):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    base_s1 = activate_full(env, [pdf(b"one")], key="key-s1")
    # 同成员集合预览基于 S1；随后活动基准切换为 S2（S1 不再是有效基准）。
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"one")],
        created_by="tester",
    )
    assert preview.base_snapshot_id == base_s1.evidence_snapshot_id
    activate_full(env, [pdf(b"two", name="lab.pdf")], key="key-s2")
    # 该预览的成员集合与 S1 相同（full 重新纳入同内容），本可命中 no-op，但活动
    # 基准已变化：必须因基准变化被拒绝。
    with raises_upload_error("STALE_BASE_REVISION"):
        service.confirm(make_command(preview, idempotency_key="key-stale-base-noop"), created_by="tester")
    assert count(env, "evidence_snapshots_v2") == 2


def test_concurrent_incremental_confirm_single_snapshot_and_job(env):
    """同基准（ACTIVE）两个并发补充预览：收敛到同一候选，只有一个 Job。"""
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    base = activate_full(env, [pdf(b"X")], key="key-base")
    files = [pdf(b"W", name="new.pdf")]
    p1 = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.INCREMENTAL,
        base_revision=1,
        files=files,
        created_by="tester",
    )
    p2 = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.INCREMENTAL,
        base_revision=1,
        files=files,
        created_by="tester",
    )
    assert p1.base_snapshot_id == p2.base_snapshot_id == base.evidence_snapshot_id
    base_jobs = jobs(env)  # 激活基准本身产生一个 Job
    results: list = []
    errors: list = []

    def run(preview, key):
        try:
            results.append(
                service.confirm(make_command(preview, idempotency_key=key), created_by="tester")
            )
        except Exception as exc:  # noqa: BLE001 - 并发反例测试收集任意失败
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(run, p1, "key-inc-c1"),
            pool.submit(run, p2, "key-inc-c2"),
        ]
        for future in futures:
            future.result(timeout=60)

    assert len(results) == 2 and not errors, f"并发增量确认失败：{errors}"
    assert sum(1 for r in results if r.created) == 1
    assert sum(1 for r in results if r.duplicate) == 1
    assert results[0].evidence_snapshot_id == results[1].evidence_snapshot_id
    assert count(env, "evidence_snapshots_v2") == 2  # ACTIVE 基准 + 一个候选
    assert jobs(env) - base_jobs == 1  # 并发增量确认只创建一个 Job


# ---------------------------------------------------------------------------
# 取消清理故障注入（Slice 4.2 修订）：失败必须诚实且可重试
# ---------------------------------------------------------------------------


def test_cancel_cleanup_failure_is_honest_and_retryable(env, monkeypatch):
    service = env["service"]
    project_id, subject_id, episode_id = env["scope"]
    preview = service.create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        base_revision=1,
        files=[pdf(b"one")],
        created_by="tester",
    )
    staging_dir = env["paths"].root / f"staging/{preview.preview_id}"
    assert staging_dir.is_dir()
    real_remove = service._remove_staging_dir
    calls = {"n": 0}

    def flaky_remove(preview_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return False  # 模拟首次清理失败/残留
        return real_remove(preview_id)

    monkeypatch.setattr(service, "_remove_staging_dir", flaky_remove)
    with raises_upload_error("PREVIEW_CLEANUP_FAILED"):
        service.cancel(preview.preview_id, actor="tester")
    # 不静默报告已彻底取消：保持 cancel_pending（可重试），暂存目录仍存在。
    with env["factory"]() as session:
        row = session.get(EvidenceUploadPreviewRecord, preview.preview_id)
        assert row.status == UploadPreviewStatus.CANCEL_PENDING.value
    assert staging_dir.is_dir()
    # 取消待清理的预览不允许确认（残缺暂存不得进入确认）。
    with raises_upload_error("PREVIEW_STATE_CONFLICT"):
        service.confirm(make_command(preview), created_by="tester")
    assert count(env, "evidence_snapshots_v2") == 0
    # 重试取消：真实清理执行并核实，转为终态 cancelled，目录消失。
    monkeypatch.setattr(service, "_remove_staging_dir", real_remove)
    cancelled = service.cancel(preview.preview_id, actor="tester")
    assert cancelled.status == UploadPreviewStatus.CANCELLED
    assert not staging_dir.exists()
    # 共享 blob 与历史不受影响。
    assert count(env, "source_blobs") == 0
    assert count(env, "evidence_snapshots_v2") == 0
    assert count(env, "evidence_upload_commits") == 0


# ---------------------------------------------------------------------------
# 格式探测反例：内容优先于扩展名，压缩包不得伪装
# ---------------------------------------------------------------------------


def test_detect_file_format_content_beats_extension():
    # 扩展名与魔数冲突：按真实内容分类。
    assert detect_file_format("a.txt", b"%PDF-1.4 x").kind == "pdf"
    assert detect_file_format("a.pdf", b"\xff\xd8\xff\xe0").kind == "image"
    # 普通 ZIP 伪装 DOCX：真实内容没有 OOXML 标记 -> 压缩包（不支持），不静默接受。
    evil = detect_file_format("evil.docx", b"PK\x03\x04plain-zip-entry")
    assert not evil.supported and evil.kind == "archive", evil
    # DOCX 伪装 ZIP：真实内容含 OOXML 清单/部件 -> docx（受支持），内容优先。
    docx = detect_file_format("fake.zip", b"PK\x03\x04[Content_Types].xmlword/document.xml")
    assert docx.supported and docx.kind == "docx", docx
    # 受支持扩展名但不可识别内容：诚实标记无法读取，不按扩展名接受。
    assert detect_file_format("report.pdf", b"garbage bytes").kind == "unreadable"
    assert detect_file_format("a.docx", b"plain text without signature").kind == "unreadable"
