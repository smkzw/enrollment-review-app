"""Synthetic functional family; no clinical documents or model calls."""
from datetime import UTC, date, datetime
from hashlib import sha256
from types import SimpleNamespace

import pytest

from app.domain.contracts.enums import (AnchorType, Comparator, ComponentDecision as D,
    DatePrecision, FactPolarity, ProfileLane, ReviewStage, RuleKind, SourceStrength, StudyPhase,
    TimeDirection)
from app.domain.contracts.common import DateValue
from app.domain.contracts.facts import AssertionBasis, ClinicalFactV2, FactAuthority, PartialDateRange, clinical_fact_stable_identity
from app.domain.contracts.rules import AtomicExpression, AtomicPredicate, EvidenceRequirement, Rule, RuleComponent, RuleSet, TimeConstraint
from app.domain.contracts.work_draft import SystemIssue, WorkDraftItem
from app.domain.variables.dictionary import load_dictionary
from app.graph.subject_graph import SUBJECT_GRAPH, work_draft_steps
from app.projections.clause_pack import project_clause_pack
from app.services.work_draft_calculation import calculate_work_component, compose_parent, select_by_variable
from app.domain.contracts.work_draft import WorkDraftEvidenceRef

NOW = datetime(2026, 10, 12, tzinfo=UTC)


def material(*, value=52, variable_id="age", unit="岁", day=None, snapshot="snapshot", polarity=FactPolarity.AFFIRMED):
    authority = FactAuthority(project_id="project", subject_id="subject", review_episode_id="episode",
        episode_revision=1, protocol_version_id="protocol", rule_set_id="rules", rule_set_revision=1,
        evidence_snapshot_v2_id=snapshot, complete_processing_revision_id="complete")
    text = f"{load_dictionary()[variable_id].label_zh} {value} {unit}"
    basis = AssertionBasis(asserted_object=load_dictionary()[variable_id].label_zh, assertion_text=text,
        locator_id=f"locator-{snapshot}", source_text_sha256=sha256(text.encode()).hexdigest())
    values = dict(authority=authority, fact_type="不同显示名称", profile_lane=ProfileLane.TEST_EXAM_SCORE,
        asserted_object=basis.asserted_object, polarity=polarity, value=value, unit=unit,
        variable_id=variable_id, date_role="sampling" if day else "unknown",
        date_range=PartialDateRange(precision=DatePrecision.DAY, lower_bound=day, upper_bound=day) if day else None)
    return ClinicalFactV2(**values, fact_id=f"fact-{snapshot}", run_id="normalizer", gate_id="gate", locator_ids=[basis.locator_id],
        assertion_basis=basis, stable_identity=clinical_fact_stable_identity(**values), revision=1,
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE, created_at=NOW)


def clause(*, time=None, kind=RuleKind.INCLUSION):
    predicate = AtomicPredicate(predicate_id="age-limit", subject="受试者", attribute="年龄", comparator=Comparator.GTE,
        value=18, unit="岁")
    requirement = EvidenceRequirement(requirement_id="age-record", rule_component_id="age-component",
        fact_type="另一个显示名称", variable_id="age", predicate_ids=[predicate.predicate_id],
        required_source_types=["study_chart"], allows_screening_record_transcription=True,
        requires_contemporaneous_objective_source=False,
        due_stage=ReviewStage.SCREENING, description="年龄记录")
    component = RuleComponent(rule_component_id="age-component", parent_rule_id="age-rule", display_code="IN-01-a",
        title="成年", expression=AtomicExpression(predicate=predicate, time_constraint=time), evidence_requirements=[requirement])
    rule = Rule(rule_id="age-rule", official_code="IN-01" if kind == RuleKind.INCLUSION else "EX-01",
        kind=kind, source_text="年龄至少18岁", study_phase=StudyPhase.PHASE_III, components=[component])
    rules = RuleSet(rule_set_id="rules", protocol_version_id="protocol", revision=1, study_phase=StudyPhase.PHASE_III,
        rules=[rule], variable_definitions=[load_dictionary()["age"]])
    return rules, project_clause_pack(rules).clauses[0], component


