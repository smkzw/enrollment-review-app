"""草稿 revision 服务：历史只追加、乐观并发、取消/恢复与编辑边界。"""
from __future__ import annotations

import pytest

from app.domain.contracts.enums import ReviewStage
from app.domain.contracts.protocol_drafts import (
    DraftFeedbackKind,
    DraftRevisionReason,
    DraftRevisionStatus,
    ProtocolDraftRevision,
    _legacy_content_payload_without_source_validity_window,
)
from app.domain.publication import canonical_hash
from app.domain.contracts.rules import RestrictedRuleComponent
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


def _draft_with_restricted_component():
    _, draft, _ = confirmed_fixture()
    draft.proposed_rules[1].restricted_components = [RestrictedRuleComponent(
        rule_component_id="restricted-ex", display_code="EX-01b",
        title="尚待核清的要求", source_span_ids=["span-ex"],
        source_excerpts=[draft.proposed_rules[1].source_text],
        limitation_kind="interpretation_unresolved",
        unresolved_dimensions=["适用范围尚待核清"],
    )]
    return draft


def test_initial_save_creates_revision_1_and_rejects_duplicate(session) -> None:
    with session.begin():
        r1, _draft = _save_initial(session)
        assert r1.revision_number == 1
        assert r1.status == DraftRevisionStatus.SAVED
        assert r1.reason == DraftRevisionReason.INITIAL_SAVE
        assert r1.previous_revision_id is None
        with pytest.raises(DuplicateDraftError):
            _save_initial(session)


def test_pre_source_validity_revision_hash_remains_readable(session) -> None:
    with session.begin():
        revision, _draft = _save_initial(session)
        payload = revision.model_dump(mode="json")
        payload["content_sha256"] = canonical_hash(
            _legacy_content_payload_without_source_validity_window(
                payload["content"]
            )
        )

        restored = ProtocolDraftRevision.model_validate(payload)
        assert restored.revision_id == revision.revision_id


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
        # 提交方真实 expected revision=1，当前链头=2；不得写成 2/2 或空差异。
        assert error.expected_revision == 1
        assert error.current_revision == 2
        assert error.field_diff, "过期提交必须携带结构化差异信封"
        stage_change = error.field_diff["workflow_stage:stage-screening"]
        assert stage_change.submitted["display_name"] == "筛选期审核"
        assert stage_change.current["display_name"] == "标签页 A 的修改"
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
        saved = service.save_draft(
            draft_id=draft.draft_id,
            expected_revision_id=restored.revision_id,
        )
        assert saved.status == DraftRevisionStatus.SAVED
        reloaded = service.revisions.get(restored.revision_id)
        assert reloaded.status == DraftRevisionStatus.SAVED
        assert reloaded.reason == DraftRevisionReason.RESTORE


def test_restored_revision_can_be_published_without_hidden_save_step(session) -> None:
    with session.begin():
        r1, draft = _save_initial(session)
        service = _service(session)
        restored = service.restore_draft(
            draft_id=draft.draft_id,
            expected_revision_id=r1.revision_id,
            restore_from_revision_id=r1.revision_id,
            actor="医学监查员",
            created_at=NOW,
        )
        from app.services.protocol_draft_service import mark_revision_published

        published = mark_revision_published(
            service.revisions,
            draft_id=draft.draft_id,
            expected_revision_id=restored.revision_id,
        )

        assert published.status == DraftRevisionStatus.PUBLISHED
        assert service.revisions.get(restored.revision_id).reason == DraftRevisionReason.RESTORE


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


