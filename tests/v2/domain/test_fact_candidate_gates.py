"""Phase 5 Slice 5.2 纯确定性候选门禁聚焦测试。

覆盖纯校验子集：极性/断言、值/单位、部分日期边界、记录时间、
来源派生输入、候选引用闭包；不触及定位真实性、页覆盖、OCR 阻断、去重/冲突
（后两者由证据闭包和批量编排负责）。所有用例基于结构化 fixture，不调用模型、
不访问数据库、不生成 Profile。
"""

from __future__ import annotations

import pytest
from datetime import date, datetime, timezone, timedelta

from app.domain.contracts.enums import DatePrecision, DurationStatus, FactGate, FactPolarity, GateOutcome
from app.domain.contracts.facts import (
    AssertionBasis,
    ClinicalEventCandidateV2,
    ClinicalFactCandidateV2,
    MedicationExposureCandidateV2,
    PartialDateRange,
)
from app.domain.gates.fact_candidate_gates import (
    batch_gate_candidates,
    gate_event_candidate,
    gate_exposure_candidate,
    gate_fact_candidate,
    validate_candidate_reference_closure,
    validate_duration_bounds,
    validate_exposure_value_unit,
    validate_fact_polarity_assertion,
    validate_fact_value_unit,
    validate_partial_date_range,
    validate_record_time,
    validate_source_derivation_inputs,
)

UTC = timezone.utc
SHA = "a" * 64
_NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)
_FUTURE = datetime(2026, 8, 24, 12, 0, 0, tzinfo=UTC)  # +2 days
_NAIVE = datetime(2026, 8, 22, 12, 0, 0)  # naive
_NON_UTC = datetime(2026, 8, 22, 12, 0, 0, tzinfo=timezone(timedelta(hours=8)))


def _range_day(d: date = date(2026, 3, 1)) -> PartialDateRange:
    return PartialDateRange(source_text=d.isoformat(), precision=DatePrecision.DAY, lower_bound=d, upper_bound=d)


def _range_month(y: int = 2026, m: int = 2) -> PartialDateRange:
    import calendar

    last = calendar.monthrange(y, m)[1]
    return PartialDateRange(
        source_text=f"{y}-{m:02d}",
        precision=DatePrecision.MONTH,
        lower_bound=date(y, m, 1),
        upper_bound=date(y, m, last),
    )


def _range_year(y: int = 2020) -> PartialDateRange:
    return PartialDateRange(source_text=str(y), precision=DatePrecision.YEAR, lower_bound=date(y, 1, 1), upper_bound=date(y, 12, 31))


def _range_unknown() -> PartialDateRange:
    return PartialDateRange(source_text=None, precision=DatePrecision.UNKNOWN, lower_bound=None, upper_bound=None)


def _basis(locator_id: str = "loc-1", asserted_object: str = "高血压", text: str = "否认高血压病史") -> AssertionBasis:
    return AssertionBasis(asserted_object=asserted_object, assertion_text=text, locator_id=locator_id, source_text_sha256=SHA)


def _fact_candidate(**overrides) -> ClinicalFactCandidateV2:
    base = {
        "candidate_id": "cand-fact-1",
        "run_id": "run-1",
        "call_id": "call-1",
        "fact_type": "diagnosis",
        "polarity": FactPolarity.AFFIRMED,
        "asserted_object": "高血压",
        "raw_value": "高血压",
        "canonical_value": "高血压",
        "unit": None,
        "date_range": _range_day(),
        "record_time": _NOW,
        "locator_ids": ["loc-1"],
        "candidate_source_semantics": "既往原始资料",
        "assertion_basis": _basis("loc-1", "高血压", "受试者既往有高血压病史"),
        "model_uncertainty": 0.12,
        "created_at": _NOW,
    }
    base.update(overrides)
    return ClinicalFactCandidateV2(**base)


