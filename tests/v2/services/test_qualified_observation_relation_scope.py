from types import SimpleNamespace

import pytest

from app.domain.repeat_result_selection import RepeatResultSelection
from app.services import qualified_observation_relation as relation_service

from app.services.qualified_observation_relation import _merged_acquisition_scope_reasons
from app.storage.repositories import ScopeViolationError


def _fact(fact_id, *, candidates=(), locators=(), observations=()):
    return SimpleNamespace(
        fact_id=fact_id,
        source_candidate_ids=list(candidates),
        locator_ids=list(locators),
        source_observation_refs=list(observations),
        date_range=None,
    )


def test_merged_source_appearances_require_acquisition_review_only_for_selected_fact():
    facts = [
        _fact("single", candidates=("c1",), locators=("l1",)),
        _fact("merged-readings", candidates=("c2", "c3"), locators=("l2",)),
        _fact("merged-locations", candidates=("c4",), locators=("l3", "l4")),
        _fact("merged-observations", candidates=("c5",), locators=("l5",),
              observations=("o1", "o2")),
    ]
    assert _merged_acquisition_scope_reasons(facts, ["single"]) == []
    assert _merged_acquisition_scope_reasons(facts, ["merged-readings"]) == [
        "repeat_acquisition_identity_unverified"
    ]
    assert _merged_acquisition_scope_reasons(facts, ["merged-locations"]) == [
        "repeat_acquisition_identity_unverified"
    ]
    assert _merged_acquisition_scope_reasons(facts, ["single", "merged-readings"]) == [
        "repeat_acquisition_identity_unverified"
    ]
    assert _merged_acquisition_scope_reasons(facts, ["merged-observations"]) == [
        "repeat_acquisition_identity_unverified"
    ]


def test_distinct_facts_sharing_a_source_reading_are_not_two_proven_acquisitions():
    facts = [
        _fact("first", candidates=("c1",), locators=("l1",), observations=("o1",)),
        _fact("second", candidates=("c2",), locators=("l2",), observations=("o1",)),
        _fact("independent", candidates=("c3",), locators=("l3",), observations=("o3",)),
        _fact("same-candidate", candidates=("c1",), locators=("l4",), observations=("o4",)),
        _fact("same-location", candidates=("c5",), locators=("l1",), observations=("o5",)),
    ]
    reason = ["repeat_acquisition_identity_unverified"]
    assert _merged_acquisition_scope_reasons(facts, ["first", "second"]) == reason
    assert _merged_acquisition_scope_reasons(facts, ["first", "same-candidate"]) == reason
    assert _merged_acquisition_scope_reasons(facts, ["first", "same-location"]) == reason
    assert _merged_acquisition_scope_reasons(facts, ["first", "independent"]) == []
    assert _merged_acquisition_scope_reasons(facts, ["first"]) == []


def test_old_observation_evaluation_cannot_authorize_changed_consumer():
    binding_method = SimpleNamespace(candidate_family="repeat")
    evidence = {
        "contract": "source-contract", "prompt_version": "prompt-v1",
        "summary": {"version": "summary-v1"}, "routes": {},
    }
    method = SimpleNamespace(
        candidate_family="repeat", source_qualification_method=binding_method,
        content_contract="source-contract", content_prompt_version="prompt-v1",
        content_summary_version="summary-v1", content_routes={},
        content_consumer_version="qualified-observation-relation/v9",
    )
    manifest = SimpleNamespace(
        evaluation_kind="observation_relationship_fidelity", methods=[method],
    )
    with pytest.raises(ScopeViolationError, match="评测版本不同"):
        relation_service.require_observation_method(manifest, binding_method, evidence)
    method.content_consumer_version = relation_service.OBSERVATION_CONSUMER_VERSION
    relation_service.require_observation_method(manifest, binding_method, evidence)


def test_source_appearances_reach_repeat_review_scope_and_policy(monkeypatch):
    pair_id = "pair-1"
    identity = "a" * 64
    locator_id = "locator-1"
    quote = {"fact_id": "fact-1", "locator_id": locator_id, "excerpt": "初查记录"}
    member = SimpleNamespace(
        pair_id=pair_id, fact_id="fact-1", locator_id=locator_id,
        fact_attribute="value", identity_sha256=identity,
        identity_field="predicate_identity_sha256", locator={"excerpt": "初查记录"},
        episode={"anchor_dates": {}},
    )
    group = SimpleNamespace(
        pair_id="group-1", identity_sha256=identity, members=[member],
        auxiliary_members=[], scheme=object(),
    )
    lane = {
        "links": [], "origins": [{"fact_id": "fact-1", "quotes": [quote]}],
        "episode_memberships": [], "auxiliary_associations": [],
        "unresolved_notes": [], "auxiliary_unresolved_notes": [],
    }
    evidence = {
        "pairs": [group], "summary_sha256": "b" * 64,
        "summary": {"comparisons": [{
            "group_id": "group-1", "lanes": {"main-A": lane, "main-B": lane},
            "agreed_relationships": [],
            "agreed_origins": [{"fact_id": "fact-1", "role": "initial"}],
            "agreed_episode_memberships": [], "disputed_relationships": [],
            "agreed_auxiliary_associations": [], "disputed_auxiliary_associations": [],
            "auxiliary_pairs_without_agreed_association": [],
        }]},
    }
    record = SimpleNamespace(
        pair_id=pair_id, identity_sha256=identity, fact_id="fact-1",
        locator_id=locator_id, fact_attribute="value",
    )
    accounting = [{"predicate_identity_sha256": identity, "fact_accounting": [
        {"fact_id": "fact-1", "status": "candidates_in_both_lanes"},
    ]}]
    from app.services import qualified_binding_selection
    monkeypatch.setattr(qualified_binding_selection, "pair_direct_selection_rejection_reasons",
                        lambda *args, **kwargs: [])
    monkeypatch.setattr(qualified_binding_selection, "source_validity_operand_calculable",
                        lambda *args, **kwargs: True)
    monkeypatch.setattr(relation_service, "calculate_repeat_series_constraints",
                        lambda *args, **kwargs: {})
    captured = []

    def select_policy(*args, **kwargs):
        captured.append(kwargs)
        return RepeatResultSelection(
            graph_sha256="a" * 64, scheme_sha256="b" * 64,
            supplied_scope_sha256="c" * 64, considered_group_ids=(),
        )

    monkeypatch.setattr(relation_service, "select_repeat_result_groups", select_policy)

    def review(fact):
        return relation_service.select_qualified_observation_relations(
            evidence, [record], frozen_facts=[fact],
            candidate_fact_accounting=accounting,
        )[0]

    single = review(_fact("fact-1", candidates=("c1",), locators=(locator_id,)))
    merged = review(_fact("fact-1", candidates=("c1", "c2"), locators=(locator_id,)))
    assert single["supplied_scope"]["complete"] is True
    assert single["supplied_scope"]["initial_scope"]["complete"] is True
    assert merged["supplied_scope"]["complete"] is False
    assert merged["supplied_scope"]["initial_scope"]["complete"] is False
    assert "repeat_acquisition_identity_unverified" in merged["supplied_scope"]["reason_codes"]
    assert captured[0]["scope_complete"] is True
    assert captured[0]["initial_scope_complete"] is True
    assert captured[1]["scope_complete"] is False
    assert captured[1]["initial_scope_complete"] is False


