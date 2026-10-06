"""Question-only recovery preserves the original draft and all source identities."""
from copy import deepcopy
import hashlib
import json

import pytest

from app.agents.evidence_normalizer import (
    DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE, EvidenceNormalizerAgentResponse,
    EvidenceNormalizerRunner,
)
from app.agents.evidence_question_repair import QuestionClassificationRepair, replay_question_repair
from app.projections.normalizer_reference_aliases import NormalizerReferenceAliases
from tests.v2.agents.test_evidence_normalizer_adapter import _input, _bound_draft_payload, _requirement


def _case():
    inp = _input([_requirement("req-history", "既往史")])
    payload = _bound_draft_payload("req-history")
    payload["schema_version"] = "phase5/normalizer-draft/v5"
    payload["fact_candidates"][0]["assertion_scope"] = "observed_state"
    payload["fact_candidates"][0].update(raw_value=True, canonical_value=True)
    payload["unresolved_items"][0].update(
        code="ambiguous_date", message="原日期含义待核对", reason="原文的日期归属未确定",
        affected_requirement_ids=["req-history"], affected_locator_ids=["loc-2"],
        gap_type="interpretation_conflict",
    )
    return inp, payload


def _proposal(repair, gap="date_or_anchor_missing"):
    return {"policy": repair.schema()["properties"]["policy"]["const"],
        "precondition_sha256": repair.precondition, "input_scope_sha256": repair.input_scope,
        "changes": [{"index": i, "question_sha256": repair.targets[i], "gap_type": gap}
                    for i in repair.indices]}


class QuestionTransport:
    def __init__(self, inp, payload, mutation=None):
        self.inp, self.payload, self.mutation = inp, payload, mutation
        self.starts = self.proposals = self.full_repairs = 0
        self.prompt = None

    def start(self, *, prompt):
        self.starts += 1
        return EvidenceNormalizerAgentResponse(session_id="original",
            text=json.dumps(self.payload, ensure_ascii=False))

    def propose_question_classifications(self, *, prompt, output_schema):
        self.proposals += 1
        self.prompt = prompt
        repair = QuestionClassificationRepair(json.dumps(self.payload, ensure_ascii=False), self.inp, [0])
        proposed = _proposal(repair)
        if self.mutation:
            self.mutation(proposed)
        return EvidenceNormalizerAgentResponse(session_id="question-only", text=json.dumps(proposed))

    def continue_session(self, **kwargs):
        self.full_repairs += 1
        raise AssertionError("Question recovery must not request a replacement full draft")


@pytest.mark.parametrize("compact", [False, True])
def test_only_question_classification_changes_and_replay_matches_source(compact):
    inp, payload = _case()
    aliases = NormalizerReferenceAliases.from_payload(inp.model_dump(mode="json")) if compact else None
    raw = json.dumps(aliases.transform(payload) if aliases else payload, ensure_ascii=False)
    repair = QuestionClassificationRepair(raw, inp, [0], reference_aliases=aliases)
    composed, receipt = repair.apply(json.dumps(_proposal(repair)))
    expected = json.loads(raw)
    expected["unresolved_items"][0]["gap_type"] = "date_or_anchor_missing"
    assert json.loads(composed) == expected
    assert receipt["raw_output_sha256"] == hashlib.sha256(raw.encode()).hexdigest()
    assert receipt["original_response"] == raw
    output = replay_question_repair(receipt, inp, reference_aliases=aliases)
    assert output.fact_candidates[0].assertion_basis.assertion_text == "患者无糖尿病病史"
    assert output.unresolved_items[0].message == payload["unresolved_items"][0]["message"]
    assert output.unresolved_items[0].gap_type.value == "date_or_anchor_missing"


def test_runner_uses_one_source_bound_proposal_and_shares_existing_budget():
    inp, payload = _case()
    transport = QuestionTransport(inp, payload)
    result = EvidenceNormalizerRunner(max_transport_retries=0, max_schema_repairs=1).run(
        inp, transport, prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
        require_current_draft=True, allow_question_classification_repair=True)
    assert result.final_output is not None
    assert result.question_classification_receipt is not None
    assert (transport.starts, transport.proposals, transport.full_repairs) == (1, 1, 0)
    assert len(result.attempts) == 2
    # Only the question's source is included, not the entire frozen document/draft.
    assert "患者无糖尿病病史" not in transport.prompt
    exhausted = QuestionTransport(inp, payload)
    failed = EvidenceNormalizerRunner(max_transport_retries=0, max_schema_repairs=0).run(
        inp, exhausted, prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
        require_current_draft=True, allow_question_classification_repair=True)
    assert failed.final_output is None and exhausted.proposals == 0


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(precondition_sha256="0" * 64),
    lambda p: p.update(input_scope_sha256="0" * 64),
    lambda p: p["changes"][0].update(question_sha256="0" * 64),
    lambda p: p["changes"][0].update(index=1),
    lambda p: p["changes"][0].update(gap_type=None),
    lambda p: p["changes"][0].update(gap_type="required_procedure_not_done"),
    lambda p: p["changes"][0].update(gap_type="record_incomplete"),
    lambda p: p["changes"][0].update(message="没有研究者判断"),
    lambda p: p.update(fact_candidates=[]),
    lambda p: p.update(changes=[]),
])
def test_bad_or_declined_proposal_never_triggers_whole_answer_rewrite(mutation):
    inp, payload = _case()
    transport = QuestionTransport(inp, payload, mutation)
    result = EvidenceNormalizerRunner(max_transport_retries=0, max_schema_repairs=4).run(
        inp, transport, prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
        require_current_draft=True, allow_question_classification_repair=True,
        allow_candidate_partition=True)
    assert result.final_output is None
    assert result.question_classification_receipt is None
    assert (transport.starts, transport.proposals, transport.full_repairs) == (1, 1, 0)


