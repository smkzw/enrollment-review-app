"""Synthetic source questions; no model, protocol originals or adoption."""

import hashlib
import json
from dataclasses import asdict

import pytest

from app.agents.protocol_control_source_interpretation import (
    SOURCE_INTERPRETATION_VERSION, SourceInterpretation, SourceStatement,
    apply_source_scope_question_recheck, build_source_scope_question_prompt,
    can_recheck_source_scope_question, build_source_scope_correction_prompt,
    SourceScopeCorrection, apply_source_scope_correction,
)
from app.services import protocol_control_execution as execution
from tests.v2.protocols.test_slice58c_control_deconstructor import _batch, _wire, _candidate


def _native_row_target_material(*, wrong_row=False, label="操作甲^7", hashed=False):
    from app.domain.contracts.protocol_controls import (
        ProtocolStructureUnit, TableCellContext, KnownRequiredProcedureTarget,
    )
    from app.agents.protocol_control_source_interpretation import (
        SourceStatementCoverage, SourceTargetReview, SourceTargetReviewItem,
        SOURCE_TARGET_REVIEW_VERSION,
    )
    refs = ["body.t0.r4.c0.p0", "body.t0.r4.c1.p0"]
    spans = ["sha-label", "sha-mark"] if hashed else [f"snapshot::{ref}" for ref in refs]
    unit = ProtocolStructureUnit(
        structure_unit_id="action-row", source_ref="body.t0.r4",
        member_source_refs=refs, member_texts=[label, "X"],
        member_source_span_ids=[[spans[0]], [spans[1]]], source_span_ids=spans,
        unit_kind="table_row", heading_path=["流程表"], source_order=4,
        study_phase="phase_ii", phase_scopes=["shared"], excerpt=f"{label} | X",
        table_context=TableCellContext(table_path=(4, 0), row_index=4, column_index=0,
                                      member_cell_paths=[(4, 0), (4, 1)]),
    )
    footnote = "操作甲与操作乙均在同一访视执行。"
    target = KnownRequiredProcedureTarget(
        catalog_item_id="existing-action", label="操作乙" if wrong_row else label,
        visit_instance="baseline", review_stage="baseline", position=1,
        source_span_ids=sorted(["common-note", "other-row-label" if wrong_row else spans[0]]),
        source_excerpts=[footnote, "操作乙" if wrong_row else label],
    )
    batch = _batch().model_copy(update={
        "owned_units": [unit], "context_units": [], "owned_structure_unit_ids": [unit.structure_unit_id],
        "context_structure_unit_ids": [], "owned_source_span_ids": sorted(spans),
        "context_source_span_ids": [], "known_official_targets": [], "known_procedure_targets": [target],
    })
    source = SourceInterpretation(version=SOURCE_INTERPRETATION_VERSION,
        statements=[SourceStatement(structure_unit_id=unit.structure_unit_id,
            quoted_text=unit.excerpt, force="required", decision_functions=["action"], time_words=[])],
        units_without_statement=[])
    coverage = [SourceStatementCoverage(statement_index=0, structure_unit_id=unit.structure_unit_id,
        disposition="required_procedure", status="linked_only", linked_procedure_target_ids=[target.catalog_item_id])]
    review = SourceTargetReview(version=SOURCE_TARGET_REVIEW_VERSION, items=[SourceTargetReviewItem(
        statement_index=0, decision="covered_by_procedure", target_id=target.catalog_item_id,
        source_action_excerpt="操作甲", target_action_excerpt=footnote, unresolved_aspects=[])])
    return batch, source, coverage, review


@pytest.mark.parametrize("label,hashed", [("操作甲^7", False), ("操作甲^7", True), ("操作甲 | 记录^7", True)])
def test_native_procedure_target_uses_row_identity_not_shared_note(label, hashed):
    from app.agents.protocol_control_source_interpretation import (
        validate_source_target_review, validated_source_review_seed,
        SourceTargetReviewValidationError, target_action_established,
        build_source_target_review_prompt,
    )
    batch, source, coverage, review = _native_row_target_material(label=label, hashed=hashed)
    validate_source_target_review(batch, source, coverage, review)
    assert "native_row_link_diagnostic" not in build_source_target_review_prompt(batch, source, coverage)
    wrong, source, coverage, review = _native_row_target_material(wrong_row=True, label=label, hashed=hashed)
    with pytest.raises(SourceTargetReviewValidationError) as error:
        validate_source_target_review(wrong, source, coverage, review)
    assert error.value.code == "TARGET_PROCEDURE_ROW_UNPROVEN"
    assert error.value.statement_index == 0 and error.value.retry_class == "single_statement"
    assert error.value.source_refs == tuple(wrong.owned_units[0].source_span_ids)
    assert validated_source_review_seed(wrong, source, coverage, review) is None
    assert not target_action_established(wrong, source.statements[0], wrong.known_procedure_targets[0])
    prompt = build_source_target_review_prompt(wrong, source, coverage)
    packet = json.loads(next(line.removeprefix("待核陈述：") for line in prompt.splitlines()
                             if line.startswith("待核陈述：")))[0]
    assert packet["native_row_link_diagnostic"]["rejected_target_ids"] == ["existing-action"]
    # Only the model can propose an increment; the host does not rewrite the saved wire.
    increment = review.model_copy(deep=True)
    increment.items[0].decision = "additional_requirement"
    increment.items[0].unresolved_aspects = ["原文操作未被该流程项目覆盖"]
    validate_source_target_review(wrong, source, coverage, increment)
    assert coverage[0].linked_procedure_target_ids == ["existing-action"]


