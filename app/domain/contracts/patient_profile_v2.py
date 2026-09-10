"""Phase 5 Patient Profile v2 领域合同（Slice 5.5，worker_01，纯校验，无存储）。

不可变 Patient Profile revision、13 条主题泳道、确定性首屏突出集合与严格验证的合同
层，覆盖 PRD P5-R08 / P5-AC08 / P5-AC09 与设计书 §5.3：

- ``PatientProfileRevisionV2``  不可变 Profile revision，绑定不可变权威元组、
  Profile 状态、审核阶段、13 条泳道与首屏突出集合；``succeeded`` 必须携带完整
  确定性投影，``generating`` / ``failed`` 是显式状态记录（不能伪装成空成功
  Profile），``stale`` 是对照当前 ReviewEpisode 权威派生的完整旧投影；
- ``ProfileItem``              单条 Profile 条目，通过类型化身份
  （``kind`` + ``source_id``）引用已发布事实/事件/暴露/冲突/期望；条目只携带
  结构化展示字段（时间/记录时间分离、部分日期范围、来源强度、全部定位与规则身份），
  绝不从合同之外发明临床措辞；
- ``ProfileHighlight``         首屏突出集合：全量条目的确定性子集，带显式结构化
  ``ProfileHighlightReason``；``FactRuleLink`` 本身永不是突出原因；
- ``ProfileLaneAssignment``    事实/事件到 13 条泳道的显式归属（typed
  ``kind + source_id + lane``），由发布服务提供，投影只消费、绝不猜测；
- ``PROFILE_LANE_ORDER``       13 条泳道的稳定展示顺序；
- ``profile_item_identity`` / ``profile_revision_identity`` 稳定身份推导。

Slice 5.5 硬不变量：Profile 只读已发布 v2 合同（不读 fixture/旧事实）；不显示入排
主结论、行动数量或通过/不通过标签；``not_due`` 期望保留在全量 Profile 但不是当前
到期突出；``succeeded`` 必须完整、``generating``/``failed`` 不能冒充成功。泳道归类
绝不基于 fact_type/event_type 共享词汇表（那会形成项目特异系统规则）；事实/事件
泳道只来自显式 ``ProfileLaneAssignment``，exposure 固定 MEDICATION，conflict/
expectation 固定 EVIDENCE_QUALITY。首屏突出不接收无来源旁路信号；OCR/解析风险与
溯源突出只由 ``EvidenceExpectationV2(status=observed_weak, ...)`` 触发。
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from .common import ContractModel, ScalarValue
from .enums import (
    DurationStatus,
    ExpectationStatus,
    FactPolarity,
    GapType,
    ProfileLane,
    ReviewStage,
    SourceStrength,
    StableEnum,
)
from .facts import FactAuthority, PartialDateRange

__all__ = [
    "ALL_PROFILE_LANES",
    "PROFILE_LANE_ORDER",
    "PatientProfileRevisionV2",
    "ProfileHighlight",
    "ProfileHighlightReason",
    "ProfileItem",
    "ProfileItemKind",
    "ProfileLaneAssignment",
    "ProfileLaneSection",
    "ProfileStatus",
    "profile_item_identity",
    "profile_items",
    "profile_revision_identity",
]


class ProfilePhase5Model(ContractModel):
    """Phase 5 Profile 合同基类：与 legacy ``fixture/v1`` 合同明确区分。"""

    schema_version: Literal["phase5/v1"] = "phase5/v1"


def _require_utc(value: datetime, field_name: str) -> None:
    """拒绝非 UTC 时区或 naive 时间戳（与 Phase 4/5 合同边界一致）。"""
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise ValueError(f"{field_name} 必须携带 UTC 时区")
    if offset.total_seconds() != 0:
        raise ValueError(f"{field_name} 必须使用 UTC 时区")


def _require_sorted_unique(values: list[str], label: str) -> None:
    if values != sorted(set(values)):
        raise ValueError(f"{label} 必须按 ID 排序且不得重复")


# --------------------------------------------------------------------------- 泳道


class ProfileItemKind(StableEnum):
    """Profile 条目引用的已发布 v2 实体类型（类型化身份）。"""

    FACT = "fact"
    EVENT = "event"
    EXPOSURE = "exposure"
    CONFLICT = "conflict"
    EXPECTATION = "expectation"


class ProfileStatus(StableEnum):
    """Profile revision 状态（机器值，与 0013 检查约束一致）。

    - ``succeeded``  完整确定性投影（带全量泳道与首屏突出集合）；
    - ``generating`` 生成中（显式状态记录，无投影）；
    - ``failed``     失败（显式状态记录，无投影）；
    - ``stale``      对照当前 ReviewEpisode 权威派生的完整旧投影（读取时派生，
                     不改写历史行）。
    """

    SUCCEEDED = "succeeded"
    GENERATING = "generating"
    FAILED = "failed"
    STALE = "stale"


class ProfileHighlightReason(StableEnum):
    """首屏突出原因的完整允许集（显式结构化，绝不从协议阈值/关键词/模型置信度推导）。

    单纯存在 FactRuleLink 不是突出原因。``source_report_abnormal/critical/trend``
    保留为未来已发布合同结构化字段扩展点，本轮投影不产生这些原因（不得由无来源
    旁路信号触发）。
    """

    UNRESOLVED_CONFLICT = "unresolved_conflict"
    CURRENT_DUE_EXPECTATION_GAP = "current_due_expectation_gap"
    WEAK_SOURCE_POSITIVE_LONG_TERM_HISTORY = "weak_source_positive_long_term_history"
    STRUCTURED_OCR_OR_PARSE_RISK = "structured_ocr_or_parse_risk"
    SOURCE_REPORT_ABNORMAL = "source_report_abnormal"
    SOURCE_REPORT_CRITICAL = "source_report_critical"
    SOURCE_REPORT_TREND = "source_report_trend"


#: 13 条主题泳道的稳定展示顺序（含可能为空的泳道，绝不静默省略临床类别）。
PROFILE_LANE_ORDER: tuple[ProfileLane, ...] = (
    ProfileLane.STUDY_MILESTONE,
    ProfileLane.DEMOGRAPHICS,
    ProfileLane.TARGET_DISEASE,
    ProfileLane.SYMPTOMS_SIGNS,
    ProfileLane.MEDICAL_HISTORY,
    ProfileLane.MEDICATION,
    ProfileLane.NON_DRUG_TREATMENT,
    ProfileLane.TEST_EXAM_SCORE,
    ProfileLane.ALLERGY_INFECTION_IMMUNE,
    ProfileLane.REPRODUCTIVE,
    ProfileLane.SOCIAL_ENVIRONMENTAL,
    ProfileLane.SPECIAL_HISTORY,
    ProfileLane.EVIDENCE_QUALITY,
)

ALL_PROFILE_LANES: frozenset[ProfileLane] = frozenset(PROFILE_LANE_ORDER)


# --------------------------------------------------------------------------- 泳道归属


class ProfileLaneAssignment(ContractModel):
    """事实/事件到 13 条泳道的显式归属（由发布服务提供，投影绝不猜测）。

    typed ``kind + source_id + lane``：``kind`` 只允许 fact/event；``lane`` 必须是
    13 条主题泳道之一。exposure 固定 MEDICATION、conflict/expectation 固定
    EVIDENCE_QUALITY，不需要也不允许 assignment（多余归属会被投影拒绝）。
    此结构将在 Codex 后续把 ``profile_lane`` 加入 Normalizer/发布合同时由服务提供。
    """

    model_config = ConfigDict(extra="forbid")

    kind: ProfileItemKind
    source_id: str = Field(min_length=1)
    lane: ProfileLane

    @model_validator(mode="after")
    def validate_assignment(self) -> "ProfileLaneAssignment":
        if self.kind not in (ProfileItemKind.FACT, ProfileItemKind.EVENT):
            raise ValueError("ProfileLaneAssignment 只允许 fact/event 归属")
        if self.lane not in ALL_PROFILE_LANES:
            raise ValueError("ProfileLaneAssignment 泳道必须属于 13 条主题泳道")
        return self


# --------------------------------------------------------------------------- 稳定身份


def profile_item_identity(kind: ProfileItemKind, source_id: str) -> str:
    """Profile 条目稳定身份：类型化实体身份，一次发布实体恰好一条条目。"""
    from app.domain.publication import canonical_hash

    return "profile-item:" + canonical_hash(
        {"kind": kind.value, "source_id": source_id}
    )[:32]


def profile_revision_identity(review_episode_id: str, revision: int) -> str:
    """Profile revision 稳定身份：``(review_episode_id, revision)`` 唯一。"""
    from app.domain.publication import canonical_hash

    return "profile:" + canonical_hash(
        {"review_episode_id": review_episode_id, "revision": revision}
    )[:32]


# --------------------------------------------------------------------------- Profile 条目


class ProfileItem(ContractModel):
    """单条 Profile 条目：通过类型化身份引用已发布 v2 实体，只携带结构化展示字段。

    事件时间（``start_range``/``end_range`` 与 ``duration_status``）与记录时间
    （``record_time``）分开保存；部分日期范围/精度、来源强度、全部定位 ID 与精确
    规则身份（``requirement_ids``/``template_id``）原样保留。``title``/``subtitle``
    由投影从源合同结构化字段确定性组合，绝不发明源合同之外的临床措辞。
    """

    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1)
    lane: ProfileLane
    kind: ProfileItemKind
    source_id: str = Field(min_length=1)
    source_revision: int = Field(ge=1)
    title: str = Field(min_length=1)
    subtitle: str | None = None

    # 时间线（事件发生时间与记录时间分离）
    start_range: PartialDateRange | None = None
    end_range: PartialDateRange | None = None
    duration_status: DurationStatus | None = None
    record_time: datetime | None = None

    # 溯源与定位
    source_strength: SourceStrength | None = None
    locator_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)

    # 事实
    polarity: FactPolarity | None = None
    asserted_object: str | None = None
    value: ScalarValue | None = None
    unit: str | None = None

    # 事件
    event_type: str | None = None

    # 暴露
    medication_name: str | None = None
    category: str | None = None
    indication: str | None = None
    dose: str | None = None
    frequency: str | None = None
    route: str | None = None

    # 实体引用闭包（事件/暴露引用事实；期望引用覆盖事实）
    fact_ids: list[str] = Field(default_factory=list)

    # 冲突
    conflict_member_kind: Literal["fact", "event", "exposure"] | None = None
    conflict_member_ids: list[str] = Field(default_factory=list)
    conflict_resolution_revision: int | None = None

    # 期望
    template_id: str | None = None
    expectation_status: ExpectationStatus | None = None
    gap_type: GapType | None = None
    gap_detail: str | None = None
    provenance_followup: bool = False
    provenance_reason: str | None = None

    @model_validator(mode="after")
    def validate_item(self) -> "ProfileItem":
        expected_id = profile_item_identity(self.kind, self.source_id)
        if self.item_id != expected_id:
            raise ValueError("ProfileItem ID 与 kind/source_id 稳定身份不一致")
        if self.lane not in ALL_PROFILE_LANES:
            raise ValueError("Profile 条目必须属于 13 条主题泳道之一")
        _require_sorted_unique(self.locator_ids, "Profile 条目定位")
        _require_sorted_unique(self.requirement_ids, "Profile 条目资料要求")
        _require_sorted_unique(self.fact_ids, "Profile 条目事实引用")
        _require_sorted_unique(self.conflict_member_ids, "Profile 条目冲突成员")
        if self.record_time is not None:
            _require_utc(self.record_time, "Profile 条目记录时间")
        if self.kind == ProfileItemKind.FACT:
            self._validate_fact()
        elif self.kind == ProfileItemKind.EVENT:
            self._validate_event()
        elif self.kind == ProfileItemKind.EXPOSURE:
            self._validate_exposure()
        elif self.kind == ProfileItemKind.CONFLICT:
            self._validate_conflict()
        else:  # EXPECTATION
            self._validate_expectation()
        return self

    def _forbid(self, label: str, present: bool) -> None:
        if present:
            raise ValueError(f"{label} 不属于 {self.kind.value} Profile 条目")

    def _validate_fact(self) -> None:
        if self.polarity is None or self.asserted_object is None or self.source_strength is None:
            raise ValueError("事实 Profile 条目必须携带极性、被断言对象与来源强度")
        if not self.locator_ids:
            raise ValueError("事实 Profile 条目必须携带定位")
        if self.polarity == FactPolarity.UNKNOWN:
            if self.value is not None or self.unit is not None:
                raise ValueError("未知极性事实 Profile 条目不能携带被断言值或单位")
        else:
            if self.value is None:
                raise ValueError("肯定或否定事实 Profile 条目必须携带被断言的规范值")
            if isinstance(self.value, (int, float)) and not isinstance(self.value, bool) and not self.unit:
                raise ValueError("数值事实 Profile 条目必须声明单位")
        if self.unit is not None and self.value is None:
            raise ValueError("事实 Profile 条目不能在没有值时携带单位")
        for label, value in (
            ("事件类型", self.event_type),
            ("药名", self.medication_name),
            ("类别", self.category),
            ("适应证", self.indication),
            ("剂量", self.dose),
            ("频次", self.frequency),
            ("途径", self.route),
            ("结束日期范围", self.end_range),
            ("持续状态", self.duration_status),
            ("模板身份", self.template_id),
            ("期望状态", self.expectation_status),
            ("缺口类型", self.gap_type),
            ("缺口说明", self.gap_detail),
            ("冲突成员类型", self.conflict_member_kind),
            ("冲突解决修订", self.conflict_resolution_revision),
        ):
            self._forbid(label, value is not None)
        if self.provenance_followup:
            raise ValueError("溯源提醒 不属于 fact Profile 条目")
        if self.provenance_reason is not None:
            raise ValueError("溯源原因 不属于 fact Profile 条目")
        if self.fact_ids or self.conflict_member_ids:
            raise ValueError("事实 Profile 条目不能携带实体引用")

    def _validate_event(self) -> None:
        if self.event_type is None or self.source_strength is None or self.duration_status is None:
            raise ValueError("事件 Profile 条目必须携带事件类型、来源强度与持续状态")
        if not self.fact_ids:
            raise ValueError("事件 Profile 条目必须引用至少一个已发布事实")
        if not self.locator_ids:
            raise ValueError("事件 Profile 条目必须携带定位")
        if self.requirement_ids:
            raise ValueError("事件 Profile 条目不能携带资料要求")
        for label, value in (
            ("极性", self.polarity),
            ("被断言对象", self.asserted_object),
            ("被断言值", self.value),
            ("单位", self.unit),
            ("药名", self.medication_name),
            ("类别", self.category),
            ("适应证", self.indication),
            ("剂量", self.dose),
            ("频次", self.frequency),
            ("途径", self.route),
            ("模板身份", self.template_id),
            ("期望状态", self.expectation_status),
            ("缺口类型", self.gap_type),
            ("缺口说明", self.gap_detail),
            ("冲突成员类型", self.conflict_member_kind),
            ("冲突解决修订", self.conflict_resolution_revision),
        ):
            self._forbid(label, value is not None)
        if self.provenance_followup:
            raise ValueError("溯源提醒 不属于 event Profile 条目")
        if self.provenance_reason is not None:
            raise ValueError("溯源原因 不属于 event Profile 条目")
        if self.conflict_member_ids:
            raise ValueError("事件 Profile 条目不能携带冲突成员")

    def _validate_exposure(self) -> None:
        if self.medication_name is None or self.source_strength is None or self.duration_status is None:
            raise ValueError("暴露 Profile 条目必须携带药名、来源强度与持续状态")
        if not self.fact_ids:
            raise ValueError("暴露 Profile 条目必须引用至少一个已发布事实")
        if not self.locator_ids:
            raise ValueError("暴露 Profile 条目必须携带定位")
        if self.requirement_ids:
            raise ValueError("暴露 Profile 条目不能携带资料要求")
        # unit 是暴露剂量单位（与事实规范值单位共享字段），允许携带。
        if self.duration_status == DurationStatus.ENDED and self.end_range is None:
            raise ValueError("已结束暴露 Profile 条目必须由资料明确给出终止日期范围")
        if self.duration_status == DurationStatus.ONGOING and self.end_range is not None:
            raise ValueError("持续暴露 Profile 条目不能携带终止日期范围")
        for label, value in (
            ("极性", self.polarity),
            ("被断言对象", self.asserted_object),
            ("被断言值", self.value),
            ("事件类型", self.event_type),
            ("模板身份", self.template_id),
            ("期望状态", self.expectation_status),
            ("缺口类型", self.gap_type),
            ("缺口说明", self.gap_detail),
            ("冲突成员类型", self.conflict_member_kind),
            ("冲突解决修订", self.conflict_resolution_revision),
        ):
            self._forbid(label, value is not None)
        if self.provenance_followup:
            raise ValueError("溯源提醒 不属于 exposure Profile 条目")
        if self.provenance_reason is not None:
            raise ValueError("溯源原因 不属于 exposure Profile 条目")
        if self.conflict_member_ids:
            raise ValueError("暴露 Profile 条目不能携带冲突成员")

    def _validate_conflict(self) -> None:
        if self.conflict_member_kind is None or self.conflict_resolution_revision is None:
            raise ValueError("冲突 Profile 条目必须携带成员类型与解决修订")
        if len(self.conflict_member_ids) < 2:
            raise ValueError("冲突 Profile 条目必须并列至少两个同类型成员")
        if not self.locator_ids:
            raise ValueError("冲突 Profile 条目必须携带定位")
        for label, value in (
            ("极性", self.polarity),
            ("被断言对象", self.asserted_object),
            ("被断言值", self.value),
            ("单位", self.unit),
            ("事件类型", self.event_type),
            ("药名", self.medication_name),
            ("类别", self.category),
            ("适应证", self.indication),
            ("剂量", self.dose),
            ("频次", self.frequency),
            ("途径", self.route),
            ("来源强度", self.source_strength),
            ("开始日期范围", self.start_range),
            ("结束日期范围", self.end_range),
            ("持续状态", self.duration_status),
            ("记录时间", self.record_time),
            ("模板身份", self.template_id),
            ("期望状态", self.expectation_status),
            ("缺口类型", self.gap_type),
            ("缺口说明", self.gap_detail),
        ):
            self._forbid(label, value is not None)
        if self.provenance_followup:
            raise ValueError("溯源提醒 不属于 conflict Profile 条目")
        if self.provenance_reason is not None:
            raise ValueError("溯源原因 不属于 conflict Profile 条目")
        if self.fact_ids or self.requirement_ids:
            raise ValueError("冲突 Profile 条目不能携带实体引用或资料要求")

    def _validate_expectation(self) -> None:
        if self.template_id is None or self.expectation_status is None:
            raise ValueError("期望 Profile 条目必须携带模板身份与期望状态")
        if self.requirement_ids:
            raise ValueError("期望 Profile 条目不能携带资料要求")
        for label, value in (
            ("极性", self.polarity),
            ("被断言对象", self.asserted_object),
            ("被断言值", self.value),
            ("单位", self.unit),
            ("事件类型", self.event_type),
            ("药名", self.medication_name),
            ("类别", self.category),
            ("适应证", self.indication),
            ("剂量", self.dose),
            ("频次", self.frequency),
            ("途径", self.route),
            ("来源强度", self.source_strength),
            ("开始日期范围", self.start_range),
            ("结束日期范围", self.end_range),
            ("持续状态", self.duration_status),
            ("记录时间", self.record_time),
            ("冲突成员类型", self.conflict_member_kind),
            ("冲突解决修订", self.conflict_resolution_revision),
        ):
            self._forbid(label, value is not None)
        if self.conflict_member_ids:
            raise ValueError("期望 Profile 条目不能携带冲突成员")
        status = self.expectation_status
        if status == ExpectationStatus.NOT_DUE:
            if self.gap_type != GapType.FUTURE_STAGE_NOT_DUE:
                raise ValueError("尚未到期期望 Profile 条目必须使用 future_stage_not_due 缺口")
            if self.locator_ids or self.fact_ids:
                raise ValueError("尚未到期期望 Profile 条目不能携带定位或覆盖事实")
        elif status == ExpectationStatus.OBSERVED:
            if self.gap_type is not None:
                raise ValueError("完整证据期望 Profile 条目不能携带缺口")
            if not self.locator_ids or not self.fact_ids:
                raise ValueError("已观察期望 Profile 条目必须携带覆盖事实与定位")
        elif status == ExpectationStatus.OBSERVED_WEAK:
            if not self.locator_ids or not self.fact_ids:
                raise ValueError("较弱证据期望 Profile 条目必须携带覆盖事实与定位")
        elif status == ExpectationStatus.REFERENCED_MISSING:
            if self.gap_type != GapType.REFERENCED_FILE_MISSING:
                raise ValueError("已引用未提供期望 Profile 条目必须使用 referenced_file_missing 缺口")
            if self.locator_ids or self.fact_ids:
                raise ValueError("已引用未提供期望 Profile 条目不能携带定位或覆盖事实")
        else:  # ABSENT
            if self.gap_type is None:
                raise ValueError("未观察到期期望 Profile 条目必须给出具体缺口类型")
            if self.locator_ids or self.fact_ids:
                raise ValueError("未观察到期望 Profile 条目不能携带定位或覆盖事实")
        # 溯源提醒镜像 EvidenceExpectationV2：只有较弱证据 + 溯源/历史来源缺口才允许。
        if status == ExpectationStatus.OBSERVED_WEAK and self.gap_type in (
            GapType.PROVENANCE_FOLLOWUP,
            GapType.HISTORICAL_SOURCE_UNAVAILABLE,
        ):
            if not self.provenance_followup:
                raise ValueError("溯源/历史来源较弱证据期望必须携带溯源提醒")
        elif self.provenance_followup:
            raise ValueError("非溯源/历史来源缺口的期望不能携带溯源提醒")
        if self.provenance_reason is not None and not self.provenance_followup:
            raise ValueError("溯源原因只能伴随溯源提醒")


class ProfileLaneSection(ContractModel):
    """一条主题泳道：泳道 + 该泳道内确定排序的 Profile 条目（可为空）。"""

    lane: ProfileLane
    items: list[ProfileItem] = Field(default_factory=list)


# --------------------------------------------------------------------------- 突出


class ProfileHighlight(ContractModel):
    """首屏突出：全量 Profile 条目的确定性子集，带显式结构化原因。"""

    item_id: str = Field(min_length=1)
    reasons: list[ProfileHighlightReason] = Field(min_length=1)
    gap_type: GapType | None = None
    detail: str | None = None

    @model_validator(mode="after")
    def validate_highlight(self) -> "ProfileHighlight":
        if self.reasons != sorted(set(self.reasons)):
            raise ValueError("突出原因必须按枚举值排序且不得重复")
        if ProfileHighlightReason.CURRENT_DUE_EXPECTATION_GAP in self.reasons:
            if self.gap_type is None:
                raise ValueError("当前到期资料缺口突出必须给出具体缺口类型")
        elif self.gap_type is not None:
            raise ValueError("非当前到期缺口突出不能携带缺口类型")
        return self


# --------------------------------------------------------------------------- revision


class PatientProfileRevisionV2(ProfilePhase5Model):
    """不可变 Patient Profile revision：绑定权威元组、状态、审核阶段与 13 条泳道。

    - ``succeeded`` / ``stale`` 必须携带完整确定性投影（13 条泳道、突出集合与
      待核对数一致）；
    - ``generating`` / ``failed`` 是显式状态记录：无泳道、无突出、待核对数为 0，
      绝不伪装成空成功 Profile；
    - ``stale`` 是对照当前 ReviewEpisode 权威派生的完整旧投影（读取时派生，
      不改写历史行）；``(review_episode_id, revision)`` 唯一。
    """

    model_config = ConfigDict(extra="forbid")

    patient_profile_revision_id: str = Field(min_length=1)
    authority: FactAuthority
    status: ProfileStatus
    revision: int = Field(ge=1)
    review_stage: ReviewStage
    generated_at: datetime | None = None
    created_at: datetime
    pending_review_count: int = Field(ge=0)
    lanes: list[ProfileLaneSection] = Field(default_factory=list)
    highlights: list[ProfileHighlight] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_revision(self) -> "PatientProfileRevisionV2":
        _require_utc(self.created_at, "Profile created_at")
        if self.generated_at is not None:
            _require_utc(self.generated_at, "Profile generated_at")
        expected_id = profile_revision_identity(
            self.authority.review_episode_id, self.revision
        )
        if self.patient_profile_revision_id != expected_id:
            raise ValueError(
                "Patient Profile 修订编号与权威节点/revision 稳定身份不一致"
            )
        complete = self.status in (ProfileStatus.SUCCEEDED, ProfileStatus.STALE)
        if complete:
            self._validate_complete()
        else:
            self._validate_status_record()
        return self

    def _validate_complete(self) -> None:
        if self.generated_at is None:
            raise ValueError("成功/陈旧 Profile 必须携带生成时间")
        lanes = self.lanes
        if [section.lane for section in lanes] != list(PROFILE_LANE_ORDER):
            raise ValueError("Profile 必须按稳定展示顺序恰好包含 13 条泳道（含空泳道）")
        for section in lanes:
            for item in section.items:
                if item.lane != section.lane:
                    raise ValueError("Profile 条目泳道必须与其所在泳道一致")
        items = profile_items(self)
        item_ids = {item.item_id for item in items}
        if len(item_ids) != len(items):
            raise ValueError("Profile 条目 ID 必须唯一")
        for highlight in self.highlights:
            if highlight.item_id not in item_ids:
                raise ValueError(f"首屏突出引用不存在的 Profile 条目 {highlight.item_id}")
        if self.pending_review_count != len(self.highlights):
            raise ValueError("待核对数必须等于首屏突出集合大小")

    def _validate_status_record(self) -> None:
        if self.generated_at is not None:
            raise ValueError("生成中/失败 Profile 是显式状态记录，不能携带生成时间")
        if self.lanes or self.highlights or self.pending_review_count:
            raise ValueError(
                "生成中/失败 Profile 不能携带泳道/突出集合/待核对数，不得伪装成空成功 Profile"
            )


def profile_items(revision: PatientProfileRevisionV2) -> list[ProfileItem]:
    """按 13 条泳道稳定展示顺序展开全部 Profile 条目。"""
    return [item for section in revision.lanes for item in section.items]
