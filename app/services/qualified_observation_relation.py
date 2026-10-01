"""Intersect dual observation references with qualified source locations."""
from dataclasses import asdict

from app.domain.observation_relation_graph import (
    analyze_observation_appearances, analyze_observation_relationships,
    appearance_relationship_edge, observation_appearance_id,
    reused_fact_groups_follow_source_chain,
)
from app.domain.publication import canonical_hash
from app.domain.repeat_result_selection import select_repeat_result_groups
from app.domain.repeat_series_constraints import calculate_repeat_series_constraints
from app.services.observation_relation_job import verify_completed_observation_relation
from app.services.review_method_evidence import read_method_evaluation
from app.storage.repositories import ScopeViolationError

OBSERVATION_CONSUMER_VERSION = "qualified-observation-relation/v13"


def _merged_acquisition_scope_reasons(frozen_facts, member_fact_ids, *, graph=None):
    """Source appearances cannot establish distinct clinical acquisitions."""
    selected = set(member_fact_ids)
    if graph is not None and graph.get("version") == "observation-relation-graph/v3":
        appearances = graph["appearances"]
        by_fact = {}
        for item in graph["acquisition_groups"]:
            for fact_id in item["fact_ids"]:
                by_fact.setdefault(fact_id, set()).add(item["group_id"])
        if not reused_fact_groups_follow_source_chain(graph):
            return ["repeat_acquisition_identity_unverified"]
        appeared = {item["fact_id"]: set() for item in appearances}
        for item in appearances:
            appeared[item["fact_id"]].add(item["locator_id"])
        for fact in frozen_facts:
            if fact.fact_id not in selected:
                continue
            if appeared.get(fact.fact_id) != set(fact.locator_ids):
                return ["repeat_acquisition_identity_unverified"]
        predecessors = {}
        for edge in graph["repeat_edges"]:
            predecessors.setdefault(edge["repeat_group_id"], set()).add(edge["prior_group_id"])

        def linked_by_repeat(left, right):
            pending, visited = [left], set()
            while pending:
                current = pending.pop()
                if current == right:
                    return True
                if current not in visited:
                    visited.add(current)
                    pending.extend(predecessors.get(current, ()))
            return False

        def groups_comparable(left, right):
            return left == right or linked_by_repeat(left, right) or linked_by_repeat(right, left)

        # Shared source handles may only be collapsed inside the same proven
        # acquisition. One locator may contain separate measurements, but only
        # a quoted repeat chain can establish their distinct identities.
        owners = {}
        for fact in frozen_facts:
            if fact.fact_id not in selected:
                continue
            group_ids = by_fact[fact.fact_id]
            for kind, values in (
                ("candidate", fact.source_candidate_ids),
                ("observation", fact.source_observation_refs),
                ("locator", fact.locator_ids),
            ):
                for value in values:
                    key = kind, value
                    if key in owners and not owners[key] & group_ids:
                        if (kind != "locator" or not all(
                            groups_comparable(left, right)
                            for left in owners[key] for right in group_ids
                        )):
                            return ["repeat_acquisition_identity_unverified"]
                    owners.setdefault(key, set()).update(group_ids)
        return []
    seen_candidates: set[str] = set()
    seen_observations: set[str] = set()
    seen_locators: set[str] = set()
    for fact in frozen_facts:
        if fact.fact_id not in selected:
            continue
        if (len(fact.source_candidate_ids) > 1 or len(fact.locator_ids) > 1
                or len(fact.source_observation_refs) > 1):
            return ["repeat_acquisition_identity_unverified"]
        candidates = set(fact.source_candidate_ids)
        observations = set(fact.source_observation_refs)
        locators = set(fact.locator_ids)
        if (candidates & seen_candidates or observations & seen_observations
                or locators & seen_locators):
            return ["repeat_acquisition_identity_unverified"]
        seen_candidates.update(candidates)
        seen_observations.update(observations)
        seen_locators.update(locators)
    return []


