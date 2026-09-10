"""Phase 5 Patient Profile 投影（Slice 5.5，worker_01，纯确定性投影，无存储）。

从已发布 v2 合同（``ClinicalFactV2`` / ``ClinicalEventV2`` /
``MedicationExposureV2`` / ``ClinicalConflictGroupV2`` / ``EvidenceExpectationV2``）
与显式 ``ProfileLaneAssignment`` 生成不可变 ``PatientProfileRevisionV2``：

- 13 条主题泳道按稳定展示顺序生成（含空泳道）；事实/事件泳道只来自调用方提供的
  显式 ``ProfileLaneAssignment``（typed ``kind + source_id + lane``），每个
  fact/event 恰好一个归属，缺失/重复/多余/跨类型一律 ``ProjectionInputError``，
  投影绝不基于 fact_type/event_type 猜测（那会形成项目特异系统规则）；exposure
  固定 MEDICATION，conflict/expectation 固定 EVIDENCE_QUALITY；
- 条目字段由源合同逐字复制（定位闭包、资料要求、事实引用、日期/记录时间分离、
  来源强度），``title``/``subtitle`` 由结构化字段确定性组合，绝不发明源合同之外
  的临床措辞；``FactRuleLink``（``supported_requirement_ids``）本身永不是突出原因；
- 首屏突出集合是全量条目的确定性子集，只由已发布合同状态触发：未解决冲突
  （``resolution_revision == 0``）、当前到期资料缺口（``absent`` /
  ``referenced_missing``）、较弱证据的 OCR/解析风险
  （``observed_weak + gap_type=ocr_or_parse_risk``）、较弱证据的溯源提醒
  （``observed_weak + gap_type in provenance_followup/historical_source_unavailable
  + provenance_followup=true``，突出对应期望条目）；``not_due`` 期望保留在全量
  Profile 但不突出；单个较弱来源事实本身不因来源强度自动突出；不存在无来源旁路
  信号（原报告异常/临界/趋势本轮不产生）；
- 本投影只生成 ``succeeded`` 完整投影；``generating`` / ``failed`` 是服务层显式
  状态记录，不由本投影构造。
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from app.domain.contracts.enums import (
    DurationStatus,
    ExpectationStatus,
    GapType,
    ProfileLane,
    ReviewStage,
    SourceStrength,
)
from app.domain.contracts.evidence_expectations_v2 import EvidenceExpectationV2
from app.domain.contracts.facts import (
    ClinicalConflictGroupV2,
    ClinicalEventV2,
    ClinicalFactV2,
    FactAuthority,
    MedicationExposureV2,
)
from app.domain.contracts.patient_profile_v2 import (
    PROFILE_LANE_ORDER,
    PatientProfileRevisionV2,
    ProfileHighlight,
    ProfileHighlightReason,
    ProfileItem,
    ProfileItemKind,
    ProfileLaneAssignment,
    ProfileLaneSection,
    ProfileStatus,
    profile_item_identity,
    profile_revision_identity,
)

__all__ = [
    "ProjectionInputError",
    "project_patient_profile",
]


class ProjectionInputError(ValueError):
    """投影输入不满足确定性前提（跨权威元组 / 泳道归属缺失/重复/多余/跨类型）。"""


# --------------------------------------------------------------------------- 中文标签
# 用户可见中文由稳定机器状态确定性映射，不解析自由文本；内部机器值不是用户文案。

_POLARITY_LABELS = {
    "affirmed": "有",
    "negated": "无",
    "unknown": "未知",
}

_DURATION_LABELS = {
    DurationStatus.ONGOING: "持续",
    DurationStatus.ENDED: "已结束",
    DurationStatus.INTERMITTENT: "间歇",
    DurationStatus.SINGLE: "单次",
    DurationStatus.UNKNOWN: "未知",
}

_EXPECTATION_LABELS = {
    ExpectationStatus.OBSERVED: "已观察",
    ExpectationStatus.OBSERVED_WEAK: "较弱证据",
    ExpectationStatus.REFERENCED_MISSING: "已引用未提供",
    ExpectationStatus.ABSENT: "未观察到",
    ExpectationStatus.NOT_DUE: "尚未到期",
}

_CONFLICT_HIGHLIGHT_DETAIL = "同一临床对象存在不兼容来源，并列展示，系统不择优"
_OCR_RISK_HIGHLIGHT_DETAIL = "受 OCR/解析风险影响，需人工校对后确认"
_WEAK_HISTORY_HIGHLIGHT_DETAIL = "覆盖证据为较弱来源，需加强溯源核对"


# --------------------------------------------------------------------------- 条目组合
# 条目结构化字段由源合同逐字复制（fidelity by construction）：定位闭包、资料要求、
# 事实引用、日期/记录时间、来源强度、极性/值/单位与修订号全部原样保留。


def _fact_item(fact: ClinicalFactV2, lane: ProfileLane) -> ProfileItem:
    return ProfileItem(
        item_id=profile_item_identity(ProfileItemKind.FACT, fact.fact_id),
        lane=lane,
        kind=ProfileItemKind.FACT,
        source_id=fact.fact_id,
        source_revision=fact.revision,
        title=fact.asserted_object,
        subtitle=_POLARITY_LABELS[fact.polarity.value],
        start_range=fact.date_range,
        record_time=fact.record_time,
        source_strength=fact.source_strength,
        locator_ids=sorted(set(fact.locator_ids)),
        requirement_ids=sorted(set(fact.supported_requirement_ids)),
        polarity=fact.polarity,
        asserted_object=fact.asserted_object,
        value=fact.value,
        unit=fact.unit,
    )


def _event_item(
    event: ClinicalEventV2,
    lane: ProfileLane,
    facts_by_id: dict[str, ClinicalFactV2],
) -> ProfileItem:
    missing_fact_ids = sorted(set(event.fact_ids) - set(facts_by_id))
    if missing_fact_ids:
        raise ProjectionInputError(
            f"事件 {event.event_id} 引用了未进入本次档案的事实：{', '.join(missing_fact_ids)}"
        )
    title = "、".join(
        sorted({facts_by_id[fact_id].asserted_object for fact_id in event.fact_ids})
    )
    return ProfileItem(
        item_id=profile_item_identity(ProfileItemKind.EVENT, event.event_id),
        lane=lane,
        kind=ProfileItemKind.EVENT,
        source_id=event.event_id,
        source_revision=event.revision,
        title=title,
        subtitle=_DURATION_LABELS[event.duration_status],
        start_range=event.start_range,
        end_range=event.end_range,
        duration_status=event.duration_status,
        record_time=event.record_time,
        source_strength=event.source_strength,
        locator_ids=sorted(set(event.locator_ids)),
        event_type=event.event_type,
        fact_ids=sorted(set(event.fact_ids)),
    )


def _exposure_item(exposure: MedicationExposureV2) -> ProfileItem:
    parts = []
    if exposure.dose:
        dose = exposure.dose
        unit = exposure.unit or ""
        parts.append(dose if unit and dose.casefold().endswith(unit.casefold()) else dose + unit)
    if exposure.frequency:
        parts.append(exposure.frequency)
    if exposure.route:
        parts.append(exposure.route)
    if exposure.indication:
        parts.append(exposure.indication)
    return ProfileItem(
        item_id=profile_item_identity(ProfileItemKind.EXPOSURE, exposure.exposure_id),
        lane=ProfileLane.MEDICATION,
        kind=ProfileItemKind.EXPOSURE,
        source_id=exposure.exposure_id,
        source_revision=exposure.revision,
        title=exposure.medication_name,
        subtitle="、".join(parts) if parts else None,
        start_range=exposure.start_range,
        end_range=exposure.end_range,
        duration_status=exposure.duration_status,
        record_time=exposure.record_time,
        source_strength=exposure.source_strength,
        locator_ids=sorted(set(exposure.locator_ids)),
        medication_name=exposure.medication_name,
        category=exposure.category,
        indication=exposure.indication,
        dose=exposure.dose,
        unit=exposure.unit,
        frequency=exposure.frequency,
        route=exposure.route,
        fact_ids=sorted(set(exposure.fact_ids)),
    )


def _conflict_item(conflict: ClinicalConflictGroupV2) -> ProfileItem:
    member_ids = sorted(
        set(conflict.fact_ids + conflict.event_ids + conflict.exposure_ids)
    )
    return ProfileItem(
        item_id=profile_item_identity(
            ProfileItemKind.CONFLICT, conflict.conflict_group_id
        ),
        lane=ProfileLane.EVIDENCE_QUALITY,
        kind=ProfileItemKind.CONFLICT,
        source_id=conflict.conflict_group_id,
        source_revision=1,
        title="未解决冲突",
        locator_ids=sorted(set(conflict.locator_ids)),
        conflict_member_kind=conflict.member_kind,
        conflict_member_ids=member_ids,
        conflict_resolution_revision=conflict.resolution_revision,
    )


def _expectation_item(expectation: EvidenceExpectationV2) -> ProfileItem:
    return ProfileItem(
        item_id=profile_item_identity(
            ProfileItemKind.EXPECTATION, expectation.expectation_id
        ),
        lane=ProfileLane.EVIDENCE_QUALITY,
        kind=ProfileItemKind.EXPECTATION,
        source_id=expectation.expectation_id,
        source_revision=expectation.revision,
        title="资料覆盖期望",
        subtitle=_EXPECTATION_LABELS[expectation.status],
        locator_ids=sorted(set(expectation.locator_ids)),
        fact_ids=sorted(set(expectation.coverage_fact_ids)),
        template_id=expectation.template_id,
        expectation_status=expectation.status,
        gap_type=expectation.gap_type,
        gap_detail=expectation.gap_detail,
        provenance_followup=expectation.provenance_followup,
        provenance_reason=(
            expectation.provenance_reason
            if expectation.provenance_followup
            else None
        ),
    )


# --------------------------------------------------------------------------- 泳道归属


def _build_lane_assignments(
    facts: Sequence[ClinicalFactV2],
    events: Sequence[ClinicalEventV2],
    lane_assignments: Sequence[ProfileLaneAssignment],
) -> dict[tuple[ProfileItemKind, str], ProfileLane]:
    """校验并构建 (kind, source_id) -> lane 的泳道归属；缺失/重复/多余/跨类型一律拒绝。

    只允许 fact/event 归属；exposure/conflict/expectation 泳道固定，多余归属按
    “多余归属”拒绝（跨类型也落入“多余”/“缺失”双侧检测）。
    """
    assignment_map: dict[tuple[ProfileItemKind, str], ProfileLane] = {}
    for assignment in lane_assignments:
        key = (assignment.kind, assignment.source_id)
        if key in assignment_map:
            raise ProjectionInputError(
                f"重复的泳道归属 {assignment.kind.value}:{assignment.source_id}"
            )
        assignment_map[key] = assignment.lane

    expected_keys = {
        (ProfileItemKind.FACT, fact.fact_id) for fact in facts
    } | {(ProfileItemKind.EVENT, event.event_id) for event in events}
    for kind, source_id in sorted(expected_keys):
        if (kind, source_id) not in assignment_map:
            raise ProjectionInputError(
                f"缺少泳道归属 {kind.value}:{source_id}；每个 fact/event 必须恰好一个归属"
            )
    extra_keys = set(assignment_map) - expected_keys
    if extra_keys:
        rendered = ", ".join(
            f"{kind.value}:{source_id}" for kind, source_id in sorted(extra_keys)
        )
        raise ProjectionInputError(f"多余泳道归属 {rendered}；exposure/conflict/expectation 泳道固定")
    return assignment_map


# --------------------------------------------------------------------------- 首屏突出


def _item_highlight(item: ProfileItem) -> ProfileHighlight | None:
    """单条 Profile 条目的确定突出判定（全量条目的确定性子集）。

    只由已发布合同状态触发：未解决冲突、当前到期资料缺口、较弱证据的 OCR/解析
    风险、较弱证据的溯源提醒。不存在无来源旁路信号；单个较弱事实不因来源强度
    自动突出。
    """
    reasons: list[ProfileHighlightReason] = []
    gap_type: GapType | None = None
    detail: str | None = None
    if item.kind == ProfileItemKind.CONFLICT:
        if item.conflict_resolution_revision == 0:
            reasons.append(ProfileHighlightReason.UNRESOLVED_CONFLICT)
            detail = _CONFLICT_HIGHLIGHT_DETAIL
    elif item.kind == ProfileItemKind.EXPECTATION:
        status = item.expectation_status
        if status in (ExpectationStatus.ABSENT, ExpectationStatus.REFERENCED_MISSING):
            reasons.append(ProfileHighlightReason.CURRENT_DUE_EXPECTATION_GAP)
            gap_type = item.gap_type
            detail = item.gap_detail
        elif status == ExpectationStatus.OBSERVED_WEAK:
            if item.gap_type == GapType.OCR_OR_PARSE_RISK:
                reasons.append(ProfileHighlightReason.STRUCTURED_OCR_OR_PARSE_RISK)
                detail = _OCR_RISK_HIGHLIGHT_DETAIL
            elif (
                item.gap_type
                in (GapType.PROVENANCE_FOLLOWUP, GapType.HISTORICAL_SOURCE_UNAVAILABLE)
                and item.provenance_followup
            ):
                reasons.append(
                    ProfileHighlightReason.WEAK_SOURCE_POSITIVE_LONG_TERM_HISTORY
                )
                detail = item.provenance_reason or _WEAK_HISTORY_HIGHLIGHT_DETAIL
    if not reasons:
        return None
    return ProfileHighlight(
        item_id=item.item_id,
        reasons=sorted(set(reasons)),
        gap_type=gap_type,
        detail=detail,
    )


# --------------------------------------------------------------------------- 主投影


def _require_authority(
    entity_id: str, label: str, authority: FactAuthority, expected: FactAuthority
) -> None:
    if authority != expected:
        raise ProjectionInputError(
            f"{label} {entity_id} 的权威元组与 Profile 权威元组不一致，拒绝投影"
        )


def project_patient_profile(
    *,
    authority: FactAuthority,
    review_stage: ReviewStage,
    facts: Sequence[ClinicalFactV2] = (),
    events: Sequence[ClinicalEventV2] = (),
    exposures: Sequence[MedicationExposureV2] = (),
    conflicts: Sequence[ClinicalConflictGroupV2] = (),
    expectations: Sequence[EvidenceExpectationV2] = (),
    lane_assignments: Sequence[ProfileLaneAssignment] = (),
    revision: int = 1,
    created_at: datetime | None = None,
    generated_at: datetime | None = None,
) -> PatientProfileRevisionV2:
    """投影当前权威元组的完整确定性 Patient Profile（纯函数，不做持久化）。

    所有输入必须是已发布 v2 合同且绑定同一权威元组；每个 fact/event 必须恰好一个
    显式 ``ProfileLaneAssignment``。泳道归属缺失/重复/多余/跨类型、跨权威元组一律
    抛 ``ProjectionInputError``。只生成 ``succeeded`` 完整投影。
    """
    lane_map = _build_lane_assignments(facts, events, lane_assignments)

    items: list[ProfileItem] = []
    facts_by_id = {fact.fact_id: fact for fact in facts}
    for fact in facts:
        _require_authority(fact.fact_id, "事实", fact.authority, authority)
        items.append(_fact_item(fact, lane_map[(ProfileItemKind.FACT, fact.fact_id)]))
    for event in events:
        _require_authority(event.event_id, "事件", event.authority, authority)
        items.append(
            _event_item(
                event,
                lane_map[(ProfileItemKind.EVENT, event.event_id)],
                facts_by_id,
            )
        )
    for exposure in exposures:
        _require_authority(exposure.exposure_id, "暴露", exposure.authority, authority)
        items.append(_exposure_item(exposure))
    for conflict in conflicts:
        _require_authority(
            conflict.conflict_group_id, "冲突", conflict.authority, authority
        )
        items.append(_conflict_item(conflict))
    for expectation in expectations:
        _require_authority(
            expectation.expectation_id, "期望", expectation.authority, authority
        )
        items.append(_expectation_item(expectation))

    by_lane: dict[ProfileLane, list[ProfileItem]] = {lane: [] for lane in PROFILE_LANE_ORDER}
    for item in items:
        by_lane[item.lane].append(item)
    sections = [
        ProfileLaneSection(
            lane=lane,
            items=sorted(by_lane[lane], key=lambda item: (item.kind.value, item.source_id)),
        )
        for lane in PROFILE_LANE_ORDER
    ]
    ordered_items = [item for section in sections for item in section.items]

    highlights = [
        highlight
        for item in ordered_items
        if (highlight := _item_highlight(item)) is not None
    ]

    patient_profile_revision_id = profile_revision_identity(
        authority.review_episode_id, revision
    )
    return PatientProfileRevisionV2(
        patient_profile_revision_id=patient_profile_revision_id,
        authority=authority,
        status=ProfileStatus.SUCCEEDED,
        revision=revision,
        review_stage=review_stage,
        generated_at=generated_at or datetime.now(UTC),
        created_at=created_at or datetime.now(UTC),
        pending_review_count=len(highlights),
        lanes=sections,
        highlights=highlights,
    )
