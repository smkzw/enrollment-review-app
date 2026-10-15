"""Phase 5 Slice 5.2 批量门禁编排聚焦测试（纯确定性）。

覆盖批量编排职责：
- 稳定精确去重分组（权威元组+类型/极性/规范值/单位/日期/持续状态，不含定位/置信度）
- 语义冲突检测（同一语义对象但不同稳定身份时建立未解决组，不择优）
- 逐候选裁决与受影响范围（IN_DOCUMENT / CROSS_DOCUMENT 两门）
- 空输出与页覆盖不完整失败行为（不生成空 Profile）
- 持久化衔接（FactGateResult 确定性转换，不发布事实）
- 属性/反例测试（确定性、排序、无赢家、幂等）

所有用例基于结构化 fixture，不调用模型、不发布事实/Profile、不创建 API/UI。
"""

from __future__ import annotations

import calendar
import random
from datetime import date, datetime, timezone, timedelta

import pytest
from pydantic import ValidationError

from app.domain.contracts.enums import DatePrecision, DurationStatus, FactGate, FactPolarity, GateOutcome
from app.domain.contracts.facts import (
    AssertionBasis,
    ClinicalEventCandidateV2,
    ClinicalFactCandidateV2,
    FactAuthority,
    MedicationExposureCandidateV2,
    PartialDateRange,
    FactNormalizationCall,
    FactGateResult,
    clinical_event_stable_identity,
)
from app.domain.contracts.fact_gates import BatchGateResult, DedupGroup, SemanticConflictGroup
from app.domain.gates.fact_batch_orchestration import (
    compute_stable_identity_map,
    detect_semantic_conflicts,
    group_exact_duplicates,
    gate_in_document_dedup_conflict,
    gate_cross_document_merge_conflict,
    orchestrate_batch_gates,
    orchestrate_run_gates,
    run_gate_results_to_fact_gate_results,
    batch_gate_results_to_fact_gate_results,
)
from app.domain.contracts.evidence_locator import CompleteEvidenceProcessingRevision, EvidenceLocatorArtifact
from app.domain.contracts.evidence_processing import EvidenceProcessingRevisionPage
from app.domain.contracts.enums import LocatorAuthenticity, LocatorPrecision, LocatorSourceLayer

UTC = timezone.utc
SHA = "a" * 64
SHA_B = "b" * 64
_NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)
_AUTHORITY = FactAuthority(
    project_id="proj-1",
    subject_id="subj-1",
    review_episode_id="ep-1",
    episode_revision=1,
    protocol_version_id="pv-1",
    rule_set_id="rs-1",
    rule_set_revision=1,
    evidence_snapshot_v2_id="snap-1",
    complete_processing_revision_id="rev-1",
)
_AUTHORITY2 = FactAuthority(
    project_id="proj-1",
    subject_id="subj-1",
    review_episode_id="ep-1",
    episode_revision=1,
    protocol_version_id="pv-1",
    rule_set_id="rs-1",
    rule_set_revision=1,
    evidence_snapshot_v2_id="snap-1",
    complete_processing_revision_id="rev-2",
)


def _range_day(d: date = date(2026, 3, 1)) -> PartialDateRange:
    return PartialDateRange(source_text=d.isoformat(), precision=DatePrecision.DAY, lower_bound=d, upper_bound=d)


def _range_month(y: int = 2026, m: int = 2) -> PartialDateRange:
    last = calendar.monthrange(y, m)[1]
    return PartialDateRange(
        source_text=f"{y}-{m:02d}", precision=DatePrecision.MONTH, lower_bound=date(y, m, 1), upper_bound=date(y, m, last)
    )


def _range_year(y: int = 2020) -> PartialDateRange:
    return PartialDateRange(source_text=str(y), precision=DatePrecision.YEAR, lower_bound=date(y, 1, 1), upper_bound=date(y, 12, 31))


def _range_unknown() -> PartialDateRange:
    return PartialDateRange(source_text=None, precision=DatePrecision.UNKNOWN, lower_bound=None, upper_bound=None)


def _basis(locator_id: str = "loc-1", asserted_object: str = "高血压", text: str = "否认高血压病史") -> AssertionBasis:
    return AssertionBasis(asserted_object=asserted_object, assertion_text=text, locator_id=locator_id, source_text_sha256=SHA)


def _make_revision(manifest_entries: list[tuple[str, int, str]]) -> CompleteEvidenceProcessingRevision:
    # manifest_entries: list of (source_doc_version_id, page_number, page_artifact_id)
    # 使用 model_construct 绕过 manifest_sha256 严格校验，仅保留 validate_page_coverage 所需字段
    manifest = []
    for idx, (src, pn, pa) in enumerate(manifest_entries, start=1):
        page = EvidenceProcessingRevisionPage.model_construct(
            entry_id=f"entry-{idx}",
            position=idx,
            source_document_version_id=src,
            page_number=pn,
            original_frame=None,
            page_artifact_id=pa,
            ocr_page_id=f"op-{pa}-{pn}",
            status="succeeded",
            failure_reason=None,
        )
        manifest.append(page)
    # 使用 model_construct 创建完整修订，绕过 manifest_sha256 校验
    rev = CompleteEvidenceProcessingRevision.model_construct(
        evidence_processing_revision_id="rev-1",
        evidence_snapshot_id="snap-1",
        project_id="proj-1",
        subject_id="subj-1",
        review_episode_id="ep-1",
        revision_kind="complete",
        base_processing_revision_id="base-1",
        producer_candidate_id="cand-1",
        candidate_input_sha256=SHA,
        manifest=manifest,
        manifest_sha256=SHA,
        locator_ids=["loc-1", "loc-2"],
        risk_scan_ids=[],
        risk_review_ids=[],
        correction_ids=[],
        metadata_revision_ids=[],
        referenced_document_revision_ids=[],
        resolution_revision_ids=[],
        completion_manifest_sha256=SHA,
        status="ready",
        is_activatable=True,
        created_at=_NOW,
        created_by="tester",
    )
    return rev


