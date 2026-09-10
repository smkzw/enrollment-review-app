"""Phase 5 临床事实合同确定性测试（Slice 5.1，纯校验，无存储）。

覆盖：不可变权威元组；部分日期精度/上下界；断言依据；候选与发布合同物理分离；
发布合同携带 Gate id/权威元组/稳定身份/来源强度/revision 且不携带模型置信度；
稳定身份不含定位与置信度；否定/沉默/数值单位约束；持续状态与终止日期约束；
运行/调用/门禁结果合同与幂等键；不依赖 ReviewRun。
"""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.domain.contracts.enums import (
    DatePrecision,
    DurationStatus,
    FactCallStatus,
    FactGate,
    FactNormalizationRunStatus,
    FactPolarity,
    GateOutcome,
    ProfileLane,
    SourceStrength,
)
from app.domain.contracts.facts import (
    AssertionBasis,
    ClinicalConflictGroupV2,
    ClinicalEventCandidateV2,
    ClinicalEventV2,
    ClinicalFactCandidateV2,
    ClinicalFactV2,
    FactAuthority,
    FactGateResult,
    FactNormalizationCall,
    FactNormalizationRun,
    MedicationExposureCandidateV2,
    MedicationExposureV2,
    PartialDateRange,
    clinical_event_stable_identity,
    clinical_fact_stable_identity,
    fact_authority_hash,
    fact_run_idempotency_key,
    medication_exposure_stable_identity,
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


_MISSING = object()


def _date_range(precision=DatePrecision.DAY, lower=_MISSING, upper=_MISSING, **overrides):
    base = {"source_text": "2026-03-01", "precision": precision}
    if lower is not _MISSING:
        base["lower_bound"] = lower
    else:
        base["lower_bound"] = date(2026, 3, 1)
    if upper is not _MISSING:
        base["upper_bound"] = upper
    else:
        base["upper_bound"] = date(2026, 3, 1)
    base.update(overrides)
    return PartialDateRange(**base)


def _basis(**overrides):
    base = {
        "asserted_object": "高血压病史",
        "assertion_text": "否认高血压病史",
        "locator_id": "loc-1",
        "source_text_sha256": SHA,
    }
    base.update(overrides)
    return AssertionBasis(**base)


def _fact_candidate(**overrides):
    base = {
        "candidate_id": "cand-fact-1",
        "run_id": "run-1",
        "call_id": "call-1",
        "fact_type": "medical_history",
        "polarity": FactPolarity.NEGATED,
        "asserted_object": "高血压病史",
        "raw_value": "否认",
        "canonical_value": "无",
        "unit": None,
        "date_range": _date_range(),
        "record_time": _UTC,
        "locator_ids": ["loc-1"],
        "candidate_source_semantics": "screening_record_transcription",
        "assertion_basis": _basis(),
        "model_uncertainty": 0.2,
        "created_at": _UTC,
    }
    base.update(overrides)
    return ClinicalFactCandidateV2(**base)


def _fact(**overrides):
    base = {
        "fact_id": "fact-1",
        "run_id": "run-1",
        "gate_id": "gate-run-1",
        "authority": _authority(),
        "fact_type": "medical_history",
        "polarity": FactPolarity.NEGATED,
        "asserted_object": "高血压病史",
        "value": "无",
        "unit": None,
        "source_strength": SourceStrength.SCREENING_RECORD_TRANSCRIPTION,
        "date_range": _date_range(),
        "record_time": _UTC,
        "locator_ids": ["loc-1"],
        "assertion_basis": _basis(),
        "revision": 1,
        "created_at": _UTC,
    }
    base.update(overrides)
    if "stable_identity" not in overrides:
        base["stable_identity"] = clinical_fact_stable_identity(
            authority=base["authority"],
            fact_type=base["fact_type"],
            asserted_object=base["asserted_object"],
            polarity=base["polarity"],
            value=base["value"],
            unit=base["unit"],
            date_range=base["date_range"],
        )
    return ClinicalFactV2(**base)


def _event(**overrides):
    base = {
        "event_id": "event-1",
        "run_id": "run-1",
        "gate_id": "gate-run-1",
        "authority": _authority(),
        "event_type": "diagnosis",
        "start_range": _date_range(precision=DatePrecision.YEAR, lower=date(2020, 1, 1), upper=date(2020, 12, 31)),
        "end_range": None,
        "duration_status": DurationStatus.ONGOING,
        "record_time": _UTC,
        "fact_ids": ["fact-1"],
        "referenced_fact_objects": ["medical_history:高血压病史"],
        "locator_ids": ["loc-1"],
        "source_strength": SourceStrength.HISTORICAL_PRIMARY,
        "revision": 1,
        "created_at": _UTC,
    }
    base.update(overrides)
    if "stable_identity" not in overrides:
        base["stable_identity"] = clinical_event_stable_identity(
            authority=base["authority"],
            event_type=base["event_type"],
            referenced_fact_objects=base["referenced_fact_objects"],
            start_range=base["start_range"],
            end_range=base["end_range"],
            duration_status=base["duration_status"],
        )
    return ClinicalEventV2(**base)


def _exposure(**overrides):
    base = {
        "exposure_id": "exposure-1",
        "run_id": "run-1",
        "gate_id": "gate-run-1",
        "authority": _authority(),
        "medication_name": "二甲双胍",
        "category": "降糖药",
        "indication": "2 型糖尿病",
        "dose": "500",
        "unit": "mg",
        "frequency": "bid",
        "route": "口服",
        "start_range": _date_range(lower=date(2026, 1, 1), upper=date(2026, 1, 1)),
        "end_range": None,
        "duration_status": DurationStatus.ONGOING,
        "record_time": _UTC,
        "fact_ids": ["fact-1"],
        "locator_ids": ["loc-1"],
        "source_strength": SourceStrength.CURRENT_STUDY_CHART,
        "revision": 1,
        "created_at": _UTC,
    }
    base.update(overrides)
    if "stable_identity" not in overrides:
        base["stable_identity"] = medication_exposure_stable_identity(
            authority=base["authority"],
            medication_name=base["medication_name"],
            category=base["category"],
            indication=base["indication"],
            dose=base["dose"],
            unit=base["unit"],
            frequency=base["frequency"],
            route=base["route"],
            start_range=base["start_range"],
            end_range=base["end_range"],
            duration_status=base["duration_status"],
        )
    return MedicationExposureV2(**base)


# ------------------------------------------------------------- 不可变权威元组


def test_fact_authority_is_frozen_and_immutable():
    authority = _authority()
    assert authority.episode_revision == 3
    payload = _authority().model_dump()
    payload["episode_revision"] = 0
    with pytest.raises(ValidationError):
        FactAuthority(**payload)
    with pytest.raises((TypeError, ValueError, AttributeError)):
        authority.episode_revision = 99


def test_fact_authority_hash_is_deterministic_and_order_stable():
    a1 = _authority()
    a2 = _authority(project_id="project-2")
    assert fact_authority_hash(a1) == fact_authority_hash(_authority())
    assert fact_authority_hash(a1) != fact_authority_hash(a2)


def test_fact_authority_requires_all_tuple_members():
    payload = _authority().model_dump()
    for field in (
        "project_id",
        "subject_id",
        "review_episode_id",
        "episode_revision",
        "protocol_version_id",
        "rule_set_id",
        "rule_set_revision",
        "evidence_snapshot_v2_id",
        "complete_processing_revision_id",
    ):
        missing = {k: v for k, v in payload.items() if k != field}
        with pytest.raises(ValidationError):
            FactAuthority(**missing)


# ------------------------------------------------------------- 部分日期范围


def test_partial_date_day_bounds_equal():
    r = _date_range(precision=DatePrecision.DAY)
    assert r.lower_bound == r.upper_bound == date(2026, 3, 1)


def test_partial_date_month_first_to_last():
    r = _date_range(
        precision=DatePrecision.MONTH,
        lower=date(2026, 2, 1),
        upper=date(2026, 2, 28),
    )
    assert r.lower_bound.day == 1
    assert r.upper_bound.day == 28


def test_partial_date_year_jan1_to_dec31():
    r = _date_range(
        precision=DatePrecision.YEAR,
        lower=date(2020, 1, 1),
        upper=date(2020, 12, 31),
    )
    assert r.upper_bound == date(2020, 12, 31)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"precision": DatePrecision.DAY, "lower": date(2026, 3, 1), "upper": date(2026, 3, 2)},
        {"precision": DatePrecision.MONTH, "lower": date(2026, 2, 2), "upper": date(2026, 2, 28)},
        {"precision": DatePrecision.MONTH, "lower": date(2026, 2, 1), "upper": date(2026, 2, 27)},
        {"precision": DatePrecision.MONTH, "lower": date(2026, 2, 1), "upper": date(2026, 3, 31)},
        {"precision": DatePrecision.YEAR, "lower": date(2020, 2, 1), "upper": date(2020, 12, 31)},
        {"precision": DatePrecision.YEAR, "lower": date(2020, 1, 1), "upper": date(2021, 12, 31)},
        {"precision": DatePrecision.YEAR, "lower": date(2021, 1, 1), "upper": date(2020, 12, 31)},
    ],
)
def test_partial_date_invalid_bounds_rejected(kwargs):
    with pytest.raises(ValidationError):
        _date_range(**kwargs)


