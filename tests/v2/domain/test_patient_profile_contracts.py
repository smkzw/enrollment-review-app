"""Phase 5 Patient Profile v2 合同确定性测试（Slice 5.5，纯校验，无存储）。

覆盖：13 条泳道稳定展示顺序（含空泳道）；ProfileItem 按类型的严格字段矩阵；条目
稳定身份与全量引用闭包；首屏突出子集与结构化原因（gap_type 仅限当前到期缺口）；
ProfileLaneAssignment 严格归属（只允许 fact/event、泳道属于 13 条）；期望条目溯源
提醒镜像（只有较弱证据 + 溯源/历史来源缺口才允许）；状态语义（succeeded/stale
必须完整、generating/failed 不能伪装成空成功 Profile）；profile_item_identity /
profile_revision_identity 确定性；生成中/失败不得携带投影。
"""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.domain.contracts.enums import (
    DatePrecision,
    DurationStatus,
    ExpectationStatus,
    FactPolarity,
    GapType,
    ProfileLane,
    ReviewStage,
    SourceStrength,
)
from app.domain.contracts.facts import FactAuthority, PartialDateRange
from app.domain.contracts.patient_profile_v2 import (
    ALL_PROFILE_LANES,
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
    profile_items,
    profile_revision_identity,
)

SHA = "a" * 64
_UTC = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)


def _authority(**overrides):
    base = {
        "project_id": "project-1",
        "subject_id": "subject-1",
        "review_episode_id": "episode-1",
        "episode_revision": 3,
        "protocol_version_id": "protocol-v2",
        "rule_set_id": "ruleset-1",
        "rule_set_revision": 4,
        "evidence_snapshot_v2_id": "snapshot-v2-1",
        "complete_processing_revision_id": "complete-rev-1",
    }
    base.update(overrides)
    return FactAuthority(**base)


def _date_range(precision=DatePrecision.DAY, lower=date(2026, 3, 1), upper=date(2026, 3, 1)):
    return PartialDateRange(
        source_text="2026-03-01", precision=precision, lower_bound=lower, upper_bound=upper
    )


def _fact_item(**overrides):
    base = {
        "item_id": profile_item_identity(ProfileItemKind.FACT, "fact-1"),
        "lane": ProfileLane.TEST_EXAM_SCORE,
        "kind": ProfileItemKind.FACT,
        "source_id": "fact-1",
        "source_revision": 1,
        "title": "血红蛋白",
        "subtitle": "有",
        "start_range": _date_range(),
        "record_time": _UTC,
        "source_strength": SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        "locator_ids": ["loc-1"],
        "requirement_ids": [],
        "polarity": FactPolarity.AFFIRMED,
        "asserted_object": "血红蛋白",
        "value": 120,
        "unit": "g/L",
    }
    base.update(overrides)
    return ProfileItem(**base)


def _event_item(**overrides):
    base = {
        "item_id": profile_item_identity(ProfileItemKind.EVENT, "event-1"),
        "lane": ProfileLane.TEST_EXAM_SCORE,
        "kind": ProfileItemKind.EVENT,
        "source_id": "event-1",
        "source_revision": 1,
        "title": "lab_event",
        "subtitle": "单次",
        "start_range": _date_range(),
        "duration_status": DurationStatus.SINGLE,
        "record_time": _UTC,
        "source_strength": SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        "locator_ids": ["loc-1"],
        "event_type": "lab_event",
        "fact_ids": ["fact-1"],
    }
    base.update(overrides)
    return ProfileItem(**base)


def _exposure_item(**overrides):
    base = {
        "item_id": profile_item_identity(ProfileItemKind.EXPOSURE, "exposure-1"),
        "lane": ProfileLane.MEDICATION,
        "kind": ProfileItemKind.EXPOSURE,
        "source_id": "exposure-1",
        "source_revision": 1,
        "title": "二甲双胍",
        "subtitle": "500mg、每日一次、口服",
        "start_range": _date_range(),
        "end_range": _date_range(),
        "duration_status": DurationStatus.ENDED,
        "record_time": _UTC,
        "source_strength": SourceStrength.HISTORICAL_PRIMARY,
        "locator_ids": ["loc-2"],
        "medication_name": "二甲双胍",
        "dose": "500",
        "unit": "mg",
        "frequency": "每日一次",
        "route": "口服",
        "indication": "2 型糖尿病",
        "fact_ids": ["fact-1"],
    }
    base.update(overrides)
    return ProfileItem(**base)


