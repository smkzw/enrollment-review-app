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
from app.domain.contracts.rules import AtomicExpression, AtomicPredicate, EvidenceRequirement, LogicalExpression, Rule, RuleComponent, RuleSet, TimeConstraint, TimeQuantity
from app.domain.contracts.enums import LogicalOperator
from app.domain.contracts.work_draft import SystemIssue, WorkDraftItem
from app.domain.variables.dictionary import load_dictionary
from app.graph.subject_graph import SUBJECT_GRAPH, work_draft_steps
from app.projections.clause_pack import project_clause_pack
from app.services.work_draft_calculation import calculate_work_component, compose_parent, select_by_variable
from app.domain.contracts.work_draft import WorkDraftEvidenceRef

NOW = datetime(2026, 10, 12, tzinfo=UTC)


@pytest.mark.parametrize("kind,truth,expected", [
    (RuleKind.INCLUSION, "true", D.INCLUSION_MET),
    (RuleKind.INCLUSION, "unknown", D.INDETERMINATE),
    (RuleKind.EXCLUSION, "false", D.EXCLUSION_NOT_TRIGGERED),
    (RuleKind.EXCLUSION, "true", D.EXCLUSION_TRIGGERED),
])
def test_chart_judgment_relations_enter_saved_rule_consumer(kind, truth, expected):
    from app.domain.variables.dictionary import VariableDef
    rules, _, component = clause(kind=kind)
    predicate = component.expression.predicate
    predicate.comparator, predicate.value, predicate.unit = Comparator.EXISTS, None, None
    predicate.requires_professional_judgment = True
    component.evidence_requirements[0].variable_id = "clinical_judgment"
    rules.variable_definitions = [VariableDef(variable_id="clinical_judgment", label_zh="病历判断",
        value_type="boolean", domain="history")]
    frame = frozen([material()])
    frame.facts, frame.source_pages = [], []
    relation = {"truth": truth, "applicable": "yes", "conflict": False, "policy": False,
        "relation": "supports" if truth == "true" else "refutes" if truth == "false" else "not_found",
        "reason": "本节点病历有明确记载。" if truth != "unknown" else "本节点病历未见相关判断。",
        "source_read_refs": [{"source_document_version_id": "document", "page_artifact_id": "page",
            "page_number": 1, "excerpt": "本节点病历有明确记载", "disposition": "mentioned"}] if truth != "unknown" else []}
    result = calculate_work_component(project_clause_pack(rules).clauses[0], frame, rules, evidence_refs={},
        source_results={f"{component.rule_component_id}:{predicate.predicate_id}": relation})
    assert result.decision == expected and result.system_issue is None
    if truth != "unknown":
        assert result.confidence == "low" and result.source_read_refs and not result.evidence_refs


def test_false_base_condition_does_not_require_unrelated_positive_judgment():
    from app.domain.variables.dictionary import VariableDef
    rules, _, component = clause(kind=RuleKind.EXCLUSION)
    first = component.expression
    second = AtomicExpression(predicate=AtomicPredicate(predicate_id="judgment", subject="研究者",
        attribute="病情可能影响评价", comparator=Comparator.EXISTS, requires_professional_judgment=True))
    component.expression = LogicalExpression(operator=LogicalOperator.ALL, children=[first, second])
    component.evidence_requirements.append(component.evidence_requirements[0].model_copy(update={
        "requirement_id": "judgment-source", "variable_id": "clinical_judgment", "predicate_ids": ["judgment"]}))
    rules.variable_definitions.append(VariableDef(variable_id="clinical_judgment", label_zh="病历判断",
        value_type="boolean", domain="history"))
    fact = material(value=17)
    result = calculate_work_component(project_clause_pack(rules).clauses[0], frozen([fact]), rules, evidence_refs={},
        source_results={f"{component.rule_component_id}:judgment": {"truth": "unknown", "applicable": "yes",
            "conflict": False, "policy": False, "relation": "not_found", "reason": "未见针对性判断", "source_read_refs": []}})
    assert result.decision == D.EXCLUSION_NOT_TRIGGERED
    assert result.system_issue is None