def test_partial_date_unknown_cannot_borrow_anchor_date():
    """未知日期绝不借用筛选/上传/操作日期。"""
    with pytest.raises(ValidationError, match="不得借用"):
        _date_range(precision=DatePrecision.UNKNOWN, lower=date(2026, 3, 1), upper=date(2026, 3, 1))
    ok = _date_range(precision=DatePrecision.UNKNOWN, lower=None, upper=None)
    assert ok.lower_bound is None and ok.upper_bound is None


def test_partial_date_known_precision_requires_bounds():
    with pytest.raises(ValidationError):
        _date_range(precision=DatePrecision.DAY, lower=None, upper=None)


def test_partial_date_identity_excludes_source_text():
    """去重身份只认语义边界，不认原文措辞。"""
    from app.domain.contracts.facts import _date_range_identity

    a = _date_range(source_text="2026-03-01")
    b = _date_range(source_text="2026年3月1日")
    assert _date_range_identity(a) == _date_range_identity(b)


# ------------------------------------------------------------- 候选合同


def test_fact_candidate_ok_and_carries_model_uncertainty():
    candidate = _fact_candidate()
    assert candidate.model_uncertainty == 0.2
    assert candidate.polarity == FactPolarity.NEGATED


def test_fact_candidate_unknown_cannot_smuggle_value_or_basis():
    with pytest.raises(ValidationError, match="未知极性"):
        _fact_candidate(
            polarity=FactPolarity.UNKNOWN,
            canonical_value="正常",
            assertion_basis=None,
        )
    with pytest.raises(ValidationError, match="未知极性"):
        _fact_candidate(polarity=FactPolarity.UNKNOWN, raw_value="未提及", canonical_value=None, assertion_basis=None)