def test_source_error_feedback_may_move_rule_requirement_to_correct_stage(session) -> None:
    with session.begin():
        r1, draft = _save_initial(session)
        service = _service(session)
        corrected = draft.model_copy(deep=True)
        requirement = corrected.proposed_rules[1].components[0].evidence_requirements[0]
        requirement.due_stage = ReviewStage.BASELINE
        requirement_draft = next(
            item
            for item in corrected.evidence_requirement_drafts
            if item.proposed_requirement.requirement_id == requirement.requirement_id
        )
        requirement_draft.proposed_requirement.due_stage = ReviewStage.BASELINE
        for stage in corrected.proposed_workflow_stages:
            stage.due_requirement_ids = [
                item
                for item in stage.due_requirement_ids
                if item != requirement.requirement_id
            ]
            if stage.stage == ReviewStage.BASELINE:
                stage.due_requirement_ids.append(requirement.requirement_id)

        r2 = service.apply_feedback(
            corrected,
            expected_revision_id=r1.revision_id,
            feedback_kind=DraftFeedbackKind.SOURCE_ERROR,
            feedback_note="原文明确要求在基线核对",
            actor="医学监查员",
            created_at=NOW,
        )

        assert r2.diff.workflow_visit_rewritten is True
        assert next(
            item for item in r2.diff.rule_diffs if item.official_code == "EX-01"
        ).due_stage_changes


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


def test_successor_content_is_normalized_to_outer_chain(session) -> None:
    """外层 revision=2 时内层 content.draft_revision 必须同步为 2，
    previous_draft_id 必须指向链头草稿；不允许外层 2 内层仍 1。"""
    with session.begin():
        r1, draft = _save_initial(session)
        service = _service(session)
        edited = draft.model_copy(deep=True)
        edited.draft_revision = 1  # 提交方携带未更新的内层链号
        r2 = service.apply_manual_edit(
            edited,
            expected_revision_id=r1.revision_id,
            actor="医学监查员",
            created_at=NOW,
        )
        assert r2.revision_number == 2
        assert r2.content.draft_revision == 2
        assert r2.content.previous_draft_id == draft.draft_id
        # 存储层再次把关：内层链号与外层不一致的 revision 被拒
        from app.storage.repositories import (
            ProtocolDraftRevisionRepository,
            ScopeViolationError,
        )

        repo = ProtocolDraftRevisionRepository(session)
        forged = r2.model_copy(deep=True)
        forged.revision_id = "draft-revision:draft-1:forged"
        forged.content = forged.content.model_copy(update={"draft_revision": 1})
        with pytest.raises(ScopeViolationError, match="draft_revision"):
            repo.save(forged)


def test_cancelled_revision_cannot_be_published_directly(session) -> None:
    """取消状态不能直接转已发布：必须先恢复，恢复也只能按明确状态创建后继。"""
    with session.begin():
        r1, draft = _save_initial(session)
        service = _service(session)
        cancelled = service.cancel_draft(
            draft_id=draft.draft_id, expected_revision_id=r1.revision_id
        )
        assert cancelled.status == DraftRevisionStatus.CANCELLED
        with pytest.raises(DraftEditBoundaryError) as exc_info:
            service.cancel_draft(
                draft_id=draft.draft_id, expected_revision_id=r1.revision_id
            )
        assert exc_info.value.code == "DRAFT_CANCELLED"
        with pytest.raises(DraftEditBoundaryError) as exc_info:
            service.save_draft(
                draft_id=draft.draft_id, expected_revision_id=r1.revision_id
            )
        assert exc_info.value.code == "DRAFT_CANCELLED"
        # 取消后不能直接编辑；恢复创建审计后继后即可继续
        edited = draft.model_copy(deep=True)
        with pytest.raises(DraftEditBoundaryError) as exc_info:
            service.apply_manual_edit(
                edited,
                expected_revision_id=r1.revision_id,
                actor="医学监查员",
                created_at=NOW,
            )
        assert exc_info.value.code == "DRAFT_CANCELLED"
        restored = service.restore_draft(
            draft_id=draft.draft_id,
            expected_revision_id=r1.revision_id,
            restore_from_revision_id=r1.revision_id,
            actor="医学监查员",
            created_at=NOW,
        )
        assert restored.status == DraftRevisionStatus.RESTORED_FROM
        r3 = service.apply_manual_edit(
            edited,
            expected_revision_id=restored.revision_id,
            actor="医学监查员",
            created_at=NOW,
        )
        assert r3.revision_number == 3