def _event_candidate(**overrides) -> ClinicalEventCandidateV2:
    base = {
        "candidate_id": "cand-event-1",
        "run_id": "run-1",
        "call_id": "call-1",
        "event_type": "diagnosis_onset",
        "start_range": _range_day(date(2020, 1, 15)),
        "end_range": None,
        "duration_status": DurationStatus.ONGOING,
        "record_time": _NOW,
        "fact_candidate_ids": ["cand-fact-1"],
        "locator_ids": ["loc-1"],
        "candidate_source_semantics": "当前研究病历直接记录",
        "model_uncertainty": 0.1,
        "created_at": _NOW,
    }
    base.update(overrides)
    return ClinicalEventCandidateV2(**base)


def _exposure_candidate(**overrides) -> MedicationExposureCandidateV2:
    base = {
        "candidate_id": "cand-exp-1",
        "run_id": "run-1",
        "call_id": "call-1",
        "medication_name": "二甲双胍",
        "category": "降糖药",
        "indication": "2 型糖尿病",
        "dose": "500",
        "unit": "mg",
        "frequency": "bid",
        "route": "口服",
        "start_range": _range_day(date(2026, 1, 10)),
        "end_range": None,
        "duration_status": DurationStatus.ONGOING,
        "record_time": _NOW,
        "fact_candidate_ids": ["cand-fact-1"],
        "locator_ids": ["loc-1"],
        "candidate_source_semantics": "同期客观结果",
        "model_uncertainty": 0.05,
        "created_at": _NOW,
    }
    base.update(overrides)
    return MedicationExposureCandidateV2(**base)


# --------------------------------------------------------------------------- 极性 / 断言

def test_polarity_unknown_must_not_carry_value_or_basis():
    cand = _fact_candidate(
        candidate_id="cand-u1",
        polarity=FactPolarity.UNKNOWN,
        canonical_value=None,
        raw_value=None,
        unit=None,
        assertion_basis=None,
        asserted_object="高血压",
    )
    # Gate should accept UNKNOWN without value/basis
    assert validate_fact_polarity_assertion(cand) == []

    # But if UNKNOWN carries value/basis, gate should reject (even though contract would also reject at construction)
    # We test via direct validator call with a manually constructed UNKNOWN that smuggles value via object bypass:
    # Use model_construct to bypass Pydantic validation and test gate's own check.
    cand2 = ClinicalFactCandidateV2.model_construct(
        candidate_id="cand-u2",
        run_id="run-1",
        call_id="call-1",
        fact_type="diagnosis",
        polarity=FactPolarity.UNKNOWN,
        asserted_object="高血压",
        raw_value="高血压",
        canonical_value="高血压",
        unit=None,
        date_range=_range_day(),
        record_time=_NOW,
        locator_ids=["loc-1"],
        candidate_source_semantics="无法确认来源",
        assertion_basis=_basis("loc-1"),
        model_uncertainty=0.1,
        created_at=_NOW,
        schema_version="phase5/v1",
    )
    errs = validate_fact_polarity_assertion(cand2)
    assert any("未知极性" in e for e in errs)


def test_polarity_affirmed_requires_basis_and_locator_closure():
    cand = ClinicalFactCandidateV2.model_construct(
        candidate_id="cand-fact-1",
        run_id="run-1",
        call_id="call-1",
        fact_type="diagnosis",
        polarity=FactPolarity.AFFIRMED,
        asserted_object="高血压",
        raw_value="高血压",
        canonical_value="高血压",
        unit=None,
        date_range=_range_day(),
        record_time=_NOW,
        locator_ids=["loc-1"],
        candidate_source_semantics="既往原始资料",
        assertion_basis=_basis("loc-2"),
        model_uncertainty=0.12,
        created_at=_NOW,
        schema_version="phase5/v1",
    )
    errs = validate_fact_polarity_assertion(cand)
    assert any("定位必须属于" in e for e in errs)


def test_polarity_basis_object_mismatch():
    cand = ClinicalFactCandidateV2.model_construct(
        candidate_id="cand-fact-1",
        run_id="run-1",
        call_id="call-1",
        fact_type="diagnosis",
        polarity=FactPolarity.AFFIRMED,
        asserted_object="糖尿病",
        raw_value="糖尿病",
        canonical_value="糖尿病",
        unit=None,
        date_range=_range_day(),
        record_time=_NOW,
        locator_ids=["loc-1"],
        candidate_source_semantics="既往原始资料",
        assertion_basis=_basis("loc-1", asserted_object="高血压"),
        model_uncertainty=0.12,
        created_at=_NOW,
        schema_version="phase5/v1",
    )
    errs = validate_fact_polarity_assertion(cand)
    assert any("断言依据对象一致" in e for e in errs)


