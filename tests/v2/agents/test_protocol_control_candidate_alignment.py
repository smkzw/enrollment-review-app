"""Source-to-candidate alignment must survive the product save/read boundary."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.domain.contracts.enums import Comparator
from app.agents.protocol_control_candidate_alignment import (
    SOURCE_CANDIDATE_ALIGNMENT_VERSION,
    SourceCandidateAlignment,
    _split_obligations_cover_source,
    candidate_alignment_response_format,
    bind_candidate_alignment,
    bind_partial_candidate_alignment,
    validate_candidate_alignment,
    build_candidate_alignment_prompt,
    reusable_proven_alignment_items,
)
from app.agents.protocol_control_deconstructor import (
    ProtocolControlAgentAttempt,
    ProtocolControlAgentRunResult,
    hydrate_protocol_control_agent_output,
    hydrated_source_coverage_indexes,
    source_statement_coverage,
)
from app.agents.protocol_control_source_interpretation import (
    SOURCE_INTERPRETATION_VERSION,
    SOURCE_TARGET_REVIEW_VERSION,
    SourceInterpretation,
    SourceTargetReview,
    SourceTargetReviewValidationError,
    can_recheck_source_scope_question,
    build_source_scope_question_prompt,
    build_source_scope_correction_prompt,
    apply_source_scope_question_recheck,
    simple_visit_action_preserves_time,
)
from app.domain.contracts.protocol_controls import ControlObligationKind
from app.domain.contracts.protocol_controls import KnownWorkflowStageTarget
from app.domain.contracts.protocol_controls import StructureUnitKind
from app.domain.contracts.enums import ReviewStage
from app.services.protocol_control_execution import _validate_saved_source_review
from tests.v2.protocols.test_slice58c_control_deconstructor import (
    _batch, _candidate, _candidate_for_second_unit, _wire, _wire_with_two_candidates,
    _native_visit_candidate_material,
)


def _native_action_material():
    batch, source, wire = _native_visit_candidate_material(label="材料分发及回收")
    atom = wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    atom.statement = "在基线期 V2 D0 完成材料分发及回收"
    atom.evaluation = atom.evaluation.model_copy(update={"proposition": atom.statement})
    source.statements[0].decision_functions = ["action"]
    coverage = source_statement_coverage(batch, source, wire)
    coverage[0] = coverage[0].model_copy(update={
        "status": "candidate_linked", "action_candidate_indexes": [0], "candidate_indexes": [0],
    })
    alignment = SourceCandidateAlignment.model_validate({
        "version": SOURCE_CANDIDATE_ALIGNMENT_VERSION,
        "items": [{"statement_index": 0, "candidate_index": 0,
                   "decision": "fully_expressed", "source_excerpt": source.statements[0].quoted_text,
                   "candidate_atom_quotes": [atom.statement], "unresolved_dimensions": []}],
    })
    return batch, source, wire, coverage, alignment


def test_alignment_prompt_includes_only_actual_candidate_source_closure():
    batch, source, wire, _, _ = _native_action_material()
    prompt = build_candidate_alignment_prompt(batch, source, wire, [(0, 0)])
    data = json.loads(prompt.split("待核对应：", 1)[1])
    assert [unit["structure_unit_id"] for unit in data[0]["candidate_source_closure"]] == wire.candidate_drafts[0].source_structure_unit_ids
    assert "兄弟要求须各自处置" in prompt
    wire.candidate_drafts[0].source_structure_unit_ids.append("outside-scope")
    with pytest.raises(ValueError, match="越出本批"):
        build_candidate_alignment_prompt(batch, source, wire, [(0, 0)])


def _mixed_validity_alignment_material():
    from tests.v2.protocols.test_slice58c_control_deconstructor import (
        _two_independent_candidate_linked_alignment_material,
    )
    batch, source, _, wire, payload = _two_independent_candidate_linked_alignment_material()
    payload["items"][1]["decision"] = "fully_expressed"
    payload["items"][1]["unresolved_dimensions"] = []
    payload["items"][1]["candidate_atom_quotes"] = ["未由该条原文支持的动作"]
    alignment = SourceCandidateAlignment.model_validate(payload)
    return batch, source, wire, source_statement_coverage(batch, source, wire), alignment


def test_partial_alignment_preserves_actual_response_and_good_sibling_only():
    batch, source, wire, coverage, alignment = _mixed_validity_alignment_material()
    raw = alignment.model_dump_json(exclude={"proofs"})
    kept, failures = bind_partial_candidate_alignment(
        batch, source, coverage, wire, alignment, raw, [(0, 0), (1, 1)],
    )
    assert [item.statement_index for item in kept.items] == [0]
    assert len(failures) == 1 and failures[0]["statement_ids"] == [1]
    assert failures[0]["candidate_indexes"] == [1]
    assert failures[0]["source_refs"] == batch.owned_units[1].source_span_ids
    assert kept.proofs[0].response_text == raw
    assert len(json.loads(kept.proofs[0].response_text)["items"]) == 2
    restored = SourceCandidateAlignment.model_validate_json(kept.model_dump_json())
    assert reusable_proven_alignment_items(batch, source, coverage, wire, restored) == kept.items
    wire.candidate_drafts[0].title += "变更"
    assert reusable_proven_alignment_items(batch, source, coverage, wire, restored) == []


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "outside", "source", "changed_raw", "proof"])
def test_partial_alignment_rejects_entire_identity_invalid_response(mutation):
    batch, source, wire, coverage, alignment = _mixed_validity_alignment_material()
    expected = [(0, 0), (1, 1)]
    if mutation == "duplicate":
        alignment.items.append(alignment.items[0].model_copy(deep=True))
    elif mutation == "missing":
        alignment.items.pop()
    elif mutation == "outside":
        alignment.items[1].candidate_index = 99
    elif mutation == "source":
        alignment.items[1].source_excerpt = source.statements[0].quoted_text
    raw = alignment.model_dump_json(exclude={"proofs"})
    if mutation == "changed_raw":
        alignment.items[0].decision = "uncertain"
        alignment.items[0].unresolved_dimensions = ["不明"]
    elif mutation == "proof":
        payload = json.loads(raw)
        payload["proofs"] = [{"statement_index": 0, "candidate_index": 0,
            "source_sha256": "a" * 64, "candidate_sha256": "b" * 64,
            "response_sha256": "c" * 64, "response_text": raw}]
        raw = json.dumps(payload)
    with pytest.raises(ValueError):
        bind_partial_candidate_alignment(batch, source, coverage, wire, alignment, raw, expected)


def _conditioned_action_material(prefix="已完成核查者"):
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentWireConditionDnf
    from tests.v2.protocols.test_slice58c_control_deconstructor import _evaluation
    batch, source, wire, coverage, alignment = _native_action_material()
    text = f"{prefix}，领取材料，回收材料"
    unit, statement = batch.owned_units[0], source.statements[0]
    unit.table_context = None
    unit.unit_kind = StructureUnitKind.PARAGRAPH
    unit.source_ref = "body.p1"
    unit.member_source_refs = [unit.source_ref]
    unit.member_texts = [text]
    unit.source_span_ids = unit.source_span_ids[:1]
    unit.member_source_span_ids = [list(unit.source_span_ids)]
    unit.excerpt = statement.quoted_text = text
    statement.scope_quote = None
    statement.time_words = []
    candidate = wire.candidate_drafts[0]
    for node in candidate.review_node_bindings:
        node.scope_citation = None
    group = candidate.obligation_expression.groups[0]
    original = group.atoms[0]
    group.atoms = [original.model_copy(deep=True, update={"statement": part,
                   "source_span_ids": list(unit.source_span_ids), "source_excerpts": [part]})
                   for part in ("领取材料", "回收材料")]
    for atom in group.atoms:
        atom.evaluation = type(atom.evaluation).model_validate(
            _evaluation(atom.statement, unit.source_span_ids[0], atom.source_excerpts[0]))
    condition = {"statement": prefix, "evaluation": _evaluation(prefix, unit.source_span_ids[0], text),
        "source_span_ids": list(unit.source_span_ids), "source_excerpts": [text],
        "time_constraint": None, "requires_professional_judgment": False}
    unit.excerpt += "。条件甲或条件乙。"
    unit.member_texts = [unit.excerpt]
    branches = []
    for label in ("条件甲", "条件乙"):
        branches.append({"atoms": [condition, {**condition, "statement": label,
            "source_excerpts": [label], "evaluation": _evaluation(label, unit.source_span_ids[0], label)}]})
    candidate.trigger_expression = ProtocolControlAgentWireConditionDnf.model_validate({"groups": branches})
    group.applies_to_trigger_branch_indexes = [0, 1]
    alignment.items[0].source_excerpt = text
    alignment.items[0].candidate_atom_quotes = [prefix, "领取材料", "回收材料"]
    return batch, source, wire, coverage, alignment


def test_alignment_prompt_offers_only_current_statement_quotes_keeps_context():
    batch, source, wire, coverage, alignment = _conditioned_action_material()
    prompt = build_candidate_alignment_prompt(batch, source, wire, [(0, 0)])
    selected = json.loads(prompt.split("待核对应：", 1)[1])[0]
    assert selected["allowed_candidate_atom_quotes"] == ["已完成核查者", "领取材料", "回收材料"]
    assert "条件甲" in json.dumps(selected["candidate"], ensure_ascii=False)
    assert "条件乙" in selected["candidate_source_closure"][0]["excerpt"]
    validate_candidate_alignment(batch, source, coverage, wire, alignment)
    bound = bind_candidate_alignment(batch, source, coverage, wire, alignment,
        alignment.model_dump_json(exclude={"proofs"}))
    assert len(reusable_proven_alignment_items(batch, source, coverage, wire, bound)) == 1


def _scoped_sibling_material():
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentWireConditionDnf
    from tests.v2.protocols.test_slice58c_control_deconstructor import _evaluation
    batch, source, wire, coverage, alignment = _conditioned_action_material()
    unit, statement = batch.owned_units[0], source.statements[0]
    text = "结果有效者，记录处理日期"
    unit.excerpt += "。" + text
    unit.member_texts = [unit.excerpt]
    sibling = statement.model_copy(deep=True, update={"quoted_text": text})
    source.statements.append(sibling)
    candidate = wire.candidate_drafts[0]
    base_condition = candidate.trigger_expression.groups[0].atoms[0].model_copy(deep=True)
    base_condition.source_excerpts = ["已完成核查者"]
    base_condition.evaluation = type(base_condition.evaluation).model_validate(
        _evaluation(base_condition.statement, unit.source_span_ids[0], "已完成核查者"))
    sibling_condition = base_condition.model_copy(deep=True, update={"statement": "结果有效者",
        "source_excerpts": ["结果有效者"]})
    sibling_condition.evaluation = type(sibling_condition.evaluation).model_validate(
        _evaluation(sibling_condition.statement, unit.source_span_ids[0], "结果有效者"))
    candidate.trigger_expression = ProtocolControlAgentWireConditionDnf.model_validate({"groups": [
        {"atoms": [base_condition]}, {"atoms": [base_condition, sibling_condition]},
    ]})
    group = candidate.obligation_expression.groups[0]
    group.applies_to_trigger_branch_indexes = [0]
    atom = group.atoms[0].model_copy(deep=True, update={"statement": "记录处理日期",
        "source_excerpts": ["记录处理日期"]})
    atom.evaluation = type(atom.evaluation).model_validate(
        _evaluation(atom.statement, unit.source_span_ids[0], atom.statement))
    candidate.obligation_expression.groups.append(group.model_copy(deep=True,
        update={"atoms": [atom], "applies_to_trigger_branch_indexes": [1]}))
    coverage.append(coverage[0].model_copy(update={"statement_index": len(source.statements) - 1}))
    return batch, source, wire, coverage, alignment


@pytest.mark.parametrize("change", [None, "missing_sibling_source", "unresolved_sibling",
    "unscoped_group", "same_binding", "wrong_trigger", "unknown_atom", "exception",
    "missing_sibling_coverage", "unlinked_sibling", "wrong_sibling_candidate",
    "shared_source_quote"])
def test_scoped_source_sibling_does_not_replace_current_requirement(change):
    batch, source, wire, coverage, alignment = _scoped_sibling_material()
    candidate = wire.candidate_drafts[0]
    if change == "missing_sibling_source":
        source.statements.pop()
    elif change == "unresolved_sibling":
        source.statements[-1].unresolved = ["原文范围未明"]
    elif change == "unscoped_group":
        candidate.obligation_expression.groups[-1].applies_to_trigger_branch_indexes = []
    elif change == "same_binding":
        candidate.obligation_expression.groups[-1].applies_to_trigger_branch_indexes = [0]
    elif change == "wrong_trigger":
        candidate.trigger_expression.groups[0].atoms[0].statement = "尚未完成核查者"
    elif change == "unknown_atom":
        atom = candidate.obligation_expression.groups[-1].atoms[0].model_copy(deep=True,
            update={"statement": "自行增加的要求", "source_excerpts": ["自行增加的要求"]})
        candidate.obligation_expression.groups[-1].atoms.append(atom)
    elif change == "exception":
        candidate.exception_expression = candidate.trigger_expression.model_copy(deep=True)
    elif change == "missing_sibling_coverage":
        coverage.pop()
    elif change == "unlinked_sibling":
        coverage[-1].status = "unresolved"
    elif change == "wrong_sibling_candidate":
        coverage[-1].action_candidate_indexes = [1]
    elif change == "shared_source_quote":
        candidate.obligation_expression.groups[-1].atoms[0].source_excerpts = [
            batch.owned_units[0].excerpt]
    if change:
        with pytest.raises(ValueError):
            validate_candidate_alignment(batch, source, coverage, wire, alignment)
    else:
        validate_candidate_alignment(batch, source, coverage, wire, alignment)
        proof = bind_candidate_alignment(batch, source, coverage, wire, alignment,
            alignment.model_dump_json(exclude={"proofs"}))
        restored = SourceCandidateAlignment.model_validate_json(proof.model_dump_json())
        assert len(reusable_proven_alignment_items(batch, source, coverage, wire, restored)) == 1
        source.statements[-1].quoted_text = "结果有效者，不得记录处理日期"
        assert reusable_proven_alignment_items(batch, source, coverage, wire, restored) == []


def _repeat_count_material():
    from app.domain.contracts.repeat_scheme import RepeatScheme
    from tests.v2.protocols.test_slice58c_control_deconstructor import _evaluation
    batch, source, wire, coverage, alignment = _conditioned_action_material()
    unit, statement = batch.owned_units[0], source.statements[0]
    text = "本次节点允许复查3次"
    unit.excerpt = statement.quoted_text = text
    unit.member_texts = [text]
    statement.decision_functions = ["action"]
    statement.affected_stage = None
    statement.force = "descriptive"
    candidate = wire.candidate_drafts[0]
    candidate.trigger_expression = None
    group = candidate.obligation_expression.groups[0]
    group.applies_to_trigger_branch_indexes = []
    atom = group.atoms[0].model_copy(deep=True, update={"statement": text,
        "source_excerpts": [text]})
    evaluation = _evaluation(text, unit.source_span_ids[0], text)
    evaluation["repeat_scheme"] = RepeatScheme(
        scope="本次节点的复查", source_span_ids=list(unit.source_span_ids), source_excerpts=[text],
        permission="optional", trigger="unconditional", count_status="specified",
        maximum_repeats=3, count_scope="per_current_episode", time_status="not_specified",
        result_use="not_specified", no_repeat_result_use="unresolved",
    ).model_dump(mode="json")
    atom.evaluation = type(atom.evaluation).model_validate(evaluation)
    group.atoms = [atom]
    alignment.items[0].source_excerpt = text
    alignment.items[0].candidate_atom_quotes = [text]
    return batch, source, wire, coverage, alignment


@pytest.mark.parametrize("change", [None, "wrong_count", "unknown_count", "missing_scheme",
    "wrong_source", "historical_scheme", "threshold", "dose", "frequency", "time_window",
    "event_count", "mandatory_permission"])
def test_source_repeat_count_uses_its_contract_not_a_measurement_predicate(change):
    batch, source, wire, coverage, alignment = _repeat_count_material()
    atom = wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    scheme = atom.evaluation.repeat_scheme
    if change == "wrong_count":
        atom.evaluation = atom.evaluation.model_copy(update={"repeat_scheme": scheme.model_copy(
            update={"maximum_repeats": 4})})
    elif change == "unknown_count":
        atom.evaluation = atom.evaluation.model_copy(update={"repeat_scheme": scheme.model_copy(
            update={"count_status": "unresolved", "maximum_repeats": None, "count_scope": None})})
    elif change == "missing_scheme":
        atom.evaluation = atom.evaluation.model_copy(update={"repeat_scheme": None})
    elif change == "wrong_source":
        atom.evaluation = atom.evaluation.model_copy(update={"repeat_scheme": scheme.model_copy(
            update={"source_span_ids": ["foreign-source"]})})
    elif change == "historical_scheme":
        atom.evaluation = atom.evaluation.model_copy(update={"repeat_scheme": scheme.model_copy(
            update={"version": "repeat-scheme/v3"})})
    elif change == "threshold":
        source.statements[0].decision_functions = ["threshold"]
    elif change == "mandatory_permission":
        atom.evaluation = atom.evaluation.model_copy(update={"repeat_scheme": scheme.model_copy(update={"permission": "required"})})
    elif change in {"dose", "frequency", "time_window", "event_count"}:
        text = {"dose": "本次节点给予3mg", "frequency": "本次节点发生至少3次事件",
                "time_window": "本次节点3天内复查", "event_count": "本次节点发生3次事件"}[change]
        batch.owned_units[0].excerpt = source.statements[0].quoted_text = text
        batch.owned_units[0].member_texts = [text]
        atom.statement = text
        atom.source_excerpts = [text]
        atom.evaluation = atom.evaluation.model_copy(update={"proposition": text,
            "source_excerpts": [text], "repeat_scheme": scheme.model_copy(update={"source_excerpts": [text]})})
        alignment.items[0].source_excerpt = text
        alignment.items[0].candidate_atom_quotes = [text]
    if change:
        with pytest.raises(ValueError):
            validate_candidate_alignment(batch, source, coverage, wire, alignment)
    else:
        validate_candidate_alignment(batch, source, coverage, wire, alignment)
        proof = bind_candidate_alignment(batch, source, coverage, wire, alignment,
            alignment.model_dump_json(exclude={"proofs"}))
        restored = SourceCandidateAlignment.model_validate_json(proof.model_dump_json())
        assert len(reusable_proven_alignment_items(batch, source, coverage, wire, restored)) == 1
        from app.domain.repeat_observation_count import evaluate_repeat_count
        from app.domain.contracts.enums import TruthValue
        assert evaluate_repeat_count(scheme, repeat_group_ids=(),
            qualified_scope="per_current_episode", scope_complete=True).result.truth == TruthValue.TRUE
        assert evaluate_repeat_count(scheme, repeat_group_ids=["a", "b", "c", "d"],
            qualified_scope="per_current_episode", scope_complete=True).result.truth == TruthValue.FALSE
        assert evaluate_repeat_count(scheme, repeat_group_ids=["a"],
            qualified_scope="per_current_episode", scope_complete=False).result.truth == TruthValue.UNKNOWN
        assert scheme.permission == "optional" and scheme.no_repeat_result_use == "unresolved"
        atom.evaluation = atom.evaluation.model_copy(update={"repeat_scheme": scheme.model_copy(
            update={"maximum_repeats": 4})})
        assert reusable_proven_alignment_items(batch, source, coverage, wire, restored) == []


@pytest.mark.parametrize("change", [None, "unknown_scope", "changed_policy", "changed_statement",
    "changed_time", "wrong_count", "missing_scheme", "historical_scheme"])
def test_source_repeat_count_field_repair_preserves_siblings_and_consumer_unknowns(change):
    from app.agents.protocol_control_deconstructor import (
        _merge_obligation_atom_repair, _build_obligation_atom_repair_prompt,
        ProtocolControlAgentWireValidationError,
    )
    batch, source, wire, coverage, alignment = _repeat_count_material()
    atom = wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    good = atom.model_copy(deep=True)
    atom.evaluation = atom.evaluation.model_copy(update={"repeat_scheme": None})
    baseline = wire.model_dump(mode="json")
    prompt = _build_obligation_atom_repair_prompt(batch, baseline, (0, 0, 0), "次数合同缺失",
                                                repeat_scheme_only=True)
    assert "本次只允许补 evaluation.repeat_scheme" in prompt
    if change == "unknown_scope":
        good.evaluation.repeat_scheme.count_scope = "unresolved"
    elif change == "changed_policy":
        good.evaluation = good.evaluation.model_copy(update={"observation_policy":
            good.evaluation.observation_policy.model_copy(update={"mode": "any"})})
    elif change == "changed_statement":
        good.statement = "另一项要求"
    elif change == "changed_time":
        good.evaluation = good.evaluation.model_copy(update={"time_purpose": "unresolved"})
    elif change == "wrong_count":
        good.evaluation.repeat_scheme.maximum_repeats = 4
    elif change == "missing_scheme":
        good.evaluation = good.evaluation.model_copy(update={"repeat_scheme": None})
    elif change == "historical_scheme":
        good.evaluation.repeat_scheme.version = "repeat-scheme/v3"
    raw = json.dumps({"atom": good.model_dump(mode="json")}, ensure_ascii=False)
    if change in {"changed_policy", "changed_statement", "changed_time", "missing_scheme", "historical_scheme"}:
        with pytest.raises(ProtocolControlAgentWireValidationError):
            _merge_obligation_atom_repair(raw, baseline, (0, 0, 0), repeat_scheme_only=True)
        assert wire.model_dump(mode="json") == baseline
        return
    merged = _merge_obligation_atom_repair(raw, baseline, (0, 0, 0), repeat_scheme_only=True)
    if change == "wrong_count":
        with pytest.raises(ValueError):
            validate_candidate_alignment(batch, source, coverage, merged, alignment)
        return
    validate_candidate_alignment(batch, source, coverage, merged, alignment)
    final = merged.model_dump(mode="json")
    final["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]["evaluation"]["repeat_scheme"] = None
    assert final == baseline
    if change == "unknown_scope":
        from app.domain.repeat_observation_count import evaluate_repeat_count
        from app.domain.contracts.enums import TruthValue
        assert evaluate_repeat_count(good.evaluation.repeat_scheme, repeat_group_ids=(),
            qualified_scope="per_current_episode", scope_complete=True).result.truth == TruthValue.UNKNOWN


@pytest.mark.parametrize("reply", ["valid", "wrong_count", "changed_policy", "transport"])
@pytest.mark.parametrize("unresolved_sibling", [False, True])
@pytest.mark.parametrize("field_patch", [False, True])
def test_source_repeat_count_runner_requests_only_missing_scheme_and_rechecks(reply, unresolved_sibling, field_patch):
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunner, ProtocolControlAgentResponse
    from tests.v2.protocols.test_slice58c_control_deconstructor import (
        _FakeTransport, _two_independent_candidate_linked_alignment_material, _evaluation,
    )
    _, _, repeat_wire, _, _ = _repeat_count_material()
    scheme = repeat_wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0].evaluation.repeat_scheme
    batch, source, review, original_wire, payload = _two_independent_candidate_linked_alignment_material()
    text = "本次节点允许复查3次"
    batch.owned_units[0].excerpt = source.statements[0].quoted_text = text
    if not unresolved_sibling:
        batch.owned_units[1].excerpt = "研究背景说明"
        source.statements = source.statements[:1]
    source.statements[0].force = "descriptive"
    source.units_without_statement = [] if unresolved_sibling else [batch.owned_units[1].structure_unit_id]
    wire = original_wire.model_copy(deep=True) if unresolved_sibling else _wire(candidate=original_wire.candidate_drafts[0])
    if unresolved_sibling:
        sibling_text = "复检前不得进行干预"
        batch.owned_units[1].excerpt = source.statements[1].quoted_text = sibling_text
        source.statements[1].force = "prohibited"
        source.statements[1].time_words = ["复检前"]
        source.statements[1].decision_functions = ["action", "time_validity"]
        sibling = wire.candidate_drafts[1]
        sibling_atom = sibling.obligation_expression.groups[0].atoms[0]
        sibling_atom.kind = type(sibling_atom.kind)("prohibit_medication_or_treatment_exposure")
        sibling_atom.statement = "不得进行干预"
        sibling_atom.source_excerpts = [sibling_text]
        sibling_atom.evaluation = type(sibling_atom.evaluation).model_validate(
            _evaluation(sibling_atom.statement, sibling_atom.source_span_ids[0], sibling_text))
        for evidence in sibling.minimum_evidence:
            evidence.description = sibling_text
            evidence.source_policy.source_excerpts = [sibling_text]
        payload["items"][1].update(source_excerpt=sibling_text,
            candidate_atom_quotes=[sibling_atom.statement], decision="fully_expressed",
            unresolved_dimensions=[])
        review.items[1].source_action_excerpt = sibling_text
        review.items[1].source_time_excerpt = "复检前"
        review.items[1].unresolved_aspects = ["复检前的时间关系尚未核实"]
    wire.candidate_drafts[0].applicability_expression = None
    atom = wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    atom.statement = "本节点可复查3次"
    atom.source_excerpts = [text]
    evaluation = _evaluation(atom.statement, atom.source_span_ids[0], text)
    evaluation["repeat_scheme"] = scheme.model_copy(update={"source_span_ids": list(atom.source_span_ids),
        "source_excerpts": [text]}).model_dump(mode="json")
    atom.evaluation = type(atom.evaluation).model_validate(evaluation)
    for evidence in wire.candidate_drafts[0].minimum_evidence:
        evidence.description = text
        evidence.source_policy.source_excerpts = [text]
    payload["items"] = payload["items"] if unresolved_sibling else payload["items"][:1]
    payload["items"][0]["source_excerpt"] = text
    alignment = SourceCandidateAlignment.model_validate(payload)
    alignment.items[0].candidate_atom_quotes = [atom.statement]
    good = atom.model_copy(deep=True)
    atom.evaluation = atom.evaluation.model_copy(update={"repeat_scheme": None})
    original = wire.model_dump(mode="json")
    sibling_review = review.items[1:] if unresolved_sibling else []
    review = SourceTargetReview.model_validate({"version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "additional_requirement", "target_id": None,
            "source_action_excerpt": source.statements[0].quoted_text, "target_action_excerpt": None,
            "source_time_excerpt": None, "target_time_excerpt": None,
            "unresolved_aspects": ["次数合同尚未结构化"]}]})
    review.items.extend(sibling_review)
    class Transport(_FakeTransport):
        atom_calls = alignment_calls = 0
        def start_source_target_review(self, *, prompt, target_ids=None):
            return ProtocolControlAgentResponse(session_id="source-check", text=review.model_dump_json())
        def start_source_candidate_alignment(self, *, prompt):
            self.alignment_calls += 1
            return ProtocolControlAgentResponse(session_id="alignment", text=alignment.model_dump_json(exclude={"proofs"}))
        def continue_atom(self, *, session_id, prompt):
            self.atom_calls += 1
            assert "本次只允许补 evaluation.repeat_scheme" in prompt
            if reply == "transport":
                raise RuntimeError("synthetic unavailable")
            proposed = good.model_copy(deep=True)
            if reply == "wrong_count":
                proposed.evaluation.repeat_scheme.maximum_repeats = 4
            elif reply == "changed_policy":
                proposed.evaluation = proposed.evaluation.model_copy(update={"observation_policy":
                    proposed.evaluation.observation_policy.model_copy(update={"mode": "any"})})
            return ProtocolControlAgentResponse(session_id=session_id,
                text=json.dumps({"evaluation_patch": {"repeat_scheme": proposed.evaluation.repeat_scheme.model_dump(
                    mode="json", exclude={"source_span_ids", "source_excerpts"})}}
                    if field_patch and reply != "changed_policy" else {"atom": proposed.model_dump(mode="json")}, ensure_ascii=False))
        def continue_numeric_predicate(self, **kwargs):
            pytest.fail("An action count must not request a measurement predicate")
        def continue_scoped_unit_repair(self, **kwargs):
            pytest.fail("A missing scheme must not rewrite the source unit")
    transport = Transport([])
    if field_patch:
        transport.continue_repeat_scheme = transport.continue_atom
    result = ProtocolControlAgentRunner(max_schema_repairs=2).run(batch, transport,
        resume_source_interpretation=source, resume_wire=wire, resume_session_id="original-wire",
        output_validator=lambda _output: None)
    assert transport.atom_calls == 1, [(attempt.error_classes, attempt.issues) for attempt in result.attempts]
    if reply == "valid" and not unresolved_sibling:
        assert result.final_output is not None
        assert transport.alignment_calls == 2
        final = result.partial_wire.model_dump(mode="json")
        final["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]["evaluation"]["repeat_scheme"] = None
        assert final == original
    else:
        assert result.final_output is None and result.partial_wire.model_dump(mode="json") == original
        assert transport.alignment_calls <= 2
        if reply == "valid" and unresolved_sibling:
            assert transport.alignment_calls == 2
            assert any(attempt.error_detail and attempt.error_detail.get("workflow_phase") == "reviewed_atom_repair"
                       and attempt.outcome == "parsed" for attempt in result.attempts)
            assert result.partial_wire.candidate_drafts[1].model_dump(mode="json") == original["candidate_drafts"][1]


@pytest.mark.parametrize("change", [None, "host_sources", "changed_source", "changed_quote", "extra_field", "missing_scheme", "null_scheme", "contradictory_result", "old_scheme", "foreign_trigger", "foreign_condition", "duplicate_frozen_sources", "unpaired_frozen_sources"])
def test_repeat_field_patch_splices_only_current_scheme(change):
    from app.agents.protocol_control_deconstructor import (
        _merge_obligation_atom_repair, ProtocolControlAgentWireValidationError,
    )
    batch, source, wire, coverage, alignment = _repeat_count_material()
    atom = wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    scheme = atom.evaluation.repeat_scheme.model_dump(mode="json")
    atom.evaluation = atom.evaluation.model_copy(update={"repeat_scheme": None})
    baseline = wire.model_dump(mode="json")
    unchanged_wire = wire.model_dump(mode="json")
    patch = {"repeat_scheme": scheme}
    if change == "host_sources":
        scheme.pop("source_span_ids")
        scheme.pop("source_excerpts")
    elif change == "changed_source":
        scheme["source_span_ids"] = ["another-source"]
    elif change == "changed_quote":
        scheme["source_excerpts"] = ["另一项要求"]
    elif change == "extra_field":
        patch["proposition"] = "其他判断"
    elif change == "missing_scheme":
        patch = {}
    elif change == "null_scheme":
        patch["repeat_scheme"] = None
    elif change == "contradictory_result":
        scheme.update(result_use="unresolved", result_population="unresolved")
    elif change == "old_scheme":
        scheme["version"] = "repeat-scheme/v3"
    elif change == "foreign_trigger":
        scheme.update(trigger="source_condition", trigger_excerpt="其他要求的前提",
                      trigger_condition_id="some-condition")
    elif change == "foreign_condition":
        scheme.update(trigger="source_condition", trigger_excerpt=scheme["source_excerpts"][0],
                      trigger_condition_id="unregistered-condition")
    elif change in {"duplicate_frozen_sources", "unpaired_frozen_sources"}:
        scheme.pop("source_span_ids")
        scheme.pop("source_excerpts")
        frozen = baseline["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]["evaluation"]
        frozen["source_span_ids"] *= 2
        if change == "duplicate_frozen_sources":
            frozen["source_excerpts"] *= 2
    raw = json.dumps({"evaluation_patch": patch}, ensure_ascii=False)
    if change not in {None, "host_sources"}:
        with pytest.raises(ProtocolControlAgentWireValidationError):
            _merge_obligation_atom_repair(raw, baseline, (0, 0, 0), repeat_scheme_only=True)
    else:
        merged = _merge_obligation_atom_repair(raw, baseline, (0, 0, 0), repeat_scheme_only=True)
        validate_candidate_alignment(batch, source, coverage, merged, alignment)
        dumped = merged.model_dump(mode="json")
        dumped["candidate_drafts"][0]["obligation_expression"]["groups"][0]["atoms"][0]["evaluation"]["repeat_scheme"] = None
        assert dumped == baseline
    assert wire.model_dump(mode="json") == unchanged_wire


@pytest.mark.parametrize("full_legacy_patch", [False, True])
def test_repeat_patch_uses_frozen_evaluation_subset_not_wider_atom(full_legacy_patch):
    from app.agents.protocol_control_deconstructor import _merge_obligation_atom_repair
    from app.domain.contracts.repeat_scheme import validate_repeat_source
    _, _, wire, _, _ = _repeat_count_material()
    atom = wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    scheme = atom.evaluation.repeat_scheme.model_dump(mode="json")
    atom.source_excerpts = ["先说明适用对象；" + atom.source_excerpts[0]]
    atom.evaluation = atom.evaluation.model_copy(update={"repeat_scheme": None})
    baseline = wire.model_dump(mode="json")
    if not full_legacy_patch:
        for field in ("source_span_ids", "source_excerpts"):
            scheme.pop(field)
    merged = _merge_obligation_atom_repair(json.dumps({"evaluation_patch": {"repeat_scheme": scheme}},
        ensure_ascii=False), baseline, (0, 0, 0), repeat_scheme_only=True)
    final = merged.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    assert final.source_excerpts == atom.source_excerpts
    assert final.evaluation.repeat_scheme.source_excerpts == atom.evaluation.source_excerpts
    assert final.evaluation.repeat_scheme.source_excerpts != final.source_excerpts
    validate_repeat_source(final.evaluation.repeat_scheme, final.evaluation.source_span_ids,
                          final.evaluation.source_excerpts)
    assert wire.model_dump(mode="json") == baseline


def test_repeat_meaning_request_excludes_source_authorship():
    import jsonschema
    from app.agents.protocol_control_deconstructor import protocol_control_atom_repair_response_format
    _, _, wire, _, _ = _repeat_count_material()
    scheme = wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0].evaluation.repeat_scheme.model_dump(mode="json")
    scheme["permission_condition_id"] = None
    request_schema = protocol_control_atom_repair_response_format(repeat_scheme_only=True)["json_schema"]["schema"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"evaluation_patch": {"repeat_scheme": scheme}}, request_schema)
    for field in ("source_span_ids", "source_excerpts"):
        scheme.pop(field)
    jsonschema.validate({"evaluation_patch": {"repeat_scheme": scheme}}, request_schema)


@pytest.mark.parametrize("change", [None, "visit_substitution", "named_visit", "reverse", "missing_word", "wrong_source", "numeric_window", "executable_time", "vague"])
def test_source_event_interval_alignment_retains_non_executable_consumer_gap(change):
    from app.domain.contracts.rules import TimeConstraint
    from app.projections.control_calculation_experiment import _proposition_observation
    from app.domain.contracts.enums import TruthValue
    from tests.v2.protocols.test_slice58c_control_deconstructor import (
        _two_independent_candidate_linked_alignment_material, _evaluation,
    )
    batch, source, _, wire, payload = _two_independent_candidate_linked_alignment_material()
    word = "筛选前" if change == "named_visit" else "此前" if change == "vague" else "核查前"
    text = f"{word}不得更改记录"
    batch.owned_units[1].excerpt = source.statements[1].quoted_text = text
    source.statements[1].force = "prohibited"
    source.statements[1].time_words = [word]
    candidate = wire.candidate_drafts[1]
    atom = candidate.obligation_expression.groups[0].atoms[0]
    atom.kind = ControlObligationKind.PROHIBIT_EVENT
    atom.statement = text if change != "missing_word" else "不得更改记录"
    atom.source_excerpts = [text]
    evaluation = _evaluation(atom.statement, atom.source_span_ids[0], text)
    evaluation.update(time_purpose="event_membership" if change == "executable_time" else "interval_condition",
                      time_operand_attribute="date_range")
    if change == "wrong_source":
        evaluation["source_excerpts"] = ["其他操作前不得更改记录"]
    atom.evaluation = type(atom.evaluation).model_validate(evaluation)
    atom.time_constraint = TimeConstraint.model_validate({
        "anchor_type": "screening_date" if change == "visit_substitution" else "event_date",
        "direction": "after" if change == "reverse" else "before",
        "upper_bound_days": 2 if change == "numeric_window" else None,
    })
    for evidence in candidate.minimum_evidence:
        evidence.source_policy.source_excerpts = [text]
    payload["items"][1].update(source_excerpt=text, candidate_atom_quotes=[atom.statement],
        decision="fully_expressed", unresolved_dimensions=[])
    coverage = source_statement_coverage(batch, source, wire)
    alignment = SourceCandidateAlignment.model_validate(payload)
    if change:
        with pytest.raises(ValueError):
            validate_candidate_alignment(batch, source, coverage, wire, alignment)
    else:
        validate_candidate_alignment(batch, source, coverage, wire, alignment)
        bound = bind_candidate_alignment(batch, source, coverage, wire, alignment, alignment.model_dump_json())
        assert bound.proofs
        truth, reasons = _proposition_observation(atom, [{"status": "entails_agreed"}], SimpleNamespace())
        assert truth == TruthValue.UNKNOWN and reasons == ["interval_calculation_unsupported"]


@pytest.mark.parametrize("outside_quote", ["条件甲", "不存在的原句", " "])
def test_duplicate_grounded_atoms_cannot_mask_an_unsupported_quote(outside_quote):
    batch, source, wire, coverage, alignment = _conditioned_action_material()
    # Two trigger branches repeat the same supported quote, not two distinct proofs.
    alignment.items[0].candidate_atom_quotes.append(outside_quote)
    with pytest.raises(ValueError, match="未由本条来源支持"):
        validate_candidate_alignment(batch, source, coverage, wire, alignment)


@pytest.mark.parametrize("mutation", [None, "missing_condition", "wrong_prefix", "wrong_position", "weaker_obligation", "partial_branch_mapping", "empty_branch_mapping"])
def test_distributed_source_condition_requires_every_relevant_branch(mutation):
    batch, source, wire, coverage, alignment = _conditioned_action_material()
    candidate = wire.candidate_drafts[0]
    if mutation == "missing_condition":
        alignment.items[0].candidate_atom_quotes.pop(0)
    elif mutation == "wrong_prefix":
        candidate.trigger_expression.groups[1].atoms[0].statement = "尚未完成核查者"
    elif mutation == "wrong_position":
        candidate.trigger_expression.groups[1].atoms[0].source_span_ids = ["wrong-source"]
    elif mutation == "weaker_obligation":
        candidate.obligation_expression.groups.append(candidate.obligation_expression.groups[0].model_copy(
            deep=True, update={"atoms": candidate.obligation_expression.groups[0].atoms[:1]}))
    elif mutation == "partial_branch_mapping":
        candidate.obligation_expression.groups[0].applies_to_trigger_branch_indexes = [0]
    elif mutation == "empty_branch_mapping":
        candidate.obligation_expression.groups[0].applies_to_trigger_branch_indexes = []
    if mutation:
        with pytest.raises(ValueError):
            validate_candidate_alignment(batch, source, coverage, wire, alignment)
    else:
        validate_candidate_alignment(batch, source, coverage, wire, alignment)


@pytest.mark.parametrize("mutation", [None, "conditional", "different_visit", "numeric_window", "missing_stage_source", "outside_visit", "before_visit", "after_visit"])
def test_source_bound_common_trigger_preserves_visit_not_date_window(mutation):
    prefix = {"conditional": "基线期如已完成核查者", "outside_visit": "基线期外已完成核查者",
              "before_visit": "基线期前已完成核查者", "after_visit": "基线期后已完成核查者"}.get(
                  mutation, "基线期：已完成核查者")
    batch, source, wire, coverage, alignment = _conditioned_action_material(prefix)
    source.statements[0].decision_functions = ["action", "time_validity"]
    source.statements[0].time_words = ["基线期"]
    if mutation == "different_visit":
        wire.candidate_drafts[0].review_node_bindings[0].workflow_stage_id = "unknown-stage"
    elif mutation == "numeric_window":
        source.statements[0].time_words = ["基线前7天"]
    elif mutation == "missing_stage_source":
        for stage in batch.known_workflow_stage_targets:
            stage.source_span_ids = []
    if mutation not in {None, "conditional"}:
        with pytest.raises(ValueError):
            validate_candidate_alignment(batch, source, coverage, wire, alignment)
    else:
        validate_candidate_alignment(batch, source, coverage, wire, alignment)


@pytest.mark.parametrize("mutation", [None, "number_only", "wrong_direction", "wrong_unit", "missing_trigger", "unscoped",
    "whole_quote_unscoped", "lost_quantifier", "lost_exception"])
def test_conditioned_numeric_consequence_uses_own_quote_without_losing_parent_scope(mutation):
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentWire
    from tests.v2.protocols.test_slice58c_control_deconstructor import _evaluation
    batch, source, wire, coverage, alignment = _conditioned_action_material()
    old, replacement = "领取材料", "领取次数至多3次"
    unit = batch.owned_units[0]
    full_consequence = ("任一访视" + replacement if mutation == "lost_quantifier" else
                        replacement + "，尚未同意者除外" if mutation == "lost_exception" else replacement)
    unit.excerpt = unit.excerpt.replace(old, full_consequence).replace("，回收材料", "")
    unit.member_texts = [unit.excerpt]
    source.statements[0].quoted_text = source.statements[0].quoted_text.replace(old, full_consequence).replace("，回收材料", "")
    source.statements[0].decision_functions = ["action", "threshold"]
    alignment.items[0].source_excerpt = source.statements[0].quoted_text
    alignment.items[0].candidate_atom_quotes = [alignment.items[0].candidate_atom_quotes[0], replacement]
    payload = json.loads(wire.model_dump_json().replace(old, full_consequence).replace("，回收材料", ""))
    group = payload["candidate_drafts"][0]["obligation_expression"]["groups"][0]
    group["atoms"] = group["atoms"][:1]
    atom = group["atoms"][0]
    atom["statement"] = replacement
    if mutation in {"whole_quote_unscoped", "lost_quantifier", "lost_exception"}:
        atom["source_excerpts"] = [source.statements[0].quoted_text]
    evaluation = _evaluation(replacement, unit.source_span_ids[0], replacement)
    evaluation.update(determination_mode="deterministic", operation="value_comparison", operand_attribute="value",
        predicate={"predicate_id": "synthetic-count", "subject": "领取", "attribute": "次数",
                   "source_clause": replacement, "comparator": "lte", "value": 3, "unit": "次"})
    if mutation == "number_only":
        evaluation["predicate"]["source_clause"] = "3"
    elif mutation == "wrong_direction":
        evaluation["predicate"]["comparator"] = "gte"
    elif mutation == "wrong_unit":
        evaluation["predicate"]["unit"] = "天"
    atom["evaluation"] = evaluation
    wire = ProtocolControlAgentWire.model_validate(payload)
    if mutation == "missing_trigger":
        alignment.items[0].candidate_atom_quotes.pop(0)
    elif mutation in {"unscoped", "whole_quote_unscoped"}:
        wire.candidate_drafts[0].obligation_expression.groups[0].applies_to_trigger_branch_indexes = []
    if mutation:
        with pytest.raises(ValueError):
            validate_candidate_alignment(batch, source, coverage, wire, alignment)
    else:
        validate_candidate_alignment(batch, source, coverage, wire, alignment)


@pytest.mark.parametrize("mutation", [None, "pure_exception", "missing_exception", "no_exception_words", "definition", "unknown", "different_exception_layer"])
def test_action_with_source_exception_is_not_a_pure_definition(mutation):
    batch, source, wire, coverage, alignment = _native_action_material()
    text = "材料分发及回收，尚未同意者除外"
    unit, statement = batch.owned_units[0], source.statements[0]
    # This family exercises a paragraph obligation, not table visit inference.
    unit.table_context = None
    unit.unit_kind = StructureUnitKind.PARAGRAPH
    unit.source_ref = "body.p1"
    unit.member_source_refs = [unit.source_ref]
    unit.member_texts = [text]
    unit.member_source_span_ids = [list(unit.source_span_ids)]
    unit.excerpt = text
    statement.quoted_text = unit.excerpt
    statement.scope_quote = None
    statement.time_words = []
    statement.decision_functions = ["action", "exception"]
    statement.exception_words = "尚未同意者除外"
    for node in wire.candidate_drafts[0].review_node_bindings:
        node.scope_citation = None
    atom = wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    atom.statement = text
    atom.evaluation = atom.evaluation.model_copy(update={"proposition": atom.statement})
    atom.source_excerpts = [text]
    alignment.items[0].source_excerpt = unit.excerpt
    alignment.items[0].candidate_atom_quotes = [atom.statement]
    if mutation == "pure_exception":
        statement.decision_functions = ["exception"]
    elif mutation == "missing_exception":
        statement.exception_words = "其他情况除外"
    elif mutation == "no_exception_words":
        statement.exception_words = None
    elif mutation == "definition":
        statement.decision_functions.append("definition")
    elif mutation == "unknown":
        statement.decision_functions.append("unclassified")
    elif mutation == "different_exception_layer":
        expression = _candidate().exception_expression
        exception = expression.groups[0].atoms[0]
        exception.statement = "已经同意者也除外"
        exception.source_span_ids = list(unit.source_span_ids)
        exception.source_excerpts = [text]
        exception.evaluation = atom.evaluation.model_copy(update={"proposition": exception.statement})
        wire.candidate_drafts[0].exception_expression = expression
    if mutation:
        with pytest.raises(ValueError):
            validate_candidate_alignment(batch, source, coverage, wire, alignment)
    else:
        validate_candidate_alignment(batch, source, coverage, wire, alignment)


def test_alignment_closure_change_invalidates_saved_proof_not_sibling_source():
    batch, source, wire, coverage, alignment = _native_action_material()
    extra = batch.owned_units[0].model_copy(deep=True, update={
        "structure_unit_id": "owned-extra", "excerpt": "另外记录操作日期",
        "table_context": None, "source_ref": "body.p99",
        "unit_kind": StructureUnitKind.PARAGRAPH,
        "member_source_refs": ["body.p99"], "member_texts": ["另外记录操作日期"],
        "source_span_ids": ["span:extra"], "member_source_span_ids": [["span:extra"]],
    })
    batch.owned_units.append(extra)
    batch.owned_structure_unit_ids.append(extra.structure_unit_id)
    batch.owned_source_span_ids.extend(extra.source_span_ids)
    wire.candidate_drafts[0].source_structure_unit_ids.append(extra.structure_unit_id)
    wire.candidate_drafts[0].source_span_ids.extend(extra.source_span_ids)
    proof = bind_candidate_alignment(batch, source, coverage, wire, alignment,
        alignment.model_dump_json(exclude={"proofs"}))
    assert len(reusable_proven_alignment_items(batch, source, coverage, wire, proof)) == 1
    extra.excerpt = "不得记录操作日期"
    extra.member_texts = [extra.excerpt]
    assert reusable_proven_alignment_items(batch, source, coverage, wire, proof) == []


@pytest.mark.parametrize("separate_alternative", [False, "unrelated", "weaker", "full_quote_weaker", "equivalent"])
def test_split_conjunction_checks_this_statement_without_erasing_or_alternative(separate_alternative):
    batch, source, wire, coverage, alignment = _native_action_material()
    unit, statement = batch.owned_units[0], source.statements[0]
    text = "领取材料，回收材料"
    unit.table_context = None
    unit.unit_kind = StructureUnitKind.PARAGRAPH
    statement.quoted_text = text
    unit.excerpt = text + "。另需记录电话。"
    unit.source_ref = "body.p1"
    unit.member_source_refs = [unit.source_ref]
    unit.member_texts = [unit.excerpt]
    unit.member_source_span_ids = [list(unit.source_span_ids)]
    statement.scope_quote = None
    statement.time_words = []
    candidate = wire.candidate_drafts[0]
    for node in candidate.review_node_bindings:
        node.scope_citation = None
    group = candidate.obligation_expression.groups[0]
    original = group.atoms[0]
    group.atoms = []
    for part in ["领取材料", "回收材料", "记录电话"]:
        atom = original.model_copy(deep=True, update={"statement": part, "source_excerpts": [part]})
        atom.evaluation = atom.evaluation.model_copy(update={"proposition": part})
        group.atoms.append(atom)
    alignment.items[0].source_excerpt = text
    alignment.items[0].candidate_atom_quotes = ["领取材料", "回收材料"]
    if separate_alternative == "unrelated":
        # An OR alternative must not bypass the current requirement.
        candidate.obligation_expression.groups.append(group.model_copy(deep=True,
            update={"atoms": [group.atoms.pop()]}))
        with pytest.raises(ValueError, match="另一义务分支"):
            validate_candidate_alignment(batch, source, coverage, wire, alignment)
    elif separate_alternative:
        if separate_alternative == "full_quote_weaker":
            group.atoms = [original.model_copy(deep=True,
                update={"statement": text, "source_excerpts": [text]})]
            group.atoms[0].evaluation = original.evaluation.model_copy(update={"proposition": text})
            alignment.items[0].candidate_atom_quotes = [text, "领取材料"]
        alternative = group.model_copy(deep=True,
            update={"atoms": [group.atoms[0]] if separate_alternative != "equivalent" else group.atoms[:2]})
        if separate_alternative == "full_quote_weaker":
            alternative.atoms[0] = original.model_copy(deep=True,
                update={"statement": "领取材料", "source_excerpts": ["领取材料"]})
            alternative.atoms[0].evaluation = original.evaluation.model_copy(update={"proposition": "领取材料"})
        candidate.obligation_expression.groups.append(alternative)
        if separate_alternative == "equivalent":
            validate_candidate_alignment(batch, source, coverage, wire, alignment)
        else:
            with pytest.raises(ValueError, match="完整合取内容"):
                validate_candidate_alignment(batch, source, coverage, wire, alignment)
    else:
        validate_candidate_alignment(batch, source, coverage, wire, alignment)


@pytest.mark.parametrize("label", ["材料分发及回收", "资料发放并回收", "资料发放及回收确认"])
def test_native_action_text_need_not_include_schedule_markers(label):
    batch, source, wire, coverage, alignment = _native_action_material()
    unit, statement = batch.owned_units[0], source.statements[0]
    unit.member_texts[0] = label
    unit.excerpt = f"{label} | X"
    statement.quoted_text = unit.excerpt
    atom = wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    atom.statement = f"在基线期 V2 D0 完成{label}"
    atom.evaluation = atom.evaluation.model_copy(update={"proposition": atom.statement})
    atom.source_excerpts[0] = label
    alignment.items[0].source_excerpt = unit.excerpt
    alignment.items[0].candidate_atom_quotes = [atom.statement]
    validate_candidate_alignment(batch, source, coverage, wire, alignment)


@pytest.mark.parametrize("mutation", ["missing_action", "partial_proposition", "wrong_row",
    "unresolved", "marker_footnote", "nonmarker_value", "exception", "wrong_scope", "no_scope"])
def test_native_action_text_does_not_prove_unknown_or_changed_content(mutation):
    batch, source, wire, coverage, alignment = _native_action_material()
    atom = wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    unit, statement = batch.owned_units[0], source.statements[0]
    if mutation == "missing_action":
        atom.statement = "在基线期 V2 D0 完成材料分发"
        alignment.items[0].candidate_atom_quotes = [atom.statement]
    elif mutation == "partial_proposition":
        atom.evaluation = atom.evaluation.model_copy(update={"proposition": "在基线期 V2 D0 完成材料分发"})
    elif mutation == "wrong_row":
        atom.source_span_ids[0] = "snapshot::body.t0.r4.c0.p0"
    elif mutation == "unresolved":
        statement.unresolved = ["适用访视尚待核对"]
    elif mutation == "marker_footnote":
        unit.member_texts[-1] = "X^5"
        unit.excerpt = "材料分发及回收 | X^5"
        statement.quoted_text = unit.excerpt
        alignment.items[0].source_excerpt = unit.excerpt
        atom.source_excerpts[-1] = "X^5"
    elif mutation == "nonmarker_value":
        unit.member_texts[-1] = "完成后3天"
        unit.excerpt = "材料分发及回收 | 完成后3天"
        statement.quoted_text = unit.excerpt
        alignment.items[0].source_excerpt = unit.excerpt
        atom.source_excerpts[-1] = "完成后3天"
    elif mutation == "exception":
        statement.exception_words = "未完成时除外"
    elif mutation == "wrong_scope":
        statement.time_words.append("V1")
    elif mutation == "no_scope":
        statement.scope_quote = None
        statement.affected_stage = None
        statement.time_words = []
    with pytest.raises(ValueError):
        validate_candidate_alignment(batch, source, coverage, wire, alignment)


def test_native_action_alignment_survives_save_and_read_without_erasing_scope():
    batch, source, wire, coverage, alignment = _native_action_material()
    output = hydrate_protocol_control_agent_output(wire, batch)
    coverage = hydrated_source_coverage_indexes(batch, wire, output, coverage)
    coverage[0] = coverage[0].model_copy(update={"status": "semantically_aligned"})
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{"statement_index": 0, "decision": "additional_requirement",
                   "source_action_excerpt": "材料分发及回收", "unresolved_aspects": ["既有目录未覆盖"]}],
    })
    alignment = bind_candidate_alignment(batch, source, coverage, wire, alignment,
                                        alignment.model_dump_json(exclude={"proofs"}))
    result = ProtocolControlAgentRunResult(status="已解析", batch_id=batch.batch_id,
        session_id="native-action", attempts=[ProtocolControlAgentAttempt(attempt=1,
        session_id="native-action", raw_output_sha256="a" * 64, outcome="parsed")],
        source_interpretation=source, source_target_review=review,
        source_statement_coverage=coverage, partial_wire=wire, final_output=output,
        source_candidate_alignment=alignment)
    restored = ProtocolControlAgentRunResult.model_validate(result.model_dump(mode="json"))
    _validate_saved_source_review(batch, restored)
    restored.source_interpretation.statements[0].unresolved = ["适用访视尚待核对"]
    with pytest.raises(SourceTargetReviewValidationError) as error:
        _validate_saved_source_review(batch, restored)
    assert error.value.code == "SOURCE_UNRESOLVED_STILL_ADDED"


@pytest.mark.parametrize("readable", [True, False])
def test_readable_native_exit_header_allows_question_not_adoption(readable):
    batch, source, wire, coverage, alignment = _native_action_material()
    source.statements[0].affected_stage = None
    source.statements[0].scope_quote = None
    source.statements[0].time_words = []
    source.statements[0].unresolved = ["提前退出列的时点尚待核对"]
    for context in batch.context_units:
        context.member_texts[-1] = "提前退出" if readable else ""
        context.excerpt = " | ".join(text for text in context.member_texts if text.strip())
    if not readable:
        batch.context_units = []
    assert can_recheck_source_scope_question(source.statements[0], batch) is readable
    with pytest.raises(ValueError, match="未核清范围"):
        validate_candidate_alignment(batch, source, coverage, wire, alignment)


def test_native_source_question_separates_missing_runtime_mapping_from_source_meaning():
    batch, source, wire, coverage, alignment = _native_action_material()
    statement = source.statements[0]
    statement.scope_quote = statement.affected_stage = None
    statement.time_words = []
    statement.unresolved = ["标题未映射到固定日期"]
    for context in batch.context_units:
        context.member_texts[-1] = "退出时"
        context.excerpt = " | ".join(text for text in context.member_texts if text.strip())
    prompt = build_source_scope_question_prompt(batch, source, 0)
    assert "没有共同阶段本身不是原文歧义" in prompt
    native_prompt = build_source_scope_correction_prompt(batch, statement, "映射尚未建立")
    assert '"fixed_visit_or_date_unmapped": true' in native_prompt
    assert "程序不能映射固定访视/日期不等于原文不清" in prompt
    assert "只有源文字、脚注或动作与列关系本身未清" in prompt
    proposal = SourceInterpretation(version=source.version,
        statements=[statement.model_copy(update={"unresolved": []})], units_without_statement=[])
    revised = apply_source_scope_question_recheck(batch, source, 0, proposal)
    assert revised.statements[0].scope_quote is None
    assert revised.statements[0].time_words == []
    # A source clarification still does not supply a usable runtime visit.
    alignment.items[0].source_excerpt = revised.statements[0].quoted_text
    with pytest.raises(ValueError):
        validate_candidate_alignment(batch, revised, coverage, wire, alignment)


def _multi_native_action_material():
    batch, source, wire, coverage, alignment = _native_action_material()
    unit, statement = batch.owned_units[0], source.statements[0]
    statement.scope_quote = statement.affected_stage = None
    statement.time_words = []
    unit.member_source_refs.append("body.t0.r3.c1.p0")
    unit.source_span_ids.append("snapshot::body.t0.r3.c1.p0")
    unit.member_texts.append("X")
    unit.table_context.member_cell_paths.append((3, 1))
    unit.excerpt += " | X"
    statement.quoted_text = unit.excerpt
    stage = KnownWorkflowStageTarget(workflow_stage_id="stage:screen:native",
        review_stage=ReviewStage.SCREENING, display_name="筛选期 / V1 / D-1",
        visit_instance="筛选期 / V1 / D-1",
        source_span_ids=[f"snapshot::body.t0.r{row}.c1.p0" for row in range(3)],
        source_excerpts=["筛选期", "V1", "D-1"])
    batch.known_workflow_stage_targets.append(stage)
    candidate = wire.candidate_drafts[0]
    candidate.review_node_bindings.append(candidate.review_node_bindings[0].model_copy(update={
        "workflow_stage_id": stage.workflow_stage_id, "review_stage": stage.review_stage}))
    candidate.source_span_ids.append(unit.source_span_ids[-1])
    atom = candidate.obligation_expression.groups[0].atoms[0]
    atom.source_span_ids.append(unit.source_span_ids[-1])
    atom.source_excerpts.append("X")
    atom.statement = "在筛选期和基线期分别完成材料分发及回收"
    atom.evaluation = atom.evaluation.model_copy(update={"proposition": atom.statement})
    alignment.items[0].source_excerpt = statement.quoted_text
    alignment.items[0].candidate_atom_quotes = [atom.statement]
    return batch, source, wire, coverage, alignment


@pytest.mark.parametrize("mutation", [None, "missing_node", "duplicate_node", "wrong_header",
    "missing_marker", "partial_action", "unresolved", "shared_scope", "extra_content"])
def test_all_current_native_marks_need_their_own_sourced_visit(mutation):
    batch, source, wire, coverage, alignment = _multi_native_action_material()
    candidate, statement, unit = wire.candidate_drafts[0], source.statements[0], batch.owned_units[0]
    atom = candidate.obligation_expression.groups[0].atoms[0]
    if mutation == "missing_node":
        candidate.review_node_bindings.pop()
    elif mutation == "duplicate_node":
        candidate.review_node_bindings[-1] = candidate.review_node_bindings[0].model_copy()
    elif mutation == "wrong_header":
        batch.known_workflow_stage_targets[-1].source_excerpts[-1] = "D-2"
    elif mutation == "missing_marker":
        atom.source_span_ids.pop()
        atom.source_excerpts.pop()
    elif mutation == "partial_action":
        atom.evaluation = atom.evaluation.model_copy(update={"proposition": "分别完成材料分发"})
    elif mutation == "unresolved":
        statement.unresolved = ["原文脚注存在两种动作含义"]
    elif mutation == "shared_scope":
        statement.scope_quote = "基线期 / V2 / D0"
    elif mutation == "extra_content":
        unit.member_texts[-1] = "完成后3天"
        unit.excerpt = " | ".join(unit.member_texts)
        statement.quoted_text = unit.excerpt
        alignment.items[0].source_excerpt = unit.excerpt
    if mutation is None:
        validate_candidate_alignment(batch, source, coverage, wire, alignment)
    else:
        with pytest.raises(ValueError):
            validate_candidate_alignment(batch, source, coverage, wire, alignment)


def test_later_native_columns_are_retained_but_not_adopted_as_current_visits():
    batch, source, wire, coverage, alignment = _multi_native_action_material()
    unit = batch.owned_units[0]
    for column, label in ((3, "治疗后 / V3 / D7"), (4, "退出时")):
        unit.member_source_refs.append(f"body.t0.r3.c{column}.p0")
        unit.source_span_ids.append(f"snapshot::body.t0.r3.c{column}.p0")
        unit.member_texts.append("X")
        unit.table_context.member_cell_paths.append((3, column))
        for row, context in enumerate(batch.context_units):
            context.member_source_refs.append(f"body.t0.r{row}.c{column}.p0")
            context.source_span_ids.append(f"snapshot::body.t0.r{row}.c{column}.p0")
            context.member_texts.append(label if row == 0 else "")
            context.table_context.member_cell_paths.append((row, column))
            context.excerpt = " | ".join(text for text in context.member_texts if text.strip())
    unit.excerpt = " | ".join(unit.member_texts)
    source.statements[0].quoted_text = unit.excerpt
    alignment.items[0].source_excerpt = unit.excerpt
    before = unit.model_dump_json()
    validate_candidate_alignment(batch, source, coverage, wire, alignment)
    assert unit.model_dump_json() == before
    assert len(wire.candidate_drafts[0].review_node_bindings) == 2
    assert all("c3" not in span and "c4" not in span for atom in
        wire.candidate_drafts[0].obligation_expression.groups[0].atoms for span in atom.source_span_ids)
    assert source_statement_coverage(batch, source, wire)[0].status == "candidate_linked"
    # A later marker cannot become adopted by merely adding it to the atom's sources.
    atom = wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
    atom.source_span_ids.append("snapshot::body.t0.r3.c3.p0")
    atom.source_excerpts.append("X")
    with pytest.raises(ValueError):
        validate_candidate_alignment(batch, source, coverage, wire, alignment)


def _material():
    batch = _batch()
    interpretation = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-01", "quoted_text": "年龄至少18岁",
            "force": "required", "decision_functions": ["action"], "time_words": [],
        }],
        "units_without_statement": ["su-02"],
    })
    candidate = _candidate().model_copy(update={"exception_expression": None})
    wire = _wire(candidate=candidate)
    output = hydrate_protocol_control_agent_output(wire, batch)
    coverage = source_statement_coverage(batch, interpretation, wire)
    coverage[0] = coverage[0].model_copy(update={"status": "candidate_linked", "action_candidate_indexes": [0]})
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{
            "statement_index": 0, "decision": "additional_requirement", "target_id": None,
            "source_action_excerpt": "年龄至少18岁", "target_action_excerpt": None,
            "source_time_excerpt": None, "target_time_excerpt": None,
            "unresolved_aspects": ["既有目录未覆盖"],
        }],
    })
    return batch, interpretation, output, coverage, review


def _alignment(*, quote: str = "年龄达到18岁", decision: str = "fully_expressed"):
    return SourceCandidateAlignment.model_validate({
        "version": SOURCE_CANDIDATE_ALIGNMENT_VERSION,
        "items": [{
            "statement_index": 0, "candidate_index": 0, "decision": decision,
            "source_excerpt": "年龄至少18岁", "candidate_atom_quotes": [quote],
            "unresolved_dimensions": [] if decision == "fully_expressed" else ["年龄界限"],
        }],
    })


def test_alignment_schema_and_provenance_reject_unrelated_quote() -> None:
    batch, interpretation, output, coverage, _ = _material()
    assert candidate_alignment_response_format()["json_schema"]["strict"] is True
    validate_candidate_alignment(batch, interpretation, coverage, output, _alignment())
    with pytest.raises(ValueError, match="候选原句"):
        validate_candidate_alignment(batch, interpretation, coverage, output,
                                     _alignment(quote="服药至少18天"))


def test_saved_review_requires_exact_positive_alignment() -> None:
    batch, interpretation, output, coverage, review = _material()
    coverage[0] = coverage[0].model_copy(update={
        "status": "semantically_aligned", "candidate_indexes": [0],
    })
    result = ProtocolControlAgentRunResult(
        status="已解析", batch_id=batch.batch_id, session_id="source-review",
        attempts=[ProtocolControlAgentAttempt(
            attempt=1, session_id="source-review", raw_output_sha256="a" * 64,
            outcome="parsed",
        )],
        final_output=output, source_interpretation=interpretation,
        source_statement_coverage=coverage, source_target_review=review,
        source_candidate_alignment=_alignment(),
        partial_wire=_wire(candidate=_candidate().model_copy(update={
            "exception_expression": None,
        })),
    )
    result.source_candidate_alignment = bind_candidate_alignment(
        batch, interpretation, coverage, result.partial_wire, result.source_candidate_alignment,
        result.source_candidate_alignment.model_dump_json(exclude={"proofs"}),
    )
    _validate_saved_source_review(batch, ProtocolControlAgentRunResult.model_validate(
        result.model_dump(mode="json")))
    with pytest.raises(ValueError, match="候选语义核对"):
        _validate_saved_source_review(batch, result.model_copy(
            update={"source_candidate_alignment": None}))
    with pytest.raises(ValueError, match="未逐项对应"):
        _validate_saved_source_review(batch, result.model_copy(
            update={"source_candidate_alignment": _alignment(decision="incomplete")}))
    with pytest.raises(ValueError, match="覆盖账不一致"):
        _validate_saved_source_review(batch, result.model_copy(update={
            "source_statement_coverage": [coverage[0].model_copy(update={
                "status": "candidate_linked", "candidate_indexes": [],
            }), *coverage[1:]],
        }))


def test_alignment_rejects_short_quote_wrong_direction_and_wrong_function() -> None:
    batch, interpretation, output, coverage, _ = _material()
    with pytest.raises(ValueError, match="候选原句"):
        validate_candidate_alignment(batch, interpretation, coverage, output,
                                     _alignment(quote="18"))
    atom = output.candidates[0].semantics.obligation_expression.groups[0].atoms[0]
    correct_predicate = atom.evaluation.predicate
    predicate = correct_predicate.model_copy(update={
        "comparator": Comparator.LTE, "value": 65,
    })
    atom.evaluation = atom.evaluation.model_copy(update={"predicate": predicate})
    with pytest.raises(ValueError, match="比较方向"):
        validate_candidate_alignment(batch, interpretation, coverage, output, _alignment())
    interpretation.statements[0].decision_functions = ["threshold"]
    with pytest.raises(ValueError, match="比较方向"):
        validate_candidate_alignment(batch, interpretation, coverage, output, _alignment())
    atom.evaluation = atom.evaluation.model_copy(update={"predicate": correct_predicate})
    validate_candidate_alignment(batch, interpretation, coverage, output, _alignment())


def test_alignment_rejects_prohibition_without_prohibition_atom() -> None:
    batch, interpretation, output, coverage, _ = _material()
    interpretation.statements[0].force = "prohibited"
    with pytest.raises(ValueError, match="禁止性原文"):
        validate_candidate_alignment(batch, interpretation, coverage, output, _alignment())


@pytest.mark.parametrize("word,correct,wrong", [
    ("大于等于", Comparator.GTE, Comparator.GT),
    ("不小于", Comparator.GTE, Comparator.LT),
    ("小于等于", Comparator.LTE, Comparator.LT),
    ("不大于", Comparator.LTE, Comparator.GT),
    (">=", Comparator.GTE, Comparator.GT),
    ("<=", Comparator.LTE, Comparator.LT),
])
def test_numeric_alignment_preserves_inclusive_and_negated_comparisons(word, correct, wrong) -> None:
    batch, interpretation, output, coverage, _ = _material()
    source = f"年龄{word}18岁"
    batch.owned_units[0].excerpt = source
    interpretation.statements[0].quoted_text = source
    atom = output.candidates[0].semantics.obligation_expression.groups[0].atoms[0]
    atom.source_excerpts = [source]
    predicate = atom.evaluation.predicate.model_copy(update={
        "comparator": correct, "source_clause": source, "source_clauses": [],
    })
    atom.evaluation = atom.evaluation.model_copy(update={"predicate": predicate})
    alignment = _alignment()
    alignment.items[0].source_excerpt = source
    validate_candidate_alignment(batch, interpretation, coverage, output, alignment)
    atom.evaluation = atom.evaluation.model_copy(update={
        "predicate": predicate.model_copy(update={"comparator": wrong}),
    })
    with pytest.raises(ValueError, match="比较方向"):
        validate_candidate_alignment(batch, interpretation, coverage, output, alignment)


def test_literal_frequency_is_not_proof_of_an_executable_time_policy() -> None:
    batch, interpretation, output, coverage, _ = _material()
    source = "每3周接受一次治疗，共12周"
    batch.owned_units[0].excerpt = source
    interpretation.statements[0].quoted_text = source
    interpretation.statements[0].decision_functions = ["action", "time_validity"]
    interpretation.statements[0].time_words = ["每3周", "12周"]
    atom = output.candidates[0].semantics.obligation_expression.groups[0].atoms[0]
    atom.statement = source
    atom.source_excerpts = [source]
    atom.evaluation = atom.evaluation.model_copy(update={
        "determination_mode": "semantic", "proposition": source,
        "operation": None, "predicate": None,
    })
    alignment = _alignment(quote=source)
    alignment.items[0].source_excerpt = source
    with pytest.raises(ValueError, match="时间锚点或方向"):
        validate_candidate_alignment(batch, interpretation, coverage, output, alignment)


def test_quantifier_is_source_semantics_not_observation_selection_readiness() -> None:
    batch, interpretation, output, coverage, _ = _material()
    source = "所有计划访视均已完成"
    batch.owned_units[0].excerpt = "其他控制：" + source
    interpretation.statements[0].quoted_text = source
    interpretation.statements[0].decision_functions = ["action", "threshold"]
    atom = output.candidates[0].semantics.obligation_expression.groups[0].atoms[0]
    atom.statement = source
    atom.source_excerpts = [source]
    atom.evaluation = atom.evaluation.model_copy(update={
        "proposition": source, "predicate": None, "operation": None,
    })
    assert atom.evaluation.observation_policy.mode == "unresolved"
    alignment = SourceCandidateAlignment.model_validate({
        "version": SOURCE_CANDIDATE_ALIGNMENT_VERSION,
        "items": [{
            "statement_index": 0, "candidate_index": 0, "decision": "fully_expressed",
            "source_excerpt": source, "candidate_atom_quotes": [source],
            "unresolved_dimensions": [],
        }],
    })
    validate_candidate_alignment(batch, interpretation, coverage, output, alignment)
    atom.statement = "任一计划访视均已完成"
    alignment.items[0].candidate_atom_quotes = [atom.statement]
    with pytest.raises(ValueError, match="数量范围"):
        validate_candidate_alignment(batch, interpretation, coverage, output, alignment)


def test_named_visit_action_is_not_a_relative_date_window() -> None:
    batch, interpretation, output, coverage, _ = _material()
    source = "筛选期内完成统一的登记与评估流程。"
    batch.owned_units[0].excerpt = "其他控制：" + source
    statement = interpretation.statements[0]
    statement.quoted_text = source
    statement.force = "descriptive"
    statement.decision_functions = ["action", "time_validity"]
    statement.time_words = ["筛选期内"]
    candidate = output.candidates[0].semantics
    atom = candidate.obligation_expression.groups[0].atoms[0]
    atom.kind = ControlObligationKind.COMPLETE_OR_VERIFY
    atom.statement = source
    atom.source_excerpts = [source]
    atom.evaluation = atom.evaluation.model_copy(update={
        "determination_mode": "semantic", "proposition": source,
        "operation": None, "predicate": None,
    })
    alignment = SourceCandidateAlignment.model_validate({
        "version": SOURCE_CANDIDATE_ALIGNMENT_VERSION,
        "items": [{
            "statement_index": 0, "candidate_index": 0,
            "decision": "fully_expressed", "source_excerpt": source,
            "candidate_atom_quotes": [source], "unresolved_dimensions": [],
        }],
    })
    assert simple_visit_action_preserves_time(batch, statement, candidate)
    validate_candidate_alignment(batch, interpretation, coverage, output, alignment)
    candidate.review_node_bindings[0].workflow_stage_id = "stage:baseline"
    assert not simple_visit_action_preserves_time(batch, statement, candidate)
    with pytest.raises(ValueError, match="时间锚点或方向"):
        validate_candidate_alignment(batch, interpretation, coverage, output, alignment)
    candidate.review_node_bindings[0].workflow_stage_id = "stage:screening:one"
    statement.time_words = ["基线前6个月内"]
    assert not simple_visit_action_preserves_time(batch, statement, candidate)
    with pytest.raises(ValueError, match="来源时点"):
        validate_candidate_alignment(batch, interpretation, coverage, output, alignment)


def test_split_obligations_preserve_and_but_not_or() -> None:
    batch, interpretation, output, coverage, _ = _material()
    scope = "进入基线前"
    source = "全部待确认事项已完成处理且处理依据已记录"
    first = "全部待确认事项已完成处理"
    second = "处理依据已记录"
    batch.owned_units[0].excerpt = scope + "，" + source
    statement = interpretation.statements[0]
    statement.quoted_text = source
    statement.scope_quote = scope
    statement.decision_functions = ["action", "threshold"]
    candidate = output.candidates[0].semantics
    atom = candidate.obligation_expression.groups[0].atoms[0]
    atom.kind = ControlObligationKind.COMPLETE_OR_VERIFY
    atom.statement = scope + "，" + first
    atom.source_excerpts = [atom.statement]
    atom.evaluation = atom.evaluation.model_copy(update={
        "determination_mode": "semantic", "proposition": atom.statement,
        "operation": None, "predicate": None,
    })
    sibling = atom.model_copy(deep=True)
    sibling.statement = second
    sibling.source_excerpts = [second]
    sibling.evaluation = sibling.evaluation.model_copy(update={"proposition": second})
    candidate.obligation_expression.groups[0].atoms.append(sibling)
    alignment = SourceCandidateAlignment.model_validate({
        "version": SOURCE_CANDIDATE_ALIGNMENT_VERSION,
        "items": [{
            "statement_index": 0, "candidate_index": 0, "decision": "fully_expressed",
            "source_excerpt": source,
            "candidate_atom_quotes": [atom.statement, sibling.statement],
            "unresolved_dimensions": [],
        }],
    })
    validate_candidate_alignment(batch, interpretation, coverage, output, alignment)
    atom.evaluation = atom.evaluation.model_copy(update={
        "proposition": "任一待确认事项已完成处理",
    })
    with pytest.raises(ValueError, match="数量范围"):
        validate_candidate_alignment(batch, interpretation, coverage, output, alignment)
    atom.evaluation = atom.evaluation.model_copy(update={"proposition": atom.statement})
    statement.quoted_text = source.replace("且", "或")
    batch.owned_units[0].excerpt = scope + "，" + statement.quoted_text
    alignment.items[0].source_excerpt = statement.quoted_text
    with pytest.raises(ValueError, match="完整合取内容"):
        validate_candidate_alignment(batch, interpretation, coverage, output, alignment)


def test_split_obligations_preserve_leading_scope_without_ignoring_a_conjunct() -> None:
    prefix = "该受试者进入基线节点前"
    first = "与其相关的上一阶段全部待确认事项必须同时满足已完成处理"
    second = "处理依据已记录"
    atoms = [
        SimpleNamespace(source_excerpts=[first], statement=first,
                        evaluation=SimpleNamespace(proposition=f"{prefix}，{first}")),
        SimpleNamespace(source_excerpts=[second], statement=second,
                        evaluation=SimpleNamespace(proposition=second)),
    ]
    assert _split_obligations_cover_source(f"{prefix}，{first}且{second}", "", atoms)
    assert not _split_obligations_cover_source(f"{prefix}，{first}或{second}", "", atoms)
    assert not _split_obligations_cover_source(f"{prefix}，{first}且{second}且记录日期", "", atoms)
    assert not _split_obligations_cover_source(f"研究者确认后，{first}且{second}", "", atoms)
    atoms[0].evaluation.proposition = first
    assert not _split_obligations_cover_source(f"{prefix}，{first}且{second}", "", atoms)


def test_source_coverage_uses_hydrated_identity_after_candidate_reordering() -> None:
    batch, interpretation, _, coverage, _ = _material()
    first = _candidate().model_copy(update={"exception_expression": None})
    second = first.model_copy(deep=True)
    second.title = "另一有源审核要求"
    wire = _wire(candidate=first)
    wire.candidate_drafts.append(second)
    output = hydrate_protocol_control_agent_output(wire, batch)
    if output.candidates[0].title == first.title:
        wire.candidate_drafts.reverse()
        output = hydrate_protocol_control_agent_output(wire, batch)
    assert output.candidates[0].title != wire.candidate_drafts[0].title
    mapped = hydrated_source_coverage_indexes(
        batch, wire, output,
        [coverage[0].model_copy(update={"candidate_indexes": [0]})],
    )
    assert mapped[0].candidate_indexes == [1]
    assert output.candidates[mapped[0].candidate_indexes[0]].title == wire.candidate_drafts[0].title


def test_saved_alignment_preserves_wire_identity_after_hydration_reorders() -> None:
    batch, interpretation, _, _, review = _material()
    age = _candidate().model_copy(update={"exception_expression": None})
    medication = _candidate_for_second_unit()
    wire = _wire_with_two_candidates(medication, age)
    output = hydrate_protocol_control_agent_output(wire, batch)
    assert output.candidates[0].title == age.title
    coverage = source_statement_coverage(batch, interpretation, wire)
    assert coverage[0].action_candidate_indexes == [1]
    coverage[0] = coverage[0].model_copy(update={
        "status": "semantically_aligned", "candidate_indexes": [0],
    })
    alignment = _alignment().model_copy(deep=True)
    alignment.items[0].candidate_index = 1
    alignment = bind_candidate_alignment(
        batch, interpretation, coverage, wire, alignment,
        alignment.model_dump_json(exclude={"proofs"}),
    )
    result = ProtocolControlAgentRunResult(
        status="已解析", batch_id=batch.batch_id, session_id="source-review",
        attempts=[ProtocolControlAgentAttempt(
            attempt=1, session_id="source-review", raw_output_sha256="a" * 64,
            outcome="parsed",
        )],
        final_output=output, source_interpretation=interpretation,
        source_statement_coverage=hydrated_source_coverage_indexes(
            batch, wire, output, [coverage[0].model_copy(update={"candidate_indexes": [1]}), *coverage[1:]],
        ),
        source_target_review=review, source_candidate_alignment=alignment,
        partial_wire=wire,
    )
    _validate_saved_source_review(batch, result)
    invalid = result.model_copy(deep=True)
    invalid.source_statement_coverage[0].candidate_indexes = [1]
    with pytest.raises(ValueError, match="覆盖账不一致"):
        _validate_saved_source_review(batch, invalid)
