from datetime import UTC, date, datetime
from hashlib import sha256
from types import SimpleNamespace

import pytest

from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import ComponentDecision as D, DurationStatus, FactPolarity, ProfileLane, ReviewStage, SourceStrength, ProtocolPeriod
from app.domain.contracts.facts import (AssertionBasis, ClinicalFactV2, MedicationExposureV2,
    PartialDateRange, clinical_fact_stable_identity, medication_exposure_stable_identity)
from app.domain.contracts.work_draft import WorkDraftEvidenceRef, WorkDraftItem
from app.domain.publication import canonical_hash
from app.services.work_draft_medications import calculate_medications
from app.services.work_draft_projection import project_saved_items
from tests.v2.protocols.test_medication_restrictions import frozen_medications, build
from tests.v2.services.test_work_draft_calculation import material, clause


def medication_context(*, use_day=date(2026, 3, 4)):
    authority = material().authority
    day = PartialDateRange(precision="day", lower_bound=use_day, upper_bound=use_day)
    text = f"{use_day:%Y年%m月%d日}用药物甲一次。"
    fields = dict(authority=authority, fact_type="medication_history", profile_lane=ProfileLane.MEDICATION,
        asserted_object="药物甲", polarity=FactPolarity.AFFIRMED, value=True, unit=None, date_range=day,
        assertion_basis=AssertionBasis(asserted_object="药物甲", assertion_text=text,
            locator_id="med-location", source_text_sha256=sha256(text.encode()).hexdigest()))
    fact = ClinicalFactV2(**fields, fact_id="med-fact", run_id="normalization", gate_id="gate",
        locator_ids=["med-location"], source_strength=SourceStrength.HISTORICAL_PRIMARY, revision=1,
        stable_identity=clinical_fact_stable_identity(**fields), created_at=datetime(2026, 10, 15, tzinfo=UTC))
    fields = dict(authority=authority, medication_name="药物甲", category=None, indication=None,
        dose=None, unit=None, frequency=None, route=None, start_range=day, end_range=None,
        duration_status=DurationStatus.SINGLE)
    exposure = MedicationExposureV2(**fields, exposure_id="exposure", run_id="normalization", gate_id="gate",
        fact_ids=[fact.fact_id], locator_ids=fact.locator_ids, source_strength=SourceStrength.HISTORICAL_PRIMARY,
        record_time=datetime(2026, 3, 31, tzinfo=UTC), revision=1,
        stable_identity=medication_exposure_stable_identity(**fields), created_at=datetime(2026, 10, 15, tzinfo=UTC))
    selection, view, proposal = frozen_medications()
    view["source_records"][1]["raw_text"] = "筛选前4周内禁止使用药物甲。"
    proposal["medications"][0]["source_quotes"][0]["excerpt"] = view["source_records"][1]["raw_text"]
    proposal["medications"][0].update(window_interpretation="prohibited_interval", exception_excerpt=None)
    rules = clause()[0]
    rules.scope_supplement = build(proposal, selection, view)
    frame = SimpleNamespace(authority=authority, facts=[fact], medication_exposures=[exposure],
        conflict_groups=[], review_run_id="draft", context_sha256="a" * 64,
        source_pages=[SimpleNamespace(source_document_version_id="source-doc", page_artifact_id="source-page", page_number=1)],
        review_episode=SimpleNamespace(stage=ReviewStage.SCREENING, evidence_cutoff_date=date(2026, 3, 31),
            anchor_dates={"screening_date": DateValue(value="2026-03-31", precision="day")}))
    refs = {fact.fact_id: [WorkDraftEvidenceRef(fact_id=fact.fact_id, locator_id="med-location",
        source_document_version_id="source-doc", page_artifact_id="source-page", page_number=1, excerpt=text)]}
    return frame, rules, refs


def test_published_single_use_reaches_saved_contract_projection_and_preserves_input():
    frame, rules, refs = medication_context()
    before = canonical_hash(rules.model_dump(mode="json")), frame.medication_exposures[0].model_dump_json()
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision == D.EXCLUSION_TRIGGERED and row.confidence == "low"
    assert row.evidence_refs == refs["med-fact"]
    saved = WorkDraftItem.model_validate_json(row.model_dump_json())
    projection = project_saved_items([saved], authority=frame.authority, rule_set=rules, run_id="draft")
    item, = projection.clauses
    assert item.rule_kind == "medication" and item.rule_code == "用药01"
    assert not item.can_confirm and item.fact_refs[0].page_number == 1
    assert before == (canonical_hash(rules.model_dump(mode="json")), frame.medication_exposures[0].model_dump_json())


