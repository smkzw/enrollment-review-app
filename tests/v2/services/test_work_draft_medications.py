from datetime import UTC, date, datetime
from hashlib import sha256
from types import SimpleNamespace

import pytest

from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import AnchorType, ComponentDecision as D, DurationStatus, FactPolarity, ProfileLane, ReviewStage, SourceStrength, ProtocolPeriod
from app.domain.contracts.facts import (AssertionBasis, ClinicalFactV2, MedicationExposureV2,
    PartialDateRange, clinical_fact_stable_identity, medication_exposure_stable_identity)
from app.domain.contracts.work_draft import WorkDraftEvidenceRef, WorkDraftItem, WorkDraftSourcePage
from app.domain.publication import canonical_hash
from app.services.work_draft_medications import calculate_medications, scope_source_issues, unclassified_medication_issues
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
        conflict_groups=[], system_issues=[], review_run_id="draft", context_sha256="a" * 64,
        source_pages=[WorkDraftSourcePage(source_document_version_id="source-doc", page_artifact_id="source-page", page_number=1,
            effective_text=text, effective_text_sha256=sha256(text.encode()).hexdigest(),
            document_category="study_chart", extraction_complete=True)],
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


def test_unclassified_full_formulation_name_is_reported_without_substring_adoption():
    from app.api.v2.eligibility_review import EligibilityReviewResponse
    frame, rules, refs = medication_context()
    restriction = rules.scope_supplement.medications[0]
    restriction.drug_class_id, restriction.class_scope = "fixture", "all_members"
    rules.scope_supplement.drug_classes = {"fixture": ["药物"]}
    before = frame.medication_exposures[0].model_dump_json(), rules.model_dump_json()
    result, = calculate_medications(frame, rules, evidence_refs=refs)
    issues = unclassified_medication_issues(frame, rules, evidence_refs=refs)
    issue, = issues
    assert issue.kind == "method_unsupported" and "未能归类的用药：药物甲" in issue.detail
    assert issue.page_artifact_id == "source-page" and issue.page_number == 1
    view = project_saved_items([result], authority=frame.authority, rule_set=rules, run_id="draft", issues=issues)
    dto = EligibilityReviewResponse.model_validate(view.to_dict())
    assert dto.system_issues[0].affected_codes == ["用药01"]
    assert view.clauses[0].decision == D.INDETERMINATE.value
    assert before == (frame.medication_exposures[0].model_dump_json(), rules.model_dump_json())
    # A checked exact entry, not name similarity, removes this specific gap.
    rules.scope_supplement.drug_classes["fixture"].append("药物甲")
    assert unclassified_medication_issues(frame, rules, evidence_refs=refs) == []
    assert calculate_medications(frame, rules, evidence_refs=refs)[0].decision == D.EXCLUSION_TRIGGERED


@pytest.mark.parametrize("fault", ["no_fact", "no_refs", "wrong_page", "wrong_locator", "future", "object", "record_only"])
def test_classification_notice_does_not_invent_qualified_drugs_or_page_evidence(fault):
    frame, rules, refs = medication_context()
    restriction = rules.scope_supplement.medications[0]
    restriction.drug_class_id, restriction.class_scope = "fixture", "all_members"
    rules.scope_supplement.drug_classes = {"fixture": ["药物乙"]}
    if fault == "no_fact": frame.facts = []
    elif fault == "no_refs": refs = {}
    elif fault == "wrong_page": frame.source_pages = []
    elif fault == "wrong_locator": frame.medication_exposures[0].locator_ids = ["wrong"]
    elif fault == "future": frame.medication_exposures[0].record_time = datetime(2026, 4, 1, tzinfo=UTC)
    elif fault == "object": frame.medication_exposures[0].medication_name = "药物丙"
    else: frame.medication_exposures = []
    assert unclassified_medication_issues(frame, rules, evidence_refs=refs) == []