def test_fact_candidate_affirmed_requires_canonical_value_and_basis():
    with pytest.raises(ValidationError, match="规范值"):
        _fact_candidate(polarity=FactPolarity.AFFIRMED, canonical_value=None)
    with pytest.raises(ValidationError, match="断言依据"):
        _fact_candidate(polarity=FactPolarity.AFFIRMED, canonical_value="有", assertion_basis=None)


def test_fact_candidate_numeric_requires_unit_or_unitless():
    with pytest.raises(ValidationError, match="unitless"):
        _fact_candidate(
            polarity=FactPolarity.AFFIRMED,
            canonical_value=7.2,
            unit=None,
            fact_type="lab",
        )
    ok = _fact_candidate(
        polarity=FactPolarity.AFFIRMED,
        canonical_value=7.2,
        unit="mmol/L",
        fact_type="lab",
    )
    assert ok.unit == "mmol/L"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_fact_candidate_rejects_non_finite_numeric_values(value):
    with pytest.raises(ValidationError, match="有限数"):
        _fact_candidate(canonical_value=value, unit="unitless")
    with pytest.raises(ValidationError, match="有限数"):
        _fact(value=value, unit="unitless")


def test_fact_candidate_locators_sorted_unique():
    with pytest.raises(ValidationError, match="排序"):
        _fact_candidate(locator_ids=["loc-2", "loc-1"])
    with pytest.raises(ValidationError, match="排序"):
        _fact_candidate(locator_ids=["loc-1", "loc-1"])


def test_fact_candidate_record_time_requires_utc():
    with pytest.raises(ValidationError, match="UTC"):
        _fact_candidate(record_time=datetime(2026, 8, 22, 12, 0, 0))  # naive


def test_fact_candidate_assertion_locator_must_belong_to_candidate():
    with pytest.raises(ValidationError, match="断言依据定位"):
        _fact_candidate(assertion_basis=_basis(locator_id="loc-2"))


def test_fact_candidate_asserted_object_must_match_assertion_basis():
    with pytest.raises(ValidationError, match="断言依据对象一致"):
        _fact_candidate(asserted_object="糖尿病病史")