def _make_call(logical_document_id: str = "doc-1", pages: list[int] | None = None) -> FactNormalizationCall:
    if pages is None:
        pages = [1]
    return FactNormalizationCall(
        call_id="call-1",
        run_id="run-1",
        logical_document_id=logical_document_id,
        page_numbers=pages,
        status="succeeded",
        input_sha256=SHA,
        created_at=_NOW,
    )


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
    # 预处理：若仅改变 locator_ids 或 asserted_object 而未显式提供 basis，保持一致性
    if "locator_ids" in overrides and "assertion_basis" not in overrides:
        new_locs = overrides["locator_ids"]
        if new_locs:
            asserted = overrides.get("asserted_object", base["asserted_object"])
            base["assertion_basis"] = _basis(new_locs[0], asserted, base["assertion_basis"].assertion_text if isinstance(base["assertion_basis"], AssertionBasis) else "受试者既往有高血压病史")
    elif "asserted_object" in overrides and "assertion_basis" not in overrides and "locator_ids" not in overrides:
        new_obj = overrides["asserted_object"]
        loc = base["locator_ids"][0]
        if isinstance(base["assertion_basis"], AssertionBasis):
            base["assertion_basis"] = _basis(loc, new_obj, base["assertion_basis"].assertion_text)
    base.update(overrides)
    # 后处理：若 basis 存在但其 locator 不在 locator_ids 中，自动补齐以通过合同
    basis = base.get("assertion_basis")
    locs = base.get("locator_ids")
    if isinstance(basis, AssertionBasis) and isinstance(locs, list):
        if basis.locator_id not in locs:
            base["locator_ids"] = sorted(set(locs) | {basis.locator_id})
        # 若 asserted_object 与 basis 对象不一致且两者均显式传入，则保持原值让合同报错；
        # 否则若仅 locator 对齐后仍不一致，自动对齐 basis 对象（适用于仅改 locator 的去重用例）
        if base.get("asserted_object") != basis.asserted_object and "asserted_object" not in overrides and "assertion_basis" not in overrides:
            base["assertion_basis"] = _basis(basis.locator_id, base["asserted_object"], basis.assertion_text)
    # 极性 UNKNOWN 时确保无 basis/value
    if base.get("polarity") == FactPolarity.UNKNOWN:
        base["assertion_basis"] = None
        base["canonical_value"] = None
        base["raw_value"] = None
        base["unit"] = None
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




# ---------------------------------------------------------------------------
# 精确去重分组
# ---------------------------------------------------------------------------


def test_exact_dedup_groups_same_stable_identity():
    # 两个事实候选内容完全一致（不同 locator、不同 candidate_id），应分到同一去重组
    f1 = _fact_candidate(candidate_id="f-1", locator_ids=["loc-1"])
    f2 = _fact_candidate(candidate_id="f-2", locator_ids=["loc-2"])
    groups = group_exact_duplicates(
        authority=_AUTHORITY,
        fact_candidates=[f1, f2],
        event_candidates=[],
        exposure_candidates=[],
    )
    assert len(groups) == 1
    assert groups[0].candidate_ids == ["f-1", "f-2"]
    assert groups[0].merged_locator_ids == ["loc-1", "loc-2"]
    # 验证稳定身份确实相同
    m = compute_stable_identity_map(authority=_AUTHORITY, fact_candidates=[f1, f2], event_candidates=[], exposure_candidates=[])
    assert m["f-1"] == m["f-2"]
    assert m["f-1"] == groups[0].stable_identity


def test_exact_dedup_excludes_different_value():
    f1 = _fact_candidate(candidate_id="f-1", canonical_value="高血压", asserted_object="高血压", assertion_basis=_basis("loc-1", "高血压", "高血压"))
    f2 = _fact_candidate(candidate_id="f-2", canonical_value="糖尿病", asserted_object="糖尿病", fact_type="diagnosis", assertion_basis=_basis("loc-1", "糖尿病", "糖尿病"))
    # 改变被断言对象导致稳定身份不同，不应去重
    f2b = _fact_candidate(candidate_id="f-2", canonical_value="高血压", asserted_object="高血压", fact_type="diagnosis", polarity=FactPolarity.NEGATED, assertion_basis=_basis("loc-1", "高血压", "无高血压"))
    groups = group_exact_duplicates(authority=_AUTHORITY, fact_candidates=[f1, f2b], event_candidates=[], exposure_candidates=[])
    # f1 affirmed, f2b negated => polarity 不同 => 不同身份 => 不去重
    assert len(groups) == 0


def test_exact_dedup_excludes_locator_and_confidence():
    # 同内容不同 locator / 置信度 应视为同一去重键（不含定位与置信度）
    f1 = _fact_candidate(candidate_id="f-1", locator_ids=["loc-1"], model_uncertainty=0.1)
    f2 = _fact_candidate(candidate_id="f-2", locator_ids=["loc-2"], model_uncertainty=0.9)
    groups = group_exact_duplicates(authority=_AUTHORITY, fact_candidates=[f1, f2], event_candidates=[], exposure_candidates=[])
    assert len(groups) == 1
    assert groups[0].candidate_ids == ["f-1", "f-2"]


def test_exact_dedup_different_authority_yields_different_identity():
    f1 = _fact_candidate(candidate_id="f-1", locator_ids=["loc-1"])
    f2 = _fact_candidate(candidate_id="f-2", locator_ids=["loc-1"])
    m1 = compute_stable_identity_map(authority=_AUTHORITY, fact_candidates=[f1], event_candidates=[], exposure_candidates=[])
    m2 = compute_stable_identity_map(authority=_AUTHORITY2, fact_candidates=[f2], event_candidates=[], exposure_candidates=[])
    assert m1["f-1"] != m2["f-2"]
    # 跨权威元组不应在同一批次内混批（此处仅验证身份函数区分权威）
    groups = group_exact_duplicates(authority=_AUTHORITY, fact_candidates=[f1, f2], event_candidates=[], exposure_candidates=[])
    # f1 与 f2 在同一 authority 下相同身份，会合并（因为我们传入同一 authority）
    # 但若批次权威不同，调用方应避免混批；此处验证函数本身区分权威
    assert len(groups) == 1


def test_exact_dedup_sorted_deterministic():
    # 乱序输入应产生相同且排序的去重组
    f1 = _fact_candidate(candidate_id="f-3", locator_ids=["loc-3"])
    f2 = _fact_candidate(candidate_id="f-1", locator_ids=["loc-1"])
    f3 = _fact_candidate(candidate_id="f-2", locator_ids=["loc-2"])
    # f1,f2,f3 内容相同（fact_type/极性/值等一致）
    groups_a = group_exact_duplicates(authority=_AUTHORITY, fact_candidates=[f1, f2, f3], event_candidates=[], exposure_candidates=[])
    groups_b = group_exact_duplicates(authority=_AUTHORITY, fact_candidates=[f3, f1, f2], event_candidates=[], exposure_candidates=[])
    assert groups_a == groups_b
    assert groups_a[0].candidate_ids == ["f-1", "f-2", "f-3"]
    assert groups_a[0].merged_locator_ids == ["loc-1", "loc-2", "loc-3"]


def test_exact_dedup_event_and_exposure():
    e1 = _event_candidate(candidate_id="e-1", locator_ids=["loc-1"])
    e2 = _event_candidate(candidate_id="e-2", locator_ids=["loc-2"])
    groups = group_exact_duplicates(authority=_AUTHORITY, fact_candidates=[], event_candidates=[e1, e2], exposure_candidates=[])
    assert len(groups) == 1
    assert groups[0].candidate_ids == ["e-1", "e-2"]

    x1 = _exposure_candidate(candidate_id="x-1", locator_ids=["loc-1"])
    x2 = _exposure_candidate(candidate_id="x-2", locator_ids=["loc-2"])
    groups2 = group_exact_duplicates(authority=_AUTHORITY, fact_candidates=[], event_candidates=[], exposure_candidates=[x1, x2])
    assert len(groups2) == 1
    assert groups2[0].candidate_ids == ["x-1", "x-2"]


