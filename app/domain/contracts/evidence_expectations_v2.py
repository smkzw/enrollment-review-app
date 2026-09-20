"""Phase 5 EvidenceExpectation v2 覆盖投影合同（Slice 5.4，worker_03）。

受试者级资料覆盖期望的不可变发布合同，从当前审核节点绑定的
``EvidenceExpectationTemplate`` 确定性投影五类状态
（``not_due / observed / observed_weak / referenced_missing / absent``），并细分
具体缺口类型。本模块只冻结确定性校验与稳定身份，不含存储、文件路径或外部模型调用，
覆盖设计书 §5.2 与 PRD P5-R07 / P5-AC07 / P5-AC03：

- 权威绑定：每个期望绑定不可变权威元组（``FactAuthority``）与模板；
- 五类状态互斥，按优先级 ``not_due > observed > observed_weak > referenced_missing
  > absent`` 决策；一个期望只有一个状态（不会重复报无证据）；
- ``observed`` 必须给出覆盖事实与定位；``observed_weak`` 覆盖较弱来源并携带溯源
  提醒（或 OCR/解析风险），绝不降级为 ``absent``；
- ``referenced_missing`` 只能由结构化缺失文件信号触发（绝不从散文推断）；
- ``absent`` 的到期缺口必须选择具体当前缺口类型，绝不回退到通用缺口；
- 覆盖证据必须是同权威元组、显式绑定模板要求且精确 ``fact_type`` 的已发布事实/定位；
- ``(review_episode_id, template_id, revision)`` 唯一：刷新追加更高 revision，
  绝不覆盖旧投影（旧权威元组可回放）。

旧 ``evidence_expectations``（Phase 3 合同）保持只读回归锚点，不进入本模块。
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from .common import ContractModel
from .enums import ExpectationStatus, GapType
from .facts import ClinicalFactV2, FactAuthority

__all__ = [
    "CoverageObservation",
    "CoverageGapSignal",
    "EvidenceExpectationV2",
    "canonical_input_gap_signals",
    "expectation_identity",
]

#: 缺失/风险信号允许的缺口类型（结构化输入；``absent`` 只接受具体当前缺口）。
_ABSENT_GAP_TYPES = {
    GapType.OBSERVATION_UNVERIFIED,
    GapType.RECORD_INCOMPLETE,
    GapType.DESCRIPTION_INSUFFICIENT,
    GapType.REQUIRED_PROCEDURE_NOT_DONE,
    GapType.RESULT_FIELDS_MISSING,
    GapType.DATE_OR_ANCHOR_MISSING,
    GapType.PROFESSIONAL_JUDGMENT,
    GapType.OCR_OR_PARSE_RISK,
}

_WEAK_GAP_TYPES = {
    GapType.OBSERVATION_UNVERIFIED,
    GapType.PROVENANCE_FOLLOWUP,
    GapType.OCR_OR_PARSE_RISK,
    GapType.HISTORICAL_SOURCE_UNAVAILABLE,
}

_SIGNAL_GAP_TYPES = _ABSENT_GAP_TYPES | _WEAK_GAP_TYPES | {
    GapType.REFERENCED_FILE_MISSING,
    GapType.FUTURE_STAGE_NOT_DUE,
}

#: ``referenced_missing`` 允许的来源信号缺口（只接受结构化缺失文件信号）。
_REFERENCED_MISSING_GAP = GapType.REFERENCED_FILE_MISSING


def _require_utc(value: datetime, field_name: str) -> None:
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise ValueError(f"{field_name} 必须携带 UTC 时区")
    if offset.total_seconds() != 0:
        raise ValueError(f"{field_name} 必须使用 UTC 时区")


def _require_sorted_unique(values: list[str], label: str) -> None:
    if values != sorted(set(values)):
        raise ValueError(f"{label} 必须按 ID 排序且不得重复")


class CoverageGapSignal(ContractModel):
    """结构化的资料缺失/风险输入，绝不来自散文解析。

    投影器接收结构化信号以细分缺口原因：``kind`` 为具体缺口/风险类型，``detail``
    为可展示的原因说明，``referenced_file_id`` 仅用于 ``referenced_file_missing``，
    ``applies_to_template_id`` 把信号限定到单个模板（None 表示适用于全部模板）。
    OCR/解析风险、缺失文件、未完成流程、描述不完整等一律由调用方结构化提供，
    系统不得从自由文本推断任何缺口。
    """

    model_config = ConfigDict(extra="forbid")

    kind: GapType
    detail: str | None = None
    referenced_file_id: str | None = None
    applies_to_template_id: str | None = None
    fallback_only: bool = False

    @model_validator(mode="after")
    def validate_signal(self) -> "CoverageGapSignal":
        if self.fallback_only and self.kind not in {
            GapType.OBSERVATION_UNVERIFIED, GapType.RECORD_INCOMPLETE,
        }:
            raise ValueError("仅未核实或记录不全的默认提示可在完整证据到位后撤去")
        if self.kind not in _SIGNAL_GAP_TYPES:
            raise ValueError(
                f"不支持的缺口信号类型 {self.kind}；请使用结构化缺口/风险类型"
            )
        if self.kind == GapType.REFERENCED_FILE_MISSING and not self.referenced_file_id:
            raise ValueError("referenced_file_missing 必须提供结构化缺失文件身份")
        if (
            self.kind in _ABSENT_GAP_TYPES
            or self.kind in _WEAK_GAP_TYPES
        ) and self.referenced_file_id is not None:
            raise ValueError("非 referenced_file_missing 信号不能携带缺失文件身份")
        return self


class CoverageObservation(ContractModel):
    """已发布事实及其定位所属资料类型。

    ``source_types`` 来自 Phase 4 完整处理修订冻结的资料元数据，
    与事实的 ``source_strength`` 是两个独立维度，不得互相代替。
    """

    fact: "ClinicalFactV2"
    source_types: list[str] = Field(default_factory=list)

    @field_validator("source_types", mode="before")
    @classmethod
    def normalize_source_types(cls, value):
        if value is None:
            return []
        return sorted({str(item).strip().casefold() for item in value})

    @model_validator(mode="after")
    def validate_observation(self) -> "CoverageObservation":
        if any(not value for value in self.source_types):
            raise ValueError("覆盖资料类型必须非空、有序且不重复")
        return self


def canonical_input_gap_signals(
    template_id: str,
    signals: Sequence[CoverageGapSignal],
) -> list[CoverageGapSignal]:
    """冻结一条期望实际接收的结构化输入信号（确定 canonical 序，去重）。

    - 只保留适用于该模板的信号（``applies_to_template_id`` 为 None 或等于模板）；
      绑定其他模板的信号直接拒绝，绝不静默跨模板复制；
    - 以信号的 canonical JSON 为键排序并去重，同一输入永远得到同一冻结序。
    """
    from app.domain.publication import canonical_hash

    frozen: dict[str, CoverageGapSignal] = {}
    for signal in signals:
        if (
            signal.applies_to_template_id is not None
            and signal.applies_to_template_id != template_id
        ):
            raise ValueError(
                f"期望 {template_id} 的输入信号绑定到了其他模板 "
                f"{signal.applies_to_template_id}，拒绝跨模板存储"
            )
        key = canonical_hash(signal.model_dump(mode="json"))
        frozen[key] = signal
    return [frozen[key] for key in sorted(frozen)]


class EvidenceExpectationV2(ContractModel):
    """受试者级期望覆盖投影（不可变发布合同）。

    - ``authority`` 不可变权威元组；``template_id`` 绑定当前审核节点规则修订模板；
    - ``status`` 五类状态之一；``gap_type`` 细分缺口原因（互斥组合见校验器）；
    - ``coverage_fact_ids`` 提供覆盖的已发布事实（同权威元组、显式绑定资料要求）；
      ``locator_ids`` 为其 Phase 4 定位（链接表，实体类型 expectation）；
    - ``source_coverage`` 覆盖强度相对来源要求的判定：complete/weak/none；
    - ``provenance_followup`` 溯源提醒（较弱转述/历史来源未就位）；
    - ``revision`` 追加写：``(review_episode_id, template_id, revision)`` 唯一。
    """

    schema_version: Literal["phase5/v1"] = "phase5/v1"
    model_config = ConfigDict(extra="forbid")

    expectation_id: str = Field(min_length=1)
    source_revision_of: str | None = Field(default=None, min_length=1)
    authority: FactAuthority
    template_id: str = Field(min_length=1)
    status: ExpectationStatus
    gap_type: GapType | None = None
    revision: int = Field(ge=1)
    locator_ids: list[str] = Field(default_factory=list)
    coverage_fact_ids: list[str] = Field(default_factory=list)
    source_coverage: Literal["complete", "weak", "none"] = "none"
    provenance_followup: bool = False
    provenance_reason: str | None = None
    gap_detail: str | None = None
    #: 本次投影实际接收、且适用于本模板的结构化输入信号（含 fallback_only）。
    #: None = 历史数据/来源未知（不得据此推断具体或兜底）；[] = 明确无任何信号；
    #: 非空 = 精确输入证据。追加写并参与幂等语义比较，绝不改写旧行。
    input_gap_signals: list[CoverageGapSignal] | None = None
    created_at: datetime

    @model_validator(mode="after")
    def validate_input_gap_signals(self) -> "EvidenceExpectationV2":
        if self.input_gap_signals is None:
            return self
        canonical = canonical_input_gap_signals(
            self.template_id, self.input_gap_signals
        )
        if canonical != self.input_gap_signals:
            self.input_gap_signals = canonical
        return self

    @model_validator(mode="after")
    def validate_expectation(self) -> "EvidenceExpectationV2":
        _require_utc(self.created_at, "created_at")
        _require_sorted_unique(self.locator_ids, "期望定位")
        _require_sorted_unique(self.coverage_fact_ids, "期望覆盖事实")
        if self.status == ExpectationStatus.PENDING_CONTROL_APPLICABILITY:
            if self.gap_type != GapType.CONTROL_APPLICABILITY_PENDING:
                raise ValueError("控制待判断必须使用 control_applicability_pending 缺口")
            if self.coverage_fact_ids or self.locator_ids:
                raise ValueError("控制待判断期望不能携带覆盖事实或定位")
            if self.provenance_followup:
                raise ValueError("控制待判断期望不能携带溯源提醒")
            if self.source_coverage != "none":
                raise ValueError("控制待判断期望不得声明覆盖强度")
            return self
        if self.status == ExpectationStatus.NOT_DUE:
            if self.gap_type != GapType.FUTURE_STAGE_NOT_DUE:
                raise ValueError("尚未到期必须使用 future_stage_not_due 缺口")
            if self.coverage_fact_ids or self.locator_ids:
                raise ValueError("尚未到期期望不能携带覆盖事实或定位")
            if self.provenance_followup:
                raise ValueError("尚未到期期望不能携带溯源提醒")
            return self
        if self.status == ExpectationStatus.OBSERVED:
            if not self.coverage_fact_ids or not self.locator_ids:
                raise ValueError("已观察期望必须给出覆盖事实与定位")
            if self.gap_type is not None:
                raise ValueError("完整证据不能携带阻断缺口")
            if self.source_coverage != "complete":
                raise ValueError("已观察期望的覆盖强度必须是 complete")
            if self.provenance_followup:
                raise ValueError("完整证据不能携带溯源提醒")
            return self
        if self.status == ExpectationStatus.OBSERVED_WEAK:
            if not self.coverage_fact_ids or not self.locator_ids:
                raise ValueError("较弱证据期望必须给出覆盖事实与定位")
            if self.gap_type not in _WEAK_GAP_TYPES:
                raise ValueError("较弱证据必须说明溯源、解析或历史来源风险")
            if self.gap_type in {GapType.OCR_OR_PARSE_RISK, GapType.OBSERVATION_UNVERIFIED}:
                if self.source_coverage not in {"complete", "weak"}:
                    raise ValueError("OCR/解析风险较弱证据必须仍有 complete 或 weak 覆盖")
            else:
                if self.source_coverage != "weak":
                    raise ValueError("溯源/历史来源较弱证据的覆盖强度必须是 weak")
                if not self.provenance_followup:
                    raise ValueError("溯源/历史来源较弱证据必须携带溯源提醒")
            return self
        if self.status == ExpectationStatus.REFERENCED_MISSING:
            if self.gap_type != _REFERENCED_MISSING_GAP:
                raise ValueError("已引用未提供必须使用 referenced_file_missing 缺口")
            if self.coverage_fact_ids or self.locator_ids:
                raise ValueError("已引用未提供期望不能携带覆盖事实或定位")
            if self.provenance_followup:
                raise ValueError("已引用未提供期望不能携带溯源提醒")
            return self
        # ABSENT
        if self.gap_type not in _ABSENT_GAP_TYPES:
            raise ValueError("未观察到的到期证据必须使用具体当前缺口，不得回退通用缺口")
        if self.coverage_fact_ids or self.locator_ids:
            raise ValueError("未观察到期望不能携带覆盖事实或定位")
        if self.provenance_followup:
            raise ValueError("未观察到期望不能携带溯源提醒")
        return self


def expectation_identity(
    review_episode_id: str, template_id: str, revision: int = 1
) -> str:
    """期望行 ID：同一审核节点同一模板的每次追加（revision）得到唯一 ID。

    ``evidence_expectations_v2`` 以 ``expectation_id`` 为主键且
    ``(review_episode_id, template_id, revision)`` 唯一：刷新追加更高 revision 时
    必须生成新的行 ID，绝不覆盖旧投影（旧权威元组可回放）。
    """
    from app.domain.publication import canonical_hash

    return "expectation:" + canonical_hash(
        {
            "review_episode_id": review_episode_id,
            "template_id": template_id,
            "revision": revision,
        }
    )[:32]