def test_uncertain_repeat_does_not_erase_qualified_initial(monkeypatch):
    identity = "a" * 64

    def member(number):
        return SimpleNamespace(
            pair_id=f"pair-{number}", fact_id=f"fact-{number}",
            locator_id=f"locator-{number}", fact_attribute="value",
            identity_sha256=identity, identity_field="predicate_identity_sha256",
            locator={"excerpt": f"第{number}次检查记录"},
            episode={"anchor_dates": {}},
        )

    members = [member(1), member(2)]
    quotes = [
        {"fact_id": item.fact_id, "locator_id": item.locator_id,
         "excerpt": item.locator["excerpt"]}
        for item in members
    ]
    link = {
        "left_fact_id": "fact-2", "right_fact_id": "fact-1",
        "relation": "repeat_of", "quotes": quotes, "explanation": "原文说明复查",
    }
    lane = {
        "links": [link], "origins": [
            {"fact_id": "fact-1", "quotes": [quotes[0]]},
            {"fact_id": "fact-2", "quotes": [quotes[1]]},
        ],
        "episode_memberships": [], "auxiliary_associations": [],
        "unresolved_notes": [], "auxiliary_unresolved_notes": [],
    }
    evidence = {
        "pairs": [SimpleNamespace(
            pair_id="group-1", identity_sha256=identity, members=members,
            auxiliary_members=[], scheme=object(),
        )],
        "summary_sha256": "b" * 64,
        "summary": {"comparisons": [{
            "group_id": "group-1", "lanes": {"main-A": lane, "main-B": lane},
            "agreed_relationships": [["repeat_of", "fact-2", "fact-1"]],
            "agreed_origins": [
                {"fact_id": "fact-1", "role": "initial"},
                {"fact_id": "fact-2", "role": "repeat"},
            ],
            "agreed_episode_memberships": [], "disputed_relationships": [],
            "agreed_auxiliary_associations": [], "disputed_auxiliary_associations": [],
            "auxiliary_pairs_without_agreed_association": [],
        }]},
    }
    records = [SimpleNamespace(
        pair_id=item.pair_id, identity_sha256=identity,
        fact_id=item.fact_id, locator_id=item.locator_id,
        fact_attribute=item.fact_attribute,
    ) for item in members]
    accounting = [{"predicate_identity_sha256": identity, "fact_accounting": [
        {"fact_id": item.fact_id, "status": "candidates_in_both_lanes"}
        for item in members
    ]}]
    from app.services import qualified_binding_selection
    monkeypatch.setattr(qualified_binding_selection, "pair_direct_selection_rejection_reasons",
                        lambda *args, **kwargs: [])
    monkeypatch.setattr(qualified_binding_selection, "source_validity_operand_calculable",
                        lambda *args, **kwargs: True)
    monkeypatch.setattr(relation_service, "calculate_repeat_series_constraints",
                        lambda *args, **kwargs: {})
    selected = []

    def select_policy(*args, **kwargs):
        selected.append(kwargs)
        return RepeatResultSelection(
            graph_sha256="a" * 64, scheme_sha256="b" * 64,
            supplied_scope_sha256="c" * 64, considered_group_ids=(),
        )

    monkeypatch.setattr(relation_service, "select_repeat_result_groups", select_policy)
    result = relation_service.select_qualified_observation_relations(
        evidence, records,
        frozen_facts=[
            _fact("fact-1", candidates=("c1",), locators=("locator-1",),
                  observations=("shared-reading",)),
            _fact("fact-2", candidates=("c2",), locators=("locator-2",),
                  observations=("shared-reading",)),
        ],
        candidate_fact_accounting=accounting,
    )[0]
    assert result["supplied_scope"]["complete"] is False
    assert result["supplied_scope"]["initial_scope"]["complete"] is True
    assert "repeat_acquisition_identity_unverified" in result["supplied_scope"]["reason_codes"]
    assert selected[0]["scope_complete"] is False
    assert selected[0]["initial_scope_complete"] is True