@pytest.mark.parametrize("fault", ["missing_fact", "other_locator", "future_record", "wrong_source_scope",
    "no_exposure", "different_name", "prescription_fact_only", "missing_anchor"])
def test_unqualified_or_missing_record_never_becomes_negative_or_fabricated_exposure(fault):
    frame, rules, refs = medication_context()
    if fault == "missing_fact": refs = {}
    elif fault == "other_locator": refs["med-fact"][0] = refs["med-fact"][0].model_copy(update={"locator_id": "other"})
    elif fault == "future_record": frame.medication_exposures[0] = frame.medication_exposures[0].model_copy(update={"record_time": datetime(2026, 4, 1, tzinfo=UTC)})
    elif fault == "wrong_source_scope": frame.source_pages = []
    elif fault == "no_exposure" or fault == "prescription_fact_only": frame.medication_exposures = []
    elif fault == "different_name": frame.medication_exposures[0] = frame.medication_exposures[0].model_copy(update={"medication_name": "药物乙"})
    else: frame.review_episode.anchor_dates = {}
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision == D.INDETERMINATE and row.confidence is None


def test_exact_frozen_class_exception_and_conflict_remain_independent():
    frame, rules, refs = medication_context()
    rules.scope_supplement.medications[0].drug_class_id = "fixture_class"
    rules.scope_supplement.drug_classes = {"fixture_class": ["药物乙"]}
    assert calculate_medications(frame, rules, evidence_refs=refs)[0].decision == D.INDETERMINATE
    rules.scope_supplement.drug_classes["fixture_class"] = ["药物甲"]
    result = calculate_medications(frame, rules, evidence_refs=refs)[0]
    assert result.decision is None and result.system_issue.kind == "method_unsupported"
    old_issue = result.system_issue.model_dump_json()
    display = project_saved_items([result], authority=frame.authority, rule_set=rules, run_id="draft", issues=[result.system_issue])
    assert display.system_issues[0].affected_codes == ["用药01"]
    assert result.system_issue.model_dump_json() == old_issue
    rules.scope_supplement.medications[0].drug_class_id = None
    rules.scope_supplement.medications[0].exception_excerpt = "补救治疗除外"
    assert calculate_medications(frame, rules, evidence_refs=refs)[0].decision == D.INDETERMINATE
    frame.conflict_groups = [SimpleNamespace(member_kind="exposure", exposure_ids=["exposure"])]
    assert calculate_medications(frame, rules, evidence_refs=refs)[0].decision == D.CONFLICT


def test_ongoing_does_not_invent_continuation_to_a_future_anchor():
    frame, rules, refs = medication_context(use_day=date(2026, 2, 1))
    frame.medication_exposures[0] = frame.medication_exposures[0].model_copy(update={"duration_status": DurationStatus.ONGOING,
        "record_time": datetime(2026, 2, 1, tzinfo=UTC)})
    assert calculate_medications(frame, rules, evidence_refs=refs)[0].decision == D.INDETERMINATE


@pytest.mark.parametrize("scope,expected", [(None, None), ("qualified", None), ("all_members", D.EXCLUSION_TRIGGERED)])
def test_class_scope_only_changes_qualified_exposure_consumption(scope, expected):
    frame, rules, refs = medication_context()
    restriction = rules.scope_supplement.medications[0]
    restriction.drug_class_id = "fixture_class"
    restriction.class_scope = scope
    rules.scope_supplement.drug_classes = {"fixture_class": ["药物甲"]}
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision == expected
    assert (row.system_issue is not None) == (scope != "all_members")
    if scope == "all_members":
        assert row.confidence == "low" and row.evidence_refs == refs["med-fact"]
        frame.medication_exposures = []
        assert calculate_medications(frame, rules, evidence_refs=refs)[0].decision == D.INDETERMINATE


