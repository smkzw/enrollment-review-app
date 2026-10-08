"""Synthetic source questions; no model, protocol originals or adoption."""

import hashlib
from dataclasses import asdict

import pytest

from app.agents.protocol_control_source_interpretation import (
    SOURCE_INTERPRETATION_VERSION, SourceInterpretation, SourceStatement,
    apply_source_scope_question_recheck, build_source_scope_question_prompt,
    can_recheck_source_scope_question, build_source_scope_correction_prompt,
    SourceScopeCorrection, apply_source_scope_correction,
)
from app.services import protocol_control_execution as execution
from tests.v2.protocols.test_slice58c_control_deconstructor import _batch


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
