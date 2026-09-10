from copy import deepcopy

from app.projections.normalizer_reference_aliases import NormalizerReferenceAliases


def test_aliases_round_trip_without_modifying_clinical_text():
    payload = {"locators": [{"locator_id": "long-locator", "localized_text": "long-locator @L1"}],
               "related_requirements": [{"requirement_id": "long-requirement"}],
               "page_review": {"accepted_observations": [{"source_observation_ref": "long-observation",
                                 "observation": {"raw_text": "long-observation", "raw_value": "0001"}}]}}
    original = deepcopy(payload)
    aliases = NormalizerReferenceAliases.from_payload(payload)
    compact = aliases.transform(payload)
    assert compact["locators"][0]["locator_id"] == "@L1"
    assert compact["locators"][0]["localized_text"] == "long-locator @L1"
    assert aliases.transform(compact, expand=True) == original
    assert payload == original
    output = {"fact_candidates": [{"locator_ids": ["@L1"], "source_observation_refs": ["@O1"],
              "supported_requirement_ids": ["@R1"], "assertion_basis": {"locator_id": "@L1"},
              "raw_value": "@L1"}], "unresolved_items": [{"affected_locator_ids": ["@L1"],
              "affected_requirement_ids": ["@R1"], "reason": "@R1"}]}
    expanded = aliases.transform(output, expand=True)
    assert expanded["fact_candidates"][0] == {"locator_ids": ["long-locator"],
        "source_observation_refs": ["long-observation"], "supported_requirement_ids": ["long-requirement"],
        "assertion_basis": {"locator_id": "long-locator"}, "raw_value": "@L1"}
    assert expanded["unresolved_items"][0]["reason"] == "@R1"


def test_aliases_are_deterministic_and_do_not_collide_with_source_ids():
    first = {"locator_ids": ["@L1", "z", "a"]}
    second = {"locator_ids": ["a", "z", "@L1"]}
    aliases = NormalizerReferenceAliases.from_payload(first)
    assert aliases == NormalizerReferenceAliases.from_payload(second)
    assert aliases.transform(first)["locator_ids"][0] == "@@L1"
    assert aliases.transform(aliases.transform(first), expand=True) == first


def test_unknown_or_wrong_kind_references_are_not_guessed():
    aliases = NormalizerReferenceAliases.from_payload({"locator_id": "real-locator"})
    bad = {"locator_ids": ["@L999", "@O1", None, 1], "source_observation_refs": ["@L1"]}
    assert aliases.transform(bad, expand=True) == bad