@pytest.mark.parametrize("operator,first_truth,second_truth,expected", [
    (LogicalOperator.ALL, "false", "unknown", D.EXCLUSION_NOT_TRIGGERED),
    (LogicalOperator.ALL, "true", "unknown", D.INDETERMINATE),
    (LogicalOperator.ANY, "true", "unknown", D.EXCLUSION_TRIGGERED),
    (LogicalOperator.ANY, "false", "unknown", D.INDETERMINATE),
    (LogicalOperator.ALL, "true", "true", D.EXCLUSION_TRIGGERED),
    (LogicalOperator.ALL, "false", "false", D.EXCLUSION_NOT_TRIGGERED),
    (LogicalOperator.ANY, "false", "false", D.EXCLUSION_NOT_TRIGGERED),
    (LogicalOperator.ANY, "false", "true", D.EXCLUSION_TRIGGERED),
])
def test_joint_source_requirement_follows_only_its_relevant_bound_conditions(operator, first_truth, second_truth, expected):
    from app.domain.publication import canonical_hash
    from app.domain.variables.dictionary import VariableDef
    rules, _, component = clause(kind=RuleKind.EXCLUSION)
    atoms = [AtomicExpression(predicate=AtomicPredicate(predicate_id=key, subject="研究者",
        attribute=key, comparator=Comparator.EXISTS, requires_professional_judgment=True)) for key in ("base", "judgment")]
    component.expression = LogicalExpression(operator=operator, children=atoms)
    original = component.evidence_requirements[0].model_copy(update={"requirement_id": "joint-source",
        "variable_id": None, "predicate_ids": [], "fact_type": "病历判断", "description": "核对两项条件"})
    bound = [original.model_copy(update={"requirement_id": "variable_requirement:" + sha256(
        ":".join((component.rule_component_id, atom.predicate.predicate_id, original.requirement_id)).encode()).hexdigest()[:32],
        "variable_id": atom.predicate.predicate_id, "predicate_ids": [atom.predicate.predicate_id]}) for atom in atoms]
    component.evidence_requirements = [original, *bound]
    rules.variable_definitions.extend(VariableDef(variable_id=key, label_zh=key,
        value_type="boolean", domain="history") for key in ("base", "judgment"))
    frame = frozen([material()])
    frame.facts, frame.source_pages = [], []
    relation = {"truth": first_truth, "applicable": "yes", "conflict": False, "policy": False,
        "relation": "refutes" if first_truth == "false" else "supports", "reason": "病历明确记载该条件。",
        "source_read_refs": [{"source_document_version_id": "document", "page_artifact_id": "page",
            "page_number": 1, "excerpt": "病历明确记载该条件", "disposition": "mentioned"}]}
    relations = {f"{component.rule_component_id}:base": relation,
        f"{component.rule_component_id}:judgment": {**relation, "truth": second_truth,
            "relation": {"unknown": "not_found", "true": "supports", "false": "refutes"}[second_truth],
            "reason": "未见另一项判断" if second_truth == "unknown" else "另一项有明确记载",
            "source_read_refs": [] if second_truth == "unknown" else relation["source_read_refs"]}}
    before = canonical_hash(rules.model_dump(mode="json"))
    result = calculate_work_component(project_clause_pack(rules).clauses[0], frame, rules,
        evidence_refs={}, source_results=relations)
    assert result.decision == expected and result.system_issue is None
    assert canonical_hash(rules.model_dump(mode="json")) == before
    if expected in {D.EXCLUSION_NOT_TRIGGERED, D.EXCLUSION_TRIGGERED}:
        assert result.confidence == "low"
        # A changed child is not proof that the original joint source requirement was fulfilled.
        bound[0].description = "另需收集的独立资料"
        blocked = calculate_work_component(project_clause_pack(rules).clauses[0], frame, rules,
            evidence_refs={}, source_results=relations)
        assert blocked.decision == D.INDETERMINATE


def test_source_notes_do_not_hide_a_missing_numeric_operand():
    from app.domain.variables.dictionary import VariableDef
    rules, _, component = clause(kind=RuleKind.EXCLUSION)
    numeric = component.expression
    source = AtomicExpression(predicate=AtomicPredicate(predicate_id="judgment", subject="研究者",
        attribute="另一条件", comparator=Comparator.EXISTS, requires_professional_judgment=True))
    component.expression = LogicalExpression(operator=LogicalOperator.ANY, children=[numeric, source])
    component.evidence_requirements.append(component.evidence_requirements[0].model_copy(update={
        "requirement_id": "other-source", "variable_id": "clinical_judgment", "predicate_ids": ["judgment"]}))
    rules.variable_definitions.append(VariableDef(variable_id="clinical_judgment", label_zh="病历判断",
        value_type="boolean", domain="history"))
    frame = frozen([material()])
    frame.facts, frame.source_pages = [], []
    relation = {"truth": "false", "applicable": "yes", "conflict": False, "policy": False,
        "relation": "refutes", "reason": "另一条件明确否认。", "source_read_refs": [{
            "source_document_version_id": "document", "page_artifact_id": "page", "page_number": 1,
            "excerpt": "另一条件明确否认", "disposition": "mentioned"}]}
    result = calculate_work_component(project_clause_pack(rules).clauses[0], frame, rules,
        evidence_refs={}, source_results={f"{component.rule_component_id}:judgment": relation})
    assert result.decision == D.INDETERMINATE
    assert "另一条件明确否认" in result.reason_text and "年龄已核实记录" in result.reason_text


