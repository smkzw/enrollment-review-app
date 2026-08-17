"""Phase 3 切片 4 返修反例（Luna 审阅 P1/P2 根因的确定性回归）。

覆盖：
- 后继草稿内层 draft_revision 规范化（外层=2 内层不得仍=1）；
- 编辑边界：visit_instance/visit_window/父规则映射来源/临床证据语义；
- 生命周期：已取消不能保存/发布，已发布不能保存/取消/编辑/恢复；
- 发布：首次不接受覆盖版本 id、重新发布版本 id 不得脱离草稿/输入；
- 权威记录逐条资料要求来源闭包（含子规则要求）；
- 仓储防孤儿模板与断裂草稿链；
- 迁移：含证据期望子行时 0005->0006 保留子行与外键；含切片 4 数据时
  有损降级被拒绝并保持数据。
"""
from __future__ import annotations

import alembic
import pytest
from sqlalchemy import inspect, text

from app.domain.contracts.enums import ReviewStage, StudyPhase
from app.domain.contracts.protocol_drafts import (
    DraftFeedbackKind,
    DraftRevisionStatus,
)
from app.services.protocol_draft_service import (
    DraftEditBoundaryError,
    ProtocolDraftService,
    mark_revision_published,
)
from app.services.protocol_publication_service import (
    ProtocolPublicationRequest,
    ProtocolPublicationService,
    PublicationLineageError,
)
from app.storage.repositories import (
    AppendRepository,
    AUTHORITY_RECORD_CONFIG,
    ProtocolDraftRevisionRepository,
    ScopeViolationError,
)
from app.storage.migrate import MigrationManager, MigrationFailure
from app.storage.db import build_engine, build_session_factory

from tests.v2.protocols.slice4_helpers import NOW, confirmed_fixture


# ---------------------------------------------------------------------------
# 草稿服务：内层链规范化与编辑边界
# ---------------------------------------------------------------------------


def test_successor_content_draft_revision_is_normalized(session) -> None:
    """提交方内层 draft_revision 仍为 1 时，保存后继必须规范化为外层链号。"""
    from app.domain.contracts.protocol_drafts import DraftRevisionReason

    _source_input, draft, _spans = confirmed_fixture()
    service = ProtocolDraftService(session)
    with session.begin():
        r1 = service.save_initial_draft(
            draft, actor="医学监查员", created_at=NOW
        )
        # 调用方提交的编辑对象未更新内层链字段（仍为 1/无前序）。
        stale_inner = draft.model_copy(deep=True)
        stale_inner.proposed_workflow_stages[0] = (
            stale_inner.proposed_workflow_stages[0].model_copy(
                update={"display_name": "标签页 A 的修改"}
            )
        )
        assert stale_inner.draft_revision == 1
        r2 = service.apply_manual_edit(
            stale_inner,
            expected_revision_id=r1.revision_id,
            actor="医学监查员",
            created_at=NOW,
        )
        assert r2.revision_number == 2
        # 内层链与外层链一致：draft_revision=2、previous_draft_id 指向链头草稿。
        assert r2.content.draft_revision == 2
        assert r2.content.previous_draft_id == draft.draft_id


def test_repository_rejects_inner_outer_revision_mismatch(session) -> None:
    """内层 draft_revision 与外层链号不一致的 revision 必须被仓储拒绝。"""
    from app.domain.contracts.protocol_drafts import (
        DraftRevisionReason,
        ProtocolDraftRevision,
    )
    from app.domain.publication import canonical_hash

    _source_input, draft, _spans = confirmed_fixture()
    draft = draft.model_copy(update={"draft_id": "draft-x"})
    repo = ProtocolDraftRevisionRepository(session)
    with session.begin():
        r1 = ProtocolDraftRevision(
            revision_id="draft-revision:draft-x:1",
            draft_id="draft-x",
            revision_number=1,
            project_id=draft.project_id,
            protocol_version_id=draft.protocol_version_id,
            study_phase=draft.selected_phase,
            status=DraftRevisionStatus.SAVED,
            reason=DraftRevisionReason.INITIAL_SAVE,
            actor="医学监查员",
            content=draft,
            content_sha256=canonical_hash(draft.model_dump(mode="json")),
            created_at=NOW,
        )
        repo.save(r1)
        valid_content = draft.model_copy(
            update={"draft_revision": 2, "previous_draft_id": "draft-x"}
        )
        broken = ProtocolDraftRevision(
            revision_id="draft-revision:draft-x:2",
            draft_id="draft-x",
            revision_number=2,
            previous_revision_id=r1.revision_id,
            project_id=draft.project_id,
            protocol_version_id=draft.protocol_version_id,
            study_phase=draft.selected_phase,
            status=DraftRevisionStatus.SAVED,
            reason=DraftRevisionReason.MANUAL_EDIT,
            actor="医学监查员",
            content=valid_content,
            content_sha256=canonical_hash(valid_content.model_dump(mode="json")),
            created_at=NOW,
        ).model_copy(
            update={
                "content": valid_content.model_copy(update={"draft_revision": 1})
            }
        )
        with pytest.raises(ScopeViolationError, match="内层 content.draft_revision"):
            ProtocolDraftRevisionRepository(session).save(broken)