@pytest.mark.parametrize("change", ["unknown_type", "other_requirement", "other_page", "extra_field", "valid_type"])
def test_question_recovery_cannot_borrow_invalid_scope_or_valid_question(change):
    inp, payload = _case()
    question = payload["unresolved_items"][0]
    if change == "unknown_type":
        question["gap_type"] = "made_up"
    elif change == "other_requirement":
        question["affected_requirement_ids"] = ["other-patient-requirement"]
    elif change == "other_page":
        question["affected_pages"] = [99]
    elif change == "extra_field":
        question["approved"] = True
    else:
        question["gap_type"] = "date_or_anchor_missing"
    with pytest.raises(ValueError):
        QuestionClassificationRepair(json.dumps(payload), inp, [0])


@pytest.mark.parametrize("key", ["original_response", "proposal_response", "input_scope_sha256", "composed_sha256"])
def test_saved_proof_cannot_replace_original_or_compose_different_content(key):
    inp, payload = _case()
    repair = QuestionClassificationRepair(json.dumps(payload), inp, [0])
    _, receipt = repair.apply(json.dumps(_proposal(repair)))
    corrupted = deepcopy(receipt)
    corrupted[key] = "0" * 64
    with pytest.raises((ValueError, KeyError)):
        replay_question_repair(corrupted, inp)


def test_other_candidate_source_error_remains_terminal_after_question_proposal():
    inp, payload = _case()
    payload["fact_candidates"][0]["assertion_basis"]["asserted_object"] = "原文没有的疾病"
    transport = QuestionTransport(inp, payload)
    result = EvidenceNormalizerRunner(max_transport_retries=0, max_schema_repairs=2).run(
        inp, transport, prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
        require_current_draft=True, allow_question_classification_repair=True)
    assert result.final_output is None
    assert transport.full_repairs == 0


def test_unclear_written_annotation_is_retained_not_replaced_with_missing_judgment():
    inp, payload = _case()
    question = payload["unresolved_items"][0]
    question.update(gap_type="professional_judgment", message="研究者已有批注，缩写尚不能读清",
        reason="需核对原有批注与具体项目的关联")
    repair = QuestionClassificationRepair(json.dumps(payload), inp, [0])
    _, receipt = repair.apply(json.dumps(_proposal(repair, "ocr_or_parse_risk")))
    output = replay_question_repair(receipt, inp)
    assert output.unresolved_items[0].message == "研究者已有批注，缩写尚不能读清"
    assert output.unresolved_items[0].gap_type.value == "ocr_or_parse_risk"
    assert output.unresolved_items[0].affected_requirement_ids == ["req-history"]


@pytest.mark.parametrize("corrupt", [None, "answer", "scope", "retained"])
def test_composed_classification_then_existing_partition_keeps_independent_fact(corrupt):
    inp, payload = _case()
    bad = deepcopy(payload["fact_candidates"][0])
    bad["candidate_ref"] = "bad"
    bad["assertion_basis"]["asserted_object"] = "原文没有的疾病"
    payload["fact_candidates"].append(bad)
    transport = QuestionTransport(inp, payload)
    result = EvidenceNormalizerRunner(max_transport_retries=0, max_schema_repairs=1).run(
        inp, transport, prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
        require_current_draft=True, allow_question_classification_repair=True, allow_candidate_partition=True)
    assert result.final_output is not None
    assert len(result.final_output.fact_candidates) == 1
    question, partition = result.question_classification_receipt, deepcopy(result.candidate_partition_receipt)
    assert partition["raw_output_sha256"] == question["composed_sha256"]
    assert question["raw_output_sha256"] != partition["raw_output_sha256"]
    assert partition["quarantined_candidate_refs"] == ["bad"]
    assert transport.full_repairs == 0
    if corrupt == "answer":
        partition["original_response"] = question["original_response"]
    elif corrupt == "scope":
        partition["input_sha256"] = "0" * 64
    elif corrupt == "retained":
        partition["retained_draft"]["fact_candidates"][0]["raw_value"] = "changed"
    if corrupt:
        with pytest.raises(ValueError):
            replay_question_repair(question, inp, partition_receipt=partition)
    else:
        assert replay_question_repair(question, inp, partition_receipt=partition) == result.final_output