@pytest.mark.parametrize("original_types,bound_types,compatible", [
    ([], ["investigator_assessment"], True),
    (["investigator_assessment"], [], False),
    (["investigator_assessment"], ["prescription"], False),
])
def test_binding_source_type_refinement_is_not_a_change_to_other_source_policies(original_types, bound_types, compatible):
    from app.services.work_draft_calculation import binding_preserves_source_requirement
    _, _, component = clause()
    original = component.evidence_requirements[0].model_copy(update={"required_source_types": original_types})
    bound = original.model_copy(update={"required_source_types": bound_types})
    assert binding_preserves_source_requirement(original, bound) is compatible
    bound.description = "不同要求，不能按相同标签采信"
    assert not binding_preserves_source_requirement(original, bound)
    bound.description = original.description
    bound.source_validity_window = TimeQuantity(value=3, unit="day")
    assert not binding_preserves_source_requirement(original, bound)


@pytest.mark.parametrize("anchor,role,exact,truth,expected", [
    (True, "sampling", True, "true", D.INCLUSION_MET),
    (False, "sampling", True, "true", D.INDETERMINATE),
    (True, "report", True, "true", D.INDETERMINATE),
    (True, "sampling", False, "true", D.INDETERMINATE),
    (False, "sampling", True, "false", D.INDETERMINATE),
    (True, "sampling", True, "false", D.INCLUSION_NOT_MET),
])
def test_source_relation_cannot_bypass_deterministic_time_proof(anchor, role, exact, truth, expected):
    window = TimeConstraint(anchor_type=AnchorType.SCREENING_DATE, direction=TimeDirection.BEFORE,
        upper_bound_days=7)
    rules, _, component = clause(time=window)
    component.expression.predicate.requires_professional_judgment = True
    fact = material(day=date(2026, 10, 10)).model_copy(update={"date_role": role})
    frame = frozen([fact], {AnchorType.SCREENING_DATE: DateValue(value=date(2026, 10, 12), precision=DatePrecision.DAY)} if anchor else {})
    ref = WorkDraftEvidenceRef(fact_id=fact.fact_id, locator_id=fact.locator_ids[0], source_document_version_id="document",
        page_artifact_id="page", page_number=1, excerpt=fact.assertion_basis.assertion_text)
    relation = {"truth": truth, "applicable": "yes", "conflict": False, "policy": False,
        "relation": "supports" if truth == "true" else "refutes",
        "reason": "原文有相关记录，时间由程序核对。", "source_read_refs": [{
            "source_document_version_id": "document", "page_artifact_id": "page", "page_number": 1,
            "excerpt": ref.excerpt if exact else "另一个位置的记录", "disposition": "mentioned"}]}
    result = calculate_work_component(project_clause_pack(rules).clauses[0], frame, rules,
        evidence_refs={fact.fact_id: [ref]}, source_results={f"{component.rule_component_id}:age-limit": relation})
    assert result.decision == expected and result.system_issue is None
    if expected == D.INDETERMINATE:
        assert "不能直接认作落入规定期间" in result.reason_text


@pytest.mark.parametrize("kind", [RuleKind.INCLUSION, RuleKind.EXCLUSION])
@pytest.mark.parametrize("operator", [LogicalOperator.ALL, LogicalOperator.ANY])
@pytest.mark.parametrize("value", [17, 52])
def test_inapplicable_atom_does_not_erase_an_independent_active_condition(kind, operator, value):
    from app.domain.publication import canonical_hash
    rules, _, component = clause(kind=kind)
    active = component.expression
    scoped = AtomicExpression(predicate=active.predicate.model_copy(update={"predicate_id": "scoped",
        "applicable_population": "另一适用人群"}))
    component.expression = LogicalExpression(operator=operator, children=[scoped, active])
    component.evidence_requirements.append(component.evidence_requirements[0].model_copy(update={
        "requirement_id": "scope-record", "predicate_ids": ["scoped"]}))
    before = canonical_hash(rules.model_dump(mode="json"))
    relation = {"truth": "unknown", "applicable": "no", "conflict": False, "policy": False,
        "relation": "unclear", "reason": "原件证明不属于该原子条件的适用人群。", "source_read_refs": [{
            "source_document_version_id": "document", "page_artifact_id": "page", "page_number": 1,
            "excerpt": "不属于该人群", "disposition": "unresolved"}]}
    result = calculate_work_component(project_clause_pack(rules).clauses[0], frozen([material(value=value)]), rules,
        evidence_refs={}, source_results={f"{component.rule_component_id}:scoped": relation})
    expected = (D.INCLUSION_MET if value >= 18 else D.INCLUSION_NOT_MET) if kind == RuleKind.INCLUSION else (
        D.EXCLUSION_TRIGGERED if value >= 18 else D.EXCLUSION_NOT_TRIGGERED)
    assert result.decision == expected and result.system_issue is None
    assert result.source_read_refs[0].excerpt == "不属于该人群"
    assert canonical_hash(rules.model_dump(mode="json")) == before


