"""Source presentations are addressable without equating them to acquisitions."""
import json
from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest

from app.domain.contracts.observation_relation import ObservationRelationLink
from app.domain.contracts.binding_qualification import (
    BindingQualificationBatch, BindingQualificationPairContext,
    binding_qualification_pair_id,
)
from app.domain.contracts.observation_relation import (
    ObservationRelationContext, OBSERVATION_RELATION_VERSION,
)
from app.domain.contracts.repeat_scheme import RepeatDuration, RepeatScheme, RepeatTimeLimit
from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import DatePrecision
from app.domain.contracts.rules import WorkflowStage
from app.domain.observation_relation_graph import (
    analyze_observation_appearances, appearance_relationship_edge,
    observation_appearance_id,
)
from app.domain.repeat_result_selection import RepeatResultSelection
from app.domain.repeat_series_constraints import calculate_repeat_series_constraints
from app.domain.publication import canonical_hash
from app.llm.observation_relation import (
    build_observation_relation_messages, relation_batch,
    validate_observation_relation_payload,
)
from app.services import qualified_observation_relation as relation_service
from app.services import observation_relation_receipts as receipts
from app.services import repeat_observation_ordering as ordering
from app.services.ordered_observation_selection import OrderedObservationSelection


def _appearance(fact_id, locator_id):
    return {
        "fact_id": fact_id, "locator_id": locator_id,
        "appearance_id": observation_appearance_id(fact_id, locator_id),
    }


def _quote(locator_id):
    return {"fact_id": "fact-1", "locator_id": locator_id,
            "excerpt": f"同一采样编号的第{locator_id}份报告"}


def _link():
    return {
        "left_fact_id": "fact-1", "left_locator_id": "l1",
        "right_fact_id": "fact-1", "right_locator_id": "l2",
        "relation": "same_acquisition", "quotes": [_quote("l1"), _quote("l2")],
        "explanation": "原文明确记载同一采样编号",
    }


def test_product_v6_prompt_accepts_real_frozen_pair_contract():
    identity = "b" * 64
    frozen = "c" * 64
    members = []
    for locator_id in ("l1", "l2"):
        material = {
            "candidate_job_id": "candidate-job", "frozen_input_sha256": frozen,
            "identity_field": "predicate_identity_sha256", "identity_sha256": identity,
            "fact_id": "fact-1", "fact_attribute": "value",
            "locator_id": locator_id, "candidate_batch_sha256": None,
        }
        members.append(BindingQualificationPairContext(
            pair_id=binding_qualification_pair_id(**material),
            candidate_family="predicate", candidate_job_type="predicate_candidate",
            candidate_contract="predicate-candidate/v1", comparison_sha256="d" * 64,
            condition={}, fact={"fact_id": "fact-1"},
            locator={"locator_id": locator_id, "excerpt": _quote(locator_id)["excerpt"]},
            episode={"workflow_stage_id": "stage-1", "stage": "screening", "anchor_dates": {}},
            parent_source_context={}, source_policy_status="missing",
            lane_declarations={"main-A": {}, "main-B": {}},
            candidate_receipt_sha256s={"main-A": [], "main-B": []},
            **material,
        ))
    scheme = RepeatScheme(
        scope="本次筛选", source_span_ids=["protocol-span"], source_excerpts=["复查"],
        permission="required", trigger="unconditional", count_status="not_specified",
        time_status="not_specified", result_use="retain_initial",
    )
    content = {
        "version": OBSERVATION_RELATION_VERSION,
        "identity_sha256": identity, "candidate_job_id": "candidate-job",
        "frozen_input_sha256": frozen, "scheme": scheme.model_dump(mode="json"),
        "members": [item.model_dump(mode="json") for item in members],
        "auxiliary_members": [],
        "workflow_stage": WorkflowStage(
            workflow_stage_id="stage-1", stage="screening", display_name="筛选访视",
        ).model_dump(mode="json"),
    }
    group = ObservationRelationContext(
        pair_id=canonical_hash({"version": OBSERVATION_RELATION_VERSION, **content}),
        **content,
    )
    messages = build_observation_relation_messages([group], relation_batch([group]))
    user = json.loads(messages[1]["content"][0]["text"])
    assert user["groups"][0]["observation_appearances"] == [
        {"fact_id": "fact-1", "locator_id": key} for key in ("l1", "l2")
    ]
    schema = user["output_schema"]
    assert "reviewed_appearances" in schema["$defs"]["ObservationRelationResult"]["required"]
    assert "left_locator_id" in schema["$defs"]["ObservationRelationLink"]["required"]


