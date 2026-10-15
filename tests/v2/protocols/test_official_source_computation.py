"""Calculation definitions persist without approving an operand set."""
from __future__ import annotations

import copy
import json
from fractions import Fraction

import pytest
from pydantic import ValidationError
from jsonschema import Draft202012Validator

from app.agents.protocol_deconstructor import (
    _SOURCE_COMPUTATION_CONTRACT, _batch_schema_repair_prompt, _next_batch_prompt,
    _canonical_wire_atom_key, _compact_schema, _compact_repair_schema,
    _repair_prompt, _system_predicate_id, _wire_atom, _wire_source_computation_schema,
    build_protocol_deconstruction_prompt, protocol_prompt_template_sha256,
    revise_protocol_draft_from_feedback, ProtocolAgentResponse, semantic_candidate_from_draft,
)
from app.agents.protocol_control_semantic_point import SourceComputation as AgentComputation
from app.domain.contracts.source_computation import SourceComputation
from app.domain.contracts.rules import AtomicPredicate, AtomicExpression, LogicalExpression, RuleComponent, Rule
from app.domain.contracts.enums import GapType, LogicalOperator, ReviewStage, TruthValue, ActionTarget, RuleKind, StudyPhase
from app.domain.contracts.predicate_binding import FrozenRuleComponent, FrozenPredicateIdentity
from app.domain.expression import evaluate_calculated_numeric_value, evaluate_component, evaluate_expression
from app.domain.gates.assessment import derive_gate_gap_types
from app.domain.policies import ACTION_CONTENT
from app.services.protocol_draft_service import _logic_payload
from app.services.predicate_binding_input import _frozen_component
from app.evidence.artifacts import ArtifactStore
from app.storage.config import resolve_data_paths
from tests.v2.test_contract_logic import evaluation_context
from tests.v2.protocols.test_deconstruction_gate_slice3 import _fixture


CLAUSES = ["取最近三次记录的均值，本次审核值至少为7分。", "缺失记录不填补，最多允许缺失一次。"]


def computation():
    return {
        "operator": "mean", "operator_ref": {"statement_index": 0, "quote": "均值"},
        "input_refs": [{"statement_index": 0, "quote": "最近三次记录"}],
        "missing_policy": "exclude", "missing_ref": {"statement_index": 1, "quote": CLAUSES[1]},
        "declared_input_count": {"value": 3, "number_text": "三", "source": {"statement_index": 0, "quote": "最近三次记录"}},
        "max_missing_count": {"value": 1, "number_text": "一", "source": {"statement_index": 1, "quote": "最多允许缺失一次"}},
    }


def predicate(**updates):
    data = dict(predicate_id="p-computation", subject="受试者", attribute="审核值",
                comparator="gte", value=7, unit="分", source_clauses=CLAUSES,
                source_computation=computation())
    return AtomicPredicate(**(data | updates))


def test_agent_reexports_identical_type_and_optional_absence_preserves_old_bytes():
    assert AgentComputation is SourceComputation
    without = predicate(source_computation=None).model_dump(mode="json")
    assert "source_computation" not in without
    assert AtomicPredicate.model_validate(without).model_dump(mode="json") == without


@pytest.mark.parametrize("compact", [False, True])
def test_computation_guidance_is_shared_by_author_batch_and_recovery(compact):
    source, _, _ = _fixture()
    prompts = [
        build_protocol_deconstruction_prompt(source, prompt_template="忠实理解来源。", compact=compact),
        _next_batch_prompt(["IN-01"], batch_number=2, batch_total=2,
                          candidate_id="candidate", compact=compact),
        _batch_schema_repair_prompt(["IN-01"], candidate_id="candidate", agent_call_id=None,
            batch_id="batch", problem="缺少输入来源", compact=compact),
        _repair_prompt([], attempt=1, parsed_draft_available=True,
            replacement_rule_codes=["IN-01"], compact=compact),
    ]
    for prompt in prompts:
        assert prompt.count(_SOURCE_COMPUTATION_CONTRACT) == 1
        assert "不另造‘已计算’的患者义务" in prompt
        assert "不证明病历输入已核实" in prompt


