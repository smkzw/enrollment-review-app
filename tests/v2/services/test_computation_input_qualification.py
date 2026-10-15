"""Synthetic source/semantic counterexamples, not patient gold or adoption."""
from types import SimpleNamespace

import pytest

from app.domain.contracts.computation_input import ComputationInputContext
from app.domain.contracts.source_computation import SourceComputation, SourceQuantityBasis
from app.domain.expression import _canonical_unit
from app.domain.observation_relation_graph import analyze_computation_acquisitions
from app.domain.publication import canonical_hash
from app.services.binding_qualification_support import SEMANTIC_DIMENSIONS
from app.services.qualified_computation_input import qualify_computation_inputs
from tests.v2.llm.test_computation_input import group


def material():
    source = group()
    computation = SourceComputation(
        operator="mean", operator_ref={"statement_index": 0, "quote": "均值"},
        input_refs=[{"statement_index": 0, "quote": "全部两次采集"}],
        missing_policy="not_specified",
        declared_input_count={"value": 2, "number_text": "两",
                              "source": {"statement_index": 0, "quote": "全部两次采集"}},
        input_selection={"mode": "all", "source": {"statement_index": 0, "quote": "全部两次采集"}})
    members = [member.model_copy(update={
        "condition": {"predicate": {"unit": "bpm", "source_computation": computation.model_dump(mode="json")}},
        "source_policy_status": "present", "source_policies": [{"synthetic": True}],
    }) for member in source.members]
    body = source.model_dump(mode="json", exclude={"pair_id"})
    body.update(computation=computation.model_dump(mode="json"),
                members=[member.model_dump(mode="json") for member in members])
    source = ComputationInputContext(**body, pair_id=canonical_hash(body))
    facts = [SimpleNamespace(fact_id=member.fact_id, locator_ids=[member.locator_id],
                             source_observation_refs=[], source_candidate_ids=[])
             for member in source.members]
    judgments = [SimpleNamespace(source_admissibility="admissible", object_match="supported",
        denial_scope="compatible", temporal_role="not_applicable", attribute_match="derivation_operand",
        direct_operand_usable="not_usable", unresolved_reasons=["The aggregate has not been calculated."],
        public_agreement_key=lambda: ("synthetic-derivation",)) for _ in range(2)]
    records = [SimpleNamespace(pair_id=member.pair_id, identity_sha256=member.identity_sha256,
        fact_id=member.fact_id, locator_id=member.locator_id, structurally_valid=True, dual_agreement=True,
        structural=SimpleNamespace(body_matches_frozen=True, operand_shape="source_computation_input",
            source_policy_status="present", referenced_value=70, referenced_unit="bpm",
            pending_checks=["source_computation_input_set_unverified"]),
        lane_judgments=dict(zip(("main-A", "main-B"), judgments)), remaining_unverified=[],
        semantic_dimensions_rechecked=list(SEMANTIC_DIMENSIONS)) for member in source.members]
    comparison = {"group_id": source.pair_id,
        "agreed_source_descriptions": [
            {"pair_id": member.pair_id, "input_role": "raw_input", "input_excerpt": member.locator["excerpt"],
             "input_ref": computation.input_refs[0].model_dump(mode="json"), "token_kind": "unresolved",
             "date_role": "unresolved", "explanation": "只证明本记录属于计算输入。"}
            for member in source.members],
        "agreed_relationships": [["distinct_acquisition", *sorted(member.pair_id for member in source.members)]],
        "disputed_relationships": [], "lanes": {"main-A": {"unresolved_notes": []}, "main-B": {"unresolved_notes": []}}}
    evidence = {"pairs": [source], "summary": {"comparisons": [comparison]}, "summary_sha256": "a" * 64,
                "summary_artifact_sha256": "b" * 64, "payload": {"input_sha256": "c" * 64}}
    accounting = [{"predicate_identity_sha256": source.identity_sha256, "fact_accounting": [
        {"fact_id": fact.fact_id, "status": "candidates_in_both_lanes"} for fact in facts]}]
    return evidence, records, facts, accounting


def run(items):
    evidence, records, facts, accounting = items
    value, = qualify_computation_inputs(evidence, records, frozen_facts=facts, accounting=accounting)
    return value


def test_source_explicit_independence_and_complete_policy_produce_inputs_not_adoption():
    value = run(material())
    assert value["input_set_qualified"] and not value["authorized_clinical_adoption"]
    assert len(value["acquisition_fact_ids"]) == 2
    assert value["scope"] == "supplied_facts_only"
    assert all(notes["main-A"] == ["The aggregate has not been calculated."]
               for notes in value["derivation_operand_notes"].values())
    assert value["qualification_sha256"] == canonical_hash({
        key: item for key, item in value.items() if key != "qualification_sha256"})