def test_unclassified_repeated_measurements_share_one_source_notice_without_merging_records():
    frame, rules, refs = medication_context()
    rules.scope_supplement.medications[0].drug_class_id = "fixture"
    rules.scope_supplement.drug_classes = {"fixture": ["药物乙"]}
    frame.medication_exposures.append(frame.medication_exposures[0].model_copy(update={"exposure_id": "other-reading"}))
    issue, = unclassified_medication_issues(frame, rules, evidence_refs=refs)
    assert issue.detail.count("药物甲") == 1 and len(frame.medication_exposures) == 2


def test_missing_named_anchor_does_not_misdescribe_existing_medication_history():
    frame, rules, refs = medication_context()
    rules.scope_supplement.medications[0].window.anchor_type = AnchorType.RANDOMIZATION_DATE
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision == D.INDETERMINATE and row.evidence_refs == refs["med-fact"]
    assert "已找到相关用药记录" in row.reason_text and "时间起点" in row.reason_text
    assert "没有发生" not in row.reason_text
    frame.medication_exposures = []
    frame.facts = []
    row, = calculate_medications(frame, rules, evidence_refs={})
    assert row.decision == D.INDETERMINATE and "不代表没有用药记录" in row.reason_text


def test_unresolved_protocol_source_reaches_api_without_changing_independent_medication_result():
    from app.api.v2.eligibility_review import EligibilityReviewResponse
    frame, rules, refs = medication_context()
    rules.scope_supplement.source_dispositions[0].disposition = "unresolved"
    rules.scope_supplement.source_dispositions[0].reason = "本段还需核对适用条件。"
    original = rules.model_dump_json()
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    issue, = scope_source_issues(rules)
    assert issue.kind == "component_unstructured" and issue.affected_codes == []
    assert rules.scope_supplement.sources[0].excerpt in issue.detail
    assert "病历" not in issue.alternative and issue.page_artifact_id is None
    view = project_saved_items([row], authority=frame.authority, rule_set=rules, run_id="draft", issues=[issue])
    dto = EligibilityReviewResponse.model_validate(view.to_dict())
    assert dto.system_issues == [issue]
    assert view.clauses[0].decision == D.EXCLUSION_TRIGGERED.value
    assert view.clauses[0].fact_refs[0].fact_id == "med-fact"
    assert rules.model_dump_json() == original


@pytest.mark.parametrize("disposition", ["heading", "permission", "background", "other_phase"])
def test_resolved_source_disposition_does_not_create_false_patient_requirement(disposition):
    _, rules, _ = medication_context()
    rules.scope_supplement.source_dispositions[0].disposition = disposition
    assert scope_source_issues(rules) == []
    rules.scope_supplement = None
    assert scope_source_issues(rules) == []


def test_unresolved_source_cannot_borrow_another_position_or_fabricate_a_quote():
    from app.storage.repositories import ScopeViolationError
    _, rules, _ = medication_context()
    rules.scope_supplement.source_dispositions[0].disposition = "unresolved"
    rules.scope_supplement.source_dispositions[0].source_span_id = "not-in-frozen-sources"
    with pytest.raises(ScopeViolationError, match="无法对应已保存原文"):
        scope_source_issues(rules)


def test_navigation_tracks_the_requirement_not_the_saved_run_or_display_number():
    from app.api.v2.eligibility_review import EligibilityReviewResponse
    frame, rules, refs = medication_context()
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    first = project_saved_items([row], authority=frame.authority, rule_set=rules, run_id="old")
    later = row.model_copy(update={"item_id": "another-saved-item", "review_run_id": "new"})
    second = project_saved_items([later], authority=frame.authority, rule_set=rules, run_id="new")
    assert first.clauses[0].rule_component_id != second.clauses[0].rule_component_id
    assert first.clauses[0].navigation_key == second.clauses[0].navigation_key
    assert EligibilityReviewResponse.model_validate(second.to_dict()).clauses[0].navigation_key == first.clauses[0].navigation_key
    changed_rules = rules.model_copy(deep=True)
    changed_rules.scope_supplement.medications[0].drug_text = "另一条要求"
    changed = project_saved_items([later], authority=frame.authority, rule_set=changed_rules, run_id="new")
    assert changed.clauses[0].navigation_key != second.clauses[0].navigation_key
    for field in ("project_id", "subject_id", "review_episode_id"):
        other = frame.authority.model_copy(update={field: "another-scope"})
        view = project_saved_items([later], authority=other, rule_set=rules, run_id="new")
        assert view.clauses[0].navigation_key != second.clauses[0].navigation_key


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