def _conflict_item(**overrides):
    base = {
        "item_id": profile_item_identity(ProfileItemKind.CONFLICT, "conflict-1"),
        "lane": ProfileLane.EVIDENCE_QUALITY,
        "kind": ProfileItemKind.CONFLICT,
        "source_id": "conflict-1",
        "source_revision": 1,
        "title": "未解决冲突",
        "locator_ids": ["loc-1", "loc-2"],
        "conflict_member_kind": "fact",
        "conflict_member_ids": ["fact-1", "fact-2"],
        "conflict_resolution_revision": 0,
    }
    base.update(overrides)
    return ProfileItem(**base)


def _expectation_item(**overrides):
    base = {
        "item_id": profile_item_identity(ProfileItemKind.EXPECTATION, "exp-1"),
        "lane": ProfileLane.EVIDENCE_QUALITY,
        "kind": ProfileItemKind.EXPECTATION,
        "source_id": "exp-1",
        "source_revision": 1,
        "title": "资料覆盖期望",
        "subtitle": "已观察",
        "locator_ids": ["loc-1"],
        "fact_ids": ["fact-1"],
        "template_id": "template-1",
        "expectation_status": ExpectationStatus.OBSERVED,
        "gap_type": None,
        "gap_detail": None,
        "provenance_followup": False,
        "provenance_reason": None,
    }
    base.update(overrides)
    return ProfileItem(**base)


def _sections(items):
    by_lane = {lane: [] for lane in PROFILE_LANE_ORDER}
    for item in items:
        by_lane[item.lane].append(item)
    return [ProfileLaneSection(lane=lane, items=by_lane[lane]) for lane in PROFILE_LANE_ORDER]


def _revision(items=(), **overrides):
    base = {
        "patient_profile_revision_id": profile_revision_identity("episode-1", 1),
        "authority": _authority(),
        "status": ProfileStatus.SUCCEEDED,
        "revision": 1,
        "review_stage": ReviewStage.SCREENING,
        "generated_at": _UTC,
        "created_at": _UTC,
        "pending_review_count": 0,
        "lanes": _sections(items),
        "highlights": [],
    }
    base.update(overrides)
    return PatientProfileRevisionV2(**base)


# --------------------------------------------------------------------------- 泳道


def test_13_lanes_exact_stable_order():
    rev = _revision(items=[_fact_item(), _event_item()])
    assert [section.lane for section in rev.lanes] == list(PROFILE_LANE_ORDER)
    assert len(rev.lanes) == 13
    assert {section.lane for section in rev.lanes} == set(PROFILE_LANE_ORDER)


def test_empty_profile_has_13_empty_lanes():
    rev = _revision()
    assert [section.lane for section in rev.lanes] == list(PROFILE_LANE_ORDER)
    assert all(section.items == [] for section in rev.lanes)
    assert rev.highlights == []
    assert rev.pending_review_count == 0


def test_missing_lane_rejected():
    lanes = _sections([_fact_item()])[:-1]  # drop EVIDENCE_QUALITY
    with pytest.raises(ValidationError):
        _revision(lanes=lanes)


def test_wrong_lane_order_rejected():
    lanes = _sections([_fact_item()])
    lanes[0], lanes[1] = lanes[1], lanes[0]
    with pytest.raises(ValidationError):
        _revision(lanes=lanes)


def test_duplicate_lane_rejected():
    lanes = _sections([_fact_item()])
    lanes.append(ProfileLaneSection(lane=ProfileLane.DEMOGRAPHICS, items=[]))
    with pytest.raises(ValidationError):
        _revision(lanes=lanes)


def test_lane_order_covers_full_enum():
    assert ALL_PROFILE_LANES == set(ProfileLane)
    assert len(PROFILE_LANE_ORDER) == 13


def test_item_lane_must_match_section():
    lanes = _sections([_fact_item()])
    # 把一个条目塞进与其 lane 不同的泳道。
    lanes[0] = ProfileLaneSection(lane=ProfileLane.STUDY_MILESTONE, items=[_fact_item()])
    with pytest.raises(ValidationError):
        _revision(lanes=lanes)


def test_item_lane_outside_13_rejected():
    item = _fact_item(lane=ProfileLane.EVIDENCE_QUALITY)
    assert item.lane in ALL_PROFILE_LANES  # 仍在 13 泳道内
    with pytest.raises(ValidationError):
        _fact_item(lane="not-a-lane")


