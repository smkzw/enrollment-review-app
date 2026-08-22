"""Phase 5 临床事实与 Patient Profile 领域合同（Slice 5.1，纯校验，无存储）。

本模块只冻结确定性校验与身份计算，不含存储、文件路径或外部模型调用，覆盖设计书
§2.1 不可变权威元组、§3.1 候选/发布分离、§3.2 部分日期与时态、§3.3 极性/沉默/
来源强度、§3.4 重复与冲突，以及 §4.1 规范化运行/调用/门禁记录的合同层身份：

- ``FactAuthority``           不可变权威元组，冻结活动证据快照与完整处理修订；
- ``PartialDateRange``        年/年月/日/未知精度与确定性上下界；未知日期绝不借用
                              筛选/上传/操作日期；
- ``AssertionBasis``          否定/肯定事实的明确断言依据（对象+语句+定位原文哈希）；
- ``ClinicalFactCandidateV2`` / ``ClinicalEventCandidateV2`` /
  ``MedicationExposureCandidateV2``   证据规范化候选（携带模型不确定性）；
- ``ClinicalFactV2`` / ``ClinicalEventV2`` / ``MedicationExposureV2`` /
  ``ClinicalConflictGroupV2`` 发布合同（携带 Gate id、权威元组、稳定身份、来源强度
                              与 revision；不携带可用于临床裁决的模型置信度）；
- ``FactNormalizationRun`` / ``FactNormalizationCall`` / ``FactGateResult``
                              持久化运行/调用/逐门禁结果合同；不依赖 ReviewRun；
- 稳定身份推导：``clinical_fact_stable_identity`` / ``clinical_event_stable_identity``
  / ``medication_exposure_stable_identity``，以及运行幂等键
  ``fact_run_idempotency_key``。

Slice 5.1 硬不变量：发布对象必须绑定不可变权威元组；未知极性不得携带被断言值；
沉默/未提及/缺页绝不生成否认或正常事实（只能形成期望缺口）；否定事实必须有明确
否定原句与定位原文哈希；重复身份不含模型置信度与定位；冲突不由 Agent 选择赢家。
候选合同与发布合同物理分离；旧 ``clinical_facts`` 占位合同不进入本模块。
"""
from __future__ import annotations

import calendar
import math
from datetime import date, datetime
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from .common import ContractModel, ScalarValue
from .enums import (
    DatePrecision,
    DurationStatus,
    FactCallStatus,
    FactGate,
    FactNormalizationRunStatus,
    FactPolarity,
    GateOutcome,
    SourceStrength,
)

__all__ = [
    "AssertionBasis",
    "ClinicalConflictGroupV2",
    "ClinicalEventCandidateV2",
    "ClinicalEventV2",
    "ClinicalFactCandidateV2",
    "ClinicalFactV2",
    "FactAuthority",
    "FactGateResult",
    "FactNormalizationCall",
    "FactNormalizationRun",
    "MedicationExposureCandidateV2",
    "MedicationExposureV2",
    "PartialDateRange",
    "clinical_event_stable_identity",
    "clinical_fact_stable_identity",
    "fact_authority_hash",
    "fact_run_idempotency_key",
    "medication_exposure_stable_identity",
]

_SHA256 = r"^[0-9a-f]{64}$"


class Phase5Model(ContractModel):
    """Phase 5 合同基类：与 legacy ``fixture/v1`` 合同明确区分。"""

    schema_version: Literal["phase5/v1"] = "phase5/v1"


def _require_utc(value: datetime, field_name: str) -> None:
    """拒绝非 UTC 时区或 naive 时间戳（与 Phase 4 合同边界一致）。"""
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise ValueError(f"{field_name} 必须携带 UTC 时区")
    if offset.total_seconds() != 0:
        raise ValueError(f"{field_name} 必须使用 UTC 时区")


# --------------------------------------------------------------------------- 权威元组