def frozen(facts, anchors=None):
    return SimpleNamespace(authority=facts[0].authority, facts=facts, review_run_id="working-run",
        review_episode=SimpleNamespace(stage=ReviewStage.SCREENING, anchor_dates=anchors or {},
            model_dump=lambda **_: {"anchor_dates": {key.value: val.model_dump(mode="json") for key, val in (anchors or {}).items()}}))


def test_variable_identity_not_display_type_selects_and_computes():
    rules, projected, component = clause()
    fact = material()
    selections = select_by_variable(component, [fact], {}, authority=fact.authority, definitions=load_dictionary())
    assert selections["age-limit"].fact_ids == (fact.fact_id,)
    result = calculate_work_component(projected, frozen([fact]), rules, evidence_refs={})
    assert result.decision == D.INCLUSION_MET and result.confidence == "high"


def test_original_source_requirement_is_consumed_through_exact_wp2_binding_ancestry():
    from hashlib import sha256
    rules, _, component = clause()
    bound = component.evidence_requirements[0]
    original = bound.model_copy(update={"requirement_id": "original-source", "variable_id": None, "predicate_ids": []})
    derived_id = "variable_requirement:" + sha256(":".join((component.rule_component_id,
        "age-limit", original.requirement_id)).encode()).hexdigest()[:32]
    bound.requirement_id = derived_id
    component.evidence_requirements.insert(0, original)
    projected = project_clause_pack(rules).clauses[0]
    fact = material()
    assert calculate_work_component(projected, frozen([fact]), rules, evidence_refs={}).decision == D.INCLUSION_MET
    # Merely sharing a label/type is not ancestry and cannot close another requirement.
    original.requirement_id = "unrelated-source"
    projected = project_clause_pack(rules).clauses[0]
    assert calculate_work_component(projected, frozen([fact]), rules, evidence_refs={}).decision == D.INDETERMINATE


def test_unbound_same_display_type_never_matches():
    _, _, component = clause()
    fact = material(variable_id="alt", unit="U/L")
    assert not select_by_variable(component, [fact], {}, authority=fact.authority,
                                  definitions=load_dictionary())["age-limit"].fact_ids


@pytest.mark.parametrize("age,expected", [(17, D.EXCLUSION_NOT_TRIGGERED), (52, D.INDETERMINATE)])
def test_exception_only_evidence_is_needed_only_when_trigger_is_true(age, expected):
    rules, _, component = clause(kind=RuleKind.EXCLUSION)
    condition = AtomicPredicate(predicate_id="exception", subject="受试者", attribute="ANC",
        comparator=Comparator.GT, value=1.2, unit="10^9/L")
    component.exception_expression = AtomicExpression(predicate=condition)
    component.evidence_requirements.append(component.evidence_requirements[0].model_copy(update={
        "requirement_id": "exception-record", "variable_id": "anc", "predicate_ids": [condition.predicate_id]}))
    rules.variable_definitions.append(load_dictionary()["anc"])
    fact = material(value=age)
    result = calculate_work_component(project_clause_pack(rules).clauses[0], frozen([fact]), rules, evidence_refs={})
    assert result.decision == expected
    assert len(component.evidence_requirements) == 2


def test_existing_out_of_window_record_is_not_described_as_no_record():
    rules, projected, _ = clause()
    fact = material(day=date(2026, 10, 13))
    frame = frozen([fact], {AnchorType.SCREENING_DATE: DateValue(value=date(2026, 10, 12), precision=DatePrecision.DAY)})
    result = calculate_work_component(projected, frame, rules, evidence_refs={})
    assert result.decision == D.INDETERMINATE
    assert "已找到相关记录" in result.reason_text
    assert "适用时间尚未核实" in result.reason_text


def test_single_low_confidence_child_does_not_claim_unknown_siblings():
    rule = clause()[0].rules[0]
    item = WorkDraftItem(item_id="child", review_run_id="run", official_code="IN-01",
        rule_kind=RuleKind.INCLUSION, title="年龄", source_text="年龄至少18岁", reason_text="已有依据",
        input_hash="f" * 64, decision=D.INCLUSION_MET, confidence="low", confidence_reason="日期待核实")
    result = compose_parent(rule, [item], "run")
    assert result.confidence_reason == "日期待核实"