def test_formal_local_revision_receives_guidance_without_rewriting_other_rules():
    from app.domain.contracts.agent_io import ProtocolSemanticRuleRepair
    source, draft, _ = _fixture()
    current = semantic_candidate_from_draft(draft)
    target = next(rule for rule in current.proposed_rules if rule.official_code == "EX-01")
    response = ProtocolSemanticRuleRepair(candidate_id=current.candidate_id, replacement_rules=[target])
    prompts = []

    class FrozenTransport:
        def start(self, *, prompt, output_kind):
            assert output_kind == "semantic_rule_repair"
            prompts.append(prompt)
            return ProtocolAgentResponse(session_id="frozen-guidance", text=response.model_dump_json())

        def continue_session(self, **kwargs):
            raise AssertionError("Valid unchanged reply must not trigger recovery")

    revised = revise_protocol_draft_from_feedback(source, draft, target_rule_code="EX-01",
        feedback_note="仅核对计算定义的归属，没有原文依据不修改。", transport=FrozenTransport(), preserve_review_items=True)
    assert len(prompts) == 1 and prompts[0].count(_SOURCE_COMPUTATION_CONTRACT) == 1
    assert semantic_candidate_from_draft(revised).proposed_rules == current.proposed_rules
    assert [rule for rule in revised.proposed_rules if rule.official_code != "EX-01"] == [
        rule for rule in draft.proposed_rules if rule.official_code != "EX-01"]
    assert revised.unresolved_items == draft.unresolved_items


def test_shared_computation_guidance_changes_prompt_identity_not_saved_predicates(monkeypatch):
    original = predicate().model_dump_json()
    before = protocol_prompt_template_sha256("fixture")
    monkeypatch.setattr("app.agents.protocol_deconstructor._SOURCE_COMPUTATION_CONTRACT",
                        _SOURCE_COMPUTATION_CONTRACT + "变更的有源合同。")
    assert protocol_prompt_template_sha256("fixture") != before
    assert predicate().model_dump_json() == original


@pytest.mark.parametrize("schema_factory", [_compact_schema, _compact_repair_schema])
def test_remote_author_and_repair_explicitly_require_calculation_input_sources(schema_factory):
    schema = json.loads(schema_factory())
    definition = schema["$defs"]["SourceComputation"]
    assert "input_refs" in definition["required"]
    validator = Draft202012Validator(definition | {"$defs": schema["$defs"]})
    validator.validate(computation())
    missing = computation()
    missing.pop("input_refs")
    assert list(validator.iter_errors(missing))
    # Saved legacy omissions remain readable, not a valid new author response
    # or an approval to construct the source scope on the author's behalf.
    legacy = SourceComputation.model_validate(missing)
    assert legacy.input_refs == []
    with pytest.raises(ValidationError, match="计算操作须声明输入选择"):
        predicate(source_computation=missing)


def test_wire_schema_hydration_save_restore_diff_preserves_calculation_sources(tmp_path):
    calculation = computation()
    Draft202012Validator(_wire_source_computation_schema()).validate(calculation | {"input_selection": None, "quantity_basis": None})
    data = _wire_atom(dict(subject="受试者", attribute="审核值", source_term="审核值",
        comparator="gte", value=7, unit="分", negated=False, semantic_proposition=None,
        observation_policy=None, repeat_scheme=None,
        source_locator={"source_clauses": CLAUSES}, requires_professional_judgment=False,
        source_computation=calculation), shape="scalar")
    assert data["source_computation"] == calculation
    atom = predicate()
    store = ArtifactStore(resolve_data_paths(tmp_path / "data"))
    saved = store.put("evaluation_manifest", atom.model_dump_json().encode("utf-8"))
    restored = AtomicPredicate.model_validate_json(store.read(saved.storage_ref))
    assert restored == atom
    component = RuleComponent(rule_component_id="c", parent_rule_id="r", display_code="IN-01a",
        title="审核值", expression=AtomicExpression(predicate=restored))
    logic = _logic_payload(None, component, None)
    assert logic["predicate"]["source_computation"] == calculation
    assert json.loads(restored.model_dump_json())["source_clauses"] == CLAUSES