def test_native_row_guard_does_not_replace_narrative_semantic_review():
    from app.agents.protocol_control_source_interpretation import validate_source_target_review
    batch, source, coverage, review = _native_row_target_material(wrong_row=True)
    batch.owned_units[0].table_context = None
    validate_source_target_review(batch, source, coverage, review)


def material():
    batch = _batch().model_copy(deep=True)
    quote = "既往发生甲事件或准备期发现乙结果。"
    batch.owned_units[0].excerpt = quote
    source = SourceInterpretation(version=SOURCE_INTERPRETATION_VERSION,
        statements=[SourceStatement(structure_unit_id=batch.owned_units[0].structure_unit_id,
            quoted_text=quote, force="required", decision_functions=["action"],
            scope_quote=None, affected_stage=None, time_words=["既往", "准备期"],
            exception_words=None, unresolved=["共同阶段未确定"])],
        units_without_statement=[batch.owned_units[1].structure_unit_id])
    proposal = SourceInterpretation(version=source.version,
        statements=[source.statements[0].model_copy(update={"unresolved": []})],
        units_without_statement=[])
    return batch, source, proposal


def test_question_proposal_preserves_source_and_does_not_adopt_a_rule():
    batch, source, proposal = material()
    prompt = build_source_scope_question_prompt(batch, source, 0)
    assert "没有共同 affected_stage 本身不构成原文歧义" in prompt
    revised = apply_source_scope_question_recheck(batch, source, 0, proposal)
    assert revised.statements[0].unresolved == []
    assert source.statements[0].unresolved == ["共同阶段未确定"]
    assert revised.units_without_statement == source.units_without_statement
    assert revised.statements[0].affected_stage is None


@pytest.mark.parametrize("field,value", [
    ("quoted_text", "既往发生甲事件且准备期发现乙结果。"),
    ("time_words", ["准备期"]), ("affected_stage", "准备期"),
    ("decision_functions", ["background"]), ("structure_unit_id", "another-unit"),
])
def test_question_proposal_cannot_change_any_frozen_semantics(field, value):
    batch, source, proposal = material()
    setattr(proposal.statements[0], field, value)
    with pytest.raises(ValueError):
        apply_source_scope_question_recheck(batch, source, 0, proposal)


def test_real_uncertainty_is_retained_and_single_time_is_not_selected():
    batch, source, proposal = material()
    proposal.statements[0].unresolved = ["原文未说明两个子条件的关系"]
    revised = apply_source_scope_question_recheck(batch, source, 0, proposal)
    assert revised.statements[0].unresolved == proposal.statements[0].unresolved
    assert not can_recheck_source_scope_question(source.statements[0].model_copy(
        update={"time_words": ["既往"]}))
    assert not can_recheck_source_scope_question(proposal.statements[0].model_copy(
        update={"time_words": ["既往", "随访期"]}))


