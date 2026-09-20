"""Conservative bounds over explicitly qualified occurrence identities."""
from dataclasses import dataclass
from datetime import date

from .occurrence_count_bounds import OccurrenceCountBounds


@dataclass(frozen=True)
class DistinctOccurrenceBounds:
    bounds: OccurrenceCountBounds | None
    groups: tuple[tuple[str, ...], ...]
    distinct_witness: tuple[str, ...]
    reason_codes: tuple[str, ...]


def bound_distinct_occurrences(
    occurrence_ids: list[str], *, same_pairs: list[tuple[str, str]],
    distinct_pairs: list[tuple[str, str]], enumeration_complete: bool,
) -> DistinctOccurrenceBounds:
    """Missing edges are unknown; distinctness is not transitive.

    A deterministic clique witness provides a sound lower bound without an
    exponential maximum-clique search. It need not be the tightest bound.
    enumeration_complete means the source establishes a complete enumeration,
    not merely that every uploaded page has been read.
    """
    ids = sorted(occurrence_ids)
    if (len(set(ids)) != len(ids) or any(not isinstance(item, str) or not item.strip() for item in ids)
            or type(enumeration_complete) is not bool):
        raise ValueError("发生次数须使用不同的已核实来源声明，并明确列举范围")
    parent = {item: item for item in ids}
    def root(item):
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item
    for pairs in (same_pairs, distinct_pairs):
        seen = set()
        for pair in pairs:
            if (len(pair) != 2 or pair[0] == pair[1] or not set(pair) <= set(ids)
                    or tuple(sorted(pair)) in seen):
                raise ValueError("同次或异次证明须指向本次两条不同声明且不得重复")
            seen.add(tuple(sorted(pair)))
    for left, right in same_pairs:
        low, high = sorted((root(left), root(right)))
        parent[high] = low
    grouped = {}
    for item in ids:
        grouped.setdefault(root(item), []).append(item)
    groups = tuple(tuple(values) for _, values in sorted(grouped.items()))
    adjacent = {key: set() for key in grouped}
    for left, right in distinct_pairs:
        left, right = root(left), root(right)
        if left == right:
            return DistinctOccurrenceBounds(None, groups, (), ("occurrence_identity_conflict",))
        adjacent[left].add(right)
        adjacent[right].add(left)
    witness = ()
    order = sorted(adjacent, key=lambda key: (-len(adjacent[key]), key))
    positions = {key: index for index, key in enumerate(order)}
    masks = [sum(1 << positions[other] for other in adjacent[key]) for key in order]
    for index, start in enumerate(order):
        clique, candidates = [start], masks[index]
        while candidates:
            position = (candidates & -candidates).bit_length() - 1
            clique.append(order[position])
            candidates &= masks[position]
        candidate_witness = tuple(sorted(clique))
        if len(candidate_witness) > len(witness) or (
            len(candidate_witness) == len(witness) and candidate_witness < witness
        ):
            witness = candidate_witness
    upper = len(groups) if enumeration_complete else None
    reasons = [] if enumeration_complete else ["occurrence_enumeration_incomplete"]
    if len(witness) < len(groups):
        reasons.append("occurrence_distinctness_unresolved")
    return DistinctOccurrenceBounds(OccurrenceCountBounds(len(witness), upper), groups, witness, tuple(reasons))


def bound_stated_total(
    count: int, *, stated_start: date, stated_end: date, required_start: date, required_end: date,
    count_relation: str = "eq",
) -> OccurrenceCountBounds | None:
    """Both inclusive intervals must already be source-qualified and exact.

    No period text parsing, guessed anchors, partial-date expansion, or
    unrelated event-kind conversion occurs here. Partial overlap yields no
    usable bound; zero is not substituted for unknown coverage.
    """
    if type(count) is not int or count < 0:
        raise ValueError("原文总数须为已核实的非负整数")
    if any(type(value) is not date for value in (stated_start, stated_end, required_start, required_end)):
        raise ValueError("总数期间比较须使用已核实的完整日期")
    if stated_start > stated_end or required_start > required_end:
        raise ValueError("计数期间不能倒置")
    if count_relation == "eq":
        stated = OccurrenceCountBounds(count, count)
    elif count_relation in {"gte", "gt"}:
        stated = OccurrenceCountBounds(count + (count_relation == "gt"), None)
    elif count_relation in {"lte", "lt"}:
        stated = OccurrenceCountBounds(0, count - (count_relation == "lt"))
    else:
        return None
    if (stated_start, stated_end) == (required_start, required_end):
        return stated
    if required_start <= stated_start and stated_end <= required_end:
        return OccurrenceCountBounds(stated.lower, None)
    if stated_start <= required_start and required_end <= stated_end:
        return OccurrenceCountBounds(0, stated.upper)
    return None