def test_polarity_basis_text_blank_rejected():
    basis = AssertionBasis.model_construct(asserted_object="高血压", assertion_text="  ", locator_id="loc-1", source_text_sha256=SHA)
    cand = ClinicalFactCandidateV2.model_construct(
        candidate_id="cand-fact-1",
        run_id="run-1",
        call_id="call-1",
        fact_type="diagnosis",
        polarity=FactPolarity.AFFIRMED,
        asserted_object="高血压",
        raw_value="高血压",
        canonical_value="高血压",
        unit=None,
        date_range=_range_day(),
        record_time=_NOW,
        locator_ids=["loc-1"],
        candidate_source_semantics="既往原始资料",
        assertion_basis=basis,
        model_uncertainty=0.12,
        created_at=_NOW,
        schema_version="phase5/v1",
    )
    errs = validate_fact_polarity_assertion(cand)
    assert any("文本不能为空" in e for e in errs)


def test_polarity_basis_hash_malformed():
    basis = AssertionBasis.model_construct(asserted_object="高血压", assertion_text="高血压", locator_id="loc-1", source_text_sha256="zzzz")
    cand = ClinicalFactCandidateV2.model_construct(
        candidate_id="cand-fact-1",
        run_id="run-1",
        call_id="call-1",
        fact_type="diagnosis",
        polarity=FactPolarity.AFFIRMED,
        asserted_object="高血压",
        raw_value="高血压",
        canonical_value="高血压",
        unit=None,
        date_range=_range_day(),
        record_time=_NOW,
        locator_ids=["loc-1"],
        candidate_source_semantics="既往原始资料",
        assertion_basis=basis,
        model_uncertainty=0.12,
        created_at=_NOW,
        schema_version="phase5/v1",
    )
    errs = validate_fact_polarity_assertion(cand)
    assert any("原文哈希" in e for e in errs)


def test_polarity_gate_verdict_accepted_and_rejected():
    ok = _fact_candidate()
    verdicts = gate_fact_candidate(ok)
    assert verdicts[FactGate.POLARITY_AND_ASSERTED_OBJECT].outcome == GateOutcome.ACCEPTED
    assert verdicts[FactGate.POLARITY_AND_ASSERTED_OBJECT].reasons == []

    bad = ClinicalFactCandidateV2.model_construct(
        candidate_id="cand-fact-1",
        run_id="run-1",
        call_id="call-1",
        fact_type="diagnosis",
        polarity=FactPolarity.AFFIRMED,
        asserted_object="高血压",
        raw_value="高血压",
        canonical_value="高血压",
        unit=None,
        date_range=_range_day(),
        record_time=_NOW,
        locator_ids=["loc-1"],
        candidate_source_semantics="既往原始资料",
        assertion_basis=_basis("loc-2"),
        model_uncertainty=0.12,
        created_at=_NOW,
        schema_version="phase5/v1",
    )
    verdicts2 = gate_fact_candidate(bad)
    v = verdicts2[FactGate.POLARITY_AND_ASSERTED_OBJECT]
    assert v.outcome == GateOutcome.REJECTED
    assert v.reasons
    assert v.affected_scope == ["loc-1"]


# --------------------------------------------------------------------------- 值 / 单位

