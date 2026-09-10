"""Phase 5 Patient Profile 投影确定性测试（Slice 5.5，纯投影，无存储）。

覆盖：显式 ProfileLaneAssignment 泳道归属（未知 fact_type 可稳定投影；缺失/重复/
多余/跨类型归属一律拒绝；exposure 固定 MEDICATION、conflict/expectation 固定
EVIDENCE_QUALITY）；条目与源合同逐字保真（定位/资料要求/事实引用/日期/记录时间/
来源强度/溯源提醒）；首屏突出确定性子集（未解决冲突、当前到期缺口、较弱证据的
OCR/解析风险、较弱证据的溯源提醒；``not_due`` 保留但不突出；FactRuleLink 本身不
突出；affirmed 筛选病历转述事实没有 observed_weak 期望时不突出；无法再通过旁路
信号制造异常/趋势突出）；跨权威元组大声失败；同输入完全可重放；投影/合同源码不含
研究实例派生类型词汇。
"""
from __future__ import annotations

import inspect
from datetime import UTC, date, datetime

import pytest

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
from app.domain.contracts.evidence_expectations_v2 import EvidenceExpectationV2
from app.domain.contracts.facts import (
    AssertionBasis,
    ClinicalConflictGroupV2,
    ClinicalEventV2,
    ClinicalFactV2,
    FactAuthority,
    MedicationExposureV2,
    PartialDateRange,
    clinical_event_stable_identity,
    clinical_fact_stable_identity,
    medication_exposure_stable_identity,
)
from app.domain.contracts.patient_profile_v2 import (
    PROFILE_LANE_ORDER,
    PatientProfileRevisionV2,
    ProfileHighlightReason,
    ProfileItemKind,
    ProfileLaneAssignment,
    ProfileStatus,
    profile_item_identity,
    profile_items,
)
from app.projections.patient_profile import (
    ProjectionInputError,
    project_patient_profile,
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


AUTHORITY = _authority()


def _date_range(precision=DatePrecision.DAY, lower=date(2026, 3, 1), upper=date(2026, 3, 1)):
    return PartialDateRange(
        source_text="2026-03-01", precision=precision, lower_bound=lower, upper_bound=upper
    )


def _basis(asserted_object="ALT", value=35, locator_id="loc-1"):
    return AssertionBasis(
        asserted_object=asserted_object,
        assertion_text=f"{asserted_object} {value}",
        locator_id=locator_id,
        source_text_sha256=SHA,
    )


def _fact(
    authority=AUTHORITY,
    fact_id="fact-1",
    fact_type="lab",
    polarity=FactPolarity.AFFIRMED,
    asserted_object="ALT",
    value=35,
    unit="U/L",
    source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
    date_range=None,
    record_time=_UTC,
    locator_ids=None,
    supported_requirement_ids=(),
    revision=1,
    gate_id="gate-1",
    created_at=_UTC,
):
    locator_ids = locator_ids or ["loc-1"]
    return ClinicalFactV2(
        fact_id=fact_id,
        run_id="run-1",
        gate_id=gate_id,
        authority=authority,
        fact_type=fact_type,
        supported_requirement_ids=sorted(set(supported_requirement_ids)),
        polarity=polarity,
        asserted_object=asserted_object,
        value=value,
        unit=unit,
        source_strength=source_strength,
        date_range=date_range,
        record_time=record_time,
        locator_ids=sorted(set(locator_ids)),
        assertion_basis=_basis(asserted_object, value, locator_ids[0]),
        stable_identity=clinical_fact_stable_identity(
            authority=authority,
            fact_type=fact_type,
            asserted_object=asserted_object,
            polarity=polarity,
            value=value,
            unit=unit,
            date_range=date_range,
        ),
        revision=revision,
        created_at=created_at,
    )


def _event(
    authority=AUTHORITY,
    event_id="event-1",
    event_type="lab_event",
    start_range=None,
    end_range=None,
    duration_status=DurationStatus.SINGLE,
    record_time=_UTC,
    fact_ids=None,
    locator_ids=None,
    source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
    facts_by_id=None,
    revision=1,
    gate_id="gate-1",
    created_at=_UTC,
):
    fact_ids = fact_ids or ["fact-1"]
    locator_ids = locator_ids or ["loc-2"]
    facts_by_id = facts_by_id or {}
    referenced_objects = sorted(
        {
            f"{facts_by_id[fid].fact_type}:{facts_by_id[fid].asserted_object}"
            for fid in fact_ids
            if fid in facts_by_id
        }
        or ["lab:ALT"]
    )
    return ClinicalEventV2(
        event_id=event_id,
        run_id="run-1",
        gate_id=gate_id,
        authority=authority,
        event_type=event_type,
        start_range=start_range,
        end_range=end_range,
        duration_status=duration_status,
        record_time=record_time,
        fact_ids=sorted(set(fact_ids)),
        referenced_fact_objects=referenced_objects,
        locator_ids=sorted(set(locator_ids)),
        source_strength=source_strength,
        stable_identity=clinical_event_stable_identity(
            authority=authority,
            event_type=event_type,
            referenced_fact_objects=referenced_objects,
            start_range=start_range,
            end_range=end_range,
            duration_status=duration_status,
        ),
        revision=revision,
        created_at=created_at,
    )


def _exposure(
    authority=AUTHORITY,
    exposure_id="exposure-1",
    medication_name="二甲双胍",
    category=None,
    indication="2 型糖尿病",
    dose="500",
    unit="mg",
    frequency="每日一次",
    route="口服",
    start_range=None,
    end_range=None,
    duration_status=DurationStatus.ENDED,
    record_time=_UTC,
    fact_ids=None,
    locator_ids=None,
    source_strength=SourceStrength.HISTORICAL_PRIMARY,
    revision=1,
    gate_id="gate-1",
    created_at=_UTC,
):
    fact_ids = fact_ids or ["fact-1"]
    locator_ids = locator_ids or ["loc-3"]
    end_range = end_range if end_range is not None else _date_range()
    return MedicationExposureV2(
        exposure_id=exposure_id,
        run_id="run-1",
        gate_id=gate_id,
        authority=authority,
        medication_name=medication_name,
        category=category,
        indication=indication,
        dose=dose,
        unit=unit,
        frequency=frequency,
        route=route,
        start_range=start_range,
        end_range=end_range,
        duration_status=duration_status,
        record_time=record_time,
        fact_ids=sorted(set(fact_ids)),
        locator_ids=sorted(set(locator_ids)),
        source_strength=source_strength,
        stable_identity=medication_exposure_stable_identity(
            authority=authority,
            medication_name=medication_name,
            category=category,
            indication=indication,
            dose=dose,
            unit=unit,
            frequency=frequency,
            route=route,
            start_range=start_range,
            end_range=end_range,
            duration_status=duration_status,
        ),
        revision=revision,
        created_at=created_at,
    )


def _conflict(
    authority=AUTHORITY,
    conflict_id="conflict-1",
    member_kind="fact",
    fact_ids=None,
    locator_ids=None,
    gate_id="gate-1",
    created_at=_UTC,
):
    fact_ids = fact_ids or ["fact-1", "fact-2"]
    locator_ids = locator_ids or ["loc-1", "loc-2"]
    return ClinicalConflictGroupV2(
        conflict_group_id=conflict_id,
        run_id="run-1",
        gate_id=gate_id,
        authority=authority,
        member_kind=member_kind,
        fact_ids=sorted(set(fact_ids)),
        locator_ids=sorted(set(locator_ids)),
        resolution_revision=0,
        created_at=created_at,
    )


def _expectation(
    authority=AUTHORITY,
    expectation_id="exp-1",
    template_id="template-1",
    status=ExpectationStatus.OBSERVED,
    gap_type=None,
    revision=1,
    locator_ids=None,
    coverage_fact_ids=None,
    source_coverage="complete",
    provenance_followup=False,
    provenance_reason=None,
    gap_detail=None,
    created_at=_UTC,
):
    locator_ids = locator_ids if locator_ids is not None else ["loc-1"]
    coverage_fact_ids = coverage_fact_ids if coverage_fact_ids is not None else ["fact-1"]
    return EvidenceExpectationV2(
        expectation_id=expectation_id,
        authority=authority,
        template_id=template_id,
        status=status,
        gap_type=gap_type,
        revision=revision,
        locator_ids=locator_ids,
        coverage_fact_ids=coverage_fact_ids,
        source_coverage=source_coverage,
        provenance_followup=provenance_followup,
        provenance_reason=provenance_reason,
        gap_detail=gap_detail,
        created_at=created_at,
    )


def _assignment(kind, source_id, lane):
    return ProfileLaneAssignment(kind=kind, source_id=source_id, lane=lane)


def _assign_fact(fact_id, lane=ProfileLane.TEST_EXAM_SCORE):
    return _assignment(ProfileItemKind.FACT, fact_id, lane)


def _assign_event(event_id, lane=ProfileLane.TEST_EXAM_SCORE):
    return _assignment(ProfileItemKind.EVENT, event_id, lane)


def _project(**kwargs):
    kwargs.setdefault("authority", AUTHORITY)
    kwargs.setdefault("review_stage", ReviewStage.SCREENING)
    kwargs.setdefault("created_at", _UTC)
    kwargs.setdefault("generated_at", _UTC)
    return project_patient_profile(**kwargs)


def _items_by_lane(rev):
    return {section.lane: section.items for section in rev.lanes}


def _highlight_reasons(rev):
    source_by_item = {item.item_id: item.source_id for item in profile_items(rev)}
    return {
        source_by_item[hl.item_id]: [reason.value for reason in hl.reasons]
        for hl in rev.highlights
    }


def _highlight_by_source(rev):
    source_by_item = {item.item_id: item.source_id for item in profile_items(rev)}
    return {source_by_item[hl.item_id]: hl for hl in rev.highlights}


# --------------------------------------------------------------------------- 泳道归属


def test_unknown_fact_type_projects_with_explicit_assignment():
    # 任意未知 fact_type，只要有显式 ProfileLaneAssignment 就稳定投影
    fact = _fact(fact_id="f-x", fact_type="completely_unknown_study_type",
                 asserted_object="未知对象", value=True, unit="unitless",
                 locator_ids=["loc-1"])
    rev = _project(
        facts=[fact],
        lane_assignments=[_assign_fact("f-x", ProfileLane.SPECIAL_HISTORY)],
    )
    items = _items_by_lane(rev)[ProfileLane.SPECIAL_HISTORY]
    assert [item.source_id for item in items] == ["f-x"]
    assert items[0].title == "未知对象"


def test_full_projection_13_lanes_and_classification():
    facts = [
        _fact(fact_id="f-demo", fact_type="demographics", asserted_object="性别",
              value="女", unit="unitless", locator_ids=["loc-demo"]),
        _fact(fact_id="f-hist", fact_type="medical_history", asserted_object="高血压病史",
              value="有", unit="unitless",
              source_strength=SourceStrength.SCREENING_RECORD_TRANSCRIPTION,
              locator_ids=["loc-hist"]),
        _fact(fact_id="f-alt", fact_type="lab", asserted_object="ALT", value=80,
              unit="U/L", locator_ids=["loc-alt"], supported_requirement_ids=["req-alt"]),
    ]
    events = [_event(event_id="e-lab", fact_ids=["f-alt"], locator_ids=["loc-e"],
                     facts_by_id={f.fact_id: f for f in facts})]
    exposures = [_exposure(exposure_id="x-met", fact_ids=["f-alt"], locator_ids=["loc-x"])]
    conflicts = [_conflict(conflict_id="c-1", fact_ids=["f-alt", "f-hist"],
                           locator_ids=["loc-alt", "loc-hist"])]
    expectations = [
        _expectation(expectation_id="exp-obs", template_id="t-obs",
                     status=ExpectationStatus.OBSERVED,
                     coverage_fact_ids=["f-alt"], locator_ids=["loc-alt"]),
        _expectation(expectation_id="exp-absent", template_id="t-absent",
                     status=ExpectationStatus.ABSENT,
                     gap_type=GapType.REQUIRED_PROCEDURE_NOT_DONE,
                     coverage_fact_ids=[], locator_ids=[],
                     source_coverage="none", gap_detail="未完成"),
    ]
    rev = _project(
        facts=facts,
        events=events,
        exposures=exposures,
        conflicts=conflicts,
        expectations=expectations,
        lane_assignments=[
            _assign_fact("f-demo", ProfileLane.DEMOGRAPHICS),
            _assign_fact("f-hist", ProfileLane.MEDICAL_HISTORY),
            _assign_fact("f-alt", ProfileLane.TEST_EXAM_SCORE),
            _assign_event("e-lab", ProfileLane.TEST_EXAM_SCORE),
        ],
    )

    assert rev.status == ProfileStatus.SUCCEEDED
    assert [section.lane for section in rev.lanes] == list(PROFILE_LANE_ORDER)
    by_lane = _items_by_lane(rev)
    assert {item.source_id for item in by_lane[ProfileLane.DEMOGRAPHICS]} == {"f-demo"}
    assert {item.source_id for item in by_lane[ProfileLane.MEDICAL_HISTORY]} == {"f-hist"}
    assert {item.source_id for item in by_lane[ProfileLane.TEST_EXAM_SCORE]} == {"f-alt", "e-lab"}
    assert {item.source_id for item in by_lane[ProfileLane.MEDICATION]} == {"x-met"}
    assert {item.source_id for item in by_lane[ProfileLane.EVIDENCE_QUALITY]} == {
        "c-1", "exp-obs", "exp-absent"
    }
    for lane in PROFILE_LANE_ORDER:
        assert lane in by_lane


def test_exposure_conflict_expectation_fixed_lanes_need_no_assignment():
    rev = _project(
        exposures=[_exposure()],
        conflicts=[_conflict()],
        expectations=[_expectation(
            expectation_id="exp-nd", status=ExpectationStatus.NOT_DUE,
            gap_type=GapType.FUTURE_STAGE_NOT_DUE,
            coverage_fact_ids=[], locator_ids=[], source_coverage="none")],
    )
    by_lane = _items_by_lane(rev)
    assert [item.source_id for item in by_lane[ProfileLane.MEDICATION]] == ["exposure-1"]
    assert {item.source_id for item in by_lane[ProfileLane.EVIDENCE_QUALITY]} == {
        "conflict-1", "exp-nd"
    }


def test_missing_assignment_rejected():
    fact = _fact(fact_id="f-1")
    with pytest.raises(ProjectionInputError, match="缺少泳道归属"):
        _project(facts=[fact])
    event = _event(event_id="e-1", fact_ids=["f-1"])
    with pytest.raises(ProjectionInputError, match="缺少泳道归属"):
        _project(facts=[fact], events=[event],
                 lane_assignments=[_assign_fact("f-1")])


def test_event_title_requires_and_uses_linked_clinical_facts():
    fact = _fact(fact_id="f-1", asserted_object="过敏性鼻炎首次诊断")
    event = _event(event_id="e-1", fact_ids=["f-1"])
    rev = _project(
        facts=[fact],
        events=[event],
        lane_assignments=[_assign_fact("f-1"), _assign_event("e-1")],
    )
    event_item = next(item for item in profile_items(rev) if item.source_id == "e-1")
    assert event_item.title == "过敏性鼻炎首次诊断"

    with pytest.raises(ProjectionInputError, match="引用了未进入本次档案的事实"):
        _project(
            events=[event],
            lane_assignments=[_assign_event("e-1")],
        )


def test_duplicate_assignment_rejected():
    fact = _fact(fact_id="f-1")
    with pytest.raises(ProjectionInputError, match="重复的泳道归属"):
        _project(
            facts=[fact],
            lane_assignments=[
                _assign_fact("f-1", ProfileLane.TEST_EXAM_SCORE),
                _assign_fact("f-1", ProfileLane.DEMOGRAPHICS),
            ],
        )


def test_extra_assignment_rejected():
    fact = _fact(fact_id="f-1")
    # 为不存在的实体提供归属 → 多余
    with pytest.raises(ProjectionInputError, match="多余泳道归属"):
        _project(
            facts=[fact],
            lane_assignments=[
                _assign_fact("f-1"),
                _assign_fact("ghost-fact"),
            ],
        )
    # exposure/conflict/expectation 泳道固定：无归属即可投影，
    # 且非 fact/event 归属在合同层已被拒绝（见 test_profile_lane_assignment_rejects_non_fact_event_kind）。


def test_cross_type_assignment_rejected():
    # 用 EVENT 归属覆盖 fact → fact 缺归属、事件归属多余
    fact = _fact(fact_id="f-1")
    with pytest.raises(ProjectionInputError):
        _project(
            facts=[fact],
            lane_assignments=[
                _assignment(ProfileItemKind.EVENT, "f-1", ProfileLane.TEST_EXAM_SCORE),
            ],
        )


def test_items_sorted_deterministically_within_lane():
    rev = _project(
        facts=[
            _fact(fact_id="f-b", fact_type="lab", asserted_object="ALT", locator_ids=["loc-1"]),
            _fact(fact_id="f-a", fact_type="lab", asserted_object="AST", locator_ids=["loc-2"]),
        ],
        lane_assignments=[
            _assign_fact("f-a", ProfileLane.TEST_EXAM_SCORE),
            _assign_fact("f-b", ProfileLane.TEST_EXAM_SCORE),
        ],
    )
    items = _items_by_lane(rev)[ProfileLane.TEST_EXAM_SCORE]
    assert [item.source_id for item in items] == ["f-a", "f-b"]


# --------------------------------------------------------------------------- 源合同保真


def test_item_fields_fidelity_with_source_contracts():
    date_range = _date_range()
    fact = _fact(fact_id="f-alt", fact_type="lab", asserted_object="ALT", value=80,
                 unit="U/L", date_range=date_range, record_time=_UTC,
                 locator_ids=["loc-1", "loc-2"], supported_requirement_ids=["req-a", "req-b"])
    event = _event(event_id="e-1", fact_ids=["f-alt"], locator_ids=["loc-3"],
                   facts_by_id={"f-alt": fact})
    exposure = _exposure(exposure_id="x-1", fact_ids=["f-alt"], locator_ids=["loc-4"])
    rev = _project(
        facts=[fact],
        events=[event],
        exposures=[exposure],
        lane_assignments=[
            _assign_fact("f-alt", ProfileLane.TEST_EXAM_SCORE),
            _assign_event("e-1", ProfileLane.TEST_EXAM_SCORE),
        ],
    )
    items = {item.source_id: item for item in profile_items(rev)}

    f_item = items["f-alt"]
    assert f_item.kind == ProfileItemKind.FACT
    assert f_item.locator_ids == ["loc-1", "loc-2"]
    assert f_item.requirement_ids == ["req-a", "req-b"]
    assert f_item.polarity == fact.polarity
    assert f_item.value == 80 and f_item.unit == "U/L"
    assert f_item.asserted_object == "ALT"
    assert f_item.start_range == fact.date_range
    assert f_item.record_time == fact.record_time
    assert f_item.source_strength == fact.source_strength
    assert f_item.source_revision == fact.revision
    assert f_item.title == "ALT" and f_item.subtitle == "有"

    e_item = items["e-1"]
    assert e_item.kind == ProfileItemKind.EVENT
    assert e_item.event_type == "lab_event"
    assert e_item.title == "ALT"
    assert e_item.duration_status == DurationStatus.SINGLE
    assert e_item.fact_ids == ["f-alt"]
    assert e_item.locator_ids == ["loc-3"]
    assert e_item.source_strength == event.source_strength
    assert e_item.source_revision == event.revision

    x_item = items["x-1"]
    assert x_item.kind == ProfileItemKind.EXPOSURE
    assert x_item.medication_name == "二甲双胍"
    assert x_item.dose == "500" and x_item.unit == "mg"
    assert x_item.frequency == "每日一次" and x_item.route == "口服"
    assert x_item.fact_ids == ["f-alt"]
    assert x_item.locator_ids == ["loc-4"]
    assert x_item.subtitle == "500mg、每日一次、口服、2 型糖尿病"


def test_exposure_subtitle_does_not_repeat_legacy_embedded_unit():
    rev = _project(exposures=[_exposure(dose="500mg", unit="mg")])
    item = next(item for item in profile_items(rev) if item.kind == ProfileItemKind.EXPOSURE)

    assert item.subtitle == "500mg、每日一次、口服、2 型糖尿病"


def test_expectation_fidelity_fields():
    exp = _expectation(
        expectation_id="exp-w", status=ExpectationStatus.OBSERVED_WEAK,
        gap_type=GapType.PROVENANCE_FOLLOWUP, coverage_fact_ids=["f-1"],
        locator_ids=["loc-1"], source_coverage="weak", provenance_followup=True,
        provenance_reason="需溯源", gap_detail=None,
    )
    rev = _project(expectations=[exp])
    item = _items_by_lane(rev)[ProfileLane.EVIDENCE_QUALITY][0]
    assert item.template_id == "template-1"
    assert item.expectation_status == ExpectationStatus.OBSERVED_WEAK
    assert item.gap_type == GapType.PROVENANCE_FOLLOWUP
    assert item.provenance_followup is True
    assert item.provenance_reason == "需溯源"
    assert item.fact_ids == ["f-1"]
    assert item.locator_ids == ["loc-1"]
    assert item.subtitle == "较弱证据"


# --------------------------------------------------------------------------- 首屏突出


def test_highlight_rules_full_matrix():
    facts = [
        # 弱来源阳性长期史事实，但无 observed_weak 期望 → 不突出
        _fact(fact_id="f-weak", fact_type="medical_history", asserted_object="高血压病史",
              value="有", unit="unitless",
              source_strength=SourceStrength.SCREENING_RECORD_TRANSCRIPTION,
              locator_ids=["loc-1"]),
        # 强来源带规则链接 → 不突出（FactRuleLink 本身不是突出原因）
        _fact(fact_id="f-linked", fact_type="lab", asserted_object="ALT", value=35,
              unit="U/L", locator_ids=["loc-2"], supported_requirement_ids=["req-alt"]),
    ]
    conflicts = [_conflict(conflict_id="c-1", fact_ids=["f-weak", "f-linked"],
                           locator_ids=["loc-1", "loc-2"])]
    expectations = [
        _expectation(expectation_id="exp-abs", template_id="t-abs",
                     status=ExpectationStatus.ABSENT,
                     gap_type=GapType.RECORD_INCOMPLETE,
                     coverage_fact_ids=[], locator_ids=[], source_coverage="none",
                     gap_detail="缺页"),
        _expectation(expectation_id="exp-nd", template_id="t-nd",
                     status=ExpectationStatus.NOT_DUE,
                     gap_type=GapType.FUTURE_STAGE_NOT_DUE,
                     coverage_fact_ids=[], locator_ids=[], source_coverage="none"),
        _expectation(expectation_id="exp-obs", template_id="t-obs",
                     status=ExpectationStatus.OBSERVED,
                     coverage_fact_ids=["f-linked"], locator_ids=["loc-2"]),
        _expectation(expectation_id="exp-weak", template_id="t-weak",
                     status=ExpectationStatus.OBSERVED_WEAK,
                     gap_type=GapType.PROVENANCE_FOLLOWUP,
                     coverage_fact_ids=["f-weak"], locator_ids=["loc-1"],
                     source_coverage="weak", provenance_followup=True,
                     provenance_reason="需溯源"),
        _expectation(expectation_id="exp-ocr", template_id="t-ocr",
                     status=ExpectationStatus.OBSERVED_WEAK,
                     gap_type=GapType.OCR_OR_PARSE_RISK,
                     coverage_fact_ids=["f-linked"], locator_ids=["loc-2"],
                     source_coverage="complete"),
    ]
    rev = _project(
        facts=facts,
        conflicts=conflicts,
        expectations=expectations,
        lane_assignments=[
            _assign_fact("f-weak", ProfileLane.MEDICAL_HISTORY),
            _assign_fact("f-linked", ProfileLane.TEST_EXAM_SCORE),
        ],
    )

    reasons = _highlight_reasons(rev)
    assert reasons["c-1"] == ["unresolved_conflict"]
    assert reasons["exp-abs"] == ["current_due_expectation_gap"]
    assert reasons["exp-weak"] == ["weak_source_positive_long_term_history"]
    assert reasons["exp-ocr"] == ["structured_ocr_or_parse_risk"]
    # 弱来源事实本身不突出；FactRuleLink 本身不突出；not_due / observed 不突出
    assert "f-weak" not in reasons
    assert "f-linked" not in reasons
    assert "exp-nd" not in reasons
    assert "exp-obs" not in reasons
    # not_due 保留在全量 Profile
    full_ids = {item.source_id for item in profile_items(rev)}
    assert "exp-nd" in full_ids
    # 当前到期缺口突出带具体 gap_type
    hl_by_item = _highlight_by_source(rev)
    assert hl_by_item["exp-abs"].gap_type == GapType.RECORD_INCOMPLETE
    assert rev.pending_review_count == len(rev.highlights)


def test_affirmed_weak_source_fact_alone_not_highlighted():
    rev = _project(
        facts=[
            _fact(fact_id="f-weak", fact_type="medical_history", asserted_object="高血压病史",
                  value="有", unit="unitless",
                  source_strength=SourceStrength.SCREENING_RECORD_TRANSCRIPTION,
                  locator_ids=["loc-1"]),
        ],
        lane_assignments=[_assign_fact("f-weak", ProfileLane.MEDICAL_HISTORY)],
    )
    assert rev.highlights == []
    items = _items_by_lane(rev)[ProfileLane.MEDICAL_HISTORY]
    assert [item.source_id for item in items] == ["f-weak"]


def test_negated_weak_source_fact_not_highlighted():
    rev = _project(
        facts=[
            _fact(fact_id="f-neg", fact_type="medical_history", asserted_object="糖尿病病史",
                  polarity=FactPolarity.NEGATED, value="无", unit="unitless",
                  source_strength=SourceStrength.SCREENING_RECORD_TRANSCRIPTION,
                  locator_ids=["loc-1"]),
        ],
        lane_assignments=[_assign_fact("f-neg", ProfileLane.MEDICAL_HISTORY)],
    )
    assert rev.highlights == []


def test_no_side_channel_abnormal_or_trend_highlights():
    # 无法再通过旁路信号制造异常/趋势突出：只有期望/冲突状态能产生突出。
    rev = _project(
        facts=[_fact(fact_id="f-1", fact_type="lab", asserted_object="ALT", value=80,
                     unit="U/L", locator_ids=["loc-1"])],
        lane_assignments=[_assign_fact("f-1", ProfileLane.TEST_EXAM_SCORE)],
    )
    assert rev.highlights == []
    produced = {
        reason
        for hl in rev.highlights
        for reason in hl.reasons
    }
    assert ProfileHighlightReason.SOURCE_REPORT_ABNORMAL not in produced
    assert ProfileHighlightReason.SOURCE_REPORT_CRITICAL not in produced
    assert ProfileHighlightReason.SOURCE_REPORT_TREND not in produced
    assert ProfileHighlightReason.STRUCTURED_OCR_OR_PARSE_RISK not in produced


def test_observed_weak_ocr_risk_from_expectation_only():
    # OCR 风险只从 observed_weak + ocr_or_parse_risk 期望触发
    rev = _project(
        expectations=[_expectation(
            expectation_id="exp-ocr", status=ExpectationStatus.OBSERVED_WEAK,
            gap_type=GapType.OCR_OR_PARSE_RISK, coverage_fact_ids=["f-1"],
            locator_ids=["loc-1"], source_coverage="complete")],
    )
    reasons = _highlight_reasons(rev)
    assert reasons["exp-ocr"] == ["structured_ocr_or_parse_risk"]


def test_ocr_review_reason_is_not_mislabeled_as_provenance_followup():
    rev = _project(
        expectations=[_expectation(
            expectation_id="exp-ocr-reason",
            status=ExpectationStatus.OBSERVED_WEAK,
            gap_type=GapType.OCR_OR_PARSE_RISK,
            coverage_fact_ids=["f-1"],
            locator_ids=["loc-1"],
            source_coverage="complete",
            provenance_reason="需人工校对后确认完整",
        )],
    )
    item = _items_by_lane(rev)[ProfileLane.EVIDENCE_QUALITY][0]
    assert item.provenance_followup is False
    assert item.provenance_reason is None


def test_provenance_highlight_from_expectation_only():
    # 溯源突出只由 observed_weak + provenance_followup 缺口的期望条目触发
    rev = _project(
        expectations=[_expectation(
            expectation_id="exp-w", status=ExpectationStatus.OBSERVED_WEAK,
            gap_type=GapType.PROVENANCE_FOLLOWUP, coverage_fact_ids=["f-1"],
            locator_ids=["loc-1"], source_coverage="weak", provenance_followup=True,
            provenance_reason="需溯源")],
    )
    reasons = _highlight_reasons(rev)
    assert reasons["exp-w"] == ["weak_source_positive_long_term_history"]
    hl = _highlight_by_source(rev)
    assert hl["exp-w"].detail == "需溯源"


# --------------------------------------------------------------------------- 权威与可重放


def test_authority_mismatch_rejected():
    other = _authority(review_episode_id="episode-2", episode_revision=1)
    with pytest.raises(ProjectionInputError):
        _project(facts=[_fact(authority=other, fact_id="f-other")],
                 lane_assignments=[_assign_fact("f-other")])
    with pytest.raises(ProjectionInputError):
        _project(events=[_event(authority=other, event_id="e-other")],
                 lane_assignments=[_assign_event("e-other")])
    with pytest.raises(ProjectionInputError):
        _project(exposures=[_exposure(authority=other, exposure_id="x-other")])
    with pytest.raises(ProjectionInputError):
        _project(conflicts=[_conflict(authority=other, conflict_id="c-other")])
    with pytest.raises(ProjectionInputError):
        _project(expectations=[_expectation(authority=other, expectation_id="e-other")])


def test_empty_input_produces_13_empty_lanes():
    rev = _project()
    assert rev.pending_review_count == 0
    assert rev.highlights == []
    assert all(section.items == [] for section in rev.lanes)


def test_determinism_same_input_same_payload():
    kwargs = dict(
        facts=[_fact(fact_id="f-1", fact_type="lab", asserted_object="ALT", value=80,
                     unit="U/L", locator_ids=["loc-1"])],
        lane_assignments=[_assign_fact("f-1", ProfileLane.TEST_EXAM_SCORE)],
        expectations=[_expectation(
            expectation_id="exp-abs", status=ExpectationStatus.ABSENT,
            gap_type=GapType.RECORD_INCOMPLETE,
            coverage_fact_ids=[], locator_ids=[], source_coverage="none")],
    )
    a = _project(**kwargs)
    b = _project(**kwargs)
    assert a.model_dump(mode="json") == b.model_dump(mode="json")
    assert a.patient_profile_revision_id == b.patient_profile_revision_id
    # 输入顺序无关：同一批实体不同顺序得到同一 Profile
    c = _project(
        facts=list(reversed(kwargs["facts"])),
        lane_assignments=list(reversed(kwargs["lane_assignments"])),
        expectations=list(reversed(kwargs["expectations"])),
    )
    assert a.model_dump(mode="json") == c.model_dump(mode="json")


def test_revision_identity_and_review_stage():
    rev = _project(review_stage=ReviewStage.BASELINE)
    assert rev.review_stage == ReviewStage.BASELINE
    assert rev.revision == 1
    assert rev.generated_at == _UTC and rev.created_at == _UTC


# --------------------------------------------------------------------------- 词汇表禁令


def test_no_shared_fact_type_vocabulary_in_source():
    import app.domain.contracts.patient_profile_v2 as contract_module
    import app.projections.patient_profile as projection_module

    for module in (contract_module, projection_module):
        assert not hasattr(module, "_FACT_TYPE_LANES")
        assert not hasattr(module, "_EVENT_TYPE_LANES")
        source = inspect.getsource(module)
        # 研究实例派生类型 / legacy fixture 类型词汇不得出现在投影/合同源码。
        for token in (
            "laboratory.ggt_multiple_of_uln",
            "medication.prohibited_exposure",
            "history.condition_present",
            "history.event_present",
        ):
            assert token not in source, f"{module.__name__} 包含实例类型词汇 {token}"
