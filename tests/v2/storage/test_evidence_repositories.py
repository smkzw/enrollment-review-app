"""Phase 4 证据快照仓储确定性测试（Slice 4.1，worker_02）。

以临时库 ``Base.metadata.create_all`` 建表（不依赖尚未落地的迁移 0008），播种一份
Phase 3 fixture 作为项目/受试者/审核节点作用域基座，然后证明：

- 内容寻址去重与尺寸冲突拒绝（BlobRepository）；
- 逻辑资料版本作用域门禁与显式替代线性链（SourceDocumentRepository）；
- 元数据修订追加链（SourceDocumentMetadataRevisionRepository）；
- 证据快照作用域门禁、前序链无环、增量继承/显式替代/新增语义、集合哈希、
  重复集合 no-op、不可变 + 三方交叉校验、候选状态机（EvidenceSnapshotRepository）。

每个用例构造对象时用确定性 ID 与固定 UTC 时间，结果只由领域逻辑决定。
"""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.domain.contracts.enums import SnapshotMemberOrigin, SnapshotStatus, UploadMode
from app.domain.contracts.evidence_ingestion import (
    EvidenceSnapshot,
    EvidenceSnapshotMember,
    SourceBlob,
    SourceDocumentMetadataRevision,
    SourceDocumentVersion,
)
from app.domain.publication import evidence_snapshot_collection_hash
from app.storage import evidence_repositories as er
from app.storage.evidence_models import (
    EvidenceSnapshotMemberRecord,
    EvidenceSnapshotStatusEventRecord,
    EvidenceSnapshotV2Record,
    SourceBlobRecord,
    SourceDocumentMetadataRevisionRecord,
)
from app.storage.repositories import (
    DuplicateRecordError,
    InvalidReferenceError,
    ScopeViolationError,
    _flush_guarded,
    persist_fixture,
)
from tests.v2.storage.test_repositories_roundtrip import FIXTURES

FIXED_UTC = datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def evidence_engine(tmp_path, monkeypatch):
    monkeypatch.setenv("ENROLLMENT_V2_DATA_DIR", str(tmp_path / "data_v2"))
    from app.storage.config import resolve_data_paths
    from app.storage.db import Base, build_engine

    paths = resolve_data_paths()
    paths.ensure_directories()
    engine = build_engine(paths.db_path)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def seeded(evidence_engine):
    from app.storage.db import build_session_factory

    factory = build_session_factory(evidence_engine)
    with factory() as session:
        fixture = FIXTURES[0]
        persist_fixture(session, fixture)
        session.commit()
        yield session, fixture
        session.rollback()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def make_blob(
    content: bytes,
    media_type: str = "application/pdf",
    storage_ref: str | None = None,
) -> SourceBlob:
    digest = sha(content)
    return SourceBlob(
        source_blob_id=digest,
        sha256=digest,
        byte_size=len(content),
        media_type=media_type,
        storage_ref=storage_ref or f"blobs/{digest}",
        created_at=FIXED_UTC,
    )


def scope_of(fixture) -> tuple[str, str, str]:
    return (
        fixture.project.project_id,
        fixture.subject.subject_id,
        fixture.review_episode.review_episode_id,
    )


def make_version(
    *,
    version_id: str,
    logical_id: str,
    blob_sha: str,
    project_id: str,
    subject_id: str,
    episode_id: str,
    version_number: int,
    supersedes_version_id: str | None = None,
    file_name: str = "report.pdf",
) -> SourceDocumentVersion:
    return SourceDocumentVersion(
        source_document_version_id=version_id,
        logical_document_id=logical_id,
        source_blob_sha256=blob_sha,
        file_name=file_name,
        media_type="application/pdf",
        page_count=3,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        version_number=version_number,
        supersedes_version_id=supersedes_version_id,
        created_at=FIXED_UTC,
        created_by="tester",
    )


def make_member(
    *, member_id: str, snapshot_id: str, logical_id: str, version_id: str, origin: SnapshotMemberOrigin
) -> EvidenceSnapshotMember:
    return EvidenceSnapshotMember(
        member_id=member_id,
        snapshot_id=snapshot_id,
        logical_document_id=logical_id,
        source_document_version_id=version_id,
        origin=origin,
    )


def make_snapshot(
    *,
    snapshot_id: str,
    project_id: str,
    subject_id: str,
    episode_id: str,
    upload_mode: UploadMode,
    members: list[EvidenceSnapshotMember],
    prior_snapshot_id: str | None = None,
    comparison_snapshot_id: str | None = None,
    status: SnapshotStatus = SnapshotStatus.STAGED,
) -> EvidenceSnapshot:
    collection = evidence_snapshot_collection_hash(
        members=[(m.logical_document_id, m.source_document_version_id) for m in members]
    )
    return EvidenceSnapshot(
        evidence_snapshot_id=snapshot_id,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=upload_mode,
        prior_snapshot_id=prior_snapshot_id,
        comparison_snapshot_id=comparison_snapshot_id,
        members=members,
        collection_sha256=collection,
        status=status,
        created_at=FIXED_UTC,
        created_by="tester",
    )


# ---------------------------------------------------------------------------
# BlobRepository：内容寻址去重
# ---------------------------------------------------------------------------


def test_blob_dedupe_and_roundtrip(seeded):
    session, _ = seeded
    repo = er.BlobRepository(session)
    blob = make_blob(b"identical bytes")
    assert repo.get_or_create_by_sha256(blob) == blob
    assert session.execute(
        select(func.count()).select_from(SourceBlobRecord)
    ).scalar_one() == 1
    # 同内容重复上传：no-op 返回既有记录，不新增行。
    second = make_blob(b"identical bytes")
    assert repo.get_or_create_by_sha256(second) == blob
    assert session.execute(
        select(func.count()).select_from(SourceBlobRecord)
    ).scalar_one() == 1
    assert repo.get(blob.source_blob_id) == blob


def test_blob_size_mismatch_rejected(seeded):
    session, _ = seeded
    repo = er.BlobRepository(session)
    repo.get_or_create_by_sha256(make_blob(b"aaaa"))
    with pytest.raises(er.DuplicateBlobMismatchError):
        repo.get_or_create_by_sha256(
            SourceBlob(
                source_blob_id=sha(b"aaaa"),
                sha256=sha(b"aaaa"),
                byte_size=999,
                media_type="application/pdf",
                storage_ref="blobs/x",
                created_at=FIXED_UTC,
            )
        )


def test_blob_deduplication_is_serialized_across_sessions(seeded):
    session, _fixture = seeded
    from app.storage.db import build_session_factory

    session.commit()
    factory = build_session_factory(session.get_bind())

    def submit(index: int) -> str:
        blob = make_blob(b"concurrent-blob", storage_ref=f"blobs/race-{index}")
        with factory() as current:
            result = er.BlobRepository(current).get_or_create_by_sha256(blob)
            current.commit()
            return result.storage_ref

    with ThreadPoolExecutor(max_workers=4) as pool:
        storage_refs = list(pool.map(submit, range(4)))

    assert len(set(storage_refs)) == 1
    assert session.execute(select(func.count()).select_from(SourceBlobRecord)).scalar_one() == 1


# ---------------------------------------------------------------------------
# SourceDocumentRepository：作用域门禁 + 显式替代线性链
# ---------------------------------------------------------------------------


