"""Slice 4.4 “资料中提及但未提供”修订/满足服务测试（WP-44B）。

覆盖 §8.5：确定性候选只能 proposed，未经确认不能进入 confirmed；confirmed 必须
保留可回放触发定位；provided 必须绑定存在且同闭包的资料版本；dismiss/解除只追加
修订，旧候选与触发原文仍在；R1 unresolved、R2 provided 后回放 R1 仍 unresolved。
"""
from __future__ import annotations

import pytest

from app.domain.contracts.enums import (
    ReferencedDocumentOrigin,
    ReferencedDocumentResolutionStatus,
    ReferencedDocumentStatus,
)
from app.services.evidence_activation_service import EvidenceActivationService
from app.services.evidence_locator_service import EvidenceLocatorService, LocatorRequest
from app.services.evidence_referenced_document_service import (
    EvidenceReferencedDocumentService,
    ReferencedDocumentServiceError,
)
from app.storage.evidence_locator_repositories import ReferencedDocumentRepository
from app.storage.evidence_repositories import SourceDocumentRepository
from app.storage.repositories import EpisodeRepository, SubjectRepository
from tests.v2.services.test_slice44_upload_pointer_authority import _activate_pair
from tests.v2.storage.test_ocr_repositories import make_version
from tests.v2.storage.test_slice44_repositories import (
    RAW_TEXT,
    sha,
)


@pytest.fixture
def stack(revision_stack, session_factory):
    session, fixture, keys = revision_stack
    session.commit()
    _activate_pair(session, keys)
    EvidenceActivationService(session_factory).activate(
        target_snapshot_id="snap-1",
        target_revision_id="complete-1",
        expected_revision=1,
        actor="tester",
        reason="建立被提及资料测试的当前资料版本",
        candidate_id="producer-complete-1",
    )
    return session, fixture, keys

def test_deterministic_candidate_is_proposed_then_user_can_confirm(stack, session_factory):
    _session, _fixture, keys = stack
    service = EvidenceReferencedDocumentService(session_factory)
    revision = service.register(
        project_id=keys["project_id"],
        subject_id=keys["subject_id"],
        review_episode_id=keys["episode_id"],
        description="原文提及的检查报告",
        origin=ReferencedDocumentOrigin.DETERMINISTIC_CANDIDATE,
        pattern_version="mentions/v1",
        created_by="tester",
    )
    assert revision.status == ReferencedDocumentStatus.PROPOSED
    assert revision.origin == ReferencedDocumentOrigin.DETERMINISTIC_CANDIDATE
    locator = EvidenceLocatorService(session_factory).create_locator(
        LocatorRequest(
            page_artifact_id="pa-1", ocr_page_id="op-1",
            source_layer="raw_ocr",
            source_text_sha256=sha(RAW_TEXT.encode("utf-8")),
            target_id="t-deterministic", target_text_start=0, target_text_end=5,
            excerpt="ALT 5",
        )
    )
    confirmed = service.confirm(
        referenced_document_id=revision.referenced_document_id,
        trigger_locator_id=locator.locator_id,
        reason="用户确认原文确有提及",
        created_by="tester",
    )
    assert confirmed.status == ReferencedDocumentStatus.CONFIRMED
    assert confirmed.origin == ReferencedDocumentOrigin.DETERMINISTIC_CANDIDATE
    assert confirmed.user_reviewed is True
    assert confirmed.reason == "用户确认原文确有提及"

def test_manual_confirm_requires_replayable_trigger(stack, session_factory):
    _session, _fixture, keys = stack
    service = EvidenceReferencedDocumentService(session_factory)
    revision = service.register(
        project_id=keys["project_id"], subject_id=keys["subject_id"],
        review_episode_id=keys["episode_id"], description="检查报告",
        created_by="tester",
    )
    # 确认必须携带触发定位；先构造同作用域定位。
    locator_service = EvidenceLocatorService(session_factory)
    locator = locator_service.create_locator(
        LocatorRequest(
            page_artifact_id="pa-1", ocr_page_id="op-1",
            source_layer="raw_ocr",
            source_text_sha256=sha(RAW_TEXT.encode("utf-8")),
            target_id="t-ref", target_text_start=0, target_text_end=5, excerpt="ALT 5",
        )
    )
    confirmed = service.confirm(
        referenced_document_id=revision.referenced_document_id,
        trigger_locator_id=locator.locator_id,
        reason="确认原文提及",
        created_by="tester",
    )
    assert confirmed.status == ReferencedDocumentStatus.CONFIRMED
    assert confirmed.trigger_locator_id == locator.locator_id
    assert confirmed.revision == 2

