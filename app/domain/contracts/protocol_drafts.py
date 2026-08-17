"""Phase 3 slice 4: immutable draft revision history contracts.

``ProtocolDraftRevision`` 记录每一次已保存的方案草稿版本：初始保存、手工编辑、
原文理解纠错反馈、解释性澄清反馈、恢复后继版本。历史只追加，取消与发布均不
物理删除任何已保存 revision；乐观并发通过「后继必须指向当前链头」保证，过期
编辑不能覆盖新状态。

结构化差异 ``ProtocolDraftRevisionDiff`` 由确定性算法生成（设计书 §10），
展示层只消费该结构，不解析自由文本摘要。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import Field, model_validator

from .agent_io import ProtocolDeconstructionDraft
from .common import VersionedModel
from .enums import StableEnum, StudyPhase


class DraftRevisionStatus(StableEnum):
    """已保存草稿 revision 的生命周期状态（机器值，中文标签由投影词汇表提供）。"""

    DRAFT = "draft"
    SAVED = "saved"
    CANCELLED = "cancelled"
    PUBLISHED = "published"
    RESTORED_FROM = "restored_from"


class DraftRevisionReason(StableEnum):
    """形成本 revision 的原因类别。"""

    INITIAL_SAVE = "initial_save"
    MANUAL_EDIT = "manual_edit"
    SOURCE_ERROR_FEEDBACK = "source_error_feedback"
    CLARIFICATION_FEEDBACK = "clarification_feedback"
    RESTORE = "restore"


class DraftFeedbackKind(StableEnum):
    """用户反馈的分类：「指出原文理解错误」或「补充解释」。

    ``SOURCE_ERROR`` 必须关联当前方案来源片段（来源忠实纠错）；
    ``CLARIFICATION`` 只能进入解释说明层，不得改变阈值或布尔逻辑。
    """

    SOURCE_ERROR = "source_error"
    CLARIFICATION = "clarification"


class DiffCategory(StableEnum):
    """八类结构化差异的机器类别（中文标签由投影词汇表提供，展示层不解析自由文本）。

    ``ADDED``/``REMOVED`` 在规则与子组件两个粒度分别表达；其余六类是同一稳定子组件
    在前后稿中该维度的变化。
    """

    ADDED = "added"                     # 新增
    REMOVED = "removed"                 # 删除
    ORIGINAL_TEXT = "original_text"     # 原文
    LOGIC = "logic"                     # 逻辑
    TIME_WINDOW = "time_window"         # 时间窗
    EXCEPTION = "exception"             # 例外
    EVIDENCE = "evidence"               # 证据要求
    DUE_STAGE = "due_stage"             # 应完成阶段


class CategoryChange(VersionedModel):
    """某个稳定项在单个类别的前后结构化快照（确定性比较输出）。

    ``stable_ref`` 为稳定引用：父规则使用官方编号，子组件使用其展示编号（如
    ``IN-04a``），资料要求使用 ``<组件引用>#req[序号]``。``previous``/``current``
    为该类别在前后稿上的结构化快照；一边缺失（首稿或该项前稿不存在）时为 None。
    """

    stable_ref: str = Field(min_length=1)
    kind: Literal["rule", "component", "requirement"] = "component"
    previous: Any | None = None
    current: Any | None = None


class ParentRuleDiff(VersionedModel):
    """一条官方父规则相对前序稿的八类结构化差异（按 ``official_code`` 对齐）。

    新增/删除在父规则与稳定子组件两个粒度列出；其余六类（原文、逻辑、时间窗、例外、
    证据要求、应完成阶段）以稳定子组件引用的前后快照分列，供展示层逐条并列显示。
    """

    official_code: str = Field(min_length=1)
    added: bool = False
    removed: bool = False
    added_component_refs: list[str] = Field(default_factory=list)
    removed_component_refs: list[str] = Field(default_factory=list)
    original_text_changes: list[CategoryChange] = Field(default_factory=list)
    logic_changes: list[CategoryChange] = Field(default_factory=list)
    time_window_changes: list[CategoryChange] = Field(default_factory=list)
    exception_changes: list[CategoryChange] = Field(default_factory=list)
    evidence_changes: list[CategoryChange] = Field(default_factory=list)
    due_stage_changes: list[CategoryChange] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_exclusivity(self) -> "ParentRuleDiff":
        if self.added and self.removed:
            raise ValueError("同一父规则不能同时为新增和删除")
        return self


class ProtocolDraftRevisionDiff(VersionedModel):
    """一次 revision 相对其前序的结构化差异（设计书 §10 差异算法输出）。"""

    added_rule_codes: list[str] = Field(default_factory=list)
    removed_rule_codes: list[str] = Field(default_factory=list)
    modified_rule_codes: list[str] = Field(default_factory=list)
    added_workflow_stage_ids: list[str] = Field(default_factory=list)
    removed_workflow_stage_ids: list[str] = Field(default_factory=list)
    modified_workflow_stage_ids: list[str] = Field(default_factory=list)
    changed_component_ids: list[str] = Field(default_factory=list)
    changed_requirement_ids: list[str] = Field(default_factory=list)
    changed_procedure_mapping_ids: list[str] = Field(default_factory=list)
    source_scope_changed: bool = False
    workflow_visit_rewritten: bool = False
    clarification_semantics_changed: bool = False
    # 切片 6：按官方父规则编号对齐的八类结构化详情（新增/删除/原文/逻辑/时间窗/例外/
    # 证据要求/应完成阶段）。粗粒度字段保留以兼容前序调用方；展示层应优先消费本字段。
    rule_diffs: list[ParentRuleDiff] = Field(default_factory=list)


class ProtocolDraftRevision(VersionedModel):
    """一份已保存草稿的不可变历史版本。

    ``content`` 为该 revision 时刻完整的 :class:`ProtocolDeconstructionDraft`
    快照；``content_sha256`` 为快照的规范哈希，读取时交叉核验。``diff`` 相对
    ``previous_revision_id`` 指向的 revision 计算；首稿 diff 为空结构。
    """

    revision_id: str = Field(min_length=1)
    draft_id: str = Field(min_length=1)
    revision_number: int = Field(ge=1)
    previous_revision_id: str | None = None
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    study_phase: StudyPhase
    status: DraftRevisionStatus
    reason: DraftRevisionReason
    feedback_kind: DraftFeedbackKind | None = None
    feedback_note: str | None = None
    actor: str = Field(min_length=1)
    content: ProtocolDeconstructionDraft
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    diff: ProtocolDraftRevisionDiff = Field(default_factory=ProtocolDraftRevisionDiff)
    created_at: datetime

    @model_validator(mode="after")
    def validate_chain(self) -> "ProtocolDraftRevision":
        from app.domain.publication import canonical_hash

        if self.content.draft_id != self.draft_id:
            raise ValueError("ProtocolDraftRevision 内外层 draft_id 不一致")
        if self.content.project_id != self.project_id:
            raise ValueError("ProtocolDraftRevision 内外层 project_id 不一致")
        if self.content.protocol_version_id != self.protocol_version_id:
            raise ValueError("ProtocolDraftRevision 内外层 protocol_version_id 不一致")
        if self.content.selected_phase != self.study_phase:
            raise ValueError("ProtocolDraftRevision 内外层研究期别不一致")
        if self.content.draft_revision != self.revision_number:
            raise ValueError("ProtocolDraftRevision 内外层 revision 号不一致")
        expected_hash = canonical_hash(self.content.model_dump(mode="json"))
        if self.content_sha256 != expected_hash:
            raise ValueError("ProtocolDraftRevision 内容哈希与草稿快照不一致")
        if self.revision_number == 1:
            if self.previous_revision_id is not None:
                raise ValueError("首稿 revision 不能引用前序 revision")
            if self.reason != DraftRevisionReason.INITIAL_SAVE:
                raise ValueError("首稿 revision 必须由初始保存形成")
        else:
            if not self.previous_revision_id:
                raise ValueError("后继 revision 必须引用前序 revision")
            if self.reason == DraftRevisionReason.INITIAL_SAVE:
                raise ValueError("初始保存只能形成首稿 revision")
        if self.reason == DraftRevisionReason.CLARIFICATION_FEEDBACK:
            if self.feedback_kind != DraftFeedbackKind.CLARIFICATION:
                raise ValueError("澄清反馈 revision 必须声明澄清反馈分类")
        if self.reason == DraftRevisionReason.SOURCE_ERROR_FEEDBACK:
            if self.feedback_kind != DraftFeedbackKind.SOURCE_ERROR:
                raise ValueError("原文理解纠错 revision 必须声明纠错反馈分类")
        if self.reason == DraftRevisionReason.RESTORE:
            if self.status != DraftRevisionStatus.RESTORED_FROM:
                raise ValueError("恢复后继 revision 必须标记为 restored_from")
        if self.status == DraftRevisionStatus.RESTORED_FROM:
            if self.reason != DraftRevisionReason.RESTORE:
                raise ValueError("restored_from 状态只能由恢复后继 revision 使用")
        if self.reason == DraftRevisionReason.CLARIFICATION_FEEDBACK:
            if self.diff.clarification_semantics_changed:
                raise ValueError("澄清反馈不得改变方案阈值或布尔逻辑")
        return self


__all__ = [
    "CategoryChange",
    "DiffCategory",
    "DraftFeedbackKind",
    "DraftRevisionReason",
    "DraftRevisionStatus",
    "ParentRuleDiff",
    "ProtocolDraftRevision",
    "ProtocolDraftRevisionDiff",
]
