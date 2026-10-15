import asyncio
from copy import deepcopy
from decimal import Decimal

import pytest

from app.domain.publication import canonical_hash
from app.domain.variables.dictionary import VariableDef, load_dictionary, load_drug_classes
from app.domain.contracts.rules import AtomicPredicate, EvidenceRequirement
from app.services.protocol_variable_binding import (
    VariableBinding, VariableBindingProposal, apply_variable_bindings, binding_view,
    validate_publication_bindings, validate_variable_predicate, component_predicates,
    validated_variable_suggestions,
)
from tests.v2.protocols.slice4_helpers import confirmed_fixture, NOW


def fixture_bindings(draft):
    """Synthetic fixture only: explicit typed definitions, not production inference."""
    variables, bindings = [], []
    for index, item in enumerate(binding_view(draft)["predicates"]):
        predicate = item["predicate"]
        value = predicate.get("value")
        numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
        identifier = f"fixture_variable_{index}"
        variables.append(VariableDef(variable_id=identifier, label_zh=item["label"],
            value_type="number" if numeric else "boolean" if value is None or isinstance(value, bool) else "category",
            canonical_unit=predicate.get("unit") if numeric else None,
            plausible_range=(-1000000, 1000000) if numeric else None, domain="history"))
        bindings.append(VariableBinding(component_id=item["component_id"], predicate_id=item["predicate_id"],
            variable_id=identifier, requirement_id=item["requirements"][0]["requirement_id"]))
    return VariableBindingProposal(variables=variables, bindings=bindings)


def test_dictionary_exact_units_and_non_numeric_identity():
    dictionary = load_dictionary()
    assert dictionary["eos"].convert(0.32, "×10^9/L") == Decimal("320.000")
    assert dictionary["anc"].convert(2000, "/μL") == Decimal("2.0000")
    assert load_drug_classes()["systemic_corticosteroids"]
    with pytest.raises(ValueError): dictionary["alt"].convert(3, "×ULN")
    with pytest.raises(ValueError): dictionary["age"].convert(True, "周岁")
    with pytest.raises(ValueError):
        load_dictionary([dictionary["age"].model_copy(update={"label_zh": "不同含义"})])
    with pytest.raises(ValueError):
        VariableDef(variable_id="new", label_zh="数值", value_type="number", domain="lab")


def test_binding_preserves_predicates_sources_and_legacy_payload():
    _, draft, _ = confirmed_fixture()
    before = draft.model_dump(mode="json")
    original = deepcopy(before)
    assert "variable_definitions" not in original
    assert canonical_hash(type(draft).model_validate(original).model_dump(mode="json")) == canonical_hash(original)
    result = apply_variable_bindings(draft, fixture_bindings(draft))
    validate_publication_bindings(result)
    assert draft.model_dump(mode="json") == before
    for old, new in zip(draft.component_drafts, result.component_drafts):
        assert old.source_refs == new.source_refs and old.source_excerpts == new.source_excerpts
        assert old.proposed_component.expression == new.proposed_component.expression
        assert old.proposed_component.exception_expression == new.proposed_component.exception_expression
    assert all(item.proposed_requirement.variable_id == "procedure:" + item.procedure_catalog_item_id
               for item in result.evidence_requirement_drafts if item.procedure_catalog_item_id)
    old_requirement = draft.evidence_requirement_drafts[0].proposed_requirement.model_dump(mode="json")
    assert "variable_id" not in old_requirement
    assert EvidenceRequirement.model_validate(old_requirement).model_dump(mode="json") == old_requirement


def test_binding_rejects_wrong_scope_duplicate_type_and_units():
    _, draft, _ = confirmed_fixture()
    proposal = fixture_bindings(draft)
    bad = proposal.model_copy(deep=True); bad.bindings[0].component_id = "other"
    with pytest.raises(ValueError, match="不存在"): apply_variable_bindings(draft, bad)
    bad = proposal.model_copy(deep=True); bad.bindings.append(bad.bindings[0])
    with pytest.raises(ValueError, match="重复"): apply_variable_bindings(draft, bad)
    predicate = AtomicPredicate(predicate_id="p", subject="受试者", attribute="计数", comparator="gte", value=3, unit="/μL")
    with pytest.raises(ValueError, match="非数值"):
        validate_variable_predicate(load_dictionary()["sex"], predicate)
    with pytest.raises(ValueError, match="无法换算"):
        validate_variable_predicate(load_dictionary()["age"], predicate)
    with pytest.raises(ValueError, match="未选择"):
        validate_publication_bindings(draft)


