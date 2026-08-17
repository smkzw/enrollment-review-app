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
    # 流程访视结构 = (节点 ID, 阶段, 访视实例, 时间窗, 到期资料要求)
    # + (必做项目映射绑定)；展示名等外观字段变化不计为访视改写。
    previous_stage_structure = {
        (
            stage.workflow_stage_id,
            stage.stage.value,
            stage.visit_instance,
            stage.visit_window,
        ): tuple(stage.due_requirement_ids)
        for stage in previous.proposed_workflow_stages
    }
    current_stage_structure = {
        (
            stage.workflow_stage_id,
            stage.stage.value,
            stage.visit_instance,
            stage.visit_window,
        ): tuple(stage.due_requirement_ids)
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
    """比较组件表达式/例外/阈值/逻辑及临床证据语义的规范哈希。

    临床证据语义包括：fact_type、due_stage、required_source_types、
    允许筛选记录转录、要求同期客观来源与描述文本——澄清反馈不得改变这些
    权威语义，仅来源忠实纠错或手工编辑可调整（发布前仍过确定性门禁）。
    """

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
                            "required_source_types": sorted(
                                set(requirement.required_source_types)
                            ),
                            "allows_screening_record_transcription": (
                                requirement.allows_screening_record_transcription
                            ),
                            "requires_contemporaneous_objective_source": (
                                requirement.requires_contemporaneous_objective_source
                            ),
                            "description": requirement.description,
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

    - 任何编辑不得增删冻结目录成员、改写流程访视结构或换绑目录来源；
    - 澄清反馈（解释材料）不得改变阈值、布尔逻辑、临床证据语义或来源绑定；
    - 原文理解纠错与手工编辑允许修正语义与来源映射，但必须保留冻结目录
      成员与流程结构（由 ProtocolDeconstructionGate 的 source_coverage /
      parent_catalog / workflow_coverage 把关）。
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
    # 父规则映射来源属于冻结目录身份的一部分：换绑即破坏「目录成员不可增删」。
    previous_parent_sources = {
        item.catalog_item_id: tuple(sorted(item.source_span_ids))
        for item in previous.parent_catalog_mappings
    }
    current_parent_sources = {
        item.catalog_item_id: tuple(sorted(item.source_span_ids))
        for item in current.parent_catalog_mappings
    }
    if previous_parent_sources != current_parent_sources:
        _fail_boundary(
            "PARENT_SOURCE_REBOUND",
            "编辑不得换绑官方父规则映射的方案来源定位",
        )
    previous_stage_structure = {
        (
            stage.workflow_stage_id,
            stage.stage.value,
            stage.visit_instance,
            stage.visit_window,
        ): tuple(stage.due_requirement_ids)
        for stage in previous.proposed_workflow_stages
    }
    current_stage_structure = {
        (
            stage.workflow_stage_id,
            stage.stage.value,
            stage.visit_instance,
            stage.visit_window,
        ): tuple(stage.due_requirement_ids)
        for stage in current.proposed_workflow_stages
    }
    if previous_stage_structure != current_stage_structure:
        _fail_boundary(
            "WORKFLOW_VISIT_REWRITTEN",
            "编辑不得增删或重命名流程访视节点、不得改写访视实例/时间窗/到期"
            "资料要求；同一操作在筛选与基线必须保持两个实例",
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
    diff = compute_draft_diff(previous, current)
    if feedback_kind == DraftFeedbackKind.CLARIFICATION:
        if diff.clarification_semantics_changed or diff.workflow_visit_rewritten:
            _fail_boundary(
                "CLARIFICATION_ALTERS_SEMANTICS",
                "解释性澄清只能附着在说明层，不得改变方案阈值、布尔逻辑、"
                "临床证据语义或流程结构",
            )
        # 澄清反馈不得改变任何来源绑定（组件/资料要求摘录与来源范围）。
        if _source_bindings_changed(previous, current):
            _fail_boundary(
                "CLARIFICATION_ALTERS_SOURCE_BINDING",
                "解释性澄清不得改写子规则或资料要求的方案来源绑定",
            )


def _source_bindings_changed(
    previous: ProtocolDeconstructionDraft,
    current: ProtocolDeconstructionDraft,
) -> bool:
    """组件/资料要求来源绑定（source_refs 与摘录）是否被改写。"""
    previous_component_sources = {
        item.draft_component_id: (
            tuple(sorted(item.source_refs)),
            tuple(item.source_excerpts),
        )
        for item in previous.component_drafts
    }
    current_component_sources = {
        item.draft_component_id: (
            tuple(sorted(item.source_refs)),
            tuple(item.source_excerpts),
        )
        for item in current.component_drafts
    }
    if previous_component_sources != current_component_sources:
        return True
    previous_requirement_sources = {
        item.draft_requirement_id: tuple(sorted(item.source_refs))
        for item in previous.evidence_requirement_drafts
    }
    current_requirement_sources = {
        item.draft_requirement_id: tuple(sorted(item.source_refs))
        for item in current.evidence_requirement_drafts
    }
    if previous_requirement_sources != current_requirement_sources:
        return True
    return False


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
        """从任意已保存 revision 恢复：创建审计后继，不覆盖历史。

        恢复只能从明确状态创建后继：已取消/已保存/已恢复的链头可恢复，
        已发布的链头不可恢复（发布后形成正式规则版本，旧版本供历史追溯）。
        """
        head = self._require_head(draft_id, expected_revision_id)
        if head.status == DraftRevisionStatus.PUBLISHED:
            raise DraftEditBoundaryError(
                "DRAFT_PUBLISHED",
                "已发布的草稿 revision 不能恢复或覆盖；请基于新草稿重新解构。",
            )
        source = self.revisions.get(restore_from_revision_id)
        if source.draft_id != draft_id:
            raise NotFoundError(
                f"revision {restore_from_revision_id} 不属于草稿 {draft_id}"
            )
        restored_content = source.content.model_copy(deep=True)
        next_number = head.revision_number + 1
        # 规范化内层草稿链：恢复后继的 draft_revision 与 previous_draft_id
        # 指向链头（而非被恢复的旧 revision），与外层链一致。
        restored_content = restored_content.model_copy(
            update={
                "draft_revision": next_number,
                "previous_draft_id": head.content.draft_id,
            }
        )
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
        if head.status == DraftRevisionStatus.PUBLISHED:
            raise DraftEditBoundaryError(
                "DRAFT_PUBLISHED",
                "已发布的草稿 revision 不能再保存或编辑。",
            )
        if head.status == DraftRevisionStatus.CANCELLED:
            raise DraftEditBoundaryError(
                "DRAFT_CANCELLED",
                "已取消的草稿不能直接保存；请先恢复后再保存。",
            )
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
        if head.status == DraftRevisionStatus.PUBLISHED:
            raise DraftEditBoundaryError(
                "DRAFT_PUBLISHED",
                "已发布的草稿 revision 不能取消。",
            )
        if head.status == DraftRevisionStatus.CANCELLED:
            raise DraftEditBoundaryError(
                "DRAFT_CANCELLED",
                "当前链头已处于取消状态；如需继续请恢复。",
            )
        return self._transition_status(head, DraftRevisionStatus.CANCELLED)

    def _mark_published(
        self,
        *,
        draft_id: str,
        expected_revision_id: str,
    ) -> ProtocolDraftRevision:
        """发布成功后才由发布服务在发布事务内调用的内部路径。

        只能从 已保存/草稿 状态转移到 已发布；已取消、已恢复或已发布的
        链头都不能被直接标记为已发布（取消必须走恢复，发布必须过发布事务）。
        """
        head = self._require_head(draft_id, expected_revision_id)
        if head.status not in {
            DraftRevisionStatus.SAVED,
            DraftRevisionStatus.DRAFT,
        }:
            raise DraftEditBoundaryError(
                "DRAFT_NOT_PUBLISHABLE",
                "只有已保存（或草稿）状态的链头能被发布事务标记为已发布；"
                f"当前状态 {head.status.value} 不允许直接发布。",
            )
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
        if head.status == DraftRevisionStatus.CANCELLED:
            raise DraftEditBoundaryError(
                "DRAFT_CANCELLED",
                "已取消的草稿不能直接继续编辑；请先恢复后再修改。",
            )
        if head.status == DraftRevisionStatus.PUBLISHED:
            raise DraftEditBoundaryError(
                "DRAFT_PUBLISHED",
                "已发布的草稿 revision 不能继续编辑；请基于新草稿重新解构。",
            )
        enforce_draft_edit_boundary(
            head.content, draft, feedback_kind=feedback_kind
        )
        next_number = head.revision_number + 1
        # 规范化内层草稿链：content.draft_revision 与 previous_draft_id 必须
        # 与外层 ProtocolDraftRevision 链一致，杜绝「外层 revision=2、内层仍=1」
        # 的不一致状态。
        normalized_content = draft.model_copy(
            update={
                "draft_revision": next_number,
                "previous_draft_id": head.content.draft_id,
            }
        )
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
            content=normalized_content,
            content_sha256=canonical_hash(normalized_content.model_dump(mode="json")),
            diff=compute_draft_diff(head.content, normalized_content),
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
            self.revisions,
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


def mark_revision_published(
    revisions: ProtocolDraftRevisionRepository,
    *,
    draft_id: str,
    expected_revision_id: str,
) -> ProtocolDraftRevision:
    """发布服务专用内部入口：绕过公开服务面标记链头为已发布。

    公开的 :class:`ProtocolDraftService` 不再暴露 ``mark_published``；
    只有发布事务（经 :class:`ProtocolPublicationService`）调用本函数，
    并在同一事务内完成全部正式写入与幂等记录，杜绝外部绕过发布事务
    直接给草稿打上已发布状态。
    """
    service = ProtocolDraftService(
        revisions.session, revision_repository=revisions
    )
    return service._mark_published(
        draft_id=draft_id,
        expected_revision_id=expected_revision_id,
    )


def _draft_diff_as_field_changes(
    submitted: ProtocolDeconstructionDraft,
    current: ProtocolDeconstructionDraft,
) -> dict[str, "FieldChange"]:
    """把结构化草稿差异转换为 StaleRevisionError 的字段差异信封。

    每个差异项直接取两份草稿中的真实结构化快照，给出 current（链头现值）
    与 submitted（提交方值）。不能用空数组或布尔量代替内容，否则前端会把
    “链头新增”误呈现为“提交方新增”，也无法让用户判断应保留哪一版。
    """
    from app.storage.concurrency import FieldChange

    diff = compute_draft_diff(submitted, current)
    changes: dict[str, FieldChange] = {}

    def _dump(item: Any | None) -> Any | None:
        return item.model_dump(mode="json") if item is not None else None

    def _index(values: Sequence[Any], key) -> dict[str, Any]:
        return {key(item): item for item in values}

    submitted_rules = _index(submitted.proposed_rules, lambda item: item.official_code)
    current_rules = _index(current.proposed_rules, lambda item: item.official_code)
    changed_rule_codes = sorted(
        set(diff.added_rule_codes)
        | set(diff.removed_rule_codes)
        | set(diff.modified_rule_codes)
    )
    for code in changed_rule_codes:
        changes[f"rule:{code}"] = FieldChange(
            current=_dump(current_rules.get(code)),
            submitted=_dump(submitted_rules.get(code)),
        )

    submitted_stages = _index(
        submitted.proposed_workflow_stages, lambda item: item.workflow_stage_id
    )
    current_stages = _index(
        current.proposed_workflow_stages, lambda item: item.workflow_stage_id
    )
    changed_stage_ids = sorted(
        set(diff.added_workflow_stage_ids)
        | set(diff.removed_workflow_stage_ids)
        | set(diff.modified_workflow_stage_ids)
    )
    for stage_id in changed_stage_ids:
        changes[f"workflow_stage:{stage_id}"] = FieldChange(
            current=_dump(current_stages.get(stage_id)),
            submitted=_dump(submitted_stages.get(stage_id)),
        )

    def _components(draft: ProtocolDeconstructionDraft) -> dict[str, Any]:
        return {
            component.rule_component_id: component
            for rule in draft.proposed_rules
            for component in rule.components
        }

    submitted_components = _components(submitted)
    current_components = _components(current)
    for component_id in diff.changed_component_ids:
        changes[f"rule_component:{component_id}"] = FieldChange(
            current=_dump(current_components.get(component_id)),
            submitted=_dump(submitted_components.get(component_id)),
        )

    submitted_requirements = _index(
        submitted.evidence_requirement_drafts,
        lambda item: item.draft_requirement_id,
    )
    current_requirements = _index(
        current.evidence_requirement_drafts,
        lambda item: item.draft_requirement_id,
    )
    for requirement_id in diff.changed_requirement_ids:
        changes[f"evidence_requirement:{requirement_id}"] = FieldChange(
            current=_dump(current_requirements.get(requirement_id)),
            submitted=_dump(submitted_requirements.get(requirement_id)),
        )

    submitted_mappings = _index(
        submitted.procedure_catalog_mappings, lambda item: item.catalog_item_id
    )
    current_mappings = _index(
        current.procedure_catalog_mappings, lambda item: item.catalog_item_id
    )
    for catalog_item_id in diff.changed_procedure_mapping_ids:
        changes[f"procedure_mapping:{catalog_item_id}"] = FieldChange(
            current=_dump(current_mappings.get(catalog_item_id)),
            submitted=_dump(submitted_mappings.get(catalog_item_id)),
        )

    if diff.source_scope_changed:
        changes["source_scope"] = FieldChange(
            current={
                "source_refs": current.source_refs,
                "procedure_source_span_ids": {
                    item.catalog_item_id: item.source_span_ids
                    for item in current.procedure_catalog_mappings
                },
            },
            submitted={
                "source_refs": submitted.source_refs,
                "procedure_source_span_ids": {
                    item.catalog_item_id: item.source_span_ids
                    for item in submitted.procedure_catalog_mappings
                },
            },
        )
    return changes


def _head_error(
    revisions: ProtocolDraftRevisionRepository,
    *,
    draft_id: str,
    expected_revision_id: str,
    head: ProtocolDraftRevision | None,
) -> StaleRevisionError:
    """过期提交错误：报告提交方真实 expected revision、当前 revision 与
    结构化差异，而不是把两值都写成当前值并清空差异。"""
    submitter: ProtocolDraftRevision | None = None
    try:
        candidate = revisions.get(expected_revision_id)
        if candidate.draft_id == draft_id:
            submitter = candidate
    except NotFoundError:
        submitter = None
    expected_revision = (
        submitter.revision_number
        if submitter is not None
        else (head.revision_number + 1 if head is not None else 1)
    )
    current_revision = head.revision_number if head is not None else 0
    field_diff: dict[str, "FieldChange"] = {}
    if submitter is not None and head is not None:
        field_diff = _draft_diff_as_field_changes(
            submitter.content, head.content
        )
    return StaleRevisionError(
        entity_type="ProtocolDraftRevision",
        entity_id=draft_id,
        expected_revision=expected_revision,
        current_revision=current_revision,
        field_diff=field_diff,
        current_record=head,
    )


def head_stale_error(
    revisions: ProtocolDraftRevisionRepository,
    *,
    draft_id: str,
    expected_revision_id: str,
    head: ProtocolDraftRevision | None,
) -> StaleRevisionError:
    """公共过期提交错误构造器（发布服务与草稿服务共用）。

    报告提交方真实 expected revision、当前 revision 与结构化差异信封。
    """
    return _head_error(
        revisions,
        draft_id=draft_id,
        expected_revision_id=expected_revision_id,
        head=head,
    )


__all__ = [
    "DraftEditBoundaryError",
    "DuplicateDraftError",
    "ProtocolDraftService",
    "compute_draft_diff",
    "enforce_draft_edit_boundary",
    "head_stale_error",
    "mark_revision_published",
]