def test_edit_cannot_change_visit_instance_or_window(session) -> None:
    _source_input, draft, _spans = confirmed_fixture()
    service = ProtocolDraftService(session)
    with session.begin():
        r1 = service.save_initial_draft(
            draft, actor="医学监查员", created_at=NOW
        )
        for field, value in (
            ("visit_instance", "基线 D1"),
            ("visit_window", "D-28~D-1"),
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


def test_edit_cannot_rebind_parent_mapping_sources(session) -> None:
    _source_input, draft, _spans = confirmed_fixture()
    service = ProtocolDraftService(session)
    with session.begin():
        r1 = service.save_initial_draft(
            draft, actor="医学监查员", created_at=NOW
        )
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


def test_clarification_cannot_change_evidence_semantics(session) -> None:
    """澄清反馈不得改变 required_source_types 等临床证据语义。"""
    _source_input, draft, _spans = confirmed_fixture()
    service = ProtocolDraftService(session)
    with session.begin():
        r1 = service.save_initial_draft(
            draft, actor="医学监查员", created_at=NOW
        )
        clarified = draft.model_copy(deep=True)
        req = clarified.proposed_rules[0].components[0].evidence_requirements[0]
        clarified.proposed_rules[0].components[0].evidence_requirements[0] = (
            req.model_copy(update={"required_source_types": ["检验报告单"]})
        )
        with pytest.raises(DraftEditBoundaryError) as exc_info:
            service.apply_feedback(
                clarified,
                expected_revision_id=r1.revision_id,
                feedback_kind=DraftFeedbackKind.CLARIFICATION,
                feedback_note="解释材料不得改变证据语义",
                actor="医学监查员",
                created_at=NOW,
            )
        assert exc_info.value.code == "CLARIFICATION_ALTERS_SEMANTICS"


def test_clarification_cannot_change_source_bindings(session) -> None:
    _source_input, draft, _spans = confirmed_fixture()
    service = ProtocolDraftService(session)
    with session.begin():
        r1 = service.save_initial_draft(
            draft, actor="医学监查员", created_at=NOW
        )
        clarified = draft.model_copy(deep=True)
        clarified.component_drafts[0] = clarified.component_drafts[0].model_copy(
            update={"source_refs": ["span-ex"]}
        )
        with pytest.raises(DraftEditBoundaryError) as exc_info:
            service.apply_feedback(
                clarified,
                expected_revision_id=r1.revision_id,
                feedback_kind=DraftFeedbackKind.CLARIFICATION,
                feedback_note="解释材料不得改写来源绑定",
                actor="医学监查员",
                created_at=NOW,
            )
        assert exc_info.value.code == "CLARIFICATION_ALTERS_SOURCE_BINDING"


def test_stale_component_source_change_reports_real_snapshots(session) -> None:
    """只改组件来源时，陈旧提交也必须显示链头与提交方的真实来源快照。"""
    _source_input, draft, _spans = confirmed_fixture()
    service = ProtocolDraftService(session)
    with session.begin():
        r1 = service.save_initial_draft(
            draft, actor="医学监查员", created_at=NOW
        )
        changed = draft.model_copy(deep=True)
        item = changed.component_drafts[0]
        changed.component_drafts[0] = item.model_copy(
            update={"source_excerpts": [*item.source_excerpts, "来源纠错记录"]}
        )
        r2 = service.apply_manual_edit(
            changed,
            expected_revision_id=r1.revision_id,
            actor="医学监查员",
            created_at=NOW,
        )
        with pytest.raises(Exception) as exc_info:
            service.apply_manual_edit(
                draft,
                expected_revision_id=r1.revision_id,
                actor="另一标签页",
                created_at=NOW,
            )
        error = exc_info.value
        component_id = item.proposed_component.rule_component_id
        change = error.field_diff[f"rule_component:{component_id}"]
        assert change.current["source_binding"]["source_excerpts"][-1] == "来源纠错记录"
        assert "来源纠错记录" not in change.submitted["source_binding"]["source_excerpts"]
        assert error.expected_revision == 1
        assert error.current_revision == r2.revision_number


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_id", "project-other"),
        ("protocol_version_id", "protocol-version-other"),
        ("selected_phase", StudyPhase.PHASE_III),
    ],
)
def test_edit_cannot_detach_inner_protocol_identity(
    session, field, value
) -> None:
    _source_input, draft, _spans = confirmed_fixture()
    service = ProtocolDraftService(session)
    with session.begin():
        r1 = service.save_initial_draft(
            draft, actor="医学监查员", created_at=NOW
        )
        detached = draft.model_copy(update={field: value})
        with pytest.raises(DraftEditBoundaryError) as exc_info:
            service.apply_manual_edit(
                detached,
                expected_revision_id=r1.revision_id,
                actor="医学监查员",
                created_at=NOW,
            )
        assert exc_info.value.code == "DRAFT_IDENTITY_CHANGED"