@pytest.mark.parametrize("reading, expected", [("阳性", D.EXCLUSION_TRIGGERED),
    (">4.00阳性(＋)", D.EXCLUSION_TRIGGERED), ("0.04阴性(-)", D.EXCLUSION_NOT_TRIGGERED),
    ("＜0.05 阴性（－）", D.EXCLUSION_NOT_TRIGGERED)])
def test_qualitative_lab_comparison_keeps_original_reading_and_unit(reading, expected):
    rules, _, component = clause(kind=RuleKind.EXCLUSION)
    predicate = component.expression.predicate
    predicate.comparator, predicate.value, predicate.unit = Comparator.EQ, "阳性", "unitless"
    component.evidence_requirements[0].variable_id = "hiv_antibody"
    rules.variable_definitions = [load_dictionary()["hiv_antibody"]]
    fact = material(value=reading, variable_id="hiv_antibody", unit="S/CO")
    before = fact.model_dump_json()
    result = calculate_work_component(project_clause_pack(rules).clauses[0], frozen([fact]), rules, evidence_refs={})
    assert result.decision == expected
    assert fact.model_dump_json() == before and reading in result.reason_text


@pytest.mark.parametrize("reading", ["0.04", "超出正常值范围", "阴性(+)", "阳性但待复核", "未见阳性", "弱阳性"])
def test_unresolved_lab_label_is_not_a_negative_result(reading):
    rules, _, component = clause(kind=RuleKind.EXCLUSION)
    predicate = component.expression.predicate
    predicate.comparator, predicate.value, predicate.unit = Comparator.EQ, "阳性", "unitless"
    component.evidence_requirements[0].variable_id = "hiv_antibody"
    rules.variable_definitions = [load_dictionary()["hiv_antibody"]]
    result = calculate_work_component(project_clause_pack(rules).clauses[0],
        frozen([material(value=reading, variable_id="hiv_antibody", unit=None)]), rules, evidence_refs={})
    assert result.decision is None and result.system_issue is not None


def test_prescription_string_does_not_prove_current_medication_use():
    from app.domain.variables.dictionary import VariableDef
    rules, _, component = clause(kind=RuleKind.EXCLUSION)
    predicate = component.expression.predicate
    predicate.comparator, predicate.value, predicate.unit = Comparator.EXISTS, None, None
    component.evidence_requirements[0].variable_id = "medication_record"
    rules.variable_definitions = [VariableDef(variable_id="medication_record", label_zh="用药记录",
        value_type="exposure", domain="medication")]
    original = material()
    values = dict(authority=original.authority, fact_type="处方", profile_lane=original.profile_lane,
        asserted_object="用药记录", polarity=FactPolarity.AFFIRMED, value="三个月前开具药物甲", unit=None,
        variable_id="medication_record", date_role="unknown", date_range=None)
    fact = original.model_copy(update={**values, "assertion_basis": None,
        "stable_identity": clinical_fact_stable_identity(**values)})
    result = calculate_work_component(project_clause_pack(rules).clauses[0], frozen([fact]), rules, evidence_refs={})
    assert result.decision is None and result.system_issue is not None
    assert "用药记录" in result.reason_text


def test_published_other_rule_revision_still_matches_without_rewriting_fact():
    rules, projected, _ = clause()
    fact = material()
    before = fact.model_dump_json()
    frame = frozen([fact])
    frame.authority = fact.authority.model_copy(update={"rule_set_revision": 2})
    rules = rules.model_copy(update={"revision": 2})
    assert calculate_work_component(projected, frame, rules, evidence_refs={}).decision == D.INCLUSION_MET
    assert fact.model_dump_json() == before


def test_time_window_does_not_use_future_or_unknown_date():
    time = TimeConstraint(anchor_type=AnchorType.SCREENING_DATE, direction=TimeDirection.BEFORE,
                          upper_bound_days=30)
    _, _, component = clause(time=time)
    a = material(day=date(2025, 8, 1), snapshot="first")
    b = material(day=date(2025, 8, 15), snapshot="future")
    c = material(snapshot="undated")
    anchors = {AnchorType.SCREENING_DATE: DateValue(value=date(2025, 8, 8), precision=DatePrecision.DAY)}
    selected = select_by_variable(component, [a, b, c], anchors, authority=a.authority, definitions=load_dictionary())
    assert selected["age-limit"].fact_ids == (a.fact_id,)


