"""Select source-declared acquisition groups, without inventing values or dates."""
from dataclasses import dataclass, field

from app.domain.contracts.repeat_scheme import RepeatScheme
from app.domain.contracts.enums import TruthValue
from app.domain.publication import canonical_hash


@dataclass(frozen=True)
class RepeatResultSelection:
    graph_sha256: str
    scheme_sha256: str
    supplied_scope_sha256: str
    considered_group_ids: tuple[str, ...]
    scope: str = field(default="supplied_facts_only", init=False)
    selected_group_ids: tuple[str, ...] = ()
    combination: str | None = None
    reason_codes: tuple[str, ...] = ()
    replacement_authorized: bool = field(default=False, init=False)


def select_repeat_result_groups(
    scheme: RepeatScheme, graph: dict, *, initial_group_id: str,
    repeat_group_ids: tuple[str, ...], scope_complete: bool, supplied_scope_sha256: str,
    initial_scope_complete: bool | None = None,
    absence_trigger_truth: TruthValue | None = None,
) -> RepeatResultSelection:
    """Caller proves scope, source qualification, permission, trigger and windows.

    scope_complete concerns the supplied review set, not all clinical history.
    Known missing source obligations remain separate and are never cleared here.
    This function only applies result-use policy to that supplied scope. It
    never uses chronology to invent links or picks a favorable clinical value.
    """
    if graph.get("graph_sha256") != canonical_hash({key: value for key, value in graph.items()
                                                  if key != "graph_sha256"}):
        raise ValueError("检查对应记录已变化，不能沿用原结果选择")
    if (not isinstance(supplied_scope_sha256, str) or len(supplied_scope_sha256) != 64
            or any(char not in "0123456789abcdef" for char in supplied_scope_sha256)):
        raise ValueError("结果选择须保留本次资料核对范围的依据")
    def result(**kwargs):
        return RepeatResultSelection(
            graph_sha256=graph["graph_sha256"],
            scheme_sha256=canonical_hash(scheme.model_dump(mode="json")),
            supplied_scope_sha256=supplied_scope_sha256,
            considered_group_ids=tuple(sorted((initial_group_id, *repeat_group_ids))), **kwargs,
        )

    groups = {item["group_id"] for item in graph["acquisition_groups"]}
    if (not isinstance(repeat_group_ids, tuple) or len(set(repeat_group_ids)) != len(repeat_group_ids)
            or initial_group_id not in groups or initial_group_id in repeat_group_ids
            or not set(repeat_group_ids) <= groups or type(scope_complete) is not bool):
        raise ValueError("结果选择须使用本次核实的初查及独立复查范围")
    if initial_scope_complete is not None and type(initial_scope_complete) is not bool:
        raise ValueError("初查范围须由本次原件核实")
    roles = {item["group_id"]: item["role"] for item in graph.get("acquisition_roles", ())}
    if not repeat_group_ids:
        if not scope_complete:
            return result(reason_codes=("repeat_result_scope_incomplete",))
        conditional = scheme.no_repeat_result_use == "retain_initial_when_trigger_false"
        if conditional and absence_trigger_truth != TruthValue.FALSE:
            return result(reason_codes=("repeat_result_required_not_supplied" if absence_trigger_truth == TruthValue.TRUE
                                        else "repeat_absence_trigger_unverified",))
        if scheme.no_repeat_result_use != "retain_initial" and not conditional:
            return result(reason_codes=("repeat_result_required_not_supplied" if scheme.no_repeat_result_use == "no_result"
                                        else "repeat_absence_policy_unverified",))
    if scheme.result_use == "retain_initial" or not repeat_group_ids:
        if roles.get(initial_group_id) != "initial" or initial_scope_complete is not True:
            return result(reason_codes=("repeat_initial_scope_unverified",))
        if repeat_group_ids:
            return result(selected_group_ids=(initial_group_id,))
    if graph["structural_reasons"]:
        return result(reason_codes=tuple(graph["structural_reasons"]))
    if roles.get(initial_group_id) != "initial" or any(roles.get(key) != "repeat" for key in repeat_group_ids):
        return result(reason_codes=("repeat_origin_unverified",))
    if not scope_complete:
        return result(reason_codes=("repeat_result_scope_incomplete",))
    predecessors = {key: set() for key in groups}
    for edge in graph["repeat_edges"]:
        predecessors[edge["repeat_group_id"]].add(edge["prior_group_id"])

    def ancestors(group_id):
        pending, visited = list(predecessors[group_id]), set()
        while pending:
            key = pending.pop()
            if key not in visited:
                visited.add(key)
                pending.extend(predecessors[key])
        return visited

    scope = {initial_group_id, *repeat_group_ids}
    if any(initial_group_id not in ancestors(key) or not ancestors(key) <= scope for key in repeat_group_ids):
        return result(reason_codes=("repeat_initial_correspondence_unverified",))
    if scheme.result_use == "retain_initial":
        return result(selected_group_ids=(initial_group_id,))
    if not repeat_group_ids:
        return result(selected_group_ids=(initial_group_id,))
    if scheme.result_use == "use_single_repeat":
        return (result(selected_group_ids=repeat_group_ids) if len(repeat_group_ids) == 1
                else result(reason_codes=("repeat_result_not_unique",)))
    if scheme.result_use == "use_last_repeat":
        last = [key for key in repeat_group_ids if set(repeat_group_ids) - {key} <= ancestors(key)]
        return (result(selected_group_ids=(last[0],)) if len(last) == 1
                else result(reason_codes=("repeat_last_observation_unverified",)))
    if scheme.result_use == "combine":
        if scheme.result_population not in {"initial_and_repeats", "repeats_only"}:
            return result(reason_codes=("repeat_result_population_unverified",))
        if scheme.result_combine in {None, "unresolved"}:
            return result(reason_codes=("repeat_result_combination_unverified",))
        selected = ((*repeat_group_ids, initial_group_id) if scheme.result_population == "initial_and_repeats"
                    else repeat_group_ids)
        return result(selected_group_ids=tuple(sorted(selected)), combination=scheme.result_combine)
    return result(reason_codes=("repeat_result_use_unverified",))