@pytest.mark.parametrize("operator", [LogicalOperator.ALL, LogicalOperator.ANY, LogicalOperator.NOT])
def test_entirely_inapplicable_tree_is_not_applicable_not_met_or_refuted(operator):
    rules, _, component = clause()
    first = component.expression
    first.predicate.applicable_population = "指定人群"
    atoms = [first] if operator == LogicalOperator.NOT else [first, AtomicExpression(
        predicate=first.predicate.model_copy(update={"predicate_id": "second"}))]
    component.expression = LogicalExpression(operator=operator, children=atoms)
    relations = {f"{component.rule_component_id}:{atom.predicate.predicate_id}": {
        "truth": "unknown", "applicable": "no", "conflict": False, "policy": False,
        "relation": "unclear", "reason": "原件证明该人群要求不适用。", "source_read_refs": [{
            "source_document_version_id": "document", "page_artifact_id": "page", "page_number": 1,
            "excerpt": "不属于该人群", "disposition": "unresolved"}]} for atom in atoms}
    result = calculate_work_component(project_clause_pack(rules).clauses[0], frozen([material()]), rules,
        evidence_refs={}, source_results=relations)
    assert result.decision == D.NOT_APPLICABLE and result.confidence is None and result.system_issue is None


@pytest.mark.parametrize("population,quotes,conflict", [(None, True, False), ("指定人群", False, False),
    ("指定人群", True, True)])
def test_inapplicability_never_comes_from_unscoped_unquoted_or_conflicting_claim(population, quotes, conflict):
    rules, _, component = clause()
    component.expression.predicate.applicable_population = population
    relation = {"truth": "unknown", "applicable": "no", "conflict": conflict, "policy": False,
        "relation": "unclear", "reason": "尚未核清", "source_read_refs": [{
            "source_document_version_id": "document", "page_artifact_id": "page", "page_number": 1,
            "excerpt": "相关记录", "disposition": "unresolved"}] if quotes else []}
    result = calculate_work_component(project_clause_pack(rules).clauses[0], frozen([material()]), rules,
        evidence_refs={}, source_results={f"{component.rule_component_id}:age-limit": relation})
    assert result.decision != D.NOT_APPLICABLE


def test_evaluator_change_invalidates_prior_acknowledgement_identity():
    rules, projected, _ = clause()
    frame = frozen([material()])
    frame.evaluator_version = "previous"
    old = calculate_work_component(projected, frame, rules, evidence_refs={})
    frame.evaluator_version = "current"
    new = calculate_work_component(projected, frame, rules, evidence_refs={})
    assert old.decision == new.decision and old.input_hash != new.input_hash


@pytest.mark.parametrize("value,expected", [(17, D.EXCLUSION_NOT_TRIGGERED), (52, D.EXCLUSION_TRIGGERED)])
def test_inapplicable_exception_does_not_erase_active_trigger(value, expected):
    from app.domain.publication import canonical_hash
    rules, _, component = clause(kind=RuleKind.EXCLUSION)
    component.exception_expression = AtomicExpression(predicate=component.expression.predicate.model_copy(update={
        "predicate_id": "exception", "applicable_population": "另一适用人群"}))
    component.evidence_requirements.append(component.evidence_requirements[0].model_copy(update={
        "requirement_id": "exception-source", "predicate_ids": ["exception"]}))
    relation = {"truth": "unknown", "applicable": "no", "conflict": False, "policy": False,
        "relation": "unclear", "reason": "不属于例外所限定的人群。", "source_read_refs": [{
            "source_document_version_id": "document", "page_artifact_id": "page", "page_number": 1,
            "excerpt": "不属于例外人群", "disposition": "mentioned"}]}
    before = canonical_hash(rules.model_dump(mode="json"))
    result = calculate_work_component(project_clause_pack(rules).clauses[0], frozen([material(value=value)]), rules,
        evidence_refs={}, source_results={f"{component.rule_component_id}:exception": relation})
    assert result.decision == expected and result.system_issue is None
    assert canonical_hash(rules.model_dump(mode="json")) == before


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