def test_dismiss_appends_revision_keeps_history(stack, session_factory):
    _session, _fixture, keys = stack
    service = EvidenceReferencedDocumentService(session_factory)
    revision = service.register(
        project_id=keys["project_id"], subject_id=keys["subject_id"],
        review_episode_id=keys["episode_id"], description="候选",
        created_by="tester",
    )
    dismissed = service.dismiss(
        referenced_document_id=revision.referenced_document_id,
        reason="用户解除候选",
        created_by="tester",
    )
    assert dismissed.status == ReferencedDocumentStatus.DISMISSED
    assert dismissed.reason == "用户解除候选"
    assert dismissed.supersedes_revision_id == revision.revision_id
    with session_factory() as fresh:
        repo = ReferencedDocumentRepository(fresh)
        # 旧候选与历史仍在，可精确回放。
        old = repo.get_revision(revision.revision_id)
        assert old.status == ReferencedDocumentStatus.PROPOSED


def test_confirm_and_dismiss_require_nonblank_reason(stack, session_factory):
    _session, _fixture, keys = stack
    service = EvidenceReferencedDocumentService(session_factory)
    revision = service.register(
        project_id=keys["project_id"],
        subject_id=keys["subject_id"],
        review_episode_id=keys["episode_id"],
        description="检查报告",
        created_by="tester",
    )
    with pytest.raises(ReferencedDocumentServiceError, match="必须说明原因"):
        service.dismiss(
            referenced_document_id=revision.referenced_document_id,
            reason="   ",
            created_by="tester",
        )
    with pytest.raises(ReferencedDocumentServiceError, match="必须说明原因"):
        service.confirm(
            referenced_document_id=revision.referenced_document_id,
            trigger_locator_id="unused-because-reason-is-rejected-first",
            reason="",
            created_by="tester",
        )


def test_confirm_revise_dismiss_uses_latest_chain_head(stack, session_factory):
    _session, _fixture, keys = stack
    service = EvidenceReferencedDocumentService(session_factory)
    initial = service.register(
        project_id=keys["project_id"], subject_id=keys["subject_id"],
        review_episode_id=keys["episode_id"], description="既往报告",
        origin=ReferencedDocumentOrigin.DETERMINISTIC_CANDIDATE,
        created_by="scanner",
    )
    locator = EvidenceLocatorService(session_factory).create_locator(
        LocatorRequest(
            page_artifact_id="pa-1", ocr_page_id="op-1", source_layer="raw_ocr",
            source_text_sha256=sha(RAW_TEXT.encode("utf-8")), target_id="t-chain",
            target_text_start=0, target_text_end=5, excerpt="ALT 5",
        )
    )
    confirmed = service.confirm(
        referenced_document_id=initial.referenced_document_id,
        trigger_locator_id=locator.locator_id,
        reason="确认", created_by="user",
    )
    revised = service.revise(
        referenced_document_id=initial.referenced_document_id,
        description="既往肝功能检查报告", document_type="lab",
        source_party="研究者方", reason="补充资料类型", created_by="user",
    )
    dismissed = service.dismiss(
        referenced_document_id=initial.referenced_document_id,
        reason="确认不需补充", created_by="user",
    )
    assert [confirmed.revision, revised.revision, dismissed.revision] == [2, 3, 4]
    assert revised.supersedes_revision_id == confirmed.revision_id
    assert dismissed.supersedes_revision_id == revised.revision_id
    assert revised.description == "既往肝功能检查报告"
    assert [confirmed.reason, revised.reason, dismissed.reason] == [
        "确认",
        "补充资料类型",
        "确认不需补充",
    ]


def test_resolution_can_unlink_after_provided(stack, session_factory):
    _session, _fixture, keys = stack
    service = EvidenceReferencedDocumentService(session_factory)
    revision = service.register(
        project_id=keys["project_id"], subject_id=keys["subject_id"],
        review_episode_id=keys["episode_id"], description="报告", created_by="tester",
    )
    unresolved = service.resolve(
        referenced_document_id=revision.referenced_document_id,
        status=ReferencedDocumentResolutionStatus.UNRESOLVED, created_by="tester",
    )
    provided = service.resolve(
        referenced_document_id=revision.referenced_document_id,
        status=ReferencedDocumentResolutionStatus.PROVIDED,
        source_document_version_id="doc-1", created_by="tester",
    )
    unlinked = service.resolve(
        referenced_document_id=revision.referenced_document_id,
        status=ReferencedDocumentResolutionStatus.UNRESOLVED, created_by="tester",
    )
    assert [unresolved.revision, provided.revision, unlinked.revision] == [1, 2, 3]
    assert unlinked.supersedes_resolution_revision_id == provided.resolution_revision_id
    assert unlinked.source_document_version_id is None