def _seed_docs(session, fixture) -> tuple[str, str, str]:
    project_id, subject_id, episode_id = scope_of(fixture)
    blob_repo = er.BlobRepository(session)
    doc_repo = er.SourceDocumentRepository(session)
    blob_repo.get_or_create_by_sha256(make_blob(b"content-A", media_type="application/pdf"))
    blob_repo.get_or_create_by_sha256(make_blob(b"content-B", media_type="application/pdf"))
    blob_repo.get_or_create_by_sha256(make_blob(b"content-C", media_type="application/pdf"))
    a = blob_repo.get_or_none(sha(b"content-A"))
    b = blob_repo.get_or_none(sha(b"content-B"))
    c = blob_repo.get_or_none(sha(b"content-C"))
    va = doc_repo.create_version(
        make_version(
            version_id="docA-v1", logical_id="logical-A", blob_sha=a.sha256,
            project_id=project_id, subject_id=subject_id, episode_id=episode_id, version_number=1,
        )
    )
    vb = doc_repo.create_version(
        make_version(
            version_id="docB-v1", logical_id="logical-B", blob_sha=b.sha256,
            project_id=project_id, subject_id=subject_id, episode_id=episode_id, version_number=1,
        )
    )
    vc = doc_repo.create_version(
        make_version(
            version_id="docC-v1", logical_id="logical-C", blob_sha=c.sha256,
            project_id=project_id, subject_id=subject_id, episode_id=episode_id, version_number=1,
        )
    )
    return va.source_document_version_id, vb.source_document_version_id, vc.source_document_version_id


def test_doc_version_scope_gates(seeded):
    session, fixture = seeded
    _, _, episode_id = scope_of(fixture)
    blob_repo = er.BlobRepository(session)
    doc_repo = er.SourceDocumentRepository(session)
    blob_repo.get_or_create_by_sha256(make_blob(b"scope-content"))
    blob = blob_repo.get_or_none(sha(b"scope-content"))
    # blob 不存在
    with pytest.raises(InvalidReferenceError):
        doc_repo.create_version(
            make_version(
                version_id="v-no-blob", logical_id="L", blob_sha="0" * 64,
                project_id="p", subject_id="s", episode_id=episode_id, version_number=1,
            )
        )
    # subject 超出 episode
    with pytest.raises(ScopeViolationError):
        doc_repo.create_version(
            make_version(
                version_id="v-wrong-subject", logical_id="L", blob_sha=blob.sha256,
                project_id="p", subject_id="other-subject", episode_id=episode_id, version_number=1,
            )
        )
    # project 与 subject 不一致
    with pytest.raises(ScopeViolationError):
        doc_repo.create_version(
            make_version(
                version_id="v-wrong-project", logical_id="L", blob_sha=blob.sha256,
                project_id="p", subject_id=fixture.subject.subject_id, episode_id=episode_id,
                version_number=1,
            )
        )


def test_doc_version_roundtrip_and_list(seeded):
    session, fixture = seeded
    doc_repo = er.SourceDocumentRepository(session)
    a, b, c = _seed_docs(session, fixture)
    got = doc_repo.get(a)
    assert got.source_document_version_id == a
    assert got.logical_document_id == "logical-A"
    project_id, subject_id, episode_id = scope_of(fixture)
    listed = doc_repo.list_by_scope(
        project_id=project_id, subject_id=subject_id, review_episode_id=episode_id
    )
    assert {v.source_document_version_id for v in listed} == {a, b, c}


def test_explicit_supersession_linear_chain(seeded):
    session, fixture = seeded
    doc_repo = er.SourceDocumentRepository(session)
    a, _, _ = _seed_docs(session, fixture)
    project_id, subject_id, episode_id = scope_of(fixture)
    # v2 必须显式替代前序
    with pytest.raises(ValidationError, match="非首版本必须显式替代"):
        make_version(
            version_id="docA-v2-no-sup", logical_id="logical-A", blob_sha=sha(b"content-A"),
            project_id=project_id, subject_id=subject_id, episode_id=episode_id,
            version_number=2, supersedes_version_id=None,
        )
    # 显式替代必须指向同一逻辑资料
    with pytest.raises(er.SnapshotSupersessionError):
        doc_repo.create_version(
            make_version(
                version_id="docA-v2-wrong-logic", logical_id="logical-A",
                blob_sha=sha(b"content-A"), project_id=project_id, subject_id=subject_id,
                episode_id=episode_id, version_number=2, supersedes_version_id="docB-v1",
            )
        )
    # 版本号必须紧邻前序
    with pytest.raises(er.SnapshotSupersessionError):
        doc_repo.create_version(
            make_version(
                version_id="docA-v3-skip", logical_id="logical-A", blob_sha=sha(b"content-A"),
                project_id=project_id, subject_id=subject_id, episode_id=episode_id,
                version_number=3, supersedes_version_id=a,
            )
        )
    # 合法 v2
    v2 = doc_repo.create_version(
        make_version(
            version_id="docA-v2", logical_id="logical-A", blob_sha=sha(b"content-A"),
            project_id=project_id, subject_id=subject_id, episode_id=episode_id,
            version_number=2, supersedes_version_id=a,
        )
    )
    assert v2.supersedes_version_id == a
    # 重复 (episode, logical, version)：链头校验先于唯一约束拒绝（已存在的
    # docA-v2 已成为链头，任何再指向前序的 v2 都违反“必须替代当前链头"）。
    with pytest.raises(er.SnapshotSupersessionError):
        doc_repo.create_version(
            make_version(
                version_id="docA-v2-dup", logical_id="logical-A", blob_sha=sha(b"content-A"),
                project_id=project_id, subject_id=subject_id, episode_id=episode_id,
                version_number=2, supersedes_version_id=a,
            )
        )
    # 显式替代必须指向链头：v3 替代 v1 而链头是 v2 -> 拒绝
    with pytest.raises(er.SnapshotSupersessionError):
        doc_repo.create_version(
            make_version(
                version_id="docA-v3-not-head", logical_id="logical-A",
                blob_sha=sha(b"content-A"), project_id=project_id, subject_id=subject_id,
                episode_id=episode_id, version_number=3, supersedes_version_id=a,
            )
        )


def test_document_version_predecessor_drift_is_rejected_on_read(seeded):
    session, fixture = seeded
    doc_repo = er.SourceDocumentRepository(session)
    _seed_docs(session, fixture)
    row = session.get(er.SourceDocumentVersionV2Record, "docA-v1")
    assert row is not None
    # The predecessor column is intentionally not an FK; update both mirrors to
    # simulate a database-level corruption that a plain ORM read would accept.
    version = doc_repo.get("docA-v1")
    corrupted = version.model_copy(
        update={"version_number": 2, "supersedes_version_id": "missing-version"}
    )
    payload_json, payload_sha256 = er.encode_contract(corrupted)
    row.version_number = 2
    row.supersedes_version_id = "missing-version"
    row.payload_json = payload_json
    row.payload_sha256 = payload_sha256
    _flush_guarded(session)
    with pytest.raises(InvalidReferenceError):
        doc_repo.get("docA-v1")


# ---------------------------------------------------------------------------
# SourceDocumentMetadataRevisionRepository：元数据修订追加链
# ---------------------------------------------------------------------------


def test_metadata_revision_chain(seeded):
    session, fixture = seeded
    meta_repo = er.SourceDocumentMetadataRevisionRepository(session)
    a, _, _ = _seed_docs(session, fixture)

    def rev(revision_id: str, rev: int, supersedes: str | None = None) -> SourceDocumentMetadataRevision:
        return SourceDocumentMetadataRevision(
            metadata_revision_id=revision_id,
            source_document_version_id=a,
            document_type="lab",
            source_party="center",
            reason="initial",
            is_auto_suggestion=True,
            supersedes_metadata_revision_id=supersedes,
            revision=rev,
            created_at=FIXED_UTC,
            created_by="tester",
        )

    meta_repo.append(rev("m1", 1))
    # 第二份 revision 1 拒绝
    with pytest.raises(DuplicateRecordError):
        meta_repo.append(rev("m1-dup", 1))
    # revision 2 引用不存在的前序修订拒绝（"无前序引用"由合同层校验）
    with pytest.raises(InvalidReferenceError):
        meta_repo.append(rev("m2-bad-prev", 2, supersedes="nonexistent-rev"))
    # revision 2 必须紧邻前序
    with pytest.raises(InvalidReferenceError):
        meta_repo.append(
            SourceDocumentMetadataRevision(
                metadata_revision_id="m3-skip", source_document_version_id=a,
                document_type="lab", source_party="center", reason="x",
                is_auto_suggestion=False, supersedes_metadata_revision_id="m1",
                revision=3, created_at=FIXED_UTC, created_by="tester",
            )
        )
    meta_repo.append(rev("m2", 2, supersedes="m1"))
    chain = meta_repo.list_chain(a)
    assert [r.revision for r in chain] == [1, 2]
    head = meta_repo.head(a)
    assert head is not None and head.metadata_revision_id == "m2"
    assert meta_repo.get("m1").revision == 1