@pytest.mark.parametrize("binding", ["top_scope", "procedure_mapping"])
def test_clarification_cannot_rebind_top_or_procedure_sources(
    session, binding
) -> None:
    _source_input, draft, _spans = confirmed_fixture()
    service = ProtocolDraftService(session)
    with session.begin():
        r1 = service.save_initial_draft(
            draft, actor="医学监查员", created_at=NOW
        )
        changed = draft.model_copy(deep=True)
        if binding == "top_scope":
            changed.source_refs = [*changed.source_refs, "source:other"]
        else:
            mapping = changed.procedure_catalog_mappings[0]
            changed.procedure_catalog_mappings[0] = mapping.model_copy(
                update={"source_span_ids": [*mapping.source_span_ids, "span-other"]}
            )
        with pytest.raises(DraftEditBoundaryError) as exc_info:
            service.apply_feedback(
                changed,
                expected_revision_id=r1.revision_id,
                feedback_kind=DraftFeedbackKind.CLARIFICATION,
                feedback_note="仅作解释",
                actor="医学监查员",
                created_at=NOW,
            )
        assert exc_info.value.code == "CLARIFICATION_ALTERS_SOURCE_BINDING"


# ---------------------------------------------------------------------------
# 草稿服务：合法生命周期转移
# ---------------------------------------------------------------------------


def test_cancelled_head_cannot_be_saved_or_published(session) -> None:
    _source_input, draft, _spans = confirmed_fixture()
    service = ProtocolDraftService(session)
    with session.begin():
        r1 = service.save_initial_draft(
            draft, actor="医学监查员", created_at=NOW
        )
        cancelled = service.cancel_draft(
            draft_id=draft.draft_id, expected_revision_id=r1.revision_id
        )
        assert cancelled.status == DraftRevisionStatus.CANCELLED
        with pytest.raises(DraftEditBoundaryError, match="已取消"):
            service.save_draft(
                draft_id=draft.draft_id, expected_revision_id=r1.revision_id
            )
        with pytest.raises(DraftEditBoundaryError, match="只有已保存"):
            mark_revision_published(
                service.revisions,
                draft_id=draft.draft_id,
                expected_revision_id=r1.revision_id,
            )


def test_published_head_cannot_be_saved_cancelled_edited_or_restored(
    session,
) -> None:
    _source_input, draft, _spans = confirmed_fixture()
    service = ProtocolDraftService(session)
    with session.begin():
        r1 = service.save_initial_draft(
            draft, actor="医学监查员", created_at=NOW
        )
        mark_revision_published(
            service.revisions,
            draft_id=draft.draft_id,
            expected_revision_id=r1.revision_id,
        )
        with pytest.raises(DraftEditBoundaryError, match="已发布"):
            service.save_draft(
                draft_id=draft.draft_id, expected_revision_id=r1.revision_id
            )
        with pytest.raises(DraftEditBoundaryError, match="已发布"):
            service.cancel_draft(
                draft_id=draft.draft_id, expected_revision_id=r1.revision_id
            )
        with pytest.raises(DraftEditBoundaryError, match="已发布"):
            service.apply_manual_edit(
                draft.model_copy(deep=True),
                expected_revision_id=r1.revision_id,
                actor="医学监查员",
                created_at=NOW,
            )
        with pytest.raises(DraftEditBoundaryError, match="已发布"):
            service.restore_draft(
                draft_id=draft.draft_id,
                expected_revision_id=r1.revision_id,
                restore_from_revision_id=r1.revision_id,
                actor="医学监查员",
                created_at=NOW,
            )