@pytest.mark.parametrize("change", [None, "precondition", "source_refs", "budget", "raw_hash"])
def test_seed_replay_binds_the_actual_local_answer_and_original_budget(change):
    batch, source, proposal = material()
    revised = apply_source_scope_question_recheck(batch, source, 0, proposal)
    current = execution._deep_component_identity({}, execution.DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE)
    detail = dict(workflow_phase="source_scope_question_recheck", code="SOURCE_SCOPE_QUESTION_RECHECK",
        statement_id=0, json_path="statements[0].unresolved",
        source_refs=list(batch.owned_units[0].source_span_ids),
        precondition_sha256=hashlib.sha256(source.statements[0].model_dump_json().encode()).hexdigest())
    attempts = [dict(attempt=i + 1, outcome="parsed", session_id=f"source-{i}",
                    raw_output_text=text, raw_output_sha256=hashlib.sha256(text.encode()).hexdigest(),
                    error_classes=[], **({"error_detail": detail} if i else {}))
                for i, text in enumerate([source.model_dump_json(), proposal.model_dump_json()])]
    saved = dict(component_identity=current, prompt_template_sha256=current["prompt_material_sha256"],
                 attempts=attempts, source_interpretation=revised.model_dump(mode="json"))
    if change == "precondition":
        detail["precondition_sha256"] = "0" * 64
    if change == "source_refs":
        detail["source_refs"] = ["other-patient"]
    if change == "raw_hash":
        attempts[1]["raw_output_sha256"] = "0" * 64
    args = dict(source_job_id="old", step_id="deep", checkpoint_id="checkpoint",
                max_source_corrections=0 if change == "budget" else 1)
    if change == "raw_hash":
        with pytest.raises(ValueError, match="摘要损坏"):
            execution._revalidated_source_seed_proof(batch, saved, current, **args)
    else:
        proof = execution._revalidated_source_seed_proof(batch, saved, current, **args)
        assert bool(proof) is (change is None)
        if proof:
            assert proof["schema_version"] == "phase5/revalidated-source-seed-proof/v5"
            assert proof["scope_question_indexes"] == [0]
            assert proof["discarded"] == ["partial_wire", "source_target_review",
                "source_statement_coverage", "source_candidate_alignment", "session_id"]


def test_scope_prompt_shows_native_headers_without_enabling_arbitrary_context(monkeypatch):
    from app.agents import protocol_control_source_interpretation as module
    from app.protocols.procedure_catalog import ScheduleColumnScope
    batch, source, _ = material()
    column = ScheduleColumnScope(structure_unit_id=batch.owned_units[0].structure_unit_id,
        cell_path=(4, 2), cell_source_ref="body.t0.r4.c2.p0", column_index=2,
        header_text="基线期 / V2 / D1", header_source_refs=("body.t0.r0.c2.p0",),
        review_stage=None, boundary_side="unresolved", visit_unresolved=False)
    monkeypatch.setattr(module, "schedule_column_scope", lambda *_: (column,))
    prompt = build_source_scope_correction_prompt(batch, source.statements[0], "范围待核")
    assert "标记列原生来源" in prompt and asdict(column)["header_source_refs"][0] in prompt
    assert "本行全部标记列" in prompt
    with pytest.raises(ValueError):
        apply_source_scope_correction(batch, source, 0, SourceScopeCorrection(
            version="phase5/control-source-scope-correction/v1", structure_unit_id="su-01",
            scope_quote="无来源访视", affected_stage=None, time_words=source.statements[0].time_words))


@pytest.mark.parametrize("mixed", [False, True])
def test_native_column_question_uses_real_headers_not_an_unrelated_action_target(mixed):
    from app.domain.contracts.protocol_controls import ProtocolStructureUnit, TableCellContext
    from app.domain.contracts.enums import StudyPhase, PhaseScope

    def row(index, values):
        refs = [f"body.t0.r{index}.c{column}.p0" for column, _ in values]
        return ProtocolStructureUnit(structure_unit_id=f"row-{index}", source_ref=f"body.t0.r{index}",
            source_order=index, member_source_refs=refs, member_texts=[text for _, text in values],
            source_span_ids=[f"snapshot::{ref}" for ref in refs], unit_kind="table_row",
            heading_path=["日程"], study_phase=StudyPhase.PHASE_II, phase_scopes=[PhaseScope.SHARED],
            excerpt=" | ".join(text for _, text in values),
            table_context=TableCellContext(table_path=(index, 0), row_index=index, column_index=0,
                member_cell_paths=[(index, col) for col, _ in values]))

    headers = [row(0, [(0, "阶段"), (1, "筛选期"), (2, "基线期")]),
               row(1, [(0, "访视"), (1, "V1"), (2, "V2")])]
    action = row(4, [(0, "执行操作甲"), (1, "X")] + ([(2, "X")] if mixed else []))
    batch = _batch().model_copy(update={"owned_units": [action], "context_units": headers})
    source = SourceInterpretation(version=SOURCE_INTERPRETATION_VERSION,
        statements=[SourceStatement(structure_unit_id=action.structure_unit_id,
            quoted_text="执行操作甲", force="required", decision_functions=["action"],
            time_words=[], unresolved=["标记格没有访视关系"])], units_without_statement=[])
    assert can_recheck_source_scope_question(source.statements[0], batch)
    prompt = build_source_scope_question_prompt(batch, source, 0)
    assert "body.t0.r0.c1.p0" in prompt
    proposal = source.model_copy(deep=True)
    proposal.statements[0].unresolved = []
    proposal.statements[0].scope_quote = "筛选期"
    proposal.statements[0].affected_stage = "筛选期"
    proposal.statements[0].time_words = ["筛选期"]
    if mixed:
        with pytest.raises(ValueError, match="共享范围"):
            apply_source_scope_question_recheck(batch, source, 0, proposal)
    else:
        revised = apply_source_scope_question_recheck(batch, source, 0, proposal)
        assert revised.statements[0].affected_stage == "筛选期"
        assert source.statements[0].unresolved and source.statements[0].scope_quote is None