def test_appearance_graph_keeps_unlinked_sources_separate_but_not_verified():
    appearances = [_appearance("fact-1", "l1"), _appearance("fact-1", "l2")]
    separate = analyze_observation_appearances(appearances, [])
    assert len(separate["acquisition_groups"]) == 2
    assert separate["clinical_identity_verified"] is False
    key = ObservationRelationLink.model_validate(_link()).agreement_key()
    grouped = analyze_observation_appearances(
        appearances, [appearance_relationship_edge(key)],
        origins={item["appearance_id"]: "initial" for item in appearances},
    )
    assert len(grouped["acquisition_groups"]) == 1
    assert grouped["acquisition_groups"][0]["fact_ids"] == ["fact-1"]
    assert len(grouped["acquisition_groups"][0]["appearance_ids"]) == 2
    with pytest.raises(ValueError, match="身份不一致"):
        analyze_observation_appearances([appearances[0], {**appearances[1], "appearance_id": "forged"}], [])


def test_same_acquisition_requires_each_presentation_origin():
    appearances = [_appearance("fact-1", "l1"), _appearance("fact-1", "l2")]
    grouped = analyze_observation_appearances(
        appearances,
        [appearance_relationship_edge(ObservationRelationLink.model_validate(_link()).agreement_key())],
        origins={appearances[0]["appearance_id"]: "repeat"},
    )
    assert grouped["origin_unresolved_appearance_ids"] == [appearances[1]["appearance_id"]]
    assert grouped["acquisition_roles"][0]["role"] == "unresolved"


def test_one_acquisition_with_two_reader_candidates_is_not_two_measurements():
    appearances = [_appearance("fact-1", "l1")]
    graph = analyze_observation_appearances(
        appearances, [], origins={appearances[0]["appearance_id"]: "initial"},
    )
    fact = SimpleNamespace(
        fact_id="fact-1", source_candidate_ids=["reader-a", "reader-b"],
        source_observation_refs=["observation-a", "observation-b"], locator_ids=["l1"],
    )
    assert relation_service._merged_acquisition_scope_reasons([fact], ["fact-1"], graph=graph) == []


def test_extra_reader_candidates_do_not_invent_a_third_acquisition():
    appearances = [_appearance("fact-1", "l1"), _appearance("fact-1", "l2")]
    graph = analyze_observation_appearances(
        appearances,
        [("repeat_of", appearances[1]["appearance_id"],
          appearances[0]["appearance_id"], "initial_observation")],
        origins={appearances[0]["appearance_id"]: "initial",
                 appearances[1]["appearance_id"]: "repeat"},
    )
    fact = SimpleNamespace(
        fact_id="fact-1", locator_ids=["l1", "l2"],
        source_candidate_ids=["reader-a", "reader-b", "reader-c"],
        source_observation_refs=["read-a", "read-b", "read-c"],
    )
    assert relation_service._merged_acquisition_scope_reasons(
        [fact], ["fact-1"], graph=graph,
    ) == []
    assert len(graph["acquisition_groups"]) == 2


def test_two_quoted_acquisitions_may_share_a_page_locator():
    appearances = [_appearance("first", "page-1"), _appearance("later", "page-1")]
    initial, repeat = (item["appearance_id"] for item in appearances)
    origins = {initial: "initial", repeat: "repeat"}
    facts = [
        SimpleNamespace(fact_id="first", locator_ids=["page-1"],
                        source_candidate_ids=["candidate-first"],
                        source_observation_refs=["observation-first"]),
        SimpleNamespace(fact_id="later", locator_ids=["page-1"],
                        source_candidate_ids=["candidate-later"],
                        source_observation_refs=["observation-later"]),
    ]
    unlinked = analyze_observation_appearances(appearances, [], origins=origins)
    assert relation_service._merged_acquisition_scope_reasons(
        facts, ["first", "later"], graph=unlinked,
    ) == ["repeat_acquisition_identity_unverified"]
    linked = analyze_observation_appearances(
        appearances, [("repeat_of", repeat, initial, "initial_observation")], origins=origins,
    )
    assert relation_service._merged_acquisition_scope_reasons(
        facts, ["first", "later"], graph=linked,
    ) == []