def numeric_history_case(*, value=None, domain="history", time=None):
    from app.domain.variables.dictionary import VariableDef
    rules, _, component = clause(kind=RuleKind.EXCLUSION, time=time)
    definition = VariableDef(variable_id="historical_quantity", label_zh="既往记录用量",
        value_type="number", canonical_unit="mg", plausible_range=(0, 1000), domain=domain)
    rules.variable_definitions = [definition]
    predicate = component.expression.predicate
    predicate.attribute, predicate.value, predicate.unit = "既往记录用量", 20, "mg"
    component.evidence_requirements[0].variable_id = definition.variable_id
    seed = material(value=25 if value is None else value)
    frame = frozen([seed])
    text = "否认既往有达到所述用量的记录。"
    from app.domain.contracts.work_draft import WorkDraftSourcePage
    frame.source_pages = [WorkDraftSourcePage(source_document_version_id="document", page_artifact_id="page",
        page_number=1, document_category="study_chart", effective_text=text,
        effective_text_sha256=sha256(text.encode()).hexdigest(), extraction_complete=True)]
    refs = {}
    frame.facts = []
    if value is not None:
        basis = seed.assertion_basis.model_copy(update={"asserted_object": definition.label_zh,
            "assertion_text": f"既往记录用量 {value} mg"})
        values = {key: getattr(seed, key) for key in ("authority", "fact_type", "polarity", "date_range", "profile_lane", "date_role")}
        values.update(asserted_object=definition.label_zh, assertion_basis=basis,
            variable_id=definition.variable_id, value=value, unit="mg")
        fact = seed.model_copy(update={**values, "stable_identity": clinical_fact_stable_identity(**values)})
        frame.facts = [fact]
        refs[fact.fact_id] = [WorkDraftEvidenceRef(fact_id=fact.fact_id, locator_id=basis.locator_id,
            source_document_version_id="document", page_artifact_id="page", page_number=1,
            excerpt=basis.assertion_text)]
    frame.clause_pack = project_clause_pack(rules)
    frame.procedure_catalog = None
    return rules, frame, refs


@pytest.mark.parametrize("domain,expected", [("history", 1), ("medication", 1), ("lab", 0),
    ("vital", 0), ("score", 0), ("demographic", 0)])
def test_numeric_history_routing_is_domain_based_not_a_clinical_keyword(domain, expected):
    from app.services.work_draft_semantics import targets_for_review
    rules, frame, _ = numeric_history_case(domain=domain)
    assert len(targets_for_review(frame, rules)) == expected


def test_compound_judgment_reads_receive_approved_policy_and_full_sibling_logic():
    from app.domain.variables.dictionary import VariableDef
    from app.domain.publication import canonical_hash
    from app.services.work_draft_semantics import targets_for_review, wire_target
    rules, frame, _ = numeric_history_case()
    component = rules.rules[0].components[0]
    judgment = AtomicExpression(predicate=AtomicPredicate(predicate_id="paired-response",
        subject="受试者", attribute="与该次既往治疗相对应的疗效", comparator=Comparator.EXISTS,
        requires_professional_judgment=True))
    component.expression = LogicalExpression(operator=LogicalOperator.ALL, children=[component.expression, judgment])
    component.evidence_requirements.append(component.evidence_requirements[0].model_copy(update={
        "requirement_id": "paired-response-record", "variable_id": "paired_response", "predicate_ids": ["paired-response"],
        "description": "须核同一次治疗与疗效，不将随后开始的治疗用于当前节点。"}))
    rules.variable_definitions.append(VariableDef(variable_id="paired_response", label_zh="对应治疗的疗效",
        value_type="boolean", domain="history"))
    before = canonical_hash(rules.model_dump(mode="json"))
    frame.clause_pack = project_clause_pack(rules)
    targets = targets_for_review(frame, rules)
    assert len(targets) == 2
    context = targets[0]["source_context"]
    assert all(t["source_context"] == context for t in targets)
    assert "correspondence_check" not in targets[0]
    assert "同一事件、治疗或采集" in targets[1]["correspondence_check"]
    assert "其他期间的结果不能移给所要求的期间" in targets[1]["correspondence_check"]
    assert context["expression"]["operator"] == "all"
    assert {x["predicate"]["predicate_id"] for x in context["expression"]["children"]} == {"age-limit", "paired-response"}
    assert context["evidence_requirements"][1]["description"] == component.evidence_requirements[1].description
    assert canonical_hash(rules.model_dump(mode="json")) == before
    # An old atom-only request cannot qualify an answer under an unseen policy.
    old = {k: v for k, v in targets[0].items() if k != "source_context"}
    assert wire_target(old) != wire_target(targets[0])
    component.evidence_requirements[1].description += " 且期间必须相同。"
    frame.clause_pack = project_clause_pack(rules)
    assert wire_target(targets_for_review(frame, rules)[0]) != wire_target(targets[0])


