"""Phase 4 上传预览仓储确定性测试（Slice 4.2）。

覆盖：预览主行 + 逐文件条目的 payload/列镜像三方交叉校验、作用域门禁、三态
生命周期（staged -> committed / staged -> cancelled，终态冻结）、确认记录追加写，
以及 ``latest_effective_for_scope``（活动快照优先，否则最新可演进候选；终态不参与）。
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.contracts.enums import (
    SnapshotMemberOrigin,
    SnapshotStatus,
    UploadItemStatus,
    UploadMode,
    UploadPreviewStatus,
)
from app.domain.contracts.evidence_ingestion import EvidenceSnapshot
from app.domain.contracts.evidence_upload import (
    EvidenceUploadCommit,
    EvidenceUploadItem,
    EvidenceUploadPreview,
    evidence_preview_digest,
)
from app.storage.codecs import PersistedContractInvalid
from app.storage.evidence_repositories import (
    BlobRepository,
    EvidenceSnapshotRepository,
    SourceDocumentRepository,
)
from app.storage.evidence_upload_models import (
    EvidenceUploadCommitRecord,
    EvidenceUploadItemRecord,
    EvidenceUploadPreviewRecord,
)
from app.storage.evidence_upload_repositories import (
    EvidenceUploadCommitRepository,
    EvidenceUploadPreviewRepository,
    PreviewNotFoundError,
    PreviewStatusTransitionError,
)
from app.storage.repositories import (
    InvalidReferenceError,
    _flush_guarded,
    persist_fixture,
)
from tests.v2.storage.test_evidence_repositories import (
    make_blob,
    make_member,
    make_snapshot,
    make_version,
    scope_of,
)
from tests.v2.storage.test_repositories_roundtrip import FIXTURES

NOW = datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC)
_DIGEST = "a" * 64


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


def _item(preview_id: str, **overrides) -> EvidenceUploadItem:
    base = {
        "item_id": uuid4().hex,
        "preview_id": preview_id,
        "file_name": "report.pdf",
        "sha256": _DIGEST,
        "byte_size": 10,
        "media_type": "application/pdf",
        "storage_ref": f"staging/{preview_id}/{_DIGEST}",
        "status": UploadItemStatus.ADDED,
        "processing_hint": "process_new",
    }
    base.update(overrides)
    return EvidenceUploadItem.model_validate(base)


def _preview(project_id: str, subject_id: str, episode_id: str, **overrides):
    preview_id = overrides.pop("preview_id", uuid4().hex)
    items = overrides.pop("items", None) or [_item(preview_id)]
    base = {
        "preview_id": preview_id,
        "project_id": project_id,
        "subject_id": subject_id,
        "review_episode_id": episode_id,
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
# 预览读写与镜像校验
# ---------------------------------------------------------------------------


def test_preview_roundtrip_with_item_mirror(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    repo = EvidenceUploadPreviewRepository(session)
    preview = _preview(project_id, subject_id, episode_id)
    repo.create(preview)
    session.flush()
    loaded = repo.get(preview.preview_id)
    assert loaded == preview
    assert [item.item_id for item in loaded.items] == [
        item.item_id for item in preview.items
    ]


def test_preview_get_missing_raises_not_found(seeded):
    session, _ = seeded
    with pytest.raises(PreviewNotFoundError, match="不存在"):
        EvidenceUploadPreviewRepository(session).get("missing-preview")


def test_preview_list_by_scope_excludes_other_episodes(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    repo = EvidenceUploadPreviewRepository(session)
    repo.create(_preview(project_id, subject_id, episode_id))
    session.flush()
    listed = repo.list_by_scope(
        project_id=project_id, subject_id=subject_id, review_episode_id=episode_id
    )
    assert len(listed) == 1
    assert repo.list_by_scope(
        project_id=project_id, subject_id=subject_id, review_episode_id="other-episode"
    ) == []


def test_preview_scope_violation_is_rejected(seeded):
    session, fixture = seeded
    project_id, subject_id, _episode_id = scope_of(fixture)
    other_episode = _preview(
        project_id,
        subject_id,
        "episode-not-exists",
    )
    with pytest.raises(InvalidReferenceError, match="不存在"):
        EvidenceUploadPreviewRepository(session).create(other_episode)


def test_preview_item_mirror_drift_is_rejected(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    repo = EvidenceUploadPreviewRepository(session)
    preview = _preview(project_id, subject_id, episode_id)
    repo.create(preview)
    session.flush()
    # 篡改条目镜像列：与 payload 不一致 -> 读取拒绝。
    row = session.get(EvidenceUploadItemRecord, preview.items[0].item_id)
    row.file_name = "tampered.pdf"
    session.flush()
    with pytest.raises(Exception, match="不一致"):
        repo.get(preview.preview_id)


def test_preview_payload_sha_mismatch_is_rejected(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    repo = EvidenceUploadPreviewRepository(session)
    preview = _preview(project_id, subject_id, episode_id)
    repo.create(preview)
    session.flush()
    row = session.get(EvidenceUploadPreviewRecord, preview.preview_id)
    row.payload_sha256 = "f" * 64
    session.flush()
    with pytest.raises(Exception, match="哈希不一致"):
        repo.get(preview.preview_id)


def test_create_preview_requires_staged_status(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    committed = _preview(
        project_id,
        subject_id,
        episode_id,
        status=UploadPreviewStatus.COMMITTED,
    )
    with pytest.raises(PreviewStatusTransitionError, match="创建时状态必须为 staged"):
        EvidenceUploadPreviewRepository(session).create(committed)


# ---------------------------------------------------------------------------
# 三态生命周期
# ---------------------------------------------------------------------------


def test_preview_transitions_and_terminal_freeze(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    repo = EvidenceUploadPreviewRepository(session)
    preview = _preview(project_id, subject_id, episode_id)
    repo.create(preview)
    session.flush()

    cancelled = repo.transition_status(
        preview.preview_id,
        to_status=UploadPreviewStatus.CANCELLED,
        actor="tester",
        reason="用户取消",
    )
    assert cancelled.status == UploadPreviewStatus.CANCELLED
    assert cancelled.created_by == "tester"  # 原创建者保留
    # 重复取消同状态是幂等 no-op（不报错也不改动）。
    again = repo.transition_status(
        preview.preview_id,
        to_status=UploadPreviewStatus.CANCELLED,
        actor="tester",
        reason="再取消",
    )
    assert again.status == UploadPreviewStatus.CANCELLED
    # 终态冻结：取消后不可再向其他状态转换。
    with pytest.raises(PreviewStatusTransitionError, match="终态"):
        repo.transition_status(
            preview.preview_id,
            to_status=UploadPreviewStatus.COMMITTED,
            actor="tester",
            reason="再确认",
        )


def test_preview_transition_committed_then_frozen(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    repo = EvidenceUploadPreviewRepository(session)
    preview = _preview(project_id, subject_id, episode_id)
    repo.create(preview)
    session.flush()
    committed = repo.transition_status(
        preview.preview_id,
        to_status=UploadPreviewStatus.COMMITTED,
        actor="tester",
        reason="确认",
    )
    assert committed.status == UploadPreviewStatus.COMMITTED
    with pytest.raises(PreviewStatusTransitionError, match="终态"):
        repo.transition_status(
            preview.preview_id,
            to_status=UploadPreviewStatus.CANCELLED,
            actor="tester",
            reason="取消已确认预览",
        )


def test_preview_transition_unknown_status_rejected(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    repo = EvidenceUploadPreviewRepository(session)
    preview = _preview(project_id, subject_id, episode_id)
    repo.create(preview)
    session.flush()
    with pytest.raises(PreviewStatusTransitionError, match="未知的预览状态"):
        repo.transition_status(
            preview.preview_id,
            to_status="bogus",  # type: ignore[arg-type]
            actor="tester",
            reason="非法",
        )


# ---------------------------------------------------------------------------
# 确认记录
# ---------------------------------------------------------------------------


def test_commit_roundtrip(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    preview_repo = EvidenceUploadPreviewRepository(session)
    preview = _preview(project_id, subject_id, episode_id)
    preview_repo.create(preview)
    session.flush()
    _seed_snapshot(
        session,
        fixture,
        snapshot_id="snapshot-1",
        mode=UploadMode.FULL,
        member_blob=b"commit",
    )
    repo = EvidenceUploadCommitRepository(session)
    commit = EvidenceUploadCommit(
        commit_id="commit-1",
        preview_id=preview.preview_id,
        evidence_snapshot_id="snapshot-1",
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        preview_sha256=_DIGEST,
        idempotency_key="key-1",
        job_id="job-1",
        duplicate=False,
        created_at=NOW,
        created_by="tester",
    )
    repo.create(commit)
    session.flush()
    assert repo.get("commit-1") == commit
    assert repo.get_or_none("commit-missing") is None


def test_snapshot_job_projection_rejects_hidden_commit_mirror_drift(seeded):
    session, fixture = seeded
    project_id, subject_id, episode_id = scope_of(fixture)
    preview = _preview(project_id, subject_id, episode_id)
    EvidenceUploadPreviewRepository(session).create(preview)
    _seed_snapshot(
        session,
        fixture,
        snapshot_id="snapshot-job",
        mode=UploadMode.FULL,
        member_blob=b"job",
    )
    repo = EvidenceUploadCommitRepository(session)
    repo.create(
        EvidenceUploadCommit(
            commit_id="commit-job",
            preview_id=preview.preview_id,
            evidence_snapshot_id="snapshot-job",
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=episode_id,
            upload_mode=UploadMode.FULL,
            preview_sha256=_DIGEST,
            idempotency_key="key-job",
            job_id="job-1",
            duplicate=False,
            created_at=NOW,
            created_by="tester",
        )
    )
    assert repo.processing_job_id_for_snapshot("snapshot-job") == "job-1"

    _seed_snapshot(
        session,
        fixture,
        snapshot_id="snapshot-other",
        mode=UploadMode.FULL,
        member_blob=b"other",
    )
    row = session.get(EvidenceUploadCommitRecord, "commit-job")
    assert row is not None
    row.evidence_snapshot_id = "snapshot-other"
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="payload 不一致"):
        repo.processing_job_id_for_snapshot("snapshot-job")


# ---------------------------------------------------------------------------
# current_snapshot_for_episode（指针权威；不再按 ACTIVE/时间/ID 推断）
# ---------------------------------------------------------------------------


def _seed_snapshot(
    session,
    fixture,
    *,
    snapshot_id: str,
    mode: UploadMode,
    member_blob: bytes,
    prior: str | None = None,
    comparison: str | None = None,
) -> EvidenceSnapshot:
    project_id, subject_id, episode_id = scope_of(fixture)
    blob = make_blob(member_blob)
    BlobRepository(session).get_or_create_by_sha256(blob)
    version = make_version(
        version_id=f"version-{snapshot_id}",
        logical_id=f"logical-{snapshot_id}",
        blob_sha=blob.sha256,
        project_id=project_id,
        subject_id=subject_id,
        episode_id=episode_id,
        version_number=1,
    )
    SourceDocumentRepository(session).create_version(version)
    member = make_member(
        member_id=f"member-{snapshot_id}",
        snapshot_id=snapshot_id,
        logical_id=f"logical-{snapshot_id}",
        version_id=version.source_document_version_id,
        origin=SnapshotMemberOrigin.ADDED,
    )
    snapshot = make_snapshot(
        snapshot_id=snapshot_id,
        project_id=project_id,
        subject_id=subject_id,
        episode_id=episode_id,
        upload_mode=mode,
        members=[member],
        prior_snapshot_id=prior,
        comparison_snapshot_id=comparison,
    )
    return EvidenceSnapshotRepository(session).create_full(snapshot)


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


def test_current_snapshot_none_when_pointer_null_even_with_active(seeded):
    """指针为 null 但存在 ACTIVE 历史快照时不得回退（§8.4 反例 4）。"""
    session, fixture = seeded
    _project_id, _subject_id, episode_id = scope_of(fixture)
    _seed_snapshot(
        session, fixture, snapshot_id="snap-1", mode=UploadMode.FULL, member_blob=b"one"
    )
    _activate_snapshot_row(session, "snap-1")
    assert (
        EvidenceSnapshotRepository(session).current_snapshot_for_episode(episode_id)
        is None
    )


def test_current_snapshot_follows_pointer_over_active_order(seeded):
    """多个 ACTIVE（时间/ID 乱序）+ 相等时间戳：只有指针目标是 current。"""
    session, fixture = seeded
    _project_id, _subject_id, episode_id = scope_of(fixture)
    repo = EvidenceSnapshotRepository(session)
    _seed_snapshot(
        session, fixture, snapshot_id="snap-a", mode=UploadMode.FULL, member_blob=b"a"
    )
    _seed_snapshot(
        session, fixture, snapshot_id="snap-b", mode=UploadMode.FULL, member_blob=b"b"
    )
    _seed_snapshot(
        session, fixture, snapshot_id="snap-c", mode=UploadMode.FULL, member_blob=b"c"
    )
    _activate_snapshot_row(session, "snap-a")
    _activate_snapshot_row(session, "snap-b")
    _activate_snapshot_row(session, "snap-c")
    # 指针指向最早创建/最小 ID 的 snap-a：仍以指针为权威，绝不按顺序取最后 ACTIVE。
    _set_episode_pointer(session, episode_id, "snap-a", "complete-a")
    latest = repo.current_snapshot_for_episode(episode_id)
    assert latest is not None and latest.evidence_snapshot_id == "snap-a"


def test_current_snapshot_ignores_legacy_snapshot_id(seeded):
    """legacy evidence_snapshot_id 非空但活动指针为 null 时仍不消费（§5.5）。"""
    session, fixture = seeded
    _project_id, _subject_id, episode_id = scope_of(fixture)
    _seed_snapshot(
        session, fixture, snapshot_id="snap-1", mode=UploadMode.FULL, member_blob=b"one"
    )
    _activate_snapshot_row(session, "snap-1")
    # fixture legacy evidence_snapshot_id 非空；活动指针对为 null -> current 为 None。
    assert (
        EvidenceSnapshotRepository(session).current_snapshot_for_episode(episode_id)
        is None
    )


def _activate_snapshot_row(session, snapshot_id: str) -> None:
    """测试脚手架：把快照状态直接改为 ACTIVE（不建立活动指针）。"""
    from app.storage.codecs import encode_contract
    from app.storage.evidence_models import EvidenceSnapshotV2Record

    repo = EvidenceSnapshotRepository(session)
    contract = repo.get(snapshot_id)
    activated = contract.model_copy(update={"status": SnapshotStatus.ACTIVE})
    payload_json, payload_sha256 = encode_contract(activated)
    row = session.get(EvidenceSnapshotV2Record, snapshot_id)
    row.status = SnapshotStatus.ACTIVE.value
    row.payload_json = payload_json
    row.payload_sha256 = payload_sha256
    _flush_guarded(session)
