"""已保存方案草稿 revision 服务（Phase 3 切片 4）。

每次 Agent 输出、已保存的手工编辑或反馈修订都形成一个新的不可变 revision；
历史只追加，取消与发布都只做生命周期状态转移，绝不物理删除任何已保存
revision。乐观并发通过「后继 revision 必须指向当前链头」实现：双标签页或
并发编辑中后提交者收到带差异信封的 :class:`StaleRevisionError`。

编辑边界（PRD/设计书）：手工或反馈编辑只能做来源忠实的纠错，不能增删冻结
目录成员、不能改写流程访视结构；解释性澄清反馈不能改变方案阈值或布尔逻辑。
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from app.domain.contracts.agent_io import ProtocolDeconstructionDraft
from app.domain.contracts.protocol_drafts import (
    DraftFeedbackKind,
    DraftRevisionReason,
    DraftRevisionStatus,
    ProtocolDraftRevision,
    ProtocolDraftRevisionDiff,
)
from app.domain.publication import canonical_hash
from app.storage.concurrency import StaleRevisionError
from app.storage.repositories import (
    NotFoundError,
    ProtocolDraftRevisionRepository,
)


class DraftEditBoundaryError(ValueError):
    """编辑越过了冻结目录/流程结构/解释材料权威边界。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class DuplicateDraftError(ValueError):
    """同一 draft_id 重复初始保存。"""


def _fail_boundary(code: str, message: str) -> None:
    raise DraftEditBoundaryError(code, message)


# ---------------------------------------------------------------------------
# 结构化差异（设计书 §10：按官方编号/稳定键对齐，不依赖随机 ID）
# ---------------------------------------------------------------------------


def _hash_map(values: Sequence[Any], key) -> dict[str, str]:
    return {key(item): canonical_hash(item.model_dump(mode="json")) for item in values}


def _changed_keys(old: dict[str, str], new: dict[str, str]) -> list[str]:
    return sorted(key for key in old if key in new and old[key] != new[key])