# --------------------------------------------------------------------------- 条目身份与引用闭包


def test_item_id_deterministic_and_immutable():
    a = _fact_item()
    b = _fact_item()
    assert a.item_id == b.item_id
    assert a.item_id == profile_item_identity(ProfileItemKind.FACT, "fact-1")
    assert a.item_id != profile_item_identity(ProfileItemKind.FACT, "fact-other")
    assert a.item_id != profile_item_identity(ProfileItemKind.EVENT, "fact-1")


def test_wrong_item_id_rejected():
    with pytest.raises(ValidationError):
        _fact_item(item_id="profile-item:stale")


def test_duplicate_item_id_in_profile_rejected():
    with pytest.raises(ValidationError):
        _revision(items=[_fact_item(), _fact_item()])


def test_locator_requirement_fact_ids_sorted_unique():
    with pytest.raises(ValidationError):
        _fact_item(locator_ids=["loc-2", "loc-1"])
    with pytest.raises(ValidationError):
        _fact_item(locator_ids=["loc-1", "loc-1"])
    with pytest.raises(ValidationError):
        _fact_item(requirement_ids=["req-b", "req-a"])
    with pytest.raises(ValidationError):
        _event_item(fact_ids=["fact-2", "fact-1"])
    with pytest.raises(ValidationError):
        _conflict_item(conflict_member_ids=["fact-2", "fact-1"])


def test_naive_record_time_rejected():
    with pytest.raises(ValidationError):
        _fact_item(record_time=datetime(2026, 3, 1, 12, 0, 0))


# --------------------------------------------------------------------------- ProfileItem 类型矩阵


def test_fact_item_matrix():
    # 缺极性/对象/来源强度 → 拒绝
    with pytest.raises(ValidationError):
        _fact_item(polarity=None)
    with pytest.raises(ValidationError):
        _fact_item(asserted_object=None)
    with pytest.raises(ValidationError):
        _fact_item(source_strength=None)
    # 肯定事实缺值 → 拒绝
    with pytest.raises(ValidationError):
        _fact_item(value=None)
    # 数值事实缺单位 → 拒绝
    with pytest.raises(ValidationError):
        _fact_item(unit=None)
    # 未知极性携带值/单位 → 拒绝
    with pytest.raises(ValidationError):
        _fact_item(polarity=FactPolarity.UNKNOWN, value=120, unit="g/L")
    # 无值携带单位 → 拒绝
    with pytest.raises(ValidationError):
        _fact_item(polarity=FactPolarity.UNKNOWN, value=None, unit="g/L")
    # 事实带事件类型/药名/冲突/期望字段 → 拒绝
    with pytest.raises(ValidationError):
        _fact_item(event_type="lab_event")
    with pytest.raises(ValidationError):
        _fact_item(medication_name="二甲双胍")
    with pytest.raises(ValidationError):
        _fact_item(duration_status=DurationStatus.SINGLE)
    with pytest.raises(ValidationError):
        _fact_item(fact_ids=["fact-2"])
    with pytest.raises(ValidationError):
        _fact_item(template_id="template-1")
    with pytest.raises(ValidationError):
        _fact_item(conflict_member_kind="fact")
    # 未知极性无值 → 合法
    ok = _fact_item(polarity=FactPolarity.UNKNOWN, value=None, unit=None, title="血红蛋白", subtitle="未知")
    assert ok.value is None and ok.unit is None


def test_event_item_matrix():
    with pytest.raises(ValidationError):
        _event_item(event_type=None)
    with pytest.raises(ValidationError):
        _event_item(source_strength=None)
    with pytest.raises(ValidationError):
        _event_item(duration_status=None)
    with pytest.raises(ValidationError):
        _event_item(fact_ids=[])
    with pytest.raises(ValidationError):
        _event_item(asserted_object="血红蛋白")
    with pytest.raises(ValidationError):
        _event_item(polarity=FactPolarity.AFFIRMED)
    with pytest.raises(ValidationError):
        _event_item(medication_name="二甲双胍")
    with pytest.raises(ValidationError):
        _event_item(requirement_ids=["req-1"])
    with pytest.raises(ValidationError):
        _event_item(conflict_member_ids=["fact-1"])