@pytest.mark.parametrize("path,value", [
    (("operator_ref", "statement_index"), 2),
    (("operator_ref", "quote"), "合计"),
    (("input_refs", 0, "quote"), "最后一次记录"),
    (("declared_input_count", "value"), 4),
    (("max_missing_count", "value"), 2),
    (("missing_ref", "statement_index"), 0),
    (("operator_ref", "statement_index"), False),
    (("operator_ref", "statement_index"), "0"),
    (("max_missing_count", "value"), True),
    (("max_missing_count", "value"), "1"),
])
def test_invented_source_index_input_operation_or_count_is_rejected(path, value):
    data = computation()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        predicate(source_computation=data)


@pytest.mark.parametrize("updates", [
    dict(comparator="exists", value=None, unit=None),
    dict(requires_professional_judgment=True), dict(semantic_proposition="已完成计算"),
    dict(value=True),
])
def test_computation_cannot_become_an_exists_obligation_or_professional_judgment(updates):
    with pytest.raises(ValidationError):
        predicate(**updates)


def test_unqualified_calculation_is_technical_gap_not_patient_missing_or_judgment():
    atom = AtomicExpression(predicate=predicate())
    component = RuleComponent(rule_component_id="c", parent_rule_id="r", display_code="IN-01a",
                              title="审核值", expression=atom)
    context = evaluation_context()
    for unverified in (frozenset(), frozenset({"p-computation"})):
        result = evaluate_component(component, context, predicate_fact_ids={"p-computation": []},
                                    unverified_predicate_ids=unverified)
        assert result.trigger.truth == TruthValue.UNKNOWN
        assert result.trigger.reason_codes == ["source_computation_operands_unverified"]
        gaps = derive_gate_gap_types(component=component, evaluation=result,
            episode_stage=ReviewStage.SCREENING, expectations=[], conflict_groups=[])
        assert gaps == {GapType.CALCULATION_CAPABILITY_UNAVAILABLE}
        assert ACTION_CONTENT[next(iter(gaps))][0] == ActionTarget.SPONSOR_MEDICAL_OR_PROJECT
    assert evaluate_expression(atom, context).truth == TruthValue.UNKNOWN


def test_unknown_calculation_does_not_freeze_an_independent_definitive_branch():
    unknown = AtomicExpression(predicate=predicate())
    # An independently false comparison suffices to disprove an ALL condition.
    from tests.v2.test_contract_logic import clinical_fact
    fact = clinical_fact(fact_id="f", fact_type="laboratory.other", value=1, unit="分",
                         certainty=1, evidence_span_ids=["s"], polarity="affirmed")
    other = AtomicExpression(predicate=AtomicPredicate(predicate_id="other", subject="laboratory",
        attribute="other", comparator="gt", value=10, unit="分"))
    tree = LogicalExpression(operator=LogicalOperator.ALL, children=[unknown, other])
    assert evaluate_expression(tree, evaluation_context(facts=[fact])).truth == TruthValue.FALSE


def test_semantics_preserving_clause_layout_remaps_refs_without_guessing_counts():
    data = computation()
    data["operator_ref"]["statement_index"] = 1
    data["input_refs"][0]["statement_index"] = 1
    data["declared_input_count"]["source"]["statement_index"] = 1
    data["missing_ref"]["statement_index"] = 0
    data["max_missing_count"]["source"]["statement_index"] = 0
    changed = predicate(source_clauses=list(reversed(CLAUSES)), source_computation=data)
    assert changed.source_computation.operator == "mean"
    assert changed.source_computation.declared_input_count.value == 3
    broken = copy.deepcopy(data)
    broken["input_refs"][0]["statement_index"] = 0
    with pytest.raises(ValidationError):
        predicate(source_clauses=list(reversed(CLAUSES)), source_computation=broken)