# ---------------------------------------------------------------------------
# 语义冲突检测（不择优）
# ---------------------------------------------------------------------------


def test_semantic_conflict_fact_same_object_different_polarity():
    f1 = _fact_candidate(candidate_id="f-1", polarity=FactPolarity.AFFIRMED, canonical_value="高血压", asserted_object="高血压", assertion_basis=_basis("loc-1", "高血压", "有高血压"))
    f2 = _fact_candidate(candidate_id="f-2", polarity=FactPolarity.NEGATED, canonical_value="高血压", asserted_object="高血压", assertion_basis=_basis("loc-2", "高血压", "无高血压"))
    conflicts = detect_semantic_conflicts(authority=_AUTHORITY, fact_candidates=[f1, f2], event_candidates=[], exposure_candidates=[])
    assert len(conflicts) == 1
    assert conflicts[0].semantic_key == "fact:diagnosis:高血压"
    assert conflicts[0].candidate_ids == ["f-1", "f-2"]
    assert len(conflicts[0].distinct_stable_identities) == 2
    # 验证不择优：冲突组包含全部成员，无赢家字段
    assert conflicts[0].semantic_type == "fact"


def test_semantic_fact_same_payload_different_date_is_longitudinal_not_conflict():
    f1 = _fact_candidate(candidate_id="f-1", date_range=_range_day(date(2020, 1, 1)))
    f2 = _fact_candidate(candidate_id="f-2", date_range=_range_day(date(2021, 1, 1)))
    conflicts = detect_semantic_conflicts(authority=_AUTHORITY, fact_candidates=[f1, f2], event_candidates=[], exposure_candidates=[])
    assert conflicts == []


def test_different_fact_values_at_definitely_disjoint_dates_are_longitudinal():
    f1 = _fact_candidate(
        candidate_id="f-1", raw_value="120", canonical_value="120",
        date_range=_range_day(date(2020, 1, 1)),
    )
    f2 = _fact_candidate(
        candidate_id="f-2", raw_value="130", canonical_value="130",
        date_range=_range_day(date(2021, 1, 1)),
    )
    assert detect_semantic_conflicts(
        authority=_AUTHORITY,
        fact_candidates=[f1, f2],
        event_candidates=[],
        exposure_candidates=[],
    ) == []


def test_different_fact_values_with_unknown_time_remain_a_conflict():
    f1 = _fact_candidate(
        candidate_id="f-1", raw_value="120", canonical_value="120",
        date_range=_range_unknown(),
    )
    f2 = _fact_candidate(
        candidate_id="f-2", raw_value="130", canonical_value="130",
        date_range=_range_day(date(2021, 1, 1)),
    )
    conflicts = detect_semantic_conflicts(
        authority=_AUTHORITY,
        fact_candidates=[f1, f2],
        event_candidates=[],
        exposure_candidates=[],
    )
    assert len(conflicts) == 1
    assert "时间重叠无法排除" in conflicts[0].reasons[0]


def test_semantic_conflict_event_same_type_different_status():
    e1 = _event_candidate(candidate_id="e-1", duration_status=DurationStatus.ONGOING, end_range=None)
    e2 = _event_candidate(candidate_id="e-2", duration_status=DurationStatus.ENDED, end_range=_range_day(date(2026, 3, 2)), start_range=_range_day(date(2026, 1, 10)))
    conflicts = detect_semantic_conflicts(authority=_AUTHORITY, fact_candidates=[], event_candidates=[e1, e2], exposure_candidates=[])
    assert len(conflicts) == 1
    assert conflicts[0].semantic_type == "event"
    assert conflicts[0].candidate_ids == ["e-1", "e-2"]


def test_semantic_conflict_exposure_same_med_different_dose():
    x1 = _exposure_candidate(candidate_id="x-1", dose="500", unit="mg")
    x2 = _exposure_candidate(candidate_id="x-2", dose="1000", unit="mg")
    conflicts = detect_semantic_conflicts(authority=_AUTHORITY, fact_candidates=[], event_candidates=[], exposure_candidates=[x1, x2])
    assert len(conflicts) == 1
    assert conflicts[0].semantic_key == "exposure:二甲双胍"
    assert conflicts[0].candidate_ids == ["x-1", "x-2"]


def test_serial_exposure_dose_change_is_not_a_conflict():
    x1 = _exposure_candidate(
        candidate_id="x-1", dose="500", duration_status=DurationStatus.ENDED,
        start_range=_range_day(date(2020, 1, 1)),
        end_range=_range_day(date(2020, 6, 30)),
    )
    x2 = _exposure_candidate(
        candidate_id="x-2", dose="1000", duration_status=DurationStatus.ENDED,
        start_range=_range_day(date(2020, 7, 1)),
        end_range=_range_day(date(2020, 12, 31)),
    )
    assert detect_semantic_conflicts(
        authority=_AUTHORITY,
        fact_candidates=[],
        event_candidates=[],
        exposure_candidates=[x1, x2],
    ) == []


def test_separate_single_doses_are_not_a_conflict():
    x1 = _exposure_candidate(
        candidate_id="x-1", dose="300", duration_status=DurationStatus.SINGLE,
        start_range=_range_day(date(2025, 4, 9)), end_range=None,
    )
    x2 = _exposure_candidate(
        candidate_id="x-2", dose="300", duration_status=DurationStatus.SINGLE,
        start_range=_range_day(date(2025, 6, 4)), end_range=None,
    )
    assert detect_semantic_conflicts(
        authority=_AUTHORITY,
        fact_candidates=[],
        event_candidates=[],
        exposure_candidates=[x1, x2],
    ) == []


def test_unknown_exposure_detail_does_not_conflict_with_more_complete_record():
    start = _range_day(date(2025, 4, 5))
    partial = _exposure_candidate(
        candidate_id="x-1", dose=None, unit=None,
        duration_status=DurationStatus.UNKNOWN, start_range=start, end_range=None,
    )
    complete = _exposure_candidate(
        candidate_id="x-2", dose="8.8", unit="mg",
        duration_status=DurationStatus.ENDED, start_range=start,
        end_range=_range_day(date(2025, 4, 19)),
    )
    assert detect_semantic_conflicts(
        authority=_AUTHORITY,
        fact_candidates=[],
        event_candidates=[],
        exposure_candidates=[partial, complete],
    ) == []


def test_compatible_indication_wording_is_not_a_deterministic_conflict():
    start = _range_day(date(2025, 4, 5))
    broad = _exposure_candidate(
        candidate_id="x-1", indication="过敏性鼻炎",
        duration_status=DurationStatus.UNKNOWN, start_range=start, end_range=None,
    )
    specific = _exposure_candidate(
        candidate_id="x-2", indication="季节性过敏性鼻炎",
        duration_status=DurationStatus.ENDED, start_range=start,
        end_range=_range_day(date(2025, 4, 19)),
    )
    assert detect_semantic_conflicts(
        authority=_AUTHORITY,
        fact_candidates=[],
        event_candidates=[],
        exposure_candidates=[broad, specific],
    ) == []


