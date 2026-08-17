"""草稿 revision 服务：历史只追加、乐观并发、取消/恢复与编辑边界。"""
from __future__ import annotations

import pytest

from app.domain.contracts.protocol_drafts import (
    DraftFeedbackKind,
    DraftRevisionReason,
    DraftRevisionStatus,
)
from app.services.protocol_draft_service import (
    DraftEditBoundaryError,
    DuplicateDraftError,
    ProtocolDraftService,
    compute_draft_diff,
)
from app.storage.concurrency import StaleRevisionError

from tests.v2.protocols.slice4_helpers import NOW, confirmed_fixture


def _service(session) -> ProtocolDraftService:
    return ProtocolDraftService(session)


def _save_initial(session, draft=None):
    _source_input, base_draft, _spans = confirmed_fixture()
    draft = draft or base_draft
    return _service(session).save_initial_draft(
        draft, actor="医学监查员", created_at=NOW
    ), base_draft


def test_initial_save_creates_revision_1_and_rejects_duplicate(session) -> None:
    with session.begin():
        r1, _draft = _save_initial(session)
        assert r1.revision_number == 1
        assert r1.status == DraftRevisionStatus.SAVED
        assert r1.reason == DraftRevisionReason.INITIAL_SAVE
        assert r1.previous_revision_id is None
        with pytest.raises(DuplicateDraftError):
            _save_initial(session)


def test_manual_edit_appends_immutable_revision_with_structured_diff(session) -> None:
    with session.begin():
        r1, draft = _save_initial(session)
        service = _service(session)
        edited = draft.model_copy(deep=True)
        edited.proposed_workflow_stages[0] = (
            edited.proposed_workflow_stages[0].model_copy(
                update={"display_name": "筛选期审核（修改）"}
            )
        )
        r2 = service.apply_manual_edit(
            edited,
            expected_revision_id=r1.revision_id,
            actor="医学监查员",
            created_at=NOW,
        )
        assert r2.revision_number == 2
        assert r2.previous_revision_id == r1.revision_id
        assert r2.status == DraftRevisionStatus.SAVED
        assert r2.reason == DraftRevisionReason.MANUAL_EDIT
        # 首稿 revision 内容不可变
        assert r1.content.proposed_workflow_stages[0].display_name == "筛选期审核"
        assert r2.diff.modified_workflow_stage_ids == ["stage-screening"]
        # 历史保留：链头是 r2
        assert service.revisions.get_head(draft.draft_id).revision_id == r2.revision_id
        assert service.revisions.count(draft.draft_id) == 2


def test_two_tab_concurrent_edit_second_gets_stale_revision(session) -> None:
    with session.begin():
        r1, draft = _save_initial(session)
        service = _service(session)
        edited = draft.model_copy(deep=True)
        edited.proposed_workflow_stages[0] = (
            edited.proposed_workflow_stages[0].model_copy(
                update={"display_name": "标签页 A 的修改"}
            )
        )
        service.apply_manual_edit(
            edited,
            expected_revision_id=r1.revision_id,
            actor="tab-a",
            created_at=NOW,
        )
        # 标签页 B 仍持 r1 提交 -> 过期，不得覆盖
        with pytest.raises(StaleRevisionError) as exc_info:
            service.apply_manual_edit(
                edited,
                expected_revision_id=r1.revision_id,
                actor="tab-b",
                created_at=NOW,
            )
        error = exc_info.value
        assert error.entity_type == "ProtocolDraftRevision"
        assert error.expected_revision == error.current_revision == 2
        assert service.revisions.count(draft.draft_id) == 2


def test_cancel_marks_head_cancelled_and_never_deletes_history(session) -> None:
    with session.begin():
        r1, draft = _save_initial(session)
        service = _service(session)
        edited = draft.model_copy(deep=True)
        edited.proposed_workflow_stages[0] = (
            edited.proposed_workflow_stages[0].model_copy(
                update={"display_name": "第二次修改"}
            )
        )
        r2 = service.apply_manual_edit(
            edited,
            expected_revision_id=r1.revision_id,
            actor="医学监查员",
            created_at=NOW,
        )
        cancelled = service.cancel_draft(
            draft_id=draft.draft_id, expected_revision_id=r2.revision_id
        )
        assert cancelled.status == DraftRevisionStatus.CANCELLED
        # 历史不物理删除
        assert service.revisions.count(draft.draft_id) == 2
        all_revisions = service.revisions.list_by_draft(draft.draft_id)
        assert [item.status for item in all_revisions] == [
            DraftRevisionStatus.SAVED,
            DraftRevisionStatus.CANCELLED,
        ]


def test_restore_creates_auditable_successor_without_overwriting(session) -> None:
    with session.begin():
        r1, draft = _save_initial(session)
        service = _service(session)
        edited = draft.model_copy(deep=True)
        edited.proposed_workflow_stages[0] = (
            edited.proposed_workflow_stages[0].model_copy(
                update={"display_name": "改坏的名字"}
            )
        )
        r2 = service.apply_manual_edit(
            edited,
            expected_revision_id=r1.revision_id,
            actor="医学监查员",
            created_at=NOW,
        )
        restored = service.restore_draft(
            draft_id=draft.draft_id,
            expected_revision_id=r2.revision_id,
            restore_from_revision_id=r1.revision_id,
            actor="医学监查员",
            created_at=NOW,
        )
        assert restored.status == DraftRevisionStatus.RESTORED_FROM
        assert restored.reason == DraftRevisionReason.RESTORE
        assert restored.revision_number == 3
        assert restored.previous_revision_id == r2.revision_id
        # 恢复后内容等于被恢复 revision 的快照，且 r2 原文未被覆盖
        assert (
            restored.content.proposed_workflow_stages[0].display_name
            == r1.content.proposed_workflow_stages[0].display_name
        )
        assert r2.content.proposed_workflow_stages[0].display_name == "改坏的名字"
        assert service.revisions.count(draft.draft_id) == 3