def test_fact_value_unit_numeric_requires_unit():
    cand = ClinicalFactCandidateV2.model_construct(
        candidate_id="cand-fact-1",
        run_id="run-1",
        call_id="call-1",
        fact_type="lab",
        polarity=FactPolarity.AFFIRMED,
        asserted_object="血红蛋白",
        raw_value=120,
        canonical_value=120,
        unit=None,
        date_range=_range_day(),
        record_time=_NOW,
        locator_ids=["loc-1"],
        candidate_source_semantics="同期客观结果",
        assertion_basis=AssertionBasis(asserted_object="血红蛋白", assertion_text="血红蛋白 120", locator_id="loc-1", source_text_sha256=SHA),
        model_uncertainty=0.12,
        created_at=_NOW,
        schema_version="phase5/v1",
    )
    errs = validate_fact_value_unit(cand)
    assert any("必须声明单位" in e for e in errs)

    cand_ok = _fact_candidate(canonical_value=120, unit="mmHg", raw_value="120", asserted_object="血红蛋白", assertion_basis=AssertionBasis(asserted_object="血红蛋白", assertion_text="血红蛋白 120 mmHg", locator_id="loc-1", source_text_sha256=SHA))
    assert validate_fact_value_unit(cand_ok) == []

    cand_unitless = _fact_candidate(canonical_value=5, unit="unitless", raw_value="5", asserted_object="计数", assertion_basis=AssertionBasis(asserted_object="计数", assertion_text="计数 5", locator_id="loc-1", source_text_sha256=SHA))
    assert validate_fact_value_unit(cand_unitless) == []



def test_fact_value_unit_text_must_not_carry_unit():
    cand = _fact_candidate(canonical_value="高血压", unit="mmHg")
    errs = validate_fact_value_unit(cand)
    assert any("不应携带单位" in e for e in errs)

    cand2 = _fact_candidate(canonical_value="高血压", unit=None)
    assert validate_fact_value_unit(cand2) == []


def test_fact_value_unit_blank_text_rejected():
    cand = _fact_candidate(canonical_value="   ", unit=None, raw_value="   ")
    errs = validate_fact_value_unit(cand)
    assert any("不能为空" in e for e in errs)


def test_fact_value_unit_finite_check():
    cand = ClinicalFactCandidateV2.model_construct(
        candidate_id="cand-num-inf",
        run_id="run-1",
        call_id="call-1",
        fact_type="lab",
        polarity=FactPolarity.AFFIRMED,
        asserted_object="血糖",
        raw_value=float("inf"),
        canonical_value=float("inf"),
        unit="mmol/L",
        date_range=_range_day(),
        record_time=_NOW,
        locator_ids=["loc-1"],
        candidate_source_semantics="同期客观结果",
        assertion_basis=_basis("loc-1", "血糖", "血糖 6.1 mmol/L"),
        model_uncertainty=0.01,
        created_at=_NOW,
        schema_version="phase5/v1",
    )
    errs = validate_fact_value_unit(cand)
    assert any("有限数" in e for e in errs)


def test_exposure_value_unit_dose_unit_coherence():
    ok = _exposure_candidate()
    assert validate_exposure_value_unit(ok) == []

    # unit without dose
    bad = _exposure_candidate(dose=None, unit="mg")
    errs = validate_exposure_value_unit(bad)
    assert any("不能在无剂量" in e for e in errs)

    # blank frequency
    bad2 = _exposure_candidate(frequency="  ")
    errs2 = validate_exposure_value_unit(bad2)
    assert any("不能为空白" in e for e in errs2)

    # blank route
    bad3 = _exposure_candidate(route="\t")
    errs3 = validate_exposure_value_unit(bad3)
    assert any("不能为空白" in e for e in errs3)

    # no dose no unit is OK (e.g. unknown dose)
    ok2 = _exposure_candidate(dose=None, unit=None, frequency=None, route=None, category=None, indication=None)
    assert validate_exposure_value_unit(ok2) == []


def test_exposure_gate_aggregates_value_unit():
    cand = _exposure_candidate(dose=None, unit="mg")
    verdicts = gate_exposure_candidate(cand, fact_id_set={"cand-fact-1"})
    v = verdicts[FactGate.VALUE_UNIT_DATE_SOURCE]
    assert v.outcome == GateOutcome.REJECTED
    assert any("不能在无剂量" in r for r in v.reasons)


# --------------------------------------------------------------------------- 部分日期边界

def test_partial_date_day_must_have_equal_bounds():
    # Valid day already tested via contract; gate should also accept
    assert validate_partial_date_range(_range_day(date(2026, 3, 1)), "事实日期范围") == []

    # Invalid day: lower != upper -> construct via model_construct to bypass contract validator, test gate
    bad = PartialDateRange.model_construct(source_text="2026-03-01", precision=DatePrecision.DAY, lower_bound=date(2026, 3, 1), upper_bound=date(2026, 3, 2))
    errs = validate_partial_date_range(bad, "事实日期范围")
    assert any("日精度" in e for e in errs)