@pytest.mark.parametrize("period,expected", [(None, D.INDETERMINATE),
    (ProtocolPeriod.STUDY_PERIOD, D.INDETERMINATE), (ProtocolPeriod.TREATMENT_PERIOD, D.EXCLUSION_TRIGGERED)])
def test_later_treatment_exception_does_not_waive_eligibility_window(period, expected):
    frame, rules, refs = medication_context()
    item = rules.scope_supplement.medications[0]
    item.exception_excerpt = "研究药物治疗期间可以补救治疗"
    item.exception_period = period
    assert calculate_medications(frame, rules, evidence_refs=refs)[0].decision == expected
    assert item.exception_excerpt == "研究药物治疗期间可以补救治疗"


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


@pytest.mark.parametrize("day,expected", [(date(2026, 3, 4), D.EXCLUSION_TRIGGERED),
    (date(2026, 1, 1), D.INDETERMINATE)])
def test_minimum_calendar_and_half_life_reaches_consumer_without_invented_pk(day, expected):
    frame, rules, refs = medication_context(use_day=day)
    medication = rules.scope_supplement.medications[0]
    medication.window = type(medication.window).model_validate({**medication.window.model_dump(mode="json"), "upper_bound_days": None,
        "upper_bound": None, "lower_bound_days": 28, "half_life_multiplier": 5,
        "combined_window_selection": "longer_of_calendar_and_half_life"})
    medication.window_interpretation = "minimum_washout"
    before = frame.medication_exposures[0].model_dump_json()
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision == expected
    assert row.confidence == ("low" if expected == D.EXCLUSION_TRIGGERED else None)
    assert row.evidence_refs == refs["med-fact"]
    assert frame.medication_exposures[0].model_dump_json() == before


def test_no_supplement_leaves_existing_official_consumer_unchanged():
    frame, rules, refs = medication_context()
    rules.scope_supplement = None
    assert calculate_medications(frame, rules, evidence_refs=refs) == []


def test_published_record_without_exposure_is_navigable_but_not_used_for_time_calculation():
    frame, rules, refs = medication_context()
    frame.medication_exposures = []
    before = frame.facts[0].model_dump_json()
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision == D.INDETERMINATE and row.confidence is None
    assert row.evidence_refs == refs["med-fact"]
    assert "发现可能相关的药物记录" in row.reason_text and "不代表药物类别、实际使用或停药日期已经核实" in row.reason_text
    saved = WorkDraftItem.model_validate_json(row.model_dump_json())
    view = project_saved_items([saved], authority=frame.authority, rule_set=rules, run_id="draft")
    item, = view.clauses
    assert item.fact_refs[0].page_number == 1 and not item.can_confirm
    assert frame.medication_exposures == [] and frame.facts[0].model_dump_json() == before


@pytest.mark.parametrize("fault", ["other_name", "other_lane", "denied", "missing_basis",
    "other_locator", "other_excerpt", "other_fact_ref", "wrong_page", "future_record", "future_date", "missing_cutoff"])
