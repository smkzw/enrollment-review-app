"""Slice 4.4 上传基准指针权威测试（WP-44B）。

替换上传比较/前序选择的过渡性当前版本推断（按时间/ID/ACTIVE 状态取末项）为
权威审核节点活动指针：指针为 null 时补充资料拒绝（即使快照被标记 ACTIVE 也不
回退）；正式激活后基准 = 指针指向快照。
"""
from __future__ import annotations

import pytest

from app.domain.contracts.enums import SnapshotStatus
from app.domain.contracts.evidence_upload import UploadMode
from app.services.evidence_activation_service import EvidenceActivationService
from app.services.evidence_app_errors import AppEvidenceUploadError
from app.services.evidence_upload_service import (
    EvidenceUploadService,
    UploadedFileInput,
)
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository,
    EvidenceProcessingCandidateRepository,
)
from app.storage.evidence_models import EvidenceSnapshotV2Record
from app.storage.evidence_repositories import EvidenceSnapshotRepository
from app.storage.repositories import EpisodeRepository
from tests.v2.storage.test_slice44_repositories import (
    _candidate_event,
    _closed_revision,
)

PDF_HEAD = b"%PDF-1.7\n"

@pytest.fixture
def stack(revision_stack):
    session, fixture, keys = revision_stack
    session.commit()
    return session, fixture, keys

def _new_file(name="new.pdf"):
    return UploadedFileInput(file_name=name, content=PDF_HEAD + b"new content")

def _activate_pair(session, keys):
    # _closed_revision 内部完成元数据/扫描/核对播种。
    revision = _closed_revision(keys, session)
    complete = CompleteEvidenceProcessingRevisionRepository(session).create(revision)
    candidate_repo = EvidenceProcessingCandidateRepository(session)
    candidate = candidate_repo.get(complete.producer_candidate_id)
    candidate_repo.append_event(
        _candidate_event(
            candidate.candidate_id,
            2,
            "processing",
            "all_gates_passed",
            "ready",
            complete_revision_id=complete.evidence_processing_revision_id,
        )
    )
    EvidenceSnapshotRepository(session).transition_status(
        "snap-1", event="all_gates_passed", new_status=SnapshotStatus.READY,
        actor="tester", reason="就绪",
    )
    session.commit()

def test_incremental_requires_pointer_even_with_active_status(stack, session_factory, data_paths):
    """指针为 null 时补充资料拒绝；即使快照被标记 ACTIVE 也不回退（§8.4 反例 4）。"""
    _session, _fixture, keys = stack
    service = EvidenceUploadService(session_factory, data_paths)
    # 指针未建立 → 补充资料拒绝。
    with pytest.raises(AppEvidenceUploadError) as missing_pointer:
        service.create_preview(
            project_id=keys["project_id"], subject_id=keys["subject_id"],
            review_episode_id=keys["episode_id"], upload_mode=UploadMode.INCREMENTAL,
            base_revision=1, files=[_new_file()], created_by="tester",
        )
    assert missing_pointer.value.code == "NO_EFFECTIVE_SNAPSHOT"
    # 伪造快照为 ACTIVE 状态（无指针）→ 仍拒绝（指针权威，状态非基准）。
    with session_factory() as fresh, fresh.begin():
        from app.storage.codecs import encode_contract

        repo = EvidenceSnapshotRepository(fresh)
        contract = repo.get("snap-1")
        activated = contract.model_copy(update={"status": SnapshotStatus.ACTIVE})
        payload_json, payload_sha256 = encode_contract(activated)
        row = fresh.get(EvidenceSnapshotV2Record, "snap-1")
        row.status = SnapshotStatus.ACTIVE.value
        row.payload_json = payload_json
        row.payload_sha256 = payload_sha256
    with pytest.raises(AppEvidenceUploadError) as forged_status:
        service.create_preview(
            project_id=keys["project_id"], subject_id=keys["subject_id"],
            review_episode_id=keys["episode_id"], upload_mode=UploadMode.INCREMENTAL,
            base_revision=1, files=[_new_file()], created_by="tester",
        )
    assert forged_status.value.code == "NO_EFFECTIVE_SNAPSHOT"

def test_incremental_baseline_uses_pointer_after_activation(stack, session_factory, data_paths):
    session, _fixture, keys = stack
    _activate_pair(session, keys)
    activation = EvidenceActivationService(session_factory)
    activation.activate(
        target_snapshot_id="snap-1", target_revision_id="complete-1",
        expected_revision=1, actor="tester", reason="发布",
        candidate_id="producer-complete-1",
    )
    service = EvidenceUploadService(session_factory, data_paths)
    preview = service.create_preview(
        project_id=keys["project_id"], subject_id=keys["subject_id"],
        review_episode_id=keys["episode_id"], upload_mode=UploadMode.INCREMENTAL,
        base_revision=2, files=[_new_file()], created_by="tester",
    )
    # 基准 = 指针指向快照（唯一权威），非按时间/状态/ID 推断。
    with session_factory() as fresh:
        pointer = EpisodeRepository(fresh).get(keys["episode_id"]).active_evidence_snapshot_id
    assert preview.base_snapshot_id == pointer == "snap-1"