def test_metadata_reason_mirror_drift_is_rejected(seeded):
    session, fixture = seeded
    document_id, _, _ = _seed_docs(session, fixture)
    meta_repo = er.SourceDocumentMetadataRevisionRepository(session)
    meta_repo.append(
        SourceDocumentMetadataRevision(
            metadata_revision_id="m-reason",
            source_document_version_id=document_id,
            document_type="lab",
            source_party="center",
            reason="initial",
            is_auto_suggestion=True,
            created_at=FIXED_UTC,
            created_by="tester",
        )
    )
    row = session.get(SourceDocumentMetadataRevisionRecord, "m-reason")
    assert row is not None
    row.reason = "tampered"
    _flush_guarded(session)
    with pytest.raises(er.PersistedContractInvalid):
        meta_repo.get("m-reason")


def test_metadata_predecessor_drift_is_rejected_on_read(seeded):
    session, fixture = seeded
    document_id, _, _ = _seed_docs(session, fixture)
    meta_repo = er.SourceDocumentMetadataRevisionRepository(session)
    initial = SourceDocumentMetadataRevision(
        metadata_revision_id="m-chain-1",
        source_document_version_id=document_id,
        document_type="lab",
        source_party="center",
        reason="initial",
        is_auto_suggestion=True,
        created_at=FIXED_UTC,
        created_by="tester",
    )
    meta_repo.append(initial)
    followup = SourceDocumentMetadataRevision(
        metadata_revision_id="m-chain-2",
        source_document_version_id=document_id,
        document_type="lab",
        source_party="center",
        reason="corrected",
        is_auto_suggestion=False,
        supersedes_metadata_revision_id=initial.metadata_revision_id,
        revision=2,
        created_at=FIXED_UTC,
        created_by="tester",
    )
    meta_repo.append(followup)
    row = session.get(SourceDocumentMetadataRevisionRecord, "m-chain-2")
    assert row is not None
    corrupted = followup.model_copy(
        update={"supersedes_metadata_revision_id": "missing-metadata"}
    )
    payload_json, payload_sha256 = er.encode_contract(corrupted)
    row.supersedes_metadata_revision_id = "missing-metadata"
    row.payload_json = payload_json
    row.payload_sha256 = payload_sha256
    _flush_guarded(session)
    with pytest.raises(InvalidReferenceError):
        meta_repo.get("m-chain-2")


def test_metadata_revision_cannot_branch_from_stale_head(seeded):
    """同一元数据前序只能有一个后继，旧链头不能再次分叉。"""
    session, fixture = seeded
    document_id, _, _ = _seed_docs(session, fixture)
    repo = er.SourceDocumentMetadataRevisionRepository(session)
    initial = SourceDocumentMetadataRevision(
        metadata_revision_id="m-branch-1",
        source_document_version_id=document_id,
        document_type="lab",
        source_party="center",
        reason="initial",
        is_auto_suggestion=True,
        created_at=FIXED_UTC,
        created_by="tester",
    )
    repo.append(initial)
    repo.append(
        initial.model_copy(
            update={
                "metadata_revision_id": "m-branch-2",
                "revision": 2,
                "supersedes_metadata_revision_id": "m-branch-1",
                "reason": "first successor",
            }
        )
    )
    with pytest.raises(InvalidReferenceError, match="当前链头"):
        repo.append(
            initial.model_copy(
                update={
                    "metadata_revision_id": "m-branch-3",
                    "revision": 2,
                    "supersedes_metadata_revision_id": "m-branch-1",
                    "reason": "branch",
                }
            )
        )


# ---------------------------------------------------------------------------
# EvidenceSnapshotRepository：full / incremental / 门禁 / no-op / 不可变 / 状态机
# ---------------------------------------------------------------------------


def _seed_full_snapshot(session, fixture, snapshot_id="snap-full-1") -> EvidenceSnapshot:
    project_id, subject_id, episode_id = scope_of(fixture)
    a, b, c = _seed_docs(session, fixture)
    snapshot = make_snapshot(
        snapshot_id=snapshot_id,
        project_id=project_id,
        subject_id=subject_id,
        episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        members=[
            make_member(member_id="mem-a1", snapshot_id=snapshot_id, logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.ADDED),
            make_member(member_id="mem-b1", snapshot_id=snapshot_id, logical_id="logical-B",
                        version_id=b, origin=SnapshotMemberOrigin.ADDED),
        ],
    )
    return er.EvidenceSnapshotRepository(session).create_full(snapshot)


def _activate_snapshot(session, snapshot_id: str) -> EvidenceSnapshot:
    """把候选快照标记为 ACTIVE（测试脚手架，模拟 Slice 4.4 激活后的状态）。

    直接改写快照 payload/列状态为 ACTIVE（无状态事件，读取时以 fallback 状态
    为准），不实现激活 API/ActivationEvent。
    """
    from app.storage.codecs import encode_contract

    repo = er.EvidenceSnapshotRepository(session)
    contract = repo.get(snapshot_id)
    activated = contract.model_copy(update={"status": SnapshotStatus.ACTIVE})
    payload_json, payload_sha256 = encode_contract(activated)
    row = session.get(EvidenceSnapshotV2Record, snapshot_id)
    row.status = SnapshotStatus.ACTIVE.value
    row.payload_json = payload_json
    row.payload_sha256 = payload_sha256
    _flush_guarded(session)
    return activated