def test_partial_date_month_boundaries():
    assert validate_partial_date_range(_range_month(2026, 2), "开始范围") == []
    # Non-leap Feb 2026 has 28 days
    bad_last = PartialDateRange.model_construct(source_text="2026-02", precision=DatePrecision.MONTH, lower_bound=date(2026, 2, 1), upper_bound=date(2026, 2, 27))
    errs = validate_partial_date_range(bad_last, "开始范围")
    assert any("末日" in e for e in errs)

    bad_first = PartialDateRange.model_construct(source_text="2026-02", precision=DatePrecision.MONTH, lower_bound=date(2026, 2, 2), upper_bound=date(2026, 2, 28))
    errs2 = validate_partial_date_range(bad_first, "开始范围")
    assert any("首日" in e for e in errs2)


def test_partial_date_year_boundaries():
    assert validate_partial_date_range(_range_year(2020), "结束范围") == []
    bad = PartialDateRange.model_construct(source_text="2020", precision=DatePrecision.YEAR, lower_bound=date(2020, 1, 2), upper_bound=date(2020, 12, 31))
    errs = validate_partial_date_range(bad, "结束范围")
    assert any("1 月 1 日" in e for e in errs)

    bad2 = PartialDateRange.model_construct(source_text="2020", precision=DatePrecision.YEAR, lower_bound=date(2020, 1, 1), upper_bound=date(2020, 12, 30))
    errs2 = validate_partial_date_range(bad2, "结束范围")
    assert any("12 月 31 日" in e for e in errs2)


def test_partial_date_unknown_must_not_carry_bounds():
    assert validate_partial_date_range(_range_unknown(), "事实日期范围") == []
    bad = PartialDateRange.model_construct(source_text=None, precision=DatePrecision.UNKNOWN, lower_bound=date(2026, 1, 1), upper_bound=date(2026, 12, 31))
    errs = validate_partial_date_range(bad, "事实日期范围")
    assert any("未知日期不能携带" in e for e in errs)


def test_partial_date_known_requires_bounds():
    bad = PartialDateRange.model_construct(source_text="2026-03-01", precision=DatePrecision.DAY, lower_bound=None, upper_bound=None)
    errs = validate_partial_date_range(bad, "事实日期范围")
    assert any("必须提供" in e for e in errs)


def test_partial_date_upper_before_lower():
    bad = PartialDateRange.model_construct(source_text="2026-03-01", precision=DatePrecision.DAY, lower_bound=date(2026, 3, 2), upper_bound=date(2026, 3, 1))
    errs = validate_partial_date_range(bad, "事实日期范围")
    assert any("不能早于下界" in e for e in errs)


def test_partial_date_gate_in_fact_candidate():
    cand = _fact_candidate(date_range=_range_unknown())
    # unknown with no bounds is OK
    assert gate_fact_candidate(cand)[FactGate.VALUE_UNIT_DATE_SOURCE].outcome == GateOutcome.ACCEPTED

    # known but missing bounds via bypass -> gate should reject
    bad_range = PartialDateRange.model_construct(source_text="2026-03-01", precision=DatePrecision.DAY, lower_bound=None, upper_bound=None)
    cand2 = ClinicalFactCandidateV2.model_construct(
        candidate_id="cand-bad-date",
        run_id="run-1",
        call_id="call-1",
        fact_type="diagnosis",
        polarity=FactPolarity.AFFIRMED,
        asserted_object="高血压",
        raw_value="高血压",
        canonical_value="高血压",
        unit=None,
        date_range=bad_range,
        record_time=_NOW,
        locator_ids=["loc-1"],
        candidate_source_semantics="既往原始资料",
        assertion_basis=_basis("loc-1", "高血压", "高血压"),
        model_uncertainty=0.1,
        created_at=_NOW,
        schema_version="phase5/v1",
    )
    errs = validate_partial_date_range(cand2.date_range, "事实日期范围")
    assert errs


# --------------------------------------------------------------------------- 持续状态 / 时态