@pytest.mark.parametrize("number_text,value", [("4", 4), ("四", 4), ("４", 4)])
def test_explicit_source_total_uses_number_token_and_local_input_scope(number_text, value):
    clause = f"选择末尾三次及本节点一次记录（共{number_text}个）的均值。"
    data = computation() | {
        "operator_ref": {"statement_index": 0, "quote": "均值"},
        "input_refs": [{"statement_index": 0, "quote": clause}],
        "missing_policy": "not_specified", "missing_ref": None, "max_missing_count": None,
        "declared_input_count": {"value": value, "number_text": number_text,
            "source": {"statement_index": 0, "quote": f"共{number_text}个"}},
    }
    atom = predicate(source_clauses=[clause], source_computation=data)
    assert atom.source_computation.declared_input_count.value == 4
    assert evaluate_expression(AtomicExpression(predicate=atom), evaluation_context()).truth == TruthValue.UNKNOWN
    for invalid in (
        {"number_text": f"共{number_text}个"},
        {"source": {"statement_index": 3, "quote": f"共{number_text}个"}},
        {"source": {"statement_index": 0, "quote": "末尾三次及本节点一次"}},
    ):
        changed = copy.deepcopy(data)
        changed["declared_input_count"].update(invalid)
        with pytest.raises(ValidationError):
            predicate(source_clauses=[clause], source_computation=changed)


def test_source_count_schema_explains_local_refs_without_changing_values():
    count = _wire_source_computation_schema()["anyOf"][0]["properties"]["declared_input_count"]["anyOf"][0]
    assert "本条件" in count["properties"]["source"]["properties"]["statement_index"]["description"]
    assert "仅原文数词" in count["properties"]["number_text"]["description"]


def test_quoted_operator_is_not_semantic_approval_or_numerical_evaluation():
    data = computation()
    data["operator"] = "sum"
    # Binding proves where a proposal came from, not whether "sum" means "mean".
    atom = AtomicExpression(predicate=predicate(source_computation=data))
    result = evaluate_expression(atom, evaluation_context())
    assert result.truth == TruthValue.UNKNOWN
    assert result.reason_codes == ["source_computation_operands_unverified"]


def test_direct_arithmetic_comparison_cannot_bypass_unqualified_definition():
    for value in (Fraction(8), Fraction(6)):
        result = evaluate_calculated_numeric_value(predicate(), value=value, unit="分")
        assert result.truth == TruthValue.UNKNOWN
        assert result.reason_codes == ["source_computation_operands_unverified"]
    ordinary = predicate(source_computation=None)
    assert evaluate_calculated_numeric_value(ordinary, value=Fraction(8), unit="分").truth == TruthValue.TRUE
    assert evaluate_calculated_numeric_value(ordinary, value=Fraction(6), unit="分").truth == TruthValue.FALSE


def test_definition_prose_does_not_donate_computation_to_numeric_sibling(tmp_path):
    definition = AtomicPredicate(predicate_id="definition", subject="受试者", attribute="审核值定义",
        comparator="exists", semantic_proposition="按最近三次记录求均值", source_clause=CLAUSES[0])
    threshold = predicate(source_computation=None)
    store = ArtifactStore(resolve_data_paths(tmp_path / "data"))
    before = definition.model_dump_json()
    saved = store.put("evaluation_manifest", threshold.model_dump_json().encode())
    restored = AtomicPredicate.model_validate_json(store.read(saved.storage_ref))
    assert restored.source_computation is None
    assert evaluate_expression(AtomicExpression(predicate=restored), evaluation_context()).truth == TruthValue.UNKNOWN
    with pytest.raises(ValidationError):
        AtomicPredicate.model_validate(definition.model_dump(mode="json") | {"source_computation": computation()})
    attached = AtomicPredicate.model_validate(restored.model_dump(mode="json") | {"source_computation": computation()})
    result = evaluate_expression(AtomicExpression(predicate=attached), evaluation_context())
    assert result.truth == TruthValue.UNKNOWN
    assert result.reason_codes == ["source_computation_operands_unverified"]
    assert definition.model_dump_json() == before