def test_semantic_conflict_not_triggered_for_duplicates():
    # 同一语义对象且同一稳定身份 => 去重，不应产生冲突
    f1 = _fact_candidate(candidate_id="f-1", locator_ids=["loc-1"])
    f2 = _fact_candidate(candidate_id="f-2", locator_ids=["loc-2"])
    conflicts = detect_semantic_conflicts(authority=_AUTHORITY, fact_candidates=[f1, f2], event_candidates=[], exposure_candidates=[])
    assert len(conflicts) == 0
    dedups = group_exact_duplicates(authority=_AUTHORITY, fact_candidates=[f1, f2], event_candidates=[], exposure_candidates=[])
    assert len(dedups) == 1


def test_semantic_conflict_different_semantic_keys_no_conflict():
    f1 = _fact_candidate(candidate_id="f-1", asserted_object="高血压", fact_type="diagnosis", assertion_basis=_basis("loc-1", "高血压", "高血压"))
    f2 = _fact_candidate(candidate_id="f-2", asserted_object="糖尿病", fact_type="diagnosis", assertion_basis=_basis("loc-2", "糖尿病", "糖尿病"), canonical_value="糖尿病")
    conflicts = detect_semantic_conflicts(authority=_AUTHORITY, fact_candidates=[f1, f2], event_candidates=[], exposure_candidates=[])
    assert len(conflicts) == 0


def test_multiple_serial_fact_observations_are_not_a_conflict_group():
    f1 = _fact_candidate(candidate_id="f-1", date_range=_range_day(date(2020, 1, 1)))
    f2 = _fact_candidate(candidate_id="f-2", date_range=_range_day(date(2021, 1, 1)))
    f3 = _fact_candidate(candidate_id="f-3", date_range=_range_day(date(2022, 1, 1)))
    conflicts = detect_semantic_conflicts(authority=_AUTHORITY, fact_candidates=[f1, f2, f3], event_candidates=[], exposure_candidates=[])
    assert conflicts == []


# ---------------------------------------------------------------------------
# 逐候选门禁：受影响范围与确定性排序
# ---------------------------------------------------------------------------


def test_gate_in_document_dedup_affected_scope_sorted():
    f1 = _fact_candidate(candidate_id="f-1", locator_ids=["loc-1"])
    f2 = _fact_candidate(candidate_id="f-2", locator_ids=["loc-2"])
    # f3 使用不同 asserted_object/值以形成不同稳定身份，避免与 f1/f2 去重
    f3 = _fact_candidate(candidate_id="f-3", locator_ids=["loc-3"], asserted_object="糖尿病", canonical_value="糖尿病", fact_type="diagnosis", assertion_basis=_basis("loc-3", "糖尿病", "糖尿病"))
    # f1,f2 去重，f3 唯一
    verdicts = gate_in_document_dedup_conflict(authority=_AUTHORITY, fact_candidates=[f1, f2, f3], event_candidates=[], exposure_candidates=[])
    # f1 的 affected 应为其他重复者 f-2
    assert verdicts["f-1"].affected_scope == ["f-2"]
    assert verdicts["f-2"].affected_scope == ["f-1"]
    assert verdicts["f-3"].affected_scope == []
    # 均为 ACCEPTED
    assert all(v.outcome == GateOutcome.ACCEPTED for v in verdicts.values())
    # 确定性排序
    assert list(verdicts.keys()) == sorted(verdicts.keys())


def test_gate_cross_document_conflict_affected_scope_and_outcome():
    f1 = _fact_candidate(candidate_id="f-1", polarity=FactPolarity.AFFIRMED, canonical_value="高血压", asserted_object="高血压", assertion_basis=_basis("loc-1", "高血压", "有高血压"))
    f2 = _fact_candidate(candidate_id="f-2", polarity=FactPolarity.NEGATED, canonical_value="高血压", asserted_object="高血压", assertion_basis=_basis("loc-2", "高血压", "无高血压"))
    f3 = _fact_candidate(candidate_id="f-3", asserted_object="糖尿病", fact_type="diagnosis", canonical_value="糖尿病", assertion_basis=_basis("loc-3", "糖尿病", "糖尿病"))
    verdicts = gate_cross_document_merge_conflict(authority=_AUTHORITY, fact_candidates=[f1, f2, f3], event_candidates=[], exposure_candidates=[])
    assert verdicts["f-1"].outcome == GateOutcome.ACCEPTED
    assert verdicts["f-2"].outcome == GateOutcome.ACCEPTED
    assert verdicts["f-1"].affected_scope == ["f-2"]
    assert verdicts["f-2"].affected_scope == ["f-1"]
    assert verdicts["f-3"].outcome == GateOutcome.ACCEPTED
    assert verdicts["f-3"].affected_scope == []
    # reasons 非空且有序
    assert verdicts["f-1"].reasons == sorted(verdicts["f-1"].reasons)


def test_batch_orchestration_per_candidate_outcomes_deterministic():
    f1 = _fact_candidate(candidate_id="f-1", locator_ids=["loc-1"])
    f2 = _fact_candidate(candidate_id="f-2", locator_ids=["loc-2"])
    # 打乱输入顺序，两次编排结果应一致
    r1 = orchestrate_batch_gates(authority=_AUTHORITY, run_id="run-1", call_id="call-1", fact_candidates=[f1, f2], event_candidates=[], exposure_candidates=[])
    r2 = orchestrate_batch_gates(authority=_AUTHORITY, run_id="run-1", call_id="call-1", fact_candidates=[f2, f1], event_candidates=[], exposure_candidates=[])
    assert r1.dedup_groups == r2.dedup_groups
    assert r1.conflict_groups == r2.conflict_groups
    assert r1.gate_results == r2.gate_results
    assert r1.affected_scope == r2.affected_scope
    # gate_results 已按 (candidate_id, gate) 排序
    assert r1.gate_results == sorted(r1.gate_results, key=lambda v: (v.candidate_id, v.gate.value))


# ---------------------------------------------------------------------------
# 空输出失败
# ---------------------------------------------------------------------------


def test_batch_empty_output_rejected():
    result = orchestrate_batch_gates(authority=_AUTHORITY, run_id="run-1", call_id="call-1", fact_candidates=[], event_candidates=[], exposure_candidates=[])
    assert result.overall_outcome == GateOutcome.REJECTED
    assert any("为空" in r for r in result.failure_reasons)
    assert result.gate_results == []
    assert result.dedup_groups == []
    assert result.conflict_groups == []


def test_batch_empty_output_no_profile_persistence():
    result = orchestrate_batch_gates(authority=_AUTHORITY, run_id="run-1", call_id="call-1", fact_candidates=[], event_candidates=[], exposure_candidates=[])
    gate_results = batch_gate_results_to_fact_gate_results(result, created_at=_NOW)
    assert gate_results == []