@pytest.mark.parametrize("ordering_basis", [None, "unresolved"])
def test_saved_unknown_selection_never_qualifies_patient_operands(ordering_basis):
    items = material()
    computation = items[0]["pairs"][0].computation
    raw = computation.model_dump(mode="json")
    raw["input_selection"].update(mode="unresolved", ordering_basis=ordering_basis)
    items[0]["pairs"][0].computation = SourceComputation.model_validate(raw)
    result = run(items)
    assert not result["input_set_qualified"]
    assert not result["authorized_clinical_adoption"]
    assert "computation_selection_policy_unsupported" in result["reason_codes"]


@pytest.mark.parametrize("case, reason", [
    ("no_relation", "computation_acquisition_identity_unverified"),
    ("same_acquisition", "computation_required_inputs_incomplete"),
    ("wrong_membership", "computation_input_membership_unverified"),
    ("source_rejected", "computation_source_correspondence_unverified"),
    ("source_pending", "unknown_source_boundary"),
    ("missing_appearance", "computation_source_appearances_incomplete"),
    ("accounting_gap", "candidate_enumeration_incomplete"),
    ("shared_origin", "computation_acquisition_identity_unverified"),
    ("unit_mismatch", "computation_unit_unverified"),
    ("false_direct_derivation", "computation_source_correspondence_unverified"),
    ("professional_judgment", "computation_scope_policy_unsupported"),
    ("time_constraint", "computation_scope_policy_unsupported"),
    ("missing_policy", "computation_missing_policy_unsupported"),
    ("repeat_computation", "computation_scope_policy_unsupported"),
    ("period_quantity", "computation_period_quantity_unsupported"),
])
def test_no_count_by_rows_tokens_or_read_lanes(case, reason):
    items = material()
    evidence, records, facts, accounting = items
    comparison = evidence["summary"]["comparisons"][0]
    if case == "no_relation":
        comparison["agreed_relationships"] = []
    elif case == "same_acquisition":
        comparison["agreed_relationships"][0][0] = "same_acquisition"
    elif case == "wrong_membership":
        comparison["agreed_source_descriptions"][0].update(
            input_role="unresolved", input_ref=None, input_excerpt=None)
    elif case == "source_rejected":
        records[0].lane_judgments["main-A"].object_match = "rejected"
    elif case == "source_pending":
        records[0].remaining_unverified.append("unknown_source_boundary")
    elif case == "missing_appearance":
        facts[0].locator_ids.append("unread-locator")
    elif case == "accounting_gap":
        accounting[0]["fact_accounting"].pop()
    elif case == "shared_origin":
        for fact in facts:
            fact.source_observation_refs = ["same-real-observation"]
    elif case == "unit_mismatch":
        records[0].structural.referenced_unit = "mg"
    elif case == "false_direct_derivation":
        records[0].lane_judgments["main-A"].direct_operand_usable = "usable"
    elif case in {"professional_judgment", "time_constraint"}:
        for member in evidence["pairs"][0].members:
            member.condition["requires_professional_judgment" if case == "professional_judgment"
                             else "time_constraint"] = True
    elif case == "missing_policy":
        evidence["pairs"][0].computation.missing_policy = "exclude"
    elif case == "repeat_computation":
        for member in evidence["pairs"][0].members:
            member.condition["predicate"]["repeat_scheme"] = {"synthetic": True}
    elif case == "period_quantity":
        evidence["pairs"][0].computation.quantity_basis = SourceQuantityBasis.model_validate({
            "period_ref": {"statement_index": 0, "quote": "每周"},
            "period_partition": "unresolved", "partition_ref": None, "unit_equivalence_refs": []})
    value = run(items)
    assert not value["input_set_qualified"] and reason in value["reason_codes"]


def test_transitive_same_distinct_conflict_is_rejected_and_same_appearance_cannot_split():
    source = group(excerpts=["记录甲", "记录乙", "记录丙"])
    a, b, c = [member.pair_id for member in source.members]
    with pytest.raises(ValueError, match="同时声明"):
        analyze_computation_acquisitions(source.members, [
            ("same_acquisition", a, b), ("same_acquisition", b, c), ("distinct_acquisition", a, c)])
    clone = source.members[0].model_copy(update={"pair_id": "f" * 64})
    with pytest.raises(ValueError, match="同时声明"):
        analyze_computation_acquisitions([source.members[0], clone], [("distinct_acquisition", a, clone.pair_id)])
    assert _canonical_unit(" BPM ") == _canonical_unit("bpm")


def test_exact_numeric_kernel_preserves_threshold_without_rounding():
    from decimal import Decimal
    from fractions import Fraction
    from app.domain.contracts.enums import FactPolarity
    from app.domain.repeat_numeric_result import aggregate_numeric_acquisitions
    facts = [SimpleNamespace(fact_id=str(index), value=value, unit=None,
                             polarity=FactPolarity.AFFIRMED, conflict_group_id=None)
             for index, value in enumerate([Decimal("0.1"), Decimal("0.2"), Decimal("0.2")])]
    mean, unit, reasons = aggregate_numeric_acquisitions([[fact] for fact in facts],
        operation="mean", unit_required=False)
    assert mean == Fraction(1, 6) and unit is None and reasons == ()