def test_snapshot_full_roundtrip(seeded):
    session, fixture = seeded
    snap = _seed_full_snapshot(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    got = repo.get(snap.evidence_snapshot_id)
    assert got.evidence_snapshot_id == snap.evidence_snapshot_id
    assert got.status == SnapshotStatus.STAGED
    assert len(got.members) == 2
    assert repo.list_by_episode(fixture.review_episode.review_episode_id) == [got]


def test_snapshot_scope_gates(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    a, _, _ = _seed_docs(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    # subject 超出 episode
    bad = make_snapshot(
        snapshot_id="snap-bad-subject", project_id=project_id, subject_id="other-subject",
        episode_id=episode_id, upload_mode=UploadMode.FULL,
        members=[make_member(member_id="m", snapshot_id="snap-bad-subject", logical_id="logical-A",
                             version_id=a, origin=SnapshotMemberOrigin.ADDED)],
    )
    with pytest.raises(ScopeViolationError):
        repo.create_full(bad)
    # 成员版本超出快照作用域：先建立 subject-other（外键目标），再以 ORM 写入
    # 一个 subject 不同的资料版本（绕过仓储作用域门禁，专测快照成员级作用域校验）。

    from app.storage.codecs import encode_contract
    from app.storage.evidence_models import SourceDocumentVersionV2Record
    from app.storage.models import SubjectRecord

    now_naive = FIXED_UTC.replace(tzinfo=None)
    session.add(
        SubjectRecord(
            subject_id="subject-other", subject_code="OTHER-1", project_id=project_id,
            revision=1, created_at=now_naive, updated_at=now_naive,
            payload_json="{}", payload_sha256="0" * 64,
        )
    )
    _flush_guarded(session)  # 先落 subject 行，避免全量元数据的全局 FK 排序把版本插到其前
    out_version = make_version(
        version_id="docX-v1", logical_id="logical-X", blob_sha=sha(b"content-A"),
        project_id=project_id, subject_id="subject-other", episode_id=episode_id, version_number=1,
    )
    payload_json, payload_sha256 = encode_contract(out_version)
    session.add(
        SourceDocumentVersionV2Record(
            source_document_version_id="docX-v1",
            logical_document_id="logical-X",
            source_blob_sha256=out_version.source_blob_sha256,
            file_name=out_version.file_name,
            media_type=out_version.media_type,
            page_count=out_version.page_count,
            project_id=project_id,
            subject_id="subject-other",
            review_episode_id=episode_id,
            version_number=1,
            supersedes_version_id=None,
            created_by="tester",
            created_at=FIXED_UTC,
            payload_json=payload_json,
            payload_sha256=payload_sha256,
        )
    )
    bad_member = make_snapshot(
        snapshot_id="snap-bad-member", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.FULL,
        members=[make_member(member_id="m2", snapshot_id="snap-bad-member", logical_id="logical-X",
                             version_id="docX-v1", origin=SnapshotMemberOrigin.ADDED)],
    )
    with pytest.raises(ScopeViolationError):
        repo.create_full(bad_member)


def test_snapshot_collection_hash_defense(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    a, _, _ = _seed_docs(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    members = [
        make_member(member_id="m", snapshot_id="snap-hash", logical_id="logical-A",
                    version_id=a, origin=SnapshotMemberOrigin.ADDED)
    ]
    valid = make_snapshot(
        snapshot_id="snap-hash", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.FULL, members=members,
    )
    # 绕过合同校验（model_copy 不重跑 validator），只测仓储自身的集合哈希重算门禁
    tampered = valid.model_copy(update={"collection_sha256": "0" * 64})
    with pytest.raises(er.SnapshotSupersessionError):
        repo.create_full(tampered)


def test_snapshot_requires_staged(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    a, _, _ = _seed_docs(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    ready = make_snapshot(
        snapshot_id="snap-ready-in", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.FULL,
        members=[make_member(member_id="m", snapshot_id="snap-ready-in", logical_id="logical-A",
                             version_id=a, origin=SnapshotMemberOrigin.ADDED)],
        status=SnapshotStatus.READY,
    )
    with pytest.raises(InvalidReferenceError):
        repo.create_full(ready)


def test_snapshot_duplicate_full_noop(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    a, b, _ = _seed_docs(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    original = make_snapshot(
        snapshot_id="snap-full-orig", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.FULL,
        members=[
            make_member(member_id="oa", snapshot_id="snap-full-orig", logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.ADDED),
            make_member(member_id="ob", snapshot_id="snap-full-orig", logical_id="logical-B",
                        version_id=b, origin=SnapshotMemberOrigin.ADDED),
        ],
    )
    repo.create_full(original)
    # 同作用域/上传方式/活动成员集合 -> no-op 返回既有快照，不新增行
    dup = make_snapshot(
        snapshot_id="snap-full-dup", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.FULL,
        members=[
            make_member(member_id="dm-a", snapshot_id="snap-full-dup", logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.ADDED),
            make_member(member_id="dm-b", snapshot_id="snap-full-dup", logical_id="logical-B",
                        version_id=b, origin=SnapshotMemberOrigin.ADDED),
        ],
    )
    returned = repo.create_full(dup)
    assert returned.evidence_snapshot_id == "snap-full-orig"
    assert repo.get("snap-full-orig").evidence_snapshot_id == "snap-full-orig"
    count = session.execute(
        select(func.count()).select_from(EvidenceSnapshotV2Record)
    ).scalar_one()
    assert count == 1


def test_snapshot_members_immutable_three_way(seeded):
    session, fixture = seeded
    snap = _seed_full_snapshot(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    assert repo.get(snap.evidence_snapshot_id).evidence_snapshot_id == snap.evidence_snapshot_id
    # 物理篡改成员表 origin 列 -> 读取拒绝（成员表与 payload 三方不一致）
    row = session.execute(
        select(EvidenceSnapshotMemberRecord).where(
            EvidenceSnapshotMemberRecord.snapshot_id == snap.evidence_snapshot_id
        )
    ).scalars().first()
    row.origin = SnapshotMemberOrigin.REPLACED.value
    _flush_guarded(session)
    with pytest.raises(er.PersistedContractInvalid):
        repo.get(snap.evidence_snapshot_id)


def test_snapshot_member_payload_drift_is_rejected_by_find_by_collection(seeded):
    session, fixture = seeded
    snap = _seed_full_snapshot(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    row = session.execute(
        select(EvidenceSnapshotMemberRecord).where(
            EvidenceSnapshotMemberRecord.snapshot_id == snap.evidence_snapshot_id
        )
    ).scalars().first()
    assert row is not None
    payload = json.loads(row.payload_json)
    payload["origin"] = SnapshotMemberOrigin.REPLACED.value
    row.payload_json = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    row.payload_sha256 = sha(row.payload_json.encode("utf-8"))
    _flush_guarded(session)
    with pytest.raises(er.PersistedContractInvalid):
        repo.find_by_collection(
            project_id=snap.project_id,
            subject_id=snap.subject_id,
            review_episode_id=snap.review_episode_id,
            upload_mode=snap.upload_mode,
            collection_sha256=snap.collection_sha256,
        )


def test_snapshot_member_identity_drift_is_rejected(seeded):
    session, fixture = seeded
    snap = _seed_full_snapshot(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    row = session.execute(
        select(EvidenceSnapshotMemberRecord).where(
            EvidenceSnapshotMemberRecord.snapshot_id == snap.evidence_snapshot_id
        )
    ).scalars().first()
    assert row is not None
    payload = json.loads(row.payload_json)
    payload["member_id"] = "drifted-member-id"
    row.member_id = "drifted-member-id"
    row.payload_json = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    row.payload_sha256 = sha(row.payload_json.encode("utf-8"))
    _flush_guarded(session)
    with pytest.raises(er.PersistedContractInvalid):
        repo.get(snap.evidence_snapshot_id)


def test_snapshot_comparison_members_are_rechecked_on_read(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    a, b, c = _seed_docs(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    baseline = make_snapshot(
        snapshot_id="snap-baseline-integrity",
        project_id=project_id,
        subject_id=subject_id,
        episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        members=[
            make_member(
                member_id="baseline-a",
                snapshot_id="snap-baseline-integrity",
                logical_id="logical-A",
                version_id=a,
                origin=SnapshotMemberOrigin.ADDED,
            ),
            make_member(
                member_id="baseline-b",
                snapshot_id="snap-baseline-integrity",
                logical_id="logical-B",
                version_id=b,
                origin=SnapshotMemberOrigin.ADDED,
            ),
        ],
    )
    repo.create_full(baseline)
    candidate = make_snapshot(
        snapshot_id="snap-comparison-integrity",
        project_id=project_id,
        subject_id=subject_id,
        episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        comparison_snapshot_id=baseline.evidence_snapshot_id,
        members=[
            make_member(
                member_id="candidate-a",
                snapshot_id="snap-comparison-integrity",
                logical_id="logical-A",
                version_id=a,
                origin=SnapshotMemberOrigin.ADDED,
            ),
            make_member(
                member_id="candidate-c",
                snapshot_id="snap-comparison-integrity",
                logical_id="logical-C",
                version_id=c,
                origin=SnapshotMemberOrigin.ADDED,
            ),
        ],
    )
    repo.create_full(candidate)
    assert repo.get(candidate.evidence_snapshot_id).evidence_snapshot_id == (
        candidate.evidence_snapshot_id
    )

    row = session.execute(
        select(EvidenceSnapshotMemberRecord).where(
            EvidenceSnapshotMemberRecord.snapshot_id == baseline.evidence_snapshot_id
        )
    ).scalars().first()
    assert row is not None
    payload = json.loads(row.payload_json)
    payload["origin"] = SnapshotMemberOrigin.REPLACED.value
    row.payload_json = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    row.payload_sha256 = sha(row.payload_json.encode("utf-8"))
    _flush_guarded(session)
    with pytest.raises(er.PersistedContractInvalid):
        repo.get(candidate.evidence_snapshot_id)


def test_snapshot_status_event_payload_and_mirror_drift_is_rejected(seeded):
    session, fixture = seeded
    snap = _seed_full_snapshot(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    repo.transition_status(
        snap.evidence_snapshot_id,
        event="worker_start",
        new_status=SnapshotStatus.PROCESSING,
        actor="worker",
        reason="start",
    )
    row = session.execute(
        select(EvidenceSnapshotStatusEventRecord).where(
            EvidenceSnapshotStatusEventRecord.snapshot_id == snap.evidence_snapshot_id
        )
    ).scalars().first()
    assert row is not None
    row.reason = "tampered"
    _flush_guarded(session)
    with pytest.raises(er.PersistedContractInvalid):
        repo.current_status(snap.evidence_snapshot_id)


def test_incremental_inherit_add_replace(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    a, b, c = _seed_docs(session, fixture)
    doc_repo = er.SourceDocumentRepository(session)
    repo = er.EvidenceSnapshotRepository(session)
    prior = make_snapshot(
        snapshot_id="snap-inc-prior", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.FULL,
        members=[
            make_member(member_id="p-a", snapshot_id="snap-inc-prior", logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.ADDED),
            make_member(member_id="p-b", snapshot_id="snap-inc-prior", logical_id="logical-B",
                        version_id=b, origin=SnapshotMemberOrigin.ADDED),
        ],
    )
    repo.create_full(prior)
    _activate_snapshot(session, prior.evidence_snapshot_id)
    # docB 显式替代为 v2
    b2 = doc_repo.create_version(
        make_version(
            version_id="docB-v2", logical_id="logical-B", blob_sha=sha(b"content-B"),
            project_id=project_id, subject_id=subject_id, episode_id=episode_id,
            version_number=2, supersedes_version_id=b,
        )
    )
    inc = make_snapshot(
        snapshot_id="snap-inc-1", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.INCREMENTAL,
        prior_snapshot_id="snap-inc-prior", comparison_snapshot_id="snap-inc-prior",
        members=[
            make_member(member_id="i-a", snapshot_id="snap-inc-1", logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.INHERITED),
            make_member(member_id="i-b", snapshot_id="snap-inc-1", logical_id="logical-B",
                        version_id=b2.source_document_version_id, origin=SnapshotMemberOrigin.REPLACED),
            make_member(member_id="i-c", snapshot_id="snap-inc-1", logical_id="logical-C",
                        version_id=c, origin=SnapshotMemberOrigin.ADDED),
        ],
    )
    saved = repo.create_incremental(inc)
    assert saved.evidence_snapshot_id == "snap-inc-1"
    got = repo.get("snap-inc-1")
    assert {m.logical_document_id for m in got.members} == {"logical-A", "logical-B", "logical-C"}


def test_incremental_new_logical_document_must_be_added(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    a, _, c = _seed_docs(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    prior = make_snapshot(
        snapshot_id="snap-origin-prior",
        project_id=project_id,
        subject_id=subject_id,
        episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        members=[
            make_member(
                member_id="p-a",
                snapshot_id="snap-origin-prior",
                logical_id="logical-A",
                version_id=a,
                origin=SnapshotMemberOrigin.ADDED,
            )
        ],
    )
    repo.create_full(prior)
    _activate_snapshot(session, prior.evidence_snapshot_id)
    invalid = make_snapshot(
        snapshot_id="snap-origin-invalid",
        project_id=project_id,
        subject_id=subject_id,
        episode_id=episode_id,
        upload_mode=UploadMode.INCREMENTAL,
        prior_snapshot_id=prior.evidence_snapshot_id,
        comparison_snapshot_id=prior.evidence_snapshot_id,
        members=[
            make_member(
                member_id="i-a",
                snapshot_id="snap-origin-invalid",
                logical_id="logical-A",
                version_id=a,
                origin=SnapshotMemberOrigin.INHERITED,
            ),
            make_member(
                member_id="i-c",
                snapshot_id="snap-origin-invalid",
                logical_id="logical-C",
                version_id=c,
                origin=SnapshotMemberOrigin.INHERITED,
            ),
        ],
    )
    with pytest.raises(er.SnapshotSupersessionError):
        repo.create_incremental(invalid)


def test_full_snapshot_comparison_baseline_must_exist_in_scope(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    a, _, _ = _seed_docs(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    snapshot = make_snapshot(
        snapshot_id="snap-comparison-missing",
        project_id=project_id,
        subject_id=subject_id,
        episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        comparison_snapshot_id="does-not-exist",
        members=[
            make_member(
                member_id="m-a",
                snapshot_id="snap-comparison-missing",
                logical_id="logical-A",
                version_id=a,
                origin=SnapshotMemberOrigin.ADDED,
            )
        ],
    )
    with pytest.raises(InvalidReferenceError):
        repo.create_full(snapshot)


def test_incremental_rejects_silent_drop(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    a, b, _ = _seed_docs(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    prior = make_snapshot(
        snapshot_id="snap-drop-prior", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.FULL,
        members=[
            make_member(member_id="p-a", snapshot_id="snap-drop-prior", logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.ADDED),
            make_member(member_id="p-b", snapshot_id="snap-drop-prior", logical_id="logical-B",
                        version_id=b, origin=SnapshotMemberOrigin.ADDED),
        ],
    )
    repo.create_full(prior)
    _activate_snapshot(session, prior.evidence_snapshot_id)
    # 增量只保留 logical-A，静默移除 logical-B -> 拒绝
    dropped = make_snapshot(
        snapshot_id="snap-drop-1", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.INCREMENTAL,
        prior_snapshot_id="snap-drop-prior", comparison_snapshot_id="snap-drop-prior",
        members=[
            make_member(member_id="d-a", snapshot_id="snap-drop-1", logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.INHERITED),
        ],
    )
    with pytest.raises(er.SnapshotSupersessionError):
        repo.create_incremental(dropped)


def test_incremental_scope_and_cycle_rejected(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    a, b, c = _seed_docs(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    prior = make_snapshot(
        snapshot_id="snap-cycle-prior", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.FULL,
        members=[
            make_member(member_id="p-a", snapshot_id="snap-cycle-prior", logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.ADDED),
        ],
    )
    repo.create_full(prior)
    # 前序快照超出作用域：复制 barrier 审核节点行形成第二个审核节点
    from app.storage.models import ReviewEpisodeRecord

    barrier = session.get(ReviewEpisodeRecord, episode_id)
    barrier_contract = fixture.review_episode.model_copy(
        update={"review_episode_id": "episode-other"}
    )
    barrier_payload, barrier_hash = er.encode_contract(barrier_contract)
    session.add(
        ReviewEpisodeRecord(
            review_episode_id="episode-other",
            subject_id=barrier.subject_id,
            project_id=barrier.project_id,
            rule_set_id=barrier.rule_set_id,
            rule_set_revision=barrier.rule_set_revision,
            study_phase=barrier.study_phase,
            stage=barrier.stage,
            protocol_version_id=barrier.protocol_version_id,
            evidence_snapshot_id=barrier.evidence_snapshot_id,
            anchor_dates_json=barrier.anchor_dates_json,
            due_at=barrier.due_at,
            revision=1,
            created_at=barrier.created_at,
            updated_at=barrier.updated_at,
                payload_json=barrier_payload,
                payload_sha256=barrier_hash,
            )
        )
    _flush_guarded(session)
    other_episode = make_snapshot(
        snapshot_id="snap-other-ep", project_id=project_id, subject_id=subject_id,
        episode_id="episode-other", upload_mode=UploadMode.INCREMENTAL,
        prior_snapshot_id="snap-cycle-prior", comparison_snapshot_id="snap-cycle-prior",
        members=[make_member(member_id="x", snapshot_id="snap-other-ep", logical_id="logical-A",
                             version_id=a, origin=SnapshotMemberOrigin.INHERITED)],
    )
    with pytest.raises(ScopeViolationError):
        repo.create_incremental(other_episode)

    # 前序链无环：先建立合法链 X(full) <- A(inc) <- B(inc)，再把 A 的前序改指 B，
    # 形成 A -> B -> A 环（payload 与列同步重编码，保持镜像一致），随后任何以 A
    # 为前序的增量都必须被无环门禁拒绝。每步集合严格增长，避免重复集合 no-op
    # 在到达无环门禁前短路。
    doc_repo = er.SourceDocumentRepository(session)
    d = doc_repo.create_version(
        make_version(
            version_id="docD-v1", logical_id="logical-D", blob_sha=sha(b"content-A"),
            project_id=project_id, subject_id=subject_id, episode_id=episode_id,
            version_number=1,
        )
    ).source_document_version_id
    e = doc_repo.create_version(
        make_version(
            version_id="docE-v1", logical_id="logical-E", blob_sha=sha(b"content-B"),
            project_id=project_id, subject_id=subject_id, episode_id=episode_id,
            version_number=1,
        )
    ).source_document_version_id
    x_full = make_snapshot(
        snapshot_id="snap-cycle-X", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.FULL,
        members=[
            make_member(member_id="x-a", snapshot_id="snap-cycle-X", logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.ADDED),
            make_member(member_id="x-b", snapshot_id="snap-cycle-X", logical_id="logical-B",
                        version_id=b, origin=SnapshotMemberOrigin.ADDED),
        ],
    )
    repo.create_full(x_full)
    _activate_snapshot(session, x_full.evidence_snapshot_id)
    inc_a = make_snapshot(
        snapshot_id="snap-cycle-A", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.INCREMENTAL,
        prior_snapshot_id="snap-cycle-X", comparison_snapshot_id="snap-cycle-X",
        members=[
            make_member(member_id="a1", snapshot_id="snap-cycle-A", logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.INHERITED),
            make_member(member_id="a2", snapshot_id="snap-cycle-A", logical_id="logical-B",
                        version_id=b, origin=SnapshotMemberOrigin.INHERITED),
            make_member(member_id="a3", snapshot_id="snap-cycle-A", logical_id="logical-C",
                        version_id=c, origin=SnapshotMemberOrigin.ADDED),
        ],
    )
    repo.create_incremental(inc_a)
    _activate_snapshot(session, inc_a.evidence_snapshot_id)
    inc_b = make_snapshot(
        snapshot_id="snap-cycle-B", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.INCREMENTAL,
        prior_snapshot_id="snap-cycle-A", comparison_snapshot_id="snap-cycle-A",
        members=[
            make_member(member_id="b1", snapshot_id="snap-cycle-B", logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.INHERITED),
            make_member(member_id="b2", snapshot_id="snap-cycle-B", logical_id="logical-B",
                        version_id=b, origin=SnapshotMemberOrigin.INHERITED),
            make_member(member_id="b3", snapshot_id="snap-cycle-B", logical_id="logical-C",
                        version_id=c, origin=SnapshotMemberOrigin.INHERITED),
            make_member(member_id="b4", snapshot_id="snap-cycle-B", logical_id="logical-D",
                        version_id=d, origin=SnapshotMemberOrigin.ADDED),
        ],
    )
    repo.create_incremental(inc_b)
    # 把 A 的前序改指 B（A 与 B 互为前序成环），payload/镜像列同步重写。
    from app.storage.codecs import encode_contract

    a_cycled = repo.get("snap-cycle-A").model_copy(
        update={"prior_snapshot_id": "snap-cycle-B", "comparison_snapshot_id": "snap-cycle-B"}
    )
    payload_json, payload_sha256 = encode_contract(a_cycled)
    a_row = session.get(EvidenceSnapshotV2Record, "snap-cycle-A")
    a_row.prior_snapshot_id = "snap-cycle-B"
    a_row.comparison_snapshot_id = "snap-cycle-B"
    a_row.payload_json = payload_json
    a_row.payload_sha256 = payload_sha256
    _flush_guarded(session)

    cyclic = make_snapshot(
        snapshot_id="snap-cycle-2", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.INCREMENTAL,
        prior_snapshot_id="snap-cycle-A", comparison_snapshot_id="snap-cycle-A",
        members=[
            make_member(member_id="m2a", snapshot_id="snap-cycle-2", logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.INHERITED),
            make_member(member_id="m2b", snapshot_id="snap-cycle-2", logical_id="logical-B",
                        version_id=b, origin=SnapshotMemberOrigin.INHERITED),
            make_member(member_id="m2c", snapshot_id="snap-cycle-2", logical_id="logical-C",
                        version_id=c, origin=SnapshotMemberOrigin.INHERITED),
            make_member(member_id="m2d", snapshot_id="snap-cycle-2", logical_id="logical-D",
                        version_id=d, origin=SnapshotMemberOrigin.INHERITED),
            make_member(member_id="m2e", snapshot_id="snap-cycle-2", logical_id="logical-E",
                        version_id=e, origin=SnapshotMemberOrigin.ADDED),
        ],
    )
    with pytest.raises(er.SnapshotCycleError):
        repo.create_incremental(cyclic)


def test_incremental_duplicate_noop(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    a, b, _ = _seed_docs(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    prior = make_snapshot(
        snapshot_id="snap-nop-prior", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.FULL,
        members=[
            make_member(member_id="p-a", snapshot_id="snap-nop-prior", logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.ADDED),
            make_member(member_id="p-b", snapshot_id="snap-nop-prior", logical_id="logical-B",
                        version_id=b, origin=SnapshotMemberOrigin.ADDED),
        ],
    )
    repo.create_full(prior)
    _activate_snapshot(session, prior.evidence_snapshot_id)
    inc = make_snapshot(
        snapshot_id="snap-nop-1", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.INCREMENTAL,
        prior_snapshot_id="snap-nop-prior", comparison_snapshot_id="snap-nop-prior",
        members=[
            make_member(member_id="i-a", snapshot_id="snap-nop-1", logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.INHERITED),
            make_member(member_id="i-b", snapshot_id="snap-nop-1", logical_id="logical-B",
                        version_id=b, origin=SnapshotMemberOrigin.INHERITED),
        ],
    )
    first_returned = repo.create_incremental(inc)
    assert first_returned.evidence_snapshot_id == "snap-nop-prior"
    dup = make_snapshot(
        snapshot_id="snap-nop-2", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.INCREMENTAL,
        prior_snapshot_id="snap-nop-prior", comparison_snapshot_id="snap-nop-prior",
        members=[
            make_member(member_id="d-a", snapshot_id="snap-nop-2", logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.INHERITED),
            make_member(member_id="d-b", snapshot_id="snap-nop-2", logical_id="logical-B",
                        version_id=b, origin=SnapshotMemberOrigin.INHERITED),
        ],
    )
    returned = repo.create_incremental(dup)
    assert returned.evidence_snapshot_id == "snap-nop-prior"
    assert session.get(EvidenceSnapshotV2Record, "snap-nop-1") is None
    assert session.get(EvidenceSnapshotV2Record, "snap-nop-2") is None


def _full_snapshot(session, fixture, snapshot_id, logical_version_pairs, doc_repo) -> str:
    """按 (logical_id, version_id) 成员建立一张 distinct 完整快照并返回 id。"""
    project_id, subject_id, episode_id = scope_of(fixture)
    snapshot = make_snapshot(
        snapshot_id=snapshot_id,
        project_id=project_id,
        subject_id=subject_id,
        episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        members=[
            make_member(
                member_id=f"{snapshot_id}-{logical_id}",
                snapshot_id=snapshot_id,
                logical_id=logical_id,
                version_id=version_id,
                origin=SnapshotMemberOrigin.ADDED,
            )
            for logical_id, version_id in logical_version_pairs
        ],
    )
    repo = er.EvidenceSnapshotRepository(session)
    created = repo.create_full(snapshot)
    return created.evidence_snapshot_id


def _set_episode_pointer(session, episode_id: str, snapshot_id: str, revision_id: str):
    """测试脚手架：以最小 ORM 行建立 base/complete 修订对并把审核节点活动指针
    指向 (snapshot_id, revision_id)。"""
    from datetime import UTC, datetime

    from app.domain.contracts.evidence_locator import CompleteEvidenceProcessingRevision
    from app.domain.contracts.evidence_processing import EvidenceProcessingRevision
    from app.domain.publication import evidence_processing_manifest_hash
    from app.storage.codecs import encode_contract, to_utc_naive
    from app.storage.models import ReviewEpisodeRecord
    from app.storage.ocr_models import EvidenceProcessingRevisionRecord
    from app.storage.repositories import EpisodeRepository

    fixed = datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC)
    contract = EpisodeRepository(session).get(episode_id)
    base_id = f"base-{snapshot_id}"
    complete_id = revision_id
    empty_manifest = evidence_processing_manifest_hash(entries=[])
    if session.get(EvidenceProcessingRevisionRecord, base_id) is None:
        base_contract = EvidenceProcessingRevision(
            evidence_processing_revision_id=base_id,
            evidence_snapshot_id=snapshot_id,
            project_id=contract.project_id,
            subject_id=contract.subject_id,
            review_episode_id=episode_id,
            manifest=[], manifest_sha256=empty_manifest,
            created_at=fixed, created_by="scaffold",
        )
        bj, bsh = encode_contract(base_contract)
        session.add(
            EvidenceProcessingRevisionRecord(
                evidence_processing_revision_id=base_id,
                evidence_snapshot_id=snapshot_id,
                project_id=contract.project_id,
                subject_id=contract.subject_id,
                review_episode_id=episode_id,
                manifest_sha256=empty_manifest, status="ready",
                is_activatable=False, revision_kind="base",
                created_by="scaffold", created_at=to_utc_naive(fixed),
                payload_json=bj, payload_sha256=bsh,
            )
        )
    if session.get(EvidenceProcessingRevisionRecord, complete_id) is None:
        complete_contract = CompleteEvidenceProcessingRevision(
            evidence_processing_revision_id=complete_id,
            evidence_snapshot_id=snapshot_id,
            project_id=contract.project_id,
            subject_id=contract.subject_id,
            review_episode_id=episode_id,
            base_processing_revision_id=base_id,
            producer_candidate_id=f"scaffold-producer-{snapshot_id}",
            candidate_input_sha256="f" * 64,
            manifest=[], manifest_sha256=empty_manifest,
            completion_manifest_sha256="0" * 64,
            created_at=fixed, created_by="scaffold",
        )
        cj, csh = encode_contract(complete_contract)
        session.add(
            EvidenceProcessingRevisionRecord(
                evidence_processing_revision_id=complete_id,
                evidence_snapshot_id=snapshot_id,
                project_id=contract.project_id,
                subject_id=contract.subject_id,
                review_episode_id=episode_id,
                manifest_sha256=empty_manifest, status="ready",
                is_activatable=True, revision_kind="complete",
                base_processing_revision_id=base_id,
                producer_candidate_id=f"scaffold-producer-{snapshot_id}",
                candidate_input_sha256="f" * 64,
                completion_manifest_sha256="0" * 64,
                created_by="scaffold", created_at=to_utc_naive(fixed),
                payload_json=cj, payload_sha256=csh,
            )
        )
    row = session.get(ReviewEpisodeRecord, episode_id)
    updated = contract.model_copy(
        update={
            "active_evidence_snapshot_id": snapshot_id,
            "active_evidence_processing_revision_id": complete_id,
        }
    )
    payload_json, payload_sha256 = encode_contract(updated)
    row.active_evidence_snapshot_id = snapshot_id
    row.active_evidence_processing_revision_id = complete_id
    row.payload_json = payload_json
    row.payload_sha256 = payload_sha256
    _flush_guarded(session)


def test_current_snapshot_requires_pointer_not_active_status(seeded):
    """指针为 null 时即使存在历史 ACTIVE 快照也不回退（§8.4 反例 3/4）。"""
    session, fixture = seeded
    _project_id, _subject_id, episode_id = scope_of(fixture)
    a, b, _ = _seed_docs(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    doc_repo = er.SourceDocumentRepository(session)
    active_id = _full_snapshot(
        session, fixture, "snap-active-1", [("logical-A", a)], doc_repo
    )
    _activate_snapshot(session, active_id)
    _full_snapshot(
        session, fixture, "snap-active-2",
        [("logical-A", a), ("logical-B", b)], doc_repo,
    )
    _activate_snapshot(session, "snap-active-2")
    # 指针为 null：即使存在两个 ACTIVE 历史快照，也不得推断当前版本。
    assert repo.current_snapshot_for_episode(episode_id) is None


def test_current_snapshot_follows_pointer_only(seeded):
    """多个 ACTIVE / 乱序 / 相同时间戳 / 乱序 ID：只有指针目标是当前。"""
    session, fixture = seeded
    _project_id, _subject_id, episode_id = scope_of(fixture)
    a, b, c = _seed_docs(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    doc_repo = er.SourceDocumentRepository(session)
    id_1 = _full_snapshot(
        session, fixture, "snap-1", [("logical-A", a)], doc_repo
    )
    _activate_snapshot(session, id_1)
    id_2 = _full_snapshot(
        session, fixture, "snap-2", [("logical-A", a), ("logical-B", b)], doc_repo
    )
    _activate_snapshot(session, id_2)
    id_3 = _full_snapshot(
        session, fixture, "snap-3", [("logical-A", a), ("logical-C", c)], doc_repo
    )
    _activate_snapshot(session, id_3)
    # 指针指向较早创建/较小 ID 的快照：仍以指针为权威。
    _set_episode_pointer(session, episode_id, id_1, "complete-1")
    latest = repo.current_snapshot_for_episode(episode_id)
    assert latest is not None
    assert latest.evidence_snapshot_id == id_1


def test_current_snapshot_ignores_legacy_snapshot_id(seeded):
    """legacy evidence_snapshot_id 非空但活动指针为 null 时仍不消费（§5.5）。"""
    session, fixture = seeded
    _project_id, _subject_id, episode_id = scope_of(fixture)
    a, _, _ = _seed_docs(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    active_id = _full_snapshot(
        session, fixture, "snap-legacy-active", [("logical-A", a)],
        er.SourceDocumentRepository(session),
    )
    _activate_snapshot(session, active_id)
    # fixture 的 legacy evidence_snapshot_id 非空，但活动指针对为 null：
    # Phase 4 current 读取不得回退到 legacy 字段。
    assert repo.current_snapshot_for_episode(episode_id) is None


def test_incremental_rejects_non_active_prior_and_accepts_active(seeded):
    """仓储层门禁：补充资料只能继承 ACTIVE 前序；候选作前序必须拒绝。"""
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    a, b, c = _seed_docs(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    prior = make_snapshot(
        snapshot_id="snap-gate-prior", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.FULL,
        members=[
            make_member(member_id="p-a", snapshot_id="snap-gate-prior", logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.ADDED),
            make_member(member_id="p-b", snapshot_id="snap-gate-prior", logical_id="logical-B",
                        version_id=b, origin=SnapshotMemberOrigin.ADDED),
        ],
    )
    repo.create_full(prior)
    inc = make_snapshot(
        snapshot_id="snap-gate-inc", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.INCREMENTAL,
        prior_snapshot_id="snap-gate-prior", comparison_snapshot_id="snap-gate-prior",
        members=[
            make_member(member_id="i-a", snapshot_id="snap-gate-inc", logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.INHERITED),
            make_member(member_id="i-b", snapshot_id="snap-gate-inc", logical_id="logical-B",
                        version_id=b, origin=SnapshotMemberOrigin.INHERITED),
            make_member(member_id="i-c", snapshot_id="snap-gate-inc", logical_id="logical-C",
                        version_id=c, origin=SnapshotMemberOrigin.ADDED),
        ],
    )
    # STAGED 候选前序：拒绝，不能依赖服务层选择正确基准。
    with pytest.raises(er.SnapshotSupersessionError, match="ACTIVE"):
        repo.create_incremental(inc)
    # ACTIVE 前序：通过。
    _activate_snapshot(session, prior.evidence_snapshot_id)
    saved = repo.create_incremental(inc)
    assert saved.evidence_snapshot_id == "snap-gate-inc"


def test_duplicate_full_creation_is_serialized_across_sessions(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    a, b, _ = _seed_docs(session, fixture)
    from app.storage.db import build_session_factory

    session.commit()
    factory = build_session_factory(session.get_bind())

    def submit(index: int) -> str:
        snapshot_id = f"snap-race-{index}"
        snapshot = make_snapshot(
            snapshot_id=snapshot_id,
            project_id=project_id,
            subject_id=subject_id,
            episode_id=episode_id,
            upload_mode=UploadMode.FULL,
            members=[
                make_member(
                    member_id=f"race-{index}-a",
                    snapshot_id=snapshot_id,
                    logical_id="logical-A",
                    version_id=a,
                    origin=SnapshotMemberOrigin.ADDED,
                ),
                make_member(
                    member_id=f"race-{index}-b",
                    snapshot_id=snapshot_id,
                    logical_id="logical-B",
                    version_id=b,
                    origin=SnapshotMemberOrigin.ADDED,
                ),
            ],
        )
        with factory() as current:
            result = er.EvidenceSnapshotRepository(current).create_full(snapshot)
            current.commit()
            return result.evidence_snapshot_id

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(submit, range(4)))

    assert len(set(results)) == 1
    assert session.execute(
        select(func.count()).select_from(EvidenceSnapshotV2Record)
    ).scalar_one() == 1


def test_snapshot_state_machine(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    a, b, c = _seed_docs(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    snap = make_snapshot(
        snapshot_id="snap-state-1", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.FULL,
        members=[
            make_member(member_id="s-a", snapshot_id="snap-state-1", logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.ADDED),
            make_member(member_id="s-b", snapshot_id="snap-state-1", logical_id="logical-B",
                        version_id=b, origin=SnapshotMemberOrigin.ADDED),
        ],
    )
    repo.create_full(snap)
    # 合法链 staged -> processing -> retryable_failure -> processing -> ready
    assert repo.transition_status(snap.evidence_snapshot_id, event="worker_start",
                                  new_status=SnapshotStatus.PROCESSING, actor="worker-1",
                                  reason="start").status == SnapshotStatus.PROCESSING
    assert repo.transition_status(snap.evidence_snapshot_id, event="retryable_error",
                                  new_status=SnapshotStatus.RETRYABLE_FAILURE, actor="worker-1",
                                  reason="timeout").status == SnapshotStatus.RETRYABLE_FAILURE
    assert repo.transition_status(snap.evidence_snapshot_id, event="retry",
                                  new_status=SnapshotStatus.PROCESSING, actor="worker-1",
                                  reason="retry").status == SnapshotStatus.PROCESSING
    assert repo.transition_status(snap.evidence_snapshot_id, event="blocking_risk_found",
                                  new_status=SnapshotStatus.NEEDS_ATTENTION, actor="worker-1",
                                  reason="risk").status == SnapshotStatus.NEEDS_ATTENTION
    assert repo.transition_status(snap.evidence_snapshot_id, event="correction_or_resolution",
                                  new_status=SnapshotStatus.PROCESSING, actor="worker-1",
                                  reason="corrected").status == SnapshotStatus.PROCESSING
    ready = repo.transition_status(snap.evidence_snapshot_id, event="all_gates_passed",
                                   new_status=SnapshotStatus.READY, actor="gate",
                                   reason="passed")
    assert ready.status == SnapshotStatus.READY
    # ready -> active 属 Slice 4.4 激活路径，本切片拒绝
    with pytest.raises(er.SnapshotStatusTransitionError):
        repo.transition_status(snap.evidence_snapshot_id, event="activate",
                               new_status=SnapshotStatus.ACTIVE, actor="x", reason="act")
    # terminal_error 进入终态后冻结
    other = make_snapshot(
        snapshot_id="snap-state-terminal", project_id=project_id, subject_id=subject_id,
        episode_id=episode_id, upload_mode=UploadMode.FULL,
        members=[
            make_member(member_id="t-a", snapshot_id="snap-state-terminal", logical_id="logical-A",
                        version_id=a, origin=SnapshotMemberOrigin.ADDED),
            make_member(member_id="t-b", snapshot_id="snap-state-terminal", logical_id="logical-B",
                        version_id=b, origin=SnapshotMemberOrigin.ADDED),
            make_member(member_id="t-c", snapshot_id="snap-state-terminal", logical_id="logical-C",
                        version_id=c, origin=SnapshotMemberOrigin.ADDED),
        ],
    )
    repo.create_full(other)
    repo.transition_status(other.evidence_snapshot_id, event="worker_start",
                           new_status=SnapshotStatus.PROCESSING, actor="w", reason="start")
    repo.transition_status(other.evidence_snapshot_id, event="terminal_error",
                           new_status=SnapshotStatus.TERMINAL_FAILURE, actor="w",
                           reason="unsupported format")
    assert repo.get(other.evidence_snapshot_id).status == SnapshotStatus.TERMINAL_FAILURE
    with pytest.raises(er.SnapshotStatusTransitionError):
        repo.transition_status(other.evidence_snapshot_id, event="retry",
                               new_status=SnapshotStatus.PROCESSING, actor="w", reason="frozen")


def test_snapshot_state_machine_illegal_and_terminal(seeded):
    session, fixture = seeded
    snap = _seed_full_snapshot(session, fixture)
    repo = er.EvidenceSnapshotRepository(session)
    # staged 不能直接到 ready
    with pytest.raises(er.SnapshotStatusTransitionError):
        repo.transition_status(snap.evidence_snapshot_id, event="all_gates_passed",
                               new_status=SnapshotStatus.READY, actor="x", reason="skip")
    # staged -> cancelled 后进入终态，冻结
    repo.transition_status(snap.evidence_snapshot_id, event="cancel",
                           new_status=SnapshotStatus.CANCELLED, actor="user", reason="user cancel")
    assert repo.get(snap.evidence_snapshot_id).status == SnapshotStatus.CANCELLED
    with pytest.raises(er.SnapshotStatusTransitionError):
        repo.transition_status(snap.evidence_snapshot_id, event="worker_start",
                               new_status=SnapshotStatus.PROCESSING, actor="x", reason="frozen")