# ---------------------------------------------------------------------------
# 页覆盖不完整失败
# ---------------------------------------------------------------------------


def test_batch_incomplete_page_coverage_rejected():
    rev = _make_revision([("doc-1", 1, "pa-1"), ("doc-1", 2, "pa-2"), ("doc-1", 3, "pa-3")])
    # 只覆盖 1,2 缺 3
    call = _make_call("doc-1", [1, 2])
    f1 = _fact_candidate(candidate_id="f-1", locator_ids=["loc-1"])
    result = orchestrate_batch_gates(
        authority=_AUTHORITY, run_id="run-1", call_id="call-1", fact_candidates=[f1], event_candidates=[], exposure_candidates=[], revision=rev, calls=[call]
    )
    assert result.overall_outcome == GateOutcome.REJECTED
    assert any("缺失" in r for r in result.failure_reasons)
    assert "doc-1:3" in result.affected_scope
    # 逐候选页覆盖门禁应为 REJECTED
    page_verdicts = [v for v in result.gate_results if v.gate == FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE]
    assert len(page_verdicts) == 1
    assert page_verdicts[0].outcome == GateOutcome.REJECTED
    assert "doc-1:3" in page_verdicts[0].affected_scope


def test_batch_page_coverage_extra_rejected():
    rev = _make_revision([("doc-1", 1, "pa-1")])
    call = _make_call("doc-1", [1, 2])  # 多余页 2
    f1 = _fact_candidate(candidate_id="f-1", locator_ids=["loc-1"])
    result = orchestrate_batch_gates(authority=_AUTHORITY, run_id="run-1", call_id="call-1", fact_candidates=[f1], event_candidates=[], exposure_candidates=[], revision=rev, calls=[call])
    assert result.overall_outcome == GateOutcome.REJECTED
    assert any("多余" in r for r in result.failure_reasons)


def test_batch_page_coverage_duplicate_rejected():
    rev = _make_revision([("doc-1", 1, "pa-1"), ("doc-1", 2, "pa-2")])
    call1 = FactNormalizationCall(call_id="call-1", run_id="run-1", logical_document_id="doc-1", page_numbers=[1, 2], status="succeeded", input_sha256=SHA, created_at=_NOW)
    call2 = FactNormalizationCall(call_id="call-2", run_id="run-1", logical_document_id="doc-1", page_numbers=[2], status="succeeded", input_sha256=SHA, created_at=_NOW)
    f1 = _fact_candidate(candidate_id="f-1", locator_ids=["loc-1"])
    result = orchestrate_batch_gates(authority=_AUTHORITY, run_id="run-1", call_id="call-1", fact_candidates=[f1], event_candidates=[], exposure_candidates=[], revision=rev, calls=[call1, call2])
    assert result.overall_outcome == GateOutcome.REJECTED
    assert any("重复" in r for r in result.failure_reasons)


def test_batch_page_coverage_complete_accepted():
    rev = _make_revision([("doc-1", 1, "pa-1"), ("doc-1", 2, "pa-2")])
    call = _make_call("doc-1", [1, 2])
    f1 = _fact_candidate(candidate_id="f-1", locator_ids=["loc-1"])
    result = orchestrate_batch_gates(authority=_AUTHORITY, run_id="run-1", call_id="call-1", fact_candidates=[f1], event_candidates=[], exposure_candidates=[], revision=rev, calls=[call])
    assert result.overall_outcome == GateOutcome.ACCEPTED
    page_verdicts = [v for v in result.gate_results if v.gate == FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE]
    assert page_verdicts[0].outcome == GateOutcome.ACCEPTED


def test_batch_empty_with_page_coverage_still_empty_rejected():
    rev = _make_revision([("doc-1", 1, "pa-1")])
    call = _make_call("doc-1", [1])
    result = orchestrate_batch_gates(authority=_AUTHORITY, run_id="run-1", call_id="call-1", fact_candidates=[], event_candidates=[], exposure_candidates=[], revision=rev, calls=[call])
    # 空输出优先于页覆盖检查
    assert result.overall_outcome == GateOutcome.REJECTED
    assert any("为空" in r for r in result.failure_reasons)


# ---------------------------------------------------------------------------
# 持久化衔接
# ---------------------------------------------------------------------------


def test_batch_gate_results_to_fact_gate_results_deterministic():
    f1 = _fact_candidate(candidate_id="f-1", locator_ids=["loc-1"])
    f2 = _fact_candidate(candidate_id="f-2", locator_ids=["loc-2"], canonical_value="糖尿病", asserted_object="糖尿病", assertion_basis=_basis("loc-2", "糖尿病", "糖尿病"))
    # 故意让 f1/f2 同语义冲突？用同一对象不同极性
    f2_conf = _fact_candidate(candidate_id="f-2", polarity=FactPolarity.NEGATED, canonical_value="高血压", asserted_object="高血压", locator_ids=["loc-2"], assertion_basis=_basis("loc-2", "高血压", "无高血压"))
    batch = orchestrate_batch_gates(authority=_AUTHORITY, run_id="run-1", call_id="call-1", fact_candidates=[f1, f2_conf], event_candidates=[], exposure_candidates=[])
    results = batch_gate_results_to_fact_gate_results(batch, created_at=_NOW)
    # 结果按 (candidate_id, gate) 排序
    assert results == sorted(results, key=lambda r: (r.candidate_id, r.gate.value))
    assert all(r.run_id == "run-1" and r.call_id == "call-1" for r in results)
    assert all(r.created_at == _NOW for r in results)
    # gate_result_id 格式
    for r in results:
        assert r.gate_result_id.startswith("gate-")
        assert r.candidate_id in r.gate_result_id
        assert r.gate.value in r.gate_result_id


def test_batch_gate_result_validation_sorted():
    f1 = _fact_candidate(candidate_id="f-1", locator_ids=["loc-1"])
    batch = orchestrate_batch_gates(authority=_AUTHORITY, run_id="run-1", call_id="call-1", fact_candidates=[f1], event_candidates=[], exposure_candidates=[])
    # 整体校验：dedup/conflict 已排序，gate_results 已排序
    assert batch.gate_results == sorted(batch.gate_results, key=lambda v: (v.candidate_id, v.gate.value))
    # 构造未排序的 gate_results 应触发校验失败
    from app.domain.contracts.fact_gates import GateVerdict

    v1 = GateVerdict(candidate_id="f-1", gate=FactGate.CROSS_DOCUMENT_MERGE_CONFLICT, outcome=GateOutcome.ACCEPTED, reasons=[], affected_scope=[])
    v2 = GateVerdict(candidate_id="f-1", gate=FactGate.IN_DOCUMENT_DEDUP_CONFLICT, outcome=GateOutcome.ACCEPTED, reasons=[], affected_scope=[])
    # 正确排序应为 CROSS (c) 在 IN (i) 之前；此处故意放反：[IN, CROSS] 为未排序
    with pytest.raises(ValidationError):
        BatchGateResult(
            run_id="run-1",
            call_id="call-1",
            overall_outcome=GateOutcome.ACCEPTED,
            failure_reasons=[],
            dedup_groups=[],
            conflict_groups=[],
            gate_results=[v2, v1],  # 错误顺序：IN 在 CROSS 前
            affected_scope=[],
        )

