"""Structural relationship checks; a well-formed graph does not prove permission."""
from graphlib import CycleError, TopologicalSorter

from app.domain.publication import canonical_hash


def analyze_observation_relationships(fact_ids, relationships, *, origins=None):
    identifiers = set(fact_ids)
    if len(identifiers) != len(fact_ids) or any(not isinstance(item, str) or not item for item in identifiers):
        raise ValueError("观察关系图的记录身份无效")
    if origins is not None and (not isinstance(origins, dict) or not set(origins) <= identifiers
                               or any(value not in {"initial", "repeat"} for value in origins.values())):
        raise ValueError("观察次序须来自本组记录的明确原文，不能补推未核实身份")
    edges = [tuple(item) for item in relationships]
    if len(set(edges)) != len(edges):
        raise ValueError("观察关系图不得重复记录同一关系")
    for edge in edges:
        if (len(edge) not in {3, 4} or edge[0] not in {"repeat_of", "same_acquisition"}
                or not set(edge[1:3]) <= identifiers or edge[1] == edge[2]
                or len(edge) == 4 and (edge[0] != "repeat_of" or edge[3] not in {
                    "initial_observation", "preceding_observation", "unspecified"})):
            raise ValueError("观察关系图包含不属于本次原文的关系")
    parent = {item: item for item in identifiers}

    def root(item):
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    for edge in edges:
        relation, left, right = edge[:3]
        if relation == "same_acquisition":
            a, b = sorted((root(left), root(right)))
            parent[b] = a
    groups = {}
    for item in sorted(identifiers):
        groups.setdefault(root(item), []).append(item)
    group_ids = {key: canonical_hash({"version": "observation-acquisition-group/v1", "fact_ids": members})
                 for key, members in groups.items()}
    source_roles = {group_ids[key]: {origins[item] for item in members if item in origins}
                    for key, members in groups.items()} if origins is not None else {}
    directed = set()
    reasons = []
    if any(len(values) > 1 for values in source_roles.values()):
        reasons.append("same_acquisition_origin_conflict")
    for edge in edges:
        relation, left, right = edge[:3]
        if relation != "repeat_of":
            continue
        child, prior = group_ids[root(left)], group_ids[root(right)]
        directed.add((child, prior, edge[3] if len(edge) == 4 else None))
        if child == prior:
            reasons.append("repeat_and_same_acquisition_conflict")
        if "initial" in source_roles.get(child, set()):
            reasons.append("initial_marked_as_repeat")
        if len(edge) == 4 and edge[3] == "initial_observation" and "repeat" in source_roles.get(prior, set()):
            reasons.append("repeat_reference_origin_conflict")
    predecessors = {group_id: set() for group_id in group_ids.values()}
    by_reference = {}
    for child, prior, reference in directed:
        predecessors[child].add(prior)
        by_reference.setdefault((child, reference), set()).add(prior)
    if any(len(values) > 1 for values in by_reference.values()):
        reasons.append("repeat_predecessor_ambiguous")
    try:
        TopologicalSorter(predecessors).prepare()
    except CycleError:
        reasons.append("repeat_relationship_cycle")
    # Initial and immediately preceding can be the same acquisition. They
    # conflict only when an agreed intervening acquisition disproves adjacency.
    for child, prior, reference in directed:
        if reference != "preceding_observation":
            continue
        pending = list(predecessors[child] - {prior})
        visited = set()
        while pending:
            current = pending.pop()
            if current == prior:
                reasons.append("repeat_reference_kind_conflict")
                break
            if current not in visited:
                visited.add(current)
                pending.extend(predecessors[current])
    linked = {item for edge in edges for item in edge[1:3]}
    material = {
        "version": ("observation-relation-graph/v2" if origins is not None or any(len(edge) == 4 for edge in edges)
                    else "observation-relation-graph/v1"),
        "acquisition_groups": sorted(
            ({"group_id": group_ids[key], "fact_ids": members} for key, members in groups.items()),
            key=lambda item: item["group_id"],
        ),
        "repeat_edges": [{"repeat_group_id": child, "prior_group_id": prior,
                          **({"reference_kind": reference} if reference is not None else {})}
                         for child, prior, reference in sorted(
                             directed, key=lambda item: (item[0], item[1], item[2] or ""))],
        "unclassified_fact_ids": sorted(identifiers - linked),
        "structural_reasons": sorted(set(reasons)),
        "clinical_identity_verified": False, "replacement_authorized": False,
    }
    if origins is not None:
        material["source_origins"] = [{"fact_id": key, "role": value} for key, value in sorted(origins.items())]
        material["acquisition_roles"] = [
            {"group_id": key, "role": next(iter(values)) if len(values) == 1 else "unresolved"}
            for key, values in sorted(source_roles.items())
        ]
        material["origin_unresolved_fact_ids"] = sorted(item for key, members in groups.items()
            if len(source_roles[group_ids[key]]) != 1 for item in members)
    return {**material, "graph_sha256": canonical_hash(material)}