def test_same_fact_repeat_relation_requires_a_source_quoted_chain():
    appearances = [_appearance("fact-1", "l1"), _appearance("fact-1", "l2")]
    edge = ("repeat_of", appearances[1]["appearance_id"],
            appearances[0]["appearance_id"], "initial_observation")
    graph = analyze_observation_appearances(
        appearances, [edge], origins={
            appearances[0]["appearance_id"]: "initial",
            appearances[1]["appearance_id"]: "repeat",
        },
    )
    fact = SimpleNamespace(
        fact_id="fact-1", source_candidate_ids=["c1", "c2"],
        source_observation_refs=["o1", "o2"], locator_ids=["l1", "l2"],
    )
    assert len(graph["acquisition_groups"]) == 2
    assert relation_service._merged_acquisition_scope_reasons(
        [fact], ["fact-1"], graph=graph,
    ) == []
    unlinked = analyze_observation_appearances(appearances, [])
    assert relation_service._merged_acquisition_scope_reasons(
        [fact], ["fact-1"], graph=unlinked,
    ) == ["repeat_acquisition_identity_unverified"]


def test_ordered_repeat_keeps_unique_facts_but_refuses_reused_fact_instances(monkeypatch):
    policy = SimpleNamespace(
        selection=SimpleNamespace(criterion="latest"),
        model_dump=lambda mode: {"selection": "latest"},
    )
    cases = [
        ([_appearance("same", "l1"), _appearance("same", "l2")],
         "repeat_ordering_instance_unverified"),
        ([_appearance("first", "l1"), _appearance("later", "l2")], None),
    ]
    monkeypatch.setattr(
        ordering, "select_qualified_observation_dates",
        lambda **kwargs: OrderedObservationSelection(("first",), ()),
    )
    for appearances, expected_reason in cases:
        graph = analyze_observation_appearances(appearances, [])
        group_ids = [item["group_id"] for item in graph["acquisition_groups"]]
        selected_group = next(
            (item["group_id"] for item in graph["acquisition_groups"]
             if "first" in item["fact_ids"]), group_ids[0],
        )
        observation = {"relationship_graph": graph, "supplied_scope": {"complete": True}}
        resolution = {
            "policy_selection": {"combination": None},
            "selected_group_ids": [selected_group], "multi_initial_selection": None,
        }
        facts = {item["fact_id"]: SimpleNamespace(date_range=None) for item in appearances}
        qualified = {(item["fact_id"], item["locator_id"], attribute)
                     for item in appearances for attribute in ("value", "date_range")}
        reasons, _ = ordering.reconcile_repeat_ordering(
            policy=policy, observation=observation, resolution=resolution,
            facts=facts, qualified=qualified, operand="value", semantic=False,
            time_constraint=None, anchor_dates={}, time_purpose="event_membership",
            conflicting_fact_ids=frozenset(),
        )
        if expected_reason:
            assert reasons == (expected_reason,)
        else:
            assert reasons == ()


def test_repeat_time_requires_the_date_at_each_source_position():
    appearances = [_appearance("same", "initial"), _appearance("same", "repeat")]
    initial, repeat = (item["appearance_id"] for item in appearances)
    graph = analyze_observation_appearances(
        appearances, [("repeat_of", repeat, initial, "initial_observation")],
        origins={initial: "initial", repeat: "repeat"},
    )
    scheme = RepeatScheme(
        scope="本次筛选", source_span_ids=["p"], source_excerpts=["三日内复查"],
        permission="required", trigger="unconditional", count_status="not_specified",
        time_status="specified", time_limit=RepeatTimeLimit(
            reference="initial_observation", direction="after",
            upper_bound=RepeatDuration(value=3, unit="day"),
        ), result_use="retain_initial",
    )
    supplied = {"graph_sha256": graph["graph_sha256"], "scope": "supplied_facts_only",
                "fact_ids": ["same"], "complete": True}

    def check(qualified):
        result = calculate_repeat_series_constraints(
            scheme, graph, supplied,
            fact_dates={"same": DateValue(value=date(2026, 9, 1), precision=DatePrecision.DAY)},
            qualified_date_fact_ids=frozenset({"same"}),
            qualified_date_appearance_ids=frozenset(qualified), anchor_dates={},
        )
        return result["time_checks"][0]["result"]["reason_codes"]

    assert "repeat_date_unverified" in check({initial})
    assert "repeat_date_unverified" not in check({initial, repeat})