def compute_draft_diff(
    previous: ProtocolDeconstructionDraft | None,
    current: ProtocolDeconstructionDraft,
) -> ProtocolDraftRevisionDiff:
    """按官方编号/稳定 ID 对齐计算两个草稿的结构化差异。"""
    if previous is None:
        return ProtocolDraftRevisionDiff(
            added_rule_codes=[rule.official_code for rule in current.proposed_rules],
            added_workflow_stage_ids=[
                stage.workflow_stage_id for stage in current.proposed_workflow_stages
            ],
            changed_component_ids=[
                component.rule_component_id
                for rule in current.proposed_rules
                for component in rule.components
            ],
            changed_requirement_ids=[
                item.proposed_requirement.requirement_id
                for item in current.evidence_requirement_drafts
            ],
            changed_procedure_mapping_ids=[
                mapping.catalog_item_id
                for mapping in current.procedure_catalog_mappings
            ],
        )

    old_rules = _hash_map(previous.proposed_rules, lambda rule: rule.official_code)
    new_rules = _hash_map(current.proposed_rules, lambda rule: rule.official_code)
    added_rule_codes = sorted(set(new_rules) - set(old_rules))
    removed_rule_codes = sorted(set(old_rules) - set(new_rules))
    modified_rule_codes = _changed_keys(old_rules, new_rules)

    old_stages = _hash_map(
        previous.proposed_workflow_stages, lambda stage: stage.workflow_stage_id
    )
    new_stages = _hash_map(
        current.proposed_workflow_stages, lambda stage: stage.workflow_stage_id
    )
    added_workflow_stage_ids = sorted(set(new_stages) - set(old_stages))
    removed_workflow_stage_ids = sorted(set(old_stages) - set(new_stages))
    modified_workflow_stage_ids = _changed_keys(old_stages, new_stages)

    old_components = {
        component.rule_component_id: canonical_hash(
            component.model_dump(mode="json")
        )
        for rule in previous.proposed_rules
        for component in rule.components
    }
    new_components = {
        component.rule_component_id: canonical_hash(
            component.model_dump(mode="json")
        )
        for rule in current.proposed_rules
        for component in rule.components
    }
    changed_component_ids = _changed_keys(old_components, new_components)

    old_requirements = _hash_map(
        previous.evidence_requirement_drafts, lambda item: item.draft_requirement_id
    )
    new_requirements = _hash_map(
        current.evidence_requirement_drafts, lambda item: item.draft_requirement_id
    )
    changed_requirement_ids = _changed_keys(old_requirements, new_requirements)

    old_mappings = _hash_map(
        previous.procedure_catalog_mappings, lambda item: item.catalog_item_id
    )
    new_mappings = _hash_map(
        current.procedure_catalog_mappings, lambda item: item.catalog_item_id
    )
    changed_procedure_mapping_ids = _changed_keys(old_mappings, new_mappings)

    old_source_scope = canonical_hash(
        sorted(previous.source_refs)
        + sorted(
            span
            for item in previous.procedure_catalog_mappings
            for span in item.source_span_ids
        )
    )
    new_source_scope = canonical_hash(
        sorted(current.source_refs)
        + sorted(
            span
            for item in current.procedure_catalog_mappings
            for span in item.source_span_ids
        )
    )
    # 流程访视结构 = (节点 ID, 阶段, 到期资料要求) + (必做项目映射绑定)；
    # 展示名等外观字段变化不计为访视改写。
    previous_stage_structure = {
        (stage.workflow_stage_id, stage.stage.value): tuple(
            stage.due_requirement_ids
        )
        for stage in previous.proposed_workflow_stages
    }
    current_stage_structure = {
        (stage.workflow_stage_id, stage.stage.value): tuple(
            stage.due_requirement_ids
        )
        for stage in current.proposed_workflow_stages
    }
    previous_mapping_bindings = {
        (mapping.catalog_item_id, mapping.proposed_workflow_stage_id): tuple(
            mapping.proposed_requirement_ids
        )
        for mapping in previous.procedure_catalog_mappings
    }
    current_mapping_bindings = {
        (mapping.catalog_item_id, mapping.proposed_workflow_stage_id): tuple(
            mapping.proposed_requirement_ids
        )
        for mapping in current.procedure_catalog_mappings
    }
    return ProtocolDraftRevisionDiff(
        added_rule_codes=added_rule_codes,
        removed_rule_codes=removed_rule_codes,
        modified_rule_codes=modified_rule_codes,
        added_workflow_stage_ids=added_workflow_stage_ids,
        removed_workflow_stage_ids=removed_workflow_stage_ids,
        modified_workflow_stage_ids=modified_workflow_stage_ids,
        changed_component_ids=changed_component_ids,
        changed_requirement_ids=changed_requirement_ids,
        changed_procedure_mapping_ids=changed_procedure_mapping_ids,
        source_scope_changed=old_source_scope != new_source_scope,
        workflow_visit_rewritten=(
            previous_stage_structure != current_stage_structure
            or previous_mapping_bindings != current_mapping_bindings
        ),
        clarification_semantics_changed=_semantics_changed(previous, current),
    )


def _semantics_changed(
    previous: ProtocolDeconstructionDraft,
    current: ProtocolDeconstructionDraft,
) -> bool:
    """比较组件表达式/例外/阈值/逻辑的规范哈希（不含描述性文本）。"""

    def semantic_map(draft: ProtocolDeconstructionDraft) -> dict[str, str]:
        result: dict[str, str] = {}
        for rule in draft.proposed_rules:
            for component in rule.components:
                payload = {
                    "expression": component.expression.model_dump(mode="json"),
                    "exception": (
                        component.exception_expression.model_dump(mode="json")
                        if component.exception_expression is not None
                        else None
                    ),
                    "evidence": [
                        {
                            "requirement_id": requirement.requirement_id,
                            "fact_type": requirement.fact_type,
                            "due_stage": requirement.due_stage.value,
                        }
                        for requirement in component.evidence_requirements
                    ],
                }
                result[component.rule_component_id] = canonical_hash(payload)
        return result

    return semantic_map(previous) != semantic_map(current)