def test_nearest_date_and_same_day_conflict():
    _, _, component = clause()
    a = material(value=52, day=date(2025, 8, 1), snapshot="first")
    b = material(value=53, day=date(2025, 8, 8), snapshot="second")
    selected = select_by_variable(component, [a, b], {}, authority=a.authority, definitions=load_dictionary())
    assert selected["age-limit"].fact_ids == (b.fact_id,) and not selected["age-limit"].conflict
    c = material(value=54, day=date(2025, 8, 8), snapshot="third")
    assert select_by_variable(component, [b, c], {}, authority=b.authority, definitions=load_dictionary())["age-limit"].conflict


def test_shared_locator_does_not_merge_distinct_dated_collections():
    _, _, component = clause()
    a = material(value=52, day=date(2025, 8, 1), snapshot="first")
    b = material(value=53, day=date(2025, 8, 8), snapshot="second")
    b = b.model_copy(update={"locator_ids": a.locator_ids})
    result = select_by_variable(component, [a, b], {}, authority=a.authority, definitions=load_dictionary())["age-limit"]
    assert not result.conflict and result.fact_ids == (b.fact_id,)


def test_calculation_cannot_downgrade_wrong_patient_to_a_system_issue():
    from app.storage.repositories import ScopeViolationError
    rules, projected, _ = clause()
    fact = material()
    frame = frozen([fact])
    frame.facts = [fact.model_copy(update={"authority": fact.authority.model_copy(update={"subject_id": "other"})})]
    with pytest.raises(ScopeViolationError):
        calculate_work_component(projected, frame, rules, evidence_refs={})


def test_present_but_unknown_anchor_cannot_grant_high_confidence():
    rules, _, component = clause()
    predicate = component.expression.predicate
    predicate.unit = "U/L"
    component.evidence_requirements[0].variable_id = "alt"
    rules.variable_definitions = [load_dictionary()["alt"]]
    anchors = {AnchorType.SCREENING_DATE: DateValue(precision=DatePrecision.UNKNOWN)}
    result = calculate_work_component(project_clause_pack(rules).clauses[0],
        frozen([material(variable_id="alt", unit="U/L", day=date(2025, 8, 8))], anchors), rules, evidence_refs={})
    assert result.decision == D.INCLUSION_MET and result.confidence == "low"


def test_recovery_identity_requires_the_same_reading_not_merely_the_same_page():
    from app.services.review_context_assembly import _source_reading_identity
    fact = material()
    candidate = SimpleNamespace(**{name: getattr(fact, name) for name in (
        "assertion_basis", "variable_id", "asserted_object", "unit", "polarity", "date_role", "date_range")},
        canonical_value=fact.value)
    assert _source_reading_identity(candidate) == _source_reading_identity(fact)
    candidate.canonical_value = 53
    assert _source_reading_identity(candidate) != _source_reading_identity(fact)
    candidate.canonical_value = fact.value
    candidate.assertion_basis = fact.assertion_basis.model_copy(update={"locator_id": "another-field-on-the-same-page"})
    assert _source_reading_identity(candidate) != _source_reading_identity(fact)


def test_bad_primary_quote_is_omitted_without_losing_other_fact_refs(monkeypatch):
    from app.services import work_draft_review as service
    import app.domain.gates.fact_evidence_closure as closure
    from app.storage.fact_authority import FactAuthorityValidator
    a, b = material(snapshot="good"), material(snapshot="bad")
    texts = {a.locator_ids[0]: a.assertion_basis.assertion_text, b.locator_ids[0]: "另一条原文"}
    monkeypatch.setattr(FactAuthorityValidator, "validate_frozen_source", lambda *_: object())
    monkeypatch.setattr(closure, "_localized_locator_text", lambda _session, loc, _revision: texts[loc.locator_id])
    monkeypatch.setattr(service.EvidenceLocatorRepository, "get", lambda _self, key: SimpleNamespace(
        locator_id=key, source_document_version_id="document", page_artifact_id="page", page_number=1))
    refs = service._fact_refs(object(), frozen([a, b]))
    assert set(refs) == {a.fact_id}
    assert refs[a.fact_id][0].excerpt == a.assertion_basis.assertion_text