@pytest.mark.parametrize("malicious,budget", [(False, 1), (True, 1), (False, 0)])
def test_runner_recheck_shares_budget_retains_failure_and_cannot_complete_without_consumer(malicious, budget):
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunner, ProtocolControlAgentResponse
    batch, source, proposal = material()
    if malicious:
        proposal.statements[0].quoted_text = "既往发生甲事件且准备期发现乙结果。"

    class Transport:
        question_calls = 0
        author_calls = 0

        def start_source_interpretation(self, *, prompt):
            self.question_calls += 1
            return ProtocolControlAgentResponse(session_id="question", text=proposal.model_dump_json())

        def start(self, *, prompt):
            self.author_calls += 1
            raise RuntimeError("synthetic author unavailable; source proposal is not adoption")

    transport = Transport()
    result = ProtocolControlAgentRunner(max_schema_repairs=budget, max_transport_retries=0).run(
        batch, transport, resume_source_interpretation=source)
    assert transport.question_calls == bool(budget)
    assert transport.author_calls == (0 if malicious else 1)
    assert result.final_output is None and result.status == "需要核对"
    assert result.repair_used is bool(budget)
    assert result.source_interpretation.statements[0].quoted_text == source.statements[0].quoted_text
    assert bool(result.source_interpretation.statements[0].unresolved) == (malicious or not budget)
    if budget:
        assert result.attempts[0].error_detail["workflow_phase"] == "source_scope_question_recheck"
        assert result.attempts[0].outcome == ("schema_invalid" if malicious else "parsed")


def question_record(batch, statement, proposal, index=0):
    text = proposal.model_dump_json()
    return dict(attempt=1, session_id="old-question", outcome="parsed", error_classes=[],
        raw_output_text=text, raw_output_chars=len(text),
        raw_output_sha256=hashlib.sha256(text.encode()).hexdigest(),
        error_detail=dict(workflow_phase="source_scope_question_recheck", code="SOURCE_SCOPE_QUESTION_RECHECK",
            statement_id=index, json_path=f"statements[{index}].unresolved",
            source_refs=list(batch.owned_units[index].source_span_ids),
            precondition_sha256=hashlib.sha256(statement.model_dump_json().encode()).hexdigest()))


@pytest.mark.parametrize("kind,budget", [("valid", 2), ("transport", 2), ("malicious", 2), ("valid", 1)])
def test_saved_wire_continues_only_unwitnessed_question_without_resetting_paid_history(kind, budget):
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunner, ProtocolControlAgentResponse
    batch, source, _ = material()
    batch.owned_units[0].excerpt = _batch().owned_units[0].excerpt + "；" + batch.owned_units[0].excerpt
    source.units_without_statement = []
    second_quote = "既往发生丙事件或准备期发现丁结果。"
    batch.owned_units[1].excerpt = second_quote
    source.statements.append(source.statements[0].model_copy(update={
        "structure_unit_id": batch.owned_units[1].structure_unit_id, "quoted_text": second_quote}))
    old_proposal = SourceInterpretation(version=source.version,
        statements=[source.statements[0].model_copy(deep=True)], units_without_statement=[])
    history = [question_record(batch, source.statements[0], old_proposal)]
    proposal = SourceInterpretation(version=source.version,
        statements=[source.statements[1].model_copy(update={"unresolved": []})], units_without_statement=[])
    if kind == "malicious":
        proposal.statements[0].quoted_text = second_quote.replace("或", "且")
    wire = _wire(candidate=_candidate())
    before = wire.model_dump_json()

    class Transport:
        question_calls = 0

        def start_source_interpretation(self, *, prompt):
            self.question_calls += 1
            assert second_quote in prompt
            if kind == "transport":
                raise RuntimeError("synthetic connection failure")
            return ProtocolControlAgentResponse(session_id="new-question", text=proposal.model_dump_json())

        def start(self, *, prompt):
            pytest.fail("已过门禁的草稿不能因为补核来源问题而全组重新生成")

    transport = Transport()
    result = ProtocolControlAgentRunner(max_schema_repairs=budget, max_transport_retries=0).run(
        batch, transport, resume_wire=wire, resume_source_interpretation=source,
        resume_source_scope_question_history=history, resume_session_id="saved-wire",
        output_validator=lambda _: None)
    assert transport.question_calls == (budget > 1)
    assert result.partial_wire.model_dump_json() == before
    assert source.statements[1].unresolved
    assert result.source_interpretation.statements[0] == source.statements[0]
    assert bool(result.source_interpretation.statements[1].unresolved) == (kind != "valid" or budget == 1)
    assert len(result.source_scope_question_history) == (2 if budget > 1 else 1)
    assert "source_scope_question_history" not in result.model_dump()
    assert result.final_output is None
    if kind in {"malicious", "transport"}:
        assert result.session_id == "saved-wire"