# ---------------------------------------------------------------------------
# 发布服务：版本 id 绑定与逐条来源闭包
# ---------------------------------------------------------------------------


def _save_revision(factory, draft):
    with factory() as session:
        with session.begin():
            return ProtocolDraftService(session).save_initial_draft(
                draft, actor="医学监查员", created_at=NOW
            )


def _publish(factory, source_input, draft, spans, revision_id, key, **kwargs):
    service = ProtocolPublicationService(factory, now=lambda: NOW)
    return service.publish(
        ProtocolPublicationRequest(
            idempotency_key=key,
            draft_revision_id=revision_id,
            source_input=source_input,
            source_spans=spans,
            actor="医学监查员",
            published_at=NOW,
            **kwargs,
        )
    )


def test_first_publication_rejects_override_version_id(slice4_env) -> None:
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    with pytest.raises(PublicationLineageError) as exc_info:
        _publish(
            factory,
            source_input,
            draft,
            spans,
            r1.revision_id,
            "pub-override",
            protocol_version_id="protocol-version-999",
        )
    assert exc_info.value.code == "first_publish_cannot_override_version"


def test_republish_rejects_detached_version_id(slice4_env) -> None:
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    _publish(factory, source_input, draft, spans, r1.revision_id, "pub-base")
    # 重新解构草稿携带新版本 id，但请求给出脱离草稿/输入的另一个 id。
    revised = draft.model_copy(deep=True)
    revised.draft_id = "draft-v2-detached"
    revised.protocol_version_id = "protocol-version-2"
    revised_input = source_input.model_copy(deep=True)
    revised_input.protocol_version_id = "protocol-version-2"
    rv2 = _save_revision(factory, revised)
    with pytest.raises(PublicationLineageError) as exc_info:
        _publish(
            factory,
            revised_input,
            revised,
            spans,
            rv2.revision_id,
            "pub-detached",
            project_id="project-1",
            protocol_version_id="protocol-version-999",
        )
    assert exc_info.value.code == "republish_version_mismatch"
    # 不携带版本 id 时从草稿/输入派生（已校验一致），允许重新发布。
    derived = _publish(
        factory,
        revised_input,
        revised,
        spans,
        rv2.revision_id,
        "pub-derived",
        project_id="project-1",
    )
    assert derived.protocol_version_id == "protocol-version-2"


def test_published_authority_has_per_requirement_source_anchors(
    slice4_env,
) -> None:
    """权威记录必须逐条保存全部资料要求来源锚点（含子规则要求）。"""
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    result = _publish(factory, source_input, draft, spans, r1.revision_id, "pub-anchors")
    with factory() as session:
        authority = AppendRepository(session, AUTHORITY_RECORD_CONFIG).get(
            result.authority_record_id
        )
    all_requirement_ids = {
        req.requirement_id
        for rule in authority.official_rules
        for component in rule.components
        for req in component.evidence_requirements
    } | {
        req.requirement_id
        for req in authority.procedure_evidence_requirements
    }
    # 闭包：每条资料要求（含子规则要求）都有来源锚点，且锚点绑定当前版本。
    assert set(authority.requirement_source_anchor_refs) == all_requirement_ids
    prefix = f"{result.protocol_version_id}:"
    assert all(
        ref.startswith(prefix)
        for refs in authority.requirement_source_anchor_refs.values()
        for ref in refs
    )


def test_successor_publication_reruns_diff_integrity_with_previous(
    slice4_env,
) -> None:
    """后继 revision 发布必须携带前序草稿与声明差异复跑 diff_integrity。"""
    from app.services.protocol_draft_service import ProtocolDraftService as DraftSvc

    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    with factory() as session:
        with session.begin():
            r1 = DraftSvc(session).save_initial_draft(
                draft, actor="医学监查员", created_at=NOW
            )
            edited = draft.model_copy(deep=True)
            edited.proposed_workflow_stages[0] = (
                edited.proposed_workflow_stages[0].model_copy(
                    update={"display_name": "筛选期审核（修订）"}
                )
            )
            r2 = DraftSvc(session).apply_manual_edit(
                edited,
                expected_revision_id=r1.revision_id,
                actor="医学监查员",
                created_at=NOW,
            )
            r2_id = r2.revision_id
    # 后继 revision 发布成功：门禁以 previous_draft + declared_diff 复跑通过。
    result = _publish(
        factory,
        source_input,
        draft,
        spans,
        r2_id,
        "pub-successor",
        project_id=None,
    )
    assert result.published_revision_id == r2_id