def test_record_navigation_does_not_borrow_nearby_or_unqualified_evidence(fault):
    frame, rules, refs = medication_context()
    frame.medication_exposures = []
    fact = frame.facts[0]
    if fault == "other_name": fact = fact.model_copy(update={"asserted_object": "药物乙"})
    elif fault == "other_lane": fact = fact.model_copy(update={"profile_lane": ProfileLane.MEDICAL_HISTORY})
    elif fault == "denied": fact = fact.model_copy(update={"polarity": FactPolarity.NEGATED})
    elif fault == "missing_basis": fact = fact.model_copy(update={"assertion_basis": None})
    elif fault == "other_locator": refs["med-fact"][0] = refs["med-fact"][0].model_copy(update={"locator_id": "other"})
    elif fault == "other_excerpt": refs["med-fact"][0] = refs["med-fact"][0].model_copy(update={"excerpt": "同页另一个药物的记录"})
    elif fault == "other_fact_ref": refs["med-fact"][0] = refs["med-fact"][0].model_copy(update={"fact_id": "other"})
    elif fault == "wrong_page": frame.source_pages = []
    elif fault == "future_record": fact = fact.model_copy(update={"record_time": datetime(2026, 4, 1, tzinfo=UTC)})
    elif fault == "future_date": fact = fact.model_copy(update={"date_range": PartialDateRange(
        precision="day", lower_bound=date(2026, 4, 1), upper_bound=date(2026, 4, 1))})
    else:
        frame.review_episode.anchor_dates = {}
        frame.review_episode.evidence_cutoff_date = None
    frame.facts = [fact]
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision == D.INDETERMINATE and row.confidence is None
    assert row.evidence_refs == [] and "发现可能相关的药物记录" not in row.reason_text


def test_name_mention_only_opens_related_record_and_cannot_classify_or_compute_use():
    frame, rules, refs = medication_context()
    frame.medication_exposures = []
    text = "药物甲乙片的处方记录"
    frame.facts = [frame.facts[0].model_copy(update={"asserted_object": "药物甲乙片",
        "assertion_basis": AssertionBasis(asserted_object="药物甲乙片", assertion_text=text,
            locator_id="med-location", source_text_sha256=sha256(text.encode()).hexdigest())})]
    refs["med-fact"] = [refs["med-fact"][0].model_copy(update={"excerpt": text})]
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision == D.INDETERMINATE and row.confidence is None
    assert row.evidence_refs == refs["med-fact"] and "可能相关" in row.reason_text
    assert frame.medication_exposures == []


def test_record_navigation_preserves_unknown_dates_and_never_infers_continuation():
    frame, rules, refs = medication_context()
    frame.medication_exposures = []
    frame.facts = [frame.facts[0].model_copy(update={"date_range": None, "record_time": None})]
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision == D.INDETERMINATE and row.evidence_refs == refs["med-fact"]
    assert frame.facts[0].date_range is None and frame.medication_exposures == []


def test_related_record_does_not_certify_class_qualifiers_or_a_different_drug():
    frame, rules, refs = medication_context()
    frame.medication_exposures = []
    restriction = rules.scope_supplement.medications[0]
    restriction.drug_class_id, restriction.class_scope = "fixture_class", "qualified"
    rules.scope_supplement.drug_classes = {"fixture_class": ["药物甲"]}
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision == D.INDETERMINATE and row.evidence_refs == refs["med-fact"]
    rules.scope_supplement.drug_classes = {"fixture_class": ["药物乙"]}
    assert calculate_medications(frame, rules, evidence_refs=refs)[0].evidence_refs == []


def test_record_only_does_not_add_unrelated_sources_to_a_qualified_positive():
    frame, rules, refs = medication_context()
    extra = refs["med-fact"][0].model_copy(update={"locator_id": "other-location"})
    another = frame.facts[0].model_copy(update={"fact_id": "another", "locator_ids": ["other-location"],
        "assertion_basis": frame.facts[0].assertion_basis.model_copy(update={"locator_id": "other-location"})})
    frame.facts.append(another)
    refs["another"] = [extra.model_copy(update={"fact_id": "another"})]
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision == D.EXCLUSION_TRIGGERED and row.evidence_refs == refs["med-fact"]


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