def test_rebinding_preserves_source_and_unique_due_stage():
    _, draft, _ = confirmed_fixture()
    proposal = fixture_bindings(draft)
    first = proposal.bindings[0]
    original = next(item for item in draft.evidence_requirement_drafts
                    if item.proposed_requirement.requirement_id == first.requirement_id)
    stage = next(item for item in draft.proposed_workflow_stages
                 if first.requirement_id in item.due_requirement_ids)
    bound = apply_variable_bindings(draft, proposal)
    rebound = apply_variable_bindings(bound, VariableBindingProposal(bindings=[first]))
    validate_publication_bindings(rebound)
    requirement = next(item for item in rebound.evidence_requirement_drafts
        if item.proposed_requirement.variable_id == first.variable_id)
    assert requirement.source_refs == original.source_refs
    assert [item.workflow_stage_id for item in rebound.proposed_workflow_stages
        if requirement.proposed_requirement.requirement_id in item.due_requirement_ids] == [stage.workflow_stage_id]
    assert binding_view(rebound)["predicates"][0]["variable_id"] == first.variable_id


def test_professional_judgment_binding_requires_written_assessment():
    _, draft, _ = confirmed_fixture()
    component = draft.proposed_rules[0].components[0]
    predicate = next(iter(component_predicates(component)))
    predicate.requires_professional_judgment = True
    component_draft = next(item for item in draft.component_drafts
        if item.proposed_component.rule_component_id == component.rule_component_id)
    component_draft.proposed_component = component
    bound = apply_variable_bindings(draft, fixture_bindings(draft))
    validate_publication_bindings(bound)
    selected = next(item for item in bound.proposed_rules[0].components[0].evidence_requirements
        if predicate.predicate_id in item.predicate_ids)
    assert "investigator_assessment" in selected.required_source_types
    selected.required_source_types.remove("investigator_assessment")
    with pytest.raises(ValueError, match="书面判断"):
        validate_publication_bindings(bound)


def test_multiple_source_policies_for_one_predicate_are_retained():
    _, draft, _ = confirmed_fixture()
    proposal = fixture_bindings(draft)
    first = proposal.bindings[0]
    template = next(item for item in draft.evidence_requirement_drafts
        if item.proposed_requirement.requirement_id == first.requirement_id)
    other = template.model_copy(deep=True)
    other.draft_requirement_id += ":other"
    other.proposed_requirement.requirement_id += ":other"
    draft.evidence_requirement_drafts.append(other)
    component = next(item.proposed_component for item in draft.component_drafts
        if item.proposed_component.rule_component_id == first.component_id)
    component.evidence_requirements.append(other.proposed_requirement)
    stage = next(stage for stage in draft.proposed_workflow_stages
        if first.requirement_id in stage.due_requirement_ids)
    stage.due_requirement_ids.append(other.proposed_requirement.requirement_id)
    proposal.bindings.append(first.model_copy(update={"requirement_id": other.proposed_requirement.requirement_id}))
    bound = apply_variable_bindings(draft, proposal)
    selected = [item for item in bound.evidence_requirement_drafts
        if first.predicate_id in item.proposed_requirement.predicate_ids]
    assert len(selected) == 2
    assert {item.proposed_requirement.variable_id for item in selected} == {first.variable_id}
    assert all(item.source_refs == template.source_refs for item in selected)
    assert all(item.proposed_requirement.requirement_id in next(s for s in bound.proposed_workflow_stages
        if s.workflow_stage_id == stage.workflow_stage_id).due_requirement_ids for item in selected)
    validate_publication_bindings(bound)
    conflict = proposal.model_copy(deep=True)
    conflict.bindings[-1].variable_id = "sex"
    with pytest.raises(ValueError, match="不同数据"):
        apply_variable_bindings(draft, conflict)


def test_invalid_suggestion_does_not_erase_valid_siblings():
    _, draft, _ = confirmed_fixture()
    proposal = fixture_bindings(draft)
    proposal.bindings[0].component_id = "missing"
    accepted, issues = validated_variable_suggestions(draft, proposal)
    assert len(accepted.bindings) == len(proposal.bindings) - 1
    assert len(issues) == 1 and issues[0]["component_id"] == "missing"
    assert draft.variable_definitions is None
    assert apply_variable_bindings(draft, accepted).variable_definitions