def test_exposure_item_matrix():
    with pytest.raises(ValidationError):
        _exposure_item(medication_name=None)
    with pytest.raises(ValidationError):
        _exposure_item(source_strength=None)
    with pytest.raises(ValidationError):
        _exposure_item(duration_status=None)
    with pytest.raises(ValidationError):
        _exposure_item(fact_ids=[])
    with pytest.raises(ValidationError):
        _exposure_item(polarity=FactPolarity.AFFIRMED)
    with pytest.raises(ValidationError):
        _exposure_item(event_type="medication_start")
    with pytest.raises(ValidationError):
        _exposure_item(requirement_ids=["req-1"])
    # 已结束暴露必须携带终止范围（镜像暴露合同）
    with pytest.raises(ValidationError):
        _exposure_item(end_range=None)


def test_conflict_item_matrix():
    with pytest.raises(ValidationError):
        _conflict_item(conflict_member_kind=None)
    with pytest.raises(ValidationError):
        _conflict_item(conflict_resolution_revision=None)
    with pytest.raises(ValidationError):
        _conflict_item(conflict_member_ids=["fact-1"])  # 少于两个成员
    with pytest.raises(ValidationError):
        _conflict_item(source_strength=SourceStrength.UNVERIFIABLE)
    with pytest.raises(ValidationError):
        _conflict_item(duration_status=DurationStatus.UNKNOWN)
    with pytest.raises(ValidationError):
        _conflict_item(fact_ids=["fact-1"])
    with pytest.raises(ValidationError):
        _conflict_item(requirement_ids=["req-1"])
    with pytest.raises(ValidationError):
        _conflict_item(record_time=_UTC)


def test_expectation_item_matrix():
    with pytest.raises(ValidationError):
        _expectation_item(template_id=None)
    with pytest.raises(ValidationError):
        _expectation_item(expectation_status=None)
    # NOT_DUE：缺口必须 future_stage_not_due，且不能携带定位/覆盖事实
    ok = _expectation_item(
        expectation_status=ExpectationStatus.NOT_DUE,
        gap_type=GapType.FUTURE_STAGE_NOT_DUE,
        locator_ids=[],
        fact_ids=[],
        subtitle="尚未到期",
    )
    assert ok.expectation_status == ExpectationStatus.NOT_DUE
    with pytest.raises(ValidationError):
        _expectation_item(
            expectation_status=ExpectationStatus.NOT_DUE,
            gap_type=GapType.REFERENCED_FILE_MISSING,
            locator_ids=[],
            fact_ids=[],
        )
    with pytest.raises(ValidationError):
        _expectation_item(
            expectation_status=ExpectationStatus.NOT_DUE,
            gap_type=GapType.FUTURE_STAGE_NOT_DUE,
            locator_ids=["loc-1"],
            fact_ids=[],
        )
    # OBSERVED 必须携带覆盖事实与定位、无缺口
    with pytest.raises(ValidationError):
        _expectation_item(expectation_status=ExpectationStatus.OBSERVED, fact_ids=[])
    with pytest.raises(ValidationError):
        _expectation_item(
            expectation_status=ExpectationStatus.OBSERVED, gap_type=GapType.RECORD_INCOMPLETE
        )
    # REFERENCED_MISSING 必须 referenced_file_missing、无覆盖
    with pytest.raises(ValidationError):
        _expectation_item(
            expectation_status=ExpectationStatus.REFERENCED_MISSING,
            gap_type=GapType.RECORD_INCOMPLETE,
        )
    # ABSENT 必须给出具体缺口
    with pytest.raises(ValidationError):
        _expectation_item(expectation_status=ExpectationStatus.ABSENT, gap_type=None)
    with pytest.raises(ValidationError):
        _expectation_item(
            expectation_status=ExpectationStatus.ABSENT,
            gap_type=GapType.RECORD_INCOMPLETE,
            locator_ids=["loc-1"],
        )
    # 期望不能携带临床值/来源强度等
    with pytest.raises(ValidationError):
        _expectation_item(source_strength=SourceStrength.UNVERIFIABLE)
    with pytest.raises(ValidationError):
        _expectation_item(asserted_object="血红蛋白")
    with pytest.raises(ValidationError):
        _expectation_item(duration_status=DurationStatus.UNKNOWN)