def _frozen_relationship_key(value):
    return tuple(tuple(item) if isinstance(item, list) else item for item in value)


def require_observation_method(manifest, binding_method, evidence):
    methods = [item for item in manifest.methods if item.candidate_family == binding_method.candidate_family]
    if manifest.evaluation_kind != "observation_relationship_fidelity" or len(methods) != 1:
        raise ScopeViolationError("复查对应尚无本类要求的专门评测")
    method = methods[0]
    if (method.source_qualification_method != binding_method
            or method.content_contract != evidence["contract"]
            or method.content_prompt_version != evidence["prompt_version"]
            or method.content_summary_version != evidence["summary"]["version"]
            or {key: value.model_dump(mode="json") for key, value in method.content_routes.items()} != evidence["routes"]
            or method.content_consumer_version != OBSERVATION_CONSUMER_VERSION):
        raise ScopeViolationError("复查核对的来源、提示、模型配置或采用方法与评测版本不同")


def verify_qualified_observation_relation(session, artifact_store, *, source, binding_method, adoption):
    evidence = verify_completed_observation_relation(session, artifact_store, adoption.job_id)
    payload = evidence["payload"]
    if (payload["candidate_job_id"] != source["payload"]["candidate_job_id"]
            or any(payload.get(key) is None or payload[key] != source["payload"].get(key)
                   for key in ("review_context_id", "review_context_sha256", "frozen_input_sha256", "comparison_sha256"))
            or evidence["summary_sha256"] != adoption.summary_logical_sha256
            or evidence["summary_artifact_sha256"] != adoption.summary_artifact_sha256):
        raise ScopeViolationError("复查对应结果与本次资料及审核节点不一致")
    sources = {pair.pair_id: pair for pair in source["pairs"]}
    if any(sources.get(member.pair_id) != member or member.candidate_family != source["candidate_family"]
           for group in evidence["pairs"] for member in group.source_members):
        raise ScopeViolationError("复查对应原文不属于本次已核实的来源")
    require_observation_method(read_method_evaluation(artifact_store, adoption.evaluation_sha256),
                               binding_method, evidence)
    return evidence


