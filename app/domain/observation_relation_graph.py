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


def observation_appearance_id(fact_id: str, locator_id: str) -> str:
    if not fact_id or not locator_id:
        raise ValueError("检查原文位置必须同时绑定事实与定位")
    return canonical_hash({
        "version": "observation-appearance/v1", "fact_id": fact_id,
        "locator_id": locator_id,
    })


def appearance_relationship_edge(key):
    relation, left, right, *reference = key
    if (relation not in {"same_acquisition", "repeat_of"}
            or not isinstance(left, (tuple, list)) or len(left) != 2
            or not isinstance(right, (tuple, list)) or len(right) != 2):
        raise ValueError("逐处检查关系须指向两端已冻结的事实与原文位置")
    return (relation, observation_appearance_id(*left),
            observation_appearance_id(*right), *reference)


def analyze_observation_appearances(appearances, relationships, *, origins=None):
    """Group source presentations; a presentation is not itself an acquisition."""
    indexed = {}
    for item in appearances:
        fact_id, locator_id = item["fact_id"], item["locator_id"]
        appearance_id = observation_appearance_id(fact_id, locator_id)
        if item.get("appearance_id") != appearance_id or appearance_id in indexed:
            raise ValueError("检查原文位置重复或与冻结来源身份不一致")
        indexed[appearance_id] = {"appearance_id": appearance_id,
                                  "fact_id": fact_id, "locator_id": locator_id}
    if not indexed:
        raise ValueError("检查原文位置不能为空")
    base = analyze_observation_relationships(
        sorted(indexed), relationships, origins=origins,
    )
    groups = []
    group_ids = {}
    for group in base["acquisition_groups"]:
        members = group["fact_ids"]
        group_id = canonical_hash({
            "version": "observation-acquisition-group/v2", "appearance_ids": members,
        })
        group_ids[group["group_id"]] = group_id
        groups.append({
            "group_id": group_id, "appearance_ids": members,
            "fact_ids": sorted({indexed[key]["fact_id"] for key in members}),
        })
    material = {
        "version": "observation-relation-graph/v3",
        "appearances": [indexed[key] for key in sorted(indexed)],
        "acquisition_groups": sorted(groups, key=lambda item: item["group_id"]),
        "repeat_edges": [{
            **edge, "repeat_group_id": group_ids[edge["repeat_group_id"]],
            "prior_group_id": group_ids[edge["prior_group_id"]],
        } for edge in base["repeat_edges"]],
        "unclassified_appearance_ids": base["unclassified_fact_ids"],
        "structural_reasons": base["structural_reasons"],
        "clinical_identity_verified": False, "replacement_authorized": False,
    }
    if origins is not None:
        unresolved = set(base["origin_unresolved_fact_ids"]) | (set(indexed) - set(origins))
        roles_by_group = {
            group_ids[item["group_id"]]: item["role"] for item in base["acquisition_roles"]
        }
        material["source_origins"] = [
            {"appearance_id": item["fact_id"], "role": item["role"]}
            for item in base["source_origins"]
        ]
        material["acquisition_roles"] = [
            {"group_id": item["group_id"],
             "role": ("unresolved" if set(item["appearance_ids"]) & unresolved
                      else roles_by_group[item["group_id"]])}
            for item in material["acquisition_groups"]
        ]
        material["origin_unresolved_appearance_ids"] = sorted(unresolved)
    return {**material, "graph_sha256": canonical_hash(material)}


def reused_fact_groups_follow_source_chain(graph) -> bool:
    """Same semantic fact may recur only along a quoted repeat chain."""
    if graph.get("version") != "observation-relation-graph/v3" or graph.get("structural_reasons"):
        return False
    by_fact = {}
    for group in graph["acquisition_groups"]:
        for fact_id in group["fact_ids"]:
            by_fact.setdefault(fact_id, set()).add(group["group_id"])
    predecessors = {}
    for edge in graph["repeat_edges"]:
        predecessors.setdefault(edge["repeat_group_id"], set()).add(edge["prior_group_id"])

    def ancestors(group_id):
        pending, visited = list(predecessors.get(group_id, ())), set()
        while pending:
            prior = pending.pop()
            if prior not in visited:
                visited.add(prior)
                pending.extend(predecessors.get(prior, ()))
        return visited

    return all(
        left in ancestors(right) or right in ancestors(left)
        for groups in by_fact.values() for left in groups for right in groups if left != right
    )