def test_expectation_provenance_mirror():
    # 较弱证据 + 溯源缺口必须携带 provenance_followup
    with pytest.raises(ValidationError):
        _expectation_item(
            expectation_status=ExpectationStatus.OBSERVED_WEAK,
            gap_type=GapType.PROVENANCE_FOLLOWUP,
            provenance_followup=False,
        )
    # 较弱证据 + OCR 风险不能携带 provenance_followup
    with pytest.raises(ValidationError):
        _expectation_item(
            expectation_status=ExpectationStatus.OBSERVED_WEAK,
            gap_type=GapType.OCR_OR_PARSE_RISK,
            provenance_followup=True,
        )
    # 非溯源/历史缺口（含已观察）不能携带 provenance_followup
    with pytest.raises(ValidationError):
        _expectation_item(expectation_status=ExpectationStatus.OBSERVED, provenance_followup=True)
    # 合法：较弱证据 + 溯源缺口 + provenance_followup
    ok = _expectation_item(
        expectation_status=ExpectationStatus.OBSERVED_WEAK,
        gap_type=GapType.PROVENANCE_FOLLOWUP,
        provenance_followup=True,
        provenance_reason="需溯源",
    )
    assert ok.provenance_followup is True and ok.provenance_reason == "需溯源"
    # 溯源原因只能伴随溯源提醒
    with pytest.raises(ValidationError):
        _expectation_item(provenance_reason="需溯源", provenance_followup=False)


def test_provenance_forbidden_on_non_expectation_kinds():
    with pytest.raises(ValidationError):
        _fact_item(provenance_followup=True)
    with pytest.raises(ValidationError):
        _fact_item(provenance_reason="需溯源")
    with pytest.raises(ValidationError):
        _event_item(provenance_followup=True)
    with pytest.raises(ValidationError):
        _exposure_item(provenance_reason="需溯源")
    with pytest.raises(ValidationError):
        _conflict_item(provenance_followup=True)


# --------------------------------------------------------------------------- 状态语义


def test_generating_failed_are_status_records():
    for status in (ProfileStatus.GENERATING, ProfileStatus.FAILED):
        rev = PatientProfileRevisionV2(
            patient_profile_revision_id=profile_revision_identity("episode-1", 1),
            authority=_authority(),
            status=status,
            revision=1,
            review_stage=ReviewStage.SCREENING,
            generated_at=None,
            created_at=_UTC,
            pending_review_count=0,
            lanes=[],
            highlights=[],
        )
        assert rev.lanes == [] and rev.highlights == []
    # 生成中不能携带生成时间
    with pytest.raises(ValidationError):
        PatientProfileRevisionV2(
            patient_profile_revision_id=profile_revision_identity("episode-1", 1),
            authority=_authority(),
            status=ProfileStatus.GENERATING,
            revision=1,
            review_stage=ReviewStage.SCREENING,
            generated_at=_UTC,
            created_at=_UTC,
            pending_review_count=0,
        )
    # 生成中/失败不能伪装成空成功 Profile（带泳道/突出/待核对）
    with pytest.raises(ValidationError):
        PatientProfileRevisionV2(
            patient_profile_revision_id=profile_revision_identity("episode-1", 1),
            authority=_authority(),
            status=ProfileStatus.FAILED,
            revision=1,
            review_stage=ReviewStage.SCREENING,
            generated_at=None,
            created_at=_UTC,
            pending_review_count=0,
            lanes=_sections([_fact_item()]),
        )
    with pytest.raises(ValidationError):
        PatientProfileRevisionV2(
            patient_profile_revision_id=profile_revision_identity("episode-1", 1),
            authority=_authority(),
            status=ProfileStatus.GENERATING,
            revision=1,
            review_stage=ReviewStage.SCREENING,
            generated_at=None,
            created_at=_UTC,
            pending_review_count=3,
        )


def test_succeeded_allows_genuine_empty_projection():
    # 空输入 → 13 条空泳道是完整确定性投影（不是伪装成功）
    rev = _revision(items=[], status=ProfileStatus.SUCCEEDED, generated_at=_UTC)
    assert len(rev.lanes) == 13
    assert all(section.items == [] for section in rev.lanes)
    # succeeded 缺生成时间 → 拒绝
    with pytest.raises(ValidationError):
        _revision(items=[_fact_item()], generated_at=None)


def test_stale_keeps_complete_projection():
    rev = _revision(
        items=[_fact_item()],
        status=ProfileStatus.STALE,
        generated_at=_UTC,
    )
    assert rev.status == ProfileStatus.STALE
    assert len(rev.lanes) == 13