def test_published_revision_cannot_be_edited_saved_or_cancelled(session) -> None:
    """已发布 revision 不能再 save/cancel/edit（发布后进入正式规则历史）。"""
    with session.begin():
        r1, draft = _save_initial(session)
        service = _service(session)
        from app.services.protocol_draft_service import mark_revision_published

        published = mark_revision_published(
            service.revisions,
            draft_id=draft.draft_id,
            expected_revision_id=r1.revision_id,
        )
        assert published.status == DraftRevisionStatus.PUBLISHED
        for action, kwargs in (
            ("save_draft", {"draft_id": draft.draft_id, "expected_revision_id": r1.revision_id}),
            ("cancel_draft", {"draft_id": draft.draft_id, "expected_revision_id": r1.revision_id}),
            ("restore_draft", {"draft_id": draft.draft_id, "expected_revision_id": r1.revision_id, "restore_from_revision_id": r1.revision_id, "actor": "医学监查员", "created_at": NOW}),
        ):
            with pytest.raises(DraftEditBoundaryError):
                getattr(service, action)(**kwargs)
        edited = draft.model_copy(deep=True)
        with pytest.raises(DraftEditBoundaryError) as exc_info:
            service.apply_manual_edit(
                edited,
                expected_revision_id=r1.revision_id,
                actor="医学监查员",
                created_at=NOW,
            )
        assert exc_info.value.code == "DRAFT_PUBLISHED"
        # 公开服务面不再暴露 mark_published：外部无法绕过发布事务
        assert not hasattr(ProtocolDraftService, "mark_published")


def test_clarification_cannot_change_evidence_semantics(session) -> None:
    """澄清反馈不得改变 required_source_types / 转录/同期来源/描述等权威语义。"""
    with session.begin():
        r1, draft = _save_initial(session)
        service = _service(session)
        clarified = draft.model_copy(deep=True)
        requirement = clarified.proposed_rules[0].components[0].evidence_requirements[0]
        clarified.proposed_rules[0].components[0] = (
            clarified.proposed_rules[0].components[0].model_copy(
                update={
                    "evidence_requirements": [
                        requirement.model_copy(
                            update={
                                "required_source_types": ["正式检验报告"],
                                "description": "必须提供原始记录",
                            }
                        )
                    ]
                }
            )
        )
        with pytest.raises(DraftEditBoundaryError) as exc_info:
            service.apply_feedback(
                clarified,
                expected_revision_id=r1.revision_id,
                feedback_kind=DraftFeedbackKind.CLARIFICATION,
                feedback_note="解释材料不能改证据要求",
                actor="医学监查员",
                created_at=NOW,
            )
        assert exc_info.value.code == "CLARIFICATION_ALTERS_SEMANTICS"


def test_clarification_cannot_change_source_binding(session) -> None:
    """澄清反馈不得改写组件/资料要求的来源绑定（摘录或来源范围）。"""
    with session.begin():
        r1, draft = _save_initial(session)
        service = _service(session)
        clarified = draft.model_copy(deep=True)
        clarified.component_drafts[0] = clarified.component_drafts[0].model_copy(
            update={"source_refs": ["span-ex"]}
        )
        with pytest.raises(DraftEditBoundaryError) as exc_info:
            service.apply_feedback(
                clarified,
                expected_revision_id=r1.revision_id,
                feedback_kind=DraftFeedbackKind.CLARIFICATION,
                feedback_note="解释材料不能改来源绑定",
                actor="医学监查员",
                created_at=NOW,
            )
        assert exc_info.value.code == "CLARIFICATION_ALTERS_SOURCE_BINDING"