def test_numeric_history_explicit_denial_enters_consumer_without_fabricating_a_zero_fact():
    from app.services.work_draft_semantics import targets_for_review, SourceRelation, validate_relations, relation_inputs
    rules, frame, refs = numeric_history_case()
    target = targets_for_review(frame, rules)[0]
    row = SourceRelation(target_id=target["target_id"], relation="refutes", applicable="yes",
        object_matches=True, time_matches=True, reason="原件明确否认该完整条件。",
        quotes=[{"page_artifact_id": "page", "excerpt": frame.source_pages[0].effective_text}])
    valid = validate_relations({"results": [row.model_dump()]}, [target], frame.source_pages)[0]
    result = calculate_work_component(frame.clause_pack.clauses[0], frame, rules, evidence_refs=refs,
        source_results={target["target_id"]: relation_inputs(valid, target, frame.source_pages)})
    assert result.decision == D.EXCLUSION_NOT_TRIGGERED and result.confidence == "low"
    assert result.source_read_refs[0].excerpt == frame.source_pages[0].effective_text
    assert not result.evidence_refs and not frame.facts
    assert "0mg" not in result.reason_text


@pytest.mark.parametrize("value,truth,conflict,expected", [
    (25, "unknown", False, D.EXCLUSION_TRIGGERED),
    (5, "unknown", False, D.EXCLUSION_NOT_TRIGGERED),
    (25, "true", False, D.EXCLUSION_TRIGGERED),
    (5, "false", False, D.EXCLUSION_NOT_TRIGGERED),
    (25, "false", False, D.CONFLICT),
    (5, "true", False, D.CONFLICT),
    (25, "unknown", True, D.CONFLICT),
    (None, "unknown", False, D.INDETERMINATE),
])
def test_numeric_history_keeps_proven_arithmetic_and_opposing_source(value, truth, conflict, expected):
    rules, frame, refs = numeric_history_case(value=value)
    target_id = "age-component:age-limit"
    source = {"truth": truth, "applicable": "yes", "conflict": conflict, "policy": False,
        "relation": "conflict" if conflict else "unclear" if truth == "unknown" else "refutes" if truth == "false" else "supports",
        "reason": "本次病历原文关系。", "source_read_refs": [{"source_document_version_id": "document",
            "page_artifact_id": "page", "page_number": 1, "excerpt": frame.source_pages[0].effective_text,
            "disposition": "unresolved" if truth == "unknown" else "mentioned"}]}
    result = calculate_work_component(frame.clause_pack.clauses[0], frame, rules, evidence_refs=refs,
        source_results={target_id: source})
    assert result.decision == expected and result.system_issue is None
    if value is not None:
        assert result.evidence_refs[0].fact_id == frame.facts[0].fact_id
        assert f"{value}mg" in result.reason_text
    if expected == D.CONFLICT:
        assert "未选择有利结果" in result.reason_text and result.source_read_refs


def test_unperformed_numeric_history_read_is_technical_not_patient_missing_data():
    rules, frame, refs = numeric_history_case()
    result = calculate_work_component(frame.clause_pack.clauses[0], frame, rules, evidence_refs=refs)
    assert result.decision is None and result.system_issue is not None
    assert "原文核对尚未完成" in result.reason_text
    # A valid quantity remains usable even if the semantic read did not complete.
    rules, frame, refs = numeric_history_case(value=25)
    result = calculate_work_component(frame.clause_pack.clauses[0], frame, rules, evidence_refs=refs)
    assert result.decision == D.EXCLUSION_TRIGGERED and result.system_issue is None


def test_variable_identity_not_display_type_selects_and_computes():
    rules, projected, component = clause()
    fact = material()
    selections = select_by_variable(component, [fact], {}, authority=fact.authority, definitions=load_dictionary())
    assert selections["age-limit"].fact_ids == (fact.fact_id,)
    result = calculate_work_component(projected, frozen([fact]), rules, evidence_refs={})
    assert result.decision == D.INCLUSION_MET and result.confidence == "high"


def test_outer_all_does_not_become_any_because_one_inner_group_is_any():
    rules, _, component = clause()
    a = component.expression
    b = AtomicExpression(predicate=a.predicate.model_copy(update={"predicate_id": "upper", "comparator": Comparator.LTE, "value": 40}))
    c = AtomicExpression(predicate=a.predicate.model_copy(update={"predicate_id": "alternative", "comparator": Comparator.LTE, "value": 60}))
    component.expression = LogicalExpression(operator=LogicalOperator.ALL, children=[a,
        LogicalExpression(operator=LogicalOperator.ANY, children=[b, c])])
    for predicate in (b.predicate, c.predicate):
        component.evidence_requirements.append(component.evidence_requirements[0].model_copy(update={
            "requirement_id": predicate.predicate_id + "-record", "predicate_ids": [predicate.predicate_id]}))
    fact = material(value=52)
    result = calculate_work_component(project_clause_pack(rules).clauses[0], frozen([fact]), rules, evidence_refs={})
    assert result.decision == D.INCLUSION_MET
    older = material(value=17)
    result = calculate_work_component(project_clause_pack(rules).clauses[0], frozen([older]), rules, evidence_refs={})
    assert result.decision == D.INCLUSION_NOT_MET
    assert component.expression.children[1].operator == LogicalOperator.ANY


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