def test_repeat_count_uses_only_linked_acquisitions_as_a_proven_lower_bound():
    appearances = [_appearance(key, key) for key in ("initial", "repeat-1", "repeat-2")]
    identifiers = {item["fact_id"]: item["appearance_id"] for item in appearances}
    origins = {item["appearance_id"]: ("initial" if item["fact_id"] == "initial" else "repeat")
               for item in appearances}
    scheme = RepeatScheme(
        scope="本次筛选", source_span_ids=["p"], source_excerpts=["本次最多复查一次"],
        permission="required", trigger="unconditional", count_status="specified",
        count_scope="per_current_episode", maximum_repeats=1,
        time_status="not_specified", result_use="retain_initial",
    )

    def check(links):
        graph = analyze_observation_appearances(appearances, links, origins=origins)
        scope = {"graph_sha256": graph["graph_sha256"], "scope": "supplied_facts_only",
                 "fact_ids": sorted(identifiers), "complete": True}
        result = calculate_repeat_series_constraints(
            scheme, graph, scope, fact_dates={}, qualified_date_fact_ids=frozenset(),
            anchor_dates={}, qualified_episode_memberships={key: "current_episode"
                for key in identifiers}, episode_sha256="a" * 64,
        )
        return result["count_result"]["truth"], result["counted_repeat_group_ids"]

    no_links, none_counted = check([])
    assert no_links == "unknown" and none_counted == []
    one_link, one_counted = check([
        ("repeat_of", identifiers["repeat-1"], identifiers["initial"], "initial_observation"),
    ])
    assert one_link == "unknown" and len(one_counted) == 1
    two_links, two_counted = check([
        ("repeat_of", identifiers[key], identifiers["initial"], "initial_observation")
        for key in ("repeat-1", "repeat-2")
    ])
    assert two_links == "false" and len(two_counted) == 2


def test_v6_reader_requires_each_source_and_both_link_quotes():
    group = SimpleNamespace(
        pair_id="a" * 64, version="observation-relation/v6",
        members=[SimpleNamespace(fact_id="fact-1", locator_id=key,
                                 locator={"excerpt": _quote(key)["excerpt"]})
                 for key in ("l1", "l2")],
        auxiliary_members=[], scheme=SimpleNamespace(count_scope="per_initial_acquisition"),
    )
    answer = {
        "results": [{
            "pair_id": group.pair_id, "reviewed_fact_ids": ["fact-1"],
            "reviewed_appearances": [
                {"fact_id": "fact-1", "locator_id": key} for key in ("l1", "l2")
            ],
            "links": [_link()],
            "origins": [{"fact_id": "fact-1", "locator_id": key,
                         "role": "initial", "quotes": [_quote(key)],
                         "explanation": "原文标记初查"} for key in ("l1", "l2")],
            "unresolved_notes": [], "reviewed_auxiliary_pair_ids": [],
            "auxiliary_associations": [], "auxiliary_unresolved_notes": [],
            "episode_memberships": [],
        }],
    }
    assert validate_observation_relation_payload([group], json.dumps(answer)).results[0].links
    missing = json.loads(json.dumps(answer))
    missing["results"][0]["reviewed_appearances"].pop()
    with pytest.raises(ValueError, match="逐处|覆盖"):
        validate_observation_relation_payload([group], json.dumps(missing))
    fact_only = json.loads(json.dumps(answer))
    fact_only["results"][0]["links"][0].pop("left_locator_id")
    fact_only["results"][0]["links"][0].pop("right_locator_id")
    with pytest.raises(ValueError, match="原文位置|本组以外|不同记录"):
        validate_observation_relation_payload([group], json.dumps(fact_only))
    duplicate_reference = deepcopy(answer)
    duplicate_reference["results"][0]["links"] = [
        {**_link(), "relation": "repeat_of", "reference_kind": kind}
        for kind in ("initial_observation", "preceding_observation")
    ]
    with pytest.raises(ValueError, match="回指|冲突"):
        validate_observation_relation_payload([group], json.dumps(duplicate_reference))


