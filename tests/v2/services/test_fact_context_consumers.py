"""Synthetic context assembly/correction checks, not source/adoption approval."""
from types import SimpleNamespace

import pytest

from app.domain.contracts.fact_context import FactContextQualifier
from app.domain.contracts.fact_corrections import (
    _parse_canonical_snapshot, canonical_json, fact_semantic_snapshot,
)
from app.domain.contracts.facts import AssertionBasis, ClinicalFactV2, clinical_fact_stable_identity
from app.domain.contracts.enums import FactPolarity, ProfileLane
from app.projections.patient_profile import _fact_item
from app.api.v2.patient_profile_schemas import profile_item_dto
from app.services.binding_qualification_support import _fact_material
from app.services import fact_correction_service as correction
from tests.v2.projections.test_patient_profile_projection import _fact, _UTC


def _context_fact(label="量表甲"):
    old = _fact(asserted_object="项目乙", value=2, unit="unitless")
    basis = AssertionBasis(
        asserted_object=old.asserted_object, assertion_text=f"{label}：项目甲1，项目乙2",
        locator_id=old.locator_ids[0], source_text_sha256="a" * 64,
        contextual_qualifiers=[FactContextQualifier(kind="assessment", label=label)],
    )
    stable = clinical_fact_stable_identity(
        authority=old.authority, fact_type=old.fact_type, profile_lane=old.profile_lane,
        asserted_object=old.asserted_object, polarity=old.polarity, value=old.value,
        unit=old.unit, date_range=old.date_range, assertion_basis=basis,
    )
    return ClinicalFactV2.model_validate({**old.model_dump(mode="json"),
        "assertion_basis": basis.model_dump(mode="json"), "stable_identity": stable})


def test_context_reaches_profile_api_and_frozen_qualification_material():
    first, second = _context_fact(), _context_fact("量表乙")
    for fact, title in ((first, "量表甲：项目乙"), (second, "量表乙：项目乙")):
        dto = profile_item_dto(_fact_item(fact, ProfileLane.TEST_EXAM_SCORE))
        assert dto.title == title
        assert dto.asserted_object == "项目乙" and dto.value == 2
        assert dto.locator_ids == fact.locator_ids
        assert _fact_material(fact)["assertion_basis"]["contextual_qualifiers"] == [
            {"kind": "assessment", "label": title.split("：")[0]}]
    assert first.stable_identity != second.stable_identity
    assert not first.source_observation_refs and not second.source_observation_refs
    old = _fact()
    assert profile_item_dto(_fact_item(old, ProfileLane.TEST_EXAM_SCORE)).title == old.asserted_object
    assert "contextual_qualifiers" not in _fact_material(old)["assertion_basis"]


def test_same_label_whitespace_is_not_a_new_semantic_identity():
    first, spaced = _context_fact("量表甲"), _context_fact("  量表甲  ")
    assert first.stable_identity == spaced.stable_identity
    assert spaced.assertion_basis.contextual_qualifiers[0].label == "  量表甲  "


def test_preparation_consumer_rejects_old_context_but_preserves_history(monkeypatch):
    from app.services import review_candidate_scope as scope
    from app.services.predicate_binding_input import _frozen_fact
    from app.domain.publication import canonical_hash
    from app.storage.repositories import ScopeViolationError
    old, new = _context_fact(), _context_fact("量表乙")
    old_frozen = _frozen_fact(old)
    history = old_frozen.model_dump(mode="json")
    rules = SimpleNamespace(rules=[], model_dump=lambda **kwargs: {"rules": []})
    context = SimpleNamespace(authority=new.authority, review_episode="episode", facts=[new],
        rule_set_sha256=canonical_hash({"rules": []}), context_sha256="c" * 64)
    monkeypatch.setattr(scope, "ReviewContextV2Repository", lambda session: SimpleNamespace(get=lambda key: context))
    monkeypatch.setattr(scope, "get_rule_set", lambda *args: rules)
    source = SimpleNamespace(authority=new.authority, episode="episode", facts=[old_frozen], components=[])
    with pytest.raises(ScopeViolationError, match="已核实资料已变化"):
        scope.require_prepared_candidate_scope(None, "context", source)
    source.facts = [_frozen_fact(new)]
    assert scope.require_prepared_candidate_scope(None, "context", source) == context.context_sha256
    assert old_frozen.model_dump(mode="json") == history