# ---------------------------------------------------------------------------
# 仓储：防孤儿模板与断裂草稿链
# ---------------------------------------------------------------------------


def test_ghost_expectation_template_is_rejected(session) -> None:
    from app.domain.contracts.evidence import EvidenceExpectationTemplate
    from app.projections.evidence_expectation_templates import (
        template_identity,
        template_projection_sha256,
    )
    from app.storage.repositories import save_expectation_templates

    _source_input, draft, _spans = confirmed_fixture()
    ghost = EvidenceExpectationTemplate(
        template_id=template_identity("ruleset:ghost", 1, "req-ghost"),
        rule_set_id="ruleset:ghost",
        rule_set_revision=1,
        requirement_id="req-ghost",
        due_stage=ReviewStage.SCREENING,
        study_phase=draft.selected_phase,
        workflow_stage_id=None,
        fact_type="方案要求事实",
        description="孤儿模板",
        projection_sha256=template_projection_sha256(
            rule_set_id="ruleset:ghost",
            revision=1,
            requirement_id="req-ghost",
            due_stage=ReviewStage.SCREENING,
            study_phase=draft.selected_phase,
            workflow_stage_id=None,
            fact_type="方案要求事实",
            required_source_types=[],
            requires_contemporaneous_objective_source=False,
            allows_screening_record_transcription=True,
            description="孤儿模板",
        ),
        created_at=NOW,
    )
    with pytest.raises(Exception, match="RuleSet"):
        save_expectation_templates(session, [ghost])


def test_broken_draft_chain_is_rejected(session) -> None:
    from app.domain.contracts.protocol_drafts import (
        DraftRevisionReason,
        ProtocolDraftRevision,
    )
    from app.domain.publication import canonical_hash

    _source_input, draft, _spans = confirmed_fixture()
    draft = draft.model_copy(update={"draft_id": "chain-a"})
    repo = ProtocolDraftRevisionRepository(session)
    with session.begin():
        r1 = ProtocolDraftRevision(
            revision_id="draft-revision:chain-a:1",
            draft_id="chain-a",
            revision_number=1,
            project_id=draft.project_id,
            protocol_version_id=draft.protocol_version_id,
            study_phase=draft.selected_phase,
            status=DraftRevisionStatus.SAVED,
            reason=DraftRevisionReason.INITIAL_SAVE,
            actor="医学监查员",
            content=draft,
            content_sha256=canonical_hash(draft.model_dump(mode="json")),
            created_at=NOW,
        )
        repo.save(r1)
        # 跨草稿前序：b 的 revision 2 引用 a 的 revision 1。
        cross_draft_content = draft.model_copy(
            update={
                "draft_id": "chain-b",
                "draft_revision": 2,
                "previous_draft_id": "chain-b",
            }
        )
        cross_draft = ProtocolDraftRevision(
            revision_id="draft-revision:chain-b:2",
            draft_id="chain-b",
            revision_number=2,
            previous_revision_id=r1.revision_id,
            project_id=draft.project_id,
            protocol_version_id=draft.protocol_version_id,
            study_phase=draft.selected_phase,
            status=DraftRevisionStatus.SAVED,
            reason=DraftRevisionReason.MANUAL_EDIT,
            actor="医学监查员",
            content=cross_draft_content,
            content_sha256=canonical_hash(
                cross_draft_content.model_dump(mode="json")
            ),
            created_at=NOW,
        )
        with pytest.raises(ScopeViolationError, match="不属于同一草稿"):
            repo.save(cross_draft)
        # 非紧邻前序：revision 3 直接引用 revision 1。
        non_adjacent_content = draft.model_copy(
            update={"draft_revision": 3, "previous_draft_id": "chain-a"}
        )
        non_adjacent = ProtocolDraftRevision(
            revision_id="draft-revision:chain-a:3",
            draft_id="chain-a",
            revision_number=3,
            previous_revision_id=r1.revision_id,
            project_id=draft.project_id,
            protocol_version_id=draft.protocol_version_id,
            study_phase=draft.selected_phase,
            status=DraftRevisionStatus.SAVED,
            reason=DraftRevisionReason.MANUAL_EDIT,
            actor="医学监查员",
            content=non_adjacent_content,
            content_sha256=canonical_hash(
                non_adjacent_content.model_dump(mode="json")
            ),
            created_at=NOW,
        )
        with pytest.raises(ScopeViolationError, match="不是紧邻前序"):
            repo.save(non_adjacent)
