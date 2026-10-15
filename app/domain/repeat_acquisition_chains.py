"""Separate explicitly linked acquisition chains; dates never create an edge."""
from app.domain.publication import canonical_hash


def decompose_repeat_chains(graph):
    if graph.get("graph_sha256") != canonical_hash({key: value for key, value in graph.items() if key != "graph_sha256"}):
        raise ValueError("检查对应内容已变化")
    trace = {"version": "repeat-acquisition-chains/v1", "graph_sha256": graph["graph_sha256"],
             "chains": [], "reason_codes": list(graph["structural_reasons"])}
    if trace["reason_codes"]:
        return trace
    groups = {item["group_id"] for item in graph["acquisition_groups"]}
    roles = {item["group_id"]: item["role"] for item in graph["acquisition_roles"]}
    if any(roles.get(key) not in {"initial", "repeat"} for key in groups):
        return {**trace, "reason_codes": ["repeat_origin_unverified"]}
    initials = {key for key in groups if roles[key] == "initial"}
    predecessors = {key: set() for key in groups}
    for edge in graph["repeat_edges"]:
        predecessors[edge["repeat_group_id"]].add(edge["prior_group_id"])
    chains = {key: [] for key in initials}
    for target in sorted(groups - initials):
        pending, ancestors = list(predecessors[target]), set()
        while pending:
            prior = pending.pop()
            if prior not in ancestors:
                ancestors.add(prior)
                pending.extend(predecessors[prior])
        roots = initials & ancestors
        if len(roots) != 1 or target in ancestors:
            return {**trace, "reason_codes": ["repeat_initial_correspondence_unverified"]}
        chains[next(iter(roots))].append(target)
    if not initials:
        return {**trace, "reason_codes": ["repeat_initial_scope_unverified"]}
    trace["chains"] = [{"initial_group_id": key, "repeat_group_ids": value} for key, value in sorted(chains.items())]
    return trace