def test_unimplemented_written_judgment_search_is_not_reported_as_missing_record():
    rules, _, component = clause()
    component.expression.predicate.requires_professional_judgment = True
    result = calculate_work_component(project_clause_pack(rules).clauses[0],
        frozen([material()]), rules, evidence_refs={})
    assert result.system_issue is not None and result.decision is None
    assert "尚未接入" in result.reason_text


def test_wrong_subject_is_hard_rejection():
    _, _, component = clause()
    a = material()
    b = material(snapshot="bad").model_copy(update={"authority": a.authority.model_copy(update={"subject_id": "other"})})
    with pytest.raises(ValueError, match="受试者"):
        select_by_variable(component, [b], {}, authority=a.authority, definitions=load_dictionary())


@pytest.mark.parametrize("kind, decisive", [(RuleKind.INCLUSION, D.INCLUSION_NOT_MET), (RuleKind.EXCLUSION, D.EXCLUSION_TRIGGERED)])
def test_decisive_parent_keeps_unknown_sibling_low(kind, decisive):
    rule = clause(kind=kind)[0].rules[0]
    issue = SystemIssue(kind="method_unsupported", affected_codes=[rule.official_code], detail="计算未接入", alternative="核查原件")
    common = dict(review_run_id="run", official_code=rule.official_code, rule_kind=kind,
        title="子项", source_text="原文", reason_text="原因", input_hash="f" * 64)
    children = [WorkDraftItem(**common, item_id="good", decision=decisive, confidence="high"),
                WorkDraftItem(**common, item_id="unavailable", system_issue=issue)]
    result = compose_parent(rule, children, "run")
    assert result.decision == decisive and result.confidence == "low" and result.system_issue is None


def test_graph_reuses_existing_owners_and_declares_placeholder():
    assert set(SUBJECT_GRAPH) == {f"S{index}" for index in range(1, 9)}
    assert list(work_draft_steps()) == [("calculate", ()), ("semantic", ("calculate",)),
                                       ("compose", ("semantic",)), ("save", ("compose",))]


def test_pdf_bundle_does_not_prove_same_report_or_a_patient_conflict():
    _, _, component = clause()
    a = material(value=52, snapshot="first")
    b = material(value=53, snapshot="second")
    def ref(fact, document):
        return WorkDraftEvidenceRef(fact_id=fact.fact_id, locator_id=fact.locator_ids[0],
            source_document_version_id=document, page_artifact_id="page", page_number=1,
            excerpt=fact.assertion_basis.assertion_text)
    refs = {a.fact_id: [ref(a, "same-report")], b.fact_id: [ref(b, "same-report")]}
    selected = select_by_variable(component, [a, b], {}, authority=a.authority,
        definitions=load_dictionary(), evidence_refs=refs)["age-limit"]
    assert not selected.conflict and not selected.fact_ids
    assert a.locator_ids != b.locator_ids


def test_explicit_future_sample_header_excludes_later_record_without_rewriting_date():
    from app.domain.contracts.work_draft import WorkDraftSourcePage
    rules, projected, component = clause()
    a, b = material(value=51, snapshot="visit"), material(value=52, snapshot="later")
    text = "采样时间:2025-08-15 9:46\n年龄:52岁"
    page = WorkDraftSourcePage(source_document_version_id="later-report", page_artifact_id="later-page", page_number=1,
        effective_text=text, effective_text_sha256=sha256(text.encode()).hexdigest(), extraction_complete=True)
    ref = WorkDraftEvidenceRef(fact_id=b.fact_id, locator_id=b.locator_ids[0],
        source_document_version_id=page.source_document_version_id, page_artifact_id=page.page_artifact_id,
        page_number=1, excerpt="年龄:52岁")
    anchors = {AnchorType.SCREENING_DATE: DateValue(value=date(2025, 8, 8), precision=DatePrecision.DAY)}
    before = b.model_dump_json()
    selected = select_by_variable(component, [a, b], anchors, authority=a.authority, definitions=load_dictionary(),
        evidence_refs={b.fact_id: [ref]}, source_pages=[page])["age-limit"]
    assert selected.fact_ids == (a.fact_id,) and not selected.conflict
    assert b.model_dump_json() == before and b.date_range is None
    # A print timestamp is not a visit/sample timestamp and cannot censor a result.
    other_text = text.replace("采样时间", "打印时间")
    other_page = page.model_copy(update={"effective_text": other_text,
        "effective_text_sha256": sha256(other_text.encode()).hexdigest()})
    unclear = select_by_variable(component, [a, b], anchors, authority=a.authority, definitions=load_dictionary(),
        evidence_refs={b.fact_id: [ref]}, source_pages=[other_page])["age-limit"]
    assert not unclear.fact_ids and not unclear.conflict


