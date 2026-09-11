"""Phase 5 Patient Profile HTTP 契约（Slice 5.5，worker_03，薄 DTO，无存储）。

只做协议转换：把不可变 :class:`PatientProfileRevisionV2` 领域合同映射为
带中文原生标签的请求/响应 DTO。本模块不导入 SQLAlchemy 或 ``app.storage``
（薄 API 边界验收由 AST 测试强制）。

约定：

- 机器值（status/revision/lane/kind/…）原样保留，供程序与测试使用；每个机器值
  旁配 ``*_label`` 自然中文字段，供医学监查员界面直接展示；
- 首屏突出只透出领域合同已允许的显式结构化原因，绝不从协议阈值/关键词推导；
- 证据深链同时提供条目定位身份、冻结权威元组，以及经过 Phase 4 定位门禁读取的
  资料版本、页码、定位精度和真实坐标；没有真实坐标时保持为空，不伪造红框；
- 不显示入排主结论、行动数量或通过/不通过标签。

中文词汇表暂置于本模块（Slice 5.5 授权文件边界内）；Codex 如需统一收敛到
``app/api/v2/vocabulary.py``，可直接迁移这些表而不改 DTO 形状。
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.api.v2.evidence_processing_schemas import LocatorDTO, locator_dto
from app.api.v2.vocabulary import review_stage_label
from app.domain.contracts.common import ScalarValue
from app.domain.contracts.evidence_locator import EvidenceLocatorArtifact
from app.domain.contracts.patient_profile_v2 import (
    PatientProfileRevisionV2,
    ProfileItem,
)

__all__ = [
    "DATE_PRECISION_LABELS",
    "DURATION_STATUS_LABELS",
    "EXPECTATION_STATUS_LABELS",
    "FACT_POLARITY_LABELS",
    "GAP_TYPE_LABELS",
    "PROFILE_HIGHLIGHT_REASON_LABELS",
    "PROFILE_ITEM_KIND_LABELS",
    "PROFILE_LANE_LABELS",
    "PROFILE_STATUS_LABELS",
    "SOURCE_STRENGTH_LABELS",
    "PatientProfileHistoryDTO",
    "PatientProfileRevisionDTO",
    "ProfileDateRangeDTO",
    "ProfileEvidenceNavigationDTO",
    "ProfileHighlightDTO",
    "ProfileItemDTO",
    "ProfileLaneSectionDTO",
    "profile_locator_ids",
    "profile_date_range_label",
    "profile_item_dto",
    "profile_revision_dto",
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# 中文原生词汇表（稳定机器值 -> 自然中文；未知值回退为机器值本身）
# ---------------------------------------------------------------------------


PROFILE_LANE_LABELS: dict[str, str] = {
    "study_milestone": "研究节点",
    "demographics": "人口学/基线",
    "target_disease": "目标疾病",
    "symptoms_signs": "症状体征",
    "medical_history": "病史",
    "medication": "药物暴露",
    "non_drug_treatment": "非药物治疗/操作",
    "test_exam_score": "检验检查/评分",
    "allergy_infection_immune": "过敏/感染/免疫",
    "reproductive": "生育",
    "social_environmental": "社会环境",
    "special_history": "家族史/特殊经历",
    "evidence_quality": "证据冲突与资料质量",
}

PROFILE_STATUS_LABELS: dict[str, str] = {
    "succeeded": "已生成",
    "generating": "生成中",
    "failed": "生成失败",
    "stale": "资料已更新，档案待重新生成",
}

PROFILE_ITEM_KIND_LABELS: dict[str, str] = {
    "fact": "事实",
    "event": "事件",
    "exposure": "用药暴露",
    "conflict": "证据冲突",
    "expectation": "资料期望",
}

PROFILE_HIGHLIGHT_REASON_LABELS: dict[str, str] = {
    "unresolved_conflict": "未解决冲突",
    "current_due_expectation_gap": "当前到期资料缺口",
    "weak_source_positive_long_term_history": "较弱来源阳性长期史",
    "structured_ocr_or_parse_risk": "识别或解析风险",
    "source_report_abnormal": "原报告异常",
    "source_report_critical": "原报告临界",
    "source_report_trend": "原报告趋势",
}

GAP_TYPE_LABELS: dict[str, str] = {
    "observation_unverified": "资料尚待核实",
    "record_incomplete": "病历记录不完整",
    "description_insufficient": "描述不充分",
    "historical_source_unavailable": "历史来源不可用",
    "referenced_file_missing": "已引用文件未提供",
    "required_procedure_not_done": "必要检查未执行",
    "result_fields_missing": "结果字段缺失",
    "date_or_anchor_missing": "日期或锚点缺失",
    "professional_judgment": "需专业判断",
    "source_conflict": "来源冲突",
    "ocr_or_parse_risk": "识别或解析风险",
    "interpretation_conflict": "解读冲突",
    "future_stage_not_due": "后续节点尚未到期",
    "provenance_followup": "需溯源核对",
}

EXPECTATION_STATUS_LABELS: dict[str, str] = {
    "observed": "证据完整",
    "observed_weak": "较弱证据",
    "referenced_missing": "已引用未提供",
    "absent": "未观察到",
    "not_due": "尚未到期",
}

SOURCE_STRENGTH_LABELS: dict[str, str] = {
    "contemporaneous_objective_result": "同期客观结果",
    "historical_primary_document": "既往原始资料",
    "current_study_chart_direct_record": "当前研究病历直接记录",
    "screening_record_transcription": "筛选病历转述",
    "unverifiable_source": "来源无法确认",
}

DURATION_STATUS_LABELS: dict[str, str] = {
    "ongoing": "持续",
    "ended": "已结束",
    "intermittent": "间歇",
    "single": "单次",
    "unknown": "未知",
}

FACT_POLARITY_LABELS: dict[str, str] = {
    "affirmed": "肯定",
    "negated": "否定",
    "unknown": "未知",
}

DATE_PRECISION_LABELS: dict[str, str] = {
    "day": "日",
    "month": "月",
    "year": "年",
    "unknown": "未知",
}


def _label(table: dict[str, str], value: str | None) -> str | None:
    if value is None:
        return None
    return table.get(value, value)


def profile_date_range_label(value: str | None) -> str | None:
    return _label(DATE_PRECISION_LABELS, value)


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


class ProfileDateRangeDTO(_StrictModel):
    """部分日期范围：保留来源原文、精度机器值/中文标签与确定性上下界。"""

    source_text: str | None = None
    precision: str | None = None
    precision_label: str | None = None
    lower_bound: str | None = None
    upper_bound: str | None = None


class ProfileEvidenceNavigationDTO(_StrictModel):
    """证据深链导航上下文：冻结权威元组中的 Phase 4 导航身份。

    与每条目 ``locator_ids`` 及 revision 级 ``evidence_locators`` 一起构成到
    Phase 4 证据查看器的深链。
    """

    project_id: str
    subject_id: str
    review_episode_id: str
    evidence_snapshot_v2_id: str
    complete_processing_revision_id: str


class ProfileItemDTO(_StrictModel):
    """单条 Profile 条目 DTO：领域合同字段原样 + 中文标签，不发明临床措辞。"""

    item_id: str
    lane: str
    lane_label: str
    kind: str
    kind_label: str
    source_id: str
    source_revision: int
    title: str
    subtitle: str | None = None

    # 时间线（事件发生时间与记录时间分离）
    start_range: ProfileDateRangeDTO | None = None
    end_range: ProfileDateRangeDTO | None = None
    duration_status: str | None = None
    duration_status_label: str | None = None
    record_time: datetime | None = None

    # 溯源与定位
    source_strength: str | None = None
    source_strength_label: str | None = None
    locator_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)

    # 事实
    polarity: str | None = None
    polarity_label: str | None = None
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

    # 实体引用闭包
    fact_ids: list[str] = Field(default_factory=list)

    # 冲突
    conflict_member_kind: str | None = None
    conflict_member_ids: list[str] = Field(default_factory=list)
    conflict_resolution_revision: int | None = None

    # 期望
    template_id: str | None = None
    expectation_status: str | None = None
    expectation_status_label: str | None = None
    gap_type: str | None = None
    gap_type_label: str | None = None
    gap_detail: str | None = None
    provenance_followup: bool = False
    provenance_reason: str | None = None


class ProfileLaneSectionDTO(_StrictModel):
    """一条主题泳道：泳道机器值/中文标签 + 该泳道内确定排序的条目（可为空）。"""

    lane: str
    lane_label: str
    items: list[ProfileItemDTO] = Field(default_factory=list)


class ProfileHighlightDTO(_StrictModel):
    """首屏突出 DTO：条目身份 + 显式结构化原因（机器值与中文标签并列）。"""

    item_id: str
    reasons: list[str]
    reason_labels: list[str]
    gap_type: str | None = None
    gap_type_label: str | None = None
    detail: str | None = None


class PatientProfileRevisionDTO(_StrictModel):
    """不可变 Patient Profile revision DTO（状态/历史/证据深链一次给全）。"""

    patient_profile_revision_id: str
    schema_version: str
    status: str
    status_label: str
    revision: int
    review_stage: str
    review_stage_label: str
    generated_at: datetime | None = None
    created_at: datetime
    pending_review_count: int
    lanes: list[ProfileLaneSectionDTO] = Field(default_factory=list)
    highlights: list[ProfileHighlightDTO] = Field(default_factory=list)
    evidence_locators: list[LocatorDTO] = Field(default_factory=list)
    evidence_navigation: ProfileEvidenceNavigationDTO


class PatientProfileHistoryDTO(_StrictModel):
    """审核节点 Profile 历史：全部 revision 按 revision 升序。"""

    subject_id: str
    review_episode_id: str
    items: list[PatientProfileRevisionDTO] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 合同 -> DTO 映射（纯协议转换，不读取存储、不做领域判断）
# ---------------------------------------------------------------------------


def _as_utc(value: datetime | None) -> datetime | None:
    """恢复存储层 UTC 约定（payload 内时间为 aware UTC；naive 时补回时区）。"""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _date_range_dto(value: Any) -> ProfileDateRangeDTO | None:
    if value is None:
        return None
    precision = getattr(value, "precision", None)
    precision_value = precision.value if hasattr(precision, "value") else precision
    return ProfileDateRangeDTO(
        source_text=getattr(value, "source_text", None),
        precision=precision_value,
        precision_label=profile_date_range_label(str(precision_value))
        if precision_value is not None
        else None,
        lower_bound=(
            value.lower_bound.isoformat() if value.lower_bound is not None else None
        ),
        upper_bound=(
            value.upper_bound.isoformat() if value.upper_bound is not None else None
        ),
    )


def profile_item_dto(item: ProfileItem) -> ProfileItemDTO:
    """把领域 Profile 条目映射为中文原生 DTO（机器值 + 标签，无临床推断）。"""
    lane = item.lane.value if hasattr(item.lane, "value") else item.lane
    kind = item.kind.value if hasattr(item.kind, "value") else item.kind
    return ProfileItemDTO(
        item_id=item.item_id,
        lane=lane,
        lane_label=PROFILE_LANE_LABELS.get(lane, lane),
        kind=kind,
        kind_label=PROFILE_ITEM_KIND_LABELS.get(kind, kind),
        source_id=item.source_id,
        source_revision=item.source_revision,
        title=item.title,
        subtitle=item.subtitle,
        start_range=_date_range_dto(item.start_range),
        end_range=_date_range_dto(item.end_range),
        duration_status=(
            item.duration_status.value
            if hasattr(item.duration_status, "value")
            else item.duration_status
        ),
        duration_status_label=(
            DURATION_STATUS_LABELS.get(
                item.duration_status.value, item.duration_status.value
            )
            if hasattr(item.duration_status, "value")
            else item.duration_status
        ),
        record_time=_as_utc(item.record_time),
        source_strength=(
            item.source_strength.value
            if hasattr(item.source_strength, "value")
            else item.source_strength
        ),
        source_strength_label=(
            SOURCE_STRENGTH_LABELS.get(
                item.source_strength.value, item.source_strength.value
            )
            if hasattr(item.source_strength, "value")
            else item.source_strength
        ),
        locator_ids=list(item.locator_ids),
        requirement_ids=list(item.requirement_ids),
        polarity=(
            item.polarity.value if hasattr(item.polarity, "value") else item.polarity
        ),
        polarity_label=(
            FACT_POLARITY_LABELS.get(item.polarity.value, item.polarity.value)
            if hasattr(item.polarity, "value")
            else item.polarity
        ),
        asserted_object=item.asserted_object,
        value=item.value,
        unit=item.unit,
        event_type=item.event_type,
        medication_name=item.medication_name,
        category=item.category,
        indication=item.indication,
        dose=item.dose,
        frequency=item.frequency,
        route=item.route,
        fact_ids=list(item.fact_ids),
        conflict_member_kind=item.conflict_member_kind,
        conflict_member_ids=list(item.conflict_member_ids),
        conflict_resolution_revision=(
            # 域模型用 0 表示未解决；wire 契约为“正整数或 null（null=未解决）”。
            item.conflict_resolution_revision
            if (item.conflict_resolution_revision or 0) > 0
            else None
        ),
        template_id=item.template_id,
        expectation_status=(
            item.expectation_status.value
            if hasattr(item.expectation_status, "value")
            else item.expectation_status
        ),
        expectation_status_label=(
            "资料尚待核实"
            if item.gap_type == "observation_unverified"
            else
            EXPECTATION_STATUS_LABELS.get(
                item.expectation_status.value, item.expectation_status.value
            )
            if hasattr(item.expectation_status, "value")
            else item.expectation_status
        ),
        gap_type=(
            item.gap_type.value if hasattr(item.gap_type, "value") else item.gap_type
        ),
        gap_type_label=(
            GAP_TYPE_LABELS.get(item.gap_type.value, item.gap_type.value)
            if hasattr(item.gap_type, "value")
            else item.gap_type
        ),
        gap_detail=item.gap_detail,
        provenance_followup=item.provenance_followup,
        provenance_reason=item.provenance_reason,
    )


def profile_locator_ids(revision: PatientProfileRevisionV2) -> list[str]:
    """返回 revision 全部条目引用的定位身份，去重并稳定排序。"""
    return sorted(
        {
            locator_id
            for section in revision.lanes
            for item in section.items
            for locator_id in item.locator_ids
        }
    )


def profile_revision_dto(
    revision: PatientProfileRevisionV2,
    *,
    locators: dict[str, EvidenceLocatorArtifact] | None = None,
) -> PatientProfileRevisionDTO:
    """把领域 revision 映射为带证据导航上下文的 DTO（状态/历史/深链一次给全）。"""
    status = revision.status.value if hasattr(revision.status, "value") else revision.status
    stage = (
        revision.review_stage.value
        if hasattr(revision.review_stage, "value")
        else revision.review_stage
    )
    authority = revision.authority
    required_locator_ids = profile_locator_ids(revision)
    locator_map = locators or {}
    missing_locator_ids = [
        locator_id for locator_id in required_locator_ids if locator_id not in locator_map
    ]
    if missing_locator_ids:
        raise ValueError("病历档案引用的原文定位没有完整解析")
    return PatientProfileRevisionDTO(
        patient_profile_revision_id=revision.patient_profile_revision_id,
        schema_version=revision.schema_version,
        status=status,
        status_label=PROFILE_STATUS_LABELS.get(status, status),
        revision=revision.revision,
        review_stage=stage,
        review_stage_label=review_stage_label(str(stage)),
        generated_at=_as_utc(revision.generated_at),
        created_at=_as_utc(revision.created_at),
        pending_review_count=revision.pending_review_count,
        lanes=[
            ProfileLaneSectionDTO(
                lane=section.lane.value,
                lane_label=PROFILE_LANE_LABELS.get(
                    section.lane.value, section.lane.value
                ),
                items=[profile_item_dto(item) for item in section.items],
            )
            for section in revision.lanes
        ],
        highlights=[
            ProfileHighlightDTO(
                item_id=highlight.item_id,
                reasons=[reason.value for reason in highlight.reasons],
                reason_labels=[
                    PROFILE_HIGHLIGHT_REASON_LABELS.get(reason.value, reason.value)
                    for reason in highlight.reasons
                ],
                gap_type=(
                    highlight.gap_type.value
                    if highlight.gap_type is not None
                    else None
                ),
                gap_type_label=(
                    GAP_TYPE_LABELS.get(
                        highlight.gap_type.value, highlight.gap_type.value
                    )
                    if highlight.gap_type is not None
                    else None
                ),
                detail=highlight.detail,
            )
            for highlight in revision.highlights
        ],
        evidence_locators=[
            locator_dto(locator_map[locator_id])
            for locator_id in required_locator_ids
        ],
        evidence_navigation=ProfileEvidenceNavigationDTO(
            project_id=authority.project_id,
            subject_id=authority.subject_id,
            review_episode_id=authority.review_episode_id,
            evidence_snapshot_v2_id=authority.evidence_snapshot_v2_id,
            complete_processing_revision_id=authority.complete_processing_revision_id,
        ),
    )