# ---------------------------------------------------------------------------
# 属性/反例测试（确定性循环，无 hypothesis 依赖）
# ---------------------------------------------------------------------------


def test_property_stable_identity_deterministic_and_sorted():
    # 生成 20 个随机候选（确定性 seed），验证 compute_stable_identity_map 的幂等与排序
    rng = random.Random(42)
    facts: list[ClinicalFactCandidateV2] = []
    for i in range(20):
        val = rng.choice(["高血压", "糖尿病", "正常"])
        # 保证不同模式下合同通过：UNKNOWN 不能有值
        polarity = rng.choice([FactPolarity.AFFIRMED, FactPolarity.NEGATED, FactPolarity.UNKNOWN])
        if polarity == FactPolarity.UNKNOWN:
            facts.append(
                _fact_candidate(
                    candidate_id=f"f-{i:02d}",
                    polarity=polarity,
                    canonical_value=None,
                    raw_value=None,
                    unit=None,
                    assertion_basis=None,
                    asserted_object=val,
                    fact_type="lab",
                    locator_ids=[f"loc-{rng.randint(1,5)}"],
                )
            )
        else:
            facts.append(
                _fact_candidate(
                    candidate_id=f"f-{i:02d}",
                    polarity=polarity,
                    canonical_value=val,
                    asserted_object=val,
                    fact_type="lab",
                    locator_ids=[f"loc-{rng.randint(1,5)}"],
                    assertion_basis=_basis(f"loc-{rng.randint(1,5)}", val, val),
                )
            )
            # 修正 locator_ids 与 basis 一致（上行随机导致不匹配，强制对齐）
            facts[-1].locator_ids = [facts[-1].assertion_basis.locator_id] if facts[-1].assertion_basis else facts[-1].locator_ids

    m1 = compute_stable_identity_map(authority=_AUTHORITY, fact_candidates=facts, event_candidates=[], exposure_candidates=[])
    # 打乱顺序再次计算应得到相同映射
    shuffled = list(facts)
    rng.shuffle(shuffled)
    m2 = compute_stable_identity_map(authority=_AUTHORITY, fact_candidates=shuffled, event_candidates=[], exposure_candidates=[])
    assert m1 == m2
    # 每个身份都是 64 hex
    for sid in m1.values():
        assert len(sid) == 64 and all(c in "0123456789abcdef" for c in sid)
    # 去重分组候选集是全集子集
    groups = group_exact_duplicates(authority=_AUTHORITY, fact_candidates=facts, event_candidates=[], exposure_candidates=[])
    all_grouped = set(cid for g in groups for cid in g.candidate_ids)
    assert all_grouped.issubset({c.candidate_id for c in facts})


def test_property_no_winner_selection_in_conflict():
    # 构造 5 个同日但值不兼容的事实，验证冲突组包含全部且无赢家。
    candidates = [
        _fact_candidate(
            candidate_id=f"f-{i}", raw_value=f"值{i}", canonical_value=f"值{i}",
            locator_ids=[f"loc-{i}"],
        )
        for i in range(5)
    ]
    conflicts = detect_semantic_conflicts(authority=_AUTHORITY, fact_candidates=candidates, event_candidates=[], exposure_candidates=[])
    assert len(conflicts) == 1
    assert set(conflicts[0].candidate_ids) == {f"f-{i}" for i in range(5)}
    # 冲突成员均可发布，后续才能并列建立 ConflictGroup；无人被选为赢家
    verdicts = gate_cross_document_merge_conflict(authority=_AUTHORITY, fact_candidates=candidates, event_candidates=[], exposure_candidates=[])
    assert all(v.outcome == GateOutcome.ACCEPTED for v in verdicts.values())
    # affected_scope 均指向其他成员，不含自己
    for cid, v in verdicts.items():
        assert cid not in v.affected_scope
        assert set(v.affected_scope) == {f"f-{i}" for i in range(5) if f"f-{i}" != cid}


def test_property_dedup_and_conflict_mutually_exclusive_for_same_key():
    # 同一语义键下，若身份相同则只去重不同冲突；若身份不同则只冲突不去重
    f1 = _fact_candidate(candidate_id="f-1", locator_ids=["loc-1"])
    f2 = _fact_candidate(candidate_id="f-2", locator_ids=["loc-2"])  # 同身份 -> 去重
    f3 = _fact_candidate(
        candidate_id="f-3", raw_value="另一值", canonical_value="另一值",
        locator_ids=["loc-3"],
    )
    # f1 与 f2 同身份形成去重组；同日不同值的 f3 与两者形成冲突组。
    batch = orchestrate_batch_gates(authority=_AUTHORITY, run_id="run-1", call_id="call-1", fact_candidates=[f1, f2, f3], event_candidates=[], exposure_candidates=[])
    # 此时既有去重组也有冲突组，验证互斥性：去重组身份不应出现在冲突 distinct 之外？
    dedup_sids = {g.stable_identity for g in batch.dedup_groups}
    conflict_sids = {sid for g in batch.conflict_groups for sid in g.distinct_stable_identities}
    # 去重身份必然在冲突 distinct 中（因为 f1/f2 身份与 f3 身份冲突）
    assert dedup_sids.issubset(conflict_sids)
    # 冲突不等于丢弃成员；批次可进入并列发布
    assert batch.overall_outcome == GateOutcome.ACCEPTED


def test_counterexample_locator_not_in_identity_but_in_affected_scope():
    # 反例：两个候选仅 locator 不同，稳定身份相同，去重组合并 locator 但身份不变
    f1 = _fact_candidate(candidate_id="f-1", locator_ids=["loc-1"], model_uncertainty=0.1)
    f2 = _fact_candidate(candidate_id="f-2", locator_ids=["loc-99"], model_uncertainty=0.99)
    m = compute_stable_identity_map(authority=_AUTHORITY, fact_candidates=[f1, f2], event_candidates=[], exposure_candidates=[])
    assert m["f-1"] == m["f-2"]
    groups = group_exact_duplicates(authority=_AUTHORITY, fact_candidates=[f1, f2], event_candidates=[], exposure_candidates=[])
    assert groups[0].merged_locator_ids == ["loc-1", "loc-99"]
    # 逐候选 affected_scope 为对方 ID，不含 locator（门禁层 affected_scope 用候选 ID）
    verdicts = gate_in_document_dedup_conflict(authority=_AUTHORITY, fact_candidates=[f1, f2], event_candidates=[], exposure_candidates=[])
    assert verdicts["f-1"].affected_scope == ["f-2"]