def test_edit_cannot_add_or_remove_frozen_parent_members(session) -> None:
    with session.begin():
        r1, draft = _save_initial(session)
        service = _service(session)
        tampered = draft.model_copy(deep=True)
        mapping = tampered.parent_catalog_mappings[0].model_copy(
            update={"catalog_item_id": "parent:in-fake"}
        )
        tampered.parent_catalog_mappings = [mapping] + list(
            tampered.parent_catalog_mappings[1:]
        )
        with pytest.raises(DraftEditBoundaryError) as exc_info:
            service.apply_manual_edit(
                tampered,
                expected_revision_id=r1.revision_id,
                actor="医学监查员",
                created_at=NOW,
            )
        assert exc_info.value.code == "FROZEN_PARENT_RULE_MEMBERSHIP_CHANGED"


def test_edit_cannot_rewrite_workflow_visit_structure(session) -> None:
    with session.begin():
        r1, draft = _save_initial(session)
        service = _service(session)
        tampered = draft.model_copy(deep=True)
        # 把基线资料要求改绑到筛选节点：流程访视被改写
        tampered.proposed_workflow_stages[0] = (
            tampered.proposed_workflow_stages[0].model_copy(
                update={"due_requirement_ids": ["req-proc-base"]}
            )
        )
        with pytest.raises(DraftEditBoundaryError) as exc_info:
            service.apply_manual_edit(
                tampered,
                expected_revision_id=r1.revision_id,
                actor="医学监查员",
                created_at=NOW,
            )
        assert exc_info.value.code == "WORKFLOW_VISIT_REWRITTEN"


def test_clarification_feedback_cannot_change_threshold(session) -> None:
    with session.begin():
        r1, draft = _save_initial(session)
        service = _service(session)
        clarified = draft.model_copy(deep=True)
        clarified.proposed_rules[1].components[0].expression.children[0].predicate.value = 2.0
        with pytest.raises(DraftEditBoundaryError) as exc_info:
            service.apply_feedback(
                clarified,
                expected_revision_id=r1.revision_id,
                feedback_kind=DraftFeedbackKind.CLARIFICATION,
                feedback_note="解释材料不能改阈值",
                actor="医学监查员",
                created_at=NOW,
            )
        assert exc_info.value.code == "CLARIFICATION_ALTERS_SEMANTICS"


def test_source_error_feedback_may_correct_semantics_and_keeps_kind(session) -> None:
    with session.begin():
        r1, draft = _save_initial(session)
        service = _service(session)
        corrected = draft.model_copy(deep=True)
        corrected.proposed_rules[1].components[0].expression.children[0].predicate.value = 2.0
        r2 = service.apply_feedback(
            corrected,
            expected_revision_id=r1.revision_id,
            feedback_kind=DraftFeedbackKind.SOURCE_ERROR,
            feedback_note="方案原文实为≥2.0",
            actor="医学监查员",
            created_at=NOW,
        )
        assert r2.reason == DraftRevisionReason.SOURCE_ERROR_FEEDBACK
        assert r2.feedback_kind == DraftFeedbackKind.SOURCE_ERROR
        assert r2.diff.modified_rule_codes == ["EX-01"]
        assert r2.diff.clarification_semantics_changed is True


def test_clarification_feedback_requires_note_and_keeps_semantics(session) -> None:
    with session.begin():
        r1, draft = _save_initial(session)
        service = _service(session)
        with pytest.raises(ValueError, match="澄清反馈必须提供"):
            service.apply_feedback(
                draft,
                expected_revision_id=r1.revision_id,
                feedback_kind=DraftFeedbackKind.CLARIFICATION,
                feedback_note=None,
                actor="医学监查员",
                created_at=NOW,
            )
        annotated = draft.model_copy(deep=True)
        annotated.proposed_workflow_stages[0] = (
            annotated.proposed_workflow_stages[0].model_copy(
                update={"display_name": "筛选期审核（澄清说明后）"}
            )
        )
        r2 = service.apply_feedback(
            annotated,
            expected_revision_id=r1.revision_id,
            feedback_kind=DraftFeedbackKind.CLARIFICATION,
            feedback_note="仅补充说明",
            actor="医学监查员",
            created_at=NOW,
        )
        assert r2.diff.clarification_semantics_changed is False
        assert r2.diff.workflow_visit_rewritten is False


def test_compute_draft_diff_aligns_by_official_code(session) -> None:
    _source_input, draft, _spans = confirmed_fixture()
    edited = draft.model_copy(deep=True)
    edited.proposed_rules[0].components[0].title = "年龄要求（修改）"
    diff = compute_draft_diff(draft, edited)
    assert diff.modified_rule_codes == ["IN-01"]
    assert diff.changed_component_ids == ["component-in"]
    assert diff.added_rule_codes == []
    assert diff.removed_rule_codes == []