def test_pending_review_count_must_match_highlights():
    fact = _fact_item()
    hl = ProfileHighlight(
        item_id=fact.item_id,
        reasons=[ProfileHighlightReason.WEAK_SOURCE_POSITIVE_LONG_TERM_HISTORY],
    )
    # pending 与 highlights 数量不一致 → 拒绝
    with pytest.raises(ValidationError):
        _revision(items=[fact], highlights=[hl], pending_review_count=2)
    ok = _revision(items=[fact], highlights=[hl], pending_review_count=1)
    assert ok.pending_review_count == 1


# --------------------------------------------------------------------------- 突出


def test_highlight_must_reference_existing_item():
    with pytest.raises(ValidationError):
        _revision(
            items=[_fact_item()],
            highlights=[
                ProfileHighlight(
                    item_id="profile-item:ghost",
                    reasons=[ProfileHighlightReason.UNRESOLVED_CONFLICT],
                )
            ],
            pending_review_count=1,
        )


def test_highlight_reasons_nonempty_sorted_unique():
    fact = _fact_item()
    with pytest.raises(ValidationError):
        ProfileHighlight(item_id=fact.item_id, reasons=[])
    with pytest.raises(ValidationError):
        ProfileHighlight(
            item_id=fact.item_id,
            reasons=[
                ProfileHighlightReason.WEAK_SOURCE_POSITIVE_LONG_TERM_HISTORY,
                ProfileHighlightReason.UNRESOLVED_CONFLICT,
            ],
        )  # 未排序（unresolved_conflict 应排在 weak_source 之前）


def test_highlight_gap_type_required_only_for_current_due():
    fact = _fact_item()
    with pytest.raises(ValidationError):
        ProfileHighlight(
            item_id=fact.item_id,
            reasons=[ProfileHighlightReason.CURRENT_DUE_EXPECTATION_GAP],
        )
    ok = ProfileHighlight(
        item_id=fact.item_id,
        reasons=[ProfileHighlightReason.CURRENT_DUE_EXPECTATION_GAP],
        gap_type=GapType.RECORD_INCOMPLETE,
    )
    assert ok.gap_type == GapType.RECORD_INCOMPLETE
    # 非当前到期缺口不能携带 gap_type
    with pytest.raises(ValidationError):
        ProfileHighlight(
            item_id=fact.item_id,
            reasons=[ProfileHighlightReason.UNRESOLVED_CONFLICT],
            gap_type=GapType.RECORD_INCOMPLETE,
        )


# --------------------------------------------------------------------------- 泳道归属


def test_profile_lane_assignment_valid():
    a = ProfileLaneAssignment(
        kind=ProfileItemKind.FACT, source_id="fact-1", lane=ProfileLane.TEST_EXAM_SCORE
    )
    b = ProfileLaneAssignment(
        kind=ProfileItemKind.EVENT, source_id="event-1", lane=ProfileLane.STUDY_MILESTONE
    )
    assert a.kind == ProfileItemKind.FACT and a.lane == ProfileLane.TEST_EXAM_SCORE
    assert b.kind == ProfileItemKind.EVENT and b.lane == ProfileLane.STUDY_MILESTONE


def test_profile_lane_assignment_rejects_non_fact_event_kind():
    for kind in (ProfileItemKind.EXPOSURE, ProfileItemKind.CONFLICT, ProfileItemKind.EXPECTATION):
        with pytest.raises(ValidationError):
            ProfileLaneAssignment(
                kind=kind, source_id="x-1", lane=ProfileLane.EVIDENCE_QUALITY
            )


def test_profile_lane_assignment_rejects_non_lane():
    with pytest.raises(ValidationError):
        ProfileLaneAssignment(kind=ProfileItemKind.FACT, source_id="f-1", lane="not-a-lane")


# --------------------------------------------------------------------------- 身份与展开


def test_revision_id_deterministic():
    assert profile_revision_identity("episode-1", 1) == profile_revision_identity("episode-1", 1)
    assert profile_revision_identity("episode-1", 1) != profile_revision_identity("episode-1", 2)
    assert profile_revision_identity("episode-1", 1) != profile_revision_identity("episode-2", 1)
    with pytest.raises(ValidationError):
        _revision(patient_profile_revision_id="profile:stale")


def test_profile_items_flatten_in_lane_order():
    fact = _fact_item()
    event = _event_item()
    rev = _revision(items=[event, fact])
    flat = profile_items(rev)
    assert [item.item_id for item in flat] == [event.item_id, fact.item_id]