class FactAuthority(ContractModel):
    """不可变权威元组：每个发布实体绑定同一活动证据快照与完整处理修订。

    ``episode_revision`` 与 ``complete_processing_revision_id`` 一起冻结运行时审核
    节点指针；指针或修订变化时结果记为陈旧并拒绝发布。字段 frozen，杜绝发布后漂移。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    episode_revision: int = Field(ge=1)
    protocol_version_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    evidence_snapshot_v2_id: str = Field(min_length=1)
    complete_processing_revision_id: str = Field(min_length=1)


def fact_authority_hash(authority: FactAuthority) -> str:
    """权威元组的可重建内容身份（不含任何人工易变信息）。"""
    from app.domain.publication import canonical_hash

    return canonical_hash({"authority": authority.model_dump(mode="json")})


# --------------------------------------------------------------------------- 日期与时态


class PartialDateRange(ContractModel):
    """部分日期范围：保留精度与确定性上下界。

    - day    上下界相同（完整日）；
    - month  当月首日至末日；
    - year   当年 1 月 1 日至 12 月 31 日；
    - unknown 上下界为空；绝不借用筛选日、上传日或操作日。

    ``source_text`` 只用于溯源展示，不参与稳定身份（去重只认语义边界）。
    """

    source_text: str | None = None
    precision: DatePrecision
    lower_bound: date | None = None
    upper_bound: date | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "PartialDateRange":
        if self.precision == DatePrecision.UNKNOWN:
            if self.lower_bound is not None or self.upper_bound is not None:
                raise ValueError("未知日期不能携带上下界；不得借用筛选/上传/操作日期")
            return self
        if self.lower_bound is None or self.upper_bound is None:
            raise ValueError("已知日期精度必须提供确定性上下界")
        if self.upper_bound < self.lower_bound:
            raise ValueError("日期上界不能早于下界")
        if self.precision == DatePrecision.DAY:
            if self.lower_bound != self.upper_bound:
                raise ValueError("日精度日期上下界必须相同")
        elif self.precision == DatePrecision.MONTH:
            if not (
                self.lower_bound.year == self.upper_bound.year
                and self.lower_bound.month == self.upper_bound.month
            ):
                raise ValueError("月精度上下界必须属于同一月份")
            if self.lower_bound.day != 1:
                raise ValueError("月精度下界必须是当月首日")
            last_day = calendar.monthrange(
                self.upper_bound.year, self.upper_bound.month
            )[1]
            if self.upper_bound.day != last_day:
                raise ValueError("月精度上界必须是当月末日")
        elif self.precision == DatePrecision.YEAR:
            if self.lower_bound.month != 1 or self.lower_bound.day != 1:
                raise ValueError("年精度下界必须是当年 1 月 1 日")
            if self.upper_bound.month != 12 or self.upper_bound.day != 31:
                raise ValueError("年精度上界必须是当年 12 月 31 日")
            if self.lower_bound.year != self.upper_bound.year:
                raise ValueError("年精度上下界必须属于同一年")
        return self


def _date_range_identity(dr: PartialDateRange | None) -> dict | None:
    """日期范围的语义身份（不含 source_text），用于稳定身份/去重键。"""
    if dr is None:
        return None
    return {
        "precision": dr.precision.value,
        "lower_bound": dr.lower_bound.isoformat() if dr.lower_bound else None,
        "upper_bound": dr.upper_bound.isoformat() if dr.upper_bound else None,
    }


# --------------------------------------------------------------------------- 断言依据


class AssertionBasis(ContractModel):
    """肯定/否定事实的明确断言依据。

    否定事实必须同时满足：明确被断言对象、明确否定语句、定位原文哈希一致。
    未提及、空白、邻近句否定、缺页或未勾选只能生成期望缺口，不能作为否定依据。
    """

    asserted_object: str = Field(min_length=1)
    assertion_text: str = Field(min_length=1)
    locator_id: str = Field(min_length=1)
    source_text_sha256: str = Field(pattern=_SHA256)


# --------------------------------------------------------------------------- 极性/值共享校验


def _validate_fact_polarity_value(
    polarity: FactPolarity,
    value: ScalarValue | None,
    unit: str | None,
    assertion_basis: AssertionBasis | None,
) -> None:
    if polarity == FactPolarity.UNKNOWN:
        if value is not None or unit is not None:
            raise ValueError("未知极性事实不能携带被断言值或单位")
        if assertion_basis is not None:
            raise ValueError("未知极性事实不能携带断言依据")
        return
    if value is None:
        raise ValueError("肯定或否定事实必须携带被断言的规范值")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("数值事实必须是有限数")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and not unit:
        raise ValueError("数值事实必须声明单位；无量纲值显式使用 unitless")
    if assertion_basis is None:
        raise ValueError("肯定或否定事实必须携带明确断言依据")


def _require_sorted_unique(values: list[str], label: str) -> None:
    if values != sorted(set(values)):
        raise ValueError(f"{label} 必须按 ID 排序且不得重复")


# --------------------------------------------------------------------------- 候选合同


class ClinicalFactCandidateV2(Phase5Model):
    """证据规范化候选：被断言对象、极性、原始/规范值、单位、时间建议、定位引用。

    携带模型不确定性（只作为候选质量审计信息，不得成为发布/隐藏/排序阈值）。
    """

    candidate_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    candidate_kind: Literal["fact"] = "fact"
    fact_type: str = Field(min_length=1)
    polarity: FactPolarity
    asserted_object: str = Field(min_length=1)
    raw_value: ScalarValue | None = None
    canonical_value: ScalarValue | None = None
    unit: str | None = None
    date_range: PartialDateRange | None = None
    record_time: datetime | None = None
    locator_ids: list[str] = Field(min_length=1)
    candidate_source_semantics: str = Field(min_length=1)
    assertion_basis: AssertionBasis | None = None
    model_uncertainty: float = Field(ge=0, le=1)
    created_at: datetime

    @model_validator(mode="after")
    def validate_candidate(self) -> "ClinicalFactCandidateV2":
        _require_utc(self.created_at, "created_at")
        if self.record_time is not None:
            _require_utc(self.record_time, "record_time")
        _require_sorted_unique(self.locator_ids, "候选定位")
        if self.polarity == FactPolarity.UNKNOWN:
            if self.raw_value is not None or self.canonical_value is not None:
                raise ValueError("未知极性候选不能携带被断言值")
            if self.assertion_basis is not None:
                raise ValueError("未知极性候选不能携带断言依据")
        else:
            if self.canonical_value is None:
                raise ValueError("肯定或否定候选必须携带规范值")
            if isinstance(self.canonical_value, float) and not math.isfinite(
                self.canonical_value
            ):
                raise ValueError("候选规范数值必须是有限数")
            if isinstance(self.canonical_value, (int, float)) and not isinstance(
                self.canonical_value, bool
            ) and not self.unit:
                raise ValueError("数值候选必须声明单位；无量纲值显式使用 unitless")
            if self.assertion_basis is None:
                raise ValueError("肯定或否定候选必须携带明确断言依据")
            if self.assertion_basis.locator_id not in self.locator_ids:
                raise ValueError("断言依据定位必须属于候选事实的定位集合")
            if self.assertion_basis.asserted_object != self.asserted_object:
                raise ValueError("候选被断言对象必须与断言依据对象一致")
        return self


class ClinicalEventCandidateV2(Phase5Model):
    """事件候选：事件类型、起止范围、持续状态、记录时间与引用。"""

    candidate_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    candidate_kind: Literal["event"] = "event"
    event_type: str = Field(min_length=1)
    start_range: PartialDateRange | None = None
    end_range: PartialDateRange | None = None
    duration_status: DurationStatus
    record_time: datetime | None = None
    fact_candidate_ids: list[str] = Field(min_length=1)
    locator_ids: list[str] = Field(min_length=1)
    candidate_source_semantics: str = Field(min_length=1)
    model_uncertainty: float = Field(ge=0, le=1)
    created_at: datetime

    @model_validator(mode="after")
    def validate_candidate(self) -> "ClinicalEventCandidateV2":
        _require_utc(self.created_at, "created_at")
        if self.record_time is not None:
            _require_utc(self.record_time, "record_time")
        _require_sorted_unique(self.fact_candidate_ids, "事件候选事实引用")
        _require_sorted_unique(self.locator_ids, "事件候选定位")
        _validate_duration_bounds(self.start_range, self.end_range, self.duration_status)
        return self


class MedicationExposureCandidateV2(Phase5Model):
    """用药暴露候选：原始药名/类别、适应证、剂量/单位/频次/途径、起止与持续状态。

    保留原始药名、起止日期范围与持续状态；本阶段不判断是否违反洗脱期。
    """

    candidate_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    candidate_kind: Literal["exposure"] = "exposure"
    medication_name: str = Field(min_length=1)
    category: str | None = None
    indication: str | None = None
    dose: str | None = None
    unit: str | None = None
    frequency: str | None = None
    route: str | None = None
    start_range: PartialDateRange | None = None
    end_range: PartialDateRange | None = None
    duration_status: DurationStatus
    record_time: datetime | None = None
    fact_candidate_ids: list[str] = Field(min_length=1)
    locator_ids: list[str] = Field(min_length=1)
    candidate_source_semantics: str = Field(min_length=1)
    model_uncertainty: float = Field(ge=0, le=1)
    created_at: datetime

    @model_validator(mode="after")
    def validate_candidate(self) -> "MedicationExposureCandidateV2":
        _require_utc(self.created_at, "created_at")
        if self.record_time is not None:
            _require_utc(self.record_time, "record_time")
        _require_sorted_unique(self.fact_candidate_ids, "暴露候选事实引用")
        _require_sorted_unique(self.locator_ids, "暴露候选定位")
        _validate_duration_bounds(self.start_range, self.end_range, self.duration_status)
        return self


# --------------------------------------------------------------------------- 发布合同


class ClinicalFactV2(Phase5Model):
    """发布接受的临床事实：绑定权威元组、Gate id、来源强度与稳定身份。

    不含模型置信度；稳定身份由权威元组、类型、极性、规范值/单位与日期范围推导，
    不包含定位（同内容多来源合并后保留全部定位）。
    """

    fact_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    gate_id: str = Field(min_length=1)
    authority: FactAuthority
    fact_type: str = Field(min_length=1)
    polarity: FactPolarity
    asserted_object: str = Field(min_length=1)
    value: ScalarValue | None = None
    unit: str | None = None
    source_strength: SourceStrength
    date_range: PartialDateRange | None = None
    record_time: datetime | None = None
    locator_ids: list[str] = Field(min_length=1)
    assertion_basis: AssertionBasis | None = None
    stable_identity: str = Field(pattern=_SHA256)
    revision: int = Field(ge=1)
    created_at: datetime

    @model_validator(mode="after")
    def validate_fact(self) -> "ClinicalFactV2":
        _require_utc(self.created_at, "created_at")
        if self.record_time is not None:
            _require_utc(self.record_time, "record_time")
        _require_sorted_unique(self.locator_ids, "发布事实定位")
        _validate_fact_polarity_value(
            self.polarity, self.value, self.unit, self.assertion_basis
        )
        if (
            self.assertion_basis is not None
            and self.assertion_basis.locator_id not in self.locator_ids
        ):
            raise ValueError("断言依据定位必须属于发布事实的定位集合")
        if (
            self.assertion_basis is not None
            and self.assertion_basis.asserted_object != self.asserted_object
        ):
            raise ValueError("发布事实被断言对象必须与断言依据对象一致")
        expected = clinical_fact_stable_identity(
            authority=self.authority,
            fact_type=self.fact_type,
            asserted_object=self.asserted_object,
            polarity=self.polarity,
            value=self.value,
            unit=self.unit,
            date_range=self.date_range,
        )
        if self.stable_identity != expected:
            raise ValueError("发布事实稳定身份与权威元组/类型/对象/极性/规范值/单位/日期范围不一致")
        return self


class ClinicalEventV2(Phase5Model):
    """发布接受的事件：起止范围、持续状态、记录时间与证据引用。

    事件的事实引用与证据定位引用必须属于同一审核节点与处理修订（权威元组一致），
    跨实体核对在仓储层（worker_03）执行；本合同保证引用集合稳定有序。
    """

    event_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    gate_id: str = Field(min_length=1)
    authority: FactAuthority
    event_type: str = Field(min_length=1)
    start_range: PartialDateRange | None = None
    end_range: PartialDateRange | None = None
    duration_status: DurationStatus
    record_time: datetime | None = None
    fact_ids: list[str] = Field(min_length=1)
    referenced_fact_objects: list[str] = Field(min_length=1)
    locator_ids: list[str] = Field(min_length=1)
    source_strength: SourceStrength
    stable_identity: str = Field(pattern=_SHA256)
    revision: int = Field(ge=1)
    created_at: datetime

    @model_validator(mode="after")
    def validate_event(self) -> "ClinicalEventV2":
        _require_utc(self.created_at, "created_at")
        if self.record_time is not None:
            _require_utc(self.record_time, "record_time")
        _require_sorted_unique(self.fact_ids, "事件事实引用")
        _require_sorted_unique(self.referenced_fact_objects, "事件引用事实对象")
        _require_sorted_unique(self.locator_ids, "事件定位")
        _validate_duration_bounds(self.start_range, self.end_range, self.duration_status)
        expected = clinical_event_stable_identity(
            authority=self.authority,
            event_type=self.event_type,
            referenced_fact_objects=self.referenced_fact_objects,
            start_range=self.start_range,
            end_range=self.end_range,
            duration_status=self.duration_status,
        )
        if self.stable_identity != expected:
            raise ValueError("发布事件稳定身份与权威元组/事件类型/引用事实对象/起止/持续状态不一致")
        return self


class MedicationExposureV2(Phase5Model):
    """发布接受的用药/治疗暴露：保留原始药名、起止范围与持续状态。

    ENDED 必须由资料明确给出终止信息（不得由“既往”推断）；ONGOING 不得携带终止范围。
    本阶段不判断是否违反洗脱期。
    """

    exposure_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    gate_id: str = Field(min_length=1)
    authority: FactAuthority
    medication_name: str = Field(min_length=1)
    category: str | None = None
    indication: str | None = None
    dose: str | None = None
    unit: str | None = None
    frequency: str | None = None
    route: str | None = None
    start_range: PartialDateRange | None = None
    end_range: PartialDateRange | None = None
    duration_status: DurationStatus
    record_time: datetime | None = None
    fact_ids: list[str] = Field(min_length=1)
    locator_ids: list[str] = Field(min_length=1)
    source_strength: SourceStrength
    stable_identity: str = Field(pattern=_SHA256)
    revision: int = Field(ge=1)
    created_at: datetime

    @model_validator(mode="after")
    def validate_exposure(self) -> "MedicationExposureV2":
        _require_utc(self.created_at, "created_at")
        if self.record_time is not None:
            _require_utc(self.record_time, "record_time")
        _require_sorted_unique(self.fact_ids, "暴露事实引用")
        _require_sorted_unique(self.locator_ids, "暴露定位")
        _validate_duration_bounds(self.start_range, self.end_range, self.duration_status)
        expected = medication_exposure_stable_identity(
            authority=self.authority,
            medication_name=self.medication_name,
            category=self.category,
            indication=self.indication,
            dose=self.dose,
            unit=self.unit,
            frequency=self.frequency,
            route=self.route,
            start_range=self.start_range,
            end_range=self.end_range,
            duration_status=self.duration_status,
        )
        if self.stable_identity != expected:
            raise ValueError("发布暴露稳定身份与权威元组/药名/剂量/途径/起止/持续状态不一致")
        return self


def _validate_duration_bounds(
    start_range: PartialDateRange | None,
    end_range: PartialDateRange | None,
    duration_status: DurationStatus,
) -> None:
    if duration_status == DurationStatus.ENDED and end_range is None:
        raise ValueError("已结束暴露必须由资料明确给出终止日期，不得由“既往”推断")
    if duration_status == DurationStatus.ONGOING and end_range is not None:
        raise ValueError("持续暴露不能携带终止日期范围")
    if start_range is not None and end_range is not None:
        if start_range.lower_bound is None or end_range.upper_bound is None:
            return
        if start_range.lower_bound > end_range.upper_bound:
            raise ValueError("暴露开始范围不能晚于结束范围")


class ClinicalConflictGroupV2(Phase5Model):
    """同一语义对象的不同来源不兼容值/极性/日期/持续状态时的未解决冲突组。

    冲突并列展示，不自动择优或覆盖；只有来源校对或人工事实修订生成新 revision 后
    才能变化（``resolution_revision > 0``），Agent 无权选择赢家。
    """

    conflict_group_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    gate_id: str = Field(min_length=1)
    authority: FactAuthority
    fact_ids: list[str] = Field(min_length=2)
    locator_ids: list[str] = Field(min_length=1)
    resolution_revision: int = Field(default=0, ge=0)
    created_at: datetime

    @model_validator(mode="after")
    def validate_conflict(self) -> "ClinicalConflictGroupV2":
        _require_utc(self.created_at, "created_at")
        _require_sorted_unique(self.fact_ids, "冲突组事实引用")
        _require_sorted_unique(self.locator_ids, "冲突组定位")
        if self.resolution_revision != 0:
            raise ValueError(
                "Slice 5.1 只允许追加未解决冲突；解决必须由后续有理由的人工修订生成新 revision"
            )
        return self


# --------------------------------------------------------------------------- 稳定身份


def clinical_fact_stable_identity(
    *,
    authority: FactAuthority,
    fact_type: str,
    asserted_object: str,
    polarity: FactPolarity,
    value: ScalarValue | None,
    unit: str | None,
    date_range: PartialDateRange | None,
) -> str:
    """临床事实稳定重复键：包含被断言对象，排除置信度与定位。"""
    from app.domain.publication import canonical_hash

    return canonical_hash(
        {
            "identity": "clinical_fact/v2",
            "authority": authority.model_dump(mode="json"),
            "fact_type": fact_type,
            "asserted_object": asserted_object,
            "polarity": polarity.value,
            "value": value,
            "unit": unit,
            "date_range": _date_range_identity(date_range),
        }
    )


def clinical_event_stable_identity(
    *,
    authority: FactAuthority,
    event_type: str,
    referenced_fact_objects: list[str],
    start_range: PartialDateRange | None,
    end_range: PartialDateRange | None,
    duration_status: DurationStatus,
) -> str:
    """事件稳定重复键：包含引用事实对象，防止不同临床对象误合并。"""
    from app.domain.publication import canonical_hash

    return canonical_hash(
        {
            "identity": "clinical_event/v2",
            "authority": authority.model_dump(mode="json"),
            "event_type": event_type,
            "referenced_fact_objects": referenced_fact_objects,
            "start_range": _date_range_identity(start_range),
            "end_range": _date_range_identity(end_range),
            "duration_status": duration_status.value,
        }
    )


def medication_exposure_stable_identity(
    *,
    authority: FactAuthority,
    medication_name: str,
    category: str | None,
    indication: str | None,
    dose: str | None,
    unit: str | None,
    frequency: str | None,
    route: str | None,
    start_range: PartialDateRange | None,
    end_range: PartialDateRange | None,
    duration_status: DurationStatus,
) -> str:
    """用药暴露稳定重复键：权威元组/药名/类别/适应证/剂量/单位/频次/途径/起止/持续状态。"""
    from app.domain.publication import canonical_hash

    return canonical_hash(
        {
            "identity": "medication_exposure/v2",
            "authority": authority.model_dump(mode="json"),
            "medication_name": medication_name,
            "category": category,
            "indication": indication,
            "dose": dose,
            "unit": unit,
            "frequency": frequency,
            "route": route,
            "start_range": _date_range_identity(start_range),
            "end_range": _date_range_identity(end_range),
            "duration_status": duration_status.value,
        }
    )


# --------------------------------------------------------------------------- 运行/调用/门禁


def fact_run_idempotency_key(
    *,
    authority: FactAuthority,
    prompt_version_id: str,
    model_config_id: str,
    input_scope_sha256: str,
    contract_version: str = "phase5/facts/v1",
) -> str:
    """规范化运行幂等键：权威元组 + PromptVersion + ModelConfig + 文档切片哈希 + 合同版本。

    同一活动处理修订、PromptVersion、ModelConfig 与输入范围重复运行不得创建重复事实
    或 Profile；本阶段不伪造 Phase 6 ReviewRun。
    """
    from app.domain.publication import canonical_hash

    return canonical_hash(
        {
            "idempotency": "fact_normalization_run/v1",
            "authority": authority.model_dump(mode="json"),
            "prompt_version_id": prompt_version_id,
            "model_config_id": model_config_id,
            "input_scope_sha256": input_scope_sha256,
            "contract_version": contract_version,
        }
    )


class FactNormalizationRun(Phase5Model):
    """一次规范化运行：冻结权威元组、幂等键、Prompt/ModelConfig 与输入范围哈希。

    Agent 只写候选与未解决项，不能写接受事实、冲突裁决、Expectation 最终状态或入排
    结论。失败或被拒候选不污染上一活动 Profile。
    """

    run_id: str = Field(min_length=1)
    authority: FactAuthority
    idempotency_key: str = Field(min_length=1)
    prompt_version_id: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
    input_scope_sha256: str = Field(pattern=_SHA256)
    status: FactNormalizationRunStatus
    created_at: datetime
    created_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_run(self) -> "FactNormalizationRun":
        _require_utc(self.created_at, "created_at")
        expected = fact_run_idempotency_key(
            authority=self.authority,
            prompt_version_id=self.prompt_version_id,
            model_config_id=self.model_config_id,
            input_scope_sha256=self.input_scope_sha256,
        )
        if self.idempotency_key != expected:
            raise ValueError("运行幂等键与权威元组/PromptVersion/ModelConfig/输入范围不一致")
        return self


class FactNormalizationCall(Phase5Model):
    """一次规范化调用：默认每个逻辑文档一次；超长文档按连续页组切片。

    每次调用显式声明页清单，页覆盖门禁要求所有页已处理或有逐页未解决原因；整页
    遗漏、空输出、跨节点定位、虚构定位或活动指针变化均失败，不生成空 Profile。
    """

    call_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    logical_document_id: str = Field(min_length=1)
    page_numbers: list[int] = Field(min_length=1)
    status: FactCallStatus
    input_sha256: str = Field(pattern=_SHA256)
    raw_output_sha256: str | None = Field(default=None, pattern=_SHA256)
    created_at: datetime

    @model_validator(mode="after")
    def validate_call(self) -> "FactNormalizationCall":
        _require_utc(self.created_at, "created_at")
        pages = self.page_numbers
        if pages != sorted(set(pages)) or any(p < 1 for p in pages):
            raise ValueError("调用页清单必须升序、无重复且页码从 1 起")
        return self


class FactGateResult(Phase5Model):
    """逐候选门禁结果（设计书 §4.2 顺序）；ACCEPTED 可空原因，REJECTED/BLOCKED 必须说明。"""

    gate_result_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    gate: FactGate
    outcome: GateOutcome
    reasons: list[str] = Field(default_factory=list)
    created_at: datetime

    @model_validator(mode="after")
    def validate_result(self) -> "FactGateResult":
        _require_utc(self.created_at, "created_at")
        if self.outcome != GateOutcome.ACCEPTED and not self.reasons:
            raise ValueError("被拒或阻断的门禁结果必须给出原因")
        return self