def classified_context(*, use_day=date(2026, 2, 1)):
    frame, rules, refs = medication_context(use_day=use_day)
    rules.scope_supplement.drug_classes = {"fixture_class": ["药物甲"]}
    item = rules.scope_supplement.medications[0]
    item.drug_class_id, item.class_scope = "fixture_class", "all_members"
    return frame, rules, refs


@pytest.mark.parametrize("status", [DurationStatus.SINGLE, DurationStatus.ENDED])
def test_complete_classified_history_outside_window_has_a_saved_navigable_negative(status):
    from app.api.v2.eligibility_review import EligibilityReviewResponse
    frame, rules, refs = classified_context()
    exposure = frame.medication_exposures[0]
    frame.medication_exposures = [exposure.model_copy(update={"duration_status": status,
        "end_range": exposure.start_range if status == DurationStatus.ENDED else None})]
    before = frame.facts[0].model_dump_json(), frame.medication_exposures[0].model_dump_json()
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision == D.EXCLUSION_NOT_TRIGGERED and row.confidence == "low"
    assert "本次资料范围" in row.reason_text and row.evidence_refs == refs["med-fact"]
    saved = WorkDraftItem.model_validate_json(row.model_dump_json())
    projected = project_saved_items([saved], authority=frame.authority, rule_set=rules, run_id="draft")
    assert projected.clauses[0].rule_kind == "medication" and not projected.clauses[0].can_confirm
    assert projected.clauses[0].fact_refs[0].page_number == 1
    assert EligibilityReviewResponse.model_validate(projected.to_dict()).clauses[0].decision == "exclusion_not_triggered"
    assert before == (frame.facts[0].model_dump_json(), frame.medication_exposures[0].model_dump_json())


@pytest.mark.parametrize("fault", ["unread", "new_target_unread", "unverified", "unknown_class", "other_unclassified_fact",
    "unlinked_fact", "unknown_polarity", "missing_history_source", "missing_refs", "wrong_ref",
    "wrong_page", "future_record", "future_fact", "no_exposure", "wrong_drug", "wrong_locator",
    "unknown_course", "intermittent", "ongoing", "missing_last_use", "conflict", "scope", "no_anchor", "missing_class"])
def test_negative_never_uses_an_accepted_subset_as_the_whole_medication_history(fault):
    from app.domain.contracts.work_draft import SystemIssue
    frame, rules, refs = classified_context()
    fact, exposure = frame.facts[0], frame.medication_exposures[0]
    if fault == "unread": frame.source_pages[0].extraction_complete = False
    elif fault == "new_target_unread": frame.source_pages[0].unread_variable_ids = ["new_value"]
    elif fault == "unverified": frame.system_issues = [SystemIssue(kind="excerpt_unverified",
        affected_codes=[], detail="同页尚有未通过核对的记录", alternative="核对原件")]
    elif fault == "unknown_class": rules.scope_supplement.drug_classes["fixture_class"] = ["药物乙"]
    elif fault == "other_unclassified_fact": frame.facts.append(fact.model_copy(update={
        "fact_id": "unclassified", "asserted_object": "药物乙"}))
    elif fault == "unlinked_fact": frame.facts.append(fact.model_copy(update={"fact_id": "unlinked"}))
    elif fault == "unknown_polarity": frame.facts[0] = fact.model_copy(update={"polarity": FactPolarity.UNKNOWN})
    elif fault == "missing_history_source": frame.source_pages[0].document_category = "objective_report"
    elif fault == "missing_refs": refs = {}
    elif fault == "wrong_ref": refs["med-fact"][0] = refs["med-fact"][0].model_copy(update={"fact_id": "another"})
    elif fault == "wrong_page": frame.source_pages[0].page_number = 2
    elif fault == "future_record": frame.medication_exposures[0] = exposure.model_copy(update={
        "record_time": datetime(2026, 4, 1, tzinfo=UTC)})
    elif fault == "future_fact": frame.facts[0] = fact.model_copy(update={
        "record_time": datetime(2026, 4, 1, tzinfo=UTC)})
    elif fault == "no_exposure": frame.medication_exposures = []
    elif fault == "wrong_drug": frame.medication_exposures[0] = exposure.model_copy(update={"medication_name": "药物乙"})
    elif fault == "wrong_locator": frame.medication_exposures[0] = exposure.model_copy(update={"locator_ids": ["another"]})
    elif fault in {"unknown_course", "intermittent", "ongoing", "missing_last_use"}:
        status = {"unknown_course": DurationStatus.UNKNOWN, "intermittent": DurationStatus.INTERMITTENT,
            "ongoing": DurationStatus.ONGOING, "missing_last_use": DurationStatus.ENDED}[fault]
        frame.medication_exposures[0] = exposure.model_copy(update={"duration_status": status})
    elif fault == "conflict": frame.conflict_groups = [SimpleNamespace(member_kind="exposure", exposure_ids=["exposure"])]
    elif fault == "scope": rules.scope_supplement.medications[0].class_scope = "qualified"
    elif fault == "missing_class": rules.scope_supplement.medications[0].drug_class_id = "missing-class"
    else: frame.review_episode.anchor_dates = {}
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision != D.EXCLUSION_NOT_TRIGGERED