def test_any_edit_cannot_change_visit_instance_or_window(session) -> None:
    """任何编辑（含手工编辑）不得改写访视实例/时间窗结构。"""
    with session.begin():
        r1, draft = _save_initial(session)
        service = _service(session)
        for field, value in (
            ("visit_instance", "筛选期 D1"),
            ("visit_window", "D-1"),
        ):
            tampered = draft.model_copy(deep=True)
            tampered.proposed_workflow_stages[0] = (
                tampered.proposed_workflow_stages[0].model_copy(
                    update={field: value}
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


def test_any_edit_cannot_rebind_parent_mapping_source(session) -> None:
    """父规则映射来源换绑被拒（冻结目录身份的一部分）。"""
    with session.begin():
        r1, draft = _save_initial(session)
        service = _service(session)
        tampered = draft.model_copy(deep=True)
        tampered.parent_catalog_mappings[0] = (
            tampered.parent_catalog_mappings[0].model_copy(
                update={"source_span_ids": ["span-ex"]}
            )
        )
        with pytest.raises(DraftEditBoundaryError) as exc_info:
            service.apply_manual_edit(
                tampered,
                expected_revision_id=r1.revision_id,
                actor="医学监查员",
                created_at=NOW,
            )
        assert exc_info.value.code == "PARENT_SOURCE_REBOUND"


@pytest.mark.parametrize("change", ["remove", "add", "identity", "display"])
def test_manual_edit_cannot_rewrite_restricted_component_tree(session, change) -> None:
    with session.begin():
        draft = _draft_with_restricted_component()
        r1, _ = _save_initial(session, draft)
        edited = draft.model_copy(deep=True)
        rule = edited.proposed_rules[1]
        item = rule.restricted_components[0]
        if change == "remove":
            rule.restricted_components = []
        elif change == "add":
            rule.restricted_components.append(item.model_copy(update={
                "rule_component_id": "restricted-second", "display_code": "EX-01c",
            }))
        else:
            field = "rule_component_id" if change == "identity" else "display_code"
            rule.restricted_components[0] = item.model_copy(update={field: "changed"})
        with pytest.raises(DraftEditBoundaryError) as caught:
            _service(session).apply_manual_edit(
                edited, expected_revision_id=r1.revision_id,
                actor="医学监查员", created_at=NOW,
            )
        assert caught.value.code == "MANUAL_EDIT_REWRITES_RULE_TREE"
        assert _service(session).revisions.count(draft.draft_id) == 1


@pytest.mark.parametrize("field,value", [
    ("source_span_ids", ["span-in"]),
    ("source_excerpts", ["替换后的摘录"]),
])
@pytest.mark.parametrize("feedback_kind", [None, DraftFeedbackKind.CLARIFICATION])
def test_restricted_source_binding_obeys_existing_edit_boundary(
    session, field, value, feedback_kind,
) -> None:
    with session.begin():
        draft = _draft_with_restricted_component()
        r1, _ = _save_initial(session, draft)
        edited = draft.model_copy(deep=True)
        item = edited.proposed_rules[1].restricted_components[0]
        edited.proposed_rules[1].restricted_components[0] = item.model_copy(
            update={field: value},
        )
        service = _service(session)
        with pytest.raises(DraftEditBoundaryError) as caught:
            if feedback_kind is None:
                service.apply_manual_edit(
                    edited, expected_revision_id=r1.revision_id,
                    actor="医学监查员", created_at=NOW,
                )
            else:
                service.apply_feedback(
                    edited, expected_revision_id=r1.revision_id,
                    feedback_kind=feedback_kind, feedback_note="解释材料",
                    actor="医学监查员", created_at=NOW,
                )
        assert caught.value.code == (
            "MANUAL_EDIT_REWRITES_SOURCE" if feedback_kind is None
            else "CLARIFICATION_ALTERS_SOURCE_BINDING"
        )
        assert service.revisions.count(draft.draft_id) == 1


@pytest.mark.parametrize("field,value", [
    ("limitation_kind", "consumer_unavailable"),
    ("unresolved_dimensions", ["时间尚待核清"]),
])
def test_clarification_cannot_change_restricted_semantics(session, field, value) -> None:
    with session.begin():
        draft = _draft_with_restricted_component()
        r1, _ = _save_initial(session, draft)
        edited = draft.model_copy(deep=True)
        item = edited.proposed_rules[1].restricted_components[0]
        edited.proposed_rules[1].restricted_components[0] = item.model_copy(
            update={field: value},
        )
        with pytest.raises(DraftEditBoundaryError) as caught:
            _service(session).apply_feedback(
                edited, expected_revision_id=r1.revision_id,
                feedback_kind=DraftFeedbackKind.CLARIFICATION,
                feedback_note="解释材料", actor="医学监查员", created_at=NOW,
            )
        assert caught.value.code == "CLARIFICATION_ALTERS_SEMANTICS"


def test_restricted_revision_is_saved_diffed_and_reported_in_stale_envelope(session) -> None:
    with session.begin():
        draft = _draft_with_restricted_component()
        r1, _ = _save_initial(session, draft)
        old_hash = r1.content_sha256
        service = _service(session)
        edited = draft.model_copy(deep=True)
        edited.proposed_rules[1].restricted_components[0].unresolved_dimensions = [
            "具体时间尚待核清",
        ]
        r2 = service.apply_manual_edit(
            edited, expected_revision_id=r1.revision_id,
            actor="医学监查员", created_at=NOW,
        )
        assert "restricted-ex" in r1.diff.changed_component_ids
        assert r1.diff.rule_diffs[1].added_component_refs == ["EX-01a", "EX-01b"]
        assert r2.diff.modified_rule_codes == ["EX-01"]
        assert r2.diff.changed_component_ids == ["restricted-ex"]
        assert r2.diff.clarification_semantics_changed
        changes = next(x for x in r2.diff.rule_diffs if x.official_code == "EX-01")
        assert changes.logic_changes[0].current["unresolved_dimensions"] == [
            "具体时间尚待核清",
        ]
        assert service.revisions.get(r1.revision_id).content_sha256 == old_hash
        assert r2.content.proposed_rules[0] == draft.proposed_rules[0]
        assert r2.content.proposed_rules[1].components == draft.proposed_rules[1].components
        with pytest.raises(StaleRevisionError) as caught:
            service.apply_manual_edit(
                draft, expected_revision_id=r1.revision_id,
                actor="另一个窗口", created_at=NOW,
            )
        fields = caught.value.field_diff
        assert fields["rule:EX-01"].current["restricted_components"][0][
            "unresolved_dimensions"
        ] == ["具体时间尚待核清"]
        assert fields["rule_component:restricted-ex"].submitted["component"][
            "unresolved_dimensions"
        ] == ["适用范围尚待核清"]
        assert fields["rule_component:restricted-ex"].current["component"][
            "unresolved_dimensions"
        ] == ["具体时间尚待核清"]
        assert service.revisions.count(draft.draft_id) == 2


def test_source_error_can_correct_restricted_sources_with_append_only_history(session) -> None:
    with session.begin():
        draft = _draft_with_restricted_component()
        r1, _ = _save_initial(session, draft)
        edited = draft.model_copy(deep=True)
        edited.proposed_rules[1].restricted_components[0].source_excerpts = [
            "经冻结方案重新核对的摘录",
        ]
        r2 = _service(session).apply_feedback(
            edited, expected_revision_id=r1.revision_id,
            feedback_kind=DraftFeedbackKind.SOURCE_ERROR,
            feedback_note="重新核对原文", actor="医学监查员", created_at=NOW,
        )
        changes = next(x for x in r2.diff.rule_diffs if x.official_code == "EX-01")
        assert changes.original_text_changes[0].current["source_binding"][
            "source_excerpts"
        ] == ["经冻结方案重新核对的摘录"]
        assert r2.diff.modified_rule_codes == ["EX-01"]
        assert r1.content.proposed_rules[1].restricted_components[0].source_excerpts == [
            draft.proposed_rules[1].source_text,
        ]
        # Saving a feedback revision is not a publication or source-authenticity gate.
        assert r2.status == DraftRevisionStatus.SAVED