def test_suggestion_accepts_outer_fence_but_rejects_ambiguous_json(data_paths, monkeypatch):
    import app.agents.protocol_variable_binder as module
    from app.llm.page_review_harness import PageCompletion
    _, draft, _ = confirmed_fixture()
    monkeypatch.setattr(module, "resolve_openai_connection", lambda *a, **k: ("http://localhost/v1", "test"))
    calls = []
    async def fenced(route, messages, max_tokens):
        calls.append(messages)
        return PageCompletion('```json\n{"variables":[],"bindings":[]}\n```', "stop", {})
    outcome = asyncio.run(module.suggest_variables(draft, data_paths, completion=fenced))
    assert outcome["proposal"] is not None and len(calls) == 1
    for text in ('{"variables":[],"variables":[],"bindings":[]}', '{} {}'):
        calls.clear()
        async def invalid(route, messages, max_tokens):
            calls.append(messages)
            return PageCompletion(text, "stop", {})
        outcome = asyncio.run(module.suggest_variables(draft, data_paths, completion=invalid))
        assert outcome["proposal"] is None and len(calls) == 2


def test_bound_publication_keeps_dictionary_projection_and_review_identity(slice4_env):
    from tests.v2.protocols.test_publication_service import _save_revision
    from tests.v2.protocols.test_rule_reviews import approve_draft
    from app.services.protocol_publication_service import ProtocolPublicationService, ProtocolPublicationRequest
    from app.storage.repositories import get_rule_set
    from app.storage.models import RuleSetVariablesRecord
    from app.storage.codecs import verify_payload_sha256
    from app.services.protocol_rule_review import review_entries
    factory, _ = slice4_env
    source, draft, spans = confirmed_fixture()
    draft = apply_variable_bindings(draft, fixture_bindings(draft))
    revision = _save_revision(factory, draft)
    approve_draft(factory, source, draft, kind="medical_manager")
    result = ProtocolPublicationService(factory).publish(ProtocolPublicationRequest(
        idempotency_key="bound", draft_revision_id=revision.revision_id, source_input=source,
        source_spans=spans, actor="测试", published_at=NOW))
    with factory() as session:
        rules = get_rule_set(session, result.rule_set_id, result.rule_set_revision)
        row = session.get(RuleSetVariablesRecord, (result.rule_set_id, result.rule_set_revision))
        assert verify_payload_sha256(row.payload_json, row.payload_sha256) == [v.model_dump(mode="json") for v in rules.variable_definitions]
        assert rules.verification_only is False
    changed = draft.model_copy(deep=True)
    used = changed.proposed_rules[0].components[0].evidence_requirements[-1].variable_id
    next(v for v in changed.variable_definitions if v.variable_id == used).label_zh += "（改）"
    before, after = review_entries(source, draft), review_entries(source, changed)
    assert before[0]["rule_content_hash"] != after[0]["rule_content_hash"]
    assert all(x["rule_content_hash"] == y["rule_content_hash"] for x, y in zip(before[1:], after[1:]))


def test_suggestion_two_invalid_completions_preserve_receipts_without_changes(data_paths, monkeypatch):
    import app.agents.protocol_variable_binder as module
    from app.llm.page_review_harness import PageCompletion
    paths = data_paths
    _, draft, _ = confirmed_fixture()
    monkeypatch.setattr(module, "resolve_openai_connection", lambda *a, **k: ("http://localhost/v1", "test"))
    calls = []
    async def completion(route, messages, max_tokens):
        calls.append(messages)
        return PageCompletion("{}", "stop", {}, response_model="test")
    # Empty proposal is an honest unbound suggestion, not an adopted complete mapping.
    outcome = asyncio.run(module.suggest_variables(draft, paths, completion=completion))
    assert outcome["unbound_count"] == len(binding_view(draft)["predicates"])
    assert len(calls) == 1
    assert draft.variable_definitions is None
    async def invalid(route, messages, max_tokens):
        calls.append(messages); return PageCompletion("bad json", "length", {})
    calls.clear(); outcome = asyncio.run(module.suggest_variables(draft, paths, completion=invalid))
    assert len(calls) == len(outcome["receipts"]) == 2 and outcome["proposal"] is None
    assert all(item["request_ref"] and item["response_ref"] for item in outcome["receipts"])