@pytest.mark.parametrize("extra", [
    {"verified": True}, {"operand_filter": "所有记录"}, {"max_missing": 1},
])
def test_unknown_nested_computation_fields_are_rejected_not_erased(extra):
    with pytest.raises(ValidationError):
        predicate(source_computation=computation() | extra)


def test_hydrated_atom_identity_changes_only_with_declared_calculation():
    wire = dict(subject="受试者", attribute="审核值", source_term="审核值",
                comparator="gte", value=7, unit="分", negated=False, semantic_proposition=None,
                observation_policy=None, repeat_scheme=None,
                source_locator={"source_clauses": CLAUSES}, requires_professional_judgment=False)

    def identity(data):
        atom = _wire_atom(data, shape="scalar")
        key = _canonical_wire_atom_key("scalar", atom)
        return _system_predicate_id(identity_prefix="synthetic", group_key="group", atom_key=key)

    assert identity(wire) == identity(wire | {"source_computation": None})
    with_definition = identity(wire | {"source_computation": computation()})
    assert with_definition != identity(wire)
    assert with_definition == identity(wire | {"source_computation": computation()})
    changed = computation() | {"operator": "sum"}
    assert identity(wire | {"source_computation": changed}) != with_definition


def input_selection(**updates):
    return dict(mode="latest_n", source={"statement_index": 0, "quote": "最近三次记录"},
                ordering_basis="unresolved", ordering_ref=None, window_refs=[]) | updates


def test_explicit_selection_hydrates_and_preserves_unknown_date_role(tmp_path):
    calculation = computation() | {"input_selection": input_selection()}
    Draft202012Validator(_wire_source_computation_schema()).validate(calculation | {"quantity_basis": None})
    hydrated = _wire_atom(dict(subject="受试者", attribute="审核值", source_term="审核值",
        comparator="gte", value=7, unit="分", negated=False, semantic_proposition=None,
        observation_policy=None, repeat_scheme=None, source_locator={"source_clauses": CLAUSES},
        requires_professional_judgment=False, source_computation=calculation), shape="scalar")
    assert hydrated["source_computation"] == calculation
    atom = predicate(source_computation=calculation)
    store = ArtifactStore(resolve_data_paths(tmp_path / "data"))
    saved = store.put("evaluation_manifest", atom.model_dump_json().encode())
    restored = AtomicPredicate.model_validate_json(store.read(saved.storage_ref))
    assert restored.source_computation.model_dump(mode="json") == calculation
    component = RuleComponent(rule_component_id="c", parent_rule_id="r", display_code="IN-01a",
        title="审核值", expression=AtomicExpression(predicate=restored))
    assert _logic_payload(None, component, None)["predicate"]["source_computation"] == calculation
    assert evaluate_expression(AtomicExpression(predicate=restored), evaluation_context()).reason_codes == ["source_computation_operands_unverified"]
    legacy = predicate(source_computation=computation() | {"input_selection": None})
    assert legacy.source_computation.model_dump(mode="json") == computation()


@pytest.mark.parametrize("ordering_basis", [None, "unresolved"])
def test_unresolved_selection_preserves_source_and_stays_unqualified(tmp_path, ordering_basis):
    calculation = computation() | {"input_selection": input_selection(
        mode="unresolved", ordering_basis=ordering_basis,
        window_refs=[{"statement_index": 0, "quote": "最近三次记录"}],
    )}
    original = predicate(source_computation=calculation)
    store = ArtifactStore(resolve_data_paths(tmp_path / "data"))
    saved = store.put("evaluation_manifest", original.model_dump_json().encode())
    restored = AtomicPredicate.model_validate_json(store.read(saved.storage_ref))
    assert restored.source_computation.model_dump(mode="json") == calculation
    assert restored.source_clauses == CLAUSES
    component = RuleComponent(
        rule_component_id="c", parent_rule_id="r", display_code="IN-01a", title="审核值",
        expression=AtomicExpression(predicate=restored),
    )
    frozen = _frozen_component(component, Rule(
        rule_id="r", official_code="IN-01", kind=RuleKind.INCLUSION,
        source_text="".join(CLAUSES), study_phase=StudyPhase.PHASE_III, components=[component],
    ))
    assert frozen.trigger_predicates[0].predicate.source_computation == restored.source_computation
    result = evaluate_expression(frozen.expression, evaluation_context())
    assert result.truth == TruthValue.UNKNOWN
    assert result.reason_codes == ["source_computation_operands_unverified"]


