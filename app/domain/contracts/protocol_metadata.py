"""Phase 3 slice 2 contracts: protocol identity, phase scope and interpretations.

This module deliberately keeps three concerns separate:

* identity candidates are traceable observations, not a chosen protocol identity;
* phase applicability is a source-level projection, not a RuleSet;
* interpretation material is an attached clarification or amendment, never an
  implicit replacement for the protocol source.

The contracts are intentionally independent of python-docx, SQLAlchemy and any
model SDK.  Deterministic extraction and authority checks live in
``app.protocols`` and ``app.domain.interpretation`` respectively.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from .common import ContractModel, DateValue, VersionedModel
from .enums import (
    AlignmentStatus,
    AnchorResolutionMode,
    ApplicabilityGranularity,
    DocumentPart,
    IdentityAuthority,
    InterpretationAuthority,
    InterpretationConflictStatus,
    InterpretationSourceType,
    MetadataResolutionStatus,
    MetadataSourceKind,
    PhaseDesignType,
    PhaseScope,
    ProtocolMetadataField,
    ReviewStage,
    SourceLocatorPrecision,
    StudyPhase,
)

_SHA256 = r"^[0-9a-f]{64}$"


class ProtocolMetadataCandidate(VersionedModel):
    """One deterministic candidate for one identity field.

    ``identity_authority`` describes how suitable the source is for identifying
    the protocol.  ``locator_precision`` and ``source_alignment_status`` only
    describe rule-level/source-text localization.  A header/footer candidate
    therefore remains high-authority even when its rendered page alignment is
    degraded.
    """

    candidate_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    field_category: ProtocolMetadataField
    candidate_value: str = Field(min_length=1)
    normalized_value: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    source_span_id: str | None = None
    document_part: DocumentPart
    source_kind: MetadataSourceKind
    identity_authority: IdentityAuthority
    priority_rank: int = Field(ge=0)
    confidence_basis: list[str] = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    locator_precision: SourceLocatorPrecision = SourceLocatorPrecision.BLOCK
    source_alignment_status: AlignmentStatus = AlignmentStatus.UNALIGNED
    conflict_group_id: str | None = None
    is_fallback: bool = False
    is_generic_title: bool = False

    @model_validator(mode="after")
    def validate_source_semantics(self) -> "ProtocolMetadataCandidate":
        if self.source_kind == MetadataSourceKind.HEADER_FOOTER:
            if self.identity_authority != IdentityAuthority.HIGH:
                raise ValueError("页眉/页脚身份候选必须保持高身份权威级别")
            if self.is_fallback:
                raise ValueError("页眉/页脚明确字段不能标记为文件名兜底")
        if self.source_kind == MetadataSourceKind.FILENAME:
            if self.identity_authority != IdentityAuthority.LOW:
                raise ValueError("文件名候选只能是低权威身份兜底")
            if not self.is_fallback:
                raise ValueError("文件名候选必须明确标记为兜底")
        if self.is_generic_title and self.field_category not in {
            ProtocolMetadataField.DOCUMENT_TITLE,
            ProtocolMetadataField.PROJECT_NAME,
        }:
            raise ValueError("通用标题标记只能用于标题或项目名称候选")
        return self

    @property
    def field(self) -> ProtocolMetadataField:
        """兼容设计文档中的简写，同时保持持久化字段类别明确。"""

        return self.field_category

    @property
    def value(self) -> str:
        return self.candidate_value


class ProtocolMetadataConflict(VersionedModel):
    """同一字段的最高优先级候选无法确定为同一个值。"""

    conflict_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    field_category: ProtocolMetadataField
    candidate_ids: list[str] = Field(min_length=2)
    normalized_values: list[str] = Field(min_length=2)
    reason: str = Field(min_length=1)
    status: MetadataResolutionStatus = MetadataResolutionStatus.NEEDS_CONFIRMATION
    selected_candidate_id: str | None = None
    resolved_by: str | None = None
    resolved_at: datetime | None = None

    @model_validator(mode="after")
    def validate_conflict(self) -> "ProtocolMetadataConflict":
        if len(self.candidate_ids) != len(set(self.candidate_ids)):
            raise ValueError("元信息冲突候选不得重复")
        if len(self.normalized_values) != len(set(self.normalized_values)):
            raise ValueError("元信息冲突必须包含不同的规范化值")
        if self.status == MetadataResolutionStatus.CONFIRMED:
            if not self.selected_candidate_id or not self.resolved_by or self.resolved_at is None:
                raise ValueError("已确认的元信息冲突必须记录选择、确认人和时间")
            if self.selected_candidate_id not in self.candidate_ids:
                raise ValueError("确认的元信息候选不属于冲突组")
        return self


class ProtocolIdentityDecision(VersionedModel):
    """用户确认后的方案身份；在确认前允许保存为待核对状态。"""

    identity_decision_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    project_name: str | None = None
    project_code: str | None = None
    protocol_code: str | None = None
    official_version: str | None = None
    official_date: DateValue | None = None
    study_phase: StudyPhase | None = None
    selected_candidate_ids: list[str] = Field(default_factory=list)
    conflict_ids: list[str] = Field(default_factory=list)
    resolved_conflict_ids: list[str] = Field(default_factory=list)
    status: MetadataResolutionStatus = MetadataResolutionStatus.NEEDS_CONFIRMATION
    confirmation_required: bool = True
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_decision(self) -> "ProtocolIdentityDecision":
        if len(self.selected_candidate_ids) != len(set(self.selected_candidate_ids)):
            raise ValueError("身份确认候选引用不得重复")
        if len(self.conflict_ids) != len(set(self.conflict_ids)):
            raise ValueError("身份确认冲突引用不得重复")
        if len(self.resolved_conflict_ids) != len(set(self.resolved_conflict_ids)):
            raise ValueError("身份确认已解决冲突引用不得重复")
        if set(self.conflict_ids) & set(self.resolved_conflict_ids):
            raise ValueError("同一元信息冲突不能同时标记为待确认和已解决")
        if self.status == MetadataResolutionStatus.CONFIRMED:
            if self.confirmation_required:
                raise ValueError("已确认身份不能仍标记为需要确认")
            if not self.confirmed_by or self.confirmed_at is None:
                raise ValueError("已确认身份必须记录确认人和时间")
            if self.conflict_ids:
                raise ValueError("已确认身份不能仍携带未解决元信息冲突")
            if (
                not self.project_name
                or not self.protocol_code
                or not self.official_version
                or self.official_date is None
                or not self.study_phase
            ):
                raise ValueError("已确认身份必须包含项目名称、方案编号、版本、日期和研究期别")
            if self.official_date.value is None or self.official_date.precision.value == "unknown":
                raise ValueError("已确认方案日期必须具有年、月或日精度的规范值")
        if self.status == MetadataResolutionStatus.REJECTED and not self.confirmed_by:
            raise ValueError("拒绝身份候选必须记录操作人")
        return self


class StudyPhaseCandidate(VersionedModel):
    """一个文档片段对研究期别/设计类型的确定性候选。"""

    candidate_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    phase_scopes: list[PhaseScope] = Field(min_length=1)
    design_type: PhaseDesignType = PhaseDesignType.UNKNOWN
    source_ref: str = Field(min_length=1)
    source_span_id: str | None = None
    source_kind: MetadataSourceKind
    excerpt: str = Field(min_length=1)
    priority_rank: int = Field(ge=0)
    confidence_basis: list[str] = Field(min_length=1)
    explicit_design_evidence: bool = False
    same_cohort_evidence: bool = False
    disqualifying_evidence: list[str] = Field(default_factory=list)
    requires_confirmation: bool = True

    @model_validator(mode="after")
    def validate_phase_candidate(self) -> "StudyPhaseCandidate":
        if len(self.phase_scopes) != len(set(self.phase_scopes)):
            raise ValueError("期别候选范围不得重复")
        if self.design_type == PhaseDesignType.SEAMLESS_CANDIDATE:
            if not self.explicit_design_evidence or not self.same_cohort_evidence:
                raise ValueError("真正无缝候选必须同时有明确设计和同一受试者队列证据")
            if self.disqualifying_evidence:
                raise ValueError("存在反向证据时不能建立无缝候选")
            if PhaseScope.PHASE_II not in self.phase_scopes or PhaseScope.PHASE_III not in self.phase_scopes:
                raise ValueError("无缝候选必须同时覆盖 II 期和 III 期")
        return self


class StudyPhaseSelection(VersionedModel):
    """用户选择的本次解构期别；合并候选不能绕过确认。"""

    selection_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    selected_phase: StudyPhase
    candidate_ids: list[str] = Field(min_length=1)
    status: MetadataResolutionStatus = MetadataResolutionStatus.NEEDS_CONFIRMATION
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_selection(self) -> "StudyPhaseSelection":
        if self.selected_phase == StudyPhase.OTHER:
            raise ValueError("本次解构必须选择明确的 II 期、III 期或已确认的无缝期别")
        if self.status == MetadataResolutionStatus.CONFIRMED and (
            not self.confirmed_by or self.confirmed_at is None
        ):
            raise ValueError("已确认期别必须记录确认人和时间")
        return self


class PhaseApplicabilityBlock(VersionedModel):
    """段落、表格行或访视列的适用范围。"""

    block_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    source_span_ids: list[str] = Field(min_length=1)
    granularity: ApplicabilityGranularity
    source_order: int = Field(ge=0)
    text: str = Field(min_length=1)
    phase_scopes: list[PhaseScope] = Field(min_length=1)
    table_path: tuple[int, ...] | None = None
    table_row: int | None = Field(default=None, ge=0)
    visit_column: int | None = Field(default=None, ge=0)
    cross_phase_comparison: bool = False
    projection_text: str | None = None
    is_aggregate: bool = False
    child_block_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_block(self) -> "PhaseApplicabilityBlock":
        if len(self.source_span_ids) != len(set(self.source_span_ids)):
            raise ValueError("适用范围来源片段不得重复")
        if len(self.phase_scopes) != len(set(self.phase_scopes)):
            raise ValueError("适用范围期别不得重复")
        if len(self.child_block_ids) != len(set(self.child_block_ids)):
            raise ValueError("聚合适用范围子块不得重复")
        if not self.is_aggregate and self.child_block_ids:
            raise ValueError("非聚合适用范围不能携带子块")
        if self.is_aggregate and not self.child_block_ids:
            raise ValueError("聚合适用范围必须保留子块来源")
        if self.granularity == ApplicabilityGranularity.TABLE_ROW and self.table_row is None:
            raise ValueError("表格行适用范围必须包含 table_row")
        if self.granularity == ApplicabilityGranularity.VISIT_COLUMN and self.visit_column is None:
            raise ValueError("访视列适用范围必须包含 visit_column")
        if self.granularity == ApplicabilityGranularity.PARAGRAPH and self.table_row is not None:
            raise ValueError("正文段落适用范围不能携带 table_row")
        if self.projection_text is not None and not self.cross_phase_comparison:
            raise ValueError("仅跨期原文块可以携带单期派生显示文本")
        if self.table_path is not None:
            if len(self.table_path) % 2 != 0 or any(item < 0 for item in self.table_path):
                raise ValueError("适用范围 table_path 必须是非负 row/col 对")
        return self

    @property
    def is_shared(self) -> bool:
        return self.phase_scopes == [PhaseScope.SHARED]

    @property
    def is_ambiguous(self) -> bool:
        """Whether this block cannot be safely assigned to one phase."""

        scopes = set(self.phase_scopes)
        return bool(scopes & {PhaseScope.MIXED, PhaseScope.UNKNOWN})


class SeamlessPhaseCandidate(VersionedModel):
    """只有明确无缝设计且同一受试者队列连续跨期时才允许出现。"""

    candidate_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)
    explicit_design_excerpt: str = Field(min_length=1)
    same_cohort_excerpt: str = Field(min_length=1)
    supporting_source_refs: list[str] = Field(min_length=1)
    requires_second_confirmation: bool = True

    @model_validator(mode="after")
    def validate_candidate(self) -> "SeamlessPhaseCandidate":
        if len(self.source_refs) != len(set(self.source_refs)):
            raise ValueError("无缝候选来源不得重复")
        if not self.requires_second_confirmation:
            raise ValueError("无缝候选必须要求二次确认")
        return self


class PhaseApplicabilityGraph(VersionedModel):
    """整份方案的期别适用图；不直接产生 RuleSet。"""

    graph_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    blocks: list[PhaseApplicabilityBlock] = Field(min_length=1)
    seamless_candidates: list[SeamlessPhaseCandidate] = Field(default_factory=list)
    detected_phase_scopes: list[PhaseScope] = Field(min_length=1)
    default_design_type: PhaseDesignType = PhaseDesignType.INDEPENDENT

    @model_validator(mode="after")
    def validate_graph(self) -> "PhaseApplicabilityGraph":
        block_ids = [item.block_id for item in self.blocks]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("期别适用图 block_id 必须唯一")
        refs = [item.source_ref for item in self.blocks]
        if len(refs) != len(set(refs)):
            raise ValueError("期别适用图 source_ref 必须唯一")
        by_id = {item.block_id: item for item in self.blocks}
        for block in self.blocks:
            if not block.is_aggregate:
                continue
            if any(child_id not in by_id for child_id in block.child_block_ids):
                raise ValueError("聚合适用范围必须引用图内原子子块")
            child_spans = {
                span_id
                for child_id in block.child_block_ids
                for span_id in by_id[child_id].source_span_ids
            }
            if not child_spans <= set(block.source_span_ids):
                raise ValueError("聚合适用范围必须保留全部子块来源片段")
        if PhaseScope.SEAMLESS_CANDIDATE in self.detected_phase_scopes and not self.seamless_candidates:
            raise ValueError("声明无缝期别范围时必须有同一队列候选")
        return self


class PhaseProjection(VersionedModel):
    """单一期别展示/发送给 Agent 的投影，只含选定期别和共享块。"""

    projection_id: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    selected_phase: StudyPhase
    blocks: list[PhaseApplicabilityBlock] = Field(min_length=1)
    excluded_block_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_projection(self) -> "PhaseProjection":
        if self.selected_phase not in {
            StudyPhase.PHASE_II,
            StudyPhase.PHASE_III,
            StudyPhase.SEAMLESS_II_III,
        }:
            raise ValueError("单一期别投影必须绑定 II 期、III 期或已确认的无缝期别")
        allowed = {
            PhaseScope.PHASE_II if self.selected_phase == StudyPhase.PHASE_II else PhaseScope.PHASE_III,
            PhaseScope.SHARED,
        }
        if self.selected_phase == StudyPhase.SEAMLESS_II_III:
            allowed = {
                PhaseScope.PHASE_II,
                PhaseScope.PHASE_III,
                PhaseScope.SHARED,
                PhaseScope.SEAMLESS_CANDIDATE,
            }
        if any(item.is_ambiguous for item in self.blocks):
            raise ValueError("单一期别投影不能包含混合或未知期别块")
        if self.selected_phase == StudyPhase.SEAMLESS_II_III:
            invalid = any(not set(item.phase_scopes) <= allowed for item in self.blocks)
        else:
            selected = next(iter(allowed - {PhaseScope.SHARED}))
            invalid = any(
                tuple(item.phase_scopes) not in {
                    (selected,),
                    (PhaseScope.SHARED,),
                }
                for item in self.blocks
            )
        if invalid:
            raise ValueError("单一期别投影包含未选期别专属块")
        return self


class AnchorResolutionStatement(VersionedModel):
    """解释材料对未命名回溯锚点的一条结构化解析声明。

    解析只绑定锚点身份：受影响父规则（官方编号）、原歧义方案来源定位、
    目标审核节点集合和唯一解析模式。它不携带、也不允许携带窗口量、方向、
    阈值、布尔逻辑或官方编号改写——这些仍必须逐字来自方案原文，并由
    确定性门禁按原文核验。
    """

    resolution_id: str = Field(min_length=1)
    affected_rule_refs: list[str] = Field(min_length=1)
    ambiguous_source_refs: list[str] = Field(min_length=1)
    target_review_stages: list[ReviewStage] = Field(min_length=1)
    resolution_mode: AnchorResolutionMode

    @model_validator(mode="after")
    def validate_resolution(self) -> "AnchorResolutionStatement":
        if len(self.affected_rule_refs) != len(set(self.affected_rule_refs)):
            raise ValueError("锚点解析影响的父规则不得重复")
        if len(self.ambiguous_source_refs) != len(set(self.ambiguous_source_refs)):
            raise ValueError("锚点解析的歧义方案来源不得重复")
        if len(self.target_review_stages) != len(set(self.target_review_stages)):
            raise ValueError("锚点解析的目标审核节点不得重复")
        if self.resolution_mode is not AnchorResolutionMode.CURRENT_REVIEW_NODE_DATE:
            raise ValueError("锚点解析只能使用当前审核节点日期这一项目无关模式")
        return self


class InterpretationSource(VersionedModel):
    """方案修订/解释材料来源及其可改变的权威边界。"""

    interpretation_source_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    source_type: InterpretationSourceType
    file_sha256: str = Field(pattern=_SHA256)
    source_version: str | None = None
    source_date: DateValue | None = None
    source_ref: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    applies_to_rule_refs: list[str] = Field(default_factory=list)
    is_current_amendment: bool = False
    clarifies_ambiguity: bool = False
    formal_change_summary: str | None = None
    anchor_resolutions: list[AnchorResolutionStatement] = Field(default_factory=list)
    authority: InterpretationAuthority | None = None

    @model_validator(mode="after")
    def derive_authority(self) -> "InterpretationSource":
        expected = (
            InterpretationAuthority.FORMAL_REQUIREMENT
            if self.source_type == InterpretationSourceType.AMENDMENT
            and self.is_current_amendment
            else InterpretationAuthority.CLARIFICATION_ONLY
        )
        if self.authority is not None and self.authority != expected:
            raise ValueError("解释材料权威级别必须由来源类型和当前修订状态确定")
        self.authority = expected
        if self.authority == InterpretationAuthority.CLARIFICATION_ONLY and self.formal_change_summary:
            raise ValueError("Q&A、澄清函、邮件和医学解释不能声明正式规则变更")
        if self.anchor_resolutions:
            if self.authority != InterpretationAuthority.CLARIFICATION_ONLY:
                raise ValueError(
                    "锚点解析只能由澄清级解释材料提供；当前修订案应直接修改方案原文"
                )
            if not self.clarifies_ambiguity:
                raise ValueError("携带锚点解析的解释材料必须明确标注为方案模糊处的补充说明")
            if not self.applies_to_rule_refs:
                raise ValueError("携带锚点解析的解释材料必须声明其适用的父规则范围")
            covered = set(self.applies_to_rule_refs)
            for resolution in self.anchor_resolutions:
                if not set(resolution.affected_rule_refs) <= covered:
                    raise ValueError(
                        "锚点解析影响的父规则必须在该解释材料声明的适用范围内"
                    )
        return self


class InterpretationConflict(VersionedModel):
    """解释材料与方案/当前修订案冲突时的显式阻断记录。"""

    conflict_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    interpretation_source_id: str = Field(min_length=1)
    affected_rule_refs: list[str] = Field(min_length=1)
    protocol_source_refs: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)
    impact: str = Field(min_length=1)
    status: InterpretationConflictStatus = InterpretationConflictStatus.OPEN
    blocks_publication: bool = True
    resolved_by_amendment_source_id: str | None = None
    resolved_at: datetime | None = None

    @model_validator(mode="after")
    def validate_conflict(self) -> "InterpretationConflict":
        if len(self.affected_rule_refs) != len(set(self.affected_rule_refs)):
            raise ValueError("解释冲突影响规则不得重复")
        if len(self.protocol_source_refs) != len(set(self.protocol_source_refs)):
            raise ValueError("解释冲突的方案来源不得重复")
        if self.status in {
            InterpretationConflictStatus.OPEN,
            InterpretationConflictStatus.ACKNOWLEDGED,
        } and not self.blocks_publication:
            raise ValueError("未解决解释冲突必须阻止发布")
        if self.status == InterpretationConflictStatus.RESOLVED_BY_CURRENT_AMENDMENT:
            if not self.resolved_by_amendment_source_id or self.resolved_at is None:
                raise ValueError("由当前修订案解决的冲突必须记录修订案和时间")
            if self.blocks_publication:
                raise ValueError("已由当前修订案解决的冲突不能继续阻止发布")
        return self


class InterpretationAssessment(ContractModel):
    """确定性权威检查结果；不直接改写 RuleSet。"""

    allowed: bool
    authority: InterpretationAuthority
    clarification_only: bool
    conflicts: list[str] = Field(default_factory=list)
    forbidden_changes: list[str] = Field(default_factory=list)
    message: str = Field(min_length=1)


# 设计文档和调用方常用的同义名，统一指向同一份领域合同。
MetadataFieldCategory = ProtocolMetadataField
PhaseApplicabilityMap = PhaseApplicabilityGraph
ProtocolPhaseProjection = PhaseProjection
