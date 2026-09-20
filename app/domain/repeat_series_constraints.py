"""Count and time checks for a source-qualified supplied acquisition graph."""
from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import TruthValue
from app.domain.expression import EvaluationResult
from app.domain.publication import canonical_hash
from app.domain.repeat_observation_count import evaluate_repeat_count
from app.domain.repeat_observation_time import evaluate_repeat_time_limit
from app.domain.repeat_acquisition_chains import decompose_repeat_chains


def calculate_repeat_series_constraints(
    scheme, graph, supplied_scope, *, fact_dates, qualified_date_fact_ids, anchor_dates,
    qualified_episode_memberships=None, episode_sha256=None,
):
    """No permission or result adoption is inferred from passing these checks.

    Date operands belong to the same rule's qualified pairs. Current-episode
    counting needs explicit episode membership, not merely shared upload scope.
    """
    if graph.get("graph_sha256") != canonical_hash({
        key: value for key, value in graph.items() if key != "graph_sha256"
    }):
        raise ValueError("复查对应内容已变化，不能计算次数和期限")
    groups = {item["group_id"]: set(item["fact_ids"]) for item in graph["acquisition_groups"]}
    all_facts = {key for values in groups.values() for key in values}
    if (supplied_scope.get("graph_sha256") != graph["graph_sha256"]
            or supplied_scope.get("scope") != "supplied_facts_only"
            or set(supplied_scope.get("fact_ids", ())) != all_facts
            or type(supplied_scope.get("complete")) is not bool):
        raise ValueError("复查计算与本次已核对资料范围不一致")
    roles = {item["group_id"]: item["role"] for item in graph.get("acquisition_roles", ())}
    repeats = tuple(sorted(key for key in groups if roles.get(key) == "repeat"))
    initials = {key for key in groups if roles.get(key) == "initial"}
    predecessors = {key: set() for key in groups}
    for edge in graph["repeat_edges"]:
        predecessors[edge["repeat_group_id"]].add(edge["prior_group_id"])

    def ancestors(key):
        pending, visited = list(predecessors[key]), set()
        while pending:
            prior = pending.pop()
            if prior not in visited:
                visited.add(prior)
                pending.extend(predecessors[prior])
        return visited

    def unknown(reason):
        return EvaluationResult(truth=TruthValue.UNKNOWN, reason_codes=[reason])

    structural = bool(graph["structural_reasons"])
    role_complete = all(roles.get(key) in {"initial", "repeat"} for key in groups)
    one_initial_series = (not structural and len(initials) == 1 and role_complete
                          and all(initials <= ancestors(key) for key in repeats))
    chains = decompose_repeat_chains(graph)
    count_by_initial = {}
    if (scheme.count_status == "specified" and scheme.count_scope == "per_initial_acquisition"
            and not chains["reason_codes"]):
        for chain in chains["chains"]:
            calculated = evaluate_repeat_count(
                scheme, repeat_group_ids=tuple(chain["repeat_group_ids"]), qualified_scope="per_initial_acquisition",
                scope_complete=supplied_scope["complete"] and role_complete,
            )
            count_by_initial[chain["initial_group_id"]] = {
                "repeat_group_ids": chain["repeat_group_ids"], "result": calculated.result.model_dump(mode="json"),
                "scope_complete": calculated.scope_complete,
            }
    count = None
    memberships = qualified_episode_memberships or {}
    if (not set(memberships) <= all_facts
            or any(value not in {"current_episode", "other_episode"} for value in memberships.values())):
        raise ValueError("复查节点归属必须对应本次已核实的原始记录")
    group_memberships = {
        key: (memberships[next(iter(ids))] if ids and ids <= set(memberships)
              and len({memberships[item] for item in ids}) == 1 else "unresolved")
        for key, ids in groups.items()
    }
    counted_repeats = repeats
    if structural:
        count_result = EvaluationResult(truth=TruthValue.UNKNOWN, reason_codes=graph["structural_reasons"])
    elif scheme.count_status == "specified" and scheme.count_scope == "per_current_episode":
        counted_repeats = tuple(key for key in repeats if group_memberships[key] == "current_episode")
        if not isinstance(episode_sha256, str) or len(episode_sha256) != 64:
            count_result = unknown("repeat_count_scope_unverified")
        else:
            count = evaluate_repeat_count(
                scheme, repeat_group_ids=counted_repeats, qualified_scope="per_current_episode",
                scope_complete=supplied_scope["complete"] and role_complete
                and all(value != "unresolved" for value in group_memberships.values()),
            )
            count_result = count.result
    elif scheme.count_status == "specified" and (
        scheme.count_scope != "per_initial_acquisition" or not one_initial_series
    ):
        count_result = unknown("repeat_count_scope_unverified")
    else:
        count = evaluate_repeat_count(
            scheme, repeat_group_ids=repeats, qualified_scope="per_initial_acquisition",
            scope_complete=supplied_scope["complete"] and role_complete,
        )
        count_result = count.result

    def group_date(key):
        ids = groups[key]
        if not ids or not ids <= qualified_date_fact_ids:
            return None
        values = [fact_dates.get(fact_id) for fact_id in sorted(ids)]
        if any(value is None for value in values):
            return None
        # Source wording may differ; compare the actual precision and date.
        identities = {canonical_hash(value.model_dump(mode="json", exclude={"source_text"}))
                      for value in values}
        return values[0] if len(identities) == 1 else None

    time_checks = []
    for target in repeats:
        reference_group = None
        reference = None
        observed = group_date(target)
        if structural:
            result = EvaluationResult(truth=TruthValue.UNKNOWN, reason_codes=graph["structural_reasons"])
        elif scheme.time_status == "not_specified":
            result = EvaluationResult(truth=TruthValue.TRUE, reason_codes=["repeat_time_not_specified"])
        elif scheme.time_status != "specified":
            result = unknown("repeat_time_reference_unverified")
        else:
            limit = scheme.time_limit
            if limit.reference == "episode_anchor":
                raw = anchor_dates.get(limit.episode_anchor)
                reference = DateValue.model_validate(raw) if raw is not None else None
            else:
                candidates = (initials & ancestors(target) if limit.reference == "initial_observation" else {
                    edge["prior_group_id"] for edge in graph["repeat_edges"]
                    if edge["repeat_group_id"] == target
                    and edge.get("reference_kind") == "preceding_observation"
                })
                if len(candidates) == 1:
                    reference_group = next(iter(candidates))
                    reference = group_date(reference_group)
            result = (unknown("repeat_time_reference_unverified") if reference is None else
                      unknown("repeat_date_unverified") if observed is None else
                      evaluate_repeat_time_limit(limit, observation_date=observed, reference_date=reference))
        time_checks.append({
            "repeat_group_id": target, "reference_group_id": reference_group,
            "observation_date": None if observed is None else observed.model_dump(mode="json"),
            "reference_date": None if reference is None else reference.model_dump(mode="json"),
            "result": result.model_dump(mode="json"),
        })
    return {
        "version": "repeat-series-constraints/v3", "scope": "supplied_facts_only",
        "scheme_sha256": canonical_hash(scheme.model_dump(mode="json")),
        "graph_sha256": graph["graph_sha256"], "supplied_scope_sha256": canonical_hash(supplied_scope),
        "observed_repeat_group_ids": list(repeats), "count_result": count_result.model_dump(mode="json"),
        "acquisition_chains": chains, "count_by_initial": count_by_initial,
        "counted_repeat_group_ids": list(counted_repeats),
        "episode_sha256": episode_sha256,
        "qualified_episode_memberships": dict(sorted(memberships.items())),
        "acquisition_episode_memberships": dict(sorted(group_memberships.items())),
        "count_scope_complete": False if count is None else count.scope_complete,
        "time_checks": time_checks,
        "time_scope_complete": supplied_scope["complete"] and role_complete and not structural,
        "replacement_authorized": False,
    }