@pytest.mark.parametrize("other_value,expected", [("0.06阴性(-)", D.EXCLUSION_NOT_TRIGGERED),
    ("阳性(+)", D.CONFLICT)])
def test_same_day_qualitative_labels_use_the_same_comparison_for_conflicts(other_value, expected):
    rules, _, component = clause(kind=RuleKind.EXCLUSION)
    component.expression.predicate.attribute = "抗体结果"
    component.expression.predicate.comparator = Comparator.EQ
    component.expression.predicate.value = "阳性"
    component.expression.predicate.unit = "unitless"
    component.evidence_requirements[0].variable_id = "hiv_antibody"
    rules.variable_definitions = [load_dictionary()["hiv_antibody"]]
    first = material(variable_id="hiv_antibody", value="阴性", unit="unitless", day=date(2026, 10, 12))
    second = material(variable_id="hiv_antibody", value=other_value, unit="unitless", day=date(2026, 10, 12), snapshot="second")
    before = [first.model_dump_json(), second.model_dump_json()]
    frame = frozen([first, second], {AnchorType.SCREENING_DATE: DateValue(value=date(2026, 10, 12), precision=DatePrecision.DAY)})
    result = calculate_work_component(project_clause_pack(rules).clauses[0], frame, rules, evidence_refs={})
    assert result.decision == expected
    assert [first.model_dump_json(), second.model_dump_json()] == before


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


@pytest.mark.parametrize("value,expected", [(150, D.EXCLUSION_NOT_TRIGGERED), (250, D.EXCLUSION_TRIGGERED),
    (199, D.EXCLUSION_NOT_TRIGGERED)])
@pytest.mark.parametrize("range_text", ["10-100", "10--100 U/L"])
def test_reference_ratio_uses_raw_published_fact_without_rewriting_it(value, expected, range_text):
    from app.domain.contracts.fact_context import FactContextQualifier
    rules, _, component = clause(kind=RuleKind.EXCLUSION)
    atom = component.expression.predicate
    atom.attribute, atom.comparator, atom.value, atom.unit = "AST相对上限倍数", Comparator.GT, 2, "×ULN"
    component.evidence_requirements[0].variable_id = "ast_uln_ratio"
    rules.variable_definitions = [load_dictionary()["ast_uln_ratio"]]
    fact = material(value=value, variable_id="ast", unit="U/L", day=date(2026, 10, 12))
    basis = fact.assertion_basis.model_copy(update={"asserted_object": "AST",
        "assertion_text": f"AST {value} 10--100 U/L" if "--" in range_text else f"AST {value} 10-100 U/L",
        "contextual_qualifiers": [FactContextQualifier(kind="reference_range", label=range_text)]})
    fact = fact.model_copy(update={"asserted_object": "AST", "assertion_basis": basis})
    frame = frozen([fact], {AnchorType.SCREENING_DATE: DateValue(value=date(2026, 10, 12), precision=DatePrecision.DAY)})
    before = fact.model_dump_json()
    result = calculate_work_component(project_clause_pack(rules).clauses[0], frame, rules, evidence_refs={})
    assert result.decision == expected
    assert "本行参考上限100U/L" in result.reason_text
    assert fact.model_dump_json() == before
    unclear = material(value=150, variable_id="ast", unit="U/L", snapshot="unclear", day=date(2026, 10, 12))
    partial = calculate_work_component(project_clause_pack(rules).clauses[0],
        frozen([fact, unclear], frame.review_episode.anchor_dates), rules, evidence_refs={})
    assert partial.decision == expected and partial.confidence == "low"
    if value == 199:
        assert result.confidence == "low" and "接近方案阈值" in result.confidence_reason
    changed = fact.model_copy(update={"assertion_basis": basis.model_copy(update={
        "assertion_text": f"AST {value} 10-150 U/L", "contextual_qualifiers": [FactContextQualifier(kind="reference_range", label="10-150")]})})
    second = calculate_work_component(project_clause_pack(rules).clauses[0], frozen([changed], frame.review_episode.anchor_dates), rules, evidence_refs={})
    assert second.input_hash != result.input_hash


def test_missing_reference_cannot_become_an_assumed_ratio():
    rules, _, component = clause(kind=RuleKind.EXCLUSION)
    component.expression.predicate.unit = "×ULN"
    component.evidence_requirements[0].variable_id = "alt_uln_ratio"
    rules.variable_definitions = [load_dictionary()["alt_uln_ratio"]]
    fact = material(value=150, variable_id="alt", unit="U/L")
    result = calculate_work_component(project_clause_pack(rules).clauses[0], frozen([fact]), rules, evidence_refs={})
    assert result.decision is None and result.system_issue is not None


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