@pytest.mark.parametrize("fault", ["exception", "missing_fact", "wrong_page", "after_cutoff", "conflict"])
def test_class_scope_does_not_bypass_source_date_or_exception(fault):
    frame, rules, refs = medication_context()
    restriction = rules.scope_supplement.medications[0]
    restriction.drug_class_id, restriction.class_scope = "fixture_class", "all_members"
    rules.scope_supplement.drug_classes = {"fixture_class": ["药物甲"]}
    if fault == "exception": restriction.exception_excerpt = "另有例外"
    elif fault == "missing_fact": refs = {}
    elif fault == "wrong_page": frame.source_pages = []
    elif fault == "after_cutoff": frame.medication_exposures[0] = frame.medication_exposures[0].model_copy(update={"record_time": datetime(2026, 4, 1, tzinfo=UTC)})
    else: frame.conflict_groups = [SimpleNamespace(member_kind="exposure", exposure_ids=["exposure"])]
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision == (D.CONFLICT if fault == "conflict" else D.INDETERMINATE)


@pytest.mark.parametrize("status", [DurationStatus.UNKNOWN, DurationStatus.INTERMITTENT, DurationStatus.ONGOING])
def test_dated_start_inside_prohibited_window_is_a_low_confidence_positive_not_invented_cessation(status):
    frame, rules, refs = medication_context()
    frame.medication_exposures[0] = frame.medication_exposures[0].model_copy(update={"duration_status": status,
        "record_time": datetime(2026, 3, 4, tzinfo=UTC)})
    before = frame.medication_exposures[0].model_dump_json()
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision == D.EXCLUSION_TRIGGERED and row.confidence == "low"
    assert row.evidence_refs == refs["med-fact"]
    assert "停药日期" in row.reason_text
    assert frame.medication_exposures[0].model_dump_json() == before


@pytest.mark.parametrize("status", [DurationStatus.UNKNOWN, DurationStatus.INTERMITTENT, DurationStatus.ONGOING])
def test_start_outside_window_never_proves_a_sufficient_washout_or_no_recent_use(status):
    frame, rules, refs = medication_context(use_day=date(2026, 2, 1))
    frame.medication_exposures[0] = frame.medication_exposures[0].model_copy(update={"duration_status": status,
        "record_time": datetime(2026, 2, 1, tzinfo=UTC)})
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision == D.INDETERMINATE and row.confidence is None


@pytest.mark.parametrize("use_day,expected", [(date(2026, 3, 4), D.EXCLUSION_TRIGGERED),
    (date(2026, 2, 1), D.INDETERMINATE), (date(2026, 4, 1), D.INDETERMINATE)])
def test_unknown_course_start_respects_minimum_gap_and_does_not_read_after_cutoff(use_day, expected):
    frame, rules, refs = medication_context(use_day=use_day)
    medication = rules.scope_supplement.medications[0]
    medication.window = medication.window.model_copy(update={"lower_bound": medication.window.upper_bound, "upper_bound": None})
    medication.window_interpretation = "minimum_washout"
    frame.medication_exposures[0] = frame.medication_exposures[0].model_copy(update={"duration_status": DurationStatus.UNKNOWN})
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision == expected
    assert row.confidence == ("low" if expected == D.EXCLUSION_TRIGGERED else None)


def test_known_single_use_date_does_not_require_a_second_record_date():
    frame, rules, refs = medication_context()
    frame.medication_exposures[0] = frame.medication_exposures[0].model_copy(update={"record_time": None})
    assert calculate_medications(frame, rules, evidence_refs=refs)[0].decision == D.EXCLUSION_TRIGGERED


def test_no_supplement_leaves_existing_official_consumer_unchanged():
    frame, rules, refs = medication_context()
    rules.scope_supplement = None
    assert calculate_medications(frame, rules, evidence_refs=refs) == []


def test_current_stage_use_can_support_study_period_but_not_an_unstarted_treatment_period():
    frame, rules, refs = medication_context()
    medication = rules.scope_supplement.medications[0]
    medication.window, medication.window_interpretation, medication.period = None, None, ProtocolPeriod.STUDY_PERIOD
    frame.review_episode.anchor_dates["screening_date"] = DateValue(value="2026-03-01", precision="day")
    assert calculate_medications(frame, rules, evidence_refs=refs)[0].decision == D.EXCLUSION_TRIGGERED
    medication.period = ProtocolPeriod.TREATMENT_PERIOD
    assert calculate_medications(frame, rules, evidence_refs=refs)[0].decision == D.INDETERMINATE
    frame.review_episode.anchor_dates["first_dose_date"] = DateValue(value="2026-03-02", precision="day")
    assert calculate_medications(frame, rules, evidence_refs=refs)[0].decision == D.EXCLUSION_TRIGGERED
