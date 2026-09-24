"""Phase 5 Slice 5.8a/5.8b 全方案控制合同（纯校验，无存储）。

本模块只冻结确定性校验与身份边界，不含 Agent 调用、存储、文件路径或真实项目写路径，
覆盖研究纪要与设计书对「全文覆盖 / 候选 / 发布」三层分离的第一阶段合同：

- ``ProtocolStructureUnit`` / ``ProtocolSectionCoverageManifest``
  选定期别全文结构单元清单与逐项处置；关键词只可影响优先级，不得过滤未命中单元；
- ``ProtocolControlCandidate`` / ``ProtocolControlCandidateDisposition``
  Agent 只能对冻结结构单元身份结构化、拆分或明确排除；不得直接写成发布控制；
- ``ProtocolReviewControl`` / ``PublishedProtocolControlCatalog``
  正式发布控制：非空多义务原子、审核节点作用、最低证据、来源闭包与跨来源关系。
- ``Control*Dnf`` / ``ProtocolControl*Batch``
  5.8b 的独立适用性、触发、义务、例外 DNF 层、语义草稿/系统水合与逐项处置批次。

硬边界：

- 其他方案控制使用稳定 ``protocol_control_id``，界面顺序标签为「方案控制 NN」；
  不得生成 ``CTRL-xx``、``REQ-xx`` 或新的 ``IN/EX`` 官方编号；
- 义务类型至少支持：完成/核对、达到条件、禁止事件、禁止药物/治疗暴露、
  必须记录、必须专业评估；
- 审核节点绑定必须显式标记：提前关注、本节点判定或后续节点复核；
- 跨来源关系仅为重复表述、补充要求、进一步解释或实质冲突；不实现文本相似度合并；
- 任一结构单元未处置时，不得宣称全文覆盖完整。
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal, Sequence

from pydantic import AliasChoices, ConfigDict, Field, model_serializer, model_validator

from .common import ContractModel
from .control_evaluation_spec import ControlAtomEvaluationSpec, validate_control_atom_evaluation
from .control_evidence_policy import ControlEvidenceSourcePolicy
from .control_evidence_dependency import ControlEvidenceAtomReference
from .control_time_binding import ControlTimeBinding, validate_control_time_bindings
from .enums import LogicalOperator, PhaseScope, ReviewStage, StableEnum, StudyPhase
from .rules import ProspectivePeriod, TimeConstraint
from .repeat_scheme import (RepeatEvidenceRole, RepeatEvidenceRoleReference,
                            resolve_repeat_evidence_roles, validate_repeat_evidence_roles)

__all__ = [
    "ControlConditionAtom",
    "ControlConditionAtomDraft",
    "ControlConditionDnf",
    "ControlConditionGroup",
    "ControlConditionGroupDraft",
    "ControlCandidateAction",
    "ControlCrossSourceRelation",
    "ControlCrossSourceRelationDraft",
    "ControlExceptionDnf",
    "ControlExceptionGroup",
    "ControlMinimumEvidence",
    "ControlMinimumEvidenceDraft",
    "ControlObligationAtom",
    "ControlObligationAtomDraft",
    "ControlContinuingObligation",
    "ControlObligationKind",
    "ControlObligationModality",
    "ControlTemporalScopeKind",
    "ControlObligationDnf",
    "ControlObligationDnfDraft",
    "ControlObligationGroup",
    "ControlObligationGroupDraft",
    "ControlRelationTargetKind",
    "CrossSourceRelationKind",
    "KnownOfficialRuleTarget",
    "KnownRequiredProcedureTarget",
    "KnownWorkflowStageTarget",
    "ProtocolControlDiscoveryBatch",
    "ProtocolControlDiscoveryDecision",
    "ProtocolControlDiscoveryDisposition",
    "ProtocolControlDiscoveryPlan",
    "ProtocolControlBatchDisposition",
    "ProtocolControlBatchDispositionHydrated",
    "ProtocolControlFinalBatchDisposition",
    "ProtocolControlCandidateSemanticDraft",
    "ProtocolControlCandidateSemantics",
    "ProtocolControlUnitDisposition",
    "ProtocolControlUnitDispositionDraft",
    "hydrate_protocol_control_candidate_semantics",
    "hydrate_protocol_control_batch_disposition",
    "ProtocolControlBatch",
    "ProtocolControlPlan",
    "ProtocolControlDispositionBatch",
    "ProtocolControlBatchPlan",
    "ProtocolControlCandidate",
    "ProtocolControlCandidateDisposition",
    "ProtocolReviewControl",
    "ProtocolSectionCoverageManifest",
    "ProtocolStructureUnit",
    "PublishedProtocolControlCatalog",
    "ReviewNodeBinding",
    "ReviewNodeRole",
    "StructureUnitDisposition",
    "StructureUnitDispositionKind",
    "StructureUnitKind",
    "TableCellContext",
    "ProtocolControlDiscoveryToDeepPlan",
    "ProtocolControlDeepPlan",
    "stable_protocol_control_atom_id",
    "stable_protocol_control_candidate_id",
    "stable_protocol_control_batch_id",
    "stable_protocol_control_discovery_batch_id",
    "stable_protocol_control_manifest_structure_unit_ids_sha256",
    "stable_protocol_control_evidence_id",
    "stable_protocol_control_relation_id",
    "stable_protocol_control_trigger_branch_id",
    "stable_protocol_control_obligation_group_id",
    "stable_protocol_control_exception_group_id",
    "is_forbidden_protocol_control_code",
    "protocol_control_display_label",
]

_SHA256 = r"^[0-9a-f]{64}$"
# 官方 IN/EX/REQ 与伪官方 CTRL 均禁止用作其他方案控制身份或展示编号。
_FORBIDDEN_CONTROL_CODE = re.compile(
    r"^(?:IN|EX|REQ|CTRL)[-_ ]?\d{1,4}$",
    re.IGNORECASE,
)
_CONTROL_CANDIDATE_ID = re.compile(
    r"^candidate[-_:][A-Za-z0-9][A-Za-z0-9._:/-]*$",
    re.IGNORECASE,
)


class StructureUnitKind(StableEnum):
    """全文结构单元种类：覆盖段落、列表项、表头、表格行与注释，而非关键词命中。"""

    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE_HEADER = "table_header"
    TABLE_ROW = "table_row"
    TABLE_NOTE = "table_note"
    FOOTNOTE_OR_ANNOTATION = "footnote_or_annotation"


class StructureUnitDispositionKind(StableEnum):
    """选定期别结构单元的处置结果；「待确认」仍是已处置，缺省才算未处置。"""

    OFFICIAL_ELIGIBILITY = "official_eligibility"
    REQUIRED_PROCEDURE = "required_procedure"
    OTHER_CONTROL_CANDIDATE = "other_control_candidate"
    SUPPORTING_OR_SUPPLEMENT = "supporting_or_supplement"
    POST_TREATMENT_EXECUTION = "post_treatment_execution"
    NON_ENROLLMENT_EXECUTION = "non_enrollment_execution"
    ADMINISTRATIVE_STATISTICAL_BACKGROUND = "administrative_statistical_background"
    PHASE_EXCLUDED = "phase_excluded"
    PENDING_CONFIRMATION = "pending_confirmation"
 
 
class ProtocolControlDiscoveryDisposition(StableEnum):
    """Coarse first-stage routing outcome for one manifest structure unit."""

    CANDIDATE = "candidate"
    CONTEXT_ONLY = "context_only"
    NON_CONTROL = "non_control"
    UNCERTAIN = "uncertain"




class ControlObligationKind(StableEnum):
    """正式控制的类型化义务原子。"""

    COMPLETE_OR_VERIFY = "complete_or_verify"
    COMPLETE_BEFORE_ANCHOR = "complete_before_anchor"
    SCHEDULE_OR_VERIFY_VISIT = "schedule_or_verify_visit"
    VERIFY_RESULT_VALIDITY = "verify_result_validity"
    SELECT_BASELINE_VALUE = "select_baseline_value"
    REACH_CONDITION = "reach_condition"
    PROHIBIT_EVENT = "prohibit_event"
    PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE = (
        "prohibit_medication_or_treatment_exposure"
    )
    MUST_RECORD = "must_record"
    MUST_PROFESSIONAL_ASSESSMENT = "must_professional_assessment"


class ControlObligationModality(StableEnum):
    """方案对义务完成强度的原文限定。"""

    MANDATORY = "mandatory"
    RECOMMENDED = "recommended"
    BEST_EFFORT = "best_effort"


class ControlTemporalScopeKind(StableEnum):
    """义务时间范围的来源类型，避免把不同层级窗口互相覆盖。"""

    CALENDAR_LOOKBACK = "calendar_lookback"
    FULL_HISTORY = "full_history"
    OFFICIAL_RULE_DEFINED = "official_rule_defined"
    SINCE_PREVIOUS_VISIT = "since_previous_visit"


def _validate_obligation_semantics(
    *,
    kind: ControlObligationKind,
    modality: ControlObligationModality,
    temporal_scope: ControlTemporalScopeKind | None,
    time_constraint: TimeConstraint | None,
) -> None:
    if modality == ControlObligationModality.BEST_EFFORT and kind in (
        ControlObligationKind.PROHIBIT_EVENT,
        ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE,
    ):
        raise ValueError("尽力完成不得用于禁止类义务")
    if modality == ControlObligationModality.RECOMMENDED and kind in (
        ControlObligationKind.PROHIBIT_EVENT,
        ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE,
    ):
        raise ValueError("建议完成不得用于禁止类义务")
    if temporal_scope == ControlTemporalScopeKind.CALENDAR_LOOKBACK:
        if time_constraint is None:
            raise ValueError("日历回顾范围必须提供结构化时间窗")
        return
    if temporal_scope is not None and time_constraint is not None:
        raise ValueError("完整历程、按正式条款窗口或自上次访视以来不得附加统一日历窗")

class ReviewNodeRole(StableEnum):
    """控制在审核节点上的作用；不得省略或使用模糊占位。"""

    EARLY_ATTENTION = "early_attention"
    DECIDE_AT_NODE = "decide_at_node"
    LATER_NODE_REVIEW = "later_node_review"


class CrossSourceRelationKind(StableEnum):
    """跨来源可审计关系；不依据文本相似度静默合并。"""

    DUPLICATE_STATEMENT = "duplicate_statement"
    SUPPLEMENTARY_REQUIREMENT = "supplementary_requirement"
    FURTHER_EXPLANATION = "further_explanation"
    SUBSTANTIVE_CONFLICT = "substantive_conflict"


class ControlRelationTargetKind(StableEnum):
    """跨来源关系对端身份种类。"""

    OFFICIAL_RULE = "official_rule"
    RULE_COMPONENT = "rule_component"
    REQUIRED_PROCEDURE = "required_procedure"
    WORKFLOW_STAGE = "workflow_stage"
    PROTOCOL_CONTROL = "protocol_control"
    CONTROL_CANDIDATE = "control_candidate"


class ControlCandidateAction(StableEnum):
    """Agent 对冻结结构单元身份的允许动作。"""

    STRUCTURE = "structure"
    SPLIT = "split"
    EXCLUDE = "exclude"


class Phase5ControlModel(ContractModel):
    """Phase 5 控制合同基类：与 legacy ``fixture/v1`` 明确区分。"""

    schema_version: Literal["phase5/v1"] = "phase5/v1"
    model_config = ConfigDict(extra="forbid")


def is_forbidden_protocol_control_code(value: str) -> bool:
    """其他方案控制不得伪装为 IN/EX/REQ/CTRL 官方或伪官方编号。"""

    return bool(_FORBIDDEN_CONTROL_CODE.match(value.strip()))


def protocol_control_display_label(display_ordinal: int) -> str:
    """界面顺序标签；不是官方条款编号。"""

    if display_ordinal < 1:
        raise ValueError("方案控制顺序标签必须从 1 起")
    return f"方案控制 {display_ordinal:02d}"


def _require_sorted_unique(values: list[str], label: str) -> None:
    if any(not value.strip() for value in values):
        raise ValueError(f"{label} 不得包含空 ID")
    if values != sorted(set(values)):
        raise ValueError(f"{label} 必须按 ID 排序且不得重复")


def _require_unique(values: Sequence[str], label: str) -> None:
    if any(not value.strip() for value in values):
        raise ValueError(f"{label} 不得包含空 ID")
    if len(values) != len(set(values)):
        raise ValueError(f"{label} 不得重复")


def _require_sorted_nonnegative_unique(
    values: Sequence[int],
    label: str,
) -> None:
    if any(value < 0 for value in values):
        raise ValueError(f"{label} 必须为非负整数")
    if list(values) != sorted(set(values)):
        raise ValueError(f"{label} 必须按升序排列且不得重复")


def _reject_forbidden_control_identity(value: str, field_name: str) -> None:
    if is_forbidden_protocol_control_code(value):
        raise ValueError(
            f"{field_name} 不得使用 IN/EX/REQ/CTRL 伪官方或官方编号形态"
        )


def _reject_invalid_control_candidate_identity(
    value: str,
    field_name: str,
) -> None:
    if not _CONTROL_CANDIDATE_ID.fullmatch(value):
        raise ValueError(
            f"{field_name} 必须使用稳定的 candidate 前缀，且不得伪装正式身份"
        )
    suffix = re.sub(r"^candidate[-_:]", "", value, flags=re.IGNORECASE)
    if is_forbidden_protocol_control_code(suffix):
        raise ValueError(
            f"{field_name} 不得使用 IN/EX/REQ/CTRL 伪官方或官方编号形态"
        )


def _validate_atom_sources(
    source_span_ids: Sequence[str],
    source_excerpts: Sequence[str],
    *,
    strict: bool,
    label: str,
) -> None:
    """Validate the positional source closure carried by one semantic atom.

    The source lists intentionally stay positional: each ``source_span_ids[i]``
    is the span that supports ``source_excerpts[i]``.  A control-level source
    union cannot provide the same guarantee.  ``strict=False`` is retained only
    for the already accepted 5.8a placeholder constructor; all new DNF draft
    and hydrated atom types use ``strict=True``.
    """

    if not strict and not source_span_ids and not source_excerpts:
        return
    if not source_span_ids or not source_excerpts:
        raise ValueError(f"{label} 必须同时提供直接来源片段 ID 和精确摘录")
    if len(source_span_ids) != len(source_excerpts):
        raise ValueError(f"{label} 的来源片段 ID 与精确摘录必须一一对应")
    if any(not value.strip() for value in source_span_ids):
        raise ValueError(f"{label} 的来源片段 ID 不得为空")
    if any(not value.strip() for value in source_excerpts):
        raise ValueError(f"{label} 的精确摘录不得为空")


def _reject_duplicate_dnf_groups(groups: Sequence[object], label: str) -> None:
    fingerprints = {
        json.dumps(
            group.model_dump(mode="json"),  # type: ignore[attr-defined]
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for group in groups
    }
    if len(fingerprints) != len(groups):
        raise ValueError(f"{label} DNF 不得包含重复替代组")


class TableCellContext(ContractModel):
    """表格行列语境：保留表头与单元格定位，供全文覆盖而非关键词过滤。"""

    model_config = ConfigDict(extra="forbid")

    table_path: tuple[int, ...] = Field(min_length=2)
    row_index: int = Field(ge=0)
    column_index: int = Field(ge=0)
    member_cell_paths: list[tuple[int, ...]] = Field(min_length=1)
    row_headers: list[str] = Field(default_factory=list)
    column_headers: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_table_context(self) -> "TableCellContext":
        if len(self.table_path) % 2 != 0:
            raise ValueError("table_path 必须由 (row, col) 对组成")
        if any(value < 0 for value in self.table_path):
            raise ValueError("table_path 坐标必须非负")
        if (
            self.row_index != self.table_path[-2]
            or self.column_index != self.table_path[-1]
        ):
            raise ValueError("row_index/column_index 必须等于 table_path 最内层坐标")
        if len(self.member_cell_paths) != len(set(self.member_cell_paths)):
            raise ValueError("表格结构单元的成员单元格路径不得重复")
        if any(
            len(path) % 2 != 0 or any(value < 0 for value in path)
            for path in self.member_cell_paths
        ):
            raise ValueError("成员单元格路径必须由非负 (row, col) 对组成")
        if any(path[-2] != self.row_index for path in self.member_cell_paths):
            raise ValueError("表格行成员必须属于同一行")
        if any(not header.strip() for header in self.row_headers):
            raise ValueError("行表头不得包含空字符串")
        if any(not header.strip() for header in self.column_headers):
            raise ValueError("列表头不得包含空字符串")
        return self


class ProtocolStructureUnit(Phase5ControlModel):
    """选定期别全文结构单元：保留标题路径、表格语境、来源定位与原文顺序。"""

    structure_unit_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    member_source_refs: list[str] = Field(min_length=1)
    source_span_ids: list[str] = Field(min_length=1)
    unit_kind: StructureUnitKind
    heading_path: list[str] = Field(min_length=1)
    table_context: TableCellContext | None = None
    is_footnote_or_note: bool = False
    source_order: int = Field(ge=0)
    study_phase: StudyPhase
    phase_scopes: list[PhaseScope] = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    # 关键词只影响优先级，不得用于过滤未命中单元。
    priority_rank: int = Field(default=0, ge=0)
    priority_keyword_hits: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unit(self) -> "ProtocolStructureUnit":
        _require_sorted_unique(self.member_source_refs, "member_source_refs")
        _require_sorted_unique(self.source_span_ids, "source_span_ids")
        if len(self.phase_scopes) != len(set(self.phase_scopes)):
            raise ValueError("结构单元期别适用性不得重复")
        if any(not segment.strip() for segment in self.heading_path):
            raise ValueError("标题路径分段不得为空")
        if any(not hit.strip() for hit in self.priority_keyword_hits):
            raise ValueError("优先级关键词命中不得包含空字符串")
        if self.unit_kind in {
            StructureUnitKind.TABLE_HEADER,
            StructureUnitKind.TABLE_ROW,
            StructureUnitKind.TABLE_NOTE,
        } and self.table_context is None:
            raise ValueError("表格类结构单元必须提供表格行列语境")
        if (
            self.unit_kind
            in {
                StructureUnitKind.PARAGRAPH,
                StructureUnitKind.LIST_ITEM,
            }
            and self.table_context is not None
            and not self.is_footnote_or_note
        ):
            # 段落/列表项可位于嵌套单元格内；允许 table_context。
            pass
        if (
            self.unit_kind == StructureUnitKind.FOOTNOTE_OR_ANNOTATION
            and not self.is_footnote_or_note
        ):
            raise ValueError("脚注/注释单元必须标记 is_footnote_or_note")
        return self


class StructureUnitDisposition(Phase5ControlModel):
    """单个结构单元的处置结果；与发布控制身份分离。"""

    structure_unit_id: str = Field(min_length=1)
    disposition: StructureUnitDispositionKind
    linked_official_code: str | None = Field(default=None, min_length=1)
    linked_procedure_catalog_item_id: str | None = Field(default=None, min_length=1)
    linked_procedure_candidate_id: str | None = Field(default=None, min_length=1)
    linked_control_candidate_id: str | None = Field(default=None, min_length=1)
    notes: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_disposition_links(self) -> "StructureUnitDisposition":
        if self.linked_official_code is not None:
            if not re.fullmatch(r"(IN|EX)-\d{2}", self.linked_official_code):
                raise ValueError(
                    "结构单元仅可链接既有官方 IN/EX 父编号，不得新建或使用 REQ/CTRL"
                )
            if self.disposition != StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY:
                raise ValueError("仅官方入排处置可链接官方 IN/EX 编号")
        if self.linked_procedure_catalog_item_id is not None:
            if _CONTROL_CANDIDATE_ID.fullmatch(self.linked_procedure_catalog_item_id):
                raise ValueError("正式流程目录身份不得使用流程候选身份")
            if self.disposition != StructureUnitDispositionKind.REQUIRED_PROCEDURE:
                raise ValueError("仅流程必做处置可链接必做项目录项")
        if self.linked_procedure_candidate_id is not None:
            _reject_invalid_control_candidate_identity(
                self.linked_procedure_candidate_id,
                "linked_procedure_candidate_id",
            )
            if self.disposition != StructureUnitDispositionKind.REQUIRED_PROCEDURE:
                raise ValueError("仅流程必做处置可链接流程候选身份")
        if (
            self.linked_procedure_catalog_item_id is not None
            and self.linked_procedure_candidate_id is not None
        ):
            raise ValueError("流程必做处置必须且只能绑定正式流程目录身份或流程候选身份")
        if self.linked_control_candidate_id is not None:
            _reject_forbidden_control_identity(
                self.linked_control_candidate_id,
                "linked_control_candidate_id",
            )
            if self.disposition != StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE:
                raise ValueError("仅其他控制候选处置可链接控制候选身份")
        if (
            self.disposition == StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY
            and self.linked_official_code is None
        ):
            raise ValueError("官方入排处置必须链接既有官方 IN/EX 编号")
        if (
            self.disposition == StructureUnitDispositionKind.REQUIRED_PROCEDURE
            and self.linked_procedure_catalog_item_id is None
            and self.linked_procedure_candidate_id is None
        ):
            raise ValueError("流程必做处置必须且只能绑定正式流程目录身份或流程候选身份")
        if (
            self.disposition == StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
            and self.linked_control_candidate_id is None
        ):
            raise ValueError("其他控制候选处置必须链接控制候选身份")
        return self


class ProtocolSectionCoverageManifest(Phase5ControlModel):
    """选定期别全文结构单元覆盖清单；完整性与关键词优先级分离。"""

    manifest_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    protocol_document_sha256: str = Field(pattern=_SHA256)
    study_phase: StudyPhase
    snapshot_id: str = Field(min_length=1)
    units: list[ProtocolStructureUnit] = Field(min_length=1)
    dispositions: list[StructureUnitDisposition] = Field(default_factory=list)
    # 仅当全部单元已处置时可为 True；关键词命中不得影响 units 成员资格。
    claims_full_coverage: bool = False

    @model_validator(mode="after")
    def validate_manifest(self) -> "ProtocolSectionCoverageManifest":
        unit_ids = [unit.structure_unit_id for unit in self.units]
        if len(unit_ids) != len(set(unit_ids)):
            raise ValueError("结构单元 ID 必须唯一")
        source_orders = [unit.source_order for unit in self.units]
        if len(source_orders) != len(set(source_orders)):
            raise ValueError("结构单元原文顺序必须唯一")
        if any(unit.study_phase != self.study_phase for unit in self.units):
            raise ValueError("结构单元期别必须与覆盖清单期别一致")
        if self.units != sorted(self.units, key=lambda item: item.source_order):
            raise ValueError("结构单元必须按原文顺序排列")

        disposition_ids = [
            item.structure_unit_id for item in self.dispositions
        ]
        if len(disposition_ids) != len(set(disposition_ids)):
            raise ValueError("每个结构单元至多一条处置")
        unknown = set(disposition_ids) - set(unit_ids)
        if unknown:
            raise ValueError("处置不得引用覆盖清单外的结构单元")

        disposed = set(disposition_ids)
        missing = [unit_id for unit_id in unit_ids if unit_id not in disposed]
        if self.claims_full_coverage and missing:
            raise ValueError(
                "存在未处置结构单元时不得宣称全方案解构完整："
                + ",".join(missing)
            )
        if self.claims_full_coverage and len(self.dispositions) != len(self.units):
            raise ValueError("宣称全文覆盖完整时，处置条数必须等于结构单元数")
        return self

    @property
    def undisposed_structure_unit_ids(self) -> list[str]:
        disposed = {item.structure_unit_id for item in self.dispositions}
        return [
            unit.structure_unit_id
            for unit in self.units
            if unit.structure_unit_id not in disposed
        ]
class ProtocolControlDiscoveryDecision(Phase5ControlModel):
    """Provider-neutral coarse routing for one frozen manifest unit."""

    structure_unit_id: str = Field(min_length=1)
    disposition: ProtocolControlDiscoveryDisposition
    required_context_structure_unit_ids: list[str] = Field(default_factory=list)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_context_scope(self) -> "ProtocolControlDiscoveryDecision":
        _require_sorted_unique(
            self.required_context_structure_unit_ids,
            "发现阶段所需上下文结构单元",
        )
        if self.structure_unit_id in self.required_context_structure_unit_ids:
            raise ValueError("发现阶段单元不得将自身声明为上下文")
        if (
            self.disposition
            in {
                ProtocolControlDiscoveryDisposition.CONTEXT_ONLY,
                ProtocolControlDiscoveryDisposition.NON_CONTROL,
            }
            and self.required_context_structure_unit_ids
        ):
            raise ValueError("context_only/non_control 处置不得反向声明所服务的单元")
        return self


class ProtocolControlDiscoveryBatch(Phase5ControlModel):
    """Bounded first-stage input; target units are coarse-screened once."""

    discovery_batch_id: str = Field(min_length=1)
    coverage_manifest_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    study_phase: StudyPhase
    batch_number: int = Field(ge=1)
    batch_total: int = Field(ge=1)
    target_units: list[ProtocolStructureUnit] = Field(min_length=1)
    context_units: list[ProtocolStructureUnit] = Field(default_factory=list)
    target_structure_unit_ids: list[str] = Field(min_length=1)
    context_structure_unit_ids: list[str] = Field(default_factory=list)
    target_source_span_ids: list[str] = Field(min_length=1)
    context_source_span_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_batch(self) -> "ProtocolControlDiscoveryBatch":
        if self.batch_number > self.batch_total:
            raise ValueError("发现批次序号不得大于批次总数")
        target_ids = [unit.structure_unit_id for unit in self.target_units]
        context_ids = [unit.structure_unit_id for unit in self.context_units]
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("发现批次 target_units 不得重复")
        if len(context_ids) != len(set(context_ids)):
            raise ValueError("发现批次 context_units 不得重复")
        if target_ids != self.target_structure_unit_ids:
            raise ValueError(
                "target_structure_unit_ids 必须与 target_units 顺序和身份一致"
            )
        if context_ids != self.context_structure_unit_ids:
            raise ValueError(
                "context_structure_unit_ids 必须与 context_units 顺序和身份一致"
            )
        if set(target_ids) & set(context_ids):
            raise ValueError("发现批次 target/context 单元不得重叠")
        target_orders = [unit.source_order for unit in self.target_units]
        context_orders = [unit.source_order for unit in self.context_units]
        if target_orders != sorted(target_orders):
            raise ValueError("发现批次 target_units 必须按原文顺序排列")
        if context_orders != sorted(context_orders):
            raise ValueError("发现批次 context_units 必须按原文顺序排列")
        if any(
            unit.study_phase != self.study_phase
            for unit in (*self.target_units, *self.context_units)
        ):
            raise ValueError("发现批次结构单元期别必须与批次一致")
        expected_target_spans = sorted(
            {span_id for unit in self.target_units for span_id in unit.source_span_ids}
        )
        expected_context_spans = sorted(
            {span_id for unit in self.context_units for span_id in unit.source_span_ids}
        )
        if self.target_source_span_ids != expected_target_spans:
            raise ValueError("target_source_span_ids 必须闭合到全部 target_units")
        if self.context_source_span_ids != expected_context_spans:
            raise ValueError("context_source_span_ids 必须闭合到全部 context_units")
        _require_sorted_unique(self.target_source_span_ids, "target_source_span_ids")
        _require_sorted_unique(
            self.context_source_span_ids,
            "context_source_span_ids",
        )
        return self

    @property
    def structure_units(self) -> tuple[ProtocolStructureUnit, ...]:
        """Target units shown to the discovery model."""

        return tuple(self.target_units)


class ProtocolControlDiscoveryPlan(Phase5ControlModel):
    """System-owned full-manifest plan for the bounded discovery stage."""

    plan_id: str = Field(min_length=1)
    coverage_manifest_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    protocol_document_sha256: str = Field(pattern=_SHA256)
    snapshot_id: str = Field(min_length=1)
    study_phase: StudyPhase
    manifest_structure_unit_count: int = Field(ge=1)
    manifest_structure_unit_ids_sha256: str = Field(pattern=_SHA256)
    expected_structure_unit_ids: list[str] = Field(min_length=1)
    max_units_per_batch: int = Field(ge=1)
    context_radius: int = Field(ge=0)
    batches: list[ProtocolControlDiscoveryBatch] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_plan(self) -> "ProtocolControlDiscoveryPlan":
        expected_ids = self.expected_structure_unit_ids
        if any(not value.strip() for value in expected_ids):
            raise ValueError("发现计划 expected_structure_unit_ids 不得包含空 ID")
        if len(expected_ids) != len(set(expected_ids)):
            raise ValueError("发现计划 expected_structure_unit_ids 不得重复")
        if self.manifest_structure_unit_count != len(expected_ids):
            raise ValueError("发现计划结构单元总数与完整清单不一致")
        if (
            self.manifest_structure_unit_ids_sha256
            != stable_protocol_control_manifest_structure_unit_ids_sha256(
                expected_ids
            )
        ):
            raise ValueError("发现计划完整清单结构单元身份哈希不一致")
        expected_set = set(expected_ids)
        if any(
            batch.coverage_manifest_id != self.coverage_manifest_id
            or batch.protocol_version_id != self.protocol_version_id
            or batch.study_phase != self.study_phase
            for batch in self.batches
        ):
            raise ValueError("发现批次必须绑定同一清单、方案版本和期别")
        batch_total = len(self.batches)
        if any(batch.batch_total != batch_total for batch in self.batches):
            raise ValueError("发现批次 batch_total 必须等于发现计划批次数")
        numbers = [batch.batch_number for batch in self.batches]
        if numbers != list(range(1, batch_total + 1)):
            raise ValueError("发现批次必须按连续序号排列")
        target_ids = [
            structure_unit_id
            for batch in self.batches
            for structure_unit_id in batch.target_structure_unit_ids
        ]
        if target_ids != expected_ids:
            raise ValueError("发现批次必须按原文顺序恰好覆盖完整清单")
        if any(
            len(batch.target_units) > self.max_units_per_batch
            for batch in self.batches
        ):
            raise ValueError("发现批次超过 max_units_per_batch")
        unit_by_id: dict[str, ProtocolStructureUnit] = {}
        for batch in self.batches:
            for unit in (*batch.target_units, *batch.context_units):
                if unit.structure_unit_id not in expected_set:
                    raise ValueError("发现批次引用了完整清单外的结构单元")
                previous = unit_by_id.get(unit.structure_unit_id)
                if previous is not None and previous != unit:
                    raise ValueError("同一发现结构单元的冻结原文不得漂移")
                unit_by_id[unit.structure_unit_id] = unit
        if set(unit_by_id) != expected_set:
            raise ValueError("发现计划未冻结全部结构单元原文")
        if any(
            context_id not in expected_set
            for batch in self.batches
            for context_id in batch.context_structure_unit_ids
        ):
            raise ValueError("发现批次上下文结构单元越出完整清单")
        source_orders = [
            unit.source_order
            for batch in self.batches
            for unit in batch.target_units
        ]
        if source_orders != sorted(source_orders):
            raise ValueError("发现批次 target_units 必须保持原文顺序")
        return self

    @property
    def manifest_structure_unit_ids(self) -> tuple[str, ...]:
        """Full identity is retained only by this system-owned plan."""

        return tuple(self.expected_structure_unit_ids)

    @property
    def total_structure_unit_count(self) -> int:
        return self.manifest_structure_unit_count




class ProtocolControlCandidate(Phase5ControlModel):
    """Agent 侧其他控制候选：绑定冻结结构单元，尚未成为发布控制。"""

    control_candidate_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    study_phase: StudyPhase
    frozen_structure_unit_ids: list[str] = Field(min_length=1)
    title: str = Field(min_length=1)
    applicable_population: str | None = Field(default=None, min_length=1)
    trigger_condition: str | None = Field(default=None, min_length=1)
    source_span_ids: list[str] = Field(min_length=1)
    # Candidate identity is system-owned.  The semantic payload is optional for
    # the 5.8a frozen-candidate boundary and becomes required only after the
    # dedicated control Agent output has been hydrated.
    semantics: ProtocolControlCandidateSemantics | None = None

    @model_validator(mode="after")
    def validate_candidate(self) -> "ProtocolControlCandidate":
        _reject_forbidden_control_identity(
            self.control_candidate_id,
            "control_candidate_id",
        )
        _require_sorted_unique(
            self.frozen_structure_unit_ids,
            "frozen_structure_unit_ids",
        )
        _require_sorted_unique(self.source_span_ids, "source_span_ids")
        if self.semantics is not None:
            if self.title != self.semantics.title:
                raise ValueError("候选标题必须与水合语义标题一致")
            if self.applicable_population != self.semantics.applicable_population:
                raise ValueError("候选适用人群必须与水合语义一致")
            if (
                self.semantics.control_candidate_id is not None
                and self.semantics.control_candidate_id != self.control_candidate_id
            ):
                raise ValueError("候选水合语义必须绑定当前控制候选身份")
            if self.semantics.source_structure_unit_ids != self.frozen_structure_unit_ids:
                raise ValueError("候选水合语义的结构单元范围必须等于冻结候选范围")
            if self.semantics.source_span_ids != self.source_span_ids:
                raise ValueError("候选水合语义的来源片段必须等于候选来源闭包")
        return self


class ProtocolControlCandidateDisposition(Phase5ControlModel):
    """Agent 对冻结结构单元身份的候选处置；与发布控制目录分离。"""

    disposition_id: str = Field(min_length=1)
    coverage_manifest_id: str = Field(min_length=1)
    action: ControlCandidateAction
    frozen_structure_unit_ids: list[str] = Field(min_length=1)
    control_candidate_id: str | None = Field(default=None, min_length=1)
    exclude_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_candidate_disposition(
        self,
    ) -> "ProtocolControlCandidateDisposition":
        _require_sorted_unique(
            self.frozen_structure_unit_ids,
            "frozen_structure_unit_ids",
        )
        if self.action == ControlCandidateAction.EXCLUDE:
            if self.control_candidate_id is not None:
                raise ValueError("明确排除不得同时绑定控制候选身份")
            if not self.exclude_reason:
                raise ValueError("明确排除必须给出排除理由")
            return self
        if self.control_candidate_id is None:
            raise ValueError("结构化或拆分必须绑定控制候选身份")
        _reject_forbidden_control_identity(
            self.control_candidate_id,
            "control_candidate_id",
        )
        if self.exclude_reason is not None:
            raise ValueError("结构化或拆分不得携带排除理由")
        return self


class ControlContinuingObligation(Phase5ControlModel):
    """Source-bound prohibition that is not yet due at an eligibility node."""

    statement: str = Field(min_length=1)
    prospective_period: ProspectivePeriod
    source_span_ids: list[str] = Field(min_length=1)
    source_excerpts: list[str] = Field(min_length=1)
    status: Literal["not_due_at_review_node"] = "not_due_at_review_node"

    @model_validator(mode="after")
    def validate_sources(self) -> "ControlContinuingObligation":
        _validate_atom_sources(
            self.source_span_ids, self.source_excerpts, strict=True, label="后续持续义务"
        )
        return self


def _validate_continuing_obligation(atom: object) -> None:
    continuation = getattr(atom, "continuing_obligation", None)
    if continuation is None:
        return
    if getattr(atom, "kind") not in {
        ControlObligationKind.PROHIBIT_EVENT,
        ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE,
    }:
        raise ValueError("后续持续义务只适用于禁止类原子")
    if getattr(atom, "prospective_period") is not None:
        raise ValueError("当前节点义务不得同时承担后续持续期间")
    sources = set(zip(getattr(atom, "source_span_ids"), getattr(atom, "source_excerpts")))
    if not set(zip(continuation.source_span_ids, continuation.source_excerpts)) <= sources:
        raise ValueError("后续持续义务必须引用同一原子的直接来源")


class ControlObligationAtom(Phase5ControlModel):
    """正式控制的单个类型化义务原子。"""

    obligation_id: str = Field(min_length=1)
    evaluation: ControlAtomEvaluationSpec | None = None

    @model_serializer(mode="wrap")
    def serialize_evaluation(self, handler):
        value = handler(self)
        if self.evaluation is None:
            value.pop("evaluation", None)
        if self.continuing_obligation is None:
            value.pop("continuing_obligation", None)
        return value
    kind: ControlObligationKind
    statement: str = Field(min_length=1)
    time_constraint: TimeConstraint | None = None
    prospective_period: ProspectivePeriod | None = None
    continuing_obligation: ControlContinuingObligation | None = None
    modality: ControlObligationModality = ControlObligationModality.MANDATORY
    temporal_scope: ControlTemporalScopeKind | None = None
    # 旧的 5.8a 构造器允许先创建没有来源的占位义务；严格的 5.8b
    # candidate/published DNF 会在 ``ControlObligationGroup`` 中要求这两列。
    # 将来源放在原子上，而不是控制级别，防止一个原文摘录被错误地复用为
    # 同一控制内所有义务的证据。
    source_span_ids: list[str] = Field(default_factory=list)
    source_excerpts: list[str | None] = Field(default_factory=list)
    requires_professional_judgment: bool = False

    @model_validator(mode="after")
    def validate_obligation_sources(self) -> "ControlObligationAtom":
        validate_control_atom_evaluation(self)
        _validate_obligation_semantics(
            kind=self.kind,
            modality=self.modality,
            temporal_scope=self.temporal_scope,
            time_constraint=self.time_constraint,
        )
        _validate_atom_sources(
            self.source_span_ids,
            self.source_excerpts,
            strict=False,
            label="义务原子",
        )
        _validate_continuing_obligation(self)
        return self


class ControlConditionAtomDraft(Phase5ControlModel):
    """Provider-neutral condition draft with no model-owned stable identity.

    This is the semantic payload that a future wire adapter may parse.  The
    system assigns ``condition_atom_id`` only when hydrating it into
    :class:`ControlConditionAtom`; a provider cannot choose or persist that
    identity.
    """

    statement: str = Field(min_length=1)
    evaluation: ControlAtomEvaluationSpec | None = None

    @model_serializer(mode="wrap")
    def serialize_evaluation(self, handler):
        value = handler(self)
        if self.evaluation is None:
            value.pop("evaluation", None)
        return value
    source_span_ids: list[str] = Field(min_length=1)
    source_excerpts: list[str] = Field(min_length=1)
    time_constraint: TimeConstraint | None = None
    requires_professional_judgment: bool = False

    @model_validator(mode="after")
    def validate_condition_sources(self) -> "ControlConditionAtomDraft":
        validate_control_atom_evaluation(self)
        _validate_atom_sources(
            self.source_span_ids,
            self.source_excerpts,
            strict=True,
            label="条件原子草稿",
        )
        return self


class ControlConditionAtom(ControlConditionAtomDraft):
    """System-hydrated condition atom with a system-owned stable identity."""

    condition_atom_id: str = Field(
        min_length=1,
        validation_alias=AliasChoices(
            "condition_atom_id",
            "condition_id",
            "atom_id",
        ),
    )


class ControlObligationAtomDraft(Phase5ControlModel):
    """Provider-neutral typed obligation atom; stable obligation IDs are injected."""

    kind: ControlObligationKind
    evaluation: ControlAtomEvaluationSpec | None = None

    @model_serializer(mode="wrap")
    def serialize_evaluation(self, handler):
        value = handler(self)
        if self.evaluation is None:
            value.pop("evaluation", None)
        if self.continuing_obligation is None:
            value.pop("continuing_obligation", None)
        return value
    statement: str = Field(min_length=1)
    time_constraint: TimeConstraint | None = None
    prospective_period: ProspectivePeriod | None = None
    continuing_obligation: ControlContinuingObligation | None = None
    modality: ControlObligationModality = ControlObligationModality.MANDATORY
    temporal_scope: ControlTemporalScopeKind | None = None
    source_span_ids: list[str] = Field(min_length=1)
    source_excerpts: list[str] = Field(min_length=1)
    requires_professional_judgment: bool = False

    @model_validator(mode="after")
    def validate_obligation_draft_sources(self) -> "ControlObligationAtomDraft":
        validate_control_atom_evaluation(self)
        _validate_obligation_semantics(
            kind=self.kind,
            modality=self.modality,
            temporal_scope=self.temporal_scope,
            time_constraint=self.time_constraint,
        )
        _validate_atom_sources(
            self.source_span_ids,
            self.source_excerpts,
            strict=True,
            label="义务原子草稿",
        )
        _validate_continuing_obligation(self)
        return self


class ControlConditionGroupDraft(Phase5ControlModel):
    """One DNF conjunction (all atoms in ``atoms`` must hold).

    Exception-layer drafts may carry:
    - ``waives_trigger_branch_indexes``: which trigger branches this condition
      overrides;
    - ``activates_obligation_group_indexes``: which obligation groups become the
      replacement consequences when this condition holds.

    Applicability/trigger drafts must leave both lists empty.  Hydration
    converts ordinals into system-owned branch/group IDs.
    """

    atoms: list[ControlConditionAtomDraft] = Field(min_length=1)
    waives_trigger_branch_indexes: list[int] = Field(default_factory=list)
    activates_obligation_group_indexes: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_scope_indexes(self) -> "ControlConditionGroupDraft":
        if self.waives_trigger_branch_indexes:
            _require_sorted_nonnegative_unique(
                self.waives_trigger_branch_indexes,
                "例外触发分支序位",
            )
        if self.activates_obligation_group_indexes:
            _require_sorted_nonnegative_unique(
                self.activates_obligation_group_indexes,
                "例外激活义务组序位",
            )
        return self


class ControlConditionGroup(Phase5ControlModel):
    """System-hydrated condition conjunction.

    ``trigger_branch_id`` is set only for trigger-layer groups.  Exception
    scopes and obligation activations live on :class:`ControlExceptionGroup`.
    """

    atoms: list[ControlConditionAtom] = Field(min_length=1)
    trigger_branch_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_unique_atom_ids(self) -> "ControlConditionGroup":
        ids = [atom.condition_atom_id for atom in self.atoms]
        if len(ids) != len(set(ids)):
            raise ValueError("条件合取组内原子 ID 不得重复")
        return self


class ControlObligationGroupDraft(Phase5ControlModel):
    """One obligation DNF conjunction; each atom retains its own source closure.

    ``applies_to_trigger_branch_indexes`` scopes this obligation path to explicit
    trigger branches.  Empty means control-level / unscoped.  Whether the group
    is a default path or a conditional replacement is decided by exception-side
    ``activates_obligation_group_indexes`` during hydration—not by free OR.
    """

    atoms: list[ControlObligationAtomDraft] = Field(min_length=1)
    applies_to_trigger_branch_indexes: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_apply_indexes(self) -> "ControlObligationGroupDraft":
        if self.applies_to_trigger_branch_indexes:
            _require_sorted_nonnegative_unique(
                self.applies_to_trigger_branch_indexes,
                "义务触发分支序位",
            )
        return self


class ControlObligationGroup(Phase5ControlModel):
    """System-hydrated obligation conjunction.

    ``obligation_group_id`` is system-owned.  ``activated_by_exception_group_ids``
    is empty for the default path; non-empty means this group is only the
    replacement consequence when those exception groups hold—not an
    unconditional OR sibling of the default window.
    """

    atoms: list[ControlObligationAtom] = Field(min_length=1)
    obligation_group_id: str | None = Field(default=None, min_length=1)
    applies_to_trigger_branch_ids: list[str] = Field(default_factory=list)
    activated_by_exception_group_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_strict_obligation_sources(self) -> "ControlObligationGroup":
        ids = [atom.obligation_id for atom in self.atoms]
        if len(ids) != len(set(ids)):
            raise ValueError("义务合取组内原子 ID 不得重复")
        if self.applies_to_trigger_branch_ids:
            _require_sorted_unique(
                list(self.applies_to_trigger_branch_ids),
                "义务触发分支作用域",
            )
        if self.activated_by_exception_group_ids:
            _require_sorted_unique(
                list(self.activated_by_exception_group_ids),
                "义务条件激活例外组",
            )
        for atom in self.atoms:
            _validate_atom_sources(
                atom.source_span_ids,
                atom.source_excerpts,
                strict=True,
                label="正式义务原子",
            )
        return self


class ControlConditionDnfDraft(Phase5ControlModel):
    """Explicit DNF draft: groups are alternatives, atoms per group are ALL."""

    groups: list[ControlConditionGroupDraft] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_groups(self) -> "ControlConditionDnfDraft":
        if any(not group.atoms for group in self.groups):
            raise ValueError("条件 DNF 不得包含空合取组")
        _reject_duplicate_dnf_groups(self.groups, "条件")
        return self


class ControlConditionDnf(Phase5ControlModel):
    """System-hydrated condition DNF: ``(A AND B) OR (C ...)``."""

    groups: list[ControlConditionGroup] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_groups(self) -> "ControlConditionDnf":
        if any(not group.atoms for group in self.groups):
            raise ValueError("条件 DNF 不得包含空合取组")
        _reject_duplicate_dnf_groups(self.groups, "条件")
        ids = [
            atom.condition_atom_id
            for group in self.groups
            for atom in group.atoms
        ]
        if len(ids) != len(set(ids)):
            raise ValueError("条件 DNF 中原子 ID 不得重复")
        return self


class ControlObligationDnfDraft(Phase5ControlModel):
    """Explicit obligation DNF draft; multiple obligation kinds are allowed."""

    groups: list[ControlObligationGroupDraft] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_groups(self) -> "ControlObligationDnfDraft":
        if any(not group.atoms for group in self.groups):
            raise ValueError("义务 DNF 不得包含空合取组")
        _reject_duplicate_dnf_groups(self.groups, "义务")
        return self


class ControlObligationDnf(Phase5ControlModel):
    """System-hydrated obligation DNF with typed, source-backed atoms."""

    groups: list[ControlObligationGroup] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_groups(self) -> "ControlObligationDnf":
        if any(not group.atoms for group in self.groups):
            raise ValueError("义务 DNF 不得包含空合取组")
        _reject_duplicate_dnf_groups(self.groups, "义务")
        ids = [
            atom.obligation_id
            for group in self.groups
            for atom in group.atoms
        ]
        if len(ids) != len(set(ids)):
            raise ValueError("义务 DNF 中原子 ID 不得重复")
        return self


class ControlExceptionGroup(Phase5ControlModel):
    """One explicit exception conjunction; exceptions are not obligation fields.

    ``waives_trigger_branch_ids`` keeps the condition local to named trigger
    branches.  ``activates_obligation_group_ids`` binds that condition to the
    replacement obligation consequences (e.g. clearance-agent condition →
    6-month prohibition group).  Condition atoms express only the predicate;
    substitute time windows live on the activated obligation groups.
    """

    atoms: list[ControlConditionAtom] = Field(min_length=1)
    exception_group_id: str | None = Field(default=None, min_length=1)
    waives_trigger_branch_ids: list[str] = Field(default_factory=list)
    activates_obligation_group_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_atom_ids(self) -> "ControlExceptionGroup":
        ids = [atom.condition_atom_id for atom in self.atoms]
        if len(ids) != len(set(ids)):
            raise ValueError("例外合取组内原子 ID 不得重复")
        if self.waives_trigger_branch_ids:
            _require_sorted_unique(
                list(self.waives_trigger_branch_ids),
                "例外触发分支作用域",
            )
        if self.activates_obligation_group_ids:
            _require_sorted_unique(
                list(self.activates_obligation_group_ids),
                "例外激活义务组",
            )
        return self


class ControlExceptionDnf(Phase5ControlModel):
    """Exception DNF kept independent from applicability, trigger and obligations."""

    groups: list[ControlExceptionGroup] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_groups(self) -> "ControlExceptionDnf":
        if any(not group.atoms for group in self.groups):
            raise ValueError("例外 DNF 不得包含空合取组")
        _reject_duplicate_dnf_groups(self.groups, "例外")
        ids = [
            atom.condition_atom_id
            for group in self.groups
            for atom in group.atoms
        ]
        if len(ids) != len(set(ids)):
            raise ValueError("例外 DNF 中原子 ID 不得重复")
        return self


class ControlRepeatTriggerDraft(Phase5ControlModel):
    condition_id: str = Field(min_length=1)
    expression: ControlConditionDnfDraft
    evidence_roles: list[RepeatEvidenceRoleReference] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def preserve_legacy_roles(self, handler):
        value = handler(self)
        if not self.evidence_roles:
            value.pop("evidence_roles", None)
        return value

    @model_validator(mode="after")
    def validate_role_references(self):
        resolve_repeat_evidence_roles(self.evidence_roles, [
            [f"{i}:{j}" for j, _ in enumerate(group.atoms)]
            for i, group in enumerate(self.expression.groups)
        ])
        return self


class ControlRepeatTrigger(Phase5ControlModel):
    condition_id: str = Field(min_length=1)
    expression: ControlConditionDnf
    predicate_evidence_roles: dict[str, RepeatEvidenceRole] = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def preserve_legacy_roles(self, handler):
        value = handler(self)
        if not self.predicate_evidence_roles:
            value.pop("predicate_evidence_roles", None)
        return value

    @model_validator(mode="after")
    def validate_role_identities(self):
        validate_repeat_evidence_roles(self.predicate_evidence_roles, [
            atom.condition_atom_id for group in self.expression.groups for atom in group.atoms
        ])
        return self


def validate_control_repeat_conditions(control):
    conditions = {item.condition_id: item for item in control.repeat_trigger_conditions}
    if len(conditions) != len(control.repeat_trigger_conditions) or any(not key.strip() for key in conditions):
        raise ValueError("复查触发条件身份须非空且不能重复")
    owners = [atom for name in ("applicability_expression", "trigger_expression",
                               "obligation_expression", "exception_expression")
              for expression in (getattr(control, name),) if expression is not None
              for group in expression.groups for atom in group.atoms]
    if getattr(control, "obligation_expression", None) is None:
        owners.extend(getattr(control, "obligations", []))
    atoms = [*owners, *(atom for condition in conditions.values()
                       for group in condition.expression.groups for atom in group.atoms)]
    identities = [identity for atom in atoms
                  if (identity := getattr(atom, "condition_atom_id", None)
                      or getattr(atom, "obligation_id", None)) is not None]
    if len(identities) != len(set(identities)):
        raise ValueError("复查条件与本控制其他条件的原子编号不得重复")
    referenced = set()
    for owner in owners:
        scheme = owner.evaluation.repeat_scheme if owner.evaluation is not None else None
        if scheme is None:
            continue
        sources = dict(zip(scheme.source_span_ids, scheme.source_excerpts, strict=True))
        for condition_id in scheme.ancillary_condition_ids:
            referenced.add(condition_id)
            condition = conditions.get(condition_id)
            if condition is None:
                raise ValueError("复查要求缺少对应的完整触发或许可条件")
            roles = (condition.predicate_evidence_roles.values()
                     if isinstance(condition, ControlRepeatTrigger)
                     else (item.evidence_role for item in condition.evidence_roles))
            if any(not any(quote in source for source in scheme.source_excerpts)
                   for role in roles for quote in role.source_excerpts):
                raise ValueError("复查取证范围须来自本项复查要求的方案原文")
            for group in condition.expression.groups:
                if any(getattr(group, field, []) for field in (
                    "waives_trigger_branch_indexes", "activates_obligation_group_indexes",
                    "waives_trigger_branch_ids", "activates_obligation_group_ids",
                    "trigger_branch_id",
                )):
                    raise ValueError("复查条件不能豁免或激活补充控制的入排分支")
                for atom in group.atoms:
                    if atom.evaluation is not None and atom.evaluation.repeat_scheme is not None:
                        raise ValueError("复查条件不能再次嵌套复查要求")
                    if any(span not in sources or excerpt not in sources[span]
                           for span, excerpt in zip(atom.source_span_ids, atom.source_excerpts, strict=True)):
                        raise ValueError("复查条件须来自本项复查要求的方案原文")
    if referenced != set(conditions):
        raise ValueError("不得加入未被本控制复查要求引用的额外条件")


class ProtocolControlCandidateSemanticDraft(Phase5ControlModel):
    """Non-identity semantic draft for one frozen candidate.

    ``applicability_expression``, ``trigger_expression``,
    ``obligation_expression`` and ``exception_expression`` deliberately remain
    four independent layers.  A missing optional condition layer means no
    condition was asserted; it must not be silently folded into obligations.
    """

    title: str = Field(min_length=1)
    applicable_population: str = Field(min_length=1)
    applicability_expression: ControlConditionDnfDraft | None = None
    trigger_expression: ControlConditionDnfDraft | None = None
    obligation_expression: ControlObligationDnfDraft = Field(...)
    exception_expression: ControlConditionDnfDraft | None = None
    repeat_trigger_conditions: list[ControlRepeatTriggerDraft] = Field(default_factory=list)
    review_node_bindings: list["ReviewNodeBinding"] = Field(min_length=1)
    minimum_evidence: list["ControlMinimumEvidenceDraft"] = Field(min_length=1)
    source_structure_unit_ids: list[str] = Field(min_length=1)
    source_span_ids: list[str] = Field(min_length=1)
    cross_source_relations: list["ControlCrossSourceRelationDraft"] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_draft_scope(self) -> "ProtocolControlCandidateSemanticDraft":
        validate_control_repeat_conditions(self)
        _require_sorted_unique(
            self.source_structure_unit_ids,
            "语义草稿 source_structure_unit_ids",
        )
        _require_sorted_unique(self.source_span_ids, "语义草稿 source_span_ids")
        for layer_name, expression in (
            ("适用性", self.applicability_expression),
            ("触发", self.trigger_expression),
        ):
            if expression is None:
                continue
            if any(group.waives_trigger_branch_indexes for group in expression.groups):
                raise ValueError(
                    f"{layer_name} DNF 不得携带例外触发分支序位"
                )
            if any(
                group.activates_obligation_group_indexes for group in expression.groups
            ):
                raise ValueError(
                    f"{layer_name} DNF 不得携带例外激活义务组序位"
                )
        atom_spans: set[str] = set()
        for expression in (
            self.applicability_expression,
            self.trigger_expression,
            self.exception_expression,
        ):
            if expression is not None:
                atom_spans.update(
                    span_id
                    for group in expression.groups
                    for atom in group.atoms
                    for span_id in atom.source_span_ids
                )
        atom_spans.update(
            span_id
            for group in self.obligation_expression.groups
            for atom in group.atoms
            for span_id in atom.source_span_ids
        )
        if not atom_spans <= set(self.source_span_ids):
            raise ValueError("语义草稿 source_span_ids 必须覆盖所有原子直接来源")
        relation_keys = [
            (
                item.kind.value,
                item.external_target_kind.value,
                item.external_target_id,
                item.candidate_side,
                item.affected_workflow_stage_id,
            )
            for item in self.cross_source_relations
        ]
        if len(relation_keys) != len(set(relation_keys)):
            raise ValueError("语义草稿跨来源关系不得重复")
        if any(
            target_kind
            not in {
                ControlRelationTargetKind.OFFICIAL_RULE,
                ControlRelationTargetKind.REQUIRED_PROCEDURE,
                ControlRelationTargetKind.WORKFLOW_STAGE,
            }
            for relation in self.cross_source_relations
            for target_kind in (relation.external_target_kind,)
        ):
            raise ValueError(
                "provider 关系草稿只能引用已知官方规则、流程必做项或冻结流程节点"
            )
        trigger_count = (
            len(self.trigger_expression.groups)
            if self.trigger_expression is not None
            else 0
        )
        obligation_count = len(self.obligation_expression.groups)
        if self.exception_expression is not None:
            for group in self.exception_expression.groups:
                if trigger_count == 0 and group.waives_trigger_branch_indexes:
                    raise ValueError("无触发 DNF 时例外不得声明触发分支作用域")
                if trigger_count > 0 and not group.waives_trigger_branch_indexes:
                    raise ValueError(
                        "存在触发 DNF 时每个例外路径必须声明可作用的触发分支序位"
                    )
                if any(
                    index >= trigger_count
                    for index in group.waives_trigger_branch_indexes
                ):
                    raise ValueError("例外触发分支序位越出触发 DNF 范围")
                if any(
                    index >= obligation_count
                    for index in group.activates_obligation_group_indexes
                ):
                    raise ValueError("例外激活义务组序位越出义务 DNF 范围")
                if group.activates_obligation_group_indexes and any(
                    atom.time_constraint is not None for atom in group.atoms
                ):
                    raise ValueError(
                        "激活替代义务的例外条件原子不得携带替代时间窗；"
                        "时间窗必须写在被激活的义务组上"
                    )
        for group in self.obligation_expression.groups:
            if trigger_count == 0 and group.applies_to_trigger_branch_indexes:
                raise ValueError("无触发 DNF 时义务不得声明触发分支作用域")
            if any(
                index >= trigger_count
                for index in group.applies_to_trigger_branch_indexes
            ):
                raise ValueError("义务触发分支序位越出触发 DNF 范围")
        return self


    @model_serializer(mode="wrap")
    def preserve_old_repeat_conditions(self, handler):
        value = handler(self)
        if not self.repeat_trigger_conditions:
            value.pop("repeat_trigger_conditions", None)
        return value


class ProtocolControlCandidateSemantics(Phase5ControlModel):
    """System-hydrated semantic layers with stable atom identities."""

    title: str = Field(min_length=1)
    applicable_population: str = Field(min_length=1)
    # System-owned identity is carried only after hydration so relation
    # endpoints can prove that they mention the current candidate.
    control_candidate_id: str | None = Field(default=None, min_length=1)
    applicability_expression: ControlConditionDnf | None = None
    trigger_expression: ControlConditionDnf | None = None
    obligation_expression: ControlObligationDnf
    exception_expression: ControlExceptionDnf | None = None
    repeat_trigger_conditions: list[ControlRepeatTrigger] = Field(default_factory=list)
    review_node_bindings: list["ReviewNodeBinding"] = Field(min_length=1)
    minimum_evidence: list["ControlMinimumEvidence"] = Field(min_length=1)
    source_structure_unit_ids: list[str] = Field(min_length=1)
    source_span_ids: list[str] = Field(min_length=1)
    cross_source_relations: list["ControlCrossSourceRelation"] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_hydrated_scope(self) -> "ProtocolControlCandidateSemantics":
        validate_control_repeat_conditions(self)
        _require_sorted_unique(
            self.source_structure_unit_ids,
            "水合语义 source_structure_unit_ids",
        )
        _require_sorted_unique(self.source_span_ids, "水合语义 source_span_ids")
        atom_spans: set[str] = set()
        for expression in (
            self.applicability_expression,
            self.trigger_expression,
            self.exception_expression,
        ):
            if expression is not None:
                atom_spans.update(
                    span_id
                    for group in expression.groups
                    for atom in group.atoms
                    for span_id in atom.source_span_ids
                )
        atom_spans.update(
            span_id
            for group in self.obligation_expression.groups
            for atom in group.atoms
            for span_id in atom.source_span_ids
        )
        if not atom_spans <= set(self.source_span_ids):
            raise ValueError("水合语义 source_span_ids 必须覆盖所有原子直接来源")
        relation_ids = [item.relation_id for item in self.cross_source_relations]
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("水合语义跨来源关系 ID 不得重复")
        if self.cross_source_relations:
            if self.control_candidate_id is None:
                raise ValueError(
                    "含跨来源关系的水合语义必须携带当前控制候选身份"
                )
            for relation in self.cross_source_relations:
                candidate_endpoints = [
                    target_id
                    for target_kind, target_id in (
                        (relation.left_target_kind, relation.left_target_id),
                        (relation.right_target_kind, relation.right_target_id),
                    )
                    if target_kind == ControlRelationTargetKind.CONTROL_CANDIDATE
                ]
                if candidate_endpoints != [self.control_candidate_id]:
                    raise ValueError(
                        "水合语义每条跨来源关系必须恰好指向当前控制候选身份"
                    )
        evidence_keys = [item.evidence_key for item in self.minimum_evidence]
        if len(evidence_keys) != len(set(evidence_keys)):
            raise ValueError("水合语义最低证据键不得重复")
        return self


    @model_serializer(mode="wrap")
    def preserve_old_repeat_conditions(self, handler):
        value = handler(self)
        if not self.repeat_trigger_conditions:
            value.pop("repeat_trigger_conditions", None)
        return value


class ReviewNodeBinding(Phase5ControlModel):
    """控制在审核节点上的显式作用绑定。"""

    workflow_stage_id: str = Field(min_length=1)
    review_stage: ReviewStage
    role: ReviewNodeRole
    guidance: str | None = Field(default=None, min_length=1)


class ControlMinimumEvidence(Phase5ControlModel):
    """正式控制的最低证据要求（不伪装为新的官方 REQ 编号）。"""

    evidence_key: str = Field(min_length=1)
    fact_type: str = Field(min_length=1)
    description: str = Field(min_length=1)
    due_stage: ReviewStage
    required_source_types: list[str] = Field(default_factory=list)
    # Empty only for decoding historical catalogs; new publication requires IDs.
    workflow_stage_ids: list[str] = Field(default_factory=list)
    source_policy: ControlEvidenceSourcePolicy | None = None
    atom_refs: list[ControlEvidenceAtomReference] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def serialize_evidence(self, handler):
        data = handler(self)
        if not self.atom_refs:
            data.pop("atom_refs", None)
        if not self.workflow_stage_ids:
            data.pop("workflow_stage_ids", None)
        if self.source_policy is None:
            data.pop("source_policy", None)
        return data

    @model_validator(mode="after")
    def validate_evidence(self) -> "ControlMinimumEvidence":
        _reject_forbidden_control_identity(self.evidence_key, "evidence_key")
        if any(not item.strip() for item in self.required_source_types):
            raise ValueError("最低证据资料类型不得包含空字符串")
        if any(not item.strip() for item in self.workflow_stage_ids) or len(self.workflow_stage_ids) != len(set(self.workflow_stage_ids)):
            raise ValueError("最低证据节点身份不得为空或重复")
        return self


class ControlMinimumEvidenceDraft(Phase5ControlModel):
    """Semantic evidence description before the system assigns ``evidence_key``."""

    fact_type: str = Field(min_length=1)
    description: str = Field(min_length=1)
    due_stage: ReviewStage
    required_source_types: list[str] = Field(default_factory=list)
    workflow_stage_ids: list[str] = Field(default_factory=list)
    source_policy: ControlEvidenceSourcePolicy | None = None
    atom_refs: list[ControlEvidenceAtomReference] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def serialize_evidence_draft(self, handler):
        data = handler(self)
        if not self.atom_refs:
            data.pop("atom_refs", None)
        if not self.workflow_stage_ids:
            data.pop("workflow_stage_ids", None)
        if self.source_policy is None:
            data.pop("source_policy", None)
        return data

    @model_validator(mode="after")
    def validate_evidence_draft(self) -> "ControlMinimumEvidenceDraft":
        if any(not item.strip() for item in self.required_source_types):
            raise ValueError("最低证据资料类型不得包含空字符串")
        if any(not item.strip() for item in self.workflow_stage_ids) or len(self.workflow_stage_ids) != len(set(self.workflow_stage_ids)):
            raise ValueError("最低证据节点身份不得为空或重复")
        return self


class ControlCrossSourceRelation(Phase5ControlModel):
    """控制与官方规则/流程/其他控制之间的可审计关系。"""

    relation_id: str = Field(min_length=1)
    kind: CrossSourceRelationKind
    left_target_kind: ControlRelationTargetKind
    left_target_id: str = Field(min_length=1)
    right_target_kind: ControlRelationTargetKind
    right_target_id: str = Field(min_length=1)
    # Only supplementary relations to a visit-level required procedure use
    # this node. Older read-only records remain decodable with ``None``;
    # publication gates require it for newly publishable candidates.
    affected_workflow_stage_id: str | None = Field(default=None, min_length=1)
    # 仅完全等价且经确认的重复可共享评估身份。
    shared_assessment_identity: str | None = Field(default=None, min_length=1)
    notes: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_relation(self) -> "ControlCrossSourceRelation":
        if (
            self.left_target_kind == self.right_target_kind
            and self.left_target_id == self.right_target_id
        ):
            raise ValueError("跨来源关系两端不得指向同一身份")
        for target_kind, target_id, field_name in (
            (self.left_target_kind, self.left_target_id, "left_target_id"),
            (self.right_target_kind, self.right_target_id, "right_target_id"),
        ):
            if target_kind == ControlRelationTargetKind.OFFICIAL_RULE:
                if not re.fullmatch(r"(IN|EX)-\d{2}", target_id):
                    raise ValueError("官方规则关系端必须使用既有 IN/EX 编号")
            elif target_kind in {
                ControlRelationTargetKind.PROTOCOL_CONTROL,
                ControlRelationTargetKind.CONTROL_CANDIDATE,
            }:
                _reject_forbidden_control_identity(target_id, field_name)
            elif target_kind == ControlRelationTargetKind.REQUIRED_PROCEDURE:
                _reject_forbidden_control_identity(target_id, field_name)
            elif target_kind == ControlRelationTargetKind.WORKFLOW_STAGE:
                _reject_forbidden_control_identity(target_id, field_name)
        if self.kind == CrossSourceRelationKind.DUPLICATE_STATEMENT:
            if self.shared_assessment_identity is None:
                raise ValueError("确认的重复表述必须提供共享评估身份")
        elif self.shared_assessment_identity is not None:
            raise ValueError("非重复表述关系不得共享评估身份")
        if self.kind == CrossSourceRelationKind.SUBSTANTIVE_CONFLICT:
            if self.shared_assessment_identity is not None:
                raise ValueError("实质冲突不得共享评估身份")
        return self


class ControlCrossSourceRelationDraft(Phase5ControlModel):
    """Provider-neutral relation proposal with one frozen external target.

    The provider chooses only the relation kind, one known external target and
    which side the current candidate occupies.  The candidate/control identity
    is injected by system hydration and can never be authored on this wire.
    """

    kind: CrossSourceRelationKind
    external_target_kind: ControlRelationTargetKind
    external_target_id: str = Field(min_length=1)
    candidate_side: Literal["left", "right"]
    affected_workflow_stage_id: str | None = Field(default=None, min_length=1)
    notes: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_target_shapes(self) -> "ControlCrossSourceRelationDraft":
        allowed_target_kinds = {
            ControlRelationTargetKind.OFFICIAL_RULE,
            ControlRelationTargetKind.REQUIRED_PROCEDURE,
            ControlRelationTargetKind.WORKFLOW_STAGE,
        }
        if self.external_target_kind not in allowed_target_kinds:
            raise ValueError(
                "provider 关系草稿只能引用已知官方规则、流程必做项或冻结流程节点"
            )
        if self.external_target_kind == ControlRelationTargetKind.OFFICIAL_RULE:
            if not re.fullmatch(r"(IN|EX)-\d{2}", self.external_target_id):
                raise ValueError("关系草稿官方目标必须使用既有 IN/EX 编号形态")
        else:
            _reject_forbidden_control_identity(
                self.external_target_id,
                "external_target_id",
            )
        return self


class ProtocolReviewControl(Phase5ControlModel):
    """正式发布的其他方案审核控制；与覆盖清单、候选处置分离。

    The flat ``obligations`` list remains only as a narrow 5.8a compatibility
    surface.  It is intentionally observable through
    :attr:`is_legacy_flat_compatibility`; the future publication gate must
    reject that shape for 5.8b publication and require
    ``obligation_expression`` instead.
    """

    protocol_control_id: str = Field(min_length=1)
    display_ordinal: int = Field(ge=1)
    protocol_version_id: str = Field(min_length=1)
    study_phase: StudyPhase
    title: str = Field(min_length=1)
    applicable_population: str = Field(min_length=1)
    trigger_condition: str | None = Field(default=None, min_length=1)
    # 5.8a compatibility surface.  New controls should use the explicit DNF
    # layers below; the old flat list remains accepted for already focused 5.8a
    # fixtures and is never treated as an exception layer.
    obligations: list[ControlObligationAtom] = Field(default_factory=list)
    obligation_combination: Literal["all", "any"] = "all"
    applicability_expression: ControlConditionDnf | None = None
    trigger_expression: ControlConditionDnf | None = None
    obligation_expression: ControlObligationDnf | None = None
    exception_expression: ControlExceptionDnf | None = None
    repeat_trigger_conditions: list[ControlRepeatTrigger] = Field(default_factory=list)
    control_time_constraint: TimeConstraint | None = None
    control_time_bindings: list[ControlTimeBinding] = Field(default_factory=list)
    review_node_bindings: list[ReviewNodeBinding] = Field(min_length=1)
    minimum_evidence: list[ControlMinimumEvidence] = Field(min_length=1)
    source_span_ids: list[str] = Field(min_length=1)
    source_structure_unit_ids: list[str] = Field(min_length=1)
    cross_source_relations: list[ControlCrossSourceRelation] = Field(
        default_factory=list
    )
    originating_candidate_id: str | None = Field(default=None, min_length=1)

    @model_serializer(mode="wrap")
    def serialize_time_bindings(self, handler):
        value = handler(self)
        if not self.control_time_bindings:
            value.pop("control_time_bindings", None)
        if not self.repeat_trigger_conditions:
            value.pop("repeat_trigger_conditions", None)
        return value

    @property
    def display_label(self) -> str:
        return protocol_control_display_label(self.display_ordinal)

    @property
    def is_legacy_flat_compatibility(self) -> bool:
        """Whether this control still relies on the accepted 5.8a flat list."""

        return self.obligation_expression is None

    @property
    def has_explicit_obligation_dnf(self) -> bool:
        """Whether the control is eligible for the explicit 5.8b gate path."""

        return self.obligation_expression is not None

    @model_validator(mode="after")
    def validate_published_control(self) -> "ProtocolReviewControl":
        validate_control_repeat_conditions(self)
        validate_control_time_bindings(self)
        _reject_forbidden_control_identity(
            self.protocol_control_id,
            "protocol_control_id",
        )
        if is_forbidden_protocol_control_code(self.display_label):
            raise ValueError("展示标签不得伪装为官方编号")
        if self.obligation_expression is None and not self.obligations:
            raise ValueError("正式控制必须包含非空义务 DNF 或兼容义务原子集")
        if self.obligation_expression is not None and self.obligations:
            expression_ids = [
                atom.obligation_id
                for group in self.obligation_expression.groups
                for atom in group.atoms
            ]
            flat_ids = [item.obligation_id for item in self.obligations]
            if expression_ids != flat_ids:
                raise ValueError("显式义务 DNF 与兼容义务原子集不得表达两套语义")
        obligation_ids = (
            [
                atom.obligation_id
                for group in self.obligation_expression.groups
                for atom in group.atoms
            ]
            if self.obligation_expression is not None
            else [item.obligation_id for item in self.obligations]
        )
        if len(obligation_ids) != len(set(obligation_ids)):
            raise ValueError("义务原子 ID 必须唯一")
        obligation_count = len(obligation_ids)
        if self.obligation_combination == LogicalOperator.ANY.value and obligation_count < 2:
            raise ValueError("ANY 义务组合至少需要两个义务原子")

        if self.obligation_expression is not None:
            for group in self.obligation_expression.groups:
                for atom in group.atoms:
                    _validate_atom_sources(
                        atom.source_span_ids,
                        atom.source_excerpts,
                        strict=True,
                        label="正式义务原子",
                    )

        stage_keys = [
            (binding.workflow_stage_id, binding.role.value)
            for binding in self.review_node_bindings
        ]
        if len(stage_keys) != len(set(stage_keys)):
            raise ValueError("同一审核节点不得重复绑定相同节点作用")

        evidence_keys = [item.evidence_key for item in self.minimum_evidence]
        if len(evidence_keys) != len(set(evidence_keys)):
            raise ValueError("最低证据键必须唯一")

        _require_sorted_unique(self.source_span_ids, "source_span_ids")
        _require_sorted_unique(
            self.source_structure_unit_ids,
            "source_structure_unit_ids",
        )

        if self.obligation_expression is not None:
            explicit_atom_spans = {
                span_id
                for group in self.obligation_expression.groups
                for atom in group.atoms
                for span_id in atom.source_span_ids
            }
            for expression in (
                self.applicability_expression,
                self.trigger_expression,
                self.exception_expression,
            ):
                if expression is not None:
                    explicit_atom_spans.update(
                        span_id
                        for group in expression.groups
                        for atom in group.atoms
                        for span_id in atom.source_span_ids
                    )
            if not explicit_atom_spans <= set(self.source_span_ids):
                raise ValueError("正式控制 source_span_ids 必须覆盖所有原子直接来源")

        relation_ids = [item.relation_id for item in self.cross_source_relations]
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("跨来源关系 ID 必须唯一")
        for relation in self.cross_source_relations:
            mentions_self = (
                relation.left_target_kind
                == ControlRelationTargetKind.PROTOCOL_CONTROL
                and relation.left_target_id == self.protocol_control_id
            ) or (
                relation.right_target_kind
                == ControlRelationTargetKind.PROTOCOL_CONTROL
                and relation.right_target_id == self.protocol_control_id
            )
            if not mentions_self:
                raise ValueError(
                    "跨来源关系必须至少一端指向本 protocol_control_id"
                )

        if self.originating_candidate_id is not None:
            _reject_forbidden_control_identity(
                self.originating_candidate_id,
                "originating_candidate_id",
            )
        return self


class PublishedProtocolControlCatalog(Phase5ControlModel):
    """正式发布控制目录：来源闭包与未解冲突门禁。"""

    catalog_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    protocol_document_sha256: str = Field(pattern=_SHA256)
    study_phase: StudyPhase
    coverage_manifest_id: str = Field(min_length=1)
    allowed_source_span_ids: list[str] = Field(min_length=1)
    controls: list[ProtocolReviewControl] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_catalog(self) -> "PublishedProtocolControlCatalog":
        _require_sorted_unique(
            self.allowed_source_span_ids,
            "allowed_source_span_ids",
        )
        control_ids = [item.protocol_control_id for item in self.controls]
        if len(control_ids) != len(set(control_ids)):
            raise ValueError("发布控制 ID 必须唯一")
        ordinals = [item.display_ordinal for item in self.controls]
        if len(ordinals) != len(set(ordinals)):
            raise ValueError("方案控制顺序标签必须唯一")
        if self.controls != sorted(
            self.controls, key=lambda item: item.display_ordinal
        ):
            raise ValueError("发布控制必须按 display_ordinal 升序排列")

        allowed = set(self.allowed_source_span_ids)
        unresolved_conflicts: list[str] = []
        for control in self.controls:
            if control.protocol_version_id != self.protocol_version_id:
                raise ValueError("发布控制必须绑定当前 protocol_version_id")
            if control.study_phase != self.study_phase:
                raise ValueError("发布控制期别必须与目录期别一致")
            outside = set(control.source_span_ids) - allowed
            if outside:
                raise ValueError(
                    "发布控制来源越界："
                    + ",".join(sorted(outside))
                )
            for relation in control.cross_source_relations:
                if relation.kind == CrossSourceRelationKind.SUBSTANTIVE_CONFLICT:
                    unresolved_conflicts.append(relation.relation_id)

        if unresolved_conflicts:
            raise ValueError(
                "未解决的实质冲突阻断发布控制目录："
                + ",".join(sorted(unresolved_conflicts))
            )
        return self


class KnownOfficialRuleTarget(Phase5ControlModel):
    """A frozen official IN/EX target exposed to a control Agent batch."""

    catalog_item_id: str = Field(min_length=1)
    official_code: str = Field(pattern=r"^(IN|EX)-\d{2}$")
    label: str = Field(min_length=1)
    position: int = Field(ge=0)
    source_span_ids: list[str] = Field(min_length=1)
    source_excerpts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_target(self) -> "KnownOfficialRuleTarget":
        _require_sorted_unique(self.source_span_ids, "官方目标 source_span_ids")
        if self.source_excerpts and len(self.source_excerpts) != len(
            self.source_span_ids
        ):
            raise ValueError("官方目标来源摘录必须与来源定位一一对应")
        if self.source_excerpts and not any(
            excerpt is not None for excerpt in self.source_excerpts
        ):
            raise ValueError("官方目标至少需要一段可核验的来源摘录")
        if any(
            excerpt is not None and not excerpt.strip()
            for excerpt in self.source_excerpts
        ):
            raise ValueError("官方目标来源摘录不得为空")
        return self


class KnownRequiredProcedureTarget(Phase5ControlModel):
    """A frozen required-procedure target exposed to a control Agent batch."""

    catalog_item_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    visit_instance: str = Field(min_length=1)
    review_stage: ReviewStage
    position: int = Field(ge=0)
    semantic_family: str | None = Field(default=None, min_length=1)
    covered_action_kinds: list[str] = Field(default_factory=list)
    source_span_ids: list[str] = Field(min_length=1)
    source_excerpts: list[str | None] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_target(self) -> "KnownRequiredProcedureTarget":
        _require_sorted_unique(self.covered_action_kinds, "流程目标覆盖动作")
        _require_sorted_unique(self.source_span_ids, "流程目标 source_span_ids")
        if self.source_excerpts and len(self.source_excerpts) != len(
            self.source_span_ids
        ):
            raise ValueError("流程目标来源摘录必须与来源定位一一对应")
        if self.source_excerpts and not any(
            excerpt is not None for excerpt in self.source_excerpts
        ):
            raise ValueError("流程目标至少需要一段可核验的来源摘录")
        if any(
            excerpt is not None and not excerpt.strip()
            for excerpt in self.source_excerpts
        ):
            raise ValueError("流程目标来源摘录不得为空")
        return self


class KnownWorkflowStageTarget(Phase5ControlModel):
    """A frozen selected-phase workflow stage exposed to a control Agent batch."""

    workflow_stage_id: str = Field(min_length=1)
    review_stage: ReviewStage
    display_name: str = Field(min_length=1)
    visit_instance: str | None = Field(default=None, min_length=1)
    visit_window: str | None = Field(default=None, min_length=1)


class ProtocolControlDispositionBatch(Phase5ControlModel):
    """Deterministic planner output for one bounded owned-unit batch.

    ``context_units`` are deliberately separate from ``owned_units``.  They
    may be repeated in neighboring batches as read-only context, but they can
    never appear in ``owned_structure_unit_ids`` for this batch's disposition.
    """

    batch_id: str = Field(min_length=1)
    coverage_manifest_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    study_phase: StudyPhase
    batch_number: int = Field(ge=1)
    batch_total: int = Field(ge=1)
    context_is_read_only: Literal[True] = True
    # Scheduling hint only.  It never changes source ordering, batch_number,
    # or batch_id; canonical identity remains source-derived.
    priority_rank: int = Field(default=0, ge=0)
    owned_units: list[ProtocolStructureUnit] = Field(min_length=1)
    context_units: list[ProtocolStructureUnit] = Field(default_factory=list)
    owned_structure_unit_ids: list[str] = Field(min_length=1)
    context_structure_unit_ids: list[str] = Field(default_factory=list)
    owned_source_span_ids: list[str] = Field(min_length=1)
    context_source_span_ids: list[str] = Field(default_factory=list)
    # Frozen structural evidence that these owned units occur before the
    # enrollment boundary within their visit. The Agent may not downgrade
    # them to post-treatment execution based on a broad chapter heading.
    pre_enrollment_structure_unit_ids: list[str] = Field(default_factory=list)
    # Frozen structural labels or section markers that provide context only.
    # They must never be promoted to a clinical rule, procedure, or candidate.
    structural_only_structure_unit_ids: list[str] = Field(default_factory=list)
    # Exact frozen visit where an owned known-procedure source unit is
    # executed. This is distinct from retrospective interval references
    # inside the source text and cannot be downgraded to a generic supplement.
    owned_visit_instance_by_structure_unit_id: dict[str, str] = Field(
        default_factory=dict
    )
    # Independent structured expectation used only by deterministic gates.
    # It is deliberately excluded from the Agent input to avoid answer leakage.
    owned_procedure_semantic_families_by_structure_unit_id: dict[
        str, list[str]
    ] = Field(default_factory=dict)
    # Frozen action predicates required by each owned unit. This is checked by
    # deterministic gates and is intentionally absent from Agent input.
    owned_required_action_kinds_by_structure_unit_id: dict[str, list[str]] = Field(
        default_factory=dict
    )
    # Frozen procedure targets whose workflow scope applies to each action-bearing
    # owned unit. This is gate-only metadata and is not exposed to the Agent.
    owned_required_procedure_target_ids_by_structure_unit_id: dict[
        str, list[str]
    ] = Field(default_factory=dict)
    known_official_targets: list[KnownOfficialRuleTarget] = Field(
        default_factory=list
    )
    known_procedure_targets: list[KnownRequiredProcedureTarget] = Field(
        default_factory=list
    )
    # Empty is retained only for narrow 5.8a/5.8b fixtures; publication gates
    # may require this frozen catalog for a phase-specific run.
    known_workflow_stage_targets: list[KnownWorkflowStageTarget] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_batch(self) -> "ProtocolControlDispositionBatch":
        if self.batch_number > self.batch_total:
            raise ValueError("处置批次序号不得大于批次总数")
        owned_ids = [unit.structure_unit_id for unit in self.owned_units]
        context_ids = [unit.structure_unit_id for unit in self.context_units]
        if len(owned_ids) != len(set(owned_ids)):
            raise ValueError("同一批次 owned 结构单元不得重复")
        if len(context_ids) != len(set(context_ids)):
            raise ValueError("同一批次 context 结构单元不得重复")
        if owned_ids != self.owned_structure_unit_ids:
            raise ValueError("owned_structure_unit_ids 必须与 owned_units 顺序和身份一致")
        if context_ids != self.context_structure_unit_ids:
            raise ValueError("context_structure_unit_ids 必须与 context_units 顺序和身份一致")
        if set(owned_ids) & set(context_ids):
            raise ValueError("同一批次的 owned/context 结构单元不得重叠")
        if not set(self.pre_enrollment_structure_unit_ids) <= set(owned_ids):
            raise ValueError("给药前结构单元必须属于本批 owned_units")
        if self.pre_enrollment_structure_unit_ids != [
            unit_id
            for unit_id in owned_ids
            if unit_id in set(self.pre_enrollment_structure_unit_ids)
        ]:
            raise ValueError("给药前结构单元必须按 owned_units 原文顺序排列且不得重复")
        if not set(self.structural_only_structure_unit_ids) <= set(owned_ids):
            raise ValueError("纯结构单元必须属于本批 owned_units")
        if self.structural_only_structure_unit_ids != [
            unit_id
            for unit_id in owned_ids
            if unit_id in set(self.structural_only_structure_unit_ids)
        ]:
            raise ValueError("纯结构单元必须按 owned_units 原文顺序排列且不得重复")
        visit_unit_ids = list(self.owned_visit_instance_by_structure_unit_id)
        if not set(visit_unit_ids) <= set(owned_ids):
            raise ValueError("执行访视归属只能引用本批 owned_units")
        if visit_unit_ids != [
            unit_id for unit_id in owned_ids if unit_id in set(visit_unit_ids)
        ]:
            raise ValueError("执行访视归属必须按 owned_units 原文顺序排列")
        known_visit_instances = {
            item.visit_instance
            for item in self.known_workflow_stage_targets
            if item.visit_instance is not None
        }
        unknown_visit_instances = sorted(
            set(self.owned_visit_instance_by_structure_unit_id.values())
            - known_visit_instances
        )
        if unknown_visit_instances:
            raise ValueError(
                "执行访视归属必须使用冻结工作流中的精确访视："
                + "、".join(unknown_visit_instances)
            )
        family_unit_ids = list(
            self.owned_procedure_semantic_families_by_structure_unit_id
        )
        if not set(family_unit_ids) <= set(owned_ids):
            raise ValueError("流程资料家族归属只能引用本批 owned_units")
        if family_unit_ids != [
            unit_id for unit_id in owned_ids if unit_id in set(family_unit_ids)
        ]:
            raise ValueError("流程资料家族归属必须按 owned_units 原文顺序排列")
        known_families = {
            item.semantic_family
            for item in self.known_procedure_targets
            if item.semantic_family is not None
        }
        for unit_id, families in (
            self.owned_procedure_semantic_families_by_structure_unit_id.items()
        ):
            _require_sorted_unique(families, f"{unit_id} 流程资料家族")
            if not set(families) <= known_families:
                raise ValueError("流程资料家族归属必须来自冻结流程目标")
        action_unit_ids = list(
            self.owned_required_action_kinds_by_structure_unit_id
        )
        if not set(action_unit_ids) <= set(owned_ids):
            raise ValueError("必需动作归属只能引用本批 owned_units")
        if action_unit_ids != [
            unit_id for unit_id in owned_ids if unit_id in set(action_unit_ids)
        ]:
            raise ValueError("必需动作归属必须按 owned_units 原文顺序排列")
        for unit_id, action_kinds in (
            self.owned_required_action_kinds_by_structure_unit_id.items()
        ):
            _require_sorted_unique(action_kinds, f"{unit_id} 必需动作")
        target_unit_ids = list(
            self.owned_required_procedure_target_ids_by_structure_unit_id
        )
        if not set(target_unit_ids) <= set(owned_ids):
            raise ValueError("必需流程目标归属只能引用本批 owned_units")
        if target_unit_ids != [
            unit_id for unit_id in owned_ids if unit_id in set(target_unit_ids)
        ]:
            raise ValueError("必需流程目标归属必须按 owned_units 原文顺序排列")
        known_procedure_ids = {
            item.catalog_item_id for item in self.known_procedure_targets
        }
        for unit_id, target_ids in (
            self.owned_required_procedure_target_ids_by_structure_unit_id.items()
        ):
            _require_sorted_unique(target_ids, f"{unit_id} 必需流程目标")
            if not set(target_ids) <= known_procedure_ids:
                raise ValueError("必需流程目标归属必须来自冻结流程目录")
        if any(unit.study_phase != self.study_phase for unit in (*self.owned_units, *self.context_units)):
            raise ValueError("批次结构单元期别必须与批次一致")
        expected_owned_spans = sorted(
            {
                span_id
                for unit in self.owned_units
                for span_id in unit.source_span_ids
            }
        )
        expected_context_spans = sorted(
            {
                span_id
                for unit in self.context_units
                for span_id in unit.source_span_ids
            }
        )
        if self.owned_source_span_ids != expected_owned_spans:
            raise ValueError("owned_source_span_ids 必须闭合到所有 owned 结构单元")
        if self.context_source_span_ids != expected_context_spans:
            raise ValueError("context_source_span_ids 必须闭合到所有 context 结构单元")
        _require_sorted_unique(self.owned_source_span_ids, "owned_source_span_ids")
        _require_sorted_unique(self.context_source_span_ids, "context_source_span_ids")
        official_positions = [item.position for item in self.known_official_targets]
        procedure_positions = [item.position for item in self.known_procedure_targets]
        if official_positions != sorted(official_positions):
            raise ValueError("官方已知目标必须按冻结目录位置排序")
        if procedure_positions != sorted(procedure_positions):
            raise ValueError("流程已知目标必须按冻结目录位置排序")
        workflow_stage_ids = [
            item.workflow_stage_id for item in self.known_workflow_stage_targets
        ]
        if len(workflow_stage_ids) != len(set(workflow_stage_ids)):
            raise ValueError("已知流程节点 workflow_stage_id 不得重复")
        workflow_stage_keys = [
            (item.review_stage.value, item.visit_instance)
            for item in self.known_workflow_stage_targets
        ]
        if len(workflow_stage_keys) != len(set(workflow_stage_keys)):
            raise ValueError("已知流程节点的 (审核阶段, 访视实例) 身份不得重复")
        if self.known_workflow_stage_targets:
            known_stage_keys = set(workflow_stage_keys)
            for target in self.known_procedure_targets:
                if (target.review_stage.value, target.visit_instance) not in known_stage_keys:
                    raise ValueError(
                        "流程必做目标无法与本批次已知流程节点的审核阶段和访视实例对应"
                    )
        return self

    @property
    def known_target_source_span_ids(self) -> list[str]:
        """Frozen catalog source closure, kept separate from owned unit spans."""

        return sorted(
            {
                span_id
                for target in (
                    *self.known_official_targets,
                    *self.known_procedure_targets,
                )
                for span_id in target.source_span_ids
            }
        )

    @property
    def all_context_source_span_ids(self) -> list[str]:
        """Read-only context span closure (never an owned disposition scope)."""

        return list(self.context_source_span_ids)



class ProtocolControlBatchPlan(Phase5ControlModel):
    """Complete deterministic plan; every manifest unit has exactly one owner.

    A batch may additionally carry same-protocol, same-phase read-only context
    that is outside the manifest.  Such context is prompt material only: it is
    never owned, disposed, or eligible as candidate evidence.
    """

    plan_id: str = Field(min_length=1)
    coverage_manifest_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    study_phase: StudyPhase
    max_owned_units_per_batch: int = Field(ge=1)
    context_radius: int = Field(ge=0)
    expected_structure_unit_ids: list[str] = Field(min_length=1)
    batches: list[ProtocolControlDispositionBatch] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_plan(self) -> "ProtocolControlBatchPlan":
        if any(not value.strip() for value in self.expected_structure_unit_ids):
            raise ValueError("expected_structure_unit_ids 不得包含空 ID")
        if len(self.expected_structure_unit_ids) != len(
            set(self.expected_structure_unit_ids)
        ):
            raise ValueError("expected_structure_unit_ids 不得重复")
        if any(
            batch.coverage_manifest_id != self.coverage_manifest_id
            or batch.protocol_version_id != self.protocol_version_id
            or batch.study_phase != self.study_phase
            for batch in self.batches
        ):
            raise ValueError("处置批次必须绑定同一覆盖清单、方案版本和期别")
        expected_total = len(self.batches)
        if any(batch.batch_total != expected_total for batch in self.batches):
            raise ValueError("处置批次 batch_total 必须等于计划批次数")
        numbers = [batch.batch_number for batch in self.batches]
        if numbers != list(range(1, expected_total + 1)):
            raise ValueError("处置批次必须按连续序号排列")
        owned_ids = [
            unit_id
            for batch in self.batches
            for unit_id in batch.owned_structure_unit_ids
        ]
        if len(owned_ids) != len(set(owned_ids)):
            raise ValueError("每个结构单元必须且只能归属一个处置批次")
        if set(owned_ids) != set(self.expected_structure_unit_ids):
            raise ValueError("处置批次未覆盖全部且仅覆盖清单结构单元")
        if any(
            len(batch.owned_units) > self.max_owned_units_per_batch
            for batch in self.batches
        ):
            raise ValueError("批次超过 max_owned_units_per_batch")
        return self
class ProtocolControlDiscoveryToDeepPlan(Phase5ControlModel):
    """System-owned bridge from coarse discovery to bounded deep batches."""

    plan_id: str = Field(min_length=1)
    discovery_plan_id: str = Field(min_length=1)
    coverage_manifest_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    protocol_document_sha256: str = Field(pattern=_SHA256)
    snapshot_id: str = Field(min_length=1)
    study_phase: StudyPhase
    manifest_structure_unit_count: int = Field(ge=1)
    manifest_structure_unit_ids_sha256: str = Field(pattern=_SHA256)
    expected_structure_unit_ids: list[str] = Field(min_length=1)
    discovery_decisions: list[ProtocolControlDiscoveryDecision] = Field(
        min_length=1
    )
    max_owned_units_per_batch: int = Field(ge=1)
    batches: list[ProtocolControlDispositionBatch] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_bridge(self) -> "ProtocolControlDiscoveryToDeepPlan":
        expected_ids = self.expected_structure_unit_ids
        expected_set = set(expected_ids)
        if any(not value.strip() for value in expected_ids):
            raise ValueError("深析计划 expected_structure_unit_ids 不得包含空 ID")
        if len(expected_ids) != len(expected_set):
            raise ValueError("深析计划 expected_structure_unit_ids 不得重复")
        if self.manifest_structure_unit_count != len(expected_ids):
            raise ValueError("深析计划结构单元总数与完整清单不一致")
        if (
            self.manifest_structure_unit_ids_sha256
            != stable_protocol_control_manifest_structure_unit_ids_sha256(
                expected_ids
            )
        ):
            raise ValueError("深析计划完整清单结构单元身份哈希不一致")
        decision_ids = [item.structure_unit_id for item in self.discovery_decisions]
        if decision_ids != expected_ids:
            raise ValueError("深析计划发现处置必须按原文恰好覆盖完整清单")
        decision_by_id = dict(
            zip(decision_ids, self.discovery_decisions, strict=True)
        )
        for decision in self.discovery_decisions:
            if not set(decision.required_context_structure_unit_ids) <= expected_set:
                raise ValueError("发现阶段所需上下文结构单元越出完整清单")
        deep_ids = [
            structure_unit_id
            for structure_unit_id in expected_ids
            if decision_by_id[structure_unit_id].disposition
            in {
                ProtocolControlDiscoveryDisposition.CANDIDATE,
                ProtocolControlDiscoveryDisposition.UNCERTAIN,
            }
        ]
        non_control_ids = {
            structure_unit_id
            for structure_unit_id, decision in decision_by_id.items()
            if decision.disposition
            == ProtocolControlDiscoveryDisposition.NON_CONTROL
        }
        for decision in self.discovery_decisions:
            if any(
                context_id in non_control_ids
                for context_id in decision.required_context_structure_unit_ids
            ):
                raise ValueError("深析上下文不得来自 non_control 发现处置")

        if any(
            batch.coverage_manifest_id != self.coverage_manifest_id
            or batch.protocol_version_id != self.protocol_version_id
            or batch.study_phase != self.study_phase
            for batch in self.batches
        ):
            raise ValueError("深析批次必须绑定同一清单、方案版本和期别")
        batch_total = len(self.batches)
        if any(batch.batch_total != batch_total for batch in self.batches):
            raise ValueError("深析批次 batch_total 必须等于深析批次数")
        numbers = [batch.batch_number for batch in self.batches]
        if numbers != list(range(1, batch_total + 1)):
            raise ValueError("深析批次必须按连续序号排列")
        if any(
            len(batch.owned_units) > self.max_owned_units_per_batch
            for batch in self.batches
        ):
            raise ValueError("深析批次超过 max_owned_units_per_batch")
        owned_ids = [
            structure_unit_id
            for batch in self.batches
            for structure_unit_id in batch.owned_structure_unit_ids
        ]
        if owned_ids != deep_ids:
            raise ValueError("深析批次必须且只能拥有 candidate/uncertain 单元")
        if len(owned_ids) != len(set(owned_ids)):
            raise ValueError("深析批次 owned 结构单元不得重复")
        for batch in self.batches:
            actual_context_ids = set(batch.context_structure_unit_ids)
            expected_context_ids = {
                context_id
                for owned_id in batch.owned_structure_unit_ids
                for context_id in decision_by_id[
                    owned_id
                ].required_context_structure_unit_ids
            } - set(batch.owned_structure_unit_ids)
            owned_tables = {
                unit.source_ref.rpartition(".r")[0]
                for unit in batch.owned_units
                if unit.table_context is not None
                and unit.source_ref.rpartition(".r")[1]
                and unit.source_ref.rpartition(".r")[2].isdigit()
            }
            table_context_ids = set()
            for unit in batch.context_units:
                table_ref, row_marker, row_text = unit.source_ref.rpartition(".r")
                if (
                    unit.structure_unit_id in expected_set
                    and unit.table_context is not None
                    and row_marker
                    and row_text.isdigit()
                    and int(row_text) == unit.table_context.row_index
                    and 0 <= unit.table_context.row_index < 5
                    and table_ref in owned_tables
                ):
                    table_context_ids.add(unit.structure_unit_id)
            if actual_context_ids & (non_control_ids - table_context_ids):
                raise ValueError("深析批次 context_units 不得包含非表格前置语境的 non_control 单元")
            if actual_context_ids != expected_context_ids | (actual_context_ids & table_context_ids):
                raise ValueError("深析批次上下文必须精确闭合到发现阶段声明")
        return self

    @property
    def deep_structure_unit_ids(self) -> tuple[str, ...]:
        return tuple(
            item.structure_unit_id
            for item in self.discovery_decisions
            if item.disposition
            in {
                ProtocolControlDiscoveryDisposition.CANDIDATE,
                ProtocolControlDiscoveryDisposition.UNCERTAIN,
            }
        )

    @property
    def non_deep_structure_unit_ids(self) -> tuple[str, ...]:
        return tuple(
            item.structure_unit_id
            for item in self.discovery_decisions
            if item.disposition
            in {
                ProtocolControlDiscoveryDisposition.CONTEXT_ONLY,
                ProtocolControlDiscoveryDisposition.NON_CONTROL,
            }
        )


ProtocolControlDeepPlan = ProtocolControlDiscoveryToDeepPlan




class ProtocolControlUnitDispositionDraft(Phase5ControlModel):
    """Provider-neutral disposition for one owned structure unit.

    Candidate references are positional indexes into the enclosing batch's
    ``candidate_drafts`` list.  They are deliberately not stable candidate
    identities; system hydration replaces them with plural stable IDs.
    """

    structure_unit_id: str = Field(min_length=1)
    disposition: StructureUnitDispositionKind
    linked_official_code: str | None = Field(default=None, min_length=1)
    linked_procedure_catalog_item_id: str | None = Field(default=None, min_length=1)
    linked_procedure_catalog_item_ids: list[str] = Field(default_factory=list)
    candidate_draft_indexes: list[int] = Field(default_factory=list)
    notes: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_draft_links(self) -> "ProtocolControlUnitDispositionDraft":
        _require_sorted_nonnegative_unique(
            self.candidate_draft_indexes,
            "candidate_draft_indexes",
        )
        _require_sorted_unique(
            self.linked_procedure_catalog_item_ids,
            "linked_procedure_catalog_item_ids",
        )
        if (
            self.linked_procedure_catalog_item_id is not None
            and self.linked_procedure_catalog_item_ids
        ):
            raise ValueError("流程必做处置不得同时使用单项目标和多项目标字段")
        procedure_target_ids = self.linked_procedure_catalog_item_ids or (
            [self.linked_procedure_catalog_item_id]
            if self.linked_procedure_catalog_item_id is not None
            else []
        )
        if self.linked_official_code is not None:
            if not re.fullmatch(r"(IN|EX)-\d{2}", self.linked_official_code):
                raise ValueError("结构单元仅可链接既有官方 IN/EX 父编号")
            if self.disposition != StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY:
                raise ValueError("仅官方入排处置可链接官方 IN/EX 编号")
        if procedure_target_ids:
            if self.disposition != StructureUnitDispositionKind.REQUIRED_PROCEDURE:
                raise ValueError("仅流程必做处置可链接必做项目录项")
        if (
            self.disposition == StructureUnitDispositionKind.REQUIRED_PROCEDURE
            and not procedure_target_ids
        ):
            raise ValueError("流程必做处置必须链接一个或多个访视级必做项目录项")
        if (
            self.candidate_draft_indexes
            and self.disposition
            != StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
        ):
            raise ValueError("非其他控制处置不得携带 candidate_draft_indexes")
        if (
            self.disposition == StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
            and not self.candidate_draft_indexes
        ):
            raise ValueError("其他控制候选处置至少引用一个 candidate_draft_index")
        return self


class ProtocolControlUnitDisposition(Phase5ControlModel):
    """System-hydrated disposition with plural stable candidate identities."""

    structure_unit_id: str = Field(min_length=1)
    disposition: StructureUnitDispositionKind
    linked_official_code: str | None = Field(default=None, min_length=1)
    linked_procedure_catalog_item_id: str | None = Field(default=None, min_length=1)
    linked_procedure_catalog_item_ids: list[str] = Field(default_factory=list)
    linked_control_candidate_ids: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_hydrated_links(self) -> "ProtocolControlUnitDisposition":
        _require_sorted_unique(
            self.linked_control_candidate_ids,
            "linked_control_candidate_ids",
        )
        _require_sorted_unique(
            self.linked_procedure_catalog_item_ids,
            "linked_procedure_catalog_item_ids",
        )
        if (
            self.linked_procedure_catalog_item_id is not None
            and self.linked_procedure_catalog_item_ids
        ):
            raise ValueError("流程必做处置不得同时使用单项目标和多项目标字段")
        procedure_target_ids = self.linked_procedure_catalog_item_ids or (
            [self.linked_procedure_catalog_item_id]
            if self.linked_procedure_catalog_item_id is not None
            else []
        )
        for candidate_id in self.linked_control_candidate_ids:
            _reject_forbidden_control_identity(
                candidate_id,
                "linked_control_candidate_ids",
            )
        if self.linked_official_code is not None:
            if not re.fullmatch(r"(IN|EX)-\d{2}", self.linked_official_code):
                raise ValueError("结构单元仅可链接既有官方 IN/EX 父编号")
            if self.disposition != StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY:
                raise ValueError("仅官方入排处置可链接官方 IN/EX 编号")
        if procedure_target_ids:
            if self.disposition != StructureUnitDispositionKind.REQUIRED_PROCEDURE:
                raise ValueError("仅流程必做处置可链接必做项目录项")
        if (
            self.disposition == StructureUnitDispositionKind.REQUIRED_PROCEDURE
            and not procedure_target_ids
        ):
            raise ValueError("流程必做处置必须链接一个或多个访视级必做项目录项")
        if (
            self.linked_control_candidate_ids
            and self.disposition
            != StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
        ):
            raise ValueError("非其他控制处置不得携带 linked_control_candidate_ids")
        if (
            self.disposition == StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
            and not self.linked_control_candidate_ids
        ):
            raise ValueError("其他控制候选处置至少绑定一个控制候选身份")
        return self


class ProtocolControlBatchDisposition(Phase5ControlModel):
    """Provider result envelope before stable IDs are system-hydrated.

    ``candidate_draft_indexes`` and ``candidate_drafts`` form one closed
    positional namespace.  The model must not emit candidate IDs.  Official
    and procedure links are checked against the planner batch's frozen target
    catalogs during ``hydrate_protocol_control_batch_disposition``.
    """

    batch_id: str = Field(min_length=1)
    coverage_manifest_id: str = Field(min_length=1)
    owned_structure_unit_ids: list[str] = Field(min_length=1)
    owned_source_span_ids: list[str] = Field(min_length=1)
    dispositions: list[ProtocolControlUnitDispositionDraft] = Field(min_length=1)
    candidate_drafts: list[ProtocolControlCandidateSemanticDraft] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_result_scope(self) -> "ProtocolControlBatchDisposition":
        _require_unique(
            self.owned_structure_unit_ids,
            "批次结果 owned_structure_unit_ids",
        )
        _require_sorted_unique(
            self.owned_source_span_ids,
            "批次结果 owned_source_span_ids",
        )
        disposition_ids = [item.structure_unit_id for item in self.dispositions]
        if len(disposition_ids) != len(set(disposition_ids)):
            raise ValueError("批次结果每个结构单元只能有一条处置")
        if set(disposition_ids) != set(self.owned_structure_unit_ids):
            raise ValueError("批次结果必须逐项处置全部 owned 结构单元")
        owned = set(self.owned_structure_unit_ids)
        disposition_by_unit = {
            item.structure_unit_id: item for item in self.dispositions
        }
        all_candidate_indexes = set(range(len(self.candidate_drafts)))
        referenced_candidate_indexes: set[int] = set()
        for disposition in self.dispositions:
            referenced_candidate_indexes.update(
                disposition.candidate_draft_indexes
            )
            unknown_indexes = (
                set(disposition.candidate_draft_indexes)
                - all_candidate_indexes
            )
            if unknown_indexes:
                raise ValueError(
                    "处置引用了不存在的 candidate_draft_index："
                    + ",".join(str(index) for index in sorted(unknown_indexes))
                )
        for candidate in self.candidate_drafts:
            if not set(candidate.source_structure_unit_ids) <= owned:
                raise ValueError("候选语义草稿不得引用批次外的 owned 结构单元")
            if not set(candidate.source_span_ids) <= set(self.owned_source_span_ids):
                raise ValueError("候选语义草稿来源不得越出批次来源闭包")
        if referenced_candidate_indexes != all_candidate_indexes:
            orphaned = sorted(all_candidate_indexes - referenced_candidate_indexes)
            raise ValueError(
                "candidate_drafts 存在未被任何结构单元引用的孤儿候选："
                + ",".join(str(index) for index in orphaned)
            )
        for candidate_index, candidate in enumerate(self.candidate_drafts):
            referring_units = [
                item
                for item in self.dispositions
                if candidate_index in item.candidate_draft_indexes
            ]
            if not referring_units:
                raise ValueError(
                    f"candidate_draft_index {candidate_index} 未被任何结构单元引用"
                )
            referring_unit_ids = {
                item.structure_unit_id for item in referring_units
            }
            candidate_unit_ids = set(candidate.source_structure_unit_ids)
            if referring_unit_ids != candidate_unit_ids:
                raise ValueError(
                    "候选草稿与结构单元处置之间必须保持双向精确闭包"
                )
            for source_unit_id in candidate.source_structure_unit_ids:
                source_disposition = disposition_by_unit[source_unit_id]
                if (
                    source_disposition.disposition
                    != StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
                    or candidate_index
                    not in source_disposition.candidate_draft_indexes
                ):
                    raise ValueError(
                        "候选语义草稿来源结构单元必须处置为 OTHER_CONTROL_CANDIDATE 并引用该草稿"
                    )
        return self


class ProtocolControlBatchDispositionHydrated(Phase5ControlModel):
    """System-hydrated batch result with final plural candidate links."""

    batch_id: str = Field(min_length=1)
    coverage_manifest_id: str = Field(min_length=1)
    owned_structure_unit_ids: list[str] = Field(min_length=1)
    owned_source_span_ids: list[str] = Field(min_length=1)
    dispositions: list[ProtocolControlUnitDisposition] = Field(min_length=1)
    candidates: list[ProtocolControlCandidate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_hydrated_result(self) -> "ProtocolControlBatchDispositionHydrated":
        _require_unique(
            self.owned_structure_unit_ids,
            "水合批次 owned_structure_unit_ids",
        )
        _require_sorted_unique(
            self.owned_source_span_ids,
            "水合批次 owned_source_span_ids",
        )
        disposition_ids = [item.structure_unit_id for item in self.dispositions]
        if len(disposition_ids) != len(set(disposition_ids)):
            raise ValueError("水合批次每个结构单元只能有一条处置")
        if set(disposition_ids) != set(self.owned_structure_unit_ids):
            raise ValueError("水合批次必须逐项处置全部 owned 结构单元")

        candidate_by_id = {
            candidate.control_candidate_id: candidate
            for candidate in self.candidates
        }
        if len(candidate_by_id) != len(self.candidates):
            raise ValueError("水合批次控制候选 ID 不得重复")
        owned = set(self.owned_structure_unit_ids)
        owned_spans = set(self.owned_source_span_ids)
        for candidate in self.candidates:
            if candidate.semantics is None:
                raise ValueError("水合批次候选必须携带系统水合语义")
            if not set(candidate.frozen_structure_unit_ids) <= owned:
                raise ValueError("水合候选不得引用批次外的 owned 结构单元")
            if not set(candidate.source_span_ids) <= owned_spans:
                raise ValueError("水合候选来源不得越出批次来源闭包")

        disposition_by_unit = {
            item.structure_unit_id: item for item in self.dispositions
        }
        referenced_candidate_ids = {
            candidate_id
            for disposition in self.dispositions
            for candidate_id in disposition.linked_control_candidate_ids
        }
        if referenced_candidate_ids != set(candidate_by_id):
            raise ValueError("水合批次候选必须全部被结构单元引用且不得引用未知候选")
        for candidate in self.candidates:
            referring_unit_ids = {
                item.structure_unit_id
                for item in self.dispositions
                if candidate.control_candidate_id
                in item.linked_control_candidate_ids
            }
            candidate_unit_ids = set(candidate.frozen_structure_unit_ids)
            if referring_unit_ids != candidate_unit_ids:
                raise ValueError(
                    "水合候选与结构单元处置之间必须保持双向精确闭包"
                )
            for source_unit_id in candidate.frozen_structure_unit_ids:
                source_disposition = disposition_by_unit[source_unit_id]
                if (
                    source_disposition.disposition
                    != StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
                    or candidate.control_candidate_id
                    not in source_disposition.linked_control_candidate_ids
                ):
                    raise ValueError(
                        "水合候选来源结构单元必须处置为 OTHER_CONTROL_CANDIDATE 并绑定该候选"
                    )
        return self


# Descriptive alias for callers that want to emphasize that this is the final
# post-hydration envelope rather than the provider-neutral batch result.
ProtocolControlFinalBatchDisposition = ProtocolControlBatchDispositionHydrated


# Short descriptive aliases keep the planner surface discoverable while
# preserving one canonical contract and one validation path.
ProtocolControlBatch = ProtocolControlDispositionBatch
ProtocolControlPlan = ProtocolControlBatchPlan


def _stable_digest(*parts: object) -> str:
    payload = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
def stable_protocol_control_manifest_structure_unit_ids_sha256(
    structure_unit_ids: Sequence[str],
) -> str:
    """Hash the ordered full-manifest identity at the system plan boundary."""

    values = list(structure_unit_ids)
    _require_unique(values, "完整清单结构单元 ID")
    payload = json.dumps(
        values,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stable_protocol_control_discovery_batch_id(
    coverage_manifest_id: str,
    batch_number: int,
    target_structure_unit_ids: Sequence[str],
) -> str:
    """Return a system-owned identity for one discovery chunk."""

    return "pcd-" + _stable_digest(
        coverage_manifest_id,
        batch_number,
        tuple(target_structure_unit_ids),
    )




def stable_protocol_control_batch_id(
    coverage_manifest_id: str,
    batch_number: int,
    owned_structure_unit_ids: Sequence[str],
) -> str:
    """Return an ID derived only from frozen system inputs, never model text."""

    return "pcb-" + _stable_digest(
        coverage_manifest_id,
        batch_number,
        tuple(owned_structure_unit_ids),
    )


def stable_protocol_control_candidate_id(
    coverage_manifest_id: str,
    batch_id: str,
    source_structure_unit_ids: Sequence[str],
    semantic_fingerprint: str = "",
    candidate_ordinal: int = 0,
) -> str:
    """Return a system-assigned candidate identity for hydration.

    ``candidate_ordinal`` is system-assigned when one batch yields multiple
    candidates with the same owned source closure; it is never read from a
    provider-provided candidate ID.
    """

    if candidate_ordinal < 0:
        raise ValueError("候选序号必须非负")

    return "pcc-" + _stable_digest(
        coverage_manifest_id,
        batch_id,
        tuple(sorted(source_structure_unit_ids)),
        semantic_fingerprint,
        candidate_ordinal,
    )


def stable_protocol_control_evidence_id(
    control_candidate_id: str,
    evidence_index: int,
) -> str:
    """Return a system-owned minimum-evidence identity for hydration."""

    if evidence_index < 0:
        raise ValueError("最低证据序号必须非负")
    return "pce-" + _stable_digest(control_candidate_id, "evidence", evidence_index)


def stable_protocol_control_relation_id(
    control_candidate_id: str,
    relation_index: int,
) -> str:
    """Return a system-owned cross-source relation identity for hydration."""

    if relation_index < 0:
        raise ValueError("跨来源关系序号必须非负")
    return "pcr-" + _stable_digest(control_candidate_id, "relation", relation_index)


def stable_protocol_control_trigger_branch_id(
    control_candidate_id: str,
    branch_ordinal: int,
) -> str:
    """Derive a trigger-branch identity from candidate identity and branch order.

    Identities are system-owned.  Providers may only reference branch ordinals;
    hydration converts ordinals into these stable IDs so exception/obligation
    scopes cannot invent or float free-form branch handles.
    """

    if not control_candidate_id.strip() or branch_ordinal < 0:
        raise ValueError("触发分支身份输入无效")
    return "pct-" + _stable_digest(
        control_candidate_id,
        "trigger",
        branch_ordinal,
    )


def stable_protocol_control_obligation_group_id(
    control_candidate_id: str,
    group_ordinal: int,
) -> str:
    """Derive a stable obligation-group identity for conditional activation."""

    if not control_candidate_id.strip() or group_ordinal < 0:
        raise ValueError("义务组身份输入无效")
    return "pog-" + _stable_digest(
        control_candidate_id,
        "obligation_group",
        group_ordinal,
    )


def stable_protocol_control_exception_group_id(
    control_candidate_id: str,
    group_ordinal: int,
) -> str:
    """Derive a stable exception-group identity for obligation activation links."""

    if not control_candidate_id.strip() or group_ordinal < 0:
        raise ValueError("例外组身份输入无效")
    return "peg-" + _stable_digest(
        control_candidate_id,
        "exception_group",
        group_ordinal,
    )


def stable_protocol_control_atom_id(
    control_candidate_id: str,
    layer: Literal["applicability", "trigger", "obligation", "exception", "repeat_trigger"],
    group_index: int,
    atom_index: int,
    *, repeat_condition_id: str | None = None,
) -> str:
    """Return a system-owned atom identity scoped to one hydrated candidate."""

    if group_index < 0 or atom_index < 0:
        raise ValueError("DNF group/atom index 必须非负")
    if (layer == "repeat_trigger") != (repeat_condition_id is not None):
        raise ValueError("复查触发原子须携带独立条件归属，不能与正式入排层混用")
    if repeat_condition_id is not None:
        if not repeat_condition_id.strip():
            raise ValueError("复查条件身份不得为空白")
        return "pca-" + _stable_digest(control_candidate_id, layer, repeat_condition_id, group_index, atom_index)
    return "pca-" + _stable_digest(
        control_candidate_id,
        layer,
        group_index,
        atom_index,
    )


def hydrate_protocol_control_candidate_semantics(
    draft: ProtocolControlCandidateSemanticDraft,
    *,
    control_candidate_id: str,
) -> ProtocolControlCandidateSemantics:
    """Inject system-owned IDs into a provider-neutral semantic draft.

    The function accepts no provider identity fields.  It copies only typed
    values and source closure from the draft, then derives every condition and
    obligation atom identity from the system candidate ID and DNF location.
    """

    _reject_forbidden_control_identity(
        control_candidate_id,
        "control_candidate_id",
    )

    def condition_dnf(
        value: ControlConditionDnfDraft | None,
        *,
        layer: Literal["applicability", "trigger", "repeat_trigger"],
        repeat_condition_id: str | None = None,
    ) -> ControlConditionDnf | None:
        if value is None:
            return None
        groups: list[ControlConditionGroup] = []
        for group_index, group in enumerate(value.groups):
            if group.waives_trigger_branch_indexes:
                raise ValueError(
                    f"{layer} DNF 不得携带例外触发分支序位"
                )
            if group.activates_obligation_group_indexes:
                raise ValueError(
                    f"{layer} DNF 不得携带例外激活义务组序位"
                )
            atoms = [
                ControlConditionAtom(
                    condition_atom_id=stable_protocol_control_atom_id(
                        control_candidate_id,
                        layer,
                        group_index,
                        atom_index,
                        repeat_condition_id=repeat_condition_id,
                    ),
                    statement=atom.statement,
                    evaluation=atom.evaluation,
                    source_span_ids=list(atom.source_span_ids),
                    source_excerpts=list(atom.source_excerpts),
                    time_constraint=atom.time_constraint,
                    requires_professional_judgment=atom.requires_professional_judgment,
                )
                for atom_index, atom in enumerate(group.atoms)
            ]
            trigger_branch_id = (
                stable_protocol_control_trigger_branch_id(
                    control_candidate_id,
                    group_index,
                )
                if layer == "trigger"
                else None
            )
            groups.append(
                ControlConditionGroup(
                    atoms=atoms,
                    trigger_branch_id=trigger_branch_id,
                )
            )
        return ControlConditionDnf(groups=groups)

    trigger_expression = condition_dnf(
        draft.trigger_expression,
        layer="trigger",
    )
    trigger_branch_ids = [
        group.trigger_branch_id
        for group in (trigger_expression.groups if trigger_expression else ())
        if group.trigger_branch_id is not None
    ]

    def resolve_branch_ids(indexes: Sequence[int], *, label: str) -> list[str]:
        if not indexes:
            return []
        if not trigger_branch_ids:
            raise ValueError(f"无触发分支时不得声明{label}")
        resolved: list[str] = []
        for index in indexes:
            if index >= len(trigger_branch_ids):
                raise ValueError(f"{label}序位越出触发 DNF 范围")
            resolved.append(trigger_branch_ids[index])
        return sorted(set(resolved))

    obligation_group_ids = [
        stable_protocol_control_obligation_group_id(control_candidate_id, index)
        for index in range(len(draft.obligation_expression.groups))
    ]
    activated_by: dict[str, list[str]] = {
        group_id: [] for group_id in obligation_group_ids
    }

    exception_groups: list[ControlExceptionGroup] | None = None
    if draft.exception_expression is not None:
        exception_groups = []
        for group_index, group in enumerate(draft.exception_expression.groups):
            if group.activates_obligation_group_indexes and any(
                atom.time_constraint is not None for atom in group.atoms
            ):
                raise ValueError(
                    "激活替代义务的例外条件原子不得携带替代时间窗；"
                    "时间窗必须写在被激活的义务组上"
                )
            atoms = [
                ControlConditionAtom(
                    condition_atom_id=stable_protocol_control_atom_id(
                        control_candidate_id,
                        "exception",
                        group_index,
                        atom_index,
                    ),
                    statement=atom.statement,
                    evaluation=atom.evaluation,
                    source_span_ids=list(atom.source_span_ids),
                    source_excerpts=list(atom.source_excerpts),
                    time_constraint=atom.time_constraint,
                    requires_professional_judgment=atom.requires_professional_judgment,
                )
                for atom_index, atom in enumerate(group.atoms)
            ]
            waives = resolve_branch_ids(
                group.waives_trigger_branch_indexes,
                label="例外触发分支",
            )
            if trigger_branch_ids and not waives:
                raise ValueError(
                    "存在触发 DNF 时每个例外路径必须声明可作用的触发分支"
                )
            exception_group_id = stable_protocol_control_exception_group_id(
                control_candidate_id,
                group_index,
            )
            activates: list[str] = []
            for index in group.activates_obligation_group_indexes:
                if index >= len(obligation_group_ids):
                    raise ValueError("例外激活义务组序位越出义务 DNF 范围")
                obligation_group_id = obligation_group_ids[index]
                activates.append(obligation_group_id)
                activated_by[obligation_group_id].append(exception_group_id)
            exception_groups.append(
                ControlExceptionGroup(
                    atoms=atoms,
                    exception_group_id=exception_group_id,
                    waives_trigger_branch_ids=waives,
                    activates_obligation_group_ids=sorted(set(activates)),
                )
            )

    obligation_groups: list[ControlObligationGroup] = []
    for group_index, group in enumerate(draft.obligation_expression.groups):
        atoms = [
            ControlObligationAtom(
                obligation_id=stable_protocol_control_atom_id(
                    control_candidate_id,
                    "obligation",
                    group_index,
                    atom_index,
                ),
                kind=atom.kind,
                evaluation=atom.evaluation,
                statement=atom.statement,
                time_constraint=atom.time_constraint,
                prospective_period=atom.prospective_period,
                continuing_obligation=atom.continuing_obligation,
                modality=atom.modality,
                temporal_scope=atom.temporal_scope,
                source_span_ids=list(atom.source_span_ids),
                source_excerpts=list(atom.source_excerpts),
                requires_professional_judgment=atom.requires_professional_judgment,
            )
            for atom_index, atom in enumerate(group.atoms)
        ]
        obligation_group_id = obligation_group_ids[group_index]
        obligation_groups.append(
            ControlObligationGroup(
                atoms=atoms,
                obligation_group_id=obligation_group_id,
                applies_to_trigger_branch_ids=resolve_branch_ids(
                    group.applies_to_trigger_branch_indexes,
                    label="义务触发分支",
                ),
                activated_by_exception_group_ids=sorted(
                    set(activated_by[obligation_group_id])
                ),
            )
        )

    hydrated_evidence = [
        ControlMinimumEvidence(
            evidence_key=stable_protocol_control_evidence_id(
                control_candidate_id,
                evidence_index,
            ),
            fact_type=item.fact_type,
            description=item.description,
            due_stage=item.due_stage,
            required_source_types=list(item.required_source_types),
            workflow_stage_ids=list(item.workflow_stage_ids),
            source_policy=item.source_policy,
            atom_refs=list(item.atom_refs),
        )
        for evidence_index, item in enumerate(draft.minimum_evidence)
    ]
    hydrated_relations: list[ControlCrossSourceRelation] = []
    for relation_index, item in enumerate(draft.cross_source_relations):
        candidate_target = (
            ControlRelationTargetKind.CONTROL_CANDIDATE,
            control_candidate_id,
        )
        external_target = (
            item.external_target_kind,
            item.external_target_id,
        )
        left_target_kind, left_target_id, right_target_kind, right_target_id = (
            (*candidate_target, *external_target)
            if item.candidate_side == "left"
            else (*external_target, *candidate_target)
        )
        hydrated_relations.append(
            ControlCrossSourceRelation(
                relation_id=stable_protocol_control_relation_id(
                    control_candidate_id,
                    relation_index,
                ),
                kind=item.kind,
                left_target_kind=left_target_kind,
                left_target_id=left_target_id,
                right_target_kind=right_target_kind,
                right_target_id=right_target_id,
                affected_workflow_stage_id=item.affected_workflow_stage_id,
                shared_assessment_identity=(
                    "pca-"
                    + _stable_digest(
                        control_candidate_id,
                        "shared",
                        relation_index,
                    )
                    if item.kind == CrossSourceRelationKind.DUPLICATE_STATEMENT
                    else None
                ),
                notes=item.notes,
            )
        )

    return ProtocolControlCandidateSemantics(
        title=draft.title,
        applicable_population=draft.applicable_population,
        control_candidate_id=control_candidate_id,
        applicability_expression=condition_dnf(
            draft.applicability_expression,
            layer="applicability",
        ),
        trigger_expression=trigger_expression,
        repeat_trigger_conditions=[ControlRepeatTrigger(
            condition_id=item.condition_id, expression=expression,
            predicate_evidence_roles=resolve_repeat_evidence_roles(item.evidence_roles, [
                [atom.condition_atom_id for atom in group.atoms] for group in expression.groups
            ]),
        ) for item in draft.repeat_trigger_conditions for expression in (
            condition_dnf(item.expression, layer="repeat_trigger", repeat_condition_id=item.condition_id),
        )],
        obligation_expression=ControlObligationDnf(groups=obligation_groups),
        exception_expression=(
            ControlExceptionDnf(groups=exception_groups)
            if exception_groups is not None
            else None
        ),
        review_node_bindings=list(draft.review_node_bindings),
        minimum_evidence=hydrated_evidence,
        source_structure_unit_ids=list(draft.source_structure_unit_ids),
        source_span_ids=list(draft.source_span_ids),
        cross_source_relations=hydrated_relations,
    )


def hydrate_protocol_control_batch_disposition(
    batch: ProtocolControlDispositionBatch,
    result: ProtocolControlBatchDisposition,
) -> ProtocolControlBatchDispositionHydrated:
    """Hydrate provider indexes into system-owned candidate/control identities.

    Candidate IDs are derived from the frozen batch, source-unit closure and a
    system canonical semantic fingerprint.  Provider list order is not used
    for identity except as a deterministic tie-breaker for byte-identical
    drafts.  Relation targets are checked against the known targets carried by
    this batch; cross-batch candidate/control alignment is intentionally out of
    scope and must be performed later by a deterministic system step.
    """

    if result.batch_id != batch.batch_id:
        raise ValueError("批次结果 batch_id 与规划批次不一致")
    if result.coverage_manifest_id != batch.coverage_manifest_id:
        raise ValueError("批次结果 coverage_manifest_id 与规划批次不一致")
    if result.owned_structure_unit_ids != batch.owned_structure_unit_ids:
        raise ValueError("批次结果 owned 结构单元必须与规划批次一致")
    if result.owned_source_span_ids != batch.owned_source_span_ids:
        raise ValueError("批次结果 owned 来源闭包必须与规划批次一致")

    known_official_codes = {
        target.official_code for target in batch.known_official_targets
    }
    known_procedure_ids = {
        target.catalog_item_id for target in batch.known_procedure_targets
    }
    known_workflow_stage_ids = {
        target.workflow_stage_id for target in batch.known_workflow_stage_targets
    }
    for disposition in result.dispositions:
        if (
            disposition.linked_official_code is not None
            and disposition.linked_official_code not in known_official_codes
        ):
            raise ValueError(
                "provider 处置引用了本批次未知的官方规则身份："
                + disposition.linked_official_code
            )
        procedure_target_ids = disposition.linked_procedure_catalog_item_ids or (
            [disposition.linked_procedure_catalog_item_id]
            if disposition.linked_procedure_catalog_item_id is not None
            else []
        )
        unknown_procedure_ids = sorted(
            set(procedure_target_ids) - known_procedure_ids
        )
        if unknown_procedure_ids:
            raise ValueError(
                "provider 处置引用了本批次未知的流程必做身份："
                + ",".join(unknown_procedure_ids)
            )
    for candidate in result.candidate_drafts:
        for relation in candidate.cross_source_relations:
            if relation.external_target_kind == ControlRelationTargetKind.OFFICIAL_RULE:
                if relation.external_target_id not in known_official_codes:
                    raise ValueError(
                        "provider 关系草稿引用了本批次未知的官方规则身份："
                        + relation.external_target_id
                    )
            elif relation.external_target_kind == ControlRelationTargetKind.REQUIRED_PROCEDURE:
                if relation.external_target_id not in known_procedure_ids:
                    raise ValueError(
                        "provider 关系草稿引用了本批次未知的流程必做身份："
                        + relation.external_target_id
                    )
            elif relation.external_target_kind == ControlRelationTargetKind.WORKFLOW_STAGE:
                if relation.external_target_id not in known_workflow_stage_ids:
                    raise ValueError(
                        "provider 关系草稿引用了本批次未知的流程节点："
                        + relation.external_target_id
                    )
            else:
                # The draft model rejects this earlier; keep the boundary
                # explicit here so direct model construction cannot bypass
                # the batch-context restriction.
                raise ValueError(
                    "provider 关系草稿只能引用本批次已知官方规则、流程必做项或冻结流程节点"
                )

    def semantic_fingerprint(
        candidate: ProtocolControlCandidateSemanticDraft,
    ) -> str:
        return _stable_digest(candidate.model_dump(mode="json"))

    ordered_candidates = sorted(
        enumerate(result.candidate_drafts),
        key=lambda item: (
            tuple(item[1].source_structure_unit_ids),
            semantic_fingerprint(item[1]),
            item[0],
        ),
    )
    candidate_ids_by_draft_index: dict[int, str] = {}
    candidate_records: list[ProtocolControlCandidate] = []
    duplicate_ordinals: dict[tuple[tuple[str, ...], str], int] = {}
    for draft_index, draft in ordered_candidates:
        fingerprint = semantic_fingerprint(draft)
        source_key = (tuple(draft.source_structure_unit_ids), fingerprint)
        ordinal = duplicate_ordinals.get(source_key, 0)
        duplicate_ordinals[source_key] = ordinal + 1
        candidate_id = stable_protocol_control_candidate_id(
            batch.coverage_manifest_id,
            batch.batch_id,
            draft.source_structure_unit_ids,
            fingerprint,
            ordinal,
        )
        candidate_ids_by_draft_index[draft_index] = candidate_id
        semantics = hydrate_protocol_control_candidate_semantics(
            draft,
            control_candidate_id=candidate_id,
        )
        candidate_records.append(
            ProtocolControlCandidate(
                control_candidate_id=candidate_id,
                protocol_version_id=batch.protocol_version_id,
                study_phase=batch.study_phase,
                frozen_structure_unit_ids=list(draft.source_structure_unit_ids),
                title=draft.title,
                applicable_population=draft.applicable_population,
                source_span_ids=list(draft.source_span_ids),
                semantics=semantics,
            )
        )

    hydrated_dispositions = [
        ProtocolControlUnitDisposition(
            structure_unit_id=disposition.structure_unit_id,
            disposition=disposition.disposition,
            linked_official_code=disposition.linked_official_code,
            linked_procedure_catalog_item_id=(
                disposition.linked_procedure_catalog_item_id
            ),
            linked_procedure_catalog_item_ids=list(
                disposition.linked_procedure_catalog_item_ids
            ),
            linked_control_candidate_ids=sorted(
                candidate_ids_by_draft_index[index]
                for index in disposition.candidate_draft_indexes
            ),
            notes=disposition.notes,
        )
        for disposition in result.dispositions
    ]
    return ProtocolControlBatchDispositionHydrated(
        batch_id=result.batch_id,
        coverage_manifest_id=result.coverage_manifest_id,
        owned_structure_unit_ids=list(result.owned_structure_unit_ids),
        owned_source_span_ids=list(result.owned_source_span_ids),
        dispositions=hydrated_dispositions,
        candidates=candidate_records,
    )


# The semantic draft classes are declared before the target/relation/evidence
# contracts they reference so the file remains readable by layer.  Resolve the
# annotations once all Phase 5 contracts are defined.
ProtocolControlCandidateSemanticDraft.model_rebuild()
ProtocolControlCandidateSemantics.model_rebuild()
