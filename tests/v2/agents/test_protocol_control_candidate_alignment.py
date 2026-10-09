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
    with pytest.raises(ValueError, match="未核清范围"):
        _validate_saved_source_review(batch, restored)


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
