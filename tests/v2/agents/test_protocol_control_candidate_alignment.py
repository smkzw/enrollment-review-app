"""Source-to-candidate alignment must survive the product save/read boundary."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domain.contracts.enums import Comparator
from app.agents.protocol_control_candidate_alignment import (
    SOURCE_CANDIDATE_ALIGNMENT_VERSION,
    SourceCandidateAlignment,
    _split_obligations_cover_source,
    candidate_alignment_response_format,
    bind_candidate_alignment,
    validate_candidate_alignment,
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
    simple_visit_action_preserves_time,
)
from app.domain.contracts.protocol_controls import ControlObligationKind
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