def test_candidate_payload_owns_call_provenance_kind_and_created_at():
    candidate = _fact_candidate()
    assert candidate.call_id == "call-1"
    assert candidate.candidate_kind == "fact"
    with pytest.raises(ValidationError, match="UTC"):
        _fact_candidate(created_at=datetime(2026, 8, 22, 12, 0, 0))


def test_event_and_exposure_candidates_ok():
    event = ClinicalEventCandidateV2(
        candidate_id="cand-event-1",
        run_id="run-1",
        call_id="call-1",
        event_type="diagnosis",
        start_range=_date_range(precision=DatePrecision.YEAR, lower=date(2020, 1, 1), upper=date(2020, 12, 31)),
        end_range=None,
        duration_status=DurationStatus.ONGOING,
        record_time=_UTC,
        fact_candidate_ids=["cand-fact-1"],
        locator_ids=["loc-1"],
        candidate_source_semantics="direct_record",
        model_uncertainty=0.1,
        created_at=_UTC,
    )
    assert event.event_type == "diagnosis"
    exposure = MedicationExposureCandidateV2(
        candidate_id="cand-exposure-1",
        run_id="run-1",
        call_id="call-1",
        medication_name="二甲双胍",
        start_range=_date_range(lower=date(2026, 1, 1), upper=date(2026, 1, 1)),
        end_range=None,
        duration_status=DurationStatus.ONGOING,
        record_time=_UTC,
        fact_candidate_ids=["cand-fact-1"],
        locator_ids=["loc-1"],
        candidate_source_semantics="direct_record",
        model_uncertainty=0.05,
        created_at=_UTC,
    )
    assert exposure.duration_status == DurationStatus.ONGOING
    assert exposure.record_time == _UTC


def test_exposure_candidate_ended_requires_explicit_end():
    with pytest.raises(ValidationError, match="已结束"):
        MedicationExposureCandidateV2(
            candidate_id="cand-exposure-2",
            run_id="run-1",
            call_id="call-1",
            medication_name="二甲双胍",
            start_range=_date_range(lower=date(2026, 1, 1), upper=date(2026, 1, 1)),
            end_range=None,
            duration_status=DurationStatus.ENDED,
            record_time=_UTC,
            fact_candidate_ids=["cand-fact-1"],
            locator_ids=["loc-1"],
            candidate_source_semantics="direct_record",
            model_uncertainty=0.05,
            created_at=_UTC,
        )


# ------------------------------------------------------------- 发布合同


def test_published_fact_carries_authority_gate_strength_revision():
    fact = _fact()
    assert fact.authority.evidence_snapshot_v2_id == "snapshot-v2-1"
    assert fact.gate_id == "gate-run-1"
    assert fact.source_strength == SourceStrength.SCREENING_RECORD_TRANSCRIPTION
    assert fact.revision == 1


def test_published_fact_has_no_model_uncertainty_field():
    """发布合同不携带可用于临床裁决的模型置信度。"""
    fact = _fact()
    assert "model_uncertainty" not in fact.model_dump()
    assert not hasattr(fact, "model_uncertainty")


def test_published_fact_stable_identity_tamper_rejected():
    with pytest.raises(ValidationError, match="稳定身份"):
        _fact(stable_identity="b" * 64)


def test_published_fact_asserted_object_must_match_basis():
    with pytest.raises(ValidationError, match="断言依据对象一致"):
        _fact(asserted_object="糖尿病")


def test_published_fact_unknown_polarity_rejected_with_value():
    with pytest.raises(ValidationError, match="未知极性"):
        _fact(polarity=FactPolarity.UNKNOWN, value="正常", assertion_basis=None)