@pytest.mark.parametrize("fault", ["unread", "new_target_unread", "unverified", "unclassified"])
def test_incomplete_history_does_not_hide_an_independently_proven_use_in_window(fault):
    from app.domain.contracts.work_draft import SystemIssue
    frame, rules, refs = classified_context(use_day=date(2026, 3, 4))
    if fault == "unread": frame.source_pages[0].extraction_complete = False
    elif fault == "new_target_unread": frame.source_pages[0].unread_variable_ids = ["new_value"]
    elif fault == "unverified": frame.system_issues = [SystemIssue(kind="excerpt_unverified",
        affected_codes=[], detail="其他记录未核", alternative="查看原件")]
    else: frame.facts.append(frame.facts[0].model_copy(update={"fact_id": "other", "asserted_object": "药物乙"}))
    assert calculate_medications(frame, rules, evidence_refs=refs)[0].decision == D.EXCLUSION_TRIGGERED


def test_no_use_of_this_class_requires_a_complete_differently_classified_history():
    frame, rules, refs = classified_context()
    rules.scope_supplement.drug_classes["other_class"] = ["药物乙"]
    rules.scope_supplement.medications[0].drug_class_id = "other_class"
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision == D.EXCLUSION_NOT_TRIGGERED and row.evidence_refs == refs["med-fact"]
    frame.medication_exposures = []
    assert calculate_medications(frame, rules, evidence_refs=refs)[0].decision == D.INDETERMINATE


def test_classified_history_does_not_invent_a_class_for_untyped_restriction_text():
    frame, rules, refs = classified_context()
    rules.scope_supplement.medications[0].drug_class_id = None
    row, = calculate_medications(frame, rules, evidence_refs=refs)
    assert row.decision == D.INDETERMINATE


def test_future_treatment_interval_cannot_be_declared_negative_from_earlier_history():
    frame, rules, refs = classified_context()
    item = rules.scope_supplement.medications[0]
    item.window, item.window_interpretation, item.period = None, None, ProtocolPeriod.TREATMENT_PERIOD
    frame.review_episode.anchor_dates["first_dose_date"] = DateValue(value="2026-04-01", precision="day")
    assert calculate_medications(frame, rules, evidence_refs=refs)[0].decision == D.INDETERMINATE


def test_an_additional_unlinked_course_cannot_be_hidden_behind_a_valid_one():
    frame, rules, refs = classified_context()
    frame.medication_exposures.append(frame.medication_exposures[0].model_copy(update={
        "exposure_id": "unlinked-course", "fact_ids": ["missing-fact"]}))
    assert calculate_medications(frame, rules, evidence_refs=refs)[0].decision == D.INDETERMINATE