def test_two_readers_agree_on_the_same_source_presentations(monkeypatch):
    group = SimpleNamespace(
        pair_id="a" * 64, version="observation-relation/v6",
        identity_sha256="b" * 64,
        members=[SimpleNamespace(fact_id="fact-1", locator_id=key,
                                 locator={"excerpt": _quote(key)["excerpt"]})
                 for key in ("l1", "l2")],
        auxiliary_members=[], scheme=SimpleNamespace(count_scope="per_initial_acquisition"),
    )
    answer = {
        "results": [{
            "pair_id": group.pair_id, "reviewed_fact_ids": ["fact-1"],
            "reviewed_appearances": [{"fact_id": "fact-1", "locator_id": key}
                                     for key in ("l1", "l2")],
            "links": [_link()],
            "origins": [{"fact_id": "fact-1", "locator_id": key,
                         "role": "initial", "quotes": [_quote(key)],
                         "explanation": "原文标记初查"} for key in ("l1", "l2")],
            "unresolved_notes": [], "reviewed_auxiliary_pair_ids": [],
            "auxiliary_associations": [], "auxiliary_unresolved_notes": [],
            "episode_memberships": [],
        }],
    }
    checked = validate_observation_relation_payload([group], json.dumps(answer))
    batch = BindingQualificationBatch.model_construct(
        batch_sha256="c" * 64, frozen_input_sha256="d" * 64,
        candidate_job_id="candidate", pair_ids=[group.pair_id],
        identity_sha256s=[group.identity_sha256], fact_ids=["fact-1"],
        locator_ids=["l1", "l2"],
    )
    messages = [{"role": "user", "content": "frozen source"}]
    monkeypatch.setattr(receipts, "build_observation_relation_messages", lambda *_: messages)
    reads = {}
    for lane, provider in (("main-A", "A"), ("main-B", "B")):
        reads[lane] = SimpleNamespace(
            payload=checked, lane=lane, requested_provider=provider,
            requested_model=provider, frozen_input_sha256=batch.frozen_input_sha256,
            batch_sha256=batch.batch_sha256, messages_sha256=canonical_hash(messages),
        )
    payload = {field: "frozen" for field in receipts.INPUT_FIELDS if field != "pairs"}
    result = receipts.compose_observation_relation_summary(
        payload=payload, pairs=[group], batches=[batch],
        lane_reads={batch.batch_sha256: reads},
        lane_receipts={batch.batch_sha256: {"main-A": ["receipt-a"], "main-B": ["receipt-b"]}},
    )
    comparison = result["comparisons"][0]
    assert result["version"] == "observation-relation-summary/v7"
    assert len(comparison["relationship_graph"]["acquisition_groups"]) == 1
    assert len(comparison["agreed_origins"]) == 2
    assert comparison["disputed_relationships"] == []

    for lane, kind in (("main-A", "initial_observation"),
                       ("main-B", "preceding_observation")):
        revised = deepcopy(answer)
        row = revised["results"][0]
        row["links"] = [{**_link(), "relation": "repeat_of", "reference_kind": kind}]
        row["origins"][0]["role"] = "initial"
        row["origins"][1]["role"] = "repeat"
        reads[lane].payload = validate_observation_relation_payload(
            [group], json.dumps(revised),
        )
    with_reference_disagreement = receipts.compose_observation_relation_summary(
        payload=payload, pairs=[group], batches=[batch],
        lane_reads={batch.batch_sha256: reads},
        lane_receipts={batch.batch_sha256: {"main-A": ["receipt-a"], "main-B": ["receipt-b"]}},
    )["comparisons"][0]
    assert with_reference_disagreement["disputed_relationships"] == []
    assert with_reference_disagreement["disputed_reference_kinds"][0]["main-A"] == "initial_observation"
    assert with_reference_disagreement["agreed_relationships"][0][-1] == "unspecified"
    assert len(with_reference_disagreement["relationship_graph"]["repeat_edges"]) == 1