def test_counterexample_empty_batch_vs_single_candidate():
    empty = orchestrate_batch_gates(authority=_AUTHORITY, run_id="run-1", call_id="call-1", fact_candidates=[], event_candidates=[], exposure_candidates=[])
    single = orchestrate_batch_gates(authority=_AUTHORITY, run_id="run-1", call_id="call-1", fact_candidates=[_fact_candidate(candidate_id="f-1")], event_candidates=[], exposure_candidates=[])
    assert empty.overall_outcome == GateOutcome.REJECTED
    assert single.overall_outcome == GateOutcome.ACCEPTED
    # 空批次无 gate_results，单条批次有 2 门（IN_DOCUMENT + CROSS_DOCUMENT）或含 PAGE_COVERAGE
    assert len(empty.gate_results) == 0
    assert len(single.gate_results) >= 2


def test_property_batch_affected_scope_is_union_sorted():
    # 构造含缺页、去重、冲突的混合批次，验证 batch.affected_scope 为各门 affected 并集且有序去重
    rev = _make_revision([("doc-1", 1, "pa-1"), ("doc-1", 2, "pa-2")])
    call = _make_call("doc-1", [1])  # 缺页 2
    f1 = _fact_candidate(candidate_id="f-1", locator_ids=["loc-1"])
    f2 = _fact_candidate(candidate_id="f-2", locator_ids=["loc-2"])  # 同身份去重
    f3 = _fact_candidate(
        candidate_id="f-3", raw_value="另一值", canonical_value="另一值",
        locator_ids=["loc-3"],
    )
    batch = orchestrate_batch_gates(authority=_AUTHORITY, run_id="run-1", call_id="call-1", fact_candidates=[f1, f2, f3], event_candidates=[], exposure_candidates=[], revision=rev, calls=[call])
    # affected_scope 必须有序去重
    assert batch.affected_scope == sorted(set(batch.affected_scope))
    # 缺页标识应在其中
    assert "doc-1:2" in batch.affected_scope
    # 去重/冲突成员应在其中
    for cid in ["f-1", "f-2", "f-3"]:
        assert cid in batch.affected_scope


def test_property_gate_results_cover_all_candidates_and_gates():
    facts = [_fact_candidate(candidate_id=f"f-{i}", locator_ids=[f"loc-{i}"]) for i in range(3)]
    events = [_event_candidate(candidate_id=f"e-{i}", locator_ids=[f"loc-e-{i}"], fact_candidate_ids=["f-0"]) for i in range(2)]
    exposures = [_exposure_candidate(candidate_id=f"x-{i}", locator_ids=[f"loc-x-{i}"], fact_candidate_ids=["f-0"]) for i in range(2)]
    batch = orchestrate_batch_gates(authority=_AUTHORITY, run_id="run-1", call_id="call-1", fact_candidates=facts, event_candidates=events, exposure_candidates=exposures)
    # 每个候选应有 IN_DOCUMENT 与 CROSS_DOCUMENT 两门结果
    cids = {c.candidate_id for c in facts + events + exposures}
    for cid in cids:
        gates = {v.gate for v in batch.gate_results if v.candidate_id == cid}
        assert FactGate.IN_DOCUMENT_DEDUP_CONFLICT in gates
        assert FactGate.CROSS_DOCUMENT_MERGE_CONFLICT in gates
    # 整体结果排序不变
    assert batch.gate_results == sorted(batch.gate_results, key=lambda v: (v.candidate_id, v.gate.value))


def test_property_id_consistency_after_shuffle_and_duplicate():
    # 生成含重复与冲突的随机批次，验证 shuffle 后 Dedup/Conflict 分组幂等
    rng = random.Random(123)
    base = _fact_candidate(candidate_id="f-base", date_range=_range_day(date(2020, 1, 1)))
    # 3 个与 base 同身份（去重），2 个与 base 同日但值不同（冲突）。
    dup1 = _fact_candidate(candidate_id="f-dup1", locator_ids=["loc-10"], date_range=_range_day(date(2020, 1, 1)))
    dup2 = _fact_candidate(candidate_id="f-dup2", locator_ids=["loc-11"], date_range=_range_day(date(2020, 1, 1)))
    conf1 = _fact_candidate(
        candidate_id="f-c1", raw_value="值A", canonical_value="值A",
        date_range=_range_day(date(2020, 1, 1)), locator_ids=["loc-20"],
    )
    conf2 = _fact_candidate(
        candidate_id="f-c2", raw_value="值B", canonical_value="值B",
        date_range=_range_day(date(2020, 1, 1)), locator_ids=["loc-21"],
    )
    candidates = [base, dup1, dup2, conf1, conf2]
    # 打乱三次
    for _ in range(3):
        rng.shuffle(candidates)
        batch = orchestrate_batch_gates(authority=_AUTHORITY, run_id="run-1", call_id="call-1", fact_candidates=list(candidates), event_candidates=[], exposure_candidates=[])
        # Dedup 应稳定为 1 组（base/dup1/dup2 同身份）
        assert any(len(g.candidate_ids) == 3 for g in batch.dedup_groups)
        # 冲突应稳定为 1 组覆盖 5 者中的至少 2 种身份
        assert len(batch.conflict_groups) == 1
        assert set(batch.conflict_groups[0].candidate_ids) == {c.candidate_id for c in candidates}


def test_event_conflict_key_keeps_different_diseases_separate():
    hypertension = _fact_candidate(
        candidate_id="f-htn", asserted_object="高血压", canonical_value="高血压",
        assertion_basis=_basis("loc-1", "高血压", "有高血压"), call_id="call-1",
    )
    diabetes = _fact_candidate(
        candidate_id="f-dm", asserted_object="糖尿病", canonical_value="糖尿病",
        assertion_basis=_basis("loc-2", "糖尿病", "有糖尿病"), call_id="call-2",
    )
    first = _event_candidate(candidate_id="e-htn", fact_candidate_ids=["f-htn"], call_id="call-1")
    second = _event_candidate(
        candidate_id="e-dm", fact_candidate_ids=["f-dm"], call_id="call-2",
        duration_status=DurationStatus.ENDED, end_range=_range_day(date(2026, 3, 2)),
    )
    conflicts = detect_semantic_conflicts(
        authority=_AUTHORITY, fact_candidates=[hypertension, diabetes],
        event_candidates=[first, second], exposure_candidates=[],
    )
    assert [group for group in conflicts if group.semantic_type == "event"] == []
    same_shape_second = second.model_copy(
        update={"duration_status": first.duration_status, "end_range": first.end_range}
    )
    dedup_groups = group_exact_duplicates(
        authority=_AUTHORITY, fact_candidates=[hypertension, diabetes],
        event_candidates=[first, same_shape_second], exposure_candidates=[],
    )
    assert [
        group
        for group in dedup_groups
        if {"e-htn", "e-dm"}.issubset(group.candidate_ids)
    ] == []