@pytest.mark.parametrize("period,definition", [
    ("每周", "1单位=200 mL甲液或50 mL乙液"),
    ("每7天", "1单位=200 mL甲液或50 mL乙液"),
    ("per month", "one unit equals 30 mL of material A"),
])
def test_period_amount_basis_survives_schema_hydration_save_and_consumer(tmp_path, period, definition):
    clause = f"{period}数量超过9单位（{definition}）。"
    raw = dict(operator="other", operator_ref={"statement_index": 0, "quote": period},
        input_refs=[{"statement_index": 0, "quote": clause}], missing_policy="not_specified",
        input_selection={"mode": "unresolved", "source": {"statement_index": 0, "quote": period}},
        quantity_basis={"period_ref": {"statement_index": 0, "quote": period},
            "period_partition": "unresolved", "partition_ref": None,
            "unit_equivalence_refs": [{"statement_index": 0, "quote": definition}]})
    atom = predicate(source_clauses=[clause], source_computation=raw, value=9, unit="单位")
    schema = json.loads(_compact_schema())
    Draft202012Validator(schema["$defs"]["SourceComputation"] | {"$defs": schema["$defs"]}).validate(raw)
    wire = _wire_atom(dict(subject="受试者", attribute="数量", source_term="数量",
        comparator="gt", value=9, unit="单位", source_locator={"source_clauses": [clause]},
        source_computation=raw, negated=False, semantic_proposition=None,
        observation_policy=None, repeat_scheme=None, requires_professional_judgment=False), shape="scalar")
    assert wire["source_computation"] == SourceComputation.model_validate(raw).model_dump(mode="json")
    artifacts = ArtifactStore(resolve_data_paths(tmp_path / "data"))
    saved = artifacts.put("evaluation_manifest", atom.model_dump_json().encode())
    restored = AtomicPredicate.model_validate_json(artifacts.read(saved.storage_ref))
    assert restored == atom and restored.value == 9
    basis = restored.source_computation.quantity_basis
    assert basis.period_ref.quote == period and basis.unit_equivalence_refs[0].quote == definition
    assert basis.period_partition == "unresolved"
    pending = evaluate_expression(AtomicExpression(predicate=restored), evaluation_context())
    assert pending.truth == TruthValue.UNKNOWN
    assert pending.reason_codes == ["computation_period_quantity_unsupported"]
    assert evaluate_calculated_numeric_value(restored, value=Fraction(10), unit="单位").truth == TruthValue.UNKNOWN
    changed = raw | {"quantity_basis": None}
    assert predicate(source_clauses=[clause], source_computation=changed).model_dump_json() != atom.model_dump_json()


@pytest.mark.parametrize("case", ["foreign_period", "foreign_conversion", "wrong_index", "borrow_input", "invent_partition", "duplicate_conversion"])
def test_period_quantity_cannot_borrow_sources_or_invent_partition(case):
    clause = "每周数量超过9单位（1单位=200 mL甲液）。"
    basis = dict(period_ref={"statement_index": 0, "quote": "每周"},
        period_partition="unresolved", partition_ref=None,
        unit_equivalence_refs=[{"statement_index": 0, "quote": "1单位=200 mL甲液"}])
    raw = dict(operator="other", operator_ref={"statement_index": 0, "quote": "每周"},
        input_refs=[{"statement_index": 0, "quote": clause}], missing_policy="not_specified",
        quantity_basis=basis)
    if case == "foreign_period":
        basis["period_ref"]["quote"] = "每月"
    elif case == "foreign_conversion":
        basis["unit_equivalence_refs"][0]["quote"] = "1单位=20 mL甲液"
    elif case == "wrong_index":
        basis["period_ref"]["statement_index"] = 1
    elif case == "borrow_input":
        raw["input_refs"] = [{"statement_index": 0, "quote": "数量超过9单位"}]
    elif case == "invent_partition":
        basis["period_partition"] = "source_defined"
    else:
        basis["unit_equivalence_refs"] *= 2
    with pytest.raises(ValidationError):
        predicate(source_clauses=[clause], source_computation=raw)