@pytest.mark.parametrize("change", ["raw", "refs", "index"])
def test_corrupt_saved_question_history_is_rejected_before_any_model_call(change):
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunner
    batch, source, proposal = material()
    record = question_record(batch, source.statements[0], proposal)
    if change == "raw":
        record["raw_output_sha256"] = "0" * 64
    elif change == "refs":
        record["error_detail"]["source_refs"] = ["another-source"]
    else:
        record["error_detail"]["statement_id"] = 999
    with pytest.raises(ValueError, match="历史核对"):
        ProtocolControlAgentRunner().run(batch, object(), resume_source_interpretation=source,
            resume_source_scope_question_history=[record])


def test_history_checkpoint_consumer_retains_actual_answers_and_never_duplicates_them():
    batch, source, proposal = material()
    history = [question_record(batch, source.statements[0], proposal)]
    assert execution._saved_source_scope_question_history({"attempts": history}) == history
    assert execution._saved_source_scope_question_history({
        "attempts": history, "source_scope_question_history": history}) == history
    with pytest.raises(ValueError, match="核对账"):
        execution._saved_source_scope_question_history({"source_scope_question_history": "broken"})


def test_changed_source_cannot_reuse_unqualified_old_covered_item_beside_a_valid_sibling():
    import json
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunner, ProtocolControlAgentResponse, source_statement_coverage
    from app.agents.protocol_control_source_interpretation import (
        SOURCE_TARGET_REVIEW_VERSION, SourceTargetReview, SourceTargetReviewItem,
    )
    batch, source, _ = material()
    source.statements[0].force = "descriptive"
    source.statements[0].decision_functions = ["background"]
    source.units_without_statement = []
    source.statements.append(SourceStatement(structure_unit_id=batch.owned_units[1].structure_unit_id,
        quoted_text=batch.owned_units[1].excerpt, force="descriptive", decision_functions=["background"],
        time_words=[], unresolved=[]))
    wire = _wire()
    coverage = source_statement_coverage(batch, source, wire)
    old = SourceTargetReview(version=SOURCE_TARGET_REVIEW_VERSION, items=[
        SourceTargetReviewItem(statement_index=index, decision="background_context",
            source_action_excerpt=statement.quoted_text, non_control_basis_excerpt=statement.quoted_text)
        for index, statement in enumerate(source.statements)])
    proposal = SourceInterpretation(version=source.version,
        statements=[source.statements[0].model_copy(update={"unresolved": []})], units_without_statement=[])

    class Transport:
        calls = 0

        def start_source_interpretation(self, *, prompt):
            return ProtocolControlAgentResponse(session_id="question", text=proposal.model_dump_json())

        def start_source_target_review(self, *, prompt):
            self.calls += 1
            packet = json.loads(prompt.split("待核陈述：", 1)[1].split("\n冻结已有目标：", 1)[0])
            assert [item["statement_index"] for item in packet] == [0]
            reviewed = SourceTargetReview(version=SOURCE_TARGET_REVIEW_VERSION, items=[
                SourceTargetReviewItem(statement_index=0, decision="unresolved",
                    source_action_excerpt=source.statements[0].quoted_text,
                    unresolved_aspects=["来源疑问已变，旧覆盖不能替代本次核查"])])
            return ProtocolControlAgentResponse(session_id="review", text=reviewed.model_dump_json())

    transport = Transport()
    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(
        batch, transport, resume_wire=wire, resume_source_interpretation=source,
        resume_session_id="saved-wire", resume_source_target_review=old,
        resume_source_statement_coverage=coverage, output_validator=lambda _: None)
    assert transport.calls == 1
    assert result.final_output is None and result.partial_wire == wire
    assert {item.statement_index: item.decision for item in result.source_target_review.items} == {
        0: "unresolved", 1: "background_context"}