def test_event_identity_uses_unique_referenced_fact_objects_after_fact_dedup():
    first = _fact_candidate(candidate_id="f-htn-1")
    duplicate = _fact_candidate(
        candidate_id="f-htn-2",
        locator_ids=["loc-2"],
        assertion_basis=_basis("loc-2", "高血压", "有高血压"),
    )
    event = _event_candidate(
        candidate_id="e-htn",
        fact_candidate_ids=["f-htn-1", "f-htn-2"],
        locator_ids=["loc-1", "loc-2"],
    )

    identities = compute_stable_identity_map(
        authority=_AUTHORITY,
        fact_candidates=[first, duplicate],
        event_candidates=[event],
        exposure_candidates=[],
    )

    assert identities["e-htn"] == clinical_event_stable_identity(
        authority=_AUTHORITY,
        event_type=event.event_type,
        referenced_fact_objects=["diagnosis:高血压"],
        start_range=event.start_range,
        end_range=event.end_range,
        duration_status=event.duration_status,
    )


def test_fact_identity_keeps_same_value_different_lab_objects_separate():
    alt = _fact_candidate(
        candidate_id="f-alt", fact_type="lab", asserted_object="ALT",
        canonical_value=40, unit="U/L",
        assertion_basis=_basis("loc-1", "ALT", "ALT 40 U/L"),
    )
    ast = _fact_candidate(
        candidate_id="f-ast", fact_type="lab", asserted_object="AST",
        canonical_value=40, unit="U/L",
        assertion_basis=_basis("loc-2", "AST", "AST 40 U/L"),
    )

    groups = group_exact_duplicates(
        authority=_AUTHORITY, fact_candidates=[alt, ast],
        event_candidates=[], exposure_candidates=[],
    )

    assert groups == []


def test_run_orchestration_merges_three_modules_and_preserves_real_calls():
    call1 = _make_call("doc-1", [1])
    call2 = FactNormalizationCall(
        call_id="call-2", run_id="run-1", logical_document_id="doc-2",
        page_numbers=[1], status="succeeded", input_sha256=SHA, created_at=_NOW,
    )
    fact = _fact_candidate(candidate_id="f-1", call_id="call-1")
    event = _event_candidate(
        candidate_id="e-1", call_id="call-2", fact_candidate_ids=["f-1"]
    )
    result = orchestrate_run_gates(
        authority=_AUTHORITY, run_id="run-1", calls=[call1, call2],
        fact_candidates=[fact], event_candidates=[event], exposure_candidates=[],
        revision=_make_revision([("doc-1", 1, "pa-1"), ("doc-2", 1, "pa-2")]),
    )
    keys = [(item.candidate_id, item.gate) for item in result.gate_results]
    assert len(keys) == len(set(keys))
    assert result.overall_outcome == GateOutcome.ACCEPTED
    for candidate_id in ("f-1", "e-1"):
        candidate_gates = {
            item.gate for item in result.gate_results if item.candidate_id == candidate_id
        }
        assert FactGate.CONTRACT_AND_ENUM in candidate_gates
        assert FactGate.AUTHORITY_AND_ACTIVE_REVISION in candidate_gates
        assert FactGate.TRANSACTIONAL_PUBLISH not in candidate_gates
    persisted = run_gate_results_to_fact_gate_results(result, created_at=_NOW)
    assert {item.candidate_id: item.call_id for item in persisted} == {
        "f-1": "call-1", "e-1": "call-2"
    }


def test_run_orchestration_rejects_cross_call_event_borrowing_unreferenced_locator():
    call1 = _make_call("doc-1", [1])
    call2 = FactNormalizationCall(
        call_id="call-2", run_id="run-1", logical_document_id="doc-2",
        page_numbers=[1], status="succeeded", input_sha256=SHA, created_at=_NOW,
    )
    referenced = _fact_candidate(
        candidate_id="f-1", call_id="call-1", locator_ids=["loc-1"]
    )
    unrelated = _fact_candidate(
        candidate_id="f-2", call_id="call-2", locator_ids=["loc-2"]
    )
    event = _event_candidate(
        candidate_id="e-1", call_id="call-2", fact_candidate_ids=["f-1"],
        locator_ids=["loc-2"],
    )

    result = orchestrate_run_gates(
        authority=_AUTHORITY, run_id="run-1", calls=[call1, call2],
        fact_candidates=[referenced, unrelated], event_candidates=[event],
        exposure_candidates=[],
        revision=_make_revision([("doc-1", 1, "pa-1"), ("doc-2", 1, "pa-2")]),
    )

    verdict = next(
        item for item in result.gate_results
        if item.candidate_id == "e-1"
        and item.gate == FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE
    )
    assert verdict.outcome == GateOutcome.REJECTED
    assert verdict.affected_scope == ["loc-2"]
    assert any("不属于所引用事实" in reason for reason in verdict.reasons)


def test_run_orchestration_rejects_revision_outside_frozen_authority():
    revision = _make_revision([("doc-1", 1, "pa-1")]).model_copy(
        update={"evidence_processing_revision_id": "rev-other"}
    )

    result = orchestrate_run_gates(
        authority=_AUTHORITY,
        run_id="run-1",
        calls=[_make_call("doc-1", [1])],
        fact_candidates=[_fact_candidate()],
        event_candidates=[],
        exposure_candidates=[],
        revision=revision,
    )

    verdict = next(
        item
        for item in result.gate_results
        if item.candidate_id == "cand-fact-1"
        and item.gate == FactGate.AUTHORITY_AND_ACTIVE_REVISION
    )
    assert verdict.outcome == GateOutcome.REJECTED
    assert verdict.affected_scope == ["rev-1"]
    assert result.overall_outcome == GateOutcome.REJECTED


def test_run_orchestration_rejects_one_empty_document_call():
    call1 = _make_call("doc-1", [1])
    call2 = FactNormalizationCall(
        call_id="call-2", run_id="run-1", logical_document_id="doc-2",
        page_numbers=[1], status="succeeded", input_sha256=SHA, created_at=_NOW,
    )
    result = orchestrate_run_gates(
        authority=_AUTHORITY, run_id="run-1", calls=[call1, call2],
        fact_candidates=[_fact_candidate(call_id="call-1")],
        event_candidates=[], exposure_candidates=[],
        revision=_make_revision([("doc-1", 1, "pa-1"), ("doc-2", 1, "pa-2")]),
    )
    assert result.overall_outcome == GateOutcome.REJECTED
    assert any("call-2" in reason for reason in result.failure_reasons)


def test_run_orchestration_requires_revision_page_context():
    with pytest.raises(ValueError, match="完整处理修订"):
        orchestrate_run_gates(
            authority=_AUTHORITY, run_id="run-1", calls=[_make_call("doc-1", [1])],
            fact_candidates=[_fact_candidate()], event_candidates=[], exposure_candidates=[],
        )


def test_run_orchestration_rejects_non_successful_calls():
    failed_call = _make_call("doc-1", [1]).model_copy(update={"status": "failed"})
    with pytest.raises(ValueError, match="已成功调用"):
        orchestrate_run_gates(
            authority=_AUTHORITY, run_id="run-1", calls=[failed_call],
            fact_candidates=[_fact_candidate()], event_candidates=[], exposure_candidates=[],
            revision=_make_revision([("doc-1", 1, "pa-1")]),
        )
