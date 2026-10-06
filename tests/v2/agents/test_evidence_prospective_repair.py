"""Future occurrence recovery withdraws certainty, not original records or siblings."""
from copy import deepcopy
import json

import pytest

from app.agents.evidence_normalizer import EvidenceNormalizerRunner, DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE
from tests.v2.agents.test_fact_context_sources import _payload, _source_input
from tests.v2.agents.test_evidence_normalizer_adapter import _FakeTransport


def _pair():
    initial = _payload()
    fact = initial["fact_candidates"][0]
    fact.update(assertion_scope="prospective_or_conditional", profile_lane="medication", locator_ids=["loc-2"])
    fact["assertion_basis"]["contextual_qualifiers"] = []
    sibling = deepcopy(fact)
    sibling.update(candidate_ref="f2", assertion_scope="observed_state", profile_lane="test_exam_score",
        asserted_object="量表甲", raw_value="量表甲", canonical_value="量表甲", unit=None, locator_ids=["loc-1"])
    sibling["assertion_basis"].update(asserted_object="量表甲", assertion_text="量表甲", locator_id="loc-1")
    initial["fact_candidates"].append(sibling)
    initial["non_exposure_medication_fact_refs"] = ["f1"]
    proposed = deepcopy(initial)
    proposed["fact_candidates"][0].update(polarity="unknown", raw_value=None, canonical_value=None,
        unit=None, assertion_basis=None, supported_requirement_ids=[])
    proposed["non_exposure_medication_fact_refs"] = []
    return initial, proposed


def _run(initial, proposal, *, compact=False):
    if compact:
        from app.projections.normalizer_reference_aliases import NormalizerReferenceAliases
        aliases = NormalizerReferenceAliases.from_payload(_source_input().model_dump(mode="json"))
        initial, proposal = [aliases.transform(item) for item in (initial, proposal)]
    transport = _FakeTransport([(json.dumps(value, ensure_ascii=False), "future-session") for value in (initial, proposal)])
    result = EvidenceNormalizerRunner(max_transport_retries=0, max_schema_repairs=1).run(
        _source_input(), transport, prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
        require_current_draft=True, compact_references=compact)
    return result, transport


@pytest.mark.parametrize("compact", [False, True])
def test_unknown_target_and_classification_dependencies_recover_together(compact):
    initial, proposal = _pair()
    result, transport = _run(initial, proposal, compact=compact)
    assert len(transport.repair_prompts) == 1
    assert "肯定药物分类清单" in transport.repair_prompts[0][1]
    output = result.final_output
    assert output is not None and len(output.fact_candidates) == 2
    assert output.fact_candidates[0].polarity.value == "unknown"
    assert output.fact_candidates[1].polarity.value == "affirmed"
    assert not output.exposure_candidates and not output.event_candidates
    question = output.unresolved_items[0]
    assert question.code == "occurrence_not_confirmed" and question.gap_type is None
    assert question.affected_locator_ids == ["loc-2"]
    assert "项目乙2" in question.reason and "原始回答摘录（尚待核实）" in question.reason


@pytest.mark.parametrize("change", ["classification", "rename", "promote", "negate", "sibling", "source", "remove"])
def test_future_recovery_cannot_relabel_or_rewrite_unrelated_content(change):
    initial, proposal = _pair()
    fact = proposal["fact_candidates"][0]
    if change == "classification":
        proposal["non_exposure_medication_fact_refs"] = ["f1"]
    elif change == "rename":
        fact["asserted_object"] = "已经讲解要求"
    elif change == "promote":
        fact.update(assertion_scope="completed_action", polarity="affirmed", canonical_value=True)
    elif change == "negate":
        fact["polarity"] = "negated"
    elif change == "sibling":
        proposal["fact_candidates"][1]["canonical_value"] = 3
    elif change == "source":
        fact["locator_ids"] = ["loc-1"]
    else:
        proposal["fact_candidates"].pop(0)
    result, transport = _run(initial, proposal)
    assert result.final_output is None and len(transport.repair_prompts) == 1


@pytest.mark.parametrize("dependency", ["event_candidates", "exposure_candidates", "pending_context"])
def test_unsupported_withdrawal_or_pending_context_stops_before_another_read(dependency):
    initial, proposal = _pair()
    if dependency == "pending_context":
        initial["fact_candidates"][0]["assertion_basis"]["contextual_qualifiers"] = _payload()["fact_candidates"][0]["assertion_basis"]["contextual_qualifiers"]
        initial["fact_candidates"][0]["locator_ids"] = ["loc-1", "loc-2"]
    else:
        initial[dependency] = [{"candidate_ref": "dependent1", "fact_candidate_refs": ["f1"]}]
    result, transport = _run(initial, proposal)
    assert result.final_output is None and not transport.repair_prompts


@pytest.mark.parametrize("dependency", ["event_candidates", "exposure_candidates"])
@pytest.mark.parametrize("refs", [None, "f1", {"f1": True}, [None], [["f1"]], [""]])
def test_malformed_dependency_is_retained_failure_not_an_unhandled_recovery(refs, dependency):
    initial, proposal = _pair()
    initial[dependency] = [{"candidate_ref": "dependent1", "fact_candidate_refs": refs}]
    result, transport = _run(initial, proposal)
    assert result.final_output is None and not transport.repair_prompts
    assert result.attempts[0].outcome == "schema_invalid"