def test_publication_assembly_keeps_contexts_separate_and_repeated_reading_merged(monkeypatch):
    # Only the existing assembly stage is exercised; upstream authority/source gates
    # are not replaced with a claim of clinical acceptance.
    from app.services import fact_publication_service as publication
    from app.domain.contracts.facts import ClinicalFactCandidateV2
    candidates = []
    for ref, label in (("a", "量表甲"), ("b", "量表乙"), ("a-repeat", "量表甲")):
        fact = _context_fact(label)
        candidates.append(ClinicalFactCandidateV2(
            candidate_id=ref, run_id="run-1", call_id="call-1", fact_type=fact.fact_type,
            profile_lane=fact.profile_lane, polarity=fact.polarity, asserted_object=fact.asserted_object,
            raw_value=fact.value, canonical_value=fact.value, unit=fact.unit,
            locator_ids=fact.locator_ids, assertion_basis=fact.assertion_basis,
            candidate_source_semantics="同期客观结果", model_uncertainty=0.1, created_at=_UTC))
    monkeypatch.setattr(publication, "_source_strength", lambda *args: _context_fact().source_strength)
    stored = []
    gates = {item.candidate_id: SimpleNamespace(gate_result_id=f"gate-{item.candidate_id}") for item in candidates}
    facts, mapping = publication.FactPublicationService()._publish_facts(
        session=None, authority=_context_fact().authority, run_id="run-1", revision=None,
        candidates=candidates, gates=gates, existing=[], created_at=_UTC,
        repository=SimpleNamespace(create=stored.append))
    assert len(facts) == len(stored) == 2
    assert mapping["a"] == mapping["a-repeat"] != mapping["b"]
    assert sorted(len(item.source_candidate_ids) for item in facts) == [1, 2]
    assert all(not item.source_observation_refs for item in facts)
    assert {item.assertion_basis.contextual_qualifiers[0].label for item in facts} == {"量表甲", "量表乙"}


def test_correction_snapshot_retains_context_without_changing_legacy_format():
    old = _fact()
    assert "contextual_qualifiers" not in fact_semantic_snapshot(old)
    snapshot = fact_semantic_snapshot(_context_fact())
    assert _parse_canonical_snapshot(canonical_json(snapshot), target_kind="fact", label="旧") == snapshot
    borrowed = {**snapshot, "contextual_qualifiers": [{"kind": "assessment", "label": "量表乙"}]}
    with pytest.raises(ValueError, match="须逐字来自同一断言依据"):
        _parse_canonical_snapshot(canonical_json(borrowed), target_kind="fact", label="旧")


@pytest.mark.parametrize("updates", [{"value": 3}, {"unit": "other"}, {"asserted_object": "项目甲"}])
def test_changed_context_fact_cannot_borrow_old_basis(monkeypatch, updates):
    fact = _context_fact()
    locator = SimpleNamespace(source_text_sha256="a" * 64, excerpt=fact.assertion_basis.assertion_text)
    monkeypatch.setattr(correction, "EvidenceLocatorRepository", lambda session: SimpleNamespace(get=lambda key: locator))
    with pytest.raises(correction.FactCorrectionValidationError, match="需重新核对其归属"):
        correction._build_new_fact(None, fact, fact.locator_ids, updates, _UTC)


def test_context_correction_preserves_unchanged_basis_and_allows_explicit_withdrawal(monkeypatch):
    fact = _context_fact()
    locator = SimpleNamespace(source_text_sha256="a" * 64, excerpt=fact.assertion_basis.assertion_text)
    monkeypatch.setattr(correction, "EvidenceLocatorRepository", lambda session: SimpleNamespace(get=lambda key: locator))
    monkeypatch.setattr(correction, "ClinicalFactV2Repository", lambda session: SimpleNamespace(list_for_authority=lambda auth: [fact]))
    updated, candidate, _ = correction._build_new_fact(None, fact, fact.locator_ids, {}, _UTC)
    assert updated.assertion_basis == fact.assertion_basis
    assert updated.stable_identity == fact.stable_identity
    assert candidate["assertion_basis"] == fact.assertion_basis.model_dump(mode="json")
    withdrawn, candidate, _ = correction._build_new_fact(None, fact, fact.locator_ids,
        {"polarity": FactPolarity.UNKNOWN.value, "value": None, "unit": None}, _UTC)
    assert withdrawn.assertion_basis is None and candidate["assertion_basis"] is None
    assert fact.assertion_basis.contextual_qualifiers[0].label == "量表甲"