def test_resolution_provided_requires_existing_member_document(stack, session_factory):
    _session, _fixture, keys = stack
    service = EvidenceReferencedDocumentService(session_factory)
    revision = service.register(
        project_id=keys["project_id"], subject_id=keys["subject_id"],
        review_episode_id=keys["episode_id"], description="报告",
        created_by="tester",
    )
    from app.storage.evidence_locator_repositories import InvalidReferenceError

    with pytest.raises(InvalidReferenceError, match="不存在"):
        service.resolve(
            referenced_document_id=revision.referenced_document_id,
            status=ReferencedDocumentResolutionStatus.PROVIDED,
            source_document_version_id="doc-missing",
            created_by="tester",
        )
    resolved = service.resolve(
        referenced_document_id=revision.referenced_document_id,
        status=ReferencedDocumentResolutionStatus.PROVIDED,
        source_document_version_id="doc-1",
        created_by="tester",
    )
    assert resolved.status == ReferencedDocumentResolutionStatus.PROVIDED
    assert resolved.source_document_version_id == "doc-1"

def test_resolution_unresolved_then_provided_replays_old_unresolved(stack, session_factory):
    _session, _fixture, keys = stack
    service = EvidenceReferencedDocumentService(session_factory)
    revision = service.register(
        project_id=keys["project_id"], subject_id=keys["subject_id"],
        review_episode_id=keys["episode_id"], description="报告",
        created_by="tester",
    )
    r1 = service.resolve(
        referenced_document_id=revision.referenced_document_id,
        status=ReferencedDocumentResolutionStatus.UNRESOLVED,
        created_by="tester",
    )
    r2 = service.resolve(
        referenced_document_id=revision.referenced_document_id,
        status=ReferencedDocumentResolutionStatus.PROVIDED,
        source_document_version_id="doc-1",
        created_by="tester",
    )
    assert r2.revision == 2 and r2.supersedes_resolution_revision_id == r1.resolution_revision_id
    with session_factory() as fresh:
        repo = ReferencedDocumentRepository(fresh)
        # 旧满足修订仍回放 unresolved。
        old = repo.get_resolution(r1.resolution_revision_id)
        assert old.status == ReferencedDocumentResolutionStatus.UNRESOLVED
        assert old.source_document_version_id is None


def test_resolution_rejects_document_from_another_subject(stack, session_factory):
    """存在的资料也必须属于同一受试者、审核节点和当前快照。"""
    _session, fixture, keys = stack
    service = EvidenceReferencedDocumentService(session_factory)
    referenced = service.register(
        project_id=keys["project_id"],
        subject_id=keys["subject_id"],
        review_episode_id=keys["episode_id"],
        description="既往检查报告",
        created_by="tester",
    )
    with session_factory() as session, session.begin():
        other_subject = fixture.subject.model_copy(
            update={"subject_id": "subject-other", "subject_code": "OTHER-001"}
        )
        SubjectRepository(session).save(other_subject)
        other_episode = fixture.review_episode.model_copy(
            update={
                "review_episode_id": "episode-other",
                "subject_id": other_subject.subject_id,
                "active_evidence_snapshot_id": None,
                "active_evidence_processing_revision_id": None,
            }
        )
        EpisodeRepository(session).save(other_episode)
        source = SourceDocumentRepository(session).get("doc-1")
        SourceDocumentRepository(session).create_version(
            make_version(
                version_id="doc-other-subject",
                logical_id="log-other-subject",
                blob_sha=source.source_blob_sha256,
                scope=(
                    keys["project_id"],
                    other_subject.subject_id,
                    other_episode.review_episode_id,
                ),
                page_count=1,
            )
        )
    with pytest.raises(ReferencedDocumentServiceError, match="不属于这名受试者"):
        service.resolve(
            referenced_document_id=referenced.referenced_document_id,
            status=ReferencedDocumentResolutionStatus.PROVIDED,
            source_document_version_id="doc-other-subject",
            created_by="tester",
        )
    with session_factory() as session:
        assert (
            EvidenceReferencedDocumentService.resolution_head(
                session, referenced.referenced_document_id
            )
            is None
        )

def test_resolution_without_registration_chain_rejected(stack, session_factory):
    _session, _fixture, _keys = stack
    service = EvidenceReferencedDocumentService(session_factory)
    with pytest.raises(ReferencedDocumentServiceError, match="找不到对应"):
        service.resolve(
            referenced_document_id="orphan-ref",
            status=ReferencedDocumentResolutionStatus.UNRESOLVED,
            created_by="tester",
        )
