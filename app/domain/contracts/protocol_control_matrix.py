"""Machine-readable full-protocol control comparison matrix contracts.

The matrix is an audit baseline for a selected protocol phase.  It is kept
separate from the publication contracts in :mod:`protocol_controls`: a row
may point at an official IN/EX rule, a required-procedure catalogue item, or a
published ``ProtocolReviewControl``; pending formalization it may instead
carry an explicitly prefixed source candidate identity.  It never creates or
replaces any formal identity.

This module deliberately contains no document or project paths and no model
calls.  Exact source closure is checked by the protocol-level validator after
the matrix is joined to a frozen ``ProtocolSectionCoverageManifest``.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Literal

from pydantic import AliasChoices, ConfigDict, Field, model_validator

from .common import ContractModel
from .enums import (
    AnchorType,
    PhaseScope,
    ReviewStage,
    StableEnum,
    StudyPhase,
    TimeDirection,
)
from .protocol_controls import (
    ControlObligationKind,
    ControlObligationModality,
    ControlTemporalScopeKind,
    CrossSourceRelationKind,
    ProtocolReviewControl,
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    ReviewNodeRole,
    StructureUnitDispositionKind,
)
from .rules import TimeConstraint, TimeUnit

__all__ = [
    "CONTROL_MATRIX_CONTRACT_VERSION",
    "ControlMatrixSourceKind",
    "MatrixCrossSourceRelation",
    "MatrixDnf",
    "MatrixDnfGroup",
    "MatrixEvidence",
    "MatrixPhaseDisposition",
    "MatrixReviewNode",
    "MatrixSourceAnchor",
    "MatrixSourceKind",
    "MatrixTimeAnchor",
    "MatrixConditionAtom",
    "MatrixObligation",
    "MatrixObligationKind",
    "ProtocolControlMatrix",
    "ProtocolControlMatrixError",
    "ProtocolControlMatrixReport",
    "ProtocolControlMatrixRow",
    "ProtocolControlMatrixSourceKind",
    "ProtocolControlMatrixValidationReport",
    "build_protocol_control_matrix_json",
    "check_protocol_control_matrix",
    "render_protocol_control_matrix_markdown",
    "stable_protocol_control_matrix_anchor_id",
    "stable_protocol_control_matrix_trigger_branch_id",
    "stable_protocol_control_matrix_row_id",
    "validate_protocol_control_matrix",
    "validate_protocol_control_matrix_serializations",
]


CONTROL_MATRIX_CONTRACT_VERSION = "phase5/control-matrix/v5"
_SHA256 = r"^[0-9a-f]{64}$"
_OFFICIAL_PARENT = re.compile(r"^(?:IN|EX)-\d{2}$")
_OFFICIAL_CHILD = re.compile(
    r"^(?:IN|EX)-\d{2}(?:[.\-/][A-Za-z0-9]+)+$"
)
_RESERVED_ID = re.compile(r"^(?:IN|EX|REQ|CTRL)[-_ ]?\d{1,4}$", re.IGNORECASE)
_CANDIDATE_ID = re.compile(
    r"^candidate[-_:][A-Za-z0-9][A-Za-z0-9._:/-]*$",
    re.IGNORECASE,
)
_GENERIC_TITLE_TOKEN = r"(?:官方|入选|排除|标准|条件|条款|规则|资格|要求|入排)"
_OBLIGATION_PLACEHOLDERS = frozenset(
    {
        "无",
        "无要求",
        "无额外要求",
        "无特殊要求",
        "不适用",
        "不涉及",
        "暂无",
        "暂无要求",
        "na",
        "n/a",
        "none",
        "notapplicable",
    }
)
_EVIDENCE_PLACEHOLDER_FACT_TYPES = frozenset(
    {
        "方案官方条件",
        "方案要求",
        "入排条件",
        "官方条件",
        "方案条件",
        "官方入排条件",
        "核对结果",
        "方案规定",
    }
)
_OBJECTIVE_EVIDENCE_CUES = (
    "实验室",
    "检验",
    "化验",
    "影像",
    "影像学",
    "心电图",
    "妊娠",
    "量表",
    "评分",
    "检查报告",
    "检测结果",
)
_STAGE_SOURCE_CUES = {
    ReviewStage.PRE_SCREENING: ("预筛选", "筛选前"),
    ReviewStage.SCREENING: ("筛选",),
    ReviewStage.RUN_IN: ("导入期", "导入"),
    ReviewStage.BASELINE: ("基线",),
}
_EXCEPTION_BROAD_SCOPE_CUES = (
    "全部",
    "所有",
    "任一",
    "任意",
    "任何",
    "各项",
    "各个",
    "每一",
)


class ProtocolControlMatrixSourceKind(StableEnum):
    """The three first-class source families represented by the matrix."""

    OFFICIAL_ELIGIBILITY = "official_eligibility"
    REQUIRED_PROCEDURE = "required_procedure"
    OTHER_SECTION_CONTROL = "other_section_control"


ControlMatrixSourceKind = ProtocolControlMatrixSourceKind
MatrixSourceKind = ProtocolControlMatrixSourceKind
MatrixObligationKind = ControlObligationKind


class MatrixPhaseDisposition(StableEnum):
    """Phase resolution retained on every matrix row.

    ``opposite_phase_applicable`` and ``unresolved`` are retained so an audit
    draft can show why it is not publishable.  The strict validator rejects
    both; it never silently projects them into the selected phase.
    """

    SELECTED_PHASE_APPLICABLE = "selected_phase_applicable"
    OPPOSITE_PHASE_APPLICABLE = "opposite_phase_applicable"
    CROSS_PHASE_SHARED = "cross_phase_shared"
    UNRESOLVED = "unresolved"


_SOURCE_KIND_ZH = {
    ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY: "官方入排条件",
    ProtocolControlMatrixSourceKind.REQUIRED_PROCEDURE: "流程必做项",
    ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL: "其他章节控制",
}
_PHASE_DISPOSITION_ZH = {
    MatrixPhaseDisposition.SELECTED_PHASE_APPLICABLE: "选定期别适用",
    MatrixPhaseDisposition.OPPOSITE_PHASE_APPLICABLE: "对侧期别适用",
    MatrixPhaseDisposition.CROSS_PHASE_SHARED: "跨期共享",
    MatrixPhaseDisposition.UNRESOLVED: "期别未决",
}
_PHASE_DISPOSITION_VISIBLE_ZH = {
    MatrixPhaseDisposition.SELECTED_PHASE_APPLICABLE: "本项目适用",
    MatrixPhaseDisposition.OPPOSITE_PHASE_APPLICABLE: "对侧期别不适用（禁止发布）",
    MatrixPhaseDisposition.CROSS_PHASE_SHARED: "本项目适用",
    MatrixPhaseDisposition.UNRESOLVED: "期别未决（禁止发布）",
}
_STUDY_PHASE_ZH = {
    StudyPhase.PHASE_II: "II期",
    StudyPhase.PHASE_III: "III期",
    StudyPhase.SEAMLESS_II_III: "II/III无缝期",
    StudyPhase.OTHER: "未确认期别",
}
_REVIEW_STAGE_ZH = {
    ReviewStage.PRE_SCREENING: "预筛选",
    ReviewStage.SCREENING: "筛选",
    ReviewStage.RUN_IN: "导入期",
    ReviewStage.BASELINE: "基线",
}
_REVIEW_ROLE_ZH = {
    ReviewNodeRole.EARLY_ATTENTION: "提前关注",
    ReviewNodeRole.DECIDE_AT_NODE: "本节点判定",
    ReviewNodeRole.LATER_NODE_REVIEW: "后续节点复核",
}
_OBLIGATION_KIND_ZH = {
    ControlObligationKind.COMPLETE_OR_VERIFY: "完成/核对",
    ControlObligationKind.COMPLETE_BEFORE_ANCHOR: "节点前完成",
    ControlObligationKind.SCHEDULE_OR_VERIFY_VISIT: "访视安排/核对",
    ControlObligationKind.VERIFY_RESULT_VALIDITY: "结果有效期核对",
    ControlObligationKind.SELECT_BASELINE_VALUE: "基线值选取",
    ControlObligationKind.REACH_CONDITION: "达到条件",
    ControlObligationKind.PROHIBIT_EVENT: "禁止事件",
    ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE: "禁止药物/治疗暴露",
    ControlObligationKind.MUST_RECORD: "必须记录",
    ControlObligationKind.MUST_PROFESSIONAL_ASSESSMENT: "必须专业评估",
}
_OBLIGATION_MODALITY_ZH = {
    ControlObligationModality.MANDATORY: "必须完成",
    ControlObligationModality.RECOMMENDED: "建议完成",
    ControlObligationModality.BEST_EFFORT: "尽力完成",
}
_TEMPORAL_SCOPE_ZH = {
    ControlTemporalScopeKind.CALENDAR_LOOKBACK: "明确日历回顾窗",
    ControlTemporalScopeKind.FULL_HISTORY: "完整历程",
    ControlTemporalScopeKind.OFFICIAL_RULE_DEFINED: "按正式入排条款窗口",
    ControlTemporalScopeKind.SINCE_PREVIOUS_VISIT: "自上次访视以来",
}
_RELATION_KIND_ZH = {
    CrossSourceRelationKind.DUPLICATE_STATEMENT: "重复表述",
    CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT: "补充要求",
    CrossSourceRelationKind.FURTHER_EXPLANATION: "进一步解释",
    CrossSourceRelationKind.SUBSTANTIVE_CONFLICT: "实质冲突",
}
_ANCHOR_TYPE_ZH = {
    AnchorType.ICF_DATE: "知情同意日期",
    AnchorType.SCREENING_DATE: "筛选日期",
    AnchorType.BASELINE_DATE: "基线日期",
    AnchorType.RANDOMIZATION_DATE: "随机日期",
    AnchorType.FIRST_DOSE_DATE: "首次给药日期",
    AnchorType.STUDY_DRUG_ADMINISTRATION_DATE: "研究药物给药日期",
    AnchorType.LAST_DOSE_DATE: "末次给药日期",
    AnchorType.STUDY_COMPLETION_DATE: "研究完成日期",
    AnchorType.EVENT_DATE: "事件日期",
}
_TIME_DIRECTION_ZH = {
    TimeDirection.BEFORE: "之前",
    TimeDirection.AFTER: "之后",
    TimeDirection.ON: "当日",
}
_TIME_UNIT_ZH = {
    TimeUnit.DAY: "日",
    TimeUnit.WEEK: "周",
    TimeUnit.MONTH: "月",
    TimeUnit.YEAR: "年",
}
_VISIBLE_ENUM_VALUES = frozenset(
    str(value.value)
    for mapping in (
        _SOURCE_KIND_ZH,
        _PHASE_DISPOSITION_ZH,
        _REVIEW_STAGE_ZH,
        _REVIEW_ROLE_ZH,
        _OBLIGATION_KIND_ZH,
        _OBLIGATION_MODALITY_ZH,
        _TEMPORAL_SCOPE_ZH,
        _RELATION_KIND_ZH,
        _ANCHOR_TYPE_ZH,
        _TIME_DIRECTION_ZH,
        _TIME_UNIT_ZH,
    )
    for value in mapping
)
_VISIBLE_MACHINE_ID_PREFIXES = (
    "pcm-row-",
    "pcm-src-",
    "pcm-trg-",
    "stage:",
    "proc-",
    "pctrl-",
    "candidate-",
    "candidate:",
    "candidate_",
)
_VISIBLE_INTERNAL_FIELD_NAMES = (
    "matrix_row_id",
    "source_anchor_id",
    "source_anchor_ids",
    "source_ordinal",
    "structure_unit_id",
    "source_ref",
    "source_span_ids",
    "trigger_branch_id",
    "waives_trigger_branch_ids",
    "negated_atom_ids",
    "workflow_stage_id",
    "workflow_basis_row_id",
    "time_constraint_id",
    "evidence_id",
    "relation_id",
    "target_row_id",
    "atom_id",
    "obligation_id",
    "conjunction_group_id",
    "source_kind",
    "source_identity",
    "source_candidate_id",
    "candidate_identity",
    "candidate_id",
    "required_procedure_catalog_item_id",
    "procedure_catalog_item_id",
    "protocol_control_id",
    "official_parent_code",
    "official_child_code",
    "phase_disposition",
    "selected_phase",
    "protocol_version_id",
    "matrix_id",
    "schema_version",
    "condition_atoms",
    "obligations",
    "obligation_expression",
    "applicability_expression",
    "trigger_expression",
    "exception_expression",
    "minimum_evidence",
    "cross_source_relations",
    "verbatim_excerpt",
    "heading_path_zh",
    "source_title_zh",
    "required_source_types",
    "requires_professional_judgment",
    "requires_contemporaneous_objective_source",
    "requires_researcher_assessment_record",
    "allows_screening_record_transcription",
    "due_workflow_stage_id",
)


class _MatrixModel(ContractModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


def _value(value: object) -> str:
    return str(getattr(value, "value", value))


def _nonempty_unique(values: Sequence[str], label: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{label} 不得包含空值")
    if len(values) != len(set(values)):
        raise ValueError(f"{label} 不得重复")


def _has_substantive_text(value: str | None) -> bool:
    if value is None:
        return False
    normalized = re.sub(r"[\s:：，,。.!！?？/\\_-]+", "", value.casefold())
    return bool(normalized) and normalized not in _OBLIGATION_PLACEHOLDERS


def _normalise_title_token(value: str) -> str:
    return re.sub(r"[\s:：，,。.!！?？/\\_()（）\[\]【】{}\-]+", "", value.casefold())


_BRACKET_PAIRS = {
    "(": ")",
    "（": "）",
    "[": "]",
    "【": "】",
    "{": "}",
}
_CLOSING_BRACKETS = frozenset(_BRACKET_PAIRS.values())


def _top_level_logic_tokens(value: str) -> tuple[str, ...]:
    """Return Chinese logic connectors outside paired examples/terms."""

    tokens: list[str] = []
    depth = 0
    index = 0
    while index < len(value):
        char = value[index]
        if char in _BRACKET_PAIRS:
            depth += 1
            index += 1
            continue
        if char in _CLOSING_BRACKETS:
            depth = max(0, depth - 1)
            index += 1
            continue
        if depth == 0:
            matched = next(
                (
                    token
                    for token in (
                        "并且",
                        "或者",
                        "同时",
                        "以及",
                        "且",
                        "或",
                        "和",
                        "与",
                        "+",
                    )
                    if value.startswith(token, index)
                ),
                None,
            )
            if matched is not None:
                tokens.append(matched)
                index += len(matched)
                continue
        index += 1
    return tuple(tokens)


def _is_non_fact_label(value: str) -> bool:
    normalized = re.sub(r"[\s:：；;。.!！]+", "", value)
    return normalized.startswith(
        ("符合以下任一项", "存在以下任何一种", "以下要求", "注")
    )


def _validate_atomic_statement(value: str, label: str) -> None:
    if "\n" in value or "\r" in value or value.count(";") + value.count("；") >= 2:
        raise ValueError(f"{label}不得把换行或长分号列表压成一个原子")
    if _is_non_fact_label(value):
        raise ValueError(f"{label}不得使用列表引导语、章节提示或注记标签")
    tokens = _top_level_logic_tokens(value)
    if tokens:
        raise ValueError(f"{label}包含顶层逻辑连接词，必须拆分为原子和 DNF：{''.join(tokens)}")


def _logic_basis_has(basis: str | None, tokens: tuple[str, ...]) -> bool:
    return bool(basis and any(token in _top_level_logic_tokens(basis) for token in tokens))


def _compact_text(value: str) -> str:
    return re.sub(r"[\s:：，,。.!！?？;；]+", "", value.casefold()).strip()


def _is_candidate_identity(value: object) -> bool:
    if not isinstance(value, str) or not _CANDIDATE_ID.fullmatch(value):
        return False
    suffix = re.sub(r"^candidate[-_:]", "", value, flags=re.IGNORECASE)
    return _RESERVED_ID.fullmatch(suffix) is None


def _is_mechanical_official_title(title: str, official_code: str) -> bool:
    """Reject a title that only repeats an official code and generic words."""

    normalized_title = _normalise_title_token(title)
    normalized_code = _normalise_title_token(official_code)
    if not normalized_title or not normalized_code:
        return False
    if normalized_title == normalized_code:
        return True
    generic = rf"(?:{_GENERIC_TITLE_TOKEN})+"
    return bool(
        re.fullmatch(
            rf"(?:{generic}{re.escape(normalized_code)}|"
            rf"{re.escape(normalized_code)}{generic}|"
            rf"{generic}{re.escape(normalized_code)}{generic})",
            normalized_title,
        )
    )


def _sorted_unique(values: Sequence[str], label: str) -> None:
    _nonempty_unique(values, label)
    if list(values) != sorted(values):
        raise ValueError(f"{label} 必须按字典序排列")


def _stable_digest(*parts: object) -> str:
    payload = json.dumps(
        [_value(part) if isinstance(part, StableEnum) else part for part in parts],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def stable_protocol_control_matrix_row_id(
    source_kind: ProtocolControlMatrixSourceKind,
    source_identity: str,
    official_child_code: str | None = None,
) -> str:
    """Derive a deterministic row identity from source identity only."""

    if not source_identity.strip():
        raise ValueError("矩阵行来源身份不能为空")
    if official_child_code is not None and not official_child_code.strip():
        raise ValueError("官方子编号不能是空字符串")
    return "pcm-row-" + _stable_digest(
        _value(source_kind), source_identity, official_child_code
    )


def stable_protocol_control_matrix_anchor_id(
    matrix_row_id: str,
    anchor_ordinal: int,
) -> str:
    if not matrix_row_id.strip() or anchor_ordinal < 0:
        raise ValueError("矩阵来源锚点身份输入无效")
    return "pcm-src-" + _stable_digest(matrix_row_id, anchor_ordinal)


def stable_protocol_control_matrix_trigger_branch_id(
    matrix_row_id: str,
    branch_ordinal: int,
) -> str:
    """Derive a trigger branch identity from row identity and branch order."""

    if not matrix_row_id.strip() or branch_ordinal < 0:
        raise ValueError("矩阵触发分支身份输入无效")
    return "pcm-trg-" + _stable_digest(matrix_row_id, "trigger", branch_ordinal)


class MatrixSourceAnchor(_MatrixModel):
    """A verbatim excerpt tied to one frozen structure unit and its spans."""

    source_anchor_id: str = Field(
        min_length=1,
        validation_alias=AliasChoices("source_anchor_id", "anchor_id"),
    )
    source_ordinal: int = Field(
        ge=0,
        validation_alias=AliasChoices("source_ordinal", "anchor_ordinal"),
    )
    structure_unit_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    source_title_zh: str = Field(
        min_length=1,
        validation_alias=AliasChoices("source_title_zh", "source_title"),
    )
    heading_path_zh: list[str] = Field(
        min_length=1,
        validation_alias=AliasChoices("heading_path_zh", "heading_path"),
    )
    source_span_ids: list[str] = Field(min_length=1)
    verbatim_excerpt: str = Field(
        min_length=1,
        validation_alias=AliasChoices("verbatim_excerpt", "excerpt"),
    )

    @model_validator(mode="after")
    def validate_anchor(self) -> "MatrixSourceAnchor":
        _sorted_unique(self.source_span_ids, "矩阵来源锚点 source_span_ids")
        if any(not item.strip() for item in self.heading_path_zh):
            raise ValueError("矩阵来源标题路径不得包含空段")
        if not self.verbatim_excerpt.strip():
            raise ValueError("矩阵来源逐字摘录不得为空")
        return self


class MatrixConditionAtom(_MatrixModel):
    """A source-backed condition used by applicability, trigger or exception DNF."""

    atom_id: str = Field(min_length=1)
    statement_zh: str = Field(
        min_length=1,
        validation_alias=AliasChoices("statement_zh", "statement"),
    )
    source_anchor_ids: list[str] = Field(min_length=1)
    time_constraint_id: str | None = Field(default=None, min_length=1)
    requires_professional_judgment: bool = False

    @model_validator(mode="after")
    def validate_atom(self) -> "MatrixConditionAtom":
        _sorted_unique(self.source_anchor_ids, "矩阵条件原子 source_anchor_ids")
        if not self.statement_zh.strip():
            raise ValueError("矩阵条件原子中文表述不得为空")
        _validate_atomic_statement(self.statement_zh, "矩阵条件原子")
        return self


class MatrixObligation(_MatrixModel):
    """One typed obligation retained by a matrix row."""

    obligation_id: str = Field(min_length=1)
    kind: ControlObligationKind
    statement_zh: str = Field(
        min_length=1,
        validation_alias=AliasChoices("statement_zh", "statement"),
    )
    conjunction_group_id: str | None = Field(default=None, min_length=1)
    source_anchor_ids: list[str] = Field(min_length=1)
    time_constraint_id: str | None = Field(default=None, min_length=1)
    modality: ControlObligationModality = ControlObligationModality.MANDATORY
    temporal_scope: ControlTemporalScopeKind | None = None
    requires_professional_judgment: bool = False

    @model_validator(mode="after")
    def validate_obligation(self) -> "MatrixObligation":
        _sorted_unique(self.source_anchor_ids, "矩阵义务 source_anchor_ids")
        if not self.statement_zh.strip():
            raise ValueError("矩阵义务中文表述不得为空")
        _validate_atomic_statement(self.statement_zh, "矩阵义务")
        normalized = re.sub(r"[\s:：，,。.!！?？/\\_-]+", "", self.statement_zh.casefold())
        if normalized in _OBLIGATION_PLACEHOLDERS:
            raise ValueError("矩阵义务不得使用虚假占位表述")
        if self.conjunction_group_id is not None and not self.conjunction_group_id.strip():
            raise ValueError("且复合义务的合取组身份不得为空")
        if (
            self.modality == ControlObligationModality.BEST_EFFORT
            and self.kind
            in (
                ControlObligationKind.PROHIBIT_EVENT,
                ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE,
            )
        ):
            raise ValueError("尽力完成不得用于禁止类义务")
        if (
            self.modality == ControlObligationModality.RECOMMENDED
            and self.kind
            in (
                ControlObligationKind.PROHIBIT_EVENT,
                ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE,
            )
        ):
            raise ValueError("建议完成不得用于禁止类义务")
        if self.temporal_scope == ControlTemporalScopeKind.CALENDAR_LOOKBACK:
            if self.time_constraint_id is None:
                raise ValueError("日历回顾范围必须关联结构化时间窗")
        elif self.temporal_scope is not None and self.time_constraint_id is not None:
            raise ValueError("非日历时间范围不得复用全局结构化时间窗")
        return self


class MatrixDnfGroup(_MatrixModel):
    """One ALL path in explicit DNF, optionally containing deterministic NOT atoms."""

    atom_ids: list[str] = Field(default_factory=list)
    negated_atom_ids: list[str] = Field(default_factory=list)
    trigger_branch_id: str | None = Field(default=None, min_length=1)
    waives_trigger_branch_ids: list[str] = Field(default_factory=list)
    logic_basis_zh: str | None = Field(
        default=None,
        validation_alias=AliasChoices("logic_basis_zh", "basis_zh"),
    )
    source_anchor_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_group(self) -> "MatrixDnfGroup":
        if not self.atom_ids and not self.negated_atom_ids:
            raise ValueError("矩阵 DNF 路径至少需要一个正向或 NOT 原子")
        if self.atom_ids:
            _sorted_unique(self.atom_ids, "矩阵 DNF 合取组 atom_ids")
        if self.negated_atom_ids:
            _sorted_unique(self.negated_atom_ids, "矩阵 DNF 合取组 negated_atom_ids")
        if set(self.atom_ids).intersection(self.negated_atom_ids):
            raise ValueError("矩阵 DNF 同一原子不得同时正向和 NOT 引用")
        if self.waives_trigger_branch_ids:
            _sorted_unique(
                self.waives_trigger_branch_ids,
                "矩阵例外触发分支作用域",
            )
        if self.source_anchor_ids:
            _sorted_unique(self.source_anchor_ids, "矩阵 DNF 合取组 source_anchor_ids")
        if self.logic_basis_zh is not None and not self.logic_basis_zh.strip():
            raise ValueError("矩阵 DNF 逻辑依据不得为空")
        if self.member_count > 1:
            if not self.logic_basis_zh or not self.source_anchor_ids:
                raise ValueError("多原子 DNF 合取组必须保留逻辑依据和直接来源")
            if not _logic_basis_has(self.logic_basis_zh, ("且", "并且", "同时")):
                raise ValueError("多原子 DNF 合取组逻辑依据必须明确且关系")
        return self

    @property
    def member_count(self) -> int:
        return len(self.atom_ids) + len(self.negated_atom_ids)


class MatrixDnf(_MatrixModel):
    """Explicit ``(A AND B) OR (C)``; no free-text logic is accepted."""

    groups: list[MatrixDnfGroup] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dnf(self) -> "MatrixDnf":
        fingerprints = {
            (tuple(group.atom_ids), tuple(group.negated_atom_ids))
            for group in self.groups
        }
        if len(fingerprints) != len(self.groups):
            raise ValueError("矩阵 DNF 不得包含重复替代组")
        if len(self.groups) > 1:
            for group in self.groups:
                if not group.logic_basis_zh or not group.source_anchor_ids:
                    raise ValueError("多替代组 DNF 必须逐组保留逻辑依据和直接来源")
                if not _logic_basis_has(group.logic_basis_zh, ("或", "或者")):
                    raise ValueError("多替代组 DNF 逻辑依据必须明确或关系")
        return self


class MatrixTimeAnchor(_MatrixModel):
    """A named protocol time anchor/window with direct source support."""

    time_constraint_id: str = Field(min_length=1)
    anchor_label_zh: str = Field(
        min_length=1,
        validation_alias=AliasChoices("anchor_label_zh", "anchor_label"),
    )
    time_constraint: TimeConstraint = Field(
        validation_alias=AliasChoices("time_constraint", "constraint")
    )
    source_anchor_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_time_anchor(self) -> "MatrixTimeAnchor":
        _sorted_unique(self.source_anchor_ids, "矩阵时间锚点 source_anchor_ids")
        if not self.anchor_label_zh.strip():
            raise ValueError("时间锚点必须保留方案命名中文标签")
        return self


class MatrixReviewNode(_MatrixModel):
    """One explicit role of this control at one ordered review node."""

    workflow_stage_id: str = Field(min_length=1)
    review_stage: ReviewStage
    role: ReviewNodeRole
    stage_ordinal: int = Field(ge=0)
    node_label_zh: str = Field(
        min_length=1,
        validation_alias=AliasChoices("node_label_zh", "node_label"),
    )
    source_anchor_ids: list[str] = Field(default_factory=list)
    workflow_basis_row_id: str | None = Field(default=None, min_length=1)
    visit_instance: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_node(self) -> "MatrixReviewNode":
        if not self.node_label_zh.strip():
            raise ValueError("审核节点中文名称不得为空")
        if self.source_anchor_ids:
            _sorted_unique(self.source_anchor_ids, "审核节点 source_anchor_ids")
        if not self.source_anchor_ids and self.workflow_basis_row_id is None:
            raise ValueError("审核节点至少需要直接来源锚点或同矩阵流程依据")
        return self


class MatrixEvidence(_MatrixModel):
    """The minimum acceptable evidence and its due review node."""

    evidence_id: str = Field(min_length=1)
    fact_type_zh: str = Field(
        min_length=1,
        validation_alias=AliasChoices("fact_type_zh", "fact_type"),
    )
    description_zh: str = Field(
        min_length=1,
        validation_alias=AliasChoices("description_zh", "description"),
    )
    due_workflow_stage_id: str = Field(min_length=1)
    required_source_types: list[str] = Field(default_factory=list)
    source_anchor_ids: list[str] = Field(min_length=1)
    validity_time_constraint_id: str | None = Field(default=None, min_length=1)
    allows_screening_record_transcription: bool = True
    requires_contemporaneous_objective_source: bool = False
    requires_researcher_assessment_record: bool = False

    @model_validator(mode="after")
    def validate_evidence(self) -> "MatrixEvidence":
        _sorted_unique(self.source_anchor_ids, "矩阵最低证据 source_anchor_ids")
        if any(not item.strip() for item in self.required_source_types):
            raise ValueError("最低证据资料类型不得为空")
        if not self.fact_type_zh.strip() or not self.description_zh.strip():
            raise ValueError("最低证据必须有中文事实类型和说明")
        if _compact_text(self.fact_type_zh) in {
            _compact_text(item) for item in _EVIDENCE_PLACEHOLDER_FACT_TYPES
        }:
            raise ValueError("最低证据事实类型不得使用空泛方案条件或核对结果占位词")
        return self


class MatrixCrossSourceRelation(_MatrixModel):
    """A directional, explicit relation to another matrix row."""

    relation_id: str = Field(min_length=1)
    kind: CrossSourceRelationKind
    target_row_id: str = Field(min_length=1)
    source_anchor_ids: list[str] = Field(min_length=1)
    shared_assessment_identity: str | None = Field(default=None, min_length=1)
    resolution_zh: str | None = Field(default=None, min_length=1)
    notes_zh: str | None = Field(
        default=None,
        validation_alias=AliasChoices("notes_zh", "notes"),
    )

    @model_validator(mode="after")
    def validate_relation(self) -> "MatrixCrossSourceRelation":
        _sorted_unique(self.source_anchor_ids, "矩阵跨章节关系 source_anchor_ids")
        if self.kind == CrossSourceRelationKind.DUPLICATE_STATEMENT:
            if self.shared_assessment_identity is None:
                raise ValueError("重复表述关系必须提供共享评估身份")
        elif self.shared_assessment_identity is not None:
            raise ValueError("非重复表述关系不得共享评估身份")
        if self.kind != CrossSourceRelationKind.SUBSTANTIVE_CONFLICT and self.resolution_zh is not None:
            raise ValueError("非实质冲突关系不得携带冲突解决说明")
        return self


class ProtocolControlMatrixRow(_MatrixModel):
    """One row in the source-grounded comparison matrix."""

    matrix_row_id: str = Field(
        min_length=1,
        validation_alias=AliasChoices("matrix_row_id", "row_id"),
    )
    display_ordinal: int = Field(
        ge=1,
        validation_alias=AliasChoices("display_ordinal", "ordinal"),
    )
    source_kind: ProtocolControlMatrixSourceKind
    official_parent_code: str | None = Field(default=None, min_length=1)
    official_child_code: str | None = Field(default=None, min_length=1)
    required_procedure_catalog_item_id: str | None = Field(
        default=None,
        min_length=1,
        validation_alias=AliasChoices(
            "required_procedure_catalog_item_id",
            "procedure_catalog_item_id",
        ),
    )
    protocol_control_id: str | None = Field(default=None, min_length=1)
    source_candidate_id: str | None = Field(
        default=None,
        min_length=1,
        validation_alias=AliasChoices(
            "source_candidate_id",
            "candidate_identity",
            "candidate_id",
        ),
    )
    title_zh: str = Field(
        min_length=1,
        validation_alias=AliasChoices("title_zh", "short_title_zh", "title"),
    )
    applicable_population_zh: str = Field(
        min_length=1,
        validation_alias=AliasChoices(
            "applicable_population_zh", "applicable_population"
        ),
    )
    trigger_condition_zh: str | None = Field(
        default=None,
        min_length=1,
        validation_alias=AliasChoices("trigger_condition_zh", "trigger_condition"),
    )
    required_action_zh: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "required_action_zh", "action_zh", "what_to_do_zh"
        ),
    )
    attainment_criteria_zh: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "attainment_criteria_zh", "target_state_zh", "target_to_reach_zh"
        ),
    )
    prohibition_zh: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "prohibition_zh", "prohibited_what_zh", "cannot_happen_zh"
        ),
    )
    phase_disposition: MatrixPhaseDisposition = Field(
        validation_alias=AliasChoices("phase_disposition", "phase_applicability")
    )
    source_anchors: list[MatrixSourceAnchor] = Field(
        min_length=1,
        validation_alias=AliasChoices("source_anchors", "sources"),
    )
    condition_atoms: list[MatrixConditionAtom] = Field(default_factory=list)
    applicability_expression: MatrixDnf | None = None
    trigger_expression: MatrixDnf | None = None
    obligations: list[MatrixObligation] = Field(min_length=1)
    obligation_expression: MatrixDnf = Field(...)
    exception_expression: MatrixDnf | None = None
    time_anchors: list[MatrixTimeAnchor] = Field(default_factory=list)
    review_nodes: list[MatrixReviewNode] = Field(min_length=1)
    minimum_evidence: list[MatrixEvidence] = Field(min_length=1)
    cross_source_relations: list[MatrixCrossSourceRelation] = Field(
        default_factory=list
    )
    unexpressed_logic: list[str] = Field(default_factory=list)

    @property
    def source_identity(self) -> str:
        if self.source_kind == ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY:
            return self.official_child_code or self.official_parent_code or ""
        if self.source_kind == ProtocolControlMatrixSourceKind.REQUIRED_PROCEDURE:
            return (
                self.required_procedure_catalog_item_id
                or self.source_candidate_id
                or ""
            )
        return self.protocol_control_id or self.source_candidate_id or ""

    @property
    def source_structure_unit_ids(self) -> list[str]:
        return sorted({item.structure_unit_id for item in self.source_anchors})

    @property
    def source_span_ids(self) -> list[str]:
        return sorted(
            {
                span_id
                for item in self.source_anchors
                for span_id in item.source_span_ids
            }
        )

    @property
    def display_label_zh(self) -> str:
        return f"矩阵控制 {self.display_ordinal:02d}"

    @model_validator(mode="after")
    def validate_row(self) -> "ProtocolControlMatrixRow":
        if _RESERVED_ID.fullmatch(self.matrix_row_id.strip()):
            raise ValueError("矩阵行身份不得伪装为 IN/EX/REQ/CTRL 官方编号")
        if not self.title_zh.strip() or not self.applicable_population_zh.strip():
            raise ValueError("矩阵行必须保留中文标题和适用人群")

        if self.official_parent_code is not None and not _OFFICIAL_PARENT.fullmatch(
            self.official_parent_code
        ):
            raise ValueError("官方父编号必须是既有 IN-xx 或 EX-xx 形态")
        if self.official_child_code is not None:
            if self.official_parent_code is None:
                raise ValueError("官方子编号必须绑定官方父编号")
            if not _OFFICIAL_CHILD.fullmatch(self.official_child_code):
                raise ValueError("官方子编号必须保留父编号前缀和层级分隔符")
            if not self.official_child_code.startswith(self.official_parent_code):
                raise ValueError("官方子编号必须以其父编号开头")

        if self.source_kind == ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY:
            if self.official_parent_code is None:
                raise ValueError("官方入排矩阵行必须提供官方父编号")
            if any(
                item is not None
                for item in (
                    self.required_procedure_catalog_item_id,
                    self.protocol_control_id,
                    self.source_candidate_id,
                )
            ):
                raise ValueError("官方入排行不得携带流程、其他控制或候选身份")
            for official_code in filter(
                None, (self.official_child_code, self.official_parent_code)
            ):
                if _is_mechanical_official_title(self.title_zh, official_code):
                    raise ValueError("官方矩阵标题不得仅机械重复编号和泛化词")
        elif self.source_kind == ProtocolControlMatrixSourceKind.REQUIRED_PROCEDURE:
            if sum(
                item is not None
                for item in (
                    self.required_procedure_catalog_item_id,
                    self.source_candidate_id,
                )
            ) != 1:
                raise ValueError(
                    "流程必做矩阵行必须且只能提供正式流程目录身份或来源候选身份"
                )
            if self.required_procedure_catalog_item_id is not None and _CANDIDATE_ID.fullmatch(
                self.required_procedure_catalog_item_id
            ):
                raise ValueError("正式流程目录身份不得使用流程候选身份")
            if any(
                item is not None
                for item in (
                    self.official_parent_code,
                    self.official_child_code,
                    self.protocol_control_id,
                )
            ):
                raise ValueError("流程必做行不得伪造官方或其他控制身份")
            if self.source_candidate_id is not None and not _is_candidate_identity(
                self.source_candidate_id
            ):
                raise ValueError("来源候选身份必须使用稳定的 candidate 前缀且不得伪装正式身份")
        elif self.source_kind == ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL:
            if sum(
                item is not None
                for item in (self.protocol_control_id, self.source_candidate_id)
            ) != 1:
                raise ValueError(
                    "其他章节控制矩阵行必须且只能提供正式控制身份或来源候选身份"
                )
            if any(
                item is not None
                for item in (
                    self.official_parent_code,
                    self.official_child_code,
                    self.required_procedure_catalog_item_id,
                )
            ):
                raise ValueError("其他章节控制行不得携带官方或流程身份")
            if self.source_candidate_id is not None and not _is_candidate_identity(
                self.source_candidate_id
            ):
                raise ValueError("来源候选身份必须使用稳定的 candidate 前缀且不得伪装正式身份")

        expected_row_id = stable_protocol_control_matrix_row_id(
            self.source_kind,
            self.source_identity,
            self.official_child_code,
        )
        if self.matrix_row_id != expected_row_id:
            raise ValueError("矩阵行身份必须等于系统派生身份")

        anchor_ids = [item.source_anchor_id for item in self.source_anchors]
        _nonempty_unique(anchor_ids, "矩阵来源锚点身份")
        anchor_ordinals = [item.source_ordinal for item in self.source_anchors]
        if anchor_ordinals != list(range(len(anchor_ordinals))):
            raise ValueError("矩阵来源锚点必须按稳定序位连续排列")
        for anchor in self.source_anchors:
            expected_anchor_id = stable_protocol_control_matrix_anchor_id(
                self.matrix_row_id, anchor.source_ordinal
            )
            if anchor.source_anchor_id != expected_anchor_id:
                raise ValueError("矩阵来源锚点身份必须等于行身份和稳定序位的派生值")
        condition_ids = [item.atom_id for item in self.condition_atoms]
        obligation_ids = [item.obligation_id for item in self.obligations]
        time_ids = [item.time_constraint_id for item in self.time_anchors]
        evidence_ids = [item.evidence_id for item in self.minimum_evidence]
        relation_ids = [item.relation_id for item in self.cross_source_relations]
        node_keys = [(item.workflow_stage_id, item.role.value) for item in self.review_nodes]
        _nonempty_unique(condition_ids, "矩阵条件原子身份")
        _nonempty_unique(obligation_ids, "矩阵义务身份")
        _nonempty_unique(time_ids, "矩阵时间锚点身份")
        _nonempty_unique(evidence_ids, "矩阵最低证据身份")
        _nonempty_unique(relation_ids, "矩阵跨章节关系身份")
        if not any(
            _has_substantive_text(value)
            for value in (
                self.required_action_zh,
                self.attainment_criteria_zh,
                self.prohibition_zh,
                *(item.statement_zh for item in self.obligations),
            )
        ):
            raise ValueError("矩阵行至少需要一项来自方案的实质性内容")
        if len(node_keys) != len(set(node_keys)):
            raise ValueError("同一审核节点不得重复绑定相同作用")
        if not any(item.role == ReviewNodeRole.DECIDE_AT_NODE for item in self.review_nodes):
            raise ValueError("矩阵控制至少需要一个本节点判定作用")

        if self.unexpressed_logic:
            if any(not item.strip() for item in self.unexpressed_logic):
                raise ValueError("未表达逻辑原因不得包含空值")
            raise ValueError("存在不能表达的逻辑，矩阵行必须拒绝")

        atom_ids_by_layer: dict[str, list[str]] = {
            "applicability": [],
            "trigger": [],
            "exception": [],
        }
        for expression_name, expression in (
            ("applicability", self.applicability_expression),
            ("trigger", self.trigger_expression),
            ("exception", self.exception_expression),
        ):
            if expression is not None:
                atom_ids_by_layer[expression_name] = [
                    atom_id
                    for group in expression.groups
                    for atom_id in (*group.atom_ids, *group.negated_atom_ids)
                ]
        referenced_conditions = [
            atom_id
            for values in atom_ids_by_layer.values()
            for atom_id in values
        ]
        if set(referenced_conditions) != set(condition_ids) or len(
            referenced_conditions
        ) != len(condition_ids):
            raise ValueError("条件原子必须在适用/触发/例外 DNF 中恰好引用一次")

        referenced_obligations = [
            atom_id
            for group in self.obligation_expression.groups
            for atom_id in (*group.atom_ids, *group.negated_atom_ids)
        ]
        if set(referenced_obligations) != set(obligation_ids) or len(
            referenced_obligations
        ) != len(obligation_ids):
            raise ValueError("六类义务原子必须在义务 DNF 中恰好引用一次")
        if any(
            group.negated_atom_ids for group in self.obligation_expression.groups
        ):
            raise ValueError("义务 DNF 不支持 NOT 义务原子")

        known_anchor_ids = set(anchor_ids)
        used_anchor_ids: set[str] = set()
        for expression_name, expression in (
            ("适用", self.applicability_expression),
            ("触发", self.trigger_expression),
            ("义务", self.obligation_expression),
            ("例外", self.exception_expression),
        ):
            if expression is None:
                continue
            if len(expression.groups) > 1:
                for group in expression.groups:
                    if not group.logic_basis_zh or not group.source_anchor_ids:
                        raise ValueError(f"{expression_name} DNF 的替代组必须保留逻辑依据和来源")
            if not set(
                anchor_id
                for group in expression.groups
                for anchor_id in group.source_anchor_ids
            ) <= known_anchor_ids:
                raise ValueError(f"{expression_name} DNF 逻辑依据来源不得越出矩阵来源锚点闭包")
            used_anchor_ids.update(
                anchor_id
                for group in expression.groups
                for anchor_id in group.source_anchor_ids
            )

        conjunctions: dict[str, list[str]] = {}
        for obligation in self.obligations:
            if obligation.conjunction_group_id is not None:
                conjunctions.setdefault(obligation.conjunction_group_id, []).append(
                    obligation.obligation_id
                )
        obligation_groups = [set(group.atom_ids) for group in self.obligation_expression.groups]
        for conjunction_id, members in conjunctions.items():
            if len(members) < 2:
                raise ValueError("且复合义务必须拆分为至少两个原子")
            if set(members) not in obligation_groups:
                raise ValueError("且复合义务不得被弱化为单原子或替代组")

        for atom in (*self.condition_atoms, *self.obligations):
            if not set(atom.source_anchor_ids) <= known_anchor_ids:
                raise ValueError("语义原子来源不得越出矩阵来源锚点闭包")
            used_anchor_ids.update(atom.source_anchor_ids)
            if atom.time_constraint_id is not None and atom.time_constraint_id not in time_ids:
                raise ValueError("语义原子引用了未知时间锚点")
        for item in self.time_anchors:
            if not set(item.source_anchor_ids) <= known_anchor_ids:
                raise ValueError("时间锚点来源不得越出矩阵来源闭包")
            used_anchor_ids.update(item.source_anchor_ids)
        node_ids = {item.workflow_stage_id for item in self.review_nodes}
        for node in self.review_nodes:
            used_anchor_ids.update(node.source_anchor_ids)
        for item in self.minimum_evidence:
            if item.due_workflow_stage_id not in node_ids:
                raise ValueError("最低证据 due_workflow_stage_id 必须绑定审核节点")
            if not set(item.source_anchor_ids) <= known_anchor_ids:
                raise ValueError("最低证据来源不得越出矩阵来源闭包")
            used_anchor_ids.update(item.source_anchor_ids)
            if (
                item.validity_time_constraint_id is not None
                and item.validity_time_constraint_id not in time_ids
            ):
                raise ValueError("最低证据引用了未知结果有效期时间锚点")
        for relation in self.cross_source_relations:
            if not set(relation.source_anchor_ids) <= known_anchor_ids:
                raise ValueError("跨章节关系来源不得越出矩阵来源闭包")
            used_anchor_ids.update(relation.source_anchor_ids)
            if relation.target_row_id == self.matrix_row_id:
                raise ValueError("跨章节关系不得指向自身")
        if used_anchor_ids != known_anchor_ids:
            unused = sorted(known_anchor_ids - used_anchor_ids)
            raise ValueError("矩阵来源锚点存在未绑定语义的孤儿来源：" + ",".join(unused))

        for item in self.review_nodes:
            if item.role == ReviewNodeRole.LATER_NODE_REVIEW and not any(
                other.role == ReviewNodeRole.DECIDE_AT_NODE
                and other.stage_ordinal > item.stage_ordinal
                for other in self.review_nodes
            ):
                raise ValueError("后续节点复核必须存在更晚的本节点判定")
        for item in self.time_anchors:
            label = item.anchor_label_zh
            anchor = item.time_constraint.anchor_type
            if anchor == AnchorType.SCREENING_DATE and any(
                cue in label for cue in ("随机", "基线", "首次给药", "首次用药")
            ):
                raise ValueError("随机/基线/首次给药时间窗不得用筛选日期替代")
        _validate_row_semantic_boundaries(self)
        return self


def _reject_semantic_boundary(
    message: str,
    *,
    code: str,
    entity_id: str | None,
    strict: bool,
) -> None:
    if strict:
        raise ProtocolControlMatrixError(code, message, entity_id=entity_id)
    raise ValueError(message)


def _row_source_text(
    row: ProtocolControlMatrixRow,
    source_anchor_ids: Sequence[str] | None = None,
) -> str:
    wanted = set(source_anchor_ids) if source_anchor_ids is not None else None
    chunks: list[str] = []
    for anchor in row.source_anchors:
        if wanted is not None and anchor.source_anchor_id not in wanted:
            continue
        chunks.extend(
            (
                anchor.source_title_zh,
                " ".join(anchor.heading_path_zh),
                anchor.verbatim_excerpt,
            )
        )
    return " ".join(chunks)


def _validate_dnf_logic_boundaries(
    row: ProtocolControlMatrixRow,
    *,
    strict: bool,
) -> None:
    for expression_name, expression in (
        ("适用", row.applicability_expression),
        ("触发", row.trigger_expression),
        ("义务", row.obligation_expression),
        ("例外", row.exception_expression),
    ):
        if expression is None:
            continue
        multiple_groups = len(expression.groups) > 1
        has_compound_group = any(group.member_count > 1 for group in expression.groups)
        if not (multiple_groups or has_compound_group):
            continue
        for group in expression.groups:
            if not group.logic_basis_zh or not group.source_anchor_ids:
                _reject_semantic_boundary(
                    f"{expression_name} DNF 每个复合/替代组必须保留逻辑依据和直接来源",
                    code="DNF_LOGIC_BASIS_MISSING",
                    entity_id=row.matrix_row_id,
                    strict=strict,
                )
            if group.member_count > 1 and not _logic_basis_has(
                group.logic_basis_zh, ("且", "并且", "同时")
            ):
                _reject_semantic_boundary(
                    f"{expression_name} DNF 合取组逻辑依据必须明确且关系",
                    code="DNF_AND_BASIS_MISSING",
                    entity_id=row.matrix_row_id,
                    strict=strict,
                )
            if multiple_groups and not _logic_basis_has(
                group.logic_basis_zh, ("或", "或者")
            ):
                _reject_semantic_boundary(
                    f"{expression_name} DNF 替代组逻辑依据必须明确或关系",
                    code="DNF_OR_BASIS_MISSING",
                    entity_id=row.matrix_row_id,
                    strict=strict,
                )


def _validate_trigger_branch_boundaries(
    row: ProtocolControlMatrixRow,
    *,
    strict: bool,
) -> None:
    expressions = (
        ("适用", row.applicability_expression),
        ("义务", row.obligation_expression),
        ("例外", row.exception_expression),
    )
    for expression_name, expression in expressions:
        if expression is not None and any(
            group.trigger_branch_id is not None for group in expression.groups
        ):
            _reject_semantic_boundary(
                f"触发分支身份不得出现在{expression_name} DNF",
                code="TRIGGER_BRANCH_ID_WRONG_LAYER",
                entity_id=row.matrix_row_id,
                strict=strict,
            )
        if expression is not None and any(
            group.waives_trigger_branch_ids for group in expression.groups
        ) and expression_name != "例外":
            _reject_semantic_boundary(
                f"例外触发分支作用域不得出现在{expression_name} DNF",
                code="EXCEPTION_SCOPE_WRONG_LAYER",
                entity_id=row.matrix_row_id,
                strict=strict,
            )

    expression = row.trigger_expression
    if expression is None:
        return
    for ordinal, group in enumerate(expression.groups):
        expected = stable_protocol_control_matrix_trigger_branch_id(
            row.matrix_row_id,
            ordinal,
        )
        if group.trigger_branch_id is None:
            _reject_semantic_boundary(
                "触发 DNF 每个替代分支必须有稳定身份",
                code="TRIGGER_BRANCH_ID_MISSING",
                entity_id=row.matrix_row_id,
                strict=strict,
            )
        if group.trigger_branch_id != expected:
            _reject_semantic_boundary(
                "触发 DNF 分支身份必须由行身份和稳定序位派生",
                code="TRIGGER_BRANCH_ID_DERIVED_MISMATCH",
                entity_id=group.trigger_branch_id,
                strict=strict,
            )


def _validate_exception_scope_boundaries(
    row: ProtocolControlMatrixRow,
    *,
    strict: bool,
) -> None:
    expression = row.exception_expression
    if expression is None:
        return
    trigger_expression = row.trigger_expression
    if trigger_expression is None:
        _reject_semantic_boundary(
            "存在例外 DNF 时必须同时存在可被作用的触发 DNF",
            code="EXCEPTION_TRIGGER_MISSING",
            entity_id=row.matrix_row_id,
            strict=strict,
        )
    trigger_branch_ids = [
        group.trigger_branch_id
        for group in trigger_expression.groups
        if group.trigger_branch_id is not None
    ]
    non_trigger_branch_ids = {
        group.trigger_branch_id
        for candidate_expression in (
            row.applicability_expression,
            row.obligation_expression,
        )
        if candidate_expression is not None
        for group in candidate_expression.groups
        if group.trigger_branch_id is not None
    }
    known_anchor_ids = {anchor.source_anchor_id for anchor in row.source_anchors}
    for group in expression.groups:
        scoped_ids = group.waives_trigger_branch_ids
        if not scoped_ids:
            _reject_semantic_boundary(
                "每个例外 DNF 路径必须明确声明可作用的触发分支",
                code="EXCEPTION_SCOPE_MISSING",
                entity_id=row.matrix_row_id,
                strict=strict,
            )
        if list(scoped_ids) != sorted(set(scoped_ids)):
            _reject_semantic_boundary(
                "例外触发分支作用域必须按字典序唯一排列",
                code="EXCEPTION_SCOPE_ORDER_INVALID",
                entity_id=row.matrix_row_id,
                strict=strict,
            )
        if set(scoped_ids).intersection(non_trigger_branch_ids):
            _reject_semantic_boundary(
                "例外作用域不得引用适用或义务 DNF 分支",
                code="EXCEPTION_SCOPE_NON_TRIGGER",
                entity_id=row.matrix_row_id,
                strict=strict,
            )
        unknown_ids = set(scoped_ids) - set(trigger_branch_ids)
        if unknown_ids:
            _reject_semantic_boundary(
                "例外作用域引用了未知触发 DNF 分支",
                code="EXCEPTION_SCOPE_UNKNOWN_TRIGGER",
                entity_id=sorted(unknown_ids)[0],
                strict=strict,
            )
        if not group.source_anchor_ids:
            _reject_semantic_boundary(
                "例外 DNF 路径必须保留直接来源锚点以支持作用域",
                code="EXCEPTION_SCOPE_SOURCE_MISSING",
                entity_id=row.matrix_row_id,
                strict=strict,
            )
        if not set(group.source_anchor_ids) <= known_anchor_ids:
            _reject_semantic_boundary(
                "例外作用域来源不得越出矩阵来源闭包",
                code="EXCEPTION_SCOPE_SOURCE_ESCAPE",
                entity_id=row.matrix_row_id,
                strict=strict,
            )
        if len(trigger_branch_ids) > 1 and set(scoped_ids) == set(trigger_branch_ids):
            source_text = _row_source_text(row, group.source_anchor_ids)
            if not any(cue in source_text for cue in _EXCEPTION_BROAD_SCOPE_CUES):
                _reject_semantic_boundary(
                    "例外作用于全部触发分支时必须有来源明确支持",
                    code="EXCEPTION_SCOPE_ALL_UNSUPPORTED",
                    entity_id=row.matrix_row_id,
                    strict=strict,
                )


def _validate_atomic_boundaries(
    row: ProtocolControlMatrixRow,
    *,
    strict: bool,
) -> None:
    for atom in (*row.condition_atoms, *row.obligations):
        try:
            _validate_atomic_statement(
                atom.statement_zh,
                "矩阵条件原子" if isinstance(atom, MatrixConditionAtom) else "矩阵义务",
            )
        except ValueError:
            _reject_semantic_boundary(
                "条件/义务原子包含未拆分的顶层逻辑、列表或长文本",
                code="ATOMIC_LOGIC_NOT_EXPRESSED",
                entity_id=getattr(atom, "atom_id", getattr(atom, "obligation_id", None)),
                strict=strict,
            )


def _validate_source_logic_boundaries(
    row: ProtocolControlMatrixRow,
    *,
    strict: bool,
) -> None:
    if getattr(row, "unexpressed_logic", ()):
        _reject_semantic_boundary(
            "存在未表达逻辑，矩阵行不得发布",
            code="UNEXPRESSED_LOGIC_PRESENT",
            entity_id=row.matrix_row_id,
            strict=strict,
        )
    source_tokens: set[str] = set()
    for anchor in row.source_anchors:
        tokens = set(_top_level_logic_tokens(anchor.verbatim_excerpt))
        # A fixed-window/half-life choice is a time-window expression, not a
        # condition DNF alternative; its completeness is checked below.
        anchor_text = " ".join(
            (
                anchor.source_title_zh,
                " ".join(anchor.heading_path_zh),
                anchor.verbatim_excerpt,
            )
        )
        if "半衰期" in anchor_text or re.search(
            r"筛选\s*(?:和|或|与|及)\s*基线|基线\s*(?:和|或|与|及)\s*筛选",
            anchor_text,
        ):
            tokens.difference_update({"或", "或者", "和", "与", "以及"})
        source_tokens.update(tokens)
    source_has_list_guide = any(
        any(
            _is_non_fact_label(piece)
            and not re.sub(r"[\s:：；;。.!！]+", "", piece).startswith("注")
            for piece in (
                anchor.source_title_zh,
                *anchor.heading_path_zh,
                anchor.verbatim_excerpt,
            )
        )
        for anchor in row.source_anchors
    )
    and_tokens = {"且", "并且", "同时", "以及", "和", "与", "+"}
    or_tokens = {"或", "或者"}
    expressions = (
        row.applicability_expression,
        row.trigger_expression,
        row.obligation_expression,
        row.exception_expression,
    )
    if source_tokens.intersection(and_tokens) and not any(
        expression is not None
        and any(group.member_count > 1 for group in expression.groups)
        for expression in expressions
    ):
        _reject_semantic_boundary(
            "来源存在顶层且关系但矩阵未拆分并表达合取逻辑",
            code="SOURCE_AND_LOGIC_NOT_EXPRESSED",
            entity_id=row.matrix_row_id,
            strict=strict,
        )
    if (source_tokens.intersection(or_tokens) or source_has_list_guide) and not any(
        expression is not None and len(expression.groups) > 1
        for expression in expressions
    ):
        _reject_semantic_boundary(
            "来源存在顶层或/列表分支关系但矩阵未表达替代组",
            code="SOURCE_OR_LOGIC_NOT_EXPRESSED",
            entity_id=row.matrix_row_id,
            strict=strict,
        )


def _evidence_has_researcher_record(evidence: MatrixEvidence) -> bool:
    if evidence.requires_researcher_assessment_record:
        return True
    text = " ".join(
        (
            evidence.fact_type_zh,
            evidence.description_zh,
            *evidence.required_source_types,
        )
    )
    return "研究者" in text and any(cue in text for cue in ("评估", "判断", "记录"))


def _validate_evidence_boundaries(
    row: ProtocolControlMatrixRow,
    *,
    strict: bool,
) -> None:
    if row.source_kind == ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY and any(
        not evidence.required_source_types for evidence in row.minimum_evidence
    ):
        _reject_semantic_boundary(
            "官方入排行的最低证据必须声明具体来源类型",
            code="OFFICIAL_EVIDENCE_SOURCE_TYPES_MISSING",
            entity_id=row.matrix_row_id,
            strict=strict,
        )
    source_excerpts = {
        _compact_text(anchor.verbatim_excerpt)
        for anchor in row.source_anchors
    }
    obligation_statements = {
        _compact_text(obligation.statement_zh)
        for obligation in row.obligations
    }
    for evidence in row.minimum_evidence:
        if _compact_text(evidence.fact_type_zh) in {
            _compact_text(item) for item in _EVIDENCE_PLACEHOLDER_FACT_TYPES
        }:
            _reject_semantic_boundary(
                "最低证据事实类型不得使用空泛方案条件或核对结果占位词",
                code="EVIDENCE_FACT_TYPE_PLACEHOLDER",
                entity_id=evidence.evidence_id,
                strict=strict,
            )
        description = _compact_text(evidence.description_zh)
        if description in source_excerpts or description in obligation_statements:
            _reject_semantic_boundary(
                "最低证据说明不得逐字复述完整来源规则或义务原子",
                code="EVIDENCE_DESCRIPTION_REPEATS_RULE",
                entity_id=evidence.evidence_id,
                strict=strict,
            )
    semantic_text = " ".join(
        (
            _row_source_text(row),
            row.title_zh,
            row.applicable_population_zh,
            row.trigger_condition_zh or "",
            row.required_action_zh or "",
            row.attainment_criteria_zh or "",
            row.prohibition_zh or "",
            *(atom.statement_zh for atom in row.condition_atoms),
            *(obligation.statement_zh for obligation in row.obligations),
        )
    )
    if any(cue in semantic_text for cue in _OBJECTIVE_EVIDENCE_CUES) and not any(
        evidence.requires_contemporaneous_objective_source
        for evidence in row.minimum_evidence
    ):
        _reject_semantic_boundary(
            "涉及实验室、检查、妊娠或评分等客观结果时必须声明同期客观来源",
            code="OBJECTIVE_EVIDENCE_SOURCE_REQUIRED",
            entity_id=row.matrix_row_id,
            strict=strict,
        )
    needs_researcher_record = any(
        atom.requires_professional_judgment
        for atom in (*row.condition_atoms, *row.obligations)
    )
    if needs_researcher_record and not any(
        _evidence_has_researcher_record(evidence)
        for evidence in row.minimum_evidence
    ):
        _reject_semantic_boundary(
            "需要专业判断的控制必须有研究者评估记录最低证据",
            code="RESEARCHER_EVIDENCE_REQUIRED",
            entity_id=row.matrix_row_id,
            strict=strict,
        )


def _validate_review_node_boundaries(
    row: ProtocolControlMatrixRow,
    *,
    strict: bool,
) -> None:
    known_anchor_ids = {anchor.source_anchor_id for anchor in row.source_anchors}
    for node in row.review_nodes:
        source_ids = getattr(node, "source_anchor_ids", None) or []
        if not getattr(node, "node_label_zh", "").strip():
            _reject_semantic_boundary(
                "审核节点中文名称不得为空",
                code="REVIEW_NODE_LABEL_EMPTY",
                entity_id=node.workflow_stage_id,
                strict=strict,
            )
        workflow_basis_row_id = getattr(node, "workflow_basis_row_id", None)
        if not source_ids and workflow_basis_row_id is None:
            _reject_semantic_boundary(
                "审核节点必须绑定直接来源锚点或同矩阵流程依据",
                code="REVIEW_NODE_SOURCE_MISSING",
                entity_id=node.workflow_stage_id,
                strict=strict,
            )
        if source_ids and list(source_ids) != sorted(set(source_ids)):
            _reject_semantic_boundary(
                "审核节点来源锚点必须按字典序唯一排列",
                code="REVIEW_NODE_SOURCE_ORDER_INVALID",
                entity_id=node.workflow_stage_id,
                strict=strict,
            )
        if not set(source_ids) <= known_anchor_ids:
            _reject_semantic_boundary(
                "审核节点来源不得越出矩阵来源闭包",
                code="REVIEW_NODE_SOURCE_ESCAPE",
                entity_id=node.workflow_stage_id,
                strict=strict,
            )
        source_text = _row_source_text(row, source_ids) if source_ids else ""
        stage_cues = _STAGE_SOURCE_CUES[node.review_stage]
        if not workflow_basis_row_id and not any(cue in source_text for cue in stage_cues):
            _reject_semantic_boundary(
                "审核节点阶段必须由直接来源锚点命名或规范映射支持，或由同矩阵流程依据支持",
                code="REVIEW_NODE_STAGE_UNSUPPORTED",
                entity_id=node.workflow_stage_id,
                strict=strict,
            )
        label_supported = _normalise_title_token(node.node_label_zh) in _normalise_title_token(
            source_text
        )
        if (
            not label_supported
            and not any(cue in node.node_label_zh for cue in stage_cues)
            and not workflow_basis_row_id
        ):
            _reject_semantic_boundary(
                "审核节点中文名称必须由直接来源摘录、规范阶段名称或同矩阵流程依据支持",
                code="REVIEW_NODE_LABEL_UNSUPPORTED",
                entity_id=node.workflow_stage_id,
                strict=strict,
            )


def _validate_time_boundaries(
    row: ProtocolControlMatrixRow,
    *,
    strict: bool,
) -> None:
    source_text = _row_source_text(row)
    milestone_text = " ".join(
        [source_text, *(anchor.anchor_label_zh for anchor in row.time_anchors)]
    )
    has_screening_baseline_pair = bool(
        re.search(r"筛选\s*(?:和|或|与|及)\s*基线", milestone_text)
        or re.search(r"基线\s*(?:和|或|与|及)\s*筛选", milestone_text)
    )
    if has_screening_baseline_pair:
        labels = [anchor.anchor_label_zh for anchor in row.time_anchors]
        if len(set(labels)) < 2 or not any("筛选" in label for label in labels) or not any(
            "基线" in label for label in labels
        ):
            _reject_semantic_boundary(
                "来源同时命名筛选和基线时必须保留两个命名时间锚点",
                code="TIME_MULTIPLE_MILESTONES_COLLAPSED",
                entity_id=row.matrix_row_id,
                strict=strict,
            )
    source_by_anchor_id = {
        anchor.source_anchor_id: anchor.verbatim_excerpt
        for anchor in row.source_anchors
    }
    for anchor in row.time_anchors:
        label = anchor.anchor_label_zh
        anchor_type = anchor.time_constraint.anchor_type
        if "筛选" in label and anchor_type == AnchorType.EVENT_DATE:
            _reject_semantic_boundary(
                "筛选命名时间锚点不得使用泛化事件日期",
                code="TIME_EVENT_DATE_SCREENING_GENERIC",
                entity_id=anchor.time_constraint_id,
                strict=strict,
            )
        if "基线" in label and anchor_type == AnchorType.EVENT_DATE:
            _reject_semantic_boundary(
                "基线命名时间锚点不得使用泛化事件日期",
                code="TIME_EVENT_DATE_BASELINE_GENERIC",
                entity_id=anchor.time_constraint_id,
                strict=strict,
            )
        if any(cue in label for cue in ("随机", "首次给药", "首次用药")) and anchor_type in {
            AnchorType.SCREENING_DATE,
            AnchorType.EVENT_DATE,
        }:
            _reject_semantic_boundary(
                "随机/首次给药命名时间锚点不得使用筛选或泛化事件日期",
                code="TIME_ANCHOR_NAMED_MILESTONE_GENERIC",
                entity_id=anchor.time_constraint_id,
                strict=strict,
            )
        has_window_cue = bool(
            re.search(r"\d|半衰期|时间窗|窗口|期限|周|月|日|年", label)
        )
        has_relative_cue = any(cue in label for cue in ("前", "之前", "以内", "内", "后", "之后"))
        if anchor.time_constraint.direction == TimeDirection.ON and any(
            cue in label for cue in ("后", "之后")
        ):
            _reject_semantic_boundary(
                "含后/之后的时间锚点不得标为当日 ON",
                code="TIME_AFTER_ON_INVALID",
                entity_id=anchor.time_constraint_id,
                strict=strict,
            )
        if anchor.time_constraint.direction == TimeDirection.ON and has_relative_cue and (
            has_window_cue or any(cue in label for cue in ("首次给药", "首次用药", "随机"))
        ):
            _reject_semantic_boundary(
                "带相对方向或回溯窗口的时间锚点不得标为当日 ON",
                code="TIME_WINDOW_ON_INVALID",
                entity_id=anchor.time_constraint_id,
                strict=strict,
            )
        anchor_source_text = " ".join(
            source_by_anchor_id.get(source_id, "")
            for source_id in anchor.source_anchor_ids
        )
        combined = f"{label} {anchor_source_text}"
        source_tokens = _top_level_logic_tokens(combined)
        if "半衰期" in combined and (
            "较长" in combined or set(source_tokens).intersection({"或", "或者"})
        ):
            constraint = anchor.time_constraint
            has_calendar_bound = any(
                value is not None
                for value in (
                    constraint.lower_bound_days,
                    constraint.upper_bound_days,
                    constraint.lower_bound,
                    constraint.upper_bound,
                )
            )
            if constraint.direction == TimeDirection.ON:
                _reject_semantic_boundary(
                    "半衰期与固定窗口择长规则不得压缩为当日 ON",
                    code="TIME_HALF_LIFE_ON_INVALID",
                    entity_id=anchor.time_constraint_id,
                    strict=strict,
                )
            if constraint.half_life_multiplier is None or not has_calendar_bound:
                _reject_semantic_boundary(
                    "半衰期与固定窗口择长规则必须同时保留两类窗口",
                    code="TIME_HALF_LIFE_WINDOW_INCOMPLETE",
                    entity_id=anchor.time_constraint_id,
                    strict=strict,
                )


def _validate_row_semantic_boundaries(row: ProtocolControlMatrixRow) -> None:
    _validate_atomic_boundaries(row, strict=False)
    _validate_dnf_logic_boundaries(row, strict=False)
    _validate_trigger_branch_boundaries(row, strict=False)
    _validate_exception_scope_boundaries(row, strict=False)
    _validate_source_logic_boundaries(row, strict=False)
    _validate_evidence_boundaries(row, strict=False)
    _validate_review_node_boundaries(row, strict=False)
    _validate_time_boundaries(row, strict=False)


class ProtocolControlMatrix(_MatrixModel):
    """Complete JSON contract for one selected-phase comparison matrix."""

    schema_version: Literal[CONTROL_MATRIX_CONTRACT_VERSION] = (
        CONTROL_MATRIX_CONTRACT_VERSION
    )
    matrix_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    protocol_document_sha256: str = Field(pattern=_SHA256)
    selected_phase: StudyPhase
    snapshot_id: str = Field(min_length=1)
    coverage_manifest_id: str = Field(
        min_length=1,
        validation_alias=AliasChoices("coverage_manifest_id", "manifest_id"),
    )
    title_zh: str = Field(
        min_length=1,
        validation_alias=AliasChoices("title_zh", "title"),
    )
    rows: list[ProtocolControlMatrixRow] = Field(min_length=1)
    claims_complete: bool = False

    @model_validator(mode="after")
    def validate_matrix(self) -> "ProtocolControlMatrix":
        if self.selected_phase == StudyPhase.OTHER:
            raise ValueError("矩阵必须绑定已确认的 II/III 或无缝期别")
        if not self.title_zh.strip():
            raise ValueError("矩阵中文标题不得为空")
        row_ids = [item.matrix_row_id for item in self.rows]
        ordinals = [item.display_ordinal for item in self.rows]
        _nonempty_unique(row_ids, "矩阵行身份")
        for row in self.rows:
            _validate_row_identity_closure(row)
        _nonempty_unique(
            [item.source_identity for item in self.rows],
            "矩阵来源身份",
        )
        if len(ordinals) != len(set(ordinals)):
            raise ValueError("矩阵行 display_ordinal 必须唯一")
        if ordinals != sorted(ordinals):
            raise ValueError("矩阵行必须按 display_ordinal 升序排列")
        _validate_workflow_basis_rows(self.rows)
        if self.claims_complete and any(
            item.source_candidate_id is not None for item in self.rows
        ):
            raise ValueError("使用来源候选身份的矩阵行不得声明 claims_complete=true")
        if any(
            item.phase_disposition
            in {
                MatrixPhaseDisposition.OPPOSITE_PHASE_APPLICABLE,
                MatrixPhaseDisposition.UNRESOLVED,
            }
            for item in self.rows
        ) and self.claims_complete:
            raise ValueError("对侧期别或未决矩阵行不得声明完整可发布")
        return self


def _validate_workflow_basis_rows(
    rows: Sequence[ProtocolControlMatrixRow],
    *,
    strict: bool = False,
) -> None:
    """Validate cross-row workflow evidence without merging source anchors."""

    row_by_id = {row.matrix_row_id: row for row in rows}
    for row in rows:
        for node in row.review_nodes:
            basis_id = node.workflow_basis_row_id
            if basis_id is None:
                continue
            if basis_id == row.matrix_row_id:
                _reject_semantic_boundary(
                    "审核节点流程依据不得引用自身",
                    code="REVIEW_NODE_BASIS_SELF",
                    entity_id=basis_id,
                    strict=strict,
                )
            basis_row = row_by_id.get(basis_id)
            if basis_row is None:
                _reject_semantic_boundary(
                    "审核节点流程依据必须存在于同一矩阵",
                    code="REVIEW_NODE_BASIS_UNKNOWN",
                    entity_id=basis_id,
                    strict=strict,
                )
            if basis_row.source_kind != ProtocolControlMatrixSourceKind.REQUIRED_PROCEDURE:
                _reject_semantic_boundary(
                    "审核节点流程依据必须是同一矩阵中的流程必做行",
                    code="REVIEW_NODE_BASIS_KIND_INVALID",
                    entity_id=basis_id,
                    strict=strict,
                )
            matching_nodes = [
                candidate
                for candidate in basis_row.review_nodes
                if candidate.review_stage == node.review_stage
            ]
            if not matching_nodes:
                _reject_semantic_boundary(
                    "审核节点流程依据行必须包含相同审核阶段",
                    code="REVIEW_NODE_BASIS_STAGE_MISSING",
                    entity_id=basis_id,
                    strict=strict,
                )
            stage_cues = _STAGE_SOURCE_CUES[node.review_stage]
            if not any(
                candidate.source_anchor_ids
                and any(
                    cue in _row_source_text(basis_row, candidate.source_anchor_ids)
                    for cue in stage_cues
                )
                for candidate in matching_nodes
            ):
                _reject_semantic_boundary(
                    "审核节点流程依据行的来源锚点必须支持相同审核阶段",
                    code="REVIEW_NODE_BASIS_STAGE_SOURCE_MISSING",
                    entity_id=basis_id,
                    strict=strict,
                )


def _row_identity(row: ProtocolControlMatrixRow) -> tuple[str, str, str | None]:
    return (_value(row.source_kind), row.source_identity, row.official_child_code)


def _normalise_id_values(values: object, *, attr_names: Sequence[str]) -> set[str]:
    if values is None:
        return set()
    if isinstance(values, Mapping):
        items = list(values.keys())
    elif isinstance(values, (str, bytes)):
        items = [values]
    elif isinstance(values, Iterable):
        items = list(values)
    else:
        items = [values]
    result: set[str] = set()
    for item in items:
        if isinstance(item, str):
            result.add(item)
            continue
        for attr in attr_names:
            value = getattr(item, attr, None)
            if isinstance(value, str) and value.strip():
                result.add(value)
                break
    return result


def _flatten_rules(values: object) -> list[object]:
    if values is None:
        return []
    if hasattr(values, "official_rules"):
        return list(getattr(values, "official_rules"))
    if hasattr(values, "rules") and not isinstance(values, Sequence):
        return list(getattr(values, "rules"))
    if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
        return list(values)
    return [values]


class ProtocolControlMatrixError(ValueError):
    """A deterministic matrix rejection with a stable code."""

    def __init__(self, code: str, message: str, *, entity_id: str | None = None):
        self.code = code
        self.entity_id = entity_id
        suffix = f" [{entity_id}]" if entity_id else ""
        super().__init__(f"{code}{suffix}: {message}")


class ProtocolControlMatrixValidationReport:
    """Non-throwing diagnostic equivalent of the strict validator."""

    def __init__(
        self,
        accepted: bool,
        issues: tuple[tuple[str, str, str | None], ...] = (),
    ) -> None:
        self.accepted = accepted
        self.contract_version = CONTROL_MATRIX_CONTRACT_VERSION
        self.issues = issues


ProtocolControlMatrixReport = ProtocolControlMatrixValidationReport


def _fail(code: str, message: str, *, entity_id: str | None = None) -> None:
    raise ProtocolControlMatrixError(code, message, entity_id=entity_id)


def _manifest_units(
    coverage_manifest: ProtocolSectionCoverageManifest,
) -> dict[str, ProtocolStructureUnit]:
    if not isinstance(coverage_manifest, ProtocolSectionCoverageManifest):
        _fail("MANIFEST_TYPE_INVALID", "必须提供 ProtocolSectionCoverageManifest")
    units: dict[str, ProtocolStructureUnit] = {}
    for unit in coverage_manifest.units:
        if unit.structure_unit_id in units:
            _fail("MANIFEST_UNIT_DUPLICATE", "全文结构单元身份重复", entity_id=unit.structure_unit_id)
        units[unit.structure_unit_id] = unit
    if not units:
        _fail("MANIFEST_EMPTY", "全文覆盖清单不能为空")
    return units


def _validate_row_identity_closure(row: ProtocolControlMatrixRow) -> None:
    expected_row_id = stable_protocol_control_matrix_row_id(
        row.source_kind,
        row.source_identity,
        row.official_child_code,
    )
    if row.matrix_row_id != expected_row_id:
        _fail(
            "MATRIX_ROW_ID_DERIVED_MISMATCH",
            "矩阵行身份必须等于来源类别、来源身份和官方子编号的系统派生值",
            entity_id=row.matrix_row_id,
        )
    expected_ordinals = list(range(len(row.source_anchors)))
    actual_ordinals = [anchor.source_ordinal for anchor in row.source_anchors]
    if actual_ordinals != expected_ordinals:
        _fail(
            "SOURCE_ANCHOR_ORDINAL_MISMATCH",
            "来源锚点必须按稳定序位连续排列，行内顺序不可静默调换",
            entity_id=row.matrix_row_id,
        )
    for anchor in row.source_anchors:
        expected_anchor_id = stable_protocol_control_matrix_anchor_id(
            row.matrix_row_id, anchor.source_ordinal
        )
        if anchor.source_anchor_id != expected_anchor_id:
            _fail(
                "SOURCE_ANCHOR_ID_DERIVED_MISMATCH",
                "来源锚点身份必须等于行身份和稳定序位的系统派生值",
                entity_id=anchor.source_anchor_id,
            )


def _validate_row_source_closure(
    row: ProtocolControlMatrixRow,
    unit_by_id: Mapping[str, ProtocolStructureUnit],
) -> None:
    expected_spans: set[str] = set()
    source_orders: list[int] = []
    for anchor in row.source_anchors:
        unit = unit_by_id.get(anchor.structure_unit_id)
        if unit is None:
            _fail("SOURCE_UNIT_UNKNOWN", "矩阵来源引用了冻结清单外结构单元", entity_id=anchor.structure_unit_id)
        source_orders.append(unit.source_order)
        if anchor.source_ref != unit.source_ref:
            _fail("SOURCE_REF_MISMATCH", "矩阵来源 source_ref 与冻结结构单元不一致", entity_id=anchor.source_anchor_id)
        if anchor.heading_path_zh != unit.heading_path:
            _fail("SOURCE_HEADING_PATH_MISMATCH", "矩阵来源标题路径与冻结结构单元不一致", entity_id=anchor.source_anchor_id)
        unit_spans = set(unit.source_span_ids)
        if not set(anchor.source_span_ids) <= unit_spans:
            _fail("SOURCE_SPAN_ESCAPE", "矩阵来源片段越出冻结结构单元来源闭包", entity_id=anchor.source_anchor_id)
        if anchor.verbatim_excerpt not in unit.excerpt:
            _fail("VERBATIM_EXCERPT_NOT_FOUND", "矩阵逐字摘录无法在冻结结构单元中回源", entity_id=anchor.source_anchor_id)
        expected_spans.update(unit_spans)
    if source_orders != sorted(source_orders):
        _fail(
            "SOURCE_ANCHOR_ORDER_MISMATCH",
            "来源锚点顺序必须与冻结结构单元的稳定来源顺序一致",
            entity_id=row.matrix_row_id,
        )
    if set(row.source_span_ids) != expected_spans:
        _fail("SOURCE_UNIT_CLOSURE_INCOMPLETE", "矩阵来源片段未闭合到全部冻结源单元", entity_id=row.matrix_row_id)


def _validate_phase(
    matrix: ProtocolControlMatrix,
    row: ProtocolControlMatrixRow,
    unit_by_id: Mapping[str, ProtocolStructureUnit],
) -> None:
    if row.phase_disposition in {
        MatrixPhaseDisposition.OPPOSITE_PHASE_APPLICABLE,
        MatrixPhaseDisposition.UNRESOLVED,
    }:
        _fail("PHASE_DISPOSITION_NOT_PUBLISHABLE", "对侧期别或未决期别不得进入选定期别矩阵", entity_id=row.matrix_row_id)
    opposite = {
        StudyPhase.PHASE_II: StudyPhase.PHASE_III,
        StudyPhase.PHASE_III: StudyPhase.PHASE_II,
        StudyPhase.SEAMLESS_II_III: None,
    }[matrix.selected_phase]
    for unit_id in row.source_structure_unit_ids:
        unit = unit_by_id[unit_id]
        scopes = set(unit.phase_scopes)
        if PhaseScope.MIXED in scopes:
            _fail("PHASE_MIXED_REJECTED", "混合期别来源不得进入矩阵", entity_id=unit_id)
        if PhaseScope.UNKNOWN in scopes:
            _fail("PHASE_UNRESOLVED", "未确定期别来源不得进入矩阵", entity_id=unit_id)
        if PhaseScope.SEAMLESS_CANDIDATE in scopes and matrix.selected_phase != StudyPhase.SEAMLESS_II_III:
            _fail("PHASE_SEAMLESS_UNRESOLVED", "无缝候选来源不得投影到独立 II/III 期", entity_id=unit_id)
        selected_scope = {
            StudyPhase.PHASE_II: PhaseScope.PHASE_II,
            StudyPhase.PHASE_III: PhaseScope.PHASE_III,
            StudyPhase.SEAMLESS_II_III: PhaseScope.SEAMLESS_CANDIDATE,
        }[matrix.selected_phase]
        if row.phase_disposition == MatrixPhaseDisposition.CROSS_PHASE_SHARED:
            if PhaseScope.SHARED not in scopes:
                _fail("PHASE_SHARED_SOURCE_MISSING", "跨期共享矩阵行必须有共享期别来源依据", entity_id=row.matrix_row_id)
        elif selected_scope not in scopes and PhaseScope.SHARED not in scopes:
            if opposite is not None and opposite in {
                StudyPhase.PHASE_II,
                StudyPhase.PHASE_III,
            } and {
                PhaseScope.PHASE_II,
                PhaseScope.PHASE_III,
            }.intersection(scopes):
                _fail("PHASE_OPPOSITE_SOURCE", "矩阵行来源只属于对侧期别", entity_id=unit_id)
            _fail("PHASE_SELECTED_SOURCE_MISSING", "矩阵行来源没有选定期别适用依据", entity_id=unit_id)


def _validate_time_alignment(row: ProtocolControlMatrixRow) -> None:
    for anchor in row.time_anchors:
        if anchor.time_constraint.anchor_type == AnchorType.SCREENING_DATE and any(
            cue in anchor.anchor_label_zh
            for cue in ("随机", "基线", "首次给药", "首次用药")
        ):
            _fail(
                "TIME_ANCHOR_GUESSED_FROM_SCREENING",
                "方案命名的随机/基线/首次给药锚点不得改写为筛选日期",
                entity_id=anchor.time_constraint_id,
            )
    _validate_time_boundaries(row, strict=True)
    for anchor in row.time_anchors:
        if anchor.time_constraint.direction not in {
            TimeDirection.BEFORE,
            TimeDirection.AFTER,
            TimeDirection.ON,
        }:
            _fail(
                "TIME_DIRECTION_UNSUPPORTED",
                "时间方向不能被确定性矩阵表达",
                entity_id=anchor.time_constraint_id,
            )


def _manifest_disposition(
    coverage_manifest: ProtocolSectionCoverageManifest,
    unit_id: str,
    *,
    missing_code: str,
) -> object:
    disposition = next(
        (
            item
            for item in coverage_manifest.dispositions
            if item.structure_unit_id == unit_id
        ),
        None,
    )
    if disposition is None:
        _fail(missing_code, "矩阵来源结构单元没有全文清单处置", entity_id=unit_id)
    return disposition


def _validate_row_source_identity_contract(row: ProtocolControlMatrixRow) -> None:
    """Re-check source identity exclusivity at the strict validator boundary.

    ``model_copy``/``model_construct`` are useful for adversarial fixtures and
    can bypass Pydantic's row validator; the publication gate must not trust
    those bypasses.
    """

    candidate = row.source_candidate_id
    if candidate is not None and (
        not _is_candidate_identity(candidate)
    ):
        _fail(
            "CANDIDATE_ID_INVALID",
            "来源候选身份必须使用稳定的 candidate 前缀且不得伪装正式身份",
            entity_id=str(candidate),
        )
    if row.required_procedure_catalog_item_id is not None and _CANDIDATE_ID.fullmatch(
        row.required_procedure_catalog_item_id
    ):
        _fail(
            "FORMAL_PROCEDURE_ID_CANDIDATE_FORBIDDEN",
            "正式流程目录身份不得使用流程候选身份",
            entity_id=row.required_procedure_catalog_item_id,
        )
    if row.source_kind == ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY:
        if any(
            value is not None
            for value in (
                row.required_procedure_catalog_item_id,
                row.protocol_control_id,
                candidate,
            )
        ):
            _fail(
                "SOURCE_IDENTITY_MUTUAL_EXCLUSION",
                "官方入排行不得携带流程、其他控制或候选身份",
                entity_id=row.matrix_row_id,
            )
        for official_code in filter(
            None, (row.official_child_code, row.official_parent_code)
        ):
            if _is_mechanical_official_title(row.title_zh, official_code):
                _fail(
                    "OFFICIAL_TITLE_MECHANICAL",
                    "官方矩阵标题不得仅机械重复编号和泛化词",
                    entity_id=row.matrix_row_id,
                )
    elif row.source_kind == ProtocolControlMatrixSourceKind.REQUIRED_PROCEDURE:
        if sum(
            value is not None
            for value in (row.required_procedure_catalog_item_id, candidate)
        ) != 1:
            _fail(
                "SOURCE_IDENTITY_MUTUAL_EXCLUSION",
                "流程必做矩阵行必须且只能提供正式流程目录身份或来源候选身份",
                entity_id=row.matrix_row_id,
            )
        if any(
            value is not None
            for value in (
                row.official_parent_code,
                row.official_child_code,
                row.protocol_control_id,
            )
        ):
            _fail(
                "SOURCE_IDENTITY_MUTUAL_EXCLUSION",
                "流程必做行不得伪造官方或其他控制身份",
                entity_id=row.matrix_row_id,
            )
    elif row.source_kind == ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL:
        if sum(value is not None for value in (row.protocol_control_id, candidate)) != 1:
            _fail(
                "SOURCE_IDENTITY_MUTUAL_EXCLUSION",
                "其他章节控制矩阵行必须且只能提供正式控制身份或来源候选身份",
                entity_id=row.matrix_row_id,
            )
        if any(
            value is not None
            for value in (
                row.official_parent_code,
                row.official_child_code,
                row.required_procedure_catalog_item_id,
            )
        ):
            _fail(
                "SOURCE_IDENTITY_MUTUAL_EXCLUSION",
                "其他章节控制行不得携带官方或流程身份",
                entity_id=row.matrix_row_id,
            )


def _validate_candidate_disposition(
    row: ProtocolControlMatrixRow,
    disposition: object,
) -> None:
    """Close a candidate row to the existing disposition contract.

    Procedure candidates close through the explicit
    ``linked_procedure_candidate_id`` field while the formal procedure link
    remains empty.  Other-section candidates use the existing explicit
    ``linked_control_candidate_id`` field.
    """

    if row.source_kind == ProtocolControlMatrixSourceKind.REQUIRED_PROCEDURE:
        if getattr(disposition, "disposition", None) != StructureUnitDispositionKind.REQUIRED_PROCEDURE:
            _fail(
                "CANDIDATE_DISPOSITION_MISMATCH",
                "候选流程行的冻结处置必须明确为流程必做",
                entity_id=row.source_candidate_id,
            )
        formal_link = getattr(disposition, "linked_procedure_catalog_item_id", None)
        if formal_link is not None:
            _fail(
                "CANDIDATE_FORMAL_LINK_FORBIDDEN",
                "候选流程行必须保持正式流程目录链接为空，不得把候选身份写入正式流程链接",
                entity_id=row.source_candidate_id,
            )
        if getattr(disposition, "linked_procedure_candidate_id", None) != row.source_candidate_id:
            _fail(
                "CANDIDATE_DISPOSITION_MISMATCH",
                "候选流程行必须与冻结清单流程候选身份完全闭合",
                entity_id=row.source_candidate_id,
            )
        if getattr(disposition, "linked_official_code", None) is not None:
            _fail(
                "CANDIDATE_DISPOSITION_MISMATCH",
                "候选流程行不得携带官方编号处置",
                entity_id=row.source_candidate_id,
            )
        if getattr(disposition, "linked_control_candidate_id", None) is not None:
            _fail(
                "CANDIDATE_DISPOSITION_MISMATCH",
                "流程候选不得借用其他章节候选链接字段",
                entity_id=row.source_candidate_id,
            )
        return

    if getattr(disposition, "disposition", None) != StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE:
        _fail(
            "CANDIDATE_DISPOSITION_MISMATCH",
            "候选其他章节行的冻结处置必须明确为其他控制候选",
            entity_id=row.source_candidate_id,
        )
    if getattr(disposition, "linked_control_candidate_id", None) != row.source_candidate_id:
        _fail(
            "CANDIDATE_DISPOSITION_MISMATCH",
            "候选其他章节行必须与冻结清单候选身份闭合",
            entity_id=row.source_candidate_id,
        )
    if any(
        getattr(disposition, field_name, None) is not None
        for field_name in ("linked_official_code", "linked_procedure_catalog_item_id")
    ):
        _fail(
            "CANDIDATE_DISPOSITION_MISMATCH",
            "候选其他章节行不得携带官方或正式流程链接",
            entity_id=row.source_candidate_id,
        )


def validate_protocol_control_matrix(
    matrix: ProtocolControlMatrix,
    coverage_manifest: ProtocolSectionCoverageManifest | None = None,
    *,
    official_rules: object = (),
    official_parent_codes: Sequence[str] = (),
    official_child_codes: Sequence[str] = (),
    required_procedure_ids: Sequence[str] = (),
    procedure_catalog: object = (),
    published_controls: Sequence[ProtocolReviewControl] = (),
    protocol_controls: Sequence[ProtocolReviewControl] = (),
    workflow_stage_ids: Sequence[str] = (),
    require_all_source_kinds: bool = False,
) -> ProtocolControlMatrix:
    """Strictly validate a matrix against frozen source and existing identities.

    ``coverage_manifest`` is required for acceptance because Pydantic can only
    validate the shape of a source anchor; exact excerpts and span closure
    require the frozen source unit payload.  Existing official/procedure/
    published-control collections are optional identity indexes.  When passed,
    they are checked for membership and scope, never replaced by the matrix.
    """

    if not isinstance(matrix, ProtocolControlMatrix):
        _fail("MATRIX_TYPE_INVALID", "必须提供 ProtocolControlMatrix")
    if coverage_manifest is None:
        _fail("SOURCE_MANIFEST_REQUIRED", "矩阵验收必须绑定冻结 ProtocolSectionCoverageManifest")
    unit_by_id = _manifest_units(coverage_manifest)
    if matrix.coverage_manifest_id != coverage_manifest.manifest_id:
        _fail("MANIFEST_ID_MISMATCH", "矩阵与全文覆盖清单身份不一致")
    if matrix.protocol_version_id != coverage_manifest.protocol_version_id:
        _fail("PROTOCOL_VERSION_MISMATCH", "矩阵与全文覆盖清单方案版本不一致")
    if matrix.protocol_document_sha256 != coverage_manifest.protocol_document_sha256:
        _fail("PROTOCOL_HASH_MISMATCH", "矩阵与全文覆盖清单文档哈希不一致")
    if matrix.selected_phase != coverage_manifest.study_phase:
        _fail("STUDY_PHASE_MISMATCH", "矩阵与全文覆盖清单选定期别不一致")

    official_codes = _normalise_id_values(
        official_parent_codes,
        attr_names=("official_code",),
    )
    child_codes = _normalise_id_values(
        official_child_codes,
        attr_names=("display_code", "official_code"),
    )
    for item in _flatten_rules(official_rules):
        code = getattr(item, "official_code", None)
        if isinstance(code, str):
            official_codes.add(code)
        for component in getattr(item, "components", ()):
            display_code = getattr(component, "display_code", None)
            if isinstance(display_code, str) and display_code.strip():
                child_codes.add(display_code)
    procedure_ids = _normalise_id_values(
        required_procedure_ids,
        attr_names=("catalog_item_id", "procedure_catalog_item_id", "item_id"),
    )
    procedure_catalog_items = (
        getattr(procedure_catalog, "items", procedure_catalog)
        if procedure_catalog is not None
        else ()
    )
    procedure_ids.update(
        _normalise_id_values(
            procedure_catalog_items,
            attr_names=("catalog_item_id", "procedure_catalog_item_id", "item_id"),
        )
    )
    published_control_items = (
        getattr(published_controls, "controls", published_controls)
        if published_controls is not None
        else ()
    )
    protocol_control_items = (
        getattr(protocol_controls, "controls", protocol_controls)
        if protocol_controls is not None
        else ()
    )
    controls = list(published_control_items or ()) + list(protocol_control_items or ())
    control_by_id: dict[str, ProtocolReviewControl] = {}
    for control in controls:
        if control.protocol_control_id in control_by_id:
            _fail("CONTROL_ID_DUPLICATE", "已有 ProtocolReviewControl 身份重复", entity_id=control.protocol_control_id)
        control_by_id[control.protocol_control_id] = control
    known_stage_ids = _normalise_id_values(
        workflow_stage_ids,
        attr_names=("workflow_stage_id", "stage_id"),
    )
    for row in matrix.rows:
        _validate_row_source_identity_contract(row)
        _validate_row_identity_closure(row)
        _validate_row_source_closure(row, unit_by_id)
        _validate_phase(matrix, row, unit_by_id)
        _validate_time_alignment(row)
        _validate_atomic_boundaries(row, strict=True)
        _validate_dnf_logic_boundaries(row, strict=True)
        _validate_trigger_branch_boundaries(row, strict=True)
        _validate_exception_scope_boundaries(row, strict=True)
        _validate_source_logic_boundaries(row, strict=True)
        _validate_evidence_boundaries(row, strict=True)
        _validate_review_node_boundaries(row, strict=True)
        for node in row.review_nodes:
            if known_stage_ids and node.workflow_stage_id not in known_stage_ids:
                _fail("WORKFLOW_STAGE_UNKNOWN", "矩阵审核节点不在冻结流程节点目录中", entity_id=node.workflow_stage_id)

        if row.source_candidate_id is not None and matrix.claims_complete:
            _fail(
                "CANDIDATE_ID_NOT_COMPLETE",
                "使用来源候选身份的矩阵行不得声明 claims_complete=true",
                entity_id=row.source_candidate_id,
            )

        if row.source_kind == ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY:
            if official_codes and row.official_parent_code not in official_codes:
                _fail("OFFICIAL_PARENT_UNKNOWN", "矩阵官方父编号不在既有官方规则目录中", entity_id=row.official_parent_code)
            if child_codes and row.official_child_code is not None and row.official_child_code not in child_codes:
                _fail("OFFICIAL_CHILD_UNKNOWN", "矩阵官方子编号不在既有父规则组件目录中", entity_id=row.official_child_code)
            for unit_id in row.source_structure_unit_ids:
                disposition = _manifest_disposition(
                    coverage_manifest,
                    unit_id,
                    missing_code="OFFICIAL_DISPOSITION_MISSING",
                )
                if disposition.linked_official_code != row.official_parent_code:
                    _fail("OFFICIAL_DISPOSITION_MISMATCH", "官方行与全文清单 IN/EX 父编号处置不一致", entity_id=row.matrix_row_id)
        elif row.source_kind == ProtocolControlMatrixSourceKind.REQUIRED_PROCEDURE:
            if row.source_candidate_id is not None:
                for unit_id in row.source_structure_unit_ids:
                    disposition = _manifest_disposition(
                        coverage_manifest,
                        unit_id,
                        missing_code="PROCEDURE_DISPOSITION_MISSING",
                    )
                    _validate_candidate_disposition(row, disposition)
            else:
                if matrix.claims_complete and not procedure_ids:
                    _fail(
                        "PROCEDURE_AUTHORITY_REQUIRED",
                        "claims_complete=true 的正式流程行必须提供非空权威流程目录集合",
                        entity_id=row.required_procedure_catalog_item_id,
                    )
                if procedure_ids and row.required_procedure_catalog_item_id not in procedure_ids:
                    _fail("PROCEDURE_ID_UNKNOWN", "矩阵流程必做身份不在既有流程目录中", entity_id=row.required_procedure_catalog_item_id)
                for unit_id in row.source_structure_unit_ids:
                    disposition = _manifest_disposition(
                        coverage_manifest,
                        unit_id,
                        missing_code="PROCEDURE_DISPOSITION_MISSING",
                    )
                    if disposition.disposition != StructureUnitDispositionKind.REQUIRED_PROCEDURE:
                        _fail("PROCEDURE_DISPOSITION_MISMATCH", "流程行与全文清单流程必做处置不一致", entity_id=row.matrix_row_id)
                    if disposition.linked_procedure_candidate_id is not None:
                        _fail("PROCEDURE_DISPOSITION_CANDIDATE_MISMATCH", "正式流程行不得引用流程候选处置", entity_id=row.matrix_row_id)
                    if disposition.linked_procedure_catalog_item_id != row.required_procedure_catalog_item_id:
                        _fail("PROCEDURE_DISPOSITION_MISMATCH", "流程行与全文清单流程必做处置不一致", entity_id=row.matrix_row_id)
        else:
            if row.source_candidate_id is not None:
                for unit_id in row.source_structure_unit_ids:
                    disposition = _manifest_disposition(
                        coverage_manifest,
                        unit_id,
                        missing_code="OTHER_DISPOSITION_MISSING",
                    )
                    _validate_candidate_disposition(row, disposition)
            else:
                if matrix.claims_complete and not controls:
                    _fail(
                        "PROTOCOL_CONTROL_AUTHORITY_REQUIRED",
                        "claims_complete=true 的正式其他章节行必须提供非空已发布 ProtocolReviewControl 集合",
                        entity_id=row.protocol_control_id,
                    )
                control = control_by_id.get(row.protocol_control_id or "")
                if controls and control is None:
                    _fail("PROTOCOL_CONTROL_UNKNOWN", "其他章节矩阵行未绑定已有 ProtocolReviewControl", entity_id=row.protocol_control_id)
                if control is not None:
                    if control.protocol_version_id != matrix.protocol_version_id or control.study_phase != matrix.selected_phase:
                        _fail("PROTOCOL_CONTROL_SCOPE_MISMATCH", "矩阵其他控制与已有正式控制版本/期别不一致", entity_id=row.protocol_control_id)
                    if set(control.source_structure_unit_ids) != set(row.source_structure_unit_ids):
                        _fail("PROTOCOL_CONTROL_SOURCE_SCOPE_MISMATCH", "矩阵其他控制来源结构单元与已有正式控制不一致", entity_id=row.protocol_control_id)
                    if set(control.source_span_ids) != set(row.source_span_ids):
                        _fail("PROTOCOL_CONTROL_SOURCE_SPAN_MISMATCH", "矩阵其他控制来源片段与已有正式控制不一致", entity_id=row.protocol_control_id)

    _validate_workflow_basis_rows(matrix.rows, strict=True)

    if require_all_source_kinds:
        kinds = {item.source_kind for item in matrix.rows}
        missing = {
            ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY,
            ProtocolControlMatrixSourceKind.REQUIRED_PROCEDURE,
            ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
        } - kinds
        if missing:
            _fail("SOURCE_KIND_MISSING", "矩阵缺少三类并列来源：" + ",".join(sorted(item.value for item in missing)))

    row_by_id = {item.matrix_row_id: item for item in matrix.rows}
    for row in matrix.rows:
        relation_keys: set[tuple[str, str]] = set()
        for relation in row.cross_source_relations:
            if relation.target_row_id not in row_by_id:
                _fail("RELATION_TARGET_UNKNOWN", "跨章节关系目标不在同一矩阵中", entity_id=relation.relation_id)
            target = row_by_id[relation.target_row_id]
            key = (relation.kind.value, target.matrix_row_id)
            if key in relation_keys:
                _fail("RELATION_DUPLICATE", "矩阵跨章节关系不得重复", entity_id=relation.relation_id)
            relation_keys.add(key)
            if relation.kind == CrossSourceRelationKind.DUPLICATE_STATEMENT and target.source_identity == row.source_identity:
                _fail("RELATION_SELF_IDENTITY", "重复关系不能指向同一来源身份", entity_id=relation.relation_id)
            if relation.kind == CrossSourceRelationKind.SUBSTANTIVE_CONFLICT and relation.resolution_zh is None:
                _fail("UNRESOLVED_SUBSTANTIVE_CONFLICT", "未解决的实质冲突阻断矩阵验收", entity_id=relation.relation_id)

    if matrix.claims_complete:
        if not coverage_manifest.claims_full_coverage:
            _fail("MANIFEST_NOT_COMPLETE", "全文覆盖清单未声明完整，矩阵不得声明完整")
        if coverage_manifest.undisposed_structure_unit_ids:
            _fail("MANIFEST_UNDISPOSED", "存在未处置结构单元，矩阵不得声明完整")
    return matrix


def check_protocol_control_matrix(
    matrix: ProtocolControlMatrix,
    coverage_manifest: ProtocolSectionCoverageManifest | None = None,
    **kwargs: object,
) -> ProtocolControlMatrixValidationReport:
    try:
        validate_protocol_control_matrix(matrix, coverage_manifest, **kwargs)
    except ProtocolControlMatrixError as exc:
        return ProtocolControlMatrixValidationReport(
            accepted=False,
            issues=((exc.code, str(exc), exc.entity_id),),
        )
    return ProtocolControlMatrixValidationReport(accepted=True)


def build_protocol_control_matrix_json(matrix: ProtocolControlMatrix) -> str:
    """Return canonical JSON used as the machine-readable matrix artifact."""

    if not isinstance(matrix, ProtocolControlMatrix):
        raise TypeError("matrix 必须是 ProtocolControlMatrix")
    return json.dumps(
        matrix.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _zh(mapping: Mapping[object, str], value: object) -> str:
    return mapping.get(value, mapping.get(_value(value), str(value)))


def _markdown_optional(value: object | None, default: str = "未声明") -> str:
    if value is None or not str(value).strip():
        return default
    return _markdown_cell(value)


def _time_quantity(value: object | None) -> str:
    if value is None:
        return "未声明"
    return f"{value.value}{_zh(_TIME_UNIT_ZH, value.unit)}"


def _time_constraint_text(constraint: TimeConstraint) -> str:
    parts = [
        f"锚点={_zh(_ANCHOR_TYPE_ZH, constraint.anchor_type)}",
        f"方向={_zh(_TIME_DIRECTION_ZH, constraint.direction)}",
    ]
    if constraint.lower_bound_days is not None:
        label = "至少" if constraint.lower_bound_inclusive else "超过"
        parts.append(f"{label}{constraint.lower_bound_days}日")
    if constraint.lower_bound is not None:
        label = "至少" if constraint.lower_bound_inclusive else "超过"
        parts.append(f"{label}{_time_quantity(constraint.lower_bound)}")
    if constraint.upper_bound_days is not None:
        label = "不超过" if constraint.upper_bound_inclusive else "少于"
        parts.append(f"{label}{constraint.upper_bound_days}日")
    if constraint.upper_bound is not None:
        label = "不超过" if constraint.upper_bound_inclusive else "少于"
        parts.append(f"{label}{_time_quantity(constraint.upper_bound)}")
    if constraint.half_life_multiplier is not None:
        parts.append(f"半衰期倍数={constraint.half_life_multiplier}")
    parts.append(f"允许部分日期={'是' if constraint.allow_partial_date else '否'}")
    return "；".join(parts)


def _dnf_text(
    expression: MatrixDnf | None,
    labels: Mapping[str, str] | None = None,
) -> str:
    if expression is None:
        return "未声明"
    labels = labels or {}
    groups: list[str] = []
    for group in expression.groups:
        atom_text = _dnf_group_text(group, labels)
        text = f"（{atom_text}）"
        if group.logic_basis_zh:
            text += f"（依据：{_markdown_cell(group.logic_basis_zh)}）"
        groups.append(text)
    return " 或 ".join(groups)


def _dnf_group_text(
    group: MatrixDnfGroup,
    labels: Mapping[str, str],
) -> str:
    positive = [
        _markdown_cell(labels.get(item, "方案原文条件")) for item in group.atom_ids
    ]
    negative = [
        f"非（{_markdown_cell(labels.get(item, '方案原文条件'))}）"
        for item in group.negated_atom_ids
    ]
    return " 且 ".join((*positive, *negative))


def _markdown_table_cells(line: str) -> list[str]:
    return [
        item.strip().replace("\\|", "|")
        for item in re.split(r"(?<!\\)\|", line.strip()[1:-1])
    ]


def _visible_row_labels(matrix: ProtocolControlMatrix) -> dict[str, str]:
    counters: dict[ProtocolControlMatrixSourceKind, int] = {}
    labels: dict[str, str] = {}
    for row in matrix.rows:
        if row.source_kind == ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY:
            labels[row.matrix_row_id] = row.official_child_code or row.official_parent_code or "官方入排"
            continue
        ordinal = counters.get(row.source_kind, 0) + 1
        counters[row.source_kind] = ordinal
        prefix = (
            "流程必做"
            if row.source_kind == ProtocolControlMatrixSourceKind.REQUIRED_PROCEDURE
            else "方案控制"
        )
        labels[row.matrix_row_id] = f"{prefix} {ordinal:02d}"
    return labels


def _human_source_location(source_ref: str) -> str:
    body_match = re.fullmatch(r"body\.p(\d+)", source_ref)
    if body_match:
        return f"正文第 {int(body_match.group(1)) + 1} 段"
    if source_ref.startswith("table"):
        return "方案表格中的对应位置"
    if source_ref.startswith("page"):
        return "方案页面中的对应位置"
    return "方案原文对应位置（见标题路径）"


def _matrix_internal_values(matrix: ProtocolControlMatrix) -> set[str]:
    values = {
        matrix.matrix_id,
        matrix.protocol_version_id,
        matrix.snapshot_id,
        matrix.coverage_manifest_id,
    }
    for row in matrix.rows:
        values.update(
            value
            for value in (
                row.matrix_row_id,
                row.required_procedure_catalog_item_id,
                row.protocol_control_id,
                row.source_candidate_id,
            )
            if value
        )
        for anchor in row.source_anchors:
            values.update(
                {
                    anchor.source_anchor_id,
                    anchor.structure_unit_id,
                    anchor.source_ref,
                    *anchor.source_span_ids,
                }
            )
        for atom in row.condition_atoms:
            values.add(atom.atom_id)
            if atom.time_constraint_id:
                values.add(atom.time_constraint_id)
            values.update(atom.source_anchor_ids)
        for obligation in row.obligations:
            values.add(obligation.obligation_id)
            if obligation.conjunction_group_id:
                values.add(obligation.conjunction_group_id)
            if obligation.time_constraint_id:
                values.add(obligation.time_constraint_id)
            values.update(obligation.source_anchor_ids)
        for expression in (
            row.applicability_expression,
            row.trigger_expression,
            row.obligation_expression,
            row.exception_expression,
        ):
            if expression is not None:
                for group in expression.groups:
                    values.update(group.source_anchor_ids)
                    values.update(group.atom_ids)
                    values.update(group.negated_atom_ids)
                    if group.trigger_branch_id:
                        values.add(group.trigger_branch_id)
                    values.update(group.waives_trigger_branch_ids)
        for time_anchor in row.time_anchors:
            values.add(time_anchor.time_constraint_id)
            values.update(time_anchor.source_anchor_ids)
        for node in row.review_nodes:
            values.add(node.workflow_stage_id)
            if node.workflow_basis_row_id:
                values.add(node.workflow_basis_row_id)
            values.update(node.source_anchor_ids)
        for evidence in row.minimum_evidence:
            values.add(evidence.evidence_id)
            values.add(evidence.due_workflow_stage_id)
            values.update(evidence.source_anchor_ids)
            if evidence.validity_time_constraint_id:
                values.add(evidence.validity_time_constraint_id)
        for relation in row.cross_source_relations:
            values.update(
                value
                for value in (
                    relation.relation_id,
                    relation.target_row_id,
                    relation.shared_assessment_identity,
                )
                if value
            )
            values.update(relation.source_anchor_ids)
    return {value for value in values if value}


def _review_node_marker(node: MatrixReviewNode) -> dict[str, object]:
    return {
        "workflow_stage_id": node.workflow_stage_id,
        "review_stage": node.review_stage.value,
        "role": node.role.value,
        "stage_ordinal": node.stage_ordinal,
        "node_label_zh": node.node_label_zh,
        "source_anchor_ids": list(node.source_anchor_ids),
        "workflow_basis_row_id": node.workflow_basis_row_id,
    }


def _dnf_marker(expression: MatrixDnf | None) -> list[dict[str, object]] | None:
    if expression is None:
        return None
    return [
        {
            "atom_ids": list(group.atom_ids),
            "negated_atom_ids": list(group.negated_atom_ids),
            "trigger_branch_id": group.trigger_branch_id,
            "waives_trigger_branch_ids": list(group.waives_trigger_branch_ids),
            "logic_basis_zh": group.logic_basis_zh,
            "source_anchor_ids": list(group.source_anchor_ids),
        }
        for group in expression.groups
    ]


def render_protocol_control_matrix_markdown(matrix: ProtocolControlMatrix) -> str:
    """Render a Chinese, row-by-row clinical-monitor review artifact."""

    if not isinstance(matrix, ProtocolControlMatrix):
        raise TypeError("matrix 必须是 ProtocolControlMatrix")
    _validate_workflow_basis_rows(matrix.rows)
    for row in matrix.rows:
        _validate_trigger_branch_boundaries(row, strict=False)
        _validate_exception_scope_boundaries(row, strict=False)
    visible_labels = _visible_row_labels(matrix)
    row_by_id = {row.matrix_row_id: row for row in matrix.rows}
    lines = [
        f"# {_markdown_cell(matrix.title_zh)}",
        "",
        "<!-- protocol-control-matrix: "
        + json.dumps(
            {
                "matrix_id": matrix.matrix_id,
                "schema_version": matrix.schema_version,
                "protocol_version_id": matrix.protocol_version_id,
                "selected_phase": matrix.selected_phase.value,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + " -->",
        "",
        "## 审阅索引",
        "",
        "| 审阅标签 | 来源类别 | 控制标题 | 本项目适用性 |",
        "|---|---|---|---|",
    ]
    for row in matrix.rows:
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    visible_labels[row.matrix_row_id],
                    _zh(_SOURCE_KIND_ZH, row.source_kind),
                    row.title_zh,
                    _zh(_PHASE_DISPOSITION_VISIBLE_ZH, row.phase_disposition),
                )
            )
            + " |"
        )
    lines.extend(("", "---", ""))

    for row in matrix.rows:
        marker = {
            "row_id": row.matrix_row_id,
            "source_kind": row.source_kind.value,
            "source_identity": row.source_identity,
            "source_candidate_id": row.source_candidate_id,
            "official_child_code": row.official_child_code,
            "review_nodes": [_review_node_marker(node) for node in row.review_nodes],
            "trigger_expression": _dnf_marker(row.trigger_expression),
            "exception_expression": _dnf_marker(row.exception_expression),
        }
        condition_labels = {atom.atom_id: atom.statement_zh for atom in row.condition_atoms}
        obligation_labels = {
            obligation.obligation_id: obligation.statement_zh
            for obligation in row.obligations
        }
        dnf_labels = {**condition_labels, **obligation_labels}
        trigger_branch_labels = {
            group.trigger_branch_id: _dnf_group_text(group, condition_labels)
            for group in (row.trigger_expression.groups if row.trigger_expression else [])
            if group.trigger_branch_id is not None
        }
        time_labels = {
            anchor.time_constraint_id: anchor.anchor_label_zh
            for anchor in row.time_anchors
        }
        node_labels = {
            node.workflow_stage_id: node.node_label_zh for node in row.review_nodes
        }
        lines.extend(
            (
                f"## {visible_labels[row.matrix_row_id]}：{_markdown_cell(row.title_zh)}",
                "",
                "<!-- protocol-control-matrix-row: "
                + json.dumps(marker, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + " -->",
                "",
                "### 来源与期别",
                "",
                f"- 审阅标签：{_markdown_cell(visible_labels[row.matrix_row_id])}",
                f"- 来源类别：{_zh(_SOURCE_KIND_ZH, row.source_kind)}",
                f"- 官方父编号：{_markdown_optional(row.official_parent_code, '不适用')}",
                f"- 官方子编号：{_markdown_optional(row.official_child_code, '不适用')}",
                f"- 本项目适用性：{_zh(_PHASE_DISPOSITION_VISIBLE_ZH, row.phase_disposition)}",
                "",
                "### 控制内容",
                "",
                f"- 做什么：{_markdown_optional(row.required_action_zh, '方案未规定该类要求')}",
                f"- 达标条件：{_markdown_optional(row.attainment_criteria_zh, '方案未规定该类要求')}",
                f"- 禁止事项：{_markdown_optional(row.prohibition_zh, '方案未规定该类要求')}",
                f"- 适用人群：{_markdown_cell(row.applicable_population_zh)}",
                f"- 触发条件：{_markdown_optional(row.trigger_condition_zh)}",
                "",
                "### 审核节点",
                "",
                "| 节点 | 阶段 | 作用 | 顺序 |",
                "|---|---|---|---:|",
            )
        )
        for node in row.review_nodes:
            lines.append(
                "| "
                + " | ".join(
                    _markdown_cell(value)
                    for value in (
                        node.node_label_zh,
                        _zh(_REVIEW_STAGE_ZH, node.review_stage),
                        _zh(_REVIEW_ROLE_ZH, node.role),
                        node.stage_ordinal,
                    )
                )
                + " |"
            )
        for node in row.review_nodes:
            if node.workflow_basis_row_id is None:
                basis_text = "本行直接来源闭包"
            else:
                basis_row = row_by_id[node.workflow_basis_row_id]
                basis_text = (
                    "研究流程中的"
                    f"{visible_labels[basis_row.matrix_row_id]}（{basis_row.title_zh}）"
                )
            lines.append(
                f"- 节点依据：{_markdown_cell(basis_text)}"
            )

        lines.extend(("", "### 方案命名时间锚点/窗口", ""))
        if row.time_anchors:
            for anchor in row.time_anchors:
                lines.append(
                    f"- {_markdown_cell(anchor.anchor_label_zh)}："
                    f"{_time_constraint_text(anchor.time_constraint)}"
                )
        else:
            lines.append("- 未声明")

        lines.extend(
            (
                "",
                "### 六类义务及 DNF 逻辑",
                "",
                f"- 义务逻辑：{_dnf_text(row.obligation_expression, dnf_labels)}",
                "- 实际出现的义务类型（不补齐未声明类型）：",
            )
        )
        obligation_types: list[str] = []
        for obligation in row.obligations:
            kind_label = _zh(_OBLIGATION_KIND_ZH, obligation.kind)
            obligation_types.append(kind_label)
            details = [
                f"类型={kind_label}",
                f"方案表述={_markdown_cell(obligation.statement_zh)}",
                f"完成强度={_zh(_OBLIGATION_MODALITY_ZH, obligation.modality)}",
                f"专业判断={'是' if obligation.requires_professional_judgment else '否'}",
            ]
            if obligation.temporal_scope is not None:
                details.append(
                    f"资料范围={_zh(_TEMPORAL_SCOPE_ZH, obligation.temporal_scope)}"
                )
            if obligation.time_constraint_id:
                details.append(
                    f"时间锚点={_markdown_cell(time_labels.get(obligation.time_constraint_id, '方案命名锚点'))}"
                )
            lines.append("  - " + "；".join(details))
        lines.append(f"- 本行义务类型汇总：{_markdown_cell('、'.join(dict.fromkeys(obligation_types)))}")
        if row.condition_atoms:
            lines.append("- 适用/触发/例外条件逻辑：")
            if row.applicability_expression is not None:
                lines.append(
                    f"  - 适用条件：{_dnf_text(row.applicability_expression, condition_labels)}"
                )
            if row.trigger_expression is not None:
                lines.append(
                    f"  - 触发条件：{_dnf_text(row.trigger_expression, condition_labels)}"
                )
            if row.exception_expression is not None:
                lines.append(
                    f"  - 例外条件：{_dnf_text(row.exception_expression, condition_labels)}"
                )
                lines.append("  - 例外作用域（仅作用于明确触发分支）：")
                for group in row.exception_expression.groups:
                    scoped_labels = "、".join(
                        _markdown_cell(trigger_branch_labels[branch_id])
                        for branch_id in group.waives_trigger_branch_ids
                    )
                    lines.append(f"    - 仅适用于触发条件：{scoped_labels}")
        elif row.exception_expression is not None:
            lines.append(
                f"- 例外条件：{_dnf_text(row.exception_expression, condition_labels)}"
            )
            lines.append("- 例外作用域（仅作用于明确触发分支）：")
            for group in row.exception_expression.groups:
                scoped_labels = "、".join(
                    _markdown_cell(trigger_branch_labels[branch_id])
                    for branch_id in group.waives_trigger_branch_ids
                )
                lines.append(f"  - 仅适用于触发条件：{scoped_labels}")

        lines.extend(("", "### 最低证据", ""))
        for evidence in row.minimum_evidence:
            due_node = node_labels.get(evidence.due_workflow_stage_id, "对应审核节点")
            strength = [
                "允许使用筛选记录转录"
                if evidence.allows_screening_record_transcription
                else "不允许使用筛选记录转录",
                "要求同期客观来源"
                if evidence.requires_contemporaneous_objective_source
                else "可由非同期资料补充",
                "要求研究者评估记录"
                if evidence.requires_researcher_assessment_record
                else "无需单独研究者评估记录",
            ]
            lines.append(
                "- "
                + "；".join(
                    (
                        f"事实类型={_markdown_cell(evidence.fact_type_zh)}",
                        f"说明={_markdown_cell(evidence.description_zh)}",
                        f"应于节点={_markdown_cell(due_node)}",
                        f"来源类型={_markdown_cell('、'.join(evidence.required_source_types) or '方案未限定')}",
                        f"证据强度要求={_markdown_cell('；'.join(str(item) for item in strength))}",
                    )
                )
            )

        lines.extend(("", "### 专业判断", ""))
        judgment_items = [
            f"条件：{atom.statement_zh}"
            for atom in row.condition_atoms
            if atom.requires_professional_judgment
        ] + [
            f"义务：{obligation.statement_zh}"
            for obligation in row.obligations
            if obligation.requires_professional_judgment
        ]
        if judgment_items:
            lines.extend(f"- {_markdown_cell(item)}" for item in judgment_items)
        else:
            lines.append("- 本行未声明额外专业判断")

        lines.extend(("", "### 跨章节关系", ""))
        if row.cross_source_relations:
            for relation in row.cross_source_relations:
                target = row_by_id.get(relation.target_row_id)
                target_label = (
                    f"{visible_labels[target.matrix_row_id]}：{target.title_zh}"
                    if target is not None
                    else "目标控制（未解析）"
                )
                details = [
                    f"类型={_zh(_RELATION_KIND_ZH, relation.kind)}",
                    f"目标控制={_markdown_cell(target_label)}",
                ]
                if relation.shared_assessment_identity:
                    details.append("共享同一评估口径")
                if relation.resolution_zh:
                    details.append(f"解决说明={_markdown_cell(relation.resolution_zh)}")
                if relation.notes_zh:
                    details.append(f"备注={_markdown_cell(relation.notes_zh)}")
                lines.append("- " + "；".join(details))
        else:
            lines.append("- 无")

        lines.extend(("", "### 来源闭包", ""))
        for anchor in row.source_anchors:
            lines.extend(
                (
                    f"- 来源标题：{_markdown_cell(anchor.source_title_zh)}",
                    f"  - 来源标题路径：{_markdown_cell(' > '.join(anchor.heading_path_zh))}",
                    f"  - 原文位置：{_human_source_location(anchor.source_ref)}",
                    "  - 逐字摘录：",
                )
            )
            lines.extend(
                f"    > {_markdown_cell(line)}"
                for line in anchor.verbatim_excerpt.splitlines()
            )
        lines.extend(("", "---", ""))

    return "\n".join(lines).rstrip() + "\n"


def validate_protocol_control_matrix_serializations(
    matrix: ProtocolControlMatrix,
    json_payload: str | Mapping[str, object],
    markdown_text: str,
) -> ProtocolControlMatrix:
    """Prove JSON and Markdown carry the same ordered, Chinese review rows."""

    if isinstance(json_payload, str):
        try:
            parsed_payload = json.loads(json_payload)
        except json.JSONDecodeError as exc:
            raise ProtocolControlMatrixError("JSON_INVALID", "矩阵 JSON 无法解析") from exc
    else:
        parsed_payload = dict(json_payload)
    try:
        parsed = ProtocolControlMatrix.model_validate(parsed_payload)
    except Exception as exc:
        raise ProtocolControlMatrixError("JSON_SCHEMA_INVALID", "矩阵 JSON 不符合合同") from exc
    if parsed.model_dump(mode="json") != matrix.model_dump(mode="json"):
        raise ProtocolControlMatrixError("JSON_IDENTITY_MISMATCH", "JSON 与当前矩阵内容/身份不一致")

    header_match = re.search(
        r"<!--\s*protocol-control-matrix:\s*(\{.*?\})\s*-->",
        markdown_text,
    )
    if header_match is None:
        raise ProtocolControlMatrixError("MARKDOWN_HEADER_MISSING", "Markdown 缺少矩阵身份标记")
    try:
        header = json.loads(header_match.group(1))
    except json.JSONDecodeError as exc:
        raise ProtocolControlMatrixError("MARKDOWN_HEADER_INVALID", "Markdown 矩阵身份标记无法解析") from exc
    expected_header = {
        "matrix_id": matrix.matrix_id,
        "schema_version": matrix.schema_version,
        "protocol_version_id": matrix.protocol_version_id,
        "selected_phase": matrix.selected_phase.value,
    }
    if header != expected_header:
        raise ProtocolControlMatrixError("MARKDOWN_MATRIX_IDENTITY_MISMATCH", "Markdown 矩阵身份与 JSON 不一致")

    visible_markdown = re.sub(r"<!--.*?-->", "", markdown_text, flags=re.DOTALL)
    for prefix in _VISIBLE_MACHINE_ID_PREFIXES:
        if prefix in visible_markdown:
            raise ProtocolControlMatrixError(
                "MARKDOWN_MACHINE_ID_VISIBLE",
                "Markdown 可见正文不得出现机器身份前缀",
            )
    for value in _matrix_internal_values(matrix):
        if value in visible_markdown:
            raise ProtocolControlMatrixError(
                "MARKDOWN_MACHINE_ID_VISIBLE",
                "Markdown 可见正文不得出现机器身份或内部引用",
            )
    for field_name in _VISIBLE_INTERNAL_FIELD_NAMES:
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(field_name)}(?![A-Za-z0-9_])", visible_markdown):
            raise ProtocolControlMatrixError(
                "MARKDOWN_INTERNAL_FIELD_VISIBLE",
                "Markdown 可见正文不得出现内部字段名",
            )
    for enum_value in _VISIBLE_ENUM_VALUES:
        if re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(enum_value)}(?![A-Za-z0-9_])",
            visible_markdown,
        ):
            raise ProtocolControlMatrixError(
                "MARKDOWN_ENUM_VISIBLE",
                "Markdown 可见正文不得出现英文枚举值",
            )

    index_match = re.search(
        r"(?ms)^## 审阅索引\s*\n(?P<body>.*?)(?=^---\s*$)",
        visible_markdown,
    )
    if index_match is None:
        raise ProtocolControlMatrixError("MARKDOWN_INDEX_MISSING", "Markdown 缺少审阅索引")
    actual_index: list[tuple[object, ...]] = []
    for line in index_match.group("body").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = _markdown_table_cells(line)
        if len(cells) != 4 or not cells[0] or cells[0] == "审阅标签" or cells[0].startswith("-"):
            continue
        actual_index.append(tuple(cells))
    visible_labels = _visible_row_labels(matrix)
    expected_index: list[tuple[object, ...]] = []
    for row in matrix.rows:
        expected_index.append(
            (
                visible_labels[row.matrix_row_id],
                _zh(_SOURCE_KIND_ZH, row.source_kind),
                _markdown_cell(row.title_zh),
                _zh(_PHASE_DISPOSITION_VISIBLE_ZH, row.phase_disposition),
            )
        )
    if actual_index != expected_index:
        raise ProtocolControlMatrixError(
            "MARKDOWN_INDEX_MISMATCH",
            "Markdown 审阅索引行顺序/身份与 JSON 不一致",
        )

    detail_blocks = list(
        re.finditer(
            r"(?ms)^## (?P<label>[^：\n]+)：(?P<title>[^\n]+)\n(?P<body>.*?)(?=^## |\Z)",
            visible_markdown,
        )
    )
    expected_details = [
        (visible_labels[row.matrix_row_id], _markdown_cell(row.title_zh))
        for row in matrix.rows
    ]
    actual_details = [
        (match.group("label"), match.group("title")) for match in detail_blocks
    ]
    if actual_details != expected_details:
        raise ProtocolControlMatrixError(
            "MARKDOWN_DETAIL_ORDER_MISMATCH",
            "Markdown 详情区块顺序/标题与 JSON 行顺序不一致",
        )
    for row, block in zip(matrix.rows, detail_blocks):
        if f"- 审阅标签：{visible_labels[row.matrix_row_id]}" not in block.group("body"):
            raise ProtocolControlMatrixError(
                "MARKDOWN_DETAIL_IDENTITY_MISMATCH",
                "Markdown 详情标签与 JSON 行顺序不一致",
            )

    actual_rows: list[tuple[object, ...]] = []
    for match in re.finditer(
        r"<!--\s*protocol-control-matrix-row:\s*(\{.*?\})\s*-->",
        markdown_text,
    ):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise ProtocolControlMatrixError("MARKDOWN_ROW_INVALID", "Markdown 行身份标记无法解析") from exc
        actual_rows.append(
            (
                str(payload.get("row_id", "")),
                str(payload.get("source_kind", "")),
                str(payload.get("source_identity", "")),
                payload.get("official_child_code"),
                payload.get("source_candidate_id"),
                payload.get("review_nodes", []),
                payload.get("trigger_expression"),
                payload.get("exception_expression"),
            )
        )
    expected_rows = [
        (row.matrix_row_id,)
        + _row_identity(row)
        + (
            row.source_candidate_id,
            [_review_node_marker(node) for node in row.review_nodes],
            _dnf_marker(row.trigger_expression),
            _dnf_marker(row.exception_expression),
        )
        for row in matrix.rows
    ]
    if actual_rows != expected_rows:
        raise ProtocolControlMatrixError("MARKDOWN_ROW_IDENTITY_MISMATCH", "Markdown 行身份/顺序与 JSON 不一致")
    return matrix