# ---------------------------------------------------------------------------
# 编辑边界（冻结目录 / 流程结构 / 解释材料权威）
# ---------------------------------------------------------------------------


def enforce_draft_edit_boundary(
    previous: ProtocolDeconstructionDraft,
    current: ProtocolDeconstructionDraft,
    *,
    feedback_kind: DraftFeedbackKind | None,
) -> None:
    """校验一次编辑是否越过权威边界。

    - 任何编辑不得增删冻结目录成员或改写流程访视结构；
    - 澄清反馈（解释材料）不得改变阈值或布尔逻辑；
    - 原文理解纠错与手工编辑允许修正语义，但必须保留来源绑定
      （由 ProtocolDeconstructionGate 的 source_coverage 把关）。
    """
    previous_parent_items = {
        item.catalog_item_id for item in previous.parent_catalog_mappings
    }
    current_parent_items = {
        item.catalog_item_id for item in current.parent_catalog_mappings
    }
    if previous_parent_items != current_parent_items:
        _fail_boundary(
            "FROZEN_PARENT_RULE_MEMBERSHIP_CHANGED",
            "编辑不得增删冻结的官方父规则目录成员",
        )
    previous_procedure_items = {
        item.catalog_item_id for item in previous.procedure_catalog_mappings
    }
    current_procedure_items = {
        item.catalog_item_id for item in current.procedure_catalog_mappings
    }
    if previous_procedure_items != current_procedure_items:
        _fail_boundary(
            "FROZEN_PROCEDURE_MEMBERSHIP_CHANGED",
            "编辑不得增删冻结的基线及以前必做项目录成员",
        )
    previous_stage_structure = {
        (stage.workflow_stage_id, stage.stage.value): tuple(
            stage.due_requirement_ids
        )
        for stage in previous.proposed_workflow_stages
    }
    current_stage_structure = {
        (stage.workflow_stage_id, stage.stage.value): tuple(
            stage.due_requirement_ids
        )
        for stage in current.proposed_workflow_stages
    }
    if previous_stage_structure != current_stage_structure:
        _fail_boundary(
            "WORKFLOW_VISIT_REWRITTEN",
            "编辑不得增删或重命名流程访视节点、不得改写到期资料要求；"
            "同一操作在筛选与基线必须保持两个实例",
        )
    previous_mapping_bindings = {
        (mapping.catalog_item_id, mapping.proposed_workflow_stage_id): tuple(
            mapping.proposed_requirement_ids
        )
        for mapping in previous.procedure_catalog_mappings
    }
    current_mapping_bindings = {
        (mapping.catalog_item_id, mapping.proposed_workflow_stage_id): tuple(
            mapping.proposed_requirement_ids
        )
        for mapping in current.procedure_catalog_mappings
    }
    if previous_mapping_bindings != current_mapping_bindings:
        _fail_boundary(
            "WORKFLOW_VISIT_REWRITTEN",
            "编辑不得改写必做项目与资料要求/到期访视的绑定",
        )
    previous_requirement_bindings = {
        (item.proposed_requirement.requirement_id, item.procedure_catalog_item_id)
        for item in previous.evidence_requirement_drafts
        if item.procedure_catalog_item_id is not None
    }
    current_requirement_bindings = {
        (item.proposed_requirement.requirement_id, item.procedure_catalog_item_id)
        for item in current.evidence_requirement_drafts
        if item.procedure_catalog_item_id is not None
    }
    if previous_requirement_bindings != current_requirement_bindings:
        _fail_boundary(
            "WORKFLOW_VISIT_REWRITTEN",
            "编辑不得改写必做项目与资料要求/到期访视的绑定",
        )
    if feedback_kind == DraftFeedbackKind.CLARIFICATION:
        diff = compute_draft_diff(previous, current)
        if diff.clarification_semantics_changed or diff.workflow_visit_rewritten:
            _fail_boundary(
                "CLARIFICATION_ALTERS_SEMANTICS",
                "解释性澄清只能附着在说明层，不得改变方案阈值、布尔逻辑或流程结构",
            )