def test_period_basis_omission_preserves_saved_legacy_identity():
    raw = computation()
    old = SourceComputation.model_validate(raw).model_dump(mode="json")
    assert old == raw
    assert SourceComputation.model_validate(raw | {"quantity_basis": None}).model_dump(mode="json") == old


@pytest.mark.parametrize("truth", [TruthValue.TRUE, TruthValue.FALSE, TruthValue.UNKNOWN])
def test_period_quantity_consumer_does_not_accept_a_self_sealed_calculation(truth):
    from app.domain.contracts.evaluation_result import ComputationAtomEvaluation, EvaluationResult
    from app.domain.publication import canonical_hash
    from app.services.computation_atom_calculation import computation_result_note

    calculation = computation() | {"quantity_basis": {
        "period_ref": {"statement_index": 0, "quote": "最近三次记录"},
        "period_partition": "unresolved", "partition_ref": None, "unit_equivalence_refs": []}}
    # This is a typed proposal, not semantic proof that the quote is a period.
    atom = AtomicExpression(predicate=predicate(source_computation=calculation))
    component = RuleComponent(rule_component_id="c", parent_rule_id="r", display_code="IN-01a",
        title="审核值", expression=atom)
    context = evaluation_context()
    result = EvaluationResult(truth=truth, reason_codes=(
        ["computation_period_quantity_unsupported"] if truth == TruthValue.UNKNOWN else []))
    resolution = {"input_qualification": {"fact_ids": [], "input_set_qualified": True, "reason_codes": []},
        "exact_value": {"numerator": "10", "denominator": "1"}, "result": result.model_dump(mode="json")}
    receipt = ComputationAtomEvaluation(context_sha256=canonical_hash(context.model_dump(mode="json")),
        atom_sha256=canonical_hash(atom.model_dump(mode="json")), resolution_sha256=canonical_hash(resolution),
        source_fact_ids=[], result=result, resolution=resolution)
    if truth != TruthValue.UNKNOWN:
        with pytest.raises(ValueError, match="计算结果不能跨越"):
            evaluate_component(component, context, predicate_fact_ids={"p-computation": []},
                computation_evaluations={"p-computation": receipt})
    else:
        evaluation = evaluate_component(component, context, predicate_fact_ids={"p-computation": []},
            computation_evaluations={"p-computation": receipt})
        assert evaluation.trigger.truth == TruthValue.UNKNOWN
        assert derive_gate_gap_types(component=component, evaluation=evaluation,
            episode_stage=ReviewStage.SCREENING, expectations=[], conflict_groups=[]) == {
                GapType.CALCULATION_CAPABILITY_UNAVAILABLE}
        assert "相关计算尚未接通" in computation_result_note(receipt)


@pytest.mark.parametrize("updates", [
    {"ordering_basis": "collection_time"},
    {"ordering_ref": {"statement_index": 0, "quote": "最近三次记录"}},
    {"window_refs": [{"statement_index": 1, "quote": CLAUSES[1]}]},
])
def test_unresolved_selection_does_not_authorize_ordering_or_foreign_windows(updates):
    with pytest.raises(ValidationError):
        predicate(source_computation=computation() | {"input_selection": input_selection(
            mode="unresolved", **updates,
        )})