def test_qualified_source_accepts_proven_same_acquisition_but_not_two_unproven_instances(monkeypatch):
    identity = "a" * 64
    locators = ("l1", "l2")
    members = [SimpleNamespace(
        pair_id=f"pair-{key}", fact_id="fact-1", locator_id=key,
        fact_attribute="value", identity_sha256=identity,
        identity_field="predicate_identity_sha256",
        locator={"excerpt": _quote(key)["excerpt"]}, episode={"anchor_dates": {}},
    ) for key in locators]
    group = SimpleNamespace(pair_id="group-1", identity_sha256=identity,
                            members=members, auxiliary_members=[], scheme=object())
    origins = [
        {"fact_id": "fact-1", "locator_id": key, "quotes": [_quote(key)]}
        for key in locators
    ]
    link = ObservationRelationLink.model_validate(_link()).agreement_key()
    appearances = [_appearance("fact-1", key) for key in locators]

    def evidence(linked):
        graph = analyze_observation_appearances(
            appearances, [appearance_relationship_edge(link)] if linked else [],
            origins={item["appearance_id"]: "initial" for item in appearances},
        )
        lane = {"links": [_link()] if linked else [], "origins": origins,
                "episode_memberships": [], "auxiliary_associations": [],
                "unresolved_notes": [], "auxiliary_unresolved_notes": []}
        return {"pairs": [group], "summary_sha256": "b" * 64, "summary": {"comparisons": [{
            "group_id": group.pair_id, "relationship_graph": graph,
            "lanes": {"main-A": lane, "main-B": lane},
            "agreed_relationships": [list(link)] if linked else [],
            "agreed_origins": [{"appearance_id": item["appearance_id"], "role": "initial"}
                                for item in appearances],
            "agreed_episode_memberships": [], "disputed_relationships": [],
            "agreed_auxiliary_associations": [], "disputed_auxiliary_associations": [],
            "auxiliary_pairs_without_agreed_association": [],
        }]}}

    records = [SimpleNamespace(pair_id=item.pair_id, identity_sha256=identity,
                               fact_id=item.fact_id, locator_id=item.locator_id,
                               fact_attribute=item.fact_attribute) for item in members]
    accounting = [{"predicate_identity_sha256": identity, "fact_accounting": [
        {"fact_id": "fact-1", "status": "candidates_in_both_lanes"},
    ]}]
    frozen_fact = SimpleNamespace(
        fact_id="fact-1", source_candidate_ids=["c1", "c2"],
        source_observation_refs=["o1", "o2"], locator_ids=list(locators), date_range=None,
    )
    from app.services import qualified_binding_selection
    monkeypatch.setattr(qualified_binding_selection, "pair_direct_selection_rejection_reasons",
                        lambda *args, **kwargs: [])
    monkeypatch.setattr(qualified_binding_selection, "source_validity_operand_calculable",
                        lambda *args, **kwargs: True)
    monkeypatch.setattr(relation_service, "calculate_repeat_series_constraints", lambda *args, **kwargs: {})
    monkeypatch.setattr(relation_service, "select_repeat_result_groups", lambda *args, **kwargs:
                        RepeatResultSelection(graph_sha256="a" * 64, scheme_sha256="b" * 64,
                                              supplied_scope_sha256="c" * 64,
                                              considered_group_ids=()))

    def result(linked):
        return relation_service.select_qualified_observation_relations(
            evidence(linked), records, frozen_facts=[frozen_fact],
            candidate_fact_accounting=accounting,
        )[0]

    accepted = result(True)
    assert accepted["supplied_scope"]["complete"] is True
    assert accepted["supplied_scope"]["initial_scope"]["complete"] is True
    assert len(accepted["relationship_graph"]["acquisition_groups"]) == 1
    unproven = result(False)
    assert unproven["supplied_scope"]["complete"] is False
    assert "repeat_acquisition_identity_unverified" in unproven["supplied_scope"]["reason_codes"]

    differing_reference = evidence(True)
    comparison = differing_reference["summary"]["comparisons"][0]
    for lane, kind in (("main-A", "initial_observation"),
                       ("main-B", "preceding_observation")):
        lane_result = deepcopy(comparison["lanes"][lane])
        lane_result["links"] = [{**_link(), "left_locator_id": "l2", "right_locator_id": "l1",
                                 "relation": "repeat_of", "reference_kind": kind}]
        lane_result["origins"][1]["role"] = "repeat"
        comparison["lanes"][lane] = lane_result
    comparison["agreed_relationships"] = [[
        "repeat_of", ["fact-1", "l2"], ["fact-1", "l1"], "unspecified",
    ]]
    comparison["agreed_origins"][1]["role"] = "repeat"
    comparison["disputed_reference_kinds"] = [{"main-A": "initial_observation",
                                                "main-B": "preceding_observation"}]
    qualified = relation_service.select_qualified_observation_relations(
        differing_reference, records, frozen_facts=[frozen_fact],
        candidate_fact_accounting=accounting,
    )[0]
    assert qualified["disputed_relationships"] == []
    assert len(qualified["relationship_graph"]["repeat_edges"]) == 1
    assert qualified["relationship_graph"]["repeat_edges"][0]["reference_kind"] == "unspecified"