def select_qualified_observation_relations(
    evidence, source_records, *, frozen_facts, candidate_fact_accounting, source_validity_specs=None,
    written_content_verified_pair_ids=frozenset(),
):
    """Qualify every cited location, retaining unresolved links and original lanes.

    This is evidence correspondence, not proof of complete visits or permission.
    No absence, origin, or relation is inferred from discarded source references.
    """
    from app.services.qualified_binding_selection import (
        pair_direct_selection_rejection_reasons, source_validity_operand_calculable,
    )
    from app.services.ordered_observation_selection import observation_scope_reasons
    from app.services.eligibility_review_projection import _phase3_date_value
    records = {item.pair_id: item for item in source_records}
    groups = {item.pair_id: item for item in evidence["pairs"]}
    specs = source_validity_specs or {}
    output = []
    for comparison in evidence["summary"]["comparisons"]:
        group = groups[comparison["group_id"]]
        appearance_graph = comparison.get("relationship_graph", {}).get("version") == "observation-relation-graph/v3"
        appearances = sorted({(item.fact_id, item.locator_id) for item in group.members})
        appearance_rows = [
            {"fact_id": fact_id, "locator_id": locator_id,
             "appearance_id": observation_appearance_id(fact_id, locator_id)}
            for fact_id, locator_id in appearances
        ]
        members = {}
        for item in group.members:
            members.setdefault((item.fact_id, item.locator_id), []).append(item)
        qualified_source_pair_ids = set()

        def quote_reasons(quotes, *, auxiliary_pair=None):
            reasons = []
            for quote in quotes:
                candidates = ((auxiliary_pair,) if auxiliary_pair is not None
                              else members.get((quote["fact_id"], quote["locator_id"]), ()))
                rejected, admitted = [], []
                for pair in candidates:
                    record = records.get(pair.pair_id)
                    excerpt = pair.locator.get("excerpt")
                    if (record is None or record.identity_sha256 != pair.identity_sha256
                            or record.fact_id != pair.fact_id or record.locator_id != pair.locator_id
                            or record.fact_attribute != pair.fact_attribute
                            or (quote["fact_id"], quote["locator_id"]) != (pair.fact_id, pair.locator_id)
                            or not isinstance(excerpt, str) or not quote["excerpt"].strip()
                            or quote["excerpt"] not in excerpt):
                        rejected.append("source_qualification_missing")
                        continue
                    failures = pair_direct_selection_rejection_reasons(
                        record, written_content_verified=pair.pair_id in written_content_verified_pair_ids,
                        source_validity_calculable=source_validity_operand_calculable(
                            record, specs.get(record.identity_sha256)))
                    if failures:
                        rejected.extend(failures)
                    else:
                        admitted.append(pair.pair_id)
                if admitted:
                    qualified_source_pair_ids.update(admitted)
                else:
                    reasons.extend(rejected or ["source_qualification_missing"])
            return sorted(set(reasons))

        from app.domain.contracts.observation_relation import ObservationRelationLink
        lanes = comparison["lanes"]
        links = [{ObservationRelationLink.model_validate(item).agreement_key(): item
                  for item in lanes[lane]["links"]} for lane in ("main-A", "main-B")]
        origins = [{(observation_appearance_id(item["fact_id"], item["locator_id"])
                    if appearance_graph else item["fact_id"]): item
                    for item in lanes[lane]["origins"]}
                   for lane in ("main-A", "main-B")]
        qualified_links, qualified_origins, unresolved = [], {}, []
        for raw in comparison["agreed_relationships"]:
            key = _frozen_relationship_key(raw)
            lane_sources = [lane_links.get(key) or next(
                (item for candidate, item in lane_links.items() if candidate[:3] == key[:3]), None,
            ) for lane_links in links]
            if any(item is None for item in lane_sources):
                raise ScopeViolationError("两路复查关系的共同回指缺少原文来源")
            reasons = sorted({reason for item in lane_sources
                              for reason in quote_reasons(item["quotes"])})
            if reasons:
                unresolved.append({"relationship": raw, "reasons": reasons})
            else:
                qualified_links.append(key)
        for agreed in comparison["agreed_origins"]:
            fact_id = agreed["appearance_id"] if appearance_graph else agreed["fact_id"]
            reasons = sorted({reason for lane_origins in origins
                              for reason in quote_reasons(lane_origins[fact_id]["quotes"])})
            if reasons:
                unresolved.append({"fact_id": fact_id, "reasons": reasons})
            else:
                qualified_origins[fact_id] = agreed["role"]
        if appearance_graph:
            graph = analyze_observation_appearances(
                appearance_rows, [appearance_relationship_edge(key) for key in qualified_links],
                origins=qualified_origins,
            )
        else:
            graph = analyze_observation_relationships(
                sorted({item.fact_id for item in group.members}), qualified_links,
                origins=qualified_origins,
            )
        membership_lanes = [{(observation_appearance_id(item["fact_id"], item["locator_id"])
                             if appearance_graph else item["fact_id"]): item
                             for item in lanes[lane]["episode_memberships"]}
                            for lane in ("main-A", "main-B")]
        qualified_memberships, membership_unresolved = {}, []
        for agreed in comparison["agreed_episode_memberships"]:
            fact_id = agreed["appearance_id"] if appearance_graph else agreed["fact_id"]
            reasons = sorted({reason for lane_memberships in membership_lanes
                              for reason in quote_reasons(lane_memberships[fact_id]["quotes"])})
            if reasons:
                membership_unresolved.append({"fact_id": fact_id, "reasons": reasons})
            else:
                qualified_memberships[fact_id] = agreed["membership"]
        # Auxiliary evidence belongs to an examination but is never a result operand.
        auxiliary_members = {item.pair_id: item for item in group.auxiliary_members}
        auxiliary_lanes = [{(item["auxiliary_pair_id"], item["observation_fact_id"]): item
                            for item in lanes[lane]["auxiliary_associations"]}
                           for lane in ("main-A", "main-B")]
        acquisition_by_fact = {}
        for item in graph["acquisition_groups"]:
            for fact_id in item["fact_ids"]:
                acquisition_by_fact.setdefault(fact_id, set()).add(item["group_id"])
        qualified_auxiliary, auxiliary_unresolved = [], []
        for raw in comparison["agreed_auxiliary_associations"]:
            key = tuple(raw)
            member = auxiliary_members[key[0]]
            reasons = []
            for lane in auxiliary_lanes:
                association = lane[key]
                reasons.extend(quote_reasons(association["observation_quotes"]))
                reasons.extend(quote_reasons([{
                    "fact_id": member.fact_id, "locator_id": member.locator_id,
                    "excerpt": association["auxiliary_excerpt"],
                }], auxiliary_pair=member))
            if reasons:
                auxiliary_unresolved.append({"association": raw, "reasons": sorted(set(reasons))})
            else:
                if len(acquisition_by_fact[key[1]]) != 1:
                    auxiliary_unresolved.append({
                        "association": raw,
                        "reasons": ["auxiliary_observation_assignment_ambiguous"],
                    })
                    continue
                shared_scope_quotes = [lane[key].get("shared_scope_excerpt") for lane in auxiliary_lanes]
                shared_scope_verified = all(shared_scope_quotes)
                if shared_scope_verified:
                    shared_scope_verified = not any(quote_reasons([{
                        "fact_id": member.fact_id, "locator_id": member.locator_id,
                        "excerpt": quote,
                    }], auxiliary_pair=member) for quote in shared_scope_quotes)
                qualified_auxiliary.append({
                    "auxiliary_pair_id": member.pair_id, "identity_sha256": member.identity_sha256,
                    "fact_id": member.fact_id, "locator_id": member.locator_id,
                    "fact_attribute": member.fact_attribute, "observation_fact_id": key[1],
                    "acquisition_group_id": next(iter(acquisition_by_fact[key[1]])),
                    "shared_scope_verified": shared_scope_verified,
                    "shared_scope_excerpts": shared_scope_quotes if shared_scope_verified else [],
                })
        auxiliary_groups = {}
        for item in qualified_auxiliary:
            auxiliary_groups.setdefault(item["auxiliary_pair_id"], set()).add(item["acquisition_group_id"])
        ambiguous_pairs = {key for key, values in auxiliary_groups.items() if len(values) > 1
                           and not all(item["shared_scope_verified"] for item in qualified_auxiliary
                                       if item["auxiliary_pair_id"] == key)}
        if ambiguous_pairs:
            auxiliary_unresolved.extend({
                "auxiliary_pair_id": key, "acquisition_group_ids": sorted(auxiliary_groups[key]),
                "reasons": ["auxiliary_observation_assignment_ambiguous"],
            } for key in sorted(ambiguous_pairs))
            qualified_auxiliary = [item for item in qualified_auxiliary
                                   if item["auxiliary_pair_id"] not in ambiguous_pairs]
        accounting = [row for item in candidate_fact_accounting
                      if item.get(group.members[0].identity_field) == group.identity_sha256
                      for row in item["fact_accounting"]]
        accounting_reasons = list(observation_scope_reasons(
            facts={item.fact_id: item for item in frozen_facts},
            operand_fact_ids=sorted({item.fact_id for item in group.members}), accounting=accounting,
        ))
        scope_reasons = list(accounting_reasons)
        scope_reasons.extend(_merged_acquisition_scope_reasons(
            frozen_facts, (item.fact_id for item in group.members),
            graph=graph if appearance_graph else None,
        ))
        if unresolved:
            scope_reasons.append("repeat_correspondence_sources_unverified")
        if comparison["disputed_relationships"]:
            scope_reasons.append("repeat_correspondence_disagreement")
        if any(lanes[lane]["unresolved_notes"] for lane in ("main-A", "main-B")):
            scope_reasons.append("repeat_correspondence_notes_unresolved")
        scope_reasons.extend(graph["structural_reasons"])
        if graph["origin_unresolved_appearance_ids" if appearance_graph else "origin_unresolved_fact_ids"]:
            scope_reasons.append("repeat_origin_unverified")
        supplied_scope = {
            "version": "repeat-supplied-scope/v1", "scope": "supplied_facts_only",
            "accounting_sha256": canonical_hash(accounting), "graph_sha256": graph["graph_sha256"],
            "fact_ids": sorted({item.fact_id for item in group.members}),
            "complete": not scope_reasons, "reason_codes": sorted(set(scope_reasons)),
        }
        initial_groups = [item["group_id"] for item in graph["acquisition_roles"] if item["role"] == "initial"]
        repeat_groups = tuple(item["group_id"] for item in graph["acquisition_roles"] if item["role"] == "repeat")
        initial_ids = {key for item in graph["acquisition_groups"] if item["group_id"] in initial_groups
                       for key in item["fact_ids"]}
        initial_appearance_ids = {key for item in graph["acquisition_groups"]
                                  if item["group_id"] in initial_groups
                                  for key in item.get("appearance_ids", ())}
        initial_reasons = list(accounting_reasons)
        initial_reasons.extend(_merged_acquisition_scope_reasons(
            frozen_facts, initial_ids, graph=graph if appearance_graph else None,
        ))
        if len(initial_groups) != 1:
            initial_reasons.append("repeat_initial_scope_not_unique")
        # Every supplied candidate must have a verified origin: an unknown
        # candidate could be another initial examination, not just a repeat.
        for member in group.members:
            origin_key = (observation_appearance_id(member.fact_id, member.locator_id)
                          if appearance_graph else member.fact_id)
            expected_role = ("initial" if origin_key in initial_appearance_ids else "repeat") if appearance_graph else (
                "initial" if member.fact_id in initial_ids else "repeat"
            )
            if qualified_origins.get(origin_key) != expected_role:
                initial_reasons.append("repeat_initial_scope_unverified")
        def affects_initial(edge):
            if appearance_graph:
                edge = appearance_relationship_edge(edge)
                selected = initial_appearance_ids
            else:
                selected = initial_ids
            return (bool(set(edge[1:3]) & selected) if edge[0] == "same_acquisition"
                    else edge[1] in selected)
        if any(affects_initial(item) for item in comparison["disputed_relationships"]):
            initial_reasons.append("repeat_correspondence_disagreement")
        if any("relationship" in item and affects_initial(item["relationship"]) for item in unresolved):
            initial_reasons.append("repeat_correspondence_sources_unverified")
        if appearance_graph:
            initial_graph = analyze_observation_appearances(
                appearance_rows,
                [appearance_relationship_edge(edge) for edge in qualified_links if affects_initial(edge)],
                origins=qualified_origins,
            )
        else:
            initial_graph = analyze_observation_relationships(
                sorted({item.fact_id for item in group.members}),
                [edge for edge in qualified_links if affects_initial(edge)], origins=qualified_origins,
            )
        initial_reasons.extend(initial_graph["structural_reasons"])
        # Free-text doubts have no proven target; do not guess they concern
        # only repeats. Structured repeat-link doubts are separated above.
        if any(lanes[lane]["unresolved_notes"] for lane in ("main-A", "main-B")):
            initial_reasons.append("repeat_correspondence_notes_unresolved")
        supplied_scope["initial_scope"] = {
            "version": "repeat-initial-scope/v1", "group_ids": initial_groups,
            "fact_ids": sorted(initial_ids), "complete": not initial_reasons,
            "reason_codes": sorted(set(initial_reasons)),
        }
        policy_selection = None
        selection_reasons = []
        if len(initial_groups) == 1:
            policy_selection = asdict(select_repeat_result_groups(
                group.scheme, graph, initial_group_id=initial_groups[0],
                repeat_group_ids=repeat_groups, scope_complete=not scope_reasons,
                supplied_scope_sha256=canonical_hash(supplied_scope),
                initial_scope_complete=not initial_reasons,
            ))
        else:
            selection_reasons.append("repeat_initial_scope_not_unique" if initial_groups
                                     else "repeat_initial_scope_unverified")
        operand_pairs = []
        for member in group.members:
            record = records.get(member.pair_id)
            if (record is not None and record.identity_sha256 == group.identity_sha256
                    and record.fact_id == member.fact_id and record.locator_id == member.locator_id
                    and record.fact_attribute == member.fact_attribute
                    and not pair_direct_selection_rejection_reasons(
                        record, written_content_verified=record.pair_id in written_content_verified_pair_ids,
                        source_validity_calculable=source_validity_operand_calculable(
                            record, specs.get(record.identity_sha256)))):
                operand_pairs.append({"pair_id": record.pair_id, "fact_id": record.fact_id,
                                      "fact_attribute": record.fact_attribute,
                                      **({"locator_id": record.locator_id} if appearance_graph else {})})
        if appearance_graph:
            membership_by_fact = {}
            for item in appearance_rows:
                membership_by_fact.setdefault(item["fact_id"], []).append(
                    qualified_memberships.get(item["appearance_id"]),
                )
            series_memberships = {
                fact_id: values[0] for fact_id, values in membership_by_fact.items()
                if values[0] is not None and len(set(values)) == 1
            }
        else:
            series_memberships = qualified_memberships
        series_constraints = calculate_repeat_series_constraints(
            group.scheme, graph, supplied_scope,
            fact_dates={item.fact_id: _phase3_date_value(item.date_range) for item in frozen_facts},
            qualified_date_fact_ids=frozenset(item["fact_id"] for item in operand_pairs
                                              if item["fact_attribute"] == "date_range"),
            qualified_date_appearance_ids=frozenset(
                observation_appearance_id(item["fact_id"], item["locator_id"])
                for item in operand_pairs if appearance_graph and item["fact_attribute"] == "date_range"
            ),
            anchor_dates=group.members[0].episode.get("anchor_dates", {}),
            qualified_episode_memberships=series_memberships,
            episode_sha256=canonical_hash(group.members[0].episode),
        )
        output.append({
            "group_id": group.pair_id, "identity_sha256": group.identity_sha256,
            "source_summary_sha256": evidence["summary_sha256"],
            "qualified_relationships": [list(key) for key in sorted(qualified_links)],
            "qualified_origins": qualified_origins,
            "qualified_episode_memberships": qualified_memberships,
            "episode_membership_source_unresolved": membership_unresolved,
            "source_unresolved": unresolved,
            "qualified_source_pair_ids": sorted(qualified_source_pair_ids),
            "disputed_relationships": comparison["disputed_relationships"],
            "disputed_reference_kinds": comparison.get("disputed_reference_kinds", []),
            "relationship_graph": graph,
            "supplied_scope": supplied_scope,
            "result_policy_selection": policy_selection,
            "result_policy_selection_reasons": selection_reasons,
            "qualified_operand_pairs": sorted(operand_pairs, key=lambda item: item["pair_id"]),
            "series_constraints": series_constraints,
            "qualified_auxiliary_associations": qualified_auxiliary,
            "auxiliary_source_unresolved": auxiliary_unresolved,
            "auxiliary_unresolved_notes": {
                lane: lanes[lane]["auxiliary_unresolved_notes"] for lane in ("main-A", "main-B")
            },
            "disputed_auxiliary_associations": comparison["disputed_auxiliary_associations"],
            "auxiliary_pairs_without_agreed_association": comparison["auxiliary_pairs_without_agreed_association"],
            "clinical_scope_complete": False, "replacement_authorized": False,
        })
    return output