def test_duration_ended_requires_end():
    errs = validate_duration_bounds(_range_day(date(2026, 1, 10)), None, DurationStatus.ENDED, "暴露持续状态")
    assert any("必须由资料明确给出终止" in e for e in errs)
    assert validate_duration_bounds(_range_day(), _range_day(date(2026, 3, 2)), DurationStatus.ENDED) == []


def test_duration_ongoing_cannot_have_end():
    errs = validate_duration_bounds(_range_day(), _range_day(date(2026, 3, 2)), DurationStatus.ONGOING, "事件持续状态")
    assert any("不能携带终止" in e for e in errs)
    assert validate_duration_bounds(_range_day(), None, DurationStatus.ONGOING) == []


def test_duration_start_after_end_rejected():
    errs = validate_duration_bounds(_range_day(date(2026, 4, 1)), _range_day(date(2026, 3, 1)), DurationStatus.ENDED, "暴露持续状态")
    assert any("不能晚于结束范围" in e for e in errs)


def test_duration_unknown_dates_skip_comparison():
    # unknown start has no lower_bound, so comparison skipped, no error
    assert validate_duration_bounds(_range_unknown(), _range_day(date(2026, 3, 1)), DurationStatus.ENDED) == []


# --------------------------------------------------------------------------- 记录时间

def test_record_time_requires_utc():
    assert validate_record_time(_NOW, _NOW) == []
    errs = validate_record_time(_NAIVE, _NOW, "事实记录时间")
    assert any("UTC" in e for e in errs)
    errs2 = validate_record_time(_NON_UTC, _NOW, "事实记录时间")
    assert any("UTC" in e for e in errs2)


def test_record_time_year_range():
    far = datetime(1800, 1, 1, tzinfo=UTC)
    errs = validate_record_time(far, _NOW, "事实记录时间")
    assert any("超出合理范围" in e for e in errs)


def test_record_time_future_beyond_created_plus_one_day():
    errs = validate_record_time(_FUTURE, _NOW, "事实记录时间")
    assert any("不应晚于创建时间" in e for e in errs)
    # within 1 day is OK
    within = _NOW + timedelta(hours=12)
    assert validate_record_time(within, _NOW, "事实记录时间") == []


def test_record_time_none_is_allowed():
    assert validate_record_time(None, _NOW, "事件记录时间") == []


def test_fact_gate_includes_record_time():
    cand = ClinicalFactCandidateV2.model_construct(
        candidate_id="cand-fact-1",
        run_id="run-1",
        call_id="call-1",
        fact_type="diagnosis",
        polarity=FactPolarity.AFFIRMED,
        asserted_object="高血压",
        raw_value="高血压",
        canonical_value="高血压",
        unit=None,
        date_range=_range_day(),
        record_time=_NAIVE,
        locator_ids=["loc-1"],
        candidate_source_semantics="既往原始资料",
        assertion_basis=_basis("loc-1", "高血压", "高血压"),
        model_uncertainty=0.12,
        created_at=_NOW,
        schema_version="phase5/v1",
    )
    verdicts = gate_fact_candidate(cand)
    v = verdicts[FactGate.VALUE_UNIT_DATE_SOURCE]
    assert v.outcome == GateOutcome.REJECTED
    assert any("UTC" in r for r in v.reasons)

# --------------------------------------------------------------------------- 来源派生输入

def test_source_derivation_blank_rejected():
    errs = validate_source_derivation_inputs("", "事实来源语义")
    assert any("不能为空" in e for e in errs)
    errs2 = validate_source_derivation_inputs("   ", "事实来源语义")
    assert any("不能为空" in e for e in errs2)


def test_source_derivation_whitespace_prefix_rejected():
    errs = validate_source_derivation_inputs(" 既往原始资料", "事实来源语义")
    assert any("前后不能为空格" in e for e in errs)


def test_source_derivation_control_char_rejected():
    errs = validate_source_derivation_inputs("既往原始资料\n", "事实来源语义")
    assert any("控制字符" in e for e in errs)


def test_source_derivation_too_long():
    errs = validate_source_derivation_inputs("a" * 129, "事实来源语义")
    assert any("不得超过 128" in e for e in errs)