# ---------------------------------------------------------------------------
# revision 服务
# ---------------------------------------------------------------------------


def _revision_id(draft_id: str, revision_number: int) -> str:
    return f"draft-revision:{draft_id}:{revision_number}"


class ProtocolDraftService:
    """已保存草稿 revision 的创建、生命周期与恢复。"""

    def __init__(
        self,
        session,
        *,
        revision_repository: ProtocolDraftRevisionRepository | None = None,
    ) -> None:
        self.session = session
        self.revisions = revision_repository or ProtocolDraftRevisionRepository(session)

    # -- 创建 -------------------------------------------------------------

    def save_initial_draft(
        self,
        draft: ProtocolDeconstructionDraft,
        *,
        actor: str,
        created_at: datetime,
    ) -> ProtocolDraftRevision:
        if draft.draft_revision != 1:
            raise ValueError("初始保存的草稿必须是首稿（draft_revision=1）")
        if self.revisions.count(draft.draft_id) > 0:
            raise DuplicateDraftError(
                f"草稿 {draft.draft_id} 已有保存的 revision，不能重复初始保存"
            )
        revision = ProtocolDraftRevision(
            revision_id=_revision_id(draft.draft_id, 1),
            draft_id=draft.draft_id,
            revision_number=1,
            project_id=draft.project_id,
            protocol_version_id=draft.protocol_version_id,
            study_phase=draft.selected_phase,
            status=DraftRevisionStatus.SAVED,
            reason=DraftRevisionReason.INITIAL_SAVE,
            actor=actor,
            content=draft,
            content_sha256=canonical_hash(draft.model_dump(mode="json")),
            diff=compute_draft_diff(None, draft),
            created_at=created_at,
        )
        return self.revisions.save(revision)

    def apply_manual_edit(
        self,
        draft: ProtocolDeconstructionDraft,
        *,
        expected_revision_id: str,
        actor: str,
        created_at: datetime,
    ) -> ProtocolDraftRevision:
        return self._append_revision(
            draft,
            expected_revision_id=expected_revision_id,
            reason=DraftRevisionReason.MANUAL_EDIT,
            feedback_kind=None,
            feedback_note=None,
            actor=actor,
            created_at=created_at,
        )

    def apply_feedback(
        self,
        draft: ProtocolDeconstructionDraft,
        *,
        expected_revision_id: str,
        feedback_kind: DraftFeedbackKind,
        feedback_note: str | None,
        actor: str,
        created_at: datetime,
    ) -> ProtocolDraftRevision:
        if feedback_kind == DraftFeedbackKind.CLARIFICATION and not feedback_note:
            raise ValueError("澄清反馈必须提供解释说明文本")
        reason = (
            DraftRevisionReason.CLARIFICATION_FEEDBACK
            if feedback_kind == DraftFeedbackKind.CLARIFICATION
            else DraftRevisionReason.SOURCE_ERROR_FEEDBACK
        )
        return self._append_revision(
            draft,
            expected_revision_id=expected_revision_id,
            reason=reason,
            feedback_kind=feedback_kind,
            feedback_note=feedback_note,
            actor=actor,
            created_at=created_at,
        )

    def restore_draft(
        self,
        *,
        draft_id: str,
        expected_revision_id: str,
        restore_from_revision_id: str,
        actor: str,
        created_at: datetime,
    ) -> ProtocolDraftRevision:
        """从任意已保存 revision 恢复：创建审计后继，不覆盖历史。"""
        head = self._require_head(draft_id, expected_revision_id)
        source = self.revisions.get(restore_from_revision_id)
        if source.draft_id != draft_id:
            raise NotFoundError(
                f"revision {restore_from_revision_id} 不属于草稿 {draft_id}"
            )
        restored_content = source.content.model_copy(deep=True)
        next_number = head.revision_number + 1
        revision = ProtocolDraftRevision(
            revision_id=_revision_id(draft_id, next_number),
            draft_id=draft_id,
            revision_number=next_number,
            previous_revision_id=head.revision_id,
            project_id=head.project_id,
            protocol_version_id=head.protocol_version_id,
            study_phase=head.study_phase,
            status=DraftRevisionStatus.RESTORED_FROM,
            reason=DraftRevisionReason.RESTORE,
            actor=actor,
            content=restored_content,
            content_sha256=canonical_hash(restored_content.model_dump(mode="json")),
            diff=compute_draft_diff(head.content, restored_content),
            created_at=created_at,
        )
        return self.revisions.save(revision)

    # -- 生命周期 ---------------------------------------------------------

    def save_draft(
        self,
        *,
        draft_id: str,
        expected_revision_id: str,
    ) -> ProtocolDraftRevision:
        """把当前链头显式标记为已保存（幂等；历史不物理删除）。"""
        head = self._require_head(draft_id, expected_revision_id)
        if head.status == DraftRevisionStatus.SAVED:
            return head
        return self._transition_status(head, DraftRevisionStatus.SAVED)

    def cancel_draft(
        self,
        *,
        draft_id: str,
        expected_revision_id: str,
    ) -> ProtocolDraftRevision:
        """取消本次编辑会话：链头标记为已取消，可恢复，不物理删除。"""
        head = self._require_head(draft_id, expected_revision_id)
        return self._transition_status(head, DraftRevisionStatus.CANCELLED)

    def mark_published(
        self,
        *,
        draft_id: str,
        expected_revision_id: str,
    ) -> ProtocolDraftRevision:
        """发布成功后把链头标记为已发布（同一事务内调用）。"""
        head = self._require_head(draft_id, expected_revision_id)
        return self._transition_status(head, DraftRevisionStatus.PUBLISHED)

    # -- 内部 -------------------------------------------------------------

    def _append_revision(
        self,
        draft: ProtocolDeconstructionDraft,
        *,
        expected_revision_id: str,
        reason: DraftRevisionReason,
        feedback_kind: DraftFeedbackKind | None,
        feedback_note: str | None,
        actor: str,
        created_at: datetime,
    ) -> ProtocolDraftRevision:
        head = self._require_head(draft.draft_id, expected_revision_id)
        enforce_draft_edit_boundary(
            head.content, draft, feedback_kind=feedback_kind
        )
        next_number = head.revision_number + 1
        revision = ProtocolDraftRevision(
            revision_id=_revision_id(draft.draft_id, next_number),
            draft_id=draft.draft_id,
            revision_number=next_number,
            previous_revision_id=head.revision_id,
            project_id=head.project_id,
            protocol_version_id=head.protocol_version_id,
            study_phase=head.study_phase,
            status=DraftRevisionStatus.SAVED,
            reason=reason,
            feedback_kind=feedback_kind,
            feedback_note=feedback_note,
            actor=actor,
            content=draft,
            content_sha256=canonical_hash(draft.model_dump(mode="json")),
            diff=compute_draft_diff(head.content, draft),
            created_at=created_at,
        )
        return self.revisions.save(revision)

    def _require_head(
        self,
        draft_id: str,
        expected_revision_id: str,
    ) -> ProtocolDraftRevision:
        head = self.revisions.get_head(draft_id)
        if head is not None and head.revision_id == expected_revision_id:
            return head
        raise _head_error(
            draft_id=draft_id,
            expected_revision_id=expected_revision_id,
            head=head,
        )

    def _transition_status(
        self,
        revision: ProtocolDraftRevision,
        status: DraftRevisionStatus,
    ) -> ProtocolDraftRevision:
        updated = revision.model_copy(update={"status": status})
        return self.revisions.update_status(updated)


def _head_error(
    *,
    draft_id: str,
    expected_revision_id: str,
    head: ProtocolDraftRevision | None,
) -> StaleRevisionError:
    current_number = head.revision_number if head is not None else 0
    return StaleRevisionError(
        entity_type="ProtocolDraftRevision",
        entity_id=draft_id,
        expected_revision=current_number,
        current_revision=current_number,
        field_diff={},
        current_record=head,
    )


__all__ = [
    "DraftEditBoundaryError",
    "DuplicateDraftError",
    "ProtocolDraftService",
    "compute_draft_diff",
    "enforce_draft_edit_boundary",
]
