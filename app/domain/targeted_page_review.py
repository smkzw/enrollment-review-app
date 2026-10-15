"""Conservative comparison of auxiliary reads; never accepts clinical facts."""

from collections import defaultdict
import re

from app.domain.contracts.page_review import PageReviewLane
from app.domain.page_normalization import (
    normalize_field_name, normalize_text, observation_context_key, source_arrow_marks,
)


def _indexed(record):
    groups = defaultdict(list)
    for fact in record.facts:
        if fact.context is not None and normalize_text(fact.context.target_text):
            key = (normalize_field_name(fact.field_name),
                   observation_context_key(fact.context.model_dump()))
            groups[key].append(fact)
    return groups


def _value(fact):
    return fact.normalized_value, fact.normalized_unit, source_arrow_marks(fact.raw_value)


def _structured_value(fact):
    value = fact.normalized_value
    return bool(re.fullmatch(r"(?:<=|>=|<|>|≤|≥)?[+-]?(?:\d+(?:\.\d*)?|\.\d+)", value)
                or re.fullmatch(r"\d{4}-\d{2}(?:-\d{2}(?:T.*)?)?", value))


def validate_pair(records):
    if len(records) != 2 or {r.lane for r in records} != {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}:
        raise ValueError("复核必须绑定两个不同主读道")
    if len({(r.page_artifact_id, r.page_image_sha256, r.source_document_version_id,
             r.page_number, r.clause_pack_sha256) for r in records}) != 1:
        raise ValueError("复核原件或条款包不一致")


def explicit_conflict_fields(records):
    validate_pair(records)
    left, right = map(_indexed, records)
    conflicts = {key[0] for key in left.keys() & right.keys()
                         if len(left[key]) == len(right[key]) == 1
                         and _structured_value(left[key][0]) and _structured_value(right[key][0])
                         and _value(left[key][0]) != _value(right[key][0])}
    # A one-sided observation is a reread candidate, never proof of absence.
    fields = [{normalize_field_name(f.field_name) for f in record.facts}
              for record in records]
    one_sided = fields[0] ^ fields[1]
    missing = {normalize_field_name(f.field_name) for record in records for f in record.facts
               if normalize_field_name(f.field_name) in one_sided and _structured_value(f)}
    return tuple(sorted(conflicts | missing | missing_time_review_fields(records)))


def missing_time_review_fields(records):
    validate_pair(records)
    # Broaden reread eligibility only; full context is still required for agreement.
    groups = []
    for record in records:
        fields = defaultdict(list)
        for fact in record.facts:
            fields[normalize_field_name(fact.field_name)].append(fact)
        groups.append(fields)
    left, right = groups
    targets = set()
    for field in left.keys() & right.keys():
        if len(left[field]) != 1 or len(right[field]) != 1:
            continue
        a, b = left[field][0], right[field][0]
        if (a.context is None or b.context is None
                or not all(normalize_text(f.context.target_text) and _structured_value(f) for f in (a, b))
                or _value(a) != _value(b)):
            continue
        contexts = [f.context.model_dump() for f in (a, b)]
        times = [normalize_text(context.pop("time_text")) for context in contexts]
        if (bool(times[0]) != bool(times[1])
                and observation_context_key(contexts[0]) == observation_context_key(contexts[1])):
            targets.add(field)
    return targets


def compare_targeted_reads(records, targets, *, required_time_targets=()):
    validate_pair(records)
    required_times = {normalize_field_name(target) for target in required_time_targets}
    left, right = map(_indexed, records)
    agreed, pending = [], []
    for target in targets:
        field = normalize_field_name(target)
        a = {key: values for key, values in left.items() if key[0] == field}
        b = {key: values for key, values in right.items() if key[0] == field}
        # Empty or ambiguous observations are not evidence of absence or agreement.
        complete = all(f.context is not None and normalize_text(f.context.target_text) for r in records for f in r.facts
                       if normalize_field_name(f.field_name) == field)
        if field in required_times:
            complete = complete and all(
                f.context is not None and normalize_text(f.context.time_text)
                for record in records for f in record.facts
                if normalize_field_name(f.field_name) == field)
        equal = complete and bool(a) and a.keys() == b.keys() and all(
            len(a[key]) == len(b[key]) == 1 and _value(a[key][0]) == _value(b[key][0])
            for key in a)
        (agreed if equal else pending).append(target)
    return {"agreed_candidate_targets": agreed, "pending_targets": pending,
            "candidate_auto_accept": False}