def test_source_derivation_allowed_values():
    for val in ["同期客观结果", "既往原始资料", "当前研究病历直接记录", "筛选病历转述", "无法确认来源", "objective_result"]:
        assert validate_source_derivation_inputs(val, "事实来源语义") == []


def test_event_gate_includes_source():
    cand = _event_candidate(candidate_source_semantics="   ")
    verdicts = gate_event_candidate(cand, fact_id_set={"cand-fact-1"})
    v = verdicts[FactGate.VALUE_UNIT_DATE_SOURCE]
    assert v.outcome == GateOutcome.REJECTED


# --------------------------------------------------------------------------- 候选引用闭包

def test_reference_closure_dangling_fact_id():
    fact = _fact_candidate()
    event = _event_candidate(fact_candidate_ids=["missing-fact"])
    errs = validate_candidate_reference_closure(
        fact_candidates=[fact], event_candidates=[event], exposure_candidates=[], run_id="run-1", call_id="call-1"
    )
    assert "cand-event-1" in errs
    assert any("不存在的事实候选" in e for e in errs["cand-event-1"])


def test_reference_closure_run_call_mismatch():
    fact = _fact_candidate(run_id="run-other")
    errs = validate_candidate_reference_closure(
        fact_candidates=[fact], event_candidates=[], exposure_candidates=[], run_id="run-1", call_id="call-1"
    )
    assert "cand-fact-1" in errs
    assert any("run_id" in e for e in errs["cand-fact-1"])


def test_reference_closure_duplicate_candidate_id():
    fact = _fact_candidate(candidate_id="dup-1")
    fact2 = _fact_candidate(candidate_id="dup-1", fact_type="lab", asserted_object="血糖", assertion_basis=_basis("loc-1", "血糖", "血糖"))
    errs = validate_candidate_reference_closure(
        fact_candidates=[fact, fact2], event_candidates=[], exposure_candidates=[], run_id="run-1", call_id="call-1"
    )
    assert "dup-1" in errs
    assert any("重复" in e for e in errs["dup-1"])


def test_reference_closure_ok():
    fact = _fact_candidate()
    event = _event_candidate()
    exposure = _exposure_candidate()
    errs = validate_candidate_reference_closure(
        fact_candidates=[fact], event_candidates=[event], exposure_candidates=[exposure], run_id="run-1", call_id="call-1"
    )
    assert errs == {}


def test_event_gate_reference_closure_via_batch():
    fact = _fact_candidate(candidate_id="f1", assertion_basis=_basis("loc-1", "高血压", "高血压"))
    event_ok = _event_candidate(candidate_id="e1", fact_candidate_ids=["f1"])
    event_bad = _event_candidate(candidate_id="e2", fact_candidate_ids=["missing"])
    verdicts_ok = gate_event_candidate(event_ok, fact_id_set={"f1"})
    assert verdicts_ok[FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE].outcome == GateOutcome.ACCEPTED
    verdicts_bad = gate_event_candidate(event_bad, fact_id_set={"f1"})
    assert verdicts_bad[FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE].outcome == GateOutcome.REJECTED


# --------------------------------------------------------------------------- 批次门禁

def test_batch_gate_produces_verdicts_per_candidate():
    fact_ok = _fact_candidate(candidate_id="f-ok")
    # fact bad: numeric without unit
    fact_bad = ClinicalFactCandidateV2.model_construct(
        candidate_id="f-bad",
        run_id="run-1",
        call_id="call-1",
        fact_type="lab",
        polarity=FactPolarity.AFFIRMED,
        asserted_object="血红蛋白",
        raw_value=12.5,
        canonical_value=12.5,
        unit=None,
        date_range=_range_day(),
        record_time=_NOW,
        locator_ids=["loc-1"],
        candidate_source_semantics="同期客观结果",
        assertion_basis=AssertionBasis(asserted_object="血红蛋白", assertion_text="血红蛋白 12.5", locator_id="loc-1", source_text_sha256=SHA),
        model_uncertainty=0.01,
        created_at=_NOW,
        schema_version="phase5/v1",
    )
    event = _event_candidate(candidate_id="e-ok", fact_candidate_ids=["f-ok"])
    exposure = _exposure_candidate(candidate_id="exp-ok", fact_candidate_ids=["f-ok"])

    batch = batch_gate_candidates(
        fact_candidates=[fact_ok, fact_bad],
        event_candidates=[event],
        exposure_candidates=[exposure],
        run_id="run-1",
        call_id="call-1",
    )
    # f-ok should be fully accepted
    assert batch["f-ok"][FactGate.POLARITY_AND_ASSERTED_OBJECT].outcome == GateOutcome.ACCEPTED
    assert batch["f-ok"][FactGate.VALUE_UNIT_DATE_SOURCE].outcome == GateOutcome.ACCEPTED
    # f-bad should be rejected on value/unit
    assert batch["f-bad"][FactGate.VALUE_UNIT_DATE_SOURCE].outcome == GateOutcome.REJECTED
    # event and exposure should be accepted (reference closure ok)
    assert batch["e-ok"][FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE].outcome == GateOutcome.ACCEPTED
    assert batch["exp-ok"][FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE].outcome == GateOutcome.ACCEPTED