def test_stable_identity_excludes_locator_and_confidence():
    """同内容多来源合并：稳定身份不含定位与置信度。"""
    a = clinical_fact_stable_identity(
        authority=_authority(),
        fact_type="medical_history",
        asserted_object="高血压病史",
        polarity=FactPolarity.NEGATED,
        value="无",
        unit=None,
        date_range=_date_range(),
    )
    b = clinical_fact_stable_identity(
        authority=_authority(),
        fact_type="medical_history",
        asserted_object="高血压病史",
        polarity=FactPolarity.NEGATED,
        value="无",
        unit=None,
        date_range=_date_range(),
    )
    assert a == b
    changed_value = clinical_fact_stable_identity(
        authority=_authority(),
        fact_type="medical_history",
        asserted_object="高血压病史",
        polarity=FactPolarity.NEGATED,
        value="有",
        unit=None,
        date_range=_date_range(),
    )
    assert a != changed_value
    changed_object = clinical_fact_stable_identity(
        authority=_authority(),
        fact_type="medical_history",
        asserted_object="糖尿病病史",
        polarity=FactPolarity.NEGATED,
        value="无",
        unit=None,
        date_range=_date_range(),
    )
    assert a != changed_object
    changed_authority = clinical_fact_stable_identity(
        authority=_authority(complete_processing_revision_id="complete-rev-2"),
        fact_type="medical_history",
        asserted_object="高血压病史",
        polarity=FactPolarity.NEGATED,
        value="无",
        unit=None,
        date_range=_date_range(),
    )
    assert a != changed_authority
    changed_lane = clinical_fact_stable_identity(
        authority=_authority(),
        fact_type="medical_history",
        profile_lane=ProfileLane.TARGET_DISEASE,
        asserted_object="高血压病史",
        polarity=FactPolarity.NEGATED,
        value="无",
        unit=None,
        date_range=_date_range(),
    )
    assert a != changed_lane


def test_event_and_exposure_published_contracts_ok():
    event = _event()
    assert event.stable_identity == clinical_event_stable_identity(
        authority=event.authority,
        event_type=event.event_type,
        referenced_fact_objects=event.referenced_fact_objects,
        start_range=event.start_range,
        end_range=event.end_range,
        duration_status=event.duration_status,
    )
    exposure = _exposure()
    assert exposure.stable_identity == medication_exposure_stable_identity(
        authority=exposure.authority,
        medication_name=exposure.medication_name,
        category=exposure.category,
        indication=exposure.indication,
        dose=exposure.dose,
        unit=exposure.unit,
        frequency=exposure.frequency,
        route=exposure.route,
        start_range=exposure.start_range,
        end_range=exposure.end_range,
        duration_status=exposure.duration_status,
    )


def test_exposure_ongoing_cannot_carry_end_range():
    with pytest.raises(ValidationError, match="持续暴露"):
        _exposure(
            end_range=_date_range(lower=date(2026, 6, 1), upper=date(2026, 6, 1)),
            duration_status=DurationStatus.ONGOING,
        )


def test_exposure_ended_requires_end_range():
    with pytest.raises(ValidationError, match="已结束"):
        _exposure(end_range=None, duration_status=DurationStatus.ENDED)


def test_event_stable_identity_tamper_rejected():
    with pytest.raises(ValidationError, match="稳定身份"):
        _event(stable_identity="b" * 64)


def test_event_ended_requires_distinct_end_range():
    ended = _event(
        start_range=_date_range(
            precision=DatePrecision.MONTH,
            lower=date(2025, 1, 1),
            upper=date(2025, 1, 31),
        ),
        end_range=_date_range(
            precision=DatePrecision.MONTH,
            lower=date(2025, 3, 1),
            upper=date(2025, 3, 31),
        ),
        duration_status=DurationStatus.ENDED,
    )
    assert ended.start_range.lower_bound == date(2025, 1, 1)
    assert ended.end_range.upper_bound == date(2025, 3, 31)
    with pytest.raises(ValidationError, match="已结束"):
        _event(end_range=None, duration_status=DurationStatus.ENDED)


def test_conflict_group_requires_at_least_two_facts_and_is_unresolved_by_default():
    group = ClinicalConflictGroupV2(
        conflict_group_id="conflict-1",
        run_id="run-1",
        gate_id="gate-run-1",
        authority=_authority(),
        fact_ids=["fact-1", "fact-2"],
        locator_ids=["loc-1", "loc-2"],
        created_at=_UTC,
    )
    assert group.resolution_revision == 0
    with pytest.raises(ValidationError, match="只允许追加未解决冲突"):
        ClinicalConflictGroupV2.model_validate(
            {**group.model_dump(), "resolution_revision": 1}
        )
    with pytest.raises(ValidationError):
        ClinicalConflictGroupV2(
            conflict_group_id="conflict-2",
            run_id="run-1",
            gate_id="gate-run-1",
            authority=_authority(),
            fact_ids=["fact-1"],
            locator_ids=["loc-1"],
            created_at=_UTC,
        )


# ------------------------------------------------------------- 运行/调用/门禁