def test_unknown_value_does_not_shadow_a_literal_valid_reading():
    rules, projected, _ = clause()
    fact = material()
    unknown = material(snapshot="unknown").model_copy(update={"value": None, "polarity": FactPolarity.UNKNOWN})
    result = calculate_work_component(projected, frozen([fact, unknown]), rules, evidence_refs={})
    assert result.decision == D.INCLUSION_MET


def test_counterfactual_value_changes_result_without_changing_rule():
    rules, projected, _ = clause()
    old_hash = rules.model_dump_json()
    fact = material(value=17)
    result = calculate_work_component(projected, frozen([fact]), rules, evidence_refs={})
    assert result.decision == D.INCLUSION_NOT_MET
    assert rules.model_dump_json() == old_hash


@pytest.mark.parametrize("kind", [RuleKind.INCLUSION, RuleKind.EXCLUSION])
def test_no_child_result_never_becomes_a_vacuously_positive_parent(kind):
    rule = clause(kind=kind)[0].rules[0]
    result = compose_parent(rule, [], "run")
    assert result.system_issue is not None and result.decision is None and result.confidence is None


def test_numeric_threshold_is_converted_with_the_fact_not_just_displayed():
    from app.domain.variables.dictionary import VariableDef
    rules, projected, _ = clause()
    definition = VariableDef(variable_id="measurement", label_zh="测量值", value_type="number",
        canonical_unit="mg/L", unit_conversions={"g/L": 1000}, plausible_range=(0, 10000), domain="lab")
    atom = projected.expression.model_copy(deep=True)
    atom.predicate.value, atom.predicate.unit = 0.02, "g/L"
    requirements = [req.model_copy(update={"variable_id": "measurement"}) for req in projected.evidence_requirements]
    projected = projected.model_copy(update={"expression": atom, "evidence_requirements": requirements})
    rules = rules.model_copy(update={"variable_definitions": [definition]})
    fact = material(value=25).model_copy(update={"variable_id": "measurement", "unit": "mg/L"})
    result = calculate_work_component(projected, frozen([fact]), rules, evidence_refs={})
    assert result.decision == D.INCLUSION_MET and result.confidence == "low"


@pytest.mark.parametrize("sampling,expected", [(date(2025, 8, 15), D.INDETERMINATE), (date(2025, 8, 8), D.REQUIREMENT_MET)])
def test_procedure_completion_respects_date_and_does_not_assert_unspecified_fields(sampling, expected):
    from app.services.work_draft_calculation import calculate_procedures
    rules, _, component = clause()
    fact = material(day=sampling)
    frame = frozen([fact], {AnchorType.SCREENING_DATE: DateValue(value=date(2025, 8, 8), precision=DatePrecision.DAY)})
    requirement = component.evidence_requirements[0].model_copy(update={"procedure_catalog_item_id": "procedure"})
    frame.procedure_catalog = SimpleNamespace(items=[SimpleNamespace(item_id="procedure", official_code=None,
        position=0, source_excerpts=["完成检查"], label="检查", model_dump=lambda **_: {"label": "检查"})])
    frame.procedure_requirements = [requirement]
    result = calculate_procedures(frame, rules, evidence_refs={})
    assert result[0].decision == expected
    if expected == D.INDETERMINATE:
        assert result[0].confidence is None
    else:
        assert "未据此确认报告内所有结果齐全" in result[0].reason_text