def test_batch_gate_reference_closure_rejected_affects_scope():
    fact = _fact_candidate(candidate_id="f1")
    event = _event_candidate(candidate_id="e1", fact_candidate_ids=["missing"])
    batch = batch_gate_candidates(
        fact_candidates=[fact], event_candidates=[event], exposure_candidates=[], run_id="run-1", call_id="call-1"
    )
    v = batch["e1"][FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE]
    assert v.outcome == GateOutcome.REJECTED
    assert "missing" in v.affected_scope


def test_batch_gate_scope_is_deterministic_sorted():
    # No error case with sorted locators
    fact = _fact_candidate(candidate_id="f1")
    event = _event_candidate(candidate_id="e1", fact_candidate_ids=["f1"], locator_ids=["loc-1"])
    batch = batch_gate_candidates(fact_candidates=[fact], event_candidates=[event], exposure_candidates=[], run_id="run-1", call_id="call-1")
    assert batch["e1"][FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE].outcome == GateOutcome.ACCEPTED
    # Force error: fact with run_id mismatch, affected_scope should be sorted
    fact_bad = ClinicalFactCandidateV2.model_construct(
        candidate_id="f-bad2",
        run_id="run-other",
        call_id="call-1",
        fact_type="diagnosis",
        polarity=FactPolarity.AFFIRMED,
        asserted_object="高血压",
        raw_value="高血压",
        canonical_value="高血压",
        unit=None,
        date_range=_range_day(),
        record_time=_NOW,
        locator_ids=["loc-2", "loc-1"],
        candidate_source_semantics="既往原始资料",
        assertion_basis=_basis("loc-1", "高血压", "高血压"),
        model_uncertainty=0.1,
        created_at=_NOW,
        schema_version="phase5/v1",
    )
    batch2 = batch_gate_candidates(fact_candidates=[fact_bad], event_candidates=[], exposure_candidates=[], run_id="run-1", call_id="call-1")
    v = batch2["f-bad2"][FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE]
    assert v.affected_scope == sorted(v.affected_scope)

def test_verdict_to_gate_result_conversion():
    from app.domain.gates.fact_candidate_gates import verdict_to_gate_result, verdicts_to_gate_results

    fact = _fact_candidate(candidate_id="f1")
    batch = batch_gate_candidates(fact_candidates=[fact], event_candidates=[], exposure_candidates=[], run_id="run-1", call_id="call-1")
    verdict = batch["f1"][FactGate.POLARITY_AND_ASSERTED_OBJECT]
    gr = verdict_to_gate_result(verdict, run_id="run-1", call_id="call-1", gate_result_id="gate-1", created_at=_NOW)
    assert gr.gate == FactGate.POLARITY_AND_ASSERTED_OBJECT
    assert gr.outcome == GateOutcome.ACCEPTED
    assert gr.candidate_id == "f1"

    flat = verdicts_to_gate_results(batch, run_id="run-1", call_id="call-1", created_at=_NOW)
    # Should be deterministic sorted: 1 fact * 2 gates + reference closure gate? fact has 2 gates + maybe one closure
    assert len(flat) >= 2
    assert flat == sorted(flat, key=lambda r: (r.candidate_id, r.gate.value))