@pytest.mark.parametrize("selection, count", [
    (input_selection(ordering_basis=None), 3),
    (input_selection(ordering_basis="report_time"), 3),
    (input_selection(ordering_ref={"statement_index": 0, "quote": "最近"}), 3),
    (input_selection(mode="all"), 3),
    (input_selection(mode="single", ordering_basis=None), 3),
    (input_selection(), None),
    (input_selection(window_refs=[{"statement_index": 1, "quote": "缺失记录不填补"}]), 3),
    (input_selection(source={"statement_index": 1, "quote": "缺失记录不填补"}), 3),
])
def test_selection_cannot_invent_sorting_borrow_window_or_replace_input_count(selection, count):
    data = computation() | {"input_selection": selection}
    if count is None:
        data["declared_input_count"] = None
    with pytest.raises(ValidationError):
        predicate(source_computation=data)


def test_date_role_source_preserved_and_changed_meaning_changes_identity():
    clauses = ["按采样时间取最近三次记录的均值，本次审核值至少为7分。", CLAUSES[1]]
    data = computation()
    data["input_refs"][0]["quote"] = "按采样时间取最近三次记录"
    data["input_selection"] = input_selection(ordering_basis="collection_time",
        ordering_ref={"statement_index": 0, "quote": "采样时间"})
    original = predicate(source_clauses=clauses, source_computation=data)
    changed = copy.deepcopy(data)
    changed["input_selection"]["ordering_basis"] = "report_time"
    other = predicate(source_clauses=clauses, source_computation=changed)
    assert original.model_dump(mode="json") != other.model_dump(mode="json")
    # A matching quote proves provenance, not that the author's interpretation is correct.
    for atom in (original, other):
        assert evaluate_expression(AtomicExpression(predicate=atom), evaluation_context()).truth == TruthValue.UNKNOWN


@pytest.mark.parametrize("mode, source_text, count", [
    ("all", "所规定范围内全部记录", None),
    ("single", "所规定的一次记录", (1, "一")),
    ("earliest_n", "最早三次记录", (3, "三")),
])
def test_normal_selection_modes_preserve_source_without_evaluating(mode, source_text, count):
    clauses = [f"取{source_text}的均值，本次审核值至少为7分。", CLAUSES[1]]
    data = computation()
    data["input_refs"] = [{"statement_index": 0, "quote": source_text}]
    data["declared_input_count"] = None if count is None else {
        "value": count[0], "number_text": count[1], "source": {"statement_index": 0, "quote": source_text},
    }
    data["input_selection"] = input_selection(mode=mode, source={"statement_index": 0, "quote": source_text},
        ordering_basis="unresolved" if mode == "earliest_n" else None)
    atom = predicate(source_clauses=clauses, source_computation=data)
    assert atom.source_computation.input_selection.mode == mode
    assert evaluate_expression(AtomicExpression(predicate=atom), evaluation_context()).truth == TruthValue.UNKNOWN


def test_frozen_binding_producer_preserves_selection_and_rejects_old_identity():
    calculation = computation() | {"input_selection": input_selection()}
    atom = predicate(source_computation=calculation)
    component = RuleComponent(rule_component_id="c", parent_rule_id="r", display_code="IN-01a",
        title="审核值", expression=AtomicExpression(predicate=atom))
    rule = Rule(rule_id="r", official_code="IN-01", kind=RuleKind.INCLUSION,
        source_text="".join(CLAUSES), study_phase=StudyPhase.PHASE_III, components=[component])
    frozen = _frozen_component(component, rule)
    restored = FrozenRuleComponent.model_validate_json(frozen.model_dump_json())
    original = restored.trigger_predicates[0]
    assert original.predicate.source_computation.model_dump(mode="json") == calculation
    assert restored.expression.predicate == atom
    # A different selection must not borrow the original frozen predicate identity.
    changed = calculation | {"input_selection": input_selection(mode="earliest_n")}
    stale = original.model_dump(mode="json")
    stale["predicate"] = predicate(source_computation=changed).model_dump(mode="json")
    with pytest.raises(ValidationError):
        FrozenPredicateIdentity.model_validate(stale)
    assert evaluate_expression(restored.expression, evaluation_context()).reason_codes == ["source_computation_operands_unverified"]