def _run(**overrides):
    authority = overrides.pop("authority", None) or _authority()
    base = {
        "run_id": "run-1",
        "authority": authority,
        "prompt_version_id": "prompt-v1",
        "model_config_id": "model-config-1",
        "input_scope_sha256": SHA,
        "status": FactNormalizationRunStatus.RUNNING,
        "created_at": _UTC,
        "created_by": "system",
    }
    base.update(overrides)
    if "idempotency_key" not in overrides:
        base["idempotency_key"] = fact_run_idempotency_key(
            authority=base["authority"],
            prompt_version_id=base["prompt_version_id"],
            model_config_id=base["model_config_id"],
            input_scope_sha256=base["input_scope_sha256"],
        )
    return FactNormalizationRun(**base)


def test_run_idempotency_key_matches_frozen_identity():
    run = _run()
    assert run.idempotency_key == fact_run_idempotency_key(
        authority=run.authority,
        prompt_version_id=run.prompt_version_id,
        model_config_id=run.model_config_id,
        input_scope_sha256=run.input_scope_sha256,
    )


def test_run_idempotency_key_tamper_rejected():
    with pytest.raises(ValidationError, match="幂等键"):
        _run(idempotency_key="b" * 64)


def test_run_binds_complete_revision_without_reviewrun():
    """规范化运行只绑定完整处理修订；不得伪造 Phase 6 ReviewRun。"""
    run = _run()
    assert run.authority.complete_processing_revision_id == "complete-rev-1"
    assert "review_run" not in run.model_dump()


def test_call_page_list_must_be_sorted_unique_and_positive():
    call = FactNormalizationCall(
        call_id="call-1",
        run_id="run-1",
        logical_document_id="doc-1",
        page_numbers=[1, 2, 3],
        status=FactCallStatus.SUCCEEDED,
        input_sha256=SHA,
        created_at=_UTC,
    )
    assert call.page_numbers == [1, 2, 3]
    with pytest.raises(ValidationError, match="升序"):
        FactNormalizationCall(
            call_id="call-2",
            run_id="run-1",
            logical_document_id="doc-1",
            page_numbers=[3, 1],
            status=FactCallStatus.SUCCEEDED,
            input_sha256=SHA,
            created_at=_UTC,
        )
    with pytest.raises(ValidationError, match="升序"):
        FactNormalizationCall(
            call_id="call-3",
            run_id="run-1",
            logical_document_id="doc-1",
            page_numbers=[0],
            status=FactCallStatus.SUCCEEDED,
            input_sha256=SHA,
            created_at=_UTC,
        )


def test_gate_result_rejected_requires_reason():
    ok = FactGateResult(
        gate_result_id="gate-1",
        run_id="run-1",
        call_id="call-1",
        candidate_id="cand-fact-1",
        gate=FactGate.LOCATOR_AND_TEXT_HASH,
        outcome=GateOutcome.ACCEPTED,
        created_at=_UTC,
    )
    assert ok.outcome == GateOutcome.ACCEPTED
    with pytest.raises(ValidationError, match="原因"):
        FactGateResult(
            gate_result_id="gate-2",
            run_id="run-1",
            call_id="call-1",
            candidate_id="cand-fact-1",
            gate=FactGate.POLARITY_AND_ASSERTED_OBJECT,
            outcome=GateOutcome.REJECTED,
            reasons=[],
            created_at=_UTC,
        )


def test_gate_sequence_covers_design_order():
    """设计书 §4.2 九个门禁步骤全部出现在合同枚举中。"""
    ordered = [
        FactGate.CONTRACT_AND_ENUM,
        FactGate.AUTHORITY_AND_ACTIVE_REVISION,
        FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE,
        FactGate.LOCATOR_AND_TEXT_HASH,
        FactGate.POLARITY_AND_ASSERTED_OBJECT,
        FactGate.VALUE_UNIT_DATE_SOURCE,
        FactGate.IN_DOCUMENT_DEDUP_CONFLICT,
        FactGate.CROSS_DOCUMENT_MERGE_CONFLICT,
        FactGate.TRANSACTIONAL_PUBLISH,
    ]
    assert list(FactGate) == ordered


def test_candidate_and_published_contracts_are_physically_separate():
    """候选合同携带模型不确定性；发布合同不携带，且二者为不同类型。"""
    candidate = _fact_candidate()
    published = _fact()
    assert type(candidate) is not type(published)
    assert "model_uncertainty" in candidate.model_dump()
    assert "model_uncertainty" not in published.model_dump()
    assert published.schema_version == "phase5/v1"
    assert candidate.schema_version == "phase5/v1"