def test_unfinished_written_judgment_search_is_not_reported_as_missing_record():
    rules, _, component = clause()
    component.expression.predicate.requires_professional_judgment = True
    result = calculate_work_component(project_clause_pack(rules).clauses[0],
        frozen([material()]), rules, evidence_refs={})
    assert result.system_issue is not None and result.decision is None
    assert "核对尚未完成" in result.reason_text
    assert "没有记载" not in result.reason_text


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


@pytest.mark.parametrize("kind, current_decision", [
    (RuleKind.INCLUSION, D.INCLUSION_MET),
    (RuleKind.INCLUSION, D.INCLUSION_NOT_MET),
    (RuleKind.EXCLUSION, D.EXCLUSION_NOT_TRIGGERED),
    (RuleKind.EXCLUSION, D.EXCLUSION_TRIGGERED),
    (RuleKind.INCLUSION, D.INDETERMINATE),
    (RuleKind.INCLUSION, D.CONFLICT),
    (RuleKind.INCLUSION, D.PROFESSIONAL_JUDGMENT),
])
def test_parent_judges_current_node_without_approving_future_requirements(kind, current_decision):
    rule = clause(kind=kind)[0].rules[0]
    common = dict(review_run_id="run", official_code=rule.official_code, rule_kind=kind,
        title="当前要求", source_text="有源要求", reason_text="已核对当前要求", input_hash="f" * 64)
    due = WorkDraftItem(**common, item_id="due", decision=current_decision,
        confidence="high" if current_decision in {D.INCLUSION_MET, D.INCLUSION_NOT_MET,
            D.EXCLUSION_NOT_TRIGGERED, D.EXCLUSION_TRIGGERED} else None)
    future = WorkDraftItem(**{**common, "title": "后续要求", "reason_text": "未到期"},
        item_id="future", decision=D.NOT_DUE)
    result = compose_parent(rule, [due, future], "run")
    assert result.decision == current_decision
    assert result.confidence == due.confidence
    assert "仅依据已到期要求" in result.reason_text
    assert "后续要求未到期，届时须重新审核" in result.reason_text
    assert future.decision == D.NOT_DUE and future.confidence is None


def test_future_requirement_does_not_hide_current_system_issue_or_create_completion():
    rule = clause()[0].rules[0]
    common = dict(review_run_id="run", official_code=rule.official_code, rule_kind=rule.kind,
        title="要求", source_text="原文", reason_text="原因", input_hash="f" * 64)
    future = WorkDraftItem(**common, item_id="future", decision=D.NOT_DUE)
    issue = SystemIssue(kind="method_unsupported", affected_codes=[rule.official_code],
        detail="计算未接入", alternative="核查原件")
    current = WorkDraftItem(**common, item_id="current", system_issue=issue)
    result = compose_parent(rule, [current, future], "run")
    assert result.decision is None and result.system_issue == issue
    assert issue.detail in result.reason_text
    assert compose_parent(rule, [future], "run").decision == D.NOT_DUE


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


@pytest.mark.parametrize("change,expected", [(None, True), ("source", False), ("subject", False),
    ("snapshot", False), ("processing", False), ("dictionary", False), ("running", False),
    ("rules", False), ("phase", False)])
def test_saved_page_coverage_reuse_checks_source_and_dictionary_not_rule_revision(change, expected):
    from app.services.review_context_assembly import normalization_source_is_reusable
    current = material().authority
    prior = current.model_copy(update={"protocol_version_id": "old-protocol", "rule_set_revision": 0,
        "episode_revision": 0})
    run = SimpleNamespace(authority=prior, status=SimpleNamespace(value="partial"))
    old_rules, _, _ = clause()
    new_rules = old_rules.model_copy(deep=True)
    old_protocol, new_protocol = SimpleNamespace(sha256="a" * 64), SimpleNamespace(sha256="a" * 64)
    if change == "source":
        new_protocol.sha256 = "b" * 64
    elif change in {"subject", "snapshot", "processing", "rules"}:
        key = {"subject": "subject_id", "snapshot": "evidence_snapshot_v2_id",
            "processing": "complete_processing_revision_id", "rules": "rule_set_id"}[change]
        run.authority = prior.model_copy(update={key: "other"})
    elif change == "dictionary":
        new_rules.variable_definitions = []
    elif change == "running":
        run.status.value = "running"
    elif change == "phase":
        new_rules.study_phase = StudyPhase.PHASE_II
    assert normalization_source_is_reusable(run, current, old_rules, new_rules, old_protocol, new_protocol) == expected


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
